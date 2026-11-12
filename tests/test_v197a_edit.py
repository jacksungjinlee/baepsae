# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.7a 종목 바꾸기 · 빼기 · 담기 (src/v2/edit.js · store.js 의 changes · history reason) — Node 에서 돌려봐요.

docs/tasks/v19.7-portfolio-edit.md Parts A–C, Store and rules, Test changes (adds only):
- 목표 비중: 합계를 100%로 맞추기는 방금 바꾼 종목을 그대로 두고 나머지를 비율대로 (정수 %, 합계 정확히 100). 한 종목 최대 비중
  (settings.maxPct) 을 넘기지 않고, 이미 넘은 종목(채권·금)은 더 올리지 않아요. 저장은 100% 일 때만
- [B1]/[C3] 25% → 10%: 같은 날 바로 걸려요. 바뀐 종목만 plannedQty 를 자기 planPx 로 다시 계산하고 비중 규칙을 새로 만들어요.
  나머지 종목의 규칙 · plannedQty · planPx 는 한 글자도 안 바뀌어요 (예전처럼 plannedQty 를 두면 안 걸려요: 그 버그)
- [D2] 4종목 × 20% → 줄과 y = 25, 저장 꺼짐 → 버튼 → 25% 씩, 저장 켜짐, planPx 그대로 · 5 × 20 은 줄 없음 · 팔고 빼기는 판 기록 ·
  빼기 · maxPct 25 · 합계 100% 를 한 번에
- 담기: 빌드 단계와 같은 규칙(rulesFor), planPx = 오늘 종가, plannedQty 는 목표 비중으로, setAt 오늘
- 빼기: 판 기록 · 배당 기록이 있으면 history 로 (이유와 함께), 바꾼 기록(changes), 마지막 한 종목은 못 빼요
- 저장 기록: changes 는 검사하고(200개까지), 두 창이 합칠 때 둘 다 남고, 내보내기 → 불러오기 그대로, 예전 앱(v19.6a · main)도
  읽고 그대로 다시 써요 (모르는 칸을 버리지 않아요)
