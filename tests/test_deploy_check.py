# -*- coding: utf-8 -*-
"""배포 전 화면 검사 (Jack J6, 2026-11-12): deploy.yml 이 코드가 바뀌는 배포를 올리기 전에 매일 실행의 세 검사를 올릴 데이터 그대로 돌려요.

- 자리: 올릴 폴더(_site) · 발행 관문(--live) 다음, 올리기(upload-pages-artifact) 바로 앞. build job 의 단계에는 조건(if)이 없어요.
- 코드 배포(push · workflow_dispatch)는 늘 검사해요. 데이터 실행 뒤의 배포(workflow_run)는 그 실행이 검사한 커밋에서 지금 main 까지
  데이터 네 파일만 바뀌었고, 올릴 데이터가 그 실행이 올린 data 브랜치 커밋 그대로일 때만 건너뛰어요 (확인하지 못하면 검사해요).
- 결정은 검사 줄마다 (Jack J6 의 'a check'): 새 코드가 실패한 줄을 지금 사이트 코드가 통과하면 막음 · 새 코드가 실패한 줄을 지금 코드도 모두
  실패하면 올리고 알림 (data-alert 이슈 + deploy-check 표시) · 지금 코드를 알 수 없음 · 결과 줄 전에 멈춤 · 줄을 읽지 못함 → 막음.
  같은 코드(데이터 네 파일 말고는 같음)끼리는 막지 않아요: 한 번 더 돌려 통과하면 됐고, 또 실패하면 올리고 알려요.
- 토큰: checkout 은 토큰을 작업 폴더에 남기지 않아요. 토큰은 GitHub API 를 부르는 세 단계(관문 · 필요한지 · 결과)의 환경에만.
  지금 사이트 코드는 설치 스크립트 없이(npm ci --ignore-scripts) 따로 된 폴더에서 빌드하고, 저장소의 .git 에는 아무것도 받지 않아요.
- 올리기 · 배포 단계에 always() · continue-on-error 가 없어요. 올리기 바로 전 단계가 통과 영수증과 올릴 폴더를 맞춰 봐요.
"""
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")
TOOL = os.path.join(ROOT, "tools", "deploy_check.py")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import deploy_check as DC  # noqa: E402
import watchdog as W  # noqa: E402

GATE = "발행 관문 (validate_data.py --live, 올릴 파일 그대로)"
NEED = "배포 전 화면 검사가 필요한지 (코드가 바뀌는 배포만)"
TOOLS = "화면 검사 도구 설치 (requirements-dev.txt 그대로 · 검사하는 배포만)"
RESTORE = "브라우저 보관본 불러오기"
BROWSER = "브라우저 · 한글 글꼴 준비 (보관본 그대로 · 없을 때만 내려받기 · apt 없음 · 검사하는 배포만)"
CHECK = "배포 전 화면 검사 (올릴 데이터 그대로 · 새 코드, 실패하면 지금 사이트의 코드와 비교)"
REPORT = "배포 전 화면 검사 결과 (영수증 = 올릴 폴더 · 경보 이슈)"
SKIP_LINE = "if python3 tools/deploy_check.py skip; then exit 0; fi"
HEAD, LIVE, RUN = "a" * 40, "b" * 40, "c" * 40
TOKEN_RE = re.compile(r"github\.token|secrets\.|GITHUB_TOKEN|GH_TOKEN|x-access-token|extraheader|DART_API_KEY|ECOS_API_KEY|HC_PING")


