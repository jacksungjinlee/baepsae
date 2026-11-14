# -*- coding: utf-8 -*-
"""과거 주가 기록 오류 종목의 숫자 비움 (Jack, 2026-11-14) — 파이프라인과 관문. (네트워크 없음)

Q2 (a): "For those 18 stocks, hide every number built on the broken price history: the 52-week range, 출렁임, 위험, beta, 1-year and
other period returns, and the % labels on their charts. Take them out of the 추세 list on 홈 and any 출렁임-based list or rule."
저녁: "1. Must-have stock with a broken day: warn when one is affected; block the publish when two or more must-haves are affected, or
when many stocks newly break in one run … 2. Old bad days: hide only the numbers whose calculation window includes the bad day, so the
9 stocks with a bad day over a year old show their 52-week range. …"

- 그 종목 = 오늘 실행의 krSeries.jump 에 있는 종목 (날마다 바뀔 수 있어요).
- fetch_data.mark_px_bad: 계산 창에 움직임 날짜가 든 칸만 비워요 (validate_data.PX_BAD_WIN: 252봉 hi · lo · mom · mz · 64봉 r3 · 22봉 r1 · 그 밖은
  시계열 전체라 늘). pxBad = 가장 최근 움직임 날짜 · pxBadF = 비운 칸 · krSeries.hidden = 표시한 종목.
- 점수(mz · lz)와 순위는 비운 칸 없이 · 필수 종목은 꼭 들어 있어야 해요 · corp.json 도 같은 표시와 칸.
- 관문: '과거 주가 기록 오류 종목의 숫자 비움 (pxBad)' · '새로 생긴 과거 주가 기록 오류 종목 수' · '필수 종목 추세 · 저변동 순위 (mz · lz)'
  (새 줄) · '필수 종목 52주 최고·최저 (야후)' · '필수 종목 새 칸' (예전 줄: 표시가 맞는 필수 종목 하나만 경고로 넘겨요 — Jack 2026-11-14)."""
import copy
import inspect
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402
from test_validate import check, failed_names  # noqa: E402

NAME = "과거 주가 기록 오류 종목의 숫자 비움 (pxBad)"
MUST_NAME = "필수 종목 추세 · 저변동 순위 (mz · lz)"
NEW_NAME = f"새로 생긴 과거 주가 기록 오류 종목 수 ({V.PX_BAD_NEW_FAIL}종목 이상이면 실패)"
HILO_NAME = "필수 종목 52주 최고·최저 (야후)"
NEWF_NAME = "필수 종목 새 칸 (배당 분할 확인·베타 표준오차·재무 경고 검사)"
SERIES = {"hi": 6760.0, "lo": 280.0, "vol": 88.1, "beta": 0.54, "betaSE": 0.84, "betaN": 755, "al": -12.3, "r1": -0.7, "r3": -29.9,
          "r36": 44.1, "mom": 206.4, "sh": 0.01, "mdd": -84.6, "hit": 32, "mz": 99, "lz": 3}
KEEP = {"price": 1881.0, "cap": 0.048, "d1": -0.21, "val": 0.8, "val20": 2.0, "pbr": 0.8, "roe": -44.3, "dps": 0.0, "dy": 0.0, "dyt": 0.0,
        "pz": 76, "vz": 48, "qz": 6, "dz": 25, "shr": 25650015, "fy": 2025}
# 기준일 2026-11-13 의 창 첫 봉 (KOSPI 거래일 달력 그대로: 252봉 · 64봉 · 22봉 전)
CUT = {"y": "2025-11-04", "q": "2026-08-11", "m": "2026-10-15"}
ALL = list(V.PX_BAD_DATA)
OLD = [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS]                       # 움직임이 252봉보다 오래됨: 시계열 전체 칸만
Y = [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS or k in V.PX_BAD_WIN["y"]]   # 252봉 안 · 64봉 밖


def kr(t, nk, **kw):
    return {"t": t, "nk": nk, "ne": nk, "cls": "kr", "s": "bio", **KEEP, **SERIES, **kw}


def series(jump):
    return {"v": 1, "days": 19, "pinned": 39943, "pinStocks": 2343, "kept": {"basis": 157, "far": 8, "shr": 0}, "keptStocks": 23,
            "bad": 0, "badStocks": [], "ref": {"breakStocks": 18, "unknownStocks": 0, "newStocks": 14}, "jump": jump}


def cuts(*codes, cut=CUT):
    return {c: dict(cut) for c in codes}


