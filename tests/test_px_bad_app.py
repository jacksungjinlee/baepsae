# -*- coding: utf-8 -*-
"""과거 주가 기록 오류 (Jack, 2026-11-14) — 앱 쪽: src/repair.js pxBad · pxBadFields · pxBadFull · src/v2/fix.js · src/v2/fixnote.jsx PxBadNote ·
PxBadOneNote · src/copy/v2.js co.pxBad · co.pxBadOne · 예전 뱁새 src/fixnote.jsx PxBadLine · PxBadOneLine · src/data.js mergeStocks, 그리고 비운 숫자를
엔진 · 목록 · 규칙이 '빈 칸'으로 다루는지 (Node 로 직접).

- 파이프라인(fetch_data.py mark_px_bad)이 계산 창에 움직임이 든 숫자만 비우고 pxBad · pxBadF 를 달아요 (Jack 2026-11-14 저녁).
- 52주까지 비운 종목 (움직임이 252봉 안): 2.0 회사 페이지 머리의 52주 막대 자리에 "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는
  비워 두었어요." 한 번 (모든 탭) · 출렁임 칸 "–" · 출렁임 카드와 주가 분해 없음. 예전 뱁새 기업분석 · 비교 · 고르기도 그 줄.
- 52주는 보이는 종목 (움직임이 252봉보다 오래됨): 52주 막대 · 1 · 3개월 · 1년 수익률 · 추세 점수는 그대로, 비운 숫자마다 그 자리에 "과거 주가 기록
  일부에 오류가 있어서 이 숫자는 비워 두었어요." (출렁임 칸 · 출렁임 카드 · 주가 분해 · 내 기준의 낮은 변동성 줄 · 예전 뱁새의 베타 줄 · 주가 분해 ·
  비교 표 · 고르기).
- 홈 종목 순위의 추세에서는 52주까지 비운 종목만, 낮은 변동성에서는 둘 다 빠져요 (0 이 아니에요).
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
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"R": "src/repair.js", "FX": "src/v2/fix.js", "FN": "src/v2/fixnote.jsx", "E": "src/v2/engine.js", "K": "src/v2/company.js",
        "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx", "CP": "src/copy/v2.js", "RK": "src/v2/ranks.js", "OF": "src/fixnote.jsx",
        "OLD": "src/corp.jsx", "D": "src/data.js", "P": "src/v2/pf.js"}
LINE = "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요."
ONE = "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요."
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
ALL = list(V.PX_BAD_DATA)
OLDF = [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS]
YF = [k for k in V.PX_BAD_DATA if k in V.PX_BAD_ALWAYS or k in V.PX_BAD_WIN["y"]]
BAD_T = "043260"                  # 시험 데이터의 성호전자 (추세 1위): 움직임이 22봉 안 — 모두 비움
MID_T = "010170"                  # 대한광통신: 252봉 안 · 64봉 밖 — 52주까지 (3개월 · 1개월은 보여요)
CALM_T = "030000"                 # 제일기획 (낮은 변동성 위쪽): 252봉보다 오래된 움직임 — 52주는 보여요
MARKED = {BAD_T: ("2026-10-20", ALL), MID_T: ("2026-05-08", YF), CALM_T: ("2024-01-19", OLDF)}
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


def fixture():
    """2.0 시험 데이터 (tests/fixtures/v2) 에서 세 종목을 파이프라인처럼 비운 data.json · corp.json (창에 든 칸만 · validate_data.PX_BAD_CORP)."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(FIX, "corp.json"), encoding="utf-8") as f:
        corp = json.load(f)
    for t, (d, fl) in MARKED.items():
        s = next(x for x in data["stocks"] if x["t"] == t)
        assert s.get("mom") is not None and s.get("vol") is not None and s.get("lo") is not None
        for k in fl:
            s.pop(k, None)
        s["pxBad"], s["pxBadF"] = d, list(fl)
        c = next(x for x in corp["companies"] if x["t"] == t)
        c.update({k: None for k in V.PX_BAD_CORP if k in fl}, pxBad=d, pxBadF=list(fl))
    return data, corp


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { R, FX, FN, E, K, CO, CT, CP, RK, OF, OLD, D, P } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            "const has = (x, id) => new RegExp('data-ui-v2=\"' + id + '\"').test(x);\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(_B['data'])}, 'utf8')); const CORP = JSON.parse(fs.readFileSync({json.dumps(_B['corp'])}, 'utf8'));\n"
            f"const ODATA = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8'));"
            f" const OCORP = JSON.parse(fs.readFileSync({json.dumps(os.path.join(FIX, 'corp.json'))}, 'utf8'));\n"
            "const mk = (d, c) => ({ status: 'ok', data: d, corp: c, fresh: { md: null, days: 0, stale: false }, byT: new Map(d.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(c.companies.map((x) => [x.t, x])), preview: false });\n"
            "const LOAD = mk(DATA, CORP), OLOAD = mk(ODATA, OCORP);\n"
            "const STORE = { data: { decks: [], notes: {}, assume: {} }, writable: false };\n"
            f"const LINE = {json.dumps(LINE, ensure_ascii=False)}; const ONE = {json.dumps(ONE, ensure_ascii=False)};\n"
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
    if "p" in _B:                                                                   # 번들 임시 폴더도 지워요 (남기지 않아요)
        shutil.rmtree(_B.pop("p"), ignore_errors=True)




