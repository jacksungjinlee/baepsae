# -*- coding: utf-8 -*-
"""2026-11-20: 2차 출처(다음 × 야후)의 종목마다 묻는 단계에 시간 한도 (fetch_data.KR_FB_PHASE_BUDGET_S). (네트워크 없음)

사고: 11-19 23:19 · 11-20 00:34 KST 시험 실행 두 번이 '데이터 수집'에서 61~74분 멈춰 취소됐어요. 마지막 로그는 1차 출처 목록 줄
("· 종목 목록: 2026-11-16 최종본 …") — 2차 출처의 메모는 모두 끝난 뒤에 한꺼번에 나와서 어디서 멈췄는지 몰랐어요.
요청마다 시간 한도는 있었지만 단계 전체에는 없었어요. 이 시험은:
- 느린 가짜 출처: 한도가 지나면 새 종목을 묻지 않고, 크게 남기고, 남은 종목은 확인 못 한 종목 (그날 파일에서 빠져요) — 필수 종목은 먼저 물어요;
- 빠른 가짜 출처: 아무것도 바뀌지 않아요;
- pxSrc.fb.cut (1차 출처 날은 pxSrc.chk.cut) 에 한도에 걸린 수가 적히고, 관문은 경고만 해요 (새 실패 줄 없음);
- 1차 출처(자원봉사 최종본) 날은 2차 출처를 부르지 않아요 (예전 그대로);
- 이 길의 HTTP 요청은 모두 시간 한도가 있어요 (KOSPI 일봉 캐시 CSV 까지).
시계는 가짜 (clock 인자) — 실제로 기다리지 않아요.
"""
import datetime as dt
import functools
import inspect
import json
import os
import socket
import sys

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "kr_two_source")
D16, D17, D18 = (dt.date(2026, 11, d) for d in (16, 17, 18))
KONEX = "496320"
NOW = dt.datetime(2026, 11, 19, 4, 0, tzinfo=F.KST)


class Clock:
    """가짜 시계: 가짜 출처가 물을 때마다 앞으로 가요."""
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def listing(name):
    return F.parse_listing_csv(open(os.path.join(FX, f"krx_{name}.csv"), encoding="utf-8").read())


def daum_raw():
    return json.load(open(os.path.join(FX, "daum_days.json"), encoding="utf-8"))


def yahoo():
    js = json.load(open(os.path.join(FX, "yahoo_closes.json"), encoding="utf-8"))
    return {c: {dt.date.fromisoformat(d): v for d, v in v.items()} for c, v in js.items()}


def no_fill(*a, **k):
    return {"need": 0, "bar": 0, "meta": 0, "none": 0, "fail": 0, "metaCodes": set()}


def bar_chart(d, close):
    """야후 차트 응답 result[0] 의 최소 모양: 그날(KST) 일봉 하나."""
    ts = int(dt.datetime.combine(d, dt.time(9, 0), F.KST).timestamp())
    return {"timestamp": [ts], "indicators": {"quote": [{"close": [close]}]}, "meta": {}}


# ── 1. 다음 일별 시세: 느린 출처는 한도에서 멈추고, 필수 종목은 먼저 ─────────────────────
def test_daum_budget_stops_a_slow_fetcher_must_first_and_says_so():
    clk, asked, said = Clock(), [], []

    def slow(code, n):
        asked.append(code)
        clk.t += 100                                    # 한 종목에 100초
        return {"data": []}
    codes = {"000010", "000020", "000030", "000040", "105560"}       # 105560 KB금융 = 필수 종목 (코드 순이면 마지막)
    out, failed, cut = F.fetch_daum_all(codes, 5, fetch=slow, workers=1, budget_s=250, clock=clk, say=said.append)
    assert asked == ["105560", "000010", "000020"]                   # 0 · 100 · 200초에 물음 → 300초에는 한도(250초) 지남
    assert sorted(out) == ["000010", "000020", "105560"] and failed == [] and cut == ["000030", "000040"]
    assert len(said) == 1 and said[0].lstrip().startswith("!! 2차 출처 시간 한도 250초") and "확인 못 한 종목" in said[0]


def test_daum_budget_with_the_real_clock():
    """진짜 시계 (time.monotonic · 기본값): 한 종목에 0.05초 · 한도 0.15초 → 몇 종목만 묻고 나머지는 묻지 않아요 (2초 안에 끝나요)."""
    import time
    codes = {f"{i:06d}" for i in range(10, 110, 10)}

    def slow(code, n):
        time.sleep(0.05)
        return {"data": []}
    t0 = time.monotonic()
    out, failed, cut = F.fetch_daum_all(codes, 5, fetch=slow, workers=1, budget_s=0.15, say=lambda s: None)
    assert cut and out and len(out) + len(cut) == len(codes) and failed == [] and time.monotonic() - t0 < 2.0


