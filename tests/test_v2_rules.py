# -*- coding: utf-8 -*-
"""뱁새 2.0 매일 점검 (src/v2/rules.js, v18.3 Part C) — Node 로 직접 돌려봐요.

판정 순서(규칙 깨짐 → 확인 필요·지켜봐요 → 비중 → 할 일 없음) · 비중 경계 0.75 / 1.25 / 1.4 · 가격은 규칙을 움직이지 않아요 ·
멈춘·실패한 데이터로는 아무 판정도 하지 않아요 · 배당 감소는 확인 필요(혼자서는 규칙 깨짐 아님) · '실제로 줄였어요' → 규칙 깨짐,
'줄인 게 아니에요' → 그 보고서만 해제 · 산 때 있던 자료가 오늘 비면 확인 필요 · 산 때 보고서(since)보다 새 보고서만 셈 ·
금융회사는 부채비율 규칙 없음 · 영업이익은 [올해, 작년, 재작년] 순서.
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
            f.write(f"export * from {json.dumps(os.path.join(ROOT, 'src/v2/rules.js'))};\n"
                    f"export * as E from {json.dumps(os.path.join(ROOT, 'src/v2/engine.js'))};\n"
                    f"export * as S from {json.dumps(os.path.join(ROOT, 'src/v2/store.js'))};\n"
                    f"export * as D from {json.dumps(os.path.join(ROOT, 'src/v2/deckcalc.js'))};\n"
                    f"export * as L from {json.dumps(os.path.join(ROOT, 'src/v2/load.js'))};\n"
                    f"export * as F from {json.dumps(os.path.join(ROOT, 'src/v2/format.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/rules.mjs",
                            "--log-level=warning", "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


# deck(stocks, corps, holdings, opts): a deck bought at purchase-time data `buy` (rule books from engine.ruleBook), then
# checked against today's data `now`. Helper JS so every test builds rule books the way 샀어요 does.
HELPERS = """
const ctxOf = (stocks, corps, fx = 1300, state = { ok: true }) => ({ state, byT: new Map(stocks.map((s) => [s.t, s])),
  coByT: new Map((corps || []).map((c) => [c.t, c])), fx, pxDate: '2026-10-30' });
const book = (s, co, points, target) => R.E.ruleBook(s, co || null, points || {}, target);
const mkDeck = (rows, extra = {}) => ({ id: 'd1', name: 'deck', createdAt: '2026-10-01',
  holdings: rows.map((r) => ({ t: r.s.t, nk: r.s.nk, cls: r.s.cls, kind: 'core', target: r.target, rules: r.rules ?? book(r.s, r.co, r.points, r.target) })),
  purchases: rows.filter((r) => r.qty > 0).map((r) => ({ t: r.s.t, date: '2026-10-01', qty: r.qty, price: r.s.price, ccy: r.s.cls === 'us' ? 'USD' : 'KRW' })),
  ...extra });
const one = (deck, stocks, corps, fx) => R.evaluateDeck(deck, ctxOf(stocks, corps, fx));
const hold = (ev, t) => ev.holdings.find((x) => x.t === t);
"""


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = "import * as R from './rules.mjs';\n" + HELPERS + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())              # a file: fixtures are too big for -e
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def kr(t, **kw):
    s = {"t": t, "nk": "K" + t, "cls": "kr", "price": 10000.0, "roe": 10.0, "debt": 80.0, "dps": 500.0,
         "dps3": [500.0, 450.0, 400.0], "fy": 2025, "d1": 0.5, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def co(t, op=(120.0, 110.0, 100.0), fy=2025, **kw):
    c = {"t": t, "op": list(op), "fy": fy}
    c.update(kw)
    return c


def us(t, **kw):
    s = {"t": t, "nk": "U" + t, "cls": "us", "price": 100.0, "roe": 20.0, "debt": 60.0, "d1": 0.2, "ind": "soft", "indName": "소프트웨어"}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def at(s, **kw):
    """Today's row: the same stock with some fields changed (None = blank today)."""
    x = dict(s)
    for k, v in kw.items():
        if v is None:
            x.pop(k, None)
        else:
            x[k] = v
    return x


# A deck of two equal halves bought at 2024 data (since = 2024), checked on today's 2025 report.
def pair(a_now, a_co_now, b_now=None, points=None, a_buy=None, a_co_buy=None, qa=10, qb=10):
    a_buy = a_buy or at(a_now, fy=2024)
    a_co_buy = a_co_buy or {**a_co_now, "fy": 2024}
    b_now = b_now or kr("000200")
    return {"a_buy": a_buy, "a_co_buy": a_co_buy, "a_now": a_now, "a_co_now": a_co_now, "b": b_now,
            "points": points or {"stable": 3, "profit": 2}, "qa": qa, "qb": qb}


PAIR_JS = """
const d = mkDeck([{ s: P.a_buy, co: P.a_co_buy, points: P.points, target: 0.5, qty: P.qa },
                  { s: P.b, co: null, points: P.points, target: 0.5, qty: P.qb }], typeof EXTRA === 'undefined' ? {} : EXTRA);
const ev = one(d, [P.a_now, P.b], [P.a_co_now]);
const h = hold(ev, P.a_now.t);
"""


