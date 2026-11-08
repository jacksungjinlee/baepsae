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
