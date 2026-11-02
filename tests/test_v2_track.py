# -*- coding: utf-8 -*-
"""뱁새 2.0 내 덱 · 오늘 · 왜 움직였나 계산 (src/v2/track.js, v18.3 Part E) — Node 로 직접 돌려봐요.

추가로 넣을 돈: 규칙 깨짐 · 확인 필요 · 지켜봐요 · 목표 1.25배 초과(그만 살 차례 · 줄일 차례)는 건너뛰고, 가장 덜 담긴 종목부터,
한국·미국 모두 1주 단위, 남는 돈은 정확히 · 사지 않은 계획 종목(0주)에는 넣지 않아요 · 멈춘·실패한 데이터로는 계산하지 않아요 ·
계획대로 산 덱은 첫날 비중 표시도 건너뛰는 종목도 없어요.
코스피 비교: 같은 날짜(산 날 직전 종가 → 오늘 종가 = pxDate), 여러 날 샀으면 넣은 돈으로 가중 · 날짜가 안 맞으면 숫자 없음.
원금: 미국 매수는 기록한 환율로만 (없으면 원금·수익률 없음). 같은 업종 점 띠: 진짜 업종 · 같은 시장 · 5종목 이상, other·etc 는 절대 아님.
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


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write(f"export * from {json.dumps(os.path.join(ROOT, 'src/v2/track.js'))};\n"
                    f"export * as R from {json.dumps(os.path.join(ROOT, 'src/v2/rules.js'))};\n"
                    f"export * as E from {json.dumps(os.path.join(ROOT, 'src/v2/engine.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/track.mjs",
                            "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


HELPERS = """
const ctxOf = (stocks, corps, fx = 1300) => ({ state: { ok: true }, byT: new Map(stocks.map((s) => [s.t, s])),
  coByT: new Map((corps || []).map((c) => [c.t, c])), fx, pxDate: '2026-10-30' });
// A deck as 샀어요 stores it: rule books from engine.ruleBook, purchases at the given price (US with the plan's fx).
const mkDeck = (rows, fx = 1300) => ({ id: 'd1', name: 'deck', createdAt: '2026-10-01',
  holdings: rows.map((r) => ({ t: r.s.t, nk: r.s.nk, cls: r.s.cls, kind: 'core', target: r.target, plannedQty: r.qty,
    rules: T.E.ruleBook(r.s, r.co || null, r.points || {}, r.target) })),
  purchases: rows.filter((r) => r.qty > 0).map((r) => ({ t: r.s.t, date: r.date || '2026-10-01', qty: r.qty, price: r.price ?? r.s.price,
    ccy: r.s.cls === 'us' ? 'USD' : 'KRW', ...(r.s.cls === 'us' && r.fx !== null ? { fx: r.fx ?? fx } : {}) })) });
// A daily evaluation written by hand: only the fields addMoney reads (t, nk, qty, value, target, status, w; no band
// result, so the 1.25x edge is 1.25 x target).
const deOf = (rows) => { const total = rows.reduce((a, r) => a + r[1], 0); return { ok: true, weights: { ok: true }, unheld: [],
  holdings: rows.map(([t, value, px, target, status]) => ({ t, nk: 'N' + t, qty: value / px, value, target, status, w: value / total, rules: [] })) }; };
"""


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = "import * as T from './track.mjs';\n" + HELPERS + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def kr(t, **kw):
    s = {"t": t, "nk": "K" + t, "cls": "kr", "price": 10000.0, "roe": 10.0, "debt": 80.0, "dps": 500.0, "dps3": [500.0, 450.0, 400.0],
         "fy": 2025, "d1": 0.5, "ind": "machine", "indName": "기계", "vol": 30.0, "beta": 1.0, "val20": 1000.0, "etf": False}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def us(t, **kw):
    s = {"t": t, "nk": "U" + t, "cls": "us", "price": 100.0, "roe": 20.0, "debt": 60.0, "d1": 0.2, "ind": "soft", "indName": "소프트웨어",
         "vol": 25.0, "beta": 1.0, "val": 1000.0, "etf": False, "cap": 50.0}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


# ── 추가로 넣을 돈 ──
def test_add_money_skips_broken_check_watch_and_anything_above_125x_target():
    got = run("""
