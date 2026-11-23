# -*- coding: utf-8 -*-
"""v19.5b 후속 — 미국 회사의 최근 분기 매출 · 자본 (fetch_data.us_size_*, 관문 validate_data.check_us_size). Jack, 2026-11-13: "v19.5b's
US minimum sizes (25억원 of quarterly revenue, 100억원 of equity, at the day's rate) need a small data PR first."

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 관문 줄은 그대로):
- 야후 분기 표에서 가장 최근 분기의 값과 그 분기 말 날짜 (빈 값 · 무한 · 날짜가 아닌 칸은 건너뜀 · 정수 달러)
- 재무제표 통화가 달러인 회사만 (달러가 아니면 fcur · 모르면 cur · ETF · 펀드는 칸 없음) — 통화를 섞지 않아요
- 받지 못하면 보관본의 값을 그대로 (그 분기 말 날짜와 함께) · 다음 실행이 다시 받아요 · 보관본도 없으면 빈 칸과 이유
- 분기 말이 미국 기준일보다 200일 넘게 앞이거나 뒤면 빈 칸 · 0 · 음수(자본잠식)는 그대로
- 가격을 지키는 장치 (리뷰 2026-11-23): 한 실행에 많아야 300곳 (보관본에 없는 회사를 시가총액 큰 순으로 먼저, 그다음 받은 지 오래된 순) ·
  시간 상한 180초 · 429 는 첫 번에, 빈 답은 3번 이어지면 멈춤 (남은 회사는 다음 실행) · main 의 맨 끝 (가격에 쓰는 야후 요청이 모두 끝난 뒤)
- 로그와 data.json usSize: 채운 수 · 이유별 수 · 크기를 몰라 앱이 목록에 두는 수 (noData) · 아직 받지 않은 수 (pending · 0 이어야 앱이
  최소 크기를 켜요 · 영영 모르는 회사는 들어가지 않아요) · 요청 수 · 멈춘 까닭 · 이름 (크게)
- 설명 글(UNITS)과 기록에 관문의 nan · None · null 낱말이 없어요 · 야후 함수 자리 (yfinance 1.7.0 고정)
- 관문: 경고만 (예전 파일은 통과 · 채움 90% 아래 (아직 차례가 오지 않은 회사 빼고) · 모양 · 달러가 아닌 회사의 칸 · 멈춤 · 거절 · 검사 오류도
  경고) — 실패 줄이 없어요
"""
import datetime as dt
import inspect
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

US_PX = dt.date(2026, 11, 20)
TODAY = dt.date(2026, 11, 23)
Q3, Q2, Q1 = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-06-30"), pd.Timestamp("2026-03-31")


def table(rows, cols=(Q3, Q2, Q1)):
    """yfinance 모양의 분기 표: 줄 = 항목 이름, 칸 = 분기 말 날짜 (새 분기부터)."""
    return pd.DataFrame({c: [vals[i] for vals in rows.values()] for i, c in enumerate(cols)}, index=list(rows))


def stmt(rev=(1.2e9, 1.1e9, 1.0e9), eq=(5.0e9, 4.9e9, 4.8e9)):
    rows = {}
    if rev is not None:
        rows["TotalRevenue"] = list(rev)
    if eq is not None:
        rows["CommonStockEquity"] = list(eq)
    return table(rows) if rows else pd.DataFrame()


def rec(t, **kw):
    return {"t": t, "cls": "us", "price": 100.0, "etf": False, **kw}


class YFRateLimitError(Exception):
    """yfinance.exceptions.YFRateLimitError 와 같은 이름 (429)."""


# ── 표에서 값 고르기 ──
def test_pick_takes_the_newest_quarter_with_a_finite_number():
    df = table({"TotalRevenue": [np.nan, 1.1e9, 1.0e9], "CommonStockEquity": [np.inf, -3.4665e7, 2e8]})
    assert F.us_size_pick(df, "TotalRevenue") == ["2026-06-30", 1100000000]
    assert F.us_size_pick(df, "CommonStockEquity") == ["2026-06-30", -34665000]          # 무한은 건너뛰고 음수는 그대로
    assert F.us_size_pick(df, "StockholdersEquity") is None                              # 줄 없음
    assert F.us_size_pick(pd.DataFrame(), "TotalRevenue") is None and F.us_size_pick(None, "TotalRevenue") is None
    odd = pd.DataFrame({pd.NaT: [5.0], Q1: [7.4]}, index=["TotalRevenue"])
    assert F.us_size_pick(odd, "TotalRevenue") == ["2026-03-31", 7]                    # 날짜가 아닌 칸은 건너뛰고 정수로 반올림
    assert F.US_SIZE_ROWS == (("qrev", "TotalRevenue"), ("qeq", "CommonStockEquity"))


