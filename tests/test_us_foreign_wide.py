# -*- coding: utf-8 -*-
"""미국 상장 외국 회사 검사 넓히기 (Jack, 2026-11-14 Q5) — fetch_data.py us_foreign_set · us_country · us_country_due · log_us_foreign_set ·
fetch_us(외국 회사 판별 · 나라 칸 다시 받기) 와 validate_data.py check_us_foreign 의 set 줄. (네트워크 없음 · 더하기만)

- 외국 회사는 규칙으로 찾아요: 재무제표 통화가 달러가 아님(fcur) · S&P 500 밖이면서 야후 본사 나라가 미국(푸에르토리코 포함) 밖이거나 이름이
  예탁증서 · #126 의 21곳은 바닥. S&P 500 회사(LIN · MDT · ACN · CB · TEL · ACGL …)는 외국 회사로 보지 않아요 (10-K · 달러 · 그 보통주).
- 넓힌 회사에도 같은 허용 폭 (PER 1.10 · PBR 1.35 · 배당 1.10) · fcur 회사는 #114 그대로 (검사 건너뜀 · 표시 없음 · 통화 줄 하나).
- 관문: set 의 회사(fcur 없음)에 숫자가 있는데 checked 에 없으면 실패 · 표시(fgnCut)는 set 의 회사에만 · set 모양과 근거 · 빠진 21곳 · fcur 회사.
  나라 모름 · 판별 중 멈춤 · TSM ASML BABA NVO SHOP 이 set 에 없음은 경고만. 검사가 멈춘 날은 #126 대로 경고.
값은 2026-11-14 야후 그대로 (필요한 칸만)."""
import datetime as dt
import json
import os
import sys
import types

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_us_more_stocks import SHEL, BP, BTI  # noqa: E402  (#126 의 2026-11-14 야후 값)

FOREIGN = "미국 상장 외국 회사: 회사 합계와 맞춘 PER·PBR·배당수익률만"
CONFIGURED = V.US_FGN_NOCMP          # 이 파일을 읽을 때의 스위치 값 (아래 고정 장치가 바꾸기 전 · 스위치를 다른 값으로 바꿔도 이 파일이 지나가는지 봐요)
SWITCHES = tuple(V.US_FGN_NOCMP_KIND)


def set_switch(monkeypatch, value):
    """스위치(validate_data.US_FGN_NOCMP)를 관문과 파이프라인 양쪽에서 같은 값으로 (fetch_data 는 그 값을 이름으로 가져와 따로 들고 있어요)."""
    monkeypatch.setattr(V, "US_FGN_NOCMP", value)
    monkeypatch.setattr(F, "US_FGN_NOCMP", value)


@pytest.fixture(autouse=True)
def switch_line(monkeypatch):
    """리뷰 2차 S2: 이 파일의 시험은 스위치 "line" 을 전제로 해요 — 그 값을 직접 정해 둬서, 누가 스위치를 keep · own 으로 바꿔도 (한 줄) 이 시험들이
    그 때문에 깨지지 않아요. 스위치마다 달라지는 시험은 SWITCHES 로 값마다 한 번씩 돌아요."""
    set_switch(monkeypatch, "line")


def yi(country, fc, short, **kw):
    """2026-11-14 야후 info 한 벌 (필요한 칸만)."""
    i = {"shortName": short, "longName": short, "quoteType": "EQUITY", "currency": "USD", "sector": "Technology", "industry": "Software",
         "averageVolume": 1e6, "longBusinessSummary": f"{short} does things."}
    if country is not None:
        i["country"] = country
    if fc is not None:
        i["financialCurrency"] = fc
    i.update(kw)
    return i


SHOP = yi("Canada", "USD", "Shopify Inc.", marketCap=189234511872, netIncomeToCommon=2126000000, trailingPE=90.239265,
          priceToBook=14.8410845, returnOnEquity=0.16833, dividendYield=0.0)
NBIS = yi("Netherlands", "USD", "Nebius Group N.V.", marketCap=33941528576, netIncomeToCommon=124500000, trailingPE=90.53125,
          priceToBook=2.761283, returnOnEquity=0.01455, dividendYield=0.0)
TRI = yi("Canada", "USD", "Thomson Reuters Corp", marketCap=47377055744, netIncomeToCommon=1618000000, trailingPE=33.527607,
         priceToBook=4.2210555, returnOnEquity=0.14114, dividendYield=2.4)
CRDO = yi("Cayman Islands", "USD", "Credo Technology Group Holding ", marketCap=24717555712, netIncomeToCommon=538305024,
          trailingPE=46.63475, priceToBook=9.050305, returnOnEquity=0.30674, dividendYield=0.0)
ARM = yi("United Kingdom", "USD", "Arm Holdings plc", marketCap=203867095040, netIncomeToCommon=936000000, trailingPE=219.0,
         priceToBook=22.43377, returnOnEquity=0.11349, dividendYield=0.0)
TSM = yi("Taiwan", "TWD", "Taiwan Semiconductor Manufactur", marketCap=2068002373632, netIncomeToCommon=2527570952192,
         trailingPE=25.841219, priceToBook=76.09467, returnOnEquity=0.41855, dividendYield=0.95)
LIN = yi("United Kingdom", "USD", "Linde plc", marketCap=241505615872, netIncomeToCommon=7007000064, trailingPE=34.930943,
         priceToBook=6.126166, returnOnEquity=0.17723, dividendYield=1.22)
ACN = yi("Ireland", "USD", "Accenture plc", marketCap=147973832704, netIncomeToCommon=8367055872, trailingPE=18.472713,
         priceToBook=4.725602, returnOnEquity=0.26025, dividendYield=2.73)
AAPL = yi("United States", "USD", "Apple Inc.", marketCap=5177380175872, netIncomeToCommon=132175003648, trailingPE=39.67372,
          priceToBook=46.190845, returnOnEquity=1.42257, dividendYield=0.3)
BPOP = yi("Puerto Rico", "USD", "Popular, Inc.", marketCap=9851592704, netIncomeToCommon=998761024, trailingPE=10.198967,
          priceToBook=1.6019157, returnOnEquity=0.16223, dividendYield=2.28)
# Jack 이 이름으로 넓힌 회사와 나스닥 ADR (2026-11-14 야후 나라 · 재무제표 통화)
NAMED = {"TSM": ("Taiwan", "TWD"), "ASML": ("Netherlands", "EUR"), "BABA": ("China", "CNY"), "NVO": ("Denmark", "DKK"),
         "SHOP": ("Canada", "USD"), "PDD": ("Ireland", "CNY"), "JD": ("China", "CNY"), "BIDU": ("China", "CNY"), "NTES": ("China", "CNY"),
         "ARM": ("United Kingdom", "USD"), "AZN": ("United Kingdom", "USD")}
# S&P 500 회사인데 야후 본사 나라가 미국 밖 (세금 때문에 밖에 본사를 둔 미국 회사 · 2026-11-14 야후 나라)
HOME = {"LIN": "United Kingdom", "MDT": "Ireland", "ACN": "Ireland", "ETN": "Ireland", "JCI": "Ireland", "STX": "Singapore",
        "CB": "Switzerland", "TEL": "Ireland", "ACGL": "Bermuda", "EG": "Bermuda", "WTW": "United Kingdom", "PNR": "United Kingdom"}
# #126 의 21곳 (2026-11-14 야후 나라)
FLOOR = {"BTI": "United Kingdom", "ENB": "Canada", "BCE": "Canada", "TD": "Canada", "RY": "Canada", "SHEL": "United Kingdom",
         "BP": "United Kingdom", "UL": "United Kingdom", "TM": "Japan", "SONY": "Japan", "AZN": "United Kingdom", "HSBC": "United Kingdom",
         "SAP": "Germany", "NVS": "Switzerland", "RIO": "United Kingdom", "BHP": "Australia", "TTE": "France", "DEO": "United Kingdom",
         "BUD": "Belgium", "SAN": "Spain", "GSK": "United Kingdom"}
SP = frozenset(HOME) | {"AAPL", "MSFT", "KO"}


def rec(t, price, info, today=dt.date(2026, 11, 14)):
    r = {"t": t, "nk": t, "ne": t, "cls": "us", "ccy": "USD", "fxu": True, "price": price, "etf": False}
    assert F.apply_us_info(r, dict(info), price, 1333.8, today=today) is True
    return r


