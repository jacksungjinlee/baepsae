# -*- coding: utf-8 -*-
"""v19.6e (Part I.2, 데이터만): data.json c1w · wkFrom · usWkFrom — 이번 주 정리 (Part E) 가 쓰는 그 주 시작 종가.

스펙 (그대로): "each stock's close on the last trading day before its market's current week, from the same series as price (Korea
official closes; US the same Yahoo closes price uses). Meta wkFrom and usWkFrom (those dates). Blank when missing. [Q9] Korea's official
closes aren't split-adjusted, so the pipeline keeps last week's listed share count with c1w and blanks c1w when the count changed by more
than 20% (splits, 무상증자, big issues); log the count. US closes come from the same adjusted series as price, so splits are already
handled. Never a partial bar."

여기서 보는 것 (네트워크 없음 · 새 파일 · 예전 시험은 그대로):
1. 그 주 시작 날짜: 보통 주 · 금요일 휴장 · 월요일 기준일 · 한국과 미국의 주가 다른 날 · 해 넘김 · 휴장일 표와 맞춰 보기
2. 한국 주식: 그날 최종본 목록 파일의 공식 종가 · 주식 수 20% 넘게 바뀌면 빈 칸 (정확히 20% 는 남겨요) · KRX 기준가가 새로 정해지면 빈 칸
   (무상증자 권리락 — 주식 수로는 잡히지 않아요) · 실제 목록 파일 (2026-11-13 · 11-16) 로
3. 자기 가격 날짜 종목 (pxd · pxc · 금 추정) 은 빈 칸 · 그날 봉이 없으면 빈 칸 (앞 날 값을 쓰지 않아요) · NaN · 무한대는 쓰지 않아요
4. fetch_us (가짜 야후) → c1w_fields · fetch_kr_funds (가짜 시계열) · main 의 순서
5. 관문 줄: 통과 · 경고 · 절대 실패하지 않아요 (실제 하루치 사본으로도)
"""
import collections
import copy
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
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import fixture_data as FD  # noqa: E402

D = dt.date
HOL = F.load_market_holidays()
FX2 = os.path.join(ROOT, "tests", "fixtures", "kr_two_source")


def trade_days(mk, a, b):
    """휴장일 표대로의 거래일 (지수 일봉처럼)."""
    out, d = [], a
    while d <= b:
        if d.weekday() < 5 and d not in HOL[mk]:
            out.append(pd.Timestamp(d))
        d += dt.timedelta(days=1)
    return out


def week(mk, px):
    return F.c1w_week(px, trade_days(mk, px - dt.timedelta(days=40), px))


# ── 1. 그 주 시작 날짜 ─────────────────────────────────────────────────────────
def test_normal_week_monday_price_date_and_friday_holiday():
    assert week("KR", D(2026, 11, 20)) == (D(2026, 11, 13), None)            # 금요일 기준일 → 앞 주 금요일
    assert week("KR", D(2026, 11, 18)) == (D(2026, 11, 13), None)            # 주 가운데
    assert week("KR", D(2026, 11, 16)) == (D(2026, 11, 13), None)            # 월요일 기준일 → 앞 주 금요일 (그 주는 월요일 하루)
    assert week("KR", D(2026, 10, 16)) == (D(2026, 10, 8), None)             # 10-09 (금) 한글날 휴장 → 목요일
    assert week("US", D(2027, 4, 1)) == (D(2027, 3, 25), None)               # 2027-03-26 (금) Good Friday → 목요일
    assert week("US", D(2026, 11, 27)) == (D(2026, 11, 20), None)            # 추수감사절 주: 앞 주 금요일 (11-26 은 그 주 안)


def test_us_and_korean_weeks_can_differ():
    """한국 기준일이 월요일 · 미국 기준일이 앞 금요일인 아침 (월요일 한국 장 뒤 · 미국 월요일 장 전): 둘의 주가 달라요."""
    assert week("KR", D(2026, 11, 23)) == (D(2026, 11, 20), None)
    assert week("US", D(2026, 11, 20)) == (D(2026, 11, 13), None)


def test_year_boundary():
    assert week("KR", D(2027, 1, 4)) == (D(2026, 12, 30), None)             # 12-31 연말 휴장 · 1-1 신정
    assert week("KR", D(2027, 1, 8)) == (D(2026, 12, 30), None)             # 9일 앞 (C1W_FROM_MAX_DAYS 12 안)
    assert week("US", D(2027, 1, 4)) == (D(2026, 12, 31), None)             # NYSE 는 12-31 에 열어요


def test_bad_calendars_give_no_date():
    assert F.c1w_week(None, []) == (None, "noPx")
    assert F.c1w_week(D(2026, 11, 20), [pd.Timestamp("2026-11-20")]) == (None, "noDay")
    gap = [t for t in trade_days("KR", D(2026, 10, 1), D(2026, 11, 20)) if not (D(2026, 11, 2) <= t.date() <= D(2026, 11, 13))]
    assert F.c1w_week(D(2026, 11, 20), gap) == (None, "far")                 # 두 주가 빠진 일봉 → 10-30 은 21일 앞
    assert F.c1w_week(D(2026, 11, 20), [pd.Timestamp("2026-11-14"), pd.Timestamp("2026-11-20")]) == (None, "weekend")


