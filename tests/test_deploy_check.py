# -*- coding: utf-8 -*-
"""배포 전 화면 검사 (Jack J6, 2026-11-12): deploy.yml 이 코드가 바뀌는 배포를 올리기 전에 매일 실행의 세 검사를 올릴 데이터 그대로 돌려요.

- 자리: 올릴 폴더(_site) · 발행 관문(--live) 다음, 올리기(upload-pages-artifact) 바로 앞. build job 의 단계에는 조건(if)이 없어요.
- 코드 배포(push · workflow_dispatch)는 늘 검사해요. 데이터 실행 뒤의 배포(workflow_run)는 그 실행이 검사한 커밋에서 지금 main 까지
  데이터 네 파일만 바뀌었을 때만 건너뛰어요 (확인하지 못하면 검사해요).
- 결정 (검사마다): 새 코드만 실패 → 막음 · 지금 사이트 코드도 실패 → 올리고 알림 (data-alert 이슈 + deploy-check 표시) · 지금 코드를 알 수
  없음 → 막음. 검사가 끝까지 돌지 못한 것은 새 코드 쪽에서는 실패, 지금 코드 쪽에서는 '알 수 없음'.
- 브라우저 단계의 환경에는 비밀 값이 없어요 (매일 실행의 규칙과 같아요 · tests/test_screen_check.py). 올리기 · 배포 단계에 always() ·
  continue-on-error 가 없어요. 올리기 바로 전 단계가 통과 영수증과 올릴 폴더를 맞춰 봐요.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import deploy_check as DC  # noqa: E402
import watchdog as W  # noqa: E402

NEED = "배포 전 화면 검사가 필요한지 (코드가 바뀌는 배포만)"
TOOLS = "화면 검사 도구 설치 (requirements-dev.txt 그대로 · 검사하는 배포만)"
RESTORE = "브라우저 보관본 불러오기"
BROWSER = "브라우저 · 한글 글꼴 준비 (보관본 그대로 · 없을 때만 내려받기 · apt 없음 · 검사하는 배포만)"
CHECK = "배포 전 화면 검사 (올릴 데이터 그대로 · 새 코드, 실패하면 지금 사이트의 코드와 비교)"
REPORT = "배포 전 화면 검사 결과 (영수증 = 올릴 폴더 · 경보 이슈)"
SKIP_LINE = "if python3 tools/deploy_check.py skip; then exit 0; fi"
HEAD, LIVE, RUN = "a" * 40, "b" * 40, "c" * 40


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
    i_gate = next(i for i, x in enumerate(n) if x.startswith("발행 관문"))
    i_up = n.index("actions/upload-pages-artifact@v5")
    assert i_site < i_gate and i_up == len(st) - 1
    assert n[i_gate + 1:i_up] == [NEED, TOOLS, RESTORE, BROWSER, CHECK, REPORT]          # 관문 다음 · 올리기 바로 앞, 이 순서로
    assert st[i_site]["run"].split()[2] == "_site" and st[i_up]["with"]["path"] == "_site"  # 검사하는 폴더 = 올리는 폴더
    assert step(CHECK)["run"].strip() == "python3 tools/deploy_check.py check --site _site"
    assert step(REPORT)["run"].strip() == "python3 tools/deploy_check.py report --site _site"
    assert step(NEED)["run"].strip() == "python3 tools/deploy_check.py need"
    for s in st:                                                                              # 조건으로 건너뛰는 단계가 없어요
        assert "if" not in s and "continue-on-error" not in s, s.get("name") or s.get("uses")
    for name in (TOOLS, BROWSER):                                                             # 건너뛰기는 단계 안에서, 맨 앞 줄에서만
        lines = [ln.strip() for ln in step(name)["run"].strip().splitlines()]
        assert lines[0] == SKIP_LINE and step(name)["run"].count("deploy_check.py skip") == 1, name
    assert {k: step(k).get("timeout-minutes") for k in (NEED, TOOLS, RESTORE, BROWSER, CHECK, REPORT)} == {
        NEED: None, TOOLS: 10, RESTORE: None, BROWSER: 10, CHECK: 45, REPORT: 5}
    job = load("deploy.yml")["jobs"]["build"]
    assert job["timeout-minutes"] >= 10 + 10 + 45 + 5 + 5
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


def test_browser_steps_get_no_secret():
    """매일 실행의 규칙과 같아요: 세 검사와 그 준비 단계의 환경에는 비밀 값 · 토큰이 없어요. 토큰은 '필요한지'와 '결과' 단계에만."""
    wf = load("deploy.yml")
    for env in (wf.get("env") or {}, wf["jobs"]["build"].get("env") or {}):
        assert not env, env
    for name in (TOOLS, RESTORE, BROWSER, CHECK):
        s = step(name)
        assert "env" not in s, name
        assert not re.search(r"secrets\.|github\.token|GITHUB_TOKEN|DART_API_KEY|ECOS_API_KEY|HC_PING", json.dumps(s, ensure_ascii=False)), name
    assert step(NEED)["env"] == {"GITHUB_TOKEN": "${{ github.token }}", "EVENT": "${{ github.event_name }}",
                                 "RUN_HEAD": "${{ github.event.workflow_run.head_sha }}"}
    assert step(REPORT)["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    raw = open(os.path.join(WF, "deploy.yml"), encoding="utf-8").read()
    assert "secrets." not in raw                                                              # 배포는 비밀 값을 하나도 쓰지 않아요
    # 검사 단계는 받은 환경을 그대로 넘기지만, 그 단계의 환경에 토큰이 없어요 (job · workflow 의 env 도 없음 — 위)


def test_deploy_gets_the_browser_and_tools_the_same_way_as_the_daily_run():
    upd = load("update-data.yml")["jobs"]["update"]["steps"]
    daily_cache = next(s for s in upd if s.get("name") == "브라우저 보관본 불러오기")
    mine = step(RESTORE)
    assert mine["uses"] == "actions/cache/restore@v6" and set(mine["with"]) == {"path", "key"}   # restore-keys 없음
    assert mine["with"] == daily_cache["with"]                                                   # 같은 보관본 (판 숫자를 올리면 함께)
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


def test_each_check_runs_with_the_exact_command_and_no_extra_flags(monkeypatch, tmp_path, capsys):
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
    assert env["GITHUB_ACTIONS"] == "true"                                                     # 새 코드의 실패 알림은 이 배포의 결론이에요
    DC.run_check("smoke_app", "/live", "/data/_site", live=True)
    cmd, cwd, env = seen[-1]
    assert cwd == "/live" and "GITHUB_ACTIONS" not in env                                      # 비교용 실행은 알림을 남기지 않아요
    assert "::group::smoke_app · 새 코드" in capsys.readouterr().out


# ── 결과 줄 읽기 ──
@pytest.mark.parametrize("rc, lines, want", [
    (0, ["3 / 3 통과"], DC.PASS),
    (1, ["  FAIL  x", "2 / 3 통과"], DC.FAIL),
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


# ── 결정 ──
def res(o, d=None):
    return {"outcome": o, "detail": d or {DC.PASS: "3 / 3 통과", DC.FAIL: "2 / 3 통과", DC.CRASH: "끝까지 돌지 못했어요"}[o]}


ALL_PASS = {t: res(DC.PASS) for t in DC.CHECKS}


def with_(**kw):
    return {**ALL_PASS, **kw}


@pytest.mark.parametrize("new, live, unknown, want", [
    (ALL_PASS, None, None, "pass"),
    (with_(smoke_app=res(DC.FAIL)), {"smoke_app": res(DC.PASS)}, None, "block"),          # 새 코드만 실패 → 막음
    (with_(smoke_app=res(DC.FAIL)), {"smoke_app": res(DC.FAIL)}, None, "alert"),          # 지금 코드도 실패 → 올리고 알림
    (with_(smoke_app=res(DC.FAIL)), None, "빌드 표시 없음", "block"),                      # 지금 코드를 알 수 없음 → 막음
    (with_(smoke_app=res(DC.FAIL)), {}, None, "block"),                                    # 지금 코드로 돌리지 않은 검사
    (with_(smoke_app=res(DC.CRASH)), {"smoke_app": res(DC.FAIL)}, None, "alert"),         # 새 코드의 '끝까지 못 돎'도 실패예요
    (with_(smoke_app=res(DC.CRASH)), {"smoke_app": res(DC.PASS)}, None, "block"),
    (with_(smoke_app=res(DC.FAIL)), {"smoke_app": res(DC.CRASH)}, None, "block"),         # 지금 코드가 끝까지 못 돎 = 알 수 없음
    (with_(smoke_launch=res(DC.FAIL), smoke_app=res(DC.FAIL)),                              # 검사마다: B 는 둘 다 실패해도 A 가 새 코드만 실패면 막음
     {"smoke_launch": res(DC.PASS), "smoke_app": res(DC.FAIL)}, None, "block"),
    (with_(real_data_check=res(DC.FAIL), smoke_app=res(DC.FAIL)),
     {"real_data_check": res(DC.FAIL), "smoke_app": res(DC.FAIL)}, None, "alert"),
    ({"real_data_check": res(DC.PASS), "smoke_app": res(DC.PASS)}, {}, None, "block"),     # 새 코드에서 돌지 않은 검사는 실패
])
def test_decide_compares_check_by_check(new, live, unknown, want):
    got, rows = DC.decide(new, live, unknown)
    assert got == want, rows
    assert [r[0] for r in rows] == list(DC.CHECKS)


def test_decide_names_the_check_and_both_results():
    got, rows = DC.decide(with_(smoke_app=res(DC.FAIL, "141 / 145 통과")), {"smoke_app": res(DC.PASS, "145 / 145 통과")})
    assert got == "block"
    row = next(r for r in rows if r[0] == "smoke_app")
    assert row[1] == "block" and "141 / 145 통과" in row[2] and "145 / 145 통과" in row[2] and "새 코드만 실패" in row[2]


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
            return 200, {"files": [{"filename": f} for f in self.commits[p.rsplit("/", 1)[-1]]]}
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


def test_code_deploys_always_run_the_checks():
    for event in ("push", "workflow_dispatch", "", "schedule"):
        run, why = DC.need_checks(event, RUN, HEAD, Net())
        assert run is True, (event, why)
    assert DC.need_checks("push", HEAD, HEAD, Net())[0] is True                               # 머지는 같은 커밋이어도 검사해요


def test_data_deploys_skip_only_when_nothing_but_the_four_data_files_changed():
    # 실제 모양 (2026-11-12 아침): 매일 실행 43105073111 (head b519dfa) → data 커밋 403884a 하나 (데이터 네 파일) → Deploy 43108129970
    net = window(("d" * 40, DATA))
    run, why = DC.need_checks("workflow_run", RUN, HEAD, net)
    assert run is False and "데이터 네 파일만" in why, why
    assert [c[1].split("?")[0] for c in net.calls] == [f"/repos/{W.REPO}/compare/{RUN}...{HEAD}", f"/repos/{W.REPO}/commits/{'d' * 40}"]
    assert DC.need_checks("workflow_run", HEAD, HEAD, Net())[0] is False                      # 데이터 커밋이 없던 날 (같은 커밋)
    # 그 사이에 코드가 들어왔으면 (머지가 데이터 실행 도중에) 검사해요 — 그 코드로는 아무도 이 데이터를 검사하지 않았어요
    run, why = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, ["src/app.jsx", "app.html"]), ("d" * 40, DATA)))
    assert run is True and "app.html" in why and "src/app.jsx" in why
    # 바뀌었다가 되돌아온 코드도 커밋마다 보니까 잡아요
    run, _ = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, ["src/a.js"]), ("f" * 40, ["src/a.js"]), ("d" * 40, DATA)))
    assert run is True
    run, _ = DC.need_checks("workflow_run", RUN, HEAD, window(("e" * 40, ["data.json", "tests/smoke_app.py"])))
    assert run is True                                                                        # 데이터와 함께 바뀐 검사 코드


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
    run, why = DC.need_checks("workflow_run", head, HEAD, net)
    assert run is True, why


def test_need_file_drives_the_setup_steps_and_the_check(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    assert DC.cmd_skip() == 1                                                                 # 파일이 없으면 준비해요 (검사해요)
    monkeypatch.setattr(DC, "head_sha", lambda cwd=None: HEAD)
    monkeypatch.setenv("EVENT", "workflow_run")
    monkeypatch.setenv("RUN_HEAD", RUN)
    assert DC.cmd_need(net=window(("d" * 40, DATA))) == 0
    assert json.loads((tmp_path / DC.NEED_FILE).read_text()) ["run"] is False
    assert DC.cmd_skip() == 0 and DC.read_need(str(tmp_path))[0] is False
    monkeypatch.setenv("EVENT", "push")
    assert DC.cmd_need(net=Net()) == 0 and DC.cmd_skip() == 1
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


def test_live_code_is_built_apart_and_must_match_the_served_pages(tmp_path, monkeypatch):
    calls = []

    def fake_step(what, cmd, cwd, env=None, timeout=600):
        calls.append((cmd, cwd, (env or {}).get("BAEPSAE_BUILD")))
        if cmd[0] == "bash" and cmd[1] == "build-styleguide.sh":                              # 빌드가 끝나면 페이지가 생겨요
            for p in W.PAGES:
                (tmp_path / DC.LIVE_DIR / p).write_bytes(page(LIVE))
    monkeypatch.setattr(DC, "_step", fake_step)
    monkeypatch.setattr(DC, "has_commit", lambda sha: False)                                   # 배포의 checkout: 커밋 하나뿐
    served = {p: page(LIVE) for p in W.PAGES}
    d = DC.prepare_live(LIVE, served, str(tmp_path))
    assert d == str(tmp_path / DC.LIVE_DIR) and d != ROOT
    cmds = [c[0] for c in calls]
    assert cmds[0] == ["git", "fetch", "-q", "--depth=1", "--no-tags", "origin", LIVE]
    assert cmds[1][:3] == ["git", "archive", "--format=tar"] and cmds[1][-1] == LIVE
    assert cmds[2][:2] == ["tar", "-x"] and cmds[2][-1] == d
    assert cmds[3][:2] == ["npm", "ci"] and calls[3][1] == d
    assert [c[0] for c in calls[4:]] == [["bash", s] for s in DC.LIVE_BUILD] and {c[1] for c in calls[4:]} == {d}
    assert {c[2] for c in calls[4:]} == {LIVE}                                               # 사이트와 같은 빌드 표시로
    with pytest.raises(DC.Unknown, match="app.html"):                                         # 다시 빌드한 페이지가 사이트의 것과 다르면
        DC.prepare_live(LIVE, {**served, "app.html": page(LIVE) + b" "}, str(tmp_path))
    calls.clear()                                                                             # 이미 있는 커밋은 받지 않아요: 얕은 받기는
    monkeypatch.setattr(DC, "has_commit", lambda sha: True)                                   # 있는 기록을 그 커밋에서 잘라 버려요
    DC.prepare_live(LIVE, served, str(tmp_path))
    assert [c[0][:2] for c in calls][:2] == [["git", "archive"], ["tar", "-x"]] and not [c for c in calls if "fetch" in c[0]]
    monkeypatch.undo()
    assert DC.has_commit(subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    assert not DC.has_commit("0" * 40) and not DC.has_commit("1234567890" * 4)


def test_a_failing_live_step_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(DC.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 128, "", "fatal: not our ref"))
    monkeypatch.setattr(DC, "has_commit", lambda sha: False)
    with pytest.raises(DC.Unknown, match="git fetch"):
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


def orchestrate(tmp_path, monkeypatch, new, live=None, find=None, need=True, touch=None):
    rt = tmp_path / "rt"
    rt.mkdir(exist_ok=True)
    monkeypatch.setenv("RUNNER_TEMP", str(rt))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(rt / "summary.md"))
    monkeypatch.setattr(DC, "head_sha", lambda cwd=None: HEAD)
    if need is not None:
        (rt / DC.NEED_FILE).write_text(json.dumps({"run": need, "why": "시험"}))
    site = tmp_path / "_site" if (tmp_path / "_site").exists() else make_site(tmp_path)
    ran = []

    def run(name, root, data, live_=False, **kw):
        live_ = live_ or kw.get("live", False)
        ran.append((name, "live" if live_ else "new", root, data))
        if touch and name == touch:
            (site / "extra.txt").write_text("x")
        return {"outcome": (live if live_ else new).get(name, DC.PASS), "detail": "x / y 통과", "fails": [], "unseen": []}

    def fake_find(net):
        if find:
            raise find
        return LIVE, {"app.html": b"x"}
    rc = DC.cmd_check(str(site), net=Net(), run=lambda n, r, d, live=False: run(n, r, d, live), find=fake_find,
                      prepare=lambda sha, served, tmp: str(tmp_path / "live"))
    dec = json.loads((rt / DC.DECISION_FILE).read_text()) if (rt / DC.DECISION_FILE).exists() else None
    return rc, dec, (rt / DC.RECEIPT_FILE), ran, site


def test_all_three_pass_writes_the_receipt_and_never_looks_at_the_live_code(tmp_path, monkeypatch):
    rc, dec, rec, ran, site = orchestrate(tmp_path, monkeypatch, new={})
    assert rc == 0 and dec["result"] == "pass" and rec.exists()
    assert ran == [(t, "new", ROOT, str(site)) for t in DC.CHECKS]                              # 셋 모두 · 이 순서로 · 새 코드 = 저장소 · 올릴 폴더
    assert rec.read_text() == DC.file_tree(str(site))


def test_new_code_failing_what_the_live_code_passes_blocks(tmp_path, monkeypatch, capsys):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_launch": DC.FAIL}, live={"smoke_launch": DC.PASS})
    out = capsys.readouterr().out
    assert rc == 1 and dec["result"] == "block" and not rec.exists()
    assert [r[:3] for r in ran] == [(t, "new", ROOT) for t in DC.CHECKS] + [("smoke_launch", "live", str(tmp_path / "live"))]
    err = [ln for ln in out.splitlines() if ln.startswith("::error title=배포 막음 · 배포 전 화면 검사::")]
    assert len(err) == 1 and "smoke_launch" in err[0] and "사이트는 그대로" in err[0]
    assert "### 뱁새 배포 전 화면 검사 — 막음" in (tmp_path / "rt" / "summary.md").read_text()


def test_live_code_failing_too_deploys_and_warns(tmp_path, monkeypatch, capsys):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": DC.FAIL}, live={"smoke_app": DC.FAIL})
    out = capsys.readouterr().out
    assert rc == 0 and dec["result"] == "alert" and rec.exists() and dec["live"] == LIVE
    assert any(ln.startswith("::warning title=배포 · 지금 사이트 코드도 실패::smoke_app") for ln in out.splitlines())
    assert "::error" not in out


def test_one_check_new_only_blocks_even_if_another_fails_on_both(tmp_path, monkeypatch):
    rc, dec, rec, _, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": DC.FAIL, "real_data_check": DC.FAIL},
                                     live={"smoke_app": DC.FAIL, "real_data_check": DC.PASS})
    assert rc == 1 and dec["result"] == "block" and not rec.exists()


@pytest.mark.parametrize("err", [DC.Unknown("사이트의 app.html 에 빌드 표시(baepsae-build)가 없어요"), KeyError("bug")])
def test_unknown_live_code_blocks_loudly(tmp_path, monkeypatch, capsys, err):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": DC.FAIL}, find=err)
    out = capsys.readouterr().out
    assert rc == 1 and dec["result"] == "block" and dec["unknown"] and not rec.exists()
    assert "지금 사이트의 코드를 알 수 없어요" in out and "::error title=배포 막음" in out
    assert not [r for r in ran if r[1] == "live"]


def test_skipped_data_deploy_runs_nothing_and_still_writes_the_receipt(tmp_path, monkeypatch):
    rc, dec, rec, ran, _ = orchestrate(tmp_path, monkeypatch, new={"smoke_app": DC.FAIL}, need=False)
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
            "rows": rows or [("smoke_app", "alert", "새 코드 141 / 145 통과 · 지금 사이트 코드도 142 / 145 통과")],
            "checks": {"smoke_app": {"new": {"fails": ["FAIL  [정상] x"]}, "live": {"fails": ["FAIL  [정상] y"]}}}}


@pytest.mark.parametrize("dec, receipt, change, match", [
    (None, True, None, "결과가 없어요"),
    (decision("block"), True, None, "올려도 돼요"),
    ({"result": "maybe"}, True, None, "올려도 돼요"),
    (decision("pass"), False, None, "영수증이 없어요"),
    (decision("pass"), True, "data.json", "검사한 것과 달라요"),
    (decision("pass"), True, "new-file.js", "검사한 것과 달라요"),                         # 더해진 파일도 잡아요
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
    assert body.splitlines()[0].startswith(DC.MARK) and "지금 사이트에 있던 코드" in body.splitlines()[0]
    assert W.MENTION in body and "/actions/runs/77" in body and W.PASTE.format(n=net.issues[-1]["number"]) in body
    assert "FAIL  [정상] x" in body and "FAIL  [정상] y" in body and "smoke_app" in body
    assert ("POST", f"/repos/{W.REPO}/labels") in [c[:2] for c in net.calls]                   # deploy-check 표시를 만들어요 (있으면 그대로)
    patched = [c for c in net.calls if c[0] == "PATCH"]
    assert len(patched) == 1 and W.PASTE.format(n=net.issues[-1]["number"]) in patched[0][2]["body"]


def test_alert_comments_on_the_open_issue_instead_of_opening_a_second_one(tmp_path, monkeypatch):
    net = Net(issues=[{"number": 9, "labels": [{"name": W.LABEL}]}])
    assert report(tmp_path, monkeypatch, decision("alert"), net) == 0
    assert not [c for c in net.calls if c[0] == "POST" and c[1].endswith("/issues")]
    comment = [c for c in net.calls if c[1].endswith("/issues/9/comments")]
    assert len(comment) == 1 and comment[0][2]["body"].startswith(DC.MARK) and W.MENTION in comment[0][2]["body"]
    assert ("POST", f"/repos/{W.REPO}/issues/9/labels", {"labels": [DC.LABEL]}) in net.calls


def test_alert_that_cannot_reach_jack_stops_the_upload(tmp_path, monkeypatch):
    net = Net(fail=lambda m, p: m == "POST" and p.endswith("/issues"))
    with pytest.raises(SystemExit, match="경보 이슈를 열지 못했어요"):
        report(tmp_path, monkeypatch, decision("alert"), net)


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
