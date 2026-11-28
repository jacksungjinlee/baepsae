# -*- coding: utf-8 -*-
"""2026-11-11 (Jack): 매일 실행은 발행하기 전에 오늘 데이터로 앱을 진짜 브라우저에서 열어 봐요 (update-data.yml '발행 전 화면 검사').

- 자리: 발행 관문 다음, 커밋 · data 브랜치 앞. DART 캐시 저장보다는 뒤 (여기서 멈춰도 다음 실행이 전체 DART 실행이 되지 않아요).
- 실패하면 발행하지 않아요: 통과 영수증(screen-pass.sha256)이 없으면 커밋 단계도 data 브랜치 단계도 멈춰요.
  건너뛰는 조건(if) · 실패를 삼키는 장치 · 다시 시도해서 초록으로 바꾸는 장치가 없어요. 시험 실행(dry_run)에서도 돌아요.
- 진짜 데이터로 보는 검사 셋: tests/real_data_check.py · tests/smoke_launch.py --data · tests/smoke_app.py --data (전부).
- 브라우저는 보관본에서: 매일 실행과 CI 는 실행 중에 Ubuntu 패키지 서버(apt)를 쓰지 않아요.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")
sys.path.insert(0, os.path.join(ROOT, "tests"))
import real_data_check as RC  # noqa: E402

LIVE = ("data.json", "corp.json", "disc.json", "macro.json")
SCREEN = "발행 전 화면 검사 (오늘 데이터 · 헤드리스 크롬)"
GATE = "발행 관문 (validate_data.py)"
TOOLS = ("real_data_check", "smoke_launch", "smoke_app")
# 보관본 열쇠: 판 숫자(v1, v2 …)는 올릴 수 있어요 (보관본이 망가졌을 때 — docs/RUNBOOK.md). 다만 모든 곳이 같은 열쇠여야 해요.
CACHE_KEY = re.compile(r"playwright-v\d+-ubuntu-24\.04-\$\{\{ hashFiles\('requirements-dev\.txt'\) \}\}")
TOOLS_STEP = "화면 검사 도구 설치 (package-lock.json · requirements-dev.txt 그대로)"
BROWSER_STEP = "브라우저 · 한글 글꼴 준비 (보관본 그대로 · 없을 때만 내려받기 · apt 없음)"
FONT_SHA = "3090ccde0442bb347aa7685d9ba8b17436a60682df6e8f92a9a670de14056e22"
NODE = shutil.which("node")


def load(name):
    with open(os.path.join(WF, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def update_steps():
    return load("update-data.yml")["jobs"]["update"]["steps"]


def names(st):
    return [s.get("name") or s.get("uses") for s in st]


def step(name):
    return next(s for s in update_steps() if s.get("name") == name)


# ── 자리와 모양 ──
def test_screen_check_sits_between_the_gate_and_publishing_and_after_the_dart_cache_is_saved():
    st = update_steps()
    n = names(st)
    i_fetch, i_save, i_gate = n.index("데이터 수집"), n.index("DART 캐시 저장"), n.index(GATE)
    i_screen, i_main, i_data = n.index(SCREEN), n.index("커밋 & 푸시"), n.index("data 브랜치에 올리기")
    assert i_fetch < i_save < i_gate < i_screen < i_main < i_data == len(st) - 1
    assert st[i_save]["if"] == "always()"                                    # 뒤에서 무엇이 실패해도 DART 결과는 이미 보관돼 있어요
    # 관문과 발행 사이에 새로 들어온 것은 화면 검사와 그 준비뿐이고, 모두 조건 없이 돌아요 (시험 실행에서도)
    between = st[i_gate + 1:i_main]
    assert names(between) == ["actions/setup-node@v7", TOOLS_STEP, "브라우저 보관본 불러오기", BROWSER_STEP, "브라우저 보관", SCREEN]
    for s in between:
        n = s.get("name") or s.get("uses")
        assert "continue-on-error" not in s, n
        # 조건(if)은 '방금 받은 브라우저 보관' 하나뿐 (보관본이 없던 실행에서만) — 검사와 그 준비는 언제나 돌아요
        assert ("if" in s) is (n == "브라우저 보관"), n
    assert between[4]["if"] == "steps.browser_cache.outputs.cache-hit != 'true'" and between[2]["id"] == "browser_cache"
    # 시간 한도: 멈춘 채로 다음 실행들을 막지 않게 (한도를 넘으면 실패 → 발행 없음). 평소 검사는 5분쯤이에요.
    assert {(s.get("name") or s.get("uses")): s.get("timeout-minutes") for s in between} == {
        "actions/setup-node@v7": None, TOOLS_STEP: 10, "브라우저 보관본 불러오기": None, BROWSER_STEP: 10, "브라우저 보관": None, SCREEN: 30}
    # 관문보다 앞에는 화면 검사 도구를 깔지 않아요 (데이터 수집은 requirements.txt 그대로의 환경에서)
    before = "\n".join(s.get("run") or "" for s in st[:i_gate + 1])
    assert "requirements-dev" not in before and "playwright" not in before


def test_screen_check_runs_the_three_real_data_checks_in_full():
    run = step(SCREEN)["run"]
    assert step(SCREEN)["shell"] == "bash"                                   # bash -eo pipefail: tee 뒤에서도 실패가 실패로 남아요
    assert f"for t in {' '.join(TOOLS)}; do" in run
    assert 'if python "tests/$t.py" --data . 2>&1 | tee "$RUNNER_TEMP/screen-$t.log"; then ok=통과; else ok=실패; failed+=("$t"); fi' in run
    for bad in ("--only", "--part", "|| true", "set +e", "retry", "until ", "while "):   # 일부만 돌리거나, 삼키거나, 다시 시도하지 않아요
        assert bad not in run, bad
    assert run.count("python ") == 1                                         # 검사를 부르는 곳은 그 한 줄뿐
    for t in TOOLS:
        assert os.path.isfile(os.path.join(ROOT, "tests", f"{t}.py")), t
    lines = [ln.strip() for ln in run.strip().splitlines()]
    assert lines[1] == 'sha256sum --quiet --strict -c "$RUNNER_TEMP/gate-pass.sha256"'              # 관문을 통과한 그 파일로 시작
    assert lines[-2] == 'sha256sum --quiet --strict -c "$RUNNER_TEMP/gate-pass.sha256"'             # 검사 뒤에도 그 파일 그대로
    assert lines[-1] == 'sha256sum data.json corp.json disc.json macro.json > "$RUNNER_TEMP/screen-pass.sha256"'
    assert run.count("screen-pass.sha256") == 1                              # 영수증은 맨 마지막 줄에서만
    i_exit = next(i for i, ln in enumerate(lines) if ln == "exit 1")
    assert i_exit < len(lines) - 2


def test_publishing_steps_need_the_screen_receipt():
    main_run, data_run = step("커밋 & 푸시")["run"], step("data 브랜치에 올리기")["run"]
    need = 'sha256sum --quiet --strict -c "$RUNNER_TEMP/screen-pass.sha256"'
    assert main_run.index(need) < main_run.index("git config") < main_run.index("git add")
    assert data_run.index(need) < data_run.index("bash tools/push_data_branch.sh")
    for run in (main_run, data_run):
        assert run.count(need) == 1 and run.count('sha256sum --quiet --strict -c "$RUNNER_TEMP/gate-pass.sha256"') <= 1
    whole = "\n".join(s.get("run") or "" for s in update_steps())
    assert whole.count('> "$RUNNER_TEMP/screen-pass.sha256"') == 1           # 영수증을 쓰는 곳은 화면 검사 한 곳


# ── 단계의 bash 를 그대로 돌려 보기 (가짜 python · git) ──
def fake_bin(tmp_path, fail=()):
    """가짜 python: tests/<이름>.py 를 부르면 기록하고 'N / N 통과'를 찍어요. fail 에 든 이름은 exit 1."""
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    py = bin_ / "python"
    py.write_text("#!/bin/bash\n"
                  'name=$(basename "$1" .py)\n'
                  f'echo "$*" >> "{tmp_path}/calls.txt"\n'
                  f'for f in {" ".join(fail) or "__none__"}; do if [ "$name" = "$f" ]; then echo "  FAIL  x"; echo "1 / 2 통과"; exit 1; fi; done\n'
                  'if [ -n "$TOUCH" ] && [ "$name" = "$TOUCH" ]; then echo " " >> data.json; fi\n'
                  'if [ -n "$UNSEEN" ] && [ "$name" = "smoke_app" ]; then echo "!! 확인 못 함  $UNSEEN"; fi\n'
                  'if [ -n "$NOTICE" ] && [ "$name" = "smoke_app" ]; then echo "!! 알림  $NOTICE"; fi\n'
                  'echo "2 / 2 통과"\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    return bin_


def run_screen(tmp_path, fail=(), gate_receipt=True, touch="", unseen="", notice=""):
    for f in LIVE:
        (tmp_path / f).write_text("{}")
    for f in ("calls.txt", "screen-pass.sha256", "screen-summary.txt", "screen-unseen.txt", "summary.md", "gate-pass.sha256"):
        if (tmp_path / f).exists():
            (tmp_path / f).unlink()
    bin_ = fake_bin(tmp_path, fail)
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
           "TOUCH": touch, "UNSEEN": unseen, "NOTICE": notice}
    if gate_receipt:
        subprocess.run("sha256sum data.json corp.json disc.json macro.json > gate-pass.sha256", shell=True, cwd=tmp_path, check=True)
    r = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step(SCREEN)["run"]], cwd=tmp_path, env=env,
                       capture_output=True, text=True)
    calls = (tmp_path / "calls.txt").read_text().splitlines() if (tmp_path / "calls.txt").exists() else []
    return r, calls, (tmp_path / "screen-pass.sha256")


def test_screen_step_writes_the_receipt_only_when_all_three_pass(tmp_path):
    r, calls, rec = run_screen(tmp_path)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert calls == [f"tests/{t}.py --data ." for t in TOOLS]                # 셋 모두 · 이 순서로 · 진짜 데이터 폴더(.)로
    assert rec.exists()
    assert subprocess.run(["sha256sum", "--quiet", "--strict", "-c", str(rec)], cwd=tmp_path).returncode == 0
    summary = (tmp_path / "summary.md").read_text()
    assert "### 뱁새 발행 전 화면 검사 — PASS" in summary
    for t in TOOLS:
        assert f"· {t}: 통과 · 2 / 2 통과" in summary, summary


@pytest.mark.parametrize("bad", TOOLS)
def test_screen_step_fails_without_a_receipt_when_one_check_fails(tmp_path, bad):
    r, calls, rec = run_screen(tmp_path, fail=(bad,))
    assert r.returncode == 1 and not rec.exists(), (r.stdout, r.stderr)
    assert calls == [f"tests/{t}.py --data ." for t in TOOLS]                # 하나가 실패해도 나머지를 끝까지 돌려 보여 줘요
    assert f"::error title=발행 전 화면 검사 실패::{bad} → 이 실행은 발행하지 않아요" in r.stdout
    summary = (tmp_path / "summary.md").read_text()
    assert "### 뱁새 발행 전 화면 검사 — FAIL" in summary and f"· {bad}: 실패 · 1 / 2 통과" in summary


def test_screen_step_needs_the_gate_receipt_and_untouched_files(tmp_path):
    r, calls, rec = run_screen(tmp_path, gate_receipt=False)                 # 관문 영수증이 없으면 검사를 시작도 하지 않아요
    assert r.returncode != 0 and calls == [] and not rec.exists()
    r, calls, rec = run_screen(tmp_path, touch="smoke_app")                  # 검사 도중 파일이 바뀌면 영수증을 쓰지 않아요
    assert r.returncode != 0 and len(calls) == 3 and not rec.exists(), (r.stdout, r.stderr)


def publish_env(tmp_path, receipts):
    """커밋 · data 브랜치 단계를 돌릴 폴더: 네 파일, 가짜 git, 가짜 tools/push_data_branch.sh, 고른 영수증."""
    for f in LIVE:
        (tmp_path / f).write_text("{}")
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    git = bin_ / "git"
    git.write_text(f'#!/bin/bash\necho "git $*" >> "{tmp_path}/did.txt"\nexit 0\n')
    git.chmod(git.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "push_data_branch.sh").write_text(f'echo "push_data_branch $*" >> "{tmp_path}/did.txt"\n')
    # 2026-11-12: 발행 단계는 푸시 직전에 토큰을 git 에 알려요 (진짜 tools/git_token_auth.sh 를 가짜 git 으로 돌려요)
    shutil.copy(os.path.join(ROOT, "tools", "git_token_auth.sh"), tmp_path / "tools" / "git_token_auth.sh")
    for f in ("did.txt", "gate-pass.sha256", "screen-pass.sha256"):
        if (tmp_path / f).exists():
            (tmp_path / f).unlink()
    for name in receipts:
        subprocess.run(f"sha256sum data.json corp.json disc.json macro.json > {name}", shell=True, cwd=tmp_path, check=True)
    return {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": str(tmp_path), "GITHUB_REF": "refs/heads/main",
            "GITHUB_REF_NAME": "main", "TZ": "Asia/Seoul", "GITHUB_TOKEN": "test-token-not-real", "GITHUB_ACTIONS": "true"}


@pytest.mark.parametrize("name", ["커밋 & 푸시", "data 브랜치에 올리기"])
def test_publishing_steps_stop_before_writing_anything_without_the_screen_receipt(tmp_path, name):
    run = step(name)["run"]
    did = tmp_path / "did.txt"

    def go(receipts, change=None):
        env = publish_env(tmp_path, receipts)
        if change:
            (tmp_path / change).write_text('{"x": 1}')                     # 영수증을 받은 뒤에 파일이 바뀐 경우
        r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp_path, env=env, capture_output=True, text=True)
        return r, (did.read_text() if did.exists() else "")
    r, done = go(("gate-pass.sha256", "screen-pass.sha256"))
    assert r.returncode == 0 and ("git add" in done or "push_data_branch" in done), (r.stdout, r.stderr, done)
    r, done = go(("gate-pass.sha256",))                                      # 화면 검사 영수증 없음
    assert r.returncode != 0 and done == "", (r.stdout, r.stderr, done)
    if name == "커밋 & 푸시":                                                # 관문 영수증 없음 (data 브랜치 단계는 그 확인을
        r, done = go(("screen-pass.sha256",))                                # tools/push_data_branch.sh 가 해요: test_data_branch.py)
        assert r.returncode != 0 and done == "", (r.stdout, r.stderr, done)
    r, done = go(("gate-pass.sha256", "screen-pass.sha256"), change="corp.json")
    assert r.returncode != 0 and done == "", (r.stdout, r.stderr, done)


# ── 브라우저: 보관본에서, apt 없이 ──
def test_daily_run_and_ci_get_the_browser_from_the_cache_and_never_use_apt():
    keys = set()
    for name in ("update-data.yml", "ci.yml"):
        wf = load(name)
        with open(os.path.join(WF, name), encoding="utf-8") as f:
            raw = f.read()
        runs = "\n".join(s.get("run") or "" for j in wf["jobs"].values() for s in j.get("steps", []))
        for bad in ("--with-deps", "install-deps", "apt-get", "apt install", "apt update", "dpkg ", "ubuntu.com"):
            assert bad not in runs, (name, bad)
        assert "ubuntu.com" not in raw                                           # 그 서버는 어디에도 적혀 있지 않아요
        jobs = {k: j for k, j in wf["jobs"].items() if "playwright install" in "\n".join(s.get("run") or "" for s in j.get("steps", []))}
        assert sorted(jobs) == (["update"] if name == "update-data.yml" else ["checks", "smoke_app", "smoke_rest", "smoke_v2"]), jobs.keys()
        for k, j in jobs.items():
            st = j["steps"]
            caches = [s for s in st if s.get("uses", "").startswith("actions/cache") and s["with"]["path"] == "~/.cache/ms-playwright"]
            for c in caches:
                assert set(c["with"]) == {"path", "key"} and CACHE_KEY.fullmatch(c["with"]["key"]), (name, k)   # restore-keys 없음: 다른 판의 브라우저를 받아 쓰지 않아요
                keys.add(c["with"]["key"])
            if name == "ci.yml":                                              # CI: 한 단계 (job 이 성공으로 끝나면 보관 · 단계의 if 는 CI 에서 못 써요)
                assert [c["uses"] for c in caches] == ["actions/cache@v6"], (name, k)
            else:                                                             # 매일 실행: 꺼내기 → 준비 → (없던 실행만) 검사 전에 보관
                assert [c["uses"] for c in caches] == ["actions/cache/restore@v6", "actions/cache/save@v6"], (name, k)
            installs = [i for i, s in enumerate(st) if "playwright install" in (s.get("run") or "")]
            assert len(installs) == 1 and installs[0] > st.index(caches[0]), (name, k)
            lines = [ln.strip() for ln in st[installs[0]]["run"].strip().splitlines()]
            assert lines[-2:] == ["python -m playwright install chromium", "bash tests/fonts/install.sh"], (name, k)   # 브라우저, 그리고 한글 글꼴
            if name != "ci.yml":
                assert installs[0] < st.index(caches[1]) < names(st).index(SCREEN)                  # 검사가 실패해도 브라우저는 이미 보관돼 있어요
    assert len(keys) == 1, keys                                               # 매일 실행과 CI 의 모든 곳이 같은 보관본을 나눠 써요
    # 보관본 열쇠는 Playwright 판이 바뀌면 바뀌어요: 판은 requirements-dev.txt 에 정확한 숫자로
    with open(os.path.join(ROOT, "requirements-dev.txt"), encoding="utf-8") as f:
        assert re.search(r"^playwright==\d+\.\d+\.\d+$", f.read(), re.M)


def test_daily_run_installs_the_same_tools_as_ci():
    """화면 검사가 쓰는 도구는 CI 와 같아요: 같은 node, package-lock.json 그대로의 node_modules (smoke_launch 가 화면 문구를 읽을 때
    node_modules/.bin/esbuild 를 써요 — 없으면 검사가 시작도 못 해요), requirements-dev.txt 그대로의 파이썬 도구."""
    def node(steps):
        return next(s for s in steps if s.get("uses", "").startswith("actions/setup-node"))["with"]
    assert node(update_steps())["node-version"] == node(load("ci.yml")["jobs"]["checks"]["steps"])["node-version"]
    assert node(update_steps())["cache"] == "npm"                              # npm 보관본 먼저 (--prefer-offline)
    lines = [ln.strip() for ln in step(TOOLS_STEP)["run"].strip().splitlines()]
    # --ignore-scripts: 저장소에 쓸 수 있는 job 에서는 npm 패키지의 설치 스크립트를 돌리지 않아요 (esbuild 는 없어도 돌아요)
    assert lines == ["npm ci --prefer-offline --ignore-scripts", "pip install -r requirements-dev.txt"]
    for j in ("checks", "smoke_app", "smoke_v2", "smoke_rest"):               # CI 도 npm 보관본을 써요 (main 의 CI 가 보관본을 채워 둬요)
        assert node(load("ci.yml")["jobs"][j]["steps"])["cache"] == "npm", j
    py = next(s for s in update_steps() if s.get("uses", "").startswith("actions/setup-python"))["with"]
    assert py["cache"] == "pip" and py["cache-dependency-path"].split() == ["requirements.txt", "requirements-dev.txt"]
    # 세 검사 스크립트가 node_modules 를 쓰는지: 쓰는 것이 하나라도 있으면 npm ci 가 꼭 있어야 해요 (지금: copytrace.py 의 esbuild)
    with open(os.path.join(ROOT, "tests", "copytrace.py"), encoding="utf-8") as f:
        assert '"node_modules", ".bin", "esbuild"' in f.read()
    with open(os.path.join(ROOT, "tests", "smoke_launch.py"), encoding="utf-8") as f:
        assert "from copytrace import copy_strings" in f.read()


def test_test_font_is_the_pinned_file_and_installs_without_a_download(tmp_path):
    """한글 글꼴: 저장소의 Pretendard 한 파일 (고정된 sha256 · 라이선스 동봉). 설치 스크립트는 내려받지 않고, 깔리지 않으면 실패해요."""
    import hashlib
    d = os.path.join(ROOT, "tests", "fonts")
    with open(os.path.join(d, "PretendardVariable.ttf"), "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == FONT_SHA
    for f in ("LICENSE.txt", "SOURCE.txt", "install.sh"):
        assert os.path.isfile(os.path.join(d, f)), f
    with open(os.path.join(d, "SOURCE.txt"), encoding="utf-8") as f:
        assert FONT_SHA in f.read()
    with open(os.path.join(d, "install.sh"), encoding="utf-8") as f:
        sh = f.read()
    assert FONT_SHA in sh and "exit 1" in sh and "set -euo pipefail" in sh
    code = "\n".join(ln for ln in sh.splitlines() if not ln.lstrip().startswith("#"))      # 주석 말고 실제 명령에
    for bad in ("curl", "wget", "apt", "npm ", "pip ", "http"):
        assert bad not in code, bad
    if shutil.which("fc-cache") is None or shutil.which("fc-match") is None:
        pytest.skip("이 기계에 fontconfig 가 없어요 (CI 와 매일 실행에는 있어요: 없으면 install.sh 가 실패해요)")
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    r = subprocess.run(["bash", os.path.join(d, "install.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 0 and "baepsae-tests/PretendardVariable.ttf" in r.stdout, r.stdout + r.stderr
    assert (tmp_path / ".local" / "share" / "fonts" / "baepsae-tests" / "PretendardVariable.ttf").is_file()
    bad = tmp_path / "copy"                                                   # 파일이 바뀌었으면 (sha 가 다르면) 깔지 않고 실패
    shutil.copytree(d, bad)
    with open(bad / "PretendardVariable.ttf", "ab") as f:
        f.write(b"x")
    r = subprocess.run(["bash", str(bad / "install.sh")], env={"PATH": os.environ["PATH"], "HOME": str(tmp_path / "h2")}, capture_output=True, text=True)
    assert r.returncode != 0 and "FAILED" in r.stdout + r.stderr, r.stdout + r.stderr          # sha256 이 달라서 멈춘 거예요
    assert not (tmp_path / "h2" / ".local" / "share" / "fonts" / "baepsae-tests").exists()       # 깔기 전에 멈춰요


# ── tests/real_data_check.py ──
def fixture_dir(tmp_path, change=None):
    files = {}
    for f in ("data.json", "corp.json", "disc.json", "macro.json"):
        with open(os.path.join(ROOT, "tests", "fixtures", "v2", f), encoding="utf-8") as fh:
            files[f] = json.load(fh)
    if change:
        change(files)
    for f, j in files.items():
        with open(tmp_path / f, "w", encoding="utf-8") as fh:
            json.dump(j, fh, ensure_ascii=False)
    return str(tmp_path)


def test_real_data_check_names_each_missing_field(tmp_path):
    files = RC.load(fixture_dir(tmp_path))
    assert RC.check_fields(files)[0] is True

    def drop(key):
        def change(f):
            for s in f["data.json"]["stocks"]:
                s.pop(key, None)
        return change
    for key in ("d1", "val20", "ind"):
        ok, msg = RC.check_fields(RC.load(fixture_dir(tmp_path, drop(key))))
        assert ok is False and key in msg, (key, msg)
    ok, msg = RC.check_fields(RC.load(fixture_dir(tmp_path, lambda f: f["macro.json"].pop("idxHist"))))
    assert ok is False and "idxHist" in msg


def test_real_data_check_growth_rule_is_the_same_as_the_pytest_one():
    good = {"n": 2328, "diff": [], "y2": 2297, "y1": 13, "none": 18}
    assert RC.check_growth(good)[0] is True
    for change in ({"diff": ["005930"]}, {"n": 1000}, {"n": 0}, {"y2": 13, "y1": 13}, {"y2": 1, "y1": 5}, {"y1": -1}, {"n": None}, {"diff": None}):
        ok, msg = RC.check_growth({**good, **change})
        assert ok is False, (change, msg)
    assert "005930" in RC.check_growth({**good, "diff": ["005930"]})[1]
    assert RC.check_growth({})[0] is False
    # tests/test_app_data.py 의 '오늘 데이터' 비교와 같은 계산 · 같은 기준 (둘이 따로 바뀌지 않게)
    with open(os.path.join(ROOT, "tests", "test_app_data.py"), encoding="utf-8") as f:
        src = f.read()
    for piece in ("for (const s of d.stocks) { if (s.cls !== 'kr' || s.g3 == null) continue; const k = co.get(s.t); out.n++;",
                  " const a = D.krGrowthBasis(s.g3, k ? k.rev : null), b = E.growthBasis(s, k || null); if (a !== b) out.diff.push(s.t);",
                  " out[a || 'none']++; }"):
        assert piece in src and piece in RC.GROWTH_JS, piece
    assert RC.GROWTH_MIN == 1000


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_real_data_check_compares_growth_with_node(tmp_path):
    got = RC.growth_compare(os.path.join(ROOT, "tests", "fixtures", "v2"))
    assert got["n"] >= 300 and got["diff"] == [] and got["y2"] > got["y1"] >= 0, got


def test_real_data_check_never_skips_a_check_it_cannot_run(tmp_path):
    d = fixture_dir(tmp_path)
    rows = RC.run_all(d, node="/nonexistent/node")                          # node 를 못 돌리면 그 검사는 실패 (건너뜀 아님)
    assert [r[0] for r in rows] == ["데이터 파일 읽기 (data · corp · disc · macro)", "2.0 이 쓰는 항목", "매출 성장 기준: 예전 뱁새 = 2.0"]
    assert [r[1] for r in rows] == [True, True, False] and "검사하지 못했어요" in rows[2][2]
    assert RC.main(["--data", d]) == 1                                      # 고정 시험 데이터는 종목이 적어서(1,000개 이하) 발행 검사로는 실패예요

    def no_node(*a, **k):
        return None
    import shutil as _sh
    orig = _sh.which
    _sh.which = no_node
    try:
        with pytest.raises(RuntimeError, match="node 가 없어요"):
            RC.growth_compare(d)
    finally:
        _sh.which = orig
    (tmp_path / "corp.json").unlink()                                       # 파일이 없으면
    rows = RC.run_all(d)
    assert len(rows) == 1 and rows[0][1] is False and "corp.json" in rows[0][2]
    (tmp_path / "corp.json").write_text('{"companies": [{"per": NaN}]}')     # NaN 이 있으면
    rows = RC.run_all(d)
    assert len(rows) == 1 and rows[0][1] is False and "NaN" in rows[0][2]
    (tmp_path / "corp.json").write_text('{"companies": []}')
    (tmp_path / "disc.json").write_text('{"x": Infinity}')                   # disc.json 도 엄격하게 읽어요 (네 파일 모두)
    rows = RC.run_all(d)
    assert len(rows) == 1 and rows[0][1] is False and "disc.json" in rows[0][2] and "Infinity" in rows[0][2]
    (tmp_path / "disc.json").write_text("{}")
    (tmp_path / "corp.json").write_text('{"companies": "x"}')               # 모양이 달라 검사가 죽어도 실패로 남아요
    rows = RC.run_all(d)
    assert [r[1] for r in rows][0] is True and not all(r[1] for r in rows)
    assert RC.main(["--data", d]) == 1


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_real_data_check_passes_end_to_end_on_good_data(tmp_path, monkeypatch, capsys):
    """스크립트를 처음부터 끝까지: 좋은 데이터면 3 / 3 통과로 exit 0. 그날의 발행 파일이 아니라 고정 시험 데이터로 봐요
    (종목 수 기준만 그 데이터에 맞게 낮춰요) — 진짜 데이터로는 매일 실행과 브랜치 시험 실행이 돌려요."""
    monkeypatch.setattr(RC, "GROWTH_MIN", 300)
    assert RC.main(["--data", fixture_dir(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "3 / 3 통과" in out and "FAIL" not in out, out


# ── tests/smoke_launch.py --data · tests/smoke_app.py --data: 그 폴더의 파일만 ──
# 여기서는 --data 의 행동만 봐요 (옵션 없이 돌 때의 데이터는 이 테스트가 정하지 않아요: #104 가 고정 데이터로 옮겨요).
def stopped_before_any_check(r, path):
    """실패로 끝났고, 검사 줄(PASS · 통과)이 하나도 없고, 못 읽은 그 파일의 경로를 말해요."""
    out = r.stdout + r.stderr
    return r.returncode != 0 and "PASS" not in r.stdout and "통과" not in r.stdout and path in out


def test_smoke_launch_data_option_reads_only_that_folder(tmp_path):
    pytest.importorskip("playwright.sync_api")
    if not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")):
        pytest.skip("node_modules 가 없어요 (npm ci 전) — smoke_launch 는 시작할 수 없어요")
    script = os.path.join(ROOT, "tests", "smoke_launch.py")
    # 폴더에 파일이 없으면 브라우저를 열기 전에 멈춰요 (저장소의 파일 · 고정 시험 데이터로 조용히 바꾸지 않아요)
    r = subprocess.run([sys.executable, script, "--data", str(tmp_path)], capture_output=True, text=True)
    assert stopped_before_any_check(r, os.path.join(str(tmp_path), "data.json")), r.stdout + r.stderr[-400:]
    # 2.0 이 쓰는 항목이 빠진 데이터('준비 중' · '불러오지 못했어요' 화면이 뜰 데이터)는 발행 전 검사에서 통과가 아니에요
    d = fixture_dir(tmp_path, lambda f: [s.pop("d1", None) for s in f["data.json"]["stocks"]])
    r = subprocess.run([sys.executable, script, "--data", d], capture_output=True, text=True)
    assert r.returncode != 0 and "PASS" not in r.stdout and "빠진 데이터예요 (d1)" in r.stderr, r.stdout + r.stderr[-400:]


def test_smoke_app_data_option_reads_only_that_folder(tmp_path):
    """매일 실행이 부르는 `smoke_app.py --data .` 는 그 폴더의 네 파일을 읽어요: 폴더에 파일이 없으면 다른 데이터(저장소의 파일 ·
    고정 시험 데이터)로 조용히 바꾸지 않고, 브라우저를 열기 전에 멈춰요. (#104 가 기본 데이터를 고정본으로 바꿔도 --data 는 그대로여야 해요.)"""
    pytest.importorskip("playwright.sync_api")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "smoke_app.py"), "--data", str(tmp_path)], capture_output=True, text=True)
    assert stopped_before_any_check(r, os.path.join(str(tmp_path), "data.json")), r.stdout + r.stderr[-400:]


