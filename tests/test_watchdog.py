# -*- coding: utf-8 -*-
"""v17.6 Part 1: 감시(watchdog.py) — 사이트를 밖에서 확인하고, 경보 이슈를 하나만 열고, 정상화되면 닫아요.

밖(사이트 · GitHub API · 관문 · 달력)은 모두 가짜로 바꿔서 봐요. 실제 사이트로는 로컬에서 `python3 watchdog.py --dry` 를 돌려요.
"""
import datetime as dt
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import watchdog as W          # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
HEAD = "a" * 40
OLD = "b" * 40
D = dt.date


def kst(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=KST)


class Resp:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content


def page(tag=None):
    meta = f'\n<meta name="baepsae-build" content="{tag}">' if tag else ""
    return f'<!DOCTYPE html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">{meta}\n</head><body></body></html>'.encode()


class FakeNet:
    """사이트 파일 · GitHub API 를 흉내 내요. calls 에 GitHub 호출을 남겨요."""

    def __init__(self, px="2026-11-04", tag=HEAD, head=HEAD, head_at="2026-11-05T00:00:00Z", data_runs=None,
                 deploy_runs=None, deploy_exists=True, state="active", issues=(), files_status=200, pages_mode="workflow",
                 jobs=None, busy=0, data_tip_at="2026-11-05T00:00:00Z", data_branch=True):
        self.px, self.tag, self.head, self.head_at = px, tag, head, head_at
        self.data_bytes = json.dumps({"pxDate": px, "stocks": [{"t": "005930"}]}).encode()
        self.data_tip_at, self.data_branch = data_tip_at, data_branch
        self.data_runs = data_runs if data_runs is not None else [run(1, "success")]
        self.deploy_runs = deploy_runs if deploy_runs is not None else [run(2, "success")]
        self.deploy_exists, self.state, self.files_status = deploy_exists, state, files_status
        self.issues = [dict(i) for i in issues]
        real_deploy = [{"name": "decide", "conclusion": "success", "steps": [{"name": "x"}]},
                       {"name": "build", "conclusion": "success", "steps": [{"name": "x"}]},
                       {"name": "deploy", "conclusion": "success", "steps": [{"name": "x"}]}]
        self.pages_mode, self.jobs, self.busy = pages_mode, {2: real_deploy, **(jobs or {})}, busy
        self.calls, self.urls, self.next_issue = [], [], 50

    def get(self, url, timeout=30):
        self.urls.append(url)
        name = url.split("?")[0].rsplit("/", 1)[-1]
        if name in W.V.FILES:
            return Resp(self.files_status, self.data_bytes if name == "data.json" else b"{}")
        if name in W.PAGES:
            return Resp(200, page(self.tag))
        if "hc-ping" in url:
            return Resp(200)
        raise AssertionError(url)

    def gh(self, method, path, body=None, ok=(200, 201, 204)):
        self.calls.append((method, path, body))
        st, js = self._answer(method, path, body)
        if st not in ok:
            raise RuntimeError(f"{st} {path}")
        return st, js

    def _answer(self, method, path, body):
        p = path.split("?")[0]
        if method == "GET" and p.endswith("/actions/workflows/deploy.yml") and not self.deploy_exists:
            return 404, None
        if method == "GET" and p.rsplit("/", 1)[-1] in ("update-data.yml", "deploy.yml"):
            return 200, {"state": self.state}
        if method == "GET" and p.endswith("/update-data.yml/runs"):
            return 200, {"workflow_runs": self.data_runs}
        if method == "GET" and p.endswith("/deploy.yml/runs"):
            if not self.deploy_exists:
                return 404, None
            if "status=completed" in path:
                return 200, {"workflow_runs": self.deploy_runs}
            return 200, {"total_count": self.busy if "in_progress" in path else 0, "workflow_runs": []}
        if method == "GET" and "/actions/runs/" in p and p.endswith("/jobs"):
            rid = int(p.split("/actions/runs/")[1].split("/")[0])
            return 200, {"jobs": self.jobs.get(rid, [{"name": "update", "steps": [{"name": "x", "conclusion": "success"}]}])}
        if method == "GET" and p.endswith("/commits/main"):
            return 200, {"sha": self.head, "commit": {"committer": {"date": self.head_at}}}
        if method == "GET" and p.endswith("/commits/data"):
            if not self.data_branch:
                return 422, None
            return 200, {"sha": "d" * 40, "commit": {"committer": {"date": self.data_tip_at}}}
        if method == "GET" and p.endswith("/pages"):
            return 200, {"build_type": self.pages_mode}
        if method == "GET" and p.endswith("/issues"):
            return 200, [i for i in self.issues if i.get("state", "open") == "open"]
        if method == "POST" and p.endswith("/labels"):
            return 422, None
        if method == "POST" and p.endswith("/issues"):
            self.next_issue += 1
            i = {"number": self.next_issue, "created_at": "2026-11-05T07:37:00Z", **body}
            self.issues.append(i)
            return 201, i
        if method == "POST" and p.endswith("/comments"):
            return 201, {"id": 1}
        if method == "PATCH" and "/issues/" in p:
            n = int(p.rsplit("/", 1)[-1])
            for i in self.issues:
                if i["number"] == n:
                    i.update(body)
            return 200, {"number": n}
        raise AssertionError((method, path))


