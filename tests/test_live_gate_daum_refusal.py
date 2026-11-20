# -*- coding: utf-8 -*-
"""2026-11-21 (Jack, 11-20 질문 3, 그대로): "Deploy price check when Daum refuses instead of being slow. Your 10-minute limit covers a slow
Daum. If Daum starts refusing GitHub's servers outright, the way KRX did, nothing times out, and every code deploy stops until Daum answers
again. Skip the Daum check in that case too, with the same loud warning? It loosens a check, so it's yours. (Recommended: yes, for code
deploys only. The daily data publish keeps its own two-source checks either way.)" → 11-21 "3. Yes." (바깥 네트워크 없음 · 몇 시험은 이
컴퓨터 안의 포트에 진짜로 물어요)

이 시험은 (새 파일 · 다른 시험은 고치지 않았어요):
- 거절의 뜻 (px_refusal_answer · px_refusal_error): HTTP 401 · 403 · 451, 세 번 모두 연결 거부 · 연결 끊김 · 상대가 TLS 를 끊음 · 상대의 거절
  TLS 경보 · HTTP 429 — 시간 초과 · 5xx · DNS · 프록시 · 우리 쪽 OpenSSL 이 거절한 TLS · 인증서 · JSON 이 아닌 200 · 404 · 그날 행 없음은
  거절이 아니에요. 보기에는 짧은 이름 (HTTP 403 · ConnectionRefusedError · SSLEOFError …);
- 코드 배포만 (한도 + PX_ALT_REFUSE_ENV=1 · deploy.yml 은 workflow_run 이 아닐 때만 1): 답이 정해진 종목이 모두 거절이고 필수 종목이 모두
  그 안에 있고 그 수가 px_alt_refuse_need (207종목이면 21) 에 닿으면 더 묻지 않고, 시간 한도와 같은 줄을 경고로 바꿔 배포가 다른 검사로
  계속해요 (로그 '!!' 두 줄 · 실행 요약 표 · GitHub 경고 알림);
- 데이터 실행 뒤 배포 (한도만 · 스위치 0) · 감시 (한도 없는 --live) · 발행 관문은 같은 거절에도 예전 그대로 실패해요;
- 일부만 거절 (거절이 아닌 답이 하나라도 먼저 옴) 은 예전 그대로예요;
- 받은 종가가 발행 가격과 다르면 예전과 같은 가격 줄이 실패해요 (#157 의 기준 그대로) · 다음이 분명히 '그날 종가 없음' 이라고 답한 필수
  종목은 예전 그대로 실패해요.
"""
import datetime as dt
import http.client
import os
import socket
import ssl
import sys
import threading

import pytest
import requests
import urllib3
import yaml

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
AFTER = "!! 관문의 두 출처 확인을 다음이 거절했어요 (Jack 2026-11-21 · 코드 배포만)"
WARN_HOW = "다음이 거절해 건너뜀 (Jack 2026-11-21 · 코드 배포만)"
CODE_DEPLOY_EXPR = "${{ github.event_name != 'workflow_run' && '1' || '0' }}"


def deploy_alt(cur, **k):
    """코드 배포의 관문처럼 (한도 600초 + 거절로 건너뛰기 켜짐)."""
    return live_alt(cur, refuse_skip=True, **k)


# ── 진짜와 같은 꼴의 예외 (requests 가 urllib3 · 소켓 · ssl 오류를 감싸는 꼴 그대로 — 이 컴퓨터에서 본 꼴) ─────────────────────
def wrap_ssl(inner):
    return requests.exceptions.SSLError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=urllib3.exceptions.SSLError(inner)))


def ssl_reason(reason):
    return ssl.SSLError(1, f"[SSL: {reason}] {reason.lower().replace('_', ' ')} (_ssl.c:1032)")


def refused_exc():
    nce = urllib3.exceptions.NewConnectionError(None, "Failed to establish a new connection: [Errno 111] Connection refused")
    nce.__cause__ = ConnectionRefusedError(111, "Connection refused")
    return requests.ConnectionError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=nce))


def reset_exc():
    return requests.ConnectionError(urllib3.exceptions.ProtocolError("Connection aborted.", ConnectionResetError(104, "Connection reset by peer")))


def closed_exc():
    return requests.ConnectionError(urllib3.exceptions.ProtocolError(
        "Connection aborted.", http.client.RemoteDisconnected("Remote end closed connection without response")))


def tls_eof_exc():
    return wrap_ssl(ssl.SSLEOFError(8, "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)"))


def tls_zero_exc():
    return wrap_ssl(ssl.SSLZeroReturnError(6, "TLS/SSL connection has been closed (EOF) (_ssl.c:1032)"))


def cert_exc():
    return wrap_ssl(ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"))


def dns_exc():
    nre = urllib3.exceptions.NameResolutionError("finance.daum.net", None, socket.gaierror(-3, "Temporary failure in name resolution"))
    return requests.ConnectionError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=nre))