def load(name):
    with open(os.path.join(WF, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def names(st):
    return [s.get("name") or s.get("uses") for s in st]


def build_steps():
    return load("deploy.yml")["jobs"]["build"]["steps"]


def step(name):
    return next(s for s in build_steps() if (s.get("name") or s.get("uses")) == name)


# ── 자리와 모양 ──
def test_code_deploys_run_the_three_checks_after_the_gate_and_right_before_upload():
    st = build_steps()
    n = names(st)
    i_site = next(i for i, x in enumerate(n) if x.startswith("올릴 폴더 만들기"))
    i_gate = n.index(GATE)
    i_up = n.index("actions/upload-pages-artifact@v5")
    assert i_site < i_gate and i_up == len(st) - 1
    assert n[i_gate + 1:i_up] == [NEED, TOOLS, RESTORE, BROWSER, CHECK, REPORT]          # 관문 다음 · 올리기 바로 앞, 이 순서로
    assert st[i_site]["run"].split()[2] == "_site" and st[i_up]["with"]["path"] == "_site"  # 검사하는 폴더 = 올리는 폴더
    assert step(CHECK)["run"].strip() == "python3 tools/deploy_check.py check --site _site"
    assert step(REPORT)["run"].strip() == "python3 tools/deploy_check.py report --site _site"
    assert step(NEED)["run"].strip() == "python3 tools/deploy_check.py need --site _site" and step(NEED)["id"] == "need"
    for s in st:                                                                              # 조건으로 건너뛰는 단계가 없어요
        assert "if" not in s and "continue-on-error" not in s, s.get("name") or s.get("uses")
    for name in (TOOLS, BROWSER):                                                             # 건너뛰기는 단계 안에서, 맨 앞 줄에서만
        lines = [ln.strip() for ln in step(name)["run"].strip().splitlines()]
        assert lines[0] == SKIP_LINE and step(name)["run"].count("deploy_check.py skip") == 1, name
    assert {k: step(k).get("timeout-minutes") for k in (NEED, TOOLS, RESTORE, BROWSER, CHECK, REPORT)} == {
        NEED: 5, TOOLS: 10, RESTORE: None, BROWSER: 10, CHECK: 45, REPORT: 5}
    job = load("deploy.yml")["jobs"]["build"]
    assert job["timeout-minutes"] >= 5 + 10 + 10 + 45 + 5 + 5
    assert job["permissions"] == {"contents": "read", "issues": "write"}                    # 경보 이슈만 (저장소에는 못 써요)


def test_upload_and_deploy_hang_on_the_check_result():
    """올리기 · 배포는 언제나 build job 의 모든 단계가 성공했을 때만: always() · continue-on-error · || true · set +e 가 없어요."""
    wf = load("deploy.yml")
    up = step("actions/upload-pages-artifact@v5")
    assert set(up) == {"uses", "with"}
    d = wf["jobs"]["deploy"]
    assert d["needs"] == "build" and "if" not in d and "continue-on-error" not in d
    assert [set(s) - {"name", "id", "uses"} for s in d["steps"]] == [set()]                    # 배포 단계: 조건 · 실패 삼키기 없음
    raw = open(os.path.join(WF, "deploy.yml"), encoding="utf-8").read()
    for bad in ("always()", "!cancelled()", "continue-on-error", "|| true", "set +e", "|| exit 0"):
        assert bad not in raw, bad
    assert wf["jobs"]["build"]["if"] == "needs.decide.outputs.go == 'true'"


# ── 토큰 (tests/test_publish_token.py 와 같은 방식) ──
def test_checkout_never_leaves_the_token_in_the_checkout():
    seen = 0
    for job in load("deploy.yml")["jobs"].values():
        for s in job.get("steps", []):
            if str(s.get("uses", "")).startswith("actions/checkout@"):
                seen += 1
                assert (s.get("with") or {}).get("persist-credentials") is False
    assert seen == 1


def test_only_the_steps_that_call_the_github_api_get_the_token():
    """build job 에서 토큰은 GitHub API 를 부르는 세 단계의 환경에만 (관문 --live · 필요한지 · 결과). 세 검사와 그 준비 단계(npm · pip
    패키지, 브라우저)에는 어떤 이름으로도 없고, job · workflow 전체의 env 로도 주지 않아요."""
    st = build_steps()
    with_token = [s.get("name") for s in st if "GITHUB_TOKEN" in (s.get("env") or {})]
    assert with_token == [GATE, NEED, REPORT]
    for s in st:
        if s.get("name") in with_token:
            assert s["env"]["GITHUB_TOKEN"] == "${{ github.token }}"
            others = {k: v for k, v in s["env"].items() if k != "GITHUB_TOKEN"}
            assert not TOKEN_RE.search(json.dumps(others, ensure_ascii=False)), s.get("name")
        else:
            assert not TOKEN_RE.search(json.dumps(s, ensure_ascii=False)), s.get("name") or s.get("uses")
    for name in (TOOLS, RESTORE, BROWSER, CHECK):
        assert "env" not in step(name), name
    wf = load("deploy.yml")
    for scope in (wf.get("env") or {}, wf["jobs"]["build"].get("env") or {}):
        assert not TOKEN_RE.search(json.dumps(scope, ensure_ascii=False)), scope
    assert step(NEED)["env"] == {"GITHUB_TOKEN": "${{ github.token }}", "EVENT": "${{ github.event_name }}",
                                 "RUN_HEAD": "${{ github.event.workflow_run.head_sha }}",
                                 "RUN_STARTED": "${{ github.event.workflow_run.run_started_at }}",
                                 "RUN_UPDATED": "${{ github.event.workflow_run.updated_at }}"}
    assert step(REPORT)["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    assert "secrets." not in open(os.path.join(WF, "deploy.yml"), encoding="utf-8").read()


def test_live_code_and_the_main_build_install_without_package_scripts():
    src = open(TOOL, encoding="utf-8").read()
    assert '["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]' in src and src.count('"npm", "ci"') == 1
    runs = [s.get("run") or "" for s in build_steps()]
    npm = [ln.strip() for r in runs for ln in r.splitlines() if ln.strip().startswith("npm ")]
    assert npm == ["npm ci --ignore-scripts"]                                                 # 배포의 빌드도 설치 스크립트 없이 (결과는 같아요)


def test_deploy_gets_the_browser_and_tools_the_same_way_as_the_daily_run():
    upd = load("update-data.yml")["jobs"]["update"]["steps"]
    daily_cache = next(s for s in upd if s.get("name") == "브라우저 보관본 불러오기")
    mine = step(RESTORE)
    assert mine["uses"] == "actions/cache/restore@v6"
    # 같은 보관본 (판 숫자를 올리면 함께) · restore-keys 없음 · 검사하지 않는 배포는 꺼내지 않고 있는지만 봐요
    assert mine["with"] == {**daily_cache["with"], "lookup-only": "${{ steps.need.outputs.run == 'no' }}"}
    daily_browser = next(s for s in upd if (s.get("name") or "").startswith("브라우저 · 한글 글꼴 준비"))["run"].strip().splitlines()
    assert [ln.strip() for ln in step(BROWSER)["run"].strip().splitlines()][1:] == [ln.strip() for ln in daily_browser]
    assert [ln.strip() for ln in step(TOOLS)["run"].strip().splitlines()][1:] == ["pip install -r requirements-dev.txt"]
    saves = [s for j in load("deploy.yml")["jobs"].values() for s in j.get("steps", []) if "cache/save" in s.get("uses", "")
             or s.get("uses", "").startswith("actions/cache@")]
    assert not saves                                                                          # 배포는 꺼내기만 (보관은 매일 실행 · CI)
    runs = "\n".join(s.get("run") or "" for j in load("deploy.yml")["jobs"].values() for s in j.get("steps", []))
    for bad in ("--with-deps", "install-deps", "apt-get", "apt install", "apt update", "dpkg "):
        assert bad not in runs, bad
    py = next(s for s in build_steps() if s.get("uses", "").startswith("actions/setup-python"))["with"]
    assert py["cache-dependency-path"].split() == ["requirements.txt", "requirements-dev.txt"]
    node = next(s for s in build_steps() if s.get("uses", "").startswith("actions/setup-node"))["with"]["node-version"]
    assert node == next(s for s in upd if s.get("uses", "").startswith("actions/setup-node"))["with"]["node-version"]


def test_the_three_checks_are_the_daily_runs():
    run = next(s for s in load("update-data.yml")["jobs"]["update"]["steps"]
               if s.get("name") == "발행 전 화면 검사 (오늘 데이터 · 헤드리스 크롬)")["run"]
    daily = re.search(r"for t in ([^;\n]+); do", run).group(1).split()
    assert list(DC.CHECKS) == daily == ["real_data_check", "smoke_launch", "smoke_app"]
    assert 'python "tests/$t.py" --data .' in run                                             # 같은 명령 모양 (아래에서 배포 쪽 명령을 봐요)
    for t in DC.CHECKS:
        assert os.path.isfile(os.path.join(ROOT, "tests", f"{t}.py")), t


class FakeProc:
    def __init__(self, lines, rc):
        self.stdout, self.rc = iter(lines), rc

    def wait(self):
        return self.rc


def test_each_check_runs_with_the_exact_command_and_no_script_annotations(monkeypatch, capsys):
    seen = []

    def popen(cmd, cwd=None, env=None, **kw):
        seen.append((cmd, cwd, env))
        return FakeProc(["  PASS  x\n", "\n", "3 / 3 통과\n"], 0)
    monkeypatch.setattr(DC.subprocess, "Popen", popen)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    got = DC.run_check("smoke_app", "/new", "/data/_site")
    assert got["outcome"] == DC.PASS and got["detail"] == "3 / 3 통과"
    cmd, cwd, env = seen[-1]
    assert cmd == [sys.executable, os.path.join("tests", "smoke_app.py"), "--data", "/data/_site"] and cwd == "/new"
    assert "GITHUB_ACTIONS" not in env                       # 스크립트의 ::error 가 초록 실행(알림 배포)에 빨갛게 남지 않게 — 알림은 이 도구가
    DC.run_check("smoke_app", "/live", "/data/_site", live=True)
    cmd, cwd, env = seen[-1]
    assert cwd == "/live" and "GITHUB_ACTIONS" not in env
    assert "::group::smoke_app · 새 코드" in capsys.readouterr().out


# ── 결과 줄 · 결과 표 읽기 ──
@pytest.mark.parametrize("rc, lines, want", [
    (0, ["3 / 3 통과"], DC.PASS),
    (1, ["  FAIL  x  y", "2 / 3 통과"], DC.FAIL),
    (1, ["!! --data: 빠진 데이터예요"], DC.CRASH),                 # 결과 줄 없이 멈춤
    (0, ["아무 말"], DC.CRASH),                                    # 0 으로 끝났어도 결과 줄이 없으면 통과가 아니에요
    (None, [], DC.CRASH),                                          # 시작도 못 함
    (0, ["2 / 3 통과"], DC.CRASH),                                 # 앞뒤가 맞지 않음
    (1, ["3 / 3 통과"], DC.CRASH),
    (0, ["0 / 0 통과"], DC.CRASH),                                 # 아무것도 검사하지 않음
    (0, ["1 / 2 통과", "3 / 3 통과"], DC.PASS),                     # 마지막 결과 줄
    (1, ["3 / 3 통과", "  FAIL  x", "144 / 145 통과"], DC.FAIL),
    (0, ["  145 / 145 통과 (덧붙인 말)"], DC.CRASH),               # 정확히 그 줄만 (매일 실행의 요약과 같은 줄)
])
def test_outcome_reads_the_result_line(rc, lines, want):
    assert DC.outcome(rc, lines)[0] == want


def smoke_out(rows, notes=(), progress=True, header="뱁새 스모크 테스트 결과 · 데이터: /x"):
    """smoke 스크립트처럼: 진행 줄 → 빈 줄 → 머리줄 → 폭을 맞춘 결과 표 → (알림) → 결과 줄. rows = [(이름, 통과?, 설명)]."""
    w = max(len(n) for n, _, _ in rows)
    out = [f"  {'PASS' if ok else 'FAIL'}  {n}" for n, ok, _ in rows] if progress else []
    out += ["", header] + [f"  {'PASS' if ok else 'FAIL'}  {n.ljust(w)}  {m}" for n, ok, m in rows]
    for nt in notes:
        out += ["", nt, "   · 무엇"]
    bad = sum(1 for _, ok, _ in rows if not ok)
    return out + ["", f"{len(rows) - bad} / {len(rows)} 통과"]


def rdc_out(rows):
    """real_data_check 처럼: '이름: 설명' 줄 (폭 맞춤 없음)."""
    out = ["발행 전 확인 (진짜 데이터 · 브라우저 없이) · 데이터: /x"]
    out += [f"  {'PASS' if ok else 'FAIL'}  {n}: {m}" for n, ok, m in rows]
    bad = sum(1 for _, ok, _ in rows if not ok)
    return out + ["", f"{len(rows) - bad} / {len(rows)} 통과"]


def test_failing_lines_are_read_from_the_final_table_by_name():
    rows = [("[정상] 검색: 삼성전자(005930)", True, ""), ("[정상] 30초 진단 열림 (KO)", False, "보이지 않아요"),
            ("[B안] 첫 화면: 30초 진단 소개에 '건강 점수' 없음 (1.2s)", False, "'건강 점수' 가 있어요"),
            ("페이지 오류 0건 (모든 장면)", True, "")]
    r = DC.parse_run(1, smoke_out(rows, notes=("!! 오늘 데이터라서 다르게 확인한 것 1개:",)))
    assert r["outcome"] == DC.FAIL and r["detail"] == "2 / 4 통과"
    assert r["fails"] == ["[정상] 30초 진단 열림 (KO)", "[B안] 첫 화면: 30초 진단 소개에 '건강 점수' 없음 (1.2s)"]   # 이름만 (설명 빼고)
    assert r["raw"][0][0] == "[정상] 30초 진단 열림 (KO)" and r["raw"][0][1].endswith("보이지 않아요")
    r = DC.parse_run(1, rdc_out([("데이터 파일 읽기 (data · corp · disc · macro)", True, "네 파일"),
                                 ("2.0 이 쓰는 항목", False, "빠진 항목: d1"),
                                 ("매출 성장 기준: 예전 뱁새 = 2.0", False, "한국 종목 0개 비교 · 다른 종목 0개")]))
    assert r["fails"] == ["2.0 이 쓰는 항목", "매출 성장 기준"]
    # 결과 표가 결과 줄과 맞지 않으면 (줄 수 · FAIL 수) 읽지 못한 것 → None
    broken = smoke_out(rows)
    broken[-1] = "1 / 4 통과"
    assert DC.parse_run(1, broken)["fails"] is None
    short = smoke_out(rows)
    del short[-4]
    assert DC.parse_run(1, short)["fails"] is None
    # 표 안에서 설명이 줄을 넘겨도(이어진 줄) 줄 수는 맞아요
    wrapped = smoke_out(rows)
    wrapped.insert(len(wrapped) - 3, "    at Object.<anonymous> (app.js:1:2)")
    assert DC.parse_run(1, wrapped)["fails"] == ["[정상] 30초 진단 열림 (KO)", "[B안] 첫 화면: 30초 진단 소개에 '건강 점수' 없음 (1.2s)"]


def test_names_are_never_cut_or_merged_and_collisions_make_the_table_unreadable():
    """리뷰 2회차: 이름 안의 두 칸 빈칸에서 자르지 않아요 · 끝의 숫자를 지우지 않아요 ('(45분)' 과 '(90분)' 은 다른 줄) · 실패한 줄의
    이름이 표의 다른 줄과 겹치거나 이름을 가를 수 없으면 읽지 못함(→ 막음)."""
    rows = [("[A]  두 칸 이름", False, "깨짐"), ("[A]", True, ""), ("[늦음] 발행 뒤 (45분)", False, "x"), ("[늦음] 발행 뒤 (90분)", True, "")]
    r = DC.parse_run(1, smoke_out(rows))
    assert r["fails"] == ["[A] 두 칸 이름", "[늦음] 발행 뒤 (45분)"], r                     # 잘리지 않고 ('[A]' 와 겹치지 않고) · 45분 ≠ 90분
    live = DC.parse_run(1, smoke_out([("[A]  두 칸 이름", True, ""), ("[A]", False, "x"), ("[늦음] 발행 뒤 (45분)", True, ""),
                                      ("[늦음] 발행 뒤 (90분)", False, "y")]))
    got, rows_ = DC.decide(with_(smoke_app=r), {"smoke_app": live})
    assert got == "block" and rows_[2]["new_only"] == ["[A] 두 칸 이름", "[늦음] 발행 뒤 (45분)"]
    dup = [("[정상] 같은 이름", False, "깨짐"), ("[정상] 같은 이름", True, ""), ("[정상] 다른", True, "")]
    assert DC.parse_run(1, smoke_out(dup))["fails"] is None                                   # 실패한 이름이 다른 줄과 겹침
    one = [("[A]  두 칸", False, "깨짐")]                                                       # 줄 하나 · 이름 안 두 칸: 이름 끝이 둘 → 모름
    assert DC.parse_run(1, smoke_out(one))["fails"] is None
    lead = [("[A] 하나", False, "  빈칸으로 시작하는 설명"), ("[B] 둘", True, "")]
    assert DC.parse_run(1, smoke_out(lead))["fails"] is None
    rdc = rdc_out([("2.0 이 쓰는 항목", False, "빠진 항목:  d1"), ("매출 성장 기준", True, "ok")])     # '이름: 설명' 표에 두 칸 빈칸
    assert DC.parse_run(1, rdc)["fails"] is None
    rdc_dup = rdc_out([("매출 성장 기준: 2년", False, "x"), ("매출 성장 기준: 1년", True, "y")])        # ': ' 앞이 겹침
    assert DC.parse_run(1, rdc_dup)["fails"] is None
    got, _ = DC.decide(with_(smoke_app=DC.parse_run(1, smoke_out(dup))), {"smoke_app": DC.parse_run(1, smoke_out(dup))})
    assert got == "block"


def test_smoke_launch_stopping_on_missing_2_0_fields_is_a_failing_line_not_a_crash():
    line = ("!! --data /tmp/x: 2.0 이 쓰는 항목이 빠진 데이터예요 (pxDate·publishedAt (v17.5 형식), ind, d1) → 발행 전 검사는 실패예요")
    r = DC.parse_run(1, ["Traceback 없음", line])
    assert r["outcome"] == DC.FAIL and r["fails"] == ["[데이터] 2.0 이 쓰는 항목이 빠진 데이터 (pxDate·publishedAt (v17.5 형식), ind, d1)"]
    assert DC.parse_run(0, [line])["outcome"] == DC.CRASH                                     # 0 으로 끝나면 앞뒤가 안 맞아요
    src = open(os.path.join(ROOT, "tests", "smoke_launch.py"), encoding="utf-8").read()       # smoke_launch 가 실제로 찍는 줄
    assert '2.0 이 쓰는 항목이 빠진 데이터예요 ({\', \'.join(missing)}) → 발행 전 검사는 실패예요' in src


# ── 결정 ──
def res(o, fails=None, d=None):
    detail = d or {DC.PASS: "3 / 3 통과", DC.FAIL: "2 / 3 통과", DC.CRASH: "끝까지 돌지 못했어요"}[o]
    return {"outcome": o, "detail": detail, "fails": ([] if o == DC.PASS else None if o == DC.CRASH else list(fails or ["x"]))}


ALL_PASS = {t: res(DC.PASS) for t in DC.CHECKS}


def with_(**kw):
    return {**ALL_PASS, **kw}


@pytest.mark.parametrize("new, live, unknown, want", [
    (ALL_PASS, None, None, "pass"),
    (with_(smoke_app=res(DC.FAIL, ["a"])), {"smoke_app": res(DC.PASS)}, None, "block"),            # 새 코드만 실패 → 막음
    (with_(smoke_app=res(DC.FAIL, ["a"])), {"smoke_app": res(DC.FAIL, ["a"])}, None, "alert"),     # 같은 줄을 지금 코드도 실패 → 올리고 알림
    (with_(smoke_app=res(DC.FAIL, ["a"])), {"smoke_app": res(DC.FAIL, ["a", "b"])}, None, "alert"),  # 새 코드가 줄 하나를 고침
    (with_(smoke_app=res(DC.FAIL, ["a", "b"])), {"smoke_app": res(DC.FAIL, ["a"])}, None, "block"),  # 새로 실패한 줄 b
    (with_(smoke_app=res(DC.FAIL, ["b"])), {"smoke_app": res(DC.FAIL, ["a"])}, None, "block"),       # 1/3 vs 2/3, 다른 줄
    (with_(smoke_app=res(DC.FAIL, ["a"])), None, "빌드 표시 없음", "block"),                         # 지금 코드를 알 수 없음
    (with_(smoke_app=res(DC.FAIL, ["a"])), {}, None, "block"),                                       # 지금 코드로 돌리지 않은 검사
    (with_(smoke_app=res(DC.CRASH)), {"smoke_app": res(DC.FAIL, ["a"])}, None, "block"),            # 새 코드만 결과 줄 전에 멈춤
    (with_(smoke_app=res(DC.CRASH)), {"smoke_app": res(DC.PASS)}, None, "block"),
    (with_(smoke_app=res(DC.FAIL, ["a"])), {"smoke_app": res(DC.CRASH)}, None, "block"),            # 지금 코드가 멈춤 = 알 수 없음
    (with_(smoke_app={"outcome": DC.FAIL, "detail": "2 / 3", "fails": None}), {"smoke_app": res(DC.FAIL, ["a"])}, None, "block"),
    (with_(smoke_app=res(DC.FAIL, ["a"])), {"smoke_app": {"outcome": DC.FAIL, "detail": "2 / 3", "fails": None}}, None, "block"),
    (with_(smoke_launch=res(DC.FAIL, ["a"]), smoke_app=res(DC.FAIL, ["z"])),                        # 스크립트마다: B 는 둘 다 실패해도
     {"smoke_launch": res(DC.PASS), "smoke_app": res(DC.FAIL, ["z"])}, None, "block"),             # A 가 새 코드만 실패면 막음
    (with_(real_data_check=res(DC.FAIL, ["r"]), smoke_app=res(DC.FAIL, ["z"])),
     {"real_data_check": res(DC.FAIL, ["r"]), "smoke_app": res(DC.FAIL, ["z"])}, None, "alert"),
    ({"real_data_check": res(DC.PASS), "smoke_app": res(DC.PASS)}, {}, None, "block"),             # 새 코드에서 돌지 않은 검사는 실패
])
def test_decide_compares_line_by_line(new, live, unknown, want):
    got, rows = DC.decide(new, live, unknown)
    assert got == want, rows
    assert [r["check"] for r in rows] == list(DC.CHECKS)


def test_decide_lists_the_lines_only_the_new_code_fails_first():
    names145 = [f"[장면{i}] 줄 {i}" for i in range(145)]
    new = with_(smoke_app=res(DC.FAIL, names145[:100], "45 / 145 통과"))
    live = {"smoke_app": res(DC.FAIL, [names145[0]], "144 / 145 통과")}
    got, rows = DC.decide(new, live)                                                          # 45/145 vs 144/145 → 막음
    row = next(r for r in rows if r["check"] == "smoke_app")
    assert got == "block" and row["verdict"] == "block" and len(row["new_only"]) == 99 and row["both"] == [names145[0]]
    assert "45 / 145 통과" in row["text"] and "144 / 145 통과" in row["text"] and "새 코드만 실패한 줄 99개" in row["text"]


def test_same_code_is_never_blocked_against_itself():
    """지금 사이트와 같은 코드(데이터 네 파일 말고는 같음)끼리 다른 결과는 흔들림이나 시계: 한 번 더 돌려 통과하면 됐고, 또 실패하면
    올리고 알려요. 막지 않아요 (그걸로 아침 데이터가 올라가지 못하면 안 돼요)."""
    new = with_(smoke_app=res(DC.FAIL, ["a"]))
    live = {"smoke_app": res(DC.PASS)}
    assert DC.decide(new, live, same=True)[0] == "block"                                      # 다시 돌리기 전
    got, rows = DC.decide(new, live, same=True, again={"smoke_app": res(DC.PASS)})
    assert got == "pass" and "흔들린" in rows[2]["text"]
    got, rows = DC.decide(new, live, same=True, again={"smoke_app": res(DC.FAIL, ["a"])})
    assert got == "alert" and "같은 코드" in rows[2]["text"] and rows[2]["kind"] == "same" and "두 번 실패" in rows[2]["text"]
    got, _ = DC.decide(new, {"smoke_app": res(DC.CRASH)}, same=True, again={"smoke_app": res(DC.FAIL, ["a"])})
    assert got == "alert"
    assert DC.decide(new, live, same=False, again={"smoke_app": res(DC.PASS)})[0] == "block"  # 다른 코드면 다시 돌리지 않아요
    assert DC.decide(new, None, "모름", same=True, again={"smoke_app": res(DC.PASS)})[0] == "block"


# ── 이 배포가 검사해야 하는지 ──
class Net:
    """GitHub API · 사이트를 흉내 내요. calls 에 GitHub 호출을 남겨요."""

    def __init__(self, compare=None, commits=None, issues=(), fail=None, pages=None):
        self.compare, self.commits = compare, commits or {}
        self.issues = [dict(i) for i in issues]
        self.fail, self.pages = fail, pages or {}
        self.calls, self.next_issue = [], 50

    def get(self, url, timeout=30):
        name = url.split("?")[0].rsplit("/", 1)[-1]
        if name not in self.pages:
            raise RuntimeError(f"{name}: ConnectionError")
        st, body = self.pages[name]
        return type("R", (), {"status_code": st, "content": body})()

    def gh(self, method, path, body=None, ok=(200, 201, 204)):
        self.calls.append((method, path, body))
        if self.fail and self.fail(method, path):
            raise RuntimeError(f"GitHub {method} {path}: 503")
        p = path.split("?")[0]
        if "/compare/" in p:
            return 200, self.compare
        if "/commits/" in p:
            files = self.commits[p.rsplit("/", 1)[-1]]
            return 200, {"files": [f if isinstance(f, dict) else {"filename": f} for f in files]}
        if method == "GET" and p.endswith("/issues"):
            return 200, [i for i in self.issues if i.get("state", "open") == "open"]
        if method == "POST" and p.endswith("/labels") and "/issues/" not in p:
            return 422, None
        if method == "POST" and p.endswith("/issues"):
            self.next_issue += 1
            i = {"number": self.next_issue, **body}
            self.issues.append(i)
            return 201, i
        if method == "PATCH" and "/issues/" in p:
            n = int(p.rsplit("/", 1)[-1])
            for i in self.issues:
                if i["number"] == n:
                    i.update(body)
            return 200, {"number": n}
        if method in ("POST", "DELETE"):
            return 200, {}
        raise AssertionError((method, path))


def window(*commits, status="ahead"):
    """compare 응답과 커밋별 파일: commits = [(sha, [파일 …]), …]."""
    cmp = {"status": status, "total_commits": len(commits), "commits": [{"sha": s} for s, _ in commits]}
    return Net(compare=cmp, commits={s: files for s, files in commits})


DATA = ["corp.json", "data.json", "disc.json", "macro.json"]
BOUND = lambda: (True, "올릴 데이터 = 그 실행이 올린 data 브랜치 커밋 d0d0d0d")  # noqa: E731


def test_code_deploys_always_run_the_checks():
    for event in ("push", "workflow_dispatch", "", "schedule"):
        run, why = DC.need_checks(event, RUN, HEAD, Net(), BOUND)
        assert run is True, (event, why)
    assert DC.need_checks("push", HEAD, HEAD, Net(), BOUND)[0] is True                        # 머지는 같은 커밋이어도 검사해요


def test_data_deploys_skip_only_when_nothing_but_the_four_data_files_changed_and_the_data_is_that_runs():
    # 실제 모양 (2026-11-12 아침): 매일 실행 43105073111 (head b519dfa) → data 커밋 403884a 하나 (데이터 네 파일) → Deploy 43108129970
    net = window(("d" * 40, DATA))
    run, why = DC.need_checks("workflow_run", RUN, HEAD, net, BOUND)
    assert run is False and "데이터 네 파일만" in why and "d0d0d0d" in why, why
    assert [c[1].split("?")[0] for c in net.calls] == [f"/repos/{W.REPO}/compare/{RUN}...{HEAD}", f"/repos/{W.REPO}/commits/{'d' * 40}"]
    assert DC.need_checks("workflow_run", HEAD, HEAD, Net(), BOUND)[0] is False               # 데이터 커밋이 없던 날 (같은 커밋)
    # 데이터가 그 실행의 것인지 확인하지 못하면 검사해요
    for bound in (lambda: (False, "올릴 폴더의 data.json 이 다름"), None, lambda: 1 / 0):
        assert DC.need_checks("workflow_run", RUN, HEAD, window(("d" * 40, DATA)), bound)[0] is True
        assert DC.need_checks("workflow_run", HEAD, HEAD, Net(), bound)[0] is True
    # 그 사이에 코드가 들어왔으면 (머지가 데이터 실행 도중에) 검사해요 — 그 코드로는 아무도 이 데이터를 검사하지 않았어요
    run, why = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, ["src/app.jsx", "app.html"]), ("d" * 40, DATA)), BOUND)
    assert run is True and "app.html" in why and "src/app.jsx" in why
    # 바뀌었다가 되돌아온 코드도 커밋마다 보니까 잡아요
    run, _ = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, ["src/a.js"]), ("f" * 40, ["src/a.js"]), ("d" * 40, DATA)), BOUND)
    assert run is True
    run, _ = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, ["data.json", "tests/smoke_app.py"])), BOUND)
    assert run is True                                                                        # 데이터와 함께 바뀐 검사 코드
    # 데이터 파일로 이름을 바꾼 것은 코드예요
    renamed = [{"filename": "data.json", "previous_filename": "src/evil.js", "status": "renamed"}]
    run, why = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, renamed)), BOUND)
    assert run is True and "src/evil.js → data.json" in why