def run(rid, conclusion, title="시세 데이터 갱신", event="schedule"):
    return {"id": rid, "conclusion": conclusion, "display_title": title, "event": event, "html_url": f"https://x/runs/{rid}",
            "created_at": "2026-11-05T21:47:00Z", "run_started_at": "2026-11-05T21:47:00Z"}


def ok_gate(d):
    return True, "| 검사 | 값 |", []


def bad_gate(d):
    return False, "| 검사 | 값 |\n| 필수 종목 | 없음 |", ["필수 종목 (가격·시총): 없음: 005930 (기준 …)"]


def expect(want):
    return lambda today: (want, "시험 달력")


def published(net, data=None, html=None):
    """발행본 읽기 흉내: data.json 은 (주지 않으면) 사이트와 같은 바이트, 페이지는 빌드 표시 없는 main 의 것. 읽은 곳을 남겨요."""
    seen = []

    def read(ref, path):
        seen.append((ref, path))
        if path == "data.json":
            return net.data_bytes if data is None else data
        return page(None) if html is None else html
    read.seen = seen
    return read


def go(net, now, argv=(), gate=ok_gate, want=D(2026, 11, 4), read_ref=None, env=None, monkeypatch=None):
    for k in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_RUN_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HC_PING_URL", "https://hc-ping.com/xyz")
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    return W.main(list(argv), net=net, now=now, gate=gate, expect=expect(want), read_ref=read_ref or published(net))


AFTER = kst(2026, 11, 5, 16, 37)
MORNING = kst(2026, 11, 5, 7, 5)


def posts(net, suffix):
    return [c for c in net.calls if c[0] == "POST" and c[1].split("?")[0].endswith(suffix)]


def test_healthy_site_passes_and_pings_without_touching_issues(monkeypatch):
    net = FakeNet()
    assert go(net, AFTER, monkeypatch=monkeypatch) == 0
    assert not posts(net, "/issues") and not posts(net, "/comments")
    assert net.urls[-1] == "https://hc-ping.com/xyz"                          # 정상이면 healthchecks.io 에 알려요
    assert all("?t=" in u for u in net.urls if "jacksungjinlee.github.io" in u)   # 캐시를 피해요