def proxy_exc():
    nce = urllib3.exceptions.NewConnectionError(None, "Connection refused")
    nce.__cause__ = ConnectionRefusedError(111, "Connection refused")
    return requests.exceptions.ProxyError(urllib3.exceptions.MaxRetryError(None, "/api/quote", reason=nce))


# 거절 → 보기에 남는 짧은 이름
REFUSAL_EXC = {"연결 거부": (refused_exc, "ConnectionRefusedError"), "연결 끊김 (reset)": (reset_exc, "ConnectionResetError"),
               "응답 없이 닫음": (closed_exc, "RemoteDisconnected"), "TLS 끊김 (EOF)": (tls_eof_exc, "SSLEOFError"),
               "TLS 닫음": (tls_zero_exc, "SSLZeroReturnError"),
               "TLS 경보 access denied": (lambda: wrap_ssl(ssl_reason("TLSV1_ALERT_ACCESS_DENIED")), "SSLError TLSV1_ALERT_ACCESS_DENIED"),
               "HTTP 429": (lambda: requests.HTTPError("429 Client Error: Too Many Requests", response=FakeResp(429)), "HTTP 429")}
# 우리 쪽 OpenSSL 이 스스로 거절했거나 (리뷰 2026-11-21) 상대의 고장 경보 — 거절이 아니에요
LOCAL_TLS = ("WRONG_VERSION_NUMBER", "UNSAFE_LEGACY_RENEGOTIATION_DISABLED", "DH_KEY_TOO_SMALL", "HANDSHAKE_FAILURE",
             "UNSUPPORTED_PROTOCOL", "TLSV1_ALERT_INTERNAL_ERROR", "SSLV3_ALERT_BAD_RECORD_MAC", "CERTIFICATE_VERIFY_FAILED")


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
    yes = [make() for make, _ in REFUSAL_EXC.values()] + [
        ConnectionRefusedError(111, "x"), ConnectionResetError(104, "x"), ConnectionAbortedError("x"), BrokenPipeError("x"),
        requests.HTTPError("429 Client Error")] + [wrap_ssl(ssl_reason(r)) for r in V.PX_REFUSE_TLS_ALERTS]
    no = [requests.Timeout("x"), requests.exceptions.ReadTimeout("x"), requests.exceptions.ConnectTimeout("x"), TimeoutError("read timed out"),
          cert_exc(), dns_exc(), proxy_exc(), ConnectionError("refused"), requests.ConnectionError("x"),
          requests.HTTPError("x", response=FakeResp(500)), requests.HTTPError("x", response=FakeResp(503)), requests.HTTPError("502 err"),
          requests.HTTPError("x", response=FakeResp(403)), requests.HTTPError("x", response=FakeResp(404)),
          requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0), ValueError("Expecting value"), KeyError("data"), RuntimeError("x")]
    assert all(V.px_refusal_error(e) for e in yes), [e for e in yes if not V.px_refusal_error(e)]
    assert not any(V.px_refusal_error(e) for e in no), [e for e in no if V.px_refusal_error(e)]
    assert all(V.px_net_error(e) for e in yes if not isinstance(e, ssl.SSLError))   # 거절은 #157 의 네트워크 오류 안이에요 (새 갈래가 아니에요)


@pytest.mark.parametrize("reason", LOCAL_TLS)
def test_tls_errors_our_own_client_raises_are_not_refusals(reason):
    """리뷰 2026-11-21 (반드시): 우리 쪽 OpenSSL 이 다음을 거절한 것 (WRONG_VERSION_NUMBER · UNSAFE_LEGACY_RENEGOTIATION_DISABLED ·
    DH_KEY_TOO_SMALL · HANDSHAKE_FAILURE …) 과 상대의 고장 경보는 거절이 아니에요 — 감싼 꼴 · 그대로 · 거절 쪽 오류와 섞여도."""
    e = ssl_reason(reason)
    assert not V.px_refusal_error(wrap_ssl(e)) and not V.px_refusal_error(e)
    mixed = requests.ConnectionError(urllib3.exceptions.ProtocolError("Connection aborted.", ConnectionResetError(104, "reset")))
    mixed.__context__ = e
    assert not V.px_refusal_error(mixed)                               # 안에 우리 쪽 TLS 오류가 하나라도 있으면 거절이 아니에요


@pytest.mark.parametrize("reason", V.PX_REFUSE_TLS_ALERTS)
def test_tls_alerts_sent_by_daum_are_refusals(reason):
    assert V.px_refusal_error(wrap_ssl(ssl_reason(reason))) and V.px_refusal_name(wrap_ssl(ssl_reason(reason))) == f"SSLError {reason}"
    assert V.px_refusal_error(tls_eof_exc()) and V.px_refusal_error(tls_zero_exc())