# ── 판정 순서 ──
def test_decision_order_sell_then_check_then_keep_then_band_then_nothing():
    a = kr("000100", dps3=[300.0, 500.0, 450.0], dps=300.0, debt=300.0)           # 2025 보고서: 배당 500 → 300, 부채비율 300%
    co_now = co("000100", op=(80.0, 100.0, 120.0))                              # 영업이익 2년 연속 감소
    buy = at(a, fy=2024, dps=500.0, dps3=[500.0, 450.0, 400.0], debt=150.0)
    base = pair(a, co_now, a_buy=buy, a_co_buy=co("000100", op=(100.0, 120.0, 90.0), fy=2024), qa=30, qb=10)   # 비중 75%
    cut = {"confirms": [{"t": "000100", "rule": "divCut", "fy": 2025, "a": 500.0, "b": 300.0, "answer": "cut", "at": "2026-11-01"}]}
    got = run("const outs = [];\n"
              "for (const [P, EXTRA] of CASES) { " + PAIR_JS.replace("const ", "let ") + " outs.push({ s: h.status, codes: h.reasons.map((r) => r.code) }); }\n"
              "out = outs;",
              CASES=[[base, cut], [base, {}],
                     [pair(at(a, dps3=[500.0, 500.0, 450.0], dps=500.0), co_now, a_buy=buy, a_co_buy=co("000100", op=(100.0, 120.0, 90.0), fy=2024), qa=30, qb=10), {}],
                     [pair(at(a, dps3=[500.0, 500.0, 450.0], dps=500.0, debt=100.0), co("000100", op=(130.0, 100.0, 120.0)), a_buy=buy,
                           a_co_buy=co("000100", op=(100.0, 120.0, 90.0), fy=2024), qa=30, qb=10), {}],
                     [pair(at(a, dps3=[500.0, 500.0, 450.0], dps=500.0, debt=100.0), co("000100", op=(130.0, 100.0, 120.0)), a_buy=buy,
                           a_co_buy=co("000100", op=(100.0, 120.0, 90.0), fy=2024), qa=10, qb=10), {}]])
    # 1) 실제로 줄였다고 답한 배당 삭감 → 규칙 깨짐 (부채비율·영업이익·비중도 이유로 같이 남아요)
    assert got[0]["s"] == "broken" and got[0]["codes"][0] == "divCut" and {"debtOver", "opFell2", "band"} <= set(got[0]["codes"]), got[0]
    # 2) 답하지 않은 배당 감소 → 확인 필요 (지켜봐요보다 먼저)
    assert got[1]["s"] == "check" and got[1]["codes"][0] == "divDrop", got[1]
    # 3) 배당은 그대로, 부채비율·영업이익이 어긋남 → 지켜봐요
    assert got[2]["s"] == "watch" and set(got[2]["codes"]) == {"debtOver", "opFell2", "band"}, got[2]
    # 4) 규칙은 다 지켜지고 비중만 목표의 1.5배 → 줄일 차례
    assert got[3]["s"] == "trim" and got[3]["codes"] == ["band"], got[3]
    # 5) 아무것도 없으면 할 일 없음
    assert got[4]["s"] == "none" and got[4]["codes"] == [], got[4]


# ── 비중 경계 ──
def test_band_edges_exactly_at_075_125_14_stay_in_the_milder_band():
    # 두 종목 목표 50% · 50%. 값을 바꿔 첫 종목 비중을 정확히 목표 × r 로 만들어요. 1만 주씩이라 한 주의 여유는 아주 작아요.
    cases = {"0.75": 0.375, "below 0.75": 0.37, "1.25": 0.625, "above 1.25": 0.63, "1.4": 0.7, "above 1.4": 0.71, "1.0": 0.5}
    got = run("""
const out2 = {};
for (const [k, w] of Object.entries(CASES)) {
  const a = { ...A, price: w * 1000 / 10000 }, b = { ...B, price: (1 - w) * 1000 / 10000 };
  const d = mkDeck([{ s: A, target: 0.5, qty: 10000 }, { s: B, target: 0.5, qty: 10000 }]);
  const ev = one(d, [a, b], []);
  out2[k] = [hold(ev, A.t).status, hold(ev, A.t).reasons.map((r) => r.band || r.code)];
}
out = out2;""", CASES=cases, A=kr("000100"), B=kr("000200"))
    assert got["1.0"][0] == "none"
    assert got["0.75"][0] == "none" and got["below 0.75"][0] == "low", got        # 0.75 미만부터 먼저 살 차례
    assert got["1.25"][0] == "none" and got["above 1.25"][0] == "high", got       # 1.25 초과부터 그만 살 차례
    assert got["1.4"][0] == "high" and got["above 1.4"][0] == "trim", got         # 1.4 초과부터 줄일 차례


# rows: [t, target, qty bought, purchase price, plannedQty?, planPx?, cls?]; a case: [name, rows, today's prices, fx?, planFx?]
BAND_JS = """
const outs = {}, gaps = {};
for (const [k, rows, prices, fx, planFx] of CASES) {
  const cls = (t) => (rows.find((r) => r[0] === t) || [])[6] || 'kr';
  const holdings = rows.map(([t, tg, , , pq, ppx, c]) => ({ t, nk: t, cls: c || 'kr', kind: 'core', target: tg,
    ...(pq != null ? { plannedQty: pq } : {}), ...(ppx != null ? { planPx: ppx } : {}),
    rules: [{ id: 'band', kind: 'band', check: 'checked', target: tg, bands: [0.75 * tg, 1.25 * tg, 1.4 * tg] }] }));
  const purchases = rows.filter((r) => r[2] > 0).map(([t, , q, px]) => ({ t, date: '2026-10-01', qty: q, price: px, ccy: cls(t) === 'us' ? 'USD' : 'KRW' }));
  const ev = one({ id: 'd', name: 'x', holdings, purchases, ...(planFx ? { planFx } : {}) },
    Object.entries(prices).map(([t, price]) => ({ t, cls: cls(t), price })), [], fx || 1300);
  outs[k] = Object.fromEntries(ev.holdings.map((h) => [h.t, [h.status, Math.round(h.w * 1000) / 10]]));
  gaps[k] = Object.fromEntries(ev.holdings.map((h) => [h.t, Math.round(h.rules.find((r) => r.id === 'band').gap * 1000) / 10]));
}
out = { ...outs, gaps };"""


def test_one_expensive_share_is_never_hidden_and_never_told_to_sell_its_only_share():
    # 두 종목 목표 50% · 50%, 산 날 반반: A 1주 100만원 · B 100주 1만원. 그 뒤 A 만 오르거나 내려요.
    rows = [["A", 0.5, 1, 1000000.0], ["B", 0.5, 100, 10000.0]]
    cases = [[f"x{m}", rows, {"A": 1000000.0 * m, "B": 10000.0}] for m in (1.5, 2, 3, 5, 10, 0.3)]
    got = run(BAND_JS, CASES=cases)
    assert got["x1.5"]["A"][0] == "none", got                                   # 60%: 1.25배(62.5%) 안
    for m in ("x2", "x3", "x5", "x10"):                                         # 한 주짜리 비싼 종목도 그만 살 차례는 떠요
        assert got[m]["A"][0] == "high" and got[m]["B"][0] == "low", (m, got[m])
    assert got["x10"]["A"] == ["high", 90.9], got["x10"]                        # 하나뿐인 주식을 팔면 더 멀어져요: 줄일 차례 아님
    assert got["x0.3"]["A"][0] == "low" and got["x0.3"]["B"][0] == "trim", got["x0.3"]   # B 100주는 팔수록 가까워져요
    # 목표 10% 인 A 1주 10만원 · B 90주. A 가 7만원이 되면 7.2% (7.5% 아래) 지만, 1주 더 사면 13.5% 로 목표에서 더 멀어져요 → 먼저 살 차례 아님
    small = [["A", 0.1, 1, 100000.0], ["B", 0.9, 90, 10000.0]]
    got2 = run(BAND_JS, CASES=[["overshoot", small, {"A": 70000.0, "B": 10000.0}], ["far", small, {"A": 40000.0, "B": 10000.0}]])
    assert got2["overshoot"]["A"] == ["none", 7.2], got2
    assert got2["far"]["A"][0] == "low", got2                                    # 4.3%: 1주 사면 8.5%, 더 가까워져요


