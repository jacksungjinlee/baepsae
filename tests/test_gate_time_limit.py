# -*- coding: utf-8 -*-
"""2026-11-27 (Jack, 11-27 답 8 그대로 — 질문: "May I add a 10-minute limit? If the limit is hit, that run doesn't publish and the next
scheduled run tries again. That adds a way to stop the publish, so it needs your yes."): "Yes, with one immediate retry inside the same run
before giving up." (네트워크 없음)

사고: 11-24 가지 시험 실행의 발행 관문이 "관문의 두 출처 확인 (다음 × 야후): 204종목 · 동시 4 · 시간 한도 없음 (발행 관문)" 에서 46분 동안
한 줄도 남기지 않고 멈췄어요 (다시 돌리니 52초). 이 시험은 (새 파일 · 다른 시험은 고치지 않았어요):
- 발행 관문(publish · bootstrap)의 두 출처 확인 전체에 600초 · 넘으면 크게 남기고 같은 실행에서 처음부터 한 번 더 (새 한도 · 첫 확인의 답은
  다시 쓰지 않아요) · 다시 물은 확인이 끝까지 가면 예전 기준 그대로 판단하고 날짜 줄이 경고로 알려요 (매일 아침 점검이 읽어요);
- 다시 물은 확인도 넘으면 실패 (publish · bootstrap 모두 · main 끝 코드 1 · '발행 관문 실패' 알림에 까닭) — 받은 종목 수가 기준을 채웠어도
  통과 · 건너뜀이 되지 않아요 (느슨해지지 않아요) · 세 번째는 없어요;
- 배포(--live + 한도)와 감시(--live · 한도 없음)는 예전 그대로 (한 번만 · 같은 인자 · 같은 결과와 로그 · 발행 관문의 한도를 읽지 않아요);
- 묻는 중인 요청은 끝까지 기다리고, 돌아온 뒤 남는 스레드가 없고, 따로 띄운 파이썬이 바로 끝나요 (진짜 시계 · 한도를 0.2초로 줄여요);
- 리뷰 #198 1차 (두 리뷰어 모두): 한도 때문에 다시 묻지 못한 종목은 마지막 오류가 네트워크 오류가 아니어도 (JSON 이 아닌 200 · 야후 404)
  '남은' 종목이에요 — 그래서 그 확인은 끝난 것이 아니고 한 번 더 물어요 (예전 규칙이 막는 것을 통과시키지 않고, 한 번 만에 실패하지도 않아요) ·
  남은 종목이 없는 확인은 한도 없이 물었을 때와 똑같아요 · 배포 · 감시는 예전 그대로 ('그날 종가를 주지 않음').
"""
import datetime as dt
import inspect
import os
import subprocess
import sys
import textwrap
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

TODAY = dt.date(2026, 10, 31)
PX = dt.date(2026, 10, 30)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}
REAL_HTTP_PX_ALT = V.http_px_alt
REAL_RUN_CHECKS = V.run_checks
GATE_KEYS = ("tries", "timeouts", "firstCut")


class Clock:
    """가짜 시계: 가짜 출처가 물을 때마다 앞으로 가요 (실제로 기다리지 않아요)."""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def fb_files():
    """좋은 데이터를 2차 출처 날로 (pxDate 10-30 · 캐시 최종본은 10-29 까지): (이번 파일, 직전 발행본, 하루 전 최종본)."""
    cur, prev, final = good_pair()
    nk = len(V.kr_stocks(cur["data"]))
    cur["data"]["pxSrc"] = {"v": 1, "px": V.PX_SRC_FB, "date": "2026-10-30", "days": {"2026-10-30": V.PX_SRC_FB},
                            "fb": {"n": nk + 100, "conf": nk + 50, "noDaum": 40, "bad": 0, "noYahoo": 7, "diff": 3, "diffEx": [], "must": []},
                            "must": [], "chk": None, "n": {V.PX_SRC_FB: nk}}
    old = {"date": dt.date(2026, 10, 29), "closes": {c: v * 0.98 for c, v in final["closes"].items()}, "how": "시험 (하루 전)"}
    return cur, prev, old


def prices(cur):
    return {s["t"]: float(s["price"]) for s in V.kr_stocks(cur["data"])}


def daum(cur, clk=None, step=0.0, calls=None, wrong=None, nap=0.0):
    """가짜 다음: 발행 가격 그대로 (wrong 에 있는 종목은 그만큼 다르게) · 물을 때마다 가짜 시계가 step 초 · 진짜로 nap 초 쉬어요."""
    px = prices(cur)
    lock = threading.Lock()

    def f(code, d):
        if calls is not None:
            with lock:
                calls.append(code)
        if clk is not None:
            clk.t += step
        if nap:
            time.sleep(nap)
        return px.get(code, 1000.0) + (wrong or {}).get(code, 0), "daum"
    return f


def yahoo_same(cur, wrong=None):
    px = prices(cur)
    return lambda sym, d, close_time=None: (px.get(sym.split(".")[0], 1000.0) + (wrong or {}).get(sym.split(".")[0], 0), "bar")


def asker(cur, steps, calls=None, lines=None, wrong=None, seen=None):
    """main 처럼 http_px_alt 를 한 번 부르는 함수 — 부를 때마다 새 가짜 시계 · 그 번째의 step (steps[i] · 모자라면 마지막)."""
    n = {"i": 0}

    def ask():
        i = n["i"]
        n["i"] += 1
        if seen is not None:
            seen.append(V._PX_ALT_GATE_S.get())
        clk = Clock()
        got = []
        alt = V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur, clk, steps[min(i, len(steps) - 1)], got, wrong),
                            workers=1, clock=clk, sleep=lambda s: None, say=(lines.append if lines is not None else (lambda s: None)))
        if calls is not None:
            calls.append(got)
        return alt
    return ask


def check(cur, alt, mode="publish", final=None, prev=None, now=NOW, today=TODAY):
    return V.run_checks(cur, prev, final, today, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=now,
                        hilo=hilo_of(cur, V.MUST), alt=alt)


def rows(rep):
    return {r[0]: r for r in rep.rows}


def failed(rep):
    return {r[0] for r in rep.failed}


def strip_gate(alt):
    return {k: v for k, v in alt.items() if k not in GATE_KEYS}


# ── 1. 값 · 한도는 발행 관문만 ───────────────────────────────────────────────────────
def test_the_limit_is_ten_minutes_with_one_retry():
    assert V.PX_ALT_GATE_BUDGET_S == 600 and V.PX_ALT_GATE_TRIES == 2
    assert V._PX_ALT_GATE_S.get() is None                               # 켜지 않았으면 꺼져 있어요
    assert V.px_alt_budget("publish") is None and V.px_alt_budget("bootstrap", 600) is None   # 배포의 한도(건너뜀)는 예전 그대로 발행에 없어요


