# -*- coding: utf-8 -*-
"""과거 주가 기록 오류 종목의 숫자 비움 (Jack, 2026-11-14 · Q2 (a) "this week") — 파이프라인과 관문. (네트워크 없음)

"For those 18 stocks, hide every number built on the broken price history: the 52-week range, 출렁임, 위험, beta, 1-year and other
period returns, and the % labels on their charts. Take them out of the 추세 list on 홈 and any 출렁임-based list or rule."

- 그 종목 = 오늘 실행의 krSeries.jump 에 있는 종목 (하루 움직임이 가격 제한폭으로 설명되지 않아요 · 날마다 바뀔 수 있어요).
- fetch_data.mark_px_bad: 그 종목의 시계열 칸(validate_data.PX_BAD_DATA)을 모두 지우고 pxBad = 가장 최근 움직임 날짜 · krSeries.hidden.
- 추세(mz) · 저변동(lz) 점수는 그 종목 없이 매겨요 (add_percentiles 가 빈 칸을 빼요) · 필수 종목은 꼭 들어 있어야 해요.
- corp.json(build_corp) 도 같은 표시 · 같은 칸이 비어요.
- 관문: '과거 주가 기록 오류 종목의 숫자 비움 (pxBad)' (실패 · 그 전 형식만 경고) · '필수 종목 추세 · 저변동 순위 (mz · lz)' (실패)."""
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
SERIES = {"hi": 6760.0, "lo": 280.0, "vol": 88.1, "beta": 0.54, "betaSE": 0.84, "betaN": 755, "al": -12.3, "r1": -0.7, "r3": -29.9,
          "r36": 44.1, "mom": 206.4, "sh": 0.01, "mdd": -84.6, "hit": 32, "mz": 99, "lz": 3}
KEEP = {"price": 1881.0, "cap": 0.048, "d1": -0.21, "val": 0.8, "val20": 2.0, "pbr": 0.8, "roe": -44.3, "dps": 0.0, "dy": 0.0, "dyt": 0.0,
        "pz": 76, "vz": 48, "qz": 6, "dz": 25, "shr": 25650015, "fy": 2025}


def kr(t, nk, **kw):
    return {"t": t, "nk": nk, "ne": nk, "cls": "kr", "s": "bio", **KEEP, **SERIES, **kw}


def series(jump):
    return {"v": 1, "days": 19, "pinned": 39943, "pinStocks": 2343, "kept": {"basis": 157, "far": 8, "shr": 0}, "keptStocks": 23,
            "bad": 0, "badStocks": [], "ref": {"breakStocks": 18, "unknownStocks": 0, "newStocks": 14}, "jump": jump}


# ── 1. 비우는 칸 목록 = 시계열로 만드는 칸 모두 ─────────────────────
def test_the_blank_list_is_every_number_the_series_makes_and_nothing_else():
    """fetch_korea 가 px(그 시계열)로 만드는 칸 · perf_stats 가 만드는 칸 · 그 칸으로 매기는 점수 — 하나도 빠지지 않아요. 가격 · 시가총액 ·
    d1(공식 종가끼리) · 거래대금 · 재무 · 배당과 그 점수는 시계열이 아니라서 남겨요."""
    src = inspect.getsource(F.fetch_korea)
    rec = src[src.index("rec = {"):src.rindex("hilo_note(code, px, rec)")]
    from_px = {"vol", "beta", "al", "betaSE", "betaN", "lo", "hi"}
    for k in from_px:
        assert f'"{k}":' in rec, k
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
    # 실제로 돌려 봐도: 표시 없는 종목의 시계열 칸 중 corp.json 에 실리는 것 = PX_BAD_CORP (어느 길로 가든)
    row = F.build_corp([kr("005930", "삼성전자")], {}, "2026-11-14")["companies"][0]
    assert {k for k in V.PX_BAD_DATA if row.get(k) is not None} == set(V.PX_BAD_CORP), row


