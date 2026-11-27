# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6b 켜기 (Jack, 2026-11-22: PR #168 의 질문 1–5 "all yes") — Node 에서 돌려봐요. 더하기만 한 시험이에요.

docs/tasks/v19.6-records-alerts-dark.md Part B.2 (the expected values worked by hand):
- 공시 보기: 확인 필요 카드마다 그 공시의 DART 원문 https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rc} (정확한 14자리 접수번호만,
  아니면 버튼 없음) · 새 탭 · rel=noopener · 글은 승인된 look.open '공시 보기'
- 임원 · 주요주주 지분 변동: look.js ROLE_OF 가 role 을 읽어요 · 역할별 제목 (임원 / 주요주주 / 둘 다이거나 빈 역할은 look.insBoth
  '임원·주요주주 지분 변동', Jack 이 그대로 승인) · 가진 종목과 관심 종목만 (다 판 종목 · 가지지도 지켜보지도 않는 종목은 없음) ·
  |q| × 오늘 종가가 1억원 이상 (저장된 amt 말고) · 공시일이 최근 7일 (오늘 포함, 미래는 없음)
- 홈: 가진 종목의 지분 변동은 v19.3e 공시 줄 하나로만 (같은 공시가 두 번 나오지 않아요), 관심 종목만 자기 줄
- 콘솔: '역할을 아직 읽지 않아요' · 'Jack 의 제목을 기다려요' 줄은 더 나오지 않아요
(what the screens show is checked in tests/smoke_v2.py scene_v196b_on)
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
_B = {}
DART = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="                  # Part B.2 의 주소 그대로


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-look-on-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("Lk", "look.js"), ("Tl", "todaylook.jsx"), ("R", "routes.js"), ("Hm", "home.js"),
                              ("Co", "company.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, Lk, Tl, R, Hm, Co, C } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


FAKE = """
const mem = new Map(); const warns = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = (m) => warns.push(String(m)); console.info = () => {};
const T = '2026-11-12', ymd = (n) => { const d = new Date(Date.parse(T + 'T00:00:00Z') - n * 86400000); return d.toISOString().slice(0, 10).replace(/-/g, ''); };
const kr = (t, more = {}) => ({ t, nk: '종목' + t, cls: 'kr', price: 50000, ...more });
const loadOf = (stocks) => ({ status: 'ok', preview: true, data: { pxDate: T, usPxDate: T, fx: 1400, stocks },
  byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map(), fresh: { stale: false, days: 0 }, corp: { publishedAt: '2026-11-08T09:00:00+09:00' } });
const NOW = Date.parse(T + 'T08:00:00+09:00');
const discOf = (d, more = {}) => ({ status: 'ok', data: { asOf: T, newest: T, listOk: true, publishedAt: T + 'T06:40:00+09:00', insider: [], nps: [],
  issue: [], issueOk: true, ...d, ...more } });
const deckOf = (rows, sales = []) => ({ id: 'd1', name: '포트폴리오', createdAt: '2026-11-01', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
  holdings: rows.map(([t, cls]) => ({ t, nk: '종목' + t, cls })), purchases: [], sales,
  imported: rows.map(([t, cls]) => ({ t, nk: '종목' + t, ccy: cls === 'us' ? 'USD' : 'KRW', qty: 3 })) });
const ins = (rc, t, days, q, role, pos = '이사', more = {}) => ({ rc: '2026' + String(rc).padStart(10, '0'), d: ymd(days), t, nk: 'x', q, role, pos, amt: 0.5, ...more });
const row = (rc, t, kind, days, more = {}) => ({ rc: '2026' + String(rc).padStart(10, '0'), d: ymd(days), t, nk: '종목' + t, kind, bd: ymd(days + 1), how: null,
  n: null, p: null, amt: null, cor: false, ...(kind === 'rights' ? { cls: 'common' } : {}), ...more });
// held: 000001 · watched: 000002 · sold out: 000004 (3 bought, 3 sold) · neither: 000003
const STORE = { data: { v: 2, decks: [deckOf([['000001', 'kr'], ['000004', 'kr']], [{ t: '000004', date: '2026-11-10', qty: 3, price: 50000 }])],
  watch: { '000002': { at: '2026-11-01' } } } };
const STOCKS = [kr('000001'), kr('000002'), kr('000003'), kr('000004')];
"""


def test_the_role_is_read_and_each_role_gets_its_approved_title():
    got = run("""
      const insider = [ins(1, '000001', 0, 2000, '임원', '대표이사'), ins(2, '000001', 1, -2000, '주요주주', '10%이상주주'),
        ins(3, '000001', 2, 2000, '임원·주요주주', '전무'), ins(4, '000001', 3, -2000, null, '-'), (() => { const x = ins(5, '000001', 4, 2000, null, ''); delete x.role; return x; })()];
      const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ insider }), T, NOW);
      out = { reader: [typeof Lk.ROLE_OF, Lk.ROLE_OF({ role: '임원' }), Lk.ROLE_OF({}) ?? null], insBoth: C.look.insBoth,
        cards: m.insider.map((c) => [c.rc.slice(-1), c.title, Tl.insiderTitle(c), Tl.insiderText(c)]),
        shown: Tl.shownInsider(m).length, page: Tl.pageHas(m) };""")
    assert got["reader"] == ["function", "임원", None]
    assert got["insBoth"] == "임원·주요주주 지분 변동"                          # Jack, 2026-11-22, word for word
    assert got["cards"] == [
        ["1", "exec", "종목000001 · 임원 지분 변동", "대표이사가 지분을 늘린 보고가 있어요. 지금 주가로 약 1억원이에요."],
        ["2", "major", "종목000001 · 주요주주 지분 변동", "10%이상주주가 지분을 줄인 보고가 있어요. 지금 주가로 약 1억원이에요."],
        ["3", "both", "종목000001 · 임원·주요주주 지분 변동", "전무가 지분을 늘린 보고가 있어요. 지금 주가로 약 1억원이에요."],
        ["4", "both", "종목000001 · 임원·주요주주 지분 변동", "임원·주요주주가 지분을 줄인 보고가 있어요. 지금 주가로 약 1억원이에요."],      # role blank, pos "-"
        ["5", "both", "종목000001 · 임원·주요주주 지분 변동", "임원·주요주주가 지분을 늘린 보고가 있어요. 지금 주가로 약 1억원이에요."]], got["cards"]
    assert got["shown"] == 5 and got["page"] is True


def test_insider_cards_only_for_held_and_watched_stocks():
    got = run("""
      const insider = ['000001', '000002', '000003', '000004'].map((t, i) => ins(10 + i, t, 0, 5000, '임원'));
      const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ insider }), T, NOW);
      const none = Lk.lookModel(loadOf(STOCKS), { data: { v: 1, decks: [] } }, discOf({ insider }), T, NOW);
      out = { ts: Tl.shownInsider(m).map((c) => c.t).sort(), none: [none.insider.length, none.ds] };""")
    # held 000001 and watched 000002 (Part B.2: every stock held in any portfolio, plus 관심 종목); sold-out 000004 and 000003 never
    assert got["ts"] == ["000001", "000002"], got
    assert got["none"] == [0, "skip"]                                          # nothing held or watched: no filings read at all


def test_the_one_billion_won_line_at_todays_close_and_the_seven_day_window():
    got = run("""
      const insider = [ins(1, '000001', 0, 2000, '임원'), ins(2, '000001', 0, 1999, '임원'), ins(3, '000001', 0, -2000, '임원'),
        ins(4, '000001', 6, 3000, '임원'), ins(5, '000001', 7, 3000, '임원'), ins(6, '000001', -1, 3000, '임원'),
        ins(7, '000001', 1, 100, '임원', '이사', { amt: 999 }), ins(8, '000002', 2, 1000, '주요주주')];
      const stocks = [kr('000001'), kr('000002', { price: 100000 }), kr('000003'), kr('000004')];
      const m = Lk.lookModel(loadOf(stocks), STORE, discOf({ insider }), T, NOW);
      out = Tl.shownInsider(m).map((c) => [c.rc.slice(-1), c.date, Math.round(c.won), c.up]);""")
    # 2,000 × 50,000 = 1억원 exactly is in, 1,999 shares is under; a lowered stake counts by its size; 6 days back is in, 7 is out, a
    # future date is out; the stored amt (999억원) is not used (100 × 50,000 = 500만원); 1,000 × 100,000 = 1억원 on a watched stock
    assert got == [["3", "2026-11-12", 100000000, False], ["1", "2026-11-12", 100000000, True], ["8", "2026-11-10", 100000000, True],
                   ["4", "2026-11-06", 150000000, True]], got


def test_home_never_shows_a_held_stocks_filing_twice():
    got = run("""
      const insider = [ins(1, '000001', 0, 5000, '임원'), ins(2, '000002', 1, 5000, '주요주주'), ins(3, '000001', 2, 10, '임원')];
      const disc = discOf({ insider, nps: [{ d: ymd(0), t: '000001', rt: 8, chg: 1 }] });
      const m = Lk.lookModel(loadOf(STOCKS), STORE, disc, T, NOW);
      const heldTs = new Set(['000001']);                                     // home2.jsx lookOf: the held rows of 홈's blocks
      const files = Hm.filingRows(disc, heldTs, T, Co.discDate(disc.data, NOW));
      const rows = Tl.LookRows({ m, part: 'filings', onOpen: () => {}, heldTs }).map((e) => [e.props.data['data-ui-v2'], e.props.data['data-t']]);
      out = { page: m.insider.map((c) => c.t), files: files.map((f) => [f.t, f.n]), rows, count: Tl.lookRowCount(m, heldTs),
        noHeld: Tl.LookRows({ m, part: 'filings', onOpen: () => {} }).length };""")
    assert got["page"] == ["000001", "000002"]                               # the page shows both cards
    assert got["files"] == [["000001", 2]]                                    # 홈's v19.3e 공시 row covers the held stock's every report
    # so 홈 gives only the watched stock's card a row of its own (and the 국민연금 row), never a second row for the held one
    # (newest first: the 국민연금 filing of today, then the watched stock's 지분 변동 of yesterday; the held stock's small report of
    # 50만원 counts only in the 공시 row)
    assert got["rows"] == [["home-nps", "000001"], ["home-insider", "000002"]], got["rows"]
    assert got["count"] == 2 and got["noHeld"] == 3


def test_each_issue_card_links_to_its_own_filing_on_dart():
    got = run("""
      const issue = [row(1, '000001', 'cb', 0, { amt: 3e10, p: 7 }), row(2, '000001', 'rights', 1, { how: 'holders', n: 100, p: 5 }),
        { ...row(3, '000001', 'bw', 2, { pend: true }), rc: '2026000000003' }];
      const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ issue }), T, NOW);
      out = { links: m.issue.map((c) => [c.rc, R.dartFilingUrl(c.rc)]), open: C.look.open,
        bad: [R.dartFilingUrl(undefined), R.dartFilingUrl(20260000000001), R.dartFilingUrl('2026000000000x'), R.dartFilingUrl('202600000000011')] };""")
    assert got["links"] == [["20260000000001", DART + "20260000000001"], ["20260000000002", DART + "20260000000002"],
                            ["2026000000003", None]], got["links"]            # 13 digits: no exact number, so no 공시 보기 button
    assert got["bad"] == [None, None, None, None]
    assert got["open"] == "공시 보기"


def test_the_issue_card_draws_the_link_as_a_plain_new_tab_link():
    src = open(os.path.join(ROOT, "src", "v2", "todaylook.jsx"), encoding="utf-8").read()
    card = src.split("function IssueCard(", 1)[1].split("\nfunction ", 1)[0]
    assert "const href = dartFilingUrl(c.rc);" in card and "{href && (" in card
    a = re.search(r"<a data-ui-v2=\"look-open\"[^>]*>", card).group(0)
    assert 'href={href} target="_blank" rel="noopener"' in a and "aria-describedby={titleId}" in a
    assert "{L().open}" in card and '<Icon name="arrow-square-out"' in card
    # board Today2: 공시 보기 left (outlined, the shared tokens), 확인했어요 right; either alone keeps its half
    assert "border: `1.5px solid ${COLOR.edge}`" in card and "background: COLOR.surface" in card and 'marginLeft: "auto"' in card
    for bad in ("fetch(", "window.open", "location", "<img", "<iframe", "#", "px solid #"):
        assert bad not in card, bad


def test_the_console_no_longer_says_the_insider_cards_wait():
    got = run("""
      const insider = [ins(1, '000001', 0, 5000, null, ''), ins(2, '000002', 0, 5000, '임원')];
      const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ insider }), T, NOW);
      Lk.lookSay(m, 'test');
      out = { n: m.insider.length, warns };""")
    assert got["n"] == 2
    assert not [w for w in got["warns"] if "insider" in w], got["warns"]


def test_a_stock_shown_at_an_older_close_gets_no_insider_card_and_the_console_names_it():
    """Review (2026-11-22): a stock priced at its last confirmed close (data.json pxd) would read "지금 주가로 약 …" from an older close
    under today's date line. It gets no card (watch.js never judges such a stock either); the console says why."""
    got = run("""
      const stocks = [kr('000001', { pxd: '2026-11-10' }), kr('000002'), kr('000003'), kr('000004')];
      const insider = [ins(1, '000001', 0, 5000, '임원'), ins(2, '000001', 1, 10, '임원'), ins(3, '000002', 0, 5000, '주요주주')];
      const m = Lk.lookModel(loadOf(stocks), STORE, discOf({ insider }), T, NOW);
      Lk.lookSay(m, 'pxd');
      out = { cards: m.insider.map((c) => c.t), shown: Tl.shownInsider(m).map((c) => c.t), skipped: m.skipped.map((x) => [x.rc.slice(-1), x.why]),
        rows: Tl.lookRowCount(m, new Set(['000001'])), warns };""")
    assert got["cards"] == ["000002"] and got["shown"] == ["000002"]
    # only the report that would have made a card (5,000 × 50,000 = 2.5억원) is named; 10 shares never would have
    assert got["skipped"] == [["1", "shown at its last confirmed close (pxd \"2026-11-10\"), not today's"]], got["skipped"]
    assert got["rows"] == 1                                                    # 홈: the watched stock's row only
    assert len(got["warns"]) == 1 and got["warns"][0].startswith("[v2] today-look (pxd): left out 1 (")
    assert "000001 20260000000001 (shown at its last confirmed close" in got["warns"][0]


def test_the_position_keeps_one_space_for_each_run_of_spaces_and_line_breaks():
    """Review (2026-11-22): real data has "수석매니저\\n(직책 : 본부장)" (2 rows on the 11-21 file, 75 positions with spaces)."""
    got = run("""
      const insider = [ins(1, '000001', 0, 2000, '임원', '수석매니저\\n(직책 : 본부장)'), ins(2, '000001', 1, -2000, '임원', '  대표이사\\t \\n사장 '),
        ins(3, '000001', 2, 2000, '주요주주', ' \\n\\t ')];
      const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ insider }), T, NOW);
      out = m.insider.map((c) => [c.pos, Tl.insiderText(c)]);""")
    assert got == [["수석매니저 (직책 : 본부장)", "수석매니저 (직책 : 본부장)이 지분을 늘린 보고가 있어요. 지금 주가로 약 1억원이에요."],
                   ["대표이사 사장", "대표이사 사장이 지분을 줄인 보고가 있어요. 지금 주가로 약 1억원이에요."],
                   [None, "임원·주요주주가 지분을 늘린 보고가 있어요. 지금 주가로 약 1억원이에요."]], got


def test_the_console_says_what_happens_to_an_unknown_role_and_to_a_card_without_a_title():
    """Review (2026-11-22): a role that is none of the three (the pipeline and its gate allow only 임원 · 주요주주 · 임원·주요주주 or blank)
    is shown with the both-or-blank title, so the console says "shown", never "left out"; a card whose title has no words (the role
    not read) is named as not shown."""
    got = run("""
      const insider = [ins(1, '000001', 0, 5000, '감사', '감사'), ins(2, '000002', 0, 5000, '임원')];
      const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ insider }), T, NOW);
      Lk.lookSay(m, 'odd');
      const w1 = [...warns]; warns.length = 0;
      Lk.lookSay({ fresh: true, skipped: [], oddRole: [], missing: false, insider: [{ t: 'A', rc: '20260000000009', title: 'none' }, { t: 'B', rc: '20260000000008', title: 'exec' }] }, 'none');
      out = { cards: m.insider.map((c) => [c.t, c.title, Tl.insiderTitle(c)]), skipped: m.skipped.length, odd: m.oddRole.map((x) => [x.t, x.why]),
        w1, w2: [...warns] };""")
    assert got["cards"] == [["000002", "exec", "종목000002 · 임원 지분 변동"], ["000001", "both", "종목000001 · 임원·주요주주 지분 변동"]], got["cards"]
    assert got["skipped"] == 0 and got["odd"] == [["000001", 'role "감사" is not one of the three']]
    assert got["w1"] == ['[v2] today-look (odd): insider cards shown with the title for both or blank (look.insBoth), their role is none of the three: '
                         '000001 20260000000001 (role "감사" is not one of the three)'], got["w1"]
    assert got["w2"] == ["[v2] today-look (none): insider cards not shown, no title for them (none): A 20260000000009"], got["w2"]


def test_the_insider_amount_has_one_decimal_under_10_eok_whole_eok_above_and_jo_as_elsewhere():
    """Jack, 2026-11-23: "one decimal only under 10억원; whole 억원 above that; 조원 with one decimal, the same as other amounts".
    The unit is chosen after rounding (9.96억 is "10억원", 999.6억 is "1,000억원", 9,999.6억 would be "1.0조원" as eokText does); a
    trailing .0 is dropped under 10억원; tenths are whole numbers (1.05억 is 1.1, never 1.0 from floating-point noise). Only the
    지분 변동 card changes: the 확인 필요 cards and the other screens keep cofmt.bigWon's whole 억."""
    got = run("""
      const w = Lk.insiderWon, e = (x) => Math.round(x * 1e8);
      out = {
        edges: [1, 1.04, 1.05, 1.41, 2, 2.82, 3.6, 9.94, 9.95, 9.96, 10, 14.18, 999.4, 999.6, 1234.4, 10000, 12500, 12340, 99999.6].map((x) => [x, w(e(x))]),
        bad: [w(0), w(-1e8), w(NaN), w(Infinity), w('1e8'), w(null)],
        text: [Tl.insiderText({ pos: '전무', up: false, won: 141000000 }), Tl.insiderText({ pos: '대표이사', up: false, won: 360000000 }),
          Tl.insiderText({ pos: '부사장', up: true, won: 999600000 }), Tl.insiderText({ pos: 'CEO', up: true, won: 1.23e12 })],
        issue: Tl.issueText({ body: 'cb', amt: 141000000, p: 1 }),
        under: (() => { const m = Lk.lookModel(loadOf(STOCKS), STORE, discOf({ insider: [ins(1, '000001', 0, 1998, '임원')] }), T, NOW);
          return [m.insider.length, 1998 * 50000]; })() };""")
    assert got["edges"] == [[1, "1억원"], [1.04, "1억원"], [1.05, "1.1억원"], [1.41, "1.4억원"], [2, "2억원"], [2.82, "2.8억원"], [3.6, "3.6억원"],
                            [9.94, "9.9억원"], [9.95, "10억원"], [9.96, "10억원"], [10, "10억원"], [14.18, "14억원"], [999.4, "999억원"],
                            [999.6, "1,000억원"], [1234.4, "1,234억원"], [10000, "1.0조원"], [12500, "1.3조원"], [12340, "1.2조원"],
                            [99999.6, "10.0조원"]], got["edges"]
    assert got["bad"] == [None] * 6
    assert got["text"] == ["전무가 지분을 줄인 보고가 있어요. 지금 주가로 약 1.4억원이에요.", "대표이사가 지분을 줄인 보고가 있어요. 지금 주가로 약 3.6억원이에요.",
                           "부사장이 지분을 늘린 보고가 있어요. 지금 주가로 약 10억원이에요.", "CEO가 지분을 늘린 보고가 있어요. 지금 주가로 약 1.2조원이에요."]
    # the 확인 필요 cards keep the whole 억 (cofmt.bigWon is unchanged)
    assert got["issue"] == "회사가 나중에 주식으로 바꿀 수 있는 채권을 1억원어치 발행하기로 했어요. 모두 주식으로 바뀌면 주식 수가 지금보다 1% 늘어나요."
    # 0.999억원 (1,998 × 50,000) never makes a card: the card needs 1억원 or more at today's close
    assert got["under"] == [0, 99900000]


def test_home_row_count_skips_an_insider_card_without_a_title():
    """홈의 오늘 볼 것 줄 수(lookRowCount)는 제목이 없는 지분 변동 카드(title "none": 역할을 읽지 않은 카드)를 세지 않아요 —
    그 카드는 줄로도 페이지에서도 보이지 않으니, 세면 홈이 '볼 것이 있다'고 잘못 말해요. 제목이 있는 카드는 그대로 세요 (리뷰 2026-11-28)."""
    got = run("""
      const base = { fresh: true, issue: [], insider: [], nps: [], dates: [] };
      const ic = (title) => ({ t: 'A', nk: 'A', title, rc: '20260000000001', date: T, up: true, won: 1e8, pos: null });
      out = [Tl.lookRowCount({ ...base, insider: [ic('none'), ic('exec')] }), Tl.lookRowCount({ ...base, insider: [ic('none')] }),
        Tl.lookRowCount({ ...base, insider: [ic('exec'), ic('both')] })];""")
    assert got == [1, 0, 2], got
