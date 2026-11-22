# -*- coding: utf-8 -*-
"""2026-11-22 (Jack, verbatim): "2. No relaxation. Instead, a stock newly added to the S&P (or NASDAQ) list joins our list only once
it has a confirmed close; until then it isn't added. Nobody can hold it in the app before it joins, so nothing is lost, and the check
stays as it is."

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 관문 validate_data.py 는 그대로):
- 파이프라인 (fetch_data.us_new_wait · us_new_wait_step · fetch_us): 지난 발행본의 미국 종목 행에도 usSrc.own.aged 에도 없는 티커가 미국 기준일
  종가가 야후에 없으면 (기준일 봉이 비거나 0 · 더 오래된 봉만) 오늘 목록에 넣지 않아요 — 크게 남기고 usSrc.newWait · 빠진 까닭 (EXTRA_US ·
  주식 종류 티커 · S&P 500 기록). 종가가 확인되면 다른 종목처럼 들어와요. 지난 발행본에 있던 종목 · 잠시 뺀 종목은 #165 그대로 · 지난 발행본이
  없으면 예전 그대로 · 기다리는 종목은 분할 목록으로도 파일에 들어가지 않아요 · 야후가 다 준 보통 날은 이 단계가 없던 때와 같은 결과
- 관문: 손으로 더한 종목이 기다리면 그 줄은 경고 (까닭이 적혀서) · 2026-11-21 의 모양 (지난 발행본의 종목은 모두 마지막 확인 종가 + 지난 발행본에
  없던 4종목의 기준일 봉이 빔) → '미국 d1 채움' 의 빠짐 0 · 6종목이어도 발행이 멈추지 않아요 (이 단계가 없으면 멈췄어요)
"""
import copy
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_us_own_close import _fake_yf, us  # noqa: E402

D18, D19 = "2026-11-18", "2026-11-19"
WAIT = F.US_NEW_WAIT_WHY
D1_ROW = "미국 d1 채움 (미국 기준일 봉)"
EXTRA_ROW = "손으로 더한 미국 종목 (EXTRA_US): 목록에 있거나 빠진 이유"
OWN_ROW = "미국 마지막 확인 종가 (usSrc.own · pxc)"
NEW_1121 = ["LGND", "MKTX", "SNDK", "VRNS"]          # 2026-11-21 시험 실행 44849045557 에서 지난 발행본에 없던 4종목


def rows_of(rep):
    return {r[0]: (r[3], r[1]) for r in rep.rows}


# ── 1. 순수 함수 ─────────────────────────────────────────────────────────────
def test_the_rule_waits_only_for_tickers_the_previous_publish_did_not_know():
    prev = {"usPxDate": D18, "stocks": [us("AAPL"), us("MSFT"), {"t": "069500", "cls": "kr", "price": 1.0}],
            "usSrc": {"v": 1, "own": {"v": 1, "aged": [{"t": "OLD", "nk": "OLD", "pxd": "2026-11-05"}]}},
            "usLeftOut": {"preferred": ["PFD"], "krListing": [], "badBar": []}}
    nocl = {"NEW": "bar", "AAPL": "bar", "OLD": "bar", "EMP": "empty", "ERR": "err"}
    out = [us("AAPL", d1=None, pxd=D18), us("NEW", d1=None, pxd=D18), us("OLD", d1=None, pxd=D18), us("JOIN"), us("PFD"), us("MSFT")]
    r = F.us_new_wait(prev, nocl, out)
    assert r == {"wait": ["NEW"], "left": [], "joined": ["JOIN"], "off": None}, r   # 지난 발행본의 종목 · 잠시 뺀 종목은 #165 · 가격이 없는 새 티커는 예전 그대로
    # 리뷰 (2026-11-22): clean_us_list 가 매일 빼는 티커 (usLeftOut.preferred · krListing) 만 기다리지 않아요 — 예전 길 그대로.
    # 검증 리뷰 (11-22): badBar 나 앞으로 생길 목록은 예외가 아니에요 (Jack 의 규칙대로 기다려요)
    lo = {**prev, "usLeftOut": {"preferred": ["PFD"], "krListing": ["SKHY"], "badBar": ["XBAD"], "later": ["ODD"]}}
    r2 = F.us_new_wait(lo, {"NEW": "bar", "PFD": "bar", "SKHY": "bar", "XBAD": "bar", "ODD": "bar"}, out)
    assert r2["wait"] == ["NEW", "ODD", "XBAD"] and r2["left"] == ["PFD", "SKHY"], r2
    for bad in (None, [], {"stocks": None}, {"stocks": [{"t": "069500", "cls": "kr"}]}, {"stocks": [us("X", fund=True)]}):
        got = F.us_new_wait(bad, {"NEW": "bar"}, out)
        assert got["wait"] == [] and got["left"] == [] and got["joined"] == [] and got["off"], (bad, got)   # 무엇이 새로 들어왔는지 알 수 없어요 → 예전 그대로
    # 모양이 틀린 aged 기록은 아는 티커가 아니에요 (그 종목은 기다려요 — 틀린 숫자 대신 빠짐)
    weird = {**prev, "usSrc": {"v": 1, "own": {"aged": "x"}}}
    assert F.us_new_wait(weird, {"OLD": "bar"})["wait"] == ["OLD"]


