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
    """지난주 06:40 발행 (data 브랜치): 11-19 2,743 / 2,771 = 98.99% · 11-20 2,740 / 2,771 = 98.88% — 둘 다 98% 바닥 위 (발행)."""
    assert P.COVERAGE_FLOOR_PCT == 98
    for conf in (2743, 2740):
        d = P.floor_decision(FB, conf, 2771)
        assert d.hold is False and d.kind == "publish" and "2,771" in d.why
    # 98% 의 2,771 = 2,715.58 → 2,716 부터 발행 (확인 못 한 종목 55 까지)
    assert P.floor_decision(FB, 2716, 2771).hold is False
    d = P.floor_decision(FB, 2715, 2771)
    assert d.hold is True and d.kind == "floor" and "모자람 1" in d.why and "2,716" in d.why
    # 야후가 빈 새벽 (11-19 밤 같은 수: 약 240 확인 못 함) → 보류
    d = P.floor_decision(FB, 2526, 2771)
    assert d.hold is True and d.loud is True and "91.16%" in d.why and "다음 실행이 다시 해요" in d.why


def test_exactly_the_floor_publishes():
    assert 2744 * 100 == 98 * 2800                                                # 딱 98%
    assert P.floor_decision(FB, 2744, 2800).hold is False
    assert P.floor_decision(FB, 2743, 2800).hold is True
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
def n_of(d):
    return P.kk_counts(d)[0]


def test_same_day_publishes_only_when_strictly_better_and_nothing_is_lost():
    prev = fb_data("2026-11-20", 2716, noYahoo=30)                                # 06:40: 98.01%
    better = fb_data("2026-11-20", 2700, noYahoo=46, rr=reuse(25))                # 이 실행 2,700 + 다시 씀 25 = 2,725 > 2,716 · 잃은 종목 0
    d = P.same_day_decision(FB, FB, n_of(better), n_of(prev))
    assert d.hold is False and d.kind == "publish" and "2,716 → 2,725 (+9)" in d.why
    same = fb_data("2026-11-20", 2700, noYahoo=46, rr=reuse(16))                  # 2,716 = 2,716
    d = P.same_day_decision(FB, FB, n_of(same), n_of(prev))
    assert d.hold is True and d.kind == "same" and "더 많지 않아" in d.why
    worse = fb_data("2026-11-20", 2690, noYahoo=56, rr=reuse(20))
    assert P.same_day_decision(FB, FB, n_of(worse), n_of(prev)).hold is True
    lost = fb_data("2026-11-20", 2740, rr=reuse(0, lost=1))                       # 더 많지만 하나를 잃었어요 (지금 두 출처가 다름 등)
    d = P.same_day_decision(FB, FB, n_of(lost), n_of(prev))
    assert d.hold is True and d.loud is True and "1개를 이 실행이 잃었어요" in d.why
    norec = fb_data("2026-11-20", 2740)                                           # 다시 쓰기 기록이 없으면 잃은 종목을 몰라요 → 발행 안 함
    d = P.same_day_decision(FB, FB, n_of(norec), n_of(prev))
    assert d.hold is True and "다시 쓰기 기록" in d.why
    assert P.same_day_decision(FB, FB, None, n_of(prev)).hold is True and P.same_day_decision(FB, FB, n_of(better), None).hold is True


def test_same_day_mode_changes():
    assert P.same_day_decision(LISTING, FB, None, None).hold is False             # KRX 최종본이 생김 → 발행
    assert P.same_day_decision(LISTING, LISTING, None, None).hold is False        # 손으로 다시 돌린 1차 출처 날 → 예전 그대로
    d = P.same_day_decision(FB, LISTING, n_of(fb_data("2026-11-20", 2740, rr=reuse(0))), None)
    assert d.hold is True and "2차 출처로 바꿔 발행하지 않아요" in d.why