@pytest.mark.parametrize("net, head", [
    (window(("d" * 40, DATA), status="diverged"), RUN),
    (window(("d" * 40, DATA), status="behind"), RUN),
    (Net(compare={"status": "ahead", "total_commits": 300, "commits": [{"sha": "d" * 40}]}, commits={"d" * 40: DATA}), RUN),
    (window(*[(f"{i:040x}", DATA) for i in range(DC.MAX_COMMITS + 1)]), RUN),
    (window(("d" * 40, [])), RUN),                                                            # 바뀐 파일 목록이 비었음
    (window(("d" * 40, [f"f{i}" for i in range(300)])), RUN),                                 # 목록이 잘렸을 수 있음
    (Net(compare=None), RUN),                                                                 # 이상한 응답
    (Net(fail=lambda m, p: True), RUN),                                                       # GitHub 장애
    (Net(), ""), (Net(), "abc"),                                                              # 데이터 실행의 커밋을 모름
])
def test_data_deploys_run_the_checks_when_it_cannot_be_proven(net, head):
    run, why = DC.need_checks("workflow_run", head, HEAD, net, BOUND)
    assert run is True, why


def site_with_data(tmp_path, body=b'{"pxDate": "2026-11-11"}'):
    site = tmp_path / "_site"
    site.mkdir(exist_ok=True)
    for f in DC.DATA_FILES:
        (site / f).write_bytes(body + f.encode())
    return site


