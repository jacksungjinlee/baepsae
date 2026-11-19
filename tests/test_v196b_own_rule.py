# -*- coding: utf-8 -*-
"""Jack 의 상시 규칙 (2026-11-19 ~17:45 KST, 그대로): "Standing rule for checks on our own processing: a single bad row is dropped or
blanked with a loud warning and the rest publishes. Block only when many rows fail in one run (set the number from recent runs and show it
in the PR) or when a value would show a wrong number."

#145 의 네 검사: 주요사항 공시 줄 모양 (issueShape · 줄을 빼요) · 유상증자 결의일이 공시일 뒤 (issueBd · bd 를 비워요) · insider role
(insiderRole · role 을 비우고 객체가 아닌 줄은 빼요) · 미국 ed · xd (usDates · 그 칸을 비워요). 나쁜 행은 validate_data 의 같은 함수가 골라요.
파이프라인은 쓰기 앞에서 빼거나 비우고 ownDrop 에 적어요. 관문: N 을 넘거나 틀린 숫자를 보일 값이 남으면 실패 · 그 밖은 경고 · 기록이 없는 예전
파일은 예전 규칙. 네트워크 없음."""
import copy
import datetime as dt
import inspect
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
import test_v196b_data as T  # noqa: E402

BASE = dt.date(2026, 10, 31)       # good_files 의 asOf
N = 5


def irow(i, **kw):
    r = {"rc": f"2026103000{i:04d}", "d": "20261030", "t": "005930", "nk": "삼성전자", "kind": "rights", "bd": None, "how": "others",
         "n": 1000 + i, "p": 1.5, "amt": None, "cor": False, "cls": "common"}
    r.update(kw)
    return r


def disc_of(issue=None, insider=None):
    return {"asOf": BASE.isoformat(), "newest": None, "listOk": True, "issue": [irow(1), irow(2)] if issue is None else issue,
            "issueOk": True, "nps": [],
            "insider": [{"rc": "20261030000444", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "가", "pos": "상무", "role": "임원",
                         "q": 10}] if insider is None else insider}


def rows_of(cur):
    got, rep = T.rows_of(cur)
    rep2 = V.Report()
    V.check_issue_bd(rep2, cur["disc"])
    got.update({r[0]: r for r in rep2.rows})
    rep.rows += rep2.rows
    rep.details += rep2.details
    return got, rep


def files_with(disc=None, us=None):
    cur = T.good_files()[0]
    if disc is not None:
        cur["disc"] = disc
    if us is not None:
        for s in cur["data"]["stocks"]:
            if s["t"] in us:
                s.update(us[s["t"]])
    return cur


ISSUE, ROLE, US, BD = T.ISSUE_ROW, T.ROLE_ROW, T.US_ROW, V.ISSUE_BD_ROW


def test_thresholds_and_keys_are_the_stated_ones():
    """N 은 최근 실행에서 (PR #145 의 표: data 브랜치 발행 25번 · 이 브랜치 시험 실행 5번 — 모두 0) max(5, 3 × 0) = 5."""
    assert (V.ISSUE_SHAPE_MAX, V.ISSUE_BD_MAX, V.INSIDER_ROLE_MAX, V.US_DATE_MAX) == (N, N, N, N)
    assert (V.ISSUE_SHAPE_KEY, V.ISSUE_BD_KEY, V.INSIDER_ROLE_KEY, V.US_DATE_KEY) == ("issueShape", "issueBd", "insiderRole", "usDates")
    assert V.OWN_ROWS_SHOW == 30


# ── 같은 함수 (관문 파일) ─────────────────────────────────────────────────

