# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.7b 내 기준으로 찾기 · 두 종목 비교 · 바꾸기 (src/v2/find.js · compare.jsx · edit.js 의 바꾸기) — Node 에서 돌려봐요.

docs/tasks/v19.7-portfolio-edit.md Parts D–E, Test changes (adds only: "finder ranking excludes held stocks and applies each filter;
compare verdict variants and blank facts"), Acceptance 2:
- 찾기 목록 = 이 포트폴리오의 기준(점수 · 빼기 · 엄격함 · 한국:미국)으로 돌린 screen() 의 순서에서 가진 종목(기다리는 담기 · 빼기 포함)을
  뺀 것. 네 칩: 전체 · 없는 업종(포트폴리오에서 0% 인 업종) · 주가 변동 작은 순(위 20% 를 변동성 낮은 순, 빈 변동성은 빼요) · 배당 주는
  종목(확인된 배당만). 칩마다 20줄까지. 테스트 안에서 screen() 으로 따로 계산한 것과 같아요 — 시험 데이터와, BAEPSAE_FIND_DATA 에
  발행 파일 폴더를 주면 그 진짜 데이터에서도 (보이는 기준 템플릿마다, 칩마다)
- 비교 판정: 네 가지 · 한 가지 사실 · 빈 사실 · 같은 값 (빈 것처럼) · 이/가 · 은/는
- 바꾸기: 후보가 그 종목의 목표 비중을 이어받아 합계 100% · 팔고 빼기는 한 번에 저장 · 마지막 한 종목도 바꿀 수 있어요
- 칸의 숫자는 회사 페이지의 규칙대로, 데이터가 비운 숫자는 "–" 와 회사 페이지의 그 줄
- 새 주소 (…/find · …/compare/<코드>), 기준 점수 저장, 새 파일은 색을 직접 쓰지 않아요
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
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
REAL = os.environ.get("BAEPSAE_FIND_DATA")          # 발행 파일 폴더 (data.json · corp.json): Acceptance 2 의 진짜 데이터 확인
_B = {}


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-find-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("F", "find.js"), ("E", "edit.js"), ("En", "engine.js"), ("Rk", "ranks.js"), ("S", "store.js"), ("Rc", "records.js"),
                              ("Rt", "routes.js"), ("Cm", "compare.jsx"), ("Fi", "finder.jsx")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export {{ C }} from {json.dumps(os.path.join(ROOT, 'src', 'copy', 'v2.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/b.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { F, E, En, Rk, S, Rc, Rt, Cm, Fi, C } from './b.mjs';\nimport fs from 'fs';\n" + HELP + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


HELP = r"""
const warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};
const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
const T = '2026-11-12';
const loadDir = (dir) => {
  const data = JSON.parse(fs.readFileSync(dir + '/data.json', 'utf8'));
  const corp = JSON.parse(fs.readFileSync(dir + '/corp.json', 'utf8'));
  En.setDataShape(data);
  return { status: 'ok', data, byT: new Map(data.stocks.map((s) => [s.t, s])), coByT: new Map((corp.companies || []).map((c) => [c.t, c])) };
};
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const pend = (id) => ({ id, kind: 'sell', check: 'pending' });
// a built portfolio over real rows: equal targets, planned at today's prices, no purchases unless asked
const deckOf = (load, ts, settings, held = []) => {
  const w = Math.round(1e6 / ts.length) / 1e6;
  return { id: 'd1', name: '시험 포트폴리오', createdAt: '2026-10-01', planFx: 1300, settings: { maxPct: 100, amountMan: 1000, ...settings },
    holdings: ts.map((t, i) => { const s = load.byT.get(t); return { t, nk: s.nk, cls: s.cls === 'us' ? 'us' : 'kr', ind: s.ind || null, kind: 'core',
      target: i === ts.length - 1 ? Math.round((1 - w * (ts.length - 1)) * 1e6) / 1e6 : w, setAt: '2026-10-01', plannedQty: 10, planPx: s.price, rules: [pend('audit'), ...band(w)] }; }),
    purchases: held.map((t, i) => { const s = load.byT.get(t); return { id: 'p' + i + 'aaaaaa', t, qty: 10, price: s.price, date: '2026-10-01', ccy: s.cls === 'us' ? 'USD' : 'KRW', ...(s.cls === 'us' ? { fx: 1300 } : {}) }; }) };
};
// THE independent reading of Acceptance 2: screen() with the portfolio's settings, its markets as one list (total, then code),
// without the held stocks (and a share class of a held company), the value guards' rows when 가치 has points, a company's second
// listing; then each chip as the spec says it. Written here from screen() and the data, not from find.js.
const expected = (load, deck, draft, chip) => {
  const st0 = deck.settings;
  const st = { points: st0.points, exclude: st0.exclude || {}, strict: st0.strict, mix: st0.mix, pinned: [] };
  const res = En.screen(load.data.stocks, st);
  const all = Object.values(res.markets).flatMap((m) => m.survivors).sort((a, b) => b.total - a.total || (a.t < b.t ? -1 : 1));
  const held = new Set([...deck.holdings.map((h) => h.t), ...(draft.adds || []).map((a) => a.t)]);
  const heldRows = [...held].map((t) => load.byT.get(t)).filter(Boolean);
  const guard = (st.points.value || 0) > 0;
  let rows = all.filter((x) => !held.has(x.t) && !(x.s.cls === 'us' && heldRows.some((h) => h.cls === 'us' && En.sameCompany(h, x.s)))
    && !(guard && Rk.valueGuarded(x.s, x.s.cls)));
  const kept = [];
  for (const x of rows) if (!(x.s.cls === 'us' && kept.some((k) => k.s.cls === 'us' && En.sameCompany(k.s, x.s)))) kept.push(x);
  rows = kept;
  const groups = new Set();
  for (const r of E.editRows(deck, draft)) { const g = E.groupOf(r, load.byT); if (r.pct > 0 && g && g !== E.CUSHION) groups.add(g); }
  if (chip === 'newInd') rows = rows.filter((x) => En.hasGroup(x.s) && !groups.has(x.s.ind));
  if (chip === 'div') rows = rows.filter((x) => (x.s.cls === 'kr' ? (En.exactData() ? En.dytOf(x.s) : null) : En.okDy(x.s)) > 0);
  if (chip === 'lowVol') rows = rows.slice(0, Math.ceil(rows.length * 0.2)).map((x, i) => [x, i]).filter(([x]) => typeof x.s.vol === 'number')
    .sort((a, b) => a[0].s.vol - b[0].s.vol || a[1] - b[1]).map(([x]) => x);
  return { ts: rows.slice(0, 20).map((x) => x.t), survivors: all.length };
};
const got = (load, deck, draft, chip) => F.chipRows(F.findList(load, deck, draft), chip).map((r) => r.t);
"""

VISIBLE = """En.DECKS.filter((d) => !d.hidden)"""


def _acceptance(dir_):
    return run(f"""
      const load = loadDir({json.dumps(dir_)});
      const res = [];
      for (const d of {VISIBLE}) {{
        const settings = {{ points: d.points, strict: d.strict || 'normal', mix: d.mix || 'k73', exclude: {{}} }};
        // held: the list's own top three (so they must be taken out), one stock that is not a survivor, and one US stock
        const free = expected(load, {{ holdings: [], settings }}, E.emptyDraft(), 'all').ts;
        const us = load.data.stocks.find((s) => s.cls === 'us' && En.inUniverse(s) && !free.slice(0, 3).includes(s.t));
        const ts = [...free.slice(0, 3), '005930', ...(us ? [us.t] : [])].filter((t, i, a) => a.indexOf(t) === i && load.byT.has(t));
        const deck = deckOf(load, ts, settings, ts.slice(0, 2));
        // a pending 담기 (the 4th of the free list) and a pending 빼기 (the first holding) wait in the draft
        const draft = {{ ...E.emptyDraft(), adds: free[3] ? [{{ t: free[3], nk: load.byT.get(free[3]).nk, cls: load.byT.get(free[3]).cls, ind: null, kind: 'pinned', s: load.byT.get(free[3]) }}] : [],
          removed: [{{ t: ts[0], reason: 'better' }}] }};
        for (const chip of F.FIND_CHIPS) {{
          const want = expected(load, deck, draft, chip), have = got(load, deck, draft, chip);
          res.push({{ deck: d.id, chip, n: have.length, same: JSON.stringify(want.ts) === JSON.stringify(have), heldIn: have.filter((t) => ts.includes(t) || (draft.adds[0] && draft.adds[0].t === t)),
            survivors: want.survivors, want: want.ts.slice(0, 5), have: have.slice(0, 5) }});
        }}
        // the exclude switches and strictness: a deck with every live 빼기 switch on
        const strictDeck = deckOf(load, ts, {{ ...settings, exclude: {{ loss: true, debt: true, noDiv: true, holding: true }}, strict: 'strict' }});
        const w2 = expected(load, strictDeck, E.emptyDraft(), 'all'), h2 = got(load, strictDeck, E.emptyDraft(), 'all');
        res.push({{ deck: d.id + '+exclude', chip: 'all', n: h2.length, same: JSON.stringify(w2.ts) === JSON.stringify(h2), heldIn: h2.filter((t) => ts.includes(t)), survivors: w2.survivors }});
      }}
      // the dropped rows on this data, said in the console by find.js (no row leaves silently)
      const list = F.findList(load, deckOf(load, ['005930'], {{ points: {{ value: 3, div: 2 }}, strict: 'normal', mix: 'k73', exclude: {{}} }}), E.emptyDraft());
      out = {{ res, dropped: list.dropped, rows: list.rows.length, exact: En.exactData() }};""")


def test_acceptance_2_finder_matches_screen_without_held_stocks_on_the_fixture():
    got = _acceptance(FIX)
    for r in got["res"]:
        assert r["same"] is True, r
        assert r["heldIn"] == [], r                       # 가진 종목 · 기다리는 담기는 목록에 없어요
    assert sum(r["n"] for r in got["res"]) > 100           # 비어 있는 비교가 아니에요
    assert any(r["chip"] == "lowVol" and r["n"] > 0 for r in got["res"]) and any(r["chip"] == "newInd" and r["n"] > 0 for r in got["res"])


@pytest.mark.skipif(not REAL, reason="BAEPSAE_FIND_DATA (발행 파일 폴더) 가 없어요: 진짜 데이터 확인은 그 폴더를 주고 돌려요")
def test_acceptance_2_finder_matches_screen_without_held_stocks_on_real_data():
    got = _acceptance(REAL)
    print(json.dumps({"dropped": got["dropped"], "rows": got["rows"], "exact": got["exact"],
                      "per": [(r["deck"], r["chip"], r["n"], r["survivors"]) for r in got["res"]]}, ensure_ascii=False))
    assert got["exact"] is True
    for r in got["res"]:
        assert r["same"] is True and r["heldIn"] == [], r
    full = [r for r in got["res"] if r["chip"] == "all" and r["survivors"] > 30]
    assert len(full) >= 8 and all(r["n"] == 20 for r in full), full      # screen() 이 30개 넘게 남기면 20줄이 차요 (엄격한 템플릿은 그보다 적어요)
    for chip in ("newInd", "lowVol", "div"):
        assert any(r["chip"] == chip and r["n"] == 20 for r in got["res"]), chip


def test_the_finder_needs_points_and_reads_the_saved_settings():
    got = run("""const load = loadDir(%s);
      const none = deckOf(load, ['005930'], { points: {} });
      const pendOnly = deckOf(load, ['005930'], { points: { divGrowth: 5, payout: 3 } });     // only 준비 중 cards: no live points
      const ok = deckOf(load, ['005930'], { points: { value: 3 } });
      const noEx = { ...ok, settings: { points: { value: 3 } } };                          // an older portfolio: no exclude, strict, mix
      out = { none: F.findSettings(none), pend: F.findSettings(pendOnly), ok: F.findSettings(ok), noEx: F.findSettings(noEx), listNone: F.findList(load, none, E.emptyDraft()),
        n: F.chipRows(F.findList(load, noEx, E.emptyDraft()), 'all').length };""" % json.dumps(FIX))
    assert got["none"] is None and got["pend"] is None and got["listNone"] is None
    assert got["ok"]["points"] == {"value": 3} and got["ok"]["pinned"] == [] and got["ok"]["exclude"] == {}
    assert got["noEx"]["exclude"] == {} and "strict" not in got["noEx"] and "mix" not in got["noEx"] and got["n"] == 20


def test_each_chip_is_what_the_spec_says():
    got = run("""const load = loadDir(%s);
      const deck = deckOf(load, ['005930', '005380', 'AAPL'], { points: { value: 3, div: 2 }, strict: 'normal', mix: 'k73' });
      const list = F.findList(load, deck, E.emptyDraft());
      const groups = F.heldGroups(deck, E.emptyDraft(), load.byT);
      const rows = (c) => F.chipRows(list, c);
      const lv = rows('lowVol'), top = list.rows.slice(0, Math.ceil(list.rows.length * 0.2)).map((r) => r.t);
      out = { groups: [...groups].sort(), ranks: rows('all').map((r) => r.rank),
        newInd: rows('newInd').every((r) => r.newInd && En.hasGroup(r.s) && !groups.has(r.s.ind)), newIndN: rows('newInd').length,
        tagged: list.rows.filter((r) => r.newInd).length === list.rows.filter((r) => En.hasGroup(r.s) && !groups.has(r.s.ind)).length,
        lv: lv.map((r) => r.s.vol), lvIn: lv.every((r) => top.includes(r.t)), lvN: lv.length, top: top.length,
        div: rows('div').every((r) => F.paysDividend(r.s)), divN: rows('div').length,
        pct: list.rows.every((r) => r.pct == null || (r.pct >= 1 && r.pct <= 100)), pctNum: list.rows.filter((r) => r.pct != null).length, n: list.rows.length };""" % json.dumps(FIX))
    assert got["groups"] == ["auto", "elec", "semi"], got["groups"]
    assert got["ranks"] == list(range(1, 21))
    assert got["newInd"] is True and got["tagged"] is True and got["newIndN"] > 0
    assert got["lv"] == sorted(got["lv"]) and got["lvIn"] is True and got["lvN"] == min(20, got["top"])
    assert got["div"] is True and got["divN"] > 0
    assert got["pct"] is True and got["pctNum"] == got["n"]          # 목록의 종목은 모두 점수를 매길 수 있어요 (screen() 을 지난 종목)


def test_blank_vol_and_blank_or_unverified_yields_are_left_out_never_read_as_0():
    got = run("""const load = loadDir(%s);
      const deck = deckOf(load, ['005930'], { points: { value: 3 }, strict: 'loose', mix: 'kr' });
      const base = F.findList(load, deck, E.emptyDraft());
      const first = base.rows.slice(0, 5).map((r) => r.t);
      // blank the first five's vol and the yield of the payers among them (a fresh copy of the data: findList keeps one list per file)
      const stocks = load.data.stocks.map((s) => (first.includes(s.t) ? { ...s, vol: null, dyt: null, dy: null } : s));
      const L2 = { ...load, data: { ...load.data, stocks }, byT: new Map(stocks.map((s) => [s.t, s])) };
      const list = F.findList(L2, deck, E.emptyDraft());
      out = { lv: F.chipRows(list, 'lowVol').map((r) => r.t).filter((t) => first.includes(t)), dv: F.chipRows(list, 'div').map((r) => r.t).filter((t) => first.includes(t)),
        all: F.chipRows(list, 'all').slice(0, 5).map((r) => r.t), first,
        us: F.paysDividend({ cls: 'us', dy: null }), us0: F.paysDividend({ cls: 'us', dy: 0 }), etf: F.paysDividend({ cls: 'etf', dy: 3 }) };""" % json.dumps(FIX))
    assert got["lv"] == [] and got["dv"] == []
    assert got["us"] is False and got["us0"] is False and got["etf"] is False


def test_pending_adds_and_removals_and_a_held_companys_other_share_class_stay_out():
    got = run("""const load = loadDir(%s);
      const settings = { points: { profit: 3, large: 2 }, strict: 'loose', mix: 'us' };
      const free = F.findList(load, deckOf(load, ['AAPL'], settings), E.emptyDraft()).rows.map((r) => r.t);
      const goog = ['GOOG', 'GOOGL'].filter((t) => free.includes(t));
      // hold GOOGL: GOOG (the same company) is not offered either
      const deck = deckOf(load, ['GOOGL', 'AAPL'], settings);
      const l2 = F.findList(load, deck, E.emptyDraft()).rows.map((r) => r.t);
      const add = load.byT.get(free.find((t) => !['GOOG', 'GOOGL', 'AAPL'].includes(t)));
      const draft = { ...E.emptyDraft(), adds: [{ t: add.t, nk: add.nk, cls: 'us', ind: null, kind: 'pinned', s: add }], removed: [{ t: 'AAPL', reason: null }] };
      const l3 = F.findList(load, deck, draft).rows.map((r) => r.t);
      out = { goog, both: free.filter((t) => t === 'GOOG' || t === 'GOOGL'), l2: l2.filter((t) => t === 'GOOG' || t === 'GOOGL'), add: add.t, l3add: l3.includes(add.t), l3aapl: l3.includes('AAPL') };""" % json.dumps(FIX))
    assert len(got["both"]) == 1                     # one company, one row (the better-placed class)
    assert got["l2"] == []                           # GOOGL held: GOOG is the same company
    assert got["l3add"] is False and got["l3aapl"] is False


def test_compare_verdict_variants_blank_and_equal_facts_and_particles():
    got = run("""
      const v = (a, b) => F.verdictOf(a, b).kind;
      const kinds = { both: v({ pct: 60, vol: 40 }, { pct: 4, vol: 19 }), fitBig: v({ pct: 60, vol: 20 }, { pct: 4, vol: 30 }),
        lessSmall: v({ pct: 4, vol: 40 }, { pct: 60, vol: 20 }), worse: v({ pct: 4, vol: 20 }, { pct: 60, vol: 40 }),
        fit: v({ pct: 60, vol: null }, { pct: 4, vol: 19 }), less: v({ pct: 4, vol: 30 }, { pct: 60, vol: null }),
        small: v({ pct: null, vol: 40 }, { pct: 4, vol: 19 }), big: v({ pct: 4, vol: 20 }, { pct: null, vol: 40 }),
        none: v({ pct: null, vol: null }, { pct: 4, vol: 19 }), eqFit: v({ pct: 4, vol: 40 }, { pct: 4, vol: 19 }),
        eqVol: v({ pct: 60, vol: 19.04 }, { pct: 4, vol: 18.96 }), eqBoth: v({ pct: 4, vol: 19 }, { pct: 4, vol: 19 }) };
      const texts = Object.fromEntries(['both', 'fitBig', 'lessSmall', 'worse', 'fit', 'less', 'small', 'big'].flatMap((k) =>
        [[k + ':한결화학', Cm.verdictText(k, '한결화학')], [k + ':솔담정밀', Cm.verdictText(k, '솔담정밀')], [k + ':Apple Inc.', Cm.verdictText(k, 'Apple Inc.')]]));
      out = { kinds, texts, nul: Cm.verdictText(null, 'x'), swap: [Cm.swapLabel('솔담정밀'), Cm.swapLabel('삼성전자'), Cm.swapLabel('LS ELECTRIC')],
        note: Cm.swapNoteText('솔담정밀', '한결화학', '13'), note2: Cm.swapNoteText('솔담정밀', '삼성전자', '13') };""")
    k = got["kinds"]
    assert k == {"both": "both", "fitBig": "fitBig", "lessSmall": "lessSmall", "worse": "worse", "fit": "fit", "less": "less", "small": "small",
                 "big": "big", "none": None, "eqFit": "small", "eqVol": "fit", "eqBoth": None}, k
    t = got["texts"]
    # Appendix 1, word for word, particles after the last syllable (한결화학: 학 → 이 · 은; 솔담정밀: 밀 → 이 · 은; Apple Inc.: C → 가 · 는)
    assert t["both:한결화학"] == "한결화학이 내 기준에 더 잘 맞고, 지난 1년 주가 변동이 더 작았어요."
    assert t["both:Apple Inc."] == "Apple Inc.가 내 기준에 더 잘 맞고, 지난 1년 주가 변동이 더 작았어요."
    assert t["fitBig:한결화학"] == "한결화학이 내 기준에 더 잘 맞지만, 지난 1년 주가 변동은 더 컸어요."
    assert t["lessSmall:솔담정밀"] == "솔담정밀은 내 기준에 덜 맞지만, 지난 1년 주가 변동은 더 작았어요."
    assert t["lessSmall:Apple Inc."] == "Apple Inc.는 내 기준에 덜 맞지만, 지난 1년 주가 변동은 더 작았어요."
    assert t["worse:솔담정밀"] == "솔담정밀은 내 기준에 덜 맞고, 지난 1년 주가 변동도 더 컸어요."
    assert t["fit:한결화학"] == "한결화학이 내 기준에 더 잘 맞아요." and t["less:한결화학"] == "한결화학은 내 기준에 덜 맞아요."
    assert t["small:Apple Inc."] == "지난 1년 주가 변동은 Apple Inc.가 더 작았어요." and t["big:한결화학"] == "지난 1년 주가 변동은 한결화학이 더 컸어요."
    assert got["nul"] is None
    assert got["swap"] == ["솔담정밀과 바꾸기", "삼성전자와 바꾸기", "LS ELECTRIC과 바꾸기"]
    assert got["note"] == "바꾸면 한결화학이 솔담정밀의 목표 비중(13%)을 이어받아요." and got["note2"] == "바꾸면 삼성전자가 솔담정밀의 목표 비중(13%)을 이어받아요."
    for v in t.values():
        assert "수익" not in v and "벌" not in v                # 판정은 수익을 말하지 않아요


def test_default_holding_the_after_line_and_the_swap_rows():
    got = run("""
      const rows = [{ t: 'A' }, { t: 'B' }, { t: 'C' }];
      const pct = { A: 10, B: 62, C: null };
      const d1 = F.defaultHolding(rows, (t) => pct[t], (t) => t === 'C');
      const d2 = F.defaultHolding(rows, (t) => pct[t], () => false);
      const d3 = F.defaultHolding(rows, () => null, () => false);
      // the board: 반도체 38 (25 + 13) · 금융 25 · 전력 25 · 음식료 12 → swap the 13%% 반도체 holding for 화학
      const before = [{ key: 'semi', name: '반도체', pct: 38 }, { key: 'fin', name: '금융', pct: 25 }, { key: 'util', name: '전력·유틸리티', pct: 25 }, { key: 'food', name: '음식료', pct: 12 }];
      const after = [{ key: 'semi', name: '반도체', pct: 25 }, { key: 'fin', name: '금융', pct: 25 }, { key: 'util', name: '전력·유틸리티', pct: 25 }, { key: 'chem', name: '화학', pct: 13 }, { key: 'food', name: '음식료', pct: 12 }];
      const same = F.afterChange(before, before);
      const cush = F.afterChange([{ key: 'cushion', name: null, cushion: true, pct: 30 }, { key: 'semi', name: '반도체', pct: 70 }], [{ key: 'semi', name: '반도체', pct: 100 }]);
      out = { d1, d2, d3, ch: F.afterChange(before, after), same, cush, line: C.cmp.afterLine };""")
    assert got["d1"] == "C" and got["d2"] == "B" and got["d3"] == "A"
    assert got["ch"] == {"key": "semi", "name": "반도체", "a": 38, "b": 25, "n": 4, "m": 5}            # 보드: 반도체 38% → 25% · 업종 4개 → 5개
    assert got["same"] is None
    assert got["cush"]["key"] == "semi" and got["cush"]["n"] == 1 and got["cush"]["m"] == 1           # 안전자산은 업종이 아니에요


SWAP = r"""
const CODES = ['000010', '000020', '000030', '000040', '000050'];
const stock = (t, price = 100000, more = {}) => ({ t, nk: '종목', cls: 'kr', price, ind: 'semi', indName: '반도체', ...more });
const deck5 = (n = 5, w = 0.2, cap = 50, extra = {}) => ({ id: 'd1', name: '시험 포트폴리오', createdAt: '2026-10-01', planFx: 1300,
  settings: { points: { value: 3 }, maxPct: cap, amountMan: 1000 },
  holdings: CODES.slice(0, n).map((t, i) => ({ t, nk: '종목' + (i + 1), cls: 'kr', ind: 'semi', kind: 'core', target: w, setAt: '2026-10-01',
    plannedQty: Math.round(w * 1e7 / 100000), planPx: 100000, rules: [pend('audit'), ...band(w)] })),
  purchases: CODES.slice(0, n).map((t, i) => ({ id: 'p' + i + 'aaaaaa', t, qty: Math.round(w * 1e7 / 100000), price: 100000, date: '2026-10-01', ccy: 'KRW' })), ...extra });
const cand = (price = 50000) => ({ t: '005930', nk: '삼성전자', cls: 'kr', ind: 'chem', kind: 'pinned', s: { t: '005930', nk: '삼성전자', cls: 'kr', price, ind: 'chem', indName: '화학' } });
const load = { status: 'ok', data: { fx: 1400, stocks: [] }, coByT: new Map(), byT: new Map() };
const sellAll = (data, t, qty) => { const de = data.decks[0];
  const c = Rc.checkSale(de, t, { qty: String(qty), price: '110000', date: T }, stock(t, 110000), { today: T, fx: 1400 });
  if (!c.ok) throw new Error('sale ' + c.why);
  return Rc.withRecord(data, 'd1', 'sales', c.rec, T); };
const sumT = (de) => Math.round(de.holdings.reduce((x, h) => x + h.target, 0) * 1e9) / 1e9;
const noId = (cs) => (cs || []).map(({ id, ...c }) => c);
"""


def test_a_swap_waiting_for_save_gives_the_candidate_the_holdings_target():
    got = run(SWAP + """
      const d = deck5(5, 0.2);
      const dr = E.swapDraft(d, E.emptyDraft(), '000030', 'better', cand());
      const rows = E.editRows(d, dr);
      const saved = E.applyEdit({ v: 2, decks: [d] }, 'd1', dr, { load, today: T, ts: 1762900000000 });
      const de = saved.data.decks[0];
      const c = de.holdings.find((h) => h.t === '005930');
      // the last stock can be swapped (a swap keeps the number of stocks)
      const one = deck5(1, 1, 100);
      const dr1 = E.swapDraft(one, E.emptyDraft(), '000010', 'better', cand());
      const s1 = E.applyEdit({ v: 2, decks: [one] }, 'd1', dr1, { load, today: T, ts: 1762900000000 });
      out = { pcts: rows.map((r) => [r.t, r.pct]), removed: dr.removed, pending: E.pending(d, dr), ok: saved.ok,
        overs: Object.keys(E.swapDraft(d, { ...E.emptyDraft(), over: { '000030': 20 } }, '000030', 'better', cand()).over).sort(), sum: sumT(de), held: de.holdings.map((h) => h.t),
        c: { target: c.target, kind: c.kind, setAt: c.setAt, planPx: c.planPx, plannedQty: c.plannedQty, band: c.rules.find((r) => r.id === 'band').target },
        others: de.holdings.filter((h) => h.t !== '005930').map((h) => h.target), changes: noId(de.changes), history: (de.history || []).map((x) => [x.t, x.reason]),
        valid: S.validStore(saved.data, T), one: s1.ok && s1.data.decks[0].holdings.map((h) => [h.t, h.target]),
        twice: E.swapDraft(d, dr, '000040', 'better', cand()) === dr, notStored: E.swapDraft(d, E.addDraft(d, E.emptyDraft(), cand(), 10), '005930', 'better', cand()) };""")
    assert got["pcts"] == [["000010", 20], ["000020", 20], ["000040", 20], ["000050", 20], ["005930", 20]]
    assert got["removed"] == [{"t": "000030", "reason": "better"}] and got["pending"] is True
    assert got["overs"] == ["005930"]                                  # the holding's own target goes with it (only the candidate's is set)
    assert got["ok"] is True and got["sum"] == 1 and got["valid"] is True
    assert got["held"] == ["000010", "000020", "000040", "000050", "005930"]
    assert got["c"] == {"target": 0.2, "kind": "pinned", "setAt": "2026-11-12", "planPx": 50000, "plannedQty": 40, "band": 0.2}
    assert got["others"] == [0.2] * 4
    assert got["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000030", "nk": "종목3", "reason": "better"},
                              {"at": "2026-11-12", "kind": "add", "t": "005930", "nk": "삼성전자"}]
    assert got["history"] == []                                      # bought only, never sold: no records to keep (v19.6 A.3), the reason is in the change
    assert got["one"] == [["005930", 1]]
    assert got["twice"] is True                                     # the candidate is already waiting: nothing changes


def test_a_swap_with_a_sale_saves_the_sale_the_removal_and_the_add_in_one_write():
    got = run(SWAP + """
      const d = deck5(5, 0.2);
      const data = { v: 2, decks: [d] };
      const after = sellAll(data, '000020', 20);
      const r = E.sellAndSwap(after, 'd1', '000020', cand(), { reason: 'better', raise: null, load, today: T, ts: 1762900000000 });
      const de = r.data.decks[0];
      const partial = E.sellAndSwap(sellAll(data, '000020', 5), 'd1', '000020', cand(), { reason: 'better', raise: null, load, today: T, ts: 1 });
      const dup = E.sellAndSwap(after, 'd1', '000020', { ...cand(), t: '000030' }, { reason: 'better', raise: null, load, today: T, ts: 1 });
      // the last stock, held: swapped with its sale
      const one = deck5(1, 1, 100);
      const r1 = E.sellAndSwap(sellAll({ v: 2, decks: [one] }, '000010', 100), 'd1', '000010', cand(), { reason: 'better', raise: null, load, today: T, ts: 1 });
      out = { ok: r.ok, valid: S.validStore(r.data, T), sum: sumT(de), held: de.holdings.map((h) => [h.t, h.target]), changes: noId(de.changes),
        hist: de.history.map((x) => [x.t, x.reason, (x.sales || []).length]), partial, dup, one: r1.ok && r1.data.decks[0].holdings.map((h) => [h.t, h.target]),
        planw: de.holdings.every((h) => typeof h.planW === 'number' && h.planW >= 0), untouched: de.holdings.filter((h) => h.t !== '005930').every((h, i) => h.planPx === 100000) };""")
    assert got["ok"] is True and got["valid"] is True and got["sum"] == 1
    assert got["held"] == [["000010", 0.2], ["000030", 0.2], ["000040", 0.2], ["000050", 0.2], ["005930", 0.2]]
    assert got["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000020", "nk": "종목2", "reason": "better"},
                              {"at": "2026-11-12", "kind": "add", "t": "005930", "nk": "삼성전자"}]
    assert got["hist"] == [["000020", "better", 1]]
    assert got["partial"] == {"ok": False, "why": "partial"} and got["dup"] == {"ok": False, "why": "gone"}
    assert got["one"] == [["005930", 1]]
    assert got["planw"] is True and got["untouched"] is True


def test_a_holding_saved_above_the_cap_gives_the_candidate_the_cap_and_the_rest_shared_out():
    got = run(SWAP + """
      // a 15% 채권·금 cushion under a 10% cap (v19.7a's dcush shape): seven at 10%, two cushions at 15%
      const hs = [...CODES, '000060', '000070'].map((t, i) => ({ t, nk: '종목' + i, cls: 'kr', ind: 'semi', kind: 'core', target: 0.1, setAt: '2026-10-01', plannedQty: 10, planPx: 100000, rules: band(0.1) }));
      const d = { id: 'd1', name: 'c', createdAt: '2026-10-01', planFx: 1300, settings: { points: { value: 3 }, maxPct: 10, amountMan: 1000 }, purchases: [],
        holdings: [...hs, { t: '114260', nk: '채권', cls: 'bond', kind: 'cushion', target: 0.15, plannedQty: 10, planPx: 100000, rules: band(0.15) },
          { t: '132030', nk: '금', cls: 'metal', kind: 'cushion', target: 0.15, plannedQty: 10, planPx: 100000, rules: band(0.15) }] };
      const dr = E.swapDraft(d, E.emptyDraft(), '114260', 'better', cand());
      const rows = E.editRows(d, dr);
      const chk = E.swapCheck(d, E.emptyDraft(), '114260', cand());
      out = { cand: rows.find((r) => r.t === '005930').pct, sum: E.sumPct(rows), d2: E.d2Of(rows, 10), chk: { pct: chk.pct, low: chk.low, y: chk.y } };""")
    assert got["cand"] == 10                                          # 15% → the cap (10%)
    assert got["d2"]["low"] is True and got["chk"] == {"pct": 10, "low": True, "y": 12}      # 7 × 10 + 10 + 15 < 100: D2 (100 ÷ 9 → 12)


# review B1 · S4 · S5: a holding saved above the cap (a 30% 채권·금 cushion under a 20% cap). The candidate gets the cap; the 10%
# left goes to the holdings with room (the two at 15%), on both paths, and the compare screen shows exactly that write.
CUSH = SWAP + r"""
const cushDeck = (heldA = false) => { const d = deck5(5, 0.2, 20);
  const w = { '000010': 0.3, '000020': 0.2, '000030': 0.2, '000040': 0.15, '000050': 0.15 };
  d.holdings = d.holdings.map((h) => ({ ...h, target: w[h.t], kind: h.t === '000010' ? 'cushion' : 'core', rules: [pend('audit'), ...band(w[h.t])] }));
  d.purchases = heldA ? d.purchases.filter((p) => p.t === '000010') : [];
  return d; };
const pcts = (rows) => Object.fromEntries(rows.map((r) => [r.t, Math.round(r.pct * 1000) / 1000]));
"""


def test_a_swap_never_gives_the_candidate_more_than_the_cap_on_either_path_and_the_screen_shows_that_write():
    got = run(CUSH + """
      const d = cushDeck(false), dh = cushDeck(true);
      const dr = E.swapDraft(d, E.emptyDraft(), '000010', 'better', cand());
      const vDraft = E.swapView(d, E.emptyDraft(), '000010', cand());
      const vSale = E.swapView(dh, E.emptyDraft(), '000010', cand());
      const r = E.sellAndSwap(sellAll({ v: 2, decks: [dh] }, '000010', 20), 'd1', '000010', cand(), { reason: 'better', raise: null, load, today: T, ts: 1 });
      const written = r.ok ? Object.fromEntries(r.data.decks[0].holdings.map((h) => [h.t, Math.round(h.target * 100000) / 1000])) : r;
      out = { groups: [...F.heldGroups(d, E.emptyDraft(), new Map())], draft: pcts(E.editRows(d, dr)), view: { path: vDraft.path, pct: vDraft.pct, rows: pcts(vDraft.rows) },
        sale: { path: vSale.path, pct: vSale.pct, rows: pcts(vSale.rows) }, written, sum: r.ok ? sumT(r.data.decks[0]) : null };""")
    want = {"000020": 20, "000030": 20, "000040": 20, "000050": 20, "005930": 20}
    assert got["groups"] == ["semi"]                                     # a 채권·금 cushion is no industry (없는 업종 · 새 업종)
    assert got["draft"] == want                                          # the cap, and the 10% left shared out (100%)
    assert got["view"] == {"path": "draft", "pct": 20, "rows": want}     # what the screen shows = what waits for 바꾼 내용 저장
    assert got["sale"] == {"path": "sale", "pct": 20, "rows": want}      # what the screen shows = what 팔고 빼기 writes
    assert got["written"] == want and got["sum"] == 1


def test_a_swap_with_a_sale_that_cannot_reach_100_under_the_cap_is_refused_until_the_raise_which_is_saved():
    got = run(SWAP + """
      // v19.7a's dcush shape: seven at 10% under a 10% cap and two 15% cushions; the first cushion is held
      const ts = ['000010', '000020', '000030', '000040', '000050', '000060', '000070'];
      const hs = ts.map((t, i) => ({ t, nk: '종목' + i, cls: 'kr', ind: 'semi', kind: 'core', target: 0.1, setAt: '2026-10-01', plannedQty: 10, planPx: 100000, rules: band(0.1) }));
      const d = { id: 'd1', name: 'c', createdAt: '2026-10-01', planFx: 1300, settings: { points: { value: 3 }, maxPct: 10, amountMan: 1000 },
        purchases: [{ id: 'p1aaaaaa', t: '114260', qty: 10, price: 100000, date: '2026-10-01', ccy: 'KRW' }],
        holdings: [...hs, { t: '114260', nk: '채권', cls: 'bond', kind: 'cushion', target: 0.15, plannedQty: 10, planPx: 100000, rules: band(0.15) },
          { t: '132030', nk: '금', cls: 'metal', kind: 'cushion', target: 0.15, plannedQty: 10, planPx: 100000, rules: band(0.15) }] };
      const after = sellAll({ v: 2, decks: [d] }, '114260', 10);
      const chk = E.swapCheck(d, E.emptyDraft(), '114260', cand());
      const no = E.sellAndSwap(after, 'd1', '114260', cand(), { reason: 'better', raise: null, load, today: T, ts: 1 });
      const yes = E.sellAndSwap(after, 'd1', '114260', cand(), { reason: 'better', raise: chk.y, load, today: T, ts: 1 });
      const de = yes.ok ? yes.data.decks[0] : null;
      // round-2 review SF2: what 두 종목 비교 shows is the write the sheet's raise makes (the only one 팔고 빼기 can make here)
      const view = E.swapView(d, E.emptyDraft(), '114260', cand());
      const r1000 = (x) => Math.round(x * 1000) / 1000;
      out = { chk: { low: chk.low, y: chk.y, pct: chk.pct, n: chk.n, names: chk.names.length, cand: chk.names.includes('삼성전자') }, no, ok: yes.ok,
        max: de && de.settings.maxPct, sum: de && sumT(de),
        cand: de && de.holdings.find((h) => h.t === '005930').target, top: de && Math.max(...de.holdings.filter((h) => h.kind !== 'cushion').map((h) => h.target)),
        view: { path: view.path, raised: view.raised, cap: view.cap, pct: view.pct, from: view.from },
        same: de && JSON.stringify(Object.fromEntries(view.rows.map((r) => [r.t, r1000(r.pct)]))) === JSON.stringify(Object.fromEntries(de.holdings.map((h) => [h.t, r1000(h.target * 100)]))) };""")
    assert {k: got["chk"][k] for k in ("low", "y", "pct")} == {"low": True, "y": 12, "pct": 10}     # 7 × 10 + 10 + 15 = 95 < 100: D2 first (100 ÷ 9 → 12)
    assert got["no"] == {"ok": False, "why": "sum"}                    # never a write that does not add up to 100%
    assert got["ok"] is True and got["max"] == 12 and got["sum"] == 1 and got["cand"] == 0.12 and got["top"] <= 0.12
    assert got["chk"]["n"] == got["chk"]["names"] == 9 and got["chk"]["cand"] is True    # "종목이 9개뿐이라" beside the same 9 names
    assert got["view"] == {"path": "sale", "raised": True, "cap": 12, "pct": 12, "from": 15}
    assert got["same"] is True                                          # the bar and the note show exactly what is written


def test_a_swap_never_takes_a_candidate_that_is_stored_even_when_its_removal_waits():
    got = run(SWAP + """
      const d = deck5(5, 0.2);
      const dr = E.removeDraft(d, E.emptyDraft(), '000040', null);            // 000040 waits to be taken out: not in the edited list
      const stored = { ...cand(), t: '000040', nk: '종목4' };
      out = { same: E.swapDraft(d, dr, '000030', 'better', stored) === dr, view: E.swapView(d, dr, '000030', stored) };""")
    assert got["same"] is True and got["view"] is None


def test_a_korean_stock_whose_verified_yield_is_0_is_not_a_payer_on_an_exact_file():
    """The fixture made exact (a divCheck, dyt on every Korean payer, as v19.1b's files): 배당 주는 종목 keeps only dyt above 0."""
    got = run("""const L0 = loadDir(%s);
      const stocks = L0.data.stocks.map((s) => ({ ...s }));
      const data = { ...L0.data, stocks, divCheck: { v: 1 } };
      En.setDataShape(data);
      const load = { ...L0, data, byT: new Map(stocks.map((s) => [s.t, s])) };
      const deck = deckOf(load, ['005930'], { points: { value: 3 }, strict: 'loose', mix: 'kr' });
      const kr = F.findList(load, deck, E.emptyDraft()).rows.slice(0, 12).map((r) => r.s);
      kr.forEach((s, i) => { s.dps = i < 4 ? 0 : 500; s.dyt = i < 4 ? 0 : 2.5; });           // the first four pay nothing (dyt 0)
      const rows = F.chipRows(F.findList(load, { ...deck, id: 'd2' }, E.emptyDraft()), 'div').map((r) => r.t);
      out = { zero: kr.slice(0, 4).map((s) => s.t).filter((t) => rows.includes(t)), paying: kr.slice(4).map((s) => s.t).filter((t) => rows.includes(t)).length, exact: En.exactData() };""" % json.dumps(FIX))
    assert got["exact"] is True and got["zero"] == [] and got["paying"] == 8


def test_the_short_beta_form_is_used_only_under_its_own_benchmark():
    """review S3: once Jack approves "평균 {lo}~{hi}%" (cmp.p.beta), a cell drops its benchmark only when it is the row label's: a US
    stock under "코스피 1% →" keeps the whole "S&P 500 1% → 평균 …". Until then every cell shows the company page's tile text."""
    got = run("""const load = loadDir(%s);
      const names = E.indNames(load.data.stocks);
      const kr = { ...load.byT.get('005930'), beta: 1.25, betaSE: 0.05 }, us = { ...load.data.stocks.find((s) => s.cls === 'us' && typeof s.beta === 'number'), beta: 0.9, betaSE: 0.05 };
      En.setDataShape({ divCheck: { v: 1 } });
      const ctx = { stocks: load.data.stocks, points: { value: 3 }, names, load, groups: null, row: null };
      const b = (s, short) => Cm.compareCells(s, null, { ...ctx, betaShort: short }).beta.text;
      const before = [b(kr, true), b(us, false)];
      C.cmp.p.beta = '평균 {lo}~{hi}%%';
      out = { before, krShort: b(kr, true), usUnderKospi: b(us, false), usUnderSp: b(us, true), band: C.co.tiles.riskBand };""" % json.dumps(FIX))
    assert got["before"] == [got["band"]["kr"].replace("{lo}", "1.2").replace("{hi}", "1.4"), got["band"]["us"].replace("{lo}", "0.8").replace("{hi}", "1.0")]
    assert got["krShort"] == "평균 1.2~1.4%"
    assert got["usUnderKospi"] == got["band"]["us"].replace("{lo}", "0.8").replace("{hi}", "1.0")        # its own benchmark, whole
    assert got["usUnderSp"] == "평균 0.8~1.0%"


def test_the_swap_note_never_says_the_candidate_takes_a_target_it_does_not_get():
    """round-2 review SF1: "…{a}의 목표 비중({x}%)을 이어받아요." only when the candidate takes the holding's whole target; capped, the
    capped line (P5) waits for Jack and nothing stands in for it, the approved cap line says why where it is true (not while the cap is
    a raise still to be tapped); the sale sentence only on the sale path."""
    got = run("""
      const N = (sv) => Cm.swapNoteParts(sv, '솔담정밀', '한화');
      const plain = N({ path: 'sale', pct: 20, from: 20, cap: 20, raised: false });
      const capped = N({ path: 'draft', pct: 10, from: 15, cap: 10, raised: false });
      const raised = N({ path: 'sale', pct: 12, from: 15, cap: 12, raised: true });
      C.cmp.p.swapNoteCap = '바꾸면 {b}이 {a}의 목표 비중 {y}% 중 {x}%만 이어받아요.';
      C.cmp.p.swapNoteCapGa = '바꾸면 {b}가 {a}의 목표 비중 {y}% 중 {x}%만 이어받아요.';
      const p5 = N({ path: 'draft', pct: 10, from: 15, cap: 10, raised: false });
      out = { plain, capped, raised, p5, none: N(null), max: C.edit.max, note: C.cmp.swapNote, sale: C.cmp.swapSale };""")
    assert got["plain"] == {"first": "바꾸면 한화가 솔담정밀의 목표 비중(20%)을 이어받아요.", "cap": None, "sale": got["sale"], "capped": False}
    assert got["capped"] == {"first": None, "cap": got["max"].replace("{x}", "10"), "sale": None, "capped": True}
    assert got["raised"] == {"first": None, "cap": None, "sale": got["sale"], "capped": True}
    assert got["p5"]["first"] == "바꾸면 한화가 솔담정밀의 목표 비중 15% 중 10%만 이어받아요."      # once Jack approves P5 (한화: 가)
    assert got["none"] == {"first": None, "cap": None, "sale": None, "capped": False}


def test_points_are_saved_to_the_portfolio_and_nothing_else_changes():
    got = run(SWAP + """
      const d = deck5(3, 1 / 3);
      const d0 = { ...d, settings: { maxPct: 50, amountMan: 1000, points: {} } };
      const r = E.withPoints({ v: 2, decks: [d0] }, 'd1', { value: 2, div: 3 }, 'strict', T);
      const de = r.data.decks[0];
      const { settings: a, ...restA } = de, { settings: b, ...restB } = d0;
      out = { ok: r.ok, settings: de.settings, same: JSON.stringify(restA) === JSON.stringify(restB), gone: E.withPoints({ v: 2, decks: [d0] }, 'zz', { value: 1 }, null, T) };""")
    assert got["ok"] is True and got["settings"] == {"maxPct": 50, "amountMan": 1000, "points": {"value": 2, "div": 3}, "strict": "strict"}
    assert got["same"] is True and got["gone"] == {"ok": False, "why": "gone"}


def test_compare_cells_follow_the_company_pages_blank_rules():
    got = run("""const load = loadDir(%s);
      const C2 = C;
      const names = E.indNames(load.data.stocks);
      const base = load.byT.get('005930');
      const ctx = { stocks: load.data.stocks, points: { value: 3, div: 2 }, names, load, groups: new Set(['semi']), row: null };
      const cells = (s, co = null) => { const c = Cm.compareCells(s, co, ctx); return Object.fromEntries(Cm.ROWS.map((k) => [k, [c[k].text, c[k].note]])); };
      const us = load.data.stocks.find((s) => s.cls === 'us' && typeof s.pbr === 'number' && s.pbr > 0);
      out = {
        plain: cells(base, load.coByT.get('005930')),
        gone: cells(null),
        px: cells({ ...base, vol: null, beta: null, betaSE: null, pxBad: '2026-05-08', pxBadF: ['vol', 'beta', 'betaSE', 'lz'] }),
        pxFull: cells({ ...base, vol: null, beta: null, pxBad: '2026-05-08', pxBadF: ['hi', 'lo', 'vol', 'beta', 'betaSE'] }),
        fgn: cells({ ...us, pbr: null, dy: null, fgnCut: { pbr: 'mismatch', dy: 'mismatch' } }),
        pbr0: cells({ ...us, pbr: null, pbrZero: true }),
        fgnKinds: cells({ ...us, pbr: null, dy: null, fgnCut: { pbr: 'nocompare-own', dy: 'stopped' } }),
        pref: cells({ ...base, t: '005935', nk: '삼성전자우', pbr: null }),
        usNew: cells(us).ind, kr: cells(base).ind,
        copy: { na: C2.co.tiles.na, pxOne: C2.co.pxBadOne, px: C2.co.pxBad, fgn: C2.co.fgnCut, fgnOwn: C2.co.fgnNoCmp, fgnStop: C2.co.fgnStopped, pbr0: C2.co.pbrZero, pref: C2.co.fit.pref, prefCo: C2.co.pref, newInd: C2.find.newInd },
        usInd: [us.ind, load.byT.get(us.t).indName] };
      // a file with the split check (exact data): a Korean payer whose yield the pipeline left blank because its share count changed
      // with no filing to explain it (dvLine 1) says so; one blank for another reason gets no line
      En.setDataShape({ divCheck: { v: 1 } });
      out.dv = cells({ ...base, dps: 361, dyt: null, dvLine: 1, dvWhy: 'nc-unexplained' }).dy;
      out.dvOther = cells({ ...base, dps: 361, dyt: null }).dy;
      out.dvOk = cells({ ...base, dps: 361, dyt: 0.62, dps3a: [361, 361, 361], divSt: 'same' }).dy;
      out.shareHidden = C2.co.div.shareHidden;""" % json.dumps(FIX))
    cp = got["copy"]
    p = got["plain"]
    assert p["fit"][0].startswith("상위 ") and p["vol"][0].startswith("연 변동성 ") and p["pbr"][0].endswith("배") and p["dy"][0].endswith("%")
    assert all(v == ["–", None] for k, v in got["gone"].items() if k not in ("fit", "ind")), got["gone"]
    assert got["px"]["vol"] == ["–", cp["pxOne"]] and got["px"]["beta"] == ["–", cp["pxOne"]]
    assert got["pxFull"]["vol"] == ["–", cp["px"]] and got["pxFull"]["beta"] == ["–", cp["px"]]
    assert got["fgn"]["pbr"] == ["–", cp["fgn"]] and got["fgn"]["dy"] == ["–", cp["fgn"]]
    assert got["pbr0"]["pbr"] == ["–", cp["pbr0"]]
    assert got["fgnKinds"]["pbr"] == ["–", cp["fgnOwn"]] and got["fgnKinds"]["dy"] == ["–", cp["fgnStop"]]     # #133: each kind its own line
    assert got["pref"]["fit"] == ["–", cp["pref"]] and got["pref"]["pbr"] == [cp["na"], cp["prefCo"]]
    assert got["usNew"][0] == f"미국 · {got['usInd'][1]} · {cp['newInd']}" and not got["kr"][0].endswith(cp["newInd"])   # 반도체 is held: not new
    assert got["dv"] == ["\u2013", got["shareHidden"]] and got["dvOther"] == ["\u2013", None] and got["dvOk"] == ["0.6%", None], (got["dv"], got["dvOther"], got["dvOk"])
    for k, v in got["plain"].items():
        assert v[0] and "NaN" not in v[0] and "undefined" not in v[0], (k, v)


def test_the_finder_and_compare_addresses():
    got = run("""out = Object.fromEntries(['#portfolio/edit/d1/find', '#portfolio/edit/d1/compare/005930', '#portfolio/edit/d1/compare/BRK-B',
      '#portfolio/edit/d1/compare/', '#portfolio/edit/d1/compare/a%20b', '#portfolio/edit/d1/find/x', '#portfolio/edit/d 1/find', '#portfolio/edit/d1/x'].map((h) => [h, Rt.parseHash(h)]));
      out.subs = [Rt.editSub('d1'), Rt.editSub('d1', 'find'), Rt.editSub('d1', 'compare', 'BRK.B')];""")
    assert got["#portfolio/edit/d1/find"] == {"tab": "portfolio", "sub": "edit/d1/find", "about": False, "known": True, "edit": "d1", "eview": "find"}
    assert got["#portfolio/edit/d1/compare/005930"] == {"tab": "portfolio", "sub": "edit/d1/compare/005930", "about": False, "known": True, "edit": "d1",
                                                        "eview": "compare", "ecode": "005930"}
    assert got["#portfolio/edit/d1/compare/BRK-B"]["ecode"] == "BRK-B"
    for h in ("#portfolio/edit/d1/compare/", "#portfolio/edit/d1/compare/a%20b", "#portfolio/edit/d1/find/x", "#portfolio/edit/d 1/find", "#portfolio/edit/d1/x"):
        assert got[h]["known"] is False and "edit" not in got[h], h
    assert got["subs"] == ["edit/d1", "edit/d1/find", "edit/d1/compare/BRK.B"]


def test_one_function_gives_the_one_number():
    """[B3] one function computes 상위 {x}%: fitpct.js is ranks.js criteriaPct itself (v19.5b is merged)."""
    with open(os.path.join(ROOT, "src", "v2", "fitpct.js"), encoding="utf-8") as fh:
        src = fh.read()
    code = [l for l in src.splitlines() if l.strip() and not l.strip().startswith("//")]
    assert code == ['export { criteriaPct } from "./ranks.js";']
    for f in ("find.js", "compare.jsx"):
        with open(os.path.join(ROOT, "src", "v2", f), encoding="utf-8") as fh:
            body = fh.read()
        assert "criteriaPct" in body and "percentileScores" not in body, f


NEW_FILES = ["src/v2/find.js", "src/v2/finder.jsx", "src/v2/compare.jsx", "src/v2/editparts.jsx"]
HEX = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_])")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(", re.I)
NAMED = re.compile(r"""["'`](?:white|black|red|blue|green|gray|grey|silver|navy|orange|yellow|purple|transparent|currentcolor)["'`]""", re.I)