def test_the_reviewers_cases_meritz_four_shares_and_one_share_at_91_percent():
    # 장기 우량주 300만원 (실제 데이터): 6종목 중 3종목만 샀어요(나머지 0주). 메리츠금융지주 4주 · 한미반도체 3주 · 리노공업 9주.
    plan = [["M", 0.2, 4, 133200.0], ["H", 0.161, 3, 182700.0], ["L", 0.171, 9, 56100.0], ["X", 0.168, 0, 0], ["Y", 0.176, 0, 0], ["Z", 0.124, 0, 0]]
    px = {"M": 133200.0, "H": 182700.0, "L": 56100.0}
    two = [["A", 0.5, 1, 1000000.0], ["B", 0.5, 100, 10000.0]]
    got = run(BAND_JS, CASES=[["day1", plan, px], ["x2", plan, {**px, "M": 266400.0}], ["x3", plan, {**px, "M": 399600.0}],
                              ["91%", two, {"A": 10000000.0, "B": 10000.0}]])
    assert set(x[0] for x in got["day1"].values()) == {"none"}, got["day1"]     # 계획대로 산 날은 아무것도 없음
    assert got["x2"]["M"] == ["high", 50.3] and got["x3"]["M"] == ["trim", 60.3], got   # 3배면 37.6% 목표의 1.61배 → 줄일 차례
    assert got["91%"]["A"] == ["high", 90.9], got["91%"]                        # 1주로 91%: 그만 살 차례, 줄일 차례 아님


def test_the_plans_rounding_gap_widens_only_its_own_side():
    # 목표 50% · 50% 인데 1주 값 때문에 계획이 60% · 40% (A 3주 20만원 · B 4주 10만원, g = +10%p · −10%p). 계획대로 샀어요.
    rows = [["A", 0.5, 3, 200000.0, 3, 200000.0], ["B", 0.5, 4, 100000.0, 4, 100000.0]]
    got = run(BAND_JS, CASES=[["day1", rows, {"A": 200000.0, "B": 100000.0}],
                              # A 가 올라 70%: 1.25배 선 62.5% + 10%p = 72.5% 안 → 할 일 없음 (계획의 반올림은 탓하지 않아요)
                              ["A up a bit", rows, {"A": 311111.0, "B": 100000.0}],
                              # A 가 더 올라 76%: 72.5% 를 넘음 → 그만 살 차례 · B 24%: 37.5% − 10%p = 27.5% 아래 → 먼저 살 차례
                              ["A up more", rows, {"A": 422222.0, "B": 100000.0}],
                              # A 가 내려 45%: 낮은 쪽은 넓히지 않아요(37.5% 그대로) → 할 일 없음 · B 55% 도 62.5% 안
                              ["A down", rows, {"A": 109090.0, "B": 100000.0}],
                              # A 가 더 내려 30%: 37.5% 아래 → 먼저 살 차례 (넓히지 않은 쪽)
                              ["A down more", rows, {"A": 57142.0, "B": 100000.0}]])
    assert got["gaps"]["day1"] == {"A": 10.0, "B": -10.0}, got["gaps"]
    assert set(x[0] for x in got["day1"].values()) == {"none"}, got["day1"]
    assert got["A up a bit"]["A"][0] == "none" and got["A up a bit"]["B"][0] == "none", got["A up a bit"]
    assert got["A up more"]["A"][0] == "high" and got["A up more"]["B"][0] == "low", got["A up more"]
    assert got["A down"]["A"][0] == "none" and got["A down"]["B"][0] == "none", got["A down"]
    assert got["A down more"]["A"][0] == "low", got["A down more"]


FIVE = [[t, 0.2, 10, 10000.0, 10, 10000.0] for t in "ABCDE"]
FIVE_PX = {t: 10000.0 for t in "ABCDE"}


def test_buying_more_than_planned_or_a_price_typo_never_widens_the_bands():
    # 5종목 20%씩, 계획 10주씩. 샀어요에서 A 를 60주로 적으면 A 60% (목표의 3배): 계획이 아니라 사용자가 만든 차이라 잡아요.
    over = [["A", 0.2, 60, 10000.0, 10, 10000.0]] + FIVE[1:]
    typo = [["A", 0.2, 10, 100000.0, 10, 10000.0]] + FIVE[1:]                 # 가격을 10배로 잘못 적음
    got = run(BAND_JS, CASES=[["over", over, FIVE_PX], ["plain", FIVE, {**FIVE_PX, "A": 20000.0}], ["typo", typo, {**FIVE_PX, "A": 20000.0}]])
    assert got["over"]["A"] == ["trim", 60.0] and all(got["over"][t][0] == "low" for t in "BCDE"), got["over"]
    assert got["gaps"]["over"]["A"] == 0 and got["gaps"]["typo"]["A"] == 0, got["gaps"]    # 차이는 계획에서만
    assert got["typo"] == got["plain"] and got["typo"]["A"] == ["trim", 33.3], (got["typo"], got["plain"])   # 오타가 숨기지 않아요


def test_a_currency_move_changes_us_weights_and_is_flagged():
    # 미국 U 목표 10% (13주 $100, 계획 환율 1,300원) · 한국 K 90% (1,521주 1만원). 계획대로 샀어요.
    rows = [["U", 0.1, 13, 100.0, 13, 100.0, "us"], ["K", 0.9, 1521, 10000.0, 1521, 10000.0]]
    got = run(BAND_JS, CASES=[["day1", rows, {"U": 100.0, "K": 10000.0}, 1300, 1300],
                              ["dollar x2", rows, {"U": 100.0, "K": 10000.0}, 2600, 1300],
                              ["U+20% dollar+20%", rows, {"U": 120.0, "K": 10000.0}, 1560, 1300],
                              ["U+20% dollar same", rows, {"U": 120.0, "K": 10000.0}, 1300, 1300]])
    assert got["day1"]["U"] == ["none", 10.0], got["day1"]
    assert got["dollar x2"]["U"] == ["trim", 18.2], got["dollar x2"]                     # 환율만 두 배여도 잡아요
    assert got["U+20% dollar+20%"]["U"] == ["high", 13.8], got                           # 1.38배: 1.25배 선 넘음, 1.4배 선 안
    assert got["U+20% dollar same"]["U"] == ["none", 11.8], got


