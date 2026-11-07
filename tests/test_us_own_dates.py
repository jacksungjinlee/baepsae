# -*- coding: utf-8 -*-
"""v19.1c 앱 (Jack, 2026-11-07: "Stale US prices under today's date are disaster #1") — Node 로 직접 돌려봐요.

data.json 의 새 칸 (파이프라인 PR, claude/us-stale-dates):
- 미국 종목 pxd: 그 종목의 마지막 종가 날짜 (미국 기준일 usPxDate 보다 앞설 때만 · 그때 d1 은 없어요)
- 맨 위 nextPub · staleAfter: staleAfter 가 지나면 '늦음' 경고 (없거나 못 읽으면 예전 4일 규칙)

여기서 보는 것:
- data.js ownCloseDate · ownCloseGroups (날짜마다 한 묶음 · 새 날짜 먼저 · 화면 순서 · 한 번만 · 오늘 데이터에 없는 종목 빼고) ·
  stockPriceDate · ownCloseReport, 그리고 2.0 이 같은 규칙을 쓰는지 (stocklist.js ownCloses)
- d1 은 pxd 가 있는 종목에서 절대 읽지 않아요 (engine.todayD1: 오늘 변화 · 큰 움직임 · 같은 업종 점 띠)
- 매일 점검(rules.js evaluateHolding)이 pxd 를 실어 보내요 · 회사 페이지 날짜(cofmt.priceDate · closeLine)가 그 종목의 날짜
- 예전 뱁새 mergeStocks 가 pxd 를 지켜요 (두 갈래 모두)
- 늦음 규칙: staleAfter 전 · 뒤 · 없음(4일 규칙) · 못 읽음(4일 규칙) · 4일 규칙은 staleAfter 가 있어도 그대로 (늦게 뜨는 일 없음) ·
  n ≤ 1 이면 '갱신이 늦어지고 있어요', 2 부터 '{n}일째 갱신이 멈췄어요' · 공시 탭의 n(가장 최근 공시일부터) = 1 도 같은 규칙
- 열어 둔 화면: 데이터를 다시 받지 않고 늦음만 다시 봐요 (load.js refreshFresh · nextFreshCheck, data.js nextFreshChange)
- 문구: 승인된 그대로 (Jack, 2026-11-07 디자인 채팅) · 홈 띠의 n ≤ 1 문구(today.staleLate)도 Jack 의 문장 그대로 (A3)
- n 은 예정일(nextPub) 아침부터 한국 달력으로 세요 (staleAfter 가 지났을 때) · 그 밖에는 예전처럼 발행 뒤 날 수
- pxd · staleAfter 가 없는 파일은 지금과 똑같이 동작해요
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

from copytrace import chat_approved, copy_strings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
_B = {}
MODS = {"D": "src/data.js", "L": "src/v2/stocklist.js", "E": "src/v2/engine.js", "R": "src/v2/rules.js", "T": "src/v2/track.js",
        "CF": "src/v2/cofmt.js", "F": "src/v2/format.js", "LD": "src/v2/load.js", "C": "src/copy/v2.js", "CO": "src/v2/company.js"}


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
    code = ("import * as M from './own.mjs';\nconst { D, L, E, R, T, CF, F, LD, CO } = M; const CP = M.C.C;\n"
            "const WARN = []; console.warn = (m) => WARN.push(String(m));\n" + decl + "let out;\n" + body
            + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


US_DATE = "2026-11-05"


def us(t, **kw):
    s = {"t": t, "nk": t + " Inc.", "ne": t + " Inc.", "cls": "us", "ccy": "USD", "price": 100.0, "d1": 0.5, "etf": False,
         "ind": "software", "indName": "소프트웨어", "beta": 1.0, "vol": 30.0}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def kr(t, **kw):
    s = {"t": t, "nk": "K" + t, "cls": "kr", "price": 10000.0, "d1": 0.5, "etf": False, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return s


# ── 묶기: data.js ownCloseGroups (2.0 은 stocklist.js 로 같은 것을 써요) ──
def test_own_close_groups_by_date_newest_first_in_screen_order_once_each():
    rows = [us("MSFT"), us("NVDA", pxd="2026-11-03", d1=None), kr("005930"), us("AAPL", pxd="2026-11-04", d1=None), None,
            us("TSLA", pxd="2026-11-04", d1=None), us("AAPL", pxd="2026-11-04", d1=None), us("META", pxd=US_DATE),
            us("BAD1", pxd="11/04/2026"), us("BAD2", pxd=20261104), {"t": "", "pxd": "2026-11-01"}]
    got = run("out = { d: D.ownCloseGroups(ROWS, U), l: L.ownCloseGroups(ROWS, U), none: D.ownCloseGroups([], U), nul: D.ownCloseGroups(null, U),"
              " load: L.ownCloses({ status: 'ok', data: { usPxDate: U } }, ROWS), loading: L.ownCloses({ status: 'loading' }, ROWS) };",
              ROWS=rows, U=US_DATE)
    want = [{"date": "2026-11-04", "ts": ["AAPL", "TSLA"]}, {"date": "2026-11-03", "ts": ["NVDA"]}]
    assert got["d"] == want, got["d"]            # 새 날짜 먼저 · 묶음 안은 화면 순서 · AAPL 한 번 · 기준일과 같은 pxd · 못 읽는 pxd · null 은 빠져요
    assert got["l"] == want and got["load"] == want, got           # 2.0 은 같은 규칙 (그 데이터의 usPxDate 로)
    assert got["none"] == [] and got["nul"] == [] and got["loading"] == []


def test_stock_price_date_and_the_load_report():
    rows = [us("AAPL", pxd="2026-11-04", d1=None), us("MSFT"), us("META", pxd=US_DATE), us("BAD", pxd="2026-13"), kr("005930")]
    got = run("out = { dates: ROWS.map((s) => D.stockPriceDate(s, U)), own: ROWS.map((s) => D.ownCloseDate(s, U)), rep: D.ownCloseReport(ROWS, U),"
              " badMarket: D.stockPriceDate(ROWS[1], 'soon'), noMarket: D.stockPriceDate(ROWS[0], null) };", ROWS=rows, U=US_DATE)
    assert got["dates"] == ["2026-11-04", US_DATE, US_DATE, None, US_DATE], got["dates"]   # 못 읽는 pxd: 날짜 없음 (틀린 날짜보다 나아요)
    assert got["own"] == ["2026-11-04", None, None, None, None], got["own"]
    assert got["rep"] == {"own": [["AAPL", "2026-11-04"]], "same": ["META"], "bad": ["BAD"]}, got["rep"]
    assert got["badMarket"] is None and got["noMarket"] == "2026-11-04"


# ── 문장: format.js ownCloseText (승인 문구 그대로) ──
def test_own_close_text_is_one_sentence_per_date_newest_first():
    got = run("out = { two: F.ownCloseText([{ date: '2026-11-05', ts: ['AAPL', 'TSLA'] }, { date: '2026-11-04', ts: ['NVDA'] }]),"
              " one: F.ownCloseText([{ date: '2026-11-04', ts: ['AAPL'] }]), none: F.ownCloseText([]), nul: F.ownCloseText(null),"
              " badDate: F.ownCloseText([{ date: 'x', ts: ['AAPL'] }]), key: CP.app.ownClose };")
    assert got["key"] == "{names} 가격은 {md} 종가예요."
    assert got["two"] == "AAPL, TSLA 가격은 11월 5일 종가예요. NVDA 가격은 11월 4일 종가예요.", got["two"]   # Jack 의 예 그대로
    assert got["one"] == "AAPL 가격은 11월 4일 종가예요."
    assert got["none"] is None and got["nul"] is None and got["badDate"] is None      # 날짜를 쓸 수 없으면 문장도 없어요


# ── d1: pxd 가 있는 종목의 d1 은 읽지 않아요 ──
def test_today_d1_is_never_read_for_a_stock_at_an_earlier_close():
    got = run("out = [E.todayD1(A), E.todayD1(B), E.todayD1(C), E.todayD1(null), E.todayD1(K), E.todayD1({ t: 'X', d1: NaN })];",
              A=us("AAPL", pxd="2026-11-04", d1=-7.5), B=us("MSFT", d1=-7.5), C=us("BAD", pxd="??", d1=2.0), K=kr("005930", d1=1.25))
    assert got == [None, -7.5, None, None, 1.25, None], got          # pxd 가 있으면 (읽을 수 없어도) 오늘 변화 없음


def test_daily_check_carries_pxd_and_never_a_big_move_from_another_day():
    stocks = [us("AAPL", pxd="2026-11-04", d1=-9.0), us("MSFT", d1=-9.0), us("BAD", pxd="?", d1=-9.0)]
    got = run("""