# ── 1. 비우는 칸 목록 = 시계열로 만드는 칸 모두 · 칸마다 창 ─────────────────
def test_the_blank_list_is_every_number_the_series_makes_and_nothing_else():
    """fetch_korea 가 px(그 시계열)로 만드는 칸 · perf_stats 가 만드는 칸 · 그 칸으로 매기는 점수 — 하나도 빠지지 않아요. 가격 · 시가총액 ·
    d1(공식 종가끼리) · 거래대금 · 재무 · 배당과 그 점수는 시계열이 아니라서 남겨요."""
    src = inspect.getsource(F.fetch_korea)
    rec = src[src.index("rec = {"):src.rindex("hilo_note(code, px, rec)")]
    from_px = {"vol", "beta", "al", "betaSE", "betaN", "lo", "hi"}
    assert '"vol": ann_vol(ret.values), "beta": b, "al": a,' in rec and '"betaSE": bse, "betaN": bn,' in rec
    assert '"lo": float(px.tail(252).min()), "hi": float(px.tail(252).max()),' in rec
    for k in ("r1", "r3", "r36"):
        assert f'rec["{k}"] = round(float(px.iloc[-1] / px.iloc[' in src, k
    idx = pd.bdate_range("2023-10-02", periods=760)
    px = pd.Series(np.linspace(1000, 2000, 760) * (1 + 0.01 * np.sin(np.arange(760))), index=idx)
    perf = set(F.perf_stats(px, 0.03))
    assert perf == {"sh", "mdd", "hit", "mom"}
    built = from_px | {"r1", "r3", "r36"} | perf | {"mz", "lz"}                   # mz = mom 의 백분위 · lz = vol 의 백분위 (add_percentiles)
    assert set(V.PX_BAD_DATA) == built and len(V.PX_BAD_DATA) == len(built)
    assert F.PX_BAD_DATA is V.PX_BAD_DATA                                          # 파이프라인과 관문이 같은 목록 (관문 파일 한곳)
    for k in ("price", "cap", "d1", "val", "val20", "pbr", "roe", "pz", "vz", "qz", "dz", "dyt", "dps", "dy"):
        assert k not in V.PX_BAD_DATA, k
    # corp.json: build_corp 가 data.json 에서 옮겨 싣는 시계열 칸 = PX_BAD_CORP — 두 길 모두 (행을 만들 때 s.get · CORP_DIV_KEYS 로 옮기는 칸,
    # 리뷰 #126 S1: betaSE · betaN 은 뒤의 길로만 가요)
    bsrc = inspect.getsource(F.build_corp)
    copied = {k for k in V.PX_BAD_DATA if f'"{k}": s.get("{k}")' in bsrc} | (set(V.PX_BAD_DATA) & set(F.CORP_DIV_KEYS))
    assert {"betaSE", "betaN"} <= set(F.CORP_DIV_KEYS)
    assert copied == set(V.PX_BAD_CORP), copied
    row = F.build_corp([kr("005930", "삼성전자")], {}, "2026-11-14")["companies"][0]
    assert {k for k in V.PX_BAD_DATA if row.get(k) is not None} == set(V.PX_BAD_CORP), row


def test_each_fields_window_is_the_calculation_itself():
    """Jack 2026-11-14 저녁: 칸마다 계산 창 — 짐작하지 않고 fetch_korea · perf_stats 의 계산에서 읽어요. 252봉: px.tail(252) (hi · lo) ·
    px.iloc[-252] (mom, perf_stats) · mz (mom 의 백분위) · 64봉: px.iloc[-64] (r3) · 22봉: px.iloc[-22] (r1) · 그 밖은 시계열 전체."""
    assert V.PX_BAD_WIN == {"y": ("hi", "lo", "mom", "mz"), "q": ("r3",), "m": ("r1",)}
    assert V.PX_BAD_WIN_BARS == {"y": 252, "q": 64, "m": 22}
    assert set(V.PX_BAD_ALWAYS) == {"vol", "beta", "betaSE", "betaN", "al", "r36", "sh", "mdd", "hit", "lz"}
    src = inspect.getsource(F.fetch_korea)
    assert "px.tail(252)" in src and 'rec["r3"] = round(float(px.iloc[-1] / px.iloc[-64] - 1) * 100, 1)' in src
    assert 'rec["r1"] = round(float(px.iloc[-1] / px.iloc[-22] - 1) * 100, 1)' in src
    assert 'rec["r36"] = round(float(px.iloc[-1] / px.iloc[0] - 1) * 100, 1)' in src
    psrc = inspect.getsource(F.perf_stats)
    assert "base = float(px.iloc[-252])" in psrc and "dd = (px / px.cummax() - 1).min()" in psrc     # mom 252봉 · 낙폭은 전체
    assert 'px.resample("ME").last()' in psrc and "first, last = float(px.iloc[0]), float(px.iloc[-1])" in psrc   # 상승 월 · 샤프는 전체
    # 창의 첫 봉은 그 계산이 쓰는 봉 그대로 (봉이 모자라면 첫 봉)
    assert "cut = {w: (px.index[-n] if len(px) >= n else px.index[0]).date().isoformat() for w, n in PX_BAD_WIN_BARS.items()}" in src
    i_jm = src.index('jm = kr_jumps(px, raw, kr_day_limit(row.get("Market")))')
    assert i_jm < src.index("win_cut[code] = cut") < src.index("ret = px.pct_change().dropna()")