# ── 순수 함수 · 문구 ──
def test_the_marks_the_windows_and_the_two_lines():
    got = run("""
      const g = (t) => [LOAD.byT.get(t), LOAD.coByT.get(t)];
      const [b, bc] = g(BAD_T), [m, mc] = g(MID_T), [c, cc] = g(CALM_T), [sam, samc] = g('005930');
      const us = { t: 'X', cls: 'us', pxBad: '2026-05-08', pxBadF: ['vol'] };
      out = {
        all: R.PX_BAD_ALL,
        fields: [R.pxBadFields(b).length, R.pxBadFields(c), R.pxBadFields({ pxBad: '2026-01-02' }).length, R.pxBadFields({ pxBad: '2026-01-02', pxBadF: 'x' }).length,
          R.pxBadFields(sam)],
        full: [R.pxBadFull(b), R.pxBadFull(m), R.pxBadFull(c), R.pxBadFull(sam), R.pxBadFull({ pxBad: '2026-01-02' })],
        fullFor: [FX.pxBadFullFor(b, bc), FX.pxBadFullFor(m, mc), FX.pxBadFullFor(c, cc), FX.pxBadFullFor(sam, samc), FX.pxBadFullFor(us, null)],
        partFor: [FX.pxBadPartFor(b, bc), FX.pxBadPartFor(c, cc), FX.pxBadPartFor(c, null), FX.pxBadPartFor({ ...c, pxBad: undefined, pxBadF: undefined }, cc),
          FX.pxBadPartFor(us, null)],
        hides: ['hi', 'mom', 'mz', 'r3', 'beta', 'lz', 'r36'].map((k) => [FX.pxBadHidesFor(b, bc, k), FX.pxBadHidesFor(m, mc, k), FX.pxBadHidesFor(c, cc, k)]),
        text: [FN.pxBadText(b, bc), FN.pxBadText(m, mc), FN.pxBadText(c, cc), FN.pxBadText(sam, samc)],
        one: [FN.pxBadOneText(b, bc, 'beta'), FN.pxBadOneText(c, cc, 'beta'), FN.pxBadOneText(c, cc, 'r36'), FN.pxBadOneText(c, cc, 'hi'),
          FN.pxBadOneText(c, cc, 'mz'), FN.pxBadOneText(sam, samc, 'beta')],
        note: [text(renderToStaticMarkup(h(FN.PxBadNote, { s: b, co: bc }))).trim(), renderToStaticMarkup(h(FN.PxBadNote, { s: c, co: cc })),
          text(renderToStaticMarkup(h(FN.PxBadOneNote, { s: c, co: cc, field: 'beta' }))).trim(), renderToStaticMarkup(h(FN.PxBadOneNote, { s: b, co: bc, field: 'beta' })),
          has(renderToStaticMarkup(h(FN.PxBadOneNote, { s: c, co: cc, field: 'beta' })), 'px-bad-one')],
        same: [C2.co.pxBad, OF.FIX_PX_BAD, C2.co.pxBadOne, OF.FIX_PX_BAD_ONE],
        old: [text(renderToStaticMarkup(h(OF.PxBadLine, { c: bc }))).trim(), renderToStaticMarkup(h(OF.PxBadLine, { c: cc })),
          text(renderToStaticMarkup(h(OF.PxBadOneLine, { c: cc, field: 'beta' }))).trim(), renderToStaticMarkup(h(OF.PxBadOneLine, { c: bc, field: 'beta' })),
          renderToStaticMarkup(h(OF.PxBadOneLine, { c: cc, field: 'hi' })), renderToStaticMarkup(h(OF.PxBadLine, { c: bc, lang: 'en' })),
          renderToStaticMarkup(h(OF.PxBadOneLine, { c: cc, field: 'beta', lang: 'en' }))],
      };
      const keep = C2.co.pxBadOne; C2.co.pxBadOne = null;                         // 문구가 없으면 줄도 없어요 (빈 자리 없이)
      out.noWords = renderToStaticMarkup(h(FN.PxBadOneNote, { s: c, co: cc, field: 'beta' })); C2.co.pxBadOne = keep;""",
        BAD_T=BAD_T, MID_T=MID_T, CALM_T=CALM_T)
    assert got["all"] == ALL                                                       # 앱의 목록 = 관문의 목록
    assert got["fields"] == [16, OLDF, 16, 16, []]                                 # 목록 없는 표시는 모두 비운 것으로
    assert got["full"] == [True, True, False, False, True]
    assert got["fullFor"] == [True, True, False, False, False]
    assert got["partFor"] == [False, True, True, True, False]                      # 두 파일 중 하나면 돼요 · 미국 종목은 아니에요
    assert got["hides"] == [[True, True, False], [True, True, False], [True, True, False], [True, False, False], [True, True, True],
                            [True, True, True], [True, True, True]]
    assert got["text"] == [LINE, LINE, None, None]
    assert got["one"] == [None, ONE, ONE, None, None, None]
    assert got["note"] == [LINE, "", ONE, "", True]
    assert got["same"] == [LINE, LINE, ONE, ONE]
    assert got["old"] == [LINE, "", ONE, "", "", "", ""]                            # 영어 화면: 승인된 영어 글이 없어 줄 없이
    assert got["noWords"] == ""


