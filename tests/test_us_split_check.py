# -*- coding: utf-8 -*-
"""분할 뒤 30일 안의 미국 회사 주당 숫자 검사 (2026-11-24 · SNDK) — fetch_data.py us_recent_splits · us_split_check · us_split_stopped ·
us_split_step · fetch_us(호출) · us_meta_drop 과 validate_data.py check_us_split_cut (경고만) · src/v2/fcur.js (splCut 을 fgnCut 처럼). 네트워크 없음.

- SNDK 는 2026-11-20 8:1 분할 뒤 야후 주당순이익이 분할 전 기준(923.7달러)으로 남아 PER 0.1 이 나갔어요 (시가총액 ÷ 순이익 5.1).
- 외국 회사 검사(us_foreign_cuts)와 같은 허용 폭 · 같은 종류 · 앱의 같은 줄 (co.fgnCut · co.fgnNoCmp · co.fgnStopped). 맞는 숫자는 비우지 않아요.
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

    def boom(rec_, info, div12, days=F.US_FOREIGN_DIV_DAYS):
        calls.append(rec_["t"])
        if rec_["t"] == "GOOD":
            raise RuntimeError("시험")
        return real(rec_, info, div12, days)
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
    assert any(x.startswith("· 최근 30일 안에 분할한 미국 종목 (2026-10-14 ~ 2026-11-14): 2곳: GOOD(2026-11-03), SNDK(2026-11-03)") for x in lines), lines
    json.dumps(meta["usSplitChk"], allow_nan=False, ensure_ascii=False)
    r = gate_row({"usPxDate": "2026-11-13", "asOf": "2026-11-14", "splits": meta["splits"], "usSplitChk": u}, us)
    assert r[3] == "PASS" and "비운 칸 PER 1 · PBR 0 · 배당 0 (SNDK.per)" in r[1], r


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
    (lambda d, us: us[3].update(splCut={"per": "mismatch"}, per=None), "AAPL.splCut (최근 분할 목록 recent 밖)"),
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