def test_entry_keeps_the_old_values_when_nothing_came_and_counts_the_tries():
    old = {"at": "2026-11-01", "qrev": ["2026-06-30", 900], "qeq": ["2026-06-30", 800], "seen": True}
    assert F.us_size_entry(stmt(), old, TODAY) == {"at": "2026-11-23", "seen": True, "qrev": ["2026-09-30", 1200000000], "qeq": ["2026-09-30", 5000000000]}
    e = F.us_size_entry(stmt(rev=None), old, TODAY)                                     # 반기 보고 회사: 분기 매출 줄이 없음 (받은 것)
    assert e == {"at": "2026-11-23", "seen": True, "qrev": None, "qeq": ["2026-09-30", 5000000000], "no": {"qrev": "noRow"}}
    for nothing in (None, pd.DataFrame()):                                              # 오류 · 빈 답: 예전 값 그대로 · 다음 실행에서 다시
        e = F.us_size_entry(nothing, old, TODAY)
        assert e == {"at": "2026-11-23", "seen": True, "tries": 1, "qrev": ["2026-06-30", 900], "qeq": ["2026-06-30", 800], "old": ["qrev", "qeq"],
                     "due": True}, e
    e = F.us_size_entry(None, F.us_size_entry(None, None, TODAY), TODAY)                # 한 번도 받지 못한 회사: seen 없이 tries 만 늘어요
    assert e == {"at": "2026-11-23", "tries": 2, "qrev": None, "qeq": None, "due": True}, e
    assert "tries" not in F.us_size_entry(stmt(), e, TODAY)                              # 받으면 없어져요
    assert F.us_size_tries({"tries": True}) == 0 and F.us_size_tries({"tries": "3"}) == 0 and F.us_size_tries(None) == 0


def test_pending_is_nothing_cached_or_never_answered_before_the_tries_run_out():
    assert F.us_size_pending(None) and F.us_size_pending({"at": "2026-11-23", "tries": 2})
    assert not F.us_size_pending({"at": "2026-11-23", "tries": 3})                      # 3번 이어서 받지 못함: 영영 모름 (pending 아님)
    assert not F.us_size_pending({"at": "2026-11-23", "tries": 5, "seen": True})         # 답을 받은 적 있음
    assert not F.us_size_pending({"at": "2026-11-23", "qeq": ["2026-09-30", 1]}) and not F.us_size_pending({"at": "x", "no": {"qrev": "noRow"}})
    assert F.US_SIZE_TRIES == 3 and F.US_SIZE_FRESH_DAYS == 7


def test_order_takes_missing_biggest_first_then_oldest_then_given_up_and_no_entry_falls_out():
    have = lambda at, **kw: {"at": at, "qrev": ["2026-09-30", 1], "qeq": ["2026-09-30", 1], "seen": True, **kw}   # noqa: E731
    cache = {"OLD1": have("2026-11-01"), "OLD2": have("2026-11-10"), "OLD0": have("2026-11-10"), "FRESH": have("2026-11-20"),
             "RETRYV": have("2026-11-22", due=True, tries=1), "RETRY0": {"at": "2026-11-22", "qrev": None, "qeq": None, "due": True, "tries": 2},
             "GIVEUP1": {"at": "2026-11-10", "qrev": None, "qeq": None, "due": True, "tries": 3},          # 3번 받지 못함 · 7일 지남: 맨 뒤
             "GIVEUP0": {"at": "2026-11-20", "qrev": None, "qeq": None, "due": True, "tries": 4},          # 7일 안: 오늘은 받지 않아요
             "NOVAL": {"at": "2026-11-10", "seen": True, "qrev": None, "qeq": None, "no": {"qrev": "noRow", "qeq": "noRow"}},   # 값 없이 답만 · 7일 지남
             "FUTURE": have("2026-12-01"), "BADAT": have("x")}                                            # 받은 날이 이상함: 다시 받아요
    caps = {"NEWBIG": 900.0, "NEWSMALL": 1.0, "NEWNOCAP": None, "RETRY0": 50.0, "RETRYV": 40.0, "OLD2": 10.0, "OLD0": 20.0, "FUTURE": 30.0, "BADAT": 5.0}
    want = sorted(list(cache) + ["NEWBIG", "NEWSMALL", "NEWNOCAP"])
    ask, n1, n2, n3 = F.us_size_order(want, cache, caps, TODAY, per_run=100)
    assert ask == ["NEWBIG", "RETRY0", "RETRYV", "FUTURE", "BADAT", "NEWSMALL", "NEWNOCAP",      # ① 없음 · 지난번 실패 · 날짜가 이상함 (큰 순)
                   "OLD1", "OLD0", "OLD2", "NOVAL",                                              # ② 7일 지남 (오래된 순 · 같은 날은 큰 순)
                   "GIVEUP1"], ask                                                               # ③ 3번 이어서 받지 못함 (7일에 한 번 · 맨 뒤)
    assert (n1, n2, n3) == (7, 4, 1) and "FRESH" not in ask and "GIVEUP0" not in ask
    assert F.us_size_order(want, cache, caps, TODAY, per_run=3)[0] == ["NEWBIG", "RETRY0", "RETRYV"]
    assert F.US_SIZE_PER_RUN == 300 and F.US_SIZE_BUDGET_S == 180 and F.US_SIZE_EMPTY_STOP == 3 and F.US_SIZE_WORKERS == 3


