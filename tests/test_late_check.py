# -*- coding: utf-8 -*-
"""늦은 데이터의 매일 점검 (Jack, 2026-11-19) — Node 로 직접 돌려봐요.

Jack: "when data is late, still run the portfolio check on the last official close, with its date ("11월 16일 종가로
점검했어요."), for up to 5 trading days. Skip it only after that." 답 (2026-11-19): 오늘은 할 일이 없어요는 숨기지 말고 지난 종가로
점검했을 때 "{date} 종가 기준으로는 할 일이 없어요." · 미국 종가가 늦은 것도 5거래일에 세요.

여기서 보는 것:
- src/v2/tradedays.js 의 휴장일이 data/market_holidays.csv (파이프라인의 표) 와 같아요 · 표의 처음과 끝도
- 거래일 세기가 파이프라인의 next_session 과 같아요 (2026–2027 의 모든 날짜 · 두 시장)
- 주말 · 수능일(2026-11-19, 늦게 열고 늦게 닫지만 거래일) · 12-31 (한국 휴장 · 미국 거래) · 설날 · 표 밖(평일은 모두 거래일) · 못 읽는 날짜
- rules.js checkState: 11-16 종가의 실제 사고를 시각마다 (늦음 전 · 늦음 1일 · 5거래일 마지막 순간 · 6거래일 0시) · 연말 · 설날 2027 ·
  추석 2026 · 추수감사절 (미국이 먼저 끝나는 날) · 발행이 다른 corp.json · 못 읽는 usPxDate · 실패 · 날짜 없음 · 미리 보기
- evaluateAll 이 late 를 실어요 (늦은 점검일 때만) · dayState 는 그대로 (멈춤)
- 열어 둔 화면: refreshFresh 가 6거래일 0시에 새 상태를 주고 nextFreshCheck 가 그 0시에 깨어요
- 문구: today.calmLate 가 Jack 의 승인 그대로
화면(390 px · 밝은 · 어두운 화면)은 tests/smoke_v2.py 장면 '늦은 점검'이 봐요.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

from copytrace import chat_approved

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as FD  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
_B = {}
MODS = {"D": "src/data.js", "R": "src/v2/rules.js", "LD": "src/v2/load.js", "TD": "src/v2/tradedays.js", "F": "src/v2/format.js",
        "C": "src/copy/v2.js"}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/own.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as M from './own.mjs';\nconst { D, R, LD, TD, F } = M; const CP = M.C.C;\n"
            "const WARN = []; console.warn = (m) => WARN.push(String(m)); console.info = () => {};\n"
            "const at = (x) => Date.parse(x);\n" + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def kr(t, **kw):
    s = {"t": t, "nk": "K" + t, "cls": "kr", "price": 10000.0, "d1": 0.5, "etf": False, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return s


def files(px, usd, published, nxt=None, stale=None, corp_published=None):
    """A publish the way the pipeline writes it: nextPub and staleAfter from fetch_data's own table and functions."""
    hol = FD.load_market_holidays()
    if nxt is None:
        nxt = FD.next_publish(dt.date.fromisoformat(px), dt.date.fromisoformat(usd), hol).isoformat()
        stale = FD.stale_after(dt.date.fromisoformat(nxt))
    data = {"asOf": published[:10], "pxDate": px, "usPxDate": usd, "fxDate": px, "fx": 1350.0, "publishedAt": published,
            "nextPub": nxt, "staleAfter": stale, "stocks": [kr("005930")]}
    corp = {"pxDate": px, "publishedAt": corp_published or published, "companies": []}
    return {"data": data, "corp": corp}


LOAD = """const loadOf = (f, when) => LD.resolveLoad({ data: { ok: true, data: f.data }, corp: { ok: true, data: f.corp }, macro: { ok: false, error: 'x' } }, at(when));
const stateAt = (f, when) => R.todayCtx(loadOf(f, when), at(when)).state;
"""


