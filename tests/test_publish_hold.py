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
    bad = pub(kr=KR5, conf=2700, noYahoo=46)
    bad["pxSrc"]["fb"]["conf"] += 5
    d, lines = P.evaluate(bad, "data.json", prev, "git", now)
    assert d.hold is False and d.loud is True and lines[1].startswith("!! 오늘:")
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
    hold = P.main(list(argv), now_fn=lambda: now, cur_reader=lambda p: (cur, p), prev_reader=prev_reader)
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


def test_main_never_holds_when_it_breaks(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    def boom(path):
        raise RuntimeError("읽기 실패")
    assert P.main([], now_fn=lambda: kst(2026, 11, 21, 6, 41), cur_reader=boom) is False
    log = capsys.readouterr().out
    assert out.read_text().splitlines()[-1] == "hold=false"
    assert "!! 발행 판단이 오류로 멈췄어요" in log and log.count("::warning title=발행 판단 확인 못 함 (보류 없이 판단)::") == 1
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
    """단계의 bash 를 진짜 publish_hold.py · git 으로: 직전 발행본은 커밋된 data.json (HEAD), 오늘 것은 작업 폴더의 data.json."""
    repo = tmp_path / "repo"
    repo.mkdir()
    genv = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    (repo / "data.json").write_text(json.dumps(pub(kr=KR5, own=["100060"], others=US2, conf=2716, noYahoo=30)))   # 06:40 발행본
    for cmd in (["git", "init", "-q"], ["git", "add", "data.json"], ["git", "commit", "-q", "-m", "prev"]):
        subprocess.run(cmd, cwd=repo, env=genv, check=True, capture_output=True)
    run = next(s for s in update_steps() if s.get("name") == HOLD_STEP)["run"]
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    py = bin_ / "python"
    py.write_text(f'#!/bin/bash\n[ "$1" = "tools/publish_hold.py" ] || exit 9\nshift\n'
                  f'exec "{sys.executable}" "{os.path.join(ROOT, "tools", "publish_hold.py")}" "$@"\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    cases = ((pub(kr=KR5 + ["100060"], others=US2, conf=2720, noYahoo=26), "hold=false", "publish"),   # 같은 날 · 더 나음 → 발행
             (pub(kr=KR5, own=["100060"], others=US2, conf=2716, noYahoo=30), "hold=true", "same"),     # 같은 날 · 같음 → 발행 안 함 (건강)
             (pub(kr=KR5, others=US2, conf=2720, noYahoo=26), "hold=true", "loss"),                     # 같은 날 · 마지막 확인 종가 종목을 잃음
             (pub(px="2026-11-21", us="2026-11-21", conf=2526, noYahoo=220), "hold=true", "floor"),     # 새 날 · 바닥 아래 → 보류
             (pub(px="2026-11-21", us="2026-11-21", kr=KR5, others=US2), "hold=false", "publish"))      # 새 날 · 바닥 위 → 발행
    for cur, want, kind in cases:
        (repo / "data.json").write_text(json.dumps(cur))
        out = tmp_path / "out.txt"
        out.write_text("")
        e = {**genv, "PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "BOOTSTRAP": "", "PREV_REF": "", "DRY_RUN": ""}
        e.pop("GITHUB_ACTIONS", None)
        e.pop("GITHUB_STEP_SUMMARY", None)
        r = subprocess.run(["bash", "-e", "-c", run], cwd=repo, env=e, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        lines = out.read_text().splitlines()
        assert lines[-1] == want and f"kind={kind}" in lines, (cur["pxDate"], r.stdout, r.stderr)
        assert ("neutral=true" in lines) is (kind in ("floor", "loss")), lines                # 표시 단계: 감시에 중립인 보류만
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, env=genv, capture_output=True, text=True).stdout
    assert len(log.strip().splitlines()) == 1                                     # 단계는 커밋하지 않아요


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
def _fb_run(uni, day, cached=None, keep=None, asked=None, no_yahoo=()):
    """test_kr_two_source 의 실제 응답 픽스처로 kr_fallback_days 를 돌려요. asked: 묻는 종목을 단계마다 적어요 {"daum", "yahoo", "fill"}.
    no_yahoo: 야후가 그날 종가를 주지 않는 종목 (확인 못 한 종목을 만들어요)."""
    import test_kr_two_source as T2
    asked = asked if asked is not None else {}

    def fetch_daum(codes, n):
        asked.setdefault("daum", []).extend(codes)
        return {c: v for c, v in T2.daum().items() if c in codes}, []

    def fetch_yahoo(cm, s, e):
        asked.setdefault("yahoo", []).extend(cm)
        return {c: {k: v for k, v in d.items() if k != day} for c, d in T2.yahoo().items() if c in cm and c not in no_yahoo}, 0

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
    """리뷰 5: 같은 날 다시 도는 실행은 DART 를 부르지 않아요 (하루 한도 20,000 · 다시 도는 실행마다 670 ~ 800회 × 7 + 전체 DART 날)."""
    def boom(*a, **k):
        raise AssertionError("DART 를 불렀어요")
    monkeypatch.setattr(F.requests, "get", boom)
    c = F.DartClient("시험키아님", path=str(tmp_path / "none.json.gz"))
    c.no_call = "같은 날 다시 도는 실행 (시험)"
    assert c.get("list.json", {"corp_code": "00126380"}) is None and c.get("elestock.json", {"corp_code": "1"}) is None
    assert c.blocked == 2 and "DART 를 부르지 않았어요 (막은 조회 2회" in c.summary()
    body = __import__("inspect").getsource(F.main)
    assert "client.no_call = why_sd" in body and "load_morning_disc()" in body
    i_reuse, i_fetch = body.index("if prev_disc is not None:"), body.index('disc = ph.run("공시", fetch_disclosures')
    assert i_reuse < i_fetch                                                      # 아침 발행본이 있으면 공시 단계를 부르지 않아요


def test_same_day_rerun_and_the_morning_disc():
    today = dt.date(2026, 11, 21)
    prev = dict(pub(kr=KR5), publishedAt="2026-11-21T06:52:00+09:00")
    src = {"px": FB}
    assert F.kr_same_day_rerun(prev, src, dt.date(2026, 11, 20), today)[0] is True
    assert F.kr_same_day_rerun(prev, src, dt.date(2026, 11, 21), today)[0] is False       # 새 기준일
    assert F.kr_same_day_rerun(dict(prev, publishedAt="2026-11-20T23:59:00+09:00"), src, dt.date(2026, 11, 20), today)[0] is False   # 어제 발행
    assert F.kr_same_day_rerun(prev, {"px": LISTING}, dt.date(2026, 11, 20), today)[0] is False
    assert F.kr_same_day_rerun(listing_data("2026-11-20"), src, dt.date(2026, 11, 20), today)[0] is False


def test_load_morning_disc(tmp_path):
    p = tmp_path / "disc.json"
    p.write_text(json.dumps({"insider": [{"t": "005930"}], "nps": [], "issue": []}))
    d, why = F.load_morning_disc(str(p))
    assert d["insider"] == [{"t": "005930"}] and "내부자 1건" in why
    p.write_text("{}")
    assert F.load_morning_disc(str(p))[0] is None
    assert F.load_morning_disc(str(tmp_path / "없음.json"))[0] is None


def test_a_rerun_that_gained_nothing_quiets_later_starts_for_three_hours():
    """리뷰 6: 같은 날 다시 돌아 그 날짜 종가 국내 종목을 늘리지 못하면, 3시간 안의 정해진 시각 · 바깥 타이머 실행은 데이터를 모으지 않아요."""
    prev = dict(pub(kr=KR5, us="2026-11-20"), publishedAt="2026-11-21T06:52:00+09:00")
    state = F.kr_rerun_state(prev, {"pxDate": "2026-11-20", "usPxDate": "2026-11-20"}, kst(2026, 11, 21, 9, 30), 2474, 2474)
    assert state["gain"] == 0 and state["day"] == "2026-11-21"
    why = F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0))
    assert why and "09:30 KST" in why and "90분 남음" in why
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 12, 30)) is None     # 3시간 지남
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 21, 11, 0), auto=False) is None   # 손으로 누른 실행은 늘 돌아요
    assert F.kr_rerun_throttle(dict(state, gain=3), prev, kst(2026, 11, 21, 11, 0)) is None  # 늘었으면 쉬지 않아요
    assert F.kr_rerun_throttle(dict(state, gain=None), prev, kst(2026, 11, 21, 11, 0)) is None
    assert F.kr_rerun_throttle(state, dict(prev, usPxDate="2026-11-21"), kst(2026, 11, 21, 11, 0)) is None   # 발행본 날짜가 바뀜
    assert F.kr_rerun_throttle(state, prev, kst(2026, 11, 22, 9, 40)) is None      # 다음 날
    late = F.kr_rerun_state(prev, {"pxDate": "2026-11-20", "usPxDate": "2026-11-20"}, kst(2026, 11, 21, 14, 0), 2474, 2474)
    assert F.kr_rerun_throttle(late, prev, kst(2026, 11, 21, 15, 31)) is None      # 15:30 뒤에는 새 거래일이 끝날 수 있어 쉬지 않아요
    assert F.kr_rerun_state(prev, {"pxDate": "2026-11-21", "usPxDate": "2026-11-21"}, kst(2026, 11, 21, 9, 30), 2474, 2474)["gain"] is None
    assert F.kr_rerun_throttle(None, prev, kst(2026, 11, 21, 11, 0)) is None


