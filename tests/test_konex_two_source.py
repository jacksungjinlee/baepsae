# -*- coding: utf-8 -*-
"""2026-11-20: 코넥스 종가의 두 출처 — 야후 .KQ × 네이버 (Jack, 2026-11-19 답 5 그대로: "Yes: Naver for KONEX only, always with Yahoo,
published only when they agree to the won; daily KONEX checking too."). (네트워크 없음 · 실제 응답 일부)

픽스처 tests/fixtures/konex_two_source/ — 2026-11-20 07:40 KST 에 받은 실제 응답, 코넥스 8종목 (거래 있음 2 · 거래 없음 2 · 거래 없이 KRX 가
기준가를 옮긴 날이 있는 종목 2 · 야후에 없는 종목 2 — 그중 영문 코드 1):
  krx_konex_*_final.csv  fdr_krx_data_cache 의 11-13 · 11-16 최종본 (그 8종목 행만)
  krx_konex_*_cache.csv  11-18 · 11-19 캐시 파일 (최종본이 아니에요 · 이름 · 시장 · 상장주식수만 써요)
  naver_days.json        네이버 일봉 api.stock.naver.com/chart/domestic/item/{코드}/day (11-10 ~ 11-19)
  yahoo_charts.json      야후 {코드}.KQ 차트 (11-09 ~ 11-19 일봉 · 404 두 종목)
코스피 · 코스닥은 tests/fixtures/kr_two_source/ (다음 × 야후) 를 그대로 써요 — 코넥스 단계가 있어도 그 결과는 하나도 바뀌지 않아야 해요.
"""
import datetime as dt
import functools
import inspect
import json
import math
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

FXK = os.path.join(ROOT, "tests", "fixtures", "konex_two_source")
FX2 = os.path.join(ROOT, "tests", "fixtures", "kr_two_source")
D13, D16, D17, D18, D19 = (dt.date(2026, 11, d) for d in (13, 16, 17, 18, 19))
NOW = dt.datetime(2026, 11, 20, 7, 40, tzinfo=F.KST)
KNX = ["232530", "260870", "336040", "076340", "278990", "296520", "496320", "0203K0"]
TRADED, NO_TRADE, BASE_MOVED, NOT_ON_YAHOO = ["232530", "260870"], ["336040", "076340"], ["278990", "296520"], ["496320", "0203K0"]


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def knx_listing(name):
    return F.parse_listing_csv(open(os.path.join(FXK, f"krx_konex_{name}.csv"), encoding="utf-8").read())


def kk_listing(name):
    return F.parse_listing_csv(open(os.path.join(FX2, f"krx_{name}.csv"), encoding="utf-8").read())


def naver_raw():
    return json.load(open(os.path.join(FXK, "naver_days.json"), encoding="utf-8"))


def yahoo_raw():
    return json.load(open(os.path.join(FXK, "yahoo_charts.json"), encoding="utf-8"))


def naver():
    return {c: F.naver_rows_by_day(v["body"]) for c, v in naver_raw().items() if v["status"] == 200}


def yahoo(start=dt.date(2026, 11, 1), end=dt.date(2026, 11, 21)):
    return {c: F.yahoo_chart_closes(v["body"], start, end) for c, v in yahoo_raw().items() if v["status"] == 200}


def daum2():
    js = json.load(open(os.path.join(FX2, "daum_days.json"), encoding="utf-8"))
    return {c: F.daum_rows_by_day(v) for c, v in js.items()}


def yahoo2():
    js = json.load(open(os.path.join(FX2, "yahoo_closes.json"), encoding="utf-8"))
    return {c: {dt.date.fromisoformat(d): v for d, v in v.items()} for c, v in js.items()}


def no_fill(*a, **k):
    return {"need": 0, "bar": 0, "meta": 0, "none": 0, "fail": 0, "cut": 0, "metaCodes": set()}


def official(df):
    return {str(r["Code"]).strip(): F.kr_official_close(r) for _, r in df.iterrows()}


def knx_fakes(asked_n=None, asked_y=None, raw_y=None, naver_fetch=None, workers=4, clock=None, said=None):
    """진짜 받는 함수 (순서 · 시간 한도 · 세기) 에 기록한 응답을 주는 가짜 fetch 만 끼워요."""
    ry = raw_y or yahoo_raw()
    rn = naver_raw()

    def fn(code, start, end):
        if asked_n is not None:
            asked_n.append(code)
        v = rn[code]
        if v["status"] != 200:
            raise RuntimeError(f"HTTP {v['status']}")
        return v["body"]

    def fy(sym, start=None, end=None):
        if asked_y is not None:
            asked_y.append(sym)
        v = ry.get(sym.split(".")[0])
        if not v or v["status"] != 200:
            raise RuntimeError("HTTP 404")
        return v["body"]
    sa = said.append if said is not None else (lambda s: None)
    kw = {"clock": clock} if clock is not None else {}
    return {"naver": functools.partial(F.fetch_naver_all, fetch=naver_fetch or fn, workers=workers, say=sa, **kw),
            "yahoo": functools.partial(F.fetch_yahoo_kr_closes, fetch=fy, sym=F.yahoo_knx_symbol, say=sa, label="코넥스 야후 .KQ 일봉 종가"),
            "fill": functools.partial(F.yahoo_fill_day, fetch=fy, sym=F.yahoo_knx_symbol, say=sa, label="코넥스 야후 차트 다시 읽기")}


