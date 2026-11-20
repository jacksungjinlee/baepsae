# -*- coding: utf-8 -*-
"""미국 주식 종류 티커 (Jack, 2026-11-15: "fix Brown-Forman B, then check every share-class ticker in the S&P 500 and NASDAQ sources (dots,
missing separators, A/B classes) and add any others missing for the same reason") — fetch_data.py us_symbol · us_tickers · us_list_sym ·
fetch_us(usListSym) 와 validate_data.py check_us_share_class. (네트워크 없음 · 더하기만)

- FinanceDataReader 의 S&P 500 목록(위키백과 표)은 점을 지워요: 'BRK.B' → 'BRKB' · 'BF.B' → 'BFB'. 야후에 그런 티커는 없어서 BF-B 는 목록에 한 번도
  없었고 BRK-B 는 EXTRA_US 로만 들어왔어요. 이제 us_symbol 이 근거를 확인한 표(US_CLASS_JOINED)로 야후 대시 꼴로 바꿔요 (끝 글자를 떼어 짐작하지
  않아요 · 목록 이름이 있고 맞아야 해요). 점 · 빗금 · 띄어쓰기 꼴은 어느 출처든 대시로.
- 나스닥 목록(네이버)의 종류 티커(GOOGL · GOOG · FOXA · FOX · NWSA · NWS · FWONK · LLYVK …)는 나스닥 자기 티커 그대로라 야후와 같아요 (바꾸지 않아요).
- 바꾸지 못한 티커는 크게 남기고 기록(usListSym.unmapped)에 적어요 · S&P 500 목록 티커인데 야후가 가격을 하나도 주지 않으면 (점이 지워진 새 주식
  종류 티커의 모습) noPx, 처리하다 오류가 나면 spErr 에 적고 관문이 경고해요.
- 관문: 이 바꾸기로 들어온 종목(BF-B)은 목록에 있어야 해요. 빠지면 이유가 있든 없든 경고 (Jack 2026-11-20: "Brown-Forman B: no, it becomes a
  warning; one stock missing from a source never holds the publish.") · 목록에 있는데 가격이 없으면 발행 실패 (틀린 값).

표(US_CLASS_JOINED)에 줄을 더할 때 (RUNBOOK "US share-class tickers"): 이 파일에는 SP_ROWS 에 그 S&P 500 목록 행 하나만 더하면 돼요
(test_every_table_row_has_a_fixture_row 가 알려 줘요). 다른 시험은 표에서 기대값을 만들어요.
값은 2026-11-15 의 실제 목록 · 야후 값 그대로 (필요한 칸만)."""
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
from fixture_data import good_pair  # noqa: E402

ROW1 = f"주식 종류 티커로 들어온 미국 종목 ({', '.join(sorted(V.US_CLASS_SET))}): 목록에 있거나 빠진 이유"
ROW2 = "미국 목록 출처 티커 (주식 종류 · 점이 지워진 꼴)"
N_ADDED = len(V.US_CLASS_SET)
TH1 = "모두 있어야 함 (빠지면 이유가 있든 없든 경고 · 목록에 있는데 가격이 없으면 실패, 사이트 점검은 경고)"

# 2026-11-15 FinanceDataReader StockListing("S&P500") 의 행 그대로 (위키백과 표의 BRK.B · BF.B 가 점이 지워진 채로).
# 표(US_CLASS_JOINED)의 열쇠마다 그 S&P 500 목록 행이 여기 있어야 해요 — 표에 줄을 더하면 여기에도 한 줄.
SP_ROWS = [("AAPL", "Apple Inc."), ("BRKB", "Berkshire Hathaway"), ("BFB", "Brown–Forman"), ("GOOGL", "Alphabet Inc. (Class A)"),
           ("GOOG", "Alphabet Inc. (Class C)"), ("FOXA", "Fox Corporation (Class A)"), ("FOX", "Fox Corporation (Class B)"),
           ("NWSA", "News Corp (Class A)"), ("NWS", "News Corp (Class B)"), ("VYLR", "Vylor")]
# 2026-11-15 위키백과 표의 원래 꼴 (점) — FinanceDataReader 가 점을 지우지 않게 바뀌어도 같은 티커가 돼요
WIKI_DOTTED = [("BRK.B", "Berkshire Hathaway"), ("BF.B", "Brown–Forman")]
# 2026-11-15 FinanceDataReader StockListing("NASDAQ") (네이버, 3,985행) 의 보통주 종류 티커 그대로 — 나스닥 자기 티커 (괄호 = 시가총액 순위).
# 상위 400 (실행이 읽어요): GOOGL(5) · GOOG(9) · FWONK(159) · FOXA(164) · FCNCA(165) · FOX(241) · NWSA(288) · LLYVK(372)
NQ_ROWS = [("GOOGL", "Alphabet Inc. Class A"), ("GOOG", "Alphabet Inc. Class C"), ("FWONK", "Liberty Media Formula One Ord Shs Series C"),
           ("FOXA", "Fox Corporation Class A"), ("FCNCA", "First Citizens BancShares  Inc."), ("FOX", "Fox Corporation Class B"),
           ("NWSA", "News Corporation Class A"), ("LLYVK", "Liberty Live Holdings Inc Series C")]
# 400 밖 (읽지 않아요 · 야후 꼴 그대로 — 티커 모양 문제가 아니라 400 경계 때문이에요)
NQ_OUTSIDE = [("NWS", "News Corporation Class B"), ("Z", "Zillow Group  Inc. Class C"), ("PAGP", "Plains GP Holdings Limited Partner Interests Units Class A"),
              ("RUSHA", "Rush Enterprises  Inc. Class A"),
              ("BELFB", "Bel Fuse Inc. Class B"), ("BATRK", "Liberty Media Liberty Braves Ord Shs Series C"),
              ("LLYVA", "Liberty Live Holdings Inc Series A"), ("FWONA", "Liberty Media Formula One Ord Shs Series A"),
              ("CENTA", "Central Garden & Pet Co Class A"), ("LBTYA", "Liberty Global Ltd Class A"), ("LBTYK", "Liberty Global Ltd Class C"),
              ("RUSHB", "Rush Enterprises  Inc. Class B"), ("LILAK", "Liberty Latin America Ltd. Class C"), ("ZG", "Zillow Group  Inc. Class A"),
              ("GLIBK", "Liberty Capital Corporation Series C"), ("SENEA", "Seneca Foods Corporation Class A"),
              ("PSNY", "Polestar Automotive Holding UK PLC ADR Class A"), ("DGICA", "Donegal Group Inc Class A"),
              ("BATRA", "Liberty Media Liberty Braves Ord Shs  Series A"), ("CENT", "Central Garden & Pet Co"),
              ("KELYA", "Kelly Services Inc Class A"), ("QVCG", "QVC Group  Inc."), ("BELFA", "Bel Fuse Inc. Class A"),
              ("METC", "Ramaco Resources  Inc. Class A"), ("LILA", "Liberty Latin America Ltd. Class A"), ("SENEB", "Seneca Foods Corporation Class B"),
              ("LBTYB", "Liberty Global Ltd Class B"), ("DGICB", "Donegal Group Inc Class B"), ("GLIBA", "Liberty Capital Corporation Series A"),
              ("KELYB", "Kelly Services Inc Class B"), ("METCB", "Ramaco Resources  Inc. Class B"), ("RDI", "Reading International Inc Class A"),
              ("RDIB", "Reading International Inc Class B"), ("UONEK", "Urban One Inc Class D"), ("UONE", "Urban One Inc Class A"),
              ("QVCGA", "QVC Group Inc Series A")]