def test_a_check_that_finishes_in_time_is_asked_once_and_left_as_is():
    cur, _, _ = fb_files()
    calls, lines, said = [], [], []
    alt = V.px_alt_publish_gate(asker(cur, [0.0], calls=calls, lines=lines), say=said.append)
    assert len(calls) == 1 and len(calls[0]) == alt["asked"] == alt["got"] == len(V.MUST) + V.PX_CHECK_SAMPLE
    assert alt["cut"] == 0 and alt["limit"] == 600.0 and not any(k in alt for k in GATE_KEYS) and said == []
    assert lines == ["· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 × 야후): 207종목 · 동시 1 · 시간 한도 600초 (발행 관문 — 넘으면 처음부터 "
                     "한 번 더 묻고, 또 넘으면 이번 실행은 발행하지 않아요)"]
    assert V._PX_ALT_GATE_S.get() is None                               # 끝나면 꺼요
    # 예전처럼 따로 부른 발행 확인과 같은 결과 (한도 값만 달라요) · 같은 판단
    plain = V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur), workers=1, sleep=lambda s: None, say=lambda s: None)
    keep = [k for k in plain if k not in ("limit", "secs")]
    assert plain["limit"] is None and {k: alt[k] for k in keep} == {k: plain[k] for k in keep}
    _, prev, old = fb_files()
    assert check(cur, alt, final=old, prev=prev).rows == check(cur, plain, final=old, prev=prev).rows
    assert not check(cur, alt, final=old, prev=prev).failed


def test_a_direct_publish_call_still_has_no_limit():
    """main 밖에서 부른 http_px_alt(발행) 는 예전 그대로 한도 없이 — 한도는 px_alt_publish_gate 가 켠 동안만이에요."""
    cur, _, _ = fb_files()
    clk, calls = Clock(), []
    alt = V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur, clk, 100.0, calls), workers=1, clock=clk,
                        sleep=lambda s: None, say=lambda s: None)
    assert len(calls) == alt["asked"] == alt["got"] and alt["cut"] == 0 and alt["limit"] is None


# ── 2. 첫 확인이 넘으면 바로 처음부터 한 번 더 — 끝까지 가면 예전 기준 그대로 (경고) ─────────────────────────
def test_first_timeout_then_a_retry_that_finishes_passes_with_a_loud_note():
    cur, prev, old = fb_files()
    calls, lines, said, seen = [], [], [], []
    alt = V.px_alt_publish_gate(asker(cur, [10.0, 0.0], calls=calls, lines=lines, seen=seen), say=said.append)
    assert seen == [600.0, 600.0] and V._PX_ALT_GATE_S.get() is None    # 두 번 모두 새 한도 · 끝나면 꺼요
    # 첫 확인: 한 번에 10초 → 다음에 60번 묻고 (0 ~ 590초), 60번째 종목은 다음이 답한 600초에 한도가 지나 야후를 묻지 않아요 (남은 종목)
    assert [len(c) for c in calls] == [60, 207]                         # 다시 물은 확인은 처음부터 모든 종목 (첫 확인의 답은 쓰지 않아요)
    assert calls[1] == sorted(V.px_alt_pick(cur["data"]))                # 예전 순서 그대로 (코드 순)
    assert alt["cut"] == 0 and alt["got"] == 207 and alt["tries"] == 2 and alt["timeouts"] == 1
    assert alt["firstCut"] == {"asked": 207, "got": 59, "cut": 148, "secs": 600.0}
    # 크게: 그 순간 (http_px_alt) · 넘긴 뒤 (몇 번째 · 대상 / 끝까지 물은 / 남은) · 다시 물은 확인이 끝난 뒤
    assert "!! 관문의 두 출처 확인 시간 한도 600초 (발행 관문): 다음 · 야후에 더 묻지 않아요 (확인 59 / 대상 207)" in lines[1]
    assert said[0] == ("!! 관문의 두 출처 확인이 시간 한도 600초를 넘겼어요 (발행 관문 · 1/2번째 · Jack 2026-11-27): 대상 207종목 · "
                       "끝까지 물은 59 (확인 59) · 남은 148 · 걸린 시간 600초 — 처음부터 한 번 더 물어요 (새 한도 600초 · 받은 답은 다시 쓰지 않아요)")
    assert said[1].startswith("!! 관문의 두 출처 확인: 다시 물은 확인은 시간 한도 안에 끝났어요 (2/2번째") and len(said) == 2
    rep = check(cur, alt, final=old, prev=prev)
    assert not rep.failed, rep.table()
    r = rows(rep)["pxDate = 최종본 날짜"]
    assert r[3] == "WARN" and "첫 확인이 시간 한도 600초를 넘겨 처음부터 다시 물었어요 (Jack 2026-11-27 · 첫 확인: 대상 207종목 · 끝까지 물은 59 " \
        "(확인 59) · 남은 148)" in r[2]
    assert rows(rep)["한국 가격 = 공식 종가"][3] == "PASS" and rows(rep)["005930 = 공식 종가"][3] == "PASS"
    # 나머지 줄은 다시 묻지 않은 같은 확인과 똑같아요 (예전 기준 그대로)
    once = V.px_alt_publish_gate(asker(cur, [0.0]), say=lambda s: None)
    a, b = rows(rep), rows(check(cur, once, final=old, prev=prev))
    assert set(a) == set(b) and all(a[k] == b[k] for k in a if k != "pxDate = 최종본 날짜")
    assert b["pxDate = 최종본 날짜"][3] == "PASS"


def test_a_retry_that_finishes_is_judged_exactly_as_before():
    """다시 물어 끝까지 간 확인에서 다른 종가가 오면 예전과 같은 줄이 실패해요 — 다시 물었다고 느슨해지지 않아요."""
    cur, prev, old = fb_files()
    for wrong, row in (({"005930": 100}, "005930 = 공식 종가"), ({c: 1 for c in sorted(V.px_alt_pick(cur["data"]))[7:20]}, "한국 가격 = 공식 종가")):
        retried = V.px_alt_publish_gate(asker(cur, [10.0, 0.0], wrong=wrong), say=lambda s: None)
        once = V.px_alt_publish_gate(asker(cur, [0.0], wrong=wrong), say=lambda s: None)
        assert retried["timeouts"] == 1 and "timeouts" not in once
        for alt in (retried, once):
            assert row in failed(check(cur, alt, final=old, prev=prev)), row
    # 다시 물은 확인이 필수 종목을 못 받으면 예전 그대로 실패 (까닭에 다시 물었다는 것도 붙어요)
    cur2, prev2, old2 = fb_files()

    def ask_missing(n={"i": 0}):
        n["i"] += 1
        clk = Clock()
        base = daum(cur2, clk, 10.0 if n["i"] == 1 else 0.0)
        f = (lambda code, d: (None, "그날 행 0개") if code == "005930" and n["i"] == 2 else base(code, d))
        return V.http_px_alt(cur2["data"], PX, fetch=yahoo_same(cur2), fetch_daum=f, workers=1, clock=clk, sleep=lambda s: None,
                             say=lambda s: None)
    alt = V.px_alt_publish_gate(ask_missing, say=lambda s: None)
    assert alt["timeouts"] == 1 and alt["mustMissing"] == ["005930"]
    r = rows(check(cur2, alt, final=old2, prev=prev2))["pxDate = 최종본 날짜"]
    assert r[3] == "FAIL" and "필수 종목을 확인하지 못했어요: 005930" in r[2] and "첫 확인이 시간 한도 600초를 넘겨" in r[2]


