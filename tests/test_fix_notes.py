# -*- coding: utf-8 -*-
"""DART 다시 읽기 전까지의 두 안내 줄 (Jack, 2026-11-08) — src/repair.js · src/v2/fix.js · src/v2/fixnote.jsx · src/fixnote.jsx.

- PER · EPS 줄 "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.": 한국 종목에만, corp.json 에 epsBasis "owners" 가
  없을 때만. 파일이 없거나 값이 다르면 줄이 있어요 (고쳐졌다고 짐작하지 않아요). {date} 는 src/repair.js EPS_FIX_DATE 하나를 각 앱의
  월 · 일 표시로 ("11월 9일"). 그 날짜가 지났는데 표시가 없으면 줄은 그대로, console 에 크게 한 번
- 이자보상배율 줄 "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요.": corp.json flWhy.icr 가 "off" 인 회사의 재무 경고
  (경고가 있을 때 목록 밑 · 아무것도 말할 수 없어 카드가 숨을 때 그 자리 · 가진 종목 '재무 경고 0개' 칸의 확인하지 못했어요 밑).
  flWhy.icr 가 "off" 가 아니면 없어요
- 다시 읽은 뒤에는 회사마다: 표시가 있고 그 회사의 epsIn.b 가 "o" · "s" 일 때만 줄이 사라져요 ("t" · epsIn 없음은 그대로)
- 주가는 무엇으로 움직였나 · 지금 가격이 가정하는 것: 두 끝이 EPS 와 같은 기준 (지금 발행은 예전 식 그대로, 다시 읽은 뒤에는 지배주주
  순이익 ÷ 보통주 + 상장 우선주). 같은 기준이 없으면 숫자 없이 PER · EPS 줄만
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
        "CP": "src/copy/v2.js", "FM": "src/v2/format.js", "OF": "src/fixnote.jsx", "SH": "src/shell.jsx", "OLD": "src/corp.jsx", "D": "src/data.js",
        "K": "src/v2/company.js"}
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
      const e = FX.setEpsBasis({ companies: [{ t: '005930', epsIn: { ni: 1, b: 'o', p: '2026.2Q', sh: 1 } }], epsBasis: 'owners' }, { now: after });
      out = { live: [a, b, c, d, e], w0, w1, w2, shown, after: FX.epsFixFor({ t: '005930', cls: 'kr' }),
        old: [RP.warnEpsFixLate({}, D.kstDate(after), 'old-app'), RP.warnEpsFixLate({}, D.kstDate(after), 'old-app'),
          RP.warnEpsFixLate({ epsBasis: 'owners' }, D.kstDate(after), 'other')] };""")
    assert got["live"] == [False, False, False, False, True]
    assert got["w0"] == 0 and got["w1"] == 0, got
    assert len(got["w2"]) == 1 and "!!" in got["w2"][0] and "EPS_FIX_DATE" in got["w2"][0] and "src/repair.js" in got["w2"][0], got["w2"]
    assert got["shown"] is True and got["after"] is False
    assert got["old"] == [True, False, False]                                # 예전 뱁새도 한 번만, 표시가 있으면 말하지 않아요