# ── 2. 표시 · 비움 ───────────────────────────────────────────
def test_mark_hides_only_the_fields_whose_window_holds_the_bad_day(capsys):
    """에이프로젠 (2026-05-08: 252봉 안) → 52주까지 · 1년 · 추세 점수도 (3개월 · 1개월은 그대로) · BYC우 (2024-04-17: 252봉 밖) → 시계열 전체 칸만
    (52주 · 1 · 3개월 · 1년 · 추세 점수는 보여요) · 진코스텍 (2026-10-15 = 22봉 창의 첫 봉) → 모두."""
    a, b, c, z = kr("007460", "에이프로젠"), kr("001465", "BYC우"), kr("250030", "진코스텍"), kr("005930", "삼성전자")
    before = copy.deepcopy(z)
    ks = series([["007460", "2026-05-08", 1446.1, "halt"], ["001465", "2024-04-17", -91.4, "halt"], ["250030", "2026-10-15", -48.7, "other"]])
    got = F.mark_px_bad([a, b, c, z], ks, cuts("007460", "001465", "250030"))
    assert got["hidden"] == ["001465", "007460", "250030"] and ks["hidden"] == got["hidden"] and got["missing"] == [] and got["noCut"] == []
    assert a["pxBadF"] == Y and b["pxBadF"] == OLD and c["pxBadF"] == ALL
    assert a["pxBad"] == "2026-05-08" and b["pxBad"] == "2024-04-17" and c["pxBad"] == "2026-10-15"
    for s in (a, b, c):
        assert not set(s["pxBadF"]) & set(s), s
        assert {k: s[k] for k in KEEP} == KEEP
        assert {k: s[k] for k in V.PX_BAD_DATA if k not in s["pxBadF"]} == {k: SERIES[k] for k in V.PX_BAD_DATA if k not in s["pxBadF"]}
    assert z == before
    assert got["f"] == {"007460": Y, "001465": OLD, "250030": ALL}
    json.dumps([a, b, c, ks], allow_nan=False)
    out = capsys.readouterr().out
    assert "  !! 과거 주가 기록 오류(하루 가격 제한폭 넘는 움직임)로 숫자를 비운 국내 종목: 3 (52주까지 2 · 52주는 보임 1) — 001465 BYC우 " \
           "(2024-04-17 · 52주는 보여요), 007460 에이프로젠 (2026-05-08), 250030 진코스텍 (2026-10-15)" in out


@pytest.mark.parametrize("d,want", [
    ("2025-11-04", Y), ("2025-11-03", OLD),                                          # 252봉 창의 첫 봉 · 그 앞날
    ("2026-08-11", [k for k in ALL if k != "r1"]), ("2026-08-10", Y),               # 64봉
    ("2026-10-15", ALL), ("2026-10-14", [k for k in ALL if k != "r1"]),             # 22봉
])
def test_the_window_edge_is_the_first_bar_the_calculation_uses(d, want):
    s = kr("007460", "에이프로젠")
    F.mark_px_bad([s], series([["007460", d, 99.0, "other"]]), cuts("007460"))
    assert s["pxBadF"] == want, (d, s["pxBadF"])


def test_any_move_in_the_window_counts_and_the_mark_is_the_latest():
    s = kr("012170", "아센디오")
    F.mark_px_bad([s], series([["012170", "2025-03-06", 797.8, "halt"], ["012170", "2026-08-28", 395.3, "halt"]]), cuts("012170"))
    assert s["pxBad"] == "2026-08-28" and s["pxBadF"] == [k for k in ALL if k != "r1"]


def test_without_a_window_every_number_is_hidden_and_it_is_loud(capsys):
    s = kr("007460", "에이프로젠")
    got = F.mark_px_bad([s], series([["007460", "2024-01-02", 99.0, "other"]]), {})
    assert s["pxBadF"] == ALL and got["noCut"] == ["007460"]
    assert "창을 모르는 종목 1: 007460 (모두 비웠어요)" in capsys.readouterr().out


def test_mark_counts_only_the_numbers_that_were_there_and_never_leaves_an_old_mark(capsys):
    a = kr("007460", "에이프로젠")
    del a["vol"], a["lz"], a["al"]                                                 # 변동성 300% 넘게 → 원래 빈 칸 (ann_vol)
    old = kr("000660", "SK하이닉스", pxBad="2026-01-02", pxBadF=ALL)              # 어제 표시 · 오늘 jump 에 없음 → 표시를 떼고 숫자는 그대로
    ks = series([["007460", "2026-05-08", 1446.1, "halt"]])
    got = F.mark_px_bad([a, old], ks, cuts("007460"))
    assert "vol" not in got["fields"] and got["fields"]["beta"] == 1 and got["hidden"] == ["007460"]
    assert "pxBad" not in old and "pxBadF" not in old and old["mom"] == SERIES["mom"]
    assert "비운 칸: hi 1 · lo 1 · beta 1 · betaSE 1 · betaN 1 · r36 1 · mom 1" in capsys.readouterr().out


def test_mark_with_nothing_named_is_quiet_and_writes_an_empty_list(capsys):
    a = kr("005930", "삼성전자")
    ks = series([])
    got = F.mark_px_bad([a], ks, {})
    assert got == {"hidden": [], "fields": {}, "missing": [], "f": {}, "noCut": []} and ks["hidden"] == [] and "pxBad" not in a
    out = capsys.readouterr().out
    assert "· 과거 주가 기록 오류(하루 가격 제한폭 넘는 움직임)로 숫자를 비운 국내 종목: 0" in out and "!!" not in out


def test_a_named_code_that_is_not_published_is_loud(capsys):
    ks = series([["999990", "2025-01-02", 99.0, "other"]])
    got = F.mark_px_bad([kr("005930", "삼성전자")], ks, cuts("999990"))
    assert got["hidden"] == [] and got["missing"] == ["999990"] and ks["hidden"] == []
    assert "  !! " in capsys.readouterr().out


