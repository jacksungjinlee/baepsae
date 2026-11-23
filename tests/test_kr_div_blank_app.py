# -*- coding: utf-8 -*-
"""2026-11-23 앱 (Node 로): 파이프라인이 보고서의 주당 배당을 비운 한국 회사 (data.json dps 없음 + dvLine · fetch_data.div_raw_guard).

- A · dvLine 4 (proofSub nodps: 총액은 있는데 보통주 주당 칸이 0 · '-'): 보통주가 받았는지 몰라요 → '자료가 없어요' (배당을 줘요가 아님) + 줄 4
  "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요." · 배당성향 없음.
- B · dvLine 3 (proofSub div: 주당 칸의 값이 주당 금액이 아님 — 와이엔텍): 회사는 배당해요 → '배당을 줘요' + 줄 3 (예전과 같아요) · 총액으로 센
  배당성향은 그대로.
- 그 밖 (dps 가 있는 종목 · 다른 표시 · 예전 파일 · 미국)은 예전 그대로. 새 문구 없음 (승인된 두 줄과 '자료가 없어요' · '배당을 줘요')."""
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
L3 = "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요."
L4 = "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요."
A, B = "066570", "033780"                         # fixture 의 배당 회사 둘 (오늘 데이터의 종목이 아니에요)
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
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n')).split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8'));\n"
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'corp.json'))}, 'utf8'));\n"
            "const st = (t) => DATA.stocks.find((x) => x.t === t), co = (t) => CORP.companies.find((x) => x.t === t);\n"
            # 파이프라인처럼: 확인한 배당 칸 (divCheck 가 있는 파일) · 두 회사의 올해 주당 배당을 비우고 표시를 달아요 · 그 회사의 총액 (억원)
            "DATA.divCheck = { v: 1 };\n"
            "for (const s of DATA.stocks) if (s.cls === 'kr' && Array.isArray(s.dps3)) { s.dps3a = s.dps3.slice(); s.dpsF = [1, 1, 1]; s.divSt = 'same';"
            " if (s.price > 0 && s.dps3[0] != null) s.dyt = Math.round(s.dps3[0] / s.price * 10000) / 100; }\n"
            "const blank = (t, line) => { const s = st(t); delete s.dps; s.dps3 = [null, ...s.dps3.slice(1)]; s.dps3a = [null, null, null];"
            " s.dpsF = [null, null, null]; s.divSt = 'nd'; delete s.dyt; delete s.dz; s.dvLine = line; s.fy = 2025;"
            " Object.assign(co(t), { cash3: [100, 90, 80], fy: 2025 }); };\n"
            f"blank('{A}', 4); blank('{B}', 3);\n"
            "E.setDataShape(DATA);\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const S = (t) => LOAD.byT.get(t), O = (t) => LOAD.coByT.get(t) || null;\n"
            "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_kind_comes_from_the_mark_only_when_the_per_share_dividend_is_blank():
    got = run(f"""
      const k = (s) => K.divBlankKind(s);
      out = {{ a: k(S('{A}')), b: k(S('{B}')), hasDps: k({{ ...S('005930'), dvLine: 4 }}),
        other: [1, 2, 5, true, '4'].map((v) => k({{ ...S('{A}'), dvLine: v }})), noMark: k({{ ...S('{A}'), dvLine: undefined }}),
        us: k({{ ...S('AAPL'), dvLine: 4, dps: undefined }}) }};
      E.setDataShape({{}});
      out.old = [k(S('{A}')), k(S('{B}'))];
      E.setDataShape(DATA);""")
    assert got["a"] == "unknown" and got["b"] == "pays"
    assert got["hasDps"] is None and got["other"] == [None] * 5 and got["noMark"] is None and got["us"] is None
    assert got["old"] == [None, None]                                                  # 예전 파일 (분할 확인 전): 아무것도 바뀌지 않아요


