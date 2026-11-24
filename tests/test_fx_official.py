# -*- coding: utf-8 -*-
"""2026-11-24 (Track 2 감사 3.8): data.json fx 는 그 날짜(fxDate)의 공식 종가 — 환율 이력(macro.json fxHist · ECOS 15:30 종가)의 마지막 줄.

예전: fx = 야후 USDKRW=X 의 마지막 봉. 아침 발행(06:40) 때 그 봉(런던 날짜)은 아직 끝나지 않아, 11-21 발행은 '11-20' 밑에 1,345.7 (그날 아침 값)을
냈고 같은 날짜의 ECOS 종가는 1,336.2 (미국 시가총액 · '약 {원}' 이 0.7% 어긋남) · 11-24 발행은 '11-23' 밑에 1,340.7 · 종가 1,345.9 (0.39%).

여기서 보는 것 (네트워크 없음 · 새 파일만 · 예전 시험은 그대로):
- fetch_data.fx_official: 이력을 이번 실행에 새로 읽었으면 그 마지막 줄 (값 · 날짜 · fxSrc.src = 출처) · 아니면 야후 (fxSrc.src "yahoo" · why) —
  끝나지 않은 야후 봉은 지난 날짜로 적지 않아요 (이 실행의 한국 날짜) · 마지막 줄이 FX_HIST_ECOS_TAIL 일 넘게 전이면 야후 · 멈추면 야후 + why err
- ecos_fx_series_once: 미국 단계와 main 이 같은 이력을 만들어요 (ECOS 요청 한 번 · 멈춘 오류도 한 번)
- fetch_us: 미국 시가총액 · 거래대금(원)이 그 환율을 써요 · 2차 확인에는 야후 값이 가요 · main 의 연결
- 관문 '환율 출처 (fx · 경고만)': fx = fxHist 의 fxDate 줄이면 통과, 아니면 출처를 적어 경고 — 어떤 경우에도 실패하지 않아요
"""
import datetime as dt
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

UTC = dt.timezone.utc
ROW = V.FX_SRC_ROW
D20, D21, D23, D24 = dt.date(2026, 11, 20), dt.date(2026, 11, 21), dt.date(2026, 11, 23), dt.date(2026, 11, 24)
AT_1121 = dt.datetime(2026, 11, 21, 6, 41, tzinfo=V.KST).astimezone(UTC)      # 11-21 발행 (토 06:41 KST = 런던 11-20 21:41)
AT_1124 = dt.datetime(2026, 11, 24, 6, 40, 59, tzinfo=V.KST).astimezone(UTC)  # 11-24 발행


class Log:
    def __init__(self, monkeypatch):
        self.lines = []
        monkeypatch.setattr(F, "log", lambda *a: self.lines.append(" ".join(str(x) for x in a)))

    def has(self, *words):
        return any(all(w in ln for w in words) for ln in self.lines)


def ecos_rows(last_day="2026-11-20", tail=None):
    """2016-01-04 부터 한국 평일 (값은 1,180 ~ 1,480 사이를 천천히) · tail = 마지막 줄들 {날짜: 값} (실제 발행본의 값)."""
    idx = [d for d in pd.date_range("2016-01-04", last_day) if d.weekday() < 5]
    o = pd.Timestamp("2026-11-20").toordinal()
    by = {d.strftime("%Y-%m-%d"): round(1336.2 + 150.0 * math.sin((d.toordinal() - o) / 430.0), 1) for d in idx}
    by.update(tail or {})
    return [[d, by[d]] for d in sorted(by)]


def fields(rows, src="ecos_close", fresh="2026-11-21", final=True):
    return {"fxHist": {"asOf": rows[-1][0], "final": final, "rows": rows}, "fxHistSrc": src, "fxHistFresh": fresh}


# 실제 발행본 두 개의 마지막 줄 (macro.json fxHist · ecos_close) 과 data.json fx (야후)
TAIL_1121 = {"2026-11-17": 1338.2, "2026-11-18": 1333.0, "2026-11-19": 1330.0, "2026-11-20": 1336.2}
TAIL_1124 = dict(TAIL_1121, **{"2026-11-23": 1345.9})