- 내 기준 상위 {x}%: v19.5b 의 criteriaPct 와 같은 숫자 (fitpct.js 는 그 함수를 그대로 옮긴 것)
- 새 파일은 색을 직접 쓰지 않아요 (Jack, 2026-11-13; tests/test_v196a_colours.py 와 같은 검사)
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
FIX = os.path.join(ROOT, "tests", "fixtures")
# Committed copies (no test may depend on git history: CI checks out shallow), each with a header line saying where it came from:
OLD6 = os.path.join(FIX, "old_client_v196a", "store.js")    # v19.6a (claude/v19.6a-records 0d749bc): the app a tab may still run when v19.7a ships
OLDM = os.path.join(FIX, "old_client_7b5c895", "store.js")  # main when v19.6a branched (v19.3d2)
RANKS = os.path.join(FIX, "v195b_ranks", "ranks.js")         # v19.5b (claude/v19.5b-rankings 94eea80): ranks.js criteriaPct


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-edit-")
        entry = os.path.join(tmp, "entry.js")
        with open(RANKS, encoding="utf-8") as fh:
            ranks = fh.read()
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("H", "held.js"), ("E", "edit.js"), ("Rc", "records.js"), ("Ru", "rules.js"), ("Dc", "deckcalc.js"),
                              ("F", "fitpct.js"), ("Rt", "routes.js"), ("En", "engine.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export * as Old6 from {json.dumps(OLD6)};\nexport * as OldM from {json.dumps(OLDM)};\n")
            # v19.5b's ranks.js, its imports pointed at this checkout's modules (engine · track · warn are the same files)
            src = re.sub(r'from "\./([a-z0-9]+\.js)"', lambda m: "from " + json.dumps(os.path.join(ROOT, "src", "v2", m.group(1))), ranks)
            with open(os.path.join(tmp, "ranks.js"), "w", encoding="utf-8") as fh:
                fh.write(src)
            f.write(f"export * as Rk from {json.dumps(os.path.join(tmp, 'ranks.js'))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/edit.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, H, E, Rc, Ru, Dc, F, Rt, En, Old6, OldM, Rk } from './edit.mjs';\n" + FAKE + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
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
const K = 'baepsae2.v1', T = '2026-11-12';
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const pend = (id) => ({ id, kind: 'sell', check: 'pending' });
// four Korean holdings at 25%, bought as planned (1,000만원 at 100,000원 a share: 25 shares each), prices unchanged today
const CODES = ['000010', '000020', '000030', '000040', '000050', '000060', '000070', '000080', '000090', '000100'];
const deck4 = (extra = {}, n = 4, w = 0.25, maxPct = 50) => ({ id: 'd1', name: '시험 포트폴리오', createdAt: '2026-10-01', planFx: 1300,
  settings: { points: { value: 3 }, maxPct, amountMan: 1000 },
  holdings: CODES.slice(0, n).map((t, i) => ({ t, nk: '종목' + (i + 1), cls: 'kr', ind: 'semi', kind: 'core', target: w, setAt: '2026-10-01',
    plannedQty: Math.round(w * 1e7 / 100000), planPx: 100000, rules: [pend('audit'), ...band(w)] })),
  purchases: CODES.slice(0, n).map((t, i) => ({ id: 'p' + i + 'aaaaaa', t, qty: Math.round(w * 1e7 / 100000), price: 100000, date: '2026-10-01', ccy: 'KRW' })),
  ...extra });
const stock = (t, price = 100000, more = {}) => ({ t, nk: '종목', cls: 'kr', price, ind: 'semi', indName: '반도체', ...more });
const ctxOf = (prices = {}) => ({ state: { ok: true }, byT: new Map(CODES.map((t) => [t, stock(t, prices[t] || 100000)])), coByT: new Map(), fx: 1400, pxDate: T });
const load = { status: 'ok', data: { fx: 1400, stocks: [] }, coByT: new Map(), byT: new Map() };
const env = { load, today: T, ts: 1762900000000 };
const sumT = (de) => Math.round(de.holdings.reduce((x, h) => x + h.target, 0) * 1e9) / 1e9;
const tgts = (de) => de.holdings.map((h) => [h.t, h.target, h.plannedQty ?? null, (h.rules.find((r) => r.id === 'band') || {}).target ?? null]);
// a deck whose targets are not all equal (30 / 25 / 20 / 15 / 10): a share-out has to be in proportion, and its rounding has
// to go by the largest remainder
const uneq = (cap = 50) => { const d = deck4({}, 5, 0.2, cap); const w = [0.3, 0.25, 0.2, 0.15, 0.1];
  return { ...d, holdings: d.holdings.map((h, i) => ({ ...h, target: w[i], plannedQty: Math.round(w[i] * 100), rules: [pend('audit'), ...band(w[i])] })),
    purchases: d.purchases.map((p, i) => ({ ...p, qty: Math.round(w[i] * 100) })) }; };
const sam = (price = 50000) => ({ t: '005930', nk: '삼성전자', cls: 'kr', price, ind: 'semi', indName: '반도체' });
const addSam = (price) => ({ t: '005930', nk: '삼성전자', cls: 'kr', ind: 'semi', kind: 'pinned', s: sam(price) });
const sellAll = (data, t, qty, opts = {}) => { const de = data.decks[0];
  const c = Rc.checkSale(de, t, { qty: String(qty), price: '110000', date: T }, stock(t, 110000), { today: T, fx: 1400 });
  if (!c.ok) throw new Error('sale ' + c.why);
  return Rc.withRecord(data, 'd1', 'sales', c.rec, T); };
const noId = (cs) => (cs || []).map(({ id, ...c }) => c);
const ids = (cs) => (cs || []).every((c) => typeof c.id === 'string' && /^[a-z0-9]{8,32}$/.test(c.id));
const bandOf = (de, t) => { const x = de.holdings.find((y) => y.t === t); const r = x.rules.find((y) => y.id === 'band'); return { status: x.status, bands: r.bands, target: r.target }; };
"""


def test_fix_keeps_the_one_just_changed_and_shares_the_rest_in_whole_percents():
    got = run("""const d = deck4({}, 5, 0.2, 30);
      let dr = E.stepDraft(E.emptyDraft(), '000010', 25);
      const before = E.sumPct(E.editRows(d, dr));
      dr = E.fixDraft(d, dr);
      const rows = E.editRows(d, dr);
      // cap: 30% max, one stepped to 30 then the fix may not push anyone past 30
      let dc = E.fixDraft(d, E.stepDraft(E.emptyDraft(), '000010', 5));
      out = { before, pcts: rows.map((r) => r.pct), sum: E.sumPct(rows), ok: E.sumOk(E.sumPct(rows)),
        capped: E.editRows(d, dc).map((r) => r.pct), shown: E.sumShown(99.6), shown2: E.sumShown(100.0000001), shown3: E.sumShown(99.9994), shown4: E.sumShown(99.9996) };""")
    assert got["before"] == 105                                                                # 25 + 20 × 4
    assert got["pcts"] == [25, 19, 19, 19, 18] and got["sum"] == 100 and got["ok"] is True     # 75 ÷ 4 = 18.75 → 19 19 19 18 (정수, 합계 100)
    assert got["capped"] == [5, 24, 24, 24, 23] and sum(got["capped"]) == 100                  # 95 ÷ 4 = 23.75, 30 아래
    assert got["shown"] == {"n": 99.6, "d": 1} and got["shown2"] == {"n": 100, "d": 0}         # 100 으로 읽히지 않게 소수점
    assert got["shown3"] == {"n": 99.999, "d": 3} and got["shown4"] == {"n": 100, "d": 0}       # 0.0005%p 안은 100 (계획의 소수 목표)


def test_the_cap_is_never_crossed_and_a_holding_above_it_is_never_pushed_higher():
    got = run("""// a 채권·금 cushion at 30% with a 20% cap, four others; one removed: the share-out never raises the cushion and nobody passes 20
      const d = deck4({}, 5, 0.175, 20);
      d.holdings[4] = { ...d.holdings[4], kind: 'cushion', target: 0.3, rules: band(0.3) };
      const dr = E.removeDraft(d, E.emptyDraft(), '000010', 'thesis');
      const rows = E.editRows(d, dr);
      out = { pcts: rows.map((r) => [r.t, r.pct]), sum: E.sumPct(rows), up: E.stepped(rows, '000050', 1, 20), upOther: E.stepped(rows, '000020', 1, 20),
        removed: dr.removed };""")
    pcts = dict(got["pcts"])
    assert pcts["000050"] == 30 and all(pcts[t] <= 20 for t in ("000020", "000030", "000040"))
    assert got["sum"] == 90                                                                     # 3 × 20 + 30: the cap leaves the sum short (D2 says so)
    assert got["up"] is None and got["upOther"] is None and got["removed"] == [{"t": "000010", "reason": "thesis"}]


def test_25_to_10_is_flagged_the_same_day_and_the_other_bands_do_not_change():
    """[B1] corrected by [C3]: cut A from 25% to 10% (B up to 40%) while A sits at 25%."""
    got = run("""const d = deck4();
      const ctx = ctxOf();
      const before = Ru.evaluateDeck(d, ctx);
      const dr = E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 10), '000020', 40);
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', dr, env);
      const nd = r.data.decks[0];
      const after = Ru.evaluateDeck(nd, ctx);
      // the old way (the bug): the band rule follows the new target but plannedQty stays: the plan's gap hides the drift
      const oldWay = { ...d, holdings: d.holdings.map((h) => h.t === '000010' ? { ...h, target: 0.1, rules: [pend('audit'), ...band(0.1)] }
        : h.t === '000020' ? { ...h, target: 0.4, rules: [pend('audit'), ...band(0.4)] } : h) };
      const old = Ru.evaluateDeck(oldWay, ctx);
      const same = (t) => JSON.stringify(d.holdings.find((h) => h.t === t)) === JSON.stringify(nd.holdings.find((h) => h.t === t));
      out = { ok: r.ok, a: bandOf(after, '000010'), aBefore: bandOf(before, '000010'), oldA: bandOf(old, '000010'),
        c: [bandOf(before, '000030'), bandOf(after, '000030')], dd: [bandOf(before, '000040'), bandOf(after, '000040')],
        sameC: same('000030'), sameD: same('000040'), hA: nd.holdings[0], hB: nd.holdings[1],
        valid: S.validStore(r.data, T), changes: noId(nd.changes), ids: ids(nd.changes) };""")
    assert got["ok"] is True and got["valid"] is True and got["ids"] is True
    assert got["aBefore"]["status"] == "none"
    assert got["a"]["status"] == "trim", got["a"]                                              # 같은 날 바로: 25% 가 10% 목표의 1.4배를 넘어요
    assert got["oldA"]["status"] == "none"                                                     # plannedQty 를 그대로 두면 안 걸려요 (그 버그)
    assert got["c"][0] == got["c"][1] and got["dd"][0] == got["dd"][1]                        # 다른 종목의 오늘 기준선은 그대로
    assert got["sameC"] and got["sameD"]                                                       # 저장된 규칙 · plannedQty · planPx 도 그대로
    a, b = got["hA"], got["hB"]
    assert a["planPx"] == 100000 and a["plannedQty"] == 10 and a["target"] == 0.1              # 자기 planPx 로 다시 계산
    assert b["planPx"] == 100000 and b["plannedQty"] == 40
    assert [r["id"] for r in a["rules"]] == ["audit", "band"] and a["rules"][0] == {"id": "audit", "kind": "sell", "check": "pending"}
    assert a["rules"][1]["target"] == 0.1 and [round(x, 6) for x in a["rules"][1]["bands"]] == [0.075, 0.125, 0.14]
    assert got["changes"] == [{"at": "2026-11-12", "kind": "targets"}]


def test_d2_cap_below_100_line_button_and_one_write_for_sell_and_remove():
    got = run("""const d = deck4({}, 5, 0.2, 20);
      const base = { v: 1, decks: [d] };
      const five = E.capCheck(5, 20);
      // 기록 없이 빼기 (pending): four left at the 20% cap -> the line, y = 25, save refused
      let dr = E.removeDraft(d, E.emptyDraft(), '000050', null);
      const n = E.editRows(d, dr).length, chk = E.capCheck(n, E.capOf(d, dr));
      const refused = E.applyEdit(base, 'd1', dr, env);
      dr = E.raiseDraft(d, dr);
      const rows = E.editRows(d, dr);
      const saved = E.applyEdit(base, 'd1', dr, env);
      const nd = saved.data.decks[0];
      // 팔고 빼기 from five at 20%: the sale, the removal, maxPct 25 and targets summing to 100 in one store
      const sale = Rc.checkSale(d, '000010', { qty: '20', price: '110000', date: T }, stock('000010', 110000), { today: T, fx: 1400 });
      const afterSale = Rc.withRecord(base, 'd1', 'sales', sale.rec, T);
      const sr = E.sellAndRemove(afterSale, 'd1', '000010', { reason: 'better', raise: E.capCheck(4, 20).y, load, today: T, ts: env.ts });
      const sd = sr.data.decks[0];
      out = { five, chk, refused, rows: rows.map((r) => r.pct), maxPct: nd.settings.maxPct, planPx: nd.holdings.map((h) => h.planPx),
        planned: nd.holdings.map((h) => h.plannedQty), held: nd.holdings.map((h) => h.t), ys: [3, 4, 6, 7, 9, 1].map((k) => E.capCheck(k, 10).y),
        zero: E.capCheck(0, 20), exact: [E.capCheck(5, 20).low, E.capCheck(4, 25).low],
        sr: { ok: sr.ok, valid: S.validStore(sr.data, T), max: sd.settings.maxPct, targets: sd.holdings.map((h) => h.target), sales: sd.sales.length,
          hist: sd.history.map((e) => ({ t: e.t, reason: e.reason, out: e.out, sales: e.sales.length })), changes: noId(sd.changes), planPx: sd.holdings.map((h) => h.planPx) } };""")
    assert got["five"] == {"low": False, "y": 20}                                               # 5 × 20 = 100: 줄 없음
    assert got["chk"] == {"low": True, "y": 25}
    assert got["refused"] == {"ok": False, "why": "sum"}                                       # 합계 80%: 저장 꺼짐
    assert got["rows"] == [25, 25, 25, 25] and got["maxPct"] == 25
    assert got["planPx"] == [100000] * 4 and got["planned"] == [25] * 4 and got["held"] == ["000010", "000020", "000030", "000040"]
    assert got["ys"] == [34, 25, 17, 15, 12, 100] and got["zero"] == {"low": False, "y": None} and got["exact"] == [False, False]
    s = got["sr"]
    assert s["ok"] and s["valid"] and s["max"] == 25 and s["targets"] == [0.25] * 4 and s["planPx"] == [100000] * 4
    assert s["sales"] == 0 and s["hist"] == [{"t": "000010", "reason": "better", "out": "2026-11-12", "sales": 1}]   # 판 기록은 history 로
    assert s["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000010", "nk": "종목1", "reason": "better"}]   # 한 줄 (나눠 준 비중은 그 줄의 일부)


def test_add_takes_the_build_steps_rules_and_a_planned_qty_from_its_target():
    got = run("""const d = deck4({}, 4, 0.25, 30);
      const s = { t: '005930', nk: '삼성전자', cls: 'kr', price: 225000, ind: 'semi', indName: '반도체', dps: 1444, fy: 2025, debt: 30, roe: 9 };
      const add = { t: s.t, nk: s.nk, cls: 'kr', ind: 'semi', kind: 'core', s };
      const def = E.addDefault(4, 30);
      const dr = E.addDraft(d, E.emptyDraft(), add, def);
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', dr, env);
      const nd = r.data.decks[0], h = nd.holdings.find((x) => x.t === '005930');
      const want = Dc.rulesFor(load, { s, kind: 'pinned', targetW: 0.2 }, { points: d.settings.points });   // 꼭 담을 종목 (이름으로 고른 종목)
      // an ETF (no score) is added as 직접 추가 (kind pinned), and a US stock goes into a Korea-only portfolio
      const us = { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', ccy: 'USD', price: 270, ind: 'elec', indName: '전자부품' };
      const r2 = E.applyEdit({ v: 1, decks: [d] }, 'd1', E.addDraft(d, E.emptyDraft(), { t: 'AAPL', nk: us.nk, cls: 'us', ind: 'elec', kind: 'pinned', s: us }, 10), env);
      const hu = r2.data.decks[0].holdings.find((x) => x.t === 'AAPL');
      out = { def, pcts: E.editRows(d, dr).map((r) => r.pct), ok: r.ok, valid: S.validStore(r.data, T), h, rulesSame: JSON.stringify(h.rules) === JSON.stringify(want),
        others: nd.holdings.filter((x) => x.t !== '005930').map((x) => [x.target, x.plannedQty, x.planPx]), changes: noId(nd.changes), purchases: nd.purchases.length,
        us: { kind: hu.kind, planPx: hu.planPx, plannedQty: hu.plannedQty, cls: hu.cls }, unheld: Ru.evaluateDeck(nd, ctxOf()).unheld };""")
    assert got["def"] == 20 and got["pcts"] == [20, 20, 20, 20, 20]                              # 100 ÷ (4 + 1)
    assert got["ok"] and got["valid"] and got["rulesSame"]                                      # 빌드 단계의 rulesFor 그대로
    h = got["h"]
    assert h["planPx"] == 225000 and h["plannedQty"] == round(0.2 * 1e7 / 225000) and h["setAt"] == "2026-11-12" and h["kind"] == "pinned"
    assert h["target"] == 0.2 and h["ts"] == 1762900000000 and h["ind"] == "semi" and h["reasons"] == [{"code": "pinned"}] and h["cls"] == "kr"
    assert got["others"] == [[0.2, 20, 100000]] * 4                                             # 나머지는 비율대로, planPx 그대로
    assert got["purchases"] == 4 and got["unheld"] == ["005930"]                               # 산 기록 없이 담아요 (계획한 종목)
    assert got["changes"] == [{"at": "2026-11-12", "kind": "add", "t": "005930", "nk": "삼성전자"}]                # 한 줄 (나눠 준 비중은 그 줄의 일부)
    assert got["us"] == {"kind": "pinned", "planPx": 270, "plannedQty": round(0.1 * 1e7 / (270 * 1300)), "cls": "us"}   # 계획 환율로


def test_remove_with_and_without_records_reasons_change_log_and_the_last_holding():
    got = run("""const d = deck4({ sales: [{ id: 's1aaaaaa', t: '000020', qty: 5, price: 120000, date: '2026-11-01', ccy: 'KRW' }],
        divs: [{ id: 'v1aaaaaa', t: '000030', amount: 5000, ccy: 'KRW', date: '2026-11-02' }] });
      let dr = E.removeDraft(d, E.emptyDraft(), '000020', 'rule');      // 기록 없이 빼기: a sale -> history
      dr = E.removeDraft(d, dr, '000040', null);                        // no records: gone, no history entry
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', dr, env);
      const nd = r.data.decks[0];
      const one = deck4({}, 1, 1, 100);
      const last = E.removeDraft(one, E.emptyDraft(), '000010', 'other');
      out = { ok: r.ok, valid: S.validStore(r.data, T), held: nd.holdings.map((h) => [h.t, h.target]), hist: nd.history, sales: nd.sales, purchases: nd.purchases.map((p) => p.t),
        removed: nd.removed.map((m) => m.t), changes: noId(nd.changes), last: last === E.emptyDraft() ? 'same' : JSON.stringify(last), lastRows: E.editRows(one, last).length,
        list: E.changeList(nd).map((c) => c.kind) };""")
    assert got["ok"] and got["valid"]
    assert got["held"] == [["000010", 0.5], ["000030", 0.5]]                                    # 25 + 25 를 비율대로 나눠 50 · 50
    h = got["hist"]
    assert len(h) == 1 and h[0]["t"] == "000020" and h[0]["reason"] == "rule" and len(h[0]["sales"]) == 1 and len(h[0]["purchases"]) == 1
    assert got["sales"] == [] and got["purchases"] == ["000010", "000030"] and got["removed"] == ["000020", "000040"]
    assert got["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000020", "nk": "종목2", "reason": "rule"},
                              {"at": "2026-11-12", "kind": "remove", "t": "000040", "nk": "종목4"}]          # 빼기마다 한 줄, '목표 비중 바꿈' 따로 없음
    assert got["lastRows"] == 1 and json.loads(got["last"]) == {"over": {}, "adds": [], "removed": [], "maxPct": None, "last": None, "touched": False}   # 마지막 한 종목은 못 빼요
    assert got["list"] == ["remove", "remove"]                                                  # 화면은 최신부터


def test_nothing_waits_until_save_and_a_draft_follows_the_store_after_a_sale():
    got = run("""const d = deck4();
      const p0 = E.pending(d, E.emptyDraft());
      const same = E.pending(d, E.stepDraft(E.emptyDraft(), '000010', 25));
      const dr = E.stepDraft(E.emptyDraft(), '000030', 30);
      const gone = { ...d, holdings: d.holdings.filter((h) => h.t !== '000010') };
      const rb = E.rebaseDraft(gone, { ...dr, over: { ...dr.over, '000010': 12 }, last: '000010', removed: [{ t: '000010', reason: null }] });
      out = { p0, same, p1: E.pending(d, dr), rb, noop: E.applyEdit({ v: 1, decks: [d] }, 'd1', E.emptyDraft(), env).data.decks[0] === d ? 'same' : 'changed',
        gone: E.applyEdit({ v: 1, decks: [d] }, 'nope', dr, env) };""")
    assert got["p0"] is False and got["same"] is False and got["p1"] is True
    assert got["rb"] == {"over": {"000030": 30}, "adds": [], "removed": [], "maxPct": None, "last": None, "touched": True}
    assert got["gone"] == {"ok": False, "why": "gone"}


def test_store_checks_merges_and_round_trips_the_change_log_and_history_reasons():
    got = run("""const d = deck4({ changes: [{ at: '2026-11-10', kind: 'add', t: '000010', nk: '종목1' }],
        sales: [{ id: 's1aaaaaa', t: '000020', qty: 5, price: 120000, date: '2026-11-01', ccy: 'KRW' }] });
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', E.removeDraft(d, E.emptyDraft(), '000020', 'thesis'), env);
      const good = S.validStore(r.data, T);
      const bad = (c) => S.validStore({ v: 2, decks: [{ ...r.data.decks[0], changes: c }] }, T);
      const badHist = S.validStore({ v: 2, decks: [{ ...r.data.decks[0], history: r.data.decks[0].history.map((e) => ({ ...e, reason: 7 })) }] }, T);
      const many = Array.from({ length: 201 }, () => ({ at: '2026-11-10', kind: 'targets' }));
      // two tabs: each logged its own edit; the merge keeps both, oldest first, the newest 200 at most
      const a = { v: 2, decks: [{ ...r.data.decks[0], changes: [...r.data.decks[0].changes, { at: '2026-11-12', kind: 'targets' }] }] };
      const b = { v: 2, decks: [{ ...r.data.decks[0], changes: [{ at: '2026-11-09', kind: 'add', t: '000030', nk: '종목3' }, ...r.data.decks[0].changes] }] };
      const m = S.mergeTabs(b, a, T);
      const big = S.mergeTabs({ v: 2, decks: [{ ...d, changes: Array.from({ length: 150 }, (_, i) => ({ at: '2026-10-0' + (1 + (i % 9)), kind: 'targets', t: '000010' })) }] },
        { v: 2, decks: [{ ...d, changes: Array.from({ length: 150 }, (_, i) => ({ at: '2026-11-0' + (1 + (i % 9)), kind: 'targets', t: '000020' })) }] }, T);
      // 기록 내보내기 -> 기록 불러오기
      const file = S.exportText(r.data);
      const inc = S.parseImport(file, T);
      const back = S.mergeStores({ v: 1, decks: [] }, inc, env.ts, [], T);
      out = { good, futureAt: bad([{ at: '2026-11-13', kind: 'targets' }]), noKind: bad([{ at: T }]), badT: bad([{ at: T, kind: 'add', t: '삼성' }]),
        later: bad([{ at: T, kind: 'swap', reason: 'later' }]), notList: bad({}), tooMany: bad(many), badHist,
        merged: m && m.decks[0].changes.map((c) => c.at + ' ' + c.kind), bigN: big && big.decks[0].changes.length, bigOld: big && big.decks[0].changes.some((c) => c.t === '000010'),
        bigNov: big && big.decks[0].changes.filter((c) => c.t === '000020').length, bigOct: big && [...new Set(big.decks[0].changes.filter((c) => c.t === '000010').map((c) => c.at))].sort(),
        back: JSON.stringify(back.decks[0].changes) === JSON.stringify(r.data.decks[0].changes) && back.decks[0].history[0].reason === 'thesis',
        version: S.versionFor({ v: 1, decks: [{ ...deck4(), changes: [{ at: T, kind: 'targets' }] }] }) };""")
    assert got["good"] is True
    assert got["futureAt"] is False and got["noKind"] is False and got["badT"] is False and got["notList"] is False
    assert got["later"] is True                                                                  # 나중 판의 종류는 남겨 두고 보여 주지 않아요
    assert got["tooMany"] is True                                                                # 200개 넘는 기록(나중 판)도 따로 두지 않아요 (round-1 nit)
    assert got["badHist"] is False
    assert got["merged"] == ["2026-11-09 add", "2026-11-10 add", "2026-11-12 remove", "2026-11-12 targets"]
    assert got["bigN"] == 200 and got["bigOld"] is True                                          # 300 → 최신 200
    assert got["bigNov"] == 150 and got["bigOct"] == ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]   # 오래된 쪽이 빠져요
    assert got["back"] is True
    assert got["version"] == 1                                                                  # changes 만으로는 2판이 아니에요 (예전 앱도 읽어요)


@pytest.mark.parametrize("old", ["Old6", "OldM"])
def test_an_earlier_app_reads_and_writes_back_the_change_log_and_reasons(old):
    """v19.6a (this branch's base) and main (v19.3d2): neither knows changes or a history entry's reason. Each reads the store
    with nothing set aside, and its own write (a note) keeps both: the earlier apps keep a portfolio's fields they do not know."""
    got = run(f"""const d = deck4({{ sales: [{{ id: 's1aaaaaa', t: '000020', qty: 5, price: 120000, date: '2026-11-01', ccy: 'KRW' }}] }});
      const r = E.applyEdit({{ v: 1, decks: [d] }}, 'd1', E.removeDraft(d, E.emptyDraft(), '000020', 'thesis'), env);
      S.writeStore(r.data, K, T);
      const o = {old}.readStore(K, T);
      const wrote = {old}.writeStore({{ ...o.data, notes: {{ '000010': {{ text: '메모', at: T }} }} }}, K, T);
      const back = S.readStore(K, T);
      const x = back.data.decks[0];
      out = {{ locked: o.locked, problems: o.problems, wrote, changes: x.changes, reason: x.history[0].reason, note: !!(back.data.notes && back.data.notes['000010']),
        restored: back.restored }};""")
    assert got["locked"] is False and got["problems"] == [] and got["wrote"] is True
    assert [c["kind"] for c in got["changes"]] == ["remove"] and got["reason"] == "thesis" and got["note"] is True


def test_the_edit_address_names_one_portfolio():
    got = run("""out = Object.fromEntries(['#portfolio/edit/d1', '#portfolio/edit/d_1-x', '#portfolio/edit/', '#portfolio/edit/a b', '#portfolio/edit'].map((h) => [h, Rt.parseHash(h)]));""")
    assert got["#portfolio/edit/d1"] == {"tab": "portfolio", "sub": "edit/d1", "about": False, "known": True, "edit": "d1"}
    assert got["#portfolio/edit/d_1-x"]["edit"] == "d_1-x"
    for h in ("#portfolio/edit/", "#portfolio/edit/a b", "#portfolio/edit"):
        assert got[h]["known"] is False and "edit" not in got[h], h


def test_criteria_pct_is_v195b_s_one_number_per_stock():
    got = run("""{
        const fix = JSON.parse(require('fs').readFileSync(%s, 'utf8'));
        const res = {};
        for (const [mk, pts] of [['kr', { value: 3, div: 2 }], ['us', { profit: 2, lowVol: 1 }], ['kr', { stable: 1, growth: 3, trend: 2 }]]) {
          const a = F.criteriaPct(fix.stocks, mk, pts), b = Rk.criteriaPct(fix.stocks, mk, pts);
          res[mk + JSON.stringify(pts)] = { n: a.size, same: a.size === b.size && [...a].every(([t, v]) => b.get(t) === v), min: Math.min(...a.values()), max: Math.max(...a.values()) };
        }
        out = res; }""".replace("require('fs')", "(await import('fs'))") % json.dumps(os.path.join(ROOT, "tests", "fixtures", "v2", "data.json")))
    for k, v in got.items():
        assert v["n"] > 20 and v["same"] is True and v["min"] >= 1 and v["max"] <= 100, (k, v)


NEW_FILES = ["src/v2/editor.jsx", "src/v2/edit.js", "src/v2/fitpct.js"]
HEX = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_])")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(", re.I)
NAMED = re.compile(r"""["'`](?:white|black|red|blue|green|gray|grey|silver|navy|orange|yellow|purple|transparent|currentcolor)["'`]""", re.I)


