# -*- coding: utf-8 -*-
"""2026-11-20 (Jack, verbatim): "Also: US stocks carry like Korean ones. A US stock with no close from Yahoo carries its last
confirmed close with its own date and the same line. Block only if many are missing (set the number from history), so a Yahoo gap
never stops the Korean data again."

여기서 보는 것 (네트워크 없음 · 더한 시험만):
- 파이프라인: 미국 기준일 종가가 야후에 없는 종목 (빈 값 · 0 · 음수 · 가격 없음)을 지난 발행본의 마지막 확인 종가로
  (fetch_data.us_own_close_carry · us_own_close_step · fetch_us) — pxd = 그 발행본의 usPxDate · pxc = true · d1 없음 · 이미 pxc 면 같은 가격 ·
  같은 pxd · 같은 usPxDate 로 다시 발행하면 그날 종가와 d1 그대로 (same) · 나이 상한 5 미국 거래일 (추수감사절 포함) · 넘으면 빼고 aged ·
  거래 정지(pxc 없는 pxd)와 새 종목은 예전 그대로 · 이 단계의 오류는 발행을 멈추지 않아요 · 0 종가는 가격 0 인 행이 되지 않아요
- 관문: '미국 d1 채움' 은 마지막 확인 종가로 싣지 못한 종목이 N(5)을 넘을 때만 실패 · 깨끗한 마지막 확인 종가만 오늘 가격 줄에서 빠져요
  (지난 발행본의 가격 · 날짜 그대로) · 날짜가 깨졌거나 d1 이 옆에 있으면 실패 · 거른 행이 한 점검에 5 넘으면 실패
- 2026-11-20 의 모양 (야후의 최신 봉이 많이 빔): 발행이 경고로 통과해요 (실제 하루치 발행을 줄인 사본 tests/fixtures/snapshot 으로)
- 앱: 2.0 · 예전 뱁새가 미국 마지막 확인 종가에 Jack 의 줄을 그대로 쓰는지 · 거래 정지 미국 pxd 는 예전 그대로 · 늦은 데이터 점검의 상한 (NYSE 거래일)
"""
import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

JACK = "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
JACK_LIST = "{names}: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
JACK_EN = "We couldn't confirm today's close, so this shows the {date} close."
JACK_AGED = "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요."
# 미국 거래일 (S&P 500 일봉 날짜 · 2026-11-26 추수감사절은 휴장)
UDAYS = ["2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24",
         "2026-11-25", "2026-11-27", "2026-11-30", "2026-12-01"]
D18, D19, D20 = "2026-11-18", "2026-11-19", "2026-11-20"


def us(t, **kw):
    s = {"t": t, "nk": t + " Inc.", "ne": t + " Inc.", "cls": "us", "ccy": "USD", "fxu": True, "s": "tech", "etf": False, "d1": 0.5,
         "price": 100.0, "vol": 30.0, "beta": 1.1, "al": 2.0, "betaSE": 0.05, "betaN": 700, "lo": 80.0, "hi": 120.0, "sh": 0.6,
         "mdd": -30.0, "hit": 55, "mom": 12.0, "per": 25.0, "pbr": 5.0, "dy": 0.5, "cap": 3000.0, "val": 9000.0, "pz": 40, "vz": 30,
         "mz": 60, "qz": 70, "lz": 50}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def prev_file(stocks, usd=D19, aged=None):
    out = {"pxDate": usd, "usPxDate": usd, "stocks": stocks}
    if aged is not None:
        out["usSrc"] = {"v": 1, "own": {"v": 1, "n": 0, "codes": [], "same": [], "aged": aged}}
    return out


# ── 1. 파이프라인 ─────────────────────────────────────────────────────────────
def test_tail_clean_treats_zero_negative_and_infinite_last_bars_as_no_close():
    idx = pd.to_datetime(["2026-11-17", "2026-11-18", "2026-11-19"])
    s = lambda *v: pd.Series(list(v), index=idx, dtype=float)
    assert list(F.us_px_tail_clean(s(1.0, 2.0, 0.0)).values) == [1.0, 2.0]
    assert list(F.us_px_tail_clean(s(1.0, -2.0, np.inf)).values) == [1.0]
    assert list(F.us_px_tail_clean(s(1.0, 0.0, 2.0)).values) == [1.0, 0.0, 2.0]          # 가운데 봉은 그대로 (깨진 봉 검사가 따로 봐요)
    assert len(F.us_px_tail_clean(s(0.0, 0.0, 0.0))) == 0


def test_carried_from_a_confirmed_previous_publish_with_its_own_date_and_mark():
    p = us("AAPL", price=270.12, d1=-1.4)
    carried, same, drop = F.us_own_close_carry(prev_file([p]), {"AAPL": "bar"}, dt.date(2026, 11, 20), UDAYS)
    assert drop == {} and same == [] and len(carried) == 1
    r = carried[0]
    assert r["pxd"] == D19 and r["pxc"] is True and r["price"] == 270.12 and "d1" not in r     # 그 발행본의 가격 · 그 날짜 · 오늘 변화 없음
    assert set(r) <= set(F.US_OWN_KEYS) | {"t", "nk", "ne", "cls", "ccy", "fxu", "s", "etf", "pxd", "pxc"}
    assert not {"per", "pbr", "dy", "cap", "val", "pz", "vz", "mz", "qz", "lz"} & set(r)       # 상세 정보 · 점수는 오늘 그 가격으로 다시
    for k in ("vol", "beta", "al", "betaSE", "betaN", "lo", "hi", "sh", "mdd", "hit", "mom"):
        assert r[k] == p[k], k                                                                   # 그 종가까지의 시계열로 그날 만든 숫자 그대로


