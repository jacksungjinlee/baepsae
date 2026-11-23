# -*- coding: utf-8 -*-
"""홈 포트폴리오 카드의 '오늘 {금액} ({%})'는 그 변화 동안 가지고 있던 주식만 세요 (2026-11-24, 감사 4.2) — Node 로 돌려봐요.

감사에서 찾은 것: 토요일(11-21)에 금요일(11-20) 종가로 산 기록이 금요일 하루의 하락을 다 받아서 '오늘 −17만원 (−4.3%)'이
'산 가격보다 0원 (0.0%)' 바로 위에 나왔어요 (그런 손실은 없었어요). 이제 (src/v2/lots.js dayShare · home.js homeMoney · track.js deckDayMove):
- 가진 종목 줄(가져온 줄)과 가격 날짜(pxDate) 전 날짜의 샀어요 기록: 전날 종가부터, 하루 변화 전부 (예전과 같아요)
- 가격 날짜의 샀어요 기록: 그 기록의 가격부터 종가까지
- 가격 날짜 뒤의 샀어요 기록: 0 (양쪽 값이 같아요)
- 판 주식(가격 날짜든 그 뒤든)은 더는 가지고 있지 않아서 평가 금액에도 오늘에도 없어요. 남은 주식은 묶음(lots)마다 같은 비율로 줄어요
- 한국 종목만: 미국 종목이 있으면 '오늘'은 예전처럼 없어요. 거래 없는 종목은 기준가 변화(ntD1)로
- 기록을 가격 날짜에 맞출 수 없으면(날짜를 읽을 수 없음 · 가격 날짜의 가격 없음) '오늘'을 빼요 (예전의 null), 짐작하지 않아요.
  NaN 도, '−0원'·'+0원'도 없어요
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

PX = "2026-11-06"          # 가격 날짜 (금요일)
BEFORE, AFTER, LATER = "2026-11-05", "2026-11-07", "2026-11-08"


def run(body, **data):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-dayafter-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("Hm", "home.js"), ("T", "track.js"), ("R", "rules.js"), ("L", "lots.js"), ("F", "format.js"), ("H2", "home2.jsx")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/b.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8", "--external:react", "--external:react-dom"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    pre = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import { Hm, T, R, L, F, H2 } from './b.mjs';\nconst warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};\n"
            + pre + HELP + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


def kr(t, nk, price, d1=None, **kw):
    s = {"t": t, "nk": nk, "ne": nk, "cls": "kr", "price": price, "val20": 50.0, "vz": 50, "debt": 50, "ind": "semi", "indName": "반도체",
         "beta": 1.0, "betaSE": 0.05, "fy": 2025, **kw}
    if d1 is not None:
        s["d1"] = d1
    return s


STOCKS = [kr("000010", "가나전자", 10000.0, d1=2.0), kr("000020", "가나은행", 20000.0, d1=-1.0), kr("000030", "다라물산", 5000.0, d1=-4.3),
          kr("000050", "마바정지", 8000.0, noTrade=True, d1Why="noTrade", ntD1=0.0),          # 거래 정지: 기준가 변화 0
          kr("000060", "사아코넥스", 3000.0, noTrade=True, d1Why="noTrade", ntD1=1.5),       # 거래 없이 기준가만 움직였어요
          kr("000070", "자차이월", 7000.0, pxd="2026-11-05"),                                # 마지막 확인 종가(다른 날): d1 없음
          {"t": "AAA", "nk": "Alpha Inc.", "ne": "Alpha Inc.", "cls": "us", "ccy": "USD", "price": 100.0, "val": 50.0, "vz": 40, "ind": "software",
           "indName": "소프트웨어", "beta": 1.0, "betaSE": 0.05, "d1": 0.5, "dy": 1.0}]
BY = {s["t"]: s for s in STOCKS}

HELP = """
const ctxOf = (stocks) => ({ state: { ok: true }, byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map(), fx: 1000, pxDate: PX });
const isKr = (t) => /^[0-9]/.test(t);
const buy = (t, qty, price, date) => ({ t, date, qty, price, ccy: isKr(t) ? 'KRW' : 'USD', ...(isKr(t) ? {} : { fx: 1000 }) });
const sell = (t, qty, price, date) => ({ t, date, qty, price, ccy: isKr(t) ? 'KRW' : 'USD', ...(isKr(t) ? {} : { fx: 1000 }) });
const band = (target) => ({ id: 'band', kind: 'band', check: 'checked', target, bands: [0.75 * target, 1.25 * target, 1.4 * target] });
const nkOf = (t) => (STOCKS.find((s) => s.t === t) || {}).nk || t;
// 포트폴리오 만들기로 만든 포트폴리오: ts 의 종목을 같은 비중으로, 기록은 purchases · sales 그대로
const built = (ts, purchases, sales = [], extra = {}) => ({ id: 'dbuilt', name: 'b', createdAt: '2026-10-01', planFx: 1000,
  holdings: ts.map((t) => ({ t, nk: nkOf(t), cls: isKr(t) ? 'kr' : 'us', target: 1 / ts.length, plannedQty: 1, rules: [band(1 / ts.length)] })),
  purchases, ...(sales.length ? { sales } : {}), ...extra });
