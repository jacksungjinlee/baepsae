# -*- coding: utf-8 -*-
"""다시 읽은 뒤의 줄들 (Jack 승인 2026-11-08, 전달) — src/repair.js · src/v2/fix.js · src/v2/fixnote.jsx · src/fixnote.jsx ·
src/v2/pf.js · src/v2/pfview.jsx · src/v2/home2.jsx · src/corp.jsx · src/shell.jsx.

1. 총 순이익 줄: "이 회사는 지배주주 몫 순이익을 따로 공시하지 않아, PER과 EPS를 회사 전체 순이익으로 계산했어요."
   화면의 corp.json 에 epsBasis "owners" 가 있고 그 회사의 epsIn.b 가 "t" 이고 epsIn.nci 가 true 일 때만, 고치는 중 줄이 있던 자리에.
   표시가 있으면 고치는 중 줄은 어느 회사에도 없어요 (날짜가 지났어요). 표시가 없으면 예전 그대로.
2. 원화가 아닌 재무제표 줄을 두 곳 더: 2.0 홈 · 포트폴리오의 '재무 경고 0개 — 확인하지 못했어요' 칸, 예전 뱁새 기업 비교 표 밑에 한 번.
3. 예전 뱁새 영어 첫 화면 성적표의 통화 줄: "This company files its statements in {currency}, so we don't show its financial figures yet."
화면은 react-dom/server 로 실제 컴포넌트를 그려서 봐요 (tests/test_fix_notes.py 의 묶음과 도우미를 같이 써요)."""
import os

import test_reread_lines as RL  # noqa: E402  (2.0 회사 페이지를 load 상태로 그리는 도우미)
from test_fix_notes import bundle_dir, company, eps_line, reread, run  # noqa: F401  (bundle_dir: 같은 묶음)

import shutil

import pytest

import test_fix_notes as FNT


@pytest.fixture(scope="module", autouse=True)
def _own_bundles():
    """The two helper modules clean their bundle when their own tests end: this module makes (and removes) its own."""
    for m in (FNT, RL):
        m._TMP.pop("p", None)
    yield
    for m in (FNT, RL):
        if "p" in m._TMP:
            shutil.rmtree(m._TMP.pop("p"), ignore_errors=True)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOTAL = "이 회사는 지배주주 몫 순이익을 따로 공시하지 않아, PER과 EPS를 회사 전체 순이익으로 계산했어요."
CUR = "이 회사는 재무제표를 원화가 아닌 {currency}로 공시해서, 실적 숫자는 아직 보여 드리지 않아요."
CUR_EN = "This company files its statements in {currency}, so we don't show its financial figures yet."


def test_the_total_line_words_are_jacks_and_the_same_in_both_apps():
    got = run(bundle_dir(), "out = { v2: C2.fix.total, old: OF.FIX_TOTAL, en: OF.FIX_STMT_CUR_EN };")
    assert got == {"v2": TOTAL, "old": TOTAL, "en": CUR_EN}


