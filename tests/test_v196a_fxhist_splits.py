# -*- coding: utf-8 -*-
"""v19.6a 데이터 (docs/tasks/v19.6-records-alerts-dark.md Part I.1 · A.6) — 네트워크 없이.

- macro.json fxHist: 원/달러 일별 환율 2016-01-01 ~, 출처 스위치 FX_HIST_SOURCE (지금 "ecos_close"): ECOS 15:30 종가 · 다음 날 매매기준율
  (ecos_next) · 그날 매매기준율 (ecos) — 한국 영업일 · 끝난 값 — 또는 야후 다음 봉 시가 (yahoo_next · 마지막 줄은 다음 봉이 없으면 이 실행의
  환율 · final 거짓). 새로 읽지 못하면 지난 발행본 (같은 출처 · 며칠이 지나도 · 오늘 환율과 10% 넘게 다르면 빼요), 그것도 안 되면 싣지 않아요.
  오늘의 덜 끝난 봉 없음 · NaN 없음.
- data.json splits: 2016-01-01 부터 (splitsFrom) 의 미국 분할 [[코드, 날짜, 배율]]. 커밋한 시드(data/us_splits_seed.csv · 오늘 목록의 종목만) +
  어제 줄 + 오늘 야후. 한 번 실은 분할은 빼지 않아요 (야후가 빼거나 바꾸면 splitsInfo.diff). 시드에도 어제에도 없는 종목만 2016년부터 따로 읽어요
  (한 실행에 20개까지). 고정 표(SPLIT_OVERRIDES). splitsAsOf.
- 관문(validate_data.py) 세 줄: 환율 이력 · 주식 분할 목록 · 주식 분할 목록 변화.
"""
import datetime as dt
import math
import os
import sys
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}
FXH, SPL, SPC = "환율 이력 (fxHist)", "주식 분할 목록 (splits)", "주식 분할 목록 변화 (직전 발행본과)"
UTC = dt.timezone.utc


class Log:
    def __init__(self, monkeypatch):
        self.lines = []
        monkeypatch.setattr(F, "log", lambda *a: self.lines.append(" ".join(str(x) for x in a)))

    def has(self, *words):
        return any(all(w in ln for w in words) for ln in self.lines)


# ── 가짜 환율 ─────────────────────────────────────────────
def days(a, b, kr_holidays=()):
    return [d for d in pd.date_range(a, b) if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in kr_holidays]


def smooth(idx, last=None):
    """1,183 ~ 1,483 사이를 천천히 움직이는 환율 (2026-10-30 = 1,333.3 = 시험 data.json fx) — 날짜만으로 정해져요 (가짜 다운로드 둘이
    같은 날 같은 값)."""
    o = dt.date(2026, 10, 30).toordinal()
    s = pd.Series([1333.3 + 150.0 * math.sin((pd.Timestamp(d).toordinal() - o) / 430.0) for d in idx], index=pd.DatetimeIndex(idx),
                  dtype=float)
    if last is not None:
        s.iloc[-1] = last
    return s


# 2017 추석처럼 한국 영업일이 11일 비는 연휴 (2017-09-29 금 → 10-10 화)
KR_HOL = tuple(d.strftime("%Y-%m-%d") for d in pd.date_range("2017-10-02", "2017-10-09"))


def ecos_ser(end="2026-10-30", last=None):
    return smooth(days("2016-01-04", end, KR_HOL), last=last)


def run_fx(end="2026-10-30", last=1333.3):
    """fetch_us 의 fx: 이 실행의 환율 (3년 · 환율 날짜까지)."""
    return smooth(days("2023-09-21", end), last=last)


def yahoo_frame(end="2026-10-31", shift=0.0):
    """yf.download(USDKRW=X) 모양: 시가 · 종가 (종가 = 다음 날 시가와 비슷, 야후처럼)."""
    idx = days("2016-01-01", end)
    o = smooth(idx)
    c = o * (1 + shift)
    return pd.DataFrame({("Open", "USDKRW=X"): o.values, ("Close", "USDKRW=X"): c.values}, index=pd.DatetimeIndex(idx))


