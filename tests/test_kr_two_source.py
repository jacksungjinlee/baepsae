# -*- coding: utf-8 -*-
"""2026-11-19 사고 고침: 공식 종가는 늘 두 출처로 (Jack 규칙 3) · 업종 이어 쓰기. (네트워크 없음 · 실제 응답 일부)

픽스처 tests/fixtures/kr_two_source/ — 2026-11-19 새벽에 받은 실제 응답 13종목 (필수 7 · 거래 없음 2 · 다음 종가가 틀린 날 1 ·
기준가가 새로 정해진 종목 1 · 영문 코드 1 · 코넥스 1):
  krx_*.csv          fdr_krx_data_cache 의 같은 날짜 파일 여러 버전 (장 전 05:45 · 07:01 / 최종본 21:58 · 22:11 / 장중 11-17 15:29 · 11-18 14:52)
  daum_days.json     다음 일별 시세 (perPage 10)
  yahoo_closes.json  야후 .KS/.KQ 일봉 Close (수정 안 한 값 · 11-18 은 아직 빈 값이었어요)
  naver_005930.xml   네이버 일봉 (종가가 공식 종가가 아니라는 증거)
"""
import datetime as dt
import inspect
import json
import os
import re
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "kr_two_source")
D13, D16, D17, D18 = (dt.date(2026, 11, d) for d in (13, 16, 17, 18))
FIELDS = ["Close", "ChangeCode", "Changes", "ChagesRatio", "Open", "High", "Low", "Volume", "Amount", "Marcap", "Stocks",
          "Name", "Market", "ISU_CD", "Dept", "MarketId"]
KONEX = "496320"


def listing(name):
    return F.parse_listing_csv(open(os.path.join(FX, f"krx_{name}.csv"), encoding="utf-8").read())


def daum():
    js = json.load(open(os.path.join(FX, "daum_days.json"), encoding="utf-8"))
    return {c: F.daum_rows_by_day(v) for c, v in js.items()}


def yahoo():
    js = json.load(open(os.path.join(FX, "yahoo_closes.json"), encoding="utf-8"))
    return {c: {dt.date.fromisoformat(d): v for d, v in v.items()} for c, v in js.items()}


def same(a, b, k):
    if k == "ChagesRatio":
        return abs(float(a) - float(b)) < 0.005
    if (a is None or a != a) and (b is None or b != b):           # 빈 값 (NaN) 끼리
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


# ── 1. 11-13 · 11-16 을 2차 출처만으로 다시 만들면 진짜 최종본과 칸마다 같아요 ─────────────
@pytest.mark.parametrize("d, pre, fin", [(D13, "2026-11-13_0701", "2026-11-13_2158"), (D16, "2026-11-16_0545", "2026-11-16_2211")])
def test_rebuild_matches_the_real_final_file(d, pre, fin):
    fr, st = F.kr_fb_confirm(d, listing(pre), daum(), yahoo())
    final = {str(r["Code"]): r for r in listing(fin).to_dict("records")}
    assert st["must"] == [] and len(fr) >= 9
    for r in fr.to_dict("records"):
        g = final[r["Code"]]
        bad = [k for k in FIELDS if not same(g[k], r[k], k)]
        assert not bad, (r["Code"], bad)
        assert r["Close"] == round(g["Marcap"] / g["Stocks"])        # 공식 종가 = 시가총액 ÷ 상장주식수
    # 빠진 종목과 까닭: 코넥스는 이 다음 × 야후 단계에서 묻지 않아요 (다음에 코넥스가 없어요 · 코넥스는 따로 야후 .KQ × 네이버 단계 — test_konex_two_source.py) · STX 는 야후 값이 엉뚱 (거래정지 종목의 수정 값)
    assert KONEX in st["mkt"] and KONEX not in st["noDaum"]                    # 코넥스는 이 단계에서 묻지 않아요 (다음에 없는 시장)
    assert "011810" in {c for c, *_ in st["diff"]}


def test_daum_alone_is_not_enough_yahoo_catches_a_wrong_daum_close():
    """11-13 비에이치: 다음 종가 16,020 · 공식 종가(최종본) 16,070 · 야후 16,070 → 다름으로 빠져요 (두 출처 규칙이 막아요)."""
    fr, st = F.kr_fb_confirm(D13, listing("2026-11-13_0701"), daum(), yahoo())
    diff = {c: (a, b) for c, _, a, b in st["diff"]}
    assert diff["090460"] == (16020, 16070.0) and "090460" not in set(fr["Code"])
    g = listing("2026-11-13_2158").set_index("Code").loc["090460"]
    assert round(g["Marcap"] / g["Stocks"]) == 16070
    # 11-16 은 두 출처가 같아 들어가요
    fr16, _ = F.kr_fb_confirm(D16, listing("2026-11-16_0545"), daum(), yahoo())
    assert "090460" in set(fr16["Code"])


def test_no_trade_stock_matches_the_listing_convention():
    """금양(001570) 11-16 거래 없음: 다음은 시가 · 고가 · 저가를 종가로 채우지만 목록 파일은 0 — 0 으로 적어 거래 없음 표시가 같아요."""
    fr, _ = F.kr_fb_confirm(D16, listing("2026-11-16_0545"), daum(), yahoo())
    r = fr.set_index("Code").loc["001570"]
    assert (r["Open"], r["High"], r["Low"], r["Volume"], r["Amount"], r["Close"], r["Changes"]) == (0, 0, 0, 0, 0, 9900, 0)
    nt, cols, odd = F.kr_no_trade(fr)
    assert cols and "001570" in nt and not odd
    assert "005930" not in nt


