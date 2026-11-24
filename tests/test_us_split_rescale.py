# -*- coding: utf-8 -*-
"""2026-11-23 (감사 · SNDK 8:1 분할 2026-11-20 · #176): 분할 뒤 미국 상세 정보 보관본 맞춤 · 기록 (usSrc.split) · 관문의 새 경고 줄.

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 시험은 그대로):
- 파이프라인: 야후 상세 정보 보관본의 기준 가격(px)이 분할 전 주식 수 기준이면 PER · PBR · 시가총액 · 배당수익률 · 거래대금을 오늘 가격 × 배율 ÷ 그때
  가격으로 맞춰요 (fetch_data.us_rescale · apply_us_info split · us_info_split_view) — 분할 없음 · 병합 · 두 번 · 기준 가격 날짜(pd · 예전 항목은 받은 날
  하루 전) · 미국 기준일 뒤 날짜의 분할 (야후가 반영했으면 곱함 · 리뷰 S1) · 곱하면 더 멀어지는 때는 예전 그대로 · 다시 물음 (odd)
- 리뷰 #176 1차: 배율을 믿을 수 있는 보관본은 따로 다시 받지 않아요 · 보통 때처럼 다시 받은 새 상세 정보는 보관본 × 배율과 맞춰 보고 √배율 넘게
  다르면 보관본을 써요 (11-21 SNDK: 새 PBR 0.63 ↔ 보관본 × 8 이면 5.03) · 분할을 모르는데 가격이 2배 밖이면 다시 물어요 (S2) · 그런 길은 data.json
  usSrc.split 에 적고 관문 줄이 이름을 적어요 · 마지막 확인 종가 행 · ETF 거래대금 · 0.00 PBR 세기 · 나중에 분할이 나와 야후 봉으로 되돌리는 행
- 관문: '미국 분할 뒤 상세 숫자' 줄은 경고만 — 어떤 모드에서도 실패하지 않고, 검사가 멈춰도 경고예요
"""
import datetime as dt
import math
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
from fixture_data import good_pair, hilo_of  # noqa: E402

FX = 1345.7
ROW = V.US_SPLIT_PBR_ROW
US21, US20, US19, US18 = "2026-11-21", "2026-11-20", "2026-11-19", "2026-11-18"
# 2026-11-11 발행본의 SNDK (분할 전): 가격 977.69 · PER 7.8 · PBR 7.76 · 주식 수 142.3백만 · 평균 거래량 10.78백만 → 주당순이익 125.3 · 주당 장부가 126.0
EPS0, BPS0, SH0, AV0 = 977.69 / 7.8, 977.69 / 7.76, 142.3e6, 10.78e6
PX18 = 755.12                       # 2026-11-18 종가 (분할 전 · 11-20 의 79.24 는 11-19 의 94.39 에서 −16.05%)
# #188 (2026-11-24): 회사 합계 — 보통주 몫 순이익은 야후가 2026-11-24 SNDK 에 준 값 (netIncomeToCommon 19.422십억 달러). 최근 분할한 회사의 주당 숫자 검사
# (fetch_data.us_split_check)가 이 합계와 맞춰 봐요: 시가총액 ÷ 순이익 5.53 ↔ PER 6.02 (1.09배 · 폭 1.10) · × ROE 7.81 ↔ PBR 5.99 (1.30배 · 폭 1.35) — 맞음
SNDK_NI = 19.422e9
SNDK_PRE = {"shortName": "Sandisk Corporation", "longName": "Sandisk Corporation", "quoteType": "EQUITY", "sector": "Technology",
            "industry": "Computer Hardware", "financialCurrency": "USD", "currency": "USD", "country": "United States",
            "trailingPE": PX18 / EPS0, "priceToBook": PX18 / BPS0, "returnOnEquity": 1.412, "marketCap": PX18 * SH0,
            "averageVolume": AV0, "dividendYield": 0.0, "totalRevenue": 1e10, "operatingMargins": 0.3, "netIncomeToCommon": SNDK_NI}
# 11-21 에 실제로 받은 모양: 분할 뒤 새로 받았는데 PBR 만 분할 전 주당 장부가 (79.24 ÷ 126 = 0.63) · PER · 시가총액 · 평균 거래량은 분할 뒤 값
SNDK_STALE = dict(SNDK_PRE, trailingPE=79.24 / (EPS0 / 8), priceToBook=79.24 / BPS0, marketCap=79.24 * SH0 * 8, averageVolume=AV0 * 8)
SNDK_POST = dict(SNDK_STALE, priceToBook=79.24 / (BPS0 / 8))
K8 = 79.24 * 8 / PX18               # 분할 전 보관본(11-18 종가) → 오늘 79.24 · 8:1


def rows_of(rep):
    return {r[0]: (r[3], r[1]) for r in rep.rows}


def entry(at, px, info=None, pd_=None):
    e = {"at": at, "px": px, "k": F.US_INFO_SCHEMA, "info": dict(info or SNDK_PRE)}
    if pd_:
        e["pd"] = pd_
    return e


# ── 1. 순수 함수 ─────────────────────────────────────────────────────────────
def test_rescale_without_a_split_is_the_price_ratio_as_before():
    assert F.us_rescale(110.0, 100.0) == pytest.approx(1.1) == F.us_rescale(110.0, 100.0, 1.0)
    assert F.us_rescale(None, 100.0, 8.0) == 1.0 and F.us_rescale(110.0, None, 8.0) == 1.0 and F.us_rescale(110.0, 0.0, 8.0) == 1.0
    for bad in (None, 0, -2.0, float("nan"), float("inf"), "x"):
        assert F.us_rescale(110.0, 100.0, bad) == pytest.approx(1.1), bad      # 숫자가 아닌 배율은 분할 없음


def test_rescale_with_a_split_a_reverse_split_and_two_splits():
    assert F.us_rescale(100.0, 800.0, 8.0) == pytest.approx(1.0)              # 8:1 · 움직임 없음 (예전 0.125)
    assert F.us_rescale(100.0, 10.0, 0.1) == pytest.approx(1.0)               # 1:10 병합 · 움직임 없음 (예전 10)
    assert F.us_rescale(100.0, 600.0, 2.0 * 3.0) == pytest.approx(1.0)        # 2:1 뒤 3:1
    assert F.us_rescale(90.0, 800.0, 8.0) == pytest.approx(0.9)               # 분할 뒤 실제로 10% 내림


def test_anchor_day_and_price_basis():
    assert F.us_info_anchor_day({"at": US20}) == US19 and F.us_info_anchor_day({"at": US20, "pd": US18}) == US18
    assert F.us_info_anchor_day({"at": US20, "pd": "11/18"}) == US19                    # 읽지 못한 pd → 받은 날 하루 전
    assert F.us_info_anchor_day({"at": "nope"}) is None and F.us_info_anchor_day(None) is None
    assert F.us_price_basis_day({"pxc": True, "pxd": US18}, dt.date(2026, 11, 20)) == US18
    assert F.us_price_basis_day({"pxd": US18}, dt.date(2026, 11, 20)) == US20 == F.us_price_basis_day({}, dt.date(2026, 11, 20))


