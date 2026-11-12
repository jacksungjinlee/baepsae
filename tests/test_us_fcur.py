# -*- coding: utf-8 -*-
"""미국 상장 회사 중 재무제표 통화가 달러가 아닌 곳 (Jack, 2026-11-12) — fetch_data.py apply_us_info · us_fin_currency · us_info_due ·
us_fcur_summary · fetch_us(보관본 다시 받기) 와 validate_data.py check_us_fcur. (네트워크 없음)

- 야후 financialCurrency 가 달러가 아니면 data.json fcur = ISO 코드, PER · PBR · 배당수익률(0% 도)은 빈 칸 (None — 0 이 아니에요).
  가치 점수(vz)는 PBR 이 비어 매기지 않고, 다른 미국 종목의 순위는 그 회사들 없이 매겨요. ROE · 영업이익률 · 매출 증가율 · 차입금 비율 ·
  시가총액 · 거래대금 · 가격으로 만든 값은 그대로예요
- financialCurrency 가 USD 거나 없으면(모름) 예전 그대로예요 (모름은 로그에 수와 티커)
- 보관본 항목에 새 모양 표시(k)가 없으면 받은 지 3일이 안 됐어도 한 번 다시 받아요
- 관문: fcur 가 있는 미국 회사에 per · pbr · dy · vz 가 남아 있으면(0 도) 실패 · fcur 가 USD 거나 세 글자 대문자가 아니면 실패 ·
  fcur 가 없는 회사는 이 줄이 보지 않아요 (야후가 financialCurrency 를 주지 않아도 실패하지 않아요)
"""
import copy
import datetime as dt
import json
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
from fixture_data import good_pair  # noqa: E402

ROW = "미국 재무제표 통화가 달러가 아닌 회사: PER·PBR·배당수익률·가치 점수 빈 칸"
FX = 1338.3


def info(fc=None, **kw):
    """야후 info 한 벌 (2026-11-12 TSM 과 비슷한 값)."""
    i = {"shortName": "Taiwan Semiconductor Manufactur", "sector": "Technology", "industry": "Semiconductors",
         "trailingPE": 26.05, "priceToBook": 76.71, "returnOnEquity": 0.3657, "operatingMargins": 0.5814,
         "revenueGrowth": 0.405, "debtToEquity": 17.9, "dividendYield": 0.91, "marketCap": 2.084e12, "averageVolume": 1.3e7,
         "longBusinessSummary": "Makes chips.", "currency": "USD"}
    if fc is not None:
        i["financialCurrency"] = fc
    i.update(kw)
    return i


def rec(t="TSM", price=401.98):
    return {"t": t, "nk": t, "ne": t, "cls": "us", "ccy": "USD", "fxu": True, "price": price, "beta": 1.7, "vol": 42.0, "mom": 40.0,
            "etf": False}


# ── apply_us_info ─────────────────────────────────────────
def test_non_dollar_statements_blank_per_pbr_dy_and_keep_the_rest():
    r = rec()
    assert F.apply_us_info(r, info("TWD"), px_then=401.98, fx=FX) is True
    assert r["fcur"] == "TWD"
    for k in ("per", "pbr", "dy"):
        assert k not in r, k                                         # 빈 칸 (0 이 아니에요)
    # 같은 통화끼리 나눈 비율 · 시가총액(달러 주가 × 주식 수) · 거래대금은 그대로
    assert r["roe"] == 36.6 and r["opm"] == 58.1 and r["g3"] == 40.5 and r["debt"] == 17.9
    assert r["cap"] == round(2.084e12 * FX / 1e12, 3) and r["val"] == round(1.3e7 * 401.98 * FX / 1e8, 1)
    assert r["nk"] == "Taiwan Semiconductor Manufactur" and r["de"] == "Makes chips."
    json.dumps(r, allow_nan=False)


