# -*- coding: utf-8 -*-
"""2026-11-12 (Jack): 매일 실행의 쓰기 토큰을 git 은 발행하는 두 단계에서만 알아요.

예전에는 actions/checkout 이 토큰을 작업 폴더(.git/config)에 남겨, 그 뒤의 모든 단계가 파일로 읽을 수 있었어요 — 화면 검사
도구(npm · pip 패키지), 브라우저까지. 변조된 도구 하나가 그 토큰으로 관문을 거치지 않고 main · data 에 푸시할 수 있었어요.
줄인 것이지 막은 것은 아니에요: 데이터 수집 · 관문 단계는 GitHub API 를 읽으려고 아직 환경으로 토큰을 받아요 (다음 일: 읽기 전용
작업과 발행 작업 나누기).
- 두 checkout 모두 persist-credentials: false
- 토큰은 '커밋 & 푸시' · 'data 브랜치에 올리기' 두 단계의 환경에만 (API 를 읽는 데이터 수집 · 관문 단계는 예전 그대로 자기 환경으로)
- 두 단계는 영수증 확인 뒤, git 으로 무엇을 쓰기 전에 tools/git_token_auth.sh 를 불러요 (토큰을 찍지 않고, 안 되면 멈춰요)
"""
import base64
import json
import os
import re
import stat
import subprocess

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows", "update-data.yml")
SCRIPT = os.path.join(ROOT, "tools", "git_token_auth.sh")
PUBLISH = ("커밋 & 푸시", "data 브랜치에 올리기")
TOKEN = "ghs_TESTtokenNOTreal0123456789"


def jobs():
    with open(WF, encoding="utf-8") as f:
        return yaml.safe_load(f)["jobs"]


def name_of(s):
    return s.get("name") or s.get("uses")


def test_checkout_never_leaves_the_token_in_the_checkout():
    seen = 0
    for job in jobs().values():
        for s in job["steps"]:
            if str(s.get("uses", "")).startswith("actions/checkout@"):
                seen += 1
                assert (s.get("with") or {}).get("persist-credentials") is False, name_of(s)
    assert seen == 2                                                          # check · update 두 job


def test_only_the_two_publishing_steps_hand_the_token_to_git():
    st = jobs()["update"]["steps"]
    names = [name_of(s) for s in st]
    i_main, i_data = names.index(PUBLISH[0]), names.index(PUBLISH[1])
    assert i_data == i_main + 1 == len(st) - 1          # 둘은 붙어 있고 마지막 — 그 사이에 토큰이 git 설정에 있는 채로 도는 단계가 없어요
    for s in st:
        run, env = s.get("run") or "", s.get("env") or {}
        if name_of(s) in PUBLISH:
            assert env == {"GITHUB_TOKEN": "${{ github.token }}"}, name_of(s)
            lines = [ln.strip() for ln in run.splitlines()]
            i_auth = lines.index("bash tools/git_token_auth.sh")
            assert lines.count("bash tools/git_token_auth.sh") == 1
            # 영수증 확인 뒤에, git 으로 무엇을 하기 전에
            assert max(i for i, ln in enumerate(lines) if ln.startswith("sha256sum --quiet --strict -c")) < i_auth
            assert min(i for i, ln in enumerate(lines) if ln.startswith("git ") or "push_data_branch.sh" in ln) > i_auth
        else:
            assert "git_token_auth" not in run and "extraheader" not in run and "x-access-token" not in run, name_of(s)
            assert "git push" not in run and "git commit" not in run, name_of(s)
    # 토큰을 환경으로 받는 단계: 발행 둘 + GitHub API 를 읽는 둘 (데이터 수집 · 관문) — 그 사이의 화면 검사 단계들은 없음
    with_token = [name_of(s) for s in st if "GITHUB_TOKEN" in (s.get("env") or {})]
    assert with_token == ["데이터 수집", "발행 관문 (validate_data.py)", *PUBLISH]
    # 그 넷 밖의 어떤 단계도 어떤 이름으로든 토큰을 받지 않아요 (env 이름을 바꾸거나 run 안에 바로 써도 걸려요)
    allowed = {"데이터 수집", "발행 관문 (validate_data.py)", *PUBLISH}
    pat = re.compile(r"github\.token|secrets\.GITHUB_TOKEN|GITHUB_TOKEN|GH_TOKEN|x-access-token|extraheader")
    for s in st:
        if name_of(s) not in allowed:
            assert not pat.search(json.dumps(s, ensure_ascii=False)), name_of(s)
    # 작업 · 워크플로 전체의 env 로도 주지 않아요 (그러면 모든 단계가 받아요)
    with open(WF, encoding="utf-8") as f:
        whole = yaml.safe_load(f)
    for scope in (whole.get("env") or {}, jobs()["update"].get("env") or {}, jobs()["check"].get("env") or {}):
        assert not pat.search(json.dumps(scope, ensure_ascii=False)), scope
    # 읽기만 하는 check job 에는 토큰도 푸시도 없어요
    text = yaml.safe_dump(jobs()["check"], allow_unicode=True)
    assert "GITHUB_TOKEN" not in text and "github.token" not in text and "git push" not in text