@pytest.mark.parametrize("path", NEW_FILES)
def test_no_literal_colour_in_new_v197a_files(path):
    """Jack, 2026-11-13: new screens use the shared colour tokens only (dark mode, v19.6d, then covers them)."""
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, os.path.join(ROOT, path), "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    hits = HEX.findall(r.stdout) + FUNC.findall(r.stdout) + NAMED.findall(r.stdout)
    assert not hits, f"{path}: 색을 직접 썼어요 {hits[:5]} (src/ui/tokens.js 의 토큰으로)"


def test_a_removal_outside_the_edit_screen_is_logged_too():
    """v19.6a's 포트폴리오에서도 뺄까요? → 빼기 and the missing stock's 포트폴리오에서 빼기 take the stock out exactly as before
    (store.withoutHolding: records into history, a removal mark) and add one change-log line, without a reason."""
    got = run("""const d = deck4({ sales: [{ id: 's1aaaaaa', t: '000020', qty: 25, price: 120000, date: '2026-11-01', ccy: 'KRW' }] });
      const a = E.withRemoval({ v: 1, decks: [d] }, 'd1', '000020', T, env.ts);
      const b = S.withoutHolding({ v: 1, decks: [d] }, 'd1', '000020', T, env.ts);
      const { changes, ...rest } = a.decks[0];
      out = { changes: noId(changes), cid: ids(changes), same: JSON.stringify(rest) === JSON.stringify(b.decks[0]), valid: S.validStore(a, T), none: E.withRemoval({ v: 1, decks: [d] }, 'd1', 'XXXX', T, env.ts) };""")
    assert got["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000020", "nk": "종목2"}] and got["cid"] is True
    assert got["same"] is True and got["valid"] is True
    assert got["none"] is None