def test_legacy_decks_without_plan_prices_use_planned_quantities_at_the_paid_price():
    # 출시 밤 ~ 이 변경 사이에 저장된 덱: planPx · planFx 가 없어요. plannedQty x 평균 매수가로 계획 비중을 만들어요.
    legacy = [["A", 0.5, 3, 200000.0, 3], ["B", 0.5, 4, 100000.0, 4]]                    # 계획 60% · 40% (반올림)
    over = [["A", 0.2, 60, 10000.0, 10]] + [[t, 0.2, 10, 10000.0, 10] for t in "BCDE"]
    us = [["U", 0.1, 13, 100.0, 13, None, "us"], ["K", 0.9, 1521, 10000.0, 1521]]
    noqty = [["A", 0.5, 3, 200000.0, None, 200000.0], ["B", 0.3, 4, 100000.0, 4, 100000.0], ["C", 0.2, 2, 100000.0, 2, 100000.0]]
    got = run(BAND_JS, CASES=[["legacy day1", legacy, {"A": 200000.0, "B": 100000.0}], ["legacy over", over, FIVE_PX],
                              ["legacy us", us, {"U": 100.0, "K": 10000.0}, 1300], ["no plannedQty", noqty, {"A": 200000.0, "B": 100000.0, "C": 100000.0}]])
    assert set(x[0] for x in got["legacy day1"].values()) == {"none"} and got["gaps"]["legacy day1"] == {"A": 10.0, "B": -10.0}, got
    assert got["legacy over"]["A"][0] == "trim", got["legacy over"]                      # 계획보다 많이 산 건 그대로 잡아요
    assert got["gaps"]["legacy us"] == {"U": 0, "K": 0}, got["gaps"]["legacy us"]          # 계획 때 환율을 몰라요: 덱 전체 g = 0
    # 계획 수량이 없는 종목(A)만 g = 0. 나머지는 남는 50% 를 계획 금액 비율(4 : 2)로 나눠요: B 33.3% (목표 30%) · C 16.7% (목표 20%)
    assert got["gaps"]["no plannedQty"] == {"A": 0, "B": 3.3, "C": -3.3}, got["gaps"]["no plannedQty"]


def test_targets_are_rebased_over_what_is_held():
    # 계획 3종목(목표 20% · 20% · 60%) 중 60% 종목은 0주(1주 값이 너무 비쌈). 산 두 종목은 서로 반반이면 정상이에요.
    got = run("""
const d = mkDeck([{ s: A, target: 0.2, qty: 10 }, { s: B, target: 0.2, qty: 10 }, { s: C, target: 0.6, qty: 0 }]);
const ev = one(d, [A, B, C], []);
const moved = one(d, [{ ...A, price: A.price * 5 }, B, C], []);
const ha = hold(ev, A.t), hm = hold(moved, A.t);
out = { st: ev.holdings.map((x) => x.status), unheld: ev.unheld, target: ha.target, plan: ha.planTarget, w: ha.w,
        band: ha.rules.find((r) => r.id === 'band').bands.map((x) => Math.round(x * 1000) / 1000), moved: [hm.status, hold(moved, B.t).status] };""",
              A=kr("000100"), B=kr("000200"), C=kr("000300", price=5000000.0))
    assert got["st"] == ["none", "none"] and got["unheld"] == ["000300"], got
    assert abs(got["target"] - 0.5) < 1e-9 and got["plan"] == 0.2 and abs(got["w"] - 0.5) < 1e-9, got   # 20% ÷ (20% + 20%)
    assert got["band"] == [0.375, 0.625, 0.7], got["band"]
    assert got["moved"] == ["trim", "low"], got["moved"]          # 실제로 비중이 벌어지면 여전히 잡아요 (83% · 17%)


def test_day_one_a_deck_bought_exactly_as_planned_has_nothing_to_do():
    """후보 고르기 → 매수 계획(engine size · planShares) → 샀어요(계획한 수량, 그날 종가) → 같은 날 점검: 비중 때문에 무엇도 뜨지 않아요.
    덱 7종 × 금액 3가지 × 안전자산 0·20% (시험용 실제 데이터 표본). 남는 돈 · 0주 종목 · 안전자산이 모두 들어가요."""
    fx = {f: json.load(open(os.path.join(ROOT, "tests", "fixtures", "v2", f), encoding="utf-8")) for f in ("data.json", "corp.json", "macro.json")}
    got = run("""
const now = Date.parse(F['data.json'].publishedAt) + 3600e3;
const load = R.L.resolveLoad({ data: { ok: true, data: F['data.json'] }, corp: { ok: true, data: F['corp.json'] }, macro: { ok: true, data: F['macro.json'] } }, now);
const ctx = R.todayCtx(load, now);
const res = [];
for (const deckId of ['deepValue', 'garp', 'quality', 'lowVol', 'trend', 'krUs', 'income']) for (const amountMan of [150, 300, 1000, 5000]) for (const cushion of [0, 20]) {
  const st = { ...R.E.applyDeck(R.E.defaultSettings(), deckId), amountMan, cushion };
  const ds = R.D.deckState(load, st);
  if (ds.blocked) { res.push({ deckId, amountMan, cushion, blocked: true }); continue; }
  const p = R.D.computePlan(load, st, R.D.pickItems(ds, R.D.defaultPicks(ds)), ds.pinned);
  if (!p.ok) { res.push({ deckId, amountMan, cushion, clash: true }); continue; }
  const rows = p.plan.rows;
  const purchases = rows.filter((x) => x.shares > 0).map((x) => ({ t: x.t, date: '2026-10-30', qty: x.shares, price: x.s.price, ccy: x.s.cls === 'us' ? 'USD' : 'KRW' }));
  const deck = R.D.deckRecord({ load, st, plan: p.plan, purchases, id: 'd', today: '2026-10-30' });     // what 샀어요 saves
  if (!R.S.validStore({ v: 1, decks: [deck] }, '2026-10-30')) throw new Error('deckRecord is not a valid record');
  const ev = R.evaluateDeck(deck, ctx);
  res.push({ deckId, amountMan, cushion, zero: rows.filter((x) => x.shares === 0).length, left: p.plan.left, cush: rows.some((x) => x.kind === 'cushion' && x.shares > 0),
    st: ev.holdings.map((h) => h.nk + ':' + h.status + ':' + h.reasons.map((r) => r.code).join('+')), ok: ev.ok });
}
out = { ok: ctx.state.ok, res };""", F=fx)
    assert got["ok"], "점검이 돌지 않았어요"
    plans = [r for r in got["res"] if "st" in r]
    assert len(plans) >= 40, [r for r in got["res"] if "st" not in r]
    assert any(r["zero"] for r in plans) and any(r["cush"] for r in plans) and all(r["left"] >= 0 for r in plans), plans
    bad = [(r["deckId"], r["amountMan"], r["cushion"], x) for r in plans for x in r["st"] if not x.endswith(":none:")]
    assert not bad, bad