def ecos_json(ser, total=None, result=None):
    if result:
        return {"RESULT": result}
    rows = [{"TIME": d.strftime("%Y%m%d"), "DATA_VALUE": ("-" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.2f}")}
            for d, v in ser.items()]
    return {"StatisticSearch": {"list_total_count": len(rows) if total is None else total, "row": rows}}


# ── fxHist: 파이프라인 ───────────────────────────────────
def test_fx_hist_rows_count_bad_values_and_same_dates():
    idx = pd.DatetimeIndex(["2016-01-04", "2016-01-05", "2016-01-06", "2016-01-07", "2016-01-08", "2016-01-08", "2016-01-11"])
    s = pd.Series([1188.14, np.nan, np.inf, 0.0, 1190.0, 1191.26, -5.0], index=idx)
    rows, bad, dup = F.fx_hist_rows(s)
    assert rows == [["2016-01-04", 1188.1], ["2016-01-08", 1191.3]]      # 소수 첫째 자리 · 같은 날은 뒤의 값
    assert (bad, dup) == (4, 1)                                         # NaN · inf · 0 · 음수 / 겹친 날짜 하나


def test_ecos_fx_series_parses_and_refuses_partial_answers():
    ser = ecos_ser(end="2016-02-05")
    got = F.ecos_fx_series(dt.date(2016, 1, 1), dt.date(2016, 2, 5), get=lambda u: ecos_json(ser))
    assert len(got) == len(ser) and got.index[0] == pd.Timestamp("2016-01-04") and abs(got.iloc[0] - ser.iloc[0]) < 0.006
    with pytest.raises(RuntimeError, match="받은 줄"):
        F.ecos_fx_series(dt.date(2016, 1, 1), dt.date(2016, 2, 5), get=lambda u: ecos_json(ser, total=len(ser) + 5))
    with pytest.raises(RuntimeError, match="INFO-200"):
        F.ecos_fx_series(dt.date(2016, 1, 1), dt.date(2016, 2, 5), get=lambda u: ecos_json(ser, result={"CODE": "INFO-200"}))
    asked = []
    F.ecos_fx_series(dt.date(2016, 1, 1), dt.date(2016, 2, 5), get=lambda u: asked.append(u) or ecos_json(ser))
    assert "/731Y001/D/20160101/20160205/0000001" in asked[0]                # 원/미국달러(매매기준율)


def test_fetch_fx_hist_ecos_is_korean_business_days_final_and_cut_at_today(monkeypatch):
    log = Log(monkeypatch)
    ser = ecos_ser(end="2026-11-02", last=1330.0)              # ECOS 가 내일 날짜를 돌려줘도 (오늘 10-31 뒤는 잘라요)
    hist, src, fresh = F.fetch_fx_hist(run_fx(), 1333.3, TODAY, None, source="ecos", ecos=lambda a, b, it: ser)
    assert src == "ecos" and fresh == "2026-10-31" and hist["final"] is True
    assert hist["rows"][0][0] == "2016-01-04" and hist["asOf"] == hist["rows"][-1][0] == "2026-10-30"
    ds = [r[0] for r in hist["rows"]]
    assert "2017-10-04" not in ds and "2017-09-29" in ds and "2017-10-10" in ds    # 11일 연휴는 한국 영업일 그대로 (ECOS 기준 ≤ 14일)
    assert log.has("환율 이력(fxHist, ecos)", "2016-01-04 ~ 2026-10-30", "ECOS 731Y001/0000001")


@pytest.mark.parametrize("hurt, why", [
    (lambda s: s.where(s.index != pd.Timestamp("2018-03-05"), np.nan), "숫자가 아닌 날"),
    (lambda s: s.where(s.index != pd.Timestamp("2018-03-05"), 12000.0), "범위"),
    (lambda s: s.where(s.index != pd.Timestamp("2019-06-05"), 1500.0), "하루"),
    (lambda s: s[(s.index < pd.Timestamp("2019-02-01")) | (s.index > pd.Timestamp("2019-02-20"))], "비어요"),
    (lambda s: s[s.index >= pd.Timestamp("2020-01-02")], "첫날"),
    (lambda s: s.where(s.index != s.index[-1], 1500.0), "10%"),         # 마지막 값이 이 실행의 환율과 10% 넘게 달라요
])
def test_a_bad_ecos_history_is_never_published(monkeypatch, hurt, why):
    log = Log(monkeypatch)
    bad = hurt(ecos_ser())
    assert F.fetch_fx_hist(run_fx(), 1333.3, TODAY, None, source="ecos", ecos=lambda a, b, it: bad) == (None, None, None)
    assert log.has("만들지 못했어요", why), log.lines


def prev_macro(src="ecos", fresh="2026-10-29", end="2026-10-29"):
    if src == "ecos":
        rows = F.fx_hist_rows(ecos_ser(end=end))[0]
        return {"fxHist": {"asOf": rows[-1][0], "final": True, "rows": rows}, "fxHistSrc": "ecos", "fxHistFresh": fresh}
    rows = F.fx_hist_rows(smooth(days("2016-01-01", end)))[0]
    return {"fxHist": {"asOf": rows[-1][0], "final": False, "rows": rows}, "fxHistSrc": src, "fxHistFresh": fresh}


def test_ecos_down_keeps_yesterdays_history_without_renewing_its_date(monkeypatch):
    log = Log(monkeypatch)

    def down(a, b, it):
        raise RuntimeError("ECOS 응답 없음 (3번 시도): ConnectionError")
    pm = prev_macro(fresh="2026-10-29")
    hist, src, fresh = F.fetch_fx_hist(run_fx(), 1333.3, TODAY, pm, source="ecos", ecos=down)
    assert src == "ecos" and fresh == "2026-10-29" and hist["asOf"] == "2026-10-29" and hist["rows"] == pm["fxHist"]["rows"]
    assert log.has("!!", "지난 발행본의 이력을 그대로 둬요", "마지막으로 새로 읽은 날 2026-10-29")
    # 이어 쓴 이력을 다시 이어 써도 fxHistFresh 는 그대로 — 10일이 지나면 싣지 않아요 (끝없이 이어지지 않게)
    again = {"fxHist": hist, "fxHistSrc": src, "fxHistFresh": fresh}
    assert F.fetch_fx_hist(run_fx(), 1333.3, dt.date(2026, 11, 8), again, source="ecos", ecos=down)[2] == "2026-10-29"
    # 10일이 지나도 그대로 둬요 (#117 리뷰 2 N4): 줄은 그 날짜들에 대해 맞고, 앱은 asOf 뒤를 받지 않아요 — 빼면 2019년 기록까지 막혀요
    h, s2, f2 = F.fetch_fx_hist(run_fx(), 1333.3, dt.date(2026, 12, 20), again, source="ecos", ecos=down)
    assert (s2, f2, h["asOf"]) == ("ecos", "2026-10-29", "2026-10-29") and log.has("앱은 2026-10-29 뒤 날짜를 받지 않아요")


@pytest.mark.parametrize("pm, why", [
    (None, "fxHist 없음"),
    ({"curve": {}}, "fxHist 없음"),
    (prev_macro(src="yahoo_next"), "출처를 섞지 않아요"),
    (dict(prev_macro(), fxHistFresh=None), "fxHistFresh"),
    (dict(prev_macro(), fxHistFresh="2026-11-05"), "오늘 뒤예요"),                # 앞날
    (dict(prev_macro(), fxHistSrc=None), "출처를 섞지 않아요"),
])
def test_ecos_down_and_no_usable_yesterday_omits(monkeypatch, pm, why):
    log = Log(monkeypatch)
    out = F.fetch_fx_hist(run_fx(), 1333.3, TODAY, pm, source="ecos", ecos=lambda a, b, it: (_ for _ in ()).throw(ConnectionError("x")))
    assert out == (None, None, None) and log.has("만들지 못했어요", why), log.lines


def test_no_ecos_key_is_a_failure_not_a_guess(monkeypatch):
    log = Log(monkeypatch)
    monkeypatch.setattr(F, "ECOS_KEY", "")
    assert F.fetch_fx_hist(run_fx(), 1333.3, TODAY, None, source="ecos") == (None, None, None)
    assert log.has("ECOS_API_KEY 없음")


def test_unknown_source_is_refused():
    with pytest.raises(ValueError):
        F.fetch_fx_hist(run_fx(), 1333.3, TODAY, None, source="yahoo")
    assert F.FX_HIST_SOURCE == "ecos_close" and F.FX_HIST_SOURCE in V.FX_HIST_SOURCES      # Jack 의 답을 기다리는 동안 (#117 리뷰 3 권고)
    assert V.FX_HIST_SOURCES == ("ecos_next", "ecos_close", "ecos", "yahoo_next") and V.FX_HIST_REL == 0.10


def test_london_midnight():
    assert F.london_midnight_after(dt.date(2026, 11, 11)) == dt.datetime(2026, 11, 12, 0, 0, tzinfo=UTC)     # 겨울: 한국 09:00
    assert F.london_midnight_after(dt.date(2026, 7, 1)) == dt.datetime(2026, 7, 1, 23, 0, tzinfo=UTC)        # 여름: 한국 08:00


def test_yahoo_next_row_d_is_the_next_bars_open():
    raw = yahoo_frame(end="2026-11-02")                       # 10-30(금) 다음 봉은 11-02(월)
    fx = run_fx(last=None)
    fx_last = float(fx.iloc[-1])
    after = dt.datetime(2026, 11, 2, 1, 0, tzinfo=UTC)        # 런던 10-30 자정이 지난 뒤
    hist, how = F.fx_hist_yahoo_next(raw, fx, fx_last, after)
    o = raw[("Open", "USDKRW=X")]
    assert hist["asOf"] == "2026-10-30" and hist["final"] is True
    assert hist["rows"][-1] == ["2026-10-30", round(float(o[pd.Timestamp("2026-11-02")]), 1)]
    assert hist["rows"][-2] == ["2026-10-29", round(float(o[pd.Timestamp("2026-10-30")]), 1)]
    assert all(r[0] <= "2026-10-30" for r in hist["rows"])                              # 환율 날짜 뒤 줄은 없어요
    # 런던 자정 전(한국 아침 06:40)이면 다음 봉이 있어도 마지막 줄은 이 실행의 환율 · final 거짓
    before = dt.datetime(2026, 10, 30, 21, 40, tzinfo=UTC)
    h2, _ = F.fx_hist_yahoo_next(raw, fx, fx_last, before)
    assert h2["final"] is False and h2["rows"][-1] == ["2026-10-30", round(fx_last, 1)]
    # 다음 봉이 아직 없으면 (야후가 10-30 까지만)
    h3, _ = F.fx_hist_yahoo_next(yahoo_frame(end="2026-10-30"), fx, fx_last, after)
    assert h3["final"] is False and h3["rows"][-1] == ["2026-10-30", round(fx_last, 1)]


def test_fetch_fx_hist_yahoo_next_retries_then_falls_back(monkeypatch):
    log = Log(monkeypatch)
    calls, slept = [], []

    def broken(tk, **kw):
        calls.append((tk, kw["start"], kw["end"]))
        raise ConnectionError("야후가 막았어요")
    pm = prev_macro(src="yahoo_next")
    hist, src, fresh = F.fetch_fx_hist(run_fx(), 1333.3, TODAY, pm, source="yahoo_next", download=broken, sleep=slept.append)
    assert calls == [("USDKRW=X", dt.date(2016, 1, 1), dt.date(2026, 11, 1))] * 2 and slept == [F.FX_HIST_PAUSE]
    assert src == "yahoo_next" and fresh == "2026-10-29" and hist["asOf"] == "2026-10-29"
    assert log.has("야후 USDKRW=X 2016-01-01부터 받기 실패", "15초 뒤 다시") and log.has("지난 발행본의 이력을 그대로 둬요")


def at(f, d, v):
    f = f.copy()
    f.loc[pd.Timestamp(d), :] = v
    return f


@pytest.mark.parametrize("hurt, why", [
    (lambda f: f * 1.01, "겹치는 날 값이 달라요"),                                     # 다른 시계열
    (lambda f: at(f, "2018-03-05", 12000.0), "범위"),
    (lambda f: at(f, "2018-03-05", 0.0), "시가가 깨진"),                                # (NaN 줄은 빠진 봉 — 빈 날 기준이 봐요)
    (lambda f: f[(f.index < pd.Timestamp("2017-02-01")) | (f.index > pd.Timestamp("2017-02-10"))], "비어요"),   # 야후는 7일까지
    (lambda f: f[f.index >= pd.Timestamp("2020-01-02")], "첫날"),
])
def test_a_bad_yahoo_history_is_never_published(monkeypatch, hurt, why):
    log = Log(monkeypatch)
    raw = hurt(yahoo_frame())
    fx = run_fx(last=None)
    out = F.fetch_fx_hist(fx, float(fx.iloc[-1]), TODAY, None, source="yahoo_next", download=lambda tk, **kw: raw, sleep=lambda s: None)
    assert out == (None, None, None) and log.has("만들지 못했어요", why), log.lines


def test_fx_hist_gap_rule_depends_on_the_source():
    rows = [["2016-01-04", 1180.0], ["2016-01-15", 1185.0], ["2016-01-27", 1190.0]]     # 11일 · 12일
    assert F.fx_hist_problems(rows, "ecos") == []
    assert any("11일" in p for p in F.fx_hist_problems(rows, "yahoo_next"))
    assert any("15일" in p for p in F.fx_hist_problems([["2016-01-04", 1180.0], ["2016-01-19", 1181.0]], "ecos"))
    assert F.fx_hist_problems([], "ecos") == ["줄이 없어요"]


def test_fx_hist_never_writes_nan(tmp_path, monkeypatch):
    Log(monkeypatch)
    hist, src, fresh = F.fetch_fx_hist(run_fx(), 1333.3, TODAY, None, source="ecos", ecos=lambda a, b, it: ecos_ser())
    p = tmp_path / "macro.json"
    assert F.write_json(str(p), {"fxHist": hist, "fxHistSrc": src, "fxHistFresh": fresh}) == 0
    text = p.read_text(encoding="utf-8")
    assert "NaN" not in text and V.strict_loads(text, "macro.json")["fxHist"]["final"] is True


# ── splits: 파이프라인 ───────────────────────────────────
def bulk(events, index=None, no_col=(), layout="ticker"):
    """yf.download(..., actions=True) 모양. events: {티커: {날짜: 배율}}. layout: ticker = (티커, 칸) · field = (칸, 티커)."""
    idx = pd.DatetimeIndex(index or [d for d in pd.date_range("2016-01-01", "2026-11-02") if d.weekday() < 5])
    cols = {}
    for t, ev in events.items():
        cols[(t, "Close") if layout == "ticker" else ("Close", t)] = np.linspace(10, 20, len(idx))
        if t not in no_col:
            s = pd.Series(0.0, index=idx)
            for d, r in ev.items():
                s[pd.Timestamp(d)] = r
            cols[(t, "Stock Splits") if layout == "ticker" else ("Stock Splits", t)] = s.values
    return pd.DataFrame(cols, index=idx)


def test_us_splits_since_2016_from_a_fake_yahoo_download():
    data = bulk({"NVDA": {"2021-07-20": 4.0, "2024-06-10": 10.0}, "AMCR": {"2026-01-15": 0.2}, "GE": {"2024-04-02": 1.253},
                 "CBSH": {"2024-12-03": 1.05}, "ONE": {"2025-01-06": 1.0}, "BIG": {"2025-01-06": 2000.0},
                 "OLD": {"2016-01-01": 2.0}, "SOON": {"2026-11-02": 4.0}, "NONE": {}, "GSAT": {"2025-02-11": 1 / 15}},
                index=["2015-12-31"] + [d for d in pd.date_range("2016-01-01", "2026-11-02") if d.weekday() < 5])
    data.loc[pd.Timestamp("2015-12-31"), ("OLD", "Stock Splits")] = 3.0                  # 2016 앞은 빼요
    out, info = F.us_splits(data, ["NVDA", "AMCR", "GE", "CBSH", "ONE", "BIG", "OLD", "SOON", "NONE", "GSAT"], TODAY)
    assert out == [["AMCR", "2026-01-15", 0.2], ["CBSH", "2024-12-03", 1.05], ["GSAT", "2025-02-11", 1 / 15],
                   ["NVDA", "2021-07-20", 4.0], ["NVDA", "2024-06-10", 10.0], ["OLD", "2016-01-01", 2.0]]
    # 배율 = 옛 1주가 새로 몇 주 (NVDA 10:1 → 10 · AMCR 1:5 병합 → 0.2) · 날짜 = 야후의 분할 날짜 그대로 · 2016-01-01 부터 (창 없음)
    assert info == {"noCol": [], "future": ["SOON 2026-11-02 ×4"], "bad": ["ONE 2025-01-06 ×1", "BIG 2025-01-06 ×2000"],
                    "spin": ["GE 2024-04-02 ×1.253"]}


def test_split_dates_use_the_korean_today():
    # 러너 시계는 UTC: 2026-11-12 16:30 UTC = 2026-11-13 01:30 KST → 오늘은 11-13 (UTC 날짜 11-12 가 아니에요)
    today = F.today_kst(dt.datetime(2026, 11, 12, 16, 30, tzinfo=UTC))
    assert today == dt.date(2026, 11, 13)
    data = bulk({"A": {"2026-11-12": 4.0, "2026-11-13": 5.0, "2026-11-14": 10.0}}, index=["2026-11-12", "2026-11-13", "2026-11-14"])
    out, info = F.us_splits(data, ["A"], today)
    assert out == [["A", "2026-11-12", 4.0], ["A", "2026-11-13", 5.0]] and info["future"] == ["A 2026-11-14 ×10"]


@pytest.mark.parametrize("layout", ["ticker", "field"])
def test_split_column_layouts_and_missing_column(layout):
    data = bulk({"NVDA": {"2024-06-10": 10.0}, "XYZ": {}}, no_col=("XYZ",), layout=layout)
    out, info = F.us_splits(data, ["NVDA", "XYZ"], TODAY)
    assert out == [["NVDA", "2024-06-10", 10.0]] and info["noCol"] == ["XYZ"]
    flat = pd.DataFrame({"Close": [1.0, 2.0], "Stock Splits": [0.0, 3.0]}, index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"]))
    assert F.us_splits(flat, ["ONE"], TODAY)[0] == [["ONE", "2020-01-03", 3.0]]


def test_fetch_split_history_retries_the_missing_ones_once(monkeypatch):
    log = Log(monkeypatch)
    calls, slept = [], []

    def download(codes, **kw):
        calls.append((list(codes), kw["threads"], kw["start"], kw["actions"]))
        ok = {"TSLA": {"2020-08-31": 5.0, "2022-08-25": 3.0}, "AAPL": {"2020-08-31": 4.0}}
        have = [c for c in codes if len(calls) > 1 or c == "TSLA"]          # 처음엔 AAPL · ZZZ 를 못 받고, 두 번째엔 AAPL 만
        return bulk({c: ok.get(c, {}) for c in codes}, no_col=tuple(c for c in codes if c not in have or c == "ZZZ"))
    out, info = F.fetch_split_history(["TSLA", "AAPL", "ZZZ"], TODAY, download=download, sleep=slept.append)
    assert out == [["AAPL", "2020-08-31", 4.0], ["TSLA", "2020-08-31", 5.0], ["TSLA", "2022-08-25", 3.0]] and info["noCol"] == ["ZZZ"]
    assert calls == [(["AAPL", "TSLA", "ZZZ"], True, dt.date(2016, 1, 1), True), (["AAPL", "ZZZ"], False, dt.date(2016, 1, 1), True)]
    assert slept == [F.SPLIT_HIST_RETRY_PAUSE] and log.has("한 번 더")
    assert F.fetch_split_history([], TODAY, download=download)[0] == []


@pytest.mark.parametrize("r, clean", [
    (10.0, True), (2.0, True), (1.5, True), (0.2, True), (1 / 15, True), (1 / 35, True), (50.0, True), (1.05, True), (1.25, True),
    (0.004, True), (25.0, True), (1 / 3, True),
    (1.253, False), (1.196, False), (2.39, False), (1.01, False), (2.499, False), (0.9535, False), (1.0476, False), (1.02, False),
    (0.4873294346978557, False), (0.4725, False), (0.3775, False), (0.963, False), (1.025, False), (1.04, False),
])
def test_clean_ratio_rule_pipeline_and_gate_agree(r, clean):
    # 실제 야후 값 (2026-11-13): GE 1253:1000 · MMM 1196:1000 · DD 239:100 · J 101:100 · RYAAY 2499:1000 · HON 1907:2000 · BDX 41:40 ·
    # GE 26:25 은 분사 조정 (또는 고정 표로 넣는 진짜 사건) · CBSH 105:100 (= 21:20, 5% 주식배당) · GSAT 1:15 · DD 1:3 은 진짜 주식 수 변화
    assert F.split_is_clean(r) is clean
    assert V.simple_ratio(r) is clean


def test_pipeline_clean_rule_is_never_looser_than_the_gate():
    vals = {p / q for p in range(1, 61) for q in range(1, 61)} | {1.253, 1.196, 2.39, 1.01, 2.499, 0.9535, 0.4725, 1 / 2.649, 0.963957}
    for r in vals:
        if F.split_is_clean(r):
            assert V.simple_ratio(r), r
        f = Fraction(r).limit_denominator(1000)
        assert F.split_is_clean(r) == (min(f.numerator, f.denominator) <= 20), r


def test_override_table_is_well_formed_and_documented():
    for (t, d), (r, note) in F.SPLIT_OVERRIDES.items():
        assert t and dt.date.fromisoformat(d) >= dt.date(2016, 1, 1) and isinstance(note, str) and len(note) > 20
        assert r is None or (V.SPLIT_R[0] <= r <= V.SPLIT_R[1] and r != 1)
    assert F.SPLIT_OVERRIDES[("RYAAY", "2024-09-30")][0] == 2.5 and F.SPLIT_OVERRIDES[("HLT", "2017-01-04")][0] == 1 / 3


def prev_data(entries, us=("NVDA", "AAPL", "TSLA", "WMT"), gap=(), as_of="2026-10-30", frm=V.SPLITS_FROM):
    return {"splits": [list(x) for x in entries], "splitsFrom": frm, "splitsAsOf": as_of, "splitsInfo": {"gap": list(gap)},
            "stocks": [{"t": t, "cls": "us"} for t in us] + [{"t": "379800", "cls": "us", "fund": True}]}


START = dt.date(2023, 9, 21)
NONE = {"noCol": []}


def test_merge_first_run_reads_everything_and_applies_the_override_table(monkeypatch):
    log = Log(monkeypatch)
    us = ["NVDA", "AAPL", "RYAAY", "HLT"]
    hist = [["AAPL", "2020-08-31", 4.0], ["NVDA", "2021-07-20", 4.0], ["NVDA", "2024-06-10", 10.0]]
    recent = [["NVDA", "2024-06-10", 10.0]]                               # 두 다운로드가 겹쳐요
    sp = F.merge_splits(None, None, us, recent, NONE, START, hist, NONE, us, TODAY)
    assert sp["src"] == "yahoo" and sp["asOf"] == "2026-10-31" and sp["info"]["gap"] == [] and sp["info"]["noCol"] == 0
    assert sp["splits"] == [["AAPL", "2020-08-31", 4.0], ["HLT", "2017-01-04", 1 / 3], ["NVDA", "2021-07-20", 4.0],
                            ["NVDA", "2024-06-10", 10.0], ["RYAAY", "2024-09-30", 2.5]]
    assert len(sp["info"]["fixed"]) == len(F.SPLIT_OVERRIDES) and all(len(x) == 4 for x in sp["info"]["fixed"])
    assert ["TRI", "2023-06-23"] not in [x[:2] for x in sp["splits"]]       # 목록에 없는 종목의 고정 줄은 넣지 않아요
    assert log.has("두 다운로드가 겹친 줄 1")


def test_merge_never_drops_a_published_split(monkeypatch):
    log = Log(monkeypatch)
    prev = prev_data([["NVDA", "2024-06-10", 10.0], ["AAPL", "2020-08-31", 4.0], ["GONE", "2019-05-01", 2.0], ["WMT", "2024-02-26", 3.0],
                      ["TSLA", "2016-03-01", 2.0]])
    us = ["NVDA", "AAPL", "TSLA", "WMT"]
    # 오늘 야후: NVDA 를 빼고(3년 창 안) · WMT 배율을 바꾸고 · GONE 은 목록에서 빠졌어요. TSLA 2016 은 오늘 다운로드(2023-09 부터) 밖이라 비교 안 해요
    recent = [["WMT", "2024-02-26", 2.0]]
    sp = F.merge_splits(prev, None, us, recent, NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["AAPL", "2020-08-31", 4.0], ["GONE", "2019-05-01", 2.0], ["NVDA", "2024-06-10", 10.0],
                            ["TSLA", "2016-03-01", 2.0], ["WMT", "2024-02-26", 3.0]]
    assert sp["info"]["diff"] == [["WMT", "2024-02-26", 3.0, 2.0], ["NVDA", "2024-06-10", 10.0, None]]
    assert sp["src"] == "yahoo" and sp["new"] == [] and log.has("실은 값을 그대로 둬요")


def test_merge_new_stock_gets_its_history_and_gaps_are_retried(monkeypatch):
    Log(monkeypatch)
    prev = prev_data([["NVDA", "2024-06-10", 10.0]], us=("NVDA",))
    entries, covered, as_of, _f, _d = F.splits_prev(prev)
    assert covered == {"NVDA"} and as_of == "2026-10-30"
    us = ["NVDA", "TSLA", "NEWB"]
    need = sorted(set(us) - covered)
    hist = [["TSLA", "2020-08-31", 5.0], ["TSLA", "2022-08-25", 3.0]]
    sp = F.merge_splits(prev, None, us, [["NVDA", "2024-06-10", 10.0]], NONE, START, hist, {"noCol": ["NEWB"]}, need, TODAY)
    assert sp["info"]["gap"] == ["NEWB"] and sp["src"] == "part" and sp["asOf"] == "2026-10-31"
    assert [x[:2] for x in sp["new"]] == [["TSLA", "2020-08-31"], ["TSLA", "2022-08-25"]]
    # 다음 날: NEWB 는 gap 이라 다시 읽어요
    nxt = dict(prev_data(sp["splits"], us=us, gap=sp["info"]["gap"]))
    assert sorted(set(us) - F.splits_prev(nxt)[1]) == ["NEWB"]
    # 2016년부터의 목록이 아닌 지난 파일(splitsFrom 없음)은 줄은 이어 두되 모든 종목을 다시 읽어요
    old = prev_data([["NVDA", "2024-06-10", 10.0]], frm=None)
    assert F.splits_prev(old)[0] == {("NVDA", "2024-06-10"): 10.0} and F.splits_prev(old)[1] == set()
    # 배율 0 이하 · 모양이 틀린 지난 줄은 버려요
    assert F.splits_prev(prev_data([["A", "2024-01-02", 0.0], ["B", "2024-01-02", -2.0], ["C", "2024-02-30", 2.0], ["D", "2024-01-02", 2.0]]))[0] \
        == {("D", "2024-01-02"): 2.0}


def test_merge_when_nothing_is_read(monkeypatch):
    Log(monkeypatch)
    prev = prev_data([["NVDA", "2024-06-10", 10.0]])
    sp = F.merge_splits(prev, None, ["NVDA"], None, {}, START, None, {}, [], TODAY)        # 오늘 다운로드도 이력도 못 읽음
    assert sp["src"] == "kept" and sp["asOf"] == "2026-10-30" and sp["splits"] == [["NVDA", "2024-06-10", 10.0]]
    sp = F.merge_splits(prev, None, ["NVDA", "AAPL"], [], {"noCol": ["AAPL"]}, START, [], NONE, [], TODAY)   # AAPL 만 못 읽음
    assert sp["src"] == "part" and sp["info"]["noCol"] == 1
    assert F.merge_splits(None, None, ["NVDA"], None, {}, START, None, {}, ["NVDA"], TODAY)["splits"] is None   # 이어 올 것도 없음


def test_merge_conflicting_downloads_and_force_out(monkeypatch):
    log = Log(monkeypatch)
    sp = F.merge_splits(None, None, ["NVDA"], [["NVDA", "2024-06-10", 10.0]], NONE, START, [["NVDA", "2024-06-10", 4.0]], NONE, ["NVDA"], TODAY)
    assert sp["splits"] == [["NVDA", "2024-06-10", 10.0]] and log.has("두 다운로드의 배율이 달라요", "NVDA 2024-06-10")
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("NVDA", "2024-06-10"): (None, "시험: 분사인데 깨끗한 배율로 적힌 줄이라고 해 봐요 (빼요)")})
    prev = prev_data([["NVDA", "2024-06-10", 10.0], ["NVDA", "2021-07-20", 4.0]])
    sp = F.merge_splits(prev, None, ["NVDA"], [["NVDA", "2024-06-10", 10.0]], NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["NVDA", "2021-07-20", 4.0]] and sp["info"]["fixed"][0][:3] == ["NVDA", "2024-06-10", None]
    assert sp["info"]["diff"] == []


