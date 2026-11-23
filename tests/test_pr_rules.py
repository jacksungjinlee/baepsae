# -*- coding: utf-8 -*-
"""Jack 2026-11-23: CI 가 PR 규칙 두 가지를 확인해요 (tools/pr_rules.py, ci.yml 의 checks job 마지막 단계).

규칙 1 — 사이트가 내보내는 것을 바꾸는 PR: 설명에 실제 데이터 화면 검사 세 결과(N / N)와 그 데이터의 날짜.
규칙 2 — src/ 나 데이터 파이프라인을 바꾸는 PR: docs/HANDOFF.md § 0 수정.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pr_rules as PR  # noqa: E402

TODAY = dt.date(2026, 11, 23)


def rd(body, today=TODAY):
    return PR.real_data_results(body, today)

GOOD_INLINE = ("- Real data (copies of the latest publish on main, pxDate 2026-11-16): `real_data_check.py --data` → 3 / 3 · "
               "`smoke_launch.py --data` → 14 / 14 · `smoke_app.py --data` → 151 / 151.")
GOOD_LIST = ("- Real data (a copy of the 2026-11-14 23:08 publish, prices of 11-13):\n"
             "  - `tests/real_data_check.py --data`: 3 / 3;\n"
             "  - `tests/smoke_launch.py --data`: 14 / 14;\n"
             "  - `tests/smoke_app.py --data`: 151 / 151.")
GOOD_DIR = ("Data branch copy at $S/livedata (pxDate 2026-11-20):\n"
            "- `python tests/real_data_check.py --data DIR` → **3 / 3 통과**\n"
            "- `python tests/smoke_launch.py --data DIR` → **14 / 14 통과**\n"
            "- `python tests/smoke_app.py --data DIR` → **171 / 171 통과**")


# ── 규칙 1: 설명의 결과 ──

@pytest.mark.parametrize("body", [GOOD_INLINE, GOOD_LIST, GOOD_DIR, "## Test evidence\n" + GOOD_LIST + "\n\n## After merge\n없음"])
def test_results_in_every_shape_we_write_them_pass(body):
    ok, lines = rd(body)
    assert ok, lines
    assert any("데이터 날짜" in ln for ln in lines)


@pytest.mark.parametrize("drop", PR.CHECKS)
def test_a_missing_check_fails(drop):
    body = "\n".join(ln for ln in GOOD_DIR.split("\n") if drop + ".py" not in ln)
    ok, lines = rd(body)
    assert not ok and any(drop in ln and "결과가 없어요" in ln for ln in lines), lines


def test_a_failing_result_fails_even_beside_a_passing_one():
    body = GOOD_DIR + "\n- before the fix: `smoke_app.py --data` 170 / 171"
    ok, lines = rd(body)
    assert not ok and any("170 / 171" in ln for ln in lines), lines


@pytest.mark.parametrize("res", ["0 / 0", "13 / 14", "14/13"])
def test_zero_or_unequal_counts_fail(res):
    ok, _ = rd(GOOD_DIR.replace("14 / 14 통과", res + " 통과"))
    assert not ok


def test_a_name_without_a_number_is_not_a_result():
    body = "I will run `smoke_app.py --data DIR` after the merge.\n" + GOOD_DIR.replace("171 / 171 통과", "통과")
    ok, lines = rd(body)
    assert not ok and any("smoke_app" in ln and "N / N" in ln for ln in lines), lines


def test_a_date_like_slash_is_not_read_as_the_result():
    body = GOOD_DIR.replace("`python tests/smoke_app.py --data DIR` → **171 / 171 통과**",
                            "`python tests/smoke_app.py --data DIR` (data of 11/20) → **171 / 171 통과**")
    ok, lines = rd(body)
    assert ok and any("171 / 171" in ln for ln in lines), lines


def test_the_data_date_must_be_near_the_results():
    no_date = GOOD_DIR.replace(" (pxDate 2026-11-20)", "")
    assert not rd(no_date)[0]
    far = "data of 2026-11-20\nx\ny\nz\nw\n" + no_date           # 결과 줄보다 내용 있는 줄 넷 넘게 위
    assert not rd(far)[0]
    assert rd("data of 2026-11-20\n" + no_date)[0]


def test_empty_or_missing_body_fails():
    assert not rd("")[0]
    assert not rd(None)[0]


def test_other_script_names_do_not_count():
    body = GOOD_DIR.replace("tests/smoke_app.py", "tests/xsmoke_app.py")
    assert not rd(body)[0]


# 리뷰 2026-11-23 (Opus): 검사 이름 뒤의 결과를 모두 봐요 · 날짜를 진짜 날짜로 재요 · 주석 안의 글은 읽지 않아요

@pytest.mark.parametrize("tail", ["171 / 171 first run; rerun 170 / 171", "142 / 142 (part 2/2: 70 / 71)", "171 / 171 · 0 / 0"])
def test_every_result_after_a_check_name_must_pass(tail):
    body = GOOD_DIR.replace("**171 / 171 통과**", tail)
    ok, lines = rd(body)
    assert not ok and any("통과하지 못한 결과" in ln for ln in lines), lines


def test_an_unspaced_part_marker_beside_a_spaced_result_is_not_a_result():
    body = GOOD_DIR.replace("**171 / 171 통과**", "**171 / 171 통과** (part 1/2 and 2/2)")
    assert rd(body)[0]


@pytest.mark.parametrize("date, ok", [("2026-11-20", True), ("2026-11-09", True), ("2026-11-08", False),
                                      ("2019-01-01", False), ("2026-11-24", False), ("2026-19-39", False),
                                      ("2026-02-30", False)])
def test_the_data_date_must_be_a_real_date_within_fourteen_days(date, ok):
    body = GOOD_DIR.replace("2026-11-20", date)
    r, lines = rd(body)
    assert r is ok, (date, lines)
    if not ok:
        assert any("14일 안" in ln for ln in lines) and any(ln.startswith("예:") for ln in lines), lines


def test_results_inside_an_html_comment_do_not_count():
    assert not rd("<!--\n" + GOOD_DIR + "\n-->")[0]
    assert rd("<!-- note -->\n" + GOOD_DIR)[0]


def test_a_failing_result_inside_a_comment_is_ignored():
    assert rd(GOOD_DIR + "\n<!-- smoke_app.py --data 170 / 171 -->")[0]


# 리뷰 2026-11-23 (Fable): 세션이 실제로 적는 모양을 받아요 · 같은 줄의 다른 숫자는 결과가 아니에요

def test_real_data_check_without_data_flag_counts():
    """real_data_check.py 는 --data 로만 돌아요 (#114–#133 · #142 · #159 가 이렇게 적었어요)."""
    body = GOOD_INLINE.replace("`real_data_check.py --data` → 3 / 3", "`real_data_check` 3 / 3")
    assert rd(body)[0]


def test_a_table_under_an_intro_line_passes():
    """#121 모양: 날짜 줄 · 빈 줄 · 머리 · |---| · 결과 줄들."""
    body = ("Real data (data branch copy, pxDate 2026-11-20):\n\n| check | result |\n|---|---|\n"
            "| `real_data_check.py --data` | 3 / 3 |\n| `smoke_launch.py --data` | 14 / 14 |\n| `smoke_app.py --data` | 171 / 171 |")
    ok, lines = rd(body)
    assert ok, lines


@pytest.mark.parametrize("tail", ["171 / 171. Dry run: TTM 합성 성공 2,341 / 2,476",
                                  "171 / 171 | 2 / 171 scenes had no company today |"])
def test_other_numbers_later_on_the_line_are_not_results(tail):
    body = GOOD_DIR.replace("**171 / 171 통과**", tail)
    ok, lines = rd(body)
    assert ok, lines


def test_a_table_row_with_a_failing_result_fails():
    body = ("pxDate 2026-11-20\n| `real_data_check.py --data` | 3 / 3 |\n| `smoke_launch.py --data` | 14 / 14 |\n"
            "| `smoke_app.py --data` | 170 / 171 |")
    assert not rd(body)[0]


# ── 바뀐 파일 분류 ──

def test_the_check_helpers_follow_imports_inside_tests():
    h = PR.check_helpers()
    for need in ("tests/real_data_check.py", "tests/smoke_launch.py", "tests/smoke_app.py",
                 "tests/test_launch.py", "tests/copytrace.py", "tests/visualcheck.py", "tests/tmpdirs.py", "tests/testclock.py"):
        assert need in h, (need, h)
    assert all(p.startswith("tests/") and os.path.isfile(os.path.join(ROOT, p)) for p in h)


@pytest.mark.parametrize("path", ["app.html", "baepsae.html", "index.html", "sw.js", "manifest.webmanifest", "app-preview.html",
                                  "src/v2/look.js", "src/copy/v2.js", "template.html", "build.sh", "build-app.sh",
                                  "package-lock.json", "tools/assemble_site.py", ".github/workflows/deploy.yml",
                                  "tests/smoke_app.py", "tests/real_data_check.py", "tests/testclock.py", "tests/copytrace.py"])
def test_site_changes(path):
    assert PR.site_changes([path]) == [path]


def test_build_and_deploy_tools_are_followed_to_the_end():
    b = PR.build_tools()
    for need in ("tools/assemble_site.py", "tools/build_tag.py", "tools/logos/logo_index.py"):
        assert need in b, (need, b)
    for p in ("tools/build_tag.py", "tools/logos/logo_index.py", "build-styleguide.sh"):
        assert PR.site_changes([p]) == [p], p


def test_a_deleted_or_renamed_served_file_counts():
    # git diff --no-renames lists both sides; a deleted path is no longer tracked but still names a served file
    assert PR.site_changes(["baepi-9.png", "pictures/new-name.png"]) == ["baepi-9.png", "pictures/new-name.png"]


@pytest.mark.parametrize("path", ["docs/HANDOFF.md", "docs/CHANGELOG.md", "CLAUDE.md", "tests/test_v2_app.py", "tests/smoke_v2.py",
                                  "fetch_data.py", "validate_data.py", ".github/workflows/ci.yml", "data.json", "README.md"])
def test_not_site_changes(path):
    assert PR.site_changes([path]) == []


@pytest.mark.parametrize("path", ["src/v2/look.js", "fetch_data.py", "validate_data.py", "already_published.py", "watchdog.py",
                                  "requirements.txt", "data/ksic_overrides.csv", ".github/workflows/update-data.yml",
                                  ".github/workflows/deploy.yml", ".github/workflows/watchdog.yml",
                                  "tools/publish_hold.py", "tools/push_data_branch.sh", "tools/assemble_site.py"])
def test_handoff_changes(path):
    assert PR.handoff_changes([path]) == [path]


@pytest.mark.parametrize("path", ["tests/smoke_app.py", "tests/real_data_check.py", "tests/testclock.py", "requirements-dev.txt",
                                  "tests/fonts/install.sh", "app.html", "sw.js", "index.html", "build.sh", "template.html",
                                  "package-lock.json", "tools/build_tag.py", ".github/workflows/ci.yml", "tools/pr_rules.py",
                                  ".github/workflows/logo-dev-fetch.yml", "tools/logos/logodev_fetch.py", "tools/push_logos_branch.sh",
                                  "tools/render_og.py"])
def test_the_daily_runs_screen_checks_and_their_tools_need_section0(path):
    assert PR.handoff_changes([path]) == [path]


@pytest.mark.parametrize("path", ["docs/CHANGELOG.md", "tests/test_x.py", "CLAUDE.md", "README.md", "tools/vendor_phosphor.py"])
def test_not_handoff_changes(path):
    assert PR.handoff_changes([path]) == []


def test_pipeline_tools_are_read_from_the_workflows():
    t = PR.pipeline_tools()
    assert "tools/publish_hold.py" in t and "tools/deploy_check.py" in t
    assert all(os.path.isfile(os.path.join(ROOT, p)) for p in t)


# ── 규칙 2: HANDOFF § 0 ──

H = "# 뱁새\n\n## 0. Current state (updated 2026-11-23)\n\n- live: a\n- next: b\n\n## 1. Product\n\ntext\n"


def test_section0_is_the_text_up_to_the_next_heading():
    s = PR.section0(H)
    assert s.startswith("## 0. Current") and "next: b" in s and "Product" not in s
    assert PR.section0("# x\n## 1. y\n") is None and PR.section0(None) is None


def test_section0_change_rules():
    assert PR.section0_changed(H, H.replace("next: b", "next: c"))[0]
    assert not PR.section0_changed(H, H.replace("text", "other text"))[0]          # § 1 만 바뀜
    assert not PR.section0_changed(H, H.replace("- live: a", "-  live:   a \n"))[0]  # 공백만
    assert not PR.section0_changed(H, H.replace("## 0.", "## Zero."))[0]           # 제목이 사라짐
    assert PR.section0_changed(None, H)[0]                                         # 새로 생김


def test_the_real_handoff_has_a_section0():
    with open(os.path.join(ROOT, PR.HANDOFF), encoding="utf-8") as f:
        assert PR.section0(f.read())


# ── 끝까지: 임시 저장소에서 merge 커밋을 만들어 돌려요 ──

def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    for rel in ("tools/pr_rules.py", "tools/assemble_site.py", "tools/logos/logo_index.py"):
        os.makedirs(r / os.path.dirname(rel), exist_ok=True)
        shutil.copy(os.path.join(ROOT, rel), r / rel)
    (r / "docs").mkdir()
    (r / "docs" / "HANDOFF.md").write_text(H, encoding="utf-8")
    (r / "src").mkdir()
    (r / "src" / "a.js").write_text("1\n")
    (r / "docs" / "notes.md").write_text("n\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    _git(r, "checkout", "-q", "-b", "pr")
    return r


def _merge(r):
    """GitHub 의 refs/pull/N/merge 처럼: main 위에 PR 을 merge 한 커밋 (첫 부모 = main)."""
    _git(r, "checkout", "-q", "main")
    (r / "docs" / "notes.md").write_text("main moved on\n")         # main 이 앞서 나가도 PR 이 바꾼 것만 봐요
    _git(r, "commit", "-q", "-am", "main moves")
    _git(r, "merge", "-q", "--no-ff", "-m", "merge", "pr")


def _run(r, body, event="pull_request", ref="refs/pull/7/merge", head_sha=None):
    ev = r.parent / "event.json"
    if head_sha is None:
        head_sha = _git(r, "rev-parse", "pr").strip()
    ev.write_text(json.dumps({"pull_request": {"number": 7, "body": body, "head": {"sha": head_sha}}}), encoding="utf-8")
    env = {"PATH": os.environ["PATH"], "GITHUB_EVENT_NAME": event, "GITHUB_EVENT_PATH": str(ev), "HOME": str(r.parent),
           "GITHUB_REF": ref}
    return subprocess.run([sys.executable, "tools/pr_rules.py", "--today", TODAY.isoformat()], cwd=r, capture_output=True, text=True, env=env)


def test_end_to_end_src_change_needs_both(repo):
    (repo / "src" / "a.js").write_text("2\n")
    _git(repo, "commit", "-q", "-am", "change src")
    _merge(repo)
    r = _run(repo, "")
    assert r.returncode == 1, r.stdout
    assert "결과가 없어요" in r.stdout and "§ 0 이 바뀌지 않았어요" in r.stdout and "notes.md" not in r.stdout


def test_end_to_end_src_change_with_results_and_section0_passes(repo):
    (repo / "src" / "a.js").write_text("2\n")
    (repo / "docs" / "HANDOFF.md").write_text(H.replace("next: b", "next: c"), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "change src + handoff")
    _merge(repo)
    r = _run(repo, GOOD_LIST)
    assert r.returncode == 0, r.stdout
    assert "PR 규칙 통과" in r.stdout and "PR #7" in r.stdout


def test_end_to_end_docs_only_passes_without_anything(repo):
    (repo / "docs" / "CHANGELOG.md").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs")
    _merge(repo)
    r = _run(repo, None)
    assert r.returncode == 0 and "해당 없음" in r.stdout, r.stdout


def test_end_to_end_push_to_main_and_dispatch_on_main_pass(repo):
    for ev in ("push", "workflow_dispatch"):
        r = _run(repo, "", event=ev, ref="refs/heads/main")
        assert r.returncode == 0 and "PR 이 아닌 실행" in r.stdout, (ev, r.stdout)


@pytest.mark.parametrize("event, ref", [("workflow_dispatch", "refs/heads/claude/x"), ("workflow_dispatch", ""),
                                         ("pull_request_target", "refs/heads/main"), ("", "")])
def test_end_to_end_a_manual_run_on_a_branch_fails(repo, event, ref):
    """리뷰 2026-11-23: 브랜치에서 손으로 돌린 실행이 초록으로 끝나면 PR 의 빨강을 덮어요 → 실패."""
    r = _run(repo, "", event=event, ref=ref)
    assert r.returncode == 1 and "확인하지 못했어요" in r.stdout and "Traceback" not in r.stderr, (r.stdout, r.stderr)


def test_end_to_end_missing_event_file_stops(repo):
    (repo / "src" / "a.js").write_text("2\n")
    _git(repo, "commit", "-q", "-am", "change src")
    _merge(repo)
    env = {"PATH": os.environ["PATH"], "GITHUB_EVENT_NAME": "pull_request",
           "GITHUB_EVENT_PATH": str(repo.parent / "nope.json"), "HOME": str(repo.parent)}
    r = subprocess.run([sys.executable, "tools/pr_rules.py"], cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "읽지 못했어요" in r.stdout and "Traceback" not in r.stderr, (r.stdout, r.stderr)



def test_end_to_end_a_bad_revision_is_a_clear_message_not_a_traceback(repo, tmp_path):
    body = tmp_path / "b.md"
    body.write_text(GOOD_LIST, encoding="utf-8")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    r = subprocess.run([sys.executable, "tools/pr_rules.py", "--body-file", str(body), "--base", "nope", "--head", "HEAD"],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "확인하지 못했어요" in r.stdout and "Traceback" not in r.stderr, (r.stdout, r.stderr)
    r = subprocess.run([sys.executable, "tools/pr_rules.py", "--body-file", str(tmp_path / "missing.md")],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "읽지 못했어요" in r.stdout and "Traceback" not in r.stderr, (r.stdout, r.stderr)



def test_end_to_end_a_push_on_a_branch_fails(repo):
    r = _run(repo, "", event="push", ref="refs/heads/claude/x")
    assert r.returncode == 1 and "확인하지 못했어요" in r.stdout, r.stdout


def test_end_to_end_head_must_be_the_prs_merge_commit(repo):
    (repo / "docs" / "CHANGELOG.md").write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "docs")
    _merge(repo)
    r = _run(repo, "", head_sha="0" * 40)
    assert r.returncode == 1 and "merge 커밋이 아니에요" in r.stdout and "Traceback" not in r.stderr, (r.stdout, r.stderr)


def test_a_deleted_helper_is_still_caught_through_the_base_tree(repo):
    """리뷰 2026-11-23 (Fable): 지운 파일은 머리 트리에 없어요 — base 트리에서 찾아요."""
    _git(repo, "checkout", "-q", "main")
    (repo / "tests").mkdir()
    (repo / "tests" / "smoke_app.py").write_text("import helperx\n")
    (repo / "tests" / "helperx.py").write_text("X = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "checks")
    _git(repo, "checkout", "-q", "-B", "pr")
    (repo / "tests" / "smoke_app.py").write_text("X = 2\n")
    _git(repo, "rm", "-q", "tests/helperx.py")
    _git(repo, "commit", "-q", "-am", "drop helper")
    _merge(repo)
    ok, lines = PR.run("", "HEAD^1", "HEAD", root=str(repo), today=TODAY)
    assert not ok and "tests/helperx.py" in "\n".join(lines), lines


# ── ci.yml 에 걸려 있어요 ──

def test_ci_runs_the_rules_as_the_last_step_of_checks_with_two_commits_and_no_key():
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    st = wf["jobs"]["checks"]["steps"]
    assert st[0]["uses"].startswith("actions/checkout") and st[0]["with"]["fetch-depth"] == 2
    assert st[-1]["run"].strip() == "python tools/pr_rules.py" and set(st[-1]) == {"name", "run"}
    assert "checks" in wf["jobs"]["ci"]["needs"]
    with open(os.path.join(ROOT, "tools", "pr_rules.py"), encoding="utf-8") as f:
        src = f.read()
    assert "GITHUB_TOKEN" not in src and not re.search(r"^\s*(import|from)\s+(urllib|requests|http)", src, re.M)   # 읽기만, 열쇠 없이
