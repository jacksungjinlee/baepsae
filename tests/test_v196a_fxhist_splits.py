# -*- coding: utf-8 -*-
"""v19.6a 데이터 (docs/tasks/v19.6-records-alerts-dark.md Part I.1 · A.6) — 네트워크 없이.

- macro.json fxHist: 원/달러 일별 종가 2016-01-01 ~ 이 실행의 환율 날짜. 최근 부분은 이 실행의 환율 시계열(data.json fx 의 출처) 그대로,
  그 앞은 야후 2016년부터 (실패하면 지난 발행본의 fxHist — 10일 안일 때만), 둘 다 안 되면 싣지 않아요. 오늘의 덜 끝난 봉 없음 · NaN 없음.
- data.json splits: [[코드, 날짜, 배율], …] 최근 3년, 미국 (야후 분할 칸). 배율 = 옛 1주가 새로 몇 주 (앱 held.js 와 같은 방향).
  오늘(KST) 뒤 날짜 없음 · 야후가 분할 칸에 적은 분사 조정(1253:1000 같은 값)은 넣지 않아요.
- 관문(validate_data.py) 세 줄: 환율 이력 · 주식 분할 목록 · 주식 분할 목록 변화.
"""
import datetime as dt
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
from fixture_data import good_pair, hilo_of  # noqa: E402

TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}
FXH, SPL, SPC = "환율 이력 (fxHist)", "주식 분할 목록 (splits)", "주식 분할 목록 변화 (직전 발행본과)"


# ── 가짜 환율 시계열 ─────────────────────────────────────
def weekdays(a, b):
    return [d for d in pd.date_range(a, b) if d.weekday() < 5]


def fx_series(a="2016-01-01", b="2026-10-30", last=None):
    """평일마다 1,100 ~ 1,450 사이를 천천히 움직이는 환율 (하루 변화는 아주 작아요). last 를 주면 마지막 값."""
    idx = weekdays(a, b)
    v = [1275.0 + 175.0 * math.sin(i / 300.0) for i in range(len(idx))]
    s = pd.Series(v, index=pd.DatetimeIndex(idx), dtype=float)
    if last is not None:
        s.iloc[-1] = last
    return s


def run_fx(full, fx_date="2026-10-30", start="2023-09-21"):
    """fetch_us 처럼: 이 실행의 환율 = start 부터 환율 날짜까지 (data.json fx 의 출처)."""
    f = full[(full.index >= pd.Timestamp(start)) & (full.index <= pd.Timestamp(fx_date))]
    return f


def frame(ser):
    """yf.download(단일 티커) 모양: ('Close', 'USDKRW=X') 열."""
    return pd.DataFrame({("Close", "USDKRW=X"): ser.values}, index=ser.index)


class Log:
    def __init__(self, monkeypatch):
        self.lines = []
        monkeypatch.setattr(F, "log", lambda *a: self.lines.append(" ".join(str(x) for x in a)))

    def has(self, *words):
        return any(all(w in ln for w in words) for ln in self.lines)


# ── fxHist: 파이프라인 ───────────────────────────────────
def test_fx_hist_rows_drop_bad_values_keep_last_of_a_date_and_round():
    idx = pd.DatetimeIndex(["2016-01-04", "2016-01-05", "2016-01-06", "2016-01-07", "2016-01-08", "2016-01-08", "2016-01-11"])
    s = pd.Series([1188.14, np.nan, np.inf, 0.0, 1190.0, 1191.26, -5.0], index=idx)
    rows, bad = F.fx_hist_rows(s)
    assert rows == [["2016-01-04", 1188.1], ["2016-01-08", 1191.3]]      # 소수 첫째 자리 · 같은 날은 뒤의 값
    assert bad == 5                                                       # NaN · inf · 0 · 음수 · 겹친 날짜 하나


