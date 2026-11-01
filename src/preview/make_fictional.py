# -*- coding: utf-8 -*-
"""Fictional example data for the 2.0 preview page (app-preview.html): python src/preview/make_fictional.py [--real DIR]

Every company, code and number here is MADE UP. Names follow the style of Jack's mockup (늘봄금융, 솔담정밀, 마루식품,
Pinecrest Health come from docs/design/mockup-copy.csv). Group ids and Korean group names are the real ones from
data/industry_groups.csv (branch claude/v17.5.1-industry), so the screens behave like they will on live data.

Hard rules (checked here and again in tests/test_preview.py):
- no name equals a real company name, and no code equals a real code, in the reference files: the repo's data.json,
  tests/fixtures/v2/*.json, and --real DIR/{data,corp}.json when given (a real published run);
- every v17.5.1 field is present: d1, val20 (KR), etf (all), ind/indName, dps incl. some 0, fy, macro idxHist;
- every industry group used has at least 5 members in its market; a few funds, bonds and gold are included (never
  ranked) and two preferred shares (never ranked, can be pinned).
Fixed dates (the preview never shows a stale warning, see src/v2/load.js): pxDate 2026-10-30, published 2026-10-31.
Output: src/preview/fictional.json (embedded into app-preview.html by build-app.sh).
"""
import argparse
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "src", "preview", "fictional.json")
SEED = 20261101
PX_DATE, PUBLISHED = "2026-10-30", "2026-10-31T06:41:00+09:00"

# group id -> (Korean name from data/industry_groups.csv, KR name suffixes, US name suffixes)
KR_GROUPS = {
    "semi": ("반도체", ["반도체", "실리콘"]), "semi_eq": ("반도체 장비", ["정밀", "테크"]),
    "auto": ("자동차", ["모터스", "자동차"]), "bank": ("은행", ["금융", "은행"]),
    "insurance": ("보험", ["생명", "화재"]), "securities": ("증권", ["증권", "투자증권"]),
    "food": ("음식료·담배", ["식품", "푸드"]), "chem": ("화학", ["화학", "케미칼"]),
    "machinery": ("기계", ["기계", "중공업"]), "pharma": ("제약", ["제약", "약품"]),
    "holding": ("지주회사", ["홀딩스", "지주"]), "utility": ("전력·가스·환경", ["에너지", "전력"]),
    "construction": ("건설·엔지니어링", ["건설", "산업개발"]),
}
US_GROUPS = {
    "semi": ("반도체", ["Semiconductor", "Silicon"]), "software": ("소프트웨어", ["Software", "Systems"]),
    "bank": ("은행", ["Bancorp", "Financial"]), "medical": ("의료기기", ["Health", "Medical"]),
    "food": ("음식료·담배", ["Foods", "Brands"]), "utility": ("전력·가스·환경", ["Utilities", "Power"]),
    "energy": ("정유·에너지", ["Energy", "Resources"]),
}
FIN = {"bank", "insurance", "securities", "finance", "fin"}
KR_PREFIX = ["늘봄", "솔담", "마루", "다온", "가람", "미르", "해솔", "온새", "바름", "단비", "새결", "고운", "별하", "도담",
             "시나", "여울", "이든", "한울", "다솜", "산들", "예솔", "윤슬", "은솔", "찬솔", "해든", "푸름", "가온", "슬기",
             "보람", "새봄", "하람", "도란", "비솔", "소담", "아토", "늘솔", "단솔", "결고", "물빛", "들꽃", "볕뉘", "구름결"]
US_PREFIX = ["Pinecrest", "Larkfield", "Northwind", "Silverbay", "Amberline", "Cedarbrook", "Foxhollow", "Glenmoor",
             "Harborview", "Ironwood", "Juniper", "Kestrel", "Lakemont", "Meadowlark", "Oakhaven", "Quarrystone",
             "Redfern", "Stonebridge", "Thistledown", "Willowmere", "Brightwater", "Copperleaf", "Driftwood", "Eastvale",
             "Fernhill", "Goldmoor", "Hollowell", "Marbleton", "Nettlefield", "Orchardine", "Pebblecrest", "Rosewick"]
MOCKUP = {"bank": "늘봄금융", "semi_eq": "솔담정밀", "food": "마루식품"}


def real_reference(extra):
    names, codes = set(), set()
    paths = [os.path.join(ROOT, "data.json"), os.path.join(ROOT, "corp.json")]
    paths += [os.path.join(ROOT, "tests", "fixtures", "v2", f) for f in ("data.json", "corp.json")]
    if extra:
        paths += [os.path.join(extra, "data.json"), os.path.join(extra, "corp.json")]
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for s in d.get("stocks", []) + d.get("companies", []):
            codes.add(str(s.get("t")).upper())
            for k in ("nk", "ne"):
                if s.get(k):
                    names.add(str(s[k]).strip().lower())
    return names, codes