def test_bulk_us_download_keeps_the_split_column():
    # 분할 칸은 시세를 받는 그 다운로드에서 와요 (새 요청 없음): actions=True 가 빠지면 모든 종목이 '모름'이 돼요
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    call = src.split("data = yf.download(syms,", 1)[1].split(")", 1)[0]
    assert "actions=True" in call and "auto_adjust=True" in call


# ── 관문 ─────────────────────────────────────────────────
MUST = [list(x) for x in V.MUST_SPLITS]
NEW_US = ("TSLA", "AMZN", "GOOGL", "WMT", "CMG", "HLT", "RYAAY")


def add_us(files):
    us0 = next(s for s in files["data"]["stocks"] if s["t"] == "MSFT")
    files["data"]["stocks"] += [dict(us0, t=t) for t in NEW_US]


def with_new(cur, src="ecos"):
    add_us(cur)
    cur["data"]["fxDate"] = "2026-10-30"
    if src in ("ecos", "ecos_close"):
        rows = F.fx_hist_rows(ecos_ser(last=1330.0))[0]
        cur["macro"]["fxHist"] = {"asOf": rows[-1][0], "final": True, "rows": rows}
    elif src == "ecos_next":
        r0 = F.fx_hist_rows(ecos_ser(last=1330.0))[0]
        rows = [[a[0], b[1]] for a, b in zip(r0, r0[1:])]
        cur["macro"]["fxHist"] = {"asOf": rows[-1][0], "final": True, "rows": rows}
    else:
        rows = F.fx_hist_rows(smooth(days("2016-01-01", "2026-10-30"), last=1333.3))[0]
        cur["macro"]["fxHist"] = {"asOf": rows[-1][0], "final": False, "rows": rows}
    cur["macro"]["fxHistSrc"], cur["macro"]["fxHistFresh"] = src, "2026-10-31"
    cur["data"]["splits"] = sorted([list(x) for x in MUST] + [["QQQ", "2026-10-15", 2.0], ["U0001", "2025-03-03", 0.1], ["RYAAY", "2024-09-30", 2.5]])
    cur["data"].update({"splitsFrom": "2016-01-01", "splitsAsOf": "2026-10-31", "splitsSrc": "yahoo",
                        "splitsInfo": {"noCol": 0, "gap": [], "diff": [], "fixed": [[t, d, r, n] for (t, d), (r, n) in sorted(F.SPLIT_OVERRIDES.items())]}})
    return cur