# ── 휴장일 표: 앱의 것 = 파이프라인의 것 ──
def test_app_calendar_is_the_pipeline_table():
    hol = FD.load_market_holidays()
    got = run("out = { kr: [...TD.CLOSED.KR].sort(), us: [...TD.CLOSED.US].sort(), start: TD.CAL_START, end: TD.CAL_END, n: TD.LATE_CHECK_DAYS };")
    assert got["kr"] == sorted(d.isoformat() for d in hol["KR"]), "src/v2/tradedays.js 의 한국 휴장일을 data/market_holidays.csv 와 맞춰 주세요 (RUNBOOK)"
    assert got["us"] == sorted(d.isoformat() for d in hol["US"]), "src/v2/tradedays.js 의 미국 휴장일을 data/market_holidays.csv 와 맞춰 주세요 (RUNBOOK)"
    assert (got["start"], got["end"]) == (hol["start"].isoformat(), hol["end"].isoformat()), got
    assert got["n"] == 5                                                     # Jack: "for up to 5 trading days"


def test_app_counts_trading_days_exactly_like_the_pipeline():
    """Every close date the table covers (2026-01-01 … 2027-12-20), both markets: the day the 6th trading day after it begins
    (the late check stops then) is the pipeline's next_session applied six times."""
    hol = FD.load_market_holidays()
    got = run("""
const iso = (n) => new Date(n * 86400000).toISOString().slice(0, 10);
const rows = [];
for (let p = Date.UTC(2026, 0, 1) / 86400000; p <= Date.UTC(2027, 11, 20) / 86400000; p++) {
  for (const m of ['KR', 'US']) {
    let d = p, k = 0;
    while (k < 6) { d++; k = TD.tradingDaysAfter(iso(p), iso(d), m); }
    rows.push([iso(p), m, iso(d)]);
  }
}
out = rows;""")
    assert len(got) == 2 * 719, len(got)
    bad = []
    for p, m, sixth in got:
        d = dt.date.fromisoformat(p)
        for _ in range(6):
            d = FD.next_session(d, hol[m], hol["end"])
        if d.isoformat() != sixth:
            bad.append((p, m, sixth, d.isoformat()))
    assert not bad, bad[:10]


def test_trading_day_cases():
    got = run("""
const T = (d, m) => TD.isTradingDay(d, m), A = (a, b, m) => TD.tradingDaysAfter(a, b, m);
out = {
  weekend: [T('2026-11-21', 'KR'), T('2026-11-22', 'US'), A('2026-11-20', '2026-11-22', 'KR')],
  suneung: [T('2026-11-19', 'KR'), A('2026-11-18', '2026-11-19', 'KR')],         // 수능일: 10:00~16:30 이지만 거래일
  yearEnd: [T('2026-12-31', 'KR'), T('2026-12-31', 'US'), T('2027-01-01', 'KR'), T('2027-01-01', 'US'), A('2026-12-30', '2027-01-04', 'KR'), A('2026-12-30', '2027-01-04', 'US')],
  seollal: [T('2026-02-16', 'KR'), T('2026-02-17', 'KR'), T('2026-02-18', 'KR'), T('2027-02-08', 'KR'), T('2027-02-09', 'KR'), T('2027-02-08', 'US'), A('2027-02-05', '2027-02-12', 'KR')],
  chuseok: [A('2026-09-23', '2026-10-02', 'KR'), A('2026-09-23', '2026-10-02', 'US')],
  thanks: [T('2026-11-26', 'US'), T('2026-11-26', 'KR')],
  past: [T('2028-01-03', 'KR'), T('2028-01-01', 'KR'), A('2027-12-30', '2028-01-07', 'KR')],   // 표 밖: 평일은 모두 거래일 (더 엄하게)
  bad: [A('2026-02-30', '2026-03-05', 'KR'), A('2026-11-16', 'x', 'KR'), A(null, '2026-11-20', 'US'), A('2026-11-16', '2026-11-20', 'JP'), A('2026/11/16', '2026-11-20', 'KR')],
  none: [A('2026-11-16', '2026-11-16', 'KR'), A('2026-11-16', '2026-11-10', 'KR')],
  days: [TD.isDay('2026-02-28'), TD.isDay('2026-02-29'), TD.isDay('2026-13-01'), TD.isDay(20261116)],
  late: [TD.lateDays({ pxDate: '2026-11-25', usPxDate: '2026-11-24' }, '2026-11-27'), TD.lateDays({ pxDate: '2026-11-16' }, '2026-11-20'),
         TD.lateDays({ pxDate: '2026-11-16', usPxDate: '2026-11-16' }, 'today')],
};""")
    assert got["weekend"] == [False, False, 0]
    assert got["suneung"] == [True, 1]
    assert got["yearEnd"] == [False, True, False, False, 1, 2], got["yearEnd"]       # 한국 12-31 휴장 · 미국은 열려요
    assert got["seollal"] == [False, False, False, False, False, True, 3], got["seollal"]
    assert got["chuseok"] == [5, 7], got["chuseok"]                                  # 추석에도 미국은 거래해요
    assert got["thanks"] == [False, True]
    assert got["past"] == [True, False, 5], got["past"]
    assert got["bad"] == [None] * 5, got["bad"]
    assert got["none"] == [0, 0]
    assert got["days"] == [True, False, False, False]
    # 추수감사절(11-26) 뒤 금요일: 한국 11-26 · 11-27 = 2, 미국 11-25 · 11-27 = 2 · usPxDate 가 없으면 셀 수 없어요 (점검하지 않아요)
    assert got["late"] == [{"n": 2, "kr": 2, "us": 2}, None, None], got["late"]


