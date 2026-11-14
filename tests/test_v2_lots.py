# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6a 판 기록의 계산 (src/v2/lots.js · held.js · track.js · pf.js) — Node 로 돌려봐요.

docs/tasks/v19.6-records-alerts-dark.md A.4 · A.5 · A.6:
- 이동평균: 팔면 모든 묶음(산 기록 · 가져온 줄)이 같은 비율로 줄어요. 판 뒤의 평균 단가는 그대로, 판 뒤에 산 것은 남은 것과 평균
- 판 수익(원) = 수량 × 가격 × 판 날 환율 − 그 판매가 덜어 낸 원화 원가. 달러 평균 단가만 있는 미국 종목은 달러 수익 × 판 날 환율,
  가지고 있는 동안은 오늘 환율 ([Q11]). 원가를 모르면(평균 단가 없음 · 환율 없음) 수익은 없음, 0 이 아니에요
- 0.1 + 0.2 주를 다 팔아도 거절하지 않아요 (1/10,000 주 단위)
- 미국 종목 수익, 어디서 왔나: 주가 + 환율 = 그 묶음들의 원화 수익 (판 뒤에도 정확히)
- 코스피 비교 [Q4]: 판 비율만큼 코스피도 팔아요. 배당은 양쪽 모두 빼요. 뺀 종목(history)은 판 만큼만
- 내 수익: 세 줄이 같은 기준(평균 단가를 넣은 종목)이고, 반올림한 줄을 더한 것이 머리 금액 · 모르는 부분은 빼고 이름을 밝혀요
- 주식 분할: 분할 전 기록은 수량 × r, 가격 ÷ r 로 읽어요 (저장은 쓴 그대로). 날짜 없는 가져온 줄은 포트폴리오를 만든 날 기준
- 가진 수량은 어디서나 같은 규칙: 매일 점검(비중 · 밴드 · 추가로 넣을 돈), 원금, 점검 보고서(pfState), 코스피 비교
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

MODS = (("L", "lots.js"), ("H", "held.js"), ("S", "store.js"), ("T", "track.js"), ("R", "rules.js"), ("P", "pf.js"), ("Rc", "records.js"),
        ("Hm", "home.js"))


