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
            # a second tab of this app: the same files in another place, so it has its own module state (what it last read or wrote)
            tab2 = os.path.join(tmp, "tab2")
            os.makedirs(tab2)
            for m in ("store.js", "held.js", "dcf.js"):
                shutil.copy(os.path.join(ROOT, "src", "v2", m), tab2)
            f.write(f"export * as S2 from {json.dumps(os.path.join(tab2, 'store.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, S2, Wt, Wx, En, Rt, Old7 } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
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
      out = { rows: Wt.watchHits(data, l).map((h) => [h.t, h.k, h.val, h.date]), marks: [...Wt.watchMarks(data, l)].map((m) => m[0]),
              bbb: Wt.condState(l, l.byT.get('BBB'), { k: 'pxBelow', v: 150 }, true).state, locked: Wt.watchHits(data, l, undefined, false) };""")
    # newest first (AAA added 11-05, 000002 11-01); within a stock pxBelow · pbrBelow · dyAtLeast; a US stock dated by usPxDate.
    # BBB is priced at an earlier close than its market's (pxd: a halt): not today's price, so never judged: no mark, no row
    assert got["rows"] == [["AAA", "pxBelow", 148.5, "2026-11-11"], ["000002", "pbrBelow", 0.7, "2026-11-12"], ["000002", "dyAtLeast", 4.2, "2026-11-12"]]
    assert got["bbb"] == "stale" and sorted(got["marks"]) == ["000002|dyAtLeast", "000002|pbrBelow", "AAA|pxBelow"]
    assert got["locked"] == []                       # records that cannot be written: no row (its mark could not stop it repeating)


def test_words_follow_appendix_1_with_the_right_particle():
    got = run("""
      const h = Wt.hitText;
      out = { px: h('pxBelow', 75000, 74000, false), pxUs: h('pxBelow', 150, 148.5, true), pxUs2: h('pxBelow', 150, 148.55, true),
              pbr: h('pbrBelow', 0.8, 0.7, false), dy: h('dyAtLeast', 4, 4.2, false), dy35: Wt.condText('dyAtLeast', 3.5, false),
              pbr1: Wt.condText('pbrBelow', 1, false), now: [Wt.nowValue('pxBelow', 84200, false), Wt.nowValue('pbrBelow', 1.3, false), Wt.nowValue('dyAtLeast', 0.03, false)] };""")
    assert got["px"] == "주가 75,000원 아래 조건에 맞아요. 지금 74,000원이에요."
    # a US price is read "…달러" (review B1): always 예요, whatever its last digit
    assert got["pxUs"] == "주가 $150.00 아래 조건에 맞아요. 지금 $148.50예요."
    assert got["pxUs2"] == "주가 $150.00 아래 조건에 맞아요. 지금 $148.55예요."
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
        code: ok({ 'x y': { at: T } }), badAt: ok({ '005930': { at: '11/12' } }),
      };
      const r = S.checkStore({ v: 1, decks: [], notes: { '005930': { text: '메모', at: T } }, watch: { '005930': { at: T, conds: [{ k: 'pxBelow', v: 0 }] } } }, T);
      out.read = { notes: !!r.data.notes, watch: r.data.watch ?? null, problems: r.problems };
      const gone = (g) => S.checkStore({ v: 1, decks: [], gone: { watch: g } }, T).problems;
      out.gone = [gone({ '005930': { at: T } }), gone({ '005930': { at: T, ts: 'x' } }), gone({ 'x y': { at: T, ts: 5 } }), gone({ '005930': { at: '11/12', ts: 5 } }),
                  gone({ '005930': { at: T, ts: 5 } })];""")
    assert got["good"] is None and got["later"] is None
    assert got["many"] == "more than 30 stocks" and "two conditions of one kind" in got["twice"] and "pbrBelow" in got["dec"]
    assert "pxBelow" in got["zero"] and "hitAt" in got["hit"] and "stock code" in got["code"] and "real date" in got["badAt"]
    assert got["future"] is None                     # a date after today is a clock that was ahead: read as today, never set aside (below)
    assert got["read"] == {"notes": True, "watch": None, "problems": ["watch (the watch list): 005930: pxBelow: the number is not valid"]}
    bad = ["gone (deleted notes or watch-list marks): not valid"]
    assert got["gone"] == [bad, bad, bad, bad, []]  # a mark needs a code, a date and a time (ms)