def test_main_skips_collecting_when_quiet(monkeypatch, capsys):
    prev = dict(pub(kr=KR5, us="2026-11-20"), publishedAt="2026-11-21T06:52:00+09:00")
    state = F.kr_rerun_state(prev, {"pxDate": "2026-11-20", "usPxDate": "2026-11-20"}, kst(2026, 11, 21, 9, 30), 5, 5)

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return kst(2026, 11, 21, 10, 53).astimezone(tz) if tz else kst(2026, 11, 21, 10, 53)
    monkeypatch.setattr(F.dt, "datetime", Clock)
    monkeypatch.setattr(F, "read_prev_data", lambda: prev)
    monkeypatch.setattr(F, "kr_rerun_state_load", lambda: state)
    monkeypatch.setattr(F, "load_industry_tables", lambda: (_ for _ in ()).throw(AssertionError("데이터를 모으기 시작했어요")))
    monkeypatch.setenv("BAEPSAE_AUTO_RUN", "1")
    monkeypatch.setenv("DART_MODE", "cache")
    assert F.main() is None
    assert "3시간이 지나기 전이라" in capsys.readouterr().out


def test_open_closes_count_only_what_a_re_ask_can_change():
    """리뷰 6: 두 출처가 다른 종목 · 야후가 싣지 않는 종목은 하루 종일 그대로라 '남은 것' 으로 세지 않아요 (fb.open · fb.knx.open)."""
    import test_kr_two_source as T2
    D18 = dt.date(2026, 11, 18)
    out, _ = _fb_run(T2.listing("2026-11-18_1452"), D18, no_yahoo=("047400", "090460"))
    st = out[D18][1]
    c = F.px_src_counts(st)
    assert c["noYahoo"] == 2 and c["noList"] == 2 and c["open"] == 0              # 야후에 차트가 없는 두 종목 → 다시 물어도 같아요
    d = fb_data("2026-11-20", 2740, own={"v": 1, "n": 25, "codes": [], "unconf": 31})
    d["pxSrc"]["fb"].update({"open": 1, "noList": 5})
    assert A.open_closes(d) == {"kr": 1, "us": 0}
    d["pxSrc"]["fb"]["open"] = 0
    assert A.open_closes(d) == {"kr": 0, "us": 0}
    assert A.decide(d, kst(2026, 11, 21, 10, 53), CAL)[0] is True                  # 바뀔 수 있는 것이 없으면 예전처럼 건너뛰어요
    d["pxSrc"]["fb"]["knx"] = {"kept": 20, "open": 3}
    assert A.open_closes(d) == {"kr": 3, "us": 0}