def test_data_binding_needs_the_bots_commit_from_that_run_with_the_same_four_files(tmp_path):
    site = site_with_data(tmp_path)
    blobs = {f: DC.git_blob(str(site / f)) for f in DC.DATA_FILES}
    info = {"sha": "d" * 40, "date": "2026-11-11T22:00:30Z", "committer": "baepsae-bot", "blobs": dict(blobs)}
    started, updated = "2026-11-11T21:40:11Z", "2026-11-11T22:01:08Z"
    ok, why = DC.data_bound(info, str(site), started, updated)
    assert ok, why
    assert not DC.data_bound({**info, "committer": "Claude"}, str(site), started, updated)[0]          # 손으로 되돌린 data
    assert not DC.data_bound({**info, "date": "2026-11-12T22:00:00Z"}, str(site), started, updated)[0]  # 그 뒤의 다른 실행
    assert not DC.data_bound({**info, "date": "2026-11-11T21:00:00Z"}, str(site), started, updated)[0]  # 그 전의 것 (바뀐 것 없던 날)
    assert not DC.data_bound(info, str(site), "", updated)[0]
    assert not DC.data_bound({**info, "blobs": {**blobs, "macro.json": "0" * 40}}, str(site), started, updated)[0]
    (site / "corp.json").write_bytes(b"{}")
    assert not DC.data_bound(info, str(site), started, updated)[0]                                    # 올릴 폴더의 파일이 다름
    # git 이 매기는 이름과 같아요
    p = tmp_path / "x.json"
    p.write_bytes(b'{"a": 1}\n')
    assert DC.git_blob(str(p)) == subprocess.run(["git", "hash-object", str(p)], capture_output=True, text=True).stdout.strip()