def test_a_clock_that_was_ahead_never_locks_the_store_and_times_are_kept_as_made():
    """Round 3: a date added after today or a time after now (watch entries, gone.watch marks) is kept as stored (never rewritten)
    and never sets the list aside; the next edit of that stock is stamped after it (watchSaveTime), so it still wins a merge with
    the copy that holds the time from the clock that was ahead. The notes' own rule is unchanged."""
    got = run("""
      const NOW = Date.now(), AHEAD = NOW + 3 * 86400000, day = new Date(NOW + 9 * 3600 * 1000).toISOString().slice(0, 10);
      const ahead = { v: 1, decks: [], watch: { '005930': { at: '2099-01-01', ts: AHEAD, conds: [{ k: 'pxBelow', v: 70000 }] } },
                      gone: { watch: { '000660': { at: '2099-01-01', ts: AHEAD } } } };
      mem.set(K, JSON.stringify(ahead));
      const r = S.readStore(K, day);
      const ts1 = S.watchSaveTime(K, r.data, '005930'), ts2 = S.watchSaveTime(K, r.data, '000660'), ts3 = S.watchSaveTime(K, r.data, '035720');
      const edit = S.withWatchConds(r.data, '005930', [{ k: 'pxBelow', v: 60000 }], day, ts1);
      const back = S.withWatchAdd(edit, '000660', 'SK하이닉스', day, ts2);
      const m = S.mergeTabs(ahead, back, day), m2 = S.mergeTabs(back, ahead, day);
      const notes = S.checkStore({ v: 1, decks: [], notes: { '005930': { text: 'x', at: '2099-01-01' } } }, day);
      out = { locked: r.locked, problems: r.problems, kept: JSON.stringify(r.data.watch) === JSON.stringify(ahead.watch) && JSON.stringify(r.data.gone) === JSON.stringify(ahead.gone),
              ts: [ts1 === AHEAD + 1, ts2 === AHEAD + 1, ts3 >= NOW && ts3 < AHEAD],
              m: [m.watch['005930'].conds[0].v, !!m.watch['000660']], m2: [m2.watch['005930'].conds[0].v, !!m2.watch['000660']], notes: notes.problems };""")
    assert got["locked"] is False and got["problems"] == [] and got["kept"] is True and got["ts"] == [True, True, True]
    assert got["m"] == [60000, True] and got["m2"] == [60000, True]
    assert got["notes"] == ["notes: not valid"]       # unchanged: a note dated after today is still set aside


CLOCK = """
const realNow = Date.now; let offset = 0; Date.now = () => realNow() + offset;
const today = () => new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
const Wv = (d) => Object.fromEntries(Object.entries(d.watch || {}).map(([t, e]) => [t, (e.conds || []).map((c) => c.v)]));
// an edit as the screens make it: stamped by watchSaveTime (now, or after any time this device holds for the stock)
const conds = (St, d, v) => St.withWatchConds(d, '005930', [{ k: 'pxBelow', v }], today(), St.watchSaveTime(K, d, '005930'));
"""


@pytest.mark.parametrize("ahead_ms", [0, 5 * 60_000, 86_400_000])
def test_round3_sc3_an_edit_made_while_the_clock_was_ahead_wins_over_an_old_tabs_older_copy(ahead_ms):
    """sc3: 1,000원 set two hours ago; a tab of the app now on main reads it; this app sets 2,000원 while the clock is ahead (5 min,
    a day); the clock is corrected; the old tab saves a 메모 from its copy. The next start shows 2,000원 and says 합쳤어요."""
    got = run(CLOCK + f"""
      let d = S.withWatchAdd({{ v: 1, decks: [] }}, '005930', 'a', today(), Date.now() - 7200e3);
      d = S.withWatchConds(d, '005930', [{{ k: 'pxBelow', v: 1000 }}], today(), Date.now() - 7200e3 + 1);
      S.writeStore(d, K, today()); S.readStore(K, today());
      const old = Old7.readStore(K, today());
      offset = {ahead_ms};
      S.writeStore(conds(S, S.readStore(K, today()).data, 2000), K, today());
      offset = 0;
      Old7.writeStore(Old7.withNote(old.data, '000660', 'm', today(), Date.now()), K, today());
      const r = S.readStore(K, today());
      out = {{ final: Wv(r.data), restored: r.restored }};""")
    assert got == {"final": {"005930": [2000]}, "restored": True}