# ── 가격은 규칙을 움직이지 않아요 ──
def test_price_moves_never_change_a_status_only_the_big_move_note():
    a = kr("000100", debt=300.0, dps3=[500.0, 500.0, 450.0])
    p = pair(a, co("000100"), a_buy=at(a, fy=2024, debt=150.0))
    got = run("""
const outs = [];
for (const [d1, scale] of [[0.5, 1], [-6.2, 1], [21, 1], [-29.9, 1], [-6.2, 0.4], [9, 3]]) {
  const now = { ...P.a_now, d1, price: P.a_now.price * scale }, b = { ...P.b, d1, price: P.b.price * scale };
  const d = mkDeck([{ s: P.a_buy, co: P.a_co_buy, points: P.points, target: 0.5, qty: 10 }, { s: P.b, points: P.points, target: 0.5, qty: 10 }]);
  const ev = one(d, [now, b], [P.a_co_now]);
  const h = hold(ev, P.a_now.t);
  outs.push({ d1, s: h.status, calm: hold(ev, P.b.t).status, big: h.bigMove, rules: h.rules.filter((r) => r.id !== 'band').map((r) => r.result), all: ev.bigMoves });
}
out = outs;""", P=p)
    for x in got:
        assert x["s"] == "watch" and x["rules"] == got[0]["rules"], x            # 오르든 내리든 판정은 그대로
        assert x["calm"] == "none", x                                             # 아무 일 없는 종목은 크게 움직여도 할 일 없음
        assert x["big"] == (abs(x["d1"]) >= 5), x
    assert got[0]["all"] == [] and got[1]["all"] == ["000100", "000200"]


def test_a_crash_in_one_stock_changes_only_its_weight_band_never_a_rule():
    p = pair(kr("000100"), co("000100"))
    got = run("""
const d = mkDeck([{ s: P.a_buy, co: P.a_co_buy, points: P.points, target: 0.5, qty: 10 }, { s: P.b, points: P.points, target: 0.5, qty: 10 }]);
const crash = one(d, [{ ...P.a_now, price: P.a_now.price * 0.5, d1: -30 }, P.b], [P.a_co_now]);
const h = hold(crash, P.a_now.t);
out = { s: h.status, codes: h.reasons.map((r) => r.code), big: h.bigMove, w: h.w };""", P=p)
    # 50% 떨어져 비중이 1/3 → 목표 50% 의 0.67배: 먼저 살 차례(비중 계산)일 뿐 규칙은 그대로
    assert got["s"] == "low" and got["codes"] == ["band"] and got["big"] is True and abs(got["w"] - 1 / 3) < 1e-9, got


# ── 멈춘·실패한 데이터 ──
def test_stale_or_failed_data_computes_no_status_at_all():
    got = run("""
const fresh = { ok: true }, data = { pxDate: '2026-10-30', publishedAt: '2026-11-02T06:30:00+09:00', fx: 1300 };
const now = Date.parse('2026-11-02T12:00:00+09:00');
const corp = (pub) => ({ publishedAt: pub });
const load = (o) => ({ status: 'ok', data, corp: corp('2026-11-02T06:30:00+09:00'), byT: new Map(), coByT: new Map(), fresh: { days: 0, stale: false }, ...o });
const d = mkDeck([{ s: A, target: 1, qty: 1 }]);
const states = {
  fresh: R.dayState(load({}), now),
  stale: R.dayState(load({ fresh: { days: 6, stale: true } }), now),
  corpStale: R.dayState(load({ corp: corp('2026-10-27T06:30:00+09:00') }), now),
  fail: R.dayState({ status: 'fail' }, now),
  loading: R.dayState({ status: 'loading' }, now),
  undated: R.dayState(load({ fresh: { days: null, stale: false } }), now),
  preview: R.dayState(load({ preview: true, corp: corp('2020-01-01T00:00:00+09:00') }), now),
};
const evs = Object.fromEntries(Object.entries(states).map(([k, st]) => [k, R.evaluateAll([d], { ...ctxOf([A], []), state: st })]));
const deckOnly = R.evaluateDeck(d, { ...ctxOf([A], []), state: states.stale });
out = { states, evs, deckOnly };""", A=kr("000100"))
    st, evs = got["states"], got["evs"]
    assert st["fresh"] == {"ok": True} and st["preview"] == {"ok": True}
    assert st["stale"] == {"ok": False, "why": "stale", "days": 6}
    assert st["corpStale"]["why"] == "stale" and st["corpStale"]["days"] == 6       # corp.json 이 멈춰도 점검하지 않아요
    assert st["fail"]["why"] == "fail" and st["loading"]["why"] == "loading" and st["undated"]["why"] == "undated"
    for k in ("stale", "corpStale", "fail", "loading", "undated"):
        assert evs[k]["ok"] is False and evs[k]["decks"] == [] and "counts" not in evs[k], (k, evs[k])
        assert "none" not in json.dumps(evs[k]), k                                   # 할 일 없음이 나오지 않아요
    assert evs["fresh"]["ok"] is True and evs["fresh"]["counts"]["none"] == 1
    assert got["deckOnly"]["ok"] is False and "holdings" not in got["deckOnly"]


# ── 배당 감소 ──
def test_dividend_drop_is_a_check_never_broken_on_its_own():
    a = kr("005380", dps=10000.0, dps3=[10000.0, 12000.0, 11400.0])           # 현대차처럼 12,000 → 10,000원
    p = pair(a, co("005380"), a_buy=at(a, fy=2024, dps=12000.0, dps3=[12000.0, 11400.0, 10000.0]))
    got = run(PAIR_JS + "out = { s: h.status, reasons: h.reasons, div: h.rules.find((r) => r.id === 'divCut'), todo: ev.todo, counts: ev.counts };", P=p)
    assert got["s"] == "check" and got["div"]["result"] == "check", got
    drop = got["reasons"][0]
    assert drop["code"] == "divDrop" and (drop["fy"], drop["a"], drop["b"]) == (2025, 12000, 10000)
    assert drop["confirm"] == {"t": "005380", "rule": "divCut", "fy": 2025, "a": 12000, "b": 10000}
    assert got["counts"]["broken"] == 0 and got["todo"] == 1
    assert "broken" not in json.dumps(got["reasons"])