def test_a_chain_keeps_price_and_pxd_never_redated():
    p = us("MSFT", price=410.0, d1=None, pxd=D18, pxc=True)
    carried, same, drop = F.us_own_close_carry(prev_file([p], usd=D19), {"MSFT": "bar"}, dt.date(2026, 11, 20), UDAYS)
    assert drop == {} and carried[0]["pxd"] == D18 and carried[0]["price"] == 410.0 and carried[0]["pxc"] is True


def test_same_day_republish_keeps_that_days_close_and_change():
    """2026-11-20 의 시험 실행들: 지난 발행본(07:00 KST)이 이미 usPxDate 11-19 였고, 그 뒤 야후가 11-19 봉을 비웠어요 — 그날의 확인된 종가예요."""
    p = us("SHEL", price=71.2, d1=0.8)
    carried, same, drop = F.us_own_close_carry(prev_file([p], usd=D19), {"SHEL": "bar"}, dt.date(2026, 11, 19), UDAYS)
    assert carried == [] and drop == {} and len(same) == 1
    assert same[0]["price"] == 71.2 and same[0]["d1"] == 0.8 and "pxd" not in same[0] and "pxc" not in same[0]


def test_halted_new_and_unreadable_stay_as_before():
    rows = [us("HALT", d1=None, pxd="2026-11-10"), us("ZERO", price=0.0), us("ODD", d1=None, pxc=True)]
    carried, same, drop = F.us_own_close_carry(prev_file(rows), {"HALT": "bar", "NEW": "bar", "ZERO": "bar", "ODD": "bar"},
                                               dt.date(2026, 11, 20), UDAYS)
    assert carried == [] and same == []
    assert drop == {"HALT": "halt", "NEW": "none", "ZERO": "bad", "ODD": "bad"}       # 예전 그대로 (야후의 마지막 봉이 있으면 그 날짜)


def test_age_limit_counts_nyse_trading_days_across_thanksgiving():
    p = us("NVDA", price=180.0, d1=None, pxd=D19, pxc=True)
    prev = prev_file([p], usd="2026-11-25")
    ok, _s, d1 = F.us_own_close_carry(prev, {"NVDA": "bar"}, dt.date(2026, 11, 27), UDAYS)   # 11-20 · 23 · 24 · 25 · 27 = 5 (11-26 휴장)
    old, _s, d2 = F.us_own_close_carry({**prev, "usPxDate": "2026-11-27"}, {"NVDA": "bar"}, dt.date(2026, 11, 30), UDAYS)   # 6
    assert len(ok) == 1 and d1 == {} and ok[0]["pxd"] == D19
    assert old == [] and d2 == {"NVDA": "old"}
    weekdays = [d for d in pd.bdate_range(D19, "2026-11-27").strftime("%Y-%m-%d") if d > D19]
    assert len(weekdays) == 6                                                          # 휴장일을 세면 하루 일찍 빠졌을 거예요


def test_aged_record_written_kept_and_dropped():
    p = us("NVDA", price=180.0, d1=None, pxd=D19, pxc=True)
    prev = prev_file([p], usd="2026-11-27")
    _c, _s, drop = F.us_own_close_carry(prev, {"NVDA": "bar"}, dt.date(2026, 11, 30), UDAYS)
    aged = F.us_own_aged(prev, {"NVDA": "bar"}, drop)
    assert aged == [{"t": "NVDA", "nk": "NVDA Inc.", "pxd": D19}] and drop == {"NVDA": "old"}
    nxt = prev_file([], usd="2026-11-30", aged=aged)                                  # 다음 실행: 지난 발행본의 stocks 에는 없어요
    _c, _s, drop2 = F.us_own_close_carry(nxt, {"NVDA": "empty"}, dt.date(2026, 12, 1), UDAYS)
    assert F.us_own_aged(nxt, {"NVDA": "empty"}, drop2) == aged and drop2 == {"NVDA": "old"}
    assert F.us_own_aged(nxt, {}, {}) == []                                            # 야후 종가가 다시 오면 (또는 목록에서 사라지면) 빠져요


