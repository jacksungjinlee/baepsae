# -*- coding: utf-8 -*-
"""공시 단위 확인 (Jack, 2026-11-13) — 앱 쪽: src/repair.js unitHeld · src/v2/fix.js unitHeldFor · src/v2/fixnote.jsx UnitChkNote ·
src/copy/v2.js co.unitChk · 예전 뱁새 src/fixnote.jsx UnitChkLine, 그리고 그 회사의 빈 숫자를 엔진 · 규칙이 '빈 칸'으로 다루는지 (Node 로 직접).

- 파이프라인(fetch_data.py unit_guard)이 단위가 틀린 재무제표로 만든 숫자를 비우고 data.json · corp.json 에 unitChk 를 달아요.
- 2.0: 그 숫자가 있을 영역마다 "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요." 한 번 (다른 회사 · 미국 종목에는 없음),
  '고치는 중' · '전체 순이익' · 이자보상배율 줄은 없어요.
- 엔진: 가치 · 수익성 · 안정성 · 성장 카드에서 빈 칸 (해당 없음도 0 도 아니에요) → 그 카드에 점수가 있으면 순위에서 빠지고 '자료가 없어
  빠진 종목'으로 세요. 내 기준 점검의 부채비율 · ROE 규칙은 '확인 필요'(missing) — 지켰다고도 어겼다고도 하지 않아요.
- 예전 뱁새: 숫자 칸이 비어도 오류 없이 그려지고, 기업분석 투자지표 · 첫 화면 성적표(한국어)에 그 줄 한 번 · 맞지 않는 이유 문장은 없어요.
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
MODS = {"R": "src/repair.js", "FX": "src/v2/fix.js", "FN": "src/v2/fixnote.jsx", "E": "src/v2/engine.js", "K": "src/v2/company.js",
        "CO": "src/v2/company.jsx", "CT": "src/v2/cotabs.jsx", "CP": "src/copy/v2.js", "RU": "src/v2/rules.js", "OF": "src/fixnote.jsx",
        "OLD": "src/corp.jsx", "SH": "src/shell.jsx", "DT": "src/detail.jsx"}
LINE = "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요."
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
UNIT_T = "028260"                 # 시험 데이터의 삼성물산 (배당을 줘요) — tests/smoke_v2.py 의 장면과 같은 회사
DATA_BLANK = ("per", "pbr", "eps", "bps", "roe", "debt", "opm", "g3", "vz", "qz")
CORP_POP = ("evE", "evR", "pcf", "bq", "nio3", "nio3Hyb", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "fl", "flSrc", "flWhy")
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
    """2.0 시험 데이터 (tests/fixtures/v2) 에서 삼성물산을 파이프라인처럼 비운 data.json · corp.json."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(FIX, "corp.json"), encoding="utf-8") as f:
        corp = json.load(f)
    s = next(x for x in data["stocks"] if x["t"] == UNIT_T)
    for k in DATA_BLANK:
        s.pop(k, None)
    s["unitChk"] = ["scale"]
    c = next(x for x in corp["companies"] if x["t"] == UNIT_T)
    c.update(rev=[None] * 3, op=[None] * 3, ni=[None] * 3, eq=None, dcfReady=False, unitChk=["scale"], flRan=[], **{k: None for k in DATA_BLANK})
    for k in CORP_POP:
        c.pop(k, None)
    return data, corp


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { R, FX, FN, E, K, CO, CT, CP, RU, OF, OLD, SH, DT } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m));\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(_B['data'])}, 'utf8')); const CORP = JSON.parse(fs.readFileSync({json.dumps(_B['corp'])}, 'utf8'));\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const STORE = { data: { decks: [], notes: {}, assume: {} }, writable: false };\n"
            f"const LINE = {json.dumps(LINE, ensure_ascii=False)};\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=90)
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


