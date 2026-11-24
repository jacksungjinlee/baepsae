# -*- coding: utf-8 -*-
"""분할 뒤 30일 안의 미국 회사 주당 숫자 검사 (2026-11-24 · SNDK) — fetch_data.py us_recent_splits · us_split_check · us_split_stopped ·
us_split_step · fetch_us(호출) · us_meta_drop 과 validate_data.py check_us_split_cut (경고만) · src/v2/fcur.js (splCut 을 fgnCut 처럼). 네트워크 없음.

- SNDK 는 2026-11-20 8:1 분할 뒤 야후 주당순이익이 923.7달러로 나와 PER 0.1 이 나갔어요 — 회사 합계(순이익 ÷ 주식 수 ≈ 17.06)의 약 54배 (분할
  배율 8배가 아니에요) · 시가총액 ÷ 순이익 5.1.
- 외국 회사 검사(us_foreign_cuts)와 같은 비교 · 같은 종류 · 앱의 같은 줄 (co.fgnCut · co.fgnNoCmp · co.fgnStopped). 허용 폭은 분할 크기
  (max(1.5, √배율) · 리뷰 1차 S1) · 맞춰 보지 못한 currency · norecord 는 co.fgnNoCmp (N1) · mismatch 표시는 30일이 지나도 맞을 때까지 (S2).
  맞는 숫자는 비우지 않아요.
- 종목 표시는 splCut — 관문의 외국 회사 줄(fgnCut 은 외국 회사에만)은 그대로이고, 새 줄은 경고만이에요.
값은 2026-11-24 야후 그대로 (필요한 칸만)."""
import copy
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

ROW = V.US_SPLIT_ROW
FOREIGN = "미국 상장 외국 회사: 회사 합계와 맞춘 PER·PBR·배당수익률만"
LINE = "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요."
TODAY, US_DAY = dt.date(2026, 11, 14), dt.date(2026, 11, 13)
SPLIT_DAY = "2026-11-03"                       # 오늘(KST)에서 11일 전


def yi(short, **kw):
    i = {"shortName": short, "longName": short, "quoteType": "EQUITY", "currency": "USD", "financialCurrency": "USD",
         "country": "United States", "sector": "Technology", "industry": "Computer Hardware", "averageVolume": 1e7,
         "longBusinessSummary": f"{short} does things."}
    i.update(kw)
    return i


# 2026-11-24 야후 (SNDK 그대로) · 맞는 회사 · 회사 합계를 주지 않은 회사 · 분할이 없는 회사
SNDK = yi("Sandisk Corporation", marketCap=99841597440, netIncomeToCommon=19421999104, trailingPE=0.09495507, priceToBook=5.572073,
          returnOnEquity=1.41174, dividendYield=0.0)
GOOD = yi("Good Split Inc", marketCap=120e9, netIncomeToCommon=3e9, trailingPE=40.4, priceToBook=12.1, returnOnEquity=0.30,
          dividendYield=1.0)
NOFIN = yi("No Totals Inc", trailingPE=30.0, priceToBook=5.0, dividendYield=0.0)          # 시가총액 · 순이익 · ROE 를 받지 못함
PLAIN = yi("Plain Old Inc", marketCap=50e9, netIncomeToCommon=1e9, trailingPE=5.0, priceToBook=2.0, returnOnEquity=0.1,
           dividendYield=0.0)                                                                    # PER 5 ↔ 50 — 분할이 없어 보지 않아요


def rec(t, price, info):
    r = {"t": t, "nk": t, "ne": t, "cls": "us", "ccy": "USD", "fxu": True, "price": price, "etf": False}
    assert F.apply_us_info(r, dict(info), price, 1470.0, today=TODAY) is True
    return r


def divs(prices, paid):
    """다운로드 모양 (티커, 칸): Close · Dividends (paid = {티커: [(날짜, 달러)]})."""
    days = pd.bdate_range("2025-11-01", US_DAY)
    cols = {}
    for t, p in prices.items():
        cols[(t, "Close")] = pd.Series(p, index=days)
        dv = pd.Series(0.0, index=days)
        for d, v in paid.get(t, []):
            dv[pd.Timestamp(d)] = v
        cols[(t, "Dividends")] = dv
    return pd.DataFrame(cols)


def setup():
    out = [rec("SNDK", 87.71, SNDK), rec("GOOD", 101.0, GOOD), rec("NOFIN", 50.0, NOFIN), rec("PLN", 20.0, PLAIN)]
    cache = {t: {"at": "2026-11-14", "px": r["price"], "k": F.US_INFO_SCHEMA, "info": dict(i)}
             for (t, i), r in zip((("SNDK", SNDK), ("GOOD", GOOD), ("NOFIN", NOFIN), ("PLN", PLAIN)), out)}
    data = divs({r["t"]: r["price"] for r in out}, {"GOOD": [("2026-02-10", 0.25), ("2026-05-10", 0.25), ("2026-08-10", 0.25),
                                                             ("2026-11-04", 0.26)]})
    return out, cache, data


RECENT = {"SNDK": SPLIT_DAY, "GOOD": SPLIT_DAY, "NOFIN": SPLIT_DAY}


@pytest.fixture
def lines(monkeypatch):
    got = []
    monkeypatch.setattr(F, "log", got.append)
    return got


# ── 파이프라인 ─────────────────────────────────────────────
def test_sndk_like_per_is_blanked_with_the_reason(lines):
    out, cache, data = setup()
    by = {r["t"]: r for r in out}
    assert by["SNDK"]["per"] == 0.1 and by["SNDK"]["pbr"] == 5.57 and by["SNDK"]["dy"] == 0.0      # 발행된 모양 (PER 0.1)
    got = F.us_split_check(out, cache, data, US_DAY, RECENT)
    assert "per" not in by["SNDK"] and by["SNDK"]["splCut"] == {"per": "mismatch"}
    assert (by["SNDK"]["pbr"], by["SNDK"]["dy"]) == (5.57, 0.0)                                   # 맞는 PBR (1.30배) · 0% 는 그대로
    assert ["SNDK", "per", "주가 ÷ 주당순이익 0.09 ↔ 시가총액 ÷ 순이익 5.14 (54.14배)"] in got["cut"]
    assert got["kind"]["SNDK"] == {"per": "mismatch"} and "fgnCut" not in by["SNDK"]
    assert any(x.startswith("  !! 최근 30일 안에 분할한 미국 회사의 주당 숫자") and "PER 비움 2곳 (SNDK, NOFIN)" in x for x in lines), lines
    assert any("SNDK PER: 주가 ÷ 주당순이익 0.09 ↔ 시가총액 ÷ 순이익 5.14 (54.14배) [mismatch] (분할 2026-11-03)" in x for x in lines), lines


def test_an_agreeing_stock_with_a_recent_split_is_untouched(lines):
    out, cache, data = setup()
    before = copy.deepcopy(next(r for r in out if r["t"] == "GOOD"))
    got = F.us_split_check(out, cache, data, US_DAY, RECENT)
    good = next(r for r in out if r["t"] == "GOOD")
    assert good == before and "splCut" not in good                              # PER 40.4 ↔ 40 · PBR 12.1 ↔ 12 · 배당 1.0% ↔ 1.01달러 ÷ 101
    assert "GOOD" in got["checked"] and "GOOD" not in got["kind"]


def test_no_split_is_untouched_and_nothing_else_moves(lines):
    out, cache, data = setup()
    before = {r["t"]: copy.deepcopy(r) for r in out}
    F.us_split_check(out, cache, data, US_DAY, RECENT)
    after = {r["t"]: r for r in out}
    assert after["PLN"] == before["PLN"] and after["PLN"]["per"] == 5.0          # 회사 합계와 맞지 않아도 분할이 없으면 보지 않아요
    for t in ("SNDK", "NOFIN"):
        changed = {k for k in set(before[t]) | set(after[t]) if before[t].get(k) != after[t].get(k)}
        assert changed <= {"per", "pbr", "splCut"}, (t, changed)


