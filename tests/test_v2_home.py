# -*- coding: utf-8 -*-
"""뱁새 2.0 홈과 회사 페이지 고침 (v19.3e: src/v2/home.js · company.js · cotabs.jsx · pfview.jsx, v19.3 Parts H · I) — Node 로 돌려봐요.

- 홈의 '산 가격보다'는 평균 단가가 있는 종목만으로 계산하고 그 종목 수를 말해요 (수락 조건 5). 평균 단가가 없는 종목은 양쪽에서 빼요.
  미국 종목의 평균 단가(달러)는 오늘 환율로 바꾸고 그렇다고 말해요. 판 기록이 있는 만든 포트폴리오는 v19.6a 전까지 계산하지 않아요
- '오늘'은 모든 종목에 오늘 변화가 있을 때만 (미국 종목 · 금액만 넣은 종목이 있으면 없음)
- 멈춘 데이터 · 불러오기 실패: 홈에 포트폴리오 숫자가 없어요 (점검하지 않으니 ✓ 도 없음)
- 가치 고침: '지금 가격이 가정하는 것'은 순이익끼리 비교해요 (ni[2] → ni[0] 연평균, 둘 다 0보다 클 때만). 비슷 = 3%p 안
- 재무 경고 칩: 돌았고 걸리지 않은 확인만. 돌지 않은 확인 · 해당 없음 · 꺼진 이자보상배율은 칩이 없어요
- 비율을 한계와 함께 보여 줄 때 반올림이 한계 안쪽처럼 읽히지 않아요 (30.4% 는 '30%'가 아니에요)
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
        tmp = tempfile.mkdtemp(prefix="baepsae-home-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("Hm", "home.js"), ("P", "pf.js"), ("T", "track.js"), ("R", "rules.js"), ("K", "company.js"), ("W", "warn.js"),
                              ("X", "cotabs.jsx"), ("V", "pfview.jsx"), ("A", "coart.jsx"), ("Co", "company.jsx")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/home.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8",
                            "--define:process.env.NODE_ENV='\"production\"'"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    pre = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import { Hm, P, T, R, K, W, X, V, A, Co, C } from './home.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m));\n" + pre + HELP
            + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


def kr(t, nk, price, d1=1.0, ind="semi", **kw):
    return {"t": t, "nk": nk, "ne": nk, "cls": "kr", "price": price, "val20": 50.0, "vz": 50, "debt": 50, "ind": ind,
            "indName": {"semi": "반도체", "bank": "은행", "chem": "화학"}.get(ind), "beta": 1.0, "betaSE": 0.05, "d1": d1, "fy": 2025, **kw}


STOCKS = [kr("000010", "가나전자", 10000.0, d1=2.0), kr("000020", "가나은행", 20000.0, d1=-1.0, ind="bank"), kr("000040", "마바물산", 5000.0, ind="chem"),
          {"t": "AAA", "nk": "Alpha Inc.", "ne": "Alpha Inc.", "cls": "us", "ccy": "USD", "price": 100.0, "val": 50.0, "vz": 40, "ind": "software",
           "indName": "소프트웨어", "beta": 1.0, "betaSE": 0.05, "d1": 0.5, "dy": 1.0}]

HELP = """
const ctxOf = (stocks, corps = [], state = { ok: true }) => ({ state, byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map(corps.map((c) => [c.t, c])),
  fx: 1000, pxDate: '2026-11-06' });