# ── 3. 다시 물은 확인도 넘으면 실패 — 통과 · 건너뜀이 되지 않아요 ─────────────────────────────────────
def test_two_timeouts_fail_even_when_enough_closes_came_in():
    """다시 물은 확인도 넘으면 실패. 600초 안에 199종목 (필수 7 + 표본 192 — 예전 기준 90% 를 넘는 수) 을 받았어도 쓰지 않아요: 받지 못한 8종목의
    다른 종가를 놓칠 수 있어요."""
    cur, prev, old = fb_files()
    calls, said = [], []
    alt = V.px_alt_publish_gate(asker(cur, [3.0], calls=calls), say=said.append)
    assert [len(c) for c in calls] == [200, 200] and len(said) == 2       # 두 번만 (세 번째는 없어요) · 200번째는 다음만 묻고 한도
    assert alt["got"] == 199 and alt["cut"] == 8 and not alt["mustMissing"] and alt["got"] >= V.PX_ALT_MIN_SHARE * alt["asked"]
    assert alt["tries"] == 2 and alt["timeouts"] == 2 and alt["firstCut"]["cut"] == 8
    assert said[1] == ("!! 관문의 두 출처 확인이 시간 한도 600초를 두 번 넘겼어요 (발행 관문 · 2/2번째 · Jack 2026-11-27): 대상 207종목 · "
                       "끝까지 물은 199 (확인 199) · 남은 8 · 걸린 시간 600초 — 이번 실행은 발행하지 않아요 (관문 실패 · 다음 예정 실행이 다시 해요)")
    for mode in ("publish", "bootstrap"):
        ok, why = V.px_alt_confirms(cur["data"], alt, PX, old, mode, today=TODAY, now=NOW, special={})
        assert not ok and why == ("관문의 두 출처 확인(다음 × 야후)이 시간 한도 600초를 두 번 넘김 (Jack 2026-11-27) — 다시 물은 확인: 대상 207종목 · "
                                  "끝까지 물은 199 (확인 199) · 남은 8 · 이번 실행은 발행하지 않아요 (다음 예정 실행이 다시 해요)"), mode
        rep = check(cur, alt, mode=mode, final=old, prev=prev if mode == "publish" else None)
        r = rows(rep)["pxDate = 최종본 날짜"]
        assert r[3] == "FAIL" and why.split("이 ", 1)[1] in r[2] and r[2].count("두 번 넘김") == 1, (mode, r)
        assert not any(x[3] == "WARN" for x in rep.rows if x[0] == "pxDate = 최종본 날짜")
        # 캐시에 최종본이 없는 날도 실패 ('최종본 날짜 계산')
        rep = check(cur, alt, mode=mode, final=None, prev=prev if mode == "publish" else None)
        assert "최종본 날짜 계산" in failed(rep) and "시간 한도 600초를 두 번 넘김" in rows(rep)["최종본 날짜 계산"][2]
    # 한도 기록만 지우면 (cut 0 — 예전 규칙) 같은 받은 수(199 / 207 · 필수 모두)로 통과했을 거예요 — 실패의 까닭은 시간 한도 하나예요
    assert V.px_alt_confirms(cur["data"], dict(alt, cut=0), PX, old, "publish", today=TODAY, now=NOW, special={})[0] is True
    full = V.px_alt_publish_gate(asker(cur, [0.0]), say=lambda s: None)
    assert V.px_alt_confirms(cur["data"], full, PX, old, "publish", today=TODAY, now=NOW, special={})[0] is True


@pytest.mark.parametrize("cutv", [1, 7, 207, True, "1"])
def test_any_cut_record_in_publish_never_passes(cutv):
    """기록이 어떤 꼴이든 발행 관문에서 cut 이 0 이 아니면 쓰지 않아요 (가장 엄한 쪽) — 다 받았다고 적혀 있어도."""
    cur, prev, old = fb_files()
    full = V.px_alt_publish_gate(asker(cur, [0.0]), say=lambda s: None)
    for alt in (dict(full, cut=cutv), dict(full, cut=cutv, timeouts=2, tries=2), dict(full, cut=cutv, limit=None)):
        ok, why = V.px_alt_confirms(cur["data"], alt, PX, old, "publish", today=TODAY, now=NOW, special={})
        assert not ok and "시간 한도" in why and "넘김" in why
        assert "pxDate = 최종본 날짜" in failed(check(cur, alt, final=old, prev=prev))


def test_the_gate_never_swallows_an_error_and_always_switches_off():
    cur, _, _ = fb_files()

    def boom():
        assert V._PX_ALT_GATE_S.get() == 600.0
        raise RuntimeError("시험")
    with pytest.raises(RuntimeError):
        V.px_alt_publish_gate(boom, say=lambda s: None)
    assert V._PX_ALT_GATE_S.get() is None
    # 첫 확인이 넘고 다시 물은 확인이 예외 → 그대로 올라가요 (main 이 '확인 못 함'으로 실패시켜요)
    n = {"i": 0}
    first = asker(cur, [10.0])

    def second_boom():
        n["i"] += 1
        if n["i"] == 2:
            raise RuntimeError("두 번째")
        return first()
    with pytest.raises(RuntimeError):
        V.px_alt_publish_gate(second_boom, say=lambda s: None)
    assert V._PX_ALT_GATE_S.get() is None and n["i"] == 2