# ── 2026-11-12 (Jack): 화면 검사는 회사 하나에 매이지 않아요 — 회사 하나가 목록에서 빠졌다고 모두의 데이터 발행이 멈추면 안 돼요 ──
@pytest.fixture
def SA():
    """tests/smoke_app.py (Playwright 가 있어야 불러올 수 있어요 — 불러올 때 데이터 파일은 읽지 않아요)."""
    pytest.importorskip("playwright.sync_api")
    import smoke_app
    return smoke_app


class Stub:
    """아무 일도 하지 않는 창 · 서버 · 페이지."""
    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeRunner:
    """브라우저 없는 Runner: 창을 연 횟수와 장면이 등록한 검사 이름만 적어요 (검사 함수는 돌리지 않아요)."""
    def __init__(self):
        self.results, self.errors, self.console, self.unseen, self.notes, self.opened = [], [], [], [], [], 0

    def open(self, *a, **kw):
        self.opened += 1
        return Stub(), Stub(), Stub(), "http://127.0.0.1:0"

    def check(self, page, scene, name, fn):
        self.results.append((f"[{scene}] {name}", True, "등록만"))


def tiny_files(corp, stocks=()):
    """장면이 회사를 고를 때 보는 것만 담은 데이터: 목록(data.json stocks)과 회사(corp.json companies)."""
    return {"data.json": {"stocks": [{"t": c["t"], "nk": "회사" + c["t"]} for c in corp] + [{"t": "005930", "nk": "삼성전자"}] + list(stocks)},
            "corp.json": {"companies": [dict(c) for c in corp] + [{"t": "005930"}, {"t": "777777", "stmtCur": "USD"}]},   # 777777: 목록에 없는 회사
            "disc.json": {}, "macro.json": {}}


