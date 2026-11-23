# -*- coding: utf-8 -*-
"""달러 아닌 재무제표 미국 회사(fcur)의 PER · PBR · 배당수익률을 회사 합계로 (Jack, 2026-11-13 "Next, within days") — fetch_data.py
us_fcur_* 와 validate_data.py check_us_fcur_tot. (네트워크 없음 · 야후 · ECOS 는 가짜)

- PER = 시가총액 ÷ 지난 4분기 순이익 · PBR = 시가총액 ÷ 최근 분기 자본 (둘 다 그 통화 금액을 미국 종가 시각의 환율로 달러로)
- 순이익은 두 길이 맞아야 · 자본 · 순이익은 최근 보고 분기 것이어야 · 환율은 야후(미국 종가 시각 1시간 봉) × ECOS 가 맞아야 · 아니면 빈 칸과 까닭
- 배당수익률은 실제 배당의 주기가 고르고 야후 배당수익률과 맞을 때만 · 0% 는 #114 규칙 그대로
- 스위치 validate_data.US_FCUR_TOT_ON 이 꺼져 있으면(지금) 종목 칸은 #114 그대로 빈 칸 · 기록(usFcurTot)과 관문 경고만
- 관문 줄은 경고만 (실패하지 않아요)
"""
import datetime as dt
import inspect
import json
import os
import sys
import types

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

D = dt.date(2026, 11, 20)            # 미국 기준일 (금요일)
TODAY = dt.date(2026, 11, 21)
NOW = dt.datetime(2026, 11, 20, 21, 40, tzinfo=dt.timezone.utc)   # 06:40 KST 다음 날 — 미국 정규장(16:00 뉴욕 = 21:00 UTC)이 끝난 뒤
ROW = V.US_FCUR_TOT_ROW


def ts(d):
    return pd.Timestamp(d)


def stmt(rows):
    """{줄 이름: {날짜: 값 | None}} → 야후 재무제표 모양 (줄 = 항목, 열 = 기간 끝)."""
    cols = sorted({c for v in rows.values() for c in v}, reverse=True)
    return pd.DataFrame({ts(c): {n: (v.get(c) if v.get(c) is not None else np.nan) for n, v in rows.items()} for c in cols})


def tsm_st():
    """TSMC 2026-11-20 의 모양 (야후 표 · 단위 TWD)."""
    return {"eq": [["2026-06-30", 6432.52e9], ["2026-09-30", 6997.90e9]], "eqRow": "Common Stock Equity",
            "bsCols": ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"],
            "q": [["2025-09-30", 452.30e9], ["2025-12-31", 485.47e9], ["2026-03-31", 572.48e9], ["2026-06-30", 706.56e9],
                  ["2026-09-30", 763.06e9]], "qRow": "Net Income Common Stockholders",
            "qCols": ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"],
            "ttm": [["2026-09-30", 2527.57e9]], "ttmCols": ["2026-09-30"]}


def tsm_info(**kw):
    i = {"marketCap": 5186472994 * 318.71, "netIncomeToCommon": 2527.57e9, "mostRecentQuarter": 1790726400,   # 2026-09-30
         "trailingPE": 20.66, "priceToBook": 61.2, "dividendYield": 1.18, "trailingAnnualDividendRate": 28.0, "dividendRate": 3.77,
         "financialCurrency": "TWD"}
    i.update(kw)
    return i


def tsm_rec(**kw):
    r = {"t": "TSM", "cls": "us", "fcur": "TWD", "price": 318.71, "etf": False, "cap": 2224.0, "roe": 41.9}
    r.update(kw)
    return r


def divs(pays):
    return pd.Series({ts(d): v for d, v in pays})


TSM_DIVS = [("2024-12-12", 0.616), ("2025-03-18", 0.684), ("2025-06-12", 0.78), ("2025-09-16", 0.822), ("2025-12-11", 0.835),
            ("2026-03-17", 0.956), ("2026-06-11", 0.955), ("2026-09-16", 1.107)]
FX_TWD = {"r": 32.988, "at": "2026-11-20T15:00:00-05:00", "e": 33.056, "eD": "2026-11-20", "why": None}


# ── 재무제표 표 읽기 ────────────────────────────────────────
def test_stmt_rows_prefer_common_equity_and_keep_every_column_date():
    df = stmt({"Stockholders Equity": {"2026-06-30": 24.14e9, "2026-09-30": None},
               "Common Stock Equity": {"2026-06-30": 20.65e9, "2026-09-30": None, "2026-03-31": 20.11e9}})
    name, rows, cols = F.us_fcur_stmt_rows(df, F.US_FCUR_EQ_ROWS)
    assert name == "Common Stock Equity"                                  # 우선주 · 소수주주 몫을 뺀 보통주 자본 (BCE · ENB)
    assert rows == [["2026-03-31", 20.11e9], ["2026-06-30", 20.65e9]]      # 값이 빈 열은 줄에 없어요
    assert cols == ["2026-03-31", "2026-06-30", "2026-09-30"]               # … 하지만 열 날짜에는 있어요 (새 분기가 비었음을 알아요)
    assert F.us_fcur_stmt_rows(None, F.US_FCUR_EQ_ROWS) == (None, [], [])
    assert F.us_fcur_stmt_rows(stmt({"Total Assets": {"2026-09-30": 1.0}}), F.US_FCUR_EQ_ROWS)[0] is None


