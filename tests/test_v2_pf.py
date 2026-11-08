# -*- coding: utf-8 -*-
"""뱁새 2.0 가진 종목 넣기 · 내 포트폴리오 점검 · 포트폴리오 규칙 (v19.3d: src/v2/pf.js, v19.3 Parts F · G · O.1) — Node 로 돌려봐요.

- 포트폴리오 규칙 네 가지: 한 종목 30% 이하 · 한 업종 35% 이하 · 내 기준 평균 상위 {top}% 안 · 재무 경고 0개. 확인할 수 없는 규칙은
  'unknown'(확인하지 못했어요)이지 통과가 아니에요. 멈춘 데이터로는 아무것도 점검하지 않아요
- 잘 맞아요 = screen() 의 기준선(점수를 준 기준마다 상위 {top}% 안, 넉넉하게는 50%). 점수를 매길 수 없는 종목(우선주 · 펀드 ·
  데이터 밖)은 어느 쪽에도 넣지 않고 이름을 밝혀요. 빈칸과 '해당 없음'은 빈 점이 아니에요
- 2022년: 종목마다 β ∓ 2 × betaSE 로 범위, 작은 하락부터. betaSE 가 0.5 넘으면 빼요. 아래 끝이 하락이 아니면 추정하지 않아요
- 붙여 넣기: 한 줄에 종목 하나와 수량 하나. 수량이 둘 이상이면 읽지 않아요. 이름 일부가 둘 이상에 맞으면 고르게 해요
- 저장할 포트폴리오는 store.js 검사를 통과하고, 평균 단가는 넣은 것만 있어요 (지어내지 않아요)
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


def run(body, **data):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-pf-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("P", "pf.js"), ("S", "store.js"), ("H", "held.js"), ("T", "track.js"), ("R", "rules.js"), ("K", "company.js"),
                              ("E", "engine.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/pf.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    pre = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import { P, S, H, T, R, K, E } from './pf.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m));\n" + pre + HELP + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


def kr(t, nk, vz, debt, ind="semi", **kw):
    return {"t": t, "nk": nk, "ne": nk, "cls": "kr", "price": 10000.0, "val20": 50.0, "vz": vz, "debt": debt, "ind": ind,
            "indName": {"semi": "반도체", "bank": "은행", "chem": "화학"}.get(ind), "beta": 1.0, "betaSE": 0.05, "d1": 1.0, "fy": 2025, **kw}


def us(t, nk, vz, debt, ind="software", **kw):
    return {"t": t, "nk": nk, "ne": nk, "cls": "us", "ccy": "USD", "price": 100.0, "val": 50.0, "vz": vz, "debt": debt, "ind": ind, "indName": "소프트웨어",
            "beta": 1.0, "betaSE": 0.0, "d1": 0.5, "dy": 1.0, **kw}


STOCKS = [kr("000010", "가나전자", 90, 50), kr("000020", "가나은행", 70, 100, ind="bank", beta=0.5, betaSE=0.1),
          kr("000030", "다라화학", 50, 150, beta=1.2, betaSE=0.6), kr("000040", "마바물산", 30, 200, ind="chem"),
          kr("000050", "사아건설", 10, 250, ind="chem"), kr("000060", "자차식품", None, 300, ind="chem"),
          kr("000015", "가나전자우", None, None), {**kr("069500", "KODEX 200", None, None, ind=None), "etf": True, "indName": None},
          us("AAA", "Alpha Inc.", 40, 10), us("BBB", "Beta Corp.", 30, 20), us("CCC", "Gamma Corp.", 20, 30), us("DDD", "Delta Corp.", 10, 40)]
CORPS = [{"t": "000010", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"]},
         {"t": "000020", "fy": 2025, "flRan": ["l3", "imp"], "flNa": ["cr", "icr"]},
         {"t": "000030", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"], "fl": {"cr": 80}},
         {"t": "000015", "fy": 2025, "flRan": ["cr", "icr", "l3", "imp"]}]

HELP = """
const ctxOf = (stocks, corps, state = { ok: true }) => ({ state, byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map((corps || []).map((c) => [c.t, c])),
  fx: 1000, pxDate: '2026-11-06' });
