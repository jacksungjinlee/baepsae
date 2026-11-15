# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6f 연말에 확인할 숫자 (src/v2/tax.js) — Node 로 돌려봐요.

docs/tasks/v19.6-records-alerts-dark.md Part F:
- 보이는 때: 한국 날짜로 TAX_YEAR(2026) 의 11월 1일 ~ 12월 31일, 결제일 줄은 12월 15일부터. 다른 해는 닫혀요 (사실을 다시 확인하는
  PR 이 TAX_YEAR 를 옮길 때까지). 기기의 시간대(미국 서부 · 키리티마티 UTC+14)와 상관없이 한국 날짜로
- 링크 조건: 올해 미국 판 기록 · 미국 가진 종목 · 올해 배당 기록 중 하나 (모든 포트폴리오, 뺀 종목의 기록 포함)
- 양도차익: 올해 날짜의 미국 판 기록만, 이동평균(A.4), 판 기록마다 자기 환율. 달러 평균 단가만 있는 종목은 판 날 환율. 수익을
  모르는 판 기록은 빼고 그 수를 세요 (0 으로 세지 않아요). 두 포트폴리오에 같은 거래를 적으면 두 번 (알려진 한계, 화면의 줄이 말해요)
- 세 상태: 공제 250만원보다 적음 · 같음 · 많음 (세금 = (차익 − 250만원) × 22%, 1,000원 단위) · 손실
- 배당: 한국 ÷ (1 − 15.4%), 미국 (달러 × 그 기록의 환율) ÷ (1 − 15%), 1,000원 단위. 환율 없는 미국 배당은 빼고 세요
- 손실 중인 미국 종목: 종목마다 모든 포트폴리오를 더해서, 한 포트폴리오라도 셀 수 없으면 그 종목은 통째로 빠지고 이유별로 이름이 남아요
기대값은 모두 손으로 계산했어요 (계산한 코드를 다시 쓰지 않아요).
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
MODS = (("X", "tax.js"), ("L", "lots.js"), ("F", "format.js"))


def run(body, tz=None, **data):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-tax-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in MODS:
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/tax.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    pre = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import { X, L, F } from './tax.mjs';\nconsole.warn = () => {}; console.info = () => {};\n" + pre + HELP + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    env = dict(os.environ)
    if tz:
        env["TZ"] = tz
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


HELP = """
const usd = (t) => !/^[0-9]/.test(t);
const buy = (t, qty, price, date, extra = {}) => ({ t, qty, price, date, ccy: usd(t) ? 'USD' : 'KRW', ...extra });
const sell = buy;
const div = (t, amount, date, extra = {}) => ({ t, amount, date, ccy: usd(t) ? 'USD' : 'KRW', ...extra });
const deck = (id, extra = {}) => ({ id, name: id, createdAt: '2025-01-02', holdings: [], purchases: [], ...extra });
const hold = (...ts) => ts.map((t) => ({ t, nk: t, cls: usd(t) ? 'us' : 'kr', target: 1 / ts.length }));
const q = (prices, fx = 1400) => ({ pxOf: (t) => (prices[t] > 0 ? prices[t] : null), fx, absent: { has: (t) => !(t in prices) } });
"""


# ── 보이는 때 ──
def test_the_window_is_nov_1_to_dec_31_kst_of_the_tax_year_and_the_settlement_line_from_dec_15():
    got = run("""out = Object.fromEntries(D.map((d) => [d, X.taxWindow(d)]));""",
              D=["2026-10-31", "2026-11-01", "2026-11-15", "2026-12-14", "2026-12-15", "2026-12-31", "2027-01-01", "2026-01-15", "nope", ""])
    closed = {"open": False, "settle": False, "ria": False}
    for d in ("2026-10-31", "2027-01-01", "2026-01-15"):
        assert {k: got[d][k] for k in closed} == closed, d
    for d in ("2026-11-01", "2026-11-15", "2026-12-14"):
        assert got[d] == {"open": True, "year": 2026, "settle": False, "ria": True}, d
    for d in ("2026-12-15", "2026-12-31"):
        assert got[d] == {"open": True, "year": 2026, "settle": True, "ria": True}, d
    assert got["nope"]["open"] is False and got[""]["open"] is False