def test_newest_period_counts_empty_new_columns_and_mrq():
    st = {"bsCols": ["2025-12-31", "2026-06-30"], "qCols": ["2026-06-30"], "ttm": [["2026-06-30", 1.0]]}
    assert F.us_fcur_newest(st) == "2026-06-30"
    assert F.us_fcur_newest(st, 1790726400) == "2026-09-30"                # 야후 mostRecentQuarter 가 더 늦으면 그것
    assert F.us_fcur_newest({}, None) is None


# ── 자본 · 순이익 ────────────────────────────────────────────
def test_equity_must_be_the_latest_reported_quarter():
    assert F.us_fcur_equity(tsm_st(), "2026-09-30", D) == (6997.90e9, "2026-09-30", None)
    ccep = {"eq": [["2025-06-30", 8.03e9], ["2025-12-31", 7.83e9]], "bsCols": ["2025-06-30", "2025-12-31", "2026-06-30"]}
    newest = F.us_fcur_newest(ccep, 1783036800)                            # 2026-07-03 (CCEP 반기 끝) · 2026-06-30 열은 비었어요
    assert F.us_fcur_equity(ccep, newest, D) == (None, "2025-12-31", "eqStale")
    asml = {"eq": [["2026-09-30", 22.06e9]]}
    assert F.us_fcur_equity(asml, "2026-09-27", D)[2] is None               # 52주 회계 (9-27 ↔ 9-30): 7일 안
    old = {"eq": [["2026-01-31", 1e9]]}
    assert F.us_fcur_equity(old, "2026-01-31", D) == (None, "2026-01-31", "eqStale")   # 280일 넘게 앞
    assert F.us_fcur_equity({"eq": [["2026-06-30", -116807e9]]}, "2026-06-30", D) == (None, "2026-06-30", "eqNeg")   # VinFast
    assert F.us_fcur_equity({}, "2026-09-30", D) == (None, None, "eqMissing")


def test_net_income_sums_four_quarters_and_needs_a_second_route():
    assert F.us_fcur_net_income(tsm_st(), "2026-09-30", D, 2527.57e9) == (pytest.approx(2527.57e9), "2026-09-30", "q4", None)
    # FUTU 2026-11-23: 분기 넷의 합 11.08B = info, 야후 TTM 줄만 3.80B (틀림) → 한 길이 맞으면 돼요 (stockanalysis 순이익 1.41B 달러 = 11.08B 홍콩 달러)
    futu = {"q": [["2025-12-31", 3.39e9], ["2026-03-31", 0.85e9], ["2026-06-30", 3.65e9], ["2026-09-30", 3.19e9]],
            "ttm": [["2026-09-30", 3.797e9]]}
    assert F.us_fcur_net_income(futu, "2026-09-30", D, 11.08e9)[3] is None
    assert F.us_fcur_net_income(futu, "2026-09-30", D, None)[3] == "niUnconfirmed"     # TTM 줄과도 info 와도 맞지 않으면 빈 칸
    # Unilever: 반기 보고 (분기 손익 없음) · 야후 TTM 줄 9.27B ↔ info 5.60B → 빈 칸
    ul = {"ttm": [["2026-06-30", 9.273e9]], "bsCols": ["2026-06-30"]}
    assert F.us_fcur_net_income(ul, "2026-06-30", D, 5.598e9) == (None, "2026-06-30", "ttm", "niUnconfirmed")
    assert F.us_fcur_net_income(ul, "2026-06-30", D, 9.2e9)[3] is None                  # BTI 처럼 맞으면 TTM 줄
    # Sony: 분기 넷의 합과 TTM 줄이 적자 (−134B) · info 는 +1,252B → 적자 쪽이 맞아요 (값과 함께 loss · PER 은 빈 칸)
    sony = {"q": [["2025-12-31", -1008.61e9], ["2026-03-31", 82.87e9], ["2026-06-30", 342.16e9], ["2026-09-30", 449.60e9]],
            "ttm": [["2026-09-30", -133.98e9]]}
    v, d, how, why = F.us_fcur_net_income(sony, "2026-09-30", D, 1252.2e9)
    assert why == "loss" and v < 0 and how == "q4"


def test_net_income_gaps_and_stale_quarters():
    enb = {"q": [["2025-06-30", 2.18e9], ["2025-09-30", 0.68e9], ["2025-12-31", 1.95e9], ["2026-03-31", 1.67e9], ["2026-09-30", 1.29e9]],
           "ttm": [["2026-09-30", 6.307e9]]}                               # 2026-06-30 분기가 비었어요 → 넷이 이어지지 않아 TTM 줄
    assert F.us_fcur_net_income(enb, "2026-09-30", D, 6.313e9)[1:] == ("2026-09-30", "ttm", None)
    san = {"q": [["2025-09-30", 3.5e9], ["2025-12-31", 3.76e9], ["2026-03-31", 5.46e9], ["2026-06-30", 3.52e9]], "qCols": ["2026-09-30"]}
    assert F.us_fcur_net_income(san, "2026-09-30", D, 13.2e9)[3] == "niStale"        # 넷의 끝이 최근 보고 분기(9-30)가 아님
    assert F.us_fcur_net_income({}, "2026-09-30", D, 1e9)[3] == "niMissing"