def test_the_step_removes_the_row_writes_the_reason_and_logs(monkeypatch):
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    prev = {"usPxDate": D18, "stocks": [us("AAPL")]}
    out = [us("AAPL", d1=None, pxd=D18), us("NEW", d1=None, pxd=D18), us("JOIN")]
    nocl, why = {"AAPL": "bar", "NEW": "bar"}, {}
    wait = F.us_new_wait_step(prev, nocl, out, why, dt.date(2026, 11, 19))
    assert wait == ["NEW"] and [r["t"] for r in out] == ["AAPL", "JOIN"] and nocl == {"AAPL": "bar"} and why == {"NEW": WAIT}
    assert any(x.startswith("  !! 새로 들어온 미국 종목 1 (지난 발행본에 없고 미국 기준일 2026-11-19 종가가 야후에 없음): NEW")
               and "미국 기준일 종가가 확인되면 넣어요" in x for x in lines), lines
    assert any(x.startswith("· 새로 들어온 미국 종목 중 미국 기준일 2026-11-19 종가가 있어 오늘 들어감 1: JOIN") for x in lines), lines
    # 보통 날: 한 줄 (· ) · 아무것도 바꾸지 않아요
    lines.clear()
    out2, nocl2, why2 = [us("AAPL"), us("JOIN")], {}, {}
    assert F.us_new_wait_step(prev, nocl2, out2, why2, dt.date(2026, 11, 19)) == [] and out2 == [us("AAPL"), us("JOIN")] and why2 == {}
    assert lines == ["· 새로 들어온 미국 종목 (지난 발행본에 없던 티커): 미국 기준일 2026-11-19 종가가 있어 오늘 들어감 1: JOIN · 종가를 기다림 0"]
    # 지난 발행본이 없음: 예전 그대로 · 크게 남겨요
    lines.clear()
    out3, nocl3 = [us("NEW", d1=None, pxd=D18)], {"NEW": "bar"}
    assert F.us_new_wait_step(None, nocl3, out3, {}, dt.date(2026, 11, 19)) == [] and [r["t"] for r in out3] == ["NEW"] and nocl3 == {"NEW": "bar"}
    assert len(lines) == 1 and lines[0].startswith("  !! 지난 발행본이 없거나 읽지 못했어요") and "종가가 없는 1종목은 야후의 마지막 봉 날짜로" in lines[0]
    # 지난 발행본이 없고 기준일 종가가 없는 종목도 없음: 그래도 크게 (리뷰 2026-11-22 · 예전 그대로라는 것을)
    lines.clear()
    assert F.us_new_wait_step(None, {}, [us("AAPL")], {}, dt.date(2026, 11, 19)) == []
    assert len(lines) == 1 and lines[0].startswith("  !! 지난 발행본이 없거나 읽지 못했어요") and "종가가 없는 0종목" in lines[0], lines
    # 가리다 멈춤: 예전 그대로 · 크게 남겨요 (발행은 멈추지 않아요)
    lines.clear()
    real = F.us_new_wait
    monkeypatch.setattr(F, "us_new_wait", lambda *a, **k: 1 / 0)
    out4, nocl4 = [us("NEW", d1=None, pxd=D18)], {"NEW": "bar"}
    assert F.us_new_wait_step(prev, nocl4, out4, {}, dt.date(2026, 11, 19)) == [] and len(out4) == 1 and nocl4 == {"NEW": "bar"}
    assert lines and lines[0].startswith("  !! 새로 들어온 미국 종목을 가리다 오류로 멈췄어요 (ZeroDivisionError")
    monkeypatch.setattr(F, "us_new_wait", real)
    # 행을 뺀 뒤에 멈춰도 (리뷰 2026-11-22): 바꾼 것을 모두 되돌려요 — out · nocl · why 가 단계 앞과 같아요
    class Boom(dict):
        def __setitem__(self, k, v):
            raise KeyError("boom")
    lines.clear()
    out5, nocl5, why5 = [us("AAPL", d1=None, pxd=D18), us("NEW", d1=None, pxd=D18)], {"AAPL": "bar", "NEW": "bar"}, Boom(x="kept")
    before = (copy.deepcopy(out5), dict(nocl5), dict(why5))
    assert F.us_new_wait_step(prev, nocl5, out5, why5, dt.date(2026, 11, 19)) == []
    assert (out5, nocl5, dict(why5)) == before, (out5, nocl5, why5)
    assert lines and lines[-1].startswith("  !! 새로 들어온 미국 종목을 가리다 오류로 멈췄어요 (KeyError")


