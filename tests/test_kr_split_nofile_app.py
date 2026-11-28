# -*- coding: utf-8 -*-
"""공시로 확인하지 못한 분할 — 앱 쪽 (2026-11-27 · Jack 답 11 · 새 시험 파일 · #186 다시 짓기).

Jack, 2026-11-27 (그대로): "Any other stock gets its affected numbers blanked with '주식 수가 크게 바뀌었는데, 공시로 확인하지 못해서 이 숫자는
비워 두었어요.'" — 파이프라인(fetch_data.mark_split_nofile)이 과거 주가 기록 오류(pxBad)와 같은 칸 · 같은 창으로 숫자를 비우고 spNo · spNoF 를
달아요 (data.json · corp.json). 2.0 은 과거 주가 기록 오류 줄이 가는 자리마다 (섹션마다 한 번) 이 줄을 보여요: 52주까지 비웠으면 회사 페이지
머리의 52주 막대 자리 (모든 탭), 52주는 보이면 비운 숫자마다 그 자리 (요약의 출렁임 칸 · 실적의 주가 분해 · 가치의 출렁임 카드 · 내 기준과 맞는
정도 · 두 종목 비교). 예전 뱁새는 '–' 만 (줄 없음 · 내장 값으로 메우지 않아요). src/repair.js spNo · src/v2/fix.js spNoFor · fixnote.jsx.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import validate_data as V  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None or not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")), reason="node · esbuild 가 없어요")
MODS = {"R": "src/repair.js", "FX": "src/v2/fix.js", "FN": "src/v2/fixnote.jsx", "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx",
        "CP": "src/copy/v2.js", "K": "src/v2/company.js", "CMP": "src/v2/compare.jsx", "OLD": "src/corp.jsx", "OF": "src/fixnote.jsx", "D": "src/data.js"}
SP = "주식 수가 크게 바뀌었는데, 공시로 확인하지 못해서 이 숫자는 비워 두었어요."
PX = "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요."
PX1 = "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요."
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
ALL = list(V.PX_BAD_DATA)
OLDF = [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS]
FULL_T = "043260"                  # 시험 데이터의 성호전자: 사건이 22봉 안 — 모두 비움 (52주까지)
CALM_T = "030000"                  # 제일기획: 252봉보다 오래된 사건 — 시계열 전체 칸만 (52주는 보여요)
BOTH_T = "010170"                  # 대한광통신: 오래된 과거 주가 기록 오류(시계열 전체 칸) + 최근 분할(모두) — 두 표시
MARKED = {FULL_T: ("2026-10-20", ALL), CALM_T: ("2024-01-19", OLDF)}
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-spno-")
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


def fixture():
    """2.0 시험 데이터에서 세 종목을 파이프라인처럼 비운 data.json · corp.json (spNo · spNoF · 창에 든 칸만)."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(FIX, "corp.json"), encoding="utf-8") as f:
        corp = json.load(f)

    def mark(t, d, fl, key="spNo"):
        s = next(x for x in data["stocks"] if x["t"] == t)
        for k in fl:
            s.pop(k, None)
        s[key], s[key + "F"] = d, list(fl)
        c = next(x for x in corp["companies"] if x["t"] == t)
        c.update({k: None for k in V.PX_BAD_CORP if k in fl}, **{key: d, key + "F": list(fl)})
    for t, (d, fl) in MARKED.items():
        mark(t, d, fl)
    mark(BOTH_T, "2024-01-19", OLDF, "pxBad")
    mark(BOTH_T, "2026-10-20", ALL)
    for x in (next(s for s in data["stocks"] if s["t"] == BOTH_T), next(c for c in corp["companies"] if c["t"] == BOTH_T)):
        x["pxBadF"] = list(ALL)                                                    # 파이프라인처럼 두 목록의 합
    return data, corp


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { R, FX, FN, CO, CT, CP, K, CMP, OLD, OF, D } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            "const has = (x, id) => new RegExp('data-ui-v2=\"' + id + '\"').test(x);\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(_B['data'])}, 'utf8')); const CORP = JSON.parse(fs.readFileSync({json.dumps(_B['corp'])}, 'utf8'));\n"
            "const mk = (d, c) => ({ status: 'ok', data: d, corp: c, fresh: { md: null, days: 0, stale: false }, byT: new Map(d.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(c.companies.map((x) => [x.t, x])), preview: false });\n"
            "const LOAD = mk(DATA, CORP);\n"
            "const STORE = { data: { decks: [], notes: {}, assume: {} }, writable: false };\n"
            f"const SP = {json.dumps(SP, ensure_ascii=False)}; const PX = {json.dumps(PX, ensure_ascii=False)}; const PX1 = {json.dumps(PX1, ensure_ascii=False)};\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(autouse=True, scope="module")