const de = deOf([['A', 1e6, 1e4, 0.125, 'broken'], ['B', 1e6, 1e4, 0.125, 'check'], ['C', 1e6, 1e4, 0.125, 'watch'],
                 ['D', 1.6e6, 1e4, 0.125, 'high'], ['E', 1.8e6, 1e4, 0.125, 'trim'],
                 ['F', 0.4e6, 1e4, 0.125, 'low'], ['G', 1e6, 1e4, 0.125, 'none'], ['H', 1.2e6, 1e4, 0.125, 'none']]);
const r = T.addMoney(de, 5e6);
out = { eligible: r.eligible, skipped: r.skipped, bought: r.buys.map((b) => b.t) };""")
    assert got["eligible"] == ["F", "G", "H"], got
    assert {s["t"]: s["why"] for s in got["skipped"]} == {"A": "broken", "B": "check", "C": "watch", "D": "high", "E": "trim"}
    assert set(got["bought"]) <= {"F", "G", "H"} and "F" in got["bought"], got


def test_add_money_fills_the_most_underweight_first_in_whole_shares_and_shows_the_money_left():
    # 600만원 덱, 목표 30% · 40% · 30%: A 100만(목표의 0.56배, 가장 덜 담김) · B 300만(정확히 1.25배: 아직 살 수 있음) · C 200만.
    # 50만원 → A 만 7주(1주 7만원) · 1만원 남음
    got = run("""
const de = deOf([['A', 1e6, 7e4, 0.3, 'low'], ['B', 3e6, 5e4, 0.4, 'none'], ['C', 2e6, 3e4, 0.3, 'none']]);
const small = T.addMoney(de, 5e5);
const big = T.addMoney(de, 3e6);
const tiny = T.addMoney(de, 2e4);
const zero = T.addMoney(de, 0);
// 둘 다 목표보다 적을 때: A(목표의 0.73배)가 C(0.91배)보다 먼저. 30만원이면 A 4주(28만원)로 A가 C보다 덜 담긴 동안만 사고 2만원 남아요.
const two = T.addMoney(deOf([['A', 1e6, 7e4, 0.25, 'low'], ['B', 3e6, 5e4, 0.45, 'none'], ['C', 1.5e6, 3e4, 0.3, 'none']]), 3e5);
out = { small, big, tiny: [tiny.buys, tiny.left, tiny.eligible.length], zero: [zero.buys, zero.left],
        two: [two.buys.map((b) => [b.t, b.shares, b.cost]), two.left] };""")
    s = got["small"]
    assert s["eligible"] == ["A", "B", "C"], s                   # 목표의 정확히 1.25배는 아직 살 수 있어요
    assert [(b["t"], b["shares"], b["cost"]) for b in s["buys"]] == [("A", 7, 490000)], s
    assert s["spent"] == 490000 and s["left"] == 10000
    b = got["big"]
    assert b["buys"][0]["t"] == "A", b                          # 가장 덜 담긴 종목이 먼저
    assert all(isinstance(x["shares"], int) and x["shares"] > 0 for x in b["buys"])
    assert all(abs(x["cost"] - x["shares"] * {"A": 7e4, "B": 5e4, "C": 3e4}[x["t"]]) < 1e-6 for x in b["buys"])   # 1주 단위
    assert b["spent"] <= 3e6 and b["spent"] + b["left"] == 3e6
    costs = {x["t"]: x["cost"] for x in b["buys"]}
    T = 6e6 + 3e6
    for t, v0, tg in (("A", 1e6, 0.3), ("B", 3e6, 0.4), ("C", 2e6, 0.3)):
        assert v0 + costs.get(t, 0) <= 1.25 * tg * T + 1e-6, (t, costs)
    assert costs["A"] == max(costs.values()), costs
    assert got["tiny"] == [[], 20000, 3]                         # 1주도 못 사면 아무것도 사지 않고 그대로 남아요
    assert got["zero"] == [[], 0]
    assert got["two"] == [[["A", 4, 280000]], 20000], got["two"]


def test_add_money_never_takes_a_stock_above_125x_target_even_when_one_share_is_big():
    # A: 1주 100만원, 지금 1주 · 목표 5%. 400만원을 더 넣으면 덱 3,100만원 · A 목표 155만원 · 1.25배 193.75만원.
    # 목표까지 55만원이 모자라(반 주 넘게) 보통이면 1주를 더 사지만, 그러면 200만원 = 목표의 1.29배라 사지 않아요.
    got = run("""
