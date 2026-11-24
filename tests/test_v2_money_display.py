# -*- coding: utf-8 -*-
"""돈과 주식 수를 보이는 세 자리 (Track 2 점검 1.2 · 1.5 · 1.6, 2026-11-23) — 화면을 Node 에서 그려 봐요 (react-dom/server).

- 1.2 포트폴리오의 가진 종목 줄: 미국 주식의 소수점 수량을 기록 화면처럼 소수 넷째 자리까지, 끝의 0 없이 써요 (pfview.qtyText):
  7.5주 · 0.4주 · 2.3456주. 예전에는 반올림해서 "8주" · "0주" 였어요. 한국 주식의 온주는 예전 그대로 (10주 · 1,234주).
- 1.5 연말에 확인할 숫자: 1,000원이 안 되는 어림값은 원 단위로 써요 (tax.js shownEstimate). 승인된 "약"은 그대로: 배당 카드
  "약 {x}" (361원 배당 → 세금 떼기 전 약 427원, 예전에는 "약 0원") · 양도차익 줄 (세금은 약 361원이에요). 어림값이라서요 (v19.6 Part F,
  #187 검토). 1,000원부터는 예전 그대로 1,000원 단위 (약 123만 5,000원). taxState · yearDivs 가 돌려주는 값은 그대로예요.
- 1.6 내 수익의 날짜 줄: 계산에 들어간 가진 종목이 모두 미국 종목이면 미국 기준일(usPxDate)을 써요. 미국 휴장일 다음 날
  (2026-11-26 추수감사절: 한국 11월 26일 종가 · 미국 11월 25일 종가) "11월 25일 종가 · …" — 연말에 확인할 숫자의 손실 카드와 같은 날짜.
  한국 종목이 하나라도 들어가면 (또는 가진 종목이 없으면) 예전처럼 한국 날짜에, 미국 종목이 함께면 승인된 app.usClose 줄.
  usPxDate 가 없는 파일이면 날짜 줄 없이, 콘솔에 이유. 미국 종목은 달러로 값이 매겨진 종목이에요 (pf.usdOf): cls 가 "us" 인
  379800 KODEX 미국S&P500 은 한국 거래소에서 원으로, 한국 종가로 거래돼요 (#187 검토).
기대값은 모두 손으로 계산했어요. 시험 데이터: tests/fixtures/v2 (fx 1,338원 · AAPL $344.63 · MSFT $521.91 · 삼성전자 225,000원).
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
MODS = {"P": "src/v2/portfolio.jsx", "RJ": "src/v2/returns.jsx", "TJ": "src/v2/tax.jsx", "X": "src/v2/tax.js", "CP": "src/copy/v2.js"}
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-money-")
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


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


# 시험의 '지금'은 2026-11-27 (금) 09:00 KST: 연말에 확인할 숫자가 열려 있고, 그날 아침 발행본은 한국 11월 26일 종가 · 미국 11월 25일
# 종가예요 (11월 26일은 미국 추수감사절 휴장). 발행 시각이 지금보다 조금 앞이라 데이터는 새것이에요 (늦지 않음).
HELP = """
const NOW = Date.parse('2026-11-27T09:00:00+09:00'); Date.now = () => NOW;
const C = CP.C;
const logs = []; console.warn = (m) => logs.push(String(m)); console.info = (m) => logs.push(String(m));
const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).split(/<[^>]+>/).map((x) => x.trim()).filter(Boolean);
// the text inside the first element carrying data-ui-v2="id" (its own tags stripped), or null
const part = (html, id) => {
  const i = html.indexOf('data-ui-v2="' + id + '"'); if (i < 0) return null;
  const open = html.lastIndexOf('<', i), tag = /^<([a-z0-9]+)/.exec(html.slice(open))[1];
  let depth = 0, j = open; const re = new RegExp('<(/?)' + tag + '\\\\b[^>]*>', 'g'); re.lastIndex = open;
  for (let m; (m = re.exec(html));) { depth += m[1] ? -1 : 1; if (depth === 0) { j = m.index + m[0].length; break; } }
  return html.slice(open, j);
};
const text = (html) => (html == null ? null : ent(html.replace(/<[^>]+>/g, '')));
const attr = (html, id, a) => { const p = part(html, id); const m = p && new RegExp(a + '="([^"]*)"').exec(p.slice(0, p.indexOf('>') + 1)); return m ? m[1] : null; };
const D0 = JSON.parse(fs.readFileSync(FIX + '/data.json', 'utf8')), CO0 = JSON.parse(fs.readFileSync(FIX + '/corp.json', 'utf8'));
const loadOf = (over = {}) => {
  const D = { ...D0, pxDate: '2026-11-26', usPxDate: '2026-11-25', fxDate: '2026-11-26', publishedAt: '2026-11-27T05:00:00+09:00', ...over };
  for (const k of Object.keys(over)) if (over[k] === undefined) delete D[k];
  const CO = { ...CO0, publishedAt: '2026-11-27T05:00:00+09:00' };
  return { status: 'ok', data: D, corp: CO, fresh: { md: null, days: 0, stale: false }, byT: new Map(D.stocks.map((s) => [s.t, s])),
    coByT: new Map(CO.companies.map((x) => [x.t, x])), preview: false };
};
const usd = (t) => !/^[0-9]/.test(t);
const rec = (id, t, qty, price, date, fx) => ({ id, t, qty, price, date, ccy: usd(t) ? 'USD' : 'KRW', ...(usd(t) && fx ? { fx } : {}) });
const div = (id, t, amount, date) => ({ id, t, amount, date, ccy: 'KRW' });
const NK = { AAPL: 'Apple Inc.', MSFT: 'Microsoft Corporation', '005930': '삼성전자', '005380': '현대차' };
const deck = (id, ts, extra = {}) => ({ id, name: id, createdAt: '2026-01-05', planFx: 1450,
  holdings: ts.map((t) => ({ t, nk: NK[t] || t, cls: usd(t) ? 'us' : 'kr', target: 1 / ts.length })), purchases: [], ...extra });