def test_fx_hist_build_old_part_plus_the_runs_own_series():
    full = fx_series()
    fx = run_fx(full)
    hist, how = F.fx_hist_build(fx, full)
    assert hist is not None, how
    rows = hist["rows"]
    assert rows[0][0] == "2016-01-01" and hist["asOf"] == rows[-1][0] == "2026-10-30"
    assert rows[-1][1] == round(float(fx.iloc[-1]), 1)                    # 마지막 값 = data.json fx (같은 반올림)
    tail = [r for r in rows if r[0] >= "2023-09-21"]
    assert tail == F.fx_hist_rows(fx)[0]                                  # 최근 부분은 이 실행의 시계열 그대로
    assert all(a[0] < b[0] for a, b in zip(rows, rows[1:]))
    assert "앞부분" in how and "겹치는" in how


def test_fetch_fx_hist_cuts_at_the_fx_date_never_todays_partial_bar(monkeypatch):
    log = Log(monkeypatch)
    full = fx_series(b="2026-10-31")                       # 야후가 오늘(KST 10-31)의 덜 끝난 봉까지 돌려줘도
    fx = run_fx(full, fx_date="2026-10-30")
    asked = []

    def download(tk, **kw):
        asked.append((tk, kw["start"], kw["end"]))
        return frame(full)
    hist, src = F.fetch_fx_hist(fx, TODAY, None, download=download, sleep=lambda s: None)
    assert src == "yahoo" and hist["asOf"] == "2026-10-30" and hist["rows"][-1][0] == "2026-10-30"
    assert all(r[0] < TODAY.isoformat() for r in hist["rows"])
    assert asked == [("USDKRW=X", dt.date(2016, 1, 1), dt.date(2026, 11, 1))]     # 요청 한 번
    assert log.has("환율 이력(fxHist, 야후 USDKRW=X)", "2016-01-01 ~ 2026-10-30")


def test_fetch_fx_hist_retries_then_keeps_the_previous_publish_with_a_loud_line(monkeypatch):
    log = Log(monkeypatch)
    full = fx_series()
    fx = run_fx(full)
    prev_full = full[full.index <= pd.Timestamp("2026-10-29")]          # 어제 발행본: 10-29 까지
    prev = {"fxHist": {"asOf": "2026-10-29", "rows": F.fx_hist_rows(prev_full)[0]}}
    calls, slept = [], []

    def broken(tk, **kw):
        calls.append(tk)
        raise ConnectionError("야후가 막았어요")
    hist, src = F.fetch_fx_hist(fx, TODAY, prev, download=broken, sleep=slept.append)
    assert src == "kept" and len(calls) == F.FX_HIST_TRIES == 2 and slept == [F.FX_HIST_PAUSE]
    assert hist["asOf"] == "2026-10-30" and hist["rows"][0][0] == "2016-01-01"
    assert hist["rows"][-1][1] == round(float(fx.iloc[-1]), 1)
    assert log.has("!!", "지난 발행본(기준 2026-10-29)의 앞부분을 이어 써요")


def test_fetch_fx_hist_omits_when_the_previous_publish_is_too_old_or_missing(monkeypatch):
    log = Log(monkeypatch)
    full = fx_series()
    fx = run_fx(full)
    old = full[full.index <= pd.Timestamp("2026-10-19")]                 # 11일 전 (> FX_HIST_KEEP_DAYS 10)
    prev = {"fxHist": {"asOf": "2026-10-19", "rows": F.fx_hist_rows(old)[0]}}
    empty = lambda tk, **kw: pd.DataFrame({("Close", "USDKRW=X"): []})     # noqa: E731 — 야후 빈 응답
    assert F.fetch_fx_hist(fx, TODAY, prev, download=empty, sleep=lambda s: None) == (None, None)
    assert log.has("!! 환율 이력(fxHist)을 만들지 못했어요", "빈 응답", "10일 안이 아니에요", "싣지 않아요")
    assert F.fetch_fx_hist(fx, TODAY, {"curve": {}}, download=empty, sleep=lambda s: None) == (None, None)
    assert log.has("지난 발행본에 fxHist 없음")
    assert F.fetch_fx_hist(fx, TODAY, None, download=empty, sleep=lambda s: None) == (None, None)