def test_holiday_table_catches_a_missing_index_day_and_a_holiday_bar():
    st, end = HOL["start"], HOL["end"]
    assert F.c1w_table_why(D(2026, 11, 13), D(2026, 11, 20), HOL["KR"], st, end) == []
    assert F.c1w_table_why(D(2026, 11, 12), D(2026, 11, 20), HOL["KR"], st, end) == [D(2026, 11, 13)]   # 일봉이 금요일을 빠뜨림
    assert F.c1w_table_why(D(2026, 10, 9), D(2026, 10, 16), HOL["KR"], st, end) == [D(2026, 10, 9)]     # 한글날의 봉
    assert F.c1w_table_why(D(2026, 10, 8), D(2026, 10, 16), HOL["KR"], st, end) == []
    assert F.c1w_table_why(D(2026, 11, 12), D(2026, 11, 20), HOL["KR"], st, None) == []                 # 표가 없으면 보지 않아요
    assert F.c1w_table_why(D(2028, 1, 6), D(2028, 1, 14), HOL["KR"], st, end) == []                    # 표 밖 날짜도
    # 관문의 따로 된 계산도 같은 날을 말해요
    vh, vend = V.load_holidays()
    for mk, px, want in (("KR", D(2026, 10, 16), D(2026, 10, 8)), ("KR", D(2027, 1, 4), D(2026, 12, 30)),
                         ("US", D(2027, 4, 1), D(2027, 3, 25)), ("US", D(2027, 1, 4), D(2026, 12, 31))):
        assert V.c1w_week_expect(px, vh[mk], vh["start"], vend) == want == week(mk, px)[0]


def test_whole_market_blank_when_the_table_disagrees():
    kr_wk = {"date": "2026-11-12", "px": "2026-11-20", "why": None, "close": {"005930": 100.0}, "shr": {"005930": 10.0}, "ref": {}}
    us_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"AAPL": 10.0}}
    st = [{"t": "005930", "cls": "kr", "price": 101.0, "shr": 10}, {"t": "AAPL", "cls": "us", "price": 11.0},
          {"t": "069500", "cls": "kr", "fund": True, "price": 5.0, "c1w": 4.0}]
    meta, info = F.c1w_apply(st, kr_wk, us_wk, HOL)
    assert meta == {"wkFrom": None, "usWkFrom": "2026-11-13"}
    assert "c1w" not in st[0] and "c1w" not in st[2] and st[1]["c1w"] == 10.0
    assert info["wk"]["kr"] == (None, "table", ["2026-11-13"]) and info["kr"]["why"]["week"] == 1 and info["fund"]["why"]["week"] == 1


# ── 2. 한국 주식: 그날 최종본 목록 파일 · 주식 수 · KRX 기준가 ─────────────────────────────────────
def listing(name):
    return F.parse_listing_csv(open(os.path.join(FX2, f"krx_{name}.csv"), encoding="utf-8").read())


D13, D16 = D(2026, 11, 13), D(2026, 11, 16)
TD = trade_days("KR", D(2026, 10, 1), D16)


def kr_rows(df):
    """fetch_korea 가 만드는 행의 c1w 에 쓰는 칸 (가격 = 공식 종가 · shr = 오늘 상장주식수)."""
    return [{"t": str(r["Code"]).strip(), "nk": str(r["Name"]), "cls": "kr", "price": F.kr_official_close(r), "shr": int(r["Stocks"])}
            for _, r in df.iterrows()]


def kr_run(df16, df13=None, sessions=None):
    df13 = listing("2026-11-13_2158") if df13 is None else df13
    sessions = [(D13, df13)] if sessions is None else sessions
    ref_by_day, _ = F.kr_ref_links([(D16, df16)] + sessions, TD, set(df16["Code"].astype(str).str.strip()))
    kr_wk = F.kr_week_closes(D16, TD, sessions, ref_by_day)
    rows = kr_rows(df16)
    meta, info = F.c1w_apply(rows, kr_wk, None, HOL)
    return {r["t"]: r for r in rows}, meta, info, kr_wk