def test_daum_fast_fetcher_is_unaffected():
    clk, said = Clock(), []
    codes = {f"{i:06d}" for i in range(10, 60, 10)} | {"005930"}

    def fast(code, n):
        if code == "000030":
            raise RuntimeError("HTTP 400")             # 답하지 않은 종목은 예전처럼 '못 받음'
        return {"data": []}
    out, failed, cut = F.fetch_daum_all(codes, 5, fetch=fast, workers=3, budget_s=250, clock=clk, say=said.append)
    assert set(out) == codes - {"000030"} and failed == ["000030"] and cut == [] and said == []


# ── 2. 야후 일괄 종가: 남은 묶음을 묻지 않아요 · 필수 종목은 첫 묶음 · 요청마다 시간 한도 ─────────
def test_yahoo_batch_budget_skips_the_remaining_chunks():
    clk, said, calls = Clock(), [], []

    def dl(part, start, end, **kw):
        calls.append((list(part), kw.get("timeout")))
        clk.t += 100
        idx = pd.to_datetime(["2026-11-17", "2026-11-18"])
        cols = pd.MultiIndex.from_product([list(part), ["Close"]])
        return pd.DataFrame([[1000.0] * len(part), [1010.0] * len(part)], index=idx, columns=cols)
    cm = {c: "KOSPI" for c in ("000010", "000020", "000030", "000040", "000050", "000060", "005930")}
    cm[KONEX] = "KONEX"
    out, failed, cut = F.fetch_yahoo_kr_closes(cm, D17, D18 + dt.timedelta(days=1), chunk=2, budget_s=150, clock=clk, download=dl,
                                               say=said.append)
    assert [p for p, _ in calls] == [["005930.KS", "000010.KS"], ["000020.KS", "000030.KS"]]    # 필수 종목이 첫 묶음 · 셋째 묶음부터 한도
    assert all(t == F.KR_FB_YAHOO_TIMEOUT for _, t in calls)
    assert sorted(out) == ["000010", "000020", "000030", "005930"] and failed == 0 and cut == 3   # 000040 · 000050 · 000060
    assert out["005930"] == {D17: 1000.0, D18: 1010.0} and KONEX not in out
    assert len(said) == 1 and "2차 출처 시간 한도 150초" in said[0]


def test_yahoo_batch_fast_is_unaffected():
    clk = Clock()

    def dl(part, start, end, **kw):
        idx = pd.to_datetime(["2026-11-18"])
        return pd.DataFrame([[2000.0] * len(part)], index=idx, columns=pd.MultiIndex.from_product([list(part), ["Close"]]))
    cm = {c: "KOSDAQ" for c in ("000010", "000020", "000030")}
    out, failed, cut = F.fetch_yahoo_kr_closes(cm, D18, D18 + dt.timedelta(days=1), chunk=2, budget_s=150, clock=clk, download=dl,
                                               say=lambda s: (_ for _ in ()).throw(AssertionError(s)))
    assert out == {c: {D18: 2000.0} for c in cm} and failed == 0 and cut == 0


# ── 3. 야후 차트 다시 읽기 (마지막 날 종가가 빈 종목) ───────────────────────────────
def test_fill_day_budget_stops_and_counts_the_rest():
    clk, said, asked = Clock(), [], []

    def slow(sym):
        asked.append(sym)
        clk.t += 100
        return bar_chart(D18, 5000.0)
    cm = {c: "KOSPI" for c in ("000010", "000020", "000030", "000040", "035420")}    # 035420 NAVER = 필수 종목
    yahoo_ = {}
    out = F.yahoo_fill_day(yahoo_, cm, D18, dt.time(15, 30), fetch=slow, workers=1, budget_s=250, clock=clk, say=said.append)
    assert asked == ["035420.KS", "000010.KS", "000020.KS"]
    assert out["need"] == 5 and out["bar"] == 3 and out["cut"] == 2 and out["fail"] == 0
    assert sorted(yahoo_) == ["000010", "000020", "035420"]               # 묻지 못한 종목은 그날 야후 종가가 없어요 → 확인 못 함
    assert len(said) == 1 and "2차 출처 시간 한도 250초" in said[0]