@pytest.mark.parametrize("ahead_ms,earlier_ms", [(5 * 60_000, 3_600_000), (86_400_000, 3_600_000), (5 * 60_000, 30 * 3_600_000), (0, 3_600_000)])
def test_round3_sc2_two_tabs_of_this_app_keep_the_edit_made_while_the_clock_was_ahead(ahead_ms, earlier_ms):
    """sc2: tab A and tab B read 1,000원; A sets 2,000원 while the clock is ahead; the clock is corrected; B (stale) saves a 메모.
    The next start shows 2,000원 (not B's older 1,000원)."""
    got = run(CLOCK + f"""
      let d = S.withWatchAdd({{ v: 1, decks: [] }}, '005930', 'a', today(), Date.now() - {earlier_ms});
      d = S.withWatchConds(d, '005930', [{{ k: 'pxBelow', v: 1000 }}], today(), Date.now() - {earlier_ms} + 1);
      S.writeStore(d, K, today()); S.readStore(K, today());
      const b = S2.readStore(K, today()).data;
      offset = {ahead_ms};
      S.writeStore(conds(S, S.readStore(K, today()).data, 2000), K, today());
      offset = 0;
      S2.writeStore(S2.withNote(b, '000660', 'm', today(), Date.now()), K, today());
      const r = S.readStore(K, today());
      out = {{ final: Wv(r.data) }};""")
    assert got == {"final": {"005930": [2000]}}


def test_round3_sc_c_a_clock_set_back_after_an_edit_never_lets_an_older_edit_win():
    """sc.mjs case C: 1,000원 an hour ago; tab B reads it; tab A sets 2,000원; the clock is set back a minute and A reloads and saves
    a 메모 inside that minute (times are kept as made); B, stale, saves. The next start shows 2,000원. Then an edit made inside the
    minute is stamped after 2,000원's time, so it is the latest."""
    got = run(CLOCK + """
      let d = S.withWatchAdd({ v: 1, decks: [] }, '005930', 'a', today(), Date.now() - 3600e3);
      d = S.withWatchConds(d, '005930', [{ k: 'pxBelow', v: 1000 }], today(), Date.now() - 3600e3 + 1);
      S.writeStore(d, K, today()); S.readStore(K, today());
      const stale = S2.readStore(K, today()).data;
      const tA = Date.now();
      S.writeStore(conds(S, S.readStore(K, today()).data, 2000), K, today());
      offset = -60e3;
      const rA = S.readStore(K, today());
      S.writeStore(S.withNote(rA.data, '000660', 'memo', today(), Date.now()), K, today());
      const kept = JSON.parse(mem.get(K)).watch['005930'].ts;
      const inside = conds(S, S.readStore(K, today()).data, 3000);
      offset = 0;
      S2.writeStore(S2.withNote(stale, '035720', 'memo B', today(), Date.now()), K, today());
      const rEnd = S.readStore(K, today());
      out = { kept: kept >= tA, final: Wv(rEnd.data), restored: rEnd.restored, inside: inside.watch['005930'].ts > kept };""")
    assert got == {"kept": True, "final": {"005930": [2000]}, "restored": True, "inside": True}


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


def test_review_s1_no_check_without_todays_dated_price_no_row_on_stale_data_and_no_word_from_an_older_close():
    """W11: a US stock in a file without a US date (no price date) is never met. W18: stale data gives no 관심 종목 조건 row even
    for a condition met with no mark yet (the no-portfolio 홈 reads watchHits the same way). S1(c): a value dated before the
    stored mark neither clears nor sets it."""
    got = run("""
      const data = W({ AAA: { at: '2026-11-05', conds: [{ k: 'pxBelow', v: 150 }] }, '000002': { at: '2026-11-01', conds: [{ k: 'pbrBelow', v: 0.8, hitAt: '2026-11-13' }] } });
      const noUs = loadOf([us('AAA'), kr('000002', { pbr: 0.9 })], { usPxDate: null });
      const stale = loadOf([us('AAA'), kr('000002', { pbr: 0.7 })], { stale: true });
      const older = loadOf([us('AAA'), kr('000002', { pbr: 0.9 })], { pxDate: '2026-11-12' });       // fresh, but before the mark's 11-13
      out = { noDate: Wt.condState(noUs, noUs.byT.get('AAA'), { k: 'pxBelow', v: 150 }, true).state, noDateRows: Wt.watchHits(data, noUs).map((h) => h.t),
              stale: Wt.watchHits(data, stale), staleMarks: [...Wt.watchMarks(data, stale)], older: [...Wt.watchMarks(data, older)].filter(([k]) => k.startsWith('000002')),
              olderWrite: Wt.withWatchHits(W({ '000002': data.watch['000002'] }), older) };""")
    assert got["noDate"] == "stale" and got["noDateRows"] == []
    assert got["stale"] == [] and got["staleMarks"] == []
    assert got["older"] == [] and got["olderWrite"] is None