def test_real_listing_files_give_the_official_close_of_that_day():
    df13, df16 = listing("2026-11-13_2158"), listing("2026-11-16_2211")
    by, meta, info, kr_wk = kr_run(df16)
    want = {str(r["Code"]).strip(): F.kr_official_close(r) for _, r in df13.iterrows()}
    assert meta["wkFrom"] == "2026-11-13" and kr_wk["why"] is None
    assert by["005930"]["c1w"] == 206000.0 == want["005930"] and by["005930"]["price"] == 196800.0
    for t, r in by.items():
        if t != "047400":
            assert r.get("c1w") == want.get(t), t                              # 그날 공식 종가 그대로
    # 실제 주식병합 (유니온머티리얼 5:1 — 4,200만 → 840만 주 · 11-13 종가 746원 · 11-16 기준가 3,730원): 비워요 (가짜 +326% 가 나가지 않게)
    assert "c1w" not in by["047400"] and info["kr"]["base"] == [("047400", "유니온머티리얼")]
    assert info["kr"]["ok"] == len(by) - 1 and info["kr"]["why"] == collections.Counter({"base": 1})
    old = F.C1W_BASE_BLANK
    try:
        F.C1W_BASE_BLANK = False
        by2, _, info2, _ = kr_run(df16)
    finally:
        F.C1W_BASE_BLANK = old
    assert "c1w" not in by2["047400"] and info2["kr"]["shr"] == [("047400", "유니온머티리얼", 42000000.0, 8400000.0)]   # 주식 수 규칙도 잡아요


def _set(df, code, **kw):
    df = df.copy()
    i = df.index[df["Code"].astype(str).str.strip() == code][0]
    for k, v in kw.items():
        df.at[i, k] = v
    return df


def test_share_count_rule_more_than_20_percent_blanks_exactly_20_keeps():
    """현대차 · KB금융: 주식 수만 바뀌고 (공식 종가 · KRX 기준가 연결은 그대로) — 정확히 20% 는 남기고 20% + 1주는 비워요 (정수로 비교).
    늘어도 줄어도 같은 규칙이에요."""
    df13 = _set(listing("2026-11-13_2158"), "005380", Stocks=203466490, Marcap=269500 * 203466490)   # 5 로 나눠떨어지는 주식 수 (공식 종가 그대로)
    up20 = 203466490 + 203466490 // 5                                                                 # 정확히 +20%
    k0 = int(df13.loc[df13["Code"] == "105560", "Stocks"].iloc[0])
    df16 = _set(listing("2026-11-16_2211"), "005380", Stocks=up20, Marcap=265500 * up20)
    df16 = _set(df16, "105560", Stocks=k0 + k0 // 5 + 1, Marcap=161600 * (k0 + k0 // 5 + 1))
    by, meta, info, _ = kr_run(df16, df13)
    assert by["005380"]["c1w"] == 269500.0 and by["005380"]["price"] == 265500.0   # 정확히 20% → 남겨요
    assert "c1w" not in by["105560"]                                               # 20% 넘음 → 비워요
    assert [x[0] for x in info["kr"]["shr"]] == ["105560"] and info["kr"]["why"]["shr"] == 1
    down = 203466490 - 203466490 // 5                                              # 정확히 −20% → 남겨요 · 1주 더 줄면 비워요
    for n, kept in ((down, True), (down - 1, False)):
        by, _, _, _ = kr_run(_set(listing("2026-11-16_2211"), "005380", Stocks=n, Marcap=265500 * n), df13)
        assert ("c1w" in by["005380"]) is kept, n


def test_unknown_share_count_blanks():
    by, _, info, _ = kr_run(listing("2026-11-16_2211"))
    rows = [dict(by["005930"]), dict(by["000660"])]
    rows[0].pop("shr")
    kw = F.kr_week_closes(D16, TD, [(D13, listing("2026-11-13_2158"))], {})
    F.c1w_apply(rows, kw, None)
    assert "c1w" not in rows[0] and rows[1]["c1w"] == 1216000.0


def test_split_and_bonus_issue_are_blanked_by_the_base_reset():
    """2:1 분할 (주식 수 두 배 · 기준가 반) 과 무상증자 권리락 (가격이 반이 됐는데 새 주식은 아직 상장 전 — 주식 수 그대로) 둘 다 비워요.
    무상증자 주는 주식 수 규칙만으로는 잡히지 않아요 → C1W_BASE_BLANK (스펙보다 엄하게만)."""
    df16 = listing("2026-11-16_2211")
    s = int(df16.loc[df16["Code"] == "005930", "Stocks"].iloc[0])
    df16 = _set(df16, "005930", Stocks=2 * s, Marcap=98400 * 2 * s, Close=98400, Changes=-4600)      # 분할: 기준가 103,000 ≠ 206,000
    h = int(df16.loc[df16["Code"] == "000660", "Stocks"].iloc[0])
    df16 = _set(df16, "000660", Marcap=560000 * h, Close=560000, Changes=-48000)                      # 권리락: 기준가 608,000 · 주식 수 그대로
    by, _, info, _ = kr_run(df16)
    assert "c1w" not in by["005930"] and "c1w" not in by["000660"]
    assert sorted(t for t, _ in info["kr"]["base"]) == ["000660", "005930", "047400"] and info["kr"]["why"]["base"] == 3   # 047400: 실제 병합
    assert by["005380"]["c1w"] == 269500.0
    # 스위치를 끄면 무상증자 주의 가짜 −54% 가 나가요 (그래서 켜 둬요)
    old = F.C1W_BASE_BLANK
    try:
        F.C1W_BASE_BLANK = False
        by2, _, _, _ = kr_run(df16)
    finally:
        F.C1W_BASE_BLANK = old
    assert by2["000660"]["c1w"] == 1216000.0 and round(by2["000660"]["price"] / by2["000660"]["c1w"] - 1, 2) == -0.54
    assert "c1w" not in by2["005930"]                                          # 분할은 주식 수 규칙으로도 잡혀요


def test_no_final_file_for_that_day_blanks_korea_only_and_keeps_the_date():
    df16 = listing("2026-11-16_2211")
    by, meta, info, kr_wk = kr_run(df16, sessions=[])                          # 11-13 파일이 최종본이 아니었던 날
    assert kr_wk["why"] == "file" and meta["wkFrom"] == "2026-11-13" and not any("c1w" in r for r in by.values())
    fund = {"t": "069500", "cls": "kr", "fund": True, "price": 5.0, "c1w": 4.0}
    F.c1w_apply([fund], kr_wk, None, HOL)
    assert fund["c1w"] == 4.0                                                  # 채권 · ETF · 금은 그 날짜의 시계열 봉 그대로
    # 지수 일봉이 빠뜨린 거래일: 그날과 월요일 사이에 최종본 목록 파일이 있으면 날짜를 쓰지 않아요
    td = [t for t in TD if t.date() != D13]
    kw = F.kr_week_closes(D16, td, [(D13, listing("2026-11-13_2158"))], {})
    assert kw["date"] is None and kw["why"] == "later" and kw["later"] == ["2026-11-13"]


# ── 3. 자기 가격 날짜 · 빈 봉 · NaN ──────────────────────────────────────────────────────────
def test_own_date_rows_are_blank_even_inside_the_week():
    kr_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"A": 100.0, "B": 100.0}, "shr": {"A": 10.0, "B": 10.0}, "ref": {}}
    us_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"X": 10.0, "Y": 10.0, "Z": 10.0}}
    st = [{"t": "A", "cls": "kr", "price": 110.0, "shr": 10},
          {"t": "B", "cls": "kr", "price": 120.0, "shr": 10, "pxd": "2026-11-18"},          # 2차 출처 날의 마지막 확인 종가 (그 주 안)
          {"t": "X", "cls": "us", "ccy": "USD", "price": 11.0},
          {"t": "Y", "cls": "us", "ccy": "USD", "price": 12.0, "pxd": "2026-11-19", "pxc": True},
          {"t": "Z", "cls": "us", "ccy": "USD", "price": 13.0, "pxd": "2026-11-10"},          # 거래 정지 (그 주 앞)
          {"t": "04020000", "cls": "metal", "fund": True, "price": 200000.0, "est": True, "c1w": 190000.0}]
    meta, info = F.c1w_apply(st, kr_wk, us_wk, HOL)
    by = {s["t"]: s for s in st}
    assert by["A"]["c1w"] == 100.0 and by["X"]["c1w"] == 10.0
    assert all("c1w" not in by[t] for t in ("B", "Y", "Z", "04020000"))
    assert info["kr"]["why"]["own"] == 1 and info["us"]["why"]["own"] == 2 and info["fund"]["why"]["est"] == 1
    assert (info["kr"]["px"], info["us"]["px"], info["fund"]["px"]) == (1, 1, 0)


