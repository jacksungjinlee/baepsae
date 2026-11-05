#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test for logo-test.html (the temporary logo coverage test page): python tests/smoke_logo_test.py [PAGE]

Both providers' terms forbid loading their logo images from a script or a headless browser, so here NO request ever
reaches cdn.brandfetch.io or img.logo.dev: Chromium starts without a proxy, and every request to those hosts is
stopped inside the browser — aborted (scenarios A–C) or answered by a fake inside the browser (D). Any other outside
request is aborted too and fails the test. Keys in the page are never printed.

  A  blocked, checks on        both providers stop at the known-logo check (2 requests each); nothing counted as a miss
  B  blocked, checks off       every applicable route is one request and counts as a miss; the requested URLs are exactly
                               the ones tools/logos/logo_ids.logo_url builds for the embedded sample (same keys)
  C  blocked, real pace        Brandfetch ≥ 0.5 s and logo.dev ≥ 0.25 s between request starts
  D  fake answers (in-browser) hits, misses, logo.dev's first-request placeholder (202) caught by the second load,
                               one request at a time per route (answers take 20-60 ms), counts equal the expected ones
Zero page errors in every scenario; screenshots (phone and PC) go to SMOKE_OUT, else a new temporary folder.
"""
import asyncio
import base64
import collections
import hashlib
import http.server
import json
import os
import pathlib
import re
import socketserver
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))
from logo_ids import Masker, logo_url  # noqa: E402

PROVIDER_HOSTS = {"cdn.brandfetch.io", "img.logo.dev"}
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAAB"
                       "JRU5ErkJggg==")
ROUTES = [("bfI", "bf", "isin", "isin"), ("bfT", "bf", "ticker", "tk"), ("ldT", "ld", "ticker", "tk"),
          ("bfD", "bf", "domain", "dom"), ("ldD", "ld", "domain", "dom")]
PROV = {"bf": "brandfetch", "ld": "logodev"}


def page_parts(html):
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    keys = json.loads(re.search(r"var KEYS = (\{.*?\});", html).group(1))
    return data, keys


def serve(folder):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(folder), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", httpd


def classify_url(url):
    """(provider, route, ident, v) for a provider URL."""
    u = urlparse(url)
    qs = parse_qs(u.query)
    parts = [unquote(p) for p in u.path.split("/") if p]
    if u.hostname == "cdn.brandfetch.io":
        return "bf", parts[0], parts[1], None
    if parts[0] in ("ticker", "isin"):
        return "ld", parts[0], parts[1], (qs.get("v") or [None])[0]
    return "ld", "domain", parts[0], (qs.get("v") or [None])[0]


def h(*xs):
    return int(hashlib.sha1("|".join(str(x) for x in xs).encode()).hexdigest(), 16)


class Fake:
    """The fake provider: known logos load, made-up identifiers give 404, the rest by a fixed hash. logo.dev answers a
    domain's first request with a 202 placeholder image; the second load (v=2) is the real answer."""

    def __init__(self, meta, ld_domain_always=False):
        self.good = set(meta["good"].values()) | set(meta["rotate"])
        self.bad = set(meta["bad"].values())
        self.ld_domain_always = ld_domain_always          # E: logo.dev answers every domain with an image

    def control(self, ident):
        return ident in self.good or ident in self.bad or ident.startswith("ZZQX")

    def image(self, p, r, ident, v):
        if p == "ld" and r == "domain" and (not v or self.ld_domain_always):
            return True
        if ident in self.good:
            return True
        if ident in self.bad or ident.startswith("ZZQX"):
            return False
        if p == "ld" and r == "domain":
            return h("ldD", ident) % 2 == 0
        return h(p, r, ident) % 3 != 0 if p == "bf" else h(p, r, ident) % 2 == 0


