# -*- coding: utf-8 -*-
"""감시(watchdog.py): 사이트의 5xx 는 한 번 더 물어요 (Jack 2026-11-19, "Q10 watchdog retry: yes").

GitHub Pages 가 한 번 502 · 503 을 내면 전에는 바로 '뱁새 데이터 경보' 이슈가 열렸어요. 이제 사이트에 묻는 GET(네 데이터 파일 ·
세 페이지)은 5xx 면 RETRY_5XX_WAIT 초 쉬고 한 번만 다시 물어요. 두 번째도 200 이 아니면 전과 같이 실패예요. 4xx 는 다시 묻지
않고, 연결 오류는 전처럼 Net.get 이 세 번 물어요. 다시 물은 곳은 한 줄씩, 끝에 몇 곳인지 로그에 적어요.
밖(사이트 · GitHub API · 관문 · 달력)은 tests/test_watchdog.py 의 가짜를 그대로 써요.
"""
import datetime as dt
import os
import sys

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import watchdog as W                                                      # noqa: E402
from test_watchdog import AFTER, FakeNet, Resp, expect, ok_gate, page, published     # noqa: E402

D = dt.date
WANT = D(2026, 11, 4)


class Scripted(FakeNet):
    """사이트의 정해진 파일에 정해진 답을 차례로 줘요 (숫자 = 그 상태 코드, 예외 = 연결 오류). 다 쓰면 FakeNet 의 보통 답."""

    def __init__(self, script=None, **kw):
        super().__init__(**kw)
        self.script = {k: list(v) for k, v in (script or {}).items()}

    def get(self, url, timeout=30):
        todo = self.script.get(url.split("?")[0][len(W.SITE):])
        if todo:
            x = todo.pop(0)
            self.urls.append(url)
            if isinstance(x, Exception):
                raise x
            return Resp(x)
        return super().get(url, timeout)

    def asked(self, name):
        return sum(u.split("?")[0] == W.SITE + name for u in self.urls)