# ── 규칙 ──────────────────────────────────────────────────
def test_the_rule_finds_named_companies_and_the_nasdaq_adrs():
    us, infos = [], {}
    for t, (c, fc) in NAMED.items():
        infos[t] = yi(c, fc, t, trailingPE=20.0, priceToBook=2.0, dividendYield=1.0)
        us.append(rec(t, 100.0, infos[t]))
    fs = F.us_foreign_set(us, infos, SP)
    assert set(fs["set"]) == set(NAMED)
    for t, (c, fc) in NAMED.items():
        assert fs["set"][t] == [c, fc, "fcur" if fc != "USD" else "country"], t
    assert fs["home"] == {} and fs["unknown"] == [] and fs["errors"] == []
    json.dumps(fs, allow_nan=False, ensure_ascii=False)


def test_the_rule_finds_all_21_of_pr_126_by_itself():
    us, infos = [], {}
    for t, c in FLOOR.items():
        infos[t] = yi(c, "USD", t)
        us.append(rec(t, 50.0, infos[t]))
    fs = F.us_foreign_set(us, infos, SP)
    assert set(fs["set"]) == set(FLOOR) and all(v[2] == "country" for v in fs["set"].values())   # 바닥(floor) 없이도 모두 찾아요
    for t in FLOOR:                                           # 야후가 나라를 빼먹은 날: 바닥으로 들어가요 (크게 남겨요)
        infos[t].pop("country")
    fs = F.us_foreign_set(us, infos, SP)
    assert set(fs["set"]) == set(FLOOR) and all(v == [None, "USD", "floor"] for v in fs["set"].values())


def test_s_and_p_companies_headquartered_abroad_are_not_foreign():
    us, infos = [], {}
    for t, c in HOME.items():
        infos[t] = yi(c, "USD", t, trailingPE=20.0, priceToBook=3.0, dividendYield=1.5)
        us.append(rec(t, 100.0, infos[t]))
    fs = F.us_foreign_set(us, infos, SP)
    assert fs["set"] == {} and fs["home"] == HOME and fs["unknown"] == []
    # S&P 500 목록을 쓸 수 없는 날 (리뷰 S2): 본사 나라 규칙을 쓰지 않아요 — 21곳 · fcur · 어제 목록만이라 이 회사들은 그대로예요
    fs = F.us_foreign_set(us, infos, None)
    assert fs["set"] == {} and fs["home"] == {} and fs["unknown"] == []


def test_us_puerto_rico_etfs_funds_and_unknown_countries():
    us = [rec("AAPL", 356.27, AAPL), rec("BPOP", 157.88, BPOP), rec("ZZZ", 10.0, yi(None, "USD", "Zed Corp")),
          rec("YYY", 10.0, yi("  ", "USD", "Why Corp")), rec("NANC", 10.0, yi(float("nan"), "USD", "Nan Corp"))]
    spy = {"t": "SPY", "cls": "us", "price": 600.0, "etf": True}
    fund = {"t": "FND", "cls": "us", "price": 6.0, "etf": False, "fund": True}
    infos = {"AAPL": AAPL, "BPOP": BPOP, "ZZZ": yi(None, "USD", "Zed Corp"), "YYY": yi("  ", "USD", "Why Corp"),
             "NANC": yi(float("nan"), "USD", "Nan Corp"), "SPY": yi("Japan", "JPY", "SPDR"), "FND": yi("Japan", "JPY", "Fund")}
    fs = F.us_foreign_set(us + [spy, fund], infos, SP)
    assert fs["set"] == {} and fs["home"] == {}
    assert fs["unknown"] == ["NANC", "YYY", "ZZZ"]           # 나라 모름: 외국 회사로 보지 않고 크게 남겨요 (#114 의 통화 모름과 같은 뜻)
    assert F.us_country({"country": " United   Kingdom "}) == "United Kingdom" and F.us_country({"country": 7}) is None
    assert F.us_country(None) is None


def test_a_depositary_name_counts_and_a_crashing_stock_is_checked():
    adr = yi("United States", "USD", "Example Holdings ADR", trailingPE=10.0)
    ads = yi(None, "USD", "Other Co", listName="Other Co - American Depositary Shares")
    us = [rec("EXA", 10.0, adr), rec("OTH", 10.0, ads)]
    fs = F.us_foreign_set(us, {"EXA": adr, "OTH": ads}, SP)
    assert fs["set"] == {"EXA": ["United States", "USD", "adr"], "OTH": [None, "USD", "adr"]}
    assert F.US_ADR_NAME.search("ADRs of X") and not F.US_ADR_NAME.search("Adrian Steel Inc") and not F.US_ADR_NAME.search("Leadership")

    class Odd(dict):
        def get(self, k, d=None):
            if k == "country":
                raise RuntimeError("시험")
            return super().get(k, d)
    fs = F.us_foreign_set([rec("AAPL", 356.27, AAPL)], {"AAPL": Odd(AAPL)}, SP)
    assert fs["set"] == {"AAPL": [None, None, "error"]} and fs["errors"] == [("AAPL", "RuntimeError")]   # 멈춘 종목은 맞춰 보는 쪽으로


def test_country_due_only_for_companies_outside_the_s_and_p():
    shop = {"at": "2026-11-13", "k": F.US_INFO_SCHEMA, "info": {k: v for k, v in SHOP.items() if k != "country"}}
    assert F.us_country_due(shop, "SHOP", SP) is True
    assert F.us_country_due({"at": "2026-11-13", "k": F.US_INFO_SCHEMA, "info": SHOP}, "SHOP", SP) is False   # 나라가 있어요
    assert F.us_country_due(shop, "LIN", SP) is False                    # S&P 500 회사: 나라가 필요 없어요
    assert F.us_country_due(shop, "SHOP", None) is False                 # S&P 500 목록을 모르면 (시험 · 목록 실패) 다시 받지 않아요
    assert F.us_country_due(shop, "SPY", SP) is False                    # ETF
    assert F.us_country_due({"info": {"quoteType": "ETF"}}, "QQQX", SP) is False and F.us_country_due(None, "SHOP", SP) is False
    assert F.us_country_due({"at": "2026-11-13", "info": {}}, "SHOP", SP) is False      # 회사인지 모르는 빈 항목 (#114 의 시험과 같은 모양)
    assert "country" in F.US_INFO_KEYS and "country" in F.US_INFO_STICKY and F.US_INFO_SCHEMA == 3


