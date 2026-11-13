# -*- coding: utf-8 -*-
"""v19.7a: the five lines Jack approved on 2026-11-13 (P1–P5).

- each key holds exactly the approved text, is recorded in docs/tasks/v18.3-approved-in-chat.md with "Jack, 2026-11-13", and
  is gone from docs/tasks/v18.3-new-strings-pending.md
- 나가기 is the second button of both questions (the leave sheet in 종목 바꾸기 and the ask before another portfolio's 종목
  바꾸기 drops a waiting edit); 닫기 stays first and is the main button; the 포트폴리오 fallback is gone
- the − / + names, the 바꾼 기록 title (the log shows at the bottom of 종목 바꾸기) and the save-refused line (종목 바꾸기 and
  팔고 빼기's form) are read without an "until approved" branch
(what the screens show is checked in tests/smoke_v2.py scene_v197a)
"""
import json
import os
import shutil
import subprocess

import pytest

import copytrace as CT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")

APPROVED = {
    "edit.leaveGo": "나가기",
    "edit.down": "{name} 목표 비중 줄이기",
    "edit.up": "{name} 목표 비중 늘리기",
    "edit.log": "바꾼 기록",
    "edit.saveFail": "바꾼 내용을 저장하지 못했어요. 화면을 다시 열어 확인해 주세요.",
}


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_the_five_lines_are_exactly_what_jack_approved():
    r = subprocess.run([NODE, "--input-type=module", "-e",
                        f"import {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))}; process.stdout.write(JSON.stringify(C.edit));"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    edit = json.loads(r.stdout)
    for key, text in APPROVED.items():
        assert edit[key.split(".")[1]] == text, key
    assert not [k for k, v in edit.items() if v is None]              # 종목 바꾸기에는 기다리는 문구가 없어요


def test_each_line_is_recorded_as_approved_on_2026_11_13_and_no_longer_pending():
    chat = CT.chat_approved()
    doc = read("docs/tasks/v18.3-approved-in-chat.md")
    pending = read("docs/tasks/v18.3-new-strings-pending.md")
    for key, text in APPROVED.items():
        assert chat.get(key) == text, key
        row = [l for l in doc.splitlines() if l.startswith(f"| `{key}` |")]
        assert len(row) == 1 and row[0].split("|")[3].strip().startswith("Jack, 2026-11-13"), key
        assert f"`{key}` |" not in pending, key


def test_both_questions_keep_닫기_first_and_say_나가기_second():
    ed, app = read("src/v2/editor.jsx"), read("src/v2/app.jsx")
    leave = ed.split('data-ui-v2="edit-leave"', 1)[1].split("</BottomSheet>", 1)[0]
    drop = app.split('data-ui-v2="edit-drop"', 1)[1].split("</BottomSheet>", 1)[0]
    for name, part in (("leave", leave), ("drop", drop)):
        stay, go = part.index("{C.app.close}</Button>"), part.index("{C.edit.leaveGo}</Button>")
        assert stay < go, name                                       # 닫기(머물기)가 먼저
        assert part.count("<Button") == 2 and part.count('kind="secondary"') == 1, name
        assert part.index('kind="secondary"') > stay, name          # 나가기가 둘째(보조) 버튼
        assert "C.app.tabs.portfolio" not in part, name              # [포트폴리오] 로 대신하던 것은 없어요
    assert "C.edit.leaveGo ?" not in ed and "C.edit.leaveGo ||" not in app


def test_the_names_the_log_and_the_refusal_line_have_no_waiting_branch():
    ed, rec = read("src/v2/editor.jsx"), read("src/v2/records.jsx")
    assert "const downLabel = (name) => fill(C.edit.down, { name });" in ed and "const upLabel = (name) => fill(C.edit.up, { name });" in ed
    assert "aria-label={downLabel(name)}" in ed and "aria-label={upLabel(name)}" in ed
    assert "const logs = E.changeList(deck);" in ed and "{C.edit.log}</h3>" in ed
    # the log card sits after the save button and its notes: the bottom of 종목 바꾸기
    at = ed.index('data-ui-v2="edit-log"')
    assert ed.index("{C.edit.save}</Button>") < ed.index('data-ui-v2="edit-save-fail"') < at
    rest = ed[at:].split("<Footer />", 1)[0]                          # nothing but the log's own card before the footer
    assert rest.count("<Card") == 0 and rest.count("</Card>") == 1 and "<Button" not in rest
    line = '{fail === "refused" && <Note tone="watch" data-ui-v2="edit-save-fail">{C.edit.saveFail}</Note>}'
    assert line in ed and line in rec                                # 종목 바꾸기 · 팔고 빼기의 팔았어요 양식
    for src in (ed, rec):
        assert "C.edit.saveFail &&" not in src and "C.edit.log ?" not in src and "C.edit.down ?" not in src and "C.edit.up ?" not in src


def test_the_sold_out_line_opens_that_stocks_빼기_sheet():
    """Jack, 2026-11-13 (J4): the line "다 판 종목이에요. 다시 살 계획이 없으면 계획에서 빼 주세요." (v19.6a, daily.soldOutKept) is
    itself the link, with no new words: on 포트폴리오 (where 종목 바꾸기 opens: data loaded, records writable) and on the company
    page it opens 종목 바꾸기 of that portfolio with that stock's 빼기 sheet already open. An address reached while another
    portfolio's edits wait still asks first; 닫기 there drops the request. (smoke_v2 scene_v196a_sold_out: tapping it from both
    screens opens the sheet; 빼기 and 바꾼 내용 저장 leave no 0주 row and no line.)"""
    pf, co, app, ed = read("src/v2/portfolio.jsx"), read("src/v2/company.jsx"), read("src/v2/app.jsx"), read("src/v2/editor.jsx")
    block = pf.split("(de.soldOut || []).map(", 1)[1].split("de.rebased", 1)[0]
    assert "{onEdit && canRecord" in block and 'data-ui-v2="sold-out-remove" onClick={() => onEdit(d.id, t)}' in block
    assert 'data-ui-v2="sold-out-remove" onClick={() => onRemove(deckId, x.t)}' in co
    assert "onRemove={nav.removeFrom && store.writable && !store.locked ? nav.removeFrom : null}" in co
    assert "removeFrom: (deckId, t) => { setEditRm({ deckId, t }); router.go(\"portfolio\", \"edit/\" + deckId); }" in app
    assert "setEditRm(rmT ? { deckId: id, t: rmT } : null);" in app and "onClick={() => { setAskDrop(null); setEditRm(null); }}" in app
    assert "startRemove={editRm && editRm.deckId === editDeck.id ? editRm.t : null} onStarted={() => setEditRm(null)}" in app
    assert 'useState(() => (startRemove ? { kind: "remove", t: startRemove } : null))' in ed
