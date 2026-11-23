# -*- coding: utf-8 -*-
"""v19.5b 후속 — 미국 회사의 최근 분기 매출 · 자본 (fetch_data.us_size_*, 관문 validate_data.check_us_size). Jack, 2026-11-13: "v19.5b's
US minimum sizes (25억원 of quarterly revenue, 100억원 of equity, at the day's rate) need a small data PR first."

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 관문 줄은 그대로):
- 야후 분기 표에서 가장 최근 분기의 값과 그 분기 말 날짜 (빈 값 · 무한 · 날짜가 아닌 칸은 건너뜀 · 정수 달러)
- 재무제표 통화가 달러인 회사만 (달러가 아니면 fcur · 모르면 cur · ETF · 펀드는 칸 없음) — 통화를 섞지 않아요
- 받지 못한 표는 보관본의 값을 그대로 (그 분기 말 날짜와 함께) · 다음 실행이 다시 받아요 · 보관본도 없으면 빈 칸과 이유
- 분기 말이 미국 기준일보다 200일 넘게 앞이거나 뒤면 빈 칸 · 0 · 음수(자본잠식)는 그대로
- 보관본: 7일 안의 항목은 다시 받지 않아요 · 지난 항목은 한 번에 상한까지 오래된 것부터 · 시간 상한 · 두 번째 차례 (쉬었다가)
- 로그와 data.json usSize: 채운 수 · 이유별 수 · 이름 (크게) · 단계가 멈추면 모두 비우고 기록 (발행은 이어가요)
- fetch_us 가 행에 붙이고 meta 에 기록을 담아요 · 설명 글(UNITS)과 기록에 관문의 nan · None · null 낱말이 없어요
- 관문: 경고만 (예전 파일은 통과 · 채움 90% 아래 · 모양 · 달러가 아닌 회사의 칸 · 멈춤 · 검사 오류도 경고) — 실패 줄이 없어요
"""
import datetime as dt
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


def stmts(rev=(1.2e9, 1.1e9, 1.0e9), eq=(5.0e9, 4.9e9, 4.8e9)):
    inc = table({"TotalRevenue": list(rev), "CostOfRevenue": [1.0, 1.0, 1.0]}) if rev is not None else pd.DataFrame()
    bal = table({"StockholdersEquity": [x + 1e8 for x in eq], "CommonStockEquity": list(eq)}) if eq is not None else pd.DataFrame()
    return {"income": inc, "balance": bal}


def rec(t, **kw):
    return {"t": t, "cls": "us", "price": 100.0, "etf": False, **kw}


# ── 표에서 값 고르기 ──
def test_pick_takes_the_newest_quarter_with_a_finite_number():
    df = table({"TotalRevenue": [np.nan, 1.1e9, 1.0e9], "CommonStockEquity": [np.inf, -3.4665e7, 2e8]})
    assert F.us_size_pick(df, "TotalRevenue") == ["2026-06-30", 1100000000]
    assert F.us_size_pick(df, "CommonStockEquity") == ["2026-06-30", -34665000]          # 무한은 건너뛰고 음수는 그대로
    assert F.us_size_pick(df, "StockholdersEquity") is None                              # 줄 없음
    assert F.us_size_pick(pd.DataFrame(), "TotalRevenue") is None and F.us_size_pick(None, "TotalRevenue") is None
    odd = pd.DataFrame({pd.NaT: [5.0], Q1: [7.4]}, index=["TotalRevenue"])
    assert F.us_size_pick(odd, "TotalRevenue") == ["2026-03-31", 7]                    # 날짜가 아닌 칸은 건너뛰고 정수로 반올림
    assert F.US_SIZE_ROWS == (("qrev", "income", "TotalRevenue"), ("qeq", "balance", "CommonStockEquity"))