# ── 1. fx_official (순수 함수) ───────────────────────────────────────────────
def test_the_1121_publish_gets_the_1120_close_not_the_open_yahoo_bar():
    fx, d, rec = F.fx_official(fields(ecos_rows("2026-11-20", TAIL_1121)), 1345.7, D20, D21, AT_1121)
    assert (fx, d) == (1336.2, D20)                                   # 예전 1,345.7 (야후 11-20 봉 · 아직 끝나지 않음)
    assert rec == {"v": 1, "src": "ecos_close", "final": True, "yahoo": {"d": "2026-11-20", "fx": 1345.7, "final": False}}


def test_the_1124_publish_gets_the_1123_close():
    fx, d, rec = F.fx_official(fields(ecos_rows("2026-11-23", TAIL_1124), fresh="2026-11-24"), 1340.7, D23, D24, AT_1124)
    assert (fx, d, rec["src"], rec["yahoo"]) == (1345.9, D23, "ecos_close", {"d": "2026-11-23", "fx": 1340.7, "final": False})
    assert "why" not in rec


def test_a_morning_when_ecos_has_not_posted_yesterday_takes_the_last_close_it_has():
    """ECOS 가 11-23 종가를 아직 올리지 않은 아침 (#117: 그런 아침 약 5.5%): 그 전 영업일 11-20 종가 · 날짜도 11-20 (fxHist 와 같은 날짜 · 같은 값)."""
    fx, d, rec = F.fx_official(fields(ecos_rows("2026-11-20", TAIL_1121), fresh="2026-11-24"), 1340.7, D23, D24, AT_1124)
    assert (fx, d, rec["src"]) == (1336.2, D20, "ecos_close")


def test_a_late_run_with_todays_close_takes_today():
    """수동 실행이 그날 밤이면 ECOS 에 오늘 15:30 종가가 있을 수 있어요 (fxHist 의 줄은 오늘까지): 그 종가 · 오늘 날짜."""
    rows = ecos_rows("2026-11-24", dict(TAIL_1124, **{"2026-11-24": 1349.0}))
    at = dt.datetime(2026, 11, 24, 21, 0, tzinfo=V.KST).astimezone(UTC)
    assert F.fx_official(fields(rows, fresh="2026-11-24"), 1341.0, D23, D24, at)[:2] == (1349.0, D24)


@pytest.mark.parametrize("src, final", [("ecos", True), ("ecos_next", True), ("yahoo_next", False), ("yahoo_next", True)])
def test_every_history_source_gives_its_last_row(src, final):
    """출처 스위치의 다른 값도 같은 규칙: 마지막 줄 = fx (관문의 yahoo_next 규칙 '마지막 날 = fxDate' 와 맞아요 · final 은 이력 그대로)."""
    fx, d, rec = F.fx_official(fields(ecos_rows("2026-11-20", TAIL_1121), src=src, final=final), 1345.7, D20, D21, AT_1121)
    assert (fx, d, rec["src"], rec["final"]) == (1336.2, D20, src, final)


@pytest.mark.parametrize("f, why", [({}, "noHist"), (None, "noHist"), ({"fxHist": None}, "noHist"),
                                    ({"fxHist": {"asOf": "2026-11-20", "final": True, "rows": []}, "fxHistSrc": "ecos_close",
                                      "fxHistFresh": "2026-11-21"}, "noHist"),
                                    (fields(ecos_rows("2026-11-19"), fresh="2026-11-20"), "kept")])
def test_without_a_fresh_history_the_yahoo_rate_is_dated_the_day_it_was_read(f, why):
    """이력을 이번 실행에 새로 읽지 못했으면 야후 값 그대로 — 봉(11-20 런던)이 아직 끝나지 않았으니 날짜는 이 실행의 한국 날짜 11-21 (지난 날짜의 종가로
    적지 않아요). 지난 발행본의 이력(kept)은 날짜가 지났어도 그 줄을 쓰지 않아요 (오래 멈춘 ECOS 가 오늘 값을 대신하지 않게)."""
    fx, d, rec = F.fx_official(f, 1345.7, D20, D21, AT_1121)
    assert (fx, d) == (1345.7, D21)
    assert rec == {"v": 1, "src": "yahoo", "final": False, "yahoo": {"d": "2026-11-20", "fx": 1345.7, "final": False}, "why": why}
    assert why in V.FX_SRC_WHY


