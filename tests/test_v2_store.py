# -*- coding: utf-8 -*-
"""뱁새 2.0 기록 저장 (src/v2/store.js) — Node 에서 가짜 localStorage 로 돌려봐요.

- 기록 불러오기: 모양은 맞아도 칸 하나라도 틀리면(문자열 수량, NaN 가격, 객체 이름, 미래 날짜, 소수 주식 …) 파일 전체를 거부하고
  아무것도 저장하지 않아요
- 알 수 없는 형식으로 저장된 기록은 '저장할 수 없어요'라고 하지 않고 그대로 둬요. 처음 쓸 때 다른 키로 옮겨 보관해요
- 저장소가 막힌 기기는 writable=false
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

FAKE = """
const mem = new Map(); let blocked = false;
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => { if (blocked) throw new Error('blocked'); mem.set(k, String(v)); }, removeItem: (k) => mem.delete(k) };
"""


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, "src/v2/store.js", "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/store.mjs",
                            "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = "import * as S from './store.mjs';\n" + FAKE + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


GOOD = {"v": 1, "decks": [{"id": "d1", "name": "배당 생활비 덱", "createdAt": "2026-10-31",
                           "holdings": [{"t": "005930", "nk": "삼성전자", "target": 0.2, "plannedQty": 4, "rules": []},
                                        {"t": "AAPL", "nk": "Apple Inc.", "target": 0.1, "plannedQty": 2}],
                           "purchases": [{"t": "005930", "date": "2026-10-31", "qty": 4, "price": 225000, "ccy": "KRW"},
                                         {"t": "AAPL", "date": "2026-10-30", "qty": 2, "price": 344.63, "ccy": "USD"}]}]}


def bad(path, value):
    d = json.loads(json.dumps(GOOD))
    obj = d
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value
    return json.dumps(d, ensure_ascii=False)


def test_a_good_file_imports_and_round_trips():
    got = run(f"out = S.parseImport({json.dumps(json.dumps(GOOD, ensure_ascii=False))}, '2026-11-01');")
    assert got == GOOD


@pytest.mark.parametrize("why, text", [
    ("문자열 수량", bad(["decks", 0, "purchases", 0, "qty"], "4")),
    ("소수 주식", bad(["decks", 0, "purchases", 0, "qty"], 1.5)),
    ("0주", bad(["decks", 0, "purchases", 0, "qty"], 0)),
    ("NaN 가격 (글자)", bad(["decks", 0, "purchases", 0, "price"], "NaN")),
    ("음수 가격", bad(["decks", 0, "purchases", 1, "price"], -3)),
    ("객체 이름", bad(["decks", 0, "name"], {"x": 1})),
    ("객체 종목 이름", bad(["decks", 0, "holdings", 0, "nk"], {"x": 1})),
    ("미래 날짜", bad(["decks", 0, "purchases", 0, "date"], "2026-11-02")),
    ("없는 날짜", bad(["decks", 0, "purchases", 0, "date"], "2026-02-30")),
    ("통화", bad(["decks", 0, "purchases", 0, "ccy"], "EUR")),
    ("보유에 없는 종목", bad(["decks", 0, "purchases", 0, "t"], "999999")),
    ("목표 비중 2", bad(["decks", 0, "holdings", 0, "target"], 2)),
    ("판 버전", bad(["v"], 2)),
    ("덱 배열 아님", bad(["decks"], {"0": 1})),
])
def test_malformed_files_are_rejected_whole(why, text):
    got = run(f"out = S.parseImport({json.dumps(text)}, '2026-11-01');")
    assert got is None, why


def test_nan_literal_and_broken_json_are_rejected():
    raw = json.dumps(GOOD).replace("225000", "NaN")
    got = run(f"out = [S.parseImport({json.dumps(raw)}, '2026-11-01'), S.parseImport('{{\"v\":1,', '2026-11-01'), S.parseImport('[]', '2026-11-01')];")
    assert got == [None, None, None]


def test_duplicate_deck_ids_are_rejected():
    d = json.loads(json.dumps(GOOD))
    d["decks"].append(json.loads(json.dumps(GOOD["decks"][0])))
    got = run(f"out = S.parseImport({json.dumps(json.dumps(d))}, '2026-11-01');")
    assert got is None


def test_unknown_stored_format_is_kept_and_not_called_unavailable():
    got = run("mem.set('baepsae2.v1', '{\"v\":9,\"stuff\":[1]}');"
              "const r = S.readStore('baepsae2.v1', '2026-11-01');"
              f"const ok = S.writeStore({json.dumps(GOOD, ensure_ascii=False)}, 'baepsae2.v1');"
              "out = { locked: r.locked, writable: r.writable, empty: r.data.decks.length, ok,"
              " kept: [...mem.entries()].filter(([k]) => k.startsWith('baepsae2.v1.unreadable.')).map(([, v]) => v),"
              " now: JSON.parse(mem.get('baepsae2.v1')).decks.length };")
    assert got["locked"] and got["writable"] and got["empty"] == 0 and got["ok"]
    assert got["kept"] == ['{"v":9,"stuff":[1]}'] and got["now"] == 1


def test_blocked_storage_is_reported_and_keys_are_separate():
    got = run("blocked = true; const r = S.readStore('baepsae2.v1', '2026-11-01'); blocked = false;"
              f"S.writeStore({json.dumps(GOOD, ensure_ascii=False)}, S.PREVIEW_STORE_KEY);"
              "out = { writable: r.writable, live: S.readStore(S.STORE_KEY).data.decks.length, prev: S.readStore(S.PREVIEW_STORE_KEY).data.decks.length,"
              " keys: [S.STORE_KEY, S.PREVIEW_STORE_KEY] };")
    assert got == {"writable": False, "live": 0, "prev": 1, "keys": ["baepsae2.v1", "baepsae2.preview.v1"]}


def test_preview_and_live_exports_never_cross():
    """미리 보기에서 내보낸 기록(예시 데이터)은 실제 앱에 들어가지 않고, 실제 기록은 미리 보기에 들어가지 않아요."""
    got = run(f"const d = {json.dumps(GOOD, ensure_ascii=False)};"
              "const prev = S.exportText(d, true), live = S.exportText(d, false);"
              "out = { tag: JSON.parse(prev).preview, liveTag: JSON.parse(live).preview === undefined,"
              " liveTakesPreview: S.parseImport(prev, '2026-11-01', false), previewTakesLive: S.parseImport(live, '2026-11-01', true),"
              " liveTakesLive: !!S.parseImport(live, '2026-11-01', false), previewTakesPreview: !!S.parseImport(prev, '2026-11-01', true) };")
    assert got == {"tag": True, "liveTag": True, "liveTakesPreview": None, "previewTakesLive": None,
                   "liveTakesLive": True, "previewTakesPreview": True}


def test_write_checks_the_old_blob_with_todays_date_and_backs_it_up():
    future = json.loads(json.dumps(GOOD))
    future["decks"][0]["purchases"][0]["date"] = "2026-12-24"            # 오늘(11월 1일) 기준으로는 읽을 수 없는 기록
    got = run(f"mem.set('baepsae2.v1', {json.dumps(json.dumps(future))});"
              f"const ok = S.writeStore({json.dumps(GOOD, ensure_ascii=False)}, 'baepsae2.v1', '2026-11-01');"
              "out = { ok, backups: [...mem.keys()].filter((k) => k.startsWith('baepsae2.v1.unreadable.')).length };")
    assert got == {"ok": True, "backups": 1}


def test_old_app_portfolios_are_only_detected_never_changed():
    """예전 뱁새(baepsae.html)의 포트폴리오 목록이 있으면 안내를 보여요. 비었거나 깨졌거나 저장소가 막혀도 오류 없이 '없음'."""
    got = run("""
      const cases = {};
      cases.none = S.hasOldAppRecords();
      localStorage.setItem('baepsae_v10_slots', '[{"id":"s1","name":"포트폴리오 1"}]');
      cases.one = S.hasOldAppRecords();
      const kept = localStorage.getItem('baepsae_v10_slots');
      localStorage.setItem('baepsae_v10_slots', '[]'); cases.empty = S.hasOldAppRecords();
      localStorage.setItem('baepsae_v10_slots', '{not json'); cases.broken = S.hasOldAppRecords();
      localStorage.setItem('baepsae_v10_slots', '{"a":1}'); cases.object = S.hasOldAppRecords();
      cases.throws = S.hasOldAppRecords(() => { throw new Error('blocked'); });
      out = { cases, kept, key: S.OLD_APP_SLOTS_KEY };
    """)
    assert got["key"] == "baepsae_v10_slots"
    assert got["cases"] == {"none": False, "one": True, "empty": False, "broken": False, "object": False, "throws": False}
    assert got["kept"] == '[{"id":"s1","name":"포트폴리오 1"}]'


def test_old_app_key_matches_the_current_app():
    """2.0 이 보는 키가 지금 앱(src/detail.jsx)이 포트폴리오를 저장하는 키와 같아요."""
    with open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8") as f:
        assert 'const KEY_SLOTS = "baepsae_v10_slots";' in f.read()
    with open(os.path.join(ROOT, "src", "v2", "store.js"), encoding="utf-8") as f:
        assert 'OLD_APP_SLOTS_KEY = "baepsae_v10_slots"' in f.read()


# ── 확인 필요 답 (v18.3 Part C): 덱 기록 안의 confirms ──
CONFIRM = {"t": "005930", "rule": "divCut", "fy": 2025, "a": 1446.0, "b": 1200.0, "answer": "cut", "at": "2026-11-01"}


def with_confirms(confirms):
    d = json.loads(json.dumps(GOOD))
    d["decks"][0]["confirms"] = confirms
    return json.dumps(d, ensure_ascii=False)


@pytest.mark.parametrize("why, confirms", [
    ("배열 아님", {"0": CONFIRM}),
    ("모르는 답", [{**CONFIRM, "answer": "maybe"}]),
    ("모르는 규칙", [{**CONFIRM, "rule": "debtCeiling"}]),
    ("보고서 연도 글자", [{**CONFIRM, "fy": "2025"}]),
    ("감소가 아님", [{**CONFIRM, "b": 1446.0}]),
    ("음수 배당", [{**CONFIRM, "b": -1}]),
    ("미래 날짜", [{**CONFIRM, "at": "2026-11-02"}]),
    ("보유에 없는 종목", [{**CONFIRM, "t": "999999"}]),
])
def test_bad_confirm_answers_reject_the_whole_file(why, confirms):
    got = run(f"out = S.parseImport({json.dumps(with_confirms(confirms))}, '2026-11-01');")
    assert got is None, why


def test_confirm_answers_round_trip_and_old_records_without_them_still_read():
    got = run(f"const t = {json.dumps(with_confirms([CONFIRM]))};"
              f"const old = {json.dumps(json.dumps(GOOD, ensure_ascii=False))};"
              "const d = S.parseImport(t, '2026-11-01');"
              "const again = S.parseImport(S.exportText(d), '2026-11-01');"
              "out = { c: again && again.decks[0].confirms, old: !!S.parseImport(old, '2026-11-01') };")
    assert got == {"c": [CONFIRM], "old": True}


def test_with_confirm_replaces_the_same_item_and_keeps_others():
    got = run(f"const d = S.parseImport({json.dumps(with_confirms([CONFIRM]))}, '2026-11-01');"
              "const item = { t: '005930', rule: 'divCut', fy: 2025, a: 1446, b: 1200 };"
              "const flip = S.withConfirm(d, 'd1', item, 'notCut', '2026-11-02');"
              "const other = S.withConfirm(flip, 'd1', { ...item, fy: 2026, a: 1200, b: 1000 }, 'cut', '2026-11-02');"
              "out = { flip: flip.decks[0].confirms.map((c) => c.answer), other: other.decks[0].confirms.map((c) => c.fy + c.answer),"
              " untouched: d.decks[0].confirms.length, valid: S.validStore(other, '2026-11-02') };")
    assert got == {"flip": ["notCut"], "other": ["2025notCut", "2026cut"], "untouched": 1, "valid": True}
