# -*- coding: utf-8 -*-
"""v19.6a: the sixteen lines and the switches Jack approved on 2026-11-13.

- each of the sixteen keys holds exactly the approved text, is recorded in docs/tasks/v18.3-approved-in-chat.md with
  "Jack, 2026-11-13", and is gone from docs/tasks/v18.3-new-strings-pending.md
- each key is read by the screen code (no line is approved and then shown nowhere), and the "until it is approved" fallbacks
  are gone (닫기 for 취소, 판 금액 for 판 금액 (원), the composed 지우기 name)
- exact amounts read "18만 8,000원" (app.manWon) and another year's date "2025년 3월 6일" (app.ymd)
- switches: A a sold-out kept holding is read at 0 shares on its own band ("own", until Jack answers the final review's
  question) · B all or nothing per stock · C exact amounts always
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
            for name, mod in (("F", "format.js"), ("L", "lots.js"), ("R", "rules.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/appr.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = "import { F, L, R } from './appr.mjs';\nlet out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));"
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
    # A (마지막 리뷰 S1): 세 값 중 "own" — 다 팔고 남겨 둔 종목은 0주로 제 선에서 읽고(먼저 사요), 남은 종목은 예전 그대로. Jack 의 답을 기다려요
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