def test_smoke_app_picks_companies_by_rule_not_by_name(SA):
    f = tiny_files([{"t": "950160", "stmtCur": "USD"}, {"t": "241560", "stmtCur": "USD"}, {"t": "900110", "stmtCur": "CNY"}, {"t": "008700", "stmtCur": "JPY"},
                    {"t": "950250"}, {"t": "000020", "stmtCur": "KRW"}, {"t": "000040", "stmtCur": "XXX"}, {"t": "000050", "stmtCur": "usd"},
                    {"t": "90001", "stmtCur": "USD"}, {"t": "9500001"}])
    # 원화가 아닌 통화로 공시: 데이터의 표시(stmtCur, 앱과 같은 규칙)만 봐요. 국내 코드 먼저, 그다음 종목코드 순. 목록에 없는 회사는 못 열어요.
    assert [c["t"] for c in SA.non_won_companies(f)] == ["008700", "241560", "90001", "900110", "950160"]
    # 해외 기업: 9로 시작하는 여섯 자리 (통화 표시가 있든 없든)
    assert [c["t"] for c in SA.foreign_companies(f)] == ["900110", "950160", "950250"]
    assert [SA.stmt_cur_of({"stmtCur": v}) for v in ("USD", "KRW", "XXX", "usd", "US", "", None, 3)] == ["USD", None, None, None, None, None, None, None]
    assert SA.stmt_cur_line("JPY") == "이 회사는 재무제표를 원화가 아닌 JPY로 공시해서, 실적 숫자는 아직 보여 드리지 않아요."
    # 장면이 회사를 이름(종목코드)으로 고르지 않아요: 설명 글 밖에는 두산밥캣의 코드가 없어요
    src = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()
    assert '"241560"' not in src and "corp=241560" not in src and "'241560'" not in src
    a, b = src.index("def scene_stmt_cur("), src.index("def scene_foreign_issuer(")
    body = src[a:src.index("\ndef ", a + 1)]
    assert "non_won_companies(f)" in body and "foreign_companies(f)" in src[b:b + 1500]
    # 통화 줄은 고른 회사의 통화를 따라요 (USD 로 못 박지 않아요)
    assert "LINE = stmt_cur_line(CUR)" in body and "T, CUR = co[\"t\"], stmt_cur_of(co)" in body and '"USD"' not in body


def test_smoke_app_stmt_cur_scene_follows_the_first_company_the_data_marks(SA, monkeypatch):
    monkeypatch.setattr(SA, "build_site", lambda f: "site")
    monkeypatch.setattr(SA, "REAL_DATA", True)
    R = FakeRunner()
    SA.scene_stmt_cur(R, tiny_files([{"t": "900110", "stmtCur": "CNY"}, {"t": "950170", "stmtCur": "JPY"}]))
    assert R.opened == 1 and len(R.results) == 1 and "기업분석 900110 (stmtCur CNY)" in R.results[0][0] and not R.unseen, R.results
    R = FakeRunner()
    SA.scene_stmt_cur(R, tiny_files([{"t": "900110", "stmtCur": "CNY"}, {"t": "008700", "stmtCur": "JPY"}]))
    assert "기업분석 008700 (stmtCur JPY)" in R.results[0][0]                 # 국내 코드가 먼저


