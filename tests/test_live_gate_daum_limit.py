# -*- coding: utf-8 -*-
"""2026-11-20 (Jack, 그대로): "Yes to 10 minutes, but a timeout skips the Daum spot-check with a loud warning; the deploy continues on the
other checks. An outside site must never block a code fix." (네트워크 없음)

사고: 11-20 09:03 KST 배포의 발행 관문(validate_data.py --live)이 19분 동안 멈춰 있었어요 — 관문이 따로 묻는 다음 일별 시세
(http_px_alt · 필수 7 + 표본 200)가 느렸던 것으로 보여요. 요청마다 시간 한도는 있었지만 확인 전체에는 없었어요.
이 시험은 (새 파일 · 다른 시험은 고치지 않았어요):
- 사이트 점검(live)에서 한도(PX_ALT_LIVE_BUDGET_S)에 걸리면 그 확인의 '받은 종목 수' 부분만 경고로 건너뛰고, 다른 검사가 모두 통과하면
  관문은 0 으로 끝나요 (main 까지 · 크게 남는 줄과 GitHub 경고 알림);
- 발행 관문(publish)은 한도가 없어요 — 느린 출처에도 모든 종목을 물어요 · 받은 종목 수가 모자라면 예전 그대로 실패해요;
- 한도 전에 받은 종가가 발행 가격과 다르면 예전과 같은 줄이 실패해요 (005930 정확히 같음 · 99%);
- 파일의 발행 기록 조건(pxSrc · 날짜 · 마감 뒤)은 한도에 걸려도 그대로예요;
- 한도가 지나면 새 요청을 하지 않아요 — 다시 묻기도 (가짜 시계) · 필수 종목을 먼저 물어요;
- 묻는 중인 요청은 끝까지 기다리고, 돌아온 뒤 남는 스레드가 없어요 (진짜 시계 · 따로 띄운 파이썬이 바로 끝나요);
- 시작 줄 (종목 수 · 한도) 이 두 모드 모두 나와요.
"""
import datetime as dt
import os
import subprocess
import sys
import textwrap
import threading
import time

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


def daum(cur, clk=None, step=0.0, calls=None, wrong=None):
    """가짜 다음: 발행 가격 그대로 (wrong 에 있는 종목은 그만큼 다르게) · 물을 때마다 가짜 시계가 step 초 가요."""
    px = prices(cur)

    def f(code, d):
        if calls is not None:
            calls.append((code, clk() if clk else None))
        if clk is not None:
            clk.t += step
        return px.get(code, 1000.0) + (wrong or {}).get(code, 0), "daum"
    return f


def yahoo_same(cur):
    px = prices(cur)
    return lambda sym, d, close_time=None: (px.get(sym.split(".")[0], 1000.0), "bar")


def live_alt(cur, step=10.0, wrong=None, calls=None, lines=None, **k):
    clk = Clock()
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=daum(cur, clk, step, calls, wrong), workers=1, clock=clk,
                        sleep=lambda s: None, say=(lines.append if lines is not None else (lambda s: None)), **k)
    return alt


def check(cur, alt, mode="live", final=None, prev=None, now=NOW, today=TODAY):
    return V.run_checks(cur, prev, final, today, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=now,
                        hilo=hilo_of(cur, V.MUST), alt=alt)


def rows(rep):
    return {r[0]: r for r in rep.rows}


def failed(rep):
    return {r[0] for r in rep.failed}


# ── 1. 한도가 지나면 새 요청을 하지 않아요 (가짜 시계) ─────────────────────────────
def test_the_limit_is_ten_minutes_and_live_only():
    assert V.PX_ALT_LIVE_BUDGET_S == 600
    assert V.px_alt_budget("live") == 600.0 and V.px_alt_budget("live", 5) == 5.0
    assert V.px_alt_budget("publish") is None and V.px_alt_budget("publish", 5) is None and V.px_alt_budget("bootstrap") is None