def test_evaluate_runs_the_floor_first_then_the_same_day_rule():
    now = kst(2026, 11, 21, 10, 53)
    prev = fb_data("2026-11-20", 2716, noYahoo=30)
    # 같은 날 · 더 나음 → 발행
    d, lines = P.evaluate(fb_data("2026-11-20", 2700, noYahoo=46, rr=reuse(25)), "data.json", prev, "git HEAD:data.json", now)
    assert d.hold is False and any("직전 발행본 (같은 날)" in ln for ln in lines)
    # 같은 날인데 바닥 아래 → 바닥 보류 (같은 날 비교 전에)
    d, _ = P.evaluate(fb_data("2026-11-20", 2600, noYahoo=146, rr=reuse(10)), "data.json", prev, "git HEAD:data.json", now)
    assert d.kind == "floor"
    # 미국 기준일이 바뀌면 새 발행 (바닥만) — 미국 종가를 막지 않아요
    d, lines = P.evaluate(fb_data("2026-11-20", 2716, noYahoo=30, us="2026-11-20"), "data.json", fb_data("2026-11-20", 2740, us="2026-11-19"),
                          "git HEAD:data.json", now)
    assert d.hold is False and any("새 날" in ln for ln in lines)
    # 새 한국 기준일 → 바닥만
    assert P.evaluate(fb_data("2026-11-21", 2716, noYahoo=30), "data.json", prev, "git", now)[0].hold is False
    # 직전 발행본을 못 읽으면 같은 날인지 몰라 바닥만 (크게)
    d, lines = P.evaluate(fb_data("2026-11-20", 2716, noYahoo=30), "data.json", None, "git show HEAD:data.json → 종료 코드 128", now)
    assert d.hold is False and d.loud is True and d.kind == "unknown" and any(ln.startswith("!! 직전 발행본:") for ln in lines)
    # 오늘 기록을 못 쓰면 보류하지 않아요 (크게 · 오늘 줄에 !!)
    bad = fb_data("2026-11-20", 2700, noYahoo=46)
    bad["pxSrc"]["fb"]["conf"] += 5
    d, lines = P.evaluate(bad, "data.json", prev, "git", now)
    assert d.hold is False and d.loud is True and lines[1].startswith("!! 오늘:")
    # 오늘 data.json 을 못 읽으면 보류하지 않아요
    assert P.evaluate(None, "data.json 없음", prev, "git", now)[0].hold is False


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
    for part in ("2,526", "2,771", "91.16%", "바닥 98%", "2,716"):
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
    assert n == 0                                                                 # 마지막 확인 종가로 실은 종목 0 (STX 는 같은 날이라 옮기지 않아요)
    rr = src["own"]["reuse"]
    assert (rr["n"], rr["kk"], rr["lost"]) == (1, 0, 1) and rr["codes"] == [konex]
    assert [r for r in out if r["t"] == konex][0].get("pxd") is None and not [r for r in out if r["t"] == stx]
    assert src["own"]["unconf"] == 2                                              # 이 실행이 확인 못 한 수는 그대로 (관문의 코넥스 비교와 같게)
    log = capsys.readouterr().out
    assert "!! 같은 기준일을 다시 도는 실행" in log and "잃은 종목 1" in log
    data = json.loads(json.dumps({"pxDate": px.isoformat(), "usPxDate": "2026-11-16", "pxSrc": F.px_src_final(src, out), "stocks": out}))
    c = P.kk_counts(data)[0]
    assert c["lost"] == 1 and c["reuse"] == 0
    d = P.same_day_decision(FB, FB, c, dict(c, total=c["total"] - 1, lost=0))   # 확인이 더 많아도 잃은 종목이 있으면 발행 안 함
    assert d.hold is True and d.kind == "same" and "1개를 이 실행이 잃었어요" in d.why


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
    assert [s.get("name") for s in st if "steps.hold" in json.dumps(s, ensure_ascii=False)] == list(PUBLISH)


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
    (repo / "data.json").write_text(json.dumps(fb_data("2026-11-20", 2716, noYahoo=30)))       # 06:40 발행본
    for cmd in (["git", "init", "-q"], ["git", "add", "data.json"], ["git", "commit", "-q", "-m", "prev"]):
        subprocess.run(cmd, cwd=repo, env=genv, check=True, capture_output=True)
    run = next(s for s in update_steps() if s.get("name") == HOLD_STEP)["run"]
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    py = bin_ / "python"
    py.write_text(f'#!/bin/bash\n[ "$1" = "tools/publish_hold.py" ] || exit 9\nshift\n'
                  f'exec "{sys.executable}" "{os.path.join(ROOT, "tools", "publish_hold.py")}" "$@"\n')
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    cases = ((fb_data("2026-11-20", 2700, noYahoo=46, rr=reuse(25)), "hold=false"),     # 같은 날 · 더 나음 → 발행
             (fb_data("2026-11-20", 2716, noYahoo=30, rr=reuse(0)), "hold=true"),       # 같은 날 · 같음 → 발행 안 함
             (fb_data("2026-11-21", 2526, noYahoo=220), "hold=true"),                   # 새 날 · 바닥 아래 → 보류
             (fb_data("2026-11-21", 2740), "hold=false"))                               # 새 날 · 바닥 위 → 발행
    for cur, want in cases:
        (repo / "data.json").write_text(json.dumps(cur))
        out = tmp_path / "out.txt"
        out.write_text("")
        e = {**genv, "PATH": f"{bin_}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), "BOOTSTRAP": "", "PREV_REF": "", "DRY_RUN": ""}
        e.pop("GITHUB_ACTIONS", None)
        e.pop("GITHUB_STEP_SUMMARY", None)
        r = subprocess.run(["bash", "-e", "-c", run], cwd=repo, env=e, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert out.read_text().splitlines()[-1] == want, (cur["pxDate"], r.stdout, r.stderr)
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, env=genv, capture_output=True, text=True).stdout
    assert len(log.strip().splitlines()) == 1                                     # 단계는 커밋하지 않아요


# ── 9. 발행하지 않은 실행은 발행이 아니에요: 배포 · 감시 ─────────────
HELD_JOBS = [{"name": "check", "conclusion": "success", "steps": [{"name": "x", "conclusion": "success"}]},
             {"name": "update", "conclusion": "success",
              "steps": [{"name": HOLD_STEP, "conclusion": "success"}, {"name": GATE, "conclusion": "success"},
                        {"name": PUBLISH[0], "conclusion": "skipped"}, {"name": PUBLISH[1], "conclusion": "skipped"}]}]


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
