#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logo coverage test (v19.1 Part L): which Korean and US stocks get a real logo from Brandfetch and logo.dev, by route.

  python3 tools/logo_test/run_test.py --dry-run                 # planned requests per route, no keys, no provider calls
  python3 tools/logo_test/run_test.py --self-test               # whole pipeline against a fake provider on 127.0.0.1
  BRANDFETCH_CLIENT_ID=… LOGODEV_TOKEN=pk_… python3 tools/logo_test/run_test.py --top 200      # pilot
  BRANDFETCH_CLIENT_ID=… LOGODEV_TOKEN=pk_… python3 tools/logo_test/run_test.py                # every ticker

How requests are made (both providers' rules, read 2026-11-04): their CDN images are for embedding in pages; scripted
downloads are not allowed (Brandfetch answers them with a 302 'automated_traffic'), so every logo here is an <img> load
from a local page (http://127.0.0.1, which sends a Referer) in Playwright's Chromium. Status, content type, bytes and a
sha256 come from the browser's response events; the image's natural size from the page. Images are NOT saved unless
--save-images is given (both providers ask you not to keep copies; see README.md).

  - Probe first: one well-known company per route (must be found, or that provider stops: bad key, blocked, …) and one
    nonsense identifier per route with the default fallback and with fallback=404, to record how "no logo" looks.
  - Main run uses fallback=404 (no logo -> HTTP 404). A 200 whose sha256 equals a probed fallback image also counts as
    "no logo" ('fallback').
  - Polite: Brandfetch ≤ 3 requests/s (its documented limit is 1,000 per 5 min per IP), logo.dev ≤ 5/s (Community
    plan: a per-minute limit with Retry-After, number not published), 4 in flight per provider. 429 / 5xx / timeouts
    are retried with backoff (Retry-After honoured); a refusal (bad key, hotlink or automated-traffic block, quota)
    stops that provider at once instead of hammering it.
  - Resumable: results.csv in the scratch folder is append-only; a rerun skips finished rows and retries the rest.
Outputs in the scratch folder: results.csv, probes.csv, summary.md (coverage per provider × route × market and the best
mix), mix.csv (the route the best mix picked for each ticker; contact_sheet.py reads it).
Keys come only from BRANDFETCH_CLIENT_ID and LOGODEV_TOKEN and are masked (***) in every line printed or written.
"""
import argparse
import asyncio
import base64
import collections
import csv
import hashlib
import pathlib
import random
import sys
import time

from logo_common import (BF_BASE, DEFAULT_MIX, ENV_BRANDFETCH, ENV_LOGODEV, FINAL_VERDICTS, HARNESS_HTML, LD_BASE,
                         MARKETS, PROBE_JS, PROVIDERS, RESULT_COLS, ROUTE_KEYS, ROUTES, Masker, browser_launch_args,
                         group_of, isin_check_digit, latest_results, log_factory, logo_url, now_kst, out_dir,
                         read_csv, read_keys, route_ident, serve, shared_image_hashes, summarize, write_csv)

RATE = {"brandfetch": 3.0, "logodev": 5.0}
CONC = 4
BATCH = 40
TIMEOUT_MS = 20000
MAX_TRIES = 5
PENDING_WAIT_S = 330            # logo.dev 202: "usually ready within a minute", the placeholder is cached 5 minutes
RELOAD_EVERY = 1000             # reload the page now and then so the browser does not grow

# Probe identifiers: (route, known company, nonsense). The nonsense ISIN has a valid check digit but no issuer.
_NONSENSE_ISIN = "KR799999900" + isin_check_digit("KR799999900")
_PROBE_SET = [("ticker", "AAPL", "ZZQXJ9"), ("isin", "US0378331005", _NONSENSE_ISIN),
              ("domain", "apple.com", "no-such-brand-baepsae-test.com")]
PROBES = {"brandfetch": _PROBE_SET, "logodev": _PROBE_SET}
# Brandfetch refusals (x-bf-error, docs.brandfetch.com/logo-api/guidelines): any of these stops Brandfetch at once.
BF_FATAL = {"client_id_invalid_signature", "client_id_disabled", "region_unavailable", "client_id_expired",
            "quota_exceeded", "rate_limited", "client_id_required", "user_agent_required", "hotlink_blocked",
            "automated_traffic"}
PROBE_COLS = ["provider", "route", "ident", "fallback", "status", "content_type", "bytes", "sha256", "w", "h",
              "x_bf_error", "verdict", "referer"]


def classify(provider, status, headers, js, sha, fallback_hashes):
    """One image load -> (verdict, retry_after_seconds or None, fatal reason or None). Pure.
    verdict: hit · miss · fallback · bad_request (final) | pending · error · rate_limited (retried)."""
    h = {k.lower(): v for k, v in (headers or {}).items()}
    bf_err = h.get("x-bf-error", "") if provider == "brandfetch" else ""
    ra = h.get("retry-after")
    try:
        ra = float(ra) if ra is not None else None
    except ValueError:
        ra = None
    if status is None:
        return "error", None, None
    if bf_err in BF_FATAL:
        return "error", None, f"Brandfetch refused the request: HTTP {status}, x-bf-error {bf_err}"
    if status in (401, 403, 410):
        return "error", None, f"HTTP {status} (key missing, invalid, disabled, domain-restricted or account paused)"
    if status == 429:
        if ra is not None and ra > 600:
            return "error", None, f"HTTP 429 with Retry-After {ra:.0f}s (monthly allowance used up?)"
        return "rate_limited", ra if ra is not None else 30.0, None
    if status in (200, 203, 202):
        ok = bool(js and js.get("ok"))
        if sha and sha in fallback_hashes:
            return ("pending" if status == 202 else "fallback"), (PENDING_WAIT_S if status == 202 else None), None
        if status == 202:
            return "pending", PENDING_WAIT_S, None
        return ("hit" if ok else "error"), None, None
    if status == 404:
        return "miss", None, None
    if status == 400:
        return "bad_request", None, None
    if status >= 500:
        return "error", ra, None
    return "error", None, None


class NetCapture:
    """Status, headers and body of each image load, from the page's DevTools network events. Playwright's own response
    events are not enough: Chromium's opaque-response blocking (ORB) hides a cross-origin JSON error (logo.dev 400/401,
    Brandfetch 403) from them, so a bad key would look like a network error. The raw-header event still carries the
    status and the x-bf-error header. For a redirect (Brandfetch's 302 refusals) the first hop is what counts."""

    def __init__(self, cdp):
        self.cdp, self.req, self.by_url = cdp, {}, {}
        cdp.on("Network.requestWillBeSent", self._sent)
        cdp.on("Network.responseReceivedExtraInfo", self._extra)
        cdp.on("Network.responseReceived", self._received)
        cdp.on("Network.loadingFinished", lambda ev: self._end(ev, None))
        cdp.on("Network.loadingFailed", lambda ev: self._end(ev, ev.get("blockedReason") or ev.get("errorText") or "failed"))

    @classmethod
    async def attach(cls, context, page):
        cdp = await context.new_cdp_session(page)
        cap = cls(cdp)
        await cdp.send("Network.enable")
        await cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})      # every load is a real request
        return cap

    def _first(self, rec, status, headers):
        if rec is not None and rec["status"] is None:
            rec["status"], rec["headers"] = status, dict(headers or {})

    def _sent(self, ev):
        rid = ev["requestId"]
        if ev.get("redirectResponse") and rid in self.req:
            rec = self.req[rid]
            self._first(rec, ev["redirectResponse"].get("status"), ev["redirectResponse"].get("headers"))
            rec["redirected"] = True
            return
        url = ev["request"]["url"]
        ref = {str(k).lower(): v for k, v in (ev["request"].get("headers") or {}).items()}.get("referer", "")
        self.req[rid] = {"url": url, "status": None, "headers": {}, "mime": "", "redirected": False, "done": False,
                         "failure": None, "referer": ref}
        self.by_url[url] = rid

    def _extra(self, ev):
        self._first(self.req.get(ev["requestId"]), ev.get("statusCode"), ev.get("headers"))

    def _received(self, ev):
        rec = self.req.get(ev["requestId"])
        if rec is not None:
            self._first(rec, ev["response"].get("status"), ev["response"].get("headers"))
            rec["mime"] = rec["mime"] or ev["response"].get("mimeType", "")

    def _end(self, ev, failure):
        rec = self.req.get(ev["requestId"])
        if rec is not None:
            rec["done"], rec["failure"] = True, failure

    async def take(self, url, settle_s=3.0):
        """(record, body bytes or None) for the last load of url, or (None, None) when the page never asked for it."""
        t_end = time.monotonic() + settle_s
        while True:
            rid = self.by_url.get(url)
            rec = self.req.get(rid) if rid else None
            if (rec and rec["done"]) or time.monotonic() > t_end:
                break
            await asyncio.sleep(0.05)
        if rec is None:
            return None, None
        self.by_url.pop(url, None)
        self.req.pop(rid, None)
        body = None
        if rec["done"] and not rec["failure"] and not rec["redirected"]:
            try:
                r = await self.cdp.send("Network.getResponseBody", {"requestId": rid})
                body = base64.b64decode(r["body"]) if r.get("base64Encoded") else r["body"].encode("utf-8")
            except Exception:                                   # noqa: BLE001 — e.g. no body kept for an empty 404
                body = None
        return rec, body


