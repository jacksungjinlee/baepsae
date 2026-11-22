# -*- coding: utf-8 -*-
"""v19.6e (Part I.2, 데이터만): data.json c1w · wkFrom · usWkFrom — 이번 주 정리 (Part E) 가 쓰는 그 주 시작 종가.

스펙 (그대로): "each stock's close on the last trading day before its market's current week, from the same series as price (Korea
official closes; US the same Yahoo closes price uses). Meta wkFrom and usWkFrom (those dates). Blank when missing. [Q9] Korea's official
closes aren't split-adjusted, so the pipeline keeps last week's listed share count with c1w and blanks c1w when the count changed by more
than 20% (splits, 무상증자, big issues); log the count. US closes come from the same adjusted series as price, so splits are already
handled. Never a partial bar."

여기서 보는 것 (네트워크 없음 · 새 파일 · 예전 시험은 그대로):
1. 그 주 시작 날짜: 보통 주 · 금요일 휴장 · 월요일 기준일 · 한국과 미국의 주가 다른 날 · 해 넘김 · 휴장일 표와 맞춰 보기
2. 한국 주식: 그날 최종본 목록 파일의 공식 종가 · KRX 기준가 연결이 모두 확인된 종목만 ('ok' — 기준가가 새로 정해짐도 확인 못 함도 빈 칸:
   무상증자 권리락은 주식 수로는 잡히지 않아요 · 그 사이 목록 파일이 없는 날 · 전일 대비가 빈 행 · 2차 출처 날의 코넥스) · 주식 수 20% 넘게
   바뀌면 빈 칸 (정확히 20% 는 남겨요) · 실제 목록 파일 (2026-11-13 · 11-16 · 코넥스) 로
3. 자기 가격 날짜 종목 (pxd · pxc · 금 추정) 은 빈 칸 · 그날 봉이 없으면 빈 칸 (앞 날 값을 쓰지 않아요) · NaN · 무한대는 쓰지 않아요
4. 미국: 가격만 (그 주의 배당락을 실제 종가로 되돌려요 — 손으로 푼 예 · yfinance 1.7.0 의 auto_adjust) · 그 주 분할은 빈 칸 · 지수 일봉이
   빠뜨린 날 · fetch_us (가짜 야후) → c1w_step · 같은 날 다시 발행 · 재료 줄이 멈춰도 행은 그대로 · 채권 · ETF · 금 · main 의 순서
5. 관문 줄: 통과 · 경고 · 절대 실패하지 않아요 (실제 하루치 사본으로도) · 한국의 제한폭 안 큰 움직임은 이름만 (경고 아님)
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


def test_chuseok_and_seollal_weeks():
    assert week("KR", D(2026, 10, 2)) == (D(2026, 9, 23), None)              # 추석 09-24 · 09-25 (목 · 금) 휴장 → 수요일 (9일 앞)
    assert week("KR", D(2026, 9, 23)) == (D(2026, 9, 18), None)              # 추석 주 안의 수요일 기준일 → 앞 주 금요일
    assert week("KR", D(2026, 10, 6)) == (D(2026, 10, 2), None)              # 10-05 (월) 개천절 대체 휴일 → 화요일 기준일도 앞 주 금요일
    assert week("KR", D(2026, 2, 19)) == (D(2026, 2, 13), None)              # 설 02-16 ~ 18 (월 ~ 수) → 그 주 첫 거래일은 목요일
    assert week("KR", D(2027, 2, 10)) == (D(2027, 2, 5), None)               # 2027 설 다음날 · 대체 휴일 02-08 · 09 (월 · 화)
    vh, vend = V.load_holidays()
    for px in (D(2026, 10, 2), D(2026, 2, 19), D(2027, 2, 10)):
        assert V.c1w_week_expect(px, vh["KR"], vh["start"], vend) == week("KR", px)[0]


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
    kr_wk = {"date": "2026-11-12", "px": "2026-11-20", "why": None, "close": {"005930": 100.0}, "shr": {"005930": 10.0}, "ref": {"005930": "ok"}}
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
    assert kr_wk["src"] == "listing" and kr_wk["rows"] == len(df13) and kr_wk["gap"] == [] and info["kr"]["linkN"] == 0


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
    kw["ref"] = {"005930": "ok", "000660": "ok"}
    F.c1w_apply(rows, kw, None)
    assert "c1w" not in rows[0] and rows[1]["c1w"] == 1216000.0


def test_split_and_bonus_issue_are_blanked_by_the_base_reset():
    """2:1 분할 (주식 수 두 배 · 기준가 반) 과 무상증자 권리락 (가격이 반이 됐는데 새 주식은 아직 상장 전 — 주식 수 그대로) 둘 다 비워요.
    무상증자 주는 주식 수 규칙만으로는 잡히지 않아요 (그 종목의 주식 수는 그대로) → KRX 기준가 연결 (스펙보다 엄하게만)."""
    df16 = listing("2026-11-16_2211")
    s = int(df16.loc[df16["Code"] == "005930", "Stocks"].iloc[0])
    df16 = _set(df16, "005930", Stocks=2 * s, Marcap=98400 * 2 * s, Close=98400, Changes=-4600)      # 분할: 기준가 103,000 ≠ 206,000
    h = int(df16.loc[df16["Code"] == "000660", "Stocks"].iloc[0])
    df16 = _set(df16, "000660", Marcap=560000 * h, Close=560000, Changes=-48000)                      # 권리락: 기준가 608,000 · 주식 수 그대로
    by, _, info, _ = kr_run(df16)
    assert "c1w" not in by["005930"] and "c1w" not in by["000660"]
    assert sorted(t for t, _ in info["kr"]["base"]) == ["000660", "005930", "047400"] and info["kr"]["why"]["base"] == 3   # 047400: 실제 병합
    assert by["005380"]["c1w"] == 269500.0
    assert by["000660"]["shr"] == h and round(560000 / 1216000 - 1, 2) == -0.54     # 주식 수만 봤다면 가짜 −54% 가 나갔을 거예요


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


def _bonus(df, code="000660", changes=-48000):
    """무상증자 1:1 권리락 모양: 가격이 반 (560,000) · 상장 주식 수는 그대로 (새 주식은 몇 주 뒤 상장)."""
    h = int(df.loc[df["Code"] == code, "Stocks"].iloc[0])
    return _set(df, code, Marcap=560000 * h, Close=560000, Changes=changes)


def test_unconfirmed_base_link_blanks_a_missing_mid_week_file():
    """리뷰 (must-fix): 그 주 가운데 날 (11-16) 의 최종본 목록 파일이 없으면 (최종본이 아니었거나 받지 못함) 그 사이 연결을 확인할 수 없어요 — 그날의
    무상증자 권리락이 가짜 −54% 로 나가지 않게 모두 비우고 크게 남겨요."""
    PX = D(2026, 11, 17)
    today = _bonus(listing("2026-11-16_2211"), changes=-10000)                # 11-16 파일 모양을 11-17 (화) 파일로
    td = trade_days("KR", D(2026, 10, 1), PX)
    sessions = [(D13, listing("2026-11-13_2158"))]                            # 11-16 파일 없음
    ref_by_day, _ = F.kr_ref_links([(PX, today)] + sessions, td, set(today["Code"].astype(str).str.strip()))
    kw = F.kr_week_closes(PX, td, sessions, ref_by_day)
    assert kw["date"] == "2026-11-13" and kw["gap"] == ["2026-11-16"] and set(kw["ref"].values()) == {"unknown"}
    rows = kr_rows(today)
    meta, info = F.c1w_apply(rows, kw, None, HOL)
    by = {r["t"]: r for r in rows}
    assert "c1w" not in by["000660"] and not any("c1w" in r for r in rows)
    assert info["kr"]["why"] == collections.Counter({"link": len(rows)}) and info["kr"]["linkN"] == len(rows) and info["krGap"] == ["2026-11-16"]


def test_unconfirmed_base_link_blanks_a_row_without_changes():
    """그날 행의 전일 대비가 빈 값이면 (2차 출처 행 · 받지 못한 칸) 그 종목의 연결은 확인 못 함 → 비워요 (주식 수는 그대로라 20% 규칙만으로는 −54%)."""
    by, _, info, kw = kr_run(_bonus(listing("2026-11-16_2211"), changes=np.nan))
    assert kw["ref"]["000660"] == "unknown" and "c1w" not in by["000660"]
    assert ("000660", "SK하이닉스", "확인 못 함") in info["kr"]["link"] and info["kr"]["why"]["link"] == 1
    assert by["005930"]["c1w"] == 206000.0                                    # 다른 종목은 그대로 (연결 ok)


def test_konex_on_a_backup_day_is_blank_and_on_a_final_day_is_kept():
    """코넥스: 2차 출처 날의 행 (kr_knx_row) 은 전일 대비가 빈 값이라 (두 출처 모두 기준가를 주지 않아요) 연결을 확인 못 함 → 비워요.
    1차 출처 최종본 날은 KRX 기준가가 있어 그대로 실어요 (실제 코넥스 목록 파일 2026-11-13 · 11-16)."""
    FXK = os.path.join(ROOT, "tests", "fixtures", "konex_two_source")
    knx = lambda n: F.parse_listing_csv(open(os.path.join(FXK, f"krx_konex_{n}.csv"), encoding="utf-8").read())
    k13, k16 = knx("2026-11-13_final"), knx("2026-11-16_final")
    for backup in (False, True):
        today = k16.copy()
        if backup:
            today["Changes"] = np.nan
        ref, _ = F.kr_ref_links([(D16, today), (D13, k13)], TD, set(today["Code"].astype(str).str.strip()))
        kw = F.kr_week_closes(D16, TD, [(D13, k13)], ref, known={D13: k13} if backup else None)
        rows = kr_rows(today)
        meta, info = F.c1w_apply(rows, kw, None, HOL)
        kept = [r for r in rows if "c1w" in r]
        if backup:
            assert not kept and info["kr"]["why"]["link"] == len(rows) and kw["src"] == "fb"
        else:
            assert len(kept) == sum(1 for t, st in kw["ref"].items() if st == "ok") > 0 and kw["src"] == "listing"


# ── 3. 자기 가격 날짜 · 빈 봉 · NaN ──────────────────────────────────────────────────────────
def test_own_date_rows_are_blank_even_inside_the_week():
    kr_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"A": 100.0, "B": 100.0}, "shr": {"A": 10.0, "B": 10.0},
             "ref": {"A": "ok", "B": "ok"}}
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
             "shr": {k: 10.0 for k in "ABCD"}, "ref": {k: "ok" for k in "ABCD"}}
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
    kr_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {k: 100.0 for k in "ABCDE"},
             "shr": {k: 10.0 for k in "ABCDE"}, "ref": {"A": "ok", "B": "ok", "C": "break", "D": "unknown"}, "src": "listing", "rows": 2500,
             "gap": ["2026-11-17"]}
    us_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"X": 10.0, "Y": 10.0}, "unadj": ["X"], "bad": {"W": "prev"},
             "split": [], "err": 0}
    st = [{"t": "A", "nk": "가", "cls": "kr", "price": 101.0, "shr": 10}, {"t": "B", "nk": "나", "cls": "kr", "price": 101.0, "shr": 30},
          {"t": "C", "nk": "다", "cls": "kr", "price": 50.0, "shr": 10}, {"t": "D", "nk": "라", "cls": "kr", "price": 50.0, "shr": 10},
          {"t": "E", "nk": "마", "cls": "kr", "price": 50.0, "shr": 10},
          {"t": "P", "nk": "바", "cls": "kr", "price": 50.0, "shr": 10, "pxd": "2026-11-19"},
          {"t": "X", "cls": "us", "price": 11.0}, {"t": "Y", "cls": "us", "price": 11.0}, {"t": "W", "cls": "us", "price": 11.0}]
    meta = F.c1w_fields(st, kr_wk, us_wk, HOL, splits=[["Y", "2026-11-17", 2.0], ["X", "2026-11-12", 2.0]])
    assert meta == {"wkFrom": "2026-11-13", "usWkFrom": "2026-11-13"}
    text = "\n".join(lines)
    assert lines[0] == ("  !! c1w (이번 주 정리 · 그 시장의 이번 주 앞 마지막 거래일 종가 · 기준일 종가 종목 중): 국내 1 / 5 (wkFrom 2026-11-13 · "
                        "최종본 목록 파일 · 자기 가격 날짜 1종목은 빼고) · 미국 1 / 3 (usWkFrom 2026-11-13 · 야후 일봉 · 실제 종가 기준) · 채권·ETF·금 0 / 0"), lines[0]
    assert ("  !! c1w 국내 빈 칸 5: 자기 가격 날짜 (마지막 확인 종가 · 거래 정지) 1 · 그 사이 KRX 기준가가 새로 정해짐 (분할 · 병합 · 감자 · 권리락 · "
            "무상증자 · 코넥스 기준가 조정 등) 1 · 그 사이 KRX 기준가 연결을 확인하지 못함 (목록 파일 · 그날 행 · 전일 대비가 없음) 2 · "
            "상장 주식 수가 20% 넘게 바뀜 (또는 모름) 1") in lines
    assert "  !! c1w 미국 빈 칸 2: 그 주에 주식 분할 (야후 분할 칸 · splits) 1 · 그 주의 배당락을 실제 종가로 되돌리지 못함 1" in lines
    assert "· c1w 주식 수 20% 넘게 바뀌어 비움: 1 / 5 — B 나 (10 → 30주)" in lines
    assert "· c1w KRX 기준가가 그 사이 새로 정해져 비움 (분할 · 병합 · 감자 · 권리락 · 무상증자 · 코넥스 기준가 조정 등): 1 / 5 — C 다" in lines
    assert ("  !! c1w 기준가 연결 확인 못 함 2 · 그중 비움 2 / 5 (그 사이 최종본 목록 파일이 없는 거래일: 2026-11-17) — D 라 (확인 못 함), "
            "E 마 (오늘 목록에 없음)") in lines
    assert "  !! c1w 미국 그 주 배당락: 실제 종가로 되돌림 1 (X) · 되돌리지 못해 비움 1 (W 배당락 앞 거래일 봉이 없음) · 그 주 분할로 비움 1 (Y)" in lines
    lines.clear()
    F.c1w_fields([{"t": "A", "cls": "kr", "price": 101.0, "shr": 10}], dict(kr_wk, ref={"A": "ok"}, gap=[], src="fb", rows=2400),
                 dict(us_wk, unadj=[], bad={}), HOL)
    assert lines[0].startswith("· c1w") and "(wkFrom 2026-11-13 · 2차 출처 행 (두 출처로 확인한 2,400종목))" in lines[0], lines[0]
    assert "· c1w 주식 수 20% 넘게 바뀌어 비움: 0 / 1" in lines and "· c1w 기준가 연결 확인 못 함 0 · 그중 비움 0 / 1" in lines   # 0 이어도 적어요
    assert "· c1w 미국 그 주 배당락: 실제 종가로 되돌림 0 · 되돌리지 못해 비움 0 · 그 주 분할로 비움 0" in lines


def test_a_crash_blanks_everything_and_says_so(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    st = [{"t": "A", "cls": "kr", "price": 1.0, "c1w": 1.0}, {"t": "X", "cls": "us", "price": 1.0, "c1w": 2.0}]
    assert F.c1w_fail(st, ValueError("x")) == {"wkFrom": None, "usWkFrom": None}
    assert not any("c1w" in s for s in st) and lines[0].startswith("  !! c1w 단계가 오류로 멈췄어요 (ValueError: x)")


def test_the_korea_material_step_never_stops_the_run(monkeypatch):
    """fetch_korea 가 부르는 kr_week_closes_safe: 멈추면 크게 남기고 국내 c1w 를 모두 비우는 기록 (발행은 이어가요)."""
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    monkeypatch.setattr(F, "kr_week_closes", lambda *a, **k: 1 / 0)
    kw = F.kr_week_closes_safe(D16, TD, [], {})
    assert kw["date"] is None and kw["why"] == "err" and kw["close"] == {} and kw["px"] == "2026-11-16"
    assert lines[0].startswith("  !! c1w: 이번 주 앞 마지막 거래일의 국내 공식 종가를 읽다가 멈췄어요 (ZeroDivisionError")
    st = [{"t": "A", "cls": "kr", "price": 1.0, "shr": 1}]
    meta, info = F.c1w_apply(st, kw, None, HOL)
    assert meta["wkFrom"] is None and info["wk"]["kr"][1] == "err" and "c1w" not in st[0]


def test_a_crash_inside_the_log_reaches_c1w_fail_through_the_main_step(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    kr_wk = {"date": "2026-11-13", "px": "2026-11-20", "why": None, "close": {"A": 100.0}, "shr": {"A": 10.0}, "ref": {"A": "ok"}}
    st = [{"t": "A", "cls": "kr", "price": 101.0, "shr": 10}]

    def boom(info):
        raise KeyError("log broke")
    monkeypatch.setattr(F, "log_c1w", boom)
    assert F.c1w_step(st, kr_wk, None, HOL) == {"wkFrom": None, "usWkFrom": None}
    assert "c1w" not in st[0] and lines[-1].startswith("  !! c1w 단계가 오류로 멈췄어요 (KeyError: 'log broke')")
    assert "c1w_meta = c1w_step(stocks, " in inspect.getsource(F.main)        # main 은 이 한 곳으로만 불러요


# ── 4. fetch_us (가짜 야후) → c1w_fields · 채권 · ETF · 금 · main 의 순서 ─────────────────────────────
INFO = {"shortName": "Co", "longName": "Co Inc.", "quoteType": "EQUITY", "sector": "Technology", "industry": "Software",
        "financialCurrency": "USD", "currency": "USD", "trailingPE": 20.0, "priceToBook": 4.0, "marketCap": 1e11, "averageVolume": 1e6,
        "country": "United States", "dividendYield": 0.5}


def _fake_yf(series, divs=None, splits=None):
    divs, splits = divs or {}, splits or {}

    def download(tickers, **kw):
        if isinstance(tickers, str):
            return pd.DataFrame({"Close": series["_spx"]})
        cols = {}
        for t in tickers:
            if t in series:
                cols[(t, "Close")] = series[t]
                dv = pd.Series(0.0, index=series[t].index)
                for d, v in divs.get(t, []):
                    dv[pd.Timestamp(d)] = v
                cols[(t, "Dividends")] = dv
                sp = pd.Series(0.0, index=series[t].index)
                for d, v in splits.get(t, []):
                    sp[pd.Timestamp(d)] = v
                cols[(t, "Stock Splits")] = sp
        return pd.DataFrame(cols)

    class Ticker:
        def __init__(self, t):
            self.t = t

        def get_info(self):
            return dict(INFO, shortName=self.t + " Co")
    return types.SimpleNamespace(download=download, Ticker=Ticker)


USD = ["2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]


def crsp_adjust(raw, divs):
    """야후 (CRSP) 수정 종가를 손으로: 배당락일 e 앞의 모든 봉 × (1 − D ÷ e 앞 거래일의 실제 종가) — 뒤 배당락부터 모두 곱해요."""
    adj = raw.copy()
    for e, d in divs.items():
        prev = raw[raw.index < pd.Timestamp(e)].iloc[-1]
        adj[adj.index < pd.Timestamp(e)] *= (1 - d / prev)
    return adj


def test_us_dividend_inside_the_week_is_undone_to_the_actual_close_hand_worked():
    """손으로 푼 예 (오너 결정: c1w 는 두 시장 모두 가격만). 실제 종가 금 11-13 100 · 월 101 · 화 102 · 수 100.5 (배당락 1.02) · 목 101.
    m = 1 − 1.02 ÷ 102 = 0.99 → 야후 수정 종가 금 99.0 · 화 100.98 → A = 100.98, A + D = 102, m = A ÷ (A + D) = 0.99 → c1w = 99.0 ÷ 0.99 = 100."""
    idx = pd.to_datetime(USD[3:])
    raw = pd.Series([100.0, 101.0, 102.0, 100.5, 101.0], index=idx)
    adj = crsp_adjust(raw, {"2026-11-18": 1.02})
    assert round(adj["2026-11-13"], 10) == 99.0 and round(adj["2026-11-17"], 10) == 100.98
    divs = pd.Series(0.0, index=idx)
    divs["2026-11-18"] = 1.02
    v, how = F.us_c1w_close(adj, divs, None, D13, USD)
    assert how == "unadj" and round(v, 9) == 100.0 and round(adj.iloc[-1] / v - 1, 6) == round(101.0 / 100.0 - 1, 6)   # 가격만의 움직임
    # 두 번 (월 11-16 배당락 0.5 · 앞 거래일 = 그 주 시작 금 100): 뒤에서부터 — 앞 배당락의 A 는 뒤 배당락의 m 으로 먼저 나눠요
    divs2 = divs.copy()
    divs2["2026-11-16"] = 0.5
    adj2 = crsp_adjust(raw, {"2026-11-18": 1.02, "2026-11-16": 0.5})
    assert round(adj2["2026-11-13"], 10) == round(100 * 0.995 * 0.99, 10)
    v2, how2 = F.us_c1w_close(adj2, divs2, None, D13, USD)
    assert how2 == "unadj" and round(v2, 9) == 100.0
    # 그 주에 배당락이 없으면 그대로 (plain)
    v3, how3 = F.us_c1w_close(raw, pd.Series(0.0, index=idx), None, D13, USD)
    assert (v3, how3) == (100.0, "plain")


def test_us_dividend_undo_matches_yfinance_auto_adjust():
    """yfinance 1.7.0 (requirements.txt): download(auto_adjust=True, repair=False) 의 Close = 야후 차트 API 의 adjclose (utils.auto_adjust 가 Close 를
    Adj Close 로 바꿔요). 그 함수에 실제 종가와 CRSP 수정 종가를 넣어 나온 Close 를 되돌리면 실제 종가예요."""
    yfu = pytest.importorskip("yfinance.utils")
    idx = pd.to_datetime(USD)
    raw = pd.Series([97.0, 98.5, 99.0, 100.0, 101.0, 102.0, 100.5, 101.0], index=idx)
    adj_close = crsp_adjust(raw, {"2026-11-18": 1.02, "2026-11-12": 0.4})
    df = pd.DataFrame({"Open": raw, "High": raw, "Low": raw, "Close": raw, "Adj Close": adj_close, "Volume": 1})
    out = yfu.auto_adjust(df)
    assert list(out["Close"]) == list(adj_close)
    divs = pd.Series(0.0, index=idx)
    divs["2026-11-18"], divs["2026-11-12"] = 1.02, 0.4                        # 11-12 는 그 주 앞 — 되돌리지 않아요 (가격과 c1w 가 함께 받는 몫)
    v, how = F.us_c1w_close(out["Close"], divs, None, D13, USD)
    assert how == "unadj" and round(out["Close"].iloc[-1] / v, 9) == round(101.0 / 100.0, 9)


@pytest.mark.parametrize("change, why", [
    (lambda d, g: (None, g), "noDiv"),
    (lambda d, g: (d.where(d.index != pd.Timestamp("2026-11-17"), np.nan), g), "odd"),         # 봉이 있는 날의 빈 값
    (lambda d, g: (d.where(d.index != pd.Timestamp("2026-11-16"), -0.2), g), "odd"),           # 음수 배당 기록
    (lambda d, g: (pd.concat([d, pd.Series([0.3], index=pd.to_datetime(["2026-11-20"]))]), g), "after"),   # 기준일 뒤 배당락
    (lambda d, g: (d, pd.Series([0.0, 0.7], index=pd.to_datetime(["2026-11-16", "2026-11-17"]))), "gain"),
    (lambda d, g: (d.where(d.index != pd.Timestamp("2026-11-18"), 200.0), g), "size"),           # 배당 ≥ 앞 종가
])
def test_us_dividend_undo_blanks_when_inputs_are_missing_or_odd(change, why):
    idx = pd.to_datetime(USD[3:])
    adj = crsp_adjust(pd.Series([100.0, 101.0, 102.0, 100.5, 101.0], index=idx), {"2026-11-18": 1.02})
    divs = pd.Series(0.0, index=idx)
    divs["2026-11-18"] = 1.02
    d2, g2 = change(divs, None)
    assert F.us_c1w_close(adj, d2, g2, D13, USD) == (None, why)


def test_us_dividend_undo_needs_the_bar_before_the_ex_date():
    idx = pd.to_datetime(["2026-11-13", "2026-11-16", "2026-11-18", "2026-11-19"])          # 11-17 (배당락 앞 거래일) 봉 없음
    px = pd.Series([99.0, 100.0, 100.5, 101.0], index=idx)
    divs = pd.Series([0.0, 0.0, 1.02, 0.0], index=idx)
    assert F.us_c1w_close(px, divs, None, D13, USD) == (None, "prev")
    nan_gap = pd.Series([0.0, np.nan, 0.0, 0.0], index=pd.to_datetime(["2026-11-13", "2026-11-17", "2026-11-18", "2026-11-19"]))
    assert F.us_c1w_close(px, nan_gap, None, D13, USD) == (99.0, "plain")    # 봉이 없는 날의 빈 값은 합친 다운로드의 빈칸 — 문제 아님


def test_us_split_inside_the_week_blanks():
    col = pd.Series(0.0, index=pd.to_datetime(USD))
    assert F.us_c1w_split_days(col, D13, pd.Timestamp("2026-11-19")) is False
    col["2026-11-17"] = 0.5
    assert F.us_c1w_split_days(col, D13, pd.Timestamp("2026-11-19")) is True
    assert F.us_c1w_split_days(col, D(2026, 11, 17), pd.Timestamp("2026-11-19")) is False      # 그 주 시작 날의 분할은 이미 그 봉에 반영
    assert F.us_c1w_split_days(None, D13, pd.Timestamp("2026-11-19")) is None
    uw = {"date": "2026-11-13", "px": "2026-11-19", "why": None, "close": {"A": 10.0, "B": 10.0, "C": 10.0}}
    st = [{"t": t, "cls": "us", "price": 11.0} for t in "ABC"]
    meta, info = F.c1w_apply(st, None, uw, HOL, splits=[["A", "2026-11-19", 4.0], ["B", "2026-11-13", 2.0], ["C", "2026-11-20", 2.0]])
    assert [s.get("c1w") for s in st] == [None, 10.0, 10.0] and info["us"]["split"] == ["A"]


TICKERS = ("AAPL", "MSFT", "NVDA", "SHEL", "HALT", "SPLT", "KO")


def _us_run(tmp_path, monkeypatch, prev_usd="2026-11-18", blank_last=("MSFT",), divs=None, splits=None, extra=None):
    """가짜 야후로 fetch_us (기준일 2026-11-19 목 → 그 주 월요일 11-16 → usWkFrom 11-13). 반환: (out, meta, lines, series)."""
    today_us = D(2026, 11, 19)
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)
    rnd = np.random.default_rng(3)
    walk = lambda last: pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days) * last
    series = {"_spx": walk(6700.0)}
    for t in TICKERS:
        series[t] = walk(100.0)
    for t in blank_last:
        series[t].iloc[-1] = np.nan                                            # 기준일 봉 없음 → 지난 발행본의 종가 (pxc · 같은 날이면 same)
    series["NVDA"].loc[pd.Timestamp("2026-11-13")] = np.nan                    # 그 주 시작 봉만 없음 → 빈 칸 (11-12 값을 쓰지 않아요)
    series["HALT"].loc[series["HALT"].index > pd.Timestamp("2026-11-17")] = np.nan   # 거래 정지 (자기 날짜 11-17)
    if extra:
        extra(series)
    prev = {"pxDate": prev_usd, "usPxDate": prev_usd,
            "stocks": [{"t": t, "nk": t, "cls": "us", "ccy": "USD", "price": 55.0, "d1": 0.2, "vol": 20.0, "beta": 1.0, "lo": 40.0, "hi": 60.0}
                       for t in blank_last]
                      # #169 (Jack, 11-22): 지난 발행본에 없는 티커는 기준일 종가가 확인될 때까지 들어오지 않아요 — 거래 정지 종목은 실제로는
                      # 지난 발행본에 자기 날짜(pxd)로 이미 있어요 (#165 의 halted 길: 예전처럼 야후의 마지막 봉 날짜)
                      + [{"t": "HALT", "nk": "HALT", "cls": "us", "ccy": "USD", "price": 50.0, "pxd": "2026-11-17", "vol": 20.0, "beta": 1.0,
                          "lo": 40.0, "hi": 60.0}]}
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series, divs, splits))
    monkeypatch.setattr(F, "us_tickers", lambda names: list(TICKERS))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today_us)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "us-info.json.gz"))
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    today = today_us + dt.timedelta(days=1)
    out, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, prev=prev)
    return out, meta, lines, series


def test_fetch_us_records_the_week_start_close_price_only_and_c1w_step_applies_it(tmp_path, monkeypatch):
    out, meta, lines, series = _us_run(tmp_path, monkeypatch, divs={"KO": [("2026-11-17", 1.5)]}, splits={"SPLT": [("2026-11-18", 2.0)]})
    uw = meta["_c1wUs"]
    assert uw["date"] == "2026-11-13" and uw["px"] == "2026-11-19" and uw["why"] is None and uw["bars"] == 0
    assert uw["close"]["AAPL"] == round(float(series["AAPL"].loc["2026-11-13"]), 2) and "NVDA" not in uw["close"]
    # KO: 11-17 배당락 1.5 달러 → 그 앞 거래일(11-16)의 수정 종가 A 로 m = A ÷ (A + 1.5) · c1w = 수정 값 ÷ m (실제 종가 기준 · 가격만)
    a = float(series["KO"].loc["2026-11-16"])
    assert uw["close"]["KO"] == round(float(series["KO"].loc["2026-11-13"]) / (a / (a + 1.5)), 2) and uw["unadj"] == ["KO"]
    assert uw["split"] == ["SPLT"] and "SPLT" not in uw["close"]               # 그 주 분할 → 비워요
    meta.pop("_index")
    json.dumps(meta, allow_nan=False)                                          # 재료도 JSON 으로 쓸 수 있는 모양 (날짜는 글자)
    by = {r["t"]: r for r in out}
    assert by["MSFT"].get("pxc") is True and by["HALT"].get("pxd") == "2026-11-17"
    assert not any("c1w" in r for r in out)                                    # 붙이는 곳은 main 의 c1w_step 한 곳
    m = F.c1w_step(out, None, uw, HOL, splits=meta.get("splits"))
    assert m == {"wkFrom": None, "usWkFrom": "2026-11-13"}
    for t in ("AAPL", "SHEL"):
        assert by[t]["c1w"] == round(float(series[t].loc["2026-11-13"]), 2) and by[t]["price"] == round(float(series[t].iloc[-1]), 2)
    assert by["KO"]["c1w"] == uw["close"]["KO"]
    assert all("c1w" not in by[t] for t in ("MSFT", "NVDA", "HALT", "SPLT"))
    json.dumps(out, allow_nan=False)
    assert any(x.startswith("  !! c1w (이번 주 정리") and "미국 3 / 5 (usWkFrom 2026-11-13 · 야후 일봉 · 실제 종가 기준 · 자기 가격 날짜 2종목은 빼고)" in x
               for x in lines), lines[-8:]
    assert "· c1w 미국 그 주 배당락: 실제 종가로 되돌림 1 (KO) · 되돌리지 못해 비움 0 · 그 주 분할로 비움 1 (SPLT)" in lines


def test_fetch_us_same_day_rows_keep_their_week_start_close(tmp_path, monkeypatch):
    """같은 usPxDate 로 다시 발행 (usSrc.own.same): 그날의 확인된 종가 (pxd 없음) 라 c1w 를 실어요 (오늘 받은 시계열의 그 주 시작 봉)."""
    out, meta, lines, series = _us_run(tmp_path, monkeypatch, prev_usd="2026-11-19", blank_last=("MSFT",))
    by = {r["t"]: r for r in out}
    assert meta["usSrc"]["own"]["same"] == ["MSFT"] and "pxd" not in by["MSFT"] and by["MSFT"]["price"] == 55.0
    F.c1w_step(out, None, meta["_c1wUs"], HOL)
    assert by["MSFT"]["c1w"] == round(float(series["MSFT"].loc["2026-11-13"]), 2)


def test_a_broken_c1w_line_never_drops_or_changes_a_row(tmp_path, monkeypatch):
    """리뷰 nit: 재료 줄은 따로 감싸요 — 거기서 멈춰도 미국 행 · 마지막 확인 종가 · 채권 대표 시계열은 그대로예요."""
    base, bmeta, _l, _s = _us_run(tmp_path, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("c1w broke")
    monkeypatch.setattr(F, "c1w_at", boom)
    out, meta, lines, _s = _us_run(tmp_path, monkeypatch)
    assert out == base and meta["usSrc"] == bmeta["usSrc"] and meta["_c1wUs"]["close"] == {} and meta["_c1wUs"]["err"] == 7
    assert sum(1 for x in lines if "그 주 시작 종가를 만들다가 멈췄어요 (RuntimeError: c1w broke)" in x) == 3   # 처음 세 종목만 적어요
    days = pd.bdate_range("2025-10-01", "2026-11-20")
    px = pd.Series(np.linspace(9000, 11000, len(days)), index=days)
    monkeypatch.setattr(F, "kr_fund_series", lambda t, start, px_date: px)
    bonds, proxy = F.fetch_bonds(D(2023, 1, 1), D(2026, 11, 20), px.pct_change().dropna(), {}, 0.03, wk_from="2026-11-13")
    assert len(bonds) == len(F.BOND_ETFS) and proxy is not None and not any("c1w" in r for r in bonds)


def test_us_index_missing_a_friday_blanks_the_us_week(tmp_path, monkeypatch):
    """S&P 500 일봉이 금요일(11-13)을 빠뜨리면 usWkFrom 이 목요일이 돼요 — 그 사이(11-13)에 봉이 있는 종목이 C1W_US_BARS_MAX 를 넘으면 미국 모두 비움
    (휴장일 표를 읽지 못한 날에도). 한두 종목의 봉은 넘어가요."""
    def drop_fri(series):
        series["_spx"] = series["_spx"].drop(pd.Timestamp("2026-11-13"))
    uw = F.us_week_start(D(2026, 11, 19), [t for t in pd.bdate_range("2026-10-01", "2026-11-19") if t != pd.Timestamp("2026-11-13")])
    assert uw["date"] == "2026-11-12"
    px = pd.Series(1.0, index=pd.bdate_range("2026-10-01", "2026-11-19"))
    data = pd.DataFrame({("A", "Close"): px})
    monkeypatch.setattr(F, "log", lambda *a: None)
    for i in range(F.C1W_US_BARS_MAX):
        F.us_c1w_add(uw, f"T{i}", px, data, D(2026, 11, 16))
    assert F.us_c1w_finish(dict(uw))["date"] == "2026-11-12"                   # 10 종목까지는 그대로
    F.us_c1w_add(uw, "T10", px, data, D(2026, 11, 16))
    done = F.us_c1w_finish(uw)
    assert done["date"] is None and done["why"] == "bars" and done["bars"] == 11
    meta, info = F.c1w_apply([{"t": "T0", "cls": "us", "price": 1.0}], None, done, None)
    assert meta["usWkFrom"] is None and info["us"]["why"]["week"] == 1 and info["wk"]["us"][1] == "bars"
    out, m2, lines, _s = _us_run(tmp_path, monkeypatch, extra=drop_fri)                # fetch_us 를 지나도 같아요
    assert m2["_c1wUs"]["bars"] == 6 and m2["_c1wUs"]["date"] == "2026-11-12"   # 가짜 목록은 7종목뿐 (≤ 10 · 휴장일 표가 따로 잡아요)
    _m, info2 = F.c1w_apply(out, None, m2["_c1wUs"], HOL)
    assert info2["wk"]["us"] == (None, "table", ["2026-11-13"])
    monkeypatch.setattr(F, "C1W_US_BARS_MAX", 5)                                # 표를 읽지 못한 날: 봉 수만으로 (기준을 낮춰 봐요)
    out, m3, lines, _s = _us_run(tmp_path, monkeypatch, extra=drop_fri)
    assert m3["_c1wUs"]["date"] is None and m3["_c1wUs"]["why"] == "bars"
    assert any(x.startswith("  !! c1w: 미국의 그 주 앞 마지막 날 2026-11-12 과 월요일 사이에 봉이 있는 종목 6개 (> 5") for x in lines), lines


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
    i_stocks, i_c1w, i_pay = main.index("stocks = kr + us + bonds + funds"), main.index("c1w_meta = c1w_step(stocks, "), main.index("payload = {")
    assert i_stocks < i_c1w < i_pay and "payload.update(c1w_meta)" in main and main.count("c1w_fields(") == 0
    assert 'splits=list(sp_fields.get("splits") or []) + list(umeta.get("splits") or [])' in main and main.index("sp_fields = splits_fields(") < i_c1w
    for later_drop in ("kr_own_close_final(", "us_own_close_final(", "us_own_split_late(", "own_drop_us_class("):
        assert main.index(later_drop) < i_c1w, later_drop                       # 행을 빼는 단계가 모두 끝난 뒤
    assert "wk_from=kr_wk_from" in main and main.count("wk_from=kr_wk_from") == 2
    kr = inspect.getsource(F.fetch_korea)
    assert "kr_wk = kr_week_closes_safe(px_date, ks_all.index, sessions, ref_by_day, known=fb_known)" in kr and 'meta["_c1wKr"] = kr_wk' in kr
    us = inspect.getsource(F.fetch_us)
    i_nocl, i_add = us.index('nocl[sym] = "bar"'), us.index("us_c1w_add(us_wk, sym, px, data, us_mon)")
    assert i_nocl < i_add and 'meta["_c1wUs"] = us_c1w_finish(us_wk)' in us and "us_wk = us_week_start(us_px_date, spx.index)" in us
    bonds = inspect.getsource(F.fetch_bonds)
    assert bonds.index("proxy = px.pct_change().dropna()") < bonds.index("fund_c1w(recs[-1], px, wk_from)")
    assert F.c1w_group is V.c1w_group and F.C1W_COVER_MIN is V.C1W_COVER_MIN     # 파이프라인과 관문이 같은 함수 · 같은 값
    for k in ("c1w", "wkFrom", "usWkFrom"):
        assert k in F.UNITS and not [p for p, v in V.text_values({k: F.UNITS[k]}) if V.BAD_WORD.search(v)]
    assert 'cls 가 us 이고 fund 가 아닌 행 (미국 주식) 은 usWkFrom' in F.UNITS["c1w"] and "ccy USD" not in F.UNITS["c1w"]


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
    (lambda d: _st(d, "AAPL").update(c1w=_st(d, "AAPL")["price"] * 3), "0.5 ~ 2 밖 1 (AAPL US Corp 0 -67%)"),
    (lambda d: _st(d, "B1").update(c1w=_st(d, "B1")["price"] / 2.5), "0.5 ~ 2 밖 1 (B1 채권1 +150%)"),
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


def test_korean_big_moves_inside_the_price_limit_are_named_without_a_warning():
    """리뷰 nit (알림 소음): 한국 주식의 0.5 ~ 2 밖 움직임이 그 주 거래일만큼 곱한 가격 제한폭 안이면 이름만 (경고 아님 · 테마주의 진짜 움직임) —
    제한폭 밖이면 경고."""
    cur, _, _ = FD.good_pair()
    cur = with_c1w(cur)
    _st(cur["data"], "005380").update(c1w=_st(cur["data"], "005380")["price"] * 3)        # −67% (5거래일 0.7^5 = 0.168 안)
    r = one(cur["data"], cur["macro"])
    assert r[3] == "PASS" and "한국 0.5 ~ 2 밖 1 (경고 아님 · 005380 현대차 -67%)" in r[1], r
    _st(cur["data"], "005930").update(c1w=_st(cur["data"], "005930")["price"] / 4)        # +300% (1.3^5 = 3.71 밖)
    r = one(cur["data"], cur["macro"])
    assert r[3] == "WARN" and "제한폭 밖 1 (005930 삼성전자 +300%)" in r[1], r


def test_gate_says_what_it_skipped_and_survives_odd_macro(monkeypatch):
    cur, _, _ = FD.good_pair()
    cur = with_c1w(cur)
    _st(cur["data"], "005380").update(c1w=_st(cur["data"], "005380")["price"] / 4)
    for macro in ({}, {"idxHist": {"KOSPI": "x", "SP500": [1, 2]}}, {"idxHist": {"SP500": {"rows": None}}}):
        r = one(cur["data"], macro)
        assert r[3] == "PASS", r                                                 # 제한폭을 모르는 날: +300% 는 이름만
        assert "idxHist KOSPI 없어 지수 일봉 확인 · 한국 제한폭 확인 건너뜀" in r[1] and "idxHist SP500 없어 지수 일봉 확인 건너뜀" in r[1], r
        assert "한국 0.5 ~ 2 밖 1 (경고 아님 · 005380 현대차 +300%)" in r[1]
    # 휴장일 표를 읽지 못함 → 경고 (날짜는 지수 일봉으로만 맞춰 봐요)
    monkeypatch.setattr(V, "load_holidays", lambda *a: 1 / 0)
    r = one(with_c1w(FD.good_pair()[0])["data"], FD.build()[0]["macro"])
    assert r[3] == "WARN" and "휴장일 표를 읽지 못해 날짜를 표와 맞춰 보지 않았어요 (ZeroDivisionError)" in r[1], r


def test_gate_names_a_weekend_week_start():
    cur, _, _ = FD.good_pair()
    cur = with_c1w(cur, wk="2026-10-24")
    r = one(cur["data"], cur["macro"])
    assert r[3] == "WARN" and "wkFrom 2026-10-24 가 주말" in r[1] and "≠ 휴장일 표로 본 그 주 앞 마지막 거래일 2026-10-23" in r[1], r


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