def test_base_price_reset_is_kept_as_a_break():
    """유니온머티리얼(047400): 11-13 공식 종가 746 · 11-16 기준가 3,730 (병합). 2차 출처 11-16 행의 Close − Changes 가 새 기준가라
    기준가 연결이 'break' 로 잡혀요 (그 앞 봉을 공식 종가로 고치지 않아요). 야후는 11-13 값을 새 기준으로 고쳐 둬서 (3,730) 11-13 은 확인되지 않아요."""
    fr16, _ = F.kr_fb_confirm(D16, listing("2026-11-16_0545"), daum(), yahoo())
    r = fr16.set_index("Code").loc["047400"]
    assert r["Close"] - r["Changes"] == 3730
    by_day, events = F.kr_ref_links([(D16, fr16), (D13, listing("2026-11-13_2158"))], [D13, D16], {"047400", "005930"})
    assert by_day[pd.Timestamp(D13)]["047400"] == "break" and by_day[pd.Timestamp(D13)]["005930"] == "ok"
    assert ("047400", D16, 746.0, 3730.0) in events
    _, st13 = F.kr_fb_confirm(D13, listing("2026-11-13_0701"), daum(), yahoo())
    assert ("047400", "유니온머티리얼", 746, 3730.0) in st13["diff"]


def test_next_day_snapshot_base_agrees_with_the_fallback_close():
    """11-17 2차 출처 종가 = 11-18 장중 파일의 기준가 (Close − Changes) — 캐시의 다른 버전과도 같아요 (기준가가 바뀐 종목 빼고)."""
    fr17, st = F.kr_fb_confirm(D17, listing("2026-11-17_1529"), daum(), yahoo())
    snap = listing("2026-11-18_1452").set_index("Code")
    assert st["must"] == []
    for r in fr17.to_dict("records"):
        s = snap.loc[r["Code"]]
        assert r["Close"] == s["Close"] - s["Changes"], r["Code"]
    assert fr17.set_index("Code").loc["005930", "Close"] == 190300          # 11-17 15:29 장중 파일은 190,200 (최종본 아님)
    assert listing("2026-11-17_1529").set_index("Code").loc["005930", "Close"] == 190200


def test_naver_close_is_not_the_official_close():
    """네이버 일봉 종가는 시간외 · 넥스트레이드 마지막 체결가예요 — 공식 종가 출처로 쓰면 필수 종목이 확인되지 않아요."""
    text = open(os.path.join(FX, "naver_005930.xml"), encoding="utf-8").read()
    bars = {m[0]: float(m[4]) for m in (x.split("|") for x in re.findall(r'data="([^"]+)"', text))}
    official = {"20261113": 206000, "20261116": 196800, "20261117": 190300}
    assert all(bars[d] != v for d, v in official.items())             # 209,000 · 195,000 · 189,800
    nv = {"005930": {dt.date(2026, 11, 16): bars["20261116"]}}
    y = yahoo()
    y.update(nv)
    _, st = F.kr_fb_confirm(D16, listing("2026-11-16_0545"), daum(), y)
    assert "005930" in st["must"]


def test_one_source_only_is_not_confirmed():
    """11-18: 야후 종가가 아직 빈 값 → 다음 하나뿐이라 한 종목도 확인되지 않아요 (추측하지 않아요)."""
    fr, st = F.kr_fb_confirm(D18, listing("2026-11-18_1452"), daum(), yahoo())
    assert len(fr) == 0 and set(st["must"]) == set(V.MUST) and len(st["noYahoo"]) >= 11 and KONEX not in st["noYahoo"]
    fr, st = F.kr_fb_confirm(D16, listing("2026-11-16_0545"), {}, yahoo())
    assert len(fr) == 0 and len(st["noDaum"]) == 12 and st["mkt"] == [KONEX]


def test_daum_row_rules():
    u = {"Code": "005930", "Name": "삼성전자", "Market": "KOSPI"}
    r = daum()["005930"][D16]
    assert F.kr_fb_row(u, r)["Close"] == 196800
    for k, v in (("tradePrice", 196800.5), ("totalAccTradeVolume", -1), ("listedSharesCount", 0), ("change", "RISE"), ("change", "??"),
                 ("tradePrice", None), ("changePrice", None), ("totalAccTradePrice", float("nan"))):
        assert F.kr_fb_row(u, dict(r, **{k: v})) is None, (k, v)
    js = {"data": [dict(r), dict(r, tradePrice=1.0), {"date": "bad"}, dict(r, date="2026-11-13 00:00:00")]}
    rows = F.daum_rows_by_day(js)
    assert D16 not in rows and D13 in rows                             # 같은 날 두 번 → 그 날은 빼요


def test_change_ratio_rounds_half_away_from_zero_like_krx():
    assert F.kr_change_ratio(-5, 800) == -0.63 and F.kr_change_ratio(5, 800) == 0.63     # 0.625 → 0.63 (파이썬 round 는 0.62)
    assert F.kr_change_ratio(-9200, 206000) == -4.47 and F.kr_change_ratio(0, 100) == 0.0


def test_finality_uses_the_special_session_table():
    sp = F.load_krx_special_sessions()
    csat = dt.date(2026, 11, 19)
    assert csat in sp
    assert not F.kr_fb_final(csat, dt.datetime(2026, 11, 19, 16, 59, tzinfo=F.KST), sp)
    assert F.kr_fb_final(csat, dt.datetime(2026, 11, 19, 17, 0, tzinfo=F.KST), sp)
    assert not F.kr_fb_final(D18, dt.datetime(2026, 11, 18, 15, 59, tzinfo=F.KST), sp)
    assert F.kr_fb_final(D18, dt.datetime(2026, 11, 18, 16, 0, tzinfo=F.KST), sp)


# ── 2. 기준일 고르기 · d1 · val20 에 쓰는 앞 날 ───────────────────────────
def fake_fallback(frames):
    def run(days, universe_of, now, special):
        return {d: frames[d] for d in days if d in frames}, ["다음 일별 시세: 시험"]
    return run


