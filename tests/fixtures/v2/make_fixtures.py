# -*- coding: utf-8 -*-
"""Fixtures for the 2.0 beta (app.html) tests: python tests/fixtures/v2/make_fixtures.py --src DIR

DIR holds a real published run (data.json, corp.json, macro.json in the v17.5 format). The script keeps a
deterministic sample of it and adds the fields the data session is adding in v17.5.1 (v18.0 Part A additions 4-9),
which are NOT live yet:
  d1, val20, etf, ind/indName, dps = 0 kept, fy, macro.idxHist.
Everything added here is synthetic (made up for tests). The live page never loads these files.
Committed output: tests/fixtures/v2/{data,corp,macro}.json (the run used: 2026-11-01 publish, pxDate 2026-10-30).
"""
import argparse
import datetime as dt
import json
import os
import random

OUT = os.path.dirname(os.path.abspath(__file__))

# Group ids and Korean group names for the fixture only (the real ones come from data/industry_map.csv in v18.0).
GROUPS = {
    "semi": "반도체", "auto": "자동차", "bank": "은행", "insurance": "보험", "securities": "증권", "holding": "지주회사",
    "battery": "2차전지", "elec": "전자부품", "chem": "화학", "bio": "바이오", "machine": "기계", "retail": "유통",
    "steel": "철강", "build": "건설", "utility": "전력·가스", "media": "미디어", "health": "헬스케어", "platform": "인터넷",
    "textile": "섬유", "paper": "종이", "transport": "운송", "food": "식품", "realestate": "부동산", "defense": "방산",
    "telecom": "통신", "ship": "조선", "hotel": "호텔·레저", "edu": "교육", "energy": "에너지", "game": "게임",
    "cosmetic": "화장품",
}
S_TO_IND = {"insure": "insurance", "broker": "securities"}          # old sector key -> group id
MUST_IND = {"005930": "semi", "000660": "semi", "005380": "auto", "000270": "auto", "105560": "bank", "086790": "bank",
            "034730": "holding", "003550": "holding"}
MUST = ["005930", "000660", "005380", "000270", "105560", "086790", "034730", "003550", "015760", "035420", "012450",
        "005935", "005385", "055550", "032830", "000810", "316140", "006400", "051910", "068270", "207940", "035720"]
US_ETF = {"ARKK", "DIA", "GLD", "IAU", "IEF", "IVE", "IVV", "IWM", "JEPI", "JEPQ", "MTUM", "QQQ", "QUAL", "SCHD", "SHY",
          "SLV", "SMH", "SOXX", "SPHQ", "SPY", "TLT", "VBR", "VOO", "VT", "VTI", "VYM", "XLE", "XLF", "XLI", "XLK", "XLP",
          "XLV", "XLY", "STRC"}
DROP = ("de", "dk", "x")   # long description text: not needed by the tests


def load(src, name):
    with open(os.path.join(src, name), encoding="utf-8") as f:
        return json.load(f)


def write(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        f.write("\n")


def ind_of(s):
    if s["t"] in MUST_IND:
        return MUST_IND[s["t"]]
    k = S_TO_IND.get(s.get("s"), s.get("s"))
    return k if k in GROUPS else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    args = ap.parse_args()
    rnd = random.Random(18)
    data, corp, macro = load(args.src, "data.json"), load(args.src, "corp.json"), load(args.src, "macro.json")
    stocks = data["stocks"]
    kr = [s for s in stocks if s["cls"] == "kr" and not s.get("fund")]
    us = [s for s in stocks if s["cls"] == "us" and not s.get("fund")]
    other = [s for s in stocks if s["cls"] in ("bond", "metal") or s.get("fund")]
    by_cap = lambda arr: sorted(arr, key=lambda s: -(s.get("cap") or 0))
    keep_kr = {s["t"] for s in kr if s["t"] in MUST} | {s["t"] for s in by_cap(kr)[:260]}
    keep_kr |= {s["t"] for s in rnd.sample(by_cap(kr)[260:], 140)}
    keep_us = {s["t"] for s in by_cap(us)[:110]} | {s["t"] for s in us if s["t"] in US_ETF}
    out = []
    for s in stocks:
        if not (s["t"] in keep_kr or s["t"] in keep_us or s in other):
            continue
        x = {k: v for k, v in s.items() if k not in DROP}
        x["etf"] = bool(s.get("fund") or s["cls"] in ("bond", "metal") or s["t"] in US_ETF)
        if s["cls"] in ("kr", "us") and not x["etf"]:
            g = ind_of(s)
            if g and not (s["cls"] == "kr" and rnd.random() < 0.04):     # a few stocks without a group
                x["ind"], x["indName"] = g, GROUPS[g]
            x["d1"] = round(rnd.uniform(-3, 3), 2)
        if s["cls"] == "kr" and not x["etf"]:
            if s.get("val") is not None and rnd.random() > 0.02:            # a few without val20
                x["val20"] = round(s["val"] * rnd.uniform(0.6, 1.4), 1)
            if "dps" not in s and rnd.random() < 0.6:
                x["dps"] = 0.0                                              # pays nothing (kept as 0)
            if any(k in s for k in ("debt", "roe", "dps")):
                x["fy"] = 2025
        out.append(x)
    # A must-have stock below the liquidity floor would break the smoke test; keep them liquid.
    for x in out:
        if x["t"] in MUST and x.get("val20") is not None:
            x["val20"] = max(x["val20"], 50.0)
    data_out = {k: v for k, v in data.items() if k != "stocks"}
    data_out["stocks"] = out
    data_out["count"] = {"kr": sum(1 for s in out if s["cls"] == "kr" and not s["etf"]),
                         "us": sum(1 for s in out if s["cls"] == "us" and not s["etf"])}
    data_out["fixture"] = "tests/fixtures/v2: sampled from the 2026-11-01 run plus synthetic v17.5.1 fields"
    keep = {x["t"] for x in out}
    comps = []
    for c in corp["companies"]:
        if c["t"] not in keep:
            continue
        y = dict(c)
        y["fy"] = 2025
        src = next(x for x in out if x["t"] == c["t"])
        if "ind" in src:
            y["ind"], y["indName"] = src["ind"], src["indName"]
        comps.append(y)
    corp_out = {k: v for k, v in corp.items() if k != "companies"}
    corp_out["companies"] = comps
    # idxHist: synthetic weekday closes for 3 years, ending at each market's own close date.
    def hist(end, start_val, drift):
        d, rows, v = dt.date.fromisoformat(end), [], start_val
        while len(rows) < 750:
            if d.weekday() < 5:
                rows.append([d.isoformat(), round(v, 2)])
                v = v / (1 + drift + rnd.uniform(-0.012, 0.012))
            d -= dt.timedelta(days=1)
        return {"asOf": end, "rows": rows[::-1]}
    macro_out = dict(macro)
    macro_out["idxHist"] = {"KOSPI": hist(data["pxDate"], 5730.0, 0.0004), "SP500": hist(data["usPxDate"], 6800.0, 0.0003)}
    write("data.json", data_out)
    write("corp.json", corp_out)
    write("macro.json", macro_out)
    print(f"fixtures: {len(out)} items ({data_out['count']}), {len(comps)} companies")


if __name__ == "__main__":
    main()