def pair(prev_splits=True, src="ecos"):
    cur, prev, final = good_pair()
    with_new(cur, src)
    add_us(prev)
    if prev_splits:
        prev["data"].update({"splits": [list(x) for x in cur["data"]["splits"]], "splitsFrom": "2016-01-01", "splitsAsOf": "2026-10-30",
                             "splitsInfo": {"gap": []}})
    return cur, prev, final


def check(cur, prev, final, mode="publish", today=TODAY):
    return V.run_checks(cur, prev, final, today, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                        hilo=hilo_of(cur, V.MUST))


def row(rep, name):
    return next((r for r in rep.rows if r[0] == name), None)


@pytest.mark.parametrize("src", ["ecos_next", "ecos_close", "ecos", "yahoo_next"])
def test_gate_good_new_fields_pass(src):
    cur, prev, final = pair(src=src)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert row(rep, FXH)[3] == "PASS", row(rep, FXH)
    assert row(rep, FXH)[1].startswith({"ecos": "2016-01-04 ~ 2026-10-30 · ", "ecos_close": "2016-01-04 ~ 2026-10-30 · ",
                                        "ecos_next": "2016-01-04 ~ 2026-10-29 · ", "yahoo_next": "2016-01-01 ~ 2026-10-30 · "}[src])
    assert f"출처 {src}" in row(rep, FXH)[1] and ("아직 끝나지 않은 값" in row(rep, FXH)[1]) == (src == "yahoo_next")
    assert row(rep, SPL)[3] == "PASS" and row(rep, SPL)[1].startswith("13건 (2016-01-01 ~) · 최근 QQQ 2026-10-15 ×2"), row(rep, SPL)
    assert row(rep, SPC)[3] == "PASS" and row(rep, SPC)[1] == "그대로 (어제 13건 → 오늘 13건 · 새 0건)"
    live = check(cur, None, final, mode="live")
    assert row(live, FXH)[3] == "PASS" and row(live, SPL)[3] == "PASS" and row(live, SPC) is None      # 사이트 점검엔 비교 줄 없음


@pytest.mark.parametrize("hurt, said", [
    (lambda m: m.pop("fxHist"), "없음"),
    (lambda m: m.pop("fxHistSrc"), "출처 표시 None"),                    # 출처 표시가 없으면 경고 (가장 너그러운 빈 날 기준으로 봐요)
    (lambda m: m.update(fxHistSrc="yahoo"), "출처 표시 'yahoo'"),
    (lambda m: m.update(fxHistFresh="2026-10-29"), "지난 발행본의 이력을 그대로 뒀어요 (2일째"),
    (lambda m: m.pop("fxHistFresh"), "fxHistFresh None"),
    (lambda m: m["fxHist"].update(rows=m["fxHist"]["rows"][:-2], asOf=m["fxHist"]["rows"][-3][0]), "휴장일 표로 보면 2026-10-30 까지"),
    (lambda m: m.update(fxHistFresh="2026-10-20"), "11일째"),            # 오래 이어 써도 경고 — 줄은 그 날짜들에 맞아요 (#117 리뷰 2 N4)
])
def test_gate_fx_hist_warnings(hurt, said):
    cur, prev, final = pair()
    hurt(cur["macro"])
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and said in r[1], r


def _hist(cur):
    return cur["macro"]["fxHist"]


@pytest.mark.parametrize("src, hurt, said", [
    ("ecos", lambda h, d, m: h["rows"].reverse(), "날짜 차례"),
    ("ecos", lambda h, d, m: h["rows"].insert(5, list(h["rows"][5])), "날짜 차례"),
    ("ecos", lambda h, d, m: h["rows"].__delitem__(slice(300, 312)), "빈 날"),
    ("ecos_next", lambda h, d, m: h["rows"].append(["2026-10-31", 1330.0]) or h.update(asOf="2026-10-31"), "아직 없어야 할 줄"),
    ("ecos_close", lambda h, d, m: h["rows"].append(["2026-11-02", 1330.0]) or h.update(asOf="2026-11-02"), "뒤"),
    ("yahoo_next", lambda h, d, m: h["rows"].__delitem__(slice(300, 306)), "빈 날"),
    ("ecos", lambda h, d, m: h["rows"][400].__setitem__(1, h["rows"][400][1] * 1.2), "큰 변화"),
    ("ecos", lambda h, d, m: h["rows"][0].__setitem__(1, 880.0), "범위 밖"),
    ("ecos", lambda h, d, m: h.__setitem__("asOf", "2026-10-29"), "asOf"),
    ("ecos", lambda h, d, m: h["rows"][-1].__setitem__(1, 1500.0), "10%"),
    ("ecos", lambda h, d, m: h["rows"].__delitem__(slice(300, 311)), "빈 날"),     # 15일 빔 (ECOS 기준 14일 · 14일은 통과: 아래 시험)
    ("ecos", lambda h, d, m: h.__setitem__("rows", h["rows"][10:]), "첫날"),
    ("ecos", lambda h, d, m: h["rows"][7].__setitem__(1, "1180.5"), "모양"),
    ("ecos", lambda h, d, m: h["rows"][7].__setitem__(1, True), "모양"),
    ("ecos", lambda h, d, m: h["rows"][7].__setitem__(0, "2016-02-30"), "모양"),
    ("ecos", lambda h, d, m: h.__setitem__("rows", []), "rows"),
    ("ecos", lambda h, d, m: h.__setitem__("final", "yes"), "final"),
    ("ecos", lambda h, d, m: h.pop("final"), "final"),
    ("ecos", lambda h, d, m: h["rows"].append(["2026-11-02", 1330.0]) or h.update(asOf="2026-11-02"), "뒤"),
    ("yahoo_next", lambda h, d, m: h["rows"].append(["2026-10-31", 1333.3]) or h.update(asOf="2026-10-31"), "아직 없어야 할 줄"),
    ("yahoo_next", lambda h, d, m: h["rows"].pop() and h.update(asOf=h["rows"][-1][0]), "fxDate"),
    ("ecos", lambda h, d, m: m.update(fxHistFresh="2026-11-01"), "fxHistFresh"),
])
def test_gate_malformed_fx_hist_fails(src, hurt, said):
    cur, prev, final = pair(src=src)
    hurt(_hist(cur), cur["data"], cur["macro"])
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "FAIL" and said in r[1], r


@pytest.mark.parametrize("src", ["ecos", "ecos_close"])
def test_gate_ecos_may_end_today_and_be_after_the_fx_date(src):
    cur, prev, final = pair(src=src)
    _hist(cur)["rows"].append(["2026-10-31", 1331.0])        # 오늘 아침 고시된 매매기준율 (끝난 값) · fxDate 10-30 뒤
    _hist(cur)["asOf"] = "2026-10-31"
    assert row(check(cur, prev, final), FXH)[3] == "PASS"


def test_gate_kept_yahoo_history_may_end_before_the_fx_date():
    cur, prev, final = pair(src="yahoo_next")
    _hist(cur)["rows"].pop()
    _hist(cur)["asOf"] = _hist(cur)["rows"][-1][0]
    cur["macro"]["fxHistFresh"] = "2026-10-29"
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "지난 발행본" in r[1], r


def test_gate_missing_splits_warns_but_fails_when_yesterday_had_them():
    cur, prev, final = pair(prev_splits=False)
    del cur["data"]["splits"]
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "WARN" and r[1].startswith("없음"), r
    assert row(check(cur, None, final, mode="live"), SPL)[3] == "WARN"
    prev["data"]["splits"] = [["NVDA", "2024-06-10", 10.0]]
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "FAIL" and "직전 발행본에는 있었어요" in r[1], r


@pytest.mark.parametrize("hurt, said", [
    (lambda d: d["splits"].append(["NVDA", "2024-06-10"]), "모양"),
    (lambda d: d["splits"].append(["NVDA", "2024-06-31", 2.0]), "모양"),
    (lambda d: d["splits"].append([5930, "2024-06-10", 2.0]), "모양"),
    (lambda d: d["splits"].append(["NVDA", "2024-06-11", "10"]), "모양"),
    (lambda d: d["splits"].append(["MSFT", "2025-01-06", 1.0]), "배율 1"),
    (lambda d: d["splits"].append(["MSFT", "2025-01-06", 2000.0]), "배율 2000"),
    (lambda d: d["splits"].append(["MSFT", "2024-04-02", 1.253]), "깨끗한 분수가 아니에요"),
    (lambda d: d["splits"].append(["MSFT", "2026-11-01", 2.0]), "오늘 뒤"),
    (lambda d: d["splits"].append(["MSFT", "2015-12-30", 2.0]), "2016-01-01 앞"),
    (lambda d: d["splits"].append(["ZZZZ", "2025-01-06", 2.0]), "오늘 목록에 없음 (새 줄)"),
    (lambda d: d["splits"].append(["NVDA", "2024-06-10", 10.0]), "두 번"),
    (lambda d: d.update(splitsFrom="2023-10-31"), "splitsFrom"),
    (lambda d: d.update(splitsAsOf="2026-10-25"), "splitsAsOf"),
    (lambda d: d.update(splitsAsOf=None), "splitsAsOf"),
    (lambda d: d.update(splitsAsOf="2026-11-01"), "splitsAsOf"),
    (lambda d: d.update(splits=[x for x in d["splits"] if x[0] != "TSLA"]), "꼭 있어야 할 분할 없음: TSLA 2020-08-31 ×5"),
    (lambda d: d["splits"].__setitem__(next(i for i, x in enumerate(d["splits"]) if x[0] == "RYAAY"), ["RYAAY", "2024-09-30", 2.499]),
     "고정 표"),
    (lambda d: d["splitsInfo"]["fixed"].append(["MSFT", "2025-01-06", None, "시험: 빼야 할 줄"]) or d["splits"].append(
        ["MSFT", "2025-01-06", 2.0]), "고정 표에서 뺀 줄인데 있어요"),
    (lambda d: d["splitsInfo"]["fixed"].append(["MSFT", "2025-01-06", 2.0]), "fixed 모양"),
])
def test_gate_malformed_splits_fail(hurt, said):
    cur, prev, final = pair()
    hurt(cur["data"])
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "FAIL" and said in r[1], r


def test_gate_fixed_table_lets_an_unclean_true_event_through():
    cur, prev, final = pair()
    cur["data"]["splits"].append(["MSFT", "2016-01-05", 1 / 2.649])
    prev["data"]["splits"].append(["MSFT", "2016-01-05", 1 / 2.649])
    cur["data"]["splitsInfo"]["fixed"].append(["MSFT", "2016-01-05", 1 / 2.649, "시험: 2.649 → 1 병합 (근거)"])
    assert row(check(cur, prev, final), SPL)[3] == "PASS"


@pytest.mark.parametrize("hurt, said", [
    (lambda d: d.update(splitsSrc="kept", splitsAsOf="2026-10-29"), "야후에서 마지막으로 새로 읽은 날 2026-10-29"),
    (lambda d: d.update(splitsSrc="part"), "출처 part"),
    (lambda d: d.update(splitsSrc=None), "출처 None"),
    (lambda d: d["splitsInfo"].update(gap=["NEWB"]), "아직 읽지 못한 종목 1: NEWB"),
    (lambda d: d["splitsInfo"].update(noCol=3), "오늘 분할 칸을 읽지 못한 종목 3"),
    (lambda d: d["splitsInfo"].update(diff=[["WMT", "2024-02-26", 3.0, 2.0], ["NVDA", "2024-06-10", 10.0, None]]),
     "야후와 다름(실은 값 그대로) 2: WMT 2024-02-26 ×3→×2, NVDA 2024-06-10 ×10→없음"),
    (lambda d: d["splitsInfo"].update(diff=[["QQQ", "2026-10-15", 2.0, 2.0, "2026-10-16"]]), "QQQ 2026-10-15 ×2→×2 (2026-10-16)"),
    (lambda d: d["splitsInfo"].update(fixedKept=[["MSFT", "2025-01-06"]]), "고정 표에서 지운 줄을 지난 발행본에서 이어 둠 1: MSFT 2025-01-06"),
    (lambda d: d["splits"].append(["QQQ", "2026-10-16", 2.0]), "30일 안에 분할이 둘 1: QQQ 2026-10-15·2026-10-16"),
    (lambda d: d.pop("splitsInfo"), "splitsInfo 없음"),
])
def test_gate_split_warnings(hurt, said):
    cur, prev, final = pair()
    hurt(cur["data"])
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "WARN" and said in r[1], r