// 가진 종목 넣기로 만든 포트폴리오: rows = [[t, qty, avg?]] (가진 종목 줄) + 그 뒤의 샀어요 · 팔았어요 기록
const imp = (rows, purchases = [], sales = [], extra = {}) => {
  const ts = [...new Set([...rows.map((r) => r[0]), ...purchases.map((p) => p.t)])];
  return { id: 'dimp', name: 'p', kind: 'imported', createdAt: '2026-10-01', settings: { points: { value: 3 }, strict: 'normal' },
    holdings: ts.map((t) => ({ t, nk: nkOf(t), cls: isKr(t) ? 'kr' : 'us' })),
    imported: rows.map(([t, qty, avg]) => ({ t, nk: nkOf(t), ccy: isKr(t) ? 'KRW' : 'USD', qty, ...(avg ? { avg } : {}) })),
    purchases, ...(sales.length ? { sales } : {}), ...extra };
};
const blockOf = (deck) => { const ctx = ctxOf(STOCKS); const ev = R.evaluateAll([deck], ctx); return Hm.homeBlocks([deck], ev, ctx, STOCKS)[0] || null; };
const money = (deck) => { const b = blockOf(deck); return b ? b.money : null; };
const dayOf = (deck) => { const m = money(deck); return m && m.ok ? m.day : 'no money'; };
"""


def prev_px(t):
    s = BY[t]
    d1 = s.get("d1", s.get("ntD1"))
    return s["price"] / (1 + d1 / 100)


def held_over(t, qty):
    """가격 날짜 전부터 가진 qty 주: 하루 변화 전부 (예전 계산)."""
    return qty * (BY[t]["price"] - prev_px(t))


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def check_day(day, amount, now):
    assert day is not None and day != "no money", day
    assert close(day["amount"], amount), (day, amount)
    assert close(day["pct"], amount / (now - amount) * 100), (day, amount / (now - amount) * 100)


def test_bought_after_the_price_date_counts_nothing_the_audit_case():
    """감사의 경우: 토요일에 금요일 종가로 산 포트폴리오 → '오늘 0원 (0.0%)' 위에 '산 가격보다 0원 (0.0%)'. 만든 포트폴리오 · 가진 종목 둘 다."""
    got = run("""
      const b = built(['000030', '000020'], [buy('000030', 10, 5000, AFTER), buy('000020', 5, 20000, AFTER)]);
      const i = imp([], [buy('000030', 10, 5000, AFTER), buy('000020', 5, 20000, AFTER)]);
      const mb = money(b), mi = money(i);
      const ev = R.evaluateAll([b], ctxOf(STOCKS)).decks[0];
      out = { b: mb.day, i: mi.day, bNeg: Object.is(mb.day.amount, -0) || Object.is(mb.day.pct, -0), iNeg: Object.is(mi.day.amount, -0) || Object.is(mi.day.pct, -0),
        gb: mb.gain, gi: mi.gain, value: mb.value, old: T.deckDayChange(ev), shown: [H2.signedWon(mb.day.amount), H2.signedWon(mi.day.amount)] };""",
              STOCKS=STOCKS, PX=PX, AFTER=AFTER)
    for k in ("b", "i"):
        assert got[k] == {"pct": 0, "amount": 0}, got[k]                    # 정확히 0 (NaN 도 −0 도 아니에요)
        assert got[k + "Neg"] is False
        assert got["g" + k]["gain"] == 0 and got["g" + k]["ret"] == 0 and got["g" + k]["n"] == 2   # 산 가격보다 0원 (0.0%)
    assert got["value"] == 10 * 5000 + 5 * 20000
    assert got["old"] < -2.0                                                  # 기록 없이 계산하면(예전) 금요일 하루의 하락을 다 받았어요
    assert got["shown"] == ["0원", "0원"]


def test_bought_before_the_price_date_counts_the_whole_change():
    """가격 날짜 전의 샀어요 기록 · 가진 종목 줄: 예전과 같은 숫자 (기록 없이 계산한 값과 같아요)."""
    got = run("""
      const b = built(['000010', '000020'], [buy('000010', 10, 9000, BEFORE), buy('000020', 5, 21000, '2026-10-01')]);
      const i = imp([['000010', 10, 9000], ['000020', 5]]);
      const ev = R.evaluateAll([b], ctxOf(STOCKS)).decks[0];
      out = { b: dayOf(b), i: dayOf(i), old: T.deckDayChange(ev), withDeck: T.deckDayChange(ev, b) };""",
              STOCKS=STOCKS, PX=PX, BEFORE=BEFORE)
    amount = held_over("000010", 10) + held_over("000020", 5)
    now = 10 * 10000 + 5 * 20000
    check_day(got["b"], amount, now)
    check_day(got["i"], amount, now)
    assert close(got["old"], got["withDeck"], 1e-12)


def test_bought_on_the_price_date_counts_from_its_own_price():
    """가격 날짜의 샀어요 기록: 그 가격(9,500원)부터 종가(10,000원)까지. 하루 변화(+2%)가 아니에요."""
    got = run("""
      const b = built(['000010'], [buy('000010', 10, 9500, PX)]);
      const i = imp([['000020', 5]], [buy('000010', 10, 9500, PX)]);
      out = { b: dayOf(b), i: dayOf(i), share: L.dayShare(L.ledger(b, '000010'), 10000, 2, PX) };""", STOCKS=STOCKS, PX=PX)
    check_day(got["b"], 10 * (10000 - 9500), 10 * 10000)
    check_day(got["i"], 10 * (10000 - 9500) + held_over("000020", 5), 10 * 10000 + 5 * 20000)
    assert close(got["share"], 1 - 9500 / 10000, 1e-12)


def test_partial_sale_on_the_price_date():
    """가격 날짜에 10주(전부터) + 5주(그날 9,800원)를 가진 뒤 6주를 팔면, 묶음마다 같은 비율(6/15)로 줄어 전부터 6주 · 그날 산 3주가 남아요.
    오늘 = 6주 × 하루 변화 + 3주 × (종가 − 9,800원). 판 6주는 더는 없어서 세지 않아요: 판 가격을 바꿔도 같아요."""
    got = run("""
      const mk = (sp) => [built(['000010'], [buy('000010', 10, 9000, '2026-11-01'), buy('000010', 5, 9800, PX)], [sell('000010', 6, sp, PX)]),
        imp([['000010', 10, 9000]], [buy('000010', 5, 9800, PX)], [sell('000010', 6, sp, PX)])];
      const [b, i] = mk(10100), [b2, i2] = mk(12000);
      const only = imp([['000010', 10]], [], [sell('000010', 4, 9900, PX)]);     // 그날 산 것 없이 판 것만
      out = { b: dayOf(b), i: dayOf(i), b2: dayOf(b2), i2: dayOf(i2), only: dayOf(only), mb: money(b).value };""", STOCKS=STOCKS, PX=PX)
    amount = held_over("000010", 6) + 3 * (10000 - 9800)
    for k in ("b", "i", "b2", "i2"):
        check_day(got[k], amount, 9 * 10000)
    assert got["mb"] == 9 * 10000
    check_day(got["only"], held_over("000010", 6), 6 * 10000)               # 남은 6주는 하루 전부 (예전과 같은 숫자)


def test_sales_after_the_price_date_leave_with_their_share_of_each_lot():
    """가격 날짜 뒤에 판 주식은 더는 없어요. 전부터 10주 + 뒤에 산 5주에서 그 뒤 3주를 팔면 묶음마다 3/15 씩: 전부터 8주 · 뒤에 산 4주가 남아요.
    오늘 = 8주 × 하루 변화 (뒤에 산 4주는 0)."""
    got = run("""
      const b = built(['000010'], [buy('000010', 10, 9000, BEFORE), buy('000010', 5, 10000, AFTER)], [sell('000010', 3, 10000, LATER)]);
      const i = imp([['000010', 10]], [buy('000010', 5, 10000, AFTER)], [sell('000010', 3, 10000, LATER)]);
      const s = imp([['000010', 10]], [], [sell('000010', 4, 10000, AFTER)]);
      out = { b: dayOf(b), i: dayOf(i), s: dayOf(s) };""", STOCKS=STOCKS, PX=PX, BEFORE=BEFORE, AFTER=AFTER, LATER=LATER)
    check_day(got["b"], held_over("000010", 8), 12 * 10000)
    check_day(got["i"], held_over("000010", 8), 12 * 10000)
    check_day(got["s"], held_over("000010", 6), 6 * 10000)


def test_a_mix_of_stocks_and_of_lots_in_one_stock():
    """세 종목(전부터 · 그날 · 뒤에)과, 한 종목 안의 세 묶음(가진 종목 줄 4주 · 그날 3주 9,900원 · 뒤에 2주)."""
    got = run("""
      const p = [buy('000020', 5, 20500, PX), buy('000030', 10, 5000, AFTER)];
      const b = built(['000010', '000020', '000030'], [buy('000010', 10, 9000, BEFORE), ...p]);
      const i = imp([['000010', 10]], p);
      const one = imp([['000010', 4]], [buy('000010', 3, 9900, PX), buy('000010', 2, 10000, AFTER)]);
      out = { b: dayOf(b), i: dayOf(i), one: dayOf(one) };""", STOCKS=STOCKS, PX=PX, BEFORE=BEFORE, AFTER=AFTER)
    amount = held_over("000010", 10) + 5 * (20000 - 20500) + 0
    now = 10 * 10000 + 5 * 20000 + 10 * 5000
    check_day(got["b"], amount, now)
    check_day(got["i"], amount, now)
    check_day(got["one"], held_over("000010", 4) + 3 * (10000 - 9900), 9 * 10000)


def test_a_stock_with_no_trade_today():
    """거래 없는 종목: 전부터 가진 주식은 기준가 변화(ntD1: 정지면 0, 코넥스처럼 움직였으면 그만큼), 그날 산 기록은 그 가격부터, 뒤에 산 기록은 0."""
    got = run("""
      out = {
        halt: dayOf(imp([['000050', 10], ['000010', 1]])),
        haltOn: dayOf(built(['000050'], [buy('000050', 10, 7900, PX)])),
        moved: dayOf(imp([['000060', 10]])),
        movedAfter: dayOf(imp([['000060', 10]], [buy('000060', 4, 3000, AFTER)])),
      };""", STOCKS=STOCKS, PX=PX, AFTER=AFTER)
    check_day(got["halt"], 0 + held_over("000010", 1), 10 * 8000 + 10000)
    check_day(got["haltOn"], 10 * (8000 - 7900), 10 * 8000)
    check_day(got["moved"], held_over("000060", 10), 10 * 3000)
    check_day(got["movedAfter"], held_over("000060", 10), 14 * 3000)


def test_korean_only_a_us_holding_or_a_carried_close_still_leaves_today_out():
    """미국 종목이 있으면(뒤에 샀어도) '오늘'은 예전처럼 없어요. 마지막 확인 종가로 보이는 한국 종목(pxd)도 d1 이 없어서 없어요.
    lots.dayShare 는 원화 종목만 (달러 묶음이면 null)."""
    got = run("""
      out = {
        builtUs: dayOf(built(['000010', 'AAA'], [buy('000010', 10, 9000, BEFORE), buy('AAA', 1, 100, AFTER)])),
        impUs: dayOf(imp([['000010', 10], ['AAA', 1]])),
        carried: dayOf(imp([['000010', 10]], [buy('000070', 2, 7000, AFTER)])),
        usShare: L.dayShare(L.ledger(imp([['AAA', 1]]), 'AAA'), 100, 0.5, PX),
      };""", STOCKS=STOCKS, PX=PX, BEFORE=BEFORE, AFTER=AFTER)
    assert got == {"builtUs": None, "impUs": None, "carried": None, "usShare": None}


def test_records_that_cannot_be_placed_leave_today_out_and_say_so():
    """날짜를 읽을 수 없는 샀어요 기록 · 가격 날짜의 가격이 없는 기록(손으로 만든 파일): '오늘'을 빼고 콘솔에 한 번 말해요. NaN 없음."""
    got = run("""
      const bad = [built(['000010'], [buy('000010', 10, 9000, '2026/11/05')]), imp([['000020', 5]], [buy('000010', 10, 9000, 'someday')]),
        built(['000010'], [buy('000010', 10, null, PX)]), imp([['000020', 5]], [buy('000010', 10, 0, PX)])];
      const days = bad.map((d) => dayOf(d));
      out = { days, warns: warns.filter((w) => w.includes("today's change left out")), nan: JSON.stringify(days).includes('NaN'),
        share: [L.dayShare(null, 1, 1, PX), L.dayShare(L.ledger(imp([['000010', 1]]), '000010'), 0, 1, PX),
                L.dayShare(L.ledger(imp([['000010', 1]]), '000010'), 1, -100, PX), L.dayShare(L.ledger(imp([['000010', 1]]), '000010'), 1, 1, null)] };""",
              STOCKS=STOCKS, PX=PX)
    assert got["days"] == [None, None, None, None] and got["nan"] is False
    # 한 번씩: 포트폴리오와 종목마다 한 줄 (시험의 만든 포트폴리오 둘은 id 가 같아서 한 줄, 가진 종목 둘도 한 줄)
    assert len(got["warns"]) == 2 and any("dbuilt: " in w and "000010" in w for w in got["warns"]) and any("dimp: " in w and "000010" in w for w in got["warns"]), got["warns"]
    assert got["share"] == [None, None, None, None]


def test_never_minus_zero_or_plus_zero_on_screen():
    """그날 산 주식을 그날 일부 팔면 남은 묶음의 단가가 아주 조금(부동소수점) 달라질 수 있어요: 금액은 거의 0, 화면은 '0원'.
    작은 양수 · 음수 모두 '0원' ('+0원' · '−0원' 없음), 반 원 이상부터 부호가 붙어요."""
    got = run("""
      const d = dayOf(built(['000010'], [buy('000010', 7, 10000, PX)], [sell('000010', 3, 10300, PX)]));
      out = { d, shown: [1e-9, -1e-9, 0, -0, 0.4, -0.4, 0.6, -0.6, 15000, -15000].map((v) => H2.signedWon(v)), dShown: H2.signedWon(d.amount),
        pct: Math.round(d.pct * 10) / 10 };""", STOCKS=STOCKS, PX=PX)
    assert abs(got["d"]["amount"]) < 1e-6 and got["dShown"] == "0원" and got["pct"] == 0
    assert got["shown"] == ["0원", "0원", "0원", "0원", "0원", "0원", "+1원", "−1원", "+2만원", "−2만원"], got["shown"]
