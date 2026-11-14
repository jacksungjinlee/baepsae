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
                              ("X", "cotabs.jsx"), ("V", "pfview.jsx"), ("A", "coart.jsx"), ("Co", "company.jsx"), ("F", "cofmt.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/home.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8",
                            "--define:process.env.NODE_ENV='\"production\"'"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    pre = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import { Hm, P, T, R, K, W, X, V, A, Co, F, C } from './home.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m));\n" + pre + HELP
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
    """v19.6a (Jack's yes needed: the expectation changed with the lot maths): after a sale, 산 가격보다 counts the remaining
    cost of the open lots (moving average). Before v19.6a the sale case had no line (None)."""
    got = run("""const rows = [['000010', '가나전자', 0.5, 10, 8000], ['AAA', 'Alpha Inc.', 0.5, 1, 90]];
      const [b] = blockOf(builtDeck(rows), STOCKS);
      const [s] = blockOf(builtDeck(rows, { sales: [{ t: '000010', qty: 1, price: 9000, date: '2026-10-20', ccy: 'KRW' }] }), STOCKS);
      out = { g: b.money.gain, day: b.money.day, sale: s.money.gain };""", STOCKS=STOCKS)
    assert got["g"]["n"] == 2 and got["g"]["cost"] == 10 * 8000 + 90 * 1100 and got["g"]["usdToday"] is False   # 산 날 환율
    assert got["day"] is None                                                # 미국 종목이 있으면 '오늘' 없음
    # 판 기록 (v19.6a; before: None): 10주 중 1주를 팔면 원금은 9주 × 8,000원 + 미국 1주 × $90 × 1,100원
    assert got["sale"]["n"] == 2 and got["sale"]["cost"] == 9 * 8000 + 90 * 1100 and got["sale"]["value"] == 9 * 10000 + 100 * 1000
    assert got["sale"]["gain"] == got["sale"]["value"] - got["sale"]["cost"]


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
    # v19.3d2 (Jack Q8): 반도체 is in the one chip group of the 한 업종 rule (pf.js CHIP_GROUP; the screens name it 반도체·전자부품)
    assert got[0]["ind"] == "chips" and got[0]["name"] is None and round(got[0]["w"] * 100) == 80 and got[0]["names"] == ["가나전자"] and got[0]["limit"] == 35
    assert got[1]["name"] == "화학"                                         # 마바물산 30,000원 / 60,000원 = 50% > 35%


def test_a_share_over_its_limit_never_reads_as_the_limit():
    got = run("""out = [V.limitPct(0.304, 30), V.limitPct(0.296, 30), V.limitPct(0.30, 30), V.limitPct(0.3004, 30), V.limitPct(0.481, 35), V.limitPct(0.35, 35),
      V.limitPct(0.004, 30), V.limitPct(0.0094, 30), V.limitPct(0.0096, 30)];""")
    assert got == ["30.4", "30", "30", "30.04", "48", "35", "0.4", "0.9", "1"]          # 작은 종목은 0% 로 읽히지 않아요


def test_value_fix_compares_net_income_with_net_income():
    got = run("""out = { a: K.pastNiGrowth({ ni: [452068, 344513.5, 154871], fy: 2025 }), b: K.pastNiGrowth({ ni: [-251.4, 488.3, 812.4] }),
        c: K.pastNiGrowth({ ni: [100, 90, -5] }), d: K.pastNiGrowth({ ni: [100, 90, null] }), e: K.pastNiGrowth({ ni: [81, 0, 100] }), f: K.pastNiGrowth(null),
        vs: [K.dcfVs(4, 26), K.dcfVs(30, 26), K.dcfVs(29, 26), K.dcfVs(22.96, 26), K.dcfVs(22.94, 26), K.dcfVs(null, 2)],
        txt: [X.pastNiText(26.04), X.pastNiText(-10), X.pastNiText(-0.04), X.pastNiText(NaN)] };""")
    assert abs(got["a"]["x"] - ((452068 / 154871) ** 0.5 - 1) * 100) < 1e-9 and got["a"]["fy"] == 2025
    assert got["b"] is None and got["c"] is None and got["d"] is None and got["f"] is None     # 둘 다 0보다 클 때만
    assert abs(got["e"]["x"] - (-10.0)) < 1e-9                              # 가운데 해는 보지 않아요 (81 / 100 → 연 −10%)
    assert got["vs"] == ["lower", "higher", "similar", "similar", "lower", None]   # 보이는 한 자리 숫자로 3%p 안이면 비슷해요
    assert got["txt"] == ["연평균 26.0% 늘었어요", "연평균 10.0% 줄었어요", "연평균 0.0% 늘었어요", None]   # 빼기 기호 없이


def test_value_tab_never_reads_revenue_growth():
    """예전 카드(매출 증가율과 비교)는 지웠어요 (Jack, 2026-11-08)."""
    src = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    dcf = src.split("function Dcf({", 1)[1].split("\n}\n", 1)[0]
    assert "g3" not in dcf and "growthBasis" not in dcf and "growthKr" not in dcf and "pastNiGrowth(co)" in dcf
    assert "DcfRevenue" not in src and "DCF_NI" not in src


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


def test_dividend_tile_coins_follow_its_rule():
    """배당 칸의 동전 그림: 늘렸어요(streak · raised)만 올라가는 더미, 작년과 비슷하게(steady)는 같은 높이 셋, 해마다 비교하지 않은
    지급(pays: 미국 · 추세 꺼짐, noPrev: 작년 기록 없음)은 더미 하나(3년 내내 같았다고 그리지 않게), 줄였어요(cut) · 배당이 없어요 ·
    자료가 없어요는 그림 없음 (현대차의 '배당을 줄였어요' 옆에 올라가는 더미가 없게)."""
    got = run("""out = ['streak', 'raised', 'steady', 'pays', 'noPrev', 'cut', 'none', 'na'].map((r) => Co.divArt(r));""")
    assert got == ([{"kind": "coins", "shape": "rising"}] * 2 + [{"kind": "coins", "shape": "even"}] + [{"kind": "coins", "shape": "one"}] * 2
                   + [None] * 3)


def test_coin_picture_draws_one_stack_for_one_and_three_for_the_others():
    """동전 그림의 더미 수: one 은 하나, even · rising 은 셋 (그림 안 더미 = 같은 x 의 동전들)."""
    got = run("""const walk = (n, acc) => { if (Array.isArray(n)) n.forEach((x) => walk(x, acc));
        else if (n && typeof n === 'object' && n.props) { if (n.type === 'ellipse') acc.push(n.props.cx); walk(n.props.children, acc); } return acc; };
      const stacks = (shape) => { const el = A.Coins({ shape }); const cx = walk(el, []);
        return { shape: el.props['data-shape'], xs: new Set(cx).size, coins: cx.length }; };
      out = ['one', 'even', 'rising'].map(stacks);""")
    assert got == [{"shape": "one", "xs": 1, "coins": 3}, {"shape": "even", "xs": 3, "coins": 9}, {"shape": "rising", "xs": 3, "coins": 9}]


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


def test_the_four_rules_only_judge_portfolios_made_with_imported_holdings():
    """Jack (2026-11-08): 포트폴리오 규칙 네 가지는 가진 종목 넣기로 만든 포트폴리오에만. 포트폴리오 만들기로 만든 포트폴리오는
    자기 종목별 규칙과 비중 띠로만 봐요 (홈의 판정 띠), 네 규칙으로 판정하지 않아요."""
    got = run("""const b = builtDeck([['000010', '가나전자', 0.5, 10, 8000], ['000020', '가나은행', 0.5, 5, 18000]]);
      const d = impDeck([row('000010', '가나전자', 10)]);
      const ctx = ctxOf(STOCKS); const blocks = Hm.homeBlocks([b, d], R.evaluateAll([b, d], ctx), ctx, STOCKS);
      out = blocks.map((x) => [x.deck.id, x.st == null ? null : x.st.rules.length, x.money.ok]);""", STOCKS=STOCKS)
    assert got == [["dbuilt", None, True], ["dimp", 4, True]]


def test_filing_rows_only_from_a_loaded_fresh_list_and_the_last_seven_days():
    ins = [{"rc": "1", "d": "20261106", "t": "000010", "q": 100}, {"rc": "2", "d": "20261105", "t": "000010", "q": -50},
           {"rc": "3", "d": "20261030", "t": "000010", "q": 10},                      # 8일 전: 빠져요
           {"rc": "4", "d": "20261104", "t": "000020", "q": -5}, {"rc": "5", "d": "20261106", "t": "999999", "q": 5},   # 가지지 않은 종목
           {"rc": "6", "d": "20261107", "t": "000040", "q": 0}]                       # 0주는 변동이 아니에요
    got = run("""const disc = { status: 'ok', data: { insider: INS } }; const held = new Set(['000010', '000020', '000040']);
      out = { ok: Hm.filingRows(disc, held, '2026-11-07', { stale: false }), stale: Hm.filingRows(disc, held, '2026-11-07', { stale: true }),
        none: Hm.filingRows({ status: 'idle' }, held, '2026-11-07', { stale: false }), nofresh: Hm.filingRows(disc, held, '2026-11-07', null),
        edge: Hm.filingRows(disc, held, '2026-11-12', { stale: false }) };""", INS=ins)
    # 000010: 그 주에 늘린 보고(11-06)와 줄인 보고(11-05)가 섞였어요 → 방향 없음 ('지분 변동 보고', Jack 2026-11-08)
    assert got["ok"] == [{"t": "000010", "n": 2, "date": "2026-11-06", "up": None}, {"t": "000020", "n": 1, "date": "2026-11-04", "up": False}]
    assert got["stale"] == [] and got["none"] == [] and got["nofresh"] == []     # 멈춘 목록 · 아직 받지 않은 목록: 줄 없음
    assert got["edge"] == [{"t": "000010", "n": 1, "date": "2026-11-06", "up": True}]   # 11-12 기준 7일: 11-06 부터


def test_dividend_picture_wording_is_past_based_for_korea():
    got = run("""out = [C.co.div.coins, C.co.div.pastYear, C.co.div.year === undefined, C.co.tiles.scale];""")
    assert got == ["100만원어치", "100만원어치면 지난 1년 배당으로 약 {x}이에요.", True, {"cheap": "싸게", "dear": "비싸게"}]


def test_nothing_to_do_needs_every_judged_rule_checked_and_a_known_value():
    """'오늘은 할 일이 없어요'(home.quietBlock): 가진 종목 포트폴리오가 오늘 데이터로 점검됐고, 깨진 규칙이 없고, 한 종목 · 한 업종 ·
    내 기준이 모두 확인됐고, 평가 금액을 알 때만. 재무 경고만은 확인하지 못했어요여도 돼요(미국 종목). 아무 규칙도 확인하지 못했으면
    (오늘 가격이 없는 종목 · 오늘 데이터에서 빠진 종목 + 미국 종목) 절대 아니에요. 만든 포트폴리오(규칙 넷 없음)는 여기서 조용하지 않아요."""
    nopx = [dict(s) for s in STOCKS]
    nopx[1]["price"] = None
    got = run("""const even = [row('000010', '가나전자', 10), row('000020', '가나은행', 5), row('000040', '마바물산', 20), row('AAA', 'Alpha Inc.', 1)];
      const q = (deck, stocks = STOCKS) => { const [b] = blockOf(deck, stocks); return { quiet: Hm.quietBlock(b),
        st: b.st.rules.map((r) => r.id + ':' + r.state), checked: b.st.checked, money: b.money.ok, absent: b.money.absent.length }; };
      const built = blockOf(builtDeck([['000010', '가나전자', 0.5, 10, 8000], ['000020', '가나은행', 0.5, 5, 18000]]), STOCKS)[0];
      out = { even: q(impDeck(even)), broken: q(impDeck([row('000010', '가나전자', 100), ...even.slice(1)])),
        noCards: q(impDeck(even, { settings: { points: {}, strict: 'normal' } })),
        noPrice: q(impDeck(even), NOPX), gone: q(impDeck([...even, row('000099', '없는회사', 3)])),
        built: Hm.quietBlock(built), none: [Hm.quietBlock(null), Hm.quietBlock({ st: { ok: false, why: 'stale' }, money: { ok: true, absent: [] } })] };""",
              STOCKS=STOCKS, NOPX=nopx)
    e = got["even"]
    assert e["st"][:3] == ["stock:ok", "ind:ok", "fit:ok"] and e["st"][3] == "warn:unknown" and e["money"] and e["quiet"] is True, e
    assert got["broken"]["st"][0] == "stock:broken" and got["broken"]["quiet"] is False
    assert "fit:unknown" in got["noCards"]["st"] and got["noCards"]["quiet"] is False           # 고른 기준이 없으면 내 기준을 확인하지 못했어요
    n = got["noPrice"]                                                                       # 오늘 가격이 없는 종목 + 미국 종목: 네 칸 모두 확인하지 못했어요
    assert n["st"] == ["stock:unknown", "ind:unknown", "fit:unknown", "warn:unknown"] and n["checked"] == 0 and not n["money"] and n["quiet"] is False, n
    g = got["gone"]                                                                          # 오늘 데이터에서 빠진 종목: 값은 나머지로, 규칙은 확인하지 못했어요
    assert g["checked"] == 0 and g["absent"] == 1 and g["quiet"] is False, g
    assert got["built"] is False and got["none"] == [False, False]


def test_built_portfolio_bars_are_never_drawn_against_the_stock_limit():
    """만든 포트폴리오는 한 종목 30% 규칙으로 판정하지 않아요 (Jack, 2026-11-08): 홈의 막대는 전체(100%)에 대한 비중이에요. 반반이면
    두 막대가 절반씩이고, 가득 찬 막대 둘이 아니에요. 가진 종목 포트폴리오는 그대로 한 종목 한계에 대한 길이."""
    got = run("""const b = blockOf(builtDeck([['000010', '가나전자', 0.5, 10, 8000], ['000020', '가나은행', 0.5, 5, 18000]]), STOCKS)[0];
      out = { w: b.list.rows.map((r) => r.w), built: b.list.rows.map((r) => Hm.barOf(r.w, 100)), imp: b.list.rows.map((r) => Hm.barOf(r.w, 30)) };""",
              STOCKS=STOCKS)
    assert got["w"] == [0.5, 0.5] and got["built"] == [0.5, 0.5] and got["imp"] == [1, 1]


def test_rate_date_line_shows_when_the_rate_is_from_another_day():
    """미국 머리줄(US_HEAD2)은 '약 {won} · 환율 {fx}원' 한 줄. 환율 날짜가 머리줄의 가격 날짜와 다르면 '원화는 {md} 환율 {fx}원으로
    바꾼 값이에요.'를 그대로 보여 줘요 (그 날짜의 환율로 읽히지 않게). 같은 날이면 없어요. 한국 종목은 없어요."""
    got = run("""const us = { t: 'AAA', cls: 'us', ccy: 'USD', price: 100 };
      const ld = (fxDate, extra = {}) => ({ data: { pxDate: '2026-11-06', usPxDate: '2026-11-05', fxDate, fx: 1390.46, ...extra } });
      out = { head2: F.US_HEAD2, same: F.fxDateLine(ld('2026-11-05'), us), other: F.fxDateLine(ld('2026-11-06'), us),
        own: F.fxDateLine(ld('2026-11-05'), { ...us, pxd: '2026-11-04' }), kr: F.fxDateLine(ld('2026-11-05'), { t: '000010', cls: 'kr', price: 1000 }),
        noDate: F.fxDateLine(ld(null), us), noFx: F.fxDateLine(ld('2026-11-06', { fx: null }), us) };""")
    assert got["head2"] is True                                              # 켜진 상태를 시험해요 (꺼지면 늘 보여요: 예전 그대로)
    assert got["same"] is None
    assert got["other"] == "원화는 11월 6일 환율 1,390.5원으로 바꾼 값이에요."
    assert got["own"] == "원화는 11월 5일 환율 1,390.5원으로 바꾼 값이에요."   # 이전 종가로 값을 매긴 미국 종목: 머리줄 날짜는 11월 4일
    assert got["kr"] is None and got["noDate"] is None and got["noFx"] is None


def test_filing_title_names_a_direction_only_when_the_whole_week_agrees():
    """Jack (2026-11-08): 그 주 보고가 모두 같은 쪽일 때만 방향(늘린 보고 · 줄인 보고), 섞이면 '지분 변동 보고'."""
    ins = [{"rc": "1", "d": "20261106", "t": "000010", "q": 100}, {"rc": "2", "d": "20261103", "t": "000010", "q": 7},      # 모두 늘림
           {"rc": "3", "d": "20261105", "t": "000020", "q": -5}, {"rc": "4", "d": "20261102", "t": "000020", "q": -9},      # 모두 줄임
           {"rc": "5", "d": "20261106", "t": "000040", "q": 3}, {"rc": "6", "d": "20261104", "t": "000040", "q": -2},       # 섞임
           {"rc": "7", "d": "20261104", "t": "000040", "q": -1}]
    got = run("""const disc = { status: 'ok', data: { insider: INS } };
      out = { rows: Hm.filingRows(disc, new Set(['000010', '000020', '000040']), '2026-11-07', { stale: false }), both: C.home.filingsBoth,
        checked: [Hm.filingsChecked(disc, { stale: false }), Hm.filingsChecked(disc, { stale: true }), Hm.filingsChecked({ status: 'fail' }, null),
          Hm.filingsChecked({ status: 'loading' }, null)] };""", INS=ins)
    by = {r["t"]: r for r in got["rows"]}
    assert by["000010"]["up"] is True and by["000020"]["up"] is False and by["000040"]["up"] is None, got["rows"]
    assert by["000040"]["n"] == 3 and by["000040"]["date"] == "2026-11-06"
    assert got["both"] == "지분 변동 보고"
    assert got["checked"] == [True, False, False, False]                       # 멈춘 목록 · 실패 · 받는 중: 확인한 게 아니에요


def test_holds_korean_counts_only_korean_stocks_held_today():
    """홈이 공시 목록(disc.json)을 받는 조건: 저장한 포트폴리오 어디든 지금 가진 한국 종목이 있을 때 (계획만 하고 사지 않은 종목 · 미국 종목만은 아니에요)."""
    got = run("""const kr = builtDeck([['000010', '가나전자', 1, 10, 8000]]);
      const planned = builtDeck([['000010', '가나전자', 1, 0, 0]]);
      const usOnly = impDeck([row('AAA', 'Alpha Inc.', 2)]);
      const impKr = impDeck([row('AAA', 'Alpha Inc.', 2), row('000020', '가나은행', 3)]);
      const noCls = { ...impKr, holdings: [] };
      const sold = builtDeck([['000010', '가나전자', 1, 10, 8000]], { sales: [{ t: '000010', qty: 10, price: 9000, date: '2026-10-20', ccy: 'KRW' }] });
      out = [Hm.holdsKorean([kr]), Hm.holdsKorean([planned]), Hm.holdsKorean([usOnly]), Hm.holdsKorean([usOnly, impKr]), Hm.holdsKorean([noCls]),
        Hm.holdsKorean([sold]), Hm.holdsKorean([]), Hm.holdsKorean(null)];""")
    assert got == [True, False, False, True, True, False, False, False]


def test_quiet_needs_every_holding_in_the_industry_rule_and_scored():
    """리뷰(2026-11-08) 프로브: 금액만 넣은 '비상장' 20% 줄은 한 업종 · 내 기준 계산에서 빠져요. 두 칸이 ✓ 여도 빠진 종목을 홈이 말하지
    않으니 '오늘은 할 일이 없어요'가 아니에요. 업종 정보가 없는 종목도 같아요."""
    nogroup = [dict(s) for s in STOCKS] + [kr("000050", "무업종", 5000.0, ind=None)]
    got = run("""const even = [row('000010', '가나전자', 10), row('000020', '가나은행', 5), row('000040', '마바물산', 20), row('AAA', 'Alpha Inc.', 1)];
      const q = (deck, stocks = STOCKS) => { const [b] = blockOf(deck, stocks);
        return { quiet: Hm.quietBlock(b), st: b.st.rules.map((r) => r.id + ':' + r.state), none: b.st.ind.none.rows.length, unscored: b.st.stats.unscored.length,
          w: b.st.view.rows.map((r) => Math.round(r.w * 1000) / 10) }; };
      out = { even: q(impDeck(even)), amount: q(impDeck([...even, { nk: '비상장', amountWon: 100000, date: '2026-10-01' }])),
        nogroup: q(impDeck([...even, row('000050', '무업종', 20)]), NOGROUP) };""", STOCKS=STOCKS, NOGROUP=nogroup)
    assert got["even"]["quiet"] is True and got["even"]["none"] == 0 and got["even"]["unscored"] == 0
    a = got["amount"]
    assert a["w"][-1] == 20.0 and a["st"][:3] == ["stock:ok", "ind:ok", "fit:ok"], a       # 프로브 그대로: 두 칸 ✓
    assert a["none"] == 1 and a["unscored"] == 1 and a["quiet"] is False, a                # 그래도 할 일이 없다고 하지 않아요
    n = got["nogroup"]
    assert n["none"] == 1 and n["quiet"] is False, n


def test_built_weight_on_home_is_the_weight_on_portfolio():
    """만든 포트폴리오의 홈 비중 (리뷰 2026-11-08 두 번째 · 세 번째): 모든 종목에 비중 규칙이 있으면 매일 점검의 비중(x.w, 포트폴리오의 비중
    규칙 줄과 같은 숫자). 비중 규칙을 끈 종목이 하나라도 있으면(같은 금액 세 종목 중 하나) 그 포트폴리오의 모든 줄이 전체에 대한
    비중(33.3% 셋)이에요: 빈칸이 없고, '비중' 아래 숫자가 모두 같은 전체의 몫이에요 (일부끼리의 50.0% 가 아니에요)."""
    got = run("""const rows = [['000010', '가나전자', 1 / 3, 10, 10000], ['000020', '가나은행', 1 / 3, 5, 20000], ['000040', '마바물산', 1 / 3, 20, 5000]];
      const one = (off) => { const d = builtDeck(rows); if (off) d.holdings[2].rules = [];
        const ctx = ctxOf(STOCKS); const ev = R.evaluateAll([d], ctx); const [b] = Hm.homeBlocks([d], ev, ctx, STOCKS);
        return { home: Object.fromEntries(b.list.rows.map((r) => [r.t, r.w == null ? null : Math.round(r.w * 1000) / 10])),
          check: Object.fromEntries(ev.decks[0].holdings.map((x) => [x.t, x.w == null ? null : Math.round(x.w * 1000) / 10])) }; };
      out = { on: one(false), off: one(true) };""", STOCKS=STOCKS)
    assert got["on"]["home"] == got["on"]["check"] == {"000010": 33.3, "000020": 33.3, "000040": 33.3}, got["on"]      # 모두 켜짐: 매일 점검의 비중
    assert got["off"]["check"] == {"000010": 50.0, "000020": 50.0, "000040": None}, got["off"]                        # 포트폴리오: 규칙 있는 종목끼리
    assert got["off"]["home"] == {"000010": 33.3, "000020": 33.3, "000040": 33.3}, got["off"]                          # 홈: 모두 전체에 대한 비중


def test_holds_korean_falls_back_to_the_market_in_todays_data():
    """리뷰(2026-11-08): 저장한 종목에 시장(cls)이 없으면 오늘 데이터의 시장을 봐요."""
    got = run("""const d = builtDeck([['000010', '가나전자', 1, 10, 8000]]); d.holdings = d.holdings.map(({ cls, ...h }) => h);
      const u = builtDeck([['AAA', 'Alpha Inc.', 1, 2, 90]]); u.holdings = u.holdings.map(({ cls, ...h }) => h);
      const byT = ctxOf(STOCKS).byT;
      out = [Hm.holdsKorean([d]), Hm.holdsKorean([d], byT), Hm.holdsKorean([u], byT), Hm.holdsKorean([d], new Map())];""", STOCKS=STOCKS)
    assert got == [False, True, False, False]
