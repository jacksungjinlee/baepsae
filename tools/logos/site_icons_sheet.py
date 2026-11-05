#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contact sheet of the site icons (logo plan step 4): what Jack looks over before any of them goes live.

  python3 tools/logos/site_icons_sheet.py --html PATH/contact-sheet.html      # + PATH/contact-sheet-p01.png …

Reads what tools/logos/site_icons.py wrote (decisions.json, kr/, review/, raw/, collect.jsonl in $SITE_ICONS_DIR,
else $TMPDIR/site_icons) and the live data.json (company names and market caps; names are never written into this
repository). Writes one HTML file with every image inlined (it opens on its own, offline), in three sections:
  1. kept: every kept icon (128 px PNG on a checkerboard, so white and transparent parts show), largest company first,
     with its name, code, domain and rank;
  2. needs review: every icon that looks like a picture rather than a mark or is hard to see (many colours,
     gradients or photo noise, no transparency with content off every edge, far from square, text-heavy, a white
     mark invisible on a white page: shown on dark), with the reasons. Jack decides;
  3. rejected (a sample of up to 120): rule (a) groups one tile each with the other domains named, rules (b) and (c),
     then too-small icons (at least 40 places kept for them), each with the reason; the heading says how many of
     how many are shown.
with the counts on top (tried / reachable / robots / found / >= 96 px / generic / needs review / kept) and by size
group (rank by market cap among Korean common shares: top 200, #201-753, #754-1,306, #1,307-1,858, #1,859+), and the
same as PNG pages of about 120 icons (headless Chromium; Korean names drawn with the repository's own Pretendard
font, loaded by explicit file path; the run stops if the font or any picture did not load).
Nothing here fetches anything but data.json.
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
UNRANKED = "not ranked today"
PER_PAGE = 120
REJECTED_MAX = 120
SMALL_MIN = 40                     # places in the rejected sample kept for too-small icons
SEED = 20261105


def group_of(rank):
    if rank is None:
        return UNRANKED
    for lo, hi, label in GROUPS:
        if lo <= rank <= hi:
            return label
    return UNRANKED


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
:root { --ink:#1d2433; --sub:#5b6474; --line:#d9dde4; --bg:#ffffff; --chk:#eef0f3; --bad:#9a3412; --warn:#8a5a00; }
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
.i img { width: 72px; height: 72px; object-fit: contain; }
.i img.native { width: auto; height: auto; max-width: 96px; max-height: 76px; image-rendering: pixelated; }
.n { font-weight: 600; margin-top: 4px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2;
     -webkit-box-orient: vertical; word-break: keep-all; overflow-wrap: anywhere; }
.m, .d { color: var(--sub); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.r { color: var(--bad); font-size: 11px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 4;
     -webkit-box-orient: vertical; overflow-wrap: anywhere; }
.r.w { color: var(--warn); }
.i.dark { background: #2b303b; }
.page-h { color: var(--sub); margin: 0 0 10px; }
"""


def tile(row, img_src, native=False, reason="", warn=False):
    rank = f"#{row['rank']:,}" if row["rank"] else "unranked"
    extra = f" +{len(row['others'])}" if row["others"] else ""
    cls = ' class="native"' if native else ""
    img = f'<img{cls} src="{img_src}" alt="">' if img_src else ""
    r = f'<div class="r{" w" if warn else ""}">{html.escape(reason)}</div>' if reason else ""
    dark = " dark" if (row.get("metrics") or {}).get("invisible_on_white") else ""     # a white mark: show it on dark
    return (f'<div class="t"><div class="i{dark}">{img}</div><div class="n">{html.escape(row["name"])}</div>'
            f'<div class="m">{row["main"]}{extra} · {rank}</div><div class="d">{html.escape(row["domain"])}</div>{r}</div>')


def group_table(rows, rank):
    pop = collections.Counter(group_of(r) for r in rank.values())
    tried = collections.Counter(r["group"] for r in rows)
    kept = collections.Counter(r["group"] for r in rows if r["decision"] == "kept")
    rev = collections.Counter(r["group"] for r in rows if r["decision"] == "needs_review")
    out = []
    for _, _, label in GROUPS + ((0, 0, UNRANKED),):
        p, t, k, v = pop.get(label, 0), tried.get(label, 0), kept.get(label, 0), rev.get(label, 0)
        if p or t:
            out.append({"group": label, "companies": p, "tried": t, "kept": k, "review": v})
    return out


def counts_html(recs, dec, rows, rank):
    c = si.counts(recs, dec)
    out = ["<table><tr><th></th><th>companies</th><th>domains</th></tr>"]
    for k in si.COUNT_KEYS:
        out.append(f"<tr><td>{html.escape(k.strip())}</td><td>{c[('companies', k)]:,}</td>"
                   f"<td>{c[('domains', k)]:,}</td></tr>")
    out.append("</table>")
    out.append("<table><tr><th>size group (market cap rank)</th><th>companies</th><th>DART homepage tried</th>"
               "<th>kept</th><th>needs review</th><th>kept / companies</th><th>kept / tried</th></tr>")
    for g in group_table(rows, rank):
        p, t, k = g["companies"], g["tried"], g["kept"]
        out.append(f"<tr><td>{g['group']}</td><td>{p:,}</td><td>{t:,}</td><td>{k:,}</td><td>{g['review']:,}</td>"
                   f"<td>{(k / p if p else 0):.0%}</td><td>{(k / t if t else 0):.0%}</td></tr>")
    out.append("</table><p class='note'>Companies are counted by domain here (a preferred share is part of its "
               "issuer); the first table counts stock codes too.</p>")
    return "".join(out)


def rejected_sample(rows, n=REJECTED_MAX, small_min=SMALL_MIN, seed=SEED):
    """Rule (a) groups as one tile each, then rules (b) and (c), up to n - small_min; then a seeded sample of
    too-small icons to fill n. Returns (tiles' rows with a 'label', shown counts, totals)."""
    gen = [r for r in rows if r["decision"] == "generic" and r.get("raw")]
    clusters = collections.OrderedDict()
    singles = []
    for r in sorted(gen, key=lambda r: (r["reason"][:3], r.get("cluster") or 0, r["rank"] is None, r["rank"] or 0)):
        if r["reason"].startswith("(a)") and r.get("cluster"):
            clusters.setdefault(r["cluster"], []).append(r)
        else:
            singles.append(r)
    gen_tiles = []
    for members in clusters.values():
        first = members[0]
        doms = sorted({m["domain"] for m in members})
        gen_tiles.append(dict(first, label=f"(a) one image on {len(doms)} sites: " + ", ".join(doms)))
    gen_tiles += [dict(r, label=r["reason"]) for r in singles]
    small = [r for r in rows if r["decision"] == "too_small" and r.get("raw")]
    room_gen = max(0, n - min(small_min, len(small)))
    shown_gen = gen_tiles[:room_gen]
    pick = random.Random(seed).sample(small, min(n - len(shown_gen), len(small)))
    pick.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    shown_small = [dict(r, label=f"too small: {r['reason']}") for r in pick]
    return shown_gen + shown_small, (len(shown_gen), len(gen_tiles), len(gen)), (len(shown_small), len(small))


def build(out_dir, data, html_path):
    out_dir = pathlib.Path(out_dir)
    dec = json.loads((out_dir / "decisions.json").read_text(encoding="utf-8"))
    recs = si.read_state(out_dir / "collect.jsonl")
    recs = {d: r for d, r in recs.items() if d in dec}
    stocks, rank = ranks(data)
    rows = company_rows(dec, stocks, rank)
    raw = out_dir / "raw"

    def stored(folder, r):
        f = out_dir / folder / f"{r['main']}.png"
        return data_uri(f if f.exists() else out_dir / folder / f"{r['codes'][0]}.png")

    kept = [r for r in rows if r["decision"] == "kept"]
    review = [r for r in rows if r["decision"] == "needs_review"]
    kept_tiles = [tile(r, stored("kr", r)) for r in kept]
    review_tiles = [tile(r, stored("review", r), reason=f"{r['original_size']} {r['source_type']}: "
                         + r["reason"].replace("needs a look: ", ""), warn=True) for r in review]
    rej, (g_shown, g_tiles, g_all), (s_shown, s_all) = rejected_sample(rows)
    rej_tiles = [tile(r, data_uri(raw / r["raw"]), native=True, reason=f"{r['source_type']}: {r['label']}")
                 for r in rej]
    span = sorted(r["at"] for r in recs.values())
    head = (f"<h1>Site icons from DART homepages — contact sheet</h1>"
            f"<p class='note'>Logo plan step 4. Collected {span[0][:16]} – {span[-1][:16]} KST from each company's "
            f"own homepage (DART hm_url): apple-touch-icon, manifest icons, site icons only (never og:image or other "
            f"preview pictures). Names and ranks: data.json {data.get('pxDate')}. Nothing here is live. The app "
            f"would show one of these only when the logo service has none.</p>")
    counts = counts_html(recs, dec, rows, rank)
    h_kept = (f"<h2>1. Kept: {len(kept):,} companies (largest first)</h2><p class='note'>128 px PNG as it would be "
              f"stored, shown at 72 px on a checkerboard (white or transparent parts show). '+1' = a preferred share "
              f"uses the same icon. Please look for wrong or odd ones.</p>")
    h_review = (f"<h2>2. Needs review: {len(review):,} companies (largest first)</h2><p class='note'>At least 96 px "
                f"and not generic, but it looks like a picture rather than a mark, or would be hard to see (white "
                f"marks are shown on dark here). None of these is kept until you say so. Signs: many colours (entropy &ge; {si.PHOTO_ENTROPY} bits or &ge; {si.PHOTO_COLOURS:,} "
                f"colours) · smooth gradients or photo noise (soft share &ge; {si.PHOTO_SOFT} with entropy &ge; "
                f"{si.PHOTO_SOFT_ENTROPY}) · no transparency and the picture runs off every edge · far from square "
                f"(&ge; {si.PHOTO_ASPECT}:1) · a text-heavy block · a light mark invisible on a white page.</p>")
    h_rej = (f"<h2>3. Rejected (sample): {g_shown:,} of {g_tiles:,} generic tiles ({g_all:,} companies; one tile per "
             f"group of the same image), {s_shown:,} of {s_all:,} too small (chosen at random)</h2><p class='note'>"
             f"Shown at their own size (up to 96 px). (a) the same image as 3+ other companies · (b) a "
             f"website-builder or hosting default, a known stock icon, or a parked or placeholder page · (c) blank "
             f"or one colour · too small: under 96 px, or a small icon the site enlarged.</p>")
    sections = [(h_kept, kept_tiles), (h_review, review_tiles), (h_rej, rej_tiles)]
    doc = (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width, initial-scale=1'><meta name='robots' content='noindex'>"
           f"<title>Site icons contact sheet</title><style>{CSS}</style></head><body>{head}{counts}"
           + "".join(f"{h}<div class='grid'>{''.join(t)}</div>" for h, t in sections) + "</body></html>")
    html_path = pathlib.Path(html_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(doc, encoding="utf-8")
    pages = [head + counts]
    for h, tiles in sections:
        for i in range(0, max(len(tiles), 1), PER_PAGE):
            part = tiles[i:i + PER_PAGE]
            page = (h + f"<p class='page-h'>{i + 1:,}–{i + len(part):,} of {len(tiles):,}</p>") if tiles else h
            pages.append(page + f"<div class='grid'>{''.join(part)}</div>")
    pages[1] = pages[0] + pages[1]                          # the counts and the first kept icons on page 1
    pages = pages[1:]
    groups = group_table(rows, rank)
    print(f"· {html_path} ({html_path.stat().st_size / 1e6:.1f} MB): kept {len(kept):,} · needs review "
          f"{len(review):,} · rejected shown {len(rej_tiles):,} (generic {g_shown}/{g_tiles} tiles, too small "
          f"{s_shown}/{s_all})")
    for g in groups:
        print(f"    {g['group']:<18} companies {g['companies']:>5,}  tried {g['tried']:>5,}  kept {g['kept']:>4,}  "
              f"needs review {g['review']:>3,}")
    return pages, html_path


def font_css():
    """The repository's Pretendard (dynamic subsets) with every file loaded by its absolute path."""
    css = (FONT_DIR / "pretendard-variable.css").read_text(encoding="utf-8")
    base = (FONT_DIR / "woff2-dynamic-subset").resolve().as_uri() + "/"
    css = css.replace("url(./woff2-dynamic-subset/", "url(" + base)
    assert "url(./" not in css and base in css
    return css


def render_pages(pages, html_path, width=1300):
    """PNG pages. Stops (SystemExit) when Pretendard did not load for the Korean names or a picture is broken."""
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
            page.evaluate("document.fonts.ready.then(() => true)")
            page.wait_for_function("Array.from(document.images).every(i => i.complete)")
            loaded = page.evaluate("""() => Array.from(document.fonts).filter(f =>
                f.family.replace(/["']/g, '') === 'Pretendard Variable' && f.status === 'loaded').length""")
            hangul = page.evaluate("""() => { const t = Array.from(document.querySelectorAll('.n'))
                .map(e => e.textContent).join(''); return /[\\uac00-\\ud7a3]/.test(t); }""")
            broken = page.evaluate("Array.from(document.images).filter(i => !i.naturalWidth).length")
            tmp.unlink()
            if broken or (hangul and not loaded):
                raise SystemExit(f"!! page {n}: Pretendard faces loaded {loaded} (Korean names: {hangul}), "
                                 f"broken pictures {broken}")
            f = folder / f"{stem}-p{n:02d}.png"
            page.screenshot(path=str(f), full_page=True)
            written.append(f)
            print(f"· {f.name}: Pretendard faces loaded {loaded} · broken pictures 0")
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