def test_review_s11_an_edit_keeps_a_later_versions_conditions():
    got = run("""
      const d = W({ '005930': { at: T, ts: 1, conds: [{ k: 'pbrBelow', v: 0.8 }, { k: 'perBelow', v: 9, someday: 1 }] } });
      out = S.withWatchConds(d, '005930', [{ k: 'pxBelow', v: 70000 }], T, 2).watch['005930'].conds;""")
    assert got == [{"k": "pxBelow", "v": 70000}, {"k": "perBelow", "v": 9, "someday": 1}]


def test_review_s24_s25_import_respects_a_deletion_mark_in_any_copy_and_stamps_after_it():
    """t3: this device took 005930 out in a copy another tab left (.other.), the records hold no mark; a records file brings it back:
    it comes in as an edit made now (after that mark), so the next start keeps it. S24: with the import's time before the mark's
    (a clock set back), the stamp is the mark's time + 1, never the import time alone."""
    got = run("""
      S.writeStore({ v: 1, decks: [], notes: { '000001': { text: 'a', at: T } } }, K, T); S.readStore(K, T);
      mem.set(K + '.other.5', JSON.stringify({ v: 1, decks: [], gone: { watch: { '005930': { at: T, ts: 500 }, '000660': { at: T, ts: 5000 } } } }));
      const inc = S.parseImport(JSON.stringify({ v: 1, decks: [], watch: { '005930': { at: '2026-11-01' }, '000660': { at: '2026-11-01' } } }), T);
      const cur = { v: 1, decks: [], notes: { '000001': { text: 'a', at: T } } };
      const m = S.mergeStores(cur, inc, 1000, S.storedStores(K, T), T);
      S.writeStore(m, K, T);
      const r = S.readStore(K, T);
      out = { stamped: [m.watch['005930'].ts, m.watch['000660'].ts], after: Object.keys(r.data.watch).sort() };""")
    assert got["stamped"] == [1000, 5001] and got["after"] == ["000660", "005930"]


def test_review_s14_s15_s16_s19_merges_pick_the_right_state_and_the_current_copys_stocks_at_the_cap():
    got = run("""
      const m = (other, cur) => S.mergeTabs({ v: 1, decks: [], ...other }, { v: 1, decks: [], ...cur }, T);
      // S14: one copy holds an entry and a mark of the same time: the entry (it was added again in that same moment)
      const tie = m({ watch: { '005930': { at: T, ts: 5 } }, gone: { watch: { '005930': { at: T, ts: 5 } } } }, {});
      // S15: an entry at 5 and a later mark at 9 in one copy: the mark
      const later = m({ watch: { '005930': { at: T, ts: 5 } }, gone: { watch: { '005930': { at: T, ts: 9 } } } }, {});
      // S16: the same stock edited at the same time in both copies: the current copy's
      const both = m({ watch: { '005930': { at: T, ts: 5, conds: [{ k: 'pxBelow', v: 2 }] } } }, { watch: { '005930': { at: T, ts: 5, conds: [{ k: 'pxBelow', v: 1 }] } } });
      // S19: the current copy's 29 (added earlier) and the other copy's 2 newest: 30 = all 29 of the current copy + the newest other
      const list = (from, n, at) => Object.fromEntries(Array.from({ length: n }, (_, i) => [String(from + i), { at, ts: 1000 + i }]));
      const cap = m({ watch: list(200000, 2, '2026-11-11') }, { watch: list(100000, 29, '2026-11-01') });
      out = { tie: [Object.keys(tie.watch || {}), tie.gone ?? null], later: [later.watch ?? null, later.gone], both: both.watch['005930'].conds[0].v,
              cap: Object.keys(cap.watch).sort() };""")
    assert got["tie"] == [["005930"], None]
    assert got["later"] == [None, {"watch": {"005930": {"at": "2026-11-12", "ts": 9}}}]
    assert got["both"] == 1
    assert got["cap"] == sorted([str(100000 + i) for i in range(29)] + ["200001"])


