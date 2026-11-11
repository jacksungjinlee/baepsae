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
CACHE_KEY = "playwright-v1-ubuntu-24.04-${{ hashFiles('requirements-dev.txt') }}"
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
                  'echo "2 / 2 통과"\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    return bin_


def run_screen(tmp_path, fail=(), gate_receipt=True, touch=""):
    for f in LIVE:
        (tmp_path / f).write_text("{}")
    for f in ("calls.txt", "screen-pass.sha256", "screen-summary.txt", "summary.md", "gate-pass.sha256"):
        if (tmp_path / f).exists():
            (tmp_path / f).unlink()
    bin_ = fake_bin(tmp_path, fail)
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
           "TOUCH": touch}
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
                assert c["with"] == {"path": "~/.cache/ms-playwright", "key": CACHE_KEY}, (name, k)   # 같은 보관본을 나눠 써요
                assert "restore-keys" not in c["with"]                        # 다른 판의 브라우저를 받아 쓰지 않아요
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
    assert lines == ["npm ci --prefer-offline", "pip install -r requirements-dev.txt"]
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
    assert r.returncode != 0


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


def test_real_data_check_passes_on_the_repository_data_when_it_is_there():
    """main 에 오늘 data.json · corp.json · macro.json 이 있는 동안은 그 파일로 스크립트를 처음부터 끝까지 돌려요 (매일 실행이 부르는 그대로)."""
    if not all(os.path.exists(os.path.join(ROOT, f)) for f in ("data.json", "corp.json", "macro.json")) or NODE is None:
        pytest.skip("저장소에 오늘 데이터가 없거나 node 가 없어요")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "real_data_check.py"), "--data", ROOT], capture_output=True, text=True)
    assert r.returncode == 0 and "3 / 3 통과" in r.stdout, r.stdout + r.stderr


# ── tests/smoke_launch.py --data · tests/smoke_app.py --data: 그 폴더의 파일만 ──
def test_smoke_launch_data_option_reads_only_that_folder(tmp_path):
    with open(os.path.join(ROOT, "tests", "smoke_launch.py"), encoding="utf-8") as f:
        src = f.read()
    assert 'variants = ("repo",) if args.data else ("fixtures", "repo")' in src      # 옵션이 없으면 예전 그대로 두 데이터 모두
    assert "shutil.copy(os.path.join(DATA_DIR, f), d)" in src and "DATA_DIR = ROOT" in src
    # 저장소의 파일은 옵션이 없을 때만 읽어요 (use_root): --data 면 그 폴더만
    assert src.count("real_data_missing()") == 1 and "def use_root():" in src
    assert "    if args.data:\n        use_data(args.data)\n    else:\n        use_root()\n" in src
    pytest.importorskip("playwright.sync_api")
    if not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")):
        pytest.skip("node_modules 가 없어요 (npm ci 전) — smoke_launch 는 시작할 수 없어요")
    script = os.path.join(ROOT, "tests", "smoke_launch.py")
    # 폴더에 파일이 없으면 브라우저를 열기 전에 멈춰요 (저장소의 파일로 조용히 바꾸지 않아요): 그 폴더의 data.json 을 못 찾았다는 오류
    r = subprocess.run([sys.executable, script, "--data", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode != 0 and "PASS" not in r.stdout, r.stdout + r.stderr[-400:]
    assert "FileNotFoundError" in r.stderr and os.path.join(str(tmp_path), "data.json") in r.stderr, r.stderr[-400:]
    # 2.0 이 쓰는 항목이 빠진 데이터('준비 중' · '불러오지 못했어요' 화면이 뜰 데이터)는 발행 전 검사에서 통과가 아니에요
    d = fixture_dir(tmp_path, lambda f: [s.pop("d1", None) for s in f["data.json"]["stocks"]])
    r = subprocess.run([sys.executable, script, "--data", d], capture_output=True, text=True)
    assert r.returncode != 0 and "PASS" not in r.stdout and "빠진 데이터예요 (d1)" in r.stderr, r.stdout + r.stderr[-400:]


def test_smoke_app_data_option_reads_only_that_folder(tmp_path):
    """매일 실행이 부르는 `smoke_app.py --data .` 는 그 폴더의 네 파일을 읽어요: 폴더에 파일이 없으면 다른 데이터(저장소의 파일 ·
    고정 시험 데이터)로 조용히 바꾸지 않고, 브라우저를 열기 전에 멈춰요. (#104 가 기본 데이터를 고정본으로 바꿔도 --data 는 그대로여야 해요.)"""
    pytest.importorskip("playwright.sync_api")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "smoke_app.py"), "--data", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode != 0 and "PASS" not in r.stdout and "통과" not in r.stdout, r.stdout + r.stderr[-400:]
    assert "FileNotFoundError" in r.stderr and os.path.join(str(tmp_path), "data.json") in r.stderr, r.stderr[-400:]