def files():
    tmp = tempfile.mkdtemp()
    d, c = fixture()
    for name, obj in (("data", d), ("corp", c)):
        p = os.path.join(tmp, f"{name}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        _B[name] = p
    yield
    shutil.rmtree(tmp, ignore_errors=True)
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


def test_the_line_is_jacks_verbatim_recorded_and_built_into_2_0_only():
    got = run("out = { sp: C2.co.spNo, px: C2.co.pxBad, one: C2.co.pxBadOne };")
    assert got == {"sp": SP, "px": PX, "one": PX1}
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.spNo` | {SP} | Jack, 2026-11-27" in appr
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as fh:
        assert fh.read().count(SP) == 1                                           # 2.0 에 한 번 (글은 한 곳에)
    with open(os.path.join(ROOT, "baepsae.html"), encoding="utf-8") as fh:
        assert SP not in fh.read()                                                 # 예전 뱁새에는 줄이 없어요 ('–' 만)


def test_the_marks_and_which_line_each_place_gets():
    got = run("""
      const g = (t) => [LOAD.byT.get(t), LOAD.coByT.get(t)];
      const [f, fc] = g(FULL_T), [c, cc] = g(CALM_T), [b, bc] = g(BOTH_T), [sam, samc] = g('005930');
      const us = { t: 'X', cls: 'us', spNo: '2026-05-08', spNoF: ['vol'] };
      out = {
        fields: [R.spNoFields(f).length, R.spNoFields(c), R.spNoFields({ spNo: '2026-01-02' }).length, R.spNoFields(sam)],
        full: [FX.spNoFullFor(f, fc), FX.spNoFullFor(c, cc), FX.spNoFullFor(c, null), FX.spNoFullFor(us, null)],
        pxFull: [FX.pxBadFullFor(f, fc), FX.pxBadFullFor(c, cc), FX.pxBadPartFor(c, cc), FX.pxBadFor(f, null), FX.pxBadFor(us, null)],
        text: [FN.pxBadText(f, fc), FN.pxBadText(c, cc), FN.pxBadText(b, bc), FN.pxBadText(sam, samc)],
        one: [FN.pxBadOneText(c, cc, 'beta'), FN.pxBadOneText(c, cc, 'r36'), FN.pxBadOneText(c, cc, 'hi'), FN.pxBadOneText(f, fc, 'beta')],
        note: [text(renderToStaticMarkup(h(FN.PxBadNote, { s: f, co: fc }))).trim(), has(renderToStaticMarkup(h(FN.PxBadNote, { s: f, co: fc })), 'sp-no'),
          text(renderToStaticMarkup(h(FN.PxBadOneNote, { s: c, co: cc, field: 'beta' }))).trim(),
          has(renderToStaticMarkup(h(FN.PxBadOneNote, { s: c, co: cc, field: 'beta' })), 'sp-no-one')],
      };
      const keep = C2.co.spNo; C2.co.spNo = null;                                   // 문구가 없으면 줄도 없어요 (다른 줄로 바꾸지도 않아요)
      out.noWords = [FN.pxBadText(f, fc), FN.pxBadOneText(c, cc, 'beta')]; C2.co.spNo = keep;""", FULL_T=FULL_T, CALM_T=CALM_T, BOTH_T=BOTH_T)
    assert got["fields"] == [16, OLDF, 16, []]
    assert got["full"] == [True, False, False, False] and got["pxFull"] == [True, False, True, True, False]
    assert got["text"] == [SP, None, SP, None]                                     # 두 표시가 모두 있으면 분할의 줄 (더 새롭고 구체적인 까닭)
    assert got["one"] == [SP, SP, None, None]
    assert got["note"] == [SP, True, SP, True]
    assert got["noWords"] == [None, None]


COMPANY = """
  const page = (code, ctab = null) => renderToStaticMarkup(h(CO.Company, { load: LOAD, store: STORE, setStoreData() {}, pad: 0, code, ctab,
    disc: { status: 'none' }, nav: { setTab() {}, more() {}, back() {}, onWhy() {} } }));
  const tabs = [null, 'earn', 'value', 'div'];
  const one = (code) => tabs.map((t) => { const x = page(code, t); return { sp: count(x, SP), px: count(x, PX) + count(x, PX1), range: has(x, 'co-range'),
    decomp: has(x, 'co-decomp'), risk: has(x, 'co-risk'), na: count(x, C2.co.tiles.na) }; });
"""


def test_company_page_full_line_once_per_tab_in_the_52_week_bars_place():
    got = run(COMPANY + """
      out = { full: one(FULL_T), both: one(BOTH_T), sam: one('005930') };
      const x = page(FULL_T);
      out.order = [x.indexOf('data-ui-v2="co-price"'), x.indexOf('data-ui-v2="sp-no"'), x.indexOf('data-ui-v2="co-tabs"')];""",
        FULL_T=FULL_T, BOTH_T=BOTH_T)
    for k in ("full", "both"):
        assert [(t["sp"], t["px"]) for t in got[k]] == [(1, 0)] * 4, (k, got[k])   # 요약 · 실적 · 가치 · 배당 모두 그 줄 한 번 · 과거 주가 기록 오류 줄 없음
        assert not any(t["range"] or t["decomp"] or t["risk"] for t in got[k]), got[k]
    assert got["order"][0] < got["order"][1] < got["order"][2]
    assert all(t["sp"] == 0 and t["px"] == 0 and t["range"] for t in got["sam"])


def test_company_page_old_event_keeps_the_52_week_range_and_says_it_once_per_section():
    """사건이 252봉보다 오래된 종목: 52주 막대 그대로 · 비운 숫자마다 그 자리에 한 번 — 요약의 출렁임 칸, 실적의 주가 분해 (3년 주가), 가치의 출렁임
    카드. 배당 탭에는 비운 숫자가 없어요 (과거 주가 기록 오류 줄과 같은 자리)."""
    got = run(COMPANY + """
      const x = page(CALM_T), e = page(CALM_T, 'earn'), v = page(CALM_T, 'value');
      const inside = (html, id) => { const i = html.indexOf('data-ui-v2="' + id + '"'); return i >= 0 && html.indexOf(SP, i) > i; };
      out = { tabs: one(CALM_T), tile: inside(x, 'co-tiles'), decomp: /data-ui-v2="co-decomp" data-head="pxbad"/.test(e) && inside(e, 'co-decomp'),
        risk: /data-ui-v2="co-risk" data-rule="pxbad"/.test(v) && inside(v, 'co-risk'), band: has(v, 'co-risk-band'),
        dashes: [text(e).includes(C2.co.decomp.price + ' –'), /data-ui-v2="co-risk-px"[^>]*>–</.test(v)] };""", CALM_T=CALM_T)
    assert [(t["sp"], t["px"], t["range"]) for t in got["tabs"]] == [(1, 0, True), (1, 0, True), (1, 0, True), (0, 0, True)], got["tabs"]
    assert got["tile"] and got["decomp"] and got["risk"] and not got["band"] and got["dashes"] == [True, True]
    assert not any(t["na"] for t in got["tabs"])                                  # '자료가 없어요' 가 아니에요


def test_fit_rows_and_the_two_stock_compare_say_it_once():
    got = run("""
      const g = (t) => [LOAD.byT.get(t), LOAD.coByT.get(t)];
      const rows = (code) => K.cardRanks(LOAD.byT.get(code), DATA.stocks, 'market').rows;
      out = { fit: [FX.pxBadRowsBlank(...g(CALM_T), rows(CALM_T)), FX.pxBadRowsBlank(...g(FULL_T), rows(FULL_T))],
        oneLz: FN.pxBadOneText(...g(CALM_T), 'lz') };""", CALM_T=CALM_T, FULL_T=FULL_T)
    assert got["fit"] == [True, False] and got["oneLz"] == SP                     # 52주까지 비운 종목은 머리의 줄이 말해요
    src = open(os.path.join(ROOT, "src", "v2", "compare.jsx"), encoding="utf-8").read()
    assert 'pxBadText(s, co) || pxBadOneText(s, co, "vol")' in src and 'pxBadOneText(s, co, "beta") || pxBadText(s, co)' in src   # 같은 함수 → 같은 줄


def test_old_app_shows_dashes_only_and_never_the_built_in_numbers():
    got = run("""
      const view = (t) => renderToStaticMarkup(h(OLD.CompanyView, { data: CORP, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const look = (v) => ({ sp: count(v, SP), px: count(v, PX) + count(v, PX1), beta: /연 변동성 [0-9]/.test(text(v)), d3: text(v).includes('주가 (3년) —'),
        decomp: text(v).includes('주가는 무엇으로 움직였나'), decompNums: text(v).includes('이익(EPS) 변화'), loss: text(v).includes('적자 구간이 있어서') });
      const base = [{ t: '005930', nk: '삼성전자', s: 'semi', price: 78000, beta: 1.15, vol: 32, per: 14, x: { lo: 52300, hi: 84500 } }];
      const a = D.mergeStocks(base, [{ t: '005930', nk: '삼성전자', cls: 'kr', price: 206000, cap: 1204.3, spNo: '2026-10-20', spNoF: R.PX_BAD_ALL }])[0];
      out = { full: look(view(FULL_T)), calm: look(view(CALM_T)),
        merged: [a.beta, a.vol, a.noRisk, a.live, a.pxBad === undefined, a.spNo === undefined] };""", FULL_T=FULL_T, CALM_T=CALM_T)
    assert got["full"] == {"sp": 0, "px": 0, "beta": False, "d3": False, "decomp": False, "decompNums": False, "loss": False}, got["full"]
    assert got["calm"] == {"sp": 0, "px": 0, "beta": False, "d3": True, "decomp": True, "decompNums": False, "loss": False}, got["calm"]
    assert got["merged"] == [None, None, True, True, True, True]                  # 내장 베타 · 변동성으로 메우지 않아요 · 줄을 부르는 표시도 옮기지 않아요