def test_gate_split_after_the_us_date_warns():
    cur, prev, final = pair()
    for d in (cur["data"], prev["data"]):
        d["splits"].append(["MSFT", "2026-10-31", 2.0])         # 오늘(KST) 날짜 · 미국 기준일 10-30 뒤
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "WARN" and "미국 기준일 2026-10-30 뒤 날짜: MSFT 2026-10-31" in r[1], r


def test_gate_split_of_a_stock_that_left_the_list_warns_only_on_the_first_day():
    cur, prev, final = pair()
    for d in (cur["data"], prev["data"]):
        d["splits"].append(["U0005", "2019-05-01", 2.0])         # 어제도 있던 줄
    cur["data"]["stocks"] = [s for s in cur["data"]["stocks"] if s["t"] != "U0005"]   # 오늘 처음 목록에서 빠짐 → 경고
    rep = check(cur, prev, final)
    r = row(rep, SPL)
    assert r[3] == "WARN" and "오늘 목록에서 빠진 종목의 분할(이어 둠) 1: U0005 2019-05-01" in r[1], r
    prev["data"]["stocks"] = [s for s in prev["data"]["stocks"] if s["t"] != "U0005"]  # 어제도 없었음 → 확인 목록에만 (노랗게 남지 않게)
    rep = check(cur, prev, final)
    assert row(rep, SPL)[3] == "PASS" and any("목록에 없는 종목 U0005 2019-05-01" in items for t, items in rep.details), rep.details
    assert row(check(cur, None, final, mode="live"), SPL)[3] == "PASS"                  # 사이트 점검은 어제를 몰라 확인 목록에만


def test_gate_compares_splits_with_yesterday():
    cur, prev, final = pair()
    prev["data"]["splits"] += [["AAPL", "2025-05-05", 4.0]]           # 오늘 사라짐 → 실패
    cur["data"]["splits"][[x[0] for x in cur["data"]["splits"]].index("NVDA") + 1][2] = 20.0   # NVDA 2024 배율 바뀜 → 실패
    rep = check(cur, prev, final)
    r = row(rep, SPC)
    assert r[3] == "FAIL", r
    assert "사라짐 1: AAPL 2025-05-05 ×4" in r[1] and "배율 바뀜 1: NVDA 2024-06-10 ×10→×20" in r[1]
    assert any(t == SPC and "사라짐 AAPL 2025-05-05 ×4" in items for t, items in rep.details)


def test_gate_new_splits_that_need_a_human_look():
    cur, prev, final = pair()
    cur["data"]["splits"] += [["U0002", "2024-02-01", 3.0],          # 어제 2016년부터 읽은 종목에 오래된 분할이 새로 → 경고
                              ["U0003", "2026-10-29", 1.5],          # 이틀 전 3:2 → 정수가 아닌 배율이라 경고
                              ["QQQ", "2026-10-29", 4.0]]            # 이틀 전 4:1 → 정상
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "WARN", r
    assert "새 줄 정수 아닌 배율 1: U0003 2026-10-29 ×1.5" in r[1] and "지난 날짜로 새로 1: U0002 2024-02-01 ×3" in r[1]
    assert "QQQ" not in r[1]
    # 어제 2016년부터를 아직 읽지 못한 종목(gap)이면 오래된 분할이 새로 생기는 게 정상이에요
    prev["data"]["splitsInfo"]["gap"] = ["U0002"]
    assert "U0002" not in row(check(cur, prev, final), SPC)[1]


def test_gate_fixed_table_drop_or_fix_only_warns():
    cur, prev, final = pair()
    prev["data"]["splits"] += [["MSFT", "2025-01-06", 2.0], ["U0004", "2024-01-03", 1.253]]
    cur["data"]["splitsInfo"]["fixed"] += [["MSFT", "2025-01-06", None, "시험: 분사였어요 (근거)"], ["U0004", "2024-01-03", 1.25, "시험: 5:4 (근거)"]]
    cur["data"]["splits"].append(["U0004", "2024-01-03", 1.25])
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "WARN" and "고정 표가 뺌 1: MSFT 2025-01-06 ×2" in r[1] and "고정 표가 고침 1: U0004 2024-01-03 ×1.253→×1.25" in r[1], r


def test_gate_without_yesterdays_list_skips_the_comparison():
    cur, prev, final = pair(prev_splits=False)
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "SKIP" and "첫 발행" in r[2], r


def test_gate_does_not_crash_on_odd_shapes():
    cur, prev, final = pair()
    cur["macro"]["fxHist"] = ["2016-01-04", 1180.0]
    prev["data"]["splits"] = [["NVDA", "2024-06-10"], "x", None, ["U0001", "2025-03-03", 0], ["U0001", "2025-03-03", "0.1"]] + \
        [list(x) for x in cur["data"]["splits"]]
    cur["data"]["splitsInfo"]["diff"] = [["X"], None]
    rep = check(cur, prev, final)
    assert row(rep, FXH)[3] == "FAIL" and row(rep, SPC)[3] == "PASS", rep.table()     # 어제의 깨진 줄은 비교에서 빼요


def test_pipeline_reads_its_lines_from_the_gate():
    # 파이프라인은 관문의 기준을 읽어요 (같은 선 · 한 곳) — 검사 코드는 따로예요
    for k in ("FX_LO", "FX_HI", "FX_HIST_FROM", "FX_HIST_FIRST_BY", "FX_HIST_SOURCES", "FX_HIST_ECOS", "FX_HIST_GAP_MAX", "FX_HIST_JUMP",
              "FX_HIST_REL", "SPLITS_FROM", "SPLIT_R", "SPLIT_SIMPLE_MAX", "SPLIT_CLEAN_TOL", "MUST_SPLITS"):
        assert getattr(F, k) is getattr(V, k), k


# ── #117 리뷰 2 ──────────────────────────────────────────
def test_ecos_next_row_d_is_the_next_published_rate(monkeypatch):
    Log(monkeypatch)
    idx = pd.DatetimeIndex(["2016-01-04", "2016-01-05", "2016-01-06", "2016-01-07", "2016-01-08", "2016-01-11"])
    mbr = pd.Series([1172.0, 1187.0, 1190.0, 1194.0, 1200.0, 1199.0], index=idx)
    hist, how = F.fx_hist_ecos(mbr, 1200.0, dt.date(2016, 1, 12), "ecos_next")
    # 줄 D = D 다음 고시 (= D 하루 서울 거래) · 마지막 고시일(01-11)엔 아직 줄이 없어요 · 주말 01-09 은 그 전 줄(01-08 = 01-11 고시)
    assert hist == {"asOf": "2016-01-08", "final": True, "rows": [["2016-01-04", 1187.0], ["2016-01-05", 1190.0], ["2016-01-06", 1194.0],
                                                                   ["2016-01-07", 1200.0], ["2016-01-08", 1199.0]]}
    assert F.fx_hist_ecos(mbr, 1200.0, dt.date(2016, 1, 12), "ecos")[0]["asOf"] == "2016-01-11"
    assert "731Y001/0000001" in how


@pytest.mark.parametrize("src, item", [("ecos_next", ("731Y001", "0000001")), ("ecos", ("731Y001", "0000001")),
                                       ("ecos_close", ("731Y003", "0000003"))])
def test_each_ecos_source_asks_for_its_own_series(monkeypatch, src, item):
    Log(monkeypatch)
    asked = []
    hist, got, fresh = F.fetch_fx_hist(run_fx(), 1333.3, TODAY, None, source=src, ecos=lambda a, b, it: asked.append((a, b, it)) or ecos_ser())
    assert asked == [(dt.date(2016, 1, 1), TODAY, item)] and got == src and fresh == "2026-10-31" and hist["final"] is True
    assert hist["asOf"] == ("2026-10-29" if src == "ecos_next" else "2026-10-30")


def test_fx_hist_fields_for_main(monkeypatch):
    Log(monkeypatch)
    assert set(F.fx_hist_fields(run_fx(), 1333.3, TODAY, None, ecos=lambda a, b, it: ecos_ser())) == {"fxHist", "fxHistSrc", "fxHistFresh"}
    assert F.fx_hist_fields(run_fx(), 1333.3, TODAY, None, ecos=lambda a, b, it: ecos_ser(last=1000.0)) == {}        # 깨진 이력 → 없음
    assert F.fx_hist_fields(run_fx(), 1333.3, TODAY, None, source="nope") == {}                                       # 멈춰도 크게 남기고 없음


def test_main_wiring():
    # main 은 분할을 splits_fields 로, 환율 이력을 fx_hist_fields 로 만들어 그대로 실어요 · 매일 770여 종목을 다시 읽지 않아요
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    body = src.split("\ndef main():", 1)[1]
    assert 'sp_fields = splits_fields(prev, [s["t"] for s in us], umeta.get("splits"), umeta.get("splitsNoCol") or [], start, today)' in body
    assert "payload.update(sp_fields)" in body and "fetch_split_history" not in body
    assert 'macro.update(ph.run("환율 이력", fx_hist_fields, fx, fx_last, today, prev_macro))' in body
    assert body.index("payload.update(sp_fields)") < body.index("write_json(OUT, payload)")
    assert body.index("macro.update(ph.run(") < body.index("write_json(OUT_MACRO, macro)")


def gap_rows(rows, start, n):
    """rows 에서 start 다음 날부터 start + n 일 전까지의 줄을 빼요 (start · start + n 줄은 남아요)."""
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(start) + dt.timedelta(days=n)
    assert any(r[0] == b.isoformat() for r in rows)
    return [r for r in rows if not (a.isoformat() < r[0] < b.isoformat())]


@pytest.mark.parametrize("src, n, ok", [("ecos", 14, True), ("ecos", 15, False), ("ecos_next", 14, True), ("ecos_close", 15, False),
                                         ("yahoo_next", 7, True), ("yahoo_next", 8, False)])
def test_gate_gap_limits_are_exact(src, n, ok):
    cur, prev, final = pair(src=src)
    h = _hist(cur)
    h["rows"] = gap_rows(h["rows"], "2018-03-05", n)
    r = row(check(cur, prev, final), FXH)
    assert (r[3] != "FAIL") is ok and (ok or "빈 날" in r[1]), r


def test_gate_ecos_tail_without_the_holiday_table(monkeypatch):
    monkeypatch.setattr(V, "load_holidays", lambda *a: (_ for _ in ()).throw(RuntimeError("표 없음")))
    cur, prev, final = pair(src="ecos")
    h = _hist(cur)
    h["rows"] = [r for r in h["rows"] if r[0] <= "2026-10-16"]
    h["asOf"] = h["rows"][-1][0]
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "ECOS 마지막 날 2026-10-16 이 14일 넘게 전이에요" in r[1], r
    cur, prev, final = pair(src="ecos")
    h = _hist(cur)
    h["rows"] = [r for r in h["rows"] if r[0] <= "2026-10-19"]
    h["asOf"] = h["rows"][-1][0]
    assert row(check(cur, prev, final), FXH)[3] == "PASS"
    assert V._ecos_tail_min(dt.date(2026, 10, 31), "ecos") is None