# ---------------- round-1 review fixes ----------------

def test_sell_and_remove_reads_the_stored_portfolio_not_the_draft():
    """[B1] 팔고 빼기 writes to the stored portfolio at once: the last-holding rule and D2 count the STORED holdings left after
    the sale (a pending 담기 row is not stored; a pending removal still is, but the edited list must keep a stock too)."""
    got = run("""// (a) one stored holding and a pending 담기: selling the stored one would leave the stored portfolio empty
      const one = deck4({}, 1, 1, 100);
      const dr1 = E.addDraft(one, E.emptyDraft(), addSam(), 50);
      const r1 = E.sellAndRemove(sellAll({ v: 1, decks: [one] }, '000010', 100), 'd1', '000010', { reason: null, raise: null, load, today: T, ts: env.ts });
      // (b) five at 20% under a 20% cap and a pending sixth (담기 at 10): four stored left -> D2 (4 x 20 = 80), never 80% saved
      const five = deck4({}, 5, 0.2, 20);
      const dr5 = E.addDraft(five, E.emptyDraft(), addSam(), 10);
      const after = sellAll({ v: 1, decks: [five] }, '000010', 20);
      const no = E.sellAndRemove(after, 'd1', '000010', { reason: 'better', raise: null, load, today: T, ts: env.ts });
      const yes = E.sellAndRemove(after, 'd1', '000010', { reason: 'better', raise: E.sellCheck(five, dr5, '000010').y, load, today: T, ts: env.ts });
      // (c) two stored, the other one waiting to be taken out (기록 없이 빼기): the edited list would be empty
      const two = deck4({}, 2, 0.5, 100);
      const dr2 = E.removeDraft(two, E.emptyDraft(), '000020', null);
      out = { sc1: E.sellCheck(one, dr1, '000010'), r1, rows1: E.editRows(one, dr1).length,
        sc5: E.sellCheck(five, dr5, '000010'), draftSum: E.sumPct(E.editRows(five, dr5)), no, yes: yes.ok && { valid: S.validStore(yes.data, T), sum: sumT(yes.data.decks[0]),
          max: yes.data.decks[0].settings.maxPct, held: yes.data.decks[0].holdings.map((h) => h.t), sales: yes.data.decks[0].history[0].sales.length },
        sc2: E.sellCheck(two, dr2, '000010'), sc2b: E.sellCheck(two, E.emptyDraft(), '000010') };""")
    assert got["rows1"] == 2 and got["sc1"]["last"] is True and got["sc1"]["n"] == 0             # 편집 목록은 2줄이어도 저장본에는 0개 남아요
    assert got["r1"] == {"ok": False, "why": "last"}
    s5 = got["sc5"]
    assert got["draftSum"] == 100 and s5["n"] == 4 and s5["low"] is True and s5["y"] == 25 and s5["last"] is False
    assert got["no"] == {"ok": False, "why": "sum"}                                              # 올리기 전에는 저장하지 않아요
    assert got["yes"] == {"valid": True, "sum": 1, "max": 25, "held": ["000020", "000030", "000040", "000050"], "sales": 1}
    assert got["sc2"]["last"] is True and got["sc2b"]["last"] is False and got["sc2b"]["n"] == 1