# ── 점검이 도는지: rules.js checkState (todayCtx) ──
def test_the_11_16_close_is_checked_until_the_6th_trading_day_begins():
    """The real case: 11-16 (Mon) closes, published 11-17 06:40, nothing after. staleAfter 11-18 16:47. Trading days after
    11-16: 11-17, 11-18, 11-19 (수능), 11-20, 11-23 → checked until 11-24 00:00 KST, skipped from then."""
    f = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    assert (f["data"]["nextPub"], f["data"]["staleAfter"]) == ("2026-11-18", "2026-11-18T16:47:00+09:00")
    got = run(LOAD + """
const W = ['2026-11-18T16:46:00+09:00', '2026-11-18T16:48:00+09:00', '2026-11-19T09:00:00+09:00', '2026-11-21T12:00:00+09:00',
           '2026-11-23T23:59:59+09:00', '2026-11-24T00:00:01+09:00', '2026-11-30T09:00:00+09:00'];
out = { st: W.map((w) => stateAt(F0, w)), day: W.map((w) => R.dayState(loadOf(F0, w), at(w))),
        band: F.todayStaleText(stateAt(F0, '2026-11-24T00:00:01+09:00').days) };""", F0=f)
    st, day = got["st"], got["day"]
    assert st[0] == {"ok": True} and day[0] == {"ok": True}                          # 늦음 전: 평소대로
    assert st[1] == {"ok": True, "late": {"days": 1, "n": 2}}, st[1]                 # 11-18 16:48: 늦음 1일 · 2거래일 뒤 → 점검
    assert st[2] == {"ok": True, "late": {"days": 2, "n": 3}}, st[2]                 # 수능일 아침: 3거래일 (수능일도 세요)
    assert st[3] == {"ok": True, "late": {"days": 4, "n": 4}}, st[3]                 # 토요일: 4거래일 (주말은 세지 않아요)
    assert st[4] == {"ok": True, "late": {"days": 6, "n": 5}}, st[4]                 # 5거래일의 마지막 순간: 아직 점검
    assert st[5] == {"ok": False, "why": "stale", "days": 7}, st[5]                  # 6번째 거래일 0시: 예전처럼 점검하지 않아요
    assert st[6] == {"ok": False, "why": "stale", "days": 13}, st[6]
    for d in day[1:]:                                                                # dayState 는 그대로 (멈춤 줄 · 띠의 n)
        assert d["ok"] is False and d["why"] == "stale", d
    assert [d["days"] for d in day[1:5]] == [s["late"]["days"] for s in st[1:5]]     # 늦은 점검의 days = 날짜 줄의 n
    assert got["band"] == "데이터가 7일째 갱신되지 않아 오늘은 점검하지 않았어요"


@pytest.mark.parametrize("px,usd,last,stop,why", [
    ("2026-12-30", "2026-12-30", "2027-01-07T23:59:59+09:00", "2027-01-08T00:00:01+09:00", "연말: 한국 12-31 · 1-1 휴장, 미국 12-31 거래 → 미국이 먼저 6"),
    ("2027-02-05", "2027-02-05", "2027-02-15T23:59:59+09:00", "2027-02-16T00:00:01+09:00", "설날 2027: 한국 2-8 · 2-9 휴장, 미국 2-15 휴장 → 미국 2-16"),
    ("2026-09-23", "2026-09-23", "2026-09-30T23:59:59+09:00", "2026-10-01T00:00:01+09:00", "추석 2026: 한국 9-24 · 9-25 휴장, 미국은 거래 → 미국 10-1"),
    ("2026-11-25", "2026-11-24", "2026-12-02T23:59:59+09:00", "2026-12-03T00:00:01+09:00", "추수감사절: 미국 11-26 휴장 → 둘 다 12-3"),
    ("2026-02-13", "2026-02-13", "2026-02-23T23:59:59+09:00", "2026-02-24T00:00:01+09:00", "설날 2026: 한국 2-16~18 휴장 · 미국 2-16 휴장 → 미국이 먼저 2-24"),
])
def test_holidays_move_the_stop(px, usd, last, stop, why):
    pub = (dt.date.fromisoformat(px) + dt.timedelta(days=1)).isoformat() + "T06:40:00+09:00"
    f = files(px, usd, pub)
    got = run(LOAD + "out = [stateAt(F0, LAST), stateAt(F0, STOP)];", F0=f, LAST=last, STOP=stop)
    assert got[0]["ok"] is True and got[0]["late"]["n"] == 5, (why, got[0])
    assert got[1]["ok"] is False and got[1]["why"] == "stale", (why, got[1])