def test_the_shared_functions_pick_the_bad_rows():
    rows = [irow(1), irow(2, p=-1.0), irow(3, nk=""), irow(4), irow(4), "x"]
    bad = V.issue_bad_rows(rows, BASE)
    assert [(b[0], b[1], b[3]) for b in bad] == [(1, "20261030000002", True), (2, "20261030000003", False), (3, "20261030000004", False),
                                                 (4, "20261030000004", False), (5, "#5", False)]
    assert "같은 접수번호가 2번" in bad[2][2] and "p -1.0" in bad[0][2]
    assert V.issue_bd_bad_rows([irow(1, bd="20261031"), irow(2, bd="20261030"), irow(3, bd="20261031", wd=True), irow(4, kind="cb", bd="20261031",
                                                                                                                      how=None, n=None, cls=None)]) \
        == [(0, "20261030000001", "bd 20261031 > d 20261030", True, "bd")]
    ins = [{"rc": "1", "role": "임원"}, {"rc": "2", "role": "임원 · 주요주주"}, 7, {"rc": "4", "role": None}, {"rc": "5"}]
    assert [(b[0], b[3], b[4]) for b in V.insider_bad_rows(ins)] == [(1, False, "role"), (2, True, None)]
    st = [{"t": "AAPL", "cls": "us", "ed": "2027-01-28", "xd": "2026/11/12"}, {"t": "005930", "cls": "kr", "xd": "2026-11-27"},
          {"t": "MSFT", "cls": "us", "ed": None, "xd": ""}]
    assert [(b[0], b[1], b[4], b[3]) for b in V.us_date_bad_rows(st)] == [(0, "AAPL xd", "xd", False), (1, "005930 xd", "xd", False)]
    for junk in (None, "x", 5, [None, 1, "a"], [{}]):
        V.issue_bad_rows(junk, BASE), V.issue_bd_bad_rows(junk), V.insider_bad_rows(junk), V.us_date_bad_rows(junk)


def test_issue_row_problems_keeps_its_old_answers():
    assert V.issue_row_problems(irow(1), BASE) == []
    assert V.issue_row_problems("x", BASE) == ['줄이 객체가 아님 "x"']
    assert V.issue_row_problems(irow(1, p=0), BASE) == ["p 0"]


# ── 파이프라인: 빼거나 비우고, 크게 남기고, ownDrop 에 적어요 ─────────────────────

def test_one_bad_issue_row_is_dropped_logged_and_the_rest_publishes(capsys):
    disc = disc_of([irow(1), irow(2, p="1.5%"), irow(3)])
    F.own_check_disc(disc, BASE)
    assert [r["rc"] for r in disc["issue"]] == ["20261030000001", "20261030000003"]
    assert disc["ownDrop"][V.ISSUE_SHAPE_KEY] == {"n": 1, "rows": [["20261030000002", 'p "1.5%"']]}
    assert disc["ownDrop"][V.ISSUE_BD_KEY] == {"n": 0, "rows": []} and disc["ownDrop"][V.INSIDER_ROLE_KEY] == {"n": 0, "rows": []}
    log = capsys.readouterr().out
    assert '  !! 주요사항 공시 줄 모양 (issue): 1건 빼고 발행 — 20261030000002 (p "1.5%") (disc.json ownDrop.issueShape · 관문 경고 · 5건을 넘으면 실패)' in log
    assert "· 유상증자 이사회 결의일이 공시일 뒤 (issue bd): 0건 비움 (bd)" in log and "· 임원 · 주요주주 역할 (insider role): 0건 빼거나 비움" in log
    got, _ = rows_of(files_with(disc))
    assert got[ISSUE][3] == "WARN" and "파이프라인이 뺀 줄 1개 (20261030000002 (p \"1.5%\"))" in got[ISSUE][1], got[ISSUE]
    json.dumps(disc, allow_nan=False)


def test_a_clean_run_records_zero_and_passes(capsys):
    disc = F.own_check_disc(disc_of(), BASE)
    assert disc["ownDrop"] == {k: {"n": 0, "rows": []} for k in (V.ISSUE_SHAPE_KEY, V.ISSUE_BD_KEY, V.INSIDER_ROLE_KEY)}
    got, rep = rows_of(files_with(disc))
    assert [got[k][3] for k in (ISSUE, ROLE, BD)] == ["PASS", "PASS", "WARN"], rep.table()   # BD: 결의일 빈 줄 (원문을 아직 못 읽음) 경고는 그대로
    assert "· 주요사항 공시 줄 모양 (issue): 0건 빼고 발행" in capsys.readouterr().out


