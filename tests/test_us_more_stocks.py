# -*- coding: utf-8 -*-
"""손으로 더한 미국 종목 (Jack, 2026-11-13 "Missing US stocks") — fetch_data.py EXTRA_US_ADDED · US_FOREIGN · us_foreign_cuts ·
us_div_12m · us_foreign_check · us_extra_missing · add_more_seeds · fetch_us 와 validate_data.py check_us_extra · check_us_foreign.
(네트워크 없음 · 2026-11-14 야후 값을 고정값으로 써요)

- 28곳을 EXTRA_US 에 더해요: Jack 이 이름으로 정한 BTI · ADC · NNN, 널리 가진 뉴욕 배당주 9곳, 뉴욕 상장 외국 회사 16곳. 모두 회사 주식이에요.
- 외국 회사(US_FOREIGN) 중 재무제표 통화가 달러인 곳은 야후의 PER · PBR · 배당수익률이 회사 합계 · 실제 배당과 맞을 때만 나가요 (ADR 하나가
  원주 몇 주인지 섞인 값: 2026-11-14 BP PBR 7.62 · HSBC 7.07 · 디아지오 93.64). 달러가 아닌 회사는 #114 가 이미 비워요 (fcur).
- 새 종목의 2016년부터 분할은 커밋한 두 번째 시드(data/us_splits_seed_more.csv)에 있어 첫 실행이 이력을 따로 읽지 않아요.
- 관문: 더한 종목은 목록에 있거나 빠진 이유가 있어야 하고 (이유 없으면 발행 실패), 외국 회사의 맞지 않는 칸은 빈 칸이어야 해요.
"""
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
from fixture_data import good_pair, clone  # noqa: E402
import test_v196a_fxhist_splits as T196  # noqa: E402  (분할 관문 시험의 데이터 · 관문 실행 도우미를 그대로 써요)

EXTRA = "손으로 더한 미국 종목 (EXTRA_US): 목록에 있거나 빠진 이유"
FOREIGN = "미국 상장 외국 회사: 회사 합계와 맞춘 PER·PBR·배당수익률만"
ADDED = ["BTI", "ADC", "NNN", "MAIN", "WPC", "STAG", "EPR", "OHI", "ENB", "BCE", "TD", "RY", "SHEL", "BP", "UL", "TM", "SONY",
         "AZN", "HSBC", "SAP", "NVS", "RIO", "BHP", "TTE", "DEO", "BUD", "SAN", "GSK"]

# 2026-11-14 야후 info (필요한 칸만 · 값 그대로)
SHEL = {"shortName": "Shell PLC", "longName": "Shell plc", "quoteType": "EQUITY", "financialCurrency": "USD", "currency": "USD", "sector": "Energy",
        "industry": "Oil & Gas Integrated", "marketCap": 280164270080, "netIncomeToCommon": 32707000320, "trailingPE": 8.600695,
        "priceToBook": 1.4303864, "returnOnEquity": 0.17432, "dividendYield": 3.15, "averageVolume": 6141538,
        "longBusinessSummary": "Shell plc operates as an energy and petrochemical company."}
BP = {"shortName": "BP p.l.c.", "longName": "BP p.l.c.", "quoteType": "EQUITY", "financialCurrency": "USD", "currency": "USD", "sector": "Energy",
      "industry": "Oil & Gas Integrated", "marketCap": 117707300864, "netIncomeToCommon": 8961000448, "trailingPE": 22.292685,
      "priceToBook": 7.6223836, "returnOnEquity": 0.13424, "dividendYield": 4.55, "averageVolume": 9148653,
      "longBusinessSummary": "BP p.l.c. provides carbon products and services."}
HSBC = {"shortName": "HSBC Holdings, plc.", "financialCurrency": "USD", "marketCap": 306371100672, "netIncomeToCommon": 26435000320,
        "trailingPE": 11.715033, "priceToBook": 7.0720067, "returnOnEquity": 0.14219, "dividendYield": 2.23}
BUD = {"shortName": "Anheuser-Busch Inbev SA Sponsor", "financialCurrency": "USD", "marketCap": 167001817088,
       "netIncomeToCommon": 9868999680, "trailingPE": 17.237804, "priceToBook": 10.708592, "returnOnEquity": None, "dividendYield": 1.59}
BTI = {"shortName": "British American Tobacco  Indus", "longName": "British American Tobacco p.l.c.",
       "quoteType": "EQUITY", "financialCurrency": "GBP", "currency": "USD",
       "sector": "Consumer Defensive", "industry": "Tobacco", "marketCap": 132940275712, "netIncomeToCommon": 6349000192,
       "trailingPE": 15.86923, "priceToBook": 10.759727, "returnOnEquity": 0.13424, "dividendYield": 5.4, "dividendRate": 3.34,
       "trailingAnnualDividendRate": 2.45, "averageVolume": 4989773, "longBusinessSummary": "British American Tobacco p.l.c. provides tobacco."}


def rec_of(t, price, info):
    """apply_us_info 를 지난 종목 (k = 1 · 받은 날 가격 그대로)."""
    r = {"t": t, "nk": t, "ne": t, "cls": "us", "ccy": "USD", "fxu": True, "price": price, "etf": False}
    assert F.apply_us_info(r, dict(info), price, 1333.8, today=dt.date(2026, 11, 14)) is True
    return r


# ── 목록 ──────────────────────────────────────────────────
def test_the_added_list_and_its_decisions():
    assert F.EXTRA_US_ADDED == ADDED and len(F.EXTRA_US) == len(set(F.EXTRA_US)) == 67
    assert {"BTI", "ADC", "NNN"} <= set(F.EXTRA_US)                                    # Jack 이 이름으로 정한 셋
    assert set(ADDED) <= F.US_NOT_ETF and not set(ADDED) & F.US_ETFS                   # 모두 회사 주식
    assert F.US_ETFS | F.US_NOT_ETF == set(F.EXTRA_US)
    assert F.US_FOREIGN <= set(ADDED) and len(F.US_FOREIGN) == 21          # 이번에 더한 외국 회사만 (예전 TSM · ASML · BABA · NVO · SHOP 은 그대로)
    assert not {"TSM", "ASML", "BABA", "NVO", "SHOP"} & F.US_FOREIGN
    assert {"SHEL", "BP", "UL", "TM", "SONY", "BTI"} <= F.US_FOREIGN and not {"ADC", "NNN", "MAIN", "WPC", "O"} & F.US_FOREIGN
    assert not {"BNS", "EPD", "ET"} & set(F.EXTRA_US)                                  # 뺀 이유: PR 본문 (BNS 야후 이름 'Pfd 3' · 공개 합자회사)
    # 관문은 같은 목록을 따로 적어요 (같은 실수를 같이 하지 않게)
    assert V.US_ADDED_SET == set(ADDED) and V.US_EXTRA_SET == set(F.EXTRA_US) and V.US_FOREIGN_SET == set(F.US_FOREIGN)
    assert set(ADDED) <= V.US_COMPANY_SET and not set(ADDED) & V.US_ETF_SET
    assert "netIncomeToCommon" in F.US_INFO_KEYS and F.US_INFO_SCHEMA == 3                # 칸만 더하고 모양 표시는 그대로 (770곳을 다시 받지 않게)
    assert F.US_ADDED_LONG_NAME == set(ADDED)
    assert F.US_FOREIGN_BAND == {"per": 1.10, "pbr": 1.35, "dy": 1.10} and F.US_FOREIGN_BAND["pbr"] < 2 ** 0.5   # 2배 ADR 실수가 숨지 못해요