def test_the_tax_year_gate_closes_every_other_year_until_a_recheck_moves_it():
    got = run("""out = { y: X.TAX_YEAR, checked: X.CHECKED, w: D.map((d) => X.taxWindow(d).open), moved: X.taxWindow('2027-11-15', 2027).open,
      ria27: X.taxWindow('2027-11-15', 2027).ria };""", D=["2027-11-01", "2027-12-15", "2025-11-15", "2025-12-31", "2028-11-01"])
    assert got["y"] == 2026 and got["checked"] == "2026-11-15"
    assert got["w"] == [False] * 5                                   # 2027년 11월에도 닫혀 있어요 (다시 확인하는 PR 전까지)
    assert got["moved"] is True and got["ria27"] is False            # 옮기면 열리지만 RIA 줄은 2026년에만


EDGES = [("2026-10-31T14:59:59Z", "2026-10-31", False, False), ("2026-10-31T15:00:00Z", "2026-11-01", True, False),
         ("2026-12-14T14:59:59Z", "2026-12-14", True, False), ("2026-12-14T15:00:00Z", "2026-12-15", True, True),
         ("2026-12-31T14:59:59Z", "2026-12-31", True, True), ("2026-12-31T15:00:00Z", "2027-01-01", False, False)]


@pytest.mark.parametrize("tz", ["UTC", "Asia/Seoul", "America/Los_Angeles", "Pacific/Kiritimati"])
def test_window_edges_follow_the_korean_date_whatever_the_device_time_zone(tz):
    got = run("""out = { rows: E.map(([iso]) => { const ms = Date.parse(iso); const today = X.taxToday(ms); const w = X.taxWindow(today);
        return [today, w.open, w.settle]; }), local: E.map(([iso]) => new Date(Date.parse(iso)).getDate()), tz: Intl.DateTimeFormat().resolvedOptions().timeZone };""",
              tz=tz, E=EDGES)
    assert got["tz"] == tz or (tz == "UTC" and got["tz"] in ("UTC", "Etc/UTC")), got["tz"]
    for (iso, day, opn, settle), row in zip(EDGES, got["rows"]):
        assert row == [day, opn, settle], (tz, iso, row)
    if tz == "America/Los_Angeles":                                 # 기기의 날짜는 아직 10월 31일 · 12월 31일이에요
        assert got["local"][1] == 31 and got["local"][5] == 31
    if tz == "Pacific/Kiritimati":                                   # 기기의 날짜는 이미 11월 1일 · 1월 1일이에요
        assert got["local"][0] == 1 and got["local"][4] == 1


# ── 링크 조건 ──
def test_the_link_needs_a_us_sale_this_year_a_us_holding_or_a_dividend_this_year():
    got = run("""
      const cases = {
        none: [],
        krHeldOnly: [deck('a', { holdings: hold('005930'), purchases: [buy('005930', 3, 70000, '2026-03-02')] })],
        krDivThisYear: [deck('a', { holdings: hold('005930'), purchases: [buy('005930', 3, 70000, '2026-03-02')], divs: [div('005930', 1083, '2026-04-20')] })],
        krDivLastYear: [deck('a', { holdings: hold('005930'), purchases: [buy('005930', 3, 70000, '2025-03-04')], divs: [div('005930', 1083, '2025-04-18')] })],
        usHeld: [deck('a', { holdings: hold('AAPL'), purchases: [buy('AAPL', 1, 200, '2024-05-01', { fx: 1370 })] })],
        usPlannedOnly: [deck('a', { holdings: hold('AAPL') })],
        usSoldLastYear: [deck('a', { holdings: hold('AAPL'), purchases: [buy('AAPL', 1, 200, '2024-05-01', { fx: 1370 })], sales: [sell('AAPL', 1, 230, '2025-08-01', { fx: 1390 })] })],
        usSaleInHistory: [deck('a', { holdings: hold('005930'), purchases: [buy('005930', 1, 70000, '2025-03-04')],
          history: [{ t: 'AAPL', nk: 'AAPL', out: '2026-06-01', cls: 'us', purchases: [buy('AAPL', 1, 200, '2024-05-01', { fx: 1370 })], sales: [sell('AAPL', 1, 230, '2026-05-29', { fx: 1390 })] }] })],
        usDivInHistory: [deck('a', { history: [{ t: 'KO', nk: 'KO', out: '2026-02-01', cls: 'us', divs: [div('KO', 4.25, '2026-04-01', { fx: 1450 })] }] })],
      };
      out = Object.fromEntries(Object.entries(cases).map(([k, v]) => [k, { r: X.taxRecords(v), open: X.taxOpen(v, '2026-11-15'), closed: X.taxOpen(v, '2026-10-31') }]));""")
    want = {"none": (False, False, False), "krHeldOnly": (False, False, False), "krDivThisYear": (False, False, True),
            "krDivLastYear": (False, False, False), "usHeld": (False, True, False), "usPlannedOnly": (False, False, False),
            "usSoldLastYear": (False, False, False), "usSaleInHistory": (True, False, False), "usDivInHistory": (False, False, True)}
    for k, (sale, held, dv) in want.items():
        r = got[k]["r"]
        assert (r["usSale"], r["usHeld"], r["div"]) == (sale, held, dv), (k, r)
        assert got[k]["open"] is (sale or held or dv), k
        assert got[k]["closed"] is False, k                          # 10월 31일에는 아무에게도 없어요


