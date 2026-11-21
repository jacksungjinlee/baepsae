# -*- coding: utf-8 -*-
"""#161 (Jack, 2026-11-21): 2차 출처 날의 발행 판단 — 확인 비율 바닥 · 같은 날 다시 발행 (tools/publish_hold.py · update-data.yml 단계 id hold).

Jack (그대로): "(c), with no new timer for Jack. KRX's final file has been stuck since 11-16, so treat Daum × Yahoo as the normal path.
Publish at 06:40 with what's confirmed (carries with their date line). Later runs update that day's data when more closes are confirmed.
Hold only if confirmed coverage is below a floor; set it from last week's 06:40 coverage and show the number in the PR."

- 바닥: 코스피 · 코스닥 확인 비율 (이 실행의 두 출처 확인 + 같은 날 다시 쓴 확인 종가) ÷ 그날 코스피 · 코스닥 목록이 바닥보다 낮으면 보류 — 몇 시든.
  코넥스 (#158 fb.knx.kept) · 마지막 확인 종가 (#159 pxSrc.own · pxd) 는 세지 않아요. 1차 출처 날은 그대로.
- 같은 날 다시 발행: already_published.py 는 확인 못 한 종가가 남은 2차 출처 날 뒤의 실행을 멈추지 않아요. 한국 · 미국 기준일이 같은 실행은 더
  나을 때만 발행해요 (확인이 더 많고 지난 발행본이 그 날짜 종가로 실은 종목을 하나도 잃지 않았을 때 — fetch_data.kr_same_day_reuse 가 그 종가를
  다시 써요). 관문의 '직전 발행본과 비교하는 줄' 은 같은 날 다시 발행을 그대로 통과해요 (줄은 그대로).
- 워크플로: 판단은 한 단계 (hold) 에서 한 번, 보류면 발행 두 단계만 건너뛰어요 (커밋 · data 브랜치 푸시 · 배포 없음), 실행은 초록 (감시에는 중립).
- fetch_data 의 진짜 집계 길로 만든 기록을 그대로 읽어요 (계약 시험 · 코넥스 단계 포함 · 같은 날 다시 쓰기 포함).
"""
import copy
import datetime as dt
import json
import os
import stat
import subprocess
import sys

import pandas as pd
import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import already_published as A          # noqa: E402
import fetch_data as F                 # noqa: E402
import publish_hold as P               # noqa: E402
import validate_data as V              # noqa: E402
import watchdog as W                   # noqa: E402

WF = os.path.join(ROOT, ".github", "workflows", "update-data.yml")
KST = dt.timezone(dt.timedelta(hours=9))
FB, LISTING = P.PX_SRC_FB, "listing"
HOLD_STEP = "발행 판단 (2차 출처 날 확인 비율 바닥 · 같은 날 다시 발행은 더 나을 때만)"
PUBLISH = ("커밋 & 푸시", "data 브랜치에 올리기")
GATE = "발행 관문 (validate_data.py)"
IF_PUBLISH = "${{ !inputs.dry_run && steps.hold.outputs.hold != 'true' }}"


def kst(y, m, d, hh, mm, ss=0):
    return dt.datetime(y, m, d, hh, mm, ss, tzinfo=KST)


def reuse(kk, lost=0, n=None):
    return {"v": 1, "from": "2026-11-21T06:40:00+09:00", "earlier": 2474, "n": kk if n is None else n, "kk": kk, "codes": [], "lost": lost,
            "lostEx": []}


def fb_data(px, conf, noYahoo=6, mkt=107, diff=25, own=None, stocks=None, n=None, knx_kept=None, us=None, rr=None):
    """2차 출처 날 data.json 의 필요한 부분. 기본값은 2026-11-20 06:40 발행본의 실제 수 (목록 2,878 · 코스피 · 코스닥 2,771 · 확인 2,740 ·
    코넥스 107 · 야후 없음 6 · 다름 25). conf 는 이 실행의 코스피 · 코스닥 확인 수. knx_kept 를 주면 #158 모양 (fb.conf = conf + knx_kept ·
    fb.knx). rr 을 주면 같은 날 다시 쓴 기록 (pxSrc.own.reuse)."""
    fb = {"n": n if n is not None else conf + mkt + noYahoo + diff, "conf": conf, "mkt": mkt, "noDaum": 0, "bad": 0, "noYahoo": noYahoo,
          "diff": diff, "yMeta": 1, "diffEx": [], "must": [], "cut": {"s": 600, "daum": 0, "yahoo": 0, "fill": 0}, "diffT": []}
    if knx_kept is not None:                  # fetch_data.px_src_counts (#158) 와 같은 모양
        fb["conf"] = conf + knx_kept
        fb["knx"] = {"n": 107, "conf": knx_kept + 2, "kept": knx_kept, "capOut": 2, "floor": 120000000000, "noNaver": 3, "bad": 0,
                     "noYahoo": 60, "diff": 15, "yMeta": 0, "diffEx": [], "anchor": "2026-11-16", "adj": 0, "noAnchor": 2, "adjEx": [],
                     "left": [], "cut": {"s": 600, "yahoo": 0, "fill": 0, "naver": 0}, "diffT": []}
    src = {"v": 1, "px": FB, "date": px, "days": {px: FB}, "fb": fb, "must": [], "chk": None, "n": {FB: 2475}}
    if own is None and rr is not None:
        own = {"v": 1, "max": 5, "n": 0, "codes": [], "unconf": noYahoo + diff + mkt, "drop": {}, "dropEx": [], "bad": {"n": 0, "rows": []}}
    if own is not None:
        src["own"] = dict(own)
        if rr is not None:
            src["own"]["reuse"] = rr
    return {"pxDate": px, "usPxDate": us or px, "pxSrc": src, "stocks": stocks or [{"t": "005930", "cls": "kr", "price": 50000.0}]}


def listing_data(px, us=None):
    return {"pxDate": px, "usPxDate": us or px, "stocks": [{"t": "005930", "cls": "kr", "price": 50000.0}],
            "pxSrc": {"v": 1, "px": LISTING, "date": px, "days": {}, "fb": None, "must": [],
                      "chk": {"src": "yahoo", "n": 98, "same": 98, "none": 2, "diff": []}, "n": {LISTING: 2475}}}


# ── 1. 바닥 ──────────────────────────────────────────────────
def test_the_floor_against_last_weeks_0640_publishes():
    """지난주 06:40 발행 (data 브랜치): 11-19 2,743 / 2,771 = 98.99% · 11-20 2,740 / 2,771 = 98.88% — 둘 다 97% 바닥 위 (발행)."""
    assert P.COVERAGE_FLOOR_PCT == 97
    for conf in (2743, 2740):
        d = P.floor_decision(FB, conf, 2771)
        assert d.hold is False and d.kind == "publish" and "2,771" in d.why
    # 97% 의 2,771 = 2,687.87 → 2,688 부터 발행 (확인 못 한 종목 83 까지)
    assert P.floor_decision(FB, 2688, 2771).hold is False
    d = P.floor_decision(FB, 2687, 2771)
    assert d.hold is True and d.kind == "floor" and "모자람 1" in d.why and "2,688" in d.why
    # 야후가 빈 새벽 (11-19 밤 같은 수: 약 240 확인 못 함) → 보류
    d = P.floor_decision(FB, 2526, 2771)
    assert d.hold is True and d.loud is True and "91.16%" in d.why and "다음 실행이 다시 해요" in d.why


def test_exactly_the_floor_publishes():
    assert 2716 * 100 == 97 * 2800                                                # 딱 97%
    assert P.floor_decision(FB, 2716, 2800).hold is False
    assert P.floor_decision(FB, 2715, 2800).hold is True
    assert P.floor_decision(FB, 99, 100, floor=99).hold is False and P.floor_decision(FB, 98, 100, floor=99).hold is True


@pytest.mark.parametrize("hh,mm", [(0, 5), (3, 47), (6, 40), (8, 17), (10, 53), (14, 47), (23, 59)])
def test_the_floor_applies_at_any_time_of_day(hh, mm):
    now = kst(2026, 11, 21, hh, mm)
    d, _ = P.evaluate(fb_data("2026-11-20", 2526, noYahoo=220), "data.json", fb_data("2026-11-19", 2740), "git HEAD:data.json", now)
    assert d.hold is True and d.kind == "floor"
    d, _ = P.evaluate(fb_data("2026-11-20", 2740), "data.json", fb_data("2026-11-19", 2740), "git HEAD:data.json", now)
    assert d.hold is False and d.kind == "publish"


@pytest.mark.parametrize("mode", [LISTING, None, "", "daum", "Daum+Yahoo"])
def test_a_normal_day_never_holds(mode):
    d = P.floor_decision(mode, 10, 2771)
    assert d.hold is False and d.loud is False and "2차 출처 날이 아니에요" in d.why
    assert P.kk_counts(listing_data("2026-11-20"))[0] is None


def test_unknown_coverage_never_holds_and_says_so():
    for total, listing in ((None, 2771), (2700, None), (None, None), (5, 0)):
        d = P.floor_decision(FB, total, listing)
        assert d.hold is False and d.loud is True and d.kind == "unknown" and "보류하지 않아요" in d.why


# ── 2. 셈 (kk_counts) ────────────────────────────────────────
def test_konex_kept_is_subtracted_and_the_listing_is_kospi_and_kosdaq():
    d = fb_data("2026-11-20", 2700, noYahoo=46, knx_kept=23)
    assert d["pxSrc"]["fb"]["conf"] == 2723
    c, why = P.kk_counts(d)
    assert (c["conf"], c["listing"], c["total"], c["reuse"], c["kept"]) == (2700, 2771, 2700, 0, 23) and "코넥스 23 는 빼고" in why
    # 2,650 + 코넥스 23 = 2,673 이지만 코스피 · 코스닥은 2,650 = 95.6% → 보류 (빼지 않으면 96.5% 로 보였어요)
    assert P.evaluate(fb_data("2026-11-20", 2650, noYahoo=96, knx_kept=23), "data.json", None, "없음", kst(2026, 11, 21, 6, 41))[0].hold is True


@pytest.mark.parametrize("knx", ["x", None, {}, {"kept": None}, {"kept": True}, {"kept": -1}, {"kept": 99999}])
def test_an_odd_konex_record_is_not_used(knx):
    d = fb_data("2026-11-20", 2700, knx_kept=23)
    d["pxSrc"]["fb"]["knx"] = knx
    c, why = P.kk_counts(d)
    assert c is None and ("knx" in why or "칸이 맞지 않아요" in why)


def test_carried_closes_never_count_as_confirmed():
    """#159: 확인 못 한 종목은 마지막 확인 종가로 실어요 (pxSrc.own · 종목의 pxd). 그 종목은 두 출처 확인이 아니에요."""
    carried = [{"t": f"9{i:05d}", "cls": "kr", "price": 1000, "pxd": "2026-11-19"} for i in range(129)]
    own = {"v": 1, "n": 129, "codes": [s["t"] for s in carried], "max": 5, "unconf": 160}
    cur = fb_data("2026-11-20", 2700, noYahoo=46, own=own, stocks=[{"t": "005930", "cls": "kr", "price": 50000}, *carried])
    cur["pxSrc"]["n"] = {FB: 2346}
    assert P.kk_counts(cur)[0]["total"] == 2700                                   # 2,700 + 129 가 아니에요
    bad = fb_data("2026-11-20", 2700, noYahoo=46, own=own)
    bad["pxSrc"]["fb"]["conf"] += 129                                             # 누가 실은 종목을 conf 에 더하면 칸이 맞지 않아요
    c, why = P.kk_counts(bad)
    assert c is None and "칸이 맞지 않아요" in why


def test_same_day_reuse_counts_as_confirmed_but_an_odd_record_is_not_used():
    d = fb_data("2026-11-20", 2700, noYahoo=46, rr=reuse(30, n=33))
    c, why = P.kk_counts(d)
    assert (c["conf"], c["reuse"], c["total"], c["lost"]) == (2700, 30, 2730, 0) and "다시 씀 30" in why
    for bad in ({"kk": -1, "lost": 0}, {"kk": 30}, {"kk": 30, "lost": None}, {"kk": 500, "lost": 0}, {"kk": True, "lost": 0}):
        d = fb_data("2026-11-20", 2700, noYahoo=46, rr=dict(reuse(30), **bad))
        if "lost" not in bad:
            d["pxSrc"]["own"]["reuse"].pop("lost")
        assert P.kk_counts(d)[0] is None, bad


@pytest.mark.parametrize("v", [True, -1, 2.5, "2740", None])
def test_counts_must_be_plain_non_negative_integers(v):
    d = fb_data("2026-11-20", 2740)
    d["pxSrc"]["fb"]["conf"] = v
    assert P.kk_counts(d)[0] is None


# ── 3. 같은 날 다시 발행 ─────────────────────────────────────
def pub(px="2026-11-20", us=None, kr=(), own=(), others=(), conf=2740, **kw):
    """발행 파일 모양: 그 날짜 종가 국내 (kr) · 마지막 확인 종가 국내 (own · pxd) · 미국 (others)."""
    stocks = ([{"t": c, "cls": "kr", "price": 1000.0} for c in kr] + [{"t": c, "cls": "kr", "price": 900.0, "pxd": "2026-11-19"} for c in own]
              + [{"t": c, "cls": "us", "price": 10.0} for c in others])
    return fb_data(px, conf, us=us, stocks=stocks, **kw)


KR5, US2 = ["100010", "100020", "100030", "100040", "100050"], ["AAPL", "MSFT"]


def test_same_day_publishes_only_with_more_date_priced_korean_stocks_and_nothing_lost():
    """#161 리뷰 2: 더 나음 = 발행 파일의 그 날짜 종가 국내 종목이 더 많음 (validate_data.kr_px_count) · 지난 발행본의 종목을 하나도 잃지 않음."""
    prev = pub(kr=KR5, own=["100060"], others=US2)
    d = P.same_day_decision(FB, FB, pub(kr=KR5 + ["100060"], others=US2), prev)        # 마지막 확인 종가였던 종목이 그 날짜 종가로
    assert d.hold is False and d.kind == "publish" and "5 → 6 (+1)" in d.why
    d = P.same_day_decision(FB, FB, pub(kr=KR5, own=["100060"], others=US2), prev)       # 같음
    assert d.hold is True and d.kind == "same" and d.loud is False and "더 많지 않아" in d.why
    # 발행 파일에 없는 종목의 확인은 더 나음이 아니에요 (발행 파일의 수만 세요)
    d = P.same_day_decision(FB, FB, pub(kr=KR5, own=["100060"], others=US2, conf=2760, noYahoo=1, diff=10), prev)
    assert d.kind == "same"


@pytest.mark.parametrize("cur,what", [
    (dict(kr=KR5[:4] + ["100060", "100070"], others=US2), "그 날짜 종가 국내 1"),                 # 그 날짜 종가 종목이 빠짐 (수는 늘어도)
    (dict(kr=KR5[:4] + ["100060", "100070"], own=["100050"], others=US2), "그 날짜 종가 국내 1"),  # 그 날짜 종가 → 마지막 확인 종가
    (dict(kr=KR5 + ["100070"], others=US2), "마지막 확인 종가 국내 1"),                          # 마지막 확인 종가 종목이 빠짐 (전부 빼는 길 포함)
    (dict(kr=KR5 + ["100060"], others=["AAPL"]), "미국 등 1"),                                   # 미국 종목이 빠짐
])
def test_a_same_day_republish_never_loses_a_stock(cur, what):
    prev = pub(kr=KR5, own=["100060"], others=US2)
    d = P.same_day_decision(FB, FB, pub(**cur), prev)
    assert d.hold is True and d.kind == "loss" and d.loud is True and what in d.why


def test_a_newer_us_date_publishes_without_more_korean_stocks_but_never_with_a_loss():
    prev = pub(kr=KR5, others=US2, us="2026-11-19")
    d = P.same_day_decision(FB, FB, pub(kr=KR5, others=US2, us="2026-11-20"), prev)
    assert d.hold is False and "미국 기준일 2026-11-19 → 2026-11-20" in d.why
    d = P.same_day_decision(FB, FB, pub(kr=KR5[:4], others=US2, us="2026-11-20"), prev)    # 한국을 잃으면 미국이 새로워도 발행 안 함
    assert d.hold is True and d.kind == "loss"


def test_dates_never_go_back():
    """#161 리뷰 1: 08:17 실행이 10:15 쯤 시작해 야후가 비는 틈에 걸리면 미국 기준일이 하루 앞으로 가요 (한국은 그대로) — 발행하지 않아요 (크게)."""
    now = kst(2026, 11, 21, 10, 15)
    prev = pub(kr=KR5, others=US2, us="2026-11-20")
    d, lines = P.evaluate(pub(kr=KR5 + ["100060"], others=US2, us="2026-11-19"), "data.json", prev, "git", now)
    assert d.hold is True and d.kind == "back" and d.loud is True and "미국 기준일 2026-11-19 < 발행본 2026-11-20" in d.why
    d, _ = P.evaluate(pub(px="2026-11-19", kr=KR5, others=US2, us="2026-11-20"), "data.json", prev, "git", now)
    assert d.kind == "back" and "한국 기준일 2026-11-19 < 발행본 2026-11-20" in d.why
    d, _ = P.evaluate(listing_data("2026-11-19", us="2026-11-20"), "data.json", prev, "git", now)    # 1차 출처 날도 같아요
    assert d.kind == "back"
    assert P.dates_back(prev, prev) is None and P.dates_back({"pxDate": None}, prev) is None


def test_same_day_mode_changes():
    assert P.same_day_decision(LISTING, LISTING, listing_data("2026-11-20"), listing_data("2026-11-20")).hold is False   # 예전 그대로
    d = P.same_day_decision(FB, LISTING, pub(kr=KR5), listing_data("2026-11-20"))
    assert d.hold is True and "2차 출처로 바꿔 발행하지 않아요" in d.why
    # KRX 최종본이 생긴 날 (오늘 1차 출처 · 지난 발행본 2차 출처): 잃지 않으면 발행
    lst = listing_data("2026-11-20")
    lst["stocks"] = [{"t": c, "cls": "kr", "price": 1000.0} for c in KR5 + ["100060"]]
    assert P.same_day_decision(LISTING, FB, lst, pub(kr=KR5, own=["100060"])).hold is False