@pytest.mark.parametrize("scene, corp, said, still", [
    ("scene_stmt_cur", [{"t": "950250"}, {"t": "000020", "stmtCur": "KRW"}, {"t": "000040", "stmtCur": "XXX"}],
     "원화가 아닌 통화로 공시한다고 표시된 회사", "기업분석 005930"),                     # 삼성전자 쪽 절반은 그래도 봐요
    ("scene_foreign_issuer", [{"t": "241560", "stmtCur": "USD"}], "해외 기업(종목코드 9…)", None),
    ("scene_foreign_issuer", [{"t": "950250"}], "재무제표 통화(stmtCur)가 붙은 둘째 해외 기업", "950250"),   # 하나뿐: 첫 줄은 보고, 둘째 회사만 없음
    ("scene_foreign_issuer", [{"t": "900110", "stmtCur": "CNY"}], "재무제표 통화(stmtCur)가 붙은 둘째 해외 기업", "900110"),
])
def test_smoke_app_scene_with_no_such_company_today(SA, monkeypatch, capsys, scene, corp, said, still):
    """오늘 데이터에 그 장면이 볼 회사가 하나도 없을 때. 실제 데이터(--data): 크게 알리고 통과 — 발행을 막지 않아요. 그 밖(CI): 실패."""
    monkeypatch.setattr(SA, "build_site", lambda f: "site")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(SA, "REAL_DATA", True)
    R = FakeRunner()
    getattr(SA, scene)(R, tiny_files(corp))
    out = capsys.readouterr().out
    unseen = [r for r in R.results if "확인 못 함" in r[0]]
    assert len(unseen) == 1 and unseen[0][1] is True and all(r[1] for r in R.results), R.results
    assert len(R.unseen) == 1 and said in R.unseen[0]
    assert (R.opened, [r[0] for r in R.results if r is not unseen[0] and still in r[0]].__len__()) == (1, 1) if still else R.opened == 0, R.results
    loud = [ln for ln in out.splitlines() if ln.startswith("!! 확인 못 함")]
    assert len(loud) == 1 and said in loud[0] and "오늘 확인하지 못했어요" in loud[0], out
    assert sum(ln.startswith("::warning title=발행 전 화면 검사 · 확인 못 한 장면::") for ln in out.splitlines()) == 1
    if scene == "scene_stmt_cur":                                             # 무엇을 의심해야 하는지 (통화를 못 읽은 파이프라인) · 읽을 수 없는 표시의 수
        assert "파이프라인이 통화를 못 읽은 것일 수 있어요" in loud[0] and "읽을 수 없는 회사 1곳 (000040)" in loud[0], loud[0]
    assert "고정 데이터" not in out                                           # #104 전에는 CI 도 그날 데이터로 돌아요: 없는 것을 약속하지 않아요
    # 고정 데이터 · 저장소 데이터로 돌 때는 실패로 남아요 (조용히 건너뛰면 그 장면은 아무도 안 본 게 돼요)
    monkeypatch.setattr(SA, "REAL_DATA", False)
    R = FakeRunner()
    getattr(SA, scene)(R, tiny_files(corp))
    out = capsys.readouterr().out
    bad = [r for r in R.results if not r[1]]
    assert len(bad) == 1 and said in bad[0][2] and not R.unseen, R.results
    assert "  FAIL  " in out and "::warning" not in out and "!! 확인 못 함" not in out


def test_smoke_app_is_lenient_about_a_missing_company_only_with_the_data_option(SA, monkeypatch):
    """'해당 회사 없음 → 통과'는 --data DIR 로 돌 때만 켜져요 (매일 실행). 옵션 없이 돌면(CI) 꺼져 있어요."""
    class Stop(Exception):
        pass

    def stop(*a):
        raise Stop(a)
    for reader in ("read_data", "read_snapshot"):               # 데이터를 읽는 순간 멈춰요 (read_snapshot: #104 의 고정 데이터 읽기)
        monkeypatch.setattr(SA, reader, stop, raising=False)
    for argv, want in ((["smoke_app.py", "--data", "/somewhere"], True), (["smoke_app.py"], False), (["smoke_app.py", "--part", "1/2"], False)):
        monkeypatch.setattr(SA, "REAL_DATA", not want)
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(Stop):
            SA.main()
        assert SA.REAL_DATA is want, argv


# ── 내장 종목이 오늘 데이터에 없거나 값이 빈 날 · 금 환산인 날: 앱이 안내를 보여 주는 게 맞아요 (리뷰 2026-11-12) ──
MERGE_JS = r"""
import fs from 'fs';
import { pathToFileURL } from 'url';
const { mergeStocks } = await import(pathToFileURL(process.argv[3]).href);
const { base, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = cases.map((live) => {
  const m = mergeStocks(base.map((t) => ({ t, nk: t, price: 1, beta: 1, vol: 1 })), live);
  return { examples: m.filter((s) => s.live === false && !s.est).map((s) => s.t).sort(), est: m.filter((s) => s.est).map((s) => s.t).sort() };
});
console.log(JSON.stringify(out));
"""


def banner_cases(SA):
    ok = lambda t, **kw: {"t": t, "price": 10.0, "beta": 1.0, "vol": 20.0, **kw}
    full = [ok(t) for t in SA.BASE_TICKERS]
    drop = lambda *gone: [s for s in full if s["t"] not in gone]
    swap = lambda t, **kw: [ok(t, **kw) if s["t"] == t else s for s in full]
    return [full,                                                             # 모두 있음 → 안내 없음
            drop("247540"), drop("247540", "TSLA"),                           # 상장폐지 · 빠짐
            swap("TSLA", beta=None), swap("005930", vol=None), swap("AAPL", price=None),   # 값이 빈 하루
            swap("04020000", est=True), swap("04020000", est=True, beta=None),            # 금 환산 (값이 비어도 금 환산 줄만)
            [s for s in full if s["t"] != "BRK.B"] + [ok("BRK-B")],                       # 표기만 다른 티커는 같은 종목
            full + [ok("999990")], full + [ok("999991", beta=None)],                      # 내장 목록 밖 종목은 안내와 무관
            full + [ok("999992", est=True)], full + [{"t": "999993", "price": None, "est": True}],
            drop("247540") + [ok("04020000", est=True)],                                  # (중복 줄: 앱과 같은 순서로 맞추는지)
            # 2026-11-27 (Jack, 답 7): 과거 주가 기록 오류 표시(pxBad) — 가격이 오늘 것이면 빈 베타 · 변동성이어도 예시 가격이 아니에요 (#128).
            # 가격이 비면 예시 가격 · 빈 글자나 문자열이 아닌 표시는 표시가 아니에요 · 표시가 있어도 다른 종목의 빈 값은 그대로 예시 가격
            swap("042700", beta=None, vol=None, pxBad="2024-06-24"),                      # [14] 내장 종목 · 실제 가격 → 안내 없음
            swap("000660", vol=None, pxBad="2024-06-24"),                                 # [15] 필수 종목도 같아요
            swap("042700", price=None, beta=None, vol=None, pxBad="2024-06-24"),          # [16] 가격이 비면 예시 가격
            swap("042700", beta=None, vol=None, pxBad=""),                                # [17] 빈 글자 표시 → 표시 아님 → 예시 가격
            swap("042700", beta=None, vol=None, pxBad=20240624),                          # [18] 문자열이 아닌 표시 → 예시 가격
            [ok(t, beta=None, vol=None, pxBad="2024-06-24") if t == "042700" else ok(t, beta=None) if t == "TSLA" else s
             for t, s in ((x["t"], x) for x in full)],                                    # [19] 표시 종목은 빼고 TSLA 만
            swap("04020000", est=True, beta=None, pxBad="2024-06-24"),                    # [20] 금 환산은 금 환산 줄 그대로
            full + [ok("999994", beta=None, vol=None, pxBad="2024-06-24")]]               # [21] 내장 목록 밖 표시 종목: 안내와 무관


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_example_price_rule_is_the_apps_own(SA, tmp_path):
    """smoke_app.example_price_stocks 는 앱의 mergeStocks 와 같은 답을 내요 (앱의 코드를 node 로 돌려 비교)."""
    cases = banner_cases(SA)
    (tmp_path / "in.json").write_text(json.dumps({"base": SA.BASE_TICKERS, "cases": cases}), encoding="utf-8")
    (tmp_path / "probe.mjs").write_text(MERGE_JS, encoding="utf-8")
    r = subprocess.run([NODE, str(tmp_path / "probe.mjs"), str(tmp_path / "in.json"), os.path.join(ROOT, "src", "data.js")],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]
    app = json.loads(r.stdout)
    mine = [dict(zip(("examples", "est"), SA.example_price_stocks({"data.json": {"stocks": live}}))) for live in cases]
    assert mine == app
    assert app[0] == {"examples": [], "est": []} and app[1]["examples"] == ["247540"] and app[3]["examples"] == ["TSLA"] and app[6]["est"] == ["04020000"]
    assert app[11] == {"examples": ["999992"], "est": []}                     # 내장 목록 밖 종목의 est 는 '예시 가격' 쪽 (앱이 그래요)
    # pxBad (Jack 2026-11-27, 답 7): 가격이 오늘 것이면 안내 없음 · 가격이 비거나 표시가 표시가 아니면 예시 가격 · 금 환산은 그대로
    assert app[14] == app[15] == app[21] == {"examples": [], "est": []}
    assert app[16]["examples"] == app[17]["examples"] == app[18]["examples"] == ["042700"] and app[19]["examples"] == ["TSLA"]
    assert app[20] == {"examples": [], "est": ["04020000"]}
    assert len(SA.BASE_TICKERS) == len(set(SA.BASE_TICKERS)) >= 60


class FakePage:
    def __init__(self, lines):
        self.lines = lines

    def locator(self, sel):
        lines = self.lines if sel == ".nonLiveBanner > div" else (["x"] if self.lines else [])
        return type("L", (), {"count": lambda s: len(lines), "all_inner_texts": lambda s: list(lines)})()