def test_deadline_stops_new_requests_and_asks_must_haves_first():
    cur, _, _ = fb_files()
    calls, lines = [], []
    alt = live_alt(cur, step=100.0, calls=calls, lines=lines)          # 한 번에 100초 → 0 · 100 · … · 500초에 6번 묻고 600초에 멈춰요
    assert [c for c, _ in calls] == list(V.MUST[:6])                  # 필수 종목 먼저 (코드 순이면 000660 · 005380 … 이 섞여요)
    assert all(t < V.PX_ALT_LIVE_BUDGET_S for _, t in calls)          # 한도가 지난 뒤에는 한 번도 묻지 않았어요
    assert alt["got"] == 6 and alt["cut"] == alt["asked"] - 6 and alt["cutMust"] == [V.MUST[6]] and alt["mustMissing"] == [V.MUST[6]]
    assert alt["limit"] == 600.0 and alt["secs"] == 600.0 and not alt["err"]
    loud = [x for x in lines if x.startswith("!! ")]
    assert len(loud) == 1 and "시간 한도 600초" in loud[0] and "더 묻지 않아요" in loud[0]   # 크게 한 번
    assert V.px_alt_was_cut(alt)


def test_the_limit_is_read_when_called(monkeypatch):
    cur, _, _ = fb_files()
    monkeypatch.setattr(V, "PX_ALT_LIVE_BUDGET_S", 250)
    calls = []
    alt = live_alt(cur, step=100.0, calls=calls)
    assert len(calls) == 3 and alt["limit"] == 250.0 and alt["cut"] == alt["asked"] - 3


def test_a_retry_after_the_deadline_is_not_sent():
    """요청이 실패하면 다시 묻는데 (세 번까지), 한도가 지났으면 다시 묻지 않아요 — 그 종목은 '시간 한도로 건너뜀'."""
    cur, _, _ = fb_files()
    clk, calls, waits = Clock(), [], []

    def slow_fail(code, d):
        calls.append((code, clk.t))
        clk.t += 400.0                                                 # 요청 하나가 자기 시간 한도로 끝나는 데 400초 (가짜)
        raise TimeoutError("read timed out")
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=slow_fail, workers=1, clock=clk, sleep=waits.append, say=lambda s: None)
    assert calls == [("005930", 0.0), ("005930", 400.0)]                # 0초 · 400초에 묻고, 800초에는 다시 묻지 않아요
    assert waits == [1] and alt["got"] == 0 and alt["cut"] == alt["asked"] and not alt["err"]


# ── 2. 발행 관문(publish)은 예전 그대로 ─────────────────────────────────────────
def test_publish_mode_has_no_limit_and_keeps_its_order():
    cur, _, _ = fb_files()
    fast_calls, slow_calls, lines = [], [], []
    fast = V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur, Clock(), 0.0, fast_calls), workers=1,
                         sleep=lambda s: None, say=lambda s: None)
    clk = Clock()
    slow = V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur, clk, 100.0, slow_calls), workers=1, clock=clk,
                         sleep=lambda s: None, say=lines.append, budget_s=5)        # 한도를 주어도 발행 관문은 쓰지 않아요
    assert len(slow_calls) == slow["asked"] == fast["asked"] == len(V.MUST) + V.PX_CHECK_SAMPLE   # 모든 종목을 물었어요 (가짜 시계로 20,700초)
    assert [c for c, _ in slow_calls] == sorted(V.px_alt_pick(cur["data"]))       # 예전 그대로 코드 순
    assert slow["cut"] == 0 and slow["cutMust"] == [] and slow["limit"] is None and slow["secs"] == 100.0 * slow["asked"]
    same = ("date", "mode", "closes", "asked", "got", "meta", "disagree", "mustMissing", "err", "cut", "cutMust", "limit")
    assert {k: slow[k] for k in same} == {k: fast[k] for k in same}
    assert not any(x.startswith("!! ") for x in lines)
    assert not V.px_alt_was_cut(slow)


