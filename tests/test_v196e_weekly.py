# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6e 이번 주 정리 (src/v2/weekly.js 의 숫자 · weekly.jsx 의 weeklyView · weekcfg.js 스위치) — Node 에서 돌려봐요.

docs/tasks/v19.6-records-alerts-dark.md Part E · Part I.2 (adds only; every expected value worked by hand in the comments):
- 언제: publishedAt 이 그 주(pxDate 가 든 월 ~ 일) 토요일(한국 날짜) 이후 · 금요일 휴장이면 목요일이 마지막 날 · 다음 월요일에도 그대로 ·
  다음 한국 종가가 나오면 없음 · 그 주 첫 한국 거래일 (월요일 휴장이면 화요일) · wkFrom 이 없거나 이상한 파일은 카드 없음
- 내 포트폴리오: 이득 = 지금 가치 − 그 주 시작 가치 − 이번 주 산 돈 + 이번 주 판 돈 · % = 이득 ÷ (시작 가치 + 산 돈) · 손으로 푼 예 (산 것 ·
  판 것 · 미국 종목 하나) · 미국은 usWkFrom 의 fxHist 환율 (그날 또는 그 앞 마지막 날) · c1w 없는 종목은 양쪽에서 빠지고 이름이 남아요 ·
  nv 행은 스위치마다 (out · use · note)
