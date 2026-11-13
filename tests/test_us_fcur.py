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
UNK = "미국 재무제표 통화를 모르는 회사 (경고만)"
LOST = "어제 재무제표 통화가 있던 미국 종목이 오늘 통화 없음"
PBR0 = "미국 PBR 0 근처라 비운 종목: PBR·가치 점수 빈 칸"
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
    assert r["fcur"] == "CAD" and "dy" not in r                      # 12개월 배당 없음의 근거가 없으면 0% 도 비워요
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
    assert F.US_INFO_SCHEMA == 3 and {"financialCurrency", "currency", "totalRevenue"} <= set(F.US_INFO_KEYS)
    assert F.us_info_due(None, today) is True
    assert F.us_info_due({"at": "2026-11-12", "k": F.US_INFO_SCHEMA, "info": {}}, today) is False
    assert F.us_info_due({"at": "2026-11-12", "info": {}}, today) is True          # 예전 모양: 다시 받아요
    assert F.us_info_due({"at": "2026-11-12", "k": 1, "info": {}}, today) is True
    assert F.us_info_due({"at": "2026-11-12", "k": 2, "info": {}}, today) is True          # 2 = totalRevenue 전 모양
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
    assert lines[1] == "· 그중 배당수익률 0% 를 남긴 회사 (야후가 지난 12개월 배당 없음을 분명히 말함 · Jack 2026-11-13): 0곳"
    assert lines[2].startswith("  !! 미국 재무제표 통화를 모르는 회사 1곳") and lines[2].endswith("FISV")


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
            if infos[self.t] is None:                                   # 야후가 거절 (예외)
                raise RuntimeError("401 Unauthorized")
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
    assert any("예전 모양" in x and "3곳" in x and "받은 날과 상관없이" in x for x in lines), lines
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
    assert calls == ["FISV"] and {r["t"]: r.get("fcur") for r in us2}["TSM"] == "TWD"   # 통화 없는 회사 응답만 다시 물어요 (#114 리뷰 2)
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


@pytest.mark.parametrize("k,v", [("per", 26.1), ("pbr", 78.88), ("dy", 0.94), ("dy", 0.01), ("vz", 0), ("pbr", 0)])   # 0% 는 스위치 시험이 봐요
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



# ── #114 리뷰 ────────────────────────────────────────────
def _setup_fetch(tmp_path, monkeypatch, syms, infos, old=None, today=dt.date(2026, 11, 12)):
    calls, lines = [], []
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(syms, infos, calls, today - dt.timedelta(days=500), today))
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today - dt.timedelta(days=1))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    path = str(tmp_path / "us-info.json.gz")
    monkeypatch.setattr(F, "US_INFO_PATH", path)
    if old:
        F.save_us_info(old, path)
    monkeypatch.setattr(F, "log", lines.append)
    return calls, lines, path


def test_merge_keeps_only_descriptive_fields():
    prev = {"at": "2026-11-11", "k": 3, "info": {"financialCurrency": "TWD", "sector": "Technology", "industry": "Semiconductors",
                                                "longBusinessSummary": "Makes chips.", "priceToBook": 76.7, "trailingPE": 26.0,
                                                "dividendYield": 0.9, "marketCap": 2e12, "quoteType": "EQUITY", "currency": "USD"}}
    new = {"shortName": "TSMC", "trailingPE": 25.0, "marketCap": 2.1e12}          # 시세만 담은 응답
    got, kept, age = F.us_info_merge(new, prev, dt.date(2026, 11, 12))
    assert age == 1
    assert got["financialCurrency"] == "TWD" and got["sector"] == "Technology" and got["longBusinessSummary"] == "Makes chips."
    assert got["trailingPE"] == 25.0 and got["marketCap"] == 2.1e12
    assert "priceToBook" not in got and "dividendYield" not in got                # 숫자는 옛 값을 쓰지 않아요
    assert set(kept) == {"financialCurrency", "sector", "industry", "longBusinessSummary", "quoteType", "currency"}
    assert set(F.US_INFO_STICKY).isdisjoint({"trailingPE", "priceToBook", "dividendYield", "marketCap", "averageVolume", "returnOnEquity",
                                             "operatingMargins", "revenueGrowth", "debtToEquity", "totalRevenue"})
    assert F.us_info_merge({"shortName": "X", "financialCurrency": "USD"}, prev, dt.date(2026, 11, 12))[0]["financialCurrency"] == "USD"   # 새 값이 이겨요
    assert F.us_info_merge(new, None, dt.date(2026, 11, 12)) == (new, [], None)
    assert F.us_info_merge(new, {"at": "x"}, dt.date(2026, 11, 12)) == (new, [], None)