def test_a_finished_yahoo_bar_keeps_its_own_date():
    """런던 자정(11-20 → 11-21 00:00 GMT = 한국 09:00)이 지난 실행: 끝난 봉이라 그 봉의 날짜 그대로. 1초 앞이면 아직 아니에요."""
    edge = F.london_midnight_after(D20)
    assert edge == dt.datetime(2026, 11, 21, 0, 0, tzinfo=UTC)
    fx, d, rec = F.fx_official({}, 1345.7, D20, D21, edge)
    assert (fx, d, rec["final"], rec["yahoo"]["final"]) == (1345.7, D20, True, True)
    assert F.fx_official({}, 1345.7, D20, D21, edge - dt.timedelta(seconds=1))[1] == D21


def test_summer_time_london_midnight_is_0800_kst():
    edge = F.london_midnight_after(dt.date(2026, 7, 9))
    assert edge.astimezone(V.KST) == dt.datetime(2026, 7, 10, 8, 0, tzinfo=V.KST)


def test_a_last_row_older_than_the_ecos_tail_limit_is_not_used():
    """새로 읽었는데 마지막 줄이 FX_HIST_ECOS_TAIL(14)일 넘게 전 (ECOS 가 답은 하는데 멈춤): 야후 + why old. 14일째까지는 그 줄 (추석 같은 긴 연휴)."""
    lim = V.FX_HIST_ECOS_TAIL
    today = dt.date(2026, 11, 20) + dt.timedelta(days=lim)
    at = dt.datetime.combine(today, dt.time(6, 40), V.KST).astimezone(UTC)
    yd = today - dt.timedelta(days=1)
    ok = F.fx_official(fields(ecos_rows("2026-11-20", TAIL_1121), fresh=today.isoformat()), 1350.0, yd, today, at)
    assert ok[:2] == (1336.2, D20) and ok[2]["src"] == "ecos_close"
    late = today + dt.timedelta(days=1)
    old = F.fx_official(fields(ecos_rows("2026-11-20", TAIL_1121), fresh=late.isoformat()), 1350.0, late - dt.timedelta(days=1), late,
                        at + dt.timedelta(days=1))
    assert old[0] == 1350.0 and old[2]["src"] == "yahoo" and old[2]["why"] == "old"


def test_fx_src_is_plain_json_and_carries_no_gate_word():
    for f in (fields(ecos_rows("2026-11-20", TAIL_1121)), {}):
        _fx, _d, rec = F.fx_official(f, 1345.7, D20, D21, AT_1121)
        txt = json.dumps(rec, allow_nan=False)
        assert [p for p, v in V.text_values(rec) if V.BAD_WORD.search(v)] == [], txt
    assert all(V.BAD_WORD.search(w) is None for w in V.FX_SRC_WHY.values())
    assert F.FX_SRC_WHY is V.FX_SRC_WHY and F.FX_SRC_YAHOO == V.FX_SRC_YAHOO == "yahoo"


# ── 2. fx_official_safe: 크게 남기고, 멈춰도 발행은 이어가요 ─────────────────
def test_safe_logs_the_source_and_the_yahoo_cross_check(monkeypatch):
    lg = Log(monkeypatch)
    fx, d, rec = F.fx_official_safe(fields(ecos_rows("2026-11-23", TAIL_1124), fresh="2026-11-24"), 1340.7, D23, D24, AT_1124)
    assert (fx, d) == (1345.9, D23)
    assert lg.has("환율(data.json fx): 1,345.9", "2026-11-23 공식 종가", "ecos_close", "야후 1,340.7", "아직 끝나지 않음", "+0.39%")


def test_safe_fallback_is_loud_and_names_why(monkeypatch):
    lg = Log(monkeypatch)
    fx, d, rec = F.fx_official_safe(fields(ecos_rows("2026-11-19"), fresh="2026-11-20"), 1345.7, D20, D21, AT_1121)
    assert (fx, d, rec["why"]) == (1345.7, D21, "kept")
    assert lg.has("  !! 환율(data.json fx)", "지난 발행본의 이력을 그대로 둠", "야후 1,345.7", "날짜 2026-11-21", "아직 끝나지 않아", "fxSrc")