const de = deOf([['A', 1e6, 1e6, 0.05, 'low'], ['B', 26e6, 1e4, 0.95, 'none']]);
const r = T.addMoney(de, 4e6);
out = { buys: r.buys.map((b) => [b.t, b.shares]), eligible: r.eligible, left: r.left, spent: r.spent };""")
    assert got["eligible"] == ["A", "B"], got
    assert all(t != "A" for t, _ in got["buys"]) and [t for t, _ in got["buys"]] == ["B"], got
    assert got["spent"] + got["left"] == 4e6


def test_add_money_edge_exactly_125x_is_still_bought_just_above_is_skipped():
    # Part C 의 판정(evaluateDeck)으로: 두 종목 목표 50%, 첫 종목 비중이 목표의 정확히 1.25배 · 그보다 조금 위
    got = run("""
const res = {};
for (const [k, w] of Object.entries(CASES)) {
  const a = { ...A, price: w * 1000 }, b = { ...B, price: (1 - w) * 1000 };
  // bought at the same price (as-bought weights 50% · 50%: no gap), then today's prices moved
  const d = mkDeck([{ s: a, target: 0.5, qty: 10000, price: 500 }, { s: b, target: 0.5, qty: 10000, price: 500 }]);
  const de = T.R.evaluateDeck(d, ctxOf([a, b], []));
  const r = T.addMoney(de, 1e9);
  res[k] = { st: de.holdings.map((x) => x.status), eligible: r.eligible, skipped: r.skipped.map((s) => s.t + ':' + s.why),
    edge: Math.round(de.holdings[0].rules.find((x) => x.id === 'band').bands[1] * 1e9) / 1e9 };
}
out = res;""", CASES={"1.25": 0.625, "above": 0.64}, A=kr("000100"), B=kr("000200"))
    assert got["1.25"]["st"][0] == "none" and "000100" in got["1.25"]["eligible"], got
    assert got["above"]["st"][0] == "high" and got["above"]["skipped"] == ["000100:high"], got
    assert got["above"]["edge"] == 0.625 and got["1.25"]["edge"] == 0.625, got          # Part C 의 경계 그대로


def test_add_money_us_shares_are_whole_and_priced_in_won():
    got = run("""
const d = mkDeck([{ s: K, target: 0.5, qty: 30 }, { s: U, target: 0.5, qty: 1 }]);
const de = T.R.evaluateDeck(d, ctxOf([K, U], [], 1300));
const r = T.addMoney(de, 1e6);
out = r.buys.map((b) => [b.t, b.shares, b.cost]);""", K=kr("000100", price=10000.0), U=us("AAPL", price=100.0))
    by = {t: (sh, c) for t, sh, c in got}
    assert "AAPL" in by and by["AAPL"][1] == by["AAPL"][0] * 130000 and isinstance(by["AAPL"][0], int), got


def test_add_money_never_runs_on_stale_failed_or_unpriced_data_and_skips_unbought_planned_stocks():
    got = run("""
