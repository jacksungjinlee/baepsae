# -*- coding: utf-8 -*-
"""#179 (Jack, 2026-11-27: "#179: yes. The dividend shows as unknown with the existing line "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서
배당수익률은 비워 두었어요." Block only if many appear in one run.") — 앱 (Node 로): 파이프라인이 올해 배당을 '모름'으로 비운 한국 회사 (총액은
있는데 보통주 주당 칸이 0 · '-' · data.json dps 없음 + dvLine 4 · proofSub nodps) 는 2.0 이 배당을 보여 주는 네 자리 모두에서 그 승인된 줄을 한 번씩
보여 줘요 — 줄 4 의 열쇠(co.div.missingHidden)가 이미 쓰는 자리 그대로: 요약의 배당 칸 (숫자 자리) · 배당 탭 · 관심 종목 카드 (배당수익률 조건) ·
두 종목 비교의 배당수익률 칸. 새 문구 없음."""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"E": "src/v2/engine.js", "K": "src/v2/company.js", "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx", "CP": "src/copy/v2.js",
        "CMP": "src/v2/compare.jsx", "W": "src/v2/watch.jsx"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
L4 = "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요."
A = "066570"                                  # fixture 의 배당 회사 (오늘 데이터의 종목이 아니에요)
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
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


def run(body):
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { E, K, CO, CT, CP, CMP, W } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n')).split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8'));\n"
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'corp.json'))}, 'utf8'));\n"
            "const st = (t) => DATA.stocks.find((x) => x.t === t), co = (t) => CORP.companies.find((x) => x.t === t);\n"
            # 파이프라인처럼 (tests/test_kr_div_blank_app.py 와 같은 꼴): 확인한 배당 칸 · A 의 올해 주당 배당을 모름으로 비우고 줄 4 · 그 회사의 총액
            "DATA.divCheck = { v: 1 };\n"
            "for (const s of DATA.stocks) if (s.cls === 'kr' && Array.isArray(s.dps3)) { s.dps3a = s.dps3.slice(); s.dpsF = [1, 1, 1]; s.divSt = 'same';"
            " if (s.price > 0 && s.dps3[0] != null) s.dyt = Math.round(s.dps3[0] / s.price * 10000) / 100; }\n"
            "const blank = (t) => { const s = st(t); delete s.dps; delete s.dy; s.dps3 = [null, ...s.dps3.slice(1)]; s.dps3a = [null, null, null];"
            " s.dpsF = [null, null, null]; s.divSt = 'nd'; delete s.dyt; delete s.dz; s.dvLine = 4; s.fy = 2025;"
            " Object.assign(co(t), { cash3: [84.08, 84.08, 72.07], fy: 2025 }); };\n"
            f"blank('{A}');\n"
            "E.setDataShape(DATA);\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const S = (t) => LOAD.byT.get(t), O = (t) => LOAD.coByT.get(t) || null;\n"
            "const count = (xs, line) => xs.filter((x) => x === line).length;\n"
            "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_line_is_the_approved_one_under_its_existing_key():
    got = run("out = { line: C2.co.div.missingHidden, key: K.divHiddenLine(S('" + A + "'), O('" + A + "')), ui: K.DIV_HIDDEN_UI.missingHidden };")
    assert got == {"line": L4, "key": "missingHidden", "ui": "div-missing-hidden"}


def test_an_unknown_dividend_shows_the_line_once_in_each_place_that_shows_a_dividend():
    """요약의 배당 칸 · 배당 탭 · 관심 종목 카드 · 두 종목 비교의 배당수익률 칸: 저마다 그 줄 한 번 · 수익률 · 주당 배당 숫자 없음 · '배당을 주지
    않았어요' 없음 (예전에는 0원 · 0.0% 로 보였어요)."""
    got = run(f"""
      const tile = CO.tileViews(LOAD, S('{A}')).find((x) => x.topic === 'div');
      const tab = renderToStaticMarkup(h(CT.DivTab, {{ load: LOAD, s: S('{A}') }}));
      const cell = CMP.compareCells(S('{A}'), O('{A}'), {{ stocks: DATA.stocks, points: null, names: null, load: LOAD, groups: null, row: null }}).dy;
      const store = {{ data: {{ v: 2, decks: [], watch: {{ '{A}': {{ at: '2026-11-05', conds: [{{ k: 'dyAtLeast', v: 1 }}] }} }} }}, writable: true }};
      const watch = renderToStaticMarkup(h(W.WatchScreen, {{ load: LOAD, store, setStoreData: () => {{}}, pad: 0, onBack: () => {{}}, onAdd: () => {{}} }}));
      const card = watch.slice(watch.indexOf('data-ui-v2="watch-card"'));
      out = {{
        tile: [tile.rule, tile.phrase, tile.number, tile.note, tile.noteUi, tile.phrase === C2.co.tiles.na],
        tab: [count(text(tab), C2.co.div.missingHidden), /data-ui-v2="co-div-missing-hidden"/.test(tab), /data-ui-v2="co-dps"/.test(tab),
              text(tab).includes(C2.co.div.head.none), (tab.match(/co-div-missing-hidden/g) || []).length],
        cmp: [cell.text, cell.note, cell.data.blank || null, cell.data.y],
        watch: [count(text(card), C2.co.div.missingHidden), (card.match(/data-ui-v2="div-missing-hidden"/g) || []).length],
        none: C2.co.div.head.none,
      }};""")
    rule, phrase, number, note, ui, is_na = got["tile"]
    assert (rule, number, note, ui, is_na) == ("na", None, L4, "div-missing-hidden", True), got["tile"]
    assert got["tab"] == [1, True, False, False, 1], got["tab"]
    assert got["cmp"] == ["–", L4, "div-missing-hidden", ""], got["cmp"]
    assert got["watch"] == [1, 1], got["watch"]


def test_a_stock_with_a_known_dividend_gets_no_line():
    """같은 자리에서 주당 배당이 있는 회사 (삼성전자) 는 그 줄이 없어요 — 줄은 파이프라인이 모름으로 비운 회사에만."""
    got = run("""
      const t = '005930';
      const tile = CO.tileViews(LOAD, S(t)).find((x) => x.topic === 'div');
      const tab = renderToStaticMarkup(h(CT.DivTab, { load: LOAD, s: S(t) }));
      out = { tile: tile.note ?? null, tab: text(tab).includes(C2.co.div.missingHidden), cmp: CMP.compareCells(S(t), O(t), { stocks: DATA.stocks, points: null, names: null, load: LOAD, groups: null, row: null }).dy.note,
              key: K.divHiddenLine(S(t), O(t)) };""")
    assert got == {"tile": None, "tab": False, "cmp": None, "key": None}, got