const ctx = { state: { ok: true }, byT: new Map(S.map((s) => [s.t, s])), coByT: new Map(), fx: 1300, pxDate: U, usPxDate: U };
const deck = { id: 'd', name: 'deck', createdAt: '2026-10-01',
  holdings: S.map((s) => ({ t: s.t, nk: s.nk, cls: 'us', kind: 'core', target: 1 / 3, rules: [] })),
  purchases: S.map((s) => ({ t: s.t, date: '2026-10-01', qty: 1, price: 100, ccy: 'USD', fx: 1300 })) };
const ev = R.evaluateDeck(deck, ctx);
out = { h: ev.holdings.map((x) => [x.t, x.d1, x.pxd, x.bigMove]), big: ev.bigMoves, day: T.deckDayChange(ev),
  groups: L.ownCloseGroups(ev.holdings, null) };""", S=stocks, U=US_DATE)
    assert got["h"] == [["AAPL", None, "2026-11-04", False], ["MSFT", -9.0, None, True], ["BAD", None, None, False]], got["h"]
    assert got["big"] == ["MSFT"] and got["day"] is None, got
    assert got["groups"] == [{"date": "2026-11-04", "ts": ["AAPL"]}], got["groups"]     # 점검 결과로도 같은 안내를 만들어요 (추가로 넣을 돈)


def test_peer_group_leaves_out_stocks_at_an_earlier_close():
    peers = [us(f"P{i}", d1=-2.0) for i in range(5)] + [us("OLD", pxd="2026-11-04", d1=-20.0)]
    got = run("out = { mine: T.peerGroup(S[0], S), old: T.peerGroup(S[5], S) };", S=peers)
    assert got["old"] == {"ok": False, "n": 0}, got["old"]                        # 그 종목 자체: 오늘 변화가 없어요
    assert got["mine"]["ok"] and got["mine"]["n"] == 5 and "OLD" not in [x["id"] for x in got["mine"]["items"]], got["mine"]
    assert abs(got["mine"]["avg"] + 2.0) < 1e-9


# ── 회사 페이지 날짜 (새 문구 없음: co.usClose 에 그 종목의 날짜) ──
def test_company_page_dates_use_the_stocks_own_close():
    got = run("""