def test_evaluate_runs_dates_then_the_floor_then_the_same_day_rule():
    now = kst(2026, 11, 21, 10, 53)
    prev = pub(kr=KR5, own=["100060"], others=US2, conf=2716, noYahoo=30)
    d, lines = P.evaluate(pub(kr=KR5 + ["100060"], others=US2, conf=2720, noYahoo=26), "data.json", prev, "git HEAD:data.json", now)
    assert d.hold is False and any("직전 발행본 (같은 한국 기준일)" in ln and "5 → 이 실행 6" in ln for ln in lines)
    d, _ = P.evaluate(pub(kr=KR5 + ["100060"], others=US2, conf=2600, noYahoo=146), "data.json", prev, "git", now)
    assert d.kind == "floor"                                                       # 같은 날이어도 바닥이 먼저
    assert P.evaluate(pub(px="2026-11-21", kr=KR5, others=US2, us="2026-11-21"), "data.json", prev, "git", now)[0].hold is False   # 새 날
    d, lines = P.evaluate(pub(kr=KR5, others=US2), "data.json", None, "git show HEAD:data.json → 종료 코드 128", now)
    assert d.hold is False and d.loud is True and d.kind == "unknown" and any(ln.startswith("!! 직전 발행본:") for ln in lines)
    # 오늘 확인 비율을 셀 수 없으면 (기록이 맞지 않음) 바닥은 보지 않지만 같은 날 규칙은 그대로 봐요 (#161 리뷰 3차 B-S4 · rev161b/repro.py A):
    # 잃는 것이 있으면 보류, 없고 더 나으면 크게 남기고 발행
    bad = pub(kr=KR5, conf=2700, noYahoo=46)
    bad["pxSrc"]["fb"]["conf"] += 5
    d, lines = P.evaluate(bad, "data.json", prev, "git", now)
    assert d.hold is True and d.kind == "loss" and lines[1].startswith("!! 오늘:")
    better = pub(kr=KR5 + ["100060"], others=US2, conf=2700, noYahoo=46)
    better["pxSrc"]["fb"]["conf"] += 5
    d, lines = P.evaluate(better, "data.json", prev, "git", now)
    assert d.hold is False and d.loud is True and d.kind == "unknown" and "같은 날 규칙:" in d.why and lines[1].startswith("!! 오늘:")
    d, _ = P.evaluate(bad, "data.json", pub(px="2026-11-19", kr=KR5, us="2026-11-19"), "git", now)      # 새 날: 예전처럼 보류 없이 (크게)
    assert d.hold is False and d.loud is True and d.kind == "unknown"
    assert P.evaluate(None, "data.json 없음", prev, "git", now)[0].hold is False


def test_the_review_repros():
    """리뷰의 재현 (scratchpad revHA s1 · s2 · revHB us_back) 과 같은 모양: 미국 119 빠짐 · 국내 150 빠짐 (네이버 시계열 실패) · 미국 기준일 하루 앞."""
    us = [f"U{i:04d}" for i in range(800)]
    krs = [f"{200000 + i}" for i in range(2474)]
    prev = pub(kr=krs, others=us, conf=2743, noYahoo=6, diff=22)
    cur = pub(kr=krs, others=us[119:], conf=2746, noYahoo=3, diff=22)
    assert P.evaluate(cur, "cur", prev, "prev", kst(2026, 11, 20, 10, 53))[0].kind == "loss"
    cur = pub(kr=krs[:100] + krs[250:], others=us, conf=2746, noYahoo=3, diff=22)
    d = P.evaluate(cur, "cur", prev, "prev", kst(2026, 11, 20, 10, 53))[0]
    assert d.kind == "loss" and "그 날짜 종가 국내 150" in d.why
    cur = pub(kr=krs, others=us, conf=2743, noYahoo=6, diff=22, us="2026-11-19")
    assert P.evaluate(cur, "cur", prev, "prev", kst(2026, 11, 20, 10, 15))[0].kind == "back"


# ── 4. main: 로그 · 요약 · 출력 · 알림 ────────────────────────
def run_main(tmp_path, monkeypatch, cur, prev, now, argv=(), dry=False, actions=False):
    out, summ = tmp_path / "out.txt", tmp_path / "summary.md"
    for p in (out, summ):
        if p.exists():
            p.unlink()
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summ))
    monkeypatch.setenv("DRY_RUN", "true" if dry else "")
    if actions:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    else:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    seen = []

    def prev_reader(ref):
        seen.append(ref)
        return (prev, f"git {ref}:data.json") if prev is not None else (None, f"git show {ref}:data.json → 종료 코드 128")

    def live_reader():                       # 사이트의 발행본 (data 브랜치) — 이 시험에서는 main HEAD 와 같아요 (지난 발행이 다 올랐어요)
        return (prev, "data 브랜치의 data.json") if prev is not None else (None, "data 브랜치의 data.json 을 받지 못했어요")
    hold = P.main(list(argv), now_fn=lambda: now, cur_reader=lambda p: (cur, p), prev_reader=prev_reader, live_reader=live_reader)
    return hold, out.read_text(), summ.read_text(), seen


def test_main_on_a_floor_hold_logs_the_numbers_and_warns(tmp_path, monkeypatch, capsys):
    hold, out, summ, seen = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526, noYahoo=220), fb_data("2026-11-19", 2740),
                                     kst(2026, 11, 21, 6, 41), actions=True)
    log = capsys.readouterr().out
    assert hold is True and seen == ["HEAD"] and out.splitlines()[-1] == "hold=true"
    loud = next(ln for ln in log.splitlines() if ln.startswith("!! [보류]"))
    for part in ("2,526", "2,771", "91.16%", "바닥 97%", "2,688"):
        assert part in loud, part
    assert "::warning title=발행 보류 (2차 출처 확인 비율 바닥 아래)::" in log
    assert "보류 — 확인 비율이 바닥 아래라 발행하지 않아요" in summ and "already_published.py" in summ


def test_main_same_day_not_better_leaves_a_notice_not_a_warning(tmp_path, monkeypatch, capsys):
    prev = fb_data("2026-11-20", 2740)
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2740, rr=reuse(0)), prev, kst(2026, 11, 21, 10, 53), actions=True)
    log = capsys.readouterr().out
    assert hold is True and out.splitlines()[-1] == "hold=true"
    assert "!! [같은 날 · 발행 안 함]" in log and "::notice title=같은 날 다시 발행 안 함 (더 낫지 않음)::" in log and "::warning" not in log
    assert "발행 안 함 — 같은 날 지난 발행본보다 낫지 않아요" in summ


def test_main_publishes_new_days_and_normal_days_quietly(tmp_path, monkeypatch, capsys):
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2740), fb_data("2026-11-19", 2740), kst(2026, 11, 21, 6, 41),
                                  actions=True)
    assert hold is False and out.splitlines()[-1] == "hold=false" and "발행 (보류 아님)" in summ
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, listing_data("2026-11-20"), fb_data("2026-11-19", 2740), kst(2026, 11, 21, 3, 47),
                                  actions=True)
    assert hold is False and "2차 출처 날이 아니에요" in summ
    assert "::" not in capsys.readouterr().out                                    # 알림 없음


def test_dry_runs_and_sample_runs_report_the_decision(tmp_path, monkeypatch, capsys):
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526, noYahoo=220), fb_data("2026-11-19", 2740),
                                  kst(2026, 11, 21, 6, 41), dry=True)
    assert hold is True and out.splitlines()[-1] == "hold=true" and "시험 실행" in summ and "표본" not in summ
    assert "시험 실행: 어차피 발행하지 않아요" in capsys.readouterr().out
    monkeypatch.setenv("SAMPLE_KR", "50")
    _, _, summ, _ = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2526, noYahoo=220), fb_data("2026-11-19", 2740),
                             kst(2026, 11, 21, 6, 41), dry=True)
    assert "표본 실행(sample)" in summ and "뜻이 없어요" in summ


def test_bootstrap_and_a_missing_compare_commit_look_at_the_floor_only(tmp_path, monkeypatch, capsys):
    same = fb_data("2026-11-20", 2740)
    for argv, word in ((["--bootstrap"], "bootstrap"), (["--no-prev"], "받지 못했어요")):
        hold, out, summ, seen = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2716, noYahoo=30), same, kst(2026, 11, 21, 10, 53), argv=argv)
        assert hold is False and seen == [] and out.splitlines()[-1] == "hold=false" and word in summ
    hold, out, _, seen = run_main(tmp_path, monkeypatch, fb_data("2026-11-20", 2716, noYahoo=30, rr=reuse(0)), same, kst(2026, 11, 21, 10, 53),
                                  argv=["--prev-ref", "FETCH_HEAD"])
    assert hold is True and seen == ["FETCH_HEAD"]                                # 같은 날 · 더 낫지 않음


def test_main_never_holds_when_it_breaks_on_the_first_run_but_stops_a_same_day_rerun(tmp_path, monkeypatch, capsys):
    """판단이 오류로 멈추면: 그날의 첫 실행 (새 한국 기준일) 은 예전처럼 보류하지 않아요. 같은 날 다시 하는 실행 (또는 같은 날인지 모름) 은 발행하지 않고
    kind stop (#161 리뷰 3차 B-S5) — 감시에 중립이 아니고 (neutral=false), 스크립트는 종료 코드 3 으로 끝나 워크플로 단계가 실패해요."""
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def boom(*a, **k):
        raise RuntimeError("판단 고장")
    monkeypatch.setattr(P, "evaluate", boom)
    yday, today = fb_data("2026-11-19", 2740), fb_data("2026-11-20", 2740)

    def run(cur, live, head=None, cur_reader=None):
        out.write_text("")
        return P.decide([], now_fn=lambda: kst(2026, 11, 21, 6, 41), cur_reader=cur_reader or (lambda p: (cur, p)),
                        prev_reader=lambda ref: (head if head is not None else live, f"git {ref}:data.json"),
                        live_reader=lambda: (live, "data 브랜치"))
    d = run(today, yday)                                                           # 그날 첫 실행
    log = capsys.readouterr().out
    assert d.hold is False and d.kind == "error" and out.read_text().splitlines()[-1] == "hold=false"
    assert "!! 발행 판단이 오류로 멈췄어요" in log and log.count("::warning title=발행 판단 확인 못 함 (보류 없이 판단)::") == 1
    d = run(today, today)                                                          # 같은 날 다시 하는 실행
    log = capsys.readouterr().out
    lines = out.read_text().splitlines()
    assert d.hold is True and d.kind == "stop" and lines[-1] == "hold=true" and "neutral=false" in lines and "kind=stop" in lines
    assert "!! [멈춤]" in log and "::error title=발행 판단 못 함 (같은 날 다시 하는 실행 · 발행하지 않고 실패로 끝내요)::" in log
    assert "stop" not in P.NEUTRAL

    def unreadable(path):
        raise RuntimeError("읽기 실패")
    d = run(None, today, cur_reader=unreadable)                                    # 오늘 파일도 못 읽어 같은 날인지 몰라요
    assert d.hold is True and d.kind == "stop"
    monkeypatch.undo()
    # 판단이 멈춘 것이 아니라 오늘 파일만 없으면: 예전처럼 보류 없이 (관문이 그 파일을 봐요)
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    hold, text, _, _ = run_main(tmp_path, monkeypatch, None, fb_data("2026-11-19", 2740), kst(2026, 11, 21, 6, 41))
    assert hold is False and text.splitlines()[-1] == "hold=false"


def test_read_prev_reads_the_same_file_the_gate_compares_with():
    calls = []

    class R:
        def __init__(self, rc, out):
            self.returncode, self.stdout = rc, out

    def fake(cmd, **kw):
        calls.append(cmd)
        return R(0, json.dumps(fb_data("2026-11-19", 2740)).encode())
    data, note = P.read_prev("HEAD", run=fake)
    assert calls == [["git", "show", "HEAD:data.json"]] and P.kk_counts(data)[0]["total"] == 2740 and note == "git HEAD:data.json"
    assert P.read_prev("HEAD", run=lambda cmd, **kw: R(128, b""))[0] is None
    assert P.read_prev("HEAD", run=lambda cmd, **kw: R(0, b"{not json"))[0] is None
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert 'ap.add_argument("--prev-ref", default="HEAD"' in src and V.PX_SRC_FB == FB


# ── 5. 파이프라인: 같은 날 지난 발행본의 확인 종가 다시 쓰기 ──────────
def kr(t, price=5000.0, **kw):
    s = {"t": t, "nk": "종목" + t, "ne": "종목" + t, "cls": "kr", "s": "etc", "price": price, "vol": 30.0, "beta": 1.0, "al": 1.0, "betaSE": 0.05,
         "betaN": 700, "cap": 0.05, "val": 3.0, "val20": 2.5, "lo": 4000.0, "hi": 6000.0, "etf": False, "shr": 10000000, "r1": 1.0, "r3": 2.0,
         "r36": 3.0, "dk": "업종 · KOSDAQ 상장 · 시가총액 500억원", "sh": 0.3, "mdd": -40.0, "hit": 50, "mom": 10.0, "d1": 0.5, "per": 25.0, "pbr": 1.2}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def test_same_day_reuse_keeps_the_earlier_confirmed_close_and_names_every_loss():
    px = dt.date(2026, 11, 20)
    prev = {"pxDate": "2026-11-20", "publishedAt": "2026-11-21T06:40:52+09:00", "krSeries": {"v": 1, "jump": [["400050", "2026-05-08", 90.0, "halt"]]},
            "stocks": [kr("400010", 7300.0, cap=0.9, d1=-1.2), kr("400020", 100.0, cap=0.1, noTrade=True, d1=None, d1Why="noTrade", ntD1=0.0),
                       kr("400030"), kr("400040"), kr("400050", pxBad=1, pxBadF=1), kr("400060", pxBad=1),
                       kr("400070", pxd="2026-11-19", d1=None), kr("400080")]}
    unconf = {c: ("", "conf") for c in ("400010", "400020", "400030", "400050", "400060", "400070")}
    unconf["400099"] = ("코넥스", "mkt")
    src = {"fb": {"diffT": ["400030"]}}
    reused, jumps, lost, rec = F.kr_same_day_reuse(prev, unconf, {"400080"}, px, src)
    by = {r["t"]: r for r in reused}
    assert sorted(by) == ["400010", "400020", "400050"]
    assert by["400010"]["price"] == 7300.0 and by["400010"]["d1"] == -1.2 and "pxd" not in by["400010"]       # 그 날짜 종가 · d1 그대로
    assert by["400020"]["noTrade"] is True and by["400020"]["d1Why"] == "noTrade" and "d1" not in by["400020"]
    assert not {"per", "pbr"} & set(by["400010"])                                                             # 재무 · 점수는 오늘 다시
    assert jumps == {"400050": [["400050", "2026-05-08", 90.0, "halt"]]}
    # 잃은 종목: 지금 두 출처가 다름 · 그날 목록에 없음 · 과거 주가 기록 오류 표시인데 지난 움직임이 없음 (400070 은 지난 발행본도 마지막 확인 종가라
    # 다시 쓰지 않아요 — 마지막 확인 종가 단계가 같은 pxd 로 옮겨요 · 400080 은 이 실행이 확인했어요)
    assert lost == {"400030": "clash", "400040": "gone", "400060": "jump"}
    assert (rec["earlier"], rec["n"], rec["kk"], rec["lost"]) == (7, 3, 3, 3) and rec["from"].startswith("2026-11-21T06:40")
    assert any("400030" in x and "지금 두 출처가 서로 다름" in x for x in rec["lostEx"])
    # 다른 기준일이면 아무것도 하지 않아요 (같은 날 다시 도는 실행이 아니에요)
    assert F.kr_same_day_reuse(dict(prev, pxDate="2026-11-19"), unconf, set(), px, src) == ([], {}, {}, None)
    json.dumps(rec, allow_nan=False)


def test_reuse_never_exceeds_this_runs_confirmed_count():
    """관문: 2차 출처 날 '두 출처 확인 수 ≥ 발행한 그 날짜 종가 종목 수' (validate_data.px_alt_confirms) — 그 줄을 그대로 두고, 다시 쓰는 수를 맞춰요."""
    px = dt.date(2026, 11, 20)
    prev = {"pxDate": "2026-11-20", "stocks": [kr("500010", cap=5.0), kr("500020", cap=9.0), kr("500030", cap=1.0)]}
    unconf = {c: ("", "conf") for c in ("500010", "500020", "500030")}
    reused, _, lost, rec = F.kr_same_day_reuse(prev, unconf, set(), px, {"fb": {}}, room=2)
    assert [r["t"] for r in reused] == ["500010", "500020"] and lost == {"500030": "room"} and rec["lost"] == 1     # 시가총액 큰 것부터
    assert F.kr_same_day_reuse(prev, unconf, set(), px, {"fb": {}}, room=0)[3]["n"] == 0


