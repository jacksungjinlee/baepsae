# -*- coding: utf-8 -*-
"""검증용 가짜 데이터 — 모든 검사를 통과하는 '좋은' 네 파일을 만들어요.
must-fail 테스트는 여기서 한 군데씩만 망가뜨립니다. (네트워크 없음)"""
import copy
import datetime as dt
import random

MUST = [("005930", "삼성전자"), ("000660", "SK하이닉스"), ("005380", "현대차"), ("015760", "한국전력"),
        ("105560", "KB금융"), ("035420", "NAVER"), ("012450", "한화에어로스페이스")]
FUNDS = [("069500", "kr"), ("379800", "us"), ("04020000", "metal"), ("132030", "metal"), ("144600", "metal")]
SECTORS = ["semi", "battery", "elec", "auto", "ship", "defense", "machine", "steel", "chem", "utility", "energy", "bio",
           "health", "platform", "game", "media", "telecom", "bank", "insure", "broker", "holding", "build", "retail",
           "food", "etc"]


def build(px_date="2026-10-30", us_date="2026-10-30", seed=7, n_kr=2400, n_us=600, price_shift=0.0):
    rnd = random.Random(seed)
    kr = []
    names = [(t, nk) for t, nk in MUST] + [(f"{100000 + i:06d}", f"가상종목{rnd.randrange(10**6):06d}") for i in range(n_kr - len(MUST))]
    for i, (t, nk) in enumerate(names):
        price = float(round(rnd.uniform(1000, 300000) * (1 + price_shift)))
        cap = 1300.0 if t == "005930" else (1000.0 if t == "000660" else round(rnd.uniform(0.05, 300), 3))
        kr.append({"t": t, "nk": nk, "ne": nk, "cls": "kr", "s": SECTORS[i % len(SECTORS)], "price": price,
                   "cap": cap, "val": round(rnd.uniform(1, 9000), 1) if t != "005930" else 99999.0,
                   "beta": round(rnd.uniform(0.3, 1.8), 2), "vol": round(rnd.uniform(15, 80), 1),
                   "pbr": round(rnd.uniform(0.3, 5), 2), "roe": round(rnd.uniform(-10, 30), 1),
                   "per": round(rnd.uniform(3, 60), 1), "vz": 50, "qz": 50, "mz": 50, "pz": 50, "lz": 50,
                   # v17.5.1 새 항목
                   "d1": round(rnd.uniform(-5, 5), 2), "val20": round(rnd.uniform(1, 9000), 1), "etf": False,
                   "dps": 1668.0 if t == "005930" else float(rnd.choice([0, 0, 100, 500, 1500])), "fy": 2025,
                   "hi": round(price * 1.3), "lo": round(price * 0.8),
                   "dk": f"업종{i % 40} · 주요제품: 제품{i} · KOSPI 상장 · 시가총액 {cap:,.1f}조원"})
    us_t = ["AAPL", "MSFT", "NVDA", "BRK-B", "SPY", "QQQ"] + [f"U{i:04d}" for i in range(n_us - 6)]
    us = [{"t": t, "nk": f"US Corp {i}", "ne": f"US Corp {i}", "cls": "us", "price": round(rnd.uniform(5, 900) * (1 + price_shift), 2),
           "cap": round(rnd.uniform(1, 5000), 3), "val": round(rnd.uniform(1, 90000), 1), "de": "A company.", "fxu": True,
           "d1": round(rnd.uniform(-5, 5), 2), "etf": t in ("SPY", "QQQ")}
          for i, t in enumerate(us_t)]
    bonds = [{"t": f"B{i}", "nk": f"채권{i}", "cls": "bond", "s": "bond", "price": 100000.0, "etf": True} for i in range(8)]
    funds = [{"t": t, "nk": t, "cls": c, "s": "index", "price": 10000.0, "fund": True, "etf": True} for t, c in FUNDS]
    data = {"asOf": "2026-10-31", "pxDate": px_date, "ksDate": px_date, "usPxDate": us_date,
            "publishedAt": "2026-10-31T09:30:00+09:00", "listSrc": "fdr_krx_data_cache", "fx": 1333.3,
            "settings": {"rf": 4.0, "rfSrc": "ECOS 국고채10년 " + px_date},
            "popular": ["005930", "000660"] + [s["t"] for s in kr[7:30]],
            "count": {"kr": len(kr), "us": len(us), "bond": len(bonds), "fund": len(funds)},
            "stocks": kr + us + bonds + funds}
    comps = [{"t": s["t"], "nk": s["nk"], "s": s["s"], "price": s["price"], "cap": s["cap"],
              "per": s["per"], "pbr": s["pbr"], "bq": "2026.2Q" if i % 10 else None,
              "debt": 50.0, "op": [100.0, 90.0, 80.0], "dps": s["dps"], "fy": s["fy"]} for i, s in enumerate(kr[:2100])]
    pub = data["publishedAt"]          # 네 파일 모두 같은 발행 시각 (fetch_data.main 이 한 번 정해서 씀)
    corp = {"asOf": "2026-10-31", "pxDate": px_date, "publishedAt": pub, "sectors": {k: {"n": 1} for k in SECTORS}, "companies": comps}
    macro = {"asOf": "2026-10-31", "publishedAt": pub, "curve": {"tenors": [3, 10], "now": [3.1, 4.0], "ago": [3.0, 3.5], "date": px_date},
             "idxHist": {"KOSPI": idx_rows(px_date, 2500.0), "SP500": idx_rows(us_date, 5000.0)}}
    disc = {"asOf": "2026-10-31", "publishedAt": pub, "newest": "2026-10-30", "listOk": True, "insider": [], "nps": []}
    closes = {s["t"]: round(s["price"]) for s in kr}
    return {"data": data, "corp": corp, "disc": disc, "macro": macro}, closes


def idx_rows(end, base, years=3):
    """평일만 3년치 지수 종가 (마지막 = end)."""
    e = dt.date.fromisoformat(end)
    d, rows = e - dt.timedelta(days=365 * years - 1), []
    while d <= e:
        if d.weekday() < 5:
            rows.append([d.isoformat(), round(base + len(rows) * 0.5, 2)])
        d += dt.timedelta(days=1)
    return {"asOf": end, "rows": rows}


def hilo_of(files, codes):
    """야후에서 받은 것처럼: 필수 종목의 (최고, 최저) 를 그대로."""
    by = {s["t"]: s for s in files["data"]["stocks"]}
    return {t: (by[t]["hi"], by[t]["lo"]) for t in codes if t in by}


def good_pair():
    """(이번 파일, 직전 발행본, 최종본) — 직전은 하루 전 pxDate, 가격이 조금씩 달라요."""
    cur, closes = build()
    prev, _ = build(px_date="2026-10-29", us_date="2026-10-29", price_shift=-0.01)
    for s, p in zip(cur["data"]["stocks"], prev["data"]["stocks"]):
        if s.get("cls") == "kr":
            p["price"] = round(s["price"] * 0.99)     # 하루 1% 움직임
    final = {"date": __import__("datetime").date(2026, 10, 30), "closes": closes, "how": "시험"}
    return cur, prev, final


def stock(files, t):
    return next(s for s in files["data"]["stocks"] if s["t"] == t)


def clone(x):
    return copy.deepcopy(x)