class Run:
    def __init__(self, mode, fake=None):
        self.mode, self.fake = mode, fake
        self.reqs, self.other, self.errors = [], [], []
        self.inflight, self.max_inflight = collections.Counter(), collections.Counter()

    async def open(self, browser, base, cfg, viewport=(390, 844)):
        self.ctx = await browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                             service_workers="block")    # no worker can fetch past ctx.route
        await self.ctx.route("**/*", self.on_route)
        self.page = await self.ctx.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        await self.page.add_init_script("window.__LOGO_TEST_CONFIG = " + json.dumps(cfg) + ";")
        await self.page.goto(base + "/logo-test.html", wait_until="domcontentloaded")   # images keep 'load' waiting
        return self

    async def on_route(self, route):
        req = route.request
        host = urlparse(req.url).hostname
        if host == "127.0.0.1":
            await route.continue_()
            return
        if host not in PROVIDER_HOSTS:
            self.other.append(host)
            await route.abort()
            return
        p, r, ident, v = classify_url(req.url)
        self.reqs.append((time.monotonic(), p, r, ident, v, req.url))
        if self.mode != "fake":
            await route.abort()
            return
        lane = None if self.fake.control(ident) else p + r      # checks run beside the route lanes by design
        if lane:
            self.inflight[lane] += 1
            self.max_inflight[lane] = max(self.max_inflight[lane], self.inflight[lane])
        await asyncio.sleep(0.02 + (h(req.url) % 40) / 1000)
        if lane:
            self.inflight[lane] -= 1
        if self.fake.image(p, r, ident, v):
            await route.fulfill(status=202 if (p == "ld" and r == "domain" and not v) else 200,
                                content_type="image/png", body=PNG)
        else:
            await route.fulfill(status=404, body=b"")

    async def wait_finished(self, timeout_s):
        t_end = time.monotonic() + timeout_s
        while time.monotonic() < t_end:
            if await self.page.evaluate("window.__logoTest.finished()"):
                return True
            await asyncio.sleep(0.25)
        return False

    async def states(self):
        return await self.page.evaluate("(() => { const o = {}; const s = window.__logoTest.state;"
                                        " for (const k in s) o[k] = s[k].s; return o; })()")

    async def tally(self):
        return await self.page.evaluate("window.__logoTest.tally(window.__logoTest.comps)")


def expected_urls(data, keys):
    return {logo_url(PROV[p], r, c[f], keys[p]) for c in data["companies"] for _, p, r, f in ROUTES if c[f]}


def check(cond, msg, mask):
    if not cond:
        raise AssertionError(mask(msg))