const row = (t, nk, qty, extra = {}) => ({ t, nk, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty, ...extra });
const deckOf = (rows, points, strict = 'normal', extra = {}) => ({ id: 'dimp', name: 'p', kind: 'imported', settings: { points, strict },
  holdings: rows.filter((r) => r.t).map((r) => ({ t: r.t, nk: r.nk, cls: /^[0-9]/.test(r.t) ? 'kr' : 'us' })), purchases: [], imported: rows, ...extra });
const FIVE = [row('000010', '가나전자', 10), row('000020', '가나은행', 10), row('000030', '다라화학', 10), row('000015', '가나전자우', 10), row('AAA', 'Alpha Inc.', 1)];
const rule = (st, id) => st.rules.find((r) => r.id === id);
"""


def test_the_four_rules_on_a_portfolio():
    got = run("""const st = P.pfState(deckOf(FIVE, { value: 3, stable: 2 }, 'strict'), ctxOf(STOCKS, CORPS), STOCKS);
      out = { ok: st.ok, w: st.view.rows.map((r) => [r.t, Math.round(r.w * 1000) / 10]), rules: st.rules, kept: st.kept, checked: st.checked,
        unchecked: st.unchecked, broken: st.broken && st.broken.id, fit: st.stats.fit.map((r) => r.t), less: st.stats.less.map((r) => r.t),
        unscored: st.stats.unscored.map((r) => r.t), avg: st.stats.avg, top: st.stats.top };""", STOCKS=STOCKS, CORPS=CORPS)
    assert got["ok"] and all(w == 20.0 for _, w in got["w"])
    stock, ind, fit, warn = got["rules"]
    assert stock["state"] == "ok" and stock["limit"] == 30 and round(stock["max"]["w"] * 100) == 20
    assert ind["state"] == "broken" and ind["top"]["name"] == "반도체" and round(ind["top"]["w"] * 100) == 60     # 가나전자 · 다라화학 · 가나전자우
    assert set(ind["top"]["names"]) == {"가나전자", "다라화학", "가나전자우"}
    assert fit["state"] == "ok" and fit["limit"] == 30
    assert got["avg"] == {"value": {"x": 15, "shown": 15}, "stable": {"x": pytest.approx(20 / 3), "shown": 7}}     # 은행은 재무 안정 '해당 없음'
    assert warn["state"] == "broken" and warn["flagged"] == ["다라화학"] and warn["unknown"] == ["Alpha Inc."]
    assert got["fit"] == ["000010", "000020", "AAA"] and got["less"] == ["000030"] and got["unscored"] == ["000015"]
    assert got["kept"] == 2 and got["checked"] == 4 and got["unchecked"] == 0 and got["broken"] == "ind"


def test_rules_that_cannot_be_checked_are_unknown_never_ok():
    no_flag = [dict(c) for c in CORPS]
    no_flag[2].pop("fl")
    nopx = [dict(s) for s in STOCKS]
    nopx[0]["price"] = None
    got = run("""const a = P.pfState(deckOf(FIVE, { value: 3 }), ctxOf(STOCKS, NOFLAG), STOCKS);
      const b = P.pfState(deckOf(FIVE, { value: 3 }), ctxOf(NOPX, NOFLAG), NOPX);
      const c = P.pfState(deckOf(FIVE, {}), ctxOf(STOCKS, NOFLAG), STOCKS);
      const d = P.pfState(deckOf(FIVE, { value: 3 }), ctxOf(STOCKS, NOFLAG, { ok: false, why: 'stale', days: 6 }), STOCKS);
      const e = P.pfState(deckOf([row('000040', '마바물산', 1), row('069500', 'KODEX 200', 1)], { value: 3 }), ctxOf(STOCKS, NOFLAG), STOCKS);
      out = { a: a.rules.map((r) => r.state), b: b.rules.map((r) => r.state), bmiss: b.view.missing, c: rule(c, 'fit').state, d,
        e: [rule(e, 'ind').state, rule(e, 'ind').none, rule(e, 'warn').state], ekept: [e.kept, e.checked, e.unchecked] };""",
              STOCKS=STOCKS, NOFLAG=no_flag, NOPX=nopx)
    assert got["a"] == ["ok", "broken", "ok", "unknown"]              # 미국 종목이 있으면 재무 경고는 확인하지 못했어요
    assert got["b"] == ["unknown", "unknown", "unknown", "unknown"] and got["bmiss"] == ["000010"]   # 오늘 가격이 없으면 비중을 몰라요
    assert got["c"] == "unknown"                                       # 고른 기준이 없으면
    assert got["d"] == {"ok": False, "why": "stale", "days": 6}        # 멈춘 데이터: 점검하지 않아요 (✓ 없음)
    assert got["e"][0] == "broken" and got["e"][1] == ["KODEX 200"] and got["e"][2] == "unknown"   # 업종 없는 종목은 이름을 밝혀요
    assert got["ekept"] == [0, 3, 1]                                   # 한 종목 50% · 화학 50% · 가치 평균 상위 60%: 셋 다 어겼어요


def test_limits_can_be_changed_per_portfolio_and_loose_uses_50():
    got = run("""const a = P.pfState(deckOf(FIVE, { value: 3 }, 'loose', { limits: { stock: 15, ind: 70 } }), ctxOf(STOCKS, CORPS), STOCKS);
      out = { stock: rule(a, 'stock'), ind: rule(a, 'ind').state, fit: rule(a, 'fit').limit, top: a.stats.top, less: a.stats.less.map((r) => r.t),
        lim: P.limitsOf({}), fitTop: [P.fitTop('loose'), P.fitTop('normal'), P.fitTop('strict'), P.fitTop('very')] };""", STOCKS=STOCKS, CORPS=CORPS)
    assert got["stock"]["state"] == "broken" and got["stock"]["limit"] == 15 and got["ind"] == "ok"
    assert got["fit"] == 50 and got["top"] == 50 and got["less"] == []           # 넉넉하게: 잘 맞아요는 50% 로 나눠요
    assert got["lim"] == {"stock": 30, "ind": 35} and got["fitTop"] == [50, 50, 30, 10]


def test_missing_and_not_applicable_are_never_an_empty_dot():
    got = run("""out = [P.dotOf({ st: 'blank' }), P.dotOf({ st: 'na' }), P.dotOf(null), P.dotOf({ st: 'num', sc: 71 }), P.dotOf({ st: 'num', sc: 70 }),
      P.dotOf({ st: 'num', sc: 51 }), P.dotOf({ st: 'num', sc: 50 }), P.dotOf({ st: 'num', sc: 5 })];""")
    assert got == ["blank", "na", "blank", "full", "half", "half", "empty", "empty"]


def test_the_2022_range_follows_the_beta_band():
    R = {"kr": -0.25, "usWon": -0.15, "etf": {"114260": -0.0246}}
    got = run("""const v = P.pfRows(deckOf(FIVE, { value: 3 }), ctxOf(STOCKS, CORPS));
      const lone = (beta, se) => P.pfRows(deckOf([row('000040', '마바물산', 1)], { value: 1 }), ctxOf(STOCKS.map((s) => s.t === '000040' ? { ...s, beta, betaSE: se } : s), CORPS));
      out = { r: P.range2022(v, RR), uncertain: P.range2022(lone(0.2, 0.2), RR), one: P.range2022(lone(1.0, 0.001), RR), none: P.range2022(lone(null, null), RR) };""",
              STOCKS=STOCKS, CORPS=CORPS, RR=R)
    r = got["r"]
    assert r["ok"] and r["est"] == "range" and r["small"] == 17 and r["big"] == 22     # 다라화학(betaSE 0.6)은 빼요
    assert r["out"] == ["다라화학"] and abs(r["share"] - 0.2) < 1e-9
    assert abs(r["amountSmall"] - 67500) < 1e-6 and abs(r["amountBig"] - 87500) < 1e-6
    assert got["uncertain"]["est"] == "uncertain"                      # 아래 끝이 하락이 아니면 추정하지 않아요
    assert got["one"]["est"] == "one" and got["one"]["small"] == got["one"]["big"] == 25
    assert got["none"] == {"ok": False, "why": "none", "share": 1, "out": ["마바물산"]}


def test_paste_reads_one_stock_and_one_quantity_per_line():
    text = "\n".join(["가나전자 10", "000020,3", "없는회사 5", "다라화학 10 71,500 715,000", "가나 4", "AAA 3.5", "가나전자 1.5",
                      "다라화학 1,234주", "KODEX 200 10", "", "AAA 0.12345", "000030 000030 7", "Alpha Inc.\t2"])
    got = run("out = P.parsePaste(TEXT, STOCKS, '주').map((l) => ({ line: l.line, st: l.st, t: l.s ? l.s.t : null, qty: l.qty ?? null, q: l.q ?? null,"
              " choices: l.choices ? l.choices.map((s) => s.t).sort() : null }));", STOCKS=STOCKS, TEXT=text)
    by = {g["line"]: g for g in got}
    assert sorted(by) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13]        # 빈 줄은 건너뛰고, 줄 번호는 붙여 넣은 그대로
    assert (by[1]["st"], by[1]["t"], by[1]["qty"]) == ("ok", "000010", 10)   # 이름이 딱 맞으면 그 종목 (가나전자우가 아니라)
    assert (by[2]["st"], by[2]["t"], by[2]["qty"]) == ("ok", "000020", 3)    # 쉼표로 나눈 줄
    assert by[3]["st"] == "noStock"
    assert by[4]["st"] == "noQty" and by[4]["t"] == "000030"                 # 숫자가 셋: 수량을 읽지 못했어요
    assert by[5]["st"] == "pick" and by[5]["q"] == "가나" and by[5]["choices"] == ["000010", "000015", "000020"] and by[5]["qty"] == 4
    assert (by[6]["st"], by[6]["qty"]) == ("ok", 3.5)                        # 미국: 소수 넷째 자리까지
    assert by[7]["st"] == "noQty"                                           # 한국 소수 주식
    assert (by[8]["st"], by[8]["qty"]) == ("ok", 1234)                       # 1,234주 = 천이백삼십사 주
    assert (by[9]["st"], by[9]["t"], by[9]["qty"]) == ("ok", "069500", 10)   # 띄어 쓴 이름
    assert by[11]["st"] == "noQty"                                          # 소수 다섯째 자리
    assert (by[12]["st"], by[12]["qty"]) == ("ok", 7)                        # 종목 코드를 한 번 더 적어도 수량이 아니에요
    assert (by[13]["st"], by[13]["t"], by[13]["qty"]) == ("ok", "AAA", 2)    # 영문 이름 · 탭


def test_search_finds_korean_us_and_funds_by_name_or_code():
    got = run("out = [P.findStocks(STOCKS, '가나').map((s) => s.t), P.findStocks(STOCKS, 'aaa').map((s) => s.t), P.findStocks(STOCKS, '0000').length,"
              " P.findStocks(STOCKS, 'kodex').map((s) => s.t), P.findStocks(STOCKS, '  ').length];", STOCKS=STOCKS)
    assert set(got[0]) == {"000010", "000020", "000015"} and got[1] == ["AAA"] and got[2] == 7 and got[3] == ["069500"] and got[4] == 0


def test_the_saved_portfolio_is_valid_and_invents_no_average_price():
    got = run("""const load = { data: { stocks: STOCKS, fx: 1000, pxDate: '2026-11-06', usPxDate: '2026-11-05' }, byT: new Map(STOCKS.map((s) => [s.t, s])) };
      const drafts = [{ t: '000010', mode: 'qty', qty: 10, avg: 9000 }, { t: 'AAA', mode: 'amount', amountWon: 200000, avg: null },
        { t: '000015', mode: 'qty', qty: 5, avg: null }, { t: '069500', mode: 'qty', qty: 3, avg: null }];
      const d = P.importedRecord({ drafts, load, settings: { points: { value: 3 }, strict: 'normal' }, id: 'dnew', name: 'p', today: '2026-11-07' });
      out = { d, problem: S.deckProblem(d, '2026-11-07'), held: Object.fromEntries(H.heldQty(d)),
        ok: [P.draftOk({ mode: 'qty', qty: 1.5 }, STOCKS[0]), P.draftOk({ mode: 'qty', qty: 1.5 }, STOCKS[8]), P.draftOk({ mode: 'amount', amountWon: 0 }, STOCKS[0])] };""",
              STOCKS=STOCKS)
    d = got["d"]
    assert got["problem"] is None and d["kind"] == "imported" and d["purchases"] == []
    imp = {r["t"]: r for r in d["imported"]}
    assert imp["000010"] == {"t": "000010", "nk": "가나전자", "ccy": "KRW", "avg": 9000, "qty": 10}
    assert imp["AAA"] == {"t": "AAA", "nk": "Alpha Inc.", "ccy": "USD", "amountWon": 200000, "close": 100.0, "date": "2026-11-05", "fx": 1000}
    assert "avg" not in imp["000015"] and imp["000015"]["unscored"] is True and imp["069500"]["unscored"] is True    # 평균 단가는 넣은 것만
    assert "unscored" not in imp["000010"] and "unscored" not in imp["AAA"]
    assert got["held"] == {"000010": 10, "AAA": 2, "000015": 5, "069500": 3}
    assert got["ok"] == [False, True, False]


def test_money_reads_imported_holdings_and_leaves_out_what_it_cannot_know():
    got = run("""const ctx = ctxOf(STOCKS, CORPS);
      const all = deckOf([row('000010', '가나전자', 10, { avg: 9000 }), { t: 'AAA', nk: 'Alpha Inc.', ccy: 'USD', amountWon: 200000, close: 100, date: '2026-11-05', fx: 1000, avg: 90 }], { value: 3 });
      const part = deckOf([row('000010', '가나전자', 10, { avg: 9000 }), row('000020', '가나은행', 4)], { value: 3 });
      const gone = deckOf([row('000010', '가나전자', 10, { avg: 9000 }), row('999990', '없는회사', 4)], { value: 3 });
      const named = deckOf([row('000010', '가나전자', 10), { nk: '비상장 회사', ccy: 'KRW', amountWon: 50000, date: '2026-11-01', unscored: true }], { value: 3 });
      const ev = (d) => R.evaluateDeck(d, ctx);
      out = { all: T.deckMoney(all, ev(all), ctx), part: T.deckMoney(part, ev(part), ctx), gone: T.deckMoney(gone, ev(gone), ctx),
        named: T.deckMoney(named, ev(named), ctx), ev: ev(all), stale: R.evaluateDeck(all, { ...ctx, state: { ok: false, why: 'stale', days: 5 } }) };""",
              STOCKS=STOCKS, CORPS=CORPS)
    a = got["all"]
    assert a["ok"] and a["value"] == 300000 and a["cost"] == 270000 and abs(a["ret"] - 1 / 9) < 1e-12 and a["usdToday"] is True
    assert got["part"]["ok"] and got["part"]["value"] == 140000 and got["part"]["cost"] is None and got["part"]["noAvg"] == ["000020"]
    assert got["gone"]["ok"] and got["gone"]["value"] == 100000 and [x["t"] for x in got["gone"]["absent"]] == ["999990"]
    assert got["named"]["value"] == 150000 and got["named"]["frozen"] == [{"nk": "비상장 회사", "date": "2026-11-01"}]
    ev = got["ev"]
    assert ev["ok"] and ev["imported"] and ev["holdings"] == [] and ev["todo"] == 0 and ev["notChecked"] == 0   # 확인 필요가 아니에요
    assert got["stale"]["ok"] is False


def test_a_korean_listing_priced_in_won_is_never_a_dollar_holding():
    """v19.3d review (blocker): data.json lists 379800 KODEX 미국S&P500 with cls "us" but priced in won (no ccy). It is a KRX
    listing: 한국, whole shares, its record in KRW, its value price × quantity (never × the exchange rate)."""
    kodex = {"t": "379800", "nk": "KODEX 미국S&P500", "ne": "KODEX 미국S&P500", "cls": "us", "price": 22415.0, "etf": True, "val": 300.0}
    stocks = STOCKS + [kodex]
    got = run("""const load = { data: { stocks: ST, fx: 1356.3, pxDate: '2026-11-06', usPxDate: '2026-11-05' }, byT: new Map(ST.map((s) => [s.t, s])) };
      const k = load.byT.get('379800'), a = load.byT.get('AAA');
      const d = P.importedRecord({ drafts: [{ t: '379800', mode: 'qty', qty: 10, avg: 21000 }, { t: '379800', mode: 'amount', amountWon: 500000 }],
        load, settings: { points: { value: 1 } }, id: 'dk', name: 'p', today: '2026-11-07' });
      const d2 = P.importedRecord({ drafts: [{ t: '379800', mode: 'amount', amountWon: 500000 }], load, settings: { points: { value: 1 } }, id: 'dk2', name: 'p', today: '2026-11-07' });
      const ctx = { state: { ok: true }, byT: load.byT, coByT: new Map(), fx: 1356.3, pxDate: '2026-11-06' };
      const st = P.pfState(d, ctx, ST);
      out = { usd: [P.usdOf(k), P.usdOf(a)], market: [P.marketKey(k), P.marketKey(a)], won: [P.wonPrice(k, 1356.3), P.wonPrice(a, 1356.3)],
        rec: d.imported[0], rec2: d2.imported[0], problem: S.deckProblem(d, '2026-11-07'), value: st.view.rows[0].value, usdRow: st.view.rows[0].usd,
        qty: [P.okQty(1.5, k), P.okQty(1.5, a), P.okQty(2, k)], ok: [P.draftOk({ mode: 'amount', amountWon: 500000 }, k, null), P.draftOk({ mode: 'amount', amountWon: 500000 }, a, null),
          P.draftOk({ mode: 'amount', amountWon: 500000 }, a, 1356.3), P.draftOk({ mode: 'amount', amountWon: 1 }, k, null)],
        money: T.deckMoney(d, R.evaluateDeck(d, ctx), ctx), dates: P.reportDates(st.view, ctx, new Map()).us };""", ST=stocks)
    assert got["usd"] == [False, True] and got["market"] == ["kr", "us"] and got["won"] == [22415.0, 100.0 * 1356.3]
    assert got["rec"] == {"t": "379800", "nk": "KODEX 미국S&P500", "ccy": "KRW", "avg": 21000, "qty": 10, "unscored": True}
    assert got["rec2"]["ccy"] == "KRW" and "fx" not in got["rec2"] and got["rec2"]["date"] == "2026-11-06" and got["problem"] is None
    assert got["value"] == 224150.0 and got["usdRow"] is False                    # 10주 × 22,415원 (환율을 곱하지 않아요)
    assert got["qty"] == [False, True, True]                                       # 원화 상장: 정수 주식만
    assert got["ok"] == [True, False, True, False]                                 # 미국 금액은 오늘 환율이 있어야 · 1원은 1/10,000주도 안 돼요
    assert got["money"]["ok"] and got["money"]["value"] == 224150.0 and got["money"]["cost"] == 210000 and got["money"]["usdToday"] is False
    assert got["dates"] is False


def test_sandbox_squarify_and_the_warning_checks():
    got = run("""const w = P.moveWeight(new Map([['a', 0.5], ['b', 0.3], ['c', 0.2]]), 'a', 0.2);
      const rects = P.squarify([6, 6, 4, 3, 2, 2, 1].map((v, i) => ({ key: 'k' + i, v })), 0, 0, 6, 4);
      const KR = { t: 'X', cls: 'kr' };
      const cos = [{ fy: 2025, flRan: ['cr', 'icr', 'l3', 'imp'] }, { fy: 2025, flRan: ['l3', 'imp'], flNa: ['cr', 'icr'] }, { fy: 2025, flRan: ['cr', 'l3', 'imp'] },
        { fy: 2025, flRan: ['cr', 'icr', 'l3', 'imp'], fl: { cr: 70 } }, { fy: 2025 }, null];
      const warn = cos.map((co) => [P.warnOf(KR, co), K.warnings(KR, co)]);
      out = { w: Object.fromEntries(w), sum: [...w.values()].reduce((x, y) => x + y, 0), rects, warn,
        same: P.moveWeight(new Map([['a', 1]]), 'zz', 0.5).get('a') };""")
    assert got["w"]["a"] == 0.2 and abs(got["w"]["b"] - 0.48) < 1e-12 and abs(got["w"]["c"] - 0.32) < 1e-12 and abs(got["sum"] - 1) < 1e-12
    rects = got["rects"]
    assert len(rects) == 7 and abs(sum(r["w"] * r["h"] for r in rects) - 24) < 1e-9
    for r, v in zip(rects, [6, 6, 4, 3, 2, 2, 1]):
        assert abs(r["w"] * r["h"] - v) < 1e-9 and r["x"] >= -1e-9 and r["y"] >= -1e-9 and r["x"] + r["w"] <= 6 + 1e-9 and r["y"] + r["h"] <= 4 + 1e-9
    assert got["same"] == 1
    for mine, page in got["warn"]:                                     # 회사 페이지와 같은 함수 (warn.js): 두 화면이 늘 같은 말
        assert mine == ("flag" if page["flags"] else "clear" if page["allRan"] else "unknown"), (mine, page)
    assert [m for m, _ in got["warn"]] == ["clear", "clear", "unknown", "flag", "unknown", "unknown"]

def test_a_built_portfolio_with_a_sale_shows_no_wrong_money_and_a_sold_out_holding_is_not_unbought():
    """v19.3d review: until v19.6a's lot maths, a built portfolio with a sale has no 원금, return or KOSPI comparison (null,
    never 9 of 10 shares sold counted as −40.9%), and a holding sold down to 0 is sold out, not "planned, never bought"
    (the other targets are rebased over what is held, and rebased says so: never a wrong 비중 줄이기 for the stock left)."""
    got = run("""const ctx = ctxOf(STOCKS, CORPS);
      const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
      const deck = { id: 'db', name: 'b', holdings: [{ t: '000010', nk: '가나전자', target: 0.5, rules: band(0.5) }, { t: '000040', nk: '마바물산', target: 0.5, rules: band(0.5) }],
        purchases: [{ t: '000010', qty: 10, price: 10000, date: '2026-10-01', ccy: 'KRW' }, { t: '000040', qty: 10, price: 10000, date: '2026-10-01', ccy: 'KRW' }] };
      const sold = { ...deck, sales: [{ t: '000040', qty: 10, price: 9000, date: '2026-11-01', ccy: 'KRW' }, { t: '000010', qty: 9, price: 10000, date: '2026-11-01', ccy: 'KRW' }] };
      const ev = (d) => R.evaluateDeck(d, ctx);
      const idx = { asOf: '2026-11-06', rows: [['2026-09-30', 100], ['2026-11-06', 110]] };
      const w0 = warns.length; T.deckMoney(sold, ev(sold), ctx); const lotWarns = warns.slice(w0);
      out = { lotWarns, plain: T.deckMoney(deck, ev(deck), ctx), sold: T.deckMoney(sold, ev(sold), ctx), e: ev(sold), k: [T.indexSince(deck, idx, '2026-11-06').ok, T.indexSince(sold, idx, '2026-11-06')],
        imp: S.deckProblem({ ...deck, imported: [{ t: '000010', nk: '가나전자', ccy: 'KRW', qty: 1 }] }, '2026-11-07') };
      out.lotsN = warns.filter((w) => w.includes('lot maths')).length;""", STOCKS=STOCKS, CORPS=CORPS)
    assert got["plain"]["cost"] == 200000 and got["plain"]["ret"] == 0
    s = got["sold"]
    assert s["ok"] and s["value"] == 10000 and s["cost"] is None and s["gain"] is None and s["ret"] is None and s["lots"] is True
    assert all(r["cost"] is None and r["ret"] is None for r in s["per"].values())
    assert got["lotWarns"] == ["[v2] db: 2 sale(s) and 0 imported row(s) on a built portfolio: money put in, return and the KOSPI comparison"
                               " left out until the lot maths (v19.6a)"]                     # 리뷰 3차 7: 콘솔에 한 번, 개수와 함께
    assert got["lotsN"] == 1
    e = got["e"]
    assert e["unheld"] == [] and e["soldOut"] == ["000040"] and [x["t"] for x in e["holdings"]] == ["000010"]
    assert e["rebased"] is True and e["bandPlanned"] == 2 and e["bandHeld"] == 1                 # 리뷰 3차 6: 다시 나눈 걸 말해요
    band = [r for r in e["holdings"][0]["rules"] if r["id"] == "band"][0]
    assert band["result"] == "ok" and band["band"] is None and abs(band["target"] - 1) < 1e-12   # 남은 1주 = 목표 100%: 줄이라는 말 없음
    assert got["k"] == [True, {"ok": False, "why": "lots"}]
    assert got["imp"]["part"] == "imported" and "imported portfolio" in got["imp"]["why"]     # 만든 포트폴리오에는 가져온 줄이 없어요
