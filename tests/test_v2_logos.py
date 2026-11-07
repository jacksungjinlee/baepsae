# -*- coding: utf-8 -*-
"""v19.3a: company logos in 2.0 (src/v2/logo.jsx · load.js loadLogoIndex · main.jsx), with the letter mark on any failure.

- Pure checks in Node: logoSrc gives an address only for an index entry with a plain .webp/.png file name in logos/
  (no path, no other site), and the index check (logoIndexOk) refuses anything that is not version 1 with a logos map.
- In headless Chromium on the locally served site (the committed app.html, the smoke test's fixture data):
  · logos/ present: a company with a good file shows its picture on top of its letter mark; a listed file that is
    missing or not a picture, and a company not in the index, keep the letter mark; the console counts the failures;
    an entry pointing at another site or another folder is ignored (no request leaves the site);
  · a slow picture (4 s, longer than the old 3 s timer) still shows: there is no timer (lazy pictures below the fold);
  · no logos/ folder, or a broken index.json: every company shows its letter mark, with one console warning;
  · the preview page never asks for the index and draws no picture.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def bundle(tmp):
    entry = os.path.join(tmp, "entry.js")
    with open(entry, "w", encoding="utf-8") as f:
        f.write(f"export {{ logoSrc, LOGO_FILE_RX }} from {json.dumps(os.path.join(ROOT, 'src', 'v2', 'logo.jsx'))};\n")
        f.write(f"export {{ logoIndexOk, LOGO_DIR }} from {json.dumps(os.path.join(ROOT, 'src', 'v2', 'load.js'))};\n")
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                        "--charset=utf8", f"--outfile={tmp}/l.mjs", "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return os.path.join(tmp, "l.mjs")


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_logo_address_only_for_plain_files_in_logos():
    tmp = tempfile.mkdtemp()
    try:
        mod = bundle(tmp)
        code = (f"import * as L from {json.dumps(mod)};\n"
                "const logos = { '005930': { file: '005930.webp' }, 'BRK-B': { file: 'BRK-B.png' }, A: { file: '../data.json' },"
                " B: { file: 'https://evil.example/x.png' }, C: { file: 'x.svg' }, D: { file: 5 }, E: null, F: { file: '//x.webp' } };\n"
                "console.log(JSON.stringify({ dir: L.LOGO_DIR, a: ['005930', 'BRK-B', 'A', 'B', 'C', 'D', 'E', 'F', 'ZZZ', '', 'toString']"
                ".map((c) => L.logoSrc(logos, L.LOGO_DIR, c)), none: L.logoSrc(null, L.LOGO_DIR, '005930'),"
                " ok: [{ version: 1, logos: {} }, { version: 2, logos: {} }, { version: 1, logos: [] }, { version: 1 }, null, []]"
                ".map(L.logoIndexOk) }));")
        r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=tmp, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        got = json.loads(r.stdout)
        assert got["dir"] == "./logos/"
        assert got["a"] == ["./logos/005930.webp", "./logos/BRK-B.png"] + [None] * 9
        assert got["none"] is None and got["ok"] == [True, False, False, False, False, False]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_logo_credit_on_the_sources_page_is_the_approved_text():
    """데이터 출처 (old app src/info.jsx; 2.0's menu opens it): the wording approved in Part A (Jack, 2026-11-06; changed
    by Jack on 2026-11-07 when homepage icons were added: "일부는 각 회사 홈페이지") and
    logo.dev's own link text, once each, the link opening logo.dev in a new tab with noopener noreferrer."""
    src = open(os.path.join(ROOT, "src", "info.jsx"), encoding="utf-8").read()
    for text in ("그림 · 로고 출처", "회사 로고: Logo.dev, 일부는 각 회사 홈페이지. 로고의 권리는 각 회사에 있어요.", "Logos provided by Logo.dev"):
        assert src.count(text) == 1, text
    assert src.count('<a href="https://logo.dev" target="_blank" rel="noopener noreferrer"') == 1
    assert "Part A" in src.split("그림 · 로고 출처", 1)[0][-600:]                           # the comment cites where it is approved
    sources_card = src.split('<Card id="info-sources">', 1)[1].split("</Card>", 1)[0]
    assert "Logos provided by Logo.dev" in sources_card                                     # inside the 데이터 출처 card
    old = open(os.path.join(ROOT, "baepsae.html"), encoding="utf-8").read()
    assert old.count('href:"https://logo.dev",target:"_blank",rel:"noopener noreferrer"') == 1
    for text in ("그림 · 로고 출처", "회사 로고: Logo.dev, 일부는 각 회사 홈페이지. 로고의 권리는 각 회사에 있어요.", "Logos provided by Logo.dev"):
        assert old.count(text) == 1, text
    assert "logo.dev" not in open(os.path.join(ROOT, "app.html"), encoding="utf-8").read().lower()  # 2.0 has no link