def check(net, monkeypatch, argv=()):
    """main 을 (이슈 · 알림까지) 돌려요. 반환: (끝 코드, 쉰 초 목록)."""
    for k in ("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT", "GITHUB_RUN_ID", "WATCHDOG_SELFTEST"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HC_PING_URL", "https://hc-ping.com/xyz")
    waits = []
    code = W.main(list(argv), net=net, now=AFTER, gate=ok_gate, expect=expect(WANT), read_ref=published(net),
                  sleep=waits.append)
    return code, waits


def issue_posts(net):
    return [c for c in net.calls if c[0] == "POST" and c[1].split("?")[0].endswith(("/issues", "/comments"))]


def test_the_wait_is_a_short_pause():
    assert 20 <= W.RETRY_5XX_WAIT <= 30


# ── 한 번의 5xx → 다시 물어서 200 → 경보 없음 ──
def test_one_5xx_on_a_data_file_is_asked_again_and_raises_no_alarm(monkeypatch, capsys):
    net = Scripted({"data.json": [503]})
    code, waits = check(net, monkeypatch)
    out = capsys.readouterr().out
    assert code == 0 and not issue_posts(net)
    assert net.urls[-1] == "https://hc-ping.com/xyz"                         # 정상 알림 (/fail 아님)
    assert waits == [W.RETRY_5XX_WAIT] and net.asked("data.json") == 2
    assert f"· 5xx 다시 물음 ({W.RETRY_5XX_WAIT}초 뒤): data.json 503 → 200" in out
    assert "· 5xx 다시 시도: 1곳 (data.json 503 → 200)" in out


def test_one_5xx_on_a_page_is_asked_again_and_the_row_says_so(monkeypatch, capsys):
    net = Scripted({"app.html": [502]})
    code, waits = check(net, monkeypatch)
    out = capsys.readouterr().out
    assert code == 0 and not issue_posts(net)
    assert waits == [W.RETRY_5XX_WAIT] and net.asked("app.html") == 2
    assert "app.html 502 → 200" in out and "· 5xx 다시 시도: 1곳 (app.html 502 → 200)" in out
    assert f"PASS  app.html 열림: HTTP 200 (처음 HTTP 502, {W.RETRY_5XX_WAIT}초 뒤 다시 물었어요)" in out


def test_every_site_file_and_page_gets_its_one_retry(monkeypatch, capsys):
    names = list(W.V.FILES) + list(W.PAGES)
    net = Scripted({n: [500 + i % 5] for i, n in enumerate(names)})
    code, waits = check(net, monkeypatch)
    out = capsys.readouterr().out
    assert code == 0 and not issue_posts(net)
    assert waits == [W.RETRY_5XX_WAIT] * len(names) and all(net.asked(n) == 2 for n in names)
    assert f"· 5xx 다시 시도: {len(names)}곳 (" in out


def test_a_healthy_check_never_waits_and_counts_zero(monkeypatch, capsys):
    net = Scripted()
    code, waits = check(net, monkeypatch)
    out = capsys.readouterr().out
    assert code == 0 and waits == [] and "5xx 다시 물음" not in out
    assert "· 5xx 다시 시도: 0곳\n" in out
    assert all(net.asked(n) == 1 for n in list(W.V.FILES) + list(W.PAGES))


# ── 두 번 5xx → 전과 같이 실패 ──
def test_a_second_5xx_on_a_data_file_is_still_an_alarm(monkeypatch, capsys):
    net = Scripted({"data.json": [503, 503, 503]})
    code, waits = check(net, monkeypatch)
    out = capsys.readouterr().out
    assert code == 1 and net.asked("data.json") == 2 and waits == [W.RETRY_5XX_WAIT]   # 한 번만 다시 물어요
    body = net.issues[-1]["body"]
    assert "사이트 데이터 파일 받기" in body and "data.json: HTTP 503" in body
    assert "!! 5xx 다시 물음" in out and "· 5xx 다시 시도: 1곳 (data.json 503 → 503)" in out
    assert net.urls[-1] == "https://hc-ping.com/xyz/fail"


@pytest.mark.parametrize("second", [502, 404, 301])
def test_a_5xx_then_another_non_200_answer_is_still_a_failure(second, tmp_path):
    net, waits, retried = Scripted({"macro.json": [503, second]}), [], []
    bad = W.fetch_live(net, str(tmp_path), AFTER, sleep=waits.append, retried=retried)
    assert bad == [f"macro.json: HTTP {second} (처음 HTTP 503, {W.RETRY_5XX_WAIT}초 뒤 다시 물었어요)"]
    assert waits == [W.RETRY_5XX_WAIT] and retried == [f"macro.json 503 → {second}"] and net.asked("macro.json") == 2


def test_a_second_5xx_on_a_page_is_still_a_failure():
    rep, net, waits = W.Report(), Scripted({"baepsae.html": [503, 503]}), []
    W.check_pages(rep, net, AFTER, read_ref=lambda ref, p: page(None), sleep=waits.append, retried=[])
    assert [r[0] for r in rep.problems] == ["baepsae.html 열림"]
    assert rep.problems[0][2].startswith("HTTP 503") and net.asked("baepsae.html") == 2 and waits == [W.RETRY_5XX_WAIT]


# ── 4xx 는 다시 묻지 않아요 ──
@pytest.mark.parametrize("status", [400, 403, 404, 429])
def test_a_4xx_is_never_asked_again(status, monkeypatch, capsys):
    net = Scripted({"data.json": [status], "styleguide.html": [status]})
    code, waits = check(net, monkeypatch)
    out = capsys.readouterr().out
    assert code == 1 and waits == []
    assert net.asked("data.json") == 1 and net.asked("styleguide.html") == 1
    body = net.issues[-1]["body"]
    assert f"data.json: HTTP {status}" in body and "다시 물었어요" not in body
    assert "· 5xx 다시 시도: 0곳" in out


def test_files_status_404_is_asked_once_each(tmp_path):
    net = FakeNet(files_status=404)
    waits = []
    W.fetch_live(net, str(tmp_path), AFTER, sleep=waits.append, retried=[])
    assert waits == [] and len(net.urls) == len(W.V.FILES)


# ── 연결 오류는 전과 같아요 ──
def test_a_connection_error_is_a_failure_as_before_without_the_5xx_wait(monkeypatch):
    net = Scripted({"data.json": [RuntimeError("data.json: ConnectionError")]})
    code, waits = check(net, monkeypatch)
    assert code == 1 and waits == [] and net.asked("data.json") == 1
    assert "data.json: data.json: ConnectionError" in net.issues[-1]["body"]


def test_a_5xx_then_a_connection_error_is_a_failure_and_logged(capsys, tmp_path):
    net, waits, retried = Scripted({"data.json": [503, RuntimeError("data.json: ConnectionError")]}), [], []
    bad = W.fetch_live(net, str(tmp_path), AFTER, sleep=waits.append, retried=retried)
    out = capsys.readouterr().out
    assert len(bad) == 1 and bad[0].startswith("data.json: data.json: ConnectionError") and "처음 HTTP 503" in bad[0]
    assert waits == [W.RETRY_5XX_WAIT] and retried == ["data.json 503 → data.json: ConnectionError"]
    assert "!! 5xx 다시 물음" in out


class Session:
    """requests.Session 흉내: 정해진 답을 차례로 (예외면 던져요)."""

    def __init__(self, answers):
        self.answers, self.n = list(answers), 0

    def get(self, url, timeout=30, headers=None):
        self.n += 1
        x = self.answers.pop(0)
        if isinstance(x, Exception):
            raise x
        return x


def test_net_get_still_retries_connection_errors_three_times_and_not_5xx(monkeypatch):
    slept = []
    monkeypatch.setattr(W.time, "sleep", slept.append)
    net = W.Net()
    net.s = Session([requests.ConnectionError("x")] * 3)
    with pytest.raises(RuntimeError, match="ConnectionError"):
        net.get(W.SITE + "data.json?t=1")
    assert net.s.n == 3 and slept == [2, 4, 6]
    net.s = Session([Resp(503)])                                           # Net.get 은 5xx 를 그대로 돌려줘요
    assert net.get(W.SITE + "data.json?t=1").status_code == 503 and net.s.n == 1
    net.s = Session([Resp(503), Resp(200)])                                # 다시 묻는 건 site_get 이에요
    waits = []
    r, first = W.site_get(net, W.SITE + "data.json?t=1", sleep=waits.append)
    assert r.status_code == 200 and first == 503 and net.s.n == 2 and waits == [W.RETRY_5XX_WAIT]


# ── docs/ 확인은 전처럼 (두 번까지), 다시 물은 곳만 크게 적어요 ──
def test_docs_retries_are_logged_and_counted_with_the_same_decision(capsys):
    rep, net, waits, retried = W.Report(), Scripted({"docs/RUNBOOK.md": [503]}), [], []
    W.check_no_docs(rep, net, AFTER, sleep=waits.append, retried=retried)
    out = capsys.readouterr().out
    assert not rep.problems and waits == [5]                                 # 판단 · 기다림은 전과 같아요
    assert retried == ["docs/RUNBOOK.md 503 → 404"] and "· 5xx 다시 물음: docs/RUNBOOK.md 503 → 404" in out
    rep, net, retried = W.Report(), Scripted({"docs/RUNBOOK.md": [502, 502, 502]}), []
    W.check_no_docs(rep, net, AFTER, sleep=lambda s: None, retried=retried)
    assert rep.problems and retried == ["docs/RUNBOOK.md 502 → 502 → 502"] and "!! 5xx 다시 물음" in capsys.readouterr().out


def test_the_healthchecks_ping_is_not_retried():
    class Down(FakeNet):
        def get(self, url, timeout=30):
            self.urls.append(url)
            return Resp(503)
    net = Down()
    assert W.ping(net, "https://hc-ping.com/xyz") is False and len(net.urls) == 1