def test_only_one_publish_with_readable_dates_is_checked_late():
    """Guards: each falls back to today's answer (no check)."""
    base = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    other_corp = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00", corp_published="2026-11-16T06:40:00+09:00")
    bad_us = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    bad_us["data"]["usPxDate"] = "2026/11/16"
    no_us = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    del no_us["data"]["usPxDate"]
    old = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00", nxt=None)
    old["data"]["nextPub"] = old["data"]["staleAfter"] = None               # 예전 파일: 발행 뒤 4일 규칙
    got = run(LOAD + """
const W = '2026-11-19T09:00:00+09:00', W5 = '2026-11-22T09:00:00+09:00';
const fresh = loadOf(B, W);
out = { base: stateAt(B, W), corp: stateAt(OC, W), badUs: stateAt(BU, W), noUs: stateAt(NU, W),
  old: [stateAt(OLD, W), stateAt(OLD, W5)],
  fail: R.checkState({ status: 'fail' }, at(W)), loading: R.checkState({ status: 'loading' }, at(W)), none: R.checkState(null, at(W)),
  undated: R.checkState({ ...fresh, fresh: { days: null, stale: false } }, at(W)),
  preview: R.checkState({ ...fresh, preview: true }, at('2027-06-01T09:00:00+09:00')) };""",
              B=base, OC=other_corp, BU=bad_us, NU=no_us, OLD=old)
    assert got["base"] == {"ok": True, "late": {"days": 2, "n": 3}}, got["base"]
    assert got["corp"] == {"ok": False, "why": "stale", "days": 2}, got["corp"]          # corp.json 이 다른 발행: 점검하지 않아요
    assert got["badUs"] == {"ok": False, "why": "stale", "days": 2}, got["badUs"]        # 미국 날짜를 읽을 수 없으면 셀 수 없어요
    assert got["noUs"] == {"ok": False, "why": "stale", "days": 2}, got["noUs"]
    # nextPub · staleAfter 가 없는 예전 파일: 4일 규칙으로 멈춘 뒤에도 5거래일 안이면 점검해요 (11-22 일요일: 11-17~20 = 4)
    assert got["old"][0] == {"ok": True} and got["old"][1] == {"ok": True, "late": {"days": 5, "n": 4}}, got["old"]
    assert got["fail"] == {"ok": False, "why": "fail"} and got["loading"] == {"ok": False, "why": "loading"} and got["none"]["why"] == "loading"
    assert got["undated"] == {"ok": False, "why": "undated"}
    assert got["preview"] == {"ok": True}


def test_evaluate_all_runs_on_a_late_close_and_says_so():
    f = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    deck = {"id": "d1", "name": "P", "createdAt": "2026-11-02", "holdings": [{"t": "005930", "nk": "삼성전자", "cls": "kr", "kind": "core",
            "target": 1, "plannedQty": 1, "rules": [{"id": "band", "kind": "band", "check": "checked", "target": 1, "bands": [0.75, 1.25, 1.4]}]}],
            "purchases": [{"t": "005930", "date": "2026-11-02", "qty": 1, "price": 10000, "ccy": "KRW"}]}
    got = run(LOAD + """
const ev = (w) => R.evaluateAll([DECK], R.todayCtx(loadOf(F0, w), at(w)));
const a = ev('2026-11-18T09:00:00+09:00'), b = ev('2026-11-20T09:00:00+09:00'), c = ev('2026-11-24T09:00:00+09:00');
out = { a: [a.ok, 'late' in a, a.decks.length], b: [b.ok, b.late, b.decks.length, b.decks[0].holdings[0].status], c: [c.ok, c.why, c.decks.length] };""",
              F0=f, DECK=deck)
    assert got["a"] == [True, False, 1]                                       # 제때: late 없음
    assert got["b"] == [True, {"days": 3, "n": 4}, 1, "none"], got["b"]       # 늦은 점검: 평소처럼 + late
    assert got["c"] == [False, "stale", 0], got["c"]                          # 6거래일: 예전처럼 아무것도