def test_missing_company_totals_take_the_existing_cant_compare_path(lines):
    """회사 합계(시가총액 · 순이익 · ROE)를 받지 못하면 외국 회사와 같은 '맞춰 볼 수 없음' 길: 스위치 own → nocompare-own (앱 줄 co.fgnNoCmp)."""
    out, cache, data = setup()
    got = F.us_split_check(out, cache, data, US_DAY, RECENT)
    nofin = next(r for r in out if r["t"] == "NOFIN")
    want = V.US_FGN_NOCMP_KIND[V.US_FGN_NOCMP]
    assert nofin["splCut"] == {"pbr": want, "per": want} and "per" not in nofin and "pbr" not in nofin and nofin["dy"] == 0.0
    assert ["NOFIN", "per", V.US_FGN_NOCMP_WHY["per"]] in got["cut"] and ["NOFIN", "pbr", V.US_FGN_NOCMP_WHY["pbr"]] in got["cut"]


def test_no_cached_details_means_nothing_to_blank_and_no_dividend_record_is_norecord(lines):
    out, cache, _data = setup()
    cache.pop("GOOD")
    got = F.us_split_check(out, cache, None, US_DAY, RECENT, no_info=frozenset({"GOOD"}))
    by = {r["t"]: r for r in out}
    assert "GOOD" in got["checked"] and "splCut" not in by["GOOD"]
    assert by["SNDK"]["splCut"] == {"dy": "norecord", "per": "mismatch"} and "dy" not in by["SNDK"]   # 배당 기록 칸이 없는 날: 외국 회사와 같아요


def test_foreign_fcur_and_etfs_are_skipped_by_name(lines):
    out, cache, data = setup()
    out += [{"t": "SOXX", "cls": "us", "price": 140.22, "etf": True, "per": 33.4, "pbr": 0.37, "dy": 0.24},
            {"t": "BP", "cls": "us", "price": 45.7, "etf": False, "per": 20.8},
            {"t": "TSM", "cls": "us", "price": 300.0, "etf": False, "fcur": "TWD"}]
    recent = {**RECENT, "SOXX": "2026-11-05", "BP": "2026-11-05", "TSM": "2026-11-05"}
    got = F.us_split_check(out, cache, data, US_DAY, recent, foreign=frozenset({"BP", "TSM"}))
    assert got["skip"] == {"foreign": ["BP", "TSM"], "fcur": [], "etf": ["SOXX"]}
    soxx = next(r for r in out if r["t"] == "SOXX")
    assert soxx["pbr"] == 0.37 and "splCut" not in soxx
    assert any("ETF · 펀드라 회사 합계가 없어 보지 않음 1곳 (SOXX)" in x and "외국 회사라 위 검사가 봄 2곳 (BP, TSM)" in x for x in lines), lines


def test_reason_text_never_carries_none(lines):
    """야후가 재무제표 통화를 주지 않은 회사: 외국 회사처럼 세 칸 currency — 기록의 글에 'None' 이 없어요 (관문 '글자에 … None 없음' 줄)."""
    out, cache, data = setup()
    cache["SNDK"]["info"].pop("financialCurrency")
    got = F.us_split_check(out, cache, data, US_DAY, RECENT)
    sndk = next(r for r in out if r["t"] == "SNDK")
    assert sndk["splCut"] == {"dy": "currency", "pbr": "currency", "per": "currency"}
    for _t, _f, w in got["cut"]:
        assert not V.BAD_WORD.search(w), w
    assert any(w.startswith(F.US_FOREIGN_CUR_WHY) for _t, _f, w in got["cut"])


def test_recent_window_and_sources():
    carry = F.us_carry_splits([["SNDK", "2026-11-20", 8.0]], {"splits": [["MTUM", "2026-11-05", 4.0], ["OLD", "2026-10-13", 2.0],
                                                                      ["EDGE", "2026-10-24", 2.0], ["BAD", "11-05", 2.0]]})
    end, today = dt.date(2026, 11, 23), dt.date(2026, 11, 24)
    got = F.us_recent_splits(carry, ["SNDK", "MTUM", "OLD", "EDGE", "BAD", "NONE"], end, today)
    assert got == {"EDGE": "2026-10-24", "MTUM": "2026-11-05", "SNDK": "2026-11-20"}           # 30일 앞 (10-24) 까지 · 10-13 은 밖
    carry["FUT"] = {"2026-11-25"}
    carry["TDY"] = {"2026-11-24"}
    assert set(F.us_recent_splits(carry, ["FUT", "TDY"], end, today)) == {"TDY"}               # 오늘(KST)까지
    assert F.us_recent_splits(carry, ["SNDK"], end, today) == {"SNDK": "2026-11-20"}           # 오늘 목록에 있는 종목만


def test_a_crashed_check_blanks_the_rest_as_stopped(monkeypatch, lines):
    out, cache, data = setup()
    real = F.us_foreign_cuts
    calls = []

    def boom(rec_, info, div12, days=F.US_FOREIGN_DIV_DAYS, band=None):
        calls.append(rec_["t"])
        if rec_["t"] == "GOOD":
            raise RuntimeError("시험")
        return real(rec_, info, div12, days, band=band)
    monkeypatch.setattr(F, "us_foreign_cuts", boom)
    got = F.us_split_step(out, cache, data, US_DAY, TODAY, {"splits": [[t, SPLIT_DAY, 2.0] for t in RECENT]})
    by = {r["t"]: r for r in out}
    assert calls == ["SNDK", "GOOD"]
    assert by["SNDK"]["splCut"] == {"per": "mismatch"} and by["SNDK"]["pbr"] == 5.57                 # 끝까지 본 종목은 그대로
    assert by["GOOD"]["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"}
    assert by["NOFIN"]["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"}
    assert not any(k in by["GOOD"] for k in ("per", "pbr", "dy")) and by["PLN"]["per"] == 5.0
    assert got["err"] == "RuntimeError" and got["kind"]["GOOD"] == by["GOOD"]["splCut"]
    assert all(w == "검사가 멈춤 (RuntimeError)" for t, _f, w in got["cut"] if t != "SNDK")
    assert any(x.startswith("  !! 최근 분할한 미국 회사 검사가 멈췄어요 (RuntimeError: 시험)") for x in lines), lines
    r = gate_row({"usPxDate": "2026-11-13", "asOf": "2026-11-14", "splits": [[t, SPLIT_DAY, 2.0] for t in RECENT], "usSplitChk": got}, out)
    assert r[3] == "WARN" and "검사가 멈춰 맞춰 보지 않고 비운 회사 2곳: GOOD, NOFIN" in r[1] and "모양" not in r[1], r


def test_unknown_recent_list_blanks_nothing_loudly(monkeypatch, lines):
    out, cache, data = setup()
    before = copy.deepcopy(out)
    monkeypatch.setattr(F, "us_carry_splits", lambda *a: (_ for _ in ()).throw(ValueError("시험")))
    got = F.us_split_step(out, cache, data, US_DAY, TODAY, {})
    assert out == before and got["recent"] is None and got["err"] == "ValueError"
    assert any(x.startswith("  !! 최근 분할한 미국 종목을 정하다가 멈췄어요 (ValueError: 시험)") for x in lines), lines


def test_meta_drop_removes_a_dropped_stock_from_the_record(lines):
    out, cache, data = setup()
    rec_ = F.us_split_step(out, cache, data, US_DAY, TODAY, {"splits": [[t, SPLIT_DAY, 2.0] for t in RECENT]})
    umeta = {"usSplitChk": rec_}
    F.us_meta_drop(umeta, out, {"SNDK"})
    u = umeta["usSplitChk"]
    assert "SNDK" not in u["checked"] and "SNDK" not in u["kind"] and "SNDK" not in u["recent"]
    assert all(x[0] != "SNDK" for x in u["cut"]) and {x[0] for x in u["cut"]} == {"NOFIN"}