def git_(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "baepsae-bot", "GIT_AUTHOR_EMAIL": "a@b",
                               "GIT_COMMITTER_NAME": "baepsae-bot", "GIT_COMMITTER_EMAIL": "a@b"}).stdout.strip()


def test_data_tip_info_reads_the_data_commit_the_deploy_fetched(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    git_(repo, "init", "-q")
    for f in DC.DATA_FILES:
        (repo / f).write_text(f)
    git_(repo, "add", "-A")
    git_(repo, "commit", "-q", "-m", "데이터 갱신")
    sha = git_(repo, "rev-parse", "HEAD")
    git_(repo, "update-ref", DC.DATA_REF, sha)
    info = DC.data_tip_info(str(repo))
    assert info["sha"] == sha and info["committer"] == "baepsae-bot" and set(info["blobs"]) == set(DC.DATA_FILES)
    assert info["blobs"]["data.json"] == git_(repo, "rev-parse", f"{sha}:data.json")


def test_need_file_and_output_drive_the_setup_steps_and_the_check(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert DC.cmd_skip() == 1                                                                 # 파일이 없으면 준비해요 (검사해요)
    monkeypatch.setattr(DC, "head_sha", lambda cwd=None: HEAD)
    monkeypatch.setattr(DC, "data_tip_info", lambda: {})
    monkeypatch.setattr(DC, "data_bound", lambda info, site, a, b: (True, "같은 데이터"))
    monkeypatch.setenv("EVENT", "workflow_run")
    monkeypatch.setenv("RUN_HEAD", RUN)
    assert DC.cmd_need("_site", net=window(("d" * 40, DATA))) == 0
    assert json.loads((tmp_path / DC.NEED_FILE).read_text())["run"] is False and out.read_text() == "run=no\n"
    assert DC.cmd_skip() == 0 and DC.read_need(str(tmp_path))[0] is False
    monkeypatch.setenv("EVENT", "push")
    assert DC.cmd_need("_site", net=Net()) == 0 and DC.cmd_skip() == 1 and out.read_text().splitlines()[-1] == "run=yes"
    for bad in ("", "{", '{"run": "no"}', '{"run": null}', "[]"):
        (tmp_path / DC.NEED_FILE).write_text(bad)
        assert DC.cmd_skip() == 1 and DC.read_need(str(tmp_path))[0] is True, bad          # 읽지 못하면 검사해요


# ── 지금 사이트의 코드 ──
def page(tag):
    meta = f'\n<meta name="baepsae-build" content="{tag}">' if tag else ""
    return f'<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">{meta}\n</head><body></body></html>'.encode()


def test_live_commit_is_the_build_stamp_on_every_page_the_site_serves():
    net = Net(pages={p: (200, page(LIVE)) for p in W.PAGES})
    sha, served = DC.find_live(net, now=1)
    assert sha == LIVE and set(served) == set(W.PAGES) and served["app.html"] == page(LIVE)
    bad = [{**{p: (200, page(LIVE)) for p in W.PAGES}, "app.html": (404, b"")},
           {**{p: (200, page(LIVE)) for p in W.PAGES}, "baepsae.html": (200, page(None))},
           {**{p: (200, page(LIVE)) for p in W.PAGES}, "styleguide.html": (200, page(HEAD))},
           {**{p: (200, page(LIVE)) for p in W.PAGES}, "app.html": (200, page("main"))},
           {p: (200, page(LIVE)) for p in W.PAGES if p != "app.html"}]                      # 받지 못함
    for pages in bad:
        with pytest.raises(DC.Unknown):
            DC.find_live(Net(pages=pages), now=1)
    assert W.PAGES == ("baepsae.html", "app.html", "styleguide.html")                        # 감시와 같은 페이지 · 같은 표시


def test_live_code_is_built_apart_without_install_scripts_and_must_match_the_served_pages_byte_for_byte(tmp_path, monkeypatch):
    calls = []
    repo = str(tmp_path / "repo")

    def fake_step(what, cmd, cwd, env=None, timeout=600):
        calls.append((cmd, cwd, (env or {}).get("BAEPSAE_BUILD")))
        if cmd[0] == "bash" and cmd[1] == "build-styleguide.sh":                              # 빌드가 끝나면 페이지가 생겨요
            for p in W.PAGES:
                (tmp_path / DC.LIVE_DIR / p).write_bytes(page(LIVE))
    monkeypatch.setattr(DC, "_step", fake_step)
    monkeypatch.setattr(DC, "get_commit", lambda sha, tmp: repo)
    monkeypatch.setattr(DC, "same_code", lambda r, sha: r == repo and sha == LIVE)
    served = {p: page(LIVE) for p in W.PAGES}
    got = DC.prepare_live(LIVE, served, str(tmp_path))
    d = str(tmp_path / DC.LIVE_DIR)
    assert got == {"dir": d, "same_code": True} and d != ROOT
    cmds = [c[0] for c in calls]
    assert cmds[0][:4] == ["git", "-C", repo, "archive"] and cmds[0][-1] == LIVE              # 그 커밋을 가진 저장소에서 꺼내요
    assert cmds[1][:2] == ["tar", "-x"] and cmds[1][-1] == d
    assert cmds[2] == ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"] and calls[2][1] == d
    assert [c[0] for c in calls[3:]] == [["bash", s] for s in DC.LIVE_BUILD] and {c[1] for c in calls[3:]} == {d}
    assert {c[2] for c in calls[3:]} == {LIVE}                                               # 사이트와 같은 빌드 표시로
    with pytest.raises(DC.Unknown, match="app.html"):                                         # 길이가 같아도 한 글자라도 다르면
        DC.prepare_live(LIVE, {**served, "app.html": page(LIVE).replace(b"ko", b"en")}, str(tmp_path))
    with pytest.raises(DC.Unknown, match="baepsae.html"):
        DC.prepare_live(LIVE, {**served, "baepsae.html": page(LIVE) + b" "}, str(tmp_path))


def make_repo(path, files):  # noqa: D401
    path.mkdir()
    git_(path, "init", "-q", "-b", "main")
    for k, v in files.items():
        p = path / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v)
    git_(path, "add", "-A")
    git_(path, "commit", "-q", "-m", "one")
    return git_(path, "rev-parse", "HEAD")


def test_live_commit_is_fetched_into_a_throwaway_repo_and_never_into_the_checkout(tmp_path, monkeypatch):
    """저장소(ROOT)에 없는 커밋은 RUNNER_TEMP 의 빈 저장소에만 받아요. ROOT 의 기록은 그대로 (얕게 잘리지 않아요)."""
    origin = tmp_path / "origin"
    make_repo(origin, {"app.html": "1", "data.json": "{}", "package-lock.json": "{}"})
    git_(origin, "config", "uploadpack.allowReachableSHA1InWant", "true")
    root = tmp_path / "root"
    git_(tmp_path, "clone", "-q", f"file://{origin}", str(root))                               # 기록이 다 있는 clone
    for i in range(2, 4):
        (origin / "app.html").write_text(str(i))
        git_(origin, "commit", "-q", "-am", f"c{i}")
    new = git_(origin, "rev-parse", "HEAD")                                                   # root 에는 없는 커밋
    before = git_(root, "rev-list", "--count", "HEAD")
    monkeypatch.setattr(DC, "ROOT", str(root))
    rt = tmp_path / "rt"
    rt.mkdir()
    got = DC.get_commit(new, str(rt))
    assert got == str(rt / DC.LIVE_REPO) and DC.has_commit(new, got)
    assert not DC.has_commit(new, str(root)) and git_(root, "rev-list", "--count", "HEAD") == before
    assert not (root / ".git" / "shallow").exists() and git_(root, "rev-parse", "--is-shallow-repository") == "false"
    old = git_(root, "rev-parse", "HEAD")
    assert DC.get_commit(old, str(rt)) == str(root)                                           # 이미 있으면 받지 않고 ROOT 에서 읽어요
    # 같은 코드: 데이터 네 파일 말고는 같은지
    assert DC.same_code(str(root), old, head=old)
    (root / "data.json").write_text('{"x": 1}')
    git_(root, "commit", "-q", "-am", "데이터")
    assert DC.same_code(str(root), old)                                                       # 데이터만 바뀐 커밋 = 같은 코드
    assert not DC.same_code(got, new)                                                         # app.html 이 다름
    # 데이터 네 파일(맨 위의 그 이름) 말고는 무엇이 달라도 다른 코드: 다른 .json · 더한 파일 · 뺀 파일 · 시험 데이터의 data.json
    base = git_(root, "rev-parse", "HEAD")
    for change in (lambda: (root / "package-lock.json").write_text('{"v": 2}'),
                   lambda: (root / "new.js").write_text("x"),
                   lambda: (root / "app.html").unlink(),
                   lambda: ((root / "tests" / "fixtures" / "v2").mkdir(parents=True, exist_ok=True),
                            (root / "tests" / "fixtures" / "v2" / "data.json").write_text("{}"))):
        git_(root, "reset", "-q", "--hard", base)
        git_(root, "clean", "-qfd")
        change()
        git_(root, "add", "-A")
        git_(root, "commit", "-q", "-m", "바꿈")
        assert not DC.same_code(str(root), base), change
    git_(root, "reset", "-q", "--hard", base)


def test_a_failing_live_step_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(DC, "has_commit", lambda sha, repo=None: False)
    monkeypatch.setattr(DC.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 128, "", "fatal: not our ref"))
    with pytest.raises(DC.Unknown):
        DC.prepare_live(LIVE, {}, str(tmp_path))