def test_a_says_not_known_with_line_four_and_b_says_it_pays_with_line_three():
    got = run(f"""
      const v = (t) => {{ const r = K.divKr(S(t), O(t)); return [r.rule, r.yieldPct, r.dps, r.dpsOk]; }};
      out = {{ a: v('{A}'), b: v('{B}'), line: [K.divHiddenLine(S('{A}'), O('{A}')), K.divHiddenLine(S('{B}'), O('{B}')),
                K.divHiddenLine(S('{A}'), null)],
        state: [E.krDivState(S('{A}'), O('{A}')), E.krDivState(S('{B}'), O('{B}'))],
        pay: [K.payout(S('{A}'), O('{A}')), K.payout(S('{B}'), O('{B}'))], pm: [K.perMillionKr(S('{A}')), K.perMillionKr(S('{B}'))],
        exNo: [E.exclusionsHit(S('{A}')).includes('noDiv'), E.exclusionsHit(S('{B}')).includes('noDiv')] }};""")
    assert got["a"] == ["na", None, None, False] and got["b"] == ["pays", None, None, False]
    assert got["line"] == ["missingHidden", "dataHidden", "missingHidden"]
    assert got["state"] == [None, None]                                                 # 수익률 · 금액 · 순위는 예전처럼 모름
    assert got["pay"][0] is None and got["pay"][1]["pct"] > 0                            # 배당성향 (총액 ÷ 순이익): B 만
    assert got["pm"] == [None, None] and got["exNo"] == [False, False]                  # '배당 없는 회사' 로 빼지 않아요


def test_the_tile_and_the_tab_show_the_line_under_the_truthful_head():
    got = run(f"""
      const tile = (t) => {{ const v = CO.tileViews(LOAD, S(t)).find((x) => x.topic === 'div'); return [v.rule, v.phrase, v.number, v.note ?? null, v.noteUi ?? null]; }};
      const tab = (t) => {{ const html = renderToStaticMarkup(h(CT.DivTab, {{ load: LOAD, s: S(t) }})); return [text(html), html]; }};
      const [ta, ha] = tab('{A}'), [tb, hb] = tab('{B}');
      out = {{ tile: [tile('{A}'), tile('{B}')], ta, tb, ua: /data-ui-v2="co-div-missing-hidden"/.test(ha), ub: /data-ui-v2="co-div-data-hidden"/.test(hb),
        pa: /data-ui-v2="co-payout"/.test(ha), pb: /data-ui-v2="co-payout"/.test(hb),
        na: C2.co.tiles.na, pays: C2.co.tiles.div.pays, none: C2.co.div.head.none, L: [C2.co.div.dataHidden, C2.co.div.missingHidden] }};""")
    assert got["L"] == [L3, L4]
    a, b = got["tile"]
    assert a == ["na", got["na"], None, L4, "div-missing-hidden"]
    assert b == ["pays", got["pays"], None, L3, "div-data-hidden"]
    assert got["ta"][:2] == [got["na"], L4] and got["ua"] and not got["pa"]
    assert got["tb"][:2] == [got["pays"], L3] and got["ub"] and got["pb"]
    for t in (got["ta"], got["tb"]):
        assert got["none"] not in t and t.count(L3) + t.count(L4) == 1                   # '배당을 주지 않았어요' 없음 · 줄은 하나


def test_compare_and_watch_get_the_same_line_through_the_one_function():
    """두 종목 비교 · 관심 종목은 divHiddenLine 을 그대로 써요 (화면은 tests/smoke_v2.py scene_div_blank 이 봐요): 수익률 칸은 비고 그 줄."""
    src = {f: open(os.path.join(ROOT, "src", "v2", f), encoding="utf-8").read() for f in ("compare.jsx", "watch.jsx")}
    assert "divHiddenLine(s, co)" in src["compare.jsx"] and "divHiddenLine(s, co)" in src["watch.jsx"]
    got = run(f"""out = [K.divKr(S('{A}'), O('{A}')).yieldPct, K.divKr(S('{B}'), O('{B}')).yieldPct];""")
    assert got == [None, None]


def test_stocks_with_a_per_share_dividend_are_unchanged():
    """dps 가 있는 종목 (표시가 있든 없든) 은 예전 규칙 그대로: 삼성전자 수익률 · 숨긴 수익률의 줄 3 · 배당 없음 0원."""
    got = run("""
      const s3 = { ...S('000660'), dyt: undefined, dps3a: [null, null, null], dpsF: [null, null, null], divSt: 'nd', dvLine: 3 };
      const z = { ...S('005930'), dps: 0, dps3: [0, 0, 0], dps3a: [0, 0, 0], dpsF: [null, null, null], divSt: 'zero', dyt: 0, dvLine: undefined };
      out = { sam: K.divKr(S('005930'), O('005930')).rule, hid: [K.divKr(s3, O('000660')).rule, K.divHiddenLine(s3, O('000660'))],
              zero: [K.divKr(z, O('005930')).rule, K.divHiddenLine(z, O('005930'))], kind: [K.divBlankKind(s3), K.divBlankKind(z)] };""")
    assert got["sam"] not in ("na", None) and got["hid"] == ["pays", "dataHidden"] and got["zero"] == ["none", None] and got["kind"] == [None, None]