const load = { data: { pxDate: '2026-11-06', usPxDate: U } };
out = { own: [CF.priceDate(load, A), CF.priceMd(load, A), CF.closeLine(load, A)],
  us: [CF.priceDate(load, B), CF.closeLine(load, B)], kr: [CF.priceDate(load, K), CF.closeLine(load, K)],
  bad: [CF.priceDate(load, X), CF.closeLine(load, X)], fund: CF.priceDate(load, F379) };""",
              A=us("AAPL", pxd="2026-11-04", d1=None), B=us("MSFT"), K=kr("005930"), X=us("BAD", pxd="soon"),
              F379={"t": "379800", "nk": "KODEX 미국S&P500", "cls": "us", "fund": True, "etf": True, "price": 23140.0}, U=US_DATE)
    assert got["own"] == ["2026-11-04", "11월 4일", "미국 11월 4일 종가"], got["own"]
    assert got["us"] == [US_DATE, "미국 11월 5일 종가"] and got["kr"] == ["2026-11-06", "11월 6일 종가"], got
    assert got["bad"] == [None, None], got["bad"]                                  # 못 읽는 pxd: 날짜를 빼요 (틀린 날짜 대신)
    assert got["fund"] == US_DATE                                                  # pxd 없는 379800 은 지금 그대로


# ── 예전 뱁새: mergeStocks 가 pxd 를 지켜요 ──
def test_old_app_merge_keeps_pxd_on_both_branches():
    base = [{"t": "AAPL", "nk": "애플", "ne": "Apple", "s": "elec", "cls": "us", "price": 200, "beta": 1.1, "vol": 28},
            {"t": "MSFT", "nk": "마이크로소프트", "ne": "Microsoft", "s": "platform", "cls": "us", "price": 400, "beta": 1.0, "vol": 25}]
    live = [{"t": "AAPL", "cls": "us", "price": 344.17, "beta": 1.04, "vol": 29.2, "pxd": "2026-11-04"},
            {"t": "MSFT", "cls": "us", "price": 535.93, "beta": 1.0, "vol": 26.0},
            {"t": "HUBB", "nk": "HUBB", "cls": "us", "price": 438.26, "beta": 1.2, "vol": 31.0, "pxd": "2026-11-04"},
            {"t": "NEWCO", "nk": "NEWCO", "cls": "us", "price": 10.0, "beta": 1.0, "vol": 40.0}]
    got = run("out = D.mergeStocks(B, LV).map((s) => [s.t, s.pxd === undefined ? 'absent' : s.pxd, s.live]);", B=base, LV=live)
    assert sorted(got) == sorted([["AAPL", "2026-11-04", True], ["MSFT", "absent", True], ["HUBB", "2026-11-04", True], ["NEWCO", "absent", True]]), got


# ── 늦음 규칙 (data.js freshness) ──
# 화요일(11월 10일) 17:00. 토요일(11월 7일) 06:40 발행 → 다음 발행 예정 화요일(nextPub), 늦음 경고 화요일 16:47 (staleAfter).
NOW = "2026-11-10T17:00:00+09:00"


def fresh_cases():
    return run("""