# ── 환율: 야후 미국 종가 시각 1시간 봉 × ECOS ─────────────────────
def hourly(vals, tz="Europe/London"):
    """{뉴욕 시각 'HH:MM' (D): 값} → 야후 1시간 봉 종가 (색인은 런던 시각 · 야후처럼)."""
    idx = [pd.Timestamp(f"{D} {h}", tz="America/New_York").tz_convert(tz) for h in vals]
    return pd.Series(list(vals.values()), index=pd.DatetimeIndex(idx))


def test_fx_bar_is_the_last_one_ended_by_the_us_close():
    s = hourly({"11:00": 32.90, "13:00": 32.94, "14:00": 32.98, "15:00": 32.988, "16:00": 32.958})
    r, at, why = F.us_fcur_fx_pick(s, D, NOW)
    assert (r, why) == (32.988, None) and at.startswith("2026-11-20T15:00:00")      # 15:00 봉 = 16:00 에 끝 · 16:00 봉은 장 뒤
    early = dt.datetime(2026, 11, 20, 20, 30, tzinfo=dt.timezone.utc)                # 15:30 뉴욕: 15:00 봉이 아직 끝나지 않았어요
    assert F.us_fcur_fx_pick(s, D, early)[0] == 32.98
    no15 = hourly({"14:00": 6.6765, "16:00": 6.6623})                               # 야후가 15:00 봉을 빠뜨린 통화 (CNY)
    assert F.us_fcur_fx_pick(no15, D, NOW)[0] == 6.6765
    naive = pd.Series([1.5], index=pd.DatetimeIndex([pd.Timestamp(f"{D} 20:00")]))   # 시각대가 없는 색인은 UTC (= 15:00 뉴욕)
    assert F.us_fcur_fx_pick(naive, D, NOW)[0] == 1.5
    assert F.us_fcur_fx_pick(hourly({"10:00": 1.0, "16:00": 2.0}), D, NOW)[2]       # 12:00 ~ 16:00 에 끝난 봉 없음 → 까닭
    assert F.us_fcur_fx_pick(None, D, NOW)[2]


def test_fx_must_agree_with_ecos_on_the_same_day_or_just_before():
    assert F.us_fcur_fx_check(32.988, [["2026-11-19", 32.943], ["2026-11-20", 33.056]], D) == (33.056, "2026-11-20", None)
    assert F.us_fcur_fx_check(32.988, [["2026-11-18", 32.93]], D)[2] is None          # 한국 휴일: 4일 안 앞 날
    assert F.us_fcur_fx_check(32.988, [["2026-11-14", 32.93]], D)[2]                  # 너무 앞
    e, ed, why = F.us_fcur_fx_check(434.68, [["2026-11-20", 449.62]], D)              # 야후 KZT 일봉 434.68 (3.3% 차이) 같은 값
    assert why and "ECOS" in why
    assert F.us_fcur_fx_check(1.0, [], D)[2]


def test_ecos_rows_invert_and_cross_through_won_without_leaking_the_key(monkeypatch):
    monkeypatch.setattr(F, "ECOS_KEY", "SECRETKEY123")
    seen = []

    def get(url):
        seen.append(url)
        item = url.rsplit("/", 1)[1]
        val = {"0000003": "1.0968", "0000001": "1330.8", "0000053": "199.65", "0000031": "33.056"}[item]
        return {"StatisticSearch": {"row": [{"TIME": "20261120", "DATA_VALUE": val}]}}
    assert F.us_fcur_ecos_rows("EUR", D, get=get) == [["2026-11-20", pytest.approx(1 / 1.0968)]]   # 달러/유로 → 1달러당 유로
    assert F.us_fcur_ecos_rows("TWD", D, get=get) == [["2026-11-20", 33.056]]
    assert F.us_fcur_ecos_rows("CNY", D, get=get) == [["2026-11-20", pytest.approx(1330.8 / 199.65)]]   # 원/달러 ÷ 원/위안

    def bad(url):
        return {"RESULT": {"CODE": "INFO-200", "MESSAGE": "없음"}}
    with pytest.raises(RuntimeError) as ex:
        F.us_fcur_ecos_rows("EUR", D, get=bad)
    assert "SECRETKEY123" not in str(ex.value)
    monkeypatch.setattr(F, "ECOS_KEY", "")
    with pytest.raises(RuntimeError):
        F.us_fcur_ecos_rows("EUR", D, get=get)