def test_the_step_says_so_when_a_waiting_ticker_had_no_row(monkeypatch):
    """'bar' 종목은 늘 행이 있어요 — 아니면 크게 남겨요 (그래도 기다리는 종목은 빠져요 · 리뷰 2026-11-22)."""
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    out = [us("AAPL"), us("NEW", d1=None, pxd=D18)]
    nocl, why = {"NEW": "bar", "GHOST": "bar"}, {}
    assert F.us_new_wait_step({"stocks": [us("AAPL")]}, nocl, out, why, dt.date(2026, 11, 19)) == ["GHOST", "NEW"]
    assert [r["t"] for r in out] == ["AAPL"] and nocl == {} and why == {"GHOST": WAIT, "NEW": WAIT}
    assert any(x == "  !! 새로 들어온 미국 종목 2 중 뺀 행이 1개예요 (종목마다 한 행이어야 해요 — fetch_us 의 nocl · 행을 확인해 주세요)"
               for x in lines), lines


# ── 2. fetch_us 를 가짜 야후로 ─────────────────────────────────────────────────
def _run(tmp_path, monkeypatch, syms, prev_t=None, blank=(), aged=None, prev_usd=D18, splits=None, sp500=None, tag="a", step=True, quote=None,
         kr_codes=frozenset(), dups=None, prev_extra=None):
    """syms: 오늘 미국 목록 · prev_t: 지난 발행본의 미국 종목 (None = 지난 발행본 없음) · blank: 기준일(11-19) 봉이 빈 종목 ·
    aged: 지난 발행본의 usSrc.own.aged · sp500: 가짜 S&P 500 목록 (주면 겹침 기준을 작게) · step=False: 새 단계를 끈 결과 (예전과 같은지 맞춰 봐요)."""
    today_us = dt.date(2026, 11, 19)
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)

    def walk(seed, last):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * last / float(s.iloc[-1])
    series = {"_spx": walk(1, 6700.0)}
    for i, t in enumerate(syms):
        s = walk(10 + i, 100.0 + i)
        if t in blank:
            s.iloc[-1] = np.nan                                       # 야후가 기준일 봉을 비움 (더 오래된 봉만 있어요)
        series[t] = s
    prev = None
    if prev_t is not None:
        prev = {"pxDate": prev_usd, "usPxDate": prev_usd, "stocks": [us(t, price=50.0 + i, d1=0.3) for i, t in enumerate(prev_t)]}
        if aged is not None:
            prev["usSrc"] = {"v": 1, "own": {"v": 1, "n": 0, "codes": [], "same": [], "aged": aged}}
        prev.update(prev_extra or {})

    def tickers(names):
        if sp500 is not None and hasattr(names, "sp500"):
            names.sp500 = frozenset(sp500)
        return list(syms)
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(series, quote or {t: 60.0 for t in syms}, splits))
    monkeypatch.setattr(F, "us_tickers", tickers)
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today_us)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / f"us-info-{tag}.json.gz"))
    if sp500 is not None:
        monkeypatch.setattr(F, "US_SP500_MIN", 1)                     # 가짜 목록은 몇 종목뿐이라 겹침 기준을 작게 (실제 400)
    if not step:
        monkeypatch.setattr(F, "us_new_wait_step", lambda prev, nocl, out, why, d: [])
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    today = today_us + dt.timedelta(days=1)
    out, *_rest, meta = F.fetch_us(today - dt.timedelta(days=500), today, 0.03, kr_codes=kr_codes, dups=dups or {}, prev=copy.deepcopy(prev))
    meta.pop("_index")
    json.dumps(meta, allow_nan=False, ensure_ascii=False)
    json.dumps(out, allow_nan=False, ensure_ascii=False)
    return out, meta, lines, prev


BASE = ["AAPL", "MSFT", "NVDA", "SHEL", "TD"]