const now = Date.parse(N);
const f = (pub, sa, np, at = now) => D.freshness('2026-11-06', pub, 'ko', at, sa, np);
out = {
  before: f('2026-11-10T06:40:00+09:00', '2026-11-11T16:47:00+09:00', '2026-11-11'),
  after: f('2026-11-09T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10'),
  afterDay0: f('2026-11-10T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10'),
  weekendTue1647: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10', Date.parse('2026-11-10T16:46:00+09:00')),
  weekendTue1648: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10', Date.parse('2026-11-10T16:48:00+09:00')),
  weekendTue2359: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10', Date.parse('2026-11-10T23:59:00+09:00')),
  weekendWed: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10', Date.parse('2026-11-11T00:01:00+09:00')),
  weekendThu: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10', Date.parse('2026-11-12T09:00:00+09:00')),
  utcDevice: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '2026-11-10', Date.parse('2026-11-10T15:30:00Z')),
  lateNoNextPub: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', undefined),
  lateBadNextPub: f('2026-11-07T06:40:00+09:00', '2026-11-10T16:47:00+09:00', '11/10'),
  quietWeekend: f('2026-11-07T06:40:00+09:00', '2026-11-10T18:47:00+09:00', '2026-11-10'),
  missing: f('2026-11-07T06:40:00+09:00', undefined),
  missing5: f('2026-11-05T06:40:00+09:00', null),
  nextPubOnly: f('2026-11-05T06:40:00+09:00', null, '2026-11-06'),
  dateOnly: f('2026-11-09T06:40:00+09:00', '2026-11-09'),
  bogus: f('2026-11-09T06:40:00+09:00', 'tomorrow'),
  number: f('2026-11-09T06:40:00+09:00', 1762761600000),
  farAhead: f('2026-11-05T06:40:00+09:00', '2027-01-01T16:47:00+09:00', '2027-01-01'),
  noPub: f(null, '2026-11-10T16:47:00+09:00', '2026-11-10'),
  old4: D.freshness('2026-11-06', '2026-11-07T06:40:00+09:00', 'ko', now),
  times: ['2026-11-10T16:47:00+09:00', '2026-11-10T07:47:00Z', '2026-11-10T16:47+09:00', '2026-11-10', '2026-11-10 16:47:00+09:00', null, 5].map(D.staleAfterTime),
  words: [null, 0, 1, 2, 6].map(D.staleWordsLate),
  kst: [D.kstDate(Date.parse('2026-11-10T14:59:59Z')), D.kstDate(Date.parse('2026-11-10T15:00:00Z')), D.kstDaysBetween('2026-11-10', '2026-12-01')],
};""", N=NOW)


def test_stale_after_rule_before_and_after():
    got = fresh_cases()
    assert got["before"] == {"md": "11월 6일", "days": 0, "stale": False}, got["before"]          # 예정 시각 전: 모양은 그대로 {md, days, stale}
    assert got["after"] == {"md": "11월 6일", "days": 1, "stale": True, "due": True}, got["after"]   # 예정일 당일 16:47 이 지났어요: n = 1
    assert got["afterDay0"] == {"md": "11월 6일", "days": 1, "stale": True, "due": True}, got["afterDay0"]
    assert got["quietWeekend"]["stale"] is False                                                  # 주말·휴장일: 예정 시각 전이라 조용해요


def test_n_counts_from_the_morning_the_publish_was_due():
    """Jack (2026-11-07): 토요일 발행을 화요일에 놓치면 화요일 16:48 에 n = 1 ('갱신이 늦어지고 있어요'), 수요일 2, 목요일 3.
    한국 달력으로 세요 (기기 시간대와 상관없이). nextPub 이 없거나 못 읽으면 예전처럼 발행 뒤 지난 날 수."""
    got = fresh_cases()
    assert got["weekendTue1647"] == {"md": "11월 6일", "days": 3, "stale": False}, got["weekendTue1647"]   # 아직 16:47 전: 조용
    assert got["weekendTue1648"] == {"md": "11월 6일", "days": 1, "stale": True, "due": True}, got["weekendTue1648"]   # '3일째' 가 아니에요
    assert got["weekendTue2359"]["days"] == 1 and got["weekendWed"]["days"] == 2 and got["weekendThu"]["days"] == 3, got
    assert got["utcDevice"]["days"] == 2, got["utcDevice"]                       # 15:30Z = 수요일 00:30 KST (기기가 UTC 여도)
    for k in ("lateNoNextPub", "lateBadNextPub"):
        assert got[k] == {"md": "11월 6일", "days": 3, "stale": True}, (k, got[k])   # 예정일을 모르면 발행 뒤 날 수 (due 없음)
    assert got["kst"] == ["2026-11-10", "2026-11-11", 21], got["kst"]


def test_missing_or_unreadable_stale_after_keeps_the_four_day_rule():
    got = fresh_cases()
    assert got["missing"] == {"md": "11월 6일", "days": 3, "stale": False}, got["missing"]       # 예전 규칙: 4일까지는 조용해요
    assert got["missing5"] == {"md": "11월 6일", "days": 5, "stale": True}, got["missing5"]
    assert got["nextPubOnly"] == got["missing5"]                                                  # staleAfter 없이 nextPub 만으로는 아무것도 안 바뀌어요
    assert got["old4"] == got["missing"]                                                          # 다섯째 · 여섯째 인자 없이 부른 것과 같아요
    for k in ("dateOnly", "bogus", "number"):
        assert got[k] == {"md": "11월 6일", "days": 1, "stale": False}, (k, got[k])               # 못 읽는 값은 4일 규칙
    at = int(dt.datetime(2026, 11, 10, 7, 47, tzinfo=dt.timezone.utc).timestamp() * 1000)       # 16:47 KST
    assert got["times"][:3] == [at, at, at] and got["times"][3:] == [None, None, None, None], got["times"]   # 시각 + 시간대가 있어야 해요


def test_four_day_rule_stays_as_a_backstop():
    got = fresh_cases()
    # 먼 날로 잘못 적힌 staleAfter 도 막지 못해요. 4일 규칙만 걸렸으니 n 은 발행 뒤 날 수 그대로 (Jack, 2026-11-07)
    assert got["farAhead"] == {"md": "11월 6일", "days": 5, "stale": True}, got["farAhead"]
    assert got["noPub"] == {"md": "11월 6일", "days": 1, "stale": True, "due": True}, got["noPub"]   # 발행 시각 없음: 예정일부터


def test_stale_words_n_up_to_one_then_days():
    got = fresh_cases()
    assert got["words"] == [True, True, True, False, False], got["words"]
    w = run("out = { app: [null, 0, 1, 2, 6].map(F.staleText), home: [null, 1, 2, 6].map(F.todayStaleText), key: CP.today.staleLate };")
    assert w["app"] == ["갱신이 늦어지고 있어요"] * 3 + ["2일째 갱신이 멈췄어요", "6일째 갱신이 멈췄어요"], w["app"]
    assert w["home"] == ["데이터 갱신이 늦어지고 있어 오늘은 점검하지 않았어요."] * 2 + [
        "데이터가 2일째 갱신되지 않아 오늘은 점검하지 않았어요", "데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요"], w["home"]
    assert w["key"] == "데이터 갱신이 늦어지고 있어 오늘은 점검하지 않았어요.", w["key"]


def test_home_band_n_follows_the_due_day_not_the_older_corp_file():
    """dayState (rules.js): 토요일 발행 · 화요일 16:48 → 홈 띠의 n = 1 (corp.json 이 토요일 것이라도 '3일째' 가 아니에요).
    예정일이 없는 파일(예전 모양)은 예전대로 data · corp 중 큰 날 수."""
    sat = "2026-11-07T06:40:00+09:00"
    f_new = _files(publishedAt=sat, nextPub="2026-11-10", staleAfter="2026-11-10T16:47:00+09:00")
    f_new["corp"]["publishedAt"] = sat
    f_old = _files(publishedAt="2026-11-06T06:40:00+09:00")
    f_old["corp"]["publishedAt"] = "2026-11-05T06:40:00+09:00"
    got = run("""