def test_split_view_picks_the_factor_by_dates_then_prices():
    ev = [("2026-11-10", 2.0), ("2026-11-17", 3.0)]
    v = F.us_info_split_view({"at": US21, "pd": "2026-11-09", "px": 600.0}, 100.0, US20, ev)
    assert (v["f"], v["use"], v["hit"], v["odd"], v["jump"], v["late"]) == (6.0, True, ev, False, False, [])          # 두 번
    assert F.us_info_split_view({"at": US21, "pd": "2026-11-12", "px": 300.0}, 100.0, US20, ev)["f"] == 3.0
    assert F.us_info_split_view({"at": US21, "pd": "2026-11-17", "px": 100.0}, 100.0, US20, ev)["hit"] == []         # 그날 가격은 이미 분할 뒤
    assert F.us_info_split_view({"at": US21, "pd": "2026-11-09", "px": 200.0}, 100.0, "2026-11-16", ev)["f"] == 2.0  # 가격 기준 날짜 뒤는 hit 아님
    rev = F.us_info_split_view({"at": US21, "pd": "2026-11-09", "px": 10.0}, 100.0, US20, [("2026-11-18", 0.1)])
    assert rev["f"] == 0.1 and rev["use"]                                                                            # 1:10 병합
    # 예전 항목 (pd 없음): 받은 날 하루 전 — 11-20 실행은 11-19 종가 · 11-21 실행은 11-20 (분할 뒤) 종가
    assert F.us_info_split_view({"at": US20, "px": 800.0}, 100.0, US20, [(US20, 8.0)])["f"] == 8.0
    assert F.us_info_split_view({"at": US21, "px": 100.0}, 100.0, US20, [(US20, 8.0)])["hit"] == []
    # 날짜로는 분할 전인데 보관본이 이미 분할 뒤 가격 → 곱하지 않음 (odd · 다시 물어요)
    odd = F.us_info_split_view({"at": US20, "px": 80.0}, 79.24, US20, [(US20, 8.0)])
    assert (odd["f"], odd["use"], odd["odd"]) == (1.0, False, True)
    # 리뷰 S1: 미국 기준일 뒤 날짜의 분할 — 야후 시계열이 반영했으면 곱하고 (lateUse) · 아니면 곱하지 않아요 (odd 아님)
    s1 = F.us_info_split_view({"at": US19, "px": PX18}, 79.24, US20, [(US21, 8.0)])
    assert (s1["f"], s1["use"], s1["lateUse"], s1["late"], s1["odd"], s1["jump"]) == (8.0, True, True, [(US21, 8.0)], False, False)
    s1n = F.us_info_split_view({"at": US19, "px": PX18}, 760.0, US20, [(US21, 8.0)])
    assert (s1n["f"], s1n["use"], s1n["late"], s1n["odd"]) == (1.0, False, [(US21, 8.0)], False)
    # 리뷰 S2: 분할을 모르는데 가격이 2배 밖 → jump (다시 물어요)
    assert F.us_info_split_view({"at": US19, "px": PX18}, 79.24, US20, [])["jump"] is True
    assert F.us_info_split_view({"at": US19, "px": 100.0}, 210.0, US20, None)["jump"] is True
    assert F.us_info_split_view({"at": US19, "px": 100.0}, 190.0, US20, None)["jump"] is False
    # 기준 가격 · 날짜를 모르면 아무것도 하지 않아요
    for e in ({"at": "nope", "px": 800.0}, {"at": US20}, {"at": US20, "px": 0}):
        assert F.us_info_split_view(e, 100.0, US20, [(US20, 8.0)]) == {"f": 1.0, "use": False, "hit": [], "late": [], "lateUse": False,
                                                                        "odd": False, "jump": False}


def test_split_map_uses_the_same_sources_as_the_published_list(monkeypatch):
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("Z", US18): (None, "분사"), ("W", "2026-11-02"): (0.5, "병합 · 야후에 없음")})
    prev = {"splits": [["X", "2026-11-10", 2.0], ["OLD", "2020-08-31", 4.0], ["bad", "x", 2.0]]}
    recent = [["X", "2026-11-12", 2.0],                      # 야후가 날짜를 옮긴 같은 사건 → 한 번만 · 야후의 지금 날짜 (리뷰 #176)
              ["X", "2026-11-14", 2.0],                      # 같은 사건을 또 다른 날짜에 → 더 곱하지 않아요
              ["X", "2026-11-10", 3.0],                      # 같은 종목 · 날짜인데 배율이 다름 → 지난 발행본 값 (merge_splits 와 같아요)
              ["SNDK", US20, 8.0], ["Z", US18, 1.5], ["Y", "nope", 2.0], ["Y", US18, -1.0]]
    m = F.us_info_split_map(recent, prev)
    assert m == {"X": [("2026-11-12", 2.0)], "OLD": [("2020-08-31", 4.0)], "SNDK": [(US20, 8.0)], "W": [("2026-11-02", 0.5)]}, m
    assert F.us_info_split_map(None, None) == {"W": [("2026-11-02", 0.5)]}


def test_guard_keeps_todays_behaviour_when_the_split_moves_the_ratio_away_from_one():
    assert F.us_info_split_ok(100.0, 800.0, 8.0) and F.us_info_split_ok(100.0, 10.0, 0.1)
    assert not F.us_info_split_ok(100.0, 100.0, 8.0)             # 보관본이 이미 분할 뒤 값 (곱하면 8배) → 예전 그대로
    assert F.us_info_split_ok(270.0, 800.0, 8.0)                 # 분할 뒤 2.7배 올라도 (√8 = 2.83 안) 곱해요
    assert not F.us_info_split_ok(300.0, 800.0, 8.0)             # √8 넘게 오르면 날짜만으로 믿지 않아요
    assert not F.us_info_split_ok(None, 800.0, 8.0) and not F.us_info_split_ok(100.0, None, 8.0)


def test_refetch_rule_is_unchanged_a_split_alone_does_not_make_a_copy_due():
    today = dt.date(2026, 11, 21)
    assert F.us_info_due(entry(US20, 640.0, pd_=US19), today) is False                   # 하루 된 보관본 (3일 규칙 그대로)
    assert F.us_info_due(entry("2026-11-18", 640.0), today) is True and F.us_info_due(None, today) is True


def test_fresh_details_against_the_copy_times_the_ratio():
    copy = entry(US19, PX18)
    stale = entry(US21, 79.24, SNDK_STALE, US20)                 # 11-21 의 모양: PBR 만 분할 전 (시가총액은 맞음)
    assert F.us_info_fresh_vs_copy(stale, copy, 79.24, 8.0) == ("diff", ["pbr 8.00배"])
    assert F.us_info_fresh_vs_copy(entry(US21, 79.24, SNDK_POST, US20), copy, 79.24, 8.0) == ("ok", [])
    vol = entry(US21, 79.24, dict(SNDK_POST, averageVolume=AV0), US20)                  # 평균 거래량이 아직 분할 전 주식 수
    assert F.us_info_fresh_vs_copy(vol, copy, 79.24, 8.0) == ("diff", ["vol 8.00배"])
    gone = entry(US21, 79.24, {k: v for k, v in SNDK_STALE.items() if k != "priceToBook"}, US20)
    assert F.us_info_fresh_vs_copy(gone, copy, 79.24, 8.0) == ("ok", [])                 # 한쪽이 없는 칸은 보지 않아요
    near = entry(US21, 79.24, dict(SNDK_POST, trailingPE=SNDK_POST["trailingPE"] * 2.5), US20)
    assert F.us_info_fresh_vs_copy(near, copy, 79.24, 8.0) == ("ok", [])                 # 분할 전 방향이 아니에요 (실적 같은 진짜 변화)


def test_fresh_vs_copy_flags_only_the_pre_split_direction_with_a_floor():
    """리뷰 2차 S-C: 2:1 뒤 실적으로 PER 이 35% 내린 것 · 21:20 주식배당 뒤 평균 거래량이 4% 는 것은 '분할 전 같음'이 아니에요."""
    info = {"trailingPE": 20.0, "priceToBook": 4.0, "marketCap": 1e10, "averageVolume": 1e6}
    copy = {"at": US19, "px": 200.0, "info": info}               # 분할 전 $200
    per35 = {"at": US21, "px": 100.0, "pd": US20, "info": dict(info, trailingPE=20.0 * 0.65, marketCap=2e10 / 2, averageVolume=2e6)}
    assert F.us_info_fresh_vs_copy(per35, copy, 100.0, 2.0) == ("ok", [])
    stale_per = dict(per35, info=dict(per35["info"], trailingPE=20.0 * 0.5))           # 정확히 분할 전 (×1/2) → 분할 전 같음
    assert F.us_info_fresh_vs_copy(stale_per, copy, 100.0, 2.0) == ("diff", ["per 2.00배"])
    vol4 = {"at": US21, "px": 100.0, "pd": US20, "info": dict(info, marketCap=1e10 * 100.0 / 105.0 * 1.05 / 1.05, averageVolume=1.05e6 * 1.04)}
    assert F.us_info_fresh_vs_copy(vol4, {"at": US19, "px": 105.0, "info": info}, 100.0, 1.05) == ("ok", [])
    stale_dv = dict(vol4, info=dict(vol4["info"], averageVolume=1e6))                    # 주식배당 뒤 분할 전 거래량이어도 (1.05배) 보지 않아요
    assert F.us_info_fresh_vs_copy(stale_dv, {"at": US19, "px": 105.0, "info": info}, 100.0, 1.05) == ("ok", [])
    up = dict(per35, info=dict(per35["info"], trailingPE=20.0 * 2.0))                    # 반대 방향 (× 2) 은 분할 전이 아니에요
    assert F.us_info_fresh_vs_copy(up, copy, 100.0, 2.0) == ("ok", [])


