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
      const big = L.roundRows([843217, 380000, -52000]);
      const zero = L.roundRows([0, 0, 0]);
      out = { r: { ...r, ledgers: undefined }, rr, big, zero };""")
    r = got["r"]
    assert r["held"] == 5 * 100 + (2 * 110 * 1400 - 2 * 100 * 1300) and r["sold"] == 5 * 200 and r["divs"] == 300 + 1.5 * 1350
    assert r["cost"] == 10000 + 2 * 100 * 1300 and r["n"] == 2 and r["noAvg"] == [] and r["noFx"] == []
    rr = got["rr"]
    assert rr["unit"] == 1 and rr["total"] == sum(rr["rows"])                                  # 1만원 아래 줄이 있으면 원 단위
    assert got["big"] == {"unit": 10000, "rows": [840000, 380000, -50000], "total": 1170000}   # 모두 1만원 넘으면 만원 단위, 합은 반올림한 줄의 합
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
    got = run("""out = { rr: L.roundRows([15000, 15000, 15000]), pct: L.returnsPct({ held: 15000, sold: 15000, divs: 15000, cost: 100000 }),
      exact: L.roundRows([15000, 15000, 15000], { exact: true }), none: L.returnsPct({ held: 1, sold: 0, divs: 0, cost: null }),
      sw: [L.RETURNS_EXACT, L.RETURNS_PARTIAL] };""")
    assert got["rr"] == {"unit": 10000, "rows": [20000, 20000, 20000], "total": 60000}         # 화면의 줄은 2만원씩 (합 6만원)
    assert abs(got["pct"] - 45.0) < 1e-12                                                      # 수익률은 45.0%, 60% 가 아니에요
    assert got["exact"] == {"unit": 1, "rows": [15000, 15000, 15000], "total": 45000}          # 스위치 C (정확한 원): 4만 5,000원
    assert got["none"] is None and got["sw"] == [False, False]                                # 기본값: 만원 규칙 · 종목 통째로


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
    """Round-1 review A (Jack decides): off (what ships) the sold-out holding is left out of the bands; on (spec A.1) it is
    held with 0 shares, shows below its band (먼저 사요) and 추가로 넣을 돈 buys it back; the money totals hold no money for it."""
    got = run("""const stocks = [kr('000010', 1000), kr('000020', 1000)];
      const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], { purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('000020', 10, 1000, '2026-10-01')],
        sales: [sell('000020', 10, 1000, '2026-10-10')] });
      const run1 = (on) => { const ctx = { ...ctxOf(stocks), soldOutBands: on }; const e = R.evaluateDeck(d, ctx); const m = T.deckMoney(d, e, ctx);
        return { hs: e.holdings.map((x) => [x.t, x.qty, x.status]), soldOut: e.soldOut, unheld: e.unheld, m: [m.ok, m.value, m.cost],
          add: T.addMoney(e, 10000).buys.map((b) => [b.t, b.shares]) }; };
      out = { off: run1(false), on: run1(true), def: R.SOLD_OUT_BANDS };""")
    assert got["def"] is False
    off, on = got["off"], got["on"]
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
    got = run("""out = [L.roundRows([15000, -15000, 25000]), L.roundRows([-0.5, 0.5, 2], { exact: true })];""")
    assert got[0] == {"unit": 10000, "rows": [20000, -20000, 30000], "total": 30000}
    assert got[1]["rows"] == [-1, 1, 2]


def test_sold_out_band_switch_on_with_no_price_today_does_not_stop_the_rest():
    got = run("""const stocks = [kr('000010', 1000), { ...kr('000020', null), price: null }];
      const d = built([['000010', 'a', 0.5], ['000020', 'b', 0.5]], { purchases: [buy('000010', 10, 1000, '2026-10-01'), buy('000020', 10, 1000, '2026-10-01')],
        sales: [sell('000020', 10, 1000, '2026-10-10')] });
      const ctx = { ...ctxOf(stocks), soldOutBands: true };
      const e = R.evaluateDeck(d, ctx); const m = T.deckMoney(d, e, ctx);
      out = { w: e.weights.ok, hs: e.holdings.map((x) => [x.t, x.qty]), m: [m.ok, m.value, m.cost] };""")
    assert got["w"] is True and got["hs"] == [["000010", 10]] and got["m"] == [True, 10000, 10000]