- 코스피: idxHist 의 wkFrom 종가 → pxDate 종가 · 받은 배당 · 공시 (v19.6b 카드 그대로, 이번 주 것만) · 다음 주 일정
- 가장 많이 움직인 종목: 같은 업종 규칙 (GROUP_MIN · TOGETHER_SHARE) 을 그 주의 움직임에: 빠진 한 주 · 오른 한 주 ([Q12], 따로 시험)
- 닫기: 그 주 그 포트폴리오만, 이 기기에만 (다른 주는 다시 보여요 · 저장이 막혀도 오류 없음)
- 승인되지 않은 말이 필요한 칸은 빠지고 console 이 말해요 · WEEKLY_ON 은 꺼져 있어요 (빠진 종목 줄이 승인되면 켜요)
(what the screens show is checked in tests/smoke_v2.py scene_v196e · scene_v196e_states)
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
_B = {}


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-weekly-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("W", "weekly.js"), ("WV", "weekly.jsx"), ("Tr", "track.js"), ("Lk", "look.js"), ("Cfg", "weekcfg.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { W, WV, Tr, Lk, Cfg, C } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# The test week: Monday 2026-11-16 to Sunday 11-22, the Korean close of Friday 11-20 published on Saturday 11-21 (KST). Last week's
# close is Friday 11-13 in both markets. Today's rate 1,450; fxHist has 11-13 at 1,400. Every company and number is made up.
FAKE = """
const mem = new Map(); const warns = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = (m) => warns.push(String(m)); console.info = () => {};
const T = '2026-11-20', PUB = '2026-11-21T06:45:00+09:00', NOW = Date.parse('2026-11-21T09:00:00+09:00');
const kr = (t, more = {}) => ({ t, nk: '종목' + t, cls: 'kr', ccy: 'KRW', price: 100000, ind: 'semi', ...more });
const us = (t, more = {}) => ({ t, nk: t + ' Inc.', cls: 'us', ccy: 'USD', price: 200, ind: 'elec', ...more });
const dataOf = (stocks, more = {}) => ({ pxDate: T, usPxDate: T, publishedAt: PUB, wkFrom: '2026-11-13', usWkFrom: '2026-11-13', fx: 1450, stocks, ...more });
const MACRO = { idxHist: { KOSPI: { asOf: T, rows: [['2026-11-12', 3990], ['2026-11-13', 4000], ['2026-11-16', 4010], ['2026-11-20', 4080]] } },
  fxHist: { asOf: T, final: true, rows: [['2026-11-12', 1395], ['2026-11-13', 1400], ['2026-11-16', 1420], ['2026-11-20', 1450]] } };
const loadOf = (stocks, more = {}, macro = MACRO) => ({ status: 'ok', data: dataOf(stocks, more), macro, byT: new Map(stocks.map((s) => [s.t, s])),
  coByT: new Map(), fresh: { stale: false, days: 0 } });
const ctxOf = (load) => ({ byT: load.byT, fx: load.data.fx });
const imp = (t, qty, more = {}) => ({ t, nk: '종목' + t, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty, ...more });
const deckOf = (rows, more = {}) => ({ id: 'd1', name: '내 포트폴리오', createdAt: '2026-11-01', kind: 'imported', settings: { points: {}, strict: 'normal' },
  holdings: rows.filter((r) => r.t).map((r) => ({ t: r.t, nk: r.nk, cls: r.ccy === 'USD' ? 'us' : 'kr' })), purchases: [], imported: rows, ...more });
const model = (deck, load, more = {}) => W.weeklyModel({ deck, load, ctx: ctxOf(load), now: NOW, ...more });
const money = (deck, load, more = {}) => model(deck, load, more).money;
const r3 = (x) => (x == null ? null : Math.round(x * 1000) / 1000);
// the hand-worked portfolio (acceptance 5): a buy and a sale this week, one US holding, one stock without last week's close
const WORKED = () => {
  const stocks = [kr('005930', { c1w: 100000, price: 110000 }), kr('005380', { c1w: 200000, price: 190000, ind: 'auto' }), us('AAPL', { c1w: 200, price: 210 }),
    kr('000660', { price: 50000 })];
  const deck = deckOf([imp('005930', 10), imp('005380', 20), imp('AAPL', 4), imp('000660', 2)], {
    purchases: [{ t: '005930', qty: 5, price: 105000, ccy: 'KRW', date: '2026-11-18' }],
    sales: [{ t: '005380', qty: 5, price: 210000, ccy: 'KRW', date: '2026-11-19' }] });
  return { stocks, deck, load: loadOf(stocks) };
};
"""


# ── when the card shows ─────────────────────────────────────────────────────────
def test_the_week_is_final_from_saturdays_publish_and_stays_until_the_next_korean_close():
    got = run("""
      const st = (d) => { const s = W.weekState(d); return s.ok ? [s.mon, s.sun, s.first, s.to] : s.why; };
      out = {
        saturday: st(dataOf([])),
        friday: st(dataOf([], { publishedAt: '2026-11-20T20:00:00+09:00' })),
        // the device's zone never matters: 11-20 15:30 UTC is Saturday 00:30 in Korea, 14:59 UTC is still Friday
        satUtc: st(dataOf([], { publishedAt: '2026-11-20T15:30:00Z' })), friUtc: st(dataOf([], { publishedAt: '2026-11-20T14:59:00Z' })),
        sunday: st(dataOf([], { publishedAt: '2026-11-22T07:00:00+09:00' })),
        // Monday after: the same file (nothing new published yet) still shows the week; the next Korean close (Monday's, published
        // Tuesday) is a new week whose Saturday has not come
        nextClose: st(dataOf([], { pxDate: '2026-11-23', usPxDate: '2026-11-23', publishedAt: '2026-11-24T06:45:00+09:00', wkFrom: '2026-11-20', usWkFrom: '2026-11-20' })),
        // a Friday holiday (12-25): Thursday's close is the week's last; published on Saturday it is final, on the holiday itself not yet
        friHoliday: st(dataOf([], { pxDate: '2026-12-24', usPxDate: '2026-12-24', publishedAt: '2026-12-26T06:45:00+09:00', wkFrom: '2026-12-18', usWkFrom: '2026-12-18' })),
        friHolidayEarly: st(dataOf([], { pxDate: '2026-12-24', publishedAt: '2026-12-25T06:45:00+09:00', wkFrom: '2026-12-18' })),
        // Monday 10-05 and Friday 10-09 closed: the week runs Tuesday to Thursday
        both: st(dataOf([], { pxDate: '2026-10-08', usPxDate: '2026-10-08', publishedAt: '2026-10-10T07:00:00+09:00', wkFrom: '2026-10-02', usWkFrom: '2026-10-02' })),
        noWk: st(dataOf([], { wkFrom: undefined })), blankWk: st(dataOf([], { wkFrom: '' })), wkInWeek: st(dataOf([], { wkFrom: '2026-11-16' })),
        wkTooOld: st(dataOf([], { wkFrom: '2026-11-07' })), noPub: st(dataOf([], { publishedAt: 'x' })), noPx: st(dataOf([], { pxDate: null })),
      };""")
    assert got["saturday"] == ["2026-11-16", "2026-11-22", "2026-11-16", "2026-11-20"]
    assert got["friday"] == "notFinal" and got["friUtc"] == "notFinal" and got["satUtc"] == got["saturday"] == got["sunday"]
    assert got["nextClose"] == "notFinal"
    assert got["friHoliday"] == ["2026-12-21", "2026-12-27", "2026-12-21", "2026-12-24"] and got["friHolidayEarly"] == "notFinal"
    assert got["both"] == ["2026-10-05", "2026-10-11", "2026-10-06", "2026-10-08"]
    assert got["noWk"] == got["blankWk"] == got["wkInWeek"] == got["wkTooOld"] == "wkFrom"
    assert got["noPub"] == "publishedAt" and got["noPx"] == "pxDate"


def test_the_model_needs_loaded_data():
    got = run("""out = [W.weeklyModel({ deck: deckOf([]), load: { status: 'fail' } }).why, W.weeklyModel({ deck: deckOf([]), load: { status: 'loading' } }).why,
      W.weeklyModel({ deck: null, load: loadOf([]) }).why];""")
    assert got == ["load", "load", "load"]


# ── 내 포트폴리오 ───────────────────────────────────────────────────────────────
def test_the_hand_worked_week_with_a_buy_a_sale_and_a_us_holding():
    got = run("""const { deck, load } = WORKED(); const m = model(deck, load);
      out = { m: { ...m.money, pct: r3(m.money.pct) }, kospi: r3(m.kospi.pct), shown: (() => { C.weekly.leftOut = '{n}|{names}'; const v = WV.weeklyView(m);
        return { tiles: v.tiles.map((t) => [t.id, t.big, t.sub]), notes: v.notes.map((n) => n.text) }; })() };""")
    m = got["m"]
    # 삼성 005930: 10주 × 100,000 = 1,000,000 → 5주 105,000 에 삼 (525,000) → 15주 × 110,000 = 1,650,000 · 이득 125,000
    # 현대차 005380: 20주 × 200,000 = 4,000,000 → 5주 210,000 에 팖 (1,050,000) → 15주 × 190,000 = 2,850,000 · 이득 −100,000
    # AAPL: 4주 × $200 × 1,400 (usWkFrom 11-13 의 fxHist) = 1,120,000 → 4주 × $210 × 1,450 (오늘 환율) = 1,218,000 · 이득 98,000
    # 000660: c1w 없음 → 양쪽에서 빠지고 이름이 남아요 (50,000 × 2 = 100,000 은 어디에도 없어요)
    assert m["per"] == [
        {"t": "005930", "start": 1000000, "end": 1650000, "buys": 525000, "sells": 0, "gain": 125000, "nv": False},
        {"t": "005380", "start": 4000000, "end": 2850000, "buys": 0, "sells": 1050000, "gain": -100000, "nv": False},
        {"t": "AAPL", "start": 1120000, "end": 1218000, "buys": 0, "sells": 0, "gain": 98000, "nv": False}], m["per"]
    # 이득 = 5,718,000 − 6,120,000 − 525,000 + 1,050,000 = 123,000 · % = 123,000 ÷ (6,120,000 + 525,000) = 1.851%
    assert (m["start"], m["buys"], m["sells"], m["end"], m["gain"], m["pct"], m["n"]) == (6120000, 525000, 1050000, 5718000, 123000, 1.851, 3)
    assert m["left"] == [{"t": "000660", "nk": "종목000660", "why": "none"}] and m["ok"] is True
    assert got["kospi"] == 2.0                                          # 4,000 → 4,080
    assert got["shown"]["tiles"] == [["pf", "+1.9%", "+12만원 · 코스피 +2.0%"]]
    assert got["shown"]["notes"] == ["1|종목000660"]


def test_records_of_the_week_are_monday_to_sunday_and_later_ones_count_nowhere():
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 })];
      const d = (date, more = {}) => deckOf([imp('005930', 10)], { purchases: [{ t: '005930', qty: 1, price: 100000, ccy: 'KRW', date }], ...more });
      const g = (deck) => { const x = money(deck, loadOf(stocks)); return [x.start, x.buys, x.end, x.gain]; };
      out = { sunBefore: g(d('2026-11-15')), mon: g(d('2026-11-16')), sun: g(d('2026-11-22')), monAfter: g(d('2026-11-23')) };""")
    # Sunday 11-15 counts as held at the start (11 × 100,000); Monday and Sunday of the week are buys; Monday after (a record on the
    # day the card still shows) is neither: the week's end holds 10 shares
    assert got["sunBefore"] == [1100000, 0, 1210000, 110000]
    assert got["mon"] == got["sun"] == [1000000, 100000, 1210000, 110000]
    assert got["monAfter"] == [1000000, 0, 1100000, 100000]


def test_a_us_holding_takes_the_fxhist_rate_of_the_us_week_start():
    got = run("""
      const st = [us('AAPL', { c1w: 200, price: 210 })];
      const deck = deckOf([imp('AAPL', 4)]);
      const f = (more = {}, macro = MACRO) => { const x = money(deck, loadOf(st, more, macro)); return x.ok ? [x.start, x.end, x.gain] : x.left; };
      const noRow = { ...MACRO, fxHist: { ...MACRO.fxHist, rows: MACRO.fxHist.rows.filter((r) => r[0] !== '2026-11-13') } };
      out = {
        same: f(),
        usOwnStart: f({ usWkFrom: '2026-11-12' }),                     // the US week began a day earlier: that day's rate (1,395)
        lastBefore: f({}, noRow),                                       // no row on 11-13: the last one before it (11-12, 1,395)
        noFxHist: f({}, { idxHist: MACRO.idxHist }),
        otherWeek: f({ usPxDate: '2026-11-13', usWkFrom: '2026-11-06' }),   // US prices from another week: never this week's move
        noUsWk: f({ usWkFrom: '' }),
        // bought this week (nothing held at the start): no last-week close or start rate is needed; the buy at its own rate
        bought: (() => { const d = deckOf([], { kind: undefined, holdings: [{ t: 'AAPL', nk: 'AAPL' }], imported: [],
          purchases: [{ t: 'AAPL', qty: 2, price: 205, ccy: 'USD', fx: 1430, date: '2026-11-18' }] });
          const x = money(d, loadOf([us('AAPL', { price: 210 })])); return [x.start, x.buys, x.end, r3(x.gain)]; })(),
      };""")
    assert got["same"] == [1120000, 1218000, 98000]                     # 4 × 200 × 1,400 → 4 × 210 × 1,450
    assert got["usOwnStart"] == got["lastBefore"] == [1116000, 1218000, 102000]   # 4 × 200 × 1,395
    assert got["noFxHist"] == [{"t": "AAPL", "nk": "AAPL Inc.", "why": "fx"}]
    assert got["otherWeek"] == [{"t": "AAPL", "nk": "AAPL Inc.", "why": "week"}]
    assert got["noUsWk"] == [{"t": "AAPL", "nk": "AAPL Inc.", "why": "week"}]
    assert got["bought"] == [0, 586300, 609000, 22700]                 # 2 × 205 × 1,430 → 2 × 210 × 1,450


def test_a_stock_without_a_usable_last_week_close_is_left_out_of_both_ends_and_named():
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 }), kr('000660', { price: 50000 }), kr('035420', { c1w: 1, price: 2, pxd: '2026-11-18' }),
        kr('051910', { c1w: 0, price: 300000 })];
      const base = [imp('005930', 10)];
      const g = (rows, more = {}, st = stocks) => { const x = money(deckOf([...base, ...rows], more), loadOf(st)); return { ok: x.ok, start: x.start, end: x.end, left: x.left }; };
      out = {
        none: g([imp('000660', 2)]),                                     // blank c1w
        own: g([imp('035420', 1)]),                                      // priced at its own date (pxd): neither end is the week's
        zero: g([imp('051910', 1)]),                                     // a c1w of 0 is no c1w
        absent: g([imp('009999', 1)]),                                   // not in today's data at all
        // bought this week only: needs no last-week close, so it counts
        boughtOnly: g([], { holdings: [{ t: '000660', nk: '종목000660' }], purchases: [{ t: '000660', qty: 2, price: 48000, ccy: 'KRW', date: '2026-11-17' }] }),
        name: g([{ nk: '비상장 회사', ccy: 'KRW', amountWon: 1000000, date: '2026-10-01', unscored: true }]),
        // a portfolio made in the middle of the week: its undated rows' start holding is unknown
        madeLate: (() => { const x = money(deckOf(base, { createdAt: '2026-11-18' }), loadOf(stocks)); return [x.ok, x.left]; })(),
        madeBefore: (() => { const x = money(deckOf(base, { createdAt: '2026-11-15' }), loadOf(stocks)); return [x.ok, x.start]; })(),
        allOut: (() => { const x = money(deckOf([imp('000660', 2)]), loadOf(stocks)); return [x.ok, x.gain, x.pct, x.left.length]; })(),
      };""")
    keep = {"ok": True, "start": 1000000, "end": 1100000}
    assert got["none"] == {**keep, "left": [{"t": "000660", "nk": "종목000660", "why": "none"}]}
    assert got["own"] == {**keep, "left": [{"t": "035420", "nk": "종목035420", "why": "own"}]}
    assert got["zero"] == {**keep, "left": [{"t": "051910", "nk": "종목051910", "why": "none"}]}
    assert got["absent"] == {**keep, "left": [{"t": "009999", "nk": "종목009999", "why": "absent"}]}
    assert got["boughtOnly"] == {"ok": True, "start": 1000000, "end": 1200000, "left": []}      # + 2 × 50,000 now, 96,000 bought
    assert got["name"] == {**keep, "left": [{"t": None, "nk": "비상장 회사", "why": "name"}]}
    assert got["madeLate"] == [False, [{"t": "005930", "nk": "종목005930", "why": "made"}]] and got["madeBefore"] == [True, 1000000]
    assert got["allOut"] == [False, None, None, 1]