def test_a_new_ticker_without_a_close_is_not_added_and_is_recorded(tmp_path, monkeypatch):
    syms = BASE + ["LGND", "MKTX"]
    out, meta, lines, _p = _run(tmp_path, monkeypatch, syms, prev_t=BASE, blank={"MSFT", "LGND"}, sp500=syms)
    by = {r["t"]: r for r in out}
    assert "LGND" not in by                                                          # 새 종목 · 기준일 종가 없음 → 오늘은 넣지 않아요
    assert by["MKTX"].get("d1") is not None and "pxd" not in by["MKTX"] and "pxc" not in by["MKTX"]   # 새 종목 · 종가 있음 → 들어와요
    assert by["MSFT"]["pxc"] is True and by["MSFT"]["pxd"] == D18                    # 지난 발행본에 있던 종목: #165 그대로
    src = meta["usSrc"]
    assert src["newWait"] == ["LGND"] and src["own"]["codes"] == ["MSFT"] and src["own"]["drop"] == {} and src["own"]["unconf"] == 1
    assert meta["usListSym"]["spGone"] == {"LGND": WAIT} and meta["usListSym"]["noPx"] == []      # S&P 500 중 빠진 종목의 까닭
    assert "LGND" not in meta["usInfoPartial"] and meta["usInfo"][1] == len(out)
    assert any(x.startswith("  !! 새로 들어온 미국 종목 1 (") and ": LGND —" in x for x in lines), lines
    assert any(x.startswith("· 새로 들어온 미국 종목 중 미국 기준일 2026-11-19 종가가 있어 오늘 들어감 1: MKTX") for x in lines), lines


def test_the_waiting_ticker_joins_on_the_first_run_with_a_confirmed_close(tmp_path, monkeypatch):
    syms = BASE + ["LGND"]
    out, meta, lines, _p = _run(tmp_path, monkeypatch, syms, prev_t=BASE, blank=set())
    lg = {r["t"]: r for r in out}["LGND"]
    assert lg.get("d1") is not None and "pxd" not in lg and "pxc" not in lg and lg["price"] > 0
    assert "newWait" not in meta["usSrc"]
    assert any(x.startswith("· 새로 들어온 미국 종목 (지난 발행본에 없던 티커): 미국 기준일 2026-11-19 종가가 있어 오늘 들어감 1: LGND · 종가를 기다림 0")
               for x in lines), lines


def test_previous_and_aged_tickers_keep_the_165_path(tmp_path, monkeypatch):
    """지난 발행본에 있던 종목은 마지막 확인 종가로 · 잠시 뺀 종목(지난 발행본의 stocks 에는 없음)은 더 새 야후 봉이 있으면 그 종가로 돌아와요 —
    새 단계를 끈 결과와 똑같아요 (기다리는 종목이 없으면 이 단계는 아무것도 바꾸지 않아요)."""
    syms = BASE + ["BP"]
    aged = [{"t": "BP", "nk": "BP plc", "pxd": "2026-11-05"}]
    kw = dict(prev_t=BASE, blank={"AAPL", "BP"}, aged=aged)
    out, meta, lines, _p = _run(tmp_path, monkeypatch, syms, tag="a", **kw)
    by = {r["t"]: r for r in out}
    assert by["AAPL"]["pxc"] is True and by["AAPL"]["pxd"] == D18
    assert by["BP"]["pxc"] is True and by["BP"]["pxd"] == D18 and meta["usSrc"]["own"]["newer"][0]["t"] == "BP"
    assert "newWait" not in meta["usSrc"] and meta["usSrc"]["own"]["aged"] == []
    out0, meta0, _l, _p = _run(tmp_path, monkeypatch, syms, tag="b", step=False, **kw)
    assert out == out0 and meta == meta0


def test_no_previous_publish_keeps_todays_behaviour(tmp_path, monkeypatch):
    syms = BASE + ["LGND"]
    out, meta, lines, _p = _run(tmp_path, monkeypatch, syms, prev_t=None, blank={"LGND"}, tag="a")
    lg = {r["t"]: r for r in out}["LGND"]
    assert lg["pxd"] == D18 and "pxc" not in lg and "d1" not in lg                    # 예전 그대로: 야후의 마지막 봉을 자기 날짜로
    assert "newWait" not in meta["usSrc"]
    assert any(x.startswith("  !! 지난 발행본이 없거나 읽지 못했어요") and "예전 그대로" in x for x in lines), lines
    out0, meta0, _l, _p = _run(tmp_path, monkeypatch, syms, prev_t=None, blank={"LGND"}, tag="b", step=False)
    assert out == out0 and meta == meta0