async def measure(page, cap, lane, urls, rate, conc):
    """Load urls as <img> on the page; one info dict per url (status, headers, content type, bytes, sha256, size)."""
    js = await page.evaluate("([lane, urls, rate, conc, t]) => window.probe(lane, urls, rate, conc, t)",
                             [lane, urls, rate, conc, TIMEOUT_MS])
    out = []
    for u, j in zip(urls, js):
        rec, body = await cap.take(u)
        hdr = {str(k).lower(): v for k, v in ((rec or {}).get("headers") or {}).items()}
        info = {"status": (rec or {}).get("status"), "headers": hdr, "content_type": hdr.get("content-type", ""),
                "bytes": "", "sha256": "", "body": None, "w": (j or {}).get("w", 0), "h": (j or {}).get("h", 0),
                "js": j, "failure": (rec or {}).get("failure") if rec else "the page made no request",
                "referer": (rec or {}).get("referer", "")}
        if body is not None:
            info["bytes"], info["sha256"], info["body"] = len(body), hashlib.sha256(body).hexdigest(), body
        elif info["status"] == 404:
            info["bytes"] = 0
        out.append(info)
    return out


class Lane:
    """One provider: its page, its pace, its results."""

    def __init__(self, provider, page, cap, key, args, masker, log, writer):
        self.p, self.page, self.cap, self.key, self.a = provider, page, cap, key, args
        self.mask, self.log, self.writer = masker, log, writer
        self.rate = args.bf_rate if provider == "brandfetch" else args.ld_rate
        self.fallback_hashes = set()
        self.stopped = None
        self.done = 0
        self.consecutive_errors = 0
        self.bases = {"bf_base": args.bf_base, "ld_base": args.ld_base}
        self.probe_infos = {}

    def url(self, route, ident, fallback404=True, bust=None):
        u = logo_url(self.p, route, ident, self.key, fallback404=fallback404, **self.bases)
        # A recheck after logo.dev's 202 needs a new URL: the browser keeps the 202 image in memory under the old one.
        # logo.dev's caching docs name an extra v= parameter as the way to get a fresh copy.
        return u + f"&v={bust}" if bust and self.p == "logodev" else u

    async def load(self, urls):
        """Measure urls; one the probe already loaded (the known company's ticker URL) is answered from the probe,
        because the browser would serve it from memory without a request."""
        todo = [u for u in dict.fromkeys(urls) if u not in self.probe_infos]
        got = dict(zip(todo, await measure(self.page, self.cap, self.p, todo, self.rate, self.a.concurrency))) if todo else {}
        return [got[u] if u in got else self.probe_infos[u] for u in urls]

    async def probe(self, probe_rows):
        """Known company + nonsense identifier per route. Returns False (and sets self.stopped) when the known company
        is not found on the ticker route, or any probe is refused."""
        plan = []
        for route, good, bad in PROBES[self.p]:
            plan += [(route, good, True, "known company"), (route, bad, False, "default"), (route, bad, True, "404")]
        urls = [self.url(r, i, fallback404=f) for r, i, f, _ in plan]
        infos = await self.load(urls)
        self.probe_infos = {u: info for u, info in zip(urls, infos) if info["status"] in (200, 404)}
        ok_good = {}
        for (route, ident, f404, kind), info in zip(plan, infos):
            verdict, _, fatal = classify(self.p, info["status"], info["headers"], info["js"], info["sha256"], set())
            if kind == "default" and info["status"] == 200 and info["sha256"]:
                self.fallback_hashes.add(info["sha256"])
                verdict = "fallback image"
            if kind == "known company":
                ok_good[route] = verdict == "hit"
            probe_rows.append({"provider": self.p, "route": route, "ident": ident,
                               "fallback": "default" if not f404 else ("404" if kind == "404" else "404 (known company)"),
                               "status": info["status"] if info["status"] is not None else f"none ({info['failure']})",
                               "content_type": info["content_type"], "bytes": info["bytes"],
                               "sha256": info["sha256"][:16], "w": info["w"], "h": info["h"],
                               "x_bf_error": info["headers"].get("x-bf-error", ""),
                               "verdict": verdict, "referer": info["referer"]})
            if fatal:
                self.stopped = f"probe {route} {ident}: {fatal}"
        if not self.stopped and not ok_good.get("ticker"):
            self.stopped = (f"probe: the known company (AAPL) was not found on the ticker route — key, Referer or "
                            f"block problem; see probes.csv")
        for route, good in ok_good.items():
            if not good:
                self.log(f"!! {self.p}: probe {route}: the known company was not found on this route")
        self.log(f"· {self.p}: probe done · fallback images seen: {len(self.fallback_hashes)}"
                 + (f" · STOPPED: {self.stopped}" if self.stopped else ""))
        return not self.stopped

    async def run(self, items):
        """items: list of dicts {row, route, ident, tries}. Writes one results row per finished load."""
        queue = collections.deque(items)
        later = []                                              # (not_before, item)
        since_reload = 0
        while (queue or later) and not self.stopped:
            now = time.monotonic()
            ready = [x for x in later if x[0] <= now]
            for x in ready:
                later.remove(x)
                queue.append(x[1])
            if not queue:
                await asyncio.sleep(min(5.0, max(0.1, min(x[0] for x in later) - now)))
                continue
            batch = [queue.popleft() for _ in range(min(BATCH, len(queue)))]
            urls = [self.url(it["route"], it["ident"], bust=it.get("bust")) for it in batch]
            infos = await self.load(urls)
            since_reload += len(batch)
            pause = 0.0
            for it, u, info in zip(batch, urls, infos):
                it["tries"] += 1
                verdict, retry_after, fatal = classify(self.p, info["status"], info["headers"], info["js"],
                                                       info["sha256"], self.fallback_hashes)
                if fatal:
                    self.stopped = fatal
                retry = verdict not in FINAL_VERDICTS and not fatal and it["tries"] < MAX_TRIES
                self.consecutive_errors = self.consecutive_errors + 1 if verdict in ("error", "rate_limited") else 0
                if verdict == "rate_limited":
                    pause = max(pause, retry_after or 30.0)
                    self.rate = max(0.5, self.rate * 0.7)
                if verdict == "pending":
                    it["bust"] = it["tries"] + 1
                if retry:
                    wait = retry_after if retry_after is not None else min(60.0, 2.0 ** it["tries"]) + random.random()
                    later.append((time.monotonic() + wait, it))
                self.writer(self.result_row(it, verdict, info, u))
                if verdict == "hit" and self.a.save_images and info["body"]:
                    self.save(it, info)
                self.done += 1
            if self.consecutive_errors >= 25 and not self.stopped:
                self.stopped = f"{self.consecutive_errors} errors in a row (last status {infos[-1]['status']})"
            if pause:
                self.log(f"· {self.p}: HTTP 429 — waiting {pause:.0f}s, rate now {self.rate:.2f}/s")
                await asyncio.sleep(pause)
            if since_reload >= RELOAD_EVERY:
                await self.page.reload()
                since_reload = 0
            if self.done % 200 < len(batch):
                self.log(f"· {self.p}: {self.done:,} loads done · queue {len(queue):,} · retry later {len(later):,}")
        if self.stopped:
            self.log(f"!! {self.p}: STOPPED — {self.stopped}")

    def result_row(self, it, verdict, info, url):
        h = {k.lower(): v for k, v in info["headers"].items()}
        return {"code": it["row"]["code"], "provider": self.p, "route": it["route"], "ident": it["ident"],
                "verdict": verdict, "status": "" if info["status"] is None else info["status"],
                "content_type": info["content_type"], "bytes": info["bytes"], "sha256": info["sha256"],
                "w": info["w"], "h": info["h"], "x_bf_error": h.get("x-bf-error", ""), "tries": it["tries"],
                "url": self.mask(url), "at": now_kst().isoformat(timespec="seconds")}

    def save(self, it, info):
        ext = {"image/png": "png", "image/webp": "webp", "image/jpeg": "jpg", "image/svg+xml": "svg"}.get(
            info["content_type"].split(";")[0].strip(), "img")
        d = self.a.out / "images" / f"{self.p}_{it['route']}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{it['row']['code']}.{ext}").write_bytes(info["body"])