def run(body, **data):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-lots-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in MODS:
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/lots.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    pre = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    names = ", ".join(n for n, _ in MODS)
    code = (f"import {{ {names} }} from './lots.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {{}};\n"
            + pre + HELP + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


HELP = """
const buy = (t, qty, price, date, extra = {}) => ({ t, qty, price, date, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', ...extra });
const sell = buy;
const div = (t, amount, date, extra = {}) => ({ t, amount, date, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', ...extra });
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const built = (rows, extra = {}) => ({ id: 'd', name: 'p', createdAt: '2026-09-01', planFx: 1300,
  holdings: rows.map(([t, nk, target]) => ({ t, nk, cls: /^[0-9]/.test(t) ? 'kr' : 'us', target, rules: band(target) })), purchases: [], ...extra });
const kr = (t, price, extra = {}) => ({ t, nk: t, cls: 'kr', price, ...extra });
const us = (t, price, extra = {}) => ({ t, nk: t, cls: 'us', ccy: 'USD', price, ...extra });
const ctxOf = (stocks, fx = 1400) => ({ state: { ok: true }, byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map(), fx, pxDate: '2026-11-06' });
const close = (a, b, e = 1e-6) => Math.abs(a - b) <= e;
"""


def test_moving_average_a_sale_keeps_the_average_and_a_later_buy_averages_with_what_is_left():
    got = run("""const d = built([['000010', 'a', 1]], { purchases: [buy('000010', 10, 100, '2026-10-01'), buy('000010', 5, 200, '2026-10-20')],
        sales: [sell('000010', 5, 150, '2026-10-10')] });
      const L1 = L.ledger(built([['000010', 'a', 1]], { purchases: [buy('000010', 10, 100, '2026-10-01')], sales: [sell('000010', 5, 150, '2026-10-10')] }), '000010');
      const L2 = L.ledger(d, '000010');
      out = { a1: L1.avgOwn, g1: L1.sales[0].gain, rem1: L1.lots.map((l) => [l.u, l.won]), a2: L2.avgOwn, held: L2.held, avgOf: P.avgOf(d, '000010'),
        putIn: L2.putIn.won, removed: L2.removedWon };""")
    assert got["a1"] == 100 and got["g1"] == 5 * 150 - 500 and got["rem1"] == [[50000, 500]]   # 반을 팔면 원가도 반
    assert got["a2"] == 150 and got["held"] == 100000                                           # (500 + 1,000) / 10주
    assert got["avgOf"] == {"avg": 150, "ccy": "KRW"}                                          # 화면의 평균 단가도 같은 계산
    assert got["putIn"] == 2000 and got["removed"] == 500                                      # 산 금액 전체는 판 주식 포함


def test_every_open_lot_shrinks_by_the_same_fraction_and_gain_is_proceeds_minus_removed_won_cost():
    got = run("""const d = built([['AAA', 'Alpha', 1]], { purchases: [buy('AAA', 3, 100, '2026-10-01', { fx: 1300 }), buy('AAA', 1, 120, '2026-10-02', { fx: 1400 })],
        sales: [sell('AAA', 2, 150, '2026-10-10', { fx: 1350 })] });
      const Lg = L.ledger(d, 'AAA');
      out = { s: Lg.sales[0], lots: Lg.lots.map((l) => [l.u, l.own, l.won, l.rate]), avg: Lg.avgOwn };""")
    s = got["s"]
    assert s["removedWon"] == (3 * 100 * 1300 + 120 * 1400) / 2 and s["gain"] == 2 * 150 * 1350 - (3 * 100 * 1300 + 120 * 1400) / 2
    assert s["why"] is None and s["usdOnly"] is False
    assert got["lots"] == [[15000, 150, 195000, 1300], [5000, 60, 84000, 1400]] and got["avg"] == 105


def test_dollar_only_holding_sale_uses_the_sale_date_rate_and_held_cost_uses_todays_rate():
    got = run("""const d = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} }, holdings: [{ t: 'AAA', nk: 'Alpha', cls: 'us' }],
        purchases: [], imported: [{ t: 'AAA', nk: 'Alpha', ccy: 'USD', qty: 4, avg: 80 }], sales: [sell('AAA', 1, 100, '2026-10-10', { fx: 1350 })] };
      const Lg = L.ledger(d, 'AAA');
      const v = L.openValue(Lg, 110, 1400);
      const r = L.returnsOf(d, { pxOf: () => 110, fx: 1400, absent: new Set() });
      const m = T.deckMoney(d, R.evaluateDeck(d, ctxOf([us('AAA', 110)])), ctxOf([us('AAA', 110)]));
      const noFx = L.ledger({ ...d, sales: [sell('AAA', 1, 100, '2015-10-10')] }, 'AAA').sales[0];
      out = { s: Lg.sales[0], v, r: { held: r.held, sold: r.sold, cost: r.cost, usdOnly: r.usdOnly }, m: { cost: m.cost, usdToday: m.usdToday }, noFx };""")
    s = got["s"]
    assert s["gain"] == (100 - 80) * 1350 and s["usdOnly"] is True and s["removedWon"] == 0 and s["removedUsdOwn"] == 80   # 달러 수익 × 판 날 환율
    assert got["v"]["cost"] == 3 * 80 * 1400 and got["v"]["value"] == 3 * 110 * 1400 and got["v"]["usdOnly"] is True     # 오늘 환율 ([Q11])
    assert got["r"] == {"held": 3 * 30 * 1400, "sold": 20 * 1350, "cost": 4 * 80 * 1400, "usdOnly": True}                 # 산 금액 전체도 오늘 환율
    assert got["m"] == {"cost": 3 * 80 * 1400, "usdToday": True}
    assert got["noFx"]["gain"] is None and got["noFx"]["why"] == "noRate"                     # 2016 전: 환율 없이 저장 → 수익 없음


def test_no_average_price_or_no_rate_means_no_gain_never_zero():
    got = run("""const imp = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', cls: 'kr' }],
        purchases: [], imported: [{ t: '000010', nk: 'a', ccy: 'KRW', qty: 10 }], sales: [sell('000010', 4, 100, '2026-10-10')], divs: [div('000010', 500, '2026-10-11')] };
      const noRate = built([['AAA', 'Alpha', 1]], { planFx: undefined, purchases: [buy('AAA', 2, 100, '2026-10-01')], sales: [sell('AAA', 1, 120, '2026-10-10', { fx: 1300 })] });
      delete noRate.planFx;
      const r = L.returnsOf(imp, { pxOf: () => 120, fx: 1400, absent: new Set() });
      const r2 = L.returnsOf(noRate, { pxOf: () => 130, fx: 1400, absent: new Set() });
      out = { a: L.ledger(imp, '000010').sales[0], b: L.ledger(noRate, 'AAA').sales[0], r: { ...r, ledgers: undefined }, r2: { ...r2, ledgers: undefined } };""")
    assert got["a"]["gain"] is None and got["a"]["why"] == "noCost"
    assert got["b"]["gain"] is None and got["b"]["why"] == "noRate"
    r = got["r"]
    assert r["noAvg"] == ["000010"] and r["n"] == 0 and r["held"] == 0 and r["sold"] == 0 and r["divs"] == 0 and r["soldOut"] == 1   # 통째로 빼고 이름을 밝혀요
    r2 = got["r2"]
    assert r2["noFx"] == ["AAA"] and r2["cost"] is None and r2["soldOut"] == 1               # noFx 줄: 원금 · 수익률 없음


def test_a_full_sale_of_point_one_plus_point_two_shares_is_not_refused():
    got = run("""const d = built([['AAA', 'Alpha', 1]], { purchases: [buy('AAA', 1, 100, '2026-10-01', { fx: 1300 })],
        sales: [sell('AAA', 0.1, 110, '2026-10-02', { fx: 1300 }), sell('AAA', 0.2, 110, '2026-10-03', { fx: 1300 }), sell('AAA', 0.7, 110, '2026-10-04', { fx: 1300 })] });
      const over = { ...d, sales: [...d.sales, sell('AAA', 0.0001, 110, '2026-10-05', { fx: 1300 })] };
      out = { low: H.belowZero(d), held: H.heldUnits(d).get('AAA'), lots: L.ledger(d, 'AAA').lots.length, p: S.deckProblem(d, '2026-11-06'),
        over: H.belowZero(over), gains: L.ledger(d, 'AAA').sales.map((s) => Math.round(s.gain * 1000) / 1000) };""")
    assert got["low"] is None and got["held"] == 0 and got["lots"] == 0 and got["p"] is None
    assert got["over"] == {"t": "AAA", "date": "2026-10-05"}                                  # 1/10,000 주 더 팔면 거절
    assert got["gains"] == [1300, 2600, 9100]                                                 # (110 − 100) × 수량 × 1,300


def test_fx_split_adds_up_exactly_to_the_won_gain_including_after_sales():
    got = run("""const out1 = [];
      let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
      for (let k = 0; k < 200; k++) {
        const ps = [], ss = [];
        let held = 0;
        for (let i = 0; i < 1 + Math.floor(rnd() * 4); i++) { const q = 1 + Math.floor(rnd() * 20); held += q;
          ps.push(buy('AAA', q, Math.round(50 + rnd() * 200), '2026-10-0' + (1 + i), { fx: Math.round(1200 + rnd() * 300) })); }
        if (rnd() < 0.7) { const q = Math.max(0.0001, Math.round(held * rnd() * 0.9 * 10000) / 10000); ss.push(sell('AAA', q, 100, '2026-10-08', { fx: 1333 })); }
        const d = built([['AAA', 'Alpha', 1]], { purchases: ps, sales: ss });
        const Lg = L.ledger(d, 'AAA');
        const px = Math.round(80 + rnd() * 200), fx = Math.round(1250 + rnd() * 250);
        const f = L.fxSplit([Lg], () => px, fx);
        const v = L.openValue(Lg, px, fx);
        if (f.empty) continue;
        out1.push([f.price + f.rate - v.gain, f.gain - v.gain, f.value - v.value, f.cost - v.cost]);
      }
      const one = L.fxSplit([L.ledger(built([['AAA', 'A', 1]], { purchases: [buy('AAA', 2, 100, '2026-10-01', { fx: 1320 })] }), 'AAA')], () => 150, 1390);
      out = { diffs: out1, n: out1.length, one };""")
    assert got["n"] > 150
    assert all(abs(x) < 1e-6 for row in got["diffs"] for x in row), max(abs(x) for row in got["diffs"] for x in row)
    one = got["one"]
    assert one["price"] == (150 - 100) * 2 * 1320 and one["rate"] == 150 * 2 * (1390 - 1320) and one["lotRate"] == 1320
    assert abs(one["avgRate"] - 1320) < 1e-9 and one["leftOut"] == []


def test_fx_split_rate_line_is_weighted_by_remaining_dollar_cost_and_dollar_only_holdings_are_left_out():
    got = run("""const d = built([['AAA', 'A', 0.5], ['BBB', 'B', 0.5]], { purchases: [buy('AAA', 1, 100, '2026-10-01', { fx: 1300 }), buy('AAA', 3, 100, '2026-10-02', { fx: 1400 })] });
      const imp = { t: 'BBB', ccy: 'USD', imported: [{ t: 'BBB', nk: 'B', ccy: 'USD', qty: 2, avg: 50 }] };
      const f = L.fxSplit([L.ledger(d, 'AAA'), L.ledger({ imported: imp.imported }, 'BBB')], () => 120, 1450);
      out = f;""")
    assert abs(got["avgRate"] - (100 * 1300 + 300 * 1400) / 400) < 1e-9 and got["lotRate"] is None and sorted(got["rates"]) == [1300, 1400]
    assert got["leftOut"] == ["BBB"] and got["n"] == 1


def test_kospi_mirror_sells_the_same_fraction_and_leaves_dividends_out():
    got = run("""const idx = { asOf: '2026-11-06', rows: [['2026-09-30', 100], ['2026-10-09', 120], ['2026-11-06', 130]] };
      const d = built([['000010', 'a', 1]], { purchases: [buy('000010', 10, 1000, '2026-10-01')], sales: [sell('000010', 4, 1500, '2026-10-10')],
        divs: [div('000010', 777, '2026-10-12')] });
      const k = T.indexSince(d, idx, '2026-11-06', () => 6 * 2000);
      const noDiv = T.indexSince({ ...d, divs: [] }, idx, '2026-11-06', () => 6 * 2000);
      // taken out after the sale with 6 shares unsold: only the sold part stays in (its money and its KOSPI units)
      const out2 = S.withoutHolding(S.validStore({ v: 2, decks: [d] }, '2026-11-06') ? { v: 2, decks: [d] } : null, 'd', '000010', '2026-11-06', 5);
      const h = T.indexSince(out2.decks[0], idx, '2026-11-06', () => null);
      out = { k, noDiv, h, hist: out2.decks[0].history.length };""")
    # 산 날 전 종가 100 에 1만원 → 100단위 · 판 날 전 종가 120 에 40% 팔아 40 × 120 = 4,800 · 남은 60 × 130 = 7,800
    k = got["k"]
    assert k["ok"] and abs(k["ret"] - ((60 * 130 + 40 * 120) / 10000 - 1)) < 1e-12
    assert abs(k["mine"] - ((12000 + 4 * 1500) / 10000 - 1)) < 1e-12 and k["start"] == "2026-10-01"
    assert got["noDiv"] == k                                                                  # 배당은 양쪽 모두에서 빠져요
    h = got["h"]                                                                              # 뺀 종목: 판 만큼만 (원가 4,000원 · 4,800 · 판 돈 6,000)
    assert got["hist"] == 1 and h["ok"] and abs(h["ret"] - (4800 / 4000 - 1)) < 1e-12 and abs(h["mine"] - (6000 / 4000 - 1)) < 1e-12


def test_returns_rows_add_up_and_cost_counts_every_purchase_including_sold_shares():
    got = run("""const d = built([['000010', 'a', 0.5], ['AAA', 'A', 0.5]], {
        purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('AAA', 2, 100, '2026-10-01', { fx: 1300 })],
        sales: [sell('000010', 5, 1200, '2026-10-10')], divs: [div('000010', 300, '2026-10-12'), div('AAA', 1.5, '2026-10-13', { fx: 1350 })] });
      const r = L.returnsOf(d, { pxOf: (t) => (t === 'AAA' ? 110 : 1100), fx: 1400, absent: new Set() });
      const rr = L.roundRows([r.held, r.sold, r.divs]);
      const big = L.roundRows([843217, 380000, -52000], { exact: false }), bigDef = L.roundRows([843217, 380000, -52000]);
      const zero = L.roundRows([0, 0, 0]);
      out = { r: { ...r, ledgers: undefined }, rr, big, bigDef, zero };""")
    r = got["r"]
    assert r["held"] == 5 * 100 + (2 * 110 * 1400 - 2 * 100 * 1300) and r["sold"] == 5 * 200 and r["divs"] == 300 + 1.5 * 1350
    assert r["cost"] == 10000 + 2 * 100 * 1300 and r["n"] == 2 and r["noAvg"] == [] and r["noFx"] == []
    rr = got["rr"]
    assert rr["unit"] == 1 and rr["total"] == sum(rr["rows"])                                  # 1만원 아래 줄이 있으면 원 단위
    # 스위치 C (Jack, 2026-11-13: 늘 정확한 금액): 기본은 원 단위 그대로. 만원 규칙(꺼진 상태)은 모두 1만원 넘으면 만원 단위, 합은 반올림한 줄의 합
    assert got["bigDef"] == {"unit": 1, "rows": [843217, 380000, -52000], "total": 1171217}
    assert got["big"] == {"unit": 10000, "rows": [840000, 380000, -50000], "total": 1170000}
    assert got["zero"]["total"] == 0


def test_returns_a_stock_taken_out_keeps_its_realized_gain_and_dividends_and_leaves_its_unsold_cost():
    got = run("""const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], {
        purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('000020', 1, 5000, '2026-10-01')], sales: [sell('000010', 4, 1500, '2026-10-10')],
        divs: [div('000010', 200, '2026-10-11')] });
      const out2 = S.withoutHolding({ v: 2, decks: [d] }, 'd', '000010', '2026-11-01', 5).decks[0];
      const later = Rc.withRecord({ v: 2, decks: [out2] }, 'd', 'divs', div('000010', 300, '2026-11-02'), '2026-11-06');
      const r = L.returnsOf(later.decks[0], { pxOf: () => 6000, fx: 1400, absent: new Set() });
      out = { r: { ...r, ledgers: undefined }, entry: later.decks[0].history[0] };""")
    r = got["r"]
    assert r["sold"] == 4 * 500 and r["divs"] == 500 and r["held"] == 1000                     # 판 수익 · 배당(뺀 뒤 받은 것 포함)은 남아요
    assert r["cost"] == 4000 + 5000                                                            # 안 판 6주의 원가는 빠져요 (A.3)
    assert len(got["entry"]["divs"]) == 2 and got["entry"]["out"] == "2026-11-01"


def test_returns_name_what_is_left_out_absent_stocks_and_no_price():
    got = run("""const d = built([['000010', 'a', 0.5], ['000099', 'gone', 0.5]], { purchases: [buy('000010', 1, 1000, '2026-10-01'), buy('000099', 1, 1000, '2026-10-01')] });
      const r = L.returnsOf(d, { pxOf: (t) => (t === '000010' ? 1100 : null), fx: 1400, absent: new Set(['000099']) });
      out = { ...r, ledgers: undefined };""")
    assert got["absent"] == ["000099"] and got["held"] == 100 and got["cost"] == 1000 and got["n"] == 1


def test_stock_split_reads_earlier_records_at_the_new_basis_and_the_store_accepts_a_sale_of_the_new_count():
    got = run("""const d = built([['AAA', 'A', 1]], { purchases: [buy('AAA', 10, 400, '2026-08-01', { fx: 1300 })] });
      const sale = sell('AAA', 40, 120, '2026-10-01', { fx: 1300 });
      const raw = { ...d, sales: [sale] };
      const view = L.withDataSplits({ v: 2, decks: [raw] }, [{ t: 'AAA', date: '2026-09-01', r: 4 }], '2026-11-06').decks[0];
      const stored = { ...raw, splits: [{ t: 'AAA', date: '2026-09-01', r: 4 }] };
      const viewHeld = L.withDataSplits({ v: 2, decks: [d] }, [{ t: 'AAA', date: '2026-09-01', r: 4 }], '2026-11-06').decks[0];
      const Lg = L.ledger(stored, 'AAA');
      out = { rawLow: H.belowZero(raw), viewLow: H.belowZero(view), rawProblem: S.deckProblem(raw, '2026-11-06'), viewProblem: S.deckProblem(view, '2026-11-06'),
        storedProblem: S.deckProblem(stored, '2026-11-06'), heldView: H.heldUnits(viewHeld).get('AAA'), avgView: P.avgOf(viewHeld, 'AAA'),
        gain: Lg.sales[0].gain, written: JSON.stringify(view).includes('splits'), oneSide: L.splitsToStore(viewHeld, 'AAA'), toStore: L.splitsToStore(view, 'AAA'),
        future: L.withDataSplits({ v: 2, decks: [d] }, [{ t: 'AAA', date: '2026-12-01', r: 4 }], '2026-11-06').decks[0] === d,
        merge: H.heldUnits({ ...d, splits: [{ t: 'AAA', date: '2026-09-01', r: 0.1 }] }).get('AAA') };""")
    assert got["rawLow"] == {"t": "AAA", "date": "2026-10-01"}                                 # 분할을 모르면 40주 판매는 0 아래
    assert got["viewLow"] is None and got["heldView"] == 400000 and got["avgView"] == {"avg": 100, "ccy": "USD"}   # 10주 × 4 · $400 ÷ 4
    assert got["viewProblem"] is not None                                                     # 저장 검사는 저장된 분할만 읽어요 (화면용은 저장 안 됨)
    assert got["storedProblem"] is None and got["gain"] == 40 * 120 * 1300 - 10 * 400 * 1300
    assert got["written"] is False                                                            # 화면용 분할은 JSON 에 안 나가요
    assert got["oneSide"] == [{"t": "AAA", "date": "2026-09-01", "r": 4}]                    # 리뷰 2차: 분할 전 기록이 하나라도 있으면 저장 (산 뒤 그대로 둔 사람도)
    assert got["toStore"] == [{"t": "AAA", "date": "2026-09-01", "r": 4}]
    assert got["future"] is True and got["merge"] == 10000                                     # 앞날 분할은 적용 안 함 · 10:1 병합 → 1주


def test_split_an_undated_imported_row_counts_from_the_day_the_portfolio_was_made():
    got = run("""const mk = (createdAt) => ({ id: 'i', name: 'i', createdAt, kind: 'imported', settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', cls: 'kr' }],
        purchases: [], imported: [{ t: '000010', nk: 'a', ccy: 'KRW', qty: 3, avg: 900 }], splits: [{ t: '000010', date: '2026-09-01', r: 5 }] });
      out = { before: H.heldUnits(mk('2026-08-01')).get('000010'), after: H.heldUnits(mk('2026-10-01')).get('000010'),
        avgBefore: P.avgOf(mk('2026-08-01'), '000010'), avgAfter: P.avgOf(mk('2026-10-01'), '000010') };""")
    assert got["before"] == 150000 and got["avgBefore"] == {"avg": 180, "ccy": "KRW"}          # 분할 전에 넣은 3주 → 15주, 900 ÷ 5
    assert got["after"] == 30000 and got["avgAfter"] == {"avg": 900, "ccy": "KRW"}             # 분할 뒤에 넣은 수량은 그대로


def test_held_quantity_after_a_sale_in_every_calculation():
    """A.1 'Held quantity everywhere': evaluateDeck (weights, band statuses), deckMoney, heldCost, 추가로 넣을 돈, the 점검 report
    (pfState) and 홈 all read the same held quantity after a sale."""
    got = run("""const stocks = [kr('000010', 1000), kr('000020', 1000)];
      const ctx = ctxOf(stocks);
      const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], { purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('000020', 10, 1000, '2026-10-01')],
        sales: [sell('000010', 6, 1000, '2026-10-10')] });
      const e = R.evaluateDeck(d, ctx);
      const m = T.deckMoney(d, e, ctx);
      const add = T.addMoney(e, 5000);
      const imp = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', cls: 'kr' }, { t: '000020', nk: 'b', cls: 'kr' }],
        purchases: [], imported: [{ t: '000010', nk: 'a', ccy: 'KRW', qty: 10 }, { t: '000020', nk: 'b', ccy: 'KRW', qty: 10 }], sales: [sell('000010', 6, 1000, '2026-10-10')] };
      const st = P.pfState(imp, ctx, stocks);
      const home = Hm.homeBlocks([d], R.evaluateAll([d], ctx), ctx, stocks)[0];
      out = { qty: e.holdings.map((x) => [x.t, x.qty, Math.round(x.w * 1000) / 1000, x.status]), m: { value: m.value, cost: m.cost }, hc: T.heldCost(d, '000010'),
        add: add.buys.map((b) => [b.t, b.shares]), rows: st.view.rows.map((r) => [r.t, r.qty, Math.round(r.w * 1000) / 1000]), home: home.money.gain };""")
    assert got["qty"] == [["000010", 4, 0.286, "low"], ["000020", 10, 0.714, "trim"]]          # 4주 : 10주 → 비중 띠도 그 수량으로 (71% > 50% × 1.4)
    assert got["m"] == {"value": 14000, "cost": 14000} and got["hc"] == 4000
    assert got["add"] == [["000010", 5]]                                                      # 판 뒤 4주 기준으로 모자란 종목만 (일부 팔아요 종목은 건너뜀)
    assert got["rows"] == [["000010", 4, 0.286], ["000020", 10, 0.714]]
    assert got["home"]["cost"] == 14000 and got["home"]["n"] == 2


# ── v19.6a 리뷰 1차 (2026-11-13) ──
def test_a_new_rateless_us_purchase_never_takes_plan_fx_but_an_old_one_still_does():
    """Never another day's rate: a USD purchase saved without fx by v19.6a is marked noFx (dated before 2016) and is left out
    of won totals (noFx); one saved before Part E without fx (no mark) keeps the planFx saved with it, as before."""
    got = run("""const old = built([['AAA', 'A', 1]], { purchases: [buy('AAA', 2, 100, '2026-10-01')] });             // 예전 샀어요: fx 없음, planFx 1,300
      const neu = built([['AAA', 'A', 1]], { purchases: [buy('AAA', 2, 100, '2015-06-01', { noFx: true })] });   // 새 기록: 2016 전, 표시
      const q = { pxOf: () => 110, fx: 1400, absent: new Set() };
      const Lo = L.ledger(old, 'AAA'), Ln = L.ledger(neu, 'AAA');
      const ro = L.returnsOf(old, q), rn = L.returnsOf(neu, q);
      out = { lo: [Lo.lots[0].won, Lo.lots[0].rate, Lo.putIn.noRate], ln: [Ln.lots[0].won, Ln.lots[0].rate, Ln.putIn.noRate],
        ro: [ro.cost, ro.noFx, ro.held], rn: [rn.cost, rn.noFx, rn.n], pw: [T.purchaseWon(old.purchases[0], 1300), T.purchaseWon(neu.purchases[0], 1300)],
        p: [S.deckProblem(neu, '2026-11-06'), S.deckProblem(built([['AAA', 'A', 1]], { purchases: [buy('AAA', 2, 100, '2015-06-01', { noFx: true, fx: 1100 })] }), '2026-11-06'),
          S.deckProblem(built([['000010', 'a', 1]], { purchases: [buy('000010', 2, 100, '2015-06-01', { noFx: true })] }), '2026-11-06')] };""")
    assert got["lo"] == [260000, 1300, False] and got["ro"] == [260000, [], 2 * 110 * 1400 - 260000]   # 예전 기록은 그대로 planFx
    assert got["ln"] == [None, None, True] and got["rn"] == [None, ["AAA"], 0]                 # 새 기록은 원화 합계에서 빠지고 noFx 줄
    assert got["pw"] == [260000, None]
    assert got["p"][0] is None and "noFx" in got["p"][1]["why"] and "noFx" in got["p"][2]["why"]   # 표시는 환율 없는 미국 기록에만


def test_same_date_purchases_come_before_sales_in_the_ledger():
    got = run("""const d = built([['000010', 'a', 1]], { purchases: [buy('000010', 10, 100, '2026-10-01')], sales: [sell('000010', 10, 120, '2026-10-01')] });
      const s = L.ledger(d, '000010').sales[0];
      out = [s.over, s.gain, s.why, H.belowZero(d)];""")
    assert got == [False, 200, None, None]                                                    # 같은 날: 산 것 먼저, 그다음 판 것


def test_split_boundary_a_record_dated_on_the_split_day_is_already_at_the_new_basis():
    got = run("""const sp = [{ t: '000010', date: '2026-09-01', r: 4 }];
      const on = { ...built([['000010', 'a', 1]], { purchases: [buy('000010', 10, 100, '2026-09-01')] }), splits: sp };
      const before = { ...built([['000010', 'a', 1]], { purchases: [buy('000010', 10, 100, '2026-08-31')] }), splits: sp };
      out = { on: H.heldUnits(on).get('000010'), before: H.heldUnits(before).get('000010'), f: [H.splitFactor(H.splitsOf(on), '000010', '2026-09-01'),
        H.splitFactor(H.splitsOf(on), '000010', '2026-08-31')], lines: [L.splitsFor(on, '000010'), L.splitsFor(before, '000010')] };""")
    assert got["on"] == 100000 and got["before"] == 400000 and got["f"] == [1, 4]
    assert got["lines"] == [[], [{"date": "2026-09-01", "r": 4}]]                             # 분할 줄은 기록을 바꾼 분할만


def test_returns_percent_comes_from_the_exact_sums_not_the_rounded_rows():
    got = run("""out = { rr: L.roundRows([15000, 15000, 15000], { exact: false }), pct: L.returnsPct({ held: 15000, sold: 15000, divs: 15000, cost: 100000 }),
      exact: L.roundRows([15000, 15000, 15000], { exact: true }), def: L.roundRows([15000, 15000, 15000]),
      none: L.returnsPct({ held: 1, sold: 0, divs: 0, cost: null }), sw: [L.RETURNS_EXACT, L.RETURNS_PARTIAL] };""")
    assert got["rr"] == {"unit": 10000, "rows": [20000, 20000, 20000], "total": 60000}         # 만원 규칙(꺼진 상태): 화면의 줄은 2만원씩 (합 6만원)
    assert abs(got["pct"] - 45.0) < 1e-12                                                      # 수익률은 45.0%, 60% 가 아니에요
    assert got["exact"] == {"unit": 1, "rows": [15000, 15000, 15000], "total": 45000}          # 스위치 C (정확한 원): 4만 5,000원
    assert got["def"] == got["exact"]                                                          # 기본이 그 상태예요
    assert got["none"] is None and got["sw"] == [True, False]                                 # Jack, 2026-11-13: 늘 정확한 금액 · 종목 통째로


def test_a_fully_sold_stock_without_an_average_price_is_left_out_and_named():
    got = run("""const d = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} },
        holdings: [{ t: '000010', nk: 'a', cls: 'kr' }, { t: '000020', nk: 'b', cls: 'kr' }], purchases: [],
        imported: [{ t: '000010', nk: 'a', ccy: 'KRW', qty: 10 }, { t: '000020', nk: 'b', ccy: 'KRW', qty: 1, avg: 900 }],
        sales: [sell('000010', 10, 1200, '2026-10-10')], divs: [div('000010', 300, '2026-10-12')] };
      const q = { pxOf: () => 1000, fx: 1400, absent: new Set() };
      const all = L.returnsOf(d, q), part = L.returnsOf(d, q, { partial: true });
      out = { all: { ...all, ledgers: undefined }, part: { ...part, ledgers: undefined } };""")
    a = got["all"]
    assert a["noAvg"] == ["000010"] and a["soldOut"] == 1 and a["sold"] == 0 and a["divs"] == 0 and a["held"] == 100 and a["cost"] == 900
    p = got["part"]                                                                           # 스위치 B (알려진 것은 모두): 배당은 세고 수익률은 없음
    assert p["noAvg"] == ["000010"] and p["divs"] == 300 and p["sold"] == 0 and p["held"] == 100 and p["partial"] is True and p["cost"] is None


def test_returns_name_a_held_stock_without_a_price_and_keep_the_rest():
    got = run("""const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], { purchases: [buy('000010', 1, 1000, '2026-10-01'), buy('000020', 1, 1000, '2026-10-01')],
        divs: [div('000020', 50, '2026-10-02')] });
      const r = L.returnsOf(d, { pxOf: (t) => (t === '000010' ? 1100 : null), fx: 1400, absent: new Set() });
      out = { ...r, ledgers: undefined };""")
    assert got["noPrice"] == ["000020"] and got["held"] == 100 and got["divs"] == 0 and got["cost"] == 1000   # 가격 없는 종목만 빠지고 이름이 나와요


def test_sold_out_band_switch_both_states():
    """Round-1 review A, then the final review's S1 (a three-way switch, Jack decides): "off" (v19.3d2) the sold-out holding
    is left out of the bands; "spec" (A.1 to the letter) it is held with 0 shares for everyone's bands, shows below its band
    (먼저 사요) and 추가로 넣을 돈 buys it back, and the stock left reads above its own; "own" (what ships) it reads 먼저 사요 on
    its own band and is bought back, while the stock left keeps the "off" reading. The money totals hold no money for it in
    any state."""
    got = run("""const stocks = [kr('000010', 1000), kr('000020', 1000)];
      const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], { purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('000020', 10, 1000, '2026-10-01')],
        sales: [sell('000020', 10, 1000, '2026-10-10')] });
      const run1 = (on) => { const ctx = { ...ctxOf(stocks), soldOutBands: on }; const e = R.evaluateDeck(d, ctx); const m = T.deckMoney(d, e, ctx);
        return { hs: e.holdings.map((x) => [x.t, x.qty, x.status]), soldOut: e.soldOut, unheld: e.unheld, m: [m.ok, m.value, m.cost],
          add: T.addMoney(e, 10000).buys.map((b) => [b.t, b.shares]) }; };
      out = { off: run1('off'), on: run1('spec'), own: run1('own'), dflt: run1(undefined), def: R.SOLD_OUT_BANDS };""")
    assert got["def"] == "own" and got["dflt"] == got["own"]                                  # 기본은 "own" (Jack 의 답을 기다려요)
    off, on, own = got["off"], got["on"], got["own"]
    assert own["hs"] == [["000010", 10, "none"], ["000020", 0, "low"]] and own["soldOut"] == ["000020"] and own["unheld"] == []
    assert own["m"] == [True, 10000, 10000] and own["add"] == [["000020", 10]]               # 다 판 종목만 다시 사요 (남은 종목은 계획 몫을 이미 채웠어요)
    assert off["hs"] == [["000010", 10, "none"]] and off["soldOut"] == ["000020"] and off["unheld"] == []
    assert on["hs"] == [["000010", 10, "high"], ["000020", 0, "low"]] and on["soldOut"] == ["000020"] and on["unheld"] == []
    assert off["m"] == [True, 10000, 10000] and on["m"] == [True, 10000, 10000]              # 0주 종목은 돈이 없어요
    assert off["add"] == [["000010", 10]] and on["add"] and on["add"][0][0] == "000020"     # 켜면 다시 사는 쪽으로


# ── v19.6a 리뷰 2차 (2026-11-13) ──
def test_the_same_split_dated_a_few_days_apart_applies_once():
    got = run("""const d = { ...built([['000010', 'a', 1]], { purchases: [buy('000010', 1, 1000, '2026-08-01'), buy('000010', 1, 100, '2026-10-01')] }),
        splits: [{ t: '000010', date: '2026-09-01', r: 10 }] };
      const view = L.withDataSplits({ v: 2, decks: [d] }, [{ t: '000010', date: '2026-09-03', r: 10 }], '2026-11-06').decks[0];
      const far = L.withDataSplits({ v: 2, decks: [d] }, [{ t: '000010', date: '2026-09-20', r: 10 }], '2026-11-06').decks[0];
      const other = L.withDataSplits({ v: 2, decks: [d] }, [{ t: '000010', date: '2026-09-03', r: 2 }], '2026-11-06').decks[0];
      out = { near: H.heldUnits(view).get('000010'), far: H.heldUnits(far).get('000010'), other: H.heldUnits(other).get('000010'),
        notStored: L.splitsToStore(view, '000010'), log: L.storedNotInData({ decks: [d] }, [{ t: '000010', date: '2026-09-03', r: 10 }]) };""")
    assert got["near"] == 110000                                                              # 11주 (1 × 10 + 1), 101주가 아니에요
    assert got["far"] == 1010000 and got["other"] == 210000                                   # 10일 넘게 (19일) · 다른 비율은 다른 분할
    assert got["notStored"] is None and got["log"] == []                                      # 같은 분할은 다시 저장하지도, 없다고 말하지도 않아요


def test_rateless_usd_sale_and_dividend_never_take_plan_fx():
    """M10 · M11: a USD sale or dividend without its own rate is not costed at the portfolio's planFx."""
    got = run("""const d = built([['AAA', 'A', 1]], { purchases: [buy('AAA', 2, 100, '2026-10-01', { fx: 1300 })],
        sales: [sell('AAA', 1, 120, '2026-10-02')], divs: [div('AAA', 2, '2026-10-03', { noFx: true }), div('AAA', 3, '2026-10-05')] });   // planFx 1,300 이 있어도
      const Lg = L.ledger(d, 'AAA');
      out = { sale: [Lg.sales[0].proceedsWon, Lg.sales[0].gain, Lg.sales[0].why], divs: Lg.divs.map((x) => x.won) };""")
    assert got["sale"] == [None, None, "noRate"] and got["divs"] == [None, None]


def test_splits_store_needs_a_record_strictly_before_the_split_day():
    """M4: a record dated on the split day is already at the new basis: nothing to store. A dividend dated before the split
    counts while the stock is held."""
    got = run("""const sp = [{ t: 'AAA', date: '2026-09-01', r: 4 }];
      const on = L.withDataSplits({ v: 2, decks: [built([['AAA', 'A', 1]], { purchases: [buy('AAA', 1, 100, '2026-09-01', { fx: 1300 })] })] }, sp, '2026-11-06').decks[0];
      const divHeld = L.withDataSplits({ v: 2, decks: [built([['AAA', 'A', 1]], { purchases: [buy('AAA', 1, 100, '2026-09-01', { fx: 1300 })],
        divs: [div('AAA', 1, '2026-08-20', { fx: 1300 })] })] }, sp, '2026-11-06').decks[0];
      const ws = L.withStoredSplits({ v: 2, decks: [divHeld, on] });
      out = { on: L.splitsToStore(on, 'AAA'), div: L.splitsToStore(divHeld, 'AAA'), added: ws.added, same: L.withStoredSplits({ v: 2, decks: [on] }).data.decks[0] === on };""")
    assert got["on"] is None and got["div"] == [{"t": "AAA", "date": "2026-09-01", "r": 4}]
    assert got["added"] == [{"id": "d", "t": "AAA", "date": "2026-09-01", "r": 4}] and got["same"] is True


def test_fx_card_leaves_out_a_stock_with_any_rateless_lot():
    got = run("""const d = built([['AAA', 'A', 0.5], ['BBB', 'B', 0.5]], { planFx: undefined,
        purchases: [buy('AAA', 1, 100, '2026-10-01', { fx: 1300 }), buy('AAA', 1, 100, '2015-06-01', { noFx: true }), buy('BBB', 1, 100, '2026-10-01', { fx: 1300 })] });
      delete d.planFx;
      const f = L.fxSplit([L.ledger(d, 'AAA'), L.ledger(d, 'BBB')], () => 120, 1400);
      out = { n: f.n, noRate: f.noRate, price: f.price, rate: f.rate };""")
    assert got["n"] == 1 and got["noRate"] == ["AAA"] and got["price"] == 20 * 1300 and got["rate"] == 120 * 100   # AAA 통째로 빠지고 BBB 만


def test_round_rows_rounds_halves_the_same_way_on_both_sides():
    got = run("""out = [L.roundRows([15000, -15000, 25000], { exact: false }), L.roundRows([-0.5, 0.5, 2], { exact: true })];""")
    assert got[0] == {"unit": 10000, "rows": [20000, -20000, 30000], "total": 30000}
    assert got[1]["rows"] == [-1, 1, 2]


def test_sold_out_band_switch_on_with_no_price_today_does_not_stop_the_rest():
    got = run("""const stocks = [kr('000010', 1000), { ...kr('000020', null), price: null }];
      const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], { purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('000020', 10, 1000, '2026-10-01')],
        sales: [sell('000020', 10, 1000, '2026-10-10')] });
      out = ['spec', 'own'].map((mode) => { const ctx = { ...ctxOf(stocks), soldOutBands: mode };
        const e = R.evaluateDeck(d, ctx); const m = T.deckMoney(d, e, ctx);
        return { w: e.weights.ok, hs: e.holdings.map((x) => [x.t, x.qty, x.status]), m: [m.ok, m.value, m.cost] }; });""")
    for x in got:                                                                             # "spec" 도 "own" 도: 가격 없는 0주 종목은 빼고 나머지는 그대로
        assert x["w"] is True and x["hs"] == [["000010", 10, "none"]] and x["m"] == [True, 10000, 10000]


# ── v19.6a 마지막 리뷰 S1 (2026-11-13): 다 팔고 남겨 둔 종목을 읽는 세 가지 방법 ──
SOLD3 = """const CODES = ['000010', '000020', '000030', '000040', '000050', '000060', '000070', '000080', '000090', '000100'];
      // a 1,000만원 plan at 10,000원 a share, bought as planned; then one stock sold out and kept (남겨 두기)
      const mk = (ws, sold) => { const q = (w) => Math.round(w * 1e7 / 10000);
        const d = built(ws.map((w, i) => [CODES[i], 's' + i, w]), { purchases: ws.map((w, i) => buy(CODES[i], q(w), 10000, '2026-10-01')) });
        d.holdings = d.holdings.map((h, i) => ({ ...h, plannedQty: q(ws[i]), planPx: 10000 }));
        return { ...d, sales: [sell(sold, q(ws[CODES.indexOf(sold)]), 10000, '2026-10-10')] }; };
      const view = (d, mode) => { const ctx = { ...ctxOf(d.holdings.map((h) => kr(h.t, 10000))), ...(mode ? { soldOutBands: mode } : {}) };
        const e = R.evaluateDeck(d, ctx), a = T.addMoney(e, 3000000), m = T.deckMoney(d, e, ctx);
        const band = (x) => { const r = x.rules.find((y) => y.id === 'band'); return JSON.stringify([x.status, x.w, x.target, r.target, r.bands, r.gap]); };
        return { st: e.holdings.map((x) => [x.t, x.qty, x.status]), allClear: T.todayCounts([e]).allNone, add: a.buys.map((b) => [b.t, b.shares]), left: a.left,
          rebased: e.rebased, n: [e.bandPlanned, e.bandHeld], soldOut: e.soldOut, money: [m.ok, m.value, m.cost], held: Object.fromEntries(e.holdings.filter((x) => x.qty > 0).map((x) => [x.t, band(x)])),
          zero: e.holdings.filter((x) => x.qty === 0).map((x) => [Math.round(x.target * 1000) / 10, x.w]) }; };
      const CASES = { two: [[0.5, 0.5], '000020'], three: [[1 / 3, 1 / 3, 1 / 3], '000030'], five: [[0.3, 0.25, 0.2, 0.15, 0.1], '000010'],
        four: [[0.25, 0.25, 0.25, 0.25], '000010'], ten: [Array(10).fill(0.1), '000010'] };
"""


def test_a_sold_out_kept_holding_read_three_ways_on_five_portfolios():
    """Final review S1. One stock sold down to 0 and kept, in five portfolios (2 equal · 3 equal · 30/25/20/15/10 with the 30%
    one sold · 4 equal · 10 equal), under each value of rules.SOLD_OUT_BANDS:
    - "off" (live before v19.6a): the sold-out stock has no status, the others read over what is held (할 일 없음), 홈 says all clear;
    - "spec" (A.1 to the letter): it reads 먼저 사요, but the others read above bands taken over the whole plan: 더 안 사요 with
      2 or 4 stocks, 일부 팔아요 with 3 equal and with 30/25/20/15/10 (all four). Only with 10 equal stocks is nobody else touched;
    - "own" (the default): it reads 먼저 사요 on its own band over the whole plan (30% → target 30%, weight 0), and every other
      holding reads exactly what "off" reads (the same status, weight, target and edges, digit for digit), in all five.
    홈's all-clear (todayCounts) leaves the 0-share holding out (verification nit: 홈 lists only the stocks held, so its
    먼저 사요 shows on 포트폴리오 only): it stays on under "own" in all five, and under "spec" only where nobody else got a new
    word (10 equal). 추가로 넣을 돈 300만원 in the 3-stock case: "off" 150주 + 150주 of the two held; "spec" and "own" 300주 of
    the sold-out stock and nothing else."""
    got = run(SOLD3 + """out = { def: R.SOLD_OUT_BANDS };
      for (const [k, [ws, sold]] of Object.entries(CASES)) { const d = mk(ws, sold); out[k] = { off: view(d, 'off'), spec: view(d, 'spec'), own: view(d, 'own'), dflt: view(d, null) }; }""")
    assert got["def"] == "own"
    sold = {"two": "000020", "three": "000030", "five": "000010", "four": "000010", "ten": "000010"}
    spec_others = {"two": "high", "three": "trim", "five": "trim", "four": "high", "ten": "none"}   # "spec" 이 남은 종목에 붙이는 말
    zero_target = {"two": 50, "three": 33.3, "five": 30, "four": 25, "ten": 10}
    for k, t in sold.items():
        c = got[k]
        off, spec, own = c["off"], c["spec"], c["own"]
        assert c["dflt"] == own, k                                                            # 기본 = "own"
        n = len(off["st"])
        # "off": 다 판 종목은 줄이 없고, 남은 종목은 모두 할 일 없음 · 홈은 '오늘은 할 일이 없어요'
        assert all(x[0] != t and x[2] == "none" and x[1] > 0 for x in off["st"]) and off["allClear"] is True, (k, off["st"])
        assert off["soldOut"] == [t] and off["rebased"] is False and off["n"] == [n, n] and off["zero"] == []
        # "spec": 다 판 종목 먼저 사요, 남은 종목은 계획 전체 기준의 선 위 (10종목일 때만 그대로)
        assert [x[2] for x in spec["st"] if x[0] == t] == ["low"] and {x[2] for x in spec["st"] if x[0] != t} == {spec_others[k]}, (k, spec["st"])
        assert spec["allClear"] is (k == "ten") and spec["n"] == [n + 1, n + 1] and spec["rebased"] is False
        # "own": 다 판 종목 먼저 사요 (제 목표 그대로, 비중 0), 남은 종목은 "off" 와 한 글자도 다르지 않아요
        assert [x[2] for x in own["st"] if x[0] == t] == ["low"] and all(x[2] == "none" for x in own["st"] if x[0] != t), (k, own["st"])
        assert own["held"] == off["held"], k
        assert own["zero"] == [[zero_target[k], 0]] and spec["zero"] == own["zero"], (k, own["zero"])
        assert own["allClear"] is True and own["n"] == [n, n] and own["rebased"] is False and own["soldOut"] == [t]   # 홈은 '오늘은 할 일이 없어요' 그대로
        assert off["money"] == spec["money"] == own["money"] and off["money"][0] is True     # 0주 종목은 돈이 없어요: 세 값 모두 같은 금액
    # 추가로 넣을 돈 300만원, 세 종목
    three = got["three"]
    assert three["off"]["add"] == [["000010", 150], ["000020", 150]] and three["off"]["left"] == 0
    assert three["spec"]["add"] == [["000030", 300]] and three["own"]["add"] == [["000030", 300]] and three["own"]["left"] == 0
    # 네 종목: "spec" 은 남은 종목이 더 안 사요라 50만원이 남고, "own" 은 계획대로 (다 판 종목 263주, 나머지 13 · 12 · 12주)
    four = got["four"]
    assert four["spec"]["add"] == [["000010", 250]] and four["spec"]["left"] == 500000
    assert four["own"]["add"] == [["000010", 263], ["000020", 13], ["000030", 12], ["000040", 12]] and four["own"]["left"] == 0
    # 열 종목: 누구에게도 새 말이 붙지 않으면 "spec" 과 "own" 이 같은 것을 사요
    assert got["ten"]["spec"]["add"] == got["ten"]["own"]["add"] == [["000010", 120]] + [[c, 20] for c in ["000020", "000030", "000040", "000050", "000060", "000070", "000080", "000090", "000100"]]


# ── v19.6a 검증 (2026-11-13): 다 판 종목은 비중 규칙으로만 읽어요 (B1 · S-a · 홈 · 오늘 · 큰 움직임) ──
CUT3 = """const cut3 = () => { const d = mk([1 / 3, 1 / 3, 1 / 3], '000030');
        // every holding also has a rule this version cannot read (준비 중); the sold-out one had a dividend cut the user confirmed
        d.holdings = d.holdings.map((h) => ({ ...h, rules: [{ id: 'audit', kind: 'sell', check: 'pending' },
          ...(h.t === '000030' ? [{ id: 'divCut', kind: 'sell', check: 'checked', since: 2023 }] : []), ...h.rules] }));
        return { ...d, confirms: [{ t: '000030', rule: 'divCut', fy: 2025, a: 1000, b: 800, answer: 'cut' }] }; };
"""


def test_a_sold_out_holding_after_a_confirmed_cut_is_never_bought_back():
    """Verification B1, then the coordinator (2026-11-13): never tell the user to buy back a stock that fails its own rules.
    Three stocks at a third each; the third is sold out and kept after a dividend cut the user confirmed. Before: under "own"
    and "spec" it read 규칙 깨짐 (홈's band said "…이 매도 조건에 걸렸어요 / 규칙대로면 팔 때예요" for 0 shares) and 추가로 넣을 돈
    300만원 bought nothing. Now a 0-share holding's other rules are read only to see whether one fails: this one does, so
    there is no 먼저 사요 and no target, no status of its own (no action chip; Jack 2026-11-14: never blank, so its failing
    rule is its one rule row and reason, the confirmed cut, with soldOutFails), nothing is for 오늘 확인할 일, its 준비 중 rule
    is not counted, and 추가로 넣을 돈 buys exactly what "off" buys (150주 + 150주). "spec" reads it the same way
    (its held stocks read 일부 팔아요 there, so nothing is bought). The same portfolio without the cut: it reads 먼저 사요 on its
    band and 300만원 buys it back (300주)."""
    got = run(SOLD3 + CUT3 + """const look = (d) => { const o = {};
        for (const mode of ['off', 'spec', 'own', null]) { const ctx = { ...ctxOf(d.holdings.map((h) => kr(h.t, 10000))), ...(mode ? { soldOutBands: mode } : {}) };
          const e = R.evaluateDeck(d, ctx), a = T.addMoney(e, 3000000), c = T.todayCounts([e]);
          o[mode || 'dflt'] = { st: e.holdings.map((x) => [x.t, x.qty, x.status]), todo: e.todo, nc: e.notChecked, ncIds: e.notCheckedIds,
            todoTs: [...c.todoTs], allNone: c.allNone, add: a.buys.map((b) => [b.t, b.shares]), msg: T.addMessage(a, 3000000), zeroOwn: e.zeroOwn || [],
            zero: e.holdings.filter((x) => x.qty === 0).map((x) => ({ rules: x.rules.map((r) => r.id), reasons: x.reasons.map((r) => r.code), drops: x.divDrops,
              noNew: x.noNewMoney, target: x.target, broken: x.soldOutFails })) }; }
        return o; };
      const d = cut3();
      out = { cut: look(d), fine: look({ ...d, confirms: [] }) };""")
    cut, fine = got["cut"], got["fine"]
    assert cut["dflt"] == cut["own"] and fine["dflt"] == fine["own"]
    off, spec, own = cut["off"], cut["spec"], cut["own"]
    assert off["st"] == [["000010", 333, "none"], ["000020", 333, "none"]] and off["add"] == [["000010", 150], ["000020", 150]]
    assert own["st"] == [["000010", 333, "none"], ["000020", 333, "none"], ["000030", 0, "none"]]           # 규칙 깨짐도 먼저 사요도 아니에요
    assert spec["st"] == [["000010", 333, "trim"], ["000020", 333, "trim"], ["000030", 0, "none"]]
    for x in (spec, own):
        assert x["zero"] == [{"rules": ["divCut"], "reasons": ["divCut"], "drops": [{"t": "000030", "rule": "divCut", "fy": 2025, "a": 1000, "b": 800, "answer": "cut"}],
                              "noNew": True, "target": None, "broken": True}]                      # 어긋난 규칙 하나만 보여요 (Jack 11-14)
        assert x["todo"] == 0 and x["todoTs"] == []                                                       # 홈 띠의 '매도 조건에 걸렸어요' 는 없어요
        assert x["nc"] == off["nc"] == 2 and x["ncIds"] == ["audit"]                                       # 0주 종목의 준비 중 규칙은 세지 않아요
    assert own["add"] == off["add"] and own["msg"] is None and own["allNone"] is True                    # 다시 사지 않아요: "off" 와 똑같이 150주 + 150주
    assert spec["add"] == [] and spec["msg"] == "noneEligible"                                           # "spec": 남은 둘이 일부 팔아요라 아무것도
    # 같은 포트폴리오, 배당을 줄이지 않았으면: 먼저 사요, 300만원으로 다시 사요
    assert fine["own"]["st"][2] == ["000030", 0, "low"] and fine["own"]["add"] == [["000030", 300]] and fine["own"]["zeroOwn"] == ["000030"]
    assert fine["own"]["zero"] == [{"rules": ["band"], "reasons": ["band"], "drops": [], "noNew": False, "target": 1 / 3, "broken": False}]
    assert fine["spec"]["st"][2] == ["000030", 0, "low"] and fine["spec"]["add"] == [["000030", 300]]


def test_every_holding_sold_out_and_kept_reads_as_off():
    """Verification S-a. Both stocks sold out and kept: "own" and "spec" used to read each 확인 필요 ("가격 자료를 받지 못해 확인이
    필요해요": a weight over nothing held) and 홈 listed them in 오늘 확인할 일. With nothing held, they read exactly as "off":
    no row, no status, the approved sold-out line on 포트폴리오."""
    got = run(SOLD3 + """const d0 = mk([0.5, 0.5], '000020'); const d = { ...d0, sales: [...d0.sales, sell('000010', 500, 10000, '2026-10-11')] };
      const ctx = ctxOf(d.holdings.map((h) => kr(h.t, 10000)));
      out = Object.fromEntries(['off', 'spec', 'own'].map((m) => { const e = R.evaluateDeck(d, { ...ctx, soldOutBands: m });
        return [m, { e, c: T.todayCounts([e]), day: T.deckDayChange(e), add: T.addMoney(e, 3000000) }]; }));""")
    off = got["off"]
    assert off["e"]["holdings"] == [] and off["e"]["soldOut"] == ["000010", "000020"] and off["e"]["todo"] == 0
    for m in ("spec", "own"):
        assert got[m]["e"] == off["e"], m                                                                 # "off" 와 한 글자도 다르지 않아요
        assert got[m]["c"]["todoTs"] == {} and got[m]["day"] is None and got[m]["add"] == {"ok": False}


def test_a_zero_share_holding_never_blanks_today_and_is_never_a_big_move():
    """Verification nits. The sold-out holding (0 shares) is left out of the portfolio's 오늘 change (a US one, or one without a
    change today, used to blank it) and is never a 큰 움직임 (not in de.bigMoves, no bigMove flag), under every switch value."""
    got = run(SOLD3 + """const d = mk([1 / 3, 1 / 3, 1 / 3], '000030'); const base = d.holdings.map((h) => kr(h.t, 10000, { d1: 1 }));
      const cases = { none: base.map((s) => (s.t === '000030' ? { ...s, d1: null } : s)), big: base.map((s) => (s.t === '000030' ? { ...s, d1: 12 } : s)),
        us: base.map((s) => (s.t === '000030' ? { ...s, cls: 'us' } : s)) };
      out = Object.fromEntries(Object.entries(cases).map(([k, stocks]) => [k, Object.fromEntries(['off', 'spec', 'own'].map((m) => {
        const e = R.evaluateDeck(k === 'us' ? { ...d, holdings: d.holdings.map((h) => (h.t === '000030' ? { ...h, cls: 'us' } : h)) } : d, { ...ctxOf(stocks), soldOutBands: m });
        return [m, { day: T.deckDayChange(e), big: e.bigMoves, flags: e.holdings.map((x) => x.bigMove), n: e.holdings.length }]; }))]));""")
    for k, c in got.items():
        assert c["spec"]["n"] == c["own"]["n"] == 3 and c["off"]["n"] == 2, k                              # the sold-out row is there
        for m in ("off", "spec", "own"):
            assert c[m]["day"] is not None and abs(c[m]["day"] - 1) < 1e-9, (k, m, c[m]["day"])           # 오늘 +1.0% 그대로
            assert c[m]["big"] == [] and not any(c[m]["flags"]), (k, m)                                     # 큰 움직임에 없어요


def test_sold_out_switch_fuzz_own_reads_only_its_band_and_never_buys_nothing_where_off_buys():
    """Verification B1, fuzz (the verifier's q1, 1,500 portfolios, fixed seed): under "own" a sold-out holding reads 먼저 사요 or
    할 일 없음 only (never 규칙 깨짐, 확인 필요, 지켜봐요, 일부 팔아요, 더 안 사요), every held stock reads byte for byte as under
    "off", "아직 자동으로 확인하지 못하는 규칙" counts the same, and 추가로 넣을 돈 (30만 · 300만 · 3,000만원) never buys nothing
    where "off" buys something. Under "spec" too the sold-out holding reads only 먼저 사요 or 할 일 없음. A sold-out holding that
    fails any of its own rules (its other rules read as if held: 규칙 깨짐, 지켜봐요 or 확인 필요) never reads 먼저 사요 and is
    never bought; when every sold-out holding of a portfolio is such a one, 추가로 넣을 돈 buys exactly what "off" buys."""
    got = run("""const CODES = ['000010', '000020', '000030', '000040', '000050', '000060', '000070', '000080', '000090', '000100'];
      let seed = 12345; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
      const pick = (a) => a[Math.floor(rnd() * a.length)];
      const st = { decks: 0, sold: 0, own: {}, spec: {}, heldDiff: 0, ncDiff: 0, nothing: 0, adds: 0, bad: [], brokenSold: 0, brokenLow: 0, brokenBought: 0, brokenNotOff: 0, failLevels: {} };
      for (let it = 0; it < 1500; it++) {
        const n = 2 + Math.floor(rnd() * 7), A = pick([300, 500, 1000, 3000]) * 10000, planFx = 1300;
        let ws = Array.from({ length: n }, () => 0.05 + rnd()); const sw = ws.reduce((a, b) => a + b, 0); ws = ws.map((w) => Math.round(w / sw * 100) / 100);
        ws[n - 1] = Math.max(0.01, +(1 - ws.slice(0, n - 1).reduce((a, b) => a + b, 0)).toFixed(4));
        const hs = [], ps = [], ss = [], stocks = [];
        for (let i = 0; i < n; i++) {
          const t = CODES[i], isUs = rnd() < 0.2, px = isUs ? pick([5, 40, 150, 600]) : pick([500, 3000, 25000, 100000, 700000, 1500000]);
          const q = Math.round(ws[i] * A / (px * (isUs ? planFx : 1)));
          const rules = [{ id: 'audit', kind: 'sell', check: 'pending' }, ...band(ws[i])];
          if (rnd() < 0.15) rules.unshift({ id: 'debtCeiling', kind: 'keep', check: 'checked', since: 2024, limit: 100 });
          if (rnd() < 0.15) rules.unshift({ id: 'divCut', kind: 'sell', check: 'checked', since: 2023 });
          hs.push({ t, nk: 's' + i, cls: isUs ? 'us' : 'kr', target: ws[i], plannedQty: q, planPx: px, rules });
          const mode = rnd(); let bq = q, sq = 0;
          if (mode < 0.12) bq = 0; else if (mode < 0.3) { bq = q; sq = q; } else if (mode < 0.45) bq = Math.max(1, Math.round(q * (0.3 + rnd()))); else if (mode < 0.5) { bq = q; sq = Math.floor(q * rnd()); }
          if (bq > 0) ps.push(buy(t, bq, px, '2026-10-01', isUs ? { fx: planFx } : {}));
          if (bq > 0 && sq > 0) ss.push(sell(t, sq, px, '2026-11-01', isUs ? { fx: 1350 } : {}));
          const r = rnd(); if (r < 0.04) continue;                                              // missing from today's data
          const p2 = r < 0.07 ? null : +(px * (0.5 + rnd() * 1.5)).toFixed(isUs ? 2 : 0);
          stocks.push({ ...(isUs ? us(t, p2) : kr(t, p2)), d1: rnd() < 0.1 ? null : +(rnd() * 20 - 10).toFixed(2), debt: rnd() < 0.5 ? 150 : 50, fy: 2025 });
        }
        const confirms = hs.filter(() => rnd() < 0.3).map((h) => ({ t: h.t, rule: 'divCut', fy: 2025, a: 1000, b: 800, answer: rnd() < 0.5 ? 'cut' : null }));
        const deck = { ...built([]), planFx, holdings: hs, purchases: ps, sales: ss, confirms };
        const ctx = ctxOf(stocks);
        const ef = R.evaluateDeck(deck, { ...ctx, soldOutBands: 'off' }), eo = R.evaluateDeck(deck, { ...ctx, soldOutBands: 'own' }), es = R.evaluateDeck(deck, { ...ctx, soldOutBands: 'spec' });
        st.decks++;
        if ((eo.zeroOwn || []).length) st.sold++;
        for (const [k, e] of [['own', eo], ['spec', es]]) for (const y of e.holdings) if (y.qty === 0) st[k][y.status] = (st[k][y.status] || 0) + 1;
        // a sold-out holding that fails any of its own rules (its other rules read as if held: 규칙 깨짐, 지켜봐요 or 확인 필요,
        // the levels that stop new money) never reads 먼저 사요 and is never bought
        const fails = (t) => { const h = hs.find((x) => x.t === t);
          const x = R.evaluateHolding({ ...h, rules: h.rules.filter((r) => r.id !== 'band') }, deck, ctx, { ok: false, missing: [] }, 1);
          const lv = x.reasons.filter((r) => r.code !== 'noRules').map((r) => r.level);
          for (const l of new Set(lv)) if (['broken', 'check', 'watch'].includes(l)) st.failLevels[l] = (st.failLevels[l] || 0) + 1;
          return lv.some((l) => ['broken', 'check', 'watch'].includes(l)); };
        const broken = eo.holdings.filter((y) => y.qty === 0 && fails(y.t)).map((y) => y.t);
        st.brokenSold += broken.length;
        for (const t of broken) { const y = eo.holdings.find((z) => z.t === t);
          // Jack 11-14: never blank: its failing rules are its rows and reasons, no status, no target, no new money
          if (y.status !== 'none' || y.soldOutFails !== true || y.target != null || !y.noNewMoney || !y.reasons.length
            || !y.reasons.every((r) => ['broken', 'check', 'watch'].includes(r.level)) || y.rules.length !== new Set(y.reasons.map((r) => r.rule)).size) st.brokenLow++; }
        for (const y of eo.holdings) if (y.qty === 0 && !broken.includes(y.t) && y.soldOutFails !== false) st.brokenLow++;
        for (const x of ef.holdings) { const y = eo.holdings.find((z) => z.t === x.t); if (!y || JSON.stringify(x) !== JSON.stringify(y)) st.heldDiff++; }
        if (eo.notChecked !== ef.notChecked) st.ncDiff++;
        if (!(eo.zeroOwn || []).length) continue;
        for (const amt of [300000, 3000000, 30000000]) {
          const ao = T.addMoney(eo, amt), af = T.addMoney(ef, amt); st.adds++;
          if (ao.ok && af.ok && !ao.buys.length && af.buys.length) st.nothing++;
          if (ao.ok && ao.buys.some((b) => broken.includes(b.t))) st.brokenBought++;
          if (ao.ok && af.ok && broken.length && (eo.zeroOwn || []).every((t) => broken.includes(t)) && JSON.stringify(ao.buys) !== JSON.stringify(af.buys)) st.brokenNotOff++;
          if (ao.ok && (!(ao.spent <= amt) || ao.left < 0 || ao.buys.some((b) => !Number.isInteger(b.shares) || b.shares <= 0))) st.bad.push(it);
        }
      }
      out = st;""")
    assert got["decks"] == 1500 and got["sold"] > 600 and got["adds"] > 1800, got                           # enough sold-out cases
    assert set(got["own"]) <= {"low", "none"} and got["own"].get("low", 0) > 600, got["own"]                # 먼저 사요 · 할 일 없음뿐
    assert set(got["spec"]) <= {"low", "none"}, got["spec"]
    assert got["heldDiff"] == 0 and got["ncDiff"] == 0 and got["nothing"] == 0 and got["bad"] == [], got
    # 자기 규칙이 깨진 다 판 종목: 먼저 사요도, 사는 일도 없어요 (그런 종목만 남았으면 "off" 와 똑같이 사요)
    assert got["brokenSold"] >= 80 and got["brokenLow"] == 0 and got["brokenBought"] == 0 and got["brokenNotOff"] == 0, got
    assert all(got["failLevels"].get(k, 0) >= 10 for k in ("broken", "check", "watch")), got["failLevels"]      # 세 단계 모두 나와요


def test_own_add_money_buys_the_sold_out_stock_back_or_else_exactly_what_off_buys():
    """Verification B1, 추가로 넣을 돈 under "own": the plan's goals are used only when they buy a sold-out holding back. The
    sold-out stock costs 150만원 a share: with 30만원 it cannot be bought, so the money goes exactly where "off" puts it (15주 +
    15주 of the two held, never nothing); with 300만원 it is bought back (2주)."""
    got = run(SOLD3 + """const d0 = mk([1 / 3, 1 / 3, 1 / 3], '000030'); const q = Math.round(1e7 / 3 / 1500000);
      const d = { ...d0, holdings: d0.holdings.map((h) => (h.t === '000030' ? { ...h, plannedQty: q, planPx: 1500000 } : h)),
        purchases: d0.purchases.map((p) => (p.t === '000030' ? { ...p, qty: q, price: 1500000 } : p)), sales: [sell('000030', q, 1500000, '2026-10-10')] };
      const stocks = [kr('000010', 10000), kr('000020', 10000), kr('000030', 1500000)];
      out = Object.fromEntries(['off', 'own'].map((m) => { const e = R.evaluateDeck(d, { ...ctxOf(stocks), soldOutBands: m });
        const a = (x) => { const r = T.addMoney(e, x); return { buys: r.buys.map((b) => [b.t, b.shares]), left: r.left }; };
        return [m, { st: e.holdings.map((x) => [x.t, x.status]), a30: a(300000), a300: a(3000000) }]; }));""")
    off, own = got["off"], got["own"]
    assert own["st"] == [["000010", "none"], ["000020", "none"], ["000030", "low"]]
    assert off["a30"] == own["a30"] == {"buys": [["000010", 15], ["000020", 15]], "left": 0}              # 다시 살 수 없으면 "off" 그대로
    assert own["a300"] == {"buys": [["000030", 2]], "left": 0} and off["a300"]["buys"] == [["000010", 150], ["000020", 150]]


# ── v19.6a 리뷰 (2026-11-13) B1: 자기 규칙 중 하나라도 어긋난 다 판 종목은 다시 사라고 하지 않아요 (깨짐 · 지켜봐요 · 확인 필요) ──
FAIL3 = """const DEBT = { id: 'debtCeiling', kind: 'keep', check: 'checked', since: 2024, limit: 200 };
      const ROE = { id: 'roeFloor', kind: 'keep', check: 'checked', since: 2024, floor: 8 };
      const DIV = { id: 'divCut', kind: 'sell', check: 'checked', since: 2023 };
      // three stocks at a third each, the third sold out and kept, with one more rule of its own and today's figures for it
      const fail3 = (rule, more, ctxMore = {}) => { const d0 = mk([1 / 3, 1 / 3, 1 / 3], '000030');
        const d = { ...d0, holdings: d0.holdings.map((h) => (h.t === '000030' ? { ...h, rules: [rule, ...h.rules] } : h)) };
        const stocks = d.holdings.map((h) => kr(h.t, 10000, { fy: 2025, debt: 100, roe: 10, dps3: [1000, 1000, 1000], ...(h.t === '000030' ? more : {}) }));
        return Object.fromEntries(['off', 'own'].map((m) => { const ctx = { ...ctxOf(stocks), soldOutBands: m, ...ctxMore }; const e = R.evaluateDeck(d, ctx);
          const z = e.holdings.find((x) => x.qty === 0);
          return [m, { st: e.holdings.map((x) => [x.t, x.status]), fails: z ? z.soldOutFails : null, zeroRules: z ? z.rules.map((r) => r.id) : null,
            zeroReasons: z ? z.reasons.map((r) => r.code + ':' + r.level) : null, chips: z ? z.status : null, todo: e.todo,
            add: T.addMoney(e, 3000000).buys.map((b) => [b.t, b.shares]) }]; })); };
"""


def test_a_sold_out_holding_failing_any_of_its_rules_is_never_bought_back():
    """Review B1 (2026-11-13): the guard covers every level that stops new money for a held stock, not only 규칙 깨짐. The
    sold-out third stock with 부채비율 300% over its 200% ceiling (지켜봐요), ROE 2% under its 8% floor (지켜봐요), no 부채비율
    today (확인 필요) or an unanswered dividend drop with the Korean trend switch on (확인 필요): each reads 할 일 없음 with
    nothing shown, nothing goes to 오늘 확인할 일, and 300만원 buys 150주 + 150주 of the two held, as "off". With every rule
    passing it reads 먼저 사요 and is bought back (300주). With the trend switch off a Korean dividend drop is not read at all
    (준비 중), for a held stock as for this one, so it does not stop the buy-back either: the same levels as for a held stock.
    Jack, 2026-11-14: never blank: the failing rule is its rule row and reason (the wording a held stock gets), with no status
    of its own (no action chip)."""
    got = run(SOLD3 + FAIL3 + """out = { debt: fail3(DEBT, { debt: 300 }), roe: fail3(ROE, { roe: 2 }), noDebt: fail3(DEBT, { debt: null }),
        divOn: fail3(DIV, { dps3: [800, 1000, 1000] }, { krDivTrend: true }), divOff: fail3(DIV, { dps3: [800, 1000, 1000] }, { krDivTrend: false }),
        ok: fail3(DEBT, { debt: 150 }) };""")
    held = [["000010", 150], ["000020", 150]]
    rows = {"debt": (["debtCeiling"], ["debtOver:watch"]), "roe": (["roeFloor"], ["roeUnder:watch"]), "noDebt": (["debtCeiling"], ["missing:check"]),
            "divOn": (["divCut"], ["divDrop:check"])}
    for k in ("debt", "roe", "noDebt", "divOn"):
        own, off = got[k]["own"], got[k]["off"]
        assert own["st"] == [["000010", "none"], ["000020", "none"], ["000030", "none"]] and own["fails"] is True, (k, own)
        assert (own["zeroRules"], own["zeroReasons"]) == rows[k], (k, own)                      # 어긋난 규칙 줄만 (Jack 11-14), 상태 칩은 없어요
        assert own["todo"] == 0 and own["add"] == off["add"] == held, (k, own, off)                    # 다시 사지 않아요: "off" 와 똑같이
    for k in ("ok", "divOff"):
        own = got[k]["own"]
        assert own["st"][2] == ["000030", "low"] and own["fails"] is False and own["add"] == [["000030", 300]], (k, own)   # 규칙이 다 지켜지면 다시 사요


def test_two_sold_out_stocks_one_failing_its_rules_the_plan_goals_leave_it_out():
    """Review N3 (track.js planSum): with two stocks sold out and kept, one failing its own rules (no target) and one fine, the
    plan's goals are shared over the stocks that have a target only (the failing one is not in the sum): four equal stocks,
    C fine and D over its 부채비율 ceiling; 300만원 buys C back first and tops up A and B."""
    got = run(SOLD3 + FAIL3 + """const d0 = mk([0.25, 0.25, 0.25, 0.25], '000030'); const q = d0.purchases.find((p) => p.t === '000040').qty;
      const d = { ...d0, holdings: d0.holdings.map((h) => (h.t === '000040' ? { ...h, rules: [DEBT, ...h.rules] } : h)), sales: [...d0.sales, sell('000040', q, 10000, '2026-10-11')] };
      const stocks = d.holdings.map((h) => kr(h.t, 10000, { fy: 2025, debt: h.t === '000040' ? 300 : 100 }));
      const e = R.evaluateDeck(d, { ...ctxOf(stocks), soldOutBands: 'own' });
      out = { st: e.holdings.map((x) => [x.t, x.qty, x.status, x.target == null ? null : Math.round(x.target * 1000) / 1000]), zeroOwn: e.zeroOwn,
        add: T.addMoney(e, 3000000).buys.map((b) => [b.t, b.shares]) };""")
    assert got["st"] == [["000010", 250, "none", 0.5], ["000020", 250, "none", 0.5], ["000030", 0, "low", 0.25], ["000040", 0, "none", None]], got["st"]
    assert got["zeroOwn"] == ["000030", "000040"]
    assert got["add"] == [["000030", 242], ["000010", 17], ["000020", 17]], got["add"]      # 목표의 합에 D 는 없어요 (있으면 C 125주뿐)



def test_a_sold_out_stock_not_bought_back_shows_the_rules_it_fails():
    """Jack, 2026-11-14: a sold-out stock that is not suggested for buy-back still shows which of its rules it fails (never
    blank). The confirmed cut, 부채비율 over its ceiling and a missing 부채비율 each give the sold-out third stock exactly that
    rule as its rule row and its reason, in the wording a held stock gets for it (the screens show them with the "다 판
    종목이에요. …" line), no status of its own (no action chip), nothing for 홈 (todayCounts) and no new money: 300만원 buys
    150주 + 150주 as "off". A passing sold-out stock is unchanged: 먼저 사요 on its band, 300주 bought back."""
    got = run(SOLD3 + FAIL3 + CUT3 + """const look = (d, stocks) => { const ctx = { ...ctxOf(stocks), soldOutBands: 'own' }, e = R.evaluateDeck(d, ctx), z = e.holdings.find((x) => x.qty === 0);
        return { st: z.status, rules: z.rules.map((r) => r.id + ':' + r.result), reasons: z.reasons.map((r) => r.code + ':' + r.level), noNew: z.noNewMoney,
          todo: T.todayCounts([e]).todoTs.size, allNone: T.todayCounts([e]).allNone, add: T.addMoney(e, 3000000).buys.map((b) => [b.t, b.shares]) }; };
      const base = (more) => ['000010', '000020', '000030'].map((t) => kr(t, 10000, { fy: 2025, debt: 100, roe: 10, dps3: [1000, 1000, 1000], ...(t === '000030' ? more : {}) }));
      const withRule = (rule) => { const d0 = mk([1 / 3, 1 / 3, 1 / 3], '000030'); return { ...d0, holdings: d0.holdings.map((h) => (h.t === '000030' ? { ...h, rules: [rule, ...h.rules] } : h)) }; };
      out = { cut: look(cut3(), base({})), debt: look(withRule(DEBT), base({ debt: 300 })), missing: look(withRule(DEBT), base({ debt: null })), fine: look(withRule(DEBT), base({ debt: 150 })) };""")
    want = {"cut": (["divCut:broken"], ["divCut:broken"]), "debt": (["debtCeiling:fail"], ["debtOver:watch"]), "missing": (["debtCeiling:missing"], ["missing:check"])}
    for k, (rules, reasons) in want.items():
        x = got[k]
        assert x["st"] == "none" and x["rules"] == rules and x["reasons"] == reasons and x["noNew"] is True, (k, x)
        assert x["todo"] == 0 and x["allNone"] is True and x["add"] == [["000010", 150], ["000020", 150]], (k, x)
    fine = got["fine"]
    assert fine["st"] == "low" and fine["rules"] == ["band:band"] and fine["reasons"] == ["band:low"] and fine["add"] == [["000030", 300]], fine


def test_a_rule_failing_sold_out_stock_shows_its_rules_when_its_weights_cannot_be_read():
    """Final review S2 (Jack, 2026-11-14: never blank). When a sold-out kept holding cannot be read with 0 shares today (a:
    every holding sold out and kept; b: a held stock has no price), one that fails its own rules (a confirmed dividend cut)
    still shows its failing rule as its rule row and reason, with no status, no target and no new money, and nothing on 홈
    (the portfolio is not among 홈's blocks when nothing is held). One that fails nothing still reads as under "off" (no row)."""
    got = run(SOLD3 + CUT3 + """const d0 = cut3();
      const all = { ...d0, sales: [...d0.sales, sell('000010', 333, 10000, '2026-10-11'), sell('000020', 333, 10000, '2026-10-11')] };
      const peek = (d, prices) => { const stocks = d.holdings.map((h) => kr(h.t, prices[h.t] ?? 10000)), ctx = ctxOf(stocks);
        const ev = R.evaluateAll([d], ctx), e = ev.decks[0], z = e.holdings.find((x) => x.qty === 0) || null;
        return { rows: e.holdings.map((x) => [x.t, x.qty, x.status]), zeroOwn: e.zeroOwn || [], zero: z && { rules: z.rules.map((r) => r.id + ':' + r.result),
          reasons: z.reasons.map((r) => r.code + ':' + r.level), fails: z.soldOutFails, target: z.target, noNew: z.noNewMoney },
          todo: T.todayCounts([e]).todoTs.size, home: Hm.heldDecks([d], ev).length, add: T.addMoney(e, 3000000).ok }; };
      out = { a: peek(all, {}), b: peek(d0, { '000010': 0 }), aFine: peek({ ...all, confirms: [] }, {}), bFine: peek({ ...d0, confirms: [] }, { '000010': 0 }) };""")
    cut = {"rules": ["divCut:broken"], "reasons": ["divCut:broken"], "fails": True, "target": None, "noNew": True}
    a, b = got["a"], got["b"]
    assert a["rows"] == [["000030", 0, "none"]] and a["zeroOwn"] == [] and a["zero"] == cut, a          # 다 팔아도 배당 삭감 줄은 보여요
    assert a["todo"] == 0 and a["home"] == 0 and a["add"] is False, a                                   # 홈에는 아무것도 없어요
    assert b["rows"][2] == ["000030", 0, "none"] and b["zeroOwn"] == [] and b["zero"] == cut, b
    assert b["todo"] == 2 and b["add"] is False, b                                                      # 가격 없는 종목: 늘 하던 대로 (확인 필요는 가진 두 종목만)
    assert got["aFine"]["rows"] == [] and got["bFine"]["zero"] is None                                  # 어긋난 규칙이 없으면 "off" 처럼 (줄 없음)
