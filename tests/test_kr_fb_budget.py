# -*- coding: utf-8 -*-
"""2026-11-20: 2차 출처(다음 × 야후)의 종목마다 묻는 단계에 시간 한도 (fetch_data.KR_FB_PHASE_BUDGET_S). (네트워크 없음)

사고: 11-19 23:19 · 11-20 00:34 KST 시험 실행 두 번이 '데이터 수집'에서 61~74분 멈춰 취소됐어요. 마지막 로그는 1차 출처 목록 줄
("· 종목 목록: 2026-11-16 최종본 …") — 2차 출처의 메모는 모두 끝난 뒤에 한꺼번에 나와서 어디서 멈췄는지 몰랐어요.
요청마다 시간 한도는 있었지만 단계 전체에는 없었어요. 이 시험은:
- 느린 가짜 출처: 한도가 지나면 새 종목을 묻지 않고, 크게 남기고, 남은 종목은 확인 못 한 종목 (그날 파일에서 빠져요);
- 묻는 순서: 필수 종목 → 1차 출처 최종본 시가총액 큰 순 → 모르는 종목 (리뷰 M1) — 한도에 걸려도 발행하는 상위 종목은 그대로;
- 야후는 종목마다 차트 (리뷰 S1): 멈춘 요청이 있어도 단계는 한도 + 요청 하나 안에 끝나요;
- 빠른 가짜 출처: 아무것도 바뀌지 않아요;
- pxSrc.fb.cut (1차 출처 날은 pxSrc.chk.cut) 에 한도에 걸린 수가 적히고, 관문은 경고만 해요 (새 실패 줄 없음);
- 한도 때문에 필수 종목을 확인하지 못하면 그날은 쓰지 않고, 관문의 'pxDate 뒤 끝난 거래일' 줄이 발행을 멈춰요 (리뷰 S3);
- 1차 출처(자원봉사 최종본) 날은 2차 출처를 부르지 않아요 (예전 그대로);
- 이 길의 HTTP 요청은 모두 시간 한도가 있어요 (KOSPI 일봉 캐시 CSV 까지).
시계는 대부분 가짜 (clock 인자) — 실제로 기다리지 않아요.
"""
import datetime as dt
import functools
import inspect
import json
import math
import os
import random
import socket
import sys
import threading
import time

import pandas as pd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
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


def chart(bars, meta=None):
    """야후 차트 응답 result[0] 의 최소 모양: [(날짜, 종가)] 일봉 (09:00 KST)."""
    ts = [int(dt.datetime.combine(d, dt.time(9, 0), F.KST).timestamp()) for d, _ in bars]
    return {"timestamp": ts, "indicators": {"quote": [{"close": [c for _, c in bars]}]}, "meta": meta or {}}


def say_nothing(s):
    raise AssertionError(f"빠른 출처인데 시간 한도 줄이 나왔어요: {s}")


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
    codes = {f"{i:06d}" for i in range(10, 110, 10)}

    def slow(code, n):
        time.sleep(0.05)
        return {"data": []}
    t0 = time.monotonic()
    out, failed, cut = F.fetch_daum_all(codes, 5, fetch=slow, workers=1, budget_s=0.15, say=lambda s: None)
    assert cut and out and len(out) + len(cut) == len(codes) and failed == [] and time.monotonic() - t0 < 2.0


def test_daum_fast_fetcher_is_unaffected():
    clk = Clock()
    codes = {f"{i:06d}" for i in range(10, 60, 10)} | {"005930"}

    def fast(code, n):
        if code == "000030":
            raise RuntimeError("HTTP 400")             # 답하지 않은 종목은 예전처럼 '못 받음'
        return {"data": []}
    out, failed, cut = F.fetch_daum_all(codes, 5, fetch=fast, workers=3, budget_s=250, clock=clk, say=say_nothing)
    assert set(out) == codes - {"000030"} and failed == ["000030"] and cut == []