# ── 2. apply_us_info: 감사의 재현 · 병합 · 두 번 ──────────────────────────────────
def _apply(info, px_then, price, split=1.0):
    rec = {"t": "SPLT", "price": price}
    assert F.apply_us_info(rec, dict(info), px_then, FX, today=dt.date(2026, 11, 21), split=split)
    return rec


def test_apply_us_info_after_a_split_matches_the_numbers_before_it():
    """감사의 재현: 분할 이틀 전 $800 에 받은 보관본 (시가총액 $100B · PER 40 · PBR 6 · 배당 0.4%) · 오늘 8:1 분할 뒤 $100 (움직임 없음)."""
    info = {"shortName": "Split Co", "financialCurrency": "USD", "currency": "USD", "trailingPE": 40.0, "priceToBook": 6.0,
            "marketCap": 100e9, "averageVolume": 5e6, "dividendYield": 0.4, "returnOnEquity": 0.15}
    same = _apply(info, 800.0, 800.0)
    main_way = _apply(info, 800.0, 100.0)                                            # main: 가격 비율만
    fixed = _apply(info, 800.0, 100.0, split=8.0)
    assert (main_way["per"], main_way["pbr"], main_way["dy"]) == (5.0, 0.75, 3.2) and main_way["cap"] == pytest.approx(same["cap"] / 8, abs=0.002)
    for k in ("per", "pbr", "dy", "cap", "roe", "val"):
        assert fixed[k] == pytest.approx(same[k], abs=0.051), k                      # 거래대금도: 평균 거래량(분할 전 주식 수) × 8
    assert main_way["val"] == pytest.approx(same["val"] / 8, rel=0.01)


def test_apply_us_info_reverse_split_and_two_splits():
    info = {"shortName": "Co", "financialCurrency": "USD", "currency": "USD", "trailingPE": 20.0, "priceToBook": 2.0,
            "marketCap": 1e9, "averageVolume": 1e6, "dividendYield": 1.0}
    before, ref = _apply(info, 10.0, 10.0), _apply(info, 600.0, 600.0)
    rev = _apply(info, 10.0, 100.0, split=0.1)                                       # 1:10 병합 · $10 → $100
    two = _apply(info, 600.0, 100.0, split=2.0 * 3.0)                                # 2:1 뒤 3:1 · $600 → $100
    for k in ("per", "pbr", "dy", "cap", "val"):
        assert rev[k] == pytest.approx(before[k], abs=0.051), k
        assert two[k] == pytest.approx(ref[k], abs=0.051), k
    assert _apply(info, 10.0, 100.0)["per"] == 200.0                                 # main: 병합 뒤 PER 이 10배


# ── 3. fetch_us 전체 (가짜 야후) ───────────────────────────────────────────────
def _fake_yf(series, infos, splits, refuse=()):
    calls = []

    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_fx" if tickers == F.FX_TICKER else "_spx"]})
        cols, have = {}, [t for t in tickers if t in series]
        idx = pd.DatetimeIndex(sorted(set().union(*(set(series[t].index) for t in have))
                                      | {pd.Timestamp(d) for t in have for d, _r in splits.get(t, [])}))   # 미국 기준일 뒤 날짜의 분할 줄도 (S1)
        for t in have:
            cols[(t, "Close")] = series[t].reindex(idx)
            cols[(t, "Dividends")] = pd.Series(0.0, index=idx)
            sp = pd.Series(0.0, index=idx)
            for d, r in splits.get(t, []):
                sp[pd.Timestamp(d)] = r
            cols[(t, "Stock Splits")] = sp
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            calls.append(self.t)
            if self.t in refuse:
                raise RuntimeError("야후가 거절함")
            return dict(infos[self.t])
    return types.SimpleNamespace(download=download, Ticker=Ticker), calls


def _run(tmp_path, monkeypatch, cache=None, refuse=(), sndk_info=None, splits=None, last=79.24, prev=None, blank=(), extra=None):
    """미국 기준일 2026-11-20 · 한국 날짜 11-21 실행. 야후 시계열은 분할을 반영해요 (SNDK 11-19 94.39 → 11-20 79.24). extra = {티커: (마지막 가격, info)}."""
    today_us = dt.date(2026, 11, 20)
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)
    syms = ["AAPL", "MSFT", "NVDA", "SNDK"] + sorted(extra or {})

    def walk(seed, end):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * end / float(s.iloc[-1])
    series = {"_spx": walk(1, 6700.0), "_fx": pd.Series(FX, index=days)}
    for i, t in enumerate(syms[:3]):
        series[t] = walk(10 + i, 100.0 + i)
    sn = walk(20, 94.39)
    sn.iloc[-1] = last
    series["SNDK"] = sn
    infos = {t: dict(SNDK_PRE, shortName=t + " Co", longName=t + " Inc.") for t in syms[:3]}
    infos["SNDK"] = sndk_info or dict(SNDK_PRE)
    for i, (t, (end, info)) in enumerate(sorted((extra or {}).items())):
        series[t] = walk(30 + i, end)
        infos[t] = info
    for t in blank:
        series[t] = series[t].copy()
        series[t].iloc[-1] = np.nan                                  # 야후가 미국 기준일 봉을 비움 → 마지막 확인 종가
    fake, calls = _fake_yf(series, infos, {"SNDK": [(US20, 8.0)]} if splits is None else splits, refuse)
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today_us)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    path = str(tmp_path / "us-info.json.gz")
    monkeypatch.setattr(F, "US_INFO_PATH", path)
    if cache:
        F.save_us_info(cache, path)
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    today = dt.date(2026, 11, 21)
    out, _b, _fx, fx_last, _v, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev=prev or {"usPxDate": US19, "stocks": []})
    assert fx_last == pytest.approx(FX)
    return {r["t"]: r for r in out}, meta, lines, calls, path


def _log(lines, head="미국 분할 뒤 보관본 맞춤"):
    got = [x for x in lines if head in x]
    assert len(got) == 1, lines
    return got[0]


def _split_rec(meta):
    return (meta.get("usSrc") or {}).get("split")


def _gate_of(by, meta, splits=None):
    rep = V.Report()
    V.check_us_split_pbr(rep, {"usPxDate": US20, "splits": splits if splits is not None else [["SNDK", US20, 8.0]], "stocks": list(by.values()),
                               "usSrc": meta.get("usSrc")})
    return rows_of(rep)[ROW], rep


def test_sndk_shape_a_correctable_copy_is_used_without_asking_yahoo_again(tmp_path, monkeypatch):
    """11-19 (한국 날짜) 에 받은 분할 전 보관본 · 11-21 실행 (이틀 됨 · 보통 규칙으로는 다시 받지 않아요). 리뷰 #176: 배율을 믿을 수 있으니 다시 묻지
    않고 보관본 × 8 — main 이면 PER 0.6 · PBR 0.63 · 시가총액 15.2조원, 이 변경은 PER 5.1 · PBR 5.03 · 시가총액 121.4조원 (11-21 발행본의 PER · 시가총액)."""
    by, meta, lines, calls, path = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)})
    s = by["SNDK"]
    assert s["price"] == 79.24 and "SNDK" not in calls
    assert s["per"] == round(PX18 / EPS0 * K8, 1) == 5.1 and s["pbr"] == round(PX18 / BPS0 * K8, 2) == 5.03
    assert s["cap"] == round(PX18 * SH0 * K8 * FX / 1e12, 3) and abs(s["cap"] - 121.386) < 0.2   # 발행본 121.386조원
    assert s["val"] == round(AV0 * 8 * 79.24 * FX / 1e8, 1) and s["roe"] == 141.2
    k_main = 79.24 / PX18                                                           # main: 가격 비율만
    assert round(PX18 / EPS0 * k_main, 1) == 0.6 and round(PX18 * SH0 * k_main * FX / 1e12, 1) == 15.2
    x = _log(lines)
    assert x.startswith("  !! 미국 분할 뒤 보관본 맞춤") and "곱함 1 (SNDK ×8 (8:1 분할 2026-11-20 · 보관본 2026-11-19 · 기준 가격 755.12 → 오늘 79.24))" in x, x
    assert x.endswith("· 그래서 다시 물음 0"), x                                      # 리뷰 2차 S-B: 곱함도 크게
    assert _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]]}
    assert F.load_us_info(path)["SNDK"]["at"] == US19                                 # 보관본 그대로 (3일 되는 날 보통처럼 다시 받아요)
    (st, val), _r = _gate_of(by, meta)
    assert st == "WARN" and "폭 안 1종목 (가장 큰 차이 1.43배)" in val and "보관본에 분할 배율을 곱함 (날짜와 가격으로 고른 배율" in val and "1: SNDK ×8" in val, val