# ── 허용 폭 (넓힌 회사에도 같은 값) ─────────────────────────────
def test_the_same_bands_apply_to_newly_covered_companies():
    assert F.US_FOREIGN_BAND == {"per": 1.10, "pbr": 1.35, "dy": 1.10}
    idx = pd.bdate_range("2025-10-01", "2026-11-13")
    zero = pd.Series(0.0, index=idx)
    tri = zero.copy()
    for d, v in (("2025-11-18", 0.595), ("2026-02-17", 0.655), ("2026-05-04", 1.436), ("2026-05-20", 0.655), ("2026-08-19", 0.655)):
        tri[pd.Timestamp(d)] = v
    data = pd.DataFrame({(t, "Dividends"): (tri if t == "TRI" else zero) for t in ("TRI", "NBIS", "CRDO", "SHOP", "ARM", "LIN")})
    out = [rec("TRI", 109.30, TRI), rec("NBIS", 115.88, NBIS), rec("CRDO", 131.51, CRDO), rec("SHOP", 147.09, SHOP), rec("ARM", 190.53, ARM),
           rec("LIN", 526.06, LIN)]
    cache = {t: {"info": i} for t, i in (("TRI", TRI), ("NBIS", NBIS), ("CRDO", CRDO), ("SHOP", SHOP), ("ARM", ARM), ("LIN", LIN))}
    fs = F.us_foreign_set(out, {t: e["info"] for t, e in cache.items()}, SP)
    got = F.us_foreign_check(out, cache, data, dt.date(2026, 11, 13), foreign=frozenset(fs["set"]))
    by = {r["t"]: r for r in out}
    assert got["checked"] == ["ARM", "CRDO", "NBIS", "SHOP", "TRI"] and "LIN" not in fs["set"]
    assert sorted(x[:2] for x in got["cut"]) == [["CRDO", "pbr"], ["NBIS", "pbr"], ["NBIS", "per"], ["TRI", "dy"], ["TRI", "per"]]
    assert by["TRI"]["fgnCut"] == {"dy": "mismatch", "per": "mismatch"} and by["TRI"]["pbr"] == 4.22      # PER 1.15배 · 배당 1.30배 · PBR 맞음
    assert by["NBIS"]["fgnCut"] == {"pbr": "mismatch", "per": "mismatch"} and by["NBIS"]["dy"] == 0.0     # PER 3.01배 · PBR 1.44배
    assert by["CRDO"]["fgnCut"] == {"pbr": "mismatch"} and by["CRDO"]["per"] == 46.6                       # PBR 1.56배 · PER 맞음
    assert (by["SHOP"]["per"], by["SHOP"]["pbr"], by["SHOP"]["dy"]) == (90.2, 14.84, 0.0) and "fgnCut" not in by["SHOP"]
    assert (by["ARM"]["per"], by["ARM"]["pbr"]) == (219.0, 22.43) and "fgnCut" not in by["ARM"]
    assert by["LIN"]["dy"] == 1.22 and "fgnCut" not in by["LIN"]                                           # S&P 500: 검사 밖
    # 경계: 넓힌 회사도 PER 1.08배 남음 · 1.12배 비움, PBR 1.30배 남음 · 1.40배 비움, 배당 1.07배 남음 · 1.17배 비움
    pe_c = SHOP["marketCap"] / SHOP["netIncomeToCommon"]
    imp = pe_c * SHOP["returnOnEquity"]
    for k, fac, cut in (("trailingPE", 1.08, False), ("trailingPE", 1.12, True), ("priceToBook", 1.30, False), ("priceToBook", 1.40, True)):
        base = pe_c if k == "trailingPE" else imp
        info = dict(SHOP, **{k: base * fac})
        r = rec("SHOP", 147.09, info)
        f = "per" if k == "trailingPE" else "pbr"
        assert (f in F.us_foreign_cuts(r, info, 0.0)) is cut, (k, fac)
    for dy, cut in ((3.21, False), (3.51, True)):
        r = {"t": "SHOP", "price": 100.0, "dy": dy}
        assert ("dy" in F.us_foreign_cuts(r, SHOP, 3.0)) is cut, dy
    json.dumps(got, allow_nan=False, ensure_ascii=False)


def test_non_dollar_companies_keep_exactly_the_currency_rule():
    out = [rec("TSM", 398.73, TSM), rec("BTI", 61.89, BTI)]
    cache = {"TSM": {"info": TSM}, "BTI": {"info": BTI}}
    fs = F.us_foreign_set(out, {t: e["info"] for t, e in cache.items()}, SP)
    assert fs["set"] == {"BTI": ["United Kingdom" if "country" in BTI else None, "GBP", "fcur"], "TSM": ["Taiwan", "TWD", "fcur"]}
    got = F.us_foreign_check(out, cache, None, dt.date(2026, 11, 13), foreign=frozenset(fs["set"]))
    assert (got["checked"], got["cut"], got["kind"], got["kept"]) == ([], [], {}, [])
    for r in out:
        assert r["fcur"] in ("TWD", "GBP") and "fgnCut" not in r and not any(k in r for k in ("per", "pbr", "dy"))   # 통화 줄 하나만


# ── fetch_us (가짜 야후) ──────────────────────────────────
def _fake_yf(series, divs, infos, calls, no_div=()):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"] if tickers != F.FX_TICKER else series["_spx"] * 0 + 1333.8})
        cols = {}
        for t in tickers:
            if t not in series:
                continue
            cols[(t, "Close")] = series[t]
            if t in no_div:
                continue                                          # 그 종목의 배당 칸이 다운로드에 없어요 (리뷰 2차 S1)
            dv = pd.Series(0.0, index=series[t].index)
            for d, v in divs.get(t, []):
                dv[pd.Timestamp(d)] = v
            cols[(t, "Dividends")] = dv
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            calls.append(self.t)
            return dict(infos[self.t])
    return types.SimpleNamespace(download=download, Ticker=Ticker)


def _fetch(tmp_path, monkeypatch, sp=SP, infos=None, pre=None, boom=None, sp_min=2, prev=None, extra=None, drop_div=()):
    """가짜 야후로 fetch_us 한 번: AAPL · LIN(S&P 500 · 영국 본사) · SHOP · NBIS · TRI · TSM(대만 달러) · BP(21곳) → (us, meta, 로그, calls)."""
    today = dt.date(2026, 11, 14)
    days = pd.bdate_range(today - dt.timedelta(days=500), dt.date(2026, 11, 13))

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    prices = {"AAPL": 356.27, "LIN": 526.06, "SHOP": 147.09, "NBIS": 115.88, "TRI": 109.30, "TSM": 398.73, "BP": 45.70, **(extra or {})}
    series = {"_spx": walk(1, 6700.0), **{t: walk(i + 2, p) for i, (t, p) in enumerate(prices.items())}}
    divs = {"BP": [("2026-02-20", 0.499), ("2026-05-15", 0.499), ("2026-08-14", 0.52), ("2026-11-13", 0.52)],
            "TRI": [("2025-11-18", 0.595), ("2026-02-17", 0.655), ("2026-05-04", 1.436), ("2026-05-20", 0.655), ("2026-08-19", 0.655)],
            "LIN": [("2026-03-05", 1.5), ("2026-06-04", 1.6)]}                           # 야후 기록이 빠진 S&P 500 회사 (맞춰 보면 비워져요)
    infos = infos or {"AAPL": AAPL, "LIN": LIN, "SHOP": SHOP, "NBIS": NBIS, "TRI": TRI, "TSM": TSM, "BP": dict(BP, country="United Kingdom")}
    calls = []
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series, divs, infos, calls, no_div=set(drop_div)))

    def tickers(names_out=None):
        if isinstance(names_out, F.UsListNames) and sp is not None:
            names_out.sp500 = frozenset(sp)
        return sorted(prices)
    monkeypatch.setattr(F, "us_tickers", tickers)
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: dt.date(2026, 11, 13))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    path = str(tmp_path / "us-info.json.gz")
    monkeypatch.setattr(F, "US_INFO_PATH", path)
    monkeypatch.setattr(F, "US_SP500_MIN", sp_min)          # 가짜 목록은 7종목이라 겹침 기준을 작게 (실제 400)
    monkeypatch.setattr(V, "US_SP500_MIN", sp_min)
    if pre is not None:
        F.save_us_info(pre, path)
    if boom:
        monkeypatch.setattr(F, boom, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("시험")))
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    us, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev_fgn=prev)
    meta.pop("_index")
    return us, meta, lines, calls


def gate(meta, us, mode="publish"):
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": meta["usForeign"]}, us, mode)
    return next(r for r in rep.rows if r[0] == FOREIGN)