def test_fields_only_for_dollar_filers_and_recent_quarters():
    e = {"at": "2026-11-20", "qrev": ["2026-09-30", 0], "qeq": ["2026-09-30", -343000000]}
    assert F.us_size_fields(e, "USD", US_PX) == ({"qrev": 0, "qrevD": "2026-09-30", "qeq": -343000000, "qeqD": "2026-09-30"},
                                                  {"qrev": None, "qeq": None})                  # 0 · 자본잠식도 그대로
    assert F.us_size_fields(e, "EUR", US_PX) == ({}, {"qrev": "fcur", "qeq": "fcur"})          # 통화를 섞지 않아요
    assert F.us_size_fields(e, None, US_PX) == ({}, {"qrev": "cur", "qeq": "cur"})
    assert F.us_size_fields(None, "USD", US_PX) == ({}, {"qrev": "wait", "qeq": "wait"})       # 아직 받지 않음
    assert F.us_size_fields({"at": "x", "qrev": None, "qeq": None, "tries": 2}, "USD", US_PX)[1] == {"qrev": "retry", "qeq": "retry"}
    assert F.us_size_fields({"at": "x", "qrev": None, "qeq": None, "tries": 3}, "USD", US_PX)[1] == {"qrev": "gaveUp", "qeq": "gaveUp"}
    assert F.us_size_fields({"at": "x", "qrev": None, "no": {"qrev": "noRow"}, "qeq": ["2026-09-30", 1]}, "USD", US_PX)[1] == {"qrev": "noRow", "qeq": None}
    edge = US_PX - dt.timedelta(days=F.US_SIZE_MAX_AGE_DAYS)
    old = {"qrev": [edge.isoformat(), 5], "qeq": [(edge - dt.timedelta(days=1)).isoformat(), 5]}
    assert F.us_size_fields(old, "USD", US_PX) == ({"qrev": 5, "qrevD": edge.isoformat()}, {"qrev": None, "qeq": "old"})
    assert F.us_size_fields({"qrev": ["2026-11-30", 5], "qeq": ["2026-09-30", 5.6]}, "USD", US_PX)[1]["qrev"] == "future"
    assert F.us_size_fields({"qrev": ["2026-09-30", float("nan")], "qeq": ["30/09/2026", 5], "seen": True}, "USD", US_PX)[1] == {"qrev": "fail", "qeq": "fail"}
    assert F.US_SIZE_MAX_AGE_DAYS == V.US_SIZE_MAX_AGE == 200                             # 관문과 같은 상한


def test_refusal_is_429_by_name_or_text():
    assert F.us_size_refused(YFRateLimitError("Too Many Requests. Rate limited."))
    assert F.us_size_refused(RuntimeError("HTTP Error 429: Too Many Requests")) and F.us_size_refused(OSError("status 429"))
    assert not F.us_size_refused(RuntimeError("timeout")) and not F.us_size_refused(ValueError("4290 rows"))


# ── 한 실행 (가짜 야후) ──
def step(tmp_path, out, curs, fetch, **kw):
    lines, calls = [], []

    def f(t):
        calls.append(t)
        return fetch(t)
    old = F.log
    F.log = lines.append
    try:
        r = F.us_size_step(out, curs.get, US_PX, kw.pop("today", TODAY), fetch=f, path=str(tmp_path / "us-size.json.gz"), **kw)
    finally:
        F.log = old
    return r, lines, calls