# ── 2. 묻는 순서: 필수 종목 → 1차 출처 최종본 시가총액 큰 순 → 모르는 종목 (리뷰 M1) ─────────────
def test_order_is_must_then_market_cap_then_unknown():
    caps = {"373220": 7.1e13, "000010": 3e9, "402340": 2.4e13, "000020": None, "000030": float("nan"), "000040": 0}
    codes = {"373220", "000010", "402340", "000020", "000030", "000040", "105560"}
    order = F.fb_order(codes, caps=caps)
    assert order == ["105560", "373220", "402340", "000010", "000020", "000030", "000040"]
    assert order.index("373220") < order.index("000010")                 # 큰 종목(코드가 뒤)이 작은 종목(코드가 앞)보다 먼저
    assert F.fb_order(codes) == ["105560", "000010", "000020", "000030", "000040", "373220", "402340"]   # caps 없음: 코드 순
    assert F.fb_order(["402340", "000010", "105560"]) == ["105560", "402340", "000010"]                  # 차례가 있으면 그대로
    assert F.kr_fb_caps(pd.DataFrame([{"Code": "373220", "Marcap": 7.1e13}, {"Code": "000010", "Marcap": None},
                                      {"Code": "000020", "Marcap": "x"}])) == {"373220": 7.1e13}
    assert F.kr_fb_caps(None) == {}


def test_fallback_asks_in_market_cap_order_from_the_primary_listing():
    uni = listing("2026-11-17_1529")
    asked = []

    def fetch_daum(codes, n):
        asked.extend(codes)
        return {}, []
    caps = F.kr_fb_caps(listing("2026-11-16_2211"))                       # 1차 출처 최종본 (시가총액 100%)
    F.kr_fallback_days([D17], lambda d: (uni, "시험"), NOW, {}, fetch_daum=fetch_daum, fetch_yahoo=lambda cm, a, b: ({}, 0),
                       fill_day=no_fill, say=lambda s: None, caps=caps)
    must = [c for c in V.MUST if c in asked]
    assert asked[:len(must)] == must and KONEX not in asked
    rest = asked[len(must):]
    known = [c for c in rest if c in caps]
    assert known == sorted(known, key=lambda c: -caps[c]) and rest[:len(known)] == known


def sim_universe(seed, cut, noise, order_caps=True, unconf=0.012):
    """2,772종목 (코스피 · 코스닥 · 코넥스 빼고) 을 다음에 물을 때 마지막 cut 종목을 묻지 못하면, 발행하는 상위 MAX_KR 종목 중 빠지는 수.
    1차 출처 시가총액 (로그정규) · 그날 시가총액 = 그 값 ± noise · 두 출처가 달라 원래도 빠지는 종목 unconf."""
    rnd = random.Random(seed)
    codes = list(F.MUST_KR) + [f"{200000 + i * 10:06d}" for i in range(2772 - len(F.MUST_KR))]
    caps = {c: math.exp(rnd.gauss(25.3, 1.7)) for c in codes}
    for i, c in enumerate(F.MUST_KR):
        caps[c] = 1e15 / (i + 1)
    day = {c: v * (1 + rnd.uniform(-noise, noise)) for c, v in caps.items()}
    bad = {c for c in codes if c not in F.MUST_KR and rnd.random() < unconf}
    clk = Clock()

    def fetch(code, n):
        clk.t += 1
        return {"data": []}
    order = F.fb_order(set(codes), first=(), caps=caps if order_caps else None)
    out, failed, cut_codes = F.fetch_daum_all(order, 5, fetch=fetch, workers=1, budget_s=len(codes) - cut, clock=clk, say=lambda s: None)
    assert len(cut_codes) == cut

    def published(conf):
        df = pd.DataFrame([{"Code": c, "Marcap": day[c], "Amount": 1.0} for c in conf])
        return set(F.select_kr_universe(df, F.MAX_KR)["Code"])
    base = published([c for c in codes if c not in bad])
    got = published([c for c in codes if c in out and c not in bad])
    return len(base - got)


def test_a_cut_in_cap_order_spares_the_published_top_stocks():
    """평소 2차 출처 날: 2,772종목 중 ~33종목은 두 출처가 달라 빠지고 상위 2,500종목을 발행해요 → 여유는 약 240종목.
    시가총액 순이면 한도에 걸려 빠지는 것은 가장 작은 종목들이라 발행 목록이 그대로예요. 코드 순(예전)이면 큰 종목도 빠져요."""
    for seed in (1, 3, 11):
        assert sim_universe(seed, 200, 0.02) == 0                       # 200종목 묻지 못함 · 그날 시가총액이 ±2% 달라도
        assert sim_universe(seed, 240, 0.0) == 0
        assert sim_universe(seed, 240, 0.02, order_caps=False) >= 150     # 코드 순이었다면 발행할 종목 150개 넘게 빠져요