def test_no_added_ticker_looks_like_a_preferred_or_depositary_share():
    """BNS 는 야후 짧은 이름이 'Bank Nova Scotia Halifax Pfd 3' 이라 우선주 규칙에 걸려 넣지 않았어요. 더한 28곳의 2026-11-14 야후 이름은 걸리지 않아요."""
    names = {"BTI": "British American Tobacco  Indus", "SAN": "Banco Santander, S.A. Sponsored", "BUD": "Anheuser-Busch Inbev SA Sponsor",
             "NGG": "National Grid Transco, PLC Nati", "SAP": "SAP  SE", "HSBC": "HSBC Holdings, plc.", "TD": "Toronto Dominion Bank (The)"}
    for t in ADDED:
        assert F.us_preferred_reason(t, (names.get(t, t),), "EQUITY") is None, t
    assert F.us_preferred_reason("BNS", ("Bank Nova Scotia Halifax Pfd 3",), "EQUITY") == "이름 'Pfd'"


# ── 분할 시드 ─────────────────────────────────────────────
def test_the_added_seed_covers_every_added_stock():
    rows, codes, end = F.load_split_seed(*F.SPLIT_SEED_MORE[0])
    assert codes == set(ADDED) and end == dt.date(2026, 11, 13)
    assert rows == {("AZN", "2026-02-02"): 0.5, ("BTI", "2017-02-14"): 2.0, ("GSK", "2022-07-19"): 0.8, ("SONY", "2024-10-09"): 5.0}
    assert all(F.split_is_clean(r) and V.simple_ratio(r) for r in rows.values())
    assert not set(F.SPLIT_OVERRIDES) & set(rows)
    for spin in (("BHP", "2022-06-02"), ("GSK", "2022-07-22"), ("NVS", "2019-04-09"), ("WPC", "2023-11-02"), ("UL", "2025-12-09")):
        assert spin not in rows                                                         # 야후 분사 조정 (깨끗하지 않은 배율)
    # 유니레버 2025-12-09 는 진짜 8:9 주식 병합 (Magnum 분리와 같은 날 · 야후는 둘을 합쳐 ×0.888 — 깨끗하지 않아 다운로드에서 빠져요): 고정 표에
    r, note = F.SPLIT_OVERRIDES[("UL", "2025-12-09")]
    assert r == 8 / 9 and F.split_is_clean(r) and V.simple_ratio(r) and "RNS" in note and "8937" in note
    assert not F.split_is_clean(0.888)
    first = F.load_split_seed()
    both = F.add_more_seeds(first)
    assert len(both[0]) == len(first[0]) + 4 and both[1] == first[1] | set(ADDED) and both[2] == min(first[2], end)
    assert not set(ADDED) & first[1]                                                    # 처음 시드는 그대로 (#117 리뷰를 거친 파일)


def test_the_first_run_reads_no_split_history_for_the_added_stocks(monkeypatch):
    """새 28곳은 시드가 덮어서 2016년부터의 이력을 따로 읽지 않아요 (한 실행에 20개 상한 · gap 경고 없음)."""
    monkeypatch.setattr(F, "log", lambda *a: None)
    seed = F.add_more_seeds(F.load_split_seed())
    codes = sorted(seed[1])

    def history(need, today):
        raise AssertionError(f"이력을 읽으면 안 돼요: {need}")
    f = F.splits_fields(None, codes, [], [], dt.date(2023, 10, 6), dt.date(2026, 11, 14), seed=None, history=history)
    assert f["splitsInfo"]["gap"] == []
    have = {(t, d): r for t, d, r in f["splits"]}
    assert have[("SONY", "2024-10-09")] == 5.0 and have[("AZN", "2026-02-02")] == 0.5 and have[("BTI", "2017-02-14")] == 2.0


def test_unilever_consolidation_is_published_without_a_gate_warning(monkeypatch):
    """UL 이 목록에 든 날: 고정 표의 8:9 줄이 splits 에 들어가고 (야후 ×0.888 은 깨끗하지 않아 오늘 다운로드에서 빠져요), 관문 두 줄은 UL 때문에
    경고하지 않아요 (고정 표와 같은 배율의 새 줄은 검토한 줄이에요)."""
    T196.Log(monkeypatch)
    cur, prev, final = T196.pair()
    cur["data"]["stocks"].append(dict(next(s for s in cur["data"]["stocks"] if s["t"] == "MSFT"), t="UL"))
    us = [s["t"] for s in cur["data"]["stocks"] if s.get("cls") == "us" and not s.get("fund")]
    seed = ({(t, d): r for t, d, r in V.MUST_SPLITS if (t, d) not in F.SPLIT_OVERRIDES}, set(us), dt.date(2026, 10, 30))
    recent = sorted(x for x in prev["data"]["splits"] if x[1] >= T196.START.isoformat() and (x[0], x[1]) not in F.SPLIT_OVERRIDES)
    f = F.splits_fields(prev["data"], us, recent, [], T196.START, T196.TODAY, seed=seed)     # 야후 오늘 다운로드 = 어제 줄 그대로 (UL ×0.888 은 빠짐)
    assert ["UL", "2025-12-09", 8 / 9] in f["splits"]
    assert ["UL", "2025-12-09", 8 / 9, F.SPLIT_OVERRIDES[("UL", "2025-12-09")][1]] in f["splitsInfo"]["fixed"]
    cur["data"].update(f)
    rep = T196.check(cur, prev, final)
    spl, spc = T196.row(rep, T196.SPL), T196.row(rep, T196.SPC)
    assert spl[3] == "PASS" and "최근 QQQ 2026-10-15 ×2 · UL 2025-12-09 ×0.888889" in spl[1] and not rep.failed, rep.table()
    assert spc[3] == "PASS" and spc[1] == "그대로 (어제 13건 → 오늘 14건 · 새 1건)", spc        # 고정 표의 줄이라 '새 줄 정수 아닌 배율' 경고 없음
    assert not any("UL" in x for _t, items in rep.details for x in items if "분할" in _t)