def test_amount_rows_history_entries_and_records_without_a_rate():
    got = run("""
      const st = [kr('005930', { c1w: 100000, price: 110000 }), us('AAPL', { c1w: 200, price: 210 })];
      const L = loadOf(st);
      out = {
        // 금액으로 넣기 dated in the week: its amount is the buy (2,000,000 at Tuesday's close → 20주), the week's end at today's close
        amount: (() => { const x = money(deckOf([{ t: '005930', nk: 'a', ccy: 'KRW', amountWon: 2000000, close: 100000, date: '2026-11-17' }]), L); return [x.start, x.buys, x.end]; })(),
        qtyDated: money(deckOf([imp('005930', 3, { date: '2026-11-17' })]), L).left,
        // sold out and taken out this week (history entry): the sale counts, nothing at the end
        soldOut: (() => { const x = money(deckOf([], { holdings: [], imported: [], history: [{ t: '005930', nk: '삼성', out: '2026-11-19', imported: imp('005930', 10),
          sales: [{ t: '005930', qty: 10, price: 105000, ccy: 'KRW', date: '2026-11-19' }] }] }), L); return [x.start, x.sells, x.end, x.gain]; })(),
        // taken out this week without a sale: what the shares fetched is unknown
        outNoSale: money(deckOf([], { holdings: [], imported: [], history: [{ t: '005930', nk: '삼성', out: '2026-11-19', imported: imp('005930', 10) }] }), L).left,
        // taken out before the week: not part of it
        outBefore: (() => { const x = money(deckOf([imp('AAPL', 1)], { history: [{ t: '005930', nk: '삼성', out: '2026-11-10', imported: imp('005930', 10) }] }), L); return [x.n, x.left]; })(),
        // taken out after the week (on the Monday the card still shows): it was held all week
        outAfter: (() => { const x = money(deckOf([], { holdings: [], imported: [], history: [{ t: '005930', nk: '삼성', out: '2026-11-23', imported: imp('005930', 10) }] }), L); return [x.start, x.end]; })(),
        saleNoRate: money(deckOf([imp('AAPL', 4)], { sales: [{ t: 'AAPL', qty: 1, price: 205, ccy: 'USD', date: '2026-11-18' }] }), L).left,
        buyNoRate: money(deckOf([], { kind: undefined, holdings: [{ t: 'AAPL', nk: 'AAPL' }], imported: [], purchases: [{ t: 'AAPL', qty: 1, price: 205, ccy: 'USD', date: '2026-11-18' }] }), L).left,
        buyPlanFx: money(deckOf([], { kind: undefined, planFx: 1300, holdings: [{ t: 'AAPL', nk: 'AAPL' }], imported: [], purchases: [{ t: 'AAPL', qty: 1, price: 205, ccy: 'USD', date: '2026-11-18' }] }), L).buys,
      };""")
    assert got["amount"] == [0, 2000000, 2200000]
    assert got["qtyDated"] == [{"t": "005930", "nk": "종목005930", "why": "imp"}]
    assert got["soldOut"] == [1000000, 1050000, 0, 50000]
    assert got["outNoSale"] == [{"t": "005930", "nk": "종목005930", "why": "out"}]
    assert got["outBefore"] == [1, []] and got["outAfter"] == [1000000, 1100000]
    assert got["saleNoRate"] == [{"t": "AAPL", "nk": "AAPL Inc.", "why": "fx"}] and got["buyNoRate"] == [{"t": "AAPL", "nk": "AAPL Inc.", "why": "fx"}]
    assert got["buyPlanFx"] == 266500                                  # 205 × 1,300 (the portfolio's planFx, as track.purchaseWon)