# 2026-11-15 야후 info (필요한 칸만 · 값 그대로)
BFB_INFO = {"shortName": "Brown Forman Inc", "longName": "Brown-Forman Corporation", "quoteType": "EQUITY", "sector": "Consumer Defensive",
            "industry": "Beverages - Wineries & Distilleries", "longBusinessSummary": "Brown-Forman Corporation, together with its subsidiaries, "
            "manufactures, distills, bottles, imports, exports, markets, and sells various alcoholic beverages.", "trailingPE": 19.774195,
            "priceToBook": 3.542124, "returnOnEquity": 0.18122, "operatingMargins": 0.28199, "revenueGrowth": -0.014, "debtToEquity": 61.502,
            "dividendYield": 3.01, "marketCap": 14064189440, "averageVolume": 2515207, "financialCurrency": "USD", "currency": "USD",
            "totalRevenue": 3915000064, "dividendRate": 0.92, "trailingAnnualDividendRate": 0.92, "netIncomeToCommon": 721000000,
            "country": "United States"}
BRKB_INFO = {"shortName": "Berkshire Hathaway Inc. New", "longName": "Berkshire Hathaway Inc.", "quoteType": "EQUITY",
             "sector": "Financial Services", "industry": "Insurance - Diversified", "trailingPE": 16.595018, "priceToBook": 0.0011053797,
             "marketCap": 1259712413696, "averageVolume": 4446000, "financialCurrency": "USD", "currency": "USD", "dividendYield": 0.0,
             "country": "United States", "longBusinessSummary": "Berkshire Hathaway Inc. owns subsidiaries in insurance, freight rail and utilities."}
NO_NAME = "의 회사인지 S&P 목록에 회사 이름이 없어 맞춰 보지 못함"
LOST = "S&P 500 목록에 점이 지워진 꼴 BFB 로 있는데 BF-B 로 바뀌지 않음 (바꾸기 확인 필요 · RUNBOOK 'US share-class tickers')"
SHAPE = "티커 모양이 아님 (영문 1~5자, 또는 그 뒤 점 · 빗금 · 띄어쓰기 · 대시와 종류 글자 1~2자)"


def sp_mapped():
    """SP_ROWS 를 표로 바꾼 기대값 [["S&P500", 지워진 꼴, 야후 티커]] (목록 순서)."""
    return [["S&P500", k, F.US_CLASS_JOINED[k][0]] for k, _n in SP_ROWS if k in F.US_CLASS_JOINED]


def sp_yahoo():
    return frozenset(F.US_CLASS_JOINED[k][0] if k in F.US_CLASS_JOINED else k for k, _n in SP_ROWS)


def plain(short):
    return {"shortName": short, "longName": short, "quoteType": "EQUITY", "sector": "Communication Services", "industry": "Internet Content & Information",
            "financialCurrency": "USD", "currency": "USD", "country": "United States", "marketCap": 1e11, "averageVolume": 1e6,
            "longBusinessSummary": f"{short} does things."}


def listing(rows, nasdaq=False, names=True):
    cols = {"Symbol": [r[0] for r in rows]}
    if names:
        cols["Name"] = [r[1] for r in rows]
    cols.update({"IndustryCode": "0", "Industry": "x"} if nasdaq else {"Sector": "x", "Industry": "x"})
    return pd.DataFrame(cols)


class FakeFDR:
    def __init__(self, sp=None, nq=None, fail=()):
        self.sp = listing(SP_ROWS) if sp is None else sp
        self.nq = listing(NQ_ROWS, nasdaq=True) if nq is None else nq
        self.fail = set(fail)

    def StockListing(self, name):
        if name in self.fail:
            raise RuntimeError("목록 실패 (시험)")
        return self.sp if name == "S&P500" else self.nq


# ── 표 ───────────────────────────────────────────────────
def test_brown_forman_b_and_berkshire_b_are_in():
    """이 PR 의 두 회사 (Jack 2026-11-15). 표에 줄을 더해도 이 시험은 그대로예요."""
    assert {"BRKB": "BRK-B", "BFB": "BF-B"}.items() <= {k: v[0] for k, v in F.US_CLASS_JOINED.items()}.items()
    assert "BF-B" in F.US_CLASS_ADDED and "BF-B" in V.US_CLASS_SET
    assert "BRK-B" in F.EXTRA_US and "BRK-B" in V.US_EXTRA_SET and "BRK-B" not in F.US_CLASS_ADDED   # BRK-B 는 EXTRA_US 에 그대로 (S&P 목록을 못 읽는 날의 바닥)


def test_the_pipeline_and_gate_tables_agree():
    """관문은 같은 표를 따로 적어요 (같은 실수를 같이 하지 않게). 줄을 더하면 두 파일에 같이."""
    assert V.US_CLASS_JOINED_SET == {k: v[0] for k, v in F.US_CLASS_JOINED.items()}
    assert V.US_CLASS_SET == set(F.US_CLASS_ADDED) and len(F.US_CLASS_ADDED) == len(set(F.US_CLASS_ADDED))
    assert set(F.US_CLASS_ADDED) <= {y for y, _k in F.US_CLASS_JOINED.values()}          # 더한 종목은 모두 표에서 와요
    assert not set(F.US_CLASS_ADDED) & set(F.EXTRA_US)                                   # EXTRA_US 와 겹치면 한 관문 줄로 충분해요
    for k, (y, key) in F.US_CLASS_JOINED.items():
        assert F.US_SYM_PLAIN.fullmatch(k) and F.US_SYM_YAHOO.fullmatch(y) and "-" in y, k   # 지워진 꼴 → 대시 꼴
        assert y.replace("-", "") == k                                                   # 점(대시)만 지워진 꼴이에요
        assert key and key == "".join(c for c in key if "a" <= c <= "z"), k               # 이름 글자는 영문 소문자만 (목록 이름도 그렇게 줄여 봐요)


def test_every_table_row_has_a_fixture_row():
    """표의 줄마다 SP_ROWS 에 그 S&P 500 목록 행이 있고, 그 행이 표대로 바뀌어요. 표에 줄을 더했는데 실패하면: SP_ROWS 에 ("지워진 꼴", "S&P 목록 이름") 한 줄."""
    names = dict(SP_ROWS)
    for k, (y, key) in F.US_CLASS_JOINED.items():
        assert k in names, f"SP_ROWS 에 S&P 500 목록 행 ({k!r}, '<목록 이름>') 을 더해 주세요"
        assert F.us_symbol(k, "S&P500", names[k]) == (y, f"점이 지워진 S&P 500 표기 '{k}' → {y}"), k
        assert key in "".join(c for c in names[k].lower() if "a" <= c <= "z"), k


# ── us_symbol: 출처에서 찾은 모든 꼴 ─────────────────────────
def test_the_joined_s_and_p_tickers_become_yahoo_dash_forms():
    assert F.us_symbol("BRKB", "S&P500", "Berkshire Hathaway") == ("BRK-B", "점이 지워진 S&P 500 표기 'BRKB' → BRK-B")
    assert F.us_symbol("BFB", "S&P500", "Brown–Forman") == ("BF-B", "점이 지워진 S&P 500 표기 'BFB' → BF-B")
    for raw, nm in WIKI_DOTTED:                                                   # 위키백과의 점 꼴 그대로 와도
        y, note = F.us_symbol(raw, "S&P500", nm)
        assert y == {"BRK.B": "BRK-B", "BF.B": "BF-B"}[raw] and note == f"주식 종류 '{raw}' → 야후 대시 꼴 {y}"


