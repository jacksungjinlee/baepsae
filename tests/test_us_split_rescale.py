# -*- coding: utf-8 -*-
"""2026-11-23 (감사 · SNDK 8:1 분할 2026-11-20): 분할 뒤 미국 상세 정보 보관본 맞춤 · 다시 받기 · 관문의 새 경고 줄.

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 시험은 그대로):
- 파이프라인: 야후 상세 정보 보관본의 기준 가격(px)이 분할 전 주식 수 기준이면 PER · PBR · 시가총액 · 배당수익률 · 거래대금을 오늘 가격 × 배율 ÷ 그때
  가격으로 맞춰요 (fetch_data.us_rescale · apply_us_info split · us_info_split_k) — 분할 없음 · 병합 · 두 번 · 기준 가격 날짜(pd · 예전 항목은 받은 날
  하루 전) · 곱하면 더 멀어지는 때는 예전 그대로 · 분할보다 오래된 보관본은 오늘 다시 받아요 (us_info_due) · 분할 목록을 읽지 못하면 예전 그대로 (크게)
  · 나중에 분할이 나와 야후 봉으로 되돌리는 행도 같은 배율 (us_own_restore_split)
- 2026-11-21 발행본 모양의 SNDK: 다시 받기를 야후가 거절해 분할 전 보관본을 쓰면 main 은 PER 0.6 · 시가총액 15조원 · 이 변경은 발행본의 PER 5.1 ·
  시가총액 121.4조원 (그날 실제로는 분할 뒤에 새로 받은 상세 정보였고, 야후 PBR 이 분할 전 주당 장부가라 0.63 이었어요 — 관문 줄이 그것을 이름으로 적어요)
- 관문: '미국 분할 뒤 PBR ↔ PER × ROE' 줄은 경고만 — 어떤 모드에서도 실패하지 않고, 검사가 멈춰도 경고예요
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
US20, US19, US18 = "2026-11-20", "2026-11-19", "2026-11-18"
# 2026-11-11 발행본의 SNDK (분할 전): 가격 977.69 · PER 7.8 · PBR 7.76 · 주식 수 142.3백만 · 평균 거래량 10.78백만 → 주당순이익 125.3 · 주당 장부가 126.0
EPS0, BPS0, SH0, AV0 = 977.69 / 7.8, 977.69 / 7.76, 142.3e6, 10.78e6
PX18 = 755.12                       # 2026-11-18 종가 (분할 전 · 11-20 의 79.24 는 11-19 의 94.39 에서 −16.05%)
SNDK_PRE = {"shortName": "Sandisk Corporation", "longName": "Sandisk Corporation", "quoteType": "EQUITY", "sector": "Technology",
            "industry": "Computer Hardware", "financialCurrency": "USD", "currency": "USD", "country": "United States",
            "trailingPE": PX18 / EPS0, "priceToBook": PX18 / BPS0, "returnOnEquity": 1.412, "marketCap": PX18 * SH0,
            "averageVolume": AV0, "dividendYield": 0.0, "totalRevenue": 1e10, "operatingMargins": 0.3}


def rows_of(rep):
    return {r[0]: (r[3], r[1]) for r in rep.rows}


# ── 1. 순수 함수: 배율 · 분할 창 · 분할 목록 · 다시 받기 ───────────────────────────────
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


def test_split_window_is_after_the_anchor_day_and_up_to_the_price_basis():
    ev = [("2026-11-10", 2.0), ("2026-11-17", 3.0)]
    assert F.us_info_split_k({"at": "2026-11-21", "pd": "2026-11-09"}, US20, ev) == (6.0, ev)
    assert F.us_info_split_k({"at": "2026-11-21", "pd": "2026-11-12"}, US20, ev) == (3.0, [ev[1]])
    assert F.us_info_split_k({"at": "2026-11-21", "pd": "2026-11-17"}, US20, ev) == (1.0, [])       # 그날 가격은 이미 분할 뒤
    assert F.us_info_split_k({"at": "2026-11-21", "pd": "2026-11-09"}, "2026-11-16", ev) == (2.0, [ev[0]])   # 가격 기준 날짜 뒤 분할은 빼요
    assert F.us_info_split_k({"at": "2026-11-21", "pd": "2026-11-09"}, US20, [("2026-11-18", 0.1)]) == (0.1, [("2026-11-18", 0.1)])
    # 예전 항목 (pd 없음): 받은 날(한국 날짜) 하루 전 — 한국 날짜 D 의 실행이 가진 미국 종가는 D−1 이하
    assert F.us_info_anchor_day({"at": "2026-11-20"}) == US19 and F.us_info_anchor_day({"at": "2026-11-20", "pd": US18}) == US18
    assert F.us_info_anchor_day({"at": "2026-11-20", "pd": "11/18"}) == US19                         # 읽지 못한 pd → 받은 날 하루 전
    assert F.us_info_anchor_day({"at": "nope"}) is None and F.us_info_anchor_day(None) is None
    assert F.us_info_split_k({"at": "2026-11-20"}, US20, [(US20, 8.0)]) == (8.0, [(US20, 8.0)])      # 11-20 실행은 11-19 종가 · 그 뒤 분할
    assert F.us_info_split_k({"at": "2026-11-21"}, US20, [(US20, 8.0)]) == (1.0, [])                 # 11-21 실행은 11-20 (분할 뒤) 종가
    assert F.us_info_split_k({"at": "nope"}, US20, [(US20, 8.0)]) == (1.0, [])
    # 가격 기준 날짜: 마지막 확인 종가는 그 종가 날짜 · 다른 행은 미국 기준일 (야후 시계열은 오늘까지의 분할을 반영해요)
    assert F.us_price_basis_day({"pxc": True, "pxd": US18}, dt.date(2026, 11, 20)) == US18
    assert F.us_price_basis_day({"pxd": US18}, dt.date(2026, 11, 20)) == US20 == F.us_price_basis_day({}, dt.date(2026, 11, 20))


def test_split_map_uses_the_same_sources_as_the_published_list(monkeypatch):
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("Z", US18): (None, "분사"), ("W", "2026-11-02"): (0.5, "병합 · 야후에 없음")})
    prev = {"splits": [["X", "2026-11-10", 2.0], ["OLD", "2020-08-31", 4.0], ["bad", "x", 2.0]]}
    recent = [["X", "2026-11-12", 2.0],                      # 야후가 날짜를 옮긴 같은 사건 → 한 번만 (지난 발행본 날짜)
              ["X", "2026-11-10", 3.0],                      # 같은 종목 · 날짜인데 배율이 다름 → 지난 발행본 값 (merge_splits 와 같아요)
              ["SNDK", US20, 8.0], ["Z", US18, 1.5], ["Y", "nope", 2.0], ["Y", US18, -1.0]]
    m = F.us_info_split_map(recent, prev)
    assert m == {"X": [("2026-11-10", 2.0)], "OLD": [("2020-08-31", 4.0)], "SNDK": [(US20, 8.0)], "W": [("2026-11-02", 0.5)]}, m
    assert F.us_info_split_map(None, None) == {"W": [("2026-11-02", 0.5)]}


def test_guard_keeps_todays_behaviour_when_the_split_moves_the_ratio_away_from_one():
    assert F.us_info_split_ok(100.0, 800.0, 8.0)                 # 분할 전 보관본 → 곱해요
    assert F.us_info_split_ok(100.0, 10.0, 0.1)
    assert not F.us_info_split_ok(100.0, 100.0, 8.0)             # 보관본이 이미 분할 뒤 값 (곱하면 8배) → 예전 그대로
    assert F.us_info_split_ok(270.0, 800.0, 8.0)                 # 분할 뒤 2.7배 올라도 (√8 = 2.83 안) 곱해요
    assert not F.us_info_split_ok(300.0, 800.0, 8.0)             # √8 넘게 오르면 날짜만으로 믿지 않아요
    assert not F.us_info_split_ok(None, 800.0, 8.0) and not F.us_info_split_ok(100.0, None, 8.0)


def test_an_entry_older_than_a_split_is_due_for_refetch():
    today = dt.date(2026, 11, 21)
    sp = [(US20, 8.0)]
    fresh = {"at": "2026-11-20", "pd": US19, "px": 640.0, "k": F.US_INFO_SCHEMA, "info": {}}
    assert F.us_info_due(fresh, today) is False                                   # 하루 된 보관본 (예전 규칙: 3일)
    assert F.us_info_due(fresh, today, sp) is True and F.us_info_split_due(fresh, sp, today)
    after = {**fresh, "at": "2026-11-21", "pd": US20}
    assert F.us_info_due(after, today, sp) is False                               # 분할 뒤 가격으로 받은 항목
    legacy = {"at": "2026-11-20", "px": 640.0, "k": F.US_INFO_SCHEMA, "info": {}}  # pd 없음 → 11-19
    assert F.us_info_due(legacy, today, sp) is True and F.us_info_due({**legacy, "at": "2026-11-21"}, today, sp) is False
    assert F.us_info_due(fresh, today, [("2026-11-24", 2.0)]) is False            # 오늘 뒤 날짜의 분할
    assert F.us_info_due(fresh, today, [("2026-11-01", 2.0)]) is False            # 보관본보다 앞의 분할
    assert F.us_info_due(fresh, today, None) is False and F.us_info_due(fresh, today, []) is False
    assert F.us_info_due(None, today, sp) is True                                 # 없으면 예전처럼 받아요


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
    before = _apply(info, 10.0, 10.0)
    rev = _apply(info, 10.0, 100.0, split=0.1)                                       # 1:10 병합 · $10 → $100
    two = _apply(info, 600.0, 100.0, split=2.0 * 3.0)                                # 2:1 뒤 3:1 · $600 → $100
    ref = _apply(info, 600.0, 600.0)
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
        cols = {}
        for t in tickers:
            if t not in series:
                continue
            cols[(t, "Close")] = series[t]
            cols[(t, "Dividends")] = pd.Series(0.0, index=series[t].index)
            sp = pd.Series(0.0, index=series[t].index)
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


def _run(tmp_path, monkeypatch, cache=None, refuse=(), sndk_info=None, splits=None):
    """미국 기준일 2026-11-20 (SNDK 8:1 분할 그날) · 한국 날짜 11-21 실행. 야후 시계열은 분할을 반영해요 (SNDK 11-19 94.39 → 11-20 79.24)."""
    today_us = dt.date(2026, 11, 20)
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)
    syms = ["AAPL", "MSFT", "NVDA", "SNDK"]

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    series = {"_spx": walk(1, 6700.0), "_fx": pd.Series(FX, index=days)}
    for i, t in enumerate(syms[:3]):
        series[t] = walk(10 + i, 100.0 + i)
    sn = walk(20, 94.39)
    sn.iloc[-1] = 79.24
    series["SNDK"] = sn
    infos = {t: dict(SNDK_PRE, shortName=t + " Co", longName=t + " Inc.") for t in syms[:3]}
    infos["SNDK"] = sndk_info or dict(SNDK_PRE)
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
    out, _b, _fx, fx_last, _v, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev={"usPxDate": US19, "stocks": []})
    assert fx_last == pytest.approx(FX)
    return {r["t"]: r for r in out}, meta, lines, calls, path


def _log(lines, head="미국 분할 뒤 보관본 맞춤"):
    got = [x for x in lines if head in x]
    assert len(got) == 1, lines
    return got[0]


def test_sndk_shape_refused_refetch_uses_the_split_corrected_copy(tmp_path, monkeypatch):
    """11-19 (한국 날짜) 에 받은 분할 전 보관본 · 11-21 실행이 분할 뒤라 다시 받으려는데 야후가 거절 → 보관본에 8 을 곱해요.
    main 이면 PER 0.6 · PBR 0.63 · 시가총액 15.2조원 (가치 점수 맨 위) · 이 변경은 PER 5.1 · PBR 5.0 · 시가총액 121.4조원 (11-21 발행본의 PER · 시가총액)."""
    cache = {"SNDK": {"at": "2026-11-19", "px": PX18, "k": F.US_INFO_SCHEMA, "info": dict(SNDK_PRE)}}   # 예전 모양 (pd 없음 → 11-18)
    by, meta, lines, calls, path = _run(tmp_path, monkeypatch, cache=cache, refuse={"SNDK"})
    s = by["SNDK"]
    assert s["price"] == 79.24 and calls.count("SNDK") == 3                         # 분할 뒤라 다시 물었어요 (세 번 · 예전 쉬는 시간 그대로)
    k = 79.24 * 8 / PX18
    assert s["per"] == round(PX18 / EPS0 * k, 1) == 5.1 and s["pbr"] == round(PX18 / BPS0 * k, 2) == 5.03
    assert s["cap"] == round(PX18 * SH0 * k * FX / 1e12, 3) and abs(s["cap"] - 121.386) < 0.2   # 발행본 121.386조원
    assert s["val"] == round(AV0 * 8 * 79.24 * FX / 1e8, 1) and s["roe"] == 141.2
    main_k = 79.24 / PX18                                                           # main: 가격 비율만
    assert round(PX18 / EPS0 * main_k, 1) == 0.6 and round(PX18 * SH0 * main_k * FX / 1e12, 1) == 15.2
    x = _log(lines)
    assert x.startswith("  !! 미국 분할 뒤 보관본 맞춤") and "1종목 (SNDK 8:1 분할 2026-11-20 (보관본 2026-11-19" in x, x
    assert "분할 뒤라 다시 받기 1 (받음 0 · 받지 못해 보관본 1: SNDK)" in x, x
    assert F.load_us_info(path)["SNDK"]["at"] == "2026-11-19"                         # 보관본은 그대로 · 다음 실행이 또 물어요
    # 관문 줄: PER × ROE 와 맞아요 (5.1 × 1.412 = 7.2 ↔ 5.03 · 1.43배 < √8)
    rep = V.Report()
    V.check_us_split_pbr(rep, {"usPxDate": US20, "splits": [["SNDK", US20, 8.0]], "stocks": list(by.values())})
    assert rows_of(rep)[ROW][0] == "PASS", rows_of(rep)[ROW]


def test_entry_older_than_the_split_is_refetched_and_records_its_anchor_day(tmp_path, monkeypatch):
    post = dict(SNDK_PRE, trailingPE=79.24 / (EPS0 / 8), priceToBook=79.24 / (BPS0 / 8), marketCap=79.24 * SH0 * 8, averageVolume=AV0 * 8)
    cache = {"SNDK": {"at": "2026-11-20", "pd": US19, "px": 755.0, "k": F.US_INFO_SCHEMA, "info": dict(SNDK_PRE)}}   # 하루 된 보관본
    by, meta, lines, calls, path = _run(tmp_path, monkeypatch, cache=cache, sndk_info=post)
    assert calls.count("SNDK") == 1
    e = F.load_us_info(path)["SNDK"]
    assert e["at"] == "2026-11-21" and e["pd"] == US20 and e["px"] == 79.24
    assert by["SNDK"]["per"] == round(post["trailingPE"], 1) and by["SNDK"]["pbr"] == round(post["priceToBook"], 2)   # 배율 1 (오늘 받은 값)
    x = _log(lines)
    assert x.startswith("· 미국 분할 뒤 보관본 맞춤") and "0종목 · 분할 뒤라 다시 받기 1 (받음 1 · 받지 못해 보관본 0)" in x, x
    assert all(F.load_us_info(path)[t]["pd"] == US20 for t in ("AAPL", "MSFT", "NVDA"))
    # 다음 실행 (같은 날): 분할 뒤에 받은 항목이라 다시 받지 않아요
    by2, _m, lines2, calls2, _p = _run(tmp_path, monkeypatch, sndk_info=post)
    assert calls2 == [] and _log(lines2).endswith("0종목 · 분할 뒤라 다시 받기 0")


def test_a_normal_day_logs_zero_and_changes_nothing(tmp_path, monkeypatch):
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, splits={})
    assert sorted(calls) == ["AAPL", "MSFT", "NVDA", "SNDK"]
    assert _log(lines) == "· 미국 분할 뒤 보관본 맞춤 (보관본의 기준 가격 뒤 분할 · 오늘 가격 × 배율 ÷ 그때 가격): 0종목 · 분할 뒤라 다시 받기 0"
    assert "_usOwnInfoPd" in meta and meta["_usOwnInfoPd"] == {}


def test_a_copy_already_on_the_new_share_count_is_not_multiplied(tmp_path, monkeypatch):
    """날짜로는 분할 전 보관본인데 기준 가격이 이미 분할 뒤 가격 (뉴욕 자정 무렵 실행에 야후가 분할을 미리 반영) — 곱하면 8배로 멀어져 예전 그대로 · 크게."""
    cache = {"SNDK": {"at": "2026-11-20", "px": 80.0, "k": F.US_INFO_SCHEMA, "info": dict(SNDK_PRE)}}
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache=cache, refuse={"SNDK"})
    assert by["SNDK"]["per"] == round(PX18 / EPS0 * 79.24 / 80.0, 1)
    x = _log(lines)
    assert x.startswith("  !! ") and "0종목" in x and "곱하지 않음 1" in x and "SNDK 8:1 분할 2026-11-20" in x.split("곱하지 않음")[1], x


def test_an_unreadable_split_list_keeps_todays_behaviour_and_says_so(tmp_path, monkeypatch):
    real = F.us_splits
    n = {"calls": 0}

    def flaky(data, codes, today, lo=None):
        n["calls"] += 1
        if n["calls"] == 1:                        # 상세 정보 단계의 분할 읽기 (야후 종가가 없는 종목이 없어 처음 부름이에요)
            raise RuntimeError("boom")
        return real(data, codes, today, lo)
    monkeypatch.setattr(F, "us_splits", flaky)
    cache = {"SNDK": {"at": "2026-11-19", "px": PX18, "k": F.US_INFO_SCHEMA, "info": dict(SNDK_PRE)}}
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache=cache, refuse={"SNDK"})
    assert "SNDK" not in calls                                                     # 분할을 모르면 다시 받기도 예전 그대로 (2일 된 보관본)
    assert by["SNDK"]["per"] == round(PX18 / EPS0 * 79.24 / PX18, 1) == 0.6           # 예전 그대로 (가격 비율만)
    x = _log(lines, "미국 분할을 읽지 못해")
    assert x.startswith("  !! 미국 분할을 읽지 못해 (RuntimeError: boom)") and "보관본을 쓴 1종목은 예전 그대로" in x, x
    assert meta["splits"] == [["SNDK", US20, 8.0]]                                  # 발행할 분할 목록은 그대로 읽어요


def test_a_ticker_without_a_split_column_uses_the_previous_publish(tmp_path, monkeypatch):
    """분할 칸이 없는 종목은 지난 발행본 · 고정 표의 분할만 (크게 남겨요)."""
    real = F._split_col
    monkeypatch.setattr(F, "_split_col", lambda data, t: None if t == "SNDK" else real(data, t))
    cache = {"SNDK": {"at": "2026-11-19", "px": PX18, "k": F.US_INFO_SCHEMA, "info": dict(SNDK_PRE)}}
    today_prev = {"usPxDate": US19, "stocks": [], "splits": [["SNDK", US20, 8.0]]}
    orig = F.fetch_us

    def with_prev(start, today, rf, **kw):
        return orig(start, today, rf, **{**kw, "prev": today_prev})
    monkeypatch.setattr(F, "fetch_us", with_prev)
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache=cache, refuse={"SNDK"})
    assert by["SNDK"]["per"] == 5.1
    assert any(x.startswith("  !! 오늘 다운로드에 분할 칸이 없는 미국 종목 1") and x.endswith("SNDK") for x in lines), lines


# ── 4. 나중에 분할이 나와 야후 봉으로 되돌리는 행 (us_own_split_late) ─────────────────────
def test_restore_multiplies_only_splits_after_both_the_close_and_the_copy():
    ev = [(US19, 2.0)]
    row = {"t": "TD", "pxd": US18, "pxc": True, "price": 60.0}
    assert F.us_own_restore_split(row, ev, US20, "2026-11-17") == 2.0             # 보관본도 분할 전 → 곱해요
    assert F.us_own_restore_split(row, ev, US20, US20) == 1.0                    # 분할 뒤 시세 가격으로 받은 보관본 → 이미 새 주식 수
    assert F.us_own_restore_split(row, ev, US20, None) == 1.0                    # 모르면 예전 그대로
    assert F.us_own_restore_split(row, [(US18, 2.0)], US20, "2026-11-17") == 1.0  # 실은 종가 날짜의 분할 (이미 반영)
    r = F.us_own_restore({**row, "per": 30.0, "pbr": 3.0, "cap": 100.0, "val": 10.0, "dy": 1.0}, {"t": "TD", "price": 31.0, "pxd": US18}, [], split=2.0)
    assert (r["per"], r["pbr"], r["cap"], r["val"], r["dy"]) == (31.0, 3.1, 103.333, 10.3, 0.97)   # 31 × 2 ÷ 60


def test_late_split_restore_uses_the_copy_day_from_fetch_us():
    rows = [dict(t="TD", nk="TD", cls="us", price=60.0, pxd=US19, pxc=True, per=30.0, pbr=3.0, cap=100.0, val=10.0, dy=1.0, dk="x")]
    y = {"t": "TD", "nk": "TD", "cls": "us", "price": 31.0, "pxd": US18}
    for ipd, want in (({"TD": US18}, 31.0), ({"TD": US20}, 15.5), ({}, 15.5)):
        umeta = {"usPxDate": US20, "splits": [], "splitsNoCol": [], "usInfoPartial": [], "usFcurUnknown": [], "usInfo": [1, 1], "usExtraMissing": {},
                 "_usOwnYahoo": {"TD": dict(y)}, "_usOwnInfoPd": ipd,
                 "usSrc": {"v": 1, "own": {"v": 1, "n": 1, "codes": ["TD"], "same": [], "newer": [], "split": [], "aged": []}}}
        kept, _sp = F.us_own_split_late([dict(r) for r in rows], umeta, {"splits": [["TD", US20, 2.0]]}, {"stocks": []})
        assert kept[0]["price"] == 31.0 and "pxc" not in kept[0] and kept[0]["per"] == want, (ipd, kept[0])


# ── 5. 관문: '미국 분할 뒤 PBR ↔ PER × ROE' (경고만) ─────────────────────────────────
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
    # 11-11 발행본의 숫자 (분할 전 · 1.42배)라면 폭 안
    ok = {**data, "stocks": [{**SNDK_LIVE, "per": 7.8, "pbr": 7.76}]}
    (st2, val2), _r = _gate(ok)
    assert st2 == "PASS" and "폭 안 1종목 (가장 큰 차이 1.42배)" in val2, val2


def test_gate_band_and_what_it_looks_at():
    assert V.us_split_band([8.0]) == pytest.approx(math.sqrt(8)) and V.us_split_band([0.1]) == pytest.approx(math.sqrt(10))
    assert V.us_split_band([2.0]) == 1.5 and V.us_split_band([1.05]) == 1.5 and V.us_split_band([2.0, 5.0]) == 1.5   # 가장 작은 배율 · 바닥 1.5
    co = lambda t, **kw: {"t": t, "cls": "us", "etf": False, "per": 20.0, "pbr": 4.0, "roe": 20.0, **kw}   # PER × ROE = 4.0
    data = {"usPxDate": US20, "splits": [["A", US20, 2.0], ["B", "2026-11-10", 0.1], ["C", "2026-10-15", 8.0], ["D", US20, 8.0], ["E", US20, 8.0],
                                         ["F", US20, 8.0], ["G", "2026-11-21", 8.0], ["H", "2026-11-01", 2.0], ["H", "2026-11-15", 3.0]],
            "stocks": [co("A", pbr=2.0),                     # 2:1 · 2배 차이 > 1.5 → 경고
                       co("B", pbr=1.0),                     # 1:10 병합 · 4배 > 3.16 → 경고
                       co("C", pbr=0.5),                     # 30일 넘은 분할 (10-15) → 보지 않아요
                       co("D", fcur="TWD", pbr=0.1),          # 재무제표 통화가 달러가 아님 → 보지 않아요
                       co("E", roe=-5.0),                    # ROE 0 이하 → 맞춰 볼 수 없음
                       co("F", pbr=3.0),                     # 1.33배 → 폭 안
                       co("G", pbr=0.1),                     # 미국 기준일 뒤 날짜 → 보지 않아요
                       co("H", pbr=2.4),                     # 두 번 (2:1 · 3:1) · 1.67배 > 1.5 → 경고
                       {"t": "F", "cls": "kr", "per": 1.0}]}
    (st, val), _r = _gate(data)
    assert st == "WARN" and val.startswith("최근 분할 7건 · 회사 주식 5종목 (ETF · 펀드 · fcur · 목록에 없음 1종목은 보지 않음) · 폭 밖 3종목: A 2:1 분할"), val
    assert "B 1:10 병합 2026-11-10" in val and "H 2:1 분할 2026-11-01 · 3:1 분할 2026-11-15" in val and "C " not in val and "G " not in val
    assert "폭 안 1종목 (가장 큰 차이 1.33배)" in val and "맞춰 보지 않음 1: E" in val
    (st0, val0), _r = _gate({"usPxDate": US20, "splits": [["OLD", "2020-08-31", 4.0]], "stocks": [co("OLD", pbr=0.1)]})
    assert (st0, val0) == ("PASS", "최근 분할 0건 · 회사 주식 0종목")


@pytest.mark.parametrize("data, why", [
    ({"usPxDate": US20, "splits": "x", "stocks": []}, "splits 가 목록이 아님"),
    ({"usPxDate": "nope", "splits": [], "stocks": []}, "usPxDate 를 읽지 못함"),
    ({"splits": [], "stocks": []}, "usPxDate 를 읽지 못함"),
    ("not a dict", "usPxDate 를 읽지 못함"),
])
def test_gate_row_warns_when_it_cannot_read_its_inputs(data, why):
    (st, val), _r = _gate(data)
    assert st == "WARN" and val.startswith("검사가 멈췄어요: ValueError: " + why), val


def test_gate_row_skips_a_file_without_splits():
    rep = V.Report()
    V.check_us_split_pbr(rep, {"usPxDate": US20, "stocks": [SNDK_LIVE]})
    assert rep.rows == [(ROW, "—", "splits 칸 없음 (위 '주식 분할 목록 (splits)' 줄이 경고해요)", "SKIP")]


def test_gate_row_warns_when_its_own_check_crashes(monkeypatch):
    def boom(data):
        raise KeyError("boom")
    monkeypatch.setattr(V, "us_split_pbr_scan", boom)
    (st, val), _r = _gate({"usPxDate": US20, "splits": [], "stocks": []})
    assert st == "WARN" and val.startswith("검사가 멈췄어요: KeyError")


def _with_split_stock(files, pbr):
    """좋은 fixture 의 미국 회사 하나를 오늘 8:1 분할한 회사로 (PER 5.1 · ROE 141.2% · PBR 은 받은 값) · 꼭 있어야 할 분할도 함께."""
    d = files["data"]
    s = next(x for x in d["stocks"] if x["t"] == "U0001")
    s.update(per=5.1, pbr=pbr, roe=141.2)
    d["splits"] = [list(x) for x in V.MUST_SPLITS] + [["U0001", d["usPxDate"], 8.0]]
    d["splitsFrom"], d["splitsAsOf"], d["splitsSrc"] = V.SPLITS_FROM, d["usPxDate"], "yahoo"
    d["splitsInfo"] = {"noCol": 0, "gap": [], "diff": [], "fixed": [], "fixedKept": []}
    return files


@pytest.mark.parametrize("mode", ["publish", "bootstrap", "live"])
def test_gate_row_never_fails_in_any_mode(mode, monkeypatch):
    def run(pbr, crash=False):
        cur, prev, final = good_pair()
        cur = _with_split_stock(cur, pbr)
        _with_split_stock(prev, 7.2)
        if crash:
            monkeypatch.setattr(V, "us_split_pbr_scan", lambda data: 1 / 0)
        rep = V.run_checks(cur, None if mode != "publish" else prev, final, dt.date(2026, 10, 31), mode=mode, count_between=lambda a, b: 1,
                           sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                           now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=hilo_of(cur, V.MUST))
        monkeypatch.setattr(V, "us_split_pbr_scan", REAL_SCAN)
        return rep
    good, bad, crashed = run(7.2), run(0.63), run(0.63, crash=True)
    fails = lambda rep: sorted(r[0] for r in rep.failed)
    assert rows_of(good)[ROW][0] == "PASS" and rows_of(bad)[ROW][0] == "WARN" and rows_of(crashed)[ROW][0] == "WARN"
    assert "U0001 8:1 분할" in rows_of(bad)[ROW][1] and rows_of(crashed)[ROW][1].startswith("검사가 멈췄어요: ZeroDivisionError")
    assert fails(bad) == fails(good) == fails(crashed) and ROW not in fails(bad), (mode, fails(bad))


REAL_SCAN = V.us_split_pbr_scan