def test_safe_survives_a_broken_history(monkeypatch):
    """마지막 줄이 깨져 고르다 멈추면: 야후 값 · 이 실행의 한국 날짜 · why err · 크게 남겨요 (발행은 이어가요 · 관문이 경고해요)."""
    lg = Log(monkeypatch)
    bad = {"fxHist": {"asOf": "x", "final": True, "rows": [["2026-02-30", 1.0]]}, "fxHistSrc": "ecos_close", "fxHistFresh": "2026-11-21"}
    fx, d, rec = F.fx_official_safe(bad, 1345.7, D20, D21, AT_1121)
    assert (fx, d, rec["src"], rec["why"], rec["final"]) == (1345.7, D21, "yahoo", "err", None)
    assert lg.has("  !! 환율(data.json fx): 출처를 고르다 멈췄어요", "ValueError", "why err")
    json.dumps(rec, allow_nan=False)
    boom = F.fx_official_safe(lambda: (_ for _ in ()).throw(KeyError("x")), 1345.7, D20, D21, AT_1121)    # 이력을 만들다 멈춰도
    assert boom[:2] == (1345.7, D21) and boom[2]["why"] == "err" and lg.has("출처를 고르다 멈췄어요", "KeyError")
    assert F.fx_official_safe(lambda: fields(ecos_rows("2026-11-20", TAIL_1121)), 1345.7, D20, D21, AT_1121)[:2] == (1336.2, D20)


# ── 3. 미국 단계와 main 이 같은 이력 (ECOS 요청 한 번) ──────────────────────
def _series(rows):
    return pd.Series([v for _d, v in rows], index=pd.to_datetime([d for d, _v in rows]), dtype="float64")


def yahoo_fx(end="2026-11-20", last=1345.7):
    idx = pd.bdate_range("2023-09-01", end)
    s = pd.Series(1336.2, index=idx, dtype=float)
    s.iloc[-1] = last
    return s


def test_us_step_and_main_build_the_same_history_with_one_ecos_request(monkeypatch):
    Log(monkeypatch)
    calls = []
    rows = ecos_rows("2026-11-20", TAIL_1121)
    monkeypatch.setattr(F, "ECOS_KEY", "test-key")                    # 시험용 가짜 키 (ecos_fx_series 를 바꿔 끼워 요청은 나가지 않아요)
    monkeypatch.setattr(F, "_ECOS_FX_READ", {})
    monkeypatch.setattr(F, "ecos_fx_series", lambda a, b, get=None, item=None: calls.append((a, b, item)) or _series(rows))
    monkeypatch.setattr(F, "FX_HIST_SOURCE", "ecos_close")
    early = F.fx_hist_fields(yahoo_fx(), 1345.7, D21, None)            # 미국 단계 (야후 값으로 2차 확인)
    fx, d, rec = F.fx_official_safe(early, 1345.7, D20, D21, AT_1121)
    late = F.fx_hist_fields(yahoo_fx(), fx, D21, None)                 # main (macro.json · 이 실행의 환율로)
    assert late == early and late["fxHist"]["rows"][-1] == ["2026-11-20", 1336.2] and (fx, d) == (1336.2, D20)
    assert calls == [(dt.date(2016, 1, 1), D21, ("731Y003", "0000003"))]


