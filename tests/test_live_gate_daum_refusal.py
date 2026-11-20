# -*- coding: utf-8 -*-
"""2026-11-21 (Jack, 11-20 질문 3, 그대로): "Deploy price check when Daum refuses instead of being slow. Your 10-minute limit covers a slow
Daum. If Daum starts refusing GitHub's servers outright, the way KRX did, nothing times out, and every code deploy stops until Daum answers
again. Skip the Daum check in that case too, with the same loud warning? It loosens a check, so it's yours. (Recommended: yes, for code
deploys only. The daily data publish keeps its own two-source checks either way.)" → 11-21 "3. Yes." (네트워크 없음 · 한 시험만 이 컴퓨터
안의 닫힌 포트에 진짜로 물어요)

이 시험은 (새 파일 · 다른 시험은 고치지 않았어요):
- 거절의 뜻 (px_refusal_answer · px_refusal_error): HTTP 401 · 403 · 451, 세 번 모두 연결 거부 · 연결 끊김 · TLS 끊김 · HTTP 429 — 시간 초과 ·
  5xx · DNS · 프록시 · 인증서 · JSON 이 아닌 200 · 404 · 그날 행 없음은 거절이 아니에요;
- 배포 (한도를 받은 --live): 답이 정해진 종목이 모두 거절이고 필수 종목이 모두 그 안에 있고 그 수가 px_alt_refuse_need (207종목이면 21) 에
  닿으면 더 묻지 않고, 시간 한도와 같은 줄을 경고로 바꿔 배포가 다른 검사로 계속해요 (로그 '!!' 두 줄 · 실행 요약 표 · GitHub 경고 알림);
- 감시 (한도 없는 --live) 와 발행 관문은 같은 거절에도 예전 그대로 모든 종목을 묻고 실패해요;
- 일부만 거절 (거절이 아닌 답이 하나라도 먼저 옴) 은 예전 그대로예요;
- 받은 종가가 발행 가격과 다르면 예전과 같은 가격 줄이 실패해요 (#157 의 기준 그대로) · 다음이 분명히 '그날 종가 없음' 이라고 답한 필수
  종목은 예전 그대로 실패해요.
"""
import datetime as dt
import os
import socket
import ssl
import sys
import threading

import pytest
import requests
import urllib3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import validate_data as V  # noqa: E402
from fixture_data import hilo_of  # noqa: E402
from test_live_gate_daum_limit import Clock, FakeResp, check, failed, fb_files, live_alt, prices, rows, via_daum_page  # noqa: E402

PX = dt.date(2026, 10, 30)
REAL_HTTP_PX_ALT = V.http_px_alt
NEED = 21                                    # 207종목 (필수 7 + 표본 200): 21종목이 빠지면 나머지가 모두 답해도 186 / 207 < 90%
MOMENT = "!! 관문의 두 출처 확인: 다음이 거절해요"
AFTER = "!! 관문의 두 출처 확인을 다음이 거절했어요 (Jack 2026-11-21 · 배포만)"


# ── 진짜와 같은 꼴의 예외 (requests 가 urllib3 · 소켓 오류를 감싸는 꼴 그대로 — 이 컴퓨터에서 본 꼴) ─────────────────────
def refused_exc():
    nce = urllib3.exceptions.NewConnectionError(None, "Failed to establish a new connection: [Errno 111] Connection refused")
    nce.__cause__ = ConnectionRefusedError(111, "Connection refused")
    return requests.ConnectionError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=nce))


def reset_exc():
    return requests.ConnectionError(urllib3.exceptions.ProtocolError("Connection aborted.", ConnectionResetError(104, "Connection reset by peer")))


def closed_exc():
    import http.client
    return requests.ConnectionError(urllib3.exceptions.ProtocolError(
        "Connection aborted.", http.client.RemoteDisconnected("Remote end closed connection without response")))


def tls_eof_exc():
    inner = urllib3.exceptions.SSLError(ssl.SSLEOFError(8, "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"))
    return requests.exceptions.SSLError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=inner))


def cert_exc():
    inner = urllib3.exceptions.SSLError(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"))
    return requests.exceptions.SSLError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=inner))