def test_fx_rates_join_yahoo_and_ecos(monkeypatch):
    raw = pd.concat({"TWD=X": pd.DataFrame({"Close": hourly({"14:00": 32.98, "15:00": 32.988})}),
                     "KZT=X": pd.DataFrame({"Close": hourly({"14:00": 434.68})})}, axis=1)
    yf = types.SimpleNamespace(download=lambda *a, **kw: raw)
    ecos = {"TWD": [["2026-11-20", 33.056]], "KZT": [["2026-11-20", 449.62]]}
    out = F.us_fcur_fx_rates(yf, ["TWD", "KZT", "CLP"], D, NOW, ecos=lambda c, d: ecos[c])
    assert out["TWD"]["r"] == 32.988 and out["TWD"]["e"] == 33.056 and out["TWD"]["why"] is None
    assert out["KZT"]["r"] is None and "ECOS" in out["KZT"]["why"]                   # 두 출처가 3% 넘게 달라요
    assert out["CLP"]["r"] is None and out["CLP"]["why"]                              # 야후 봉도 ECOS 표도 없음

    def boom(*a, **kw):
        raise ConnectionError("x")
    out2 = F.us_fcur_fx_rates(types.SimpleNamespace(download=boom), ["TWD"], D, NOW, ecos=lambda c, d: ecos[c])
    assert out2["TWD"]["r"] is None and "야후" in out2["TWD"]["why"]


# ── 배당수익률 ────────────────────────────────────────────────
def test_dividend_yield_from_payments_actually_received():
    info = tsm_info()
    dy, why = F.us_fcur_div(divs(TSM_DIVS), D, 318.71, info, 1.0, TODAY)
    assert why is None and dy == pytest.approx(round(100 * (0.835 + 0.956 + 0.955 + 1.107) / 318.71, 2))   # 마지막 네 분기 배당
    # 반기 (Novo: 3월 · 8월 · 간격 140 / 225일) · 연 (SAP)
    nvo = divs([("2025-03-31", 1.099), ("2025-08-18", 0.584), ("2026-03-30", 1.275), ("2026-08-17", 0.579)])
    assert F.us_fcur_div(nvo, D, 37.82, {"dividendYield": 4.75}, 1.0, TODAY) == (pytest.approx(4.9, abs=0.01), None)
    sap = divs([("2025-05-13", 2.63), ("2026-05-05", 2.929)])
    assert F.us_fcur_div(sap, D, 198.93, {"dividendYield": 1.47}, 1.0, TODAY) == (1.47, None)


def test_dividend_yield_blanks_when_the_record_is_not_clear():
    # 빠진 배당 (RY · TD: 2025-10 · 2026-01 이 야후 기록에 없어요) → 간격 273일
    ry = divs([("2025-04-24", 1.066), ("2025-07-24", 1.132), ("2026-04-23", 1.2), ("2026-07-27", 1.249), ("2026-10-26", 1.257)])
    assert F.us_fcur_div(ry, D, 183.45, {"dividendYield": 2.68}, 1.0, TODAY) == (None, "divIrregular")
    # Kaspi: 17개월 빈 뒤 석 달 사이 셋 → 주기를 믿을 수 없어요 (야후 수익률과는 맞아도: 같은 빠진 기록에서 나온 숫자)
    kspi = divs([("2024-11-20", 1.714), ("2026-04-16", 1.76), ("2026-06-12", 1.798), ("2026-09-10", 2.149)])
    assert F.us_fcur_div(kspi, D, 83.51, {"dividendYield": 6.87}, 1.0, TODAY) == (None, "divIrregular")
    # 다음 분기 배당이 기록에 없음 (마지막 배당이 120일 넘게 앞)
    late = divs([(d, v) for d, v in TSM_DIVS[:-1]])
    assert F.us_fcur_div(late, D, 318.71, tsm_info(), 1.0, TODAY)[1] == "divLate"
    # 야후 배당수익률과 10% 넘게 다름 (Ferrovial)
    assert F.us_fcur_div(divs(TSM_DIVS), D, 318.71, tsm_info(dividendYield=1.5), 1.0, TODAY)[1] == "divMismatch"
    assert F.us_fcur_div(divs(TSM_DIVS), D, 318.71, tsm_info(dividendYield=None), 1.0, TODAY)[1] == "divMismatch"
    # 기록 칸이 없음 · 지난 12개월 배당이 기록에 없는데 야후는 배당이 있다고 함 (Toyota · Sony)
    assert F.us_fcur_div(None, D, 318.71, tsm_info(), 1.0, TODAY) == (None, "divNoRecord")
    tm = divs([("2024-09-30", 2.601), ("2025-03-31", 3.457)])
    assert F.us_fcur_div(tm, D, 207.49, {"dividendYield": 3.02, "trailingAnnualDividendRate": 100.0}, 1.0, TODAY) == (None, "divUnclear")


def test_zero_yield_only_where_the_source_clearly_says_no_dividend():
    clear = {"dividendYield": 0.0, "trailingAnnualDividendRate": 0.0}
    assert F.us_fcur_div(divs([("2025-03-17", 0.3)]), D, 40.52, clear, 1.0, TODAY) == (0.0, None)     # Trip.com: 지난 배당이 1년 넘게 앞
    assert F.us_fcur_div(pd.Series(dtype=float), D, 40.52, clear, 1.0, TODAY) == (0.0, None)
    assert F.us_fcur_div(pd.Series(dtype=float), D, 40.52, {"dividendYield": 0.0}, 1.0, TODAY) == (None, "divUnclear")   # 칸이 빔
    assert F.us_fcur_div(None, D, 40.52, clear, 1.0, TODAY) == (0.0, None)              # 기록 칸이 없어도 #114 의 0% 는 그대로
    assert F.us_fcur_div(None, D, 40.52, {"dividendYield": 0.0}, 1.0, TODAY) == (None, "divNoRecord")


