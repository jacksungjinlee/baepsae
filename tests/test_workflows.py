# -*- coding: utf-8 -*-
"""v17.6: workflow 들의 안전 구조 — CI(ci.yml) · 배포(deploy.yml) · 감시(watchdog.yml) · 매일 실행(update-data.yml).

- 발행 관문이 배포 · 커밋 · data 브랜치보다 먼저, 같은 파일에. 발행 단계에 `|| true` · continue-on-error · if: always() 없음.
- data 브랜치에 쓰는 곳은 매일 실행의 한 단계뿐 (관문 영수증 확인). CI · 배포 · 감시는 저장소에 쓰지 못해요.
- 정해진 시각 6개 · 바깥 타이머 · 빈 DART 캐시 멈춤 · 확인 job 은 그대로 (자세한 것은 test_schedule.py).
- 빌드 도구 버전은 package.json 과 package-lock.json 에 정확히 같은 숫자로.
"""
import json
import os
import re
import stat
import subprocess

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")


def load(name):
    with open(os.path.join(WF, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def text(name):
    with open(os.path.join(WF, name), encoding="utf-8") as f:
        return f.read()


def steps(wf, job):
    return wf["jobs"][job]["steps"]


def names(st):
    return [s.get("name") or s.get("uses") for s in st]


def all_steps(wf):
    for job, j in wf["jobs"].items():
        for s in j.get("steps", []):
            yield job, s


def assert_no_hidden_failure(wf, allow_always=()):
    """continue-on-error 없음 · `|| true` 없음 · always() 는 허락한 단계(캐시 저장)에만."""
    for job, j in wf["jobs"].items():
        assert "continue-on-error" not in j, job
        if "if" in j:
            assert "always()" not in str(j["if"]), job
    for job, s in all_steps(wf):
        n = s.get("name") or s.get("uses")
        assert "continue-on-error" not in s, n
        assert "|| true" not in (s.get("run") or ""), n
        assert "set +e" not in (s.get("run") or ""), n
        if "always()" in str(s.get("if", "")) or "!cancelled()" in str(s.get("if", "")):
            assert n in allow_always, n


ALL = ("ci.yml", "deploy.yml", "watchdog.yml", "update-data.yml", "logo-dev-check.yml")


def test_the_four_workflows_exist_and_nothing_else():
    assert sorted(f for f in os.listdir(WF) if f.endswith((".yml", ".yaml"))) == sorted(ALL)


@pytest.mark.parametrize("name", ALL)
def test_no_workflow_hides_a_failure(name):
    assert_no_hidden_failure(load(name), allow_always=("DART 캐시 저장",) if name == "update-data.yml" else ())


@pytest.mark.parametrize("name", ["ci.yml", "deploy.yml", "watchdog.yml", "logo-dev-check.yml"])
def test_only_the_daily_run_can_write_to_the_repository(name):
    wf, raw = load(name), text(name)
    assert wf["permissions"] == {"contents": "read"}
    for job, j in wf["jobs"].items():
        assert (j.get("permissions") or {}).get("contents", "read") == "read", job
    assert "git push" not in raw and "git commit" not in raw and "push_data_branch" not in raw
    assert "DART_API_KEY" not in raw and "ECOS_API_KEY" not in raw


# ── CI ──
def test_ci_runs_build_tests_and_smoke_on_every_pr():
    wf = load("ci.yml")
    on = wf[True]
    assert on["pull_request"] in (None, {}) and on["push"] == {"branches": ["main"]}       # 모든 PR · main
    assert list(wf["jobs"]) == ["ci"] and wf["jobs"]["ci"]["name"] == "ci"                    # 보호 규칙이 찾는 이름
    st = steps(wf, "ci")
    node = next(s for s in st if s.get("uses", "").startswith("actions/setup-node"))
    assert re.fullmatch(r"\d+\.\d+\.\d+", node["with"]["node-version"])
    py = next(s for s in st if s.get("uses", "").startswith("actions/setup-python"))
    assert py["with"]["python-version"] == "3.11"                                              # 매일 실행과 같은 파이썬
    run = "\n".join(s.get("run") or "" for s in st)
    for need in ("npm ci", "pip install -r requirements-dev.txt", "playwright install --with-deps chromium",
                 "bash build.sh", "bash build-app.sh", "bash build-styleguide.sh",
                 "git diff --exit-code --stat -- baepsae.html app.html app-preview.html styleguide.html",
                 "python -m pytest tests/", "python tests/check_text.py"):
        assert need in run, need
    assert "npm install" not in run
    smoke = next(s for s in st if s.get("name", "").startswith("스모크"))["run"]
    for t in ("smoke_app", "smoke_v2", "smoke_preview", "smoke_styleguide", "smoke_launch"):
        assert t in smoke, t
    assert 'if python "tests/$t.py"; then' in smoke and "exit 1" in smoke
    assert wf["jobs"]["ci"]["timeout-minutes"] <= 20


def test_ci_smoke_step_really_fails_when_one_smoke_test_fails(tmp_path):
    """스모크 단계의 bash 를 그대로 돌려요: 다섯 중 하나만 실패해도 단계가 실패하고, 나머지도 끝까지 돌아요."""
    smoke = next(s for s in steps(load("ci.yml"), "ci") if s.get("name", "").startswith("스모크"))["run"]
    (tmp_path / "tests").mkdir()
    for t in ("smoke_app", "smoke_v2", "smoke_preview", "smoke_styleguide", "smoke_launch"):
        (tmp_path / "tests" / f"{t}.py").write_text(f"import sys\nprint('{t} 끝')\nsys.exit({1 if t == 'smoke_preview' else 0})\n")
    env = {"PATH": os.environ["PATH"]}
    r = subprocess.run(["bash", "-e", "-c", smoke], cwd=tmp_path, capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "스모크 테스트 실패: smoke_preview" in r.stdout and "smoke_launch 끝" in r.stdout
    (tmp_path / "tests" / "smoke_preview.py").write_text("print('ok')\n")
    assert subprocess.run(["bash", "-e", "-c", smoke], cwd=tmp_path, capture_output=True, text=True, env=env).returncode == 0


def test_build_tools_are_pinned_exactly_and_match_the_lock_file():
    pkg = json.load(open(os.path.join(ROOT, "package.json"), encoding="utf-8"))
    lock = json.load(open(os.path.join(ROOT, "package-lock.json"), encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert deps == {"esbuild": "0.24.2", "react": "19.2.5", "react-dom": "19.2.5"}           # 지금 사이트를 빌드한 버전
    for name, v in deps.items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", v), (name, v)                                    # ^ · ~ · 범위 없음
        assert lock["packages"][f"node_modules/{name}"]["version"] == v, name
    assert lock["packages"][""].get("devDependencies", {}) == pkg.get("devDependencies", {})


# ── 배포 ──
def test_deploy_gates_exactly_what_it_publishes():
    wf = load("deploy.yml")
    on = wf[True]
    assert on["push"] == {"branches": ["main"]} and "workflow_dispatch" in on
    assert on["workflow_run"] == {"workflows": ["시세 데이터 갱신"], "types": ["completed"], "branches": ["main"]}
    assert wf["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    b = wf["jobs"]["build"]
    assert b["needs"] == "decide" and b["if"] == "needs.decide.outputs.go == 'true'"
    st = steps(wf, "build")
    co = st[0]
    assert co["uses"].startswith("actions/checkout") and co["with"]["ref"] == "main"
    n = names(st)
    i_build = next(i for i, x in enumerate(n) if x.startswith("페이지 빌드"))
    i_data = n.index("data 브랜치의 데이터 받기")
    i_site = next(i for i, x in enumerate(n) if x.startswith("올릴 폴더 만들기"))
    i_gate = next(i for i, x in enumerate(n) if x.startswith("발행 관문"))
    i_up = next(i for i, x in enumerate(n) if x.startswith("actions/upload-pages-artifact"))
    assert i_build < i_site < i_gate < i_up and i_data < i_site and i_up == len(st) - 1
    assert st[i_site]["run"] == "python3 tools/assemble_site.py _site origin/data"
    data_step = st[i_data]["run"]
    assert '$2 == "refs/heads/data"' in data_step and "--heads" not in data_step              # 정확히 data 브랜치만
    assert st[i_gate]["run"].splitlines()[0] == "python validate_data.py --live --dir _site"
    assert st[i_up]["with"]["path"] == "_site"
    assert "npm ci" in st[n.index("라이브러리 설치 (package-lock.json · requirements.txt 그대로)")]["run"]
    assert 'BAEPSAE_BUILD="$(git rev-parse HEAD)"' in st[i_build]["run"]
    for s in st:
        assert "if" not in s, s.get("name")                                                  # 빌드 job 의 단계는 늘 다 돌아요
    d = wf["jobs"]["deploy"]
    assert d["needs"] == "build" and "if" not in d
    assert d["permissions"] == {"pages": "write", "id-token": "write"}
    assert d["environment"]["name"] == "github-pages"
    assert [s.get("uses", "").split("@")[0] for s in d["steps"]] == ["actions/deploy-pages"]
    assert wf["jobs"]["decide"]["permissions"] == {"actions": "read", "pages": "read"}


def _decide(tmp_path, event, mode, conclusion="success", pushed="success", ref="refs/heads/main"):
    """deploy.yml 의 '배포할지 정하기' 단계를 가짜 gh 로 그대로 돌려요."""
    step = steps(load("deploy.yml"), "decide")[0]
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    gh = bin_ / "gh"
    gh.write_text("#!/bin/bash\n"
                  'case "$*" in\n'
                  f'  *"/pages --jq .build_type"*) echo "{mode}" ;;\n'
                  f'  *"/jobs --jq"*) echo "{pushed}" ;;\n'
                  '  *) echo "unexpected gh $*" >&2; exit 9 ;;\n'
                  "esac\n")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    out = tmp_path / "out.txt"
    out.write_text("")
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_REF": ref, "GITHUB_REF_NAME": ref.rsplit("/", 1)[-1],
           "GITHUB_REPOSITORY": "o/r", "GITHUB_OUTPUT": str(out), "EVENT": event, "RUN_ID": "5", "RUN_CONCLUSION": conclusion}
    r = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]], env=env, capture_output=True, text=True)
    lines = out.read_text().split()
    return r.returncode, (lines[-1] if lines else None), r.stdout


def test_deploy_decides_safely(tmp_path):
    # 브랜치 배포인 동안: 자동 계기는 건너뛰고(알림), 손으로 누른 배포만 올려요
    assert _decide(tmp_path, "push", "legacy")[:2] == (0, "go=false")
    assert _decide(tmp_path, "workflow_run", "legacy")[:2] == (0, "go=false")
    assert _decide(tmp_path, "workflow_dispatch", "legacy")[:2] == (0, "go=true")
    # GitHub Actions 배포: 코드 머지 · 손으로 · data 브랜치에 실제로 올린 데이터 실행 뒤에만
    assert _decide(tmp_path, "push", "workflow")[:2] == (0, "go=true")
    assert _decide(tmp_path, "workflow_run", "workflow")[:2] == (0, "go=true")
    assert _decide(tmp_path, "workflow_run", "workflow", pushed="skipped")[:2] == (0, "go=false")      # 건너뛴 · 시험 실행
    assert _decide(tmp_path, "workflow_run", "workflow", pushed="none")[:2] == (0, "go=false")
    assert _decide(tmp_path, "workflow_run", "workflow", conclusion="failure")[:2] == (0, "go=false")
    # main 이 아닌 곳에서는 절대 배포하지 않아요
    rc, go, _ = _decide(tmp_path, "workflow_dispatch", "workflow", ref="refs/heads/claude/x")
    assert rc == 1 and go is None


def test_deploy_reads_the_step_that_really_wrote_the_data_branch():
    step = steps(load("deploy.yml"), "decide")[0]["run"]
    upd = load("update-data.yml")
    assert 'select(.name == "update")' in step and "update" in upd["jobs"]
    assert 'select(.name == "data 브랜치에 올리기")' in step
    assert "data 브랜치에 올리기" in names(steps(upd, "update"))


# ── 감시 ──
def test_watchdog_triggers_permissions_and_keepalive():
    wf = load("watchdog.yml")
    on = wf[True]
    crons = [c["cron"] for c in on["schedule"]]
    daily = next(c for c in crons if c.split()[2:] == ["*", "*", "*"])                    # 주말 포함 매일 (healthchecks.io 1일 주기)
    m, h = (int(x) for x in daily.split()[:2])
    assert 15 * 60 + 30 < ((h * 60 + m + 9 * 60) % (24 * 60)) < 18 * 60 and m not in (0, 30)   # 15:30 KST 뒤
    assert len(crons) == 2
    monthly = next(c for c in crons if c.split()[2:] == ["1", "*", "*"])
    assert on["workflow_run"] == {"workflows": ["시세 데이터 갱신", "Deploy"], "types": ["completed"], "branches": ["main"]}
    assert on["workflow_dispatch"]["inputs"]["selftest"]["default"] == "none"
    assert wf["concurrency"] == {"group": "watchdog", "cancel-in-progress": False}
    w, k = wf["jobs"]["watch"], wf["jobs"]["keepalive"]
    assert w["permissions"] == {"contents": "read", "issues": "write", "actions": "read", "pages": "read"}
    assert k["permissions"] == {"actions": "write"}
    assert w["if"] == f"github.event_name != 'schedule' || github.event.schedule != '{monthly}'"
    assert k["if"] == f"github.event_name == 'schedule' && github.event.schedule == '{monthly}'"
    keep = k["steps"][0]["run"]
    assert "update-data.yml watchdog.yml" in keep and "-X PUT" in keep and "/enable" in keep and "exit 1" in keep
    st = steps(wf, "watch")
    n = names(st)
    sleep = st[n.index("Pages 캐시 기다리기 (10분, max-age=600)")]
    assert sleep["run"] == "sleep 600" and "github.event_name == 'workflow_run'" in sleep["if"]
    check = st[n.index("사이트 점검")]
    assert check["run"] == "python3 watchdog.py" and check["env"]["HC_PING_URL"] == "${{ secrets.HC_PING_URL }}"
    assert n.index("지금 점검할지 (데이터 실행 · 배포 뒤)") < n.index("Pages 캐시 기다리기 (10분, max-age=600)") < n.index("사이트 점검")


def test_watchdog_names_match_the_workflows_it_follows():
    import sys
    sys.path.insert(0, ROOT)
    import watchdog as W
    assert load("update-data.yml")["name"] == W.DATA_NAME and load("deploy.yml")["name"] == W.DEPLOY_NAME
    assert W.DRY_MARK in load("update-data.yml")["run-name"]
    assert set(load("deploy.yml")["jobs"]) == {"decide", "build", "deploy"}


# ── 매일 실행 (update-data.yml) ──
SIX = ["47 18 * * 1-5", "13 20 * * 1-5", "43 21 * * 1-5", "17 23 * * 1-5", "53 1 * * 1-6", "37 4 * * 1-6"]


def test_daily_run_keeps_its_six_starts_timer_and_queue():
    wf = load("update-data.yml")
    assert [c["cron"] for c in wf[True]["schedule"]] == SIX
    assert wf[True]["workflow_dispatch"]["inputs"]["timer"] == {
        "description": wf[True]["workflow_dispatch"]["inputs"]["timer"]["description"], "type": "boolean", "default": False}
    assert wf["concurrency"] == {"group": "update-data-${{ inputs.dry_run && 'dry' || 'live' }}", "cancel-in-progress": False}
    assert wf["run-name"] == "${{ inputs.dry_run && '시세 데이터 갱신 · 시험 실행' || '시세 데이터 갱신' }}"
    assert wf["permissions"] == {"contents": "write"}


def test_daily_run_gate_comes_before_main_and_data_branch():
    st = steps(load("update-data.yml"), "update")
    n = names(st)
    i_gate, i_main, i_data = n.index("발행 관문 (validate_data.py)"), n.index("커밋 & 푸시"), n.index("data 브랜치에 올리기")
    assert i_gate < i_main < i_data == len(st) - 1
    gate = st[i_gate]["run"].strip().splitlines()
    i_v = next(i for i, ln in enumerate(gate) if ln.strip().startswith("python validate_data.py"))
    i_r = next(i for i, ln in enumerate(gate) if "gate-pass.sha256" in ln)
    assert i_v < i_r == len(gate) - 1                                                         # 영수증은 관문이 통과한 다음 줄에서만
    assert gate[i_r].strip() == 'sha256sum data.json corp.json disc.json macro.json > "$RUNNER_TEMP/gate-pass.sha256"'
    assert "if" not in st[i_gate]
    main_run, data_run = st[i_main]["run"], st[i_data]["run"]
    assert st[i_main]["if"] == st[i_data]["if"] == "${{ !inputs.dry_run }}"
    assert main_run.index('sha256sum --quiet --strict -c "$RUNNER_TEMP/gate-pass.sha256"') < main_run.index("git add")
    assert '[ "$GITHUB_REF" != "refs/heads/main" ]' in data_run and "exit 1" in data_run
    assert data_run.strip().splitlines()[-1].strip() == 'bash tools/push_data_branch.sh "$RUNNER_TEMP/gate-pass.sha256"'


def test_daily_run_gate_receipt_line_only_runs_after_a_pass(tmp_path):
    """관문 단계의 bash 를 가짜 validate_data.py 로 그대로 돌려요: 관문이 실패하면 영수증이 생기지 않아야 해요."""
    gate = next(s for s in steps(load("update-data.yml"), "update") if s.get("name") == "발행 관문 (validate_data.py)")["run"]
    for f in ("data.json", "corp.json", "disc.json", "macro.json"):
        (tmp_path / f).write_text("{}")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for rc, want in ((1, False), (0, True)):
        py = bin_ / "python"
        py.write_text(f"#!/bin/bash\nexit {rc}\n")
        py.chmod(py.stat().st_mode | stat.S_IEXEC)
        rec = tmp_path / "gate-pass.sha256"
        if rec.exists():
            rec.unlink()
        env = {"PATH": f"{bin_}:{os.environ['PATH']}", "RUNNER_TEMP": str(tmp_path), "BOOTSTRAP": "false", "PREV_REF": ""}
        r = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", gate], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert (r.returncode == 0) is want and rec.exists() is want, (rc, r.stdout, r.stderr)