# ── 4. main: 매일 실행의 관문 (publish · bootstrap) — 끝 코드 · 로그 · GitHub 알림 (매일 아침 점검) ──────────────────
def run_main(monkeypatch, capsys, tmp_path, steps, argv=(), wrong=None, env_limit=None):
    """매일 실행의 관문 그대로 (python validate_data.py [--bootstrap]) — http_px_alt 는 진짜 함수에 가짜 출처와 시계 (부를 때마다 새 시계).
    run_checks 는 진짜 함수에 시험의 '지금' 만 (픽스처의 publishedAt 이 2026-10-31 이에요)."""
    cur, prev, old = fb_files()
    files = {k: cur[k] for k in ("data", "corp", "disc", "macro")}
    monkeypatch.setattr(V, "load_dir", lambda d: files)
    monkeypatch.setattr(V, "load_prev", lambda *a, **k: prev)
    monkeypatch.setattr(V, "load_prev_corp", lambda *a, **k: prev["corp"])
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (old["date"], old["closes"], "시험 (하루 전)"))
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: SESSIONS)
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: hilo_of(cur, V.MUST))
    monkeypatch.setattr(V, "count_final_between", lambda a, b: 1)
    monkeypatch.setattr(V, "run_checks", lambda *a, **k: REAL_RUN_CHECKS(*a, **dict(k, now=NOW)))
    seen = []

    def alt_fn(data, px, special=None, mode="publish", **kw):              # main 이 부르는 꼴 그대로 (진짜 함수 · 가짜 출처와 시계)
        i = len(seen)
        seen.append((mode, kw, V._PX_ALT_GATE_S.get()))
        clk = Clock()
        return REAL_HTTP_PX_ALT(data, px, special=special, mode=mode, fetch=yahoo_same(cur),
                                fetch_daum=daum(cur, clk, steps[min(i, len(steps) - 1)], None, wrong), workers=1, clock=clk,
                                sleep=lambda s: None, **kw)
    monkeypatch.setattr(V, "http_px_alt", alt_fn)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.delenv(V.PX_ALT_REFUSE_ENV, raising=False)
    if env_limit is None:
        monkeypatch.delenv(V.PX_ALT_LIMIT_ENV, raising=False)
    else:
        monkeypatch.setenv(V.PX_ALT_LIMIT_ENV, env_limit)
    code = V.main(["--dir", "unused", "--today", "2026-10-31", *argv])
    out = capsys.readouterr().out
    assert all(m == "publish" and kw == {} for m, kw, _ in seen), seen          # 예전과 같은 꼴로 불러요 (한도는 인자가 아니에요)
    assert V._PX_ALT_GATE_S.get() is None
    return code, out, summary.read_text(encoding="utf-8"), [g for _, _, g in seen]


def test_main_publish_in_time_is_one_call_and_passes(monkeypatch, capsys, tmp_path):
    code, out, summ, gates = run_main(monkeypatch, capsys, tmp_path, [0.0])
    assert gates == [600.0] and code == 0, out
    assert "· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 × 야후): 207종목 · 동시 1 · 시간 한도 600초 (발행 관문 — 넘으면 처음부터 한 번 더" in out
    assert "!! 관문의 두 출처" not in out and "결과: PASS" in out and "::error" not in out
    assert not any("pxDate = 최종본 날짜" in ln for ln in out.splitlines() if ln.startswith("::warning"))


def test_main_publish_retry_that_finishes_exits_0_with_a_warning(monkeypatch, capsys, tmp_path):
    code, out, summ, gates = run_main(monkeypatch, capsys, tmp_path, [10.0, 0.0])
    assert gates == [600.0, 600.0] and code == 0, out
    assert "!! 관문의 두 출처 확인 시간 한도 600초 (발행 관문): 다음 · 야후에 더 묻지 않아요 (확인 59 / 대상 207)" in out    # 그 순간
    assert ("!! 관문의 두 출처 확인이 시간 한도 600초를 넘겼어요 (발행 관문 · 1/2번째 · Jack 2026-11-27): 대상 207종목 · 끝까지 물은 59 (확인 59) · "
            "남은 148 · 걸린 시간 600초 — 처음부터 한 번 더 물어요") in out
    assert "!! 관문의 두 출처 확인: 다시 물은 확인은 시간 한도 안에 끝났어요 (2/2번째" in out
    assert "· 관문의 두 출처 공식 종가 (2026-10-30 · 다음 × 야후): 확인 207 / 207종목" in out
    assert "결과: PASS" in out and "!! 경고  pxDate = 최종본 날짜: 2026-10-30" in out and "::error" not in out
    warns = [ln for ln in out.splitlines() if ln.startswith("::warning title=발행 관문 경고::pxDate = 최종본 날짜")]
    assert len(warns) == 1 and "첫 확인이 시간 한도 600초를 넘겨 처음부터 다시 물었어요" in warns[0]   # 매일 아침 점검이 읽어요
    assert "### 뱁새 발행 관문 — PASS (publish)" in summ and "첫 확인이 시간 한도 600초를 넘겨" in summ
    assert "2차 출처 관문 기준 (야후): 씀 — " in out and "시간 한도에 걸렸어요 (Jack 2026-11-20)" not in out   # 배포의 건너뛰기 말은 없어요


@pytest.mark.parametrize("argv", [(), ("--bootstrap",)])
def test_main_two_timeouts_fail_in_publish_and_bootstrap(monkeypatch, capsys, tmp_path, argv):
    code, out, summ, gates = run_main(monkeypatch, capsys, tmp_path, [3.0], argv=argv)    # 두 번 모두 199 / 207 에서 넘겨요
    mode = "bootstrap" if argv else "publish"
    assert gates == [600.0, 600.0] and code == 1, out                                   # 세 번째는 없어요
    assert "1/2번째" in out and ("!! 관문의 두 출처 확인이 시간 한도 600초를 두 번 넘겼어요 (발행 관문 · 2/2번째 · Jack 2026-11-27): 대상 207종목 · "
                                 "끝까지 물은 199 (확인 199) · 남은 8 · 걸린 시간 600초 — 이번 실행은 발행하지 않아요") in out
    assert "!! 관문의 두 출처 공식 종가 (2026-10-30 · 다음 × 야후): 확인 199 / 207종목" in out    # 받은 수가 기준을 넘어도 조용히 쓰지 않아요
    assert "시간 한도에 걸렸어요 (Jack 2026-11-20)" not in out and "건너뛰고 경고" not in out    # 배포처럼 건너뛰지 않아요
    assert "결과: FAIL" in out and "!! FAIL  pxDate = 최종본 날짜: 2026-10-30" in out
    errs = [ln for ln in out.splitlines() if ln.startswith("::error title=발행 관문 실패::pxDate = 최종본 날짜")]
    assert len(errs) == 1 and "시간 한도 600초를 두 번 넘김 (Jack 2026-11-27)" in errs[0] and "이번 실행은 발행하지 않아요" in errs[0]
    assert f"### 뱁새 발행 관문 — FAIL ({mode})" in summ and "시간 한도 600초를 두 번 넘김" in summ
    assert "2차 출처 관문 기준 (야후): 쓰지 않음 — 관문의 두 출처 확인(다음 × 야후)이 시간 한도 600초를 두 번 넘김" in out