def test_publish_mode_short_coverage_still_fails():
    """발행 관문에서 받은 종목 수가 모자라면 예전 그대로 실패해요 — 시간 한도라는 기록이 붙어 있어도 (건너뛰지 않아요)."""
    cur, prev, old = fb_files()
    alt = V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur), workers=1, sleep=lambda s: None, say=lambda s: None)
    assert "pxDate = 최종본 날짜" not in failed(check(cur, alt, mode="publish", final=old, prev=prev))
    short = dict(alt, got=int(alt["asked"] * 0.5), cut=alt["asked"] // 2, limit=600.0)
    assert "pxDate = 최종본 날짜" in failed(check(cur, short, mode="publish", final=old, prev=prev))
    assert "pxDate = 최종본 날짜" in failed(check(cur, dict(short, mode="live"), mode="publish", final=old, prev=prev))
    ok, why = V.px_alt_confirms(cur["data"], short, PX, old, "publish", today=TODAY, now=NOW, special={}, cover=False)
    assert not ok and "건너뛸 수 있는 확인이 아니에요" in why


def test_a_live_check_that_was_not_cut_is_judged_as_before():
    """사이트 점검이어도 한도에 걸리지 않았으면 (예: 다음이 빨리 실패) 받은 종목 수가 모자랄 때 예전 그대로 실패해요."""
    cur, _, _ = fb_files()

    def fast_fail(code, d):
        raise ConnectionError("refused")
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=fast_fail, workers=1, sleep=lambda s: None, say=lambda s: None)
    assert alt["cut"] == 0 and alt["got"] == 0 and alt["err"]
    assert "최종본 날짜 계산" in failed(check(cur, alt))
    ok, _ = V.px_alt_confirms(cur["data"], alt, PX, None, "live", today=TODAY, now=NOW, special={}, cover=False)
    assert not ok


# ── 3. 사이트 점검에서 한도에 걸리면: 경고로 건너뛰고, 다른 검사는 그대로 ───────────────────
def test_live_timeout_turns_the_spot_check_into_a_warning():
    cur, _, _ = fb_files()
    full = live_alt(cur, step=0.0)
    rep = check(cur, full)
    assert not rep.failed and rows(rep)["pxDate 최종본 여부"][3] == "PASS"     # 한도에 걸리지 않은 날은 예전 그대로
    part = live_alt(cur, step=10.0)                                               # 60종목 받고 나머지 147종목은 건너뜀
    assert part["got"] == 60 and part["cut"] == part["asked"] - 60 and not part["mustMissing"]
    assert "최종본 날짜 계산" in failed(check(cur, dict(part, cut=0)))           # 한도 기록이 없으면 예전 그대로 실패
    rep = check(cur, part)
    assert not rep.failed, rep.table()
    r = rows(rep)
    assert r["pxDate 최종본 여부"][3] == "WARN"
    assert "시간 한도 600초로 건너뜀" in r["pxDate 최종본 여부"][2] and "확인 60 / 207종목" in r["pxDate 최종본 여부"][2]
    assert "시간 한도로 건너뜀 147" in r["pxDate 최종본 여부"][2] and "Jack 2026-11-20" in r["pxDate 최종본 여부"][2]
    assert r["한국 가격 = 공식 종가"][3] == "WARN" and "받은 60종목만" in r["한국 가격 = 공식 종가"][2]
    assert r["005930 = 공식 종가"][3] == "PASS"                                   # 받은 필수 종목은 예전 그대로 비교해요


def test_live_timeout_after_enough_closes_passes_with_a_warning():
    """한도에 걸렸지만 그 전에 예전 기준(필수 종목 모두 · 표본 90%)을 채웠으면 예전 그대로 통과 — 한도에 걸린 것은 경고로 알려요."""
    cur, _, _ = fb_files()
    alt = live_alt(cur, step=3.0)                                    # 0 · 3 · … · 597초에 200종목 · 7종목 건너뜀
    assert alt["got"] == 200 and alt["cut"] == 7 and not alt["mustMissing"]
    rep = check(cur, alt)
    assert not rep.failed, rep.table()
    r = rows(rep)
    assert r["pxDate 최종본 여부"][3] == "WARN" and "시간 한도로 건너뜀 7종목" in r["pxDate 최종본 여부"][2]
    assert r["한국 가격 = 공식 종가"][3] == "PASS" and r["005930 = 공식 종가"][3] == "PASS"   # 가격 줄은 예전 그대로