const row = (t, nk, qty, extra = {}) => ({ t, nk, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD', qty, ...extra });
const impDeck = (rows, extra = {}) => ({ id: 'dimp', name: 'p', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
  holdings: rows.filter((r) => r.t).map((r) => ({ t: r.t, nk: r.nk, cls: /^[0-9]/.test(r.t) ? 'kr' : 'us' })), purchases: [], imported: rows, ...extra });
const band = (target) => ({ id: 'band', kind: 'band', check: 'checked', target, bands: [0.75 * target, 1.25 * target, 1.4 * target] });
const builtDeck = (rows, extra = {}) => ({ id: 'dbuilt', name: 'b', createdAt: '2026-10-01', planFx: 1000,
  holdings: rows.map(([t, nk, target, qty]) => ({ t, nk, cls: /^[0-9]/.test(t) ? 'kr' : 'us', target, plannedQty: qty, rules: [band(target)] })),
  purchases: rows.filter((r) => r[3] > 0).map(([t, nk, target, qty, price]) => ({ t, date: '2026-10-01', qty, price, ccy: /^[0-9]/.test(t) ? 'KRW' : 'USD',
    ...(/^[0-9]/.test(t) ? {} : { fx: 1100 }) })), ...extra });
const blockOf = (deck, stocks, corps) => { const ctx = ctxOf(stocks, corps); const ev = R.evaluateAll([deck], ctx); return Hm.homeBlocks([deck], ev, ctx, stocks); };
"""


def test_gain_counts_only_holdings_with_an_average_price():
    got = run("""const d = impDeck([row('000010', '가나전자', 10, { avg: 8000 }), row('000020', '가나은행', 5), row('AAA', 'Alpha Inc.', 2, { avg: 80 })]);
      const [b] = blockOf(d, STOCKS);
      const none = blockOf(impDeck([row('000010', '가나전자', 10), row('000020', '가나은행', 5)]), STOCKS)[0];
      out = { m: b.money, none: none.money.gain, n: b.list.rows.length };""", STOCKS=STOCKS)
    m = got["m"]
    assert m["ok"] and m["value"] == 10 * 10000 + 5 * 20000 + 2 * 100 * 1000
    g = m["gain"]
    assert g["n"] == 2                                                       # 가나은행(평균 단가 없음)은 빼요
    assert g["cost"] == 10 * 8000 + 2 * 80 * 1000 and g["value"] == 10 * 10000 + 2 * 100 * 1000   # 달러 평균 단가 × 오늘 환율
    assert g["gain"] == g["value"] - g["cost"] and abs(g["ret"] - (g["value"] / g["cost"] - 1)) < 1e-12
    assert g["usdToday"] is True                                             # '미국 종목은 … 오늘 환율로 바꿨어요.'
    assert got["none"] is None and got["n"] == 3                             # 평균 단가가 하나도 없으면 그 줄이 없어요


def test_gain_without_a_dollar_average_says_nothing_about_todays_rate():
    got = run("""const [b] = blockOf(impDeck([row('000010', '가나전자', 10, { avg: 8000 }), row('AAA', 'Alpha Inc.', 2)]), STOCKS);
      out = b.money.gain;""", STOCKS=STOCKS)
    assert got["n"] == 1 and got["usdToday"] is False


def test_built_portfolio_gain_uses_the_saved_rate_and_a_sale_waits_for_lots():
    got = run("""const rows = [['000010', '가나전자', 0.5, 10, 8000], ['AAA', 'Alpha Inc.', 0.5, 1, 90]];
      const [b] = blockOf(builtDeck(rows), STOCKS);
      const [s] = blockOf(builtDeck(rows, { sales: [{ t: '000010', qty: 1, price: 9000, date: '2026-10-20', ccy: 'KRW' }] }), STOCKS);
      out = { g: b.money.gain, day: b.money.day, sale: s.money.gain };""", STOCKS=STOCKS)
    assert got["g"]["n"] == 2 and got["g"]["cost"] == 10 * 8000 + 90 * 1100 and got["g"]["usdToday"] is False   # 산 날 환율
    assert got["day"] is None                                                # 미국 종목이 있으면 '오늘' 없음
    assert got["sale"] is None                                               # 판 기록: v19.6a 전까지 원금 · 수익 없음


def test_today_change_amount_and_percent():
    got = run("""const [a] = blockOf(impDeck([row('000010', '가나전자', 10), row('000020', '가나은행', 5)]), STOCKS);
      const [b] = blockOf(builtDeck([['000010', '가나전자', 0.5, 10, 8000], ['000020', '가나은행', 0.5, 5, 18000]]), STOCKS);
      const amt = Hm.homeBlocks([impDeck([row('000010', '가나전자', 10), { nk: '비상장', amountWon: 100000, date: '2026-10-01' }])],
        R.evaluateAll([impDeck([row('000010', '가나전자', 10), { nk: '비상장', amountWon: 100000, date: '2026-10-01' }])], ctxOf(STOCKS)), ctxOf(STOCKS), STOCKS)[0];
      out = { a: a.money.day, b: b.money.day, amt: amt.money.day, dm: [Hm.dayMove([]), Hm.dayMove([{ value: 1, d1: null }]), Hm.dayMove([{ value: 1, d1: 1, usd: true }])] };""",
              STOCKS=STOCKS)
    now = 100000 + 100000
    prev = 100000 / 1.02 + 100000 / 0.99
    for k in ("a", "b"):
        assert abs(got[k]["amount"] - (now - prev)) < 1e-6 and abs(got[k]["pct"] - (now / prev - 1) * 100) < 1e-9, got[k]
    assert got["amt"] is None and got["dm"] == [None, None, None]          # 금액만 넣은 종목은 움직이지 않아요: 오늘 없음


def test_nothing_on_stale_or_failed_data_and_unbought_portfolios_are_left_out():
    got = run("""const d = impDeck([row('000010', '가나전자', 10, { avg: 8000 })]);
      const stale = ctxOf(STOCKS, [], { ok: false, why: 'stale', days: 6 });
      const unbought = builtDeck([['000010', '가나전자', 1, 0, 0]]);
      const ok = ctxOf(STOCKS);
      out = { stale: Hm.homeBlocks([d], R.evaluateAll([d], stale), stale, STOCKS).length, st: P.pfState(d, stale, STOCKS),
        unbought: Hm.homeBlocks([unbought, d], R.evaluateAll([unbought, d], ok), ok, STOCKS).map((b) => b.deck.id) };""", STOCKS=STOCKS)
    assert got["stale"] == 0 and got["st"] == {"ok": False, "why": "stale", "days": 6}
    assert got["unbought"] == ["dimp"]


def test_rows_largest_first_with_bars_against_the_stock_limit():
    got = run("""const [b] = blockOf(impDeck([row('000040', '마바물산', 10), row('000010', '가나전자', 20)]), STOCKS);
      out = { rows: b.list.rows.map((r) => [r.t, Math.round(r.w * 1000) / 10, r.d1]), bar: [Hm.barOf(0.15, 30), Hm.barOf(0.45, 30), Hm.barOf(null, 30)],
        pct: [Hm.weightPct(0.004), Hm.weightPct(0.2549), Hm.weightPct(0.0095)] };""", STOCKS=STOCKS)
    assert got["rows"] == [["000010", 80.0, 2.0], ["000040", 20.0, 1.0]]
    assert got["bar"] == [0.5, 1, 0] and got["pct"] == [0.4, 25, 1]


def test_concentration_card_is_the_broken_industry_rule():
    got = run("""const [b] = blockOf(impDeck([row('000010', '가나전자', 20), row('000040', '마바물산', 10)]), STOCKS);
      const [c] = blockOf(impDeck([row('000010', '가나전자', 1), row('000020', '가나은행', 1), row('000040', '마바물산', 6)]), STOCKS);
      out = [Hm.concentration(b.st), Hm.concentration(c.st)];""", STOCKS=STOCKS)
    assert got[0]["name"] == "반도체" and round(got[0]["w"] * 100) == 80 and got[0]["names"] == ["가나전자"] and got[0]["limit"] == 35
    assert got[1]["name"] == "화학"                                         # 마바물산 30,000원 / 60,000원 = 50% > 35%


def test_a_share_over_its_limit_never_reads_as_the_limit():
    got = run("""out = [V.limitPct(0.304, 30), V.limitPct(0.296, 30), V.limitPct(0.30, 30), V.limitPct(0.3004, 30), V.limitPct(0.481, 35), V.limitPct(0.35, 35),
      V.limitPct(0.004, 30), V.limitPct(0.0094, 30), V.limitPct(0.0096, 30)];""")
    assert got == ["30.4", "30", "30", "30.04", "48", "35", "0.4", "0.9", "1"]          # 작은 종목은 0% 로 읽히지 않아요


def test_value_fix_compares_net_income_with_net_income():
    got = run("""out = { a: K.pastNiGrowth({ ni: [452068, 344513.5, 154871], fy: 2025 }), b: K.pastNiGrowth({ ni: [-251.4, 488.3, 812.4] }),
        c: K.pastNiGrowth({ ni: [100, 90, -5] }), d: K.pastNiGrowth({ ni: [100, 90, null] }), e: K.pastNiGrowth({ ni: [81, 0, 100] }), f: K.pastNiGrowth(null),
        vs: [K.dcfVs(4, 26), K.dcfVs(30, 26), K.dcfVs(29, 26), K.dcfVs(22.96, 26), K.dcfVs(22.94, 26), K.dcfVs(null, 2)],
        txt: [X.pastNiText(26.04), X.pastNiText(-10), X.pastNiText(-0.04), X.pastNiText(NaN)], on: X.DCF_NI };""")
    assert abs(got["a"]["x"] - ((452068 / 154871) ** 0.5 - 1) * 100) < 1e-9 and got["a"]["fy"] == 2025
    assert got["b"] is None and got["c"] is None and got["d"] is None and got["f"] is None     # 둘 다 0보다 클 때만
    assert abs(got["e"]["x"] - (-10.0)) < 1e-9                              # 가운데 해는 보지 않아요 (81 / 100 → 연 −10%)
    assert got["vs"] == ["lower", "higher", "similar", "similar", "lower", None]   # 보이는 한 자리 숫자로 3%p 안이면 비슷해요
    assert got["txt"] == ["연평균 26.0% 늘었어요", "연평균 10.0% 줄었어요", "연평균 0.0% 늘었어요", None]   # 빼기 기호 없이
    assert got["on"] is True


def test_value_tab_never_reads_revenue_growth_while_the_fix_is_on():
    src = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    dcf = src.split("function Dcf({", 1)[1].split("\nfunction DcfRevenue(", 1)[0]
    assert "if (!DCF_NI) return <DcfRevenue" in dcf
    on = dcf.split("if (!DCF_NI) return <DcfRevenue", 1)[1]
    assert "g3" not in on and "growthBasis" not in on and "growthKr" not in on and "pastNiGrowth(co)" in on


def test_warning_chips_only_for_checks_that_ran_and_passed():
    got = run("""const s = { t: '000010', cls: 'kr' };
      const f = (co) => K.warnChips(W.warnings(s, co));
      out = { all: f({ flRan: ['cr', 'icr', 'l3', 'imp'] }), off: f({ flRan: ['cr', 'l3', 'imp'], flWhy: { icr: 'off' } }),
        fin: f({ flRan: ['l3', 'imp'], flNa: ['cr', 'icr'] }), fired: f({ flRan: ['cr', 'icr', 'l3', 'imp'], fl: { cr: 80, l3: true } }),
        none: f({}), old: f({ fl: {} }), us: K.warnChips(W.warnings({ t: 'AAA', cls: 'us' }, { flRan: ['cr'] })),
        words: ['l3', 'cr', 'imp', 'icr'].map((c) => C.co.warn.chips[c]) };""")
    assert got["all"] == ["l3", "cr", "imp", "icr"]                        # 보드 순서
    assert got["off"] == ["l3", "cr", "imp"]                                # 꺼진 이자보상배율: 칩 없음
    assert got["fin"] == ["l3", "imp"]                                       # 해당 없음: 칩 없음
    assert got["fired"] == ["imp", "icr"] and got["none"] == [] and got["old"] == [] and got["us"] == []
    assert got["words"] == ["3년 연속 적자 아님", "유동비율 100% 이상", "자본잠식 없음", "이자보상배율 1배 이상"]


def test_rise_day_counts_and_together():
    stocks = [kr(f"0000{i}0", f"회사{i}", 1000.0, d1=d) for i, d in enumerate([6.0, 1.0, 2.0, 3.0, 0.5, -1.0])]
    got = run("""const g = T.peerGroup(S[0], S); const h = T.peerGroup({ ...S[0], d1: -6 }, S.map((x, i) => i ? { ...x, d1: -1 } : { ...x, d1: -6 }));
      out = { g: [g.rose, g.fell, g.together, g.togetherUp], h: [h.rose, h.fell, h.together, h.togetherUp] };""", S=stocks)
    assert got["g"] == [5, 1, False, True] and got["h"] == [0, 6, True, False]


def test_payout_as_won_out_of_a_hundred():
    got = run("""out = [X.payoutWon(24.6), X.payoutWon(0.3), X.payoutWon(99.6), X.payoutWon(50), X.payoutWon(100), X.payoutWon(99.97)];""")
    assert got == [{"x": "25", "y": "75", "rest": True}, {"x": "0.3", "y": "99.7", "rest": True}, {"x": "99.6", "y": "0.4", "rest": True},
                   {"x": "50", "y": "50", "rest": True}, {"x": "100.0", "y": "0.0", "rest": False}, {"x": "100.0", "y": "0.0", "rest": False}]   # '나머지 0원'은 말하지 않아요


def test_tile_pictures_follow_the_tile_rule_only():
    got = run("""out = { s: [A.scaleAt(1.1, 1.6), A.scaleAt(10, 1), A.scaleAt(0.01, 1), A.scaleAt(null, 1), A.scaleAt(1, 0)] };""")
    assert abs(got["s"][0] - 0.5 * 1.1 / 1.6) < 1e-12 and got["s"][1] == 0.96 and got["s"][2] == 0.04 and got["s"][3] is None and got["s"][4] is None


def test_the_value_fix_is_on():
    """가치 고침(DCF_NI)은 틀린 비교를 고치는 것이라 켜 두어요. 예전 카드(매출과 비교)는 스위치를 되돌릴 때만 써요."""
    import re
    got = re.findall(r"^export const DCF_NI = (true|false);$", open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read(), flags=re.M)
    assert got == ["true"]


def test_dividend_tile_coins_follow_its_rule():
    """배당 칸의 동전 그림: 늘렸어요(streak · raised)만 올라가는 더미, 늘지 않은 지급(steady · pays · noPrev)은 같은 높이,
    줄였어요(cut) · 배당이 없어요 · 자료가 없어요는 그림 없음 (현대차의 '배당을 줄였어요' 옆에 올라가는 더미가 없게)."""
    got = run("""out = ['streak', 'raised', 'steady', 'pays', 'noPrev', 'cut', 'none', 'na'].map((r) => Co.divArt(r));""")
    assert got == [{"kind": "coins", "shape": "rising"}] * 2 + [{"kind": "coins", "shape": "even"}] * 3 + [None] * 3


def test_holding_line_matches_the_rest_of_the_page():
    """회사 페이지의 가진 비중: 포트폴리오가 하나뿐일 때만 '내 포트폴리오의 {x}%', 아니면 이름과 함께. 만든 포트폴리오는 비중 규칙
    줄처럼 한 자리(14.5%), 가진 종목 포트폴리오는 한 종목 한계에 맞춰(30.4% 는 30% 가 아니에요)."""
    got = run("""const imp = { kind: 'imported', limits: { stock: 30 } };
      const f = (w, imported, single, deck = imported ? imp : {}) => Co.holdLine({ name: '배당 포트폴리오', x: { w }, imported, deck }, single);
      out = [f(0.145, false, true), f(0.145, false, false), f(0.304, true, true), f(0.304, true, false), f(0.296, true, true), f(0.004, true, true),
        f(0.4449, true, true), f(null, false, true), f(0.20, true, true, { kind: 'imported', limits: { stock: 15 } })];""")
    assert got == ["내 포트폴리오의 14.5%", "배당 포트폴리오의 14.5%", "내 포트폴리오의 30.4%", "배당 포트폴리오의 30.4%", "내 포트폴리오의 30%",
                   "내 포트폴리오의 0.4%", "내 포트폴리오의 44%", "배당 포트폴리오", "내 포트폴리오의 20%"]


def test_comparison_title_counts_the_smaller_median():
    got = run("""out = [X.compareN(38, { med: 1, n: 30 }), X.compareN(38, { med: 1, n: 40 }), X.compareN(38, null), X.compareN(12, { med: 1, n: 0 })];""")
    assert got == [30, 38, 38, 12]


def test_home_money_says_why_there_is_no_value():
    nopx = [dict(s) for s in STOCKS]
    nopx[0]["price"] = None
    got = run("""const d = impDeck([row('000010', '가나전자', 10, { avg: 8000 }), row('000020', '가나은행', 5)]);
      const ctx = ctxOf(NOPX); const [b] = Hm.homeBlocks([d], R.evaluateAll([d], ctx), ctx, NOPX);
      out = b.money;""", NOPX=nopx)
    assert got == {"ok": False, "why": "price", "absent": []}                 # 홈은 빈 카드 대신 카드를 빼고 콘솔에 이유를 남겨요


def test_dcf_bar_draws_nothing_at_or_below_zero():
    src = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    bar = src.split("function DcfBar(", 1)[1].split("\nfunction ", 1)[0]
    assert "{x > 0 && <div" in bar and "Math.max(0, x)" not in bar
