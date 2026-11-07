# -*- coding: utf-8 -*-
"""뱁새 2.0 저장 기록 2판 (v19.3d: src/v2/store.js · src/v2/held.js) — Node 에서 가짜 localStorage 로 돌려봐요.

v19.3 F.1 · v19.6 A.1 (2판 한 번에): 가진 종목(imported) · 판 기록(sales) · 배당 기록(divs) · 뺀 종목의 기록(history) ·
포트폴리오 규칙 한도(limits) · 처음 안내를 본 날(guideSeen).
- 전에 저장한 모든 모양(1판: 처음 모양 · 확인 필요 답 · 계획 숫자 · 매수 환율 · 메모 · 가정)이 그대로 읽혀요
- 2판 기록이 그대로 돌아와요 (저장 → 읽기, 내보내기 → 불러오기). 2판 부분이 없으면 1판으로 적어요 (예전 창 · 되돌리기)
- 가진 종목 한 줄이 틀리면 그 포트폴리오만 따로 두고 그 줄을 콘솔에 밝혀요. 다른 포트폴리오는 그대로 읽혀요
- 가진 수량 = 가져온 수량 + 산 수량 − 판 수량 (1/10,000주 단위, 같은 날은 산 것 먼저, 날짜 없는 가져온 수량이 맨 먼저)
- 예전 앱 창이 2판 기록을 옮겨 두고 자기 기록을 쓰면, 새 앱이 되돌려 놓고 합쳐요 (아무것도 잃지 않아요)
- 처음 안내를 본 표시: 예전 따로 둔 칸(키 + .guideSeen)에서 한 번 옮겨 오고, 그 뒤로는 저장 기록 안에만 있어요
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
const mem = new Map(); let blocked = false; const warns = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => { if (blocked) throw new Error('blocked'); mem.set(k, String(v)); }, removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = (m) => warns.push(String(m));
const K = 'baepsae2.v1', T = '2026-11-07';
const stored = () => JSON.parse(mem.get(K));
"""


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-store2-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write(f"export * from {json.dumps(os.path.join(ROOT, 'src/v2/store.js'))};\n"
                    f"export * as H from {json.dumps(os.path.join(ROOT, 'src/v2/held.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/store.mjs", "--log-level=warning"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = "import * as S from './store.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# ── 예전에 저장한 모양들 (1판) ──
BUILT = {"id": "d1", "name": "배당 생활비 포트폴리오", "createdAt": "2026-10-31",
         "holdings": [{"t": "005930", "nk": "삼성전자", "target": 0.2, "plannedQty": 4, "rules": []},
                      {"t": "AAPL", "nk": "Apple Inc.", "target": 0.1, "plannedQty": 2}],
         "purchases": [{"t": "005930", "date": "2026-10-31", "qty": 4, "price": 225000, "ccy": "KRW"},
                       {"t": "AAPL", "date": "2026-10-30", "qty": 2, "price": 344.63, "ccy": "USD"}]}
OLD_SHAPES = {
    "처음 모양 (v18.3 출시)": {"v": 1, "decks": [BUILT]},
    "빈 기록": {"v": 1, "decks": []},
    "계획 숫자 · 매수 환율 (Part C · E)": {"v": 1, "decks": [{**BUILT, "planFx": 1338.0,
        "holdings": [{**BUILT["holdings"][0], "planPx": 225000.0}, {**BUILT["holdings"][1], "planPx": 344.63}],
        "purchases": [BUILT["purchases"][0], {**BUILT["purchases"][1], "fx": 1338.0}]}]},
    "확인 필요 답 (Part C)": {"v": 1, "decks": [{**BUILT, "confirms": [{"t": "005930", "rule": "divCut", "fy": 2025, "a": 1446.0, "b": 1200.0,
                                                                     "answer": "notCut", "at": "2026-11-01"}]}]},
    "메모 · 가정 (v19.1a)": {"v": 1, "decks": [BUILT], "notes": {"005930": {"text": "메모", "at": "2026-11-04"}},
                             "assume": {"AAPL": {"disc": 9.5, "term": 2, "at": "2026-11-04"}}},
    "산 것 없는 포트폴리오": {"v": 1, "decks": [{**BUILT, "id": "d0", "purchases": []}]},
}


@pytest.mark.parametrize("name", list(OLD_SHAPES))
def test_every_store_shape_saved_before_still_reads(name):
    d = OLD_SHAPES[name]
    got = run(f"mem.set(K, {json.dumps(json.dumps(d, ensure_ascii=False))}); const r = S.readStore(K, T);"
              "S.writeStore(r.data, K, T);"
              "out = { data: r.data, locked: r.locked, problems: r.problems, again: stored(), backups: [...mem.keys()].filter((k) => k.includes('.unreadable.')).length };")
    assert got["locked"] is False and got["problems"] == [], name
    assert got["data"] == d, name                                       # 그대로 읽어요 (고쳐 쓸 것이 없어요)
    assert got["again"] == d and got["again"]["v"] == 1, name             # 2판 부분이 없으면 1판 그대로 적어요 (예전 창이 읽어요)
    assert got["backups"] == 0, name


# ── 2판 모양 ──
IMPORTED = {"id": "dimp", "name": "포트폴리오", "createdAt": "2026-11-07", "pxDate": "2026-11-06", "kind": "imported",
            "settings": {"points": {"value": 4, "div": 3, "stable": 2}, "strict": "normal"},
            "holdings": [{"t": "005930", "nk": "삼성전자", "cls": "kr", "ind": "semi"}, {"t": "005380", "nk": "현대차", "cls": "kr", "ind": "auto"},
                         {"t": "AAPL", "nk": "Apple Inc.", "cls": "us", "ind": "hardware"}, {"t": "005935", "nk": "삼성전자우", "cls": "kr", "ind": "semi"},
                         {"t": "MSFT", "nk": "Microsoft", "cls": "us", "ind": "software"}],
            "purchases": [{"t": "005930", "date": "2026-11-07", "qty": 2, "price": 188700, "ccy": "KRW"}],
            "imported": [{"t": "005930", "nk": "삼성전자", "ccy": "KRW", "qty": 10, "avg": 62100},
                         {"t": "005380", "nk": "현대차", "ccy": "KRW", "amountWon": 1500000, "close": 250000, "date": "2026-11-06"},
                         {"t": "AAPL", "nk": "Apple Inc.", "ccy": "USD", "qty": 3.5, "avg": 121.8},
                         {"t": "005935", "nk": "삼성전자우", "ccy": "KRW", "qty": 20, "unscored": True},
                         {"t": "MSFT", "nk": "Microsoft", "ccy": "USD", "amountWon": 2000000, "close": 500.0, "date": "2026-11-06", "fx": 1356.3},
                         {"nk": "비상장 회사", "ccy": "KRW", "amountWon": 3000000, "date": "2026-11-07", "unscored": True}],
            "sales": [{"t": "AAPL", "qty": 0.5, "price": 270.0, "date": "2026-11-07", "ccy": "USD", "fx": 1356.3},
                      {"t": "005930", "qty": 3, "price": 190000, "date": "2026-11-07", "ccy": "KRW"}],
            "divs": [{"t": "005930", "amount": 3610, "ccy": "KRW", "date": "2026-11-07"}],
            "history": [{"t": "000660", "nk": "SK하이닉스", "out": "2026-11-07", "cls": "kr",
                         "purchases": [{"t": "000660", "date": "2026-10-01", "qty": 3, "price": 500000, "ccy": "KRW"}],
                         "sales": [{"t": "000660", "qty": 3, "price": 600000, "date": "2026-11-02", "ccy": "KRW"}],
                         "divs": [{"t": "000660", "amount": 1000, "ccy": "KRW", "date": "2026-11-05"}]}],
            "limits": {"stock": 25, "ind": 40}}
V2 = {"v": 2, "decks": [BUILT, IMPORTED], "notes": {"005930": {"text": "메모", "at": "2026-11-04"}}, "guideSeen": "2026-11-06"}


def test_a_v2_store_round_trips_through_storage_and_files():
    got = run(f"const d = {json.dumps(V2, ensure_ascii=False)};"
              "const ok = S.writeStore(d, K, T); const r = S.readStore(K, T);"
              "const text = S.exportText(r.data); const back = S.parseImport(text, T);"
              "out = { ok, raw: stored(), data: r.data, locked: r.locked, problems: r.problems, file: JSON.parse(text), back,"
              " merged: S.mergeStores(r.data, back), valid: S.validStore(d, T) };")
    assert got["ok"] and got["valid"] and not got["locked"] and got["problems"] == []
    assert got["raw"] == V2 and got["data"] == V2                        # 저장 → 읽기: 한 글자도 그대로
    want_file = {k: v for k, v in V2.items() if k != "guideSeen"}          # 처음 안내 표시는 이 기기의 것: 파일에는 없어요
    assert got["file"] == want_file and got["back"] == want_file
    assert got["merged"] == V2                                            # 불러와 합쳐도 이 기기의 표시는 그대로


def test_the_version_tag_follows_what_the_store_holds():
    got = run(f"const one = {{ v: 2, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }};"
              f"const two = {{ v: 1, decks: [{json.dumps(IMPORTED, ensure_ascii=False)}] }};"
              "S.writeStore(one, K, T); const a = stored().v; S.writeStore(two, K, T); const b = stored().v;"
              "out = { a, b, empty: S.emptyStore(), newest: S.STORE_VERSION, tag: [S.versionFor(one), S.versionFor(two)] };")
    assert got == {"a": 1, "b": 2, "empty": {"v": 1, "decks": []}, "newest": 2, "tag": [1, 2]}


def bad_deck(path, value):
    d = json.loads(json.dumps(IMPORTED))
    obj = d
    for k in path[:-1]:
        obj = obj[k]
    if value is KeyError:
        del obj[path[-1]]
    else:
        obj[path[-1]] = value
    return d


BAD_ROWS = {
    "한국 소수 주식": (["imported", 0, "qty"], 1.5),
    "미국 소수 다섯 자리": (["imported", 2, "qty"], 0.12345),
    "0주": (["imported", 0, "qty"], 0),
    "수량과 금액 둘 다": (["imported", 0, "amountWon"], 100000),
    "금액에 종가 없음": (["imported", 1, "close"], KeyError),
    "금액에 날짜 없음": (["imported", 1, "date"], KeyError),
    "미국 금액에 환율 없음": (["imported", 4, "fx"], KeyError),
    "한국 줄에 환율": (["imported", 0, "fx"], 1356.3),
    "평균 단가 0": (["imported", 0, "avg"], 0),
    "평균 단가 글자": (["imported", 0, "avg"], "62100"),
    "보유에 없는 종목": (["imported", 0, "t"], "999999"),
    "같은 종목 두 줄": (["imported", 2, "t"], "005930"),
    "미래 날짜": (["imported", 1, "date"], "2026-11-08"),
    "통화": (["imported", 0, "ccy"], "EUR"),
    "점수 매길 수 없음 표시가 거짓": (["imported", 3, "unscored"], False),
    "이름만 넣은 줄에 평균 단가": (["imported", 5, "avg"], 1000),
    "이름만 넣은 줄에 표시 없음": (["imported", 5, "unscored"], KeyError),
    "가진 것보다 많이 팜": (["sales", 0, "qty"], 4),
    "한국 소수 매도": (["sales", 1, "qty"], 1.5),
    "판 가격 0": (["sales", 1, "price"], 0),
    "배당 금액 음수": (["divs", 0, "amount"], -1),
    "원화 배당에 환율": (["divs", 0, "fx"], 1356.3),
    "뺀 종목 기록의 다른 종목": (["history", 0, "sales", 0, "t"], "005930"),
    "뺀 종목에서 더 많이 팜": (["history", 0, "sales", 0, "qty"], 4),
    "한도 0": (["limits", "stock"], 0),
    "모르는 한도": (["limits", "cash"], 10),
    "모르는 종류": (["kind"], "other"),
    "가져온 포트폴리오에 기준 없음": (["settings"], KeyError),
    "점수가 정수 아님": (["settings", "points", "value"], 2.5),
    "깐깐함이 이름 아님": (["settings", "strict"], 3),
    "가져온 줄이 만든 포트폴리오에": (["kind"], KeyError),
}


@pytest.mark.parametrize("why", list(BAD_ROWS))
def test_one_bad_part_sets_that_portfolio_aside_named_and_the_others_stay_readable(why):
    path, value = BAD_ROWS[why]
    d = {"v": 2, "decks": [BUILT, bad_deck(path, value)]}
    got = run(f"mem.set(K, {json.dumps(json.dumps(d, ensure_ascii=False))}); const r = S.readStore(K, T);"
              f"const file = S.parseImport({json.dumps(json.dumps(d, ensure_ascii=False))}, T);"
              f"const issues = S.importIssues({json.dumps(json.dumps(d, ensure_ascii=False))}, T);"
              "out = { ids: r.data.decks.map((x) => x.id), locked: r.locked, problems: r.problems, warns, file, issues };")
    assert got["ids"] == ["d1"], why                                     # 다른 포트폴리오는 그대로 읽혀요
    assert got["locked"] is True, why                                    # '이전에 저장한 기록을 읽지 못해 따로 보관해 두었어요'
    assert len(got["problems"]) == 1 and got["problems"][0].startswith('portfolio "포트폴리오" (dimp): '), (why, got["problems"])
    assert any("set aside" in w and "dimp" in w for w in got["warns"]), why    # 콘솔에 그 포트폴리오를 밝혀요
    assert got["file"] is None and got["issues"] == got["problems"], why   # 파일로 불러오면 통째로 거부하고 같은 이유를 밝혀요


def test_the_message_names_the_row_and_the_stock():
    d = {"v": 2, "decks": [BUILT, bad_deck(["imported", 0, "qty"], 1.5)]}
    got = run(f"mem.set(K, {json.dumps(json.dumps(d, ensure_ascii=False))}); out = S.readStore(K, T).problems;")
    assert got == ['portfolio "포트폴리오" (dimp): imported row 1 (005930): quantity must be whole shares for a Korean stock']


def test_the_set_aside_portfolio_is_never_lost_on_the_next_write():
    d = {"v": 2, "decks": [BUILT, bad_deck(["imported", 0, "qty"], 1.5)]}
    raw = json.dumps(d, ensure_ascii=False)
    got = run(f"mem.set(K, {json.dumps(raw)}); const r = S.readStore(K, T); const ok = S.writeStore(r.data, K, T);"
              "out = { ok, now: stored().decks.map((x) => x.id), kept: [...mem.entries()].filter(([k]) => k.includes('.unreadable.')).map(([, v]) => v) };")
    assert got["ok"] and got["now"] == ["d1"] and got["kept"] == [raw]


def test_a_newer_or_unknown_version_is_never_read_or_overwritten_unkept():
    got = run("mem.set(K, '{\"v\":3,\"decks\":[]}'); const r = S.readStore(K, T); const ok = S.writeStore(S.emptyStore(), K, T);"
              "out = { locked: r.locked, n: r.data.decks.length, ok, kept: [...mem.entries()].filter(([k]) => k.includes('.unreadable.')).map(([, v]) => v) };")
    assert got == {"locked": True, "n": 0, "ok": True, "kept": ['{"v":3,"decks":[]}']}


def test_a_top_level_part_of_a_later_version_is_kept_through_reads_writes_and_imports():
    later = {"v": 2, "decks": [IMPORTED], "watch": {"005930": {"at": "2026-11-07"}}}
    got = run(f"mem.set(K, {json.dumps(json.dumps(later, ensure_ascii=False))}); const r = S.readStore(K, T);"
              "const n = S.withNote(r.data, '005930', '메모', T); S.writeStore(n, K, T);"
              f"const m = S.mergeStores(stored(), S.parseImport({json.dumps(json.dumps({'v': 1, 'decks': [BUILT]}, ensure_ascii=False))}, T));"
              "out = { read: r.data.watch, locked: r.locked, written: stored().watch, merged: m.watch, ids: m.decks.map((x) => x.id) };")
    assert got == {"read": later["watch"], "locked": False, "written": later["watch"], "merged": later["watch"], "ids": ["dimp", "d1"]}


def test_saved_criteria_stay_readable_when_the_apps_cards_change():
    """v19.3d review: a saved portfolio never becomes unreadable because a card it has points on became 준비 중, the points
    limit or the strictness names changed. The evaluation leaves out what it does not know (pf.js activeOf · fitTop)."""
    d = json.loads(json.dumps(IMPORTED))
    d["settings"] = {"points": {"value": 6, "divGrowth": 2, "someday": 1}, "strict": "loose-ish"}
    got = run(f"out = [S.deckProblem({json.dumps(d, ensure_ascii=False)}, T), S.validStore({{ v: 2, decks: [{json.dumps(d, ensure_ascii=False)}] }}, T)];")
    assert got == [None, True]


def test_a_version_2_part_in_a_version_1_store_is_not_read():
    got = run(f"mem.set(K, {json.dumps(json.dumps({'v': 1, 'decks': [BUILT, IMPORTED]}, ensure_ascii=False))}); out = S.readStore(K, T);")
    assert [x["id"] for x in got["data"]["decks"]] == ["d1"] and "version-2 part" in got["problems"][0]


def test_a_store_that_would_not_read_back_is_never_written():
    got = run(f"const before = {json.dumps(json.dumps(V2, ensure_ascii=False))}; mem.set(K, before);"
              f"const bad = {json.dumps({'v': 2, 'decks': [bad_deck(['imported', 0, 'qty'], 1.5)]}, ensure_ascii=False)};"
              "const ok = S.writeStore(bad, K, T); out = { ok, same: mem.get(K) === before, warned: warns.some((w) => w.includes('not saved')) };")
    assert got == {"ok": False, "same": True, "warned": True}


# ── 가진 수량 (held.js) ──
def test_held_quantity_is_imported_plus_bought_minus_sold_in_whole_units():
    got = run(f"const d = {json.dumps(IMPORTED, ensure_ascii=False)};"
              "const q = S.H.heldQty(d); const u = S.H.heldUnits(d);"
              "const tiny = { imported: [{ t: 'X', qty: 0.1 }, { t: 'X', qty: 0.2 }], purchases: [], sales: [{ t: 'X', qty: 0.3, date: '2026-11-01' }] };"
              "const order = { imported: [], purchases: [{ t: 'A', qty: 1, date: '2026-11-02' }], sales: [{ t: 'A', qty: 1, date: '2026-11-02' }] };"
              "const dated = { imported: [{ t: 'B', amountWon: 100000, close: 1000, ccy: 'KRW', date: '2026-11-05' }], purchases: [], sales: [{ t: 'B', qty: 1, date: '2026-11-04' }] };"
              "const undated = { imported: [{ t: 'C', qty: 5 }], purchases: [], sales: [{ t: 'C', qty: 5, date: '2020-01-01' }] };"
              "out = { q: Object.fromEntries(q), u005930: u.get('005930'), at: Object.fromEntries(S.H.heldQty(d, '2026-11-05')),"
              " tiny: [S.H.belowZero(tiny), Object.fromEntries(S.H.heldUnits(tiny))], order: S.H.belowZero(order), dated: S.H.belowZero(dated),"
              " undated: S.H.belowZero(undated), amountUnits: S.H.importedUnits(d.imported[1]), usd: S.H.importedUnits(d.imported[4]),"
              " none: S.H.importedUnits(d.imported[5]), byAmount: d.imported.map(S.H.byAmount) };")
    q = got["q"]
    assert q["005930"] == 9 and got["u005930"] == 90000                # 가져온 10 + 산 2 − 판 3
    assert q["005380"] == 6 and q["AAPL"] == 3 and q["005935"] == 20    # 금액 150만원 ÷ 종가 25만원 = 6주 · 3.5 − 0.5
    assert abs(q["MSFT"] - round(2000000 / (500 * 1356.3), 4)) < 1e-9   # 미국 금액: 그날 종가 × 그날 환율, 1/10,000주로
    assert "000660" not in q                                           # 뺀 종목(history)은 가진 수량에 없어요
    assert got["at"] == {"005930": 10, "AAPL": 3.5, "005935": 20}      # 11월 5일: 금액으로 넣은 현대차 · MSFT(6일) 전, 산 것 · 판 것 전
    assert got["tiny"] == [None, {"X": 0}]                              # 0.1 + 0.2 를 0.3 다 팔아도 거부하지 않아요 (단위 비교)
    assert got["order"] is None                                         # 같은 날은 산 것 먼저
    assert got["dated"] == {"t": "B", "date": "2026-11-04"}             # 날짜 있는 가져온 수량은 그날부터
    assert got["undated"] is None                                       # 날짜 없는 가져온 수량은 모든 기록보다 먼저
    assert got["amountUnits"] == 60000 and got["none"] is None
    assert got["byAmount"] == [False, True, False, False, True, True]


def test_a_korean_amount_holding_may_be_sold_in_part_shares_all_at_once():
    d = json.loads(json.dumps(IMPORTED))
    d["sales"] = [{"t": "005380", "qty": 6, "price": 260000, "date": "2026-11-07", "ccy": "KRW"}]
    frac = json.loads(json.dumps(d))
    frac["imported"][1]["amountWon"] = 1010000                         # 101만원 ÷ 25만원 = 4.04주 (금액으로 넣은 한국 종목)
    frac["sales"] = [{"t": "005380", "qty": 4.04, "price": 250000, "date": "2026-11-07", "ccy": "KRW"}]   # 한 번에 모두
    got = run(f"out = [S.deckProblem({json.dumps(d, ensure_ascii=False)}, T), S.deckProblem({json.dumps(frac, ensure_ascii=False)}, T),"
              f" S.H.importedUnits({json.dumps(frac['imported'][1], ensure_ascii=False)})];")
    assert got[0] is None and got[1] is None and got[2] == 40400


# ── 포트폴리오에서 빼기 (v19.6 A.3) ──
def test_taking_a_stock_out_keeps_its_sales_and_dividends_in_history():
    got = run(f"const d = {{ v: 2, decks: [{json.dumps(IMPORTED, ensure_ascii=False)}] }};"
              "const a = S.withoutHolding(d, 'dimp', '005930', T); const b = S.withoutHolding(d, 'dimp', '005380', T);"
              "out = { a: a.decks[0], b: b.decks[0], va: S.validStore(a, T), vb: S.validStore(b, T) };")
    a, b = got["a"], got["b"]
    assert got["va"] and got["vb"]
    h = a["history"][-1]
    assert h["t"] == "005930" and h["out"] == "2026-11-07" and h["imported"]["qty"] == 10 and len(h["purchases"]) == 1
    assert [s["t"] for s in h["sales"]] == ["005930"] and [x["t"] for x in h["divs"]] == ["005930"]
    assert not any(r.get("t") == "005930" for r in a["imported"] + a["purchases"] + a["sales"] + a["divs"])
    assert len(b["history"]) == 1 and not any(r.get("t") == "005380" for r in b["imported"])   # 판 것 · 배당 없으면 예전처럼 지워요


# ── 예전 앱 창과 만났을 때 (v19.6 A.1 [Q5]) ──
def test_records_an_older_tab_moved_aside_are_put_back_and_merged_once():
    old_tab = {"v": 1, "decks": [{**BUILT, "confirms": [{"t": "005930", "rule": "divCut", "fy": 2025, "a": 1446.0, "b": 1200.0,
                                                          "answer": "cut", "at": "2026-11-07"}]},
                                 {**BUILT, "id": "dnew", "name": "예전 창에서 만든 포트폴리오"}],
               "notes": {"000660": {"text": "예전 창 메모", "at": "2026-11-07"}}}
    got = run(f"mem.set(K + '.unreadable.1700000000000', {json.dumps(json.dumps(V2, ensure_ascii=False))});"
              f"mem.set(K, {json.dumps(json.dumps(old_tab, ensure_ascii=False))});"
              "const r = S.readStore(K, T); const again = S.readStore(K, T);"
              "out = { restored: r.restored, again: again.restored, ids: r.data.decks.map((x) => x.id), v: stored().v, data: r.data,"
              " keys: [...mem.keys()].sort(), notes: Object.keys(r.data.notes).sort(), guide: r.data.guideSeen };")
    assert got["restored"] is True and got["again"] is False             # 한 번만 ('다른 창에서 저장한 내용과 기록을 합쳤어요')
    assert got["ids"] == ["d1", "dnew", "dimp"] and got["v"] == 2       # 지금 기록이 앞, 가진 종목 포트폴리오도 · 예전 창의 새 포트폴리오도
    d1 = next(x for x in got["data"]["decks"] if x["id"] == "d1")
    assert d1["confirms"][0]["answer"] == "cut"                          # 예전 창이 남긴 답도
    assert got["notes"] == ["000660", "005930"] and got["guide"] == "2026-11-06"
    assert "baepsae2.v1.restored.1700000000000" in got["keys"] and not any(".unreadable." in k for k in got["keys"])   # 옮겨 둔 것은 지우지 않고 이름만


def test_a_backup_that_is_not_a_version_2_store_is_left_alone():
    got = run("mem.set(K + '.unreadable.1', '{\"v\":9}'); mem.set(K + '.unreadable.2', " + json.dumps(json.dumps(OLD_SHAPES["처음 모양 (v18.3 출시)"])) + ");"
              f"mem.set(K, {json.dumps(json.dumps({'v': 1, 'decks': []}))});"
              "const r = S.readStore(K, T); out = { restored: r.restored, keys: [...mem.keys()].sort() };")
    assert got == {"restored": False, "keys": ["baepsae2.v1", "baepsae2.v1.mine", "baepsae2.v1.unreadable.1", "baepsae2.v1.unreadable.2"]}


# ── 처음 안내를 본 표시 (v19.3 Part E: 저장 기록 안에) ──
def test_the_guide_flag_moves_into_the_store_and_round_trips():
    got = run("mem.set(K + '.guideSeen', '1');"
              "const first = S.readStore(K, T);"
              "const ok = S.writeStore(first.data, K, T); const keys = [...mem.keys()].sort();"
              "const again = S.readStore(K, '2026-11-09');"
              "const fresh = S.withGuideSeen(S.emptyStore(), '2026-11-08');"
              "out = { first: first.data, ok, raw: stored(), again: again.data.guideSeen, seen: [S.guideSeenIn(first.data), S.guideSeenIn(S.emptyStore())],"
              " fresh, same: S.withGuideSeen(fresh, '2026-11-09') === fresh, keys, exported: JSON.parse(S.exportText(fresh)),"
              " bad: S.readStore.length, future: S.checkStore({ v: 1, decks: [], guideSeen: '2026-11-08' }, T).problems };")
    assert got["first"] == {"v": 1, "decks": [], "guideSeen": "2026-11-07"} and got["seen"] == [True, False]
    assert got["ok"] and got["raw"] == {"v": 1, "decks": [], "guideSeen": "2026-11-07"} and got["again"] == "2026-11-07"
    assert got["fresh"] == {"v": 1, "decks": [], "guideSeen": "2026-11-08"} and got["same"] is True
    assert got["exported"] == {"v": 1, "decks": []}                      # 이 기기의 표시라 기록 파일에는 없어요
    assert got["future"] == ["guideSeen: not a date up to today"]


def test_the_old_guide_key_is_never_written_again():
    src = open(os.path.join(ROOT, "src", "v2", "store.js"), encoding="utf-8").read()
    guide = open(os.path.join(ROOT, "src", "v2", "guide.jsx"), encoding="utf-8").read()
    app = open(os.path.join(ROOT, "src", "v2", "app.jsx"), encoding="utf-8").read()
    assert "setItem(key + OLD_GUIDE_SUFFIX" not in src and "localStorage" not in guide.split("// No Korean here")[1]
    assert "markGuideSeen" not in app and "withGuideSeen" in app

# ── v19.3d review: tabs meeting in both directions, newer records never lost, backups kept to the newest few ──
def with_sale(deck, sale):
    d = json.loads(json.dumps(deck))
    d["sales"] = d.get("sales", []) + [sale]
    return d


SALE_B = {"t": "005930", "qty": 1, "price": 191000, "date": "2026-11-07", "ccy": "KRW"}


def test_a_newer_v2_store_leads_and_an_older_moved_copy_never_drops_its_records():
    """An earlier-app tab moved a v2 store aside, then this version wrote again (a new sale): the older copy is merged in as
    well (review round 3, item 1). The current store leads, its new sale stays and is not doubled, and what only the older
    copy held (the note, the guide flag) comes back; the copy leaves for .restored. once merged."""
    newer = {"v": 2, "decks": [BUILT, with_sale(IMPORTED, SALE_B)]}
    got = run(f"mem.set(K + '.unreadable.1700000000000', {json.dumps(json.dumps(V2, ensure_ascii=False))});"
              f"mem.set(K, {json.dumps(json.dumps(newer, ensure_ascii=False))});"
              "const r = S.readStore(K, T); out = { restored: r.restored, sales: r.data.decks[1].sales, notes: Object.keys(r.data.notes || {}),"
              " guide: r.data.guideSeen, keys: [...mem.keys()].sort(), stored: stored() };")
    assert got["restored"] is True and got["sales"] == with_sale(IMPORTED, SALE_B)["sales"]   # 새 판 기록 그대로, 두 번 세지 않아요
    assert got["notes"] == ["005930"] and got["guide"] == "2026-11-06"
    assert got["keys"] == ["baepsae2.v1", "baepsae2.v1.mine", "baepsae2.v1.restored.1700000000000"] and got["stored"]["decks"][1]["sales"] == got["sales"]


def test_an_old_tab_and_a_new_tab_taking_turns_lose_nothing():
    """Review round 3, item 1 (the blocker): old tab M and new tab A take turns. A imports P1; M saves (A's store moves to
    .unreadable.); A imports P2 and sells (M's text moves to .other.); M saves again (A's store moves to .unreadable. again).
    On the next start every copy is merged, oldest first: P1, P2 and the sale are all there, and only then 합쳤어요."""
    p2 = {**IMPORTED, "id": "dimp2", "name": "두 번째"}
    m1 = {"v": 1, "decks": [{**BUILT, "confirms": [{"t": "005930", "rule": "divCut", "fy": 2025, "a": 1446.0, "b": 1200.0, "answer": "cut", "at": "2026-11-07"}]}]}
    got = run(f"""mem.set(K, JSON.stringify({{ v: 1, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}));
      const a = S.readStore(K, T);
      const p1 = {json.dumps(IMPORTED, ensure_ascii=False)}, p2 = {json.dumps(p2, ensure_ascii=False)};
      const okA1 = S.writeStore({{ ...a.data, decks: [...a.data.decks, p1] }}, K, T);                 // A: 가진 종목 넣기 (P1)
      mem.set(K + '.unreadable.1000', mem.get(K)); mem.set(K, JSON.stringify({json.dumps(m1, ensure_ascii=False)}));   // M saves
      const sold = {{ ...p1, sales: [...p1.sales, {json.dumps(SALE_B)}] }};
      const okA2 = S.writeStore({{ ...a.data, decks: [...a.data.decks, sold, p2] }}, K, T);           // A: P2 and a sale
      mem.set(K + '.unreadable.' + (Date.now() + 1000), mem.get(K)); mem.set(K, JSON.stringify({json.dumps(m1, ensure_ascii=False)}));   // M again
      const r = S.readStore(K, T); const again = S.readStore(K, T);
      const dimp = r.data.decks.find((x) => x.id === 'dimp');
      out = {{ okA1, okA2, restored: r.restored, unmerged: !!r.unmerged, again: again.restored, ids: r.data.decks.map((x) => x.id),
        sales: dimp.sales.length, held: S.H.heldQty(dimp).get('005930'), answer: r.data.decks[0].confirms[0].answer,
        left: [...mem.keys()].filter((k) => k.includes('.unreadable.') || k.includes('.other.')), restoredN: [...mem.keys()].filter((k) => k.includes('.restored.')).length }};""")
    assert got["okA1"] and got["okA2"]
    assert got["restored"] is True and got["unmerged"] is False and got["again"] is False
    assert got["ids"] == ["d1", "dimp", "dimp2"]                        # P1도 P2도 (예전에는 P2가 사라졌어요)
    assert got["sales"] == 3 and got["held"] == 8                       # 판 기록도: 10 + 2 − 3 − 1 = 8주 (예전에는 9주)
    assert got["answer"] == "cut"                                       # 예전 창의 답도
    assert got["left"] == [] and got["restoredN"] == 2                  # A의 두 번째 저장이 첫 사본을 다 담아서 그 사본은 지웠어요 (리뷰 4차 7)


def test_records_with_ids_merge_by_id_and_equal_records_without_one_stay_as_many_as_they_were():
    """Review round 3, item 5: two genuinely equal sales stay two (a multiset, each record keeps the higher count of the
    two copies); the same record with its fields in another order counts once; a record with an id is the record with
    that id, whatever else either copy holds."""
    sale = {"t": "005930", "qty": 1, "price": 191000, "date": "2026-11-07", "ccy": "KRW"}
    turned = {"ccy": "KRW", "date": "2026-11-07", "price": 191000, "qty": 1, "t": "005930"}
    a, b = with_sale(IMPORTED, sale), with_sale(with_sale(IMPORTED, sale), sale)
    c = with_sale(IMPORTED, turned)
    ida = with_sale(IMPORTED, {**sale, "id": "sale-aaaa1"})
    idb = with_sale(with_sale(IMPORTED, {**sale, "id": "sale-aaaa1"}), {**sale, "id": "sale-bbbb2"})
    got = run(f"""const one = (d) => ({{ v: 2, decks: [d] }});
      const m = (o, c) => S.mergeTabs(one(o), one(c), T);
      const n = (x) => x && x.decks[0].sales.filter((r) => r.t === '005930' && r.qty === 1).length;
      out = {{ twoIntoOne: n(m({json.dumps(b, ensure_ascii=False)}, {json.dumps(a, ensure_ascii=False)})),
        oneIntoTwo: n(m({json.dumps(a, ensure_ascii=False)}, {json.dumps(b, ensure_ascii=False)})),
        turned: n(m({json.dumps(c, ensure_ascii=False)}, {json.dumps(a, ensure_ascii=False)})),
        byId: m({json.dumps(idb, ensure_ascii=False)}, {json.dumps(ida, ensure_ascii=False)}).decks[0].sales.filter((r) => r.id).map((r) => r.id),
        idOnce: n(m({json.dumps(ida, ensure_ascii=False)}, {json.dumps(ida, ensure_ascii=False)})),
        union: S.unionRecords([{{ id: 'x-aaaa1', q: 1 }}, {{ q: 2 }}, {{ q: 2 }}], [{{ id: 'x-aaaa1', q: 9 }}, {{ q: 2 }}, {{ q: 2 }}, {{ q: 2 }}, {{ q: 3 }}]),
        none: S.unionRecords(undefined, undefined) === undefined, id: /^[A-Za-z0-9_-]{{6,40}}$/.test(S.recordId()) && S.recordId() !== S.recordId() }};""")
    assert got["twoIntoOne"] == 2 and got["oneIntoTwo"] == 2           # 같은 기록 두 개는 두 개 (예전에는 하나로 합쳐졌어요)
    assert got["turned"] == 1                                           # 순서만 다른 같은 기록은 한 번 (예전에는 두 번)
    assert got["byId"] == ["sale-aaaa1", "sale-bbbb2"] and got["idOnce"] == 1
    assert got["union"] == [{"id": "x-aaaa1", "q": 1}, {"q": 2}, {"q": 2}, {"q": 2}, {"q": 3}] and got["none"] and got["id"]


def test_record_ids_are_checked_and_an_old_store_with_them_keeps_its_version():
    sale = {**SALE_B, "id": "sale-aaaa1"}
    twice = with_sale(with_sale(IMPORTED, sale), {**SALE_B, "date": "2026-11-06", "id": "sale-aaaa1"})
    bad_id = with_sale(IMPORTED, {**SALE_B, "id": "a b"})
    built = {**BUILT, "purchases": [{**BUILT["purchases"][0], "id": "buy-aaaa1"}, BUILT["purchases"][1]]}
    got = run(f"""const v = (d) => S.checkStore({{ v: 2, decks: [d] }}, T).problems;
      const ok = S.writeStore({{ v: 1, decks: [{json.dumps(built, ensure_ascii=False)}] }}, K, T);
      out = {{ twice: v({json.dumps(twice, ensure_ascii=False)}), bad: v({json.dumps(bad_id, ensure_ascii=False)}),
        fine: v({json.dumps(with_sale(IMPORTED, sale), ensure_ascii=False)}), ok, tag: stored().v }};""")
    assert len(got["twice"]) == 1 and "the same id twice" in got["twice"][0]
    assert len(got["bad"]) == 1 and "id is not valid" in got["bad"][0] and got["fine"] == []
    assert got["ok"] and got["tag"] == 1                                # id는 2판 부분이 아니에요: 예전 창도 그대로 읽어요


def test_a_stock_taken_out_in_one_copy_and_still_held_in_the_other_is_not_counted_twice():
    """Review round 3, item 5c: one tab took 005930 out (its records moved into history), the other still holds it. Either
    way round, the merged portfolio has its records once, in history, and no longer holds it."""
    got = run(f"""const d = {{ v: 2, decks: [{json.dumps(IMPORTED, ensure_ascii=False)}] }};
      const taken = S.withoutHolding(d, 'dimp', '005930', T);
      const look = (m) => m && {{ held: m.decks[0].holdings.some((h) => h.t === '005930'),
        own: ['purchases', 'imported', 'sales', 'divs'].reduce((n, k) => n + (m.decks[0][k] || []).filter((r) => r.t === '005930').length, 0),
        hist: m.decks[0].history.filter((e) => e.t === '005930').length, entry: m.decks[0].history.find((e) => e.t === '005930'),
        others: m.decks[0].holdings.map((h) => h.t), valid: S.validStore(m, T) }};
      const later = S.withoutHolding(d, 'dimp', '005930', '2026-11-08');
      const both = S.mergeTabs(later, taken, '2026-11-08');
      out = {{ a: look(S.mergeTabs(taken, d, T)), b: look(S.mergeTabs(d, taken, T)), want: taken.decks[0].history.find((e) => e.t === '005930'),
        wantHold: taken.decks[0].holdings.map((h) => h.t), both: both.decks[0].history.filter((e) => e.t === '005930').map((e) => e.out) }};""")
    for k in ("a", "b"):
        x = got[k]
        assert x["held"] is False and x["own"] == 0 and x["hist"] == 1 and x["valid"], (k, x)   # 판 기록이 두 곳에 있지 않아요
        assert x["entry"] == got["want"] and sorted(x["others"]) == sorted(got["wantHold"]), k
    assert got["both"] == ["2026-11-07"]                                # 두 창 다 뺐으면 (다른 날) 기록 하나, 지금 창의 것


def test_a_copy_that_cannot_be_merged_stays_and_the_screens_say_so():
    """Review round 3, item 4: the stale tab sold more of a stock the other tab had taken out; merged, it would sell more
    than held, so it is not merged. It stays (never pruned, in the export) and readStore says unmerged (C.store.locked)."""
    got = run(f"""const d = {{ v: 2, decks: [{json.dumps(IMPORTED, ensure_ascii=False)}] }};
      const taken = S.withoutHolding(d, 'dimp', '005930', T);
      const stale = {{ v: 2, decks: [{{ ...d.decks[0], sales: [...d.decks[0].sales, {{ t: '005930', qty: 1, price: 190000, date: '2026-11-07', ccy: 'KRW', id: 'late-sale1' }}] }}] }};
      mem.set(K, JSON.stringify(taken)); mem.set(K + '.other.5', JSON.stringify(stale));
      const r = S.readStore(K, T);
      for (let i = 0; i < 5; i++) S.writeStore({{ ...r.data, guideSeen: '2026-11-0' + (i + 1) }}, K, T);
      const again = S.readStore(K, T);
      out = {{ merge: S.mergeTabs(stale, taken, T), unmerged: r.unmerged, restored: r.restored, again: again.unmerged, same: JSON.stringify(r.data) === JSON.stringify(taken),
        kept: mem.has(K + '.other.5'), aside: S.setAsideCopies(K).map((x) => x.key), warned: warns.some((w) => w.includes('could not be merged')) }};""")
    assert got["merge"] is None and got["unmerged"] is True and got["restored"] is False and got["again"] is True
    assert got["same"] and got["kept"] and got["aside"] == ["other.5"] and got["warned"]


def test_storage_full_while_merging_keeps_the_merged_records_and_every_copy():
    """Review round 3, item 3: once the merged store is written it is used, even when its .restored. copy cannot be written
    (the source then stays, and merging it again on the next start adds nothing). When the merged store itself cannot be
    written, nothing changes."""
    other = with_sale(IMPORTED, SALE_B)
    got = run(f"""const set0 = localStorage.setItem; const cur = {{ v: 2, decks: [{json.dumps(IMPORTED, ensure_ascii=False)}] }};
      mem.set(K, JSON.stringify(cur)); mem.set(K + '.other.5', JSON.stringify({{ v: 2, decks: [{json.dumps(other, ensure_ascii=False)}] }}));
      localStorage.setItem = (k, v) => {{ if (k.includes('.restored.')) throw new Error('full'); set0(k, v); }};
      const r = S.readStore(K, T); const first = {{ restored: r.restored, sales: r.data.decks[0].sales.length, stored: stored().decks[0].sales.length, kept: mem.has(K + '.other.5') }};
      localStorage.setItem = set0;
      const r2 = S.readStore(K, T); const second = {{ restored: r2.restored, sales: r2.data.decks[0].sales.length, kept: mem.has(K + '.other.5'),
        moved: [...mem.keys()].filter((k) => k.includes('.restored.')).length }};
      mem.clear(); mem.set(K, JSON.stringify(cur)); mem.set(K + '.other.6', JSON.stringify({{ v: 2, decks: [{json.dumps(other, ensure_ascii=False)}] }}));
      localStorage.setItem = (k, v) => {{ if (k === K) throw new Error('full'); set0(k, v); }};
      const r3 = S.readStore(K, T); localStorage.setItem = set0;
      out = {{ first, second, third: {{ restored: r3.restored, sales: r3.data.decks[0].sales.length, kept: mem.has(K + '.other.6'), stored: stored().decks[0].sales.length }} }};""")
    assert got["first"] == {"restored": True, "sales": 3, "stored": 3, "kept": True}
    assert got["second"] == {"restored": False, "sales": 3, "kept": False, "moved": 1}   # 다시 합쳐도 더해지는 것이 없어요
    assert got["third"] == {"restored": True, "sales": 3, "kept": True, "stored": 2}   # 리뷰 4차 4: 이번에는 합친 기록을 보여 주고, 사본은 다음 시작까지


def test_copies_made_in_the_same_millisecond_never_share_a_key():
    """Review round 3, item 10: an .unreadable. and an .other. copy with the same time are both merged and both kept under
    their own .restored. key; a new backup never takes a time another kind already uses."""
    other = {"v": 1, "decks": [{**BUILT, "id": "dold", "name": "예전 창"}]}
    got = run(f"""Date.now = () => 1700000000000;
      mem.set(K, JSON.stringify({{ v: 1, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}));
      mem.set(K + '.unreadable.1700000000000', {json.dumps(json.dumps(V2, ensure_ascii=False))}); mem.set(K + '.other.1700000000000', {json.dumps(json.dumps(other, ensure_ascii=False))});
      const r = S.readStore(K, T);
      const keys = [...mem.keys()].filter((k) => k !== K).sort();
      mem.set(K, JSON.stringify({{ v: 1, decks: [{{ ...{json.dumps(BUILT, ensure_ascii=False)}, id: 'dold2' }}] }})); S.writeStore(r.data, K, T);
      out = {{ ids: r.data.decks.map((x) => x.id), keys, after: [...mem.keys()].filter((k) => k.includes('.other.')) }};""")
    assert got["ids"] == ["d1", "dimp", "dold"]
    assert got["keys"] == ["baepsae2.v1.mine", "baepsae2.v1.restored.1700000000000", "baepsae2.v1.restored.1700000000001"]
    assert got["after"] == ["baepsae2.v1.other.1700000000002"]


def test_a_write_that_fails_after_its_backup_leaves_nothing_to_merge():
    """Review round 3, item 9: another tab wrote, this tab's write keeps that text as .other. and then fails: the copy is
    removed again (the stored text is still the other tab's), so the next start does not say 합쳤어요. Old .restored.
    copies are pruned before the backup is written, so a nearly full storage still takes the backup and the write."""
    got = run(f"""const set0 = localStorage.setItem;
      const V2 = {json.dumps(V2, ensure_ascii=False)};
      const OTHER = JSON.stringify({{ ...V2, decks: [...V2.decks, {{ ...{json.dumps(BUILT, ensure_ascii=False)}, id: 'dold' }}] }});   // the other tab: everything, and more
      mem.set(K, {json.dumps(json.dumps(V2, ensure_ascii=False))}); const r = S.readStore(K, T);
      mem.set(K, OTHER);
      localStorage.setItem = (k, v) => {{ if (k === K) throw new Error('full'); set0(k, v); }};
      const failed = S.writeStore(r.data, K, T); localStorage.setItem = set0;
      const left = [...mem.keys()].filter((k) => k.includes('.other.')); const next = S.readStore(K, T);
      mem.clear(); mem.set(K, {json.dumps(json.dumps(V2, ensure_ascii=False))}); const r2 = S.readStore(K, T);
      for (let i = 1; i <= 5; i++) mem.set(K + '.restored.' + i, 'r' + i);
      mem.set(K, OTHER);
      localStorage.setItem = (k, v) => {{ if (!mem.has(k) && mem.size >= 6) throw new Error('quota'); set0(k, v); }};
      const ok = S.writeStore(r2.data, K, T); localStorage.setItem = set0;
      out = {{ failed, left, restored: next.restored, data: next.data, ok, keys: [...mem.keys()].filter((k) => k !== K).sort().map((k) => k.replace(/other[.][0-9]+$/, 'other.N')) }};""")
    assert got["failed"] is False and got["left"] == [] and got["restored"] is False and [x["id"] for x in got["data"]["decks"]] == ["d1", "dimp", "dold"]
    assert got["ok"] is True and got["keys"] == ["baepsae2.v1.mine", "baepsae2.v1.other.N", "baepsae2.v1.restored.3", "baepsae2.v1.restored.4", "baepsae2.v1.restored.5"]


def test_merging_another_copy_keeps_every_record_of_both():
    """Both copies changed the same portfolio: the current copy leads and every sale, dividend, history entry, imported row
    and purchase of either one is kept (never dropped)."""
    cur = with_sale(IMPORTED, SALE_B)
    other = with_sale(IMPORTED, {"t": "005930", "qty": 2, "price": 192000, "date": "2026-11-06", "ccy": "KRW"})
    other["divs"].append({"t": "005930", "amount": 500, "ccy": "KRW", "date": "2026-11-06"})
    other["name"] = "다른 이름"
    got = run(f"const m = S.mergeTabs({{ v: 2, decks: [{json.dumps(other, ensure_ascii=False)}] }}, {{ v: 2, decks: [{json.dumps(cur, ensure_ascii=False)}] }}, T);"
              "out = m && { name: m.decks[0].name, sales: m.decks[0].sales.map((x) => x.qty), divs: m.decks[0].divs.length, hist: m.decks[0].history.length,"
              " imp: m.decks[0].imported.length, valid: S.validStore(m, T) };")
    assert got == {"name": "포트폴리오", "sales": [0.5, 3, 1, 2], "divs": 2, "hist": 1, "imp": 6, "valid": True}


def test_an_open_new_tab_keeps_what_an_old_tab_wrote_meanwhile():
    """The other direction (v19.6 A.1: test both): this tab read the records, an earlier-app tab then wrote its own (v1),
    and this tab writes again. The old tab's text is kept before the write and merged back on the next start."""
    old_tab = {"v": 1, "decks": [BUILT, {**BUILT, "id": "dold", "name": "예전 창에서 만든 포트폴리오"}]}
    got = run(f"mem.set(K, {json.dumps(json.dumps(V2, ensure_ascii=False))}); const r = S.readStore(K, T);"
              f"mem.set(K, {json.dumps(json.dumps(old_tab, ensure_ascii=False))});"
              "const ok = S.writeStore(r.data, K, T); const kept = [...mem.keys()].filter((k) => k.includes('.other.')).length;"
              "const again = S.readStore(K, T); const third = S.readStore(K, T);"
              "out = { ok, kept, restored: again.restored, ids: again.data.decks.map((x) => x.id), later: third.restored,"
              " keys: [...mem.keys()].filter((k) => k !== K).map((k) => k.replace(/[0-9]+$/, 'N')) };")
    assert got["ok"] and got["kept"] == 1 and got["restored"] is True and got["later"] is False
    assert got["ids"] == ["d1", "dimp", "dold"]                        # 이 창의 가진 종목 포트폴리오도, 예전 창의 새 포트폴리오도
    assert got["keys"] == ["baepsae2.v1.mine", "baepsae2.v1.restored.N"]


def test_the_same_tab_writing_twice_makes_no_copy():
    got = run(f"S.readStore(K, T); S.writeStore({json.dumps(V2, ensure_ascii=False)}, K, T); S.writeStore({{ v: 2, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}, K, T);"
              "out = [...mem.keys()];")
    assert got == ["baepsae2.v1", "baepsae2.v1.mine"]                     # 이 앱이 마지막으로 쓴 글자 (예전 앱 창이 덮어써도 남아요)


def test_only_merged_back_copies_are_pruned_and_the_others_travel_in_the_export():
    """Review round 3, item 2: only .restored. copies are pruned (the newest three kept) and exact duplicates of a newer copy
    of the same kind; a copy never merged back (.unreadable., .other.) is never removed, and every one travels in the
    export under setAside."""
    got = run("for (let i = 1; i <= 5; i++) { mem.set(K + '.restored.' + i, 'r' + i); mem.set(K + '.unreadable.' + (10 + i), JSON.stringify({ v: 9, n: i })); }"
              "mem.set(K + '.unreadable.9', JSON.stringify({ v: 9, n: 5 }));"
              f"S.writeStore({json.dumps(V2, ensure_ascii=False)}, K, T);"
              "const keys = [...mem.keys()].filter((k) => k !== K).sort();"
              "const file = JSON.parse(S.exportText(S.readStore(K, T).data, false, S.setAsideCopies(K)));"
              "out = { keys, aside: file.setAside, plain: Object.keys(JSON.parse(S.exportText(S.readStore(K, T).data))),"
              " back: S.parseImport(JSON.stringify(file), T) !== null, backKeys: Object.keys(S.parseImport(JSON.stringify(file), T)) };")
    assert got["keys"] == ["baepsae2.v1.restored.3", "baepsae2.v1.restored.4", "baepsae2.v1.restored.5",
                           "baepsae2.v1.unreadable.11", "baepsae2.v1.unreadable.12", "baepsae2.v1.unreadable.13",
                           "baepsae2.v1.unreadable.14", "baepsae2.v1.unreadable.15"]   # .unreadable.9 = 15와 같은 글자라서만 지워요
    assert [a["key"] for a in got["aside"]] == ["unreadable.11", "unreadable.12", "unreadable.13", "unreadable.14", "unreadable.15"]
    assert got["aside"][-1]["text"] == '{"v":9,"n":5}'
    assert "setAside" not in got["plain"]                               # 따로 둔 것이 없으면 파일은 예전 모양 그대로
    assert got["back"] and "setAside" not in got["backKeys"]            # 불러오기는 따로 둔 것을 기록으로 읽지 않아요


# ── v19.3d review round 4: the earlier app writing over this app's save, same-day edits, 빼기, odd stores ──
T_ = "2026-11-07"
OLD_APP = """
// The earlier app (origin/main store.js) as far as two tabs go: it reads a version-1 store only, and writes over the
// records without looking (a store it cannot read is moved to .unreadable. first). Its helpers are this app's called
// without a time (no ts, no deletion or removal marks), as the earlier app's are.
const oldRead = () => { try { const d = JSON.parse(mem.get(K)); if (d && d.v === 1 && Array.isArray(d.decks)) return d; } catch (e) {} return null; };
const oldWrite = (d) => { const cur = mem.get(K); if (cur != null && !oldRead()) mem.set(K + '.unreadable.' + Date.now(), cur); mem.set(K, JSON.stringify(d)); };
let inst = 0; const tab = async () => import('./store.mjs?tab=' + (++inst));     // one tab = one module (its own memory)
"""


def run_tabs(body):
    return run(OLD_APP + body)


def test_the_earlier_app_writing_over_a_new_tabs_version_1_save_loses_nothing():
    """Review round 4, item 1 (the blocker): an old tab M and a new tab N are open. N does 샀어요 (dB: no v2 part, so the
    store stays v1), then M saves a memo over it without looking. The next start merges this app's last write
    (key + '.mine', which the earlier app never touches) back in: dB is there, M's memo too, and 합쳤어요 shows."""
    got = run_tabs(f"""mem.set(K, JSON.stringify({{ v: 1, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}));
      const N = await tab(); const n = N.readStore(K, T);
      const m = oldRead();
      const dB = {{ ...{json.dumps(BUILT, ensure_ascii=False)}, id: 'dB', name: 'B' }};
      dB.purchases = dB.purchases.map((p) => ({{ ...p, id: N.recordId() }}));
      const okN = N.writeStore({{ ...n.data, decks: [...n.data.decks, dB] }}, K, T); const v = JSON.parse(mem.get(K)).v;
      oldWrite({{ ...m, notes: {{ '005930': {{ text: '예전 창 메모', at: T }} }} }});
      const F = await tab(); const f = F.readStore(K, T); const again = (await tab()).readStore(K, T);
      // once more: the merged records are this app's last write now, and the old tab writes over them again
      oldWrite({{ ...m, notes: {{ '005930': {{ text: '예전 창 메모 2', at: T }} }} }});
      const G = (await tab()).readStore(K, T);
      out = {{ okN, v, ids: f.data.decks.map((x) => x.id), note: f.data.notes['005930'].text, restored: f.restored, again: again.restored,
        later: G.data.decks.map((x) => x.id), laterNote: G.data.notes['005930'].text, laterRestored: G.restored,
        keys: [...mem.keys()].filter((k) => k !== K).map((k) => k.replace(/[0-9]+$/, 'N')) }};""")
    assert got["okN"] and got["v"] == 1
    assert got["ids"] == ["d1", "dB"] and got["note"] == "예전 창 메모" and got["restored"] is True and got["again"] is False
    assert got["later"] == ["d1", "dB"] and got["laterNote"] == "예전 창 메모 2" and got["laterRestored"] is True
    assert got["keys"] == ["baepsae2.v1.mine"]


def test_a_new_tabs_save_kept_under_mine_is_never_lost_to_a_later_write():
    """The earlier app wrote over this app's save and another new tab (which never read that save) writes before any
    restart: this app's last save is kept as a copy first (it differs from the records and from what that tab wrote last),
    so the next start still has it."""
    got = run_tabs(f"""mem.set(K, JSON.stringify({{ v: 1, decks: [] }}));
      const A = await tab(), B = await tab(); const a = A.readStore(K, T), b = B.readStore(K, T); const m = oldRead();
      A.writeStore({{ ...a.data, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}, K, T);          // A: 샀어요
      oldWrite({{ ...m, notes: {{ '000660': {{ text: '예전 창', at: T }} }} }});                         // the old tab, over it
      B.writeStore(B.withNote(b.data, '005930', 'B 메모', T, 1700000000001), K, T);                    // B never saw A's save
      const f = (await tab()).readStore(K, T);
      out = {{ ids: f.data.decks.map((x) => x.id), notes: Object.keys(f.data.notes).sort(), restored: f.restored }};""")
    assert got == {"ids": ["d1"], "notes": ["000660", "005930"], "restored": True}


def test_the_later_edit_of_a_note_an_answer_and_an_assumption_wins_on_the_same_day():
    """Review round 4, item 2: at is a date only, so two edits on one day are told apart by ts (ms). The later edit wins
    whichever copy is merged first; an edit with a time beats a same-day value without one (saved before v19.3d or by
    the earlier app) that a stale tab carries."""
    item = {"t": "005930", "rule": "divCut", "fy": 2025, "a": 1446.0, "b": 1200.0}
    got = run_tabs(f"""const item = {json.dumps(item)};
      mem.set(K, JSON.stringify({{ v: 1, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}));
      const A = await tab(), B = await tab(); let a = A.readStore(K, T).data, b = B.readStore(K, T).data;
      a = A.withNote(a, '005930', 'v1', T, 1001); A.writeStore(a, K, T);
      b = B.withNote(b, '000660', 'y', T, 1002); B.writeStore(b, K, T);
      a = A.withNote(a, '005930', 'v2', T, 1003); A.writeStore(a, K, T);
      b = B.withNote(b, '000660', 'y2', T, 1004); B.writeStore(b, K, T);
      const f = (await tab()).readStore(K, T);
      mem.clear(); mem.set(K, JSON.stringify({{ v: 1, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}));
      const C = await tab(), D = await tab(); let c = C.readStore(K, T).data, d = D.readStore(K, T).data;
      c = C.withConfirm(c, 'd1', item, 'cut', T, 2001); C.writeStore(c, K, T);            // first answer
      d = D.withConfirm(d, 'd1', item, 'notCut', T, 2002); D.writeStore(d, K, T);         // the user changes it
      c = C.withNote(c, '000660', 'x', T, 2003); C.writeStore(c, K, T);                   // the stale tab saves something else
      c = C.withAssume(c, 'AAPL', {{ disc: 9, term: 2 }}, T, 2004); C.writeStore(c, K, T);
      d = D.withAssume(d, 'AAPL', {{ disc: 11, term: 1 }}, T, 2005); D.writeStore(d, K, T);
      const g = (await tab()).readStore(K, T);
      // a same-day note without a time (before v19.3d) carried by a stale tab never undoes an edit made with a time
      mem.clear(); mem.set(K, JSON.stringify({{ v: 1, decks: [], notes: {{ '005930': {{ text: '예전', at: T }} }} }}));
      const E = await tab(), H = await tab(); let e = E.readStore(K, T).data, h = H.readStore(K, T).data;
      e = E.withNote(e, '005930', '새로 고침', T, 3001); E.writeStore(e, K, T);
      h = H.withNote(h, '000660', 'z', T, 3002); H.writeStore(h, K, T);
      const k = (await tab()).readStore(K, T);
      out = {{ note: f.data.notes['005930'].text, other: f.data.notes['000660'].text, restored: f.restored,
        answer: g.data.decks[0].confirms.map((x) => x.answer), assume: g.data.assume.AAPL.disc, gRestored: g.restored,
        stale: k.data.notes['005930'].text, ts: [S.withNote(S.emptyStore(), '005930', 'a', T, 5).notes['005930'].ts, S.withNote(S.emptyStore(), '005930', 'a', T).notes['005930'].ts ?? null],
        bad: [S.withNote(S.emptyStore(), '005930', 'a', T, 1.5), S.withConfirm({{ v: 1, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}, 'd1', item, 'cut', T, -1) && 'x'],
        badStored: S.checkStore({{ v: 1, decks: [], notes: {{ '005930': {{ text: 'a', at: T, ts: 'x' }} }} }}, T).problems }};""")
    assert got["note"] == "v2" and got["other"] == "y2" and got["restored"] is True       # 예전에는 'v1'이 돌아왔어요
    assert got["answer"] == ["notCut"] and got["assume"] == 11                              # 예전에는 'cut'으로 뒤집혔어요 (매도 조건)
    assert got["stale"] == "새로 고침"
    assert got["ts"] == [5, None] and got["bad"] == [None, None] and got["badStored"] == ["notes: not valid"]


def test_a_deleted_note_stays_deleted_when_a_stale_copy_still_has_it():
    """Review round 4, item 2: deleting a note leaves a mark (gone, with its time and a fingerprint of the deleted text),
    so a stale tab's copy of that note does not bring it back, even one saved before v19.3d without a time. A note
    written again after the deletion does come back."""
    got = run_tabs("""mem.set(K, JSON.stringify({ v: 1, decks: [], notes: { '005930': { text: '메모', at: T } } }));
      const A = await tab(), B = await tab(); let a = A.readStore(K, T).data, b = B.readStore(K, T).data;
      b = B.withNote(b, '005930', '', T, 4001); B.writeStore(b, K, T);                   // deleted
      const mark = JSON.parse(mem.get(K)).gone;
      a = A.withNote(a, '000660', 'x', T, 4002); A.writeStore(a, K, T);                  // the stale tab saves something else
      const f = (await tab()).readStore(K, T);
      // the stale tab writes the same text again after the deletion: that is a new note, and it stays
      mem.clear(); mem.set(K, JSON.stringify({ v: 1, decks: [], notes: { '005930': { text: '메모', at: T, ts: 10 } } }));
      const C = await tab(), D = await tab(); let c = C.readStore(K, T).data, d = D.readStore(K, T).data;
      d = D.withNote(d, '005930', '', T, 20); D.writeStore(d, K, T);
      c = C.withNote(c, '005930', '메모', T, 30); C.writeStore(c, K, T);
      const g = (await tab()).readStore(K, T);
      out = { mark, note: f.data.notes ? f.data.notes['005930'] || null : null, gone: Object.keys(((f.data.gone || {}).notes) || {}), restored: f.restored,
        again: g.data.notes['005930'].text, exported: Object.keys(JSON.parse(S.exportText(f.data))), hash: S.textHash('메모') };""")
    assert got["mark"] == {"notes": {"005930": {"at": "2026-11-07", "ts": 4001, "h": got["hash"]}}}
    assert got["note"] is None and got["gone"] == ["005930"] and got["restored"] is True    # 예전에는 지운 메모가 돌아왔어요
    assert got["again"] == "메모" and got["exported"] == ["v", "decks", "notes"]            # 지운 표시(gone)는 이 기기에만 (파일에는 없어요)


def test_a_stock_taken_out_without_sales_stays_out_and_the_merge_says_so():
    """Review round 4, item 3: 빼기 with no sale or dividend writes no history entry, so it keeps a removal mark (removed:
    code, date, time). A stale tab's copy that still holds the stock does not bring it back, and 합쳤어요 shows whenever a
    merged copy held something the result left out, even when the stored records did not change. A holding added again
    after the mark (its own ts later) stays."""
    deck = {**BUILT, "holdings": [{"t": "005930", "nk": "삼성전자"}, {"t": "000660", "nk": "SK하이닉스"}],
            "purchases": [{"id": "pid000001", "t": "005930", "date": T_, "qty": 1, "price": 1000, "ccy": "KRW"},
                          {"id": "pid000002", "t": "000660", "date": T_, "qty": 1, "price": 2000, "ccy": "KRW"}]}
    got = run_tabs(f"""const deck = {json.dumps(deck, ensure_ascii=False)};
      mem.set(K, JSON.stringify({{ v: 1, decks: [deck] }}));
      const A = await tab(), B = await tab(); let a = A.readStore(K, T).data, b = B.readStore(K, T).data;
      a = A.withoutHolding(a, 'd1', '000660', T, 5001); A.writeStore(a, K, T);
      const marked = JSON.parse(mem.get(K)).decks[0].removed;
      b = B.withNote(b, '005930', '메모', T, 5002); B.writeStore(b, K, T);
      const f = (await tab()).readStore(K, T);
      // nothing changes in the stored records, but the stale copy held the stock: still 합쳤어요
      const taken = A.withoutHolding({{ v: 1, decks: [deck] }}, 'd1', '000660', T, 6001);
      mem.clear(); mem.set(K, JSON.stringify(taken)); mem.set(K + '.other.5', JSON.stringify({{ v: 1, decks: [deck] }}));
      const g = (await tab()).readStore(K, T);
      // added again after the mark: the holding's own ts is later, so it stays
      const back = {{ ...taken.decks[0], holdings: [...taken.decks[0].holdings, {{ t: '000660', nk: 'SK하이닉스', ts: 7001 }}],
        purchases: [...taken.decks[0].purchases, {{ id: 'pid000003', t: '000660', date: T, qty: 2, price: 2100, ccy: 'KRW' }}] }};
      const m = S.mergeTabs(taken, {{ v: 1, decks: [back] }}, T);
      out = {{ marked, holdings: f.data.decks[0].holdings.map((h) => h.t), purchases: f.data.decks[0].purchases.map((p) => p.t), restored: f.restored,
        same: JSON.stringify(g.data) === JSON.stringify(taken), gRestored: g.restored, back: m.decks[0].holdings.map((h) => h.t),
        backBuys: m.decks[0].purchases.map((p) => p.id), v: f.data.v,
        bad: S.checkStore({{ v: 1, decks: [{{ ...deck, removed: [{{ t: '000660', at: T }}] }}] }}, T).problems.length }};""")
    assert got["marked"] == [{"t": "000660", "at": "2026-11-07", "ts": 5001}] and got["v"] == 1   # 2판 부분이 아니에요
    assert got["holdings"] == ["005930"] and got["purchases"] == ["005930"] and got["restored"] is True   # 예전에는 돌아왔어요
    assert got["same"] and got["gRestored"] is True
    assert got["back"] == ["005930", "000660"] and got["backBuys"] == ["pid000001", "pid000003"] and got["bad"] == 1


def test_a_record_with_one_id_and_two_different_copies_is_named_in_the_console():
    got = run("""const d = (price) => ({ v: 1, decks: [{ id: 'dA', name: 'A', holdings: [{ t: '005930', nk: '삼성전자' }],
        purchases: [{ id: 'same00001', t: '005930', date: T, qty: 1, price, ccy: 'KRW' }] }] });
      const m = S.mergeTabs(d(9999), d(1000), T);
      out = { prices: m.decks[0].purchases.map((p) => p.price), warns };""")
    assert got["prices"] == [1000]
    assert got["warns"] == ["[v2] portfolio dA: two copies hold record same00001 with different fields; the current copy's is kept"]


def test_an_error_while_merging_or_a_very_deep_part_never_blanks_the_page():
    """Review round 4, item 6: anything thrown while merging the copies on start is caught: the records as read, every
    copy kept, and unmerged (the kept-aside line). A later version's part nested 3,000 deep reads, merges and writes."""
    got = run("""const js = JSON.stringify;
      mem.set(K, JSON.stringify({ v: 1, decks: [] })); mem.set(K + '.other.5', JSON.stringify({ v: 1, decks: [], notes: { '005930': { text: 'BOOM', at: T } } }));
      JSON.stringify = (x, ...r) => { if (x === 'BOOM') throw new RangeError('boom'); return js(x, ...r); };
      let r, threw = null; try { r = S.readStore(K, T); } catch (e) { threw = String(e); }
      JSON.stringify = js;
      const kept = mem.has(K + '.other.5');
      const deep = JSON.parse('['.repeat(3000) + ']'.repeat(3000));
      mem.clear(); mem.set(K, js({ v: 1, decks: [], future: deep })); mem.set(K + '.other.6', js({ v: 1, decks: [{ id: 'b', name: 'b', holdings: [], purchases: [] }], future: deep }));
      let r2 = null, threw2 = null; try { r2 = S.readStore(K, T); S.writeStore(S.withNote(r2.data, '005930', 'm', T, 9), K, T); } catch (e) { threw2 = String(e); }
      out = { threw, data: r && r.data, unmerged: r && r.unmerged, kept, warned: warns.some((w) => w.includes('merging the copies another tab left failed')),
        threw2, ids: r2 && r2.data.decks.map((x) => x.id), future: !!(r2 && r2.data.future) };""")
    assert got["threw"] is None and got["data"] == {"v": 1, "decks": []} and got["unmerged"] is True and got["kept"] and got["warned"]
    assert got["threw2"] is None and got["ids"] == ["b"] and got["future"]


def test_two_tabs_taking_turns_keep_one_copy_each_not_one_per_save():
    """Review round 4, item 7: a copy is kept before a write only when the write does not hold everything in it, and a
    write removes the copies it holds (all their records, or later edits of them). 100 turns each leave a few keys, and
    the next start has every last edit."""
    got = run_tabs("""mem.set(K, JSON.stringify({ v: 1, decks: [] }));
      const A = await tab(), B = await tab(); let a = A.readStore(K, T).data, b = B.readStore(K, T).data; let ts = 1;
      let most = 0;
      for (let i = 0; i < 100; i++) {
        a = A.withNote(a, '005930', 'A' + i, T, ++ts); A.writeStore(a, K, T); B.keepOwnText(K, mem.get(K), T);   // the storage event
        most = Math.max(most, mem.size);
        b = B.withNote(b, '000660', 'B' + i, T, ++ts); B.writeStore(b, K, T); A.keepOwnText(K, mem.get(K), T);
        most = Math.max(most, mem.size);
      }
      const f = (await tab()).readStore(K, T);
      out = { most, notes: Object.fromEntries(Object.entries(f.data.notes).map(([t, v]) => [t, v.text])), after: mem.size };""")
    assert got["most"] <= 4 and got["after"] <= 4, got                 # 예전에는 200개 넘게 쌓였어요
    assert got["notes"] == {"005930": "A99", "000660": "B99"}


def test_held_units_never_overflow():
    """Review round 4, item 8: a crafted file's quantity or amount beyond Number.MAX_SAFE_INTEGER units (or not finite)
    counts nothing, so no sum becomes Infinity, and the store refuses such a purchase."""
    got = run("""out = { amount: S.H.importedUnits({ t: '005930', ccy: 'KRW', amountWon: 1e308, close: 1e-300, date: T }),
        units: S.H.toUnits(1e300), inf: S.H.toUnits(Infinity), ok: S.H.okUnits(1e300), held: [...S.H.heldUnits({ purchases: [{ t: 'A', qty: 1e300, price: 1, date: T, ccy: 'KRW' }] })],
        fine: S.H.toUnits(1.5), store: S.checkStore({ v: 1, decks: [{ id: 'a', name: 'a', holdings: [{ t: '005930', nk: 'x' }],
          purchases: [{ t: '005930', qty: 1e300, price: 1, date: T, ccy: 'KRW' }] }] }, T).problems };""")
    assert got["amount"] is None and got["units"] is None and got["inf"] is None and got["ok"] is False and got["held"] == []
    assert got["fine"] == 15000 and len(got["store"]) == 1 and "quantity" in got["store"][0]


def test_random_runs_of_old_and_new_tabs_lose_no_record_and_keep_every_later_edit():
    """Review round 4: random interleavings of new tabs, old (earlier-app) tabs and restarts, on one storage. Whatever the
    order: no exception; every portfolio and purchase made in a new tab is there exactly once; nothing appears twice; a
    stock a new tab took out stays out; the last note and 확인 필요 answer saved in a new tab is what the next start reads;
    the keys stay few. (The earlier app writing over its own kind is its own behaviour and not checked.)"""
    got = run_tabs("""
      const STK = [['005930', '삼성전자'], ['000660', 'SK하이닉스'], ['035420', 'NAVER']];
      const rng = (seed) => () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
      const res = { seqs: 0, errors: [], lost: [], dup: [], back: [], note: [], answer: [], keys: 0 };
      for (let s = 0; s < 120; s++) {
        mem.clear(); const R = rng(7000 + s); const pick = (a) => a[Math.floor(R() * a.length)];
        let tabs = [], ctr = 0, ts = 1700000000000;
        const or = { decks: new Map(), recs: [], removed: new Map(), notes: new Map(), answers: new Map() };
        const hide = (x) => { if (x && x.kind === 'new') x.M.keepMine(K); };          // the page closes (pagehide)
        const open = async (kind) => { if (kind === 'new') { const M = await tab(); const r = M.readStore(K, T); return { kind, M, data: r.data, ok: r.writable && !r.locked }; }
          const d = oldRead(); return { kind, data: d || { v: 1, decks: [] }, ok: true }; };
        const save = (x, next) => { if (!next || !x.ok) return false; const was = mem.get(K);
          if (x.kind === 'new') { if (!x.M.writeStore(next, K, T)) return false; } else oldWrite(next); x.data = next;
          if (mem.get(K) !== was) for (const y of tabs) if (y !== x && y.kind === 'new') y.M.keepOwnText(K, mem.get(K), T);   // the storage event
          return true; };
        try {
          for (let i = 0; i < 30; i++) {
            const r = R();
            if (!tabs.length || r < 0.12) { if (tabs.length < 3) tabs.push(await open(R() < 0.6 ? 'new' : 'old')); continue; }
            if (r < 0.2) { hide(tabs.splice(Math.floor(R() * tabs.length), 1)[0]); tabs.push(await open('new')); continue; }
            const x = pick(tabs), d = x.data, op = pick(['buy', 'buy', 'note', 'delnote', 'confirm', 'remove']), nw = x.kind === 'new';
            if (op === 'buy') {
              const [t, nk] = pick(STK), id = 'd' + (++ctr) + x.kind, price = 1000 + ctr;
              const deck = { id, name: id, createdAt: T, holdings: [{ t, nk, target: 1, plannedQty: 1, rules: [] }],
                purchases: [{ ...(nw ? { id: 'p' + x.M.recordId() } : {}), t, date: T, qty: 1, price, ccy: 'KRW' }] };
              if (save(x, { ...d, decks: [...d.decks, deck] })) { or.decks.set(id, x.kind); or.recs.push({ id, t, price, by: x.kind }); }
            } else if (op === 'note' || op === 'delnote') {
              const t = pick(STK)[0];
              if (op === 'delnote' && !(d.notes && d.notes[t])) continue;
              const text = op === 'note' ? 'n' + (++ctr) : '';
              if (save(x, nw ? x.M.withNote(d, t, text, T, ++ts) : S.withNote(d, t, text, T))) or.notes.set(t, { text: text || null, by: x.kind });
            } else {
              const decks = d.decks.filter((y) => y.holdings.length);
              if (!decks.length) continue;
              const deck = pick(decks), t = pick(deck.holdings).t, k = deck.id + '|' + t;
              if (op === 'confirm') {
                const ans = pick(['cut', 'notCut']), item = { t, rule: 'divCut', fy: 2025, a: 1000, b: 800 };
                if (save(x, nw ? x.M.withConfirm(d, deck.id, item, ans, T, ++ts) : S.withConfirm(d, deck.id, item, ans, T))) or.answers.set(k, { ans, by: x.kind });
              } else if (save(x, nw ? x.M.withoutHolding(d, deck.id, t, T, ++ts) : S.withoutHolding(d, deck.id, t))) { or.removed.set(k, x.kind); or.answers.delete(k); }
            }
            res.keys = Math.max(res.keys, mem.size);
          }
          for (const x of tabs) hide(x);
          const f = (await tab()).readStore(K, T), data = f.data;
          for (const [id, by] of or.decks) if (by === 'new' && !data.decks.some((y) => y.id === id)) res.lost.push(s + ' deck ' + id);
          for (const rec of or.recs) {
            const deck = data.decks.find((y) => y.id === rec.id);
            const n = deck ? deck.purchases.filter((p) => p.price === rec.price).length : 0;
            if (n > 1) res.dup.push(s + ' ' + rec.id);
            if (rec.by === 'new' && deck && !or.removed.has(rec.id + '|' + rec.t) && n !== 1) res.lost.push(s + ' purchase ' + rec.id + ' x' + n);
          }
          for (const [k, by] of or.removed) { const [id, t] = k.split('|'); const deck = data.decks.find((y) => y.id === id);
            if (by === 'new' && deck && deck.holdings.some((h) => h.t === t)) res.back.push(s + ' ' + k); }
          for (const [t, { text, by }] of or.notes) if (by === 'new' && ((data.notes && data.notes[t] ? data.notes[t].text : null) !== text)) res.note.push(s + ' ' + t);
          for (const [k, { ans, by }] of or.answers) { const [id, t] = k.split('|'); const deck = data.decks.find((y) => y.id === id);
            const c = deck && deck.holdings.some((h) => h.t === t) ? (deck.confirms || []).find((y) => y.t === t) : undefined;
            if (by === 'new' && c !== undefined && (!c || c.answer !== ans)) res.answer.push(s + ' ' + k); }
        } catch (e) { res.errors.push(s + ': ' + (e && e.stack)); }
        res.seqs++;
      }
      out = res;""")
    assert got["seqs"] == 120 and got["errors"] == [], got["errors"][:2]
    assert got["lost"] == [] and got["dup"] == [] and got["back"] == [], got
    assert got["note"] == [] and got["answer"] == [], got
    assert got["keys"] <= 12, got["keys"]


def test_the_first_records_in_an_empty_storage_change_no_other_key_and_mine_starts_on_the_next_start():
    """An import into an empty storage (the iPhone home-screen app's first 기록 불러오기) changes no stored value but the
    records (smoke_v2's rule); this app's copy of its last write (.mine) starts at the next write or start."""
    got = run(f"""const ok = S.writeStore({json.dumps(V2, ensure_ascii=False)}, K, T); const first = [...mem.keys()];
      S.readStore(K, T); const next = [...mem.keys()].sort(); const same = mem.get(K + '.mine') === mem.get(K);
      out = {{ ok, first, next, same }};""")
    assert got == {"ok": True, "first": ["baepsae2.v1"], "next": ["baepsae2.v1", "baepsae2.v1.mine"], "same": True}


def test_an_open_tab_keeps_its_records_when_another_tab_writes_over_them():
    """The browser tells an open tab when another tab writes the records (the storage event, app.jsx): when what was
    written does not hold everything this tab saved (the earlier app writes over without looking), this tab's text is
    kept as a copy and merged back on the next start; when it does (another new tab that merged it), nothing is kept."""
    got = run_tabs(f"""const N = await tab(); const n = N.readStore(K, T);
      const m = oldRead() || {{ v: 1, decks: [] }};
      N.writeStore({{ ...n.data, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}, K, T);    // the first records: no .mine yet
      oldWrite({{ ...m, notes: {{ '000660': {{ text: '예전 창', at: T }} }} }});
      const kept = N.keepOwnText(K, mem.get(K), T);
      const f = (await tab()).readStore(K, T);
      const again = N.keepOwnText(K, JSON.stringify({{ ...f.data }}), T);                       // a text that holds all of it
      out = {{ kept, again, ids: f.data.decks.map((x) => x.id), notes: Object.keys(f.data.notes), restored: f.restored }};""")
    assert got == {"kept": True, "again": False, "ids": ["d1"], "notes": ["000660"], "restored": True}


def test_a_tab_that_wrote_the_first_records_keeps_them_when_it_closes():
    """The first records written into an empty storage have no .mine yet; when the page closes or is hidden (pagehide,
    visibilitychange: app.jsx), keepMine starts it, so a tab of the earlier app open since before cannot drop them."""
    got = run_tabs(f"""const N = await tab(); const n = N.readStore(K, T); const m = oldRead() || {{ v: 1, decks: [] }};
      N.writeStore({{ ...n.data, decks: [{json.dumps(BUILT, ensure_ascii=False)}] }}, K, T);
      const before = [...mem.keys()]; const kept = N.keepMine(K); const twice = N.keepMine(K);
      oldWrite({{ ...m, notes: {{ '000660': {{ text: '예전 창', at: T }} }} }});                 // the old tab, after N closed
      const f = (await tab()).readStore(K, T);
      out = {{ before, kept, twice, ids: f.data.decks.map((x) => x.id), restored: f.restored }};""")
    assert got == {"before": ["baepsae2.v1"], "kept": True, "twice": False, "ids": ["d1"], "restored": True}