const L2 = (f, now) => LD.resolveLoad({ data: { ok: true, data: f.data }, corp: { ok: true, data: f.corp }, macro: { ok: false, error: 'x' } }, Date.parse(now));
const at = (x) => Date.parse(x);
const tue = L2(NEW, '2026-11-10T16:48:00+09:00'), wed = L2(NEW, '2026-11-11T09:00:00+09:00'), old = L2(OLD, '2026-11-10T09:00:00+09:00');
out = { tue: [tue.fresh, R.dayState(tue, at('2026-11-10T16:48:00+09:00'))], wed: R.dayState(wed, at('2026-11-11T09:00:00+09:00')),
  old: [old.fresh, R.dayState(old, at('2026-11-10T09:00:00+09:00'))], band: F.todayStaleText(R.dayState(tue, at('2026-11-10T16:48:00+09:00')).days) };""",
              NEW=f_new, OLD=f_old)
    assert got["tue"][0]["days"] == 1 and got["tue"][1] == {"ok": False, "why": "stale", "days": 1}, got["tue"]
    assert got["band"] == "데이터 갱신이 늦어지고 있어 오늘은 점검하지 않았어요.", got["band"]
    assert got["wed"] == {"ok": False, "why": "stale", "days": 2}, got["wed"]
    assert got["old"][0] == {"md": "11월 9일", "days": 4, "stale": False} and got["old"][1] == {"ok": False, "why": "stale", "days": 5}, got["old"]


# ── 불러오기 (load.js resolveLoad): staleAfter 로 판단하고, 크게 남겨요 ──
def _files(**over):
    data = {"asOf": "2026-11-10", "pxDate": "2026-11-09", "usPxDate": "2026-11-09", "fxDate": "2026-11-09", "fx": 1350.0,
            "publishedAt": "2026-11-10T06:40:00+09:00",
            "stocks": [kr("005930"), us("AAPL", pxd="2026-11-06", d1=None), us("MSFT"), us("BAD", pxd="2026/11/06", d1=None)]}
    data.update(over)
    return {"data": data, "corp": {"pxDate": "2026-11-09", "publishedAt": "2026-11-10T06:40:00+09:00", "companies": []}}


def test_resolve_load_uses_stale_after_and_logs_dates():
    f_new = _files(nextPub="2026-11-11", staleAfter="2026-11-11T16:47:00+09:00")
    f_old = _files()
    f_old["data"]["stocks"] = [kr("005930"), us("MSFT")]
    got = run("""