@pytest.mark.parametrize("path", NEW_FILES)
def test_no_literal_colour_in_new_v197b_files(path):
    """Jack, 2026-11-13: new screens use the shared colour tokens only (dark mode, v19.6d, then covers them)."""
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, os.path.join(ROOT, path), "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    hits = HEX.findall(r.stdout) + FUNC.findall(r.stdout) + NAMED.findall(r.stdout)
    assert not hits, f"{path}: 색을 직접 썼어요 {hits[:5]} (src/ui/tokens.js 의 토큰으로)"


APPROVED = {
    "edit.byCrit": "내 기준으로 찾기", "edit.byCritSub": "기준 점수로 고른 순서",
    "find.title": "내 기준으로 찾기", "find.sub": "이 포트폴리오에 준 기준 점수로 고른 순서예요. 아직 담지 않은 종목만 보여 드려요.",
    "find.card": "이 포트폴리오의 기준", "find.noPoints": "이 포트폴리오에는 기준 점수가 없어요. 찾기 전에 기준을 골라 주세요.",
    "find.chips.all": "전체", "find.chips.newInd": "없는 업종", "find.chips.lowVol": "주가 변동 작은 순", "find.chips.div": "배당 주는 종목",
    "find.row": "{industry} · 연 변동성 {vol}%", "find.newInd": "새 업종", "find.compare": "비교", "find.add": "+ 담기",
    "find.newIndLine": "지금 포트폴리오에 없는 업종의 종목만 보여 드려요.", "find.empty": "이 조건에 맞는 종목이 없어요.",
    "find.emptyNewInd": "지금 포트폴리오에 없는 업종에서는 고를 종목이 없어요.",
    "cmp.title": "두 종목 비교", "cmp.held": "가진 종목", "cmp.cand": "후보", "cmp.picker": "어떤 종목과 비교할까요?",
    "cmp.rows.fit": "내 기준", "cmp.rows.ind": "업종", "cmp.rows.vol": "주가 변동 (지난 1년)", "cmp.rows.beta": "코스피 1% →", "cmp.rows.pbr": "PBR",
    "cmp.rows.dy": "배당수익률", "cmp.rows.growth": "오늘 주가가 가정하는 성장", "cmp.rows.warn": "재무 경고 신호",
    "cmp.after": "바꾸면 업종 비중", "cmp.afterLine": "{group} {a}% → {b}% · 업종 {n}개 → {m}개", "cmp.addOnly": "{b}만 담기",
    "cmp.swap": "{a}과 바꾸기", "cmp.swapWa": "{a}와 바꾸기", "cmp.swapNote": "바꾸면 {b}이 {a}의 목표 비중({x}%)을 이어받아요.",
    "cmp.swapNoteGa": "바꾸면 {b}가 {a}의 목표 비중({x}%)을 이어받아요.", "cmp.swapSale": "판 내용은 다음 화면에서 기록해요.",
}
SPEC = "docs/tasks/v19.7-portfolio-edit.md"