def test_the_daily_log_says_when_an_unclean_yahoo_ratio_has_an_override(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    F.log_us_splits([], {"noCol": [], "spin": ["UL 2025-12-09 ×0.888", "WPC 2023-11-02 ×1.021"], "future": [], "bad": []}, 2,
                    dt.date(2026, 11, 14))
    assert lines[-1].endswith("UL 2025-12-09 ×0.888 (고정 표: 1:1.125 병합), WPC 2023-11-02 ×1.021")


def test_a_broken_added_seed_is_left_out_loudly(tmp_path, monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    first = ({("NVDA", "2024-06-10"): 10.0}, {"NVDA"}, dt.date(2026, 11, 12))
    p, c = tmp_path / "s.csv", tmp_path / "c.txt"
    p.write_text("code,date,ratio,yahoo\nNVDA,2024-06-10,10.0,10:1\n", encoding="utf-8")       # 처음 시드와 같은 줄
    c.write_text("# end=2026-11-13\nNVDA\n", encoding="utf-8")
    assert F.add_more_seeds(first, pairs=((str(p), str(c)),)) == first
    assert lines and lines[-1].startswith("  !! 더한 종목의 분할 시드(s.csv)를 읽지 못했어요")
    assert F.add_more_seeds(first, pairs=((str(tmp_path / "없음.csv"), str(c)),)) == first
    p.write_text("code,date,ratio,yahoo\nSONY,2024-10-09,5.0,5:1\n", encoding="utf-8")
    c.write_text("# end=2026-11-13\nSONY\nBTI\n", encoding="utf-8")
    rows, codes, end = F.add_more_seeds(({}, set(), None), pairs=((str(p), str(c)),))   # 처음 시드를 못 읽은 날에도 더한 시드는 써요
    assert rows == {("SONY", "2024-10-09"): 5.0} and codes == {"SONY", "BTI"} and end == dt.date(2026, 11, 13)


# ── 외국 회사의 주당 숫자 (ADR) ───────────────────────────
def test_a_dollar_reporting_adr_with_consistent_numbers_keeps_them():
    r = rec_of("SHEL", 99.08, SHEL)
    assert (r["per"], r["pbr"], r["dy"]) == (8.6, 1.43, 3.15) and "fcur" not in r
    div12 = 0.744 + 0.7812 * 3                                     # 2026-02-20 · 05-22 · 08-14 · 11-13 (ADR 하나 = 원주 2주 · 달러)
    assert F.us_foreign_cuts(r, SHEL, div12) == {}


def test_an_adr_whose_book_value_is_per_ordinary_share_loses_pbr_and_an_odd_per():
    """BP: ADR 하나 = 원주 6주. 야후 PBR 7.62 는 ADR 가격 ÷ 원주 1주의 장부가예요 (회사 합계로는 약 1.76). PER 22.29 도 시가총액 ÷ 순이익
    13.14 와 1.7배 달라 비워요. 배당은 실제로 준 배당과 맞아요 (4.55% ↔ 4.46%)."""
    r = rec_of("BP", 45.70, BP)
    cuts = F.us_foreign_cuts(r, BP, 0.499 + 0.499 + 0.52 + 0.52)
    assert set(cuts) == {"per", "pbr"}
    assert "7.62" in cuts["pbr"] and "1.76" in cuts["pbr"] and "4.32배" in cuts["pbr"]
    assert "22.29" in cuts["per"] and "13.14" in cuts["per"]


def test_hsbc_pbr_and_a_forward_yield_that_drops_the_big_fourth_dividend_are_cut():
    r = {"t": "HSBC", "price": 89.62, "per": 11.7, "pbr": 7.07, "dy": 2.23}
    cuts = F.us_foreign_cuts(r, HSBC, 0.5 + 2.25 + 0.5 + 0.5)       # 지난 1년 실제 배당 3.75달러 = 4.18% (야후 '앞으로 1년' 2.00달러 = 2.23%)
    assert set(cuts) == {"pbr", "dy"} and "4.18%" in cuts["dy"] and "1.88배" in cuts["dy"]


def test_nothing_to_compare_means_blank():
    r = {"t": "BUD", "price": 84.81, "per": 17.2, "pbr": 10.71, "dy": 1.59}
    cuts = F.us_foreign_cuts(r, BUD, 1.174)
    assert set(cuts) == {"pbr", "dy"}                               # ROE 없음 → PBR 을 맞춰 볼 수 없어요 · 배당 1.15배 (1.10배 넘음)
    no_ni = dict(SHEL, netIncomeToCommon=None)
    assert set(F.us_foreign_cuts({"price": 99.08, "per": 8.6, "pbr": 1.43}, no_ni, 3.0)) == {"per", "pbr"}
    loss = dict(SHEL, netIncomeToCommon=-1e9)
    assert set(F.us_foreign_cuts({"price": 99.08, "per": 8.6, "pbr": 1.43}, loss, 3.0)) == {"per", "pbr"}
    assert set(F.us_foreign_cuts({"price": 99.08, "dy": 3.15}, SHEL, None)) == {"dy"}        # 배당 기록 칸을 읽지 못함
    assert F.us_foreign_cuts({"price": 50.0, "dy": 0.0}, SHEL, 0.0) == {}                    # 배당 없음이 분명함
    assert set(F.us_foreign_cuts({"price": 50.0, "dy": 0.0}, SHEL, 1.0)) == {"dy"}           # 0% 인데 배당 기록이 있어요
    assert set(F.us_foreign_cuts({"price": 50.0, "dy": 3.0}, SHEL, 0.0)) == {"dy"}           # 수익률은 있는데 배당 기록이 없어요
    assert F.us_foreign_cuts({"price": 50.0}, SHEL, None) == {}                               # 비울 칸이 없어요


def test_unconfirmed_statement_currency_blanks_all_three():
    """리뷰 S1: 야후 첫 응답에 financialCurrency 가 없으면 fcur 가 붙지 않아 이 검사가 돌아요. 통화가 섞인 숫자끼리는 맞을 수 있어서 (UL · TD …)
    달러로 확인되지 않은 회사의 PER · PBR · 배당수익률은 모두 비워요."""
    for fc in (None, "GBP", "XXX", float("nan")):
        info = dict(SHEL)
        if fc is None:
            info.pop("financialCurrency")
        else:
            info["financialCurrency"] = fc
        cuts = F.us_foreign_cuts({"price": 99.08, "per": 8.6, "pbr": 1.43, "dy": 3.15}, info, 3.088)
        assert set(cuts) == {"per", "pbr", "dy"} and all(w.startswith("재무제표 통화를 모름") for w in cuts.values()), fc
    assert F.us_foreign_cuts({"price": 99.08, "per": 8.6, "pbr": 1.43, "dy": 3.15}, dict(SHEL, financialCurrency="usd"), 3.088) == {}
    assert F.us_foreign_cuts({"price": 99.08, "pbr": 1.43}, {k: v for k, v in SHEL.items() if k != "financialCurrency"}, None) == \
        {"pbr": "재무제표 통화를 모름 (야후 financialCurrency None — 달러로 확인되지 않음)"}


def test_unknown_currency_company_through_the_check_is_blanked_and_logged(monkeypatch):
    """UL 의 첫 응답에 통화가 없던 날 (2026-11-14 야후 값: 유로 재무제표 · 달러 시가총액이라 PBR 7.84 가 '맞음'으로 보여요)."""
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    ul = {"shortName": "Unilever PLC", "longName": "Unilever PLC", "marketCap": 142574436352, "netIncomeToCommon": 5598000128,
          "trailingPE": 13.375758, "priceToBook": 7.836206, "returnOnEquity": 0.31869, "dividendYield": 3.15}
    out = [rec_of("UL", 66.21, ul)]
    assert "fcur" not in out[0] and out[0]["pbr"] == 7.84
    got = F.us_foreign_check(out, {"UL": {"info": ul}}, None, dt.date(2026, 11, 13))
    assert got["checked"] == ["UL"] and sorted(x[1] for x in got["cut"]) == ["dy", "pbr", "per"]
    assert not any(k in out[0] for k in ("per", "pbr", "dy"))
    assert out[0]["fgnCut"] == {"dy": "currency", "pbr": "currency", "per": "currency"}   # 앱: Jack 의 이유 줄 (통화 줄은 통화 이름이 있어야 해요)
    assert any(x.startswith("  !! 미국 상장 외국 회사 중 재무제표 통화가 달러로 확인되지 않아") and x.endswith("1곳: UL") for x in lines), lines


def test_the_bands_catch_moderate_misses():
    """리뷰 S2: 허용 폭을 넓히면 이 시험이 잡아요 — PBR 2배 (ADR 하나 = 원주 2주를 1주로 셈) · PER 1.2배."""
    r = {"price": 99.08, "pbr": 2.86}
    assert set(F.us_foreign_cuts(r, dict(SHEL, priceToBook=2.86), None)) == {"pbr"}            # 2.86 ↔ 1.49 (1.92배)
    assert set(F.us_foreign_cuts(r, dict(SHEL, priceToBook=1.49 * 1.4), None)) == {"pbr"}      # 1.40배: 1.35 밖
    assert F.us_foreign_cuts(r, dict(SHEL, priceToBook=1.49 * 1.3), None) == {}                # 1.30배: 1.35 안
    pe_c = SHEL["marketCap"] / SHEL["netIncomeToCommon"]
    assert set(F.us_foreign_cuts({"per": 10.3}, dict(SHEL, trailingPE=pe_c * 1.2), None)) == {"per"}    # 1.20배
    assert F.us_foreign_cuts({"per": 9.3}, dict(SHEL, trailingPE=pe_c * 1.08), None) == {}            # 1.08배
    assert set(F.us_foreign_cuts({"price": 100.0, "dy": 3.5}, SHEL, 3.0)) == {"dy"}                    # 3.5% ↔ 3.0% (1.17배)
    assert F.us_foreign_cuts({"price": 100.0, "dy": 3.2}, SHEL, 3.0) == {}                              # 1.07배


def test_a_non_dollar_adr_is_blanked_by_the_currency_rule_first():
    """BTI (재무제표 파운드 · ADR 1주): #114 의 fcur 가 PER · PBR · 배당수익률을 비워요. 그래서 외국 회사 검사는 이 회사를 보지 않아요.
    2026-11-14 손으로 확인: 야후 5.40% (ADR 하나당 분기 0.835달러 × 4 ÷ 61.89) — 실제 지난 4번 3.254달러 = 5.26% 와 맞지만, Jack 의 규칙대로 비워요."""
    r = rec_of("BTI", 61.89, BTI)
    assert r["fcur"] == "GBP" and not any(k in r for k in ("per", "pbr", "dy"))
    assert r["roe"] == 13.4 and r["cap"] == pytest.approx(177.313, abs=0.01)           # 같은 통화끼리 나눈 비율 · 시가총액은 남아요
    out = [r, rec_of("SHEL", 99.08, SHEL)]
    rec_ = F.us_foreign_check(out, {"BTI": {"info": BTI}, "SHEL": {"info": SHEL}}, None, dt.date(2026, 11, 13))
    assert rec_["checked"] == ["SHEL"]
    assert rec_["cut"] == [["SHEL", "dy", "배당 기록(야후 다운로드의 Dividends 칸) · 가격을 읽지 못함"]]    # 다운로드가 없으면 배당은 비어요


def test_added_stocks_use_the_long_name_and_older_stocks_keep_theirs():
    """리뷰 N3: 더한 28곳은 야후 긴 이름 (짧은 이름은 31자에서 잘리고 꼬리가 붙어요). 예전부터 있던 종목은 그대로 짧은 이름."""
    cases = {"BTI": ("British American Tobacco  Indus", "British American Tobacco p.l.c."),
             "BUD": ("Anheuser-Busch Inbev SA Sponsor", "Anheuser-Busch InBev SA/NV"),
             "SAN": ("Banco Santander, S.A. Sponsored", "Banco Santander, S.A."), "SAP": ("SAP  SE", "SAP SE"),
             "TD": ("Toronto Dominion Bank (The)", "The Toronto-Dominion Bank")}
    for t, (short, long_) in cases.items():
        r = {"t": t, "price": 10.0}
        F.apply_us_info(r, {"shortName": short, "longName": long_}, 10.0, 1333.8)
        assert r["nk"] == r["ne"] == long_, t
        r = {"t": t, "price": 10.0}
        F.apply_us_info(r, {"shortName": short}, 10.0, 1333.8)            # 긴 이름이 없으면 짧은 이름
        assert r["nk"] == short
    r = {"t": "TSM", "price": 10.0}
    F.apply_us_info(r, {"shortName": "Taiwan Semiconductor Manufactur", "longName": "Taiwan Semiconductor Manufacturing Company Limited"},
                    10.0, 1333.8)
    assert r["nk"] == "Taiwan Semiconductor Manufactur"                   # 예전 종목은 바꾸지 않아요
    r = {"t": "UL", "price": 10.0}
    F.apply_us_info(r, {"longName": "  Unilever   PLC "}, 10.0, 1333.8)
    assert r["nk"] == "Unilever PLC"


def test_a_hand_decided_company_is_never_flipped_to_etf():
    """리뷰 N4: 야후 종류가 하루 ETF 로 틀려도 사람이 회사 주식으로 정한 종목(US_NOT_ETF)은 그대로 — 관문의 ETF 여부 줄이 모두의 발행을 막지 않게."""
    out = [{"t": "BTI", "etf": False}, {"t": "SHOP", "etf": False}, {"t": "NEWETF", "etf": False}]
    cache = {t: {"info": {"quoteType": "ETF"}} for t in ("BTI", "SHOP", "NEWETF")}
    skipped = []
    assert F.etf_from_quote_type(out, cache, skipped=skipped) == ["NEWETF"]
    assert [r["etf"] for r in out] == [False, False, True] and skipped == ["BTI(ETF)", "SHOP(ETF)"]
    assert F.etf_from_quote_type([{"t": "SHOP", "etf": False}], {"SHOP": {"info": {"quoteType": "MUTUALFUND"}}}) == []


def test_trailing_dividends_window():
    end = dt.date(2026, 11, 13)
    idx = pd.to_datetime(["2025-11-14", "2025-11-28", "2026-02-20", "2026-05-22", "2026-08-14", "2026-11-13", "2026-11-16"])
    col = pd.Series([0.716, np.nan, 0.744, 0.7812, 0.7812, 0.7812, 9.9], index=idx)
    assert F.us_div_12m(col, end) == pytest.approx(0.744 + 0.7812 * 3)               # 364일 전(2025-11-14)과 기준일 뒤는 빼요
    assert F.us_div_12m(col, end, days=365) == pytest.approx(0.716 + 0.744 + 0.7812 * 3)
    assert F.us_div_12m(None, end) is None and F.us_div_12m(pd.Series(dtype=float), end) == 0.0


def test_the_check_pops_cut_fields_and_skips_non_dollar_and_unknown_companies():
    idx = pd.bdate_range("2025-10-01", "2026-11-13")
    zero = pd.Series(0.0, index=idx)
    shel, bp = zero.copy(), zero.copy()
    for d, v in (("2026-02-20", 0.744), ("2026-05-22", 0.7812), ("2026-08-14", 0.7812), ("2026-11-13", 0.7812)):
        shel[pd.Timestamp(d)] = v
    for d, v in (("2026-02-20", 0.499), ("2026-05-15", 0.499), ("2026-08-14", 0.52), ("2026-11-13", 0.52)):
        bp[pd.Timestamp(d)] = v
    data = pd.DataFrame({("SHEL", "Dividends"): shel, ("BP", "Dividends"): bp, ("SHEL", "Close"): zero + 99.08, ("BP", "Close"): zero + 45.7})
    out = [rec_of("SHEL", 99.08, SHEL), rec_of("BP", 45.70, BP), rec_of("BTI", 61.89, BTI),
           {"t": "AZN", "price": 184.45, "nk": "AZN"}, rec_of("ADC", 69.37, dict(SHEL, shortName="Agree Realty Corporation"))]
    cache = {"SHEL": {"info": SHEL}, "BP": {"info": BP}, "BTI": {"info": BTI}, "ADC": {"info": SHEL}}
    got = F.us_foreign_check(out, cache, data, dt.date(2026, 11, 13), no_info={"AZN"})
    assert got["checked"] == ["AZN", "BP", "SHEL"]                  # 상세 정보가 없는 AZN 도 확인한 것 (비울 칸이 없어요) · ADC 는 미국 회사
    assert [x[:2] for x in got["cut"]] == [["BP", "pbr"], ["BP", "per"]]
    by = {r["t"]: r for r in out}
    assert "per" not in by["BP"] and "pbr" not in by["BP"] and by["BP"]["dy"] == 4.55
    assert (by["SHEL"]["per"], by["SHEL"]["pbr"], by["SHEL"]["dy"]) == (8.6, 1.43, 3.15) and by["ADC"]["pbr"] == 1.43
    assert by["BP"]["fgnCut"] == {"pbr": "mismatch", "per": "mismatch"}                          # 앱이 그 칸 밑에 이유 줄을 붙여요
    assert not any("fgnCut" in by[t] for t in ("SHEL", "BTI", "AZN", "ADC"))
    stale = [dict(rec_of("SHEL", 99.08, SHEL), fgnCut={"pbr": "mismatch"})]                       # 맞는 회사에 남은 예전 표시는 지워요
    F.us_foreign_check(stale, {"SHEL": {"info": SHEL}}, data, dt.date(2026, 11, 13))
    assert "fgnCut" not in stale[0] and stale[0]["pbr"] == 1.43
    json.dumps(got, allow_nan=False, ensure_ascii=False)


def test_extra_missing_names_a_reason_for_every_absent_ticker():
    got = F.us_extra_missing(["SPY", "BTI", "NNN", "ADC"], {"SPY", "ADC"}, {"NNN": "가격 이력 30일 (60일 미만이라 넣지 않아요)"})
    assert got == {"BTI": "발행 목록에 없음 (빠진 까닭을 파이프라인이 적지 못했어요 — 확인 필요)", "NNN": "가격 이력 30일 (60일 미만이라 넣지 않아요)"}
    assert F.us_extra_missing(["SPY"], {"SPY"}, {}) == {}


# ── fetch_us: 외국 회사 검사와 빠진 이유가 발행 목록까지 ──────────────────
def _fake_yf(series, divs, infos, calls):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"]})
        cols = {}
        for t in tickers:
            if t not in series:
                continue                                            # 야후가 그 종목을 주지 않음 → 시세를 받지 못함
            cols[(t, "Close")] = series[t]
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


def _fetch(tmp_path, monkeypatch):
    """아래 시험의 가짜 야후로 fetch_us 를 한 번 (BTI 파운드 · SHEL · BP 달러 · AAPL · NNN 30일 · TD 시세 없음) → (us, meta, 로그)."""
    today = dt.date(2026, 11, 14)
    days = pd.bdate_range(today - dt.timedelta(days=500), dt.date(2026, 11, 13))

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])                          # 마지막 종가를 2026-11-13 값으로
    series = {"_spx": walk(1, 6700.0), "SHEL": walk(2, 99.08), "BP": walk(3, 45.70), "BTI": walk(4, 61.89), "AAPL": walk(5, 270.0),
              "NNN": walk(6, 41.18).tail(30), "STAG": pd.Series(np.nan, index=days)}      # STAG: 야후가 빈 칸만 줌 (리뷰 N6)
    divs = {"SHEL": [("2025-11-14", 0.716), ("2026-02-20", 0.744), ("2026-05-22", 0.7812), ("2026-08-14", 0.7812), ("2026-11-13", 0.7812)],
            "BP": [("2026-02-20", 0.499), ("2026-05-15", 0.499), ("2026-08-14", 0.52), ("2026-11-13", 0.52)]}
    aapl = dict(SHEL, shortName="Apple Inc.", industry="Consumer Electronics", sector="Technology")
    infos = {"SHEL": SHEL, "BP": BP, "BTI": BTI, "AAPL": aapl, "NNN": SHEL}
    calls = []
    syms = ["AAPL", "BP", "BTI", "NNN", "SHEL", "STAG", "TD"]        # TD: 야후가 그 종목을 아예 주지 않아요
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series, divs, infos, calls))
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: dt.date(2026, 11, 13))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    us, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    meta.pop("_index")
    return us, meta, lines