@pytest.mark.parametrize("hurt, why", [
    (lambda s: s.where(s.index != pd.Timestamp("2018-03-05"), 12000.0), "범위"),           # 깨진 값 (FX_HI 밖)
    (lambda s: s.where(s.index != pd.Timestamp("2019-06-05"), 1500.0), "하루"),            # 하루 10% 넘게 튀는 값
    (lambda s: s[(s.index < pd.Timestamp("2017-02-01")) | (s.index > pd.Timestamp("2017-02-20"))], "비어요"),   # 19일 빔
    (lambda s: s[s.index >= pd.Timestamp("2020-01-02")], "첫날"),                          # 앞이 잘린 이력
    (lambda s: s * 1.01, "겹치는 날 값이 달라요"),                                           # 다른 시계열
])
def test_a_bad_yahoo_history_is_never_published_the_previous_one_is_used(monkeypatch, hurt, why):
    log = Log(monkeypatch)
    full = fx_series()
    fx = run_fx(full)
    bad = hurt(full.copy())
    hist, src = F.fetch_fx_hist(fx, TODAY, None, download=lambda tk, **kw: frame(bad), sleep=lambda s: None)
    assert (hist, src) == (None, None) and log.has("만들지 못했어요", why)
    prev = {"fxHist": {"asOf": "2026-10-29", "rows": F.fx_hist_rows(full[full.index <= pd.Timestamp("2026-10-29")])[0]}}
    hist, src = F.fetch_fx_hist(fx, TODAY, prev, download=lambda tk, **kw: frame(bad), sleep=lambda s: None)
    assert src == "kept" and hist["rows"][0][0] == "2016-01-01"


def test_fx_hist_problems_rules():
    ok = [["2016-01-04", 1180.0], ["2016-01-05", 1185.0], ["2016-01-12", 1190.0]]     # 7일 빔은 괜찮아요
    assert F.fx_hist_problems(ok) == []
    assert any("8일" in p for p in F.fx_hist_problems([["2016-01-04", 1180.0], ["2016-01-12", 1185.0]]))
    assert any("순서" in p for p in F.fx_hist_problems([["2016-01-05", 1180.0], ["2016-01-05", 1181.0]]))
    assert any("잘린" in p for p in F.fx_hist_problems([["2016-01-11", 1180.0], ["2016-01-12", 1181.0]]))
    assert F.fx_hist_problems([]) == ["줄이 없어요"]


def test_fx_hist_never_writes_nan(tmp_path, monkeypatch):
    Log(monkeypatch)
    full = fx_series()
    full.iloc[100] = np.nan                                   # 2016년의 깨진 값 하나 (앞부분에서 버려요)
    fx = run_fx(fx_series())
    hist, src = F.fetch_fx_hist(fx, TODAY, None, download=lambda tk, **kw: frame(full), sleep=lambda s: None)
    assert src == "yahoo"
    p = tmp_path / "macro.json"
    assert F.write_json(str(p), {"fxHist": hist}) == 0
    text = p.read_text(encoding="utf-8")
    assert "NaN" not in text and V.strict_loads(text, "macro.json")["fxHist"]["asOf"] == "2026-10-30"


# ── splits: 파이프라인 ───────────────────────────────────
def bulk(events, index=None, no_col=()):
    """yf.download(여러 티커, group_by='ticker', actions=True) 모양. events: {티커: {날짜: 배율}}."""
    idx = pd.DatetimeIndex(index or [d for d in pd.date_range("2023-09-21", "2026-11-02") if d.weekday() < 5])
    cols = {}
    for t, ev in events.items():
        cols[(t, "Close")] = np.linspace(10, 20, len(idx))
        if t not in no_col:
            s = pd.Series(0.0, index=idx)
            for d, r in ev.items():
                s[pd.Timestamp(d)] = r
            cols[(t, "Stock Splits")] = s.values
    return pd.DataFrame(cols, index=idx)