def test_banner_check_follows_the_data_only_with_real_data(SA, monkeypatch, capsys):
    ok = lambda t, **kw: {"t": t, "price": 10.0, "beta": 1.0, "vol": 20.0, **kw}
    full = [ok(t) for t in SA.BASE_TICKERS]
    gone = {"data.json": {"stocks": [s for s in full if s["t"] != "247540"]}}
    gold = {"data.json": {"stocks": [ok(s["t"], est=True) if s["t"] == "04020000" else s for s in full if s["t"] != "TSLA"]}}
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    # CI · 내 컴퓨터: 언제나 '배너 없음'을 요구해요 (예전 그대로) — 알림도 없어요. 데이터에 그런 종목이 있으면 그 자리에서 실패:
    # 고정 데이터에는 없어야 하고, 없는데도 있다고 하면 내장 종목 목록을 잘못 읽은 것 (CI 에서 먼저 드러나요)
    monkeypatch.setattr(SA, "REAL_DATA", False)
    R = FakeRunner()
    assert SA.banner_due(R, "정상", {"data.json": {"stocks": full}}) == []
    for bad in (gone, gold):
        with pytest.raises(AssertionError, match="고정 데이터에는 없어야 해요"):
            SA.banner_due(R, "정상", bad)
    assert not R.notes and capsys.readouterr().out == ""
    monkeypatch.setattr(SA, "BASE_TICKERS", SA.BASE_TICKERS + ["ZZZZ"])     # 목록을 잘못 읽은 날: 데이터는 멀쩡해도 CI 가 실패
    with pytest.raises(AssertionError, match="ZZZZ"):
        SA.banner_due(R, "정상", {"data.json": {"stocks": full}})
    monkeypatch.undo()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    # 실제 데이터: 모두 있으면 [], 빠진 종목이 있으면 '예시 가격' 줄, 금 환산이면 그 줄도 (앱이 그리는 순서) — 한 번만 크게 알려요
    monkeypatch.setattr(SA, "REAL_DATA", True)
    assert SA.banner_due(R, "정상", {"data.json": {"stocks": full}}) == [] and not R.notes
    assert SA.banner_due(R, "정상", gone) == [SA.NONLIVE] and SA.banner_due(R, "미국 자기 날짜", gone) == [SA.NONLIVE]
    out = capsys.readouterr().out
    assert len(R.notes) == 1 and "247540" in R.notes[0] and out.count("!! 알림  [정상]") == 1 and out.count("::warning title=발행 전 화면 검사 · 예시 가격 안내가 뜨는 날::") == 1
    assert SA.banner_due(R, "정상", gold) == [SA.NONLIVE, SA.GOLD_EST] and "TSLA" in R.notes[1] and "04020000" in R.notes[1]
    assert "파이프라인을 의심하세요" in R.notes[0]
    # 한도: 예시 가격 종목이 EXAMPLE_MAX 개까지는 안내를 확인하고 통과, 넘으면 실패 (여러 종목이 한꺼번에 = 파이프라인 고장 → 발행 없음)
    assert SA.EXAMPLE_MAX == 3
    us = [t for t in SA.BASE_TICKERS if t.isalpha()]
    blank = lambda n: {"data.json": {"stocks": [ok(s["t"], beta=None) if s["t"] in us[:n] else s for s in full]}}
    gold3 = {"data.json": {"stocks": [ok(s["t"], est=True) if s["t"] == SA.GOLD_SPOT else s for s in blank(3)["data.json"]["stocks"]]}}
    for fine in ({"data.json": {"stocks": full}}, gone, gold, blank(3), gold3):
        SA.within_example_cap(fine)                                           # 한도 이내: 통과 (안내가 맞게 뜨는지는 장면이 봐요)
    assert SA.banner_due(R, "정상", blank(3)) == [SA.NONLIVE] and SA.banner_due(R, "정상", gold3) == [SA.NONLIVE, SA.GOLD_EST]
    with pytest.raises(AssertionError, match="파이프라인 고장으로 봐요.*아주 떠난 회사인지.*BASE_STOCKS"):
        SA.within_example_cap(blank(4))
    with pytest.raises(AssertionError, match="발행하지 않아요"):
        SA.within_example_cap(blank(len(us)))                                 # 미국 종목 베타가 통째로 빈 날
    with pytest.raises(AssertionError, match="금현물.*말고 다른 종목"):          # 금 환산 표시는 금현물에만
        SA.within_example_cap({"data.json": {"stocks": [ok(s["t"], est=True) if s["t"] in ("TSLA", SA.GOLD_SPOT) else s for s in full]}})
    # 한도 검사는 실제 데이터로 돌 때 장면들 앞에서 한 번 (실패 줄 하나) — CI 의 검사 목록은 그대로
    src0 = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()
    assert src0.count("within_example_cap(fresh)") == 1 and "        if REAL_DATA:       # 장면들 앞에서 한 번" in src0
    assert '::error title=발행 전 화면 검사 · 내장 종목 한도::{e}' in src0 and '!! 한도 초과  {e}' in src0   # 잘리지 않은 전체 이유도 찍어요
    assert src0.index("within_example_cap(fresh)") < src0.index("        for key, fn in scenes:")
    # 내장 종목 목록을 덜 읽거나 더 읽으면 불러오는 순간 멈춰요 (종목코드 수 = 이름 수)
    assert 'len(BASE_TICKERS) == len(set(BASE_TICKERS)) == len(re.findall(r"\\bnk:\\s*\\"", _block))' in src0
    # 배너 줄 비교: 떠야 하는 줄이 정확히, 그 순서로 — 없어야 하면 배너 자체가 없어야 해요
    full_line = SA.NONLIVE + " (샘플)."
    assert SA.banner_is(FakePage([]), []) and not SA.banner_is(FakePage([full_line]), [])
    assert SA.banner_is(FakePage([full_line]), [SA.NONLIVE]) and not SA.banner_is(FakePage([]), [SA.NONLIVE])
    assert not SA.banner_is(FakePage([full_line, "다른 줄"]), [SA.NONLIVE]) and not SA.banner_is(FakePage([SA.GOLD_EST + "."]), [SA.NONLIVE])
    assert SA.banner_is(FakePage([full_line, SA.GOLD_EST + "."]), [SA.NONLIVE, SA.GOLD_EST]) and not SA.banner_is(FakePage([SA.GOLD_EST + ".", full_line]), [SA.NONLIVE, SA.GOLD_EST])
    assert SA.banner_is(FakePage([full_line, "AAPL …", "MSFT …"]), [SA.NONLIVE], extra=2) and not SA.banner_is(FakePage([full_line, "AAPL …"]), [SA.NONLIVE], extra=2)
    assert SA.banner_is(FakePage(["AAPL …", "MSFT …"]), [], extra=2) and not SA.banner_is(FakePage(["AAPL …", "MSFT …", "셋째"]), [], extra=2)
    # 세 곳의 검사가 이 규칙을 써요 (정상 · 미국 자기 날짜 둘)
    src = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()
    assert src.count("assert banner_is(page, due") == 3
    assert src.count("due = banner_due(R, S, files)") == 1 and src.count("due = banner_due(R, S, f)") == 1   # 각 장면이 자기가 띄운 데이터로
    assert 'assert page.get_by_text(NONLIVE).count() == (1 if NONLIVE in due else 0)' in src
    assert 'at < body.index(LINE, at) < body.index("PER", at)' in src         # 회사 이름에 PER 이 있어도 되게, 제목 뒤에서부터


def test_dividend_count_scene_does_not_depend_on_other_stocks_dividend_data(SA):
    """B안 장면은 '배당 정보가 없는 종목 1개' 알림을 봐요. 관문은 필수 종목 하나의 배당 자료가 빈 날을 경고로 통과시키므로 (Jack 2026-11-05),
    장면은 자기가 비운 한 종목 말고 나머지 셋의 빈 배당을 복사본에서 채워요 — 그 수가 언제나 1 이게."""
    src = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()
    a = src.index("def scene_option_b(")
    body = src[a:src.index("\ndef ", a + 1)]
    i, j = body.index('stocks[hold[0][0]]["dy"] = None'), body.index("for t, _ in hold[1:]:")
    assert i < j < body.index("profile = {")
    assert 'if not isinstance(stocks[t].get("dy"), (int, float)):' in body[j:j + 400] and 'stocks[t]["dy"] = 1.0' in body[j:j + 400]
    assert "files = json.loads(json.dumps(files))" in body[:i]                # 복사본에서만 (다른 장면 · 원본 데이터는 그대로)