const L2 = (f, now) => LD.resolveLoad({ data: { ok: true, data: f.data }, corp: { ok: true, data: f.corp }, macro: { ok: false, error: 'x' } }, Date.parse(now));
const a = L2(NEW, '2026-11-11T16:00:00+09:00'); const wa = WARN.splice(0);
const b = L2(NEW, '2026-11-11T17:00:00+09:00'); WARN.splice(0);
const c = L2(OLD, '2026-11-11T17:00:00+09:00'); const wc = WARN.splice(0);
const p = LD.resolveLoad({ data: { ok: true, data: NEW.data }, corp: { ok: true, data: NEW.corp }, macro: { ok: false, error: 'x' } }, Date.parse('2026-11-20T00:00:00+09:00'), { preview: true }); const wp = WARN.splice(0);
out = { a: a.fresh, b: b.fresh, c: c.fresh, p: p.fresh, wa, wc, wp, day: R.dayState(b, Date.parse('2026-11-11T17:00:00+09:00')) };""",
              NEW=f_new, OLD=f_old)
    assert got["a"]["stale"] is False and got["b"] == {"md": "11월 9일", "days": 1, "stale": True, "due": True}, got
    assert got["day"] == {"ok": False, "why": "stale", "days": 1}, got["day"]            # 홈은 판정 없이 멈춤 띠 (n = 1)
    assert got["c"]["stale"] is False                                                   # staleAfter 없는 파일: 4일 규칙 (하루 뒤는 조용)
    assert got["p"] == {"md": None, "days": 0, "stale": False} and not [w for w in got["wp"] if "pxd" in w or "staleAfter" in w], got
    wa = " | ".join(got["wa"])
    assert "1 of 3 US stocks at an earlier close than 2026-11-09" in wa and "AAPL 2026-11-06" in wa, wa
    assert "1 US stocks with a pxd that cannot be read" in wa and "BAD" in wa, wa
    assert "staleAfter" not in wa, wa                                                  # 읽을 수 있는 staleAfter 는 조용해요
    wc = " | ".join(got["wc"])
    assert "staleAfter is missing or null" in wc and "4 days" in wc and "earlier close" not in wc, wc   # 예전 규칙으로 돌아갈 때는 크게


def test_files_without_pxd_or_stale_after_follow_the_four_day_rule():
    """오늘의 실제 파일 모양(pxd · staleAfter 없음): 늦음 판단은 예전 4일 규칙 그대로 (발행 뒤 지난 날 수 = 내림, 4일을 넘으면 멈춤),
    날짜 · d1 · 안내도 이 PR 전과 같아요. 기대값은 파이썬에서 4일 규칙으로 따로 계산해요."""
    pub = dt.datetime(2026, 11, 10, 6, 40, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    f = _files(publishedAt=pub.isoformat())
    f["data"]["stocks"] = [kr("005930", d1=-6.0), us("MSFT", d1=-7.0)]
    f["corp"]["publishedAt"] = pub.isoformat()
    offsets = [dt.timedelta(0), dt.timedelta(hours=23, minutes=59), dt.timedelta(days=1), dt.timedelta(days=2, hours=3),
               dt.timedelta(days=4, hours=23, minutes=59), dt.timedelta(days=5), dt.timedelta(days=6, hours=1)]
    nows = [int((pub + o).timestamp() * 1000) for o in offsets]
    got = run("""