def test_main_publish_ignores_the_deploy_limit_but_keeps_its_own(monkeypatch, capsys, tmp_path):
    """배포의 한도 값(건너뜀)을 받아도 발행 관문은 쓰지 않고 자기 한도(넘으면 한 번 더 · 또 넘으면 실패)만 써요."""
    code, out, _, gates = run_main(monkeypatch, capsys, tmp_path, [3.0], env_limit="900")
    assert gates == [600.0, 600.0] and code == 1
    assert ("· 다음 확인 시간 한도(900)는 사이트 점검(--live)에서만 써요 — 이 실행(publish)은 한도 없이 예전 그대로 묻지 않고, 이 값 대신 "
            "발행 관문의 한도 600초를 써요 (넘으면 바로 한 번 더, 또 넘으면 실패 · 건너뛰지 않아요 · Jack 2026-11-27)") in out


# ── 5. 배포 · 감시 (--live) 는 예전 그대로 ───────────────────────────────────────────────
def test_live_ignores_the_publish_gate_even_if_it_is_on():
    """사이트 점검(live)은 발행 관문의 한도를 읽지 않아요 — 켜진 채 불러도 결과와 로그가 글자 하나까지 같아요 (배포 · 감시 · 코드 배포 거절)."""
    cur, _, _ = fb_files()
    px = prices(cur)
    cases = [dict(budget_s=600.0, step=10.0), dict(budget_s=600.0, step=0.0), dict(budget_s=None, step=100.0), dict(budget_s=600.0, step=3.0),
             dict(budget_s=600.0, step=1.0, refuse=True)]
    for c in cases:
        outs = []
        for on in (False, True):
            clk, lines = Clock(), []

            def f(code, d, clk=clk, c=c):
                clk.t += c["step"]
                return (None, "HTTP 403") if c.get("refuse") else (px.get(code, 1000.0), "daum")
            kw = {"budget_s": c["budget_s"]} if c["budget_s"] is not None else {}
            if c.get("refuse"):
                kw["refuse_skip"] = True
            tok = V._PX_ALT_GATE_S.set(0.001) if on else None
            try:
                alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=f, workers=1, clock=clk, sleep=lambda s: None, say=lines.append, **kw)
            finally:
                if tok is not None:
                    V._PX_ALT_GATE_S.reset(tok)
            rep = check(cur, alt, mode="live")
            outs.append((alt, lines, rep.rows))
        assert outs[0] == outs[1], c
        assert not any(k in outs[0][0] for k in GATE_KEYS) and "발행 관문 —" not in " ".join(outs[0][1])
    # 배포의 시작 줄은 예전 글자 그대로
    assert outs[0][1][0].endswith("시간 한도 600초 (배포 — 넘으면 새로 묻지 않고, 시간 한도로 못 받은 부분만 경고로 건너뛰어요) · 다음이 거절하면 "
                                  "(답이 정해진 21종목 이상이 모두 거절 · 필수 종목 모두) 그만 묻고 경고로 건너뛰어요 (코드 배포만)")


def test_live_rows_ignore_gate_keys():
    """사이트 점검의 표는 발행 관문의 기록(다시 물음)을 읽지 않아요 — 같은 확인에 그 기록이 붙어 있어도 줄이 같아요."""
    cur, _, _ = fb_files()
    for step in (0.0, 10.0, 3.0):
        clk = Clock()
        alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=daum(cur, clk, step), workers=1, clock=clk, sleep=lambda s: None,
                            say=lambda s: None, budget_s=600.0)
        extra = dict(alt, tries=2, timeouts=1, firstCut={"asked": 207, "got": 1, "cut": 206, "secs": 600.0})
        assert check(cur, alt, mode="live").rows == check(cur, extra, mode="live").rows
        assert V.px_alt_gate_note(alt) is None and V.px_alt_gate_note(extra) is None


@pytest.mark.parametrize("env,want", [("600", {"budget_s": 600.0}), (None, {})])
def test_main_live_is_called_once_as_before_even_when_cut(monkeypatch, capsys, env, want):
    """배포(한도 600) · 감시(한도 없음): 한 번만, 예전과 같은 인자로 · 시간 한도에 걸린 확인도 다시 묻지 않아요 · 발행 관문의 한도는 꺼져 있어요."""
    cur, _, _ = fb_files()
    files = {k: cur[k] for k in ("data", "corp", "disc", "macro")}
    monkeypatch.setattr(V, "load_dir", lambda d: files)
    monkeypatch.setattr(V, "http_listing", lambda d: None)
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: hilo_of(cur, V.MUST))
    seen = []

    def alt_fn(data, px, special=None, mode="publish", **kw):
        seen.append((mode, kw, V._PX_ALT_GATE_S.get()))
        clk = Clock()
        return REAL_HTTP_PX_ALT(data, px, special=special, mode=mode, fetch_daum=daum(cur, clk, 10.0), workers=1, clock=clk,
                                sleep=lambda s: None, **dict(kw, budget_s=600.0))     # 감시 꼴도 한도에 걸린 기록으로 (다시 묻는지 보려고)
    monkeypatch.setattr(V, "http_px_alt", alt_fn)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv(V.PX_ALT_REFUSE_ENV, raising=False)
    if env is None:
        monkeypatch.delenv(V.PX_ALT_LIMIT_ENV, raising=False)
    else:
        monkeypatch.setenv(V.PX_ALT_LIMIT_ENV, env)
    code = V.main(["--live", "--dir", "unused", "--today", "2026-10-31"])
    out = capsys.readouterr().out
    assert seen == [("live", want, None)]
    assert code == 0, out
    assert "!! 관문의 두 출처 확인이 시간 한도 600초에 걸렸어요 (Jack 2026-11-20): 확인 60 / 207종목 · 시간 한도로 건너뜀 147" in out
    assert "(발행 관문" not in out and "발행 관문 —" not in out and "처음부터 한 번 더" not in out and "두 번 넘" not in out


def test_watchdog_and_deploy_workflows_are_untouched():
    """감시 · 배포가 관문을 부르는 꼴은 그대로 (발행 관문의 한도는 환경 변수 · 인자가 없어요 — 코드 안의 값이에요)."""
    wfd = os.path.join(ROOT, ".github", "workflows")
    for name in sorted(os.listdir(wfd)):
        text = open(os.path.join(wfd, name), encoding="utf-8").read()
        assert "PX_ALT_GATE" not in text and "GATE_BUDGET" not in text, name
    src = open(os.path.join(ROOT, "watchdog.py"), encoding="utf-8").read()
    assert "PX_ALT_GATE" not in src and "px_alt_publish_gate" not in src
    main_src = inspect.getsource(V._main)
    assert 'alt = http_px_alt(pick_data, pxd, special=special, mode="live", **lim_kw)' in main_src
    assert 'alt = px_alt_publish_gate(lambda: http_px_alt(pick_data, pxd, special=special, mode="publish", **lim_kw))' in main_src