def test_confirm_real_cut_breaks_the_rule_and_not_a_cut_clears_only_that_report():
    a = kr("005380", dps=10000.0, dps3=[10000.0, 12000.0, 11400.0])
    p = pair(a, co("005380"), a_buy=at(a, fy=2024, dps=12000.0, dps3=[12000.0, 11400.0, 10000.0]))
    later = at(a, fy=2026, dps=8000.0, dps3=[8000.0, 10000.0, 12000.0])                 # 다음 해 보고서: 또 줄었어요
    got = run("""
const base = mkDeck([{ s: P.a_buy, co: P.a_co_buy, points: P.points, target: 0.5, qty: 10 }, { s: P.b, points: P.points, target: 0.5, qty: 10 }]);
const store = { v: 1, decks: [base] };
const st = (data, now, co) => hold(one(data.decks[0], [now, P.b], [co]), P.a_now.t);
const item = st(store, P.a_now, P.a_co_now).reasons[0].confirm;
const cut = R.S.withConfirm(store, 'd1', item, 'cut', '2026-11-02');
const notCut = R.S.withConfirm(store, 'd1', item, 'notCut', '2026-11-02');
const changed = R.S.withConfirm(store, 'd1', { ...item, b: 9000 }, 'notCut', '2026-11-02');   // 숫자가 다르면 다른 일
const flip = R.S.withConfirm(cut, 'd1', item, 'notCut', '2026-11-02');
const nxt = { ...P.a_co_now, fy: 2026 };
// 2027년 보고서: 2026년에 12,000원으로 되돌렸다가 2027년에 다시 10,000원 (2025년과 같은 숫자의 새 감소)
const again = st(notCut, { ...P.a_now, fy: 2027, dps: 10000, dps3: [10000, 12000, 10000] }, { ...P.a_co_now, fy: 2027 });
// 실제로 줄였다고 답한 2025년 삭감은 그 뒤 보고서에 더는 보이지 않아도(2028년: 2026~2028 만 보여요), 자료가 비어도 규칙 깨짐
const y2028 = st(cut, { ...P.a_now, fy: 2028, dps: 14000, dps3: [14000, 13000, 12000] }, { ...P.a_co_now, fy: 2028 });
const blank = st(cut, { ...P.a_now, dps3: undefined }, P.a_co_now);
const back = R.S.withConfirm(flip, 'd1', item, 'cut', '2026-11-03');                 // 줄인 게 아니에요 → 다시 실제로 줄였어요
out = { again: [again.status, again.reasons.filter((r) => r.code === 'divDrop').map((r) => r.fy)],
  y2028: [y2028.status, y2028.reasons.map((r) => r.code + ':' + r.fy), y2028.divDrops.map((d) => d.fy + d.answer)],
  blank: [blank.status, blank.reasons.map((r) => r.code)], back: [st(back, P.a_now, P.a_co_now).status, back.decks[0].confirms.map((c) => c.answer)],
  answers: [st(store, P.a_now, P.a_co_now).divDrops.map((d) => d.answer), st(notCut, P.a_now, P.a_co_now).divDrops.map((d) => d.answer)],
  cut: st(cut, P.a_now, P.a_co_now), notCut: st(notCut, P.a_now, P.a_co_now), changed: st(changed, P.a_now, P.a_co_now).status,
  flip: [st(flip, P.a_now, P.a_co_now).status, flip.decks[0].confirms.length],
  laterAfterNotCut: st(notCut, LATER, nxt), laterAfterCut: st(cut, LATER, nxt).status,
  valid: [R.S.validStore(cut, '2026-11-02'), R.S.validStore(notCut, '2026-11-02')],
  bad: [R.S.withConfirm(store, 'd1', item, 'maybe', '2026-11-02'), R.S.withConfirm(store, 'nope', item, 'cut', '2026-11-02'),
        R.S.withConfirm(store, 'd1', { ...item, b: 13000 }, 'cut', '2026-11-02')],
};""", P=p, LATER=later)
    assert got["cut"]["status"] == "broken" and got["cut"]["reasons"][0]["code"] == "divCut", got["cut"]
    assert got["notCut"]["status"] == "none" and got["notCut"]["reasons"] == [], got["notCut"]
    assert got["changed"] == "check"                       # 다른 숫자에 대한 답은 이 감소를 해제하지 않아요
    assert got["flip"] == ["none", 1]                      # 같은 일의 답은 바뀌어도 하나만 남아요
    # 다음 해 보고서의 새 감소(10,000 → 8,000원)는 다시 확인 필요 · 실제로 줄였다고 답한 감소는 규칙 깨짐으로 남아요
    later = got["laterAfterNotCut"]
    assert later["status"] == "check" and [(r["fy"], r["a"], r["b"]) for r in later["reasons"] if r["code"] == "divDrop"] == [(2026, 10000, 8000)], later
    assert got["laterAfterCut"] == "broken"
    assert got["again"] == ["check", [2027]], got["again"]          # 같은 숫자라도 새 보고서의 감소는 다시 물어봐요
    assert got["y2028"] == ["broken", ["divCut:2025"], ["2025cut"]], got["y2028"]   # 확인한 삭감은 사라지지 않아요
    assert got["blank"][0] == "broken" and set(got["blank"][1]) == {"divCut", "missing"}, got["blank"]
    assert got["back"] == ["broken", ["cut"]], got["back"]                          # 답을 바꿀 수 있고, 하나만 남아요
    assert got["answers"] == [[None], ["notCut"]], got["answers"]                   # 화면이 두 답을 계속 보여 줄 수 있게
    assert got["valid"] == [True, True] and got["bad"] == [None, None, None]


def test_a_report_not_newer_than_since_does_not_count_and_an_older_one_is_missing():
    a = kr("005380", fy=2025, dps=10000.0, dps3=[10000.0, 12000.0, 11400.0], debt=150.0)
    c_now = co("005380", op=(115.0, 142.0, 151.0))                                     # 산 날 이미 2년 연속 감소
    got = run("""
const d = mkDeck([{ s: A, co: C0, points: { stable: 3, profit: 2 }, target: 0.5, qty: 10 }, { s: B, target: 0.5, qty: 10 }]);
const same = hold(one(d, [A, B], [C0]), A.t);
const older = hold(one(d, [{ ...A, fy: 2024 }, B], [{ ...C0, fy: 2024 }]), A.t);
out = { same: { s: same.status, rules: Object.fromEntries(same.rules.map((r) => [r.id, [r.result, r.newer ?? null]])) },
        older: { s: older.status, codes: older.reasons.map((r) => r.code + ':' + r.rule) } };""", A=a, C0=c_now, B=kr("000200"))
    same = got["same"]
    # 산 때와 같은 2025년 보고서: 그 전에 있었던 배당 감소·영업이익 감소는 세지 않아요
    assert same["s"] == "none" and same["rules"]["divCut"] == ["ok", False] and same["rules"]["opDecline"] == ["ok", False], same
    # 산 때보다 오래된 보고서(파이프라인이 한 해 전으로 돌아감)는 쓰지 않아요 → 자료를 받지 못한 것으로
    assert got["older"]["s"] == "check" and set(got["older"]["codes"]) == {"missing:divCut", "missing:debtCeiling", "missing:roeFloor", "missing:opDecline"}, got