def test_entry_keeps_the_old_value_of_a_table_that_did_not_come():
    old = {"at": "2026-11-01", "qrev": ["2026-06-30", 900], "qeq": ["2026-06-30", 800]}
    e = F.us_size_entry(stmts(), old, TODAY)
    assert e == {"at": "2026-11-23", "qrev": ["2026-09-30", 1200000000], "qeq": ["2026-09-30", 5000000000]}
    e = F.us_size_entry(stmts(rev=None), old, TODAY)                                    # 손익계산서가 빈 표 (반기 보고 회사 · 받지 못함)
    assert e == {"at": "2026-11-23", "qrev": ["2026-06-30", 900], "qeq": ["2026-09-30", 5000000000], "old": ["qrev"], "due": True}
    e = F.us_size_entry(None, old, TODAY)                                                # 받다가 오류
    assert e["qrev"] == ["2026-06-30", 900] and e["qeq"] == ["2026-06-30", 800] and e["due"] is True and e["old"] == ["qrev", "qeq"]
    e = F.us_size_entry({"income": table({"CostOfRevenue": [1.0, 1.0, 1.0]}), "balance": stmts()["balance"]}, old, TODAY)
    assert e["qrev"] is None and e["no"] == {"qrev": "noRow"} and "due" not in e         # 표는 왔는데 줄이 없음: 예전 값을 쓰지 않아요
    e = F.us_size_entry(None, {"at": "2026-11-01", "qrev": None, "no": {"qrev": "noRow"}}, TODAY)
    assert e["qrev"] is None and e["qeq"] is None and e["no"] == {"qrev": "noRow"} and e["due"] is True


def test_due_new_retry_stale():
    assert F.us_size_due(None, TODAY) == "new" and F.us_size_due({"at": "x"}, TODAY) == "new"
    assert F.us_size_due({"at": "2026-11-24"}, TODAY) == "new"                         # 받은 날이 오늘 뒤: 깨진 항목
    assert F.us_size_due({"at": "2026-11-22", "due": True}, TODAY) == "retry"
    assert F.us_size_due({"at": "2026-11-16"}, TODAY) == "stale" and F.us_size_due({"at": "2026-11-17"}, TODAY) is None
    assert F.US_SIZE_FRESH_DAYS == 7


def test_fields_only_for_dollar_filers_and_recent_quarters():
    e = {"at": "2026-11-20", "qrev": ["2026-09-30", 0], "qeq": ["2026-09-30", -343000000]}
    assert F.us_size_fields(e, "USD", US_PX) == ({"qrev": 0, "qrevD": "2026-09-30", "qeq": -343000000, "qeqD": "2026-09-30"},
                                                  {"qrev": None, "qeq": None})                  # 0 · 자본잠식도 그대로
    assert F.us_size_fields(e, "EUR", US_PX) == ({}, {"qrev": "fcur", "qeq": "fcur"})          # 통화를 섞지 않아요
    assert F.us_size_fields(e, None, US_PX) == ({}, {"qrev": "cur", "qeq": "cur"})
    assert F.us_size_fields(None, "USD", US_PX) == ({}, {"qrev": "fail", "qeq": "fail"})
    assert F.us_size_fields({"at": "x", "qrev": None, "no": {"qrev": "noRow"}, "qeq": ["2026-09-30", 1]}, "USD", US_PX)[1] == {"qrev": "noRow", "qeq": None}
    edge = US_PX - dt.timedelta(days=F.US_SIZE_MAX_AGE_DAYS)
    old = {"qrev": [edge.isoformat(), 5], "qeq": [(edge - dt.timedelta(days=1)).isoformat(), 5]}
    assert F.us_size_fields(old, "USD", US_PX) == ({"qrev": 5, "qrevD": edge.isoformat()}, {"qrev": None, "qeq": "old"})
    assert F.us_size_fields({"qrev": ["2026-11-30", 5], "qeq": ["2026-09-30", 5.6]}, "USD", US_PX)[1]["qrev"] == "future"
    assert F.us_size_fields({"qrev": ["2026-09-30", float("nan")], "qeq": ["30/09/2026", 5]}, "USD", US_PX)[1] == {"qrev": "fail", "qeq": "fail"}
    assert F.US_SIZE_MAX_AGE_DAYS == V.US_SIZE_MAX_AGE == 200                             # 관문과 같은 상한


# ── 한 실행 (가짜 야후) ──
def info(fc):
    return {"financialCurrency": fc} if fc else {}


