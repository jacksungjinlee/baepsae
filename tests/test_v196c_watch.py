# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6c 관심 종목 (src/v2/watch.js · watch.jsx parseCond · store.js 의 watch) — Node 에서 돌려봐요.

docs/tasks/v19.6-records-alerts-dark.md Part C, A.1 [Q6] [Q7], Acceptance 3 (adds only; the expected values worked by hand):
- 조건 세 가지의 값: 화면에 보이는 그대로 (한국 주가 원 단위 · 미국 주가 소수 둘째 자리 · PBR 소수 둘째 자리 · 배당수익률 yieldText) 로 견줘요
- 빈 값은 맞지 않고(정보 없음), hitAt 를 만들지도 지우지도 않아요. PBR 0 이하 · 가치 목록의 가드(한국 0.00 · 미국 PER×ROE) 도 빈 값
- 한국 배당수익률은 확인한 dyt 만 (divCheck 가 있는 파일), 미국은 배당수익률 목록과 같은 dy
- hitAt: 신선한 데이터에서 처음 맞은 날 = 그 종목의 가격 날짜, 그날만 오늘 볼 것 줄, 계속 맞으면 다시 안 나옴, 멈춘 날 · 빈 값은 그대로,
  신선한 데이터가 안 맞음을 보이면 지움 → 다시 맞으면 한 번 더