# ── in the browser ──

pw = pytest.importorskip("playwright.sync_api")
PIL = pytest.importorskip("PIL")


def webp128(color):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
    ImageDraw.Draw(im).ellipse((10, 10, 118, 118), fill=color)
    b = io.BytesIO()
    im.save(b, "WEBP", quality=90)
    return b.getvalue()


def entry(f):
    return {"file": f, "route": "ticker", "w": 512, "h": 512, "vector": False, "flags": []}


@pytest.fixture(scope="module")
def browser():
    import smoke_v2 as S
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=S.chromium_path())
        yield b
        b.close()


def site_with(logos=None, raw_index=None):
    """The smoke test's site (committed app.html + fixture data) plus a logos/ folder as given."""
    import smoke_v2 as S
    site = S.build_site(S.read_fixtures())
    shutil.copy(os.path.join(ROOT, "app-preview.html"), site)
    if logos is not None or raw_index is not None:
        d = os.path.join(site, "logos")
        os.makedirs(d)
        for name, body in (logos or {}).get("files", {}).items():
            with open(os.path.join(d, name), "wb") as fh:
                fh.write(body)
        with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as fh:
            fh.write(raw_index if raw_index is not None else
                     json.dumps({"version": 1, "size": 128, "logos": logos["index"]}))
    return site


def open_page(browser, site, path, slow=0):
    import smoke_v2 as S
    srv, base = S.serve(site)
    ctx = browser.new_context(viewport={"width": 390, "height": 780}, device_scale_factor=2, locale="ko-KR",
                              service_workers="block")
    seen = {"outside": [], "logos": [], "console": [], "errors": []}

    def route(r):
        u = r.request.url
        if not u.startswith(base):
            seen["outside"].append(u)
            r.abort()
            return
        if "/logos/" in u:
            seen["logos"].append(u[len(base):])
            if slow and u.endswith(".webp"):
                time.sleep(slow)
        r.continue_()
    ctx.route("**/*", route)
    page = ctx.new_page()
    page.set_default_timeout(15000)
    page.on("console", lambda m: seen["console"].append((m.type, m.text)))
    page.on("pageerror", lambda e: seen["errors"].append(str(e)))
    page.goto(base + path, wait_until="domcontentloaded")
    return srv, ctx, page, seen


def mark(page, code):
    return page.locator(f'[data-ui-v2="company"] [data-ui-v2="co-mark"][data-t="{code}"]').first


def company(page, code):
    page.evaluate("(h) => { location.hash = h; }", f"#stocks/{code}")
    page.locator('[data-ui-v2="company"]').wait_for(state="visible")
    page.wait_for_function("(t) => { const e = document.querySelector('[data-ui-v2=\"company\"] [data-ui-v2=\"co-mark\"]');"
                           " return !!e && e.dataset.t === t && !['idle', 'loading', 'wait'].includes(e.dataset.logo); }", arg=code)
    return mark(page, code)


