# -*- coding: utf-8 -*-
"""What Jack's logo picker (build_review_page.py) builds on: reading the two publishable keys, the live data.json,
the KRX listing and the DART homepages, every company with its exact identifiers, the known-logo / made-up-identifier
checks, and writing a page from its template. Moved here from the coverage test page's builder, which was removed on
2026-11-05 with that page.

Identifiers (exact only, never names):
  ticker  KOSPI and KONEX 005930.KS · KOSDAQ 247540.KQ (market from the KRX listing for data.json's pxDate, else
          DART corp_cls) · US as in data.json. A bare 6-digit code is never used: Chinese exchanges use 6-digit
          codes too, so it is not exact.
  ISIN    KRX listing ISU_CD (check digit verified), else the exact common-share rule (kr_isin_from_code), else none.
  domain  tools/logos/kr_homepages.csv (DART hm_url) where domain_ok = 1. Korea only.
Keys: BRANDFETCH_CLIENT_ID and LOGODEV_TOKEN (publishable, meant to sit in page source) from a keys file or the
environment. A secret key (sk_...) is refused. Keys are never printed. Nothing here requests a logo.
Unit tests: tests/test_logos.py (build_companies, read_keys), tests/test_logo_review.py.
"""
import csv
import datetime as dt
import io
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from logo_ids import (check_publishable_keys, is_common_share, is_krx_code, isin_check_digit,  # noqa: E402
                      isin_valid, kr_isin_from_code, logodev_ticker)

DATA_URL = "https://jacksungjinlee.github.io/baepsae/data.json"
LISTING_URL = ("https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/"
               "{d}.csv")
HOMEPAGES = HERE / "kr_homepages.csv"
MARKET_MAP = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ", "KOSDAQ GLOBAL": "KOSDAQ", "KONEX": "KONEX"}
DART_CLS = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX"}
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


def render(template, data, keys):
    bf, ld = keys
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    keys_js = json.dumps({"bf": bf, "ld": ld})
    assert template.count("/*DATA*/") == 1 and template.count("/*KEYS*/") == 1, "template placeholders"
    return template.replace("/*DATA*/", blob).replace("/*KEYS*/", keys_js)