def test_ecos_tail_follows_the_korean_holiday_table():
    # 2026-10-05 (월) 개천절 대체 휴일 · 10-09 (금) 한글날: 10-10(토) 발행이면 ecos 는 10-08, ecos_next 는 10-07 까지 있어야 해요
    assert V._ecos_tail_min(dt.date(2026, 10, 10), "ecos") == dt.date(2026, 10, 8)
    assert V._ecos_tail_min(dt.date(2026, 10, 10), "ecos_next") == dt.date(2026, 10, 7)
    assert V._ecos_tail_min(dt.date(2026, 10, 6), "ecos_close") == dt.date(2026, 10, 2)


def test_seed_file_is_committed_and_reviewed():
    rows, codes, end = F.load_split_seed()
    assert len(rows) == 129 and len(codes) == 773 and end == dt.date(2026, 11, 12)
    for t, d, r in V.MUST_SPLITS:
        assert (t, d) in F.SPLIT_OVERRIDES or rows.get((t, d)) == r, (t, d)
    assert rows[("NVDA", "2021-07-20")] == 4.0 and rows[("TSLA", "2022-08-25")] == 3.0 and rows[("CBSH", "2018-11-29")] == 1.05
    assert rows[("GSAT", "2025-02-11")] == 1 / 15 and ("GE", "2024-04-02") not in rows and ("RYAAY", "2024-09-30") not in rows
    assert all(F.split_is_clean(r) and V.simple_ratio(r) for r in rows.values())
    assert not set(F.SPLIT_OVERRIDES) & set(rows)                       # 고정 표의 줄은 시드에 없어요 (한 곳)
    assert rows[("GMAB", "2018-05-01")] == 5.0                          # 같은 ADR 프로그램(OTC GMXAY → Nasdaq 2019)이라 둬요 (#117 리뷰 4 N-4)


@pytest.mark.parametrize("line, codes", [
    ("NVDA,2024-06-10,1.253,1253:1000", "NVDA"), ("NVDA,2024-06-31,10.0,10:1", "NVDA"), ("NVDA,2015-12-30,2.0,2:1", "NVDA"),
    ("NVDA,2024-06-10,10.0", "NVDA"), ("NVDA,2024-06-10,10.0,10:1\nNVDA,2024-06-10,10.0,10:1", "NVDA"), ("NVDA,2024-06-10,10.0,10:1", "AAPL"),
])
def test_seed_loader_refuses_bad_files(tmp_path, line, codes):
    p, c = tmp_path / "s.csv", tmp_path / "c.txt"
    p.write_text("# 설명\ncode,date,ratio,yahoo\n" + line + "\n", encoding="utf-8")
    c.write_text("# end=2026-11-12\n" + codes + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        F.load_split_seed(str(p), str(c))
    p.write_text("code,date,ratio,yahoo\nNVDA,2024-06-10,10.0,10:1\n", encoding="utf-8")
    c.write_text("NVDA\n", encoding="utf-8")                        # end= 줄 없음
    with pytest.raises(RuntimeError):
        F.load_split_seed(str(p), str(c))


SEED = ({("NVDA", "2021-07-20"): 4.0, ("NVDA", "2024-06-10"): 10.0, ("TSLA", "2020-08-31"): 5.0, ("TSLA", "2022-08-25"): 3.0,
         ("AAPL", "2020-08-31"): 4.0}, {"NVDA", "TSLA", "AAPL", "WMT"}, dt.date(2026, 10, 30))


def test_merge_treats_seed_rows_like_published_rows(monkeypatch):
    log = Log(monkeypatch)
    recent = [["NVDA", "2024-06-10", 10.0], ["TSLA", "2024-01-02", 2.0], ["WMT", "2024-02-26", 3.0]]
    sp = F.merge_splits(None, SEED, ["NVDA", "TSLA", "AAPL", "WMT"], recent, NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["AAPL", "2020-08-31", 4.0], ["NVDA", "2021-07-20", 4.0], ["NVDA", "2024-06-10", 10.0], ["TSLA", "2020-08-31", 5.0],
                            ["TSLA", "2022-08-25", 3.0], ["TSLA", "2024-01-02", 2.0], ["WMT", "2024-02-26", 3.0]]
    assert sp["info"]["diff"] == [] and sp["src"] == "yahoo" and log.has("시드 5")
    sp = F.merge_splits(None, SEED, ["NVDA"], [["NVDA", "2024-06-10", 20.0]], NONE, START, [], NONE, [], TODAY)
    assert ["NVDA", "2024-06-10", 10.0] in sp["splits"] and sp["info"]["diff"] == [["NVDA", "2024-06-10", 10.0, 20.0]]


def test_splits_fields_reads_only_stocks_missing_from_the_seed_and_yesterday(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())                  # 이 시험의 작은 시드엔 꼭 있어야 할 분할이 다 있지 않아요 (그 안전장치는 아래 시험)
    asked = []

    def history(codes, today):
        asked.append(list(codes))
        return [["NEWX", "2019-05-01", 2.0]], {"noCol": [], "future": [], "bad": [], "spin": []}
    us = ["NVDA", "TSLA", "AAPL", "WMT", "NEWX"]
    recent = [["NVDA", "2024-06-10", 10.0], ["WMT", "2024-02-26", 3.0]]
    f = F.splits_fields(None, us, recent, [], START, TODAY, seed=SEED, history=history)
    assert asked == [["NEWX"]]
    assert set(f) == {"splits", "splitsFrom", "splitsAsOf", "splitsSrc", "splitsInfo"}
    assert f["splitsFrom"] == "2016-01-01" and f["splitsAsOf"] == "2026-10-31" and f["splitsSrc"] == "yahoo" and f["splitsInfo"]["gap"] == []
    assert ["NEWX", "2019-05-01", 2.0] in f["splits"] and ["TSLA", "2022-08-25", 3.0] in f["splits"]
    # 다음 날: 어제 목록이 2016년부터라 아무것도 다시 읽지 않아요
    prev = dict(f, stocks=[{"t": t, "cls": "us"} for t in us])
    asked.clear()
    F.splits_fields(prev, us, recent, [], START, TODAY + dt.timedelta(days=1), seed=SEED, history=history)
    assert asked == []


def test_splits_fields_caps_the_backfill_and_keeps_the_gap_on_errors(monkeypatch):
    log = Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    many = [f"N{i:02d}" for i in range(25)]
    asked = []
    hist = lambda codes, today: asked.append(list(codes)) or ([], {"noCol": [], "future": [], "bad": [], "spin": []})   # noqa: E731
    f = F.splits_fields(None, list(SEED[1]) + many, [], [], START, TODAY, seed=SEED, history=hist)
    assert asked == [many[:F.SPLIT_BACKFILL_MAX]] and f["splitsInfo"]["gap"] == many[F.SPLIT_BACKFILL_MAX:] and f["splitsSrc"] == "part"
    assert log.has("나머지 5개는 다음 실행에서")

    def broken(codes, today):
        raise ConnectionError("야후가 막았어요")
    f = F.splits_fields(None, list(SEED[1]) + ["NEWX"], [], [], START, TODAY, seed=SEED, history=broken)
    assert f["splitsInfo"]["gap"] == ["NEWX"] and log.has("받다 멈췄어요")


def test_splits_fields_belt_on_a_first_publish(monkeypatch):
    log = Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", (("TSLA", "2020-08-31", 5.0), ("NVDA", "2021-07-20", 4.0)))
    no_tsla = ({k: v for k, v in SEED[0].items() if k[0] != "TSLA"}, SEED[1], SEED[2])
    assert F.splits_fields(None, list(SEED[1]), [], [], START, TODAY, seed=no_tsla) == {}       # 꼭 있어야 할 분할이 빠진 첫 발행: 쓰지 않아요
    assert log.has("꼭 있어야 할 분할이 빠져 오늘은 splits 를 쓰지 않아요", "TSLA 2020-08-31")
    prev = {"splits": [], "splitsFrom": "2016-01-01", "stocks": []}
    assert "splits" in F.splits_fields(prev, list(SEED[1]), [], [], START, TODAY, seed=no_tsla)  # 어제 목록이 있으면 실어요 (관문이 실패로 막아요)


def test_seed_that_ends_before_the_window_does_not_count(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    asked = []
    hist = lambda codes, today: asked.append(list(codes)) or ([], {"noCol": [], "future": [], "bad": [], "spin": []})   # noqa: E731
    old = (SEED[0], SEED[1], dt.date(2023, 1, 1))
    F.splits_fields(None, ["NVDA", "TSLA"], [], [], START, TODAY, seed=old, history=hist)
    assert asked == [["NVDA", "TSLA"]]


def test_a_moved_split_date_is_the_same_event(monkeypatch):
    Log(monkeypatch)
    prev = prev_data([["QQQ", "2026-10-15", 2.0]], us=("QQQ",))
    sp = F.merge_splits(prev, None, ["QQQ"], [["QQQ", "2026-10-16", 2.0]], NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["QQQ", "2026-10-15", 2.0]] and sp["info"]["diff"] == [["QQQ", "2026-10-15", 2.0, 2.0, "2026-10-16"]]
    sp = F.merge_splits(prev, None, ["QQQ"], [["QQQ", "2026-10-27", 2.0]], NONE, START, [], NONE, [], TODAY)     # 12일 뒤 = 다른 분할
    assert sp["splits"] == [["QQQ", "2026-10-15", 2.0], ["QQQ", "2026-10-27", 2.0]]
    sp = F.merge_splits(prev, None, ["QQQ"], [["QQQ", "2026-10-16", 4.0]], NONE, START, [], NONE, [], TODAY)     # 배율이 다르면 다른 사건
    assert ["QQQ", "2026-10-16", 4.0] in sp["splits"]


def test_override_rows_are_sticky_and_out_rows_remove(monkeypatch):
    log = Log(monkeypatch)
    prev = prev_data([["MSFT", "2023-06-23", 0.963957]], us=("MSFT",))
    prev["splitsInfo"]["fixed"] = [["MSFT", "2023-06-23", 0.963957, "시험: 지운 고정 줄"]]
    sp = F.merge_splits(prev, None, ["MSFT"], [], NONE, START, [], NONE, [], TODAY)             # 고정 표에서 지웠어요
    assert ["MSFT", "2023-06-23", 0.963957] in sp["splits"] and ["MSFT", "2023-06-23", 0.963957, "시험: 지운 고정 줄"] in sp["info"]["fixed"]
    assert sp["info"]["fixedKept"] == [["MSFT", "2023-06-23"]] and log.has("고정 표에서 지운 줄 1개")
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("MSFT", "2023-06-23"): (None, "시험: 빼요 (근거)")})
    sp = F.merge_splits(prev, None, ["MSFT"], [], NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [] and sp["info"]["fixed"] == [["MSFT", "2023-06-23", None, "시험: 빼요 (근거)"]] and sp["info"]["fixedKept"] == []


def test_override_applies_to_listed_or_carried_stocks_only(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("GONE", "2019-01-02"): (2.0, "시험: 목록에서 빠진 종목 (근거)"),
                                               ("NEVR", "2019-01-02"): (2.0, "시험: 한 번도 없던 종목 (근거)"),
                                               ("NVDA", "2024-06-10"): (10.0, "시험: 고정 (근거)")})
    prev = prev_data([["GONE", "2018-01-02", 3.0], ["NVDA", "2024-06-10", 10.0]], us=("NVDA",))
    sp = F.merge_splits(prev, None, ["NVDA"], [["NVDA", "2024-06-10", 20.0]], NONE, START, [], NONE, [], TODAY)
    assert ["GONE", "2019-01-02", 2.0] in sp["splits"] and not any(x[0] == "NEVR" for x in sp["splits"])
    assert sp["info"]["diff"] == []                                     # 고정 줄은 야후와 달라도 diff 가 아니에요 (배율)
    sp = F.merge_splits(prev, None, ["NVDA"], [], NONE, START, [], NONE, [], TODAY)
    assert sp["info"]["diff"] == []                                     # … 야후에 없어도 (빠짐)