@pytest.mark.parametrize("name", [None, "", "   ", float("nan")])
def test_a_joined_form_without_a_list_name_is_not_mapped(name):
    """리뷰 1: 이름 칸이 비면 맞춰 볼 근거가 없어요 — 바꾸지 않고 (열린 채로 두지 않아요) 이유와 함께 돌려줘요."""
    for k, (y, _key) in F.US_CLASS_JOINED.items():
        assert F.us_symbol(k, "S&P500", name) == (None, f"점이 지워진 주식 종류 표({k} → {y}){NO_NAME}"), k


def test_other_separators_become_the_dash_and_the_dash_stays():
    for raw in ("BRK.B", "BRK/B", "BRK B", "brk.b", " BRK-B ", "BRK-B"):
        assert F.us_symbol(raw, "NASDAQ")[0] == "BRK-B", raw
    assert F.us_symbol("BRK-B", "EXTRA_US") == ("BRK-B", None)                 # 이미 야후 꼴이면 메모 없음
    assert F.us_symbol("BF.A", "S&P500", "Brown–Forman") == ("BF-A", "주식 종류 'BF.A' → 야후 대시 꼴 BF-A")
    assert F.us_symbol("HEI.A", "NASDAQ")[0] == "HEI-A" and F.us_symbol("MOG/A", "S&P500")[0] == "MOG-A"
    assert F.us_symbol("MKC.V", "S&P500", "McCormick")[0] == "MKC-V" and F.us_symbol("LEN.B", "S&P500")[0] == "LEN-B"


def test_class_tickers_that_already_match_yahoo_are_left_alone():
    """S&P 500 의 GOOGL · GOOG · FOXA · FOX · NWSA · NWS 와 나스닥 자기 종류 티커(2026-11-15 목록 전부)는 야후와 같은 꼴이에요 — 글자를 떼거나
    붙이지 않아요."""
    for raw, nm in SP_ROWS:
        if raw not in F.US_CLASS_JOINED:
            assert F.us_symbol(raw, "S&P500", nm) == (raw, None), raw
    for raw, nm in NQ_ROWS + NQ_OUTSIDE:
        assert F.us_symbol(raw, "NASDAQ", nm) == (raw, None), raw
    for t in F.EXTRA_US:                                                            # 손으로 더한 67개도 그대로
        assert F.us_symbol(t, "EXTRA_US") == (t, None), t


def test_a_joined_form_is_mapped_only_from_the_s_and_p_list_and_only_for_its_company():
    """'BFB' 를 짐작으로 바꾸지 않아요: S&P 500 목록에서, 그 회사 이름일 때만. 다른 출처의 'BFB' 나 처음 보는 붙은 꼴은 그대로 (야후가 답하지 않으면
    noPx 가 이름을 남겨요)."""
    assert F.us_symbol("BFB", "NASDAQ", "Brown–Forman") == ("BFB", None)
    assert F.us_symbol("BFB", "EXTRA_US") == ("BFB", None)
    assert F.us_symbol("XYZA", "S&P500", "Xyz Holdings (Class A)") == ("XYZA", None)   # 표에 없는 꼴은 짐작하지 않아요
    y, note = F.us_symbol("BFB", "S&P500", "Big Fun Bancorp")
    assert y is None and note == "점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"


@pytest.mark.parametrize("raw, why", [
    (None, "티커 칸이 비었거나 글자가 아님"), (float("nan"), "티커 칸이 비었거나 글자가 아님"), ("", "티커 칸이 비었거나 글자가 아님"),
    ("   ", "티커 칸이 비었거나 글자가 아님"), ("ÄBC", "티커에 영문이 아닌 글자"), ("ABCDEF", SHAPE), ("BRK.B.X", SHAPE), ("A1B", SHAPE)])
def test_unmappable_tickers_come_back_with_a_reason(raw, why):
    assert F.us_symbol(raw, "S&P500") == (None, why)


def test_every_output_is_yahoo_shaped():
    for raw, nm in SP_ROWS + WIKI_DOTTED + NQ_ROWS + NQ_OUTSIDE:
        y, _ = F.us_symbol(raw, "S&P500", nm)
        assert y is not None and F.US_SYM_YAHOO.fullmatch(y), raw


# ── us_tickers: 실제 목록 모양 ──────────────────────────────
def test_us_tickers_maps_the_joined_forms_and_names_them(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR())
    names = F.UsListNames()
    syms = F.us_tickers(names)
    assert {"BRK-B", "BF-B", "GOOGL", "GOOG", "FOXA", "FOX", "NWSA", "NWS", "FWONK", "LLYVK", "FCNCA", "VYLR"} <= set(syms)
    assert not set(F.US_CLASS_JOINED) & set(syms) and syms.count("BRK-B") == 1       # EXTRA_US 의 BRK-B 와 겹쳐도 한 번
    assert names.sp500 == sp_yahoo()
    assert names["BF-B"] == "Brown–Forman" and names["BRK-B"] == "Berkshire Hathaway" and names["GOOGL"] == "Alphabet Inc. (Class A)"
    assert names.sym == {"mapped": sp_mapped(), "unmapped": []}
    assert f"· 미국 목록 티커를 야후 모양으로 바꿈 {len(sp_mapped())}개: " + " · ".join(f"S&P500 {a} → {b}" for _s, a, b in sp_mapped()) in lines
    assert not any("바꾸지 못해" in x for x in lines)


def test_us_tickers_names_every_unmappable_ticker_loudly(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    sp = listing(SP_ROWS + [(float("nan"), "Blank Row Inc."), ("BRK.B.X", "Odd")])
    nq = listing(NQ_ROWS + [("ÄBC", "Umlaut Corp")], nasdaq=True)
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR(sp, nq))
    names = F.UsListNames()
    syms = F.us_tickers(names)
    assert names.sym["unmapped"] == [["S&P500", "", "티커 칸이 비었거나 글자가 아님"], ["S&P500", "BRK.B.X", SHAPE],
                                     ["NASDAQ", "ÄBC", "티커에 영문이 아닌 글자"]]
    assert not {"BRK.B.X", "ÄBC", "BRK-B.X"} & set(syms) and "BF-B" in syms
    loud = [x for x in lines if x.startswith("  !! 미국 목록 티커를 야후 모양으로 바꾸지 못해 요청하지 않은 티커 3개")]
    assert len(loud) == 1 and "S&P500 'BRK.B.X'" in loud[0] and "NASDAQ 'ÄBC' (티커에 영문이 아닌 글자)" in loud[0]
    # 이름이 맞지 않는 붙은 꼴: 바꾸지 않고 크게 남겨요
    lines.clear()
    sp = listing([r if r[0] != "BFB" else ("BFB", "Big Fun Bancorp") for r in SP_ROWS])
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR(sp))
    names = F.UsListNames()
    syms = F.us_tickers(names)
    assert "BF-B" not in syms and "BFB" not in syms and "BF-B" not in names.sp500
    assert names.sym["unmapped"] == [["S&P500", "BFB", "점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"]]
    assert any(x.startswith("  !! 미국 목록 티커를 야후 모양으로 바꾸지 못해") and "S&P500 'BFB'" in x for x in lines)


@pytest.mark.parametrize("how", ["nan", "blank", "no-column"])
def test_us_tickers_never_maps_a_joined_form_without_its_list_name(monkeypatch, how):
    """리뷰 1: S&P 목록의 이름이 비었거나 (NaN · 빈 글자) 이름 칸이 아예 없으면 점이 지워진 꼴을 바꾸지 않고 이름을 남겨요 (BF-B 는 빠진 이유가
    붙어 관문이 경고 · BRK-B 는 EXTRA_US 로 그대로)."""
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    rows = [(k, float("nan") if how == "nan" else ("  " if how == "blank" else n)) if k in F.US_CLASS_JOINED else (k, n) for k, n in SP_ROWS]
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR(listing(rows, names=how != "no-column")))
    names = F.UsListNames()
    syms = F.us_tickers(names)
    assert not set(F.US_CLASS_ADDED) & set(syms) and not set(F.US_CLASS_JOINED) & set(syms) and "BRK-B" in syms
    assert names.sym["mapped"] == []
    assert names.sym["unmapped"] == [["S&P500", k, f"점이 지워진 주식 종류 표({k} → {F.US_CLASS_JOINED[k][0]}){NO_NAME}"]
                                     for k, _n in SP_ROWS if k in F.US_CLASS_JOINED]
    assert any(x.startswith("  !! 미국 목록 티커를 야후 모양으로 바꾸지 못해 요청하지 않은 티커") for x in lines)