# ── 검사 → 결정 → 영수증 (브라우저 없이, 가짜 검사로) ──
def make_site(tmp_path):
    site = tmp_path / "_site"
    site.mkdir()
    for p in DC.SAME_PAGES:
        shutil.copyfile(os.path.join(ROOT, p), site / p)
    for f in DC.DATA_FILES:
        (site / f).write_text('{"pxDate": "2026-11-11"}' if f == "data.json" else "{}")
    (site / "logos").mkdir()
    (site / "logos" / "index.json").write_text("{}")
    return site


def orchestrate(tmp_path, monkeypatch, new, live=None, find=None, need=True, touch=None, same=False, again=None, stale=False):
    """new / live / again: {검사: (outcome, [실패 줄])} — 없으면 통과."""
    rt = tmp_path / "rt"
    rt.mkdir(exist_ok=True)
    monkeypatch.setenv("RUNNER_TEMP", str(rt))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(rt / "summary.md"))
    monkeypatch.setattr(DC, "head_sha", lambda cwd=None: HEAD)
    if need is not None:
        (rt / DC.NEED_FILE).write_text(json.dumps({"run": need, "why": "시험"}))
    if stale:
        (rt / DC.RECEIPT_FILE).write_text("old\n")
        (rt / DC.DECISION_FILE).write_text('{"result": "pass"}')
    site = tmp_path / "_site" if (tmp_path / "_site").exists() else make_site(tmp_path)
    ran = []

    def as_res(spec):
        o, fails = spec if spec else (DC.PASS, [])
        return {"outcome": o, "detail": "x / y 통과", "fails": None if o == DC.CRASH else list(fails), "raw": [], "unseen": []}

    def run(name, root, data, live_=False):
        kind = "live" if live_ else ("again" if any(r[0] == name and r[1] == "new" for r in ran) else "new")
        ran.append((name, kind, root, data))
        if touch and name == touch:
            (site / "extra.txt").write_text("x")
        table = {"new": new, "live": live or {}, "again": again or {}}[kind]
        return as_res(table.get(name))

    def fake_find(net):
        if find:
            raise find
        return LIVE, {"app.html": b"x"}
    rc = DC.cmd_check(str(site), net=Net(), run=lambda n, r, d, live=False: run(n, r, d, live), find=fake_find,
                      prepare=lambda sha, served, tmp: {"dir": str(tmp_path / "live"), "same_code": same})
    dec = json.loads((rt / DC.DECISION_FILE).read_text()) if (rt / DC.DECISION_FILE).exists() else None
    return rc, dec, (rt / DC.RECEIPT_FILE), ran, site


F = DC.FAIL


def test_all_three_pass_writes_the_receipt_and_never_looks_at_the_live_code(tmp_path, monkeypatch):
    rc, dec, rec, ran, site = orchestrate(tmp_path, monkeypatch, new={})
    assert rc == 0 and dec["result"] == "pass" and rec.exists()
    assert ran == [(t, "new", ROOT, str(site)) for t in DC.CHECKS]                              # 셋 모두 · 이 순서로 · 새 코드 = 저장소 · 올릴 폴더
    assert rec.read_text() == DC.file_tree(str(site))


def test_new_code_failing_a_line_the_live_code_passes_blocks(tmp_path, monkeypatch, capsys):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_launch": (F, ["[320px] 새로 깨진 줄"])},
                                       live={"smoke_launch": (DC.PASS, [])}, stale=True)
    out = capsys.readouterr().out
    assert rc == 1 and dec["result"] == "block" and not rec.exists()                           # 지난 영수증도 지워요
    assert [r[:3] for r in ran] == [(t, "new", ROOT) for t in DC.CHECKS] + [("smoke_launch", "live", str(tmp_path / "live"))]
    err = [ln for ln in out.splitlines() if ln.startswith("::error title=배포 막음 · 배포 전 화면 검사::")]
    assert len(err) == 1 and "smoke_launch" in err[0] and "사이트는 그대로" in err[0] and "[320px] 새로 깨진 줄" in err[0]
    summ = (tmp_path / "rt" / "summary.md").read_text()
    assert "### 뱁새 배포 전 화면 검사 — 막음" in summ and "새 코드만 실패: `[320px] 새로 깨진 줄`" in summ


def test_a_new_failing_line_hidden_behind_an_old_one_still_blocks(tmp_path, monkeypatch):
    rc, dec, rec, _, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["옛 줄", "새 줄"])},
                                     live={"smoke_app": (F, ["옛 줄"])})
    assert rc == 1 and dec["result"] == "block" and not rec.exists()
    row = next(r for r in dec["rows"] if r["check"] == "smoke_app")
    assert row["new_only"] == ["새 줄"] and row["both"] == ["옛 줄"]


def test_live_code_failing_the_same_lines_deploys_and_warns_without_red_lines(tmp_path, monkeypatch, capsys):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["옛 줄"])}, live={"smoke_app": (F, ["옛 줄", "또"])})
    out = capsys.readouterr().out
    assert rc == 0 and dec["result"] == "alert" and rec.exists() and dec["live"] == LIVE
    assert any(ln.startswith("::warning title=배포 · 지금 사이트 코드도 실패::smoke_app") for ln in out.splitlines())
    assert "::error" not in out                                                               # 올리는 실행에 빨간 줄이 없어요


def test_one_check_new_only_blocks_even_if_another_fails_on_both(tmp_path, monkeypatch):
    rc, dec, rec, _, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["z"]), "real_data_check": (F, ["r"])},
                                     live={"smoke_app": (F, ["z"]), "real_data_check": (DC.PASS, [])})
    assert rc == 1 and dec["result"] == "block" and not rec.exists()


def test_same_code_reruns_once_and_never_blocks_itself(tmp_path, monkeypatch):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["흔들린 줄"])}, live={}, same=True,
                                       again={"smoke_app": (DC.PASS, [])})
    assert rc == 0 and dec["result"] == "pass" and rec.exists() and dec["same_code"] is True
    assert [r[1] for r in ran].count("again") == 1 and ran[-1][:3] == ("smoke_app", "again", ROOT)
    for d in ("rt", "_site"):
        shutil.rmtree(tmp_path / d)
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["시계 줄"])}, live={}, same=True,
                                       again={"smoke_app": (F, ["시계 줄"])})
    assert rc == 0 and dec["result"] == "alert" and rec.exists()
    for d in ("rt", "_site"):
        shutil.rmtree(tmp_path / d)
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["새 줄"])}, live={}, same=False)
    assert rc == 1 and "again" not in [r[1] for r in ran]                                    # 다른 코드면 다시 돌리지 않아요