# ── 양도차익 ──
def test_hand_worked_gain_moving_average_each_sale_at_its_own_rate():
    got = run("""const a = deck('a', { holdings: hold('AAA'), purchases: [buy('AAA', 10, 100, '2025-06-02', { fx: 1300 }), buy('AAA', 10, 120, '2026-03-02', { fx: 1400 })],
        sales: [sell('AAA', 5, 150, '2026-10-01', { fx: 1350 })] });
      const b = deck('b', { holdings: hold('BBB'), purchases: [buy('BBB', 4, 50, '2025-01-02', { fx: 1200 })], sales: [sell('BBB', 4, 60, '2025-12-30', { fx: 1250 })] });
      out = { one: X.yearGains([a]), both: X.yearGains([a, b]), y25: X.yearGains([a, b], 2025) };""")
    # 산 것: 10주 × $100 × 1,300 = 1,300,000원 + 10주 × $120 × 1,400 = 1,680,000원 = 2,980,000원 (20주)
    # 5주를 팔면 모든 묶음이 5/20 = 1/4 씩 줄어요: 덜어 낸 원가 2,980,000 / 4 = 745,000원
    # 판 금액 5 × $150 × 1,350 = 1,012,500원 → 차익 1,012,500 − 745,000 = 267,500원
    assert got["one"] == {"gain": 267500, "exact": 267500, "n": 1, "left": 0, "usdOnly": False}
    # 2025-12-30 에 판 BBB (4 × 60 × 1,250 − 4 × 50 × 1,200 = 300,000 − 240,000 = 60,000원)는 2025년 몫이라 빠져요
    assert got["both"]["gain"] == 267500 and got["both"]["n"] == 1
    assert got["y25"]["gain"] == 60000 and got["y25"]["n"] == 1


def test_dec_31_is_in_jan_1_is_out_and_korean_sales_never_count():
    got = run("""const d = deck('a', { holdings: hold('AAA', '005930'), purchases: [buy('AAA', 10, 10, '2025-12-01', { fx: 1000 }), buy('005930', 10, 50000, '2026-01-05')],
        sales: [sell('AAA', 1, 20, '2025-12-31', { fx: 1100 }), sell('AAA', 1, 20, '2026-12-31', { fx: 1100 }), sell('AAA', 1, 20, '2027-01-01', { fx: 1100 }),
                sell('005930', 5, 90000, '2026-06-01')] });
      out = X.yearGains([d]);""")
    # 2026-12-31 한 건만: 1 × $20 × 1,100 − 1 × $10 × 1,000 = 22,000 − 10,000 = 12,000원. 한국 종목 차익(+200,000원)은 들어가지 않아요
    assert got == {"gain": 12000, "exact": 12000, "n": 1, "left": 0, "usdOnly": False}