def test_step_replaces_the_yahoo_row_adds_empty_ones_leaves_aged_out_and_never_stops(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    prev = prev_file([us("AAPL", price=270.0), us("TD", price=60.0), us("OLD", d1=None, pxd="2026-11-10", pxc=True)])
    yahoo_aapl = us("AAPL", price=268.0, d1=None, pxd=D18)                          # 야후의 마지막 봉 (예전이면 이 값이 나갔어요)
    out = [us("MSFT"), yahoo_aapl, us("OLD", price=5.0, d1=None, pxd="2026-11-09")]
    rec = F.us_own_close_step(prev, {"AAPL": "bar", "TD": "empty", "OLD": "bar"}, out, dt.date(2026, 11, 20), UDAYS)
    by = {r["t"]: r for r in out}
    assert sorted(by) == ["AAPL", "MSFT", "TD"]                                      # OLD 는 나이 상한을 넘어 빠져요
    assert by["AAPL"]["price"] == 270.0 and by["AAPL"]["pxd"] == D19 and by["AAPL"]["pxc"] is True
    assert by["TD"]["price"] == 60.0 and by["TD"]["pxc"] is True
    assert rec["codes"] == ["AAPL", "TD"] and rec["n"] == 2 and rec["unconf"] == 3 and rec["drop"] == {"old": 1}
    assert rec["aged"] == [{"t": "OLD", "nk": "OLD Inc.", "pxd": "2026-11-10"}] and rec["why"] == {"bar": 2, "empty": 1}
    assert any(x.startswith("  !! 미국 종가 미확인 3종목") and "마지막 확인 종가로 실음 2종목" in x and "AAPL (11-19)" in x for x in lines), lines
    assert any(x.startswith("  !! 마지막 확인 종가가 5거래일을 넘어 잠시 뺀 미국 종목 1") for x in lines), lines
    json.dumps(rec, allow_nan=False)
    # 오류: 바꾼 것을 되돌리고 예전 그대로 (야후의 마지막 봉) · err · 지난 aged 중 오늘도 없는 종목은 남겨요
    def boom(*a, **k):
        raise ValueError("boom")
    monkeypatch.setattr(F, "us_own_close_carry", boom)
    out2 = [us("MSFT"), dict(yahoo_aapl)]
    rec2 = F.us_own_close_step({**prev, "usSrc": {"own": {"aged": [{"t": "ZZ", "nk": "ZZ", "pxd": "2026-11-01"}]}}},
                               {"AAPL": "bar", "ZZ": "empty"}, out2, dt.date(2026, 11, 20), UDAYS)
    assert out2 == [us("MSFT"), yahoo_aapl] and rec2["n"] == 0 and rec2["codes"] == [] and "boom" in rec2["err"]
    assert rec2["aged"] == [{"t": "ZZ", "nk": "ZZ", "pxd": "2026-11-01"}] and rec2["unconf"] == 2
    assert any("마지막 확인 종가 단계(미국)가 오류로 멈췄어요" in x for x in lines)


def test_final_check_drops_wrong_rows_with_the_gate_function(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    prev = prev_file([us("AAPL", price=270.0), us("MSFT", price=410.0), us("SHEL", price=71.0, d1=0.8)], usd=D19)
    rows = [us("AAPL", price=270.0, d1=None, pxd=D19, pxc=True), us("MSFT", price=999.0, d1=None, pxd=D19, pxc=True),
            us("NVDA"), us("XX", d1=None, pxd=D19, pxc=True)]
    umeta = {"usPxDate": D20, "usSrc": {"v": 1, "own": {"v": 1, "n": 9, "codes": ["AAPL", "MSFT", "GONE"], "same": ["GONE"], "bad": {"n": 0, "rows": []}}}}
    kept = F.us_own_close_final(rows, umeta, prev, UDAYS)
    own = umeta["usSrc"]["own"]
    assert [r["t"] for r in kept] == ["AAPL", "NVDA"]                                # MSFT 는 지난 발행본의 가격이 아님 · XX 는 지난 발행본에 없음
    assert own["codes"] == ["AAPL"] and own["n"] == 1 and own["same"] == []
    assert own["bad"]["n"] == 2 and own["bad"]["why"] == {"prev": 2}
    assert any(x.startswith("  !! 마지막 확인 종가 점검 (미국 · 관문과 같은 함수): 2종목 빼고 발행") for x in lines), lines
    # 점검이 멈추면 그 행들을 모두 빼고 이어가요
    umeta2 = {"usPxDate": D20, "usSrc": {"v": 1, "own": {"v": 1, "n": 1, "codes": ["AAPL"], "same": []}}}
    left = F.us_own_close_drop_all([us("AAPL", d1=None, pxd=D19, pxc=True), us("NVDA")], umeta2, "TypeError: x")
    assert [r["t"] for r in left] == ["NVDA"] and umeta2["usSrc"]["own"]["err"] == "TypeError: x" and umeta2["usSrc"]["own"]["codes"] == []


# ── fetch_us 를 가짜 야후로: 2026-11-20 처럼 최신 봉이 비거나 0 인 종목 ─────────────────────────────
INFO = {"shortName": "Co", "longName": "Co Inc.", "quoteType": "EQUITY", "sector": "Technology", "industry": "Software",
        "financialCurrency": "USD", "currency": "USD", "trailingPE": 20.0, "priceToBook": 4.0, "marketCap": 1e11, "averageVolume": 1e6,
        "country": "United States", "dividendYield": 0.5}


def _fake_yf(series):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"]})
        cols = {}
        for t in tickers:
            if t not in series:
                continue
            cols[(t, "Close")] = series[t]
            cols[(t, "Dividends")] = pd.Series(0.0, index=series[t].index)
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            return dict(INFO, shortName=self.t + " Co")
    return types.SimpleNamespace(download=download, Ticker=Ticker)


def _fetch(tmp_path, monkeypatch, blank, zero=(), prev_usd=D18, today_us=dt.date(2026, 11, 19), extra_prev=()):
    syms = ["AAPL", "MSFT", "NVDA", "SHEL", "BP", "ZERO", "TD", "STAG"]
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)
    days = days[days != pd.Timestamp("2026-11-26")]

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    series = {"_spx": walk(1, 6700.0)}
    for i, t in enumerate(syms[:6]):
        s = walk(10 + i, 100.0 + i)
        if t in blank:
            s.iloc[-1] = np.nan                                       # 야후가 최신 봉을 비움 (2026-11-20 의 모양)
        if t in zero:
            s.iloc[-1] = 0.0                                          # 야후가 빈 값을 0 으로 줌
        series[t] = s
    series["STAG"] = pd.Series(np.nan, index=days)                    # 가격을 하나도 주지 않음
    prev_rows = [us(t, price=50.0 + i, d1=0.3) for i, t in enumerate(syms) if t != "STAG"] + list(extra_prev)
    prev = {"pxDate": prev_usd, "usPxDate": prev_usd, "stocks": prev_rows}
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series))
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today_us)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    today = today_us + dt.timedelta(days=1)
    out, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev=prev)
    return out, meta, lines, prev