def test_more_than_n_dropped_rows_fail_the_gate(capsys):
    disc = disc_of([irow(i, p=0) for i in range(1, N + 2)] + [irow(99)])
    F.own_check_disc(disc, BASE)
    assert len(disc["issue"]) == 1 and disc["ownDrop"][V.ISSUE_SHAPE_KEY]["n"] == N + 1
    log = capsys.readouterr().out
    assert f"{N + 1}건 빼고 발행" in log and "5건을 넘어 관문에서 실패해 발행하지 않아요" in log
    got, _ = rows_of(files_with(disc))
    assert got[ISSUE][3] == "FAIL" and f"이번 실행에 뺀 줄 {N + 1}개 — {N}개를 넘어요" in got[ISSUE][1]
    disc["ownDrop"][V.ISSUE_SHAPE_KEY]["n"] = N                                 # 딱 N 이면 경고
    disc["ownDrop"][V.ISSUE_SHAPE_KEY]["rows"] = disc["ownDrop"][V.ISSUE_SHAPE_KEY]["rows"][:N]
    assert rows_of(files_with(disc))[0][ISSUE][3] == "WARN"


def test_a_remaining_bad_value_that_shows_a_wrong_number_fails():
    disc = F.own_check_disc(disc_of(), BASE)
    disc["issue"].append(irow(7, p=-3.0))                                      # 빼는 단계가 실패한 파일
    got, _ = rows_of(files_with(disc))
    assert got[ISSUE][3] == "FAIL" and "틀린 숫자를 보일 수 있어요 (20261030000007 p -3.0)" in got[ISSUE][1]
    disc["issue"][-1] = irow(7, nk="")                                         # 숫자가 아닌 칸 (이름) — 경고
    got, _ = rows_of(files_with(disc))
    assert got[ISSUE][3] == "WARN" and "숫자를 보이지 않아요 (20261030000007 nk \"\")" in got[ISSUE][1]


def test_old_files_without_a_record_keep_the_old_rule():
    disc = disc_of([irow(1), irow(2, nk="")])                                  # ownDrop 이 없는 파일
    assert rows_of(files_with(disc))[0][ISSUE][3] == "FAIL"
    disc["ownDrop"] = {V.ISSUE_SHAPE_KEY: {"n": 1, "rows": []}}               # 기록 모양이 틀림 → 예전 규칙 + 경고
    got, _ = rows_of(files_with(disc))
    assert got[ISSUE][3] == "FAIL" and "ownDrop.issueShape 기록 모양이 틀림" in got[ISSUE][1]


def test_issue_list_and_flag_shape_only_warn_in_new_files():
    disc = F.own_check_disc(disc_of(), BASE)
    disc["issueOk"] = "yes"
    got, _ = rows_of(files_with(disc))
    assert got[ISSUE][3] == "WARN" and 'issueOk "yes"' in got[ISSUE][1]
    d2 = disc_of()
    d2["issue"] = "x"
    F.own_check_disc(d2, BASE)
    assert d2["issue"] == [] and d2["ownDrop"][V.ISSUE_SHAPE_KEY] == {"n": 1, "rows": [["issue", "목록이 아님 (str) → 빈 목록"]]}


# ── 유상증자 결의일이 공시일 뒤 (bd 를 비워요) ──────────────────────────────

def test_a_board_date_after_the_filing_is_blanked_and_recorded(capsys):
    disc = disc_of([irow(1, bd="20261031"), irow(2, bd="20261029"), irow(3, bd="20261101", bonus=True)])
    F.own_check_disc(disc, BASE)
    assert [r["bd"] for r in disc["issue"]] == [None, "20261029", None]
    assert disc["ownDrop"][V.ISSUE_BD_KEY] == {"n": 2, "rows": [["20261030000001", "bd 20261031 > d 20261030"],
                                                               ["20261030000003", "bd 20261101 > d 20261030"]]}
    assert "  !! 유상증자 이사회 결의일이 공시일 뒤 (issue bd): 2건 비움 (bd) — 20261030000001 (bd 20261031 > d 20261030)" in capsys.readouterr().out
    got, _ = rows_of(files_with(disc))
    assert got[BD][3] == "WARN" and "파이프라인이 비운 결의일 2개" in got[BD][1] and got[ISSUE][3] == "PASS"


