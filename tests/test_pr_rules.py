# -*- coding: utf-8 -*-
"""Jack 2026-11-23: CI 가 PR 규칙 두 가지를 확인해요 (tools/pr_rules.py, ci.yml 의 checks job 마지막 단계).

규칙 1 — 사이트가 내보내는 것을 바꾸는 PR: 설명에 실제 데이터 화면 검사 세 결과(N / N)와 그 데이터의 날짜.
규칙 2 — src/ 나 데이터 파이프라인을 바꾸는 PR: docs/HANDOFF.md § 0 수정.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pr_rules as PR  # noqa: E402

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
    ok, lines = PR.real_data_results(body)
    assert ok, lines
    assert any("데이터 날짜" in ln for ln in lines)


@pytest.mark.parametrize("drop", PR.CHECKS)
def test_a_missing_check_fails(drop):
    body = "\n".join(ln for ln in GOOD_DIR.split("\n") if drop + ".py" not in ln)
    ok, lines = PR.real_data_results(body)
    assert not ok and any(drop in ln and "결과가 없어요" in ln for ln in lines), lines


def test_a_failing_result_fails_even_beside_a_passing_one():
    body = GOOD_DIR + "\n- before the fix: `smoke_app.py --data` 170 / 171"
    ok, lines = PR.real_data_results(body)
    assert not ok and any("170 / 171" in ln for ln in lines), lines


@pytest.mark.parametrize("res", ["0 / 0", "13 / 14", "14/13"])
def test_zero_or_unequal_counts_fail(res):
    ok, _ = PR.real_data_results(GOOD_DIR.replace("14 / 14 통과", res + " 통과"))
    assert not ok


def test_a_name_without_a_number_is_not_a_result():
    body = "I will run `smoke_app.py --data DIR` after the merge.\n" + GOOD_DIR.replace("171 / 171 통과", "통과")
    ok, lines = PR.real_data_results(body)
    assert not ok and any("smoke_app" in ln and "N / N" in ln for ln in lines), lines


def test_a_date_like_slash_is_not_read_as_the_result():
    body = GOOD_DIR.replace("`python tests/smoke_app.py --data DIR` → **171 / 171 통과**",
                            "`python tests/smoke_app.py --data DIR` (data of 11/20) → **171 / 171 통과**")
    ok, lines = PR.real_data_results(body)
    assert ok and any("171 / 171" in ln for ln in lines), lines


def test_the_data_date_must_be_near_the_results():
    no_date = GOOD_DIR.replace(" (pxDate 2026-11-20)", "")
    assert not PR.real_data_results(no_date)[0]
    far = "data of 2026-11-20\n\n\n\n" + no_date                 # 결과 줄보다 네 줄 넘게 위
    assert not PR.real_data_results(far)[0]
    assert PR.real_data_results("data of 2026-11-20\n" + no_date)[0]


def test_empty_or_missing_body_fails():
    assert not PR.real_data_results("")[0]
    assert not PR.real_data_results(None)[0]


def test_other_script_names_do_not_count():
    body = GOOD_DIR.replace("tests/smoke_app.py", "tests/xsmoke_app.py")
    assert not PR.real_data_results(body)[0]


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


@pytest.mark.parametrize("path", ["docs/CHANGELOG.md", "tests/test_x.py", "app.html", ".github/workflows/ci.yml", "CLAUDE.md",
                                  "tools/render_og.py"])
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


def _run(r, body, event="pull_request"):
    ev = r.parent / "event.json"
    ev.write_text(json.dumps({"pull_request": {"number": 7, "body": body}}), encoding="utf-8")
    env = {"PATH": os.environ["PATH"], "GITHUB_EVENT_NAME": event, "GITHUB_EVENT_PATH": str(ev), "HOME": str(r.parent)}
    return subprocess.run([sys.executable, "tools/pr_rules.py"], cwd=r, capture_output=True, text=True, env=env)


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


def test_end_to_end_not_a_pr_passes(repo):
    r = _run(repo, "", event="push")
    assert r.returncode == 0 and "PR 이 아닌 실행" in r.stdout, r.stdout


def test_end_to_end_missing_event_file_stops(repo):
    (repo / "src" / "a.js").write_text("2\n")
    _git(repo, "commit", "-q", "-am", "change src")
    _merge(repo)
    env = {"PATH": os.environ["PATH"], "GITHUB_EVENT_NAME": "pull_request",
           "GITHUB_EVENT_PATH": str(repo.parent / "nope.json"), "HOME": str(repo.parent)}
    r = subprocess.run([sys.executable, "tools/pr_rules.py"], cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode != 0                                         # 이벤트를 읽지 못하면 통과시키지 않아요


# ── ci.yml 에 걸려 있어요 ──

def test_ci_runs_the_rules_as_the_last_step_of_checks_with_two_commits_and_no_key():
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    st = wf["jobs"]["checks"]["steps"]
    assert st[0]["uses"].startswith("actions/checkout") and st[0]["with"] == {"fetch-depth": 2}
    assert st[-1]["run"].strip() == "python tools/pr_rules.py" and set(st[-1]) == {"name", "run"}
    assert "checks" in wf["jobs"]["ci"]["needs"]
    with open(os.path.join(ROOT, "tools", "pr_rules.py"), encoding="utf-8") as f:
        src = f.read()
    assert "GITHUB_TOKEN" not in src and "urllib" not in src and "requests" not in src   # 읽기만, 열쇠 없이
