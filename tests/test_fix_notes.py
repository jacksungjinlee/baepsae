# -*- coding: utf-8 -*-
"""DART 다시 읽기 전까지의 두 안내 줄 (Jack, 2026-11-08) — src/repair.js · src/v2/fix.js · src/v2/fixnote.jsx · src/fixnote.jsx.

- PER · EPS 줄 "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.": 한국 종목에만, corp.json 에 epsBasis "owners" 가
  없을 때만. 파일이 없거나 값이 다르면 줄이 있어요 (고쳐졌다고 짐작하지 않아요). {date} 는 src/repair.js EPS_FIX_DATE 하나를 각 앱의
  월 · 일 표시로 ("11월 9일"). 그 날짜가 지났는데 표시가 없으면 줄은 그대로, console 에 크게 한 번
- 이자보상배율 줄 "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요.": corp.json flWhy.icr 가 "off" 인 회사의 재무 경고
  (경고가 있을 때 목록 밑 · 아무것도 말할 수 없어 카드가 숨을 때 그 자리 · 가진 종목 '재무 경고 0개' 칸의 확인하지 못했어요 밑).
  flWhy.icr 가 "off" 가 아니면 없어요
- 두 앱의 글자가 같고(2.0 src/copy/v2.js C.fix · 예전 뱁새 src/fixnote.jsx), 글자는 12px 이상이에요
화면은 react-dom/server 로 실제 컴포넌트를 그려서 봐요. 2.0 화면 전체(회사 페이지 · 재무 경고 · 규칙 칸)는 tests/smoke_v2.py 장면
'고치는 중 안내', 예전 뱁새 기업분석은 tests/smoke_app.py 의 같은 이름 장면이 봐요.
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
MODS = {"RP": "src/repair.js", "FX": "src/v2/fix.js", "FN": "src/v2/fixnote.jsx", "P": "src/v2/pf.js", "PV": "src/v2/pfview.jsx",
        "CP": "src/copy/v2.js", "FM": "src/v2/format.js", "OF": "src/fixnote.jsx", "SH": "src/shell.jsx", "OLD": "src/corp.jsx", "D": "src/data.js"}
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "v2", "corp.json")
EPS = "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요."
ICR = "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요."


def fix_date():
    src = open(os.path.join(ROOT, "src", "repair.js"), encoding="utf-8").read()
    m = re.findall(r'^export const EPS_FIX_DATE = "(\d{4})-(\d{2})-(\d{2})";$', src, flags=re.M)
    assert len(m) == 1, m
    return m[0]


def eps_line():
    y, mo, d = fix_date()
    return EPS.format(date=f"{int(mo)}월 {int(d)}일")


def run(tmp, body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react'; import fs from 'fs';\n"
            "const { RP, FX, FN, P, PV, CP, FM, OF, SH, OLD, D } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m));\n"
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(FIXTURE)}, 'utf8'));\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const count = (html, text) => lines(html).filter((l) => l === text).length;\n"
            "const kstMs = (iso) => Date.parse(iso + 'T12:00:00+09:00');\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=tmp, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def company(t):
    with open(FIXTURE, encoding="utf-8") as f:
        return next(c for c in json.load(f)["companies"] if c["t"] == t)


# ── 규칙: 표시 · 날짜 · 이자보상배율 ──
def test_the_marker_the_date_and_icr_off():
    got = run(bundle_dir(), """
      const D0 = RP.EPS_FIX_DATE;
      const next = D.kstDate(kstMs(D0) + 86400000), prev = D.kstDate(kstMs(D0) - 86400000);
      out = {
        live: [RP.epsBasisLive(null), RP.epsBasisLive(undefined), RP.epsBasisLive({}), RP.epsBasisLive({ epsBasis: 'owners' }),
          RP.epsBasisLive({ epsBasis: 'total' }), RP.epsBasisLive({ epsBasis: 'Owners' }), RP.epsBasisLive([]), RP.epsBasisLive('owners')],
        late: [RP.epsFixLate({}, prev), RP.epsFixLate({}, D0), RP.epsFixLate({}, next), RP.epsFixLate(null, next),
          RP.epsFixLate({ epsBasis: 'owners' }, next), RP.epsFixLate({}, 'tomorrow'), RP.epsFixLate({}, null)],
        icr: [RP.icrOff({ flWhy: { icr: 'off' } }), RP.icrOff({ flWhy: { icr: 'ie' } }), RP.icrOff({ flWhy: { icr: 'op' } }),
          RP.icrOff({ flWhy: { icr: 'neg' } }), RP.icrOff({ flWhy: 'off' }), RP.icrOff({}), RP.icrOff(null), RP.icrOff({ flWhy: null })],
        owners: RP.EPS_BASIS_OWNERS, date: D0,
      };""")
    assert got["owners"] == "owners" and got["date"] == "-".join(fix_date())
    assert got["live"] == [False, False, False, True, False, False, False, False]      # 정확히 epsBasis "owners" 일 때만
    assert got["late"] == [False, False, True, True, False, False, False]              # 그날이 지나야 (그날은 아직 아니에요)
    assert got["icr"] == [True, False, False, False, False, False, False, False]       # flWhy.icr "off" 만


def test_a_passed_date_warns_once_and_keeps_the_line():
    got = run(bundle_dir(), """
      const D0 = RP.EPS_FIX_DATE;
      const after = kstMs(D.kstDate(kstMs(D0) + 2 * 86400000)), before = kstMs(D0) - 86400000;
      const a = FX.setEpsBasis({ companies: [] }, { now: before });          // 아직 그날 전: 조용
      const w0 = warns.length;
      const b = FX.setEpsBasis({ companies: [] }, { now: after, preview: true });   // 미리 보기(날짜가 고정된 예시): 조용
      const w1 = warns.length;
      const c = FX.setEpsBasis({ companies: [] }, { now: after });           // 지났고 표시 없음: 한 번 크게
      const d = FX.setEpsBasis({ companies: [] }, { now: after });           // 다시 읽어도 한 번만
      const w2 = warns.slice(w1);
      const shown = FX.epsFixFor({ cls: 'kr' });                             // 줄은 그대로
      const e = FX.setEpsBasis({ companies: [], epsBasis: 'owners' }, { now: after });
      out = { live: [a, b, c, d, e], w0, w1, w2, shown, after: FX.epsFixFor({ cls: 'kr' }),
        old: [RP.warnEpsFixLate({}, D.kstDate(after), 'old-app'), RP.warnEpsFixLate({}, D.kstDate(after), 'old-app'),
          RP.warnEpsFixLate({ epsBasis: 'owners' }, D.kstDate(after), 'other')] };""")
    assert got["live"] == [False, False, False, False, True]
    assert got["w0"] == 0 and got["w1"] == 0, got
    assert len(got["w2"]) == 1 and "!!" in got["w2"][0] and "EPS_FIX_DATE" in got["w2"][0] and "src/repair.js" in got["w2"][0], got["w2"]
    assert got["shown"] is True and got["after"] is False
    assert got["old"] == [True, False, False]                                # 예전 뱁새도 한 번만, 표시가 있으면 말하지 않아요


def test_the_eps_line_is_for_korean_stocks_only_until_the_marker():
    got = run(bundle_dir(), """
      const KR = { t: '005930', cls: 'kr' }, US = { t: 'AAPL', cls: 'us' };
      const look = () => [FX.epsFixFor(KR), FX.epsFixFor(US), FX.epsFixFor(null), FX.epsFixFor({ t: 'X' }), FX.epsFixForAny([US, KR]), FX.epsFixForAny([US]),
        FX.epsFixForAny(null)];
      FX.setEpsBasis(null);                       const failed = look();      // 파일이 없어도 고쳐졌다고 짐작하지 않아요
      FX.setEpsBasis({ companies: [] });          const missing = look();
      FX.setEpsBasis({ epsBasis: 'total' });      const other = look();
      FX.setEpsBasis({ epsBasis: 'owners' });     const live = look();
      out = { failed, missing, other, live };""")
    on = [True, False, False, False, True, False, False]
    assert got["failed"] == on and got["missing"] == on and got["other"] == on
    assert got["live"] == [False] * 7


# ── 글자: 두 앱이 같고 · 날짜는 월 · 일 · 12px 이상 ──
def test_both_apps_say_the_same_approved_words_with_the_month_day_date():
    got = run(bundle_dir(), """
      FX.setEpsBasis({ companies: [] });
      const v2 = renderToStaticMarkup(h(FN.EpsFixNote, { show: true })), v2off = renderToStaticMarkup(h(FN.EpsFixNote, { show: false }));
      const icr = renderToStaticMarkup(h(FN.IcrOffNote, { show: true })), icrLine = renderToStaticMarkup(h(FN.IcrOffLine, { show: true }));
      const icrNo = renderToStaticMarkup(h(FN.IcrOffNote, { show: false })) + renderToStaticMarkup(h(FN.IcrOffLine, { show: false }));
      const old = renderToStaticMarkup(h(OF.EpsFixLine, { corp: { companies: [] } })), oldLive = renderToStaticMarkup(h(OF.EpsFixLine, { corp: { epsBasis: 'owners' } }));
      const oldIcr = renderToStaticMarkup(h(OF.IcrOffLine, { co: { flWhy: { icr: 'off' } } })), oldIcrNo = renderToStaticMarkup(h(OF.IcrOffLine, { co: { flWhy: { icr: 'ie' } } }));
      out = { copy: [C2.fix.eps, C2.fix.icr], oldWords: [OF.FIX_EPS, OF.FIX_ICR], v2text: FN.epsFixText(), oldText: OF.fixEpsText(),
        v2: lines(v2), v2off, icr: lines(icr), icrLine: lines(icrLine), icrNo, old: lines(old), oldLive, oldIcr: lines(oldIcr), oldIcrNo,
        px: [v2, icr, icrLine, old, oldIcr].map((x) => Number((/font-size:(\\d+(?:\\.\\d+)?)px/.exec(x) || [])[1])),
        md: FM.mdText(RP.EPS_FIX_DATE), oldMd: D.mdOf(RP.EPS_FIX_DATE, 'ko') };""")
    assert got["copy"] == [EPS, ICR] and got["oldWords"] == [EPS, ICR]           # Jack 의 글자 그대로, 두 앱이 같아요
    y, mo, d = fix_date()
    assert got["md"] == got["oldMd"] == f"{int(mo)}월 {int(d)}일"             # 각 앱의 월 · 일 표시 ("11월 9일")
    assert got["v2text"] == got["oldText"] == eps_line()
    assert got["v2"] == [eps_line()] and got["v2off"] == ""
    assert got["icr"] == [ICR] and got["icrLine"] == [ICR] and got["icrNo"] == ""
    assert got["old"] == [eps_line()] and got["oldLive"] == "" and got["oldIcr"] == [ICR] and got["oldIcrNo"] == ""
    assert all(px >= 12 for px in got["px"]), got["px"]                      # 12px 바닥 (2.0 은 13px, 예전 뱁새 12px)


def test_the_date_lives_in_one_constant():
    """날짜는 src/repair.js 의 EPS_FIX_DATE 하나예요. 다른 소스 파일에 그 날짜가 글자로 또 있으면 바꿀 때 하나를 놓쳐요."""
    y, mo, d = fix_date()
    iso = f"{y}-{mo}-{d}"
    hits = []
    for base, _, files in os.walk(os.path.join(ROOT, "src")):
        for f in files:
            p = os.path.join(base, f)
            if not f.endswith((".js", ".jsx")):
                continue
            body = open(p, encoding="utf-8").read()
            if "EPS_FIX_DATE =" in body and not p.endswith(os.path.join("src", "repair.js")):
                hits.append((p, "defines EPS_FIX_DATE"))
            if iso in body and not p.endswith(os.path.join("src", "repair.js")):
                hits.append((p, iso))
            if f"{int(mo)}월 {int(d)}일에 바뀔" in body:
                hits.append((p, "date written into the line"))
    assert not hits, hits


# ── 가진 종목 '재무 경고 0개' 칸 ──
def test_the_holdings_warning_tile_says_why_when_icr_is_off():
    stocks = [{"t": "000010", "nk": "가나전자", "cls": "kr", "price": 10000.0, "val20": 50.0, "ind": "semi", "indName": "반도체", "fy": 2025},
              {"t": "000020", "nk": "다라화학", "cls": "kr", "price": 10000.0, "val20": 50.0, "ind": "chem", "indName": "화학", "fy": 2025},
              {"t": "AAA", "nk": "Alpha Inc.", "cls": "us", "ccy": "USD", "price": 100.0, "val": 50.0, "ind": "software", "indName": "소프트웨어"}]
    corps = {"off": [{"t": "000010", "fy": 2025, "flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "off"}}],
             "offFlag": [{"t": "000010", "fy": 2025, "flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "off"}},
                         {"t": "000020", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"], "fl": {"cr": 80}}],
             "ie": [{"t": "000010", "fy": 2025, "flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "ie"}}],
             "on": [{"t": "000010", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"]}]}
    got = run(bundle_dir(), """
      const ctxOf = (corps) => ({ state: { ok: true }, byT: new Map(STOCKS.map((s) => [s.t, s])), coByT: new Map(corps.map((c) => [c.t, c])), fx: 1000, pxDate: '2026-11-06' });
      const row = (t, nk) => ({ t, nk, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty: 1 });
      const deckOf = (rows) => ({ id: 'd', name: 'p', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
        holdings: rows.map((r) => ({ t: r.t, nk: r.nk, cls: /^[0-9]/.test(r.t) ? 'kr' : 'us' })), purchases: [], imported: rows });
      const KR1 = [row('000010', '가나전자')], KR2 = [row('000010', '가나전자'), row('000020', '다라화학')], US1 = [row('AAA', 'Alpha Inc.')];
      const warn = (rows, corps) => { const r = P.pfState(deckOf(rows), ctxOf(corps), STOCKS).rules.find((x) => x.id === 'warn');
        return { state: r.state, icrOff: r.icrOff, tile: lines(renderToStaticMarkup(h(PV.RuleTile, { r }))) }; };
      out = { off: warn(KR1, CORPS.off), offUs: warn([...KR1, ...US1], CORPS.off), us: warn(US1, CORPS.off), flag: warn(KR2, CORPS.offFlag),
        ie: warn(KR1, CORPS.ie), on: warn(KR1, CORPS.on), noCorp: warn(KR1, []) };""", STOCKS=stocks, CORPS=corps)
    unknown = "확인하지 못했어요"
    assert got["off"] == {"state": "unknown", "icrOff": True, "tile": ["재무 경고 0개", unknown, ICR]}, got["off"]
    assert got["offUs"]["state"] == "unknown" and got["offUs"]["icrOff"] is True and got["offUs"]["tile"][-1] == ICR   # 이유 하나는 말해요
    assert got["us"] == {"state": "unknown", "icrOff": False, "tile": ["재무 경고 0개", unknown]}                         # 미국만: 이 줄이 아니에요
    assert got["flag"]["state"] == "broken" and ICR not in got["flag"]["tile"]           # 걸린 경고가 있으면 확인하지 못했어요가 아니에요
    assert got["ie"]["icrOff"] is False and ICR not in got["ie"]["tile"]                 # 이자 비용 줄이 없는 것과는 다른 이유예요
    assert got["on"]["state"] == "ok" and ICR not in got["on"]["tile"]                   # 다시 켜지면 저절로 사라져요
    assert got["noCorp"]["icrOff"] is False and ICR not in got["noCorp"]["tile"]


# ── 예전 뱁새: 첫 화면 성적표 · 기업분석 ──
def test_old_app_score_card_and_company_page_show_the_lines_until_the_marker():
    sam = company("005930")
    c_off = {**sam, "flWhy": {"icr": "off"}, "flRan": ["cr", "l3", "imp"], "fl": {"cr": 80}}
    got = run(bundle_dir(), """
      const card = (c, corp, lang) => lines(renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, corp, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } })));
      const page = (data, t) => renderToStaticMarkup(h(OLD.CompanyView, { data, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const NOW = { ...CORP, companies: CORP.companies.map((x) => (x.t === COFF.t ? COFF : x)) };
      const FIXED = { ...NOW, epsBasis: 'owners', companies: NOW.companies.map((x) => (x.t === COFF.t ? { ...COFF, flWhy: undefined } : x)) };
      const EPS = OF.fixEpsText();
      out = {
        ko: card(COFF, NOW, 'ko'), en: card(COFF, NOW, 'en'), fixed: card({ ...COFF, flWhy: undefined }, FIXED, 'ko'),
        pageNow: count(page(NOW, COFF.t), EPS), pageIcr: count(page(NOW, COFF.t), OF.FIX_ICR), pageFixed: count(page(FIXED, COFF.t), EPS),
        pageFixedIcr: count(page(FIXED, COFF.t), OF.FIX_ICR), html: page(NOW, COFF.t),
      };""", COFF=c_off)
    assert eps_line() in got["ko"] and ICR in got["ko"], got["ko"]
    assert got["ko"].index(eps_line()) > next(i for i, l in enumerate(got["ko"]) if l.startswith("PER "))   # PER 줄 밑
    assert ICR in got["ko"][got["ko"].index("짚고 갈 재무 신호 1개가 있어요"):]                         # 재무 신호 밑
    assert eps_line() not in got["en"] and ICR not in got["en"]               # 영어 화면: Jack 이 영어 글을 승인할 때까지 없어요
    assert eps_line() not in got["fixed"] and ICR not in got["fixed"]         # 다시 읽기가 끝나면 둘 다 없어요
    # 기업분석: 투자지표 · 업종 내 위치 · 주가 분해 · DCF (네 칸에 한 줄씩), 재무 신호 밑에 이자보상배율 한 줄
    assert got["pageNow"] == 4 and got["pageIcr"] == 1, (got["pageNow"], got["pageIcr"])
    assert got["pageFixed"] == 0 and got["pageFixedIcr"] == 0
    assert all(int(px) >= 12 for px in re.findall(r'data-fix="(?:eps|icr)" style="font-size:(\d+)px', got["html"]))


_TMP = {}


def bundle_dir():
    """2.0 과 예전 뱁새의 모듈을 한 파일로 한 번만 묶어요. React 는 밖에 둬요 (node_modules 의 것)."""
    if "p" not in _TMP:
        tmp = tempfile.mkdtemp(prefix="baepsae-fix-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs", "--log-level=error"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _TMP["p"] = tmp
    return _TMP["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _TMP:
        shutil.rmtree(_TMP["p"], ignore_errors=True)