# ── 2026-11-27 (Jack, 답 7): 과거 주가 기록 오류 표시(pxBad)가 붙은 종목 하나가 모두의 발행을 멈추지 않게 ──
READY_JS = r"""
import fs from 'fs';
import { pathToFileURL } from 'url';
const { mergeStocks } = await import(pathToFileURL(process.argv[3]).href);
const { base, cases } = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = cases.map((L) => {
  const r = mergeStocks(base.map((t) => ({ t, nk: t, price: 1, beta: 1, vol: 1 })), [L]).find((s) => s.t === L.t);
  return !!r && r.live !== false && !r.noRisk && r.beta != null && r.vol != null;
});
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_risk_ready_is_the_apps_own_rule(SA, tmp_path):
    """smoke_app.risk_ready (장면이 위험 숫자를 보려고 담는 종목)는 앱의 mergeStocks 가 오늘 가격 · 베타 · 변동성을 그대로 위험 계산에 쓰는 종목
    (실시간이고 noRisk 가 아님)보다 느슨하지 않아요: 앱의 코드를 node 로 돌려 비교해요. 관문이 지키는 모양의 데이터에서는 같고, 몇 곳은 더
    엄격해요 (리뷰 #200 — 아래 stricter). 베타 · 변동성이 남은 pxBad 내장 종목은 앱도 쓰지 않아요 (그 표시 하나로 가려요)."""
    ok = lambda t, **kw: {"t": t, "price": 10.0, "beta": 1.0, "vol": 20.0, **kw}   # noqa: E731
    bad = dict(beta=None, vol=None, pxBad="2024-06-24")
    cases = [ok("005930"), ok("005930", beta=None), ok("005930", vol=None), ok("005930", price=None), ok("005930", **bad),
             ok("042700", **bad), ok("04020000", est=True), ok("999990"), ok("999991", beta=None), ok("999992", **bad),
             ok("999993", price=None), ok("999994", price=0), ok("999995", est=True),
             ok("005930", pxBad="2024-06-24")]                                    # 표시만 있고 베타 · 변동성은 남음: 앱도 쓰지 않아요
    stricter = [ok("005930", price=0), ok("999996", pxBad="2024-06-24"), ok("005930", beta=True), ok("005930", vol="20")]   # 앱은 써요
    cases += stricter
    (tmp_path / "in.json").write_text(json.dumps({"base": SA.BASE_TICKERS, "cases": cases}), encoding="utf-8")
    (tmp_path / "probe.mjs").write_text(READY_JS, encoding="utf-8")
    r = subprocess.run([NODE, str(tmp_path / "probe.mjs"), str(tmp_path / "in.json"), os.path.join(ROOT, "src", "data.js")],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]
    app = json.loads(r.stdout)
    mine = [SA.risk_ready(L) for L in cases]
    n = len(cases) - len(stricter)
    assert all(a or not m for a, m in zip(app, mine))                         # 앱보다 느슨한 곳은 없어요
    assert mine[:n] == app[:n] == [True, False, False, False, False, False, False, True, False, False, False, False, False, False]
    assert app[n:] == [True] * len(stricter) and mine[n:] == [False] * len(stricter)


def test_option_b_scene_picks_any_stocks_the_app_can_use(SA, monkeypatch, capsys):
    """B안 장면은 평소의 네 종목(SK하이닉스 · 삼성전자 · 현대차 · KB금융)을 담고, 그 가운데 오늘 위험 계산에 쓸 수 없는 종목(pxBad · 빈 베타나 변동성 ·
    빠짐)이 있으면 같은 조건의 다른 한국 보통주로 바꿔 담아요 (시가총액 순 · 업종 3곳 이상 · 크게 알림). 2026-11-23 감사: SK하이닉스에 표시가 붙으면
    '시험할 종목이 모자라요'로 모두의 발행이 멈췄어요."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    mk = lambda t, s, cap, **kw: {"t": t, "cls": "kr", "s": s, "price": 1000.0, "beta": 1.0 + cap / 1000, "vol": 30.0,   # noqa: E731
                                  "mdd": -30.0, "al": 1.0, "cap": cap, **kw}
    rows = [mk("000660", "semi", 700), mk("005930", "semi", 1000), mk("005380", "auto", 50), mk("105560", "holding", 49),
            mk("069500", "index", 950, fund=True), mk("005935", "semi", 900), mk("042700", "semi", 85), mk("373220", "battery", 80),
            mk("000270", "auto", 75, pxd="2026-11-25"), dict(mk("068270", "bio", 70), cap=None), mk("207940", "bio", 60),
            mk("035420", "platform", 55, al=None), mk("012450", "defense", 40),
            dict(mk("999990", "tech", 5000), cls="us"), mk("069660", "index", 4000, etf=True)]   # 한국 종목 아님 · ETF: 담지 않아요 (리뷰 #200 2차 N3)
    stocks = {s["t"]: s for s in rows}
    want = ["000660", "005930", "005380", "105560"]
    pick = lambda st: SA.pick_ready(R, "B안", st, want, 4, need=("mdd", "al"), secs=3)   # noqa: E731
    marked = lambda *ts: {t: (dict(s, beta=None, vol=None, al=None, mdd=None, pxBad="2024-06-24") if t in ts else s)   # noqa: E731
                          for t, s in stocks.items()}
    R = FakeRunner()
    assert pick(stocks) == want and not R.notes and capsys.readouterr().out == ""        # 평소: 예전과 같은 네 종목, 알림 없음
    # SK하이닉스 표시 → 남은 셋이 이미 업종 3곳이라 시가총액 순 첫 보통주: 펀드(069500) · 우선주(005935)는 건너뛰고 042700 (업종은 상관없어요)
    assert pick(marked("000660")) == ["005930", "005380", "105560", "042700"]
    out = capsys.readouterr().out
    assert len(R.notes) == 1 and "000660 과거 주가 기록 오류 표시(pxBad)" in R.notes[0] and "042700" in R.notes[0]
    assert out.count("!! 알림  [B안]") == 1 and out.count("::warning title=발행 전 화면 검사 · 바꿔 담은 종목::[B안] ") == 1
    # 현대차 · KB금융 표시 → 반도체 둘만 남아요: 업종 3곳이 되게 새 업종 먼저 (042700 은 반도체라 건너뛰고, 000270 은 마지막 확인 종가,
    # 068270 은 시가총액이 비어 건너뛰어요)
    assert pick(marked("005380", "105560")) == ["000660", "005930", "373220", "207940"]
    # 빈 베타(내장 값으로 메움 = 예시 가격) · 오늘 데이터에 없음 · 장면이 읽는 칸(al)이 빔 → 바꿔 담아요
    assert pick(dict(stocks, **{"000660": dict(stocks["000660"], beta=None)}))[3] == "042700"
    assert pick({t: s for t, s in stocks.items() if t != "105560"})[:3] == ["000660", "005930", "005380"]
    assert pick(dict(stocks, **{"005380": dict(stocks["005380"], al=None)}))[:3] == ["000660", "005930", "105560"]
    assert "필요한 칸(al)이 빔" in R.notes[-1] and any("105560 오늘 데이터에 없음" in n for n in R.notes)
    # 쓸 종목이 모자라면 짧은 목록 → 장면이 '시험할 종목이 모자라요'로 실패해요 (지어낸 종목을 담지 않아요)
    few = {t: s for t, s in marked(*[t for t in stocks if t not in ("005930", "005380")]).items()}
    assert pick(few) == ["005930", "005380"]
    # 장면은 이 규칙으로 담고, 업종 · 개수 확인은 그대로예요
    src = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()
    a = src.index("def scene_option_b(")
    body = src[a:src.index("\ndef ", a + 1)]
    assert 'want = ["000660", "005930", "005380", "105560"]' in body
    assert 'hold = list(zip(pick_ready(R, "B안", stocks, want, 4, need=("mdd", "al"), secs=3), (400, 150, 100, 100)))' in body
    assert 'assert len(hold) == 4 and len(secs) >= 3, f"시험할 종목이 모자라요: {hold} · 업종 {secs}"' in body
    assert "isinstance(stocks[t].get(\"vol\")" not in body                     # 예전 규칙(변동성만)은 이제 risk_ready 안에
    # 장면의 전제(연 변동성 > 프로필 상한)는 알리기만 해요 — 시장의 출렁임은 그날의 데이터라 실패하면 안 돼요 (리뷰 #200 2차 N1 · Jack 11-21)
    a = body.index("shown_vol = page.evaluate(VOL_SHOWN)")
    note = body[a:body.index('R.check(page, "B안", "② 구성', a)]
    assert "assert" not in note and "raise" not in note
    assert 'print(f"\\n!! 알림  [B안] {msg}\\n", flush=True)' in note and 'R.notes.append(f"B안: {msg}")' in note
    assert '::warning title=발행 전 화면 검사 · B안 장면의 전제::[B안] {msg}' in note
    assert "{shown_vol or '(못 읽음)'}" in note and "{profile['targetVolMaxPct']}%" in note


def test_example_limit_count_is_the_app_rule_without_marks(SA):
    """리뷰 #200 2차 S1: 한도가 세는 종목(example_cap_stocks)은 표시(pxBad)를 지운 데이터에서 앱의 규칙(example_price_stocks — node 로
    mergeStocks 와 맞춰 본 것)과 같은 답이에요. 그래서 빠진 내장 종목 · 빈 가격 · 빈 변동성 · 목록 밖 금 환산을 세는 줄 하나라도 빠지면 여기서 걸려요."""
    cases = banner_cases(SA)
    unmark = lambda live: [{k: v for k, v in s.items() if k != "pxBad"} for s in live]   # noqa: E731
    for live in cases:
        assert SA.example_cap_stocks({"data.json": {"stocks": live}}) == SA.example_price_stocks({"data.json": {"stocks": unmark(live)}}), live
    # 그 네 가지가 이 표에 있어요 (한도가 세야 하는 것)
    got = [SA.example_cap_stocks({"data.json": {"stocks": live}})[0] for live in cases]
    assert got[1] == ["247540"] and got[3] == ["TSLA"] and got[4] == ["005930"] and got[5] == ["AAPL"] and got[11] == ["999992"]
    assert got[14] == got[16] == ["042700"]                                   # 표시가 있어도 셉니다 (가격이 있든 없든)


def test_example_limit_still_counts_marked_built_ins(SA, monkeypatch, capsys):
    """리뷰 #200 (Opus B1 · Fable S1): '예시 가격' 안내는 앱의 규칙을 따르지만 (pxBad 내장 종목은 안내 없음), 내장 종목 한도(EXAMPLE_MAX)는 예전
    그대로 그 종목도 세요 — 표시가 한꺼번에 많이 붙는 날은 여전히 발행하지 않아요. 한도 안이면 실행 기록 · 경고에 이름을 크게 남겨요."""
    ok = lambda t, **kw: {"t": t, "price": 10.0, "beta": 1.0, "vol": 20.0, **kw}   # noqa: E731
    full = [ok(t) for t in SA.BASE_TICKERS]
    kr = [t for t in SA.BASE_TICKERS if t.isdigit() and len(t) == 6][:4]
    mark = lambda ts, **kw: {"data.json": {"stocks": [ok(s["t"], beta=None, vol=None, pxBad="2024-06-24", **kw) if s["t"] in ts else s   # noqa: E731
                                                      for s in full]}}
    blank = lambda ts: {"data.json": {"stocks": [ok(s["t"], beta=None) if s["t"] in ts else s for s in full]}}   # noqa: E731
    SA.within_example_cap(mark(kr[:3]))                                       # 표시 3개: 한도 안
    for four in (mark(kr), mark(kr, price=None), blank(kr)):                  # 표시 4개 · 가격도 빈 표시 4개 · 표시 없는 빈 베타 4개
        with pytest.raises(AssertionError, match="내장 종목 4개가 오늘 데이터에 없거나 가격 · 베타 · 변동성이 비었어요"):
            SA.within_example_cap(four)
    assert SA.example_cap_stocks(mark(kr[:3]))[0] == sorted(kr[:3]) and SA.example_price_stocks(mark(kr[:3]))[0] == []
    # 한도 검사는 예전 규칙(example_cap_stocks), 안내는 앱의 규칙(example_price_stocks)
    src = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()
    body = src[src.index("def within_example_cap("):src.index("\ndef ", src.index("def within_example_cap(") + 1)]
    assert "examples, est = example_cap_stocks(f)" in body and "example_price_stocks" not in body
    # 실제 데이터: 표시된 내장 종목은 안내 없음 (due []) + 이름을 한 번 크게 · 진짜 예시 가격 옆이면 안내도
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(SA, "REAL_DATA", True)
    R = FakeRunner()
    assert SA.banner_due(R, "정상", mark(kr[:3])) == [] and SA.banner_due(R, "미국 자기 날짜", mark(kr[:3])) == []
    out = capsys.readouterr().out
    assert len(R.notes) == 1 and all(t in R.notes[0] for t in kr[:3]) and "내장 종목 한도에는 세어요" in R.notes[0]
    assert out.count("!! 알림  [정상]") == 1 and out.count("::warning title=발행 전 화면 검사 · 과거 주가 기록 오류 내장 종목::[정상] ") == 1
    both = {"data.json": {"stocks": [ok(s["t"], beta=None) if s["t"] == kr[3] else s for s in mark(kr[:1])["data.json"]["stocks"]]}}
    assert SA.banner_due(FakeRunner(), "정상", both) == [SA.NONLIVE]
    # CI (고정 데이터): 안내 규칙은 앱과 같아요 — 표시된 내장 종목만 있으면 '배너 없음' 그대로, 알림 없음
    monkeypatch.setattr(SA, "REAL_DATA", False)
    R = FakeRunner()
    assert SA.banner_due(R, "정상", mark(kr[:1])) == [] and not R.notes


# ── 2026-11-28 (Jack 11-27, 답 7 · 삼성전자도 내장 종목이에요): 삼성전자(005930)에 과거 주가 기록 오류 표시가 붙어도 모두의 발행을 멈추지 않게 ──
def plain_rows():
    """pick_plain 이 고르는 모양의 종목들: 내장 한국 보통주 · 내장 밖 큰 종목 · 우선주 · 펀드 · ETF · 마지막 확인 종가 · 시가총액 빔 · 미국 종목."""
    mk = lambda t, s, cap, **kw: {"t": t, "cls": "kr", "s": s, "price": 1000.0, "beta": 1.0, "vol": 30.0,   # noqa: E731
                                  "sh": 0.5, "al": 1.0, "mdd": -30.0, "hi": 1200.0, "lo": 800.0, "cap": cap, "nk": "회사" + t, **kw}
    rows = [mk("005930", "semi", 1000), mk("000660", "semi", 780), mk("005935", "semi", 116), mk("402340", "holding", 90),   # 402340: 내장 밖
            mk("373220", "battery", 74), mk("207940", "bio", 62), mk("069500", "index", 950, fund=True), mk("069660", "index", 900, etf=True),
            mk("000270", "auto", 70, pxd="2026-11-25"), dict(mk("068270", "bio", 51), cap=None), mk("005380", "auto", 54), mk("105560", "bank", 51),
            dict(mk("AAPL", "tech", 5000), cls="us")]
    return {s["t"]: s for s in rows}


def marked(stocks, *ts, **kw):
    """파이프라인처럼 표시: pxBad · 베타 · 변동성 · 과거 값 비움."""
    gone = dict(beta=None, vol=None, al=None, sh=None, mdd=None, pxBad="2024-06-24", **kw)
    return {t: (dict(s, **gone) if t in ts else s) for t, s in stocks.items()}


def test_plain_pick_keeps_005930_and_swaps_only_to_a_stock_the_app_computes_for(SA, monkeypatch, capsys):
    """pick_plain: 005930 이 risk_ready 이면 언제나 005930 (알림 없음 · 장면이 읽는 다른 칸은 보지 않아요: 예전 장면과 같은 날 같은 종목). 앱이 그
    위험 숫자를 계산하지 못하는 날만 (pxBad · 빈 베타 · 데이터에 없음) 내장 한국 보통주를 시가총액 큰 순으로 — avoid 는 빼고, 장면이 읽는 칸(need)과
    다른 조건(also)을 갖춘 것만. 바꾸면 세 곳에 크게 (실행 기록 · GitHub 경고 · 다르게 확인한 것)."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    st = plain_rows()
    R = FakeRunner()
    assert SA.pick_plain(R, "시험", st) == ("005930", "삼성전자") and not R.notes and capsys.readouterr().out == ""
    # 표시 → 다음 내장 보통주 (내장 밖 402340 · 우선주 005935 · 펀드 · ETF 는 건너뛰어요) · 이름은 앱이 보여 주는 내장 이름
    assert SA.pick_plain(R, "시험", marked(st, "005930")) == ("000660", "SK하이닉스")
    out = capsys.readouterr().out
    assert len(R.notes) == 1 and R.notes[0].startswith("시험: ") and "005930 과거 주가 기록 오류 표시(pxBad)" in R.notes[0] and "000660" in R.notes[0]
    assert out.count("!! 알림  [시험] ") == 1 and out.count("::warning title=발행 전 화면 검사 · 바꿔 담은 종목::[시험] ") == 1
    # 장면이 함께 담는 종목(avoid)은 고르지 않아요 · 마지막 확인 종가(000270) · 시가총액이 빈 종목(068270)도
    assert SA.pick_plain(FakeRunner(), "시험", marked(st, "005930"), avoid=("000660",))[0] == "373220"
    assert SA.pick_plain(FakeRunner(), "시험", marked(st, "005930", "000660", "373220", "207940"), avoid=("105560",))[0] == "005380"
    # 이유마다: 표시 없는 빈 베타(앱은 내장 예시 값 · 예시 가격) · 데이터에 없음
    for rows, why in ((dict(st, **{"005930": dict(st["005930"], beta=None)}), "베타 · 변동성 · 가격이 위험 계산에 쓸 값이 아님"),
                      ({t: s for t, s in st.items() if t != "005930"}, "오늘 데이터에 없음")):
        R = FakeRunner()
        assert SA.pick_plain(R, "시험", rows)[0] == "000660", why
        assert len(R.notes) == 1 and f"005930 {why}" in R.notes[0], (why, R.notes)
    # risk_ready 인 005930 은 장면이 읽는 다른 칸 · 조건이 비어도 그대로 (예전과 같은 날 같은 종목 · 알림 없음) — 그 칸은 바꿔 담는 종목에만
    R = FakeRunner()
    assert SA.pick_plain(R, "시험", dict(st, **{"005930": dict(st["005930"], sh=None)}), need=("sh",))[0] == "005930"
    assert SA.pick_plain(R, "시험", st, also=lambda s: s["t"] != "005930")[0] == "005930" and not R.notes
    no_sh = dict(marked(st, "005930"), **{"000660": dict(st["000660"], sh=None)})
    assert SA.pick_plain(R, "시험", no_sh, need=("sh",))[0] == "373220"                 # 000660 은 sh 가 비어 건너뛰어요
    assert SA.pick_plain(R, "시험", marked(st, "005930"), also=lambda s: s["t"] not in ("000660", "373220"))[0] == "207940"
    # 같은 장면 · 같은 바꿈은 한 번만 알려요 (한 장면이 여러 번 골라도) · 다른 장면은 따로
    R = FakeRunner()
    for scene in ("가", "가", "나"):
        SA.pick_plain(R, scene, marked(st, "005930"))
    assert [n.split(":")[0] for n in R.notes] == ["가", "나"]
    # 쓸 종목이 없으면 그 자리에서 실패 (지어낸 종목을 담지 않아요) · want 를 avoid 에 넣는 실수도
    kr = [t for t, s in st.items() if s.get("cls") == "kr"]
    with pytest.raises(AssertionError, match="시험할 종목이 모자라요"):
        SA.pick_plain(FakeRunner(), "시험", marked(st, *kr))
    with pytest.raises(AssertionError):
        SA.pick_plain(FakeRunner(), "시험", st, avoid=("005930",))