def test_live_timeout_before_any_close_warns_without_failing():
    """다음이 처음부터 멈춰 한도 전에 받은 종가가 하나도 없어도 배포는 다른 검사로 계속해요 (Jack: "An outside site must never block a code fix")."""
    cur, _, _ = fb_files()
    clk = Clock()

    def hung(code, d):
        clk.t += 700.0
        raise TimeoutError("read timed out")
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=hung, workers=1, clock=clk, sleep=lambda s: None, say=lambda s: None)
    assert alt["got"] == 0 and alt["cut"] == alt["asked"] and set(alt["cutMust"]) == set(V.MUST)
    rep = check(cur, alt)
    assert not rep.failed, rep.table()
    r = rows(rep)
    assert r["pxDate 최종본 여부"][3] == r["한국 가격 = 공식 종가"][3] == r["005930 = 공식 종가"][3] == "WARN"
    assert r["한국 가격 = 공식 종가"][1] == "비교 못 함" and "받은 종가 없음" in r["한국 가격 = 공식 종가"][2]


def test_live_timeout_keeps_the_file_record_conditions():
    """한도에 걸려도 건너뛰는 것은 관문이 받은 종목 수뿐이에요 — 파일의 발행 기록 · 날짜 · 마감 뒤 조건은 예전 그대로 실패해요."""
    cur, _, _ = fb_files()
    part = live_alt(cur, step=10.0)
    for change in ({"must": ["005930"]}, {"px": V.PX_SRC_LISTING}, {"date": "2026-10-29"}):
        c2, _, _ = fb_files()
        c2["data"]["pxSrc"].update(change)
        assert "최종본 날짜 계산" in failed(check(c2, part)), change
    c2, _, _ = fb_files()
    c2["data"]["pxSrc"]["fb"]["conf"] = 10
    assert "최종본 날짜 계산" in failed(check(c2, part))
    assert "최종본 날짜 계산" in failed(check(cur, dict(part, date=dt.date(2026, 10, 29))))
    assert "최종본 날짜 계산" in failed(check(cur, part, today=PX, now=dt.datetime(2026, 10, 30, 11, 0, tzinfo=V.KST)))   # 끝나지 않은 날
    # 캐시에 pxDate 최종본이 있으면 예전 그대로 그것과 비교해요 (한도에 걸린 확인은 쓰지 않아요)
    fin = {"date": PX, "closes": {c: v + 1 for c, v in prices(cur).items()}, "how": "캐시 최종본"}
    rep = check(cur, part, final=fin)
    assert rows(rep)["pxDate 최종본 여부"][3] == "PASS" and "한국 가격 = 공식 종가" in failed(rep)


# ── 4. 한도 전에 받은 종가가 다르면: 예전과 같은 결과 ──────────────────────────────────
def test_partial_results_with_a_mismatch_fail_as_before():
    cur, _, _ = fb_files()
    got = list(live_alt(cur, step=10.0)["closes"])                    # 한도 전에 받는 60종목 (필수 종목 먼저 · 코드 순)
    assert got[:7] == list(V.MUST) and len(got) == 60
    # 005930 이 다르면: 다 받은 날과 한도에 걸린 날 모두 '005930 = 공식 종가' 실패
    full = live_alt(cur, step=0.0, wrong={"005930": 100})
    part = live_alt(cur, step=10.0, wrong={"005930": 100})
    assert "005930 = 공식 종가" in failed(check(cur, full)) and "005930 = 공식 종가" in failed(check(cur, part))
    # 받은 종목의 1% 넘게 1원씩 다르면: 두 날 모두 '한국 가격 = 공식 종가' 실패 (같은 99% 기준)
    bad = {c: 1 for c in got[7:20]}                                    # 13종목: 다 받은 날 194/207 = 93.7% · 한도에 걸린 날 47/60 = 78.3%
    full = live_alt(cur, step=0.0, wrong=bad)
    part = live_alt(cur, step=10.0, wrong=bad)
    for alt in (full, part):
        rep = check(cur, alt)
        assert "한국 가격 = 공식 종가" in failed(rep), rows(rep)["한국 가격 = 공식 종가"]
        assert "005930 = 공식 종가" not in failed(rep)
    # 같은 호가가 아니면 같지 않아요 (반올림으로 맞추지 않아요) — 한도에 걸린 날도
    part = live_alt(cur, step=10.0, wrong={"005930": 0.5})
    assert "005930 = 공식 종가" in failed(check(cur, part))