def test_missing_bar_is_blank_never_an_earlier_day():
    idx = pd.to_datetime(["2026-11-11", "2026-11-12", "2026-11-16", "2026-11-17"])
    px = pd.Series([10.0, 11.0, 12.0, 13.0], index=idx)
    assert F.c1w_at(px, "2026-11-13") is None and F.c1w_at(px, D(2026, 11, 12)) == 11.0
    for bad in (np.nan, np.inf, -np.inf, 0.0, -1.0):
        assert F.c1w_at(pd.Series([bad], index=pd.to_datetime(["2026-11-13"])), "2026-11-13") is None
    dup = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-11-13", "2026-11-13"]))
    assert F.c1w_at(dup, "2026-11-13") is None                                # 같은 날 봉이 둘이면 어느 것도 쓰지 않아요
    assert F.c1w_at(px, None) is None and F.c1w_at(pd.Series(dtype=float), "2026-11-13") is None
    us_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {}}
    st = [{"t": "NEW", "cls": "us", "price": 5.0}]
    F.c1w_apply(st, None, us_wk)
    assert "c1w" not in st[0]


def test_nan_and_infinity_are_never_written(tmp_path, monkeypatch):
    kr_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"A": float("nan"), "B": float("inf"), "C": 0.0, "D": 100.0},
             "shr": {k: 10.0 for k in "ABCD"}, "ref": {}}
    st = [{"t": t, "cls": "kr", "price": 101.0, "shr": 10} for t in "ABCD"]
    st += [{"t": "F1", "cls": "bond", "price": 1.0, "c1w": float("nan")}, {"t": "F2", "cls": "bond", "price": 1.0, "c1w": float("-inf")}]
    meta, info = F.c1w_apply(st, kr_wk, None, HOL)
    assert [s.get("c1w") for s in st] == [None, None, None, 100.0, None, None]
    assert info["kr"]["why"]["bad"] == 3 and info["fund"]["why"]["bad"] == 2
    json.dumps({"stocks": st, **meta}, allow_nan=False)
    monkeypatch.setattr(F, "log", lambda *a: None)
    assert F.write_json(str(tmp_path / "d.json"), {"stocks": st, **meta}) == 0