def test_sell_and_remove_refuses_a_partial_sale():
    """[B2] the 팔고 빼기 form locks the quantity to every held share (records.jsx lockQty); a sale of fewer shares, however it got
    there, never takes the stock out (the unsold shares would leave 내 수익)."""
    got = run("""const d = deck4();
      const after = sellAll({ v: 1, decks: [d] }, '000010', 10);
      const before = JSON.stringify(after);
      const r = E.sellAndRemove(after, 'd1', '000010', { reason: 'thesis', raise: null, load, today: T, ts: env.ts });
      out = { r, same: JSON.stringify(after) === before, held: E.heldShares(after.decks[0], '000010') };""")
    assert got["r"] == {"ok": False, "why": "partial"} and got["same"] is True and got["held"] == 15


def test_two_tabs_the_later_target_set_wins_whole():
    """[S1] each save that sets targets stamps targetsTs; when two copies merge, the later set (every holding's target,
    plannedQty and band rule, and settings.maxPct) wins whole, whichever copy wrote last. Holdings added or taken out follow
    their own merge rules (removal marks, history), so the sum stays the later edit's."""
    got = run("""const base = (cap = 50) => ({ v: 1, decks: [deck4({}, 4, 0.25, cap)] });
      const stale = (data) => ({ v: 2, decks: [{ ...data.decks[0], divs: [{ id: 'v1aaaaaa', t: '000030', amount: 5000, ccy: 'KRW', date: T }] }] });
      const both = (a, b) => [S.mergeTabs(a, b, T), S.mergeTabs(b, a, T)].map((m) => ({ sum: sumT(m.decks[0]), max: m.decks[0].settings.maxPct, t: tgts(m.decks[0]),
        divs: (m.decks[0].divs || []).length, valid: S.validStore(m, T), ts: m.decks[0].targetsTs ?? null }));
      // 120%: 담기 in tab A (5 x 20), tab B stale records a dividend
      const b0 = base(), d0 = b0.decks[0];
      const a1 = E.applyEdit(b0, 'd1', E.addDraft(d0, E.emptyDraft(), addSam(), 20), env).data;
      // 75%: 기록 없이 빼기 with the D2 raise in A (cap 30 -> 34)
      const b2 = base(30), d2 = b2.decks[0];
      const a2 = E.applyEdit(b2, 'd1', E.raiseDraft(d2, E.removeDraft(d2, E.emptyDraft(), '000040', 'thesis')), env).data;
      // reverted stepper: A moves 25 -> 10 and 25 -> 40
      const a3 = E.applyEdit(b0, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 10), '000020', 40), env).data;
      // both tabs edited: A (earlier) 10 / 40, B (later) 30 / 20: B's set, whichever wrote last
      const bLate = E.applyEdit(b0, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 30), '000020', 20), { ...env, ts: env.ts + 60000 }).data;
      out = { add: both(a1, stale(b0)), aAdd: tgts(a1.decks[0]), rm: both(a2, stale(b2)), aRm: tgts(a2.decks[0]), step: both(a3, stale(b0)), aStep: tgts(a3.decks[0]),
        late: both(a3, bLate), bLate: tgts(bLate.decks[0]) };""")
    for k, a in (("add", "aAdd"), ("rm", "aRm"), ("step", "aStep")):
        for m in got[k]:                                                                       # 두 순서 모두 (어느 창이 나중에 썼든)
            assert m["valid"] and m["sum"] == 1 and m["divs"] == 1 and m["ts"] == 1762900000000, (k, m)
            assert m["t"] == got[a], (k, m["t"], got[a])                                        # A 의 목표 · plannedQty · 비중 규칙 그대로
    assert [m["max"] for m in got["rm"]] == [34, 34] and len(got["add"][0]["t"]) == 5 and len(got["rm"][0]["t"]) == 3
    for m in got["late"]:
        assert m["t"] == got["bLate"] and m["ts"] == 1762900060000 and m["sum"] == 1


