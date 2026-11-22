# -*- coding: utf-8 -*-
"""숨긴 한국 배당수익률의 줄: 관심 종목 · 두 종목 비교도 회사 페이지와 같은 줄 (say-why N-01 · N-02, 2026-11-22) — Node 로 진짜 함수를 불러요.

Jack's say-why rule (2026-11-08): a number the app hides says why on that screen. 관심 종목 (#143) and 두 종목 비교 (#155) were built
to reuse the company page's own line for a blank, but only dvLine 1 (co.div.shareHidden) was wired in. For every case the company
page's 배당 tile (company.jsx tileViews, its note in the number's place) or its no-statements line (fixnote.jsx NoStmtNote) gives,
the two screens now give the same line, from the same function (company.js divHiddenLine) and the same copy (co.div.*Hidden,
co.noStmt); where the company page gives none, they give none:
- dvLine 1 · 2 · 3 · 4 with the yield hidden -> co.div.shareHidden · rightsHidden · dataHidden · missingHidden;
- a hidden yield with no mark, an unknown mark (5), a mark on a yield that shows, a US stock with a mark -> no line;
- a company with no statements at all (fix.js noStmtFor) -> co.noStmt, once per 관심 종목 card even with PBR blank too.
The 관심 종목 line sits under the card (13px, theme colours); the 비교 cell shows "–" with the line under it.
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
MODS = {"E": "src/v2/engine.js", "K": "src/v2/company.js", "CO": "src/v2/company.jsx", "Cm": "src/v2/compare.jsx", "Wx": "src/v2/watch.jsx",
        "Ed": "src/v2/edit.js", "FX": "src/v2/fix.js", "CP": "src/copy/v2.js"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
L1 = "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요."               # Jack 2026-11-08
L2 = "유상증자로 주가 기준이 바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요."            # Jack 2026-11-15 (11)
L3 = "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요."          # Jack 2026-11-15 (13)
L4 = "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요."            # Jack 2026-11-19
NS = "공시된 재무제표가 아직 없어서 계산할 수 없어요."                                         # Jack 2026-11-14
LINES = [L1, L2, L3, L4, NS]
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-divlines-")
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


# The pipeline's marks on the fixture (as tests/test_v191j_div_lines_app.py sets them), plus 채비 with no statements at all.
CASES = [
    ("009150", "1"),          # 삼성전기: dvLine 1 (Jack's line of 11-08)
    ("005380", "2"),          # 현대차: dvLine 2 (주주배정 유상증자)
    ("000660", "3"),          # SK하이닉스: dvLine 3 (배당 표와 주식 수가 어긋남)
    ("035420", "4"),          # NAVER: dvLine 4 (회사 공시에 조각이 빠짐)
    ("055550", "none"),       # 신한지주: hidden, no mark -> no line
    ("005930", "unknown"),    # 삼성전자: an unknown mark 5 -> no line
    ("105560", "shown"),      # KB금융: mark 2 but the yield shows -> the number, no line
    ("AAPL", "us"),           # a US stock with a mark and no yield -> no line
    ("0011T0", "nostmt"),     # 채비: no statements at all -> co.noStmt
]
CODES = [t for t, _ in CASES]


def run(body):
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { E, K, CO, Cm, Wx, Ed, FX, CP } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8'));\n"
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'corp.json'))}, 'utf8'));\n"
            f"const LINES = {json.dumps(LINES, ensure_ascii=False)};\n"
            f"const CODES = {json.dumps(CODES)};\n"
            "const hide = (s) => { s.dps3a = s.dps3.map((d) => (d > 0 ? null : d)); s.dpsF = [null, null, null]; s.divSt = 'nc'; delete s.dyt; delete s.dz; };\n"
            "const st = (t) => DATA.stocks.find((x) => x.t === t), co = (t) => CORP.companies.find((x) => x.t === t);\n"
            "DATA.divCheck = { v: 1 };\n"
            "for (const s of DATA.stocks) if (s.cls === 'kr' && Array.isArray(s.dps3)) { s.dps3a = s.dps3.slice(); s.dpsF = [1, 1, 1]; s.divSt = 'same';"
            " if (s.price > 0 && s.dps3[0] != null) s.dyt = Math.round(s.dps3[0] / s.price * 10000) / 100; }\n"
            "hide(st('009150')); st('009150').dvWhy = { v: 1, st: 'nc-unexplained' }; co('009150').dvWhy = { v: 1, st: 'nc-unexplained' }; st('009150').dvLine = 1;\n"
            "hide(st('005380')); st('005380').dvLine = 2;\n"
            "hide(st('000660')); st('000660').dvLine = 3;\n"
            "hide(st('035420')); st('035420').dvLine = 4;\n"
            "hide(st('055550'));\n"
            "hide(st('005930')); st('005930').dvLine = 5;\n"
            "st('105560').dvLine = 2;\n"
            "st('AAPL').dvLine = 3; st('AAPL').dy = null;\n"
            # 채비: a new listing with no 사업보고서 at all (as the 2026-11-14 publish had it: fix.js noStmtFor)
            "st('0011T0').fy = null; Object.assign(co('0011T0'), { fy: null, rev: [null, null, null], op: [null, null, null], ni: [null, null, null] });\n"
            "E.setDataShape(DATA);\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const C = (t) => LOAD.coByT.get(t) || null;\n"
            "const STORE = { data: { decks: [], notes: {}, assume: {} }, writable: false };\n"
            "const page = (code) => renderToStaticMarkup(h(CO.Company, { load: LOAD, store: STORE, setStoreData() {}, pad: 0, code, ctab: null,"
            " disc: { status: 'none' }, nav: { setTab() {}, more() {}, back() {}, onWhy() {} } }));\n"
            # the company page's line for a blank 배당수익률: the 배당 tile's note (the number's place), else the no-statements line above the tiles
            "const coLine = (t) => { const v = CO.tileViews(LOAD, LOAD.byT.get(t)).find((x) => x.topic === 'div');"
            " if (v && v.note) return { line: v.note, ui: v.noteUi || null, number: v.number || null };"
            " const html = page(t); return { line: /data-ui-v2=\"no-stmt\"/.test(html) ? C2.co.noStmt : null, ui: /data-ui-v2=\"no-stmt\"/.test(html) ? 'no-stmt' : null, number: v ? v.number || null : null }; };\n"
            "const ctx = { stocks: DATA.stocks, points: { value: 3, div: 2 }, names: Ed.indNames(DATA.stocks), load: LOAD, groups: null, row: null };\n"
            "const cmp = (t) => { const c = Cm.compareCells(LOAD.byT.get(t), C(t), ctx).dy; return { text: c.text, note: c.note, blank: c.data.blank || null }; };\n"
            "const watchHtml = (conds) => renderToStaticMarkup(h(Wx.WatchScreen, { load: LOAD, store: { data: { v: 1, decks: [],"
            " watch: Object.fromEntries(Object.entries(conds).map(([t, cs], i) => [t, { at: '2026-11-01', ts: i + 1, conds: cs }])) }, writable: true },"
            " setStoreData() {}, pad: 0, onBack() {}, onAdd() {} }));\n"
            "const cardOf = (html, t) => { const i = html.indexOf(`data-ui-v2=\"watch-card\" data-t=\"${t}\"`); if (i < 0) return null;"
            " const j = html.indexOf('</section>', i); return html.slice(i, j); };\n"
            "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_copy_is_the_approved_lines():
    got = run("out = [C2.co.div.shareHidden, C2.co.div.rightsHidden, C2.co.div.dataHidden, C2.co.div.missingHidden, C2.co.noStmt];")
    assert got == LINES


def test_compare_and_watch_give_the_company_pages_line_for_every_case():
    got = run("""
      const dy = [{ k: 'dyAtLeast', v: 1 }];
      out = CODES.map((t) => {
        const html = cardOf(watchHtml({ [t]: dy }), t);
        const chip = (html.match(/data-ui-v2="watch-chip" data-k="dyAtLeast" data-state="([a-z]+)"/) || [])[1] || null;
        const uis = [...html.matchAll(/data-ui-v2="((?:div-[a-z]+-hidden)|no-stmt)"/g)].map((m) => m[1]);
        return { t, company: coLine(t), key: K.divHiddenLine(LOAD.byT.get(t), C(t)), noStmt: FX.noStmtFor(LOAD.byT.get(t), C(t)),
                 cmp: cmp(t), watch: { chip, lines: LINES.map((l) => count(html, l)), uis } };
      });""")
    by = {g["t"]: g for g in got}
    want = {"1": (L1, "div-share-hidden"), "2": (L2, "div-rights-hidden"), "3": (L3, "div-data-hidden"), "4": (L4, "div-missing-hidden"),
            "nostmt": (NS, "no-stmt")}
    for t, case in CASES:
        g = by[t]
        line, ui = want.get(case, (None, None))
        # the company page itself: the line it gives this blank (the test's anchor)
        assert g["company"]["line"] == line and g["company"]["ui"] == ui, (t, case, g["company"])
        # 두 종목 비교: the same line under the cell, with "–" in the number's place (the number itself when it shows)
        if case == "shown":
            assert g["cmp"]["text"].endswith("%") and g["cmp"]["note"] is None and g["company"]["number"], (t, g["cmp"])
        else:
            assert g["cmp"]["text"] == "\u2013" and g["cmp"]["note"] == g["company"]["line"], (t, case, g["cmp"], g["company"])
        # 관심 종목: the chip is 정보 없음 for a hidden yield and the same line sits once under the card; the number and no line when it shows
        assert g["watch"]["chip"] in (("met", "not", "stale") if case == "shown" else ("blank",)), (t, case, g["watch"])
        assert g["watch"]["lines"] == [1 if l == line else 0 for l in LINES], (t, case, g["watch"])
        assert g["watch"]["uis"] == ([ui] if ui else []), (t, case, g["watch"])
        assert g["cmp"]["blank"] == (ui if case in ("1", "2", "3", "4") else None), (t, g["cmp"])      # the cell's data-blank (smoke hook)
    # the screens read the one mark the company page reads (company.js divHiddenLine), nothing of their own
    assert [by[t]["key"] for t in CODES] == ["shareHidden", "rightsHidden", "dataHidden", "missingHidden", None, None, None, None, None]
    assert [by[t]["noStmt"] for t in CODES] == [False] * 8 + [True]


def test_a_card_with_pbr_and_the_yield_blank_says_the_no_statements_line_once():
    got = run("""
      const html = cardOf(watchHtml({ '0011T0': [{ k: 'pbrBelow', v: 1 }, { k: 'dyAtLeast', v: 1 }] }), '0011T0');
      const states = [...html.matchAll(/data-ui-v2="watch-chip" data-k="([a-zA-Z]+)" data-state="([a-z]+)"/g)].map((m) => [m[1], m[2]]);
      const pbrOnly = cardOf(watchHtml({ '0011T0': [{ k: 'pbrBelow', v: 1 }] }), '0011T0');
      const pxOnly = cardOf(watchHtml({ '0011T0': [{ k: 'pxBelow', v: 1000 }] }), '0011T0');
      out = { states, lines: LINES.map((l) => count(html, l)), pbrOnly: LINES.map((l) => count(pbrOnly, l)), pxOnly: LINES.map((l) => count(pxOnly, l)) };""")
    assert got["states"] == [["pbrBelow", "blank"], ["dyAtLeast", "blank"]], got
    assert got["lines"] == [0, 0, 0, 0, 1] and got["pbrOnly"] == [0, 0, 0, 0, 1], got           # once, for either blank or both
    assert got["pxOnly"] == [0] * 5, got                                                       # no blank: no line


def test_one_card_per_stock_carries_only_its_own_line():
    # all the cases on one 관심 종목 screen: each card its own line (or none), no line twice, none on another stock's card
    got = run("""
      const dy = [{ k: 'dyAtLeast', v: 1 }];
      const html = watchHtml(Object.fromEntries(CODES.map((t) => [t, dy])));
      out = { all: LINES.map((l) => count(html, l)), cards: CODES.map((t) => LINES.map((l) => count(cardOf(html, t), l))),
              style: [...html.matchAll(/data-ui-v2="(?:div-[a-z]+-hidden|no-stmt)" style="([^"]*)"/g)].map((m) => m[1]) };""")
    assert got["all"] == [1, 1, 1, 1, 1], got["all"]
    own = {"009150": 0, "005380": 1, "000660": 2, "035420": 3, "0011T0": 4}
    for t, lines in zip(CODES, got["cards"]):
        assert lines == [1 if own.get(t) == k else 0 for k in range(5)], (t, lines)
    assert len(got["style"]) == 5
    for css in got["style"]:
        size = re.search(r"font-size:(\d+)px", css)
        assert size and int(size.group(1)) >= 12 and "var(--" in css, css                   # 12px 밑 없음 · 색은 테마 토큰 (밝은 · 어두운 화면)


def test_an_older_file_without_the_split_check_gives_no_line_anywhere():
    # before v19.1b (no divCheck): divHiddenLine is null, so neither screen says a line the company page would not
    got = run("""
      E.setDataShape({});
      out = CODES.slice(0, 4).map((t) => [K.divHiddenLine(LOAD.byT.get(t), C(t)), cmp(t).note, LINES.slice(0, 4).map((l) => count(cardOf(watchHtml({ [t]: [{ k: 'dyAtLeast', v: 1 }] }), t), l))]);
      E.setDataShape(DATA);""")
    for key, note, lines in got:
        assert key is None and note is None and lines == [0, 0, 0, 0], (key, note, lines)