def test_logs_name_counts_and_reasons(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    kr_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"A": 100.0, "B": 100.0, "C": 100.0},
             "shr": {"A": 10.0, "B": 10.0, "C": 10.0}, "ref": {"C": "break"}}
    us_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"X": 10.0}}
    st = [{"t": "A", "nk": "가", "cls": "kr", "price": 101.0, "shr": 10}, {"t": "B", "nk": "나", "cls": "kr", "price": 101.0, "shr": 30},
          {"t": "C", "nk": "다", "cls": "kr", "price": 50.0, "shr": 10}, {"t": "X", "cls": "us", "price": 11.0}]
    meta = F.c1w_fields(st, kr_wk, us_wk, HOL)
    assert meta == {"wkFrom": "2026-11-13", "usWkFrom": "2026-11-13"}
    text = "\n".join(lines)
    assert lines[0].startswith("  !! c1w (이번 주 정리 · 그 시장의 이번 주 앞 마지막 거래일 종가): 국내 1 / 3 (wkFrom 2026-11-13) · "
                               "미국 1 / 1 (usWkFrom 2026-11-13) · 채권·ETF·금 0 / 0"), lines[0]   # 국내 33% → 크게
    assert "c1w 국내 빈 칸 2: 그 사이 KRX 기준가가 새로 정해짐 (분할 · 병합 · 감자 · 권리락) 1 · 상장 주식 수가 20% 넘게 바뀜 (또는 모름) 1" in text
    assert "· c1w 주식 수 20% 넘게 바뀌어 비움: 1 / 3 — B 나 (10 → 30주)" in text
    assert "· c1w KRX 기준가가 그 사이 새로 정해져 비움 (분할 · 병합 · 감자 · 권리락 · 무상증자): 1 / 3 — C 다" in text
    lines.clear()
    F.c1w_fields([{"t": "A", "cls": "kr", "price": 101.0, "shr": 10}], dict(kr_wk, ref={}), us_wk, HOL)
    assert lines[0].startswith("· c1w") and "· c1w 주식 수 20% 넘게 바뀌어 비움: 0 / 1" in lines        # 0 이어도 적어요


def test_a_crash_blanks_everything_and_says_so(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    st = [{"t": "A", "cls": "kr", "price": 1.0, "c1w": 1.0}, {"t": "X", "cls": "us", "price": 1.0, "c1w": 2.0}]
    assert F.c1w_fail(st, ValueError("x")) == {"wkFrom": None, "usWkFrom": None}
    assert not any("c1w" in s for s in st) and lines[0].startswith("  !! c1w 단계가 오류로 멈췄어요 (ValueError: x)")


# ── 4. fetch_us (가짜 야후) → c1w_fields · 채권 · ETF · 금 · main 의 순서 ─────────────────────────────
INFO = {"shortName": "Co", "longName": "Co Inc.", "quoteType": "EQUITY", "sector": "Technology", "industry": "Software",
        "financialCurrency": "USD", "currency": "USD", "trailingPE": 20.0, "priceToBook": 4.0, "marketCap": 1e11, "averageVolume": 1e6,
        "country": "United States", "dividendYield": 0.5}


def _fake_yf(series):
    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"]})
        cols = {}
        for t in tickers:
            if t in series:
                cols[(t, "Close")] = series[t]
                cols[(t, "Dividends")] = pd.Series(0.0, index=series[t].index)
                cols[(t, "Stock Splits")] = pd.Series(0.0, index=series[t].index)
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            return dict(INFO, shortName=self.t + " Co")
    return types.SimpleNamespace(download=download, Ticker=Ticker)


def test_fetch_us_records_the_week_start_bar_and_c1w_fields_applies_it(tmp_path, monkeypatch):
    today_us = D(2026, 11, 19)                                                 # 목요일 → 그 주 월요일 11-16 → usWkFrom 11-13
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)
    rnd = np.random.default_rng(3)
    walk = lambda last: pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days) * last
    series = {"_spx": walk(6700.0)}
    for t in ("AAPL", "MSFT", "NVDA", "SHEL", "HALT"):
        series[t] = walk(100.0)
    series["MSFT"].iloc[-1] = np.nan                                           # 기준일 봉 없음 → 지난 발행본의 마지막 확인 종가 (pxc)
    series["NVDA"].loc[pd.Timestamp("2026-11-13")] = np.nan                    # 그 주 시작 봉만 없음 → 빈 칸 (11-12 값을 쓰지 않아요)
    series["HALT"].loc[series["HALT"].index > pd.Timestamp("2026-11-17")] = np.nan   # 거래 정지 (자기 날짜 11-17)
    prev = {"pxDate": "2026-11-18", "usPxDate": "2026-11-18",
            "stocks": [{"t": "MSFT", "nk": "MSFT", "cls": "us", "ccy": "USD", "price": 55.0, "d1": 0.2, "vol": 20.0, "beta": 1.0, "lo": 40.0,
                        "hi": 60.0}]}
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series))
    monkeypatch.setattr(F, "us_tickers", lambda names: ["AAPL", "MSFT", "NVDA", "SHEL", "HALT"])
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today_us)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    today = today_us + dt.timedelta(days=1)
    out, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev=prev)
    uw = meta["_c1wUs"]
    assert uw["date"] == "2026-11-13" and uw["px"] == "2026-11-19" and uw["why"] is None
    assert uw["close"]["AAPL"] == round(float(series["AAPL"].loc["2026-11-13"]), 2) and "NVDA" not in uw["close"]
    meta.pop("_index")
    json.dumps(meta, allow_nan=False)                                          # 재료도 JSON 으로 쓸 수 있는 모양 (날짜는 글자)
    by = {r["t"]: r for r in out}
    assert by["MSFT"].get("pxc") is True and by["HALT"].get("pxd") == "2026-11-17"
    assert not any("c1w" in r for r in out)                                    # 붙이는 곳은 main 의 c1w_fields 한 곳
    m = F.c1w_fields(out, None, uw, HOL)
    assert m == {"wkFrom": None, "usWkFrom": "2026-11-13"}
    for t in ("AAPL", "SHEL"):
        assert by[t]["c1w"] == round(float(series[t].loc["2026-11-13"]), 2) and by[t]["price"] == round(float(series[t].iloc[-1]), 2)
    assert all("c1w" not in by[t] for t in ("MSFT", "NVDA", "HALT"))
    json.dumps(out, allow_nan=False)
    assert any(x.startswith("  !! c1w (이번 주 정리") and "미국 2 / 5 (usWkFrom 2026-11-13)" in x for x in lines), lines[-6:]