def test_fresh_details_still_on_the_old_share_count_keep_the_copy(tmp_path, monkeypatch):
    """리뷰 #176 1차: 4일 된 분할 전 보관본이라 보통처럼 다시 받았는데 야후의 새 PBR 이 분할 전 주당 장부가 (11-21 SNDK 그대로 0.63) — 보관본 × 8 을 써요."""
    by, meta, lines, calls, path = _run(tmp_path, monkeypatch, cache={"SNDK": entry("2026-11-17", PX18, pd_="2026-11-16")}, sndk_info=SNDK_STALE)
    s = by["SNDK"]
    assert calls.count("SNDK") == 1 and s["pbr"] == 5.03 and s["per"] == 5.1                   # 0.63 이 아니에요
    assert F.load_us_info(path)["SNDK"]["at"] == "2026-11-17"                                 # 보관본 그대로 (다음 실행이 또 맞춰 봐요)
    x = _log(lines)
    assert x.startswith("  !! ") and ("새로 받은 상세 정보의 주당 숫자가 분할 전 같아 (시가총액은 맞음) 보관본 × 배율을 씀 1 (야후가 아직 분할 전 주당 숫자일 수 "
                                      "있어요: SNDK pbr 8.00배)") in x, x
    assert _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]], "diff": [["SNDK", "pbr 8.00배"]]}
    (st, val), rep = _gate_of(by, meta)
    assert st == "WARN" and "새 상세 정보의 주당 숫자가 분할 전 같아 (시가총액은 맞음) 보관본 × 배율을 씀" in val and "1: SNDK pbr 8.00배" in val, val
    assert "폭 안 1종목" in val                                                                # 발행하는 PBR 은 PER × ROE 와 맞아요


def test_fresh_details_that_agree_replace_the_copy(tmp_path, monkeypatch):
    by, meta, lines, calls, path = _run(tmp_path, monkeypatch, cache={"SNDK": entry("2026-11-17", PX18, pd_="2026-11-16")}, sndk_info=SNDK_POST)
    e = F.load_us_info(path)["SNDK"]
    assert calls.count("SNDK") == 1 and e["at"] == US21 and e["pd"] == US20 and e["px"] == 79.24
    assert by["SNDK"]["per"] == round(SNDK_POST["trailingPE"], 1) and by["SNDK"]["pbr"] == round(SNDK_POST["priceToBook"], 2)
    assert _log(lines).startswith("· ") and _split_rec(meta) is None                           # 적을 것 없음 → usSrc.split 칸이 없어요 (오늘 받았으니 곱함 0)
    assert all(F.load_us_info(path)[t]["pd"] == US20 for t in ("AAPL", "MSFT", "NVDA"))


def test_a_copy_already_on_the_new_share_count_is_not_multiplied_and_is_asked_again(tmp_path, monkeypatch):
    """날짜로는 분할 전 보관본인데 기준 가격이 이미 분할 뒤 가격 (뉴욕 자정 무렵 실행에 야후가 분할을 미리 반영) — 곱하지 않고 다시 물어요 (odd)."""
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US20, 80.0)}, refuse={"SNDK"})
    assert calls.count("SNDK") == 3 and by["SNDK"]["per"] == round(PX18 / EPS0 * 79.24 / 80.0, 1)   # 받지 못해 예전 그대로 (곱하지 않음)
    x = _log(lines)
    assert x.startswith("  !! ") and "곱함 0" in x and "곱하지 않음 1 (보관본이 이미 분할 뒤 값일 수 있어요 · 다시 물음: SNDK (8:1 분할 2026-11-20" in x, x
    assert "그래서 다시 물음 1 (받지 못해 보관본 그대로 1: SNDK)" in x, x
    assert _split_rec(meta) == {"v": 1, "odd": ["SNDK"], "left": ["SNDK"]}
    (st, val), _r = _gate_of(by, meta)
    assert st == "WARN" and "곱하지 않고 다시 물음 1: SNDK" in val and "받지 못해 보관본 그대로 (숫자가 그 배율만큼 틀릴 수 있어요) 1: SNDK" in val, val


def test_s1_a_split_dated_after_the_us_date_that_yahoo_already_applied(tmp_path, monkeypatch):
    """리뷰 S1: 이틀 된 분할 전 보관본 · SNDK 8:1 날짜 11-21 · 미국 기준일 11-20 · 야후 시계열은 벌써 79.24 — main 이면 PER 0.6 · 조용히. 이제 × 8 · 크게."""
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)}, splits={"SNDK": [(US21, 8.0)]})
    assert by["SNDK"]["per"] == 5.1 and by["SNDK"]["pbr"] == 5.03 and "SNDK" not in calls
    x = _log(lines)
    assert x.startswith("  !! ") and "곱함 1 (SNDK ×8 (8:1 분할 2026-11-21" in x and "미국 기준일 뒤 날짜의 분할 1 (SNDK 8:1 분할 2026-11-21 (곱함))" in x, x
    assert _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]], "late": [["SNDK", True]]}
    assert meta["splits"] == [["SNDK", US21, 8.0]]
    (st, val), _r = _gate_of(by, meta, splits=[["SNDK", US21, 8.0]])
    assert st == "WARN" and "미국 기준일 뒤 날짜의 분할 (야후가 반영했으면 곱함) 1: SNDK (곱함)" in val, val


def test_s1_a_split_dated_after_the_us_date_that_yahoo_has_not_applied(tmp_path, monkeypatch):
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)}, splits={"SNDK": [(US21, 8.0)]}, last=760.0)
    assert by["SNDK"]["per"] == round(PX18 / EPS0 * 760.0 / PX18, 1) and "SNDK" not in calls      # 가격도 보관본도 분할 전 · 곱하지 않아요
    assert "미국 기준일 뒤 날짜의 분할 1 (SNDK 8:1 분할 2026-11-21 (곱하지 않음 · 보관본과 오늘 가격이 같은 주식 수로 보여요))" in _log(lines)
    assert _split_rec(meta) == {"v": 1, "late": [["SNDK", False]]}


def test_s2_a_big_price_change_with_no_known_split_asks_yahoo_again(tmp_path, monkeypatch):
    """리뷰 S2: 야후가 분할을 늦게 알려 분할 목록에 없는데 가격이 1/8 — 다시 물어요. 받지 못하면 예전 그대로 (크게 · 기록)."""
    cache = {"SNDK": entry(US19, PX18)}
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache=cache, splits={}, refuse={"SNDK"})
    assert calls.count("SNDK") == 3 and by["SNDK"]["per"] == 0.6
    x = _log(lines)
    assert x.startswith("  !! ") and "분할을 모르는데 가격이 2배 넘게 달라진 보관본 1 (늦게 알려진 분할일 수 있어요 · 다시 물음: SNDK (755.12 → 79.24))" in x, x
    assert _split_rec(meta) == {"v": 1, "jump": ["SNDK"], "left": ["SNDK"]}
    (st, val), _r = _gate_of(by, meta, splits=[])
    assert st == "WARN" and "분할을 모르는데 가격이 2배 넘게 달라진 보관본" in val and "SNDK" in val
    by2, meta2, lines2, calls2, path2 = _run(tmp_path / "ok", monkeypatch, cache=cache, splits={}, sndk_info=SNDK_POST)
    assert calls2.count("SNDK") == 1 and by2["SNDK"]["per"] == 5.1 and _split_rec(meta2) == {"v": 1, "jump": ["SNDK"]}   # 받았으면 새 숫자


def test_a_normal_day_logs_zero_and_writes_no_split_record(tmp_path, monkeypatch):
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, splits={})
    assert sorted(calls) == ["AAPL", "MSFT", "NVDA", "SNDK"]
    assert _log(lines) == "· 미국 분할 뒤 보관본 맞춤 (보관본의 기준 가격 뒤 분할 · 오늘 가격 × 배율 ÷ 그때 가격): 곱함 0 · 그래서 다시 물음 0"
    assert "split" not in meta["usSrc"] and meta["_usOwnInfoPd"] == {}


