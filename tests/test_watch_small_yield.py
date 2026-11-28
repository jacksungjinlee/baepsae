# -*- coding: utf-8 -*-
"""관심 종목의 배당수익률 조건과 소액주주 배당수익률 — Node runs the shipped src/v2/watch.js · watch.jsx (adds only).

Jack, 2026-11-27 (answer 14): "Yes, use the 소액주주 yield where it exists (관심 종목 배당수익률 condition), labelled as such."
The label and the line (C.co.div.smallBasis · smallLine) wait for Jack word for word, so everything sits behind #183's switch
(src/v2/smallcfg.js SMALL_YIELD.on) and those two copy keys:
- switch off, or on with either key null (the shipped build): every value, chip, mark, 홈 row, sheet and console line exactly as
  on main 5d12ef1 (tests/fixtures/watch_before_small_5d12ef1: main's watch.js and watch.jsx, run beside today's), for every
  stock of the repository's data.json (the daily run's file), the v2 fixture and, when set, $BAEPSAE_WATCH_DATA (a folder
  with data.json and corp.json, e.g. a data-branch copy);
- on with both keys (here only, in the test): a Korean stock whose all-holder yield is blank and whose 소액주주 yield the company
  page would show (company.js divSmallView) reads that yield, rounded as the chip shows it, judged and marked like any value,
  labelled "{y} · {smallBasis}" on the chip, in the sheet and on 홈's row, with smallLine once under its card;
- never while the all-holder yield shows, never for a US stock, never without exact data (blank); on stale data or an earlier
  close it shows and is never judged, exactly like the all-holder yield.
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
V2 = os.path.join(ROOT, "src", "v2")
OLD = os.path.join(ROOT, "tests", "fixtures", "watch_before_small_5d12ef1")     # main 5d12ef1: watch.js · watch.jsx before this change
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
MODS = {"Wt": "src/v2/watch.js", "Wx": "src/v2/watch.jsx", "E": "src/v2/engine.js", "K": "src/v2/company.js", "SC": "src/v2/smallcfg.js",
        "CP": "src/copy/v2.js"}
_B = {}
IMPORT = re.compile(r'from "(\.\.?/[^"]+)"')


def proposals():
    """The two parked lines: the copy key's value once Jack has approved it, else the proposal in its comment (as proposed)."""
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as fh:
        src = fh.read()
    out = {}
    for k in ("smallBasis", "smallLine"):
        m = re.search(rf'^\s+{k}: (null|"[^"]*"),\s+// 제안 \([^)]*\): "([^"]+)"', src, re.M)
        assert m, f"src/copy/v2.js co.div.{k}: no proposal found"
        out[k] = json.loads(m.group(1)) or m.group(2)
    return out