def test_the_eps_line_is_for_korean_stocks_until_the_marker_and_per_company():
    """다시 읽은 뒤에는 회사마다: 표시(epsBasis "owners")가 있고 그 회사의 epsIn.b 가 "o"(지배주주 순이익) · "s"(별도 재무제표)일 때만
    줄이 사라져요. "t"(지배주주 줄이 없는 연결 재무제표의 총 순이익) · epsIn 없음은 그대로예요 (코디네이터, 데이터 검토)."""
    got = run(bundle_dir(), """
      const IN = (b) => ({ ni: 100, b, p: '2026.2Q', sh: 1000000 });
      const COS = [{ t: '000010', epsIn: IN('o') }, { t: '000020', epsIn: IN('s') }, { t: '000030', epsIn: IN('t') }, { t: '000040' },
        { t: '000050', epsIn: IN('x') }, { t: '000060', epsIn: 'o' }];
      const KR = COS.map((c) => ({ t: c.t, cls: 'kr' })), US = { t: 'AAPL', cls: 'us' };
      const look = () => [...KR.map(FX.epsFixFor), FX.epsFixFor(US), FX.epsFixFor(null), FX.epsFixFor({ t: '000010' }),
        FX.epsFixForAny([US, KR[0]]), FX.epsFixForAny([KR[0], KR[2]]), FX.epsFixForAny([US]), FX.epsFixForAny(null)];
      const need = (corp) => COS.map((c) => RP.epsFixNeeded(corp, c));
      FX.setEpsBasis(null);                                        const failed = look();      // 파일이 없어도 고쳐졌다고 짐작하지 않아요
      FX.setEpsBasis({ companies: COS });                          const missing = look();     // 표시 없음 (지금 발행): 모두
      FX.setEpsBasis({ epsBasis: 'total', companies: COS });       const other = look();
      FX.setEpsBasis({ epsBasis: 'owners', companies: COS });      const live = look();
      out = { failed, missing, other, live, needNow: need({ companies: COS }), needLive: need({ epsBasis: 'owners', companies: COS }),
        fixed: COS.map(RP.epsInFixed) };""")
    on = [True] * 6 + [False, False, False, True, True, False, False]
    assert got["failed"] == on and got["missing"] == on and got["other"] == on
    assert got["live"] == [False, False, True, True, True, True] + [False, False, False, False, True, False, False]
    assert got["needNow"] == [True] * 6
    assert got["needLive"] == [False, False, True, True, True, True]            # o · s 만 고쳐졌어요
    assert got["fixed"] == [True, True, False, False, False, False]