def test_left_out_tickers_become_newwait_on_yahoo_blank(tmp_path, monkeypatch):
    """리뷰 A (2026-11-22): 야후가 모든 종가를 비운 날, 지난 발행본이 일부러 뺀 티커 (SKHY 한국 종목 상장분 · GOOGM 우선주) 는 기다리지 않아요 —
    그날의 usLeftOut 이 예전처럼 채워지고, newWait 에도 '새로 들어온' 로그에도 없어요 (새 단계를 끈 결과와 같아요)."""
    syms = BASE + ["SKHY", "GOOGM"]
    kw = dict(prev_t=BASE, blank=set(syms), kr_codes=frozenset({"000660"}), dups={"SKHY": ("000660", "SK하이닉스")},
              prev_extra={"usLeftOut": {"preferred": ["GOOGM"], "krListing": ["SKHY"], "badBar": []}})
    out, meta, lines, _p = _run(tmp_path, monkeypatch, syms, tag="a", **kw)
    assert "newWait" not in meta["usSrc"]
    assert meta["usLeftOut"]["preferred"] == ["GOOGM"] and meta["usLeftOut"]["krListing"] == ["SKHY"], meta["usLeftOut"]
    assert not any(x.startswith("  !! 새로 들어온 미국 종목") for x in lines), lines
    assert any(x.startswith("· 지난 발행본이 일부러 뺀 티커(usLeftOut) 중 미국 기준일 2026-11-19 종가가 야후에 없는 2: GOOGM, SKHY") for x in lines), lines
    out0, meta0, _l, _p0 = _run(tmp_path, monkeypatch, syms, tag="b", step=False, **kw)
    assert json.dumps([out, meta], sort_keys=True) == json.dumps([out0, meta0], sort_keys=True)


def test_badbar_yesterday_waits_like_any_new_ticker(tmp_path, monkeypatch):
    """검증 리뷰 (2026-11-22): 지난 발행본이 깨진 봉으로 뺀 티커 (usLeftOut.badBar) 는 지난 발행본에 없었어요 — 오늘 기준일 종가가 없으면 다른 새 티커처럼
    기다려요 (예전처럼 야후의 더 오래된 봉으로 실리면 '미국 d1 채움' 의 5 에 세어져 Jack 의 규칙과 어긋나요). 종가가 생기면 그날 들어와요."""
    syms = BASE + ["XBAD"]
    kw = dict(prev_t=BASE, blank={"XBAD"}, prev_extra={"usLeftOut": {"preferred": [], "krListing": [], "badBar": ["XBAD"]}})
    out, meta, _l, _p = _run(tmp_path, monkeypatch, syms, tag="a", **kw)
    assert "XBAD" not in {r["t"] for r in out} and meta["usSrc"].get("newWait") == ["XBAD"]
    out1, meta1, _l1, _p1 = _run(tmp_path, monkeypatch, syms, tag="c", prev_t=BASE,
                                 prev_extra={"usLeftOut": {"preferred": [], "krListing": [], "badBar": ["XBAD"]}})
    assert "XBAD" in {r["t"] for r in out1} and "newWait" not in meta1["usSrc"]


def test_a_normal_day_is_the_same_as_before(tmp_path, monkeypatch):
    """야후가 다 준 보통 날 (새 종목이 있어도 종가가 있으면): 이 단계가 없던 때와 같은 행 · 같은 기록 (usSrc 에 newWait 칸도 없어요)."""
    syms = BASE + ["LGND"]
    out, meta, _l, _p = _run(tmp_path, monkeypatch, syms, prev_t=BASE, tag="a")
    out0, meta0, _l0, _p0 = _run(tmp_path, monkeypatch, syms, prev_t=BASE, tag="b", step=False)
    assert json.dumps([out, meta], sort_keys=True) == json.dumps([out0, meta0], sort_keys=True)
    assert set(meta["usSrc"]) == {"v", "own"}


def test_hand_added_and_share_class_tickers_get_the_reason_and_their_rows_warn(tmp_path, monkeypatch):
    syms = BASE + ["BTI", "BF-B"]
    assert "BTI" in F.EXTRA_US and "BF-B" in F.US_CLASS_ADDED
    out, meta, _l, _p = _run(tmp_path, monkeypatch, syms, prev_t=BASE, blank={"BTI", "BF-B"})
    assert not {"BTI", "BF-B"} & {r["t"] for r in out}
    assert meta["usSrc"]["newWait"] == ["BF-B", "BTI"]
    assert meta["usExtraMissing"]["BTI"] == WAIT and meta["usListSym"]["missing"] == {"BF-B": WAIT}
    # 손으로 더한 종목 줄 (관문 그대로): 기다리는 종목은 까닭이 있어 경고 — 다른 EXTRA_US 는 모두 목록에 있는 날로
    rest = [us(t) for t in F.EXTRA_US if t != "BTI"]
    rep = V.Report()
    V.check_us_extra(rep, {"stocks": rest, "usExtraMissing": {"BTI": meta["usExtraMissing"]["BTI"]}}, rest, "publish")
    st, val = rows_of(rep)[EXTRA_ROW]
    assert st == "WARN" and "빠짐 1: BTI (새로 들어온 종목 · 확인된 종가를 기다려요" in val and "이유 없이" not in val, (st, val)
    # 손으로 새로 더한 종목 6곳이 한꺼번에 기다려도 경고 (까닭이 있어서) — 까닭 없이 6곳이 빠지면 예전처럼 실패해요
    six = [t for t in F.EXTRA_US_ADDED][:6]
    keep = [us(t) for t in F.EXTRA_US if t not in six]
    for rec, want in (({t: WAIT for t in six}, "WARN"), ({}, "FAIL")):
        rep = V.Report()
        V.check_us_extra(rep, {"stocks": keep, "usExtraMissing": rec}, keep, "publish")
        assert rows_of(rep)[EXTRA_ROW][0] == want, (want, rows_of(rep)[EXTRA_ROW])
    # 주식 종류 티커 줄 (관문 그대로): 까닭이 있어 경고
    rep = V.Report()
    V.check_us_share_class(rep, {"stocks": out, "usListSym": meta["usListSym"]}, out, "publish")
    name = next(k for k in rows_of(rep) if k.startswith("주식 종류 티커로 들어온 미국 종목"))
    assert rows_of(rep)[name][0] == "WARN" and "BF-B (새로 들어온 종목" in rows_of(rep)[name][1], rows_of(rep)[name]