def universe16():
    """11-16 의 2차 출처 종목 목록: 코스피 · 코스닥 픽스처 (장 전 파일 · 코넥스 496320 포함) + 코넥스 8종목 (최종본 행 · 이름 · 시장 · 주식 수만 써요)."""
    kk = kk_listing("2026-11-16_0545")
    kx = knx_listing("2026-11-16_final")
    return pd.concat([kk, kx[~kx["Code"].isin(set(kk["Code"]))]], ignore_index=True)


def run_fb(knx=None, said=None, caps=None, day=D16, uni=None, asked_d=None):
    def fetch_daum(codes, n):
        if asked_d is not None:
            asked_d.extend(codes)
        return daum2(), []
    return F.kr_fallback_days([day], lambda d: (uni if uni is not None else universe16(), "시험"), NOW, {}, fetch_daum=fetch_daum,
                              fetch_yahoo=lambda cm, a, b: (yahoo2(), 0), fill_day=no_fill, say=(said.append if said is not None else (lambda s: None)),
                              caps=caps, knx=knx)


# ── 1. 이름 · 심볼 · 관문 파일과 같은 값 ────────────────────────────────────────
def test_konex_symbol_and_shared_constants():
    assert F.yahoo_knx_symbol("496320", "KONEX") == "496320.KQ" and F.yahoo_knx_symbol("0203K0", " konex ") == "0203K0.KQ"
    assert F.yahoo_knx_symbol("005930", "KOSPI") is None and F.yahoo_knx_symbol("247540", "KOSDAQ") is None
    assert F.yahoo_kr_symbol("496320", "KONEX") is None                         # 다음 × 야후 짝은 예전 그대로 (코넥스 없음)
    assert F.PX_SRC_KNX is V.PX_SRC_KNX == "yahoo+naver" and F.PX_KNX_MARKET == V.PX_KNX_MARKET == "KONEX"
    assert "KONEX" not in V.PX_YAHOO_SUFFIX                                     # 관문 표본 · 다음 × 야후 짝에는 코넥스가 없어요
    assert F.KR_KNX_NAVER_URL.startswith("https://api.stock.naver.com/chart/domestic/item/")


def test_naver_rows_by_day():
    rows = F.naver_rows_by_day([{"localDate": "20261116", "closePrice": 1.0}, {"localDate": "2026-11-17", "closePrice": 2.0},
                                {"localDate": "20261118", "closePrice": 3.0}, {"localDate": "20261118", "closePrice": 4.0}, "x", None])
    assert rows == {D16: {"localDate": "20261116", "closePrice": 1.0}}       # 읽지 못한 날짜 · 두 번 나온 날은 빼요
    assert F.naver_rows_by_day({"error": 1}) == {} and F.naver_rows_by_day(None) == {} and F.naver_rows_by_day([]) == {}


# ── 2. 두 출처가 원 단위까지 같은 코넥스는 진짜 최종본의 공식 종가와 같아요 ─────────────────
def test_confirmed_konex_closes_equal_the_real_final_file():
    nv, y = naver(), yahoo()
    for d, want_conf, want_diff in ((D13, set(TRADED + NO_TRADE) | {"278990"}, {"296520"}),
                                    (D16, set(TRADED + NO_TRADE), set(BASE_MOVED))):
        fin = knx_listing(f"{d}_final")
        fr, st = F.kr_knx_confirm(d, fin, y, nv)
        off = official(fin)
        rows = {r["Code"]: r for r in fr.to_dict("records")}
        assert set(rows) == want_conf and st["conf"] == len(want_conf) and st["n"] == 8
        assert {c for c, *_ in st["diff"]} == want_diff and sorted(st["noYahoo"]) == sorted(NOT_ON_YAHOO) and not st["noNaver"] and not st["bad"]
        fv = {str(r["Code"]).strip(): r for _, r in fin.iterrows()}
        for c, r in rows.items():
            assert r["Close"] == off[c] and r["Marcap"] == r["Close"] * r["Stocks"] == fv[c]["Marcap"]      # 공식 종가 = 시가총액 ÷ 주식 수
            assert r["Volume"] == fv[c]["Volume"] and (r["Open"] == 0) == (fv[c]["Open"] == 0)                # 거래 없음 표시가 목록 파일과 같아요
            if r["Volume"] == 0:
                assert (r["Open"], r["High"], r["Low"], r["Amount"]) == (0, 0, 0, 0)
            else:
                assert math.isnan(r["Amount"]) and (r["Open"], r["High"], r["Low"]) == (fv[c]["Open"], fv[c]["High"], fv[c]["Low"])
            assert all(math.isnan(r[k]) for k in ("Changes", "ChangeCode", "ChagesRatio"))                   # 기준가는 두 출처 모두 몰라요