def test_an_unreadable_split_list_keeps_todays_behaviour_and_says_so(tmp_path, monkeypatch):
    """분할 목록을 읽지 못하면 (us_info_split_map 이 멈춤 — us_splits 부르는 차례와 상관없이) 배율 없이 예전 그대로 · 크게 · usSrc.split.err. 분할을 몰라도
    가격이 2배 밖인 보관본은 다시 물어요 (S2)."""
    def boom(recent, prev):
        raise RuntimeError("boom")
    monkeypatch.setattr(F, "us_info_split_map", boom)
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)}, refuse={"SNDK"})
    assert by["SNDK"]["per"] == round(PX18 / EPS0 * 79.24 / PX18, 1) == 0.6          # 예전 그대로 (가격 비율만)
    x = _log(lines, "미국 분할을 읽지 못해")
    assert x.startswith("  !! 미국 분할을 읽지 못해 (RuntimeError: boom)") and "보관본을 쓴 1종목은 예전 그대로" in x, x
    assert _split_rec(meta) == {"v": 1, "jump": ["SNDK"], "left": ["SNDK"], "err": "RuntimeError", "errN": 1}   # 종류 이름만 (리뷰 2차 S-A)
    assert meta["splits"] == [["SNDK", US20, 8.0]]                                  # 발행할 분할 목록은 그대로 읽어요
    (st, val), _r = _gate_of(by, meta)
    assert st == "WARN" and "분할을 읽지 못해 (RuntimeError) 보관본 맞춤을 하지 않음 — 그날 보관본을 쓴 1종목은 가격 비율만" in val, val


def test_a_ticker_without_a_split_column_uses_the_previous_publish(tmp_path, monkeypatch):
    real = F._split_col
    monkeypatch.setattr(F, "_split_col", lambda data, t: None if t == "SNDK" else real(data, t))
    prev = {"usPxDate": US19, "stocks": [], "splits": [["SNDK", US20, 8.0]]}
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)}, prev=prev)
    assert by["SNDK"]["per"] == 5.1
    assert any(x.startswith("  !! 오늘 다운로드에 분할 칸이 없는 미국 종목 1") and x.endswith("SNDK") for x in lines), lines
    assert _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]], "noCol": ["SNDK"]}


def test_a_carried_close_with_a_split_between_the_copy_and_its_date(tmp_path, monkeypatch):
    """마지막 확인 종가(pxc · pxd 11-19 · 분할 뒤 94.39) · 8:1 분할 11-18 · 보관본은 11-16 기준 (분할 전 755.12) → × 8 (그 종가 날짜까지의 분할)."""
    prev = {"usPxDate": US19, "stocks": [{"t": "SNDK", "nk": "Sandisk", "cls": "us", "ccy": "USD", "price": 94.39, "d1": -1.0, "vol": 90.0}]}
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18, pd_="2026-11-16")}, splits={"SNDK": [(US18, 8.0)]},
                                      prev=prev, blank={"SNDK"})
    s = by["SNDK"]
    assert s["pxc"] is True and s["pxd"] == US19 and s["price"] == 94.39 and "SNDK" not in calls
    k = 94.39 * 8 / PX18
    assert s["per"] == round(PX18 / EPS0 * k, 1) and s["pbr"] == round(PX18 / BPS0 * k, 2)
    assert meta["_usOwnInfoPd"] == {"SNDK": "2026-11-16"} and _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]]}


def test_etf_turnover_after_a_split_via_fetch_us(tmp_path, monkeypatch):
    """11-05 의 MTUM 4:1 모양: 분할 전 보관본($252 · 평균 거래량 1백만주 · 배당수익률 0.64%) · 오늘 $63 → 거래대금은 1백만 × 4 × $63 (main 은 × 1 · 4배 작음)."""
    etf = {"shortName": "iShares MSCI USA Momentum", "longName": "iShares MSCI USA Momentum Factor ETF", "quoteType": "ETF", "currency": "USD",
           "averageVolume": 1e6, "dividendYield": 0.64}
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"MTUM": entry(US19, 252.0, etf)}, splits={"MTUM": [(US20, 4.0)]},
                                      extra={"MTUM": (63.0, etf)})
    m = by["MTUM"]
    assert m["etf"] is True and "MTUM" not in calls
    assert m["val"] == round(1e6 * 4 * 63.0 * FX / 1e8, 1) and m["dy"] == 0.64                  # main: 거래대금 1/4 · 배당수익률 그대로 0.64 아님 (2.56)
    assert _split_rec(meta) == {"v": 1, "fit": [["MTUM", 4.0]]}


def test_the_zero_pbr_counter_uses_the_split_factor(tmp_path, monkeypatch):
    """보관본 PBR 0.03 · 8:1 — 가격 비율만이면 0.0037 (0.005 미만이라 빈 칸으로 셌어요) · 배율을 곱하면 0.025 그대로."""
    by, meta, lines, _c, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18, dict(SNDK_PRE, priceToBook=0.03,
                                                                                  returnOnEquity=0.03 * EPS0 / PX18))})
    # #188: ROE = PBR ÷ PER (회사 합계가 PBR 0.03 과 맞게 · 분할 뒤 주당 숫자 검사가 이 PBR 을 비우지 않아요)
    assert by["SNDK"]["pbr"] == round(0.03 * K8, 2) and "pbrZero" not in by["SNDK"]
    assert "· 미국 PBR 이 0.00 으로 반올림돼(0.005 미만) 빈 칸 — 가치 점수도 없음: 0곳" in lines


# ── 3b. 리뷰 2차 (#176) ───────────────────────────────────────────────────────
@pytest.mark.parametrize("err", [KeyError("None of [Index(['Stock Splits'], dtype='object')] are in the [columns]"),
                                 ValueError("cannot convert float NaN to integer"), TypeError("'NoneType' object is not subscriptable")])
def test_s_a_the_split_record_never_carries_a_bad_word(tmp_path, monkeypatch, err):
    """리뷰 2차 S-A: 판다스 오류 글이 data.json 에 들어가면 관문의 '글자에 nan·None·null·undefined 없음' 줄이 발행을 멈춰요 — 파일에는 종류 이름만."""
    def boom(recent, prev):
        raise err
    monkeypatch.setattr(F, "us_info_split_map", boom)
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)}, refuse={"SNDK"})
    rec = _split_rec(meta)
    assert rec["err"] == type(err).__name__
    bad = [(p_, v) for p_, v in V.text_values({"usSrc": meta["usSrc"]}) if V.BAD_WORD.search(v)]
    assert bad == [], bad
    assert any(x.startswith(f"  !! 미국 분할을 읽지 못해 ({type(err).__name__}: ") for x in lines)       # 오류 글은 로그에


def test_s_b_a_wrong_factor_is_loud_and_the_fresh_market_cap_undoes_it(tmp_path, monkeypatch):
    """리뷰 2차 S-B: 예전 모양 보관본(11-20 · 기준 가격 115 — 이미 분할 뒤) · 2:1 분할 날짜 11-20 · 오늘 79.24 (실제로 31% 내림). 날짜와 가격으로는 × 2 를
    골라요 (PER 이 2배로 나가요) — 그래서 곱함은 크게 남기고 관문이 경고해요. 다시 받는 날 새 시가총액이 배율 없이 맞으면 새 상세 정보를 써요."""
    post = {"shortName": "Wrong Co", "longName": "Wrong Co", "quoteType": "EQUITY", "financialCurrency": "USD", "currency": "USD",
            "trailingPE": 115 / 4.0, "priceToBook": 115 / 20.0, "returnOnEquity": 0.2, "marketCap": 115e9, "averageVolume": 5e6,
            "netIncomeToCommon": 4e9}          # #188: 회사 합계 (10억 주 × 주당순이익 4 · ROE 0.2 = 4 ÷ 주당 장부가 20) — 주당 숫자와 맞아요
    fresh = dict(post, trailingPE=79.24 / 4.0, priceToBook=79.24 / 20.0, marketCap=79.24e9)
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US20, 115.0, post)}, splits={"SNDK": [(US20, 2.0)]})
    assert "SNDK" not in calls and by["SNDK"]["per"] == round(115 / 4.0 * 79.24 * 2 / 115, 1) == 39.6      # 2배 (맞는 값 19.8)
    assert _log(lines).startswith("  !! ") and _split_rec(meta) == {"v": 1, "fit": [["SNDK", 2.0]]}
    (st, val), _r = _gate_of(by, meta, splits=[["SNDK", US20, 2.0]])
    assert st == "WARN" and "1: SNDK ×2" in val
    by2, meta2, lines2, calls2, path2 = _run(tmp_path / "day4", monkeypatch, cache={"SNDK": entry("2026-11-17", 115.0, post)},
                                             splits={"SNDK": [(US20, 2.0)]}, sndk_info=fresh)
    assert calls2.count("SNDK") == 1 and by2["SNDK"]["per"] == 19.8 and by2["SNDK"]["pbr"] == round(79.24 / 20.0, 2)
    assert F.load_us_info(path2)["SNDK"]["at"] == US21                                         # 새 상세 정보를 보관해요 (틀린 보관본으로 돌아가지 않아요)
    assert _split_rec(meta2) == {"v": 1, "unfit": [["SNDK", "cap 2.00배"]]}
    x = _log(lines2)
    assert x.startswith("  !! ") and "새 시가총액을 보니 보관본에 곱한 배율이 틀려 새 상세 정보를 씀 1 (보관본이 이미 분할 뒤 값이었어요: SNDK cap 2.00배)" in x, x
    (st2, val2), _r = _gate_of(by2, meta2, splits=[["SNDK", US20, 2.0]])
    assert st2 == "WARN" and "새 시가총액을 보니 보관본에 곱한 배율이 틀려 새 상세 정보를 씀" in val2


