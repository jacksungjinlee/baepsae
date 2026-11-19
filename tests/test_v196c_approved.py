# -*- coding: utf-8 -*-
"""v19.6c 관심 종목: the Appendix 1 lines word for word, and the condition sheet's six lines Jack approved on 2026-11-19 (Q15).

- each watch.* key holds exactly the Appendix 1 text (docs/tasks/v19.6-records-alerts-dark.md, 관심 종목 · 오늘 볼 것 · import cap),
  is recorded in docs/tasks/v18.3-approved-in-chat.md as "Jack, 2026-11-06 (v19.6 Appendix 1, …)" and is not pending
- the chip words of 주가 and PBR (watch.c.pxKr · pxUs · pbr) are Jack's "이하" of 2026-11-19 (Appendix 1 said "아래"); the
  Appendix 1 row in the spec says so too
- the six condition-sheet lines (watch.form.*) hold exactly Jack's approved text of 2026-11-19 (the hint in his wording: "넣은 값
  이하가 되면", not the earlier proposal's "넣은 값보다 낮아지면"), are recorded as "Jack, 2026-11-19 (…)" and are no longer pending
- Appendix 1 itself still says each of these lines (the spec is where they come from)
(what the screens show is checked in tests/smoke_v2.py scene_v196c)
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

APPROVED = {
    "title": "관심 종목",
    "add": "+ 추가",
    "sub": "가지고 있지 않은 종목도 지켜볼 수 있어요.",
    "c.dy": "배당수익률 {x}% 이상",
    "now": "지금 {now}",
    "blank": "정보 없음",
    "bottom": "조건에 맞으면 이 화면과 홈에서 알려 드려요.",
    "addCo": "관심 종목에 추가",
    "removeCo": "관심 종목에서 빼기",
    "cap": "관심 종목은 30개까지 넣을 수 있어요.",
    "empty": "아직 관심 종목이 없어요. 종목 화면에서 추가할 수 있어요.",
    "importCap": "관심 종목은 30개까지라서 {n}개는 넣지 못했어요.",
    "hitKind": "관심 종목 조건",
    "hit": "{condition} 조건에 맞아요. 지금 {now}이에요.",
    "hitYe": "{condition} 조건에 맞아요. 지금 {now}예요.",
}
# Jack, 2026-11-19 (Q15): "labels and error yes. Hint: …" — the hint in his words, word for word
APPROVED_Q15 = {"form.pxKr": "주가 (원)", "form.pxUs": "주가 (달러)", "form.pbr": "PBR (배)", "form.dy": "배당수익률 (%)",
                "form.hint": "주가와 PBR은 넣은 값 이하가 되면, 배당수익률은 넣은 값 이상이 되면 알려 드려요. 비워 두면 그 조건은 쓰지 않아요.",
                "form.bad": "숫자를 다시 확인해 주세요."}
# Jack, 2026-11-19: "1. Yes: "주가 {x}원 이하", "주가 ${x} 이하", "PBR {x}배 이하"" (Appendix 1 said "… 아래")
APPROVED_IHA = {"c.pxKr": "주가 {x}원 이하", "c.pxUs": "주가 ${x} 이하", "c.pbr": "PBR {x}배 이하"}
OLD_HINT = "주가와 PBR은 넣은 값보다 낮아지면"                                  # the earlier proposal's wording, not approved


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def watch_copy():
    r = subprocess.run([NODE, "--input-type=module", "-e",
                        f"import {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))}; process.stdout.write(JSON.stringify(C.watch));"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def at(d, key):
    for k in key.split("."):
        d = d[k]
    return d


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_the_lines_are_exactly_appendix_1_and_jacks_q15_answer():
    w = watch_copy()
    for key, text in APPROVED.items():
        assert at(w, key) == text, key
    for key, text in {**APPROVED_IHA, **APPROVED_Q15}.items():
        assert at(w, key) == text, key
    assert set(w["c"]) == {"pxKr", "pxUs", "pbr", "dy"} and not any("아래" in v for v in w["c"].values()), w["c"]
    assert set(w["form"]) == {k.split(".")[1] for k in APPROVED_Q15}, w["form"]


def test_each_line_is_recorded_as_approved_and_appendix_1_says_it():
    chat = CT.chat_approved()
    doc = read("docs/tasks/v18.3-approved-in-chat.md")
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    spec = read("docs/tasks/v19.6-records-alerts-dark.md").split("## Appendix 1", 1)[1]
    for key, text in APPROVED.items():
        k = "watch." + key
        assert chat.get(k) == text, k
        row = [l for l in doc.splitlines() if l.startswith(f"| `{k}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-06 (v19.6 Appendix 1"), k
        assert f"`{k}` |" not in pending, k
    # the pieces as Appendix 1 writes them (its {이에요/예요} is the two keys hit / hitYe)
    for piece in ("관심 종목 · + 추가", "가지고 있지 않은 종목도 지켜볼 수 있어요.", "주가 {x}원 이하 · 주가 ${x} 이하 · PBR {x}배 이하 · 배당수익률 {x}% 이상 · (chip) · 지금 {now} · 정보 없음 (Jack, 2026-11-19: 이하 replaces 아래",
                  "조건에 맞으면 이 화면과 홈에서 알려 드려요.", "관심 종목에 추가 · 관심 종목에서 빼기", "관심 종목은 30개까지 넣을 수 있어요.",
                  "아직 관심 종목이 없어요. 종목 화면에서 추가할 수 있어요.", "관심 종목은 30개까지라서 {n}개는 넣지 못했어요.", "/ 관심 종목 조건 |",
                  "{condition} 조건에 맞아요. 지금 {now}{이에요/예요}."):
        assert piece in spec, piece


def test_the_q15_lines_are_recorded_as_approved_and_no_longer_pending():
    chat = CT.chat_approved()
    doc = read("docs/tasks/v18.3-approved-in-chat.md")
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    for key, text in {**APPROVED_IHA, **APPROVED_Q15}.items():
        k = "watch." + key
        assert chat.get(k) == text, k
        row = [l for l in doc.splitlines() if l.startswith(f"| `{k}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-19"), k
        assert f"`{k}`" not in pending, k
    src = read("src/copy/v2.js")
    block = src.split("watch: {", 1)[1].split("\n  },", 1)[0]
    assert "Jack 승인 대기" not in block and ": null" not in block, "관심 종목에 아직 승인 대기 줄이 있어요"
    for key, text in APPROVED_Q15.items():
        name = key.split(".")[1]
        assert re.search(rf'^\s+{name}: "{re.escape(text)}",', block, re.M), key
    assert OLD_HINT not in src and OLD_HINT not in pending                  # the earlier proposal is nowhere on screen or pending