def test_fetch_us_carries_blank_and_zero_newest_bars(tmp_path, monkeypatch):
    out, meta, lines, prev = _fetch(tmp_path, monkeypatch, blank={"AAPL", "SHEL"}, zero={"ZERO"})
    by = {r["t"]: r for r in out}
    pby = {r["t"]: r for r in prev["stocks"]}
    for t in ("AAPL", "SHEL", "ZERO", "TD"):                           # TD: 야후가 주지 않음 (지난 발행본에는 있었어요)
        assert by[t]["pxc"] is True and by[t]["pxd"] == D18 and by[t]["price"] == pby[t]["price"] and "d1" not in by[t], t
        assert by[t]["nk"] in (t + " Co", "Co Inc.") and by[t].get("cap") is not None    # 상세 정보는 오늘 그 가격으로 붙여요 (SHEL 은 긴 이름)
    assert by["MSFT"]["d1"] is not None and "pxd" not in by["MSFT"] and "pxc" not in by["MSFT"]
    assert "STAG" not in by                                            # 지난 발행본에 없고 가격도 없음 → 예전처럼 빠져요
    assert all(r["price"] > 0 for r in out)                            # 0 종가가 가격 0 인 행이 되지 않아요 (EXTRA_US · 주식 종류 티커 줄)
    own = meta["usSrc"]["own"]
    assert own["codes"] == ["AAPL", "SHEL", "TD", "ZERO"] and own["unconf"] == 4 and own["why"] == {"bar": 3, "err": 1}
    assert any(x.startswith("  !! 미국 종가 미확인 4종목") for x in lines), lines
    meta.pop("_index")
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(out, allow_nan=False, ensure_ascii=False)


def test_fetch_us_same_day_republish_keeps_the_published_close(tmp_path, monkeypatch):
    out, meta, lines, prev = _fetch(tmp_path, monkeypatch, blank={"AAPL"}, prev_usd=D19)
    by = {r["t"]: r for r in out}
    p = next(r for r in prev["stocks"] if r["t"] == "AAPL")
    assert by["AAPL"]["price"] == p["price"] and by["AAPL"]["d1"] == p["d1"] and "pxd" not in by["AAPL"] and "pxc" not in by["AAPL"]
    assert meta["usSrc"]["own"]["same"] == ["AAPL", "TD"] and meta["usSrc"]["own"]["codes"] == []     # TD: 야후가 주지 않음 · 같은 날


def test_fetch_us_normal_day_records_nothing(tmp_path, monkeypatch):
    out, meta, lines, _p = _fetch(tmp_path, monkeypatch, blank=set())
    own = meta["usSrc"]["own"]
    assert own["n"] == 0 or own["codes"] == ["TD"]                      # TD 는 늘 없음 (가짜 야후가 주지 않아요)
    assert not any("pxc" in r for r in out if r["t"] != "TD")


# ── 2. 관문 ─────────────────────────────────────────────────────────────
def _usdata(stocks, usd=D20, codes=None, same=(), bad=None, aged=None, err=None):
    own = {"v": 1, "max": 5, "n": len(codes or []), "codes": sorted(codes or []), "same": list(same), "unconf": len(codes or []) + len(same),
           "drop": {}, "dropEx": [], "bad": bad or {"n": 0, "rows": []}}
    if aged is not None:
        own["aged"] = aged
    if err:
        own["err"] = err
    return {"usPxDate": usd, "pxDate": usd, "nextPub": "2026-11-21", "stocks": stocks, "usSrc": {"v": 1, "own": own}}


def macro_days():
    return {"idxHist": {"SP500": {"rows": [[d, 6000.0] for d in UDAYS]}}}


def rows_of(fn):
    rep = V.Report()
    fn(rep)
    return {r[0]: (r[3], r[1]) for r in rep.rows}


def _d1_rows(data, pdata=None):
    own = V.us_own_codes(data, pdata, UDAYS)
    us_ = V.us_stocks(data)
    by = {s["t"]: s for s in us_}
    return rows_of(lambda rep: V.check_v1751(rep, {"data": data, "macro": macro_days()}, [], us_, by, [], None, dt.date(2026, 11, 21), None,
                                             us_own=own))