def test_us_tickers_keeps_its_old_calling_shapes(monkeypatch):
    monkeypatch.setattr(F, "log", lambda *a: None)
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR())
    plain_names = {}
    F.us_tickers(plain_names)                                                     # dict 를 넘기면 이름만 (기록 칸 없음)
    assert plain_names["BF-B"] == "Brown–Forman" and not hasattr(plain_names, "sym")
    assert "BF-B" in F.us_tickers()                                               # 아무것도 안 넘겨도
    assert F.UsListNames().sym is None


# ── us_list_sym (순수 함수) ────────────────────────────────
def test_us_list_sym_reasons():
    rec = {"mapped": [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]], "unmapped": []}
    sp = frozenset({"AAPL", "BRK-B", "BF-B", "VYLR", "XYZA", "XYZ"})
    asked = set(sp) | {"SPY"}
    why = {"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)", "XYZA": F.US_NO_PX_WHY, "XYZ": "시세를 받지 못함 (KeyError)"}
    kept = {"AAPL", "SPY"} | set(F.US_CLASS_ADDED) | {"BRK-B"}
    u = F.us_list_sym(rec, sp, True, asked | set(F.US_CLASS_ADDED), kept, why)
    assert u == {"read": True, "mapped": rec["mapped"], "unmapped": [], "missing": {}, "spTickers": sorted(sp),
                 "noPx": ["XYZA"], "spErr": ["XYZ"],                                     # 리뷰 5: 가격 없음과 처리 중 오류는 따로
                 "spGone": {"VYLR": why["VYLR"], "XYZ": why["XYZ"], "XYZA": F.US_NO_PX_WHY}}
    # 믿지 못한 S&P 500 목록: 빠진 종목을 세지 않아요 (목록은 그대로 적어요)
    u = F.us_list_sym(rec, sp, False, asked, {"AAPL"}, why)
    assert u["spGone"] is None and u["noPx"] is None and u["spErr"] is None and u["spTickers"] == sorted(sp)
    assert u["missing"]["BF-B"] == "발행 목록에 없음 (빠진 까닭을 파이프라인이 적지 못했어요 — 확인 필요)"
    # 요청했는데 빠짐 · 목록을 못 읽음 · 목록에 없음 · 이름이 맞지 않음 · 이름이 없음 · 기록 없음
    assert F.us_list_sym(rec, sp, True, asked, set(), {"BF-B": "가격 이력 12일 (60일 미만이라 넣지 않아요)"})["missing"]["BF-B"] == \
        "가격 이력 12일 (60일 미만이라 넣지 않아요)"
    u = F.us_list_sym({"mapped": [], "unmapped": []}, None, False, {"SPY"}, set(), {})
    assert u["missing"]["BF-B"] == "S&P 500 목록을 읽지 못해 요청하지 않음" and u["spTickers"] is None
    assert F.us_list_sym({"mapped": [], "unmapped": []}, frozenset({"AAPL"}), True, {"AAPL"}, {"AAPL"}, {})["missing"]["BF-B"] == \
        "오늘 S&P 500 목록에 없음 (지수에서 빠졌는지 확인)"
    # 리뷰 2차 1: 지워진 꼴이 그대로 S&P 목록에 있으면 '지수에서 빠짐'이 아니라 바꾸기 문제라고 적어요 (요청했지만 가격이 없어 빠진 BFB)
    lost = F.us_list_sym({"mapped": [], "unmapped": []}, frozenset({"AAPL", "BFB"}), True, {"AAPL", "BFB"}, {"AAPL"}, {"BFB": F.US_NO_PX_WHY})
    assert lost["missing"]["BF-B"] == LOST and lost["noPx"] == ["BFB"]
    for note in ("점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'", f"점이 지워진 주식 종류 표(BFB → BF-B){NO_NAME}"):
        bad = {"mapped": [], "unmapped": [["S&P500", "BFB", note]]}
        assert F.us_list_sym(bad, frozenset({"AAPL"}), True, {"AAPL"}, {"AAPL"}, {})["missing"]["BF-B"] == \
            f"출처 티커를 야후 모양으로 바꾸지 못해 요청하지 않음 ({note})"
    u = F.us_list_sym(None, None, False, set(), set(), {})
    assert u["read"] is False and u["missing"]["BF-B"] == "출처 티커 기록이 없음 (미국 목록을 읽은 기록이 없어요 — 확인 필요)"
    json.dumps(u, allow_nan=False, ensure_ascii=False)


# ── fetch_us: 더한 종목이 발행 목록까지 ─────────────────────────
def _fake_yf(series, infos, asked_dl, splits=None):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"] if tickers != F.FX_TICKER else series["_spx"] * 0 + 1450.0})
        asked_dl.extend(tickers)
        cols = {}
        for t in tickers:
            if t not in series:
                continue                                                # 다운로드에 칸이 없음 → 처리 중 오류 (KeyError)
            cols[(t, "Close")] = series[t]                              # 빈 시계열 = 칸은 있는데 종가가 하나도 없음 (야후의 '가격 없음')
            cols[(t, "Dividends")] = pd.Series(0.0, index=series[t].index)
            sp = pd.Series(0.0, index=series[t].index)
            for d, r in (splits or {}).get(t, []):
                if pd.Timestamp(d) in sp.index:
                    sp[pd.Timestamp(d)] = r
            cols[(t, "Stock Splits")] = sp
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            return dict(infos[self.t])
    return types.SimpleNamespace(download=download, Ticker=Ticker)


PRICES = {"AAPL": 356.27, "BRK-B": 592.94, "BF-B": 30.65, "GOOGL": 284.78, "GOOG": 283.93, "FOXA": 60.1, "FOX": 55.2, "NWSA": 27.1,
          "NWS": 30.4, "FWONK": 98.0, "LLYVK": 90.0, "FCNCA": 2324.25}


def _fetch(tmp_path, monkeypatch, fdr=None, extra_px=None, short=None):
    today = dt.date(2026, 11, 15)
    days = pd.bdate_range(today - dt.timedelta(days=500), dt.date(2026, 11, 13))

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    prices = {y: 50.0 for y, _k in F.US_CLASS_JOINED.values()}                  # 표의 모든 종목에 가격 (줄을 더해도 이 시험이 그대로)
    prices.update(PRICES, **(extra_px or {}))
    series = {"_spx": walk(1, 6700.0), **{t: walk(i + 2, p) for i, (t, p) in enumerate(prices.items())}}
    series["VYLR"] = walk(99, 72.54).tail(32)                                   # 2026-10-01 상장 (32일 · 60일 미만)
    for t, n in (short or {}).items():
        series[t] = series[t].tail(n)
    infos = {t: plain(t + " Inc.") for t in series if t != "_spx"}
    infos.update({"BF-B": BFB_INFO, "BRK-B": BRKB_INFO})
    asked_dl = []
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series, infos, asked_dl,
                                                          splits={"BF-B": [("2016-08-19", 2.0), ("2018-03-01", 1.25)]}))
    monkeypatch.setitem(sys.modules, "FinanceDataReader", fdr or FakeFDR())
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: dt.date(2026, 11, 13))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    monkeypatch.setattr(F, "US_SP500_MIN", 5)                 # 가짜 S&P 500 목록은 10곳 남짓이라 겹침 기준을 작게 (실제 400)
    monkeypatch.setattr(V, "US_SP500_MIN", 5)
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    us, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03)
    meta.pop("_index")
    return us, meta, lines, asked_dl