def test_real_tls_errors_from_this_machine():
    """이 컴퓨터 안에서 진짜 TLS 오류를 만들어요 (인증서 없이): 상대가 TLS 1.3 만 받아 보낸 protocol_version 경보는 거절 · TLS 가 아닌
    서버에 TLS 로 물었을 때 우리 OpenSSL 이 내는 WRONG_VERSION_NUMBER 는 거절이 아니에요."""
    def serve(handle):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)

        def run():
            c, _ = s.accept()
            try:
                handle(c)
            except Exception:
                pass
            finally:
                c.close()
                s.close()
        threading.Thread(target=run, daemon=True).start()
        return s.getsockname()[1]

    def tls13_only(c):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.wrap_socket(c, server_side=True)

    def plain_http(c):
        c.recv(4096)
        c.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")

    def client_error(port, max_tls=None):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        if max_tls:
            ctx.maximum_version = max_tls
        with socket.create_connection(("127.0.0.1", port), timeout=5) as so:
            with pytest.raises(ssl.SSLError) as ei:
                ctx.wrap_socket(so)
        return ei.value
    alert = client_error(serve(tls13_only), ssl.TLSVersion.TLSv1_2)
    assert alert.reason == "TLSV1_ALERT_PROTOCOL_VERSION" and V.px_refusal_error(wrap_ssl(alert))
    local = client_error(serve(plain_http))
    assert local.reason == "WRONG_VERSION_NUMBER" and not V.px_refusal_error(wrap_ssl(local))


def test_refusal_names_are_short():
    """리뷰 2026-11-21: 보기에는 가장 안쪽 까닭의 짧은 이름 (겉 글 'HTTPSConnectionPool(host=…' 는 40자에서 잘려 까닭이 보이지 않았어요)."""
    for kind, (make, name) in REFUSAL_EXC.items():
        e = make()
        assert V.px_refusal_name(e) == name, kind
        assert len(name) <= 60, kind
    assert all(len(f"SSLError {r}") <= 60 for r in V.PX_REFUSE_TLS_ALERTS)   # 기록이 잘리지 않아요 (거절 까닭은 60자까지 남겨요)
    for make in (refused_exc, reset_exc, tls_eof_exc):                 # 겉 글의 앞 40자에는 까닭이 없어요 (예전 보기)
        assert not any(w in str(make())[:40] for w in ("refused", "reset", "EOF")), str(make())[:40]


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
    assert V.px_refusal_error(ei.value) and V.px_net_error(ei.value) and V.px_refusal_name(ei.value) == "ConnectionRefusedError"


# ── 2. 코드 배포 (한도 + 스위치): 거절이면 그만 묻고 경고로 건너뛰어요 ─────────────────────────────────────
@pytest.mark.parametrize("status", [403, 401, 451])
def test_code_deploy_skips_when_daum_answers_access_refused(status):
    cur, _, _ = fb_files()
    clk, calls, lines = Clock(), [], []
    page = via_daum_page(cur, clk, lambda c: status, step=1.0)

    def f(code, d):
        calls.append(code)
        return page(code, d)
    alt = deploy_alt(cur, clk=clk, fetch_daum=f, lines=lines)
    assert alt["asked"] == 207 and alt["refNeed"] == NEED and V.px_alt_refuse_need(alt["asked"]) == NEED
    assert calls[:7] == list(V.MUST) and len(calls) == NEED                 # 필수 종목 먼저 · 21종목만 묻고 멈춰요 (동시 1)
    assert (alt["refStop"], alt["ref"], alt["rskip"], alt["got"], alt["cut"], alt["no"], alt["net"]) == (True, NEED, 207 - NEED, 0, 0, 0, 0)
    assert alt["refMust"] == list(V.MUST) and alt["refEx"][0] == f"005930 HTTP {status}" and alt["noMust"] == [] and alt["noEx"] == []
    assert counted(alt) == alt["asked"]                                     # 종목마다 하나로만 세요
    assert lines[0].endswith(" · 다음이 거절하면 (답이 정해진 21종목 이상이 모두 거절 · 필수 종목 모두) 그만 묻고 경고로 건너뛰어요 (코드 배포만)")
    loud = [x for x in lines if x.startswith("!! ")]
    assert len(loud) == 1 and loud[0].startswith(MOMENT) and f"답이 정해진 {NEED}종목이 모두 거절 (필수 종목 7 / 7" in loud[0]
    assert V.px_alt_was_refused(alt) and not V.px_alt_was_cut(alt)
    rep = check(cur, alt)
    assert not rep.failed, rep.table()
    r = rows(rep)
    assert r["pxDate 최종본 여부"][3] == "WARN" and "최종본 날짜 계산" not in r
    assert WARN_HOW in r["pxDate 최종본 여부"][2]
    assert f"거절 {NEED}종목 (필수 종목 7 / 7 · 보기: 005930 HTTP {status}" in r["pxDate 최종본 여부"][2]
    assert f"거절 뒤 묻지 않음 {207 - NEED} · 확인 0 / 207종목" in r["pxDate 최종본 여부"][2]
    assert r["한국 가격 = 공식 종가"][3] == r["005930 = 공식 종가"][3] == "WARN"
    assert r["한국 가격 = 공식 종가"][1] == "비교 못 함" and "다음이 거절: 받은 종가 없음 · 건너뜀" in r["한국 가격 = 공식 종가"][2]
    assert "다음이 거절: 다음 값을 받지 못해 건너뜀" in r["005930 = 공식 종가"][2]


