# -*- coding: utf-8 -*-
"""v19.1i 앱: 주식 수가 바뀌었는데 그것을 설명하는 공시가 하나도 없어 배당수익률을 숨긴 한국 회사 (data.json dvWhy nc-unexplained) 에만
Jack 의 줄 (2026-11-08 승인) "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요." — Node 로 직접.
리뷰 2026-11-15: 그 말이 맞을 때만 — 공시가 배율을 주는 nc-mismatch (대한제강 ×1.66 · 엘앤씨바이오) 에는 줄이 없어요.

- 2.0 회사 페이지: 요약의 배당 칸(배당을 줘요 밑, 숫자 자리)과 배당 탭('배당을 줘요' 밑)에 한 번씩. 요약과 탭 둘 다 한 화면에 한 번.
- 수익률이 보이면 · nc-mismatch 이면 · 다른 이유로 숨겼으면(dvWhy 없음: 깨끗하지 않은 배율 · 회사분할 · 주주배정 유상증자 · 배당 표가
  어긋남 · 조회 실패) · 미국 종목 · v19.1b 전 파일이면 줄 없음.
- corp.json 의 dvWhy 만 있어도 (data.json 을 못 읽은 칸) 같은 판단이에요.
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
MODS = {"E": "src/v2/engine.js", "K": "src/v2/company.js", "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx", "CP": "src/copy/v2.js"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
LINE = "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요."
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
            "const { E, K, CO, CT, CP } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8'));\n"
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'corp.json'))}, 'utf8'));\n"
            f"const LINE = {json.dumps(LINE, ensure_ascii=False)};\n"
            # 파이프라인처럼: 삼성전기 = 공시 없이 주식 수가 바뀌어 숨김 (data.json dvWhy nc-unexplained) · 현대차 = 다른 이유로 숨김 (dvWhy 없음) ·
            # SK하이닉스 = corp.json 에만 dvWhy · 삼성전자 = 되살린 수익률 (dvProof) · KB금융 = 숨김 결론이 있어도 수익률이 보이면 줄 없음 ·
            # 신한지주 = 공시가 배율을 주는 nc-mismatch (숨김 · 줄 없음)
            "const hide = (s) => { s.dps3a = s.dps3.map((d) => (d > 0 ? null : d)); s.dpsF = [null, null, null]; s.divSt = 'nc'; delete s.dyt; delete s.dz; };\n"
            "const st = (t) => DATA.stocks.find((x) => x.t === t), co = (t) => CORP.companies.find((x) => x.t === t);\n"
            "DATA.divCheck = { v: 1 };\n"
            "for (const s of DATA.stocks) if (s.cls === 'kr' && Array.isArray(s.dps3)) { s.dps3a = s.dps3.slice(); s.dpsF = [1, 1, 1]; s.divSt = 'same';"
            " if (s.price > 0 && s.dps3[0] != null) s.dyt = Math.round(s.dps3[0] / s.price * 10000) / 100; }\n"
            "hide(st('009150')); st('009150').dvWhy = { v: 1, st: 'nc-unexplained' }; co('009150').dvWhy = { v: 1, st: 'nc-unexplained' };\n"
            "hide(st('055550')); st('055550').dvWhy = { v: 1, st: 'nc-mismatch' }; co('055550').dvWhy = { v: 1, st: 'nc-mismatch' };\n"
            "hide(st('005380'));\n"
            "hide(st('000660')); co('000660').dvWhy = { v: 1, st: 'nc-unexplained' };\n"
            "st('005930').dvProof = { v: 1, y0: 'today', yrs: [], c: [1, null, null], shr: 1 };\n"
            "st('105560').dvWhy = { v: 1, st: 'nc-unexplained' };\n"
            "E.setDataShape(DATA);\n"
            "const mk = (d, c) => ({ status: 'ok', data: d, corp: c, fresh: { md: null, days: 0, stale: false }, byT: new Map(d.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(c.companies.map((x) => [x.t, x])), preview: false });\n"
            "const LOAD = mk(DATA, CORP);\n"
            "const STORE = { data: { decks: [], notes: {}, assume: {} }, writable: false };\n"
            "const page = (code, ctab = null) => renderToStaticMarkup(h(CO.Company, { load: LOAD, store: STORE, setStoreData() {}, pad: 0, code, ctab,"
            " disc: { status: 'none' }, nav: { setTab() {}, more() {}, back() {}, onWhy() {} } }));\n"
            "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


CODES = ["009150", "005380", "000660", "005930", "105560", "AAPL", "055550"]


def test_the_rule_for_the_line():
    got = run("""
      const C = (t) => LOAD.coByT.get(t) || null;
      out = { exact: CODES.map((t) => K.divShareHidden(LOAD.byT.get(t), C(t))), noCo: K.divShareHidden(LOAD.byT.get('000660'), null) };
      E.setDataShape({});
      out.old = CODES.map((t) => K.divShareHidden(LOAD.byT.get(t), C(t)));
      E.setDataShape(DATA);
      out.copy = C2.co.div.shareHidden;""".replace("CODES", json.dumps(CODES)))
    assert got["exact"] == [True, False, True, False, False, False, False]           # 신한지주: nc-mismatch 는 줄 없음
    assert got["noCo"] is False                                                                    # corp.json 의 칸이 없으면 data.json 만
    assert got["old"] == [False] * 7                                                               # v19.1b 전 파일: 줄 없음
    assert got["copy"] == LINE


def test_the_line_sits_in_the_dividend_tile_and_under_the_dividend_tab_head_once():
    got = run("""
      const tile = (t) => { const v = CO.tileViews(LOAD, LOAD.byT.get(t)).find((x) => x.topic === 'div'); return v ? [v.phrase, v.number, v.note ?? null, v.noteUi ?? null] : null; };
      out = { tile: CODES.map(tile),
        page: CODES.map((t) => [count(page(t), LINE), count(page(t, 'div'), LINE)]),
        ui: [/data-ui-v2="div-share-hidden"/.test(page('009150')), /data-ui-v2="co-div-share-hidden"/.test(page('009150', 'div'))],
        tab: count(renderToStaticMarkup(h(CT.DivTab, { load: LOAD, s: LOAD.byT.get('009150') })), LINE),
        pays: count(page('009150', 'div'), C2.co.tiles.div.pays) };""".replace("CODES", json.dumps(CODES)))
    t = got["tile"]
    assert t[0][0] == "배당을 줘요" and t[0][1] is None and t[0][2:] == [LINE, "div-share-hidden"]     # 숫자 자리에 그 줄
    assert t[2][2] == LINE                                                                       # corp.json 의 dvWhy 만으로도
    assert t[1][2] is None and t[3][2] is None and t[4][2] is None and t[5][2] is None and t[6][2] is None   # 다른 이유 · 수익률 · 미국 · nc-mismatch
    assert t[3][1] and t[4][1]                                                                     # 수익률이 보이는 칸은 그대로 숫자
    assert got["page"] == [[1, 1], [0, 0], [1, 1], [0, 0], [0, 0], [0, 0], [0, 0]]                  # 요약에 한 번 · 배당 탭에 한 번
    assert got["ui"] == [True, True] and got["tab"] == 1 and got["pays"] >= 1