def test_us_stocks_are_never_marked():
    us = {"t": "AAPL", "cls": "us", **SERIES}
    ks = series([["AAPL", "2026-05-08", 50.0, "other"]])
    F.mark_px_bad([us], ks, cuts("AAPL"))
    assert "pxBad" not in us and us["mom"] == SERIES["mom"] and ks["hidden"] == []


def test_fetch_korea_marks_before_it_returns_and_main_ranks_after():
    src = inspect.getsource(F.fetch_korea)
    i_ks = src.index("krs = kr_series_check(")
    i_mark = src.index("mark_px_bad(out, krs, win_cut)")
    assert i_ks < i_mark < src.index("meta = {") and src.count("mark_px_bad(") == 1
    main = inspect.getsource(F.main)
    i_kr = main.index('ph.run("국내 시세", fetch_korea')
    i_pct = main.index("add_percentiles(kr)")
    assert i_kr < i_pct < main.index("miss_tr = trend_rank_missing(kr)") < main.index("build_corp(kr, fin_map")
    assert '"krSeries": kmeta.get("krSeries")' in main


# ── 3. 점수 · 순위는 비운 칸 없이 ─────────────────────────────
def test_scores_are_made_without_the_blanked_fields_and_an_old_bad_day_keeps_its_trend_score():
    rnd = np.random.default_rng(3)
    stocks = [kr(f"{100000 + 10 * i:06d}", f"종목{i}", mom=float(m), vol=float(v)) for i, (m, v) in
              enumerate(zip(rnd.normal(10, 40, 60).round(1), rnd.uniform(15, 90, 60).round(1)))]
    for s in stocks:
        s.pop("mz"), s.pop("lz")
    stocks[0].update(mom=1446.1, vol=5.0)                                          # 최근 움직임: 1년 수익률도 망가졌어요
    stocks[1].update(mom=42.0, vol=400.0)                                          # 오래된 움직임: 1년 수익률은 맞아요
    ks = series([["100000", "2026-05-08", 1446.1, "halt"], ["100010", "2024-04-17", -91.4, "halt"]])
    F.mark_px_bad(stocks, ks, cuts("100000", "100010"))
    F.add_percentiles(stocks)
    rest = copy.deepcopy(stocks)
    for s in rest:
        s.pop("mz", None), s.pop("lz", None)
    F.add_percentiles(rest)                                                        # 남은 값만으로 다시 매긴 점수 (같아야 해요)
    assert "mz" not in stocks[0] and "lz" not in stocks[0]
    assert "mz" in stocks[1] and "lz" not in stocks[1] and stocks[1]["mom"] == 42.0
    assert [(s.get("mz"), s.get("lz")) for s in stocks] == [(s.get("mz"), s.get("lz")) for s in rest]
    top = max(stocks[2:], key=lambda s: s["mom"])
    assert top["mz"] == 100


def test_must_have_stocks_stay_in_the_trend_and_low_volatility_ranks():
    must = [kr(t, t, mz=50, lz=50) for t in F.DIV_RANK_MUST]
    assert F.trend_rank_missing(must) == []
    gone = copy.deepcopy(must)
    F.mark_px_bad(gone, series([["005380", "2026-05-08", 50.0, "other"]]), cuts("005380"))
    F.add_percentiles(gone)
    assert F.trend_rank_missing(gone) == [("005380", "mz·lz 없음 — 과거 주가 기록 오류 (pxBad 2026-05-08)")]
    old = copy.deepcopy(must)
    F.mark_px_bad(old, series([["005380", "2024-05-08", 50.0, "other"]]), cuts("005380"))
    F.add_percentiles(old)
    assert F.trend_rank_missing(old) == [("005380", "lz 없음 — 과거 주가 기록 오류 (pxBad 2024-05-08)")]
    assert F.trend_rank_missing(must[1:]) == [(must[0]["t"], "데이터에 없음")]
    assert list(F.DIV_RANK_MUST) == list(V.MUST)


# ── 4. corp.json ─────────────────────────────────────────────
def test_corp_json_carries_the_mark_the_list_and_the_same_blanks():
    a, b, c = kr("007460", "에이프로젠"), kr("001465", "BYC우"), kr("005930", "삼성전자")
    F.mark_px_bad([a, b, c], series([["007460", "2026-05-08", 1446.1, "halt"], ["001465", "2024-04-17", -91.4, "halt"]]),
                  cuts("007460", "001465"))
    rows = {r["t"]: r for r in F.build_corp([a, b, c], {}, "2026-11-14")["companies"]}
    for t, f in (("007460", Y), ("001465", OLD)):
        assert rows[t]["pxBad"] == {"007460": "2026-05-08", "001465": "2024-04-17"}[t] and rows[t]["pxBadF"] == f
        assert all(rows[t].get(k) is None for k in V.PX_BAD_CORP if k in f)
        assert all(rows[t].get(k) == SERIES[k] for k in V.PX_BAD_CORP if k not in f)
    assert "pxBad" not in rows["005930"] and all(rows["005930"].get(k) == SERIES[k] for k in V.PX_BAD_CORP)
    json.dumps(rows, allow_nan=False)
    assert "pxBad" in F.UNITS and "pxBadF" in F.UNITS and "hidden" in F.UNITS["krSeries"]


