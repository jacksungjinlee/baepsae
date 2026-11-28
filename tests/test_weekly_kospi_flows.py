# -*- coding: utf-8 -*-
"""뱁새 2.0 이번 주 정리: 내 포트폴리오 칸의 코스피를 같은 돈의 흐름으로 (src/v2/weekly.js kospiWeek · kospiAt) — Node 에서 돌려봐요.

Jack, 2026-11-27 (answer 13): "Yes, same money flows." (Track 2 audit 4.1: 주 중간에 산 · 판 포트폴리오의 % 옆 코스피가 한 주 전체의 움직임이라
같은 질문에 대한 답이 아니었어요.) 이제 코스피도 포트폴리오와 같은 돈으로:
- 그 주 시작 가치가 wkFrom 종가에 들어가고, 이번 주 산 기록의 원화 금액은 그날 코스피 종가에 들어가고, 판 기록의 원화 금액은 그날 종가에 나와요
- 코스피의 이득 = 끝의 가치 − 시작 − 산 돈 + 판 돈 · % = 그 이득 ÷ 포트폴리오와 같은 분모 (시작 가치 + 산 돈) · 배당은 양쪽 모두 빼요
- 그날 코스피 종가가 없는 날(주말 · 휴장 · 미국 날짜)은 그 앞 마지막 종가, 한국 거래일인데 종가가 없으면 '없음' (why): 칸은 지금처럼 코스피 없이
- 산 · 판 기록이 없는 주는 지금 숫자 그대로 (wkFrom 종가 → pxDate 종가) · 칸의 말은 그대로 "코스피 {pct}" (새 문구 없음)
Adds only (tests/test_v196e_weekly.py is unchanged). Every expected value is worked by hand in the comments. Every company and number
is made up.
"""
import json
import os
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
        tmp = tempfile.mkdtemp(prefix="baepsae-weekly-kospi-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("W", "weekly.js"), ("WV", "weekly.jsx"), ("DC", "deckcalc.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = "import { W, WV, DC, C } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# The test week: Monday 2026-11-16 to Sunday 11-22, the Korean close of Friday 11-20 published on Saturday 11-21 (KST); last week's
# close is Friday 11-13 in both markets. 코스피 has a row on every Korean trading day: 11-13 4,000 · 11-16 4,010 · 11-17 4,020 ·
# 11-18 3,980 · 11-19 4,050 · 11-20 4,080 (the plain week: 4,000 → 4,080 = +2.0%). fxHist 11-13 1,400 · 11-20 1,450.
# The October week (OCT): Monday 10-05 and Friday 10-09 are Korean holidays (the US trades on 10-09); 코스피 10-02 3,600 · 10-06 3,650 ·
# 10-07 3,700 · 10-08 3,720; pxDate 10-08, usPxDate 10-09, published Saturday 10-10.
FAKE = """
const warns = [];
console.warn = (m) => warns.push(String(m)); console.info = () => {};
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {}, get length() { return 0; }, key: () => null };
const T = '2026-11-20', PUB = '2026-11-21T06:45:00+09:00', NOW = Date.parse('2026-11-21T09:00:00+09:00');
const kr = (t, more = {}) => ({ t, nk: '종목' + t, cls: 'kr', ccy: 'KRW', price: 100000, ind: 'semi', ...more });
const us = (t, more = {}) => ({ t, nk: t + ' Inc.', cls: 'us', ccy: 'USD', price: 200, ind: 'elec', ...more });
const dataOf = (stocks, more = {}) => ({ pxDate: T, usPxDate: T, publishedAt: PUB, wkFrom: '2026-11-13', usWkFrom: '2026-11-13', fx: 1450, stocks, ...more });
const KROWS = [['2026-11-12', 3990], ['2026-11-13', 4000], ['2026-11-16', 4010], ['2026-11-17', 4020], ['2026-11-18', 3980], ['2026-11-19', 4050], ['2026-11-20', 4080]];
const macroOf = (rows = KROWS) => ({ idxHist: { KOSPI: { asOf: rows.length ? rows[rows.length - 1][0] : T, rows } },
  fxHist: { asOf: T, final: true, rows: [['2026-11-12', 1395], ['2026-11-13', 1400], ['2026-11-16', 1420], ['2026-11-20', 1450]] } });
const loadOf = (stocks, more = {}, macro = macroOf()) => ({ status: 'ok', data: dataOf(stocks, more), macro, byT: new Map(stocks.map((s) => [s.t, s])),
  coByT: new Map(), fresh: { stale: false, days: 0 } });
const imp = (t, qty, more = {}) => ({ t, nk: '종목' + t, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty, ...more });
const deckOf = (rows, more = {}) => ({ id: 'd1', name: '내 포트폴리오', createdAt: '2026-09-01', kind: 'imported', settings: { points: {}, strict: 'normal' },
  holdings: rows.filter((r) => r.t).map((r) => ({ t: r.t, nk: r.nk, cls: r.ccy === 'USD' ? 'us' : 'kr' })), purchases: [], imported: rows, ...more });
const buy = (t, qty, price, date, more = {}) => ({ t, qty, price, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', date, ...more });
const model = (deck, load, now = NOW) => W.weeklyModel({ deck, load, ctx: { byT: load.byT, fx: load.data.fx }, now });
const r3 = (x) => (x == null ? null : Math.round(x * 1000) / 1000);
const r4 = (x) => (x == null ? null : Math.round(x * 10000) / 10000);
// the portfolio tile as weeklyView makes it: [big, sub, data-kospi]
const tile = (m) => { const t = WV.weeklyView(m).tiles.find((x) => x.id === 'pf'); return t ? [t.big, t.sub, t.data['data-kospi']] : null; };
const said = (m) => WV.weeklyView(m).say.filter((l) => l.includes('KOSPI'));
// the October week
const OCT = { pxDate: '2026-10-08', usPxDate: '2026-10-09', publishedAt: '2026-10-10T07:00:00+09:00', wkFrom: '2026-10-02', usWkFrom: '2026-10-02', fx: 1400 };
const OROWS = [['2026-10-01', 3500], ['2026-10-02', 3600], ['2026-10-06', 3650], ['2026-10-07', 3700], ['2026-10-08', 3720]];
const OMACRO = { idxHist: { KOSPI: { asOf: '2026-10-08', rows: OROWS } }, fxHist: { asOf: '2026-10-08', final: true, rows: [['2026-10-02', 1390], ['2026-10-08', 1400]] } };
const ONOW = Date.parse('2026-10-10T09:00:00+09:00');
"""


def test_a_week_with_no_buy_or_sale_is_exactly_the_plain_change():
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 }), us('AAPL', { c1w: 200, price: 210 }), kr('000660', { price: 50000 })];
      const plain = (4080 / 4000 - 1) * 100;                                   // today's formula, close of wkFrom to close of pxDate
      const one = (deck) => { const m = model(deck, loadOf(stocks)); return { same: m.kospi.pct === plain, keys: Object.keys(m.kospi), flows: m.money.flows,
        bare: W.kospiWeek(macroOf(), dataOf(stocks), m.week.starts).pct === m.kospi.pct, tile: tile(m) }; };
      out = {
        held: one(deckOf([imp('005930', 10), imp('AAPL', 4)])),
        // records outside the week (Sunday 11-15 counts as held at the start, Monday 11-23 is after the week): no flow of this week
        outside: one(deckOf([imp('005930', 10), imp('AAPL', 4)], { purchases: [buy('005930', 1, 100000, '2026-11-15'), buy('005930', 1, 100000, '2026-11-23')] })),
        // a stock left out of the week (held at the start without last week's close) takes its buy out with it: no flow either
        leftOut: one(deckOf([imp('005930', 10), imp('000660', 2)], { purchases: [buy('000660', 2, 48000, '2026-11-18')] })),
        // the money given with no flows (an older caller, or the flows list empty) is the same plain change
        noMoney: W.kospiWeek(macroOf(), dataOf([]), { kr: '2026-11-13' }, { start: 1, buys: 0, sells: 0, flows: [] }).pct === plain,
      };""")
    for k in ("held", "outside", "leftOut"):
        assert got[k]["same"] is True and got[k]["bare"] is True, (k, got[k])
        assert got[k]["keys"] == ["pct"] and got[k]["flows"] == [], (k, got[k])
    # 005930 10 × 100,000 + AAPL 4 × $200 × 1,400 = 2,120,000 → 1,100,000 + 4 × $210 × 1,450 = 2,318,000 · +198,000 (+9.3%) · 코스피 +2.0%
    assert got["held"]["tile"] == ["+9.3%", "+20만원 · 코스피 +2.0%", 2]
    assert got["leftOut"]["tile"][1].endswith("· 코스피 +2.0%")
    assert got["noMoney"] is True


def test_a_mid_week_buy_goes_into_kospi_at_the_close_of_its_date():
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 })];
      const m = model(deckOf([imp('005930', 10)], { purchases: [buy('005930', 5, 105000, '2026-11-18')] }), loadOf(stocks));
      out = { flows: m.money.flows, k: r4(m.kospi.pct), n: m.kospi.flows, pf: r3(m.money.pct), tile: tile(m), say: said(m) };""")
    # 내 포트폴리오: 10 × 100,000 = 1,000,000 → 5주 105,000 에 삼 (525,000) → 15 × 110,000 = 1,650,000 · 이득 125,000 ÷ 1,525,000 = 8.197%
    # 코스피, 같은 돈: 1,000,000 ÷ 4,000 = 250 단위 + 525,000 ÷ 3,980 (11-18 종가) = 131.9095 단위 → 381.9095 × 4,080 = 1,558,190.95
    #   이득 = 1,558,190.95 − 1,000,000 − 525,000 = 33,190.95 · ÷ 1,525,000 (같은 분모) = 2.1765% (한 주 전체 +2.0% 가 아니라)
    assert got["flows"] == [{"date": "2026-11-18", "won": 525000}]
    assert got["k"] == 2.1765 and got["n"] == 1 and got["pf"] == 8.197
    assert got["tile"] == ["+8.2%", "+13만원 · 코스피 +2.2%", 2.176]
    assert got["say"] == []