# ── 한 회사 ──────────────────────────────────────────────────
def test_row_computes_per_and_pbr_from_whole_company_totals():
    entry = {"px": 318.71, "info": tsm_info()}
    row = F.us_fcur_tot_row(tsm_rec(), entry, tsm_st(), FX_TWD, divs(TSM_DIVS), D, TODAY)
    mc = 5186472994 * 318.71
    assert row["mc"] == round(mc) and row["cur"] == "TWD" and row["px"] == 318.71 and row["fx"] == 32.988
    assert row["pbr"] == round(mc / (6997.90e9 / 32.988), 2) == 7.79                  # 2026-11-23 PR 표: 7.79
    assert row["per"] == round(mc / (2527.57e9 / 32.988), 1) == 21.6
    assert row["dy"] == 1.21 and row["why"] == {}
    assert row["eq"] == [6997900000000, "2026-09-30"] and row["ni"][1:] == ["2026-09-30", "q4"]
    assert row["y"][0] == 20.66 and row["y"][2] == 1.18
    json.dumps(row, allow_nan=False)


def test_row_rescales_market_cap_to_the_close_like_cap():
    entry = {"px": 300.0, "info": tsm_info(marketCap=5186472994 * 300.0)}            # 사흘 전 받은 상세 정보 (가격 300)
    row = F.us_fcur_tot_row(tsm_rec(), entry, tsm_st(), FX_TWD, None, D, TODAY)
    assert row["mc"] == pytest.approx(5186472994 * 318.71, rel=1e-9)


@pytest.mark.parametrize("change, field, why", [
    ({"rec": {"pxd": "2026-11-19"}}, "pbr", "px"),            # 그날 종가가 아님 (자기 날짜)
    ({"rec": {"pxc": True, "pxd": "2026-11-19"}}, "per", "px"),
    ({"entry": {"pxBad": True}}, "per", "px"),
    ({"info": {"marketCap": None}}, "pbr", "mc"),
    ({"fx": None}, "per", "fx"),
    ({"st": None}, "pbr", "stmt"),
    ({"info": {"netIncomeToCommon": 1e9}, "st_ttm": [["2026-09-30", 1e9]]}, "per", "niUnconfirmed"),
])
def test_row_blanks_with_a_reason(change, field, why):
    info = tsm_info(**change.get("info", {}))
    entry = {"px": 318.71, "info": info, **change.get("entry", {})}
    st = tsm_st()
    if "st_ttm" in change:
        st["ttm"] = change["st_ttm"]
    if "st" in change:
        st = change["st"]
    fx = change["fx"] if "fx" in change else FX_TWD
    row = F.us_fcur_tot_row(tsm_rec(**change.get("rec", {})), entry, st, fx, divs(TSM_DIVS), D, TODAY)
    assert field not in row and row["why"][field] == why
    if why == "px":
        assert set(row["why"]) == {"per", "pbr", "dy"}                                # 가격이 그날 것이 아니면 배당수익률도
    json.dumps(row, allow_nan=False)


def test_row_loss_and_range():
    st = tsm_st()
    st["q"] = [[d, -abs(v)] for d, v in st["q"]]
    st["ttm"] = [["2026-09-30", -2527.57e9]]
    row = F.us_fcur_tot_row(tsm_rec(), {"px": 318.71, "info": tsm_info(netIncomeToCommon=-2527.57e9)}, st, FX_TWD, None, D, TODAY)
    assert "per" not in row and row["why"]["per"] == "loss" and "pbr" in row          # 적자: PER 만 빈 칸 (다른 미국 종목처럼)
    tiny = tsm_st()
    tiny["eq"] = [["2026-09-30", 6997.90e15]]                                           # 0.005 아래 PBR
    row2 = F.us_fcur_tot_row(tsm_rec(), {"px": 318.71, "info": tsm_info()}, tiny, FX_TWD, None, D, TODAY)
    assert row2["why"]["pbr"] == "range"


# ── 단계 · 스위치 ─────────────────────────────────────────────
def step_inputs():
    out = [tsm_rec(), {"t": "AAPL", "cls": "us", "price": 250.0, "per": 30.0, "pbr": 40.0, "dy": 0.4},
           {"t": "TCOM", "cls": "us", "fcur": "CNY", "price": 40.52, "dy": 0.0},
           {"t": "XFUND", "cls": "us", "fcur": "EUR", "price": 10.0, "etf": True},
           {"t": "NOINFO", "cls": "us", "fcur": "EUR", "price": 10.0}]
    cache = {"TSM": {"px": 318.71, "info": tsm_info()}, "AAPL": {"px": 250.0, "info": {}},
             "TCOM": {"px": 40.52, "info": {"marketCap": 25.5e9, "dividendYield": 0.0, "trailingAnnualDividendRate": 0.0,
                                            "netIncomeToCommon": -1.0, "mostRecentQuarter": 1782777600}},
             "XFUND": {"px": 10.0, "info": {}}}
    data = pd.concat({"TSM": pd.DataFrame({"Close": [318.71], "Dividends": [0.0]}, index=[ts(D)])}, axis=1)
    div = divs(TSM_DIVS)
    data = pd.DataFrame({("TSM", "Close"): pd.Series(318.71, index=div.index), ("TSM", "Dividends"): div,
                         ("TCOM", "Close"): pd.Series(40.52, index=div.index)})
    stmts = {"TSM": tsm_st(), "TCOM": {"eq": [], "q": [], "ttm": [], "err": [["quarterly_balance_sheet", "HTTPError"]]}}
    return out, cache, data, stmts