# ── 5. main: 배포 · 감시의 관문 실행 (끝 코드 · 로그 · GitHub 알림) ─────────────────────
def run_main(monkeypatch, capsys, cur, step, wrong=None, live=True):
    files = {k: cur[k] for k in ("data", "corp", "disc", "macro")}
    monkeypatch.setattr(V, "load_dir", lambda d: files)
    monkeypatch.setattr(V, "http_listing", lambda d: None)                    # 캐시에 pxDate 최종본 없음
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: hilo_of(cur, V.MUST))
    clk = Clock()
    seen = []

    def alt_fn(data, px, special=None, mode="publish"):                    # main 이 부르는 꼴 그대로 (진짜 함수 · 가짜 출처와 시계)
        seen.append(mode)
        return REAL_HTTP_PX_ALT(data, px, special=special, mode=mode, fetch_daum=daum(cur, clk, step, None, wrong), workers=1, clock=clk,
                                sleep=lambda s: None)
    monkeypatch.setattr(V, "http_px_alt", alt_fn)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    code = V.main((["--live"] if live else []) + ["--dir", "unused", "--today", "2026-10-31"])
    out = capsys.readouterr().out
    assert seen == ["live"]
    return code, out


def test_main_live_timeout_exits_0_with_a_loud_warning(monkeypatch, capsys):
    cur, _, _ = fb_files()
    code, out = run_main(monkeypatch, capsys, cur, step=0.0)
    assert code == 0 and "!! 관문의 두 출처 확인" not in out and "pxDate 최종본 여부" not in "".join(
        ln for ln in out.splitlines() if ln.startswith("::warning"))
    assert "· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 일별 시세 + 발행 기록): 207종목 · 동시 1 · 시간 한도 600초" in out
    code, out = run_main(monkeypatch, capsys, cur, step=10.0)
    assert code == 0, out
    assert "· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 일별 시세 + 발행 기록): 207종목 · 동시 1 · 시간 한도 600초" in out
    assert "!! 관문의 두 출처 확인 시간 한도 600초: 다음 일별 시세를 더 묻지 않아요" in out                   # 그 순간
    assert "!! 관문의 두 출처 확인이 시간 한도 600초에 걸렸어요 (Jack 2026-11-20): 확인 60 / 207종목 · 시간 한도로 건너뜀 147" in out
    assert "걸린 시간 600초" in out
    assert "결과: PASS" in out and "!! 경고  pxDate 최종본 여부: 2026-10-30" in out
    assert any(ln.startswith("::warning title=발행 관문 경고::pxDate 최종본 여부") for ln in out.splitlines())   # 매일 아침 점검이 읽어요
    assert "::error" not in out


def test_main_live_timeout_with_a_wrong_close_still_fails(monkeypatch, capsys):
    cur, _, _ = fb_files()
    code, out = run_main(monkeypatch, capsys, cur, step=10.0, wrong={"005930": 100})
    assert code == 1 and "!! FAIL  005930 = 공식 종가" in out