# ── 2. 표시 · 비움 ───────────────────────────────────────────
def test_mark_blanks_every_series_number_and_marks_the_latest_move(capsys):
    a, b, c = kr("007460", "에이프로젠"), kr("012170", "아센디오"), kr("005930", "삼성전자")
    before = copy.deepcopy(c)
    ks = series([["007460", "2026-05-08", 1446.1, "halt"], ["012170", "2025-03-06", 797.8, "halt"], ["012170", "2026-08-28", 395.3, "halt"]])
    got = F.mark_px_bad([a, b, c], ks)
    assert got["hidden"] == ["007460", "012170"] and ks["hidden"] == ["007460", "012170"] and got["missing"] == []
    assert a["pxBad"] == "2026-05-08" and b["pxBad"] == "2026-08-28"            # 한 종목에 여러 번이면 가장 최근 날짜
    for s in (a, b):
        assert not set(V.PX_BAD_DATA) & set(s), s
        assert {k: s[k] for k in KEEP} == KEEP                                     # 가격 · 시가총액 · d1 · 재무 · 배당과 그 점수는 그대로
    assert c == before                                                              # 다른 종목은 그대로
    assert got["fields"] == {k: 2 for k in V.PX_BAD_DATA}
    json.dumps([a, b, c, ks], allow_nan=False)
    out = capsys.readouterr().out
    assert "  !! 과거 주가 기록 오류(하루 가격 제한폭 넘는 움직임)로 52주 · 출렁임 · 위험 숫자를 비운 국내 종목: 2 — 007460 에이프로젠 (2026-05-08), " \
           "012170 아센디오 (2026-08-28)" in out


def test_mark_counts_only_the_numbers_that_were_there_and_never_leaves_an_old_mark(capsys):
    a = kr("007460", "에이프로젠")
    del a["vol"], a["lz"], a["al"]                                                 # 변동성 300% 넘게 → 원래 빈 칸 (ann_vol)
    old = kr("000660", "SK하이닉스", pxBad="2026-01-02")                           # 어제 표시 · 오늘 jump 에 없음 → 표시를 떼고 숫자는 그대로
    ks = series([["007460", "2026-05-08", 1446.1, "halt"]])
    got = F.mark_px_bad([a, old], ks)
    assert "vol" not in got["fields"] and got["fields"]["beta"] == 1 and got["hidden"] == ["007460"]
    assert "pxBad" not in old and old["mom"] == SERIES["mom"]
    assert "비운 칸: hi 1 · lo 1 · beta 1 · betaSE 1 · betaN 1 · r1 1" in capsys.readouterr().out


def test_mark_with_nothing_named_is_quiet_and_writes_an_empty_list(capsys):
    a = kr("005930", "삼성전자")
    ks = series([])
    got = F.mark_px_bad([a], ks)
    assert got == {"hidden": [], "fields": {}, "missing": []} and ks["hidden"] == [] and "pxBad" not in a and a["mom"] == SERIES["mom"]
    out = capsys.readouterr().out
    assert "· 과거 주가 기록 오류(하루 가격 제한폭 넘는 움직임)로 52주 · 출렁임 · 위험 숫자를 비운 국내 종목: 0" in out and "!!" not in out


def test_a_named_code_that_is_not_published_is_loud(capsys):
    ks = series([["999990", "2025-01-02", 99.0, "other"]])
    got = F.mark_px_bad([kr("005930", "삼성전자")], ks)
    assert got["hidden"] == [] and got["missing"] == ["999990"] and ks["hidden"] == []
    assert "  !! " in capsys.readouterr().out


def test_us_stocks_are_never_marked():
    us = {"t": "AAPL", "cls": "us", **SERIES}
    ks = series([["AAPL", "2026-05-08", 50.0, "other"]])
    F.mark_px_bad([us], ks)
    assert "pxBad" not in us and us["mom"] == SERIES["mom"] and ks["hidden"] == []


