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
import csv
import datetime as dt
import io
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from logo_ids import (Masker, check_publishable_keys, draw_sample, is_common_share, is_krx_code,  # noqa: E402
                      isin_check_digit, isin_valid, kr_isin_from_code, logodev_ticker, now_kst)

DATA_URL = "https://jacksungjinlee.github.io/baepsae/data.json"
LISTING_URL = ("https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/"
               "{d}.csv")
TEMPLATE = HERE / "logo_test_template.html"
HOMEPAGES = HERE / "kr_homepages.csv"
OUT = ROOT / "logo-test.html"
SEED = 20261105
MARKET_MAP = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ", "KOSDAQ GLOBAL": "KOSDAQ", "KONEX": "KONEX"}
DART_CLS = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX"}
MUST_KR_TOP = ("005930", "000660", "005380")
# Checks the page runs before and during the test: a logo every provider has, and identifiers nobody has.
GOOD = {"ticker": "AAPL", "isin": "US0378331005", "domain": "apple.com"}
BAD = {"ticker": "ZZQXJ9", "isin": "KR799999900" + isin_check_digit("KR799999900"),
       "domain": "no-such-brand-baepsae-test.com"}


def read_keys(keys_file=None):
    vals = {"BRANDFETCH_CLIENT_ID": os.environ.get("BRANDFETCH_CLIENT_ID", ""),
            "LOGODEV_TOKEN": os.environ.get("LOGODEV_TOKEN", "")}
    if keys_file:
        for line in pathlib.Path(keys_file).read_text(encoding="utf-8").splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and k.strip() in vals:
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return check_publishable_keys(vals["BRANDFETCH_CLIENT_ID"], vals["LOGODEV_TOKEN"])


def load_text(src, what):
    if str(src).startswith(("http://", "https://")):
        import requests
        r = requests.get(src, timeout=60)
        r.raise_for_status()
        print(f"· {what}: {src} ({len(r.content):,} bytes)")
        return r.content.decode("utf-8-sig")
    t = pathlib.Path(src).read_text(encoding="utf-8-sig")
    print(f"· {what}: {src} ({len(t):,} characters)")
    return t


def load_listing(spec, px):
    """{code: row} of the KRX listing. spec = a CSV path or URL, or 'auto': the file for data.json's pxDate, else the
    newest of the 7 days before it (said loudly). Also used by build_review_page.py."""
    if not px:
        raise SystemExit("!! data.json has no pxDate")
    if spec == "auto":
        d0 = dt.date.fromisoformat(px)
        text = None
        for back in range(8):
            d = (d0 - dt.timedelta(days=back)).isoformat()
            try:
                text = load_text(LISTING_URL.format(d=d), "KRX listing")
            except Exception as e:                           # noqa: BLE001 — try the day before, loudly
                print(f"  !! KRX listing {d}: {type(e).__name__}")
                continue
            if back:
                print(f"!! no KRX listing for {px}; using {d} ({back} days older)")
            break
        if text is None:
            raise SystemExit("!! no KRX listing for the last 8 days")
    else:
        text = load_text(spec, "KRX listing")
    return {r["Code"]: r for r in csv.DictReader(io.StringIO(text))}


def load_homepages(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def build_companies(data, listing, homepages):
    """data.json + {code: KRX listing row} + {code: kr_homepages.csv row} -> (companies, log lines). Pure.
    Every Korean common share (no ETF) and every US stock (no ETF) in data.json, with its exact identifiers."""
    log = []
    out = []
    skipped = {"preferred": 0, "etf": 0}
    for s in data.get("stocks") or []:
        cls = s.get("cls")
        if cls not in ("kr", "us"):
            continue
        code = str(s.get("t") or "").strip()
        if s.get("etf"):
            skipped["etf"] += 1
            continue
        name = s.get("nk") or s.get("ne") or code
        if cls == "us":
            out.append({"code": code, "name": name, "side": "us", "market": "US", "cap": s.get("cap"),
                        "ticker": logodev_ticker(code, "US"), "isin": "", "isin_src": "", "domain": "",
                        "hm_url": "", "domain_note": ""})
            continue
        if not is_krx_code(code):
            log.append(f"!! {code}: not a KRX code — left out")
            continue
        if not is_common_share(code):
            skipped["preferred"] += 1                        # same company as its common share
            continue
        L = listing.get(code) or {}
        H = homepages.get(code) or {}
        market = MARKET_MAP.get(L.get("Market", ""), "") or DART_CLS.get(H.get("corp_cls", ""), "")
        if not market:
            log.append(f"· {code}: market unknown (not in the KRX listing, no DART corp_cls) — no ticker route")
        isin, src = "", ""
        if L.get("ISU_CD"):
            cand = L["ISU_CD"].strip().upper()
            if not isin_valid(cand):
                log.append(f"!! {code}: listing ISIN {cand!r} fails the check digit — not used")
            elif cand.startswith("KR7") and cand[3:9] != code.upper():     # a Korean ISIN carries its short code
                log.append(f"!! {code}: listing ISIN {cand!r} is for another code — not used")
            else:
                isin, src = cand, "KRX listing"
        if not isin and kr_isin_from_code(code):
            isin, src = kr_isin_from_code(code), "common-share rule"
        dom = H.get("domain", "") if H.get("domain_ok") == "1" else ""
        note = "" if dom else (H.get("domain_note") or ("not fetched from DART" if not H else ""))
        out.append({"code": code, "name": name, "side": "kr", "market": market, "cap": s.get("cap"),
                    "ticker": logodev_ticker(code, market), "isin": isin, "isin_src": src, "domain": dom,
                    "hm_url": H.get("hm_url", ""), "domain_note": note})
    log.append(f"· left out: ETFs {skipped['etf']:,} · Korean preferred shares {skipped['preferred']:,} "
               "(a preferred share uses its common share's logo)")
    return out, log


def page_data(picked, groups, left_out, meta):
    """The JSON the page embeds (short keys keep the page small)."""
    comp = [{"c": p["code"], "n": p["name"], "s": p["side"], "m": p["market"], "g": p["group"], "r": p["rank"],
             "tk": p["ticker"], "isin": p["isin"], "isrc": p["isin_src"], "dom": p["domain"], "hm": p["hm_url"],
             "dn": p["domain_note"]} for p in picked]
    return {"meta": meta, "groups": groups, "companies": comp, "leftOut": [c["code"] for c in left_out]}


def render(template, data, keys):
    bf, ld = keys
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    keys_js = json.dumps({"bf": bf, "ld": ld})
    assert template.count("/*DATA*/") == 1 and template.count("/*KEYS*/") == 1, "template placeholders"
    return template.replace("/*DATA*/", blob).replace("/*KEYS*/", keys_js)


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