def dns_exc():
    import socket as so
    nre = urllib3.exceptions.NameResolutionError("finance.daum.net", None, so.gaierror(-3, "Temporary failure in name resolution"))
    return requests.ConnectionError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=nre))


def proxy_exc():
    nce = urllib3.exceptions.NewConnectionError(None, "Connection refused")
    nce.__cause__ = ConnectionRefusedError(111, "Connection refused")
    return requests.exceptions.ProxyError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=nce))


REFUSAL_EXC = {"연결 거부": refused_exc, "연결 끊김 (reset)": reset_exc, "응답 없이 닫음": closed_exc, "TLS 끊김": tls_eof_exc,
               "HTTP 429": lambda: requests.HTTPError("429 Client Error: Too Many Requests", response=FakeResp(429))}


def raising(clk, make, calls=None, step=0.0):
    """가짜 다음: 물을 때마다 make() 의 예외를 내요 (가짜 시계는 step 초씩)."""
    def f(code, d):
        if calls is not None:
            calls.append(code)
        clk.t += step
        raise make()
    return f


def answer_only(cur, codes):
    """가짜 다음: codes 에는 발행 가격 그대로 답하고, 나머지는 세 번 모두 연결 거부."""
    px = prices(cur)

    def f(code, d):
        if code in codes:
            return px[code], "daum"
        raise refused_exc()
    return f


def counted(alt):
    return alt["got"] + alt["cut"] + alt["no"] + alt["net"] + alt["ref"] + alt["rskip"]


# ── 1. 거절의 뜻 (순수 함수) ─────────────────────────────────────────────────────────────────
def test_what_counts_as_a_refusal():
    assert all(V.px_refusal_answer(f"HTTP {s}") for s in (401, 403, 451))
    assert not any(V.px_refusal_answer(w) for w in ("HTTP 404", "HTTP 400", "HTTP 410", "HTTP 4031", "그날 행 0개", "그날 행 2개", "종가 없음",
                                                     None, 403, "시간 한도", "다음이 거절"))
    yes = [f() for f in REFUSAL_EXC.values()] + [ConnectionRefusedError(111, "x"), ConnectionResetError(104, "x"), ConnectionAbortedError("x"),
                                                 BrokenPipeError("x"), requests.HTTPError("429 Client Error")]
    no = [requests.Timeout("x"), requests.exceptions.ReadTimeout("x"), requests.exceptions.ConnectTimeout("x"), TimeoutError("read timed out"),
          cert_exc(), dns_exc(), proxy_exc(), ConnectionError("refused"), requests.ConnectionError("x"),
          requests.HTTPError("x", response=FakeResp(500)), requests.HTTPError("x", response=FakeResp(503)), requests.HTTPError("502 err"),
          requests.HTTPError("x", response=FakeResp(403)), requests.HTTPError("x", response=FakeResp(404)),
          requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0), ValueError("Expecting value"), KeyError("data"), RuntimeError("x")]
    assert all(V.px_refusal_error(e) for e in yes), [e for e in yes if not V.px_refusal_error(e)]
    assert not any(V.px_refusal_error(e) for e in no), [e for e in no if V.px_refusal_error(e)]
    assert all(V.px_net_error(e) for e in yes)                         # 거절은 모두 #157 의 네트워크 오류 안이에요 (새 갈래를 만들지 않아요)


def test_refusal_count_needed():
    assert [V.px_alt_refuse_need(n) for n in (207, 206, 200, 30, 7, 1, 0, None)] == [21, 21, 21, 7, 7, 7, 7, 7]
    for n in (207, 206, 200, 150):
        k = V.px_alt_refuse_need(n)
        assert n - k < V.PX_ALT_MIN_SHARE * n <= n - (k - 1)          # k 개가 빠지면 표본 기준을 채울 수 없고, 하나 덜 빠지면 채울 수 있어요