def test_fetch_us_checks_foreign_numbers_and_names_missing_extras(tmp_path, monkeypatch):
    us, meta, lines = _fetch(tmp_path, monkeypatch)
    by = {r["t"]: r for r in us}
    assert sorted(by) == ["AAPL", "BP", "BTI", "SHEL"]
    assert (by["SHEL"]["nk"], by["BP"]["nk"], by["BTI"]["nk"]) == ("Shell plc", "BP p.l.c.", "British American Tobacco p.l.c.")
    assert (by["SHEL"]["per"], by["SHEL"]["pbr"], by["SHEL"]["dy"]) == (8.6, 1.43, 3.15)
    assert "per" not in by["BP"] and "pbr" not in by["BP"] and by["BP"]["dy"] == 4.55
    assert by["BTI"]["fcur"] == "GBP" and not any(k in by["BTI"] for k in ("per", "pbr", "dy"))
    assert by["AAPL"]["pbr"] == 1.43                                 # 미국 회사는 이 검사를 받지 않아요
    assert meta["usForeign"]["checked"] == ["BP", "SHEL"] and [x[:2] for x in meta["usForeign"]["cut"]] == [["BP", "pbr"], ["BP", "per"]]
    miss = meta["usExtraMissing"]
    assert miss["NNN"] == "가격 이력 30일 (60일 미만이라 넣지 않아요)" and miss["TD"].startswith("시세를 받지 못함")
    assert miss["STAG"] == "야후가 가격을 하나도 주지 않음 (다운로드에 이 종목의 종가가 없어요)"
    assert miss["SPY"] == "미국 요청 목록에 없음 (티커 모양)" and "BTI" not in miss and "SHEL" not in miss
    assert set(miss) == set(F.EXTRA_US) - {"BP", "BTI", "SHEL"}
    assert any(x.startswith("  !! 미국 상장 외국 회사의 주당 숫자") and "PER 비움 1곳 (BP)" in x and "PBR 비움 1곳 (BP)" in x for x in lines), lines
    assert any("BP PBR: 주가 ÷ 주당 장부가 7.62" in x for x in lines)
    assert any(x.startswith("  !! 손으로 더한 미국 종목(EXTRA_US 67개) 중 오늘 목록에 없는 종목") for x in lines)
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(us, allow_nan=False, ensure_ascii=False)


