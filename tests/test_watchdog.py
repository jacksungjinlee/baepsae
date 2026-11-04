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
                 jobs=None, busy=0):
        self.px, self.tag, self.head, self.head_at = px, tag, head, head_at
        self.data_runs = data_runs if data_runs is not None else [run(1, "success")]
        self.deploy_runs = deploy_runs if deploy_runs is not None else [run(2, "success")]
        self.deploy_exists, self.state, self.files_status = deploy_exists, state, files_status
        self.issues = [dict(i) for i in issues]
        self.pages_mode, self.jobs, self.busy = pages_mode, jobs or {}, busy
        self.calls, self.urls, self.next_issue = [], [], 50

    def get(self, url, timeout=30):
        self.urls.append(url)
        name = url.split("?")[0].rsplit("/", 1)[-1]
        if name in W.V.FILES:
            body = {"pxDate": self.px, "stocks": [{"t": "005930"}]} if name == "data.json" else {}
            return Resp(self.files_status, json.dumps(body).encode())
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


def go(net, now, argv=(), gate=ok_gate, want=D(2026, 11, 4), read_main=lambda p: page(None), env=None, monkeypatch=None):
    for k in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_RUN_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HC_PING_URL", "https://hc-ping.com/xyz")
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    return W.main(list(argv), net=net, now=now, gate=gate, expect=expect(want), read_main=read_main)


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


def test_selftest_marks_the_issue_and_does_not_page_jack(monkeypatch):
    net = FakeNet()
    assert go(net, AFTER, argv=["--selftest", "broken"], gate=bad_gate, monkeypatch=monkeypatch) == 1
    assert net.issues[-1]["body"].startswith("**[시험]**")
    assert not any("hc-ping" in u for u in net.urls)


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
    assert go(FakeNet(tag=None), AFTER, read_main=lambda p: page(None), monkeypatch=monkeypatch) == 0
    net = FakeNet(tag=None, head_at="2026-11-05T01:00:00Z")
    assert go(net, AFTER, read_main=lambda p: page(None) + b"new", monkeypatch=monkeypatch) == 1
    assert "Pages 가 예전 빌드" in net.issues[-1]["body"]


def test_pages_with_different_builds_are_a_problem():
    class Mixed(FakeNet):
        def get(self, url, timeout=30):
            if "app.html" in url:
                return Resp(200, page(OLD))
            return super().get(url, timeout)
    rep = W.Report()
    W.check_pages(rep, Mixed(), AFTER)
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
