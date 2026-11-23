# -*- coding: utf-8 -*-
"""뱁새 2.0 주식 분할의 1/10,000 주 반올림 (src/v2/held.js count · lots.js ledger · records.js · edit.js) — Node 로 돌려봐요.

Track 2 audit 1.1 (2026-11-23): data.json 의 분할 150 건 중 47 건은 비율이 정수가 아니에요 (예: 듀폰 DD 1:3 2026-06-24 · 유니레버
UL 8:9 · AMCR 1:5 · HON 1:2 · SNEX 3:2). 그 분할 앞의 기록이 1/10,000 주로 나누어떨어지지 않으면 (DD · UL 같은 11 건은 1 주도, 나머지는
소수점 판매 · 금액으로 넣은 줄) held.js 는 기록마다 반올림하고 lots.js 는 반올림하지 않아서:
  (A) 앱이 분할을 저장하려다 "가진 것보다 많이 팔았어요"로 거절되고, 화면마다 끝없이 다시 시도했어요 (app.jsx: 이 파일 밖, smoke_v2)
  (B) 분할 전에 산 주식을 분할 전 날짜로 다 판 기록이 "가진 수량보다 많이 팔 수는 없어요"로 거절됐어요
  (C) 다 팔아도 0.0001 주가 남거나, 가진 것이 없는데 세금 화면에 −5원 '손실'이 나왔어요
Audit 1.4: 금액으로 넣은 종목을 역분할 전 날짜로 팔면 수량이 두 번 나뉘었어요 (수익이 세 배쯤).

고친 규칙 (held.js count, #184 리뷰 1차 반영): 기록마다 반올림(each, main 이 보여 준 수)과 정확한 누적을 반올림(running) 두 가지를
포지션마다 봐요. 판매로 어느 한 쪽이 (0 아래로 간 적 없이) 정확히 0 이 되면 그 포지션은 닫히고, 다음 기록은 0 에서 새로 시작해요
(다시 사도 0.0001 주가 붙지 않아요). 열린 포지션은 each 가 0 아래로 가지 않으면 each(main 과 같은 수), 아니면 running. 그래도
0 아래로 가는데 main 의 수(전체 이력 each)가 괜찮으면 main 의 수를 그대로 써요 (main 이 저장한 기록은 main 이 읽던 그대로).
가진 수량 · 묶음 · 가게의 검사 · 팔고 빼기가 모두 이 한 규칙이에요. 앱이 분할을 기록과 함께 저장하는 것은 종목마다, 그리고 main 의
수로도 읽힐 때만이에요 (lots.withStoredSplitsChecked). 분할이 없거나 단위가 맞는 분할(2:1 · 4:1 …)이면 예전 main 의 코드와 비트까지
같아요 (tests/fixtures/count_before_split_round_511fd6f 의 main 코드와 나란히 돌려 비교해요).
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
FIX = os.path.join(ROOT, "tests", "fixtures", "count_before_split_round_511fd6f")
_B = {}

NEW = (("H", "held.js"), ("L", "lots.js"), ("Rc", "records.js"), ("S", "store.js"), ("X", "tax.js"), ("P", "pf.js"), ("Tr", "track.js"), ("E", "edit.js"))
OLD = (("OH", "held.js"), ("OL", "lots.js"), ("ORc", "records.js"), ("OS", "store.js"), ("OX", "tax.js"), ("OP", "pf.js"), ("OTr", "track.js"))


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-splitround-")
        # main's count: today's src/ with held.js · lots.js · records.js as main had them (511fd6f); the other modules are unchanged
        old = os.path.join(tmp, "old")
        shutil.copytree(os.path.join(ROOT, "src"), os.path.join(old, "src"))
        for f in ("held.js", "lots.js", "records.js"):
            shutil.copy(os.path.join(FIX, f), os.path.join(old, "src", "v2", f))
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as fh:
            for name, mod in NEW:
                fh.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            for name, mod in OLD:
                fh.write(f"export * as {name} from {json.dumps(os.path.join(old, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/sr.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    names = ", ".join(n for n, _ in NEW + OLD)
    code = (f"import {{ {names} }} from './sr.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {{}};\n"
            + HELP + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# data.json's rows as published (fetch_data.py writes new shares per old share as a float): DD 1:3 on 2026-06-24, UL 8:9 on
# 2025-12-09, AMCR 1:5 on 2026-01-15 (a reverse split that gives whole units for whole shares)
HELP = """
const T = '2026-11-23';
const DD = { t: 'DD', date: '2026-06-24', r: 0.3333333333333333 }, UL = { t: 'UL', date: '2025-12-09', r: 0.8888888888888888 },
  AMCR = { t: 'AMCR', date: '2026-01-15', r: 0.2 };
const SPLITS = [DD, UL, AMCR];
const ROWS = []; for (let i = 0; i < 700; i++) ROWS.push([new Date(Date.parse('2025-01-02T00:00:00Z') + i * 864e5).toISOString().slice(0, 10), 1400 + (i % 50)]);
const HIST = { asOf: '2026-11-20', final: true, rows: ROWS.filter((r) => r[0] <= '2026-11-20') };
const env = { today: T, fx: 1460, fxDate: T, fxHist: HIST, stale: false };
const usd = (id, t, qty, price, date, fx = 1450) => ({ id, t, qty, price, date, ccy: 'USD', fx });
const deckOf = (t, purchases, sales = [], extra = {}) => ({ id: 'd1', name: '미국 주식', createdAt: '2025-11-03', planFx: 1450,
  holdings: [{ t, nk: t, cls: 'us' }], purchases, ...(sales.length ? { sales } : {}), ...extra });