def test_broken_files_open_one_alert_issue_and_end_red(monkeypatch):
    net = FakeNet()
    assert go(net, AFTER, gate=bad_gate, monkeypatch=monkeypatch, env={"GITHUB_RUN_ID": "77"}) == 1
    made = posts(net, "/issues")
    assert len(made) == 1 and made[0][2]["title"] == "뱁새 데이터 경보" and made[0][2]["labels"] == ["data-alert"]
    issue = net.issues[-1]
    body = issue["body"]
    assert "@jacksungjinlee" in body and "/actions/runs/77" in body and "필수 종목" in body
    assert f"뱁새 데이터 경보 이슈 #{issue['number']} 이 떴어. 로그를 보고 원인을 찾아서 CLAUDE.md 규칙대로 고치고 PR 열어줘." in body
    assert "검사를 통과하지 못했어요" in body and "| 필수 종목 | 없음 |" in body
    assert net.urls[-1] == "https://hc-ping.com/xyz/fail"


def test_repeat_failure_comments_instead_of_opening_a_second_issue(monkeypatch):
    net = FakeNet(issues=[{"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open"}])
    assert go(net, AFTER, gate=bad_gate, monkeypatch=monkeypatch) == 1
    assert not posts(net, "/issues")
    c = posts(net, "/issues/9/comments")
    assert len(c) == 1 and "아직 문제가 있어요" in c[0][2]["body"] and "@jacksungjinlee" not in c[0][2]["body"]


def test_recovery_comments_and_closes(monkeypatch):
    net = FakeNet(issues=[{"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open"}])
    assert go(net, AFTER, monkeypatch=monkeypatch) == 0
    c = posts(net, "/issues/9/comments")
    assert len(c) == 1 and c[0][2]["body"].startswith("정상화됐어요")
    assert ("PATCH", f"/repos/{W.REPO}/issues/9", {"state": "closed", "state_reason": "completed"}) in net.calls


def broken_only_gate(d):
    """진짜 관문처럼: 받은 data.json 에 필수 종목(005930)이 없을 때만 실패 (시험이 망가뜨린 파일만 걸려요)."""
    with open(os.path.join(d, "data.json"), encoding="utf-8") as fh:
        ts = {s.get("t") for s in json.load(fh).get("stocks", [])}
    return ok_gate(d) if "005930" in ts else bad_gate(d)


def hc_pings(net):
    return [u for u in net.urls if "hc-ping" in u]


def test_selftest_marks_the_issue_then_pages_jack_down_and_up(monkeypatch):
    """Jack, 2026-11-05: the test sends one failure signal to healthchecks.io, then a normal one — he gets 'down', then 'up'."""
    net = FakeNet()
    assert go(net, AFTER, argv=["--selftest", "broken"], gate=broken_only_gate, monkeypatch=monkeypatch) == 1
    test_issue = net.issues[-1]
    assert test_issue["body"].startswith("**[시험]**")
    assert hc_pings(net) == ["https://hc-ping.com/xyz/fail", "https://hc-ping.com/xyz"]      # 문제 → 정상, 이 순서로 한 번씩
    n = test_issue["number"]
    assert posts(net, f"/issues/{n}/comments")[-1][2]["body"].startswith("정상화됐어요")
    assert ("PATCH", f"/repos/{W.REPO}/issues/{n}", {"state": "closed", "state_reason": "completed"}) in net.calls


def test_selftest_leaves_a_real_problem_open_and_down(monkeypatch):
    """다시 점검에서도 진짜 문제가 있으면: '정상' 알림을 보내지 않고, 이슈를 닫지 않고, 진짜 경보로 남겨요."""
    net = FakeNet()
    assert go(net, AFTER, argv=["--selftest", "broken"], gate=bad_gate, monkeypatch=monkeypatch) == 1
    assert hc_pings(net) == ["https://hc-ping.com/xyz/fail"]
    assert not any(c[0] == "PATCH" and c[2] == {"state": "closed", "state_reason": "completed"} for c in net.calls)
    n = net.issues[-1]["number"]
    comments = posts(net, f"/issues/{n}/comments")
    assert comments and not comments[-1][2]["body"].startswith("**[시험]**")       # 진짜 경보의 반복 댓글 ([시험] 아님)
    assert net.issues[-1].get("state", "open") == "open"
    body = net.issues[-1]["body"]                       # 이슈 첫 줄이 '[시험] … 실제 사이트는 문제가 없어요'로 남으면 안 돼요
    assert not body.startswith("**[시험]**") and "뱁새 감시가 문제를 찾았어요" in body and f"이슈 #{n} 이 떴어" in body