const d = mkDeck([{ s: A, target: 0.4, qty: 10 }, { s: B, target: 0.4, qty: 10 }, { s: C, target: 0.2, qty: 0 }]);
const fresh = T.R.evaluateDeck(d, ctxOf([A, B, C], []));
const stale = T.R.evaluateDeck(d, { ...ctxOf([A, B, C], []), state: { ok: false, why: 'stale', days: 6 } });
const noPrice = T.R.evaluateDeck(d, ctxOf([A, { ...B, price: null }, C], []));
const r = T.addMoney(fresh, 1e6);
out = { stale: T.addMoney(stale, 1e6), fail: T.addMoney({ ok: false, why: 'fail' }, 1e6), noPrice: T.addMoney(noPrice, 1e6),
        unheld: r.unheld, eligible: r.eligible, bought: r.buys.map((b) => b.t) };""", A=kr("000100"), B=kr("000200"), C=kr("000300"))
    assert got["stale"] == {"ok": False} and got["fail"] == {"ok": False} and got["noPrice"] == {"ok": False}
    assert got["unheld"] == ["000300"] and "000300" not in got["eligible"] and "000300" not in got["bought"], got


def test_a_deck_bought_exactly_as_planned_has_no_band_flags_and_no_skips_on_day_one():
    # 매수 계획 그대로(engine.size → planShares, 남는 돈 · 1주도 못 산 계획 종목 포함)로 샀어요 → 같은 날 데이터로 점검
    stocks = [kr(f"0001{i}0", nk=f"S{i}", ind=f"g{i}", indName=f"g{i}", price=p) for i, p in enumerate([73000.0, 21450.0, 158000.0, 9870.0])]
    stocks.append(kr("000500", nk="BIG", ind="g5", indName="g5", price=25_000_000.0))     # 1주가 예산보다 비싸요 → 0주
    got = run("""
const st = { ...T.E.defaultSettings(), mix: 'kr', count: 5, maxPct: 25, method: 'even' };
const amount = 1e7;
const sz = T.E.size({ picks: STOCKS.map((s, i) => ({ t: s.t, s, total: 80 - i })), cushion: [], settings: st, amountWon: amount });
const plan = T.E.planShares(sz.items, amount, 1300);
const d = { id: 'd1', name: 'deck', createdAt: '2026-10-30',
  holdings: plan.rows.map((x) => ({ t: x.t, nk: x.s.nk, cls: x.s.cls, kind: x.kind, target: x.targetW, plannedQty: x.shares,
    rules: T.E.ruleBook(x.s, null, st.points, x.targetW) })),
  purchases: plan.rows.filter((x) => x.shares > 0).map((x) => ({ t: x.t, date: '2026-10-30', qty: x.shares, price: x.s.price, ccy: 'KRW' })) };
const de = T.R.evaluateDeck(d, ctxOf(STOCKS, []));
const r = T.addMoney(de, 3e6);
out = { ok: sz.ok, left: plan.left, zero: plan.rows.filter((x) => !x.shares).map((x) => x.t), st: de.holdings.map((x) => [x.t, x.status]),
  unheld: de.unheld, skipped: r.skipped, eligible: r.eligible };""", STOCKS=stocks)
    assert got["ok"] and got["zero"] == ["000500"] and got["left"] > 0, got
    assert got["unheld"] == ["000500"], got                              # 0주 계획 종목은 점검하지 않아요
    assert all(s == "none" for _, s in got["st"]), got["st"]              # 첫날 비중 표시 없음
    assert got["skipped"] == [] and len(got["eligible"]) == 4, got        # 추가로 넣을 돈이 건너뛰는 종목 없음


# ── 원금 · 코스피 비교 ──
IDX = {"asOf": "2026-10-30", "rows": [["2026-09-29", 100.0], ["2026-09-30", 110.0], ["2026-10-01", 120.0], ["2026-10-02", 121.0],
                                      ["2026-10-30", 132.0]]}


def test_kospi_comparison_uses_the_same_dates_and_weights_purchases_by_the_money_put_in():
    got = run("""