def test_the_total_line_rule_per_company():
    got = run(bundle_dir(), """
      const IN = (b, extra) => ({ ni: 100, b, p: 'ttm', sh: 1000000, ...(b === 't' ? { how: 'total' } : {}), ...extra });
      const COS = [{ t: '000010', epsIn: IN('o') }, { t: '000020', epsIn: IN('t', { nci: true }) }, { t: '000030', epsIn: IN('t') },
        { t: '000040', epsIn: IN('t', { how: 'hybrid', nci: true }) }, { t: '000050' }, { t: '900110' }, { t: '000060', epsIn: IN('t', { nci: 'yes' }) },
        { t: '000070', epsIn: IN('t', { nci: true }), stmtCur: 'USD' }, { t: '000080', epsIn: IN('o', { nci: true }) }];
      const NOW = { companies: COS }, LIVE = { epsBasis: 'owners', companies: COS };
      const KR = COS.map((c) => ({ t: c.t, cls: 'kr' }));
      const note = (s) => { const html = renderToStaticMarkup(h(FN.EpsFixNote, { s, show: FX.epsFixFor(s) }));
        return { lines: lines(html), total: /data-ui-v2="eps-total"/.test(html) }; };
      FX.setEpsBasis(NOW);  const nowFor = KR.map(FX.epsFixFor), nowNote = note(KR[1]);
      FX.setEpsBasis(LIVE); const liveFor = KR.map(FX.epsFixFor), liveNote = note(KR[1]), liveNoteT = note(KR[2]);
      FX.setEpsBasis(LIVE, { preview: true }); const pv = note(KR[1]);
      FX.setEpsBasis(NOW);
      const old = (corp, cos, extra = {}) => lines(renderToStaticMarkup(h(OF.EpsFixLine, { corp, cos, ...extra })));
      const st = OF.corpFixState(LIVE), stNow = OF.corpFixState(NOW);
      out = { needNow: COS.map((c) => RP.epsFixNeeded(NOW, c)), totalNow: COS.map((c) => RP.epsTotalNeeded(NOW, c)),
        needLive: COS.map((c) => RP.epsFixNeeded(LIVE, c)), totalLive: COS.map((c) => RP.epsTotalNeeded(LIVE, c)),
        nowFor, liveFor, nowNote, liveNote, liveNoteT, pv,
        oldNow: old(NOW, [COS[1]]), oldLive: old(LIVE, [COS[1]]), oldLiveMixed: old(LIVE, [COS[0], COS[2], COS[1]], { many: true }), oldLiveManyOne: old(LIVE, [COS[1]], { many: true }), oldLiveT: old(LIVE, [COS[2], COS[3]]),
        oldForceT: old(LIVE, [COS[2]], { force: true }), oldForceNci: old(LIVE, [COS[1]], { force: true }), oldEn: old(LIVE, [COS[1]], { lang: 'en' }),
        oldOff: old(LIVE, [COS[1]], { show: false }),
        kind: [OF.epsLineKind({ corp: LIVE, cos: [COS[1]] }), OF.epsLineKind({ corp: LIVE, cos: [COS[2]] }), OF.epsLineKind({ corp: NOW, cos: [COS[1]] })],
        loaded: [OF.epsFixNeedLoaded(st, ['000020']), OF.epsTotalNeedLoaded(st, '000020'), OF.epsTotalNeedLoaded(st, undefined),
          OF.epsFixNeedLoaded(stNow, ['000020']), OF.epsTotalNeedLoaded(stNow, '000020'), OF.epsTotalNeedLoaded(null, '000020'),
          OF.epsFixNeedLoaded(st, ['000050']), OF.epsFixNeedLoaded(st, ['900110']), OF.epsTotalNeedLoaded(st, '000040')] };""")
    assert got["needNow"] == [True] * 7 + [False, True]                       # 표시 전: 예전 그대로 (원화가 아닌 회사만 없음)
    assert got["totalNow"] == [False] * 9
    assert got["needLive"] == [False] * 4 + [True] + [False] * 4              # 표시 뒤: "t" · 해외 기업은 없고, epsIn 없음은 예전 그대로
    assert got["totalLive"] == [False, True] + [False] * 7                    # "t" + nci true 만 (o · nci 없는 t · hybrid · epsIn 없음 · 해외 · 원화 아님 · 'yes')
    assert got["nowFor"] == [True] * 7 + [False, True] and got["liveFor"] == [False, True, False, False, True] + [False] * 4
    assert got["nowNote"]["lines"] == [eps_line()] and not got["nowNote"]["total"]
    assert got["liveNote"]["lines"] == [TOTAL] and got["liveNote"]["total"] and got["liveNoteT"]["lines"] == []
    assert got["pv"]["lines"] == []                                           # 미리 보기에는 없어요
    assert got["oldNow"] == [eps_line()] and got["oldLive"] == [TOTAL] and got["oldLiveMixed"] == [] and got["oldLiveManyOne"] == [] and got["oldLiveT"] == []
    assert got["oldForceT"] == [] and got["oldForceNci"] == [TOTAL] and got["oldEn"] == [] and got["oldOff"] == []
    assert got["kind"] == ["total", None, "eps"]
    assert got["loaded"] == [False, True, False, True, False, False, True, False, False]   # 여러 회사 칸(one 없음)에는 총 순이익 줄 없음