def test_a_waiting_ticker_never_reaches_the_file_through_splits(tmp_path, monkeypatch):
    """분할 칸이 있는 새 종목이 기다리면: 오늘 다운로드의 분할 목록 · 마지막 확인 종가의 분할 기록 · 발행할 분할을 다시 보는 단계 어디에도 없어요."""
    syms = BASE + ["LGND"]
    out, meta, _l, prev = _run(tmp_path, monkeypatch, syms, prev_t=BASE, blank={"LGND", "NVDA"},
                               splits={"LGND": [("2026-11-10", 2.0)], "NVDA": [(D18, 10.0)]})
    assert "LGND" not in {r["t"] for r in out} and meta["usSrc"]["newWait"] == ["LGND"]
    assert not any(x[0] == "LGND" for x in meta["splits"])                         # 목록에 없는 종목의 분할 줄은 관문 실패예요
    assert not any(x.get("t") == "LGND" for x in meta["usSrc"]["own"]["split"])
    assert "LGND" not in (meta.get("_usOwnYahoo") or {})
    sp = {"splits": list(meta["splits"]) + [["LGND", "2026-11-10", 2.0]], "splitsFrom": V.SPLITS_FROM}
    kept, _sp2 = F.us_own_split_late(out, meta, sp, prev)
    assert "LGND" not in {r["t"] for r in kept}


def test_same_day_republish_new_ticker_still_waits(tmp_path, monkeypatch):
    """지난 발행본이 같은 미국 기준일 (같은 날 다시 발행): 지난 발행본의 종목은 그날 종가 그대로 (same) · 새 종목은 그래도 기다려요."""
    syms = BASE + ["LGND"]
    out, meta, _l, _p = _run(tmp_path, monkeypatch, syms, prev_t=BASE, blank={"AAPL", "LGND"}, prev_usd=D19)
    by = {r["t"]: r for r in out}
    assert "LGND" not in by and meta["usSrc"]["newWait"] == ["LGND"] and meta["usSrc"]["own"]["same"] == ["AAPL"]