def test_every_shipped_line_is_appendix_1_word_for_word_and_recorded():
    import copytrace as CT
    _, flat = CT.copy_strings()
    vals = dict(flat)
    chat = CT.chat_approved()
    with open(os.path.join(ROOT, SPEC), encoding="utf-8") as fh:
        appendix = fh.read().split("## Appendix 1", 1)[1]
    for key, text in APPROVED.items():
        assert vals.get(key) == text, key
        assert chat.get(key) == text or not CT.HANGUL.search(text), key      # recorded in docs/tasks/v18.3-approved-in-chat.md (PBR has no Korean)
    verdicts = {k: v for k, v in vals.items() if k.startswith("cmp.verdict.")}
    assert len(verdicts) == 16
    for k, v in verdicts.items():
        assert chat.get(k) == v, k
        # the Appendix line with its particle chosen: "{b}이/가" → 이 or 가, "{b}은/는" → 은 or 는
        both = v.replace("{b}이 ", "{b}이/가 ").replace("{b}가 ", "{b}이/가 ").replace("{b}은 ", "{b}은/는 ").replace("{b}는 ", "{b}은/는 ")
        assert both in appendix or both.replace("지난 1년 주가 변동은 {b}이/가 더 컸어요.", "…더 컸어요.") in appendix, (k, both)
    # the three proposals wait (null, listed in the pending doc); the screen shows approved text meanwhile
    for k in ("find.p.savePoints", "cmp.p.beta", "cmp.p.betaOne"):
        assert k in vals and vals[k] is None, k