def test_us_splits_from_a_fake_yahoo_download(monkeypatch):
    data = bulk({"NVDA": {"2024-06-10": 10.0}, "AMCR": {"2026-01-15": 0.2}, "GE": {"2024-04-02": 1.253},
                 "CBSH": {"2024-12-03": 1.05}, "ONE": {"2025-01-06": 1.0}, "BIG": {"2025-01-06": 2000.0},
                 "OLD": {"2023-10-02": 2.0}, "SOON": {"2026-11-02": 4.0}, "NONE": {}, "GSAT": {"2025-02-11": 1 / 15}})
    out, info = F.us_splits(data, ["NVDA", "AMCR", "GE", "CBSH", "ONE", "BIG", "OLD", "SOON", "NONE", "GSAT"], TODAY)
    assert out == [["AMCR", "2026-01-15", 0.2], ["CBSH", "2024-12-03", 1.05], ["GSAT", "2025-02-11", 0.0666666667],
                   ["NVDA", "2024-06-10", 10.0]]
    # 배율 = 옛 1주가 새로 몇 주 (NVDA 10:1 → 10 · AMCR 1:5 병합 → 0.2) · 날짜 = 야후의 분할 날짜 그대로
    assert info["spin"] == ["GE 2024-04-02 ×1.253"]                # 야후가 분사를 분할 칸에 적은 것
    assert info["bad"] == ["ONE 2025-01-06 ×1", "BIG 2025-01-06 ×2000"]
    assert info["future"] == ["SOON 2026-11-02 ×4"] and info["old"] == 1 and info["noCol"] == []


def test_split_dates_use_the_korean_today_and_a_three_year_window():
    # 러너 시계는 UTC: 2026-11-12 16:30 UTC = 2026-11-13 01:30 KST → 오늘은 11-13 (UTC 날짜 11-12 가 아니에요)
    today = F.today_kst(dt.datetime(2026, 11, 12, 16, 30, tzinfo=dt.timezone.utc))
    assert today == dt.date(2026, 11, 13)
    assert F.split_window_from(today) == dt.date(2023, 11, 13)
    idx = ["2023-11-10", "2023-11-13", "2026-11-12", "2026-11-13", "2026-11-14"]
    data = bulk({"A": {"2023-11-10": 2.0, "2023-11-13": 3.0, "2026-11-12": 4.0, "2026-11-13": 5.0, "2026-11-14": 10.0}}, index=idx)
    out, info = F.us_splits(data, ["A"], today)
    assert out == [["A", "2023-11-13", 3.0], ["A", "2026-11-12", 4.0], ["A", "2026-11-13", 5.0]]
    assert info["future"] == ["A 2026-11-14 ×10"] and info["old"] == 1
    assert F.split_window_from(dt.date(2028, 2, 29)) == dt.date(2025, 2, 28)
    assert V.years_before(dt.date(2028, 2, 29), 3) == dt.date(2025, 2, 28)


def test_a_stock_without_the_split_column_is_unknown_not_empty(monkeypatch):
    data = bulk({"NVDA": {"2024-06-10": 10.0}, "XYZ": {}}, no_col=("XYZ",))
    out, info = F.us_splits(data, ["NVDA", "XYZ"], TODAY)
    assert out == [["NVDA", "2024-06-10", 10.0]] and info["noCol"] == ["XYZ"]


@pytest.mark.parametrize("r, clean", [
    (10.0, True), (2.0, True), (1.5, True), (0.2, True), (1 / 15, True), (0.0666666667, True), (0.3333333333, True), (50.0, True),
    (1.05, True), (1.25, True), (0.004, True), (25.0, True),
    (1.253, False), (1.196, False), (2.39, False), (1.01, False), (2.499, False), (0.9535, False), (1.0476, False), (1.02, False),
])
def test_clean_ratio_rule_pipeline_and_gate_agree(r, clean):
    # 실제 야후 값 (2026-11-13): GE 1253:1000 · MMM 1196:1000 · DD 239:100 · J 101:100 · RYAAY 2499:1000 · HON 1907:2000 은 분사 조정,
    # CBSH 105:100 (= 21:20, 5% 주식배당) · GSAT 1:15 · DD 1:3 은 진짜 주식 수 변화
    assert F.split_is_clean(r) is clean
    assert V.simple_ratio(r) is clean