def test_review_b1_an_old_tab_that_reads_again_never_drops_newer_watch_edits():
    """B1 path (a): this app writes A; a tab of the app now on main (v19.7a) starts and reads [A]; this app adds B and puts a
    condition on A, then closes; the old tab starts again (merging this app's last text its own way) and makes an edit. Before
    the fix B and the condition were gone with no copy and no 합쳤어요. Now they come back from key + ".watch" and the screens say so.
    Path (b): a copy another tab of this app left aside (.other., holding C) is merged by an old tab's start its own way (its
    list dropped, the copy moved to .restored.); C comes back too."""
    got = run("""
      // (a)
      S.writeStore(S.withWatchAdd({ v: 1, decks: [] }, '005930', '삼성전자', T, 100), K, T);
      const old1 = Old7.readStore(K, T);
      let d = S.readStore(K, T).data;
      d = S.withWatchAdd(d, '000660', 'SK하이닉스', T, 200); S.writeStore(d, K, T);
      d = S.withWatchConds(d, '005930', [{ k: 'pbrBelow', v: 0.8 }], T, 300); S.writeStore(d, K, T);
      S.keepMine(K);
      Old7.writeStore(Old7.withNote(old1.data, '035720', '메모', T, 400), K, T);
      const old2 = Old7.readStore(K, T);
      Old7.writeStore(Old7.withNote(old2.data, '035720', '메모 2', T, 500), K, T);
      const lostBefore = Object.fromEntries(Object.entries(stored().watch || {}).map(([t, e]) => [t, (e.conds || []).length]));
      const a = S.readStore(K, T);
      const aOut = { lostBefore, watch: Object.fromEntries(Object.entries(a.data.watch).map(([t, e]) => [t, (e.conds || []).map((c) => [c.k, c.v])])),
                     restored: a.restored, note: a.data.notes['035720'].text, again: S.readStore(K, T).restored };
      // (b)
      mem.clear();
      S.writeStore({ v: 1, decks: [] }, K, T); S.readStore(K, T);
      S2.readStore(K, T);                                                          // a second tab of this app read the same records
      S.writeStore(S.withWatchAdd(S.readStore(K, T).data, '005930', '삼성전자', T, 100), K, T);
      S2.writeStore(S2.withWatchAdd({ v: 1, decks: [] }, '051910', 'LG화학', T, 200), K, T);    // its text did not hold 005930: kept aside
      const aside = [...mem.keys()].filter((k) => k.includes('.other.')).length;
      const o = Old7.readStore(K, T);                                              // the old tab's start merges that copy its own way
      Old7.writeStore(Old7.withNote(o.data, '035720', '메모', T, 300), K, T);
      const oldLeft = Object.keys(stored().watch || {});
      const b = S.readStore(K, T);
      out = { a: aOut, b: { aside, oldLeft, watch: Object.keys(b.data.watch).sort(), restored: b.restored } };""")
    a = got["a"]
    assert a["lostBefore"] == {"005930": 0}                                   # what the old tab left in the records: no 000660, no condition
    assert a["watch"] == {"005930": [["pbrBelow", 0.8]], "000660": []} and a["restored"] is True and a["note"] == "메모 2"
    assert a["again"] is False                                                # said once
    assert got["b"]["aside"] == 1 and got["b"]["oldLeft"] == ["051910"]       # the old tab's start dropped the copy's 005930
    assert got["b"]["watch"] == ["005930", "051910"] and got["b"]["restored"] is True


def test_review_b1_the_side_key_follows_the_records_and_a_bad_one_is_set_aside():
    got = run("""
      // a stock the 30 cap left out of a start's merge does not come back on a later start once there is room
      const many = Object.fromEntries(Array.from({ length: 30 }, (_, i) => [String(100000 + i), { at: '2026-11-01', ts: 1000 + i }]));
      S.writeStore({ v: 1, decks: [], watch: many }, K, T); S.readStore(K, T);
      const side = JSON.parse(mem.get(K + '.watch'));
      side.watch['200000'] = { at: '2026-11-11', ts: 999999 };                    // a later add the records do not hold (an old tab dropped it)
      mem.set(K + '.watch', JSON.stringify(side));
      const r1 = S.readStore(K, T);                                                // brought back, the cap keeps the records' 30: said, and the key follows
      const followed = Object.keys(JSON.parse(mem.get(K + '.watch')).watch).length;
      S.writeStore(S.withWatchRemove(r1.data, '100000', T, 2000000), K, T);
      const r2 = S.readStore(K, T);
      // a bad key: set aside, not used, the records read
      mem.set(K + '.watch', '{"v":1,"watch":{"x y":{}}}');
      const r3 = S.readStore(K, T);
      out = { r1: [r1.restored, Object.keys(r1.data.watch).length, '200000' in r1.data.watch], followed, r2: ['200000' in r2.data.watch, r2.restored],
              r3: [r3.locked, r3.restored, mem.has(K + '.watch'), [...mem.values()].some((v) => v === '{"v":1,"watch":{"x y":{}}}')] };""")
    assert got["r1"] == [True, 30, False] and got["followed"] == 30
    assert got["r2"] == [False, False]
    assert got["r3"][0] is False and got["r3"][1] is False and got["r3"][3] is True


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