# ── 3. 야후 일봉 종가: 종목마다 차트 · 한도가 지나면 묻지 않아요 · 멈춘 요청이 있어도 한도 + 요청 하나 (리뷰 S1) ─────
def test_yahoo_chart_closes_reads_the_bars_in_range():
    res = chart([(D16, 196800.0), (D17, 190300.0), (D18, None), (D18 + dt.timedelta(days=1), 1.0)])
    assert F.yahoo_chart_closes(res, D16, D18 + dt.timedelta(days=1)) == {D16: 196800.0, D17: 190300.0}   # 빈 종가 · 범위 밖은 빼요
    dup = chart([(D17, 190300.0), (D17, 190400.0), (D16, 1.0)])
    assert F.yahoo_chart_closes(dup, D16, D18) == {D16: 1.0}                                               # 같은 날 다른 값 → 그 날 빼요
    assert F.yahoo_chart_closes({}, D16, D18) == {}


def test_yahoo_budget_stops_a_slow_source_must_first():
    clk, said, asked = Clock(), [], []

    def slow(sym, start, end):
        asked.append(sym)
        clk.t += 100
        return chart([(D17, 1000.0), (D18, 1010.0)])
    cm = {c: "KOSPI" for c in ("000010", "000020", "000030", "000040", "005930")}
    cm[KONEX] = "KONEX"
    out, failed, cut = F.fetch_yahoo_kr_closes(cm, D17, D18 + dt.timedelta(days=1), fetch=slow, workers=1, budget_s=250, clock=clk,
                                               say=said.append)
    assert asked == ["005930.KS", "000010.KS", "000020.KS"] and KONEX not in out
    assert sorted(out) == ["000010", "000020", "005930"] and failed == 0 and cut == 2
    assert out["005930"] == {D17: 1000.0, D18: 1010.0}
    assert len(said) == 1 and "2차 출처 시간 한도 250초" in said[0]


def test_yahoo_phase_is_bounded_even_when_a_request_hangs():
    """진짜 시계: 한 종목의 요청이 1초 동안 멈춰도 단계는 한도(0.3초) + 그 요청 하나 안에 끝나고, 나머지는 묻지 않아요."""
    gate = threading.Event()

    def fetch(sym, start, end):
        if sym.startswith("000020"):
            gate.wait(1.0)                              # 멈춘 요청 (자기 시간 한도까지)
        else:
            time.sleep(0.05)
        return chart([(D18, 5.0)])
    cm = {f"{i:06d}": "KOSDAQ" for i in range(10, 210, 10)}
    t0 = time.monotonic()
    out, failed, cut = F.fetch_yahoo_kr_closes(cm, D18, D18 + dt.timedelta(days=1), fetch=fetch, workers=2, budget_s=0.3, say=lambda s: None)
    took = time.monotonic() - t0
    assert cut > 0 and "000020" in out and len(out) + cut == len(cm) and failed == 0
    assert took < 0.3 + 1.0 + 0.7, took


def test_yahoo_fast_is_unaffected():
    clk = Clock()

    def fetch(sym, start, end):
        if sym.startswith("000030"):
            raise RuntimeError("HTTP 404")
        return chart([(D18, 2000.0)])
    cm = {c: "KOSDAQ" for c in ("000010", "000020", "000030")}
    out, failed, cut = F.fetch_yahoo_kr_closes(cm, D18, D18 + dt.timedelta(days=1), fetch=fetch, budget_s=150, clock=clk, say=say_nothing)
    assert out == {"000010": {D18: 2000.0}, "000020": {D18: 2000.0}} and failed == 1 and cut == 0


def test_fill_day_budget_stops_and_counts_the_rest():
    clk, said, asked = Clock(), [], []

    def slow(sym):
        asked.append(sym)
        clk.t += 100
        return chart([(D18, 5000.0)])
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
    out = F.yahoo_fill_day(yahoo_, {"000010": "KOSPI", "000020": "KOSDAQ"}, D18, dt.time(15, 30), fetch=lambda s: chart([(D18, 7.0)]),
                           budget_s=250, clock=clk, say=say_nothing)
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
    # caps 없음 → 필수 7종목 → 나머지 코드 순 (001570 · 011810 · 0126Z0 · 047400 · 090460): 10종목을 묻고 1,000초에 한도(950초)
    assert st["cut"] == {"s": 950, "daum": 2, "yahoo": 0, "fill": 0}
    assert {"047400", "090460"} <= set(st["noDaum"]) and not {"047400", "090460"} & set(fr["Code"])     # 확인 못 함 → 빠져요
    assert st["must"] == [] and set(V.MUST) <= set(fr["Code"])                                            # 필수 종목은 먼저 물었어요
    cut_notes = [n for n in notes if "시간 한도" in n and n.startswith("!! ")]
    assert any("다음 일별 시세: 받은 10 / 대상 12 — 나머지 2종목은 확인 못 한 종목" in n for n in cut_notes), notes
    assert any(s.lstrip().startswith("!! 2차 출처 시간 한도 950초: 다음 일별 시세") for s in said)          # 그 순간 바로 남겨요
    assert any(s.startswith("· 2차 출처: 다음 일별 시세 묻는 중") for s in said)                             # 단계를 시작할 때도
    assert any("2차 출처 묻는 순서" in s and "코드 순" in s for s in said)
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