@pytest.mark.parametrize("kind", sorted(REFUSAL_EXC))
def test_code_deploy_skips_when_every_connection_is_refused(kind):
    """세 번 모두 연결 거부 · 끊김 · TLS 끊김 · 상대의 거절 경보 · 429 — 21종목 × 세 번 묻고 멈춰요 (네트워크 오류 몫이 아니라 거절 몫으로
    세요) · 보기는 짧은 이름."""
    make, name = REFUSAL_EXC[kind]
    cur, _, _ = fb_files()
    clk, calls = Clock(), []
    alt = deploy_alt(cur, clk=clk, fetch_daum=raising(clk, make, calls, step=1.0))
    assert len(calls) == 3 * NEED and calls[:3] == ["005930"] * 3
    assert (alt["refStop"], alt["ref"], alt["rskip"], alt["got"], alt["cut"], alt["no"], alt["net"]) == (True, NEED, 207 - NEED, 0, 0, 0, 0)
    assert alt["refMust"] == list(V.MUST) and alt["netMust"] == [] and alt["err"] and counted(alt) == alt["asked"]
    assert alt["refEx"][0] == f"005930 {name}"
    rep = check(cur, alt)
    assert not rep.failed, (kind, rep.table())
    r = rows(rep)["pxDate 최종본 여부"]
    assert r[3] == "WARN" and WARN_HOW in r[2] and f"보기: 005930 {name}" in r[2]


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
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=f, workers=2, sleep=waits.append, say=say, budget_s=V.PX_ALT_LIVE_BUDGET_S,
                        refuse_skip=True)
    assert alt["refStop"] and alt["ref"] == NEED and slow not in alt["refMust"]
    assert alt["rskip"] == 207 - NEED and waits == [] and counted(alt) == alt["asked"]
    assert any(e == f"{slow}: {str(refused_exc())[:60]} (다음이 거절해 다시 묻지 않음)" for e in alt["err"]), alt["err"]
    assert not check(cur, alt).failed


# ── 3. 데이터 실행 뒤 배포 · 감시 · 발행 관문: 같은 거절에도 예전 그대로 ──────────────────────────────────
@pytest.mark.parametrize("kind", ["HTTP 403", "연결 거부", "HTTP 429"])
@pytest.mark.parametrize("where", ["데이터 실행 뒤 배포 (한도만)", "감시 (한도 없음)", "감시 + 스위치 (한도 없음)"])
def test_without_the_code_deploy_switch_refusals_fail_as_before(kind, where):
    cur, _, _ = fb_files()
    clk, calls = Clock(), []
    f = (via_daum_page(cur, clk, lambda c: 403, step=0.0) if kind == "HTTP 403" else raising(clk, REFUSAL_EXC[kind][0]))   # 빨리 거절 (시간 한도 전)

    def g(code, d):
        calls.append(code)
        return f(code, d)
    k = {"데이터 실행 뒤 배포 (한도만)": {}, "감시 (한도 없음)": {"budget_s": None},
         "감시 + 스위치 (한도 없음)": {"budget_s": None, "refuse_skip": True}}[where]
    alt = live_alt(cur, clk=clk, fetch_daum=g, **k)
    assert alt["refNeed"] is None and not alt["refStop"] and alt["ref"] == alt["rskip"] == 0 and not V.px_alt_was_refused(alt)
    assert len(set(calls)) == alt["asked"] == 207 and alt["cut"] == 0
    if kind == "HTTP 403":                                                 # 403 은 예전 그대로 '다음이 분명히 답하지 않음'
        assert alt["no"] == 207 and alt["noMust"] == list(V.MUST) and alt["net"] == 0
    else:                                                                  # 연결 거부 · 429 는 예전 그대로 네트워크 오류
        assert alt["net"] == 207 and alt["netMust"] == list(V.MUST) and alt["no"] == 0 and len(calls) == 3 * 207
    rep = check(cur, alt)
    assert "최종본 날짜 계산" in failed(rep) and "pxDate 최종본 여부" not in rows(rep), (where, kind, rep.table())