def test_base_price_moved_without_a_trade_is_a_disagreement():
    """EMB 11-16: 거래 없이 KRX 가 기준가를 2,895 → 2,715 로 옮겼어요. 네이버는 2,715 (공식) · 야후는 마지막 체결가 2,895 → 빠져요."""
    fr, st = F.kr_knx_confirm(D16, knx_listing("2026-11-16_final"), yahoo(), naver())
    d = {c: (n, a, b) for c, n, a, b in st["diff"]}
    assert d["278990"] == ("EMB", 2715.0, 2895.0) and "278990" not in set(fr["Code"])
    loud, txt = F.kr_knx_note(D16, st)
    assert loud and "278990 EMB 네이버 2,715 · 야후 2,895.00" in txt and "496320 본시스템즈" in txt and "0203K0 송우인포텍" in txt
    assert "확인 4 / 8종목" in txt and "야후 종가 없음 2" in txt and "두 종가가 다름 2" in txt


def test_one_source_or_a_won_apart_is_never_published():
    fin = knx_listing("2026-11-16_final")
    y, nv = yahoo(), naver()
    y["232530"][D16] += 1.0                                                     # 1원 다름
    del nv["260870"][D16]                                                       # 네이버 하나뿐 → 야후 하나뿐
    y["336040"].pop(D16)                                                        # 야후 없음
    y["076340"][D16] += 0.004                                                   # 부동소수점 끝자리는 같아요 (다음 × 야후와 같은 KR_FB_CLOSE_TOL)
    fr, st = F.kr_knx_confirm(D16, fin, y, nv)
    assert set(fr["Code"]) == {"076340"} and fr.iloc[0]["Close"] == 4095
    assert {c for c, *_ in st["diff"]} >= {"232530"} and st["noNaver"] == ["260870"] and "336040" in st["noYahoo"]


def test_row_rules():
    u = {"Code": "232530", "Name": "이엠티", "Market": "KONEX", "Stocks": 25614304, "ISU_CD": "KR7232530006", "Dept": "일반기업부", "MarketId": "KNX"}
    n = {"closePrice": 10000.0, "openPrice": 10500.0, "highPrice": 10500.0, "lowPrice": 9900.0, "accumulatedTradingVolume": 6322}
    r = F.kr_knx_row(u, n, 10000.0)
    assert r["Close"] == 10000 and r["Volume"] == 6322 and r["Marcap"] == 10000 * 25614304 and math.isnan(r["Amount"])
    assert F.kr_knx_row(u, n, 10010.0) is None                                  # 네이버와 다른 종가로는 만들지 않아요
    assert F.kr_knx_row(u, n, 10000.5) is None                                  # 원 단위가 아니면
    assert F.kr_knx_row(dict(u, Stocks=None), n, 10000.0) is None and F.kr_knx_row(dict(u, Stocks=0), n, 10000.0) is None
    assert F.kr_knx_row(u, dict(n, accumulatedTradingVolume=None), 10000.0) is None
    assert F.kr_knx_row(u, dict(n, openPrice=None), 10000.0) is None            # 거래가 있는 날 시가가 없으면 못 믿어요
    z = F.kr_knx_row(u, dict(n, accumulatedTradingVolume=0), 10000.0)
    assert (z["Open"], z["High"], z["Low"], z["Amount"]) == (0, 0, 0, 0.0)   # 거래 없는 날: 목록 파일처럼 0
    assert F.kr_knx_row(u, None, 10000.0) is None


# ── 3. 2차 출처 날: 코스피 · 코스닥 결과는 하나도 바뀌지 않고, 코넥스 확인 종목만 더해져요 ─────────────
def test_fallback_adds_confirmed_konex_and_leaves_kospi_kosdaq_identical():
    asked_d, asked_n, asked_y, said = [], [], [], []
    base, _ = run_fb(knx=None)
    with_k, notes = run_fb(knx=knx_fakes(asked_n, asked_y, said=said), said=said, asked_d=asked_d)
    fr0, st0 = base[D16]
    fr1, st1 = with_k[D16]
    kk1 = fr1[fr1["Market"] != "KONEX"].reset_index(drop=True)
    pd.testing.assert_frame_equal(kk1, fr0.reset_index(drop=True), check_dtype=False)          # 같은 종목 · 같은 값
    assert {k: v for k, v in st1.items() if k not in ("knx", "_uni")} == {k: v for k, v in st0.items() if k != "_uni"}
    assert set(fr1.loc[fr1["Market"] == "KONEX", "Code"]) == set(TRADED + NO_TRADE)
    assert not {c for c in asked_d if c in KNX} and set(asked_n) == set(KNX)                   # 다음에는 코넥스를 묻지 않아요 · 네이버에는 코넥스만
    assert all(s.endswith(".KQ") and s.split(".")[0] in KNX for s in asked_y)                  # 야후 .KQ 도 코넥스만
    k = F.px_src_counts(st1)
    assert k["conf"] == st0["conf"] + 4 == len(fr1) and k["knx"]["conf"] == 4 and k["knx"]["n"] == 8
    assert k["knx"]["noYahoo"] == 2 and k["knx"]["diff"] == 2 and k["knx"]["left"] == sorted(BASE_MOVED + NOT_ON_YAHOO)
    assert {kk: v for kk, v in k.items() if kk not in ("conf", "knx")} == {kk: v for kk, v in F.px_src_counts(st0).items() if kk != "conf"}
    # 코넥스 단계는 코스피 · 코스닥 세 단계가 끝난 뒤에 시작해요 (그 단계의 시간 한도와 순서를 바꾸지 않게)
    i_daum = next(i for i, s in enumerate(said) if s.startswith("· 2차 출처: 다음 일별 시세 묻는 중"))
    i_fill = next(i for i, s in enumerate(said) if s.startswith("· 2차 출처: 야후 2026-11-16 일봉 종가가 빈 종목"))
    i_knx = next(i for i, s in enumerate(said) if s.startswith("· 2차 출처 (코넥스): 네이버 일봉 묻는 중"))
    assert i_daum < i_fill < i_knx
    assert any("코넥스 8종목은 아래 야후 .KQ × 네이버" in n for n in notes)
    assert json.dumps(k, allow_nan=False)                                                       # NaN 없이


