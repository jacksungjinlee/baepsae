# -*- coding: utf-8 -*-
"""v19.6a follow-ups from #117 (the fxHist and splits data): the app keeps #117's contract.

- splitsInfo.fixed "out" rows (ratio null): never applied, and a portfolio that stored that split drops it — unless its
  records need it (a sale of the post-split count), then it is kept (never a record lost or refused)
- a record dated with no fxHist row on or before it (2016-01-01..03 under ECOS) is refused, never another day's rate
- rows speak only for dates on or before asOf: any later date refused, except today (fresh data.json fx); an ecos_next
  file whose asOf is the business day before fxDate gives nothing for fxDate
- final not true (yahoo_next at the 06:40 publish says false; a missing flag is not final either): a date whose rate would be
  the unfinished last row is refused
- dates are US trading dates: a record dated on a split's date is already at the new count
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
        tmp = tempfile.mkdtemp(prefix="baepsae-fu-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("H", "held.js"), ("L", "lots.js"), ("Rc", "records.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/fu.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, H, L, Rc } from './fu.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


FAKE = """
console.warn = () => {}; console.info = () => {};
const T = '2026-11-13';
// ecos_close-shaped history: first row 2016-01-04 (ECOS's first business day), asOf the last row
const ECOS = { asOf: '2026-11-12', final: true, rows: [['2016-01-04', 1187.7], ['2016-01-05', 1188.0], ['2026-11-10', 1335.0], ['2026-11-11', 1333.6], ['2026-11-12', 1330.7]] };
const env = (o = {}) => ({ today: T, fx: 1338.3, fxDate: '2026-11-12', fxHist: ECOS, stale: false, ...o });
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const P = (id, qty, date) => ({ id, t: 'GMAB', qty, price: 30, date, ccy: 'USD', fx: 1300 });
"""


def test_no_row_on_or_before_the_date_is_refused():
    got = run("""out = ['2015-12-31', '2016-01-01', '2016-01-02', '2016-01-03', '2016-01-04', '2016-01-06'].map((d) => [d, Rc.rateFor(d, env())]);""")
    assert got[0] == ["2015-12-31", {"ok": True, "fx": None, "before": True}]                      # before 2016: no rate, marked noFx
    assert [g[1] for g in got[1:4]] == [{"ok": False, "why": "past"}] * 3                          # ECOS has no row yet: refused
    assert got[4][1] == {"ok": True, "fx": 1187.7} and got[5][1] == {"ok": True, "fx": 1188.0}


def test_rows_speak_only_up_to_as_of_and_today_uses_fresh_fx():
    got = run("""const next = { asOf: '2026-11-11', final: true, rows: [['2026-11-10', 1336.0], ['2026-11-11', 1336.7]] };   // ecos_next: asOf before fxDate
      out = { after: Rc.rateFor('2026-11-12', env({ fxHist: next })), onAsOf: Rc.rateFor('2026-11-11', env({ fxHist: next })),
        today: Rc.rateFor(T, env({ fxHist: next })), staleToday: Rc.rateFor(T, env({ fxHist: next, stale: true })),
        afterEcos: Rc.rateFor('2026-11-12', env({ today: '2026-11-14' })), badAsOf: Rc.rateFor('2026-11-11', env({ fxHist: { ...ECOS, asOf: '2026-11-13' } })) };""")
    assert got["after"] == {"ok": False, "why": "past"}                                               # never 11-11's row for 11-12
    assert got["onAsOf"] == {"ok": True, "fx": 1336.7}
    assert got["today"] == {"ok": True, "fx": 1338.3} and got["staleToday"] == {"ok": False, "why": "today"}
    assert got["afterEcos"] == {"ok": True, "fx": 1330.7}                                             # 11-12 is asOf: its own row
    assert got["badAsOf"] == {"ok": False, "why": "past"}                                             # asOf must be the last row


def test_an_unfinished_last_row_is_not_a_rate():
    got = run("""const yh = { asOf: '2026-11-12', final: false, rows: [['2026-11-10', 1335.0], ['2026-11-11', 1333.6], ['2026-11-12', 1338.3]] };
      out = { last: Rc.rateFor('2026-11-12', env({ fxHist: yh })), before: Rc.rateFor('2026-11-11', env({ fxHist: yh })),
        finalLast: Rc.rateFor('2026-11-12', env({ fxHist: { ...yh, final: true } })), today: Rc.rateFor(T, env({ fxHist: yh })),
        odd: [undefined, null, 'true', 1].map((f) => Rc.rateFor('2026-11-12', env({ fxHist: { ...yh, final: f } }))) };""")
    assert got["last"] == {"ok": False, "why": "past"} and got["before"] == {"ok": True, "fx": 1333.6}
    assert got["finalLast"] == {"ok": True, "fx": 1338.3} and got["today"] == {"ok": True, "fx": 1338.3}
    assert got["odd"] == [{"ok": False, "why": "past"}] * 4                                         # final 은 true 일 때만 (round-2)


def test_out_rows_are_never_applied_and_a_stored_one_leaves_when_the_records_allow():
    got = run("""const data = { splits: [['GMAB', '2018-05-01', 5], ['AAPL', '2020-08-31', 4]],
        splitsInfo: { fixed: [['GMAB', '2018-05-01', null, '빼요'], ['HON', '2026-06-29', 0.5, '1:2'], ['bad'], ['X', 'nodate', null, '']] } };
      const ds = L.dataSplits(data);
      const deck = (id, sales) => ({ id, name: id, createdAt: '2018-01-02', planFx: 1300, holdings: [{ t: 'GMAB', nk: 'Genmab', target: 1, rules: band(1) }],
        purchases: [P('p1aaaaaa', 10, '2018-01-02')], sales, splits: [{ t: 'GMAB', date: '2018-05-01', r: 5 }, { t: 'GMAB', date: '2018-05-08', r: 2 }] });
      const free = deck('free', []), needs = deck('needs', [{ id: 's1aaaaaa', t: 'GMAB', qty: 60, price: 10, date: '2019-01-02', ccy: 'USD', fx: 1100 }]);
      const store = { v: 2, decks: [free, needs] };
      const r = L.withoutOutSplits(store, L.outSplits(data), T);
      out = { list: ds.list.map((s) => s.t), out: ds.out, outs: L.outSplits(data), removed: r.removed, kept: r.kept.map((k) => [k.id, k.t, k.date]),
        freeSplits: r.data.decks[0].splits, needsSame: r.data.decks[1] === needs, valid: S.validStore(r.data, T),
        heldFree: H.heldUnits(r.data.decks[0]).get('GMAB') / 10000, none: L.withoutOutSplits(store, [], T).data === store };""")
    assert got["list"] == ["AAPL"] and got["out"] == 1 and got["outs"] == [{"t": "GMAB", "date": "2018-05-01"}]
    assert got["removed"] == [{"id": "free", "t": "GMAB", "date": "2018-05-01", "r": 5, "held": {"t": "GMAB", "before": 1000000, "after": 200000}}]
    assert got["freeSplits"] == [{"t": "GMAB", "date": "2018-05-08", "r": 2}]                       # only the named date (not the one a week on)
    assert got["heldFree"] == 20                                                                       # 10 × 2 (the 05-08 split only)
    assert got["kept"] == [["needs", "GMAB", "2018-05-01"]] and got["needsSame"] is True               # its 60-share sale needs the split
    assert got["valid"] is True and got["none"] is True


def test_a_record_on_the_split_day_is_already_at_the_new_count():
    got = run("""const d = { id: 'd', name: 'd', createdAt: '2020-08-01', planFx: 1300, holdings: [{ t: 'AAPL', nk: 'Apple', target: 1, rules: band(1) }],
        purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 1, price: 500, date: '2020-08-28', ccy: 'USD', fx: 1180 },
                    { id: 'p2aaaaaa', t: 'AAPL', qty: 4, price: 125, date: '2020-08-31', ccy: 'USD', fx: 1185 }],
        splits: [{ t: 'AAPL', date: '2020-08-31', r: 4 }] };
      out = H.heldUnits(d).get('AAPL') / 10000;""")
    assert got == 8                                                                                    # 1 × 4 (before) + 4 (on the day, new count)


# ---------------- round-2 review: a wrong-date split, one split at a time, the pipeline's 10-day window ----------------
GMAB = """const deckG = (id, purchases, sales, splits, more = {}) => ({ id, name: id, createdAt: '2018-01-02', planFx: 1300,
        holdings: [{ t: 'GMAB', nk: 'Genmab', target: 1, rules: band(1) }], purchases, sales, splits, ...more });
      const Sx = (id, t, qty, date) => ({ id, t, qty, price: 10, date, ccy: 'USD', fx: 1100 });
      // what the screens count: the stored splits with data.json's on top (app.jsx view)
      const shown = (store, data, i = 0, t = 'GMAB') => H.heldUnits(L.withDataSplits(store, L.dataSplits(data).list, T).decks[i]).get(t) / 10000;
      const fix = (store, data) => L.withoutOutSplits(store, L.outSplits(data), T, L.dataSplits(data).list);