def test_the_total_line_takes_the_being_fixed_lines_places_on_the_old_company_page_and_score_card():
    """예전 뱁새 기업분석: 표시 전 고치는 중 줄이 있던 네 칸(투자지표 · 업종 내 위치 · 주가 분해 · DCF)에 표시 뒤 총 순이익 줄이 한 번씩.
    nci 가 없는 "t" 는 두 줄 다 없고, 숫자를 뺀 주가 분해 칸은 제목만 남지 않게 칸이 없어요. 첫 화면 성적표(한국어)도 같은 자리."""
    sam = company("005930")
    tn = {**sam, **reread(sam, "t", nio3=None)}
    tn["epsIn"] = {**tn["epsIn"], "how": "total", "nci": True}
    t0 = {**sam, **reread(sam, "t", nio3=None)}
    got = run(bundle_dir(), """
      const page = (data, t) => renderToStaticMarkup(h(OLD.CompanyView, { data, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));
      const with_ = (co, live) => ({ ...CORP, ...(live ? { epsBasis: 'owners' } : {}), companies: CORP.companies.map((x) => (x.t === co.t ? co : x)) });
      const EPS = OF.fixEpsText();
      const card = (c, corp, lang) => lines(renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, corp, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } })));
      const v = (co, live) => { const html = page(with_(co, live), co.t);
        return { eps: count(html, EPS), total: count(html, OF.FIX_TOTAL), split: lines(html).includes('주가는 무엇으로 움직였나') }; };
      out = { now: v(TN, false), live: v(TN, true), t0: v(T0, true),
        card: card(TN, with_(TN, true), 'ko'), cardNow: card(TN, with_(TN, false), 'ko'), cardEn: card(TN, with_(TN, true), 'en') };""", TN=tn, T0=t0)
    assert got["now"]["eps"] == 4 and got["now"]["total"] == 0, got["now"]
    assert got["live"]["eps"] == 0 and got["live"]["total"] == 4, got["live"]   # 같은 네 칸 (모두 이 회사 하나의 칸)
    assert got["t0"]["eps"] == 0 and got["t0"]["total"] == 0 and not got["t0"]["split"], got["t0"]
    i = got["cardNow"].index(eps_line())
    assert got["card"][i] == TOTAL and eps_line() not in got["card"]          # 성적표: 같은 자리에 바뀌어요
    assert TOTAL not in got["cardEn"] and eps_line() not in got["cardEn"]     # 영어 글은 승인되지 않았어요


def test_the_2_0_company_page_puts_the_total_line_where_the_being_fixed_line_was():
    """2.0 회사 페이지(요약 · 실적 · 가치 · 배당 · 두 자세히): 표시 뒤 "t" + nci 회사는 표시 전 고치는 중 줄이 있던 자리 수만큼 총 순이익 줄.
    nci 가 없는 "t" 는 두 줄 다 없고, 숫자를 뺀 주가 분해 · 지금 가격이 가정하는 것 카드는 제목만 남지 않게 없어요."""
    data, corp = RL.fixture("data.json"), RL.fixture("corp.json")
    sam = next(c for c in corp["companies"] if c["t"] == "005930")
    rr = reread(sam, "t", nio3=None)
    got = RL.run("""
      const D0 = RP.EPS_FIX_DATE, ms = kstMs(RP.isoPlusDays(D0, 1));
      at(ms);
      const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };
      const store = { data: { v: 2, decks: [] }, writable: true, key: 'baepsae2.v1', preview: false };
      const look = (nci, live) => {
        const corp = JSON.parse(JSON.stringify(CORP));
        if (live) corp.epsBasis = 'owners';
        const co = corp.companies.find((c) => c.t === '005930');
        Object.assign(co, RR, { epsIn: { ...RR.epsIn, how: 'total', ...(nci ? { nci: true } : {}) } });
        delete co.nio3;
        const load = mkLoad({ data: JSON.parse(JSON.stringify(DATA)), corp, macro: read('macro.json') }, ms);
        const html = [null, 'earn', 'value', 'div', 'earn-more', 'value-more'].map((ctab) =>
          renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code: '005930', ctab, disc: null, nav }))).join('');
        return { eps: lines(html).filter((l) => l === FN.epsFixText()).length, total: lines(html).filter((l) => l === TOTAL).length,
          basisCards: (html.match(/data-edge="basis"|data-head="basis"/g) || []).length };
      };
      out = { now: look(true, false), live: look(true, true), t0: look(false, true) };""", DATA=data, CORP=corp, RR=rr, TOTAL=TOTAL)
    assert got["now"]["eps"] >= 3 and got["now"]["total"] == 0, got["now"]
    assert got["live"]["eps"] == 0 and got["live"]["total"] == got["now"]["eps"], got   # 같은 자리 수
    assert got["live"]["basisCards"] == got["now"]["basisCards"] >= 1, got
    assert got["t0"] == {"eps": 0, "total": 0, "basisCards": 0}, got["t0"]