def test_budget_before_a_must_have_keeps_the_volunteer_day_and_the_gate_stops(monkeypatch):
    """리뷰 S3: 한도가 필수 종목을 확인하기 전에 끝나면 그날은 쓰지 않아요 → pxSrc 는 1차 출처(자원봉사 최종본) 그대로 · 2차 출처 기록에
    한도가 남고 · 관문의 'pxDate 뒤 끝난 거래일 없음' 줄이 발행을 멈춰요 (예전 가격을 오늘 날짜로 내지 않아요)."""
    monkeypatch.setattr(F, "KR_FB_PHASE_BUDGET_S", 350)          # 필수 7종목 중 4종목만 물어요 (0 · 100 · 200 · 300초)
    clk = Clock()
    fb = functools.partial(F.kr_fallback_days, fetch_daum=functools.partial(F.fetch_daum_all, fetch=slow_daum(clk), workers=1, clock=clk,
                                                                            say=lambda s: None),
                           fetch_yahoo=lambda cm, a, b: (yahoo(), 0), fill_day=no_fill, say=lambda s: None)
    prim = listing("2026-11-16_2211")
    px, lst, known, src, logs, _ = F.kr_second_source(D16, prim, [D17], NOW, {}, lambda d: (listing("2026-11-17_1529"), "시험"), fallback=fb)
    assert px == D16 and lst is prim and known == {} and src["px"] == V.PX_SRC_LISTING
    assert src["fb"]["cut"]["daum"] == 8 and len(src["fb"]["must"]) == 3 and src["fbDate"] == D17.isoformat()
    assert any(loud and "필수 종목을 모두 확인한 날이 없어요" in txt for loud, txt in logs)
    # 관문: 이 data.json (pxDate 11-16) 을 11-18 에 보면 11-17 이 끝난 거래일 → 실패 · 시간 한도 줄은 2차 출처 기록을 보여요 (경고)
    fd = __import__("fixture_data")
    cur, closes = fd.build(px_date="2026-11-16", us_date="2026-11-17")
    prev, _ = fd.build(px_date="2026-11-13", us_date="2026-11-14", price_shift=-0.01)
    cur["data"]["pxSrc"] = F.px_src_final(src, cur["data"]["stocks"])
    final = {"date": D16, "closes": closes, "how": "시험"}
    rep = V.run_checks(cur, prev, final, D18, count_between=lambda a, b: 1, sessions={"dates": [D16, D17], "src": "시험"},
                       now=dt.datetime(2026, 11, 18, 11, 0, tzinfo=V.KST), hilo=None)
    failed = {r[0] for r in rep.failed}
    assert "pxDate 뒤 끝난 거래일 없음" in failed, rep.table()
    row = next(r for r in rep.rows if r[0] == "가격 확인 시간 한도 (경고만)")
    assert row[3] == "WARN" and "2차 출처 (쓸 날 없음" in row[1] and "다음 8" in row[1]


# ── 5. 관문 줄: 걸린 수가 없으면 통과 · 예전 파일은 건너뜀 · 모양이 이상해도 경고만 ─────────────────
def test_gate_row_without_a_hit_passes_and_old_files_skip():
    rep = V.Report()
    V.check_px_cut(rep, {"px": V.PX_SRC_FB, "fb": {"cut": F.fb_cut_record()}})
    V.check_px_cut(rep, {"px": V.PX_SRC_LISTING, "chk": {"cut": F.fb_cut_record({"yahoo": 0, "fill": 0})}})
    V.check_px_cut(rep, {"px": V.PX_SRC_FB, "fb": {"n": 1}})                    # 이 줄 전 발행본 (기록 없음)
    V.check_px_cut(rep, {"px": V.PX_SRC_LISTING, "chk": {"cut": {"s": 600, "daum": 0, "yahoo": 3, "fill": 1}}})
    V.check_px_cut(rep, {"px": V.PX_SRC_FB, "fb": {"cut": {"s": 600, "daum": "x"}}})   # 모양이 이상해도 경고만
    V.check_px_cut(rep, {"px": V.PX_SRC_LISTING, "fb": {"cut": {"s": 600, "daum": 5, "yahoo": 0, "fill": 0}},   # 리뷰 N1: 2차 출처를 돌렸지만
                         "chk": {"cut": F.fb_cut_record()}})                                                       # 쓸 날이 없던 날
    st = [r[3] for r in rep.rows]
    assert st == ["PASS", "PASS", "SKIP", "WARN", "WARN", "WARN"] and not rep.failed
    assert "없음" in rep.rows[0][1] and "1차 출처 야후 확인" in rep.rows[3][1]
    assert "2차 출처 (쓸 날 없음" in rep.rows[5][1] and "다음 5" in rep.rows[5][1] and "1차 출처 야후 확인: 없음" in rep.rows[5][1]