def fake_git(tmp_path, ls_remote_ok=True, fail_first=0, config_ok=True):
    """가짜 git: 부른 것을 did.txt 에 적어요. ls-remote 는 처음 fail_first 번 실패해요 (ls_remote_ok=False 면 늘 실패).
    가짜 sleep 도 둬요 (기다린 초를 slept.txt 에 적고 바로 끝나요)."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    g = bin_ / "git"
    g.write_text("#!/bin/bash\n"
                 f'echo "git $*" >> "{tmp_path}/did.txt"\n'
                 f'echo "$GIT_TERMINAL_PROMPT" >> "{tmp_path}/prompt.txt"\n'
                 f'if [ "$1" = "config" ] && [ {1 if config_ok else 0} = 0 ]; then echo "error: could not lock config file" >&2; exit 255; fi\n'
                 'if [ "$1" = "ls-remote" ]; then\n'
                 f'  n=$(cat "{tmp_path}/lsr.txt" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{tmp_path}/lsr.txt"\n'
                 f'  if [ {0 if ls_remote_ok else 1} = 1 ] || [ $n -le {fail_first} ]; then\n'
                 "    echo \"fatal: could not read Username for 'https://github.com': terminal prompts disabled\" >&2; exit 128\n"
                 "  fi\n"
                 "  exit 0\n"
                 "fi\n"
                 "exit 0\n")
    g.chmod(g.stat().st_mode | stat.S_IEXEC)
    sl = bin_ / "sleep"
    sl.write_text(f'#!/bin/bash\necho "$1" >> "{tmp_path}/slept.txt"\n')
    sl.chmod(sl.stat().st_mode | stat.S_IEXEC)
    for f in ("did.txt", "lsr.txt", "slept.txt", "prompt.txt"):
        if (tmp_path / f).exists():
            (tmp_path / f).unlink()
    return {"PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_ACTIONS": "true"}


def run_script(tmp_path, env):
    r = subprocess.run(["bash", SCRIPT], cwd=tmp_path, env=env, capture_output=True, text=True)
    did = (tmp_path / "did.txt").read_text() if (tmp_path / "did.txt").exists() else ""
    return r, did


def test_token_script_sets_the_header_checks_it_and_never_prints_the_token(tmp_path):
    import base64
    r, did = run_script(tmp_path, {**fake_git(tmp_path), "GITHUB_TOKEN": TOKEN})
    assert r.returncode == 0, r.stderr
    want = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
    lines = did.splitlines()
    assert lines[0] == f"git config --local http.https://github.com/.extraheader AUTHORIZATION: basic {want}"   # checkout 이 하던 것과 같은 설정
    assert lines[1] == "git ls-remote --exit-code origin refs/heads/main" and len(lines) == 2                # 받아들여지는지 읽기로 확인 · 그 밖의 git 일은 없음
    out = r.stdout + r.stderr
    # 토큰은 어디에도 찍지 않아요. base64 값은 GitHub 이 가리도록 '::add-mask::' 줄에만 (checkout 과 같아요)
    assert TOKEN not in out and "토큰 확인됨" in out
    assert [ln for ln in out.splitlines() if want in ln] == [f"::add-mask::{want}"], out


def test_token_script_stops_without_a_token_or_when_github_refuses_it(tmp_path):
    r, did = run_script(tmp_path, fake_git(tmp_path))                        # 토큰 없음: git 을 건드리지도 않아요
    assert r.returncode != 0 and did == "" and "GITHUB_TOKEN 이 이 단계의 환경에 없어요" in r.stdout
    r, did = run_script(tmp_path, {**fake_git(tmp_path), "GITHUB_TOKEN": ""})
    assert r.returncode != 0 and did == ""
    for blank in ("   ", "\t", f"{TOKEN} ", f"{TOKEN}\n"):                     # 공백만 · 공백이 섞인 토큰: git 을 건드리지 않아요
        r, did = run_script(tmp_path, {**fake_git(tmp_path), "GITHUB_TOKEN": blank})
        assert r.returncode != 0 and did == "" and TOKEN not in r.stdout + r.stderr, repr(blank)
    r, did = run_script(tmp_path, {**fake_git(tmp_path, ls_remote_ok=False), "GITHUB_TOKEN": TOKEN})   # GitHub 이 거절 (세 번)
    assert r.returncode != 0 and "세 번 다 읽지 못했어요 → 푸시하지 않아요" in r.stdout and TOKEN not in r.stdout + r.stderr
    # 토큰 문제와 네트워크를 가리는 법: git 이 실제로 찍는 줄 이름으로 (401 이면 'could not read Username …')
    assert "could not read Username" in r.stdout and "Could not resolve host" in r.stdout
    assert "could not read Username for 'https://github.com': terminal prompts disabled" in r.stderr   # git 의 오류 줄은 그대로 보여요
    want = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
    assert [ln for ln in (r.stdout + r.stderr).splitlines() if want in ln] == [f"::add-mask::{want}"]
    assert did.count("git ls-remote") == 3 and (tmp_path / "slept.txt").read_text().split() == ["5", "10"]
    src = open(SCRIPT, encoding="utf-8").read()
    assert "set -euo pipefail" in src and "set -x" not in src and "GIT_TERMINAL_PROMPT=0" in src
    # 정적 검사: 토큰 · base64 를 화면 · 실행 요약 · 설정 목록으로 내보내는 줄이 없어요 (add-mask 한 줄만 예외)
    for ln in src.splitlines():
        code = ln.split("#", 1)[0]
        if "::add-mask::" in code:
            continue
        assert not re.search(r"(echo|printf)[^\n]*\$\{?(GITHUB_TOKEN|basic)\b", code) or "base64" in code, ln
        assert "GITHUB_STEP_SUMMARY" not in code and "config --list" not in code and "config -l" not in code, ln


@pytest.mark.parametrize("fails,ok", [(1, True), (2, True), (3, False)])
def test_token_check_retries_a_network_blip(tmp_path, fails, ok):
    """잠깐 끊긴 네트워크로 발행이 멈추지 않게 세 번까지 읽어 봐요 (5초 · 10초 쉬고). 세 번 다 안 되면 멈춰요."""
    r, did = run_script(tmp_path, {**fake_git(tmp_path, fail_first=fails), "GITHUB_TOKEN": TOKEN})
    assert (r.returncode == 0) is ok, r.stdout
    assert did.count("git ls-remote") == min(fails + 1, 3)
    assert ("토큰 확인됨" in r.stdout) is ok and TOKEN not in r.stdout + r.stderr


@pytest.mark.parametrize("name", PUBLISH)
def test_publishing_step_sets_the_token_only_after_the_receipt_checks(tmp_path, name):
    """영수증이 없으면 토큰을 git 에 알리지도 않아요. 있으면 토큰 설정이 git 의 첫 일이에요."""
    import shutil
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_screen_check as T
    run = T.step(name)["run"]
    env = T.publish_env(tmp_path, ("gate-pass.sha256", "screen-pass.sha256"))
    assert os.path.isfile(tmp_path / "tools" / "git_token_auth.sh") and shutil.which("base64")
    r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp_path, env=env, capture_output=True, text=True)
    did = (tmp_path / "did.txt").read_text().splitlines()
    assert r.returncode == 0 and did[0].startswith("git config --local http.https://github.com/.extraheader AUTHORIZATION: basic "), (r.stderr, did)
    assert did[1] == "git ls-remote --exit-code origin refs/heads/main"
    env = T.publish_env(tmp_path, ("gate-pass.sha256",))                     # 화면 검사 영수증 없음
    r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and not (tmp_path / "did.txt").exists()
    env = T.publish_env(tmp_path, ("gate-pass.sha256", "screen-pass.sha256"))
    env.pop("GITHUB_TOKEN")                                                  # 토큰이 환경에 없으면 아무것도 쓰지 않고 멈춰요
    r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and not (tmp_path / "did.txt").exists()


def test_token_script_runs_only_on_a_github_actions_runner(tmp_path):
    """실행기 밖에서는 '::add-mask::' 가 값을 가리지 못하고 그냥 찍어요 — 그래서 아예 돌지 않아요 (git 도 건드리지 않아요)."""
    env = {**fake_git(tmp_path), "GITHUB_TOKEN": TOKEN}
    for actions in (None, "", "false", "1"):
        e = dict(env)
        if actions is None:
            e.pop("GITHUB_ACTIONS")
        else:
            e["GITHUB_ACTIONS"] = actions
        r, did = run_script(tmp_path, e)
        want = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
        assert r.returncode != 0 and did == "" and "GitHub Actions 밖에서는" in r.stdout, repr(actions)
        assert want not in r.stdout + r.stderr and TOKEN not in r.stdout + r.stderr


def test_a_long_token_gives_one_mask_line_and_one_header(tmp_path):
    """base64 는 76자에서 줄을 바꿔요 — 줄바꿈을 지우지 않으면 앞부분만 가려지고 헤더가 깨져요."""
    long_token = "ghs_" + "A1b2C3d4" * 40                                   # 324자
    r, did = run_script(tmp_path, {**fake_git(tmp_path), "GITHUB_TOKEN": long_token})
    want = base64.b64encode(f"x-access-token:{long_token}".encode()).decode()
    assert r.returncode == 0, r.stdout
    assert [ln for ln in r.stdout.splitlines() if ln.startswith("::add-mask::")] == [f"::add-mask::{want}"]
    cfg = [ln for ln in did.splitlines() if ln.startswith("git config")]
    assert cfg == [f"git config --local http.https://github.com/.extraheader AUTHORIZATION: basic {want}"]


def test_token_script_stops_when_git_config_fails_and_never_prompts(tmp_path):
    """설정을 못 쓰면 읽기 확인도 하지 않고 멈춰요 (set -e). git 은 언제나 사용자 이름을 묻지 않게 (GIT_TERMINAL_PROMPT=0)."""
    r, did = run_script(tmp_path, {**fake_git(tmp_path, config_ok=False), "GITHUB_TOKEN": TOKEN})
    assert r.returncode != 0 and "ls-remote" not in did and "토큰 확인됨" not in r.stdout
    r, did = run_script(tmp_path, {**fake_git(tmp_path, fail_first=1), "GITHUB_TOKEN": TOKEN})
    assert r.returncode == 0
    assert set((tmp_path / "prompt.txt").read_text().split()) == {"0"}


def test_check_job_is_read_only_and_no_publishing_step_force_pushes():
    """읽기만 하는 check job 은 쓰기 권한이 없어요. 발행 단계는 강제 푸시를 하지 않아요 (push_data_branch.sh 도)."""
    assert jobs()["check"].get("permissions") == {"contents": "read"}
    st = {name_of(s): s for s in jobs()["update"]["steps"]}
    for name in PUBLISH:
        run = st[name].get("run") or ""
        assert not re.search(r"git push[^\n]*(--force|\s-f\b|\+)", run), name
    src = open(os.path.join(ROOT, "tools", "push_data_branch.sh"), encoding="utf-8").read()
    assert not re.search(r"git push[^\n]*(--force|\s-f\b)", src)