def test_fixed_table_rows_are_never_counted_twice(monkeypatch):
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("Q", US18): (8.0, "고정"), ("R", US18): (8.0, "고정")})
    m = F.us_info_split_map([["Q", US19, 8.0], ["R", US19, 8.0], ["R", US18, 8.0]], {"splits": [["Q", US18, 8.0]]})
    assert m == {"Q": [(US18, 8.0)], "R": [(US18, 8.0)]}, m                                    # × 64 가 아니에요


def test_split_view_drops_bad_ratios():
    v = F.us_info_split_view({"at": US19, "px": 100.0}, 99.0, US20, [(US20, 0.0), (US20, float("nan")), (US20, -2.0), (US20, None), (US20, "x")])
    assert v["hit"] == [] and v["f"] == 1.0 and not v["use"]


def test_a_fresh_entry_with_a_later_dated_split_is_not_recorded(tmp_path, monkeypatch):
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, splits={"SNDK": [(US21, 8.0)]}, sndk_info=SNDK_POST)
    assert "SNDK" in calls and _split_rec(meta) is None and _log(lines).startswith("· ")


def test_us_meta_drop_cleans_the_split_record():
    umeta = {"usSrc": {"v": 1, "own": {}, "split": {"v": 1, "fit": [["A", 8.0], ["B", 2.0]], "left": ["A"], "err": "KeyError", "errN": 2}}}
    F.us_meta_drop(umeta, [{"t": "A"}, {"t": "B"}], {"A"})
    assert umeta["usSrc"]["split"] == {"v": 1, "fit": [["B", 2.0]], "err": "KeyError", "errN": 2}
    um2 = {"usSrc": {"v": 1, "own": {}, "split": {"v": 1, "fit": [["A", 8.0]]}}}
    F.us_meta_drop(um2, [{"t": "A"}], {"A"})
    assert "split" not in um2["usSrc"]


def test_split_record_keeps_only_published_tickers():
    rec = {"v": 1, "fit": [["A", 8.0], ["Z", 2.0]], "late": [["A", True]], "odd": ["Z"], "diff": [["Z", "pbr 2.00배"]], "err": "KeyError", "errN": 0}
    assert F.us_split_rec_keep(rec, {"A"}) == {"split": {"v": 1, "fit": [["A", 8.0]], "late": [["A", True]], "err": "KeyError", "errN": 0}}
    assert F.us_split_rec_keep({"v": 1, "odd": ["Z"]}, {"A"}) == {} and F.us_split_rec_keep({"v": 1}, {"A"}) == {} and F.us_split_rec_keep(None, {"A"}) == {}


def test_bad_paths_keep_todays_behaviour_and_are_recorded(tmp_path, monkeypatch):
    real_view, real_cmp = F.us_info_split_view, F.us_info_fresh_vs_copy

    def view(e, price, basis, events):
        if price == 79.24:
            raise ValueError("boom")
        return real_view(e, price, basis, events)
    monkeypatch.setattr(F, "us_info_split_view", view)
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(US19, PX18)})
    assert by["SNDK"]["per"] == 0.6 and _split_rec(meta) == {"v": 1, "bad": ["SNDK"]}          # 예전 그대로 (가격 비율만)
    assert any(x.startswith("  !! 미국 분할 판단이 오류로 멈춘 종목 SNDK (ValueError: boom)") for x in lines)
    monkeypatch.setattr(F, "us_info_split_view", real_view)

    def cmp_(*a):
        raise KeyError("x")
    monkeypatch.setattr(F, "us_info_fresh_vs_copy", cmp_)
    by2, meta2, lines2, _c, _p2 = _run(tmp_path / "b", monkeypatch, cache={"SNDK": entry("2026-11-17", PX18)}, sndk_info=SNDK_STALE)
    assert by2["SNDK"]["pbr"] == round(SNDK_STALE["priceToBook"], 2) and _split_rec(meta2) == {"v": 1, "bad": ["SNDK"]}   # 새 상세 정보
    assert any("새 상세 정보와 분할 전 보관본을 맞춰 보다 오류로 멈춘 종목 SNDK (KeyError)" in x for x in lines2)
    monkeypatch.setattr(F, "us_info_fresh_vs_copy", real_cmp)


@pytest.mark.parametrize("at, used", [("2026-11-07", True), ("2026-11-06", False)])
def test_the_14_day_limit_applies_to_a_copy_with_a_split(tmp_path, monkeypatch, at, used):
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(at, PX18)}, refuse={"SNDK"})
    assert calls.count("SNDK") == 3                                                           # 3일 넘어 보통처럼 다시 물었는데 거절
    if used:                                                                                  # 14일 · 보관본 × 8
        assert by["SNDK"]["per"] == 5.1 and _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]]}
    else:                                                                                     # 15일 · 쓰지 않아요 (상세 정보 없음 · 예전 그대로)
        assert "per" not in by["SNDK"] and _split_rec(meta) is None


def test_a_carried_close_keeps_the_copy_when_fresh_details_are_pre_split(tmp_path, monkeypatch):
    """마지막 확인 종가(pxd 11-19 · 94.39 · 8:1 분할 11-18 뒤) · 4일 된 분할 전 보관본 · 오늘 받은 상세 정보는 야후 시세 가격(79.24) 기준인데 PBR 이 분할 전."""
    prev = {"usPxDate": US19, "stocks": [{"t": "SNDK", "nk": "Sandisk", "cls": "us", "ccy": "USD", "price": 94.39, "d1": -1.0, "vol": 90.0}]}
    by, meta, lines, calls, path = _run(tmp_path, monkeypatch, cache={"SNDK": entry("2026-11-17", PX18, pd_="2026-11-16")},
                                        splits={"SNDK": [(US18, 8.0)]}, prev=prev, blank={"SNDK"}, sndk_info=dict(SNDK_STALE, currentPrice=79.24))
    s = by["SNDK"]
    assert s["pxc"] is True and s["price"] == 94.39 and calls.count("SNDK") == 1
    assert s["pbr"] == round(PX18 / BPS0 * 94.39 * 8 / PX18, 2) and s["per"] == round(PX18 / EPS0 * 94.39 * 8 / PX18, 1)
    assert F.load_us_info(path)["SNDK"]["at"] == "2026-11-17"
    assert _split_rec(meta) == {"v": 1, "fit": [["SNDK", 8.0]], "diff": [["SNDK", "pbr 8.00배"]]}
    assert any("마지막 확인 종가 종목 1개의 상세 정보: 오늘 받아 야후 시세 가격에 맞춤 0 · 3일 안에 받은 보관본 (또는 오늘 받지 못해 보관본) 1" in x
               for x in lines), [x for x in lines if "마지막 확인 종가 종목" in x]