def test_logos_show_and_every_failure_keeps_the_letter_mark(browser):
    good = webp128((200, 30, 40, 255))
    site = site_with({"files": {"005930.webp": good, "AAPL.webp": b"not a picture at all"},
                      "index": {"005930": entry("005930.webp"), "005935": dict(entry("005930.webp"), via="005930"),
                                "000660": entry("000660.webp"), "AAPL": entry("AAPL.webp"),
                                "005380": entry("https://evil.example/x.webp"), "373220": entry("../data.json")}})
    srv, ctx, page, seen = open_page(browser, site, "/app.html?dev=1")
    try:
        page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        m = company(page, "005930")
        assert m.get_attribute("data-logo") == "shown"
        img = m.locator("img")
        assert img.evaluate("(i) => i.complete && i.naturalWidth === 128 && getComputedStyle(i).opacity === '1'")
        assert img.get_attribute("src") == "./logos/005930.webp" and img.get_attribute("loading") == "lazy"
        assert m.locator("[data-initial]").count() == 1                                           # the mark stays underneath
        assert company(page, "005935").get_attribute("data-logo") == "shown"                      # preferred: issuer's file
        for code in ("000660", "AAPL"):                                                          # missing · not a picture
            mk = company(page, code)
            assert mk.get_attribute("data-logo") == "gone" and mk.locator("img").count() == 0, code
            assert mk.locator("[data-initial]").get_attribute("data-initial"), code
        for code in ("005380", "373220", "207940"):                                              # bad entry · not listed
            mk = company(page, code)
            assert mk.get_attribute("data-logo") == "none" and mk.locator("img").count() == 0, code
        assert seen["outside"] == [] and not any("evil" in u or "data.json" in u for u in seen["logos"])
        assert seen["logos"].count("/logos/index.json") == 1                                     # the index once
        texts = [t for _, t in seen["console"]]
        assert any("companies have a logo file" in t for t in texts)
        assert any("logo file failed for 000660" in t for t in texts) and any("logo file failed for AAPL" in t for t in texts)
        page.wait_for_timeout(1800)                                                              # the summary line
        summary = [t for _, t in seen["console"] if t.startswith("[v2] company logos: shown")]
        assert summary and "file failed 2" in summary[-1], summary
        assert seen["errors"] == []
    finally:
        ctx.close()
        srv.shutdown()
        shutil.rmtree(site, ignore_errors=True)


def test_a_slow_logo_still_shows_there_is_no_timer(browser):
    site = site_with({"files": {"005930.webp": webp128((20, 90, 200, 255))}, "index": {"005930": entry("005930.webp")}})
    srv, ctx, page, seen = open_page(browser, site, "/app.html?dev=1", slow=4.0)
    try:
        page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        page.evaluate("(h) => { location.hash = h; }", "#stocks/005930")
        page.locator('[data-ui-v2="company"]').wait_for(state="visible")
        page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"company\"] [data-ui-v2=\"co-mark\"]');"
                               " return !!e && e.dataset.logo === 'shown'; }", timeout=15000)
        assert not any("logo file failed for" in t for _, t in seen["console"])
    finally:
        ctx.close()
        srv.shutdown()
        shutil.rmtree(site, ignore_errors=True)


@pytest.mark.parametrize("how", ["no-folder", "broken-index", "wrong-version"])
def test_without_a_usable_index_every_company_shows_its_letter_mark(browser, how):
    site = {"no-folder": lambda: site_with(),
            "broken-index": lambda: site_with(raw_index="{ not json"),
            "wrong-version": lambda: site_with(raw_index=json.dumps({"version": 9, "logos": {"005930": entry("005930.webp")}}))}[how]()
    srv, ctx, page, seen = open_page(browser, site, "/app.html?dev=1")
    try:
        page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        m = company(page, "005930")
        assert m.get_attribute("data-logo") == "fail" and m.locator("img").count() == 0
        assert m.locator("[data-initial]").get_attribute("data-initial") == "삼"
        warns = [t for k, t in seen["console"] if "logos/index.json not loaded" in t]
        assert len(warns) == 1 and seen["errors"] == [] and seen["outside"] == []
        assert [u for u in seen["logos"] if u != "/logos/index.json"] == []
    finally:
        ctx.close()
        srv.shutdown()
        shutil.rmtree(site, ignore_errors=True)


def test_preview_never_asks_for_logos(browser):
    site = site_with({"files": {"005930.webp": webp128((1, 2, 3, 255))}, "index": {"005930": entry("005930.webp")}})
    srv, ctx, page, seen = open_page(browser, site, "/app-preview.html?dev=1#stocks")
    try:
        page.locator('[data-ui-v2="co-mark"]').first.wait_for(state="visible")
        page.wait_for_timeout(1000)
        assert seen["logos"] == [] and page.locator('[data-ui-v2="co-mark"] img').count() == 0
        assert page.locator('[data-ui-v2="co-mark"]').first.get_attribute("data-logo") == "off"
    finally:
        ctx.close()
        srv.shutdown()
        shutil.rmtree(site, ignore_errors=True)