const deck = (ps) => ({ purchases: ps.map(([date, qty, price, ccy, fx]) => ({ t: 'X', date, qty, price, ccy: ccy || 'KRW', ...(fx ? { fx } : {}) })) });
out = {
  one: T.indexSince(deck([['2026-10-01', 1, 1e6]]), IDX, '2026-10-30'),
  sameDay: T.indexSince(deck([['2026-10-31', 1, 1e6]]), IDX, '2026-10-30'),
  two: T.indexSince(deck([['2026-10-01', 1, 1e6], ['2026-10-02', 3, 1e6]]), IDX, '2026-10-30'),
  usFx: T.indexSince(deck([['2026-10-01', 1, 1e6], ['2026-10-02', 1, 1000, 'USD', 3000]]), IDX, '2026-10-30'),
  usNoFx: T.indexSince(deck([['2026-10-01', 1, 1e6], ['2026-10-02', 1, 1000, 'USD']]), IDX, '2026-10-30'),
  endDiffers: T.indexSince(deck([['2026-10-01', 1, 1e6]]), IDX, '2026-10-31'),
  asOfDiffers: T.indexSince(deck([['2026-10-01', 1, 1e6]]), { ...IDX, asOf: '2026-10-29' }, '2026-10-30'),
  beforeHistory: T.indexSince(deck([['2026-09-29', 1, 1e6]]), IDX, '2026-10-30'),
  unsorted: T.indexSince(deck([['2026-10-01', 1, 1e6]]), { asOf: '2026-10-30', rows: [IDX.rows[1], IDX.rows[0], IDX.rows[4]] }, '2026-10-30'),
  missing: T.indexSince(deck([['2026-10-01', 1, 1e6]]), null, '2026-10-30'),
};""", IDX=IDX)
    # 10월 1일 산 덱: 9월 30일 종가(110) → 10월 30일 종가(132) = +20%
    assert got["one"]["ok"] and abs(got["one"]["ret"] - 0.2) < 1e-12 and got["one"]["start"] == "2026-10-01" and got["one"]["end"] == "2026-10-30"
    assert got["sameDay"]["ok"] and abs(got["sameDay"]["ret"]) < 1e-12        # 오늘 종가로 오늘 산 덱: 0%
    # 100만원은 10월 1일(110 → 132), 300만원은 10월 2일(120 → 132): (100×1.2 + 300×1.1) / 400 − 1 = 12.5%
    assert abs(got["two"]["ret"] - 0.125) < 1e-12, got["two"]
    assert abs(got["usFx"]["ret"] - (1e6 * 1.2 + 3e6 * 1.1) / 4e6 + 1) < 1e-12   # 미국 매수는 기록한 환율의 원화로 가중
    for k in ("usNoFx", "endDiffers", "asOfDiffers", "beforeHistory", "unsorted", "missing"):
        assert got[k]["ok"] is False, (k, got[k])


def test_money_put_in_value_and_return_and_us_purchases_without_a_rate():
    got = run("""
const d = mkDeck([{ s: A, target: 0.5, qty: 10, price: 8000 }, { s: U, target: 0.5, qty: 1, price: 90 }], 1250);
const de = T.R.evaluateDeck(d, ctxOf([A, U], [], 1300));
const noFx = mkDeck([{ s: A, target: 0.5, qty: 10, price: 8000 }, { s: U, target: 0.5, qty: 1, price: 90, fx: null }]);
const de2 = T.R.evaluateDeck(noFx, ctxOf([A, U], [], 1300));
const c = ctxOf([A, U], [], 1300);
out = { m: T.deckMoney(d, de, c), noFx: T.deckMoney(noFx, de2, c), stale: T.deckMoney(d, { ok: false, why: 'stale' }, c),
        noPrice: T.deckMoney(d, de, ctxOf([A, { ...U, price: null }], [], 1300)) };""",
              A=kr("000100", price=10000.0), U=us("AAPL", price=100.0))
    m = got["m"]
    assert m["ok"] and m["value"] == 10 * 10000 + 130000 and m["cost"] == 80000 + 90 * 1250, m
    assert abs(m["ret"] - (230000 / 192500 - 1)) < 1e-12 and m["gain"] == 230000 - 192500 and m["start"] == "2026-10-01"
    assert abs(m["per"]["000100"]["ret"] - 0.25) < 1e-12 and abs(m["per"]["AAPL"]["ret"] - (130000 / 112500 - 1)) < 1e-12
    n = got["noFx"]                                            # 환율 없이 저장된 미국 매수: 오늘 환율로 바꾸지 않아요
    assert n["ok"] and n["cost"] is None and n["ret"] is None and n["noFx"] == ["AAPL"] and n["per"]["AAPL"]["cost"] is None
    assert got["stale"]["ok"] is False and got["noPrice"]["ok"] is False     # 값을 모르는 종목이 있으면 평가 금액도 없어요


def test_today_move_of_the_deck_needs_every_d1_and_no_us_stock():
    got = run("""