def test_quote_only_response_keeps_the_currency(tmp_path, monkeypatch):
    """시세만 담은 응답(이름은 있는데 financialCurrency · 업종 · 설명이 없음)이 와도 TSM 은 TWD 그대로 — PBR 78 이 다시 나가지 않아요."""
    syms = ["TSM", "AAPL"]
    full = info("TWD")
    quote_only = {k: full[k] for k in ("shortName", "trailingPE", "priceToBook", "dividendYield", "marketCap", "averageVolume")}
    old = {"TSM": {"at": "2026-11-05", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": full},              # 7일 전 · 새 모양
           "AAPL": {"at": "2026-11-11", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": info("USD", shortName="Apple Inc.")}}
    calls, lines, path = _setup_fetch(tmp_path, monkeypatch, syms, {"TSM": quote_only, "AAPL": info("USD")}, old)
    us, *_rest, meta = F.fetch_us(dt.date(2026, 11, 12) - dt.timedelta(days=500), dt.date(2026, 11, 12), 0.03)
    assert calls == ["TSM"]
    by = {r["t"]: r for r in us}
    assert by["TSM"]["fcur"] == "TWD" and not any(k in by["TSM"] for k in ("per", "pbr", "dy"))
    assert by["TSM"]["de"] == "Makes chips." and by["TSM"]["s"] == F.map_sector_us("Technology", "Semiconductors")
    assert any(x.startswith("  !! 야후 응답에 재무제표 통화가 없어 예전 값을 그대로 씀: 1곳 · 가장 오래된 예전 값 7일 전 (TSM)") for x in lines), lines
    assert any("설명 칸" in x and "TSM" in x for x in lines), lines
    back = F.load_us_info(path)["TSM"]
    assert back["at"] == "2026-11-12" and back["info"]["financialCurrency"] == "TWD" and back["info"]["trailingPE"] == full["trailingPE"]
    assert meta["usFcurUnknown"] == []


def test_refused_refetch_of_an_old_entry_is_counted_unknown_and_retried(tmp_path, monkeypatch):
    """예전 모양 항목(k 없음 · 통화 칸 없음)을 다시 받지 못하면: 이름 · 업종은 예전 항목 그대로, 통화를 모르는 회사로 세고 (data.json
    usFcurUnknown), 비우지 않아요. 다음 실행이 또 받아요."""
    syms = ["TSM", "AAPL"]
    old_info = {k: v for k, v in info("TWD").items() if k not in ("financialCurrency", "currency")}
    old = {"TSM": {"at": "2026-11-11", "px": 100.0, "info": old_info},
           "AAPL": {"at": "2026-11-11", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": info("USD", shortName="Apple Inc.")}}
    infos = {"TSM": None, "AAPL": info("USD")}
    calls, lines, path = _setup_fetch(tmp_path, monkeypatch, syms, infos, old)
    us, *_rest, meta = F.fetch_us(dt.date(2026, 11, 12) - dt.timedelta(days=500), dt.date(2026, 11, 12), 0.03)
    assert calls == ["TSM", "TSM", "TSM"]                                  # 세 번 (쉬었다가 더 천천히) 모두 거절
    by = {r["t"]: r for r in us}
    assert by["TSM"]["nk"] == "Taiwan Semiconductor Manufactur" and "fcur" not in by["TSM"] and by["TSM"]["pbr"] > 0
    assert meta["usFcurUnknown"] == ["TSM"]
    assert any("통화를 모르는 회사 1곳" in x and x.endswith("TSM") for x in lines), lines
    assert "k" not in F.load_us_info(path)["TSM"]                        # 예전 항목 그대로 → 다음 실행이 다시 받아요
    calls.clear()
    infos["TSM"] = info("TWD")
    us2, *_rest, meta2 = F.fetch_us(dt.date(2026, 11, 12) - dt.timedelta(days=500), dt.date(2026, 11, 12), 0.03)
    assert calls == ["TSM"] and {r["t"]: r.get("fcur") for r in us2}["TSM"] == "TWD" and meta2["usFcurUnknown"] == []


def test_pbr_that_rounds_to_zero_and_margin_without_revenue_are_blank(tmp_path, monkeypatch):
    r = rec("BRK-B", 500.0)
    F.apply_us_info(r, info("USD", shortName="Berkshire", priceToBook=0.0011), 500.0, FX)
    assert "pbr" not in r and r["per"] > 0                               # 0.00 으로 반올림 → 빈 칸 (0 이 아니에요)
    r2 = rec("X", 500.0)
    F.apply_us_info(r2, info("USD", priceToBook=0.0049), 500.0, FX)
    assert "pbr" not in r2
    r3 = rec("Y", 500.0)
    F.apply_us_info(r3, info("USD", priceToBook=0.005), 500.0, FX)
    assert r3["pbr"] == 0.01                                             # 0.005 이상은 그대로 (0.01 로 반올림)
    for rev, want in ((None, None), (0, None), (1.2e9, 0.0)):
        r4 = rec("ERIC", 10.0)
        i = info("USD", operatingMargins=0.0)
        if rev is not None:
            i["totalRevenue"] = rev
        F.apply_us_info(r4, i, 10.0, FX)
        assert r4.get("opm") == want, (rev, r4.get("opm"))                # 매출이 없을 때만 빈 칸 · 매출이 있으면 0.0% 는 진짜
    r5 = rec("BIO", 10.0)
    F.apply_us_info(r5, info("USD", operatingMargins=-3.2), 10.0, FX)    # 매출 없음 + 0 이 아닌 값: 그대로 (범위 밖이면 예전처럼 빈 칸)
    assert r5["opm"] == -320.0
    us = [r, rec("U1", 10.0), rec("U2", 10.0)]
    for x, pb in zip(us[1:], (1.0, 2.0)):
        F.apply_us_info(x, info("USD", priceToBook=pb), 10.0, FX)
    F.add_percentiles(us)
    assert "vz" not in us[0] and us[1]["vz"] == 50 and us[2]["vz"] == 0
    assert F.us_info_cuts({"priceToBook": 0.0011}) == ["pbr"] and F.us_info_cuts({"priceToBook": 0.0}) == []
    assert F.us_info_cuts({"operatingMargins": 0.0, "totalRevenue": 0}) == ["opm"] and F.us_info_cuts({"operatingMargins": 0.0, "totalRevenue": 5}) == []
    # fetch_us 가 티커와 함께 크게 남겨요
    syms = ["BRK-B", "ERIC", "AAPL"]
    infos = {"BRK-B": info("USD", shortName="Berkshire", priceToBook=0.0011), "ERIC": info("SEK", shortName="Ericsson", operatingMargins=0.0),
             "AAPL": info("USD", shortName="Apple")}
    calls, lines, path = _setup_fetch(tmp_path, monkeypatch, syms, infos)
    usx, *_ = F.fetch_us(dt.date(2026, 11, 12) - dt.timedelta(days=500), dt.date(2026, 11, 12), 0.03)
    by = {x["t"]: x for x in usx}
    assert "pbr" not in by["BRK-B"] and "opm" not in by["ERIC"] and by["AAPL"]["opm"] > 0
    assert any(x.startswith("  !! 미국 PBR 이 0.00 으로 반올림돼") and x.endswith("1곳 (BRK-B)") for x in lines), lines
    assert any(x.startswith("  !! 미국 영업이익률이 정확히 0 인데 매출") and x.endswith("1곳 (ERIC)") for x in lines), lines
    assert not any("_cut" in k or k.startswith("_") and k != "_yind" for x in usx for k in x)
    json.dumps(usx, allow_nan=False)


NO_DIV = {"dividendYield": 0.0, "trailingAnnualDividendRate": 0.0}         # 2026-11-13 의 PDD · LI · ABVX … (dividendRate 없음)
TODAY = dt.date(2026, 11, 13)


def epoch(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def test_no_dividend_evidence_must_be_clear():
    """Jack, 2026-11-13: 0% 는 자료가 지난 12개월 배당 없음을 분명히 말할 때만. 근거: dividendYield 0 · trailingAnnualDividendRate 0 ·
    dividendRate 없음 · 배당 날짜(lastDividendDate · exDividendDate)가 없거나 365일보다 오래됨. 하나라도 불분명하면 False."""
    ok = F.us_no_dividend_12m
    assert ok(NO_DIV, TODAY) is True                                        # PDD · LI · ABVX · ASND · BIDU · PAYP · VFS
    assert ok({**NO_DIV, "lastDividendDate": epoch(dt.date(2022, 6, 2)), "exDividendDate": epoch(dt.date(2022, 6, 2))}, TODAY) is True   # BNTX
    assert ok({**NO_DIV, "lastDividendDate": epoch(dt.date(2025, 3, 17))}, TODAY) is True   # TCOM: 20개월 전이 마지막
    assert ok({**NO_DIV, "lastDividendDate": epoch(dt.date(2026, 9, 10))}, TODAY) is False  # 12개월 안에 배당 (KSPI 모양)
    assert ok({**NO_DIV, "exDividendDate": epoch(dt.date(2026, 12, 10))}, TODAY) is False   # 앞으로 올 배당 기준일
    assert ok({**NO_DIV, "lastDividendDate": epoch(TODAY - dt.timedelta(days=364))}, TODAY) is False
    assert ok({**NO_DIV, "lastDividendDate": epoch(TODAY - dt.timedelta(days=366))}, TODAY) is True
    assert ok({**NO_DIV, "dividendRate": 5.74}, TODAY) is False             # KSPI: 지난 12개월 합은 0 인데 배당률은 있어요
    assert ok({"dividendYield": 0.0}, TODAY) is False                       # 12개월 합 칸이 없음 → 불분명
    assert ok({**NO_DIV, "dividendYield": None}, TODAY) is False
    assert ok({**NO_DIV, "dividendYield": 0.4}, TODAY) is False
    assert ok({**NO_DIV, "trailingAnnualDividendRate": 0.3}, TODAY) is False
    assert ok({**NO_DIV, "lastDividendDate": "soon"}, TODAY) is False
    assert ok(NO_DIV, None) is False and ok(None, TODAY) is False


@pytest.mark.parametrize("keep", [False, True])
def test_zero_yield_switch_pipeline_and_gate_agree(keep, monkeypatch):
    monkeypatch.setattr(F, "US_FCUR_KEEP_ZERO_DY", keep)
    monkeypatch.setattr(V, "US_FCUR_KEEP_ZERO_DY", keep)
    assert V.US_FCUR_KEEP_ZERO_DY is keep and F.US_FCUR_KEEP_ZERO_DY is keep
    r = rec("CAE", 28.0)
    F.apply_us_info(r, info("CAD", **NO_DIV, lastDividendDate=epoch(dt.date(2020, 3, 12))), 28.0, FX, today=TODAY)
    unclear = rec("Q", 28.0)
    F.apply_us_info(unclear, info("CAD", dividendYield=0.0), 28.0, FX, today=TODAY)     # 12개월 합 칸 없음
    no_day = rec("N", 28.0)
    F.apply_us_info(no_day, info("CAD", **NO_DIV), 28.0, FX)                            # 날짜를 모르면 비워요
    r2 = rec("TSM")
    F.apply_us_info(r2, info("TWD"), 401.98, FX, today=TODAY)              # 0 이 아닌 배당수익률은 어느 쪽이든 빈 칸
    assert ("dy" in r) is keep and (r.get("dy") == 0.0 if keep else True) and "dy" not in r2
    assert "dy" not in unclear and "dy" not in no_day
    assert not any(k in r for k in ("per", "pbr"))
    _, value, _, st = gate_row([us_row("CAE", fcur="CAD", dy=0.0), us_row("TSM", fcur="TWD")])
    assert st == ("PASS" if keep else "FAIL"), value
    _, value, _, st = gate_row([us_row("TSM", fcur="TWD", dy=0.94)])
    assert st == "FAIL"                                                  # 0 이 아닌 값은 언제나 실패


def test_the_shipped_switch_keeps_only_clear_zero_yields():
    assert V.US_FCUR_KEEP_ZERO_DY is True and F.US_FCUR_KEEP_ZERO_DY is True     # Jack, 2026-11-13
    r = rec("PDD", 77.0)
    F.apply_us_info(r, info("CNY", **NO_DIV), 77.0, FX, today=TODAY)
    assert r["dy"] == 0.0 and r["fcur"] == "CNY" and not any(k in r for k in ("per", "pbr"))
    sm = F.us_fcur_summary([r], {"PDD": info("CNY", **NO_DIV)})
    assert sm["zeroDy"] == ["PDD"] and sm["cut"]["dy"] == 0


def test_pbr_zero_is_marked_but_not_for_currency_companies():
    r = rec("BRK-B", 500.0)
    F.apply_us_info(r, info("USD", shortName="Berkshire", priceToBook=0.0011), 500.0, FX)
    assert r["pbrZero"] is True and "pbr" not in r and "fcur" not in r
    r2 = rec("TINY", 10.0)
    F.apply_us_info(r2, info("TWD", priceToBook=0.001), 10.0, FX)          # 통화 줄이 이미 말해요
    assert "pbrZero" not in r2 and r2["fcur"] == "TWD"
    F.apply_us_info(r, info("USD", shortName="Berkshire", priceToBook=1.5), 500.0, FX)
    assert "pbrZero" not in r and r["pbr"] == 1.5                          # 다시 붙이면 표시가 남지 않아요
    rows, _ = more_rows({"usFcurUnknown": []}, [us_row("BRK-B", pbrZero=True)], None)
    assert rows[PBR0][3] == "PASS" and rows[PBR0][1] == "1곳: BRK-B · 남은 칸 0"
    for bad in ({"pbrZero": True, "pbr": 0.0}, {"pbrZero": True, "vz": 100}, {"pbrZero": 1}):
        rows, _ = more_rows({"usFcurUnknown": []}, [us_row("BRK-B", **bad)], None)
        assert rows[PBR0][3] == "FAIL", (bad, rows[PBR0])
    rows, _ = more_rows({"usFcurUnknown": []}, [us_row("AAPL", pbr=40.0)], None)
    assert rows[PBR0][3] == "PASS" and rows[PBR0][1] == "0곳 · 남은 칸 0"


def test_summary_counts_etfs_with_a_currency_and_logs_quote_currency():
    us = []
    for t, fc, etf, qc in (("TSM", "TWD", False, "USD"), ("EWT", "TWD", True, "USD"), ("SPY", None, True, "USD"), ("ODD", "USD", False, "EUR")):
        r = rec(t)
        F.apply_us_info(r, info(fc, currency=qc) if fc else info(currency=qc), 401.98, FX)
        r["etf"] = etf
        us.append(r)
    infos = {"TSM": info("TWD"), "EWT": info("TWD"), "SPY": info(), "ODD": info("USD", currency="EUR")}
    sm = F.us_fcur_summary(us, infos)
    assert sm["hit"] == [("EWT", "TWD"), ("TSM", "TWD")] and sm["unknown"] == [] and sm["quoteCur"] == [("ODD", "EUR")]
    rep = V.Report()
    V.check_us_fcur(rep, us)
    assert rep.rows[0][1].startswith("2곳 (TWD 2)")                       # 파이프라인 로그와 관문이 같은 수를 세요
    lines = []
    orig = F.log
    try:
        F.log = lines.append
        F.log_us_fcur(sm)
    finally:
        F.log = orig
    assert lines[0].startswith("· 미국 재무제표 통화가 달러가 아닌 회사: 2곳")
    assert any(x.startswith("  !! 야후가 가격 통화(currency)를 달러가 아니라고 한 미국 종목 1곳") and "ODD(EUR)" in x for x in lines), lines
    assert "dy" in us[3] and "fcur" not in us[3]                          # 가격 통화로는 비우지 않아요




def more_rows(data, us, pdata):
    rep = V.Report()
    V.check_us_fcur_more(rep, data, us, pdata)
    return {r[0]: r for r in rep.rows}, rep


def test_gate_warns_on_unknown_currency_and_never_fails():
    rows, rep = more_rows({"usFcurUnknown": ["FISV"]}, [], None)
    assert rows[UNK][3] == "WARN" and rows[UNK][1] == "1곳: FISV" and LOST not in rows
    assert rep.details == [("재무제표 통화를 모르는 미국 회사 (usFcurUnknown)", ["FISV"])]
    many = [f"T{i:02d}" for i in range(13)]
    rows, _ = more_rows({"usFcurUnknown": many}, [], None)
    assert rows[UNK][3] == "WARN" and rows[UNK][1].endswith("T09 외 3곳")
    rows, _ = more_rows({"usFcurUnknown": []}, [], None)
    assert rows[UNK][3] == "PASS" and rows[UNK][1] == "0곳"
    rows, _ = more_rows({}, [], None)                                     # 이 칸 전 발행본 (오늘의 사이트): 통과
    assert rows[UNK][3] == "PASS" and "기록 없음" in rows[UNK][1]


def test_lost_currency_row_cases():
    """어제 fcur 가 있던 종목이 오늘 fcur 없이 목록에 있을 때 (코디네이터 결정 2026-11-13):
    통화 정보가 없는데 PER · PBR · 배당이 있으면 실패 (고장) · 야후가 이제 달러라고 하면 숫자가 있든 없든 경고 · 정보도 숫자도 없으면 경고."""
    prev = {"stocks": [us_row("TSM", fcur="TWD"), us_row("KSPI", fcur="KZT"), us_row("ERIC", fcur="SEK"), us_row("GONE", fcur="EUR")]}
    named = lambda t, **kw: us_row(t, nk=f"{t} Corp", **kw)     # noqa: E731 — 오늘 상세 정보가 붙은 종목 (이름이 티커가 아님)
    # 1. 그대로 (GONE 은 목록에서 빠짐): 통과
    rows, _ = more_rows({"usFcurUnknown": []}, [named("TSM", fcur="TWD"), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "PASS" and rows[LOST][1] == "0곳"
    # 2. 통화 정보 없음 (usFcurUnknown 안) · 숫자 없음: 경고
    rows, rep = more_rows({"usFcurUnknown": ["KSPI"]}, [named("TSM", fcur="TWD"), named("KSPI"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "WARN" and rows[LOST][1] == "1곳 · 통화 정보 · 숫자 없음 1곳: KSPI", rows[LOST]
    # 3. 통화 정보 없음 · 숫자 다시 나감: 실패
    rows, rep = more_rows({"usFcurUnknown": ["TSM"]}, [named("TSM", per=26.8, pbr=78.88, dy=0.94), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "FAIL" and rows[LOST][1] == "1곳 · 통화 정보 없이 숫자 있음 1곳: TSM", rows[LOST]
    assert ("어제 fcur 가 있었는데 오늘 통화 정보 없이 PER·PBR·배당이 나간 미국 종목 (고장)", ["TSM"]) in rep.details
    # 4. 야후가 이제 달러라고 함 (usFcurUnknown 밖 · 상세 정보 있음) · 숫자 다시 나감: 실패가 아니라 경고
    rows, rep = more_rows({"usFcurUnknown": []}, [named("TSM", per=26.8, pbr=24.0, dy=0.94), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "WARN", rows[LOST]
    assert rows[LOST][1] == "1곳 · 달러로 바뀜 1곳 (야후가 이제 달러 재무제표라고 함 — 숫자를 확인하세요): TSM"
    assert ("어제 fcur 가 있었는데 야후가 이제 달러 재무제표라고 하는 미국 종목 (숫자를 확인하세요)", ["TSM"]) in rep.details
    # 5. 달러로 바뀜 · 숫자 없음: 경고 (같은 문구)
    rows, _ = more_rows({"usFcurUnknown": []}, [named("TSM"), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "WARN" and "달러로 바뀜 1곳" in rows[LOST][1]
    # 6. 오늘 발행에 usFcurUnknown 칸이 없음 (모름) · 숫자 있음: 실패
    rows, _ = more_rows({}, [named("TSM", pbr=78.88), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "FAIL", rows[LOST]
    # 7. 상세 정보가 붙지 않은 종목 (이름 = 티커): 숫자 있으면 실패 · 없으면 경고 (달러라고 한 적이 없어요)
    rows, _ = more_rows({"usFcurUnknown": []}, [us_row("TSM", nk="TSM", pbr=78.88), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "FAIL"
    rows, _ = more_rows({"usFcurUnknown": []}, [us_row("TSM", nk="TSM"), named("KSPI", fcur="KZT"), named("ERIC", fcur="SEK")], prev)
    assert rows[LOST][3] == "WARN" and rows[LOST][1] == "1곳 · 통화 정보 · 숫자 없음 1곳: TSM"
    # 8. 셋이 섞이면: 실패 하나가 줄을 실패로, 값에는 셋 모두 (실패 쪽이 먼저)
    rows, rep = more_rows({"usFcurUnknown": ["KSPI", "ERIC"]}, [named("TSM", pbr=24.0), named("KSPI", pbr=0.01), named("ERIC")], prev)
    assert rows[LOST][3] == "FAIL"
    assert rows[LOST][1] == ("3곳 · 통화 정보 없이 숫자 있음 1곳: KSPI · 달러로 바뀜 1곳 (야후가 이제 달러 재무제표라고 함 — 숫자를 확인하세요): TSM"
                             " · 통화 정보 · 숫자 없음 1곳: ERIC"), rows[LOST]


def test_new_rows_inside_run_checks():
    cur, prev, final = good_pair()
    pus = [s for s in prev["data"]["stocks"] if s.get("cls") == "us" and not s.get("etf")]
    cus = {s["t"]: s for s in cur["data"]["stocks"]}
    pus[0]["fcur"] = "TWD"                                               # 어제는 통화가 있었는데 오늘은 없고 PBR 이 있어요
    cus[pus[0]["t"]]["pbr"] = 78.88
    assert "fcur" not in cus[pus[0]["t"]] and cus[pus[0]["t"]]["nk"] != pus[0]["t"]
    run = lambda: V.run_checks(cur, prev, final, dt.date(2026, 10, 31), count_between=lambda a, b: 1,   # noqa: E731
                               sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                               now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
    cur["data"]["usFcurUnknown"] = [pus[0]["t"]]                         # 통화 정보 없음 + 숫자: 실패 (발행을 막아요)
    rows = {r[0]: r for r in run().rows}
    assert rows[LOST][3] == "FAIL" and rows[UNK][3] == "WARN", (rows[LOST], rows[UNK])
    cur["data"]["usFcurUnknown"] = []                                    # 야후가 이제 달러라고 함 + 숫자: 경고 (발행은 나가요)
    rep = run()
    rows = {r[0]: r for r in rep.rows}
    assert rows[LOST][3] == "WARN" and "야후가 이제 달러 재무제표라고 함 — 숫자를 확인하세요" in rows[LOST][1] and rows[UNK][3] == "PASS"
    assert LOST not in {r[0] for r in rep.failed}
    live = V.run_checks(cur, None, final, dt.date(2026, 10, 31), mode="live", count_between=lambda a, b: 1,
                        sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                        now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
    assert LOST not in {r[0] for r in live.rows} and UNK in {r[0] for r in live.rows}   # 사이트 점검: 절대 기준만



# ── #114 리뷰 2 ──────────────────────────────────────────
def test_merge_only_from_the_same_company_or_a_recent_entry():
    """N1: 예전 항목이 같은 회사(이름이 같음)이거나 14일 안일 때만 채워요. 40일 된 다른 회사 항목(티커를 물려받은 회사)은 쓰지 않아요."""
    today = dt.date(2026, 11, 12)
    other_old = {"at": "2026-10-03", "k": 3, "info": {"shortName": "Old Corp Ltd", "financialCurrency": "TWD", "sector": "Industrials"}}
    new = {"shortName": "New Company Inc.", "trailingPE": 10.0}
    assert F.us_info_merge(new, other_old, today) == (new, [], 40)                     # 40일 · 다른 회사: 채우지 않아요
    same_old = {**other_old, "info": {**other_old["info"], "shortName": "NEW COMPANY, INC"}}
    got, kept, age = F.us_info_merge(new, same_old, today)                              # 40일이어도 같은 회사(기호 · 대소문자 무시)
    assert age == 40 and got["financialCurrency"] == "TWD" and set(kept) == {"financialCurrency", "sector"}
    recent_other = {**other_old, "at": "2026-11-02"}
    got, kept, age = F.us_info_merge(new, recent_other, today)                          # 10일 안이면 이름이 달라도 (그 사이 이름만 바뀐 회사)
    assert age == 10 and got["financialCurrency"] == "TWD"
    assert F.us_info_merge(new, other_old, None)[1] == []                               # 날짜를 모르면 이름으로만


def test_partial_answers_are_due_again_and_listed(tmp_path, monkeypatch):
    """S1 · S2: 일부만 온 응답(예전 값으로 채움 · 회사인데 통화 없음)은 오늘 받은 것으로 3일 두지 않고 다음 실행에서 다시 물어요.
    예전 값으로 채운 종목은 data.json usInfoPartial 에 남아요 (관문이 경고). 다 온 응답 · ETF 는 그렇지 않아요."""
    assert F.us_info_partial({"quoteType": "EQUITY"}, []) is True                       # 회사인데 통화 없음
    assert F.us_info_partial({"quoteType": "EQUITY", "financialCurrency": "USD"}, []) is False
    assert F.us_info_partial({"quoteType": "ETF"}, []) is False and F.us_info_partial({}, [], etf=True) is False
    assert F.us_info_partial({"financialCurrency": "TWD"}, ["sector"]) is True           # 예전 값으로 채움
    assert F.us_info_due({"at": "2026-11-12", "k": F.US_INFO_SCHEMA, "due": True}, dt.date(2026, 11, 12)) is True
    syms = ["TSM", "AAPL", "SPY"]
    full = info("TWD")
    quote_only = {k: full[k] for k in ("shortName", "trailingPE", "priceToBook", "dividendYield", "marketCap", "averageVolume")}
    old = {"TSM": {"at": "2026-11-05", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": full},
           "AAPL": {"at": "2026-11-05", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": info("USD", shortName="Apple Inc.")},
           "SPY": {"at": "2026-11-05", "px": 100.0, "k": F.US_INFO_SCHEMA, "info": {"shortName": "SPDR S&P 500", "quoteType": "ETF"}}}
    infos = {"TSM": quote_only, "AAPL": info("USD", shortName="Apple Inc."), "SPY": {"shortName": "SPDR S&P 500", "quoteType": "ETF"}}
    calls, lines, path = _setup_fetch(tmp_path, monkeypatch, syms, infos, old)
    today = dt.date(2026, 11, 12)
    us, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    assert sorted(calls) == ["AAPL", "SPY", "TSM"]                                       # 7일 전 항목: 모두 받을 날
    back = F.load_us_info(path)
    assert back["TSM"].get("due") is True and "due" not in back["AAPL"] and "due" not in back["SPY"]
    assert meta["usInfoPartial"] == ["TSM"]
    assert any("일부만 온 야후 응답" in x and "다음 실행에서 다시 물어봐요" in x and x.endswith("TSM") for x in lines), lines
    assert any("예전 값을 그대로 씀: 1곳 · 가장 오래된 예전 값 7일 전" in x for x in lines), lines
    calls.clear()
    infos["TSM"] = full                                                                  # 다음 실행: TSM 만 다시 묻고, 다 오면 끝
    us2, *_rest, meta2 = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    assert calls == ["TSM"] and "due" not in F.load_us_info(path)["TSM"] and meta2["usInfoPartial"] == []
    calls.clear()
    F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    assert calls == []


def test_partial_gate_row():
    PART = "미국 상세 정보가 일부만 온 종목 (예전 값으로 채움 · 경고만)"
    us = [us_row(f"U{i}") for i in range(20)]
    rows, rep = more_rows({"usFcurUnknown": [], "usInfoPartial": ["U0", "U1"]}, us, None)
    assert rows[PART][3] == "WARN" and rows[PART][1] == "2곳 (10.0%): U0, U1", rows[PART]
    assert ("야후 응답이 일부만 와 예전 설명 칸을 쓴 미국 종목 (usInfoPartial)", ["U0", "U1"]) in rep.details
    many = [f"U{i}" for i in range(12)]
    rows, _ = more_rows({"usFcurUnknown": [], "usInfoPartial": many}, us, None)
    assert rows[PART][3] == "WARN" and rows[PART][1].startswith("12곳 (60.0%): U0, U1") and rows[PART][1].endswith("U9 외 2곳")
    rows, _ = more_rows({"usFcurUnknown": [], "usInfoPartial": []}, us, None)
    assert rows[PART][3] == "PASS" and rows[PART][1] == "0곳 (0.0%)"
    rows, _ = more_rows({"usFcurUnknown": []}, us, None)
    assert rows[PART][3] == "PASS" and "기록 없음" in rows[PART][1]                       # 이 칸 전 발행본: 통과 (실패 없음)


def test_fetch_us_passes_today_so_a_clear_zero_yield_is_kept(tmp_path, monkeypatch):
    """N4 ①: 실제 실행(fetch_us)이 apply_us_info 에 today 를 넘겨야 0% 를 남겨요 (today 가 없으면 늘 비어요)."""
    syms = ["PDD", "BABA"]
    infos = {"PDD": info("CNY", shortName="PDD Holdings", quoteType="EQUITY", **NO_DIV),
             "BABA": info("CNY", shortName="Alibaba", quoteType="EQUITY", dividendYield=1.03, dividendRate=1.05, trailingAnnualDividendRate=7.2)}
    calls, lines, path = _setup_fetch(tmp_path, monkeypatch, syms, infos, today=dt.date(2026, 11, 13))
    us, *_ = F.fetch_us(dt.date(2026, 11, 13) - dt.timedelta(days=500), dt.date(2026, 11, 13), 0.03)
    by = {r["t"]: r for r in us}
    assert by["PDD"]["dy"] == 0.0 and by["PDD"]["fcur"] == "CNY" and "dy" not in by["BABA"]
    assert any("배당수익률 0% 를 남긴 회사" in x and "1곳 (PDD)" in x for x in lines), lines


def test_lost_currency_row_reacts_to_a_returned_yield_alone():
    """N4 ②: 통화 정보 없이 배당수익률만 다시 나가도 실패예요 (PER · PBR 이 없어도)."""
    prev = {"stocks": [us_row("TSM", fcur="TWD")]}
    rows, _ = more_rows({"usFcurUnknown": ["TSM"]}, [us_row("TSM", nk="TSM Corp", dy=0.94)], prev)
    assert rows[LOST][3] == "FAIL" and rows[LOST][1] == "1곳 · 통화 정보 없이 숫자 있음 1곳: TSM"


def test_pbr_cut_uses_todays_price():
    """N4 ③: 0.00 으로 반올림되는지는 오늘 가격에 맞춘 PBR 로 봐요 (받은 날 가격이 아니에요)."""
    r = rec("X", 50.0)                                                    # 받은 날 100 → 오늘 50: PBR 0.006 → 0.003 → 빈 칸
    F.apply_us_info(r, info("USD", priceToBook=0.006), 100.0, FX)
    assert "pbr" not in r and r["pbrZero"] is True
    r2 = rec("Y", 200.0)                                                  # 받은 날 100 → 오늘 200: PBR 0.004 → 0.008 → 0.01
    F.apply_us_info(r2, info("USD", priceToBook=0.004), 100.0, FX)
    assert r2["pbr"] == 0.01 and "pbrZero" not in r2
    assert F.us_info_cuts({"priceToBook": 0.006}, 0.5) == ["pbr"] and F.us_info_cuts({"priceToBook": 0.004}, 2.0) == []