# ── 6. 묻는 중인 요청은 끝까지 · 남는 스레드 없음 · 프로세스가 끝나요 (진짜 시계 · 한도 0.2초) ───────────────────────
def test_in_flight_requests_finish_and_no_thread_is_left(monkeypatch):
    cur, _, _ = fb_files()
    monkeypatch.setattr(V, "PX_ALT_GATE_BUDGET_S", 0.2)
    started, done, lock = [], [], threading.Lock()
    px = prices(cur)

    def slow(code, d):
        with lock:
            started.append(code)
        time.sleep(0.05)
        with lock:
            done.append(code)
        return px[code], "daum"
    said = []
    before = set(threading.enumerate())
    t0 = time.monotonic()
    alt = V.px_alt_publish_gate(lambda: V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=slow, sleep=lambda s: None,
                                                      say=lambda s: None), say=said.append)      # 동시 4 (기본)
    took = time.monotonic() - t0
    assert [t for t in threading.enumerate() if t not in before] == []         # 돌아온 뒤 남은 스레드 없음
    assert alt["tries"] == alt["timeouts"] == 2 and alt["cut"] > 0 and alt["limit"] == 0.2
    assert len(started) == len(done) >= 2                                      # 시작한 요청은 모두 끝났어요 (두 번 모두)
    assert alt["got"] + alt["cut"] + alt["no"] + alt["net"] + len(alt["disagree"]) <= alt["asked"]
    assert 0.4 <= took < 0.4 + 2 * 0.05 + 3.0                                  # 한도 두 번 + 묻는 중인 요청 (여유 3초)
    assert "시간 한도 0.2초를 두 번 넘겼어요" in said[-1]
    assert not V.px_alt_confirms(cur["data"], alt, PX, None, "publish", today=TODAY, now=NOW, special={})[0]


def test_a_gate_that_times_out_twice_does_not_keep_the_process_alive(tmp_path):
    """따로 띄운 파이썬: 발행 관문의 확인이 두 번 한도에 걸린 뒤 바로 끝나요 (남은 스레드가 프로세스를 붙잡지 않아요)."""
    script = tmp_path / "gate_exit.py"
    script.write_text(textwrap.dedent(f"""
        import datetime as dt, sys, threading, time
        sys.path.insert(0, {ROOT!r})
        import validate_data as V
        V.PX_ALT_GATE_BUDGET_S = 0.2
        stocks = [{{"t": c, "cls": "kr", "price": 1000.0, "dk": "업종 · KOSPI 상장"}} for c in V.MUST]
        stocks += [{{"t": f"9{{i:05d}}", "cls": "kr", "price": 1000.0, "dk": "업종 · KOSDAQ 상장"}} for i in range(300)]
        def slow(code, d):
            time.sleep(0.1)
            return 1000.0, "daum"
        def yahoo(sym, d, close_time=None):
            time.sleep(0.1)
            return 1000.0, "bar"
        alt = V.px_alt_publish_gate(lambda: V.http_px_alt({{"stocks": stocks}}, dt.date(2026, 10, 30), fetch=yahoo, fetch_daum=slow,
                                                          sleep=lambda s: None))
        print("cut", alt["cut"], "tries", alt["tries"], "timeouts", alt["timeouts"], "threads", threading.active_count(), flush=True)
    """), encoding="utf-8")
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    took = time.monotonic() - t0
    assert r.returncode == 0, r.stderr
    last = r.stdout.strip().splitlines()[-1].split()
    assert last[0] == "cut" and int(last[1]) > 0 and last[2:] == ["tries", "2", "timeouts", "2", "threads", "1"], r.stdout
    assert r.stdout.count("· 관문의 두 출처 확인 시작") == 2 and "시간 한도 0.2초 (발행 관문" in r.stdout
    assert "!! 관문의 두 출처 확인이 시간 한도 0.2초를 두 번 넘겼어요" in r.stdout
    assert took < 20, took                                                     # 파이썬 시작 + 2 × (0.2 + 0.2초) — 붙잡히면 훨씬 길어요


# ── 7. 리뷰 #198 1차 (두 리뷰어 모두 · 막는 문제): 네트워크 오류가 아닌 답 뒤 한도가 지나 다시 묻지 못한 종목 ───────────────────────
# 예전 (이 PR 첫 판): 그 종목은 '그날 종가를 주지 않음'(no) 으로 세져 남은 종목(cut)이 0 — 확인이 끝난 것으로 보여 다시 묻지 않고, 예전 규칙
# (한도 없음)이 다시 물어 막았을 확인을 통과시키거나 (리뷰 Fable probe1), 한 번 만에 실패했어요 (Fable probe2 · Opus edge_no). 이제 발행 관문에서는
# 오류 종류와 상관없이 남은 종목이에요. 배포 · 감시는 예전 그대로예요.
import requests  # noqa: E402


def non_json():
    """200 인데 JSON 이 아닌 답 (차단 · 확인 쪽 화면) — 네트워크 오류가 아니에요 (px_net_error)."""
    return requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)


def yahoo_404():
    r = requests.Response()
    r.status_code = 404
    return requests.HTTPError("404 Client Error: Not Found", response=r)


EDGE_ERRS = [("daum", non_json), ("yahoo", yahoo_404), ("yahoo", non_json)]


def edge_ask(cur, stage, err, victim=None, norow=(), wrong=None, again=None, once=True, calls=None, step=601.0, mode="publish", **kw):
    """한 번 부를 때마다 새 가짜 시계 · 동시 1 (코드 순). victim (기본: 마지막 종목) 의 첫 답 (stage: daum · yahoo) 이 느리고 (가짜 시계가 step 초 —
    한도를 넘겨요) 네트워크 오류가 아닌 오류예요. 다시 물으면 again 만큼 다른 종가 (없으면 발행 가격). once: 그 실패가 실행 전체에서 한 번만
    (False 면 부를 때마다 처음 한 번). norow: 다음이 '그날 행 0개' 라고 답하는 종목 · wrong: 두 출처가 다른 종목 (다음만 그만큼 다르게).
    calls: 부를 때마다 victim 을 물은 횟수를 남겨요."""
    px = prices(cur)
    victim = victim or sorted(V.px_alt_pick(cur["data"]))[-1]
    hit = {"n": 0}

    def ask():
        clk, tries = Clock(), {}

        def bad_first(code):
            tries[code] = tries.get(code, 0) + 1
            if code == victim and tries[code] == 1 and not (once and hit["n"]):
                hit["n"] += 1
                clk.t += step
                raise err()

        def fd(code, d):
            if stage == "daum":
                bad_first(code)
            if code in norow:
                return None, "그날 행 0개"
            return px.get(code, 1000.0) + (wrong or {}).get(code, 0) + ((again or 0) if code == victim else 0), "daum"

        def fy(sym, d, close_time=None):
            code = sym.split(".")[0]
            if stage == "yahoo":
                bad_first(code)
            return px.get(code, 1000.0), "bar"
        alt = V.http_px_alt(cur["data"], PX, fetch=fy, fetch_daum=fd, workers=1, clock=clk, sleep=lambda s: None, say=lambda s: None,
                            mode=mode, **kw)
        if calls is not None:
            calls.append(tries.get(victim, 0))
        return alt
    return ask, victim


