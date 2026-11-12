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
    for f in ("did.txt", "gate-pass.sha256", "screen-pass.sha256"):
        if (tmp_path / f).exists():
            (tmp_path / f).unlink()
    for name in receipts:
        subprocess.run(f"sha256sum data.json corp.json disc.json macro.json > {name}", shell=True, cwd=tmp_path, check=True)
    return {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": str(tmp_path), "GITHUB_REF": "refs/heads/main",
            "GITHUB_REF_NAME": "main", "TZ": "Asia/Seoul"}


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
            drop("247540") + [ok("04020000", est=True)]]                                  # (중복 줄: 앱과 같은 순서로 맞추는지)


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
    assert SA.banner_due(R, "정상", blank(3)) == [SA.NONLIVE]
    with pytest.raises(AssertionError, match="파이프라인 고장으로 봐요"):
        SA.banner_due(R, "정상", blank(4))
    with pytest.raises(AssertionError, match="발행하지 않아요"):
        SA.banner_due(R, "정상", blank(len(us)))                              # 미국 종목 베타가 통째로 빈 날
    assert SA.banner_due(R, "정상", {"data.json": {"stocks": [ok(s["t"], est=True) if s["t"] == "04020000" else s for s in blank(3)["data.json"]["stocks"]]}}) == [SA.NONLIVE, SA.GOLD_EST]
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
