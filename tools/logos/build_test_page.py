#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build logo-test.html: the temporary logo coverage test page (logo plan step 3). Jack opens it in his own browser.

  python3 tools/logos/build_test_page.py --keys-file PATH          # live data.json -> logo-test.html (repo root)

The page is not linked from anywhere, carries noindex, and is English only (it is for Jack, not for users). It lists
a fixed sample (seed below) and, after Jack taps Start, loads each company's logo from Brandfetch and logo.dev by exact
identifiers only, paced in his browser. Nothing here requests a logo: both providers' terms forbid fetching their
images with a script, so this builder only writes the page.

Sample (logo_ids.draw_sample, all from today's data.json, ETFs, funds and preferred shares left out):
  KR-A the 200 largest Korean companies · KR-B…E 300 more at random, 75 from each quarter of the rest by market cap ·
  US-A…D 100 US companies at random, 25 from each quarter by market cap.
Identifiers (exact only, never names):
  ticker  KOSPI and KONEX 005930.KS · KOSDAQ 247540.KQ (market from the KRX listing for data.json's pxDate, else
          DART corp_cls) · US as in data.json. A bare 6-digit code is never used: Chinese exchanges use 6-digit
          codes too, so it is not exact.
  ISIN    KRX listing ISU_CD (check digit verified), else the exact common-share rule (kr_isin_from_code), else none.
  domain  tools/logos/kr_homepages.csv (DART hm_url) where domain_ok = 1. Korea only.
Keys: BRANDFETCH_CLIENT_ID and LOGODEV_TOKEN (publishable, meant to sit in page source) from --keys-file or the
environment. A secret key (sk_…) is refused. Keys are never printed.
"""
import argparse
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from logo_ids import Masker, draw_sample, isin_valid, now_kst  # noqa: E402
from logo_sources import (BAD, DATA_URL, GOOD, HOMEPAGES, LISTING_URL, build_companies,  # noqa: E402,F401
                          load_homepages, load_listing, load_text, read_keys, render)

TEMPLATE = HERE / "logo_test_template.html"
OUT = ROOT / "logo-test.html"
SEED = 20261105
MUST_KR_TOP = ("005930", "000660", "005380")


def page_data(picked, groups, left_out, meta):
    """The JSON the page embeds (short keys keep the page small)."""
    comp = [{"c": p["code"], "n": p["name"], "s": p["side"], "m": p["market"], "g": p["group"], "r": p["rank"],
             "tk": p["ticker"], "isin": p["isin"], "isrc": p["isin_src"], "dom": p["domain"], "hm": p["hm_url"],
             "dn": p["domain_note"]} for p in picked]
    return {"meta": meta, "groups": groups, "companies": comp, "leftOut": [c["code"] for c in left_out]}


def build(data, listing, homepages, keys, seed=SEED, built_at=None, template=None):
    companies, log = build_companies(data, listing, homepages)
    picked, groups, left_out = draw_sample(companies, seed)
    top = {p["code"] for p in picked if p["group"] == "KR-A"}
    lost = [c for c in MUST_KR_TOP if c not in top]
    if lost:
        raise SystemExit(f"!! must-have companies missing from the 200 largest Korean companies: {lost}")
    us_left = [c["code"] for c in companies if c["side"] == "us" and c["code"] not in {p["code"] for p in picked}]
    us_rank = sorted((c for c in companies if c["side"] == "us" and c["code"] in us_left and c.get("cap")),
                     key=lambda c: -float(c["cap"]))
    rotate = [c["ticker"] for c in us_rank[:40]]               # known logos for the checks during the run
    for g in groups:
        g["census"] = bool(g["census"])
    meta = {"seed": seed, "pxDate": data.get("pxDate"), "usPxDate": data.get("usPxDate"), "asOf": data.get("asOf"),
            "builtAt": built_at or now_kst().strftime("%Y-%m-%d %H:%M KST"),
            "population": {side: sum(g["population"] for g in groups if g["side"] == side) for side in ("kr", "us")},
            "good": GOOD, "bad": BAD, "rotate": rotate,
            "homepagesFetched": sum(1 for r in homepages.values() if r.get("status") in ("ok", "empty", "nodata"))}
    assert isin_valid(GOOD["isin"]) and isin_valid(BAD["isin"])
    pdata = page_data(picked, groups, left_out, meta)
    tpl = template if template is not None else TEMPLATE.read_text(encoding="utf-8")
    return render(tpl, pdata, keys), pdata, log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=DATA_URL, help="data.json URL or path (default: the live site)")
    ap.add_argument("--listing", default="auto", help="KRX listing CSV path, or auto (the file for data.json pxDate)")
    ap.add_argument("--homepages", default=str(HOMEPAGES))
    ap.add_argument("--keys-file", default=os.environ.get("LOGO_KEYS_FILE"),
                    help="file with BRANDFETCH_CLIENT_ID=… and LOGODEV_TOKEN=pk_… lines (else the environment)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    keys = read_keys(a.keys_file)
    mask = Masker(*keys)
    data = json.loads(load_text(a.data, "data.json"))
    listing = load_listing(a.listing, data.get("pxDate"))
    homepages = load_homepages(a.homepages)
    page, pdata, log = build(data, listing, homepages, keys, a.seed)
    for line in log:
        print(mask(line))
    comp = pdata["companies"]
    by = {}
    for c in comp:
        by.setdefault(c["g"], []).append(c)
    print("· sample: " + " · ".join(f"{g['id']} {g['sampled']}/{g['population']:,}" for g in pdata["groups"]))
    kr = [c for c in comp if c["s"] == "kr"]
    print(f"· Korean sample {len(kr)}: ISIN {sum(1 for c in kr if c['isin']):,} · usable domain "
          f"{sum(1 for c in kr if c['dom']):,} · ticker {sum(1 for c in kr if c['tk']):,} · "
          f"US sample {len(comp) - len(kr)}")
    pathlib.Path(a.out).write_text(page, encoding="utf-8")
    print(f"wrote {a.out} ({len(page):,} bytes; keys in page source: publishable only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
