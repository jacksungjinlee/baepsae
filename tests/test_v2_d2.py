# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.3d2 — 가진 종목 넣기 · 점검 · 내 규칙 정하기의 뒤따른 일 (Node 로 돌려봐요).

- 반도체 · 반도체 장비 · 전자부품은 점검의 업종 보기와 한 업종 규칙에서만 한 묶음 (Jack Q8). 다른 업종은 그대로
- 데이터에 없는 종목을 이름과 금액으로: 코드 없는 줄 { nk, ccy KRW, amountWon, date, unscored } 로 저장되고 store.js 를 통과해요
- 내 규칙 정하기: 한도는 1~100 의 정수 %, 처음 값(30 · 35)과 같으면 저장하지 않아요. 저장한 한도로 규칙을 점검해요
- 한도는 저장한 시각(limitsTs)을 함께 둬요: 두 사본(탭)과 기록 파일이 만나도 나중에 저장한 한도가 남아요. 가진 종목 포트폴리오에만 있어요
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
            for name, mod in (("P", "pf.js"), ("S", "store.js"), ("R", "rules.js"), ("RT", "routes.js"), ("HD", "hold.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/d2.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { P, S, R, RT, HD } from './d2.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m));\nconst T = '" + T + "';\n"
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


def test_limits_keep_the_later_save_across_two_copies_and_a_records_file():
    """내 규칙 정하기 is an edit like a 메모: the portfolio keeps when its limits were saved (limitsTs, beside limits, so
    limits keeps #83's shape; a reset to 30 · 35 keeps only the time), so two copies (tabs) merge to the later limits
    whichever copy leads; a records file's other limits come in as an edit made now, and a file without limits leaves
    this device's latest ones. Only a 가진 종목 portfolio has limits (a built one would turn a v1 store into v2)."""
    got = run("""const base = { v: 2, decks: [deckOf([['000010', 20], ['000040', 30]])] };
      const A = { ...P.withLimits(base, 'dimp', 40, 60, 1000), v: 2 }, B = { ...P.withLimits(base, 'dimp', 20, 25, 2000), v: 2 };
      const R0 = { ...P.withLimits(A, 'dimp', 30, 35, 3000), v: 2 };
      const lim = (d) => (d ? { ...(d.decks[0].limits || {}), ...(d.decks[0].limitsTs != null ? { ts: d.decks[0].limitsTs } : {}) } : 'null');
      const built = { v: 1, decks: [{ id: 'db', name: 'b', createdAt: T, settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', target: 1, rules: [] }],
        purchases: [{ t: '000010', qty: 1, price: 10000, date: T, ccy: 'KRW' }] }] };
      const file = (d) => S.parseImport(S.exportText(d), T);
      const { limits: _l, limitsTs: _t, ...plain } = A.decks[0];
      out = { A: lim(A), R0: lim(R0), R0read: P.limitsOf(R0.decks[0]), valid: [A, B, R0].map((d) => S.validStore(d, T)),
        tabs: [lim(S.mergeTabs(A, B, T)), lim(S.mergeTabs(B, A, T)), lim(S.mergeTabs(R0, A, T)), lim(S.mergeTabs(A, R0, T))],
        badTs: [S.validStore({ v: 2, decks: [{ ...A.decks[0], limitsTs: -1 }] }, T), S.validStore({ v: 2, decks: [{ ...A.decks[0], limitsTs: 'x' }] }, T),
          S.validStore({ v: 2, decks: [{ ...A.decks[0], limits: { stock: 40, ts: 1 } }] }, T)],
        raw: [A.decks[0].limits, 'limits' in R0.decks[0], R0.decks[0].limitsTs, S.versionFor({ decks: [{ id: 'x', limitsTs: 5 }] })],
        imp: [lim(S.mergeStores(B, file(A), 5000, [], T)), lim(S.mergeStores(A, file({ v: 2, decks: [plain] }), 5000, [], T)),
          lim(S.mergeStores({ v: 2, decks: [] }, file(A), 5000, [], T)), lim(S.mergeStores(A, file(A), 5000, [], T)),
          lim(S.mergeStores(base, file(A), 5000, [], T))],
        built: P.withLimits(built, 'db', 40, 60, 1000), same: lim(P.withLimits(base, 'dimp', 30, 35, 4000)) };""")
    assert got["A"] == {"stock": 40, "ind": 60, "ts": 1000} and got["R0"] == {"ts": 3000} and got["R0read"] == {"stock": 30, "ind": 35}
    assert got["valid"] == [True, True, True] and got["badTs"] == [False, False, False]
    assert got["raw"] == [{"stock": 40, "ind": 60}, False, 3000, 2]       # limits keeps #83's shape; the time sits beside it
    # mergeTabs(other, cur): the later save wins whichever copy is current
    assert got["tabs"] == [{"stock": 20, "ind": 25, "ts": 2000}, {"stock": 20, "ind": 25, "ts": 2000}, {"ts": 3000}, {"ts": 3000}]
    # records files: other limits come in now; a file without limits keeps this device's; into empty records exactly as the file
    assert got["imp"] == [{"stock": 40, "ind": 60, "ts": 5000}, {"stock": 40, "ind": 60, "ts": 1000}, {"stock": 40, "ind": 60, "ts": 1000},
                          {"stock": 40, "ind": 60, "ts": 1000}, {"stock": 40, "ind": 60, "ts": 5000}]
    assert got["built"] is None
    assert got["same"] == {"ts": 4000}            # 저장 at the defaults still records when: the latest 저장 wins a merge


def test_the_2022_estimate_names_only_holdings_with_no_2022_price():
    """v19.3d2 review: of the holdings the 2022 estimate leaves out, only those with no data at all (added by name with an
    amount) are "2022년 주가가 없는 종목" (noPrice). Holdings in the data left out for another reason (no β, a β error above
    0.5, a fund with no 2022 figure — QQQ · SCHD · KODEX 200 · 맥쿼리인프라 on real data) go to noBeta and its share (#83's line).
    A listing after 2022 with a β is estimated like any other (어떻게 계산했나요 says so)."""
    got = run("""const RR = { kr: -0.249, usWon: -0.147, etf: { '114260': -0.0246 } };
      const S2 = [kr('000010', '가나전자', 'semi', '반도체'), { ...kr('000020', '상장이후', 'semi_eq', '반도체 장비'), listed: '2024-03-02' },
        { ...kr('005935', '가나전자우', 'semi', '반도체'), betaSE: null }, { ...kr('000030', '큰오차', 'elec_parts', '전자부품'), betaSE: 0.8 },
        { ...kr('069500', 'KODEX 200', null, null), etf: true }, { ...kr('088980', '맥쿼리인프라', null, null), fund: true, beta: null },
        { t: 'QQQ', nk: 'Invesco QQQ', ne: 'Invesco QQQ', cls: 'us', ccy: 'USD', price: 500, etf: true, beta: 1.1, betaSE: 0.05 },
        { ...kr('114260', 'KODEX 국고채3년', null, null), etf: true }];
      const deck = (rows, named = []) => ({ ...deckOf(rows), imported: [...deckOf(rows).imported, ...named] });
      const nm = (nk, won) => ({ nk, ccy: 'KRW', amountWon: won, date: T, unscored: true });
      const est = (d) => { const e = P.range2022(P.pfRows(d, { ...ctxOf(S2), fx: 1300 }), RR); return { ok: e.ok, out: e.out, noPrice: e.noPrice, noBeta: e.noBeta, share: Math.round((e.noBetaShare || 0) * 1000) / 1000 }; };
      out = {
        named: est(deck([['000010', 100], ['000020', 100]], [nm('비상장 회사', 1000000)])),
        data: est(deck([['000010', 2000], ['005935', 100], ['000030', 100], ['069500', 100], ['088980', 100], ['QQQ', 2], ['114260', 100]])),
        both: est(deck([['000010', 400], ['005935', 100]], [nm('비상장 회사', 1000000)])),
      };""")
    # only name-added rows: the new line names them; nothing in the data is left out (the listing after 2022 is estimated)
    assert got["named"] == {"ok": True, "out": ["비상장 회사"], "noPrice": ["비상장 회사"], "noBeta": [], "share": 0}
    # in the data, no usable β or no 2022 figure: never "2022년 주가가 없는"; the cushion ETF with a real 2022 result stays in
    d = got["data"]
    assert d["ok"] and d["noPrice"] == [] and d["noBeta"] == ["가나전자우", "큰오차", "KODEX 200", "맥쿼리인프라", "Invesco QQQ"], d
    left = 4 * 100 * 10000 + 2 * 500 * 1300                                # 1주 10,000원 × 100주씩 넷, QQQ 2주 × $500 × 1,300원
    assert d["share"] == round(left / (2000 * 10000 + 100 * 10000 + left), 3), d
    # both kinds: each its own list (two lines on the screen)
    assert got["both"]["noPrice"] == ["비상장 회사"] and got["both"]["noBeta"] == ["가나전자우"]
    assert got["both"]["share"] == round(1000000 / (5000000 + 1000000), 3)


LS = """
const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => { mem.set(k, String(v)); },
  removeItem: (k) => { mem.delete(k); }, get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
const K = 'baepsae2.v1', SIDE = K + '.limits';
const side = () => JSON.parse(mem.get(SIDE) || 'null');
const limOf = (d, id = 'dimp') => { const x = d.decks.find((y) => y.id === id); return x ? { l: x.limits || null, ts: x.limitsTs || null } : 'no deck'; };
"""


def test_limits_beside_the_records_come_back_after_an_earlier_app_drops_them():
    """v19.3d2 review 3: v19.3d (#83) never reads or writes key + ".limits", but can drop limits (its merge keeps the current
    copy's, its 'covered' check ignores them). Every write keeps the later limits there; on start, limits saved later than
    the records hold come back (합쳤어요 when the screens change; quietly when only the time differs). Older entries, a built
    portfolio of the same id, and bad entries (set aside as an ".unreadable." copy) never change the records."""
    got = run(LS + """const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const A = P.withLimits(base, 'dimp', 40, 60, 2000);
      S.writeStore(A, K, T);
      const kept = side();
      // only the side key and the records (no tab copies: each case on its own)
      const only = (sideVal, recs) => { mem.clear(); if (sideVal) mem.set(SIDE, JSON.stringify(sideVal)); mem.set(K, JSON.stringify({ ...recs, v: S.versionFor(recs) })); };
      // an earlier-app tab wrote its copy from before (limits 20/25 saved at 1000) over the records
      const old = P.withLimits(base, 'dimp', 20, 25, 1000);
      only(kept, old);
      const r1 = S.readStore(K, T);
      const stored1 = limOf(JSON.parse(mem.get(K)));
      // the same values, only an older time in the records: brought up to date quietly
      only(kept, P.withLimits(base, 'dimp', 40, 60, 1500));
      const r2 = S.readStore(K, T);
      // the records hold a later 저장 than the side key: they stay
      only(kept, P.withLimits(base, 'dimp', 30, 35, 9000));
      const r3 = S.readStore(K, T);
      S.writeStore(r3.data, K, T);                                       // the next save keeps the later 저장 beside
      const kept3 = side();
      // a reset (only the time) kept beside: the values go
      only({ v: 1, decks: { dimp: { ts: 9500 } } }, A);
      const r4 = S.readStore(K, T);
      // bad entries: set aside as a copy, the good one used
      only({ v: 1, decks: { dimp: { limits: { stock: 50 }, ts: 7000 }, bad1: { limits: { stock: 0 }, ts: 1 }, bad2: { ts: -1 }, bad3: 'x' } }, A);
      const r5 = S.readStore(K, T);
      const side5 = side(), aside = [...mem.keys()].filter((k) => k.startsWith(K + '.unreadable.')).map((k) => JSON.parse(mem.get(k)));
      // not JSON at all: set aside, the records as they are
      only(null, A);
      mem.set(SIDE, '{not json');
      const r6 = S.readStore(K, T);
      const side6 = mem.has(SIDE) ? mem.get(SIDE) : null, aside6 = [...mem.keys()].filter((k) => k.startsWith(K + '.unreadable.')).map((k) => mem.get(k));
      // a built portfolio with the same id never takes limits (it would turn a v1 store into v2)
      const built = { v: 1, decks: [{ id: 'dimp', name: 'b', createdAt: T, settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', target: 1, rules: [] }],
        purchases: [{ t: '000010', qty: 1, price: 10000, date: T, ccy: 'KRW' }] }] };
      only({ v: 1, decks: { dimp: { limits: { stock: 50 }, ts: 7000 } } }, built);
      const r7 = S.readStore(K, T);
      out = { kept, r1: { lim: limOf(r1.data), restored: r1.restored }, stored1, r2: { lim: limOf(r2.data), restored: r2.restored },
        r3: { lim: limOf(r3.data), restored: r3.restored }, kept3, r4: { lim: limOf(r4.data), restored: r4.restored },
        r5: { lim: limOf(r5.data), restored: r5.restored, side: side5 }, aside,
        r6: { lim: limOf(r6.data), restored: r6.restored, side: side6, aside: aside6 },
        r7: { v: r7.data.v, lim: limOf(r7.data), restored: r7.restored } };""")
    assert got["kept"] == {"v": 1, "decks": {"dimp": {"limits": {"stock": 40, "ind": 60}, "ts": 2000}}}
    assert got["r1"] == {"lim": {"l": {"stock": 40, "ind": 60}, "ts": 2000}, "restored": True}
    assert got["stored1"] == {"l": {"stock": 40, "ind": 60}, "ts": 2000}               # written back
    assert got["r2"] == {"lim": {"l": {"stock": 40, "ind": 60}, "ts": 2000}, "restored": False}
    assert got["r3"] == {"lim": {"l": None, "ts": 9000}, "restored": False}            # 30/35 at 9000: the defaults, no values
    assert got["kept3"] == {"v": 1, "decks": {"dimp": {"ts": 9000}}}                  # the later 저장 is kept beside too
    assert got["r4"] == {"lim": {"l": None, "ts": 9500}, "restored": True}
    assert got["r5"]["lim"] == {"l": {"stock": 50}, "ts": 7000} and got["r5"]["restored"] is True
    assert got["r5"]["side"] == {"v": 1, "decks": {"dimp": {"limits": {"stock": 50}, "ts": 7000}}}
    assert len(got["aside"]) == 1 and set(got["aside"][0]["decks"]) == {"dimp", "bad1", "bad2", "bad3"}
    assert got["r6"] == {"lim": {"l": {"stock": 40, "ind": 60}, "ts": 2000}, "restored": False, "side": None, "aside": ["{not json"]}
    assert got["r7"] == {"v": 1, "lim": {"l": None, "ts": None}, "restored": False}


def test_a_records_file_counts_the_limits_kept_beside_the_records():
    """v19.3d2 review 3 (sim6): an earlier-app tab dropped the latest limits from every copy, so only the side key holds them;
    a records file with other limits is still an edit made now (it wins, and stays at the next start), and a file with no
    limits leaves the latest ones (from beside the records)."""
    got = run(LS + """const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const older = P.withLimits(base, 'dimp', 40, 45, 1000);
      const file = (d) => S.parseImport(S.exportText(d), T);
      mem.set(K, JSON.stringify({ ...older, v: 2 }));
      mem.set(SIDE, JSON.stringify({ v: 1, decks: { dimp: { limits: { stock: 55, ind: 60 }, ts: 2000 } } }));
      const known = S.storedStores(K, T);
      const m = S.mergeStores(older, file(older), 5000, known, T);
      S.writeStore(m, K, T);
      const sideAfter = side();
      const after = S.readStore(K, T);
      // a file without limits: the latest ones (beside the records) stay
      mem.clear();
      mem.set(K, JSON.stringify({ ...older, v: 2 }));
      mem.set(SIDE, JSON.stringify({ v: 1, decks: { dimp: { limits: { stock: 55, ind: 60 }, ts: 2000 } } }));
      const { limits: _l, limitsTs: _t, ...plain } = older.decks[0];
      const m2 = S.mergeStores(older, file({ v: 2, decks: [plain] }), 5000, S.storedStores(K, T), T);
      out = { known: known.length, m: limOf(m), side: sideAfter, after: { lim: limOf(after.data), restored: after.restored }, m2: limOf(m2) };""")
    assert got["known"] == 2                                               # the records and the side key
    assert got["m"] == {"l": {"stock": 40, "ind": 45}, "ts": 5000}          # the file's limits, as an edit made now
    assert got["side"] == {"v": 1, "decks": {"dimp": {"limits": {"stock": 40, "ind": 45}, "ts": 5000}}}
    assert got["after"] == {"lim": {"l": {"stock": 40, "ind": 45}, "ts": 5000}, "restored": False}
    assert got["m2"] == {"l": {"stock": 55, "ind": 60}, "ts": 2000}


def test_side_key_ties_future_times_and_portfolios_taken_out():
    """v19.3d2 review 2. S1: a v19.3d merge ({ ...other, ...cur }) can pair an older copy's limits (20/25) with the time of a
    later 저장 that reset them; on a tie with other values the side key's (the reset) wins, and the screens say 합쳤어요.
    A tie with the same values keeps the records quietly. Future: an entry more than a day ahead of now is set aside and not
    used (one an hour ahead is). S3: a portfolio this tab's write takes out leaves the side key, so re-importing it from an
    older file without limits does not bring its old limits back; a portfolio set aside as unreadable keeps its entry."""
    got = run(LS + """const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const only = (sideVal, recs) => { mem.clear(); if (sideVal) mem.set(SIDE, JSON.stringify(sideVal)); mem.set(K, JSON.stringify({ ...recs, v: S.versionFor(recs) })); };
      // S1: records 20/25 at T2 (the merge's pairing), side: the reset at T2
      only({ v: 1, decks: { dimp: { ts: 2000 } } }, { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 20, 25, 1000).decks[0], limitsTs: 2000 }] });
      const s1 = S.readStore(K, T);
      // a tie with the same values: kept quietly
      only({ v: 1, decks: { dimp: { limits: { stock: 20, ind: 25 }, ts: 2000 } } }, { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 20, 25, 1000).decks[0], limitsTs: 2000 }] });
      const s1b = S.readStore(K, T);
      // future times
      const now = Date.now();
      only({ v: 1, decks: { dimp: { limits: { stock: 50 }, ts: now + 3 * 24 * 3600 * 1000 } } }, P.withLimits(base, 'dimp', 40, 60, 1000));
      const f1 = S.readStore(K, T);
      const f1side = mem.has(SIDE) ? mem.get(SIDE) : null, f1aside = [...mem.keys()].filter((k) => k.startsWith(K + '.unreadable.')).length;
      only({ v: 1, decks: { dimp: { limits: { stock: 50 }, ts: now + 3600 * 1000 } } }, P.withLimits(base, 'dimp', 40, 60, 1000));
      const f2 = S.readStore(K, T);
      // S3: two portfolios, dimp with limits; this tab takes dimp out; an older file without limits brings it back
      mem.clear();
      const two = { v: 2, decks: [P.withLimits(base, 'dimp', 20, 25, 1000).decks[0], { ...deckOf([['000040', 10]]), id: 'dx' }] };
      S.readStore(K, T);
      S.writeStore(two, K, T);
      const before = side();
      const fileText = S.exportText({ v: 2, decks: [deckOf([['000010', 20]])] });
      const without = { ...two, decks: two.decks.filter((x) => x.id !== 'dimp') };
      S.writeStore(without, K, T);
      const after = side();
      const m = S.mergeStores(without, S.parseImport(fileText, T), 5000, S.storedStores(K, T), T);
      // a portfolio that cannot be read (set aside) keeps its entry
      mem.clear();
      mem.set(SIDE, JSON.stringify({ v: 1, decks: { dimp: { limits: { stock: 20, ind: 25 }, ts: 1000 } } }));
      mem.set(K, JSON.stringify({ v: 2, decks: [{ ...two.decks[0], holdings: 'x' }, two.decks[1]] }));
      const r = S.readStore(K, T);
      S.writeStore({ ...r.data, decks: r.data.decks.map((x) => ({ ...x, name: 'renamed' })) }, K, T);
      out = { s1: { lim: limOf(s1.data), restored: s1.restored }, s1b: { lim: limOf(s1b.data), restored: s1b.restored },
        f1: { lim: limOf(f1.data), restored: f1.restored, side: f1side, aside: f1aside }, f2: { lim: limOf(f2.data), restored: f2.restored },
        before, after, m: limOf(m), locked: r.locked, keptAside: side() };""")
    assert got["s1"] == {"lim": {"l": None, "ts": 2000}, "restored": True}           # the reset stands
    assert got["s1b"] == {"lim": {"l": {"stock": 20, "ind": 25}, "ts": 2000}, "restored": False}
    assert got["f1"] == {"lim": {"l": {"stock": 40, "ind": 60}, "ts": 1000}, "restored": False, "side": None, "aside": 1}
    assert got["f2"]["lim"]["l"] == {"stock": 50} and got["f2"]["restored"] is True
    assert got["before"] == {"v": 1, "decks": {"dimp": {"limits": {"stock": 20, "ind": 25}, "ts": 1000}}}
    assert got["after"] == {"v": 1, "decks": {}}                                      # taken out by this tab: its entry went
    assert got["m"] == {"l": None, "ts": None}                                        # re-imported without limits: no old limits back
    assert got["locked"] is True and got["keptAside"] == {"v": 1, "decks": {"dimp": {"limits": {"stock": 20, "ind": 25}, "ts": 1000}}}


def test_the_last_save_wins_after_the_clock_is_set_back_and_unreadable_records_keep_the_side_key():
    """v19.3d2 review 3. K1: the clock 1 h (and 23 h) fast → 저장 L1 → clock corrected → 저장 L2: the second 저장 is stamped
    just after the first (store.js limitsSaveTime), so the next start shows L2, with no 합쳤어요. G1: records this app cannot
    read (a later version's) are not "taken out" by this tab's first write: the side key keeps them. K2: records whose
    limits carry a time more than a day ahead are not copied beside them on every write (no new set-aside copy each time)."""
    got = run(LS + """const H = 3600 * 1000, BASE = Date.now();
      const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const twoSaves = (fast) => {
        mem.clear();
        let d = P.withLimits(base, 'dimp', 20, 25, S.limitsSaveTime(K, base.decks[0], BASE + fast));
        S.readStore(K, T); S.writeStore(d, K, T);
        const t1 = d.decks[0].limitsTs;
        d = P.withLimits(d, 'dimp', 40, 45, S.limitsSaveTime(K, d.decks[0], BASE));      // clock corrected
        S.writeStore(d, K, T);
        const r = S.readStore(K, T);
        return { lim: limOf(r.data).l, restored: r.restored, after: limOf(r.data).ts - t1, side: side().decks.dimp.limits };
      };
      const k1 = twoSaves(H), k1b = twoSaves(23 * H);
      // G1: the stored records are a later version's (unreadable here); this tab writes its own records
      mem.clear();
      S.readStore(K, T); S.writeStore(P.withLimits(base, 'dimp', 20, 25, BASE - 5000), K, T);
      const later = JSON.parse(mem.get(K)); later.v = 3; mem.set(K, JSON.stringify(later));
      const g = S.readStore(K, T);
      const gw = S.writeStore({ v: 1, decks: [{ id: 'dn', name: 'n', createdAt: T, settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', target: 1, rules: [] }],
        purchases: [{ t: '000010', qty: 1, price: 10000, date: T, ccy: 'KRW' }] }] }, K, T);
      const gside = side();
      // K2: records whose limits are stamped two days ahead: never copied beside them, nothing set aside on each write
      mem.clear();
      const ahead = { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 20, 25, BASE).decks[0], limitsTs: BASE + 48 * H }] };
      S.readStore(K, T); S.writeStore(ahead, K, T); S.readStore(K, T); S.writeStore(S.withNote(ahead, '000010', 'memo', T, BASE), K, T); S.readStore(K, T);
      const k2 = { side: mem.has(SIDE) ? side() : null, aside: [...mem.keys()].filter((k) => k.startsWith(K + '.unreadable.')).length };   // before the clear
      mem.clear();
      const cap = [S.limitsSaveTime(K, { id: 'dimp', limitsTs: BASE + H }, BASE) - BASE, S.limitsSaveTime(K, { id: 'dimp', limitsTs: BASE + 48 * H }, BASE) - BASE];
      // S1 (review 4): tab B saves with the clock 3 h fast (beside the records too); tab A, which never saw it, saves after
      // the correction: limitsSaveTime's side-key part stamps A's 저장 just after B's, so A's (the last 저장) wins
      mem.clear();
      S.readStore(K, T); S.writeStore(base, K, T);
      const bSave = P.withLimits(base, 'dimp', 20, 25, S.limitsSaveTime(K, base.decks[0], BASE + 3 * H));
      S.writeStore(bSave, K, T);
      const aTs = S.limitsSaveTime(K, base.decks[0], BASE);                 // A still holds base (no limits)
      S.writeStore(P.withLimits(base, 'dimp', 40, 45, aTs), K, T);
      const s1 = S.readStore(K, T);
      out = { cap, k1, k1b, g: { locked: g.locked, wrote: gw, side: gside }, k2,
        s1: { after: aTs - bSave.decks[0].limitsTs, lim: limOf(s1.data).l, restored: s1.restored } };""")
    for k in ("k1", "k1b"):
        assert got[k]["lim"] == {"stock": 40, "ind": 45} and got[k]["restored"] is False and got[k]["after"] == 1, (k, got[k])
        assert got[k]["side"] == {"stock": 40, "ind": 45}, (k, got[k])
    assert got["g"]["locked"] is True and got["g"]["wrote"] is True
    assert got["g"]["side"] == {"v": 1, "decks": {"dimp": {"limits": {"stock": 20, "ind": 25}, "ts": got["g"]["side"]["decks"]["dimp"]["ts"]}}}
    assert got["k2"] == {"side": None, "aside": 0}
    assert got["cap"] == [3600 * 1000 + 1, 0]          # just after a time an hour ahead; one two days ahead is not carried on
    assert got["s1"] == {"after": 1, "lim": {"stock": 40, "ind": 45}, "restored": False}


def test_a_new_publish_is_not_held_for_a_row_added_by_name():
    """Merge with #90 (a page brought back into view switches to a newer publish, held while a draft would lose a holding):
    a "+ 종목 더하기" row has no code and does not come from the data, so it never holds the new data; a coded row whose stock
    is gone from the new data still does."""
    got = run("""const next = { status: 'ok', missing: [], byT: new Map([['000010', { t: '000010' }]]) };
      const im = (drafts) => ({ step: 0, drafts });
      const named = { key: 'n1', t: null, name: '비상장 회사', mode: 'amount', amount: '100' };
      out = [HD.draftsSurvive(im([named]), next), HD.draftsSurvive(im([{ t: '000010' }, named]), next), HD.draftsSurvive(im([{ t: '000020' }, named]), next),
        HD.holdReason({ onBuild: false, onImport: false, builder: null, importer: im([{ t: '000010' }, named]) }, next),
        HD.holdReason({ onBuild: false, onImport: false, builder: null, importer: im([{ t: '000020' }, named]) }, next)];""")
    assert got[:4] == [True, True, False, None]
    assert "would lose a holding" in got[4], got[4]


def test_imports_and_merges_never_let_a_fast_clock_time_win():
    """v19.3d2 review 4. I1: clock 1 h / 23 h fast → 저장 20/25 → clock corrected → 기록 불러오기 of a file with 50/50: the
    file's limits are stamped after the 저장 (mergeStores, the limitsSaveTime rule), so the next start shows 50/50, no
    합쳤어요. A limitsTs more than a day ahead counts as no time (store.js limitsEdit): F2: a 저장 stamped two days ahead,
    then a believable 저장 in another copy: the merge keeps the believable one. F1: a file whose limits are stamped three
    days ahead, the same values as here, then a 저장: the 저장 wins."""
    got = run(LS + """const H = 3600 * 1000, BASE = Date.now();
      const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const file = (d) => S.parseImport(S.exportText(d), T);
      const i1 = (fast) => {
        mem.clear();
        S.readStore(K, T);
        const a = P.withLimits(base, 'dimp', 20, 25, S.limitsSaveTime(K, base.decks[0], BASE + fast));
        S.writeStore(a, K, T);
        const f = P.withLimits(base, 'dimp', 50, 50, BASE - 30 * 24 * H);
        const m = S.mergeStores(a, file(f), BASE, S.storedStores(K, T), T);
        S.writeStore(m, K, T);
        const r = S.readStore(K, T);
        return { lim: limOf(r.data).l, restored: r.restored, after: limOf(m).ts - a.decks[0].limitsTs };
      };
      const i1a = i1(H), i1b = i1(23 * H), i1c = i1(0);
      // F2: copy A holds 20/25 stamped two days ahead; copy B holds 40/45 saved now: the merge keeps B's (either way round)
      const A2 = { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 20, 25, BASE).decks[0], limitsTs: BASE + 48 * H }] };
      const B2 = P.withLimits(base, 'dimp', 40, 45, BASE);
      const f2 = [limOf(S.mergeTabs(A2, B2, T)).l, limOf(S.mergeTabs(B2, A2, T)).l];
      // F1: a file with the same limits stamped three days ahead comes in; then a 저장 40/45 (now): the 저장 stays
      mem.clear();
      S.readStore(K, T);
      const own = P.withLimits(base, 'dimp', 20, 25, BASE - H);
      S.writeStore(own, K, T);
      const fd = { v: 2, decks: [{ ...own.decks[0], limitsTs: BASE + 72 * H, name: 'renamed' }] };
      const mi = S.mergeStores(own, file(fd), BASE, S.storedStores(K, T), T);
      S.writeStore(mi, K, T);
      const saved = P.withLimits(mi, 'dimp', 40, 45, S.limitsSaveTime(K, mi.decks[0], BASE));
      const f1m = [limOf(S.mergeTabs(mi, saved, T)).l, limOf(S.mergeTabs(saved, mi, T)).l];
      out = { i1a, i1b, i1c, f2, f1: { importTs: limOf(mi).ts, ownTs: own.decks[0].limitsTs, merge: f1m } };""")
    for k in ("i1a", "i1b"):
        assert got[k]["lim"] == {"stock": 50, "ind": 50} and got[k]["restored"] is False and got[k]["after"] == 1, (k, got[k])
    assert got["i1c"]["lim"] == {"stock": 50, "ind": 50} and got["i1c"]["restored"] is False
    assert got["f2"] == [{"stock": 40, "ind": 45}, {"stock": 40, "ind": 45}]
    assert got["f1"]["merge"] == [{"stock": 40, "ind": 45}, {"stock": 40, "ind": 45}], got["f1"]
    assert got["f1"]["importTs"] == got["f1"]["ownTs"]          # the file's time three days ahead is not kept: this device's stays


def test_a_slow_clock_keeps_the_last_save_and_imports_count_the_side_key():
    """v19.3d2 review 5. Slow (r5b): the records hold 20/25 saved 2 h ago, another tab's later 40/45 waits as an ".other."
    copy, and the app starts with the clock 3 days slow: both times look more than a day ahead, so the later of the two raw
    times stays (laterLimits): 40/45, before and after the clock is fixed. Notice: a copy that differs only in limitsTs (the
    same values) is merged quietly, no 합쳤어요. I1b: the records lost their limits (an earlier-app tab dropped them) and the
    side key holds a 저장 made 1 h ahead: 기록 불러오기 stamps the file's limits just after it, so they stay. A time more
    than a day ahead on this device is not used to stamp an import; a time exactly a day ahead is still believed."""
    got = run(LS + """const H = 3600 * 1000, BASE = Date.now(), REAL = Date.now;
      const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const file = (d) => S.parseImport(S.exportText(d), T);
      // slow
      mem.clear();
      mem.set(K, JSON.stringify({ ...P.withLimits(base, 'dimp', 20, 25, BASE - 2 * H), v: 2 }));
      mem.set(K + '.other.' + (BASE - H), JSON.stringify({ ...P.withLimits(base, 'dimp', 40, 45, BASE - H), v: 2 }));
      Date.now = () => REAL() - 72 * H;
      const slow = S.readStore(K, T);
      Date.now = REAL;
      const fixed = S.readStore(K, T);
      // notice: only limitsTs differs between the records and a copy
      mem.clear();
      mem.set(K, JSON.stringify({ ...P.withLimits(base, 'dimp', 20, 25, 1000), v: 2 }));
      mem.set(K + '.other.' + 5, JSON.stringify({ ...P.withLimits(base, 'dimp', 20, 25, 2000), v: 2 }));
      const quiet = S.readStore(K, T);
      const quietStored = limOf(JSON.parse(mem.get(K)));
      // I1b: records without limits, the side key holds a 저장 1 h ahead; import 50/50 at BASE
      mem.clear();
      mem.set(K, JSON.stringify({ ...base, v: 2 }));
      mem.set(SIDE, JSON.stringify({ v: 1, decks: { dimp: { limits: { stock: 20, ind: 25 }, ts: BASE + H } } }));
      const m = S.mergeStores(base, file(P.withLimits(base, 'dimp', 50, 50, BASE - 30 * 24 * H)), BASE, S.storedStores(K, T), T);
      S.writeStore(m, K, T);
      const i1b = S.readStore(K, T);
      // I1c: the records hold older limits (an earlier-app merge kept them) and the side key a later 저장 made 1 h ahead:
      // the import is stamped after the side key's, not after the records' (every copy counts, not the first)
      mem.clear();
      const older = P.withLimits(base, 'dimp', 20, 25, BASE - 2 * H);
      mem.set(K, JSON.stringify({ ...older, v: 2 }));
      mem.set(SIDE, JSON.stringify({ v: 1, decks: { dimp: { limits: { stock: 30, ind: 35 }, ts: BASE + H } } }));
      const mc = S.mergeStores(older, file(P.withLimits(base, 'dimp', 50, 50, BASE - 30 * 24 * H)), BASE, S.storedStores(K, T), T);
      S.writeStore(mc, K, T);
      const i1c = S.readStore(K, T);
      // an own time three days ahead is not used to stamp the import
      mem.clear();
      const farOwn = { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 20, 25, BASE).decks[0], limitsTs: BASE + 72 * H }] };
      mem.set(K, JSON.stringify(farOwn));
      const m2 = S.mergeStores(farOwn, file(P.withLimits(base, 'dimp', 50, 50, BASE - 30 * 24 * H)), BASE, S.storedStores(K, T), T);
      mem.clear();
      out = { slow: { lim: limOf(slow.data), restored: slow.restored }, fixed: limOf(fixed.data), quiet: { lim: limOf(quiet.data), restored: quiet.restored, stored: quietStored },
        i1b: { stamp: limOf(m).ts - (BASE + H), lim: limOf(i1b.data).l, restored: i1b.restored },
        i1c: { stamp: limOf(mc).ts - (BASE + H), lim: limOf(i1c.data).l, restored: i1c.restored }, far: limOf(m2).ts - BASE,
        edge: S.limitsSaveTime(K, { id: 'dimp', limitsTs: BASE + 24 * H }, BASE) - BASE };""")
    H = 3600 * 1000
    assert got["slow"]["lim"]["l"] == {"stock": 40, "ind": 45}, got["slow"]
    assert got["fixed"]["l"] == {"stock": 40, "ind": 45}, got["fixed"]
    assert got["quiet"]["lim"] == {"l": {"stock": 20, "ind": 25}, "ts": 2000} and got["quiet"]["restored"] is False
    assert got["quiet"]["stored"] == {"l": {"stock": 20, "ind": 25}, "ts": 2000}      # written back with the later time
    assert got["i1b"] == {"stamp": 1, "lim": {"stock": 50, "ind": 50}, "restored": False}, got["i1b"]
    assert got["i1c"] == {"stamp": 1, "lim": {"stock": 50, "ind": 50}, "restored": False}, got["i1c"]
    assert got["far"] == 0                                  # stamped at the import time, not after a time three days ahead
    assert got["edge"] == 24 * H + 1                        # exactly a day ahead is still believed


def test_a_guide_seen_date_after_today_is_seen_and_never_a_problem():
    """Jack (2026-11-08): guideSeen is this device's flag, not a record. Written while the phone's clock was ahead, its date
    can be after today: the records still read with no problem (no "이전에 저장한 기록을 읽지 못해 따로 보관해 두었어요"),
    the guide counts as seen, and the next write keeps it. A value that is not a date is still set aside, and the records'
    own dates keep their rule (a purchase dated after today is still a problem)."""
    got = run(LS + """mem.clear();
      const recs = { v: 1, decks: [{ id: 'db', name: 'b', createdAt: T, settings: { points: {} }, holdings: [{ t: '000010', nk: 'a', target: 1, rules: [] }],
        purchases: [{ t: '000010', qty: 1, price: 10000, date: T, ccy: 'KRW' }] }], guideSeen: '2026-11-20' };
      mem.set(K, JSON.stringify(recs));
      const r = S.readStore(K, T);
      const wrote = S.writeStore(S.withGuideSeen(r.data, T), K, T);
      const later = JSON.parse(mem.get(K)).guideSeen;
      const tomorrowBuy = { ...recs, decks: [{ ...recs.decks[0], purchases: [{ ...recs.decks[0].purchases[0], date: '2026-11-20' }] }] };
      out = { locked: r.locked, problems: r.problems, decks: r.data.decks.length, seen: S.guideSeenIn(r.data), wrote, later,
        notDate: S.checkStore({ v: 1, decks: [], guideSeen: 'x' }, T).problems, buy: S.checkStore(tomorrowBuy, T).problems.length };""")
    assert got["locked"] is False and got["problems"] == [] and got["decks"] == 1 and got["seen"] is True
    assert got["wrote"] is True and got["later"] == "2026-11-20"                # kept as it is (already seen)
    assert got["notDate"] == ["guideSeen: not a date"]
    assert got["buy"] == 1                                                         # a record dated after today: still a problem


def test_two_fast_clock_times_never_beat_a_believable_save_in_one_merge():
    """v19.3d2 review 6 (5a): the clock was 3 days fast during a 저장 of 20/25 and has been corrected; the records and this
    tab hold 20/25 stamped 72 h ahead, the side key holds 40/45 saved 1 h ago. 기록 불러오기 of a file without limits for
    that portfolio keeps the latest believable 저장, 40/45 with its time, whatever the order of the copies (two far-ahead
    times met first no longer turn into a real time inside the merge). Two far-ahead copies alone still keep the later one,
    written back with its own time (review 5, r5b slow)."""
    got = run(LS + """const H = 3600 * 1000, BASE = Date.now();
      const base = { v: 2, decks: [deckOf([['000010', 20]])] };
      const far = { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 20, 25, BASE).decks[0], limitsTs: BASE + 72 * H }] };
      mem.clear();
      mem.set(K, JSON.stringify(far));
      mem.set(SIDE, JSON.stringify({ v: 1, decks: { dimp: { limits: { stock: 40, ind: 45 }, ts: BASE - H } } }));
      const known = S.storedStores(K, T);
      const fileNo = S.parseImport(S.exportText(base), T);                  // the portfolio without limits
      const fwd = S.mergeStores(far, fileNo, BASE, known, T), rev = S.mergeStores(far, fileNo, BASE, [...known].reverse(), T);
      // two far-ahead copies only: the later raw time stays, with its time
      const far2 = { v: 2, decks: [{ ...P.withLimits(base, 'dimp', 40, 45, BASE).decks[0], limitsTs: BASE + 80 * H }] };
      const both = [S.mergeTabs(far, far2, T), S.mergeTabs(far2, far, T)].map((d) => limOf(d));
      mem.clear();
      out = { fwd: limOf(fwd), rev: limOf(rev), side: BASE - H, both, far2: BASE + 80 * H };""")
    assert got["fwd"] == {"l": {"stock": 40, "ind": 45}, "ts": got["side"]}, got["fwd"]
    assert got["rev"] == got["fwd"]                                    # the order of the copies does not matter
    assert got["both"] == [{"l": {"stock": 40, "ind": 45}, "ts": got["far2"]}] * 2


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