def test_a_crashed_foreign_check_blanks_every_checkable_number_loudly(tmp_path, monkeypatch):
    """리뷰 S2(c): 외국 회사 검사가 멈추면 맞춰 보지 못한 숫자를 내보내지 않아요 — 외국 회사(fcur 없음)의 PER · PBR · 배당수익률을 모두 비우고
    이유 '검사가 멈춤' 과 함께 크게 남겨요. 관문은 그 기록을 받되 경고해요 (리뷰 S1: 그 칸엔 이유 줄이 없어 앱이 '자료가 없어요')."""
    def boom(*a, **k):
        raise RuntimeError("시험")
    monkeypatch.setattr(F, "us_foreign_check", boom)
    us, meta, lines = _fetch(tmp_path, monkeypatch)
    by = {r["t"]: r for r in us}
    for t in ("SHEL", "BP"):
        assert not any(k in by[t] for k in ("per", "pbr", "dy", "fgnCut")), by[t]                  # 멈춘 날은 '–' 만 (이유 줄 없음)
    assert by["AAPL"]["pbr"] == 1.43 and by["BTI"]["fcur"] == "GBP"
    assert meta["usForeign"]["checked"] == ["BP", "SHEL"]
    assert sorted(x[:2] for x in meta["usForeign"]["cut"]) == [[t, f] for t in ("BP", "SHEL") for f in ("dy", "pbr", "per")]
    assert all(x[2] == "검사가 멈춤 (RuntimeError)" for x in meta["usForeign"]["cut"])
    assert any(x.startswith("  !! 미국 상장 외국 회사 검사가 멈췄어요 (RuntimeError: 시험) → 끝까지 본 0곳의 비운 칸 0칸은 그대로 · 나머지 6칸을")
               for x in lines), lines
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": meta["usForeign"]}, us, "publish")
    r = row(rep, FOREIGN)
    assert r[3] == "WARN" and r[1].startswith("확인 2곳 · 비운 칸 PER 2 · PBR 2 · 배당 2"), rep.table()
    assert "검사가 멈춰 맞춰 보지 않고 비운 회사 2곳: BP, SHEL" in r[1]