def test_two_tabs_with_an_earlier_app():
    """[S1] new x old. v19.6a and main do not know targetsTs: they keep the field (a portfolio's unknown fields ride along)
    but merge as before, the copy that wrote last leading. This app reading a copy an earlier app wrote: that copy has no
    later stamp, so the stamped set wins. What the earlier app itself does is pinned here so the PR can say it."""
    got = run("""const b0 = { v: 1, decks: [deck4()] }, d0 = b0.decks[0];
      const a = E.applyEdit(b0, 'd1', E.addDraft(d0, E.emptyDraft(), addSam(), 20), env).data;        // new app: 담기 (5 x 20)
      // an earlier app's tab, opened before the edit, writes a note: its copy has no stamp
      const oldCopy = { ...b0, notes: { '000010': { text: '메모', at: T } } };
      const res = {};
      for (const [name, M] of [['new', S], ['old6', Old6], ['oldm', OldM]]) {
        for (const [order, x, y] of [['oldLast', a, oldCopy], ['newLast', oldCopy, a]]) {
          const m = M.mergeTabs(x, y, T);
          res[name + ':' + order] = { sum: sumT(m.decks[0]), n: m.decks[0].holdings.length, ts: m.decks[0].targetsTs ?? null, valid: S.validStore(m, T), note: !!(m.notes && m.notes['000010']) };
        }
      }
      out = res;""")
    assert got["new:oldLast"] == got["new:newLast"] == {"sum": 1, "n": 5, "ts": 1762900000000, "valid": True, "note": True}
    for name in ("old6", "oldm"):
        assert got[name + ":newLast"]["sum"] == 1 and got[name + ":newLast"]["n"] == 5          # 새 앱 창이 나중에 썼으면 그대로
        old = got[name + ":oldLast"]
        assert old["n"] == 5 and old["sum"] == 1.2 and old["valid"] is True and old["ts"] == 1762900000000   # 예전 앱: 예전 그대로 (합계 120%, 기록은 다 남아요)


