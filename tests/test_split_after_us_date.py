# -*- coding: utf-8 -*-
"""2026-11-20: 미국 기준일(usPxDate) 뒤 날짜의 분할은 data.json splits 에 넣지 않아요 (fetch_data.hold_late_splits) — 네트워크 없이.

data.json 의 미국 가격은 usPxDate 의 종가예요. 앱은 실린 분할을 그 날짜 앞의 모든 기록에 바로 적용해요 (src/v2/held.js splitFactor ·
날짜 위 한도 없음). 06:40 KST 발행의 usPxDate 는 한국 오늘보다 하루 앞이라, 야후가 오늘(미국 날짜) 분할을 이미 적었으면 분할 뒤 주식 수 ×
분할 전 가격이 돼요 (2026-11-20 21:17 KST 시험 실행: usPxDate 11-19 · 야후 SNDK 11-20 ×8). 분할 날짜 = 새 주식 수로 거래가 시작된 첫 미국
거래일 (src/v2/lots.js) — 날짜가 usPxDate 와 같으면 그 종가는 이미 분할 뒤라 넣어요. 뒤 날짜만 빼 두고 (splitsInfo.held · "!!" 로그),
usPxDate 가 그 날짜에 닿는 첫 실행에 들어가요. 지난 발행본에 이미 실린 줄은 빼지 않아요 (빼면 관문 '주식 분할 목록 변화'가 실패):
splitsInfo.lateKept · 관문 '미국 기준일 뒤 날짜' 경고가 그대로 알려요. 관문(validate_data.py)은 바꾸지 않았어요.
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
from fixture_data import good_pair, hilo_of  # noqa: E402

D = dt.date
START = D(2023, 11, 20)            # 오늘 시세 다운로드의 첫날 (약 3년)
NO_HIST = lambda codes, today: ([], {"noCol": [], "future": [], "bad": [], "spin": []})   # noqa: E731
SPL, SPC = "주식 분할 목록 (splits)", "주식 분할 목록 변화 (직전 발행본과)"


class Log:
    def __init__(self, monkeypatch):
        self.lines = []
        monkeypatch.setattr(F, "log", lambda *a: self.lines.append(" ".join(str(x) for x in a)))

    def has(self, *words):
        return any(all(w in ln for w in words) for ln in self.lines)


def download(events, end):
    """yf.download(..., actions=True, group_by='ticker') 모양: {티커: {날짜: 배율}} — 평일 2023-11-20 ~ end."""
    idx = pd.DatetimeIndex([d for d in pd.date_range(START, end) if d.weekday() < 5])
    cols = {}
    for t, ev in events.items():
        cols[(t, "Close")] = np.linspace(10, 20, len(idx))
        s = pd.Series(0.0, index=idx)
        for d, r in ev.items():
            s[pd.Timestamp(d)] = r
        cols[(t, "Stock Splits")] = s.values
    return pd.DataFrame(cols, index=idx)


# 2016년부터의 이력: 작은 시드 (이 종목들은 다시 읽지 않아요)
SEED = ({("NVDA", "2021-07-20"): 4.0, ("NVDA", "2024-06-10"): 10.0}, {"NVDA", "SNDK", "AAPL"}, D(2026, 11, 13))
US = ["NVDA", "SNDK", "AAPL"]


def publish(fields, us=US):
    """발행한 data.json 의 분할 칸 (다음 실행의 지난 발행본)."""
    return dict(json.loads(json.dumps(fields, allow_nan=False)), stocks=[{"t": t, "cls": "us"} for t in us])


def run(prev, today, us_date, events, monkeypatch, us=US, seed=SEED, history=NO_HIST):
    """main 의 분할 부분 그대로: 오늘 시세 다운로드(us_splits) → splits_fields → hold_late_splits."""
    monkeypatch.setattr(F, "MUST_SPLITS", ())          # 이 시험의 작은 시드엔 꼭 있어야 할 분할이 없어요 (그 안전장치는 test_v196a 가 봐요)
    recent, info = F.us_splits(download(events, today), us, today)
    f = F.splits_fields(prev, us, recent, info["noCol"], START, today, seed=seed, history=history)
    return F.hold_late_splits(f, prev, us_date), info


def keys(fields):
    return [x[:2] for x in fields["splits"]]


# ── 1. SNDK: 미국 기준일 11-19 · 야후 11-20 ×8 → 빼 둠 · 다음 실행 (미국 기준일 11-20) → 실음 ───────────
def test_sndk_split_after_the_us_date_waits_for_the_next_publish(monkeypatch):
    log = Log(monkeypatch)
    ev = {"NVDA": {"2024-06-10": 10.0}, "SNDK": {"2026-11-20": 8.0}, "AAPL": {}}
    # 2026-11-20 21:17 KST 시험 실행: 한국 오늘 11-20 · 미국 기준일 11-19 (미국 11-20 장은 아직)
    f1, info = run(None, D(2026, 11, 20), D(2026, 11, 19), ev, monkeypatch)
    assert info["future"] == []                                   # 한국 오늘 뒤가 아니라 예전 규칙(future)으로는 들어갔어요
    assert ["SNDK", "2026-11-20"] not in keys(f1)
    assert f1["splitsInfo"]["held"] == [["SNDK", "2026-11-20", 8.0]] and f1["splitsInfo"]["lateKept"] == []
    assert ["NVDA", "2024-06-10"] in keys(f1) and ["NVDA", "2021-07-20"] in keys(f1)
    assert log.has("!!", "1건", "SNDK 2026-11-20 ×8 (미국 기준일 2026-11-19 뒤라 다음 발행까지 기다려요)")
    # 다음 날 06:40 KST: 미국 기준일 11-20 (분할 날 종가 = 이미 분할 뒤) → 실어요
    log.lines.clear()
    f2, _ = run(publish(f1), D(2026, 11, 21), D(2026, 11, 20), ev, monkeypatch)
    assert ["SNDK", "2026-11-20", 8.0] in f2["splits"] and f2["splitsInfo"]["held"] == [] and f2["splitsInfo"]["lateKept"] == []
    assert log.has("미국 기준일(usPxDate) 2026-11-20 뒤 날짜의 분할 0건") and not log.has("다음 발행까지 기다려요")


# ── 2. 월요일: 미국 기준일 금 11-20 · 한국 오늘 월 11-23 · 분할 11-23 → 빼 둠 (11-24 는 예전처럼 future) ─────────
def test_monday_publish_holds_a_split_effective_that_monday(monkeypatch):
    log = Log(monkeypatch)
    ev = {"NVDA": {"2024-06-10": 10.0}, "SNDK": {}, "AAPL": {"2026-11-23": 4.0}}
    prev = publish(run(None, D(2026, 11, 21), D(2026, 11, 20), {"NVDA": {"2024-06-10": 10.0}, "SNDK": {}, "AAPL": {}}, monkeypatch)[0])
    f, info = run(prev, D(2026, 11, 23), D(2026, 11, 20), ev, monkeypatch)
    assert ["AAPL", "2026-11-23"] not in keys(f) and f["splitsInfo"]["held"] == [["AAPL", "2026-11-23", 4.0]]
    assert log.has("!!", "AAPL 2026-11-23 ×4 (미국 기준일 2026-11-20 뒤라 다음 발행까지 기다려요)")
    # 다운로드 표가 11-24 까지 있어도 한국 오늘 뒤 날짜는 예전처럼 future (held 가 아니에요)
    ev2 = {"NVDA": {"2024-06-10": 10.0}, "SNDK": {}, "AAPL": {"2026-11-24": 4.0}}
    recent, info2 = F.us_splits(download(ev2, D(2026, 11, 24)), US, D(2026, 11, 23))
    assert info2["future"] == ["AAPL 2026-11-24 ×4"] and ["AAPL", "2026-11-24", 4.0] not in recent
    # 화요일 06:40: 미국 기준일 월 11-23 → 실어요
    f3, _ = run(publish(f), D(2026, 11, 24), D(2026, 11, 23), ev, monkeypatch)
    assert ["AAPL", "2026-11-23", 4.0] in f3["splits"] and f3["splitsInfo"]["held"] == []


# ── 3. 날짜 = 미국 기준일 → 실어요 (그 종가가 이미 분할 뒤 · lots.js: 분할 날짜 = 새 주식 수의 첫 미국 거래일) ─────────
def test_a_split_dated_on_the_us_date_is_published(monkeypatch):
    log = Log(monkeypatch)
    f, _ = run(None, D(2026, 11, 20), D(2026, 11, 19), {"NVDA": {}, "SNDK": {"2026-11-19": 8.0}, "AAPL": {}}, monkeypatch)
    assert ["SNDK", "2026-11-19", 8.0] in f["splits"] and f["splitsInfo"]["held"] == []
    assert not log.has("다음 발행까지 기다려요")
    # 경계 한 칸: 하루 뒤면 빼 둬요
    g = F.hold_late_splits({"splits": [["SNDK", "2026-11-19", 8.0], ["SNDK", "2026-11-20", 2.0]], "splitsInfo": {}}, None, D(2026, 11, 19))
    assert g["splits"] == [["SNDK", "2026-11-19", 8.0]] and g["splitsInfo"]["held"] == [["SNDK", "2026-11-20", 2.0]]


# ── 4. 어디서 왔든: 2016년부터 새로 읽은 종목(backfill) · 시드 · 고정 표 ───────────────────────────────────
def test_backfill_seed_and_override_rows_after_the_us_date_are_held(monkeypatch):
    log = Log(monkeypatch)
    asked = []

    def history(codes, today):          # 시드에도 어제에도 없는 NEWX 만 2016년부터 읽어요
        asked.append(list(codes))
        return [["NEWX", "2019-05-01", 2.0], ["NEWX", "2026-11-20", 3.0]], {"noCol": [], "future": [], "bad": [], "spin": []}
    seed = ({("NVDA", "2024-06-10"): 10.0, ("SNDK", "2026-11-20"): 2.0}, {"NVDA", "SNDK", "AAPL"}, D(2026, 11, 20))
    monkeypatch.setattr(F, "SPLIT_OVERRIDES", {**F.SPLIT_OVERRIDES, ("AAPL", "2026-11-20"): (0.5, "시험: 미국 기준일 뒤 날짜의 고정 줄")})
    us = US + ["NEWX"]
    f, _ = run(None, D(2026, 11, 20), D(2026, 11, 19), {t: {} for t in us}, monkeypatch, us=us, seed=seed, history=history)
    assert asked == [["NEWX"]]
    assert f["splitsInfo"]["held"] == [["AAPL", "2026-11-20", 0.5], ["NEWX", "2026-11-20", 3.0], ["SNDK", "2026-11-20", 2.0]]
    assert keys(f) == [["NEWX", "2019-05-01"], ["NVDA", "2024-06-10"]]
    assert ["AAPL", "2026-11-20", 0.5, "시험: 미국 기준일 뒤 날짜의 고정 줄"] in f["splitsInfo"]["fixed"]   # 고정 표 자체는 그대로 실려요
    assert log.has("!!", "3건", "NEWX 2026-11-20 ×3 (미국 기준일 2026-11-19 뒤라", "SNDK 2026-11-20 ×2 (", "AAPL 2026-11-20 ×0.5 (")


# ── 5. 지난 발행본에 이미 실린 줄 (예전 코드가 미국 기준일 뒤 날짜를 실었거나 기준일이 뒤로 간 날) ─────────────
def test_a_row_already_published_after_the_us_date_is_kept_and_said_loudly(monkeypatch):
    log = Log(monkeypatch)
    ev = {"NVDA": {"2024-06-10": 10.0}, "SNDK": {"2026-11-20": 8.0}, "AAPL": {}}
    old = run(None, D(2026, 11, 20), D(2026, 11, 19), ev, monkeypatch)[0]
    old = dict(old, splits=sorted(old["splits"] + [["SNDK", "2026-11-20", 8.0]]))      # 이 수정 전 코드의 발행본
    prev = publish(old)
    log.lines.clear()
    f, _ = run(prev, D(2026, 11, 20), D(2026, 11, 19), ev, monkeypatch)                # 미국 기준일이 그대로인 다음 실행
    assert ["SNDK", "2026-11-20", 8.0] in f["splits"]
    assert f["splitsInfo"]["held"] == [] and f["splitsInfo"]["lateKept"] == [["SNDK", "2026-11-20", 8.0]]
    assert log.has("!!", "지난 발행본에 이미 실린 분할 1건은 그대로 둬요", "SNDK 2026-11-20 ×8")
    assert not log.has("다음 발행까지 기다려요")


def test_dropping_an_already_published_row_would_fail_the_gate_so_it_is_kept():
    # 왜 빼지 않나: 관문 '주식 분할 목록 변화'는 어제 실린 분할이 사라지면 실패해요 (고정 표의 out 줄만 경고). 관문은 바꾸지 않았어요.
    cur, prev, final = gate_pair()
    for d in (cur["data"], prev["data"]):
        d["splits"].append(["MSFT", "2026-10-31", 2.0])                   # 어제 실린 미국 기준일(10-30) 뒤 날짜
    fields = F.hold_late_splits(split_fields_of(cur), prev["data"], D(2026, 10, 30))
    assert ["MSFT", "2026-10-31", 2.0] in fields["splits"] and fields["splitsInfo"]["lateKept"] == [["MSFT", "2026-10-31", 2.0]]
    cur["data"].update(fields)
    rep = check(cur, prev, final)
    assert row(rep, SPC)[3] == "PASS", row(rep, SPC)
    assert row(rep, SPL)[3] == "WARN" and "미국 기준일 2026-10-30 뒤 날짜: MSFT 2026-10-31" in row(rep, SPL)[1], row(rep, SPL)   # 예전 경고가 알려요
    cur["data"]["splits"] = [x for x in cur["data"]["splits"] if x[0] != "MSFT"]          # 뺐다면
    assert row(check(cur, prev, final), SPC)[3] == "FAIL"


# ── 6. 관문: 빼 둔 줄 때문에 실패하지 않아요 (꼭 있어야 할 분할 · 새 줄 · 직전 발행본) · 다음 실행의 새 줄도 통과 ─────────
NEW_US = ("TSLA", "AMZN", "GOOGL", "WMT", "CMG", "HLT", "RYAAY")
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}


def gate_pair():
    """fixture_data.good_pair (오늘 10-31 · 미국 기준일 10-30) + 꼭 있어야 할 분할의 종목과 줄 (어제와 오늘 같은 목록)."""
    cur, prev, final = good_pair()
    rows = sorted([list(x) for x in V.MUST_SPLITS] + [["RYAAY", "2024-09-30", 2.5]])
    fixed = [[t, d, r, n] for (t, d), (r, n) in sorted(F.SPLIT_OVERRIDES.items())]
    for files, as_of in ((cur, "2026-10-31"), (prev, "2026-10-30")):
        us0 = next(s for s in files["data"]["stocks"] if s["t"] == "MSFT")
        files["data"]["stocks"] += [dict(us0, t=t) for t in NEW_US]
        files["data"].update(splits=[list(x) for x in rows], splitsFrom=V.SPLITS_FROM, splitsAsOf=as_of, splitsSrc="yahoo",
                             splitsInfo={"noCol": 0, "gap": [], "diff": [], "fixed": [list(x) for x in fixed]})
    return cur, prev, final


def split_fields_of(files):
    return {k: json.loads(json.dumps(files["data"][k])) for k in ("splits", "splitsFrom", "splitsAsOf", "splitsSrc", "splitsInfo")}


def check(cur, prev, final, mode="publish", today=D(2026, 10, 31)):
    return V.run_checks(cur, prev, final, today, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                        hilo=hilo_of(cur, V.MUST))


def row(rep, name):
    return next((r for r in rep.rows if r[0] == name), None)


def test_gate_passes_a_publish_with_a_held_split_and_the_next_one_with_it(monkeypatch):
    Log(monkeypatch)
    assert D(2026, 10, 30).isoformat() == good_pair()[0]["data"]["usPxDate"]
    cur, prev, final = gate_pair()
    base = check(cur, prev, final)
    assert row(base, SPL)[3] == "PASS" and row(base, SPC)[3] == "PASS"
    # 오늘 야후가 미국 기준일(10-30) 뒤인 10-31 (한국 오늘) 날짜의 MSFT 2:1 을 적었어요 → 빼 둬요
    f = split_fields_of(cur)
    f["splits"] = sorted(f["splits"] + [["MSFT", "2026-10-31", 2.0]])
    cur["data"].update(F.hold_late_splits(f, prev["data"], D(2026, 10, 30)))
    assert cur["data"]["splitsInfo"]["held"] == [["MSFT", "2026-10-31", 2.0]]
    rep = check(cur, prev, final)
    assert row(rep, SPL)[3] == "PASS" and "미국 기준일" not in row(rep, SPL)[1], row(rep, SPL)   # 'held' 칸은 관문이 읽지 않아요
    assert row(rep, SPC)[3] == "PASS" and row(rep, SPC)[1] == "그대로 (어제 11건 → 오늘 11건 · 새 0건)", row(rep, SPC)
    assert all(r[0] not in (SPL, SPC) for r in rep.rows if r[3] == "FAIL")
    # 다음 실행: 미국 기준일이 10-31 에 닿아 MSFT 가 새 줄로 들어와요 (오늘 목록의 종목 · 정수 배율 → 경고 없음)
    nxt_prev = {**prev, "data": dict(prev["data"], **split_fields_of(cur))}
    nxt = {**cur, "data": json.loads(json.dumps(cur["data"]))}
    f2 = split_fields_of(nxt)
    f2["splits"] = sorted(f2["splits"] + [["MSFT", "2026-10-31", 2.0]])
    nxt["data"].update(F.hold_late_splits(f2, nxt_prev["data"], D(2026, 10, 31)), usPxDate="2026-10-31")
    assert nxt["data"]["splitsInfo"]["held"] == [] and ["MSFT", "2026-10-31", 2.0] in nxt["data"]["splits"]
    rep2 = check(nxt, nxt_prev, final)
    assert row(rep2, SPL)[3] == "PASS", row(rep2, SPL)
    assert row(rep2, SPC)[3] == "PASS" and row(rep2, SPC)[1] == "그대로 (어제 11건 → 오늘 12건 · 새 1건)", row(rep2, SPC)


# ── 7. 기본값 · 빈 칸 · NaN 없는 JSON · main 배선 ─────────────────────────────────────────────────
def test_defaults_keep_the_old_behaviour():
    f = {"splits": [["SNDK", "2026-11-20", 8.0]], "splitsInfo": {"gap": []}}
    assert F.hold_late_splits(f, None) is f and F.hold_late_splits(f, None, None) is f      # us_date 없음 = 예전 그대로
    assert F.hold_late_splits({}, None, D(2026, 11, 19)) == {}                                # 칸을 쓰지 않는 날은 그대로
    g = F.hold_late_splits(f, None, D(2026, 11, 19))
    assert f == {"splits": [["SNDK", "2026-11-20", 8.0]], "splitsInfo": {"gap": []}}          # 받은 dict 는 바꾸지 않아요
    assert g["splitsInfo"] == {"gap": [], "held": [["SNDK", "2026-11-20", 8.0]], "lateKept": []}


def test_published_split_fields_are_strict_json(tmp_path, monkeypatch):
    Log(monkeypatch)
    f, _ = run(None, D(2026, 11, 20), D(2026, 11, 19), {"NVDA": {"2024-06-10": 10.0}, "SNDK": {"2026-11-20": 8.0}, "AAPL": {}}, monkeypatch)
    text = json.dumps(f, allow_nan=False)
    path = str(tmp_path / "data.json")
    F.write_json(path, f)

    def no_const(c):
        raise ValueError(f"NaN/Infinity in JSON: {c}")
    back = json.loads(open(path, encoding="utf-8").read(), parse_constant=no_const)
    assert back == json.loads(text) and back["splitsInfo"]["held"] == [["SNDK", "2026-11-20", 8.0]]
    assert all(isinstance(x[2], float) and math.isfinite(x[2]) for x in back["splits"] + back["splitsInfo"]["held"])
    assert [p for p, v in V.text_values(back) if V.BAD_WORD.search(v)] == []
    assert [p for p, v in V.text_values(F.UNITS["splits"]) if V.BAD_WORD.search(v)] == []
    assert "held" in F.UNITS["splits"] and "lateKept" in F.UNITS["splits"]


def test_main_holds_late_splits_with_the_run_us_date_before_publishing():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    body = src.split("\ndef main():", 1)[1]
    a = body.index('sp_fields = splits_fields(prev, [s["t"] for s in us], umeta.get("splits"), umeta.get("splitsNoCol") or [], start, today)')
    b = body.index('sp_fields = hold_late_splits(sp_fields, prev, dt.date.fromisoformat(umeta["usPxDate"]))')
    assert a < b < body.index("payload.update(sp_fields)") < body.index("write_json(OUT, payload)")
    assert body.count("hold_late_splits(") == 1
    # 데이터의 usPxDate 와 같은 값이에요 (payload 의 usPxDate 칸)
    assert '"usPxDate": umeta["usPxDate"]' in body


@pytest.mark.parametrize("us_date, held", [(D(2026, 11, 18), 2), (D(2026, 11, 19), 1), (D(2026, 11, 20), 0)])
def test_only_dates_after_the_us_date_are_held(us_date, held):
    f = {"splits": [["A", "2026-11-19", 2.0], ["B", "2026-11-20", 3.0], ["C", "2020-01-02", 4.0]], "splitsInfo": {}}
    g = F.hold_late_splits(f, None, us_date)
    assert len(g["splitsInfo"]["held"]) == held and len(g["splits"]) == 3 - held
    assert all(x[1] <= us_date.isoformat() for x in g["splits"]) and all(x[1] > us_date.isoformat() for x in g["splitsInfo"]["held"])
