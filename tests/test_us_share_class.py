# -*- coding: utf-8 -*-
"""미국 주식 종류 티커 (Jack, 2026-11-15: "fix Brown-Forman B, then check every share-class ticker in the S&P 500 and NASDAQ sources (dots,
missing separators, A/B classes) and add any others missing for the same reason") — fetch_data.py us_symbol · us_tickers · us_list_sym ·
fetch_us(usListSym) 와 validate_data.py check_us_share_class. (네트워크 없음 · 더하기만)

- FinanceDataReader 의 S&P 500 목록(위키백과 표)은 점을 지워요: 'BRK.B' → 'BRKB' · 'BF.B' → 'BFB'. 야후에 그런 티커는 없어서 BF-B 는 목록에 한 번도
  없었고 BRK-B 는 EXTRA_US 로만 들어왔어요. 이제 us_symbol 이 근거를 확인한 표(US_CLASS_JOINED)로 야후 대시 꼴로 바꿔요 (끝 글자를 떼어 짐작하지
  않아요 · 목록 이름이 맞아야 해요). 점 · 빗금 · 띄어쓰기 꼴은 어느 출처든 대시로.
- 나스닥 목록(네이버)의 종류 티커(GOOGL · GOOG · FOXA · FOX · NWSA · NWS · FWONK · LLYVK …)는 나스닥 자기 티커 그대로라 야후와 같아요 (바꾸지 않아요).
- 바꾸지 못한 티커는 크게 남기고 기록(usListSym.unmapped)에 적어요 · S&P 500 목록 티커인데 야후가 가격을 하나도 주지 않으면 (점이 지워진 새 주식
  종류 티커의 모습) noPx 에 적고 관문이 경고해요.
- 관문: 이 바꾸기로 들어온 종목(BF-B)은 목록에 있거나 빠진 이유가 있어야 해요 (#126 의 EXTRA_US 줄과 같은 규칙).
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

ROW1 = "주식 종류 티커로 들어온 미국 종목 (BF-B): 목록에 있거나 빠진 이유"
ROW2 = "미국 목록 출처 티커 (주식 종류 · 점이 지워진 꼴)"

# 2026-11-15 FinanceDataReader StockListing("S&P500") 의 행 그대로 (위키백과 표의 BRK.B · BF.B 가 점이 지워진 채로)
SP_ROWS = [("AAPL", "Apple Inc."), ("BRKB", "Berkshire Hathaway"), ("BFB", "Brown–Forman"), ("GOOGL", "Alphabet Inc. (Class A)"),
           ("GOOG", "Alphabet Inc. (Class C)"), ("FOXA", "Fox Corporation (Class A)"), ("FOX", "Fox Corporation (Class B)"),
           ("NWSA", "News Corp (Class A)"), ("NWS", "News Corp (Class B)"), ("VYLR", "Vylor")]
# 2026-11-15 위키백과 표의 원래 꼴 (점) — FinanceDataReader 가 점을 지우지 않게 바뀌어도 같은 티커가 돼요
WIKI_DOTTED = [("BRK.B", "Berkshire Hathaway"), ("BF.B", "Brown–Forman")]
# 2026-11-15 FinanceDataReader StockListing("NASDAQ") (네이버) 의 행 그대로 — 나스닥 자기 티커 (상위 400 안: GOOGL · GOOG · FWONK · FOXA · FOX · NWSA ·
# LLYVK · GOOGM · 밖: NWS(431) · Z(436) · ZG(904) · FWONA(677) · LLYVA(673) · BATRK(656) · LBTYA · LBTYK · RUSHA · RUSHB · BELFB)
NQ_ROWS = [("GOOGL", "Alphabet Inc. Class A"), ("GOOG", "Alphabet Inc. Class C"), ("FWONK", "Liberty Media Formula One Ord Shs Series C"),
           ("FOXA", "Fox Corporation Class A"), ("FOX", "Fox Corporation Class B"), ("NWSA", "News Corporation Class A"),
           ("LLYVK", "Liberty Live Holdings Inc Series C")]
NQ_OUTSIDE = [("NWS", "News Corporation Class B"), ("Z", "Zillow Group  Inc. Class C"), ("ZG", "Zillow Group  Inc. Class A"),
              ("FWONA", "Liberty Media Formula One Ord Shs Series A"), ("LLYVA", "Liberty Live Holdings Inc Series A"),
              ("BATRK", "Liberty Media Liberty Braves Ord Shs Series C"), ("LBTYA", "Liberty Global Ltd Class A"),
              ("LBTYK", "Liberty Global Ltd Class C"), ("RUSHA", "Rush Enterprises  Inc. Class A"), ("RUSHB", "Rush Enterprises  Inc. Class B"),
              ("BELFB", "Bel Fuse Inc. Class B")]

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


def plain(short):
    return {"shortName": short, "longName": short, "quoteType": "EQUITY", "sector": "Communication Services", "industry": "Internet Content & Information",
            "financialCurrency": "USD", "currency": "USD", "country": "United States", "marketCap": 1e11, "averageVolume": 1e6,
            "longBusinessSummary": f"{short} does things."}


def listing(rows, nasdaq=False):
    if nasdaq:
        return pd.DataFrame({"Symbol": [r[0] for r in rows], "Name": [r[1] for r in rows], "IndustryCode": "0", "Industry": "x"})
    return pd.DataFrame({"Symbol": [r[0] for r in rows], "Name": [r[1] for r in rows], "Sector": "x", "Industry": "x"})


class FakeFDR:
    def __init__(self, sp=None, nq=None, fail=()):
        self.sp = listing(SP_ROWS) if sp is None else sp
        self.nq = listing(NQ_ROWS, nasdaq=True) if nq is None else nq
        self.fail = set(fail)

    def StockListing(self, name):
        if name in self.fail:
            raise RuntimeError("목록 실패 (시험)")
        return self.sp if name == "S&P500" else self.nq


# ── us_symbol: 출처에서 찾은 모든 꼴 ─────────────────────────
def test_the_two_joined_s_and_p_tickers_become_yahoo_dash_forms():
    assert F.us_symbol("BRKB", "S&P500", "Berkshire Hathaway") == ("BRK-B", "점이 지워진 S&P 500 표기 'BRKB' → BRK-B")
    assert F.us_symbol("BFB", "S&P500", "Brown–Forman") == ("BF-B", "점이 지워진 S&P 500 표기 'BFB' → BF-B")
    assert F.us_symbol("BFB", "S&P500", None)[0] == "BF-B"                       # 이름 칸이 없는 목록 (표의 근거로)
    for raw, nm in WIKI_DOTTED:                                                   # 위키백과의 점 꼴 그대로 와도
        y, note = F.us_symbol(raw, "S&P500", nm)
        assert y == {"BRK.B": "BRK-B", "BF.B": "BF-B"}[raw] and note == f"주식 종류 '{raw}' → 야후 대시 꼴 {y}"


def test_other_separators_become_the_dash_and_the_dash_stays():
    for raw in ("BRK.B", "BRK/B", "BRK B", "brk.b", " BRK-B ", "BRK-B"):
        assert F.us_symbol(raw, "NASDAQ")[0] == "BRK-B", raw
    assert F.us_symbol("BRK-B", "EXTRA_US") == ("BRK-B", None)                 # 이미 야후 꼴이면 메모 없음
    assert F.us_symbol("BF.A", "S&P500", "Brown–Forman") == ("BF-A", "주식 종류 'BF.A' → 야후 대시 꼴 BF-A")
    assert F.us_symbol("HEI.A", "NASDAQ")[0] == "HEI-A" and F.us_symbol("MOG/A", "S&P500")[0] == "MOG-A"


def test_class_tickers_that_already_match_yahoo_are_left_alone():
    """S&P 500 의 GOOGL · GOOG · FOXA · FOX · NWSA · NWS 와 나스닥 자기 종류 티커는 야후와 같은 꼴이에요 — 글자를 떼거나 붙이지 않아요."""
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
    assert F.us_symbol("MOGA", "S&P500", "Moog Inc. (Class A)") == ("MOGA", None)   # 표에 없는 꼴은 짐작하지 않아요
    y, note = F.us_symbol("BFB", "S&P500", "Big Fun Bancorp")
    assert y is None and note == "점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"


@pytest.mark.parametrize("raw, why", [
    (None, "티커 칸이 비었거나 글자가 아님"), (float("nan"), "티커 칸이 비었거나 글자가 아님"), ("", "티커 칸이 비었거나 글자가 아님"),
    ("   ", "티커 칸이 비었거나 글자가 아님"), ("ÄBC", "티커에 영문이 아닌 글자"),
    ("ABCDEF", "티커 모양이 아님 (영문 1~5자, 또는 그 뒤 점 · 빗금 · 띄어쓰기 · 대시와 종류 글자 1~2자)"),
    ("BRK.B.X", "티커 모양이 아님 (영문 1~5자, 또는 그 뒤 점 · 빗금 · 띄어쓰기 · 대시와 종류 글자 1~2자)"),
    ("A1B", "티커 모양이 아님 (영문 1~5자, 또는 그 뒤 점 · 빗금 · 띄어쓰기 · 대시와 종류 글자 1~2자)")])
def test_unmappable_tickers_come_back_with_a_reason(raw, why):
    assert F.us_symbol(raw, "S&P500") == (None, why)


def test_the_tables_agree_and_every_output_is_yahoo_shaped():
    assert F.US_CLASS_JOINED == {"BRKB": ("BRK-B", "berkshire"), "BFB": ("BF-B", "brownforman")}
    assert V.US_CLASS_JOINED_SET == {k: v[0] for k, v in F.US_CLASS_JOINED.items()}       # 관문은 따로 적어요 (같은 실수를 같이 하지 않게)
    assert F.US_CLASS_ADDED == ("BF-B",) and V.US_CLASS_SET == set(F.US_CLASS_ADDED)
    assert "BRK-B" in F.EXTRA_US and "BRK-B" in V.US_EXTRA_SET and len(F.EXTRA_US) == 67      # BRK-B 는 EXTRA_US 에 그대로 (S&P 목록을 못 읽는 날의 바닥)
    assert not set(F.US_CLASS_ADDED) & set(F.EXTRA_US)
    for raw, nm in SP_ROWS + WIKI_DOTTED + NQ_ROWS + NQ_OUTSIDE:
        y, _ = F.us_symbol(raw, "S&P500", nm)
        assert y is not None and F.US_SYM_YAHOO.fullmatch(y), raw
    for k, (y, key) in F.US_CLASS_JOINED.items():
        nm = dict(SP_ROWS)[k]
        assert F.us_symbol(k, "S&P500", nm)[0] == y and key in "".join(c for c in nm.lower() if "a" <= c <= "z")


# ── us_tickers: 실제 목록 모양 ──────────────────────────────
def test_us_tickers_maps_the_joined_forms_and_names_them(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR())
    names = F.UsListNames()
    syms = F.us_tickers(names)
    assert {"BRK-B", "BF-B", "GOOGL", "GOOG", "FOXA", "FOX", "NWSA", "NWS", "FWONK", "LLYVK", "VYLR"} <= set(syms)
    assert not {"BRKB", "BFB"} & set(syms) and syms.count("BRK-B") == 1                    # EXTRA_US 의 BRK-B 와 겹쳐도 한 번
    assert names.sp500 == frozenset({"AAPL", "BRK-B", "BF-B", "GOOGL", "GOOG", "FOXA", "FOX", "NWSA", "NWS", "VYLR"})
    assert names["BF-B"] == "Brown–Forman" and names["BRK-B"] == "Berkshire Hathaway" and names["GOOGL"] == "Alphabet Inc. (Class A)"
    assert names.sym == {"mapped": [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]], "unmapped": []}
    assert "· 미국 목록 티커를 야후 모양으로 바꿈 2개: S&P500 BRKB → BRK-B · S&P500 BFB → BF-B" in lines
    assert not any("바꾸지 못해" in x for x in lines)


def test_us_tickers_names_every_unmappable_ticker_loudly(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    sp = listing(SP_ROWS + [(float("nan"), "Blank Row Inc."), ("BRK.B.X", "Odd")])
    nq = listing(NQ_ROWS + [("ÄBC", "Umlaut Corp")], nasdaq=True)
    monkeypatch.setitem(sys.modules, "FinanceDataReader", FakeFDR(sp, nq))
    names = F.UsListNames()
    syms = F.us_tickers(names)
    un = names.sym["unmapped"]
    assert un == [["S&P500", "", "티커 칸이 비었거나 글자가 아님"],
                  ["S&P500", "BRK.B.X", "티커 모양이 아님 (영문 1~5자, 또는 그 뒤 점 · 빗금 · 띄어쓰기 · 대시와 종류 글자 1~2자)"],
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
    sp = frozenset({"AAPL", "BRK-B", "BF-B", "VYLR", "MOGA", "XYZ"})
    asked = set(sp) | {"SPY"}
    why = {"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)", "MOGA": F.US_NO_PX_WHY, "XYZ": "시세를 받지 못함 (KeyError)"}
    u = F.us_list_sym(rec, sp, True, asked, {"AAPL", "BRK-B", "BF-B", "SPY"}, why)
    assert u == {"read": True, "mapped": rec["mapped"], "unmapped": [], "missing": {}, "noPx": ["MOGA", "XYZ"],
                 "spGone": {"MOGA": F.US_NO_PX_WHY, "VYLR": why["VYLR"], "XYZ": why["XYZ"]}}
    # 믿지 못한 S&P 500 목록: 빠진 종목을 세지 않아요
    u = F.us_list_sym(rec, sp, False, asked, {"AAPL"}, why)
    assert u["spGone"] is None and u["noPx"] is None
    assert u["missing"] == {"BF-B": "발행 목록에 없음 (빠진 까닭을 파이프라인이 적지 못했어요 — 확인 필요)"}
    # 요청했는데 빠짐 · 목록을 못 읽음 · 목록에 없음 · 이름이 맞지 않음 · 기록 없음
    assert F.us_list_sym(rec, sp, True, asked, set(), {"BF-B": "가격 이력 12일 (60일 미만이라 넣지 않아요)"})["missing"] == \
        {"BF-B": "가격 이력 12일 (60일 미만이라 넣지 않아요)"}
    assert F.us_list_sym({"mapped": [], "unmapped": []}, None, False, {"SPY"}, set(), {})["missing"] == {"BF-B": "S&P 500 목록을 읽지 못해 요청하지 않음"}
    assert F.us_list_sym({"mapped": [], "unmapped": []}, frozenset({"AAPL"}), True, {"AAPL"}, {"AAPL"}, {})["missing"] == \
        {"BF-B": "오늘 S&P 500 목록에 없음 (지수에서 빠졌는지 확인)"}
    bad = {"mapped": [], "unmapped": [["S&P500", "BFB", "점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"]]}
    assert F.us_list_sym(bad, frozenset({"AAPL"}), True, {"AAPL"}, {"AAPL"}, {})["missing"]["BF-B"].startswith("출처 티커를 야후 모양으로 바꾸지 못해 요청하지 않음 (")
    u = F.us_list_sym(None, None, False, set(), set(), {})
    assert u["read"] is False and u["missing"] == {"BF-B": "출처 티커 기록이 없음 (미국 목록을 읽은 기록이 없어요 — 확인 필요)"}
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
                continue                                                # 야후가 그 종목을 주지 않음
            cols[(t, "Close")] = series[t]
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
          "NWS": 30.4, "FWONK": 98.0, "LLYVK": 90.0}


def _fetch(tmp_path, monkeypatch, fdr=None, extra_px=None, short=None):
    today = dt.date(2026, 11, 15)
    days = pd.bdate_range(today - dt.timedelta(days=500), dt.date(2026, 11, 13))

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    prices = dict(PRICES, **(extra_px or {}))
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
    monkeypatch.setattr(F, "US_SP500_MIN", 5)                 # 가짜 S&P 500 목록은 10곳이라 겹침 기준을 작게 (실제 400)
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
    assert "BF-B" in by and "BRK-B" in by and not {"BFB", "BRKB"} & set(by)
    assert not {"BFB", "BRKB"} & set(asked_dl) and asked_dl.count("BF-B") == 1      # 야후에는 대시 꼴만 물어요
    bf = by["BF-B"]
    assert bf["price"] == 30.65 and bf["nk"] == "Brown Forman Inc" and bf["etf"] is False and bf["cls"] == "us"
    assert (bf["per"], bf["pbr"], bf["dy"]) == (19.8, 3.54, 3.01) and "fcur" not in bf and "fgnCut" not in bf
    assert bf["cap"] == round(14064189440 * 1450.0 / 1e12, 3)                         # 시가총액 조원 (그날 환율)
    u = meta["usListSym"]
    assert u == {"read": True, "mapped": [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]], "unmapped": [],
                 "spGone": {"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"}, "noPx": [], "missing": {}}
    # #133: S&P 500 회사로 세요 (외국 회사가 아님) · 겹침에 BF-B · BRK-B 가 들어가요
    assert meta["usForeign"]["sp500"] == {"n": 10, "inList": 9, "ok": True} and "BF-B" not in meta["usForeign"]["set"]
    # 주식 분할: 오늘 다운로드의 분할 칸에서 (2016-01-01 부터의 이력은 splits_fields 가 새 종목으로 읽어요 — 아래 시험)
    assert "BF-B" not in meta["usExtraMissing"] and "BRK-B" not in meta["usExtraMissing"]
    assert "· 주식 종류 티커를 바꿔 들어온 미국 종목(BF-B) 중 오늘 목록에 없는 종목: 0개" in lines
    assert any(x.startswith("· S&P 500 목록 종목 중 오늘 목록에 없는 종목: 1개: VYLR (가격 이력 32일") for x in lines)
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(us, allow_nan=False, ensure_ascii=False)
    rows, _rep = gate(meta, us)
    assert rows[ROW1][1:] == ("1 / 1 있음", "모두 있어야 함 (빠지면 이유와 함께 경고 · 이유 없이 빠지면 실패)", "PASS")
    assert rows[ROW2][3] == "PASS" and "바꿈 2 (BRKB → BRK-B · BFB → BF-B)" in rows[ROW2][1] and "S&P 500 중 오늘 없음 1: VYLR" in rows[ROW2][1]


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
    assert u["missing"] == {"BF-B": "출처 티커를 야후 모양으로 바꾸지 못해 요청하지 않음 (점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 "
                                    "이름 'Big Fun Bancorp')"}
    assert any(x.startswith("  !! 주식 종류 티커를 바꿔 들어온 미국 종목(BF-B) 중 오늘 목록에 없는 종목: 1개: BF-B (") for x in lines)
    rows, rep = gate(meta, us)
    assert rows[ROW1][3] == "WARN" and rows[ROW1][1].startswith("0 / 1 있음 · 빠짐 1: BF-B (출처 티커를")
    assert rows[ROW2][3] == "WARN" and "바꾸지 못함 1: S&P500 'BFB'" in rows[ROW2][1]
    assert ("야후 모양으로 바꾸지 못해 요청하지 않은 미국 목록 티커 (usListSym.unmapped)",
            ["S&P500 'BFB': 점이 지워진 주식 종류 표(BFB → BF-B)의 회사가 아님: 목록 이름 'Big Fun Bancorp'"]) in rep.details


def test_an_unknown_joined_class_ticker_is_named_not_dropped_silently(tmp_path, monkeypatch):
    """S&P 500 에 새 주식 종류 티커가 들어와 점이 지워지면 (예: 'MOG.A' → 'MOGA') 표에 없어 짐작하지 않고 그대로 물어요. 야후가 가격을 하나도 주지
    않으니 noPx 에 이름이 남고 관문이 경고해요 — 조용히 빠지지 않아요."""
    sp = listing(SP_ROWS + [("MOGA", "Moog Inc. (Class A)")])
    us, meta, lines, asked_dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(sp))
    assert "MOGA" in asked_dl and "MOGA" not in {r["t"] for r in us}
    u = meta["usListSym"]
    assert u["noPx"] == ["MOGA"] and u["spGone"]["MOGA"].startswith("시세를 받지 못함") and u["missing"] == {}
    assert any(x.startswith("  !! S&P 500 목록 종목인데 야후가 가격을 하나도 주지 않은 티커 1개: MOGA — 점이 지워진 주식 종류 티커일 수 있어요")
               for x in lines)
    rows, rep = gate(meta, us)
    assert rows[ROW1][3] == "PASS" and rows[ROW2][3] == "WARN" and "S&P 500 티커인데 야후 가격이 없음 1: MOGA" in rows[ROW2][1]
    # 다운로드에 칸은 있는데 종가가 하나도 없는 경우 (야후 '빈 칸만')도 같아요
    us, meta, _l, _d = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(sp), extra_px={"MOGA": 50.0}, short={"MOGA": 0})
    assert meta["usListSym"]["noPx"] == ["MOGA"] and meta["usListSym"]["spGone"]["MOGA"] == F.US_NO_PX_WHY


def test_without_the_s_and_p_list_bf_b_is_named_and_brk_b_stays_through_extra_us(tmp_path, monkeypatch):
    us, meta, lines, _dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(fail={"S&P500"}))
    ts = {r["t"] for r in us}
    assert "BRK-B" in ts and "BF-B" not in ts                                       # EXTRA_US 가 BRK-B 의 바닥이에요 (그래서 손 목록에 그대로 둬요)
    u = meta["usListSym"]
    assert u["mapped"] == [] and u["spGone"] is None and u["noPx"] is None
    assert u["missing"] == {"BF-B": "S&P 500 목록을 읽지 못해 요청하지 않음"}
    rows, _rep = gate(meta, us)
    assert rows[ROW1][3] == "WARN" and "BF-B (S&P 500 목록을 읽지 못해 요청하지 않음)" in rows[ROW1][1]
    assert rows[ROW2][3] == "PASS" and "S&P 500 목록을 믿지 못한 날" in rows[ROW2][1]


def test_bf_b_with_too_short_a_history_is_named_with_that_reason(tmp_path, monkeypatch):
    us, meta, _lines, _dl = _fetch(tmp_path, monkeypatch, short={"BF-B": 40})
    assert "BF-B" not in {r["t"] for r in us}
    assert meta["usListSym"]["missing"] == {"BF-B": "가격 이력 40일 (60일 미만이라 넣지 않아요)"}
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
    rows = [{"t": t, "cls": "us", "price": 10.0} for t in ("AAPL", "BRK-B", "BF-B", "GOOG", "GOOGL") if t not in drop]
    return rows + list(extra)


def rec(**kw):
    r = {"read": True, "mapped": [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"]], "unmapped": [], "spGone": {}, "noPx": [], "missing": {}}
    r.update(kw)
    return r


def run(data, us, mode="publish"):
    rep = V.Report()
    V.check_us_share_class(rep, data, us, mode)
    return {r[0]: r for r in rep.rows}, rep


def test_gate_all_present_passes():
    rows, _ = run({"usListSym": rec()}, us_rows())
    assert rows[ROW1][1:] == ("1 / 1 있음", "모두 있어야 함 (빠지면 이유와 함께 경고 · 이유 없이 빠지면 실패)", "PASS")
    assert rows[ROW2][1:] == ("바꿈 2 (BRKB → BRK-B · BFB → BF-B)",
                              "점이 지워진 꼴이 목록에 없음 · 바꾼 꼴이 관문 표와 같음 (바꾸지 못한 티커 · 가격 없는 S&P 500 티커는 경고)", "PASS")


def test_gate_missing_with_a_reason_warns_by_name():
    rows, rep = run({"usListSym": rec(missing={"BF-B": "가격 이력 40일 (60일 미만이라 넣지 않아요)"})}, us_rows(drop={"BF-B"}))
    assert rows[ROW1][3] == "WARN" and rows[ROW1][1] == "0 / 1 있음 · 빠짐 1: BF-B (가격 이력 40일 (60일 미만이라 넣지 않아요))"
    assert ("주식 종류 티커로 들어온 미국 종목 중 오늘 없는 종목 (usListSym.missing)", ["BF-B: 가격 이력 40일 (60일 미만이라 넣지 않아요)"]) in rep.details


@pytest.mark.parametrize("why", [None, "", "  ", 3])
def test_gate_missing_without_a_reason_fails_to_publish_and_warns_on_the_site(why):
    miss = {} if why is None else {"BF-B": why}
    for us in (us_rows(drop={"BF-B"}), us_rows(drop={"BF-B"}, extra=[{"t": "BF-B", "cls": "us", "price": 0}])):   # 가격 0 도 빠진 것
        rows, _ = run({"usListSym": rec(missing=miss)}, us)
        assert rows[ROW1][3] == "FAIL" and "이유 없이 빠짐 1: BF-B" in rows[ROW1][1]
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
def test_gate_fails_a_joined_form_in_the_published_list(mode):
    """'BFB' · 'BRKB' 는 야후에 없는 티커예요. 그 꼴로 실린 종목은 바꾸기가 고장 났다는 뜻 (그날 야후가 다른 증권으로 답했을 수도) — 기록이 있든
    없든, 발행이든 사이트 점검이든 실패."""
    bad = us_rows(extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    rows, _ = run({"usListSym": rec()}, bad, mode)
    assert rows[ROW2][3] == "FAIL" and "점이 지워진 꼴이 목록에 있음: BFB" in rows[ROW2][1]
    rows, _ = run({}, bad, mode)
    assert rows[ROW2][3] == "FAIL" and rows[ROW2][1].startswith("점이 지워진 꼴이 목록에 있음: BFB · 기록 없음")


def test_gate_fails_a_mapping_that_differs_from_its_own_table():
    rows, _ = run({"usListSym": rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BFB-X"]])}, us_rows())
    assert rows[ROW2][3] == "FAIL" and "관문 표와 다르게 바꿈: BFB → BFB-X (관문 표 BF-B)" in rows[ROW2][1]


@pytest.mark.parametrize("field, value, what", [
    ("read", "yes", "read 가 참 · 거짓이 아님"), ("mapped", [["S&P500", "BRKB"]], "mapped 모양"), ("unmapped", {"x": 1}, "unmapped 모양"),
    ("missing", [], "missing 모양"), ("spGone", ["VYLR"], "spGone 모양"), ("noPx", "MOGA", "noPx 모양"),
    ("noPx", ["MOGA"], "noPx 가 spGone 안에 있지 않음"), ("noPx", None, "noPx 가 spGone 안에 있지 않음")])
def test_gate_fails_a_broken_record(field, value, what):
    rows, _ = run({"usListSym": rec(**{field: value})}, us_rows())
    assert rows[ROW2][3] == "FAIL" and what in rows[ROW2][1], rows[ROW2]


def test_gate_warns_on_unmapped_tickers_no_price_s_and_p_tickers_and_a_run_without_the_record():
    rows, rep = run({"usListSym": rec(unmapped=[["NASDAQ", "ÄBC", "티커에 영문이 아닌 글자"]])}, us_rows())
    assert rows[ROW2][3] == "WARN" and "바꾸지 못함 1: NASDAQ 'ÄBC' (티커에 영문이 아닌 글자)" in rows[ROW2][1]
    rows, rep = run({"usListSym": rec(spGone={"MOGA": F.US_NO_PX_WHY, "VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"}, noPx=["MOGA"])}, us_rows())
    assert rows[ROW2][3] == "WARN" and "S&P 500 티커인데 야후 가격이 없음 1: MOGA" in rows[ROW2][1]
    assert ("S&P 500 목록 종목 중 오늘 미국 목록에 없는 종목 (usListSym.spGone)",
            [f"MOGA: {F.US_NO_PX_WHY}", "VYLR: 가격 이력 32일 (60일 미만이라 넣지 않아요)"]) in rep.details
    rows, _ = run({"usListSym": rec(spGone={"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"})}, us_rows())
    assert rows[ROW2][3] == "PASS" and "S&P 500 중 오늘 없음 1: VYLR (가격 이력 32일" in rows[ROW2][1]   # 새 상장은 이름만 (경고 아님)
    rows, _ = run({"usListSym": rec(read=False, mapped=[], spGone=None, noPx=None)}, us_rows())
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