def test_a_dollar_only_holding_sells_at_the_sale_date_rate_and_says_so():
    got = run("""const d = deck('i', { kind: 'imported', settings: { points: {} }, holdings: [{ t: 'AAA', nk: 'Alpha', cls: 'us' }],
        imported: [{ t: 'AAA', nk: 'Alpha', ccy: 'USD', qty: 4, avg: 80 }], sales: [sell('AAA', 1, 100, '2026-10-12', { fx: 1350 })] });
      out = X.yearGains([d]);""")
    assert got == {"gain": 27000, "exact": 27000, "n": 1, "left": 0, "usdOnly": True}     # ($100 − $80) × 1,350


def test_a_sale_whose_gain_is_unknown_is_left_out_and_counted_never_zero():
    got = run("""const noFx = deck('a', { holdings: hold('AAA'), purchases: [buy('AAA', 2, 100, '2026-02-02', { fx: 1300 })], sales: [sell('AAA', 1, 150, '2026-03-02')] });
      const noAvg = deck('b', { kind: 'imported', settings: { points: {} }, holdings: [{ t: 'BBB', nk: 'B', cls: 'us' }],
        imported: [{ t: 'BBB', nk: 'B', ccy: 'USD', qty: 3 }], sales: [sell('BBB', 1, 50, '2026-04-01', { fx: 1400 })] });
      const ok = deck('c', { holdings: hold('CCC'), purchases: [buy('CCC', 1, 10, '2026-02-02', { fx: 1000 })], sales: [sell('CCC', 1, 9, '2026-05-01', { fx: 1000 })] });
      out = X.yearGains([noFx, noAvg, ok]);""")
    assert got == {"gain": -1000, "exact": -1000, "n": 1, "left": 2, "usdOnly": False}     # 9,000 − 10,000; 두 건은 빼고 셈


def test_a_stock_taken_out_keeps_its_sales_and_two_portfolios_count_the_same_trade_twice():
    got = run("""const recs = { purchases: [buy('AAA', 2, 100, '2026-02-02', { fx: 1300 })], sales: [sell('AAA', 2, 110, '2026-08-03', { fx: 1300 })] };
      const hist = deck('h', { holdings: hold('005930'), purchases: [buy('005930', 1, 50000, '2026-01-05')],
        history: [{ t: 'AAA', nk: 'AAA', out: '2026-08-03', cls: 'us', ...recs }] });
      const p1 = deck('p1', { holdings: hold('AAA'), ...recs }), p2 = deck('p2', { holdings: hold('AAA'), ...recs });
      out = { hist: X.yearGains([hist]).gain, twice: X.yearGains([p1, p2]) };""")
    assert got["hist"] == 26000                                       # 2 × ($110 − $100) × 1,300
    assert got["twice"]["gain"] == 52000 and got["twice"]["n"] == 2   # 알려진 한계: 같은 거래를 두 번 적으면 두 번 (화면의 '모든 포트폴리오' 줄)


def test_a_split_between_the_buy_and_the_sale_reads_the_sale_at_the_new_count():
    got = run("""const base = { holdings: hold('AAA'), purchases: [buy('AAA', 10, 100, '2026-02-02', { fx: 1300 })], sales: [sell('AAA', 20, 60, '2026-08-03', { fx: 1400 })] };
      const stored = deck('s', { ...base, splits: [{ t: 'AAA', date: '2026-06-01', r: 2 }] });
      const view = L.withDataSplits({ v: 2, decks: [deck('v', base)] }, [{ t: 'AAA', date: '2026-06-01', r: 2 }], '2026-11-15').decks;
      out = { stored: X.yearGains([stored]), view: X.yearGains(view), none: X.yearGains([deck('n', base)]) };""")
    # 2:1 분할: 10주가 20주가 되고 원가는 그대로 1,300,000원. 판 금액 20 × $60 × 1,400 = 1,680,000원 → 380,000원
    assert got["stored"]["gain"] == 380000 and got["view"]["gain"] == 380000
    assert got["none"] == {"gain": 0, "exact": 0, "n": 0, "left": 1, "usdOnly": False}   # 분할을 모르면 가진 것보다 많이 판 기록: 빼고 셈


