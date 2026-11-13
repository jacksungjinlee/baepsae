# -*- coding: utf-8 -*-
"""v19.6a: the sixteen lines and the switches Jack approved on 2026-11-13.

- each of the sixteen keys holds exactly the approved text, is recorded in docs/tasks/v18.3-approved-in-chat.md with
  "Jack, 2026-11-13", and is gone from docs/tasks/v18.3-new-strings-pending.md
- each key is read by the screen code (no line is approved and then shown nowhere), and the "until it is approved" fallbacks
  are gone (닫기 for 취소, 판 금액 for 판 금액 (원), the composed 지우기 name)
- exact amounts read "18만 8,000원" (app.manWon) and another year's date "2025년 3월 6일" (app.ymd)
- switches: A a sold-out kept holding is read at 0 shares on its own band ("own", Jack's choice on 2026-11-13) · B all or
  nothing per stock · C exact amounts always
- Jack's two evening lines (2026-11-13): daily.soldOutKept under a sold-out kept holding, rec.rateNotYet for a US record
  dated after the published exchange-rate history
- 내 수익's receipt takes the headline (the sum of the rows as shown) as its {gain}, so the two agree to the 원
(what the screens show is checked in tests/smoke_v2.py scene_v196a and scene_v196a_outs)
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

import copytrace as CT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")

APPROVED = {
    "app.manWon": "{a}만 {b}원",
    "app.ymd": "{y}년 {m}월 {d}일",
    "deck.vsNoDiv": "배당은 빼고 비교했어요.",
    "deck.vsSold": "판 금액까지 넣어서 비교했어요. 배당은 넣지 않았어요.",
    "rec.cancel": "취소",
    "rec.sellAmount": "판 금액 (원)",
    "rec.badAmount": "날짜·금액을 다시 확인해 주세요",
    "rec.noTodayRate": "오늘 환율 정보가 아직 없어 지금은 미국 종목 기록을 저장할 수 없어요. 잠시 뒤에 다시 해 주세요.",
    "rec.delFail": "이 기록을 지우지 못했어요. 화면을 다시 열어 확인해 주세요.",
    "rec.delAriaNew": "{date} {kind} 기록 지우기",
    "rec.splitFixed": "주식 분할 정보가 바뀌어서 주식 수를 다시 계산했어요.",
    "rec.usDateHint": "미국 주식은 미국 현지 날짜로 적어 주세요.",
    "ret.noAvg": "평균 단가가 없는 종목 {n}개({names})는 빼고 계산했어요.",
    "ret.csvFail": "파일을 내려받지 못했어요. 잠시 뒤에 다시 해 주세요.",
    "ret.noPrice": "오늘 가격이 없는 종목이 있어 계산하지 못했어요.",
    "ret.receiptFix": "수익률은 세 수익을 더한 {gain}을 산 금액 전체 {cost}으로 나눈 값이에요.",
}
# where each line is read (the file that shows it)
USED = {
    "app.manWon": "format.js", "app.ymd": "format.js", "deck.vsNoDiv": "tracking.jsx", "deck.vsSold": "tracking.jsx",
    "rec.cancel": "records.jsx", "rec.sellAmount": "records.jsx", "rec.badAmount": "records.jsx", "rec.noTodayRate": "records.jsx",
    "rec.delFail": "records.jsx", "rec.delAriaNew": "records.jsx", "rec.splitFixed": "records.jsx", "rec.usDateHint": "records.jsx",
    "ret.noAvg": "returns.jsx", "ret.csvFail": "returns.jsx", "ret.noPrice": "returns.jsx", "ret.receiptFix": "returns.jsx",
}


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def copy():
    r = subprocess.run([NODE, "--input-type=module", "-e",
                        f"import {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))}; process.stdout.write(JSON.stringify(C));"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def at(c, key):
    for k in key.split("."):
        c = c[k]
    return c


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_the_sixteen_lines_are_exactly_what_jack_approved():
    assert len(APPROVED) == 16
    c = copy()
    for key, text in APPROVED.items():
        assert at(c, key) == text, key


def test_each_line_is_recorded_as_approved_on_2026_11_13_and_no_longer_pending():
    chat = CT.chat_approved()
    doc = read("docs/tasks/v18.3-approved-in-chat.md")
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    for key, text in APPROVED.items():
        assert chat.get(key) == text, key
        row = [l for l in doc.splitlines() if l.startswith(f"| `{key}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-13"), key
        assert f"`{key}` |" not in pending, key                      # no row of the pending tables names it


def test_each_line_is_read_by_its_screen_and_the_waiting_fallbacks_are_gone():
    for key, name in USED.items():
        assert re.search(r"\bC\." + re.escape(key) + r"\b", read("src/v2/" + name)), (key, name)
    assert "C.rec.noTodayRate" in read("src/v2/plan.jsx")            # 매수 계획의 샀어요도 같은 줄
    rec, ret = read("src/v2/records.jsx"), read("src/v2/returns.jsx")
    for gone in ("C.rec.cancel ||", "C.rec.sellAmount ||", "C.rec.delAriaNew ||", "C.rec.noTodayRate ||"):
        assert gone not in rec, gone
    for gone in ("C.ret.receiptFix ?", "C.ret.noPrice ?", "C.ret.csvFail &&", "C.ret.noAvg &&"):
        assert gone not in ret, gone
    # the US date line sits right under the date field and only for a dollar record
    form = rec.split("function RecordForm", 1)[1].split("function SaleResult", 1)[0]
    date_at, hint_at = form.index('type="date"'), form.index("C.rec.usDateHint")
    assert date_at < hint_at < form.index("<SaleResult") and "{usd && <p data-ui-v2=\"rec-us-date\"" in form
    # the split line reads the visit's set (app.jsx fills it only when a share count changed)
    assert "store.splitFixed.has(`${deck.id}|${t}`)" in rec
    app = read("src/v2/app.jsx")
    assert "x.held.before !== x.held.after" in app and "setSplitFixed" in app


_B = {}


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-appr-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("F", "format.js"), ("L", "lots.js"), ("R", "rules.js"), ("Rc", "records.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/appr.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = "import { F, L, R, Rc } from './appr.mjs';\nlet out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_exact_amounts_and_another_years_date_read_as_approved():
    got = run("""out = { won: [188000, -188000, 1430000, 8000, 10001, 12345678, 9999.6, 0].map((v) => F.exactWon(v)),
      unit: [F.unitWon(188000, 1), F.unitWon(188000, 10000), F.unitWon(-4000, 10000)],
      dates: [F.recDate('2025-03-06', '2026-11-13'), F.recDate('2026-03-06', '2026-11-13'), F.recDate('2025-12-31', '2026-01-01'), F.recDate('nope', '2026-11-13')] };""")
    assert got["won"] == ["18만 8,000원", "−18만 8,000원", "143만원", "8,000원", "1만 1원", "1,234만 5,678원", "1만원", "0원"]
    assert got["unit"] == ["18만 8,000원", "19만원", "−4,000원"]
    assert got["dates"] == ["2025년 3월 6일", "3월 6일", "2025년 12월 31일", None]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_the_three_switches_are_as_jack_chose():
    got = run("""out = { a: R.SOLD_OUT_BANDS, b: L.RETURNS_PARTIAL, c: L.RETURNS_EXACT, rows: L.roundRows([843217.4, 380000.4, -52000.4]) };""")
    # A (마지막 리뷰 S1): 세 값 중 "own" — 다 팔고 남겨 둔 종목은 0주로 제 선에서 읽고(먼저 사요), 남은 종목은 예전 그대로 (Jack 11-13)
    assert got["a"] == "own"
    assert got["b"] is False                                         # B: 종목 통째로 (이름 줄 ret.noAvg 와 함께)
    assert got["c"] is True                                          # C: 늘 정확한 금액
    # 머리 금액 = 화면의 세 줄(원 단위)의 합. 반올림 전 합 1,171,217.4 → 줄의 합 1,171,217
    assert got["rows"] == {"unit": 1, "rows": [843217, 380000, -52000], "total": 1171217}


def test_the_receipt_names_the_headline_amount():
    """Jack, 2026-11-13 (switch C): exact amounts always, so the receipt and the headline agree. The headline is the sum of
    the three rows as shown (each to the 원); the receipt's {gain} is that same number, never a separately rounded sum
    (rows of 0.4원 each show 0원 + 0원 + 0원 = 0원; the unrounded sum would read 1원)."""
    ret = read("src/v2/returns.jsx")
    assert "gain: exactWon(rr.unit === 1 ? total : exact)" in ret
    assert "<Amount text={plus(unitWon(total, rr.unit), total)} />" in ret   # the headline shows the same `total`


# ---------------- Jack's evening answers (2026-11-13): two more lines ----------------
EVENING = {
    "daily.soldOutKept": "다 판 종목이에요. 다시 살 계획이 없으면 계획에서 빼 주세요.",
    "rec.rateNotYet": "이 날짜의 환율이 아직 없어요. 보통 다음 날 아침에 들어오니, 그때 다시 저장해 주세요.",
}


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_the_two_evening_lines_are_approved_recorded_and_shown_only_where_they_belong():
    c = copy()
    chat = CT.chat_approved()
    doc = read("docs/tasks/v18.3-approved-in-chat.md")
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    for key, text in EVENING.items():
        assert at(c, key) == text and chat.get(key) == text, key
        row = [l for l in doc.splitlines() if l.startswith(f"| `{key}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-13"), key
        assert f"`{key}` |" not in pending, key
    # the sold-out line: inside 포트폴리오's sold-out rows only (after them come the portfolio's notes), and on the company page
    # only for a built portfolio's 0-share row; never on 홈
    pf = read("src/v2/portfolio.jsx")
    block = pf.split("(de.soldOut || []).map(", 1)[1].split("de.rebased", 1)[0]
    assert pf.count("C.daily.soldOutKept}") == 1 and "C.daily.soldOutKept}" in block
    co = read("src/v2/company.jsx")
    assert co.count("C.daily.soldOutKept}") == 1 and "{!imported && x.qty === 0 && C.daily.soldOutKept && (" in co
    for f in ("home2.jsx", "today.jsx", "home.js", "pfview.jsx"):
        assert "soldOutKept" not in read("src/v2/" + f), f
    # the rate line: the record forms and 매수 계획's 샀어요, only for the "notYet" refusal, through one mapping (records.rateRefusal)
    assert 'rateNo === "notYet" ? C.rec.rateNotYet' in read("src/v2/records.jsx") and "rateRefusal(check.rate)" in read("src/v2/records.jsx")
    assert "setNoRate(rateRefusal(rate.why));" in read("src/v2/plan.jsx")
    assert '{noRate === "notYet" && <Note tone="watch" data-ui-v2="rec-no-rate" data-why="notYet">{C.rec.rateNotYet}</Note>}' in read("src/v2/plan.jsx")


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_only_a_us_date_after_the_published_history_is_not_yet():
    """rec.rateNotYet (Jack, 2026-11-13) answers one case: a US record dated a past day after the last day of a history that
    can be read (last night's US date before the morning publish). Every other refusal keeps its line: no history, a history
    whose asOf is not its last row, a date before its first row, an unfinished last row ("past"); today on stale data
    ("today"). A Korean record never needs a rate. The three record checks pass the reason on (the form keeps what was
    typed: nothing is cleared on a refusal)."""
    got = run("""const H = { asOf: '2026-11-11', final: true, rows: [['2016-01-04', 1187.7], ['2026-11-10', 1335.0], ['2026-11-11', 1333.6]] };
      const env = (o = {}) => ({ today: '2026-11-13', fx: 1338.3, fxDate: '2026-11-13', fxHist: H, stale: false, ...o });
      const r = (d, o) => Rc.rateFor(d, env(o)).why || 'ok';
      const deck = { id: 'd', name: 'p', createdAt: '2026-09-01', planFx: 1300, holdings: [{ t: 'AAPL', nk: 'Apple', cls: 'us', target: 0.5 }, { t: '005930', nk: '삼성전자', cls: 'kr', target: 0.5 }],
        purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 3, price: 300, date: '2026-10-02', ccy: 'USD', fx: 1300 }, { id: 'p2aaaaaa', t: '005930', qty: 10, price: 200000, date: '2026-10-02', ccy: 'KRW' }] };
      const US = { t: 'AAPL', nk: 'Apple', cls: 'us', ccy: 'USD', price: 310 }, KR = { t: '005930', nk: '삼성전자', cls: 'kr', price: 210000 };
      const why = (c) => (c.ok ? 'ok' : c.why + ':' + (c.rate || ''));
      out = { after: r('2026-11-12'), onLast: r('2026-11-11'), today: r('2026-11-13'), staleToday: r('2026-11-13', { stale: true }), staleAfter: r('2026-11-12', { stale: true }),
        noHist: r('2026-11-12', { fxHist: null }), asOf: r('2026-11-12', { fxHist: { ...H, asOf: '2026-11-12' } }), first: r('2016-01-02'),
        unfinished: r('2026-11-11', { fxHist: { ...H, final: false } }),
        sale: why(Rc.checkSale(deck, 'AAPL', { qty: '1', price: '310', date: '2026-11-12' }, US, env())),
        buy: why(Rc.checkPurchase(deck, 'AAPL', { qty: '1', price: '310', date: '2026-11-12' }, US, env())),
        div: why(Rc.checkDiv(deck, 'AAPL', { amount: '1.5', date: '2026-11-12' }, US, env())),
        kr: why(Rc.checkPurchase(deck, '005930', { qty: '1', price: '210000', date: '2026-11-12' }, KR, env())),
        lines: ['notYet', 'today', 'past', 'date', undefined].map((w) => Rc.rateRefusal(w)) };""")
    assert got["after"] == "notYet" and got["staleAfter"] == "notYet"
    assert got["onLast"] == "ok" and got["today"] == "ok" and got["staleToday"] == "today"
    assert got["noHist"] == got["asOf"] == got["first"] == got["unfinished"] == "past"
    assert got["sale"] == got["buy"] == got["div"] == "rate:notYet" and got["kr"] == "ok"
    assert got["lines"] == ["notYet", "today", "past", "past", "past"]          # 그 줄을 고르는 하나의 규칙 (양식 · 매수 계획, 리뷰 S2)


def test_the_company_page_says_no_all_kept_line_for_a_0_share_holding():
    """Review N5: a 0-share kept holding whose band reads 할 일 없음 does not get "규칙 n개가 모두 지켜지고 있어요" on the company
    page (its rules are not read for it); the "다 판 종목이에요. …" line stands alone. (smoke_v2 scene_v196a_sold_out: 035720.)"""
    co = read("src/v2/company.jsx")
    assert "const k = imported || x.qty === 0 ? 0 : keptCount(" in co