def test_second_source_picks_the_latest_day_with_every_must_have():
    f17 = F.kr_fb_confirm(D17, listing("2026-11-17_1529"), daum(), yahoo())
    f18 = F.kr_fb_confirm(D18, listing("2026-11-18_1452"), daum(), yahoo())
    prim = listing("2026-11-16_2211")
    now = dt.datetime(2026, 11, 19, 4, 0, tzinfo=F.KST)
    px, lst, known, src, logs, (full, dshr) = F.kr_second_source(D16, prim, [D17, D18], now, {}, None,
                                                                 fallback=fake_fallback({D17: f17, D18: f18}))
    assert px == D17 and len(lst) == len(f17[0]) and known == {} and len(full) == len(f17[0])
    assert src["px"] == V.PX_SRC_FB and src["date"] == "2026-11-17" and src["must"] == [] and src["fb"]["conf"] == len(f17[0])
    assert src["days"] == {"2026-11-17": V.PX_SRC_FB}
    assert any(loud and "2026-11-18" in t and "관문이 멈춰요" in t for loud, t in logs)     # 11-18 은 확인 못 함 → 크게
    # 필수 종목을 모두 확인한 날이 없으면 1차 출처 그대로 (관문이 멈춰요)
    px, lst, known, src, logs, _ = F.kr_second_source(D16, prim, [D18], now, {}, None, fallback=fake_fallback({D18: f18}))
    assert px == D16 and lst is prim and src["px"] == V.PX_SRC_LISTING and src["fb"]["must"]
    assert any(loud and "필수 종목을 모두 확인한 날이 없어요" in t for loud, t in logs)
    # 끝난 거래일이 없으면 아무것도 받지 않아요
    px, lst, known, src, logs, (full, _) = F.kr_second_source(D16, prim, [], now, {}, None, fallback=None)
    assert px == D16 and src["px"] == V.PX_SRC_LISTING and logs == [] and full is prim
    # 필수 종목이 하나만 빠져도 그날은 기준일이 될 수 없어요 (리뷰 F5)
    f17b = F.kr_fb_confirm(D17, listing("2026-11-17_1529"), daum(), {c: v for c, v in yahoo().items() if c != "012450"})
    assert f17b[1]["must"] == ["012450"]
    px, *_ = F.kr_second_source(D16, prim, [D17], now, {}, None, fallback=fake_fallback({D17: f17b}))
    assert px == D16


def test_earlier_second_source_days_feed_d1_as_final():
    f16 = F.kr_fb_confirm(D16, listing("2026-11-16_0545"), daum(), yahoo())[0]
    files = {D13: listing("2026-11-13_2158")}
    commits = {D13: dt.datetime(2026, 11, 13, 21, 58, tzinfo=F.KST)}
    ss, notes, prev_final = F.kr_recent_sessions(D17, lambda d: files.get(d), commits.get, n=2, special={}, known={D16: f16})
    assert [d for d, _ in ss] == [D16, D13] and prev_final
    assert any("2차 출처" in n for n in notes)


def test_ended_days():
    days = [pd.Timestamp(d) for d in (D13, D16, D17, D18, dt.date(2026, 11, 19))]
    assert F.kr_ended_days(D16, days, dt.date(2026, 11, 19)) == [D17, D18]
    assert F.kr_ended_days(D18, days, dt.date(2026, 11, 19)) == []
    assert F.kr_ended_days(None, days, dt.date(2026, 11, 19), max_days=2) == [D17, D18]


def test_universe_falls_back_to_an_earlier_file():
    big = pd.concat([listing("2026-11-16_0545")] * 100, ignore_index=True)
    files = {D16: big}
    df, how = F.kr_fb_universe(D17, lambda d: files.get(d))
    assert df is big and how.startswith("!!")
    df, how = F.kr_fb_universe(D16, lambda d: files.get(d))
    assert df is big and not how.startswith("!!")
    df, how = F.kr_fb_universe(D16, lambda d: None)
    assert df is None


def test_px_src_final_counts_published_kr():
    src = {"v": 1, "px": "daum+yahoo", "n": {}}
    out = F.px_src_final(src, [{"cls": "kr"}, {"cls": "kr"}, {"cls": "us"}])
    assert out["n"] == {"daum+yahoo": 2} and F.px_src_final(None, []) is None


def test_primary_check_against_yahoo():
    fin = listing("2026-11-16_2211")
    ck = F.kr_primary_check(fin, D16, yahoo())
    # 필수 7 + 표본 (코스피 · 코스닥만) · 다름은 STX(야후 값이 엉뚱) 하나
    assert ck["n"] >= 10 and ck["diff"] and all(d.startswith("011810") for d in ck["diff"])


# ── 3. 관문: 캐시 최종본이 없는 날의 기준 (같은 줄 · 같은 기준) ─────────────────
TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}


def fb_pair():
    """좋은 데이터를 2차 출처 날로: 캐시 최종본은 하루 전 (10-29), pxDate 10-30 은 다음 × 야후로 확인."""
    cur, prev, final = good_pair()
    nk = len(V.kr_stocks(cur["data"]))
    cur["data"]["pxSrc"] = {"v": 1, "px": V.PX_SRC_FB, "date": "2026-10-30", "days": {"2026-10-30": V.PX_SRC_FB},
                            "fb": {"n": nk + 100, "conf": nk + 50, "noDaum": 40, "bad": 0, "noYahoo": 7, "diff": 3, "diffEx": [], "must": []},
                            "must": [], "chk": None, "n": {V.PX_SRC_FB: nk}}
    old = {"date": dt.date(2026, 10, 29), "closes": {c: v * 0.98 for c, v in final["closes"].items()}, "how": "시험 (하루 전)"}
    by = {s["t"]: s["price"] for s in V.kr_stocks(cur["data"])}
    pick = V.px_alt_pick(cur["data"])
    alt = {"date": dt.date(2026, 10, 30), "closes": {c: float(by[c]) for c in pick}, "asked": len(pick), "got": len(pick), "mustMissing": [], "err": []}
    return cur, prev, old, alt


def check(cur, prev, final, alt=None, mode="publish"):
    return V.run_checks(cur, prev, final, TODAY, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                        hilo=hilo_of(cur, V.MUST), alt=alt)


def failed(rep):
    return {r[0] for r in rep.failed}