# ── fetch_us (가짜 야후 · 오늘 다운로드의 분할 칸) ─────────────────────
def _fake_yf(series, splits, infos):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"] if tickers != F.FX_TICKER else series["_spx"] * 0 + 1470.0})
        cols = {}
        for t in tickers:
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
            return dict(infos[self.t])
    return types.SimpleNamespace(download=download, Ticker=Ticker)


def _fetch(tmp_path, monkeypatch, step=None):
    days = pd.bdate_range(TODAY - dt.timedelta(days=500), US_DAY)

    def walk(seed, last):
        s = pd.Series(np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    prices = {"SNDK": 87.71, "GOOD": 101.0, "PLN": 20.0}
    series = {"_spx": walk(1, 6700.0), **{t: walk(i + 2, p) for i, (t, p) in enumerate(prices.items())}}
    infos = {"SNDK": SNDK, "GOOD": dict(GOOD, dividendYield=0.0), "PLN": PLAIN}
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series, {"SNDK": [(SPLIT_DAY, 8.0)], "GOOD": [(SPLIT_DAY, 4.0)]}, infos))
    monkeypatch.setattr(F, "us_tickers", lambda names_out=None: sorted(prices))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: US_DAY)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    if step is not None:
        monkeypatch.setattr(F, "us_split_step", step)
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    us, *_rest, meta = F.fetch_us(TODAY - dt.timedelta(days=500), TODAY, 0.03)
    meta.pop("_index")
    return us, meta, lines


def test_fetch_us_runs_the_check_and_rows_are_otherwise_as_before(tmp_path, monkeypatch):
    us, meta, lines = _fetch(tmp_path / "a", monkeypatch)
    base, _m, _l = _fetch(tmp_path / "b", monkeypatch, step=lambda out, *a, **k: None)     # 이 검사 없이 (main 과 같은 행)
    by, old = {r["t"]: r for r in us}, {r["t"]: r for r in base}
    u = meta["usSplitChk"]
    assert u["recent"] == {"GOOD": SPLIT_DAY, "SNDK": SPLIT_DAY} and u["checked"] == ["GOOD", "SNDK"] and u["days"] == 30
    assert u["cut"] == [["SNDK", "per", "주가 ÷ 주당순이익 0.09 ↔ 시가총액 ÷ 순이익 5.14 (54.14배)"]]
    assert by["SNDK"]["splCut"] == {"per": "mismatch"} and "per" not in by["SNDK"] and old["SNDK"]["per"] == 0.1
    assert {k: v for k, v in by["SNDK"].items() if k != "splCut"} == {k: v for k, v in old["SNDK"].items() if k != "per"}
    assert by["GOOD"] == old["GOOD"] and by["PLN"] == old["PLN"]
    assert [x for x in meta["splits"] if x[0] == "SNDK"] == [["SNDK", SPLIT_DAY, 8.0]]
    assert any(x.startswith("· 최근 30일 안에 분할한 미국 종목 (2026-10-14 ~ 2026-11-14): 2곳: GOOD(2026-11-03 · 폭 2.00배), "
                            "SNDK(2026-11-03 · 폭 2.83배)") for x in lines), lines
    assert u["band"] == {"GOOD": 2.0, "SNDK": 2.8284} and u["held"] == {}                     # 4:1 → √4 · 8:1 → √8
    json.dumps(meta["usSplitChk"], allow_nan=False, ensure_ascii=False)
    r = gate_row({"usPxDate": "2026-11-13", "asOf": "2026-11-14", "splits": meta["splits"], "usSplitChk": u}, us)
    assert r[3] == "PASS" and "비운 칸 PER 1 · PBR 0 · 배당 0 (SNDK.per)" in r[1], r


# ── #176 의 보관본 맞춤과 함께 (같은 fetch_us · #176 시험의 가짜 야후: 미국 기준일 11-20 · 한국 11-21 · SNDK 8:1 분할 11-20) ─────────
# 이 검사는 #176 이 보관본 × 배율로 맞춘 뒤에 돌아요. 맞춰 보는 것은 상세 정보 안의 비 (PER ↔ 시가총액 ÷ 순이익 · PBR ↔ 그 × ROE) 라서 보관본에
# 곱한 배율과 상관없어요: 맞는 분할 전 보관본 × 8 은 그대로 · 야후가 분할 뒤에 준 틀린 주당순이익(PER 0.1)은 #176 이 못 보고 이 검사가 비워요.
from test_us_split_rescale import SNDK_POST, SNDK_STALE, US20, PX18, EPS0, BPS0, K8, _run, entry  # noqa: E402

SNDK_EPS_STALE = dict(SNDK_POST, trailingPE=79.24 / 923.7)     # 2026-11-24 야후 모양: 분할 뒤 가격 ÷ 주당순이익 923.7달러 (회사 합계의 약 54배)


def _merged_gate(by, meta):
    return gate_row({"usPxDate": US20, "asOf": "2026-11-21", "splits": meta["splits"], "usSplitChk": meta["usSplitChk"]}, list(by.values()))


@pytest.mark.parametrize("cache_at, fresh, diff", [
    ("2026-11-19", None, None),                                   # 이틀 된 분할 전 보관본 — 다시 묻지 않고 × 8
    ("2026-11-17", "stale_pbr", [["SNDK", "pbr 8.00배"]]),       # 4일 됨 · 다시 받은 새 PBR 이 분할 전 (11-21 모양) — 보관본 × 8 을 씀
])
def test_a_rescaled_pre_split_copy_that_agrees_with_the_totals_stays(tmp_path, monkeypatch, cache_at, fresh, diff):
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache={"SNDK": entry(cache_at, PX18, pd_=None if fresh is None else "2026-11-16")},
                                      sndk_info=SNDK_STALE if fresh else None)
    s = by["SNDK"]
    assert (s["per"], s["pbr"], s["dy"]) == (round(PX18 / EPS0 * K8, 1), round(PX18 / BPS0 * K8, 2), 0.0) == (5.1, 5.03, 0.0)   # #176: × 8
    assert "splCut" not in s and "fgnCut" not in s
    assert meta["usSrc"]["split"] == {"v": 1, "fit": [["SNDK", 8.0]], **({"diff": diff} if diff else {})}
    u = meta["usSplitChk"]
    assert u["recent"] == {"SNDK": US20} and u["checked"] == ["SNDK"] and u["cut"] == [] and u["kind"] == {}    # 보관본의 비: 1.09배 · 1.30배 — 맞음
    assert calls.count("SNDK") == (1 if fresh else 0)
    assert any(x.startswith("· 최근 30일 안에 분할한 미국 회사의 주당 숫자") and "확인 1곳 · PER 비움 0곳" in x for x in lines), lines
    r = _merged_gate(by, meta)
    assert r[3] == "PASS" and "비운 칸 PER 0 · PBR 0 · 배당 0" in r[1], r


