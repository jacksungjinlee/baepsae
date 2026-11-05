#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test for logo-review.html (Jack's logo picker): python tests/smoke_logo_review.py [PAGE]

Both providers' terms forbid loading their logo images from a script or a headless browser, so here NO request ever
reaches cdn.brandfetch.io or img.logo.dev: Chromium starts without a proxy, and every request to those hosts is stopped
inside the browser — aborted, or answered by a fake inside the browser (Pillow-drawn shapes). Any other outside request
is aborted too and fails the test. Keys in the page are never printed.

  A  blocked, checks on       both providers stop at the known-logo checks (3 requests each); no company URL is
                              requested; every tile 'not checked'; Confirm stays off, Retry shows
  B  blocked, real pace       Brandfetch >= 0.5 s and logo.dev >= 0.25 s between request starts; nothing before Start
  C  blocked, fast            only the grid you are on and the next one load (the URLs exactly as logo_ids.logo_url
                              builds them, the current grid first in every route); moving on loads the one after
  D  fake answers, CORS on    (phone 390 px and PC 1280 px, with our own icons for a few companies) every pre-pick as
                              build_review_page.pre_pick expects (agreement, order, own icon, letter mark), low-res
                              badges, logo.dev's 202 placeholder caught by the second load, one request at a time per
                              route, each image requested once; hover / long press shows the 96 px view without
                              flagging; flag -> Fix -> Confirm -> Download: reviewed companies only, exact URLs, letter
                              mark = null; progress survives a reload; only this page's localStorage key is written
  E  Load choices              a fresh browser loads D's file: same choices back; a file with bad entries keeps only
                              the valid ones; a wrong version changes nothing
  F  logo.dev without CORS    agreement off for logo.dev (said in the help text); pre-picks follow the order
  G  CORS loses logos         Brandfetch passes the readable check but answers logos without CORS headers: the first
                              audited miss loads the plain way, the page switches Brandfetch to plain loads and tries
                              its misses again; pre-picks as expected
  H  Retry and the window     both providers stop (blocked), the block lifts, Retry: checks run first, then the grid
                              loads and pre-picks as expected; a request that timed out is not tried again once Jack
                              has moved to another grid, and after the move only that grid and the next one load
  I  icon files missing       the site has no logo-review/icons: the known-icon check fails, our icons stop as
                              'not checked' (never counted as no logo), Confirm stays off
  J  paste + find more        (phone 390 px and PC 1280 px) flag -> Fix -> Paste an image address: refused addresses
                              (script, data:, Brandfetch / logo.dev, ftp, too long, not a full address) never load;
                              http made https; a preview from a local HTTPS server (its own certificate): 48 px refused,
                              80 px usable with a warning, 128 px -> Use this picture; None of these - find more ->
                              Save: choices, summary ('needs a logo: 1'), Download, the Needs a logo view (tap -> its
                              grid); only image GETs reach that server, without a referrer; the download loads back
  K  old saved progress       (phone and PC) Jack's saved progress as the page of PR #45 writes it loads, saves back
                              and exports unchanged; his old export loads as 'the same'; loading resumes by itself
  L  remembered + resume      first visit and a reload without Start load nothing; after Start, what was found is
                              remembered (source, hit/miss, day); a reload resumes by itself ('Loading resumed' +
                              Pause), runs the checks first, asks only the remembered hits, never a known miss; a
                              remembered logo that no longer loads gets its company checked again
Zero page errors in every scenario; screenshots go to SMOKE_OUT, else a new temporary folder.
"""
import asyncio
import collections
import hashlib
import http.server
import io
import json
import os
import pathlib
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logos"))
import build_review_page as br  # noqa: E402
import logo_sources as lsrc  # noqa: E402
from logo_ids import Masker, logo_url  # noqa: E402

PROVIDER_HOSTS = {"cdn.brandfetch.io", "img.logo.dev"}
STORE_KEY = "baepsae-logo-review-v1"
PROBE_KEY = "baepsae-logo-review-probes-v1"
ROUTES = [("bfI", "bf", "isin", "isin"), ("bfT", "bf", "ticker", "tk"), ("ldT", "ld", "ticker", "tk"),
          ("ldD", "ld", "domain", "dom"), ("bfD", "bf", "domain", "dom")]
PROV = {"bf": "brandfetch", "ld": "logodev"}
DESIGNS = ["disc", "wide", "tall", "ring", "tri", "cross", "checker", "bars"]
INK = (27, 43, 75, 255)


# ── fake logos (Pillow) ──

def draw(name, size=128):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = size / 128

    def R(*xy):
        return [v * s for v in xy]
    if name == "disc":
        d.ellipse(R(14, 14, 114, 114), fill=INK)
    elif name == "wide":
        d.rectangle(R(4, 44, 124, 84), fill=INK)
    elif name == "tall":
        d.rectangle(R(44, 4, 84, 124), fill=INK)
    elif name == "ring":
        d.ellipse(R(14, 14, 114, 114), outline=INK, width=int(22 * s))
    elif name == "tri":
        d.polygon(R(64, 10, 118, 118, 10, 118), fill=INK)
    elif name == "cross":
        d.rectangle(R(50, 10, 78, 118), fill=INK)
        d.rectangle(R(10, 50, 118, 78), fill=INK)
    elif name == "checker":
        d.rectangle(R(14, 14, 64, 64), fill=INK)
        d.rectangle(R(64, 64, 114, 114), fill=INK)
        d.rectangle(R(14, 14, 114, 114), outline=INK, width=max(1, int(3 * s)))
    elif name == "bars":
        for k in range(4):
            d.rectangle(R(14, 14 + 26 * k, 114, 26 + 26 * k), fill=INK)
    elif name == "frame":                                             # logo.dev's first-request placeholder
        d.rectangle(R(8, 8, 120, 120), outline=(120, 120, 120, 255), width=max(1, int(4 * s)))
    else:
        raise KeyError(name)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


_PNG = {}


def png(name, size=128):
    if (name, size) not in _PNG:
        _PNG[(name, size)] = draw(name, size)
    return _PNG[(name, size)]


def H(*xs):
    return int(hashlib.sha1("|".join(str(x) for x in xs).encode()).hexdigest(), 16)


RATE = {"bfI": 70, "bfT": 65, "ldT": 60, "ldD": 50, "bfD": 45}


def truth(code, rid):
    """The fake provider's final answer for a company's route: None (no logo) or (design, size)."""
    us = not code[:1].isdigit()
    if not us and H(code, "nologo") % 100 < 8:                                     # about 8 in 100 Korean: no logo
        return None
    if H(code, rid, "hit") % 100 >= (99 if us else RATE[rid]):                     # US tickers: nearly always
        return None
    t = H(code, "true") % len(DESIGNS)
    i = t if H(code, rid, "same") % 100 < 55 else (t + 1 + H(code, rid, "other") % (len(DESIGNS) - 1)) % len(DESIGNS)
    return DESIGNS[i], (32 if H(code, rid, "size") % 100 < 12 and DESIGNS[i] != "bars" else 128)


# pre_pick in build_review_page compares fingerprints: one far-apart fingerprint per design stands in for the
# browser's (the same shape at any size gives about the same fingerprint there, distinct shapes differ by 0.24 or more;
# fine stripes at 32 px don't, so the fake never serves 'bars' small)
FP = {d: "".join("f" if k // 2 == i else "0" for k in range(16)) for i, d in enumerate(DESIGNS)}


def expected(co, readable=("bf", "ld"), icons=None):
    """{pick, via, ...} the page should pre-pick for one company (dict as in the page data)."""
    cands = {}
    for rid, p, r, f in ROUTES:
        if not co[f]:
            continue
        t = truth(co["c"], rid)
        cands[rid] = {"s": "hit", "hash": {"g": FP[t[0]], "ar": 1.0} if p in readable else None} \
            if t else {"s": "miss"}
    if co.get("ic"):
        d = DESIGNS[H(co["c"], "true") % len(DESIGNS)]
        cands["own"] = {"s": "hit", "hash": {"g": FP[d], "ar": 1.0}, "check": bool(co.get("icx"))}
    return br.pre_pick(cands)


def classify(url):
    """(provider, route, ident, v, size) for a provider URL."""
    u = urlparse(url)
    qs = parse_qs(u.query)
    parts = [unquote(p) for p in u.path.split("/") if p]
    if u.hostname == "cdn.brandfetch.io":
        return "bf", parts[0], parts[1], None, int(parts[3])
    v, size = (qs.get("v") or [None])[0], int((qs.get("size") or ["128"])[0])
    if parts[0] in ("ticker", "isin"):
        return "ld", parts[0], parts[1], v, size
    return "ld", "domain", parts[0], v, size


class Fake:
    """Known logos load, made-up identifiers give 404, companies by truth(). logo.dev answers a domain's first request
    with a 202 placeholder; the second load (v=2) is the real answer. cors: provider -> 'all' | 'none' | 'checks'
    ('checks' = CORS headers only on the check loads, which use another size than 128)."""

    def __init__(self, data, cors=None):
        meta = data["meta"]
        self.good = set(meta["good"].values()) | set(meta["rotate"])
        self.bad = set(meta["bad"].values())
        self.cors = dict({"bf": "all", "ld": "all"}, **(cors or {}))
        self.slow = set()                                    # identifiers answered only after 3 s (a timeout)
        self.gone = set()                                    # company identifiers that now answer 404 (a logo removed)
        self.idents = {}
        for co in data["companies"]:
            for rid, p, r, f in ROUTES:
                if co[f]:
                    self.idents[(p, r, co[f])] = (co["c"], rid)

    def control(self, ident, size):
        return size != 128 or ident in self.bad or ident.startswith("ZZQX")

    def answer(self, p, r, ident, v, size):
        """(status, png bytes) or (404, b'')."""
        if p == "ld" and r == "domain" and not v:                    # any domain's first request, made-up ones too
            return 202, png("frame")
        if ident in self.bad or ident.startswith("ZZQX"):
            return 404, b""
        if size != 128 and ident in self.good:
            return 200, png("disc")
        hit = self.idents.get((p, r, ident))
        if not hit:
            return 404, b""
        code, rid = hit
        if rid == "ldD" and not v:
            return 202, png("frame")
        if (p, r, ident) in self.gone:
            return 404, b""
        t = truth(code, rid)
        return (200, png(t[0], t[1])) if t else (404, b"")

    def headers(self, p, size):
        """CORS allowed: '*'. Not allowed: another site's origin (a fulfilled answer WITHOUT the header would get one
        added by Playwright, so 'no header' is played by a header that names another site; Chromium refuses both)."""
        c = self.cors[p]
        ok = c == "all" or (c == "checks" and size != 128)
        return {"Access-Control-Allow-Origin": "*" if ok else "https://elsewhere.invalid"}


class Run:
    def __init__(self, mode, fake=None):
        self.mode, self.fake = mode, fake
        self.reqs, self.other, self.errors = [], [], []
        self.inflight, self.max_inflight = collections.Counter(), collections.Counter()
        self.closing = False

    async def open(self, browser, base, cfg, viewport=(390, 844), page="logo-review.html", touch=None, https_ok=False,
                   init=None):
        """https_ok: accept the local HTTPS test server's own certificate (pasted image addresses).
        init: script run before the page's, on every load (e.g. a saved localStorage entry)."""
        touch = viewport[0] < 600 if touch is None else touch
        self.ctx = await browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                             service_workers="block", has_touch=touch, accept_downloads=True,
                                             ignore_https_errors=https_ok)
        await self.ctx.route("**/*", self.on_route)
        self.page = await self.ctx.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        await self.page.add_init_script("window.__LOGO_REVIEW_CONFIG = " + json.dumps(cfg) + ";")
        if init:
            await self.page.add_init_script(init)
        self.base, self.cfg = base, cfg
        await self.page.goto(f"{base}/{page}", wait_until="domcontentloaded")
        return self

    async def close(self):
        """Close while logos may still be loading (a resumed page loads by itself): answers left over are dropped."""
        self.closing = True
        await self.ctx.close()

    async def on_route(self, route):
        try:
            await self._on_route(route)
        except Exception:                                    # noqa: BLE001 — only while closing (see close)
            if not self.closing:
                raise

    async def _on_route(self, route):
        req = route.request
        host = urlparse(req.url).hostname
        if host == "127.0.0.1":
            await route.continue_()
            return
        if host not in PROVIDER_HOSTS:
            self.other.append(host)
            await route.abort()
            return
        p, r, ident, v, size = classify(req.url)
        mode = "cors" if "origin" in req.headers else "no-cors"           # an img with crossOrigin sends Origin
        self.reqs.append((time.monotonic(), p, r, ident, v, size, mode, req.url))
        if self.mode != "fake":
            await route.abort()
            return
        lane = None if self.fake.control(ident, size) or mode != "cors" and self.fake.cors[p] == "all" else p + r
        if lane:
            self.inflight[lane] += 1
            self.max_inflight[lane] = max(self.max_inflight[lane], self.inflight[lane])
        await asyncio.sleep(0.004 + (H(req.url) % 12) / 1000 + (3.0 if ident in self.fake.slow else 0))
        if lane:
            self.inflight[lane] -= 1
        status, body = self.fake.answer(p, r, ident, v, size)
        hdr = self.fake.headers(p, size)
        try:
            if status == 404:
                await route.fulfill(status=404, body=b"", headers=hdr)
            else:
                await route.fulfill(status=status, content_type="image/png", body=body, headers=hdr)
        except Exception:                                    # noqa: BLE001 — the page gave up on it (timed out)
            if ident not in self.fake.slow and not self.closing:
                raise

    async def js(self, expr):
        return await self.page.evaluate(expr)

    async def wait(self, expr, timeout_s, what):
        t_end = time.monotonic() + timeout_s
        while time.monotonic() < t_end:
            if await self.js(expr):
                return
            await asyncio.sleep(0.2)
        raise AssertionError(f"timed out waiting for {what}")

    async def ready_or_gaps(self, gid, timeout_s=120):
        """Every route of the grid has ended (ready, or ended with gaps)."""
        await self.wait(f"(s => s.settled === s.total)(window.__logoReview.status({json.dumps(gid)}))", timeout_s,
                        f"grid {gid} settled")

    async def ready(self, gid, timeout_s=120):
        await self.wait(f"window.__logoReview.status({json.dumps(gid)}).ready", timeout_s, f"grid {gid} ready")


