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