def test_the_step_reuses_on_the_real_fetch_korea_shapes(capsys):
    """kr_own_close_step 을 진짜 모양으로 (test_kr_own_close.real_second_source: 11-16 · STX 다음 ≠ 야후 · 본시스템즈 코넥스): 지난 발행본이 같은
    기준일에 두 종목을 그 날짜 종가로 실었어요 → 코넥스는 다시 쓰고, STX 는 지금 두 출처가 달라 잃은 종목 (발행하지 않아요)."""
    import test_kr_own_close as T
    px, lst, src, full = T.real_second_source()
    konex, stx = "496320", "011810"
    assert stx in src["fb"]["diffT"]                                              # fetch_data 가 직접 적은 다른 종목 목록
    conf = set(lst["Code"].astype(str).str.strip())
    kept_out = sorted(conf)[:2]                                                   # 시가총액 상위로 자른 것처럼 (확인됐지만 발행하지 않은 종목 2)
    out = [{"t": c, "cls": "kr", "price": 1.0} for c in sorted(conf) if c not in kept_out]
    prev = {"pxDate": px.isoformat(), "publishedAt": "2026-11-17T06:40:00+09:00", "krSeries": {"v": 1, "jump": []},
            "stocks": [kr(c) for c in sorted(conf) if c not in kept_out]
            + [kr(konex, 1176000.0, dk="업종 · 주요제품: 기계 · KONEX 상장 · 시가총액 100억원"), kr(stx, 18360.0)]}
    krs, prod = {"jump": [], "hidden": []}, {}
    days = list(pd.to_datetime(["2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17"]))
    n = F.kr_own_close_step(prev, full, conf, src, px, days, out, krs, prod)
    assert n == 0                                                                 # 마지막 확인 종가로 실은 종목 0 (같은 날이라 옮기지 않아요)
    rr = src["own"]["reuse"]
    # 코넥스는 기록으로 다시 쓰지 않아요 (그날 파일의 코넥스 = 이 실행이 두 출처로 확인한 것 · 관문의 코넥스 줄과 같게 — 보관본 길로만) · STX 는 지금 두 출처가 달라요
    assert (rr["n"], rr["kk"], rr["lost"]) == (0, 0, 2) and rr["codes"] == []
    assert any(konex in x and "코넥스" in x for x in rr["lostEx"]) and any(stx in x and "두 출처가 서로 다름" in x for x in rr["lostEx"])
    assert not [r for r in out if r["t"] in (konex, stx)]
    assert src["own"]["unconf"] == 2                                              # 이 실행이 확인 못 한 수는 그대로 (관문의 코넥스 비교와 같게)
    log = capsys.readouterr().out
    assert "!! 같은 기준일을 다시 도는 실행" in log and "잃은 종목 2" in log
    data = json.loads(json.dumps({"pxDate": px.isoformat(), "usPxDate": "2026-11-16", "pxSrc": F.px_src_final(src, out), "stocks": out}))
    assert P.kk_counts(data)[0]["lost"] == 2
    d = P.same_day_decision(FB, FB, data, prev_d := dict(prev, usPxDate="2026-11-16", pxSrc={"px": FB, "date": px.isoformat()}))
    assert d.hold is True and d.kind == "loss" and "그 날짜 종가 국내 2" in d.why and prev_d


def test_contract_with_the_pipelines_own_second_source_record():
    """fetch_data 의 진짜 길로 pxSrc 를 만들어 그대로 읽어요: kr_fallback_days (kr_fb_confirm) → kr_second_source (px_src_counts) → px_src_final."""
    import test_kr_two_source as T2
    uni = T2.listing("2026-11-18_1452")
    D16, D18 = dt.date(2026, 11, 16), dt.date(2026, 11, 18)

    def fill(y, cm, d, close_time):
        mc = set()
        for c, rows in T2.daum().items():
            if c in cm and d in rows:
                y.setdefault(c, {})[d] = rows[d]["tradePrice"]
                mc.add(c)
        return {"need": len(mc), "bar": 0, "meta": len(mc), "none": 0, "fail": 0, "metaCodes": mc}
    seen = {}

    def fallback(days, universe_of, now, special):
        out, notes = F.kr_fallback_days(days, universe_of, now, special, fetch_daum=lambda codes, n: (T2.daum(), []),
                                        fetch_yahoo=lambda cm, s, e: ({c: {k: v for k, v in d.items() if k != D18} for c, d in T2.yahoo().items()}, 0),
                                        fill_day=fill)
        seen.update(out)
        return out, notes
    px, lst, _, src, _, _ = F.kr_second_source(D16, T2.listing("2026-11-16_2211"), [D18], dt.datetime(2026, 11, 19, 2, 15, tzinfo=F.KST), {},
                                               lambda d: (uni, "시험"), fallback=fallback)
    assert px == D18 and src["px"] == FB
    st = seen[D18][1]
    stocks = [{"t": str(c), "cls": "kr"} for c in lst["Code"]]
    data = json.loads(json.dumps({"pxDate": px.isoformat(), "pxSrc": F.px_src_final(src, stocks), "stocks": stocks}, allow_nan=False))
    c, why = P.kk_counts(data)
    assert c["conf"] == c["total"] == st["conf"] == len(lst) > 0, why
    assert c["listing"] == st["n"] - len(st["mkt"]) and st["mkt"]                 # 픽스처의 코넥스 1종목은 mkt 에
    assert data["pxSrc"]["fb"]["diffT"] == sorted(x for x, *_ in st["diff"])


def test_contract_with_the_pipelines_own_konex_record():
    """#158 의 코넥스 단계까지 진짜 길로 (tests/test_konex_two_source.knx_fakes): fb.knx.kept 를 fetch_data 가 직접 만들고, 돌아오는 수는 코스피 · 코스닥만."""
    import functools
    import test_konex_two_source as TK
    D13, D16 = dt.date(2026, 11, 13), dt.date(2026, 11, 16)
    prim = TK.pd.concat([TK.kk_listing("2026-11-13_2158"), TK.knx_listing("2026-11-13_final")], ignore_index=True)
    base, _ = TK.run_fb(knx=None)
    kk_conf = base[D16][1]["conf"]
    px, lst, _, src, _, _ = F.kr_second_source(D13, prim, [D16], TK.NOW, {}, None,
                                               fallback=functools.partial(TK.run_fb_partial, knx=TK.knx_fakes()))
    kept = src["fb"]["knx"]["kept"]
    assert px == D16 and kept > 0 and src["fb"]["conf"] == kk_conf + kept
    assert isinstance(src["fb"]["knx"]["diffT"], list) and set(src["fb"]["knx"]["diffT"]) <= set(src["fb"]["knx"]["left"])
    stocks = [{"t": str(c), "cls": "kr"} for c in lst["Code"]]
    data = json.loads(json.dumps({"pxDate": px.isoformat(), "pxSrc": F.px_src_final(src, stocks), "stocks": stocks}, allow_nan=False))
    c, why = P.kk_counts(data)
    assert c["conf"] == kk_conf and c["kept"] == kept and f"코넥스 {kept:,} 는 빼고" in why


# ── 6. already_published: 확인 못 한 종가가 남은 날은 뒤의 실행도 끝까지 ──────
def weekdays(start, end):
    d, out = start, []
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


CAL = {"kr": weekdays(dt.date(2026, 10, 1), dt.date(2026, 11, 20)), "us": weekdays(dt.date(2026, 10, 1), dt.date(2026, 11, 20)),
       "usToday": None, "krSources": 2}


def test_open_closes():
    own = {"v": 1, "n": 129, "codes": [], "unconf": 160}
    assert A.open_closes(fb_data("2026-11-20", 2740, own=own)) == {"kr": 160, "us": 0}
    assert A.open_closes(fb_data("2026-11-20", 2740, own=own, rr=reuse(150, n=160))) == {"kr": 0, "us": 0}     # 모두 다시 씀
    assert A.open_closes(fb_data("2026-11-20", 2740)) == {"kr": 138, "us": 0}     # own 이 없으면 fb 로 (목록 2,878 − 확인 2,740)
    assert A.open_closes(listing_data("2026-11-20")) == {"kr": 0, "us": 0}        # 1차 출처 날
    assert A.open_closes({"pxDate": "2026-11-12", "stocks": []}) == {"kr": 0, "us": 0}   # pxSrc 가 생기기 전 파일
    odd = fb_data("2026-11-20", 2740)
    odd["pxSrc"]["fb"] = "x"
    assert A.open_closes(odd) == {"kr": 1, "us": 0}                               # 모르면 다시 돌아요
    assert A.open_closes(None) == {"kr": 0, "us": 0}


def test_later_scheduled_runs_keep_running_while_the_day_has_open_closes():
    now = kst(2026, 11, 21, 10, 53)
    own = {"v": 1, "n": 25, "codes": [], "unconf": 31}
    skip, why = A.decide(fb_data("2026-11-20", 2740, own=own), now, CAL)
    assert skip is False and "확인 못 한 종가가 남아 있어요 (국내 31)" in why and "#161" in why
    skip, why = A.decide(fb_data("2026-11-20", 2740, own=dict(own, unconf=0)), now, CAL)
    assert skip is True and "이미 다 들어와" in why                               # 다 찬 날은 예전처럼 건너뛰어요
    assert A.decide(listing_data("2026-11-20"), now, CAL)[0] is True              # 1차 출처 날 그대로
    assert A.decide(fb_data("2026-11-19", 2740, own=own), now, CAL)[0] is False   # 날짜가 늦으면 예전처럼 실행


def test_a_held_run_leaves_the_data_branch_as_it_was_so_the_next_start_runs():
    prev, cur = fb_data("2026-11-19", 2740), fb_data("2026-11-20", 2526, noYahoo=220)
    assert P.evaluate(cur, "data.json", prev, "git HEAD:data.json", kst(2026, 11, 21, 6, 41))[0].hold is True
    for hh, mm in ((6, 43), (8, 17), (10, 53)):
        skip, why = A.decide(prev, kst(2026, 11, 21, hh, mm), CAL)
        assert skip is False and "아직이에요" in why