def test_review_tabs_a_copy_holding_what_the_records_would_lose_is_kept_and_said():
    """covers / droppedFrom (S27–S30): when this tab writes over another tab's text, that text is kept aside whenever merging it
    would leave out one of its stocks (the 30 cap) or tie an entry against its deletion mark, and the next start says 합쳤어요."""
    got = run("""
      const list = (from, n, at) => Object.fromEntries(Array.from({ length: n }, (_, i) => [String(from + i), { at, ts: 1000 + i }]));
      const run1 = (theirs, mine) => {
        mem.clear();
        S.writeStore({ v: 1, decks: [] }, K, T);                                    // this tab last wrote an empty list
        mem.set(K, JSON.stringify(theirs));                                         // another tab wrote since (not through this module)
        S.writeStore(mine, K, T);
        const kept = [...mem.keys()].filter((k) => k.includes('.other.')).length;
        return { kept, restored: S.readStore(K, T).restored };
      };
      // the cap: theirs = 29 of mine + one more; mine = 30
      const capRun = run1({ v: 1, decks: [], watch: { ...list(100000, 29, '2026-11-01'), '200000': { at: '2026-11-11', ts: 5 } } },
                          { v: 1, decks: [], watch: list(100000, 30, '2026-11-01') });
      // a tie: theirs took 005930 out at the same moment mine holds it
      const tieRun = run1({ v: 1, decks: [], gone: { watch: { '005930': { at: T, ts: 500 } } } }, { v: 1, decks: [], watch: { '005930': { at: T, ts: 500 } } });
      out = { capRun, tieRun };""")
    assert got["capRun"] == {"kept": 1, "restored": True} and got["tieRun"] == {"kept": 1, "restored": True}


def test_review_marks_and_imports_never_carry_a_device_mark_or_a_bad_date():
    got = run("""
      const d = W({ '005930': { at: T, conds: [{ k: 'pbrBelow', v: 0.8 }] } });
      const bad = S.withWatchMarks(d, new Map([['005930|pbrBelow', 'yesterday']]));        // S13: only a date or null is a mark
      const good = S.withWatchMarks(d, new Map([['005930|pbrBelow', '2026-11-11']]), 1234);
      // S26: a records file read some other way than parseImport still brings no hitAt
      const m = S.mergeStores({ v: 1, decks: [] }, { decks: [], watch: { AAPL: { at: T, conds: [{ k: 'pxBelow', v: 150, hitAt: '2026-11-11' }] } } }, 1, [], T);
      out = { bad, good: good.watch['005930'].conds, file: m.watch.AAPL.conds };""")
    assert got["bad"] is None and got["good"] == [{"k": "pbrBelow", "v": 0.8, "hitAt": "2026-11-11", "hitTs": 1234}]   # the mark's own time
    assert got["file"] == [{"k": "pxBelow", "v": 150}]


def test_review_b1_a_removal_survives_an_old_tab_writing_its_older_copy():
    """N10: this app takes 005930 out; a tab of the app now on main, which read the list before, saves a 메모 (its write puts
    005930 back, without the mark). The next start takes it out again (the mark kept beside the records) and says so."""
    got = run("""
      S.writeStore(S.withWatchAdd({ v: 1, decks: [] }, '005930', '삼성전자', T, 100), K, T);
      const old = Old7.readStore(K, T);
      const d = S.readStore(K, T).data;
      S.writeStore(S.withWatchRemove(d, '005930', T, 200), K, T);
      Old7.writeStore(Old7.withNote(old.data, '035720', '메모', T, 300), K, T);
      const back = !!(stored().watch || {})['005930'];
      const r = S.readStore(K, T);
      out = { back, after: r.data.watch ?? null, gone: r.data.gone.watch, restored: r.restored };""")
    assert got["back"] is True and got["after"] is None and got["gone"] == {"005930": {"at": "2026-11-12", "ts": 200}} and got["restored"] is True