def test_gate_second_source_day_passes_with_the_same_rows():
    cur, prev, old, alt = fb_pair()
    rep = check(cur, prev, old, alt)
    assert not rep.failed, rep.table()
    names = {r[0]: r for r in rep.rows}
    assert names["pxDate = 최종본 날짜"][3] == "PASS" and names["한국 가격 = 공식 종가"][3] == "PASS"
    assert names["005930 = 공식 종가"][3] == "PASS" and names["필수 종목 두 출처 확인"][3] == "PASS"
    assert names["2차 출처 두 종가가 다른 종목 (경고만)"][3] == "WARN"
    # 같은 데이터 · 관문 확인 없음 → 예전처럼 실패 (캐시 최종본 10-29 ≠ pxDate)
    assert {"pxDate = 최종본 날짜", "한국 가격 = 공식 종가", "005930 = 공식 종가"} <= failed(check(cur, prev, old, None))


def test_gate_fails_closed_when_yahoo_could_not_be_read():
    cur, prev, old, alt = fb_pair()
    for bad_alt in (dict(alt, mustMissing=["005930"]), dict(alt, got=int(alt["asked"] * 0.5)), dict(alt, closes={}, got=0, mustMissing=list(V.MUST)),
                    dict(alt, date=dt.date(2026, 10, 29))):
        assert "pxDate = 최종본 날짜" in failed(check(cur, prev, old, bad_alt))


def test_gate_fails_when_a_published_price_differs_from_yahoo():
    cur, prev, old, alt = fb_pair()
    alt["closes"]["005930"] += 100
    assert "005930 = 공식 종가" in failed(check(cur, prev, old, alt))
    cur, prev, old, alt = fb_pair()
    for c in list(alt["closes"])[7:20]:                               # 표본 13종목이 1원씩 다름 → 99% 아래
        alt["closes"][c] += 1
    assert "한국 가격 = 공식 종가" in failed(check(cur, prev, old, alt))
    cur, prev, old, alt = fb_pair()
    alt["closes"]["005930"] += 0.5                                     # 같은 호가가 아니면 같지 않아요 (반올림으로 맞추지 않아요)
    assert "005930 = 공식 종가" in failed(check(cur, prev, old, alt))


def test_gate_needs_the_pipeline_confirmation_too():
    for change in ({"must": ["005930"]}, {"px": V.PX_SRC_LISTING}, {"date": "2026-10-29"}):
        cur, prev, old, alt = fb_pair()
        cur["data"]["pxSrc"].update(change)
        assert "pxDate = 최종본 날짜" in failed(check(cur, prev, old, alt)), change
    cur, prev, old, alt = fb_pair()
    cur["data"]["pxSrc"]["fb"]["conf"] = 10
    assert "pxDate = 최종본 날짜" in failed(check(cur, prev, old, alt))
    cur, prev, old, alt = fb_pair()
    cur["data"]["pxSrc"]["must"] = ["005930"]
    assert "필수 종목 두 출처 확인" in failed(check(cur, prev, old, alt))


def test_gate_uses_the_cache_final_file_when_it_exists():
    """캐시에 pxDate 최종본이 있으면 예전 그대로 그것과 비교해요 (야후 확인이 있어도)."""
    cur, prev, final = good_pair()
    _, _, _, alt = fb_pair()
    cur["data"]["pxSrc"] = fb_pair()[0]["data"]["pxSrc"]
    final = dict(final, closes={c: v + 1 for c, v in final["closes"].items()})       # 캐시 최종본과 가격이 다르면
    assert "한국 가격 = 공식 종가" in failed(check(cur, prev, final, alt))
    later = dict(final, date=dt.date(2026, 10, 31))
    assert "pxDate = 최종본 날짜" in failed(check(cur, prev, later, alt))


def test_gate_live_mode_accepts_the_second_source_day():
    cur, _, _, alt = fb_pair()
    alt["mode"] = "live"
    rep = check(cur, None, None, alt, mode="live")
    names = {r[0]: r for r in rep.rows}
    assert names["pxDate 최종본 여부"][3] == "PASS" and names["한국 가격 = 공식 종가"][3] == "PASS"
    assert "최종본 날짜 계산" in failed(check(cur, None, None, None, mode="live"))
    assert "최종본 날짜 계산" in failed(check(cur, None, None, dict(alt, mode="publish"), mode="live"))   # 방식이 다르면 쓰지 않아요
    # 캐시에 pxDate 최종본이 있으면 배포 · 감시도 그것과 비교해요 (리뷰 V11)
    fin = {"date": dt.date(2026, 10, 30), "closes": {c: v + 1 for c, v in alt["closes"].items()}, "how": "캐시 최종본"}
    assert "한국 가격 = 공식 종가" in failed(check(cur, None, fin, alt, mode="live"))


def test_http_px_alt_never_raises():
    cur, _, _, _ = fb_pair()

    def boom(sym, d, close_time=None):
        raise ConnectionError("no network")
    d30, k = dt.date(2026, 10, 30), {"sleep": lambda s: None}
    daum_ok = lambda c, d: (1000.0, "daum")                                     # noqa: E731
    alt = V.http_px_alt(cur["data"], d30, fetch=boom, fetch_daum=daum_ok, **k)
    assert alt["got"] == 0 and set(alt["mustMissing"]) == set(V.MUST) and alt["err"]
    alt = V.http_px_alt(cur["data"], d30, fetch=lambda s, d, close_time=None: (1000.0, "bar"), fetch_daum=boom, **k)
    assert alt["got"] == 0 and set(alt["mustMissing"]) == set(V.MUST)        # 다음을 받지 못하면 확인 못 함 (야후만으로는 안 돼요)
    ok = V.http_px_alt(cur["data"], d30, fetch=lambda s, d, close_time=None: (1000.0, "meta"), fetch_daum=daum_ok, **k)
    assert ok["got"] == ok["asked"] and not ok["mustMissing"] and ok["asked"] == len(V.MUST) + V.PX_CHECK_SAMPLE and ok["meta"] == ok["got"]
    dis = V.http_px_alt(cur["data"], d30, fetch=lambda s, d, close_time=None: (1001.0, "bar"), fetch_daum=daum_ok, **k)
    assert dis["got"] == 0 and len(dis["disagree"]) == dis["asked"] and all(v == 1000.5 for v in dis["closes"].values())
    live = V.http_px_alt(cur["data"], d30, fetch=boom, fetch_daum=daum_ok, mode="live", **k)
    assert live["got"] == live["asked"] and live["mode"] == "live"           # 배포 · 감시: 다음 + 발행 기록 (야후 일봉이 비어도)
    seen = []
    V.http_px_alt(cur["data"], CSAT, fetch=lambda s, d, close_time=None: (seen.append(close_time), (None, "x"))[1], fetch_daum=daum_ok,
                  special=V.load_special_sessions(), **k)
    assert set(seen) == {dt.time(16, 30)}                                  # 수능일은 16:30 마감 뒤여야 해요