def step(tmp_path, out, infos, fetch, **kw):
    lines = []
    calls = []

    def f(t):
        calls.append(t)
        return fetch(t)
    old = F.log
    F.log = lines.append
    try:
        r = F.us_size_step(out, lambda t: infos.get(t), US_PX, kw.pop("today", TODAY), fetch=f, path=str(tmp_path / "us-size.json.gz"),
                           sleep=kw.pop("sleep", lambda s: None), **kw)
    finally:
        F.log = old
    return r, lines, calls


def test_step_fills_dollar_filers_and_names_every_blank(tmp_path):
    out = [rec("AAA"), rec("BBB"), rec("CCC"), rec("DDD", etf=True), rec("EEE"), rec("FFF"), rec("GGG", fund=True), rec("HHH"),
           rec("III", qrev=1, qrevD="2020-01-01")]                                          # 예전 칸이 남아 있으면 지워요
    infos = {"AAA": info("USD"), "BBB": info("EUR"), "DDD": info("USD"), "EEE": info("USD"), "FFF": info("USD"), "HHH": info("USD"), "III": info("TWD")}

    def fake(t):
        if t == "EEE":
            raise RuntimeError("boom")
        if t == "FFF":
            return stmts(rev=None)                                                          # 반기 보고 회사: 분기 손익계산서가 빔
        if t == "HHH":
            return stmts(rev=(np.nan, np.nan, 2e6), eq=(1e9, 1e9, 1e9))                     # 오래된 매출만 (3월 말 · 235일)
        return stmts()
    r, lines, calls = step(tmp_path, out, infos, fake)
    by = {x["t"]: x for x in out}
    assert by["AAA"] == rec("AAA", qrev=1200000000, qrevD="2026-09-30", qeq=5000000000, qeqD="2026-09-30")
    for t in ("BBB", "CCC", "DDD", "EEE", "GGG", "III"):
        assert not any(k in by[t] for k in ("qrev", "qrevD", "qeq", "qeqD")), t
    assert by["FFF"].get("qeq") == 5000000000 and "qrev" not in by["FFF"]
    assert by["HHH"].get("qeq") == 1000000000 and "qrev" not in by["HHH"]
    assert sorted(set(calls)) == ["AAA", "EEE", "FFF", "HHH"]                               # 달러 재무제표 회사만 받아요 (ETF · 펀드 · fcur · 통화 모름 빼고)
    assert calls.count("EEE") == 2 and calls.count("FFF") == 2 and calls.count("AAA") == 1   # 받지 못한 곳만 두 번째 차례에
    assert r["n"] == 7 and r["usd"] == 4 and r["qrev"] == 1 and r["qeq"] == 3, r
    assert r["why"] == {"qrev": {"fcur": 2, "cur": 1, "fail": 2, "old": 1}, "qeq": {"fcur": 2, "cur": 1, "fail": 1}}, r["why"]
    assert (r["asked"], r["ok"], r["part"], r["err"], r["time"], r["kept"]) == (4, 2, 1, 1, 0, 0), r
    assert r["unit"] == "USD" and "CommonStockEquity" in r["src"]
    head = [x for x in lines if "미국 회사 크기" in x and "채움" in x]
    assert len(head) == 1 and head[0].startswith("  !! ") and "오류 1 (RuntimeError 1)" in head[0], head
    assert any(x.startswith("  · 미국 qrev") and "BBB, III" in x for x in lines), lines           # 달러가 아닌 회사: 알려진 빈 칸 (조용한 줄 아님 · 이름)
    assert any(x.startswith("  !! 미국 qrev") and "EEE, FFF" in x for x in lines) and any(x.startswith("  !! 미국 qrev") and "HHH" in x and "200일" in x for x in lines)
    assert any(x.startswith("  !! 미국 qeq") and "CCC" in x for x in lines)                    # 통화를 모름
    json.dumps(out, allow_nan=False)                                                            # NaN 이 없어요
    assert all(isinstance(x.get(k), int) for x in out for k in ("qrev", "qeq") if k in x)