def test_merge_splits_paths():
    prev = {"splits": [["NVDA", "2024-06-10", 10.0], ["GONE", "2024-01-02", 2.0], ["OLD", "2023-01-03", 2.0],
                       ["GE", "2024-04-02", 1.253], ["AMCR", "2026-01-15", 0.2]]}
    us = ["NVDA", "AMCR", "OLD", "GE"]
    fresh = [["NVDA", "2024-06-10", 10.0]]
    assert F.merge_splits(fresh, [], prev, us, TODAY) == (fresh, "yahoo", "")
    got, src, why = F.merge_splits(None, [], prev, us, TODAY)       # 이번 실행이 읽지 못함 → 지난 목록 (오늘 종목 · 3년 · 깨끗한 배율)
    assert src == "kept" and got == [["AMCR", "2026-01-15", 0.2], ["NVDA", "2024-06-10", 10.0]] and "2건" in why
    assert F.merge_splits(None, [], {}, us, TODAY)[:2] == (None, None)
    got, src, why = F.merge_splits(fresh, ["AMCR"], prev, us, TODAY)   # 한 종목만 칸이 없음 → 그 종목만 지난 목록에서
    assert src == "kept" and got == [["AMCR", "2026-01-15", 0.2], ["NVDA", "2024-06-10", 10.0]]
    got, src, why = F.merge_splits(fresh, ["AMCR"], {}, us, TODAY)
    assert src == "part" and got == fresh and "AMCR" in why


def test_bulk_us_download_keeps_the_split_column():
    # 분할 칸은 시세를 받는 그 다운로드에서 와요 (새 요청 없음): actions=True 가 빠지면 모든 종목이 '모름'이 돼요
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    call = src.split("data = yf.download(syms,", 1)[1].split(")", 1)[0]
    assert "actions=True" in call and "auto_adjust=True" in call


# ── 관문 ─────────────────────────────────────────────────
def fx_rows(end="2026-10-30", last=1333.3):
    rows, _ = F.fx_hist_rows(fx_series(b=end, last=last))
    return rows


def with_new(cur, fxh=True, splits=True):
    cur["data"]["fxDate"] = "2026-10-30"
    if fxh:
        rows = fx_rows()
        cur["macro"]["fxHist"] = {"asOf": rows[-1][0], "rows": rows}
        cur["macro"]["fxHistSrc"] = "yahoo"
    if splits:
        cur["data"]["splits"] = [["NVDA", "2024-06-10", 10.0], ["QQQ", "2026-10-15", 2.0], ["U0001", "2025-03-03", 0.1]]
        cur["data"]["splitsSrc"] = "yahoo"
    return cur


def pair(prev_splits=True):
    cur, prev, final = good_pair()
    with_new(cur)
    if prev_splits:
        prev["data"]["splits"] = [list(x) for x in cur["data"]["splits"]]
    return cur, prev, final


def check(cur, prev, final, mode="publish", today=TODAY):
    return V.run_checks(cur, prev, final, today, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                        hilo=hilo_of(cur, V.MUST))


def row(rep, name):
    return next((r for r in rep.rows if r[0] == name), None)


def test_gate_good_new_fields_pass():
    cur, prev, final = pair()
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert row(rep, FXH)[3] == "PASS" and row(rep, FXH)[1].startswith("2016-01-01 ~ 2026-10-30 · ")
    assert "마지막 1,333.3 = fx · 출처 yahoo" in row(rep, FXH)[1]
    assert row(rep, SPL)[3] == "PASS" and row(rep, SPL)[1].startswith("3건 · 최근 QQQ 2026-10-15 ×2")
    assert row(rep, SPC)[3] == "PASS" and row(rep, SPC)[1] == "그대로 (어제 3건 → 오늘 3건)"
    live = check(cur, None, final, mode="live")
    assert row(live, FXH)[3] == "PASS" and row(live, SPL)[3] == "PASS" and row(live, SPC) is None      # 사이트 점검엔 비교 줄 없음