def test_a_mid_week_sale_comes_out_of_kospi_at_the_close_of_its_date():
    got = run("""
      const sale = (deck) => model(deck, loadOf([kr('005380', { c1w: 200000, price: 190000, ind: 'auto' })]));
      const m = sale(deckOf([imp('005380', 20)], { sales: [{ t: '005380', qty: 5, price: 210000, ccy: 'KRW', date: '2026-11-19' }] }));
      // the hand-worked week of tests/test_v196e_weekly.py (a buy, a sale, a US holding, one stock left out), on 코스피 rows for every day
      const stocks = [kr('005930', { c1w: 100000, price: 110000 }), kr('005380', { c1w: 200000, price: 190000, ind: 'auto' }), us('AAPL', { c1w: 200, price: 210 }),
        kr('000660', { price: 50000 })];
      const wk = model(deckOf([imp('005930', 10), imp('005380', 20), imp('AAPL', 4), imp('000660', 2)], {
        purchases: [buy('005930', 5, 105000, '2026-11-18')], sales: [{ t: '005380', qty: 5, price: 210000, ccy: 'KRW', date: '2026-11-19' }] }), loadOf(stocks));
      out = { flows: m.money.flows, k: r4(m.kospi.pct), tile: tile(m),
        wk: { flows: wk.money.flows, k: r4(wk.kospi.pct), pf: r3(wk.money.pct), tile: tile(wk) } };""")
    # 내 포트폴리오: 20 × 200,000 = 4,000,000 → 5주 210,000 에 팖 (1,050,000) → 15 × 190,000 = 2,850,000 · 이득 −100,000 ÷ 4,000,000 = −2.5%
    # 코스피: 4,000,000 ÷ 4,000 = 1,000 단위 − 1,050,000 ÷ 4,050 (11-19 종가) = 259.2593 단위 → 740.7407 × 4,080 = 3,022,222.22
    #   이득 = 3,022,222.22 − 4,000,000 + 1,050,000 = 72,222.22 · ÷ 4,000,000 = 1.8056%
    assert got["flows"] == [{"date": "2026-11-19", "won": -1050000}]
    assert got["k"] == 1.8056 and got["tile"] == ["−2.5%", "−10만원 · 코스피 +1.8%", 1.806]
    # the hand-worked week: start 6,120,000 · buys 525,000 (11-18) · sales 1,050,000 (11-19) · its own % 1.851 (unchanged)
    # 코스피: 6,120,000 ÷ 4,000 = 1,530 + 525,000 ÷ 3,980 = 131.9095 − 1,050,000 ÷ 4,050 = 259.2593 → 1,402.6503 × 4,080 = 5,722,813.18
    #   이득 = 5,722,813.18 − 6,120,000 − 525,000 + 1,050,000 = 127,813.18 · ÷ 6,645,000 = 1.9234%
    assert got["wk"]["flows"] == [{"date": "2026-11-18", "won": 525000}, {"date": "2026-11-19", "won": -1050000}]
    assert got["wk"]["k"] == 1.9234 and got["wk"]["pf"] == 1.851 and got["wk"]["tile"] == ["+1.9%", "+12만원 · 코스피 +1.9%", 1.923]