def gate(meta, us, mode="publish"):
    rep = V.Report()
    V.check_us_share_class(rep, {"usListSym": meta["usListSym"]}, us, mode)
    return {r[0]: r for r in rep.rows}, rep


def test_fetch_us_brings_brown_forman_b_into_the_published_list(tmp_path, monkeypatch):
    us, meta, lines, asked_dl = _fetch(tmp_path, monkeypatch)
    by = {r["t"]: r for r in us}
    assert set(F.US_CLASS_ADDED) <= set(by) and "BRK-B" in by and not set(F.US_CLASS_JOINED) & set(by)
    assert not set(F.US_CLASS_JOINED) & set(asked_dl) and asked_dl.count("BF-B") == 1   # 야후에는 대시 꼴만 물어요
    bf = by["BF-B"]
    assert bf["price"] == 30.65 and bf["nk"] == "Brown Forman Inc" and bf["etf"] is False and bf["cls"] == "us"
    assert (bf["per"], bf["pbr"], bf["dy"]) == (19.8, 3.54, 3.01) and "fcur" not in bf and "fgnCut" not in bf
    assert bf["cap"] == round(14064189440 * 1450.0 / 1e12, 3)                         # 시가총액 조원 (그날 환율)
    u = meta["usListSym"]
    assert u == {"read": True, "mapped": sp_mapped(), "unmapped": [], "spTickers": sorted(sp_yahoo()),
                 "spGone": {"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"}, "noPx": [], "spErr": [], "missing": {}}
    # #133: S&P 500 회사로 세요 (외국 회사가 아님) · 겹침에 BF-B · BRK-B 가 들어가요
    assert meta["usForeign"]["sp500"] == {"n": len(SP_ROWS), "inList": len(SP_ROWS) - 1, "ok": True}
    assert "BF-B" not in meta["usForeign"]["set"]
    assert "BF-B" not in meta["usExtraMissing"] and "BRK-B" not in meta["usExtraMissing"]
    assert f"· 주식 종류 티커를 바꿔 들어온 미국 종목({', '.join(F.US_CLASS_ADDED)}) 중 오늘 목록에 없는 종목: 0개" in lines
    assert any(x.startswith("· S&P 500 목록 종목 중 오늘 목록에 없는 종목: 1개: VYLR (가격 이력 32일") for x in lines)
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(us, allow_nan=False, ensure_ascii=False)
    rows, _rep = gate(meta, us)
    assert rows[ROW1][1:] == (f"{N_ADDED} / {N_ADDED} 있음", TH1, "PASS")
    assert rows[ROW2][3] == "PASS" and f"바꿈 {len(sp_mapped())} (" in rows[ROW2][1] and "BFB → BF-B" in rows[ROW2][1]
    assert "S&P 500 중 오늘 없음 1: VYLR" in rows[ROW2][1]


def test_one_row_per_company_is_left_to_the_app_as_for_goog_and_googl(tmp_path, monkeypatch):
    """두 종류가 다 목록에 있으면 (GOOG · GOOGL, FOX · FOXA, NWS · NWSA) 파이프라인은 둘 다 실어요 — 목록의 '회사 하나에 한 줄'은 앱이 해요
    (engine.sameCompany: 같은 야후 짧은 이름 · 같은 전체 주식 수). 이번에 더한 BF-B 는 B 주식뿐이에요 (BF-A 는 두 출처 어디에도 없어요)."""
    us, meta, _lines, _dl = _fetch(tmp_path, monkeypatch)
    ts = {r["t"] for r in us}
    assert {"GOOG", "GOOGL", "FOX", "FOXA", "NWS", "NWSA"} <= ts and "BF-A" not in ts and "BRK-A" not in ts


def test_a_mismatched_name_leaves_bf_b_out_loudly_and_named(tmp_path, monkeypatch):
    sp = listing([r if r[0] != "BFB" else ("BFB", "Big Fun Bancorp") for r in SP_ROWS])
    us, meta, lines, asked_dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(sp))
    assert "BF-B" not in {r["t"] for r in us} and "BFB" not in asked_dl
    u = meta["usListSym"]
    assert u["unmapped"] == [["S&P500", "BFB", "점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"]]
    assert u["missing"]["BF-B"] == ("출처 티커를 야후 모양으로 바꾸지 못해 요청하지 않음 (점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 "
                                    "이름 'Big Fun Bancorp')")
    assert any(x.startswith("  !! 주식 종류 티커를 바꿔 들어온 미국 종목(") and "BF-B (" in x for x in lines)
    rows, rep = gate(meta, us)
    assert rows[ROW1][3] == "WARN" and rows[ROW1][1].startswith(f"{N_ADDED - 1} / {N_ADDED} 있음 · 빠짐 1: BF-B (출처 티커를")
    assert rows[ROW2][3] == "WARN" and "바꾸지 못함 1: S&P500 'BFB'" in rows[ROW2][1]
    assert ("야후 모양으로 바꾸지 못해 요청하지 않은 미국 목록 티커 (usListSym.unmapped)",
            ["S&P500 'BFB': 점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"]) in rep.details


def test_a_blank_list_name_leaves_bf_b_out_with_a_reason_and_the_gate_warns(tmp_path, monkeypatch):
    """리뷰 1: S&P 목록의 BFB 행에 이름이 없으면 (NaN) 바꾸지 않아요 — BF-B 는 빠진 이유와 함께 (관문 경고 · 실패 아님)."""
    sp = listing([r if r[0] != "BFB" else ("BFB", float("nan")) for r in SP_ROWS])
    us, meta, _lines, asked_dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(sp))
    assert "BF-B" not in {r["t"] for r in us} and "BFB" not in asked_dl
    assert meta["usListSym"]["missing"]["BF-B"] == f"출처 티커를 야후 모양으로 바꾸지 못해 요청하지 않음 (점이 지워진 주식 종류 표(BFB → BF-B){NO_NAME})"
    rows, _rep = gate(meta, us)
    assert rows[ROW1][3] == "WARN" and rows[ROW2][3] == "WARN"


def test_a_nasdaq_company_with_the_ticker_bfb_is_not_mistaken_for_brown_forman(tmp_path, monkeypatch):
    """리뷰 4: 진짜 회사가 'BFB' 를 쓰게 되어 나스닥 상위 400 에 들면, 그 회사는 그 티커 그대로 실리고 (S&P 목록의 BFB 는 BF-B 로) 관문은 막지 않아요
    — 날마다 발행이 막혀 사이트가 멈추지 않게. 관문 값 칸에 이름만 남아요."""
    nq = listing(NQ_ROWS + [("BFB", "Big Fun Bancorp")], nasdaq=True)
    us, meta, _lines, asked_dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(nq=nq), extra_px={"BFB": 12.0})
    ts = {r["t"] for r in us}
    assert {"BFB", "BF-B"} <= ts and asked_dl.count("BFB") == 1
    assert "BFB" not in meta["usListSym"]["spTickers"]
    rows, _rep = gate(meta, us)
    assert rows[ROW1][3] == "PASS" and rows[ROW2][3] == "PASS"
    assert "다른 출처의 같은 글자 티커 (S&P 500 목록 밖 · 다른 회사일 수 있어요): BFB" in rows[ROW2][1]
    rows, _rep = gate(meta, us, "live")
    assert rows[ROW2][3] == "PASS"