# ── 순수 함수 ──
def test_unit_held_and_the_lines_it_switches_off():
    got = run("""
      const co = LOAD.coByT.get(UNIT_T), s = LOAD.byT.get(UNIT_T), sam = LOAD.byT.get('005930'), samCo = LOAD.coByT.get('005930');
      const live = { epsBasis: 'owners', companies: CORP.companies };
      out = {
        held: [R.unitHeld(co), R.unitHeld(s), R.unitHeld({ unitChk: [] }), R.unitHeld({ unitChk: 'scale' }), R.unitHeld(null), R.unitHeld(samCo)],
        for: [FX.unitHeldFor(s, co), FX.unitHeldFor(s, null), FX.unitHeldFor({ ...s, unitChk: undefined }, co), FX.unitHeldFor(sam, samCo),
          FX.unitHeldFor({ t: 'X', cls: 'us', unitChk: ['scale'] }, null)],
        fixNeeded: [R.epsFixNeeded(CORP, co), R.epsFixNeeded(CORP, samCo), R.epsFixNeeded(live, { ...co, epsIn: { b: 't', how: 'total', nci: true } }),
          R.epsTotalNeeded(live, { ...co, epsIn: { b: 't', how: 'total', nci: true } }), R.icrOff({ ...co, flWhy: { icr: 'off' } })],
      };
      FX.setEpsBasis(CORP);                                                      // 시험 데이터: 다시 읽기 전 (epsBasis 없음)
      out.epsFixFor = [FX.epsFixFor(s), FX.epsFixFor(sam), FX.epsFixFor({ ...s })];
      out.rows = [FX.unitRowsBlank(s, co, [{ id: 'value', blank: true }]), FX.unitRowsBlank(s, co, [{ id: 'div', blank: true }, { id: 'lowVol', side: 'top', pct: 3 }]),
        FX.unitRowsBlank(sam, samCo, [{ id: 'value', blank: true }]), FX.unitRowsBlank(s, co, [{ id: 'stable', na: true }])];
      out.text = [FN.unitChkText(s, co), FN.unitChkText(sam, samCo), FN.unitChkText({ t: 'X', cls: 'us', unitChk: ['scale'] }, null)];""",
        UNIT_T=UNIT_T)
    assert got["held"] == [True, True, False, False, False, False]
    assert got["for"] == [True, True, True, False, False]                       # 두 파일 중 하나면 돼요 · 미국 종목은 아니에요
    assert got["fixNeeded"] == [False, True, False, False, False]               # 고치는 중 · 전체 순이익 · 이자보상배율 줄 없음
    assert got["epsFixFor"] == [False, True, False]
    assert got["rows"] == [True, False, False, False]
    assert got["text"] == [LINE, None, None]


def test_the_note_renders_once_and_only_for_the_held_company():
    got = run("""
      const co = LOAD.coByT.get(UNIT_T), s = LOAD.byT.get(UNIT_T);
      const a = renderToStaticMarkup(h(FN.UnitChkNote, { s, co }));
      out = { a: text(a).trim(), ui: /data-ui-v2="unit-chk"/.test(a), off: renderToStaticMarkup(h(FN.UnitChkNote, { s, co, show: false })),
        sam: renderToStaticMarkup(h(FN.UnitChkNote, { s: LOAD.byT.get('005930'), co: LOAD.coByT.get('005930') })) };
      const keep = C2.co.unitChk; C2.co.unitChk = null;                         // 문구가 없으면 줄도 없어요 (빈 자리 없이)
      out.noWords = renderToStaticMarkup(h(FN.UnitChkNote, { s, co })); C2.co.unitChk = keep;""", UNIT_T=UNIT_T)
    assert got["a"] == LINE and got["ui"]
    assert got["off"] == "" and got["sam"] == "" and got["noWords"] == ""


# ── 회사 페이지의 탭과 자세히: 영역마다 한 번 ──
def test_each_tab_says_it_once_and_drops_the_parts_with_no_numbers():
    got = run("""
      FX.setEpsBasis(CORP);
      const tab = (T, code, extra = {}) => renderToStaticMarkup(h(T, { load: LOAD, s: LOAD.byT.get(code), store: STORE, setStoreData() {}, onMore() {},
        pad: 0, onBack() {}, backLabel: '', ...extra }));
      const html = { earn: tab(CT.EarnTab, UNIT_T), value: tab(CT.ValueTab, UNIT_T), div: tab(CT.DivTab, UNIT_T), vmore: tab(CT.ValueMore, UNIT_T),
        emore: tab(CT.EarnMore, UNIT_T) };
      const sam = { earn: tab(CT.EarnTab, '005930'), value: tab(CT.ValueTab, '005930'), div: tab(CT.DivTab, '005930'), vmore: tab(CT.ValueMore, '005930') };
      const has = (x, id) => new RegExp('data-ui-v2="' + id + '"').test(x);
      out = {
        n: Object.fromEntries(Object.entries(html).map(([k, x]) => [k, count(x, LINE)])),
        sam: Object.fromEntries(Object.entries(sam).map(([k, x]) => [k, count(x, LINE)])),
        earn: ['co-earn-big', 'co-decomp', 'co-earn-more', 'co-growth'].filter((id) => has(html.earn, id)),
        value: ['co-pbr', 'co-per', 'co-compare', 'co-dcf', 'co-value-basis', 'co-value-more', 'date-line'].filter((id) => has(html.value, id)),
        risk: has(html.value, 'co-risk'),
        div: ['co-payout', 'co-dps', 'co-million'].filter((id) => has(html.div, id)),
        vmore: ['co-ratios', 'co-map', 'co-calc'].filter((id) => has(html.vmore, id)),
        emoreTable: /role="table"/.test(html.emore),
        fixLine: Object.values(html).some((x) => /data-ui-v2="eps-fix"/.test(x)),
        samValue: ['co-pbr', 'co-per'].filter((id) => has(sam.value, id)),
        na: Object.values(html).some((x) => text(x).includes(C2.co.tiles.na)),
      };""", UNIT_T=UNIT_T)
    assert got["n"] == {"earn": 1, "value": 1, "div": 1, "vmore": 1, "emore": 1}, got["n"]
    assert got["sam"] == {"earn": 0, "value": 0, "div": 0, "vmore": 0}, got["sam"]
    assert got["earn"] == [] and got["value"] == [] and got["vmore"] == [] and not got["emoreTable"]
    assert got["risk"]                                                          # 출렁임(베타)은 그대로
    assert "co-payout" not in got["div"] and got["div"], got["div"]             # 배당은 그대로 · 배당성향은 그 줄로
    assert not got["fixLine"] and not got["na"]                                 # '고치는 중' · '자료가 없어요' 없음
    assert got["samValue"]                                                      # 다른 회사는 숫자 그대로