@pytest.mark.parametrize("stage,err", EDGE_ERRS)
def test_a_reask_stopped_by_the_limit_is_cut_whatever_the_error(stage, err):
    cur, _, _ = fb_files()
    ask, victim = edge_ask(cur, stage, err, once=False)
    tok = V._PX_ALT_GATE_S.set(600.0)
    try:
        alt = ask()
    finally:
        V._PX_ALT_GATE_S.reset(tok)
    assert alt["cut"] == 1 and alt["got"] == 206 and alt["no"] == 0, (alt["cut"], alt["got"], alt["no"])
    assert any(e.startswith(victim if stage == "daum" else f"{victim}.") and e.endswith("(시간 한도로 다시 묻지 않음)") for e in alt["err"]), alt["err"]
    assert alt["cutErrN"] == 0                                         # '네트워크 오류 뒤 다시 묻지 못한 종목' 은 그대로 네트워크 오류만 세요


@pytest.mark.parametrize("stage,err", EDGE_ERRS)
def test_review_probe1_a_check_main_stops_is_not_passed(stage, err):
    """Fable probe1 꼴: 표본 두 종목이 다르고, 마지막 종목의 첫 답이 느리고 네트워크 오류가 아니에요 — 다시 물으면 세 번째로 다른 종가.
    예전 규칙 (한도 없이 다시 물음): 다름 3 → '한국 가격 = 공식 종가' 실패. 발행 관문: 그 종목은 남은 종목 → 바로 한 번 더 → 같은 실패
    (첫 판은 한 번에 끝난 것으로 보고 99.0% 로 통과시켰어요)."""
    cur, prev, old = fb_files()
    order = sorted(V.px_alt_pick(cur["data"]))
    wrong = {c: 1 for c in order[10:12]}
    plain, _ = edge_ask(cur, stage, err, wrong=wrong, again=5)
    main_like = plain()                                                # 한도 없이 (예전 규칙 · main 과 같은 길)
    assert main_like["cut"] == 0 and len(main_like["disagree"]) == 3
    assert "한국 가격 = 공식 종가" in failed(check(cur, main_like, final=old, prev=prev))
    for once in (True, False):                                         # 실패가 한 번뿐 (다시 물은 확인은 깨끗) · 부를 때마다 (두 번 모두 넘김)
        calls, said = [], []
        ask, _ = edge_ask(cur, stage, err, wrong=wrong, again=5, once=once, calls=calls)
        alt = V.px_alt_publish_gate(ask, say=said.append)
        assert len(calls) == 2 and alt["tries"] == 2, once                # 한 번 만에 끝난 것으로 보지 않아요
        assert said[0].startswith("!! 관문의 두 출처 확인이 시간 한도 600초를 넘겼어요 (발행 관문 · 1/2번째") and "남은 1" in said[0]
        rep = check(cur, alt, final=old, prev=prev)
        assert rep.failed, (once, rep.table())                           # 예전 규칙이 막는 확인을 통과시키지 않아요
        if once:
            assert alt["cut"] == 0 and len(alt["disagree"]) == 3 and "한국 가격 = 공식 종가" in failed(rep)   # 다시 물어 예전과 같은 판단
            assert {k: alt[k] for k in ("closes", "got", "disagree", "mustMissing")} == \
                {k: main_like[k] for k in ("closes", "got", "disagree", "mustMissing")}
        else:
            assert alt["cut"] == 1 and alt["timeouts"] == 2 and "시간 한도 600초를 두 번 넘김" in rows(rep)["pxDate = 최종본 날짜"][2]


@pytest.mark.parametrize("stage,err", EDGE_ERRS)
def test_review_probe2_one_slow_odd_answer_retries_instead_of_failing_at_once(stage, err):
    """Fable probe2 꼴: 표본 20종목에 다음이 그날 행이 없다고 답해요 (187 / 207 — 90% 를 겨우 넘어요). 마지막 종목의 첫 답이 느리고 네트워크
    오류가 아니에요 (다시 물으면 맞아요). 예전 규칙: 187 / 207 통과. 첫 판: 한 번 만에 186 / 207 로 실패 ('두 번 넘김' 없이). 이제: 남은 종목 1 →
    바로 한 번 더 → 187 / 207 통과 (날짜 줄 경고)."""
    cur, prev, old = fb_files()
    order = sorted(V.px_alt_pick(cur["data"]))
    norow = set([c for c in order if c not in V.MUST][:20])
    plain, _ = edge_ask(cur, stage, err, norow=norow)
    main_like = plain()
    assert main_like["got"] == 187 and not check(cur, main_like, final=old, prev=prev).failed
    calls, said = [], []
    ask, _ = edge_ask(cur, stage, err, norow=norow, calls=calls)
    alt = V.px_alt_publish_gate(ask, say=said.append)
    assert len(calls) == 2 and alt["tries"] == 2 and alt["timeouts"] == 1 and alt["firstCut"]["cut"] == 1
    assert alt["got"] == 187 and alt["cut"] == 0
    rep = check(cur, alt, final=old, prev=prev)
    assert not rep.failed, rep.table()
    r = rows(rep)["pxDate = 최종본 날짜"]
    assert r[3] == "WARN" and "첫 확인이 시간 한도 600초를 넘겨 처음부터 다시 물었어요" in r[2] and "남은 1)" in r[2]
    a, b = rows(rep), rows(check(cur, main_like, final=old, prev=prev))
    assert all(a[k] == b[k] for k in a if k != "pxDate = 최종본 날짜")      # 나머지 줄은 예전 규칙과 똑같아요