# ── 5. 관문 ──────────────────────────────────────────────────
# 시험 데이터의 기준일은 2026-10-30: 창의 첫 봉도 그 달력으로 (252봉 · 64봉 · 22봉 전 평일)
GCUT = {"y": "2025-11-14", "q": "2026-08-03", "m": "2026-09-30"}
JUMP = [["200100", "2026-05-08", 1446.1, "halt"], ["200110", "2024-03-06", 797.8, "halt"], ["200110", "2025-03-06", 395.3, "halt"],
        ["200120", "2026-10-20", -48.7, "other"]]                                   # 52주까지 · 52주는 보임 · 모두


def marked_pair(jump=JUMP, prev_jump=None, divcheck=False):
    """good_pair 에 파이프라인처럼: krSeries (jump · hidden) · 창에 든 칸을 지우고 pxBad · pxBadF · corp.json 도 같게. 직전 발행본도 새 형식
    (prev_jump: 직전 발행본의 jump — 없으면 오늘과 같아요). divcheck: 새 칸 줄이 돌게 (v19.1b 형식)."""
    cur, prev, final = good_pair()
    stocks = cur["data"]["stocks"]
    by = {s["t"]: s for s in stocks}
    assert all(j[0] in by for j in jump)
    for s in stocks:
        if s.get("cls") == "kr":
            s.update({k: v for k, v in SERIES.items() if k not in s and k not in ("mz", "lz")})
    ks = series(copy.deepcopy(jump))
    F.mark_px_bad([s for s in stocks if s.get("cls") == "kr"], ks, {j[0]: dict(GCUT) for j in jump})
    cur["data"]["krSeries"] = ks
    for c in cur["corp"]["companies"]:
        s = by[c["t"]]
        c.update({k: s.get(k) for k in V.PX_BAD_CORP})
        if s.get("pxBad"):
            c["pxBad"], c["pxBadF"] = s["pxBad"], list(s["pxBadF"])
    prev["data"]["krSeries"] = series(copy.deepcopy(jump if prev_jump is None else prev_jump))
    prev["data"]["krSeries"]["hidden"] = []
    if divcheck:
        for f in (cur, prev):
            f["data"]["divCheck"] = {"v": 1}
            for c in f["corp"]["companies"]:
                c.setdefault("flRan", [])
    return cur, prev, final


def row(rep, name):
    return next(r for r in rep.rows if r[0] == name)


def test_gate_passes_the_marked_publish():
    cur, prev, final = marked_pair()
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    assert by["200100"]["pxBadF"] == Y and by["200110"]["pxBadF"] == OLD and by["200110"]["hi"] is not None and by["200120"]["pxBadF"] == ALL
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    r = row(rep, NAME)
    assert r[3] == "PASS" and r[1].startswith("3종목 (52주까지 비움 2 · 52주는 보임 1) · 문제 0 — 200100 ") and "(2026-05-08 · 52주까지)" in r[1] \
        and "(2025-03-06 · 52주는 보여요)" in r[1], r
    assert row(rep, MUST_NAME)[3] == "PASS" and row(rep, MUST_NAME)[1] == "모두 있음"
    assert row(rep, NEW_NAME)[3] == "PASS" and row(rep, NEW_NAME)[1] == "새로 0종목"
    assert not check(cur, None, final, mode="live").failed


def test_gate_passes_a_day_with_nothing_named():
    cur, prev, final = marked_pair(jump=[])
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "PASS" and row(rep, NAME)[1] == "0종목 (52주까지 비움 0 · 52주는 보임 0) · 문제 0"


HOWS = ["not hidden", "hidden but not named", "no mark", "mark but not hidden", "older date", "date shape", "date empty", "date bool",
        "corp mark missing", "corp mark differs", "corp list differs", "corp only mark", "hidden not a list", "hidden duplicate",
        "hidden number", "us mark", "list only", "list missing always", "list unknown field", "list not a list", "list duplicate",
        "half a window", "short window alone", "recent but 52 shown", "52 shown but missing", "corp 52 shown but missing"]