def test_gate_missing_fx_hist_warns_never_fails():
    cur, prev, final = pair()
    del cur["macro"]["fxHist"]
    for mode, p in (("publish", prev), ("live", None)):
        r = row(check(cur, p, final, mode=mode), FXH)
        assert r[3] == "WARN" and r[1].startswith("없음"), r


def test_gate_kept_fx_hist_warns():
    cur, prev, final = pair()
    cur["macro"]["fxHistSrc"] = "kept"
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "WARN" and "지난 발행본" in r[1], r


def _hist(cur):
    return cur["macro"]["fxHist"]


@pytest.mark.parametrize("hurt, said", [
    (lambda h, d: h["rows"].reverse(), "날짜 차례"),
    (lambda h, d: h["rows"].insert(5, list(h["rows"][5])), "날짜 차례"),
    (lambda h, d: h["rows"].__delitem__(slice(300, 310)), "빈 날"),
    (lambda h, d: h["rows"][400].__setitem__(1, h["rows"][400][1] * 1.2), "큰 변화"),
    (lambda h, d: h["rows"][0].__setitem__(1, 880.0), "범위 밖"),
    (lambda h, d: h.__setitem__("asOf", "2026-10-29"), "asOf"),
    (lambda h, d: h["rows"].pop(), "fxDate"),
    (lambda h, d: h["rows"][-1].__setitem__(1, 1333.4), "마지막 값"),
    (lambda h, d: h.__setitem__("rows", h["rows"][10:]), "첫날"),
    (lambda h, d: h["rows"][7].__setitem__(1, "1180.5"), "모양"),
    (lambda h, d: h["rows"][7].__setitem__(1, True), "모양"),
    (lambda h, d: h["rows"][7].__setitem__(0, "2016-02-30"), "모양"),
    (lambda h, d: h.__setitem__("rows", []), "rows"),
    (lambda h, d: d.update({"fxDate": "2026-10-31"}) or h["rows"].append(["2026-10-31", 1333.3]) or h.update({"asOf": "2026-10-31"}),
     "오늘"),
])
def test_gate_malformed_fx_hist_fails(hurt, said):
    cur, prev, final = pair()
    hurt(_hist(cur), cur["data"])
    r = row(check(cur, prev, final), FXH)
    assert r[3] == "FAIL" and said in r[1], r


def test_gate_missing_splits_warns_but_fails_when_yesterday_had_them():
    cur, prev, final = pair(prev_splits=False)
    del cur["data"]["splits"]
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "WARN" and r[1].startswith("없음"), r
    assert row(check(cur, None, final, mode="live"), SPL)[3] == "WARN"
    prev["data"]["splits"] = [["NVDA", "2024-06-10", 10.0]]
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "FAIL" and "직전 발행본에는 있었어요" in r[1], r


@pytest.mark.parametrize("bad, said", [
    (["NVDA", "2024-06-10"], "모양"),
    (["NVDA", "2024-06-31", 2.0], "모양"),
    ([5930, "2024-06-10", 2.0], "모양"),
    (["NVDA", "2024-06-10", "10"], "모양"),
    (["MSFT", "2025-01-06", 1.0], "배율 1"),
    (["MSFT", "2025-01-06", 0.0], "배율 0"),
    (["MSFT", "2025-01-06", 2000.0], "배율 2000"),
    (["MSFT", "2024-04-02", 1.253], "깨끗한 분수가 아니에요"),
    (["MSFT", "2026-11-01", 2.0], "오늘 뒤"),
    (["ZZZZ", "2025-01-06", 2.0], "오늘 목록에 없음"),
    (["NVDA", "2024-06-10", 10.0], "두 번"),
])
def test_gate_malformed_splits_fail(bad, said):
    cur, prev, final = pair()
    cur["data"]["splits"].append(bad)
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "FAIL" and said in r[1], r


def test_gate_splits_not_a_list_fails():
    cur, prev, final = pair()
    cur["data"]["splits"] = {"NVDA": 10}
    assert row(check(cur, prev, final), SPL)[3] == "FAIL"