def test_a_flow_on_a_day_without_a_kospi_close_takes_the_last_close_before_it():
    got = run("""
      const at = (d, rows = OROWS) => W.kospiAt(rows, d, '2026-10-02', '2026-10-08');
      const st = [kr('005930', { c1w: 100000, price: 104000 }), us('AAPL', { price: 255 })];
      const L = { status: 'ok', data: { ...OCT, stocks: st }, macro: OMACRO, byT: new Map(st.map((s) => [s.t, s])), coByT: new Map(), fresh: { stale: false, days: 0 } };
      // a buy on the Korean holiday Monday 10-05 and a US buy dated Friday 10-09 (the US trades, the Korean market is closed)
      const m = model(deckOf([imp('005930', 10)], { holdings: [{ t: '005930', nk: '종목005930', cls: 'kr' }, { t: 'AAPL', nk: 'AAPL', cls: 'us' }],
        purchases: [buy('005930', 2, 101000, '2026-10-05'), buy('AAPL', 1, 250, '2026-10-09', { fx: 1400 })] }), L, ONOW);
      out = { at: { holiday: at('2026-10-05'), tue: at('2026-10-06'), us: at('2026-10-09'), sat: at('2026-10-10'), sun: at('2026-10-11'),
          // a Saturday and a Sunday of the November week: Friday's close (11-20)
          novSat: W.kospiAt(KROWS, '2026-11-21', '2026-11-13', T), novSun: W.kospiAt(KROWS, '2026-11-22', '2026-11-13', T) },
        week: m.week.ok, flows: m.money.flows, k: r4(m.kospi.pct), plain: r4((3720 / 3600 - 1) * 100), tile: tile(m) };""")
    assert got["at"] == {"holiday": 3600, "tue": 3650, "us": 3720, "sat": 3720, "sun": 3720, "novSat": 4080, "novSun": 4080}
    # start 10 × 100,000 = 1,000,000 (10-02) · buys 2 × 101,000 = 202,000 (10-05 → 10-02's 3,600) and 1 × $250 × 1,400 = 350,000 (10-09 → 10-08's 3,720)
    # 코스피: (1,000,000 + 202,000) ÷ 3,600 = 333.8889 단위 + 350,000 ÷ 3,720 = 94.0860 → × 3,720 = 1,592,066.67
    #   이득 = 1,592,066.67 − 1,000,000 − 552,000 = 40,066.67 · ÷ 1,552,000 = 2.5816% (한 주 전체는 3,600 → 3,720 = +3.3333%)
    assert got["week"] is True
    assert got["flows"] == [{"date": "2026-10-05", "won": 202000}, {"date": "2026-10-09", "won": 350000}]
    assert got["k"] == 2.5816 and got["plain"] == 3.3333
    assert got["tile"][1].endswith("· 코스피 +2.6%") and got["tile"][2] == 2.582