# ── 글자: 두 앱이 같고 · 날짜는 월 · 일 · 12px 이상 ──
def test_both_apps_say_the_same_approved_words_with_the_month_day_date():
    got = run(bundle_dir(), """
      FX.setEpsBasis({ companies: [] });
      const v2 = renderToStaticMarkup(h(FN.EpsFixNote, { show: true })), v2off = renderToStaticMarkup(h(FN.EpsFixNote, { show: false }));
      const icr = renderToStaticMarkup(h(FN.IcrOffNote, { show: true })), icrLine = renderToStaticMarkup(h(FN.IcrOffLine, { show: true }));
      const icrNo = renderToStaticMarkup(h(FN.IcrOffNote, { show: false })) + renderToStaticMarkup(h(FN.IcrOffLine, { show: false }));
      const CO = { t: '000010', epsIn: { ni: 1, b: 'o', p: '2026.2Q', sh: 1 } }, CT = { t: '000020', epsIn: { ni: 1, b: 't', p: '2026.2Q', sh: 1 } };
      const LIVE = { epsBasis: 'owners', companies: [CO, CT] };
      const old = renderToStaticMarkup(h(OF.EpsFixLine, { corp: { companies: [CO] }, cos: [CO] })), oldLive = renderToStaticMarkup(h(OF.EpsFixLine, { corp: LIVE, cos: [CO] }));
      const oldT = lines(renderToStaticMarkup(h(OF.EpsFixLine, { corp: LIVE, cos: [CO, CT] }))), oldForce = lines(renderToStaticMarkup(h(OF.EpsFixLine, { corp: LIVE, cos: [CO], force: true })));
      const oldIcr = renderToStaticMarkup(h(OF.IcrOffLine, { co: { flWhy: { icr: 'off' } } })), oldIcrNo = renderToStaticMarkup(h(OF.IcrOffLine, { co: { flWhy: { icr: 'ie' } } }));
      out = { copy: [C2.fix.eps, C2.fix.icr], oldWords: [OF.FIX_EPS, OF.FIX_ICR], v2text: FN.epsFixText(), oldText: OF.fixEpsText(),
        v2: lines(v2), v2off, icr: lines(icr), icrLine: lines(icrLine), icrNo, old: lines(old), oldLive, oldT, oldForce, oldIcr: lines(oldIcr), oldIcrNo,
        px: [v2, icr, icrLine, old, oldIcr].map((x) => Number((/font-size:(\\d+(?:\\.\\d+)?)px/.exec(x) || [])[1])),
        md: FM.mdText(RP.EPS_FIX_DATE), oldMd: D.mdOf(RP.EPS_FIX_DATE, 'ko') };""")
    assert got["copy"] == [EPS, ICR] and got["oldWords"] == [EPS, ICR]           # Jack 의 글자 그대로, 두 앱이 같아요
    y, mo, d = fix_date()
    assert got["md"] == got["oldMd"] == f"{int(mo)}월 {int(d)}일"             # 각 앱의 월 · 일 표시 ("11월 9일")
    assert got["v2text"] == got["oldText"] == eps_line()
    assert got["v2"] == [eps_line()] and got["v2off"] == ""
    assert got["icr"] == [ICR] and got["icrLine"] == [ICR] and got["icrNo"] == ""
    assert got["old"] == [eps_line()] and got["oldLive"] == "" and got["oldIcr"] == [ICR] and got["oldIcrNo"] == ""
    assert got["oldT"] == [eps_line()] and got["oldForce"] == [eps_line()]   # 칸의 한 회사라도 총 순이익이면 · 숫자를 뺀 칸은 언제나
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
      const FIXED = { ...NOW, epsBasis: 'owners', companies: NOW.companies.map((x) => (x.t === COFF.t ? { ...COFF, flWhy: undefined, ...REREAD } : x)) };
      const EPS = OF.fixEpsText();
      out = {
        ko: card(COFF, NOW, 'ko'), en: card(COFF, NOW, 'en'), fixed: card({ ...COFF, flWhy: undefined, ...REREAD }, FIXED, 'ko'),
        stillTotal: card({ ...COFF, flWhy: undefined }, FIXED, 'ko'),                       // 표시는 있지만 이 회사는 epsIn 없음 (총 순이익)
        pageNow: count(page(NOW, COFF.t), EPS), pageIcr: count(page(NOW, COFF.t), OF.FIX_ICR), pageFixed: count(page(FIXED, COFF.t), EPS),
        pageFixedIcr: count(page(FIXED, COFF.t), OF.FIX_ICR), html: page(NOW, COFF.t),
      };""", COFF=c_off, REREAD=reread(sam, "o"))
    assert eps_line() in got["ko"] and ICR in got["ko"], got["ko"]
    assert got["ko"].index(eps_line()) > next(i for i, l in enumerate(got["ko"]) if l.startswith("PER "))   # PER 줄 밑
    assert ICR in got["ko"][got["ko"].index("짚고 갈 재무 신호 1개가 있어요"):]                         # 재무 신호 밑
    assert eps_line() not in got["en"] and ICR not in got["en"]               # 영어 화면: Jack 이 영어 글을 승인할 때까지 없어요
    assert eps_line() not in got["fixed"] and ICR not in got["fixed"]         # 다시 읽기가 끝나면 둘 다 없어요 (이 회사 epsIn.b "o")
    assert eps_line() in got["stillTotal"]                                    # 표시가 있어도 그 회사가 총 순이익이면 줄은 그대로
    # 기업분석: 투자지표 · 업종 내 위치 · 주가 분해 · DCF (네 칸에 한 줄씩), 재무 신호 밑에 이자보상배율 한 줄
    assert got["pageNow"] == 4 and got["pageIcr"] == 1, (got["pageNow"], got["pageIcr"])
    assert got["pageFixed"] == 0 and got["pageFixedIcr"] == 0
    assert all(int(px) >= 12 for px in re.findall(r'data-fix="(?:eps|icr)" style="font-size:(\d+)px', got["html"]))


# ── 주가는 무엇으로 움직였나 · 지금 가격이 가정하는 것: 두 끝이 같은 기준 (코디네이터, 데이터 검토 2026-11-08) ──
# 다시 읽기 전 파일(지금): eps = 총 순이익 ÷ 보통주 → 3년 전 끝도 ni[2] ÷ shm (예전 식 그대로).
# 다시 읽은 뒤(epsIn · nio3): eps = 지배주주 순이익 ÷ (보통주 + 상장 우선주) → 3년 전 끝도 nio3[2] ÷ epsIn.sh ("s" 는 ni[2] ÷ epsIn.sh).
# "t" 이거나 필요한 칸이 없으면 숫자 없이 PER · EPS 줄만. 단위: ni · nio3 · epsIn.ni 는 억원, epsIn.sh 는 주식 수.
SAM_PREF = 815974664            # 삼성전자우 상장 주식 수 (보통주 5,846,278,608 + 우선주 = epsIn.sh)
SAM_NIO3 = [442609.56, 336213.63, 144734.01]   # 지배주주 순이익 (실제 발행본 epsNi3 와 같은 값, 억원)


def js(v):
    """숫자를 브라우저가 input 값으로 쓰는 모양으로 (452068.0 → '452068')."""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def reread(co, b, nio3=SAM_NIO3, sh=None, ni_ttm=450000.0):
    """다시 읽은 corp.json 의 모양 (지어낸 값): epsIn {ni, b, p, sh} · nio3 · 그 기준의 eps."""
    sh = sh if sh is not None else round(co["shm"] * 1e6) + SAM_PREF
    out = {"epsIn": {"ni": ni_ttm, "b": b, "p": "2026.2Q", "sh": sh}, "eps": round(ni_ttm * 1e8 / sh)}
    if nio3 is not None:
        out["nio3"] = nio3
    return out


def test_both_ends_of_the_split_and_the_reverse_dcf_share_one_basis():
    sam = company("005930")
    shapes = {"today": sam, "o": {**sam, **reread(sam, "o")}, "s": {**sam, **reread(sam, "s", nio3=None)}, "t": {**sam, **reread(sam, "t", nio3=None)},
              "oNoNio3": {**sam, **reread(sam, "o", nio3=None)}, "oNoThen": {**sam, **reread(sam, "o", nio3=SAM_NIO3[:2] + [None])},
              "oNoSh": {**sam, **reread(sam, "o"), "epsIn": {**reread(sam, "o")["epsIn"], "sh": None}}}
    got = run(bundle_dir(), """
      const K = B.K;
      out = Object.fromEntries(Object.entries(SHAPES).map(([k, co]) => {
        const s = { t: co.t, cls: 'kr', price: co.price, cap: co.cap };
        const d = K.decompose(co), old = OLD.decomposeReturn(co), g = K.impliedGrowth(s, co);
        return [k, { d, old, g, base0: RP.epsBase(co, 0), base2: RP.epsBase(co, 2),
          rev: g.ni0 != null && g.sharesM ? K.reverseDcf({ price: co.price, ni0: g.ni0, sharesM: g.sharesM, fade: true, disc: 10, term: 2 }) : null }];
      }));""", SHAPES=shapes)
    t = got["today"]
    then_today = sam["ni"][2] * 100 / sam["shm"]                                  # 지금 식 그대로: 총 순이익 ÷ 보통주
    assert abs(t["d"]["epsThen"] - then_today) < 1e-9 and abs(t["old"]["epsThen"] - then_today) < 1e-9
    assert abs(t["d"]["eF"] - sam["eps"] / then_today) < 1e-12 and abs(t["old"]["eF"] - t["d"]["eF"]) < 1e-12
    assert t["g"]["ni0"] == sam["ni"][0] and t["g"]["sharesM"] == sam["shm"] and t["base2"]["basis"] == "today"
    for k, ni in (("o", SAM_NIO3), ("s", sam["ni"])):
        x, co = got[k], shapes[k]
        sh = co["epsIn"]["sh"]
        then = ni[2] * 1e8 / sh
        assert abs(x["d"]["epsThen"] - then) < 1e-9 and abs(x["old"]["epsThen"] - then) < 1e-9, (k, x["d"], then)
        # 두 끝이 같은 순이익 기준 · 같은 주식 수: 3년 전 = 그해 순이익 ÷ sh, 지금 = 최근 순이익(epsIn.ni) ÷ sh
        assert abs(x["d"]["epsThen"] * sh / 1e8 - ni[2]) < 1e-6
        assert abs(x["d"]["epsNow"] * sh / 1e8 - co["epsIn"]["ni"]) < sh / 1e8        # eps 는 원 단위로 반올림돼 있어요
        assert abs(x["d"]["eF"] - co["eps"] / then) < 1e-12 and abs(x["old"]["eF"] - x["d"]["eF"]) < 1e-12
        assert abs(x["d"]["priceRatio"] - x["d"]["eF"] * x["d"]["mF"]) < 1e-9        # 참인 곱셈 그대로
        assert abs(x["d"]["perThen"] * x["d"]["epsThen"] - x["d"]["priceThen"]) < 1e-6    # 눈높이도 같은 기준
        # 지금 가격이 가정하는 것: 시작 순이익과 주식 수도 같은 기준
        assert x["g"]["ni0"] == ni[0] and abs(x["g"]["sharesM"] - sh / 1e6) < 1e-12, (k, x["g"])
        assert x["g"].get("g") == x["rev"].get("g") and x["g"].get("edge") == x["rev"].get("edge"), (k, x["g"], x["rev"])
        assert x["base0"]["basis"] == k and x["base2"]["basis"] == k
    # 같은 기준이 없으면 숫자를 만들지 않아요 (섞지 않아요)
    for k in ("t", "oNoNio3", "oNoSh"):
        assert got[k]["d"] == {"why": "basis"} and got[k]["old"] == {"why": "basis"} and got[k]["g"] == {"why": "basis"}, (k, got[k])
    assert got["oNoThen"]["d"] == {"why": "basis"} and got["oNoThen"]["old"] == {"why": "basis"}     # 3년 전 지배주주 순이익이 없어요
    assert got["oNoThen"]["g"]["ni0"] == SAM_NIO3[0]                              # 시작 순이익(올해)은 있어요
    # 예전 식으로 섞으면 얼마나 틀리는지 (이 PR 이 막는 것): 3년 전 끝이 총 순이익 ÷ 보통주면 이익 배율이 달라져요
    mixed = shapes["o"]["eps"] / then_today
    assert abs(mixed / got["o"]["d"]["eF"] - 1) > 0.05


def test_old_app_cards_follow_the_same_basis_and_show_the_line_in_place_of_numbers():
    sam = company("005930")
    o = {**sam, **reread(sam, "o")}
    tt = {**sam, **reread(sam, "t", nio3=None)}
    got = run(bundle_dir(), """
      const page = (data, t) => renderToStaticMarkup(h(OLD.CompanyView, { data, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const with_ = (co, live) => ({ ...CORP, ...(live ? { epsBasis: 'owners' } : {}), companies: CORP.companies.map((x) => (x.t === co.t ? co : x)) });
      const EPS = OF.fixEpsText();
      const view = (co, live) => { const html = page(with_(co, live), co.t);
        const nums = [...html.matchAll(/<input[^>]*type="number"[^>]*value="([^"]*)"/g)].map((m) => m[1]);
        return { eps: count(html, EPS), split: lines(html).includes('이익(EPS) 변화'), lossText: lines(html).some((l) => l.includes('적자 구간이 있어서')),
          inputs: nums, then: (lines(html).map((l) => /^([\\d,]+)원 → ([\\d,]+)원$/.exec(l)).find(Boolean) || []).slice(1) }; };
      out = { today: view(SAM, false), o: view(O, true), t: view(T, true), tNow: view(T, false) };""", SAM=sam, O=o, T=tt)
    # 지금 발행: 숫자와 함께 네 칸에 한 줄씩 (투자지표 · 업종 내 위치 · 주가 분해 · DCF), 시작 순이익 = ni[0], 주식 수 = 보통주
    assert got["today"]["split"] and got["today"]["eps"] == 4 and got["today"]["inputs"][:2] == [js(sam["ni"][0]), js(round(sam["shm"], 1))], got["today"]
    # 다시 읽은 뒤 "o": 숫자는 지배주주 기준, 줄은 없어요
    sh = o["epsIn"]["sh"]
    assert got["o"]["split"] and got["o"]["eps"] == 0, got["o"]
    assert got["o"]["inputs"][:2] == [js(SAM_NIO3[0]), js(round(sh / 1e6 * 10) / 10)], got["o"]["inputs"]
    assert got["o"]["then"][0] == f"{round(SAM_NIO3[2] * 1e8 / sh):,}", got["o"]["then"]
    # "t": 주가 분해는 숫자 · '적자 구간' 문장 없이 줄만, DCF 는 채우지 않고 줄 — 투자지표 · 업종 내 위치도 줄 (총 순이익이라)
    assert not got["t"]["split"] and not got["t"]["lossText"] and got["t"]["eps"] == 4, got["t"]
    assert got["t"]["inputs"][:2] == ["", ""], got["t"]["inputs"]
    assert not got["tNow"]["split"] and got["tNow"]["eps"] == 4


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