def run_step(on, monkeypatch, out=None):
    o, cache, data, stmts = step_inputs()
    out = out or o
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    asked = {}

    def fx(curs, d, now):
        asked["curs"] = list(curs)
        return {"TWD": dict(FX_TWD)}
    rec = F.us_fcur_totals_safe(None, out, cache, data, D, TODAY, frozenset({"NOINFO"}), now=NOW,
                                stmts=lambda ts_: {t: stmts.get(t, {}) for t in ts_}, fx_rates=fx, on=on)
    return out, rec, lines, asked


def test_switch_off_records_but_leaves_every_published_number_blank(monkeypatch):
    out, rec, lines, asked = run_step(False, monkeypatch)
    by = {r["t"]: r for r in out}
    assert not any(k in by["TSM"] for k in ("per", "pbr", "dy", "fcurTot"))            # #114 그대로
    assert by["TCOM"]["dy"] == 0.0 and "fcurTot" not in by["TCOM"]
    assert by["AAPL"] == {"t": "AAPL", "cls": "us", "price": 250.0, "per": 30.0, "pbr": 40.0, "dy": 0.4}
    assert rec["on"] is False and sorted(rec["rows"]) == ["TCOM", "TSM"]                # ETF · 상세 정보 없는 종목은 빼요
    assert rec["rows"]["TSM"]["pbr"] == 7.79 and rec["rows"]["TSM"]["per"] == 21.6 and rec["rows"]["TSM"]["dy"] == 1.21
    assert rec["rows"]["TCOM"]["why"] == {"per": "stmt", "pbr": "stmt"} and rec["rows"]["TCOM"]["dy"] == 0.0
    assert asked["curs"] == ["TWD"]                                                     # 재무제표가 있는 회사의 통화만 물어요
    assert rec["n"] == {"per": 1, "pbr": 1, "dy": 1, "dy0": 1, "blank": {"stmt": 2}}
    assert rec["fx"]["TWD"]["r"] == 32.988 and "why" not in rec["fx"]["TWD"]
    json.dumps(rec, allow_nan=False)
    # 관문의 #114 줄은 그대로 통과 (종목 칸이 비었으니까요)
    rep = V.Report()
    V.check_us_fcur(rep, out)
    assert rep.rows[0][3] == "PASS"
    head = next(x for x in lines if x.startswith("· 달러 아닌 재무제표"))
    assert head.startswith("· 달러 아닌 재무제표 2곳: PER 1 / PBR 1 / 배당 1 되살림 (배당 0% 그대로 1), 빈 칸 2 (재무제표를 받지 못함 2)")
    assert "스위치 꺼짐" in head and "#114 그대로" in head
    assert any(x.strip().startswith("TSM (TWD): 시가총액 $1,652.98B") and "PBR 7.79" in x for x in lines), lines
    assert any(x.startswith("  !! 달러 아닌 재무제표 회사의 재무제표 표를 다 받지 못한 곳 1곳: TCOM") for x in lines), lines


def test_switch_on_puts_checked_numbers_on_the_stock_and_marks_them(monkeypatch):
    out, rec, _lines, _a = run_step(True, monkeypatch)
    by = {r["t"]: r for r in out}
    assert (by["TSM"]["per"], by["TSM"]["pbr"], by["TSM"]["dy"]) == (21.6, 7.79, 1.21) and by["TSM"]["fcurTot"] == ["per", "pbr", "dy"]
    assert "fcurTot" not in by["TCOM"] and by["TCOM"]["dy"] == 0.0                     # 0% 는 #114 가 이미 실어요
    assert rec["on"] is True
    rep = V.Report()
    V.check_us_fcur(rep, out)
    assert rep.rows[0][3] == "FAIL"        # 스위치만 켜면 #114 줄이 발행을 막아요 (켜려면 Jack 의 예 · 그 줄과 앱을 함께 바꿔요 — RUNBOOK)


def test_shipped_switch_is_off_and_shared():
    assert V.US_FCUR_TOT_ON is False and F.US_FCUR_TOT_ON is V.US_FCUR_TOT_ON
    assert F.US_FCUR_TOT_FIELDS == ("per", "pbr", "dy")
    assert "mostRecentQuarter" in F.US_INFO_KEYS and F.US_INFO_SCHEMA == 3            # 칸만 더하고 모양 표시는 그대로


def test_a_crash_leaves_the_stocks_as_they_were(monkeypatch):
    out, cache, data, _st = step_inputs()
    lines = []
    monkeypatch.setattr(F, "log", lines.append)

    def boom(ts_):
        raise RuntimeError("yahoo down")
    rec = F.us_fcur_totals_safe(None, out, cache, data, D, TODAY, frozenset(), now=NOW, stmts=boom, on=True)
    assert rec["err"].startswith("RuntimeError") and rec["on"] is True and "rows" not in rec
    assert not any(k in out[0] for k in ("per", "pbr", "dy", "fcurTot"))
    assert any("회사 합계 계산이 멈췄어요" in x for x in lines)