def test_step_fills_dollar_filers_and_names_every_blank(tmp_path):
    out = [rec("AAA", cap=9.0), rec("BBB", cap=8.0), rec("CCC"), rec("DDD", etf=True), rec("EEE"), rec("FFF"), rec("GGG", fund=True),
           rec("HHH"), rec("III", qrev=1, qrevD="2020-01-01")]                               # 예전 칸이 남아 있으면 지워요
    curs = {"AAA": "USD", "BBB": "EUR", "DDD": "USD", "EEE": "USD", "FFF": "USD", "HHH": "USD", "III": "TWD"}

    def fake(t):
        if t == "EEE":
            raise RuntimeError("boom")
        if t == "FFF":
            return stmt(rev=None)                                                           # 반기 보고 회사: 분기 매출 줄이 없음
        if t == "HHH":
            return stmt(rev=(np.nan, np.nan, 2e6), eq=(1e9, 1e9, 1e9))                      # 오래된 매출만 (3월 말 · 235일)
        return stmt()
    r, lines, calls = step(tmp_path, out, curs, fake, workers=1)
    by = {x["t"]: x for x in out}
    assert by["AAA"] == rec("AAA", cap=9.0, qrev=1200000000, qrevD="2026-09-30", qeq=5000000000, qeqD="2026-09-30")
    for t in ("BBB", "CCC", "DDD", "EEE", "GGG", "III"):
        assert not any(k in by[t] for k in ("qrev", "qrevD", "qeq", "qeqD")), t
    assert by["FFF"].get("qeq") == 5000000000 and "qrev" not in by["FFF"]
    assert by["HHH"].get("qeq") == 1000000000 and "qrev" not in by["HHH"]
    assert calls == ["AAA", "EEE", "FFF", "HHH"]                                             # 달러 재무제표 회사만 · 한 번씩 (요청 = 회사 수)
    assert r["n"] == 7 and r["usd"] == 4 and r["qrev"] == 1 and r["qeq"] == 3, r
    assert r["why"] == {"qrev": {"fcur": 2, "cur": 1, "retry": 1, "noRow": 1, "old": 1}, "qeq": {"fcur": 2, "cur": 1, "retry": 1}}, r["why"]
    assert r["noData"] == {"qrev": 6, "qeq": 4}                                              # 크기가 빈 행 (최소 크기가 켜지면 수익성에서 빠져요)
    assert r["pending"] == 1                                    # EEE: 오류 한 번 · 3번까지 pending · 통화 모름(CCC) · 다른 통화는 영영 모름 (pending 아님)
    assert r["blank"] == {"qrev": {"BBB": "fcur", "CCC": "cur", "FFF": "noRow", "HHH": "old", "III": "fcur"},
                          "qeq": {"BBB": "fcur", "CCC": "cur", "III": "fcur"}}, r["blank"]   # 아직 차례가 남은 EEE 는 빼고 (앱 콘솔이 이름과 이유로)
    assert (r["asked"], r["req"], r["ok"], r["empty"], r["err"], r["time"], r["stop"], r["stopKind"], r["kept"]) == (4, 4, 3, 0, 1, 0, None, None, 0), r
    assert r["cached"] == 4 and r["perRun"] == F.US_SIZE_PER_RUN and r["unit"] == "USD" and "CommonStockEquity" in r["src"]
    head = [x for x in lines if "미국 회사 크기 (" in x]
    assert len(head) == 1 and head[0].startswith("  !! ") and "요청 4" in head[0] and "오류 1 (RuntimeError 1)" in head[0], head
    assert any("미국 회사 크기가 빈 회사: 매출 6 · 자본 4 — 앱의 미국 최소 크기가 켜지면 수익성 목록에서 빠져요" in x for x in lines), lines
    assert any(x.startswith("  · 미국 qrev") and "BBB, III" in x for x in lines), lines           # 달러가 아닌 회사: 알려진 빈 칸 (이름)
    assert any(x.startswith("  !! 미국 qrev") and "EEE" in x for x in lines) and any(x.startswith("  !! 미국 qrev") and "HHH" in x and "200일" in x for x in lines)
    assert any(x.startswith("  !! 미국 qeq") and "CCC" in x for x in lines)                    # 통화를 모름
    json.dumps(out, allow_nan=False)                                                            # NaN 이 없어요
    assert all(isinstance(x.get(k), int) for x in out for k in ("qrev", "qeq") if k in x)


def test_failed_fetch_keeps_the_dated_cache_and_fresh_entries_are_not_fetched_again(tmp_path):
    out = [rec("AAA"), rec("BBB")]
    curs = {"AAA": "USD", "BBB": "USD"}
    step(tmp_path, out, curs, lambda t: stmt())
    out = [rec("AAA"), rec("BBB")]
    r, lines, calls = step(tmp_path, out, curs, lambda t: stmt(), today=TODAY + dt.timedelta(days=6))
    assert calls == [] and r["asked"] == r["req"] == 0 and r["qeq"] == 2                       # 7일 안: 받지 않고 보관본
    out = [rec("AAA"), rec("BBB")]
    r, lines, calls = step(tmp_path, out, curs, lambda t: (_ for _ in ()).throw(OSError("down")), today=TODAY + dt.timedelta(days=8), workers=1)
    assert sorted(calls) == ["AAA", "BBB"] and r["err"] == 2 and r["kept"] == 2 and r["stop"] is None
    assert all(x["qeqD"] == "2026-09-30" and x["qeq"] == 5000000000 for x in out)              # 받지 못해도 날짜가 붙은 보관본 값
    back = F.load_us_size(str(tmp_path / "us-size.json.gz"))
    assert back["AAA"]["due"] is True and back["AAA"]["old"] == ["qrev", "qeq"] and back["AAA"]["tries"] == 1   # 다음 실행이 다시 받아요
    assert r["pending"] == 0                                                                    # 답을 받은 적 있는 회사는 pending 이 아니에요
    out = [rec("AAA"), rec("BBB")]
    r, lines, calls = step(tmp_path, out, curs, lambda t: stmt(), today=TODAY + dt.timedelta(days=9))
    assert sorted(calls) == ["AAA", "BBB"] and r["ok"] == 2
    assert not {"due", "tries"} & set(F.load_us_size(str(tmp_path / "us-size.json.gz"))["AAA"])


def test_cap_per_run_fills_the_cache_over_several_runs(tmp_path):
    names = [f"T{i:03d}" for i in range(7)]
    curs = {t: "USD" for t in names}
    seen = []
    for day in range(4):
        out = [rec(t, cap=float(100 - i)) for i, t in enumerate(names)]
        r, lines, calls = step(tmp_path, out, curs, lambda t: stmt(), per_run=3, today=TODAY + dt.timedelta(days=day))
        seen.append((sorted(calls), r["req"], r["qeq"], r["noData"]["qeq"], r["why"]["qeq"].get("wait", 0), r["cached"], r["pending"]))
    assert [s[0] for s in seen] == [names[:3], names[3:6], names[6:], []], seen          # 큰 회사부터 3곳씩 · 다 차면 받지 않아요 (7일 안)
    assert [s[1:] for s in seen] == [(3, 3, 4, 4, 3, 4), (3, 6, 1, 1, 6, 1), (1, 7, 0, 0, 7, 0), (0, 7, 0, 0, 7, 0)], seen   # pending 4 → 1 → 0
    assert any("아직 받지 않음" in x and "T006" in x for x in step(tmp_path / "x", [rec(t) for t in names], curs, lambda t: stmt(), per_run=6)[1])