def test_fetch_korea_marks_before_it_returns_and_main_ranks_after():
    """fetch_korea: 점검(kr_series_check) 바로 다음에 비우고, 그 뒤에 meta 를 만들어요 — krSeries 를 싣는 길은 늘 비운 뒤예요.
    main: 점수(add_percentiles)와 corp.json(build_corp)은 그 뒤라 빈 칸을 그대로 받아요. 필수 종목 순위 줄도 점수 바로 뒤예요."""
    src = inspect.getsource(F.fetch_korea)
    i_ks = src.index("krs = kr_series_check(")
    i_mark = src.index("mark_px_bad(out, krs)")
    assert i_ks < i_mark < src.index("meta = {") and src.count("mark_px_bad(") == 1
    main = inspect.getsource(F.main)
    i_kr = main.index('ph.run("국내 시세", fetch_korea')
    i_pct = main.index("add_percentiles(kr)")
    assert i_kr < i_pct < main.index("miss_tr = trend_rank_missing(kr)") < main.index("build_corp(kr, fin_map")
    assert '"krSeries": kmeta.get("krSeries")' in main


# ── 3. 점수 · 순위는 그 종목 없이 ─────────────────────────────
def test_trend_and_low_volatility_scores_are_made_without_the_marked_stocks():
    rnd = np.random.default_rng(3)
    stocks = [kr(f"{100000 + 10 * i:06d}", f"종목{i}", mom=float(m), vol=float(v)) for i, (m, v) in
              enumerate(zip(rnd.normal(10, 40, 60).round(1), rnd.uniform(15, 90, 60).round(1)))]
    for s in stocks:
        s.pop("mz"), s.pop("lz")
    stocks[0].update(mom=1446.1, vol=5.0)                                          # 망가진 시계열: 추세 1위 · 변동성 꼴찌 (저변동 1위)처럼 보여요
    stocks[1].update(mom=-91.4, vol=400.0)
    ks = series([["100000", "2026-05-08", 1446.1, "halt"], ["100010", "2024-04-17", -91.4, "halt"]])
    F.mark_px_bad(stocks, ks)
    F.add_percentiles(stocks)
    rest = copy.deepcopy(stocks[2:])
    for s in rest:
        s.pop("mz", None), s.pop("lz", None)
    F.add_percentiles(rest)                                                        # 그 두 종목을 아예 빼고 매긴 점수
    assert all("mz" not in s and "lz" not in s for s in stocks[:2])
    assert [(s["mz"], s["lz"]) for s in stocks[2:]] == [(s["mz"], s["lz"]) for s in rest]
    top = max(stocks[2:], key=lambda s: s["mom"])
    calm = min(stocks[2:], key=lambda s: s["vol"])
    assert top["mz"] == 100 and calm["lz"] == max(s["lz"] for s in stocks[2:])     # 1위는 남은 종목 중에서


def test_must_have_stocks_stay_in_the_trend_and_low_volatility_ranks():
    must = [kr(t, t, mz=50, lz=50) for t in F.DIV_RANK_MUST]
    assert F.trend_rank_missing(must) == []
    gone = copy.deepcopy(must)
    F.mark_px_bad(gone, series([["005380", "2026-05-08", 50.0, "other"]]))
    F.add_percentiles(gone)
    assert F.trend_rank_missing(gone) == [("005380", "mz·lz 없음 — 과거 주가 기록 오류 (pxBad 2026-05-08)")]
    assert F.trend_rank_missing(must[1:]) == [(must[0]["t"], "데이터에 없음")]
    assert list(F.DIV_RANK_MUST) == list(V.MUST)                                  # 관문의 필수 종목과 같아요


# ── 4. corp.json ─────────────────────────────────────────────
def test_corp_json_carries_the_mark_and_the_same_blanks():
    a, c = kr("007460", "에이프로젠"), kr("005930", "삼성전자")
    F.mark_px_bad([a, c], series([["007460", "2026-05-08", 1446.1, "halt"]]))
    rows = {r["t"]: r for r in F.build_corp([a, c], {}, "2026-11-14")["companies"]}
    assert rows["007460"]["pxBad"] == "2026-05-08" and "pxBad" not in rows["005930"]
    assert all(rows["007460"].get(k) is None for k in V.PX_BAD_CORP)
    assert all(rows["005930"].get(k) == SERIES[k] for k in V.PX_BAD_CORP)
    assert rows["007460"]["price"] == KEEP["price"] and rows["007460"]["pz"] == KEEP["pz"]
    json.dumps(rows, allow_nan=False)
    assert "pxBad" in F.UNITS and "hidden" in F.UNITS["krSeries"]