def test_a_broken_konex_stage_leaves_konex_out_loudly_and_kospi_kosdaq_alone():
    """코넥스 단계가 예상하지 못한 고장 (받는 함수의 예외) 으로 멈춰도 코스피 · 코스닥 결과는 그대로 · 코넥스만 빠지고 크게 남아요."""
    def broken(*a, **k):
        raise TypeError("시험 고장")
    said = []
    base, _ = run_fb(knx=None)
    out, notes = run_fb(knx={"naver": broken, "yahoo": broken, "fill": broken}, said=said)
    fr, st = out[D16]
    assert "knx" not in st and "KONEX" not in set(fr["Market"])
    pd.testing.assert_frame_equal(fr.reset_index(drop=True), base[D16][0].reset_index(drop=True))
    assert any(n.startswith("!! 코넥스 2차 출처 단계가 고장 났어요 (TypeError: 시험 고장)") for n in notes)
    assert any("코넥스 2차 출처 단계가 고장" in s for s in said)
    px, lst, known, src, logs, _ = F.kr_second_source(D13, kk_listing("2026-11-13_2158"), [D16], NOW, {}, None,
                                                      fallback=lambda *a: run_fb(knx={"naver": broken, "yahoo": broken, "fill": broken}))
    assert px == D16 and src["knx"]["px"] is None                                             # 관문 줄: '코넥스 단계를 묻지 않았어요' (경고)


def test_konex_is_asked_in_market_cap_order():
    asked_n = []
    caps = F.kr_fb_caps(knx_listing("2026-11-13_final"))
    run_fb(knx=knx_fakes(asked_n, workers=1), caps=caps)
    by_cap = sorted(KNX, key=lambda c: -caps[c])
    assert asked_n == by_cap and asked_n[0] == "496320"                                       # 본시스템즈 (1.2조원) 먼저


def test_konex_time_limit_leaves_the_rest_unconfirmed_and_the_gate_only_warns(monkeypatch):
    monkeypatch.setattr(F, "KR_FB_PHASE_BUDGET_S", 250)
    clk, said, asked = Clock(), [], []

    def slow(code, start, end):
        asked.append(code)
        clk.t += 100
        return naver_raw()[code]["body"]
    caps = F.kr_fb_caps(knx_listing("2026-11-13_final"))
    out, notes = run_fb(knx=knx_fakes(naver_fetch=slow, workers=1, clock=clk, said=said), said=said, caps=caps)
    fr, st = out[D16]
    assert asked == ["496320", "232530", "260870"]                                            # 0 · 100 · 200초 · 그 뒤로는 묻지 않아요
    kst = st["knx"]
    assert kst["cut"] == {"s": 250, "yahoo": 0, "fill": 0, "naver": 5} and len(kst["noNaver"]) == 5
    assert set(fr.loc[fr["Market"] == "KONEX", "Code"]) == {"232530", "260870"}
    assert any(s.lstrip().startswith("!! 2차 출처 시간 한도 250초: 코넥스 네이버 일봉을 더 묻지 않아요") for s in said)
    assert any(n.startswith("!! 2차 출처 시간 한도 250초 — 코넥스 네이버 일봉: 받은 3 / 대상 8") for n in notes)
    loud, txt = F.kr_knx_note(D16, kst)
    assert loud and "시간 한도 250초로 묻지 못한 종목 (야후 일봉 0 · 야후 다시 읽기 0 · 네이버 5)" in txt
    src = {"px": V.PX_SRC_FB, "fb": F.px_src_counts(st)}
    rep = V.Report()
    V.check_px_cut(rep, src)
    (name, val, rule, status), = rep.rows
    assert status == "WARN" and "코넥스 2차 출처: 묻지 못함 야후 일봉 0 · 야후 다시 읽기 0 · 네이버 5종목" in val and not rep.failed
    assert "2차 출처: 없음" in val                                                             # 코스피 · 코스닥 단계는 걸리지 않았어요