def check(cond, msg, mask):
    if not cond:
        raise AssertionError(mask(msg))


def grid_codes(data, gid):
    return [c["c"] for c in data["companies"] if c["g"] == gid]


def url_for(co, rid, keys):
    p, r, f = {rid_: (p_, r_, f_) for rid_, p_, r_, f_ in ROUTES}[rid]
    return logo_url(PROV[p], r, co[f], keys[p])


def with_icons(html, data, keys, folder, n=8):
    """The same page with fake own icons (instead of the real ones) for a few companies of the first Korean grid:
    kept ones, some for companies with no provider logo, and two that need a look (never pre-picked)."""
    data = json.loads(json.dumps(data))
    for c in data["companies"]:
        c["ic"] = ""
        c.pop("icx", None)
    kr1 = [c for c in data["companies"] if c["g"] == "KR-1"]
    none = [c for c in kr1 if not any(c[f] and truth(c["c"], rid) for rid, _, _, f in ROUTES)]
    some = [c for c in kr1 if c not in none]
    pick = none[:n // 2] + some[:n - len(none[:n // 2])]
    check = none[n // 2:n // 2 + 1] + some[n:n + 1]                     # needs a look: one with, one without logos
    (folder / "logo-review" / "fake").mkdir(parents=True, exist_ok=True)
    for c in pick + check:
        name = f"{c['c']}.png"
        (folder / "logo-review" / "fake" / name).write_bytes(png(DESIGNS[H(c["c"], "true") % len(DESIGNS)]))
        c["ic"] = f"logo-review/fake/{name}"
    for c in check:
        c["icx"] = 1
    data["meta"]["icons"], data["meta"]["iconsCheck"] = len(pick) + len(check), len(check)
    tpl = (ROOT / "tools" / "logos" / "logo_review_template.html").read_text(encoding="utf-8")
    page = lsrc.render(tpl, data, (keys["bf"], keys["ld"]))
    assert lsrc.render(tpl, json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html,
                                                 re.S).group(1)), (keys["bf"], keys["ld"])) == html, "page != template"
    return page, data, [c["c"] for c in pick + check], [c["c"] for c in none[:n // 2]], [c["c"] for c in check]


async def picks_match(run, data, gid, readable, mask, label):
    comps = {c["c"]: c for c in data["companies"]}
    got = await run.js(f"Object.fromEntries({json.dumps(grid_codes(data, gid))}.map(c => [c, window.__logoReview.prePickOf(c)]))")
    bad = []
    for code, g in got.items():
        e = expected(comps[code], readable)
        if (g["pick"], g["via"]) != (e["pick"], e["via"]) or not g["settled"]:
            bad.append((code, (g["pick"], g["via"], g["settled"]), (e["pick"], e["via"])))
    check(not bad, f"{label}: {len(bad)} pre-picks differ, e.g. {bad[:4]}", mask)
    vias = collections.Counter(g["via"] for g in got.values())
    return got, vias


async def scenario_d(browser, base, data, keys, out, mask, vp, name, icon_codes, iconless, checks):
    comps = {c["c"]: c for c in data["companies"]}
    cfg = {"bfGapMs": 5, "ldGapMs": 5, "recheckMs": 1500, "canaryRetryMs": 300, "checkEvery": 150, "badEvery": 400,
           "longPressMs": 400}
    run = await Run("fake", Fake(data)).open(browser, base, cfg, viewport=vp, page="logo-review-icons.html")
    await asyncio.sleep(1.0)
    check(not run.reqs, f"D-{name}: {len(run.reqs)} requests before Start", mask)
    await run.page.click("#start")
    await run.ready("KR-1")
    await run.ready("KR-2")
    await run.wait("window.__logoReview.pending() === 0", 30, "timers")
    got, vias = await picks_match(run, data, "KR-1", ("bf", "ld"), mask, f"D-{name}")
    exp_ic = [c for c in iconless if expected(comps[c])["pick"] == "own"]
    check(all(got[c]["pick"] == "own" for c in iconless) and len(exp_ic) == len(iconless) and iconless,
          f"D-{name}: own icon not the pre-pick for {iconless}", mask)
    check(len(checks) == 2 and all(got[c]["pick"] != "own" for c in checks) and got[checks[0]]["pick"] is None,
          f"D-{name}: an icon to check was pre-picked: {[(c, got[c]) for c in checks]}", mask)
    def first_hit(c):
        return next(rid for rid, _, _, f in ROUTES if comps[c][f] and truth(c, rid))
    overrode = [c for c, g in got.items() if g["via"] == "agree" and g["pick"] != first_hit(c)]
    check(vias["agree"] >= 10 and vias["order"] >= 10 and overrode, f"D-{name}: pre-picks {dict(vias)}, "
          f"agreement changed {len(overrode)}", mask)
    # one request per company URL (logo.dev domains: the first and the second load), checks and audits aside
    company = collections.Counter(u for _, p, r, ident, v, size, mode, u in run.reqs
                                  if size == 128 and not run.fake.control(ident, size) and mode == "cors")
    check(max(company.values()) == 1, f"D-{name}: a URL was requested twice: {company.most_common(2)}", mask)
    want = set()
    for gid in ("KR-1", "KR-2"):
        for code in grid_codes(data, gid):
            for rid, p, r, f in ROUTES:
                if comps[code][f]:
                    u = url_for(comps[code], rid, keys)
                    want.add(u)
                    if rid == "ldD":
                        want.add(u + "&v=2")
    check(set(company) == want, f"D-{name}: requested {len(company)} company URLs, expected {len(want)} "
          f"(differ {len(set(company) ^ want)})", mask)
    check(max(run.max_inflight.values()) == 1, f"D-{name}: in flight per route {dict(run.max_inflight)}", mask)
    ctr = await run.js("window.__logoReview.counters")
    placeholders = sum(1 for g in ("KR-1", "KR-2") for c in grid_codes(data, g) if comps[c]["dom"] and not truth(c, "ldD"))
    check(ctr["placeholders"] == placeholders, f"D-{name}: placeholders {ctr} vs {placeholders}", mask)
    alerts = await run.page.inner_text("#alerts")
    agree_help = await run.page.text_content("#agreestate")                       # inside the closed help
    check("Brandfetch checks: known logo loads" in alerts and "202 placeholder" in alerts and "stopped" not in alerts
          and "(agreement on)" in agree_help, f"D-{name}: alerts {alerts} · help {agree_help}", mask)
    low = sum(1 for c, g in got.items() if g["pick"] in ("bfI", "bfT", "ldT", "ldD", "bfD") and truth(c, g["pick"])[1] == 32)
    nlow = await run.js("document.querySelectorAll('#grid .b.low').length")
    nagr = await run.js("document.querySelectorAll('#grid .b.agr').length")
    check(nlow == low and low > 0 and nagr == vias["agree"], f"D-{name}: low-res badges {nlow} vs {low}, agree {nagr}", mask)
    if vp[0] < 600:
        row = await run.js("(() => { const t = [...document.querySelectorAll('#grid .tile')]; return t.filter(x => "
                           "x.offsetTop === t[0].offsetTop).length; })()")
        w = await run.js("document.querySelector('#grid .tile').getBoundingClientRect().width")
        check(row == 5 and w >= 60, f"D-{name}: {row} tiles per row, {w:.0f} px wide", mask)
    width = await run.js("document.documentElement.scrollWidth")
    check(width <= vp[0], f"D-{name}: the page scrolls sideways ({width}px > {vp[0]}px)", mask)
    await run.page.screenshot(path=str(out / f"D-{name}-top.png"))
    await run.page.locator("#review").scroll_into_view_if_needed()
    await run.page.screenshot(path=str(out / f"D-{name}-grid.png"))

    # a closer look: hover (PC) / press and hold (phone) shows 96 px, and does not flag
    codes = grid_codes(data, "KR-1")
    tile = run.page.locator(f'#grid .tile[data-code="{codes[0]}"]')
    if vp[0] < 600:
        box = await tile.bounding_box()
        cdp = await run.ctx.new_cdp_session(run.page)
        pt = [{"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}]
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt})
        await asyncio.sleep(0.7)
        shown = await run.js("!document.getElementById('peek').classList.contains('hide')")
        size = await run.js("(() => { const i = document.querySelector('#peek .big'); return i.getBoundingClientRect().width; })()")
        await run.page.screenshot(path=str(out / f"D-{name}-hold.png"))
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await asyncio.sleep(0.3)
    else:
        await tile.hover()
        await asyncio.sleep(0.6)
        shown = await run.js("!document.getElementById('peek').classList.contains('hide')")
        size = await run.js("document.querySelector('#peek .big').getBoundingClientRect().width")
        await run.page.screenshot(path=str(out / f"D-{name}-hover.png"))
        await run.page.mouse.move(2, 2)
    flagged0 = await run.js(f"!!window.__logoReview.prog().flags[{json.dumps(codes[0])}]")
    check(shown and 96 <= size <= 100 and not flagged0, f"D-{name}: closer look shown={shown} size={size} "
          f"flagged={flagged0}", mask)

    # flag four tiles; one is tapped twice (undone)
    hits = {c: [rid for rid, _, _, f in ROUTES if comps[c][f] and truth(c, rid)] + (["own"] if comps[c].get("ic") else [])
            for c in codes}
    multi = next(c for c in codes[1:] if len(hits[c]) >= 2 and c not in icon_codes)
    single = next(c for c in codes[1:] if hits[c] and c != multi and c not in icon_codes)
    nothing = next((c for c in codes if not hits[c] and not comps[c].get("ic")), None)
    undone = next(c for c in codes[1:] if c not in (multi, single, nothing) and c not in checks)
    other = next(rid for rid in hits[multi] if rid != got[multi]["pick"])
    plan = {multi: other, single: "letter", checks[1]: "own"}                  # Jack takes an icon that needed a look
    if nothing:
        plan[nothing] = "letter"

    async def tap(code):
        t = run.page.locator(f'#grid .tile[data-code="{code}"]')
        await t.scroll_into_view_if_needed()
        if vp[0] < 600:
            await t.tap()
        else:
            await t.click()
    for c in list(plan) + [undone, undone]:
        await tap(c)
    flags = await run.js("Object.keys(window.__logoReview.prog().flags).sort()")
    check(flags == sorted(plan), f"D-{name}: flags {flags} vs {sorted(plan)}", mask)
    check(await run.js("document.getElementById('export').disabled"), f"D-{name}: export on before any Confirm", mask)
    await run.page.screenshot(path=str(out / f"D-{name}-flagged.png"))
    await run.page.click("#confirm")
    await run.page.wait_for_selector("#fix:not(.hide)")
    rows = await run.js("[...document.querySelectorAll('#fixlist .fixrow')].map(r => [r.dataset.code, "
                        "[...r.querySelectorAll('.opt')].map(o => o.dataset.src)])")
    src_of = dict(br.SOURCE)
    want_rows = [[c, [src_of[r] for r in br.ORDER if r in hits[c]] + ["letter", "manual", "need"]] for c in codes
                 if c in plan]
    check(rows == want_rows, f"D-{name}: Fix rows {rows} vs {want_rows}", mask)
    label = await run.js(f"document.querySelector('#fixlist .fixrow[data-code=\"{checks[1]}\"] .opt[data-src=\"own-icon\"]').textContent")
    check(label.startswith("Own icon (check)"), f"D-{name}: the icon to check is labelled {label!r}", mask)
    check(await run.js("document.getElementById('fixsave').disabled"), f"D-{name}: Save on before choosing", mask)
    await run.page.screenshot(path=str(out / f"D-{name}-fix.png"))
    for c, rid in plan.items():
        src = "letter" if rid == "letter" else src_of[rid]
        await run.page.click(f'#fixlist .fixrow[data-code="{c}"] .opt[data-src="{src}"]')
    await run.page.click("#fixsave")
    await run.wait("window.__logoReview.current() === 'KR-2'", 10, "the next grid after Confirm")
    await run.page.screenshot(path=str(out / f"D-{name}-after.png"))
    await run.wait("/Korea 1\u2013200\\s+200\\s+100\\s/.test(document.getElementById('sumtable').innerText)", 5,
                   "the summary to count KR-1")
    summary = await run.page.inner_text("#sumtable")
    nletter = sum(1 for c in codes if (plan.get(c) or got[c]["pick"] or "letter") == "letter")
    row = re.search(r"Korea 1\u2013200\s+200\s+100\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%", summary)
    check(row and int(row.group(2)) == nletter and int(row.group(1)) == 100 - nletter and int(row.group(3)) == 0 and
          abs(float(row.group(4)) - (100 - nletter)) < 0.06, f"D-{name}: summary {summary[:300]}", mask)

    # Download: reviewed companies only (KR-1), exact URLs, letter mark = null
    async with run.page.expect_download() as dl:
        await run.page.click("#export")
    path = out / f"choices-{name}.json"
    await (await dl.value).save_as(str(path))
    exp = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    check(set(exp) == {"version", "created", "choices"} and exp["version"] == 1 and
          re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+09:00", exp["created"]), f"D-{name}: export head {list(exp)}", mask)
    check(sorted(exp["choices"]) == sorted(codes), f"D-{name}: export has {len(exp['choices'])} codes, not KR-1's "
          f"{len(codes)} (KR-2 was loaded but not reviewed)", mask)
    today = await run.js("new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10)")
    wrong = []
    for c in codes:
        e = exp["choices"][c]
        rid = plan[c] if c in plan else (got[c]["pick"] or "letter")
        src = "letter" if rid == "letter" else src_of[rid]
        url = None if rid == "letter" else comps[c]["ic"] if rid == "own" else url_for(comps[c], rid, keys)
        if e != {"source": src, "url": url, "reviewed": today}:
            wrong.append((c, e, src))
    check(not wrong, f"D-{name}: {len(wrong)} exported choices differ, e.g. {wrong[:2]}", mask)
    check("data:" not in json.dumps(exp) and "base64" not in json.dumps(exp), f"D-{name}: image data in export", mask)
    own = [c for c in codes if exp["choices"][c]["source"] == "own-icon"]
    check(set(iconless) <= set(own) and checks[1] in own and checks[0] not in own, f"D-{name}: own icons in export {own}",
          mask)

    # storage: only this page's key; progress survives a reload
    await run.page.locator(f'#grid .tile[data-code="{grid_codes(data, "KR-2")[3]}"]').click()
    await run.js("window.__logoReview.flushMem()")
    keys_ = await run.js("[Object.keys(localStorage).sort(), sessionStorage.length, document.cookie]")
    check(keys_ == [sorted([STORE_KEY, PROBE_KEY]), 0, ""], f"D-{name}: storage {keys_}", mask)
    await run.page.reload(wait_until="domcontentloaded")
    back = await run.js("[window.__logoReview.current(), Object.keys(window.__logoReview.prog().choices).length, "
                        "Object.keys(window.__logoReview.prog().flags), window.__logoReview.running(), "
                        "!document.getElementById('resumed').classList.contains('hide')]")
    check(back == ["KR-2", len(codes), [grid_codes(data, "KR-2")[3]], True, True], f"D-{name}: after reload {back}", mask)
    check(not run.errors and not run.other, f"D-{name}: page errors {run.errors} · other hosts {run.other}", mask)
    await run.close()
    return path, (f"D fake answers ({name} {vp[0]} px): KR-1 pre-picks as expected ({vias['agree']} by agreement, "
                  f"{len(overrode)} of them overriding the order, {vias['order']} by order, {vias['none']} letter marks, "
                  f"{len(iconless)} own icons; {len(checks)} icons to check never pre-picked, one taken in Fix as 'Own icon (check)') · "
                  f"{low} low-res badges · {placeholders} placeholders caught · 1 request "
                  f"per URL, 1 in flight per route · Fix rows = loaded logos + letter mark + paste + find more · export = KR-1 only, exact "
                  "URLs · this page's two localStorage keys only · a reload keeps progress and resumes loading by itself")


# ── J, K, L (2026-11-05): a pasted image address, None of these - find more, Jack's saved progress, what was found ──

def make_cert(folder):
    """A certificate of its own for the local HTTPS image server (accepted by the test's browser contexts only)."""
    cert, key = folder / "cert.pem", folder / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                    "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=127.0.0.1",
                    "-addext", "subjectAltName=IP:127.0.0.1"], check=True, capture_output=True)
    return cert, key


def https_images(folder):
    """The local test server for pasted image addresses, over HTTPS: logo.png 128 px, soft.png 80 px, small.png 48 px.
    Returns (base, server, log of (method, path, Referer, Origin))."""
    import socket
    import ssl
    img = folder / "img"
    img.mkdir(parents=True, exist_ok=True)
    for name, design, size in (("logo.png", "cross", 128), ("soft.png", "ring", 80), ("small.png", "tri", 48)):
        (img / name).write_bytes(png(design, size))
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(*make_cert(folder))
    log = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(img), **k)

        def log_message(self, *a):
            pass

        def note(self):
            log.append((self.command, self.path, self.headers.get("Referer"), self.headers.get("Origin")))

        def do_GET(self):
            self.note()
            super().do_GET()

        def do_HEAD(self):
            self.note()
            super().do_HEAD()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

        def finish_request(self, request, client_address):          # the TLS handshake in the request's own thread
            request.settimeout(15)
            try:
                conn = tls.wrap_socket(request, server_side=True)
            except (ssl.SSLError, OSError):
                return
            try:
                self.RequestHandlerClass(conn, client_address, self)
            finally:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                conn.close()

    httpd = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"https://127.0.0.1:{httpd.server_address[1]}", httpd, log