- 저장: 30개까지 · 종류마다 하나 · 다음 판의 종류는 그대로 · 내보내기에 hitAt 없음 · 불러오기는 이 기기 먼저, 그다음 파일 순서대로 30개까지
  (못 넣은 수) · 두 창: 나중 편집이 이기고 뺀 종목이 되살아나지 않고 30개를 넘으면 합쳤어요 · 예전 앱(main, v19.7a)도 그대로 읽고 다시 써요
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
OLD7 = os.path.join(ROOT, "tests", "fixtures", "old_client_v197a", "store.js")   # main c5faa0b (v19.7a): the app a tab may still run


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-watch-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("Wt", "watch.js"), ("Wx", "watch.jsx"), ("En", "engine.js"), ("Rt", "routes.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export * as Old7 from {json.dumps(OLD7)};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, Wt, Wx, En, Rt, Old7 } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


FAKE = """
const mem = new Map(); const warns = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = (m) => warns.push(String(m)); console.info = () => {};
const K = 'baepsae2.v1', T = '2026-11-12';
const stored = () => JSON.parse(mem.get(K));
En.setDataShape({ divCheck: {} });                                   // a v19.1b file: Korean yields are the verified dyt
const kr = (t, more = {}) => ({ t, nk: '종목' + t, cls: 'kr', price: 84200, pbr: 1.3, dyt: 2.5, d1: 2.1, ...more });
const us = (t, more = {}) => ({ t, nk: t + ' Inc.', cls: 'us', price: 148.504, pbr: 3.2, dy: 1.1, d1: 0.4, ...more });
// a load with fresh data (the example page counts as fresh: rules.dayState) or stale data (staleAfter passed, 3 days)
const loadOf = (stocks, { pxDate = T, usPxDate = '2026-11-11', stale = false } = {}) => ({ status: 'ok', preview: !stale,
  data: { pxDate, usPxDate, fx: 1400, stocks }, byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map(),
  fresh: stale ? { stale: true, days: 3 } : { stale: false, days: 0 }, corp: { publishedAt: '2026-11-08T09:00:00+09:00' } });
const W = (entries) => ({ v: 1, decks: [], watch: entries });
"""


def test_each_kind_reads_the_value_as_the_screens_show_it_and_blanks_stay_blank():
    got = run("""
      const v = (s, k) => Wt.watchValue(s, k);
      out = {
        krPx: v(kr('000001', { price: 84200.4 }), 'pxBelow'), usPx: v(us('AAA'), 'pxBelow'), noPx: v(kr('000001', { price: null }), 'pxBelow'),
        pbr: v(kr('000001', { pbr: 0.799 }), 'pbrBelow'), pbr0: v(kr('000001', { pbr: 0 }), 'pbrBelow'), pbrNeg: v(kr('000001', { pbr: -0.4 }), 'pbrBelow'),
        krRound0: v(kr('000001', { pbr: 0.004 }), 'pbrBelow'),                     // 가치 guard: a Korean PBR that rounds to 0.00
        usFar: v(us('AAA', { pbr: 1.0, per: 20, roe: 30 }), 'pbrBelow'),             // 20 × 30 ÷ 100 ÷ 4 = 1.5 > 1.0: the US guard
        usNear: v(us('AAA', { pbr: 1.6, per: 20, roe: 30 }), 'pbrBelow'),
        usBlank: v(us('AAA', { pbr: null, fcur: 'TWD' }), 'pbrBelow'),
        krDy: v(kr('000001', { dyt: 4.25 }), 'dyAtLeast'), krDyTiny: v(kr('000001', { dyt: 0.034 }), 'dyAtLeast'),
        krDyNone: v(kr('000001', { dyt: null, dy: 3.1 }), 'dyAtLeast'), krDyOver: v(kr('000001', { dyt: 31 }), 'dyAtLeast'),
        usDy: v(us('AAA', { dy: 1.06 }), 'dyAtLeast'), usDyOver: v(us('AAA', { dy: 45 }), 'dyAtLeast'),
        fund: v({ t: 'X', cls: 'fund', price: 10 }, 'pxBelow'),
      };
      En.setDataShape({});                                                           // a file without the split check
      out.oldFile = v(kr('000001', { dyt: 4.2 }), 'dyAtLeast');
      En.setDataShape({ divCheck: {} });""")
    assert got == {"krPx": 84200, "usPx": 148.5, "noPx": None, "pbr": 0.8, "pbr0": None, "pbrNeg": None, "krRound0": None,
                   "usFar": None, "usNear": 1.6, "usBlank": None, "krDy": 4.3, "krDyTiny": 0.03, "krDyNone": None, "krDyOver": None,
                   "usDy": 1.1, "usDyOver": None, "fund": None, "oldFile": None}


def test_met_compares_the_shown_value_strictly_below_or_at_least():
    got = run("""const m = Wt.condMet;
      out = [m('pxBelow', 74000, 75000), m('pxBelow', 75000, 75000), m('pbrBelow', 0.79, 0.8), m('pbrBelow', 0.8, 0.8),
             m('dyAtLeast', 4.0, 4), m('dyAtLeast', 3.9, 4), m('pxBelow', 148.5, 150), m('pbrBelow', 0.7, 0.8)];""")
    assert got == [True, False, True, False, True, False, True, True]


def test_states_on_fresh_stale_and_blank_data():
    got = run("""
      const s = kr('000002', { price: 41900, pbr: 0.7, dyt: 4.2 });
      const c = [{ k: 'pxBelow', v: 40000 }, { k: 'pbrBelow', v: 0.8 }, { k: 'dyAtLeast', v: 4 }];
      const fresh = loadOf([s]), stale = loadOf([s], { stale: true });
      const st = (l, f) => c.map((x) => Wt.condState(l, s, x, f)).map((r) => [r.k, r.state, r.val, r.date]);
      const blank = Wt.condState(fresh, kr('000003', { pbr: null }), { k: 'pbrBelow', v: 0.8 }, true);
      out = { fresh: st(fresh, Wt.watchFresh(fresh)), stale: st(stale, Wt.watchFresh(stale)), blank: [blank.state, blank.val],
              isFresh: [Wt.watchFresh(fresh), Wt.watchFresh(stale), Wt.watchFresh({ status: 'fail' })] };""")
    assert got["fresh"] == [["pxBelow", "not", 41900, "2026-11-12"], ["pbrBelow", "met", 0.7, "2026-11-12"], ["dyAtLeast", "met", 4.2, "2026-11-12"]]
    assert got["stale"] == [["pxBelow", "stale", 41900, "2026-11-12"], ["pbrBelow", "stale", 0.7, "2026-11-12"], ["dyAtLeast", "stale", 4.2, "2026-11-12"]]
    assert got["blank"] == ["blank", None] and got["isFresh"] == [True, False, False]


def test_hit_at_first_day_only_survives_stale_and_blank_days_and_clears_on_fresh_not_met():
    """Acceptance 3: hitAt survives a stale day. Days: 12 met (row) · 13 still met (no row) · 14 stale and not met (kept) ·
    15 fresh but PBR blank (kept) · 16 fresh, not met (cleared) · 17 met again (a row once more)."""
    got = run("""
      const t = '000002', cond = { k: 'pbrBelow', v: 0.8 };
      let data = W({ [t]: { at: '2026-11-01', ts: 1762000000000, conds: [cond] } });
      const day = (pxDate, pbr, stale = false) => loadOf([kr(t, { pbr })], { pxDate, stale });
      const step = (l) => { const rows = Wt.watchHits(data, l).map((h) => [h.t, h.k, h.date]); const n = Wt.withWatchHits(data, l); if (n) data = n;
        return { rows, hit: data.watch[t].conds[0].hitAt ?? null, wrote: !!n }; };
      out = [step(day('2026-11-12', 0.7)), step(day('2026-11-12', 0.7)), step(day('2026-11-13', 0.7)), step(day('2026-11-14', 0.9, true)),
             step(day('2026-11-15', null)), step(day('2026-11-16', 0.9)), step(day('2026-11-17', 0.75))];""")
    assert got == [
        {"rows": [["000002", "pbrBelow", "2026-11-12"]], "hit": "2026-11-12", "wrote": True},    # first seen met: the row, and the mark
        {"rows": [["000002", "pbrBelow", "2026-11-12"]], "hit": "2026-11-12", "wrote": False},   # the same close: the row stays, nothing new
        {"rows": [], "hit": "2026-11-12", "wrote": False},                                       # still met the next day: no row again
        {"rows": [], "hit": "2026-11-12", "wrote": False},                                       # stale (and not met): the mark stays
        {"rows": [], "hit": "2026-11-12", "wrote": False},                                       # blank PBR: never clears it
        {"rows": [], "hit": None, "wrote": True},                                                # fresh, not met: cleared
        {"rows": [["000002", "pbrBelow", "2026-11-17"]], "hit": "2026-11-17", "wrote": True},    # met again: one more row
    ]


def test_a_us_stock_hit_is_dated_by_its_own_close_and_rows_keep_list_then_kind_order():
    got = run("""
      const data = W({ '000002': { at: '2026-11-01', conds: [{ k: 'dyAtLeast', v: 4 }, { k: 'pbrBelow', v: 0.8 }] },
                       AAA: { at: '2026-11-05', conds: [{ k: 'pxBelow', v: 150 }] }, BBB: { at: '2026-11-03', conds: [{ k: 'pxBelow', v: 150 }] } });
      const l = loadOf([kr('000002', { pbr: 0.7, dyt: 4.2 }), us('AAA'), us('BBB', { pxd: '2026-11-07' })]);
      out = Wt.watchHits(data, l).map((h) => [h.t, h.k, h.val, h.date]);""")
    # newest first (AAA added 11-05, BBB 11-03, 000002 11-01); within a stock pxBelow · pbrBelow · dyAtLeast; US dated by usPxDate or pxd
    assert got == [["AAA", "pxBelow", 148.5, "2026-11-11"], ["BBB", "pxBelow", 148.5, "2026-11-07"],
                   ["000002", "pbrBelow", 0.7, "2026-11-12"], ["000002", "dyAtLeast", 4.2, "2026-11-12"]]


def test_words_follow_appendix_1_with_the_right_particle():
    got = run("""
      const h = Wt.hitText;
      out = { px: h('pxBelow', 75000, 74000, false), pxUs: h('pxBelow', 150, 148.5, true), pxUs2: h('pxBelow', 150, 148.55, true),
              pbr: h('pbrBelow', 0.8, 0.7, false), dy: h('dyAtLeast', 4, 4.2, false), dy35: Wt.condText('dyAtLeast', 3.5, false),
              pbr1: Wt.condText('pbrBelow', 1, false), now: [Wt.nowValue('pxBelow', 84200, false), Wt.nowValue('pbrBelow', 1.3, false), Wt.nowValue('dyAtLeast', 0.03, false)] };""")
    assert got["px"] == "주가 75,000원 아래 조건에 맞아요. 지금 74,000원이에요."
    assert got["pxUs"] == "주가 $150.00 아래 조건에 맞아요. 지금 $148.50이에요."             # …50 → 영: 받침
    assert got["pxUs2"] == "주가 $150.00 아래 조건에 맞아요. 지금 $148.55예요."             # …5 → 오
    assert got["pbr"] == "PBR 0.8배 아래 조건에 맞아요. 지금 0.70배예요."
    assert got["dy"] == "배당수익률 4% 이상 조건에 맞아요. 지금 4.2%예요."
    assert got["dy35"] == "배당수익률 3.5% 이상" and got["pbr1"] == "PBR 1배 아래"
    assert got["now"] == ["84,200원", "1.30배", "0.03%"]


def test_the_sheet_reads_typed_numbers_by_the_kinds_rules():
    got = run("""const p = Wx.parseCond;
      out = [p('pxBelow', '75,000', false), p('pxBelow', '75000.5', false), p('pxBelow', '150.25', true), p('pxBelow', '150.255', true),
             p('pbrBelow', '0.8', false), p('pbrBelow', '0.85', false), p('dyAtLeast', '4', false), p('dyAtLeast', '101', false),
             p('dyAtLeast', '', false), p('pbrBelow', 'abc', false), p('pxBelow', '0', false), p('pbrBelow', ' 1.5 ', false)].map((x) => (Number.isNaN(x) ? 'bad' : x));""")
    assert got == [75000, "bad", 150.25, "bad", 0.8, "bad", 4, "bad", None, "bad", "bad", 1.5]


def test_the_store_checks_the_watch_part_and_sets_a_bad_one_aside():
    got = run("""
      const ok = (w) => S.watchProblem(w, T);
      const many = Object.fromEntries(Array.from({ length: 31 }, (_, i) => [String(100000 + i), { at: T }]));
      out = {
        good: ok({ '005930': { at: T, ts: 1762900000000, nk: '삼성전자', conds: [{ k: 'pxBelow', v: 75000, hitAt: '2026-11-11' }, { k: 'pbrBelow', v: 0.8 }] },
                   AAPL: { at: '2026-11-01', conds: [{ k: 'pxBelow', v: 150.25 }, { k: 'dyAtLeast', v: 3.5 }] } }),
        later: ok({ '005930': { at: T, conds: [{ k: 'perBelow', v: 'anything' }], someday: true } }),     // a later version's kind and field: kept
        many: ok(many), twice: ok({ '005930': { at: T, conds: [{ k: 'pbrBelow', v: 0.8 }, { k: 'pbrBelow', v: 0.9 }] } }),
        dec: ok({ '005930': { at: T, conds: [{ k: 'pbrBelow', v: 0.85 }] } }), zero: ok({ '005930': { at: T, conds: [{ k: 'pxBelow', v: 0 }] } }),
        future: ok({ '005930': { at: '2026-11-13' } }), hit: ok({ '005930': { at: T, conds: [{ k: 'pxBelow', v: 1, hitAt: 'yesterday' }] } }),
        code: ok({ 'x y': { at: T } }),
      };
      const r = S.checkStore({ v: 1, decks: [], notes: { '005930': { text: '메모', at: T } }, watch: { '005930': { at: '2026-11-13' } } }, T);
      out.read = { notes: !!r.data.notes, watch: r.data.watch ?? null, problems: r.problems };""")
    assert got["good"] is None and got["later"] is None
    assert got["many"] == "more than 30 stocks" and "two conditions of one kind" in got["twice"] and "pbrBelow" in got["dec"]
    assert "pxBelow" in got["zero"] and "not after today" in got["future"] and "hitAt" in got["hit"] and "stock code" in got["code"]
    assert got["read"] == {"notes": True, "watch": None, "problems": ["watch (the watch list): 005930: the date added must be a real date, not after today"]}


def test_add_remove_and_conditions_edit_the_store_purely():
    got = run("""
      let d = { v: 1, decks: [] };
      const a = S.withWatchAdd(d, '005930', '삼성전자', T, 1762900000000);
      const twice = S.withWatchAdd(a, '005930', '삼성전자', T, 1762900000001);
      const full = { v: 1, decks: [], watch: Object.fromEntries(Array.from({ length: 30 }, (_, i) => [String(100000 + i), { at: T }])) };
      const c1 = S.withWatchConds(a, '005930', [{ k: 'pbrBelow', v: 0.8 }, { k: 'pxBelow', v: 75000 }], T, 1762900001000);
      const hit = { ...c1, watch: { '005930': { ...c1.watch['005930'], conds: c1.watch['005930'].conds.map((c) => ({ ...c, hitAt: '2026-11-11' })) } } };
      const c2 = S.withWatchConds(hit, '005930', [{ k: 'pxBelow', v: 75000 }, { k: 'pbrBelow', v: 0.9 }], T, 1762900002000);
      const bad = S.withWatchConds(a, '005930', [{ k: 'pbrBelow', v: 0.85 }], T, 1);
      const r = S.withWatchRemove(c2, '005930', T, 1762900003000);
      const back = S.withWatchAdd(r, '005930', '삼성전자', T, 1762900004000);
      out = { a: a.watch, twice, full: S.withWatchAdd(full, '005380', '현대차', T, 1), c1: c1.watch['005930'], c2: c2.watch['005930'].conds, bad,
              r: [r.watch ?? null, r.gone], back: [Object.keys(back.watch), back.gone ?? null], valid: [a, c1, c2, r, back].every((x) => S.validStore(x, T)) };""")
    assert got["a"] == {"005930": {"at": "2026-11-12", "ts": 1762900000000, "nk": "삼성전자"}}
    assert got["twice"] is None and got["full"] is None and got["bad"] is None
    assert got["c1"] == {"at": "2026-11-12", "nk": "삼성전자", "ts": 1762900001000, "conds": [{"k": "pxBelow", "v": 75000}, {"k": "pbrBelow", "v": 0.8}]}
    # the price condition did not change: it keeps its mark; the PBR condition changed (0.8 → 0.9): it starts without
    assert got["c2"] == [{"k": "pxBelow", "v": 75000, "hitAt": "2026-11-11"}, {"k": "pbrBelow", "v": 0.9}]
    assert got["r"] == [None, {"watch": {"005930": {"at": "2026-11-12", "ts": 1762900003000}}}]
    assert got["back"] == [["005930"], None] and got["valid"] is True


def test_a_records_file_carries_the_list_without_hitAt_and_reads_back_after_a_reload():
    got = run("""
      const d = { v: 1, decks: [], watch: { '005930': { at: T, ts: 5, nk: '삼성전자', conds: [{ k: 'pbrBelow', v: 0.8, hitAt: '2026-11-11' }] } },
                  gone: { watch: { '000660': { at: T, ts: 4 } } } };
      const text = S.exportText(d);
      S.writeStore(d, K, T);
      const re = S.readStore(K, T);
      const inc = S.parseImport(text, T);
      const into = S.mergeStores({ v: 1, decks: [] }, inc, 1762900000000, [], T);
      out = { file: JSON.parse(text), reload: re.data.watch, gone: re.data.gone, into: into.watch, intoGone: into.gone ?? null, v: re.data.v };""")
    assert got["file"] == {"v": 1, "decks": [], "watch": {"005930": {"at": "2026-11-12", "ts": 5, "nk": "삼성전자", "conds": [{"k": "pbrBelow", "v": 0.8}]}}}
    assert got["reload"] == {"005930": {"at": "2026-11-12", "ts": 5, "nk": "삼성전자", "conds": [{"k": "pbrBelow", "v": 0.8, "hitAt": "2026-11-11"}]}}
    assert got["gone"] == {"watch": {"000660": {"at": "2026-11-12", "ts": 4}}} and got["v"] == 1      # no version-2 part: still tagged 1
    assert got["into"] == got["file"]["watch"] and got["intoGone"] is None


def test_import_keeps_this_devices_list_first_then_the_files_up_to_30_and_counts_the_rest():
    got = run("""
      const mine = Object.fromEntries(Array.from({ length: 27 }, (_, i) => [String(100000 + i), { at: '2026-11-01', ts: 1000 + i }]));
      mine['005930'] = { at: '2026-11-02', conds: [{ k: 'pxBelow', v: 70000, hitAt: '2026-11-11' }] };       // 28 on this device
      // the file: 005930 (this device's stays), then five new ones; in the file's order (newest first): 000660, AAPL, 035720, MSFT, 051910
      const file = { '005930': { at: '2026-11-09', conds: [{ k: 'pxBelow', v: 99999 }] }, '051910': { at: '2026-11-01' }, MSFT: { at: '2026-11-03' },
                     '035720': { at: '2026-11-05' }, AAPL: { at: '2026-11-07' }, '000660': { at: '2026-11-09', ts: 9 } };
      const cur = { v: 1, decks: [], watch: mine, gone: { watch: { AAPL: { at: '2026-11-10', ts: 1762700000000 } } } };
      const inc = S.parseImport(JSON.stringify({ v: 1, decks: [], watch: file }), T);
      const m = S.mergeStores(cur, inc, 1762900000000, [], T);
      out = { n: Object.keys(m.watch).length, dropped: m[S.WATCH_DROPPED], keptMine: m.watch['005930'], added: S.watchOrder(m.watch).filter((t) => !mine[t]),
              aapl: m.watch.AAPL, gone: m.gone ?? null, ok: S.validStore({ ...m }, T) };""")
    assert got["n"] == 30 and got["dropped"] == 3
    assert got["keptMine"] == {"at": "2026-11-02", "conds": [{"k": "pxBelow", "v": 70000, "hitAt": "2026-11-11"}]}   # this device's entry stays
    assert got["added"] == ["000660", "AAPL"]                     # the file's own order (newest first) until 30: 035720, MSFT, 051910 did not fit
    # AAPL had been taken out on this device: it comes back as an edit made now (after the mark) and its mark goes
    assert got["aapl"] == {"at": "2026-11-07", "ts": 1762900000000} and got["gone"] is None and got["ok"] is True


def test_two_tabs_keep_the_later_edit_and_a_removed_stock_never_comes_back():
    got = run("""
      // this tab read base; another tab then wrote base + 005930; this tab (not knowing) writes base + 000660
      const base = { v: 1, decks: [], watch: { '035720': { at: '2026-11-01', ts: 100 } } };
      S.writeStore(base, K, T);
      mem.set(K, JSON.stringify(S.withWatchAdd(base, '005930', '삼성전자', T, 200)));
      S.writeStore(S.withWatchAdd(base, '000660', 'SK하이닉스', T, 300), K, T);
      const kept = [...mem.keys()].filter((k) => k.includes('.other.')).length;
      const next = S.readStore(K, T);                       // the next start merges the other tab's text back
      // a removal (a mark at 400) against a stale copy that still holds 035720 (added at 100) and adds 051910
      const r = S.withWatchRemove(next.data, '035720', T, 400);
      const stale = S.withWatchAdd(next.data, '051910', 'LG화학', T, 350);
      const m1 = S.mergeTabs(stale, r, T), m2 = S.mergeTabs(r, stale, T);
      out = { kept, first: S.watchOrder(next.data.watch), restored: next.restored,
              m1: [S.watchOrder(m1.watch), m1.gone], m2: [S.watchOrder(m2.watch), m2.gone] };""")
    assert got["kept"] == 1 and got["first"] == ["000660", "005930", "035720"] and got["restored"] is True
    mark = {"watch": {"035720": {"at": "2026-11-12", "ts": 400}}}
    # 035720 stays out whichever copy leads (the mark at 400 is later than its entry at 100); 051910 comes in; newest first (ts 350 · 300 · 200)
    assert got["m1"] == [["051910", "000660", "005930"], mark] and got["m2"] == [["051910", "000660", "005930"], mark]


def test_a_tab_merge_over_30_keeps_the_current_copys_stocks_first_and_says_so():
    got = run("""
      const list = (from, n, ts) => Object.fromEntries(Array.from({ length: n }, (_, i) => [String(from + i), { at: '2026-11-01', ts: ts + i }]));
      const cur = { v: 1, decks: [], watch: list(100000, 29, 1000) };
      const other = { v: 1, decks: [], watch: { ...list(100000, 28, 1000), ...list(200000, 2, 5000) } };       // 30: a valid copy
      const m = S.mergeTabs(other, cur, T);
      // the stored copy (other) left aside: the next start merges it, the cap leaves one out, and the screens say 합쳤어요
      S.writeStore(cur, K, T); S.readStore(K, T);
      mem.set(K + '.other.1', JSON.stringify(other));
      const r = S.readStore(K, T);
      out = { n: Object.keys(m.watch).length, newest: S.watchOrder(m.watch).slice(0, 1), restored: r.restored, keptCopy: [...mem.keys()].some((k) => k.includes('.restored.')) };""")
    assert got["n"] == 30 and got["newest"] == ["200001"]           # 29 of the current copy, then the other copy's newest of its two
    assert got["restored"] is True and got["keptCopy"] is True      # said once; the other copy is kept under .restored.


def test_the_old_app_main_v197a_reads_keeps_and_writes_back_the_watch_list_and_its_marks():
    got = run("""
      const d = { v: 1, decks: [], watch: { '005930': { at: T, ts: 5, nk: '삼성전자', conds: [{ k: 'pbrBelow', v: 0.8, hitAt: '2026-11-11' }] } },
                  gone: { watch: { '000660': { at: T, ts: 4 } } } };
      S.writeStore(d, K, T);
      const old = Old7.readStore(K, T);
      const n = Old7.withNote(old.data, '005930', '메모', T, 6);
      Old7.writeStore(n, K, T);
      const after = stored();
      const back = S.readStore(K, T);
      out = { oldLocked: old.locked, watch: after.watch, gone: after.gone, newRead: back.data.watch, note: back.data.notes['005930'].text };""")
    assert got["oldLocked"] is False
    assert got["watch"] == {"005930": {"at": "2026-11-12", "ts": 5, "nk": "삼성전자", "conds": [{"k": "pbrBelow", "v": 0.8, "hitAt": "2026-11-11"}]}}
    assert got["gone"] == {"watch": {"000660": {"at": "2026-11-12", "ts": 4}}} and got["newRead"] == got["watch"] and got["note"] == "메모"


def test_an_old_tab_writing_over_a_newer_watch_list_loses_nothing_on_the_next_start():
    got = run("""
      const base = { v: 1, decks: [] };
      S.writeStore(base, K, T); S.readStore(K, T);
      const old = Old7.readStore(K, T);                                 // the old tab reads the records first
      const a = S.withWatchAdd(S.readStore(K, T).data, '005930', '삼성전자', T, 200);
      S.writeStore(a, K, T);                                            // this app adds a stock (its .mine keeps the text)
      Old7.writeStore(Old7.withNote(old.data, '000660', '메모', T, 300), K, T);   // the old tab writes over from its older copy
      const r = S.readStore(K, T);
      out = { stored: stored().watch ?? null, merged: r.data.watch, note: r.data.notes['000660'].text, restored: r.restored };""")
    assert got["merged"] == {"005930": {"at": "2026-11-12", "ts": 200, "nk": "삼성전자"}} and got["note"] == "메모"
    assert got["restored"] is True


def test_the_watch_screen_has_its_own_address_under_stocks():
    got = run("""out = ['#stocks/watch', '#stocks/watch/x', '#stocks/WATCH'].map((h) => Rt.parseHash(h));""")
    assert got[0] == {"tab": "stocks", "sub": "watch", "about": False, "known": True}
    assert got[1]["known"] is False and got[2]["code"] == "WATCH"           # a code-shaped address is a company page, as before


# ── 새 파일은 색을 직접 쓰지 않아요 (Jack, 2026-11-13; tests/test_v196a_colours.py 와 같은 검사) ──
HEX = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_])")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(", re.I)
NAMED = re.compile(r"""["'`](?:white|black|red|blue|green|gray|grey|silver|navy|orange|yellow|purple|transparent|currentcolor)["'`]""", re.I)