# ── 7. 관문: 같은 기준일 다시 발행 ─────────────────────────────
def test_gate_rows_comparing_with_the_previous_publish_pass_a_same_day_republish():
    """같은 pxDate 를 더 많이 확인해 다시 발행: '직전 발행본과 비교하는 줄' (pxDate 가 뒤로 가지 않음 · 국내 종목 수 변화 · 큰 가격 변동 비율) 이
    줄을 바꾸지 않고 통과해요. 지난 발행본 = 같은 날 · 같은 가격 · 5% 적은 종목 (그때 확인 못 한 종목)."""
    import test_kr_two_source as T2
    cur, _, old, alt = T2.fb_pair()
    earlier = copy.deepcopy(cur)
    codes = [s["t"] for s in V.kr_stocks(earlier["data"]) if s["t"] not in V.MUST]
    gone = set(codes[:max(1, len(codes) // 20)])
    earlier["data"]["stocks"] = [s for s in earlier["data"]["stocks"] if s["t"] not in gone]
    earlier["data"]["pxSrc"]["fb"]["conf"] -= len(gone)
    assert earlier["data"]["pxDate"] == cur["data"]["pxDate"]
    rep = V.run_checks(cur, earlier, old, T2.TODAY, mode="publish", count_between=lambda a, b: 0, sessions=T2.SESSIONS, now=T2.NOW,
                       hilo=T2.hilo_of(cur, V.MUST), alt=alt)                    # 같은 날 사이 거래일 0 (관문이 max(1, 0) 으로)
    rows = {r[0]: r for r in rep.rows}
    for name in ("pxDate 가 뒤로 가지 않음", "국내 종목 수 변화", "큰 가격 변동 비율"):
        assert rows[name][3] == "PASS", rows[name]
    assert not rep.failed, rep.table()


# ── 8. 워크플로 ──────────────────────────────────────────────
def update_steps():
    with open(WF, encoding="utf-8") as f:
        return yaml.safe_load(f)["jobs"]["update"]["steps"]


def names(st):
    return [s.get("name") or s.get("uses") for s in st]


def test_the_decision_is_made_once_before_the_gate_and_runs_on_every_run():
    st = update_steps()
    n = names(st)
    i_fetch, i_save, i_hold, i_gate = n.index("데이터 수집"), n.index("DART 캐시 저장"), n.index(HOLD_STEP), n.index(GATE)
    i_main, i_data = n.index(PUBLISH[0]), n.index(PUBLISH[1])
    assert i_fetch < i_save < i_hold < i_gate < i_main < i_data == len(st) - 1
    hold = st[i_hold]
    assert hold["id"] == "hold"
    for k in ("if", "env", "continue-on-error", "timeout-minutes"):
        assert k not in hold, k
    run = hold["run"]
    assert run.count("python tools/publish_hold.py") == 1 and "|| true" not in run
    for bad in ("git push", "git commit", "push_data_branch", "GITHUB_TOKEN", "secrets.", "github.token"):
        assert bad not in json.dumps(hold, ensure_ascii=False), bad
    whole = json.dumps(st, ensure_ascii=False)
    assert whole.count("publish_hold.py") == 1
    assert [s.get("name") for s in st if "steps.hold" in json.dumps(s, ensure_ascii=False)] == [W.HOLD_MARK, *PUBLISH]
    mark = st[n.index(W.HOLD_MARK)]
    assert n.index(W.HOLD_MARK) == i_hold + 1 and mark["if"] == "steps.hold.outputs.neutral == 'true'"
    assert set(mark) == {"name", "if", "run"} and mark["run"].startswith("echo ")       # 표시만 해요 (토큰 · 쓰기 없음)


def test_a_hold_skips_exactly_the_commit_and_the_data_branch_push():
    st = update_steps()
    by = dict(zip(names(st), st))
    for name in PUBLISH:
        assert by[name]["if"] == IF_PUBLISH, name
    writers = [s.get("name") for s in st if any(w in (s.get("run") or "") for w in ("git push", "git commit", "push_data_branch"))]
    assert writers == list(PUBLISH)

    def gh_if(dry_run, hold_out):
        return (not dry_run) and (hold_out or "") != "true"
    assert gh_if(False, "false") is True and gh_if(False, None) is True
    assert gh_if(False, "true") is False
    assert gh_if(True, "false") is False and gh_if(True, "true") is False


def fake_bin(tmp_path, py_body, git_ok=True):
    bin_ = tmp_path / "bin"
    bin_.mkdir(exist_ok=True)
    py = bin_ / "python"
    py.write_text("#!/bin/bash\n" f'echo "$*" >> "{tmp_path}/calls.txt"\n' + py_body)
    git = bin_ / "git"
    git.write_text("#!/bin/bash\n" f'echo "git $*" >> "{tmp_path}/calls.txt"\n' + ("exit 0\n" if git_ok else "exit 128\n"))
    for f in (py, git):
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return bin_


def run_hold_step(tmp_path, py_body, env=None, git_ok=True):
    run = next(s for s in update_steps() if s.get("name") == HOLD_STEP)["run"]
    bin_ = fake_bin(tmp_path, py_body, git_ok)
    out = tmp_path / "out.txt"
    out.write_text("")
    (tmp_path / "calls.txt").write_text("")
    e = {"PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "BOOTSTRAP": "", "PREV_REF": "", **(env or {})}
    r = subprocess.run(["bash", "-e", "-c", run], cwd=tmp_path, env=e, capture_output=True, text=True)
    return r, out.read_text().split(), (tmp_path / "calls.txt").read_text()


def test_hold_step_bash_passes_the_gate_inputs_and_fails_open(tmp_path):
    ok = 'echo "hold=true" >> "$GITHUB_OUTPUT"\n'
    r, out, calls = run_hold_step(tmp_path, ok)
    assert r.returncode == 0 and out == ["hold=true"] and calls.strip() == "tools/publish_hold.py"
    r, out, calls = run_hold_step(tmp_path, ok, {"BOOTSTRAP": "true"})
    assert r.returncode == 0 and calls.strip() == "tools/publish_hold.py --bootstrap"
    r, out, calls = run_hold_step(tmp_path, ok, {"PREV_REF": "abc123"})
    assert "git fetch --depth=1 origin abc123" in calls and "tools/publish_hold.py --prev-ref FETCH_HEAD" in calls
    r, out, calls = run_hold_step(tmp_path, ok, {"PREV_REF": "abc123"}, git_ok=False)
    assert r.returncode == 0 and "tools/publish_hold.py --no-prev" in calls and "받지 못했어요" in r.stdout
    r, out, calls = run_hold_step(tmp_path, "exit 1\n")
    assert r.returncode == 0 and out == ["hold=false"] and "!! 발행 판단이 오류로 멈췄어요" in r.stdout
    assert "::warning title=발행 판단 확인 못 함 (보류 없이 판단)::" in r.stdout


def test_hold_step_end_to_end_with_the_real_script_and_git(tmp_path):
    """단계의 bash 를 진짜 publish_hold.py · git 으로: 지난 발행본은 사이트의 발행본 = origin 의 data 브랜치 data.json (#161 리뷰 3차 B-M1 ·
    already_published.read_published 와 같은 길), 오늘 것은 작업 폴더의 data.json. main HEAD 는 같은 날인지 · 다 올랐는지 볼 때만."""
    repo, origin = tmp_path / "repo", tmp_path / "origin.git"
    repo.mkdir()
    genv = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}

    def git(*cmd, cwd=repo):
        return subprocess.run(["git", *cmd], cwd=cwd, env=genv, check=True, capture_output=True, text=True)
    morning = dict(pub(kr=KR5, own=["100060"], others=US2, conf=2716, noYahoo=30), publishedAt="2026-11-21T06:40:00+09:00")   # 06:40 발행본
    (repo / "data.json").write_text(json.dumps(morning))
    git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    for cmd in (["init", "-q"], ["add", "data.json"], ["commit", "-q", "-m", "prev"], ["remote", "add", "origin", str(origin)],
                ["push", "-q", "origin", "HEAD:refs/heads/main"], ["push", "-q", "origin", "HEAD:refs/heads/data"]):
        git(*cmd)
    run = next(s for s in update_steps() if s.get("name") == HOLD_STEP)["run"]
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    py = bin_ / "python"
    py.write_text(f'#!/bin/bash\n[ "$1" = "tools/publish_hold.py" ] || exit 9\nshift\n'
                  f'exec "{sys.executable}" "{os.path.join(ROOT, "tools", "publish_hold.py")}" "$@"\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)

    def step(cur):
        (repo / "data.json").write_text(json.dumps(cur))
        out = tmp_path / "out.txt"
        out.write_text("")
        e = {**genv, "PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "BOOTSTRAP": "", "PREV_REF": "", "DRY_RUN": ""}
        e.pop("GITHUB_ACTIONS", None)
        e.pop("GITHUB_STEP_SUMMARY", None)
        r = subprocess.run(["bash", "-e", "-c", run], cwd=repo, env=e, capture_output=True, text=True)
        return r, out.read_text().splitlines()
    cases = ((pub(kr=KR5 + ["100060"], others=US2, conf=2720, noYahoo=26), "hold=false", "publish"),   # 같은 날 · 더 나음 → 발행
             (pub(kr=KR5, own=["100060"], others=US2, conf=2716, noYahoo=30), "hold=true", "same"),     # 같은 날 · 같음 → 발행 안 함 (건강)
             (pub(kr=KR5, others=US2, conf=2720, noYahoo=26), "hold=true", "loss"),                     # 같은 날 · 마지막 확인 종가 종목을 잃음
             (pub(px="2026-11-21", us="2026-11-21", conf=2526, noYahoo=220), "hold=true", "floor"),     # 새 날 · 바닥 아래 → 보류
             (pub(px="2026-11-21", us="2026-11-21", kr=KR5, others=US2), "hold=false", "publish"))      # 새 날 · 바닥 위 → 발행
    for cur, want, kind in cases:
        r, lines = step(cur)
        assert r.returncode == 0, r.stderr
        assert lines[-1] == want and f"kind={kind}" in lines, (cur["pxDate"], r.stdout, r.stderr)
        assert ("neutral=true" in lines) is (kind in ("floor", "loss")), lines                # 표시 단계: 감시에 중립인 보류만
        assert "data 브랜치의 data.json (한국 2026-11-20" in r.stdout                           # 사이트의 발행본과 비교했어요
    # B-M1: 지난 발행의 'data 브랜치에 올리기' 가 실패해 main HEAD (10:53 발행본) 가 data 브랜치 (06:40) 보다 앞서요 — 같은 것을 다시 받은 실행은
    # '같은 날 · 더 낫지 않음' 으로 보류하지 않고 발행해 data 브랜치를 고쳐요 (예전: main HEAD 와 비교해 건강한 보류 → 경보가 닫히고 사이트는 뒤)
    noon = dict(pub(kr=KR5 + ["100060"], others=US2, conf=2720, noYahoo=26), publishedAt="2026-11-21T10:53:00+09:00")
    (repo / "data.json").write_text(json.dumps(noon))
    git("commit", "-q", "-am", "10:53 발행 (main 에만)")
    r, lines = step(morning)
    assert r.returncode == 0 and lines[-1] == "hold=false" and "kind=publish" in lines, (r.stdout, r.stderr)
    assert "지난 발행이 data 브랜치에 다 오르지 못했어요" in r.stdout
    # data 브랜치를 읽지 못했는데 main HEAD 와 같은 한국 기준일 → 판단할 수 없는 같은 날 실행: 발행하지 않고 단계가 실패해요 (빨간 실행)
    git("remote", "set-url", "origin", str(tmp_path / "없는 곳.git"))
    r, lines = step(noon)
    assert r.returncode != 0 and lines[-1] == "hold=true" and "kind=stop" in lines and "neutral=false" in lines, (r.stdout, r.stderr)
    assert "발행하지 않고 이 실행을 실패로 끝내요" in r.stdout
    # 같은 상황인데 새 날 (main HEAD 보다 새 한국 기준일): 예전처럼 바닥만 보고 보류 없이 (크게)
    r, lines = step(pub(px="2026-11-21", us="2026-11-21", kr=KR5, others=US2))
    assert r.returncode == 0 and lines[-1] == "hold=false", (r.stdout, r.stderr)
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, env=genv, capture_output=True, text=True).stdout
    assert len(log.strip().splitlines()) == 2                                     # 단계는 커밋하지 않아요


# ── 9. 발행하지 않은 실행은 발행이 아니에요: 배포 · 감시 ─────────────
def held_jobs(mark="success"):
    """매일 실행의 job 결과 모양: 발행 판단 → 표시 단계 (mark: success = 감시에 중립인 보류 · skipped = 같은 날 · 더 낫지 않음 · None = 표시 단계 전 실행)."""
    st = [{"name": HOLD_STEP, "conclusion": "success"}] + ([{"name": W.HOLD_MARK, "conclusion": mark}] if mark else [])
    st += [{"name": GATE, "conclusion": "success"}, {"name": PUBLISH[0], "conclusion": "skipped"}, {"name": PUBLISH[1], "conclusion": "skipped"}]
    return [{"name": "check", "conclusion": "success", "steps": [{"name": "x", "conclusion": "success"}]},
            {"name": "update", "conclusion": "success", "steps": st}]


HELD_JOBS = held_jobs("success")


def test_a_held_run_does_not_deploy(tmp_path):
    import test_workflows as TW
    rc, go, log = TW._decide(tmp_path, "workflow_run", "workflow", conclusion="success", pushed="skipped")
    assert (rc, go) == (0, "go=false") and "올리지 않았어요" in log


def test_a_held_run_raises_no_data_alarm(monkeypatch):
    import test_watchdog as TWD
    runs = [TWD.run(2, "success"), TWD.run(1, "success")]
    net = TWD.FakeNet(data_runs=runs, jobs={2: HELD_JOBS})
    assert W.decide(net, "workflow_run", W.DATA_NAME, 2)[0] is True
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 0 and net.issues == []
    rep = W.Report()
    W.check_runs(rep, TWD.FakeNet(data_runs=runs, jobs={2: HELD_JOBS}), W.DATA_WF, W.DATA_NAME)
    name, st, detail = rep.rows[-1][:3]
    assert st == "PASS" and "/runs/1" in detail and "발행하지 않은 실행 1번" in detail


def test_a_held_run_never_closes_a_real_alarm(monkeypatch):
    import test_watchdog as TWD
    alarm = {"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open"}
    net = TWD.FakeNet(data_runs=[TWD.run(2, "success"), TWD.run(1, "failure")], jobs={2: HELD_JOBS}, issues=[alarm])
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 1
    assert not [c for c in net.calls if c[0] == "PATCH"]
    c = TWD.posts(net, "/issues/9/comments")
    assert len(c) == 1 and "아직 문제가 있어요" in c[0][2]["body"]
    assert net.urls[-1].endswith("/fail")
    net = TWD.FakeNet(data_runs=[TWD.run(3, "success"), TWD.run(2, "success"), TWD.run(1, "success")], jobs={3: HELD_JOBS, 2: HELD_JOBS})
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 0 and net.issues == []


def test_only_a_held_run_is_neutral_and_an_api_hiccup_counts_the_run_as_before(capsys):
    import test_watchdog as TWD
    pushed = [{"name": "update", "conclusion": "success", "steps": [{"name": W.PUSH_STEP, "conclusion": "success"}]}]
    already = [{"name": "check", "conclusion": "success", "steps": []}, {"name": "update", "conclusion": "skipped", "steps": []}]
    net = TWD.FakeNet(jobs={1: HELD_JOBS, 2: pushed, 3: already})
    assert W.is_held_run(net, TWD.run(1, "success")) is True
    assert W.is_held_run(net, TWD.run(2, "success")) is False
    assert W.is_held_run(net, TWD.run(3, "success")) is False
    assert W.is_held_run(net, TWD.run(1, "failure")) is False

    class Down(TWD.FakeNet):
        def gh(self, method, path, body=None, ok=(200, 201, 204)):
            if "/jobs" in path:
                raise RuntimeError("API 막힘")
            return super().gh(method, path, body, ok)
    assert W.is_held_run(Down(jobs={1: HELD_JOBS}), TWD.run(1, "success")) is False
    assert "보류한 실행인지 몰라요" in capsys.readouterr().out


# ── 10. 같은 날 다시 도는 실행은 발행본이 확인한 종목을 다시 묻지 않아요 (출처 요청 줄이기) ──────────
def _fb_run(uni, day, cached=None, keep=None, asked=None, no_yahoo=(), answered=True):
    """test_kr_two_source 의 실제 응답 픽스처로 kr_fallback_days 를 돌려요. asked: 묻는 종목을 단계마다 적어요 {"daum", "yahoo", "fill"}.
    no_yahoo: 야후가 그날 종가를 주지 않는 종목 (확인 못 한 종목을 만들어요)."""
    import test_kr_two_source as T2
    asked = asked if asked is not None else {}

    def fetch_daum(codes, n):
        asked.setdefault("daum", []).extend(codes)
        return {c: v for c, v in T2.daum().items() if c in codes}, []

    def fetch_yahoo(cm, s, e):
        asked.setdefault("yahoo", []).extend(cm)
        out = F.YahooAnswers({c: {k: v for k, v in d.items() if k != day} for c, d in T2.yahoo().items() if c in cm and c not in no_yahoo})
        if answered:                                                              # 야후가 '자료 없음' 으로 답함 (아니면 받지 못함 — 오류 · 시간 초과)
            out.empty |= {c for c in no_yahoo if c in cm}
        return out, 0

    def fill(y, cm, d, close_time):
        asked.setdefault("fill", []).extend(cm)
        mc = set()
        for c, rows in T2.daum().items():
            if c in cm and c not in no_yahoo and d in rows and d not in (y.get(c) or {}):
                y.setdefault(c, {})[d] = rows[d]["tradePrice"]
                mc.add(c)
        return {"need": len(cm), "bar": 0, "meta": len(mc), "none": 0, "fail": 0, "metaCodes": mc}
    return F.kr_fallback_days([day], lambda d: (uni, "시험"), dt.datetime(2026, 11, 19, 7, 0, tzinfo=F.KST), {}, fetch_daum=fetch_daum,
                              fetch_yahoo=fetch_yahoo, fill_day=fill, say=lambda s: None, cached=cached, keep=keep)


def _published(fr, day, extra=()):
    return {"pxDate": day.isoformat(), "usPxDate": day.isoformat(), "pxSrc": {"px": FB, "date": day.isoformat()},
            "stocks": [{"t": str(r["Code"]), "cls": "kr", "price": float(r["Close"])} for _, r in fr.iterrows()] + list(extra)}


def test_a_same_day_rerun_asks_only_the_unconfirmed_stocks_and_confirms_the_same(tmp_path):
    import test_kr_two_source as T2
    D18 = dt.date(2026, 11, 18)
    uni = T2.listing("2026-11-18_1452")
    miss = ("047400", "090460")                                                   # 야후가 그날 종가를 주지 않는 두 종목 (두 실행 모두 · 필수 종목 아님)
    keep, asked0 = {}, {}
    out0, _ = _fb_run(uni, D18, keep=keep, asked=asked0, no_yahoo=miss)
    fr0, st0 = out0[D18]
    assert set(miss) <= set(asked0["daum"]) and not set(miss) & set(fr0["Code"].astype(str))
    assert keep["day"] == "2026-11-18" and set(keep["kk"]) == set(fr0["Code"].astype(str)) and keep["knx"] == {}
    path = str(tmp_path / "kr-fb-v1.json")
    F.kr_fb_cache_save(keep, path)                                                # 보관본에 쓰고 읽어 와요 (진짜 파일 모양)
    cache = F.kr_fb_cache_load(path)
    cached, why = F.kr_fb_cache_pick(cache, _published(fr0, D18), D18)
    assert set(cached["kk"]) == set(fr0["Code"].astype(str)) and "다시 묻지 않아요" in why
    asked1 = {}
    out1, notes = _fb_run(uni, D18, cached=cached, asked=asked1, no_yahoo=miss)
    fr1, st1 = out1[D18]
    # 묻는 종목: 발행본이 확인하지 못한 종목만 (다음 · 야후 · 다시 읽기 모두) — 확인된 종목은 다시 묻지 않아요
    unconf = sorted(set(asked0["daum"]) - set(fr0["Code"].astype(str)))
    assert unconf == sorted(miss) and sorted(asked1["daum"]) == unconf and sorted(asked1["yahoo"]) == unconf and set(asked1.get("fill", [])) <= set(unconf)
    assert len(asked0["daum"]) == len(fr0) + len(unconf) > len(asked1["daum"])
    # 확인 결과는 모두 물은 실행과 똑같아요 (같은 종목 · 같은 종가 · 같은 집계)
    pd.testing.assert_frame_equal(fr1.sort_values("Code").reset_index(drop=True), fr0.sort_values("Code").reset_index(drop=True), check_dtype=False)
    for k in ("n", "conf", "mkt", "noDaum", "bad", "noYahoo", "diff", "must"):
        assert (len(st1[k]) if isinstance(st1[k], list) else st1[k]) == (len(st0[k]) if isinstance(st0[k], list) else st0[k]), k
    assert st1["skip"] == len(cached["kk"]) and F.px_src_counts(st1)["skip"] == len(cached["kk"]) and F.px_src_counts(st0)["skip"] == 0
    assert any("다음 · 야후 다시 묻지 않음" in n and f"묻는 종목 {len(unconf)}" in n for n in notes)


def test_the_cache_is_used_only_for_closes_the_publish_has_at_that_date():
    import test_kr_two_source as T2
    D18 = dt.date(2026, 11, 18)
    keep = {}
    out0, _ = _fb_run(T2.listing("2026-11-18_1452"), D18, keep=keep)
    fr0 = out0[D18][0]
    pub = _published(fr0, D18)
    cache = json.loads(json.dumps(keep))
    one = str(fr0["Code"].iloc[0])
    # 발행본 가격과 보관본 종가가 1원이라도 다르면 그 종목은 다시 물어요
    moved = copy.deepcopy(pub)
    next(s for s in moved["stocks"] if s["t"] == one)["price"] += 1
    c, why = F.kr_fb_cache_pick(cache, moved, D18)
    assert one not in c["kk"] and len(c["kk"]) == len(fr0) - 1 and "다시 물어요" in why
    # 발행본에 그 날짜 종가로 없는 종목 (마지막 확인 종가로 실었거나 · 시가총액 기준 밖이라 없음) 은 보관본을 믿지 않고 다시 물어요 (리뷰 3: 보관본은
    # 관문 전에 저장돼 보류 · 관문 실패 · 시험 실행의 값일 수 있어요)
    carried = copy.deepcopy(pub)
    next(s for s in carried["stocks"] if s["t"] == one)["pxd"] = "2026-11-17"
    c, why = F.kr_fb_cache_pick(cache, carried, D18)
    assert one not in c["kk"] and "발행본에 그 날짜 종가로 없는 보관본 종목 1은 다시 물어요" in why
    absent = dict(pub, stocks=[s for s in pub["stocks"] if s["t"] != one])
    assert one not in F.kr_fb_cache_pick(cache, absent, D18)[0]["kk"]
    # 보관본의 두 값이 서로 다르면 (두 출처 확인이 아니에요) 다시 물어요
    split = copy.deepcopy(cache)
    split["kk"][one]["y"]["2026-11-18"] += 1
    c, why = F.kr_fb_cache_pick(split, pub, D18)
    assert one not in c["kk"] and "읽을 수 없는 1종목은 다시 물어요" in why
    # 같은 날이 아니면 (새 거래일 · 발행본이 1차 출처 날 · 보관본 날짜가 다름 · 모양이 다름) 모두 물어요
    assert F.kr_fb_cache_pick(cache, pub, dt.date(2026, 11, 19))[0] is None
    assert F.kr_fb_cache_pick(cache, dict(pub, pxSrc={"px": LISTING, "date": "2026-11-18"}), D18)[0] is None
    assert F.kr_fb_cache_pick(dict(cache, day="2026-11-17"), pub, D18)[0] is None
    assert F.kr_fb_cache_pick(dict(cache, v=99), pub, D18)[0] is None and F.kr_fb_cache_pick(None, pub, D18)[0] is None
    bad = copy.deepcopy(cache)
    bad["kk"][one]["d"] = {"어제": {}}
    assert one not in F.kr_fb_cache_pick(bad, pub, D18)[0]["kk"]


def test_a_same_day_rerun_asks_only_unconfirmed_konex():
    """코넥스 (#158 · 야후 .KQ × 네이버): 그날 파일에 넣은 코넥스는 다시 묻지 않고, 확인 못 한 코넥스만 네이버 · 야후에 물어요. 결과는 같아요."""
    import test_konex_two_source as TK
    D16 = TK.D16

    def run(cached=None, keep=None, asked_n=None, asked_y=None):
        return F.kr_fallback_days([D16], lambda d: (TK.universe16(), "시험"), TK.NOW, {}, fetch_daum=lambda codes, n: (TK.daum2(), []),
                                  fetch_yahoo=lambda cm, a, b: (TK.yahoo2(), 0), fill_day=TK.no_fill, say=lambda s: None,
                                  caps=TK.CAPS_190, knx=TK.knx_fakes(asked_n, asked_y), cached=cached, keep=keep)
    keep, an0, ay0 = {}, [], []
    out0, _ = run(keep=keep, asked_n=an0, asked_y=ay0)
    fr0, st0 = out0[D16]
    kept = set(fr0.loc[fr0["Market"] == "KONEX", "Code"].astype(str))
    assert kept and set(keep["knx"]) == kept
    cached, _ = F.kr_fb_cache_pick(json.loads(json.dumps(keep)), _published(fr0, D16), D16)
    assert set(cached["knx"]) == kept
    an1, ay1 = [], []
    out1, notes = run(cached=cached, asked_n=an1, asked_y=ay1)
    fr1, st1 = out1[D16]
    assert set(an1) == set(an0) - kept and not kept & set(an1)
    assert {s.split(".")[0] for s in ay1} <= set(an0) - kept
    assert sorted(fr1["Code"].astype(str)) == sorted(fr0["Code"].astype(str))
    assert st1["knx"]["conf"] == st0["knx"]["conf"] and st1["knx"]["kept"] == st0["knx"]["kept"] and st1["conf"] == st0["conf"]
    assert F.px_src_counts(st1)["conf"] == F.px_src_counts(st0)["conf"]


def test_fetch_korea_wires_the_cache_once():
    import inspect
    body = inspect.getsource(F.fetch_korea)
    assert body.count("kr_fb_cache_pick(kr_fb_cache_load(), prev, max(ended))") == 1
    assert "cached=fb_cached, keep=fb_keep" in body and body.count("kr_fb_cache_save(fb_keep)") == 1
    assert F.KR_FB_CACHE_PATH.startswith(".dart-cache/")                          # 'DART 캐시 저장' 단계가 같이 보관해요
    with open(WF, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    save = next(s for s in wf["jobs"]["update"]["steps"] if s.get("name") == "DART 캐시 저장")
    assert save["with"]["path"] == ".dart-cache" and save["if"] == "always()"


def test_the_kept_daum_fields_build_the_same_row():
    """보관본은 다음 행에서 KR_FB_DAUM_KEEP 칸만 남겨요 — 그 칸만으로 만든 행이 원래 행으로 만든 것과 같아야 해요 (실제 응답 픽스처 모두)."""
    import test_kr_two_source as T2
    uni = T2.listing("2026-11-18_1452")
    us = {str(r["Code"]).strip(): r for _, r in uni.iterrows()}
    n = 0
    for c, rows in T2.daum().items():
        if c not in us:
            continue
        for d, r in rows.items():
            assert F.kr_fb_row(us[c], {k: r[k] for k in F.KR_FB_DAUM_KEEP if k in r}) == F.kr_fb_row(us[c], r), (c, d)
            n += 1
    assert n > 50



def test_a_green_not_better_run_is_healthy_and_closes_a_real_alarm(monkeypatch):
    """#161 리뷰 7: 06:40 발행 뒤 빨간 실행이 경보를 열었어도, 그 뒤 '같은 날 · 더 낫지 않음' 실행 (관문 · 화면 검사 통과 · 같은 날짜) 은 건강한
    실행이라 경보가 닫혀요. 바닥 아래 · 잃은 종목 보류는 그대로 중립이에요 (닫지 않아요)."""
    import test_watchdog as TWD
    alarm = {"number": 9, "created_at": "2026-11-04T07:37:00Z", "state": "open"}
    net = TWD.FakeNet(data_runs=[TWD.run(3, "success"), TWD.run(2, "failure"), TWD.run(1, "success")], jobs={3: held_jobs("skipped")},
                      issues=[dict(alarm)])
    assert W.is_held_run(net, TWD.run(3, "success")) is False
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 0
    assert TWD.posts(net, "/issues/9/comments")[-1][2]["body"].startswith("정상화됐어요")
    net = TWD.FakeNet(data_runs=[TWD.run(3, "success"), TWD.run(2, "failure"), TWD.run(1, "success")], jobs={3: held_jobs("success")},
                      issues=[dict(alarm)])
    assert TWD.go(net, TWD.MORNING, monkeypatch=monkeypatch) == 1 and not [c for c in net.calls if c[0] == "PATCH"]
    # 표시 단계 전의 실행 (보류만 있던 이 PR 의 첫 모양) 은 예전처럼 중립
    assert W.is_held_run(TWD.FakeNet(jobs={4: held_jobs(None)}), TWD.run(4, "success")) is True


def test_a_file_with_a_same_day_reuse_record_passes_the_gate_and_the_konex_row_counts_right():
    """리뷰 4: 같은 날 다시 쓴 기록이 있는 파일로 관문을 돌려요 (#158 코넥스 모양 · 다시 쓴 코스피 · 코스닥 2종목). 코넥스는 기록으로 다시 쓰지 않아서
    (보관본 길로만 · 그날 확인 수에 들어가요) 코넥스 줄의 '발행한 코넥스 = 기록 · 그날 파일에 넣은 수' 가 그대로 맞아요."""
    import test_konex_two_source as TK
    cur, prev0, old, alt, codes = TK.fb_pair_konex()
    kr = [s["t"] for s in V.kr_stocks(cur["data"]) if s["t"] not in V.MUST and s["t"] not in codes]
    re_used = kr[:2]
    cur["data"]["pxSrc"]["own"] = {"v": 1, "max": 5, "n": 0, "codes": [], "unconf": 2, "unconfWhy": {"mkt": 0, "conf": 2, "knx": 0},
                                   "drop": {}, "dropEx": [], "bad": {"n": 0, "rows": []}, "aged": [],
                                   "reuse": {"v": 1, "from": "2026-10-31T06:40:00+09:00", "earlier": 50, "n": 2, "kk": 2, "codes": re_used,
                                             "lost": 0, "lostEx": []}}
    earlier = copy.deepcopy(cur)                                                  # 같은 날 아침 발행본 (같은 종목 · 같은 가격)
    earlier["data"]["pxSrc"].pop("own")
    rep = TK.check(cur, earlier, old, alt)
    assert not rep.failed, rep.table()
    r = TK.row(rep)
    assert r[3] == "PASS" and "발행 3" in r[1], r


def test_dart_makes_no_calls_on_a_same_day_rerun(tmp_path, monkeypatch):
    """리뷰 5: 같은 기준일을 다시 도는 실행은 DART 를 부르지 않아요 (하루 한도 20,000 · 다시 도는 실행마다 670 ~ 800회). 재확인 · 다시 읽기 몫도 쓰지 않아요."""
    def boom(*a, **k):
        raise AssertionError("DART 를 불렀어요")
    monkeypatch.setattr(F.requests, "get", boom)
    c = F.DartClient("시험키아님", path=str(tmp_path / "none.json.gz"))
    c.no_call = "같은 기준일을 다시 도는 실행 (시험)"
    assert c.get("list.json", {"corp_code": "00126380"}) is None and c.get("elestock.json", {"corp_code": "1"}) is None
    assert c.blocked == 2 and "DART 를 부르지 않았어요 (막은 조회 2회" in c.summary()
    # 90일 지난 항목 (재확인 대상): 부르지 않는 실행은 재확인으로 세지 않고 보관본 값을 그대로 줘요
    key = "00126380|2025|11011|t"
    c.entries[key] = {"st": "000", "at": "2026-01-01", "d": {"x": 1}}
    left = c.revalidate_left
    assert c.report("fnlttSinglAcnt.json", "00126380", 2025, "11011", "t", lambda j: j) == {"x": 1}
    assert c.revalidated == 0 and c.revalidate_left == left and c.blocked == 2 and "재확인" not in c.summary()
    body = __import__("inspect").getsource(F.main)
    assert "client.no_call = why_sd" in body and "load_morning_disc(live=prev)" in body
    assert body.index("if prev_disc is not None:") < body.index('disc = ph.run("공시", fetch_disclosures')


def test_same_day_rerun_is_keyed_on_the_price_date_not_the_publish_day():
    """리뷰 2: 월요일에 금요일 데이터를 다시 도는 실행도 같은 기준일이에요 (DART 를 부르지 않아요) — 발행한 날과 상관없이."""
    prev = dict(pub(kr=KR5), publishedAt="2026-11-21T06:52:00+09:00")
    src = {"px": FB}
    assert F.kr_same_day_rerun(prev, src, dt.date(2026, 11, 20))[0] is True
    assert F.kr_same_day_rerun(dict(prev, publishedAt="2026-11-14T06:40:00+09:00"), src, dt.date(2026, 11, 20))[0] is True
    assert F.kr_same_day_rerun(prev, src, dt.date(2026, 11, 21))[0] is False       # 새 기준일
    assert F.kr_same_day_rerun(prev, {"px": LISTING}, dt.date(2026, 11, 20))[0] is False
    assert F.kr_same_day_rerun(listing_data("2026-11-20"), src, dt.date(2026, 11, 20))[0] is False


def test_the_morning_disc_is_reused_only_from_the_same_publish(tmp_path):
    p = tmp_path / "disc.json"
    live = {"publishedAt": "2026-11-21T06:52:00+09:00"}
    p.write_text(json.dumps({"asOf": "2026-11-21", "insider": [{"t": "005930"}], "nps": [], "issue": [], "publishedAt": live["publishedAt"]}))
    d, why = F.load_morning_disc(str(p), live=live)
    assert d["insider"] == [{"t": "005930"}] and "내부자 1건" in why and "공시 내용 날짜 2026-11-21" in why
    d, why = F.load_morning_disc(str(p), live={"publishedAt": "2026-11-21T09:40:00+09:00"})    # 다른 발행의 disc.json → 쓰지 않아요
    assert d is None and "다른 발행" in why
    p.write_text("{}")
    assert F.load_morning_disc(str(p))[0] is None
    assert F.load_morning_disc(str(tmp_path / "없음.json"))[0] is None


LIVE_ENV = {"GITHUB_RUN_ID": "44700000001", "DRY_RUN": ""}


def test_a_green_rerun_that_gained_nothing_quiets_later_starts_for_three_hours():
    """리뷰 6 · 2차: 같은 기준일을 다시 돌아 그 날짜 종가 국내 종목을 늘리지 못한 실제 실행이 초록으로 끝났을 때만, 3시간 안의 정해진 시각 · 바깥 타이머
    실행은 데이터를 모으지 않아요. 시험 실행은 기록을 남기지 않고, 관문 · 화면 검사에 실패한 실행 (초록 아님) 의 기록은 믿지 않아요."""
    prev = dict(pub(kr=KR5, us="2026-11-20"), publishedAt="2026-11-21T06:52:00+09:00")
    same = pub(kr=KR5, us="2026-11-20")
    state = F.kr_rerun_state(prev, same, kst(2026, 11, 21, 9, 30), 2474, 2474, env=LIVE_ENV)
    assert state["gain"] == 0 and state["run"] == "44700000001"
    green, red = (lambda r: True), (lambda r: False)
    why = F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0), run_ok=green)
    assert why and "09:30 KST" in why and "90분 남음" in why and "44700000001" in why
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0), run_ok=red) is None          # 그 실행이 빨갛게 끝남 → 쉬지 않아요
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0), run_ok=lambda r: None) is None   # 확인 못 함
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0)) is None                   # 확인하는 함수 없음
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 12, 30), run_ok=green) is None    # 3시간 지남
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0), auto=False, run_ok=green) is None   # 손으로 누른 실행은 늘 돌아요
    assert F.kr_rerun_throttle(dict(state, gain=3), prev, kst(2026, 11, 21, 11, 0), run_ok=green) is None
    assert F.kr_rerun_throttle(state, dict(prev, usPxDate="2026-11-21"), kst(2026, 11, 21, 11, 0), run_ok=green) is None
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 22, 9, 40), run_ok=green) is None     # 다음 날
    early = F.kr_rerun_state(prev, same, kst(2026, 11, 21, 6, 50), 5, 5, env=LIVE_ENV)
    assert F.kr_rerun_throttle(early, prev, kst(2026, 11, 21, 7, 30), run_ok=green) is None     # 07:00 전 기록 (미국 종가 확정 앞뒤)
    late = F.kr_rerun_state(prev, same, kst(2026, 11, 21, 14, 0), 5, 5, env=LIVE_ENV)
    assert F.kr_rerun_throttle(late, prev, kst(2026, 11, 21, 15, 31), run_ok=green) is None     # 15:30 뒤에는 새 거래일이 끝날 수 있어요
    # 기록을 남기지 않는 실행: 시험 실행 · GitHub 실행 번호 없음 · 같은 기준일이 아님
    assert F.kr_rerun_state(prev, same, kst(2026, 11, 21, 9, 30), 5, 5, env={"GITHUB_RUN_ID": "1", "DRY_RUN": "true"}) is None
    assert F.kr_rerun_state(prev, same, kst(2026, 11, 21, 9, 30), 5, 5, env={}) is None
    assert F.kr_rerun_state(prev, pub(px="2026-11-21", us="2026-11-21"), kst(2026, 11, 21, 9, 30), 5, 5, env=LIVE_ENV) is None
    # 월요일: 토요일 기록은 쉬게 하지 않아요 (같은 날 기록만)
    sat = F.kr_rerun_state(prev, same, kst(2026, 11, 21, 9, 30), 5, 5, env=LIVE_ENV)
    assert F.kr_rerun_throttle(sat, prev, kst(2026, 11, 23, 10, 53), run_ok=green) is None