# ── 산 때 있던 자료가 오늘 비면 ──
def test_an_input_blank_today_is_a_check_never_fine():
    a = kr("000100")
    got = run("""
const d = mkDeck([{ s: A, co: C0, points: { stable: 3, profit: 2 }, target: 0.5, qty: 10 }, { s: B, target: 0.5, qty: 10 }]);
const outs = {};
for (const [k, now, c, b] of CASES) {
  const h = hold(one(d, [now, b || B].filter(Boolean), c ? [c] : []), A.t);
  outs[k] = { s: h.status, miss: h.reasons.filter((r) => r.code === 'missing').map((r) => r.rule + ':' + r.input) };
}
out = outs;""", A=at(a, fy=2024), C0=co("000100", fy=2024), B=kr("000200"),
              CASES=[["dps3", at(a, dps3=None), co("000100"), None], ["dps3 latest", at(a, dps3=[None, 450.0, 400.0]), co("000100"), None],
                     ["debt", at(a, debt=None), co("000100"), None], ["roe", at(a, roe=None), co("000100"), None],
                     ["fy", at(a, fy=None), {"t": "000100", "op": [120.0, 110.0, 100.0]}, None],
                     ["op", a, co("000100", op=(None, 110.0, 100.0)), None], ["op 3 years", a, co("000100", op=(120.0, 110.0, None)), None],
                     ["corp row", a, None, None], ["price", at(a, price=None), co("000100"), None],
                     ["other price", a, co("000100"), at(kr("000200"), price=None)], ["whole row", None, None, None]])
    exp = {"dps3": ["divCut:dps"], "dps3 latest": ["divCut:dps"], "debt": ["debtCeiling:debt"], "roe": ["roeFloor:roe"],
           "fy": ["divCut:dps", "debtCeiling:debt", "roeFloor:roe", "opDecline:op"], "op": ["opDecline:op"], "op 3 years": ["opDecline:op"],
           "corp row": ["opDecline:op"], "price": ["band:price"], "other price": ["band:price"]}
    for k, want in exp.items():
        assert got[k]["s"] == "check" and sorted(got[k]["miss"]) == sorted(want), (k, got[k])
    assert got["whole row"]["s"] == "check" and len(got["whole row"]["miss"]) == 5, got["whole row"]   # 종목이 데이터에서 사라짐


def test_a_missing_price_leaves_every_band_in_the_deck_unchecked():
    got = run("""
const d = mkDeck([{ s: A, target: 0.5, qty: 10 }, { s: B, target: 0.5, qty: 10 }]);
const ev = one(d, [A, { ...B, price: null }], []);
out = { w: ev.weights, a: hold(ev, A.t), us: hold(one(mkDeck([{ s: U, target: 1, qty: 3 }]), [U], [], null), U.t).reasons };""",
              A=kr("000100"), B=kr("000200"), U=us("AAPL"))
    assert got["w"] == {"ok": False, "missing": ["000200"]}
    a = got["a"]
    assert a["status"] == "check" and a["w"] is None and a["reasons"][0]["missingPrice"] == ["000200"], a
    assert [r["input"] for r in got["us"] if r["code"] == "missing"] == ["price"]        # 환율이 없으면 미국 종목 원화 값을 몰라요


# ── 금융회사 · 미국 · 영업이익 순서 ──
def test_financial_companies_skip_the_debt_rule():
    bank = kr("105560", price=155500.0, ind="bank", indName="은행", debt=1212.0, dps3=[4367.0, 3174.0, 3060.0], dps=4367.0)
    got = run("""
const d = mkDeck([{ s: { ...BANK, fy: 2024 }, co: { ...C0, fy: 2024 }, points: { stable: 3, profit: 2 }, target: 0.5, qty: 1 },
                  { s: B, target: 0.5, qty: 15 }]);
const h = hold(one(d, [BANK, B], [C0]), BANK.t);
// 산 날 업종 자료가 없어 부채비율 규칙이 붙었는데 오늘 은행으로 분류된 경우에도 '해당 없음'
const stored = { id: 'debtCeiling', kind: 'keep', check: 'checked', input: 'debt', baseline: 900, since: 2024, debt: 900, limit: 1130, fy: 2024 };
const d2 = mkDeck([{ s: BANK, target: 0.5, qty: 1, rules: [stored] }, { s: B, target: 0.5, qty: 15 }]);
const h2 = hold(one(d2, [BANK, B], [C0]), BANK.t);
out = { ids: h.rules.map((r) => r.id), s: h.status, na: h2.rules[0].result, s2: h2.status };""",
              BANK=bank, C0=co("105560", op=(85177.1, 80452.6, 63850.2)), B=kr("000200", price=10370.0))
    assert "debtCeiling" not in got["ids"] and "cet1" in got["ids"], got
    assert got["s"] == "none" and got["na"] == "na" and got["s2"] == "none", got


def test_us_roe_floor_has_no_report_year_and_us_has_no_debt_rule():
    u = us("AAPL", roe=148.8)
    got = run("""
const d = mkDeck([{ s: U, points: { stable: 3, profit: 2 }, target: 1, qty: 3 }]);
const ok = hold(one(d, [U], [], 1300), U.t), low = hold(one(d, [{ ...U, roe: 50 }], [], 1300), U.t);
out = { ids: ok.rules.map((r) => r.id + ':' + r.result), low: low.reasons };""", U=u)
    assert "roeFloor:ok" in got["ids"] and not any(x.startswith("debtCeiling") for x in got["ids"]), got
    assert "divCut:pending" in got["ids"]
    assert got["low"][0]["code"] == "roeUnder" and got["low"][0]["limit"] == 74 and got["low"][0]["fy"] is None, got["low"]