def test_yahoo_day_close_reads_the_kst_day():
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            ts = [int(dt.datetime(2026, 11, d, 9, 0, tzinfo=V.KST).timestamp()) for d in (16, 17, 18)]
            return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{"close": [196800.0, 190300.0, None]}]}}]}}
    assert V._yahoo_day_close("005930.KS", D17, get=lambda u: R()) == (190300.0, "bar")
    assert V._yahoo_day_close("005930.KS", D18, get=lambda u: R())[0] is None          # 종가 빈 값 · meta 없음


# ── 5. 야후 일봉 종가가 빈 날: 마감 뒤 regularMarketPrice (2026-11-19) ─────────────────
CSAT = dt.date(2026, 11, 19)


def chart():
    """실제 응답 (11-19 02:15 KST): 005930.KS 11-18 일봉 종가 null · regularMarketPrice 194,700 · regularMarketTime 11-18 15:30:16 KST."""
    return json.load(open(os.path.join(FX, "yahoo_chart_005930_KS.json"), encoding="utf-8"))["chart"]["result"][0]


def at_kst(d, hh, mm, ss=0):
    return int(dt.datetime.combine(d, dt.time(hh, mm, ss), F.KST).timestamp())


@pytest.mark.parametrize("fn", [lambda r, d, t: F.yahoo_chart_close(r, d, t), lambda r, d, t: V.yahoo_day_close(r, d, t)])
def test_empty_daily_close_uses_the_price_after_the_close(fn):
    r = chart()
    assert r["indicators"]["quote"][0]["close"][-1] is None
    assert fn(r, D18, dt.time(15, 30)) == (194700.0, "meta")                 # 다음 11-18 종가도 194,700
    assert fn(r, D17, dt.time(15, 30)) == (190300.0, "bar")                  # 종가가 있는 날은 일봉 그대로
    early = dict(r, meta=dict(r["meta"], regularMarketTime=at_kst(D18, 15, 10)))
    assert fn(early, D18, dt.time(15, 30))[0] is None                         # 마감 전 시각 → 장중 값이라 확인 못 함
    other = dict(r, meta=dict(r["meta"], regularMarketTime=at_kst(D17, 15, 30, 16)))
    assert fn(other, D18, dt.time(15, 30))[0] is None                         # 다른 날의 시각 → 확인 못 함
    nxt = dict(r, meta=dict(r["meta"], regularMarketTime=at_kst(CSAT, 9, 5)))
    assert fn(nxt, D18, dt.time(15, 30))[0] is None                           # 다음 거래일의 값 → 확인 못 함
    assert fn(r, D18, dt.time(16, 30))[0] is None                             # 수능일 같은 늦은 마감이면 15:30 값은 장중
    late = dict(r, meta=dict(r["meta"], regularMarketTime=at_kst(D18, 16, 5)))
    assert fn(late, D18, dt.time(15, 30))[0] is None                          # 마감 + 10분 뒤 시각 (시간외일 수 있어요) → 확인 못 함
    edge = dict(r, meta=dict(r["meta"], regularMarketTime=at_kst(D18, 15, 39, 59)))
    assert fn(edge, D18, dt.time(15, 30)) == (194700.0, "meta")
    nobar = dict(r, timestamp=r["timestamp"][:-1], indicators={"quote": [{"close": r["indicators"]["quote"][0]["close"][:-1]}]})
    assert fn(nobar, D18, dt.time(15, 30))[0] is None                         # 그날 일봉이 없으면 meta 가 그날이어도 안 돼요 (리뷰 F24 · V8)
    assert fn(r, CSAT, dt.time(16, 30))[0] is None                            # 그날 일봉이 없으면 확인 못 함
    assert fn(dict(r, meta={}), D18, dt.time(15, 30))[0] is None


def test_fill_day_reads_only_the_missing_closes_and_counts_the_meta_path():
    yahoo = {"005930": {D17: 190300.0}, "000660": {D17: 1.0, D18: 1153000.0}}
    asked = []

    def fetch(sym):
        asked.append(sym)
        if sym.startswith("000270"):
            raise ConnectionError("x")
        return chart()
    out = F.yahoo_fill_day(yahoo, {"005930": "KOSPI", "000660": "KOSPI", "000270": "KOSPI", KONEX: "KONEX"}, D18, dt.time(15, 30), fetch=fetch)
    assert sorted(asked) == ["000270.KS", "005930.KS"]                        # 이미 있는 종목 · 코넥스는 묻지 않아요
    assert yahoo["005930"][D18] == 194700.0 and out["meta"] == 1 and out["fail"] == 1 and out["metaCodes"] == {"005930"}


