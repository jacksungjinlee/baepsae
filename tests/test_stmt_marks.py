# -*- coding: utf-8 -*-
"""2026-11-12 (Jack): 관문 줄 '원화가 아닌 재무제표 표시가 직전 발행보다 사라지지 않음 (stmtCur)' — 더하기만.

DART 의 통화 칸을 못 읽은 날에는 corp.json 의 stmtCur 표시가 통째로 사라지고, 달러로 공시하는 국내 회사(두산밥캣 등)의 금액이
원으로 읽혀 경고 없이 사용자에게 가요. 직전 발행에서 표시가 있던 회사(오늘도 목록에 있는) 중 절반 넘게 사라지면 실패,
하나라도 사라지면 경고(회사가 통화를 바꿨을 수도 있어요 — 회사 하나가 모두의 발행을 막지 않게)."""
import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402
from test_validate import check, failed_names  # noqa: E402

NAME = "원화가 아닌 재무제표 표시가 직전 발행보다 사라지지 않음 (stmtCur)"
USD = ["241560", "008700", "900070", "950160", "950210"]          # 직전에 표시가 있던 회사 (시험용 코드)


def companies(marked, also=()):
    """표시가 있는 회사(marked: {코드: 통화}) + 표시 없는 회사(also)."""
    out = [{"t": t, "nk": "회사" + t, "stmtCur": cur} for t, cur in marked.items()]
    return out + [{"t": t, "nk": "회사" + t, "rev": [1.0, 2.0, 3.0]} for t in also]


def run(prev_marked, cur_marked, cur_unmarked=(), prev_extra=None):
    rep = V.Report()
    prev = {"corp": {"companies": companies(prev_marked)}} if prev_extra is None else prev_extra
    V.check_stmt_marks(rep, companies(cur_marked, cur_unmarked), prev)
    row = next(r for r in rep.rows if r[0] == NAME)
    return row, rep


def is_fail(rep):
    return NAME in {r[0] for r in rep.failed}


def is_warn(rep):
    return NAME in {r[0] for r in rep.warned}


def test_same_marks_pass_quietly():
    marks = {t: "USD" for t in USD}
    row, rep = run(marks, marks)
    assert not is_fail(rep) and not is_warn(rep), rep.table()
    assert "직전 5곳 · 오늘도 목록에 5곳 · 표시가 사라짐 0" in rep.table()


def test_marks_vanishing_fails():
    """DART 통화 칸을 못 읽은 날: 다섯 곳 모두 표시가 없고 금액이 채워졌어요."""
    row, rep = run({t: "USD" for t in USD}, {}, cur_unmarked=USD)
    assert is_fail(rep), rep.table()
    assert "표시가 사라짐 5" in rep.table() and "241560 회사241560 (금액 있음)" in rep.table()


@pytest.mark.parametrize("lost, fail", [(0, False), (1, False), (2, False), (3, True), (4, True), (5, True)])
def test_more_than_half_lost_fails_and_any_loss_warns(lost, fail):
    prev = {t: "USD" for t in USD}
    cur = {t: "USD" for t in USD[lost:]}
    row, rep = run(prev, cur, cur_unmarked=USD[:lost])
    assert is_fail(rep) is fail, (lost, rep.table())
    assert is_warn(rep) is (lost > 0 and not fail), (lost, rep.table())


def test_exactly_half_is_a_warning_not_a_failure():
    prev = {t: "USD" for t in USD[:4]}
    row, rep = run(prev, {t: "USD" for t in USD[2:4]}, cur_unmarked=USD[:2])
    assert not is_fail(rep) and is_warn(rep)


def test_few_marks_never_fail():
    """직전에 표시된 회사가 셋 미만이면 모두 사라져도 경고만 (회사 하나 · 둘이 모두의 발행을 막지 않게)."""
    row, rep = run({"241560": "USD", "008700": "USD"}, {}, cur_unmarked=["241560", "008700"])
    assert not is_fail(rep) and is_warn(rep), rep.table()


def test_a_company_that_left_the_market_is_not_counted():
    prev = {t: "USD" for t in USD}
    row, rep = run(prev, {t: "USD" for t in USD[2:]})                  # 두 곳이 오늘 목록에 없음 (상장폐지)
    assert not is_fail(rep) and not is_warn(rep) and "오늘도 목록에 3곳 · 표시가 사라짐 0" in rep.table()
    row, rep = run(prev, {}, cur_unmarked=USD[2:])                     # 남은 세 곳 모두 표시가 사라짐 → 실패
    assert is_fail(rep)


def test_any_currency_other_than_won_is_a_mark_and_won_is_not():
    prev = {"241560": "USD", "900110": "CNY", "950170": "JPY", "900999": "XXX"}
    row, rep = run(prev, dict(prev))
    assert not is_fail(rep) and not is_warn(rep)
    row, rep = run(prev, {"241560": "USD", "900110": "KRW", "950170": "KRW", "900999": "KRW"})   # KRW 는 표시가 아니에요
    assert is_fail(rep) and "표시가 사라짐 3" in rep.table()
    row, rep = run({t: "KRW" for t in USD}, {}, cur_unmarked=USD)       # 직전의 KRW 는 비교 대상이 아니에요
    assert not is_fail(rep) and not is_warn(rep) and "직전 0곳" in rep.table()


def test_unreadable_previous_corp_fails_and_a_missing_one_is_skipped():
    row, rep = run({}, {}, prev_extra={"corpError": "FileNotFoundError: corp.json"})
    assert is_fail(rep) and "직전 corp.json 을 읽지 못했어요" in rep.table()
    rep = V.Report()
    V.check_stmt_marks(rep, companies({"241560": "USD"}), {"data": {}})  # 관문 밖에서 직전 corp 없이 부른 경우
    assert not is_fail(rep) and NAME in rep.table()


def test_the_gate_runs_the_row_only_against_a_previous_publication():
    cur, prev, final = good_pair()
    for c in prev["corp"]["companies"][:5]:
        c["stmtCur"] = "USD"
    bad = failed_names(check(cur, prev, final))
    assert NAME in bad                                                  # 직전에 다섯 곳, 오늘 없음 → 실패
    for c in cur["corp"]["companies"][:5]:
        c["stmtCur"] = "USD"
    assert NAME not in failed_names(check(cur, prev, final))
    rep = check(cur, None, final, mode="bootstrap")                     # 첫 실행 (직전 없음): 이 줄은 돌지 않아요
    assert NAME not in rep.table()


def test_previous_corp_is_read_loosely_and_main_records_why_it_could_not(tmp_path):
    (tmp_path / "corp.json").write_text('{"companies":[{"t":"241560","stmtCur":"USD","per":NaN}]}', encoding="utf-8")
    got = V.load_prev_corp(str(tmp_path), None)                         # 직전 파일의 NaN 이 오늘 발행을 막지 않아요
    assert got["companies"][0]["stmtCur"] == "USD"
    with pytest.raises(FileNotFoundError):
        V.load_prev_corp(str(tmp_path / "없음"), None)
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    i = src.index("def _main(")
    body = src[i:]
    assert 'prev["corp"] = load_prev_corp(a.prev_dir, a.prev_ref)' in body and 'prev["corpError"] = ' in body
    assert body.index('prev["corp"] = load_prev_corp') < body.index("special = None")      # 검사 전에 읽어요