def test_429_stops_the_step_at_once_and_leaves_the_rest_for_the_next_run(tmp_path):
    names = [f"T{i}" for i in range(6)]

    def fake(t):
        if t == "T1":
            raise YFRateLimitError("Too Many Requests. Rate limited. Try after a while.")
        return stmt()
    out = [rec(t, cap=float(10 - i)) for i, t in enumerate(names)]
    r, lines, calls = step(tmp_path, out, {t: "USD" for t in names}, fake, workers=1)
    assert calls == ["T0", "T1"] and r["req"] == 2 and r["stop"] == "야후 거절 (429 · T1)" and r["stopKind"] == "429", (calls, r)
    assert r["qeq"] == 1 and r["why"]["qeq"] == {"retry": 1, "stop": 4} and r["noData"]["qeq"] == 5 and r["pending"] == 5   # 거절된 T1 도 pending
    assert any(x.startswith("  !! 미국 회사 크기: 이 단계를 멈췄어요 — 야후 거절 (429 · T1)") and "영향 없음" in x for x in lines), lines
    r, lines, calls = step(tmp_path, [rec(t, cap=float(10 - i)) for i, t in enumerate(names)], {t: "USD" for t in names}, lambda t: stmt(), workers=1)
    assert calls == ["T1", "T2", "T3", "T4", "T5"] and r["qeq"] == 6                          # 다음 실행: 남은 곳부터


def test_empty_answers_in_a_row_stop_the_step_and_one_good_answer_resets(tmp_path):
    names = [f"T{i}" for i in range(8)]
    empty = {"T0", "T1", "T3", "T4", "T5"}
    out = [rec(t, cap=float(10 - i)) for i, t in enumerate(names)]
    r, lines, calls = step(tmp_path, out, {t: "USD" for t in names}, lambda t: pd.DataFrame() if t in empty else stmt(), workers=1)
    assert calls == ["T0", "T1", "T2", "T3", "T4", "T5"] and r["stopKind"] == "empty", (calls, r["stop"])
    assert r["stop"] == "처음 받지 못한 회사의 빈 답 · 오류가 3번 이어짐 (마지막 T5 · 야후가 막는 것일 수 있어요)", r["stop"]
    assert (r["ok"], r["empty"], r["why"]["qeq"], r["pending"]) == (1, 5, {"retry": 5, "stop": 2}, 7), r


def test_always_empty_companies_do_not_stall_the_fill_and_a_new_listing_is_fetched(tmp_path):
    """리뷰 2026-11-24 S1: 늘 빈 답인 회사 3곳이 (가장 큰 회사라 맨 앞) 매번 단계를 멈추면 다른 회사는 영영 받지 못하고 pending 이 0 이 되지 않아요.
    이제 지난번에도 받지 못한 회사는 빈 답 셈에서 빠지고, 3번 뒤로는 7일에 한 번 맨 뒤에서만 다시 받아요."""
    good_t, bad_t = [f"G{i}" for i in range(5)], ["E0", "E1", "E2"]
    curs = {t: "USD" for t in good_t + bad_t + ["NEW"]}
    caps = {**{t: 100.0 - i for i, t in enumerate(bad_t)}, **{t: 50.0 - i for i, t in enumerate(good_t)}, "NEW": 1.0}
    fake = lambda t: pd.DataFrame() if t in bad_t else stmt()   # noqa: E731
    runs = []
    for day, names in ((0, good_t + bad_t), (1, good_t + bad_t), (2, good_t + bad_t + ["NEW"]), (3, good_t + bad_t + ["NEW"]),
                       (12, good_t + bad_t + ["NEW"])):
        out = [rec(t, cap=caps[t]) for t in names]
        r, lines, calls = step(tmp_path, out, curs, fake, workers=1, today=TODAY + dt.timedelta(days=day))
        runs.append((calls, r, lines))
    (c0, r0, l0), (c1, r1, _l1), (c2, r2, l2), (c3, r3, _l3), (c4, r4, _l4) = runs
    assert c0 == bad_t and r0["stopKind"] == "empty" and r0["pending"] == 8               # 첫 실행: 처음 받지 못한 3곳이 이어져 멈춤 (그럴 수 있어요)
    assert c1 == bad_t + good_t and r1["stop"] is None and r1["qeq"] == 5 and r1["pending"] == 3   # 둘째: 지난번에도 받지 못한 곳은 셈에서 빠져요
    assert c2 == bad_t + ["NEW"] and r2["stop"] is None and r2["pending"] == 0 and r2["gaveUp"] == 3, (c2, r2)   # 셋째: 새 상장도 받고 다 받음
    assert r2["why"]["qeq"] == {"gaveUp": 3} and r2["blank"]["qeq"] == {"E0": "gaveUp", "E1": "gaveUp", "E2": "gaveUp"}
    assert any("3번 이어서 받지 못한 회사 3곳" in x and "E0, E1, E2" in x for x in l2), l2
    assert c3 == [] and r3["pending"] == 0                                                 # 넷째: 다 7일 안 · 3번 받지 못한 곳도 7일에 한 번
    assert c4 == good_t + ["NEW"] + bad_t and r4["stop"] is None and r4["qeq"] == 6        # 12일 뒤: 다시 받을 때는 받아 온 회사 먼저, 그 뒤 E 들

    back = F.load_us_size(str(tmp_path / "us-size.json.gz"))
    assert back["E0"]["tries"] == 4 and "seen" not in back["E0"]


