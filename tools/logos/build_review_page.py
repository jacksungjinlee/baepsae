#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build logo-review.html: Jack's logo picker (temporary review tool). Jack opens it in his own browser.

  python3 tools/logos/build_review_page.py --keys-file PATH        # live data.json -> logo-review.html (repo root)

Jack's design (2026-11-05): a human confirms every logo, by exception. The page pre-picks the most likely logo per
company, shows about 100 companies per grid, and Jack taps only the wrong ones, then chooses among the alternatives or
the letter mark. Unreviewed companies keep the letter mark. Only his choices are stored (source + address, exported as
JSON); logos stay hotlinked.

Who is on it: every Korean company (common shares; ETFs, funds and preferred shares left out — a preferred share uses
its common share's logo) and every US company (no ETFs) in today's data.json, sorted by market cap within each market
(a company without a market cap goes last and is said loudly). Grids of GRID companies: Korea 1-100, US 1-100, ...

Pre-pick order (the page's JavaScript; pre_pick() below is the same rule in Python, for the tests):
  1. a logo both services agree on (Brandfetch and logo.dev images that look the same, compared in Jack's browser
     only, and only where the provider lets the page read its images);
  2. Brandfetch by exact ID: ISIN, then ticker;
  3. logo.dev: ticker, then the DART-homepage domain;
  4. Brandfetch by the DART-homepage domain (added 2026-11-05: it was right for 금호석유화학);
  5. our own website icon, when logo-review/icons.json lists it as kept (tools/logos/add_site_icons.py; an icon
     flagged as photo-like or hard to see is never pre-picked, only offered in the Fix panel as "Own icon (check)");
  else the letter mark.
When every alternative is wrong, the Fix panel also takes a pasted image address (source "manual": https only, checked
and previewed in Jack's browser, at least 64 px; later downloaded once and stored as our own site file, not done here) or
"None of these - find more" (source "need": letter mark for now, listed in the page's Needs a logo view).
The page remembers in Jack's browser, for 7 days, which sources found a logo per company (hit / miss and the day, never an
image), so a reload asks again only for the found logos, after the usual checks; once Start was tapped in that browser,
a reload starts loading by itself on the first grid not reviewed yet.

Identifiers are exact only (ticker, ISIN, DART homepage), never names — the same ones as the coverage test page
(logo_sources.build_companies). Nothing here requests a logo: both providers' terms forbid fetching their images
with a script, so this builder only writes the page.

Keys: BRANDFETCH_CLIENT_ID and LOGODEV_TOKEN (publishable, meant to sit in page source) from --keys-file or the
environment. A secret key (sk_...) is refused. Keys are never printed.
"""
import argparse
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import logo_sources as lsrc  # noqa: E402
from logo_ids import Masker, common_code, is_krx_code, now_kst  # noqa: E402

TEMPLATE = HERE / "logo_review_template.html"
OUT = ROOT / "logo-review.html"
ICONS_DIR = "logo-review/icons"                    # site path of our own website icons (page-relative)
ICONS_MANIFEST = ROOT / "logo-review" / "icons.json"
GRID = 100
SIZE_GROUPS = ((1, 200), (201, 1000), (1001, None))       # ranks within a market, for the summary bar
MUST = {"kr": ("005930", "000660", "005380"), "us": ("AAPL", "MSFT")}
ROTATE = 60                                        # the largest US companies: known logos for the checks
SIDE_NAME = {"kr": "Korea", "us": "US"}

# The pre-pick order (rules 2-5) and the export's source names. Same as ROUTES in the page.
ORDER = ("bfI", "bfT", "ldT", "ldD", "bfD", "own")
SOURCE = {"bfI": "bf-isin", "bfT": "bf-ticker", "ldT": "ld-ticker", "ldD": "ld-domain", "bfD": "bf-domain",
          "own": "own-icon"}
SOURCES = tuple(SOURCE[r] for r in ORDER) + ("letter",)
# Added 2026-11-05, chosen in the Fix panel only (exports stay version 1: the format is the same, these are additions):
# "manual" = an image address Jack pasted (https, checked in the page; later downloaded once and stored as our own file),
# "need" = none of these, find more (url null; letter mark for now, listed in the Needs a logo view).
EXTRA_SOURCES = ("manual", "need")
STORE_KEY = "baepsae-logo-review-v1"               # Jack's choices (the page's localStorage)
PROBE_KEY = "baepsae-logo-review-probes-v1"        # hit / miss per company and source, with the day; never an image
PROBE_DAYS = 7
PROVIDER = {"bfI": "bf", "bfT": "bf", "bfD": "bf", "ldT": "ld", "ldD": "ld", "own": "own"}
ENDED = ("na", "hit", "miss", "off", "err", "stopped")
AGREE_MAX = 0.15       # fingerprints (16 x 16 ink cells, one hex digit each) that differ by at most this agree
ASPECT_MAX = 1.35      # content boxes whose width/height differ more than this never agree


# ── the pre-pick rule (mirror of the page's prePick; tests/test_logo_review.py checks they agree) ──

def distance(a, b):
    """Mean difference of two fingerprints' cells (hex digits 0-f), 0 = the same, 1 = opposite."""
    return sum(abs(int(x, 16) - int(y, 16)) for x, y in zip(a, b)) / (15 * len(a))


def agrees(x, y):
    """Two fingerprints {g, ar} (16 x 16 ink cells as hex, content aspect ratio) of the same picture."""
    if not x or not y or not x.get("g") or not y.get("g") or len(x["g"]) != len(y["g"]):
        return False
    if max(x["ar"] / y["ar"], y["ar"] / x["ar"]) > ASPECT_MAX:
        return False
    return distance(x["g"], y["g"]) <= AGREE_MAX


def pre_pick(cands):
    """cands: {route: {"s": state, "hash": {g, ar} | None, "check": our icon needs a look}}; a missing route is 'na'.
    Returns {pick: route | None (letter mark), via: agree | order | none, partner, settled}.
    settled = every route has ended (a route still loading could still win, by order or by agreeing)."""
    def get(r):
        return cands.get(r) or {"s": "na"}
    settled = all(get(r)["s"] in ENDED for r in ORDER)
    hits = [r for r in ORDER if get(r)["s"] == "hit" and not get(r).get("check")]   # an icon to check: Fix panel only
    for r in hits:
        if PROVIDER[r] == "own":
            continue
        for o in hits:
            if PROVIDER[o] not in ("own", PROVIDER[r]) and agrees(get(r).get("hash"), get(o).get("hash")):
                return {"pick": r, "via": "agree", "partner": o, "settled": settled}
    if hits:
        return {"pick": hits[0], "via": "order", "partner": None, "settled": settled}
    return {"pick": None, "via": "none", "partner": None, "settled": settled}


# ── who is on the page ──

def _cap(c):
    v = c.get("cap")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) and v > 0 else None


def rank_companies(companies):
    """Every company, per market: market cap largest first (ties by code); a company without a usable market cap goes
    last (by code), flagged nocap, and is logged. Adds rank (1 = largest), grid id and size group."""
    out, log = [], []
    for side in ("kr", "us"):
        rows = [c for c in companies if c["side"] == side]
        with_cap = sorted((c for c in rows if _cap(c) is not None), key=lambda c: (-_cap(c), str(c["code"])))
        no_cap = sorted((c for c in rows if _cap(c) is None), key=lambda c: str(c["code"]))
        if no_cap:
            log.append(f"!! {SIDE_NAME[side]}: {len(no_cap)} companies without a market cap, listed last: "
                       + ", ".join(c["code"] for c in no_cap[:12]) + (" ..." if len(no_cap) > 12 else ""))
        for i, c in enumerate(with_cap + no_cap, 1):
            out.append(dict(c, rank=i, nocap=_cap(c) is None, grid=f"{side.upper()}-{(i - 1) // GRID + 1}",
                            zone=next(k for k, (lo, hi) in enumerate(SIZE_GROUPS) if i >= lo and (hi is None or i <= hi))))
    return out, log


def make_grids(rows):
    grids = []
    for side in ("kr", "us"):
        n = sum(1 for r in rows if r["side"] == side)
        for k in range((n + GRID - 1) // GRID):
            lo, hi = k * GRID + 1, min(n, (k + 1) * GRID)
            grids.append({"id": f"{side.upper()}-{k + 1}", "side": side, "from": lo, "to": hi,
                          "label": f"{SIDE_NAME[side]} {lo:,}–{hi:,}"})
    return grids


def make_zones(rows):
    zones = []
    for side in ("kr", "us"):
        n = sum(1 for r in rows if r["side"] == side)
        for k, (lo, hi) in enumerate(SIZE_GROUPS):
            if lo > n:
                continue
            top = n if hi is None or hi > n else hi
            zones.append({"side": side, "z": k, "from": lo, "to": top, "label": f"{SIDE_NAME[side]} {lo:,}–{top:,}"})
    return zones


# ── our own website icons (optional) ──

_ICON_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.png$")


def icon_path(raw):
    """'icons/005930.png' or 'logo-review/icons/005930.png' -> 'logo-review/icons/005930.png'. Anything else
    (another folder, '..', an absolute path or a web address, not .png) -> ''."""
    s = str(raw or "").strip()
    for prefix in (ICONS_DIR + "/", "icons/"):
        if s.startswith(prefix):
            name = s[len(prefix):]
            return f"{ICONS_DIR}/{name}" if _ICON_FILE.match(name) and ".." not in name else ""
    return ""


def load_icons(manifest, codes, root=ROOT):
    """{code: (page-relative PNG path, check)} from logo-review/icons.json, which tools/logos/add_site_icons.py writes:
    {code: "icons/<file>.png"} for a kept icon, {code: {"path": ..., "check": true}} for one that needs a look (never
    pre-picked; offered in the Fix panel only). A missing manifest is fine (no icons yet). A preferred share's entry
    (it points to its issuer's file) is accepted but not shown: preferred shares are not on the page. Entries for
    other codes, bad paths and missing files are left out, loudly."""
    manifest = pathlib.Path(manifest)
    if not manifest.exists():
        return {}, [f"· no {manifest.name}: our website icons are not candidates yet"]
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"!! {manifest}: expected an object {{code: path}}")
    icons, log = {}, []
    bad = {"unknown code": 0, "bad entry": 0, "bad path": 0, "missing file": 0}
    preferred = 0
    for code, entry in sorted(raw.items()):
        if isinstance(entry, str):
            path, check = entry, False
        elif isinstance(entry, dict) and isinstance(entry.get("path"), str) and entry.get("check", False) in (True, False):
            path, check = entry["path"], bool(entry.get("check"))
        else:
            bad["bad entry"] += 1
            log.append(f"  !! icon for {code}: {str(entry)[:80]!r} is neither a path nor {{path, check}} — left out")
            continue
        p = icon_path(path)
        if code not in codes:
            if is_krx_code(code) and common_code(code) != code and common_code(code) in codes:
                preferred += 1                                 # same issuer as a company on the page: not shown
            else:
                bad["unknown code"] += 1
                log.append(f"  !! icon for {code}: not a company on this page — left out")
        elif not p:
            bad["bad path"] += 1
            log.append(f"  !! icon for {code}: {str(path)[:80]!r} is not a .png under {ICONS_DIR}/ — left out")
        elif not (pathlib.Path(root) / p).is_file():
            bad["missing file"] += 1
            log.append(f"  !! icon for {code}: {p} does not exist — left out")
        else:
            icons[code] = (p, check)
    nchk = sum(1 for _, c in icons.values() if c)
    log.insert(0, f"· our website icons: {len(icons):,} of {len(raw):,} in {manifest.name} on the page "
               f"({len(icons) - nchk:,} kept, {nchk:,} to check) · preferred shares (same file as their issuer, not "
               f"shown) {preferred:,}" + "".join(f" · {k} {v}" for k, v in bad.items() if v))
    return icons, log


# ── the page ──

def page_data(rows, grids, zones, icons, meta):
    """The JSON the page embeds (short keys keep the page small)."""
    comp = [{"c": r["code"], "n": r["name"], "s": r["side"], "m": r["market"], "r": r["rank"], "g": r["grid"],
             "z": r["zone"], "tk": r["ticker"], "isin": r["isin"], "dom": r["domain"],
             "ic": icons[r["code"]][0] if r["code"] in icons else "",
             **({"icx": 1} if r["code"] in icons and icons[r["code"]][1] else {}),
             **({"nc": 1} if r["nocap"] else {})} for r in rows]
    return {"meta": meta, "grids": grids, "zones": zones, "companies": comp}


def build(data, listing, homepages, keys, icons_manifest=None, built_at=None, template=None, root=ROOT):
    companies, log = lsrc.build_companies(data, listing, homepages)
    rows, rlog = rank_companies(companies)
    log += rlog
    for side, must in MUST.items():
        lost = [c for c in must if c not in {r["code"] for r in rows if r["side"] == side}]
        if lost:
            raise SystemExit(f"!! must-have companies missing from {SIDE_NAME[side]}: {lost}")
    icons, ilog = load_icons(icons_manifest or ICONS_MANIFEST, {r["code"] for r in rows}, root)
    log += ilog
    grids, zones = make_grids(rows), make_zones(rows)
    rotate = [r["ticker"] for r in rows if r["side"] == "us" and not r["nocap"]][:ROTATE]
    # a kept icon of ours the page loads first: if it fails, the icon files are missing and our icons stop (a gap)
    own_check = next((icons[r["code"]][0] for r in rows if r["code"] in icons and not icons[r["code"]][1]), "")
    meta = {"pxDate": data.get("pxDate"), "usPxDate": data.get("usPxDate"), "asOf": data.get("asOf"),
            "builtAt": built_at or now_kst().strftime("%Y-%m-%d %H:%M KST"), "grid": GRID,
            "good": lsrc.GOOD, "bad": lsrc.BAD, "rotate": rotate, "ownCheck": own_check,
            "counts": {side: sum(1 for r in rows if r["side"] == side) for side in ("kr", "us")},
            "icons": len(icons), "iconsCheck": sum(1 for _, c in icons.values() if c)}
    pdata = page_data(rows, grids, zones, icons, meta)
    tpl = template if template is not None else TEMPLATE.read_text(encoding="utf-8")
    return lsrc.render(tpl, pdata, keys), pdata, log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=lsrc.DATA_URL, help="data.json URL or path (default: the live site)")
    ap.add_argument("--listing", default="auto", help="KRX listing CSV path, or auto (the file for data.json pxDate)")
    ap.add_argument("--homepages", default=str(lsrc.HOMEPAGES))
    ap.add_argument("--icons", default=str(ICONS_MANIFEST), help="optional manifest of our own website icons")
    ap.add_argument("--keys-file", default=os.environ.get("LOGO_KEYS_FILE"),
                    help="file with BRANDFETCH_CLIENT_ID=... and LOGODEV_TOKEN=pk_... lines (else the environment)")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    keys = lsrc.read_keys(a.keys_file)
    mask = Masker(*keys)
    data = json.loads(lsrc.load_text(a.data, "data.json"))
    listing = lsrc.load_listing(a.listing, data.get("pxDate"))
    homepages = lsrc.load_homepages(a.homepages)
    page, pdata, log = build(data, listing, homepages, keys, a.icons)
    for line in log:
        print(mask(line))
    comp = pdata["companies"]
    for side in ("kr", "us"):
        cs = [c for c in comp if c["s"] == side]
        print(f"· {SIDE_NAME[side]}: {len(cs):,} companies in {sum(1 for g in pdata['grids'] if g['side'] == side)} grids"
              f" · ISIN {sum(1 for c in cs if c['isin']):,} · ticker {sum(1 for c in cs if c['tk']):,}"
              f" · domain {sum(1 for c in cs if c['dom']):,} · own icon {sum(1 for c in cs if c['ic']):,}")
    pathlib.Path(a.out).write_text(page, encoding="utf-8")
    print(f"wrote {a.out} ({len(page):,} bytes; keys in page source: publishable only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