def test_plain_pick_is_never_looser_than_risk_ready_and_is_deterministic(SA):
    """무작위 데이터 3,000 개: 고른 종목은 언제나 risk_ready · avoid 밖이에요. 005930 이 risk_ready 이면 언제나 005930. 아니면 need 칸 숫자 · also ·
    내장 한국 보통주 · 펀드 · ETF · 마지막 확인 종가 아님 · 시가총액 있음인 종목 가운데 시가총액이 가장 큰 것 (없으면 실패). 데이터 순서를 섞어도 같은 답."""
    import random
    rnd = random.Random(20261128)
    base = plain_rows()
    pool = set(SA.BASE_TICKERS)
    for _ in range(3000):
        st = {}
        for t, s in base.items():
            s = dict(s)
            for k, bad in (("beta", None), ("vol", None), ("price", None), ("price", 0), ("sh", None), ("pxBad", "2024-06-24"), ("pxBad", ""),
                           ("est", True), ("vol", "30"), ("beta", True), ("cap", None), ("pxd", "2026-11-25")):
                if rnd.random() < 0.08:
                    s[k] = bad
            s["cap"] = s["cap"] if s.get("cap") is None else rnd.choice([s["cap"], rnd.uniform(1, 2000)])
            if rnd.random() > 0.05:
                st[t] = s
        avoid = tuple(t for t in ("000660", "105560", "373220") if rnd.random() < 0.3)
        need = tuple(k for k in ("sh", "hi") if rnd.random() < 0.3)
        also = (lambda s: s["t"] != "207940") if rnd.random() < 0.3 else None
        ok = lambda s: SA.risk_ready(s) and all(SA._num(s.get(k)) for k in need) and (also is None or also(s))   # noqa: E731
        cands = sorted((s for s in st.values() if s["t"] in pool and s["t"] not in avoid and s.get("cls") == "kr" and s["t"].endswith("0")
                        and not s.get("fund") and not s.get("etf") and s.get("pxd") is None and SA._num(s.get("cap")) and ok(s)),
                       key=lambda s: (-s["cap"], s["t"]))
        want = "005930" if "005930" in st and SA.risk_ready(st["005930"]) else (cands[0]["t"] if cands else None)
        try:
            got = SA.pick_plain(FakeRunner(), "무작위", st, avoid=avoid, need=need, also=also)[0]
        except AssertionError:
            got = None
        assert got == want, (got, want, avoid, need)
        if got:
            assert SA.risk_ready(st[got]) and got not in avoid and (got == "005930" or ok(st[got]))
        items = list(st.items())
        rnd.shuffle(items)
        again = None
        try:
            again = SA.pick_plain(FakeRunner(), "무작위", dict(items), avoid=avoid, need=need, also=also)[0]
        except AssertionError:
            pass
        assert again == got