async def scenarios(data, keys, base, out, mask):
    from playwright.async_api import async_playwright
    comps = data["companies"]
    applicable = sum(1 for c in comps for *_, f in ROUTES if c[f])
    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)        # no proxy: nothing can leave the machine
        try:
            # A: blocked, checks on — both providers stop at the known-logo check; nothing counted as a miss
            run = await Run("abort").open(browser, base, {"autostart": True, "canaryRetryMs": 300})
            check(await run.wait_finished(60), "A: page did not finish", mask)
            s = await run.states()
            n_by = collections.Counter(p for _, p, *_ in run.reqs)
            alerts = await run.page.inner_text("#alerts")
            check(n_by["bf"] == 2 and n_by["ld"] == 2, f"A: requests per provider {dict(n_by)}", mask)
            check(collections.Counter(s.values()) == collections.Counter({"stopped": applicable, "na": len(s) - applicable}),
                  f"A: states {collections.Counter(s.values())}", mask)
            check("Brandfetch stopped" in alerts and "logo.dev stopped" in alerts, "A: no stop message: " + alerts, mask)
            body = (await run.page.inner_text("#sumtable")).split("Group", 1)[1]
            check("%" not in body, "A: a percentage is shown although nothing was tested", mask)
            check(not run.errors and not run.other, f"A: page errors {run.errors} · other hosts {run.other}", mask)
            await run.page.screenshot(path=str(out / "A-phone-blocked.png"))
            await run.ctx.close()
            results.append(f"A blocked + checks: both providers stopped after 2 requests each · {applicable:,} routes "
                           "'not tested' · 0 misses counted · no percentage shown")

            # B: blocked, checks off, fast — every applicable route once, all misses, URLs exactly as logo_ids builds
            run = await Run("abort").open(browser, base, {"autostart": True, "controls": False, "bfGapMs": 3,
                                                          "ldGapMs": 3, "timeoutMs": 5000})
            check(await run.wait_finished(240), "B: page did not finish", mask)
            s = await run.states()
            got = [u for *_, u in run.reqs]
            want = expected_urls(data, keys)
            check(len(got) == applicable and set(got) == want,
                  f"B: {len(got):,} requests, {len(set(got)):,} distinct, expected {applicable:,} "
                  f"(differ: {len(set(got) ^ want)})", mask)
            check(collections.Counter(s.values()) == collections.Counter({"miss": applicable, "na": len(s) - applicable}),
                  f"B: states {collections.Counter(s.values())}", mask)
            t = await run.tally()
            check(t["mix"]["h"] == 0 and t["mix"]["n"] == len(comps) and t["mix"]["none"] == len(comps),
                  f"B: mix {t['mix']}", mask)
            table = await run.page.inner_text("#sumtable")
            check("0%" in table and not re.search(r"(?<![\d.])[1-9]\d*%", table), "B: summary shows hits: " + table[:300],
                  mask)
            check(not run.errors and not run.other, f"B: page errors {run.errors} · other hosts {run.other}", mask)
            await run.page.screenshot(path=str(out / "B-phone-all-misses.png"))
            await run.ctx.close()
            results.append(f"B blocked, no checks: {applicable:,} requests for {applicable:,} routes, all counted as "
                           "misses, 0% everywhere, URLs identical to logo_ids.logo_url")

            # C: real pace (blocked) for 12 s
            run = await Run("abort").open(browser, base, {"autostart": True, "controls": False})
            await asyncio.sleep(12)
            await run.page.click("#pause")
            await asyncio.sleep(0.6)
            gaps = {}
            for p in ("bf", "ld"):
                ts = [t for t, pp, *_ in run.reqs if pp == p]
                gaps[p] = (len(ts), min(b - a for a, b in zip(ts, ts[1:])))
            check(gaps["bf"][1] >= 0.45 and gaps["ld"][1] >= 0.22, f"C: smallest gaps {gaps}", mask)
            check(gaps["bf"][0] <= 12 / 0.5 + 2 and gaps["ld"][0] <= 12 / 0.25 + 2, f"C: request counts {gaps}", mask)
            check(not run.errors and not run.other, f"C: page errors {run.errors} · other hosts {run.other}", mask)
            await run.ctx.close()
            results.append(f"C real pace, 12 s: Brandfetch {gaps['bf'][0]} requests, smallest gap {gaps['bf'][1]:.3f} s "
                           f"· logo.dev {gaps['ld'][0]} requests, smallest gap {gaps['ld'][1]:.3f} s")

            # D: fake answers inside the browser — counts must equal the expected ones
            fake = Fake(data["meta"])
            cfg = {"autostart": True, "bfGapMs": 5, "ldGapMs": 5, "recheckMs": 1500, "canaryRetryMs": 300,
                   "checkEvery": 150, "badEvery": 400}
            exp = {}
            for c in comps:
                for rid, p, r, f in ROUTES:
                    ident = c[f]
                    exp[f"{c['c']}|{rid}"] = ("na" if not ident else
                                              "hit" if fake.image(p, r, ident, "2" if rid == "ldD" else None) else "miss")
            placeholders = sum(1 for k, v in exp.items() if k.endswith("|ldD") and v == "miss")
            exp_mix = sum(1 for c in comps if any(exp[f"{c['c']}|{rid}"] == "hit" for rid, *_ in ROUTES))
            first = collections.Counter()
            for c in comps:
                hits = [i for i, (rid, *_) in enumerate(ROUTES) if exp[f"{c['c']}|{rid}"] == "hit"]
                first[hits[0] if hits else None] += 1
            for vp, name in (((390, 844), "phone"), ((1280, 900), "pc")):
                run = await Run("fake", fake).open(browser, base, cfg, viewport=vp)
                check(await run.wait_finished(600), f"D-{name}: page did not finish", mask)
                s = await run.states()
                diff = [k for k in exp if exp[k] != s.get(k)]
                check(not diff, f"D-{name}: {len(diff)} states differ, e.g. {[(k, exp[k], s.get(k)) for k in diff[:5]]}",
                      mask)
                ctr = await run.page.evaluate("window.__logoTest.counters")
                check(ctr["placeholders"] == placeholders, f"D-{name}: placeholders {ctr} vs {placeholders}", mask)
                check(max(run.max_inflight.values()) == 1, f"D-{name}: in flight per route {dict(run.max_inflight)}",
                      mask)
                t = await run.tally()
                check(t["mix"]["h"] == exp_mix and t["mix"]["n"] == len(comps), f"D-{name}: mix {t['mix']}", mask)
                check(t["mix"]["first"] == [first[i] for i in range(5)] and t["mix"]["none"] == first[None],
                      f"D-{name}: first hits {t['mix']} vs {dict(first)}", mask)
                alerts = await run.page.inner_text("#alerts")
                check("Brandfetch checks: known logo loads" in alerts and "logo.dev checks: known logo loads" in alerts
                      and "stopped" not in alerts and "202 placeholder" in alerts, "D: checks: " + alerts, mask)
                check(not run.errors and not run.other, f"D-{name}: page errors {run.errors} · other {run.other}", mask)
                await run.page.screenshot(path=str(out / f"D-{name}-top.png"))
                await run.page.locator("#summary").screenshot(path=str(out / f"D-{name}-summary.png"))
                await run.page.evaluate("document.querySelector('.grp').scrollIntoView()")
                await run.page.screenshot(path=str(out / f"D-{name}-grid.png"))
                width = await run.page.evaluate("document.documentElement.scrollWidth")
                check(width <= vp[0], f"D-{name}: the page scrolls sideways ({width}px > {vp[0]}px)", mask)
                await run.ctx.close()
            results.append(f"D fake answers (phone and PC): {len(comps)} companies, every route state as expected, best "
                           f"mix {exp_mix}/{len(comps)}, first hits as expected, {placeholders} first-request "
                           "placeholders caught by the second load, at most 1 request in flight per route")

            # E: logo.dev answers even the made-up domain with an image when it is loaded again -> LD domain is void
            run = await Run("fake", Fake(data["meta"], ld_domain_always=True)).open(browser, base, cfg)
            check(await run.wait_finished(600), "E: page did not finish", mask)
            s = await run.states()
            ld_dom = [v for k, v in s.items() if k.endswith("|ldD") and v != "na"]
            others = {k: v for k, v in s.items() if not k.endswith("|ldD")}
            check(ld_dom and set(ld_dom) == {"stopped"}, f"E: LD domain states {collections.Counter(ld_dom)}", mask)
            check(all(others[k] == exp[k] for k in others), "E: another route changed", mask)
            alerts = await run.page.inner_text("#alerts")
            check("LD domain route is marked 'off'" in alerts, "E: no alert: " + alerts, mask)
            t = await run.tally()
            exp_mix_e = sum(1 for c in comps if any(exp[f"{c['c']}|{rid}"] == "hit" for rid, *_ in ROUTES if rid != "ldD"))
            check(t["mix"]["h"] == exp_mix_e and t["routes"][4]["t"] == 0, f"E: mix {t['mix']} · ldD {t['routes'][4]}",
                  mask)
            check(not run.errors and not run.other, f"E: page errors {run.errors} · other {run.other}", mask)
            await run.ctx.close()
            results.append(f"E made-up domain still an image on the second load: LD domain switched off for all "
                           f"{len(ld_dom)} companies, not counted; best mix without it {exp_mix_e}/{len(comps)}")
        finally:
            await browser.close()
    return results


def main(argv):
    src = pathlib.Path(argv[0]) if argv else ROOT / "logo-test.html"
    html = src.read_text(encoding="utf-8")
    data, keys = page_parts(html)
    mask = Masker(keys["bf"], keys["ld"])
    out = pathlib.Path(os.environ.get("SMOKE_OUT") or tempfile.mkdtemp(prefix="smoke-logo-"))
    out.mkdir(parents=True, exist_ok=True)
    folder = pathlib.Path(tempfile.mkdtemp(prefix="logo-site-"))
    (folder / "logo-test.html").write_text(html, encoding="utf-8")
    base, httpd = serve(folder)
    try:
        results = asyncio.run(scenarios(data, keys, base, out, mask))
    finally:
        httpd.shutdown()
    for line in results:
        print("· " + line)
    print(f"logo-test.html smoke: {len(results)} scenarios passed · 0 page errors · no request left the browser for "
          f"the logo providers · screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