def test_operating_profit_order_is_this_year_last_year_two_years_ago():
    # corp.json op = [fy, fy-1, fy-2] (fetch_data.py: thstrm, frmtrm, bfefrmtrm of the fy 사업보고서)
    a = kr("000100")
    got = run("""
const d = mkDeck([{ s: { ...A, fy: 2024 }, co: { t: A.t, op: [100, 90, 80], fy: 2024 }, target: 0.5, qty: 10 }, { s: B, target: 0.5, qty: 10 }]);
out = Object.fromEntries(CASES.map(([k, op]) => [k, hold(one(d, [A, B], [{ t: A.t, op, fy: 2025 }]), A.t).rules.find((r) => r.id === 'opDecline').result]));""",
              A=a, B=kr("000200"),
              CASES=[["fell twice", [80.0, 90.0, 100.0]], ["rose twice", [100.0, 90.0, 80.0]], ["fell once", [85.0, 90.0, 80.0]],
                     ["deeper loss", [-50.0, -10.0, 20.0]], ["flat", [90.0, 90.0, 100.0]]])
    assert got == {"fell twice": "fail", "rose twice": "ok", "fell once": "ok", "deeper loss": "fail", "flat": "ok"}, got


def test_the_operating_profit_line_shows_the_fact_and_the_amounts_once_their_unit_is_approved():
    # 후보 고르기 주의할 점과 내 덱 지켜봐요 줄이 같은 조각을 써요. 단위(억원 · 조원)는 승인 전이라 금액은 빠지고,
    # 승인되면(아래에서 흉내) 세 해 금액이 옛날 → 올해 순서로 붙어요. 작년이 적자면 '작년 대비 %' 없이 '영업이익'.
    got = run("""
const before = [R.D.opPieces([114678.5, 142395.9, 151269.0], (114678.5 / 142395.9 - 1) * 100), R.D.opPieces([-50, -10, 20], null)];
R.F.C.app.eok = '{n}억원'; R.F.C.app.jo = '{n}조원';
const after = [R.D.opPieces([114678.5, 142395.9, 151269.0], -19.5), R.D.opPieces([-50, -10, 20], null), R.D.opAmounts([1, null, 3])];
R.F.C.app.eok = null; R.F.C.app.jo = null;
out = { before, after, units: [R.F.C.app.eok, R.F.C.app.jo] };""")
    assert got["units"] == [None, None]                                                     # 승인 전: 비어 있어요
    assert got["before"] == [["영업이익 (작년 대비) \u221219.5%"], ["영업이익"]], got["before"]
    assert got["after"][0] == ["영업이익 (작년 대비) \u221219.5%", "15.1조원 → 14.2조원 → 11.5조원"], got["after"]
    assert got["after"][1] == ["영업이익", "20억원 → \u221210억원 → \u221250억원"] and got["after"][2] is None, got["after"]


# ── 확인하지 못하는 규칙 ──
def test_pending_and_unknown_rules_are_counted_never_passed():
    a = kr("000100")
    got = run("""
const weird = [{ id: 'band', kind: 'band', check: 'checked', target: 0.5, bands: [0.375, 0.625, 0.7] },
               { id: 'futureRule', kind: 'sell', check: 'checked', x: 1 },
               { id: 'debtCeiling', kind: 'keep', check: 'checked' }];
const d = mkDeck([{ s: { ...A, fy: 2024 }, co: { t: A.t, op: [1, 2, 3], fy: 2024 }, points: { stable: 3 }, target: 0.5, qty: 10 },
                  { s: B, target: 0.5, qty: 10, rules: weird }, { s: C, target: 0, qty: 5, rules: [] }]);
const ev = one(d, [A, B, C], [{ t: A.t, op: [3, 2, 1], fy: 2025 }]);
out = { n: ev.notChecked, ids: ev.notCheckedIds.sort(), b: hold(ev, B.t).rules.map((r) => r.id + ':' + r.result), c: hold(ev, C.t), counts: ev.counts };""",
              A=a, B=kr("000200"), C=kr("000300"))
    # A: 감사의견 · 횡령·배임 · 인수 (3) · B: 모르는 규칙 · 숫자 없는 부채비율 규칙 (2) = 5
    assert got["n"] == 5 and got["ids"] == ["acquisition", "audit", "debtCeiling", "embezzle", "futureRule"], got
    assert got["b"] == ["band:ok", "futureRule:pending", "debtCeiling:pending"], got["b"]
    assert got["c"]["status"] == "check" and got["c"]["reasons"][0]["code"] == "noRules"     # 규칙 책이 없으면 할 일 없음이 아니에요


def test_a_malformed_or_all_pending_rule_book_is_a_check_never_nothing():
    got = run("""
const pend = [{ id: 'audit', kind: 'sell', check: 'pending' }];
const out2 = {};
for (const [k, rules] of Object.entries({ empty: [], junk: [{}], nulls: [null, 3, 'x'], badBand: [{ id: 'band', check: 'checked', target: 'x' }], pending: pend })) {
  const d = mkDeck([{ s: A, target: 0.5, qty: 10, rules }, { s: B, target: 0.5, qty: 10 }]);
  const h = hold(one(d, [A, B], []), A.t);
  out2[k] = [h.status, h.reasons[0] && h.reasons[0].code];
}
out = out2;""", A=kr("000100"), B=kr("000200"))
    for k, v in got.items():
        assert v == ["check", "noRules"], (k, v)


def test_an_unreadable_publish_time_is_a_failed_load():
    got = run("""
const base = { pxDate: '2026-10-30', stocks: [{ t: '1' }], companies: [] };
out = [R.L.CHECKS.data({ ...base, publishedAt: '2026-11-02T06:30:00+09:00' }), R.L.CHECKS.data({ ...base, publishedAt: 'soon' }),
       R.L.CHECKS.corp({ ...base, publishedAt: 'soon' }), R.L.CHECKS.data({ ...base, publishedAt: 20261102 }), R.L.CHECKS.corp({ ...base })];""")
    assert got == [True, False, False, False, False], got


def test_planned_but_unbought_holdings_are_not_checked_and_weights_use_held_value():
    got = run("""
const d = mkDeck([{ s: A, target: 0.5, qty: 10 }, { s: B, target: 0.4, qty: 10 }, { s: C, target: 0.1, qty: 0 }]);
const ev = one(d, [A, B, C], []);
out = { ts: ev.holdings.map((x) => [x.t, x.status, Math.round(x.w * 1000) / 1000]), unheld: ev.unheld };""",
              A=kr("000100"), B=kr("000200"), C=kr("000300"))
    # 사지 않은 종목은 점검하지 않아요. 비중은 산 종목의 오늘 값으로 50% · 50%, 목표도 산 종목끼리 다시 나눠 55.6% · 44.4% → 정상
    assert got["unheld"] == ["000300"] and got["ts"] == [["000100", "none", 0.5], ["000200", "none", 0.5]], got