def test_review_b1_random_runs_of_this_app_and_an_old_tab_never_lose_a_watch_edit():
    """Review A's race (race_old.mjs): random steps of a tab of this app (add · remove · a condition) and a tab of the app now on
    main (a 메모, a restart that reads the list, close · reopen), 200 runs; the next start of this app holds every last edit of
    this app (a stock added or changed is there with its conditions, one taken out is not). Before the fix: 11 of 400 lost one."""
    got = run("""
      const POOL = ['005930', '000660', '035720', '051910', 'AAPL', 'MSFT', '005380', 'NVDA'];
      let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
      const pick = (a) => a[Math.floor(rnd() * a.length)];
      const condsOf = (e) => JSON.stringify((e && e.conds || []).map((c) => [c.k, c.v]));
      let fails = 0, first = null;
      for (let run = 0; run < 200; run++) {
        mem.clear();
        const tabs = [S, Old7]; let clock = 1762900000000;
        S.writeStore({ v: 1, decks: [] }, K, T);
        const D = [S.readStore(K, T).data, Old7.readStore(K, T).data], open = [true, true], oracle = new Map();
        const fire = (i, before) => { const now = mem.get(K); if (now !== before && open[1 - i]) tabs[1 - i].keepOwnText(K, now, T); };
        const steps = 8 + Math.floor(rnd() * 20), log = [];
        for (let s = 0; s < steps; s++) {
          const i = rnd() < 0.5 ? 0 : 1, St = tabs[i], r = rnd();
          if (!open[i]) { const rr = St.readStore(K, T); if (!rr.locked) D[i] = rr.data; open[i] = true; fire(i, null); continue; }
          if (r > 0.93) { if (open[1 - i]) { St.keepMine(K); open[i] = false; } continue; }
          const before = mem.get(K);
          if (r < 0.15) { const rr = St.readStore(K, T); if (!rr.locked) D[i] = rr.data; log.push('t' + i + ' restart'); }
          else if (i === 1) { const n = Old7.withNote(D[1], pick(POOL), 'm' + clock, T, ++clock); if (n && Old7.writeStore(n, K, T)) D[1] = n; log.push('old note'); }
          else {
            const t = pick(POOL), ts = ++clock, w = D[0].watch || {};
            let n = null, act;
            if (!w[t]) { n = S.withWatchAdd(D[0], t, 'n' + t, T, ts); act = 'add'; }
            else if (rnd() < 0.4) { n = S.withWatchRemove(D[0], t, T, ts); act = 'remove'; }
            else { n = S.withWatchConds(D[0], t, [{ k: 'pxBelow', v: 1 + Math.floor(rnd() * 5) * 1000 }], T, ts); act = 'conds'; }
            if (!n || !S.writeStore(n, K, T)) continue;
            D[0] = n; log.push(act + ' ' + t);
            oracle.set(t, act === 'remove' ? { present: false } : { present: true, conds: condsOf(n.watch[t]) });
          }
          fire(i, before);
        }
        const got = S.readStore(K, T).data.watch || {}, bad = [];
        for (const [t, o] of oracle) {
          if (!o.present && got[t]) bad.push(t + ' back');
          if (o.present && !got[t]) bad.push(t + ' lost');
          if (o.present && got[t] && condsOf(got[t]) !== o.conds) bad.push(t + ' conds');
        }
        if (bad.length) { fails++; if (!first) first = [run, bad, log]; }
      }
      out = { fails, first };""")
    assert got["fails"] == 0, got["first"]


def test_round3_n10_a_removal_holds_even_when_the_old_copy_has_marks_of_its_own():
    """mut/n10: the old tab's copy already has a gone.watch part (000660 taken out earlier), so its own merge keeps its marks and
    drops a later removal; this app takes 005930 out, the old tab saves a 메모 from its copy. The next start keeps 005930 out (the
    mark kept beside the records) and says so."""
    got = run("""
      let d = S.withWatchAdd({ v: 1, decks: [] }, '000660', 'Y', T, 100); S.writeStore(d, K, T);
      d = S.withWatchRemove(S.readStore(K, T).data, '000660', T, 110); S.writeStore(d, K, T);
      d = S.withWatchAdd(d, '005930', 'X', T, 120); S.writeStore(d, K, T);
      const old = Old7.readStore(K, T);
      S.writeStore(S.withWatchRemove(S.readStore(K, T).data, '005930', T, 200), K, T);
      S.keepMine(K);
      Old7.writeStore(Old7.withNote(old.data, '035720', 'memo', T, 300), K, T);
      const back = Object.keys(stored().watch || {});
      const r = S.readStore(K, T);
      out = { back, watch: Object.keys(r.data.watch || {}), restored: r.restored };""")
    assert got == {"back": ["005930"], "watch": [], "restored": True}