def test_selftest_never_rewrites_a_real_alert_that_was_already_open(monkeypatch):
    """시험 전부터 열린 진짜 경보는 본문을 바꾸지 않아요 (언제부터 · 첫 줄이 그대로)."""
    real = {"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open", "body": "@jacksungjinlee 진짜 경보 (처음 본문)"}
    net = FakeNet(issues=[real])
    assert go(net, AFTER, argv=["--selftest", "broken"], gate=bad_gate, monkeypatch=monkeypatch) == 1
    assert net.issues[0]["body"] == real["body"] and net.issues[0].get("state", "open") == "open"
    assert not any(c[0] == "PATCH" and c[1].endswith("/issues/9") for c in net.calls)


def test_selftest_really_breaks_the_downloaded_data(tmp_path):
    (tmp_path / "data.json").write_text(json.dumps({"pxDate": "2026-11-04", "stocks": [{"t": "005930"}, {"t": "999999"}]}))
    W.break_for_selftest(str(tmp_path))
    left = [s["t"] for s in json.loads((tmp_path / "data.json").read_text())["stocks"]]
    assert left == ["999999"] and not set(left) & set(W.V.MUST)


def test_dry_run_never_writes_or_pings(monkeypatch):
    net = FakeNet(issues=[{"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open"}])
    assert go(net, AFTER, argv=["--dry"], gate=bad_gate, monkeypatch=monkeypatch) == 1
    assert not [c for c in net.calls if c[0] != "GET"] and not any("hc-ping" in u for u in net.urls)


def test_missing_ping_url_warns_loudly(monkeypatch, capsys):
    net = FakeNet()
    assert W.ping(net, "") is False
    assert "::warning title=healthchecks.io 없음::" in capsys.readouterr().out


def test_unreachable_data_file_is_a_problem(monkeypatch):
    net = FakeNet(files_status=404)
    assert go(net, AFTER, monkeypatch=monkeypatch) == 1
    assert "사이트 데이터 파일 받기" in net.issues[-1]["body"]


# ── 낡은 가격 ──
def test_stale_price_is_checked_only_after_1530_kst(monkeypatch):
    net = FakeNet(px="2026-11-03")
    assert go(net, MORNING, monkeypatch=monkeypatch) == 0                     # 아침: 그날 실행이 아직 돌 수 있어요
    net = FakeNet(px="2026-11-03")
    assert go(net, AFTER, monkeypatch=monkeypatch) == 1
    assert "낡은 가격" in net.issues[-1]["body"] and "사이트 2026-11-03" in net.issues[-1]["body"]
    assert go(FakeNet(px="2026-11-04"), AFTER, monkeypatch=monkeypatch) == 0


def test_expected_date_is_the_later_of_two_independent_sources():
    t = D(2026, 11, 5)
    got, src = W.expected_px(t, lambda d: D(2026, 11, 3), lambda: [D(2026, 11, 3), D(2026, 11, 4), D(2026, 11, 5)], sleep=lambda s: None)
    assert got == D(2026, 11, 4) and "야후 ^KS11 2026-11-04" in src           # 오늘 봉은 빼요
    got, _ = W.expected_px(t, lambda d: D(2026, 11, 4), lambda: [D(2026, 11, 3)], sleep=lambda s: None)
    assert got == D(2026, 11, 4)

    def boom(*a):
        raise OSError("막힘")
    got, src = W.expected_px(t, boom, lambda: [D(2026, 11, 4)], sleep=lambda s: None)
    assert got == D(2026, 11, 4) and "최종본 목록: 받지 못함" in src
    got, src = W.expected_px(t, boom, boom, sleep=lambda s: None)
    assert got is None
    rep = W.Report()
    W.check_stale(rep, "2026-11-04", AFTER, lambda today: (None, "둘 다 실패"))
    assert rep.problems and "기대 날짜를 정하지 못했어요" in rep.problems[0][2]