def test_unresolved_diffs_are_carried_until_settled(monkeypatch):
    Log(monkeypatch)
    # 재사용된 티커: 옛 회사의 2019 분할은 오늘 다운로드(2023-09 부터) 밖이라 다시 보이지 않지만, 어제의 diff 를 매일 이어 적어요
    prev = prev_data([["REUS", "2019-03-04", 0.1]], us=("REUS",))
    prev["splitsInfo"]["diff"] = [["REUS", "2019-03-04", 0.1, None]]
    sp = F.merge_splits(prev, None, ["REUS"], [], NONE, START, [], NONE, [], TODAY)
    assert sp["info"]["diff"] == [["REUS", "2019-03-04", 0.1, None]] and ["REUS", "2019-03-04", 0.1] in sp["splits"]
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("REUS", "2019-03-04"): (None, "시험: 옛 회사의 분할이라 빼요 (근거)")})
    sp = F.merge_splits(prev, None, ["REUS"], [], NONE, START, [], NONE, [], TODAY)
    assert sp["info"]["diff"] == [] and sp["splits"] == []
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {})
    prev2 = prev_data([["REUS", "2024-03-04", 0.1]], us=("REUS",))
    prev2["splitsInfo"]["diff"] = [["REUS", "2024-03-04", 0.1, None]]
    sp = F.merge_splits(prev2, None, ["REUS"], [["REUS", "2024-03-04", 0.1]], NONE, START, [], NONE, [], TODAY)   # 야후가 다시 같은 값
    assert sp["info"]["diff"] == []


def test_override_table_pins():
    assert {k: v[0] for k, v in F.SPLIT_OVERRIDES.items()} == {
        ("RYAAY", "2024-09-30"): 2.5, ("HLT", "2017-01-04"): 1 / 3, ("DD", "2019-06-03"): 1 / 3, ("WTW", "2016-01-05"): 1 / 2.649,
        ("TRI", "2018-11-27"): 0.9079, ("TRI", "2023-06-23"): 0.963957, ("CBSH", "2016-11-30"): 1.05, ("CBSH", "2017-11-29"): 1.05,
        ("CBSH", "2019-12-02"): 1.05, ("CBSH", "2022-12-01"): 1.05, ("CBSH", "2023-12-01"): 1.05, ("HON", "2026-06-29"): 0.5}
    assert not any(t == "FERG" for t, _ in F.SPLIT_OVERRIDES)            # 2018 엔 미국 상장이 아니었어요


def test_tolerance_pins():
    assert V.SPLIT_CLEAN_TOL == 1e-9 and F.split_is_clean.__defaults__[1] is V.SPLIT_CLEAN_TOL
    assert F.split_is_clean(1.5000001) is False and V.simple_ratio(1.5000001) is False      # 1e-6 허용이면 깨끗하다고 봤을 값
    assert F.split_is_clean(1.5 + 1e-12) is True


def test_conflict_and_diff_tolerances_are_tight(monkeypatch):
    log = Log(monkeypatch)
    F.merge_splits(None, None, ["NVDA"], [["NVDA", "2024-06-10", 10.001]], NONE, START, [["NVDA", "2024-06-10", 10.0]], NONE, ["NVDA"], TODAY)
    assert log.has("두 다운로드의 배율이 달라요")
    prev = prev_data([["NVDA", "2024-06-10", 10.0]], us=("NVDA",))
    sp = F.merge_splits(prev, None, ["NVDA"], [["NVDA", "2024-06-10", 10.001]], NONE, START, [], NONE, [], TODAY)
    assert sp["info"]["diff"] == [["NVDA", "2024-06-10", 10.0, 10.001]]


@pytest.mark.parametrize("ago, warn", [(8, True), (6, False)])
def test_gate_new_old_dated_split_boundary(ago, warn):
    cur, prev, final = pair()
    d = (dt.date(2026, 10, 31) - dt.timedelta(days=ago)).isoformat()
    cur["data"]["splits"].append(["U0002", d, 2.0])
    r = row(check(cur, prev, final), SPC)
    assert ("지난 날짜로 새로 1: U0002" in r[1]) is warn, r


def test_gate_fixed_row_for_a_stock_that_left_the_list_is_not_a_failure():
    cur, prev, final = pair()
    cur["data"]["splits"].append(["GONEX", "2019-01-02", 2.0])
    cur["data"]["splitsInfo"]["fixed"].append(["GONEX", "2019-01-02", 2.0, "시험: 목록에서 빠진 종목의 고정 줄 (근거)"])
    r = row(check(cur, prev, final), SPL)
    assert r[3] != "FAIL", r


# ── #117 리뷰 3 ──────────────────────────────────────────
AAON_SEED = ({("AAON", "2023-08-17"): 1.5, **SEED[0]}, SEED[1] | {"AAON"}, SEED[2])


def test_seed_rows_of_an_unlisted_stock_wait_until_it_joins(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    us = ["NVDA", "TSLA", "AAPL", "WMT"]                                   # AAON 은 오늘 목록에 없어요 (10-30 ~ 11-11 의 여러 날처럼)
    f = F.splits_fields(None, us, [], [], START, TODAY, seed=AAON_SEED)
    assert not any(x[0] == "AAON" for x in f["splits"])
    prev = dict(f, stocks=[{"t": t, "cls": "us"} for t in us])
    f2 = F.splits_fields(prev, us + ["AAON"], [], [], START, TODAY + dt.timedelta(days=1), seed=AAON_SEED)    # 다시 든 날 나타나요
    assert ["AAON", "2023-08-17", 1.5] in f2["splits"]
    prev2 = dict(f2, stocks=[{"t": t, "cls": "us"} for t in us + ["AAON"]])
    f3 = F.splits_fields(prev2, us, [], [], START, TODAY + dt.timedelta(days=2), seed=AAON_SEED)               # 또 빠져도 실은 줄은 남아요
    assert ["AAON", "2023-08-17", 1.5] in f3["splits"]


def test_gate_first_publish_with_an_unlisted_seed_stock_passes(monkeypatch):
    Log(monkeypatch)
    cur, prev, final = pair(prev_splits=False)
    us = [s["t"] for s in cur["data"]["stocks"] if s.get("cls") == "us" and not s.get("fund")]
    seed = ({**{(t, d): r for t, d, r in V.MUST_SPLITS if (t, d) not in F.SPLIT_OVERRIDES}, ("AAON", "2023-08-17"): 1.5},
            set(us) | {"AAON"}, dt.date(2026, 10, 30))
    recent = sorted([t, d, r] for (t, d), r in seed[0].items() if d >= START.isoformat())      # 야후가 오늘 다운로드에서 보여 주는 줄
    f = F.splits_fields(prev["data"], us, [x for x in recent if x[0] in us], [], START, TODAY, seed=seed)
    assert f and not any(x[0] == "AAON" for x in f["splits"])
    cur["data"].update(f)
    rep = check(cur, prev, final)
    assert row(rep, SPL)[3] == "PASS" and row(rep, SPC)[3] == "SKIP", rep.table()
    # 다음 날 AAON 이 목록에 들어요: 그 줄이 새로 나타나고 관문은 통과 (목록에 있는 종목의 새 줄)
    nxt, _, _ = pair(prev_splits=False)
    nxt["data"]["stocks"].append(dict(next(s for s in nxt["data"]["stocks"] if s["t"] == "MSFT"), t="AAON"))
    prev_day = {"data": dict(cur["data"]), "corp": cur["corp"]}   # 어제 = 첫 발행본 (#107 의 표시 비교가 어제 corp.json 을 읽어요)
    f2 = F.splits_fields(cur["data"], us + ["AAON"], recent, [], START, TODAY, seed=seed)
    assert ["AAON", "2023-08-17", 1.5] in f2["splits"]
    nxt["data"].update(f2)
    rep = check(nxt, prev_day, final)
    assert row(rep, SPL)[3] == "PASS" and row(rep, SPC)[3] in ("PASS", "WARN") and not rep.failed, rep.table()


@pytest.mark.parametrize("recent, no_col", [(None, []), ([], ["NVDA", "TSLA", "AAPL", "WMT"])])
def test_first_publish_with_nothing_read_leaves_splits_out(monkeypatch, recent, no_col):
    log = Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    assert F.splits_fields(None, ["NVDA", "TSLA", "AAPL", "WMT"], recent, no_col, START, TODAY, seed=SEED) == {}
    assert log.has("하나도 읽지 못해 splits 를 쓰지 않아요")


@pytest.mark.parametrize("gap, same", [(10, True), (11, False)])
def test_same_event_window_boundary(monkeypatch, gap, same):
    Log(monkeypatch)
    d = (dt.date(2026, 10, 15) + dt.timedelta(days=gap)).isoformat()
    prev = prev_data([["QQQ", "2026-10-15", 2.0]], us=("QQQ",))
    sp = F.merge_splits(prev, None, ["QQQ"], [["QQQ", d, 2.0]], NONE, START, [], NONE, [], TODAY)
    assert (["QQQ", d, 2.0] in sp["splits"]) is (not same)


def test_yahoo_listing_the_same_split_on_two_dates_is_reported(monkeypatch):
    log = Log(monkeypatch)
    prev = prev_data([["QQQ", "2026-10-15", 2.0]], us=("QQQ",))
    sp = F.merge_splits(prev, None, ["QQQ"], [["QQQ", "2026-10-15", 2.0], ["QQQ", "2026-10-16", 2.0]], NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["QQQ", "2026-10-15", 2.0]] and sp["info"]["diff"] == [["QQQ", "2026-10-15", 2.0, 2.0, "2026-10-16"]]
    assert log.has("두 날짜에 적었어요", "QQQ 2026-10-15 · 2026-10-16")


def test_a_wrong_date_fixed_with_an_out_row_is_not_hidden(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {("QQQ", "2026-10-15"): (None, "시험: 날짜가 틀렸어요 — 10-16 이 맞아요 (근거)")})
    prev = prev_data([["QQQ", "2026-10-15", 2.0]], us=("QQQ",))
    sp = F.merge_splits(prev, None, ["QQQ"], [["QQQ", "2026-10-16", 2.0]], NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["QQQ", "2026-10-16", 2.0]] and sp["info"]["diff"] == []


def test_backfill_order_new_joiners_first_and_failures_rotate(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    bad = [f"B{i:02d}" for i in range(50)]                    # 어제부터 계속 실패하는 50 종목 (gap)
    new = [f"N{i}" for i in range(5)]
    prev = {"splits": [], "splitsFrom": "2016-01-01", "stocks": [{"t": t, "cls": "us"} for t in list(SEED[1]) + bad],
            "splitsInfo": {"gap": bad}}
    asked = []

    def hist(codes, today):
        asked.append(list(codes))
        return [], {"noCol": [c for c in codes if c.startswith("B")], "future": [], "bad": [], "spin": []}
    f = F.splits_fields(prev, list(SEED[1]) + bad + new, [], [], START, TODAY, seed=SEED, history=hist)
    assert asked[0][:5] == new and asked[0][5:] == bad[:15]            # 새 종목 먼저 · 어제 gap 은 그 순서대로
    assert f["splitsInfo"]["gap"] == bad[15:] + bad[:15]             # 이번에 묻지 않은 종목이 다음 실행의 앞으로


def test_kept_fx_history_is_dropped_only_when_fx_moved_more_than_10_percent(monkeypatch):
    Log(monkeypatch)
    pm = prev_macro(fresh="2026-10-29")
    assert F.kept_fx_hist(pm, "ecos", run_fx(), 1333.3, TODAY)[0] is not None
    h, why = F.kept_fx_hist(pm, "ecos", run_fx(), 1500.0, TODAY)
    assert h is None and "10%" in why


def test_published_rows_beat_the_seed_and_the_belt_checks_ratios(monkeypatch):
    log = Log(monkeypatch)
    prev = prev_data([["NVDA", "2024-06-10", 10.0]], us=("NVDA",))
    seed = ({("NVDA", "2024-06-10"): 20.0}, {"NVDA"}, dt.date(2026, 10, 30))
    sp = F.merge_splits(prev, seed, ["NVDA"], [], NONE, START, [], NONE, [], TODAY)
    assert sp["splits"] == [["NVDA", "2024-06-10", 10.0]]
    monkeypatch.setattr(F, "MUST_SPLITS", (("NVDA", "2024-06-10", 10.0),))
    assert F.splits_fields(None, ["NVDA"], [["NVDA", "2024-06-10", 20.0]], [], START, TODAY, seed=({}, {"NVDA"}, dt.date(2026, 10, 30))) == {}
    assert log.has("꼭 있어야 할 분할이 빠져")


def test_gate_warns_when_past_fx_rows_change_against_yesterday():
    cur, prev, final = pair(src="ecos")
    prev["macro"].update(fxHist={**_hist(cur), "rows": [list(r) for r in _hist(cur)["rows"][:-1]], "asOf": _hist(cur)["rows"][-2][0]},
                         fxHistSrc="ecos", fxHistFresh="2026-10-30")
    assert row(check(cur, prev, final), FXH)[3] == "PASS"                   # 어제보다 한 줄 늘었을 뿐
    for i in (100, 200, 300, 400, 500, 600):
        _hist(cur)["rows"][i][1] += 1.0
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "지난 줄이 어제와 달라요 6: " + _hist(cur)["rows"][100][0] in r[1], r
    cur, prev, final = pair(src="ecos")
    prev["macro"].update(fxHist={**_hist(cur), "rows": _hist(cur)["rows"] + [["2026-11-02", 1333.0]], "asOf": "2026-11-02"}, fxHistSrc="ecos")
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "asOf 2026-10-30 가 어제 2026-11-02 보다 앞이에요" in r[1], r
    prev["macro"].update(fxHistSrc="ecos_next")
    assert "출처가 어제 'ecos_next' 에서 바뀌었어요" in row(check(cur, prev, final), FXH)[1]


def test_gate_ignores_yesterdays_unfinished_yahoo_row():
    cur, prev, final = pair(src="yahoo_next")
    prow = [list(r) for r in _hist(cur)["rows"]]
    prow[-1][1] += 3.0                                                      # 어제 아침의 끝나지 않은 마지막 값은 오늘 바뀌어요
    prev["macro"].update(fxHist={"asOf": prow[-1][0], "final": False, "rows": prow}, fxHistSrc="yahoo_next")
    assert row(check(cur, prev, final), FXH)[3] == "PASS"


def test_prev_macro_is_read_leniently(tmp_path):
    cur, prev, final = pair()
    for name in ("data",):
        (tmp_path / f"{name}.json").write_text(__import__("json").dumps(prev[name], ensure_ascii=False), encoding="utf-8")
    got = V.load_prev(str(tmp_path), None)
    assert set(got) == {"data"}                                             # macro.json 이 없어도 그대로 (그 비교만 없이)
    (tmp_path / "macro.json").write_text("{ broken", encoding="utf-8")
    assert set(V.load_prev(str(tmp_path), None)) == {"data"}
    (tmp_path / "macro.json").write_text(__import__("json").dumps({"fxHist": None}), encoding="utf-8")
    assert set(V.load_prev(str(tmp_path), None)) == {"data", "macro"}


def test_prev_macro_is_read_from_git_too(tmp_path, monkeypatch):
    import json
    import subprocess
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)     # noqa: E731
    run("init", "-q")
    run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "0")
    (tmp_path / "data.json").write_text(json.dumps({"asOf": "2026-10-30"}), encoding="utf-8")
    run("add", "data.json")
    run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "1")
    monkeypatch.chdir(tmp_path)
    assert set(V.load_prev(None, "HEAD")) == {"data"}                     # macro.json 이 없는 발행본
    (tmp_path / "macro.json").write_text(json.dumps({"fxHistSrc": "ecos_close"}), encoding="utf-8")
    run("add", "macro.json")
    run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "2")
    got = V.load_prev(None, "HEAD")
    assert set(got) == {"data", "macro"} and got["macro"]["fxHistSrc"] == "ecos_close"