def test_a_missing_kospi_close_leaves_kospi_out_of_the_tile_as_before():
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 })];
      const deck = deckOf([imp('005930', 10)], { purchases: [buy('005930', 5, 105000, '2026-11-18')] });
      const without = (d) => macroOf(KROWS.filter((r) => r[0] !== d));
      const g = (macro) => { const m = model(deck, loadOf(stocks, {}, macro)); return { k: m.kospi, pf: r3(m.money.pct), tile: tile(m), say: said(m) }; };
      out = {
        // 11-18 is a Korean trading day: its row missing is a missing close, never Tuesday's close in its place
        flowDay: g(without('2026-11-18')),
        start: g(without('2026-11-13')).k, end: g(without('2026-11-20')).k, rows: g(macroOf([])).k,
        // kospiAt: a trading day without its row · before wkFrom · a date that cannot be read
        at: [W.kospiAt(KROWS.filter((r) => r[0] !== '2026-11-18'), '2026-11-18', '2026-11-13', T), W.kospiAt(KROWS, '2026-11-12', '2026-11-13', T),
          W.kospiAt(KROWS, '2026-11-31', '2026-11-13', T), W.kospiAt(KROWS, '2026-11-19', '2026-11-13', T)],
      };""")
    # the portfolio's own figure stays (8.197%, 125,000원 → +13만원); the 코스피 part is left out and the console says why, as today
    assert got["flowDay"]["k"] == {"pct": None, "why": "flow"}
    assert got["flowDay"]["pf"] == 8.197 and got["flowDay"]["tile"] == ["+8.2%", "+13만원", ""]
    assert got["flowDay"]["say"] == ["no KOSPI week (flow)"]
    assert got["start"] == {"pct": None, "why": "start"} and got["end"] == {"pct": None, "why": "end"} and got["rows"] == {"pct": None, "why": "rows"}
    assert got["at"] == [None, None, None, 4050]


def test_a_dollar_flow_uses_the_portfolios_own_won_amount():
    got = run("""
      const stocks = [us('AAPL', { c1w: 200, price: 210 })];
      const g = (more) => { const m = model(deckOf([imp('AAPL', 4)], more), loadOf(stocks));
        return { flows: m.money.flows, buys: m.money.buys, sells: m.money.sells, k: r4(m.kospi.pct), left: m.money.left.map((x) => x.why), tile: tile(m) }; };
      out = {
        buy: g({ purchases: [buy('AAPL', 2, 205, '2026-11-18', { fx: 1430 })] }),
        sale: g({ sales: [{ t: 'AAPL', qty: 2, price: 205, ccy: 'USD', fx: 1440, date: '2026-11-19' }] }),
        // a dollar buy without a rate: the stock is left out (fx), so its money is no flow either
        noRate: g({ purchases: [buy('AAPL', 2, 205, '2026-11-18')] }),
      };""")
    # start 4 × $200 × 1,400 = 1,120,000 · buy 2 × $205 × 1,430 (the record's own rate) = 586,300 won, the same amount in both
    # 코스피: 1,120,000 ÷ 4,000 = 280 + 586,300 ÷ 3,980 = 147.3116 → 427.3116 × 4,080 = 1,743,431.16 · 이득 37,131.16 ÷ 1,706,300 = 2.1761%
    assert got["buy"]["flows"] == [{"date": "2026-11-18", "won": 586300}] and got["buy"]["buys"] == 586300 and got["buy"]["k"] == 2.1761
    # sale 2 × $205 × 1,440 = 590,400 won out · 280 − 590,400 ÷ 4,050 = 145.7778 → 134.2222 × 4,080 = 547,626.67
    #   이득 = 547,626.67 − 1,120,000 + 590,400 = 18,026.67 · ÷ 1,120,000 = 1.6095%
    assert got["sale"]["flows"] == [{"date": "2026-11-19", "won": -590400}] and got["sale"]["sells"] == 590400 and got["sale"]["k"] == 1.6095
    assert got["noRate"]["left"] == ["fx"] and got["noRate"]["flows"] == [] and got["noRate"]["tile"] is None


def test_the_kospi_figure_rounds_as_the_tile_shows_it():
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 })];
      const deck = deckOf([imp('005930', 10)], { purchases: [buy('005930', 5, 105000, '2026-11-18')] });
      // 코스피 flat at 4,000 all week but 4,002 on 11-18, the day of the buy
      const flat = [['2026-11-13', 4000], ['2026-11-16', 4000], ['2026-11-17', 4000], ['2026-11-18', 4002], ['2026-11-19', 4000], ['2026-11-20', 4000]];
      const one = (macro) => { const m = model(deck, loadOf(stocks, {}, macro)); const t = tile(m);
        return { k: m.kospi.pct, t, text: C.weekly.kospi.replace('{pct}', DC.signedPct(m.kospi.pct)), r3: r3(m.kospi.pct) }; };
      out = { tiny: one(macroOf(flat)), normal: one(macroOf()) };""")
    # 525,000 bought at 4,002 and worth 525,000 × 4,000 ÷ 4,002 = 524,737.63 at the end: 코스피 이득 −262.37 ÷ 1,525,000 = −0.0172%
    # → "코스피 0.0%" (no sign, as the tile's own % at one decimal) and data-kospi −0.017
    assert round(got["tiny"]["k"], 4) == -0.0172
    for k in ("tiny", "normal"):
        g = got[k]
        assert g["t"][1].endswith(" · " + g["text"]) and g["t"][2] == g["r3"], (k, g)          # one pct: the words and data-kospi
    assert got["tiny"]["t"][1] == "+13만원 · 코스피 0.0%" and got["tiny"]["t"][2] == -0.017
    assert got["normal"]["t"][1] == "+13만원 · 코스피 +2.2%"