def test_fallback_counts_meta_confirmations():
    uni = listing("2026-11-18_1452")

    def fetch_daum(codes, n):
        return daum(), []

    def fetch_yahoo(cm, start, end):
        return {c: {k: v for k, v in d.items() if k != D18} for c, d in yahoo().items()}, 0

    def fill(y, cm, d, close_time):
        mc = set()
        for c, rows in daum().items():
            if c in cm and d in rows:
                y.setdefault(c, {})[d] = rows[d]["tradePrice"]              # 시험: 야후 meta 값 = 다음 종가
                mc.add(c)
        return {"need": len(mc), "bar": 0, "meta": len(mc), "none": 0, "fail": 0, "metaCodes": mc}
    out, notes = F.kr_fallback_days([D18], lambda d: (uni, "시험"), dt.datetime(2026, 11, 19, 2, 15, tzinfo=F.KST), {},
                                    fetch_daum=fetch_daum, fetch_yahoo=fetch_yahoo, fill_day=fill)
    fr, st = out[D18]
    assert st["must"] == [] and st["yMeta"] == len(fr) > 0 and F.px_src_counts(st)["yMeta"] == st["yMeta"]
    assert any("regularMarketPrice" in n for n in notes)


# ── 6. 커밋 시각을 확인하지 못한 캐시 파일은 최종본이 아니에요 (2026-11-19 · 더 엄격하게만) ─────────
def test_pipeline_never_treats_an_unknown_commit_as_final(monkeypatch, capsys):
    files = {D18: pd.concat([listing("2026-11-18_1452")] * 100, ignore_index=True),
             D17: pd.concat([listing("2026-11-17_1529")] * 100, ignore_index=True),
             D16: pd.concat([listing("2026-11-16_2211")] * 100, ignore_index=True)}
    commits = {D16: dt.datetime(2026, 11, 16, 22, 11, tzinfo=F.KST)}            # 11-17 · 11-18 은 API 실패 (None)
    monkeypatch.setattr(F, "_fetch_listing_csv", lambda d: files.get(d))
    monkeypatch.setattr(F, "_listing_commit_kst", lambda d: commits.get(d))
    d, df = F.load_kr_listing(CSAT)
    out = capsys.readouterr().out
    assert d == D16 and "커밋 시각 확인 불가 → 최종본으로 보지 않아요" in out             # 예전 규칙이면 11-17 장중 파일 (190,200)
    # 그 뒤 끝난 거래일은 2차 출처가 정해요 (다음 × 야후)
    f17 = F.kr_fb_confirm(D17, listing("2026-11-17_1529"), daum(), yahoo())
    px, lst, _, src, _, _ = F.kr_second_source(d, df, [D17, D18], dt.datetime(2026, 11, 19, 4, 0, tzinfo=F.KST), {}, None,
                                              fallback=fake_fallback({D17: f17}))
    assert px == D17 and src["px"] == V.PX_SRC_FB and lst.set_index("Code").loc["005930", "Close"] == 190300
    # 2차 출처도 없으면 1차 출처 그대로 → 관문의 '끝난 거래일' 줄이 발행을 막아요
    px, lst, _, src, logs, _ = F.kr_second_source(d, df, [D17, D18], dt.datetime(2026, 11, 19, 4, 0, tzinfo=F.KST), {}, None,
                                                 fallback=fake_fallback({}))
    assert px == D16 and src["px"] == V.PX_SRC_LISTING and any(loud for loud, _ in logs)
    # d1 · val20 의 앞 날도: 커밋 시각을 모르면 최종본이 아니에요
    ss, notes, prev_final = F.kr_recent_sessions(D18, lambda d: files.get(d), lambda d: commits.get(d), n=3, special={})
    assert [x for x, _ in ss] == [D16] and prev_final is False
    assert any("커밋 시각을 확인하지 못해" in n for n in notes)


def test_gate_never_treats_an_unknown_commit_as_final():
    texts = {D17: open(os.path.join(FX, "krx_2026-11-17_1529.csv"), encoding="utf-8").read(),
             D18: open(os.path.join(FX, "krx_2026-11-18_1452.csv"), encoding="utf-8").read(),
             D16: open(os.path.join(FX, "krx_2026-11-16_2211.csv"), encoding="utf-8").read()}
    commits = {D16: dt.datetime(2026, 11, 16, 22, 11, tzinfo=V.KST)}
    ok, how = V.is_final(D17, texts[D17], texts.get, commits.get, CSAT, {})
    assert not ok and "확인 불가" in how                                         # 예전: 11-18 장중 파일이 있어 최종본으로 봤어요
    d, closes, how = V.latest_final(CSAT, texts.get, commits.get, special={})
    assert d == D16 and closes["005930"] == 196800
    # 파이프라인이 그 장중 파일(11-17)로 발행하려 하면 관문이 막아요 (2차 출처 확인 없음)
    cur, prev, final = good_pair()
    final = dict(final, date=dt.date(2026, 10, 29))
    assert "pxDate = 최종본 날짜" in failed(check(cur, prev, final))


def test_commit_time_lookups_retry_before_giving_up(monkeypatch):
    calls = []

    class R:
        status_code = 502

        def json(self):
            return []
    monkeypatch.setattr(V.requests, "get", lambda *a, **k: (calls.append(1), R())[1])
    assert V.http_commit_kst(D17, sleep=lambda s: None) is None and len(calls) == 3
    calls.clear()
    monkeypatch.setattr(F.requests, "get", lambda *a, **k: (calls.append(1), R())[1])
    assert F._listing_commit_kst(D17, sleep=lambda s: None) is None and len(calls) == 3


def test_gate_main_fetches_yahoo_only_for_a_second_source_day(monkeypatch, tmp_path):
    cur, prev, old, alt = fb_pair()
    files = {k: cur[k] for k in ("data", "corp", "disc", "macro")}
    seen, asked = [], []
    monkeypatch.setattr(V, "load_dir", lambda d: files)
    monkeypatch.setattr(V, "load_prev", lambda *a, **k: prev)
    monkeypatch.setattr(V, "load_prev_corp", lambda *a, **k: prev["corp"])
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (old["date"], old["closes"], "시험"))
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: SESSIONS)
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: {})
    monkeypatch.setattr(V, "http_px_alt", lambda data, px, special=None, mode="publish": (asked.append(px), alt)[1])
    monkeypatch.setattr(V, "run_checks", lambda *a, **k: (seen.append(k.get("alt")), V.Report())[1])
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    V.main(["--dir", "unused", "--prev-dir", str(tmp_path), "--today", "2026-10-31"])
    assert asked == [dt.date(2026, 10, 30)] and seen[-1] is alt
    files["data"] = dict(files["data"], pxSrc=dict(files["data"]["pxSrc"], px=V.PX_SRC_LISTING))
    V.main(["--dir", "unused", "--prev-dir", str(tmp_path), "--today", "2026-10-31"])
    assert asked == [dt.date(2026, 10, 30)] and seen[-1] is None             # 1차 출처라고 하면 야후를 받지 않아요 (예전 그대로)