def test_a_real_refused_port_is_a_refusal():
    """이 컴퓨터 안의 닫힌 포트에 진짜로 물어요 (requests 가 실제로 내는 꼴 그대로 · 바깥 네트워크 없음)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    sess = requests.Session()
    sess.trust_env = False                                             # 프록시 없이 바로
    with pytest.raises(requests.ConnectionError) as ei:
        V._daum_day_close("005930", PX, get=lambda u: sess.get(f"http://127.0.0.1:{port}/api", timeout=5))
    assert V.px_refusal_error(ei.value) and V.px_net_error(ei.value)


# ── 2. 배포 (한도를 받은 --live): 거절이면 그만 묻고 경고로 건너뛰어요 ─────────────────────────────────────
@pytest.mark.parametrize("status", [403, 401, 451])
def test_deploy_skips_when_daum_answers_access_refused(status):
    cur, _, _ = fb_files()
    clk, calls, lines = Clock(), [], []
    page = via_daum_page(cur, clk, lambda c: status, step=1.0)

    def f(code, d):
        calls.append(code)
        return page(code, d)
    alt = live_alt(cur, clk=clk, fetch_daum=f, lines=lines)
    assert alt["asked"] == 207 and alt["refNeed"] == NEED and V.px_alt_refuse_need(alt["asked"]) == NEED
    assert calls[:7] == list(V.MUST) and len(calls) == NEED                 # 필수 종목 먼저 · 21종목만 묻고 멈춰요
    assert (alt["refStop"], alt["ref"], alt["rskip"], alt["got"], alt["cut"], alt["no"], alt["net"]) == (True, NEED, 207 - NEED, 0, 0, 0, 0)
    assert alt["refMust"] == list(V.MUST) and alt["refEx"][0] == f"005930 HTTP {status}" and alt["noMust"] == [] and alt["noEx"] == []
    assert counted(alt) == alt["asked"]                                     # 종목마다 하나로만 세요
    loud = [x for x in lines if x.startswith("!! ")]
    assert len(loud) == 1 and loud[0].startswith(MOMENT) and f"답이 정해진 {NEED}종목이 모두 거절 (필수 종목 7 / 7" in loud[0]
    assert V.px_alt_was_refused(alt) and not V.px_alt_was_cut(alt)
    rep = check(cur, alt)
    assert not rep.failed, rep.table()
    r = rows(rep)
    assert r["pxDate 최종본 여부"][3] == "WARN" and "최종본 날짜 계산" not in r
    assert "다음이 거절해 건너뜀 (Jack 2026-11-21 · 배포만)" in r["pxDate 최종본 여부"][2]
    assert f"거절 {NEED}종목 (필수 종목 7 / 7 · 보기: 005930 HTTP {status}" in r["pxDate 최종본 여부"][2]
    assert f"거절 뒤 묻지 않음 {207 - NEED} · 확인 0 / 207종목" in r["pxDate 최종본 여부"][2]
    assert r["한국 가격 = 공식 종가"][3] == r["005930 = 공식 종가"][3] == "WARN"
    assert r["한국 가격 = 공식 종가"][1] == "비교 못 함" and "다음이 거절: 받은 종가 없음 · 건너뜀" in r["한국 가격 = 공식 종가"][2]
    assert "다음이 거절: 다음 값을 받지 못해 건너뜀" in r["005930 = 공식 종가"][2]


@pytest.mark.parametrize("kind", sorted(REFUSAL_EXC))
def test_deploy_skips_when_every_connection_is_refused(kind):
    """세 번 모두 연결 거부 · 끊김 · TLS 끊김 · 429 — 21종목 × 세 번 묻고 멈춰요 (네트워크 오류 몫이 아니라 거절 몫으로 세요)."""
    cur, _, _ = fb_files()
    clk, calls = Clock(), []
    alt = live_alt(cur, clk=clk, fetch_daum=raising(clk, REFUSAL_EXC[kind], calls, step=1.0))
    assert len(calls) == 3 * NEED and calls[:3] == ["005930"] * 3
    assert (alt["refStop"], alt["ref"], alt["rskip"], alt["got"], alt["cut"], alt["no"], alt["net"]) == (True, NEED, 207 - NEED, 0, 0, 0, 0)
    assert alt["refMust"] == list(V.MUST) and alt["netMust"] == [] and alt["err"] and counted(alt) == alt["asked"]
    rep = check(cur, alt)
    assert not rep.failed, (kind, rep.table())
    assert rows(rep)["pxDate 최종본 여부"][3] == "WARN" and "다음이 거절해 건너뜀" in rows(rep)["pxDate 최종본 여부"][2]


def test_a_retry_after_the_refusal_stop_is_not_sent():
    """멈춘 뒤에는 다시 묻기도 하지 않아요 (동시에 묻는 중이던 종목) — 그 종목은 '거절 뒤 묻지 않음' 으로 세요 · 쉬지도 않아요."""
    cur, _, _ = fb_files()
    order = list(V.MUST) + [c for c in sorted(V.px_alt_pick(cur["data"])) if c not in V.MUST]
    slow = order[7]                                                    # 표본 첫 종목: 한 번 거절된 뒤 다시 묻기 전에 멈춰요
    first_try = threading.Event()
    stopped = threading.Event()
    first2, lock, n = threading.Barrier(2), threading.Lock(), [0]
    lines, waits = [], []

    def f(code, d):
        with lock:
            n[0] += 1
            k = n[0]
        if k <= 2:                                                     # 처음 둘이 함께 기다려 일하는 스레드가 둘이 되게 해요
            first2.wait(10)
        if code == slow:
            if first_try.is_set():
                raise AssertionError("멈춘 뒤 다시 물었어요")
            first_try.set()
            stopped.wait(10)
            raise refused_exc()
        return None, "HTTP 403"

    def say(line):
        lines.append(line)
        if line.startswith(MOMENT):
            stopped.set()
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=f, workers=2, sleep=waits.append, say=say, budget_s=V.PX_ALT_LIVE_BUDGET_S)
    assert alt["refStop"] and alt["ref"] == NEED and slow not in alt["refMust"]
    assert alt["rskip"] == 207 - NEED and waits == [] and counted(alt) == alt["asked"]
    assert any(e == f"{slow}: {str(refused_exc())[:60]} (다음이 거절해 다시 묻지 않음)" for e in alt["err"]), alt["err"]
    assert not check(cur, alt).failed


# ── 3. 감시 (한도 없는 --live) · 발행 관문: 같은 거절에도 예전 그대로 ──────────────────────────────────
@pytest.mark.parametrize("kind", ["HTTP 403", "연결 거부", "HTTP 429"])
def test_the_watchdog_still_asks_everything_and_fails(kind):
    cur, _, _ = fb_files()
    clk, calls = Clock(), []
    f = (via_daum_page(cur, clk, lambda c: 403, step=1.0) if kind == "HTTP 403" else raising(clk, REFUSAL_EXC[kind], step=1.0))

    def g(code, d):
        calls.append(code)
        return f(code, d)
    alt = live_alt(cur, clk=clk, fetch_daum=g, budget_s=None)              # 감시 그대로 (한도 없음)
    assert alt["refNeed"] is None and not alt["refStop"] and alt["ref"] == alt["rskip"] == 0 and not V.px_alt_was_refused(alt)
    assert len(set(calls)) == alt["asked"] == 207 and alt["cut"] == 0
    if kind == "HTTP 403":                                                 # 403 은 예전 그대로 '다음이 분명히 답하지 않음'
        assert alt["no"] == 207 and alt["noMust"] == list(V.MUST) and alt["net"] == 0
    else:                                                                  # 연결 거부 · 429 는 예전 그대로 네트워크 오류
        assert alt["net"] == 207 and alt["netMust"] == list(V.MUST) and alt["no"] == 0 and len(calls) == 3 * 207
    rep = check(cur, alt)
    assert "최종본 날짜 계산" in failed(rep) and "pxDate 최종본 여부" not in rows(rep)


def test_the_daily_publish_gate_is_unchanged_by_refusals():
    cur, prev, old = fb_files()
    clk = Clock()
    alt = V.http_px_alt(cur["data"], PX, fetch=lambda s, d, close_time=None: (1000.0, "bar"),
                        fetch_daum=via_daum_page(cur, clk, lambda c: 403, step=1.0), workers=1, clock=clk, sleep=lambda s: None,
                        say=lambda s: None, budget_s=600)                  # 발행 관문은 한도를 받아도 쓰지 않아요 — 거절 규칙도 없어요
    assert alt["refNeed"] is None and not alt["refStop"] and alt["no"] == 207 and alt["limit"] is None
    assert "pxDate = 최종본 날짜" in failed(check(cur, alt, mode="publish", final=old, prev=prev))
    ok, why = V.px_alt_confirms(cur["data"], dict(alt, refStop=True, ref=NEED, refMust=list(V.MUST)), PX, old, "publish",
                                today=dt.date(2026, 10, 31), now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), special={}, cover=False)
    assert not ok and "건너뛸 수 있는 확인이 아니에요" in why


# ── 4. 일부만 거절 (거절이 아닌 답이 하나라도 먼저 옴): 예전 그대로 ─────────────────────────────────────
def test_a_partial_refusal_behaves_as_before():
    """005930 은 답하고 나머지는 403: 거절로 멈추지 않아요 → 모든 종목을 묻고, 403 은 예전 그대로 '분명히 답하지 않음' → 실패."""
    cur, _, _ = fb_files()
    clk, calls = Clock(), []
    page = via_daum_page(cur, clk, lambda c: 200 if c == "005930" else 403, step=1.0)

    def f(code, d):
        calls.append(code)
        return page(code, d)
    alt = live_alt(cur, clk=clk, fetch_daum=f)
    assert not alt["refStop"] and alt["ref"] == alt["rskip"] == 0 and len(calls) == 207
    assert (alt["got"], alt["no"], alt["net"], alt["cut"]) == (1, 206, 0, 0) and alt["noMust"] == list(V.MUST[1:])
    rep = check(cur, alt)
    assert "최종본 날짜 계산" in failed(rep) and "pxDate 최종본 여부" not in rows(rep)


def test_one_answer_before_the_count_is_reached_keeps_the_old_rule():
    """필수 7 과 표본 13 이 거절된 뒤 (20 < 21) 표본 하나가 답하면 그 실행에서는 거절로 멈추지 않아요 — 나머지 거절도 예전 그대로 세요."""
    cur, _, _ = fb_files()
    order = list(V.MUST) + [c for c in sorted(V.px_alt_pick(cur["data"])) if c not in V.MUST]
    alt = live_alt(cur, fetch_daum=answer_only(cur, {order[NEED - 1]}))
    assert not alt["refStop"] and alt["got"] == 1 and alt["net"] == 206 and alt["netMust"] == list(V.MUST) and alt["ref"] == 0
    assert "최종본 날짜 계산" in failed(check(cur, alt))
    # 답하는 종목이 22번째면 그 앞 21종목이 모두 거절이라 멈춰요 (그 종목은 묻지도 않아요) — 21 은 표본 기준을 이미 채울 수 없게 하는 수예요
    alt2 = live_alt(cur, fetch_daum=answer_only(cur, {order[NEED]}))
    assert alt2["refStop"] and alt2["ref"] == NEED and alt2["got"] == 0


def test_timeouts_5xx_dns_and_block_pages_are_not_refusals():
    """시간 초과 · 5xx · DNS · 인증서 · 프록시 · JSON 이 아닌 200 · 404 · 그날 행 없음은 거절이 아니에요 — 배포에서도 예전 그대로 (빨리 실패하면 실패)."""
    cur, _, _ = fb_files()
    kinds = {"503": lambda clk: via_daum_page(cur, clk, lambda c: 503, step=0.0),
             "html": lambda clk: via_daum_page(cur, clk, lambda c: "html", step=0.0),
             "404": lambda clk: via_daum_page(cur, clk, lambda c: 404, step=0.0),
             "norow": lambda clk: via_daum_page(cur, clk, lambda c: "norow", step=0.0),
             "timeout": lambda clk: raising(clk, lambda: requests.exceptions.ConnectTimeout("connect timed out"), step=0.0),
             "dns": lambda clk: raising(clk, dns_exc, step=0.0), "cert": lambda clk: raising(clk, cert_exc, step=0.0),
             "proxy": lambda clk: raising(clk, proxy_exc, step=0.0), "bare": lambda clk: raising(clk, lambda: ConnectionError("refused"), step=0.0)}
    for kind, make in kinds.items():
        clk = Clock()
        alt = live_alt(cur, clk=clk, fetch_daum=make(clk))
        assert not alt["refStop"] and alt["ref"] == alt["rskip"] == 0 and alt["cut"] == 0, kind
        assert alt["no"] + alt["net"] == 207, kind
        assert "최종본 날짜 계산" in failed(check(cur, alt)), kind


# ── 5. 받은 종가가 다르면: 거절로 건너뛰어도 예전과 같은 가격 줄이 실패 ─────────────────────────────────
def test_a_mismatch_among_mixed_answers_still_fails():
    cur, _, _ = fb_files()
    px = prices(cur)
    # (a) 005930 이 다른 종가로 답하고 나머지는 403 — 거절로 멈추지 않아요 (일부만 거절) → 예전 그대로 실패
    clk = Clock()
    alt = live_alt(cur, clk=clk, fetch_daum=lambda code, d: (px[code] + 100, "daum") if code == "005930" else (None, "HTTP 403"))
    assert not alt["refStop"] and alt["got"] == 1 and alt["closes"]["005930"] == px["005930"] + 100
    assert "최종본 날짜 계산" in failed(check(cur, alt))
    # (b) 표본 열 종목만 403 이고 나머지는 답하는데 005930 이 다름 — 예전 기준을 채워 비교 → '005930 = 공식 종가' 실패
    sample = [c for c in sorted(V.px_alt_pick(cur["data"])) if c not in V.MUST]
    refused = set(sample[:10])
    clk = Clock()
    alt = live_alt(cur, clk=clk, fetch_daum=lambda code, d: (None, "HTTP 403") if code in refused else (px[code] + (100 if code == "005930" else 0), "daum"))
    assert not alt["refStop"] and alt["got"] == 197 and alt["no"] == 10
    rep = check(cur, alt)
    assert "005930 = 공식 종가" in failed(rep) and rows(rep)["pxDate 최종본 여부"][3] == "PASS"


def in_flight_after_the_stop(cur, wrong):
    """동시 4: 표본 첫 세 종목은 거절로 멈춘 그 순간까지 기다렸다가 종가를 줘요 (wrong 에 있으면 1원 다르게) · 나머지는 모두 403.
    세 종목이 모두 묻는 중이 된 뒤에야 표본의 403 이 나가요 (멈추기 전에 셋 모두 물었게 — 스레드 순서에 기대지 않아요)."""
    order = list(V.MUST) + [c for c in sorted(V.px_alt_pick(cur["data"])) if c not in V.MUST]
    late3 = order[7:10]
    px = prices(cur)
    stopped, all3, lock = threading.Event(), threading.Event(), threading.Lock()
    first4, started3, n = threading.Barrier(4), set(), [0]
    lines = []

    def f(code, d):
        with lock:
            n[0] += 1
            k = n[0]
        if k <= 4:                                                     # 처음 넷이 함께 기다려 일하는 스레드가 넷이 되게 해요
            first4.wait(10)
        if code in late3:
            with lock:
                started3.add(code)
                if len(started3) == 3:
                    all3.set()
            stopped.wait(10)
            return px[code] + (1 if code in wrong(late3) else 0), "daum"
        if code not in V.MUST:
            all3.wait(10)
        return None, "HTTP 403"

    def say(line):
        lines.append(line)
        if line.startswith(MOMENT):
            stopped.set()
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=f, workers=4, sleep=lambda s: None, say=say, budget_s=V.PX_ALT_LIVE_BUDGET_S)
    assert stopped.is_set() and alt["refStop"] and alt["ref"] == NEED and alt["got"] == 3 and set(alt["closes"]) == set(late3)
    assert alt["rskip"] == 207 - NEED - 3 and counted(alt) == alt["asked"]
    return alt


def test_closes_that_arrive_after_the_stop_are_still_compared():
    """거절로 멈춘 뒤 받은 종가도 가격 줄에서 비교해요 (#157 의 기준 그대로 — 묻기로 한 207종목 기준 99%): 세 종목이 다르면 (207 - 3)/207 =
    98.6% 로 실패 — 다 받았어도 실패하는 경우예요. 한 종목이 다르면 (207 - 1)/207 = 99.5% 로 경고 — 다 받았어도 통과하는 경우예요."""
    cur, _, _ = fb_files()
    rep = check(cur, in_flight_after_the_stop(cur, wrong=lambda late3: set(late3)))
    r = rows(rep)
    assert "한국 가격 = 공식 종가" in failed(rep) and r["한국 가격 = 공식 종가"][1] == "98.6%", rep.table()
    assert "다음이 거절: 받은 3종목만 비교 · 다름 3 · 비율은 묻기로 한 207종목 기준" in r["한국 가격 = 공식 종가"][2]
    assert r["pxDate 최종본 여부"][3] == "WARN"                         # 건너뛴 것은 다음의 거절 몫뿐 — 다른 종가는 실패로 남아요
    rep = check(cur, in_flight_after_the_stop(cur, wrong=lambda late3: {late3[0]}))
    assert not rep.failed and rows(rep)["한국 가격 = 공식 종가"][3] == "WARN" and rows(rep)["한국 가격 = 공식 종가"][1] == "99.5%"


# ── 6. 다음이 분명히 '그날 종가 없음' 이라고 답한 필수 종목: 예전 그대로 실패 ───────────────────────────
@pytest.mark.parametrize("answer", ["norow", "html", 404])
def test_a_must_have_with_a_definite_non_answer_still_fails(answer):
    """나머지는 모두 403 이어도 005380 하나가 '그날 행 없음' · 차단 쪽 화면(JSON 이 아님) · 404 로 답하면 다음이 답한 거예요 — 거절로 멈추지
    않고 예전 그대로 실패해요."""
    cur, _, _ = fb_files()
    clk = Clock()
    alt = live_alt(cur, clk=clk, fetch_daum=via_daum_page(cur, clk, lambda c: answer if c == "005380" else 403, step=1.0))
    assert not alt["refStop"] and alt["ref"] == 0 and "005380" in alt["noMust"]
    rep = check(cur, alt)
    assert "최종본 날짜 계산" in failed(rep) and "005380" in rows(rep)["최종본 날짜 계산"][2]


def test_a_refusal_record_without_every_must_have_is_not_skipped():
    """거절로 멈췄다는 기록이어도 필수 종목이 모두 거절이 아니면 (예: 한 종목이 '그날 행 없음') 건너뛰지 않아요."""
    cur, _, _ = fb_files()
    clk = Clock()
    alt = live_alt(cur, clk=clk, fetch_daum=via_daum_page(cur, clk, lambda c: 403, step=1.0))
    assert V.px_alt_was_refused(alt) and not check(cur, alt).failed
    odd = dict(alt, refMust=list(V.MUST[1:]), ref=NEED - 1, no=1, noMust=["005930"], noEx=["005930 그날 행 0개"])
    assert not V.px_alt_was_refused(odd)
    assert "최종본 날짜 계산" in failed(check(cur, odd))
    for bad in (dict(alt, refStop=1), dict(alt, refStop="yes"), dict(alt, mode="publish"), dict(alt, ref=3)):
        assert not V.px_alt_was_refused(bad)
    hard, reach = V.px_alt_cut_gap(alt)
    assert hard == [] and reach == alt["asked"]
    hard, reach = V.px_alt_cut_gap(dict(alt, refStop=False))           # 멈추지 않은 기록이면 예전 그대로 (거절 몫을 설명해 주지 않아요)
    assert hard == list(V.MUST) and reach == 0


# ── 7. main: 배포의 관문 (끝 코드 · 로그 '!!' 두 줄 · 실행 요약 · GitHub 경고) · 감시는 예전 그대로 ───────────────────
def run_main(monkeypatch, capsys, tmp_path, cur, make, deploy=True):
    files = {k: cur[k] for k in ("data", "corp", "disc", "macro")}
    monkeypatch.setattr(V, "load_dir", lambda d: files)
    monkeypatch.setattr(V, "http_listing", lambda d: None)                # 캐시에 pxDate 최종본 없음
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: hilo_of(cur, V.MUST))
    seen = []

    def alt_fn(data, px, special=None, mode="publish", **kw):
        seen.append((mode, kw))
        clk = Clock()
        return REAL_HTTP_PX_ALT(data, px, special=special, mode=mode, fetch_daum=make(clk), workers=1, clock=clk, sleep=lambda s: None, **kw)
    monkeypatch.setattr(V, "http_px_alt", alt_fn)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    if deploy:
        monkeypatch.setenv(V.PX_ALT_LIMIT_ENV, str(V.PX_ALT_LIVE_BUDGET_S))
    else:
        monkeypatch.delenv(V.PX_ALT_LIMIT_ENV, raising=False)
    code = V.main(["--live", "--dir", "unused", "--today", "2026-10-31"])
    out = capsys.readouterr().out
    assert seen == [("live", {"budget_s": 600.0} if deploy else {})]
    return code, out, summary.read_text(encoding="utf-8")


def test_main_deploy_refusal_exits_0_with_a_loud_warning(monkeypatch, capsys, tmp_path):
    cur, _, _ = fb_files()
    code, out, summ = run_main(monkeypatch, capsys, tmp_path, cur, lambda clk: via_daum_page(cur, clk, lambda c: 403, step=1.0))
    assert code == 0, out
    assert "· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 일별 시세 + 발행 기록): 207종목 · 동시 1 · 시간 한도 600초" in out
    assert f"{MOMENT} — 답이 정해진 {NEED}종목이 모두 거절 (필수 종목 7 / 7 · 보기: 005930 HTTP 403" in out          # 그 순간
    after = next(ln for ln in out.splitlines() if ln.startswith(AFTER))                                              # 끝난 뒤
    assert f"거절 {NEED}종목 (필수 종목 7 / 7 · 보기: 005930 HTTP 403" in after and f"거절 뒤 묻지 않음 {207 - NEED}" in after
    assert "다음의 확인을 건너뛰고 경고 ('pxDate 최종본 여부' 줄)" in after and "시간 한도에 걸렸어요" not in out
    assert "결과: PASS" in out and "!! 경고  pxDate 최종본 여부: 2026-10-30" in out
    warns = [ln for ln in out.splitlines() if ln.startswith("::warning title=발행 관문 경고::")]
    assert any("pxDate 최종본 여부" in ln and "다음이 거절해 건너뜀" in ln for ln in warns)      # 매일 아침 점검이 읽어요
    assert "::error" not in out
    assert "### 뱁새 발행 관문 — PASS (live)" in summ and "다음이 거절해 건너뜀 (Jack 2026-11-21 · 배포만)" in summ   # 실행 요약 표
    assert "2차 출처 관문 기준 (야후): 다음이 거절해 확인을 건너뜀 (경고)" in out


def test_main_deploy_refusal_with_a_wrong_close_still_fails(monkeypatch, capsys, tmp_path):
    """거절과 섞여 다른 종가가 오면 (일부만 거절) 예전 그대로 실패해요 — main 끝 코드 1."""
    cur, _, _ = fb_files()
    px = prices(cur)

    def make(clk):
        return lambda code, d: (px[code] + 100, "daum") if code == "005930" else (None, "HTTP 403")
    code, out, _ = run_main(monkeypatch, capsys, tmp_path, cur, make)
    assert code == 1 and MOMENT not in out and AFTER not in out and "!! FAIL  최종본 날짜 계산" in out


def test_main_watchdog_refusal_fails_as_before(monkeypatch, capsys, tmp_path):
    cur, _, _ = fb_files()
    code, out, summ = run_main(monkeypatch, capsys, tmp_path, cur, lambda clk: via_daum_page(cur, clk, lambda c: 403, step=1.0), deploy=False)
    assert code == 1 and MOMENT not in out and AFTER not in out
    assert "시간 한도 없음 (예전 그대로)" in out and "!! FAIL  최종본 날짜 계산" in out and "### 뱁새 발행 관문 — FAIL (live)" in summ