@pytest.mark.parametrize("err", [DC.Unknown("사이트의 app.html 에 빌드 표시(baepsae-build)가 없어요"), KeyError("bug")])
def test_unknown_live_code_blocks_loudly(tmp_path, monkeypatch, capsys, err):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["a"])}, find=err)
    out = capsys.readouterr().out
    assert rc == 1 and dec["result"] == "block" and dec["unknown"] and not rec.exists()
    assert "지금 사이트의 코드를 알 수 없어요" in out and "::error title=배포 막음" in out
    assert not [r for r in ran if r[1] == "live"]


def test_skipped_data_deploy_runs_nothing_and_still_writes_the_receipt(tmp_path, monkeypatch):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["a"])}, need=False)
    assert rc == 0 and dec["result"] == "skipped" and rec.exists() and ran == []


def test_missing_need_file_runs_the_checks(tmp_path, monkeypatch):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={}, need=None)
    assert rc == 0 and dec["result"] == "pass" and len(ran) == 3


def test_checks_that_change_the_folder_stop_the_deploy(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="올릴 폴더가 바뀌었어요"):
        orchestrate(tmp_path, monkeypatch, new={}, touch="smoke_launch")
    assert not (tmp_path / "rt" / DC.RECEIPT_FILE).exists()


def test_pages_checked_must_be_the_pages_uploaded(tmp_path, monkeypatch):
    site = make_site(tmp_path)
    (site / "app.html").write_bytes(b"<html>other</html>")
    with pytest.raises(SystemExit, match="app.html"):
        orchestrate(tmp_path, monkeypatch, new={})
    assert not (tmp_path / "rt" / DC.RECEIPT_FILE).exists()


def test_a_hung_script_is_stopped_at_its_own_limit_and_counts_as_stopped(tmp_path, monkeypatch):
    """한 스크립트가 멈춰 버리면 단계 한도까지 기다리지 않고 그 스크립트만 멈춰요 → '결과 줄 전에 멈춤' (새 코드면 실패 → 비교 · 지금 코드면 알 수 없음)."""
    import time as _t
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "slow.py").write_text("import time, sys\nprint('시작', flush=True)\ntime.sleep(60)\nprint('1 / 1 통과')\n")
    monkeypatch.setattr(DC, "SCRIPT_TIMEOUT", 1)
    t0 = _t.time()
    r = DC.run_check("slow", str(tmp_path), "/data")
    assert _t.time() - t0 < 30 and r["outcome"] == DC.CRASH and "시간 한도" in r["detail"] and r["fails"] is None
    assert DC.SCRIPT_TIMEOUT == 1 and 0 < DC.SCRIPT_TIMEOUT * 3 < 45 * 60
    monkeypatch.undo()
    assert DC.SCRIPT_TIMEOUT == 20 * 60                                                       # 세 스크립트 + 비교가 단계 한도(45분) 안에서 결정을 남기게


def test_same_code_alert_says_so_and_names_the_lines(tmp_path, monkeypatch, capsys):
    """리뷰 2회차 S1: 같은 코드에서 새 실행이 두 번 실패하고 지금 코드 실행은 통과했으면 '지금 사이트 코드도 실패'라고 하지 않아요."""
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["[늦음 시각] 자정 직전"])}, live={}, same=True,
                                       again={"smoke_app": (F, ["[늦음 시각] 자정 직전"])})
    out = capsys.readouterr().out
    assert rc == 0 and dec["result"] == "alert"
    warn = [ln for ln in out.splitlines() if ln.startswith("::warning title=배포 · ")]
    assert len(warn) == 1 and warn[0].startswith("::warning title=배포 · 같은 코드인데 두 번 실패::smoke_app")
    assert "[늦음 시각] 자정 직전" in warn[0] and "흔들리거나 시계" in warn[0] and "같은 줄에 실패" not in warn[0]
    summ = (tmp_path / "rt" / "summary.md").read_text()
    assert "— 같은 코드인데 두 번 실패 · 올리고 알려요" in summ and "올림 (같은 코드 · 두 번 실패)" in summ and "지금 코드도 실패" not in summ
    net = Net()
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    assert DC.cmd_report(str(tmp_path / "_site"), net=net) == 0
    first = net.issues[-1]["body"].splitlines()[0]
    assert first.startswith(DC.MARK) and "같은 코드인데 새 실행이 두 번 실패했어요 ([늦음 시각] 자정 직전)" in first
    assert "도 같은 데이터에서 같은 줄에 실패" not in first and "흔들리거나 시계" in first
    assert "(같은 코드 · 두 번 실패) [늦음 시각] 자정 직전" in net.issues[-1]["body"]


def test_a_block_still_shows_the_lines_the_live_code_fails_too(tmp_path, monkeypatch, capsys):
    """리뷰 2회차 S2: 막는 실행에서도 지금 사이트 코드도 실패하는 줄은 경고로 보여요 (J6: 지금 코드도 실패하면 그때마다 알려요)."""
    rc, dec, rec, _, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": (F, ["옛 줄", "새 줄"]), "real_data_check": (F, ["r"])},
                                     live={"smoke_app": (F, ["옛 줄"]), "real_data_check": (F, ["r"])})
    out = capsys.readouterr().out
    assert rc == 1 and dec["result"] == "block"
    assert "::warning title=배포 · 지금 사이트 코드도 실패하는 줄::smoke_app: 두 코드 모두 실패: 옛 줄" in out
    assert any(ln.startswith("::warning title=배포 · 지금 사이트 코드도 실패::real_data_check") for ln in out.splitlines())
    assert any(ln.startswith("::error title=배포 막음 · 배포 전 화면 검사::smoke_app") and "새 줄" in ln for ln in out.splitlines())
    summ = (tmp_path / "rt" / "summary.md").read_text()
    assert "두 코드 모두 실패: `옛 줄`" in summ and "새 코드만 실패: `새 줄`" in summ


# ── 결과 단계: 영수증 · 경보 이슈 ──
def report(tmp_path, monkeypatch, dec, net, receipt=True, change=None):
    rt = tmp_path / "rt"
    rt.mkdir(exist_ok=True)
    monkeypatch.setenv("RUNNER_TEMP", str(rt))
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    site = tmp_path / "_site" if (tmp_path / "_site").exists() else make_site(tmp_path)
    for f in (DC.DECISION_FILE, DC.RECEIPT_FILE):
        if (rt / f).exists():
            (rt / f).unlink()
    if dec is not None:
        (rt / DC.DECISION_FILE).write_text(json.dumps(dec, ensure_ascii=False))
    if receipt:
        (rt / DC.RECEIPT_FILE).write_text(DC.file_tree(str(site)))
    if change:
        (site / change).write_text("changed")
    return DC.cmd_report(str(site), net=net)


def decision(result, rows=None):
    return {"result": result, "head": HEAD, "live": LIVE, "px": "2026-11-11", "why": "시험",
            "rows": rows if rows is not None else [DC._row("smoke_app", "alert", "새 코드 141 / 145 통과 · 지금 사이트 코드도 142 / 145 통과",
                                                           (), ["[정상] 깨진 줄"])],
            "checks": {}}


@pytest.mark.parametrize("dec, receipt, change, match", [
    (None, True, None, "결과가 없어요"),
    (decision("block"), True, None, "올려도 돼요"),
    ({"result": "maybe"}, True, None, "올려도 돼요"),
    (decision("pass"), False, None, "영수증이 없어요"),
    (decision("pass"), True, "data.json", "검사한 것과 달라요"),
    (decision("pass"), True, "new-file.js", "검사한 것과 달라요"),                         # 더해진 파일도 잡아요
    (decision("skipped"), False, None, "영수증이 없어요"),                                   # 건너뛴 데이터 배포도 영수증으로
    (decision("skipped"), True, "data.json", "검사한 것과 달라요"),
    (decision("alert"), True, "corp.json", "검사한 것과 달라요"),
])
def test_report_refuses_to_let_the_upload_go_without_a_matching_receipt(tmp_path, monkeypatch, dec, receipt, change, match):
    with pytest.raises(SystemExit, match=match):
        report(tmp_path, monkeypatch, dec, Net(), receipt=receipt, change=change)