@pytest.mark.parametrize("cache", [None, "pre_split_due"])
def test_yahoos_wrong_post_split_eps_is_blanked_after_the_rescale(tmp_path, monkeypatch, cache):
    """11-24 모양: 다시 받은 상세 정보의 PER 이 0.1 (분할 뒤 가격 ÷ 틀린 주당순이익 923.7) · 시가총액 ÷ 순이익 4.6. #176 의 맞춤은 분할 전 방향(× 1/8)만 보니
    이 PER 을 '새 상세 정보'로 써요 (보관본이 있어도) — 이 검사가 PER 만 비우고 splCut 을 붙여요. PBR (1.30배) · 배당 0% 는 그대로."""
    c = {"SNDK": entry("2026-11-17", PX18, pd_="2026-11-16")} if cache else None
    by, meta, lines, calls, _p = _run(tmp_path, monkeypatch, cache=c, sndk_info=SNDK_EPS_STALE)
    s = by["SNDK"]
    assert calls.count("SNDK") == 1
    if cache:                                                       # #176 의 맞춤: 분할 전 방향이 아니라 '새 상세 정보를 씀'
        assert F.us_info_fresh_vs_copy({"px": 79.24, "info": SNDK_EPS_STALE}, c["SNDK"], 79.24, 8.0) == ("ok", [])
    assert "per" not in s and s["splCut"] == {"per": "mismatch"} and "fgnCut" not in s
    assert (s["pbr"], s["dy"]) == (round(SNDK_EPS_STALE["priceToBook"], 2), 0.0) == (5.03, 0.0)
    assert (meta["usSrc"].get("split") or {}).get("diff") is None                                      # #176 은 새 상세 정보를 씀
    u = meta["usSplitChk"]
    pe, pe_c = SNDK_EPS_STALE["trailingPE"], SNDK_EPS_STALE["marketCap"] / SNDK_EPS_STALE["netIncomeToCommon"]
    assert round(pe, 2) == 0.09 and 4.6 < pe_c < 4.7
    assert u["cut"] == [["SNDK", "per", f"주가 ÷ 주당순이익 {pe:.2f} ↔ 시가총액 ÷ 순이익 {pe_c:.2f} ({pe_c / pe:.2f}배)"]], u["cut"]
    assert u["kind"] == {"SNDK": {"per": "mismatch"}} and u["checked"] == ["SNDK"]
    assert any(x.startswith("  !! 최근 30일 안에 분할한 미국 회사의 주당 숫자") and "PER 비움 1곳 (SNDK)" in x for x in lines), lines
    r = _merged_gate(by, meta)
    assert r[3] == "PASS" and "비운 칸 PER 1 · PBR 0 · 배당 0 (SNDK.per)" in r[1], r
    assert u["band"] == {"SNDK": 2.8284} and u["held"] == {}                                      # 8:1 → √8 · 54배는 그 밖


# ── 리뷰 1차 (#188): 분할 크기만큼의 허용 폭 (S1) · 30일 끝 (S2) · 맞춰 보지 못한 종류의 줄 (N1) · 안전망 (N3) · 글자 ─────────
# NVDA 모양 (2026-11-24 야후): PBR 이 시가총액 ÷ 순이익 × ROE 와 1.39배 (ROE 가 평균 자본이라) — 맞는 숫자 · APH 모양: 배당 0.15달러로 올린 뒤의 앞으로
# 1년 배당수익률 0.77% ↔ 지난 350일 배당 0.50달러 ÷ 77.41 = 0.65% (1.19배) — 맞는 숫자. 외국 회사의 폭(1.35 · 1.10)이면 둘 다 비워요.
NVDA_LIKE = yi("Nvidia Like", marketCap=4.5e12, netIncomeToCommon=1.2e11, trailingPE=37.5, priceToBook=37.5 * 1.0 / 1.39,
               returnOnEquity=1.0, dividendYield=0.0)
APH_LIKE = yi("Amphenol Like", marketCap=94e9, netIncomeToCommon=2.5e9, trailingPE=37.6, priceToBook=37.6 * 0.25, returnOnEquity=0.25,
              dividendYield=0.77)
APH_PAID = [("2025-12-10", 0.125), ("2026-03-10", 0.125), ("2026-06-10", 0.125), ("2026-09-10", 0.125)]


def _one(t, price, info, ratio, paid=()):
    """종목 하나를 분할 배율 ratio 의 허용 폭으로 검사 → (종목, 반환)."""
    r = rec(t, price, info)
    cache = {t: {"at": "2026-11-14", "px": price, "k": F.US_INFO_SCHEMA, "info": dict(info)}}
    got = F.us_split_check([r], cache, divs({t: price}, {t: list(paid)}), US_DAY, {t: SPLIT_DAY}, bands={t: F.us_split_check_band([ratio])})
    return r, got


def test_the_band_is_the_split_size_and_the_same_function_as_the_176_row():
    for rs in ([8.0], [2.0], [4.0], [0.1], [2.0, 3.0], [1.05], [10.0]):
        assert F.us_split_check_band(rs) == V.us_split_band(rs), rs
    assert F.us_split_check_band([8.0]) == pytest.approx(8 ** 0.5) and F.us_split_check_band([2.0]) == 1.5 == F.US_SPLIT_BAND_MIN
    assert F.us_split_check_band([0.1]) == pytest.approx(10 ** 0.5)                                # 1:10 병합은 역수
    assert F.us_split_check_band([]) == 1.5 == F.us_split_check_band([None, "x", 0, -2.0, 1.0, float("nan")])   # 모르면 가장 좁게


@pytest.mark.parametrize("ratio", [2.0, 10.0])
def test_nvda_like_pbr_off_by_1_39_stays_after_a_split(lines, ratio):
    r, got = _one("NVL", 180.0, NVDA_LIKE, ratio)
    assert (r["per"], r["pbr"]) == (37.5, round(37.5 / 1.39, 2)) and "splCut" not in r and got["cut"] == []
    assert set(F.us_foreign_cuts(r, NVDA_LIKE, 0.0)) == {"pbr"}                                  # 외국 회사의 폭(1.35)이면 비워요 — 그 검사는 그대로


def test_aph_like_forward_yield_off_by_1_19_stays_after_a_split(lines):
    r, got = _one("APL", 77.41, APH_LIKE, 2.0, APH_PAID)
    assert r["dy"] == 0.77 and "splCut" not in r and got["cut"] == []
    assert set(F.us_foreign_cuts(r, APH_LIKE, F.us_div_12m(divs({"APL": 77.41}, {"APL": APH_PAID})[("APL", "Dividends")], US_DAY))) == {"dy"}


def test_a_gap_beyond_the_split_band_is_cut_and_one_inside_it_stays(lines):
    off16 = dict(NVDA_LIKE, priceToBook=37.5, trailingPE=37.5 * 1.6)                                # PER 1.6배 (2:1 의 폭 1.5 밖)
    r, got = _one("X2", 180.0, off16, 2.0)
    assert r["splCut"] == {"per": "mismatch"} and "per" not in r and got["cut"][0][2].endswith("(1.60배)")
    r8, got8 = _one("X8", 180.0, dict(off16, trailingPE=37.5 * 2.5), 8.0)                           # 8:1 뒤 2.5배는 √8 = 2.83 안 — 남아요
    assert r8["per"] == round(37.5 * 2.5, 1) and got8["cut"] == []


def test_ratio_map_and_bands_use_the_published_sources(monkeypatch):
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("W", "2026-11-02"): (0.5, "병합 · 야후에 없음"), ("Z", "2026-11-02"): (None, "분사")})
    rmap = F.us_split_ratio_map([["A", "2026-11-03", 4.0], ["B", "bad", 2.0]], {"splits": [["A", "2026-11-03", 2.0], ["H", "2026-09-01", 8.0],
                                                                                         ["H", "2020-01-02", 3.0]]})
    assert rmap == {"A": {"2026-11-03": [4.0, 2.0]}, "H": {"2020-01-02": [3.0], "2026-09-01": [8.0]}, "W": {"2026-11-02": [0.5]}}
    b = F.us_split_bands(rmap, {"A": "2026-11-03", "W": "2026-11-02", "H": "2026-09-01", "N": ""}, "2026-10-14", "2026-11-14")
    assert b == {"A": 1.5, "W": 1.5, "H": 2.8284, "N": 1.5}          # 같은 날 4 · 2 → 더 좁게 (√2 → 1.5) · held 는 가장 늦은 분할 (8:1) · 모르면 1.5


# 30일 끝 (리뷰 1차 S2 · 2차 S1 · S2): SNDK 8:1 분할 2026-11-20 — 미국 기준일 12-18 은 30일 안 · 12-21 부터 밖. 지난 발행본에서 비운 칸(어떤 종류든)과
# 지난 usSplitChk.held 칸은 맞춰 보고 맞을 때까지 잡아 둬요 — 맞춰 볼 수 없음 · 검사가 멈춤 · 단계가 멈춤이면 잡아 둔 채 비워요.
SPL = [["SNDK", "2026-11-20", 8.0]]
IN_DAY, OUT_DAY = dt.date(2026, 12, 18), dt.date(2026, 12, 21)
SNDK_NONI = {k: v for k, v in SNDK.items() if k != "netIncomeToCommon"}     # 야후가 다시 준 상세 정보에 순이익 칸이 없는 날
SNDK_FIXED = dict(SNDK, trailingPE=SNDK["marketCap"] / SNDK["netIncomeToCommon"])   # 야후가 주당순이익을 고친 날


