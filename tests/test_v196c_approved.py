# -*- coding: utf-8 -*-
"""v19.6c 관심 종목: the Appendix 1 lines word for word, and the condition sheet's proposals parked for Jack.

- each watch.* key holds exactly the Appendix 1 text (docs/tasks/v19.6-records-alerts-dark.md, 관심 종목 · 오늘 볼 것 · import cap),
  is recorded in docs/tasks/v18.3-approved-in-chat.md as "Jack, 2026-11-06 (v19.6 Appendix 1, …)" and is not pending
- the six condition-sheet labels (watch.form.*) are null and listed in docs/tasks/v18.3-new-strings-pending.md with their proposal
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
    "c.pxKr": "주가 {x}원 아래",
    "c.pxUs": "주가 ${x} 아래",
    "c.pbr": "PBR {x}배 아래",
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
PROPOSED = {"form.pxKr": "주가 (원)", "form.pxUs": "주가 (달러)", "form.pbr": "PBR (배)", "form.dy": "배당수익률 (%)",
            "form.hint": "주가와 PBR은 넣은 값보다 낮아지면, 배당수익률은 넣은 값 이상이 되면 알려 드려요. 비워 두면 그 조건은 쓰지 않아요.",
            "form.bad": "숫자를 다시 확인해 주세요."}


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
def test_the_lines_are_exactly_appendix_1_and_the_proposals_wait():
    w = watch_copy()
    for key, text in APPROVED.items():
        assert at(w, key) == text, key
    for key in PROPOSED:
        assert at(w, key) is None, key                                      # 승인 전에는 null (화면은 승인된 이름을 대신 써요)


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
    for piece in ("관심 종목 · + 추가", "가지고 있지 않은 종목도 지켜볼 수 있어요.", "주가 {x}원 아래 · 주가 ${x} 아래 · PBR {x}배 아래 · 배당수익률 {x}% 이상 · (chip) · 지금 {now} · 정보 없음",
                  "조건에 맞으면 이 화면과 홈에서 알려 드려요.", "관심 종목에 추가 · 관심 종목에서 빼기", "관심 종목은 30개까지 넣을 수 있어요.",
                  "아직 관심 종목이 없어요. 종목 화면에서 추가할 수 있어요.", "관심 종목은 30개까지라서 {n}개는 넣지 못했어요.", "/ 관심 종목 조건 |",
                  "{condition} 조건에 맞아요. 지금 {now}{이에요/예요}."):
        assert piece in spec, piece


def test_the_proposals_are_parked_with_their_wording():
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    for key, text in PROPOSED.items():
        row = [l for l in pending.splitlines() if l.startswith(f"| `watch.{key}` |")]
        assert len(row) == 1 and row[0].split("|")[2].strip() == text, key
    src = read("src/copy/v2.js")
    for key, text in PROPOSED.items():
        name = key.split(".")[1]
        assert re.search(rf'^\s+{name}: null,\s+// 제안 \(Jack 승인 대기, v19\.6c\): "{re.escape(text)}"$', src, re.M), key