async def tap_tile(run, code, vp):
    t = run.page.locator(f'#grid .tile[data-code="{code}"]')
    await t.scroll_into_view_if_needed()
    if vp[0] < 600:
        await t.tap()
    else:
        await t.click()


def today_kst():
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 9 * 3600))


FAST = {"bfGapMs": 5, "ldGapMs": 5, "recheckMs": 1500, "canaryRetryMs": 300}


async def scenario_j(browser, base, data, keys, out, mask, vp, name, img_base, img_log):
    """Flag two tiles -> Confirm -> Fix: paste addresses (refused ones, http made https, too small, not loading, small
    but usable, right) -> preview -> Use this picture; None of these - find more -> Save; the summary, Download, the
    Needs a logo view and back to the grid. Only the image loads leave the page, to the local HTTPS server."""
    run = await Run("fake", Fake(data)).open(browser, base, dict(FAST, autostart=True), viewport=vp, https_ok=True)
    await run.ready("KR-1")
    codes = grid_codes(data, "KR-1")
    a, b = codes[5], codes[6]
    n0 = len(img_log)
    for c in (a, b):
        await tap_tile(run, c, vp)
    await run.page.click("#confirm")
    await run.page.wait_for_selector("#fix:not(.hide)")
    rowa = f'#fixlist .fixrow[data-code="{a}"]'
    check(await run.js(f"document.querySelector('{rowa} .paste').classList.contains('hide')"), f"J-{name}: paste open", mask)
    await run.page.click(f'{rowa} .opt[data-src="manual"]')
    check(await run.js(f"!document.querySelector('{rowa} .paste').classList.contains('hide') && "
                       f"document.activeElement === document.querySelector('{rowa} .paste input')"),
          f"J-{name}: the paste box did not open with the cursor in it", mask)
    inp, pmsg = f"{rowa} .paste input", f"{rowa} .paste .pmsg"
    use = f"{rowa} .paste button[data-act=use]"

    async def preview(addr):
        await run.page.fill(inp, addr)
        await run.page.click(f"{rowa} .paste button[data-act=preview]")

    async def said(text, cls, timeout_s=15):
        await run.wait(f"document.querySelector({json.dumps(pmsg)}).textContent.includes({json.dumps(text)})", timeout_s,
                       f"'{text}' in the paste message")
        got = await run.js(f"[document.querySelector({json.dumps(pmsg)}).className, document.querySelector({json.dumps(use)}).disabled]")
        check(cls in got[0].split(), f"J-{name}: '{text}' shown as {got[0]}", mask)
        return not got[1]

    refused = [("javascript:alert(1)", "script"), ("data:image/png;base64,AAAA", "data:"),
               ("https://cdn.brandfetch.io/ticker/AAPL/w/128/h/128?c=x", "Brandfetch"),
               ("https://img.logo.dev/apple.com?token=pk_x", "logo.dev"), ("ftp://x.example/a.png", "https"),
               ("https://x.example/" + "a" * 2000, "at most 2000"), ("www.x.example/a.png", "full web address")]
    for addr, why in refused:
        await preview(addr)
        check(not await said(why, "bad", 3), f"J-{name}: Use on for {addr[:40]}", mask)
    host = img_base.split("//", 1)[1]
    await preview(f"http://{host}/small.png")
    check(not await said("Too small: 48 × 48 px", "bad"), f"J-{name}: Use on for a 48 px picture", mask)
    msg_ = await run.js(f"document.querySelector({json.dumps(pmsg)}).textContent")
    check("http to https" in msg_ and await run.page.input_value(inp) == f"{img_base}/small.png",
          f"J-{name}: http not made https: {msg_!r}", mask)
    await preview(f"{img_base}/missing.png")
    check(not await said("did not load", "bad"), f"J-{name}: Use on for a missing picture", mask)
    await preview(f"{img_base}/soft.png")
    check(await said("Small: 80 × 80 px", "warn"), f"J-{name}: Use off for an 80 px picture", mask)
    url = f"{img_base}/logo.png"
    await preview(url)
    check(await said("128 × 128 px", "good"), f"J-{name}: Use off for the right picture", mask)
    await run.page.locator(rowa).scroll_into_view_if_needed()
    await run.page.screenshot(path=str(out / f"J-{name}-paste.png"))
    await run.page.click(use)
    await said("Chosen", "good", 3)
    on = await run.js(f"[...document.querySelectorAll('{rowa} .opt.on')].map(o => o.dataset.src)")
    check(on == ["manual"] and await run.page.inner_text("#fixsave") == "Choose for 1 more", f"J-{name}: chosen {on}", mask)
    await run.page.click(f'#fixlist .fixrow[data-code="{b}"] .opt[data-src="need"]')
    sideways = await run.js("[document.documentElement.scrollWidth, (s => s.scrollWidth - s.clientWidth)"
                            "(document.querySelector('#fix .sheet'))]")
    check(sideways[0] <= vp[0] and sideways[1] <= 0, f"J-{name}: the Fix panel scrolls sideways {sideways}", mask)
    await run.page.screenshot(path=str(out / f"J-{name}-fix.png"))
    await run.page.click("#fixsave")
    await run.wait("window.__logoReview.current() === 'KR-2'", 10, "the next grid after Save")
    day = today_kst()
    ch = await run.js("window.__logoReview.prog().choices")
    want_a, want_b = {"source": "manual", "url": url, "reviewed": day}, {"source": "need", "url": None, "reviewed": day}
    check(ch[a] == want_a and ch[b] == want_b, f"J-{name}: choices {ch[a]} {ch[b]}", mask)
    await run.wait("document.getElementById('sumline').textContent.includes('needs a logo: 1')", 5, "the needs count")
    summary = await run.page.inner_text("#sumtable")
    row = re.search(r"Korea 1–200\s+200\s+100\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%", summary)
    check(row and int(row.group(3)) == 1 and await run.page.inner_text("#needbtn") == "Needs a logo (1)",
          f"J-{name}: summary {summary[:200]}", mask)
    async with run.page.expect_download() as dl:
        await run.page.click("#export")
    path = out / f"J-choices-{name}.json"
    await (await dl.value).save_as(str(path))
    exp = json.loads(path.read_text(encoding="utf-8"))
    check(exp["version"] == 1 and exp["choices"][a] == want_a and exp["choices"][b] == want_b and len(exp["choices"]) == 100,
          f"J-{name}: export {exp['choices'].get(a)} {exp['choices'].get(b)}", mask)
    # the Needs a logo view
    await run.page.select_option("#gridsel", "need")
    await run.wait("window.__logoReview.view() === 'need'", 5, "the Needs a logo view")
    view = await run.js("[[...document.querySelectorAll('#grid .tile')].map(t => [t.dataset.code, t.querySelector('.src')"
                        ".textContent, !!t.querySelector('.lm'), [...t.querySelectorAll('.b')].map(x => x.textContent)]), "
                        "document.getElementById('dockmsg').textContent, document.getElementById('confirm').disabled]")
    check(view[0] == [[b, "Korea 1\u2013100", True, ["saved", "needs logo"]]] and view[1].startswith("1 company needs a logo")
          and view[2], f"J-{name}: Needs a logo view {view}", mask)
    await run.page.screenshot(path=str(out / f"J-{name}-need.png"))
    await tap_tile(run, b, vp)
    await run.wait("window.__logoReview.current() === 'KR-1' && window.__logoReview.view() === 'grid'", 5, "back to KR-1")
    spot = await run.js(f"document.querySelector('#grid .tile[data-code=\"{b}\"]').classList.contains('spot')")
    await run.wait(f"(i => i && i.src === {json.dumps(url)})(document.querySelector('#grid .tile[data-code=\"{a}\"] img'))", 10,
                   "the pasted logo on its tile")
    check(spot and not await run.js(f"!!window.__logoReview.prog().flags['{b}']"), f"J-{name}: the tile was not shown "
          "(or was marked wrong) after the tap in the Needs a logo view", mask)
    await run.page.screenshot(path=str(out / f"J-{name}-grid.png"))
    new = img_log[n0:]
    paths = {p for _, p, _, _ in new}
    check(paths == {"/small.png", "/missing.png", "/soft.png", "/logo.png"} and all(m == "GET" for m, *_ in new)
          and not any(r or o for _, _, r, o in new), f"J-{name}: image server saw {new}", mask)
    provider = [u for *_, u in run.reqs if "w/128/h/128?c=x" in u or "token=pk_x" in u]
    check(not provider and not run.errors and not run.other, f"J-{name}: refused addresses requested {provider} · page "
          f"errors {run.errors} · other hosts {run.other}", mask)
    await run.close()
    return path, (f"J paste + find more ({name} {vp[0]} px): 7 addresses refused before any request (script, data:, "
                  f"Brandfetch, logo.dev, ftp, over 2,000 characters, no https://); http made https; 48 px refused, a "
                  f"missing picture said so, 80 px usable with a warning, 128 px chosen; find more = needs a logo: 1 in "
                  f"the summary, the export and the Needs a logo view; the view's tap opened KR-1 at that tile; only "
                  f"{len(new)} GETs to the image server, no referrer")