def pct_ranks(vals, higher_better=True):
    """0-100 percentile like pandas rank(pct=True)*100; None stays None."""
    idx = [i for i, v in enumerate(vals) if v is not None]
    order = sorted(idx, key=lambda i: vals[i])
    out = [None] * len(vals)
    n = len(order)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            p = 100 * r / n
            out[order[k]] = int(round(p if higher_better else 100 - p))
        i = j + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default=None, help="folder with a real published run (data.json, corp.json) to avoid")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    rnd = random.Random(SEED)
    real_names, real_codes = real_reference(args.real)

    used = set()

    def pick_name(prefixes, suffix, fixed=None):
        if fixed:
            assert fixed.lower() not in real_names, fixed
            used.add(fixed)
            return fixed
        for _ in range(500):
            n = rnd.choice(prefixes) + ("" if prefixes is KR_PREFIX else " ") + suffix
            if n not in used and n.lower() not in real_names:
                used.add(n)
                return n
        raise SystemExit("ran out of fictional names")

    kr_code = iter(f"98{i:03d}0" for i in range(1, 999))
    stocks, comps = [], []

    def kr_stock(g, gname, name, q, v):
        t = next(kr_code)
        while t in real_codes:
            t = next(kr_code)
        fin = g in FIN
        price = float(round(rnd.uniform(4000, 280000), -1))
        cap = round(math.exp(rnd.uniform(math.log(0.4), math.log(60))), 3)
        val = round(cap * rnd.uniform(15, 90), 1)
        roe = round(9 + 6 * q + rnd.gauss(0, 3), 1)
        debt = round(rnd.uniform(800, 1400)) if fin else round(max(15, 110 - 45 * q + rnd.gauss(0, 30)))
        pbr = round(max(0.2, 1.4 - 0.35 * v - 0.25 * q + rnd.gauss(0, 0.2)), 2)   # one shared "quality" factor q: the
        # example companies that are good on one card tend to be good on others, so multi-card decks find candidates
        vol = round(max(14, 36 - 6 * q + rnd.gauss(0, 6)), 1)
        beta = round(min(1.8, max(0.3, 0.95 + rnd.gauss(0, 0.25))), 2)
        g3 = None if fin else round(5 + 4 * q + rnd.gauss(0, 7), 1)
        opm = None if fin else round(7 + 4 * q + rnd.gauss(0, 4), 1)
        pays = rnd.random() > (0.35 - 0.15 * q)
        dps = float(round(price * rnd.uniform(0.008, 0.05) * (1 + 0.3 * max(-1, q)), -1)) if pays else 0.0
        prev = dps * rnd.uniform(0.85, 1.0) if pays else 0.0
        if pays and rnd.random() < 0.12:
            prev = dps * rnd.uniform(1.08, 1.25)                     # a dividend drop -> 확인 필요 in 후보 고르기
        dps3 = [dps, float(round(prev, -1)), float(round(prev * rnd.uniform(0.85, 1.0), -1))]
        rev0 = round(cap * rnd.uniform(800, 3000), 1)
        fall = rnd.random() < 0.1
        rev = [rev0, round(rev0 * (1.06 if fall else rnd.uniform(0.85, 0.98)), 1), round(rev0 * (1.12 if fall else rnd.uniform(0.75, 0.95)), 1)]
        op0 = round(rev0 * ((opm or 8) / 100), 1)
        opfall = rnd.random() < 0.1
        op = [op0, round(op0 * (1.2 if opfall else rnd.uniform(0.8, 1.0)), 1), round(op0 * (1.45 if opfall else rnd.uniform(0.7, 1.0)), 1)]
        s = {"t": t, "nk": name, "ne": name, "cls": "kr", "s": g, "price": price, "cap": cap, "val": val,
             "val20": round(val * rnd.uniform(0.7, 1.3), 1), "vol": vol, "beta": beta, "roe": roe, "debt": debt, "pbr": pbr,
             "per": round(max(3, pbr / max(roe, 1) * 100 + rnd.gauss(0, 2)), 1), "dps": dps, "dps3": dps3,
             "dy": round(dps / price * 100, 2), "mom": round(rnd.gauss(12 + 10 * q, 25), 1), "d1": round(rnd.gauss(0, 1.4), 2),
             "etf": False, "ind": g, "indName": gname, "fy": 2025, "lo": round(price * 0.7, -1), "hi": round(price * 1.35, -1)}
        if g3 is not None:
            s["g3"] = g3
        if opm is not None:
            s["opm"] = opm
        stocks.append(s)
        comps.append({"t": t, "nk": name, "s": g, "price": price, "cap": cap, "per": s["per"], "pbr": pbr, "dy": s["dy"], "dps": dps,
                      "roe": roe, "opm": opm, "g3": g3, "debt": debt, "beta": beta, "vol": vol, "rev": rev, "op": op,
                      "ni": [round(x * 0.75, 1) for x in op], "dps3": dps3, "fy": 2025, "bq": "2026.2Q", "ind": g, "indName": gname})
        return s

    # Korean companies: 13 groups x 6 (the mockup names first), plus 2 without a group
    for g, (gname, suffixes) in KR_GROUPS.items():
        for i in range(6):
            fixed = MOCKUP.get(g) if i == 0 else None
            name = pick_name(KR_PREFIX, rnd.choice(suffixes), fixed)
            kr_stock(g, gname, name, rnd.gauss(0, 1), rnd.gauss(0, 1))
    for _ in range(2):
        s = kr_stock("services", "사업 서비스", pick_name(KR_PREFIX, "서비스"), rnd.gauss(0, 1), rnd.gauss(0, 1))
        del s["ind"], s["indName"]
        comps[-1].pop("ind"), comps[-1].pop("indName")
    # two preferred shares (KRX code ends in 5): never ranked, can be pinned
    for base in stocks[:2]:
        p = {k: v for k, v in base.items() if k not in ("ind", "indName")}
        p.update({"t": base["t"][:-1] + "5", "nk": base["nk"] + "우", "ne": base["nk"] + "우", "price": round(base["price"] * 0.8, -1),
                  "val20": round(base["val20"] * 0.2, 1)})
        assert p["t"] not in real_codes and p["nk"].lower() not in real_names
        stocks.append(p)

    # US companies: 7 groups, 5-6 each (Pinecrest Health first)
    tick_used = set()

    def ticker(name):
        letters = [c for c in name.upper() if c.isalpha()]
        for _ in range(500):
            n = rnd.choice([4, 5])
            t = letters[0] + "".join(rnd.choice(letters[1:] + list("QXZ")) for _ in range(n - 1))
            if t not in real_codes and t not in tick_used:
                tick_used.add(t)
                return t
        raise SystemExit("no ticker")

    sizes = {"semi": 6, "software": 6, "bank": 6, "medical": 6, "food": 6, "utility": 5, "energy": 5}
    for g, (gname, suffixes) in US_GROUPS.items():
        for i in range(sizes[g]):
            name = "Pinecrest Health" if (g == "medical" and i == 0) else pick_name(US_PREFIX, rnd.choice(suffixes))
            if name == "Pinecrest Health":
                assert name.lower() not in real_names
            q = rnd.gauss(0, 1)
            fin = g in FIN
            price = round(math.exp(rnd.uniform(math.log(15), math.log(600))), 2)
            cap = round(math.exp(rnd.uniform(math.log(5), math.log(900))), 3)
            pays = g in ("bank", "food", "utility", "energy") or rnd.random() > (0.5 - 0.25 * q)
            s = {"t": ticker(name), "nk": name, "ne": name, "cls": "us", "ccy": "USD", "fxu": True, "s": g, "price": price, "cap": cap,
                 "val": round(cap * rnd.uniform(20, 120), 1), "vol": round(max(14, 30 - 5 * q + rnd.gauss(0, 6)), 1),
                 "beta": round(min(1.7, max(0.4, 1.0 + rnd.gauss(0, 0.25))), 2), "roe": round(14 + 7 * q + rnd.gauss(0, 4), 1),
                 "debt": round(rnd.uniform(200, 900)) if fin else round(max(5, 80 - 30 * q + rnd.gauss(0, 25))),
                 "pbr": round(max(0.6, 3.2 - 0.8 * rnd.gauss(0, 1) - 0.6 * q + rnd.gauss(0, 0.5)), 2), "g3": round(6 + 4 * q + rnd.gauss(0, 6), 1),
                 "opm": round(15 + 5 * q + rnd.gauss(0, 5), 1), "dy": round(rnd.uniform(0.6, 4.0) * (1 + 0.25 * max(-1, q)), 2) if pays else 0.0,
                 "mom": round(rnd.gauss(10 + 8 * q, 20), 1), "d1": round(rnd.gauss(0, 1.2), 2), "etf": False, "ind": g, "indName": gname,
                 "lo": round(price * 0.75, 2), "hi": round(price * 1.3, 2)}
            stocks.append(s)

    # funds, bonds, gold (fictional; never ranked). The bond and gold funds are the preview's 안전자산.
    funds = [
        {"t": "98B010", "nk": "누리솔 국고채3년", "cls": "bond", "s": "bond", "price": 61250.0, "vol": 2.1, "beta": 0.01, "dur": 2.6, "grp": "국고채"},
        {"t": "98B020", "nk": "누리솔 단기채권", "cls": "bond", "s": "bond", "price": 104300.0, "vol": 0.4, "beta": 0.0, "dur": 0.5, "grp": "단기"},
        {"t": "98G010", "nk": "누리솔 금선물(H)", "cls": "metal", "s": "metal", "price": 21800.0, "vol": 22.0, "beta": 0.2, "fund": True},
        {"t": "98I010", "nk": "누리솔 코스피 대형주", "cls": "kr", "s": "index", "price": 18450.0, "vol": 30.0, "beta": 1.0, "fund": True},
        {"t": "LRKBX", "nk": "Larkfield Broad Market ETF", "cls": "us", "ccy": "USD", "fxu": True, "s": "index", "price": 182.4, "vol": 17.0,
         "beta": 1.0, "roe": 18.0, "pbr": 4.0, "dy": 1.3, "val": 9000.0, "cap": 400.0},
    ]
    for f in funds:
        assert f["t"] not in real_codes and f["nk"].lower() not in real_names, f
        f.update({"ne": f["nk"], "etf": True, "d1": round(rnd.gauss(0, 0.8), 2)})
        stocks.append(f)

    # factor percentiles within each market (company shares only), like fetch_data.add_percentiles
    for mk in ("kr", "us"):
        group = [s for s in stocks if s["cls"] == mk and not s["etf"]]
        cols = {"pz": ([s.get("cap") for s in group], False), "vz": ([s.get("pbr") for s in group], False),
                "mz": ([s.get("mom") for s in group], True), "qz": ([s.get("roe") for s in group], True),
                "lz": ([s.get("vol") for s in group], False)}
        for k, (vals, hb) in cols.items():
            for s, r in zip(group, pct_ranks(vals, hb)):
                if r is not None:
                    s[k] = r
    # a couple of bigger daily moves
    for s in [x for x in stocks if x["cls"] == "kr" and not x["etf"]][3:5]:
        s["d1"] = -6.2 if s["d1"] < 0 else 5.4

    # guards
    for s in stocks:
        assert str(s["t"]).upper() not in real_codes, s["t"]
        assert s["nk"].lower() not in real_names, s["nk"]
    for mk in ("kr", "us"):
        counts = {}
        for s in stocks:
            if s["cls"] == mk and s.get("ind") and not s["etf"]:
                counts[s["ind"]] = counts.get(s["ind"], 0) + 1
        assert all(n >= 5 for n in counts.values()), (mk, counts)

    def hist(end, start_val, drift):
        import datetime as dt
        d, rows, v = dt.date.fromisoformat(end), [], start_val
        while len(rows) < 750:
            if d.weekday() < 5:
                rows.append([d.isoformat(), round(v, 2)])
                v = v / (1 + drift + rnd.uniform(-0.011, 0.011))
            d -= dt.timedelta(days=1)
        return {"asOf": end, "rows": rows[::-1]}

    settings = {"rf": 4.0, "rfSrc": "example", "mktVol": 30.0, "usVol": 18.0, "mtVol": 22.0, "rhoKrUs": 0.3, "rhoKrMt": 0.05,
                "rhoUsMt": 0.1, "bdVol": 5.0, "rhoKrBd": 0.1, "rhoUsBd": -0.1, "rhoMtBd": 0.0}
    data = {"asOf": "2026-10-31", "pxDate": PX_DATE, "ksDate": PX_DATE, "usPxDate": PX_DATE, "fxDate": PX_DATE, "publishedAt": PUBLISHED,
            "fx": 1338.0, "fictional": True, "settings": settings, "stocks": stocks}
    corp = {"asOf": "2026-10-31", "pxDate": PX_DATE, "publishedAt": PUBLISHED, "fictional": True, "companies": comps}
    macro = {"asOf": "2026-10-31", "publishedAt": PUBLISHED, "fictional": True,
             "idxHist": {"KOSPI": hist(PX_DATE, 4100.0, 0.0004), "SP500": hist(PX_DATE, 6200.0, 0.0003)}}
    out = {"note": "Fictional example data for app-preview.html. Not real companies, codes or prices.",
           "cushion": [{"t": "98B010", "share": 0.5, "like": "114260"}, {"t": "98G010", "share": 0.5, "like": "132030"}],
           "data": data, "corp": corp, "macro": macro}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        f.write("\n")
    kr_n = sum(1 for s in stocks if s["cls"] == "kr" and not s["etf"])
    us_n = sum(1 for s in stocks if s["cls"] == "us" and not s["etf"])
    print(f"fictional.json: {kr_n} KR shares (incl. 2 preferred), {us_n} US, {len(funds)} funds; checked against {len(real_names)} real names")


if __name__ == "__main__":
    main()