def test_fill_day_fast_is_unaffected():
    clk = Clock()
    yahoo_ = {}
    out = F.yahoo_fill_day(yahoo_, {"000010": "KOSPI", "000020": "KOSDAQ"}, D18, dt.time(15, 30), fetch=lambda s: bar_chart(D18, 7.0),
                           budget_s=250, clock=clk, say=lambda s: (_ for _ in ()).throw(AssertionError(s)))
    assert out["cut"] == 0 and out["bar"] == 2 and yahoo_ == {"000010": {D18: 7.0}, "000020": {D18: 7.0}}


# ── 4. 2차 출처 전체: 묻지 못한 종목은 확인 못 한 종목 (빠짐) · 크게 남기고 · pxSrc.fb.cut 에 적어요 ─────
def slow_daum(clk, step=100):
    raw = daum_raw()

    def fetch(code, n):
        clk.t += step
        return raw[code]
    return fetch


def test_fallback_leaves_the_rest_unconfirmed_and_records_the_hit(monkeypatch):
    monkeypatch.setattr(F, "KR_FB_PHASE_BUDGET_S", 950)          # 모듈 값은 부를 때 읽어요 (단계 셋 모두)
    clk, said = Clock(), []
    uni = listing("2026-11-17_1529")
    fetch_daum = functools.partial(F.fetch_daum_all, fetch=slow_daum(clk), workers=1, clock=clk, say=said.append)
    out, notes = F.kr_fallback_days([D17], lambda d: (uni, "시험"), NOW, {}, fetch_daum=fetch_daum,
                                    fetch_yahoo=lambda cm, a, b: (yahoo(), 0),   # 예전 모양(두 칸)의 가짜도 그대로 돼요
                                    fill_day=no_fill, say=said.append)
    fr, st = out[D17]
    # 필수 7종목 → 나머지 코드 순 (001570 · 011810 · 0126Z0 · 047400 · 090460): 10종목을 묻고 1,000초에 한도(950초) → 047400 · 090460 은 묻지 못함
    assert st["cut"] == {"s": 950, "daum": 2, "yahoo": 0, "fill": 0}
    assert {"047400", "090460"} <= set(st["noDaum"]) and not {"047400", "090460"} & set(fr["Code"])     # 확인 못 함 → 빠져요
    assert st["must"] == [] and set(V.MUST) <= set(fr["Code"])                                            # 필수 종목은 먼저 물었어요
    cut_notes = [n for n in notes if "시간 한도" in n and n.startswith("!! ")]
    assert any("다음 일별 시세: 받은 10 / 대상 12 — 나머지 2종목은 확인 못 한 종목" in n for n in cut_notes), notes
    assert any(s.lstrip().startswith("!! 2차 출처 시간 한도 950초: 다음 일별 시세") for s in said)          # 그 순간 바로 남겨요
    assert any(s.startswith("· 2차 출처: 다음 일별 시세 묻는 중") for s in said)                             # 단계를 시작할 때도
    assert F.px_src_counts(st)["cut"] == {"s": 950, "daum": 2, "yahoo": 0, "fill": 0}
    loud, txt = F.kr_fb_note(D17, st, {})
    assert loud and "시간 한도 950초로 묻지 못한 종목 (다음 2" in txt


def test_second_source_pxsrc_carries_the_hit_and_the_gate_only_warns(monkeypatch):
    monkeypatch.setattr(F, "KR_FB_PHASE_BUDGET_S", 950)
    clk = Clock()
    fb = functools.partial(F.kr_fallback_days, fetch_daum=functools.partial(F.fetch_daum_all, fetch=slow_daum(clk), workers=1, clock=clk,
                                                                            say=lambda s: None),
                           fetch_yahoo=lambda cm, a, b: (yahoo(), 0), fill_day=no_fill, say=lambda s: None)
    px, lst, _, src, logs, _ = F.kr_second_source(D16, listing("2026-11-16_2211"), [D17], NOW, {}, lambda d: (listing("2026-11-17_1529"), "시험"),
                                                   fallback=fb)
    assert px == D17 and src["px"] == V.PX_SRC_FB and src["fb"]["cut"]["daum"] == 2
    assert not {"047400", "090460"} & set(lst["Code"])                                                    # 그날 파일에 없어요
    assert any(loud and "다음 일별 시세: 받은 10 / 대상 12" in txt for loud, txt in logs)
    rep = V.Report()
    V.check_px_cut(rep, src)
    (name, val, rule, status), = rep.rows
    assert status == "WARN" and "다음 2" in val and "950초" in rule and not rep.failed