def test_dollar_or_unknown_statements_are_unchanged():
    for fc in ("USD", "usd", None, float("nan"), "", "   ", 7):
        r = rec()
        i = info(fc) if fc is not None else info()
        assert F.apply_us_info(r, i, px_then=401.98, fx=FX) is True
        assert "fcur" not in r, fc
        assert r["per"] == 26.1 and r["pbr"] == 76.71 and r["dy"] == 0.91, fc
    assert F.us_fin_currency(info()) is None and F.us_fin_currency(info(float("nan"))) is None
    assert F.us_fin_currency(info("twd")) == "TWD" and F.us_fin_currency(info(" sek ")) == "SEK"
    assert F.us_fin_currency(None) is None


def test_unreadable_currency_is_not_trusted_as_dollars():
    r = rec()
    F.apply_us_info(r, info("Taiwan dollar"), px_then=401.98, fx=FX)
    assert r["fcur"] == "XXX" and not any(k in r for k in ("per", "pbr", "dy"))


def test_zero_yield_is_blanked_too_and_a_second_apply_leaves_nothing_behind():
    r = rec("CAE", 28.06)
    F.apply_us_info(r, info("CAD", dividendYield=0.0, trailingPE=43.8, priceToBook=2.39), px_then=28.06, fx=FX)
    assert r["fcur"] == "CAD" and "dy" not in r                      # Jack: 배당수익률은 0% 도 비워요
    r2 = rec()
    F.apply_us_info(r2, info("USD"), px_then=401.98, fx=FX)
    assert r2["dy"] == 0.91
    F.apply_us_info(r2, info("EUR"), px_then=401.98, fx=FX)            # 같은 rec 에 다시 붙이면 예전 값이 남지 않아요
    assert r2["fcur"] == "EUR" and not any(k in r2 for k in ("per", "pbr", "dy"))
    F.apply_us_info(r2, info("USD"), px_then=401.98, fx=FX)
    assert "fcur" not in r2 and r2["pbr"] == 76.71


def test_percentiles_never_rank_the_blanked_companies():
    us = []
    for i in range(10):
        r = rec(f"U{i}", 100.0)
        F.apply_us_info(r, info("TWD" if i < 3 else "USD", priceToBook=1.0 + i, returnOnEquity=0.1 + i / 100), 100.0, FX)
        us.append(r)
    F.add_percentiles(us)
    for r in us[:3]:
        assert "vz" not in r and "pbr" not in r                      # 가치 점수 없음 (0 점이 아니에요)
        assert isinstance(r["qz"], int) and isinstance(r["pz"], int)  # 다른 점수는 그대로
    others = us[3:]
    want = (100 - pd.Series([o["pbr"] for o in others]).rank(pct=True) * 100).round().astype(int).tolist()
    assert [o["vz"] for o in others] == want                           # 나머지 7곳끼리만 매겨요
    json.dumps(us, allow_nan=False)
    for r in us:
        for v in r.values():
            assert not (isinstance(v, float) and not math.isfinite(v))


# ── 보관본 다시 받기 ───────────────────────────────────────
def test_cache_entries_of_the_old_shape_are_due_once():
    today = dt.date(2026, 11, 13)
    assert F.US_INFO_SCHEMA == 2 and {"financialCurrency", "currency"} <= set(F.US_INFO_KEYS)
    assert F.us_info_due(None, today) is True
    assert F.us_info_due({"at": "2026-11-12", "k": F.US_INFO_SCHEMA, "info": {}}, today) is False
    assert F.us_info_due({"at": "2026-11-12", "info": {}}, today) is True          # 예전 모양: 다시 받아요
    assert F.us_info_due({"at": "2026-11-12", "k": 1, "info": {}}, today) is True
    assert F.us_info_due({"at": "2026-11-10", "k": F.US_INFO_SCHEMA, "info": {}}, today) is True   # 3일 (예전 규칙 그대로)
    assert F.us_info_due({"at": "nope", "k": F.US_INFO_SCHEMA}, today) is True