def test_gate_split_after_the_us_date_or_kept_list_warns():
    cur, prev, final = pair()
    cur["data"]["splits"].append(["MSFT", "2026-10-31", 2.0])       # 오늘(KST) 날짜 · 미국 기준일 10-30 뒤
    prev["data"]["splits"].append(["MSFT", "2026-10-31", 2.0])
    r = row(check(cur, prev, final), SPL)
    assert r[3] == "WARN" and "미국 기준일 2026-10-30 뒤 날짜: MSFT 2026-10-31" in r[1], r
    cur, prev, final = pair()
    for src in ("kept", "part", None):
        cur["data"]["splitsSrc"] = src
        r = row(check(cur, prev, final), SPL)
        assert r[3] == "WARN" and f"출처 {src}" in r[1], r


def test_gate_compares_splits_with_yesterday():
    cur, prev, final = pair()
    prev["data"]["splits"] += [["AAPL", "2025-05-05", 4.0],              # 오늘 사라짐 → 경고
                               ["MSFT", "2023-10-20", 2.0]]              # 3년이 지나 빠짐 → 정상 (오늘 창의 첫날 2023-10-31)
    cur["data"]["splits"][0][2] = 20.0                                   # NVDA 배율 바뀜 → 경고
    cur["data"]["splits"].append(["U0002", "2024-02-01", 3.0])           # 어제도 있던 종목에 오래된 분할이 새로 → 경고
    cur["data"]["splits"].append(["QQQ", "2026-10-29", 2.0])             # 이틀 전 분할 새로 → 정상 (새 분할)
    rep = check(cur, prev, final)
    r = row(rep, SPC)
    assert r[3] == "WARN", r
    assert "사라짐 1: AAPL 2025-05-05 ×4" in r[1] and "배율 바뀜 1: NVDA 2024-06-10 ×10→×20" in r[1]
    assert "지난 날짜로 새로 1: U0002 2024-02-01 ×3" in r[1] and "MSFT" not in r[1] and "2026-10-29" not in r[1]
    assert any(t == "주식 분할 목록 변화 (직전 발행본과)" and "사라짐 AAPL 2025-05-05 ×4" in items for t, items in rep.details)
    assert not rep.failed, rep.table()


def test_gate_split_of_a_stock_new_to_the_list_or_gone_from_it():
    cur, prev, final = pair()
    prev["data"]["stocks"] = [s for s in prev["data"]["stocks"] if s["t"] != "U0003"]
    cur["data"]["splits"].append(["U0003", "2024-02-01", 2.0])           # 오늘 새로 들어온 종목의 지난 분할 → 정상
    prev["data"]["splits"].append(["DEAD", "2025-02-03", 2.0])           # 목록에서 빠진 종목의 분할 → 경고 (이유를 적어요)
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "WARN" and "DEAD 2025-02-03 ×2 (종목이 오늘 목록에 없음)" in r[1] and "U0003" not in r[1], r


def test_gate_without_yesterdays_list_skips_the_comparison():
    cur, prev, final = pair(prev_splits=False)
    r = row(check(cur, prev, final), SPC)
    assert r[3] == "SKIP" and "첫 발행" in r[2], r


def test_gate_does_not_crash_on_odd_shapes():
    cur, prev, final = pair()
    cur["macro"]["fxHist"] = ["2016-01-04", 1180.0]
    prev["data"]["splits"] = [["NVDA", "2024-06-10"], "x", None, ["U0001", "2025-03-03", "0.1"]] + [list(x) for x in cur["data"]["splits"]]
    rep = check(cur, prev, final)
    assert row(rep, FXH)[3] == "FAIL" and row(rep, SPC)[3] == "PASS", rep.table()     # 어제의 깨진 줄은 비교에서 빼요


def test_pipeline_reads_its_lines_from_the_gate():
    # 파이프라인은 관문의 기준을 읽어요 (같은 선) — 검사 코드는 따로예요
    for k in ("FX_LO", "FX_HI", "FX_HIST_FROM", "FX_HIST_FIRST_BY", "FX_HIST_GAP_MAX", "FX_HIST_JUMP", "SPLIT_R", "SPLIT_SIMPLE_MAX",
              "SPLIT_YEARS"):
        assert getattr(F, k) == getattr(V, k), k
