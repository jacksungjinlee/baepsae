# -*- coding: utf-8 -*-
"""소액주주 배당수익률 (차등배당 · Jack 2026-11-19 Q6 "labelled as the 소액주주 rate"): the app side, both apps — Node runs the real code.

The pipeline (fetch_data.small_holder_div, tests/test_smallholder_div.py) puts dpsSmall · dytSmall on a 차등배당 payer whose yield is
hidden with dvLine 3. The screens show it only behind a switch that is OFF until Jack approves the label and the line:
- 2.0: src/v2/smallcfg.js SMALL_YIELD.on false and C.co.div.smallBasis · smallLine null -> every screen exactly as before (the 배당
  tile, the 배당 tab and 두 종목 비교 keep "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 …").
- With the switch on and the lines set (test words, not proposals): the 요약 배당 tile shows "배당수익률 {y} · {label}" with the line in
  the hidden-yield line's place, the 배당 tab shows the 소액주주 dividend per share and yield labelled, 두 종목 비교 the yield labelled with
  the line; 관심 종목 keeps today's line and its condition (the all-holder yield), and nothing shows beside a yield that is shown, on a
  US stock, an older file, numbers that disagree, or another mark.
- 예전 뱁새: src/smallyield.js SMALL_YIELD_OLD off with no label -> the 기업 분석 tile keeps "배당수익률".
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
MODS = {"E": "src/v2/engine.js", "K": "src/v2/company.js", "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx", "Cm": "src/v2/compare.jsx",
        "Wx": "src/v2/watch.jsx", "Ed": "src/v2/edit.js", "SC": "src/v2/smallcfg.js", "OLD": "src/smallyield.js", "CP": "src/copy/v2.js"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
L3 = "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요."          # Jack 2026-11-15 (13)
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-smallyield-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
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


# 000660 (fixture price 1,418,000원) plays a 차등배당 payer: yield hidden with dvLine 3, 소액주주 dividend 3,000원 -> 0.21%.
# 000270 plays one whose 소액주주 numbers disagree, 005930 one whose yield shows (both fields would be ignored).
def run(body):
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { E, K, CO, CT, Cm, Wx, Ed, SC, OLD, CP } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8'));\n"
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'corp.json'))}, 'utf8'));\n"
            f"const L3 = {json.dumps(L3, ensure_ascii=False)};\n"
            "const hide = (s) => { s.dps3a = s.dps3.map((d) => (d > 0 ? null : d)); s.dpsF = [null, null, null]; s.divSt = 'nd'; delete s.dyt; delete s.dz; };\n"
            "const st = (t) => DATA.stocks.find((x) => x.t === t), co = (t) => CORP.companies.find((x) => x.t === t);\n"
            "DATA.divCheck = { v: 1 };\n"
            "for (const s of DATA.stocks) if (s.cls === 'kr' && Array.isArray(s.dps3)) { s.dps3a = s.dps3.slice(); s.dpsF = [1, 1, 1]; s.divSt = 'same';"
            " if (s.price > 0 && s.dps3[0] != null) s.dyt = Math.round(s.dps3[0] / s.price * 10000) / 100; }\n"
            "hide(st('000660')); Object.assign(st('000660'), { dvLine: 3, dpsSmall: 3000, dytSmall: Math.round(3000 / 1418000 * 10000) / 100 });\n"
            "Object.assign(co('000660'), { dpsSmall: 3000, dytSmall: st('000660').dytSmall });\n"
            "hide(st('000270')); Object.assign(st('000270'), { dvLine: 3, dpsSmall: 1, dytSmall: 9.99 });\n"
            "Object.assign(st('005930'), { dvLine: 3, dpsSmall: 1, dytSmall: 0.01 });\n"
            "E.setDataShape(DATA);\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const C = (t) => LOAD.coByT.get(t) || null;\n"
            "const tile = (t) => { const v = CO.tileViews(LOAD, LOAD.byT.get(t)).find((x) => x.topic === 'div'); return v ? { number: v.number || null, note: v.note || null, ui: v.noteUi || null, ysmall: (v.data || {}).ysmall ?? null, y: (v.data || {}).y ?? null } : null; };\n"
            "const tab = (t) => renderToStaticMarkup(h(CT.DivTab, { load: LOAD, s: LOAD.byT.get(t) }));\n"
            "const ctx = { stocks: DATA.stocks, points: { value: 3, div: 2 }, names: Ed.indNames(DATA.stocks), load: LOAD, groups: null, row: null };\n"
            "const cmp = (t) => { const c = Cm.compareCells(LOAD.byT.get(t), C(t), ctx).dy; return { text: c.text, note: c.note, blank: c.data.blank || null, ysmall: c.data.ysmall ?? null }; };\n"
            "const watchHtml = (t) => renderToStaticMarkup(h(Wx.WatchScreen, { load: LOAD, store: { data: { v: 1, decks: [],"
            " watch: { [t]: { at: '2026-11-01', ts: 1, conds: [{ k: 'dyAtLeast', v: 0.1 }] } } }, writable: true }, setStoreData() {}, pad: 0, onBack() {}, onAdd() {} }));\n"
            "const turnOn = () => { SC.SMALL_YIELD.on = true; C2.co.div.smallBasis = 'LBL'; C2.co.div.smallLine = 'LINE'; };\n"
            "const turnOff = () => { SC.SMALL_YIELD.on = false; C2.co.div.smallBasis = null; C2.co.div.smallLine = null; };\n"
            "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_switches_are_off_and_the_words_wait_for_jack():
    got = run("out = { on: SC.SMALL_YIELD.on, basis: C2.co.div.smallBasis, line: C2.co.div.smallLine, old: OLD.SMALL_YIELD_OLD };")
    assert got == {"on": False, "basis": None, "line": None, "old": {"on": False, "label": None}}


def test_div_small_view_rules():
    got = run("""
      const v = (t, on = true) => K.divSmallView(LOAD.byT.get(t), C(t), on);
      const s = LOAD.byT.get('000660');
      const res = { off: v('000660', false), dflt: K.divSmallView(s, C('000660')), on: v('000660'), bad: v('000270'), shown: v('005930') };
      const tweak = (k, x) => { const o = s[k]; s[k] = x; const r = v('000660'); if (o === undefined) delete s[k]; else s[k] = o; return r; };
      res.mark2 = tweak('dvLine', 2); res.noMark = tweak('dvLine', undefined); res.big = tweak('dytSmall', 31);
      res.us = tweak('cls', 'us'); res.noDps = tweak('dpsSmall', undefined); res.zero = tweak('dpsSmall', 0);
      E.setDataShape({}); res.older = v('000660'); E.setDataShape(DATA);
      out = res;""")
    assert got["off"] is None and got["dflt"] is None
    assert got["on"] == {"y": 0.21, "dps": 3000}
    assert got["noMark"] == {"y": 0.21, "dps": 3000}                 # the record's own line (dvLine 3) may have been blanked: still shown
    for k in ("bad", "shown", "mark2", "big", "us", "noDps", "zero", "older"):
        assert got[k] is None, (k, got[k])


def test_off_every_screen_is_as_before():
    got = run("""
      out = { tile: tile('000660'), tab: tab('000660'), cmp: cmp('000660') };
      turnOn(); C2.co.div.smallLine = null; out.halfTile = tile('000660'); out.halfCmp = cmp('000660'); turnOff();
      SC.SMALL_YIELD.on = false; C2.co.div.smallBasis = 'LBL'; C2.co.div.smallLine = 'LINE'; out.wordsOnly = tile('000660'); turnOff();""")
    for t in (got["tile"], got["halfTile"], got["wordsOnly"]):
        assert t["number"] is None and t["note"] == L3 and t["ui"] == "div-data-hidden" and t["ysmall"] is None, t
    assert 'data-ui-v2="co-div-data-hidden"' in got["tab"] and "co-div-small" not in got["tab"] and "co-yield-small" not in got["tab"]
    for c in (got["cmp"], got["halfCmp"]):
        assert c["text"] == "\u2013" and c["note"] == L3 and c["blank"] == "div-data-hidden" and c["ysmall"] is None


def test_on_the_company_page_and_compare_show_the_small_holder_yield_labelled():
    got = run("""
      turnOn();
      const html = tab('000660');
      out = { tile: tile('000660'), tab: text(html), raw: html, cmp: cmp('000660'), shown: tile('005930'), bad: tile('000270'), badCmp: cmp('000270'),
              watch: text(watchHtml('000660')) };
      turnOff();""")
    t = got["tile"]
    assert t["number"] == "배당수익률 0.2% · LBL" and t["note"] == "LINE" and t["ui"] == "div-small" and t["ysmall"] == 0.21 and t["y"] is None
    assert 'data-ui-v2="co-div-small"' in got["raw"] and 'data-ui-v2="co-dps-small" data-dps="3000"' in got["raw"]
    assert 'data-ui-v2="co-yield-small" data-y="0.21"' in got["raw"] and "co-div-data-hidden" not in got["raw"]
    assert "LINE" in got["tab"] and "3,000원" in got["tab"].replace("\n", "") and "1주당 1년 배당 · LBL" in got["tab"] and "배당수익률 · LBL" in got["tab"]
    assert L3 not in got["tab"]
    c = got["cmp"]
    assert c["text"] == "0.2% · LBL" and c["note"] == "LINE" and c["blank"] is None and c["ysmall"] == 0.21
    # a yield that shows keeps its number alone; numbers that disagree keep today's line
    assert got["shown"]["number"].startswith("배당수익률 ") and "LBL" not in got["shown"]["number"] and got["shown"]["note"] is None
    assert got["bad"]["note"] == L3 and got["bad"]["number"] is None and got["badCmp"]["note"] == L3
    # 관심 종목 keeps today's line (its condition reads the all-holder yield, dyt)
    assert L3 in got["watch"] and "LINE" not in got["watch"] and "LBL" not in got["watch"]


def test_old_app_label():
    got = run("""
      const row = { t: '000660', dpsSmall: 3000, dytSmall: 0.21 };
      out = { off: OLD.smallYieldLabel(row), on: OLD.smallYieldLabel(row, { on: true, label: 'L' }), noLabel: OLD.smallYieldLabel(row, { on: true, label: null }),
              none: OLD.smallYieldLabel({ t: '005930' }, { on: true, label: 'L' }), zero: OLD.smallYieldLabel({ dpsSmall: 0, dytSmall: 0 }, { on: true, label: 'L' }) };""")
    assert got == {"off": None, "on": "L", "noLabel": None, "none": None, "zero": None}
    src = open(os.path.join(ROOT, "src", "corp.jsx"), encoding="utf-8").read()
    assert 'label={smallYieldLabel(c) ? `배당수익률 · ${smallYieldLabel(c)}` : "배당수익률"}' in src


def test_built_pages_carry_no_proposed_words():
    for name in ("app.html", "app-preview.html", "baepsae.html"):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            html = f.read()
        assert "소액주주 기준" not in html and "소액주주에게 배당을 더" not in html, name
