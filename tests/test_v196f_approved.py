# -*- coding: utf-8 -*-
"""v19.6f 연말에 확인할 숫자: the words on the screen are Appendix 1's, word for word, and nothing else is shown unapproved.

- every tax.* key with text holds exactly the Appendix 1 line it comes from (read from the spec's own table, split at " · "
  as the table writes several lines in one cell), and is recorded in docs/tasks/v18.3-approved-in-chat.md as
  "Jack, 2026-11-06 (v19.6 Appendix 1, 연말에 확인할 숫자 …)"; the "left out" line is the existing ret.soldLeftOut (same text)
- the planner's proposals M1–M5 and the rec.note reuse hold exactly what Jack approved on 2026-11-19, are recorded as
  "Jack, 2026-11-19" and are gone from docs/tasks/v18.3-new-strings-pending.md; the screen draws each of them where it
  belongs (M5, the 환헤지 line, under the RIA line's condition, with its official source cited in src/v2/tax.js)
- the numbers in the words match the constants: "2026년 세법 기준" is tax.js TAX_YEAR, "250만원" its DEDUCTION, "22%" its RATE
- no line says to sell (or buy) anything, and none promises an amount: the estimates say 약
- the new files use the shared colour tokens only (dark mode), and the screen has no 뱁이
(what the screen shows is checked in tests/smoke_v2.py scene_v196f, scene_v196f_window and scene_v196f_states)
"""
import json
import os
import re
import shutil
import subprocess

import pytest