def test_summary_counts_and_unknown_list():
    us = []
    for t, fc in (("TSM", "TWD"), ("KSPI", "KZT"), ("ASML", "EUR"), ("AAPL", "USD"), ("FISV", None), ("SPY", None), ("GONE", None)):
        r = rec(t)
        i = info(fc) if fc else info()
        if t == "ASML":
            i.pop("dividendYield")
        F.apply_us_info(r, i, 401.98, FX)
        r["etf"] = t == "SPY"
        us.append(r)
    infos = {r["t"]: (info(fc) if fc else info()) for r, fc in zip(us, ("TWD", "KZT", "EUR", "USD", None, None, None))}
    infos["ASML"].pop("dividendYield")
    sm = F.us_fcur_summary(us, infos, no_info={"GONE"})
    assert sm["hit"] == [("ASML", "EUR"), ("KSPI", "KZT"), ("TSM", "TWD")]
    assert sm["byCur"] == {"EUR": 1, "KZT": 1, "TWD": 1}
    assert sm["cut"] == {"per": 3, "pbr": 3, "dy": 2}
    assert sm["unknown"] == ["FISV"]                                   # ETF · 상세 정보 없는 종목은 세지 않아요
    lines = []
    orig = F.log
    try:
        F.log = lines.append
        F.log_us_fcur(sm)
    finally:
        F.log = orig
    assert lines[0].startswith("· 미국 재무제표 통화가 달러가 아닌 회사: 3곳 (통화별 EUR 1 · KZT 1 · TWD 1) — PER·PBR·배당수익률 비움")
    assert "ASML(EUR), KSPI(KZT), TSM(TWD)" in lines[0]
    assert lines[1].startswith("  !! 미국 재무제표 통화를 모르는 회사 1곳") and lines[1].endswith("FISV")


# ── fetch_us: 보관본 다시 받기와 빈 칸이 발행 목록까지 ───────────────
def _fake_yf(syms, infos, calls, start, end):
    days = pd.bdate_range(start, end)

    def series(seed):
        rnd = np.random.default_rng(seed)
        return pd.Series(100 * np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)

    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series(len(tickers))})
        cols = {(t, "Close"): series(i + 3) for i, t in enumerate(tickers)}
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            calls.append(self.t)
            return dict(infos[self.t])
    return types.SimpleNamespace(download=download, Ticker=Ticker)