def select_rows(tickers, top=None, markets=None):
    rows = tickers
    if top:
        rows = [t for t in rows if t.get("rank_cls") and int(t["rank_cls"]) <= top]
    if markets:
        rows = [t for t in rows if group_of(t) in markets]
    return rows


def plan_items(rows, routes, latest):
    """(provider -> items) for every applicable route not already finished in results.csv."""
    out = {p: [] for p in PROVIDERS}
    skipped = 0
    for t in rows:
        for p, r, _ in ROUTES:
            if f"{p}:{r}" not in routes:
                continue
            ident = route_ident(t, p, r)
            if not ident:
                continue
            prev = latest.get((t["code"], p, r))
            if prev and prev["verdict"] in FINAL_VERDICTS:
                skipped += 1
                continue
            out[p].append({"row": t, "route": r, "ident": ident, "tries": 0})
    return out, skipped


def plan_table(rows, routes):
    groups = MARKETS + ["ETF/fund"]
    lines = ["| route | " + " | ".join(groups) + " | total |", "|---|" + "---|" * (len(groups) + 1)]
    totals = collections.Counter()
    for key in ROUTE_KEYS:
        if key not in routes:
            continue
        p, r = key.split(":")
        n = collections.Counter(group_of(t) for t in rows if route_ident(t, p, r))
        totals[p] += sum(n.values())
        lines.append(f"| {key} | " + " | ".join(f"{n[g]:,}" for g in groups) + f" | {sum(n.values()):,} |")
    return lines, totals