const view = (deck, splits = SPLITS, M = L) => M.withDataSplits({ v: 2, decks: [deck] }, splits, T).decks[0];
const row = (t, price) => ({ t, cls: 'us', ccy: 'USD', price });
const units = (M, deck, t) => M.heldUnits(deck).get(t) || 0;
// a sale typed in the form, saved the way the screen saves it (records.withRecord, the store's own check), read back
function sell(deck, t, input, s, Rc_ = Rc, L_ = L) {
  const c = Rc_.checkSale(deck, t, input, s, env);
  if (!c.ok) return { ok: false, why: c.why };
  const w = Rc_.withRecord({ v: 2, decks: [deck] }, deck.id, 'sales', c.rec, T);
  return { ok: true, rec: c.rec, saved: !!w, after: w ? view(w.decks[0], SPLITS, L_) : null };
}
const lotsOf = (Lg) => Lg.lots.map((l) => l.u);
"""


# ── DD 1:3: 분할 전에 산 것을 분할 전 날짜로 다 팔기 (B) ──
def test_dd_a_sale_of_every_old_share_dated_before_the_split_is_accepted_and_leaves_exactly_0():
    got = run("""const deck = view(deckOf('DD', [usd('p1aaaaaa', 'DD', 1, 80, '2026-03-02'), usd('p2aaaaaa', 'DD', 1, 82, '2026-04-01')]));
      const s = sell(deck, 'DD', { qty: '2', price: '85', date: '2026-05-04' }, row('DD', 145.43));
      const Lg = L.ledger(s.after, 'DD');
      const old = ORc.checkSale(view(deckOf('DD', deck.purchases), SPLITS, OL), 'DD', { qty: '2', price: '85', date: '2026-05-04' }, row('DD', 145.43), env);
      out = { before: units(H, deck, 'DD'), ok: s.ok, saved: s.saved, after: units(H, s.after, 'DD'), soldOut: Rc.soldOutNow(s.after, 'DD'),
        lots: lotsOf(Lg), held: Lg.held, gain: Lg.sales[0].gain, fx: s.rec.fx, stored: s.after.splits, old: old.why };""")
    assert got["before"] == 6666                                   # 보이는 수는 main 과 같아요 (0.6666)
    assert got["ok"] and got["saved"] and got["after"] == 0 and got["soldOut"]
    assert got["lots"] == [] and got["held"] == 0                  # 장부에도 남은 조각이 없어요
    assert abs(got["gain"] - (2 * 85 * got["fx"] - (80 + 82) * 1450)) < 1e-6   # 판 금액 − 산 금액 전체 (다 팔았으니 원가도 다)
    assert got["stored"] == [{"t": "DD", "date": "2026-06-24", "r": 0.3333333333333333}]
    assert got["old"] == "tooMany"                                 # 고치기 전: "가진 수량보다 많이 팔 수는 없어요"


# ── DD 1:3: 분할 전 판 기록이 있는 포트폴리오 (A): 화면은 바르게 읽고, 앱은 main 이 못 읽을 분할 저장을 하지 않아요 ──
def test_dd_records_sold_before_the_split_read_right_and_the_split_is_stored_only_where_mains_count_reads_it():
    got = run("""const plain = deckOf('DD', [usd('p1aaaaaa', 'DD', 10, 80, '2026-03-02')], [usd('s1aaaaaa', 'DD', 5, 85, '2026-04-01', 1440), usd('s2aaaaaa', 'DD', 5, 86, '2026-05-04', 1430)]);
      const v = L.withDataSplits({ v: 2, decks: [plain] }, SPLITS, T);
      const c = L.withStoredSplitsChecked(v, T);
      const withSplit = { ...plain, splits: [DD] };
      // buy and hold: stored (main reads it too)
      const hold = L.withStoredSplitsChecked(L.withDataSplits({ v: 2, decks: [deckOf('DD', [usd('p1aaaaaa', 'DD', 10, 80, '2026-03-02')])] }, SPLITS, T), T);
      out = { held: units(H, v.decks[0], 'DD'), lots: lotsOf(L.ledger(v.decks[0], 'DD')), added: c.added, refused: c.refused, same: c.data === v,
        newReads: S.deckProblem(withSplit, T), mainReads: OS.deckProblem(withSplit, T), hold: [hold.added.length, hold.refused.length, S.deckProblem(hold.data.decks[0], T), OS.deckProblem(hold.data.decks[0], T)] };""")
    assert got["held"] == 0 and got["lots"] == []                  # 화면: 다 팔았어요 (main 은 −1 단위로 읽었어요)
    assert got["added"] == [] and got["same"] and len(got["refused"]) == 1
    assert "main's count" in got["refused"][0]["why"] and "sold more than held (2026-05-04)" in got["refused"][0]["why"]
    assert got["newReads"] is None and got["mainReads"]["why"].startswith("sold more than held")   # 저장했다면 main 이 따로 두었을 거예요
    assert got["hold"] == [1, 0, None, None]


def test_the_split_store_goes_stock_by_stock_one_stock_never_holds_back_another():
    got = run("""const SP = [{ t: 'AMZN', date: '2026-10-20', r: 1 / 3 }, { t: 'MSFT', date: '2026-10-20', r: 1 / 3 }];
      const d = { id: 'dsd', name: 'dsd', createdAt: '2026-08-01', planFx: 1300, holdings: [{ t: 'AMZN', nk: 'A', cls: 'us' }, { t: 'MSFT', nk: 'M', cls: 'us' }],
        purchases: [usd('p5aaaaaa', 'AMZN', 3, 200, '2026-09-01'), usd('p6aaaaaa', 'MSFT', 3, 400, '2026-09-01')], sales: [usd('s5aaaaaa', 'AMZN', 2, 230, '2026-10-26')] };
      const v = L.withDataSplits({ v: 2, decks: [d] }, SP, T);
      const a = L.withStoredSplitsChecked(v, T);
      const again = L.withStoredSplitsChecked(v, T, (x) => x.t === 'AMZN');           // a refused one is skipped next time
      out = { added: a.added.map((x) => x.t), refused: a.refused.map((x) => [x.t, x.why]), stored: a.data.decks[0].splits, ok: S.deckProblem(a.data.decks[0], T),
        main: OS.deckProblem(a.data.decks[0], T), again: [again.added.map((x) => x.t), again.refused.length] };""")
    assert got["added"] == ["MSFT"] and [t for t, _ in got["refused"]] == ["AMZN"]
    assert "sold more than held (2026-10-26)" in got["refused"][0][1]
    assert got["stored"] == [{"t": "MSFT", "date": "2026-10-20", "r": 1 / 3}] and got["ok"] is None and got["main"] is None
    assert got["again"] == [["MSFT"], 0]


# ── DD 1:3: 분할 뒤에 보이는 수량을 다 팔기 · 세금 화면 (C) ──
def test_dd_selling_the_shown_count_after_the_split_leaves_nothing_on_the_tax_screen():
    got = run("""const deck = view(deckOf('DD', [usd('p1aaaaaa', 'DD', 10, 80, '2026-03-02')]));
      const st = Rc.stockState(deck, 'DD');
      const s = sell(deck, 'DD', { qty: String(st.qty), price: '140', date: '2026-11-20' }, row('DD', 145.43));
      const q = { pxOf: () => 145.43, fx: 1460, absent: new Set() };
      const Lg = L.ledger(s.after, 'DD');
      const r = L.returnsOf(s.after, q);
      const od = view(deckOf('DD', deck.purchases, [s.rec]), SPLITS, OL);
      out = { shown: st.qty, ok: s.ok, saved: s.saved, held: units(H, s.after, 'DD'), lots: lotsOf(Lg), heldAny: r.heldAny, heldRow: r.held,
        losses: X.heldLosses([s.after], { pxOf: q.pxOf, fx: 1460, absent: { has: () => false } }), usHeld: X.taxRecords([s.after]).usHeld,
        year: X.yearGains([s.after]), rec: s.rec,
        old: { lotU: OL.ledger(od, 'DD').held, losses: OX.heldLosses([od], { pxOf: q.pxOf, fx: 1460, absent: { has: () => false } }).rows } };""")
    assert got["shown"] == 3.3333 and got["ok"] and got["saved"] and got["held"] == 0 and got["lots"] == []
    assert got["heldAny"] is False and got["heldRow"] == 0          # 내 수익: 가진 종목 손익 줄이 없어요
    assert got["losses"]["rows"] == [] and got["losses"]["held"] == 0 and got["usHeld"] is False
    rec = got["rec"]
    proceeds = rec["qty"] * rec["price"] * rec["fx"]
    assert got["year"]["n"] == 1 and got["year"]["left"] == 0
    assert got["year"]["gain"] == round(proceeds - 10 * 80 * 1450)  # 세금 화면의 합계: 판 금액 − 산 금액 전체
    # 고치기 전: 장부에 1/3 단위가 남아 세금 화면에 '손실' 줄이 나왔어요
    assert 0 < got["old"]["lotU"] < 1 and got["old"]["losses"] and got["old"]["losses"][0]["t"] == "DD"


def test_dd_selling_part_keeps_the_count_and_the_ledger_together():
    got = run("""const deck = view(deckOf('DD', [usd('p1aaaaaa', 'DD', 10, 80, '2026-03-02'), usd('p2aaaaaa', 'DD', 1, 95, '2026-05-06')]));
      const a = sell(deck, 'DD', { qty: '1.5', price: '140', date: '2026-11-20' }, row('DD', 145.43));
      const La = L.ledger(a.after, 'DD');
      const left = Rc.stockState(a.after, 'DD').qty;
      const b = sell(a.after, 'DD', { qty: String(left), price: '141', date: '2026-11-20' }, row('DD', 145.43));
      out = { before: units(H, deck, 'DD'), mid: units(H, a.after, 'DD'), ledgerMid: La.held, avg: La.avgOwn, avgBefore: L.ledger(deck, 'DD').avgOwn,
        left, end: units(H, b.after, 'DD'), lots: lotsOf(L.ledger(b.after, 'DD')), soldOut: Rc.soldOutNow(b.after, 'DD'),
        exact: [sell(deck, 'DD', { qty: '3.6667', price: '140', date: '2026-11-20' }, row('DD', 145.43))].map((x) => [x.ok, units(H, x.after, 'DD')])[0] };""")
    assert got["before"] == 36666                                   # 3,3333 + 3,333 (main 과 같은 3.6666)
    assert got["mid"] == 21666 and abs(got["ledgerMid"] - 21666) < 1e-6   # 판 뒤에도 수량과 장부가 같아요
    assert abs(got["avg"] - got["avgBefore"]) < 1e-9                # 이동평균: 판매는 평균 단가를 바꾸지 않아요
    assert got["left"] == 2.1666 and got["end"] == 0 and got["lots"] == [] and got["soldOut"]
    assert got["exact"] == [True, 0]                                # 정확한 11/3 = 3.6667 을 팔아도 0 (running 이 닫아요)


# ── UL 8:9 ──
def test_ul_eight_for_nine_buys_before_and_sales_on_either_side_of_the_split():
    got = run("""const buys = [1, 2, 3, 4, 5].map((i) => usd('p' + i + 'aaaaaaa', 'UL', 1, 55 + i, '2025-0' + (i + 3) + '-01'));
      const deck = view(deckOf('UL', buys));
      const st = Rc.stockState(deck, 'UL');
      const res = [[String(st.qty), '2026-11-20'], ['4.4444', '2026-11-20'], ['5', '2025-11-03']].map(([qty, date]) => {
        const x = sell(deck, 'UL', { qty, price: '63', date }, row('UL', 63.82));
        return [qty, x.ok, x.saved, units(H, x.after, 'UL'), lotsOf(L.ledger(x.after, 'UL'))]; });
      const od = view(deckOf('UL', buys, [usd('s1aaaaaa', 'UL', 5, 58, '2025-11-03')]), SPLITS, OL);
      out = { shown: st.qty, res, oldShown: ORc.stockState(view(deckOf('UL', buys), SPLITS, OL), 'UL').qty, oldB: units(OH, od, 'UL') };""")
    assert got["shown"] == 4.4445 == got["oldShown"]                 # 보이는 수: main 과 같아요 (5 x 8,889)
    # 보이는 4.4445 · 증권사의 4.4444 (정확한 40/9) · 분할 전 날짜로 옛 5 주: 모두 저장되고 정확히 0
    assert got["res"] == [["4.4445", True, True, 0, []], ["4.4444", True, True, 0, []], ["5", True, True, 0, []]]
    assert got["oldB"] == 1                                         # 고치기 전: 분할 전에 5 주를 다 팔아도 0.0001 주가 남았어요


# ── 예전 방식으로 저장된 기록은 저장된 그대로 ──
def test_records_saved_with_the_old_count_still_read_back_and_stay_at_0():
    got = run("""const stored = [{ t: 'DD', date: '2026-06-24', r: 0.3333333333333333 }];
      const two = [usd('p1aaaaaa', 'DD', 2, 80, '2026-03-02'), usd('p2aaaaaa', 'DD', 2, 81, '2026-04-01')];
      const three = [1, 2, 3].map((i) => usd('p' + i + 'aaaaaaa', 'DD', 1, 80, '2026-0' + (i + 2) + '-02'));
      const cases = [[two, 1.3334], [two, 1.3333], [three, 0.9999], [three, 1]];
      out = cases.map(([b, q]) => { const d = deckOf('DD', b, [usd('s1aaaaaa', 'DD', q, 140, '2026-11-02')], { splits: stored });
        return [S.deckProblem(d, T), OS.deckProblem(d, T), units(H, view(d), 'DD'), lotsOf(L.ledger(view(d), 'DD'))]; });""")
    # [1.3334: 예전에 보이던 수량] · [1.3333: 증권사가 보여 주는 수량] · [0.9999: 예전에 보이던 수량] · [1: 정확한 수량]
    assert got[0] == [None, None, 0, []] and got[2] == [None, None, 0, []]      # 예전에 저장된 그대로 읽히고 0 으로 끝나요
    assert got[1][0] is None and got[1][2:] == [0, []]                           # 예전에는 0.0001 주가 남았어요
    assert got[1][1] is None
    assert got[3][0] is None and got[3][2:] == [0, []] and got[3][1]["why"].startswith("sold more than held")   # 예전에는 거절


# ── 역분할 앞의 금액으로 넣은 종목 (audit 1.4) ──
def test_a_holding_put_in_by_amount_sold_before_a_reverse_split_sells_every_share_on_that_dates_basis():
    got = run("""const imp = { id: 'd1', name: '가진 종목', kind: 'imported', createdAt: '2025-12-01', settings: { points: {} }, holdings: [{ t: 'AMCR', nk: 'AMCR', cls: 'us' }],
        purchases: [], imported: [{ t: 'AMCR', nk: 'AMCR', ccy: 'USD', amountWon: 1000000, close: 10, date: '2025-12-01', fx: 1470, avg: 9 }] };
      const deck = view(imp);
      const res = [];
      for (const date of ['2026-01-05', '2026-03-02']) {
        const s = sell(deck, 'AMCR', { amountWon: '1200000', date }, row('AMCR', 42.35));
        const o = sell(view(imp, SPLITS, OL), 'AMCR', { amountWon: '1200000', date }, row('AMCR', 42.35), ORc, OL);
        const gain = Rc.salePreview(deck, s.rec).gain;
        res.push({ date, qty: s.rec.qty, saved: s.saved, held: units(H, s.after, 'AMCR'), gain, right: (s.rec.qty * s.rec.price - 68.0272 * 9) * s.rec.fx,
          old: { qty: o.rec.qty, held: units(OH, o.after, 'AMCR'), gain: ORc.salePreview(view(imp, SPLITS, OL), o.rec).gain } });
      }
      out = { shown: Rc.stockState(deck, 'AMCR').qty, res };""")
    assert got["shown"] == 13.6054                                   # 68.0272 주 ÷ 5
    early, late = got["res"]
    assert early["qty"] == 68.0272 and early["saved"] and early["held"] == 0     # 그날 기준 수량으로 다 팔아요
    assert abs(early["gain"] - early["right"]) < 1e-6
    assert early["old"]["qty"] == 13.6054 and early["old"]["held"] > 0           # 고치기 전: 1/5 만 팔고 나머지가 남았어요
    assert early["old"]["gain"] > 3 * early["gain"]                              #           수익은 세 배 넘게
    assert late["qty"] == 13.6054 and late["saved"] and late["held"] == 0        # 분할 뒤 날짜: 오늘 수량 그대로 (예전과 같아요)
    assert late["old"]["qty"] == late["qty"] and abs(late["gain"] - late["right"]) < 1e-6


# ── 팔고 빼기의 잠긴 수량 (edit.sellAllQty) ──
def test_sell_and_remove_takes_every_share_on_the_dates_basis_with_an_odd_ratio():
    got = run("""const deck = view(deckOf('DD', [usd('p1aaaaaa', 'DD', 1, 80, '2026-03-02'), usd('p2aaaaaa', 'DD', 1, 82, '2026-04-01'), usd('p3aaaaaa', 'DD', 1, 81, '2026-04-02')]));
      out = ['2026-05-04', '2026-11-20'].map((date) => { const q = E.sellAllQty(deck, 'DD', date);
        const d2 = { ...deck, sales: [usd('s1aaaaaa', 'DD', q, 140, date)] };
        return [q, units(H, d2, 'DD'), H.belowZero(d2)]; });""")
    assert got == [[3, 0, None], [0.9999, 0, None]]                  # 분할 전 날짜: 옛 3 주 · 오늘: 보이는 0.9999 주


# ── 0.0001 주 판매가 0 단위로 세어질 때 (분할 전 1:3, review N4) ──
def test_a_sale_that_counts_for_no_unit_takes_the_cost_of_what_it_sold():
    got = run("""const deck = view(deckOf('DD', [usd('p1aaaaaa', 'DD', 1, 80, '2026-03-02')], [usd('s1aaaaaa', 'DD', 0.0001, 85, '2026-04-01')]));
      const Lg = L.ledger(deck, 'DD');
      out = { held: units(H, deck, 'DD'), lots: lotsOf(Lg), gain: Lg.sales[0].gain, ok: Number.isFinite(Lg.sales[0].gain), left: Lg.lots[0].won, removed: Lg.sales[0].removedWon };""")
    sold = 0.3333333333333333                                       # 0.0001 옛 주 = 1/3 단위
    cost = 80 * 1450 * sold / 3333                                  # 그 몫의 원가 (3,333 단위에 116,000원)
    assert got["held"] == 3333 and got["lots"] == [3333] and got["ok"]
    assert abs(got["removed"] - cost) < 1e-6 and abs(got["left"] - (80 * 1450 - cost)) < 1e-6
    assert abs(got["gain"] - (0.0001 * 85 * 1450 - cost)) < 1e-9    # 판 금액 − 판 만큼의 원가 (판 금액 전부가 아니에요)


# ── 다 판 뒤 다시 사기 (review round 1: 포지션마다 새로 세요) ──
def test_sold_out_on_mains_count_then_bought_again_reads_as_main_did():
    got = run("""// main 에서 저장된 기록: 옛 1 + 1 주, main 이 보여 준 0.6666 을 11-02 에 팔았어요 (분할도 저장)
      const saved = { ...deckOf('DD', [usd('p1aaaaaa', 'DD', 1, 80, '2026-03-02'), usd('p2aaaaaa', 'DD', 1, 82, '2026-04-01')], [usd('s1aaaaaa', 'DD', 0.6666, 140, '2026-11-02')]), splits: [DD] };
      const deck = view(saved);
      const c = Rc.checkPurchase(deck, 'DD', { qty: '5', price: '140', date: T }, row('DD', 145.43), env);
      const w = Rc.withRecord({ v: 2, decks: [deck] }, deck.id, 'purchases', c.rec, T);
      const d2 = view(w.decks[0]), o2 = view(w.decks[0], SPLITS, OL);
      const Lg = L.ledger(d2, 'DD');
      out = { before: units(H, deck, 'DD'), qty: Rc.stockState(d2, 'DD').qty, avg: Lg.avgOwn, lots: lotsOf(Lg), main: [ORc.stockState(o2, 'DD').qty], ok: S.deckProblem(w.decks[0], T), mainOk: OS.deckProblem(w.decks[0], T) };""")
    assert got["before"] == 0 and got["qty"] == 5 == got["main"][0]  # 5.0001 주가 아니에요
    assert got["avg"] == 140 and got["lots"] == [50000] and got["ok"] is None and got["mainOk"] is None


def test_case_b_selling_one_unit_more_than_shown_and_buying_the_same_day_reads_whole_shares():
    got = run("""const deck = view(deckOf('DD', [usd('p1aaaaaa', 'DD', 2, 80, '2026-03-02'), usd('p2aaaaaa', 'DD', 2, 81, '2026-04-01')]));
      const a = sell(deck, 'DD', { qty: '1.3334', price: '140', date: T }, row('DD', 145.43));
      const c = Rc.checkPurchase(a.after, 'DD', { qty: '3', price: '140', date: T }, row('DD', 145.43), env);
      const w = Rc.withRecord({ v: 2, decks: [a.after] }, 'd1', 'purchases', c.rec, T);
      const d2 = view(w.decks[0]);
      // on another day too: the sale closes the position, the next purchase starts from 0
      const b = sell(deck, 'DD', { qty: '1.3334', price: '140', date: '2026-11-02' }, row('DD', 145.43));
      const c2 = Rc.checkPurchase(b.after, 'DD', { qty: '3', price: '140', date: T }, row('DD', 145.43), env);
      const d3 = view(Rc.withRecord({ v: 2, decks: [b.after] }, 'd1', 'purchases', c2.rec, T).decks[0]);
      out = { shown: Rc.stockState(deck, 'DD').qty, sold: [a.ok, a.saved, units(H, a.after, 'DD')], sameDay: Rc.stockState(d2, 'DD').qty, sameDayLots: lotsOf(L.ledger(d2, 'DD')),
        laterDay: [Rc.stockState(d3, 'DD').qty, L.ledger(d3, 'DD').avgOwn] };""")
    assert got["shown"] == 1.3334 and got["sold"] == [True, True, 0]
    assert got["sameDay"] == 3 and abs(sum(got["sameDayLots"]) - 30000) < 1e-6      # 2.9999 주가 아니에요
    assert got["laterDay"] == [3, 140]


def test_sell_and_remove_after_a_position_main_closed_starts_from_the_count_in_use():
    # review N1: 옛 2 주를 8 번 사고 main 이 보여 준 5.3336 을 판 뒤 3 주를 샀어요 (main: 3)
    got = run("""const buys = []; for (let i = 0; i < 8; i++) buys.push(usd('p' + i + 'aaaaaaa', 'DD', 2, 80, '2026-03-' + String(10 + i)));
      const d = { ...deckOf('DD', [...buys, usd('pzaaaaaa', 'DD', 3, 140, '2026-11-10')], [usd('s1aaaaaa', 'DD', 5.3336, 140, '2026-11-02')]), splits: [DD] };
      const v = view(d);
      out = [units(H, v, 'DD'), E.sellAllQty(v, 'DD', T), E.sellAllQty(v, 'DD', '2026-11-10')];""")
    assert got == [30000, 3, 3]


# ── #184 리뷰 2차 ──
def test_a_zero_unit_sale_after_a_full_sale_counts_its_money_as_main_did():
    # S1: 옛 3 주를 2.9999 와 0.0001 로 판 기록 (DD 1:3) · 옛 1 주를 0.9999 와 0.0001 로 (1:5): 두 번째 판매는 0 단위로 세어지고 남은 묶음도 없어요
    got = run("""const SP3 = [DD], SP5 = [{ t: 'DD', date: '2026-01-15', r: 0.2 }];
      const q = { pxOf: () => 100, fx: 1400, absent: new Set() };
      const KOSPI = []; for (let i = 0; i < 700; i++) KOSPI.push([new Date(Date.parse('2025-01-02T00:00:00Z') + i * 864e5).toISOString().slice(0, 10), 2500 + (i % 30)]);
      const one = (buys, sales, sp) => { const d = deckOf('DD', buys, sales);
        const vn = view(d, sp), vo = view(d, sp, OL);
        const a = L.returnsOf(vn, q), b = OL.returnsOf(vo, q);
        const kn = L.kospiMirror(L.recordSets(vn), KOSPI, KOSPI[KOSPI.length - 1], () => 0, Tr.closeBefore);
        return { held: units(H, vn, 'DD'), lots: lotsOf(L.ledger(vn, 'DD')), gains: L.ledger(vn, 'DD').sales.map((s) => s.gain), sold: [a.sold, b.sold], noAvg: a.noAvg, soldOut: a.soldOut,
          year: [X.yearGains([vn]), OX.yearGains([vo])], kospi: kn.ok }; };
      out = { dd: one([usd('p1aaaaaa', 'DD', 3, 80, '2026-03-02', 1400)], [usd('s1aaaaaa', 'DD', 2.9999, 85, '2026-04-01', 1400), usd('s2aaaaaa', 'DD', 0.0001, 85, '2026-04-02', 1400)], SP3),
        five: one([usd('p1aaaaaa', 'DD', 1, 10, '2025-11-03', 1400)], [usd('s1aaaaaa', 'DD', 0.9999, 12, '2025-12-01', 1400), usd('s2aaaaaa', 'DD', 0.0001, 12, '2025-12-02', 1400)], SP5) };""")
    dd, five = got["dd"], got["five"]
    assert dd["held"] == 0 and dd["lots"] == [] and dd["noAvg"] == [] and dd["soldOut"] == 0 and dd["kospi"]
    assert abs(dd["gains"][1] - 0.0001 * 85 * 1400) < 1e-9                  # 두 번째 판매: 판 금액 그대로 (원가는 첫 판매가 다 가져갔어요)
    assert round(dd["sold"][0]) == round(dd["sold"][1]) == 21000             # 내 수익 판 종목: main 과 같아요
    assert dd["year"][0]["n"] == 2 and dd["year"][0]["left"] == 0 and dd["year"][0]["gain"] == dd["year"][1]["gain"] == 21000   # 세금 화면
    assert five["held"] == 0 and five["lots"] == [] and five["noAvg"] == [] and five["soldOut"] == 0 and five["kospi"]
    assert round(five["sold"][0]) == round(five["sold"][1]) == 2800


def test_four_old_shares_sold_as_3_9998_and_0_0002_read_as_sold_out():
    # S2: 옛 4 주 = 정확히 0 이 남아요. 기록마다 반올림은 첫 판매에서 닫혀 둘째가 0 아래로 가요 → 처음부터 누적 반올림으로 읽어요
    got = run("""const d = { ...deckOf('DD', [usd('p1aaaaaa', 'DD', 4, 80, '2026-03-02', 1400)], [usd('s1aaaaaa', 'DD', 3.9998, 85, '2026-04-01', 1400), usd('s2aaaaaa', 'DD', 0.0002, 85, '2026-04-02', 1400)]), splits: [DD] };
      const v = view(d);
      const r = L.returnsOf(v, { pxOf: () => 100, fx: 1400, absent: new Set() });
      const c = Rc.checkPurchase(v, 'DD', { qty: '3', price: '140', date: T }, row('DD', 145.43), env);
      out = { ok: S.deckProblem(d, T), held: units(H, v, 'DD'), lots: lotsOf(L.ledger(v, 'DD')), sold: Math.round(r.sold), noAvg: r.noAvg, buy: !!Rc.withRecord({ v: 2, decks: [v] }, 'd1', 'purchases', c.rec, T), main: OS.deckProblem(d, T) };""")
    assert got["ok"] is None and got["held"] == 0 and got["lots"] == [] and got["noAvg"] == [] and got["sold"] == 28000 and got["buy"]
    assert got["main"]["why"].startswith("sold more than held")             # main 은 이 기록을 읽지 못해요 (그래서 앱이 분할을 저장하지 않아요)


def test_sell_and_remove_never_picks_a_quantity_that_goes_below_0_on_the_way():
    # N1: 2:3 (3 옛 주 → 2 새 주) 10-29 · 04-22 에 2 주 · 06-21 에 3 + 2 주를 사고 4.9999 주를 팔았어요 · 06-01 날짜로 팔고 빼기 (main: 2)
    got = run("""const SP = [{ t: 'AAA', date: '2026-10-29', r: 0.6666666666666666 }];
      const d = deckOf('AAA', [usd('p1aaaaaa', 'AAA', 2, 50, '2026-04-22'), usd('p2aaaaaa', 'AAA', 3, 50, '2026-06-21'), usd('p3aaaaaa', 'AAA', 2, 50, '2026-06-21')], [usd('s1aaaaaa', 'AAA', 4.9999, 55, '2026-06-21')]);
      const v = view(d, SP);
      const q = E.sellAllQty(v, 'AAA', '2026-06-01');
      out = { q, ok: Rc.checkSale(v, 'AAA', { qty: String(q), price: '60', date: '2026-06-01' }, row('AAA', 80), env).ok };""")
    assert got == {"q": 2, "ok": True}


def test_a_stock_main_already_cannot_read_never_holds_back_another_stocks_split():
    # N2: NVDA 옛 1 + 1 주를 분할 전에 2 주로 판 기록 (분할 저장됨: main 은 이 포트폴리오를 읽지 못해요) · MSFT 는 분할 전에 3 주
    got = run("""const SP = [{ t: 'NVDA', date: '2026-10-20', r: 1 / 3 }, { t: 'MSFT', date: '2026-10-20', r: 1 / 3 }];
      const d = { id: 'd2', name: 'two', createdAt: '2026-08-01', planFx: 1300, holdings: [{ t: 'NVDA', nk: 'N', cls: 'us' }, { t: 'MSFT', nk: 'M', cls: 'us' }],
        purchases: [usd('p7aaaaaa', 'NVDA', 1, 100, '2026-09-01'), usd('p8aaaaaa', 'NVDA', 1, 100, '2026-09-02'), usd('p9aaaaaa', 'MSFT', 3, 400, '2026-09-01')],
        sales: [usd('s7aaaaaa', 'NVDA', 2, 120, '2026-10-01')], splits: [SP[0]] };
      const r = L.withStoredSplitsChecked(L.withDataSplits({ v: 2, decks: [d] }, SP, T), T);
      out = { added: r.added.map((x) => x.t), refused: r.refused.length, mainBefore: OS.deckProblem(d, T) != null };""")
    assert got == {"added": ["MSFT"], "refused": 0, "mainBefore": True}


# ── 분할이 없거나 단위가 맞는 분할: main 의 코드와 비트까지 같아요 ──
COMPARE = """
// mulberry32 (review round 1: the old LCG went past 2^53 and repeated after about 10,000 draws)
let seed = 20261124;
const rnd = () => { seed = (seed + 0x6D2B79F5) | 0; let z = Math.imul(seed ^ (seed >>> 15), 1 | seed); z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z; return ((z ^ (z >>> 14)) >>> 0) / 4294967296; };
const ri = (a, b) => a + Math.floor(rnd() * (b - a + 1));
const pick = (a) => a[Math.floor(rnd() * a.length)];
const day = (n) => { const d = new Date(Date.parse('2025-01-02T00:00:00Z') + n * 864e5).toISOString().slice(0, 10); return d > T ? T : d; };
const KR = ['000010', '000020'], US = ['AAA', 'BBB', 'CCC'];
let idn = 0;
const id = () => 'r' + String(++idn).padStart(7, '0');
function make(mode) {
  const stocks = [...KR.filter(() => rnd() < 0.5), ...US.filter(() => rnd() < 0.7)];
  if (!stocks.length) stocks.push('AAA');
  const c0 = ri(0, 450), imported = rnd() < 0.4;
  const deck = { id: 'd' + ri(100000, 999999), name: 'p', createdAt: day(c0), planFx: 1300 + ri(0, 200), holdings: stocks.map((t) => ({ t, nk: t, cls: KR.includes(t) ? 'kr' : 'us' })), purchases: [] };
  if (imported) { deck.kind = 'imported'; deck.settings = { points: {} }; deck.imported = []; }
  const sales = [], divs = [], splits = [], vw = [];
  for (const t of stocks) {
    const us = US.includes(t), ccy = us ? 'USD' : 'KRW', px = () => (us ? ri(1000, 90000) / 100 : ri(1000, 900000));
    if (imported && rnd() < 0.8) {
      if (rnd() < 0.35) deck.imported.push({ t, nk: t, ccy, amountWon: ri(100000, 50000000), close: px(), date: day(c0 - ri(0, 200)), ...(us ? { fx: 1300 + ri(0, 200) } : {}), ...(rnd() < 0.7 ? { avg: px() } : {}) });
      else deck.imported.push({ t, nk: t, ccy, qty: us ? ri(1, 20000000) / 10000 : ri(1, 300), ...(rnd() < 0.8 ? { avg: px() } : {}), ...(rnd() < 0.2 ? { date: day(c0 - ri(0, 100)) } : {}) });
    }
    for (let i = ri(0, 4); i > 0; i--) deck.purchases.push({ id: id(), t, qty: ri(1, 40), price: px(), date: day(c0 + ri(-300, 300)), ccy, ...(us ? (rnd() < 0.85 ? { fx: 1300 + ri(0, 200) } : rnd() < 0.5 ? { noFx: true } : {}) : {}) });
    for (let i = ri(0, 3); i > 0; i--) sales.push({ id: id(), t, qty: us ? ri(1, 300000) / 10000 : ri(1, 30), price: px(), date: day(c0 + ri(-100, 330)), ccy, ...(us && rnd() < 0.9 ? { fx: 1300 + ri(0, 200) } : {}) });
    for (let i = ri(0, 2); i > 0; i--) divs.push({ id: id(), t, amount: us ? ri(1, 50000) / 100 : ri(100, 500000), date: day(c0 + ri(0, 330)), ccy, ...(us && rnd() < 0.9 ? { fx: 1300 + ri(0, 200) } : {}) });
    if (us && mode === 'int') for (let i = ri(0, 2); i > 0; i--) { const s = { t, date: day(c0 + ri(-150, 320)), r: pick([2, 3, 4, 5, 10, 20, 8, 15]) }; (rnd() < 0.5 ? splits : vw).push(s); }
  }
  // some records dated on a split's own day (already at the new count)
  for (const s of [...splits, ...vw]) for (const r of [...deck.purchases, ...sales]) if (r.t === s.t && rnd() < 0.2) r.date = s.date;
  if (sales.length) deck.sales = sales;
  if (divs.length) deck.divs = divs;
  if (splits.length) deck.splits = splits;
  return { deck, vw };
}
function plain(x) {
  if (x instanceof Map) return ['Map', [...x.entries()].map(([k, v]) => [k, plain(v)])];
  if (x instanceof Set) return ['Set', [...x].map(plain)];
  if (Array.isArray(x)) return x.map(plain);
  if (x && typeof x === 'object') {
    if (typeof x.id === 'string' && /^r\\d{7}$/.test(x.id)) return 'rec:' + x.id;
    const o = {};
    for (const k of Object.keys(x).sort()) if (!(k === 'id' && typeof x.id === 'string' && x.id.length === 20)) o[k] = plain(x[k]);
    return o;
  }
  return x;
}
function diff(a, b, p = '') {
  if (typeof a === 'number' && typeof b === 'number') return Object.is(a, b) ? null : p + ': ' + a + ' vs ' + b;
  if (Array.isArray(a) && Array.isArray(b)) { if (a.length !== b.length) return p + ': length'; for (let i = 0; i < a.length; i++) { const d = diff(a[i], b[i], p + '[' + i + ']'); if (d) return d; } return null; }
  if (a && b && typeof a === 'object' && typeof b === 'object') { const ka = Object.keys(a), kb = Object.keys(b); if (ka.join() !== kb.join()) return p + ': keys'; for (const k of ka) { const d = diff(a[k], b[k], p + '.' + k); if (d) return d; } return null; }
  return a === b ? null : p + ': ' + JSON.stringify(a) + ' vs ' + JSON.stringify(b);
}
// main's 팔고 빼기 quantity (edit.js sellAllQty at 511fd6f), on main's held.js
function oldSellAll(deck, t, date) {
  const u = OH.heldUnits(deck).get(t) || 0;
  if (!(u > 0) || typeof date !== 'string' || !date) return null;
  const f = OH.splitFactor(OH.splitsOf(deck), t, date);
  const q0 = Math.round(u / f);
  for (const d of [0, -1, 1, -2, 2]) { const q = q0 + d; if (q > 0 && Math.round(-q * f) === -u) return q / 10000; }
  return null;
}
const KOSPI = []; for (let i = 0; i < 800; i++) KOSPI.push([new Date(Date.parse('2024-06-03T00:00:00Z') + i * 864e5).toISOString().slice(0, 10), 2400 + Math.round(600 * Math.sin(i / 40))]);
function results(N, deck0, vw) {
  const M = N === 'new' ? { H, L, Rc, S, X, P, T: Tr } : { H: OH, L: OL, Rc: ORc, S: OS, X: OX, P: OP, T: OTr };
  const data = M.L.withDataSplits({ v: 2, decks: [deck0] }, vw, T);
  const deck = data.decks[0];
  const out = {};
  const go = (k, f) => { try { out[k] = plain(f()); } catch (e) { out[k] = 'throws ' + e.message; } };
  const q = { pxOf: (t) => (KR.includes(t) ? 123456 : 123.45), fx: 1450, absent: new Set() };
  go('heldUnits', () => M.H.heldUnits(deck));
  go('heldQty', () => M.H.heldQty(deck));
  go('belowZero', () => M.H.belowZero(deck));
  for (const d of ['2025-06-30', '2026-01-15', '2026-06-30']) go('heldUnits ' + d, () => M.H.heldUnits(deck, d));
  go('deckProblem', () => M.S.deckProblem(deck0, T));
  go('stored', () => M.L.withStoredSplits(data));
  go('returnsOf', () => M.L.returnsOf(deck, q));
  go('fxSplit', () => M.L.fxSplit(M.L.stocksOf(deck).map((t) => M.L.ledger(deck, t)), q.pxOf, 1450));
  go('kospi', () => M.L.kospiMirror(M.L.recordSets(deck), KOSPI, KOSPI[KOSPI.length - 1], () => 1000000, M.T.closeBefore));
  go('tax', () => [M.X.taxRecords([deck]), M.X.yearGains([deck]), M.X.yearDivs([deck]), M.X.heldLosses([deck], { pxOf: q.pxOf, fx: 1450, absent: { has: () => false } })]);
  for (const t of M.L.stocksOf(deck)) {
    go('ledger ' + t, () => M.L.ledger(deck, t));
    go('state ' + t, () => ({ ...M.Rc.stockState(deck, t), ledger: null }));
    go('soldOut ' + t, () => M.Rc.soldOutNow(deck, t));
    go('avg ' + t, () => M.P.avgOf(deck, t));
    go('heldCost ' + t, () => M.T.heldCost(deck, t));
    for (const date of ['2025-03-03', '2026-01-05', T]) go('sellAll ' + t + ' ' + date, () => (N === 'new' ? E.sellAllQty(deck, t, date) : oldSellAll(deck, t, date)));
    const s = KR.includes(t) ? { t, cls: 'kr', ccy: 'KRW', price: 123456 } : { t, cls: 'us', ccy: 'USD', price: 123.45 };
    const qty = String(M.Rc.stockState(deck, t).qty);
    // a holding put in by amount, sold on a date before a split, is audit 1.4 (it changes on purpose): those sales are dated today
    [{ qty, price: '100', date: T }, { qty, price: '100', date: '2026-01-05' }, { qty: '1', price: '100', date: '2026-01-05' },
      { qty: String(Number(qty) + 1), price: '100', date: T }, { amountWon: '1234567', date: T }].forEach((inp, i) => go('checkSale ' + t + ' ' + i, () => {
      const c = M.Rc.checkSale(deck, t, inp, s, env);
      return c.ok ? { ok: true, rec: c.rec, preview: M.Rc.salePreview(deck, c.rec), saved: !!M.Rc.withRecord(data, deck.id, 'sales', c.rec, T) } : c;
    }));
  }
  return out;
}
"""


def test_without_an_odd_split_every_count_and_amount_is_bit_identical_to_mains_code():
    got = run(COMPARE + """
      const tally = {};
      for (const mode of ['none', 'int']) {
        tally[mode] = { decks: 0, checks: 0, diffs: [], distinct: 0 };
        const seen = new Set();
        for (let i = 0; i < 250; i++) {
          const { deck, vw } = make(mode);
          seen.add(JSON.stringify([deck, vw]).replace(/"id":"r\\d{7}",?/g, ''));
          tally[mode].distinct = seen.size;
          const a = results('old', deck, vw), b = results('new', deck, vw);
          tally[mode].decks++;
          for (const k of Object.keys(a)) { tally[mode].checks++; const d = diff(a[k], b[k], k); if (d && tally[mode].diffs.length < 5) tally[mode].diffs.push(d.slice(0, 200)); }
        }
      }
      out = tally;""")
    for mode in ("none", "int"):
        assert got[mode]["decks"] == 250 and got[mode]["distinct"] == 250 and got[mode]["checks"] > 10000, got[mode]
        assert got[mode]["diffs"] == [], (mode, got[mode]["diffs"])