const mk = (rows) => ({ ok: true, weights: { ok: true }, holdings: rows.map(([value, d1, cls]) => ({ value, d1, cls: cls || 'kr' })) });
out = [T.deckDayChange(mk([[110, 10], [90, -10]])), T.deckDayChange(mk([[110, 10], [90, null]])), T.deckDayChange(mk([[110, 10], [90, -10, 'us']])),
       T.deckDayChange({ ok: false })];""")
    assert abs(got[0] - ((200 / (100 + 100)) - 1) * 100) < 1e-9
    assert got[1:] == [None, None, None]


# ── 같은 업종 점 띠 ──
def test_dot_strip_needs_a_real_group_with_five_members_in_the_same_market():
    base = [kr(f"0002{i}0", ind="semi", indName="반도체", d1=-1.0 - i) for i in range(5)]
    got = run("""
const me = S[0];
const g = (stocks, s = me) => T.peerGroup(s, stocks);
const four = S.slice(0, 4);
const usSame = [0, 1, 2].map((i) => ({ ...S[0], t: 'U' + i, cls: 'us', price: 10 }));
out = {
  five: g(S), four: g(four),
  fourPlusUs: g([...four, ...usSame]),
  pref: g([...four, { ...S[1], t: '000205' }]), etf: g([...four, { ...S[1], t: '000990', etf: true }]),
  noD1: g([...four, { ...S[4], d1: null }]),
  other: g(S.map((s) => ({ ...s, ind: 'other' })), { ...me, ind: 'other' }),
  etc: g(S.map((s) => ({ ...s, ind: 'etc' })), { ...me, ind: 'etc' }),
  none: g(S.map((s) => { const { ind, ...x } = s; return x; }), (() => { const { ind, ...x } = me; return x; })()),
  meNoD1: g(S, { ...me, d1: null }),
};""", S=base)
    assert got["five"]["ok"] and got["five"]["n"] == 5 and got["five"]["fell"] == 5, got["five"]
    for k in ("four", "fourPlusUs", "pref", "etf", "noD1", "other", "etc", "none", "meNoD1"):
        assert got[k]["ok"] is False, (k, got[k])


def test_the_group_fell_together_only_when_the_stock_and_80_percent_of_the_group_fell():
    got = run("""
const mk = (d1s) => d1s.map((d1, i) => ({ ...S0, t: '0003' + i + '0', d1 }));
const tog = (d1s) => { const s = mk(d1s); return T.peerGroup(s[0], s); };
out = { all: tog([-6, -3, -2, -1, -0.5]), four: tog([-6, -3, -2, -1, 0.4]), three: tog([-6, -3, -2, 1, 0.4]), up: tog([6, -3, -2, -1, -0.5]),
        avg: tog([-6, -3, -2, -1, -0.5]).avg, items: tog([-6, -3, -2, -1, -0.5]).items.length };""", S0=kr("000300", ind="semi"))
    assert got["all"]["together"] and got["four"]["together"], got          # 5개 중 4개(80%) 이상
    assert not got["three"]["together"] and not got["up"]["together"], got  # 60% · 이 종목은 올랐어요
    assert abs(got["avg"] - (-12.5 / 5)) < 1e-12 and got["items"] == 5


def test_subject_particle_follows_the_last_syllable():
    got = run("out = NAMES.map((n) => T.endsInBatchim(n));", NAMES=["KB금융", "현대차", "삼성전자", "LG에너지솔루션", "NAVER", "SK", "", "기아"])
    assert got == [True, False, False, True, False, False, False, False]