# ── 4. 나중에 분할이 나와 야후 봉으로 되돌리는 행 (us_own_split_late) ─────────────────────
def test_restore_factor_after_both_the_close_and_the_copy_with_the_guard():
    row, y = {"t": "TD", "pxd": US18, "pxc": True, "price": 60.0}, {"t": "TD", "price": 31.0, "pxd": US18}
    ev = [(US19, 2.0)]
    assert F.us_own_restore_split(row, y, ev, US20, "2026-11-17") == (2.0, "x")       # 보관본도 분할 전 → 곱해요
    assert F.us_own_restore_split(row, y, ev, US20, US20) == (1.0, "none")            # 분할 뒤 시세 가격으로 받은 보관본 → 이미 새 주식 수
    assert F.us_own_restore_split(row, y, ev, US20, None) == (1.0, "noDay")           # 모르면 예전 그대로 (크게)
    assert F.us_own_restore_split(row, y, [(US18, 2.0)], US20, "2026-11-17") == (1.0, "none")   # 실은 종가 날짜의 분할 (이미 반영)
    assert F.us_own_restore_split(row, {**y, "price": 60.0}, ev, US20, "2026-11-17") == (1.0, "odd")   # 야후 가격이 분할 전 그대로 → 곱하지 않음
    assert F.us_own_restore_split(row, y, [(US21, 2.0)], US20, "2026-11-17") == (2.0, "x")    # 미국 기준일 뒤 날짜도 가격으로 (리뷰 S1)
    r = F.us_own_restore({**row, "per": 30.0, "pbr": 3.0, "cap": 100.0, "val": 10.0, "dy": 1.0}, y, [], split=2.0)
    assert (r["per"], r["pbr"], r["cap"], r["val"], r["dy"]) == (31.0, 3.1, 103.333, 10.3, 0.97)   # 31 × 2 ÷ 60