def test_a_sale_of_more_than_the_kospi_side_holds_leaves_kospi_out():
    got = run("""
      const g = (stocks, more) => { const m = model(deckOf([imp('005930', 10)], more), loadOf(stocks)); return { k: m.kospi, r: r4(m.kospi.pct), tile: tile(m), say: said(m) }; };
      out = {
        // sold all 10 shares on 11-17 for 2,000,000 (the stock doubled): the 코스피 side holds 250 × 4,020 = 1,005,000 then
        over: g([kr('005930', { c1w: 100000, price: 200000 })], { sales: [{ t: '005930', qty: 10, price: 200000, ccy: 'KRW', date: '2026-11-17' }] }),
        // sold all 10 on 11-17 at 100,500, exactly the 코스피 side's 1,005,000: nothing left on either side, 코스피 0.5% (4,000 → 4,020)
        exact: g([kr('005930', { c1w: 100000, price: 100500 })], { sales: [{ t: '005930', qty: 10, price: 100500, ccy: 'KRW', date: '2026-11-17' }] }),
        // a sale and a buy on the same day count together (the records carry no time): 1,800,000 out and 1,000,000 in on 11-17
        sameDay: g([kr('005930', { c1w: 100000, price: 180000 }), kr('000660', { price: 101000 })], { holdings: [{ t: '005930', nk: 'a', cls: 'kr' }, { t: '000660', nk: 'b', cls: 'kr' }],
          sales: [{ t: '005930', qty: 10, price: 180000, ccy: 'KRW', date: '2026-11-17' }], purchases: [buy('000660', 10, 100000, '2026-11-17')] }),
      };""")
    assert got["over"]["k"] == {"pct": None, "why": "over"} and got["over"]["say"] == ["no KOSPI week (over)"]
    assert got["over"]["tile"] == ["+100.0%", "+100만원", ""]                       # the portfolio's own: 2,000,000 − 1,000,000 ÷ 1,000,000
    assert got["exact"]["r"] == 0.5 and got["exact"]["k"]["flows"] == 1
    # 250 units − 800,000 ÷ 4,020 = 199.0050 → 50.9950 × 4,080 = 208,059.70 · 이득 = 208,059.70 − 1,000,000 − 1,000,000 + 1,800,000 = 8,059.70
    #   ÷ 2,000,000 = 0.4030%
    assert got["sameDay"]["r"] == 0.403 and got["sameDay"]["k"]["flows"] == 2


