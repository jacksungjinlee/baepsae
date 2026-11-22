# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6b 오늘 볼 것 카드 (src/v2/look.js · todaylook.jsx 의 글 · store.js 의 seen) — Node 에서 돌려봐요.

docs/tasks/v19.6-records-alerts-dark.md Part B.2 and A.1 [Q6] (adds only; the expected values worked by hand):
- 유상증자 · CB · BW: 가진 종목만 · 공시일이 최근 30일(오늘 포함) · 철회는 없음 · 몸말은 종류와 방식으로, 숫자가 없거나 읽는 중이면 '숫자를 읽지
  못했어요' · 승인 문장이 없는 모양(유무상증자 · 기타주식 · 두 종류 · 그 밖의 방식)은 빠지고 이름이 남아요 · 그날 목록 실패(issueOk false)
- 확인했어요(seen): 같은 종목 · 종류 · 숫자에 같은 공시나 같은 결의일이면 숨김 · 숫자가 다른 정정은 다시 · 120일 지난 표시는 새 표시를 넣을 때
  빠져요 · 기록 파일과 두 창은 합집합(같은 표시는 나중 시각)
- 지분 변동: 최근 7일 · |q| × 오늘 종가 ≥ 1억원 (저장된 amt 말고 지금 주가) · 역할별 제목 · 직위 빈칸은 '임원·주요주주' · 이/가
- 국민연금: 최근 7일 · 한 자리로 반올림해 같으면 없음 · 변화가 비면 없음
- 다가오는 일정: 미국 종목만 · 오늘 ~ 7일 뒤 · 5개까지 · 같은 날은 실적 발표 먼저
- 멈춘 데이터 · 멈춘 공시 목록 · 실패: 카드 없음 (그 문구만)
(what the screens show is checked in tests/smoke_v2.py scene_v196b · scene_v196b_states)
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
_B = {}


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-look-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("Lk", "look.js"), ("Tl", "todaylook.jsx"), ("Fm", "format.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/w.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, Lk, Tl, Fm, C } from './w.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


FAKE = """
const mem = new Map(); const warns = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = (m) => warns.push(String(m)); console.info = () => {};
const T = '2026-11-12', ymd = (n) => { const d = new Date(Date.parse(T + 'T00:00:00Z') - n * 86400000); return d.toISOString().slice(0, 10).replace(/-/g, ''); };
const iso = (n) => new Date(Date.parse(T + 'T00:00:00Z') + n * 86400000).toISOString().slice(0, 10);
const kr = (t, more = {}) => ({ t, nk: '종목' + t, cls: 'kr', price: 50000, ...more });
const us = (t, more = {}) => ({ t, nk: t + ' Inc.', cls: 'us', price: 100, ...more });
const loadOf = (stocks, { stale = false } = {}) => ({ status: 'ok', preview: !stale, data: { pxDate: T, usPxDate: T, fx: 1400, stocks },
  byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map(), fresh: stale ? { stale: true, days: 3 } : { stale: false, days: 0 },
  corp: { publishedAt: '2026-11-08T09:00:00+09:00' } });
const NOW = Date.parse(T + 'T08:00:00+09:00');
const discOf = (d, more = {}) => ({ status: 'ok', data: { asOf: T, newest: T, listOk: true, publishedAt: T + 'T06:40:00+09:00', insider: [], nps: [],
  issue: [], issueOk: true, ...d, ...more } });
const deckOf = (rows) => ({ id: 'd1', name: '포트폴리오', createdAt: '2026-11-01', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
  holdings: rows.map(([t, cls]) => ({ t, nk: '종목' + t, cls })), purchases: [], imported: rows.map(([t, cls]) => ({ t, nk: '종목' + t, ccy: cls === 'us' ? 'USD' : 'KRW', qty: 3 })) });
const row = (rc, t, kind, days, more = {}) => ({ rc: '2026' + String(rc).padStart(10, '0'), d: ymd(days), t, nk: '종목' + t, kind, bd: ymd(days + 1), how: null,
  n: null, p: null, amt: null, cor: false, ...(kind === 'rights' ? { cls: 'common' } : {}), ...more });
"""


def test_issue_body_reads_each_shape_and_leaves_out_the_ones_without_an_approved_line():
    got = run("""const b = Lk.issueBody;
      out = {
        holders: b(row(1, 'A', 'rights', 0, { how: 'holders', n: 100, p: 5 })), others: b(row(1, 'A', 'rights', 0, { how: 'others', n: 100, p: 5 })),
        noP: b(row(1, 'A', 'rights', 0, { how: 'others', n: 100 })), noN: b(row(1, 'A', 'rights', 0, { how: 'holders', p: 5 })),
        pend: b(row(1, 'A', 'rights', 0, { pend: true, cls: null })), cb: b(row(1, 'A', 'cb', 0, { amt: 1e10, p: 3 })), bw: b(row(1, 'A', 'bw', 0, { amt: 1e10, p: 3 })),
        cbNoAmt: b(row(1, 'A', 'cb', 0, { p: 3 })), bwPend: b(row(1, 'A', 'bw', 0, { pend: true })),
        bonus: b(row(1, 'A', 'rights', 0, { how: 'holders', n: 100, p: 5, bonus: true })), bonusPend: b(row(1, 'A', 'rights', 0, { pend: true, bonus: true, cls: null })),
        other: b(row(1, 'A', 'rights', 0, { how: 'others', n: 100, p: 5, cls: 'other' })), both: b(row(1, 'A', 'rights', 0, { how: 'others', n: 100, p: 5, n2: 10, p2: 1 })),
        howNull: b(row(1, 'A', 'rights', 0, { n: 100, p: 5 })), eb: b({ kind: 'eb', amt: 1, p: 1 }),
      };""")
    assert got == {"holders": "holders", "others": "others", "noP": "unread", "noN": "unread", "pend": "unread", "cb": "cb", "bw": "bw",
                   "cbNoAmt": "unread", "bwPend": "unread", "bonus": None, "bonusPend": None, "other": None, "both": None, "howNull": None, "eb": None}


def test_issue_cards_held_only_last_30_days_newest_first_without_withdrawals_and_marked_ones():
    got = run("""
      const issue = [row(1, '000001', 'cb', 0, { amt: 3e10, p: 7.04 }), row(2, '000001', 'rights', 29, { how: 'holders', n: 12000000, p: 18 }),
        row(3, '000001', 'rights', 30, { how: 'holders', n: 1, p: 1 }), row(4, '000002', 'bw', 1, { amt: 1e9, p: 2 }),
        row(5, '000001', 'cb', 1, { wd: true, cor: true, bd: null }), row(6, '000001', 'rights', 2, { how: 'others', n: 9, p: 9, bonus: true }),
        row(7, '000001', 'bw', -1, { amt: 1, p: 1 }), row(8, '000001', 'bw', 3, { amt: 2e9, p: 4 }), row(9, '000001', 'rights', 0, { how: 'others', n: 5, p: 1.5 })];
      const seen = { seen: [{ t: '000001', kind: 'bw', bd: ymd(4), n: null, p: 4, amt: 2e9, at: T }] };
      const r = Lk.issueCards(discOf({ issue }), new Set(['000001']), T, seen);
      out = { cards: r.cards.map((c) => [c.rc.slice(-1), c.body, c.date]), skipped: r.skipped.map((x) => [x.rc.slice(-1), x.why]), fail: r.fail,
        failed: Lk.issueCards(discOf({ issue }, { issueOk: false }), new Set(['000001']), T, {}).fail,
        missing: (() => { const d = discOf({}); delete d.data.issue; const x = Lk.issueCards(d, new Set(['000001']), T, {}); return [x.missing, x.fail, x.cards.length]; })(),
        notList: (() => { const x = Lk.issueCards(discOf({ issue: 'x' }), new Set(['000001']), T, {}); return [x.missing, x.fail]; })() };""")
    # newest first (on the same day the later filing number first); 29 days back is in, 30 is out; a future date is out; 000002 is not held;
    # the withdrawal, the bonus issue and the marked bw are left out (only the bonus issue is named, the others are not shown by rule)
    assert got["cards"] == [["9", "others", "2026-11-12"], ["1", "cb", "2026-11-12"], ["2", "holders", "2026-10-14"]], got
    assert got["skipped"] == [["6", "bonus: a rights and bonus issue"]] and got["fail"] is False and got["failed"] is True
    assert got["missing"] == [True, False, 0] and got["notList"] == [False, True]


def test_a_mark_hides_the_same_numbers_on_the_same_filing_or_board_date_and_a_correction_with_other_numbers_shows_again():
    got = run("""
      const r = row(2, '000001', 'rights', 1, { how: 'holders', n: 100, p: 5 });
      let d = S.withSeen({ v: 1, decks: [] }, r, T, 1700000000000);
      const m = (x) => S.isSeen(d, x);
      out = {
        mark: d.seen,
        same: m(r), sameNumbersNewFiling: m({ ...r, rc: '20269999999999', cor: true }), otherNumbers: m({ ...r, rc: '20269999999999', n: 120, cor: true }),
        otherP: m({ ...r, p: 6 }), boardDateReadLater: m({ ...r, bd: ymd(5) }), otherBdOtherFiling: m({ ...r, rc: '20269999999999', bd: ymd(5) }),
        otherKind: m({ ...r, kind: 'cb' }), otherStock: m({ ...r, t: '000002' }),
      };
      // a filing marked while its numbers were not read yet shows again once they are
      const p = row(3, '000001', 'cb', 0, { pend: true });
      d = S.withSeen(d, p, T, 1700000000001);
      out.pendThenRead = [S.isSeen(d, p), S.isSeen(d, { ...p, pend: undefined, amt: 3e10, p: 7 })];""")
    assert got["mark"] == [{"t": "000001", "kind": "rights", "bd": "20261110", "n": 100, "p": 5, "amt": None, "rc": "20260000000002", "at": "2026-11-12",
                            "ts": 1700000000000}]
    assert got["same"] and got["sameNumbersNewFiling"] and got["boardDateReadLater"]
    assert not any(got[k] for k in ("otherNumbers", "otherP", "otherBdOtherFiling", "otherKind", "otherStock"))
    assert got["pendThenRead"] == [True, False]


def test_with_seen_prunes_marks_older_than_120_days_replaces_its_own_and_refuses_what_is_not_a_decision():
    got = run("""
      const old = (days, rc) => ({ t: '000001', kind: 'cb', bd: null, n: null, p: 1, amt: 1e9, rc, at: iso(-days), ts: 1 });
      const base = { v: 1, decks: [], seen: [old(121, '20260000000001'), old(120, '20260000000002'), old(10, '20260000000003')] };
      const r = row(3, '000001', 'cb', 0, { amt: 1e9, p: 1 });
      const d = S.withSeen(base, { ...r, rc: '20260000000003', bd: null }, T, 5);
      out = { kept: d.seen.map((x) => [x.rc.slice(-1), x.at, x.ts]),
        bad: [S.withSeen(base, { ...r, kind: 'eb' }, T), S.withSeen(base, { ...r, t: '' }, T), S.withSeen(base, r, '2026-13-01'), S.withSeen(base, r, T, -1)],
        cap: (() => { const many = { v: 1, decks: [], seen: Array.from({ length: S.SEEN_MAX }, (_, i) => old(1, '2026' + String(100 + i).padStart(10, '0'))) };
          const x = S.withSeen(many, r, T, 9); return [x.seen.length, x.seen[0].rc.slice(-3), x.seen[x.seen.length - 1].ts]; })() };""")
    # 121 days before today goes, 120 days stays; the same mark is replaced by the new one (its date and time)
    assert got["kept"] == [["2", "2026-07-15", 1], ["3", "2026-11-12", 5]], got["kept"]
    assert got["bad"] == [None, None, None, None]
    assert got["cap"] == [500, "101", 9]


def test_the_seen_part_is_checked_travels_in_a_records_file_and_merges_as_a_union():
    got = run("""
      const a = { t: '000001', kind: 'cb', bd: '20261101', n: null, p: 3, amt: 1e9, rc: '20260000000001', at: '2026-11-02', ts: 10 };
      const b = { t: '000002', kind: 'rights', bd: null, n: 5, p: 1, amt: null, at: '2026-11-03' };
      const ok = S.checkStore({ v: 1, decks: [], seen: [a, b] }, T);
      const bads = [[{ ...a, kind: 'eb' }], [{ ...a, bd: '2026-11-01' }], [{ ...a, n: 0 }], [{ ...a, rc: '123' }], [{ ...a, at: '2026-02-30' }], [{ ...a, ts: 1.5 }], 'x', [null],
        Array.from({ length: S.SEEN_MAX + 1 }, () => a)];
      const file = JSON.parse(S.exportText({ v: 1, decks: [], seen: [a] }));
      const back = S.parseImport(S.exportText({ v: 1, decks: [], seen: [a, b] }), T);
      const later = { ...a, at: '2026-11-05', ts: 20 };
      const merged = S.mergeStores({ v: 1, decks: [], seen: [a] }, { v: 1, decks: [], seen: [later, b] }, 99, [], T);
      const tabs = S.mergeTabs({ v: 1, decks: [], seen: [b, later] }, { v: 1, decks: [], seen: [a] }, T);
      out = { ok: [ok.readable, ok.problems, ok.data.seen.length], bad: bads.map((s) => S.checkStore({ v: 1, decks: [], seen: s }, T).problems.length),
        file: file.seen, back: back.seen.length, v: S.versionFor({ v: 1, decks: [], seen: [a] }),
        merged: merged.seen.map((x) => [x.t, x.ts ?? null]), tabs: tabs.seen.map((x) => [x.t, x.ts ?? null]),
        empty: 'seen' in JSON.parse(S.exportText({ v: 1, decks: [], seen: [] })) };""")
    assert got["ok"] == [True, [], 2] and got["bad"] == [1] * 9
    assert got["file"] == [{"t": "000001", "kind": "cb", "bd": "20261101", "n": None, "p": 3, "amt": 1e9, "rc": "20260000000001", "at": "2026-11-02", "ts": 10}]
    assert got["back"] == 2 and got["v"] == 1                                         # not a version-2 part
    # the union, the same mark keeping the later time: this device's list first, then the file's (or the other tab's) new ones
    assert got["merged"] == [["000001", 20], ["000002", None]] and got["tabs"] == [["000001", 20], ["000002", None]]
    assert got["empty"] is False


def test_insider_cards_last_7_days_from_100m_won_at_todays_close_with_role_titles():
    got = run("""
      const stocks = [kr('000001', { price: 50000 }), kr('000002', { price: 100000 }), kr('000003', { price: null }), us('AAA')];
      const ins = (rc, t, days, q, role, pos, amt = 999) => ({ rc: '2026' + String(rc).padStart(10, '0'), d: ymd(days), t, nk: 'x', q, role, pos, amt });
      const insider = [ins(1, '000001', 0, 2000, '임원', '대표이사'), ins(2, '000001', 6, -2000, '주요주주', '10%이상주주'),
        ins(3, '000001', 7, 5000, '임원', '부사장'), ins(4, '000001', 1, 1999, '임원', '상무'), ins(5, '000002', 1, -1000, '임원·주요주주', '사장'),
        ins(6, '000002', 2, 1000, null, '-'), ins(7, '000003', 0, 100000, '임원', '회장'), ins(8, '000009', 0, 100000, '임원', '회장'),
        ins(9, '000002', -1, 5000, '임원', '이사'), ins(10, '000002', 0, 0, '임원', '이사'), ins(11, '000002', 0, 1500, '감사', '감사')];
      const cover = { held: new Set(['000001']), watched: new Set(['000002', '000003']), all: new Set(['000001', '000002', '000003']) };
      const r = Lk.insiderCards(discOf({ insider }), cover, T, new Map(stocks.map((s) => [s.t, s])));
      out = { cards: r.cards.map((c) => [c.rc.slice(-2), c.title, c.pos, Math.round(c.won), c.up]), skipped: r.skipped.map((x) => [x.rc.slice(-2), x.why]),
        roles: Lk.roleWords() };""")
    # 2,000 × 50,000 = 1억원 exactly is in; 1,999 × 50,000 is under; 7 days back and a future date are out; the stored amt is not used
    assert got["cards"] == [["11", "both", "감사", 150000000, True], ["01", "exec", "대표이사", 100000000, True],
                            ["05", "both", "사장", 100000000, False], ["06", "both", None, 100000000, True],
                            ["02", "major", "10%이상주주", 100000000, False]], got["cards"]
    assert got["skipped"] == [["07", "no official close in today's data"], ["11", 'role "감사" is not one of the three']], got["skipped"]
    assert got["roles"] == {"both": "임원·주요주주", "exec": "임원", "major": "주요주주"}


def test_the_role_words_are_the_ones_the_pipeline_writes():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    both = re.search(r'^INSIDER_BOTH = "([^"]+)"', src, re.M).group(1)
    roles = re.search(r'^INSIDER_ROLES = \("([^"]+)", "([^"]+)", INSIDER_BOTH\)', src, re.M).groups()
    got = run("out = Lk.roleWords();")
    assert (got["exec"], got["major"], got["both"]) == (roles[0], roles[1], both)


def test_card_words_fill_the_approved_lines():
    got = run("""
      const L = C.look;
      out = {
        holders: Tl.issueText({ body: 'holders', n: 12000000, p: 18 }), others: Tl.issueText({ body: 'others', n: 1428571, p: 5.57 }),
        cb: Tl.issueText({ body: 'cb', amt: 30000000000, p: 7.04 }), bw: Tl.issueText({ body: 'bw', amt: 1500000000, p: 0.5 }),
        unread: Tl.issueText({ body: 'unread' }), title: Tl.issueTitle({ nk: '솔담정밀', kind: 'rights' }), titleBw: Tl.issueTitle({ nk: 'A', kind: 'bw' }),
        insI: Tl.insiderText({ pos: '부사장', up: true, won: 141800000 }), insGa: Tl.insiderText({ pos: '대표이사', up: false, won: 360000000 }),
        insBlank: Tl.insiderText({ pos: null, up: false, won: 1418000000 }), insJo: Tl.insiderText({ pos: 'CEO', up: true, won: 1.23e12 }),
        insTitle: [Tl.insiderTitle({ nk: 'A', title: 'exec' }), Tl.insiderTitle({ nk: 'A', title: 'major' }), Tl.insiderTitle({ nk: 'A', title: 'both' })],
        nps: [Tl.npsText({ a: 9.9, b: 8.8, up: false }), Tl.npsText({ a: 5, b: 6.1, up: true })], npsTitle: Tl.npsTitle({ nk: '마루식품' }),
        L };""")
    L = got["L"]
    assert got["holders"] == "회사가 새 주식 12,000,000주(지금 주식 수의 18%)를 발행하기로 했어요. 지금 주주에게 먼저 살 기회를 주는 방식이에요. 사지 않으면 내 지분 비율이 줄어들어요."
    assert got["others"] == "회사가 새 주식 1,428,571주(지금 주식 수의 5.57%)를 발행하기로 했어요. 다른 투자자에게 파는 방식이라 내 지분 비율이 줄어들어요."
    assert got["cb"] == "회사가 나중에 주식으로 바꿀 수 있는 채권을 300억원어치 발행하기로 했어요. 모두 주식으로 바뀌면 주식 수가 지금보다 7.04% 늘어나요."
    assert got["bw"] == "회사가 정해진 가격에 새 주식을 살 수 있는 권리가 붙은 채권을 15억원어치 발행하기로 했어요. 그 권리를 모두 쓰면 주식 수가 지금보다 0.5% 늘어나요."
    assert got["unread"] == "공시에서 숫자를 읽지 못했어요. 공시를 직접 확인해 주세요."
    assert got["title"] == "솔담정밀 · 유상증자 결정" and got["titleBw"] == "A · 신주인수권부사채 발행 결정"
    assert got["insI"] == "부사장이 지분을 늘린 보고가 있어요. 지금 주가로 약 1억원이에요."
    assert got["insGa"] == "대표이사가 지분을 줄인 보고가 있어요. 지금 주가로 약 4억원이에요."
    assert got["insBlank"] == "임원·주요주주가 지분을 줄인 보고가 있어요. 지금 주가로 약 14억원이에요."
    assert got["insJo"] == "CEO가 지분을 늘린 보고가 있어요. 지금 주가로 약 1.2조원이에요."
    # 둘 다인 역할 · 빈 역할의 제목은 Jack 의 승인을 기다려요 (null: 그 카드는 빠져요)
    assert got["insTitle"] == ["A · 임원 지분 변동", "A · 주요주주 지분 변동", None] and L["insBoth"] is None
    assert got["nps"] == ["국민연금 지분이 9.9%에서 8.8%로 줄었어요.", "국민연금 지분이 5.0%에서 6.1%로 늘었어요."]
    assert got["npsTitle"] == "마루식품 · 국민연금 지분"


def test_nps_cards_round_to_one_decimal_and_skip_a_blank_or_unchanged_share():
    got = run("""
      const n = (t, days, rt, chg) => ({ d: ymd(days), t, nk: 'x', rt, chg });
      const nps = [n('000001', 0, 8.8, -1.1), n('000002', 6, 6.03, 0.01), n('000003', 1, 9.94, 1.04), n('000004', 2, 5, null), n('000005', 7, 9, 1),
        n('000006', 3, 7.31, -0.12), n('000009', 0, 9, 1)];
      const all = new Set(['000001', '000002', '000003', '000004', '000005', '000006']);
      out = Lk.npsCards(discOf({ nps }), { held: all, watched: new Set(), all }, T, new Map()).map((c) => [c.t, c.a, c.b, c.up, c.date]);""")
    assert got == [["000001", 9.9, 8.8, False, "2026-11-12"], ["000003", 8.9, 9.9, True, "2026-11-11"], ["000006", 7.4, 7.3, False, "2026-11-09"]], got


def test_date_rows_us_only_today_to_7_days_at_most_five_earnings_first():
    got = run("""
      const stocks = [us('A', { ed: iso(2), xd: iso(2) }), us('B', { xd: iso(0), ed: iso(8) }), us('C', { ed: iso(7), xd: iso(-1) }), us('D', { ed: iso(3) }),
        us('E', { xd: iso(1) }), us('F', { ed: iso(4) }), kr('000001', { ed: iso(1) }), us('Z', { ed: iso(1) }), us('G', { ed: 'soon' })];
      const all = new Set(['A', 'B', 'C', 'D', 'E', 'F', '000001', 'G']);
      const rows = Lk.dateRows(new Map(stocks.map((s) => [s.t, s])), { held: new Set(), watched: all, all }, T);
      out = rows.map((r) => [r.t, r.kind, r.date]);""")
    assert got == [["B", "xd", "2026-11-12"], ["E", "xd", "2026-11-13"], ["A", "earn", "2026-11-14"], ["A", "xd", "2026-11-14"], ["D", "earn", "2026-11-15"]], got


def test_the_model_needs_fresh_data_and_the_days_filings_and_says_why_otherwise():
    got = run("""
      const stocks = [kr('000001'), kr('000002'), us('AAA', { ed: iso(1) })];
      const store = { data: { v: 2, decks: [deckOf([['000001', 'kr'], ['AAA', 'us']])], watch: { '000002': { at: '2026-11-01' } } } };
      const disc = discOf({ issue: [row(1, '000001', 'cb', 0, { amt: 3e10, p: 7 })],
        insider: [{ rc: '20260000000101', d: ymd(0), t: '000002', nk: 'x', q: 5000, role: '임원', pos: '이사' }], nps: [{ d: ymd(0), t: '000001', rt: 8, chg: 1 }] });
      const m = (load, d, s = store) => { const x = Lk.lookModel(load, s, d, T, NOW); return [x.fresh, x.ds, x.issue.length, x.insider.length, x.nps.length, x.dates.length,
        x.issueFail, x.discFail, !!x.discOld, x.any, x.noKr, x.kr]; };
      const fresh = loadOf(stocks);
      out = {
        ok: m(fresh, disc), stale: m(loadOf(stocks, { stale: true }), disc), failed: m({ status: 'fail' }, disc),
        discFail: m(fresh, { status: 'fail' }), waiting: m(fresh, { status: 'loading' }), listStopped: m(fresh, discOf({}, { listOk: false, newest: iso(-3) })),
        issueFail: m(fresh, discOf({ issue: [] }, { issueOk: false })),
        usOnly: m(fresh, null, { data: { v: 2, decks: [deckOf([['AAA', 'us']])] } }),
        watchKr: m(fresh, discOf({}), { data: { v: 1, decks: [], watch: { '000002': { at: '2026-11-01' } } } }),
      };""")
    # fresh: the issue card (held), the watched stock's 지분 변동, the held 국민연금, one US date; a Korean stock held → the no-Korean-dates line
    assert got["ok"] == [True, "ok", 1, 1, 1, 1, False, False, False, True, True, True]
    assert got["stale"] == [False, "skip", 0, 0, 0, 0, False, False, False, False, False, False]
    assert got["failed"] == got["stale"]
    assert got["discFail"] == [True, "fail", 0, 0, 0, 1, False, True, False, True, True, True]
    assert got["waiting"] == [True, "wait", 0, 0, 0, 1, False, False, False, True, True, True]
    assert got["listStopped"] == [True, "stale", 0, 0, 0, 1, False, False, True, True, True, True]
    assert got["issueFail"] == [True, "ok", 0, 0, 0, 1, True, False, False, True, True, True]
    assert got["usOnly"] == [True, "skip", 0, 0, 0, 1, False, False, False, True, False, False]
    assert got["watchKr"] == [True, "ok", 0, 0, 0, 0, False, False, False, False, False, True]


def test_the_heading_opens_the_page_only_when_it_shows_a_card():
    """An insider card whose title waits for Jack (role 임원·주요주주 or blank: look.insBoth null) is not shown, so on its own it does not
    make the 오늘 볼 것 heading a link (the page would be empty and go straight back to 홈)."""
    got = run("""
      const base = { fresh: true, issue: [], insider: [], nps: [], dates: [] };
      const ins = (title) => ({ t: 'A', nk: 'A', title, rc: '20260000000001', date: T, up: true, won: 1e8, pos: null });
      out = [Tl.pageHas({ ...base, insider: [ins('both')] }), Tl.pageHas({ ...base, insider: [ins('both'), ins('exec')] }),
        Tl.pageHas({ ...base, dates: [{}] }), Tl.pageHas({ ...base, nps: [{}] }), Tl.pageHas({ ...base, issue: [{}] }), Tl.pageHas(base),
        Tl.pageHas({ ...base, fresh: false, issue: [{}] }), Tl.lookRowCount({ ...base, insider: [ins('both'), ins('exec')] })];""")
    assert got == [False, True, True, True, True, False, False, 1]