@pytest.mark.parametrize("how", HOWS + [f"left {k}" for k in V.PX_BAD_DATA] + [f"corp left {k}" for k in V.PX_BAD_CORP])
def test_gate_fails_when_a_named_stock_still_shows_a_number_or_the_marks_disagree(how):
    """must-fail: 비운 칸에 숫자가 남았거나 (data.json · corp.json), 비우지 않은 52주가 없거나, jump · hidden · pxBad · pxBadF 가 서로 다르거나,
    pxBadF 가 창의 규칙과 다르면 (시계열 전체 칸이 빠짐 · 창의 칸이 일부만 · 짧은 창만 · 기준일에서 가까운 움직임인데 52주를 비우지 않음) 발행하지 않아요."""
    cur, prev, final = marked_pair()
    ks = cur["data"]["krSeries"]
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    cby = {c["t"]: c for c in cur["corp"]["companies"]}
    a, o, other = by["200100"], by["200110"], by["200200"]

    def both(t, **kw):
        by[t].update(kw)
        cby[t].update(copy.deepcopy(kw))
    if how == "not hidden":
        ks["hidden"].remove("200100")
        for x in (a, cby["200100"]):
            del x["pxBad"], x["pxBadF"]
    elif how == "hidden but not named":
        ks["jump"] = [j for j in ks["jump"] if j[0] != "200100"]
    elif how == "no mark":
        del a["pxBad"]
    elif how == "mark but not hidden":
        other.update(pxBad="2026-05-08", pxBadF=ALL)
        for k in V.PX_BAD_DATA:
            other.pop(k, None)
    elif how == "older date":
        both("200110", pxBad="2024-03-06")
    elif how == "date shape":
        both("200100", pxBad="2026/05/08")
    elif how == "date empty":
        both("200100", pxBad="")
    elif how == "date bool":
        both("200100", pxBad=True)
    elif how == "corp mark missing":
        del cby["200100"]["pxBad"]
    elif how == "corp mark differs":
        cby["200100"]["pxBad"] = "2026-05-07"
    elif how == "corp list differs":
        cby["200110"]["pxBadF"] = Y
    elif how == "corp only mark":
        cby["200200"]["pxBad"] = "2026-05-08"
    elif how == "hidden not a list":
        ks["hidden"] = "200100,200110"
    elif how == "hidden duplicate":
        ks["hidden"] = ["200100", "200110", "200100"]
    elif how == "hidden number":
        ks["hidden"] = [200100, "200110"]
    elif how == "us mark":
        by["AAPL"]["pxBad"] = "2026-05-08"
    elif how == "list only":
        other["pxBadF"] = OLD
    elif how == "list missing always":
        both("200110", pxBadF=[k for k in OLD if k != "hit"])
    elif how == "list unknown field":
        both("200110", pxBadF=OLD + ["price"])
    elif how == "list not a list":
        both("200110", pxBadF="vol,beta")
    elif how == "list duplicate":
        both("200110", pxBadF=OLD + ["vol"])
    elif how == "half a window":
        both("200110", pxBadF=[k for k in ALL if k in OLD or k in ("hi", "lo")])
        for x in (o, cby["200110"]):
            x.pop("hi", None), x.pop("lo", None)
    elif how == "short window alone":
        both("200110", pxBadF=[k for k in ALL if k in OLD or k == "r1"])
        o.pop("r1", None)
    elif how == "recent but 52 shown":                                           # 기준일에서 340일 안의 움직임: 52주를 꼭 비워야 해요
        ks["jump"] = [j if j[0] != "200110" else [j[0], "2026-01-02", j[2], j[3]] for j in ks["jump"]]
        both("200110", pxBad="2026-01-02")
    elif how == "52 shown but missing":
        o.pop("hi")
    elif how == "corp 52 shown but missing":
        cby["200110"]["lo"] = None
    elif how.startswith("left "):
        by["200120"][how.split()[1]] = 1.0                                         # 200120: 모두 비운 종목
    else:
        cby["200120"][how.split()[2]] = 1.0
    rep = check(cur, prev, final)
    assert NAME in failed_names(rep), (how, rep.table())
    assert MUST_NAME not in failed_names(rep)


def test_gate_value_names_the_problem():
    cur, prev, final = marked_pair()
    next(s for s in cur["data"]["stocks"] if s["t"] == "200100")["hi"] = 6760.0
    r = row(check(cur, prev, final), NAME)
    assert r[3] == "FAIL" and "문제 1 (200100 남은 칸 hi)" in r[1], r


def test_gate_old_format_only_warns_until_the_first_marked_publish():
    cur, prev, final = good_pair()
    cur["data"]["krSeries"] = series(copy.deepcopy(JUMP))
    prev["data"]["krSeries"] = series([])
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "WARN" and "2026-11-14 숨김 전 형식" in row(rep, NAME)[1], rep.table()
    rep = check(cur, None, final, mode="live")
    assert NAME not in failed_names(rep) and row(rep, NAME)[3] == "WARN"
    prev["data"]["krSeries"]["hidden"] = []
    assert NAME in failed_names(check(cur, prev, final))
    del prev["data"]["krSeries"]["hidden"]
    next(s for s in cur["data"]["stocks"] if s["t"] == "200100")["pxBad"] = "2026-05-08"
    assert NAME in failed_names(check(cur, prev, final))
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "WARN" and row(rep, NAME)[1].startswith("krSeries 없음")


# ── 6. 한 실행에 새로 생긴 움직임 종목 (Jack 2026-11-14 저녁) ──────────────
def kr_codes(n, start=300):
    return [f"{(20000 + i) * 10:06d}" for i in range(start, start + n)]


@pytest.mark.parametrize("n,fail", [(0, False), (2, False), (V.PX_BAD_NEW_FAIL - 1, False), (V.PX_BAD_NEW_FAIL, True), (40, True)])
def test_gate_fails_when_many_stocks_newly_break_in_one_run(n, fail):
    new = [[c, "2026-10-20", 60.0, "other"] for c in kr_codes(n)]
    cur, prev, final = marked_pair(jump=JUMP + new, prev_jump=JUMP)
    rep = check(cur, prev, final)
    r = row(rep, NEW_NAME)
    assert (NEW_NAME in failed_names(rep)) is fail, r
    assert r[1].startswith(f"새로 {n}종목"), r
    assert row(rep, NAME)[3] == "PASS"                                             # 비우기 자체는 맞게 됐어요