def test_d1_row_counts_only_stocks_not_carried():
    prev = prev_file([us(f"S{i}", price=10.0 + i) for i in range(200)] + [us("AAPL", price=270.0)], usd=D19)
    carried = [us(f"S{i}", price=10.0 + i, d1=None, pxd=D19, pxc=True) for i in range(200)]
    fresh = [us(f"F{i}") for i in range(600)] + [us("AAPL"), us("MSFT"), us("NVDA")]
    data = _usdata(carried + fresh, codes=[s["t"] for s in carried])
    r = _d1_rows(data, prev)
    assert r["미국 d1 채움 (미국 기준일 봉)"][0] == "WARN" and "마지막 확인 종가 200" in r["미국 d1 채움 (미국 기준일 봉)"][1]
    halted = [us(f"H{i}", d1=None, pxd=D18) for i in range(5)]                        # 마지막 확인 종가가 아닌 빠짐: 5개까지 경고
    assert _d1_rows(_usdata(carried + fresh + halted, codes=[s["t"] for s in carried]), prev)["미국 d1 채움 (미국 기준일 봉)"][0] == "WARN"
    six = halted + [us("H5", d1=None, pxd=D18)]                                      # 6개 → 실패 (N = 5)
    assert _d1_rows(_usdata(carried + fresh + six, codes=[s["t"] for s in carried]), prev)["미국 d1 채움 (미국 기준일 봉)"][0] == "FAIL"
    # 지난 발행본의 가격이 아닌 마지막 확인 종가 · 기록에 없는 종목은 빠진 것으로 세요
    wrong = [us(f"S{i}", price=99.0, d1=None, pxd=D19, pxc=True) for i in range(6)] + carried[6:]
    assert _d1_rows(_usdata(wrong + fresh, codes=[s["t"] for s in carried]), prev)["미국 d1 채움 (미국 기준일 봉)"][0] == "FAIL"
    assert _d1_rows(_usdata(carried + fresh, codes=[]), prev)["미국 d1 채움 (미국 기준일 봉)"][0] == "FAIL"
    # usSrc 가 없는 파일 (이 칸 전 발행본): 예전 규칙 그대로 (98%)
    old = {"usPxDate": D20, "stocks": fresh + [us(f"H{i}", d1=None, pxd=D18) for i in range(10)]}
    assert _d1_rows(old)["미국 d1 채움 (미국 기준일 봉)"][0] == "WARN"
    old2 = {"usPxDate": D20, "stocks": fresh + [us(f"H{i}", d1=None, pxd=D18) for i in range(20)]}
    assert _d1_rows(old2)["미국 d1 채움 (미국 기준일 봉)"][0] == "FAIL"


def test_must_have_carried_warns_and_halted_still_fails():
    prev = prev_file([us("AAPL", price=270.0)], usd=D19)
    base = [us("MSFT"), us("NVDA")] + [us(f"F{i}") for i in range(300)]
    ok = _d1_rows(_usdata(base + [us("AAPL", price=270.0, d1=None, pxd=D19, pxc=True)], codes=["AAPL"]), prev)
    assert ok["미국 필수 종목 d1"][0] == "WARN" and "AAPL(2026-11-19)" in ok["미국 필수 종목 d1"][1]
    bad = _d1_rows(_usdata(base + [us("AAPL", price=270.0, d1=None, pxd=D18)], codes=[]), prev)
    assert bad["미국 필수 종목 d1"][0] == "FAIL"


def test_own_row_fails_on_broken_dates_or_a_change_beside_and_on_many_dropped():
    prev = prev_file([us("AAPL", price=270.0), us("MSFT", price=410.0)], usd=D19)
    row = lambda data, p=prev: rows_of(lambda rep: V.check_us_own_close(rep, data, macro_days(), p))["미국 마지막 확인 종가 (usSrc.own · pxc)"]
    good = _usdata([us("AAPL", price=270.0, d1=None, pxd=D19, pxc=True), us("NVDA")], codes=["AAPL"])
    assert row(good)[0] == "WARN" and "실음 1종목" in row(good)[1]
    assert row(_usdata([us("NVDA")], codes=[]))[0] == "PASS"
    assert rows_of(lambda rep: V.check_us_own_close(rep, {"usPxDate": D20, "stocks": [us("NVDA")]}, macro_days(), prev)) == \
        {"미국 마지막 확인 종가 (usSrc.own · pxc)": ("SKIP", "—")}                       # 이 칸 전 파일
    for broken in (us("AAPL", price=270.0, d1=0.4, pxd=D19, pxc=True),            # d1 이 옆에 있음
                   us("AAPL", price=270.0, d1=None, pxd="2026-11-31", pxc=True),   # 날짜가 깨짐
                   us("AAPL", price=270.0, d1=None, pxd=D20, pxc=True),            # usPxDate 보다 앞이 아님
                   us("AAPL", price=270.0, d1=0.4, pxc=True)):                     # pxd 없는 pxc
        assert row(_usdata([broken], codes=["AAPL"]))[0] == "FAIL", broken
    soft = _usdata([us("AAPL", price=1.0, d1=None, pxd=D19, pxc=True)], codes=["AAPL"])   # 지난 발행본의 가격이 아님 → 경고 (가격 줄들이 봐요)
    assert row(soft)[0] == "WARN" and "지난 발행본" in row(soft)[1]
    many = _usdata([us("NVDA")], codes=[], bad={"n": 6, "rows": [f"X{i}" for i in range(6)], "why": {"prev": 6}})
    five = _usdata([us("NVDA")], codes=[], bad={"n": 5, "rows": [f"X{i}" for i in range(5)], "why": {"prev": 5}})
    split = _usdata([us("NVDA")], codes=[], bad={"n": 6, "rows": [f"X{i}" for i in range(6)], "why": {"prev": 3, "old": 3}})
    stopped = _usdata([us("NVDA")], codes=[], bad={"n": 9, "rows": [], "why": {"prev": 9}}, err="ValueError: x")
    assert row(many)[0] == "FAIL" and row(five)[0] == "WARN" and row(split)[0] == "WARN" and row(stopped)[0] == "WARN"
    aged = _usdata([us("NVDA")], codes=[], aged=[{"t": "OLD", "nk": "OLD", "pxd": "2026-11-10"}])
    assert row(aged)[0] == "WARN" and "잠시 뺀 종목 1" in row(aged)[1]


