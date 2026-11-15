# -*- coding: utf-8 -*-
"""v19.1j 앱 (Jack, 2026-11-15 답 11 · 13): 숨긴 한국 배당수익률의 줄 — 파이프라인이 data.json dvLine 하나로 이유를 정해요 (Node 로).

- 1 → Jack 의 줄 (2026-11-08) · 2 → "유상증자로 주가 기준이 바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요." ·
  3 → "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요."
- 자리: 요약의 배당 칸(배당을 줘요 밑, 숫자 자리)과 배당 탭('배당을 줘요' 밑) — #130 의 줄과 같은 자리 · 한 화면에 줄은 하나만.
- 수익률이 보이면 · 표시가 없거나 모르는 값이면 · 미국 종목 · v19.1b 전 파일이면 줄 없음 (배당 없음 0원에 붙은 표시는 관문이 막아요). 글자는 13px (12px 밑 없음) · 색은 테마 토큰.
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
MODS = {"E": "src/v2/engine.js", "K": "src/v2/company.js", "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx", "CP": "src/copy/v2.js"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
L1 = "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요."
L2 = "유상증자로 주가 기준이 바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요."
L3 = "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요."
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
            f"const L = {json.dumps([L1, L2, L3], ensure_ascii=False)};\n"
            # 파이프라인처럼: 삼성전기 = 줄 1 (nc-unexplained) · 현대차 = 줄 2 (주주배정 유상증자) · SK하이닉스 = 줄 3 (배당 표가 어긋남) ·
            # 신한지주 = 줄 없이 숨김 (총액 없음 · 방식을 모르는 유상증자 …) · KB금융 = 줄 2 표시가 있어도 수익률이 보이면 줄 없음 ·
            # 삼성전자 = 모르는 표시 4 (줄 없음) · 애플 = 미국 (줄 없음)
            "const hide = (s) => { s.dps3a = s.dps3.map((d) => (d > 0 ? null : d)); s.dpsF = [null, null, null]; s.divSt = 'nc'; delete s.dyt; delete s.dz; };\n"
            "const st = (t) => DATA.stocks.find((x) => x.t === t), co = (t) => CORP.companies.find((x) => x.t === t);\n"
            "DATA.divCheck = { v: 1 };\n"
            "for (const s of DATA.stocks) if (s.cls === 'kr' && Array.isArray(s.dps3)) { s.dps3a = s.dps3.slice(); s.dpsF = [1, 1, 1]; s.divSt = 'same';"
            " if (s.price > 0 && s.dps3[0] != null) s.dyt = Math.round(s.dps3[0] / s.price * 10000) / 100; }\n"
            "hide(st('009150')); st('009150').dvWhy = { v: 1, st: 'nc-unexplained' }; co('009150').dvWhy = { v: 1, st: 'nc-unexplained' }; st('009150').dvLine = 1;\n"
            "hide(st('005380')); st('005380').dvLine = 2;\n"
            "hide(st('000660')); st('000660').dvLine = 3;\n"
            "hide(st('055550'));\n"
            "st('105560').dvLine = 2;\n"
            "hide(st('005930')); st('005930').dvLine = 4;\n"
            "st('AAPL').dvLine = 3;\n"
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


CODES = ["009150", "005380", "000660", "055550", "105560", "005930", "AAPL"]


def test_the_mark_picks_the_line():
    got = run("""
      const C = (t) => LOAD.coByT.get(t) || null;
      out = { key: CODES.map((t) => K.divHiddenLine(LOAD.byT.get(t), C(t))), one: CODES.map((t) => K.divShareHidden(LOAD.byT.get(t), C(t))),
              noCo: K.divHiddenLine(LOAD.byT.get('005380'), null) };
      E.setDataShape({});
      out.old = CODES.map((t) => K.divHiddenLine(LOAD.byT.get(t), C(t)));
      E.setDataShape(DATA);
      out.copy = [C2.co.div.shareHidden, C2.co.div.rightsHidden, C2.co.div.dataHidden];""".replace("CODES", json.dumps(CODES)))
    assert got["key"] == ["shareHidden", "rightsHidden", "dataHidden", None, None, None, None]   # 표시 없음 · 수익률 · 모르는 값 · 미국은 줄 없음
    assert got["one"] == [True, False, False, False, False, False, False]                        # #130 의 판단 그대로 (줄 1 만)
    assert got["noCo"] == "rightsHidden" and got["old"] == [None] * 7 and got["copy"] == [L1, L2, L3]


def test_each_line_sits_in_the_tile_and_under_the_tab_head_once_and_never_two():
    got = run("""
      const tile = (t) => { const v = CO.tileViews(LOAD, LOAD.byT.get(t)).find((x) => x.topic === 'div'); return v ? [v.phrase, v.number, v.note ?? null, v.noteUi ?? null] : null; };
      out = { tile: CODES.map(tile),
        page: CODES.map((t) => [page(t), page(t, 'div')].map((html) => L.map((l) => count(html, l)))),
        ui: [/data-ui-v2="div-rights-hidden"/.test(page('005380')), /data-ui-v2="co-div-rights-hidden"/.test(page('005380', 'div')),
             /data-ui-v2="div-data-hidden"/.test(page('000660')), /data-ui-v2="co-div-data-hidden"/.test(page('000660', 'div'))],
        style: [page('005380'), page('000660', 'div')].map((html) => (html.match(/data-ui-v2="(?:co-)?div-(?:rights|data)-hidden" style="([^"]*)"/) || [])[1] || '') };""".replace("CODES", json.dumps(CODES)))
    t = got["tile"]
    assert t[1][0] == "배당을 줘요" and t[1][1] is None and t[1][2:] == [L2, "div-rights-hidden"]          # 숫자 자리에 그 줄
    assert t[2][0] == "배당을 줘요" and t[2][1] is None and t[2][2:] == [L3, "div-data-hidden"]
    assert t[0][2:] == [L1, "div-share-hidden"]                                                         # #130 의 줄 그대로
    assert all(t[i][2] is None for i in (3, 4, 5, 6))
    assert t[4][1]                                                                                      # 수익률이 보이는 칸은 그대로 숫자
    own = {0: 0, 1: 1, 2: 2}
    for i, (summary, tab) in enumerate(got["page"]):
        want = [1 if own.get(i) == k else 0 for k in range(3)]
        assert summary == want and tab == want, (CODES[i], summary, tab)                                 # 요약 · 배당 탭에 한 번씩 · 줄은 하나만
    assert got["ui"] == [True, True, True, True]
    for css in got["style"]:
        size = re.search(r"font-size:(\d+)px", css)
        assert size and int(size.group(1)) >= 12 and "var(--" in css, css                                 # 12px 밑 없음 · 색은 테마 토큰 (밝은 · 어두운 화면)