def test_konex_fill_reads_only_stocks_yahoo_has_and_counts_meta():
    """야후가 마지막 날 일봉 종가를 아직 비워 둔 코넥스만 다시 읽어요 · 야후에 아예 없는 종목 (404) 은 다시 묻지 않아요."""
    ry = yahoo_raw()
    for c in ("232530", "260870"):
        b = ry[c]["body"]
        b["indicators"]["quote"][0]["close"][-1] = None                       # 11-19 일봉 종가가 빈 값
    ry["232530"]["body"]["meta"] = {"regularMarketPrice": 10090.0,
                                    "regularMarketTime": int(dt.datetime(2026, 11, 19, 16, 30, 5, tzinfo=F.KST).timestamp())}
    asked_y = []
    uni = pd.concat([knx_listing("2026-11-19_cache"), kk_listing("2026-11-18_1452")], ignore_index=True)
    out, notes = F.kr_fallback_days([D19], lambda d: (uni, "시험"), NOW, F.load_krx_special_sessions(),
                                    fetch_daum=lambda codes, n: ({}, []), fetch_yahoo=lambda cm, a, b: ({}, 0), fill_day=no_fill,
                                    say=lambda s: None, knx=knx_fakes(asked_y=asked_y, raw_y=ry))
    fr, st = out[D19]
    reread = asked_y[len(KNX):]                                                                # 앞 단계는 8종목 모두 · 다시 읽기는 둘만
    assert sorted(reread) == ["232530.KQ", "260870.KQ"]
    kst = st["knx"]
    assert "232530" in set(fr["Code"]) and "260870" in kst["noYahoo"] and kst["yMeta"] == 1  # 수능일 마감 16:30 뒤 10분 안 → meta 로 확인
    assert any("코넥스 야후 2026-11-19 일봉 종가가 빈 종목 2" in n and "regularMarketPrice 1" in n for n in notes)


# ── 4. 기준일 고르기 · pxSrc · 로그 ──────────────────────────────────────────────
def test_second_source_day_records_the_konex_source_and_names_every_stock_left_out():
    prim = pd.concat([kk_listing("2026-11-13_2158"), knx_listing("2026-11-13_final")], ignore_index=True)
    fb = functools.partial(run_fb_partial, knx=knx_fakes())
    px, lst, known, src, logs, (full, _) = F.kr_second_source(D13, prim, [D16], NOW, {}, None, fallback=fb)
    assert px == D16 and src["px"] == V.PX_SRC_FB and src["knx"]["px"] == V.PX_SRC_KNX
    assert set(lst.loc[lst["Market"] == "KONEX", "Code"]) == set(TRADED + NO_TRADE)
    line = next(t for loud, t in logs if "코넥스 2차 출처" in t)
    assert next(loud for loud, t in logs if t == line)                                        # 빠진 종목이 있으면 크게
    for c in BASE_MOVED + NOT_ON_YAHOO:
        assert c in line                                                                       # 빠진 종목을 모두 이름과 까닭으로
    assert src["fb"]["knx"]["conf"] == 4 and src["fb"]["conf"] == len(lst)
    # 발행 직전: 처리한 코넥스 중 발행한 종목만 · 출처별 수
    src["knx"]["t"] = sorted(TRADED + NO_TRADE)
    stocks = [{"t": c, "cls": "kr"} for c in ["232530", "336040", "005930"]] + [{"t": "AAPL", "cls": "us"}]
    out = F.px_src_final(src, stocks)
    assert out["knx"]["t"] == ["232530", "336040"] and out["knx"]["n"] == {V.PX_SRC_KNX: 2} and out["n"] == {V.PX_SRC_FB: 3}
    assert src["knx"]["t"] == sorted(TRADED + NO_TRADE)                                       # 원본은 그대로
    assert json.dumps(out, allow_nan=False)


def run_fb_partial(days, universe_of, now, special, knx=None):
    return run_fb(knx=knx, day=days[0], uni=universe_of(days[0])[0] if universe_of else universe16())


def test_volunteer_day_records_listing_as_the_konex_source():
    prim = kk_listing("2026-11-16_2211")

    def boom(*a, **k):
        raise AssertionError("1차 출처 날에 2차 출처를 불렀어요")
    px, lst, known, src, logs, _ = F.kr_second_source(D16, prim, [], NOW, {}, None, fallback=boom)
    assert src["knx"] == {"px": V.PX_SRC_LISTING, "t": [], "n": {}, "chk": None}
    assert F.px_src_final(src, [])["knx"] == {"px": V.PX_SRC_LISTING, "t": [], "n": {}, "chk": None}


def test_no_usable_second_source_day_keeps_konex_on_the_listing():
    """필수 종목이 확인되지 않은 날 (다음이 답하지 않음): 1차 출처 그대로 → 코넥스 종가 출처도 1차 출처 (관문 '끝난 거래일' 줄이 멈춰요)."""
    prim = kk_listing("2026-11-13_2158")

    def fb(days, universe_of, now, special):
        return F.kr_fallback_days(days, lambda d: (universe16(), "시험"), now, special, fetch_daum=lambda codes, n: ({}, []),
                                  fetch_yahoo=lambda cm, a, b: ({}, 0), fill_day=no_fill, say=lambda s: None, knx=knx_fakes())
    px, lst, known, src, logs, _ = F.kr_second_source(D13, prim, [D16], NOW, {}, None, fallback=fb)
    assert px == D13 and lst is prim and src["px"] == V.PX_SRC_LISTING and src["knx"]["px"] == V.PX_SRC_LISTING
    assert src["fb"]["knx"]["conf"] == 4                                                       # 기록은 남아요 (관문 · 감시가 봐요)