def test_naver_confirmed_rows_under_each_switch():
    got = run("""
      const st = [kr('005930', { c1w: 100000, price: 110000 }), kr('000660', { c1w: 50000, price: 45000, c1wv: 'nv' })];
      const deck = deckOf([imp('005930', 10), imp('000660', 10)]);
      const g = (nv) => { const m = model(deck, loadOf(st), { nv }); const x = m.money;
        const v = WV.weeklyView(m); return { start: x.start, gain: x.gain, left: x.left.map((l) => l.why), nvUsed: x.nvUsed, notes: v.notes.map((n) => n.id),
          says: v.say.filter((l) => l.includes('Naver')).length, pct: r3(W.weekPct(st[1], m.week.starts, nv)) }; };
      C.weekly.leftOut = '{n}|{names}';
      const before = C.weekly.nvNote;
      const out1 = { def: Cfg.WEEK_NV, modes: Cfg.NV_MODES, out: g('out'), use: g('use'), note: g('note') };
      C.weekly.nvNote = '{names}';
      out1.noteWorded = (() => { const m = model(deck, loadOf(st), { nv: 'note' }); return WV.weeklyView(m).notes.map((n) => [n.id, n.text]); })();
      C.weekly.nvNote = before;
      out = out1;""")
    assert got["def"] == "out" and got["modes"] == ["out", "use", "note"]
    # out: 000660 leaves both ends (named: 'nv'); the week is 005930's alone, 1,000,000 → 1,100,000
    assert got["out"] == {"start": 1000000, "gain": 100000, "left": ["nv"], "nvUsed": [], "notes": ["left"], "says": 0, "pct": None}
    # use: 000660 counts (500,000 → 450,000), no footnote
    assert got["use"] == {"start": 1500000, "gain": 50000, "left": [], "nvUsed": ["000660"], "notes": [], "says": 0, "pct": -10.0}
    # note: counts, and the footnote waits for Jack's words (nothing shown, said in the console)
    assert got["note"] == {"start": 1500000, "gain": 50000, "left": [], "nvUsed": ["000660"], "notes": [], "says": 1, "pct": -10.0}
    assert got["noteWorded"] == [["nv", "000660"]]


