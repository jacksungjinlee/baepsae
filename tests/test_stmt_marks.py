# -*- coding: utf-8 -*-
"""2026-11-12 (Jack): 관문 줄 '원화가 아닌 재무제표 표시가 직전 발행보다 사라지지 않음 (stmtCur)' — 더하기만.

DART 의 통화 칸을 못 읽은 날에는 corp.json 의 stmtCur 표시가 통째로 사라지고, 달러로 공시하는 국내 회사(두산밥캣 등)의 금액이
원으로 읽혀 경고 없이 사용자에게 가요. 직전 발행에서 표시가 있던 회사(오늘도 목록에 있는) 중 절반 넘게 사라지면 실패,
하나라도 사라지면 경고(회사가 통화를 바꿨을 수도 있어요 — 회사 하나가 모두의 발행을 막지 않게)."""
import copy
import json
import os
import subprocess
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


def test_unreadable_or_missing_previous_corp_fails():
    row, rep = run({}, {}, prev_extra={"corpError": "FileNotFoundError: corp.json"})
    assert is_fail(rep) and "직전 corp.json 을 읽지 못했어요" in rep.table()
    for prev in ({"data": {}}, {"data": {}, "corp": []}, {"data": {}, "corp": {"companies": None}}):
        rep = V.Report()                                                # 관문이 직전 corp 를 넘기지 않은 경우 (배선이 끊긴 날)
        V.check_stmt_marks(rep, companies({"241560": "USD"}), prev)
        assert is_fail(rep), prev
    rep = V.Report()
    V.check_stmt_marks(rep, companies({"241560": "USD"}), None)         # 직전 발행본 자체가 없음: '직전 발행본 읽기' 줄이 실패해요
    assert not is_fail(rep) and NAME in rep.table()


@pytest.mark.parametrize("marked, still, lost, want", [
    (6, 3, 2, "fail"),        # 오늘도 목록에 있는 3곳 중 2곳 → 실패 (세는 기준은 '오늘도 목록에 있는' 수)
    (21, 2, 2, "warn"),       # 21곳 중 19곳이 목록에서 빠지고 남은 2곳이 사라짐 → 경고 (셋 미만)
    (3, 3, 2, "fail"),
    (4, 4, 2, "warn"),
])
def test_the_minimum_counts_companies_still_listed(marked, still, lost, want):
    codes = [f"9{i:05d}" for i in range(marked)]
    cur_marked = {t: "USD" for t in codes[lost:still]}
    row, rep = run({t: "USD" for t in codes}, cur_marked, cur_unmarked=codes[:lost])
    assert (is_fail(rep), is_warn(rep)) == (want == "fail", want == "warn"), rep.table()


def test_many_marked_companies_gone_from_the_list_warns():
    """직전에 표시된 회사의 절반 넘게 오늘 목록에 없으면 (회사 코드 모양이 바뀐 날 등) 조용히 통과하지 않아요."""
    row, rep = run({t: "USD" for t in USD}, {t: "USD" for t in USD[:2]})
    assert not is_fail(rep) and is_warn(rep) and "절반 넘게 오늘 목록에 없어요" in rep.table()


def test_marks_follow_the_apps_rule():
    """앱(src/repair.js stmtNotWon)과 같아요: null 은 표시가 아니고, 빈 글자 · 읽을 수 없는 코드는 표시예요."""
    assert not V._stmt_marked({"t": "1", "stmtCur": None}) and not V._stmt_marked({"t": "1"})
    assert not V._stmt_marked({"t": "1", "stmtCur": "KRW"})
    assert V._stmt_marked({"t": "1", "stmtCur": ""}) and V._stmt_marked({"t": "1", "stmtCur": "XXX"})
    rep = V.Report()                                                    # USD → null 은 사라진 거예요
    V.check_stmt_marks(rep, [{"t": "241560", "nk": "두산밥캣", "stmtCur": None}], {"corp": {"companies": companies({"241560": "USD"})}})
    assert is_warn(rep) and "표시가 사라짐 1" in rep.table()


def test_labels_name_harmful_companies_first_and_only_mark_real_amounts():
    prev = {t: "USD" for t in ["900110", "900120", "900130", "900140", "900150", "008700", "241560"]}
    cur = [{"t": t, "nk": f"외국{t}"} for t in ["900110", "900120", "900130", "900140", "900150"]]
    cur += [{"t": "008700", "nk": "아남전자", "rev": [1.0, 2.0, 3.0]}, {"t": "241560", "nk": None}]
    rep = V.Report()
    V.check_stmt_marks(rep, cur, {"corp": {"companies": companies(prev)}})
    value = next(r for r in rep.rows if r[0] == NAME)[1]
    assert value.split(": ", 1)[1].startswith("008700 아남전자 (금액 있음), 241560")   # 금액이 찬 국내 회사가 맨 앞
    assert "241560 (금액 있음)" not in value and "None" not in value                  # 금액 없으면 표시 없음 · 이름 null 은 빈칸
    assert rep.details and rep.details[0][0] == "표시가 사라진 회사 (stmtCur)" and len(rep.details[0][1]) == 7