def test_a_page_left_open_stops_the_late_check_at_midnight():
    f = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    old = files("2026-11-16", "2026-11-16", "2026-11-17T06:40:56+09:00")
    old["data"]["nextPub"] = old["data"]["staleAfter"] = None                # 예전 파일: 날짜 줄의 n 은 발행 시각마다만 바뀌어요
    got = run(LOAD + """
const o = loadOf(OLD, '2026-11-23T20:00:00+09:00');
const oNext = LD.refreshFresh(o, at('2026-11-24T00:00:01+09:00'));
const old = { st: R.todayCtx(o, at('2026-11-23T20:00:00+09:00')).state, sameFresh: oNext.fresh.days === o.fresh.days, moved: oNext !== o,
  after: R.todayCtx(oNext, at('2026-11-24T00:00:01+09:00')).state, wake: LD.nextFreshCheck(o, at('2026-11-23T23:30:00+09:00')) };
const l = loadOf(F0, '2026-11-23T20:00:00+09:00');
const same = LD.refreshFresh(l, at('2026-11-23T23:00:00+09:00'));
const next = LD.refreshFresh(l, at('2026-11-24T00:00:01+09:00'));
const fresh = loadOf(F0, '2026-11-17T09:00:00+09:00');
out = { st: R.todayCtx(l, at('2026-11-23T20:00:00+09:00')).state, same: same === l, moved: next !== l,
  after: R.todayCtx(next, at('2026-11-24T00:00:01+09:00')).state,
  wake: LD.nextFreshCheck(l, at('2026-11-23T23:30:00+09:00')),
  freshSame: LD.refreshFresh(fresh, at('2026-11-17T23:00:00+09:00')) === fresh,
  freshNext: LD.refreshFresh(fresh, at('2026-11-18T00:00:01+09:00')) === fresh, old };""", F0=f, OLD=old)
    assert got["st"] == {"ok": True, "late": {"days": 6, "n": 5}}, got["st"]
    assert got["same"] is True                                               # 같은 날: 같은 상태 (다시 그리지 않아요)
    assert got["moved"] is True and got["after"]["ok"] is False and got["after"]["why"] == "stale", got
    assert got["wake"] == 30 * 60000 + 1000, got["wake"]                     # 그 0시 1초 뒤에 다시 봐요
    assert got["freshSame"] is True and got["freshNext"] is True             # 제때인 데이터는 거래일이 늘어도 그대로
    # 예전 파일(staleAfter 없음): 0시에 날짜 줄의 n 은 그대로여도 거래일이 6이 되면 새 상태로, 그 0시에 깨어서 (1시간 기다리지 않고)
    o = got["old"]
    assert o["st"] == {"ok": True, "late": {"days": 6, "n": 5}}, o
    assert o["sameFresh"] is True and o["moved"] is True and o["after"] == {"ok": False, "why": "stale", "days": 6}, o
    assert o["wake"] == 30 * 60000 + 1000, o["wake"]


def test_the_new_line_is_jacks_wording():
    got = run("out = { late: CP.today.calmLate, fill: F.fill(CP.today.calmLate, { date: F.mdText('2026-11-16') }), eyebrow: CP.today.calmEyebrow, checked: F.fill(CP.pfr.checked, { date: F.mdText('2026-11-16') }) };")
    assert got["late"] == "{date} 종가 기준으로는 할 일이 없어요." == chat_approved()["today.calmLate"]
    assert got["fill"] == "11월 16일 종가 기준으로는 할 일이 없어요."
    assert got["eyebrow"] == "오늘은 할 일이 없어요"                            # 제때인 날은 그대로
    assert got["checked"] == "11월 16일 종가로 점검했어요"
    src = open(os.path.join(ROOT, "src", "v2", "today.jsx"), encoding="utf-8").read()
    assert re.search(r"calmLine\(lateMd\)", src) and "C.today.calmLate" in src