async def browser_check(args, log):
    """Dry run only: the harness page loads ONE non-provider image (this site's own icon) through the browser and the
    session proxy, to show that the measuring path works. No provider is contacted."""
    from playwright.async_api import async_playwright
    harness = args.out / "harness"
    harness.mkdir(parents=True, exist_ok=True)
    (harness / "index.html").write_text(HARNESS_HTML, encoding="utf-8")
    base, stop = serve({"/": harness})
    url = "https://jacksungjinlee.github.io/baepsae/icon-192.png"
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**browser_launch_args(args.headed))
            context = await browser.new_context()
            await context.add_init_script(PROBE_JS)
            page = await context.new_page()
            cap = await NetCapture.attach(context, page)
            await page.goto(base + "/index.html")
            info = (await measure(page, cap, "check", [url], 1, 1))[0]
            log(f"· browser check (not a provider): {url} -> HTTP {info['status']}, {info['bytes']} bytes, "
                f"{info['content_type']}, decoded {info['js']['ok']}, {info['w']}×{info['h']}, "
                f"Referer sent: {info['referer'] or 'none'}")
            await browser.close()
            return bool(info["status"] == 200 and info["js"]["ok"] and info["bytes"] and info["referer"].startswith(base))
    finally:
        stop()


async def run_live(args, keys, tickers, rows, routes, log, masker):
    from playwright.async_api import async_playwright
    out = args.out
    harness = out / "harness"
    harness.mkdir(parents=True, exist_ok=True)
    (harness / "index.html").write_text(HARNESS_HTML, encoding="utf-8")
    results_path = out / "results.csv"
    prev = read_csv(results_path) if results_path.exists() else []
    latest = latest_results(prev)
    items, skipped = plan_items(rows, routes, latest)
    if skipped:
        log(f"· resuming: {skipped:,} loads already finished in {results_path} are skipped")
    new_file = not results_path.exists()
    fh = open(results_path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=RESULT_COLS, extrasaction="ignore")
    if new_file:
        w.writeheader()

    def writer(row):
        w.writerow({k: masker(v) if isinstance(v, str) else v for k, v in row.items()})
        fh.flush()

    base, stop = serve({"/": harness})
    probe_rows, stopped = [], {}
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**browser_launch_args(args.headed))
            context = await browser.new_context()
            await context.add_init_script(PROBE_JS)
            lanes = []
            for p in args.providers:
                page = await context.new_page()
                cap = await NetCapture.attach(context, page)
                await page.goto(base + "/index.html")
                lanes.append(Lane(p, page, cap, keys[p], args, masker, log, writer))
            ok = await asyncio.gather(*(ln.probe(probe_rows) for ln in lanes))
            runnable = [ln for ln, good in zip(lanes, ok) if good]
            for ln in lanes:
                n = len(items[ln.p])
                log(f"· {ln.p}: {n:,} loads planned at ≤ {ln.rate:g}/s (≈ {n / ln.rate / 60:.0f} min)"
                    + ("" if ln in runnable else " — not run (probe failed)"))
            t0 = time.monotonic()
            await asyncio.gather(*(ln.run(items[ln.p]) for ln in runnable))
            log(f"· main run took {(time.monotonic() - t0) / 60:.1f} min")
            stopped = {ln.p: ln.stopped for ln in lanes if ln.stopped}
            await browser.close()
    finally:
        stop()
        fh.close()
    write_csv(out / "probes.csv", probe_rows, PROBE_COLS)
    return probe_rows, stopped