import copytrace as CT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
SPEC = "docs/tasks/v19.6-records-alerts-dark.md"
# Jack, 2026-11-19: yes to M1–M4, the rec.note reuse, and M5 with its official source
APPROVED_1119 = {
    "divNoFx": "환율 기록이 없는 미국 배당 {n}건은 빼고 더했어요.",
    "lossNoFx": "환율 기록이 없는 미국 종목 {n}개({names})는 빼고 계산했어요.",
    "lossNone": "지금 손실 중인 미국 종목은 없어요.",
    "equal": "양도차익이 공제 250만원과 같아요.",
    "hedge": "환헤지 상품에 투자했다면 조건에 맞을 때 공제를 더 받을 수 있어요.",
    "gainNote": "평균 단가로 계산했어요. 수수료와 세금은 빼지 않았어요.",
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


def appendix():
    """Appendix 1's 연말에 확인할 숫자 rows, and the 내 수익 'tax link' row: { where: text }."""
    text = read(SPEC).split("## Appendix 1", 1)[1].split("\n## ", 1)[0]
    rows, part = {}, None
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        if cells[0].startswith("**"):
            part = cells[0].strip("*")
            continue
        if part == "연말에 확인할 숫자" or (part == "내 수익" and cells[0] == "tax link"):
            rows[cells[0]] = cells[1]
    return rows


def expected():
    a = appendix()
    title, date, until = a["title, date"].split(" · ")
    gain_title, deduction = a["section"].split(" · ")
    loss_title, loss_note = a["losses"].split(" · ")
    div_title, div_amount = a["dividends"].split(" · ")
    return {"link": a["tax link"], "title": title, "date": date, "until": until, "gainTitle": gain_title, "deduction": deduction,
            "below": a["below"], "above": a["above"], "loss": a["loss"], "explain": a["explain"], "allDecks": a["all portfolios"],
            "ria": a["RIA (2026 only)"], "settle": a["from Dec 15"], "lossTitle": loss_title, "lossNote": loss_note,
            "divTitle": div_title, "divAmount": div_amount, "divNote": a["dividends note"], "footer": a["footer"]}, a["left out"]


def test_appendix_1_has_the_rows_this_screen_needs():
    a = appendix()
    assert len(a) == 15, sorted(a)                                   # 14 연말 rows + the 내 수익 link row
    assert a["tax link"] == "연말에 확인할 숫자 ›"


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_every_tax_line_is_appendix_1_or_jacks_2026_11_19_yes_word_for_word():
    want, left_out = expected()
    c = copy()
    tax = c["tax"]
    for k, v in want.items():
        assert tax[k] == v, k
    for k, v in APPROVED_1119.items():
        assert tax[k] == v, k
    assert sorted(tax) == sorted([*want, *APPROVED_1119]) and not [k for k, v in tax.items() if v is None]
    assert c["ret"]["soldLeftOut"] == left_out                       # 'left out': the same line 내 수익 already shows
    assert tax["gainNote"] == c["rec"]["note"]                       # the rec.note reuse is the same words


def test_each_line_is_recorded_as_approved_with_appendix_1_and_the_proposals_are_parked():
    want, left_out = expected()
    chat = CT.chat_approved()
    doc = read("docs/tasks/v18.3-approved-in-chat.md")
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    for k, v in want.items():
        key = "tax." + k
        assert chat.get(key) == v, key
        row = [l for l in doc.splitlines() if l.startswith(f"| `{key}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-06 (v19.6 Appendix 1, 연말에 확인할 숫자"), key
        assert f"`{key}` |" not in pending, key
    assert chat.get("ret.soldLeftOut") == left_out
    for k, v in APPROVED_1119.items():
        key = "tax." + k
        assert chat.get(key) == v, key
        row = [l for l in doc.splitlines() if l.startswith(f"| `{key}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-19"), key
        assert f"`{key}` |" not in pending, key
    rd = [l for l in doc.splitlines() if l.startswith("| `ret.date` |")]
    assert len(rd) == 1 and "Jack, 2026-11-19: also under the title of 연말에 확인할 숫자's losses card" in rd[0]
    section = pending.split("## v19.6f", 1)[1].split("\n## ", 1)[0]
    assert "Nothing waits here any more." in section and "| `tax." not in section


def test_the_screen_reads_every_line_and_each_waiting_one_only_behind_a_check():
    want, _ = expected()
    jsx, ret = read("src/v2/tax.jsx"), read("src/v2/returns.jsx")
    for k in want:                                                   # TaxLink is in tax.jsx too; 내 수익 draws it
        assert re.search(r"\bC\.tax\." + k + r"\b", jsx), k
    assert "<TaxLink onClick={onTax} />" in ret and "taxOpen(store.data.decks, todayKst())" in ret
    for k in ("C.ret.soldLeftOut", "C.rec.usdOnly", "C.pfr.usdToday", "C.ret.noAvg", "C.missing.line", "C.ret.noPrice", "C.app.tabs.portfolio",
              "C.ret.date"):
        assert k in jsx, k
    # Jack's 2026-11-19 lines: each is read by the screen, without a "until approved" branch
    for k in APPROVED_1119:
        assert re.search(r"\bC\.tax\." + k + r"\b", jsx), k
        assert f"!C.tax.{k}" not in jsx and f"C.tax.{k} ||" not in jsx and f"C.tax.{k} &&" not in jsx, k
    assert ': st.kind === "equal" ? C.tax.equal' in jsx                          # M4 at exactly 250만원
    assert '{win.ria && <p data-ui-v2="tax-hedge"' in jsx                        # M5 under the RIA line's condition
    gain = jsx.split("function GainCard", 1)[1].split("function LossCard", 1)[0]
    assert gain.index('data-ui-v2="tax-all"') < gain.index('data-ui-v2="tax-hedge"') < gain.index('data-ui-v2="tax-gain-note"')
    # the link counts every dividend of the year (a US one without a rate too: the dividend card names it with M1)
    tax = read("src/v2/tax.js")
    assert "out.div = true;" in tax and "divAny" not in tax


def test_what_is_left_out_is_also_said_in_the_console_with_counts():
    jsx = read("src/v2/tax.jsx")
    assert 'console.info("[v2] tax: " + m)' in jsx
    for needle in ("US sale(s) dated ${TAX_YEAR} left out of the gain", "US dividend(s) dated ${TAX_YEAR} have no exchange rate",
                   "losses card left out: no exchange rate in today's data", "left out and named on the card: ${named.join"):
        assert needle in jsx, needle
    assert "not approved yet" not in jsx
    app = read("src/v2/app.jsx")
    assert "[v2] tax: #portfolio/tax is closed today" in app and "if (taxShown) return <Tax" in app
    # a closed address becomes #portfolio in place (review B, round 1), so a record made there never opens the screen by itself
    eff = app.split("const taxShown = inTax && taxOpen(view.data.decks, todayKst());", 1)[1].split("}, [inTax, taxShown]);", 1)[0]
    assert 'router.replaceRoute("portfolio");' in eff and "if (!inTax || taxShown) return;" in eff


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_the_numbers_in_the_words_are_the_constants(tmp_path):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    out = tmp_path / "tax.mjs"
    r = subprocess.run([exe, os.path.join(ROOT, "src", "v2", "tax.js"), "--bundle", "--format=esm", "--platform=node", f"--outfile={out}",
                        "--log-level=warning", "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([NODE, "--input-type=module", "-e",
                        "import * as X from './tax.mjs'; process.stdout.write(JSON.stringify({ y: X.TAX_YEAR, d: X.DEDUCTION, p: X.RATE_PCT, r: X.RATE }));"],
                       capture_output=True, text=True, timeout=60, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    tax = copy()["tax"]
    assert tax["footer"].endswith(f"{got['y']}년 세법 기준.")
    assert got["d"] == 2500000 and all("250만원" in tax[k] for k in ("deduction", "below", "above", "explain"))
    assert got["p"] == 22 and got["r"] == 0.22 and "22% 세금" in tax["explain"]


def test_tax_js_constants_are_written_as_the_words_say():
    src = read("src/v2/tax.js")
    assert re.search(r"^export const TAX_YEAR = 2026;", src, re.M)
    assert re.search(r"^export const DEDUCTION = 2500000;", src, re.M)
    assert re.search(r"^export const RATE_PCT = 22;", src, re.M)
    assert "checked 2026-11-15" in src.lower() or 'CHECKED = "2026-11-15"' in src
    footer = expected()[0]["footer"]
    assert footer.endswith("2026년 세법 기준.")
    # M5 (Jack, 2026-11-19: only with the official source): the law text on 국가법령정보센터 is cited where the line's year lives
    assert "https://www.law.go.kr/법령/조세특례제한법/제91조의27" in src and "§91의27 환율변동위험회피상품" in src and "[본조신설 2026. 4. 21.]" in src


def test_no_line_tells_anyone_to_sell_or_buy_and_estimates_say_about():
    want, left_out = expected()
    lines = list(want.values()) + [left_out] + list(APPROVED_1119.values())
    for v in lines:
        for bad in ("파세요", "팔아", "팔면", "매도하", "사세요", "사면", "추천", "절세", "줄이세요", "하세요"):
            assert bad not in v, (bad, v)
    assert "약 {t}" in want["above"] and want["divAmount"] == "약 {x}"
    assert "증권사나 세무사에게 확인해 주세요" in want["footer"]


NEW = ["src/v2/tax.js", "src/v2/tax.jsx"]
HEX = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_])")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(", re.I)
NAMED = re.compile(r"""["'`](?:white|black|red|blue|green|gray|grey|silver|navy|orange|yellow|purple|transparent|currentcolor)["'`]""", re.I)


@pytest.mark.parametrize("path", NEW)
def test_new_files_use_colour_tokens_only_and_no_mascot(path):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    if not os.path.exists(exe):
        pytest.skip("node_modules 가 없어요")
    r = subprocess.run([exe, path, "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    code = r.stdout
    assert not (HEX.findall(code) + FUNC.findall(code) + NAMED.findall(code)), path
    assert "baepi" not in code and "Mascot" not in code and "IMG." not in code, path
    if path.endswith(".jsx"):
        assert "LoadFail,picture:!1" in code.replace(" ", "") or "picture:!1" in code, "load failure without the 뱁이 (the screen shows money)"