def test_check_px_src_shows_the_row_for_a_listing_day():
    data = {"pxDate": "2026-11-18", "pxSrc": {"v": 1, "px": V.PX_SRC_LISTING, "date": "2026-11-18", "n": {V.PX_SRC_LISTING: 2500}, "must": [],
                                              "fb": None, "chk": {"src": "yahoo", "n": 207, "same": 207, "none": 0, "diff": [],
                                                                  "cut": F.fb_cut_record()}}}
    rep = V.Report()
    V.check_px_src(rep, data, D18 + dt.timedelta(days=1))
    row = [r for r in rep.rows if r[0] == "가격 확인 시간 한도 (경고만)"]
    assert row and row[0][3] == "PASS" and not rep.failed


# ── 6. 1차 출처(자원봉사 최종본) 날은 예전 그대로 ────────────────────────────────────
def test_volunteer_final_day_never_calls_the_second_source():
    prim = listing("2026-11-16_2211")

    def boom(*a, **k):
        raise AssertionError("1차 출처 날에 2차 출처를 불렀어요")
    px, lst, known, src, logs, (full, dshr) = F.kr_second_source(D16, prim, [], NOW, {}, None, fallback=boom)
    assert px == D16 and lst is prim and known == {} and logs == [] and src["fb"] is None and src["px"] == V.PX_SRC_LISTING


# ── 7. KOSPI 일봉: 받지 못한 해가 조용히 빠지면 크게 남겨요 (리뷰 N2) ────────────────────────────
def test_kospi_series_note_flags_gaps_and_a_stale_end():
    days = pd.bdate_range("2023-10-12", "2026-11-18")
    loud, txt = F.kr_index_note(days, dt.date(2023, 10, 12), D16)
    assert not loud and "마지막 2026-11-18" in txt
    no_2024 = [d for d in days if d.year != 2024]
    loud, txt = F.kr_index_note(no_2024, dt.date(2023, 10, 12), D16)
    assert loud and "빈 구간 2023-12-29~2025-01-01" in txt
    loud, txt = F.kr_index_note([d for d in days if d.year != 2023], dt.date(2023, 10, 12), D16)
    assert loud and "시작일 2023-10-12 ~ 첫날 2024-01-01" in txt
    loud, txt = F.kr_index_note([d for d in days if d.year != 2026], dt.date(2023, 10, 12), D16)
    assert loud and "1차 출처 기준일 2026-11-16 보다 앞" in txt
    assert F.kr_index_note([], dt.date(2023, 10, 12), D16)[0]
    # 가장 긴 연휴 (2025 추석: 10-02 ~ 10-10, 8일) 는 크게 남기지 않아요
    hol = [d for d in days if not (dt.date(2025, 10, 3) <= d.date() <= dt.date(2025, 10, 9))]
    assert not F.kr_index_note(hol, dt.date(2023, 10, 12), D16)[0]


# ── 8. 이 길의 HTTP 요청은 모두 시간 한도가 있어요 · 파이썬 출력은 버퍼에 모으지 않아요 ───────────
def test_every_request_on_the_path_has_a_timeout():
    for fn in (F._fetch_daum_days, F._fetch_yahoo_chart, F._fetch_listing_csv, F._listing_commit_kst):
        src = inspect.getsource(fn)
        assert ".get(" in src and "timeout=" in src, fn.__name__
    assert inspect.signature(F.fetch_yahoo_kr_closes).parameters["fetch"].default is F._fetch_yahoo_chart       # yfinance 를 쓰지 않아요
    assert "yf." not in inspect.getsource(F.fetch_yahoo_kr_closes)
    assert "with_socket_timeout(lambda: fdr.DataReader(KR_INDEX" in inspect.getsource(F.fetch_korea)    # FinanceDataReader 는 한도 없이 받아요
    assert "caps=caps0" in inspect.getsource(F.fetch_korea)                                            # 시가총액 순으로 물어요


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