# ── 실행 결과 ──
def test_latest_completed_live_run_must_have_succeeded(monkeypatch):
    runs = [run(5, "success", "시세 데이터 갱신 · 시험 실행"), run(4, "failure")]
    assert go(FakeNet(data_runs=runs), MORNING, monkeypatch=monkeypatch) == 1          # 시험 실행은 빼고 본 마지막 = 실패
    runs = [run(5, "failure", "시세 데이터 갱신 · 시험 실행"), run(4, "success")]
    assert go(FakeNet(data_runs=runs), MORNING, monkeypatch=monkeypatch) == 0
    # 대기 중에 새 실행에 밀려 한 단계도 안 돈 취소는 실패가 아니에요 · 돌다가 취소(시간 초과 등)는 실패예요
    jobs = {6: [{"name": "update", "steps": []}], 7: [{"name": "update", "steps": [{"name": "데이터 수집"}]}]}
    assert go(FakeNet(data_runs=[run(6, "cancelled"), run(4, "success")], jobs=jobs), MORNING, monkeypatch=monkeypatch) == 0
    assert go(FakeNet(data_runs=[run(7, "cancelled"), run(4, "success")], jobs=jobs), MORNING, monkeypatch=monkeypatch) == 1
    assert go(FakeNet(deploy_runs=[run(8, "failure", "Deploy")]), MORNING, monkeypatch=monkeypatch) == 1


def test_disabled_schedule_is_a_problem(monkeypatch):
    net = FakeNet(state="disabled_inactivity")
    assert go(net, MORNING, monkeypatch=monkeypatch) == 1
    assert "꺼져 있어요" in net.issues[-1]["body"]


def test_deploy_workflow_not_on_main_yet_is_skipped(monkeypatch):
    net = FakeNet(deploy_exists=False, tag=None)
    assert go(net, MORNING, monkeypatch=monkeypatch) == 0


# ── 페이지와 빌드 ──
def test_actions_build_tag_must_match_main(monkeypatch):
    assert go(FakeNet(tag=HEAD, head=HEAD), AFTER, monkeypatch=monkeypatch) == 0
    net = FakeNet(tag=OLD, head=HEAD, head_at="2026-11-05T01:00:00Z")          # main 은 6시간 전에 바뀜, 사이트는 예전 빌드
    assert go(net, AFTER, monkeypatch=monkeypatch) == 1 and "사이트 빌드 = main" in net.issues[-1]["body"]
    fresh = (AFTER - dt.timedelta(minutes=10)).astimezone(dt.timezone.utc).isoformat()
    assert go(FakeNet(tag=OLD, head=HEAD, head_at=fresh), AFTER, monkeypatch=monkeypatch) == 0   # 방금 바뀜: 기다려요
    assert go(FakeNet(tag=OLD, head=HEAD, head_at="2026-11-05T01:00:00Z", busy=1), AFTER, monkeypatch=monkeypatch) == 0


def test_branch_deploy_pages_must_equal_main_files(monkeypatch):
    assert go(FakeNet(tag=None), AFTER, monkeypatch=monkeypatch) == 0
    net = FakeNet(tag=None, head_at="2026-11-05T01:00:00Z")
    assert go(net, AFTER, read_ref=published(net, html=page(None) + b"new"), monkeypatch=monkeypatch) == 1
    assert "Pages 가 예전 빌드" in net.issues[-1]["body"]


