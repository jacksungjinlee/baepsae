#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contact sheets for the logo test (v19.1 Part L): the largest companies with the logo the best mix chose, as PNG
grids (logo + rank + code + name + which route found it), so a person can spot wrong matches.

  python3 tools/logo_test/contact_sheet.py                      # after run_test.py: <out>/contact_sheet_kr.png and _us.png
  python3 tools/logo_test/contact_sheet.py --side all           # the 200 largest of KR and US together (mostly US)
  python3 tools/logo_test/contact_sheet.py --placeholders 24    # dry run: local placeholder images, no provider, no key
  python3 tools/logo_test/contact_sheet.py --images DIR         # logos from a local folder (<code>.png|webp|jpg|svg)

Default --side kr,us: one sheet of the 200 largest Korean-listed companies and one of the 200 largest US ones (the
200 largest of both together are 196 US companies, which would hide Korean wrong matches). ETFs and funds are left out.
Logos are hotlinked from the providers exactly as the app would show them (an <img> on a page served from
http://127.0.0.1, paced to --rate images per second); nothing is saved except the PNG screenshot, in the scratch folder.
Keys come only from BRANDFETCH_CLIENT_ID / LOGODEV_TOKEN and never appear in the picture or the log.

Korean names are drawn with Noto Sans CJK when one of NOTO_CANDIDATES exists (explicit paths), else with Pretendard
from fonts/pretendard/ (the app's font files). Before the screenshot every Korean letter is checked to be drawn by that
font (same check as tools/render_og.py); if not, the script tries the next font, then stops instead of writing a
picture in a fallback font.
"""
import argparse
import asyncio
import hashlib
import html
import pathlib
import sys

from logo_common import (BF_BASE, LD_BASE, ROOT, Masker, browser_launch_args, log_factory, logo_url, out_dir, read_csv,
                         read_keys, run_masked, serve, top_companies)

NOTO_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
    "/usr/share/fonts/noto/NotoSansKR-Regular.ttf",
]
PRETENDARD_DIR = ROOT / "fonts" / "pretendard"
COLS, CELL_W, CELL_H = 10, 168, 176
SOURCE_LABEL = {"brandfetch": "BF", "logodev": "LD", "placeholder": "PH", "local": "file"}

CHECK_JS = """async ([family, text]) => {
  await document.fonts.ready;
  const letters = [...new Set([...text].filter((c) => /[가-힣]/.test(c)))];
  const weights = [400, 700];
  for (const w of weights) await document.fonts.load(`${w} 14px '${family}'`, letters.join(''));
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
  return { letters: letters.length, bad };
}"""

# Assign each logo's src at a steady pace (no burst of 200 requests), then wait until every image settled. The page on
# disk holds key placeholders only; the keys are filled in here, in the browser's memory.
KEY_SLOTS = {"brandfetch": "__BF_KEY__", "logodev": "__LD_KEY__"}
LOAD_JS = """async ([rate, timeoutMs, subs]) => {
  const imgs = [...document.querySelectorAll('img[data-src]')];
  const fill = (u) => Object.entries(subs).reduce((t, [k, v]) => t.split(k).join(encodeURIComponent(v)), u);
  const gap = 1000 / Math.max(rate, 0.1);
  const done = imgs.map((img) => new Promise((res) => {
    img.addEventListener('load', () => res(true), { once: true });
    img.addEventListener('error', () => res(false), { once: true });
  }));
  for (const img of imgs) { img.src = fill(img.dataset.src); await new Promise((r) => setTimeout(r, gap)); }
  const all = await Promise.race([Promise.all(done), new Promise((r) => setTimeout(() => r(null), timeoutMs))]);
  let ok = 0, failed = 0;
  imgs.forEach((img) => {
    if (img.complete && img.naturalWidth > 0) { ok++; return; }
    failed++;
    const box = img.parentElement; box.classList.add('failed'); box.textContent = 'load failed';
  });
  return { n: imgs.length, ok, failed, timedOut: all === null };
}"""


def font_choices():
    """[(label, css, family, mounts)] in the order to try: Noto CJK files that exist, then Pretendard."""
    out = []
    for p in NOTO_CANDIDATES:
        f = pathlib.Path(p)
        if f.exists():
            css = (f"@font-face {{ font-family: 'NotoCJKLocal'; src: url('/noto/{f.name}'); font-weight: 100 900; }}")
            out.append((f"Noto CJK ({f})", css, "NotoCJKLocal", {"/noto/": f.parent}))
    if (PRETENDARD_DIR / "pretendard-variable.css").exists():
        out.append((f"Pretendard ({PRETENDARD_DIR / 'pretendard-variable.css'})",
                    "@import url('/fonts/pretendard/pretendard-variable.css');", "Pretendard Variable",
                    {"/fonts/pretendard/": PRETENDARD_DIR}))
    return out


def page_html(title, cells, font_css, family):
    css = f"""{font_css}
  html, body {{ margin: 0; background: #FFFFFF; color: #1C2B45; }}
  body {{ font-family: '{family}', sans-serif; width: {COLS * CELL_W + 32}px; padding: 16px; box-sizing: border-box; }}
  h1 {{ font-size: 20px; font-weight: 700; margin: 0 0 4px; }}
  p.sub {{ font-size: 13px; margin: 0 0 12px; color: #5B6576; }}
  .grid {{ display: grid; grid-template-columns: repeat({COLS}, {CELL_W}px); }}
  .cell {{ width: {CELL_W}px; height: {CELL_H}px; box-sizing: border-box; border: 1px solid #E3E6EB; padding: 6px;
          display: flex; flex-direction: column; align-items: center; gap: 4px; overflow: hidden; }}
  .top {{ width: 100%; display: flex; justify-content: space-between; font-size: 11px; color: #5B6576; }}
  .box {{ width: 72px; height: 72px; flex: none; display: flex; align-items: center; justify-content: center;
         border-radius: 8px; font-size: 11px; color: #8A93A3;
         background-color: #FFFFFF;
         background-image: linear-gradient(45deg, #EEF0F3 25%, transparent 25%), linear-gradient(-45deg, #EEF0F3 25%, transparent 25%),
           linear-gradient(45deg, transparent 75%, #EEF0F3 75%), linear-gradient(-45deg, transparent 75%, #EEF0F3 75%);
         background-size: 12px 12px; background-position: 0 0, 0 6px, 6px -6px, -6px 0; }}
  .box img {{ max-width: 72px; max-height: 72px; display: block; }}
  .box.none {{ border: 1px dashed #B8BFCC; background-image: none; }}
  .box.failed {{ border: 1px solid #B4232F; color: #B4232F; background-image: none; }}
  .name {{ font-size: 13px; font-weight: 700; line-height: 1.25; text-align: center; max-height: 33px; overflow: hidden;
          word-break: keep-all; overflow-wrap: anywhere; }}
  .src {{ font-size: 10px; color: #5B6576; text-align: center; }}
  .src.via {{ color: #9A5B00; }}
"""
    body = "\n".join(cells)
    return (f"<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"referrer\" "
            f"content=\"strict-origin-when-cross-origin\"><style>{css}</style></head><body>"
            f"<h1>{html.escape(title)}</h1><p class=\"sub\">Logo test contact sheet (tools/logo_test). Checkerboard = "
            f"transparent area. Orange source = taken from the common share.</p><div class=\"grid\">{body}</div>"
            f"</body></html>")


def cell_html(row, src, pos):
    rank = pos                                           # place by market cap on this sheet (ETFs and funds left out)
    prov, route = row.get("provider", ""), row.get("route", "")
    if src:
        box = f'<div class="box"><img data-src="{html.escape(src)}" alt=""></div>'
        label = f"{SOURCE_LABEL.get(prov, prov)} {route}"
        if row.get("via_code"):
            label += f" ← {row['via_code']}"
    else:
        box, label = '<div class="box none">no logo</div>', "–"
    via = " via" if row.get("via_code") else ""
    return (f'<div class="cell"><div class="top"><span>#{html.escape(str(rank))}</span>'
            f'<span>{html.escape(row["code"])}</span></div>{box}'
            f'<div class="name">{html.escape(row.get("name") or "")}</div>'
            f'<div class="src{via}">{html.escape(label)}</div></div>')


def make_placeholders(rows, folder):
    """Dry run: a plain coloured shape per company (no text, no logo), every third one 'no logo'."""
    from PIL import Image, ImageDraw
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i, r in enumerate(rows):
        r = dict(r)
        if i % 3 == 2:
            r.update(provider="", route="", ident="")
        else:
            h = hashlib.md5(r["code"].encode()).digest()
            im = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            col = (h[0], h[1], h[2], 255)
            if i % 2:
                d.ellipse((14, 14, 114, 114), fill=col)
            else:
                d.rounded_rectangle((8, 30, 120, 98), radius=18, fill=col)
            name = f"{r['code']}.png"
            im.save(folder / name)
            r.update(provider="placeholder", route="local", ident=name)
        out.append(r)
    return out


async def render(rows_by_sheet, srcs, out, mounts, rate, headed, log, subs=None):
    from playwright.async_api import async_playwright
    written = []
    fonts = font_choices()
    if not fonts:
        raise SystemExit("!! no Korean font: neither Noto CJK nor fonts/pretendard/ exists")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**browser_launch_args(headed))
        for sheet, (title, rows) in rows_by_sheet.items():
            text = title + "".join(r.get("name") or "" for r in rows)
            for label, font_css, family, font_mount in fonts:
                folder = out / "sheet"
                folder.mkdir(parents=True, exist_ok=True)
                cells = [cell_html(r, srcs.get(r["code"], ""), i) for i, r in enumerate(rows, 1)]
                (folder / f"{sheet}.html").write_text(page_html(title, cells, font_css, family), encoding="utf-8")
                base, stop = serve({"/": folder, **mounts, **font_mount})
                try:
                    page = await browser.new_page(viewport={"width": COLS * CELL_W + 32, "height": 200})
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    await page.goto(f"{base}/{sheet}.html", wait_until="load")
                    chk = await page.evaluate(CHECK_JS, [family, text])
                    if chk["bad"]:
                        log(f"!! {sheet}: {label} did not draw {len(chk['bad'])} letters ({chk['bad'][:6]}) — next font")
                        await page.close()
                        continue
                    res = await page.evaluate(LOAD_JS, [rate, 120000, subs or {}])
                    png = out / f"contact_sheet_{sheet}.png"
                    await page.screenshot(path=str(png), full_page=True)
                    await page.close()
                    assert not errors, errors
                    log(f"· {sheet}: {len(rows)} companies · logo picked {sum(1 for r in rows if srcs.get(r['code']))} · "
                        f"images loaded {res['ok']} · failed {res['failed']}" + (" · TIMED OUT" if res["timedOut"] else "")
                        + f" · font {label}: {chk['letters']} Korean letters, all drawn")
                    written.append(png)
                    break
                finally:
                    stop()
            else:
                raise SystemExit(f"!! {sheet}: no font drew every Korean letter; no picture written")
        await browser.close()
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=None, help="scratch folder (default: LOGO_TEST_DIR or the session scratchpad /logos)")
    ap.add_argument("--tickers", default=None, help="tickers.csv (placeholder mode; default <out>/tickers.csv)")
    ap.add_argument("--mix", default=None, help="mix.csv from run_test.py (default <out>/mix.csv)")
    ap.add_argument("--side", default="kr,us", help="kr,us (two sheets, default) · kr · us · all")
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--images", default=None, help="folder of local logos named <code>.png|webp|jpg|svg")
    ap.add_argument("--placeholders", type=int, default=0, help="dry run with N placeholder images per sheet")
    ap.add_argument("--rate", type=float, default=4.0, help="hotlinked images per second (default 4)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--bf-base", default=BF_BASE, help=argparse.SUPPRESS)
    ap.add_argument("--ld-base", default=LD_BASE, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    out = out_dir(a.out)
    keys, _ = read_keys(())
    log = log_factory(Masker(keys["brandfetch"], keys["logodev"]))

    sides = [s.strip() for s in a.side.split(",") if s.strip()]
    if any(s not in ("kr", "us", "all") for s in sides):
        ap.error("--side takes kr, us, all")
    mounts, srcs = {}, {}
    if a.placeholders:
        tickers = read_csv(pathlib.Path(a.tickers) if a.tickers else out / "tickers.csv")
        rows_by_sheet = {}
        for s in sides:
            rows = make_placeholders(top_companies(tickers, a.placeholders, s), out / "placeholders")
            rows_by_sheet[s] = (f"Placeholder dry run — {s.upper()} {len(rows)} largest", rows)
            for r in rows:
                if r["provider"] == "placeholder":
                    srcs[r["code"]] = f"/img/{r['ident']}"
        mounts["/img/"] = out / "placeholders"
        rate = 50.0
    else:
        mix_path = pathlib.Path(a.mix) if a.mix else out / "mix.csv"
        if not mix_path.exists():
            raise SystemExit(f"!! {mix_path} not found — run run_test.py first (or use --placeholders N)")
        mix = read_csv(mix_path)
        rows_by_sheet = {s: (f"{s.upper()} — {len(top_companies(mix, a.top, s))} largest companies, best mix",
                             top_companies(mix, a.top, s)) for s in sides}
        if a.images:
            folder = pathlib.Path(a.images).resolve()
            mounts["/img/"] = folder
            for _, (_, rows) in rows_by_sheet.items():
                for r in rows:
                    for ext in ("png", "webp", "jpg", "svg"):
                        if (folder / f"{r['code']}.{ext}").exists():
                            srcs[r["code"]] = f"/img/{r['code']}.{ext}"
                            r.update(provider="local", route=ext)
                            break
            rate = 50.0
        else:
            need = {r["provider"] for _, (_, rows) in rows_by_sheet.items() for r in rows if r.get("provider")}
            missing = [n for p, n in (("brandfetch", "BRANDFETCH_CLIENT_ID"), ("logodev", "LOGODEV_TOKEN"))
                       if p in need and not keys[p]]
            if missing:
                raise SystemExit(f"!! missing environment variables: {', '.join(missing)}")
            for _, (_, rows) in rows_by_sheet.items():
                for r in rows:
                    if r.get("provider"):
                        srcs[r["code"]] = logo_url(r["provider"], r["route"], r["ident"], KEY_SLOTS[r["provider"]],
                                                   bf_base=a.bf_base, ld_base=a.ld_base)
            rate = a.rate
    subs = {KEY_SLOTS[p]: keys[p] for p in KEY_SLOTS if keys[p]}
    written = asyncio.run(render(rows_by_sheet, srcs, out, mounts, rate, a.headed, log, subs))
    for p in written:
        log(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(run_masked(main))