const storeOf = (decks) => ({ data: { v: 2, decks, notes: {}, assume: {} }, writable: true, locked: false });
const portfolio = (decks, load = loadOf()) => renderToStaticMarkup(h(P.Portfolio, { load, store: storeOf(decks), setStoreData: () => {}, pad: 16, go: null }));
const returns = (d, load = loadOf()) => renderToStaticMarkup(h(RJ.Returns, { deck: d, load, store: storeOf([d]), pad: 16, onBack: () => {}, onTax: () => {} }));
const taxPage = (decks, load = loadOf()) => renderToStaticMarkup(h(TJ.Tax, { load, store: storeOf(decks), pad: 16, onBack: () => {} }));
"""


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\nconst { P, RJ, TJ, X, CP } = B;\n" + f"const FIX = {json.dumps(FIX)};\n"
            + HELP + decl + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── 1.2 포트폴리오의 주식 수 ──
FRACTION_DECKS = """
  const us = deck('dus', ['AAPL', 'MSFT'], {
    purchases: [rec('p1', 'AAPL', 10, 200, '2026-03-02', 1450), rec('p2', 'MSFT', 1, 400, '2026-03-02', 1450)],
    sales: [rec('s1', 'AAPL', 2.5, 260, '2026-09-01', 1400), rec('s2', 'MSFT', 0.6, 450, '2026-09-01', 1400)] });
  const kr = deck('dkr', ['005930', '005380'], {
    purchases: [rec('p3', '005930', 10, 70000, '2026-03-02'), rec('p4', '005380', 1234, 250000, '2026-03-02')] });
  const four = deck('dfour', ['AAPL'], { purchases: [rec('p5', 'AAPL', 3, 150, '2026-02-02', 1300)], sales: [rec('s3', 'AAPL', 0.6544, 300, '2026-10-01', 1400)] });