def test_same_day_rows_must_be_the_previous_publish_exactly():
    prev = prev_file([us("SHEL", price=71.0, d1=0.8)], usd=D20)
    ok = _usdata([us("SHEL", price=71.0, d1=0.8)], codes=[], same=["SHEL"])
    assert V.us_own_close_bad(ok, prev, UDAYS) == []
    assert V.us_own_close_bad(_usdata([us("SHEL", price=72.0, d1=0.8)], codes=[], same=["SHEL"]), prev, UDAYS) == [("SHEL", "same")]
    assert V.us_own_close_bad(ok, prev_file([us("SHEL", price=71.0, d1=0.8)], usd=D19), UDAYS) == [("SHEL", "same")]   # 다른 날 발행본


def test_exact_carry_only_is_left_out_of_todays_price_checks():
    prev = prev_file([us("AAPL", price=270.0), us("MSFT", price=410.0, d1=None, pxd="2026-11-10", pxc=True)], usd=D19)
    data = _usdata([us("AAPL", price=270.0, d1=None, pxd=D19, pxc=True), us("MSFT", price=410.0, d1=None, pxd="2026-11-10", pxc=True)],
                   codes=["AAPL", "MSFT"])
    assert V.us_own_codes(data, prev, UDAYS) == {"AAPL"}                              # MSFT: 그 종가 뒤 미국 거래일 5일 넘음
    assert V.us_own_codes(data, None, None) == {"AAPL", "MSFT"}                       # 사이트 점검 (지난 발행본 · 거래일 없이)


def _snap(carry_n, blank_new=0, same_day=False):
    """2026-11-20 의 모양: 실제 하루치 발행을 줄인 사본(tests/fixtures/snapshot)을 지난 발행본으로, 다음 미국 거래일에 야후의 최신 봉이
    carry_n 종목에서 빈 날을 만들어 관문(run_checks)까지. blank_new: 마지막 확인 종가로 싣지 못한 빠짐 (야후의 마지막 봉 · pxc 없음)."""
    snap = os.path.join(ROOT, "tests", "fixtures", "snapshot")
    load = lambda n: json.load(open(os.path.join(snap, f"snap_{n}.json"), encoding="utf-8"))
    prev = {k: load(k) for k in ("data", "corp", "disc", "macro")}
    pdat = prev["data"]
    usd0 = pdat["usPxDate"]
    rows = sorted(r[0] for r in prev["macro"]["idxHist"]["SP500"]["rows"])
    T = usd0 if same_day else next(d.strftime("%Y-%m-%d") for d in pd.bdate_range(usd0, periods=3) if d.strftime("%Y-%m-%d") > usd0)
    macro = copy.deepcopy(prev["macro"])
    if T not in rows:
        macro["idxHist"]["SP500"]["rows"].append([T, 6800.0])
    usl = [s for s in pdat["stocks"] if s.get("cls") == "us" and not s.get("fund")]
    tick = sorted(s["t"] for s in usl if s["t"] not in ("AAPL", "MSFT", "NVDA"))
    blank = set(tick[:carry_n])
    nocl = {t: "bar" for t in blank}
    out = []
    for s in usl:
        r = copy.deepcopy(s)
        if s["t"] in blank:
            r.pop("d1", None)
            r["pxd"] = s["t"] + "?"                                    # 야후의 마지막 봉 (예전이면 이 행이 나갔어요) — 단계가 바꿔요
        elif not same_day:
            r["price"] = round(s["price"] * 1.01, 2)
            r["d1"] = 1.0
        out.append(r)
    halt = sorted(t for t in tick if t not in blank)[:blank_new]
    for r in out:
        if r["t"] in halt:
            r.pop("d1", None)
            r["pxd"] = usd0
            r["price"] = round(r["price"] * 1.01, 2)
    days = sorted({r[0] for r in macro["idxHist"]["SP500"]["rows"]})
    own = F.us_own_close_step(pdat, nocl, out, dt.date.fromisoformat(T), days, etfs=F.US_ETFS)
    umeta = {"usPxDate": T, "usSrc": {"v": 1, "own": own}}
    out = F.us_own_close_final(out, umeta, pdat, days)
    for r in out:                                                       # 상세 정보 · 점수는 오늘 다시 붙여요 (여기서는 지난 발행본의 값 그대로)
        if r.get("pxc") or r["t"] in own.get("same", []):
            p = next(x for x in usl if x["t"] == r["t"])
            r.update({k: v for k, v in p.items() if k not in F.US_OWN_KEYS and k not in ("d1", "pxd", "pxc")})
    stocks = [copy.deepcopy(s) for s in pdat["stocks"] if not (s.get("cls") == "us" and not s.get("fund"))] + out
    data = {**pdat, "usPxDate": T, "stocks": stocks, "usSrc": umeta["usSrc"]}
    json.dumps(data, allow_nan=False)
    kdays = [dt.date.fromisoformat(r[0]) for r in prev["macro"]["idxHist"]["KOSPI"]["rows"]]
    rep = V.run_checks({"data": data, "corp": prev["corp"], "disc": prev["disc"], "macro": macro}, prev, None,
                       dt.date.fromisoformat(T) + dt.timedelta(days=1), "publish", count_between=lambda a, b: 1, notes=[],
                       sessions={"dates": kdays, "src": "t"}, now=None, hilo=None, special={}, alt=None)
    return data, {r[0]: (r[3], r[1]) for r in rep.rows}