def test_new_breaks_count_stocks_not_moves_and_need_the_previous_publish():
    cur, prev, final = marked_pair(prev_jump=JUMP[:1])                               # 200110 이 새로 (움직임 둘이어도 한 종목)
    assert row(check(cur, prev, final), NEW_NAME)[1].startswith("새로 2종목: 200110 가상종목")
    assert row(check(cur, None, final, mode="live"), NEW_NAME)[1] == "직전 발행본 없음 (비교 안 함)"
    cur, prev, final = marked_pair()
    del prev["data"]["krSeries"]
    r = row(check(cur, prev, final), NEW_NAME)
    assert r[3] == "PASS" and r[1].startswith("직전 발행본 또는 오늘 파일에 krSeries.jump 없음")
    assert V.PX_BAD_NEW_FAIL == 10


def test_new_break_threshold_is_far_above_the_history():
    """근거 (PR 본문 · validate_data 설명): 2026-11-14 의 21개 움직임 (18종목) 은 지난 3년의 19개 날짜, 한 날에 많아야 2종목."""
    import collections
    per_day = collections.Counter()
    jump = [["001465", "2024-04-17"], ["003060", "2026-05-08"], ["007460", "2026-05-08"], ["007610", "2026-04-29"], ["009310", "2026-05-11"],
            ["012170", "2025-03-06"], ["012170", "2026-08-28"], ["012210", "2025-04-24"], ["107640", "2024-06-24"], ["110790", "2023-10-20"],
            ["121890", "2023-10-23"], ["210120", "2026-10-12"], ["227420", "2024-01-19"], ["229500", "2024-05-29"], ["250030", "2026-10-15"],
            ["311060", "2024-01-25"], ["331660", "2026-05-06"], ["425040", "2023-12-28"], ["425040", "2024-01-02"], ["472850", "2025-12-30"],
            ["472850", "2026-01-02"]]
    first = {}
    for c, d in jump:
        first[c] = min(first.get(c, d), d)                                         # 그 종목이 처음 이름에 오른 날
    per_day.update(first.values())
    assert len(jump) == 21 and len(first) == 18 and len(per_day) == 17 and max(per_day.values()) == 2
    assert V.PX_BAD_NEW_FAIL >= 5 * max(per_day.values())


# ── 7. 필수 종목 (Jack 2026-11-14 저녁: 하나는 경고 · 둘 이상은 실패) ─────────────
def must_hilo(files):
    """'야후'의 52주 범위와 d1 (비우기 전 값으로)."""
    by = {x["t"]: x for x in files["data"]["stocks"]}
    return {t: {"hi": by[t]["hi"], "lo": by[t]["lo"], "d1": by[t].get("d1", 0.0)} for t in V.MUST if t in by}


def must_check(jump, **kw):
    cur, prev, final = good_pair()
    hilo = must_hilo(cur)
    cur, prev, final = marked_pair(jump=JUMP + jump, divcheck=True, **kw)
    by = {x["t"]: x for x in cur["data"]["stocks"]}
    for t in V.MUST:                                                                # 새 칸 줄이 보는 칸 (시험 데이터에 없어요)
        for k in ("betaSE", "betaN"):
            if k not in by[t].get("pxBadF", []):
                by[t].setdefault(k, 0.05 if k == "betaSE" else 740)
    return cur, prev, final, hilo


def test_one_marked_must_have_warns_in_all_three_rows():
    cur, prev, final, hilo = must_check([["005930", "2026-01-02", 60.0, "spike"]])
    rep = check(cur, prev, final, hilo=hilo)
    for nm in (MUST_NAME, HILO_NAME, NEWF_NAME):
        assert row(rep, nm)[3] == "WARN", (nm, row(rep, nm))
    assert row(rep, MUST_NAME)[1] == "과거 주가 기록 오류로 뺀 필수 종목 1: 005930 삼성전자 mz·lz — 과거 주가 기록 오류 (pxBad 2026-01-02)"
    assert "005930 과거 주가 기록 오류로 비움 (pxBad 2026-01-02)" in row(rep, HILO_NAME)[1]
    assert row(rep, NEWF_NAME)[1].endswith("과거 주가 기록 오류로 비운 칸 (경고): 005930.betaSE,005930.betaN")
    assert not ({MUST_NAME, HILO_NAME, NEWF_NAME, NAME} & failed_names(rep)), failed_names(rep)


def test_one_must_have_with_an_old_bad_day_keeps_its_52_week_range():
    cur, prev, final, hilo = must_check([["005930", "2024-01-02", 60.0, "spike"]])
    rep = check(cur, prev, final, hilo=hilo)
    by = {x["t"]: x for x in cur["data"]["stocks"]}
    assert by["005930"]["pxBadF"] == OLD and by["005930"]["hi"] is not None
    assert row(rep, HILO_NAME)[3] == "PASS"                                        # 52주는 그대로 야후와 견줘요
    assert row(rep, MUST_NAME)[3] == "WARN" and "005930 삼성전자 lz —" in row(rep, MUST_NAME)[1]
    assert row(rep, NEWF_NAME)[3] == "WARN"


def test_two_marked_must_haves_fail_all_three_rows():
    cur, prev, final, hilo = must_check([["005930", "2026-01-02", 60.0, "spike"], ["005380", "2025-12-01", -45.0, "other"]])
    rep = check(cur, prev, final, hilo=hilo)
    assert {MUST_NAME, HILO_NAME, NEWF_NAME} <= failed_names(rep), failed_names(rep)
    assert row(rep, MUST_NAME)[1].startswith("과거 주가 기록 오류로 뺀 필수 종목 2: 005930 삼성전자 mz·lz")
    assert "005930 없음" in row(rep, HILO_NAME)[1] and "005380 없음" in row(rep, HILO_NAME)[1]
    assert row(rep, NEWF_NAME)[1].startswith("없음: 005930.betaSE,005930.betaN,005380.betaSE,005380.betaN")