def test_a_refused_new_listing_on_a_full_cache_keeps_the_minimum_off(tmp_path):
    """리뷰 2026-11-24 S2 (Opus N1): 다 받은 보관본 + 새 회사 하나가 429 → pending 1 (앱의 최소 크기 꺼짐). 예전에는 fail 로 pending 0 이었어요."""
    names = ["AAA", "BBB", "CCC"]
    step(tmp_path, [rec(t) for t in names], {t: "USD" for t in names}, lambda t: stmt())
    def fake(t):
        if t == "NEW":
            raise YFRateLimitError("Too Many Requests")
        return stmt()
    r, lines, calls = step(tmp_path, [rec(t) for t in names + ["NEW"]], {t: "USD" for t in names + ["NEW"]}, fake, workers=1,
                           today=TODAY + dt.timedelta(days=1))
    assert calls == ["NEW"] and r["pending"] == 1 and r["why"]["qeq"] == {"retry": 1} and r["stopKind"] == "429", r
    assert any("아직 차례가 남은 달러 회사 1곳 → 앱의 종목 순위는 미국 최소 크기와 그 줄 없이 예전처럼" in x for x in lines), lines
    assert "retry" in F.US_SIZE_WHY_KO and "빈 답을 줌" not in F.US_SIZE_WHY_KO["retry"] and "거절" in F.US_SIZE_WHY_KO["retry"]


def test_a_table_that_breaks_the_reader_is_an_error_for_that_company_only(tmp_path):
    """리뷰 2026-11-24 N2: 표를 읽다 멈추면 그 회사만 오류 · 다른 회사는 그대로 · 보관본은 저장돼요."""
    class Odd:
        index = ["TotalRevenue", "CommonStockEquity"]
        empty = False

        @property
        def loc(self):
            raise KeyError("odd table")
    names = ["AAA", "ODD", "BBB"]
    r, lines, calls = step(tmp_path, [rec(t) for t in names], {t: "USD" for t in names}, lambda t: Odd() if t == "ODD" else stmt(), workers=1)
    assert sorted(calls) == sorted(names) and (r["ok"], r["err"], r["qeq"]) == (2, 1, 2), r
    back = F.load_us_size(str(tmp_path / "us-size.json.gz"))
    assert set(back) == set(names) and back["ODD"]["tries"] == 1 and "KeyError 1" in [x for x in lines if "미국 회사 크기 (" in x][0]


def test_time_limit_stops_the_step_loudly(tmp_path):
    t0 = [0.0]

    def clock():
        t0[0] += 100.0
        return t0[0]
    names = ["AAA", "BBB", "CCC", "DDD"]
    r, lines, calls = step(tmp_path, [rec(t) for t in names], {t: "USD" for t in names}, lambda t: stmt(), clock=clock, budget_s=150, workers=1)
    assert len(calls) == 1 and r["time"] == 3 and r["why"]["qeq"] == {"time": 3} and r["pending"] == 3, r
    assert any(x.startswith("  !! 미국 회사 크기: 시간 상한 150초") for x in lines) and any(x.startswith("  !! 미국 qeq") and "시간 상한" in x for x in lines)


def test_stopped_step_blanks_every_row_and_says_so():
    out = [rec("AAA", qrev=1, qrevD="2026-09-30", qeq=2, qeqD="2026-09-30"), rec("BBB")]
    lines = []
    old = F.log
    F.log = lines.append
    try:
        r = F.us_size_stopped(out, KeyError("x"))
    finally:
        F.log = old
    assert r == {"v": 1, "unit": "USD", "stopped": "KeyError"} and out == [rec("AAA"), rec("BBB")]
    assert lines[0].startswith("  !! 미국 회사 크기") and "KeyError" in lines[0]


def test_cache_path_follows_the_us_info_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("US_SIZE_CACHE", raising=False)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / "c" / "us-info-v1.json.gz"))
    assert F.us_size_path() == str(tmp_path / "c" / "us-size-v1.json.gz")
    monkeypatch.setattr(F, "US_INFO_PATH", ".dart-cache/us-info-v1.json.gz")
    assert F.us_size_path() == os.path.join(".dart-cache", "us-size-v1.json.gz")             # 워크플로가 저장하는 DART 캐시 폴더
    assert F.load_us_size(str(tmp_path / "none.json.gz")) == {}