def test_duplicate_codes_use_the_first_row_like_the_app():
    marks = {t: "USD" for t in USD[:3]}
    cur = companies(marks) + [{"t": USD[0], "nk": "중복"}]              # 뒤에 표시 없는 같은 코드 → 앱은 앞의 것을 써요
    rep = V.Report()
    V.check_stmt_marks(rep, cur, {"corp": {"companies": companies(marks) + companies({USD[0]: "USD"})}})
    assert not is_fail(rep) and not is_warn(rep) and "직전 3곳" in rep.table(), rep.table()


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


def test_previous_corp_is_read_loosely_from_a_folder(tmp_path):
    (tmp_path / "corp.json").write_text('{"companies":[{"t":"241560","stmtCur":"USD","per":NaN}]}', encoding="utf-8")
    got = V.load_prev_corp(str(tmp_path), None)                         # 직전 파일의 NaN 이 오늘 발행을 막지 않아요
    assert got["companies"][0]["stmtCur"] == "USD"
    with pytest.raises(FileNotFoundError):
        V.load_prev_corp(str(tmp_path / "없음"), None)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


def test_previous_corp_is_read_from_git_the_way_the_daily_run_does(tmp_path, monkeypatch):
    """매일 실행은 --prev-ref HEAD (기본값): git show HEAD:corp.json. data.json 이 아니라 corp.json 을 읽어요."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "data.json").write_text('{"stocks":[]}', encoding="utf-8")
    (tmp_path / "corp.json").write_text('{"companies":[{"t":"241560","stmtCur":"USD"}]}', encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "x")
    monkeypatch.chdir(tmp_path)
    assert V.load_prev_corp(None, "HEAD") == {"companies": [{"t": "241560", "stmtCur": "USD"}]}
    _git(tmp_path, "rm", "-q", "corp.json")
    _git(tmp_path, "commit", "-q", "-m", "y")
    with pytest.raises(RuntimeError) as e:                              # 못 읽으면 git 의 말까지 남겨요 (빈 {} 로 넘어가지 않아요)
        V.load_prev_corp(None, "HEAD")
    assert "HEAD:corp.json" in str(e.value) and "exist" in str(e.value)


def test_main_hands_the_previous_corp_to_the_row(tmp_path, monkeypatch, capsys):
    """관문 실행(_main) 그대로: 직전 corp.json 이 있으면 비교하고, 없으면 실패하고 1 로 끝나요 (건너뛰지 않아요)."""
    cur, prev, _ = good_pair()
    for c in cur["corp"]["companies"][:4] + prev["corp"]["companies"][:4]:
        c["stmtCur"] = "USD"
    pdir = tmp_path / "prev"
    pdir.mkdir()
    for k in ("data", "corp"):
        (pdir / f"{k}.json").write_text(json.dumps(prev[k], ensure_ascii=False), encoding="utf-8")
    seen = []

    def only_this_row(c, p, final, today, **k):                         # 다른 줄은 다른 시험들이 봐요: 넘겨받은 직전 본만 확인
        seen.append(p)
        rep = V.Report()
        V.check_stmt_marks(rep, c["corp"]["companies"], p)
        return rep
    monkeypatch.setattr(V, "load_dir", lambda d: cur)
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (None, None, "시험"))
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: {"dates": [], "src": "시험"})
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: {})
    monkeypatch.setattr(V, "run_checks", only_this_row)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert V.main(["--dir", "unused", "--prev-dir", str(pdir), "--today", "2026-10-31"]) == 0
    assert seen[-1]["corp"]["companies"][0]["stmtCur"] == "USD"
    assert "직전 4곳 · 오늘도 목록에 4곳 · 표시가 사라짐 0" in capsys.readouterr().out
    (pdir / "corp.json").unlink()
    assert V.main(["--dir", "unused", "--prev-dir", str(pdir), "--today", "2026-10-31"]) == 1
    out = capsys.readouterr().out
    assert "!! 직전 corp.json 을 읽을 수 없어요" in out and "직전 corp.json 을 읽지 못했어요: FileNotFoundError" in out
