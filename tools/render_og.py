#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Link-preview image (og-v19.png, 1200 x 630) for v19.0 Part F, rendered from plain HTML with Playwright's Chromium.

  python3 tools/render_og.py            # writes og-v19.png at the repository root (og:image in template.html, index.html)
  python3 tools/render_og.py OUT.png    # writes somewhere else

Layout follows docs/design/v19/reference/OgPreview.dc.html (Jack approved, 2026-11-03), rebuilt as plain HTML: the
board needs the design tool's support.js and /_blob/ addresses, so it is not opened here.
  - warm page background #F5F3EF, a 14 px navy bar on the left;
  - baepi-mark and "뱁새" at 96 px; "내 기준으로 만드는 / 포트폴리오" at 46 px; the catchphrase at 28 px;
  - baepi-og on a soft green circle on the right.
Jack's 뱁이 images are used as they are (docs/design/v19/assets), never redrawn or edited.
Pretendard is loaded by explicit file path (fonts/pretendard/, the same files the app uses). Before the screenshot the
script waits for document.fonts and checks that every Korean glyph on the card is drawn with Pretendard; if it is not,
it stops with an error instead of writing a picture in a fallback font.
"""
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_CSS = ROOT / "fonts" / "pretendard" / "pretendard-variable.css"
MARK = ROOT / "docs" / "design" / "v19" / "assets" / "baepi-mark.png"
BIRD = ROOT / "docs" / "design" / "v19" / "assets" / "baepi-og.png"
W, H = 1200, 630
# A new file name (Jack, 2026-11-03), so KakaoTalk and others fetch the new picture instead of their cached og.png.
OUT_NAME = "og-v19.png"

# Approved text (docs/tasks/v19.0-layout-c.md Part E · Part F): the name, the descriptor in two lines, the catchphrase.
NAME = "뱁새"
DESCRIPTOR = ["내 기준으로 만드는", "포트폴리오"]
CATCH = "철새처럼 옮겨 다니지 않는 투자"
# Colours from src/ui/tokens.js: page, ink, text2, heroCalm
PAGE, INK, TEXT2, GREEN = "#F5F3EF", "#1C2B45", "#5B6576", "#EDF4EF"
FAMILY = "Pretendard Variable"


def page_html():
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="{FONT_CSS.as_uri()}">
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ width: {W}px; height: {H}px; overflow: hidden; }}
  .card {{ width: {W}px; height: {H}px; position: relative; overflow: hidden; background: {PAGE}; color: {INK};
          font-family: '{FAMILY}'; letter-spacing: -0.01em; }}
  .bar {{ position: absolute; left: 0; top: 0; bottom: 0; width: 14px; background: {INK}; }}
  .text {{ position: absolute; left: 92px; top: 112px; width: 640px; }}
  .brand {{ display: flex; align-items: center; gap: 18px; }}
  .brand img {{ width: 92px; height: 92px; display: block; }}
  .brand span {{ font-size: 96px; font-weight: 800; letter-spacing: -0.05em; line-height: 1; }}
  .desc {{ margin: 46px 0 0; font-size: 46px; font-weight: 700; line-height: 1.3; letter-spacing: -0.03em; }}
  .catch {{ margin: 22px 0 0; font-size: 28px; font-weight: 400; color: {TEXT2}; }}
  .circle {{ position: absolute; right: 70px; bottom: 40px; width: 400px; height: 400px; border-radius: 200px; background: {GREEN}; }}
  .bird {{ position: absolute; right: 86px; bottom: 34px; width: 380px; height: auto; }}
</style></head>
<body><div class="card">
  <div class="bar"></div>
  <div class="text">
    <div class="brand"><img src="{MARK.as_uri()}" alt=""><span>{NAME}</span></div>
    <p class="desc">{DESCRIPTOR[0]}<br>{DESCRIPTOR[1]}</p>
    <p class="catch">{CATCH}</p>
  </div>
  <div class="circle"></div>
  <img class="bird" src="{BIRD.as_uri()}" alt="">
</div></body></html>"""


# Every Korean letter on the card must come from Pretendard: load the exact faces it needs, then compare each letter's
# width in Pretendard with its width in two different fallback fonts. A letter Pretendard did not draw takes the
# fallback's width, so both comparisons cannot differ at once.
CHECK_JS = """async ([family, text]) => {
  await document.fonts.ready;
  const letters = [...new Set([...text].filter((c) => /[가-힣]/.test(c)))];
  const weights = [400, 700, 800];
  for (const w of weights) await document.fonts.load(`${w} 40px '${family}'`, letters.join(''));
  await document.fonts.ready;
  const cv = document.createElement('canvas').getContext('2d');
  const bad = [];
  for (const c of letters) {
    for (const w of weights) {
      cv.font = `${w} 40px '${family}', monospace`; const a = cv.measureText(c).width;
      cv.font = `${w} 40px monospace`; const m = cv.measureText(c).width;
      cv.font = `${w} 40px '${family}', serif`; const b = cv.measureText(c).width;
      cv.font = `${w} 40px serif`; const s = cv.measureText(c).width;
      if (!(document.fonts.check(`${w} 40px '${family}'`, c) && Math.abs(a - b) < 0.01 && (Math.abs(a - m) > 0.01 || Math.abs(b - s) > 0.01))) bad.push(c + '@' + w);
    }
  }
  const imgs = [...document.images].map((i) => [i.complete, i.naturalWidth]);
  return { letters: letters.length, bad, imgs, loaded: [...document.fonts].filter((f) => f.status === 'loaded').length };
}"""


def main():
    out = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / OUT_NAME
    for f in (FONT_CSS, MARK, BIRD):
        assert f.exists(), f"missing {f}"
    html = page_html()
    tmp = ROOT / "tools" / ".og-card.html"           # beside the repo files so file:// paths resolve the same way
    tmp.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("requestfailed", lambda r: errors.append("request failed: " + r.url))
            page.goto(tmp.as_uri(), wait_until="load")
            r = page.evaluate(CHECK_JS, [FAMILY, NAME + "".join(DESCRIPTOR) + CATCH])
            print(f"· Korean letters: {r['letters']} · drawn in another font: {r['bad'] or 'none'} · font files loaded: {r['loaded']}"
                  f" · images: {r['imgs']}")
            assert not errors, errors
            assert r["letters"] >= 20 and not r["bad"], f"Pretendard did not draw: {r['bad']}"
            assert all(ok and w > 0 for ok, w in r["imgs"]), f"an image did not load: {r['imgs']}"
            page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": W, "height": H})
            browser.close()
    finally:
        tmp.unlink(missing_ok=True)
    print(f"link-preview image written: {out} ({W} x {H})")


if __name__ == "__main__":
    main()