def test_round3_n11_an_import_in_a_stale_tab_respects_a_removal_kept_only_beside_the_records():
    """mut/n11b: 005930 was taken out (its mark at 200 now only in key + ".watch": an old tab wrote it back without the mark); a tab
    of this app open since before 005930 was added imports an older records file holding it (ts 50). It comes in as an edit made
    now (1000, after the mark), so the next start keeps it."""
    got = run("""
      let d = S.withWatchAdd({ v: 1, decks: [] }, '000660', 'Y', T, 100); S.writeStore(d, K, T);
      d = S.withWatchRemove(S.readStore(K, T).data, '000660', T, 110); S.writeStore(d, K, T);
      const b = S2.readStore(K, T).data;
      d = S.withWatchAdd(d, '005930', 'X', T, 120); S.writeStore(d, K, T);
      const old = Old7.readStore(K, T);
      d = S.withWatchRemove(d, '005930', T, 200); S.writeStore(d, K, T);
      S.keepMine(K);
      Old7.writeStore(Old7.withNote(old.data, '035720', 'memo', T, 300), K, T);
      const markOnlyBeside = !((stored().gone || {}).watch || {})['005930'] && !!JSON.parse(mem.get(K + '.watch')).gone['005930'];
      const file = S2.parseImport(JSON.stringify({ v: 1, decks: [], watch: { '005930': { at: '2026-11-01', ts: 50 } } }), T);
      const m = S2.mergeStores(b, file, 1000, S2.storedStores(K, T), T);
      S2.writeStore(m, K, T);
      const r = S.readStore(K, T);
      out = { markOnlyBeside, ts: m.watch['005930'].ts, after: Object.keys(r.data.watch || {}) };""")
    assert got == {"markOnlyBeside": True, "ts": 1000, "after": ["005930"]}


def test_round3_hit_marks_carry_their_own_time_so_the_later_mark_wins():
    """hit2: the 홈 row was shown and its mark stored; a tab of the app now on main saves its older copy (no mark): the next start
    keeps the mark (no second row), quietly. And between two copies of this app, the later mark (set or cleared) wins on its own
    time, whatever copy leads."""
    got = run("""
      let d = S.withWatchConds(S.withWatchAdd({ v: 1, decks: [] }, '005930', 'a', T, 100), '005930', [{ k: 'pbrBelow', v: 1 }], T, 101);
      S.writeStore(d, K, T); d = S.readStore(K, T).data;
      const old = Old7.readStore(K, T);
      d = S.withWatchMarks(d, new Map([['005930|pbrBelow', '2026-11-12']]), 500); S.writeStore(d, K, T);
      Old7.writeStore(Old7.withNote(old.data, '000660', 'm', T, 300), K, T);
      const r = S.readStore(K, T);
      const one = { hit: r.data.watch['005930'].conds[0].hitAt ?? null, restored: r.restored };
      // two copies: A cleared the mark at 900 (fresh data, not met), B still holds the mark set at 500
      const e = (c) => ({ v: 1, decks: [], watch: { '005930': { at: T, ts: 101, conds: [c] } } });
      const A = e({ k: 'pbrBelow', v: 1, hitTs: 900 }), B = e({ k: 'pbrBelow', v: 1, hitAt: '2026-11-12', hitTs: 500 });
      const c1 = S.mergeTabs(B, A, T).watch['005930'].conds[0], c2 = S.mergeTabs(A, B, T).watch['005930'].conds[0];
      // a changed condition keeps its own (no mark from the old number)
      const C = e({ k: 'pbrBelow', v: 2 });
      const c3 = S.mergeTabs(B, { ...C, watch: { '005930': { ...C.watch['005930'], ts: 102 } } }, T).watch['005930'].conds[0];
      out = { one, c1, c2, c3 };""")
    assert got["one"] == {"hit": "2026-11-12", "restored": False}
    assert got["c1"] == {"k": "pbrBelow", "v": 1, "hitTs": 900} and got["c2"] == {"k": "pbrBelow", "v": 1, "hitTs": 900}
    assert got["c3"] == {"k": "pbrBelow", "v": 2}


def test_round3_the_save_time_also_reads_the_times_kept_beside_the_records():
    """Tab A sets 2,000원 while the clock is a day ahead (its time is in the records and beside them); the clock is corrected; tab B,
    still on the older records it read, sets 3,000원: stamped after A's time (read beside the records), so B's newest edit wins."""
    got = run(CLOCK + """
      let d = S.withWatchConds(S.withWatchAdd({ v: 1, decks: [] }, '005930', 'a', today(), Date.now() - 3600e3), '005930', [{ k: 'pxBelow', v: 1000 }], today(), Date.now() - 3600e3 + 1);
      S.writeStore(d, K, today()); S.readStore(K, today());
      const b = S2.readStore(K, today()).data;
      offset = 86400e3;
      S.writeStore(conds(S, S.readStore(K, today()).data, 2000), K, today());
      offset = 0;
      const nb = conds(S2, b, 3000);
      S2.writeStore(nb, K, today());
      const r = S.readStore(K, today());
      out = { final: Wv(r.data) };""")
    assert got == {"final": {"005930": [3000]}}