@pytest.mark.parametrize("path", ["src/v2/watch.js", "src/v2/watch.jsx"])
def test_no_literal_colour_in_the_new_v196c_files(path):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, path, "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    hits = HEX.findall(r.stdout) + FUNC.findall(r.stdout) + NAMED.findall(r.stdout)
    assert not hits, f"{path}: 색을 직접 썼어요 {hits[:5]} (src/ui/tokens.js 의 토큰으로)"


# ── 진짜 데이터 (저장소의 data.json: 매일 실행이 쓰는 파일) — 날마다 바뀌어도 맞아야 하는 것만 ──
def test_on_todays_real_data_every_value_is_a_shown_number_or_blank_and_pipeline_blanks_stay_blank():
    p = os.path.join(ROOT, "data.json")
    if not os.path.isfile(p):
        pytest.skip("data.json 이 없어요")
    got = run(f"""
      const fs = await import('fs');
      const d = JSON.parse(fs.readFileSync({json.dumps(p)}, 'utf8'));
      En.setDataShape(d);
      const out2 = {{ n: 0, kinds: {{}}, bad: [], leak: [] }};
      for (const s of d.stocks) {{
        if (s.cls !== 'kr' && s.cls !== 'us') continue;
        out2.n++;
        for (const k of Wt.WATCH_KINDS) {{
          const v = Wt.watchValue(s, k);
          const c = out2.kinds[k] = out2.kinds[k] || {{ value: 0, blank: 0 }};
          if (v == null) {{ c.blank++; continue; }}
          c.value++;
          const dec = k === 'pxBelow' ? (s.cls === 'us' ? 2 : 0) : k === 'pbrBelow' ? 2 : (v > 0 && v < 0.1 ? 2 : 1);
          if (!(Number.isFinite(v) && v >= 0 && Math.abs(v * 10 ** dec - Math.round(v * 10 ** dec)) < 1e-6) || (k !== 'dyAtLeast' && !(v > 0))) out2.bad.push([s.t, k, v]);
        }}
        // numbers the pipeline blanked never come back as a value
        const cut = (s.fgnCut && typeof s.fgnCut === 'object') ? s.fgnCut : {{}};
        if ((s.fcur && s.fcur !== 'USD') || s.pbrZero === true || cut.pbr || s.unitChk) {{ if (Wt.watchValue(s, 'pbrBelow') != null && s.pbr == null) out2.leak.push(s.t); }}
        if (s.cls === 'kr' && s.dyt == null && Wt.watchValue(s, 'dyAtLeast') != null) out2.leak.push(s.t + ':dy');
      }}
      out = out2;""")
    assert got["n"] > 1000 and not got["bad"] and not got["leak"], (got["bad"][:5], got["leak"][:5])
    k = got["kinds"]
    assert k["pxBelow"]["value"] > 0.95 * got["n"] and k["pbrBelow"]["value"] > 0 and k["dyAtLeast"]["value"] > 0, k