# ── 코스피 · 받은 배당 · 공시 · 다음 주 ──────────────────────────────────────────
def test_kospi_week_needs_both_closes():
    got = run("""
      const k = (rows, starts = { kr: '2026-11-13' }, px = T) => { const x = W.kospiWeek({ idxHist: { KOSPI: { asOf: px, rows } } }, { pxDate: px }, starts); return x.pct != null ? r3(x.pct) : x.why; };
      out = { ok: k([['2026-11-13', 4000], ['2026-11-20', 3900]]), noStart: k([['2026-11-12', 4000], ['2026-11-20', 3900]]),
        noEnd: k([['2026-11-13', 4000], ['2026-11-19', 3900]]), bad: k([['2026-11-13', 0]]), none: W.kospiWeek(null, { pxDate: T }, { kr: '2026-11-13' }).why };""")
    assert got == {"ok": -2.5, "noStart": "start", "noEnd": "end", "bad": "rows", "none": "rows"}


def test_dividends_of_the_week_in_won_with_their_count():
    got = run("""
      const deck = deckOf([imp('005930', 10)], { divs: [
        { t: '005930', amount: 3610, ccy: 'KRW', date: '2026-11-17' }, { t: 'AAPL', amount: 1.04, ccy: 'USD', fx: 1445, date: '2026-11-22' },
        { t: 'AAPL', amount: 2, ccy: 'USD', date: '2026-11-18' }, { t: '005930', amount: 100, ccy: 'KRW', date: '2026-11-15' },
        { t: '005930', amount: 100, ccy: 'KRW', date: '2026-11-23' }],
        history: [{ t: '000660', nk: 'x', out: '2026-11-01', divs: [{ t: '000660', amount: 5000, ccy: 'KRW', date: '2026-11-20' }] }] });
      const m = model(deck, loadOf([kr('005930', { c1w: 100000 })]));
      const v = WV.weeklyView(m);
      out = { d: { ...m.divs, won: r3(m.divs.won) }, tile: v.tiles.filter((t) => t.id === 'div').map((t) => [t.label, t.big, t.sub]), notes: v.notes.map((n) => n.text) };""")
    # 3,610 + 1.04 × 1,445 (1,502.8) + a taken-out stock's 5,000 = 10,112.8 → "1만 113원" · 3건; the USD one without a rate is left out and counted
    assert got["d"] == {"won": 10112.8, "n": 3, "noFx": 1}
    assert got["tile"] == [["받은 배당", "1만 113원", "3건"]]
    assert got["notes"] == ["환율 기록이 없는 미국 배당 1건은 빼고 더했어요."]


DISC = """
const ymd = (iso) => iso.replace(/-/g, '');
const discOf = (d = {}, more = {}) => ({ status: 'ok', data: { asOf: T, newest: T, listOk: true, publishedAt: '2026-11-21T06:45:00+09:00', insider: [], nps: [],
  issue: [], issueOk: true, ...d, ...more } });
const iss = (i, t, kind, date, more = {}) => ({ rc: '2099' + String(i).padStart(10, '0'), d: ymd(date), t, nk: 'x', kind, bd: ymd(date), how: 'holders', n: 100, p: 5, amt: 1e10,
  cor: false, ...(kind === 'rights' ? { cls: 'common' } : {}), ...more });
const ins = (i, t, date, q) => ({ rc: '2098' + String(i).padStart(10, '0'), d: ymd(date), t, nk: 'x', pos: '대표이사', q, r: 0, amt: 1 });
"""


