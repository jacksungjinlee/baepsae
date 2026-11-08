# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.3d2 — 가진 종목 넣기 · 점검 · 내 규칙 정하기의 뒤따른 일 (Node 로 돌려봐요).

- 반도체 · 반도체 장비 · 전자부품은 점검의 업종 보기와 한 업종 규칙에서만 한 묶음 (Jack Q8). 다른 업종은 그대로
- 데이터에 없는 종목을 이름과 금액으로: 코드 없는 줄 { nk, ccy KRW, amountWon, date, unscored } 로 저장되고 store.js 를 통과해요
- 내 규칙 정하기: 한도는 1~100 의 정수 %, 처음 값(30 · 35)과 같으면 저장하지 않아요. 저장한 한도로 규칙을 점검해요
- 다 판 종목은 '계획한 n종목 중 m종목만' 이 아니에요 (rebased 아님), 목표 비중은 남은 종목끼리 나눠요
- 주소 #portfolio/rules/<포트폴리오 id>
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
_B = {}
T = "2026-11-07"


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-d2-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("P", "pf.js"), ("S", "store.js"), ("R", "rules.js"), ("RT", "routes.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/d2.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { P, S, R, RT } from './d2.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m));\nconst T = '" + T + "';\n"
            + HELP + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


HELP = """
const kr = (t, nk, ind, indName, price = 10000) => ({ t, nk, ne: nk, cls: 'kr', price, val20: 50, ind, indName, beta: 1, betaSE: 0.05, d1: 1, fy: 2025 });
const STOCKS = [kr('000010', '가나전자', 'semi', '반도체'), kr('000020', '라마장비', 'semi_eq', '반도체 장비'), kr('000030', '바사부품', 'elec_parts', '전자부품'),
  kr('000040', '아자은행', 'bank', '은행'), kr('000050', '차카화학', 'chem', '화학'),
  { t: 'NVDX', nk: 'Nvdx', ne: 'Nvdx', cls: 'us', ccy: 'USD', price: 100, val: 50, ind: 'semi', indName: '반도체', beta: 1, betaSE: 0.05, d1: 1, fy: 2025 }];
const ctxOf = (stocks) => ({ state: { ok: true }, byT: new Map(stocks.map((s) => [s.t, s])), fx: 1300, pxDate: T, coByT: new Map() });
const deckOf = (rows, extra = {}) => ({ id: 'dimp', name: 'p', createdAt: T, kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
  holdings: rows.map(([t]) => ({ t, nk: t })), purchases: [], imported: rows.map(([t, qty]) => ({ t, nk: t, ccy: t === 'NVDX' ? 'USD' : 'KRW', qty })), ...extra });
const rule = (st, id) => st.rules.find((r) => r.id === id);
"""


def test_chips_and_electronic_parts_count_as_one_group_only_in_the_check():
    """Jack Q8: 반도체 + 반도체 장비 + 전자부품 (a US 반도체 too) make one group in 점검's industry view and the 한 업종 rule, so
    20% + 20% + 10% + 10% = 60% breaks a 35% limit that no single v17.5.1 group breaks. The other groups stay as they are,
    and nothing about the stocks' own groups changes (업종별 등락 and 왜 움직였나 read s.ind / s.indName as before)."""
    got = run("""const d = deckOf([['000010', 20], ['000020', 20], ['000030', 10], ['NVDX', 0.7692], ['000040', 20], ['000050', 20]]);
      const st = P.pfState(d, ctxOf(STOCKS), STOCKS);
      const ind = P.industryView(st.view);
      out = { groups: ind.groups.map((g) => [g.ind, g.name, Math.round(g.w * 100), g.rows.map((r) => r.t).sort()]), rule: rule(st, 'ind'),
        own: STOCKS.map((s) => s.ind), of: STOCKS.map((s) => P.pfGroupOf(s)) };""")
    assert got["groups"][0] == ["chips", None, 60, ["000010", "000020", "000030", "NVDX"]]
    assert [g[0] for g in got["groups"][1:]] == ["bank", "chem"] and got["groups"][1][1] == "은행"
    r = got["rule"]
    assert r["state"] == "broken" and r["top"]["ind"] == "chips" and round(r["top"]["w"] * 100) == 60
    assert got["own"] == ["semi", "semi_eq", "elec_parts", "bank", "chem", "semi"]          # 종목의 업종은 그대로
    assert got["of"] == ["chips", "chips", "chips", "bank", "chem", "chips"]


def test_a_stock_added_by_name_with_an_amount_is_saved_without_a_code_and_reads_back():
    """+ 종목 더하기 (금액으로 넣기): a stock not in the data, by its name and an amount, becomes a row with no code, marked
    unscored, dated today; the portfolio passes store.js and its value counts that amount (frozen, as of its date)."""
    got = run("""const load = { data: { fx: 1300, stocks: STOCKS, pxDate: T, usPxDate: T }, byT: new Map(STOCKS.map((s) => [s.t, s])) };
      const deck = P.importedRecord({ drafts: [{ t: '000010', mode: 'qty', qty: 10 }, { t: null, name: '  비상장 회사  ', mode: 'amount', amountWon: 3000000 },
        { t: null, name: '', mode: 'amount', amountWon: 1000 }], load, settings: { points: { value: 3 } }, id: 'dn', name: 'p', today: T });
      const data0 = S.withDeck({ v: 1, decks: [] }, deck, T), data = { ...data0, v: S.versionFor(data0) };   // as writeStore tags it
      const view = P.pfRows(deck, ctxOf(STOCKS));
      out = { problem: S.deckProblem(deck, T), imported: deck.imported, holdings: deck.holdings.map((h) => h.t), valid: S.validStore(data, T),
        ok: [P.draftOk({ t: null, name: '회사', mode: 'amount', amountWon: 10000 }), P.draftOk({ t: null, name: ' ', mode: 'amount', amountWon: 10000 }),
          P.draftOk({ t: null, name: '회사', mode: 'amount', amountWon: 0 }), P.draftOk({ t: null, name: 'x'.repeat(121), mode: 'amount', amountWon: 10000 })],
        rows: view.rows.map((r) => [r.nk, r.value, r.frozen]), total: view.total };""")
    assert got["imported"][1] == {"nk": "비상장 회사", "ccy": "KRW", "amountWon": 3000000, "date": T, "unscored": True}
    assert got["problem"] is None, got["problem"]
    assert len(got["imported"]) == 2 and got["holdings"] == ["000010"] and got["valid"] is True     # 이름 없는 줄은 넣지 않아요
    assert got["ok"] == [True, False, False, False]
    assert got["rows"] == [["가나전자", 100000, False], ["비상장 회사", 3000000, True]] and got["total"] == 3100000


def test_the_limits_screen_saves_whole_percents_and_the_rules_use_them():
    """내 규칙 정하기: 한 종목 · 한 업종 limits are whole % from 1 to 100; a value equal to its default (30 · 35) is not
    stored; the records written always read back; the rules then check against the saved limits."""
    got = run("""const d = deckOf([['000010', 20], ['000040', 30], ['000050', 50]]);
      const data = { v: 2, decks: [d] };
      const a = P.withLimits(data, 'dimp', 40, 60), b = P.withLimits(data, 'dimp', 30, 35), c = P.withLimits(a, 'dimp', 30, 70);
      const st = (x) => P.pfState(x.decks[0], ctxOf(STOCKS), STOCKS);
      out = { a: a.decks[0].limits, b: 'limits' in b.decks[0], c: c.decks[0].limits, valid: [S.validStore(a, T), S.validStore(b, T), S.validStore(c, T)],
        read: ['30', ' 5 ', '0', '101', '12.5', '', 'x', '100', '1'].map(P.readLimit),
        bad: [P.withLimits(data, 'dimp', 0, 35), P.withLimits(data, 'dimp', 30, 101), P.withLimits(data, 'nope', 30, 35)],
        before: [rule(st(data), 'stock').state, rule(st(data), 'ind').state], after: [rule(st(a), 'stock').limit, rule(st(a), 'stock').state, rule(st(a), 'ind').state] };""")
    assert got["a"] == {"stock": 40, "ind": 60} and got["b"] is False and got["c"] == {"ind": 70}
    assert got["valid"] == [True, True, True]
    assert got["read"] == [30, 5, None, None, None, None, None, 100, 1]
    assert got["bad"] == [None, None, None]
    assert got["before"] == ["broken", "broken"] and got["after"] == [40, "broken", "ok"]     # 50% > 40%, 화학 50% ≤ 60%


def test_a_sold_out_holding_does_not_make_the_targets_look_rebased():
    """v19.3d2 (Jack): a holding sold down to 0 is listed in soldOut (the screens say "다 팔고 목표 비중만 남아 있어요.") and
    never makes the rebased note ("계획한 {n}종목 중 {m}종목만 샀어요") appear; a planned stock never bought still does."""
    got = run("""const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
      const ctx = { ...ctxOf(STOCKS), state: { ok: true }, byT: new Map(STOCKS.map((s) => [s.t, s])) };
      const deck = { id: 'db', name: 'b', holdings: [{ t: '000010', nk: 'a', target: 0.4, rules: band(0.4) }, { t: '000040', nk: 'b', target: 0.4, rules: band(0.4) },
        { t: '000050', nk: 'c', target: 0.2, rules: band(0.2) }],
        purchases: [{ t: '000010', qty: 10, price: 10000, date: '2026-10-01', ccy: 'KRW' }, { t: '000040', qty: 10, price: 10000, date: '2026-10-01', ccy: 'KRW' }] };
      const sold = { ...deck, sales: [{ t: '000040', qty: 10, price: 9000, date: '2026-11-01', ccy: 'KRW' }] };
      const e1 = R.evaluateDeck(deck, ctx), e2 = R.evaluateDeck({ ...sold, holdings: sold.holdings.slice(0, 2) }, ctx);
      out = { neverBought: [e1.rebased, e1.unheld, e1.soldOut], soldOut: [e2.rebased, e2.unheld, e2.soldOut, e2.bandPlanned, e2.bandHeld],
        band: e2.holdings[0].rules.find((r) => r.id === 'band').result };""")
    assert got["neverBought"] == [True, ["000050"], []]
    assert got["soldOut"] == [False, [], ["000040"], 1, 1] and got["band"] == "ok"


def test_the_limits_address():
    got = run("""out = ['#portfolio/rules/dimp', '#portfolio/rules/d1x-2_y', '#portfolio/rules/', '#portfolio/rules/a b', '#portfolio/rules', '#portfolio/rules/x/y']
      .map((h) => { const r = RT.parseHash(h); return [r.known, r.tab, r.sub, r.rules || null]; });""")
    assert got[0] == [True, "portfolio", "rules/dimp", "dimp"] and got[1] == [True, "portfolio", "rules/d1x-2_y", "d1x-2_y"]
    assert all(g[0] is False for g in got[2:]), got