# ── 5. 관문 ──────────────────────────────────────────────────
JUMP = [["200100", "2026-05-08", 1446.1, "halt"], ["200110", "2025-03-06", 797.8, "halt"], ["200110", "2026-08-28", 395.3, "halt"]]


def marked_pair(jump=JUMP, prev_hidden=True):
    """good_pair 에 파이프라인처럼: krSeries (jump · hidden) · 그 종목의 시계열 칸을 지우고 pxBad · corp.json 도 같게. 직전 발행본도 새 형식."""
    cur, prev, final = good_pair()
    stocks = cur["data"]["stocks"]
    by = {s["t"]: s for s in stocks}
    assert all(j[0] in by for j in jump)
    for s in stocks:
        if s.get("cls") == "kr":
            s.update({k: v for k, v in SERIES.items() if k not in s and k not in ("mz", "lz")})
    ks = series(copy.deepcopy(jump))
    F.mark_px_bad([s for s in stocks if s.get("cls") == "kr"], ks)
    cur["data"]["krSeries"] = ks
    for c in cur["corp"]["companies"]:
        s = by[c["t"]]
        c.update({k: s.get(k) for k in V.PX_BAD_CORP})
        if s.get("pxBad"):
            c["pxBad"] = s["pxBad"]
    prev["data"]["krSeries"] = series([])
    if prev_hidden:
        prev["data"]["krSeries"]["hidden"] = []
    return cur, prev, final


def row(rep, name):
    return next(r for r in rep.rows if r[0] == name)


def test_gate_passes_the_marked_publish():
    cur, prev, final = marked_pair()
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    r = row(rep, NAME)
    assert r[3] == "PASS" and r[1].startswith("2종목 · 문제 0 — 200100 ") and "(2026-05-08)" in r[1] and "(2026-08-28)" in r[1], r
    assert row(rep, MUST_NAME)[3] == "PASS" and row(rep, MUST_NAME)[1] == "모두 있음"
    assert any(t.startswith("과거 주가 기록 오류로 52주") for t, _ in rep.details)
    assert not check(cur, None, final, mode="live").failed


def test_gate_passes_a_day_with_nothing_named():
    cur, prev, final = marked_pair(jump=[])
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "PASS" and row(rep, NAME)[1] == "0종목 · 문제 0"


def _drop(xs, t):
    xs.remove(t)


@pytest.mark.parametrize("how", [
    "not hidden", "hidden but not named", "no mark", "mark but not hidden", "older date", "date shape", "date empty", "date bool",
    "corp mark missing", "corp mark differs", "corp only mark", "hidden not a list", "hidden duplicate", "hidden number", "us mark",
] + [f"left {k}" for k in V.PX_BAD_DATA] + [f"corp left {k}" for k in V.PX_BAD_CORP])
def test_gate_fails_when_a_named_stock_still_shows_a_number_or_the_marks_disagree(how):
    """must-fail: 그 종목에 숫자가 하나라도 남았거나 (data.json · corp.json), jump · hidden · pxBad 표시가 서로 다르면 발행하지 않아요."""
    cur, prev, final = marked_pair()
    ks = cur["data"]["krSeries"]
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    cby = {c["t"]: c for c in cur["corp"]["companies"]}
    a, other = by["200100"], by["200200"]
    if how == "not hidden":
        _drop(ks["hidden"], "200100")
        del a["pxBad"], cby["200100"]["pxBad"]
    elif how == "hidden but not named":
        ks["jump"] = [j for j in ks["jump"] if j[0] != "200100"]
    elif how == "no mark":
        del a["pxBad"]
    elif how == "mark but not hidden":
        other["pxBad"] = "2026-05-08"
        for k in V.PX_BAD_DATA:
            other.pop(k, None)
    elif how == "older date":
        by["200110"]["pxBad"] = cby["200110"]["pxBad"] = "2025-03-06"
    elif how == "date shape":
        a["pxBad"] = cby["200100"]["pxBad"] = "2026/05/08"
    elif how == "date empty":
        a["pxBad"] = cby["200100"]["pxBad"] = ""
    elif how == "date bool":
        a["pxBad"] = cby["200100"]["pxBad"] = True
    elif how == "corp mark missing":
        del cby["200100"]["pxBad"]
    elif how == "corp mark differs":
        cby["200100"]["pxBad"] = "2026-05-07"
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
    elif how.startswith("left "):
        a[how.split()[1]] = 1.0
    else:
        cby["200100"][how.split()[2]] = 1.0
    rep = check(cur, prev, final)
    assert NAME in failed_names(rep), (how, rep.table())
    assert MUST_NAME not in failed_names(rep)