def test_gate_row_without_a_hit_passes_and_old_files_skip():
    rep = V.Report()
    V.check_px_cut(rep, {"px": V.PX_SRC_FB, "fb": {"cut": F.fb_cut_record()}})
    V.check_px_cut(rep, {"px": V.PX_SRC_LISTING, "chk": {"cut": F.fb_cut_record({"yahoo": 0, "fill": 0})}})
    V.check_px_cut(rep, {"px": V.PX_SRC_FB, "fb": {"n": 1}})                    # 이 줄 전 발행본 (기록 없음)
    V.check_px_cut(rep, {"px": V.PX_SRC_LISTING, "chk": {"cut": {"s": 600, "daum": 0, "yahoo": 3, "fill": 1}}})
    V.check_px_cut(rep, {"px": V.PX_SRC_FB, "fb": {"cut": {"s": 600, "daum": "x"}}})   # 모양이 이상해도 경고만
    st = [r[3] for r in rep.rows]
    assert st == ["PASS", "PASS", "SKIP", "WARN", "WARN"] and not rep.failed
    assert rep.rows[0][1] == "없음" and "1차 출처 날" in rep.rows[3][2]


def test_check_px_src_shows_the_row_for_a_listing_day():
    data = {"pxDate": "2026-11-18", "pxSrc": {"v": 1, "px": V.PX_SRC_LISTING, "date": "2026-11-18", "n": {V.PX_SRC_LISTING: 2500}, "must": [],
                                              "fb": None, "chk": {"src": "yahoo", "n": 207, "same": 207, "none": 0, "diff": [],
                                                                  "cut": F.fb_cut_record()}}}
    rep = V.Report()
    V.check_px_src(rep, data, D18 + dt.timedelta(days=1))
    row = [r for r in rep.rows if r[0] == "가격 확인 시간 한도 (경고만)"]
    assert row and row[0][3] == "PASS" and not rep.failed


# ── 5. 1차 출처(자원봉사 최종본) 날은 예전 그대로 ────────────────────────────────────
def test_volunteer_final_day_never_calls_the_second_source():
    prim = listing("2026-11-16_2211")

    def boom(*a, **k):
        raise AssertionError("1차 출처 날에 2차 출처를 불렀어요")
    px, lst, known, src, logs, (full, dshr) = F.kr_second_source(D16, prim, [], NOW, {}, None, fallback=boom)
    assert px == D16 and lst is prim and known == {} and logs == [] and src["fb"] is None and src["px"] == V.PX_SRC_LISTING


def test_fb_order_keeps_every_code():
    codes = {"000010", "105560", "005930", "999990"}
    assert F.fb_order(codes) == ["005930", "105560", "000010", "999990"]
    assert sorted(F.fb_order(codes)) == sorted(codes) and F.fb_order(set()) == []


# ── 6. 이 길의 HTTP 요청은 모두 시간 한도가 있어요 · 파이썬 출력은 버퍼에 모으지 않아요 ───────────
def test_every_request_on_the_path_has_a_timeout():
    for fn in (F._fetch_daum_days, F._fetch_yahoo_chart, F._fetch_listing_csv, F._listing_commit_kst):
        src = inspect.getsource(fn)
        assert ".get(" in src and "timeout=" in src, fn.__name__
    assert "timeout=KR_FB_YAHOO_TIMEOUT" in inspect.getsource(F.fetch_yahoo_kr_closes)
    assert "with_socket_timeout(lambda: fdr.DataReader(KR_INDEX" in inspect.getsource(F.fetch_korea)    # FinanceDataReader 는 한도 없이 받아요


def test_with_socket_timeout_sets_and_restores():
    before = socket.getdefaulttimeout()
    seen = F.with_socket_timeout(socket.getdefaulttimeout, 60)
    assert seen == 60 and socket.getdefaulttimeout() == before
    try:
        F.with_socket_timeout(lambda: 1 / 0, 60)
    except ZeroDivisionError:
        pass
    assert socket.getdefaulttimeout() == before


def test_data_step_runs_python_unbuffered():
    wf = yaml.safe_load(open(os.path.join(ROOT, ".github", "workflows", "update-data.yml"), encoding="utf-8"))
    step = next(s for s in wf["jobs"]["update"]["steps"] if s.get("name") == "데이터 수집")
    assert str(step["env"].get("PYTHONUNBUFFERED")) == "1"
    assert step["run"].strip().splitlines()[-1] == "python fetch_data.py"


def test_budget_value_is_above_normal_phase_times():
    """평소 단계 시간 (GitHub 실행 4번): 다음 108~144초 · 야후 일괄 111~178초 · 다시 읽기 0~41초 — 한도는 가장 느린 것의 3배 넘게."""
    assert F.KR_FB_PHASE_BUDGET_S >= 3 * 178 and F.KR_FB_PHASE_BUDGET_S <= 15 * 60