def _day(info, prev, us_day, cache=True, step=None):
    """그날 한 번 (미국 기준일 us_day · 한국 날짜 하루 뒤) → (SNDK 행, usSplitChk, 다음 실행의 지난 발행본)."""
    r = rec("SNDK", 87.71, info)
    c = {"SNDK": {"at": (us_day + dt.timedelta(days=1)).isoformat(), "px": 87.71, "k": F.US_INFO_SCHEMA, "info": dict(info)}} if cache else {}
    today = us_day + dt.timedelta(days=1)
    got = (step or F.us_split_step)([r], c, divs({"SNDK": 87.71}, {}), us_day, today, prev)
    return r, got, {"usPxDate": us_day.isoformat(), "asOf": today.isoformat(), "splits": SPL, "stocks": [r], "usSplitChk": got}


def _gate_day(nxt):
    return gate_row(nxt, nxt["stocks"])


def _marked(mark=None, held=None):
    s = {"t": "SNDK", "cls": "us", "price": 87.71, **({"splCut": mark} if mark else {})}
    return {"usPxDate": "2026-12-18", "splits": SPL, "stocks": [s], **({"usSplitChk": {"held": held}} if held is not None else {})}


def test_sndk_still_wrong_after_30_days_stays_blanked_and_the_gate_warns(lines):
    r0, got0, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY)                   # 30일 안: 맞춰 보고 PER 만 비움
    assert r0["splCut"] == {"per": "mismatch"} and got0["recent"] == {"SNDK": "2026-11-20"} and got0["held"] == {}
    r1, got1, p2 = _day(SNDK, p1, OUT_DAY)                                              # 30일 밖: 지난 발행본의 표시로 잡아 둠
    assert got1["recent"] == {} and got1["held"] == {"SNDK": {"d": "2026-11-20", "f": ["per"], "since": "2026-12-22"}}
    assert "per" not in r1 and r1["splCut"] == {"per": "mismatch"} and r1["pbr"] == 5.57 and got1["band"] == {"SNDK": 2.8284}
    assert any(x.startswith("  !! 30일이 지났지만 지난 발행본에서 비운 칸이 있는 종목 1곳") and "SNDK(PER · 분할 2026-11-20 · 2026-12-22부터" in x
               for x in lines), lines
    g = _gate_day(p2)
    assert g[3] == "WARN" and "30일이 지나도 비운 칸을 잡아 둔 종목 1곳" in g[1] and "SNDK PER (2026-12-22부터 1일째)" in g[1] and "밖" not in g[1], g
    r2, got2, p3 = _day(SNDK, p2, OUT_DAY + dt.timedelta(days=1))                       # 다음 날: since 는 그대로
    assert got2["held"]["SNDK"]["since"] == "2026-12-22" and "SNDK PER (2026-12-22부터 2일째)" in _gate_day(p3)[1]
    r9, got9, _p = _day(SNDK, {"splits": SPL, "stocks": []}, OUT_DAY)                   # 표시가 없었으면 보지 않아요 (30일 끝)
    assert r9["per"] == 0.1 and got9["held"] == {} and got9["checked"] == []


def test_a_refresh_without_net_income_keeps_the_hold_until_compared_and_agreed(lines):
    """2차 S1 ①: 잡아 둔 날 야후가 순이익 칸 없이 줌 → 맞춰 볼 수 없음 (nocompare-own · 앱 줄 co.fgnNoCmp) · 잡아 둔 채. 다음 날 순이익이 돌아오면
    PER 은 다르고 (그대로 잡아 둠) PBR 은 맞아 놓아요. 주당순이익을 고친 날 모두 놓고, 그다음 실행은 보지 않아요."""
    _r, _g, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY)
    r1, got1, p2 = _day(SNDK_NONI, p1, OUT_DAY)
    own = V.US_FGN_NOCMP_KIND[V.US_FGN_NOCMP]
    assert r1["splCut"] == {"pbr": own, "per": own} and "per" not in r1 and "pbr" not in r1 and r1["dy"] == 0.0
    assert got1["held"]["SNDK"]["f"] == ["pbr", "per"] and _gate_day(p2)[3] == "WARN"
    r2, got2, p3 = _day(SNDK, p2, OUT_DAY + dt.timedelta(days=1))
    assert r2["splCut"] == {"per": "mismatch"} and r2["pbr"] == 5.57 and got2["held"]["SNDK"]["f"] == ["per"]
    r3, got3, p4 = _day(SNDK_FIXED, p3, OUT_DAY + dt.timedelta(days=2))
    assert "splCut" not in r3 and r3["per"] == 5.1 and got3["held"] == {} and got3["cut"] == []
    assert _gate_day(p4)[3] == "PASS"
    r4, got4, _p = _day(SNDK, p4, OUT_DAY + dt.timedelta(days=3))                       # 놓은 뒤에는 보지 않아요 (그날 다시 틀려도)
    assert got4["checked"] == [] and r4["per"] == 0.1


def test_a_check_crash_on_a_held_day_blanks_it_stopped_and_keeps_it_held(monkeypatch, lines):
    _r, _g, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY)
    with monkeypatch.context() as m:
        m.setattr(F, "us_foreign_cuts", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("시험")))
        r1, got1, p2 = _day(SNDK, p1, OUT_DAY)
    assert r1["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"} and not any(k in r1 for k in ("per", "pbr", "dy"))
    assert got1["err"] == "RuntimeError" and got1["held"]["SNDK"]["f"] == ["dy", "pbr", "per"]
    r2, got2, _p = _day(SNDK, p2, OUT_DAY + dt.timedelta(days=1))                       # 다음 날 맞춰 봄: PER 만 남아요
    assert r2["splCut"] == {"per": "mismatch"} and r2["pbr"] == 5.57 and r2["dy"] == 0.0 and got2["held"]["SNDK"]["f"] == ["per"]


def test_a_step_crash_blanks_held_stocks_through_the_guard(lines):
    """2차 S1 ③: 단계가 멈추면 안전망이 최근 분할 회사만이 아니라 잡아 둔 종목도 비워요 (예전엔 PER 0.1 이 그날 나갔어요)."""
    _r, _g, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY)
    _r1, _g1, p2 = _day(SNDK, p1, OUT_DAY)
    guard = lambda out, cache, data, us_day, today, prev: F.us_split_guard(out, RuntimeError("시험"), prev, us_day, today)   # noqa: E731
    r2, got2, p3 = _day(SNDK, p2, OUT_DAY + dt.timedelta(days=1), step=guard)
    assert r2["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"} and not any(k in r2 for k in ("per", "pbr", "dy"))
    assert got2["recent"] == {} and got2["held"]["SNDK"]["since"] == "2026-12-22" and set(got2["held"]["SNDK"]["f"]) == {"per", "pbr", "dy"}
    assert got2["err"] == "RuntimeError" and _gate_day(p3)[3] == "WARN"
    r3, got3, _p = _day(SNDK, p3, OUT_DAY + dt.timedelta(days=2))
    assert r3["splCut"] == {"per": "mismatch"} and got3["held"]["SNDK"]["f"] == ["per"]


def test_a_crash_on_the_last_in_window_day_still_holds_after_it(lines):
    """2차 S1 ④: 12-18 (30일 안 마지막 날) 단계가 멈춤 → 안전망이 SNDK 를 stopped 로 비움 → 12-21 (밖) 그 표시로 잡아 둬요."""
    guard = lambda out, cache, data, us_day, today, prev: F.us_split_guard(out, RuntimeError("시험"), prev, us_day, today)   # noqa: E731
    r0, got0, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY, step=guard)
    assert r0["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"} and got0["recent"] == {"SNDK": "2026-11-20"}
    r1, got1, _p = _day(SNDK, p1, OUT_DAY)
    assert got1["held"] == {"SNDK": {"d": "2026-11-20", "f": ["per"], "since": "2026-12-22"}} and r1["splCut"] == {"per": "mismatch"}
    assert r1["pbr"] == 5.57 and r1["dy"] == 0.0                                        # 맞춰 보고 맞은 칸은 놓아요