# ── 3. 2026-11-21 의 모양 (줄인 실제 발행본 tests/fixtures/snapshot · 관문 run_checks 까지) ──────────────────
def _snap_new(new=(), carry_all=True, step=True, mode="publish", prev_wait=None, mutate=None):
    """줄인 실제 하루치 발행본을 지난 발행본으로, 다음 미국 거래일에 필수 세 종목(AAPL · MSFT · NVDA)을 뺀 모든 미국 종목의 기준일 봉이 비고
    (carry_all · 마지막 확인 종가로), 지난 발행본에 없던 new 종목들도 기준일 봉이 빈 날 (야후의 더 오래된 봉만 · 예전이면 그 봉의 자기 날짜로 실렸어요).
    step=False: 새 단계 없이 (예전 길). mode: 관문 모드 (live = 사이트 점검 · 배포와 감시가 부르는 모드 · 지난 발행본 없이) · prev_wait: 지난 발행본의
    usSrc.newWait · mutate(data): 관문 앞에 파일을 바꿔요. 반환: (data, {줄: (결과, 값)}, why, 실패한 줄 이름 set)."""
    snap = os.path.join(ROOT, "tests", "fixtures", "snapshot")
    load = lambda n: json.load(open(os.path.join(snap, f"snap_{n}.json"), encoding="utf-8"))   # noqa: E731
    prev = {k: load(k) for k in ("data", "corp", "disc", "macro")}
    pdat = prev["data"]
    if prev_wait is not None:
        pdat["usSrc"] = {"v": 1, "newWait": prev_wait}
    usd0 = pdat["usPxDate"]
    T = next(d.strftime("%Y-%m-%d") for d in pd.bdate_range(usd0, periods=3) if d.strftime("%Y-%m-%d") > usd0)
    macro = copy.deepcopy(prev["macro"])
    if T not in {r[0] for r in macro["idxHist"]["SP500"]["rows"]}:
        macro["idxHist"]["SP500"]["rows"].append([T, 6800.0])
    usl = [s for s in pdat["stocks"] if s.get("cls") == "us" and not s.get("fund")]
    assert not set(new) & {s["t"] for s in usl}
    blank = {s["t"] for s in usl if s["t"] not in ("AAPL", "MSFT", "NVDA")} if carry_all else set()
    nocl = {t: "bar" for t in blank}
    out = []
    for s in usl:
        r = copy.deepcopy(s)
        if s["t"] in blank:
            r.pop("d1", None)
            r["pxd"] = usd0                                              # 야후의 마지막 봉 (단계가 마지막 확인 종가로 바꿔요)
        else:
            r["price"] = round(s["price"] * 1.01, 2)
            r["d1"] = 1.0
        out.append(r)
    tmpl = next(s for s in usl if s["t"] == "AAPL")
    for i, t in enumerate(new):                                          # 새 종목: 야후의 더 오래된 봉만 (기준일 봉이 빔)
        r = {**copy.deepcopy(tmpl), "t": t, "nk": t, "ne": t, "price": 40.0 + i, "pxd": usd0}
        r.pop("d1", None)
        out.append(r)
        nocl[t] = "bar"
    days = sorted({r[0] for r in macro["idxHist"]["SP500"]["rows"]})
    why = {}
    wait = F.us_new_wait_step(pdat, nocl, out, why, dt.date.fromisoformat(T)) if step else []
    own = F.us_own_close_step(pdat, nocl, out, dt.date.fromisoformat(T), days, etfs=F.US_ETFS)
    umeta = {"usPxDate": T, "usSrc": {"v": 1, "own": own, **({"newWait": wait} if wait else {})}}
    out = F.us_own_close_final(out, umeta, pdat, days)
    for r in out:                                                        # 상세 정보 · 점수는 오늘 다시 붙여요 (여기서는 지난 발행본의 값 그대로)
        if r.get("pxc") or r["t"] in own.get("same", []):
            p = next(x for x in usl if x["t"] == r["t"])
            r.update({k: v for k, v in p.items() if k not in F.US_OWN_KEYS and k not in ("d1", "pxd", "pxc")})
    stocks = [copy.deepcopy(s) for s in pdat["stocks"] if not (s.get("cls") == "us" and not s.get("fund"))] + out
    data = {**pdat, "usPxDate": T, "stocks": stocks, "usSrc": umeta["usSrc"]}
    if mutate:
        mutate(data)
    json.dumps(data, allow_nan=False)
    kdays = [dt.date.fromisoformat(r[0]) for r in prev["macro"]["idxHist"]["KOSPI"]["rows"]]
    rep = V.run_checks({"data": data, "corp": prev["corp"], "disc": prev["disc"], "macro": macro}, prev if mode == "publish" else None, None,
                       dt.date.fromisoformat(T) + dt.timedelta(days=1), mode, count_between=lambda a, b: 1, notes=[],
                       sessions={"dates": kdays, "src": "t"}, now=None, hilo=None, special={}, alt=None)
    return data, rows_of(rep), why, {r[0] for r in rep.failed}


def test_the_1121_shape_publishes_with_no_uncarried_stock():
    data, rows, why, _f = _snap_new(NEW_1121)
    _d0, plain, _w0, _f0 = _snap_new((), carry_all=False)
    fails = lambda r: sorted(k for k, v in r.items() if v[0] == "FAIL")      # noqa: E731
    # 줄인 고정 데이터라 실패하는 줄도 있어요 (최종본 없음 · 종목 수) — 야후가 빈 날과 보통 날의 실패 줄이 같아요
    assert fails(rows) == fails(plain), set(fails(rows)) ^ set(fails(plain))
    st, val = rows[D1_ROW]
    carried = sum(1 for s in data["stocks"] if s.get("pxc"))
    assert st == "WARN" and f"마지막 확인 종가 {carried}" in val and "빠짐" not in val, (st, val)    # 마지막 확인 종가로 싣지 못한 종목 0
    assert carried == data["usSrc"]["own"]["n"] and carried > 80
    assert data["usSrc"]["newWait"] == NEW_1121 and why == {t: WAIT for t in NEW_1121}
    assert not set(NEW_1121) & {s["t"] for s in data["stocks"]}
    assert rows[OWN_ROW][0] == "WARN" and "none" not in rows[OWN_ROW][1], rows[OWN_ROW]
    # 이 단계가 없었으면: 4종목이 '빠짐' (5 이하라 경고였어요)
    _d, old4, _w, _f4 = _snap_new(NEW_1121, step=False)
    assert old4[D1_ROW][0] == "WARN" and "빠짐 4" in old4[D1_ROW][1], old4[D1_ROW]