def write_outputs(args, tickers, rows, probe_rows, stopped, log, notes):
    results_path = args.out / "results.csv"
    latest = latest_results(read_csv(results_path)) if results_path.exists() else {}
    order = args.mix_order
    shared = shared_image_hashes(rows, latest)
    md, mix_rows = summarize(rows, latest, order, notes=notes, probes=probe_rows, stopped=stopped, shared_hashes=shared)
    (args.out / "summary.md").write_text(md, encoding="utf-8")
    by_code = {t["code"]: t for t in rows}
    mix_out = []
    for m in mix_rows:
        t = by_code[m["code"]]
        src = m["via_code"] or m["code"]
        p, r = m["pick"].split(":") if m["pick"] else ("", "")
        ident = latest[(src, p, r)]["ident"] if m["pick"] else ""
        mix_out.append({"code": m["code"], "name": t["name"], "market": t["market"], "etf": t["etf"], "cap": t["cap"],
                        "rank_cls": t["rank_cls"], "provider": p, "route": r, "ident": ident, "via_code": m["via_code"]})
    write_csv(args.out / "mix.csv", mix_out,
              ["code", "name", "market", "etf", "cap", "rank_cls", "provider", "route", "ident", "via_code"])
    log(f"wrote {args.out / 'summary.md'} · {args.out / 'mix.csv'} · {results_path}")
    return md


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tickers", default=None, help="tickers.csv (default: <out>/tickers.csv from build_tickers.py)")
    ap.add_argument("--out", default=None, help="scratch folder outside the repository (default: LOGO_TEST_DIR or "
                                                "the session scratchpad /logos)")
    ap.add_argument("--dry-run", action="store_true", help="print the planned requests per route and exit")
    ap.add_argument("--no-browser-check", action="store_true", help="dry run: skip the one-image browser check")
    ap.add_argument("--self-test", action="store_true", help="run everything against a fake provider on 127.0.0.1")
    ap.add_argument("--top", type=int, default=None, help="only the N largest of each side (KR, US) by market cap")
    ap.add_argument("--markets", default="", help="comma list of KOSPI,KOSDAQ,KONEX,US,ETF/fund (default: all)")
    ap.add_argument("--providers", default="brandfetch,logodev")
    ap.add_argument("--routes", default=",".join(ROUTE_KEYS), help="comma list of provider:route")
    ap.add_argument("--mix-order", default=",".join(DEFAULT_MIX), help="best-mix order, comma list of provider:route")
    ap.add_argument("--bf-rate", type=float, default=RATE["brandfetch"], help="Brandfetch loads per second (≤ 3.3)")
    ap.add_argument("--ld-rate", type=float, default=RATE["logodev"], help="logo.dev loads per second")
    ap.add_argument("--concurrency", type=int, default=CONC, help="loads in flight per provider")
    ap.add_argument("--save-images", action="store_true",
                    help="also keep each found logo in <out>/images (off by default: both providers ask you not to "
                         "keep copies; delete them after the review)")
    ap.add_argument("--headed", action="store_true", help="show the browser window (needs a display)")
    ap.add_argument("--bf-base", default=BF_BASE, help=argparse.SUPPRESS)
    ap.add_argument("--ld-base", default=LD_BASE, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    a.providers = [p.strip() for p in a.providers.split(",") if p.strip()]
    bad = [p for p in a.providers if p not in PROVIDERS]
    a.routes = {r.strip() for r in a.routes.split(",") if r.strip()}
    a.mix_order = [r.strip() for r in a.mix_order.split(",") if r.strip()]
    bad += [r for r in a.routes | set(a.mix_order) if r not in ROUTE_KEYS]
    if bad:
        ap.error(f"unknown provider or route: {bad} (routes: {', '.join(ROUTE_KEYS)})")
    a.routes = {r for r in a.routes if r.split(":")[0] in a.providers}
    a.markets = {m.strip() for m in a.markets.split(",") if m.strip()}
    if a.bf_rate > 3.3:
        ap.error("--bf-rate above 3.3/s breaks Brandfetch's documented 1,000 requests per 5 minutes per IP")
    return a


def main(argv=None):
    a = parse_args(argv)
    if a.self_test:
        import selftest_fake
        return selftest_fake.run(a)
    a.out = out_dir(a.out)
    keys, missing = read_keys(a.providers)
    masker = Masker(keys["brandfetch"], keys["logodev"])
    log = log_factory(masker)
    tpath = pathlib.Path(a.tickers) if a.tickers else a.out / "tickers.csv"
    if not tpath.exists():
        raise SystemExit(f"!! {tpath} not found — run build_tickers.py first")
    tickers = read_csv(tpath)
    rows = select_rows(tickers, a.top, a.markets)
    lines, totals = plan_table(rows, a.routes)
    log(f"· {len(rows):,} of {len(tickers):,} tickers selected" + (f" (top {a.top} of each side)" if a.top else ""))
    if a.dry_run:
        prev = read_csv(a.out / "results.csv") if (a.out / "results.csv").exists() else []
        items, skipped = plan_items(rows, a.routes, latest_results(prev))
        for line in lines:
            log(line)
        for p in a.providers:
            n = len(items[p])
            rate = a.bf_rate if p == "brandfetch" else a.ld_rate
            log(f"· {p}: {totals[p]:,} loads planned (+{3 * len(PROBES[p])} probe loads) · {n:,} still to do · at ≤ "
                f"{rate:g}/s ≈ {n / rate / 60:.0f} min")
        log(f"· already finished in results.csv: {skipped:,}")
        log("· keys: " + ("none missing" if not missing else "missing " + ", ".join(missing))
            + " (dry run needs none; values are never printed)")
        if not a.no_browser_check:
            ok = asyncio.run(browser_check(a, log))
            if not ok:
                log("!! browser check failed: Chromium could not load a plain image through the page")
                return 1
        log("dry run: no provider was contacted")
        return 0
    if missing:
        raise SystemExit(f"!! missing environment variables: {', '.join(missing)} (see tools/logo_test/KEYS.md)")
    notes = [f"tickers.csv: {tpath} ({len(tickers):,} rows, {len(rows):,} selected"
             + (f", top {a.top} of each side" if a.top else "") + ")",
             f"providers {', '.join(a.providers)} · rates Brandfetch ≤ {a.bf_rate:g}/s, logo.dev ≤ {a.ld_rate:g}/s · "
             f"loaded as <img> in Chromium from http://127.0.0.1 · fallback=404"]
    probe_rows, stopped = asyncio.run(run_live(a, keys, tickers, rows, a.routes, log, masker))
    md = write_outputs(a, tickers, rows, probe_rows, stopped, log, notes)
    print(masker(md))
    return 0 if not stopped else 2


if __name__ == "__main__":
    sys.exit(main())