def test_the_daily_publish_gate_is_unchanged_by_refusals():
    cur, prev, old = fb_files()
    clk = Clock()
    alt = V.http_px_alt(cur["data"], PX, fetch=lambda s, d, close_time=None: (1000.0, "bar"),
                        fetch_daum=via_daum_page(cur, clk, lambda c: 403, step=1.0), workers=1, clock=clk, sleep=lambda s: None,
                        say=lambda s: None, budget_s=600, refuse_skip=True)   # 발행 관문은 한도 · 스위치를 받아도 쓰지 않아요
    assert alt["refNeed"] is None and not alt["refStop"] and alt["no"] == 207 and alt["limit"] is None
    assert "pxDate = 최종본 날짜" in failed(check(cur, alt, mode="publish", final=old, prev=prev))
    ok, why = V.px_alt_confirms(cur["data"], dict(alt, refStop=True, ref=NEED, refNeed=NEED, refMust=list(V.MUST)), PX, old, "publish",
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
    alt = deploy_alt(cur, clk=clk, fetch_daum=f)
    assert not alt["refStop"] and alt["ref"] == alt["rskip"] == 0 and len(calls) == 207
    assert (alt["got"], alt["no"], alt["net"], alt["cut"]) == (1, 206, 0, 0) and alt["noMust"] == list(V.MUST[1:])
    rep = check(cur, alt)
    assert "최종본 날짜 계산" in failed(rep) and "pxDate 최종본 여부" not in rows(rep)


def test_one_answer_before_the_count_is_reached_keeps_the_old_rule():
    """필수 7 과 표본 13 이 거절된 뒤 (20 < 21) 표본 하나가 답하면 그 실행에서는 거절로 멈추지 않아요 — 나머지 거절도 예전 그대로 세요."""
    cur, _, _ = fb_files()
    order = list(V.MUST) + [c for c in sorted(V.px_alt_pick(cur["data"])) if c not in V.MUST]
    alt = deploy_alt(cur, fetch_daum=answer_only(cur, {order[NEED - 1]}))
    assert not alt["refStop"] and alt["got"] == 1 and alt["net"] == 206 and alt["netMust"] == list(V.MUST) and alt["ref"] == 0
    assert "최종본 날짜 계산" in failed(check(cur, alt))
    # 답하는 종목이 22번째면 그 앞 21종목이 모두 거절이라 멈춰요 (그 종목은 묻지도 않아요) — 21 은 표본 기준을 이미 채울 수 없게 하는 수예요
    alt2 = deploy_alt(cur, fetch_daum=answer_only(cur, {order[NEED]}))
    assert alt2["refStop"] and alt2["ref"] == NEED and alt2["got"] == 0


def test_timeouts_5xx_dns_tls_and_block_pages_are_not_refusals():
    """시간 초과 · 5xx · DNS · 인증서 · 우리 쪽 TLS · 프록시 · JSON 이 아닌 200 · 404 · 그날 행 없음은 거절이 아니에요 — 코드 배포에서도 예전
    그대로 (빨리 실패하면 실패)."""
    cur, _, _ = fb_files()
    kinds = {"503": lambda clk: via_daum_page(cur, clk, lambda c: 503, step=0.0),
             "html": lambda clk: via_daum_page(cur, clk, lambda c: "html", step=0.0),
             "404": lambda clk: via_daum_page(cur, clk, lambda c: 404, step=0.0),
             "norow": lambda clk: via_daum_page(cur, clk, lambda c: "norow", step=0.0),
             "timeout": lambda clk: raising(clk, lambda: requests.exceptions.ConnectTimeout("connect timed out")),
             "dns": lambda clk: raising(clk, dns_exc), "cert": lambda clk: raising(clk, cert_exc),
             "wrong version": lambda clk: raising(clk, lambda: wrap_ssl(ssl_reason("WRONG_VERSION_NUMBER"))),
             "proxy": lambda clk: raising(clk, proxy_exc), "bare": lambda clk: raising(clk, lambda: ConnectionError("refused"))}
    for kind, make in kinds.items():
        clk = Clock()
        alt = deploy_alt(cur, clk=clk, fetch_daum=make(clk))
        assert not alt["refStop"] and alt["ref"] == alt["rskip"] == 0 and alt["cut"] == 0, kind
        assert alt["no"] + alt["net"] == 207, kind
        assert "최종본 날짜 계산" in failed(check(cur, alt)), kind


# ── 5. 받은 종가가 다르면: 거절로 건너뛰어도 예전과 같은 가격 줄이 실패 ─────────────────────────────────
def test_a_mismatch_among_mixed_answers_still_fails():
    cur, _, _ = fb_files()
    px = prices(cur)
    # (a) 005930 이 다른 종가로 답하고 나머지는 403 — 거절로 멈추지 않아요 (일부만 거절) → 예전 그대로 실패
    alt = deploy_alt(cur, fetch_daum=lambda code, d: (px[code] + 100, "daum") if code == "005930" else (None, "HTTP 403"))
    assert not alt["refStop"] and alt["got"] == 1 and alt["closes"]["005930"] == px["005930"] + 100
    assert "최종본 날짜 계산" in failed(check(cur, alt))
    # (b) 표본 열 종목만 403 이고 나머지는 답하는데 005930 이 다름 — 예전 기준을 채워 비교 → '005930 = 공식 종가' 실패
    sample = [c for c in sorted(V.px_alt_pick(cur["data"])) if c not in V.MUST]
    refused = set(sample[:10])
    alt = deploy_alt(cur, fetch_daum=lambda code, d: (None, "HTTP 403") if code in refused else (px[code] + (100 if code == "005930" else 0), "daum"))
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
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=f, workers=4, sleep=lambda s: None, say=say, budget_s=V.PX_ALT_LIVE_BUDGET_S,
                        refuse_skip=True)
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
    alt = deploy_alt(cur, clk=clk, fetch_daum=via_daum_page(cur, clk, lambda c: answer if c == "005380" else 403, step=1.0))
    assert not alt["refStop"] and alt["ref"] == 0 and "005380" in alt["noMust"]
    rep = check(cur, alt)
    assert "최종본 날짜 계산" in failed(rep) and "005380" in rows(rep)["최종본 날짜 계산"][2]