def test_github_run_succeeded_reads_the_public_run(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")

    class R:
        def __init__(self, st, js):
            self.status_code, self._js = st, js

        def json(self):
            return self._js
    seen = []

    def get(url, **kw):
        seen.append((url, kw.get("headers", {}).get("Authorization")))
        return R(200, {"status": "completed", "conclusion": "success"})
    assert F.github_run_succeeded("123", get=get) is True and seen == [("https://api.github.com/repos/o/r/actions/runs/123", None)]   # 토큰 없이
    assert F.github_run_succeeded("123", get=lambda u, **k: R(200, {"status": "completed", "conclusion": "failure"})) is False
    assert F.github_run_succeeded("123", get=lambda u, **k: R(403, {})) is None
    assert F.github_run_succeeded("123", get=lambda u, **k: (_ for _ in ()).throw(OSError("x"))) is None


def test_main_skips_collecting_when_quiet_and_marks_it(tmp_path, monkeypatch, capsys):
    prev = dict(pub(kr=KR5, us="2026-11-20"), publishedAt="2026-11-21T06:52:00+09:00")
    state = F.kr_rerun_state(prev, pub(kr=KR5, us="2026-11-20"), kst(2026, 11, 21, 9, 30), 5, 5, env=LIVE_ENV)

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return kst(2026, 11, 21, 10, 53).astimezone(tz) if tz else kst(2026, 11, 21, 10, 53)
    monkeypatch.setattr(F.dt, "datetime", Clock)
    monkeypatch.setattr(F, "read_prev_data", lambda: prev)
    monkeypatch.setattr(F, "kr_rerun_state_load", lambda: state)
    monkeypatch.setattr(F, "github_run_succeeded", lambda r: True)
    monkeypatch.setattr(F, "load_industry_tables", lambda: (_ for _ in ()).throw(AssertionError("데이터를 모으기 시작했어요")))
    monkeypatch.setenv("BAEPSAE_AUTO_RUN", "1")
    monkeypatch.setenv("DART_MODE", "cache")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    assert F.main() is None
    assert "3시간이 지나기 전이라" in capsys.readouterr().out
    assert (tmp_path / F.QUIET_MARK).read_text().startswith("같은 기준일을 다시 도는 실행이에요")


def test_a_quiet_run_is_neutral_and_never_closes_an_alarm(tmp_path, monkeypatch, capsys):
    """2차 리뷰 MUST: 쉬는 실행 (데이터 수집 없음 · 파일 = 발행본) 은 시험한 것이 없어 건강한 실행으로 세지 않아요 — 감시에 중립 (표시 단계가 돌아요).
    재현 (revHB/quiet_same.py): 같은 파일이면 '같은 날 · 더 낫지 않음' (건강) 이 되던 것이 이제 '쉼' (중립) 이에요."""
    live = pub(kr=KR5, others=US2)
    mark = tmp_path / "baepsae-quiet.txt"
    mark.write_text("같은 기준일을 다시 도는 실행이에요: 09:30 KST … 데이터를 모으지 않아요\n")
    hold, out, summ, _ = run_main(tmp_path, monkeypatch, copy.deepcopy(live), live, kst(2026, 11, 21, 10, 53), argv=["--quiet", str(mark)],
                                  actions=True)
    lines = out.splitlines()
    assert hold is True and "kind=quiet" in lines and "neutral=true" in lines and lines[-1] == "hold=true"
    log = capsys.readouterr().out
    assert "!! [쉼]" in log and "::notice title=쉬는 실행" in log and "쉼 — 데이터를 모으지 않은 실행" in summ
    # 표시 파일이 없으면 예전처럼 (같은 파일 → 같은 날 · 더 낫지 않음 · 건강)
    hold, out, _, _ = run_main(tmp_path, monkeypatch, copy.deepcopy(live), live, kst(2026, 11, 21, 10, 53), argv=["--quiet", str(tmp_path / "없음")])
    assert "kind=same" in out.splitlines() and "neutral=false" in out.splitlines()
    # 워크플로: 데이터 수집이 남긴 표시가 있으면 발행 판단에 넘겨요
    r, o, calls = run_hold_step(tmp_path, 'echo "hold=true" >> "$GITHUB_OUTPUT"\n', {"RUNNER_TEMP": str(tmp_path)})
    assert f"--quiet {tmp_path}/baepsae-quiet.txt" in calls
    mark.unlink()
    r, o, calls = run_hold_step(tmp_path, 'echo "hold=true" >> "$GITHUB_OUTPUT"\n', {"RUNNER_TEMP": str(tmp_path)})
    assert "--quiet" not in calls


def test_yahoo_empty_answers_are_told_apart_from_failures(monkeypatch):
    """2차 리뷰 1: '야후가 싣지 않음' (noList) 은 잘 된 빈 답 (빈 차트 · 404 Not Found) 만이에요. 받지 못한 종목 (오류 · 시간 초과) 은 다시 물어요 (남은 것)."""
    D18 = dt.date(2026, 11, 18)
    cm = {"000010": "KOSPI", "000020": "KOSPI", "000030": "KOSDAQ", "000040": "KOSPI"}

    def fetch(sym, a, b):
        c = sym.split(".")[0]
        if c == "000020":
            return {"timestamp": [], "indicators": {"quote": [{"close": []}]}}           # 잘 된 빈 답
        if c == "000030":
            raise F.YahooNotFound("HTTP 404 Not Found")
        if c == "000040":
            raise RuntimeError("ReadTimeout")
        return {"timestamp": [int(dt.datetime(2026, 11, 18, 9, tzinfo=F.KST).timestamp())], "indicators": {"quote": [{"close": [1000.0]}]}}
    out, failed, cut = F.fetch_yahoo_kr_closes(cm, D18, D18 + dt.timedelta(days=1), fetch=fetch, workers=1, say=lambda s: None)
    assert sorted(out) == ["000010"] and out.empty == {"000020", "000030"} and failed == 2 and cut == 0
    # 404 응답: 야후의 'Not Found' 답만 YahooNotFound (그 밖의 404 · 오류는 예전처럼 실패)

    class Resp:
        def __init__(self, code, js):
            self.status_code, self._js, self.headers = code, js, {}

        def json(self):
            return self._js

    class Sess:
        def __init__(self, resp):
            self.resp = resp

        def get(self, *a, **k):
            return self.resp
    monkeypatch.setattr(F._YAHOO_LOCAL, "s", Sess(Resp(404, {"chart": {"result": None, "error": {"code": "Not Found"}}})), raising=False)
    with pytest.raises(F.YahooNotFound):
        F._fetch_yahoo_chart("000030.KQ")
    monkeypatch.setattr(F._YAHOO_LOCAL, "s", Sess(Resp(404, {"x": 1})), raising=False)
    with pytest.raises(RuntimeError) as e:
        F._fetch_yahoo_chart("000030.KQ")
    assert not isinstance(e.value, F.YahooNotFound)


def test_open_closes_count_only_what_a_re_ask_can_change():
    """리뷰 6: 두 출처가 다른 종목 · 야후가 싣지 않는 종목은 하루 종일 그대로라 '남은 것' 으로 세지 않아요 (fb.open · fb.knx.open)."""
    import test_kr_two_source as T2
    D18 = dt.date(2026, 11, 18)
    out, _ = _fb_run(T2.listing("2026-11-18_1452"), D18, no_yahoo=("047400", "090460"))
    c = F.px_src_counts(out[D18][1])
    assert c["noYahoo"] == 2 and c["noList"] == 2 and c["open"] == 0              # 야후가 '자료 없음' 으로 답한 두 종목 → 다시 물어도 같아요
    out, _ = _fb_run(T2.listing("2026-11-18_1452"), D18, no_yahoo=("047400", "090460"), answered=False)
    c = F.px_src_counts(out[D18][1])
    assert c["noYahoo"] == 2 and c["noList"] == 0 and c["open"] == 2              # 받지 못함 (오류 · 시간 초과) → 남은 것 (뒤의 실행이 다시 물어요)
    d = fb_data("2026-11-20", 2740, own={"v": 1, "n": 25, "codes": [], "unconf": 31})
    d["pxSrc"]["fb"].update({"open": 1, "noList": 5})
    assert A.open_closes(d) == {"kr": 1, "us": 0}
    d["pxSrc"]["fb"]["open"] = 0
    assert A.open_closes(d) == {"kr": 0, "us": 0}
    assert A.decide(d, kst(2026, 11, 21, 10, 53), CAL)[0] is True                  # 바뀔 수 있는 것이 없으면 예전처럼 건너뛰어요
    d["pxSrc"]["fb"]["knx"] = {"kept": 20, "open": 3}
    assert A.open_closes(d) == {"kr": 3, "us": 0}


# ── 10. #161 리뷰 (2차): 상위 자르기 · 같은 날 d1 · 미국 날짜 · d1 잃음 ─────────────
D20 = dt.date(2026, 11, 20)
CUT_CODES = ["100010", "100020", "100030", "100040", "100050", "100060"]           # 시가총액 큰 순
CUT_CAPS = dict(zip(list(F.MUST_KR) + CUT_CODES, [9e14 - i * 1e13 for i in range(len(F.MUST_KR))] + [6e12, 5e12, 4e12, 3e12, 2e12, 1e12]))
CUT_MAX = len(F.MUST_KR) + 3                                                        # 필수 종목 + 3 (진짜는 2,500)
CUT_FULL = pd.DataFrame({"Code": list(CUT_CAPS), "Name": ["종목" + c for c in CUT_CAPS], "Market": ["KOSPI"] * len(CUT_CAPS),
                         "Marcap": list(CUT_CAPS.values()), "Amount": [1e9] * len(CUT_CAPS)})
CUT_DAYS = list(pd.to_datetime(["2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]))


def cut_row(c, **kw):
    return {"t": c, "cls": "kr", "nk": "종목" + c, "price": 1000.0, "cap": CUT_CAPS[c], "d1": 0.5, **kw}


def cut_run(prev, conf, mode=FB, keep=True):
    """fetch_korea 의 순서 그대로 (줄인 모양): 그날 목록 (2차 출처 날은 확인된 종목만) → select_kr_universe (같은 기준일이면 지난 발행본 종목도 ·
    kr_same_day_keep) → 시세 → 2차 출처 날이면 kr_own_close_step (다시 쓰기 · 마지막 확인 종가). keep=False 는 이 고침 전 (상위 자르기만)."""
    lst = CUT_FULL[CUT_FULL["Code"].isin(conf)] if mode == FB else CUT_FULL
    ks = F.kr_same_day_keep(prev, D20) if keep else set()
    uni = F.select_kr_universe(lst, CUT_MAX, keep=ks)
    out = [cut_row(c) for c in uni["Code"]]
    if mode == FB:
        src = {"px": FB, "date": D20.isoformat(), "fb": {"conf": len(conf), "diffT": []}, "knx": {"px": None}}
        F.kr_own_close_step(prev, CUT_FULL, set(conf), src, D20, CUT_DAYS, out, {"jump": [], "hidden": []}, {})
    else:
        src = {"px": LISTING, "date": D20.isoformat()}
    data = {"pxDate": D20.isoformat(), "usPxDate": D20.isoformat(), "publishedAt": f"2026-11-21T{len(out):02d}:00:00+09:00",
            "pxSrc": F.px_src_final(src, out), "stocks": out}
    return json.loads(json.dumps(data, allow_nan=False)), ks, uni, len(lst)


def cut_yesterday():
    """어제 발행본 (pxDate 11-19 · 2차 출처): 필수 종목 + 100010 · 100020 · 100030 · 100060 (그날 시가총액 순위는 달랐어요)."""
    rows = [cut_row(c) for c in list(F.MUST_KR) + ["100010", "100020", "100030", "100060"]]
    return {"pxDate": "2026-11-19", "usPxDate": "2026-11-19", "publishedAt": "2026-11-20T06:40:00+09:00", "pxSrc": {"px": FB, "date": "2026-11-19"},
            "krSeries": {"jump": []}, "stocks": rows}


def at_date(data):
    return sorted(s["t"] for s in data["stocks"] if s.get("cls") == "kr" and s.get("pxd") is None)


def test_a_same_day_rerun_keeps_every_stock_of_the_earlier_publish_through_the_top_cut(capsys):
    """#161 리뷰 M1 (scratchpad rev161/repro_cut.py): 확인된 종목이 상위 자르기보다 많은 날, 06:40 에 마지막 확인 종가로 실은 종목이 나중에 확인되면 상위에
    들어와 06:40 에 그 날짜 종가로 실은 종목을 밀어내거나 (그 종목은 확인돼 다시 쓰기 · 마지막 확인 종가에도 들지 않음), 상위 밖이라 빠졌어요 → 같은 날 다시
    발행이 날마다 '종목을 잃음' 이었어요. 이제 같은 기준일 실행은 지난 발행본의 종목을 상위 밖이어도 처리해요."""
    yday = cut_yesterday()
    unconf = {"100030", "100060"}                                                   # 06:40: 야후 종가가 아직 빈 두 종목
    conf0 = [c for c in CUT_CAPS if c not in unconf]
    p1, ks, uni, _ = cut_run(yday, conf0)
    # 06:40 (그날 첫 실행 · 지난 발행본은 어제): 예전 그대로 — 정확히 상위 CUT_MAX · 확인 못 한 두 종목은 마지막 확인 종가
    assert ks == set() and len(uni) == CUT_MAX
    assert at_date(p1) == sorted(list(F.MUST_KR) + ["100010", "100020", "100040"])
    assert sorted(s["t"] for s in p1["stocks"] if s.get("pxd")) == ["100030", "100060"]
    # 10:53: 모두 확인 — 예전 (상위 자르기만): 100030 이 상위에 들어와 100040 을 밀어내고, 100060 은 상위 밖이라 빠져요 → 잃음
    before, _, _, _ = cut_run(p1, list(CUT_CAPS), keep=False)
    lost = P.lost_stocks(before, p1)
    assert lost["kr"] == ["100040"] and lost["own"] == ["100060"]
    assert P.same_day_decision(FB, FB, before, p1).kind == "loss"
    # 이제: 지난 발행본의 종목은 상위 밖이어도 처리 → 잃은 것 없음 · 그 날짜 종가 국내 +2 → 발행
    capsys.readouterr()
    p2, ks, uni, n_all = cut_run(p1, list(CUT_CAPS))
    assert ks == set(s["t"] for s in p1["stocks"])
    assert list(uni["Code"]) == list(F.MUST_KR) + ["100010", "100020", "100030", "100040", "100060"]   # 시가총액 순 · 상위 뒤에 붙어요
    assert "100050" not in at_date(p2)                                              # 지난 발행본에 없던 종목은 예전처럼 상위 안만
    assert all(not v for v in P.lost_stocks(p2, p1).values())
    d = P.same_day_decision(FB, FB, p2, p1)
    assert d.hold is False and d.kind == "publish" and f"{CUT_MAX:,} → {CUT_MAX + 2:,}" in d.why
    loud, txt = F.kr_same_day_keep_note(ks, uni, CUT_MAX, n_all)
    assert loud and "상위 밖에서 더한 종목 2" in txt and "100040 종목100040" in txt and "100060 종목100060" in txt
    # 13:37 (같은 날 또 · 지난 발행본은 10:53): 같은 종목 · 같은 수 → '같은 날 · 더 낫지 않음' (잃음 아님)
    p3, _, _, _ = cut_run(p2, list(CUT_CAPS))
    assert at_date(p3) == at_date(p2) and P.same_day_decision(FB, FB, p3, p2).kind == "same"
    # 다음 새 기준일은 다시 상위 CUT_MAX 만 (지난 발행본의 기준일이 달라요)
    assert F.kr_same_day_keep(p2, dt.date(2026, 11, 21)) == set()


def test_the_volunteer_final_switch_run_keeps_the_morning_stocks_too():
    """같은 기준일에 KRX 최종본이 생긴 실행 (1차 출처 · 그날 목록 전체): 06:40 (2차 출처) 발행본의 종목을 모두 처리해요 → 잃지 않고 발행."""
    yday = cut_yesterday()
    p1, _, _, _ = cut_run(yday, [c for c in CUT_CAPS if c not in ("100030", "100060")])
    before, _, _, _ = cut_run(p1, [], mode=LISTING, keep=False)
    assert P.same_day_decision(LISTING, FB, before, p1).kind == "loss"            # 예전: 100040 을 잃어요
    sw, ks, uni, _ = cut_run(p1, [], mode=LISTING)
    assert ks and all(not v for v in P.lost_stocks(sw, p1).values())
    d = P.same_day_decision(LISTING, FB, sw, p1)
    assert d.hold is False and d.kind == "publish"


def test_the_keep_set_is_only_for_a_same_date_backup_publish():
    p = cut_yesterday()
    assert F.kr_same_day_keep(p, dt.date(2026, 11, 19)) == set(s["t"] for s in p["stocks"])
    assert F.kr_same_day_keep(p, D20) == set()                                      # 그날 첫 실행 (지난 발행본은 어제)
    assert F.kr_same_day_keep(dict(p, pxSrc={"px": LISTING, "date": "2026-11-19"}), dt.date(2026, 11, 19)) == set()   # 1차 출처 발행본 뒤
    assert F.kr_same_day_keep(None, D20) == set() and F.kr_same_day_keep(p, None) == set()
    p["stocks"] += [{"t": "069500", "cls": "kr", "fund": True, "price": 1.0}, {"t": "AAPL", "cls": "us", "price": 1.0}]
    assert "069500" not in F.kr_same_day_keep(p, dt.date(2026, 11, 19)) and "AAPL" not in F.kr_same_day_keep(p, dt.date(2026, 11, 19))
    # keep 이 비면 예전과 똑같은 결과 (같은 표 · 같은 순서)
    assert F.select_kr_universe(CUT_FULL, CUT_MAX).equals(F.select_kr_universe(CUT_FULL, CUT_MAX, keep=()))
    assert F.kr_same_day_keep_note(set(), CUT_FULL, CUT_MAX, len(CUT_FULL)) is None
    # 필수 종목 확인은 그대로
    with pytest.raises(RuntimeError):
        F.select_kr_universe(CUT_FULL[CUT_FULL["Code"] != "005930"], CUT_MAX, keep={"100060"})


def test_fetch_korea_wires_the_keep_set_before_the_sample_cut():
    import inspect
    src = inspect.getsource(F.fetch_korea)
    a = src.index("keep_same = kr_same_day_keep(prev, px_date)")
    b = src.index("listing = select_kr_universe(listing, MAX_KR, keep=keep_same)")
    c = src.index("if sample_size():")
    assert a < b < c and "kr_same_day_keep_note(keep_same, listing, MAX_KR, n_all)" in src
    assert src.count("select_kr_universe(") == 1


def test_gate_korean_count_rows_have_no_upper_bound_and_pass_slightly_above_the_cut():
    """'국내 종목 수' (바닥 KR_MIN) 와 '국내 종목 수 변화' (±KR_REL) 는 pxDate 종가만 세고 위 한도가 없어요 — 같은 날 상위 밖 종목을 더해 2,500 을 조금
    넘어도 (예: 2,500 → 2,530 · 다음 날 2,530 → 2,500) 그대로 통과해요. 관문의 그 두 줄을 같은 비율 (30 / 2,400) 로 돌려 봐요."""
    assert V.KR_MIN < F.MAX_KR
    for a, b in ((F.MAX_KR, F.MAX_KR + 30), (F.MAX_KR + 30, F.MAX_KR)):
        assert abs(b / a - 1) <= V.KR_REL
    import test_kr_two_source as T2
    cur, _, old, alt = T2.fb_pair()
    codes = [s["t"] for s in V.kr_stocks(cur["data"]) if s["t"] not in V.MUST]
    for direction in ("up", "down"):
        a, b = copy.deepcopy(cur), copy.deepcopy(cur)
        fewer = a if direction == "up" else b
        gone = set(codes[-30:])
        fewer["data"]["stocks"] = [s for s in fewer["data"]["stocks"] if s["t"] not in gone]
        rep = V.run_checks(b, a, old, T2.TODAY, mode="publish", count_between=lambda x, y: 0, sessions=T2.SESSIONS, now=T2.NOW,
                           hilo=T2.hilo_of(b, V.MUST), alt=alt)
        rows = {r[0]: r for r in rep.rows}
        assert rows["국내 종목 수"][3] == "PASS" and rows["국내 종목 수 변화"][3] == "PASS", (direction, rows["국내 종목 수 변화"])
        if direction == "up":
            assert not rep.failed, rep.table()


# M2: 같은 기준일에 자원봉사 최종본이 생긴 실행의 d1 (리뷰 재현 rev161/repro_d1.py)
def same_day_pub20(cur, **kw):
    """11-20 06:40 발행본 흉내 (pxDate 11-20 · 2차 출처): 오늘 최종본과 같은 공식 종가 · d1 = KRX 등락률 (같은 11-19 기준 · 소수 둘째 자리) ·
    거래 없는 종목은 noTrade."""
    import test_d1_after_gap as G
    ratio, nt = G.krx_ratio(cur), F.kr_no_trade_plan(cur, max_share=1.0)[0]
    stocks = []
    for c, p in F._official_map(cur).items():
        stocks.append({"t": c, "cls": "kr", "price": p, "noTrade": True, "d1Why": "noTrade"} if c in nt
                      else {"t": c, "cls": "kr", "price": p, "d1": round(ratio[c], 2)})
    out = {"pxDate": "2026-11-20", "usPxDate": "2026-11-20", "publishedAt": "2026-11-21T06:40:00+09:00", "listSrc": FB,
           "pxSrc": {"px": FB, "date": "2026-11-20"}, "stocks": stocks}
    out.update(kw)
    return out


def run_d1(cur, pub_, px_date=D20):
    """fetch_korea 의 d1 부분 그대로 (test_d1_after_gap.run_day + 이 고침의 같은 날 길 — 아래 시험이 fetch_korea 의 그 줄을 확인해요)."""
    import test_d1_after_gap as G
    sessions, notes, prev_final = F.kr_recent_sessions(px_date, lambda d: G.FILES[d]() if d in G.FILES else None, G.COMMITS.get, n=4,
                                                       special=F.load_krx_special_sessions())
    want_prev = F.kr_prev_session(px_date, [t for t in G.TRADE_DAYS if t.date() <= px_date])
    ok_prev = F.prev_session_ok(sessions, prev_final, want_prev)
    d1, _, _ = F.kr_d1_val20(cur, sessions, ok_prev)
    base_ok, rec = None, None
    if not ok_prev and want_prev is not None:
        d1, base_ok, rec = F.kr_d1_base_day(cur, pub_, want_prev)
        same_d1 = F.kr_d1_same_day(cur, pub_, px_date, want_prev) if rec.get("why") == "day" else None
        if same_d1 is not None:
            d1, base_ok, rec = same_d1
    nt = F.kr_no_trade_plan(cur, max_share=1.0)[0]
    out, why, ntm, cnt = F.kr_d1_split(cur, sessions, ok_prev, d1, nt, base_ok=base_ok)
    return {"ok_prev": ok_prev, "d1": out, "why": why, "nt": ntm, "cnt": cnt, "rec": rec, "base_ok": base_ok}


def test_a_same_day_volunteer_final_run_keeps_the_morning_d1():
    import test_d1_after_gap as G
    cur = G.cur20()
    pub20 = same_day_pub20(cur)
    # 이 고침 전: 지난 발행본이 같은 기준일이라 (직전 거래일 아님) 모두 빈 칸 → '필수 종목 d1' 실패
    old = G.run_day(cur, pub20)
    assert old["d1"] == {} and old["rec"]["why"] == "day" and all(old["why"][c] == "prev" for c in G.MUST)
    r = run_d1(cur, pub20)
    assert not r["ok_prev"] and r["rec"]["same"] == 1 and r["rec"]["why"] is None and r["rec"]["from"] == "2026-11-21T06:40:00+09:00"
    assert r["rec"]["day"] == "2026-11-19" and r["rec"]["pub"] == "2026-11-20"
    assert (r["rec"]["ok"], r["rec"]["notConf"], r["rec"]["diff"], r["rec"]["noPub"], r["rec"]["noD1"], r["rec"]["noBase"]) == (11, 3, 0, 0, 0, 0)
    ratio = G.krx_ratio(cur)
    for c in G.MUST:
        assert r["d1"][c] == pytest.approx(ratio[c], abs=0.005), c
        assert c not in r["why"]
    assert r["d1"]["005930"] == -7.01
    assert r["why"]["001570"] == r["why"]["011810"] == r["why"]["496320"] == "noTrade"
    loud, txt = F.d1_base_note(r["rec"])
    assert loud and txt.startswith("d1: 직전 거래일 2026-11-19 최종본이 없고 지난 발행본이 같은 기준일 2026-11-20 (2026-11-21T06:40:00+09:00)")
    assert "11 / 14" in txt
    json.dumps(r["rec"], allow_nan=False)
    # 관문 '필수 종목 d1' 이 그 값으로 통과해요
    gcur, gprev, gfinal = G.good_pair()
    for s in gcur["data"]["stocks"]:
        if s["t"] in G.MUST:
            s["d1"] = r["d1"][s["t"]]
    rep, rows = G.gate_rows(gcur, gprev, gfinal)
    assert rows["필수 종목 d1"][3] == "PASS" and not rep.failed, rep.table()


def test_same_day_d1_is_blank_where_the_close_differs_or_the_morning_had_none():
    import test_d1_after_gap as G
    cur = G.cur20()
    pub20 = same_day_pub20(cur)
    by = {s["t"]: s for s in pub20["stocks"]}
    by["005380"]["price"] = 254000.0                                               # 그날 아침 값과 다른 종가 → 그 d1 은 쓰지 않아요
    by["090460"].pop("d1")
    by["090460"]["d1Why"] = "prev"                                                 # 아침에도 빈 칸 → 빈 칸
    by["047400"].pop("d1")
    by["047400"]["d1Why"] = "range"                       # 아침에 ±30% 밖인데 오늘 파일의 KRX 기준가로는 −8.83% → 기준이 달라 빈 칸 (#161 리뷰 3차 A-S1)
    by["035420"]["pxd"] = "2026-11-19"                                             # 아침에 마지막 확인 종가 → 그날 확인된 종가가 아님
    pub20["stocks"] = [s for s in pub20["stocks"] if s["t"] != "489460"]           # 아침 발행본에 없음
    r = run_d1(cur, pub20)
    rec = r["rec"]
    assert (rec["diff"], rec["noD1"], rec["notConf"], rec["noPub"], rec["krx"]) == (1, 1, 4, 1, 1) and rec["ok"] == 6
    assert "005380" not in r["d1"] and r["why"]["005380"] == "prev" and rec["ex"]["diff"] == ["005380 현대차 254,000→255,000"]
    assert r["why"]["090460"] == "prev" and rec["ex"]["noD1"] == ["090460 비에이치"]
    assert r["why"]["047400"] == "prev" and "047400" not in r["base_ok"] and rec["ex"]["krx"] == ["047400 유니온머티리얼"]
    assert r["why"]["035420"] == "prev" and r["why"]["489460"] == "prev"
    txt = F.d1_base_note(rec)[1]
    assert "가격이 다름 1" in txt and "오늘 공식 종가가 앞선 발행본의 가격과 다름: 005380 현대차 254,000→255,000" in txt and "앞선 발행본도 d1 빈 칸: 090460 비에이치" in txt
    assert "KRX 기준가로 본 등락률과 다름 1" in txt
    # 아침도 ±30% 밖이고 KRX 기준가로도 밖이면 range 그대로 (같은 기준)
    cur2 = G.cur20().astype({"Close": float, "Changes": float, "Marcap": float})
    i = cur2.index[cur2["Code"] == "047400"][0]
    up = 2775 * 1.35
    cur2.loc[i, ["Close", "Changes", "Marcap"]] = [up, up - 2775, up * float(cur2.loc[i, "Stocks"])]
    pub2 = same_day_pub20(cur2)
    for s_ in pub2["stocks"]:
        if s_["t"] == "047400":
            s_.pop("d1")
            s_["d1Why"] = "range"
    r = run_d1(cur2, pub2)
    assert r["why"]["047400"] == "range" and "047400" in r["base_ok"] and r["rec"]["krx"] == 0


def test_163_after_backup_days_is_unchanged():
    """#163 의 길 (지난 발행본이 직전 거래일): 같은 날 길은 쓰이지 않고 결과가 예전과 같아요. 지난 발행본이 그보다 앞이면 예전처럼 모두 빈 칸."""
    import test_d1_after_gap as G
    cur, pub19 = G.cur20(), G.pub19()
    old, new = G.run_day(cur, pub19), run_d1(cur, pub19)
    assert new["d1"] == old["d1"] and new["why"] == old["why"] and new["rec"] == old["rec"] and "same" not in new["rec"]
    assert F.kr_d1_same_day(cur, pub19, D20, G.D19) is None                       # 그 발행본의 pxDate 는 11-19 (이 실행은 11-20)
    p18 = G.pub19()
    p18["pxDate"], p18["pxSrc"]["date"] = "2026-11-18", "2026-11-18"
    r = run_d1(cur, p18)
    assert r["d1"] == {} and r["rec"]["why"] == "day" and "same" not in r["rec"]
    # 같은 기준일이어도 가격 출처를 모르는 발행본은 쓰지 않아요
    assert F.kr_d1_same_day(cur, same_day_pub20(cur, listSrc="prev-data.json"), D20, G.D19) is None


def test_same_day_d1_must_match_the_krx_base_in_todays_file():
    """#161 리뷰 3차 A-S1 (rev161a/d1_same.py): 아침 d1 은 두 출처의 직전 거래일 종가가 기준이었어요. 오늘 KRX 최종본의 기준가 (Close − Changes) 로 본
    등락률과 0.01 넘게 다르면 (권리락 · 분할로 KRX 가 기준가를 새로 정한 날) 다시 쓰지 않고 빈 칸 · 크게 (까닭 krx). Changes 가 없으면 맞춰 보지 않아요."""
    D, D1 = dt.date(2026, 11, 20), dt.date(2026, 11, 19)
    cur = pd.DataFrame([{"Code": "005930", "Name": "삼성전자", "Close": 10500, "Changes": 500, "Marcap": 10500 * 1000, "Stocks": 1000},
                        {"Code": "000660", "Name": "SK하이닉스", "Close": 20000, "Changes": 0, "Marcap": 20000 * 1000, "Stocks": 1000},
                        {"Code": "005380", "Name": "현대차", "Close": 21000, "Changes": 1000, "Marcap": 21000 * 1000, "Stocks": 1000},
                        {"Code": "105560", "Name": "KB금융", "Close": 3000, "Changes": float("nan"), "Marcap": 3000 * 1000, "Stocks": 1000}])
    prev = {"pxDate": D.isoformat(), "publishedAt": "2026-11-21T06:52:00+09:00", "listSrc": F.PX_SRC_FB, "pxSrc": {"px": F.PX_SRC_FB, "date": D.isoformat()},
            "stocks": [{"t": "005930", "cls": "kr", "price": 10500.0, "d1": 16.67},      # 아침 기준 9,000 · KRX 기준가 10,000 (+5.00%)
                       {"t": "000660", "cls": "kr", "price": 20000.0, "d1": -4.76},      # 아침 기준 21,000 · KRX 0.00%
                       {"t": "005380", "cls": "kr", "price": 21000.0, "d1": 5.0},        # KRX 21,000 ÷ 20,000 = +5.00% → 같음
                       {"t": "105560", "cls": "kr", "price": 3000.0, "d1": 1.2}]}        # 오늘 파일에 Changes 없음 → 맞춰 보지 않음
    d1, ok, rec = F.kr_d1_same_day(cur, prev, D, D1)
    assert d1 == {"005380": 5.0, "105560": 1.2} and ok == {"005380", "105560"}
    assert rec["krx"] == 2 and rec["ok"] == 2 and rec["ex"]["krx"] == ["000660 SK하이닉스 -4.76%→+0.00%", "005930 삼성전자 +16.67%→+5.00%"]
    loud, txt = F.d1_base_note(rec)
    assert loud and "KRX 기준가로 본 등락률과 다름 2" in txt and "005930 삼성전자 +16.67%→+5.00%" in txt
    json.dumps(rec, allow_nan=False)
    prev["stocks"][2]["d1"] = 5.01                                                  # 0.01 안이면 다시 써요
    assert F.kr_d1_same_day(cur, prev, D, D1)[0]["005380"] == 5.01
    prev["stocks"][2]["d1"] = 5.03
    assert "005380" not in F.kr_d1_same_day(cur, prev, D, D1)[0]


def test_fetch_korea_tries_the_same_day_d1_only_after_the_163_path_says_day():
    import inspect
    src = inspect.getsource(F.fetch_korea)
    a = src.index("d1_map, base_ok, d1_base = kr_d1_base_day(listing, prev, want_prev)")
    b = src.index('same_d1 = kr_d1_same_day(listing, prev, px_date, want_prev) if d1_base.get("why") == "day" else None')
    c = src.index("d1_map, base_ok, d1_base = same_d1")
    d = src.index("loud, txt = d1_base_note(d1_base)")
    assert a < b < c < d
    assert "same 1" in F.UNITS["d1Base"]


def test_the_same_day_hold_now_sees_lost_d1_and_the_fixed_run_passes_it():
    """#161 리뷰 S5: 같은 종가인데 d1 을 잃은 국내 종목은 잃은 것 (이름과 함께 · 보류). 위 고침이 있는 실행은 잃지 않아요."""
    import test_d1_after_gap as G
    cur = G.cur20()
    pub20 = same_day_pub20(cur)
    nt = F.kr_no_trade_plan(cur, max_share=1.0)[0]

    def file_of(r):
        st = []
        for c, p in F._official_map(cur).items():
            s = {"t": c, "cls": "kr", "price": p}
            if c in r["d1"]:
                s["d1"] = r["d1"][c]
            if c in nt:
                s.update(noTrade=True, d1Why="noTrade")
            elif c in r["why"]:
                s["d1Why"] = r["why"][c]
            st.append(s)
        return {"pxDate": "2026-11-20", "usPxDate": "2026-11-20", "pxSrc": {"px": LISTING, "date": "2026-11-20"}, "stocks": st}
    good = file_of(run_d1(cur, pub20))
    assert P.lost_stocks(good, pub20)["d1"] == [] and P.same_day_decision(LISTING, FB, good, pub20).kind == "same"
    bad = file_of(G.run_day(cur, pub20))                                           # 이 고침 전의 실행 (모든 d1 빈 칸)
    d = P.same_day_decision(LISTING, FB, bad, pub20)
    assert d.hold is True and d.kind == "loss" and "같은 종가인데 d1 을 잃은 국내 11" in d.why and "005930 (d1 빈 칸)" in d.why


def test_kr_d1_lost_counts_only_same_close_rows_that_lost_d1():
    prev = pub(kr=KR5)
    for s in prev["stocks"]:
        s["d1"] = 1.5
    cur = copy.deepcopy(prev)
    by = {s["t"]: s for s in cur["stocks"]}
    by["100010"].pop("d1")                                                         # 같은 종가 · d1 없음 → 잃음
    by["100020"].pop("d1")
    by["100020"]["price"] = 1010.0                                                 # 종가가 다름 → d1 도 다를 수 있어 세지 않아요
    by["100030"].pop("d1")
    by["100030"].update(noTrade=True, d1Why="noTrade")                             # 거래 없음 → 까닭이 있어요
    by["100040"]["d1"] = float("nan")                                              # 숫자가 아님 → 잃음
    assert P.kr_d1_lost(cur, prev) == ["100010", "100040"]
    d = P.same_day_decision(FB, FB, cur, prev)
    assert d.kind == "loss" and "같은 종가인데 d1 을 잃은 국내 2" in d.why and "100010 (d1 빈 칸)" in d.why
    cur["stocks"].append(dict(by["100050"]))                                       # 같은 코드가 두 번 → 어느 값인지 몰라 잃은 것으로
    assert "100050" in P.kr_d1_lost(cur, prev)
    # 지난 발행본에 d1 이 없던 종목 · 마지막 확인 종가 행 · 이 실행에 없는 종목은 여기서 세지 않아요 (없는 종목은 kr)
    prev2 = pub(kr=KR5, own=["100060"])
    cur2 = pub(kr=KR5[:4])
    assert P.kr_d1_lost(cur2, prev2) == [] and P.lost_stocks(cur2, prev2)["kr"] == ["100050"]
    assert P.kr_d1_lost(None, prev) == [] and P.kr_d1_lost(cur, None) == []


def test_a_us_close_that_drops_back_to_an_older_date_is_lost():
    """#161 리뷰 S3 (rev161/repro_us.py): 미국 기준일이 같은데 그 날짜 종가였던 미국 종목이 자기 날짜 (야후의 옛 봉 pxd · 마지막 확인 종가 pxc) 로
    바뀌면 잃은 것. 미국 기준일이 새로우면 마지막 확인 종가로 넘어가는 것이 정상이에요."""
    prev = pub(kr=KR5, others=US2)
    cur = pub(kr=KR5, others=US2)
    cur["stocks"][-2]["pxd"] = "2026-11-19"                                        # AAPL: 야후의 옛 봉
    lost = P.lost_stocks(cur, prev)
    assert lost["us"] == ["AAPL"] and lost["other"] == []
    d = P.same_day_decision(FB, FB, cur, prev)
    assert d.kind == "loss" and "미국 기준일 종가가 옛 날짜로 1" in d.why and "미국 AAPL (옛 날짜로)" in d.why
    cur["stocks"][-2]["pxc"] = True                                                # 마지막 확인 종가로 옮겨도 같아요
    assert P.lost_stocks(cur, prev)["us"] == ["AAPL"]
    # 미국 기준일이 새로우면: 그 종목이 지난 기준일 종가로 남는 것은 정상 (잃음 아님)
    old = pub(kr=KR5, others=US2, us="2026-11-19")
    newer = pub(kr=KR5, others=US2, us="2026-11-20")
    newer["stocks"][-2].update(pxd="2026-11-19", pxc=True)
    assert P.lost_stocks(newer, old)["us"] == [] and P.same_day_decision(FB, FB, newer, old).kind == "publish"
    # 지난 발행본이 자기 날짜였던 종목: 그 날짜 종가로 돌아오거나 그대로면 잃음 아님
    p2 = pub(kr=KR5, others=US2)
    p2["stocks"][-1].update(pxd="2026-11-19", pxc=True)
    assert P.lost_stocks(pub(kr=KR5, others=US2), p2)["us"] == [] and P.lost_stocks(copy.deepcopy(p2), p2)["us"] == []
    # 진짜 미국 단계 (us_own_close_carry): 지난 발행본의 그날 종가를 다시 쓰지 못하면 (d1 없음 → bad) 야후의 옛 봉 → 잃음
    prev3 = {"usPxDate": "2026-11-20", "pxDate": "2026-11-20", "stocks": [{"t": "ZZZ", "cls": "us", "price": 50.0}, {"t": "AAA", "cls": "us", "price": 10.0, "d1": 1.0}]}
    ybar = {"ZZZ": {"t": "ZZZ", "cls": "us", "price": 48.0, "pxd": "2026-11-19"}}
    carried, same, drop = F.us_own_close_carry(prev3, {"ZZZ": "bar", "AAA": "bar"}, D20, ["2026-11-18", "2026-11-19", "2026-11-20"], ybar=ybar)
    assert carried == [] and [s["t"] for s in same] == ["AAA"] and drop == {"ZZZ": "bad"}
    cur3 = {"usPxDate": "2026-11-20", "pxDate": "2026-11-20", "stocks": [ybar["ZZZ"]] + same}
    assert P.lost_stocks(cur3, prev3)["us"] == ["ZZZ"]


# ── 11. #161 리뷰 (3차) ─────────────────────────────────────
def test_a_quiet_run_never_lets_the_gate_see_an_old_publish():
    """A-M1 (rev161a/monday_quiet.py): 쉬는 실행은 data.json 을 새로 쓰지 않아 관문이 발행본을 그대로 봐요 — 'publishedAt 12시간 이내' 가 실패하지
    않게, 발행본이 관문 한도 − 1시간보다 오래됐으면 쉬지 않아요. 월요일 (토요일 아침 발행본) · 연휴 뒤 · 같은 날 오후 늦게."""
    green = lambda r: True                                                         # noqa: E731
    assert F.KR_RERUN_QUIET_PUB_AGE == dt.timedelta(hours=V.PUBLISHED_MAX_HOURS - 1)
    # 월요일: 금요일 데이터 (pxDate 11-20) 를 토요일 06:52 에 발행 · 월요일 10:53 다시 돈 실행이 더 얻은 것 없음 (11:30 기록) → 13:37 은 돌아요
    sat = dict(pub(kr=KR5, us="2026-11-20"), publishedAt="2026-11-21T06:52:00+09:00")
    st = F.kr_rerun_state(sat, dict(sat), kst(2026, 11, 23, 11, 30), 2474, 2474, env=LIVE_ENV)
    for hh, mm in ((13, 37), (14, 25)):
        assert F.kr_rerun_throttle(st, sat, kst(2026, 11, 23, hh, mm), run_ok=green) is None
    # 연휴 뒤: 12-24 데이터를 12-25 06:50 발행 · 12-26 08:40 기록 → 10:53 은 돌아요
    xmas = dict(pub(px="2026-12-24", kr=KR5, us="2026-12-24"), publishedAt="2026-12-25T06:50:00+09:00")
    st2 = F.kr_rerun_state(xmas, dict(xmas), kst(2026, 12, 26, 8, 40), 10, 10, env=LIVE_ENV)
    assert F.kr_rerun_throttle(st2, xmas, kst(2026, 12, 26, 10, 53), run_ok=green) is None
    # 같은 날: 06:52 발행 → 10:53 기록 → 13:37 (6.75시간) 쉬어요 · 발행본이 11시간 넘으면 (예: 02:00 발행 → 13:37) 돌아요 · 날짜를 읽을 수 없으면 돌아요
    today = dict(pub(kr=KR5, us="2026-11-20"), publishedAt="2026-11-21T06:52:00+09:00")
    st3 = F.kr_rerun_state(today, dict(today), kst(2026, 11, 21, 10, 53), 5, 5, env=LIVE_ENV)
    assert F.kr_rerun_throttle(st3, today, kst(2026, 11, 21, 13, 37), run_ok=green)
    assert F.kr_rerun_throttle(st3, dict(today, publishedAt="2026-11-21T02:30:00+09:00"), kst(2026, 11, 21, 13, 37), run_ok=green) is None
    for bad in (None, "", "어제", "2026-11-21T06:52:00"):                         # 없음 · 읽을 수 없음 · 시간대 없음
        assert F.kr_rerun_throttle(st3, dict(today, publishedAt=bad), kst(2026, 11, 21, 13, 37), run_ok=green) is None


def test_a_single_source_close_that_disagrees_with_the_published_close_is_not_reused():
    """A-S2: 같은 날 다시 쓰기는 지금 두 출처가 다른 종목 (diffT) 만 막았어요. 이제 한 출처만 종가를 준 종목 (야후 빈 칸 → 다음 종가 · 다음 행 없음 → 야후
    종가) 이 지난 발행본의 종가와 다르면 그 종가를 다시 쓰지 않아요 (잃은 종목 · 크게 · 그 실행은 발행하지 않아요)."""
    px = dt.date(2026, 11, 20)
    prev = {"pxDate": "2026-11-20", "publishedAt": "2026-11-21T06:40:00+09:00", "krSeries": {"jump": []},
            "stocks": [kr("600010", 7300.0), kr("600020", 5000.0), kr("600030", 4000.0)]}
    unconf = {c: ("", "conf") for c in ("600010", "600020", "600030")}
    src = {"fb": {"diffT": []}, "_one": {"600010": ("daum", 7250.0), "600020": ("yahoo", 5000.0)}}
    reused, _, lost, rec = F.kr_same_day_reuse(prev, unconf, set(), px, src)
    assert [r["t"] for r in reused] == ["600020", "600030"] and lost == {"600010": "clash1"}
    assert rec["lost"] == 1 and any("600010" in x and "한 출처만 종가를 줬는데 지난 발행본의 종가와 다름" in x for x in rec["lostEx"])
    # 한 출처 종가를 만드는 곳: 야후 빈 칸 → 다음 종가 · 다음 행 없음 / 믿을 수 없음 → 야후 종가 · 둘 다 없으면 없음
    st = {"noYahoo": ["A"], "noDaum": ["B"], "bad": ["C"]}
    daum = {"A": {px: {"tradePrice": 1000}}, "C": {px: {"tradePrice": 3}}}
    yahoo = {"B": {px: 2000.0}, "C": {px: 3000.0}}
    assert F.kr_fb_one_source(px, st, daum, yahoo) == {"A": ("daum", 1000.0), "B": ("yahoo", 2000.0), "C": ("yahoo", 3000.0)}
    assert F.kr_fb_one_source(px, {"noYahoo": ["A"]}, {"A": {}}, {}) == {}
    # 내부 칸이라 data.json 에 쓰지 않아요 (px_src_final 이 빼요)
    fin = F.px_src_final({"px": FB, "date": "2026-11-20", "fb": {"conf": 1}, "_one": {"A": ("daum", 1.0)}}, [])
    assert "_one" not in fin and fin["px"] == FB
    json.dumps(fin, allow_nan=False)


def test_the_pipeline_carries_single_source_closes_to_the_reuse_step():
    """A-S2 (진짜 길): kr_fallback_days 가 그날 집계에 _one 을 남기고 kr_second_source 가 pxSrc._one 으로 넘겨요 (data.json 에는 없어요)."""
    import inspect
    import test_kr_two_source as T2
    D18 = dt.date(2026, 11, 18)
    out, _ = _fb_run(T2.listing("2026-11-18_1452"), D18, no_yahoo=("047400",))
    st = out[D18][1]
    assert "047400" in st["noYahoo"] and st["_one"]["047400"][0] == "daum" and st["_one"]["047400"][1] > 0
    assert 'src["_one"] = dict(st.get("_one") or {})' in inspect.getsource(F.kr_second_source)
    assert "_one" not in F.px_src_counts(st)


def test_dart_skips_calls_only_when_the_cache_covers_the_live_publish(tmp_path, monkeypatch):
    """A-S3: 같은 날 다시 하는 실행은 불러온 DART 보관본이 발행본을 만든 실행 (또는 그 뒤) 의 값일 때만 DART 를 부르지 않아요 (meta.dartAt ≥ 발행본
    publishedAt). 아니면 예전처럼 불러요 (보관본에 있는 것은 다시 받지 않아요 — 빈 보관본이 아니라 전체 DART 실행이 아니에요). 빈 보관본이면 부르지 않고 멈춰요."""
    import inspect
    live = {"publishedAt": "2026-11-21T06:40:12+09:00"}
    assert F.dart_cache_covers({"dartAt": "2026-11-21T06:40:12+09:00"}, live)[0] is True
    assert F.dart_cache_covers({"dartAt": "2026-11-21T10:53:00+09:00"}, live)[0] is True        # 그 뒤 실행의 값 (더 새)
    ok, why = F.dart_cache_covers({"dartAt": "2026-11-20T06:41:00+09:00"}, live)              # 아침 저장이 실패해 어제 보관본
    assert ok is False and "앞의 값" in why
    for meta in ({}, {"dartAt": None}, {"dartAt": "어제"}, {"dartAt": "2026-11-21T06:40:12"}, None):
        assert F.dart_cache_covers(meta, live)[0] is False
    assert F.dart_cache_covers({"dartAt": "2026-11-21T06:40:12+09:00"}, {})[0] is False
    # 적는 곳: DART 가 멈추지 않은 실행만 (멈추면 적지 않고 크게)
    c = F.DartClient("시험키아님", path=str(tmp_path / "none.json.gz"))
    assert F.dart_cache_mark(c, "2026-11-21T10:53:00+09:00") is True and c.meta["dartAt"] == "2026-11-21T10:53:00+09:00"
    c.down = "ConnectionError"
    assert F.dart_cache_mark(c, "2026-11-21T13:37:00+09:00") is False and c.meta["dartAt"] == "2026-11-21T10:53:00+09:00"
    body = inspect.getsource(F.main)
    i_empty, i_cov, i_set = body.index("if client.started_empty:"), body.index("covers, why_cov = dart_cache_covers(client.meta, prev)"), \
        body.index("client.no_call = why_sd")
    assert i_empty < i_cov < i_set and body.count("dart_cache_mark(client, published_at)") == 2
    assert "전체 DART 실행이라" in body[i_empty:i_cov] and "raise RuntimeError" in body[i_empty:i_cov]


def test_evaluate_compares_with_the_site_and_repairs_a_half_finished_publish():
    """B-M1 (rev161b/repro.py C): 지난 발행본은 사이트의 발행본 (data 브랜치). main HEAD 가 그와 다르면 (지난 'data 브랜치에 올리기' 실패) '같은 날 ·
    더 낫지 않음' 으로 보류하지 않고 발행해 data 브랜치를 고쳐요 (잃는 것이 있으면 그대로 보류). data 브랜치를 읽지 못했으면 main HEAD 와 같은 날이거나
    모를 때 stop, 새 날이면 바닥만."""
    now = kst(2026, 11, 21, 10, 53)
    live = pub(px="2026-11-19", kr=KR5, others=US2, us="2026-11-19")           # data 브랜치 (어제)
    head = pub(kr=KR5, own=["100060"], others=US2)                              # main (오늘 · data 브랜치에 오르지 못함)
    d, _ = P.evaluate(copy.deepcopy(head), "data.json", live, "data 브랜치", now, head=head)
    assert d.hold is False and d.kind == "publish"                               # 사이트와 비교하면 새 날 → 발행 (예전: main 과 같은 날 · 건강한 보류)
    live2 = dict(pub(kr=KR5, own=["100060"], others=US2), publishedAt="2026-11-21T06:40:00+09:00")   # data 브랜치도 오늘 06:40 · main 은 10:53
    head2 = dict(pub(kr=KR5 + ["100060"], others=US2), publishedAt="2026-11-21T10:53:00+09:00")
    d, lines = P.evaluate(copy.deepcopy(live2), "data.json", live2, "data 브랜치", now, head=head2)
    assert d.hold is False and d.kind == "publish" and d.loud and "data 브랜치를 고쳐요" in d.why
    assert any("지난 발행이 data 브랜치에 다 오르지 못했어요" in ln for ln in lines)
    d, _ = P.evaluate(copy.deepcopy(live2), "data.json", live2, "data 브랜치", now, head=copy.deepcopy(live2))
    assert d.kind == "same" and d.hold is True                                   # 다 올랐으면 예전 그대로 (건강한 보류)
    d, _ = P.evaluate(pub(kr=KR5, others=US2), "data.json", live2, "data 브랜치", now, head=head2)
    assert d.kind == "loss"                                                      # 잃는 것이 있으면 그대로 보류
    # data 브랜치를 읽지 못함
    d, _ = P.evaluate(copy.deepcopy(head2), "data.json", None, "받지 못함", now, head=head2, live_failed=True)
    assert d.hold is True and d.kind == "stop" and "main HEAD 와 같은 한국 기준일" in d.why
    d, _ = P.evaluate(copy.deepcopy(head2), "data.json", None, "받지 못함", now, head=None, live_failed=True)
    assert d.kind == "stop" and "main HEAD 도 읽지 못함" in d.why
    d, _ = P.evaluate(pub(px="2026-11-21", kr=KR5, others=US2, us="2026-11-21"), "data.json", None, "받지 못함", now, head=head2, live_failed=True)
    assert d.hold is False and d.loud is True and d.kind == "unknown"


def test_read_live_uses_the_same_path_as_already_published(monkeypatch):
    calls = []

    def fake(run=None):
        calls.append(run)
        return {"pxDate": "2026-11-20"}
    monkeypatch.setattr(A, "read_published", fake)
    d, note = P.read_live()
    assert d == {"pxDate": "2026-11-20"} and "data 브랜치" in note and calls == [None]
    monkeypatch.setattr(A, "read_published", lambda run=None: None)
    assert P.read_live() == (None, "data 브랜치의 data.json 을 받지 못했어요")


def test_a_newer_us_date_is_not_blocked_by_us_stocks_leaving_the_list():
    """B-S3 (rev161b/repro.py B): 한국 휴장일 (같은 한국 기준일) 에 미국 기준일이 새로우면, 미국 종목이 목록에서 빠진 것 (S&P 500 편출 · 마지막 확인 종가가
    5 미국 거래일을 넘어 잠시 뺌) 으로 보류하지 않아요 (그러면 설 · 추석 동안 미국 종가가 멈춰요). 펀드 · 금 · 채권은 정해진 목록이라 그대로 세요."""
    prev = pub(px="2027-02-05", kr=KR5, others=US2 + ["XYZ"], us="2027-02-05")
    cur = pub(px="2027-02-05", kr=KR5, others=US2, us="2027-02-08")
    d, _ = P.evaluate(cur, "data.json", prev, "data 브랜치", kst(2027, 2, 9, 6, 43))
    assert d.hold is False and d.kind == "publish" and "미국 목록에서 빠진 1종목은 새 미국 기준일이라 세지 않아요: XYZ" in d.why and d.loud
    same_us = pub(px="2027-02-05", kr=KR5, others=US2, us="2027-02-05")       # 미국 기준일이 같으면 예전처럼 잃음
    assert P.evaluate(same_us, "data.json", prev, "data 브랜치", kst(2027, 2, 9, 6, 43))[0].kind == "loss"
    prev["stocks"].append({"t": "AGG", "cls": "bond", "price": 100.0})
    d, _ = P.evaluate(cur, "data.json", prev, "data 브랜치", kst(2027, 2, 9, 6, 43))
    assert d.kind == "loss" and "bond AGG" in d.why                                # 채권 ETF 가 빠지면 그대로 잃음
    assert P.same_day_decision(FB, FB, pub(kr=KR5[:4], others=US2, us="2027-02-08"), pub(kr=KR5, others=US2, us="2027-02-05")).kind == "loss"


def test_the_same_day_log_line_never_stops_the_decision_and_summaries_say_held():
    """nit (rev161b/repro.py D): 로그 줄의 종목 수 셈이 실패해도 같은 날 규칙이 판단해요 (예전: 그 오류가 판단 전체를 멈춰 보류 없이 발행). 보류한 '비교할
    수 없음' 은 요약에 '발행' 으로 적지 않아요."""
    prev = pub(kr=KR5, others=US2)
    prev["stocks"].append("junk")
    d, lines = P.evaluate(pub(kr=KR5, others=US2), "d", prev, "g", kst(2026, 11, 21, 10, 53))
    assert d.kind == "unknown" and d.hold is True and any("그 날짜 종가 국내 ? → 이 실행 5" in ln for ln in lines)
    assert "보류 — 비교할 수 없어 발행하지 않아요" in P.summary_md(d, lines, False)
    assert "멈춤 —" in P.summary_md(P.Decision(True, True, "x", "stop"), lines, False)
    assert "발행 (보류 아님 · 판단을 다 하지 못했어요" in P.summary_md(P.Decision(False, True, "x", "error"), lines, False)


def test_watchdog_held_run_suffix_names_only_the_neutral_kinds():
    import inspect
    src = inspect.getsource(W)
    assert "같은 날 더 낫지 않음 · 셈하지 않아요" not in src and "바닥 아래 · 날짜가 뒤로 감 · 종목을 잃음 · 비교할 수 없음 · 쉼 · 셈하지 않아요" in src


# ── 12. #161 리뷰 (4차) ─────────────────────────────────────
def test_the_repair_rule_needs_main_head_to_be_the_newer_publish():
    """리뷰 4차 1 (rev161c/probe1.py 2): main HEAD 가 data 브랜치보다 '앞' (publishedAt 이 뒤) 일 때만 '같은 날 · 더 낫지 않음' 을 발행으로 바꿔요. HEAD 가
    더 옛 발행 (가지의 시험 실행 · 앞 실행 뒤에 줄 선 손 실행) 이면 예전처럼 보류 — 발행하면 git pull --rebase 충돌로 빨간 실행이 돼요. 읽을 수 없으면 고치지 않아요."""
    now = kst(2026, 11, 21, 10, 55)
    live = dict(fb_data("2026-11-20", 2740), publishedAt="2026-11-21T06:41:00+09:00")
    stale = dict(fb_data("2026-11-19", 2740), publishedAt="2026-11-20T06:41:00+09:00")
    d, lines = P.evaluate(fb_data("2026-11-20", 2740), "data.json", live, "data 브랜치", now, head=stale)
    assert d.kind == "same" and d.hold is True and "data 브랜치를 고쳐요" not in d.why
    assert not any("다 오르지 못했어요" in ln for ln in lines)
    newer = dict(fb_data("2026-11-20", 2741), publishedAt="2026-11-21T10:53:00+09:00")
    assert P.evaluate(fb_data("2026-11-20", 2740), "data.json", live, "data 브랜치", now, head=newer)[0].kind == "publish"
    for bad in (None, "어제", "2026-11-21T10:53:00"):                               # 없음 · 읽을 수 없음 · 시간대 없음 → 고치지 않아요
        h = dict(newer, publishedAt=bad)
        assert P.evaluate(fb_data("2026-11-20", 2740), "data.json", live, "data 브랜치", now, head=h)[0].kind == "same"
    assert P._newer({"publishedAt": "2026-11-21T10:53:00+09:00"}, {"publishedAt": "2026-11-21T01:53:00+00:00"}) is False   # 같은 시각 (UTC)


def test_a_dry_run_never_marks_the_dart_cache(tmp_path):
    """리뷰 4차 2: 시험 실행의 보관본도 main 의 캐시로 저장돼요 — dartAt 을 적지 않아요 (실제 실행의 표시만 믿어요 · kr_rerun_state 와 같게)."""
    c = F.DartClient("시험키아님", path=str(tmp_path / "none.json.gz"))
    c.meta["dartAt"] = "2026-11-21T06:40:00+09:00"
    assert F.dart_cache_mark(c, "2026-11-21T06:45:00+09:00", env={"DRY_RUN": "true"}) is False
    assert c.meta["dartAt"] == "2026-11-21T06:40:00+09:00"
    assert F.dart_cache_mark(c, "2026-11-21T10:53:00+09:00", env={"DRY_RUN": ""}) is True and c.meta["dartAt"] == "2026-11-21T10:53:00+09:00"


def test_a_us_fund_row_leaving_still_counts_with_a_newer_us_date():
    """리뷰 4차 3 (probe1 3): 새 미국 기준일에 세지 않는 것은 미국 '종목' 만이에요 — 379800 (KODEX 미국S&P500 · cls us · fund) 같은 펀드 행은 정해진
    목록이라 빠지면 그대로 잃음 (RUNBOOK 'Funds, gold and bond rows … still count')."""
    prev = fb_data("2026-11-20", 2740, us="2026-11-19", stocks=[{"t": "005930", "cls": "kr", "price": 50000.0},
                                                                {"t": "379800", "cls": "us", "fund": True, "price": 20000.0},
                                                                {"t": "AAPL", "cls": "us", "price": 1.0}, {"t": "XYZ", "cls": "us", "price": 1.0}])
    cur = fb_data("2026-11-20", 2740, us="2026-11-20", stocks=[{"t": "005930", "cls": "kr", "price": 50000.0}, {"t": "AAPL", "cls": "us", "price": 1.0}])
    d = P.same_day_decision(FB, FB, cur, prev)
    assert d.kind == "loss" and d.hold is True and "us 379800" in d.why and "XYZ" not in d.why
    cur["stocks"].append({"t": "379800", "cls": "us", "fund": True, "price": 20100.0})
    d = P.same_day_decision(FB, FB, cur, prev)
    assert d.kind == "publish" and "빠진 1종목" in d.why and "XYZ" in d.why


def test_a_korean_holiday_morning_compares_with_main_head_when_the_data_branch_is_unreadable():
    """리뷰 4차 (선택): 같은 한국 기준일 · 새 미국 기준일인데 data 브랜치를 읽지 못하면 main HEAD 와 비교해요 (예전: stop · 빨간 실행으로 미국 종가가 막혔어요).
    같은 미국 기준일이면 그대로 stop."""
    now = kst(2026, 11, 21, 6, 45)
    head = fb_data("2026-11-20", 2740, us="2026-11-20")
    d, lines = P.evaluate(fb_data("2026-11-20", 2740, us="2026-11-21"), "data.json", None, "받지 못함", now, head=head, live_failed=True)
    assert d.kind == "publish" and d.hold is False and any("main HEAD 의 data.json 과 비교해요" in ln for ln in lines)
    d, _ = P.evaluate(fb_data("2026-11-20", 2740, us="2026-11-21", stocks=[{"t": "000660", "cls": "kr", "price": 1.0}]), "data.json", None,
                      "받지 못함", now, head=head, live_failed=True)
    assert d.kind == "loss"                                                       # HEAD 와 비교해 잃는 것은 그대로 봐요
    d, _ = P.evaluate(fb_data("2026-11-20", 2740, us="2026-11-20"), "data.json", None, "받지 못함", now, head=head, live_failed=True)
    assert d.kind == "stop"
