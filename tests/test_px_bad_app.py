# -*- coding: utf-8 -*-
"""과거 주가 기록 오류 (Jack, 2026-11-14) — 앱 쪽: src/repair.js pxBad · src/v2/fix.js pxBadFor · src/v2/fixnote.jsx PxBadNote ·
src/copy/v2.js co.pxBad · 예전 뱁새 src/fixnote.jsx PxBadLine · src/data.js mergeStocks, 그리고 그 종목의 빈 숫자를 엔진 · 목록 · 규칙이
'빈 칸'으로 다루는지 (Node 로 직접).

- 파이프라인(fetch_data.py mark_px_bad)이 시계열로 만든 숫자를 비우고 data.json · corp.json 에 pxBad 를 달아요.
- 2.0 회사 페이지: 머리의 52주 막대 자리에 "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요." 한 번 (모든 탭),
  출렁임 칸은 이름 밑에 "–" (자료가 없어요 아님) · 가치 탭의 출렁임 카드와 실적 탭의 '주가는 무엇으로 움직였나' 없음. 다른 종목 · 미국 종목은 그대로.
- 홈 종목 순위의 추세 · 낮은 변동성 목록, 내 기준(저변동 · 추세 카드), 매수 계획의 2022년 · 출렁임 계산, 후보의 '변동성' 확인에서 빠져요 (0 이 아니에요).
- 예전 뱁새: 기업분석의 베타 줄 자리에 그 줄 한 번 (52주 위치 · 주가 분해 없음, '적자 구간이…' 같은 틀린 이유 없음) · 기업 비교 표 밑에 한 번 ·
  시장 지도(3개월 %)에서 빠짐 · 포트폴리오 목록은 내장 베타로 메우지 않아요.
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
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
BAD_T = "043260"                  # 시험 데이터의 성호전자: 1년 수익률이 가장 높아요 (추세 1위) — 망가진 기록이 만든 숫자라고 쳐요
CALM_T = "030000"                 # 제일기획: 변동성이 가장 낮은 축 (낮은 변동성 목록 위쪽)
MARKED = {BAD_T: "2026-05-08", CALM_T: "2024-01-19"}
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
    """2.0 시험 데이터 (tests/fixtures/v2) 에서 두 종목을 파이프라인처럼 비운 data.json · corp.json (validate_data.PX_BAD_DATA · PX_BAD_CORP)."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(FIX, "corp.json"), encoding="utf-8") as f:
        corp = json.load(f)
    for t, d in MARKED.items():
        s = next(x for x in data["stocks"] if x["t"] == t)
        assert s.get("mom") is not None and s.get("vol") is not None and s.get("lo") is not None
        for k in V.PX_BAD_DATA:
            s.pop(k, None)
        s["pxBad"] = d
        c = next(x for x in corp["companies"] if x["t"] == t)
        c.update({k: None for k in V.PX_BAD_CORP}, pxBad=d)
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
            f"const LINE = {json.dumps(LINE, ensure_ascii=False)};\n"
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
def test_the_mark_and_the_line():
    got = run("""
      const s = LOAD.byT.get(BAD_T), co = LOAD.coByT.get(BAD_T), sam = LOAD.byT.get('005930'), samCo = LOAD.coByT.get('005930');
      out = {
        mark: [R.pxBad(s), R.pxBad(co), R.pxBad({ pxBad: '' }), R.pxBad({ pxBad: true }), R.pxBad({ pxBad: 20260508 }), R.pxBad(null), R.pxBad(sam)],
        for: [FX.pxBadFor(s, co), FX.pxBadFor(s, null), FX.pxBadFor({ ...s, pxBad: undefined }, co), FX.pxBadFor(sam, samCo),
          FX.pxBadFor({ t: 'X', cls: 'us', pxBad: '2026-05-08' }, null), FX.pxBadFor(null, co)],
        text: [FN.pxBadText(s, co), FN.pxBadText(sam, samCo), FN.pxBadText({ t: 'X', cls: 'us', pxBad: '2026-05-08' }, null)],
        note: text(renderToStaticMarkup(h(FN.PxBadNote, { s, co }))).trim(), ui: has(renderToStaticMarkup(h(FN.PxBadNote, { s, co })), 'px-bad'),
        none: renderToStaticMarkup(h(FN.PxBadNote, { s: sam, co: samCo })),
        same: [C2.co.pxBad, OF.FIX_PX_BAD],
        old: text(renderToStaticMarkup(h(OF.PxBadLine, { c: co }))).trim(), oldEn: renderToStaticMarkup(h(OF.PxBadLine, { c: co, lang: 'en' })),
        oldNone: renderToStaticMarkup(h(OF.PxBadLine, { c: samCo })),
      };
      const keep = C2.co.pxBad; C2.co.pxBad = null;                             // 문구가 없으면 줄도 없어요 (빈 자리 없이)
      out.noWords = renderToStaticMarkup(h(FN.PxBadNote, { s, co })); C2.co.pxBad = keep;""", BAD_T=BAD_T)
    assert got["mark"] == [True, True, False, False, False, False, False]
    assert got["for"] == [True, True, True, False, False, False]                   # 두 파일 중 하나면 돼요 · 미국 종목은 아니에요
    assert got["text"] == [LINE, None, None]
    assert got["note"] == LINE and got["ui"] and got["none"] == "" and got["noWords"] == ""
    assert got["same"] == [LINE, LINE]
    assert got["old"] == LINE and got["oldEn"] == "" and got["oldNone"] == ""     # 영어 화면: 승인된 영어 글이 없어 줄 없이