def test_held_and_recent_list_failures_still_blank_held_stocks(monkeypatch, lines):
    _r, _g, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY)
    with monkeypatch.context() as m:                                                     # held 를 정하다 멈춤 → 지난 발행본의 splCut 만으로
        m.setattr(F, "us_split_held", lambda *a, **k: (_ for _ in ()).throw(KeyError("시험")))
        r1, got1, p2 = _day(SNDK, p1, OUT_DAY)
    assert r1["splCut"] == {"per": "mismatch"} and got1["holdErr"] == "KeyError" and got1["held"]["SNDK"]["f"] == ["per"]
    assert _gate_day(p2)[3] == "WARN" and "이어서 볼 곳을 정하지 못함 (KeyError)" in _gate_day(p2)[1]
    assert got1["held"]["SNDK"]["d"] == ""                                               # 마지막 길은 분할 날짜를 몰라요
    _r1, _g1, p2 = _day(SNDK, p1, OUT_DAY)                                               # 보통 날의 held (날짜 있음)
    with monkeypatch.context() as m:                                                     # 최근 분할 목록이 멈춤 → 잡아 둔 종목은 그대로 봐요
        m.setattr(F, "us_carry_splits", lambda *a, **k: (_ for _ in ()).throw(ValueError("시험")))
        r2, got2, p3 = _day(SNDK, p2, OUT_DAY + dt.timedelta(days=1))
    assert r2["splCut"] == {"per": "mismatch"} and got2["recent"] is None and got2["err"] == "ValueError"
    assert got2["held"]["SNDK"] == {"d": "2026-11-20", "f": ["per"], "since": "2026-12-22"}       # 날짜는 지난 held 에서
    assert any(x.startswith("  !! 최근 분할한 미국 종목을 정하다가 멈췄어요 (ValueError: 시험)") for x in lines), lines


def test_a_held_field_is_released_only_when_compared(lines):
    """상세 정보가 없는 날: 값도 없어 맞춰 보지 못함 → 잡아 둔 채 · 값이 있는데 맞춰 볼 상세 정보가 없으면 stopped 로 비워요."""
    _r, _g, p1 = _day(SNDK, {"splits": SPL, "stocks": []}, IN_DAY)
    r1, got1, p2 = _day(SNDK, p1, OUT_DAY, cache=False)
    assert r1["splCut"] == {"per": "stopped"} and "per" not in r1 and r1["pbr"] == 5.57 and got1["held"]["SNDK"]["f"] == ["per"]
    assert got1["cut"] == [["SNDK", "per", "검사가 멈춤 (상세 정보 없음)"]] and _gate_day(p2)[3] == "WARN"
    bare = {"t": "SNDK", "cls": "us", "price": 87.71}                                    # 값이 하나도 없는 날
    got = F.us_split_check([bare], {}, None, OUT_DAY, {}, held={"SNDK": {"d": "2026-11-20", "f": ["per"], "since": "2026-12-22"}})
    assert got["held"] == {"SNDK": {"d": "2026-11-20", "f": ["per"], "since": "2026-12-22"}} and "splCut" not in bare


def test_every_mark_and_the_previous_held_record_hold_a_stock_past_the_window():
    carry, today = {"SNDK": {"2026-11-20"}, "OLD": {"2020-08-31"}}, dt.date(2026, 12, 22)
    for mark in ({"per": "mismatch"}, {"pbr": "nocompare-own"}, {"dy": "norecord"}, {"per": "currency"}, {"per": "stopped"}):
        assert F.us_split_held(_marked(mark), ["SNDK"], {}, carry, today) == {"SNDK": {"d": "2026-11-20", "f": sorted(mark), "since": "2026-12-22"}}
    prev = _marked({"per": "mismatch"}, held={"SNDK": {"d": "2026-11-20", "f": ["pbr"], "since": "2026-12-20"}, "GONE": {"f": ["per"]}})
    assert F.us_split_held(prev, ["SNDK"], {}, carry, today) == {"SNDK": {"d": "2026-11-20", "f": ["pbr", "per"], "since": "2026-12-20"}}
    assert F.us_split_held(prev, ["AAPL"], {}, carry, today) == {}                     # 오늘 목록에 없음
    assert F.us_split_held(prev, ["SNDK"], {"SNDK": "2026-11-20"}, carry, today) == {}  # 30일 안이면 recent 로 봐요
    assert F.us_split_held(dict(prev, stocks=[dict(prev["stocks"][0], cls="kr")], usSplitChk={}), ["SNDK"], {}, carry, today) == {}
    assert F.us_split_held(_marked(None, held={"SNDK": "2026-11-20"}), ["SNDK"], {}, carry, today) == {}   # 모양이 다른 held 는 칸이 없어요
    assert F.us_split_held(_marked({"per": "mismatch"}), ["SNDK"], {}, {}, today)["SNDK"]["d"] == ""
    assert F.us_split_held(None, ["SNDK"], {}, carry, today) == {} and F.us_split_held_min(_marked({"per": "x"}), ["SNDK"], today) == \
        {"SNDK": {"d": "", "f": ["per"], "since": "2026-12-22"}}


def test_the_gate_row_checks_the_held_record():
    r = {"t": "SNDK", "cls": "us", "price": 87.71, "splCut": {"per": "mismatch"}, "pbr": 5.57}
    base = {"days": 30, "recent": {}, "held": {"SNDK": {"d": "2026-11-20", "f": ["per"], "since": "2026-12-22"}}, "band": {"SNDK": 2.8284},
            "checked": ["SNDK"], "cut": [["SNDK", "per", "주가 ÷ 주당순이익 0.09 ↔ 시가총액 ÷ 순이익 5.14 (54.14배)"]],
            "kind": {"SNDK": {"per": "mismatch"}}, "kept": [], "nocmp": V.US_FGN_NOCMP, "skip": {"foreign": [], "fcur": [], "etf": []}}
    d = {"usPxDate": "2026-12-23", "asOf": "2026-12-24", "splits": SPL}
    g = gate_row({**d, "usSplitChk": base}, [r])
    assert g[3] == "WARN" and "SNDK PER (2026-12-22부터 3일째)" in g[1] and "모양" not in g[1] and "남은 칸" not in g[1], g
    g = gate_row({**d, "usSplitChk": {**base, "held": {}}}, [r])
    assert g[3] == "WARN" and "SNDK.splCut (최근 분할 목록 recent · 이어서 본 목록 held 밖)" in g[1], g
    g = gate_row({**d, "usSplitChk": {**base, "held": {"SNDK": {"d": "2026-11-20", "f": ["per", "pbr"], "since": "2026-12-22"}}}}, [r])
    assert g[3] == "WARN" and "남은 칸 1: SNDK.pbr" in g[1], g
    for bad in ({"held": {"SNDK": "2026-11-20"}}, {"held": {"SNDK": {"f": [], "since": "2026-12-22"}}}, {"held": {"SNDK": {"f": ["x"], "since": "x"}}},
                {"band": {"SNDK": 1.2}}, {"band": {"SNDK": "x"}}):
        g = gate_row({**d, "usSplitChk": {**base, **bad}}, [r])
        assert g[3] == "WARN" and "모양" in g[1], (bad, g)
    assert gate_row({**d, "usSplitChk": {**base, "held": {}, "recent": {"SNDK": "2026-11-20"}}}, [r])[3] == "PASS"