def test_minus_then_plus_returns_exactly_to_the_stored_target():
    """[S3] six stocks at 16.67% (1/6): each shows 16.7%, not 17%; − then + (and + then −) gives back exactly the stored value,
    so the sum is 100% again and nothing waits to be saved."""
    got = run("""const d = deck4({}, 6, 1 / 6, 50);
      const rows = E.editRows(d, E.emptyDraft());
      const st = E.storedPct(rows[0]);
      const down = E.stepped(rows, '000010', -1, 50, st);
      let dr = E.stepDraft(E.emptyDraft(), '000010', down);
      const back = E.stepped(E.editRows(d, dr), '000010', 1, 50, st);
      dr = E.stepDraft(dr, '000010', back);
      const up = E.stepped(rows, '000010', 1, 50, st);
      const upBack = E.stepped(E.editRows(d, E.stepDraft(E.emptyDraft(), '000010', up)), '000010', -1, 50, st);
      const w = deck4({}, 5, 0.2, 50), wr = E.editRows(w, E.emptyDraft());
      out = { shown: rows.map((r) => E.pctShown(r.pct)), down, back, exact: back === st, sum: E.sumPct(E.editRows(d, dr)), ok: E.sumOk(E.sumPct(E.editRows(d, dr))),
        pending: E.pending(d, dr), up, upBack: upBack === st, whole: [E.stepped(wr, '000010', -1, 50, 20), E.stepped(wr, '000010', 1, 50, 20), E.pctShown(20), E.pctShown(0.4)] };""")
    assert got["shown"] == [{"n": 16.7, "d": 1}] * 6
    assert got["down"] == 16 and got["exact"] is True and got["ok"] is True and got["pending"] is False
    assert got["up"] == 17 and got["upBack"] is True
    assert got["whole"] == [19, 21, {"n": 20, "d": 0}, {"n": 0.4, "d": 1}]


def test_shares_are_proportional_and_rounded_by_the_largest_remainder():
    """[S7] unequal targets: an equal share-out or a smallest-remainder rounding gives other numbers."""
    got = run("""const d = uneq();
      const step = E.editRows(d, E.fixDraft(d, E.stepDraft(E.emptyDraft(), '000010', 35))).map((r) => r.pct);
      const rm = E.editRows(d, E.removeDraft(d, E.emptyDraft(), '000050', null)).map((r) => r.pct);
      const add = E.editRows(d, E.addDraft(d, E.emptyDraft(), addSam(), 10)).map((r) => r.pct);
      out = { step, rm, add };""")
    assert got["step"] == [35, 23, 19, 14, 9]          # 65 × 25:20:15:10 ÷ 70 = 23.2 18.6 13.9 9.3 → 23 19 14 9 (나머지 큰 순)
    assert got["rm"] == [33, 28, 22, 17]               # 100 × 30:25:20:15 ÷ 90 = 33.3 27.8 22.2 16.7 → 33 28 22 17
    assert got["add"] == [27, 22, 18, 14, 9, 10]       # 90 × 30:25:20:15:10 = 27 22.5 18 13.5 9 → 27 22 18 14 9 (같으면 앞 종목 코드 먼저)


def test_the_1_percent_floor_and_the_stepper_limits():
    got = run("""const d = deck4({}, 3, 1 / 3, 100);
      const rows = E.editRows(d, E.fixDraft(d, E.stepDraft(E.emptyDraft(), '000010', 99))).map((r) => r.pct);
      const r3 = E.editRows(d, E.emptyDraft());
      out = { min: E.MIN_PCT, rows, lim: E.stepLimits(r3, '000010', null), capLim: E.stepLimits(r3, '000010', 40),
        at98: E.stepped(E.editRows(d, E.stepDraft(E.emptyDraft(), '000010', 98)), '000010', 1, null, 33),
        at1: E.stepped(E.editRows(d, E.stepDraft(E.emptyDraft(), '000010', 1)), '000010', -1, null, 33) };""")
    assert got["min"] == 1 and got["rows"] == [98, 1, 1]                                       # 나머지는 1% 아래로 가지 않아요
    assert got["lim"] == {"lo": 1, "hi": 98, "byCap": False} and got["capLim"] == {"lo": 1, "hi": 40, "byCap": True}
    assert got["at98"] is None and got["at1"] is None


def test_add_default_and_its_cap():
    got = run("""out = [[5, null], [4, null], [1, 30], [4, 30], [5, 10], [299, null]].map(([n, c]) => E.addDefault(n, c));""")
    assert got == [17, 20, 30, 20, 10, 1]              # 100 ÷ 6 = 16.7 → 17 (반올림) · 최대 비중 안 · 1% 아래로 가지 않아요


def test_the_change_log_keeps_the_newest_200_and_two_tabs_entries_stay_two():
    got = run("""const old = Array.from({ length: 200 }, (_, i) => ({ id: 'old' + String(i).padStart(5, '0'), at: '2026-10-02', kind: 'targets' }));
      const d = deck4({ changes: old });
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 24), '000020', 26), env);
      const cs = r.data.decks[0].changes;
      // two tabs, the same day and kind: two entries (their ids differ); the same entry in both copies stays one
      const b0 = { v: 1, decks: [deck4()] };
      const x = E.applyEdit(b0, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 24), '000020', 26), env).data;
      const y = E.applyEdit(b0, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000030', 24), '000040', 26), { ...env, ts: env.ts + 1 }).data;
      const m = S.mergeTabs(x, y, T), mm = S.mergeTabs(x, x, T);
      out = { n: cs.length, firstGone: cs[0].id === 'old00001', last: noId([cs[cs.length - 1]]), valid: S.validStore(r.data, T),
        two: m.decks[0].changes.length, one: mm.decks[0].changes.length, oldIds: S.validStore({ v: 1, decks: [{ ...deck4(), changes: [{ id: 'not ok!', at: T, kind: 'targets' }] }] }, T) };""")
    assert got["n"] == 200 and got["firstGone"] is True and got["last"] == [{"at": "2026-11-12", "kind": "targets"}] and got["valid"] is True
    assert got["two"] == 2 and got["one"] == 1 and got["oldIds"] is False


def test_reasons_are_checked():
    got = run("""const d = deck4({ sales: [{ id: 's1aaaaaa', t: '000020', qty: 5, price: 120000, date: '2026-11-01', ccy: 'KRW' }] });
      const dr = E.removeDraft(d, E.emptyDraft(), '000020', 'bogus');
      const forged = { ...E.emptyDraft(), removed: [{ t: '000020', reason: 'bogus' }], over: { '000010': 100 / 3, '000030': 100 / 3, '000040': 100 / 3 } };
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', forged, env);
      out = { draft: dr.removed, ch: noId(r.data.decks[0].changes), hist: 'reason' in r.data.decks[0].history[0] };""")
    assert got["draft"] == [{"t": "000020", "reason": None}]
    assert got["ch"] == [{"at": "2026-11-12", "kind": "remove", "t": "000020", "nk": "종목2"}] and got["hist"] is False


def test_plan_amount_and_plan_rate_come_first():
    """[S7] the plan's own amount (settings.amountMan) before what its numbers imply; the plan's rate (planFx) before today's."""
    got = run("""const d = deck4(); d.settings.amountMan = 1200;
      const implied = { ...d, settings: { ...d.settings } }; delete implied.settings.amountMan;
      const aapl = { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', ccy: 'USD', price: 100, ind: 'elec', indName: '전자부품' };
      const h = { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', target: 0.1, planPx: 100, rules: band(0.1) };
      const plain = deck4(), noFx = { ...plain }; delete noFx.planFx;
      out = { amt: E.planAmount(d), implied: E.planAmount(implied), re: E.retarget(d, d.holdings[0], 0.1).plannedQty,
        planFx: E.plannedFor(plain, h, 0.1, 1400, aapl), todayFx: E.plannedFor(noFx, h, 0.1, 1400, aapl) };""")
    assert got["amt"] == 12000000 and got["implied"] == 10000000 and got["re"] == 12   # 0.1 × 1,200만 ÷ 10만
    assert got["planFx"] == 8 and got["todayFx"] == 7                                   # 100만 ÷ (100 × 1,300) = 7.7 → 8 · ÷ (100 × 1,400) = 7.1 → 7