def test_gate_value_names_the_problem():
    cur, prev, final = marked_pair()
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    by["200100"]["hi"] = 6760.0
    r = row(check(cur, prev, final), NAME)
    assert r[3] == "FAIL" and "문제 1 (200100 남은 칸 hi)" in r[1], r


def test_gate_old_format_only_warns_until_the_first_marked_publish():
    """krSeries.hidden 이 없는 파일 (2026-11-14 숨김 전 · 머지 뒤 첫 발행 전까지의 사이트 --live): 경고만 (배포가 막히지 않아요).
    직전 발행본에 hidden 이 있었거나 pxBad 표시가 있으면 실패 (비우는 단계가 돌지 않았어요)."""
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
    cur, prev, final = good_pair()                                                 # krSeries 자체가 없어요 (그 전 형식): 경고만
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, NAME)[3] == "WARN" and row(rep, NAME)[1].startswith("krSeries 없음")


@pytest.mark.parametrize("t", list(V.MUST))
def test_gate_fails_when_a_must_have_stock_leaves_the_trend_or_low_volatility_rank(t):
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == t)
    del s["mz"]
    rep = check(cur, prev, final)
    assert MUST_NAME in failed_names(rep), rep.table()
    assert row(rep, MUST_NAME)[1] == f"빠짐: {t} {s['nk']} mz — 1년 수익률(mom) 없음", row(rep, MUST_NAME)   # 시험 데이터엔 mom 이 없어요
    s["mom"] = 12.0
    assert row(check(cur, prev, final), MUST_NAME)[1] == f"빠짐: {t} {s['nk']} mz — mz 없음 (mom 있음)"


def must_hilo(files):
    """'야후'의 52주 범위와 d1 (비우기 전 값으로 — 필수 종목의 52주를 비우면 그 줄이 무엇을 하는지 보려고)."""
    by = {x["t"]: x for x in files["data"]["stocks"]}
    return {t: {"hi": by[t]["hi"], "lo": by[t]["lo"], "d1": by[t].get("d1", 0.0)} for t in V.MUST if t in by}