def test_a_yahoo_gap_like_1120_publishes_with_carries_and_a_warning():
    data, rows = _snap(60)
    _, plain = _snap(0)
    fails = lambda r: sorted(k for k, v in r.items() if v[0] == "FAIL")
    # 줄인 고정 데이터라 실패하는 줄도 있어요 (최종본 없음 · 종목 수) — 야후가 빈 날과 빈 종목이 없는 날의 실패 줄이 같아요
    assert fails(rows) == fails(plain), set(fails(rows)) ^ set(fails(plain))
    assert rows["미국 d1 채움 (미국 기준일 봉)"][0] == "WARN" and "마지막 확인 종가 60" in rows["미국 d1 채움 (미국 기준일 봉)"][1], rows["미국 d1 채움 (미국 기준일 봉)"]
    assert rows["미국 마지막 확인 종가 (usSrc.own · pxc)"][0] == "WARN" and rows["미국 자기 가격 날짜 (pxd)"][0] == "PASS"
    assert rows["미국 가격이 바뀌었는지"][0] == "PASS" and "마지막 확인 종가 60종목 빼고" in rows["미국 가격이 바뀌었는지"][1], rows["미국 가격이 바뀌었는지"]
    assert sum(1 for s in data["stocks"] if s.get("pxc")) == 60 and data["usSrc"]["own"]["n"] == 60
    # 예전 규칙이었으면: 60 / 90 빠짐 → '미국 d1 채움' 실패 (발행이 멈췄어요)
    old = {**data, "stocks": [{k: v for k, v in s.items() if k != "pxc"} for s in data["stocks"]]}
    old.pop("usSrc")
    assert _d1_rows(old)["미국 d1 채움 (미국 기준일 봉)"][0] == "FAIL"


def test_the_same_day_gap_republishes_the_published_closes():
    data, rows = _snap(60, same_day=True)
    assert data["usSrc"]["own"]["same"] and len(data["usSrc"]["own"]["same"]) == 60 and data["usSrc"]["own"]["n"] == 0
    assert rows["미국 d1 채움 (미국 기준일 봉)"][0] == "WARN" and rows["미국 마지막 확인 종가 (usSrc.own · pxc)"][0] == "WARN"


def test_many_missing_without_a_carry_still_blocks():
    _, rows = _snap(10, blank_new=6)
    assert rows["미국 d1 채움 (미국 기준일 봉)"][0] == "FAIL", rows["미국 d1 채움 (미국 기준일 봉)"]


# ── 3. 앱 (Node) ───────────────────────────────────────────────────────────
NODE = shutil.which("node")
_B = {}
MODS = {"D": "src/data.js", "L": "src/v2/stocklist.js", "R": "src/v2/rules.js", "CF": "src/v2/cofmt.js", "F": "src/v2/format.js",
        "LD": "src/v2/load.js", "C": "src/copy/v2.js", "FX": "src/fixnote.jsx"}
needs_node = pytest.mark.skipif(NODE is None, reason="node 가 없어요")


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/own.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as M from './own.mjs';\nconst { D, L, R, CF, F, LD, FX } = M; const CP = M.C.C;\n"
            "const WARN = []; console.warn = (m) => WARN.push(String(m));\n" + decl + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out === undefined ? null : out));\n")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def kr(t, nk, **kw):
    s = {"t": t, "nk": nk, "cls": "kr", "price": 5000.0, "d1": 0.5}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