# ── 5. 그 뒤 단계: d1 · 거래 없음 · 거래대금 · 기준가 연결 ─────────────────────────────────
def test_konex_rows_flow_through_d1_no_trade_val_and_ref_links():
    out, _ = run_fb(knx=knx_fakes())
    cur = out[D16][0]
    prev = pd.concat([kk_listing("2026-11-13_2158"), knx_listing("2026-11-13_final")], ignore_index=True)
    d1, v20, _ = F.kr_d1_val20(cur, [(D13, prev)], True, min_days=2)
    assert d1["232530"] == -1.38 and d1["260870"] == 0.12                     # 공식 종가끼리 — KRX 최종본의 등락률과 같아요 (-1.38 · 0.12)
    nt, cols, odd = F.kr_no_trade(cur)                                         # 거래 없음 (거래량 0 · 시가 0 · 거래대금 0) — 목록 파일과 같은 규칙
    assert cols and {"336040", "076340"} <= nt and not {"232530", "260870"} & nt and not odd & set(KNX)
    # 거래가 있던 코넥스는 그날 거래대금이 빈 값 (추측하지 않아요) — val20 은 거래대금이 있는 날로만
    amt = dict(zip(cur["Code"], cur["Amount"]))
    assert math.isnan(amt["232530"]) and amt["336040"] == 0 and F._fin(amt["232530"]) is None
    assert "232530" not in v20 and "336040" in v20 and "005930" in v20       # 빈 거래대금은 세지 않아요 (11-13 하루뿐 → 2일 미만이라 빈 칸)
    by_day, events = F.kr_ref_links([(D16, cur), (D13, prev)], [pd.Timestamp(D13), pd.Timestamp(D16)], set(KNX[:6]) | {"005930"})
    st = by_day[pd.Timestamp(D13)]
    assert all(st[c] == "unknown" for c in KNX[:6] if c in set(cur["Code"])) and st["005930"] == "ok"
    assert not [e for e in events if e[0] in KNX]


# ── 6. 1차 출처 날: 발행하는 코넥스를 모두 네이버와 맞춰 봐요 (경고만) ─────────────────────────
def test_daily_check_on_real_final_files():
    nv = naver()
    for d in (D13, D16):
        ck = F.kr_knx_check(knx_listing(f"{d}_final"), d, nv)
        assert ck == {"src": "naver", "n": 8, "same": 8, "none": 0, "noneEx": [], "diff": []}   # 거래 없는 날 · 기준가를 옮긴 날 · 야후에 없는 종목도


def test_daily_check_names_a_mismatch_and_a_missing_value_and_never_drops():
    fin = knx_listing("2026-11-16_final")
    nv = naver()
    nv["232530"][D16] = dict(nv["232530"][D16], closePrice=10010.0)
    del nv["496320"][D16]
    ck = F.kr_knx_check(fin, D16, nv, codes=["232530", "496320", "260870", "005930"])
    assert ck["n"] == 2 and ck["same"] == 1 and ck["diff"] == ["232530 이엠티 10000/10010"] and ck["none"] == 1 and ck["noneEx"] == ["496320 본시스템즈"]
    loud, txt = F.kr_knx_check_note(dict(ck, fail=0, cut={"s": 120, "naver": 0}), 3)
    assert loud and "다름 1: 232530 이엠티 10000/10010" in txt and "경고만" in txt and "496320 본시스템즈" in txt
    loud, txt = F.kr_knx_check_note({"src": "naver", "n": 3, "same": 3, "none": 0, "noneEx": [], "diff": [], "fail": 0, "cut": {"s": 120, "naver": 0}}, 3)
    assert not loud and "같음 3 / 3" in txt


def test_daily_check_fetch_is_bounded_and_never_raises():
    fin = knx_listing("2026-11-16_final")
    clk = Clock()

    def slow(code, start, end):
        clk.t += 50
        return naver_raw()[code]["body"]
    fetch = functools.partial(F.fetch_naver_all, fetch=slow, workers=1, clock=clk)
    ck = F.kr_knx_daily_check(fin, D16, KNX, fetch=fetch, budget_s=120, say=lambda s: None)
    assert ck["cut"] == {"s": 120, "naver": 5} and ck["n"] == 3 and ck["none"] == 5 and not ck["diff"]
    loud, _ = F.kr_knx_check_note(ck, len(KNX))
    assert loud

    def boom(*a, **k):
        raise ConnectionError("x")
    ck = F.kr_knx_daily_check(fin, D16, KNX, fetch=boom, say=lambda s: None)
    assert ck["err"].startswith("ConnectionError") and ck["n"] == 0
    assert F.kr_knx_daily_check(fin, D16, [], fetch=boom)["n"] == 0                 # 코넥스가 없으면 묻지 않아요
    assert F.KR_KNX_CHK_BUDGET_S <= F.KR_FB_PHASE_BUDGET_S


def test_naver_fetcher_waits_per_rules_and_is_bounded(monkeypatch):
    slept = []
    monkeypatch.setattr(F.time, "sleep", slept.append)

    class R:
        def __init__(self, s):
            self.status_code, self.headers = s, {}

        def json(self):
            return []

    class S:
        def __init__(self, s):
            self.s, self.calls = s, 0

        def get(self, url, params=None, headers=None, timeout=None):
            assert timeout == 20 and url == F.KR_KNX_NAVER_URL.format(c="232530") and params == {"startDateTime": "202611100000",
                                                                                                    "endDateTime": "202611192359"}
            self.calls += 1
            return R(self.s)
    for status, want in ((503, [1.0, 2.0]), (404, [])):
        slept.clear()
        F._NAVER_LOCAL.s = sess = S(status)
        try:
            F._fetch_naver_days("232530", dt.date(2026, 11, 10), D19)
            raise AssertionError("예외가 나야 해요")
        except RuntimeError as e:
            assert f"HTTP {status}" in str(e)
        finally:
            del F._NAVER_LOCAL.s
        assert slept == want and sess.calls == (1 if status == 404 else 3)
    F._NAVER_LOCAL.s = S(200)
    try:
        assert F._fetch_naver_days("232530", dt.date(2026, 11, 10), D19) == []
    finally:
        del F._NAVER_LOCAL.s