def test_board_dates_over_n_fail_and_a_remaining_one_fails():
    disc = disc_of([irow(i, bd="20261031") for i in range(1, N + 2)])
    F.own_check_disc(disc, BASE)
    assert rows_of(files_with(disc))[0][BD][3] == "FAIL"
    disc = F.own_check_disc(disc_of([irow(1, bd="20261029")]), BASE)
    disc["issue"][0]["bd"] = "20261031"                                        # 비우는 단계가 실패 — 결정의 숫자에 붙는 날짜
    got, _ = rows_of(files_with(disc))
    assert got[BD][3] == "FAIL" and "공시일 뒤 결의일 1" in got[BD][1]


def test_fill_leaves_after_filing_dates_to_the_shared_check():
    """fill_issue_bd 는 1년 창만 봐요 — 공시일 뒤인 날은 그대로 쓰고 own_check_disc 가 같은 함수로 비워 세요 (한 번에 많이 틀리면 관문 실패)."""
    import test_v196b_issue_bd as B
    row = B.irow("20261012000188", "20261012", cls="common")
    c = B.Client({"20261012000188": B.doc_on("20261013")})
    out = F.fill_issue_bd(B.disc_of([row]), c, dt.date(2026, 11, 15))
    assert row["bd"] == "20261013" and out["limited"] == 0
    disc = {"asOf": "2026-11-15", "issue": [row], "issueOk": True, "insider": []}
    F.own_check_disc(disc, dt.date(2026, 11, 15))
    assert disc["issue"] == [row] and row["bd"] is None and disc["ownDrop"][V.ISSUE_BD_KEY]["n"] == 1
    assert F.issue_bd_range_why("20261013", "20261012") == "결의일 20261013 이 공시일 20261012 뒤예요"      # 같은 함수로 봐요
    assert F.issue_bd_window_why("20261013", "20261012") is None


# ── insider role (role 을 비워요 · 객체가 아닌 줄은 빼요) ─────────────────────

def test_a_bad_role_is_blanked_and_a_non_object_row_is_dropped(capsys):
    ins = [{"rc": "20261030000444", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "가", "pos": "상무", "role": "임원 · 주요주주", "q": 1},
           "junk", {"rc": "20261030000446", "d": "20261030", "t": "005930", "nk": "삼성전자", "nm": "다", "pos": "", "role": None, "q": 1}]
    disc = disc_of(insider=ins)
    F.own_check_disc(disc, BASE)
    assert [r["role"] for r in disc["insider"]] == [None, None] and len(disc["insider"]) == 2
    assert disc["ownDrop"][V.INSIDER_ROLE_KEY] == {"n": 2, "rows": [["20261030000444", 'role "임원 · 주요주주"'], ["#1", '객체가 아닌 줄 "junk"']]}
    assert "  !! 임원 · 주요주주 역할 (insider role): 2건 빼거나 비움" in capsys.readouterr().out
    got, _ = rows_of(files_with(disc))
    assert got[ROLE][3] == "WARN" and "파이프라인이 빼거나 비운 줄 2개" in got[ROLE][1]


def test_role_over_n_fails_a_remaining_non_object_fails_a_remaining_bad_role_warns():
    ins = [{"rc": f"2026103000{i:04d}", "pos": "상무", "role": "임원/주요주주", "q": 1} for i in range(N + 1)]
    disc = F.own_check_disc(disc_of(insider=ins), BASE)
    assert rows_of(files_with(disc))[0][ROLE][3] == "FAIL"
    disc = F.own_check_disc(disc_of(), BASE)
    disc["insider"].append("junk")                                             # 공시 탭이 그 줄의 숫자를 읽어요
    assert rows_of(files_with(disc))[0][ROLE][3] == "FAIL"
    disc["insider"][-1] = {"rc": "20261030000447", "pos": "상무", "role": "임원/주요주주", "q": 1}
    got, _ = rows_of(files_with(disc))
    assert got[ROLE][3] == "WARN" and "숫자를 보이지 않아요" in got[ROLE][1]
    del disc["ownDrop"]                                                        # 예전 파일: 예전 규칙 (실패)
    assert rows_of(files_with(disc))[0][ROLE][3] == "FAIL"


# ── 미국 ed · xd (그 칸만 비워요 · 종목은 그대로) ─────────────────────────────