def test_a_refusal_record_is_read_strictly():
    """거절로 멈췄다는 기록이어도 필수 종목이 모두 거절이 아니거나, 거절 수가 refNeed 에 못 미치거나, refNeed 가 없으면 건너뛰지 않아요."""
    cur, _, _ = fb_files()
    clk = Clock()
    alt = deploy_alt(cur, clk=clk, fetch_daum=via_daum_page(cur, clk, lambda c: 403, step=1.0))
    assert V.px_alt_was_refused(alt) and not check(cur, alt).failed
    odd = dict(alt, refMust=list(V.MUST[1:]), ref=NEED - 1, no=1, noMust=["005930"], noEx=["005930 그날 행 0개"])
    assert not V.px_alt_was_refused(odd)
    assert "최종본 날짜 계산" in failed(check(cur, odd))
    for bad in (dict(alt, refStop=1), dict(alt, refStop="yes"), dict(alt, mode="publish"), dict(alt, ref=3), dict(alt, ref=NEED - 1),
                dict(alt, refNeed=None), dict(alt, refNeed=True), dict(alt, refNeed=3, ref=5), dict(alt, refNeed="21")):
        assert not V.px_alt_was_refused(bad), bad
        assert "최종본 날짜 계산" in failed(check(cur, bad))
    hard, reach = V.px_alt_cut_gap(alt)
    assert hard == [] and reach == alt["asked"]
    hard, reach = V.px_alt_cut_gap(dict(alt, refStop=False))           # 멈추지 않은 기록이면 예전 그대로 (거절 몫을 설명해 주지 않아요)
    assert hard == list(V.MUST) and reach == 0


def test_the_start_line_names_the_rule_only_when_it_is_on():
    cur, _, _ = fb_files()
    base = "· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 일별 시세 + 발행 기록): 207종목 · 동시 1 · 시간 한도 600초 (배포 — 넘으면 새로 묻지 않고, 시간 한도로 못 받은 부분만 경고로 건너뛰어요)"
    for k, want in (({}, base), ({"refuse_skip": True}, base + " · 다음이 거절하면 (답이 정해진 21종목 이상이 모두 거절 · 필수 종목 모두) 그만 묻고 "
                                                             "경고로 건너뛰어요 (코드 배포만)")):
        lines = []
        live_alt(cur, step=0.0, lines=lines, **k)
        assert lines == [want], k


# ── 7. 스위치는 코드 배포에만: deploy.yml · 감시 · main ───────────────────────────────────────────
def test_the_switch_is_on_for_code_deploys_only():
    """deploy.yml 의 관문 단계만 스위치를 줘요 — push · 손으로 (코드 배포) 는 1, 데이터 실행 바로 뒤의 배포 (workflow_run) 는 0. 한도 (#157)
    는 예전 그대로 모든 배포에."""
    wfd = os.path.join(ROOT, ".github", "workflows")
    raw = open(os.path.join(wfd, "deploy.yml"), encoding="utf-8").read()
    wf = yaml.safe_load(raw)
    on = wf.get("on", wf.get(True))
    assert set(on) == {"push", "workflow_run", "workflow_dispatch"}    # 배포의 계기 셋 — 그중 workflow_run 만 데이터 실행 뒤예요
    gates = [s for j in wf["jobs"].values() for s in j.get("steps", []) if V.PX_ALT_REFUSE_ENV in (s.get("env") or {})]
    assert len(gates) == 1 and gates[0]["name"] == "발행 관문 (validate_data.py --live, 올릴 파일 그대로)"
    assert gates[0]["env"][V.PX_ALT_REFUSE_ENV] == CODE_DEPLOY_EXPR
    assert gates[0]["env"][V.PX_ALT_LIMIT_ENV] == "600"                 # 시간 한도는 예전 그대로 모든 배포에
    assert raw.count(V.PX_ALT_REFUSE_ENV) == 1 and "--daum-refuse-skip" not in raw
    assert V.PX_ALT_REFUSE_ENV not in (wf.get("env") or {}) and all(V.PX_ALT_REFUSE_ENV not in (j.get("env") or {}) for j in wf["jobs"].values())
    for name in sorted(os.listdir(wfd)):
        if name != "deploy.yml":
            text = open(os.path.join(wfd, name), encoding="utf-8").read()
            assert V.PX_ALT_REFUSE_ENV not in text and "daum-refuse-skip" not in text, name
    for name in ("watchdog.py", "fetch_data.py"):
        text = open(os.path.join(ROOT, name), encoding="utf-8").read()
        assert V.PX_ALT_REFUSE_ENV not in text and "daum-refuse-skip" not in text and "refuse_skip" not in text, name