def test_the_gain_rounds_half_away_from_zero_to_the_won():
    got = run("""const mk = (id, p, s) => deck(id, { holdings: hold('AAA'), purchases: [buy('AAA', 1, p, '2026-02-02', { fx: 1 })], sales: [sell('AAA', 1, s, '2026-03-02', { fx: 1 })] });
      out = [X.yearGains([mk('a', 100, 100.5)]).gain, X.yearGains([mk('b', 100.5, 100)]).gain, X.yearGains([mk('c', 100, 100.25)]).gain, X.roundWon(-0.4)];""")
    assert got == [1, -1, 0, 0]                                       # +0.5 → 1, −0.5 → −1, 0.25 → 0, −0.4 → 0 (−0 아님)


# ── 세 상태 ──
def test_the_three_states_at_their_boundaries_and_the_estimate_to_1000_won():
    got = run("""out = Object.fromEntries(G.map((g) => [String(g), X.taxState(g)]));""",
              G=[-1, 0, 1250000, 2499999, 2500000, 2500001, 2502272, 2502273, 2525000, 4000000, -350000])
    assert got["-1"] == {"kind": "loss", "x": 1, "t": None, "bar": None}
    assert got["-350000"] == {"kind": "loss", "x": 350000, "t": None, "bar": None}
    assert got["0"] == {"kind": "below", "x": 2500000, "t": None, "bar": 0}
    assert got["1250000"] == {"kind": "below", "x": 1250000, "t": None, "bar": 0.5}
    assert got["2499999"]["kind"] == "below" and got["2499999"]["x"] == 1
    assert got["2500000"] == {"kind": "equal", "x": 0, "t": None, "bar": 1}
    assert got["2500001"] == {"kind": "above", "x": 1, "t": 0, "bar": 1}          # 1 × 22% = 0.22원 → 0원
    assert got["2502272"]["t"] == 0                                                 # 2,272 × 22% = 499.84원 → 0원
    assert got["2502273"]["t"] == 1000                                              # 2,273 × 22% = 500.06원 → 1,000원
    assert got["2525000"]["t"] == 6000                                              # 25,000 × 22% = 5,500원 → 6,000원 (반은 올림)
    assert got["4000000"] == {"kind": "above", "x": 1500000, "t": 330000, "bar": 1}  # 1,500,000 × 22%


def test_the_constants_are_the_rechecked_facts():
    got = run("""out = { d: X.DEDUCTION, r: X.RATE, rp: X.RATE_PCT, kr: X.KR_WH, us: X.US_WH, ria: X.RIA_YEARS, w: X.WINDOW };""")
    assert got == {"d": 2500000, "r": 0.22, "rp": 22, "kr": 0.154, "us": 0.15, "ria": [2026],
                   "w": {"from": "11-01", "to": "12-31", "settle": "12-15"}}


# ── 배당 ──
def test_dividends_turn_back_into_pre_tax_amounts_and_a_us_dividend_without_a_rate_is_counted_out():
    got = run("""const a = deck('a', { holdings: hold('005930', 'KO'), purchases: [buy('005930', 10, 50000, '2025-03-04'), buy('KO', 10, 60, '2025-03-04', { fx: 1450 })],
        divs: [div('005930', 84600, '2026-04-20'), div('KO', 85, '2026-07-01', { fx: 1350 }), div('KO', 3, '2026-10-01'), div('005930', 5000, '2025-12-30')] });
      const b = deck('b', { history: [{ t: '000660', nk: 'SK', out: '2026-02-01', cls: 'kr', divs: [div('000660', 1000, '2026-04-25')] }] });
      out = { a: X.yearDivs([a]), ab: X.yearDivs([a, b]) };""")
    # 84,600 ÷ 0.846 = 100,000원 · $85 × 1,350 = 114,750원 ÷ 0.85 = 135,000원 → 235,000원. 환율 없는 $3 은 빠지고 셈, 2025년 배당도 빠짐
    assert got["a"] == {"won": 235000, "exact": 235000, "n": 2, "kr": 1, "us": 1, "noFx": 1}
    # 뺀 종목의 배당 1,000 ÷ 0.846 = 1,182.03원 → 합 236,182.03원 → 1,000원 단위로 236,000원
    assert got["ab"]["won"] == 236000 and got["ab"]["n"] == 3 and abs(got["ab"]["exact"] - (235000 + 1000 / 0.846)) < 1e-6