const out1 = NOWS.map((now) => {
  const load = LD.resolveLoad({ data: { ok: true, data: F0.data }, corp: { ok: true, data: F0.corp }, macro: { ok: false, error: 'x' } }, now);
  return { fresh: load.fresh, day: R.dayState(load, now) };
});
const now = NOWS[3];
const load = LD.resolveLoad({ data: { ok: true, data: F0.data }, corp: { ok: true, data: F0.corp }, macro: { ok: false, error: 'x' } }, now);
const [k, m] = F0.data.stocks;
out = { all: out1, d1: [E.todayD1(k), E.todayD1(m)], dates: [CF.priceDate(load, k), CF.priceDate(load, m)], groups: L.ownCloses(load, F0.data.stocks) };""",
              F0=f, NOWS=nows)
    for o, g in zip(offsets, got["all"]):
        days = int(o.total_seconds() // 86400)
        stale = days > 4                                                         # STALE_DAYS = 4 (src/data.js), 바꾸지 않았어요
        assert g["fresh"] == {"md": "11월 9일", "days": days, "stale": stale}, (o, g)
        assert g["day"] == ({"ok": False, "why": "stale", "days": days} if stale else {"ok": True}), (o, g["day"])
    assert got["d1"] == [-6.0, -7.0] and got["dates"] == ["2026-11-09", "2026-11-09"] and got["groups"] == [], got


# ── 열어 둔 화면의 늦음 다시 보기 (load.js refreshFresh · nextFreshCheck, data.js nextFreshChange) ──
def test_refresh_fresh_turns_stale_after_stale_after_without_new_data():
    f = _files(nextPub="2026-11-11", staleAfter="2026-11-11T16:47:00+09:00", publishedAt="2026-11-10T06:40:00+09:00")
    f["corp"]["publishedAt"] = "2026-11-10T06:40:00+09:00"
    got = run("""
const at = (x) => Date.parse(x);
const load = LD.resolveLoad({ data: { ok: true, data: F0.data }, corp: { ok: true, data: F0.corp }, macro: { ok: false, error: 'x' } }, at('2026-11-11T09:00:00+09:00'));
const same = LD.refreshFresh(load, at('2026-11-11T16:00:00+09:00'));
const late = LD.refreshFresh(load, at('2026-11-11T16:48:00+09:00'));
const again = LD.refreshFresh(late, at('2026-11-11T18:00:00+09:00'));
const day2 = LD.refreshFresh(late, at('2026-11-12T06:41:00+09:00'));
const ctxA = R.todayCtx(load, at('2026-11-11T16:00:00+09:00')), ctxB = R.todayCtx(late, at('2026-11-11T16:48:00+09:00'));
const prev = LD.resolveLoad({ data: { ok: true, data: F0.data }, corp: { ok: true, data: F0.corp }, macro: { ok: false, error: 'x' } }, at('2026-11-11T09:00:00+09:00'), { preview: true });
out = { first: load.fresh, sameIsSame: same === load, late: late.fresh, lateData: late.data === load.data && late.byT === load.byT,
  againIsSame: again === late, day2: day2.fresh, stateA: ctxA.state, stateB: ctxB.state,
  prevSame: LD.refreshFresh(prev, at('2026-11-20T00:00:00+09:00')) === prev, failSame: LD.refreshFresh({ status: 'fail' }, 0).status,
  waits: [LD.nextFreshCheck(load, at('2026-11-11T09:00:00+09:00')), LD.nextFreshCheck(load, at('2026-11-11T16:30:00+09:00')),
          LD.nextFreshCheck(load, at('2026-11-11T16:47:30+09:00')), LD.nextFreshCheck(late, at('2026-11-12T06:30:00+09:00')),
          LD.nextFreshCheck(prev, 0), LD.nextFreshCheck({ status: 'loading' }, 0)],
  raw: [D.nextFreshChange(at('2026-11-11T16:30:00+09:00'), [], '2026-11-11T16:47:00+09:00'), D.nextFreshChange(0, [null, 'x'], 'bogus'),
        D.nextFreshChange(at('2026-11-11T16:30:00+09:00'), ['2026-11-10T06:40:00+09:00'], null)] };""", F0=f)
    assert got["first"] == {"md": "11월 9일", "days": 1, "stale": False}, got["first"]
    assert got["sameIsSame"] is True and got["againIsSame"] is True                 # 바뀐 게 없으면 같은 객체 (다시 그리지 않아요)
    assert got["late"] == {"md": "11월 9일", "days": 1, "stale": True, "due": True} and got["lateData"], got   # 데이터는 그대로, 경고만
    assert got["day2"] == {"md": "11월 9일", "days": 2, "stale": True, "due": True}, got["day2"]   # 다음 날(한국 달력)이면 n = 2
    assert got["stateA"] == {"ok": True} and got["stateB"] == {"ok": False, "why": "stale", "days": 1}, got   # 홈 판정도 멈춤으로
    assert got["prevSame"] is True and got["failSame"] == "fail"                    # 미리 보기 · 실패는 건드리지 않아요
    H, M = 3600000, 60000
    assert got["waits"][0] == H and got["waits"][1] == 17 * M + 1000, got["waits"]  # 길어도 1시간 · staleAfter 1초 뒤
    assert got["waits"][2] == H and got["waits"][3] == 10 * M + 1000, got["waits"]      # 지난 뒤엔 1시간마다 · 발행 뒤 날 수가 느는 때(06:40) 1초 뒤
    assert got["waits"][4] is None and got["waits"][5] is None, got["waits"]
    assert got["raw"] == [17 * M + 1000, None, H], got["raw"]


# ── 공시 탭: n 은 가장 최근 공시일부터 (최소 1) ──
def test_disclosure_tab_n_is_days_since_the_newest_filing_and_reads_late_at_one():
    got = run("""