@pytest.mark.parametrize("cur", [None, float("nan"), "null", "undefined", "NaN", "None"])
def test_reason_text_never_carries_a_bad_word(lines, cur):
    """리뷰 1차 (Fable): financialCurrency 가 None · nan · 'null' … 이어도 기록의 글에 관문이 실패시키는 글자가 없어요 ('없음')."""
    out, cache, data = setup()
    cache["SNDK"]["info"]["financialCurrency"] = cur
    got = F.us_split_check(out, cache, data, US_DAY, RECENT)
    sndk = next(r for r in out if r["t"] == "SNDK")
    assert sndk["splCut"] == {"dy": "currency", "pbr": "currency", "per": "currency"}
    assert [p_ for p_, v in V.text_values({"usSplitChk": got}) if V.BAD_WORD.search(v)] == []
    assert all("없음" in w for t, _f, w in got["cut"] if t == "SNDK")


def test_a_crash_in_the_step_does_not_stop_fetch_us(tmp_path, monkeypatch):
    """리뷰 1차 N3: us_split_step 이 받지 못한 오류로 멈춰도 fetch_us 는 끝나요 — 크게 남기고 err (관문 경고)."""
    def boom(*a, **k):
        raise RuntimeError("시험")
    us, meta, lines = _fetch(tmp_path, monkeypatch, step=boom)
    assert {r["t"] for r in us} == {"SNDK", "GOOD", "PLN"} and meta["usSplitChk"]["err"] == "RuntimeError"
    assert any(x.startswith("  !! 최근 분할한 미국 회사 검사 단계가 오류로 멈췄어요 (RuntimeError: 시험)") for x in lines), lines


def test_the_guard_blanks_recent_split_companies_as_stopped_and_keeps_no_blank_without_a_reason(lines):
    out, cache, data = setup()
    by = {r["t"]: r for r in out}
    by["SNDK"].pop("per")
    by["SNDK"]["splCut"] = {"per": "mismatch"}                     # 멈춘 실행이 이미 비운 칸
    prev = {"splits": [[t, SPLIT_DAY, 2.0] for t in RECENT]}
    got = F.us_split_guard(out, RuntimeError("시험"), prev, US_DAY, TODAY)
    assert by["SNDK"]["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"} and not any(k in by["SNDK"] for k in ("per", "pbr", "dy"))
    assert by["GOOD"]["splCut"] == {"dy": "stopped", "pbr": "stopped", "per": "stopped"} and by["PLN"]["per"] == 5.0
    assert got["err"] == "RuntimeError" and {(t, f) for t, f, _w in got["cut"]} >= {("SNDK", "per"), ("SNDK", "pbr"), ("GOOD", "per")}
    g = gate_row({"usPxDate": "2026-11-13", "asOf": "2026-11-14", "splits": prev["splits"], "usSplitChk": got}, out)
    assert g[3] == "WARN" and "cut 줄 없는 표시" not in g[1] and "이유 표시(splCut) 없음" not in g[1], g


def test_the_guard_itself_failing_blanks_nothing_and_says_so(monkeypatch, lines):
    out, cache, data = setup()
    before = copy.deepcopy(out)
    monkeypatch.setattr(F, "us_split_stopped", lambda *a, **k: (_ for _ in ()).throw(ValueError("또")))
    got = F.us_split_guard(out, RuntimeError("시험"), {"splits": [[t, SPLIT_DAY, 2.0] for t in RECENT]}, US_DAY, TODAY)
    assert out == before and got["recent"] is None and got["err"] == "RuntimeError"
    assert any(x.startswith("  !! 최근 분할한 미국 회사 검사의 안전망도 멈췄어요 (ValueError: 또)") for x in lines), lines


def test_units_describe_the_new_fields():
    assert "splCut" in F.UNITS and "usSplitChk" in F.UNITS and "fgnCut" in F.UNITS["splCut"]
    assert F.US_SPLIT_CHECK_DAYS == V.US_SPLIT_CHK_DAYS and F.US_SPLIT_MARK == V.US_SPLIT_MARK and F.US_SPLIT_SKIP == V.US_SPLIT_SKIP
    assert not V.BAD_WORD.search(F.UNITS["splCut"] + F.UNITS["usSplitChk"])


# ── 관문 (경고만 · 외국 회사 줄은 그대로) ─────────────────────────────
def gate_row(data, us):
    rep = V.Report()
    V.check_us_split_cut(rep, data, us)
    return next(r for r in rep.rows if r[0] == ROW)


def live_like():
    """11-24 발행본 모양: SNDK 2026-11-20 분할 · PER 0.1 · 기록 없음."""
    us = [{"t": "SNDK", "cls": "us", "price": 87.71, "per": 0.1, "pbr": 6.39, "dy": 0.0, "vz": 32},
          {"t": "SOXX", "cls": "us", "price": 140.22, "etf": True, "per": 33.4, "pbr": 0.37, "dy": 0.24},
          {"t": "BP", "cls": "us", "price": 45.7, "dy": 4.55, "fgnCut": {"pbr": "mismatch", "per": "mismatch"}},
          {"t": "AAPL", "cls": "us", "price": 270.0, "per": 36.0, "pbr": 50.0, "dy": 0.4}]
    data = {"usPxDate": "2026-11-23", "asOf": "2026-11-24", "splits": [["AAPL", "2020-08-31", 4.0], ["SNDK", "2026-11-20", 8.0],
                                                                      ["SOXX", "2026-11-05", 3.0], ["BP", "2026-11-10", 2.0]],
            "usForeign": {"set": {"BP": ["United Kingdom", "USD", "country"]}}}
    return data, us


def fixed():
    data, us = live_like()
    us[0].pop("per")
    us[0]["splCut"] = {"per": "mismatch"}
    data["usSplitChk"] = {"days": 30, "recent": {"BP": "2026-11-10", "SNDK": "2026-11-20", "SOXX": "2026-11-05"}, "checked": ["SNDK"],
                          "cut": [["SNDK", "per", "주가 ÷ 주당순이익 0.09 ↔ 시가총액 ÷ 순이익 5.14 (54.14배)"]],
                          "kind": {"SNDK": {"per": "mismatch"}}, "kept": [], "nocmp": V.US_FGN_NOCMP,
                          "skip": {"foreign": ["BP"], "fcur": [], "etf": ["SOXX"]}}
    return data, us


def test_gate_warns_on_todays_live_file_and_passes_the_fixed_one():
    data, us = live_like()
    r = gate_row(data, us)
    assert r[3] == "WARN" and "기록 없음 (data.json usSplitChk) · 맞춰 보지 않은 숫자 1곳: SNDK" in r[1], r
    data, us = fixed()
    r = gate_row(data, us)
    assert r[3] == "PASS" and r[1].startswith("최근 분할 3곳 · 확인 1곳 · 비운 칸 PER 1 · PBR 0 · 배당 0 (SNDK.per)"), r
    assert "보지 않음(외국 회사 · fcur · ETF) 2곳: BP, SOXX" in r[1], r


@pytest.mark.parametrize("change, expect", [
    (lambda d, us: us[0].update(per=0.1), "남은 칸 1: SNDK.per"),
    (lambda d, us: us[0].pop("splCut"), "이유 표시(splCut) 없음 1: SNDK.per"),
    (lambda d, us: d["usSplitChk"].update(checked=[]), "맞춰 보지 않은 숫자 1곳: SNDK"),
    (lambda d, us: us[3].update(splCut={"per": "mismatch"}, per=None), "AAPL.splCut (최근 분할 목록 recent · 이어서 본 목록 held 밖)"),
    (lambda d, us: us[2].update(splCut={"dy": "mismatch"}, dy=None), "BP.splCut (foreign)"),
    (lambda d, us: us[0].update(splCut={"per": "weird"}), "SNDK.splCut"),
    (lambda d, us: us[0].update(splCut={"per": "currency"}), "종류 SNDK.per currency ≠ mismatch"),
    (lambda d, us: d["usSplitChk"].update(kind={}), "kind ≠ 종목 표시 1: SNDK"),
    (lambda d, us: d["usSplitChk"].update(cut="SNDK"), "cut 모양"),
    (lambda d, us: d["usSplitChk"].update(srcErr="KeyError"), "오늘 다운로드의 분할 칸을 읽지 못해"),
    (lambda d, us: d["usSplitChk"].update(err="RuntimeError"), "검사가 멈춤 (RuntimeError)"),
    (lambda d, us: d.pop("usSplitChk"), "기록 없이 표시(splCut) 1곳: SNDK"),
])
def test_gate_row_only_ever_warns(change, expect):
    data, us = fixed()
    change(data, us)
    r = gate_row(data, us)
    assert r[3] == "WARN" and expect in r[1], r