def test_both_lines_are_jacks_and_recorded_and_built():
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.pxBad` | {LINE} | Jack, 2026-11-14" in appr and f"| `co.pxBadOne` | {ONE} | Jack, 2026-11-14" in appr
    assert f"| Old app (`baepsae.html`, `src/fixnote.jsx`) price history, 2026-11-14 | {LINE} | Jack, 2026-11-14" in appr
    assert f"| Old app (`baepsae.html`, `src/fixnote.jsx`) price history, one number, 2026-11-14 | {ONE} | Jack, 2026-11-14" in appr
    for f in ("app.html", "baepsae.html"):
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            html = fh.read()
        assert html.count(LINE) == 1 and html.count(ONE) == 1, f                  # 빌드한 두 페이지에 한 번씩 (글은 한 곳에 · 다시 빌드했어요)


# ── 2.0 회사 페이지 ──
COMPANY = """
  const page = (load, code, ctab = null) => renderToStaticMarkup(h(CO.Company, { load, store: STORE, setStoreData() {}, pad: 0, code, ctab,
    disc: { status: 'none' }, nav: { setTab() {}, more() {}, back() {}, onWhy() {} } }));
  const tabs = [null, 'earn', 'value', 'div'];
  const one = (load, code) => tabs.map((t) => { const x = page(load, code, t); return { n: count(x, LINE), k: count(x, ONE), range: has(x, 'co-range'),
    decomp: has(x, 'co-decomp'), risk: has(x, 'co-risk'), na: count(x, C2.co.tiles.na) }; });
"""


def test_company_page_full_line_once_per_tab_where_the_52_week_range_is_blank():
    got = run(COMPANY + """
      out = { bad: one(LOAD, BAD_T), mid: one(LOAD, MID_T), was: one(OLOAD, BAD_T), sam: one(LOAD, '005930'), us: one(LOAD, 'AAPL') };
      const x = page(LOAD, BAD_T);
      out.order = [x.indexOf('data-ui-v2="co-price"'), x.indexOf('data-ui-v2="px-bad"'), x.indexOf('data-ui-v2="co-tabs"')];""",
        BAD_T=BAD_T, MID_T=MID_T)
    for k in ("bad", "mid"):
        assert [(t["n"], t["k"]) for t in got[k]] == [(1, 0)] * 4, (k, got[k])     # 요약 · 실적 · 가치 · 배당 모두 그 줄 한 번 · 짧은 줄 없음
        assert not any(t["range"] or t["decomp"] or t["risk"] for t in got[k]), got[k]
    assert got["order"][0] < got["order"][1] < got["order"][2]
    was = got["was"]
    assert was[0]["range"] and was[1]["decomp"] and was[2]["risk"] and not any(t["n"] or t["k"] for t in was), was
    for k in ("sam", "us"):
        assert all(t["n"] == 0 and t["k"] == 0 and t["range"] for t in got[k]), (k, got[k])
    assert got["sam"][2]["risk"]


def test_company_page_old_bad_day_keeps_the_52_week_range_and_says_it_per_number():
    """52주는 보이는 종목 (움직임이 252봉보다 오래됨): 머리의 52주 막대 그대로 · 그 줄 없음 · 비운 숫자마다 짧은 줄 — 요약의 출렁임 칸, 실적의 주가 분해
    (3년 주가), 가치의 출렁임 카드. 배당 탭에는 비운 숫자가 없어요."""
    got = run(COMPANY + """
      const x = page(LOAD, CALM_T), e = page(LOAD, CALM_T, 'earn'), v = page(LOAD, CALM_T, 'value');
      const inside = (html, id) => { const i = html.indexOf('data-ui-v2="' + id + '"'); return i >= 0 && html.indexOf(ONE, i) > i; };
      out = { tabs: one(LOAD, CALM_T), tile: inside(x, 'co-tiles'), decomp: /data-ui-v2="co-decomp" data-head="pxbad"/.test(e) && inside(e, 'co-decomp'),
        decompNums: has(e, 'co-decomp-eq'), risk: /data-ui-v2="co-risk" data-rule="pxbad"/.test(v) && inside(v, 'co-risk'),
        riskTitle: text(v).includes(C2.co.tiles.label.risk), band: has(v, 'co-risk-band') };""", CALM_T=CALM_T)
    assert [(t["n"], t["k"], t["range"]) for t in got["tabs"]] == [(0, 1, True), (0, 1, True), (0, 1, True), (0, 0, True)], got["tabs"]
    assert got["tile"] and got["decomp"] and not got["decompNums"] and got["risk"] and got["riskTitle"] and not got["band"]
    assert not any(t["na"] for t in got["tabs"])                                  # '자료가 없어요' 가 아니에요


def test_the_risk_tile_is_held_at_a_dash_and_carries_the_short_line_only_when_the_52_week_range_shows():
    got = run("""
      const view = (load, code) => CO.tileViews(load, load.byT.get(code)).map((v) => [v.topic, v.rule, v.phrase, v.number, v.basis, !!v.art, v.note || null]);
      out = { bad: view(LOAD, BAD_T), calm: view(LOAD, CALM_T), was: view(OLOAD, BAD_T), sam: view(LOAD, '005930') };""", BAD_T=BAD_T, CALM_T=CALM_T)
    assert [v for v in got["bad"] if v[0] == "risk"] == [["risk", "pxbad", "–", None, None, False, None]], got["bad"]
    assert [v for v in got["calm"] if v[0] == "risk"] == [["risk", "pxbad", "–", None, None, False, ONE]], got["calm"]
    assert [v for v in got["bad"] if v[0] != "risk"] == [v for v in got["was"] if v[0] != "risk"]
    assert [v[1] for v in got["sam"] if v[0] == "risk"][0] != "pxbad"


def test_fit_rows_blank_only_for_blanked_scores_and_the_short_line_under_them():
    got = run("""
      const r = (load, code) => Object.fromEntries(K.cardRanks(load.byT.get(code), load.data.stocks, 'market').rows.map((x) => [x.id, x.blank ? 'blank' : x.side || 'na']));
      const rows = (code) => K.cardRanks(LOAD.byT.get(code), DATA.stocks, 'market').rows;
      const g = (t) => [LOAD.byT.get(t), LOAD.coByT.get(t)];
      out = { bad: r(LOAD, BAD_T), calm: r(LOAD, CALM_T), calmWas: r(OLOAD, CALM_T),
        line: [FX.pxBadRowsBlank(...g(CALM_T), rows(CALM_T)), FX.pxBadRowsBlank(...g(BAD_T), rows(BAD_T)),
          FX.pxBadRowsBlank(...g(CALM_T), rows(CALM_T).filter((x) => x.id !== 'lowVol'))] };""", BAD_T=BAD_T, CALM_T=CALM_T)
    assert got["bad"]["lowVol"] == "blank" and got["bad"]["trend"] == "blank"
    assert got["calm"]["lowVol"] == "blank" and got["calm"]["trend"] == got["calmWas"]["trend"] != "blank"   # 추세 점수는 맞아요 (그대로)
    assert got["line"] == [True, False, False]                                     # 52주까지 비운 종목은 머리의 줄이 말해요


# ── 목록 · 순위 · 규칙: 빠지고, 0 으로 세지 않아요 ──
def test_home_lists_leave_out_only_the_blanked_numbers():
    got = run("""
      const ids = (stocks, id) => (RK.critList(stocks, 'kr', id) || []).map((x) => x.s.t);
      out = {};
      for (const id of ['trend', 'lowVol']) out[id] = { now: ids(DATA.stocks, id), was: ids(ODATA.stocks, id) };
      out.cap = { now: RK.capList(DATA.stocks, 'kr').map((x) => x.s.t), was: RK.capList(ODATA.stocks, 'kr').map((x) => x.s.t) };""")
    trend, low = got["trend"], got["lowVol"]
    assert trend["now"] == [t for t in trend["was"] if t not in (BAD_T, MID_T)]   # 추세: 1년 수익률을 비운 두 종목만 빠져요
    assert CALM_T in trend["now"] or CALM_T not in trend["was"]
    assert low["now"] == [t for t in low["was"] if t not in MARKED]                 # 낮은 변동성: 셋 다 빠져요
    assert trend["was"][0] == BAD_T and CALM_T in low["was"][:10]
    assert got["cap"]["now"] == got["cap"]["was"]


def test_my_criteria_scores_and_plans_leave_them_out_never_as_zero():
    got = run("""
      const card = (id) => E.CARDS.find((c) => c.id === id);
      const base = { ...E.defaultSettings(), mix: 'kr', strict: 'loose' };
      const res = (stocks, points) => { const r = E.screen(stocks, { ...base, points }); return { blanks: r.blanks, in: r.markets.kr.survivors.map((x) => x.t) }; };
      const row = (st, cost) => ({ s: st, shares: 10, cost });
      const sam = LOAD.byT.get('005930');
      out = {
        raw: [BAD_T, CALM_T].map((t) => ['lowVol', 'trend', 'value'].map((id) => E.cardRaw(LOAD.byT.get(t), card(id)))),
        trend: res(DATA.stocks, { trend: 5 }), trendWas: res(ODATA.stocks, { trend: 5 }),
        lowVol: res(DATA.stocks, { lowVol: 5 }), lowVolWas: res(ODATA.stocks, { lowVol: 5 }),
        y2022: [BAD_T, CALM_T].map((t) => E.estimate2022([row(LOAD.byT.get(t), 1000000), row(sam, 3000000)]).missing),
        caut: [BAD_T, CALM_T].map((t) => E.cautions(LOAD.byT.get(t), LOAD.coByT.get(t), E.cautionContext(DATA.stocks)).ran.includes('vol')),
      };""", BAD_T=BAD_T, CALM_T=CALM_T)
    assert got["raw"][0][:2] == [None, None] and got["raw"][1][0] is None and isinstance(got["raw"][1][1], (int, float))
    assert got["lowVol"]["blanks"] == got["lowVolWas"]["blanks"] + 3 and got["trend"]["blanks"] == got["trendWas"]["blanks"] + 2
    assert BAD_T not in got["trend"]["in"] and BAD_T in got["trendWas"]["in"]
    assert all(abs(x - 0.25) < 1e-9 for x in got["y2022"])                       # 2022년 추정: 베타를 비운 종목은 '자료 없음'
    assert got["caut"] == [False, False]


# ── 예전 뱁새 ──
OLDVIEW = """
  const view = (corp, t) => renderToStaticMarkup(h(OLD.CompanyView, { data: corp, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
  const cmp = (corp, t) => renderToStaticMarkup(h(OLD.CompareView, { data: corp, baseT: t, onOpen() {}, onBack() {}, setExplain() {} }));
  const look = (v) => ({ n: count(v, LINE), k: count(v, ONE), beta: /연 변동성/.test(text(v)), w52: text(v).includes('52주 주가 위치'),
    decomp: text(v).includes('주가는 무엇으로 움직였나'), decompNums: text(v).includes('이익(EPS) 변화'), loss: text(v).includes('적자 구간이 있어서'),
    m3: /3개월\\s*[+−-]?\\d/.test(text(v)), mom: /모멘텀\\n/.test(text(v)), lowv: /저변동\\n/.test(text(v)) });
"""


def test_old_app_company_view_full_line_or_a_line_per_blanked_number():
    got = run(OLDVIEW + """
      out = { bad: look(view(CORP, BAD_T)), mid: look(view(CORP, MID_T)), calm: look(view(CORP, CALM_T)), was: look(view(OCORP, CALM_T)), sam: look(view(CORP, '005930')) };
      const x = view(CORP, CALM_T);
      out.at = [x.indexOf(ONE), x.indexOf('투자지표')];""", BAD_T=BAD_T, MID_T=MID_T, CALM_T=CALM_T)
    assert got["bad"] == {"n": 1, "k": 0, "beta": False, "w52": False, "decomp": False, "decompNums": False, "loss": False, "m3": False, "mom": False,
                          "lowv": False}, got["bad"]
    assert got["mid"]["n"] == 1 and got["mid"]["k"] == 0 and got["mid"]["m3"] and not got["mid"]["w52"]   # 3개월은 그대로 (64봉 밖)
    calm = got["calm"]                                                              # 52주 위치 · 3개월 · 모멘텀 그대로 · 베타 줄과 주가 분해 자리에 짧은 줄
    assert calm == {"n": 0, "k": 2, "beta": False, "w52": True, "decomp": True, "decompNums": False, "loss": False, "m3": True, "mom": True,
                    "lowv": False}, calm
    assert 0 < got["at"][0] < got["at"][1]
    assert got["was"]["beta"] and got["was"]["decompNums"] and got["was"]["lowv"] and got["was"]["n"] == got["was"]["k"] == 0
    assert got["sam"]["n"] == got["sam"]["k"] == 0 and got["sam"]["beta"] and got["sam"]["w52"]


def test_old_app_compare_table_says_it_once():
    got = run(OLDVIEW + """
      out = { bad: [count(cmp(CORP, BAD_T), LINE), count(cmp(CORP, BAD_T), ONE)], calm: [count(cmp(CORP, CALM_T), LINE), count(cmp(CORP, CALM_T), ONE)],
        sam: [count(cmp(CORP, '005930'), LINE), count(cmp(CORP, '005930'), ONE)] };""", BAD_T=BAD_T, CALM_T=CALM_T)
    assert got["bad"] == [1, 0] and got["calm"] == [0, 1] and got["sam"] == [0, 0]


def test_old_app_market_map_leaves_out_only_a_blanked_3_month_return():
    got = run("""
      const m = (corp) => text(renderToStaticMarkup(h(OLD.MarketView, { data: corp, heldMap: {}, onOpen() {}, setExplain() {} })));
      const tile = (t) => new RegExp(CORP.companies.find((c) => c.t === t).nk + ' · [^\\\\n]*\\\\n3개월 [+−-]?[0-9]');
      const now = m(CORP), was = m(OCORP);
      out = Object.fromEntries([BAD_T, MID_T, CALM_T].map((t) => [t, [tile(t).test(now), tile(t).test(was)]]));""",
        BAD_T=BAD_T, MID_T=MID_T, CALM_T=CALM_T)
    assert got[BAD_T] == [False, True]                                             # 3개월을 비운 종목만 지도에서 빠져요
    assert got[MID_T][0] == got[MID_T][1] and got[CALM_T][0] == got[CALM_T][1]     # 3개월이 맞는 종목은 그대로


def test_old_app_portfolio_list_never_fills_a_marked_stock_with_the_built_in_beta():
    """mergeStocks: 내장 목록에 있는 종목(삼성전자)이 표시되면 내장 베타 · 변동성으로 메우지 않아요 (위험 계산에서 빼요 · '–'). 표시와 비운 칸을 실어요."""
    got = run("""
      const base = [{ t: '005930', nk: '삼성전자', s: 'semi', price: 78000, beta: 1.15, vol: 32, per: 14, x: { lo: 52300, hi: 84500 } }];
      const L = (extra) => [{ t: '005930', nk: '삼성전자', cls: 'kr', price: 206000, cap: 1204.3, ...extra }];
      const a = D.mergeStocks(base, L({ pxBad: '2026-01-02', pxBadF: R.PX_BAD_ALL }))[0];
      const o = D.mergeStocks(base, L({ pxBad: '2024-01-02', pxBadF: ['vol', 'beta'], lo: 150000, hi: 260000 }))[0];
      const n = D.mergeStocks(base, L({ pxBad: '2026-01-02', price: null }))[0];
      const b = D.mergeStocks(base, L({}))[0];
      const c = D.mergeStocks([], [{ t: BAD_T, nk: 'x', cls: 'kr', price: 1000, pxBad: '2026-05-08', pxBadF: ['vol'] }])[0];
      out = { a: [a.beta, a.vol, a.x.lo, a.x.hi, a.pxBad, a.pxBadF.length, a.noRisk, a.live], o: [o.beta, o.x.lo, o.x.hi, o.pxBadF],
        n: [n.price, n.live], b: [b.beta, b.vol, b.x.lo, b.pxBad === undefined, b.live], c: [c.beta, c.vol, c.pxBad, c.pxBadF, c.noRisk] };""", BAD_T=BAD_T)
    assert got["a"] == [None, None, None, None, "2026-01-02", 16, True, True]
    assert got["o"] == [None, 150000, 260000, ["vol", "beta"]]                     # 52주는 오늘 값 그대로
    assert got["n"] == [78000, False]
    assert got["b"] == [1.15, 32, None, True, False]
    assert got["c"] == [None, None, "2026-05-08", ["vol"], True]
