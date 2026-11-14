# -*- coding: utf-8 -*-
"""재무 경고: 확인이 일부만 돌았거나 하나도 못 돌았을 때 (Jack, 2026-11-14: "when one check has no data, show the warnings that were
checked and count the unchecked ones, using the closest approved line until the design chat sends wording").

- warn.js warnings(): 돌지 않은 확인의 목록(unchecked) · 하나도 돌지 않음(noneRan, corp.json flRan []) · 이자보상배율만 이자 줄이 없어
  못 돌림(icrIe, 경고가 있어도).
- 2.0 회사 페이지 요약: 하나도 돌지 않은 한국 회사(재무제표가 아직 없는 회사 · 우선주 · 원화가 아닌 재무제표)는 카드가 사라지지 않고
  "재무 경고 · 확인하지 못했어요" (승인된 두 말: rank.warn · pfr.unknown). '…없어요'라고 하지 않아요. 펀드 · flRan 이 없는 예전 파일은 그대로.
- 걸린 경고가 있고 이자보상배율만 이자 줄이 없어 못 돌았으면, 목록이 네 가지를 다 본 것처럼 읽히지 않게 승인된 PR #68 줄을 그 밑에.
- 걸린 경고는 어느 경우에도 숨지 않아요 · 가진 종목 '재무 경고 0개' 칸은 돌아간 확인에서 걸린 경고를 세고, 덜 돌아간 회사가 있으면 ✓ 가 아니에요.
회사 기록은 2026-11-14 발행(11월 13일 종가)의 실제 값이에요. 화면은 react-dom/server 로 실제 컴포넌트를 그려서 봐요. 브라우저
화면(390 · 1280)은 tests/smoke_v2.py 장면 '재무 경고 일부'가 봐요.
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
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
MODS = {"L": "src/v2/load.js", "CO": "src/v2/company.jsx", "W": "src/v2/warn.js", "P": "src/v2/pf.js", "PV": "src/v2/pfview.jsx",
        "CP": "src/copy/v2.js"}

# 2026-11-14 발행의 재무 경고 칸 그대로 (corp.json companies[]: fl · flRan · flNa · flWhy · flSrc · stmtCur · bq · fy)
REAL = {
    "000270": {"flRan": ["cr", "icr", "l3"], "flSrc": {"icr": "cf"}, "bq": "2026.2Q", "fy": 2025},                    # 기아: 자본잠식 못 돌림
    "066970": {"fl": {"cr": 75.0, "l3": 1}, "flRan": ["cr", "icr", "l3"], "flSrc": {"icr": "cf"}, "bq": "2026.2Q", "fy": 2025},   # 엘앤에프
    "228760": {"fl": {"l3": 1}, "flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "ie"}, "bq": "2026.2Q", "fy": 2025},   # 지노믹트리
    "0126Z0": {"fl": {"icr": -38.2}, "flRan": ["cr", "icr", "imp"], "flSrc": {"icr": "cf"}, "fy": 2025},               # 삼성에피스홀딩스
    "0011T0": {"flRan": [], "flWhy": {"icr": "op"}, "fy": None},                                                     # 채비: 재무제표 없음
    "005935": {"flRan": [], "flWhy": {"icr": "op"}, "fy": None},                                                     # 삼성전자우
    "241560": {"flRan": [], "fy": 2025, "stmtCur": "USD"},                                                           # 두산밥캣: 달러 재무제표
    "088980": {"flRan": [], "flNa": ["cr", "icr"], "fy": None},                                                      # 맥쿼리인프라 (펀드)
    "005930": {"flRan": ["cr", "icr", "l3", "imp"], "flSrc": {"icr": "cf"}, "bq": "2026.2Q", "fy": 2025},             # 삼성전자: 다 돌았어요
}
WARN_KEYS = ("fl", "flRan", "flNa", "flWhy", "flSrc", "stmtCur", "unitChk", "bq", "fy")
HEAD, UNKNOWN = "재무 경고", "확인하지 못했어요"
NO_ICR = "이자보상배율은 재무제표에서 이자 비용을 찾지 못해 확인하지 못했어요. 유동비율, 3년 연속 순손실, 자본잠식은 최근 공시로 확인했어요."
NONE, NONE_PARTIAL = "재무 경고 신호는 없어요", "확인한 재무 경고 신호는 없어요"
_TMP = {}


def bundle_dir():
    """필요한 모듈을 한 파일로 한 번만 묶어요. React 는 밖에 둬요 (node_modules 의 것)."""
    if "p" not in _TMP:
        tmp = tempfile.mkdtemp(prefix="baepsae-finwarn-")
        with open(os.path.join(tmp, "entry.js"), "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, os.path.join(tmp, "entry.js"), "--bundle", "--format=esm", "--platform=node", "--jsx=automatic",
                            "--loader:.js=jsx", "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs",
                            "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _TMP["p"] = tmp
    return _TMP["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _TMP:
        shutil.rmtree(_TMP["p"], ignore_errors=True)


def fixture_files():
    """시험 데이터(tests/fixtures/v2)에 위 회사들의 실제 재무 경고 칸을 넣어요. 두산밥캣은 파이프라인이 하는 대로 금액을 비워요."""
    files = {}
    for name in ("data.json", "corp.json", "macro.json"):
        with open(os.path.join(FIX, name), encoding="utf-8") as f:
            files[name] = json.load(f)
    coby = {c["t"]: c for c in files["corp.json"]["companies"]}
    for t, rec in REAL.items():
        co = coby[t]
        for k in WARN_KEYS:
            co.pop(k, None)
        co.update(rec)
    co = coby["241560"]
    co.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False, per=None, pbr=None, eps=None, bps=None)
    for k in ("evE", "evR", "pcf", "cash3", "eps3r", "epsNi3", "epsB", "nio3", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep"):
        co.pop(k, None)
    s = next(x for x in files["data.json"]["stocks"] if x["t"] == "241560")
    s.update(per=None, pbr=None, eps=None, bps=None, vz=None)
    next(x for x in files["data.json"]["stocks"] if x["t"] == "088980")["etf"] = True     # 2026-11-14 발행처럼: 인프라 펀드 (etf)
    return files


def run(body, **data):
    tmp = bundle_dir()
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { L, CO, W, P, PV, CP } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const ms = Date.parse('2026-10-30T18:00:00+09:00'); Date.now = () => ms;\n"
            "const mkLoad = (files) => { for (const f of ['data.json', 'corp.json', 'macro.json']) files[f].publishedAt = new Date(ms - 3600000).toISOString();\n"
            "  return L.resolveLoad({ data: { ok: true, data: files['data.json'] }, corp: { ok: true, data: files['corp.json'] }, macro: { ok: true, data: files['macro.json'] } }, ms, {}); };\n"
            "const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };\n"
            "const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };\n"
            "const page = (load, t) => renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code: t, ctab: null, disc: null, nav }));\n"
            # the 재무 경고 section of the 요약: from its first co-warn marker to the next card after it
            "const warnPart = (html) => { const k = html.search(/data-ui-v2=\"co-warn/); if (k < 0) return ''; const i = html.lastIndexOf('<', k);\n"
            "  const ends = ['data-ui-v2=\"co-fit\"', 'data-ui-v2=\"co-held\"', 'data-ui-v2=\"co-memo\"'].map((m) => html.indexOf(m, k)).filter((j) => j > 0);\n"
            "  return html.slice(i, ends.length ? html.lastIndexOf('<', Math.min(...ends)) : undefined); };\n"
            "const kind = (part) => (/data-ui-v2=\"(co-warn(?:-unchecked|-off|-unit)?)\"/.exec(part) || [])[1] || null;\n"
            "const px = (part) => [...part.matchAll(/font-size:(\\d+(?:\\.\\d+)?)px/g)].map((m) => Number(m[1]));\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


# ── 1. 규칙 (warn.js): 무엇이 돌지 않았는지 ──
def test_warnings_says_which_checks_did_not_run():
    got = run("""
      const KR = { t: 'X', cls: 'kr' }, w = (co) => W.warnings(KR, co);
      const pick = (r) => ({ allRan: r.allRan, partial: r.partial, icrIe: r.icrIe, unchecked: r.unchecked, noneRan: r.noneRan, flags: r.flags.map((f) => f.code) });
      out = Object.fromEntries(Object.entries(REAL).map(([t, co]) => [t, pick(w(co))]));
      out.old = pick(w({ fy: 2025 }));                                        // flRan 이 없는 예전 파일: 아무것도 알 수 없어요
      out.ieNone = pick(w({ flRan: ['cr', 'l3', 'imp'], flWhy: { icr: 'ie' }, fy: 2025 }));   // PR #68 그대로: 확인한 … 없어요
      out.opFlag = pick(w({ fl: { cr: 80 }, flRan: ['cr', 'l3', 'imp'], flWhy: { icr: 'op' }, fy: 2025 }));   // 이유가 ie 가 아니면 icrIe 아님
      out.fin = pick(w({ flRan: ['l3', 'imp'], flNa: ['cr', 'icr'], fy: 2025 }));   // 금융회사: 해당 없는 건 '못 돌림'이 아니에요
      out.noCo = pick(w(null)); out.us = pick(W.warnings({ t: 'AAPL', cls: 'us' }, { flRan: [] }));""", REAL=REAL)
    assert got["000270"] == {"allRan": False, "partial": False, "icrIe": False, "unchecked": ["imp"], "noneRan": False, "flags": []}
    assert got["066970"]["flags"] == ["cr", "l3"] and got["066970"]["unchecked"] == ["imp"] and not got["066970"]["icrIe"]
    assert got["228760"] == {"allRan": False, "partial": False, "icrIe": True, "unchecked": ["icr"], "noneRan": False, "flags": ["l3"]}
    assert got["0126Z0"]["flags"] == ["icr"] and got["0126Z0"]["unchecked"] == ["l3"]
    for t in ("0011T0", "005935", "241560"):
        assert got[t]["noneRan"] is True and got[t]["unchecked"] == ["cr", "icr", "l3", "imp"] and got[t]["flags"] == [], t
    assert got["088980"]["noneRan"] is True and got["088980"]["unchecked"] == ["l3", "imp"]
    assert got["005930"]["allRan"] is True and got["005930"]["unchecked"] == [] and got["005930"]["noneRan"] is False
    assert got["old"]["unchecked"] is None and got["old"]["noneRan"] is False and got["old"]["allRan"] is False
    assert got["ieNone"]["partial"] is True and got["ieNone"]["icrIe"] is True and got["ieNone"]["unchecked"] == ["icr"]
    assert got["opFlag"]["icrIe"] is False and got["opFlag"]["unchecked"] == ["icr"]
    assert got["fin"]["allRan"] is True and got["fin"]["unchecked"] == []
    for k in ("noCo", "us"):
        assert got[k] == {"allRan": False, "partial": False, "icrIe": False, "unchecked": None, "noneRan": False, "flags": []}, k


# ── 2. 회사 페이지 요약 ──
def test_a_company_where_no_check_could_run_keeps_the_card_and_never_says_none():
    got = run("""
      const load = mkLoad(FILES);
      const one = (t) => { const html = page(load, t), part = warnPart(html);
        return { kind: kind(part), lines: lines(part), chips: (part.match(/co-warn-chip/g) || []).length, px: px(part), all: lines(html) }; };
      out = { words: [C2.rank.warn, C2.pfr.unknown], chabi: one('0011T0'), pref: one('005935'), usd: one('241560'), fund: one('088980') };
      const cur = C2.co.stmtCur.replace('{currency}', 'USD');
      out.usdCur = out.usd.all.filter((x) => x === cur).length;
      for (const k of ['chabi', 'pref', 'usd', 'fund']) delete out[k].all;
      // the unit check keeps its own line in that place (Jack, 2026-11-13), and a file without flRan says nothing
      const f2 = JSON.parse(JSON.stringify(FILES)); const co2 = f2['corp.json'].companies.find((c) => c.t === '0011T0');
      co2.unitChk = ['scale']; f2['data.json'].stocks.find((s) => s.t === '0011T0').unitChk = ['scale'];
      const f3 = JSON.parse(JSON.stringify(FILES)); delete f3['corp.json'].companies.find((c) => c.t === '0011T0').flRan;
      out.unit = kind(warnPart(page(mkLoad(f2), '0011T0')));
      out.oldFile = kind(warnPart(page(mkLoad(f3), '0011T0')));""", FILES=fixture_files())
    assert got["words"] == [HEAD, UNKNOWN]                                   # 승인된 두 말 (rank.warn · pfr.unknown) 그대로
    for k in ("chabi", "pref", "usd"):
        g = got[k]
        assert g["kind"] == "co-warn-unchecked" and g["lines"] == [HEAD, UNKNOWN], (k, g)
        assert g["chips"] == 0 and all(NONE not in x for x in g["lines"]), (k, g)          # ✓ 도 '없어요'도 없어요
        assert g["px"] and min(g["px"]) >= 12, (k, g["px"])
    assert got["usdCur"] == 1                                               # 달러 재무제표: 이유 줄은 한눈에 칸 위에 한 번 그대로
    assert got["fund"]["kind"] is None                                      # 펀드(맥쿼리인프라): 확인할 재무제표가 없어요 (그대로)
    assert got["unit"] == "co-warn-unit"                                    # 공시 단위 확인 중: 그 줄이 먼저예요 (그대로)
    assert got["oldFile"] is None                                           # flRan 이 없는 파일: 아무 말도 하지 않아요 (그대로)


def test_fired_warnings_show_and_say_when_the_interest_check_could_not_run():
    got = run("""
      const load = mkLoad(FILES);
      const one = (t) => { const part = warnPart(page(load, t));
        return { kind: kind(part), n: (/data-ui-v2="co-warn" data-n="(\\d+)"/.exec(part) || [])[1] || null, lines: lines(part),
          noIcr: (part.match(/data-ui-v2="co-warn-noicr"/g) || []).length, px: px(part),
          chips: [...part.matchAll(/data-ui-v2="co-warn-chip" data-check="([a-z0-9]+)"/g)].map((m) => m[1]) }; };
      out = { gene: one('228760'), lnf: one('066970'), epis: one('0126Z0'), kia: one('000270'), sam: one('005930'), line: C2.co.warn.noneSubNoIcr,
        texts: [C2.co.warn.l3, C2.co.warn.cr.replace('{x}', '75'), C2.co.warn.icrLoss] };""", FILES=fixture_files())
    l3, cr, icr_loss = got["texts"]
    assert got["line"] == NO_ICR
    gene = got["gene"]                                                      # 지노믹트리: 순손실 경고 + 이자보상배율은 이자 줄이 없어 못 돌림
    assert gene["kind"] == "co-warn" and gene["n"] == "1" and l3 in gene["lines"]
    assert gene["noIcr"] == 1 and NO_ICR in gene["lines"]                    # 목록 위 줄(누르기 전)에 한 번 (목록 시트는 smoke_v2 가 봐요)
    assert gene["lines"].index(NO_ICR) > gene["lines"].index(l3)
    assert min(gene["px"]) >= 12
    lnf = got["lnf"]                                                        # 엘앤에프: 경고 둘 그대로 · 자본잠식은 승인된 줄이 아직 없어요
    assert lnf["n"] == "2" and cr in lnf["lines"] and lnf["noIcr"] == 0
    assert got["epis"]["n"] == "1" and icr_loss in got["epis"]["lines"] and got["epis"]["noIcr"] == 0
    for k in ("gene", "lnf", "epis"):
        assert all(x not in (NONE, NONE_PARTIAL) for x in got[k]["lines"]), k
    kia = got["kia"]                                                        # 기아: 자본잠식을 못 돌렸어요 → 다 확인한 것처럼 말하지 않아요
    assert NONE not in kia["lines"] and "imp" not in kia["chips"]           # 자본잠식에 ✓ 없음
    assert kia["kind"] == "co-warn" and kia["n"] == "0" and kia["lines"][0] == NONE_PARTIAL and kia["chips"] == ["l3", "cr", "icr"]   # Jack, 11-14
    assert got["sam"]["kind"] == "co-warn" and got["sam"]["n"] == "0" and NONE in got["sam"]["lines"] and got["sam"]["noIcr"] == 0   # 다 돈 회사는 그대로


def test_no_fired_warning_is_ever_left_off_a_korean_company_page():
    """시험 데이터의 모든 한국 회사(실제 값을 넣은 회사 포함): 걸린 경고가 있으면 그 수만큼 목록 줄이 있어요."""
    got = run("""
      const load = mkLoad(FILES), bad = [];
      let n = 0;
      for (const s of FILES['data.json'].stocks) {
        if (s.cls !== 'kr') continue;
        const w = W.warnings(s, load.coByT.get(s.t) || null);
        if (!w.flags.length) continue;
        n += 1;
        const part = warnPart(page(load, s.t));
        if ((/data-ui-v2="co-warn" data-n="(\\d+)"/.exec(part) || [])[1] !== String(w.flags.length)) bad.push(s.t);
      }
      out = { n, bad };""", FILES=fixture_files())
    assert got["n"] >= 100 and got["bad"] == [], got


# ── 3. 가진 종목 '재무 경고 0개' 칸 (홈 · 포트폴리오 · 점검이 같은 pfState 를 읽어요) ──
def test_the_holdings_tile_counts_fired_warnings_and_never_ticks_an_unchecked_holding():
    files = fixture_files()
    stocks = [s for s in files["data.json"]["stocks"] if s["t"] in REAL or s["t"] == "AAPL"]
    corps = [c for c in files["corp.json"]["companies"] if c["t"] in REAL]
    got = run("""
      const ctx = { state: { ok: true }, byT: new Map(STOCKS.map((s) => [s.t, s])), coByT: new Map(CORPS.map((c) => [c.t, c])), fx: 1400, pxDate: '2026-10-30' };
      const nk = (t) => STOCKS.find((s) => s.t === t).nk;
      const deckOf = (ts) => ({ id: 'd', name: 'p', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
        holdings: ts.map((t) => ({ t, nk: nk(t), cls: /^[0-9]/.test(t) ? 'kr' : 'us' })), purchases: [],
        imported: ts.map((t) => ({ t, nk: nk(t), ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty: 1 })) });
      const warn = (ts) => { const r = P.pfState(deckOf(ts), ctx, STOCKS).rules.find((x) => x.id === 'warn');
        return { state: r.state, flagged: r.flagged, tile: lines(renderToStaticMarkup(h(PV.RuleTile, { r }))) }; };
      out = { lnf: warn(['066970']), lnfKia: warn(['066970', '000270']), gene: warn(['228760']), epis: warn(['0126Z0']), kia: warn(['000270']),
        chabi: warn(['0011T0']), pref: warn(['005935']), sam: warn(['005930']), samKia: warn(['005930', '000270']), samUs: warn(['005930', 'AAPL']) };""",
              STOCKS=stocks, CORPS=corps)
    lnf = next(s["nk"] for s in stocks if s["t"] == "066970")
    assert got["lnf"]["state"] == "broken" and got["lnf"]["flagged"] == [lnf]           # 덜 돌아간 회사라도 걸린 경고는 세요
    assert got["lnfKia"]["state"] == "broken" and got["lnfKia"]["flagged"] == [lnf]
    assert got["gene"]["state"] == "broken" and got["epis"]["state"] == "broken"
    for k in ("kia", "chabi", "pref", "samKia", "samUs"):                                  # 하나라도 덜 돌았으면 ✓ 가 아니에요
        assert got[k]["state"] == "unknown" and UNKNOWN in got[k]["tile"], (k, got[k])
    assert got["sam"]["state"] == "ok" and UNKNOWN not in got["sam"]["tile"]