def old_progress(data, keys):
    """Saved progress exactly as the page of PR #45 (the one Jack is using) writes it: KR-1 confirmed with every kind
    of choice (provider addresses, our own icon, letter mark, two review days), two marks and one fix in KR-2."""
    comps = {c["c"]: c for c in data["companies"]}
    kr1, kr2 = grid_codes(data, "KR-1"), grid_codes(data, "KR-2")
    field = {rid: f for rid, _, _, f in ROUTES}
    choices = {}
    for i, c in enumerate(kr1):
        co = comps[c]
        avail = [rid for rid, *_ in ROUTES if co[field[rid]]]
        if co.get("ic") and i % 3 == 0:
            choices[c] = {"source": "own-icon", "url": co["ic"], "reviewed": "2026-11-05"}
        elif avail and i % 5:
            rid = avail[(i // 2) % len(avail)]
            choices[c] = {"source": br.SOURCE[rid], "url": url_for(co, rid, keys),
                          "reviewed": "2026-11-05" if i % 2 else "2026-11-04"}
        else:
            choices[c] = {"source": "letter", "url": None, "reviewed": "2026-11-05"}
    return {"v": 1, "savedAt": "2026-11-05T15:02:11+09:00", "grid": "KR-2", "choices": choices,
            "flags": {kr2[0]: 1, kr2[1]: 1}, "fix": {kr2[0]: "letter"}}


async def scenario_k(browser, base, data, keys, out, mask, vp, name, old_file):
    """Jack's saved progress from the page he is using loads intact: every choice, mark and fix; it saves back the
    same; his old export loads as 'the same'. Its confirmed grid means Start was tapped: loading resumes by itself."""
    blob = old_progress(data, keys)
    init = (f"if (!localStorage.getItem({json.dumps(STORE_KEY)})) "
            f"localStorage.setItem({json.dumps(STORE_KEY)}, {json.dumps(json.dumps(blob))});")
    run = await Run("fake", Fake(data)).open(browser, base, FAST, viewport=vp, init=init)
    got = await run.js("[window.__logoReview.prog(), window.__logoReview.current(), window.__logoReview.running(), "
                       "!document.getElementById('resumed').classList.contains('hide'), "
                       "document.getElementById('alerts').textContent, window.__logoReview.exportObj().choices]")
    prog, cur, running, note, alerts, exported = got
    kinds = collections.Counter(e["source"] for e in blob["choices"].values())
    check(prog["choices"] == blob["choices"] and prog["flags"] == blob["flags"] and prog["fix"] == blob["fix"]
          and exported == blob["choices"], f"K-{name}: saved progress changed on load "
          f"({len(prog['choices'])} of {len(blob['choices'])} choices)", mask)
    check(cur == "KR-2" and running and note and "left out" not in alerts and "could not" not in alerts,
          f"K-{name}: grid {cur}, running {running}, note {note}, alerts {alerts[:200]}", mask)
    check(len(kinds) == 7 and kinds["letter"] and kinds["own-icon"], f"K-{name}: the old progress has {dict(kinds)}", mask)
    # any change saves: the entry keeps every old choice, mark and fix, plus started
    tile = grid_codes(data, "KR-2")[5]
    await tap_tile(run, tile, vp)
    await tap_tile(run, tile, vp)
    saved = json.loads(await run.js(f"localStorage.getItem({json.dumps(STORE_KEY)})"))
    check(saved["choices"] == blob["choices"] and saved["flags"] == blob["flags"] and saved["fix"] == blob["fix"]
          and saved["grid"] == "KR-2" and saved["started"] is True and saved["v"] == 1,
          f"K-{name}: saved back differently: {sorted(set(saved) - {'choices'})}", mask)
    await run.page.set_input_files("#importfile", str(old_file))
    await run.wait("document.getElementById('msg').textContent.includes('Loaded')", 10, "the old file loaded")
    msg_ = await run.page.inner_text("#msg")
    check("100 the same" in msg_ and await run.js("window.__logoReview.prog().choices") == blob["choices"],
          f"K-{name}: old export {msg_}", mask)
    await run.page.reload(wait_until="domcontentloaded")
    again = await run.js("window.__logoReview.prog()")
    check(again["choices"] == blob["choices"] and again["flags"] == blob["flags"] and again["fix"] == blob["fix"],
          f"K-{name}: after a reload", mask)
    await run.page.screenshot(path=str(out / f"K-{name}-old-progress.png"))
    check(not run.errors and not run.other, f"K-{name}: page errors {run.errors} · other hosts {run.other}", mask)
    await run.close()
    return (f"K old saved progress ({name} {vp[0]} px): {len(blob['choices'])} choices ({dict(kinds)}), 2 marks and 1 "
            "fix load unchanged, save back unchanged (+ started), export unchanged; the old export loads as '100 the "
            "same'; a reload keeps them; loading resumed by itself on KR-2")


async def scenario_l(browser, base, data, keys, out, mask):
    """What was found is remembered (source, hit / miss, day; never an image), and a reload resumes by itself only after
    Start was tapped: it asks only for the remembered hits (after the checks), never for a known miss, and a remembered
    logo that no longer loads gets its company checked again."""
    comps = {c["c"]: c for c in data["companies"]}
    cfg = dict(FAST, checkEvery=40, badEvery=400, probeSaveMs=200)
    fake = Fake(data)
    run = await Run("fake", fake).open(browser, base, cfg)
    await asyncio.sleep(1.0)
    first = await run.js("[window.__logoReview.running(), document.getElementById('resumed').classList.contains('hide')]")
    check(not run.reqs and first == [False, True], f"L: first visit loaded {len(run.reqs)} / {first}", mask)
    kr1 = grid_codes(data, "KR-1")
    await tap_tile(run, kr1[0], (390, 844))                       # a mark saved, but Start never tapped
    await run.page.reload(wait_until="domcontentloaded")
    await asyncio.sleep(1.0)
    check(not run.reqs and not await run.js("window.__logoReview.running()"), "L: a reload without an earlier Start "
          "loaded logos", mask)
    await tap_tile(run, kr1[0], (390, 844))
    await run.page.click("#start")
    await run.ready("KR-1")
    await run.ready("KR-2")
    await run.wait("window.__logoReview.pending() === 0 && ['bf', 'ld'].every(id => (p => !p.sinceCheck.length && "
                   "!p.ctl.length && !p.ctlBusy)(window.__logoReview.providers[id]))", 60, "every miss confirmed by a check")
    await run.js("window.__logoReview.flushMem()")
    stored = json.loads(await run.js(f"localStorage.getItem({json.dumps(PROBE_KEY)})"))
    day = today_kst()
    want, hits, misses = {}, set(), {}
    for gid in ("KR-1", "KR-2"):
        for c in grid_codes(data, gid):
            for rid, p, r, f in ROUTES:
                if not comps[c][f]:
                    continue
                t = truth(c, rid)
                want.setdefault(c, {})[br.SOURCE[rid]] = ["hit" if t else "miss", day]
                u = url_for(comps[c], rid, keys)
                if t:
                    hits.add(u + "&v=2" if rid == "ldD" else u)
                else:
                    misses.setdefault(c, set()).update({u, u + "&v=2"} if rid == "ldD" else {u})
    nmiss = sum(1 for c in want for x in want[c].values() if x[0] == "miss")
    check(stored["v"] == 1 and stored["page"] == data["meta"]["builtAt"] and stored["probes"] == want,
          f"L: remembered {sum(len(x) for x in stored['probes'].values())} results, expected {sum(len(x) for x in want.values())}",
          mask)
    check("http" not in json.dumps(stored["probes"]) and "data:" not in json.dumps(stored), "L: an address in memory", mask)
    known_miss = set().union(*misses.values())

    # a reload: loading resumes by itself; only the remembered hits are asked for, after the checks
    n0 = len(run.reqs)
    await run.page.reload(wait_until="domcontentloaded")
    note = await run.js("[window.__logoReview.running(), window.__logoReview.current(), "
                        "(e => !e.classList.contains('hide') && e.textContent)(document.getElementById('resumed'))]")
    check(note[0] and note[1] == "KR-1" and "Loading resumed" in (note[2] or "") and "Pause" in note[2],
          f"L: after the reload {note}", mask)
    await run.page.screenshot(path=str(out / "L-phone-resumed.png"))
    await run.ready("KR-1")
    await run.ready("KR-2")
    after = run.reqs[n0:]
    company = {u for _, p, r, ident, v, size, mode, u in after if size == 128 and not fake.control(ident, size)}
    asked_miss = {u for *_, u in after} & known_miss
    check(company == hits and not asked_miss, f"L: after the reload {len(company)} company URLs (expected the "
          f"{len(hits)} remembered hits), {len(asked_miss)} known misses asked again", mask)
    first_company = next(i for i, x in enumerate(after) if x[5] == 128 and not fake.control(x[3], x[5]))
    checks_first = {x[1] for x in after[:first_company] if x[5] != 128}
    check(checks_first == {"bf", "ld"}, f"L: before the first remembered logo, checks from {checks_first}", mask)
    got, vias = await picks_match(run, data, "KR-1", ("bf", "ld"), mask, "L")
    ctr = await run.js("window.__logoReview.counters")
    check(ctr["remembered"] == nmiss, f"L: {ctr['remembered']} remembered misses applied, expected {nmiss}", mask)
    await run.page.click("#resumepause")
    paused = await run.js("[window.__logoReview.running(), document.getElementById('resumed').classList.contains('hide')]")
    check(paused == [False, True], f"L: Pause in the note {paused}", mask)

    # a remembered logo that no longer loads: its company is checked again (every source), nothing else is
    x = next(c for c in kr1 if any(want[c].get(br.SOURCE[r]) == ["hit", day] for r in ("bfI", "bfT")) and c in misses)
    rid = next(r for r in ("bfI", "bfT") if want[x].get(br.SOURCE[r]) == ["hit", day])
    _, p, r, f = next(t for t in ROUTES if t[0] == rid)
    fake.gone.add((p, r, comps[x][f]))
    n1 = len(run.reqs)
    await run.page.reload(wait_until="domcontentloaded")
    await run.ready("KR-1")
    await run.ready("KR-2")
    await run.wait("window.__logoReview.pending() === 0", 30, "timers")
    after2 = {u for *_, u in run.reqs[n1:]}
    first_loads = {u for u in misses[x] if "&v=2" not in u}
    ctr2 = await run.js("window.__logoReview.counters")
    state = await run.js(f"window.__logoReview.state['{x}|{rid}'].s")
    check(first_loads <= after2 and not (after2 & (known_miss - misses[x])) and ctr2["reprobed"] == 1 and state == "miss",
          f"L: the gone logo of {x}: its misses asked again {len(first_loads & after2)} of {len(first_loads)}, other "
          f"misses asked {len(after2 & (known_miss - misses[x]))}, reprobed {ctr2['reprobed']}, state {state}", mask)
    check(not run.errors and not run.other, f"L: page errors {run.errors} · other hosts {run.other}", mask)
    await run.close()
    return (f"L remembered results: {sum(len(v) for v in want.values())} (source, hit/miss, day; no address or image) "
            f"for KR-1 + KR-2; first visit and a reload without Start loaded nothing; after Start, a reload resumed by "
            f"itself with 'Loading resumed' + Pause, ran the checks first, asked only the {len(hits)} remembered hits "
            f"(logo.dev domains: the confirmed second load only), none of the {nmiss} known misses; pre-picks as "
            f"expected; a remembered logo that stopped loading had its company checked again")


async def scenarios(html, data, keys, base, folder, out, mask):
    from playwright.async_api import async_playwright
    comps = {c["c"]: c for c in data["companies"]}
    results = []
    page_i, data_i, icon_codes, iconless, checks = with_icons(html, data, keys, folder)
    (folder / "logo-review-icons.html").write_text(page_i, encoding="utf-8")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)         # no proxy: nothing can leave the machine
        try:
            # A: blocked, checks on
            run = await Run("abort").open(browser, base, {"autostart": True, "canaryRetryMs": 300})
            await run.wait("window.__logoReview.providers.bf.stopped && window.__logoReview.providers.ld.stopped", 30,
                           "both providers stopped")
            await asyncio.sleep(0.5)
            n_by = collections.Counter(p for _, p, *_ in run.reqs)
            company = [u for *_, size, mode, u in run.reqs if size == 128]
            check(n_by == {"bf": 3, "ld": 3} and not company, f"A: requests {dict(n_by)}, company URLs {len(company)}", mask)
            states = collections.Counter((await run.js("Object.entries(window.__logoReview.state)"
                                                       ".filter(([k]) => !k.endsWith('|own')).map(([k, s]) => s.s)")))
            check(set(states) <= {"stopped", "na", "idle"} and states["stopped"] > 0, f"A: states {states}", mask)
            own = collections.Counter((await run.js("Object.entries(window.__logoReview.state)"
                                                    ".filter(([k]) => k.endsWith('|own')).map(([k, s]) => s.s)")))
            check(own["hit"] > 0 and not own["miss"], f"A: our own icons {own} (they are site files: they load)", mask)
            gaps = await run.js("document.querySelectorAll('#grid .b.gap').length")
            dock = await run.page.inner_text("#dock")
            check(gaps == 100 and await run.js("document.getElementById('confirm').disabled") and "Retry" in dock,
                  f"A: gaps {gaps}, dock {dock!r}", mask)
            check(not run.errors and not run.other, f"A: page errors {run.errors} · other hosts {run.other}", mask)
            await run.page.screenshot(path=str(out / "A-phone-blocked.png"))
            await run.ctx.close()
            results.append("A blocked + checks: both providers stopped after 3 check requests each, no company URL "
                           "requested, 100 tiles 'not checked', Confirm off, Retry shown")

            # B: real pace, blocked, nothing before Start
            run = await Run("abort").open(browser, base, {"controls": False})
            await asyncio.sleep(1.5)
            check(not run.reqs, f"B: {len(run.reqs)} requests before Start", mask)
            await run.page.click("#start")
            await asyncio.sleep(10)
            await run.page.click("#pause")
            await asyncio.sleep(0.6)
            gaps_ = {}
            for p in ("bf", "ld"):
                ts = [t for t, pp, *_ in run.reqs if pp == p]
                gaps_[p] = (len(ts), min(b - a for a, b in zip(ts, ts[1:])))
            check(gaps_["bf"][1] >= 0.45 and gaps_["ld"][1] >= 0.22, f"B: smallest gaps {gaps_}", mask)
            check(gaps_["bf"][0] <= 10 / 0.5 + 2 and gaps_["ld"][0] <= 10 / 0.25 + 2, f"B: request counts {gaps_}", mask)
            check(not run.errors and not run.other, f"B: page errors {run.errors} · other hosts {run.other}", mask)
            await run.ctx.close()
            results.append(f"B real pace, 10 s: Brandfetch {gaps_['bf'][0]} requests, smallest gap {gaps_['bf'][1]:.3f} s"
                           f" · logo.dev {gaps_['ld'][0]} requests, smallest gap {gaps_['ld'][1]:.3f} s · none before Start")

            # C: blocked, fast — only the current and the next grid; the current one first
            run = await Run("abort").open(browser, base, {"autostart": True, "controls": False, "bfGapMs": 2,
                                                          "ldGapMs": 2, "timeoutMs": 5000})
            await run.ready("KR-1")
            await run.ready("KR-2")
            await asyncio.sleep(0.5)
            want = {g: {url_for(comps[c], rid, keys) for c in grid_codes(data, g) for rid, *_, f in ROUTES if comps[c][f]}
                    for g in ("KR-1", "KR-2", "KR-3")}
            got = [u for *_, u in run.reqs]
            check(len(got) == len(set(got)) and set(got) == want["KR-1"] | want["KR-2"],
                  f"C: {len(got)} requests, {len(set(got))} distinct, expected {len(want['KR-1'] | want['KR-2'])}", mask)
            for rid, p, r, f in ROUTES:
                seq = [u for _, pp, rr, *_, u in run.reqs if (pp, rr) == (p, r)]
                last1 = max((i for i, u in enumerate(seq) if u in want["KR-1"]), default=-1)
                first2 = min((i for i, u in enumerate(seq) if u in want["KR-2"]), default=len(seq))
                check(last1 < first2, f"C: {rid}: a KR-2 request came before the last KR-1 one", mask)
            n0 = len(run.reqs)
            await run.page.click("#next")
            await run.ready("KR-3")
            got3 = {u for *_, u in run.reqs[n0:]}
            check(got3 == want["KR-3"], f"C: after Next {len(got3)} new URLs, expected KR-3's {len(want['KR-3'])}", mask)
            check(not run.errors and not run.other, f"C: page errors {run.errors} · other hosts {run.other}", mask)
            await run.ctx.close()
            results.append(f"C blocked, fast: {n0:,} requests = exactly KR-1 + KR-2's URLs (as logo_ids.logo_url builds "
                           "them), KR-1 first in every route; Next loaded exactly KR-3's")

            # D: fake answers with CORS, phone and PC
            dl_path = None
            for vp, name in (((390, 844), "phone"), ((1280, 900), "pc")):
                path, line = await scenario_d(browser, base, data_i, keys, out, mask, vp, name, icon_codes, iconless,
                                              checks)
                dl_path = dl_path or path
                results.append(line)
            saved = pathlib.Path(out / "choices.json")
            saved.write_bytes(pathlib.Path(dl_path).read_bytes())

            # E: Load choices in a fresh browser (PC), then a file with bad entries, then a wrong version
            run = await Run("fake", Fake(data_i)).open(browser, base, {}, viewport=(1280, 900),
                                                        page="logo-review-icons.html")
            await run.page.set_input_files("#importfile", str(saved))
            await run.wait("Object.keys(window.__logoReview.prog().choices).length > 0", 10, "choices loaded")
            msg = await run.page.inner_text("#msg")
            mine = json.loads(saved.read_text(encoding="utf-8"))["choices"]
            again = (await run.js("window.__logoReview.exportObj()"))["choices"]
            check(again == mine and "100 new" in msg, f"E: loaded {len(again)} vs {len(mine)}: {msg}", mask)
            check(await run.js("document.getElementById('gridsel').options[0].textContent.includes('reviewed')"),
                  "E: KR-1 not shown as reviewed", mask)
            kr2 = grid_codes(data_i, "KR-2")
            some = comps[kr2[0]]
            bad = {"version": 1, "created": "x", "choices": {
                kr2[0]: {"source": "bf-ticker", "url": url_for(some, "bfT", keys), "reviewed": "2026-12-01"},
                kr2[1]: {"source": "bf-ticker", "url": "data:image/png;base64,AAAA", "reviewed": "2026-12-01"},
                kr2[2]: {"source": "ld-ticker", "url": url_for(comps[kr2[2]], "ldT", {"bf": keys["bf"], "ld": "sk_live1234"}),
                         "reviewed": "2026-12-01"},
                kr2[3]: {"source": "made-up", "url": None, "reviewed": "2026-12-01"},
                "ZZZZZZ": {"source": "letter", "url": None, "reviewed": "2026-12-01"},
                kr2[4]: {"source": "letter", "url": "https://example.com/x.png", "reviewed": "2026-12-01"},
                kr2[5]: {"source": "letter", "url": None}}}
            badf = out / "bad-choices.json"
            badf.write_text(json.dumps(bad), encoding="utf-8")
            await run.page.set_input_files("#importfile", str(badf))
            await run.wait("document.getElementById('msg').textContent.includes('Skipped 6')", 10, "bad file message")
            now = await run.js("window.__logoReview.prog().choices")
            check(set(now) == set(mine) | {kr2[0]}, f"E: after the bad file {len(now)} choices", mask)
            versionf = out / "v2.json"
            versionf.write_text(json.dumps({"version": 2, "choices": {}}), encoding="utf-8")
            await run.page.set_input_files("#importfile", str(versionf))
            await run.wait("document.getElementById('msg').textContent.includes('unknown version')", 10, "version message")
            check(await run.js("Object.keys(window.__logoReview.prog().choices).length") == len(now), "E: version 2 changed choices", mask)
            await run.page.screenshot(path=str(out / "E-pc-loaded.png"))
            check(not run.errors and not run.other, f"E: page errors {run.errors} · other hosts {run.other}", mask)
            await run.ctx.close()
            results.append(f"E Load choices: {len(mine)} choices back unchanged in a fresh browser; a file with 7 entries "
                           "kept the 1 valid one (data: URL, sk_ key, unknown source, unknown code, letter with an "
                           "address, no date refused); version 2 changed nothing")

            # F: logo.dev without CORS headers — agreement off for it
            fast = {"bfGapMs": 5, "ldGapMs": 5, "recheckMs": 1500, "canaryRetryMs": 300, "autostart": True}
            run = await Run("fake", Fake(data, cors={"ld": "none"})).open(browser, base, fast)
            await run.ready("KR-1")
            got, vias = await picks_match(run, data, "KR-1", ("bf",), mask, "F")
            help_ = await run.page.text_content("#agreestate")                   # inside the closed help
            alerts = await run.page.inner_text("#alerts")
            check(vias["agree"] == 0 and "logo.dev: images not readable" in help_ and "agreement off" in help_
                  and "readable" not in alerts and "CORS" not in alerts, f"F: vias {dict(vias)}, help {help_!r}, "
                  f"alerts {alerts!r}", mask)
            check(not run.errors and not run.other, f"F: page errors {run.errors} · other hosts {run.other}", mask)
            await run.ctx.close()
            results.append(f"F logo.dev without CORS: agreement off for it, silently (only the help text says so), "
                           f"KR-1 pre-picks follow the order ({vias['order']} logos, {vias['none']} letter marks)")

            # G: Brandfetch's checks are readable but its logos are not: the audit catches it
            run = await Run("fake", Fake(data, cors={"bf": "checks"})).open(browser, base, fast)
            await run.ready("KR-1", 180)
            got, vias = await picks_match(run, data, "KR-1", ("ld",), mask, "G")
            alerts = await run.page.inner_text("#alerts")
            cors_bf = await run.js("window.__logoReview.providers.bf.cors")
            check(not cors_bf and "reading its images loses logos" in alerts and vias["agree"] == 0,
                  f"G: bf.cors={cors_bf}, vias {dict(vias)}, alerts {alerts}", mask)
            check(not run.errors and not run.other, f"G: page errors {run.errors} · other hosts {run.other}", mask)
            await run.ctx.close()
            results.append("G CORS loses Brandfetch logos: the audited miss loaded the plain way, Brandfetch switched "
                           "to plain loads, its misses tried again; KR-1 pre-picks as expected")

            # H1: blocked -> both stop; the block lifts; Retry -> checks first, then KR-1 loads as expected
            run = await Run("abort").open(browser, base, dict(fast, timeoutMs=4000))
            await run.wait("window.__logoReview.providers.bf.stopped && window.__logoReview.providers.ld.stopped", 30,
                           "both providers stopped")
            n0 = len(run.reqs)
            run.mode, run.fake = "fake", Fake(data)
            await run.page.click("#retry")
            await run.ready("KR-1", 180)
            got, vias = await picks_match(run, data, "KR-1", ("bf", "ld"), mask, "H1")
            after = run.reqs[n0:]
            first_company = next(i for i, x in enumerate(after) if x[5] == 128 and not run.fake.control(x[3], x[5]))
            checks_first = {x[1] for x in after[:first_company] if x[5] != 128}
            check(checks_first == {"bf", "ld"} and not await run.js("window.__logoReview.providers.bf.stopped"),
                  f"H1: before the first logo after Retry, checks from {checks_first}", mask)
            check(not run.errors and not run.other, f"H1: page errors {run.errors} · other {run.other}", mask)
            await run.ctx.close()

            # H2: a KR-2 logo times out; Jack moves to US-5 before its retry: it is not tried again
            fake = Fake(data)
            slow_code = grid_codes(data, "KR-2")[0]
            fake.slow = {comps[slow_code]["tk"]}
            run = await Run("fake", fake).open(browser, base, dict(fast, timeoutMs=800, retryMs=2500))
            await run.wait(f"window.__logoReview.state['{slow_code}|bfT'].tries >= 1", 60, "the slow logo to time out")
            await run.page.select_option("#gridsel", "US-5")
            t_nav = time.monotonic()
            await asyncio.sleep(5)
            window = {comps[c]["tk"] for g in ("US-5", "US-6") for c in grid_codes(data, g)}
            late = [x for x in run.reqs if x[0] > t_nav + 0.3 and not run.fake.control(x[3], x[5])]
            check(late and all(x[3] in window for x in late), f"H2: after the move, requests outside US-5/US-6: "
                  f"{[x[3] for x in late if x[3] not in window][:5]}", mask)
            again = [x for x in run.reqs if x[3] in fake.slow and x[0] > t_nav]
            st_ = await run.js(f"window.__logoReview.state['{slow_code}|bfT'].s")
            check(not again and st_ == "idle", f"H2: the timed-out logo was tried {len(again)} times after the move "
                  f"(state {st_})", mask)
            await run.ready("US-5", 120)
            check(not run.errors and not run.other, f"H2: page errors {run.errors} · other {run.other}", mask)
            await run.ctx.close()
            # I: the icon files are missing from the site: our icons stop, they never count as "no logo"
            bare = pathlib.Path(tempfile.mkdtemp(prefix="logo-review-bare-"))
            (bare / "logo-review.html").write_text(html, encoding="utf-8")
            base2, httpd2 = serve(bare)
            try:
                run = await Run("fake", Fake(data)).open(browser, base2, fast)
                await run.wait("window.__logoReview.providers.own.stopped", 30, "our icons stopped")
                await run.ready_or_gaps("KR-1")
                own = collections.Counter(await run.js("Object.entries(window.__logoReview.state)"
                                                       ".filter(([k]) => k.endsWith('|own')).map(([k, s]) => s.s)"))
                alerts = await run.page.inner_text("#alerts")
                status = await run.js("window.__logoReview.status('KR-1')")
                check("Own icons stopped" in alerts and not own["miss"] and not own["hit"] and own["stopped"] > 0
                      and status["gaps"] > 0 and not status["ready"]
                      and await run.js("document.getElementById('confirm').disabled"),
                      f"I: own {own}, status {status}, alerts {alerts[:200]}", mask)
                check(not run.errors and not run.other, f"I: page errors {run.errors} · other {run.other}", mask)
                await run.ctx.close()
            finally:
                httpd2.shutdown()
            results.append(f"I icon files missing: the known-icon check failed, {own['stopped']} own icons 'not "
                           f"checked' (none counted as no logo), Confirm off for KR-1 ({status['gaps']} gaps)")
            results.append(f"H Retry: both providers stopped, the block lifted, Retry ran the checks first, then KR-1 "
                           f"loaded with pre-picks as expected · a timed-out KR-2 logo was not tried again after the "
                           f"move to US-5 ({len(late)} later requests, all for US-5/US-6)")

            # J: a pasted image address and None of these - find more (phone and PC); the download loads back
            img_base, img_httpd, img_log = https_images(pathlib.Path(tempfile.mkdtemp(prefix="logo-review-img-")))
            try:
                j_path = None
                for vp, name in (((390, 844), "phone"), ((1280, 900), "pc")):
                    j_path, line = await scenario_j(browser, base, data, keys, out, mask, vp, name, img_base, img_log)
                    results.append(line)
                run = await Run("fake", Fake(data)).open(browser, base, {}, viewport=(1280, 900), https_ok=True)
                await run.page.set_input_files("#importfile", str(j_path))
                await run.wait("Object.keys(window.__logoReview.prog().choices).length > 0", 10, "choices loaded")
                mine = json.loads(j_path.read_text(encoding="utf-8"))["choices"]
                again = (await run.js("window.__logoReview.exportObj()"))["choices"]
                msg_ = await run.page.inner_text("#msg")
                check(again == mine and "100 new" in msg_, f"J: the download loaded back as {len(again)}: {msg_}", mask)
                check(not run.errors and not run.other, f"J: page errors {run.errors} · other {run.other}", mask)
                await run.close()
                results.append("J the download with a pasted address and a needs-a-logo loads back unchanged in a "
                               "fresh browser")
            finally:
                img_httpd.shutdown()

            # K: Jack's saved progress and his downloaded file, as the page he is using writes them
            blob = old_progress(data, keys)
            old_file = out / "old-choices.json"
            old_file.write_text(json.dumps({"version": 1, "created": blob["savedAt"], "choices": blob["choices"]},
                                           indent=1) + "\n", encoding="utf-8")
            for vp, name in (((390, 844), "phone"), ((1280, 900), "pc")):
                results.append(await scenario_k(browser, base, data, keys, out, mask, vp, name, old_file))

            # L: what was found, remembered; a reload resumes by itself only after an earlier Start
            results.append(await scenario_l(browser, base, data, keys, out, mask))
        finally:
            await browser.close()
    return results


def serve(folder):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(folder), **k)

        def log_message(self, *a):
            pass

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", httpd


def main(argv):
    src = pathlib.Path(argv[0]) if argv else ROOT / "logo-review.html"
    html = src.read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    keys = json.loads(re.search(r"var KEYS = (\{.*?\});", html).group(1))
    mask = Masker(keys["bf"], keys["ld"])
    out = pathlib.Path(os.environ.get("SMOKE_OUT") or tempfile.mkdtemp(prefix="smoke-logo-review-"))
    out.mkdir(parents=True, exist_ok=True)
    folder = pathlib.Path(tempfile.mkdtemp(prefix="logo-review-site-"))
    (folder / "logo-review.html").write_text(html, encoding="utf-8")
    if (src.parent / "logo-review").is_dir():                                 # our own icons, as the site serves them
        shutil.copytree(src.parent / "logo-review", folder / "logo-review")
    base, httpd = serve(folder)
    try:
        results = asyncio.run(scenarios(html, data, keys, base, folder, out, mask))
    finally:
        httpd.shutdown()
    for line in results:
        print("· " + line)
    print(f"logo-review.html smoke: {len(results)} scenarios passed · 0 page errors · no request left the browser for "
          f"the logo providers · screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