def test_funds_take_the_same_series_and_gold_estimate_has_none(monkeypatch):
    days = pd.bdate_range("2025-10-01", "2026-11-20")
    px = pd.Series(np.linspace(9000, 11000, len(days)), index=days)
    monkeypatch.setattr(F, "kr_fund_series", lambda t, start, px_date: px)
    monkeypatch.setattr(F, "log", lambda *a: None)

    def boom(*a):
        raise RuntimeError("down")
    monkeypatch.setattr(F, "krx_gold_series", boom)                            # 네트워크 없이 (금현물은 아래에서 따로)
    bench = px.pct_change().dropna()
    want = round(float(px.loc["2026-11-13"]), 0)
    funds = F.fetch_kr_funds(D(2023, 1, 1), D(2026, 11, 20), bench, {}, 0.03, wk_from="2026-11-13")
    assert len(funds) == len(F.KR_FUNDS) and all(r["c1w"] == want and r["price"] == round(float(px.iloc[-1]), 0) for r in funds)
    assert all("c1w" not in r for r in F.fetch_kr_funds(D(2023, 1, 1), D(2026, 11, 20), bench, {}, 0.03))   # 날짜를 주지 않으면 없음
    assert all("c1w" not in r for r in F.fetch_kr_funds(D(2023, 1, 1), D(2026, 11, 20), bench, {}, 0.03, wk_from="2026-11-14"))  # 봉 없는 날
    monkeypatch.setattr(F, "krx_gold_series", lambda start, px_date: px)        # KRX 금시장 시계열 → 같은 날 봉
    gold = next(r for r in F.fetch_kr_funds(D(2023, 1, 1), D(2026, 11, 20), bench, {}, 0.03, wk_from="2026-11-13") if r["t"] == F.GOLD_SPOT)
    assert gold["c1w"] == want and not gold.get("est")
    monkeypatch.setattr(F, "krx_gold_series", boom)                            # 국제 금값 환산 (추정) → c1w 없음
    usd = pd.Series(2000.0, index=days)
    fx = pd.Series(1400.0, index=days)
    est = next(r for r in F.fetch_kr_funds(D(2023, 1, 1), D(2026, 11, 20), bench, {}, 0.03, gold_usd=usd, fx=fx, wk_from="2026-11-13")
               if r["t"] == F.GOLD_SPOT)
    assert est.get("est") is True and "c1w" not in est
    bonds, _ = F.fetch_bonds(D(2023, 1, 1), D(2026, 11, 20), bench, {}, 0.03, wk_from="2026-11-13")
    assert len(bonds) == len(F.BOND_ETFS) and all(r["c1w"] == want for r in bonds)