def test_pages_with_different_builds_are_a_problem():
    class Mixed(FakeNet):
        def get(self, url, timeout=30):
            if "app.html" in url:
                return Resp(200, page(OLD))
            return super().get(url, timeout)
    rep = W.Report()
    W.check_pages(rep, Mixed(), AFTER, read_ref=lambda ref, p: page(None))
    assert any(r[0] == "페이지 빌드가 모두 같음" for r in rep.problems)


# ── 언제 점검할지 (workflow_run) ──
def test_decide_avoids_checking_twice():
    pushed = {1: [{"name": "update", "conclusion": "success", "steps": [{"name": W.PUSH_STEP, "conclusion": "success"}]}]}
    skipped = {1: [{"name": "update", "conclusion": "success", "steps": [{"name": W.PUSH_STEP, "conclusion": "skipped"}]}]}
    assert W.decide(FakeNet(), "schedule", "", "")[0] is True
    assert W.decide(FakeNet(pages_mode="workflow", jobs=pushed), "workflow_run", W.DATA_NAME, 1)[0] is False   # 배포 뒤에 봐요
    assert W.decide(FakeNet(pages_mode="legacy", jobs=pushed), "workflow_run", W.DATA_NAME, 1)[0] is True
    assert W.decide(FakeNet(pages_mode="workflow", jobs=skipped), "workflow_run", W.DATA_NAME, 1)[0] is True
    nothing = {1: [{"name": "decide", "conclusion": "success", "steps": []}, {"name": "build", "conclusion": "skipped", "steps": []},
                   {"name": "deploy", "conclusion": "skipped", "steps": []}]}
    broke = {1: [{"name": "decide", "conclusion": "success", "steps": []}, {"name": "build", "conclusion": "failure", "steps": []},
                 {"name": "deploy", "conclusion": "skipped", "steps": []}]}
    assert W.decide(FakeNet(jobs=nothing), "workflow_run", W.DEPLOY_NAME, 1)[0] is False
    assert W.decide(FakeNet(jobs=broke), "workflow_run", W.DEPLOY_NAME, 1)[0] is True             # 배포 실패는 꼭 봐요

    class Down(FakeNet):
        def gh(self, *a, **k):
            raise RuntimeError("API 막힘")
    assert W.decide(Down(), "workflow_run", W.DATA_NAME, 1)[0] is True                              # 모르면 점검해요