# ── 6. 묻는 중인 요청은 끝까지 · 남는 스레드 없음 (진짜 시계) ─────────────────────────────
def test_in_flight_requests_finish_and_no_thread_is_left(monkeypatch):
    cur, _, _ = fb_files()
    monkeypatch.setattr(V, "PX_ALT_LIVE_BUDGET_S", 0.3)
    started, done, lock = [], [], threading.Lock()
    px = prices(cur)

    def slow(code, d):
        with lock:
            started.append(code)
        time.sleep(0.2)
        with lock:
            done.append(code)
        return px[code], "daum"
    before = set(threading.enumerate())
    t0 = time.monotonic()
    alt = V.http_px_alt(cur["data"], PX, mode="live", fetch_daum=slow, sleep=lambda s: None, say=lambda s: None)   # 동시 4 (기본)
    took = time.monotonic() - t0
    assert alt["cut"] > 0 and alt["got"] == len(started) == len(done) >= 1    # 시작한 요청은 모두 끝났고 그 값을 썼어요
    assert 0.3 <= took < 0.3 + 0.2 + 1.5                                       # 한도 + 묻는 중인 요청 하나 (여유 1.5초)
    assert alt["got"] <= 4 * 3                                                 # 0 · 0.2초에 시작한 것만 (0.4초에는 한도가 지났어요)
    assert [t for t in threading.enumerate() if t not in before] == []         # 돌아온 뒤 남은 스레드 없음


def test_a_cut_check_does_not_keep_the_process_alive(tmp_path):
    """따로 띄운 파이썬: 사이트 점검의 확인이 한도에 걸린 뒤 바로 끝나요 (남은 스레드가 프로세스를 붙잡지 않아요)."""
    script = tmp_path / "cut_exit.py"
    script.write_text(textwrap.dedent(f"""
        import datetime as dt, sys, threading, time
        sys.path.insert(0, {ROOT!r})
        import validate_data as V
        V.PX_ALT_LIVE_BUDGET_S = 0.5
        stocks = [{{"t": c, "cls": "kr", "price": 1000.0, "dk": "업종 · KOSPI 상장"}} for c in V.MUST]
        stocks += [{{"t": f"9{{i:05d}}", "cls": "kr", "price": 1000.0, "dk": "업종 · KOSDAQ 상장"}} for i in range(300)]
        def slow(code, d):
            time.sleep(0.3)
            return 1000.0, "daum"
        alt = V.http_px_alt({{"stocks": stocks}}, dt.date(2026, 10, 30), mode="live", fetch_daum=slow, sleep=lambda s: None)
        print("cut", alt["cut"], "got", alt["got"], "threads", threading.active_count(), flush=True)
    """), encoding="utf-8")
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    took = time.monotonic() - t0
    assert r.returncode == 0, r.stderr
    last = r.stdout.strip().splitlines()[-1].split()
    assert last[0] == "cut" and int(last[1]) > 0 and last[4:] == ["threads", "1"], r.stdout
    assert "· 관문의 두 출처 확인 시작" in r.stdout and "!! 관문의 두 출처 확인 시간 한도 0초" in r.stdout
    assert took < 20, took                                                     # 파이썬 시작 + 0.5 + 0.3초 — 붙잡히면 훨씬 길어요


# ── 7. 시작 줄 (두 모드 모두 · 로그만) ───────────────────────────────────────────────
def test_start_line_in_both_modes():
    cur, _, _ = fb_files()
    lines = []
    live_alt(cur, step=0.0, lines=lines)
    assert lines == ["· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 일별 시세 + 발행 기록): 207종목 · 동시 1 · "
                     "시간 한도 600초 (사이트 점검 — 넘으면 새로 묻지 않고, 이 확인은 건너뛰고 경고)"]
    lines = []
    V.http_px_alt(cur["data"], PX, fetch=yahoo_same(cur), fetch_daum=daum(cur), sleep=lambda s: None, say=lines.append)
    assert lines == ["· 관문의 두 출처 확인 시작 (2026-10-30 · 다음 × 야후): 207종목 · 동시 4 · 시간 한도 없음 (발행 관문 · 예전 그대로)"]
