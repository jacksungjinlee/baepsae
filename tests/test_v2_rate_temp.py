# -*- coding: utf-8 -*-
"""뱁새 2.0: 임시 환율 (Jack, 2026-11-27, #191) — Node 에서 돌려봐요.

Jack: "not at today's rate. Save it right away at the latest available rate, marked temporary, and replace it with that date's
official rate automatically when the morning data arrives." 그 날짜의 환율이 환율 기록(macro.json fxHist)에 아직 없는 달러 기록은 앱이
가진 최근 환율(data.json fx)로 저장되고 rateTemp 표시가 붙어요 (records.rateFor · tests/test_v2_us_dates.py). 여기서는 그 다음:
- records.withOfficialRates: 불러온 데이터의 환율 기록에 그 날짜가 들어오면 그날 줄로 바꾸고 표시를 지워요. 아직이면 그대로 (그 전 날의 줄을
  쓰지 않아요). 주말 · 한국 휴일처럼 자기 줄이 끝내 없는 날짜는 그 뒤의 줄이 생겨야 (그날 줄이 다시 올 수 없을 때) 그 전 마지막 줄 — 그 날짜로
  지금 적은 기록이 받는 환율과 같아요 (#117 RUNBOOK). 마지막 줄이 final 이 아니면 기다려요. 같은 결과를 두 번 돌려도 그대로 (idempotent).
- 금액으로 넣은 종목을 판 금액(원)으로 판 기록은 원화 금액이 그대로 남아요 (달러 가격이 환율 따라 움직여요).
- 포트폴리오에서 뺀 종목(history)의 기록도 바꿔요. 지운 기록은 남지 않아요. 기록 파일로 내보냈다 불러와도 표시가 남아 바뀌어요.
- 두 창: 한 창이 바꾼 뒤 다른 창(예전 기록을 든)이 저장해도 같은 기록이 두 번 세지지 않아요 (history 의 같은 기록 id 는 같은 항목).
  #191 전 빌드(남은 캐시 · 되돌림)가 합쳐 둔 같은 기록의 두 항목도 불러올 때 하나로 (store.withoutTwinEntries).
- 멈춘 데이터 · 이 PR 전에 저장된 기록(표시 없음)은 그대로예요. 저장 기록 검사(store.js): rateTemp 는 true, 환율이 있는 달러 기록에만.
기대값은 손으로 셌어요.
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


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-ratetemp-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("Rc", "records.js"), ("L", "lots.js"), ("H", "held.js"), ("Tx", "tax.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            # main's store.js before #191 (2760844, frozen in tests/fixtures: CI's shallow clone has no history to show it from)
            f.write(f"export * as OS from {json.dumps(os.path.join(ROOT, 'tests', 'fixtures', 'store_before_191_2760844', 'store.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


FAKE = """
const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
const logs = []; console.warn = (m) => logs.push(String(m)); console.info = (m) => logs.push(String(m));
const K = 'baepsae2.v1', T = '2026-11-24';
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const ROWS = [['2016-01-04', 1172.5], ['2026-11-20', 1336.2], ['2026-11-23', 1345.9], ['2026-11-24', 1344.1], ['2026-12-30', 1420.0], ['2027-01-04', 1431.5]];
const hist = (asOf, final = true) => { const rows = ROWS.filter(([d]) => d <= asOf); return { asOf: rows[rows.length - 1][0], final, rows }; };
const tmp = (id, t, date, more = {}) => ({ id, t, qty: 2, price: 300, date, ccy: 'USD', fx: 1338.0, rateTemp: true, ...more });
const deckOf = (extra = {}) => ({ id: 'd1', name: '포트폴리오', createdAt: '2026-06-01', planFx: 1300,
  holdings: [{ t: '005930', nk: '삼성전자', target: 0.5, rules: band(0.5) }, { t: 'AAPL', nk: 'Apple Inc.', target: 0.5, rules: band(0.5) }],
  purchases: [{ id: 'p1aaaaaa', t: '005930', qty: 10, price: 200000, date: '2026-06-02', ccy: 'KRW' }, { id: 'p2aaaaaa', t: 'AAPL', qty: 3, price: 300, date: '2026-06-02', ccy: 'USD', fx: 1300 }],
  ...extra });
