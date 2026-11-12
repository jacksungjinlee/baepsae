# -*- coding: utf-8 -*-
"""v19.6a follow-ups from #117 (the fxHist and splits data): the app keeps #117's contract.

- splitsInfo.fixed "out" rows (ratio null): never applied, and a portfolio that stored that split drops it — unless its
  records need it (a sale of the post-split count), then it is kept (never a record lost or refused)
- a record dated with no fxHist row on or before it (2016-01-01..03 under ECOS) is refused, never another day's rate
- rows speak only for dates on or before asOf: any later date refused, except today (fresh data.json fx); an ecos_next
  file whose asOf is the business day before fxDate gives nothing for fxDate
- final false (yahoo_next at the 06:40 publish): a date whose rate would be the unfinished last row is refused
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
        finalLast: Rc.rateFor('2026-11-12', env({ fxHist: { ...yh, final: true } })), today: Rc.rateFor(T, env({ fxHist: yh })) };""")
    assert got["last"] == {"ok": False, "why": "past"} and got["before"] == {"ok": True, "fx": 1333.6}
    assert got["finalLast"] == {"ok": True, "fx": 1338.3} and got["today"] == {"ok": True, "fx": 1338.3}


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
    assert got["removed"] == [{"id": "free", "t": "GMAB", "date": "2018-05-01", "r": 5}]
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