def test_the_line_is_jacks_and_recorded_and_built():
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.pxBad` | {LINE} | Jack, 2026-11-14" in appr
    assert f"| Old app (`baepsae.html`, `src/fixnote.jsx`) price history, 2026-11-14 | {LINE} | Jack, 2026-11-14" in appr
    for f in ("app.html", "baepsae.html"):
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            assert fh.read().count(LINE) == 1, f                                   # 빌드한 두 페이지에 한 번씩 (글은 한 곳에 · 다시 빌드했어요)


# ── 2.0 회사 페이지 ──
COMPANY = """
  const page = (load, code, ctab = null) => renderToStaticMarkup(h(CO.Company, { load, store: STORE, setStoreData() {}, pad: 0, code, ctab,
    disc: { status: 'none' }, nav: { setTab() {}, more() {}, back() {}, onWhy() {} } }));
"""


def test_company_page_says_it_once_on_every_tab_in_the_52_week_bars_place():
    got = run(COMPANY + """
      const tabs = [null, 'earn', 'value', 'div'];
      const one = (load, code) => tabs.map((t) => { const x = page(load, code, t); return { n: count(x, LINE), range: has(x, 'co-range'), px: has(x, 'px-bad'),
        decomp: has(x, 'co-decomp'), risk: has(x, 'co-risk'), na: count(x, C2.co.tiles.na), lo: C2.co.lo ? count(x, C2.co.lo.split('{')[0]) : 0 }; });
      out = { bad: one(LOAD, BAD_T), calm: one(LOAD, CALM_T), was: one(OLOAD, BAD_T), sam: one(LOAD, '005930'), us: one(LOAD, 'AAPL') };
      const x = page(LOAD, BAD_T);
      out.order = [x.indexOf('data-ui-v2="co-price"'), x.indexOf('data-ui-v2="px-bad"'), x.indexOf('data-ui-v2="co-tabs"')];""",
        BAD_T=BAD_T, CALM_T=CALM_T)
    for k in ("bad", "calm"):
        assert [t["n"] for t in got[k]] == [1, 1, 1, 1], (k, got[k])                # 요약 · 실적 · 가치 · 배당 모두 한 번
        assert not any(t["range"] or t["decomp"] or t["risk"] or t["lo"] for t in got[k]), got[k]   # 52주 막대 · 주가 분해 · 출렁임 카드 없음
        assert all(t["px"] for t in got[k])
    assert got["order"][0] < got["order"][1] < got["order"][2]                     # 머리 (가격 밑, 탭 위)
    was = got["was"]                                                                # 비우기 전의 같은 종목: 52주 막대 · 주가 분해 · 출렁임 카드가 있었어요
    assert was[0]["range"] and was[1]["decomp"] and was[2]["risk"] and not any(t["n"] or t["px"] for t in was), was
    for k in ("sam", "us"):                                                         # 다른 종목: 그대로 (줄 없음 · 52주 막대)
        assert all(t["n"] == 0 and not t["px"] and t["range"] for t in got[k]), (k, got[k])
    assert got["sam"][2]["risk"]


def test_the_risk_tile_is_held_at_a_dash_never_no_data():
    got = run("""
      const view = (load, code) => CO.tileViews(load, load.byT.get(code)).map((v) => [v.topic, v.rule, v.phrase, v.number, v.basis, !!v.art]);
      out = { bad: view(LOAD, BAD_T), was: view(OLOAD, BAD_T), sam: view(LOAD, '005930'), order: CO.orderTiles(CO.tileViews(LOAD, LOAD.byT.get(BAD_T))).map((v) => v.topic) };""",
        BAD_T=BAD_T)
    risk = [v for v in got["bad"] if v[0] == "risk"]
    assert risk == [["risk", "pxbad", "–", None, None, False]], got["bad"]
    assert [v for v in got["bad"] if v[0] != "risk"] == [v for v in got["was"] if v[0] != "risk"]   # 실적 · 가치 · 배당 칸은 그대로
    was = [v for v in got["was"] if v[0] == "risk"][0]
    assert was[1] in ("big", "small", "similar") and was[5]                          # 비우기 전: 문장과 그림
    assert got["order"] == ["earn", "value", "div", "risk"]
    assert [v[1] for v in got["sam"] if v[0] == "risk"][0] != "pxbad"


def test_fit_rows_for_low_volatility_and_trend_are_blank():
    got = run("""
      const r = (load, code) => Object.fromEntries(K.cardRanks(load.byT.get(code), load.data.stocks, 'market').rows.map((x) => [x.id, x.blank ? 'blank' : x.side || 'na']));
      out = { bad: r(LOAD, BAD_T), was: r(OLOAD, BAD_T), text: K.cardRanks(LOAD.byT.get(BAD_T), DATA.stocks, 'market').rows.filter((x) => ['lowVol', 'trend'].includes(x.id)).map(CO.rankText) };""",
        BAD_T=BAD_T)
    assert got["bad"]["lowVol"] == "blank" and got["bad"]["trend"] == "blank"
    assert got["was"]["trend"] == "top" and got["was"]["lowVol"] != "blank"
    assert {k: v for k, v in got["bad"].items() if k not in ("lowVol", "trend")} == {k: v for k, v in got["was"].items() if k not in ("lowVol", "trend")}
    assert got["text"] == ["–", "–"]


# ── 목록 · 순위 · 규칙: 빠지고, 0 으로 세지 않아요 ──
def test_home_lists_leave_the_marked_stocks_out_and_rank_the_rest():
    got = run("""
      const ids = (stocks, id) => (RK.critList(stocks, 'kr', id) || []).map((x) => x.s.t);
      out = {};
      for (const id of ['trend', 'lowVol']) out[id] = { now: ids(DATA.stocks, id), was: ids(ODATA.stocks, id) };
      out.cap = { now: RK.capList(DATA.stocks, 'kr').map((x) => x.s.t), was: RK.capList(ODATA.stocks, 'kr').map((x) => x.s.t) };
      out.val = { now: RK.valList(DATA.stocks, 'kr').map((x) => x.s.t), was: RK.valList(ODATA.stocks, 'kr').map((x) => x.s.t) };
      out.state = [RK.critState(DATA.stocks, 'kr', 'trend'), RK.critState(DATA.stocks, 'kr', 'lowVol')];""")
    for id_ in ("trend", "lowVol"):
        now, was = got[id_]["now"], got[id_]["was"]
        assert not set(MARKED) & set(now), (id_, now[:5])
        assert now == [t for t in was if t not in MARKED], id_                        # 나머지 순서는 그대로
    assert got["trend"]["was"][0] == BAD_T and CALM_T in got["lowVol"]["was"][:10]  # 비우기 전에는 맨 위쪽에 있었어요
    assert got["cap"]["now"] == got["cap"]["was"] and got["val"]["now"] == got["val"]["was"]   # 시가총액 · 거래대금 목록은 그대로
    assert got["state"] == ["rows", "rows"]


def test_my_criteria_scores_and_plans_leave_them_out_never_as_zero():
    got = run("""
      const card = (id) => E.CARDS.find((c) => c.id === id);
      const base = { ...E.defaultSettings(), mix: 'kr', strict: 'loose' };
      const res = (stocks, points) => { const r = E.screen(stocks, { ...base, points }); return { blanks: r.blanks, in: r.markets.kr.survivors.map((x) => x.t) }; };
      const s = LOAD.byT.get(BAD_T);
      const row = (st, cost) => ({ s: st, shares: 10, cost });
      const sam = LOAD.byT.get('005930');
      out = {
        raw: ['lowVol', 'trend', 'value', 'large'].map((id) => E.cardRaw(s, card(id))),
        pct: ['lowVol', 'trend'].map((id) => E.percentileScores(E.universe(DATA.stocks, 'kr'), card(id)).has(BAD_T)),
        trend: res(DATA.stocks, { trend: 5 }), trendWas: res(ODATA.stocks, { trend: 5 }),
        lowVol: res(DATA.stocks, { lowVol: 5 }), lowVolWas: res(ODATA.stocks, { lowVol: 5 }),
        y2022: E.estimate2022([row(s, 1000000), row(sam, 3000000)]),
        vol: E.deckVol([row(s, 1000000), row(sam, 3000000)], DATA.settings, 4000000),
        caut: E.cautions(s, LOAD.coByT.get(BAD_T), E.cautionContext(DATA.stocks)).ran,
        cautWas: E.cautions(OLOAD.byT.get(BAD_T), OLOAD.coByT.get(BAD_T), E.cautionContext(ODATA.stocks)).ran,
      };""", BAD_T=BAD_T)
    assert got["raw"][:2] == [None, None] and all(isinstance(x, (int, float)) for x in got["raw"][2:])   # 빈 칸 (NA 도 0 도 아니에요)
    assert got["pct"] == [False, False]
    for k in ("trend", "lowVol"):
        assert BAD_T not in got[k]["in"] and got[k]["blanks"] == got[k + "Was"]["blanks"] + len(MARKED), (k, got[k]["blanks"], got[k + "Was"]["blanks"])
    assert BAD_T in got["trendWas"]["in"]
    assert got["y2022"]["ok"] and abs(got["y2022"]["missing"] - 0.25) < 1e-9        # 2022년 추정: 그 종목은 '자료 없음' (나머지처럼 움직인다고)
    assert got["vol"] and abs(got["vol"]["missing"] - 0.25) < 1e-9
    assert "vol" not in got["caut"] and "vol" in got["cautWas"]                     # 후보의 '변동성' 확인은 돌지 않았다고 해요 (확인했다고 하지 않아요)


# ── 예전 뱁새 ──
OLDVIEW = """
  const view = (corp, t) => renderToStaticMarkup(h(OLD.CompanyView, { data: corp, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
  const cmp = (corp, t) => renderToStaticMarkup(h(OLD.CompareView, { data: corp, baseT: t, onOpen() {}, onBack() {}, setExplain() {} }));
"""


def test_old_app_company_view_says_it_once_where_the_beta_line_was():
    got = run(OLDVIEW + """
      const x = view(CORP, BAD_T), was = view(OCORP, BAD_T), sam = view(CORP, '005930');
      const look = (v) => ({ n: count(v, LINE), beta: /연 변동성/.test(text(v)), w52: text(v).includes('52주 주가 위치'), decomp: text(v).includes('주가는 무엇으로 움직였나'),
        loss: text(v).includes('적자 구간이 있어서'), m3: /3개월\\s*[+−-]?\\d/.test(text(v)), mom: /모멘텀\\n/.test(text(v)), lowv: /저변동\\n/.test(text(v)) });
      out = { bad: look(x), was: look(was), sam: look(sam), at: [x.indexOf(LINE), x.indexOf('투자지표')] };""", BAD_T=BAD_T)
    assert got["bad"] == {"n": 1, "beta": False, "w52": False, "decomp": False, "loss": False, "m3": False, "mom": False, "lowv": False}, got["bad"]
    assert 0 < got["at"][0] < got["at"][1]                                          # 머리 카드 (회사 이름 밑, 투자지표 위)
    assert got["was"]["beta"] and got["was"]["w52"] and got["was"]["decomp"] and got["was"]["n"] == 0
    assert got["was"]["m3"] and got["was"]["mom"] and got["was"]["lowv"]           # 비우기 전: 3개월 % · 모멘텀 · 저변동 점수가 있었어요
    assert got["sam"]["n"] == 0 and got["sam"]["beta"] and got["sam"]["w52"]


def test_old_app_compare_table_says_it_once_and_its_beta_reads_a_dash():
    got = run(OLDVIEW + """
      const x = cmp(CORP, BAD_T), sam = cmp(CORP, '005930');
      out = { n: count(x, LINE), sam: count(sam, LINE) };""", BAD_T=BAD_T)
    assert got["n"] == 1 and got["sam"] == 0


def test_old_app_market_map_leaves_them_out():
    got = run("""
      const m = (corp) => text(renderToStaticMarkup(h(OLD.MarketView, { data: corp, heldMap: {}, onOpen() {}, setExplain() {} })));
      const name = CORP.companies.find((c) => c.t === BAD_T).nk;
      const tile = new RegExp(name + ' · [^\\n]*\\n3개월 [+−-]?[0-9]');      // 지도 칸의 이름표: '{이름} · {업종}' 다음 줄 '3개월 +x%'
      out = { now: tile.test(m(CORP)), was: tile.test(m(OCORP)) };""", BAD_T=BAD_T)
    assert got["was"] is True and got["now"] is False                               # 3개월 % 칸(지도)에서 빠져요


def test_old_app_portfolio_list_never_fills_a_marked_stock_with_the_built_in_beta():
    """mergeStocks: 내장 목록에 있는 종목(삼성전자)이 표시되면 내장 베타 · 변동성으로 메우지 않아요 (위험 계산에서 빼요 · '–'). 표시는 그대로 실어요."""
    got = run("""
      const base = [{ t: '005930', nk: '삼성전자', s: 'semi', price: 78000, beta: 1.15, vol: 32, per: 14, x: { lo: 52300, hi: 84500 } }];
      const L = (extra) => [{ t: '005930', nk: '삼성전자', cls: 'kr', price: 206000, cap: 1204.3, ...extra }];
      const a = D.mergeStocks(base, L({ pxBad: '2026-01-02' }))[0];
      const b = D.mergeStocks(base, L({}))[0];
      const c = D.mergeStocks([], [{ t: BAD_T, nk: 'x', cls: 'kr', price: 1000, pxBad: '2026-05-08' }])[0];
      const n = D.mergeStocks(base, L({ pxBad: '2026-01-02', price: null }))[0];
      out = { a: [a.beta, a.vol, a.x.lo, a.x.hi, a.pxBad, a.noRisk, a.live], n: [n.price, n.live], b: [b.beta, b.vol, b.x.lo, b.pxBad === undefined, b.live],
        c: [c.beta, c.vol, c.pxBad, c.noRisk] };""", BAD_T=BAD_T)
    assert got["a"] == [None, None, None, None, "2026-01-02", True, True]       # 가격은 오늘 것: '예시 가격' 안내에 들지 않아요
    assert got["n"] == [78000, False]                                             # 가격이 없으면 예전처럼 내장 가격 · '실시간 아님'
    assert got["b"] == [1.15, 32, None, True, False]                                 # 표시 없음: 예전처럼 (내장 값 · '실시간 아님')
    assert got["c"] == [None, None, "2026-05-08", True]