def test_a_failed_ecos_read_is_not_retried_by_main_so_both_halves_agree(monkeypatch):
    lg = Log(monkeypatch)
    calls = []

    def down(a, b, get=None, item=None):
        calls.append(1)
        raise RuntimeError("ECOS 응답 없음 (3번 시도): ReadTimeout")
    monkeypatch.setattr(F, "ECOS_KEY", "test-key")
    monkeypatch.setattr(F, "_ECOS_FX_READ", {})
    monkeypatch.setattr(F, "ecos_fx_series", down)
    monkeypatch.setattr(F, "FX_HIST_SOURCE", "ecos_close")
    prev_macro = fields(ecos_rows("2026-11-19"), fresh="2026-11-20")
    early = F.fx_hist_fields(yahoo_fx(), 1345.7, D21, prev_macro)
    fx, d, rec = F.fx_official_safe(early, 1345.7, D20, D21, AT_1121)
    late = F.fx_hist_fields(yahoo_fx(), fx, D21, prev_macro)
    assert early == late and early["fxHistFresh"] == "2026-11-20" and len(calls) == 1
    assert (fx, d, rec["src"], rec["why"]) == (1345.7, D21, "yahoo", "kept")
    assert lg.has("ECOS 환율 시계열 731Y003/0000003: 이 실행에서 앞서 읽은 것을 그대로", "그때 멈춤: RuntimeError")


def test_the_memo_hands_out_copies(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "_ECOS_FX_READ", {(D20, D21, ("a", "b")): pd.Series([1.0])})
    got = F.ecos_fx_series_once(D20, D21, ("a", "b"))
    got.iloc[0] = 9.0
    assert F.ecos_fx_series_once(D20, D21, ("a", "b")).iloc[0] == 1.0


# ── 4. fetch_us: 미국 시가총액 · 거래대금(원)이 그 환율로 ──────────────────
def _fetch(tmp_path, monkeypatch, fx_hist):
    from test_us_split_rescale import _fake_yf, SNDK_PRE
    today_us = dt.date(2026, 11, 20)
    days = pd.bdate_range(today_us - dt.timedelta(days=500), today_us)
    syms = ["AAPL", "MSFT", "NVDA"]

    def walk(seed, end):
        rnd = np.random.default_rng(seed)
        s = pd.Series(np.exp(np.cumsum(rnd.normal(0, 0.01, len(days)))), index=days)
        return s * end / float(s.iloc[-1])
    series = {"_spx": walk(1, 6700.0), "_fx": pd.Series(1345.7, index=days)}
    for i, t in enumerate(syms):
        series[t] = walk(10 + i, 100.0 + i)
    infos = {t: dict(SNDK_PRE, shortName=t + " Co", longName=t + " Inc.", marketCap=(1 + i) * 1e12) for i, t in enumerate(syms)}
    fake, _calls = _fake_yf(series, infos, {})
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    monkeypatch.setattr(F, "us_tickers", lambda names: list(syms))
    monkeypatch.setattr(F, "us_last_complete_day", lambda now=None: today_us)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(F, "US_INFO_PATH", str(tmp_path / f"us-info-{id(fx_hist)}.json.gz"))
    lg = Log(monkeypatch)
    out, _b, _fx, fx_last, _v, meta = F.fetch_us(today_us - dt.timedelta(days=500), D21, 0.03, prev={"usPxDate": "2026-11-19", "stocks": []},
                                                 fx_hist=fx_hist)
    return {r["t"]: r for r in out}, fx_last, meta, lg


def test_fetch_us_prices_us_caps_at_the_official_close_and_cross_checks_with_yahoo(tmp_path, monkeypatch):
    seen = []

    def hist(fx_y, fl_y):
        seen.append((float(fx_y.iloc[-1]), fl_y))
        return fields(ecos_rows("2026-11-20", TAIL_1121))
    by, fx_last, meta, lg = _fetch(tmp_path, monkeypatch, hist)
    assert seen == [(1345.7, 1345.7)]                                  # 2차 확인 (10% 안) 은 야후 값으로
    assert fx_last == 1336.2 and meta["fxDate"] == "2026-11-20"
    assert meta["fxSrc"] == {"v": 1, "src": "ecos_close", "final": True, "yahoo": {"d": "2026-11-20", "fx": 1345.7, "final": True}}
    for i, t in enumerate(["AAPL", "MSFT", "NVDA"]):
        assert by[t]["cap"] == round((1 + i) * 1e12 * 1336.2 / 1e12, 3), (t, by[t]["cap"])      # 예전: × 1,345.7
    assert lg.has("야후 환율 1,345.7 (2026-11-20 봉)") and lg.has("환율(data.json fx): 1,336.2", "2026-11-20 공식 종가")