def old_copy(tmp):
    """main's watch.js · watch.jsx in tmp/old, their imports pointing at today's src (the one engine, copy and store), and
    watch.jsx at main's watch.js."""
    d = os.path.join(tmp, "old")
    os.makedirs(d)
    for name in ("watch.js", "watch.jsx"):
        with open(os.path.join(OLD, name), encoding="utf-8") as fh:
            src = fh.read()

        def to(m):
            rel = m.group(1)
            if name == "watch.jsx" and rel == "./watch.js":
                return f'from {json.dumps(os.path.join(d, "watch.js"))}'
            return f'from {json.dumps(os.path.normpath(os.path.join(V2, rel)))}'
        src, n = IMPORT.subn(to, src)
        assert n >= 7, (name, n)
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(src)
    return d


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-watchsmall-")
        old = old_copy(tmp)
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
            f.write(f"export * as Wt0 from {json.dumps(os.path.join(old, 'watch.js'))};\n")
            f.write(f"export * as Wx0 from {json.dumps(os.path.join(old, 'watch.jsx'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/b.mjs", "--log-level=error",
                            "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(autouse=True, scope="module")
def cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


HEAD = """
import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h, Fragment } from 'react';
import fs from 'fs';
const { Wt, Wx, Wt0, Wx0, E, K, SC, CP } = B; const C2 = CP.C;
const logs = []; console.warn = (m) => logs.push(String(m)); console.info = (m) => logs.push(String(m));
const P = __PROP__;
const set = (on, basis, line) => { SC.SMALL_YIELD.on = on; C2.co.div.smallBasis = basis; C2.co.div.smallLine = line; };
const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n')).replace(/\\n+/g, '\\n');
// fresh: the example page counts as fresh (rules.dayState), so the run does not depend on today's date; stale: staleAfter passed
const loadOf = (data, corp, fresh = true) => ({ status: 'ok', data, corp: corp || { companies: [] }, preview: fresh,
  fresh: fresh ? { stale: false, days: 0, md: null } : { stale: true, days: 3, md: null },
  byT: new Map(data.stocks.map((s) => [s.t, s])), coByT: new Map(((corp && corp.companies) || []).map((x) => [x.t, x])) });
const KINDS = ['pxBelow', 'pbrBelow', 'dyAtLeast'];
// TPC로보틱스 as the 11-28 publish has it (048770: dyt blank, dvLine 3, 10원 to the small holders at 4,350원 -> 0.23%)
const tpc = (more = {}) => ({ t: '048770', nk: 'TPC로보틱스', cls: 'kr', price: 4350, pbr: 1.1, d1: 0.5, dps: 10, dyt: null, dvLine: 3,
  dpsSmall: 10, dytSmall: 0.23, divSt: 'nd', dps3a: [null, null, null], dpsF: [null, null, null], fy: 2025, ...more });
const storeOf = (watch) => ({ data: { v: 1, decks: [], watch }, writable: true, key: 'baepsae2.v1' });
const screen = (load, watch) => renderToStaticMarkup(h(Wx.WatchScreen, { load, store: storeOf(watch), setStoreData() {}, pad: 0, onBack() {}, onAdd() {} }));
const screen0 = (load, watch) => renderToStaticMarkup(h(Wx0.WatchScreen, { load, store: storeOf(watch), setStoreData() {}, pad: 0, onBack() {}, onAdd() {} }));
const sheet = (M, load, watch, t) => renderToStaticMarkup(h(M.CondSheet, { open: { t, name: (load.byT.get(t) || {}).nk || t, s: load.byT.get(t) || null,
  us: (load.byT.get(t) || {}).cls === 'us' }, store: storeOf(watch), setStoreData() {}, onClose() {} }));
const rows = (M, hits, load) => renderToStaticMarkup(h(Fragment, null, M.WatchHitRows({ hits, load, onOpen() {} })));
const hitRow = (x) => ({ ...x, s: x.s.t });
let out;
"""


def run(body):
    code = HEAD.replace("__PROP__", json.dumps(proposals(), ensure_ascii=False)) + body + "\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout)


def data_sets():
    out = [("fixture", FIX)]
    if os.path.isfile(os.path.join(ROOT, "data.json")):
        out.append(("repo", ROOT))
    env = os.environ.get("BAEPSAE_WATCH_DATA")
    if env:
        out.append(("env", env))
    return out


@pytest.mark.parametrize("name,folder", data_sets(), ids=[n for n, _ in data_sets()])
def test_off_or_without_both_lines_everything_is_as_on_main_for_every_stock(name, folder):
    """Switch off (shipped), on with either line null, or the lines without the switch: today's watch.js / watch.jsx give exactly
    main's values, condition states (fresh and stale), marks, 홈 rows and their lines, sheets, screens and console lines for every
    stock in the file (plus a TPC로보틱스-shaped row, so a 소액주주 candidate is always there; the screens hold every Korean stock with a
    blank all-holder yield, a reason mark or a 소액주주 field, and 300 others). Control: on with both lines, the only
    values that change are the 배당수익률 of the stocks divSmallView gives a 소액주주 yield, and the screen shows it."""
    dp, cp = os.path.join(folder, "data.json"), os.path.join(folder, "corp.json")
    got = run(f"""
      const D = JSON.parse(fs.readFileSync({json.dumps(dp)}, 'utf8'));
      const CO = fs.existsSync({json.dumps(cp)}) ? JSON.parse(fs.readFileSync({json.dumps(cp)}, 'utf8')) : {{ companies: [] }};
      if (!D.divCheck) D.divCheck = {{ v: 1 }};                     // the fixture predates the split check: read it as an exact file
      D.stocks = D.stocks.filter((s) => s.t !== '048770').concat([tpc()]);
      E.setDataShape(D);
      const fresh = loadOf(D, CO, true), stale = loadOf(D, CO, false);
      const stocks = D.stocks.filter((s) => s.cls === 'kr' || s.cls === 'us');
      const watch = Object.fromEntries(stocks.map((s, i) => [s.t, {{ at: '2026-11-01', ts: i + 1,
        conds: [{{ k: 'pxBelow', v: 1e12 }}, {{ k: 'pbrBelow', v: 1000 }}, {{ k: 'dyAtLeast', v: 0.1 }}] }}]));
      const someSmall = stocks.filter((s) => s.cls === 'kr' && s.dytSmall != null).map((s) => s.t);
      // the screens: every Korean stock with a blank all-holder yield, a reason mark or a 소액주주 field, and the first 300 others
      const odd = (s) => s.cls === 'kr' && (s.dyt == null || s.dvLine != null || s.dytSmall != null || s.dpsSmall != null);
      const shown = new Set([...stocks.filter(odd), ...stocks.filter((s) => !odd(s)).slice(0, 300)].map((s) => s.t));
      const onScreen = Object.fromEntries(Object.entries(watch).filter(([t]) => shown.has(t)));
      const snap = (W, X, rowsOf) => {{
        logs.length = 0;
        const vals = stocks.map((s) => KINDS.map((k) => W.watchValue(s, k)));
        const st = [fresh, stale].map((l) => stocks.map((s) => KINDS.map((k) => W.condState(l, s, {{ k, v: k === 'dyAtLeast' ? 0.1 : 1 }}, l === fresh))));
        const hits = W.watchHits({{ watch }}, fresh);
        const marks = [...W.watchMarks({{ watch }}, fresh)];
        const lines = hits.map((x) => W.hitText(x.k, x.v, x.val, x.s.cls === 'us'));
        W.watchGuardNote({{ watch }}, loadOf(D, CO, true));
        const html = {{ screen: rowsOf.screen(fresh, onScreen), staleScreen: rowsOf.screen(stale, onScreen), rows: rows(X, hits, fresh),
          sheets: someSmall.map((t) => sheet(X, fresh, watch, t)) }};
        // the watch list's own console lines (other modules say some things once per run: not this change's)
        const said = logs.filter((m) => m.startsWith('[v2] watch list'));
        return JSON.stringify({{ vals, st, hits: hits.map(hitRow), marks, lines, said, html }});
      }};
      const now = () => snap(Wt, Wx, {{ screen }}), main = () => snap(Wt0, Wx0, {{ screen: screen0 }});
      const res = {{}};
      for (const [k, a] of [['off', [false, null, null]], ['onNoBasis', [true, null, P.smallLine]], ['onNoLine', [true, P.smallBasis, null]],
                            ['wordsOff', [false, P.smallBasis, P.smallLine]], ['onNoWords', [true, null, null]]]) {{
        set(...a); const x = now(); set(false, null, null); const y = main(); res[k] = {{ same: x === y, len: x.length }};
      }}
      // control: on with both lines
      set(true, P.smallBasis, P.smallLine);
      const changed = [];
      for (const s of stocks) for (const k of KINDS) if (Wt.watchValue(s, k) !== Wt0.watchValue(s, k)) changed.push(s.t + '|' + k);
      const want = stocks.filter((s) => s.cls === 'kr' && E.dytOf(s) == null && K.divSmallView(s) != null).map((s) => s.t + '|dyAtLeast');
      const on = screen(fresh, {{ '048770': watch['048770'] }});
      set(false, null, null);
      res.control = {{ changed, want, label: text(on).includes('지금 0.2% · ' + P.smallBasis), line: text(on).split(P.smallLine).length - 1,
        n: stocks.length, small: someSmall.length }};
      out = res;""")
    for k in ("off", "onNoBasis", "onNoLine", "wordsOff", "onNoWords"):
        assert got[k]["same"] is True and got[k]["len"] > 10000, (name, k, got[k])
    c = got["control"]
    assert c["n"] > 100 and c["small"] >= 1, c
    assert c["changed"] == c["want"] and "048770|dyAtLeast" in c["want"], c
    assert c["label"] is True and c["line"] == 1, c


def test_on_a_tpc_shaped_row_reads_the_small_holder_yield_rounded_judged_and_labelled_like_the_chip():
    got = run("""
      set(true, P.smallBasis, P.smallLine);
      const D = { pxDate: '2026-11-27', usPxDate: '2026-11-26', divCheck: { v: 1 }, fx: 1400,
        stocks: [tpc(), tpc({ t: '900001', nk: '반올림', price: 4000, dytSmall: 0.25 }), tpc({ t: '900002', nk: '작은', price: 20000, dytSmall: 0.05 })] };
      E.setDataShape(D);
      const L = loadOf(D, { companies: [] }, true);
      const s = L.byT.get('048770'), r = L.byT.get('900001'), t = L.byT.get('900002');
      const cs = (x, v) => Wt.condState(L, x, { k: 'dyAtLeast', v }, true);
      const res = { val: Wt.watchValue(s, 'dyAtLeast'), small: Wt.watchSmall(s, 'dyAtLeast'), smallPx: Wt.watchSmall(s, 'pxBelow'),
        at02: cs(s, 0.2), at03: cs(s, 0.3), r: [Wt.watchValue(r, 'dyAtLeast'), cs(r, 0.3).state, cs(r, 0.4).state],
        t: [Wt.watchValue(t, 'dyAtLeast'), cs(t, 0.1).state, Wt.nowValue('dyAtLeast', Wt.watchValue(t, 'dyAtLeast'), false, true)],
        px: Wt.condState(L, s, { k: 'pxBelow', v: 5000 }, true) };
      const watch = { '048770': { at: '2026-11-02', ts: 2, conds: [{ k: 'pxBelow', v: 5000 }, { k: 'dyAtLeast', v: 0.2 }] },
                      '900001': { at: '2026-11-01', ts: 1, conds: [{ k: 'dyAtLeast', v: 0.4 }] } };
      const hits = Wt.watchHits({ watch }, L);
      res.hits = hits.map(hitRow);
      res.marks = [...Wt.watchMarks({ watch }, L)];
      res.hitLine = Wt.hitText('dyAtLeast', 0.2, 0.2, false, true);
      const rh = rows(Wx, hits, L);
      res.rows = { text: text(rh), small: (rh.match(/data-small="1"/g) || []).length };
      const html = screen(L, watch);
      const card = (code) => html.split('data-ui-v2="watch-card"').find((x) => x.includes(`data-t="${code}"`)) || '';
      res.card = { text: text(card('048770')), line: (card('048770').match(/data-ui-v2="div-small"/g) || []).length,
        hidden: /div-[a-z]+-hidden/.test(card('048770')), smallChips: (card('048770').match(/data-small="1"/g) || []).length };
      res.card2 = { text: text(card('900001')), line: (card('900001').match(/data-ui-v2="div-small"/g) || []).length };
      res.lineTotal = text(html).split(P.smallLine).length - 1;
      const sh = sheet(Wx, L, watch, '048770');
      res.sheet = { text: text(sh), small: (sh.match(/data-small="1"/g) || []).length };
      const empty = { '048770': { at: '2026-11-02', conds: [{ k: 'pxBelow', v: 5000 }] } };
      res.sheetEmpty = text(sheet(Wx, L, empty, '048770'));
      logs.length = 0; Wt.watchGuardNote({ watch }, loadOf(D, { companies: [] }, true)); res.logs = [...logs];
      set(false, null, null);
      out = res;""")
    P = proposals()
    B, LINE = P["smallBasis"], P["smallLine"]
    assert got["val"] == 0.2 and got["small"] is True and got["smallPx"] is False
    assert got["at02"] == {"k": "dyAtLeast", "v": 0.2, "val": 0.2, "state": "met", "date": "2026-11-27", "small": True}, got["at02"]
    assert got["at03"]["state"] == "not" and got["at03"]["small"] is True
    # rounded as the chip shows it: 0.25% reads "0.3%" and meets 0.3 (the raw 0.25 would not); 0.05% keeps two decimals
    assert got["r"] == [0.3, "met", "not"] and got["t"] == [0.05, "not", f"0.05% · {B}"], (got["r"], got["t"])
    assert got["px"] == {"k": "pxBelow", "v": 5000, "val": 4350, "state": "met", "date": "2026-11-27"}       # no small key on other kinds
    # 홈's row: the same label in the approved hit line (받침 on 준: 이에요); the mark is the price date
    assert got["hitLine"] == f"배당수익률 0.2% 이상 조건에 맞아요. 지금 0.2% · {B}이에요."
    assert got["hits"] == [{"t": "048770", "s": "048770", "k": "pxBelow", "v": 5000, "val": 4350, "date": "2026-11-27"},
                           {"t": "048770", "s": "048770", "k": "dyAtLeast", "v": 0.2, "val": 0.2, "date": "2026-11-27", "small": True}], got["hits"]
    assert sorted(got["marks"]) == [["048770|dyAtLeast", "2026-11-27"], ["048770|pxBelow", "2026-11-27"]], got["marks"]
    assert got["rows"]["small"] == 1 and got["hitLine"] in got["rows"]["text"] and LINE not in got["rows"]["text"]   # 홈: label, no line
    # the card: the label on the chip, the line once, no hidden-yield line
    assert f"배당수익률 0.2% 이상\n· 지금 0.2% · {B}" in got["card"]["text"], got["card"]["text"]
    assert got["card"]["line"] == 1 and got["card"]["smallChips"] == 1 and got["card"]["hidden"] is False
    assert got["card"]["text"].count(LINE) == 1 and "주가 5,000원 이하" in got["card"]["text"]
    assert f"지금 0.3% · {B}" in got["card2"]["text"] and got["card2"]["line"] == 1 and got["lineTotal"] == 2
    # the sheet: the preview chip labelled; an empty field's today's value labelled too; no line in the sheet
    assert f"지금 0.2% · {B}" in got["sheet"]["text"] and got["sheet"]["small"] == 1 and LINE not in got["sheet"]["text"]
    assert f"지금 0.2% · {B}" in got["sheetEmpty"], got["sheetEmpty"]
    assert got["logs"] == ["[v2] watch list: dividend yield on the small-shareholder basis (dytSmall, labelled) for 2 stock(s): 900001 (0.25%), 048770 (0.23%)"], got["logs"]


def test_never_beside_an_all_holder_yield_never_us_never_without_exact_data_and_stale_is_shown_not_judged():
    got = run("""
      set(true, P.smallBasis, P.smallLine);
      const D = { pxDate: '2026-11-27', usPxDate: '2026-11-26', divCheck: { v: 1 }, fx: 1400, stocks: [
        tpc(),
        tpc({ t: '900003', nk: '보임', dyt: 1.53, dps: 66, dps3a: [66, 60, 55], dpsF: [1, 1, 1], divSt: 'same', dytSmall: 3.0, dpsSmall: 130.5 }),
        tpc({ t: '900004', nk: '영', dps: 0, dyt: 0, dps3a: [0, 0, 0], divSt: 'zero' }),
        { ...tpc(), t: 'ZZZZ', nk: 'Zed Inc.', cls: 'us', dy: null },
        tpc({ t: '900005', nk: '안맞음', dytSmall: 0.5 }),
        tpc({ t: '900006', nk: '권리', dvLine: 2 }),
        tpc({ t: '900007', nk: '예전 종가', pxd: '2026-11-25' }),
      ] };
      E.setDataShape(D);
      const L = loadOf(D, { companies: [] }, true), S = loadOf(D, { companies: [] }, false);
      const v = (t) => [Wt.watchValue(L.byT.get(t), 'dyAtLeast'), Wt.watchSmall(L.byT.get(t), 'dyAtLeast')];
      const res = { shown: v('900003'), zero: v('900004'), us: v('ZZZZ'), bad: v('900005'), mark2: v('900006') };
      const watch = Object.fromEntries(D.stocks.map((s, i) => [s.t, { at: '2026-11-01', ts: i + 1, conds: [{ k: 'dyAtLeast', v: 0.1 }] }]));
      const html = text(screen(L, watch));
      res.shownLabel = html.includes('지금 1.5% · ' + P.smallBasis);
      res.lines = html.split(P.smallLine).length - 1;                 // only TPC (048770) and the earlier close (900007)
      // stale data: shown with its label and line, never judged, no mark, no 홈 row
      res.stale = Wt.condState(S, S.byT.get('048770'), { k: 'dyAtLeast', v: 0.1 }, false);
      res.staleAll = Wt.condState(S, S.byT.get('900003'), { k: 'dyAtLeast', v: 0.1 }, false);
      res.staleHits = Wt.watchHits({ watch }, S).length; res.staleMarks = Wt.watchMarks({ watch }, S).size;
      const sh = text(screen(S, watch));
      res.staleScreen = { label: sh.includes('지금 0.2% · ' + P.smallBasis), lines: sh.split(P.smallLine).length - 1 };
      // a stock shown at an earlier close than its market's (pxd): shown, never judged, as the all-holder yield
      res.pxd = Wt.condState(L, L.byT.get('900007'), { k: 'dyAtLeast', v: 0.1 }, true);
      res.hits = Wt.watchHits({ watch }, L).map((x) => [x.t, x.small || false]);
      // an older file (no divCheck): blank, as today's Korean yield; the screen keeps 정보 없음 and no label or line
      E.setDataShape({});
      res.older = [Wt.watchValue(L.byT.get('048770'), 'dyAtLeast'), Wt.condState(L, L.byT.get('048770'), { k: 'dyAtLeast', v: 0.1 }, true).state];
      const oh = text(screen(L, { '048770': watch['048770'] }));
      res.olderScreen = { blank: oh.includes('정보 없음'), label: oh.includes(P.smallBasis), line: oh.includes(P.smallLine) };
      E.setDataShape(D);
      set(false, null, null);
      out = res;""")
    assert got["shown"] == [1.5, False] and got["shownLabel"] is False, got["shown"]       # the all-holder yield shows: never dytSmall
    assert got["zero"] == [0, False] and got["us"] == [None, False]
    assert got["bad"] == [None, False] and got["mark2"] == [None, False]                    # numbers that disagree · another mark
    assert got["lines"] == 2, got["lines"]
    assert got["stale"] == {"k": "dyAtLeast", "v": 0.1, "val": 0.2, "state": "stale", "date": "2026-11-27", "small": True}, got["stale"]
    assert got["staleAll"]["state"] == "stale" and "small" not in got["staleAll"]
    assert got["staleHits"] == 0 and got["staleMarks"] == 0
    assert got["staleScreen"] == {"label": True, "lines": 2}, got["staleScreen"]
    assert got["pxd"] == {"k": "dyAtLeast", "v": 0.1, "val": 0.2, "state": "stale", "date": "2026-11-25", "small": True}, got["pxd"]
    assert got["hits"] == [["900003", False], ["048770", True]], got["hits"]                 # watch order: latest added first
    assert got["older"] == [None, "blank"] and got["olderScreen"] == {"blank": True, "label": False, "line": False}, got