def test_gate_row_that_crashes_warns(monkeypatch):
    data, us = fixed()
    monkeypatch.setattr(V, "us_split_recent", lambda d: (_ for _ in ()).throw(RuntimeError("시험")))
    r = gate_row(data, us)
    assert r[3] == "WARN" and r[1].startswith("검사가 오류로 멈췄어요: RuntimeError: 시험"), r


def test_the_foreign_row_keeps_its_rule_and_passes_a_split_mark():
    """외국 회사 줄은 바꾸지 않았어요: fgnCut 은 여전히 외국 회사에만 (SNDK 에 fgnCut 이면 실패) · splCut 은 그 줄이 보지 않아요."""
    data, us = fixed()
    uf = {"checked": ["BP"], "cut": [["BP", "pbr", "… (4.32배)"], ["BP", "per", "… (1.70배)"]], "set": data["usForeign"]["set"], "unknown": [],
          "nocmp": V.US_FGN_NOCMP, "kept": [], "kind": {"BP": {"pbr": "mismatch", "per": "mismatch"}}, "sp500": {"n": 503, "inList": 500, "ok": True}}
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": uf}, us, "publish")
    r = next(x for x in rep.rows if x[0] == FOREIGN)
    assert r[3] == "PASS", r
    us[0]["fgnCut"] = us[0].pop("splCut")
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": uf}, us, "publish")
    r = next(x for x in rep.rows if x[0] == FOREIGN)
    assert r[3] == "FAIL" and "SNDK.fgnCut (외국 회사 목록 밖이거나 fcur)" in r[1], r


# ── 앱 (splCut 을 fgnCut 과 같게) ─────────────────────────────────
from test_us_fcur_app import NODE, run  # noqa: E402

node = pytest.mark.skipif(NODE is None, reason="node 가 없어요")


@node
def test_app_reads_the_split_mark_like_the_foreign_mark():
    got = run("""
      const s = { t: 'SNDK', cls: 'us', pbr: 6.39, dy: 0, splCut: { per: 'mismatch' } };
      const html = (props) => text(renderToStaticMarkup(h(FN.FgnCutNote, props)));
      out = {
        of: FC.fgnCutOf(s), blank: [FC.fgnBlank(s, 'per'), FC.fgnBlank(s, 'pbr')], kind: FC.fgnKindOf(s, 'per'),
        value: html({ s, fields: ['pbr', 'per'] }), div: html({ s, fields: ['pbr', 'dy'] }),
        own: html({ s: { ...s, splCut: { per: 'nocompare-own', pbr: 'nocompare-own' }, pbr: null }, fields: ['pbr', 'per'] }),
        stopped: html({ s: { ...s, splCut: { per: 'stopped' } }, fields: ['pbr', 'per'] }),
        left: FC.fgnCutOf({ ...s, per: 0.1 }), fcur: FC.fgnCutOf({ ...s, fcur: 'TWD' }), kr: FC.fgnCutOf({ ...s, cls: 'kr' }),
        odd: [FC.fgnCutOf({ ...s, splCut: ['per'] }), FC.fgnCutOf({ ...s, splCut: null })],
        both: FC.fgnCutOf({ t: 'X', cls: 'us', fgnCut: { pbr: 'mismatch' }, splCut: { per: 'stopped' } }),
        bothKind: [FC.fgnKindOf({ fgnCut: { per: 'mismatch' }, splCut: { per: 'stopped' } }, 'per'), FC.fgnKindOf(null, 'per')],
        own2: FC.fgnOwnOf({ t: 'X', cls: 'us', splCut: { pbr: 'nocompare-own' } }),
        lines: [C2.co.fgnCut, C2.co.fgnNoCmp, C2.co.fgnStopped],
      };""")
    assert got["of"] == ["per"] and got["blank"] == [True, False] and got["kind"] == "mismatch"
    assert got["value"] == LINE and got["div"] == ""                       # 가치 탭 · 가치 자세히 (PBR · PER 자리)에만 · 배당 자리엔 없음
    assert got["own"] == got["lines"][1] and got["stopped"] == got["lines"][2]
    assert got["left"] == [] and got["fcur"] == [] and got["kr"] == [] and got["odd"] == [[], []]
    assert got["both"] == ["per", "pbr"] and got["bothKind"] == ["mismatch", None] and got["own2"] == ["pbr"]


@node
def test_a_split_companys_uncompared_kinds_take_the_cant_compare_line():
    """리뷰 1차 N1: 분할 회사의 currency (재무제표 통화를 확인하지 못함) · norecord (배당 기록을 읽지 못함) 는 맞춰 보지 않았어요 — '…맞지 않아서'
    (co.fgnCut) 가 아니라 승인된 '비교할 수 없어서' 줄 (co.fgnNoCmp). 외국 회사(fgnCut)의 줄은 그대로예요."""
    got = run("""
      const html = (s, fields) => text(renderToStaticMarkup(h(FN.FgnCutNote, { s, fields })));
      const spl = { t: 'SNDK', cls: 'us', splCut: { per: 'currency', pbr: 'currency', dy: 'norecord' } };
      const fgn = { t: 'BP', cls: 'us', fgnCut: { per: 'currency', dy: 'norecord' } };
      out = {
        kinds: ['per', 'pbr', 'dy'].map((k) => FC.fgnKindOf(spl, k)), fk: ['per', 'dy'].map((k) => FC.fgnKindOf(fgn, k)),
        spl: html(spl, ['per']), splDy: html(spl, ['dy']), fgn: html(fgn, ['per']), fgnDy: html(fgn, ['dy']),
        mis: html({ t: 'X', cls: 'us', splCut: { per: 'mismatch' } }, ['per']),
        stop: html({ t: 'X', cls: 'us', splCut: { per: 'stopped' } }, ['per']),
        both: FC.fgnKindOf({ fgnCut: { per: 'currency' }, splCut: { per: 'norecord' } }, 'per'),
        lines: [C2.co.fgnCut, C2.co.fgnNoCmp, C2.co.fgnStopped],
      };""")
    cut, nocmp, stopped = got["lines"]
    assert got["kinds"] == ["nocompare-own"] * 3 and got["fk"] == ["currency", "norecord"]
    assert got["spl"] == nocmp == got["splDy"] and nocmp == "회사 전체 숫자와 비교할 수 없어서 이 숫자는 비워 두었어요."
    assert got["fgn"] == cut == got["fgnDy"] == LINE and got["mis"] == cut and got["stop"] == stopped
    assert got["both"] == "currency"                                                   # 두 표시가 있으면 외국 회사 표시가 먼저


def test_the_last_cleaning_pass_covers_the_record(lines):
    """리뷰 2차 S3: 쓰기 바로 앞 마지막 한 번 (#178 pub_sweep) 이 usSplitChk 도 봐요 — 관문이 막는 낱말이 들어가도 '빈 값'."""
    assert "usSplitChk" in F.PUB_SWEEP_KEYS
    doc = {"usSplitChk": {"cut": [["SNDK", "per", "주가 ÷ 주당순이익 nan ↔ …"]], "kind": {"SNDK": {"per": "mismatch"}}}}
    F.pub_sweep(doc, "data.json")
    assert doc["usSplitChk"]["cut"][0][2] == f"주가 ÷ 주당순이익 {F.PUB_BLANK} ↔ …" and doc["usSplitChk"]["kind"] == {"SNDK": {"per": "mismatch"}}
    assert doc["ownDrop"]["sweep"]["paths"] == ["usSplitChk.cut[0][2]"]