def test_one_bad_company_does_not_stop_the_others(monkeypatch):
    out, cache, data, stmts = step_inputs()
    cache["TCOM"]["info"]["marketCap"] = object()       # 숫자가 아닌 값
    monkeypatch.setattr(F, "us_fcur_tot_row", lambda r, *a: (_ for _ in ()).throw(ValueError("x")) if r["t"] == "TCOM"
                        else ORIG_ROW(r, *a))
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    rec = F.us_fcur_totals_safe(None, out, cache, data, D, TODAY, frozenset(), now=NOW,
                                stmts=lambda ts_: {t: stmts.get(t, {}) for t in ts_}, fx_rates=lambda c, d, n: {"TWD": dict(FX_TWD)},
                                on=False)
    assert rec["rows"]["TCOM"]["why"] == {"per": "err", "pbr": "err", "dy": "err"} and rec["rows"]["TSM"]["pbr"] == 7.79


ORIG_ROW = F.us_fcur_tot_row


def test_statement_fetch_reads_three_tables_and_retries_once():
    calls = []

    class Tk:
        def __init__(self, t):
            self.t = t
            calls.append(t)

        @property
        def quarterly_balance_sheet(self):
            if self.t == "BAD" and calls.count("BAD") == 1:
                raise ConnectionError("429")
            return stmt({"Common Stock Equity": {"2026-09-30": 5.0}})

        quarterly_income_stmt = property(lambda self: stmt({"Net Income Common Stockholders": {"2026-09-30": 1.0}}))
        ttm_income_stmt = property(lambda self: stmt({"Net Income Common Stockholders": {"2026-09-30": 4.0}}))
    got = F.us_fcur_stmts_fetch(types.SimpleNamespace(Ticker=Tk), ["TSM", "BAD"], workers=1)
    assert got["TSM"]["eq"] == [["2026-09-30", 5.0]] and got["TSM"]["ttm"] == [["2026-09-30", 4.0]] and "err" not in got["TSM"]
    assert got["BAD"]["eq"] == [["2026-09-30", 5.0]] and calls.count("BAD") == 2      # 한 번 더 받아요

    class Old:                                          # 재무제표 칸이 없는 야후 (시험의 가짜 · 아주 옛 yfinance)
        def __init__(self, t):
            pass
    got2 = F.us_fcur_stmts_fetch(types.SimpleNamespace(Ticker=Old), ["X"])
    assert got2["X"]["eq"] == [] and got2["X"]["err"]


def test_dropped_rows_leave_the_record_too():
    umeta = {"usFcurTot": {"v": 1, "on": False, "rows": {"TSM": {"pbr": 7.79, "why": {}}, "BAD": {"why": {"per": "loss"}}}}}
    F.us_meta_drop(umeta, [{"t": "TSM"}, {"t": "BAD"}], {"BAD"})
    assert list(umeta["usFcurTot"]["rows"]) == ["TSM"] and umeta["usFcurTot"]["n"]["pbr"] == 1


# ── fetch_us 에서 ───────────────────────────────────────────
def test_fetch_us_writes_the_record_and_keeps_114_blanks(tmp_path, monkeypatch):
    today = dt.date(2026, 11, 12)
    syms = ["AAPL", "TSM"]
    days = pd.bdate_range(today - dt.timedelta(days=500), today)

    def series(seed):
        rnd = np.random.default_rng(seed)
        return pd.Series(100 * np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)

    def download(tickers, **kw):
        if kw.get("interval") == "1h":
            d0 = kw["end"] - dt.timedelta(days=2)
            idx = pd.DatetimeIndex([pd.Timestamp(f"{d0} 15:00", tz="America/New_York").tz_convert("Europe/London")])
            return pd.concat({t: pd.DataFrame({"Close": [32.99]}, index=idx) for t in tickers}, axis=1)
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series(len(tickers))})
        return pd.DataFrame({(t, "Close"): series(i + 3) for i, t in enumerate(tickers)})

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            base = {"shortName": self.t, "sector": "Technology", "industry": "Semiconductors", "marketCap": 1.6e12, "currency": "USD",
                    "trailingPE": 25.0, "priceToBook": 70.0, "dividendYield": 1.2, "averageVolume": 1e7, "returnOnEquity": 0.4}
            if self.t == "TSM":
                base.update(financialCurrency="TWD", netIncomeToCommon=2527.57e9, mostRecentQuarter=1790726400)
            else:
                base.update(financialCurrency="USD")
            return base

        quarterly_balance_sheet = property(lambda self: stmt({"Common Stock Equity": {"2026-09-30": 6997.9e9}}))
        quarterly_income_stmt = property(lambda self: stmt({"Net Income Common Stockholders": {
            "2025-12-31": 485.47e9, "2026-03-31": 572.48e9, "2026-06-30": 706.56e9, "2026-09-30": 763.06e9}}))
        ttm_income_stmt = property(lambda self: stmt({"Net Income Common Stockholders": {"2026-09-30": 2527.57e9}}))
    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(download=download, Ticker=Ticker))
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today - dt.timedelta(days=1))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    monkeypatch.setattr(F, "us_fcur_ecos_rows", lambda c, d: [[d.isoformat(), 33.0]])
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    us, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    tsm = {r["t"]: r for r in us}["TSM"]
    assert tsm["fcur"] == "TWD" and not any(k in tsm for k in ("per", "pbr", "dy", "fcurTot"))
    rec = meta["usFcurTot"]
    assert rec["on"] is False and set(rec["rows"]) == {"TSM"} and rec["fx"]["TWD"]["r"] == 32.99
    row = rec["rows"]["TSM"]
    assert row["eq"][1] == "2026-09-30" and row["ni"][2] == "q4" and row["pbr"] == round(row["mc"] / (6997.9e9 / 32.99), 2)
    assert row["why"]["dy"] == "divNoRecord"                                           # 가짜 다운로드에 배당 칸이 없어요
    assert any(x.startswith("· 달러 아닌 재무제표 1곳: PER 1 / PBR 1 / 배당 0 되살림") for x in lines), lines
    json.dumps(rec, allow_nan=False)