def test_summary_tiles_leave_out_earnings_and_value_and_the_fit_rows_are_blank():
    got = run("""
      const s = LOAD.byT.get(UNIT_T), co = LOAD.coByT.get(UNIT_T);
      const ranks = K.cardRanks(s, DATA.stocks, 'market').rows;
      out = {
        tiles: CO.tileViews(LOAD, s).map((v) => [v.topic, v.rule]),
        ranks: ranks.filter((r) => ['value', 'profit', 'stable', 'growth', 'div', 'lowVol'].includes(r.id)).map((r) => [r.id, !!r.blank]),
        text: ranks.filter((r) => ['value', 'profit', 'stable', 'growth'].includes(r.id)).map(CO.rankText),
        warn: K.warnings(s, co),
        fitLine: FX.unitRowsBlank(s, co, ranks),
      };""", UNIT_T=UNIT_T)
    t = dict(got["tiles"])
    assert t["earn"] == "na" and t["value"] == "na"                             # 그 칸은 화면에서 빼요 (company.jsx Tiles · smoke_v2 가 봐요)
    assert t["div"] != "na" and t["risk"] != "na"
    assert dict(got["ranks"]) == {"value": True, "profit": True, "stable": True, "growth": True, "div": False, "lowVol": False}
    assert got["text"] == ["–"] * 4 and got["fitLine"]
    assert got["warn"]["flags"] == [] and not got["warn"]["allRan"]            # '경고 없음'이라고 말할 수 없어요 (그 자리에 그 줄)


# ── 엔진 · 규칙: 빈 칸은 빈 칸 ──
def test_engine_leaves_the_company_out_only_where_it_is_blank_and_never_scores_it_as_zero():
    got = run("""
      const card = (id) => E.CARDS.find((c) => c.id === id);
      const s = LOAD.byT.get(UNIT_T);
      const base = { ...E.defaultSettings(), mix: 'kr', strict: 'loose' };
      const res = (points) => { const r = E.screen(DATA.stocks, { ...base, points }); return { blanks: r.blanks, in: r.markets.kr.survivors.some((x) => x.t === UNIT_T) }; };
      out = {
        raw: ['value', 'profit', 'stable', 'growth', 'lowVol', 'large'].map((id) => E.cardRaw(s, card(id))),
        pct: ['value', 'profit', 'stable', 'growth'].map((id) => E.percentileScores(E.universe(DATA.stocks, 'kr'), card(id)).has(UNIT_T)),
        value: res({ value: 5 }), profit: res({ profit: 5 }), stable: res({ stable: 5 }), growth: res({ growth: 5 }),
        lowVol: res({ lowVol: 5 }), large: res({ large: 5 }), base: E.screen(DATA.stocks, { ...base, points: { lowVol: 5 } }).blanks,
        excl: E.exclusionsHit(s),
      };""", UNIT_T=UNIT_T)
    assert got["raw"][:4] == [None] * 4 and all(isinstance(x, (int, float)) for x in got["raw"][4:])   # 빈 칸 (NA 도 0 도 아니에요)
    assert got["pct"] == [False] * 4                                                                    # 순위에 없어요
    for k in ("value", "profit", "stable", "growth"):
        assert got[k]["in"] is False and got[k]["blanks"] >= 1, (k, got[k])
    assert got["lowVol"]["in"] is True or got["lowVol"]["blanks"] == got["base"]                       # 다른 카드만 쓰면 그대로
    assert got["large"]["in"] is True or got["large"]["blanks"] == got["base"]
    assert "debt" not in got["excl"] and "loss" not in got["excl"]                                       # 빈 부채비율 · 영업이익률로 빼지 않아요