@needs_node
def test_app_lists_name_us_carries_with_jacks_line_and_halted_as_before():
    rows = [us("AAPL", d1=None, pxd=D18, pxc=True), kr("011810", "STX", d1=None, pxd=D18), us("HALT", d1=None, pxd=D18),
            us("MSFT"), us("TSLA", d1=None, pxd="2026-11-13", pxc=True)]
    got = run("const load = { status: 'ok', data: { pxDate: '2026-11-19', usPxDate: '2026-11-19' } };"
              " out = { g: L.ownCloses(load, ROWS), txt: F.ownCloseText(L.ownCloses(load, ROWS)) };", ROWS=rows)
    assert got["g"] == [{"date": D18, "ts": ["HALT"]},
                        {"date": D18, "ts": ["AAPL", "011810"], "kr": True, "names": ["AAPL", "STX"]},
                        {"date": "2026-11-13", "ts": ["TSLA"], "kr": True, "names": ["TSLA"]}], got["g"]
    assert got["txt"] == ("HALT 가격은 11월 18일 종가예요. "
                          "AAPL, STX: 오늘 종가를 확인하지 못해서 11월 18일 종가를 보여 드려요. "
                          "TSLA: 오늘 종가를 확인하지 못해서 11월 13일 종가를 보여 드려요."), got["txt"]


@needs_node
def test_app_single_us_carry_line_both_apps():
    got = run("""
const load = { status: 'ok', data: { pxDate: '2026-11-20', usPxDate: '2026-11-19' } };
out = { c: CF.krOwnCloseText(load, A), h: CF.krOwnCloseText(load, H), f: CF.krOwnCloseText(load, MS),
  old: [FX.krOwnCloseText(A, '2026-11-19'), FX.krOwnCloseText(H, '2026-11-19'), FX.krOwnCloseText(A, '2026-11-19', 'en')],
  list: FX.krOwnCloseListLine('AAPL', '2026-11-18', 'en'), carried: [D.ownCarried(A), D.ownCarried(H), D.ownCarried(MS)],
  merged: D.mergeStocks([], [A]).map((s) => [s.t, s.pxd, s.pxc]) };""",
              A=us("AAPL", d1=None, pxd=D18, pxc=True), H=us("HALT", d1=None, pxd=D18), MS=us("MSFT"))
    line = JACK.replace("{date}", "11월 18일")
    assert got["c"] == line and got["h"] is None and got["f"] is None
    assert got["old"] == [line, None, JACK_EN.replace("{date}", "Nov 18")]
    assert got["list"] == "AAPL: " + JACK_EN.replace("{date}", "Nov 18") and got["carried"] == [True, False, False]
    assert got["merged"] == [["AAPL", D18, True]]                     # 예전 뱁새도 표시를 받아요


@needs_node
def test_app_aged_map_has_us_stocks_too():
    got = run("out = [...D.ownAgedOf(J).entries()];", J={
        "stocks": [us("MSFT")], "pxSrc": {"own": {"aged": [{"t": "111110", "nk": "가나다", "pxd": "2026-11-10"}]}},
        "usSrc": {"own": {"aged": [{"t": "OLD", "nk": "OLD Inc.", "pxd": "2026-11-10"}, {"t": "MSFT", "nk": "x", "pxd": "2026-11-10"}]}}})
    assert got == [["111110", {"nk": "가나다", "pxd": "2026-11-10"}], ["OLD", {"nk": "OLD Inc.", "pxd": "2026-11-10"}]]   # 발행하는 종목은 무시


@needs_node
def test_app_late_check_caps_us_carries_on_nyse_days():
    """Jack (2026-11-20, f · US): 늦은 데이터의 점검은 마지막 확인 종가가 모두 합쳐 5거래일을 넘으면 돌지 않아요 — 미국은 NYSE 거래일 (추수감사절 휴장)."""
    got = run("""
const ctx = (today, S) => ({ byT: new Map(S.map((s) => [s.t, s])), pxDate: '2026-11-25', usPxDate: '2026-11-25', today });
const st = { ok: true, late: { days: 2, n: 2 } };
const deck = (t) => ({ id: 'd', holdings: [{ t, target: 1, kind: 'core', rules: [] }], purchases: [{ t, date: '2026-11-02', qty: 1, price: 100, ccy: 'USD' }] });
out = { d27: R.lateCap(st, ctx('2026-11-27', [A]), [deck('AAPL')]).ok, d30: R.lateCap(st, ctx('2026-11-30', [A]), [deck('AAPL')]).ok,
  halt30: R.lateCap(st, ctx('2026-11-30', [H]), [deck('HALT')]).ok };""",
              A=us("AAPL", d1=None, pxd=D19, pxc=True), H=us("HALT", d1=None, pxd=D19))
    assert got == {"d27": True, "d30": False, "halt30": True}, got     # 11-20 · 23 · 24 · 25 · 27 = 5 · 11-30 = 6 · 거래 정지는 예전 그대로


@needs_node
def test_app_load_report_says_us_carries():
    got = run("WARN.splice(0); LD.logDates(D1); out = WARN.splice(0).filter((m) => !/staleAfter|nextPub/.test(m));",
              D1={"pxDate": D20, "usPxDate": D19, "staleAfter": "2026-11-21T16:47:00+09:00", "nextPub": "2026-11-21",
                  "stocks": [us("AAPL", d1=None, pxd=D18, pxc=True), us("HALT", d1=None, pxd=D18), us("MSFT")]})
    assert len(got) == 2 and got[0].startswith("[v2] 2 of 3 US stocks at an earlier close") and got[1].startswith("[v2] 1 of them carried"), got
    assert "AAPL 2026-11-18" in got[1] and "HALT" not in got[1]