def test_six_new_tickers_on_a_full_yahoo_blank_no_longer_stop_the_publish():
    """11-21 에 찾은 위험: 야후가 통째로 빈 날에 S&P 목록이 6종목 넘게 바뀌면 '미국 d1 채움' 이 실패해 국내 데이터까지 발행이 멈춰요."""
    six = NEW_1121 + ["NEWA", "NEWB"]
    data, rows, _w, _f = _snap_new(six)
    assert rows[D1_ROW][0] == "WARN" and "빠짐" not in rows[D1_ROW][1], rows[D1_ROW]
    assert data["usSrc"]["newWait"] == sorted(six)
    _d, old, _w2, _f2 = _snap_new(six, step=False)
    assert old[D1_ROW][0] == "FAIL" and "빠짐 6" in old[D1_ROW][1], old[D1_ROW]       # 관문은 그대로예요 (N = 5)


def test_the_snapshot_normal_day_is_unchanged():
    """야후가 다 준 날 (기다리는 종목 없음): 이 단계가 있든 없든 같은 파일 · 같은 관문 결과."""
    d1, r1, _w, _f1 = _snap_new((), carry_all=False)
    d0, r0, _w0, _f0 = _snap_new((), carry_all=False, step=False)
    assert json.dumps(d1, sort_keys=True, ensure_ascii=False) == json.dumps(d0, sort_keys=True, ensure_ascii=False) and r1 == r0
    assert set(d1["usSrc"]) == {"v", "own"}


# ── 4. 관문의 새 줄 '미국 새 종목 확인 종가 기다림 (usSrc.newWait · 경고만)' (리뷰 2026-11-22 · 경고만 · 실패 없음) ──────────────
ROW = V.US_NEW_WAIT_ROW


def test_new_wait_row_names_the_waiting_tickers_and_never_fails():
    _d, rows, _w, failed = _snap_new(NEW_1121)
    assert rows[ROW][0] == "WARN" and rows[ROW][1].startswith("4종목: LGND, MKTX, SNDK, VRNS") and "이어서" not in rows[ROW][1], rows[ROW]
    assert ROW not in failed
    # 지난 발행본도 기다리던 티커 (두 발행본 넘게): 따로 적어요 (출처 목록의 죽은 티커일 수 있어요)
    _d, rows2, _w, failed2 = _snap_new(NEW_1121, prev_wait=["LGND", "GONE"])
    assert rows2[ROW][0] == "WARN" and "지난 발행본부터 이어서 기다림 1: LGND" in rows2[ROW][1] and ROW not in failed2, rows2[ROW]


def test_new_wait_row_passes_when_empty_or_absent():
    _d, rows, _w, _f = _snap_new((), carry_all=False)
    assert rows[ROW] == ("PASS", "없음")
    for drop in (lambda d: d.pop("usSrc"), lambda d: d["usSrc"].update(newWait=[])):
        _d, r, _w, _f = _snap_new((), carry_all=False, mutate=drop)
        assert r[ROW] == ("PASS", "없음"), r[ROW]


def test_new_wait_row_warns_on_a_broken_record_or_a_listed_ticker():
    for bad in ("LGND", [1, "A"], [""], {"LGND": 1}, None):
        _d, r, _w, failed = _snap_new((), carry_all=False, mutate=lambda d, b=bad: d["usSrc"].update(newWait=b))
        assert r[ROW][0] == "WARN" and "모양이 잘못됨" in r[ROW][1] and ROW not in failed, (bad, r[ROW])
    _d, r, _w, failed = _snap_new((), carry_all=False, mutate=lambda d: d["usSrc"].update(newWait=["AAPL", "ZZZZ"]))
    assert r[ROW][0] == "WARN" and "그런데 발행하는 종목: AAPL" in r[ROW][1] and ROW not in failed, r[ROW]


def test_new_wait_row_in_the_site_checks_is_a_warning_like_the_others():
    """배포 · 감시가 부르는 사이트 점검(live): 지난 발행본 없이 같은 줄 · 경고만 (관문의 끝 코드는 실패 줄만 봐요: validate_data.main)."""
    _d, rows, _w, failed = _snap_new(NEW_1121, mode="live")
    assert rows[ROW][0] == "WARN" and rows[ROW][1].startswith("4종목: LGND") and ROW not in failed, rows[ROW]
    _d, rows0, _w, _f = _snap_new((), carry_all=False, mode="live")
    assert rows0[ROW] == ("PASS", "없음")
    rep = V.Report()
    V.check_us_new_wait(rep, {"usSrc": {"v": 1, "newWait": "x"}}, None)
    assert rep.failed == [] and len(rep.warned) == 1