def test_daily_rules_on_the_blanked_numbers_say_missing_never_kept_or_broken():
    got = run("""
      const s = LOAD.byT.get(UNIT_T), co = LOAD.coByT.get(UNIT_T);
      const h0 = { t: UNIT_T, cls: 'kr' };
      const rules = [
        { id: 'debtCeiling', kind: 'keep', check: 'checked', input: 'debt', since: 2024, limit: 100 },
        { id: 'roeFloor', kind: 'keep', check: 'checked', input: 'roe', since: 2024, floor: 3 },
        { id: 'opDecline', kind: 'keep', check: 'checked', input: 'op', since: 2024 },
      ];
      out = rules.map((r) => { const x = RU.evalRule(r, h0, s, co, null, null); return [r.id, x && x.result]; });""", UNIT_T=UNIT_T)
    assert got == [["debtCeiling", "missing"], ["roeFloor", "missing"], ["opDecline", "missing"]]


# ── 예전 뱁새 ──
def test_old_app_renders_the_blank_company_without_errors_and_says_why_once():
    got = run("""
      const c = CORP.companies.find((x) => x.t === UNIT_T);
      const view = renderToStaticMarkup(h(OLD.CompanyView, { data: CORP, t: UNIT_T, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const card = (lang) => text(renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } })));
      const sam = renderToStaticMarkup(h(OLD.CompanyView, { data: CORP, t: '005930', heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      out = { n: count(view, LINE), wrong: ['적자이거나 데이터가 없어요', '데이터가 없어요', '현금흐름 데이터가 없어요', '차입금·상각비 데이터 부족'].filter((x) => text(view).includes(x)),
        fix: /data-fix="eps"/.test(view), ko: card('ko'), en: card('en'), sam: count(sam, LINE),
        state: [...OF.corpFixState(CORP).notWon].includes(UNIT_T), need: OF.epsFixNeedLoaded(OF.corpFixState(CORP), [UNIT_T]),
        same: OF.FIX_UNIT === C2.co.unitChk };""", UNIT_T=UNIT_T)
    assert got["n"] == 1 and got["wrong"] == [] and not got["fix"]
    assert got["ko"].count(LINE) == 1 and "적자이거나 재무 데이터가 아직 없어요" not in got["ko"]
    assert LINE not in got["en"] and "Loss-making or no financial data yet." not in got["en"]   # 영어: 승인된 글이 없어 줄 없이 · 틀린 문장도 없이
    assert got["sam"] == 0
    assert got["state"] and got["need"] is False                                                     # 포트폴리오의 '고치는 중' 줄도 없어요
    assert got["same"]


def test_old_app_peer_check_shows_a_dash_for_a_blank_roe_or_debt_never_a_level():
    """포트폴리오 스튜디오의 '같은 업종과 비교' (detail.jsx MiniCheck): 빈 ROE · 부채비율을 0 으로 읽지 않아요 (부채비율 745% 회사가 '좋은 편'이
    되지 않게). 숫자가 있으면 예전과 같아요."""
    got = run("""
      const peers = [10, 12, 14, 16].map((r, i) => ({ t: 'P' + i, per: 10 + i, x: { roe: r, debt: 80 + 10 * i } }));
      const chips = (s) => text(renderToStaticMarkup(h(DT.MiniCheck, { s, peers, lang: 'ko', t: (k) => k }))).split('\\n').map((x) => x.trim()).filter(Boolean);
      out = { blank: chips({ t: UNIT_T, s: 'retail', per: null, x: { roe: null, debt: null } }),
        full: chips({ t: 'Q', s: 'retail', per: 9, x: { roe: 20, debt: 50 } }) };""", UNIT_T=UNIT_T)
    assert got["blank"] == ["chkTitle", "chkProfit", "—", "chkSafety", "—", "chkValue", "—", "chkNote"], got["blank"]
    assert got["full"] == ["chkTitle", "chkProfit", "좋은 편", "chkSafety", "좋은 편", "chkValue", "낮은 편", "chkNote"], got["full"]


# ── 문구 ──
def test_copy_line_is_jacks_and_recorded_as_approved():
    got = run("out = { line: C2.co.unitChk };")
    assert got["line"] == LINE
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.unitChk` | {LINE} | Jack, 2026-11-13" in appr
    assert f"| Old app (`baepsae.html`, `src/fixnote.jsx`) unit check, 2026-11-13 | {LINE} |" in appr
    for f in ("app.html", "baepsae.html"):
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            assert LINE in fh.read(), f                                   # 빌드한 두 페이지에 들어 있어요 (빌드를 다시 했어요)