def test_gate_one_marked_must_have_only_warns_in_the_new_row():
    """리뷰 #126 (Jack 2026-11-13: 출처의 작은 문제가 모두의 발행을 막지 않게 · 11-05 배당 순위와 같은 틀): 맞게 표시한 필수 종목 하나는 이 줄에서
    경고 (이름 · 이유). 다만 지금은 예전 두 줄('필수 종목 52주 최고·최저 (야후)' · '필수 종목 새 칸')이 그대로 막아요 — 그 예외는 Jack 의 답을
    기다려요 (이 시험은 그 두 줄을 바꾸지 않았다는 것도 지켜요)."""
    cur, prev, final = good_pair()
    hilo = must_hilo(cur)
    cur, prev, final = marked_pair(jump=JUMP + [["005930", "2026-01-02", 60.0, "spike"]])
    rep = check(cur, prev, final, hilo=hilo)
    r = row(rep, MUST_NAME)
    assert r[3] == "WARN" and r[1] == ("과거 주가 기록 오류로 뺀 필수 종목 1: 005930 삼성전자 mz·lz — 과거 주가 기록 오류 (pxBad 2026-01-02)"
                                       " (52주 · 새 칸 줄은 아직 막아요)"), r
    assert row(rep, NAME)[3] == "PASS"                                             # 비우기 자체는 맞게 됐어요
    # 예전 줄은 그대로 막아요: 52주 (야후) — '필수 종목 새 칸' 줄은 divCheck 가 있는 실제 발행에서만 돌아요 (베타 표준오차가 빈 칸이라 그 줄도 막아요)
    assert failed_names(rep) == {"필수 종목 52주 최고·최저 (야후)"}, failed_names(rep)
    assert "005930 없음" in row(rep, "필수 종목 52주 최고·최저 (야후)")[1]


def test_gate_two_marked_must_haves_fail():
    cur, prev, final = marked_pair(jump=JUMP + [["005930", "2026-01-02", 60.0, "spike"], ["005380", "2025-12-01", -45.0, "other"]])
    r = row(check(cur, prev, final, hilo=None), MUST_NAME)
    assert r[3] == "FAIL" and r[1].startswith("과거 주가 기록 오류로 뺀 필수 종목 2: 005930 삼성전자 mz·lz") and "005380 현대차 mz·lz" in r[1], r


@pytest.mark.parametrize("how", ["corp mark missing", "left beta", "corp left betaSE", "not hidden", "other date"])
def test_gate_a_must_have_whose_mark_is_wrong_fails(how):
    """표시가 맞지 않는 필수 종목 (hidden 에 없음 · 숫자가 남음 · corp.json 이 다름 · 날짜가 다름): 이 줄도 실패 (경고가 아니에요)."""
    cur, prev, final = marked_pair(jump=JUMP + [["005930", "2026-01-02", 60.0, "spike"]])
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
    rep = check(cur, prev, final, hilo=None)
    r = row(rep, MUST_NAME)
    assert r[3] == "FAIL" and r[1].startswith("빠짐: 005930 삼성전자 mz·lz — pxBad ") and "표시가 맞지 않아요" in r[1], (how, r)
    assert NAME in failed_names(rep)


def test_gate_must_have_without_a_mark_fails_and_names_a_missing_stock():
    cur, prev, final = good_pair()
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "005930")
    del s["mz"], s["lz"]
    r = row(check(cur, prev, final), MUST_NAME)
    assert r[3] == "FAIL" and r[1] == "빠짐: 005930 삼성전자 mz·lz — 1년 수익률(mom) 없음 · lz 없음 (vol 있음)", r
    cur, prev, final = good_pair()
    cur["data"]["stocks"] = [s for s in cur["data"]["stocks"] if s["t"] != "035420"]
    assert "035420 데이터에 없음" in row(check(cur, prev, final), MUST_NAME)[1]
    assert V.PX_BAD_MUST_FAIL == 2


def test_gate_and_pipeline_agree_on_todays_named_stocks_from_the_real_fixture():
    """tests/fixtures/kr_pin_samples.json (2026-11-14 실제 자료)의 종목으로: 파이프라인이 표시한 대로면 관문이 통과해요."""
    with open(os.path.join(ROOT, "tests", "fixtures", "kr_pin_samples.json"), encoding="utf-8") as f:
        fx = json.load(f)
    codes = sorted(fx["listing"])
    stocks = [kr(c, c) for c in codes]
    jump = [[c, "2026-05-08", 100.0, "halt"] for c in codes[:3]]
    ks = series(jump)
    F.mark_px_bad(stocks, ks)
    corp = F.build_corp(stocks, {}, "2026-11-14")["companies"]
    probs = V.px_bad_problems(stocks, corp, ks)
    assert probs == [] and ks["hidden"] == codes[:3]
    assert all(math.isfinite(x) for s in stocks for x in s.values() if isinstance(x, float))