def test_a_crash_mid_loop_keeps_what_was_already_checked(tmp_path, monkeypatch):
    """리뷰 N1: BP 를 끝까지 본 뒤 SHEL 에서 멈추면 — BP 의 비운 칸 · cut 줄 · 표시(fgnCut)는 그대로, SHEL 의 세 칸만 '검사가 멈춤' 으로 비워요."""
    real = F.us_foreign_cuts

    def cuts(rec, info, div12, **kw):
        if rec["t"] == "SHEL":
            raise ValueError("시험: 중간에 멈춤")
        return real(rec, info, div12, **kw)
    monkeypatch.setattr(F, "us_foreign_cuts", cuts)
    us, meta, lines = _fetch(tmp_path, monkeypatch)
    by = {r["t"]: r for r in us}
    assert by["BP"]["fgnCut"] == {"pbr": "mismatch", "per": "mismatch"} and by["BP"]["dy"] == 4.55
    assert not any(k in by["SHEL"] for k in ("per", "pbr", "dy", "fgnCut")), by["SHEL"]
    cut = meta["usForeign"]["cut"]
    assert [x[:2] for x in cut] == [["BP", "pbr"], ["BP", "per"], ["SHEL", "per"], ["SHEL", "pbr"], ["SHEL", "dy"]], cut
    assert cut[0][2].startswith("주가 ÷ 주당 장부가") and all(x[2] == "검사가 멈춤 (ValueError)" for x in cut[2:])
    assert meta["usForeign"]["checked"] == ["BP", "SHEL"]
    assert any("끝까지 본 1곳의 비운 칸 2칸은 그대로 · 나머지 3칸을 맞춰 보지 않고 비웠어요 (이유 줄 없음): SHEL per, SHEL pbr, SHEL dy" in x
               for x in lines), lines
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": meta["usForeign"]}, us, "publish")
    r = row(rep, FOREIGN)
    assert r[3] == "WARN" and "검사가 멈춰 맞춰 보지 않고 비운 회사 1곳: SHEL" in r[1], rep.table()