@pytest.mark.parametrize("stage,err,victim", [("daum", non_json, "005930"), ("yahoo", yahoo_404, "000660")])
def test_review_opus_edge_a_must_have_with_a_slow_odd_answer_retries(monkeypatch, stage, err, victim):
    """Opus edge_no · edge_no_yahoo 꼴 (진짜 시계 · 동시 4 · 한도 0.3초): 필수 종목의 첫 답이 0.5초 걸리고 네트워크 오류가 아니에요 (다른 종목은
    바로 답해요). 첫 판: 남은 종목 0 → 다시 묻지 않고 필수 종목이 빠져 실패. 이제: 다시 물어 (그 실패는 한 번뿐) 모두 받고 통과 (경고)."""
    cur, prev, old = fb_files()
    monkeypatch.setattr(V, "PX_ALT_GATE_BUDGET_S", 0.3)
    px = prices(cur)
    tries, lock = {}, threading.Lock()

    def first_bad(code):
        with lock:
            tries[code] = tries.get(code, 0) + 1
            n = tries[code]
        if code == victim and n == 1:
            time.sleep(0.5)
            raise err()

    def fd(code, d):
        if stage == "daum":
            first_bad(code)
        return px[code], "daum"

    def fy(sym, d, close_time=None):
        if stage == "yahoo":
            first_bad(sym.split(".")[0])
        return px.get(sym.split(".")[0], 1000.0), "bar"
    said = []
    alt = V.px_alt_publish_gate(lambda: V.http_px_alt(cur["data"], PX, fetch=fy, fetch_daum=fd, sleep=lambda s: None, say=lambda s: None),
                                say=said.append)
    assert alt["tries"] == 2 and alt["timeouts"] == 1 and alt["cut"] == 0 and alt["mustMissing"] == [] and tries[victim] == 2
    assert said[0].startswith("!! 관문의 두 출처 확인이 시간 한도 0.3초를 넘겼어요 (발행 관문 · 1/2번째")
    rep = check(cur, alt, final=old, prev=prev)
    assert not rep.failed and rows(rep)["pxDate = 최종본 날짜"][3] == "WARN", rep.table()


@pytest.mark.parametrize("budget", [600.0, None])
def test_live_with_the_same_sources_is_as_before(budget):
    """배포 (한도 600) · 감시 (한도 없음): 같은 출처 (다음의 첫 답이 느리고 JSON 이 아님) 로 예전 그대로 — 한도가 지나 다시 묻지 못한 그 종목은
    '다음이 그날 종가를 주지 않음' (no) 이고 남은 종목은 0 · 발행 관문의 값이 켜져 있어도 같아요 (main 과 같은 길: 이 갈래는 gate 가 없을 때
    예전 줄을 그대로 타요)."""
    cur, _, _ = fb_files()
    outs = []
    for on in (False, True):
        ask, victim = edge_ask(cur, "daum", non_json, mode="live", once=False, **({"budget_s": budget} if budget else {}))
        tok = V._PX_ALT_GATE_S.set(0.001) if on else None
        try:
            alt = ask()
        finally:
            if tok is not None:
                V._PX_ALT_GATE_S.reset(tok)
        outs.append((alt, check(cur, alt, mode="live").rows))
    assert outs[0] == outs[1]
    alt = outs[0][0]
    if budget:                                                         # 배포: 한도가 지나 다시 묻지 못함 → 예전 그대로 no (남은 종목 0)
        assert alt["cut"] == 0 and alt["no"] == 1 and alt["noEx"] == [f"{victim} " + "Expecting value: line 1 column 1 (char 0)"[:40]]   # 까닭은 40자까지 (예전 그대로)
        assert alt["err"] == [f"{victim}: Expecting value: line 1 column 1 (char 0) (시간 한도로 다시 묻지 않음)"] and alt["got"] == 206
    else:                                                              # 감시: 한도 없이 다시 물어 받아요
        assert alt["cut"] == 0 and alt["no"] == 0 and alt["got"] == 207 and alt["limit"] is None


def test_a_gated_check_with_nothing_left_equals_the_unlimited_check():
    """남은 종목(cut)이 0 인 발행 관문의 확인은 한도 없이 물었을 때 (main 과 같은 길) 와 결과가 똑같아요 — 무작위 출처 (느림 · 연결 오류 · 시간
    초과 · JSON 이 아님 · 야후 404 · 그날 행 없음 · 다른 종가) 로. 남은 종목이 있으면 그 확인은 쓰지 않아요 (px_alt_confirms)."""
    import random
    cur, prev, old = fb_files()
    px = prices(cur)
    keep = ("closes", "asked", "got", "meta", "disagree", "mustMissing", "err", "no", "noMust", "noEx", "net", "netMust")

    def sources(seed, clk):
        rnd, plan, cnt = random.Random(seed), {}, {}
        p_err = rnd.choice([0.0, 0.05, 0.3]); p_wrong = rnd.choice([0.0, 0.02]); scale = rnd.choice([0.1, 0.3, 1.0, 3.0])

        def pick(kind, code):
            cnt[(kind, code)] = cnt.get((kind, code), 0) + 1
            key = (kind, code, cnt[(kind, code)])
            if key not in plan:
                plan[key] = (rnd.random(), scale * rnd.choice([0.0, 0.5, 1.0, 3.0, 10.0]))
            return plan[key]

        def fd(code, d):
            r, step = pick("d", code)
            clk.t += step
            if r < p_err / 4:
                raise requests.ConnectionError("conn")
            if r < p_err / 2:
                raise non_json()
            if r < p_err:
                return None, "그날 행 0개"
            return px[code] + (1 if r > 1 - p_wrong else 0), "daum"

        def fy(sym, d, close_time=None):
            r, step = pick("y", sym.split(".")[0])
            clk.t += step
            if r < p_err / 3:
                raise requests.Timeout("to")
            if r < 2 * p_err / 3:
                raise yahoo_404()
            if r < p_err:
                raise non_json()
            return px[sym.split(".")[0]], "bar"
        return fd, fy
    both = 0
    for seed in range(120):
        res = []
        for gated in (False, True):
            clk = Clock()
            fd, fy = sources(seed, clk)
            tok = V._PX_ALT_GATE_S.set(600.0) if gated else None
            try:
                res.append(V.http_px_alt(cur["data"], PX, fetch=fy, fetch_daum=fd, workers=1, clock=clk, sleep=lambda s: None,
                                         say=lambda s: None))
            finally:
                if tok is not None:
                    V._PX_ALT_GATE_S.reset(tok)
        plain, gated = res
        if gated["cut"] == 0:
            both += 1
            assert {k: gated[k] for k in keep} == {k: plain[k] for k in keep}, seed
        else:
            assert not V.px_alt_confirms(cur["data"], gated, PX, old, "publish", today=TODAY, now=NOW, special={})[0], seed
    assert 20 <= both < 120                                            # 두 길 모두 시험했어요
