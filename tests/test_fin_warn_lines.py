# -*- coding: utf-8 -*-
"""재무 경고 · 재무제표 없음: Jack 이 2026-11-14 에 승인한 세 줄 (코디네이터가 그대로 전함).

- "4가지 중 {k}가지는 필요한 자료가 없어서 확인하지 못했어요." (co.warn.uncheckedN): 걸린 경고 줄과 목록 밑 (엘앤에프: 자본잠식 못 돌림),
  '확인한 재무 경고 신호는 없어요' 밑 (기아). 이자보상배율 하나만 이자 줄이 없어 못 돌았으면 PR #68 줄만 (지노믹트리: 둘 다는 아니에요).
- "필요한 자료가 없어서 확인하지 못했어요." (co.warn.noData): '재무 경고' 카드의 제목 밑 (채비 · 우선주; 자리 표시였던 pfr.unknown 대신), 가진 종목
  '재무 경고 0개 · 확인하지 못했어요' 칸 밑 (확인이 덜 돈 한국 회사; 미국 종목만이면 없음).
- "공시된 재무제표가 아직 없어서 계산할 수 없어요." (co.noStmt): 재무제표 숫자가 하나도 없는 회사 (채비 · 본시스템즈)의 요약 한눈에 칸
  위에 한 번, 실적 · 가치 · 배당 탭에 한 번씩. 우선주 · 원화가 아닌 재무제표 · 다른 회사에는 없어요.
- 리뷰 (nit): 확인 하나(이자보상배율)만 돌았고 낸 이자가 없는 회사(int0)는 칩이 하나도 없어서 '확인한 …' 카드를 보이지 않아요.
회사 줄은 2026-11-14 발행의 실제 값 (tests/test_fin_warn_partial.py REAL · tests/fixtures/fin_warn_real_rows.json). 브라우저 화면은
tests/smoke_v2.py 장면 '재무 경고 일부' · '재무 경고 줄'이 봐요.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_fin_warn_partial import REAL, WARN_KEYS  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
MODS = {"L": "src/v2/load.js", "CO": "src/v2/company.jsx", "W": "src/v2/warn.js", "K": "src/v2/company.js", "P": "src/v2/pf.js",
        "PV": "src/v2/pfview.jsx", "FX": "src/v2/fix.js", "CP": "src/copy/v2.js"}
COUNT = "4가지 중 {k}가지는 필요한 자료가 없어서 확인하지 못했어요."
NO_DATA = "필요한 자료가 없어서 확인하지 못했어요."
NO_STMT = "공시된 재무제표가 아직 없어서 계산할 수 없어요."
NO_ICR = "이자보상배율은 재무제표에서 이자 비용을 찾지 못해 확인하지 못했어요. 유동비율, 3년 연속 순손실, 자본잠식은 최근 공시로 확인했어요."
_TMP = {}


def bundle_dir():
    if "p" not in _TMP:
        tmp = tempfile.mkdtemp(prefix="baepsae-finlines-")
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


def files():
    """시험 데이터에 실제 재무 경고 칸(REAL)을 넣고, 본시스템즈(재무제표 없음)의 실제 줄을 더해요."""
    out = {}
    for name in ("data.json", "corp.json", "macro.json"):
        with open(os.path.join(FIX, name), encoding="utf-8") as f:
            out[name] = json.load(f)
    coby = {c["t"]: c for c in out["corp.json"]["companies"]}
    for t, rec in REAL.items():
        for k in WARN_KEYS:
            coby[t].pop(k, None)
        coby[t].update(rec)
    # 채비: 실제 발행처럼 재무제표 숫자가 없어요
    coby["0011T0"].update(rev=[None] * 3, op=[None] * 3, ni=[None] * 3, eq=None)
    with open(os.path.join(ROOT, "tests", "fixtures", "fin_warn_real_rows.json"), encoding="utf-8") as f:
        real = json.load(f)
    out["data.json"]["stocks"] += real["stocks"]
    out["corp.json"]["companies"] += real["companies"]
    next(x for x in out["data.json"]["stocks"] if x["t"] == "088980")["etf"] = True
    return out


def run(body, **data):
    tmp = bundle_dir()
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { L, CO, W, K, P, PV, FX, CP } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const ms = Date.parse('2026-10-30T18:00:00+09:00'); Date.now = () => ms;\n"
            "const mkLoad = (f) => { for (const n of ['data.json', 'corp.json', 'macro.json']) f[n].publishedAt = new Date(ms - 3600000).toISOString();\n"
            "  return L.resolveLoad({ data: { ok: true, data: f['data.json'] }, corp: { ok: true, data: f['corp.json'] }, macro: { ok: true, data: f['macro.json'] } }, ms, {}); };\n"
            "const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };\n"
            "const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };\n"
            "const page = (load, t, ctab = null) => renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code: t, ctab, disc: null, nav }));\n"
            "const count = (html, x) => lines(html).filter((l) => l === x).length;\n"
            "const marked = (html, v) => (html.match(new RegExp('data-ui-v2=\"' + v + '\"', 'g')) || []).length;\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_the_three_lines_are_jacks_words():
    got = run("out = [C2.co.warn.uncheckedN, C2.co.warn.noData, C2.co.noStmt];")
    assert got == [COUNT, NO_DATA, NO_STMT]
    with open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8") as f:
        doc = f.read()
    for key, text in (("co.warn.uncheckedN", COUNT), ("co.warn.noData", NO_DATA), ("co.noStmt", NO_STMT)):
        assert f"| `{key}` | {text} | Jack, 2026-11-14" in doc, key


def test_state_and_count_rules():
    got = run("""
      const KR = { t: 'X', cls: 'kr' }, FUND = { t: 'X', cls: 'kr', etf: true };
      const k = (co, s = KR, off = false) => { const w = W.warnings(s, co); return [K.warnKind(s, w), K.uncheckedCount(w, off)]; };
      out = { kia: k(REAL['000270']), lnf: k(REAL['066970']), gene: k(REAL['228760']), epis: k(REAL['0126Z0']), chabi: k(REAL['0011T0']),
        sam: k(REAL['005930']), fund: k(REAL['088980'], FUND),
        int0: k({ flRan: ['icr'], flSrc: { icr: 'is', int0: true }, fy: 2025 }),          // 리뷰 nit: 칩이 하나도 없어요
        icrOnly: k({ flRan: ['icr'], flSrc: { icr: 'is' }, fy: 2025 }),
        off: k({ flRan: ['cr', 'l3', 'imp'], flWhy: { icr: 'off' }, fy: 2025 }, KR, true),
        offFlag: k({ fl: { cr: 80 }, flRan: ['cr', 'l3', 'imp'], flWhy: { icr: 'off' }, fy: 2025 }, KR, true),
        offMore: k({ fl: { cr: 80 }, flRan: ['cr', 'l3'], flWhy: { icr: 'off' }, fy: 2025 }, KR, true),
        fin: k({ flRan: ['l3'], flNa: ['cr', 'icr'], fy: 2025 }), old: k({ fy: 2025 }) };""", REAL=REAL)
    assert got["kia"] == ["some", 1] and got["lnf"] == ["flags", 1] and got["epis"] == ["flags", 1]
    assert got["gene"] == ["flags", 0]                      # 이자보상배율 하나만, 이자 줄이 없어서: PR #68 줄이 대신해요
    assert got["chabi"] == ["unchecked", 0] and got["sam"] == ["none", 0] and got["fund"] == [None, 0]
    assert got["int0"] == [None, 3]                         # '확인한 …' 밑에 아무 칩도 없을 카드는 없어요 (그래서 줄도 없어요)
    assert got["icrOnly"] == ["some", 3]
    assert got["off"][1] == 0 and got["offFlag"] == ["flags", 0]   # 꺼진 이자보상배율은 그 줄(fix.icr)이 말해요
    assert got["offMore"] == ["flags", 2]
    assert got["fin"] == ["some", 1] and got["old"] == [None, 0]


def test_company_page_lines():
    got = run("""
      const load = mkLoad(FILES);
      const part = (html) => { const k = html.search(/data-ui-v2="co-warn/); if (k < 0) return '';
        const i = html.lastIndexOf('<', k), j = html.indexOf('data-ui-v2="co-fit"', k); return html.slice(i, j > 0 ? html.lastIndexOf('<', j) : undefined); };
      const one = (t) => { const p = part(page(load, t)); return { lines: lines(p), count: marked(p, 'co-warn-count'), noIcr: marked(p, 'co-warn-noicr'),
        noData: marked(p, 'co-warn-nodata'), k: (/data-ui-v2="co-warn-count" data-k="(\\d)"/.exec(p) || [])[1] || null }; };
      out = { lnf: one('066970'), kia: one('000270'), gene: one('228760'), chabi: one('0011T0'), bon: one('496320'), pref: one('005935'), sam: one('005930') };""",
              FILES=files())
    one = COUNT.replace("{k}", "1")
    lnf, kia, gene = got["lnf"], got["kia"], got["gene"]
    assert lnf["count"] == 1 and one in lnf["lines"] and lnf["k"] == "1" and lnf["noIcr"] == 0      # 엘앤에프: 경고 줄 밑 (목록 밑은 smoke_v2)
    assert kia["lines"][0] == "확인한 재무 경고 신호는 없어요" and one in kia["lines"] and kia["count"] == 1   # 기아: '확인한 …' 밑
    assert gene["noIcr"] == 1 and gene["count"] == 0 and NO_ICR in gene["lines"]                    # 지노믹트리: PR #68 줄만
    for t in ("chabi", "bon", "pref"):                      # 하나도 못 돌았어요: 카드 밑에 Jack 의 이유 줄 (우선주도)
        assert got[t]["lines"] == ["재무 경고", NO_DATA] and got[t]["noData"] == 1, (t, got[t])
    assert got["sam"]["count"] == 0 and got["sam"]["noData"] == 0 and NO_DATA not in got["sam"]["lines"]


def test_no_statements_line_once_per_place():
    got = run("""
      const load = mkLoad(FILES);
      const tabs = (t) => Object.fromEntries([['summary', null], ['earn', 'earn'], ['value', 'value'], ['div', 'div']].map(([k, ct]) => {
        const html = page(load, t, ct); return [k, { n: count(html, NO), marked: marked(html, 'no-stmt'), na: (/data-ui-v2="co-div" data-cls="kr" data-rule="na"/.test(html)) }]; }));
      out = { bon: tabs('496320'), chabi: tabs('0011T0'), pref: tabs('005935'), usd: tabs('241560'), sam: tabs('005930'), aapl: tabs('AAPL'),
        tilesFirst: (() => { const html = page(load, '496320'); return html.indexOf('data-ui-v2="no-stmt"') < html.indexOf('data-ui-v2="co-tile"'); })() };""",
              FILES=files(), NO=NO_STMT)
    for t in ("bon", "chabi"):                             # 본시스템즈 · 채비: 요약 · 실적 · 가치에 한 번씩, 배당 탭은 '자료가 없어요'일 때 그 밑에
        assert all(got[t][k]["n"] == 1 and got[t][k]["marked"] == 1 for k in ("summary", "earn", "value")), (t, got[t])
        assert got[t]["div"]["n"] == (1 if got[t]["div"]["na"] else 0), (t, got[t]["div"])
    assert got["chabi"]["div"]["na"] and got["chabi"]["div"]["n"] == 1
    for t in ("pref", "usd", "sam", "aapl"):                # 우선주 · 원화가 아닌 재무제표 · 다른 회사 · 미국: 없어요
        assert all(got[t][k]["n"] == 0 for k in got[t]), (t, got[t])
    assert got["tilesFirst"]                               # 한눈에 칸들 위


def test_holdings_tile_says_no_data_only_for_korean_holdings_with_missing_checks():
    f = files()
    stocks = [s for s in f["data.json"]["stocks"] if s["t"] in REAL or s["t"] in ("AAPL", "496320")]
    corps = [c for c in f["corp.json"]["companies"] if c["t"] in REAL or c["t"] == "496320"]
    got = run("""
      const ctx = { state: { ok: true }, byT: new Map(STOCKS.map((s) => [s.t, s])), coByT: new Map(CORPS.map((c) => [c.t, c])), fx: 1400, pxDate: '2026-10-30' };
      const nk = (t) => STOCKS.find((s) => s.t === t).nk;
      const deckOf = (ts) => ({ id: 'd', name: 'p', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
        holdings: ts.map((t) => ({ t, nk: nk(t), cls: /^[0-9]/.test(t) ? 'kr' : 'us' })), purchases: [],
        imported: ts.map((t) => ({ t, nk: nk(t), ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty: 1 })) });
      const warn = (ts) => { const r = P.pfState(deckOf(ts), ctx, STOCKS).rules.find((x) => x.id === 'warn');
        return { state: r.state, noData: r.noData, tile: lines(renderToStaticMarkup(h(PV.RuleTile, { r }))) }; };
      out = { kia: warn(['000270']), chabi: warn(['0011T0']), bon: warn(['496320']), pref: warn(['005935']), samUs: warn(['005930', 'AAPL']),
        kiaUs: warn(['000270', 'AAPL']), usd: warn(['241560']), lnfKia: warn(['066970', '000270']), sam: warn(['005930']) };""", STOCKS=stocks, CORPS=corps)
    for k in ("kia", "chabi", "bon", "pref", "kiaUs"):
        assert got[k]["state"] == "unknown" and got[k]["noData"] is True and got[k]["tile"] == ["재무 경고 0개", "확인하지 못했어요", NO_DATA], (k, got[k])
    assert got["samUs"]["tile"] == ["재무 경고 0개", "확인하지 못했어요"] and got["samUs"]["noData"] is False   # 미국 종목은 자료가 없어서가 아니에요
    assert got["usd"]["noData"] is False and NO_DATA not in got["usd"]["tile"]          # 원화가 아닌 재무제표: 통화 줄이 말해요
    assert got["lnfKia"]["state"] == "broken" and NO_DATA not in got["lnfKia"]["tile"]  # 걸린 경고가 있으면 확인하지 못했어요가 아니에요
    assert got["sam"]["state"] == "ok"
