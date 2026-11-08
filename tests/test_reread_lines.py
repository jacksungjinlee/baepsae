# -*- coding: utf-8 -*-
"""DART 다시 읽기가 끝난 뒤의 세 가지 (Jack 승인 2026-11-08, DeepL 확인) — src/repair.js · src/v2/fix.js · src/v2/fixnote.jsx ·
src/fixnote.jsx.

1. 한 주 동안의 안내 (2.0 홈 · 포트폴리오): "{date}부터 EPS와 ROE를 지배주주 몫으로 계산해요. 일부 규칙의 결과가 바뀔 수 있어요."
   화면의 corp.json 에 epsBasis "owners" 가 있고 오늘(한국 시간)이 EPS_FIX_DATE + 7일 전일 때만. {date} = EPS_FIX_DATE ("11월 10일").
   표시가 없으면 · 그날부터 · 미리 보기(app-preview.html)에서는 없어요.
2. 원화가 아닌 재무제표 (corp.json stmtCur, 예: "USD"): "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직
   보여 드리지 않아요." 2.0 회사 페이지(요약의 한눈에 · 실적 탭 · 가치 탭 · 두 자세히 화면)에 한 번씩, 예전 뱁새 기업분석의 투자지표에
   한 번. stmtCur 가 없는 회사 · 미국 종목에는 없어요.
3. 예전 뱁새 영어 화면의 고치는 중 줄: "PER and EPS are being recalculated and may change on {date}." · "Interest coverage isn't
   checked while we fix how it's calculated." 한국어 줄과 같은 규칙, 날짜는 data.js mdOf(…, "en") ("Nov 10").
화면은 react-dom/server 로 실제 컴포넌트를 그려서 봐요. 브라우저 화면은 tests/smoke_v2.py 장면 '다시 읽은 뒤'가 봐요.
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
MODS = {"RP": "src/repair.js", "FX": "src/v2/fix.js", "FN": "src/v2/fixnote.jsx", "L": "src/v2/load.js", "T": "src/v2/today.jsx",
        "PF": "src/v2/portfolio.jsx", "CO": "src/v2/company.jsx", "CP": "src/copy/v2.js", "OF": "src/fixnote.jsx", "OLD": "src/corp.jsx",
        "SH": "src/shell.jsx", "D": "src/data.js", "FM": "src/v2/format.js", "K": "src/v2/company.js", "W": "src/v2/warn.js", "PFN": "src/v2/pf.js", "E": "src/v2/engine.js"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
OWNERS = "{date}부터 EPS와 ROE를 지배주주 몫으로 계산해요. 일부 규칙의 결과가 바뀔 수 있어요."
CUR = "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직 보여 드리지 않아요."
EPS_EN = "PER and EPS are being recalculated and may change on {date}."
ICR_EN = "Interest coverage isn't checked while we fix how it's calculated."
EPS_KO = "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요."
ICR_KO = "이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지 않아요."
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
STMT_T = "241560"           # 두산밥캣: 실제로 재무제표를 달러로 공시하는 회사 (시험 데이터에 있어요)


def fix_date():
    src = open(os.path.join(ROOT, "src", "repair.js"), encoding="utf-8").read()
    m = re.findall(r'^export const EPS_FIX_DATE = "(\d{4})-(\d{2})-(\d{2})";$', src, flags=re.M)
    assert len(m) == 1, m
    return m[0]


def owners_line():
    y, mo, d = fix_date()
    return OWNERS.format(date=f"{int(mo)}월 {int(d)}일")


def eps_en_line():
    y, mo, d = fix_date()
    return EPS_EN.format(date=f"{MON[int(mo) - 1]} {int(d)}")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def blank_stmt_cur(data, corp, t=STMT_T, cur="USD"):
    """다시 읽은 발행에서 재무제표가 원화가 아닌 회사의 모양 (fetch_data.py v19.1f 처럼): 금액 · 영수증 · PER · PBR · EPS · BPS 를 비우고
    stmtCur 에 통화를 남겨요 (배당은 원화 표라 남아요)."""
    co = next(c for c in corp["companies"] if c["t"] == t)
    co.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False, per=None, pbr=None, eps=None, bps=None)
    for k in ("evE", "evR", "pcf", "bq", "cash3", "eps3r", "epsNi3", "epsB", "nio3", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep"):
        co.pop(k, None)
    if cur is not None:
        co["stmtCur"] = cur
    s = next(x for x in data["stocks"] if x["t"] == t)
    s.update(per=None, pbr=None, eps=None, bps=None, vz=None)
    return co, s


def run(body, **data):
    """body 는 out 에 JSON 으로 돌려줄 값을 넣어요. FILES: 시험 데이터 네 파일, mkLoad(files, nowMs, opts): 2.0 의 load 상태."""
    tmp = bundle_dir()
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react'; import fs from 'fs';\n"
            "const { RP, FX, FN, L, T, PF, CO, CP, OF, OLD, SH, D, FM, K, W, PFN } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};\n"
            f"const FIXDIR = {json.dumps(FIX)};\n"
            "const read = (f) => JSON.parse(fs.readFileSync(FIXDIR + '/' + f, 'utf8'));\n"
            "const kstMs = (iso, hm = '12:00') => Date.parse(iso + 'T' + hm + ':00+09:00');\n"
            "const realNow = Date.now; const at = (ms) => { Date.now = () => ms; };\n"
            "const mkLoad = (files, ms, opts = {}) => { for (const f of ['data', 'corp', 'macro']) files[f].publishedAt = new Date(ms - 3600000).toISOString();\n"
            "  return L.resolveLoad({ data: { ok: true, data: files.data }, corp: { ok: true, data: files.corp }, macro: { ok: true, data: files.macro } }, ms, opts); };\n"
            "const FILES = () => ({ data: read('data.json'), corp: read('corp.json'), macro: read('macro.json') });\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const count = (html, text) => lines(html).filter((l) => l === text).length;\n"
            "const marked = (html, attr, val) => (html.match(new RegExp(attr + '=\"' + val + '\"', 'g')) || []).length;\n"
            "const px = (html, attr, val) => [...html.matchAll(new RegExp(attr + '=\"' + val + '\"[^>]*style=\"[^\"]*font-size:(\\\\d+(?:\\\\.\\\\d+)?)px', 'g'))].map((m) => Number(m[1]));\n"
            + decl + "let out;\n" + body + "\nDate.now = realNow;\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)            # 시험 데이터를 통째로 넘기면 명령 줄에 다 들어가지 않아요
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


# ── 1. 한 주 동안의 안내: 규칙 ──
def test_the_week_notice_rule_reads_the_marker_and_the_date():
    got = run("""
      const D0 = RP.EPS_FIX_DATE, P = (n) => RP.isoPlusDays(D0, n), LIVE = { epsBasis: 'owners' };
      out = {
        days: RP.EPS_NOTICE_DAYS, d0: D0, end: P(RP.EPS_NOTICE_DAYS),
        plus: [RP.isoPlusDays('2026-11-09', 7), RP.isoPlusDays('2026-12-28', 7), RP.isoPlusDays('2028-02-27', 3), RP.isoPlusDays('2027-02-27', 3),
          RP.isoPlusDays('2026-11-09', -1), RP.isoPlusDays('2026-11-09', 0)],
        bad: [RP.isoPlusDays('2026-02-30', 1), RP.isoPlusDays('2026-11-9', 1), RP.isoPlusDays('2026-11-09T00:00', 1), RP.isoPlusDays(null, 1),
          RP.isoPlusDays('2026-11-09', 1.5), RP.isoPlusDays('2026-11-09', '7'), RP.isoPlusDays('2026-13-01', 1)],
        live: [P(-1), D0, P(1), P(6), P(7), P(8), P(30)].map((d) => RP.epsNoticeOn(LIVE, d)),
        off: [null, undefined, {}, { epsBasis: 'total' }, { epsBasis: 'Owners' }, [], 'owners'].map((c) => RP.epsNoticeOn(c, P(1))),
        today: [null, '', 'tomorrow', P(1) + 'T00:00', D0.replace(/-/g, '/')].map((d) => RP.epsNoticeOn(LIVE, d)),
        other: [RP.epsNoticeOn(LIVE, '2026-12-07', '2026-12-01'), RP.epsNoticeOn(LIVE, '2026-12-08', '2026-12-01'), RP.epsNoticeOn(LIVE, D0, 'soon')],
      };""")
    y, mo, d = fix_date()
    assert got["days"] == 7 and got["d0"] == f"{y}-{mo}-{d}"
    assert got["plus"] == ["2026-11-16", "2027-01-04", "2028-03-01", "2027-03-02", "2026-11-08", "2026-11-09"]
    assert got["bad"] == [None] * 7                                       # 없는 날짜 · 다른 꼴은 날짜를 만들지 않아요
    assert got["live"] == [True, True, True, True, False, False, False]    # EPS_FIX_DATE + 7일 전까지만 (그날부터 없어요)
    assert got["off"] == [False] * 7                                      # 정확히 epsBasis "owners" 일 때만
    assert got["today"] == [False] * 5                                    # 오늘을 읽을 수 없으면 없어요
    assert got["other"] == [True, False, False]                           # 날짜는 EPS_FIX_DATE 하나에서 (바뀌면 따라가요)


# ── 1. 한 주 동안의 안내: 2.0 의 한 줄 ──
def test_the_week_notice_line_on_2_0_follows_the_load_on_screen():
    got = run("""
      const D0 = RP.EPS_FIX_DATE, P = (n) => RP.isoPlusDays(D0, n);
      const note = (load, ms) => renderToStaticMarkup(h(FN.EpsOwnersNote, { load, now: ms }));
      const live = (ms) => { const f = FILES(); f.corp.epsBasis = 'owners'; return mkLoad(f, ms); };
      const none = (ms) => { const f = FILES(); delete f.corp.epsBasis; return mkLoad(f, ms); };
      const t0 = kstMs(D0), last = kstMs(P(6), '23:59'), end = kstMs(P(7), '00:00'), endUtcTrap = kstMs(P(7), '00:30');
      const L1 = live(t0);
      const html = note(L1, t0);
      const pv = (() => { const f = FILES(); f.corp.epsBasis = 'owners'; return mkLoad(f, t0, { preview: true }); })();
      FX.setEpsBasis({ epsBasis: 'owners', companies: [] });              // the page-wide flag back on: the load's own preview mark must hide it
      out = {
        text: FN.epsOwnersText(), copy: C2.fix.owners, line: lines(html), marked: marked(html, 'data-ui-v2', 'eps-owners'), px: px(html, 'data-ui-v2', 'eps-owners'),
        before: lines(note(live(kstMs(P(-1))), kstMs(P(-1)))), last: lines(note(live(last), last)),
        end: note(live(end), end), utc: note(live(endUtcTrap), endUtcTrap), later: note(live(kstMs(P(30))), kstMs(P(30))),
        noMarker: note(none(t0), t0), preview: note(pv, t0), fail: note({ status: 'fail' }, t0), loading: note({ status: 'loading' }, t0), nul: note(null, t0),
        notOk: note({ status: 'loading', corp: { epsBasis: 'owners', companies: [] } }, t0),          // only a load that is on screen counts
        shown: [FX.epsNoticeShown(L1, D0), FX.epsNoticeShown(L1, P(7)), FX.epsNoticeShown(pv, D0)],
      };
      FX.setEpsBasis({ epsBasis: 'owners', companies: [] }, { preview: true });       // 미리 보기 페이지: 어느 안내도 없어요
      out.hiddenPage = note(L1, t0);
      FX.setEpsBasis({ epsBasis: 'owners', companies: [] });
      out.backOn = lines(note(L1, t0));""")
    want = owners_line()
    assert got["copy"] == OWNERS and got["text"] == want                   # Jack 의 글자 그대로 · 날짜는 월 · 일 ("11월 10일")
    assert got["line"] == [want] and got["marked"] == 1                     # 한 줄
    assert got["px"] and all(p >= 12 for p in got["px"]), got["px"]          # 12px 바닥 (조용한 안내 줄: 13px)
    assert got["before"] == [want] and got["last"] == [want]                # 표시가 있으면 그날 전에도 · 이레째 밤 23:59 까지
    assert got["end"] == "" and got["utc"] == "" and got["later"] == ""      # 이레가 지나면 (한국 시간 자정부터, UTC 날짜가 아니에요)
    assert got["noMarker"] == "" and got["preview"] == "" and got["fail"] == "" and got["loading"] == "" and got["nul"] == "" and got["notOk"] == ""
    assert got["shown"] == [True, False, False]
    assert got["hiddenPage"] == "" and got["backOn"] == [want]


def test_the_week_notice_is_one_line_near_the_top_of_home_and_portfolio():
    """홈(첫 방문 · 처음 안내 · 돌아온 사람)과 포트폴리오(빈 화면 · 포트폴리오가 있을 때): 날짜 줄 바로 밑, 화면의 첫 카드보다 위에 한 줄.
    표시가 없거나 · 이레가 지났거나 · 미리 보기면 없어요."""
    deck = {"id": "dfix", "name": "가진 종목", "createdAt": "2026-10-30", "kind": "imported", "settings": {"points": {"value": 2}, "strict": "normal"},
            "holdings": [{"t": "005930", "nk": "삼성전자", "cls": "kr"}], "purchases": [],
            "imported": [{"t": "005930", "nk": "삼성전자", "ccy": "KRW", "qty": 10}]}
    got = run("""
      const D0 = RP.EPS_FIX_DATE, P = (n) => RP.isoPlusDays(D0, n);
      const loadAt = (ms, marker = true, opts = {}) => { const f = FILES(); if (marker) f.corp.epsBasis = 'owners'; else delete f.corp.epsBasis; return mkLoad(f, ms, opts); };
      const store = (decks) => ({ data: { v: 2, decks }, writable: true, key: 'baepsae2.v1', preview: false });
      const noop = () => {};
      const screens = (load) => ({
        homeFirst: renderToStaticMarkup(h(T.Home, { load, store: store([]), setStoreData: noop, pad: 0, go: noop, onWhy: noop })),
        homeWelcome: renderToStaticMarkup(h(T.Home, { load, store: store([]), setStoreData: noop, pad: 0, go: noop, onWhy: noop,
          welcome: { onTry: noop, onBrowse: noop, onImport: noop } })),
        home: renderToStaticMarkup(h(T.Home, { load, store: store([DECK]), setStoreData: noop, pad: 0, go: noop, onWhy: noop })),
        pfEmpty: renderToStaticMarkup(h(PF.Portfolio, { load, store: store([]), setStoreData: noop, pad: 0, go: noop })),
        pf: renderToStaticMarkup(h(PF.Portfolio, { load, store: store([DECK]), setStoreData: noop, pad: 0, go: noop })),
      });
      const look = (ms, marker, opts) => { at(ms); const s = screens(loadAt(ms, marker, opts)); return Object.fromEntries(Object.entries(s).map(([k, html]) => {
        const i = html.indexOf('data-ui-v2="eps-owners"'), dl = html.indexOf('data-ui-v2="date-line"');
        // the marked pieces after the date line, in order: the notice must be the first (before the screen's first card)
        const after = [...html.matchAll(/data-ui-v2="([^"]+)"/g)].filter((m) => m.index > dl).map((m) => m[1]);
        return [k, { n: marked(html, 'data-ui-v2', 'eps-owners'), lines: lines(html).filter((l) => l === OWNERS_LINE).length, afterDate: i > dl && dl >= 0,
          next: after.slice(0, 2), home2: html.includes('data-ui-v2="home2"') }];
      })); };
      out = { on: look(kstMs(P(1)), true), end: look(kstMs(P(7), '00:00'), true), none: look(kstMs(P(1)), false), pv: look(kstMs(P(1)), true, { preview: true }) };""",
              DECK=deck, OWNERS_LINE=owners_line())
    on = got["on"]
    assert set(on) == {"homeFirst", "homeWelcome", "home", "pfEmpty", "pf"}
    assert on["home"]["home2"], "돌아온 사람의 홈은 v19.3e 새 홈이에요 (HOME2)"
    for k, v in on.items():
        assert v["n"] == 1 and v["lines"] == 1, (k, v)                     # 화면마다 한 줄
        assert v["afterDate"] and v["next"][0] == "eps-owners", (k, v)     # 날짜 줄 바로 밑 · 첫 카드 위 (위쪽의 조용한 한 줄)
    assert [on[k]["next"][1] for k in ("homeFirst", "homeWelcome", "home", "pfEmpty")] == ["home-hero", "guide-welcome", "home-block", "deck-empty"]
    for case in ("end", "none", "pv"):
        assert all(v["n"] == 0 and v["lines"] == 0 for v in got[case].values()), (case, got[case])


# ── 2. 원화가 아닌 재무제표 ──
def test_the_currency_code_rule():
    got = run("""
      const cos = [{ t: 'a', stmtCur: 'USD' }, { t: 'b', stmtCur: 'JPY' }, { t: 'c', stmtCur: 'KRW' }, { t: 'd', stmtCur: 'usd' }, { t: 'e', stmtCur: 'US$' },
        { t: 'f', stmtCur: '' }, { t: 'g', stmtCur: 1 }, { t: 'h' }, { t: 'i', stmtCur: null }, null, 'USD', { t: 'j', stmtCur: 'USDT' }];
      const of = cos.map(RP.stmtCurOf);
      const w0 = warns.length;
      const warned = cos.map((c) => RP.warnStmtCur(c, 'test'));
      const again = cos.map((c) => RP.warnStmtCur(c, 'test'));
      const KR = { t: 'k', cls: 'kr' }, US = { t: 'AAPL', cls: 'us' }, FUND = { t: 'f', cls: 'bond' };
      out = { of, warned, again, msgs: warns.slice(w0),
        for: [FX.stmtCurFor(KR, { stmtCur: 'USD' }), FX.stmtCurFor(US, { stmtCur: 'USD' }), FX.stmtCurFor(FUND, { stmtCur: 'USD' }), FX.stmtCurFor(KR, {}),
          FX.stmtCurFor(KR, null), FX.stmtCurFor(null, { stmtCur: 'USD' }), FX.stmtCurFor({ t: 'k' }, { stmtCur: 'USD' })],
        text: FN.stmtCurText(KR, { stmtCur: 'USD' }), textUs: FN.stmtCurText(US, { stmtCur: 'USD' }), copy: C2.co.stmtCur, old: OF.FIX_STMT_CUR,
        oldText: OF.stmtCurLineText({ t: 'k', stmtCur: 'EUR' }), oldNone: OF.stmtCurLineText({ t: 'k' }) };""")
    assert got["of"] == ["USD", "JPY", None, None, None, None, None, None, None, None, None, None]   # 세 글자 대문자 코드, KRW 는 아니에요
    assert got["warned"] == [False, False, True, True, True, True, True, False, False, False, False, True]   # 쓸 수 없는 값은 console 에 크게
    assert got["again"] == [False] * 12                                     # 한 번만
    assert all("!!" in m and "stmtCur" in m for m in got["msgs"]), got["msgs"]
    assert got["for"] == ["USD", None, None, None, None, None, None]        # 한국 종목만 (미국 · 펀드 · cls 없음: 없어요)
    assert got["copy"] == CUR and got["old"] == CUR                          # Jack 의 글자 그대로, 두 앱이 같아요
    assert got["text"] == CUR.format(currency="USD") and got["textUs"] is None
    assert got["oldText"] == CUR.format(currency="EUR") and got["oldNone"] is None


def test_the_currency_line_on_the_2_0_company_page_exactly_for_stmt_cur_companies():
    """2.0 회사 페이지: stmtCur 가 있는 한국 회사에만, 요약(한눈에 칸 위) · 실적 탭 · 가치 탭 · 실적 자세히 · 가치 자세히에 한 번씩. 배당 탭과
    다른 회사(삼성전자) · 미국 종목(AAPL, 회사 줄에 stmtCur 를 일부러 넣어도)에는 없어요."""
    data, corp = fixture("data.json"), fixture("corp.json")
    blank_stmt_cur(data, corp)
    got = run("""
      const D0 = RP.EPS_FIX_DATE, ms = kstMs(RP.isoPlusDays(D0, 1));
      at(ms);
      const f = { data: DATA, corp: CORP, macro: read('macro.json') };
      const load = mkLoad(f, ms);
      load.coByT.set('AAPL', { t: 'AAPL', stmtCur: 'USD' });             // 미국 종목: 회사 줄에 있어도 없어요
      const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };
      const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };
      const page = (code, ctab) => renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code, ctab: ctab || null, disc: null, nav }));
      const look = (code) => Object.fromEntries([null, 'earn', 'value', 'div', 'earn-more', 'value-more'].map((ctab) => {
        const html = page(code, ctab);
        const i = html.indexOf('data-ui-v2="stmt-cur"');
        return [ctab || 'summary', { n: marked(html, 'data-ui-v2', 'stmt-cur'), lines: lines(html).filter((l) => l === LINE).length,
          cur: (/data-ui-v2="stmt-cur" data-cur="([^"]*)"/.exec(html) || [])[1] || null, px: px(html, 'data-ui-v2', 'stmt-cur'),
          beforeTiles: i < 0 ? null : i < html.indexOf('data-ui-v2="co-tile"'), inEarnCard: i < 0 ? null : i > html.indexOf('data-ui-v2="co-earn"'),
          inValueCard: i < 0 ? null : i > html.indexOf('data-ui-v2="co-value"') && i < html.indexOf('data-ui-v2="co-risk"'),
          tilesNa: lines(html).filter((l) => l === C2.co.tiles.na).length }];
      }));
      out = { stmt: look(STMT_T), sam: look('005930'), us: look('AAPL') };""", DATA=data, CORP=corp, STMT_T=STMT_T, LINE=CUR.format(currency="USD"))
    s = got["stmt"]
    for tab in ("summary", "earn", "value", "earn-more", "value-more"):
        assert s[tab]["n"] == 1 and s[tab]["lines"] == 1 and s[tab]["cur"] == "USD", (tab, s[tab])   # 숫자가 있을 자리마다 한 번
        assert all(p >= 12 for p in s[tab]["px"]) and s[tab]["px"], (tab, s[tab]["px"])
    assert s["summary"]["beforeTiles"] is True and s["summary"]["tilesNa"] == 0, s["summary"]   # 남은 칸(배당 · 출렁임) 위에 이유, '자료가 없어요' 칸 없음
    assert s["earn"]["inEarnCard"] is True and s["value"]["inValueCard"] is True
    assert s["div"]["n"] == 0                                                 # 배당은 원화 표라 그대로예요
    for who in ("sam", "us"):
        assert all(v["n"] == 0 and v["lines"] == 0 for v in got[who].values()), (who, got[who])


def test_the_currency_line_in_the_old_company_page():
    data, corp = fixture("data.json"), fixture("corp.json")
    co, _ = blank_stmt_cur(data, corp)
    got = run("""
      const page = (cos, t) => renderToStaticMarkup(h(OLD.CompanyView, { data: { ...BASE, companies: cos }, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const withCur = page(BASE.companies, STMT_T);
      const noCur = page(BASE.companies.map((c) => (c.t === STMT_T ? { ...c, stmtCur: undefined } : c)), STMT_T);
      const sam = page(BASE.companies, '005930');
      const LL = lines(withCur);
      out = { n: marked(withCur, 'data-fix', 'stmt-cur'), lines: LL.filter((l) => l === LINE).length, at: LL.indexOf(LINE), head: LL.indexOf('투자지표'),
        per: LL.indexOf('PER'), px: px(withCur, 'data-fix', 'stmt-cur'), noCur: marked(noCur, 'data-fix', 'stmt-cur'), sam: marked(sam, 'data-fix', 'stmt-cur') };""",
              BASE=corp, STMT_T=STMT_T, LINE=CUR.format(currency="USD"))
    assert got["n"] == 1 and got["lines"] == 1, got                            # 기업분석에 한 번
    assert got["head"] >= 0 and got["head"] < got["at"] < got["per"], got     # 투자지표 제목 밑, 비어 있는 PER 칸 위
    assert got["px"] and all(p >= 12 for p in got["px"]), got["px"]
    assert got["noCur"] == 0 and got["sam"] == 0



def test_stmt_cur_2_0_company_page_hides_what_would_be_untrue_or_empty():
    """stmtCur 회사 (Jack 의 코디네이터, 2026-11-08 — 숨기기만, 새 글 없음): 요약은 '자료가 없어요' 뿐인 실적 · 가치 칸을 빼요. 실적 탭은
    통화 줄만 (매출 · 영업이익 · 순이익 고르기 · 사업보고서 기준 줄 · 주가는 무엇으로 움직였나 · 실적 자세히 링크 없음). 가치 탭은 보이지 않는
    PER · PBR 의 기준 줄 · 날짜 줄 · 가치 자세히 링크가 없어요 (출렁임 카드는 그대로). 실적 자세히(주소로 열면)는 '–' 표 없이 통화 줄만.
    같은 빈 숫자라도 stmtCur 가 없으면 예전 그대로예요 (숨김은 stmtCur 로만 정해요)."""
    data, corp = fixture("data.json"), fixture("corp.json")
    blank_stmt_cur(data, corp)
    nocur = json.loads(json.dumps(corp))
    next(c for c in nocur["companies"] if c["t"] == STMT_T).pop("stmtCur")
    got = run("""
      const ms = kstMs(RP.isoPlusDays(RP.EPS_FIX_DATE, 1)); at(ms);
      const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };
      const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };
      const YEAR = (fy) => C2.app.reportYear.replace('{year}', fy);
      const look = (corp, code) => {
        const load = mkLoad({ data: JSON.parse(JSON.stringify(DATA)), corp: JSON.parse(JSON.stringify(corp)), macro: read('macro.json') }, ms);
        const fy = load.coByT.get(code).fy;
        const page = (ctab) => renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code, ctab, disc: null, nav }));
        const sum = page(null), earn = page('earn'), value = page('value'), em = page('earn-more'), vm = page('value-more');
        const val = value.slice(value.indexOf('data-ui-v2="co-value"'));
        return {
          tiles: [...sum.matchAll(/data-ui-v2="co-tile" data-topic="([a-z]+)"/g)].map((m) => m[1]),
          na: lines(sum).filter((l) => l === C2.co.tiles.na).length,
          earn: { seg: marked(earn, 'data-ui', 'segmented'), year: lines(earn).filter((l) => l === YEAR(fy)).length, decomp: marked(earn, 'data-ui-v2', 'co-decomp'),
            more: marked(earn, 'data-ui-v2', 'co-earn-more'), cur: marked(earn, 'data-ui-v2', 'stmt-cur') },
          value: { basis: marked(value, 'data-ui-v2', 'co-value-basis'), date: marked(val, 'data-ui-v2', 'date-line'), more: marked(value, 'data-ui-v2', 'co-value-more'),
            risk: marked(value, 'data-ui-v2', 'co-risk'), cur: marked(value, 'data-ui-v2', 'stmt-cur') },
          earnMore: { table: (em.match(/role="table"/g) || []).length, note: lines(em).filter((l) => l === C2.co.earn.marginNote).length,
            year: lines(em).filter((l) => l === YEAR(fy)).length, cur: marked(em, 'data-ui-v2', 'stmt-cur') },
          valueMore: { cur: marked(vm, 'data-ui-v2', 'stmt-cur'), ratios: marked(vm, 'data-ui-v2', 'co-ratios') },
        };
      };
      out = { cur: look(CUR, STMT_T), nocur: look(NOCUR, STMT_T), sam: look(CUR, '005930') };""",
              DATA=data, CUR=corp, NOCUR=nocur, STMT_T=STMT_T)
    c, n, sam = got["cur"], got["nocur"], got["sam"]
    assert c["tiles"] == ["div", "risk"] and c["na"] == 0, c                               # 실적 · 가치 칸 없음
    assert n["tiles"] == ["earn", "value", "div", "risk"] and n["na"] == 2, n                # stmtCur 가 없으면 예전 그대로
    assert c["earn"] == {"seg": 0, "year": 0, "decomp": 0, "more": 0, "cur": 1}, c["earn"]  # 실적 탭: 통화 줄만
    assert n["earn"]["seg"] == 1 and n["earn"]["year"] == 1 and n["earn"]["decomp"] == 1 and n["earn"]["more"] == 1 and n["earn"]["cur"] == 0, n["earn"]
    assert c["value"] == {"basis": 0, "date": 0, "more": 0, "risk": 1, "cur": 1}, c["value"]  # 가치 탭: 보이지 않는 PER · PBR 의 기준 · 날짜 줄 없음
    assert n["value"]["basis"] == 1 and n["value"]["date"] >= 1 and n["value"]["more"] == 1 and n["value"]["cur"] == 0, n["value"]
    assert sam["value"]["basis"] == 1 and sam["value"]["date"] >= 1 and sam["earn"]["seg"] == 1 and sam["tiles"] == ["earn", "value", "div", "risk"]
    assert c["earnMore"] == {"table": 0, "note": 0, "year": 0, "cur": 1}, c["earnMore"]      # 실적 자세히: '–' 표 없이 통화 줄만
    assert n["earnMore"]["table"] == 1 and n["earnMore"]["cur"] == 0
    assert c["valueMore"] == {"cur": 1, "ratios": 0}


def test_stmt_cur_old_company_page_hides_untrue_captions_and_empty_sections():
    """예전 뱁새 기업분석, stmtCur 회사: 통화 줄이 이유를 말하니 '적자이거나 데이터가 없어요' 같은 칸 설명 · 보이지 않는 PER 의 기간
    (' · 직전 사업보고서') · 숫자 없는 3개년 실적 흐름('파이프라인이 사업보고서를 못 찾은 종목이에요') · 주가는 무엇으로 움직였나('적자 구간이
    있어서')는 없어요. 숫자가 있는 칸(ROE · 배당)의 글, 업종 내 위치, 가정으로 계산하는 가치는 그대로. 금융업의 '금융업은 미적용 지표예요'는
    참이라 남아요. stmtCur 가 없으면 예전 그대로예요."""
    data, corp = fixture("data.json"), fixture("corp.json")
    blank_stmt_cur(data, corp)
    untrue = ["적자이거나 데이터가 없어요", "데이터가 없어요", "차입금·상각비 데이터 부족", "현금흐름 데이터가 없어요", "배당이 없거나 이익 데이터가 없어요",
              "재무제표 데이터가 아직 없어요. (파이프라인이 사업보고서를 못 찾은 종목이에요)", "3개년 실적 흐름", "주가는 무엇으로 움직였나"]
    got = run("""
      const page = (cos, t) => lines(renderToStaticMarkup(h(OLD.CompanyView, { data: { ...BASE, companies: cos }, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} })));
      const swap = (f) => BASE.companies.map((c) => (c.t === STMT_T ? f(c) : c));
      out = { cur: page(BASE.companies, STMT_T), nocur: page(swap((c) => ({ ...c, stmtCur: undefined })), STMT_T),
        bank: page(swap((c) => ({ ...c, s: 'bank' })), STMT_T), sam: page(BASE.companies, '005930'),
        roeNull: page(swap((c) => ({ ...c, roe: null })), STMT_T), roeNullNoCur: page(swap((c) => ({ ...c, roe: null, stmtCur: undefined })), STMT_T) };""", BASE=corp, STMT_T=STMT_T)
    cur, nocur, bank, sam = got["cur"], got["nocur"], got["bank"], got["sam"]
    line = CUR.format(currency="USD")
    assert cur.count(line) == 1 and "투자지표" in cur
    hits = [u for u in untrue if u in cur] + [l for l in cur if "적자 구간이 있어서" in l]
    assert not hits, hits                                                                 # 맞지 않는 이유 · 빈 칸이 없어요
    assert "밸류에이션 멀티플 · 업종 사분위 대비" in cur and not any("직전 사업보고서" in l or "최근 4개분기" in l for l in cur), [l for l in cur if "밸류에이션" in l]
    roe = next(c for c in corp["companies"] if c["t"] == STMT_T)["roe"]
    assert roe is not None and f"주주 돈 100원으로 연 {roe}원" in cur                       # 숫자가 있는 칸의 글은 그대로
    assert "업종 내 위치" in cur and "가정으로 계산하는 가치" in cur
    # stmtCur 가 없으면 예전 그대로 (같은 빈 숫자라도): 이 시험이 무엇을 숨기는지 보여 줘요
    assert all(u in nocur for u in untrue) and any("적자 구간이 있어서" in l for l in nocur), [u for u in untrue if u not in nocur]
    assert "밸류에이션 멀티플 · 업종 사분위 대비 · 직전 사업보고서" in nocur and line not in nocur
    assert "금융업은 미적용 지표예요" in bank and bank.count(line) == 1                       # 참인 설명은 남아요
    assert got["roeNull"].count("데이터가 없어요") == 0 and got["roeNullNoCur"].count("데이터가 없어요") == 2   # ROE 칸이 비어도 (PBR · ROE)
    assert "밸류에이션 멀티플 · 업종 사분위 대비 · 최근 4개분기 합산(2026.2Q)" in sam and "3개년 실적 흐름" in sam and "주가는 무엇으로 움직였나" in sam



# ── 이자를 내지 않은 회사 (DART 다시 읽기 v19.1f, Jack 2026-11-08: corp.json flSrc.int0) ──
# 낸 이자가 0 이면 이자보상배율 경고를 하지 않아요 (영업손실이어도). 확인은 돌았고(flRan 에 icr, 경고 없음) flSrc = {"icr": "is"|"cf",
# "int0": true}. 그런 회사에 '이자보상배율 1배 이상'이라고 말하면 틀려요 (이자가 없으면 배율도 없어요): 칩이 없어요. '재무 경고 0개' ·
# '재무 경고 신호는 없어요'는 참이라 그대로예요 (경고가 날 수 없었어요 — 회사 페이지와 가진 종목 규칙 칸이 같은 말을 해요).
# 예전 뱁새는 걸린 신호만 보여 주고 '확인했어요'라고 말하지 않아서, 그런 회사에 이자보상배율 글이 하나도 없어요.
INT0 = {"flRan": ["cr", "icr", "l3", "imp"], "flSrc": {"icr": "is", "int0": True}}       # 예: 삼영에스앤씨 (영업손실 −17.0억, 이자 0)


def test_no_interest_paid_means_no_interest_coverage_chip():
    got = run("""const s = { t: '000010', cls: 'kr' };
      const f = (co) => K.warnChips(W.warnings(s, co));
      const ALL = ['cr', 'icr', 'l3', 'imp'];
      out = { int0: f({ flRan: ALL, flSrc: { icr: 'is', int0: true } }), cf: f({ flRan: ALL, flSrc: { icr: 'cf', int0: true } }),
        paid: f({ flRan: ALL, flSrc: { icr: 'is' } }), no: f({ flRan: ALL, flSrc: { icr: 'is', int0: false } }), str: f({ flRan: ALL, flSrc: { int0: 'true' } }),
        bad: f({ flRan: ALL, flSrc: 'int0' }), fired: f({ flRan: ALL, flSrc: { icr: 'is', int0: true }, fl: { cr: 80 } }),
        w: W.warnings(s, { flRan: ALL, flSrc: { icr: 'is', int0: true } }),
        pf: [PFN.warnOf({ t: '000010', cls: 'kr' }, { flRan: ALL, flSrc: { icr: 'is', int0: true } }), PFN.warnOf({ t: '000010', cls: 'kr' }, { flRan: ALL })] };""")
    assert got["int0"] == ["l3", "cr", "imp"] and got["cf"] == ["l3", "cr", "imp"], got   # 이자를 내지 않았으면 이자보상배율 칩 없음
    assert got["paid"] == ["l3", "cr", "imp", "icr"] and got["no"] == got["paid"]          # 이자를 냈으면 그대로
    assert got["str"] == got["paid"] and got["bad"] == got["paid"]                         # 정확히 int0 true 일 때만
    assert got["fired"] == ["l3", "imp"]
    w = got["w"]
    assert w["allRan"] is True and w["int0"] is True and w["flags"] == []                  # 확인은 돌았고 경고는 없어요
    assert got["pf"] == ["clear", "clear"]                                                 # '재무 경고 0개'는 참이라 그대로 (회사 페이지와 같아요)


def test_no_interest_paid_company_on_every_screen():
    """회사 페이지 요약: '재무 경고 신호는 없어요' + 칩 셋(3년 연속 적자 아님 · 유동비율 100% 이상 · 자본잠식 없음), 이자보상배율이라는 말은 없어요.
    예전 뱁새 성적표(한국어 · 영어) · 기업분석: 이자보상배율 · Interest coverage 라는 말이 없어요 (걸린 신호만 보여 줘요)."""
    data, corp = fixture("data.json"), fixture("corp.json")
    co = next(c for c in corp["companies"] if c["t"] == "005930")
    co.update(INT0)
    co.pop("fl", None)
    co.pop("flWhy", None)
    paid = json.loads(json.dumps(corp))
    next(c for c in paid["companies"] if c["t"] == "005930")["flSrc"] = {"icr": "is"}
    got = run("""
      const ms = kstMs(RP.isoPlusDays(RP.EPS_FIX_DATE, 1)); at(ms);
      const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };
      const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };
      const v2 = (corp) => { const load = mkLoad({ data: JSON.parse(JSON.stringify(DATA)), corp: JSON.parse(JSON.stringify(corp)), macro: read('macro.json') }, ms);
        const html = renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code: '005930', ctab: null, disc: null, nav }));
        return { chips: [...html.matchAll(/data-ui-v2="co-warn-chip" data-check="([a-z0-9]+)"/g)].map((m) => m[1]), n: (/data-ui-v2="co-warn" data-n="(\\d+)"/.exec(html) || [])[1] || null,
          head: lines(html).includes(C2.co.warn.none), icrWords: lines(html).filter((l) => l.includes('이자보상배율')) }; };
      const c = CORP.companies.find((x) => x.t === '005930');
      const card = (lang) => lines(renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, corp: CORP, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } })));
      const page = lines(renderToStaticMarkup(h(OLD.CompanyView, { data: CORP, t: '005930', heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} })));
      out = { int0: v2(CORP), paid: v2(PAID), ko: card('ko'), en: card('en'), page };""", DATA=data, CORP=corp, PAID=paid)
    i, p = got["int0"], got["paid"]
    assert i["n"] == "0" and i["head"] and i["chips"] == ["l3", "cr", "imp"] and i["icrWords"] == [], i   # 이자보상배율이라는 말 없음
    assert p["n"] == "0" and p["chips"] == ["l3", "cr", "imp", "icr"] and p["icrWords"] == ["이자보상배율 1배 이상"], p
    for k in ("ko", "en", "page"):
        said = [l for l in got[k] if "이자보상배율" in l or "Interest coverage" in l or "interest coverage" in l]
        assert said == [], (k, said)



# ── 신종자본증권 (DART 다시 읽기 v19.1f 리뷰 3): EPS 에서 분배를 뺀 회사는 nio3 이 분배를 뺀 주주 몫 순이익 ──
# epsIn.hyb (그 기간에 뺀 분배, 억원)가 있으면 "s"(별도 재무제표)도 nio3 을 읽어요 (ni 는 분배 전이라 기준이 섞여요). 그해 nio3 이
# 없으면 자료가 없는 것 (ni 로 대신하지 않아요). "o" 는 원래 nio3. hyb 가 없거나 0 이면 예전 그대로 ("s" 는 ni).
def test_hybrid_payouts_put_both_ends_on_the_owners_net_profit():
    sam = fixture("corp.json")
    sam = next(c for c in sam["companies"] if c["t"] == "005930")
    sh = round(sam["shm"] * 1e6) + 815974664
    ni_ttm = 450000.0
    net3 = [round(v - 3000.0, 1) for v in sam["ni"]]                      # 분배를 뺀 순이익 (지어낸 값: 해마다 3,000억)
    own3 = [442609.56, 336213.63, 144734.01]
    def shape(b, hyb=None, nio3=None, **kw):
        e = {"ni": ni_ttm, "b": b, "p": "2026.2Q", "sh": sh, **({"hyb": hyb} if hyb is not None else {})}
        out = {**sam, "epsIn": e, "eps": round(ni_ttm * 1e8 / sh), "cash3": [111079.06, 98107.67, 98094.38], **kw}
        if nio3 is not None:
            out["nio3"] = nio3
        return out
    shapes = {"sHyb": shape("s", 3000.0, net3), "sNoHyb": shape("s", None, net3), "sHyb0": shape("s", 0, net3), "sHybNeg": shape("s", -5.0, net3),
              "sHybTrue": shape("s", True, net3), "sHybNoNio3": shape("s", 3000.0, None), "sHybThenMissing": shape("s", 3000.0, net3[:2] + [None]),
              "oHyb": shape("o", 3000.0, own3), "oNoHyb": shape("o", None, own3)}
    got = run("""
      B.E.setDataShape({ divCheck: { v: 1 } });
      out = Object.fromEntries(Object.entries(SHAPES).map(([k, co]) => {
        const s = { t: co.t, cls: 'kr', price: co.price, cap: co.cap, dps: 1668.0, dps3a: [1668.0, 1446.0, 1444.0], dyt: 0.74, fy: 2025 };
        return [k, { cut: RP.epsHybCut(co.epsIn), b0: RP.epsBase(co, 0), b2: RP.epsBase(co, 2), d: B.K.decompose(co), old: OLD.decomposeReturn(co),
          g: B.K.impliedGrowth(s, co), past: B.K.pastNiGrowth(co), pay: B.K.payout(s, co) }];
      }));""", SHAPES=shapes)
    cut = {k: v["cut"] for k, v in got.items()}
    assert cut == {"sHyb": True, "sNoHyb": False, "sHyb0": False, "sHybNeg": False, "sHybTrue": True, "sHybNoNio3": True, "sHybThenMissing": True,
                   "oHyb": True, "oNoHyb": False}, cut
    x = got["sHyb"]                                                          # "s" + 분배: 두 끝 모두 분배를 뺀 순이익 (nio3)
    assert x["b0"] == {"basis": "s", "ni": net3[0], "sharesM": sh / 1e6} and x["b2"]["ni"] == net3[2], (x["b0"], x["b2"])
    assert abs(x["d"]["epsThen"] - net3[2] * 1e8 / sh) < 1e-9 and abs(x["old"]["epsThen"] - net3[2] * 1e8 / sh) < 1e-9
    assert x["g"]["ni0"] == net3[0] and abs(x["pay"]["pct"] - 111079.06 / net3[0] * 100) < 1e-9 and x["pay"]["basis"] == "s"
    assert got["sHybTrue"]["b2"]["ni"] == net3[2]
    for k in ("sNoHyb", "sHyb0", "sHybNeg"):                                # 분배가 없으면 예전 그대로: ni
        y = got[k]
        assert y["b0"]["ni"] == sam["ni"][0] and y["b2"]["ni"] == sam["ni"][2], (k, y["b0"], y["b2"])
        assert abs(y["d"]["epsThen"] - sam["ni"][2] * 1e8 / sh) < 1e-9 and y["g"]["ni0"] == sam["ni"][0], k
        assert abs(y["pay"]["pct"] - 111079.06 / sam["ni"][0] * 100) < 1e-9, k
    # nio3 이 없으면 자료가 없는 것 (ni 로 대신하지 않아요): 늘 하던 대로 '자료가 없어요' · 카드 없음
    z = got["sHybNoNio3"]
    assert z["b0"]["ni"] is None and z["b2"]["ni"] is None and z["d"] == {"why": "missing"} and z["old"] is None and z["pay"] is None, z
    assert z["g"].get("ni0") is None, z["g"]
    w = got["sHybThenMissing"]
    assert w["b0"]["ni"] == net3[0] and w["b2"]["ni"] is None and w["d"] == {"why": "missing"} and w["old"] is None and w["past"] is None
    for k in ("oHyb", "oNoHyb"):                                            # "o" 는 원래 nio3 (그대로)
        assert got[k]["b0"]["ni"] == own3[0] and got[k]["b2"]["ni"] == own3[2] and got[k]["g"]["ni0"] == own3[0], k


def test_an_unreadable_currency_code_shows_no_currency_line():
    """파이프라인은 읽을 수 없는 통화 이름에 stmtCur "XXX" (ISO 의 '통화 없음')를 써요. '원화가 아닌 XXX로'라고 말하지 않아요: 통화 줄 없음,
    console 에 크게 한 번 (숫자는 비어 있는 그대로). 숨기는 것도 통화 줄이 있을 때만이라 예전 화면 그대로예요."""
    data, corp = fixture("data.json"), fixture("corp.json")
    blank_stmt_cur(data, corp, cur="XXX")
    got = run("""
      const ms = kstMs(RP.isoPlusDays(RP.EPS_FIX_DATE, 1)); at(ms);
      const w0 = warns.length;
      const load = mkLoad({ data: DATA, corp: CORP, macro: read('macro.json') }, ms);
      const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };
      const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };
      const pages = [null, 'earn', 'value', 'earn-more', 'value-more'].map((ctab) => renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code: STMT_T, ctab, disc: null, nav }))).join('');
      const old = renderToStaticMarkup(h(OLD.CompanyView, { data: CORP, t: STMT_T, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const v2warns = warns.slice(w0).filter((m) => m.includes('stmtCur'));
      out = { of: RP.stmtCurOf({ stmtCur: 'XXX' }), v2: marked(pages, 'data-ui-v2', 'stmt-cur'), xxx: lines(pages + old).filter((l) => l.includes('XXX')),
        tiles: [...renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code: STMT_T, ctab: null, disc: null, nav })).matchAll(/data-ui-v2="co-tile" data-topic="([a-z]+)"/g)].map((m) => m[1]),
        old: marked(old, 'data-fix', 'stmt-cur'), oldCaption: lines(old).includes('적자이거나 데이터가 없어요'), v2warns, all: warns.slice(w0).filter((m) => m.includes('stmtCur')).length };""",
              DATA=data, CORP=corp, STMT_T=STMT_T)
    assert got["of"] is None and got["v2"] == 0 and got["old"] == 0 and got["xxx"] == [], got   # 'XXX' 라는 글이 화면에 없어요
    assert got["tiles"] == ["earn", "value", "div", "risk"] and got["oldCaption"] is True        # 통화 줄이 없으면 숨기지도 않아요 (예전 그대로)
    assert len(got["v2warns"]) == 2 and all("!!" in m and '"XXX"' in m for m in got["v2warns"]), got["v2warns"]   # 2.0 · 예전 뱁새 한 번씩



# ── 원화가 아닌 재무제표 회사에는 고치는 중 두 줄이 없어요 (코디네이터, 2026-11-08) ──
# 그런 회사는 epsIn 이 없어서 'PER과 EPS는 … {date}에 바뀔 수 있어요.'가 날짜가 지나도 남을 뻔했어요. 숫자는 비어 있고 통화 줄이 이유를
# 말하니 PER · EPS 줄도, 이자보상배율 줄도 없어요 (2.0 · 예전 뱁새). 읽을 수 없는 코드("XXX" 등)는 stmtCur 가 없는 것과 같아요.
def test_stmt_cur_companies_never_show_the_being_fixed_lines():
    got = run("""
      const OFF = { flWhy: { icr: 'off' } };
      const A = { t: '000010', stmtCur: 'USD', ...OFF }, X = { t: '000020', stmtCur: 'XXX', ...OFF }, N = { t: '000030', ...OFF };
      const COS = [A, X, N];
      const rules = (corp) => COS.map((c) => RP.epsFixNeeded(corp, c));
      const kr = (c) => ({ t: c.t, cls: 'kr' });
      FX.setEpsBasis({ companies: COS });                         const now = COS.map((c) => FX.epsFixFor(kr(c)));
      FX.setEpsBasis({ epsBasis: 'owners', companies: COS });     const live = COS.map((c) => FX.epsFixFor(kr(c)));
      const note = (s) => renderToStaticMarkup(h(FN.EpsFixNote, { show: FX.epsFixFor(s) }));
      const st = OF.corpFixState({ companies: COS }), stLive = OF.corpFixState({ epsBasis: 'owners', companies: COS });
      out = { needNow: rules({ companies: COS }), needLive: rules({ epsBasis: 'owners', companies: COS }), now, live,
        any: [FX.epsFixForAny([kr(A)]), FX.epsFixForAny([kr(A), kr(N)])], noteA: note(kr(A)), noteN: lines(note(kr(N))).length,
        icr: COS.map(RP.icrOff), icrShown: COS.map(FX.icrOffShown),
        loaded: [OF.epsFixNeedLoaded(st, [A.t]), OF.epsFixNeedLoaded(st, [X.t]), OF.epsFixNeedLoaded(st, [A.t, N.t]), OF.epsFixNeedLoaded(stLive, [A.t]),
          OF.epsFixNeedLoaded(null, [A.t])],
        notWon: [...st.notWon],
        old: [renderToStaticMarkup(h(OF.EpsFixLine, { corp: { companies: COS }, cos: [A] })), lines(renderToStaticMarkup(h(OF.EpsFixLine, { corp: { companies: COS }, cos: [N] }))).length,
          renderToStaticMarkup(h(OF.IcrOffLine, { co: A })), lines(renderToStaticMarkup(h(OF.IcrOffLine, { co: N }))).length] };""")
    assert got["needNow"] == [False, True, True] and got["needLive"] == [False, True, True], got   # USD: 없음 · XXX 는 없는 것과 같아요
    assert got["now"] == [False, True, True] and got["live"] == [False, True, True]
    assert got["any"] == [False, True] and got["noteA"] == "" and got["noteN"] == 1
    assert got["icr"] == [False, True, True] and got["icrShown"] == [False, True, True]
    assert got["loaded"] == [False, True, True, False, True] and got["notWon"] == ["000010"]       # 받기 전에는 줄이 있어요 (짐작하지 않아요)
    assert got["old"][0] == "" and got["old"][1] == 1 and got["old"][2] == "" and got["old"][3] == 1


def test_stmt_cur_company_pages_and_score_card_have_no_being_fixed_lines():
    """예전 뱁새 기업분석 (ROE 가 보여도) · 첫 화면 성적표 (한국어 · 영어): stmtCur 회사에는 고치는 중 두 줄이 없어요. 성적표의 '적자이거나 재무
    데이터가 아직 없어요.' 자리는 한국어 화면에서 승인된 통화 줄, 영어 화면에서는 아무 줄도 없어요 (영어 통화 줄은 승인되지 않았어요).
    stmtCur 가 없으면 예전 그대로."""
    data, corp = fixture("data.json"), fixture("corp.json")
    co, _ = blank_stmt_cur(data, corp)
    co.update(flWhy={"icr": "off"}, fl={"cr": 80})                          # 줄이 생길 조건을 일부러 다 갖춰요
    assert co.get("roe") is not None
    got = run("""
      const page = (cos) => renderToStaticMarkup(h(OLD.CompanyView, { data: { ...BASE, companies: cos }, t: STMT_T, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const swap = (f) => BASE.companies.map((c) => (c.t === STMT_T ? f(c) : c));
      const card = (c, lang) => renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: BASE.sectors, corp: BASE, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: BASE.pxDate, publishedAt: BASE.publishedAt } }));
      const C0 = BASE.companies.find((c) => c.t === STMT_T), CN = { ...C0, stmtCur: undefined };
      const v = (html) => ({ eps: marked(html, 'data-fix', 'eps'), icr: marked(html, 'data-fix', 'icr'), cur: marked(html, 'data-fix', 'stmt-cur'), lines: lines(html) });
      out = { page: v(page(BASE.companies)), pageNo: v(page(swap((c) => ({ ...c, stmtCur: undefined })))),
        ko: v(card(C0, 'ko')), en: v(card(C0, 'en')), koNo: v(card(CN, 'ko')), enNo: v(card(CN, 'en')) };""", BASE=corp, STMT_T=STMT_T)
    line = CUR.format(currency="USD")
    assert got["page"]["eps"] == 0 and got["page"]["icr"] == 0 and got["page"]["cur"] == 1, got["page"]
    assert got["pageNo"]["eps"] >= 1, got["pageNo"]                         # stmtCur 가 없으면 ROE 칸 밑에 그대로
    ko, en = got["ko"], got["en"]
    assert ko["cur"] == 1 and line in ko["lines"] and "적자이거나 재무 데이터가 아직 없어요." not in ko["lines"], ko["lines"]
    assert ko["eps"] == 0 and ko["icr"] == 0
    assert en["cur"] == 0 and "Loss-making or no financial data yet." not in en["lines"] and line not in en["lines"], en["lines"]
    assert not any("USD" in l for l in en["lines"]) and en["eps"] == 0 and en["icr"] == 0
    assert "적자이거나 재무 데이터가 아직 없어요." in got["koNo"]["lines"] and got["koNo"]["cur"] == 0
    assert "Loss-making or no financial data yet." in got["enNo"]["lines"] and got["enNo"]["icr"] == 1


# ── 3. 예전 뱁새 영어 화면의 고치는 중 줄 ──
def test_old_app_english_lines_follow_the_korean_rules():
    sam = fixture("corp.json")
    sam = next(c for c in sam["companies"] if c["t"] == "005930")
    c_off = {**sam, "flWhy": {"icr": "off"}, "flRan": ["cr", "l3", "imp"], "fl": {"cr": 80}}
    got = run("""
      const CORP = read('corp.json');
      const card = (c, corp, lang) => renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, corp, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } }));
      const NOW = { ...CORP, companies: CORP.companies.map((x) => (x.t === COFF.t ? COFF : x)) };
      const O = { ...COFF, flWhy: undefined, flRan: ['cr', 'icr', 'l3', 'imp'], epsIn: { ni: 1, b: 'o', p: 'fy', sh: 1 } };
      const T_ = { ...COFF, flWhy: undefined, epsIn: { ni: 1, b: 't', p: 'fy', sh: 1 } };
      const LIVE = { ...NOW, epsBasis: 'owners', companies: NOW.companies.map((x) => (x.t === COFF.t ? O : x)) };
      const LIVE_T = { ...NOW, epsBasis: 'owners', companies: NOW.companies.map((x) => (x.t === COFF.t ? T_ : x)) };
      const view = (html) => ({ lines: lines(html), eps: marked(html, 'data-fix', 'eps'), icr: marked(html, 'data-fix', 'icr'), en: marked(html, 'data-lang', 'en'),
        px: [...px(html, 'data-fix', 'eps'), ...px(html, 'data-fix', 'icr')] });
      const r = (el) => renderToStaticMarkup(el);
      out = {
        words: [OF.FIX_EPS_EN, OF.FIX_ICR_EN, OF.fixEpsText('en'), OF.fixIcrText('en'), OF.fixEpsText('ko'), OF.fixIcrText('ko'), OF.fixEpsText()],
        md: D.mdOf(RP.EPS_FIX_DATE, 'en'),
        enNow: view(card(COFF, NOW, 'en')), koNow: view(card(COFF, NOW, 'ko')),
        enLive: view(card(O, LIVE, 'en')), enStillTotal: view(card(T_, LIVE_T, 'en')),
        enNoPer: view(card({ ...COFF, per: null }, NOW, 'en')), enNoFlag: view(card({ ...COFF, fl: undefined }, NOW, 'en')),
        lineEn: lines(r(h(OF.EpsFixLine, { corp: NOW, cos: [COFF], lang: 'en' }))), lineEnLive: r(h(OF.EpsFixLine, { corp: LIVE, cos: [O], lang: 'en' })),
        lineEnForce: lines(r(h(OF.EpsFixLine, { corp: LIVE, cos: [O], force: true, lang: 'en' }))), lineEnOff: r(h(OF.EpsFixLine, { corp: NOW, cos: [COFF], show: false, lang: 'en' })),
        icrEn: lines(r(h(OF.IcrOffLine, { co: COFF, lang: 'en' }))), icrEnIe: r(h(OF.IcrOffLine, { co: { flWhy: { icr: 'ie' } }, lang: 'en' })),
        icrEnHidden: r(h(OF.IcrOffLine, { co: COFF, show: false, lang: 'en' })),
        loadedEn: lines(r(h(OF.EpsFixLineLoaded, { codes: ['005930'], lang: 'en' }))), loadedEnOff: r(h(OF.EpsFixLineLoaded, { show: false, codes: ['005930'], lang: 'en' })),
        loadedKo: lines(r(h(OF.EpsFixLineLoaded, { codes: ['005930'] }))),
      };""", COFF=c_off)
    y, mo, d = fix_date()
    en_eps, ko_eps = eps_en_line(), EPS_KO.format(date=f"{int(mo)}월 {int(d)}일")
    assert got["md"] == f"{MON[int(mo) - 1]} {int(d)}"                        # 예전 뱁새의 영어 월 · 일 ("Nov 10")
    assert got["words"] == [EPS_EN, ICR_EN, en_eps, ICR_EN, ko_eps, ICR_KO, ko_eps]   # Jack 의 글자 그대로 · 기본은 한국어
    # 첫 화면 성적표 (영어): 한국어 줄과 같은 자리 (P/E 줄 밑 · 재무 신호 밑), 한국어 글은 없어요
    en = got["enNow"]
    assert en["eps"] == 1 and en["icr"] == 1 and en["en"] == 2 and en_eps in en["lines"] and ICR_EN in en["lines"], en
    assert ko_eps not in en["lines"] and ICR_KO not in en["lines"]
    assert en["lines"].index(en_eps) > next(i for i, l in enumerate(en["lines"]) if l.startswith("P/E "))          # P/E 줄 밑
    assert en["lines"].index(en_eps) == got["koNow"]["lines"].index(ko_eps)                                      # 한국어 줄과 같은 자리
    assert en["lines"].index(ICR_EN) == next(i for i, l in enumerate(en["lines"]) if "financial caution flag" in l) + 1   # 재무 신호 바로 밑
    assert en["lines"].index(ICR_EN) == got["koNow"]["lines"].index(ICR_KO)
    assert all(p >= 12 for p in en["px"]) and len(en["px"]) == 2, en["px"]
    ko = got["koNow"]                                                          # 한국어 화면은 그대로
    assert ko_eps in ko["lines"] and ICR_KO in ko["lines"] and en_eps not in ko["lines"] and ko["en"] == 0
    # 같은 규칙: 다시 읽은 뒤 "o" 면 없고, 총 순이익("t")이면 남고, PER 줄이 없으면 · 재무 신호가 없으면 없어요
    assert got["enLive"]["eps"] == 0 and got["enLive"]["icr"] == 0, got["enLive"]
    assert got["enStillTotal"]["eps"] == 1 and en_eps in got["enStillTotal"]["lines"] and got["enStillTotal"]["icr"] == 0
    assert got["enNoPer"]["eps"] == 0 and got["enNoFlag"]["icr"] == 0
    assert got["lineEn"] == [en_eps] and got["lineEnLive"] == "" and got["lineEnForce"] == [en_eps] and got["lineEnOff"] == ""
    assert got["icrEn"] == [ICR_EN] and got["icrEnIe"] == "" and got["icrEnHidden"] == ""
    # 포트폴리오(src/detail.jsx)가 쓰는 줄: corp.json 을 받기 전에는 줄이 있어요 (고쳐졌다고 짐작하지 않아요)
    assert got["loadedEn"] == [en_eps] and got["loadedEnOff"] == "" and got["loadedKo"] == [ko_eps]


def test_old_app_passes_the_screen_language_to_the_lines():
    """첫 화면 성적표(src/shell.jsx)와 포트폴리오(src/detail.jsx)는 화면의 lang 을 넘기고, '한국어 화면에서만' 조건이 남아 있지 않아요.
    기업분석(src/corp.jsx)은 영어 화면에서도 한국어로만 보이는 칸이라 lang 을 넘기지 않아요 (한국어 줄 그대로)."""
    shell = open(os.path.join(ROOT, "src", "shell.jsx"), encoding="utf-8").read()
    detail = open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()
    corp = open(os.path.join(ROOT, "src", "corp.jsx"), encoding="utf-8").read()
    assert "<EpsFixLine corp={corp} cos={[c]} show={perShown} lang={lang}" in shell
    assert "<IcrOffLine co={c} show={flagN > 0} lang={lang}" in shell
    assert "!en && perShown" not in shell and "!en && flagN" not in shell
    uses = re.findall(r"<EpsFixLineLoaded\b[^/]*?/>", detail, flags=re.S)
    assert len(uses) == 2, uses
    assert all("lang={lang}" in u and 'lang === "ko"' not in u for u in uses), uses
    assert "lang=" not in "".join(re.findall(r"<(?:EpsFixLine|IcrOffLine)\b[^>]*>", corp))


_TMP = {}


def bundle_dir():
    """필요한 모듈을 한 파일로 한 번만 묶어요. React 는 밖에 둬요 (node_modules 의 것)."""
    if "p" not in _TMP:
        tmp = tempfile.mkdtemp(prefix="baepsae-reread-")
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