def test_main_and_fetchers_are_wired_in_the_right_order():
    main = inspect.getsource(F.main)
    i_stocks, i_c1w, i_pay = main.index("stocks = kr + us + bonds + funds"), main.index("c1w_meta = c1w_fields(stocks, "), main.index("payload = {")
    assert i_stocks < i_c1w < i_pay and "c1w_meta = c1w_fail(stocks, e)" in main and "payload.update(c1w_meta)" in main
    for later_drop in ("kr_own_close_final(", "us_own_close_final(", "us_own_split_late(", "own_drop_us_class("):
        assert main.index(later_drop) < i_c1w, later_drop                       # 행을 빼는 단계가 모두 끝난 뒤
    assert "wk_from=kr_wk_from" in main and main.count("wk_from=kr_wk_from") == 2
    kr = inspect.getsource(F.fetch_korea)
    assert "kr_wk = kr_week_closes(px_date, ks_all.index, sessions, ref_by_day)" in kr and 'meta["_c1wKr"] = kr_wk' in kr
    us = inspect.getsource(F.fetch_us)
    assert 'cw = c1w_at(px, us_wk["date"])' in us and 'meta["_c1wUs"] = us_wk' in us
    assert F.c1w_group is V.c1w_group and F.C1W_COVER_MIN is V.C1W_COVER_MIN     # 파이프라인과 관문이 같은 함수 · 같은 값
    for k in ("c1w", "wkFrom", "usWkFrom"):
        assert k in F.UNITS and not [p for p, v in V.text_values({k: F.UNITS[k]}) if V.BAD_WORD.search(v)]


# ── 5. 관문 줄 (경고만) ───────────────────────────────────────────────────────────────
def with_c1w(cur, factor=1.0 / 1.01, wk="2026-10-23", uwk="2026-10-23"):
    """좋은 고정 데이터 (pxDate · usPxDate 2026-10-30 금) 에 c1w 를 실어요 (가격 ÷ 1.01 · 그 주 시작 10-23)."""
    d = cur["data"]
    d["wkFrom"], d["usWkFrom"] = wk, uwk
    for s in d["stocks"]:
        if V.c1w_group(s) and not V.c1w_own_date(s):
            s["c1w"] = round(s["price"] * factor, 2)
    return cur


def gate(cur, prev=None, final=None):
    hilo = FD.hilo_of(cur, V.MUST)
    return V.run_checks(cur, prev, final, D(2026, 10, 31), mode="publish", count_between=lambda a, b: 1,
                        sessions={"dates": [D(2026, 10, 30)], "src": "t"}, now=dt.datetime(2026, 10, 31, 12, tzinfo=V.KST), hilo=hilo)


def row(rep):
    r = [x for x in rep.rows if x[0] == V.C1W_ROW]
    assert len(r) == 1, rep.table()
    return r[0]


def one(data, macro=None):
    rep = V.Report()
    V.check_v196e(rep, data, macro if macro is not None else FD.build()[0]["macro"])
    return row(rep)


def test_gate_passes_on_good_data_and_changes_no_other_row():
    cur, prev, final = FD.good_pair()
    base = gate(copy.deepcopy(cur), prev, final)
    rep = gate(with_c1w(cur), prev, final)
    r = row(rep)
    assert r[3] == "PASS", r
    assert r[1].startswith("국내 2,400 / 2,400 (wkFrom 2026-10-23) · 미국 600 / 600 (usWkFrom 2026-10-23) · 채권·ETF·금 13 / 13"), r
    assert [x for x in rep.rows if x[0] != V.C1W_ROW] == [x for x in base.rows if x[0] != V.C1W_ROW]
    assert row(base)[3] == "WARN" and "v19.6e 전 파일" in row(base)[1]           # 예전 파일 (지금 사이트) 은 경고만
    assert rep.rows.index(r) > [x[0] for x in rep.rows].index(V.ISSUE_BD_ROW)   # v19.6b 줄들 뒤 (알림 앞자리를 밀어내지 않게)


def _warns(mutate):
    cur, _, _ = FD.good_pair()
    cur = with_c1w(cur)
    mutate(cur["data"])
    r = one(cur["data"], cur["macro"])
    assert r[3] == "WARN", r
    return r[1]


def _st(data, t):
    return next(s for s in data["stocks"] if s["t"] == t)


def _pop(data, cls, n):
    for s in [s for s in data["stocks"] if s.get("cls") == cls and not s.get("fund")][:n]:
        s.pop("c1w")