def test_the_crash_path_clears_a_stale_mark(tmp_path, monkeypatch):
    """리뷰 N1 (살아남은 변이): 멈춘 검사가 남긴 표시는 지워요 — 끝까지 보지 못한 종목엔 이유 줄 표시가 없어야 해요."""
    def boom(out, *a, done=None, **k):
        next(r for r in out if r["t"] == "SHEL")["fgnCut"] = {"pbr": "mismatch"}
        raise RuntimeError("시험")
    monkeypatch.setattr(F, "us_foreign_check", boom)
    us, meta, _lines = _fetch(tmp_path, monkeypatch)
    by = {r["t"]: r for r in us}
    assert "fgnCut" not in by["SHEL"] and not any(k in by["SHEL"] for k in ("per", "pbr", "dy"))
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": meta["usForeign"]}, us, "publish")
    assert row(rep, FOREIGN)[3] == "WARN", rep.table()


# ── 관문 ─────────────────────────────────────────────────
def row(rep, name):
    return next(r for r in rep.rows if r[0] == name)


def us_rows(extra=(), drop=()):
    rows = [{"t": t, "cls": "us", "price": 10.0, "etf": t in V.US_ETF_SET} for t in sorted(V.US_EXTRA_SET) if t not in drop]
    return rows + list(extra)


def test_gate_extra_all_present_passes():
    rep = V.Report()
    V.check_us_extra(rep, {"usExtraMissing": {}}, us_rows(), "publish")
    assert row(rep, EXTRA)[1:] == ("67 / 67 있음", "모두 있어야 함 (빠지면 이유와 함께 경고 · 이유 없이 빠지면 실패)", "PASS")


def test_gate_extra_missing_with_a_reason_warns_by_name():
    rep = V.Report()
    V.check_us_extra(rep, {"usExtraMissing": {"BTI": "시세를 받지 못함 (KeyError)"}}, us_rows(drop={"BTI"}), "publish")
    r = row(rep, EXTRA)
    assert r[3] == "WARN" and "BTI (시세를 받지 못함 (KeyError))" in r[1] and r[1].startswith("66 / 67 있음")
    assert ("손으로 더한 미국 종목 중 오늘 없는 종목 (usExtraMissing)", ["BTI: 시세를 받지 못함 (KeyError)"]) in rep.details


@pytest.mark.parametrize("why", [None, "", "  ", 3])
def test_gate_extra_missing_without_a_reason_fails_to_publish(why):
    miss = {} if why is None else {"BTI": why}
    rep = V.Report()
    V.check_us_extra(rep, {"usExtraMissing": miss}, us_rows(drop={"BTI", "SHEL"}) + [{"t": "SHEL", "cls": "us", "price": 0}], "publish")
    r = row(rep, EXTRA)
    assert r[3] == "FAIL" and "이유 없이 빠짐 2: BTI, SHEL" in r[1]                    # 가격 0 도 빠진 것
    rep = V.Report()
    V.check_us_extra(rep, {"usExtraMissing": miss}, us_rows(drop={"BTI"}), "live")      # 사이트 점검은 경고 (어제 파일로 배포될 때 막지 않게)
    assert row(rep, EXTRA)[3] == "WARN"


def test_gate_extra_without_the_record():
    rep = V.Report()
    V.check_us_extra(rep, {}, us_rows(drop={"BTI"}), "live")
    assert row(rep, EXTRA)[3] == "SKIP"
    rep = V.Report()
    V.check_us_extra(rep, {}, us_rows(drop={"BTI"}), "publish")
    assert row(rep, EXTRA)[3] == "WARN" and "기록 없음" in row(rep, EXTRA)[1]
    rep = V.Report()
    V.check_us_extra(rep, {"usExtraMissing": {"ZZZZ": "?"}}, us_rows(), "publish")         # 두 목록이 어긋나면 경고
    assert row(rep, EXTRA)[3] == "WARN" and "관문 목록에 없는 티커 1: ZZZZ" in row(rep, EXTRA)[1]


def foreign_us():
    return [{"t": "SHEL", "cls": "us", "price": 99.08, "per": 8.6, "pbr": 1.43, "dy": 3.15, "vz": 70},
            {"t": "BP", "cls": "us", "price": 45.7, "dy": 4.55, "fgnCut": {"pbr": "mismatch", "per": "mismatch"}},
            {"t": "BTI", "cls": "us", "price": 61.89, "fcur": "GBP"},
            {"t": "AAPL", "cls": "us", "price": 270.0, "per": 36.0, "pbr": 50.0}]


GOOD = {"checked": ["BP", "SHEL"], "cut": [["BP", "pbr", "주가 ÷ 주당 장부가 7.62 ↔ … (4.32배)"], ["BP", "per", "… (1.70배)"]]}