"""


def test_a_wrong_date_split_a_sale_needs_moves_to_the_corrected_date():
    """[A1] stored 2018-05-01 x5 (wrong date); data.json: an "out" row for 05-01 and the corrected 05-20 x5 (the reviewer's
    case, 19 days on: #117's RUNBOOK puts no limit on how far a corrected date is) or 05-09 x5 (within 10 days). Bought 10
    before, sold 40 after: the stored split moves to the corrected date and the screens read 10, never 210."""
    got = run(GMAB + """const out = (d) => ({ splits: [['GMAB', d, 5]], splitsInfo: { fixed: [['GMAB', '2018-05-01', null, 'wrong date']] } });
      const res = {};
      for (const d of ['2018-05-20', '2018-05-09']) {
        const store = { v: 2, decks: [deckG('x1', [P('p1aaaaaa', 10, '2018-04-02')], [Sx('s1aaaaaa', 'GMAB', 40, '2018-06-01')], [{ t: 'GMAB', date: '2018-05-01', r: 5 }])] };
        const r = fix(store, out(d));
        res[d] = { before: shown(store, out(d)), moved: r.moved, removed: r.removed.length, kept: r.kept.length, splits: r.data.decks[0].splits,
          after: shown(r.data, out(d)), valid: S.validStore(r.data, T), again: fix(r.data, out(d)).data === r.data };
      }
      out = res;""".replace("const out = (d)", "const outD = (d)").replace("out(d)", "outD(d)"))
    far, near = got["2018-05-20"], got["2018-05-09"]
    assert far["before"] == 210                                                                       # the bug: both splits applied
    assert far["moved"] == [{"id": "x1", "t": "GMAB", "date": "2018-05-01", "r": 5, "to": "2018-05-20", "held": {"t": "GMAB", "before": 2100000, "after": 100000}}]
    assert far["splits"] == [{"t": "GMAB", "date": "2018-05-20", "r": 5}] and far["after"] == 10 and far["valid"] is True and far["again"] is True
    assert far["removed"] == 0 and far["kept"] == 0
    assert near["before"] == 10 and near["after"] == 10 and near["splits"] == [{"t": "GMAB", "date": "2018-05-09", "r": 5}]   # 10 days: one split even before
    assert near["moved"][0]["held"] == {"t": "GMAB", "before": 100000, "after": 100000}


def test_a_record_between_the_two_dates_keeps_the_old_date_and_the_new_row_is_not_applied():
    """[A1] the sale (40) is dated 05-05, between the wrong 05-01 and the corrected 05-09: it needs the old date. The stored
    split stays at 05-01 and the corrected row (within the 10-day window) is not applied on top (10, not 50 x 5 − 40).
    A corrected row further than 10 days away is a known limit (RUNBOOK): kept, both apply (50, not 10), and the console
    names it (also)."""
    got = run(GMAB + """const outD = (d) => ({ splits: [['GMAB', d, 5]], splitsInfo: { fixed: [['GMAB', '2018-05-01', null, 'wrong date']] } });
      const mk = () => ({ v: 2, decks: [deckG('x2', [P('p1aaaaaa', 10, '2018-04-02')], [Sx('s1aaaaaa', 'GMAB', 40, '2018-05-05')], [{ t: 'GMAB', date: '2018-05-01', r: 5 }])] });
      const near = fix(mk(), outD('2018-05-09')), far = fix(mk(), outD('2018-05-20'));
      out = { near: { kept: near.kept, moved: near.moved.length, same: near.data.decks[0].splits, shown: shown(near.data, outD('2018-05-09')) },
        far: { kept: far.kept.map((k) => [k.t, k.date, k.also]), shown: shown(far.data, outD('2018-05-20')) } };""")
    k = got["near"]["kept"]
    assert len(k) == 1 and k[0]["t"] == "GMAB" and k[0]["date"] == "2018-05-01" and "GMAB" in k[0]["why"] and "also" not in k[0]
    assert got["near"]["moved"] == 0 and got["near"]["same"] == [{"t": "GMAB", "date": "2018-05-01", "r": 5}] and got["near"]["shown"] == 10
    assert got["far"]["kept"] == [["GMAB", "2018-05-01", ["2018-05-20"]]] and got["far"]["shown"] == 50     # 10 x 25 − 40 x 5: known limit, named in the console


def test_each_stored_split_is_decided_on_its_own():
    """[A2] two "out" splits in one portfolio: GMAB's is needed (a sale of the post-split count), AAA's is not. AAA's leaves
    (11 shares, not 21), GMAB's stays, and the reason names GMAB."""
    got = run(GMAB + """const data = { splits: [], splitsInfo: { fixed: [['GMAB', '2018-05-01', null, 'x'], ['AAA', '2019-05-01', null, 'x']] } };
      const d = { id: 'x2', name: 'x2', createdAt: '2018-01-02', planFx: 1300,
        holdings: [{ t: 'GMAB', nk: 'Genmab', target: 0.5, rules: band(0.5) }, { t: 'AAA', nk: 'AAA', target: 0.5, rules: band(0.5) }],
        purchases: [P('p1aaaaaa', 10, '2018-04-02'), { ...P('p2aaaaaa', 10, '2019-04-02'), t: 'AAA' }, { ...P('p3aaaaaa', 1, '2019-06-02'), t: 'AAA' }],
        sales: [Sx('s1aaaaaa', 'GMAB', 40, '2018-06-01')], splits: [{ t: 'GMAB', date: '2018-05-01', r: 5 }, { t: 'AAA', date: '2019-05-01', r: 2 }] };
      const store = { v: 2, decks: [d] };
      const r = fix(store, data);
      out = { removed: r.removed.map((x) => [x.t, x.held]), kept: r.kept.map((x) => [x.t, x.why]), splits: r.data.decks[0].splits,
        aaa: H.heldUnits(r.data.decks[0]).get('AAA') / 10000, gmab: H.heldUnits(r.data.decks[0]).get('GMAB') / 10000, valid: S.validStore(r.data, T) };""")
    assert got["removed"] == [["AAA", {"t": "AAA", "before": 210000, "after": 110000}]] and got["aaa"] == 11
    assert len(got["kept"]) == 1 and got["kept"][0][0] == "GMAB" and "GMAB" in got["kept"][0][1] and "AAA" not in got["kept"][0][1]
    assert got["splits"] == [{"t": "GMAB", "date": "2018-05-01", "r": 5}] and got["gmab"] == 10 and got["valid"] is True


def test_the_same_split_window_is_the_pipelines_10_days():
    got = run("""const d = (date) => ({ id: 'w', name: 'w', createdAt: '2026-08-01', planFx: 1300, holdings: [{ t: 'NVDA', nk: 'NVIDIA', target: 1, rules: band(1) }],
        purchases: [{ ...P('p1aaaaaa', 1, '2026-08-03'), t: 'NVDA' }], splits: [{ t: 'NVDA', date: '2026-09-01', r: 10 }] });
      const seen = (date) => H.heldUnits(L.withDataSplits({ v: 2, decks: [d()] }, [{ t: 'NVDA', date, r: 10 }], T).decks[0]).get('NVDA') / 10000;
      out = { days: H.SAME_SPLIT_DAYS, ten: seen('2026-09-11'), eleven: seen('2026-09-12') };""")
    assert got == {"days": 10, "ten": 10, "eleven": 100}                                           # fetch_data.py SPLIT_SAME_EVENT_DAYS