def test_filings_tile_counts_this_weeks_part_b_cards_of_held_stocks():
    got = run(DISC + """
      const st = [kr('005930', { c1w: 100000, price: 100000 }), kr('005380', { c1w: 1, price: 2 }), us('AAPL', { c1w: 200 })];
      const deck = deckOf([imp('005930', 10), imp('AAPL', 1)]);
      const d = discOf({
        issue: [iss(1, '005930', 'rights', '2026-11-17'), iss(2, '005930', 'cb', '2026-11-20', { how: null }), iss(3, '005930', 'rights', '2026-11-13'),
          iss(4, '005380', 'rights', '2026-11-18'), iss(5, '005930', 'rights', '2026-11-19', { wd: true }), iss(6, '005930', 'rights', '2026-11-18', { bonus: true })],
        insider: [ins(1, '005930', '2026-11-18', 1000), ins(2, '005930', '2026-11-19', 999), ins(3, '005930', '2026-11-12', -5000)],
        nps: [{ d: '20261119', t: '005930', nk: 'x', rt: 7.31, chg: -0.12 }] });
      const f = (disc, dk = deck) => W.weeklyModel({ deck: dk, load: loadOf(st), ctx: ctxOf(loadOf(st)), disc, now: NOW }).files;
      const seen = { ...deck };                                    // a 확인했어요 mark never takes a filing out of the week's count
      out = { ok: f(d), seenData: W.weekFilings(d, new Set(['005930']), W.weekState(dataOf(st)), loadOf(st).byT, NOW).n,
        stale: f(discOf({}, { listOk: false })).why, fail: f({ status: 'fail' }).why, wait: f({ status: 'loading' }).why, none: f(null).why,
        issueFail: f(discOf({}, { issueOk: false })).why, noIssue: (() => { const x = discOf(); delete x.data.issue; return f(x).why; })(),
        usOnly: f(d, deckOf([imp('AAPL', 1)])).why,
        view: (() => { const m = W.weeklyModel({ deck, load: loadOf(st), ctx: ctxOf(loadOf(st)), disc: d, now: NOW }); const v = WV.weeklyView(m);
          return [v.tiles.filter((t) => t.id === 'disc').length, v.say.filter((l) => l.includes('cb, nps')).length]; })(),
        viewWorded: (() => { const b = { ...C.weekly.kinds }; C.weekly.kinds.cb = '전환사채 {n}'; C.weekly.kinds.nps = '국민연금 {n}';
          const m = W.weeklyModel({ deck, load: loadOf(st), ctx: ctxOf(loadOf(st)), disc: d, now: NOW }); const v = WV.weeklyView(m);
          Object.assign(C.weekly.kinds, b); return v.tiles.filter((t) => t.id === 'disc').map((t) => [t.label, t.big, t.sub]); })() };""")
    # this week: the 11-17 rights issue and the 11-20 CB (held 005930); not 11-13 (last week), not 005380 (not held), not the withdrawal, not
    # the 유무상증자 (no approved shape, v19.6b leaves it out); the 11-18 report of 1억원 (1,000 × 100,000); not 9,990만원; not last week's;
    # the 국민연금 change of 11-19
    assert got["ok"] == {"ok": True, "n": 4, "kinds": {"rights": 1, "cb": 1, "bw": 0, "ins": 1, "nps": 1},
                         "skipped": [{"t": "005930", "rc": "20990000000006", "why": "bonus: a rights and bonus issue"}]}
    assert got["seenData"] == 4
    assert (got["stale"], got["fail"], got["wait"], got["none"], got["issueFail"], got["noIssue"], got["usOnly"]) == (
        "stale", "disc", "disc", "disc", "issue", "issue", "noKr")
    # cb and nps have no approved tile word yet: the tile is left out that week and the console says which
    assert got["view"] == [0, 1]
    assert got["viewWorded"] == [["공시", "4건", "유상증자 1 · 전환사채 1 · 지분 변동 1 · 국민연금 1"]]


def test_next_week_dates_count_and_first_name():
    got = run("""
      const st = [kr('005930', { c1w: 1 }), us('AAPL', { ed: '2026-11-25', xd: '2026-11-24' }), us('MSFT', { nk: 'Microsoft', ed: '2026-11-27' }),
        us('NVDA', { ed: '2026-11-20' }), us('JNJ', { ed: '2026-11-30' }), us('KO', { ed: '2026-11-23' })];
      const g = (rows, more = {}) => { const m = model(deckOf(rows), loadOf(st)); const v = WV.weeklyView(m);
        return { rows: m.next.map((r) => [r.t, r.kind, r.date]), tile: v.tiles.filter((t) => t.id === 'next').map((t) => [t.label, t.big, t.sub]),
          say: v.say.filter((l) => l.includes('ex-dividend')).length }; };
      const both = g([imp('005930', 1), imp('AAPL', 1), imp('MSFT', 1), imp('NVDA', 1), imp('JNJ', 1)]);
      const usOnly = g([imp('AAPL', 1), imp('MSFT', 1)]);
      const kOnly = g([imp('005930', 1)]);
      const xdOnly = g([imp('KO', 0.5)].map((r) => ({ ...r, qty: 1 })));
      const b = C.weekly.exDiv; C.weekly.exDiv = '배당락일 {n}';
      const worded = g([imp('AAPL', 1), imp('MSFT', 1)]);
      C.weekly.exDiv = b;
      out = { both, usOnly, kOnly, xdOnly, worded };""")
    # next week is 11-23 to 11-29 (US dates): AAPL's ex-date 11-24 and earnings 11-25, MSFT 11-27; NVDA (this week) and JNJ (11-30) are not
    assert got["both"]["rows"] == [["AAPL", "xd", "2026-11-24"], ["AAPL", "earn", "2026-11-25"], ["MSFT", "earn", "2026-11-27"]]
    # 배당락일 waits for its word: earnings only, the first name is the first earnings row's; a Korean stock held → 다음 주 미국 일정
    assert got["both"]["tile"] == [["다음 주 미국 일정", "실적 발표 2", "AAPL Inc."]] and got["both"]["say"] == 1
    assert got["usOnly"]["tile"] == [["다음 주", "실적 발표 2", "AAPL Inc."]]
    assert got["kOnly"]["tile"] == [] and got["kOnly"]["rows"] == []
    assert got["xdOnly"]["tile"] == [["다음 주", "실적 발표 1", "KO Inc."]]            # KO's earnings 11-23 (Monday of next week)
    assert got["worded"]["tile"] == [["다음 주", "실적 발표 2 · 배당락일 1", "AAPL Inc."]] and got["worded"]["say"] == 0