# ── #117 리뷰 4 ──────────────────────────────────────────
def _git_repo(tmp_path, files):
    import subprocess
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)     # noqa: E731
    run("init", "-q")
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
        run("add", name)
    run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "1")


@pytest.mark.parametrize("files", [{}, {"data.json": "{ broken"}, {"data.json": '{"fx": NaN}'}])
def test_load_prev_from_git_still_fails_on_a_bad_data_json(tmp_path, monkeypatch, files):
    # 직전 발행본의 data.json 은 예전처럼 엄격해요 (없거나 · 깨졌거나 · NaN 이면 멈춰요 — 빈 값으로 넘어가지 않아요)
    _git_repo(tmp_path, files)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exception):
        V.load_prev(None, "HEAD")


def test_load_prev_says_so_when_it_drops_yesterdays_macro(tmp_path, monkeypatch, capsys):
    import json
    _git_repo(tmp_path, {"data.json": json.dumps({"asOf": "2026-10-30"}), "macro.json": "{ broken"})
    monkeypatch.chdir(tmp_path)
    assert set(V.load_prev(None, "HEAD")) == {"data"}
    assert "직전 발행본의 macro.json 을 읽지 못해 환율 이력 비교(경고 줄) 없이 해요" in capsys.readouterr().out
    d = tmp_path / "dir"
    d.mkdir()
    (d / "data.json").write_text(json.dumps({"asOf": "2026-10-30"}), encoding="utf-8")
    assert set(V.load_prev(str(d), None)) == {"data"} and "macro.json 을 읽지 못해" in capsys.readouterr().out


def test_kept_splits_are_published_after_the_first_day(monkeypatch):
    # 첫 발행 뒤에는 야후를 못 읽은 날도 어제 줄을 그대로 실어요 (빼면 분할 전 기록의 주식 수가 바뀌어 보여요)
    Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    prev = prev_data([["NVDA", "2024-06-10", 10.0]], us=("NVDA",))
    f = F.splits_fields(prev, ["NVDA"], None, [], START, TODAY, seed=SEED)
    assert f["splitsSrc"] == "kept" and f["splitsAsOf"] == "2026-10-30" and ["NVDA", "2024-06-10", 10.0] in f["splits"]


def test_a_gap_stock_that_left_the_list_is_not_asked(monkeypatch):
    Log(monkeypatch)
    monkeypatch.setattr(F, "MUST_SPLITS", ())
    prev = {"splits": [], "splitsFrom": "2016-01-01", "stocks": [{"t": t, "cls": "us"} for t in list(SEED[1]) + ["GONE1", "STAY1"]],
            "splitsInfo": {"gap": ["GONE1", "STAY1"]}}
    asked = []
    hist = lambda codes, today: asked.append(list(codes)) or ([], {"noCol": [], "future": [], "bad": [], "spin": []})   # noqa: E731
    f = F.splits_fields(prev, list(SEED[1]) + ["STAY1"], [], [], START, TODAY, seed=SEED, history=hist)
    assert asked == [["STAY1"]] and f["splitsInfo"]["gap"] == [] and not any(x[0] == "GONE1" for x in f["splits"])


def _with_yesterday(cur, prev, final_last=True, rows=None):
    prow = [list(r) for r in (rows if rows is not None else _hist(cur)["rows"])]
    prev["macro"].update(fxHist={"asOf": prow[-1][0], "final": final_last, "rows": prow}, fxHistSrc=cur["macro"]["fxHistSrc"])
    return prow


def test_gate_n7_missing_inserted_and_last_final_rows():
    cur, prev, final = pair(src="ecos")
    _with_yesterday(cur, prev)
    del _hist(cur)["rows"][500]                                              # 어제 있던 지난 줄이 사라짐
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "지난 줄이 어제와 달라요 1: " in r[1], r
    cur, prev, final = pair(src="ecos")
    prow = _with_yesterday(cur, prev)
    gone = prow.pop(400)                                                     # 어제 없던 날짜가 오늘 끼어듦
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and f"어제 없던 지난 줄이 생겼어요 1: {gone[0]}" in r[1], r
    cur, prev, final = pair(src="ecos")
    _with_yesterday(cur, prev, final_last=True)
    _hist(cur)["rows"][-1][1] += 2.0                                         # 어제의 마지막 줄이 끝난 값이었으면 바뀌면 경고
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "지난 줄이 어제와 달라요 1: 2026-10-30" in r[1], r


@pytest.mark.parametrize("pfh", [{"asOf": "2026-10-30", "final": True, "rows": "x"}, {"asOf": "2026-10-30", "final": True, "rows": None},
                                 {"asOf": "2026-10-30", "final": True, "rows": 5}, ["2026-10-30"],
                                 {"asOf": "2026-10-30", "final": True, "rows": [["2026-10-29"], "x", None, ["2026-10-29", "1333"],
                                                                                 ["bad-date", 1333.0], ["2026-10-28", 0]]}])
def test_gate_n7_ignores_odd_shapes_of_yesterday(pfh):
    cur, prev, final = pair(src="ecos")
    prev["macro"].update(fxHist=pfh, fxHistSrc="ecos")
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "PASS", r


def test_gate_n7_only_when_publishing():
    cur, prev, final = pair(src="ecos")
    _with_yesterday(cur, prev)
    _hist(cur)["rows"][300][1] += 1.0
    assert row(check(cur, prev, final, mode="live"), FXH)[3] == "PASS"       # 사이트 점검은 어제와 비교하지 않아요


def test_gate_split_source_is_named_once():
    cur, prev, final = pair()
    cur["data"]["splitsSrc"] = "part"
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "WARN" and r[1].count("출처 part") == 1 and "일부 종목을 오늘 읽지 못함" in r[1], r


# ── 검토한 줄은 '정수가 아닌 새 배율' 경고에서 빼요 ─────────────────────
def test_gate_reviewed_rows_do_not_warn_when_their_stock_joins():
    # 시드의 AAON 2023-08-17 3:2 · 고정 표의 CBSH 2016-11-30 5% 주식배당: 그 종목이 오늘 목록에 다시 들어 새 줄로 나와도 경고하지 않아요
    cur, prev, final = pair()
    assert V.load_split_seed_rows()[("AAON", "2023-08-17")] == 1.5
    cur["data"]["splits"] += [["AAON", "2023-08-17", 1.5], ["CBSH", "2016-11-30", 1.05]]
    for t in ("AAON", "CBSH"):
        cur["data"]["stocks"].append(dict(next(s for s in cur["data"]["stocks"] if s["t"] == "MSFT"), t=t))
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "PASS" and "정수 아닌 배율" not in r[1], r


def test_gate_fresh_yahoo_rows_with_a_non_whole_ratio_still_warn():
    cur, prev, final = pair()
    cur["data"]["splits"] += [["U0003", "2026-10-29", 1.5],      # 시드에도 고정 표에도 없는 새 3:2
                              ["AAON", "2023-08-17", 1.25]]      # 시드에 있지만 배율이 달라요 → 검토한 줄이 아니에요
    cur["data"]["stocks"].append(dict(next(s for s in cur["data"]["stocks"] if s["t"] == "MSFT"), t="AAON"))
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "WARN" and "새 줄 정수 아닌 배율 2: AAON 2023-08-17 ×1.25, U0003 2026-10-29 ×1.5" in r[1], r


def test_gate_without_a_readable_seed_still_warns(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(V, "SPLIT_SEED_CSV", str(tmp_path / "missing.csv"))
    cur, prev, final = pair()
    cur["data"]["splits"].append(["AAON", "2023-08-17", 1.5])
    cur["data"]["stocks"].append(dict(next(s for s in cur["data"]["stocks"] if s["t"] == "MSFT"), t="AAON"))
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "WARN" and "AAON 2023-08-17 ×1.5" in r[1], r
    assert "분할 시드(missing.csv)를 읽지 못해" in capsys.readouterr().out