const storeOf = (...decks) => ({ v: 2, decks });
const recs = (d) => [...(d.purchases || []), ...(d.sales || []), ...(d.divs || []), ...(d.history || []).flatMap((e) => [...(e.purchases || []), ...(e.sales || []), ...(e.divs || [])])];
const pick = (data, id) => recs(data.decks[0]).find((r) => r.id === id);
"""


def run(body):
    d = bundle_dir()
    code = "import { S, Rc, L, H, Tx, OS } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=d, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_a_temporary_rate_waits_for_its_own_dates_row_then_takes_it_once():
    got = run("""
      const st = storeOf(deckOf({ purchases: [...deckOf().purchases, tmp('p9aaaaaa', 'AAPL', '2026-11-23')],
        divs: [tmp('v9aaaaaa', 'AAPL', '2026-11-24', { qty: undefined, price: undefined, amount: 1.25 })] }));
      const before = Rc.withOfficialRates(st, hist('2026-11-20'));                  // 01:00 KST: the history ends on Friday
      const morning = Rc.withOfficialRates(st, hist('2026-11-23'));                 // the 06:40 publish has 11-23 (not 11-24 yet)
      const again = Rc.withOfficialRates(morning.data, hist('2026-11-23'));
      const next = Rc.withOfficialRates(morning.data, hist('2026-11-24'));
      out = { before: [before.data === st, before.fixed.length, before.waiting.map((x) => [x.t, x.kind, x.date])],
        morning: [pick(morning.data, 'p9aaaaaa'), pick(morning.data, 'v9aaaaaa').rateTemp === true, morning.fixed, morning.waiting.length],
        again: [again.data === morning.data, again.fixed.length], next: [pick(next.data, 'v9aaaaaa'), next.fixed.length],
        valid: S.validStore(morning.data, T) && S.validStore(next.data, T), untouched: pick(morning.data, 'p2aaaaaa') };""")
    assert got["before"] == [True, 0, [["AAPL", "buy", "2026-11-23"], ["AAPL", "div", "2026-11-24"]]]     # nothing written: the same object
    assert got["morning"][0] == {"id": "p9aaaaaa", "t": "AAPL", "qty": 2, "price": 300, "date": "2026-11-23", "ccy": "USD", "fx": 1345.9}
    assert got["morning"][1] is True and got["morning"][3] == 1                                       # 11-24 still waits (no row yet)
    assert got["morning"][2] == [{"id": "d1", "t": "AAPL", "date": "2026-11-23", "kind": "buy", "from": 1338.0, "to": 1345.9}]
    assert got["again"] == [True, 0]                                                                   # idempotent
    assert got["next"] == [{"id": "v9aaaaaa", "t": "AAPL", "amount": 1.25, "date": "2026-11-24", "ccy": "USD", "fx": 1344.1}, 1]
    assert got["valid"] is True
    assert got["untouched"] == {"id": "p2aaaaaa", "t": "AAPL", "qty": 3, "price": 300, "date": "2026-06-02", "ccy": "USD", "fx": 1300}


def test_a_weekend_or_korean_holiday_date_takes_the_last_row_before_it_only_once_a_later_row_shows_it_never_gets_its_own():
    """Sunday 11-22 (Monday morning KST's US trade date) and 2026-12-31 (a US trading day, a Korean market holiday: ECOS has no Seoul
    close): while the history ends before them they wait; Friday's row (or 12-30's) is never used then. Once a later row exists their
    own row can never come (rows come in date order), and they take the last row before them, the rate a record of that date typed now
    gets (#117: a weekend or Korean holiday uses the last row before it)."""
    got = run("""
      const st = storeOf(deckOf({ purchases: [...deckOf().purchases, tmp('p8aaaaaa', 'AAPL', '2026-11-22'), tmp('p9aaaaaa', 'AAPL', '2026-12-31')] }));
      const a = Rc.withOfficialRates(st, hist('2026-11-20')), b = Rc.withOfficialRates(st, hist('2026-11-23'));
      const c = Rc.withOfficialRates(b.data, hist('2026-12-30')), d = Rc.withOfficialRates(c.data, hist('2027-01-04'));
      out = { a: [a.fixed.length, a.waiting.length], b: [pick(b.data, 'p8aaaaaa').fx, pick(b.data, 'p8aaaaaa').rateTemp === true, b.waiting.length],
        c: [c.fixed.length, pick(c.data, 'p9aaaaaa').rateTemp === true], d: [pick(d.data, 'p9aaaaaa').fx, pick(d.data, 'p9aaaaaa').rateTemp === true],
        typed: [Rc.rateFor('2026-11-22', { today: null, fxHist: hist('2026-11-23') }), Rc.rateFor('2026-12-31', { today: null, fxHist: hist('2027-01-04') })] };""")
    assert got["a"] == [0, 2]
    assert got["b"] == [1336.2, False, 1]                      # Sunday: Friday 11-20's row once Monday 11-23's is in
    assert got["c"] == [0, True]                               # 12-31 waits while the history ends on 12-30
    assert got["d"] == [1420.0, False]                         # 12-30's row once 2027-01-04's is in
    assert got["typed"] == [{"ok": True, "fx": 1336.2}, {"ok": True, "fx": 1420.0}]


def test_a_last_row_not_marked_final_is_not_used_and_stale_data_changes_nothing():
    got = run("""
      const st = storeOf(deckOf({ purchases: [...deckOf().purchases, tmp('p9aaaaaa', 'AAPL', '2026-11-23')] }));
      const notFinal = Rc.withOfficialRates(st, hist('2026-11-23', false)), stale = Rc.withOfficialRates(st, hist('2026-11-20'));
      const none = Rc.withOfficialRates(st, null), bad = Rc.withOfficialRates(st, { asOf: '2026-11-24', final: true, rows: [['2026-11-23', 1345.9]] });
      out = [notFinal.data === st, notFinal.fixed.length, stale.data === st, none.data === st, none.waiting.length, bad.data === st];""")
    assert got == [True, 0, True, True, 1, True]


def test_a_sale_by_amount_keeps_its_won_amount_when_the_rate_is_replaced():
    """A holding put in by amount is sold by 판 금액 in won: its dollar price came from the temporary rate. The replaced rate moves the
    dollar price (price × old ÷ new), so qty × price × fx stays the typed 1,200,000원; a sale by quantity keeps its typed price."""
    got = run("""
      const d = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} }, holdings: [{ t: 'AAPL', nk: 'Apple', cls: 'us' }, { t: 'MSFT', nk: 'MSFT', cls: 'us' }],
        purchases: [], imported: [{ t: 'AAPL', nk: 'Apple', ccy: 'USD', amountWon: 1000000, close: 300, fx: 1300, date: '2026-10-01' }, { t: 'MSFT', nk: 'MSFT', ccy: 'USD', qty: 2 }] };
      const env = { today: T, usDay: '2026-11-23', fx: 1338.0, fxHist: hist('2026-11-20'), stale: false };
      const r = Rc.checkSale(d, 'AAPL', { amountWon: '1200000', date: '2026-11-23' }, { t: 'AAPL', cls: 'us', ccy: 'USD', price: 320 }, env);
      const q = Rc.checkSale(d, 'MSFT', { qty: '1', price: '400', date: '2026-11-23' }, { t: 'MSFT', cls: 'us', ccy: 'USD', price: 410 }, env);
      const st = { v: 2, decks: [{ ...d, sales: [r.rec, q.rec] }] };
      const f = Rc.withOfficialRates(st, hist('2026-11-23'));
      const won = (s) => Math.round(s.qty * s.price * s.fx * 1e6) / 1e6;
      const [a, b] = f.data.decks[0].sales;
      out = { temp: [r.rec.rateTemp, q.rec.rateTemp], before: won(r.rec), after: won(a), fx: [a.fx, b.fx], marks: [a.rateTemp, b.rateTemp],
        msftPrice: b.price, valid: S.validStore(f.data, T) };""")
    assert got["temp"] == [True, True] and got["before"] == 1200000 and got["after"] == 1200000, got
    assert got["fx"] == [1345.9, 1345.9] and got["marks"] == [None, None] and got["msftPrice"] == 400 and got["valid"] is True


def test_records_of_a_stock_taken_out_are_replaced_and_a_removed_record_is_simply_gone():
    got = run("""
      const sale = tmp('s9aaaaaa', 'AAPL', '2026-11-23', { qty: 3, price: 350 });
      const d = deckOf({ holdings: [deckOf().holdings[0]], purchases: [deckOf().purchases[0]],
        history: [{ t: 'AAPL', nk: 'Apple Inc.', out: T, ts: 1795000000000, purchases: [deckOf().purchases[1]], sales: [sale] }] });
      const f = Rc.withOfficialRates(storeOf(d), hist('2026-11-23'));
      const live = deckOf({ purchases: [...deckOf().purchases, tmp('p9aaaaaa', 'AAPL', '2026-11-23')] });
      const items = Rc.recordsOf(live, 'AAPL');
      const del = Rc.withoutRecord(storeOf(live), 'd1', items.find((it) => it.rec.id === 'p9aaaaaa'), T);
      const after = Rc.withOfficialRates(del.data, hist('2026-11-23'));
      out = { hist: f.data.decks[0].history[0].sales[0], fixed: f.fixed.map((x) => x.kind), temp: [Rc.hasTempRate(d), Rc.hasTempRate(f.data.decks[0]), Rc.hasTempRate(live, 'AAPL'), Rc.hasTempRate(live, '005930')],
        del: [del.ok, after.fixed.length, after.waiting.length, after.data === del.data], valid: S.validStore(f.data, T) };""")
    assert got["hist"] == {"id": "s9aaaaaa", "t": "AAPL", "qty": 3, "price": 350, "date": "2026-11-23", "ccy": "USD", "fx": 1345.9}
    assert got["fixed"] == ["sell"] and got["temp"] == [True, False, True, False]
    assert got["del"] == [True, 0, 0, True] and got["valid"] is True


def test_the_mark_survives_the_records_file_and_the_store_check_reads_it():
    got = run("""
      const st = storeOf(deckOf({ purchases: [...deckOf().purchases, tmp('p9aaaaaa', 'AAPL', '2026-11-23')] }));
      const text = S.exportText(st);
      const back = S.parseImport(text, T);
      const f = back ? Rc.withOfficialRates(back, hist('2026-11-23')) : null;
      const bad = (more) => S.validStore(storeOf(deckOf({ purchases: [...deckOf().purchases, { ...tmp('p9aaaaaa', 'AAPL', '2026-11-23'), ...more }] })), T);
      out = { kept: back && pick(back, 'p9aaaaaa').rateTemp, fixed: f && pick(f.data, 'p9aaaaaa'),
        checks: [bad({}), bad({ rateTemp: 'yes' }), bad({ rateTemp: false }), bad({ fx: undefined }), bad({ ccy: 'KRW', fx: undefined }), bad({ noFx: true, fx: undefined })] };""")
    assert got["kept"] is True
    assert got["fixed"] == {"id": "p9aaaaaa", "t": "AAPL", "qty": 2, "price": 300, "date": "2026-11-23", "ccy": "USD", "fx": 1345.9}
    assert got["checks"] == [True, False, False, False, False, False]


def test_two_tabs_never_count_a_replaced_record_twice():
    """Tab B saved a temporary record; tab A (a later start) replaced its rate and saved; tab B, still holding the temporary copy, is told
    about A's write and then saves a change of its own. The next start merges what each kept: one record, once, at its date's rate (the
    current copy's fields win, then withOfficialRates replaces again). Also for a sale of a stock taken out (history: an entry is the
    same entry when its records carry the same ids)."""
    got = run("""
      const sale = tmp('s9aaaaaa', 'AAPL', '2026-11-23', { qty: 3, price: 350 });
      const scenario = async (where, n) => {
        mem.clear();
        const A = await import('./w.mjs?a' + n), B = await import('./w.mjs?b' + n), C = await import('./w.mjs?c' + n);
        const d = where === 'history'
          ? deckOf({ holdings: [deckOf().holdings[0]], purchases: [deckOf().purchases[0]], history: [{ t: 'AAPL', nk: 'Apple Inc.', out: T, ts: 1795000000000, purchases: [deckOf().purchases[1]], sales: [sale] }] })
          : deckOf({ sales: [sale] });
        const st = storeOf(d);
        B.S.writeStore(st, K, T);
        const a = A.Rc.withOfficialRates(A.S.readStore(K, T).data, hist('2026-11-23'));
        A.S.writeStore(a.data, K, T);
        const kept = B.S.keepOwnText(K, localStorage.getItem(K), T);
        const bNext = JSON.parse(JSON.stringify(st));
        bNext.decks[0].purchases.push({ id: 'p7aaaaaa', t: '005930', qty: 1, price: 200000, date: T, ccy: 'KRW' });
        B.S.writeStore(bNext, K, T);
        const c = C.Rc.withOfficialRates(C.S.readStore(K, T).data, hist('2026-11-23'));
        const all = recs(c.data.decks[0]);
        return { kept, sales: all.filter((r) => r.id === 's9aaaaaa').map((r) => [r.fx, r.rateTemp === true]), entries: (c.data.decks[0].history || []).length,
          p7: all.some((r) => r.id === 'p7aaaaaa'), copies: [...mem.keys()].filter((k) => /other|unreadable/.test(k)).length };
      };
      out = { lists: await scenario('lists', 1), history: await scenario('history', 2) };""")
    assert got["lists"] == {"kept": False, "sales": [[1345.9, False]], "entries": 0, "p7": True, "copies": 0}, got
    assert got["history"] == {"kept": False, "sales": [[1345.9, False]], "entries": 1, "p7": True, "copies": 0}, got


def test_records_saved_before_this_release_are_left_as_they_are():
    """A dollar record without the mark (saved by main: Korea's today at data.json fx, or any earlier record) is never touched, even when
    its rate differs from its date's row; won records never carry it."""
    got = run("""
      const st = storeOf(deckOf({ purchases: [...deckOf().purchases, { id: 'p9aaaaaa', t: 'AAPL', qty: 2, price: 300, date: '2026-11-23', ccy: 'USD', fx: 1338.0 }] }));
      const f = Rc.withOfficialRates(st, hist('2027-01-04'));
      out = [f.data === st, f.fixed.length, f.waiting.length, Rc.hasTempRate(st.decks[0])];""")
    assert got == [True, 0, 0, False]


def test_a_merge_by_a_build_before_191_never_doubles_a_sale():
    """#191 review (Opus S1): a tab of the build before #191 (a stale cached copy, or #191 reverted) merges its copy (a sale of a stock
    taken out, still at the temporary rate) with a copy whose rate was replaced. That build compares every field, so it keeps two
    history entries of the same sale; this build's replacement makes them identical and the sale would count twice (내 수익 판 종목
    and 연말 yearGains doubled). On load (app.jsx) store.withoutTwinEntries keeps one entry of the same records (ids), then the rate is
    replaced: the numbers equal the single sale's. Entries without ids are left alone (two equal ones may be two real removals)."""
    got = run("""
      const sale = tmp('s1aaaaaa', 'AAPL', '2026-11-24', { qty: 3, price: 320, fx: 1338.0 });
      const base = () => deckOf({ holdings: [deckOf().holdings[0]], purchases: [deckOf().purchases[0]], removed: [{ t: 'AAPL', at: '2026-11-25', ts: 1764000000000 }],
        history: [{ t: 'AAPL', nk: 'Apple Inc.', out: '2026-11-25', ts: 1764000000000, cls: 'us', purchases: [deckOf().purchases[1]], sales: [sale], divs: [] }] });
      const temp = storeOf(base()), fh = hist('2026-11-24');
      const repl = Rc.withOfficialRates(temp, fh).data;
      const old = OS.mergeTabs(repl, temp, '2026-11-25');                     // the old build: its temporary copy merged with the replaced one
      const tw = S.withoutTwinEntries(old), after = Rc.withOfficialRates(tw.data, fh).data;
      const dup = Rc.withOfficialRates(old, fh).data;                          // without the clean-up
      const q = { pxOf: () => 300, fx: 1340, absent: new Set() };
      const sold = (d) => L.returnsOf(d.decks[0], q).sold, gains = (d) => Tx.yearGains(d.decks).exact;
      const noIds = storeOf(deckOf({ history: [0, 1].map(() => ({ t: 'MSFT', nk: 'MSFT', out: '2026-11-20', imported: { t: 'MSFT', nk: 'MSFT', ccy: 'USD', qty: 2 } })) }));
      const again = S.withoutTwinEntries(tw.data);
      out = { oldEntries: old.decks[0].history.length, dropped: tw.dropped, entries: after.decks[0].history.length,
        sold: [sold(repl), sold(after), sold(dup)], gains: [gains(repl), gains(after), gains(dup)], valid: S.validStore(after, '2026-11-25'),
        noIds: [S.withoutTwinEntries(noIds).dropped.length, S.withoutTwinEntries(noIds).data === noIds], again: [again.dropped.length, again.data === tw.data] };""")
    assert got["oldEntries"] == 2 and got["dropped"] == [{"id": "d1", "t": "AAPL"}] and got["entries"] == 1, got
    assert got["sold"][0] == got["sold"][1] and got["sold"][2] == 2 * got["sold"][0] and got["sold"][0] != 0, got["sold"]
    assert got["gains"][0] == got["gains"][1] and got["gains"][2] == 2 * got["gains"][0] and got["gains"][0] != 0, got["gains"]
    assert got["valid"] is True and got["noIds"] == [0, True] and got["again"] == [0, True]