def test_next_week_never_shows_a_date_before_today():
    """When the card still shows into the next week (a long holiday before the next Korean close), the rows start today, as Part B's
    일정 card (the Yahoo cache can be days old)."""
    got = run("""
      const st = [us('AAPL', { ed: '2026-11-24' }), us('MSFT', { ed: '2026-11-27' })];
      const rows = (iso) => model(deckOf([imp('AAPL', 1), imp('MSFT', 1)]), loadOf(st), { now: Date.parse(iso + 'T09:00:00+09:00') }).next.map((r) => r.t);
      out = [rows('2026-11-21'), rows('2026-11-23'), rows('2026-11-25'), rows('2026-11-28'), rows('2026-11-30')];""")
    assert got == [["AAPL", "MSFT"], ["AAPL", "MSFT"], ["MSFT"], [], []]


# ── 가장 많이 움직인 종목 ───────────────────────────────────────────────────────
GROUP = """
// six chip makers (codes ending in 0: common shares), each with last week's close 100 and today's price 100 + move
const grp = (moves, more = {}) => moves.map((m, i) => kr(String(100000 + i * 10), { nk: 'g' + i, c1w: 100, price: 100 + m, d1: 9, ind: 'semi', ...(more[i] || {}) }));
const mv = (stocks, held, nv) => { const L = loadOf(stocks); const m = W.weekMover(new Set(held), L.byT, stocks, W.weekState(L.data).starts, nv);
  return m && [m.t, r3(m.pct), m.why, m.n]; };
"""


def test_the_mover_is_the_held_stock_with_the_largest_weekly_move():
    got = run(GROUP + """
      const st = [...grp([-3, 1, 2, -1, 0.5]), kr('005380', { c1w: 200, price: 260, ind: 'auto' }), kr('000660', { c1w: 50, price: 40, pxd: '2026-11-18' })];
      out = { up: mv(st, ['100000', '005380']), own: mv(st, ['000660', '100010']), none: mv(st, ['999990']), flat: mv([kr('100000', { c1w: 100, price: 100.04 })], ['100000']),
        tie: mv([kr('200000', { c1w: 100, price: 105 }), kr('100000', { c1w: 100, price: 95 })], ['200000', '100000']) };""")
    assert got["up"] == ["005380", 30.0, None, 0]                       # +30% beats −3%; 자동차 has no group of 5 here
    assert got["own"] == ["100010", 1.0, None, 5]                       # a stock at its own date has no week's move (3 of 5 rose: no line)
    assert got["none"] is None and got["flat"] is None                  # nothing held with a move · 0.04% rounds to 0.0%
    assert got["tie"] == ["100000", -5.0, None, 0]                      # the same size: the first code


def test_the_same_industry_rule_on_the_week_fell_together():
    got = run(GROUP + """
      out = { five: mv(grp([-6, -1, -2, -3, 4]), ['100000']),            // 4 of 5 fell (80%): together
        three: mv(grp([-6, -1, -2, 3, 4]), ['100000']),                  // 3 of 5: no reason line
        four: mv(grp([-6, -1, -2, -3]), ['100000']),                     // a group of 4 is under GROUP_MIN
        // the week's move, never today's d1 (every d1 here is +9)
        weekNotDay: mv(grp([-6, -1, -2, -3, -4], { 0: { d1: 5 } }), ['100000']),
        // a member confirmed only through Naver: under "out" it is not in the group (4 left), under "use" it is
        nvOut: mv(grp([-6, -1, -2, -3, -4], { 4: { c1wv: 'nv' } }), ['100000'], 'out'), nvUse: mv(grp([-6, -1, -2, -3, -4], { 4: { c1wv: 'nv' } }), ['100000'], 'use'),
        rules: [Tr.GROUP_MIN, Tr.TOGETHER_SHARE], word: C.weekly.fell };""")
    assert got["five"] == ["100000", -6.0, "fell", 5] and got["three"] == ["100000", -6.0, None, 5] and got["four"] == ["100000", -6.0, None, 0]
    assert got["weekNotDay"] == ["100000", -6.0, "fell", 5]
    assert got["nvOut"] == ["100000", -6.0, None, 0] and got["nvUse"] == ["100000", -6.0, "fell", 5]
    assert got["rules"] == [5, 0.8] and got["word"] == "같은 업종이 다 같이 빠진 한 주였어요"


def test_the_same_industry_rule_on_the_week_rose_together():
    """[Q12]: the rise version, the mirror of the fall rule (it rose and at least 80% of its group rose)."""
    got = run(GROUP + """
      const view = (stocks) => { const L = loadOf(stocks); const deck = deckOf([imp('100000', 1)]); const m = model(deck, L); return WV.weeklyView(m).mover; };
      out = { five: mv(grp([7, 1, 2, 3, -4]), ['100000']), three: mv(grp([7, 1, 2, -3, -4]), ['100000']),
        flatCounts: mv(grp([7, 1, 2, 3, 0]), ['100000']),                // a member at 0.0 neither rose nor fell: 4 of 5 rose
        downAmongRisers: mv(grp([-8, 1, 2, 3, 4]), ['100000']),           // it fell while the group rose: no line
        line: (() => { const v = view(grp([7, 1, 2, 3, 4])); return [v.t, v.why, v.line]; })(),
        fellLine: (() => { const v = view(grp([-7, -1, -2, -3, -4])); return [v.why, v.line]; })(),
        noLine: (() => { const v = view(grp([7, -1, -2, 3, 4])); return [v.why, v.line]; })() };""")
    assert got["five"] == ["100000", 7.0, "rose", 5] and got["three"] == ["100000", 7.0, None, 5]
    assert got["flatCounts"] == ["100000", 7.0, "rose", 5] and got["downAmongRisers"] == ["100000", -8.0, None, 5]
    assert got["line"] == ["100000", "rose", "같은 업종이 다 같이 오른 한 주였어요"]
    assert got["fellLine"] == ["fell", "같은 업종이 다 같이 빠진 한 주였어요"] and got["noLine"] == [None, None]


