#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contact sheet of the site icons (logo plan step 4): what Jack looks over before any of them goes live.

  python3 tools/logos/site_icons_sheet.py --html PATH/contact-sheet.html      # + PATH/contact-sheet-p01.png …

Reads what tools/logos/site_icons.py wrote (decisions.json, kr/, raw/, collect.jsonl in $SITE_ICONS_DIR, else
$TMPDIR/site_icons) and the live data.json (company names and market caps; names are never written into this
repository). Writes one HTML file with every image inlined (it opens on its own, offline):
  - the counts (tried / reachable / robots / found / >= 96 px / generic / kept) and kept by size group
    (rank by market cap among Korean common shares: top 200, #201-753, #754-1,306, #1,307-1,858, #1,859+);
  - every kept icon (128 px PNG on a checkerboard, so white and transparent icons show), largest company first,
    with its name, code, domain and rank;
  - a sample of what was dropped (up to 120): every icon rejected as generic first (grouped, rule a/b/c), then
    too-small ones, each with the reason.
and the same as PNG pages of about 120 icons (headless Chromium; Korean names drawn with the repository's own
Pretendard font, loaded by explicit file path). Nothing here fetches anything but data.json.
"""
import argparse
import base64
import collections
import html
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import site_icons as si  # noqa: E402
from logo_ids import common_code, is_common_share  # noqa: E402

DATA_URL = "https://jacksungjinlee.github.io/baepsae/data.json"
FONT_DIR = ROOT / "fonts" / "pretendard"
GROUPS = ((1, 200, "Top 200"), (201, 753, "#201-753"), (754, 1306, "#754-1,306"), (1307, 1858, "#1,307-1,858"),
          (1859, 10 ** 9, "#1,859+"))
PER_PAGE = 120
DROPPED_MAX = 120
SEED = 20261105


def group_of(rank):
    if rank is None:
        return "not ranked today"
    for lo, hi, label in GROUPS:
        if lo <= rank <= hi:
            return label
    return "not ranked today"


def _cap(s):
    try:
        v = float(s.get("cap"))
    except (TypeError, ValueError):
        return None
    return v if v == v and v > 0 else None


def ranks(data):
    """Korean stocks (no ETFs) by code, and rank by market cap among common shares (the coverage test's population)."""
    stocks = {str(s.get("t") or "").upper(): s for s in data.get("stocks") or []
              if s.get("cls") == "kr" and not s.get("etf")}
    commons = sorted((s for c, s in stocks.items() if is_common_share(c) and _cap(s)),
                     key=lambda s: (-_cap(s), str(s["t"])))
    return stocks, {str(s["t"]).upper(): i for i, s in enumerate(commons, 1)}


def company_rows(dec, stocks, rank):
    """One row per domain (a company and its preferred shares): name, main code, rank, size group."""
    rows = []
    for dom, d in dec.items():
        codes = list(d["codes"])
        main = next((c for c in codes if c in rank), None) or next(
            (common_code(c) for c in codes if common_code(c) in rank), None) or codes[0]
        s = stocks.get(main) or next((stocks[c] for c in codes if c in stocks), {})
        r = rank.get(main)
        rows.append({**d, "main": main, "name": s.get("nk") or s.get("ne") or "(not in today's data)", "rank": r,
                     "group": group_of(r), "others": [c for c in codes if c != main]})
    rows.sort(key=lambda x: (x["rank"] is None, x["rank"] or 0, x["main"]))
    return rows


def data_uri(path):
    p = pathlib.Path(path)
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""


CSS = """
:root { --ink:#1d2433; --sub:#5b6474; --line:#d9dde4; --bg:#ffffff; --chk:#eef0f3; --bad:#9a3412; }
* { box-sizing: border-box; }
body { margin: 0; padding: 20px 20px 40px; background: var(--bg); color: var(--ink);
       font-family: 'Pretendard Variable', Pretendard, -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR',
       'Malgun Gothic', system-ui, sans-serif; font-size: 13px; line-height: 1.35; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 17px; margin: 28px 0 6px; }
p.note { color: var(--sub); margin: 2px 0 10px; max-width: 1100px; }
table { border-collapse: collapse; margin: 8px 0 4px; font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid var(--line); padding: 4px 10px; text-align: right; }
th:first-child, td:first-child { text-align: left; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, 108px); gap: 10px 8px; }
.t { width: 108px; }
.i { width: 108px; height: 84px; display: flex; align-items: center; justify-content: center; border-radius: 6px;
     background-color: #fff; background-image: linear-gradient(45deg, var(--chk) 25%, transparent 25%),
     linear-gradient(-45deg, var(--chk) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, var(--chk) 75%),
     linear-gradient(-45deg, transparent 75%, var(--chk) 75%);
     background-size: 12px 12px; background-position: 0 0, 0 6px, 6px -6px, -6px 0; border: 1px solid var(--line); }
.i img { width: 72px; height: 72px; object-fit: contain; image-rendering: auto; }
.i img.native { width: auto; height: auto; max-width: 96px; max-height: 76px; image-rendering: pixelated; }
.n { font-weight: 600; margin-top: 4px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2;
     -webkit-box-orient: vertical; word-break: keep-all; overflow-wrap: anywhere; }
.m, .d { color: var(--sub); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.r { color: var(--bad); font-size: 11px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3;
     -webkit-box-orient: vertical; overflow-wrap: anywhere; }
.page-h { color: var(--sub); margin: 0 0 10px; }
"""


def tile(row, img_src, native=False, reason=""):
    rank = f"#{row['rank']:,}" if row["rank"] else "unranked"
    extra = f" +{len(row['others'])}" if row["others"] else ""
    cls = ' class="native"' if native else ""
    img = f'<img{cls} src="{img_src}" alt="">' if img_src else ""
    r = f'<div class="r">{html.escape(reason)}</div>' if reason else ""
    return (f'<div class="t"><div class="i">{img}</div><div class="n">{html.escape(row["name"])}</div>'
            f'<div class="m">{row["main"]}{extra} · {rank}</div><div class="d">{html.escape(row["domain"])}</div>{r}</div>')


def counts_html(recs, dec, rows, n_items, rank):
    c = si.counts(recs, dec)
    out = ["<table><tr><th></th><th>companies</th><th>domains</th></tr>"]
    for k in si.COUNT_KEYS:
        out.append(f"<tr><td>{html.escape(k.strip())}</td><td>{c[('companies', k)]:,}</td>"
                   f"<td>{c[('domains', k)]:,}</td></tr>")
    out.append("</table>")
    pop = collections.Counter(group_of(r) for r in rank.values())
    tried = collections.Counter(r["group"] for r in rows)
    kept = collections.Counter(r["group"] for r in rows if r["decision"] == "kept")
    out.append("<table><tr><th>size group (market cap rank)</th><th>companies</th><th>with a DART homepage tried</th>"
               "<th>kept</th><th>kept / companies</th><th>kept / tried</th></tr>")
    for _, _, label in GROUPS + ((0, 0, "not ranked today"),):
        p, t, k = pop.get(label, 0), tried.get(label, 0), kept.get(label, 0)
        if not (p or t):
            continue
        out.append(f"<tr><td>{label}</td><td>{p:,}</td><td>{t:,}</td><td>{k:,}</td>"
                   f"<td>{(k / p if p else 0):.0%}</td><td>{(k / t if t else 0):.0%}</td></tr>")
    out.append("</table>")
    return "".join(out)


def dropped_sample(rows, n=DROPPED_MAX, seed=SEED):
    """Every generic rejection (rule a grouped first, then b, then c), then a seeded sample of too-small icons that
    have an image, up to n in all."""
    gen = [r for r in rows if r["decision"] == "generic" and r.get("raw")]
    gen.sort(key=lambda r: (r["reason"][:3], r.get("cluster") or 0, r["rank"] is None, r["rank"] or 0))
    small = [r for r in rows if r["decision"] == "too_small" and r.get("raw")]
    room = max(0, n - len(gen))
    pick = sorted(random.Random(seed).sample(small, min(room, len(small))),
                  key=lambda r: (r["rank"] is None, r["rank"] or 0))
    return gen[:n], pick, len(gen), len(small)


def build(out_dir, data, html_path):
    out_dir = pathlib.Path(out_dir)
    dec = json.loads((out_dir / "decisions.json").read_text(encoding="utf-8"))
    recs = si.read_state(out_dir / "collect.jsonl")
    recs = {d: r for d, r in recs.items() if d in dec}
    stocks, rank = ranks(data)
    rows = company_rows(dec, stocks, rank)
    kept = [r for r in rows if r["decision"] == "kept"]
    gen, small, n_gen, n_small = dropped_sample(rows)
    kept_tiles = [tile(r, data_uri(out_dir / "kr" / f"{r['main'] if (out_dir / 'kr' / (r['main'] + '.png')).exists() else r['codes'][0]}.png"))
                  for r in kept]
    raw = out_dir / "raw"
    drop_tiles = [tile(r, data_uri(raw / r["raw"]), native=True, reason=f"{r['source_type']}: {r['reason']}")
                  for r in gen + small]
    head = (f"<h1>Site icons from DART homepages — contact sheet</h1>"
            f"<p class='note'>Logo plan step 4. Collected {min(r['at'] for r in recs.values())[:16]} – "
            f"{max(r['at'] for r in recs.values())[:16]} KST from each company's own homepage (DART hm_url). "
            f"Names and ranks: data.json {data.get('pxDate')}. Nothing here is live: please look for wrong or "
            f"generic icons. The app will show one of these only when the logo service has none.</p>")
    counts = counts_html(recs, dec, rows, len(dec), rank)
    note_kept = (f"<h2>Kept: {len(kept):,} companies (largest first)</h2><p class='note'>128 px PNG as it would be "
                 f"stored, shown at 72 px on a checkerboard (white or transparent parts show). '+1' = a preferred "
                 f"share uses the same icon.</p>")
    note_drop = (f"<h2>Dropped: {n_gen:,} rejected as generic (all shown, grouped), {n_small:,} too small "
                 f"({len(small):,} shown at random)</h2><p class='note'>Shown at their own size (up to 96 px). (a) the "
                 f"same image as 3+ other companies · (b) a website-builder or hosting default, or a parked or "
                 f"placeholder page · (c) blank or one colour.</p>")
    doc = (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width, initial-scale=1'><meta name='robots' content='noindex'>"
           f"<title>Site icons contact sheet</title><style>{CSS}</style></head><body>{head}{counts}{note_kept}"
           f"<div class='grid'>{''.join(kept_tiles)}</div>{note_drop}<div class='grid'>{''.join(drop_tiles)}</div>"
           f"</body></html>")
    html_path = pathlib.Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(doc, encoding="utf-8")
    pages = []
    for i in range(0, max(len(kept_tiles), 1), PER_PAGE):
        part = kept_tiles[i:i + PER_PAGE]
        top = (head + counts) if i == 0 else ""
        pages.append(top + f"<p class='page-h'>Kept icons {i + 1:,}–{i + len(part):,} of {len(kept_tiles):,} "
                           f"(largest company first)</p><div class='grid'>{''.join(part)}</div>")
    for i in range(0, len(drop_tiles), PER_PAGE):
        part = drop_tiles[i:i + PER_PAGE]
        pages.append(note_drop + f"<div class='grid'>{''.join(part)}</div>")
    print(f"· {html_path} ({html_path.stat().st_size / 1e6:.1f} MB): kept {len(kept):,}, dropped shown "
          f"{len(drop_tiles):,} (generic {n_gen:,}, too small {n_small:,})")
    return pages, html_path


def font_css():
    """The repository's Pretendard (dynamic subsets) with every file loaded by its absolute path."""
    css = (FONT_DIR / "pretendard-variable.css").read_text(encoding="utf-8")
    base = (FONT_DIR / "woff2-dynamic-subset").resolve().as_uri() + "/"
    css = css.replace("url(./woff2-dynamic-subset/", "url(" + base)
    assert "url(./" not in css and base in css
    return css


def render_pages(pages, html_path, width=1300):
    from playwright.sync_api import sync_playwright
    folder = html_path.parent
    stem = html_path.stem
    for old in folder.glob(f"{stem}-p*.png"):
        old.unlink()
    fcss = font_css()
    written = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1)
        ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(("file:", "data:"))
                  else route.abort())
        page = ctx.new_page()
        for n, body in enumerate(pages, 1):
            tmp = folder / f".{stem}-render.html"
            tmp.write_text(f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><style>{fcss}{CSS}"
                           f"body{{font-family:'Pretendard Variable',sans-serif}}</style></head><body>{body}</body>"
                           f"</html>", encoding="utf-8")
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_function("Array.from(document.images).every(i => i.complete)")
            fam = page.evaluate("""() => { const el = document.querySelector('.n') || document.body;
                return document.fonts.check('600 13px "Pretendard Variable"', el.textContent || '가'); }""")
            broken = page.evaluate("Array.from(document.images).filter(i => !i.naturalWidth).length")
            f = folder / f"{stem}-p{n:02d}.png"
            page.screenshot(path=str(f), full_page=True)
            written.append(f)
            print(f"· {f.name}: Pretendard loaded {fam} · broken images {broken}")
            tmp.unlink()
        br.close()
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(si.default_out()), help="the folder site_icons.py wrote")
    ap.add_argument("--data", default=DATA_URL, help="data.json URL or path (names and market caps)")
    ap.add_argument("--html", default=None, help="contact sheet path (default: OUT/contact-sheet.html)")
    ap.add_argument("--no-png", action="store_true")
    a = ap.parse_args(argv)
    if a.data.startswith(("http://", "https://")):
        import requests
        r = requests.get(a.data, timeout=60)
        r.raise_for_status()
        data = r.json()
    else:
        data = json.loads(pathlib.Path(a.data).read_text(encoding="utf-8"))
    html_path = si.refuse_inside_repo(pathlib.Path(a.html) if a.html else pathlib.Path(a.out) / "contact-sheet.html")
    pages, html_path = build(a.out, data, html_path)
    if not a.no_png:
        render_pages(pages, html_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