# ── 2(a). 2.0 홈 · 포트폴리오의 '재무 경고 0개' 칸 ──
def test_the_holdings_warning_tile_says_why_for_statements_not_in_won():
    stocks = [{"t": "241560", "nk": "두산밥캣", "cls": "kr", "price": 48500.0, "val20": 50.0, "ind": "mach", "indName": "기계", "fy": 2025},
              {"t": "000020", "nk": "다라화학", "cls": "kr", "price": 10000.0, "val20": 50.0, "ind": "chem", "indName": "화학", "fy": 2025}]
    corps = {"usd": [{"t": "241560", "fy": 2025, "stmtCur": "USD"}, {"t": "000020", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"]}],
             "xxx": [{"t": "241560", "fy": 2025, "stmtCur": "XXX"}, {"t": "000020", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"]}],
             "none": [{"t": "241560", "fy": 2025, "flRan": ["cr", "l3", "imp"]}, {"t": "000020", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"]}],
             "flag": [{"t": "241560", "fy": 2025, "stmtCur": "USD"}, {"t": "000020", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"], "fl": {"cr": 80}}]}
    got = run(bundle_dir(), """
      const ctxOf = (corps) => ({ state: { ok: true }, byT: new Map(STOCKS.map((s) => [s.t, s])), coByT: new Map(corps.map((c) => [c.t, c])), fx: 1000, pxDate: '2026-11-06' });
      const rows = [{ t: '241560', nk: '두산밥캣', ccy: 'KRW', qty: 1 }, { t: '000020', nk: '다라화학', ccy: 'KRW', qty: 1 }];
      const deck = { id: 'd', name: 'p', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
        holdings: rows.map((r) => ({ t: r.t, nk: r.nk, cls: 'kr' })), purchases: [], imported: rows };
      const warn = (corps) => { const r = P.pfState(deck, ctxOf(corps), STOCKS).rules.find((x) => x.id === 'warn');
        const html = renderToStaticMarkup(h(PV.RuleTile, { r }));
        return { state: r.state, cur: r.stmtCur, tile: lines(html), px: (/data-ui-v2="stmt-cur"[^>]*font-size:(\\d+)px/.exec(html) || [])[1] || null }; };
      out = Object.fromEntries(Object.entries(CORPS).map(([k, c]) => [k, warn(c)]));""", STOCKS=stocks, CORPS=corps)
    line = CUR.format(currency="USD")
    assert got["usd"] == {"state": "unknown", "cur": "USD", "tile": ["재무 경고 0개", "확인하지 못했어요", line], "px": got["usd"]["px"]}, got["usd"]
    assert int(got["usd"]["px"]) >= 12
    assert got["xxx"]["cur"] is None and line not in got["xxx"]["tile"]           # 읽을 수 없는 코드: 통화 줄 없음
    assert got["none"]["cur"] is None and not any("공시해서" in x for x in got["none"]["tile"])
    assert got["flag"]["state"] == "broken" and line not in got["flag"]["tile"]    # 걸린 경고가 있으면 확인하지 못했어요가 아니에요


def test_home_hero_carries_the_currency_line_under_the_tiles():
    src = open(os.path.join(ROOT, "src", "v2", "home2.jsx"), encoding="utf-8").read()
    i = src.index("<IcrOffLine show={st.rules.some(")
    j = src.index("<StmtCurLine cur={(st.rules.find((x) => x.id === \"warn\" && x.state === \"unknown\") || {}).stmtCur}")
    assert i < j < src.index("{line && <p data-ui-v2=\"home-broken\"")


# ── 2(b). 예전 뱁새 기업 비교 ──
def test_old_compare_says_once_when_a_compared_company_is_not_in_won():
    base = {"s": "semi", "cap": 10.0, "rev": [1.0, 1.0, 1.0], "price": 1000.0}
    a = {**base, "t": "000010", "nk": "가나", "per": 10.0, "roe": 5.0}
    usd = {**base, "t": "241560", "nk": "두산밥캣", "cap": 9.0, "per": None, "roe": None, "stmtCur": "USD"}
    usd2 = {**base, "t": "000030", "nk": "마바", "cap": 8.0, "per": None, "roe": None, "stmtCur": "USD"}
    xxx = {**base, "t": "000040", "nk": "사아", "cap": 7.0, "per": None, "roe": None, "stmtCur": "XXX"}
    got = run(bundle_dir(), """
      const data = (cos) => ({ sectors: { semi: {} }, companies: cos });
      const cmp = (cos) => { const html = renderToStaticMarkup(h(OLD.CompareView, { data: data(cos), baseT: cos[0].t, onOpen() {}, onBack() {}, setExplain() {} }));
        return { n: count(html, LINE), any: lines(html).filter((l) => l.includes('공시해서')).length }; };
      out = { usd: cmp([A, U]), two: cmp([A, U, U2]), none: cmp([A]), xxx: cmp([A, X]), first: cmp([U, A]) };""",
              A=a, U=usd, U2=usd2, X=xxx, LINE=CUR.format(currency="USD"))
    assert got["usd"] == {"n": 1, "any": 1} and got["two"] == {"n": 1, "any": 1} and got["first"] == {"n": 1, "any": 1}, got
    assert got["none"]["any"] == 0 and got["xxx"]["any"] == 0, got


# ── 3. 예전 뱁새 영어 첫 화면 성적표 ──
def test_old_english_score_card_says_the_currency_line():
    sam = company("005930")
    c = {**sam, "per": None, "pbr": None, "stmtCur": "USD"}
    got = run(bundle_dir(), """
      const card = (c, lang) => lines(renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, corp: CORP, onOpenCorp() {}, onQuickDiag() {}, lang,
        asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } })));
      out = { en: card(C0, 'en'), ko: card(C0, 'ko'), xxx: card({ ...C0, stmtCur: 'XXX' }, 'en') };""", C0=c)
    assert CUR_EN.format(currency="USD") in got["en"] and CUR.format(currency="USD") not in got["en"]
    assert CUR.format(currency="USD") in got["ko"] and CUR_EN.format(currency="USD") not in got["ko"]
    assert not any("files its statements" in x for x in got["xxx"]) and "Loss-making or no financial data yet." not in got["xxx"]


def test_market_wide_places_never_say_this_company():
    """리뷰 2: 여러 회사가 함께 보이는 칸(조건 검색 · 기업 비교 표)은 그중 한 회사가 "t" + nci 여도 '이 회사는 …' 줄이 없어요."""
    base = {"s": "semi", "cap": 10.0, "rev": [1.0, 1.0, 1.0], "price": 1000.0}
    IN = {"ni": 1.0, "b": "t", "p": "fy", "sh": 1000, "how": "total", "nci": True}
    tn = {**base, "t": "000030", "nk": "마바", "per": 12.0, "roe": 5.0, "epsIn": IN}
    fixed = {**base, "t": "000010", "nk": "가나", "cap": 11.0, "per": 10.0, "roe": 5.0, "epsIn": {"ni": 1.0, "b": "o", "p": "fy", "sh": 1000}}
    got = run(bundle_dir(), """
      const data = (cos) => ({ epsBasis: 'owners', sectors: { semi: {} }, companies: cos });
      const scr = (cos) => lines(renderToStaticMarkup(h(OLD.ScreenerView, { data: data(cos), onOpen() {}, setExplain() {} }))).filter((l) => l.startsWith('이 회사는')).length;
      const cmp = (cos) => lines(renderToStaticMarkup(h(OLD.CompareView, { data: data(cos), baseT: cos[0].t, onOpen() {}, onBack() {}, setExplain() {} }))).filter((l) => l.startsWith('이 회사는')).length;
      out = { scrOne: scr([TN]), scrMix: scr([F, TN]), cmpOne: cmp([TN]), cmpMix: cmp([F, TN]) };""", TN=tn, F=fixed)
    assert got == {"scrOne": 0, "scrMix": 0, "cmpOne": 0, "cmpMix": 0}, got