def test_the_yahoo_call_is_one_request_for_both_rows_in_the_pinned_yfinance():
    yf = pytest.importorskip("yfinance")
    req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
    assert "yfinance==1.7.0" in req                                                             # 이 함수 자리는 1.7.0 에 고정 (올릴 때 다시 봐요)
    fin = yf.Ticker("AAPL")._fundamentals.financials                                            # 네트워크 없이 만들어져요
    assert list(inspect.signature(fin._get_financials_time_series).parameters) == ["timescale", "keys"]
    src = inspect.getsource(F._us_size_yahoo)
    assert '_get_financials_time_series("quarterly", [row for _k, row in US_SIZE_ROWS])' in src


def test_fetch_us_passes_the_statement_currency_and_does_not_fetch_sizes(tmp_path, monkeypatch):
    from test_us_own_close import _fetch
    monkeypatch.setattr(F, "_us_size_yahoo", lambda t: (_ for _ in ()).throw(AssertionError("fetch_us 는 크기를 받지 않아요")))
    out, meta, lines, _prev = _fetch(tmp_path, monkeypatch, blank=set())
    assert meta["_usCur"] and set(meta["_usCur"]) == {r["t"] for r in out} and set(meta["_usCur"].values()) <= {"USD", None}
    assert "usSize" not in meta and not any(k in r for r in out for k in ("qrev", "qeq"))
    assert not any("미국 회사 크기" in x for x in lines)


def test_main_runs_the_step_after_every_price_request_and_writes_data_json_again():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    body = src[src.index("def main():"):src.index('if __name__ == "__main__":')]
    step_at = body.index('ph.run("미국 회사 크기", us_size_step, us,')                       # 단계 시간이 실행 요약에 나와요 (⏱)
    for before in ('ph.run("국내 시세", fetch_korea', 'ph.run("미국", fetch_us', "fetch_split_history", 'yf.download("GC=F"', 'ph.run("ETF·금현물"',
                   'ph.run("금리·원자재", fetch_macro', 'ph.run("환율 이력", fx_hist_fields', "write_json(OUT, payload)", "write_json(OUT_CORP, corp)",
                   "write_json(OUT_MACRO, macro)"):
        i = body.find(before) if before != "fetch_split_history" else body.find("splits_fields(")
        assert 0 <= i < step_at, before
    assert "yf." not in body[step_at:] and "fetch_yahoo" not in body[step_at:]               # 이 뒤에는 야후 요청이 없어요 (DART 만)
    assert body.index("write_json(OUT, payload)", step_at) > step_at                           # 칸을 붙여 다시 써요
    assert '"usSize": {"v": 1, "unit": "USD", "stopped": "notRun"}' in body                   # 다시 쓰지 못하면 관문이 경고해요
    fu = src[src.index("def fetch_us("):src.index("def ", src.index("def fetch_us(") + 10)]
    assert "us_size_step" not in fu


def test_text_passes_the_gate_word_check():
    bad = [p for p, v in V.text_values({k: F.UNITS[k] for k in ("qrev", "qeq", "usSize")}) if V.BAD_WORD.search(v)]
    assert bad == []
    rec_ = {"v": 1, "unit": "USD", "src": "yahoo quarterly statements (TotalRevenue, CommonStockEquity)", "why": {"qrev": {"fcur": 1}},
            "stop": "빈 답 3번 이어짐 (마지막 T5)"}
    assert [p for p, v in V.text_values(rec_) if V.BAD_WORD.search(v)] == []
    assert all(V.BAD_WORD.search(w) is None for w in F.US_SIZE_WHY_KO.values())


# ── 관문: 경고만 ──
def data_of(rows, rec_=None, **kw):
    d = {"usPxDate": US_PX.isoformat(), "stocks": rows, **kw}
    if rec_ is not None:
        d["usSize"] = rec_
    return d


def gate(d):
    rep = V.Report()
    V.check_us_size(rep, d)
    assert len(rep.rows) == 1 and rep.rows[0][0] == V.US_SIZE_ROW and rep.rows[0][3] in ("PASS", "WARN"), rep.rows   # 실패가 없어요
    return rep.rows[0][3], rep.rows[0][1]


def good(t, **kw):
    return rec(t, **{"qrev": 10, "qrevD": "2026-09-30", "qeq": 20, "qeqD": "2026-09-30", **kw})


REC = {"v": 1, "unit": "USD", "n": 3, "usd": 2, "qrev": 2, "qeq": 2, "noData": {"qrev": 1, "qeq": 1}, "pending": 0, "why": {"qrev": {"fcur": 1}, "qeq": {"fcur": 1}},
       "cached": 2, "perRun": 300, "asked": 2, "req": 2, "ok": 2, "empty": 0, "err": 0, "time": 0, "stop": None, "kept": 0}