def test_bad_us_dates_are_blanked_stocks_stay_and_the_record_joins_other_keys(capsys):
    cur = T.good_files()[0]
    stocks = cur["data"]["stocks"]
    us = [s for s in stocks if s["cls"] == "us"]
    kr = [s for s in stocks if s["cls"] == "kr"]
    us[0]["ed"], us[1]["xd"], kr[0]["xd"] = "2027/01/26", "2026-02-30", "2026-11-27"
    payload = {"asOf": cur["data"]["asOf"], "stocks": stocks, "ownDrop": {"usClass": {"n": 0, "rows": []}}}
    n0 = len(stocks)
    F.own_us_dates(payload)
    assert len(payload["stocks"]) == n0 and "ed" not in us[0] and "xd" not in us[1] and "xd" not in kr[0]
    assert payload["ownDrop"]["usClass"] == {"n": 0, "rows": []}                # claude/own-check-rule 의 칸은 그대로
    assert payload["ownDrop"][V.US_DATE_KEY]["n"] == 3
    assert "  !! 미국 일정 (ed 실적 발표일 · xd 배당락일): 3건 비움" in capsys.readouterr().out
    cur["data"]["ownDrop"] = payload["ownDrop"]
    got, _ = rows_of(cur)
    assert got[US][3] == "WARN" and "파이프라인이 비운 값 3개" in got[US][1]


def test_us_dates_over_n_fail_and_a_remaining_one_only_warns():
    cur = T.good_files()[0]
    us = [s for s in cur["data"]["stocks"] if s["cls"] == "us"]
    for s in us[:N + 1]:
        s["ed"] = "soon"
    payload = {"stocks": cur["data"]["stocks"]}
    F.own_us_dates(payload)
    cur["data"]["ownDrop"] = payload["ownDrop"]
    assert rows_of(cur)[0][US][3] == "FAIL"
    cur = T.good_files()[0]
    cur["data"]["ownDrop"] = {V.US_DATE_KEY: {"n": 0, "rows": []}}
    next(s for s in cur["data"]["stocks"] if s["cls"] == "kr")["xd"] = "2026-11-27"   # 남은 값 — 일정의 날짜라 숫자가 아니에요
    got, _ = rows_of(cur)
    assert got[US][3] == "WARN" and "숫자를 보이지 않아요" in got[US][1]
    del cur["data"]["ownDrop"]
    assert rows_of(cur)[0][US][3] == "FAIL"                                     # 예전 파일: 예전 규칙


# ── 배선 · 발행 파일 ─────────────────────────────────────────────────────

def test_main_runs_the_checks_right_before_each_write():
    src = inspect.getsource(F.main)
    a = src.index("own_us_dates(payload)")
    assert a < src.index("write_json(OUT, payload)") and src.index("payload.update(sp_fields)") < a
    b = src.index("own_check_disc(disc, today)")
    assert src.index('disc["publishedAt"] = published_at') < b < src.index("write_json(OUT_DISC, disc)")


def test_the_records_are_strict_json_with_the_shared_shape():
    disc = disc_of([irow(i, p=0) for i in range(40)])
    F.own_check_disc(disc, BASE)
    rec = disc["ownDrop"][V.ISSUE_SHAPE_KEY]
    assert rec["n"] == 40 and len(rec["rows"]) == 30 and all(isinstance(x, list) and len(x) == 2 for x in rec["rows"])
    assert V.own_rows_get(disc, V.ISSUE_SHAPE_KEY)[0] == "ok"
    json.dumps(disc, allow_nan=False)
    assert "외 10건" in V.own_rows_text(rec["rows"], rec["n"])


def test_own_checks_drop_disclosure_rows_never_stocks():
    """리뷰 주의 (claude/own-check-rule): 배당 증명 목록(v19.1i)의 국내 종목 행을 빼면 그 검사가 깨져요 — 여기서는 disc.json 의 공시 줄만 빼고,
    data.json 은 미국 ed · xd 칸만 비워요."""
    cur = T.good_files()[0]
    before = copy.deepcopy(cur["data"]["stocks"])
    F.own_us_dates({"stocks": cur["data"]["stocks"]})
    assert [s["t"] for s in cur["data"]["stocks"]] == [s["t"] for s in before]
    src = inspect.getsource(F.own_check_disc)
    assert "stocks" not in src