"""


def test_portfolio_rows_write_fractional_us_shares_like_the_records():
    got = run(FRACTION_DECKS + """out = lines(portfolio([us, kr, four]));""")
    # 10 − 2.5 = 7.5주 (예전 "8주") · 1 − 0.6 = 0.4주 (예전 "0주") · 3 − 0.6544 = 2.3456주 (예전 "2주"). 평균 단가는 판 기록과 상관없이 산 값
    rows = [x for x in got if "평균 단가" in x]
    assert rows == ["7.5주 · 평균 단가 $200.00", "0.4주 · 평균 단가 $400.00",
                    "10주 · 평균 단가 70,000원", "1,234주 · 평균 단가 250,000원",
                    "2.3456주 · 평균 단가 $150.00"], rows
    assert not any(x.startswith(("8주", "0주", "2주")) for x in got)


def test_korean_whole_shares_read_exactly_as_before():
    """한국 온주: 예전 nf (소수 없이, 천 단위 쉼표) 와 새 qtyText 가 같은 글자를 써요 — 한 글자도 바뀌지 않아요."""
    got = run("""const Q = [1, 7, 10, 999, 1000, 1234, 25000, 1234567];
      const nf = (v) => Number(v).toLocaleString('ko-KR', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
      const d = deck('dkr2', ['005930'], { purchases: Q.map((q, i) => rec('k' + i, '005930', q, 70000, '2026-03-0' + ((i % 9) + 1))) });
      const one = Q.map((q) => lines(portfolio([deck('dq' + q, ['005930'], { purchases: [rec('k', '005930', q, 70000, '2026-03-02')] })]))
        .find((x) => x.includes('평균 단가')));
      out = { one, want: Q.map((q) => nf(q) + '주 · 평균 단가 70,000원') };""")
    assert got["one"] == got["want"], got
    assert got["one"][5] == "1,234주 · 평균 단가 70,000원" and got["one"][7] == "1,234,567주 · 평균 단가 70,000원"


# ── 1.5 연말에 확인할 숫자: 1,000원이 안 되는 어림값 ──
def test_shown_estimate_is_exact_below_1000_won_and_the_old_rounding_from_there():
    got = run("""out = {
      est: [0.22, 361.02, 426.71, 998.82, 999.49, 999.5, 1000, 1499, 1500, 1234567.38].map((x) => X.shownEstimate(x)),
      bad: [X.shownEstimate(NaN), X.shownEstimate(undefined), X.shownEstimate(Infinity)],
      tax: [1, 1641, 2272, 2273, 4541, 4545, 5611668].map((o) => X.taxShown(o)),
      // from 1,000원 up the shown tax is taxOf, and the shown dividend sum is round1000 (yearDivs won), for every amount tried
      same: Array.from({ length: 4000 }, (_, i) => 2273 + i * 977).every((o) => { const s = X.taxShown(o); return !s.about || s.won === X.taxOf(o); }),
      sameDiv: Array.from({ length: 4000 }, (_, i) => 999.5 + i * 313.7).every((x) => { const s = X.shownEstimate(x); return s.about && s.won === X.round1000(x); }),
      below: [X.taxState(2501641).t, X.taxState(2504541).t, X.EXACT_BELOW] };""")
    assert got["est"] == [{"won": 0, "about": False}, {"won": 361, "about": False}, {"won": 427, "about": False},
                          {"won": 999, "about": False}, {"won": 999, "about": False}, {"won": 1000, "about": True},
                          {"won": 1000, "about": True}, {"won": 1000, "about": True}, {"won": 2000, "about": True},
                          {"won": 1235000, "about": True}]
    assert got["bad"] == [None, None, None]
    # 1 × 22% = 0.22원 → 0원 · 1,641 × 22% = 361.02원 · 2,272 × 22% = 499.84원 → 500원 · 2,273 × 22% = 500.06원 → 500원 ·
    # 4,541 × 22% = 999.02원 → 999원 · 4,545 × 22% = 999.9원 → 1,000원 (약) · 5,611,668 × 22% = 1,234,566.96원 → 1,235,000원 (약)
    assert got["tax"] == [{"won": 0, "about": False}, {"won": 361, "about": False}, {"won": 500, "about": False},
                          {"won": 500, "about": False}, {"won": 999, "about": False}, {"won": 1000, "about": True},
                          {"won": 1235000, "about": True}]
    assert got["same"] is True and got["sameDiv"] is True
    assert got["below"] == [0, 1000, 1000]          # taxState 의 t 는 예전 그대로 (1,000원 단위: 361.02원 → 0원 · 999.02원 → 1,000원)


TAX_DECKS = """
  // 양도차익: AAPL 1주를 $1,000 에 사서 (환율 1) 2026년에 팔아요 → 차익 = 판 값 − 1,000원
  const gain = (id, g) => deck(id, ['AAPL'], { purchases: [rec('b' + id, 'AAPL', 1, 1000, '2026-02-02', 1)], sales: [rec('s' + id, 'AAPL', 1, 1000 + g, '2026-03-02', 1)] });
  // 배당: 삼성전자 배당 (원, 세금 뗀 뒤) 하나
  const divd = (id, amount) => deck(id, ['005930'], { purchases: [rec('b' + id, '005930', 10, 70000, '2025-03-04')], divs: [div('v' + id, '005930', amount, '2026-04-20')] });
  const card = (html) => ({ line: text(part(html, 'tax-line')), t: attr(html, 'tax-gain', 'data-t'),
    div: text(part(html, 'tax-div-amount')), v: attr(html, 'tax-div', 'data-v'), divHtml: part(html, 'tax-div-amount') });
"""


def test_the_dividend_card_writes_an_amount_under_1000_won_to_the_won_with_its_yak():
    got = run(TAX_DECKS + """out = { C: C.tax.divAmount, ...Object.fromEntries([361, 305, 845, 846, 1000, 1044444].map((a) => [a, card(taxPage([divd('d' + a, a)]))])) };""")
    assert got["C"] == "약 {x}"                              # 승인된 조각 그대로 (세금 떼기 전 금액은 어림값: 1,000원 아래도 "약")
    # 361 ÷ 0.846 = 426.71원 → 약 427원 (예전 "약 0원") · 305 ÷ 0.846 = 360.52원 → 약 361원 · 845 ÷ 0.846 = 998.82원 → 약 999원 (예전 "약 1,000원")
    assert got["361"]["div"] == "약 427원" and got["361"]["v"] == "427"
    assert got["305"]["div"] == "약 361원" and got["305"]["v"] == "361"
    assert got["845"]["div"] == "약 999원" and got["845"]["v"] == "999"
    for a in ("361", "305", "845"):                         # 1,000원부터의 카드와 같은 칸 ("약" 칸 · 금액 칸)
        assert got[a]["divHtml"].count("<span") == got["846"]["divHtml"].count("<span"), got[a]
    # 1,000원부터는 예전 그대로: 846 ÷ 0.846 = 1,000원 · 1,000 ÷ 0.846 = 1,182.03원 → 약 1,000원 · 1,044,444 ÷ 0.846 = 1,234,567.38원 → 약 123만 5,000원
    assert got["846"]["div"] == "약 1,000원" and got["846"]["v"] == "1000"
    assert got["1000"]["div"] == "약 1,000원" and got["1000"]["v"] == "1000"
    assert got["1044444"]["div"] == "약 123만 5,000원" and got["1044444"]["v"] == "1235000"


def test_the_above_line_writes_a_tax_under_1000_won_with_its_own_yak():
    got = run(TAX_DECKS + """out = { C: { above: C.tax.above },
      ...Object.fromEntries([1641, 4541, 4545, 5611668, 875000].map((o) => [o, card(taxPage([gain('g' + o, 2500000 + o)]))])) };""")
    above = got["C"]["above"]
    assert above == "양도차익이 공제 250만원보다 {x} 많아요. 이대로라면 세금은 약 {t}이에요."           # 승인된 문장 그대로 (새 낱말 없음)
    f = lambda x, t: above.replace("{x}", x).replace("{t}", t)
    assert got["1641"]["line"] == f("1,641원", "361원") and got["1641"]["t"] == "361"          # 예전 "약 0원"
    assert got["4541"]["line"] == f("4,541원", "999원") and got["4541"]["t"] == "999"          # 예전 "약 1,000원"
    assert got["4545"]["line"] == f("4,545원", "1,000원") and got["4545"]["t"] == "1000"       # 999.9원: 1,000원 단위 그대로
    assert got["5611668"]["line"] == f("561만 1,668원", "123만 5,000원") and got["5611668"]["t"] == "1235000"
    assert got["875000"]["line"] == f("87만 5,000원", "19만 3,000원") and got["875000"]["t"] == "193000"   # 875,000 × 22% = 192,500 → 193,000


# ── 1.6 내 수익의 날짜 줄 ──
RET_DECKS = """
  const usOnly = deck('dus', ['AAPL', 'MSFT'], {
    purchases: [rec('p1', 'AAPL', 10, 200, '2026-03-02', 1450), rec('p2', 'MSFT', 1, 400, '2026-03-02', 1450)],
    sales: [rec('s1', 'AAPL', 2.5, 260, '2026-09-01', 1400), rec('s2', 'MSFT', 0.6, 450, '2026-09-01', 1400)] });
  const mixed = { ...usOnly, id: 'dmix', holdings: [...usOnly.holdings, { t: '005930', nk: '삼성전자', cls: 'kr', target: 0.3 }],
    purchases: [...usOnly.purchases, rec('p3', '005930', 10, 70000, '2026-03-02')] };
  const krOnly = deck('dkr', ['005930'], { purchases: [rec('p3', '005930', 10, 70000, '2026-03-02')] });
  // 한국 종목이 평균 단가 없이 들어 있어요 (가진 종목 넣기): 계산에서 빠지니 (ret.noAvg 줄이 이름을 말해요) 계산된 종목은 미국뿐
  const krNoAvg = { id: 'dimp', name: 'dimp', createdAt: '2026-01-05', kind: 'imported', settings: { points: {} },
    holdings: [{ t: 'AAPL', nk: 'Apple Inc.', cls: 'us' }, { t: '005930', nk: '삼성전자', cls: 'kr' }], purchases: [],
    imported: [{ t: 'AAPL', nk: 'Apple Inc.', ccy: 'USD', qty: 3, avg: 200 }, { t: '005930', nk: '삼성전자', ccy: 'KRW', qty: 10 }] };
  const soldAll = deck('dsold', ['AAPL'], { purchases: [rec('p1', 'AAPL', 2, 200, '2026-03-02', 1450)], sales: [rec('s1', 'AAPL', 2, 260, '2026-09-01', 1400)] });
  const dateOf = (html) => text(part(html, 'ret-date'));
"""


def test_returns_dates_us_only_holdings_with_the_us_close_after_a_us_holiday():
    got = run(RET_DECKS + """
      const L = loadOf();
      out = { line: C.ret.date, us: dateOf(returns(usOnly)), mixed: dateOf(returns(mixed)), kr: dateOf(returns(krOnly)),
        krNoAvg: dateOf(returns(krNoAvg)), noAvgLine: text(part(returns(krNoAvg), 'ret-no-avg')), sold: dateOf(returns(soldAll)),
        tax: text(part(taxPage([usOnly]), 'tax-loss-date')),
        sameDay: dateOf(returns(usOnly, loadOf({ usPxDate: '2026-11-26' }))) };""")
    f = lambda md: got["line"].replace("{date}", md)
    assert got["line"] == "{date} 종가 · 평균 단가를 넣은 종목 기준"
    assert got["us"] == f("11월 25일")                     # 미국 종목만: 미국 11월 25일 종가 (예전 "11월 26일", 한국 날짜)
    assert got["tax"] == got["us"]                         # 연말에 확인할 숫자의 손실 카드와 같은 날짜
    assert got["krNoAvg"] == f("11월 25일")                # 평균 단가가 없는 한국 종목은 계산에 없어요 (그 줄이 이름을 말해요)
    assert got["noAvgLine"] == "평균 단가가 없는 종목 1개(삼성전자)는 빼고 계산했어요."
    assert got["mixed"] == f("11월 26일")                  # 한국 종목이 들어가면 예전 그대로 한국 날짜
    assert got["kr"] == f("11월 26일")
    assert got["sold"] == f("11월 26일")                   # 가진 종목이 없으면 예전 그대로
    assert got["sameDay"] == f("11월 26일")                # 평소 (두 날짜가 같은 날)


def test_returns_us_only_in_a_file_without_a_us_date_shows_no_date_and_says_why():
    got = run(RET_DECKS + """
      const html = returns(usOnly, loadOf({ usPxDate: undefined }));
      out = { date: part(html, 'ret-date'), total: part(html, 'ret-total') != null, mixed: dateOf(returns(mixed, loadOf({ usPxDate: undefined }))),
        logs: logs.filter((m) => m.includes('no readable usPxDate')) };""")
    assert got["date"] is None and got["total"] is True     # 금액은 그대로, 한국 날짜를 미국 가격에 붙이지 않아요
    assert got["mixed"] == "11월 26일 종가 · 평균 단가를 넣은 종목 기준"
    assert len(got["logs"]) == 1 and "dus" in got["logs"][0], got["logs"]


def test_returns_mixed_holdings_after_a_us_holiday_say_the_us_date_with_the_approved_line():
    """한국 · 미국 종목이 함께 계산되고 미국 기준일이 한국 날짜와 다를 때 (미국 휴장일 다음 날): 날짜 줄은 한국 날짜 그대로, 그 밑에 포트폴리오와
    같은 승인된 줄 app.usClose "미국 종목은 현지 기준 {md} 종가예요." (같은 조건: 미국 종목이 있고 usPxDate 가 있고 pxDate 와 다름).
    미국 종목만이면 날짜 줄이 이미 미국 날짜라 이 줄은 없어요. 계산에서 빠진 미국 종목(평균 단가 없음)만 있으면 없어요."""
    got = run(RET_DECKS + """
      const note = (html) => text(part(html, 'ret-us-close'));
      // 미국 종목이 평균 단가 없이 들어 있어요: 계산된 종목은 한국뿐
      const usNoAvg = { ...krNoAvg, id: 'dimp2', imported: [{ t: 'AAPL', nk: 'Apple Inc.', ccy: 'USD', qty: 3 }, { t: '005930', nk: '삼성전자', ccy: 'KRW', qty: 10, avg: 60000 }] };
      const pf = portfolio([mixed]);
      out = { usClose: C.app.usClose, mixed: note(returns(mixed)), mixedDate: dateOf(returns(mixed)), us: note(returns(usOnly)), kr: note(returns(krOnly)),
        usNoAvg: note(returns(usNoAvg)), usNoAvgDate: dateOf(returns(usNoAvg)), sameDay: note(returns(mixed, loadOf({ usPxDate: '2026-11-26' }))),
        noUs: note(returns(mixed, loadOf({ usPxDate: undefined }))),
        pf: lines(pf).find((x) => x.startsWith('미국 종목은')) || null };""")
    assert got["usClose"] == "미국 종목은 현지 기준 {md} 종가예요."                 # 승인된 문장 그대로 (새 낱말 없음)
    want = got["usClose"].replace("{md}", "11월 25일")
    assert got["mixed"] == want and got["pf"] == want                                # 포트폴리오와 같은 줄
    assert got["mixedDate"] == "11월 26일 종가 · 평균 단가를 넣은 종목 기준"        # 날짜 줄은 예전 그대로
    assert got["us"] is None and got["kr"] is None                                   # 미국만: 날짜 줄이 이미 11월 25일 · 한국만: 미국 가격 없음
    assert got["usNoAvg"] is None and got["usNoAvgDate"] == "11월 26일 종가 · 평균 단가를 넣은 종목 기준"
    assert got["sameDay"] is None and got["noUs"] is None                            # 평소 (두 날짜가 같음) · 미국 날짜가 없는 파일


# ── #187 검토 (1차): 379800 KODEX 미국S&P500 은 cls "us" 지만 한국 거래소 · 원 · 한국 종가 ──
ETF_DECKS = RET_DECKS + """
  const imp = (id, rows) => ({ id, name: id, createdAt: '2026-01-05', kind: 'imported', settings: { points: {} },
    holdings: rows.map((r) => ({ t: r.t, nk: r.nk, cls: r.t === '379800' || r.ccy === 'USD' ? 'us' : 'kr' })), purchases: [], imported: rows });
  const spx = { t: '379800', nk: 'KODEX 미국S&P500', ccy: 'KRW', qty: 10, avg: 20000 };
  const sam = { t: '005930', nk: '삼성전자', ccy: 'KRW', qty: 10, avg: 60000 };
  const aapl = { t: 'AAPL', nk: 'Apple Inc.', ccy: 'USD', qty: 3, avg: 200 };
  // 포트폴리오 만들기로 만든 포트폴리오에 담긴 379800 (보유 종목의 cls 는 데이터 그대로 "us")
  const built379 = { ...deck('db379', ['379800']), holdings: [{ t: '379800', nk: 'KODEX 미국S&P500', cls: 'us', target: 1 }],
    purchases: [rec('p9', '379800', 10, 20000, '2026-03-02')] };
  const note = (html) => text(part(html, 'ret-us-close'));
  const usLine = (html) => lines(html).find((x) => x.startsWith('미국 종목은')) || null;
"""


def test_a_krx_fund_on_the_sp500_is_priced_at_the_korean_close_on_returns_and_portfolio():
    got = run(ETF_DECKS + """
      const D = loadOf().data; const s = D.stocks.find((x) => x.t === '379800');
      const a = returns(imp('d379', [spx])), b = returns(imp('d379k', [sam, spx])), c = returns(imp('d379u', [aapl, spx])), e = returns(built379);
      out = { data: [s.cls, s.ccy || null],
        only379: [dateOf(a), note(a)], kr379: [dateOf(b), note(b)], us379: [dateOf(c), note(c)], built379: [dateOf(e), note(e)],
        pfOnly379: usLine(portfolio([imp('d379', [spx])])), pfKr379: usLine(portfolio([imp('d379k', [sam, spx])])),
        pfBuilt379: usLine(portfolio([built379])), pfUs379: usLine(portfolio([imp('d379u', [aapl, spx])])),
        pfBuiltUs: usLine(portfolio([usOnly])) };""")
    kr, us = "11월 26일 종가 · 평균 단가를 넣은 종목 기준", "11월 25일 종가 · 평균 단가를 넣은 종목 기준"
    line = "미국 종목은 현지 기준 11월 25일 종가예요."
    assert got["data"] == ["us", None]                       # 시험 데이터 그대로: cls "us", 통화 없음 (원)
    assert got["only379"] == [kr, None]                      # 예전 (#187 처음) 11월 25일 — 원으로, 한국 종가로 거래돼요
    assert got["built379"] == [kr, None]
    assert got["kr379"] == [kr, None]                        # 잘못된 미국 날짜 줄 없음
    assert got["us379"] == [kr, line]                        # 미국 종목과 함께: 한국 날짜 + 미국 날짜 줄
    assert got["pfOnly379"] is None and got["pfKr379"] is None and got["pfBuilt379"] is None   # 포트폴리오도 (main 에서는 pfBuilt379 에 줄이 있었어요)
    assert got["pfUs379"] == line and got["pfBuiltUs"] == line                                 # 진짜 미국 종목이 있으면 그대로