def test_fetch_us_checks_the_wider_set_and_the_gate_passes(tmp_path, monkeypatch):
    us, meta, lines, _calls = _fetch(tmp_path, monkeypatch)
    by = {r["t"]: r for r in us}
    uf = meta["usForeign"]
    assert set(uf["set"]) == {"SHOP", "NBIS", "TRI", "TSM", "BP"} and uf["unknown"] == []
    assert uf["set"]["TSM"] == ["Taiwan", "TWD", "fcur"] and uf["set"]["SHOP"] == ["Canada", "USD", "country"]
    assert uf["checked"] == ["BP", "NBIS", "SHOP", "TRI"]
    assert {(t, f) for t, f, _w in uf["cut"]} == {("BP", "pbr"), ("BP", "per"), ("NBIS", "per"), ("NBIS", "pbr"), ("TRI", "per"), ("TRI", "dy")}
    assert by["NBIS"]["fgnCut"] == {"pbr": "mismatch", "per": "mismatch"} and by["TRI"]["fgnCut"] == {"dy": "mismatch", "per": "mismatch"}
    assert (by["SHOP"]["per"], by["SHOP"]["pbr"]) == (90.2, 14.84) and "fgnCut" not in by["SHOP"]
    assert by["LIN"]["dy"] == 1.22 and by["LIN"]["pbr"] == 6.13 and "fgnCut" not in by["LIN"]       # S&P 500: 맞는 수익률을 비우지 않아요
    assert by["TSM"]["fcur"] == "TWD" and "fgnCut" not in by["TSM"] and not any(k in by["TSM"] for k in ("per", "pbr", "dy"))
    assert any(x.startswith("· 미국 상장 외국 회사 (규칙으로 찾음 · S&P 500 목록 15곳은 뺌): 5곳 — 재무제표 통화가 달러가 아님 1") and "SHOP(Canada · USD)" in x
               for x in lines), lines
    assert any(x.startswith("· S&P 500 회사라 외국 회사로 보지 않은 미국 밖 본사 1곳") and x.endswith("LIN(United Kingdom)") for x in lines), lines
    assert any(x.startswith("· S&P 500 밖인데 야후가 본사 나라를 주지 않은 회사 0곳") for x in lines), lines
    r = gate(meta, us)
    assert r[3] == "PASS", r
    assert "외국 회사 5곳 (재무제표 통화가 달러가 아님 1 · 본사 미국 밖 4 · 예탁증서 이름 0 · 손으로 정한 곳 0)" in r[1]
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(us, allow_nan=False, ensure_ascii=False)