# ── 7. 파이프라인이 코넥스 단계를 부르고, 코스피 · 코스닥에는 네이버를 쓰지 않아요 ───────────────────
def test_fetch_korea_wires_the_konex_paths():
    src = inspect.getsource(F.fetch_korea)
    assert "knx=kr_knx_fetchers()" in src and "kr_knx_daily_check(listing, px_date, knx_codes)" in src
    assert "caps=caps0" in src                                                                  # 시가총액 순 (코넥스도 같은 caps)
    k = F.kr_knx_fetchers()
    assert k["naver"] is F.fetch_naver_all and k["yahoo"].keywords["sym"] is F.yahoo_knx_symbol and k["fill"].keywords["sym"] is F.yahoo_knx_symbol
    # 코스피 · 코스닥 길의 기본값은 예전 그대로 (코넥스를 묻지 않아요)
    for fn in (F.fetch_yahoo_kr_closes, F.yahoo_fill_day):
        assert inspect.signature(fn).parameters["sym"].default is F.yahoo_kr_symbol
    assert inspect.signature(F.kr_fallback_days).parameters["knx"].default is None


def test_naver_is_never_used_for_kospi_or_kosdaq():
    """네이버 일봉을 코스피 · 코스닥 종목에 줘도 코넥스 확인은 그 종목을 보지 않아요 (시간외 체결가라 공식 종가가 아니에요)."""
    uni = universe16()
    nv = {c: {D16: {"closePrice": 1.0, "accumulatedTradingVolume": 0}} for c in uni["Code"]}
    nv.update(naver())
    fr, st = F.kr_knx_confirm(D16, uni, {**yahoo(), **{c: {D16: 1.0} for c in uni["Code"] if c not in KNX}}, nv)
    assert set(fr["Market"]) == {"KONEX"} and st["n"] == 8
    ck = F.kr_knx_check(uni, D16, nv)
    assert ck["n"] + ck["none"] == 8                                                            # 코넥스만 맞춰 봐요
    assert "naver" not in inspect.getsource(F.kr_fb_confirm).lower()
    assert "naver" not in inspect.getsource(F.kr_primary_check).lower()


# ── 8. 관문 줄 (경고만) ──────────────────────────────────────────────────────────
TODAY = dt.date(2026, 10, 31)
GNOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}


def mark_konex(cur, n=3):
    """좋은 시험 데이터의 작은 국내 종목 n개를 코넥스로 (설명 dk 의 시장만 바꿔요)."""
    kr = [s for s in V.kr_stocks(cur["data"]) if s["t"] not in V.MUST]
    picked = kr[-n:]
    for s in picked:
        s["dk"] = s["dk"].replace("KOSPI 상장", "KONEX 상장")
    return sorted(s["t"] for s in picked)


def fb_pair_konex(daum_conf_short=2):
    """2차 출처 날 (캐시 최종본은 하루 전) · 발행한 국내 종목 중 3개가 코넥스 · 다음 × 야후 확인 수만으로는 발행 수보다 적고 코넥스를 더하면 같아요."""
    cur, prev, final = good_pair()
    codes = mark_konex(cur)
    nk = len(V.kr_stocks(cur["data"]))
    knx_fb = {"n": 107, "conf": 3 + daum_conf_short, "noNaver": 0, "bad": 0, "noYahoo": 11, "diff": 5, "yMeta": 0, "diffEx": ["278990 EMB 2680/2700.00"],
              "left": [], "cut": F.knx_cut_record()}
    cur["data"]["pxSrc"] = {"v": 1, "px": V.PX_SRC_FB, "date": "2026-10-30", "days": {"2026-10-30": V.PX_SRC_FB},
                            "fb": {"n": nk + 200, "conf": nk, "mkt": 107, "noDaum": 40, "bad": 0, "noYahoo": 7, "diff": 3, "diffEx": [], "must": [],
                                   "cut": F.fb_cut_record(), "knx": knx_fb},
                            "must": [], "chk": None, "n": {V.PX_SRC_FB: nk},
                            "knx": {"px": V.PX_SRC_KNX, "t": codes, "n": {V.PX_SRC_KNX: len(codes)}, "chk": None}}
    old = {"date": dt.date(2026, 10, 29), "closes": {c: v * 0.98 for c, v in final["closes"].items()}, "how": "시험 (하루 전)"}
    by = {s["t"]: s["price"] for s in V.kr_stocks(cur["data"])}
    pick = V.px_alt_pick(cur["data"])
    alt = {"date": dt.date(2026, 10, 30), "closes": {c: float(by[c]) for c in pick}, "asked": len(pick), "got": len(pick), "mustMissing": [], "err": []}
    return cur, prev, old, alt, codes