def test_fetch_us_refetches_old_cache_entries_and_blanks_the_published_rows(tmp_path, monkeypatch):
    today = dt.date(2026, 11, 12)
    syms = ["AAPL", "TSM", "KSPI", "FISV"]
    infos = {"AAPL": info("USD", shortName="Apple Inc."), "TSM": info("TWD"), "KSPI": info("KZT", shortName="Kaspi.kz"),
             "FISV": info(None, shortName="Fiserv")}
    calls = []
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(syms, infos, calls, today - dt.timedelta(days=500), today))
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today - dt.timedelta(days=1))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    path = str(tmp_path / "us-info.json.gz")
    monkeypatch.setattr(F, "US_INFO_PATH", path)
    # 어제 받은 예전 모양 보관본 (k 없음 · financialCurrency 없음): 3일이 안 됐어도 다시 받아야 해요. AAPL 만 새 모양.
    old = {t: {"at": "2026-11-11", "px": 100.0, "info": {k: v for k, v in infos[t].items() if k not in ("financialCurrency", "currency")}}
           for t in syms}
    old["AAPL"] = {"at": "2026-11-11", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": dict(infos["AAPL"])}   # 새 모양 (통화 칸 있음)
    F.save_us_info(old, path)
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    us, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    assert sorted(calls) == ["FISV", "KSPI", "TSM"]                    # 예전 모양 셋만 (AAPL 은 새 모양 · 어제 받음)
    assert any("재무제표 통화(financialCurrency)를 담기 전 모양 3곳" in x for x in lines), lines
    by = {r["t"]: r for r in us}
    assert by["TSM"]["fcur"] == "TWD" and by["KSPI"]["fcur"] == "KZT"
    for t in ("TSM", "KSPI"):
        assert not any(k in by[t] for k in ("per", "pbr", "dy")), by[t]
        assert by[t]["cap"] > 0 and by[t]["roe"] > 0
    assert "fcur" not in by["AAPL"] and by["AAPL"]["pbr"] > 0
    assert "fcur" not in by["FISV"] and by["FISV"]["pbr"] > 0             # 모름: 비우지 않아요 (로그에 남아요)
    assert any(x.startswith("· 미국 재무제표 통화가 달러가 아닌 회사: 2곳") for x in lines), lines
    assert any("통화를 모르는 회사 1곳" in x and x.endswith("FISV") for x in lines), lines
    back = F.load_us_info(path)
    assert all(back[t]["k"] == F.US_INFO_SCHEMA for t in syms)
    assert back["TSM"]["info"]["financialCurrency"] == "TWD"
    calls.clear()                                                      # 다음 날: 다시 받지 않아요
    us2, *_ = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    assert calls == [] and {r["t"]: r.get("fcur") for r in us2}["TSM"] == "TWD"
    json.dumps(us, allow_nan=False)


# ── 관문 ─────────────────────────────────────────────────
def gate_row(us):
    rep = V.Report()
    V.check_us_fcur(rep, us)
    assert len(rep.rows) == 1
    return rep.rows[0]


def us_row(t, **kw):
    s = {"t": t, "cls": "us", "price": 10.0, "cap": 1.0, "roe": 12.0}
    s.update(kw)
    return s


def test_gate_passes_blanked_companies_and_shows_the_count():
    us = [us_row("TSM", fcur="TWD"), us_row("KSPI", fcur="KZT"), us_row("ASML", fcur="EUR"), us_row("SNY", fcur="EUR"),
          us_row("AAPL", per=30.0, pbr=40.0, dy=0.4, vz=3)]
    name, value, _, st = gate_row(us)
    assert name == ROW and st == "PASS"
    assert value == "4곳 (EUR 2 · KZT 1 · TWD 1) · 남은 칸 0"


@pytest.mark.parametrize("k,v", [("per", 26.1), ("pbr", 78.88), ("dy", 0.94), ("dy", 0.0), ("vz", 0), ("pbr", 0)])
def test_gate_fails_when_a_blanked_number_is_left(k, v):
    name, value, _, st = gate_row([us_row("TSM", fcur="TWD", **{k: v}), us_row("KSPI", fcur="KZT")])
    assert st == "FAIL" and f"TSM.{k}" in value and value.startswith("2곳 (KZT 1 · TWD 1) · 남은 칸 1"), value


@pytest.mark.parametrize("fc", ["USD", "twd", "TW", "", None, 7])
def test_gate_fails_on_a_bad_currency_code(fc):
    _, value, _, st = gate_row([us_row("TSM", fcur=fc)])
    assert st == "FAIL" and "TSM.fcur" in value, value


def test_gate_never_fails_because_yahoo_omitted_the_currency():
    # fcur 가 없는 회사(달러거나 야후가 통화를 주지 않음)는 PBR 이 있어도 이 줄은 통과 · 오늘의 발행본(fcur 없음)도 통과
    _, value, _, st = gate_row([us_row("FISV", per=12.0, pbr=3.0, dy=1.0, vz=50), us_row("TSM", per=26.8, pbr=78.88, dy=0.94, vz=0)])
    assert st == "PASS" and value == "0곳 · 남은 칸 0"
    cur, prev, final = good_pair()
    rep = V.run_checks(cur, prev, final, dt.date(2026, 10, 31), count_between=lambda a, b: 1,
                       sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                       now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
    rows = [r for r in rep.rows if r[0] == ROW]
    assert len(rows) == 1 and rows[0][3] == "PASS" and rows[0][1] == "0곳 · 남은 칸 0"


def test_gate_row_runs_inside_run_checks_on_the_us_list():
    cur, prev, final = good_pair()
    us = [s for s in cur["data"]["stocks"] if s.get("cls") == "us" and not s.get("etf")]
    us[0]["fcur"] = "TWD"
    for k in ("per", "pbr", "dy", "vz"):
        us[0].pop(k, None)
    us[1]["fcur"], us[1]["pbr"] = "SEK", 0.35                          # 남은 PBR
    rep = V.run_checks(cur, prev, final, dt.date(2026, 10, 31), count_between=lambda a, b: 1,
                       sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                       now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
    rows = [r for r in rep.rows if r[0] == ROW]
    assert len(rows) == 1 and rows[0][3] == "FAIL" and f"{us[1]['t']}.pbr" in rows[0][1], rows
    assert rows[0][1].startswith("2곳 (SEK 1 · TWD 1)")