def test_failed_fetch_keeps_the_dated_cache_and_fresh_entries_are_not_fetched_again(tmp_path):
    out = [rec("AAA"), rec("BBB")]
    infos = {"AAA": info("USD"), "BBB": info("USD")}
    step(tmp_path, out, infos, lambda t: stmts())
    out = [rec("AAA"), rec("BBB")]
    r, lines, calls = step(tmp_path, out, infos, lambda t: stmts(), today=TODAY + dt.timedelta(days=6))
    assert calls == [] and r["asked"] == 0 and r["qeq"] == 2                                   # 7일 안: 받지 않고 보관본
    out = [rec("AAA"), rec("BBB")]
    r, lines, calls = step(tmp_path, out, infos, lambda t: (_ for _ in ()).throw(OSError("down")), today=TODAY + dt.timedelta(days=8))
    assert sorted(calls) == ["AAA", "AAA", "BBB", "BBB"] and r["err"] == 2 and r["kept"] == 2
    assert all(x["qeqD"] == "2026-09-30" and x["qeq"] == 5000000000 for x in out)              # 받지 못해도 날짜가 붙은 보관본 값
    back = F.load_us_size(str(tmp_path / "us-size.json.gz"))
    assert back["AAA"]["due"] is True and back["AAA"]["old"] == ["qrev", "qeq"]                # 다음 실행이 다시 받아요
    out = [rec("AAA"), rec("BBB")]
    r, lines, calls = step(tmp_path, out, infos, lambda t: stmts(), today=TODAY + dt.timedelta(days=9))
    assert sorted(calls) == ["AAA", "BBB"] and r["ok"] == 2 and "due" not in F.load_us_size(str(tmp_path / "us-size.json.gz"))["AAA"]


def test_refresh_cap_takes_the_oldest_first_and_new_ones_always(tmp_path):
    path = tmp_path / "us-size.json.gz"
    cache = {t: {"at": d, "qrev": ["2026-09-30", 1], "qeq": ["2026-09-30", 1]} for t, d in
             (("AAA", "2026-11-10"), ("BBB", "2026-11-01"), ("CCC", "2026-11-05"), ("DDD", "2026-11-20"), ("OLD", "2026-07-01"))}
    F.save_us_size(cache, str(path))
    out = [rec(t) for t in ("AAA", "BBB", "CCC", "DDD", "NEW")]
    infos = {t: info("USD") for t in ("AAA", "BBB", "CCC", "DDD", "NEW")}
    r, lines, calls = step(tmp_path, out, infos, lambda t: stmts(), refresh_max=1)
    assert sorted(calls) == ["BBB", "NEW"], calls                                             # 새 종목 + 가장 오래된 하나
    back = F.load_us_size(str(path))
    assert "OLD" not in back and back["AAA"]["at"] == "2026-11-10" and back["BBB"]["at"] == "2026-11-23"   # 120일 넘게 받지 않은 항목은 지워요
    assert r["qeq"] == 5


def test_time_limit_leaves_the_rest_for_the_next_run(tmp_path):
    t0 = [0.0]

    def clock():
        t0[0] += 100.0
        return t0[0]
    out = [rec(t) for t in ("AAA", "BBB", "CCC", "DDD")]
    infos = {t: info("USD") for t in ("AAA", "BBB", "CCC", "DDD")}
    r, lines, calls = step(tmp_path, out, infos, lambda t: stmts(), clock=clock, budget_s=250, passes=((0, 1),))
    assert len(calls) == 1 and r["time"] == 3 and r["why"]["qeq"] == {"time": 3}, r          # 한 곳만 받고 나머지는 시간 상한
    assert any(x.startswith("  !! 미국 qeq") and "시간 상한" in x for x in lines)


def test_second_pass_waits_then_goes_slower(tmp_path):
    slept = []
    seen = {}

    def flaky(t):
        seen[t] = seen.get(t, 0) + 1
        return stmts() if seen[t] > 1 else {"income": pd.DataFrame(), "balance": pd.DataFrame()}
    out = [rec("AAA")]
    r, lines, calls = step(tmp_path, out, {"AAA": info("USD")}, flaky, sleep=slept.append)
    assert slept == [20] and calls == ["AAA", "AAA"] and r["ok"] == 1 and out[0]["qeq"] == 5000000000
    assert F.US_SIZE_PASSES == ((0, 8), (20, 3))


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