def check(cur, prev, final, alt=None):
    return V.run_checks(cur, prev, final, TODAY, count_between=lambda a, b: 1, sessions=SESSIONS, now=GNOW, hilo=hilo_of(cur, V.MUST), alt=alt)


def row(rep, name=V.KNX_ROW):
    return next(r for r in rep.rows if r[0] == name)


def test_gate_backup_day_counts_konex_confirmations_and_only_warns():
    cur, prev, old, alt, codes = fb_pair_konex()
    rep = check(cur, prev, old, alt)
    assert not rep.failed, rep.table()                                       # 확인 수(코넥스 포함) = 발행 수 → 2차 출처 관문 기준을 써요
    assert row(rep, "pxDate = 최종본 날짜")[3] == "PASS"
    r = row(rep)
    assert r[3] == "WARN" and "확인 5 / 107" in r[1] and "다름 5" in r[1] and "발행 3" in r[1] and "278990 EMB" in r[1]
    assert not any(c in V.px_alt_pick(cur["data"]) for c in codes)          # 관문의 표본에는 여전히 코넥스가 없어요


def test_gate_backup_day_without_disagreements_passes_and_odd_records_warn():
    cur, prev, old, alt, codes = fb_pair_konex()
    cur["data"]["pxSrc"]["fb"]["knx"].update(diff=0, diffEx=[])
    assert row(check(cur, prev, old, alt))[3] == "PASS"
    for change in ({"t": codes[:2]}, {"t": "x"}, {"n": {V.PX_SRC_KNX: 99}}, {"px": None}, {"px": "daum+yahoo"}):
        c2, p2, o2, a2, _ = fb_pair_konex()
        c2["data"]["pxSrc"]["fb"]["knx"].update(diff=0, diffEx=[])
        c2["data"]["pxSrc"]["knx"].update(change)
        rep = check(c2, p2, o2, a2)
        assert row(rep)[3] == "WARN" and "pxDate = 최종본 날짜" not in {r[0] for r in rep.failed}, change
    c3, p3, o3, a3, _ = fb_pair_konex()
    c3["data"]["pxSrc"]["fb"]["knx"]["conf"] = "많음"
    rep = check(c3, p3, o3, a3)
    assert row(rep)[3] == "WARN" and "fb.knx 모양" in row(rep)[1] and V.KNX_ROW not in {r[0] for r in rep.failed}


def test_gate_listing_day_daily_check_rows():
    cur, prev, final = good_pair()
    codes = mark_konex(cur)
    base = {"v": 1, "px": V.PX_SRC_LISTING, "date": "2026-10-30", "must": [], "n": {"listing": 2400},
            "chk": {"src": "yahoo", "n": 207, "same": 207, "none": 0, "diff": [], "cut": F.fb_cut_record()}}

    def with_chk(ck):
        cur["data"]["pxSrc"] = dict(base, knx={"px": V.PX_SRC_LISTING, "t": codes, "n": {V.PX_SRC_LISTING: 3}, "chk": ck})
        return check(cur, prev, final)
    ok = {"src": "naver", "n": 3, "same": 3, "none": 0, "noneEx": [], "diff": [], "fail": 0, "cut": {"s": 120, "naver": 0}}
    rep = with_chk(ok)
    assert row(rep)[3] == "PASS" and "같음 3 / 3" in row(rep)[1] and not rep.failed
    assert row(rep, "가격 확인 시간 한도 (경고만)")[3] == "PASS" and "1차 출처 코넥스 네이버 확인: 없음" in row(rep, "가격 확인 시간 한도 (경고만)")[1]
    for bad in (dict(ok, same=2, diff=[f"{codes[0]} 시험 1000/1010"]), dict(ok, n=2, same=2, none=1, noneEx=[codes[1]]),
                dict(ok, err="ConnectionError: x", n=0, same=0), dict(ok, cut={"s": 120, "naver": 1}, n=2, same=2, none=1), None):
        rep = with_chk(bad)
        assert row(rep)[3] == "WARN" and not rep.failed, bad
    rep = with_chk(dict(ok, cut={"s": 120, "naver": 1}, n=2, same=2, none=1))
    assert row(rep, "가격 확인 시간 한도 (경고만)")[3] == "WARN" and "네이버 1종목" in row(rep, "가격 확인 시간 한도 (경고만)")[1]


def test_gate_skips_files_before_this_change_and_never_fails():
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)                                            # pxSrc 없음
    assert not any(r[0] == V.KNX_ROW for r in rep.rows) or row(rep)[3] == "SKIP"
    cur["data"]["pxSrc"] = {"v": 1, "px": V.PX_SRC_LISTING, "date": "2026-10-30", "must": [], "n": {"listing": 2400},
                            "chk": {"src": "yahoo", "n": 207, "same": 207, "none": 0, "diff": []}}
    rep = check(cur, prev, final)
    assert row(rep)[3] == "SKIP" and not rep.failed                          # pxSrc.knx 없음 (이 줄 전 발행본)
    for junk in ("x", [], {"t": None}, {"px": V.PX_SRC_LISTING, "t": [], "n": {}, "chk": "x"}):
        cur["data"]["pxSrc"]["knx"] = junk
        rep = check(cur, prev, final)
        assert row(rep)[3] in ("WARN", "PASS") and V.KNX_ROW not in {r[0] for r in rep.failed}, junk