@pytest.mark.parametrize("mutate, said", [
    (lambda d: d.pop("wkFrom"), "wkFrom 칸 없음"),
    (lambda d: d.update(wkFrom=None), "wkFrom 빈 값"),
    (lambda d: d.update(usWkFrom="2026/10/23"), "YYYY-MM-DD 날짜가 아님"),
    (lambda d: d.update(wkFrom="2026-10-26"), "의 주 월요일(2026-10-26) 앞이 아님"),
    (lambda d: d.update(wkFrom="2026-10-22"), "≠ 휴장일 표로 본 그 주 앞 마지막 거래일 2026-10-23"),
    (lambda d: d.update(wkFrom="2026-10-22"), "≠ 지수 일봉(idxHist KOSPI)으로 본 2026-10-23"),
    (lambda d: d.update(usWkFrom="2026-10-16"), "보다 14일 앞 (> 12일)"),
    (lambda d: _st(d, "005930").update(c1w=float("nan")), "숫자가 아님 1"),
    (lambda d: _st(d, "AAPL").update(c1w=-1.0), "숫자가 아님 1"),
    (lambda d: _st(d, "000660").update(c1w="100"), "숫자가 아님 1"),
    (lambda d: _st(d, "005930").update(pxd="2026-10-29"), "자기 가격 날짜 종목에 있음 1"),
    (lambda d: _st(d, "AAPL").update(pxc=True, pxd="2026-10-29"), "자기 가격 날짜 종목에 있음 1"),
    (lambda d: _st(d, "005380").update(c1w=_st(d, "005380")["price"] * 3), "0.5 ~ 2 밖 1 (005380 현대차 -67%)"),
    (lambda d: _st(d, "005380").update(c1w=_st(d, "005380")["price"] / 4), "제한폭 밖 1 (005380 현대차 +300%)"),   # 1.3^5 = 3.71 배 넘음
    (lambda d: _st(d, "NVDA").update(c1w=_st(d, "NVDA")["price"] * 2.5), "0.5 ~ 2 밖 1 (NVDA"),
    (lambda d: _pop(d, "us", 600), "미국 채움 0.0% (< 95%)"),
    (lambda d: _pop(d, "kr", 121), "국내 채움 94.9% (< 95%)"),                  # 2,279 / 2,400 = 94.96% — 내림으로 적어요
    (lambda d: _st(d, "B0").pop("c1w"), "채권·ETF·금 빈 칸 1"),
    (lambda d: d["stocks"].append({"t": "Q", "cls": "crypto", "price": 1.0, "c1w": 1.0}), "시장을 모르는 행에 있음 1"),
    (lambda d: d.update(wkFrom=None) or _st(d, "005930").update(c1w=1.0), "그 시장 날짜 없이 있음"),
])
def test_gate_warns_and_never_fails(mutate, said):
    assert said in _warns(mutate)


def test_ninety_five_percent_is_still_fine():
    cur, _, _ = FD.good_pair()
    cur = with_c1w(cur)
    _pop(cur["data"], "kr", 120)
    assert one(cur["data"], cur["macro"])[3] == "PASS"                          # 2,280 / 2,400 = 95.0% — 기준 그대로


def test_gate_row_survives_junk_and_its_own_crash(monkeypatch):
    for data in ({}, {"stocks": "x"}, {"wkFrom": 3, "usWkFrom": [], "stocks": [None, 1, {"c1w": 2}]}):
        r = one(data, {})
        assert r[3] in ("PASS", "WARN"), r
    monkeypatch.setattr(V, "_check_v196e", lambda *a: 1 / 0)
    rep = V.Report()
    V.check_v196e(rep, {"wkFrom": "2026-10-23"}, {})
    assert row(rep)[3] == "WARN" and "검사가 오류로 멈췄어요: ZeroDivisionError" in row(rep)[1] and not rep.failed


def test_live_site_check_mode_is_unchanged_but_for_this_row():
    cur, prev, final = FD.good_pair()
    rep_old = V.run_checks(copy.deepcopy(cur), None, final, D(2026, 10, 31), mode="live", hilo=FD.hilo_of(cur, V.MUST))
    rep_new = V.run_checks(with_c1w(cur), None, final, D(2026, 10, 31), mode="live", hilo=FD.hilo_of(cur, V.MUST))
    assert [x for x in rep_new.rows if x[0] != V.C1W_ROW] == [x for x in rep_old.rows if x[0] != V.C1W_ROW]
    assert row(rep_new)[3] == "PASS" and row(rep_old)[3] == "WARN"


def test_real_day_snapshot_fails_the_same_rows_with_or_without_c1w():
    """실제 하루치 발행을 줄인 사본 (tests/fixtures/snapshot · pxDate 2026-11-10 화 · 그 주 시작 11-06 금): c1w 를 실어도 실패 줄이 같아요."""
    snap = os.path.join(ROOT, "tests", "fixtures", "snapshot")
    load = lambda n: json.load(open(os.path.join(snap, f"snap_{n}.json"), encoding="utf-8"))
    cur = {k: load(k) for k in ("data", "corp", "disc", "macro")}
    prev = copy.deepcopy(cur)
    kdays = [D.fromisoformat(r[0]) for r in cur["macro"]["idxHist"]["KOSPI"]["rows"]]

    def run(c):
        return V.run_checks(c, prev, None, D(2026, 11, 11), "publish", count_between=lambda a, b: 1, notes=[],
                            sessions={"dates": kdays, "src": "t"}, now=None, hilo=None, special={}, alt=None)
    base = run(copy.deepcopy(cur))
    new = copy.deepcopy(cur)
    new["data"]["wkFrom"], new["data"]["usWkFrom"] = "2026-11-06", "2026-11-06"
    for s in new["data"]["stocks"]:
        if V.c1w_group(s) and not V.c1w_own_date(s):
            s["c1w"] = round(s["price"] / 1.02, 2)
    rep = run(new)
    assert sorted(x[0] for x in rep.failed) == sorted(x[0] for x in base.failed)
    assert row(rep)[3] == "PASS", row(rep)
    assert V.C1W_ROW not in {x[0] for x in rep.failed} | {x[0] for x in base.failed}