# ── 관문 (경고만) ────────────────────────────────────────────
def gate(data, pdata=None, mode="publish"):
    rep = V.Report()
    V.check_us_fcur_tot(rep, data, V.us_stocks(data), pdata, mode)
    assert len(rep.rows) == 1 and rep.rows[0][0] == ROW
    return rep


def gdata(rows=None, **kw):
    rec = {"v": 1, "on": False, "fx": {"TWD": {"r": 32.988}},
           "rows": rows if rows is not None else {"TSM": {"cur": "TWD", "px": 318.71, "per": 21.6, "pbr": 7.79, "dy": 1.21,
                                                          "y": [20.66, 61.2, 1.18], "why": {}}},
           "n": {"per": 1, "pbr": 1, "dy": 1, "dy0": 0, "blank": {}}}
    rec.update(kw)
    return {"stocks": [{"t": "TSM", "cls": "us", "fcur": "TWD", "price": 318.71}, {"t": "AAPL", "cls": "us", "price": 250.0}],
            "usFcurTot": rec}


def test_gate_passes_a_clean_record():
    r = gate(gdata()).rows[0]                    # 야후 PBR 61.2 (#114 가 비운 그 숫자) 는 맞춰 보지 않아요 — 늘 어긋나니까요
    assert r[3] == "PASS" and r[1].startswith("1곳 · PER 1 · PBR 1 · 배당 1 계산됨 · 빈 칸 0 · 스위치 꺼짐")
    same = {"usFcurTot": {"rows": {"TSM": {"px": 300.0, "pbr": 7.33, "per": 20.3}}}}   # 지난 발행본: 가격만 바뀜
    assert gate(gdata(), same).rows[0][3] == "PASS"


@pytest.mark.parametrize("data, pdata, mode, want", [
    (gdata(rows={"TSM": {"cur": "TWD", "px": 318.71, "per": 21.6, "pbr": 7.79, "y": [40.0, 7.8, None], "why": {}}}), None, "publish",
     "야후 자기 숫자와"),                                                       # PER 21.6 ↔ 야후 40 (1.85배)
    (gdata(), {"usFcurTot": {"rows": {"TSM": {"px": 300.0, "pbr": 3.0, "per": 21.0}}}}, "publish", "지난 발행본과"),   # PBR ÷ 종가 2.4배 바뀜
    (gdata(rows={"AAPL": {"cur": "EUR", "px": 250.0, "why": {}}}), None, "publish", "fcur 회사가 아님"),
    (gdata(rows={"TSM": {"cur": "TWD", "px": 300.0, "why": {}}}), None, "publish", "종가 300.0 ≠ 종목 318.71"),
    (gdata(rows={"TSM": {"cur": "TWD", "px": 318.71, "per": float("nan"), "why": {}}}), None, "publish", "모양이 틀린 줄"),
    (gdata(on=True), None, "publish", "스위치 기록 True"),
    (gdata(rows={}), None, "publish", "줄이 없는 fcur 회사 1"),
    (gdata(err="RuntimeError: x"), None, "publish", "계산이 멈춘 날"),
    ({"stocks": [{"t": "TSM", "cls": "us", "fcur": "TWD", "price": 318.71}]}, None, "publish", "기록 없음"),
    ({"stocks": [], "usFcurTot": ["broken"]}, None, "live", "기록 모양이 틀림"),
])
def test_gate_only_warns(data, pdata, mode, want):
    r = gate(data, pdata, mode).rows[0]
    assert r[3] == "WARN" and want in r[1], r


def test_gate_reads_old_files_quietly_on_site_checks():
    r = gate({"stocks": [{"t": "TSM", "cls": "us", "fcur": "TWD", "price": 318.71}]}, None, "live").rows[0]
    assert r[3] == "PASS" and "이 기록 전의 파일" in r[1]


def test_gate_row_runs_inside_run_checks():
    assert "check_us_fcur_tot(rep, data, us, pdata, mode)" in inspect.getsource(V.run_checks)