def test_round_to_1000_is_half_up_and_never_negative_zero():
    got = run("""out = [X.round1000(499.99), X.round1000(500), X.round1000(1499), X.round1000(1500), X.round1000(0)];""")
    assert got == [0, 1000, 1000, 2000, 0]


# ── 손실 중인 미국 종목 ──
def test_losses_are_per_stock_across_portfolios_all_or_nothing_biggest_first():
    got = run("""
      const p1 = deck('p1', { planFx: 1300, holdings: hold('AAPL', 'TSLA', 'MSFT', 'AMD', 'GONE', 'NOPX'),
        purchases: [buy('AAPL', 2, 300, '2026-01-05', { fx: 1300 }), buy('TSLA', 1, 300, '2026-01-05', { fx: 1400 }), buy('MSFT', 1, 400, '2026-01-05', { fx: 1300 }),
                    buy('AMD', 1, 100, '2026-01-05', { fx: 1300 }), buy('GONE', 1, 100, '2026-01-05', { fx: 1300 }), buy('NOPX', 1, 100, '2026-01-05', { fx: 1300 }),
                    buy('005930', 1, 90000, '2026-01-05')] });
      const p2 = deck('p2', { holdings: hold('AAPL', 'AMD'), purchases: [buy('AAPL', 1, 320, '2026-02-02', { fx: 1350 }), buy('AMD', 1, 100, '2026-02-02')] });
      const p3 = deck('p3', { kind: 'imported', settings: { points: {} }, holdings: [{ t: 'INTC', nk: 'Intel', cls: 'us' }, { t: 'NVDA', nk: 'NVIDIA', cls: 'us' }],
        imported: [{ t: 'INTC', nk: 'Intel', ccy: 'USD', qty: 10, avg: 40 }, { t: 'NVDA', nk: 'NVIDIA', ccy: 'USD', qty: 1 }],
        history: [{ t: 'META', nk: 'Meta', out: '2026-05-01', cls: 'us', purchases: [buy('META', 1, 700, '2026-01-05', { fx: 1300 })] }] });
      out = X.heldLosses([p1, p2, p3], q({ AAPL: 250, TSLA: 200, MSFT: 420, AMD: 50, NOPX: null, INTC: 30, NVDA: 100, META: 100, '005930': 50000 }, 1400));""")
    # AAPL: p1 2주 × $250 × 1,400 = 700,000 − 780,000 (2 × 300 × 1,300) = −80,000 · p2 350,000 − 432,000 (320 × 1,350) = −82,000 → −162,000
    # TSLA: 280,000 − 420,000 = −140,000 · INTC (달러 평균 단가만, 오늘 환율): 10 × 30 × 1,400 − 10 × 40 × 1,400 = −140,000 (같으면 코드 순)
    # MSFT: 588,000 − 520,000 = +68,000 (손실 아님) · AMD: p2 의 산 기록에 환율이 없어 통째로 noFx · NVDA 평균 단가 없음 · GONE 오늘 데이터에 없음 ·
    # NOPX 가격 없음 · META 는 뺀 종목(history): 손실 카드에 들어가지 않아요 · 005930 은 한국 종목
    assert got["rows"] == [{"t": "AAPL", "gain": -162000, "usdOnly": False}, {"t": "INTC", "gain": -140000, "usdOnly": True},
                           {"t": "TSLA", "gain": -140000, "usdOnly": False}]
    assert got["noFx"] == ["AMD"] and got["noAvg"] == ["NVDA"] and got["absent"] == ["GONE"] and got["noPrice"] == ["NOPX"] and got["noToday"] == []
    assert got["held"] == 8 and got["usdOnly"] is True               # AAPL TSLA MSFT AMD GONE NOPX (p1 · p2) + INTC NVDA (p3)


def test_no_rate_today_values_nothing_and_says_why():
    got = run("""const d = deck('a', { holdings: hold('AAPL'), purchases: [buy('AAPL', 1, 300, '2026-01-05', { fx: 1300 })] });
      out = X.heldLosses([d], q({ AAPL: 200 }, null));""")
    assert got["rows"] == [] and got["noToday"] == ["AAPL"]