def test_pending_counts_a_cap_raise():
    got = run("""const d = deck4();
      out = [E.pending(d, { ...E.emptyDraft(), maxPct: 60 }), E.pending(d, { ...E.emptyDraft(), maxPct: 50 }), E.pending(d, E.emptyDraft())];""")
    assert got == [True, False, False]


def test_add_uses_todays_row_and_the_currency_of_the_price():
    """[S7] newHolding reads the row on screen now (a newer publish), not the row as it was picked. [Z1] 379800 KODEX
    미국S&P500 is cls "us" but priced in won: its plan is in won (cls stored as its currency's market), never × the dollar rate."""
    got = run("""const d = deck4({}, 4, 0.25, 50);
      const now = { ...load, byT: new Map([['005930', sam(230000)]]) };
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', E.addDraft(d, E.emptyDraft(), addSam(225000), 20), { ...env, load: now });
      const h = r.data.decks[0].holdings.find((x) => x.t === '005930');
      const k = { t: '379800', nk: 'KODEX 미국S&P500', cls: 'us', ccy: null, price: 22680, etf: true, fund: true, ind: null };
      const r2 = E.applyEdit({ v: 1, decks: [d] }, 'd1', E.addDraft(d, E.emptyDraft(), { t: k.t, nk: k.nk, cls: 'us', ind: null, kind: 'pinned', s: k }, 10), env);
      const hk = r2.data.decks[0].holdings.find((x) => x.t === '379800');
      // a stored 379800 holding (a hand-made file, cls "us") given a new target: still won when today's row says so
      const stored = { t: '379800', nk: k.nk, cls: 'us', target: 0.1, planPx: 22680, plannedQty: 44, rules: band(0.1) };
      const re = E.retarget(d, stored, 0.2, 1400, k);
      const nd2 = r2.data.decks[0], pw = Ru.planWeights(nd2, new Map(nd2.holdings.map((x) => [x.t, x.target])));
      out = { planPx: h.planPx, q: h.plannedQty, k: { cls: hk.cls, planPx: hk.planPx, q: hk.plannedQty }, re: re.plannedQty,
        valid: S.validStore(r2.data, T), pw: Math.round(pw.get('379800') * 1e4) / 1e4,
        pwOld: (() => { const x = { ...nd2, holdings: nd2.holdings.map((y) => (y.t === '379800' ? { ...y, cls: 'us' } : y)) };
          const m = Ru.planWeights(x, new Map(x.holdings.map((y) => [y.t, y.target]))); return Math.round(m.get('379800') * 1e4) / 1e4; })() };""")
    assert got["planPx"] == 230000 and got["q"] == round(0.2 * 1e7 / 230000)
    assert got["k"] == {"cls": "kr", "planPx": 22680, "q": round(0.1 * 1e7 / 22680)} and got["valid"] is True   # 44주, 0주가 아니에요
    assert got["re"] == round(0.2 * 1e7 / 22680)                                                 # 88주 (× 1,300 이면 0주)
    assert abs(got["pw"] - 0.1) < 0.01                                                           # 계획 비중 ≈ 10%
    assert got["pwOld"] > 0.9                                                                    # cls "us" 로 두면 × 1,300: 99% (그 버그)


def test_cushion_rows_and_bar_use_the_cushion_part():
    got = run("""const d = deck4({}, 5, 0.2, 50);
      d.holdings[4] = { ...d.holdings[4], t: '114260', kind: 'cushion', ind: null };
      const rows = E.editRows(d, E.emptyDraft());
      const byT = new Map([...ctxOf().byT, ['114260', { t: '114260', nk: 'KODEX 국고채3년', cls: 'kr', price: 60000, etf: true, ind: null }]]);
      out = { bar: E.indBar(rows, byT, new Map([['semi', '반도체']])), row: E.indOf(rows[4], byT, new Map()), plain: E.indOf(rows[0], byT, new Map([['semi', '반도체']])) };""")
    assert got["bar"] == [{"key": "semi", "name": "반도체", "pct": 80}, {"key": "cushion", "name": None, "cushion": True, "pct": 20}]
    assert got["row"] == "cushion" and got["plain"] == "반도체"


def test_a_zero_target_row_does_not_leave_the_fix_short():
    got = run("""const d = deck4({}, 4, 0.3, 30);
      d.holdings[3] = { ...d.holdings[3], target: 0, rules: [pend('audit')] };
      const rows = E.editRows(d, E.fixDraft(d, E.emptyDraft()));
      // the same with the one just changed left on a non-whole value (the others take the exact rest)
      const e = deck4({}, 4, 0.3, 30);
      e.holdings[0] = { ...e.holdings[0], target: 0.255 }; e.holdings[3] = { ...e.holdings[3], target: 0, rules: [pend('audit')] };
      const rows2 = E.editRows(e, E.fixDraft(e, E.stepDraft(E.emptyDraft(), '000010', 25.5)));
      out = { pcts: rows.map((r) => r.pct), sum: E.sumPct(rows), pcts2: rows2.map((r) => r.pct), sum2: E.sumPct(rows2) };""")
    assert got["pcts"] == [30, 30, 30, 10] and got["sum"] == 100                 # 0% 줄이 남은 몫을 받아요 (최대 비중 안, D2 줄 없이 100%)
    assert got["pcts2"] == [25.5, 30, 30, 14.5] and abs(got["sum2"] - 100) < 1e-9


def test_a_holding_above_the_cap_steps_back_to_its_own_value_never_higher():
    """[S3] a 채권·금 cushion stored at 30% under a 10% cap: − then + gives back 30 (not stuck at 29), + at 30 stays off."""
    got = run("""const d = deck4({}, 5, 0.175, 10);
      d.holdings[4] = { ...d.holdings[4], kind: 'cushion', target: 0.3, rules: band(0.3) };
      const rows = E.editRows(d, E.emptyDraft());
      const st = E.storedPct(rows[4]);
      const down = E.stepped(rows, '000050', -1, 10, st);
      const back = E.stepped(E.editRows(d, E.stepDraft(E.emptyDraft(), '000050', down)), '000050', 1, 10, st);
      out = { st, down, back, more: E.stepped(rows, '000050', 1, 10, st), lim: E.stepLimits(rows, '000050', 10, st), other: E.stepLimits(rows, '000010', 10, 17.5) };""")
    assert got["st"] == 30 and got["down"] == 29 and got["back"] == 30 and got["more"] is None
    assert got["lim"] == {"lo": 1, "hi": 30, "byCap": True} and got["other"] == {"lo": 1, "hi": 17.5, "byCap": True}