def test_the_hand_worked_week_on_the_old_sparse_kospi_rows_has_no_kospi_and_says_why():
    # tests/test_v196e_weekly.py's hand-worked week on the rows its shared MACRO has (11-12 · 11-13 · 11-16 · 11-20): the buy (11-18) and
    # the sale (11-19) fall on Korean trading days with no 코스피 row, so 코스피 is a missing close, never 11-16's 4,010 in their place
    got = run("""
      const stocks = [kr('005930', { c1w: 100000, price: 110000 }), kr('005380', { c1w: 200000, price: 190000, ind: 'auto' }), us('AAPL', { c1w: 200, price: 210 }),
        kr('000660', { price: 50000 })];
      const deck = deckOf([imp('005930', 10), imp('005380', 20), imp('AAPL', 4), imp('000660', 2)], {
        purchases: [buy('005930', 5, 105000, '2026-11-18')], sales: [{ t: '005380', qty: 5, price: 210000, ccy: 'KRW', date: '2026-11-19' }] });
      const sparse = macroOf([['2026-11-12', 3990], ['2026-11-13', 4000], ['2026-11-16', 4010], ['2026-11-20', 4080]]);
      const m = model(deck, loadOf(stocks, {}, sparse));
      out = { k: m.kospi, pf: r3(m.money.pct), tile: tile(m), say: said(m) };""")
    assert got["k"] == {"pct": None, "why": "flow"}
    assert got["pf"] == 1.851 and got["tile"] == ["+1.9%", "+12만원", ""]           # the portfolio's own figure is unchanged
    assert got["say"] == ["no KOSPI week (flow)"]