def test_a_cached_entry_without_a_country_is_asked_again(tmp_path, monkeypatch):
    """보관본 항목에 나라 칸이 없는 S&P 500 밖 회사는 받은 지 하루여도 다시 받아요 (그 회사들만 · S&P 500 회사는 아니에요)."""
    infos = {"AAPL": AAPL, "LIN": LIN, "SHOP": SHOP, "NBIS": NBIS, "TRI": TRI, "TSM": TSM, "BP": dict(BP, country="United Kingdom")}
    old = {t: {"at": "2026-11-13", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": {k: v for k, v in i.items() if k != "country"}}
           for t, i in infos.items()}
    us, meta, lines, calls = _fetch(tmp_path, monkeypatch, pre=old)
    assert sorted(calls) == ["BP", "NBIS", "SHOP", "TRI", "TSM"]          # AAPL · LIN 은 S&P 500 (어제 받은 것 그대로)
    assert any("본사 나라(country)가 없는 S&P 500 밖 회사 5곳" in x for x in lines), lines
    assert set(meta["usForeign"]["set"]) == {"SHOP", "NBIS", "TRI", "TSM", "BP"}
    back = F.load_us_info(str(tmp_path / "us-info.json.gz"))
    assert back["SHOP"]["info"]["country"] == "Canada" and "country" not in back["LIN"]["info"]


def test_unknown_country_is_kept_and_recorded(tmp_path, monkeypatch):
    infos = {"AAPL": AAPL, "LIN": LIN, "SHOP": {k: v for k, v in SHOP.items() if k != "country"}, "NBIS": NBIS, "TRI": TRI, "TSM": TSM,
             "BP": {k: v for k, v in BP.items() if k != "country"}}
    us, meta, lines, _calls = _fetch(tmp_path, monkeypatch, infos=infos)
    by = {r["t"]: r for r in us}
    assert "SHOP" not in meta["usForeign"]["set"] and meta["usForeign"]["unknown"] == ["SHOP"]
    assert meta["usForeign"]["set"]["BP"] == [None, "USD", "floor"]           # 21곳은 바닥으로 그대로
    assert by["SHOP"]["pbr"] == 14.84 and "fgnCut" not in by["SHOP"]
    assert any(x.startswith("  !! S&P 500 밖인데 야후가 본사 나라를 주지 않은 회사 1곳") and x.endswith("SHOP") for x in lines), lines
    assert any("손으로 정한 목록(US_FOREIGN)으로 넣은 곳 1곳: BP" in x for x in lines), lines
    r = gate(meta, us)
    assert r[3] == "WARN" and "나라를 몰라 외국 회사로 보지 않은 S&P 500 밖 회사 1곳: SHOP" in r[1] and \
        "외국 회사로 보지 않은 ASML·BABA·NVO·SHOP·TSM 중 1곳: SHOP" in r[1], r


def test_a_crashed_check_blanks_the_wider_set_loudly(tmp_path, monkeypatch):
    us, meta, lines, _calls = _fetch(tmp_path, monkeypatch, boom="us_foreign_check")
    by = {r["t"]: r for r in us}
    for t in ("SHOP", "NBIS", "TRI", "BP"):
        assert not any(k in by[t] for k in ("per", "pbr", "dy")), by[t]
        blanked = {f for tt, f, _w in meta["usForeign"]["cut"] if tt == t}
        assert blanked and by[t]["fgnCut"] == {f: "stopped" for f in blanked}, by[t]                  # Q10: 그날의 줄 (co.fgnStopped)
        assert meta["usForeign"]["kind"][t] == by[t]["fgnCut"]
    assert by["LIN"]["pbr"] == 6.13 and by["AAPL"]["pbr"] == 46.19 and by["TSM"]["fcur"] == "TWD"
    assert meta["usForeign"]["checked"] == ["BP", "NBIS", "SHOP", "TRI"] and set(meta["usForeign"]["set"]) == {"SHOP", "NBIS", "TRI", "TSM", "BP"}
    assert all(w == "검사가 멈춤 (RuntimeError)" for _t, _f, w in meta["usForeign"]["cut"])
    assert any(x.startswith("  !! 미국 상장 외국 회사 검사가 멈췄어요 (RuntimeError: 시험)") for x in lines), lines
    r = gate(meta, us)
    assert r[3] == "WARN" and "검사가 멈춰 맞춰 보지 않고 비운 회사 4곳: BP, NBIS, SHOP, TRI (이유 줄: 오늘은 확인하지 못함" in r[1], r
    assert "모양" not in r[1], r


def test_a_crashed_rule_falls_back_to_the_21_fcur_and_yesterday(tmp_path, monkeypatch):
    """리뷰 N1: 판별 전체가 멈추면 21곳 · fcur · 어제 발행한 set 만 — S&P 500 밖 회사 모두로 넓히지 않아요 (맞는 숫자를 비우지 않게)."""
    prev = {"SHOP": ["Canada", "USD", "country"], "GONE": ["Japan", "USD", "country"]}
    us, meta, lines, _calls = _fetch(tmp_path, monkeypatch, boom="us_foreign_set", prev=prev)
    by = {r["t"]: r for r in us}
    uf = meta["usForeign"]
    assert set(uf["set"]) == {"SHOP", "TSM", "BP"} and all(v[2] == "error" for v in uf["set"].values())
    assert uf["checked"] == ["BP", "SHOP"] and "fgnCut" not in by["SHOP"] and by["SHOP"]["pbr"] == 14.84
    assert by["NBIS"]["per"] == 90.5 and "fgnCut" not in by["NBIS"] and by["TRI"]["dy"] == 2.4    # 어제 목록에 없던 회사는 그대로
    assert by["LIN"]["dy"] == 1.22 and by["AAPL"]["pbr"] == 46.19
    assert any(x.startswith("  !! 미국 상장 외국 회사를 찾다가 멈췄어요 (RuntimeError: 시험) → 손으로 정한 21곳") for x in lines), lines
    r = gate(meta, us)
    assert r[3] == "WARN" and "외국 회사인지 보다가 멈춰 맞춰 본 곳 3: BP, SHOP, TSM" in r[1], r


# ── 관문 (실패해야 하는 경우) ─────────────────────────────────
def wide_us():
    return [{"t": "SHEL", "cls": "us", "price": 99.08, "per": 8.6, "pbr": 1.43, "dy": 3.15, "vz": 70},
            {"t": "BP", "cls": "us", "price": 45.7, "dy": 4.55, "fgnCut": {"pbr": "mismatch", "per": "mismatch"}},
            {"t": "BTI", "cls": "us", "price": 61.89, "fcur": "GBP"},
            {"t": "TSM", "cls": "us", "price": 398.73, "fcur": "TWD"},
            {"t": "SHOP", "cls": "us", "price": 147.09, "per": 90.2, "pbr": 14.84, "dy": 0.0, "vz": 10},
            {"t": "NBIS", "cls": "us", "price": 115.88, "dy": 0.0, "fgnCut": {"pbr": "mismatch", "per": "mismatch"}},
            {"t": "LIN", "cls": "us", "price": 526.06, "per": 34.9, "pbr": 6.13, "dy": 1.22, "vz": 40},
            {"t": "SPY", "cls": "us", "price": 600.0, "etf": True}]


def wide_rec():
    """관문에 줄 기록 한 벌 — 스위치(nocmp)는 그때 관문의 값 (리뷰 2차 S2)."""
    return {"checked": ["BP", "NBIS", "SHEL", "SHOP"],
            "cut": [["BP", "pbr", "… (4.32배)"], ["BP", "per", "… (1.70배)"], ["NBIS", "pbr", "… (1.44배)"], ["NBIS", "per", "… (3.01배)"]],
            "set": {"BP": ["United Kingdom", "USD", "country"], "BTI": ["United Kingdom", "GBP", "fcur"],
                    "NBIS": ["Netherlands", "USD", "country"], "SHEL": ["United Kingdom", "USD", "country"],
                    "SHOP": ["Canada", "USD", "country"], "TSM": ["Taiwan", "TWD", "fcur"]},
            "unknown": [], "nocmp": V.US_FGN_NOCMP, "kept": [],
            "kind": {"BP": {"pbr": "mismatch", "per": "mismatch"}, "NBIS": {"pbr": "mismatch", "per": "mismatch"}},
            "sp500": {"n": 503, "inList": 500, "ok": True}}


def run_gate(us, rec_, mode="publish"):
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": rec_}, us, mode)
    return next(r for r in rep.rows if r[0] == FOREIGN)


def test_gate_wide_record_passes():
    r = run_gate(wide_us(), wide_rec())
    assert r[3] == "PASS" and r[1] == ("확인 4곳 · 비운 칸 PER 2 · PBR 2 · 배당 0 (BP, NBIS) · 외국 회사 6곳 (재무제표 통화가 달러가 아님 2 · "
                                       "본사 미국 밖 4 · 예탁증서 이름 0 · 손으로 정한 곳 0)"), r


@pytest.mark.parametrize("change, expect", [
    (lambda us, rec: rec.update(checked=["BP", "NBIS", "SHEL"]), "맞춰 보지 않은 숫자 1곳: SHOP"),     # set 의 회사인데 확인 기록 없음
    (lambda us, rec: us[5].update(per=90.5), "남은 칸 1: NBIS.per"),
    (lambda us, rec: us[5].update(vz=50), "남은 칸 1: NBIS.vz"),
    (lambda us, rec: us[5].pop("fgnCut"), "이유 표시(fgnCut) 없음 2: NBIS.pbr, NBIS.per"),
    (lambda us, rec: us[6].update(fgnCut={"dy": "mismatch"}, dy=None), "LIN.fgnCut (외국 회사 목록 밖이거나 fcur)"),   # S&P 500 회사엔 표시 없음
    (lambda us, rec: rec.update(set=["SHOP"]), "set 모양"),
    (lambda us, rec: rec.update(set=None), "set 모양"),
    (lambda us, rec: rec["set"].update(SHOP=["Canada", "USD"]), "set SHOP"),
    (lambda us, rec: rec["set"].update(SHOP=["Canada", "USD", "hunch"]), "set SHOP"),
    (lambda us, rec: rec["set"].update(SHOP=["Canada", 7, "country"]), "set SHOP"),
    (lambda us, rec: rec["set"].update(SHOP=["Canada", "USD", "fcur"]), "set SHOP (근거 fcur 인데 종목에 fcur 없음)"),
    (lambda us, rec: rec["set"].update(SHOP=["United States", "USD", "country"]), "set SHOP (근거 country 인데 나라 'United States')"),
    (lambda us, rec: rec["set"].update(SHOP=[None, "USD", "country"]), "set SHOP (근거 country 인데 나라 None)"),
    (lambda us, rec: rec["set"].update(SHOP=["Canada", "USD", "floor"]), "set SHOP (근거 floor 인데 21곳 밖)"),
    (lambda us, rec: rec["set"].pop("BP"), "set 에 없는 21곳 · fcur 회사 1: BP"),
    (lambda us, rec: rec["set"].pop("TSM"), "set 에 없는 21곳 · fcur 회사 1: TSM"),
    (lambda us, rec: rec.update(unknown="SHOP"), "unknown 모양"),
])
def test_gate_wide_fails(change, expect):
    us, rec_ = wide_us(), wide_rec()
    change(us, rec_)
    r = run_gate(us, rec_)
    assert r[3] == "FAIL" and expect in r[1], r


def test_gate_wide_unchecked_numbers_fail_in_both_modes():
    """set 의 회사(fcur 없음)에 숫자가 있는데 확인 기록이 없으면 사이트 점검(live) 에서도 실패 — 우리 기록이 어긋난 것 (시장 탓일 수 없어요)."""
    for mode in ("publish", "live"):
        rec_ = wide_rec()
        rec_["checked"].remove("SHOP")
        assert run_gate(wide_us(), rec_, mode)[3] == "FAIL"


@pytest.mark.parametrize("change, expect", [
    (lambda us, rec: rec.update(unknown=["ARGX"]), "나라를 몰라 외국 회사로 보지 않은 S&P 500 밖 회사 1곳: ARGX"),
    (lambda us, rec: rec["set"].update(SHOP=[None, None, "error"]), "외국 회사인지 보다가 멈춰 맞춰 본 곳 1: SHOP"),
    (lambda us, rec: (rec["set"].pop("SHOP"), rec["checked"].remove("SHOP")), "외국 회사로 보지 않은 ASML·BABA·NVO·SHOP·TSM 중 1곳: SHOP"),
])
def test_gate_wide_warns(change, expect):
    us, rec_ = wide_us(), wide_rec()
    change(us, rec_)
    r = run_gate(us, rec_)
    assert r[3] == "WARN" and expect in r[1], r


def test_gate_without_a_set_still_sees_only_the_21():
    """set 이 없는 기록 (이 PR 전 발행본 · 사이트 점검): 예전 그대로 21곳만 봐요 — SHOP 은 확인 기록 없이도 통과, 표시는 21곳에만."""
    rec_ = {k: v for k, v in wide_rec().items() if k in ("checked", "cut")}
    rec_["checked"] = ["BP", "SHEL"]
    rec_["cut"] = rec_["cut"][:2]
    us = [s for s in wide_us() if s["t"] != "NBIS"]
    assert run_gate(us, rec_)[3] == "PASS"
    us.append({"t": "NBIS", "cls": "us", "price": 115.88, "fgnCut": {"per": "mismatch"}})
    r = run_gate(us, rec_)
    assert r[3] == "FAIL" and "NBIS.fgnCut (외국 회사 목록 밖이거나 fcur)" in r[1], r


def test_pipeline_and_gate_spell_the_rule_the_same():
    """관문은 같은 글자를 따로 적어요 (같은 실수를 같이 하지 않게) — 근거 글자 · 미국으로 보는 나라 · 이름으로 넓힌 회사."""
    assert F.US_FGN_BASIS == V.US_FGN_BASIS and set(F.US_HOME) == V.US_FGN_HOME
    assert V.US_FGN_NAMED == {"TSM", "ASML", "BABA", "NVO", "SHOP"} <= set(F.EXTRA_US)
    assert V.US_FOREIGN_SET == set(F.US_FOREIGN) and len(F.US_FOREIGN) == 21                # 바닥 21곳은 그대로


# ── 리뷰 1차: 비운 칸의 종류 (S1 · N3) ─────────────────────────
ALKS = yi("Ireland", "USD", "Alkermes plc", marketCap=6.9e9, netIncomeToCommon=4.4e8, trailingPE=None, priceToBook=4.16,
          returnOnEquity=None, dividendYield=0.0)          # ROE 가 없어요 → PBR 은 맞춰 볼 수 없음 (야후 4.16 은 맞아 보여요)


def _div_data(tickers, idx_end="2026-11-13"):
    idx = pd.bdate_range("2025-10-01", idx_end)
    return pd.DataFrame({(t, "Dividends"): pd.Series(0.0, index=idx) for t in tickers})


LOSS = yi("Netherlands", "USD", "Loss With PE N.V.", marketCap=5e9, netIncomeToCommon=-2e8, trailingPE=25.0, priceToBook=3.0,
          returnOnEquity=-0.05, dividendYield=0.0)   # 순이익은 0 이하인데 야후 PER 은 양수 — 부호가 어긋나요 (맞지 않음 · 리뷰 2차 S1)


@pytest.mark.parametrize("switch", SWITCHES)
def test_each_blank_records_its_kind(monkeypatch, switch):
    """종류: mismatch (맞춰 봤는데 달라요 · 부호가 어긋남) · norecord (배당 기록이 없는 배당수익률 — 스위치와 상관없이 늘 비워요) · 스위치가 정하는
    nocompare (회사 숫자로 PER · PBR 을 맞춰 볼 수 없음: 적자 · ROE 없음). 스위치 값마다 한 번씩."""
    set_switch(monkeypatch, switch)
    out = [rec("ALKS", 41.0, ALKS), rec("NBIS", 115.88, NBIS), rec("SHOP", 147.09, SHOP), rec("LOSS", 50.0, LOSS)]
    cache = {t: {"info": i} for t, i in (("ALKS", ALKS), ("NBIS", NBIS), ("SHOP", SHOP), ("LOSS", LOSS))}
    got = F.us_foreign_check(out, cache, _div_data(["ALKS", "NBIS", "LOSS"]), dt.date(2026, 11, 13), foreign=frozenset(cache))
    by = {r["t"]: r for r in out}
    nk = V.US_FGN_NOCMP_KIND[switch]
    assert by["NBIS"]["fgnCut"] == {"pbr": "mismatch", "per": "mismatch"}                           # 맞춰 봤는데 달라요
    # N3 · 2차 S1: SHOP 은 다운로드에 배당 칸이 없어요 → 0.00% 도 확인하지 못해 비워요 (norecord · 어느 스위치든)
    assert by["SHOP"]["fgnCut"] == {"dy": "norecord"} and "dy" not in by["SHOP"] and by["SHOP"]["pbr"] == 14.84
    assert by["LOSS"]["fgnCut"].get("per") == "mismatch" and "per" not in by["LOSS"]                 # 부호가 어긋난 PER 은 맞지 않음
    if nk is None:                                                                                    # keep: 회사 숫자로 맞춰 볼 수 없는 PBR 은 그대로
        assert by["ALKS"]["pbr"] == 4.16 and "fgnCut" not in by["ALKS"] and by["LOSS"]["pbr"] == 3.0
        assert sorted(x[:2] for x in got["kept"]) == [["ALKS", "pbr"], ["LOSS", "pbr"]]
        assert by["LOSS"]["fgnCut"] == {"per": "mismatch"}
    else:
        assert by["ALKS"]["fgnCut"] == {"pbr": nk} and "pbr" not in by["ALKS"] and got["kept"] == []
        assert by["LOSS"]["fgnCut"] == {"per": "mismatch", "pbr": nk}
    assert got["kind"] == {t: r["fgnCut"] for t, r in by.items() if "fgnCut" in r} and got["nocmp"] == switch
    assert [x for x in got["cut"] if x[0] == "SHOP"] == [["SHOP", "dy", "배당 기록(야후 다운로드의 Dividends 칸) · 가격을 읽지 못함"]]
    assert next(x[2] for x in got["cut"] if x[:2] == ["LOSS", "per"]).endswith("부호가 맞지 않음")
    assert F.us_fgn_kind("pbr", F.US_FGN_NOCMP_WHY["pbr"], switch) == nk
    assert F.us_fgn_kind("dy", V.US_FGN_NOREC_WHY, switch) == "norecord"
    assert F.us_fgn_kind("pbr", "재무제표 통화를 모름 (야후 financialCurrency None — 달러로 확인되지 않음)", switch) == "currency"
    assert F.us_fgn_kind("dy", F.US_FGN_NOCMP_WHY["pbr"], switch) == "mismatch"                     # 다른 칸의 사유 글이면 맞춰 본 것
    assert F.us_fgn_kind("per", "주가 ÷ 주당순이익 22.29 ↔ 시가총액 ÷ 순이익 13.14 (1.70배)", switch) == "mismatch"
    json.dumps(got, allow_nan=False, ensure_ascii=False)


@pytest.mark.parametrize("switch", SWITCHES)
def test_every_switch_value_publishes_through_the_gate(tmp_path, monkeypatch, switch):
    """리뷰 2차 S2: 스위치를 바꾸면 (한 줄) 파이프라인 · 관문이 같은 값을 따라 발행이 지나가요. 회사 숫자로 맞춰 볼 수 없는 PBR (ALKS) 만 달라지고,
    배당 기록이 빠진 배당수익률은 어느 값이든 비고 관문이 경고해요."""
    set_switch(monkeypatch, switch)
    infos = {"AAPL": AAPL, "LIN": LIN, "SHOP": SHOP, "NBIS": NBIS, "TRI": TRI, "TSM": TSM, "BP": dict(BP, country="United Kingdom"),
             "ALKS": ALKS}
    us, meta, _lines, _calls = _fetch(tmp_path, monkeypatch, infos=infos, extra={"ALKS": 41.0}, drop_div={"BP"})
    by = {r["t"]: r for r in us}
    uf = meta["usForeign"]
    nk = V.US_FGN_NOCMP_KIND[switch]
    assert uf["nocmp"] == switch and by["BP"]["fgnCut"].get("dy") == "norecord" and "dy" not in by["BP"]
    assert (by["ALKS"].get("pbr") == 4.16) is (nk is None) and by["ALKS"].get("fgnCut") == ({"pbr": nk} if nk else None)
    assert uf["kept"] == ([["ALKS", "pbr", V.US_FGN_NOCMP_WHY["pbr"]]] if nk is None else [])
    r = gate(meta, us)
    assert r[3] == "WARN" and "배당 기록 · 가격을 읽지 못해 비운 배당수익률 1곳: BP" in r[1], r
    assert ("모양" not in r[1]) and "맞춰 보지 않은" not in r[1], r


def test_the_switch_keep_leaves_nothing_to_compare_numbers_and_own_marks_them_apart():
    for mode, alks, kind in (("keep", 4.16, {"NBIS": {"pbr": "mismatch", "per": "mismatch"}}),
                             ("own", None, {"ALKS": {"pbr": "nocompare-own"}, "NBIS": {"pbr": "mismatch", "per": "mismatch"}})):
        out = [rec("ALKS", 41.0, ALKS), rec("NBIS", 115.88, NBIS)]
        cache = {"ALKS": {"info": ALKS}, "NBIS": {"info": NBIS}}
        got = F.us_foreign_check(out, cache, _div_data(["ALKS", "NBIS"]), dt.date(2026, 11, 13), foreign=frozenset({"ALKS", "NBIS"}), nocmp=mode)
        by = {r["t"]: r for r in out}
        assert by["ALKS"].get("pbr") == alks and got["kind"] == kind and got["nocmp"] == mode, (mode, got)
        assert "per" not in by["NBIS"] and "pbr" not in by["NBIS"]                                    # 맞지 않는 숫자는 어느 쪽이든 비워요
        assert got["kept"] == ([["ALKS", "pbr", F.US_FGN_NOCMP_WHY["pbr"]]] if mode == "keep" else [])
        assert ("fgnCut" in by["ALKS"]) is (mode == "own")


def test_one_switch_for_pipeline_and_gate():
    """스위치는 관문 파일에 하나 (파이프라인은 그 값을 가져다 써요). copy 의 줄 확인은 node 로 tests/test_us_foreign_wide_app.py 가 해요."""
    assert CONFIGURED in V.US_FGN_NOCMP_KIND                                                        # 고정 장치 밖의 진짜 값 (파일을 읽을 때)
    assert F.US_FGN_NOCMP_WHY is V.US_FGN_NOCMP_WHY and F.US_FOREIGN_CUR_WHY == V.US_FGN_CUR_WHY
    assert F.US_FGN_NOREC_WHY == V.US_FGN_NOREC_WHY and F.US_FGN_NOREC == V.US_FGN_NOREC == "norecord"
    assert V.US_FGN_NOCMP_KIND == {"line": "nocompare", "keep": None, "own": "nocompare-own"}
    assert V.US_FGN_WHY == ("mismatch", "currency")                                                 # #126 의 두 가지는 그대로
    assert set(V.US_FGN_NOCMP_WHY) == {"per", "pbr"}                                                # 배당수익률은 스위치 밖 (norecord)


# ── 리뷰 1차: S&P 500 목록 (S2 · N4) ───────────────────────────
class _FDR:
    def __init__(self, sp=None, nasdaq=None, fail=()):
        self.sp, self.nasdaq, self.fail = sp, nasdaq, set(fail)

    def StockListing(self, name):
        if name in self.fail:
            raise RuntimeError("목록 실패 (시험)")
        return self.sp if name == "S&P500" else self.nasdaq


def test_us_tickers_captures_the_s_and_p_list(monkeypatch):
    sp = pd.DataFrame({"Symbol": ["AAPL", "BRK.B", "LIN", " MDT "], "Name": ["Apple", "Berkshire B", "Linde", "Medtronic"]})
    nq = pd.DataFrame({"Symbol": ["SHOP", "ARM"], "Name": ["Shopify", "Arm Holdings plc - American Depositary Shares"]})
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    monkeypatch.setitem(sys.modules, "FinanceDataReader", _FDR(sp, nq))
    names = F.UsListNames()
    syms = F.us_tickers(names)
    assert names.sp500 == frozenset({"AAPL", "BRK-B", "LIN", "MDT"})                    # BRK.B → BRK-B (오늘 목록과 같은 모양)
    assert {"AAPL", "BRK-B", "LIN", "MDT", "SHOP", "ARM"} <= set(syms) and names["ARM"].endswith("American Depositary Shares")
    names = F.UsListNames()
    monkeypatch.setitem(sys.modules, "FinanceDataReader", _FDR(sp, nq, fail={"S&P500"}))
    F.us_tickers(names)
    assert names.sp500 is None and any("S&P500 목록 실패" in x for x in lines)               # 읽지 못하면 None (믿지 않아요)
    plain = {}
    monkeypatch.setitem(sys.modules, "FinanceDataReader", _FDR(sp, nq))
    F.us_tickers(plain)                                                                  # dict 를 넘기면 예전 그대로 (이름만)
    assert plain["LIN"] == "Linde" and not hasattr(plain, "sp500")


def test_an_unusable_s_and_p_list_turns_the_country_rule_off(tmp_path, monkeypatch):
    """리뷰 S2: 목록이 없거나 오늘 목록과 US_SP500_MIN 곳 아래로 겹치면 (칸 이름이 바뀌어 티커 대신 이름이 들어온 날) 본사 나라 규칙을 쓰지
    않아요 — 21곳 · fcur · 어제 발행한 set 만. 그날은 크게 남기고 관문이 경고해요."""
    prev = {"SHOP": ["Canada", "USD", "country"], "NBIS": ["Netherlands", "USD", "country"]}
    big = frozenset(SP | {f"Z{i:03d}" for i in range(600)})                                    # 2차 N3: S&P 500 이 아닌 큰 목록 (615곳)
    for sp, sp_min in ((frozenset({"Apple Inc.", "Linde plc"}), 2), (SP, 3), (None, 2), (big, 2)):   # 이름이 들어온 목록 · 겹침 2 < 3 · 목록 없음 · 너무 큼
        us, meta, lines, _calls = _fetch(tmp_path, monkeypatch, sp=sp, sp_min=sp_min, prev=prev)
        by = {r["t"]: r for r in us}
        uf = meta["usForeign"]
        assert uf["sp500"]["ok"] is False and (uf["sp500"]["inList"] < sp_min or uf["sp500"]["n"] > V.US_SP500_MAX), uf["sp500"]
        assert uf["set"] == {"BP": ["United Kingdom", "USD", "floor"], "NBIS": ["Netherlands", "USD", "prev"],
                             "SHOP": ["Canada", "USD", "prev"], "TSM": ["Taiwan", "TWD", "fcur"]}, uf["set"]
        assert by["TRI"]["dy"] == 2.4 and "fgnCut" not in by["TRI"]                     # 어제 목록에 없던 회사는 그날 그대로
        assert by["LIN"]["dy"] == 1.22 and "fgnCut" not in by["LIN"]                     # S&P 500 회사의 맞는 수익률을 비우지 않아요
        assert by["NBIS"]["fgnCut"] == {"pbr": "mismatch", "per": "mismatch"}
        assert any(x.startswith("  !! S&P 500 목록을 쓸 수 없어요") for x in lines), lines
        r = gate(meta, us)
        assert r[3] == "WARN" and "S&P 500 목록을 쓸 수 없던 날" in r[1], r
    us, meta, _l, _c = _fetch(tmp_path, monkeypatch, sp=SP, sp_min=2)
    assert meta["usForeign"]["sp500"] == {"n": 15, "inList": 2, "ok": True} and gate(meta, us)[3] == "PASS"


def test_a_cut_short_yahoo_name_still_says_depositary():
    """리뷰 N4: 야후 짧은 이름은 31자에서 잘려요 — 나라가 빠진 날에도 'American D…' 로 끝나면 예탁증서예요."""
    bz = yi(None, "USD", "KANZHUN LIMITED - American D")
    out = [rec("BZQ", 20.0, bz), rec("AMD2", 20.0, yi(None, "USD", "American Dynamics Corp"))]
    fs = F.us_foreign_set(out, {"BZQ": bz, "AMD2": yi(None, "USD", "American Dynamics Corp")}, SP)
    assert fs["set"] == {"BZQ": [None, "USD", "adr"]} and fs["unknown"] == ["AMD2"]
    for n in ("KANZHUN LIMITED - American D", "X Holdings - American Depos", "Y plc ADS", "Z ADRs",
              "KANZHUN LIMITED - Americ", "KANZHUN LIMITED - American", "Q Group Ltd - Am"):                 # 2차 N4: ' - Americ' 까지
        assert F.US_ADR_NAME.search(n), n
    for n in ("American Dynamics", "American Dream Co", "Leadership Inc", "Adrian Steel", "Bank of America", "Bank of America Corp",
              "Foo - Amazon Partners"):
        assert not F.US_ADR_NAME.search(n), n


# ── 리뷰 1차: 관문 (종류 · 스위치 · S&P 500 기록) ───────────────────
def nocmp_us():
    us = wide_us() + [{"t": "ALKS", "cls": "us", "price": 41.0, "dy": 0.0, "fgnCut": {"pbr": "nocompare"}}]
    return us


def nocmp_rec():
    r = wide_rec()
    r["checked"].append("ALKS")
    r["cut"].append(["ALKS", "pbr", V.US_FGN_NOCMP_WHY["pbr"]])
    r["set"]["ALKS"] = ["Ireland", "USD", "country"]
    r["kind"]["ALKS"] = {"pbr": "nocompare"}
    return r


def test_gate_accepts_nothing_to_compare_blanks_and_names_them():
    r = run_gate(nocmp_us(), nocmp_rec())
    assert r[3] == "PASS" and "맞춰 볼 값이 없어 비운 칸 1 (스위치 line): ALKS.pbr" in r[1], r


@pytest.mark.parametrize("change, expect", [
    (lambda us, rec: us[-1].update(fgnCut={"pbr": "mismatch"}), "종류 ALKS.pbr mismatch ≠ nocompare"),        # 맞춰 보지 않았는데 '맞지 않음'
    (lambda us, rec: us[5].update(fgnCut={"pbr": "nocompare", "per": "mismatch"}), "종류 NBIS.pbr nocompare ≠ mismatch"),
    (lambda us, rec: us[-1].update(fgnCut={"pbr": "nocompare-own"}), "모양"),                                  # 스위치 line 에는 없는 종류
    (lambda us, rec: rec["kind"].pop("ALKS"), "kind ≠ 종목 표시 1: ALKS"),
    (lambda us, rec: rec.update(kind=[]), "kind 모양"),
    (lambda us, rec: rec.update(nocmp="maybe"), 'nocmp "maybe"'),
    (lambda us, rec: rec.update(nocmp=["line"]), 'nocmp ["line"]'),                                    # 리뷰 2차 N1: 멈추지 않고 실패 줄
    (lambda us, rec: rec.update(nocmp={"v": "line"}), 'nocmp {"v": "line"}'),
    (lambda us, rec: rec.update(nocmp="keep"), "nocmp keep (관문 스위치 line)"),                                # 발행: 관문의 스위치를 따라야 해요
    (lambda us, rec: rec.update(kept=[["ALKS", "pbr", V.US_FGN_NOCMP_WHY["pbr"]]]), "kept ALKS.pbr (스위치 line)"),
    (lambda us, rec: rec.update(kept=[["ALKS", "pbr", "x"]]), "kept 줄"),
    (lambda us, rec: rec.update(kept="ALKS"), "kept 모양"),
    (lambda us, rec: rec.update(sp500={"n": 503, "inList": 500}), "sp500 모양"),
    (lambda us, rec: rec.pop("sp500"), "sp500 모양"),
    (lambda us, rec: rec.update(sp500={"n": 503, "inList": 120, "ok": True}), "sp500 ok True (목록 503 · 겹침 120"),
    (lambda us, rec: rec.update(sp500={"n": 2400, "inList": 500, "ok": True}), "sp500 ok True (목록 2400 · 겹침 500"),   # 2차 N3: 너무 큰 목록
    (lambda us, rec: us[-1].update(fgnCut={"pbr": "norecord"}), "종류 ALKS.pbr norecord ≠ nocompare"),
    (lambda us, rec: (rec["cut"].append(["SHOP", "dy", V.US_FGN_NOREC_WHY]), us[4].update(dy=None, fgnCut={"dy": "nocompare"}),
                      rec["kind"].update(SHOP={"dy": "nocompare"})), "종류 SHOP.dy nocompare ≠ norecord"),
    (lambda us, rec: rec.update(kept=[["SHOP", "dy", V.US_FGN_NOREC_WHY]]), "kept 줄"),               # 배당 기록 없음은 스위치 밖
    (lambda us, rec: rec.update(sp500={"n": None, "inList": 0, "ok": False}), "sp500 을 못 믿은 날인데 근거 country · adr"),
    (lambda us, rec: rec["set"].update(SHOP=["Canada", "USD", "prev"]), "sp500 을 믿은 날인데 근거 prev"),
])
def test_gate_kind_switch_and_list_fail(change, expect):
    us, rec_ = nocmp_us(), nocmp_rec()
    change(us, rec_)
    r = run_gate(us, rec_)
    assert r[3] == "FAIL" and expect in r[1], r


def test_gate_follows_the_switch(monkeypatch):
    """스위치를 바꾸면 (Jack 의 답) 관문도 같은 값을 봐요: keep 이면 비우지 않은 칸은 kept 에, 표시는 없어요. 사이트 점검은 어제 파일의 스위치를 그대로 봐요."""
    keep = nocmp_rec()
    keep.update(nocmp="keep", kept=[["ALKS", "pbr", V.US_FGN_NOCMP_WHY["pbr"]]])
    keep["cut"] = [x for x in keep["cut"] if x[0] != "ALKS"]
    keep["kind"].pop("ALKS")
    us = [s for s in wide_us()] + [{"t": "ALKS", "cls": "us", "price": 41.0, "pbr": 4.16, "dy": 0.0}]
    assert run_gate(us, keep)[3] == "FAIL"                                       # 관문 스위치는 line
    assert run_gate(us, keep, mode="live")[3] == "PASS"                           # 사이트 점검: 그 파일의 스위치
    monkeypatch.setattr(V, "US_FGN_NOCMP", "keep")
    r = run_gate(us, keep)
    assert r[3] == "PASS" and "맞춰 볼 값이 없어 비우지 않은 칸 1 (스위치 keep)" in r[1], r
    us[-1]["fgnCut"] = {"pbr": "nocompare"}
    assert run_gate(us, keep)[3] == "FAIL"                                       # keep 인데 표시가 남음
    monkeypatch.setattr(V, "US_FGN_NOCMP", "own")
    own = nocmp_rec()
    own["nocmp"], own["kind"]["ALKS"] = "own", {"pbr": "nocompare-own"}
    usn = nocmp_us()
    usn[-1]["fgnCut"] = {"pbr": "nocompare-own"}
    assert run_gate(usn, own)[3] == "PASS"


def test_gate_warns_on_every_yield_blanked_for_lack_of_a_dividend_record():
    """리뷰 2차 S1: 배당 기록 · 가격을 읽지 못해 비운 배당수익률은 우리 쪽 자료가 빠진 날이에요 — 하루 통째로 빠지면 40곳쯤이 조용히 비어요.
    그래서 늘 경고해요 (수와 이름) · set 이 없는 예전 기록도."""
    old = {"checked": ["BP", "SHEL"], "cut": [["BP", "pbr", "…"], ["BP", "per", "…"], ["SHEL", "dy", V.US_FGN_NOREC_WHY]]}
    us = [{"t": "SHEL", "cls": "us", "price": 99.08, "per": 8.6, "pbr": 1.43, "vz": 70, "fgnCut": {"dy": "mismatch"}},
          {"t": "BP", "cls": "us", "price": 45.7, "dy": 4.55, "fgnCut": {"pbr": "mismatch", "per": "mismatch"}}]
    r = run_gate(us, old)
    assert r[3] == "WARN" and "배당 기록 · 가격을 읽지 못해 비운 배당수익률 1곳: SHEL" in r[1], r
    new = wide_rec()
    new["cut"].append(["SHOP", "dy", V.US_FGN_NOREC_WHY])
    new["kind"]["SHOP"] = {"dy": "norecord"}
    usw = wide_us()
    usw[4].update(dy=None, fgnCut={"dy": "norecord"})
    r = run_gate(usw, new)
    assert r[3] == "WARN" and "배당 기록 · 가격을 읽지 못해 비운 배당수익률 1곳: SHOP" in r[1], r


# ── Jack, 2026-11-15 (Q10): 검사가 멈춘 날의 표시 stopped ─────────────────
def crash_rec_us():
    rec_ = wide_rec()
    rec_["cut"] = [["BP", "pbr", "… (4.32배)"], ["BP", "per", "… (1.70배)"]] + \
        [[t, f, "검사가 멈춤 (RuntimeError)"] for t in ("NBIS", "SHEL", "SHOP") for f in ("per", "pbr", "dy")]
    us = wide_us()
    for s_ in us:
        if s_["t"] in ("NBIS", "SHEL", "SHOP"):
            for f in ("per", "pbr", "dy", "vz"):
                s_.pop(f, None)
            s_["fgnCut"] = {"per": "stopped", "pbr": "stopped", "dy": "stopped"}
    rec_["kind"] = {"BP": {"pbr": "mismatch", "per": "mismatch"}, **{t: {"per": "stopped", "pbr": "stopped", "dy": "stopped"}
                                                                  for t in ("NBIS", "SHEL", "SHOP")}}
    return us, rec_


def test_gate_accepts_a_crash_day_with_its_marks_and_warns():
    us, rec_ = crash_rec_us()
    r = run_gate(us, rec_)
    assert r[3] == "WARN" and "검사가 멈춰 맞춰 보지 않고 비운 회사 3곳: NBIS, SHEL, SHOP (이유 줄: 오늘은 확인하지 못함" in r[1], r


@pytest.mark.parametrize("change, expect", [
    (lambda us, rec: (us[0].pop("fgnCut"), rec["kind"].pop("SHEL")), "멈춘 날 표시 SHEL.per null ≠ stopped"),     # 멈춘 칸인데 표시가 없음
    (lambda us, rec: (us[0]["fgnCut"].update(per="mismatch"), rec["kind"]["SHEL"].update(per="mismatch")), '멈춘 날 표시 SHEL.per "mismatch" ≠ stopped'),
    (lambda us, rec: (us[1]["fgnCut"].update(pbr="stopped"), rec["kind"]["BP"].update(pbr="stopped")), "종류 BP.pbr stopped ≠ mismatch"),
    (lambda us, rec: rec.pop("nocmp"), "모양"),                                                   # 이 칸 전 모양의 기록엔 stopped 표시가 없어요
])
def test_gate_crash_day_marks_fail(change, expect):
    us, rec_ = crash_rec_us()
    change(us, rec_)
    r = run_gate(us, rec_)
    assert r[3] == "FAIL" and expect in r[1], r