def test_gate_passes_an_old_file_a_good_one_and_a_planned_staged_fill():
    assert gate(data_of([rec("AAA")])) == ("PASS", "칸 없음 (이 칸을 싣기 전의 파일 · 앱의 종목 순위는 미국 최소 크기 없이)")
    st, val = gate(data_of([good("AAA"), good("BBB"), rec("CCC", fcur="EUR"), rec("ETF", etf=True)], REC))
    assert st == "PASS" and val.startswith("매출 2 · 자본 2 / 달러 재무제표 회사 2 (아직 받지 않은 곳 빼고 100.0% · 100.0%)") and "fcur 1" in val, val
    assert "아직 받지 않음 0 (앱의 미국 최소 크기 켜짐)" in val, val
    staged = dict(REC, why={"qrev": {"wait": 1, "time": 1}, "qeq": {"wait": 1, "time": 1}}, cached=2, usd=4, pending=2)   # 첫 실행: 300곳씩 (경고 아님)
    st, val = gate(data_of([good("AAA"), good("BBB"), rec("CCC"), rec("DDD")], staged))
    assert st == "PASS" and "wait 1" in val and "아직 받지 않음 2 (앱의 미국 최소 크기 꺼짐 · 다 받으면 켜져요)" in val, val


@pytest.mark.parametrize("rows,rec_,word", [
    ([good("AAA"), rec("BBB")], REC, "채움이 90% 아래"),
    ([good("AAA"), good("BBB", qeqD="2026-01-01")], REC, "BBB qeqD 2026-01-01"),
    ([good("AAA"), good("BBB", qrevD="2026-11-21")], REC, "BBB qrevD 2026-11-21"),
    ([good("AAA"), good("BBB", qeq="20")], REC, "BBB qeq 숫자 아님"),
    ([good("AAA"), good("BBB", qeq=True)], REC, "BBB qeq 숫자 아님"),
    ([good("AAA"), {k: v for k, v in good("BBB").items() if k != "qrevD"}], REC, "BBB qrev 짝 없음"),
    ([good("AAA"), good("BBB"), good("CCC", fcur="EUR")], REC, "달러 재무제표 회사가 아닌 행에 칸 1: CCC"),
    ([good("AAA"), good("ETF", etf=True)], REC, "달러 재무제표 회사가 아닌 행에 칸 1: ETF"),
    ([good("AAA")], None, "usSize 기록이 없거나 모양이 틀림"),
    ([rec("AAA")], {"v": 1, "unit": "USD", "stopped": "KeyError"}, "단계가 멈춤 (KeyError)"),
    ([rec("AAA")], {"v": 1, "unit": "USD", "stopped": "notRun"}, "단계가 멈춤 (notRun)"),
    ([good("AAA"), good("BBB")], dict(REC, stop="야후 거절 (429 · T1)", stopKind="429"), "야후 거절(429)로 받기를 멈춤 (야후 거절 (429 · T1))"),
    ([good("AAA"), good("BBB")], dict(REC, stop="처음 받지 못한 회사의 빈 답 · 오류가 3번 이어짐 (마지막 T5)", stopKind="empty"),
     "빈 답이 이어지는 회사가 있어 받기를 멈춤 (처음 받지 못한"),
    ([good("AAA"), good("BBB")], {k: v for k, v in REC.items() if k != "pending"}, "usSize.pending 이 개수가 아님"),
    ([good("AAA"), good("BBB")], dict(REC, pending=-1), "usSize.pending 이 개수가 아님 (-1)"),
    ([good("AAA"), good("BBB")], dict(REC, pending=True), "usSize.pending 이 개수가 아님"),
])
def test_gate_warns_and_never_fails(rows, rec_, word):
    st, val = gate(data_of(rows, rec_))
    assert st == "WARN" and word in val, val


def test_gate_warns_when_pending_rises_again_after_a_complete_fill():
    rep = V.Report()
    V.check_us_size(rep, data_of([good("AAA"), rec("BBB")], dict(REC, pending=1, why={"qeq": {"wait": 1}, "qrev": {"wait": 1}})),
                    {"usSize": dict(REC, pending=0)})
    assert rep.rows[0][3] == "WARN" and "pending 이 지난 발행본의 0 에서 1 으로 올라감" in rep.rows[0][1], rep.rows
    for prev in (None, {"usSize": dict(REC, pending=4)}, {"usSize": {"v": 1, "stopped": "notRun"}}, {}):
        rep = V.Report()
        V.check_us_size(rep, data_of([good("AAA"), rec("BBB")], dict(REC, pending=1, why={"qeq": {"wait": 1}, "qrev": {"wait": 1}})), prev)
        assert rep.rows[0][3] == "PASS", (prev, rep.rows)                                    # 채우는 중 · 지난 발행본에 칸 없음: 경고 아님


def test_gate_warns_when_its_own_code_breaks(monkeypatch):
    monkeypatch.setattr(V, "us_size_bad", lambda s, p: 1 / 0)
    st, val = gate(data_of([good("AAA")], REC))
    assert st == "WARN" and "ZeroDivisionError" in val


def test_gate_row_runs_in_the_publish_check_and_is_warn_only():
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert "    check_us_size(rep, data, pdata)" in src
    body = src[src.index("def _check_us_size"):src.index("def rec_stopped")]
    assert "rep.add(US_SIZE_ROW, True," in body and body.count("rep.add(") == 2 and "False" not in body.replace("warn=bool(warns)", "")
    assert not math.isnan(V.US_SIZE_FILL_WARN) and V.US_SIZE_FILL_WARN == 90.0