CORP_JS = r"""
import fs from 'fs';
import { pathToFileURL } from 'url';
const B = await import(pathToFileURL(process.argv[3]).href);
const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify(cases.map((c) => { const d = B.OLD.decomposeReturn(c);
  return { shows: !B.RP.pxBad(c) && !!d && !d.why, epsThen: d && !d.why ? d.epsThen : null }; })));
"""


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_decomp_pick_is_never_looser_than_the_app(SA, tmp_path):
    """고치는 중 장면의 주가 분해 확인이 고르는 회사(decomp_numbers)는 앱(src/corp.jsx decomposeReturn · DecompCard 의 pxBad)이 '이익(EPS) 변화'
    숫자를 보여 주는 회사이고, 그 3년 전 EPS 가 장면의 식과 같아요: 앱의 코드를 esbuild 로 묶어 node 로 돌려 비교해요. 앱이 보여 주는데 고르지 않는
    곳(더 엄격한 곳)은 괜찮아요 (영수증 's' · 주식 수 shm 이 빈 회사)."""
    sam = {"t": "005930", "r36": 160.3, "eps": 32017.0, "shm": 5846.28, "ni": [452068.0, 344513.5, 154871.0], "nio3": [442609.6, 336213.6, 144734.0],
           "epsIn": {"ni": 2128708.5, "b": "o", "p": "ttm", "sh": 6648649811}}
    today = {k: v for k, v in sam.items() if k not in ("epsIn", "nio3")}
    cases = [sam, today, dict(sam, pxBad="2024-06-24", r36=None), dict(sam, pxBad="2024-06-24"), dict(sam, r36=None), dict(sam, r36=-100.0),
             dict(sam, eps=-5.0), dict(sam, nio3=[1.0, 1.0, -91124.3]), dict(today, ni=[1.0, 1.0, -5.0]), dict(sam, epsIn=dict(sam["epsIn"], b="s")),
             dict(sam, epsIn=dict(sam["epsIn"], b="t")), dict(sam, epsIn=dict(sam["epsIn"], sh=0)), dict(sam, shm=None), dict(today, shm=None),
             dict(sam, nio3=[1.0]), dict(today, ni=None), dict(sam, epsIn="o"), dict(sam, r36=-20.0), dict(sam, pxBad="")]
    entry = tmp_path / "entry.js"
    entry.write_text("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in (("OLD", "src/corp.jsx"), ("RP", "src/repair.js"))))
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, str(entry), "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx", "--charset=utf8",
                        "--external:react", "--external:react-dom", f"--outfile={tmp_path}/b.mjs", "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]
    os.symlink(os.path.join(ROOT, "node_modules"), tmp_path / "node_modules")
    (tmp_path / "in.json").write_text(json.dumps(cases), encoding="utf-8")
    (tmp_path / "probe.mjs").write_text(CORP_JS, encoding="utf-8")
    r = subprocess.run([NODE, str(tmp_path / "probe.mjs"), str(tmp_path / "in.json"), str(tmp_path / "b.mjs")], cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]
    app = json.loads(r.stdout)
    mine = [SA.decomp_numbers(c) for c in cases]
    for c, a, m in zip(cases, app, mine):
        if m:                                                                 # 고른 회사: 앱이 숫자를 보이고, 3년 전 EPS 가 장면의 식과 같아요
            assert a["shows"], c
            own = isinstance(c.get("epsIn"), dict) and c["epsIn"].get("b") == "o"
            then = c["nio3"][2] * 1e8 / c["epsIn"]["sh"] if own else c["ni"][2] * 100 / c["shm"]
            assert abs(a["epsThen"] - then) <= 1e-9 * abs(then), (c, a["epsThen"], then)
    assert mine == [True, True] + [False] * 15 + [True, True]                 # r36 이 음수여도 · 빈 글자 표시(표시 아님)여도 고를 수 있어요
    assert app[0]["shows"] and app[1]["shows"] and not app[2]["shows"] and not app[3]["shows"]
    assert app[9]["shows"] and app[12]["shows"]                               # 영수증 's' · shm 이 빈 회사: 앱은 보여요 — 장면은 고르지 않아요 (더 엄격)


class DeepStub:
    """무엇을 불러도 또 DeepStub (창 · 페이지 · 문맥): 장면의 준비 코드가 브라우저 없이 끝까지 돌게."""
    def __getattr__(self, name):
        return lambda *a, **k: DeepStub()


class SceneRunner(FakeRunner):
    """FakeRunner + 장면이 심는 저장본(localStorage)을 적어 둬요. 검사 함수는 돌리지 않아요."""
    def __init__(self):
        super().__init__()
        self.local, self.shots = [], None

    def open(self, *a, **kw):
        self.opened += 1
        self.local.append(kw.get("local") or {})
        return DeepStub(), DeepStub(), DeepStub(), "http://127.0.0.1:0"

    def new_context(self, *a, **kw):
        return DeepStub()

    def held(self):
        return {h.get("t") for loc in self.local for k, v in loc.items() if k.startswith("baepsae_v10_slot_")
                for h in json.loads(v).get("holdings", [])}


# 삼성전자를 보통 종목으로 담아 그 위험 숫자를 읽는 장면 (pick_plain 으로 바꾼 장면) · 장면 이름 · 저장본에 담는지
PLAIN_SCENES = [("scene_no_risk_holding", "위험값 없음", True), ("scene_missing_holding", "빠진 종목", True),
                ("scene_missing_all", "빠진 종목 전부", True), ("scene_beta_return", "베타→수익률", True),
                ("scene_ghost_holding", "없는 종목", True), ("scene_auto_settings", "자동 설정", True), ("scene_own_close", "미국 자기 날짜", True),
                ("scene_json_import", "파일 불러오기", True),
                ("scene_fix_notes", "고치는 중 안내 지금", False), ("scene_kst_dates", "한국 날짜", True), ("scene_px_bad", "주가기록", True),
                ("scene_kr_own_close", "국내 마지막 확인 종가", True)]


def mark_files(files, t, fields):
    """파이프라인처럼 표시 (data.json · corp.json): pxBad · pxBadF, 그 칸은 data.json 에서 빼고 corp.json 에서는 null."""
    f = json.loads(json.dumps(files, allow_nan=True))
    s = next(x for x in f["data.json"]["stocks"] if x.get("t") == t)
    c = next(x for x in f["corp.json"]["companies"] if x.get("t") == t)
    for k in fields:
        s.pop(k, None)
        if k in c:
            c[k] = None
    s.update(pxBad="2024-06-24", pxBadF=list(fields))
    c.update(pxBad="2024-06-24", pxBadF=list(fields))
    return f


@pytest.mark.parametrize("real", [False, True])
def test_scenes_hold_005930_on_fixed_data_and_swap_it_loudly_when_it_is_marked(SA, monkeypatch, capsys, tmp_path, real):
    """고정 데이터(CI)에서는 바꾼 장면들이 예전처럼 005930 을 담고 바꿈 알림이 없어요. 005930 에 파이프라인처럼 표시를 붙이면 (과거 주가 기록 오류 ·
    52주는 보임, 또는 52주까지) 장면마다 바꿈 알림이 하나씩 크게 (실행 기록 · GitHub 경고) 남고, 저장본에도 · 주가 분해 확인에도 005930 이 없어요 —
    다른 확인 (검색 · 이름 · 기업분석의 고치는 중 줄)은 005930 그대로."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(SA, "REAL_DATA", real)
    n = [0]

    def site(*a, **k):
        n[0] += 1
        p = tmp_path / f"site{n[0]}"
        p.mkdir()
        return str(p)
    monkeypatch.setattr(SA, "build_site", site)
    files, _ = SA.read_snapshot()
    fresh = SA.upgrade(json.loads(json.dumps(files, allow_nan=True)))

    def run(f, fn, scene):
        R = SceneRunner()
        if fn == "scene_fix_notes":
            SA.scene_fix_notes(R, f)
            SA.scene_fix_notes(R, f, live=True)
        else:
            getattr(SA, fn)(R, f)
        return R, [x for x in R.notes if "바꿔 담아" in x], [x[0] for x in R.results]
    for fn, scene, slots in PLAIN_SCENES:
        R, swaps, labels = run(fresh, fn, scene)
        assert not swaps, (fn, swaps)
        assert ("005930" in R.held()) if slots else any("주가 분해: 두 끝이 같은 기준 (005930)" in x for x in labels), (fn, R.held(), labels)
    capsys.readouterr()
    for bad in (mark_files(fresh, "005930", SA.PX_BAD_OLD), mark_files(fresh, "005930", SA.PX_BAD_Y)):   # 52주는 보임 · 52주까지
        for fn, scene, slots in PLAIN_SCENES:
            R, swaps, labels = run(bad, fn, scene)
            out = capsys.readouterr().out
            scenes = [scene] if fn != "scene_fix_notes" else ["고치는 중 안내 지금", "고치는 중 안내 끝"]
            assert [x.split(": ")[0] for x in swaps] == scenes and all("005930 과거 주가 기록 오류 표시(pxBad)" in x for x in swaps), (fn, swaps)
            for s in scenes:
                assert out.count(f"!! 알림  [{s}] ") == 1 and out.count(f"::warning title=발행 전 화면 검사 · 바꿔 담은 종목::[{s}] ") == 1, (fn, out[-800:])
            if slots:
                assert "005930" not in R.held() and R.held(), (fn, R.held())
            else:
                split = [x for x in labels if "주가 분해: 두 끝이 같은 기준" in x]
                assert len(split) == 2 and not any("(005930)" in x for x in split), split
                assert sum("기업분석 005930:" in x or "첫 화면 성적표 005930" in x for x in labels) == 6, labels   # 고치는 중 줄은 005930 그대로
    # 다시 읽은 뒤 장면의 '그대로' 비교 회사 (검사 안에서 골라요): 고정 데이터는 005930 · 표시가 붙으면 (52주는 보임 · 52주까지) 주가 분해 숫자를
    # 보여 주는 다른 회사로, 크게
    R = SceneRunner()
    assert SA.won_control(R, "다시 읽은 뒤", fresh) == "005930" and not R.notes
    for fields in (SA.PX_BAD_OLD, SA.PX_BAD_Y):
        g = mark_files(fresh, "005930", fields)
        R = SceneRunner()
        got = SA.won_control(R, "다시 읽은 뒤", g)
        c = next(x for x in g["corp.json"]["companies"] if x["t"] == got)
        assert got != "005930" and SA.decomp_numbers(c) and not SA.stmt_cur_of(c), got
        assert len(R.notes) == 1 and R.notes[0].startswith("다시 읽은 뒤: ") and "005930 과거 주가 기록 오류 표시(pxBad)" in R.notes[0], R.notes
        assert capsys.readouterr().out.count("!! 알림  [다시 읽은 뒤] ") == 1


def test_every_plain_swap_is_loud_and_goes_through_one_picker():
    """바꿔 담는 길은 pick_ready 하나 (pick_plain 은 그것을 불러요) · 그 함수가 세 곳에 크게 알려요 · 바꾼 장면들은 저장본 · 파일에 005930 을 직접 적지
    않아요 (고치는 중 장면은 005930 그대로인 다른 확인 — 회사 줄 하나와 첫 화면 성적표 검색 셋 — 에만)."""
    src = open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8").read()

    def body(name):
        a = src.index(f"def {name}(")
        return src[a:src.index("\ndef ", a + 1)]
    pr, pp = body("pick_ready"), body("pick_plain")
    for loud in ('R.notes.append(f"{scene}: {msg}")', 'print(f"\\n!! 알림  [{scene}] {msg}\\n", flush=True)',
                 'print(f"::warning title=발행 전 화면 검사 · 바꿔 담은 종목::[{scene}] {msg}", flush=True)'):
        assert pr.count(loud) == 1, loud
    assert "got = pick_ready(R, scene, stocks, [want], 1, need=need, avoid=avoid, pool=set(BASE_TICKERS), also=also)" in pp
    assert "if want in stocks and risk_ready(stocks[want]):" in pp                      # want 는 risk_ready 이면 그대로 (알림 없이 · 예전과 같은 날)
    assert "assert got, " in pp and "return t, BASE_NK.get(t) or stocks[t].get(\"nk\")" in pp
    # 고르는 곳은 이 둘뿐이고, 언제나 그 장면의 이름(R, 장면)과 함께 불러요 · 바꿈 문장은 pick_ready 에만
    calls = re.findall(r"\bpick_(?:ready|plain)\(([^,]+),", src)
    assert calls and set(calls) == {"R"}, calls
    assert src.count("바꿔 담아 ") == 1 and "바꿔 담아 " in pr
    inner = {"scene_auto_settings": "_auto_settings", "scene_json_import": "_json_import"}
    # 그대로 남는 005930: 고치는 중 장면의 다른 확인 (회사 줄 하나 · 첫 화면 성적표 검색 셋) · 파일 장면의 깨진 파일 글자와 종목이 없을 때의 자리 채움
    keep = {"scene_fix_notes": 4, "scene_json_import": 2}
    for fn, scene, _ in PLAIN_SCENES:
        b = body(inner[fn]) + body(fn) if fn in inner else body(fn)
        assert "pick_plain(R, " in b, fn
        code = "\n".join(ln.split("#")[0] for ln in b.splitlines())
        assert code.count('"005930"') == keep.get(fn, 0), (fn, code.count('"005930"'))
        assert '"t": "005930"' not in b and ('"ticker": "005930"' not in b or fn == "scene_json_import"), fn
    assert body("_json_import").count('"ticker": "005930"') == 1 and "'{\"app\": \"Baepsae\", \"holdings\": [{\"ticker\": \"005930\", \"amou'" in body("_json_import")
    assert 'co = next(c for c in corp["companies"] if c.get("t") == "005930")' in body("scene_fix_notes")
    st = body("scene_stmt_cur")                                                # 다시 읽은 뒤: '그대로' 회사는 검사 안에서 won_control 로
    assert st.count("#corp={won_control(R, S, f)}") == 2 and "#corp=005930" not in st and "return pick_plain(R, scene, " in body("won_control")


def test_screen_step_puts_an_unseen_scene_in_the_summary_and_still_publishes(tmp_path):
    msg = "[다시 읽은 뒤] 오늘 데이터에 재무제표를 원화가 아닌 통화로 공시한다고 표시된 회사(stmtCur)가 하나도 없어요"
    r, calls, rec = run_screen(tmp_path, unseen=msg)
    assert r.returncode == 0 and rec.exists(), (r.stdout, r.stderr)          # 회사 하나가 없다고 발행을 막지 않아요
    summary = (tmp_path / "summary.md").read_text()
    assert "### 뱁새 발행 전 화면 검사 — PASS" in summary and "확인하지 못했거나 다르게 확인한 장면" in summary and f"· 확인 못 함: {msg}" in summary, summary
    r, calls, rec = run_screen(tmp_path, unseen=msg, notice="[정상] 오늘 데이터: 내장 종목 1개")   # '알림' 줄도 요약에
    assert r.returncode == 0 and rec.exists() and "· 알림: [정상] 오늘 데이터: 내장 종목 1개" in (tmp_path / "summary.md").read_text()
    r, calls, rec = run_screen(tmp_path)                                     # 그런 장면이 없으면 그 문단도 없어요
    assert "다르게 확인한 장면" not in (tmp_path / "summary.md").read_text()


def test_browser_steps_get_no_secret_and_every_action_is_an_official_one_pinned_by_major():
    """Jack, 2026-11-12: 화면 검사와 그 준비 단계의 환경에는 비밀 값이 없어요. 두 워크플로의 action 은 모두 GitHub 공식(actions/…)이고
    다른 것들과 같은 방식(@v숫자)으로 고정돼 있어요."""
    st = update_steps()
    n = names(st)
    job = load("update-data.yml")["jobs"]["update"]
    wf = load("update-data.yml")
    for env in (wf.get("env") or {}, job.get("env") or {}):                  # 워크플로 · job 전체에 걸리는 환경에 비밀 값이 없어요
        assert not re.search(r"secrets\.|github\.token|GITHUB_TOKEN", json.dumps(env)), env
    for s in st[n.index(GATE) + 1:n.index("커밋 & 푸시")]:
        name = s.get("name") or s.get("uses")
        assert "env" not in s, name                                          # 단계의 환경을 따로 주지 않아요
        assert not re.search(r"secrets\.|github\.token|GITHUB_TOKEN|DART_API_KEY|ECOS_API_KEY", json.dumps(s, ensure_ascii=False)), name
    with_secret = [s.get("name") for s in st if re.search(r"secrets\.", json.dumps(s.get("env") or {}))]
    assert with_secret == ["데이터 수집"]                                      # DART · ECOS 열쇠를 받는 단계는 데이터 수집 하나뿐
    ci_text = open(os.path.join(WF, "ci.yml"), encoding="utf-8").read()
    assert "secrets." not in ci_text and "github.token" not in ci_text and "GITHUB_TOKEN" not in ci_text
    for name in ("update-data.yml", "ci.yml"):
        uses = re.findall(r"^\s*(?:- )?uses:\s*(\S+)", open(os.path.join(WF, name), encoding="utf-8").read(), re.M)
        assert uses and all(re.fullmatch(r"actions/[a-z-]+(?:/[a-z-]+)?@v\d+", u) for u in uses), (name, uses)