const N = Date.parse('2026-11-11T09:00:00+09:00');
const one = CO.discDate({ asOf: '2026-11-11', newest: '2026-11-10', listOk: false, publishedAt: '2026-11-11T07:30:00+09:00' }, N);
const three = CO.discDate({ asOf: '2026-11-11', newest: '2026-11-08', listOk: false, publishedAt: '2026-11-11T07:30:00+09:00' }, N);
out = { one, three, w1: F.staleText(one.days), w3: F.staleText(three.days) };""")
    assert got["one"]["stale"] is True and got["one"]["days"] == 1, got["one"]
    assert got["w1"] == "갱신이 늦어지고 있어요", got["w1"]                       # 공시 목록을 못 받은 날, 가장 최근 공시가 어제
    assert got["three"]["days"] == 3 and got["w3"] == "3일째 갱신이 멈췄어요", got


# ── 문구 ──
def test_new_words_are_the_approved_ones():
    c, _ = copy_strings()
    assert c["app"]["ownClose"] == "{names} 가격은 {md} 종가예요."              # Jack, 2026-11-07 (디자인 채팅, A1–A3)
    assert c["app"]["staleLate"] == "갱신이 늦어지고 있어요"
    assert c["app"]["stale"] == "{n}일째 갱신이 멈췄어요" and c["today"]["stale"] == "데이터가 {n}일째 갱신되지 않아 오늘은 점검하지 않았어요"
    assert c["co"]["usClose"] == "미국 {md} 종가"
    detail = open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()
    assert 'const T_OWN_CLOSE = { ko: "{names} 가격은 {md} 종가예요.", en: "{names}: priced at the {md} close." };' in detail
    assert 'const T_STALE_LATE = { ko: "갱신이 늦어지고 있어요", en: "update is running late" };' in detail
    assert '"updates stopped " + f.days + " days ago" : f.days + "일째 갱신이 멈췄어요"' in detail     # 이틀째부터는 예전 그대로


def test_today_stale_late_has_jacks_wording():
    """홈의 멈춤 띠(today.stale)의 n ≤ 1 문구 (today.staleLate): Jack 의 문장 그대로 (2026-11-07, 디자인 채팅 A3). 자리표시로 시작했던
    키라서, 다시 자리표시나 빈 값이 되거나 승인 기록과 달라지면 실패해요. 이 검사를 지우거나 건너뛰지 마세요."""
    c, _ = copy_strings()
    v = c["today"]["staleLate"]
    assert isinstance(v, str) and v.strip(), "today.staleLate 는 빈 값이면 안 돼요 (띠 제목이 비어요)"
    assert not re.search(r"PLACEHOLDER|TODO|자리표시", v, flags=re.I), f"today.staleLate 가 아직 자리표시예요: {v!r} — Jack 의 문구가 필요해요"
    assert re.search("[가-힣]", v), v
    assert chat_approved().get("today.staleLate") == v, "today.staleLate 의 승인 기록(docs/tasks/v18.3-approved-in-chat.md)이 없어요"
    assert v == "데이터 갱신이 늦어지고 있어 오늘은 점검하지 않았어요.", v              # Jack, 2026-11-07 (design chat, stale US prices A3)