def test_the_watchdog_drops_the_switch(monkeypatch, tmp_path):
    import watchdog as W
    monkeypatch.setenv(V.PX_ALT_REFUSE_ENV, "1")
    monkeypatch.setenv(V.PX_ALT_LIMIT_ENV, "600")
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw["env"]
        with open(kw["env"]["GITHUB_STEP_SUMMARY"], "w", encoding="utf-8") as f:
            f.write("표")

        class R:
            returncode, stdout, stderr = 0, "", ""
        return R()
    W.run_live_gate(str(tmp_path), run=fake_run)
    assert seen["cmd"][2:] == ["--live", "--dir", str(tmp_path)]
    assert V.PX_ALT_REFUSE_ENV not in seen["env"] and V.PX_ALT_LIMIT_ENV not in seen["env"]


def run_main(monkeypatch, capsys, tmp_path, cur, make, deploy="code", argv=()):
    """deploy: 'code' (한도 + 스위치 1 — push · 손으로) · 'data' (한도 + 스위치 0 — workflow_run) · 'watchdog' (둘 다 없음)."""
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
    monkeypatch.delenv(V.PX_ALT_LIMIT_ENV, raising=False)
    monkeypatch.delenv(V.PX_ALT_REFUSE_ENV, raising=False)
    if deploy in ("code", "data"):
        monkeypatch.setenv(V.PX_ALT_LIMIT_ENV, str(V.PX_ALT_LIVE_BUDGET_S))
        monkeypatch.setenv(V.PX_ALT_REFUSE_ENV, "1" if deploy == "code" else "0")
    code = V.main(["--live", "--dir", "unused", "--today", "2026-10-31", *argv])
    out = capsys.readouterr().out
    want = {"code": {"budget_s": 600.0, "refuse_skip": True}, "data": {"budget_s": 600.0}, "watchdog": {}}[deploy]
    assert seen == [("live", want)], seen
    return code, out, summary.read_text(encoding="utf-8")


def all_403(cur):
    return lambda clk: via_daum_page(cur, clk, lambda c: 403, step=1.0)


def test_main_code_deploy_refusal_exits_0_with_a_loud_warning(monkeypatch, capsys, tmp_path):
    cur, _, _ = fb_files()
    code, out, summ = run_main(monkeypatch, capsys, tmp_path, cur, all_403(cur))
    assert code == 0, out
    assert "· 다음의 거절로 건너뛰기: 켜짐 (코드 배포 · Jack 2026-11-21)" in out
    assert "· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 일별 시세 + 발행 기록): 207종목 · 동시 1 · 시간 한도 600초" in out
    assert "그만 묻고 경고로 건너뛰어요 (코드 배포만)" in out
    assert f"{MOMENT} — 답이 정해진 {NEED}종목이 모두 거절 (필수 종목 7 / 7 · 보기: 005930 HTTP 403" in out          # 그 순간
    after = next(ln for ln in out.splitlines() if ln.startswith(AFTER))                                              # 끝난 뒤
    assert f"거절 {NEED}종목 (필수 종목 7 / 7 · 보기: 005930 HTTP 403" in after and f"거절 뒤 묻지 않음 {207 - NEED}" in after
    assert "다음의 확인을 건너뛰고 경고 ('pxDate 최종본 여부' 줄)" in after and "시간 한도에 걸렸어요" not in out
    assert "결과: PASS" in out and "!! 경고  pxDate 최종본 여부: 2026-10-30" in out
    warns = [ln for ln in out.splitlines() if ln.startswith("::warning title=발행 관문 경고::")]
    assert any("pxDate 최종본 여부" in ln and "다음이 거절해 건너뜀" in ln for ln in warns)      # 매일 아침 점검이 읽어요
    assert "::error" not in out
    assert "### 뱁새 발행 관문 — PASS (live)" in summ and WARN_HOW in summ                   # 실행 요약 표
    assert "2차 출처 관문 기준 (야후): 다음이 거절해 확인을 건너뜀 (경고)" in out


def test_main_code_deploy_refusal_with_connection_errors_shows_short_examples(monkeypatch, capsys, tmp_path):
    cur, _, _ = fb_files()
    code, out, summ = run_main(monkeypatch, capsys, tmp_path, cur, lambda clk: raising(clk, refused_exc, step=1.0))
    assert code == 0, out
    after = next(ln for ln in out.splitlines() if ln.startswith(AFTER))
    assert "보기: 005930 ConnectionRefusedError; 000660 ConnectionRefusedError" in after and "HTTPConnectionPool" not in after
    assert "보기: 005930 ConnectionRefusedError" in summ


def test_main_data_publish_deploy_refusal_still_fails(monkeypatch, capsys, tmp_path):
    """리뷰 2026-11-21 (반드시): 데이터 실행 바로 뒤의 배포 (workflow_run · 한도는 있고 스위치는 0) 는 예전 그대로 — 다음이 모두 거절하면 실패."""
    cur, _, _ = fb_files()
    code, out, summ = run_main(monkeypatch, capsys, tmp_path, cur, all_403(cur), deploy="data")
    assert code == 1 and MOMENT not in out and AFTER not in out and "켜짐" not in out
    assert "시간 한도 600초" in out and "그만 묻고" not in out and "!! FAIL  최종본 날짜 계산" in out and "### 뱁새 발행 관문 — FAIL (live)" in summ