def test_fetch_us_attaches_the_fields_and_records_them(tmp_path, monkeypatch):
    from test_us_own_close import _fetch
    monkeypatch.setattr(F, "_us_size_yahoo", lambda t: stmts(eq=(-3.4e8, 1e9, 1e9)) if t == "MSFT" else stmts())
    out, meta, lines, _prev = _fetch(tmp_path, monkeypatch, blank=set())
    by = {r["t"]: r for r in out}
    assert by["AAPL"]["qrev"] == 1200000000 and by["AAPL"]["qeqD"] == "2026-09-30" and by["MSFT"]["qeq"] == -340000000
    rec_ = meta["usSize"]
    assert rec_["usd"] == rec_["qrev"] == rec_["qeq"] == len([r for r in out if not r.get("etf")]) > 0, rec_
    assert (tmp_path / "us-size-v1.json.gz").exists()                                          # 시험의 임시 폴더 (US_INFO_PATH 옆)
    assert any("미국 회사 크기" in x and "채움" in x for x in lines)


def test_fetch_us_goes_on_when_the_step_breaks(tmp_path, monkeypatch):
    from test_us_own_close import _fetch

    def boom(*a, **k):
        raise ValueError("x")
    monkeypatch.setattr(F, "us_size_step", boom)
    out, meta, lines, _prev = _fetch(tmp_path, monkeypatch, blank=set())
    assert meta["usSize"] == {"v": 1, "unit": "USD", "stopped": "ValueError"} and out
    assert not any(k in r for r in out for k in ("qrev", "qeq"))


def test_text_passes_the_gate_word_check():
    bad = [p for p, v in V.text_values({k: F.UNITS[k] for k in ("qrev", "qeq", "usSize")}) if V.BAD_WORD.search(v)]
    assert bad == []
    rec_ = {"v": 1, "unit": "USD", "src": "yahoo quarterly statements (TotalRevenue, CommonStockEquity)", "why": {"qrev": {"fcur": 1}}}
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


REC = {"v": 1, "unit": "USD", "n": 3, "usd": 2, "qrev": 2, "qeq": 2, "why": {"qrev": {"fcur": 1}, "qeq": {"fcur": 1}},
       "asked": 2, "ok": 2, "part": 0, "err": 0, "time": 0, "kept": 0}


def test_gate_passes_an_old_file_and_a_good_one():
    assert gate(data_of([rec("AAA")])) == ("PASS", "칸 없음 (이 칸을 싣기 전의 파일 · 앱의 종목 순위는 미국 최소 크기 없이)")
    st, val = gate(data_of([good("AAA"), good("BBB"), rec("CCC", fcur="EUR"), rec("ETF", etf=True)], REC))
    assert st == "PASS" and val.startswith("매출 2 · 자본 2 / 달러 재무제표 회사 2 (100.0% · 100.0%)") and "매출 빈 칸 fcur 1" in val, val


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
])
def test_gate_warns_and_never_fails(rows, rec_, word):
    st, val = gate(data_of(rows, rec_))
    assert st == "WARN" and word in val, val


def test_gate_warns_when_its_own_code_breaks(monkeypatch):
    monkeypatch.setattr(V, "us_size_bad", lambda s, p: 1 / 0)
    st, val = gate(data_of([good("AAA")], REC))
    assert st == "WARN" and "ZeroDivisionError" in val


def test_gate_row_runs_in_the_publish_check_and_is_warn_only():
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert "    check_us_size(rep, data)" in src
    body = src[src.index("def _check_us_size"):src.index("def rec_stopped")]
    assert "rep.add(US_SIZE_ROW, True," in body and body.count("rep.add(") == 2 and "False" not in body.replace("warn=bool(warns)", "")
    assert not math.isnan(V.US_SIZE_FILL_WARN) and V.US_SIZE_FILL_WARN == 90.0