def test_an_unknown_joined_class_ticker_is_named_not_dropped_silently(tmp_path, monkeypatch):
    """S&P 500 에 새 주식 종류 티커가 들어와 점이 지워지면 (예: 'XYZ.A' → 'XYZA') 표에 없어 짐작하지 않고 그대로 물어요. 야후가 가격을 하나도 주지
    않으니 noPx 에 이름이 남고 관문이 경고해요 — 조용히 빠지지 않아요. 다운로드에 칸조차 없어 처리하다 멈춘 티커는 spErr 로 따로 (리뷰 5: '점이
    지워진 꼴일 수 있어요' 안내는 가격이 정말 없을 때만)."""
    sp = listing(SP_ROWS + [("XYZA", "Xyz Holdings (Class A)"), ("XYZB", "Xyz Holdings (Class B)")])
    us, meta, lines, asked_dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(sp), extra_px={"XYZA": 50.0}, short={"XYZA": 0})
    assert {"XYZA", "XYZB"} <= set(asked_dl) and not {"XYZA", "XYZB"} & {r["t"] for r in us}
    u = meta["usListSym"]
    assert u["noPx"] == ["XYZA"] and u["spGone"]["XYZA"] == F.US_NO_PX_WHY
    assert u["spErr"] == ["XYZB"] and u["spGone"]["XYZB"].startswith("시세를 받지 못함") and u["missing"] == {}
    assert any(x.startswith("  !! S&P 500 목록 종목인데 야후가 가격을 하나도 주지 않은 티커 1개: XYZA — 점이 지워진 주식 종류 티커일 수 있어요")
               for x in lines)
    err = [x for x in lines if x.startswith("  !! S&P 500 목록 종목인데 처리하다 오류로 멈춘 티커 1개: XYZB (시세를 받지 못함")]
    assert len(err) == 1 and "점이 지워진" not in err[0]
    rows, _rep = gate(meta, us)
    assert rows[ROW1][3] == "PASS" and rows[ROW2][3] == "WARN"
    assert "S&P 500 티커인데 야후 가격이 없음 1: XYZA (점이 지워진 새 주식 종류 티커일 수 있어요)" in rows[ROW2][1]
    assert "S&P 500 티커를 처리하다 오류 1: XYZB" in rows[ROW2][1]


@pytest.mark.parametrize("yahoo_answers", [False, True])
def test_a_lost_mapping_row_is_named_as_a_mapping_problem(tmp_path, monkeypatch, yahoo_answers):
    """리뷰 2차 1: 파이프라인 표에서 BFB 줄을 잃으면 S&P 목록의 'BFB' 가 그대로 야후에 가요. 야후는 그 티커를 모르니 보통 가격이 없어 빠지고 —
    BF-B 의 이유는 '지수에서 빠짐'이 아니라 '지워진 꼴로 있는데 바뀌지 않음', 관문은 BFB 를 이름으로 경고해요. 야후가 그 꼴에 다른 증권으로 답해
    엉뚱한 회사가 실리면 실패해요."""
    monkeypatch.delitem(F.US_CLASS_JOINED, "BFB")
    extra, short = ({"BFB": 12.0}, None) if yahoo_answers else ({"BFB": 1.0}, {"BFB": 0})
    us, meta, lines, asked_dl = _fetch(tmp_path, monkeypatch, extra_px=extra, short=short)
    ts = {r["t"] for r in us}
    u = meta["usListSym"]
    assert "BFB" in asked_dl and "BF-B" not in ts and "BFB" in u["spTickers"]
    assert u["missing"] == {"BF-B": LOST}
    assert any(x.startswith("  !! 주식 종류 티커를 바꿔 들어온 미국 종목(") and LOST in x for x in lines)
    rows, _rep = gate(meta, us)
    assert rows[ROW1][3] == "WARN" and f"BF-B ({LOST})" in rows[ROW1][1] and "지수에서 빠졌는지" not in rows[ROW1][1]
    assert "S&P 500 목록에 점이 지워진 꼴이 바뀌지 않고 그대로 있음 (바꾸기 확인 필요): BFB" in rows[ROW2][1]
    if yahoo_answers:                                                            # 엉뚱한 증권이 'BFB' 로 실렸어요: 실패 (발행 · 사이트 점검 모두)
        assert "BFB" in ts and rows[ROW2][3] == "FAIL" and "S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 목록에 있음: BFB" in rows[ROW2][1]
        assert gate(meta, us, "live")[0][ROW2][3] == "FAIL"
    else:                                                                        # 가격 없이 빠졌어요: 경고 (이름 · noPx)
        assert "BFB" not in ts and u["noPx"] == ["BFB"] and rows[ROW2][3] == "WARN"


def test_without_the_s_and_p_list_bf_b_is_named_and_brk_b_stays_through_extra_us(tmp_path, monkeypatch):
    us, meta, lines, _dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(fail={"S&P500"}))
    ts = {r["t"] for r in us}
    assert "BRK-B" in ts and "BF-B" not in ts                                       # EXTRA_US 가 BRK-B 의 바닥이에요 (그래서 손 목록에 그대로 둬요)
    u = meta["usListSym"]
    assert u["mapped"] == [] and u["spGone"] is None and u["noPx"] is None and u["spErr"] is None and u["spTickers"] is None
    assert u["missing"] == {t: "S&P 500 목록을 읽지 못해 요청하지 않음" for t in F.US_CLASS_ADDED}
    rows, _rep = gate(meta, us)
    assert rows[ROW1][3] == "WARN" and "BF-B (S&P 500 목록을 읽지 못해 요청하지 않음)" in rows[ROW1][1]
    assert rows[ROW2][3] == "PASS" and "S&P 500 목록을 믿지 못한 날" in rows[ROW2][1]


def test_bf_b_with_too_short_a_history_is_named_with_that_reason(tmp_path, monkeypatch):
    us, meta, _lines, _dl = _fetch(tmp_path, monkeypatch, short={"BF-B": 40})
    assert "BF-B" not in {r["t"] for r in us}
    assert meta["usListSym"]["missing"]["BF-B"] == "가격 이력 40일 (60일 미만이라 넣지 않아요)"
    assert meta["usListSym"]["spGone"]["BF-B"] == "가격 이력 40일 (60일 미만이라 넣지 않아요)"


def test_bf_b_split_history_is_read_as_a_new_stock(monkeypatch):
    """BF-B 는 시드에도 지난 발행본에도 없어 첫 실행이 2016년부터의 분할을 읽어요 (한 종목 · 상한 20 안). 2026-11-15 야후 분할 칸:
    2016-08-19 2:1 · 2018-03-01 5:4 (둘 다 깨끗한 배율 · 1.25 는 관문이 첫 발행에 한 번 '새 줄 정수 아닌 배율'로 경고해요)."""
    monkeypatch.setattr(F, "log", lambda *a: None)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    days = pd.bdate_range("2016-01-04", "2026-11-13")

    def download(codes, **kw):
        cols = {}
        for t in codes:
            cols[(t, "Close")] = pd.Series(30.0, index=days)
            sp = pd.Series(0.0, index=days)
            if t == "BF-B":
                sp[pd.Timestamp("2016-08-19")], sp[pd.Timestamp("2018-03-01")] = 2.0, 1.25
            cols[(t, "Stock Splits")] = sp
        return pd.DataFrame(cols)
    asked = []

    def history(codes, today):
        asked.append(list(codes))
        return F.fetch_split_history(codes, today, download=download, sleep=lambda s: None)
    seed = ({}, {"AAPL", "BRK-B"}, dt.date(2026, 11, 12))
    f = F.splits_fields(None, ["AAPL", "BRK-B", "BF-B"], [], [], dt.date(2025, 6, 1), dt.date(2026, 11, 15), seed=seed, history=history)
    assert asked == [["BF-B"]]
    assert ["BF-B", "2016-08-19", 2.0] in f["splits"] and ["BF-B", "2018-03-01", 1.25] in f["splits"] and f["splitsInfo"]["gap"] == []
    assert F.split_is_clean(1.25) and V.simple_ratio(1.25) and not V.whole_ratio(1.25)