def test_px_src_shape_row():
    cur, prev, old, alt = fb_pair()
    cur["data"]["pxSrc"]["fb"]["conf"] = "많음"
    assert "국내 가격 출처 (pxSrc)" in failed(check(cur, prev, old, alt))
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)
    assert ("국내 가격 출처 (pxSrc)", "-", "pxSrc 없음 (2026-11-19 전 발행본)", "SKIP") in [tuple(r) for r in rep.rows] or \
        any(r[0] == "국내 가격 출처 (pxSrc)" and r[3] == "SKIP" for r in rep.rows)
    cur["data"]["pxSrc"] = {"v": 1, "px": V.PX_SRC_LISTING, "date": "2026-10-30", "must": [], "n": {"listing": 2400},
                            "chk": {"src": "yahoo", "n": 207, "same": 206, "none": 0, "diff": ["011810 STX 18360/410465.12"]}}
    rep = check(cur, prev, final)
    assert not rep.failed and "1차 출처 야후 확인 (경고만)" in {r[0] for r in rep.warned}


# ── 4. 업종 이어 쓰기 (KRX-DESC 가 업종을 비운 날) ─────────────────────────
def test_desc_parse_round_trips_every_published_description():
    """지난 발행본(2026-11-17 · data.json)의 국내 설명을 모두 읽을 수 있어요 — 업종 이름 안의 ' · ' 도."""
    d = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8"))
    kr = [x for x in d["stocks"] if x.get("cls") == "kr" and x.get("dk")]
    assert len(kr) > 2000
    for x in kr:
        p = F.kr_desc_parse(x["dk"])
        assert p is not None, x["dk"]
    assert F.kr_desc_parse("전동기, 발전기 및 전기 변환 · 공급 · 제어 장치 제조업 · 주요제품: 연료전지 · KOSPI 상장 · 시가총액 1.7조원") == \
        ("전동기, 발전기 및 전기 변환 · 공급 · 제어 장치 제조업", "연료전지")
    assert F.kr_desc_parse("KOSPI 상장 · 시가총액 1.2조원") == ("", "")
    assert F.kr_desc_parse("주요제품: 반도체 · KOSDAQ 상장") == ("", "반도체")


def test_desc_carry_forward():
    prev = {"publishedAt": "2026-11-17T08:30:00+09:00", "stocks": [
        {"t": "005930", "cls": "kr", "dk": "통신 및 방송 장비 제조업 · 주요제품: 반도체 · KOSPI 상장 · 시가총액 1,150.5조원"},
        {"t": "000660", "cls": "kr", "dk": "KOSPI 상장 · 시가총액 774.3조원"}]}
    pdesc, day, bad = F.kr_prev_desc(prev)
    assert pdesc == {"005930": ("통신 및 방송 장비 제조업", "반도체")} and day == "2026-11-17" and bad == 0
    desc = {"005930": ("", ""), "000660": ("", ""), "035420": ("포털", "검색")}
    out, carried, none = F.kr_desc_carry(desc, pdesc, {"005930", "000660", "035420", "999990"})
    assert out["005930"] == ("통신 및 방송 장비 제조업", "반도체") and out["035420"] == ("포털", "검색")
    assert carried == ["005930"] and none == ["000660", "999990"]
    assert F.map_sector_kr(*out["005930"]) == F.map_sector_kr("통신 및 방송 장비 제조업", "반도체")
    # 지난 발행본도 이어 쓴 것이면 그 날짜 (더 오래된 날)
    prev["indSrc"] = {"carried": 5, "asOf": "2026-11-10"}
    assert F.kr_prev_desc(prev)[1] == "2026-11-10"


def test_ind_src_gate_row_warns_only():
    cur, prev, final = good_pair()
    cur["data"]["indSrc"] = {"v": 1, "desc": 0, "carried": 2400, "none": 60, "newNone": 2, "asOf": "2026-10-29", "from": "KRX-DESC + prev"}
    rep = check(cur, prev, final)
    assert not rep.failed and "국내 업종 이어 쓴 종목 (경고만)" in {r[0] for r in rep.warned}
    cur["data"]["indSrc"] = dict(cur["data"]["indSrc"], carried=0)
    rep = check(cur, prev, final)
    assert "국내 업종 이어 쓴 종목 (경고만)" not in {r[0] for r in rep.warned}
    cur["data"]["indSrc"] = dict(cur["data"]["indSrc"], carried=10, asOf="2026-10-01")
    rep = check(cur, prev, final)
    assert any(t == "국내 업종 글자가 오래됨" for t, _ in rep.details)


def test_shared_constants_come_from_the_gate_file():
    assert F.PX_SRC_FB is V.PX_SRC_FB and F.PX_YAHOO_SUFFIX is V.PX_YAHOO_SUFFIX and F.PX_CHECK_SAMPLE == V.PX_CHECK_SAMPLE
    assert F.IND_CARRY_WARN_DAYS == V.IND_CARRY_WARN_DAYS
    assert F.yahoo_kr_symbol("005930", "KOSPI") == "005930.KS" and F.yahoo_kr_symbol("247540", "KOSDAQ GLOBAL") == "247540.KQ"
    assert F.yahoo_kr_symbol(KONEX, "KONEX") is None
    assert V.px_check_sample([f"{i:06d}" for i in range(1000)], 4) == ["000000", "000250", "000500", "000750"]