def test_peer_group_still_reads_todays_change_by_default():
    got = run("""
      const st = [0, 1, 2, 3, 4].map((i) => kr(String(100000 + i * 10), { c1w: 100, price: 120, d1: i === 4 ? 1 : -1 }));
      const g = Tr.peerGroup(st[0], st);
      out = [g.ok, g.n, g.fell, g.together, g.togetherUp];""")
    assert got == [True, 5, 4, True, False]


# ── 닫기 · 스위치 · 승인되지 않은 말 ─────────────────────────────────────────────
def test_close_hides_that_portfolios_card_for_that_week_on_this_device():
    got = run("""
      const K = W.WEEK_KEY, mon = '2026-11-16';
      const a = [W.readClosed(K, mon)];
      W.closeWeek(K, mon, 'd1'); a.push(W.readClosed(K, mon)); W.closeWeek(K, mon, 'd2'); W.closeWeek(K, mon, 'd1'); a.push(W.readClosed(K, mon));
      a.push(W.readClosed(K, '2026-11-23'));                              // next week: shows again
      W.closeWeek(K, '2026-11-23', 'd2'); a.push(W.readClosed(K, mon), W.readClosed(K, '2026-11-23'));   // a new week's close replaces the old one
      a.push(W.readClosed(W.PREVIEW_WEEK_KEY, '2026-11-23'));              // the preview page keeps its own
      localStorage.setItem(K, '{not json'); a.push(W.readClosed(K, mon));
      localStorage.setItem(K, JSON.stringify({ w: mon, ids: 'd1' })); a.push(W.readClosed(K, mon));
      const keep = globalThis.localStorage;
      globalThis.localStorage = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
      a.push(W.readClosed(K, mon), W.closeWeek(K, mon, 'd1'));
      globalThis.localStorage = keep;
      out = { a, keys: [K, W.PREVIEW_WEEK_KEY], warned: warns.filter((w) => w.includes('close mark was not saved')).length,
        records: [...mem.keys()].filter((k) => k.startsWith('baepsae2.v1')).length };""")
    a = got["a"]
    assert a[0] == [] and a[1] == ["d1"] and a[2] == ["d1", "d2"] and a[3] == [] and a[4] == [] and a[5] == ["d2"] and a[6] == []
    assert a[7] == [] and a[8] == [] and a[9] == [] and a[10] is False and got["warned"] == 1
    assert got["keys"] == ["baepsae2.weekly.v1", "baepsae2.preview.weekly.v1"] and got["records"] == 0   # never in the records


def test_switches_are_off_until_the_left_out_line_is_approved():
    with open(os.path.join(ROOT, "src", "v2", "weekcfg.js"), encoding="utf-8") as f:
        cfg = f.read()
    assert re.findall(r"^export const WEEKLY_ON = (true|false);$", cfg, flags=re.M) == ["false"]
    assert re.findall(r'^export const WEEK_NV = "(out|use|note)";$', cfg, flags=re.M) == ["out"]
    got = run("out = { leftOut: C.weekly.leftOut, nvNote: C.weekly.nvNote, exDiv: C.weekly.exDiv, kinds: C.weekly.kinds };")
    assert got["leftOut"] is None and got["nvNote"] is None and got["exDiv"] is None
    assert got["kinds"] == {"rights": "유상증자 {n}", "ins": "지분 변동 {n}", "cb": None, "bw": None, "nps": None}
    with open(os.path.join(ROOT, "src", "v2", "home2.jsx"), encoding="utf-8") as f:
        home = f.read()
    assert "{WEEKLY_ON && ev.ok && blocks.length > 0 && <WeeklyCards " in home


def test_without_the_left_out_line_the_gain_tile_is_left_out_and_nothing_but_the_heading_means_no_card():
    got = run("""
      const { deck, load } = WORKED(); const m = model(deck, load);
      const v = WV.weeklyView(m);
      const empty = model(deckOf([imp('000660', 1)]), loadOf([kr('000660')]));
      const ve = WV.weeklyView(empty);
      out = { tiles: v.tiles.map((t) => t.id), notes: v.notes, say: v.say.filter((l) => l.includes('waits for Jack')).length, mover: v.mover && v.mover.t,
        show: v.show, emptyShow: ve.show, emptySay: ve.say.filter((l) => l.includes('no card')).length, off: WV.weeklyView({ ok: false }).show };""")
    assert got["tiles"] == [] and got["notes"] == [] and got["say"] == 1
    assert got["mover"] == "005930" and got["show"] is True                     # +10% (110,000 ÷ 100,000): the mover still shows
    assert got["emptyShow"] is False and got["emptySay"] == 1 and got["off"] is False


def test_weekly_code_has_no_fixed_colour_small_text_or_mascot():
    text = ""
    for f in ("weekly.jsx", "weekly.js", "weekcfg.js"):
        with open(os.path.join(ROOT, "src", "v2", f), encoding="utf-8") as fh:
            text += re.sub(r"//[^\n]*", "", fh.read())
    assert not re.findall(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", text)
    sizes = [float(x) for x in re.findall(r"tx\(\s*([0-9.]+)\s*,", text)]
    assert sizes and min(sizes) >= 12, sizes
    assert "baepi" not in text.lower() and "Mascot" not in text