def test_main_code_deploy_refusal_with_a_wrong_close_still_fails(monkeypatch, capsys, tmp_path):
    """거절과 섞여 다른 종가가 오면 (일부만 거절) 예전 그대로 실패해요 — main 끝 코드 1."""
    cur, _, _ = fb_files()
    px = prices(cur)

    def make(clk):
        return lambda code, d: (px[code] + 100, "daum") if code == "005930" else (None, "HTTP 403")
    code, out, _ = run_main(monkeypatch, capsys, tmp_path, cur, make)
    assert code == 1 and MOMENT not in out and AFTER not in out and "!! FAIL  최종본 날짜 계산" in out


def test_main_watchdog_refusal_fails_as_before(monkeypatch, capsys, tmp_path):
    cur, _, _ = fb_files()
    code, out, summ = run_main(monkeypatch, capsys, tmp_path, cur, all_403(cur), deploy="watchdog")
    assert code == 1 and MOMENT not in out and AFTER not in out
    assert "시간 한도 없음 (예전 그대로)" in out and "!! FAIL  최종본 날짜 계산" in out and "### 뱁새 발행 관문 — FAIL (live)" in summ


def test_main_reads_the_switch_strictly(monkeypatch, capsys, tmp_path):
    """스위치: 1 · 0 · 빈 값만 (--live 에서 다른 값은 묻기 전에 실패) · 한도 없이는 쓰지 않아요 · 손으로는 --daum-refuse-skip · 발행 관문은 무시."""
    cur, prev, _ = fb_files()
    files = {k: cur[k] for k in ("data", "corp", "disc", "macro")}
    calls = []
    monkeypatch.setattr(V, "load_dir", lambda d: files)
    monkeypatch.setattr(V, "load_prev", lambda *a, **k: prev)
    monkeypatch.setattr(V, "load_prev_corp", lambda *a, **k: prev["corp"])
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (dt.date(2026, 10, 29), {}, "시험"))
    monkeypatch.setattr(V, "http_listing", lambda d: None)
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: {"dates": [dt.date(2026, 10, 30)], "src": "시험"})
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: {})

    def alt_fn(data, px, special=None, mode="publish", **kw):
        calls.append((mode, kw))
        return {"date": px, "mode": mode, "closes": {}, "asked": 1, "got": 0, "mustMissing": list(V.MUST), "err": []}
    monkeypatch.setattr(V, "http_px_alt", alt_fn)
    monkeypatch.setattr(V, "run_checks", lambda *a, **k: V.Report())
    for k in ("GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY", V.PX_ALT_LIMIT_ENV, V.PX_ALT_REFUSE_ENV):
        monkeypatch.delenv(k, raising=False)
    base = ["--dir", "unused", "--today", "2026-10-31"]
    monkeypatch.setenv(V.PX_ALT_LIMIT_ENV, "600")
    for raw, want in (("1", {"budget_s": 600.0, "refuse_skip": True}), ("0", {"budget_s": 600.0}), ("", {"budget_s": 600.0}),
                      (" 1 ", {"budget_s": 600.0, "refuse_skip": True})):
        monkeypatch.setenv(V.PX_ALT_REFUSE_ENV, raw)
        assert V.main(["--live"] + base) == 0 and calls[-1] == ("live", want), raw
    capsys.readouterr()
    n = len(calls)
    for bad in ("yes", "true", "2", "on"):                                # 켜졌는지 모르는 값은 묻기 전에 실패
        monkeypatch.setenv(V.PX_ALT_REFUSE_ENV, bad)
        assert V.main(["--live"] + base) == 1 and len(calls) == n, bad
        assert f"!! FAIL  {V.PX_ALT_REFUSE_ENV}=" in capsys.readouterr().out
    monkeypatch.delenv(V.PX_ALT_REFUSE_ENV)
    assert V.main(["--live", "--daum-refuse-skip"] + base) == 0 and calls[-1] == ("live", {"budget_s": 600.0, "refuse_skip": True})
    monkeypatch.delenv(V.PX_ALT_LIMIT_ENV)
    capsys.readouterr()
    assert V.main(["--live", "--daum-refuse-skip"] + base) == 0 and calls[-1] == ("live", {})          # 한도 없이는 쓰지 않아요 (감시처럼)
    assert "· 다음의 거절로 건너뛰기는 한도를 받은 사이트 점검(--live)에서만 써요" in capsys.readouterr().out
    assert V.main(["--live", "--daum-limit", "600", "--daum-refuse-skip"] + base) == 0
    assert calls[-1] == ("live", {"budget_s": 600.0, "refuse_skip": True})                                # 손으로 같은 꼴
    monkeypatch.setenv(V.PX_ALT_REFUSE_ENV, "yes")                                                         # 발행 관문은 스위치를 쓰지 않아요
    assert V.main(base + ["--prev-dir", str(tmp_path)]) == 0 and calls[-1] == ("publish", {})