def test_late_split_restore_uses_the_copy_day_from_fetch_us(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    rows = [dict(t="TD", nk="TD", cls="us", price=60.0, pxd=US19, pxc=True, per=30.0, pbr=3.0, cap=100.0, val=10.0, dy=1.0, dk="x")]
    for ipd, y_px, want, rec in (({"TD": US18}, 31.0, 31.0, {"rx": [["TD", 2.0]]}), ({"TD": US20}, 31.0, 15.5, None),
                                 ({}, 31.0, 15.5, {"rNoDay": ["TD"]}), ({"TD": US18}, 60.0, 30.0, {"rOdd": ["TD"]})):
        lines.clear()
        umeta = {"usPxDate": US20, "splits": [], "splitsNoCol": [], "usInfoPartial": [], "usFcurUnknown": [], "usInfo": [1, 1], "usExtraMissing": {},
                 "_usOwnYahoo": {"TD": {"t": "TD", "nk": "TD", "cls": "us", "price": y_px, "pxd": US18}}, "_usOwnInfoPd": ipd,
                 "usSrc": {"v": 1, "own": {"v": 1, "n": 1, "codes": ["TD"], "same": [], "newer": [], "split": [], "aged": []}}}
        kept, _sp = F.us_own_split_late([dict(r) for r in rows], umeta, {"splits": [["TD", US20, 2.0]]}, {"stocks": []})
        assert kept[0]["price"] == y_px and "pxc" not in kept[0] and kept[0]["per"] == want, (ipd, kept[0])
        assert umeta["usSrc"].get("split") == ({"v": 1, **rec} if rec else None), umeta["usSrc"]
        x = next(z for z in lines if "야후 봉으로 되돌린 미국 종목 1의 상세 숫자" in z)
        assert x.startswith("  !! ") and ("곱함 1 (TD ×2)" in x if rec and "rx" in rec else "곱함 0" in x), x
    assert "보관본 날짜를 몰라 곱하지 않음 0 · 곱하면 가격 비율이 1 에서 더 멀어져 곱하지 않음 1 (TD)" in x


# ── 5. 관문: '미국 분할 뒤 상세 숫자' (경고만) ─────────────────────────────────────
SNDK_LIVE = {"t": "SNDK", "nk": "Sandisk Corporation", "cls": "us", "etf": False, "price": 79.24, "per": 5.1, "pbr": 0.63, "roe": 141.2,
             "dy": 0.0, "cap": 121.386, "vz": 99}                                    # 2026-11-21 발행본 (미국 기준일 11-20) 그대로


def _gate(data):
    rep = V.Report()
    V.check_us_split_pbr(rep, data)
    return rows_of(rep)[ROW], rep


def test_gate_row_names_sndk_on_the_live_shape():
    data = {"usPxDate": US20, "splits": [["MTUM", "2026-11-05", 4.0], ["QUAL", "2026-11-05", 4.0], ["SNDK", US20, 8.0], ["SOXX", "2026-11-05", 3.0]],
            "stocks": [SNDK_LIVE, {"t": "MTUM", "cls": "us", "etf": True, "price": 60.27}, {"t": "QUAL", "cls": "us", "etf": True},
                       {"t": "SOXX", "cls": "us", "etf": True}]}
    (st, val), rep = _gate(data)
    assert st == "WARN", val
    assert ("최근 분할 4건 · 회사 주식 1종목 (ETF · 펀드 · fcur · 목록에 없음 3종목은 보지 않음) · 폭 밖 1종목: SNDK 8:1 분할 2026-11-20 — PBR 0.63 ↔ "
            "PER 5.1 × ROE 141.2% = 7.20 (11.4배 · 허용 2.83배)") == val
    assert rep.details and rep.details[0][1] == ["SNDK: PBR 0.63 · PER 5.1 · ROE 141.2% → PER × ROE 7.20 (11.43배 · 허용 2.83배) · 8:1 분할 2026-11-20"]
    ok = {**data, "stocks": [{**SNDK_LIVE, "per": 7.8, "pbr": 7.76}]}              # 11-11 발행본의 숫자 (분할 전 · 1.42배)
    (st2, val2), _r = _gate(ok)
    assert st2 == "PASS" and "폭 안 1종목 (가장 큰 차이 1.42배)" in val2, val2


def test_gate_band_and_what_it_looks_at():
    assert V.us_split_band([8.0]) == pytest.approx(math.sqrt(8)) and V.us_split_band([0.1]) == pytest.approx(math.sqrt(10))
    assert V.us_split_band([2.0]) == 1.5 and V.us_split_band([1.05]) == 1.5 and V.us_split_band([2.0, 5.0]) == 1.5   # 가장 작은 배율 · 바닥 1.5
    co = lambda t, **kw: {"t": t, "cls": "us", "etf": False, "per": 20.0, "pbr": 4.0, "roe": 20.0, **kw}   # PER × ROE = 4.0
    data = {"usPxDate": US20, "splits": [["A", US20, 2.0], ["B", "2026-11-10", 0.1], ["C", "2026-10-15", 8.0], ["D", US20, 8.0], ["E", US20, 8.0],
                                         ["F", US20, 8.0], ["G", "2026-11-21", 8.0], ["H", "2026-11-01", 2.0], ["H", "2026-11-15", 3.0],
                                         ["I", "2026-11-19x", 8.0], ["J", US20, 1.0], ["K", US20, 1.5]],
            "stocks": [co("A", pbr=2.0),                     # 2:1 · 2배 차이 > 1.5 → 경고
                       co("B", pbr=1.0),                     # 1:10 병합 · 4배 > 3.16 → 경고
                       co("C", pbr=0.5),                     # 30일 넘은 분할 (10-15) → 보지 않아요
                       co("D", fcur="TWD", pbr=0.1),          # 재무제표 통화가 달러가 아님 → 보지 않아요
                       co("E", roe=-5.0),                    # ROE 0 이하 → 맞춰 볼 수 없음
                       co("F", pbr=3.0),                     # 1.33배 → 폭 안
                       co("G", pbr=0.1),                     # 미국 기준일 뒤 날짜 → 보지 않아요
                       co("H", pbr=2.4),                     # 두 번 (2:1 · 3:1) · 1.67배 > 1.5 → 경고
                       co("I", pbr=0.1),                     # 날짜 모양이 틀림 → 보지 않아요 ('주식 분할 목록' 줄이 봐요)
                       co("J", pbr=0.1),                     # 배율 1 은 분할이 아니에요
                       co("K", pbr=2.7),                     # 3:2 · 1.48배 ≤ 1.5 → 폭 안 (이 줄이 보지 못하는 크기)
                       {"t": "F", "cls": "kr", "per": 1.0}]}
    (st, val), _r = _gate(data)
    assert st == "WARN" and val.startswith("최근 분할 8건 · 회사 주식 6종목 (ETF · 펀드 · fcur · 목록에 없음 1종목은 보지 않음) · 폭 밖 3종목: A 2:1 분할"), val
    assert "B 1:10 병합 2026-11-10" in val and "H 2:1 분할 2026-11-01 · 3:1 분할 2026-11-15" in val
    assert not any(f"{t} " in val for t in "CGIJ") and "1:1 병합" not in val
    assert "폭 안 2종목 (가장 큰 차이 1.48배)" in val and "맞춰 보지 않음 1: E" in val
    (st0, val0), _r = _gate({"usPxDate": US20, "splits": [["OLD", "2020-08-31", 4.0]], "stocks": [co("OLD", pbr=0.1)]})
    assert (st0, val0) == ("PASS", "최근 분할 0건 · 회사 주식 0종목")
    (st1, val1), _r = _gate({"usPxDate": US20, "splits": [["Z", US20, 8.0]], "stocks": [co("Z", per=0.1, roe=0.001, pbr=5.0)]})
    assert st1 == "WARN" and "(1000배 넘게 · 허용 2.83배)" in val1, val1                    # PER × ROE 가 0 에 가까우면 배수 글을 잘라요


@pytest.mark.parametrize("data, why", [
    ({"usPxDate": US20, "splits": "x", "stocks": []}, "splits 가 목록이 아님"),
    ({"usPxDate": "nope", "splits": [], "stocks": []}, "usPxDate 를 읽지 못함"),
    ({"usPxDate": "2026-11-20x", "splits": [], "stocks": []}, "usPxDate 를 읽지 못함"),
    ({"splits": [], "stocks": []}, "usPxDate 를 읽지 못함"),
    ("not a dict", "usPxDate 를 읽지 못함"),
])
def test_gate_row_warns_when_it_cannot_read_its_inputs(data, why):
    (st, val), _r = _gate(data)
    assert st == "WARN" and val.startswith("검사가 멈췄어요: ValueError: " + why), val


def test_gate_row_skips_a_file_without_splits_and_says_which():
    for data, head in (({"usPxDate": US20, "stocks": [SNDK_LIVE]}, "splits 칸 없음"), ({"usPxDate": US20, "splits": None, "stocks": [SNDK_LIVE]}, "splits 가 null")):
        rep = V.Report()
        V.check_us_split_pbr(rep, data)
        assert rep.rows == [(ROW, "—", head + " — 아래 '주식 분할 목록 (splits)' 줄이 봐요 (직전 발행본에 splits 가 있었으면 그 줄이 실패해요)", "SKIP")]
    # usSrc.split 이 있으면 건너뛰지 않아요
    (st, val), _r = _gate({"usPxDate": US20, "stocks": [], "usSrc": {"split": {"v": 1, "left": ["SNDK"]}}})
    assert st == "WARN" and val.startswith("splits 칸 없음 — PBR 맞춰 보기는 건너뜀 · 다시 물었는데 받지 못해 보관본 그대로"), val


def test_gate_row_reads_the_split_record():
    base = {"usPxDate": US20, "splits": [], "stocks": []}
    (st, val), _r = _gate({**base, "usSrc": {"split": {"v": 1, "fit": [["SNDK", 8.0]], "rx": [["TD", 2.0]]}}})
    assert st == "WARN" and "1: SNDK ×8" in val and "야후 봉으로 되돌리며 분할 배율을 곱함 1: TD ×2" in val, val      # 리뷰 2차 S-B: 곱함도 경고
    (st, val), _r = _gate({**base, "usSrc": {"split": {"v": 1, "errN": 4}}})
    assert st == "WARN" and "분할을 읽지 못해 (까닭 모름) 보관본 맞춤을 하지 않음 — 그날 보관본을 쓴 4종목은 가격 비율만" in val, val
    rec = {"v": 1, "odd": ["A"], "jump": ["B"], "left": ["A", "B"], "late": [["C", False]], "diff": [["D", "pbr 8.00배"]], "unfit": [["I", "cap 2.00배"]],
           "bad": ["E"], "noCol": ["F"], "rNoDay": ["G"], "rOdd": ["H"], "err": "RuntimeError", "errN": 3}
    (st, val), rep = _gate({**base, "usSrc": {"split": rec}})
    assert st == "WARN"
    for k, (w, why) in V.US_SPLIT_REC_WHY.items():
        if k in rec:
            assert w and f"usSrc.split {k} — {why}" in {t for t, _x in rep.details}, k
    assert "그날 보관본을 쓴 3종목은 가격 비율만" in val and len(val) <= 600                     # 값 칸이 잘려도 분할을 읽지 못함이 먼저
    assert {x for _t, xs in rep.details for x in xs} >= {"C (곱하지 않음)", "D pbr 8.00배", "I cap 2.00배", "A", "G", "H"}
    assert {t for t, _x in rep.details} >= {f"usSrc.split {k} — {V.US_SPLIT_REC_WHY[k][1]}" for k in ("odd", "left", "diff")}
    for bad in ("x", {"v": 1, "left": "SNDK"}, {"v": 1, "fit": [["SNDK"]]}, {"v": 1, "what": ["X"]}, {"v": 1, "err": 3}, {"v": 1, "errN": True}):
        (st, val), _r = _gate({**base, "usSrc": {"split": bad}})
        assert st == "WARN" and "usSrc.split 모양이 잘못" in val, (bad, val)


def test_gate_row_warns_when_its_own_check_crashes(monkeypatch):
    def boom(data):
        raise KeyError("boom")
    monkeypatch.setattr(V, "us_split_pbr_scan", boom)
    (st, val), _r = _gate({"usPxDate": US20, "splits": [], "stocks": []})
    assert st == "WARN" and val.startswith("검사가 멈췄어요: KeyError")


def _with_split_stock(files, pbr, rec=None):
    """좋은 fixture 의 미국 회사 하나를 오늘 8:1 분할한 회사로 (PER 5.1 · ROE 141.2% · PBR 은 받은 값) · 꼭 있어야 할 분할도 함께."""
    d = files["data"]
    s = next(x for x in d["stocks"] if x["t"] == "U0001")
    s.update(per=5.1, pbr=pbr, roe=141.2)
    d["splits"] = [list(x) for x in V.MUST_SPLITS] + [["U0001", d["usPxDate"], 8.0]]
    d["splitsFrom"], d["splitsAsOf"], d["splitsSrc"] = V.SPLITS_FROM, d["usPxDate"], "yahoo"
    d["splitsInfo"] = {"noCol": 0, "gap": [], "diff": [], "fixed": [], "fixedKept": []}
    if rec is not None:
        d.setdefault("usSrc", {"v": 1, "own": {}})["split"] = rec
    return files


@pytest.mark.parametrize("mode", ["publish", "bootstrap", "live"])
def test_gate_row_never_fails_in_any_mode(mode, monkeypatch):
    def run(pbr, crash=False, rec=None):
        cur, prev, final = good_pair()
        cur = _with_split_stock(cur, pbr, rec)
        _with_split_stock(prev, 7.2)
        if crash:
            monkeypatch.setattr(V, "us_split_pbr_scan", lambda data: 1 / 0)
        rep = V.run_checks(cur, None if mode != "publish" else prev, final, dt.date(2026, 10, 31), mode=mode, count_between=lambda a, b: 1,
                           sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                           now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=hilo_of(cur, V.MUST))
        monkeypatch.setattr(V, "us_split_pbr_scan", REAL_SCAN)
        return rep
    good, bad, crashed = run(7.2), run(0.63), run(0.63, crash=True)
    recd = run(7.2, rec={"v": 1, "left": ["U0001"], "diff": [["U0001", "pbr 8.00배"]], "err": "KeyError", "errN": 2})
    fails = lambda rep: sorted(r[0] for r in rep.failed)
    assert rows_of(good)[ROW][0] == "PASS" and rows_of(bad)[ROW][0] == "WARN" and rows_of(crashed)[ROW][0] == "WARN"
    assert rows_of(recd)[ROW][0] == "WARN" and "U0001 pbr 8.00배" in rows_of(recd)[ROW][1]
    assert "U0001 8:1 분할" in rows_of(bad)[ROW][1] and rows_of(crashed)[ROW][1].startswith("검사가 멈췄어요: ZeroDivisionError")
    assert fails(bad) == fails(good) == fails(crashed) == fails(recd) and ROW not in fails(bad), (mode, fails(bad))


REAL_SCAN = V.us_split_pbr_scan
