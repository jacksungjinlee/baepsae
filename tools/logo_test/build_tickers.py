#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build tickers.csv for the logo coverage test (v19.1 Part L) from public files only — no DART key, no provider key.

  python3 tools/logo_test/build_tickers.py                       # live data.json -> <scratch>/tickers.csv
  python3 tools/logo_test/build_tickers.py --data data.json --out /some/scratch/folder

Sources
  - data.json (live site, or a local copy): every Korean and US stock (cls kr / us), name, market cap (조원 for both,
    US converted at that day's rate), ETF flag. pxDate picks the KRX files below.
  - KRX listing CSV for pxDate (FinanceData/fdr_krx_data_cache, the file fetch_data.py reads): Market and the ISIN
    (ISU_CD). Every ISIN's check digit is verified. The listing has no ETFs, so an ETF's ISIN is derived where the
    rule is exact (kr_isin_from_code) and marked 'derived'.
  - KRX company list CSV for pxDate (same cache, data/listing/desc): HomePage -> domain. A preferred share takes its
    common share's homepage. Platform hosts (naver.com …) and a domain listed for two or more different companies are
    left blank and logged: a logo looked up by them would belong to someone else.
  US domains and US ISINs stay blank: no free keyless source (DART company.json hm_url is Korean only and needs the
  DART key; a US website could come from Yahoo's company profile later if the ticker routes miss).

Writes tickers.csv to the scratch folder (never into the repository) and prints counts per market.
"""
import argparse
import collections
import csv
import datetime as dt
import io
import json
import sys

import requests

from logo_common import (DATA_URL, DESC_URL, LISTING_URL, ROOT, TICKER_COLS, common_code, homepage_domain, is_krx_code,
                         is_shared_host, isin_valid, kr_isin_from_code, out_dir, top_companies, write_csv)

sys.path.insert(0, str(ROOT))
from fetch_data import _fin  # noqa: E402  (the pipeline's NaN-safe number check, CLAUDE.md)

LOOKBACK_DAYS = 10
# Must be among the 200 largest companies of their side (the contact sheets are per side: the 200 largest of KR and US
# together are 196 US companies and 4 Korean ones, which would not show Korean wrong matches).
MUST_TOP = {"kr": ("005930", "000660", "005380"), "us": ("AAPL", "MSFT", "NVDA")}
MARKET_MAP = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ", "KOSDAQ GLOBAL": "KOSDAQ", "KONEX": "KONEX"}


def get_text(src, what):
    if src.startswith(("http://", "https://")):
        r = requests.get(src, timeout=60)
        r.raise_for_status()
        print(f"· {what}: {src} ({len(r.content):,} bytes)")
        return r.content.decode("utf-8-sig")
    with open(src, encoding="utf-8-sig") as f:
        t = f.read()
    print(f"· {what}: {src} ({len(t):,} chars, local file)")
    return t


def krx_csv(src, url_tpl, day, what):
    """A KRX cache CSV as {Code: row}: src is a local path, or 'auto' = the file for `day`, else the latest earlier
    one within LOOKBACK_DAYS (logged loudly when it is not `day`)."""
    if src != "auto":
        return {r["Code"]: r for r in csv.DictReader(io.StringIO(get_text(src, what)))}, src
    d0 = dt.date.fromisoformat(day)
    for back in range(LOOKBACK_DAYS + 1):
        d = (d0 - dt.timedelta(days=back)).isoformat()
        url = url_tpl.format(d=d)
        r = requests.get(url, timeout=60)
        if r.status_code == 404:
            continue
        r.raise_for_status()
        if back:
            print(f"!! {what}: no file for {day}; using {d} ({back} days older)")
        print(f"· {what}: {url} ({len(r.content):,} bytes)")
        rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
        return {x["Code"]: x for x in rows}, d
    raise SystemExit(f"!! {what}: no file for {day} or the {LOOKBACK_DAYS} days before it")


def build(data, listing, desc):
    """Pure: data.json dict + {code: listing row} + {code: desc row} -> (rows, log lines)."""
    log = []
    stocks = [s for s in data.get("stocks", []) if s.get("cls") in ("kr", "us")]
    rows = []
    for s in stocks:
        code = str(s.get("t") or "").strip()
        etf = bool(s.get("etf"))
        krx = is_krx_code(code)
        L = listing.get(code) if krx else None
        if krx:
            raw = (L or {}).get("Market", "")
            market = MARKET_MAP.get(raw, "")
            if not market and etf:
                market, raw = "KOSPI", "(ETF: KOSPI assumed — ETFs trade on the KOSPI market, not in the stock listing)"
            ticker = f"{code}.KQ" if market == "KOSDAQ" else f"{code}.KS"     # KONEX has no logo.dev suffix: .KS
        else:
            market, raw, ticker = "US", "US", code
        isin, isin_src = "", ""
        if L and L.get("ISU_CD"):
            if isin_valid(L["ISU_CD"]):
                isin, isin_src = L["ISU_CD"].strip().upper(), "krx_listing"
            else:
                log.append(f"!! {code}: listing ISIN {L['ISU_CD']!r} fails the check digit — left blank")
        elif krx:
            d = kr_isin_from_code(code)
            if d:
                isin, isin_src = d, "derived"
        issuer = common_code(code) if krx and common_code(code) in listing else code
        rows.append({
            "code": code, "name": s.get("nk") or s.get("ne") or code, "name_en": s.get("ne") or "",
            "cls": s.get("cls"), "market": market, "market_raw": raw, "etf": "1" if etf else "0",
            "cap": _fin(s.get("cap")), "ticker": ticker, "isin": isin, "isin_src": isin_src,
            "issuer_code": issuer,
            "domain": "", "domain_src": "", "homepage_raw": "",
        })
    # homepages: own row first, else the common share's
    for r in rows:
        if r["market"] == "US":
            continue
        own = (desc.get(r["code"]) or {}).get("HomePage", "").strip()
        com = (desc.get(r["issuer_code"]) or {}).get("HomePage", "").strip() if r["issuer_code"] != r["code"] else ""
        hp, src = (own, "krx_desc") if own else ((com, "krx_desc (common share)") if com else ("", ""))
        r["homepage_raw"] = hp
        dom = homepage_domain(hp)
        if hp and not dom:
            log.append(f"· {r['code']} {r['name']}: homepage {hp!r} is not a usable host — domain left blank")
        elif dom and is_shared_host(dom):
            log.append(f"· {r['code']} {r['name']}: homepage {hp!r} is a shared platform host — domain left blank")
            dom = ""
        r["domain"], r["domain_src"] = dom, (src if dom else "")
    issuers_per_domain = collections.defaultdict(set)
    for r in rows:
        if r["domain"]:
            issuers_per_domain[r["domain"]].add(r["issuer_code"])
    for r in rows:
        if r["domain"] and len(issuers_per_domain[r["domain"]]) > 1:
            log.append(f"· {r['code']} {r['name']}: domain {r['domain']} is listed for "
                       f"{len(issuers_per_domain[r['domain']])} companies — left blank")
            r["domain"], r["domain_src"] = "", ""
    # rank by cap: only rows with a cap; never rank a blank
    ranked = sorted((r for r in rows if r["cap"] and r["cap"] > 0), key=lambda r: -r["cap"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    for cls in ("kr", "us"):
        for i, r in enumerate((x for x in ranked if x["cls"] == cls), 1):
            r["rank_cls"] = i
    blank = [r["code"] for r in rows if not r.get("rank")]
    if blank:
        log.append(f"· no market cap (not ranked): {len(blank)} — {', '.join(blank[:12])}{' …' if len(blank) > 12 else ''}")
    for r in rows:
        r["cap"] = "" if r["cap"] is None else f"{r['cap']:.3f}"
        r.setdefault("rank", "")
        r.setdefault("rank_cls", "")
    return rows, log


def report(rows):
    g = collections.Counter(("ETF/fund" if r["etf"] == "1" else r["market"]) for r in rows)
    lines = ["tickers: " + " · ".join(f"{k} {g[k]:,}" for k in ("KOSPI", "KOSDAQ", "KONEX", "US", "ETF/fund"))
             + f" · total {len(rows):,}"]
    for m in ("KOSPI", "KOSDAQ", "KONEX", "US"):
        rs = [r for r in rows if r["market"] == m and r["etf"] == "0"]
        if not rs:
            continue
        isin = collections.Counter(r["isin_src"] or "none" for r in rs)
        dom = sum(1 for r in rs if r["domain"])
        lines.append(f"  {m:<6} companies {len(rs):>5,} · ISIN " + ", ".join(f"{k} {v:,}" for k, v in sorted(isin.items()))
                     + f" · domain {dom:,}")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default=DATA_URL, help="data.json URL or path (default: the live site)")
    ap.add_argument("--listing", default="auto", help="KRX listing CSV path, or auto (the file for data.json pxDate)")
    ap.add_argument("--desc", default="auto", help="KRX company list CSV path, or auto")
    ap.add_argument("--out", default=None, help="scratch folder (default: LOGO_TEST_DIR or the session scratchpad)")
    a = ap.parse_args(argv)
    folder = out_dir(a.out)
    data = json.loads(get_text(a.data, "data.json"))
    px = data.get("pxDate")
    if not px:
        raise SystemExit("!! data.json has no pxDate")
    print(f"· data.json asOf {data.get('asOf')} · pxDate {px} · count {data.get('count')}")
    listing, ld = krx_csv(a.listing, LISTING_URL, px, "KRX listing")
    desc, dd = krx_csv(a.desc, DESC_URL, px, "KRX company list")
    rows, log = build(data, listing, desc)
    for line in log:
        print(line)
    kr = [r for r in rows if r["market"] != "US"]
    missing_mkt = [r["code"] for r in kr if not r["market"]]
    if missing_mkt:
        raise SystemExit(f"!! {len(missing_mkt)} Korean codes have no market in the listing: {missing_mkt[:10]}")
    for side, must in MUST_TOP.items():
        top = {r["code"] for r in top_companies(rows, 200, side)}
        lost = [c for c in must if c not in top]
        if lost:
            raise SystemExit(f"!! must-have companies missing from the 200 largest ({side}): {lost}")
    n_kr = sum(1 for s in data["stocks"] if s.get("cls") == "kr")
    n_us = sum(1 for s in data["stocks"] if s.get("cls") == "us")
    if len(rows) != n_kr + n_us:
        raise SystemExit(f"!! wrote {len(rows)} rows but data.json has {n_kr} kr + {n_us} us")
    path = folder / "tickers.csv"
    write_csv(path, rows, TICKER_COLS)
    for line in report(rows):
        print(line)
    print(f"· KRX files: listing {ld} · company list {dd}")
    must = ", ".join(c for v in MUST_TOP.values() for c in v)
    print(f"wrote {path} ({len(rows):,} rows; must-have {must} are in the 200 largest of their side)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