# ── 관문 ─────────────────────────────────────────────────
def us_rows(extra=(), drop=()):
    rows = [{"t": t, "cls": "us", "price": 10.0} for t in sorted({"AAPL", "BRK-B", "GOOG", "GOOGL"} | V.US_CLASS_SET) if t not in drop]
    return rows + list(extra)


def rec(**kw):
    r = {"read": True, "mapped": [["S&P500", k, v] for k, v in V.US_CLASS_JOINED_SET.items()], "unmapped": [],
         "spTickers": sorted({"AAPL", "GOOG", "GOOGL"} | set(V.US_CLASS_JOINED_SET.values())), "spGone": {}, "noPx": [], "spErr": [], "missing": {}}
    r.update(kw)
    if "spTickers" not in kw and isinstance(r["spGone"], dict):                 # 파이프라인처럼: 빠진 S&P 종목은 그날 S&P 목록 안에 있어요
        r["spTickers"] = sorted(set(r["spTickers"]) | set(r["spGone"]))
    return r


def run(data, us, mode="publish"):
    rep = V.Report()
    V.check_us_share_class(rep, data, us, mode)
    return {r[0]: r for r in rep.rows}, rep


TH2 = ("S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 목록에 실리지 않음 · 바꾼 꼴이 관문 표와 같음 · 기록 모양 (사이트 점검에서는 표 · 모양은 경고) "
       "(바꾸지 않은 지워진 꼴 · 바꾸지 못한 티커 · 가격 없는 · 오류 난 S&P 500 티커는 경고)")


def test_gate_all_present_passes():
    rows, _ = run({"usListSym": rec()}, us_rows())
    assert rows[ROW1][1:] == (f"{N_ADDED} / {N_ADDED} 있음", TH1, "PASS")
    shown = " · ".join(f"{k} → {v}" for k, v in V.US_CLASS_JOINED_SET.items())
    assert rows[ROW2][1:] == (f"바꿈 {len(V.US_CLASS_JOINED_SET)} ({shown})", TH2, "PASS")


def test_gate_missing_with_a_reason_warns_by_name():
    rows, rep = run({"usListSym": rec(missing={"BF-B": "가격 이력 40일 (60일 미만이라 넣지 않아요)"})}, us_rows(drop={"BF-B"}))
    assert rows[ROW1][3] == "WARN" and rows[ROW1][1] == f"{N_ADDED - 1} / {N_ADDED} 있음 · 빠짐 1: BF-B (가격 이력 40일 (60일 미만이라 넣지 않아요))"
    assert ("주식 종류 티커로 들어온 미국 종목 중 오늘 없는 종목 (usListSym.missing)", ["BF-B: 가격 이력 40일 (60일 미만이라 넣지 않아요)"]) in rep.details


@pytest.mark.parametrize("why", [None, "", "  ", 3])
def test_gate_missing_without_a_reason_warns_but_a_listed_row_without_a_price_fails_to_publish(why):
    """Jack (2026-11-20): "Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish." 목록에 행이 없으면
    이유가 없어도 경고 (이름을 적어요). 행이 목록에 있는데 가격이 0 이면 틀린 값이 보여요 — 발행 실패 (예전 그대로) · 사이트 점검은 경고."""
    miss = {} if why is None else {"BF-B": why}
    for mode in ("publish", "live"):
        rows, rep = run({"usListSym": rec(missing=miss)}, us_rows(drop={"BF-B"}), mode)
        assert rows[ROW1][3] == "WARN" and "이유 없이 빠짐 1: BF-B" in rows[ROW1][1]
        assert ("주식 종류 티커로 들어온 미국 종목 중 오늘 없는 종목 (usListSym.missing)", ["BF-B: 이유 없음"]) in rep.details
    us = us_rows(drop={"BF-B"}, extra=[{"t": "BF-B", "cls": "us", "price": 0}])                  # 가격 0 인 행이 목록에 있음
    rows, _ = run({"usListSym": rec(missing=miss)}, us)
    assert rows[ROW1][3] == "FAIL" and "목록에 있는데 가격이 없음 1: BF-B" in rows[ROW1][1] and "이유 없이 빠짐" not in rows[ROW1][1]
    rows, _ = run({"usListSym": rec(missing=miss)}, us, "live")
    assert rows[ROW1][3] == "WARN"


def test_gate_without_the_record():
    rows, _ = run({}, us_rows(drop={"BF-B"}), "live")
    assert rows[ROW1][3] == "SKIP" and rows[ROW2][3] == "SKIP"
    rows, _ = run({}, us_rows(drop={"BF-B"}), "publish")
    assert rows[ROW1][3] == "WARN" and rows[ROW1][1] == "기록 없음 (data.json usListSym) · 오늘 없는 종목 1: BF-B"
    assert rows[ROW2][3] == "WARN" and rows[ROW2][1] == "기록 없음 (data.json usListSym)"
    rows, _ = run({}, us_rows(), "publish")
    assert rows[ROW1][3] == "WARN" and rows[ROW1][1] == "기록 없음 (data.json usListSym) · 오늘 없는 종목 0"