def test_fetch_us_without_a_history_keeps_yahoo_and_says_so(tmp_path, monkeypatch):
    by, fx_last, meta, lg = _fetch(tmp_path, monkeypatch, lambda fx_y, fl_y: {})
    assert fx_last == 1345.7 and meta["fxSrc"]["src"] == "yahoo" and meta["fxSrc"]["why"] == "noHist"
    assert meta["fxDate"] == "2026-11-20"                              # 시험 시각엔 그 봉이 이미 끝났어요 (런던 자정 지남)
    assert by["AAPL"]["cap"] == round(1e12 * 1345.7 / 1e12, 3)
    assert lg.has("  !! 환율(data.json fx)", "환율 이력 없음")


def test_main_wiring():
    """main: 지난 macro.json 을 미국 단계 앞에서 읽고, 미국 단계가 환율 이력을 먼저 만들게 해요 · data.json 에 fxSrc · macro.json 의 이력은 예전 줄
    그대로 (같은 시계열 — ecos_fx_series_once)."""
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    body = src[src.index("\ndef main():"):src.index('if __name__ == "__main__":')]
    us_at = body.index('ph.run("미국", fetch_us,')
    assert body.index("prev_macro = read_prev_data(OUT_MACRO)") < us_at and body.count("prev_macro = read_prev_data(OUT_MACRO)") == 1
    assert 'fx_hist=lambda fx_y, fl_y: ph.run("환율 이력", fx_hist_fields, fx_y, fl_y, today, prev_macro))' in body
    assert body.index('"fxSrc": umeta.get("fxSrc"),') < body.index("write_json(OUT, payload)")
    late = body.index('macro.update(ph.run("환율 이력", fx_hist_fields, fx, fx_last, today, prev_macro))')
    assert us_at < late < body.index("write_json(OUT_MACRO, macro)")
    fh = src[src.index("def fetch_fx_hist("):src.index("def fx_hist_fields(")]
    assert "(ecos or ecos_fx_series_once)(" in fh
    fu = src[src.index("def fetch_us("):src.index("\ndef ", src.index("def fetch_us(") + 10)]
    assert fu.index("fx_official_safe(") < fu.index("apply_us_info(")           # 시가총액 · 거래대금(원)보다 먼저
    assert '"fxSrc": fx_src,' in fu


# ── 5. 관문 '환율 출처 (fx · 경고만)' ───────────────────────────────────────
def _files(fx=1336.2, fx_date="2026-11-20", fx_src="ecos", rows=None):
    data = {"fx": fx, "fxDate": fx_date}
    if fx_src == "ecos":
        data["fxSrc"] = {"v": 1, "src": "ecos_close", "final": True, "yahoo": {"d": "2026-11-20", "fx": 1345.7, "final": False}}
    elif fx_src == "yahoo":
        data["fxSrc"] = {"v": 1, "src": "yahoo", "final": False, "yahoo": {"d": "2026-11-20", "fx": 1345.7, "final": False}, "why": "kept"}
    elif fx_src is not None:
        data["fxSrc"] = fx_src
    return data, {"fxHist": {"asOf": "2026-11-20", "final": True, "rows": rows or ecos_rows("2026-11-20", TAIL_1121)}}


def _row(data, macro):
    rep = V.Report()
    V.check_fx_src(rep, data, macro)
    assert len(rep.rows) == 1 and not rep.failed
    r = rep.rows[0]
    return r[3], r[1]


def test_gate_row_passes_when_fx_is_the_history_row_of_its_date():
    st, val = _row(*_files())
    assert st == "PASS" and val == "fx 1,336.2 = fxHist 2026-11-20 줄 · 출처 ecos_close"


def test_gate_row_on_the_1124_file_as_published_warns_with_both_numbers():
    """11-24 발행본 그대로 (fxSrc 없음 · fx 1,340.7 야후 · 11-23 줄 1,345.9): 경고만."""
    data, macro = _files(fx=1340.7, fx_date="2026-11-23", fx_src=None, rows=ecos_rows("2026-11-23", TAIL_1124))
    st, val = _row(data, macro)
    assert st == "WARN" and val == "fx 1,340.7 ≠ fxHist 2026-11-23 줄 1,345.9 (-0.39%) — 출처 표시 없음 (fxSrc)", val