def test_gate_foreign_good_record_passes():
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": GOOD}, foreign_us(), "publish")
    r = row(rep, FOREIGN)
    assert r[3] == "PASS" and r[1] == "확인 2곳 · 비운 칸 PER 1 · PBR 1 · 배당 0 (BP)"
    assert rep.details[0][1] == ["BP pbr: 주가 ÷ 주당 장부가 7.62 ↔ … (4.32배)", "BP per: … (1.70배)"]


@pytest.mark.parametrize("change, expect", [
    (lambda us, rec: us[1].update(pbr=7.62), "남은 칸 1: BP.pbr"),
    (lambda us, rec: us[1].update(vz=99), "남은 칸 1: BP.vz"),                         # PBR 을 비우면 가치 점수도
    (lambda us, rec: rec.update(checked=["BP"]), "맞춰 보지 않은 숫자 1곳: SHEL"),
    (lambda us, rec: rec["cut"].append(["BP", "roe", "x"]), "모양 1"),
    (lambda us, rec: rec["cut"].append(["BP", "dy", ""]), "모양 1"),
    (lambda us, rec: rec.update(checked="BP"), "모양 1: checked 모양"),
    (lambda us, rec: us[1].pop("fgnCut"), "이유 표시(fgnCut) 없음 2: BP.pbr, BP.per"),            # 앱이 '자료가 없어요' 를 보일 뻔
    (lambda us, rec: us[1]["fgnCut"].pop("per"), "이유 표시(fgnCut) 없음 1: BP.per"),
    (lambda us, rec: us[1]["fgnCut"].update(dy="mismatch"), "남은 칸 1: BP.dy"),                    # 표시한 칸에 숫자가 남음
    (lambda us, rec: us[1].update(fgnCut={"pbr": "odd"}), "모양 1"),
    (lambda us, rec: us[1].update(fgnCut=["pbr"]), "모양 1"),
    (lambda us, rec: us[0].update(fgnCut={"vz": "mismatch"}), "모양 1"),
    (lambda us, rec: us[3].update(fgnCut={"pbr": "mismatch"}, pbr=None), "모양 1: AAPL.fgnCut (외국 회사 목록 밖이거나 fcur)"),
    (lambda us, rec: rec["cut"].pop(1), "cut 줄 없는 표시 1: BP.per"),                              # 리뷰 N3: 표시만 있고 줄이 없음
    (lambda us, rec: us[0].update(fgnCut={"dy": "mismatch"}, dy=None), "cut 줄 없는 표시 1: SHEL.dy"),
])
def test_gate_foreign_fails(change, expect):
    us, rec = foreign_us(), json.loads(json.dumps(GOOD))
    change(us, rec)
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": rec}, us, "publish")
    r = row(rep, FOREIGN)
    assert r[3] == "FAIL" and expect in r[1], r


def test_gate_foreign_accepts_a_stopped_check_without_marks():
    """검사가 멈춘 날 (fetch_us 의 예외 길): 비운 칸에 이유 줄 표시가 없어도 실패하지 않지만 경고해요 (리뷰 S1 — 그날 앱은 그 회사의 요약 칸 ·
    배당 머리에 '자료가 없어요' 를 보여요 · 발행은 막지 않아요)."""
    us = [{"t": "SHEL", "cls": "us", "price": 99.08}, {"t": "BP", "cls": "us", "price": 45.7}]
    rec = {"checked": ["BP", "SHEL"], "cut": [[t, f, "검사가 멈춤 (RuntimeError)"] for t in ("BP", "SHEL") for f in ("per", "pbr")]}
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": rec}, us, "publish")
    r = row(rep, FOREIGN)
    assert r[3] == "WARN" and "검사가 멈춰 맞춰 보지 않고 비운 회사 2곳: BP, SHEL (이유 줄 없음 · 앱은 '자료가 없어요')" in r[1], rep.table()
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": GOOD}, foreign_us(), "publish")                    # 보통 날은 경고 없음
    assert row(rep, FOREIGN)[3] == "PASS"


def test_gate_foreign_without_the_record():
    rep = V.Report()                                                 # 이 칸 전 발행본: 외국 회사 숫자가 없으면 (어제 파일) 통과
    V.check_us_foreign(rep, {}, [s for s in foreign_us() if s["t"] in ("BTI", "AAPL")], "live")
    assert row(rep, FOREIGN)[3] == "PASS"
    plain = [{k: v for k, v in s.items() if k != "fgnCut"} for s in foreign_us()]
    for mode, st in (("publish", "FAIL"), ("live", "WARN")):
        rep = V.Report()
        V.check_us_foreign(rep, {}, plain, mode)
        assert row(rep, FOREIGN)[3] == st and "맞춰 보지 않은 숫자 2곳: BP, SHEL" in row(rep, FOREIGN)[1]
    for mode in ("publish", "live"):                                 # 리뷰 N3: 기록 없이 표시만 있으면 어느 쪽이든 실패
        rep = V.Report()
        V.check_us_foreign(rep, {}, foreign_us(), mode)
        assert row(rep, FOREIGN)[3] == "FAIL" and "기록 없음 (data.json usForeign) 인데 fgnCut 표시가 있는 종목 1곳: BP" in row(rep, FOREIGN)[1]


def test_good_fixture_still_passes_with_both_rows():
    """기록이 없는 시험 데이터(이 칸 전 모양): 발행 관문은 실패하지 않아요 — 더한 종목 줄은 '기록 없음' 경고, 외국 회사 줄은 통과."""
    cur, prev, final = good_pair()
    rep = V.run_checks(cur, prev, final, dt.date(2026, 10, 31), mode="publish", count_between=lambda a, b: 1,
                       sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                       now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
    assert row(rep, EXTRA)[3] == "WARN" and row(rep, FOREIGN)[3] == "PASS"
    cur2 = clone(cur)
    cur2["data"]["stocks"] += [{"t": t, "cls": "us", "price": 10.0, "etf": t in V.US_ETF_SET, "nk": t, "ne": t, "de": "x"}
                               for t in sorted(V.US_EXTRA_SET) if t not in {"BRK-B", "SPY", "QQQ"}]
    cur2["data"]["usExtraMissing"], cur2["data"]["usForeign"] = {}, {"checked": [], "cut": []}
    rep = V.Report()
    V.check_us_extra(rep, cur2["data"], V.us_stocks(cur2["data"]), "publish")
    V.check_us_foreign(rep, cur2["data"], V.us_stocks(cur2["data"]), "publish")
    assert [r[3] for r in rep.rows] == ["PASS", "PASS"], rep.table()