def test_alert_opens_one_data_alert_issue_whose_first_line_says_the_case(tmp_path, monkeypatch):
    net = Net()
    assert report(tmp_path, monkeypatch, decision("alert"), net) == 0
    made = [c for c in net.calls if c[0] == "POST" and c[1].endswith("/issues")]
    assert len(made) == 1 and made[0][2]["title"] == W.ISSUE_TITLE and made[0][2]["labels"] == [W.LABEL, DC.LABEL]
    body = net.issues[-1]["body"]                                                              # PATCH 로 이슈 번호를 넣은 본문
    first = body.splitlines()[0]
    assert first.startswith(DC.MARK) and "올리고 있어요" in first and "올렸" not in first     # 아직 올라가지 않은 배포를 올렸다고 하지 않아요
    assert W.MENTION in body and "/actions/runs/77" in body and W.PASTE.format(n=net.issues[-1]["number"]) in body
    assert body.count("[정상] 깨진 줄") == 1 and "smoke_app" in body                          # 실패한 줄은 한 번씩
    assert ("POST", f"/repos/{W.REPO}/labels") in [c[:2] for c in net.calls]                   # deploy-check 표시를 만들어요 (있으면 그대로)
    assert not [c for c in net.calls if c[0] == "DELETE"]                                      # 알린 배포는 표시를 풀지 않아요


def test_alert_issue_shows_each_failing_line_once_with_its_message(tmp_path, monkeypatch):
    dec = decision("alert", rows=[DC._row("smoke_app", "alert", "새 코드 143 / 145 통과 · 지금 사이트 코드도 143 / 145 통과", (),
                                          ["[정상] 첫 화면이 열림", "[EN] 성적표"])])
    dec["checks"] = {"smoke_app": {"new": {"raw": [["[정상] 첫 화면이 열림", "[정상] 첫 화면이 열림        안 보여요"],
                                                    ["[EN] 성적표", "[EN] 성적표                 글자가 달라요"]]}}}
    net = Net()
    assert report(tmp_path, monkeypatch, dec, net) == 0
    body = net.issues[-1]["body"]
    assert body.count("[정상] 첫 화면이 열림") == 1 and "안 보여요" in body and body.count("[EN] 성적표") == 1
    assert "(새 코드만)" not in body


def test_alert_labels_the_open_issue_before_commenting_instead_of_opening_a_second_one(tmp_path, monkeypatch):
    net = Net(issues=[{"number": 9, "labels": [{"name": W.LABEL}]}])
    assert report(tmp_path, monkeypatch, decision("alert"), net) == 0
    assert not [c for c in net.calls if c[0] == "POST" and c[1].endswith("/issues")]
    on9 = [c for c in net.calls if "/issues/9/" in c[1]]
    assert [c[1].rsplit("/", 1)[-1] for c in on9] == ["labels", "comments"] and on9[0][2] == {"labels": [DC.LABEL]}
    assert on9[1][2]["body"].startswith(DC.MARK) and W.MENTION in on9[1][2]["body"]
    assert not [c for c in net.calls if c[0] == "DELETE"]


def test_alert_that_cannot_reach_jack_stops_the_upload(tmp_path, monkeypatch):
    net = Net(fail=lambda m, p: m == "POST" and p.endswith("/issues"))
    with pytest.raises(SystemExit, match="경보 이슈를 열지 못했어요"):
        report(tmp_path, monkeypatch, decision("alert"), net)
    net = Net(fail=lambda m, p: m == "PATCH")                                                  # 열렸는데 번호만 못 넣음: 그래도 알렸어요
    assert report(tmp_path, monkeypatch, decision("alert"), net) == 0


@pytest.mark.parametrize("result", ["pass", "skipped"])
def test_a_clean_deploy_lifts_the_deploy_check_mark_and_leaves_closing_to_the_watchdog(tmp_path, monkeypatch, result):
    net = Net(issues=[{"number": 9, "labels": [{"name": W.LABEL}, {"name": DC.LABEL}]}, {"number": 12, "labels": [{"name": W.LABEL}]}])
    assert report(tmp_path, monkeypatch, decision(result, rows=[]), net) == 0
    c9 = [c for c in net.calls if c[1].endswith("/issues/9/comments")]
    assert len(c9) == 1 and c9[0][2]["body"].startswith(DC.OK_MARK)
    assert ("DELETE", f"/repos/{W.REPO}/issues/9/labels/{DC.LABEL}", None) in net.calls
    assert not [c for c in net.calls if "/issues/12" in c[1]]                                  # 표시가 없는 경보는 건드리지 않아요
    assert not [c for c in net.calls if c[0] == "PATCH"]                                       # 닫는 것은 감시가 해요


def test_a_clean_deploy_is_not_stopped_by_github_trouble(tmp_path, monkeypatch, capsys):
    net = Net(issues=[{"number": 9, "labels": [{"name": DC.LABEL}]}], fail=lambda m, p: True)
    assert report(tmp_path, monkeypatch, decision("pass", rows=[]), net) == 0
    assert "::warning title=배포 전 화면 검사 · 경보 표시를 풀지 못함::" in capsys.readouterr().out


# ── 명령줄 그대로 (deploy.yml 이 부르는 대로) ──
def cli(args, rt, env=None):
    e = {k: v for k, v in os.environ.items() if k not in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ACTIONS")}
    e.update({"RUNNER_TEMP": str(rt), **(env or {})})
    return subprocess.run([sys.executable, TOOL, *args], cwd=ROOT, env=e, capture_output=True, text=True, timeout=300)


def test_cli_skip_exits_0_only_for_a_deploy_that_skips(tmp_path):
    assert cli(["skip"], tmp_path).returncode == 1
    (tmp_path / DC.NEED_FILE).write_text('{"run": false, "why": "시험"}')
    assert cli(["skip"], tmp_path).returncode == 0
    (tmp_path / DC.NEED_FILE).write_text('{"run": true, "why": "시험"}')
    assert cli(["skip"], tmp_path).returncode == 1


def test_cli_check_exits_1_on_a_block_and_writes_no_receipt(tmp_path):
    """진짜 세 스크립트를 진짜 명령줄로: 빈 데이터 → 새 코드 실패 · 지금 사이트(가짜 주소: 빌드 표시 없는 페이지)를 알 수 없음 → 막음."""
    pytest.importorskip("playwright.sync_api")
    pages = tmp_path / "pages"
    pages.mkdir()
    for p in W.PAGES:
        (pages / p).write_bytes(page(None))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(pages)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        site = tmp_path / "_site"
        site.mkdir()
        for p in DC.SAME_PAGES:
            shutil.copyfile(os.path.join(ROOT, p), site / p)
        for f in DC.DATA_FILES:
            (site / f).write_text("{}")
        rt = tmp_path / "rt"
        rt.mkdir()
        (rt / DC.NEED_FILE).write_text('{"run": true, "why": "시험"}')
        (rt / DC.RECEIPT_FILE).write_text("old\n")                                            # 지난 영수증은 지워져야 해요
        r = cli(["check", "--site", str(site)], rt, {"BAEPSAE_SITE": f"http://127.0.0.1:{srv.server_address[1]}/"})
    finally:
        srv.shutdown()
    assert r.returncode == 1, r.stdout[-2000:] + r.stderr[-2000:]
    assert not (rt / DC.RECEIPT_FILE).exists()
    dec = json.loads((rt / DC.DECISION_FILE).read_text())
    assert dec["result"] == "block" and "빌드 표시" in dec["unknown"]
    assert dec["checks"]["smoke_launch"]["new"]["fails"][0].startswith("[데이터] 2.0 이 쓰는 항목이 빠진 데이터")   # 일부러 멈춘 것 = 실패 줄
    assert "::error title=배포 막음 · 배포 전 화면 검사::" in r.stdout
    r = cli(["report", "--site", str(site)], rt)                                              # 막힌 결과로는 올리지 않아요
    assert r.returncode != 0 and "올려도 돼요" in r.stdout + r.stderr


# ── 감시: deploy-check 표시가 붙은 경보는 '정상화됐어요'로 닫지 않아요 ──
def test_watchdog_leaves_a_deploy_check_alert_open(capsys):
    net = Net(issues=[{"number": 9, "labels": [{"name": W.LABEL}, {"name": W.DEPLOY_CHECK_LABEL}]},
                      {"number": 12, "labels": [{"name": W.LABEL}]}])
    closed = W.clear_alerts(net, {"px": "2026-11-11"}, W.dt.datetime(2026, 11, 12, tzinfo=W.dt.timezone.utc), "run")
    assert closed == [12]
    assert not [c for c in net.calls if "/issues/9" in c[1]]
    assert "#9 은 닫지 않아요" in capsys.readouterr().out
    assert DC.LABEL == W.DEPLOY_CHECK_LABEL == "deploy-check"


# ── 배포 workflow 의 다른 부분은 그대로 ──
def test_watchdog_still_follows_the_same_three_deploy_jobs():
    assert set(load("deploy.yml")["jobs"]) == {"decide", "build", "deploy"}
    assert load("deploy.yml")["jobs"]["decide"]["permissions"] == {"actions": "read", "pages": "read"}