@pytest.mark.parametrize("kw, said", [
    (dict(fx=1345.7, fx_date="2026-11-21", fx_src="yahoo"), "fxHist 에 2026-11-21 줄이 없어요 — fx 1,345.7 · 출처 yahoo · 야후로 간 까닭: 지난 발행본의 이력을 그대로 둠"),
    (dict(fx=1345.7, fx_src="yahoo"), "fx 1,345.7 ≠ fxHist 2026-11-20 줄 1,336.2 (+0.71%) — 출처 yahoo · 야후로 간 까닭: 지난 발행본의 이력을 그대로 둠"),
    (dict(fx_src="yahoo"), "fx 1,336.2 = fxHist 2026-11-20 줄 · 출처 yahoo · 야후로 간 까닭: 지난 발행본의 이력을 그대로 둠"),   # 같아도 야후면 경고
    (dict(fx_src=None), "fx 1,336.2 = fxHist 2026-11-20 줄 · 출처 표시 없음 (fxSrc)"),
    (dict(fx_src={"src": "yahoo", "why": "err"}, fx_date="2026-11-21"), "출처 yahoo · 야후로 간 까닭: 고르다 멈춤"),
    (dict(fx_src={"src": "yahoo", "why": "weird"}, fx_date="2026-11-21"), "야후로 간 까닭: weird"),
    (dict(fx_src="ecos", fx=1336.0), "fx 1,336.0 ≠ fxHist 2026-11-20 줄 1,336.2"),                    # 파이프라인이 어긋나면
    (dict(fx_date="2026-11-22"), "fxHist 에 2026-11-22 줄이 없어요"),                                  # 그날 줄이 없는 날짜
    (dict(fx=None), "fx None · fxDate '2026-11-20' 를 읽지 못해요"),
    (dict(fx_date="2026-02-30"), "를 읽지 못해요"),
])
def test_gate_row_warns_and_names_the_source_otherwise(kw, said):
    st, val = _row(*_files(**kw))
    assert st == "WARN" and said in val, val


@pytest.mark.parametrize("macro", [{}, {"fxHist": None}, {"fxHist": {"rows": "x"}}, {"fxHist": {"rows": [["2026-11-20", "1336.2"], [1], None]}}])
def test_gate_row_without_a_readable_history_warns(macro):
    st, val = _row(_files()[0], macro)
    assert st == "WARN" and "fxHist 에 2026-11-20 줄이 없어요" in val


def test_gate_row_tolerance_is_rounding_only():
    assert _row(*_files(fx=1336.24))[0] == "PASS"
    assert _row(*_files(fx=1336.3))[0] == "WARN"


def test_gate_row_in_the_full_gate_never_fails_and_a_crash_is_a_warning(monkeypatch):
    from test_v196a_fxhist_splits import pair, check, row
    cur, prev, final = pair(src="ecos_close")
    last = cur["macro"]["fxHist"]["rows"][-1]
    cur["data"].update(fx=last[1], fxDate=last[0], fxSrc={"v": 1, "src": "ecos_close", "final": True,
                                                          "yahoo": {"d": last[0], "fx": 1333.3, "final": True}})
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert row(rep, ROW)[3] == "PASS" and row(rep, ROW)[1] == f"fx {last[1]:,.1f} = fxHist {last[0]} 줄 · 출처 ecos_close"
    old, _p, _f = pair(src="ecos_close")                               # 예전 모양 (fxSrc 없음 · 시험 fx 1,333.3 ≠ 10-30 줄 1,330.0): 경고만
    rep = check(old, prev, final)
    assert not rep.failed and row(rep, ROW)[3] == "WARN", row(rep, ROW)
    monkeypatch.setattr(V, "check_fx_src", lambda *a: (_ for _ in ()).throw(KeyError("x")))
    rep = check(cur, prev, final)
    assert not rep.failed and row(rep, ROW)[3] == "WARN" and "확인하다 오류 (KeyError" in row(rep, ROW)[1]
    live = check(cur, None, final, mode="live")
    assert not live.failed