@pytest.mark.parametrize("mode", ["publish", "live"])
def test_gate_fails_a_joined_form_that_came_unmapped_from_the_s_and_p_list(mode):
    """'BFB' · 'BRKB' 는 야후에 없는 티커예요. 그날 S&P 500 목록(spTickers)에 그 꼴이 그대로 있고 그 티커로 실렸으면 바꾸기가 고장 났다는 뜻 —
    발행이든 사이트 점검이든 실패."""
    bad = us_rows(extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    rows, _ = run({"usListSym": rec(spTickers=sorted({"AAPL", "BFB", "BRK-B"}))}, bad, mode)
    assert rows[ROW2][3] == "FAIL" and "S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 목록에 있음: BFB" in rows[ROW2][1]


@pytest.mark.parametrize("mode", ["publish", "live"])
def test_gate_does_not_fail_a_same_letters_ticker_from_another_source(mode):
    """리뷰 4: 나스닥에서 온 'BFB' (그날 S&P 500 목록에 없음) 는 다른 회사일 수 있어요 — 실패도 경고도 아니고 이름만. 기록이 없는 파일에서는 출처를
    알 수 없어 경고 (실패 아님)."""
    other = us_rows(extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    rows, _ = run({"usListSym": rec()}, other, mode)
    assert rows[ROW2][3] == "PASS" and "다른 출처의 같은 글자 티커 (S&P 500 목록 밖 · 다른 회사일 수 있어요): BFB" in rows[ROW2][1]
    rows, _ = run({"usListSym": rec(spTickers=None, spGone=None, noPx=None, spErr=None)}, other, mode)   # S&P 목록을 못 읽은 날
    assert rows[ROW2][3] == "PASS"
    rows, _ = run({}, other, mode)
    assert rows[ROW2][3] == "WARN" and rows[ROW2][1].startswith("점이 지워진 꼴과 같은 티커가 목록에 있음 (출처 모름): BFB · 기록 없음")


@pytest.mark.parametrize("mode, status", [("publish", "FAIL"), ("live", "WARN")])
def test_gate_fails_a_mapping_that_differs_from_its_own_table(mode, status):
    rows, _ = run({"usListSym": rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BFB-X"]])}, us_rows(), mode)
    assert rows[ROW2][3] == status and "관문 표와 다르게 바꿈: BFB → BFB-X (관문 표 BF-B)" in rows[ROW2][1]


@pytest.mark.parametrize("mode", ["publish", "live"])
def test_gate_warns_when_a_joined_form_is_left_in_the_s_and_p_list(mode):
    """리뷰 2차 1: 그날 S&P 500 목록 티커(spTickers)에 지워진 꼴(BFB)이 그대로 있으면 — 실리지 않았어도 — 이름과 함께 경고해요 (바꾸기 표의 줄을
    잃었거나 바꾸기가 고장). 실렸으면 실패 (위 시험)."""
    rows, _ = run({"usListSym": rec(spTickers=sorted({"AAPL", "BFB", "BRK-B"}), spGone={"BFB": F.US_NO_PX_WHY}, noPx=["BFB"],
                                    missing={"BF-B": "S&P 500 목록에 점이 지워진 꼴 BFB 로 있는데 BF-B 로 바뀌지 않음"})},
                  us_rows(drop={"BF-B"}), mode)
    assert rows[ROW2][3] == "WARN" and "S&P 500 목록에 점이 지워진 꼴이 바뀌지 않고 그대로 있음 (바꾸기 확인 필요): BFB" in rows[ROW2][1]
    assert rows[ROW1][3] == "WARN" and "BF-B (S&P 500 목록에 점이 지워진 꼴 BFB 로 있는데 BF-B 로 바뀌지 않음)" in rows[ROW1][1]


@pytest.mark.parametrize("mode, status", [("publish", "FAIL"), ("live", "WARN")])
@pytest.mark.parametrize("field, value, what", [
    ("read", "yes", "read 가 참 · 거짓이 아님"), ("mapped", [["S&P500", "BRKB"]], "mapped 모양"), ("unmapped", {"x": 1}, "unmapped 모양"),
    ("missing", [], "missing 모양"), ("spTickers", "BFB", "spTickers 모양"), ("spGone", ["VYLR"], "spGone 모양"), ("noPx", "XYZA", "noPx 모양"),
    ("noPx", ["XYZA"], "noPx 가 spGone 안에 있지 않음"), ("noPx", None, "noPx 가 spGone 안에 있지 않음"), ("spErr", "XYZB", "spErr 모양"),
    ("spErr", ["XYZB"], "spErr 가 spGone 안에 있지 않음"), ("spErr", None, "spErr 가 spGone 안에 있지 않음"),
    ("spTickers", None, "spGone 이 있는데 spTickers 가 목록이 아님"), ("spTickers", ["AAPL"], "spGone 이 spTickers 안에 있지 않음")])
def test_gate_fails_a_broken_record_to_publish_and_warns_on_the_site(field, value, what, mode, status):
    """기록 모양이 틀리면 발행은 실패, 사이트 점검(live)은 경고 (리뷰 2차 3: 칸을 더하는 다음 PR 이 아직 살아 있는 예전 파일 때문에 배포 점검에서 막히지
    않게 — 이 줄은 이 PR 에서 새로 생겼어요). ('spTickers', ['AAPL']) 은 spGone 이 있을 때만 걸려요 (아래 spGone 을 채워요)."""
    kw = {field: value}
    if field == "spTickers" and value is not None:
        kw["spGone"] = {"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"}
    rows, _ = run({"usListSym": rec(**kw)}, us_rows(), mode)
    assert rows[ROW2][3] == status and what in rows[ROW2][1], rows[ROW2]


def test_a_record_without_s_and_p_tickers_cannot_switch_the_unmapped_check_off():
    """리뷰 2차 2: spGone 이 있는데 spTickers 가 없거나 비면, 'S&P 목록에서 바뀌지 않고 실린 꼴' 검사가 조용히 꺼질 수 있어요 — 기록 모양 실패로 잡아요."""
    bad = us_rows(extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    data = {"usListSym": rec(spGone={"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"})}
    del data["usListSym"]["spTickers"]
    rows, _ = run(data, bad)
    assert rows[ROW2][3] == "FAIL" and "spGone 이 있는데 spTickers 가 목록이 아님" in rows[ROW2][1]


def test_gate_fails_a_ticker_listed_as_both_no_price_and_error():
    rows, _ = run({"usListSym": rec(spGone={"XYZA": F.US_NO_PX_WHY}, noPx=["XYZA"], spErr=["XYZA"])}, us_rows())
    assert rows[ROW2][3] == "FAIL" and "noPx 와 spErr 가 겹침" in rows[ROW2][1]


def test_gate_warns_on_unmapped_tickers_no_price_or_error_s_and_p_tickers_and_a_run_without_the_record():
    rows, rep = run({"usListSym": rec(unmapped=[["NASDAQ", "ÄBC", "티커에 영문이 아닌 글자"]])}, us_rows())
    assert rows[ROW2][3] == "WARN" and "바꾸지 못함 1: NASDAQ 'ÄBC' (티커에 영문이 아닌 글자)" in rows[ROW2][1]
    gone = {"XYZA": F.US_NO_PX_WHY, "VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"}
    rows, rep = run({"usListSym": rec(spGone=gone, noPx=["XYZA"])}, us_rows())
    assert rows[ROW2][3] == "WARN" and "S&P 500 티커인데 야후 가격이 없음 1: XYZA (점이 지워진 새 주식 종류 티커일 수 있어요)" in rows[ROW2][1]
    assert ("S&P 500 목록 종목 중 오늘 미국 목록에 없는 종목 (usListSym.spGone)",
            [f"XYZA: {F.US_NO_PX_WHY}", "VYLR: 가격 이력 32일 (60일 미만이라 넣지 않아요)"]) in rep.details
    rows, _ = run({"usListSym": rec(spGone={"XYZB": "시세를 받지 못함 (KeyError)"}, spErr=["XYZB"])}, us_rows())
    assert rows[ROW2][3] == "WARN" and "S&P 500 티커를 처리하다 오류 1: XYZB" in rows[ROW2][1] and "점이 지워진 새" not in rows[ROW2][1]
    rows, _ = run({"usListSym": rec(spGone={"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"})}, us_rows())
    assert rows[ROW2][3] == "PASS" and "S&P 500 중 오늘 없음 1: VYLR (가격 이력 32일" in rows[ROW2][1]   # 새 상장은 이름만 (경고 아님)
    rows, _ = run({"usListSym": rec(read=False, mapped=[], spTickers=None, spGone=None, noPx=None, spErr=None)}, us_rows())
    assert rows[ROW2][3] == "WARN" and "출처 티커 기록이 없는 실행 (read false)" in rows[ROW2][1]
    rows, _ = run({"usListSym": rec(missing={"ZZZZ": "?"})}, us_rows())                     # 두 목록이 어긋나면 경고
    assert rows[ROW1][3] == "WARN" and "관문 목록에 없는 티커 1: ZZZZ" in rows[ROW1][1]


def test_the_rows_run_in_the_publish_gate():
    """run_checks 에 두 줄이 있어요. 기록이 없는 시험 데이터(이 칸 전 모양): 실패하지 않고 '기록 없음' 경고."""
    cur, prev, final = good_pair()
    rep = V.run_checks(cur, prev, final, dt.date(2026, 10, 31), mode="publish", count_between=lambda a, b: 1,
                       sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                       now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)
    rows = {r[0]: r for r in rep.rows}
    assert rows[ROW1][3] == "WARN" and rows[ROW2][3] == "WARN" and "기록 없음" in rows[ROW1][1]