def test_decide_writes_github_output(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    assert W.main(["--decide"], net=FakeNet()) == 0
    assert out.read_text() == "go=true\n"


def test_watchdog_uses_the_gate_in_live_mode(tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        with open(kw["env"]["GITHUB_STEP_SUMMARY"], "w", encoding="utf-8") as f:
            f.write("표")

        class R:
            returncode, stdout, stderr = 1, "!! FAIL  필수 종목 (가격·시총): 없음\n", ""
        return R()
    ok, md, fails = W.run_live_gate(str(tmp_path), run=fake_run)
    assert seen["cmd"][1].endswith("validate_data.py") and seen["cmd"][2:] == ["--live", "--dir", str(tmp_path)]
    assert ok is False and md == "표" and fails == ["필수 종목 (가격·시총): 없음"]


# ── 사이트의 data.json = 발행본 (리뷰 2026-11-05) ──
def test_live_data_must_equal_the_published_copy(monkeypatch):
    # Actions 배포: data 브랜치 끝과 비교해요
    net = FakeNet(tag=HEAD)
    read = published(net)
    assert go(net, AFTER, read_ref=read, monkeypatch=monkeypatch) == 0 and ("data", "data.json") in read.seen
    net = FakeNet(tag=HEAD, data_tip_at="2026-11-05T01:00:00Z")                    # data 가 6시간 전에 바뀌었는데 사이트는 예전 것
    assert go(net, AFTER, read_ref=published(net, data=b'{"pxDate": "2026-11-05"}'), monkeypatch=monkeypatch) == 1
    assert "사이트 data.json = 발행본" in net.issues[-1]["body"]
    fresh = (AFTER - dt.timedelta(minutes=10)).astimezone(dt.timezone.utc).isoformat()
    net = FakeNet(tag=HEAD, data_tip_at=fresh)                                      # 방금 바뀜: 배포를 기다려요
    assert go(net, AFTER, read_ref=published(net, data=b"{}"), monkeypatch=monkeypatch) == 0
    # 브랜치 배포: main 과 비교해요 (데이터만 바뀐 날 Pages 빌드가 실패한 것을 잡아요 — 페이지는 같아요)
    net = FakeNet(tag=None, head_at="2026-11-05T01:00:00Z")
    read = published(net, data=b'{"pxDate": "2026-11-05"}')
    assert go(net, AFTER, read_ref=read, monkeypatch=monkeypatch) == 1 and ("main", "data.json") in read.seen
    assert not [r for r in read.seen if r[0] == "data"]


def test_actions_mode_without_a_data_branch_is_a_problem(monkeypatch):
    net = FakeNet(tag=HEAD, data_branch=False)
    assert go(net, AFTER, monkeypatch=monkeypatch) == 1 and "data 브랜치가 없어요" in net.issues[-1]["body"]


def test_selftest_compares_the_file_as_downloaded(monkeypatch):
    net = FakeNet(tag=HEAD)
    rep, _ = W.run_all(net, AFTER, "broken", gate=bad_gate, expect=expect(D(2026, 11, 4)), read_ref=published(net))
    assert ("사이트 data.json = 발행본", "PASS") in [(r[0], r[1]) for r in rep.rows]       # 망가뜨리기 전의 바이트로 비교


def test_a_skipped_deploy_does_not_hide_an_earlier_failed_one(monkeypatch):
    noop = [{"name": "decide", "conclusion": "success", "steps": [{"name": "x"}]},
            {"name": "build", "conclusion": "skipped", "steps": []}, {"name": "deploy", "conclusion": "skipped", "steps": []}]
    runs = [run(9, "success", "Deploy"), run(8, "failure", "Deploy")]
    net = FakeNet(deploy_runs=runs, jobs={9: noop})
    assert go(net, MORNING, monkeypatch=monkeypatch) == 1 and "/runs/8" in net.issues[-1]["body"]
    # 모두 건너뛴 배포면(브랜치 배포 동안) 실패가 아니에요
    assert go(FakeNet(tag=None, deploy_runs=[run(9, "success", "Deploy")], jobs={9: noop}), MORNING, monkeypatch=monkeypatch) == 0
    rep = W.Report()
    W.check_runs(rep, FakeNet(deploy_runs=[run(9, "success", "Deploy")], jobs={9: noop}), W.DEPLOY_WF, W.DEPLOY_NAME, skip_noop=True)
    assert rep.rows[-1][1] == "SKIP"


# ── healthchecks.io ──
def test_ping_url_is_stripped(monkeypatch):
    net = FakeNet()
    assert W.ping(net, " https://hc-ping.com/xyz\n") is True and net.urls[-1] == "https://hc-ping.com/xyz"
    net = FakeNet()
    assert go(net, AFTER, env={"HC_PING_URL": "https://hc-ping.com/xyz\n"}, monkeypatch=monkeypatch) == 0
    assert net.urls[-1] == "https://hc-ping.com/xyz"


def test_fail_ping_is_sent_even_when_github_cannot_open_the_issue(monkeypatch):
    class Down(FakeNet):
        def _answer(self, method, path, body):
            if method == "POST" and path.split("?")[0].endswith("/issues"):
                return 502, None
            return super()._answer(method, path, body)
    net = Down()
    with pytest.raises(RuntimeError, match="502"):
        go(net, AFTER, gate=bad_gate, monkeypatch=monkeypatch)
    assert net.urls[-1] == "https://hc-ping.com/xyz/fail"