def test_two_marked_must_haves_fail_even_if_one_bad_day_is_old():
    cur, prev, final, hilo = must_check([["005930", "2026-01-02", 60.0, "spike"], ["005380", "2024-01-02", -45.0, "other"]])
    rep = check(cur, prev, final, hilo=hilo)
    assert {MUST_NAME, HILO_NAME, NEWF_NAME} <= failed_names(rep), failed_names(rep)


@pytest.mark.parametrize("how", ["corp mark missing", "left beta", "corp left betaSE", "not hidden", "other date"])
def test_a_must_have_whose_mark_is_wrong_still_fails_every_row(how):
    """표시가 맞지 않는 필수 종목 (hidden 에 없음 · 숫자가 남음 · corp.json 이 다름 · 날짜가 다름): 세 줄 모두 예전처럼 실패 (경고가 아니에요)."""
    cur, prev, final, hilo = must_check([["005930", "2026-01-02", 60.0, "spike"]])
    sam = next(x for x in cur["data"]["stocks"] if x["t"] == "005930")
    co = next(x for x in cur["corp"]["companies"] if x["t"] == "005930")
    if how == "corp mark missing":
        del co["pxBad"]
    elif how == "left beta":
        sam["beta"] = 1.2
    elif how == "corp left betaSE":
        co["betaSE"] = 0.02
    elif how == "not hidden":
        cur["data"]["krSeries"]["hidden"].remove("005930")
    else:
        sam["pxBad"] = co["pxBad"] = "2025-12-31"
    rep = check(cur, prev, final, hilo=hilo)
    r = row(rep, MUST_NAME)
    assert r[3] == "FAIL" and r[1].startswith("빠짐: 005930 삼성전자 mz·lz — pxBad ") and "표시가 맞지 않아요" in r[1], (how, r)
    assert {NAME, HILO_NAME, NEWF_NAME} <= failed_names(rep), (how, failed_names(rep))


def test_must_have_without_a_mark_fails_as_before():
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "005930")
    del s["mz"], s["lz"]
    r = row(check(cur, prev, final), MUST_NAME)
    assert r[3] == "FAIL" and r[1] == "빠짐: 005930 삼성전자 mz·lz — 1년 수익률(mom) 없음 · lz 없음 (vol 있음)", r
    cur, prev, final, hilo = must_check([])
    sam = next(x for x in cur["data"]["stocks"] if x["t"] == "005930")
    del sam["hi"], sam["betaSE"]
    rep = check(cur, prev, final, hilo=hilo)
    assert {HILO_NAME, NEWF_NAME} <= failed_names(rep)                              # 예전 두 줄: 표시 없이 빠지면 그대로 실패
    cur, prev, final = good_pair()
    cur["data"]["stocks"] = [s for s in cur["data"]["stocks"] if s["t"] != "035420"]
    assert "035420 데이터에 없음" in row(check(cur, prev, final), MUST_NAME)[1]
    assert V.PX_BAD_MUST_FAIL == 2


@pytest.mark.parametrize("t", list(V.MUST))
def test_gate_fails_when_a_must_have_stock_leaves_the_trend_or_low_volatility_rank(t):
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == t)
    del s["mz"]
    rep = check(cur, prev, final)
    assert MUST_NAME in failed_names(rep), rep.table()
    assert row(rep, MUST_NAME)[1] == f"빠짐: {t} {s['nk']} mz — 1년 수익률(mom) 없음", row(rep, MUST_NAME)
    s["mom"] = 12.0
    assert row(check(cur, prev, final), MUST_NAME)[1] == f"빠짐: {t} {s['nk']} mz — mz 없음 (mom 있음)"


def test_gate_and_pipeline_agree_on_real_codes():
    """tests/fixtures/kr_pin_samples.json (2026-11-14 실제 자료)의 종목 코드로: 파이프라인이 표시한 대로면 관문이 통과해요 (최근 · 오래된 · 섞인 움직임)."""
    with open(os.path.join(ROOT, "tests", "fixtures", "kr_pin_samples.json"), encoding="utf-8") as f:
        fx = json.load(f)
    codes = sorted(fx["listing"])
    stocks = [kr(c, c) for c in codes]
    jump = [[codes[0], "2026-05-08", 100.0, "halt"], [codes[1], "2024-04-17", -91.4, "halt"], [codes[2], "2023-12-28", 94.7, "spike"],
            [codes[2], "2026-10-15", -51.4, "spike"]]
    ks = series(jump)
    F.mark_px_bad(stocks, ks, cuts(*codes[:3]))
    corp = F.build_corp(stocks, {}, "2026-11-14")["companies"]
    probs = V.px_bad_problems(stocks, corp, ks, V.day("2026-11-13"))
    assert probs == [] and ks["hidden"] == codes[:3]
    assert [s["pxBadF"] for s in stocks[:3]] == [Y, OLD, ALL]
    assert all(math.isfinite(x) for s in stocks for x in s.values() if isinstance(x, float))