# ── 7. 리뷰 (2026-11-19) ─────────────────────────────────────────
def test_gate_second_source_path_needs_a_finished_day():
    """리뷰: 장중(11:00) 에 pxDate = 오늘이면 2차 출처 기준을 쓰지 않아요 · 어제여도 마감 + 30분 전 (수능일 17:00) 이면 안 돼요."""
    cur, prev, old, alt = fb_pair()
    data = cur["data"]
    px = dt.date(2026, 10, 30)
    ok, _ = V.px_alt_confirms(data, alt, px, old, today=dt.date(2026, 10, 31), now=NOW, special={})
    assert ok
    ok, why = V.px_alt_confirms(data, alt, px, old, today=px, now=dt.datetime(2026, 10, 30, 11, 0, tzinfo=V.KST), special={})
    assert not ok and "끝나지 않은 날" in why
    sp = {px: (dt.time(10, 0), dt.time(16, 30), "수능")}
    ok, why = V.px_alt_confirms(data, alt, px, old, today=dt.date(2026, 10, 31), now=dt.datetime(2026, 10, 30, 16, 59, tzinfo=V.KST), special=sp)
    assert not ok and "마감 + 30분" in why
    ok, _ = V.px_alt_confirms(data, alt, px, old, today=None, now=None, special={})
    assert not ok


def test_gate_px_src_date_must_be_the_price_date():
    cur, prev, final = good_pair()
    cur["data"]["pxSrc"] = {"v": 1, "px": V.PX_SRC_LISTING, "date": "2026-10-29", "must": [], "n": {"listing": 2400}, "chk": None}
    assert "국내 가격 출처 (pxSrc)" in failed(check(cur, prev, final))


def test_gate_never_asks_yahoo_for_konex():
    cur, _, _, _ = fb_pair()
    kx = {"t": KONEX, "cls": "kr", "price": 1176000.0, "dk": "기타 · KONEX 상장 · 시가총액 1.2조원"}
    assert V.px_alt_symbol(kx) is None
    cur["data"]["stocks"] = [dict(kx, t=f"49{i:04d}") for i in range(300)] + cur["data"]["stocks"]
    pick = V.px_alt_pick(cur["data"])
    assert not any(t.startswith("49") and len(t) == 6 and t[2:].isdigit() and int(t[2:]) < 300 for t in pick)
    assert all(not sym.endswith(".KQ") or "KOSDAQ" for sym in pick.values())


def test_meta_fill_uses_the_csat_close():
    """리뷰 F21: 수능일(11-19) 마지막 날은 16:30 마감으로 meta 를 봐요."""
    uni = listing("2026-11-18_1452")
    seen = []

    def fill(y, cm, d, close_time):
        seen.append((d, close_time))
        return {"need": 0, "bar": 0, "meta": 0, "none": 0, "fail": 0, "metaCodes": set()}
    F.kr_fallback_days([CSAT], lambda d: (uni, "시험"), dt.datetime(2026, 11, 20, 4, 0, tzinfo=F.KST), F.load_krx_special_sessions(),
                       fetch_daum=lambda codes, n: ({}, []), fetch_yahoo=lambda cm, a, b: ({}, 0), fill_day=fill)
    assert seen == [(CSAT, dt.time(16, 30))]


def test_konex_is_not_asked_and_low_coverage_is_loud():
    uni = listing("2026-11-16_0545")
    asked = []

    def fetch_daum(codes, n):
        asked.extend(codes)
        return daum(), []
    out, notes = F.kr_fallback_days([D16], lambda d: (uni, "시험"), dt.datetime(2026, 11, 19, 4, 0, tzinfo=F.KST), {},
                                    fetch_daum=fetch_daum, fetch_yahoo=lambda cm, a, b: (yahoo(), 0),
                                    fill_day=lambda *a: {"need": 0, "bar": 0, "meta": 0, "none": 0, "fail": 0, "metaCodes": set()})
    assert KONEX not in asked and len(asked) == 12
    loud, txt = F.kr_fb_note(D16, out[D16][1], {})
    assert loud and "98%" in txt                                              # 12 종목 중 10 확인 (STX 다름 · 하나 더) — 98% 아래


def test_unconfirmed_preferred_keeps_the_share_count_and_blanks_ev():
    """리뷰 B1: 2차 출처 날 우선주(005935) 종가를 확인하지 못해도 삼성전자의 주식 수는 그대로 (그날 전체 목록) · EV · P/CF 는 비우고 까닭을 달아요."""
    full = pd.DataFrame([{"Code": "005930", "Name": "삼성전자", "Market": "KOSPI", "Stocks": 5846278608, "Marcap": 190300 * 5846278608},
                         {"Code": "005935", "Name": "삼성전자우", "Market": "KOSPI", "Stocks": 802371203, "Marcap": None}])
    confirmed = full[full["Code"] == "005930"]
    s = {"t": "005930", "shr": 5846278608}
    assert F.kr_pref_shares(confirmed) == {}                                    # 확인된 종목만 쓰면 우선주가 빠져요 (예전 버그)
    full_shares = F.kr_pref_shares(full)
    assert full_shares == {"00593": [802371203.0]}
    assert F.per_share_count(s, full_shares) == 5846278608 + 802371203
    from test_pipeline import kr_trio
    kr, fin = kr_trio()
    plain = {c["t"]: c for c in F.build_corp(kr, fin, "2026-11-02")["companies"]}
    assert plain["005930"].get("evR") is not None and "evNo" not in plain["005930"]
    blank = {c["t"]: c for c in F.build_corp(kr, fin, "2026-11-02", pref_missing={"00593"})["companies"]}
    assert blank["005930"]["evNo"] == "prefPx" and not {"evE", "evR", "pcf"} & set(blank["005930"])
    src = inspect.getsource(F.fetch_korea)
    assert "pref_shares = kr_pref_shares(pref_list)" in src and "pref_caps = kr_pref_caps(listing)" in src
    assert 'pref_missing=kmeta.get("_prefCapMissing")' in inspect.getsource(F.main)
