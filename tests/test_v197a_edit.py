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
      // an untouched holding is saved as it was, plus its plan weight (planW: Jack, 2026-11-13)
      const same = (t) => { const { planW, ...h } = nd.holdings.find((x) => x.t === t); return JSON.stringify(d.holdings.find((x) => x.t === t)) === JSON.stringify(h); };
      out = { ok: r.ok, a: bandOf(after, '000010'), aBefore: bandOf(before, '000010'), oldA: bandOf(old, '000010'),
        c: [bandOf(before, '000030'), bandOf(after, '000030')], dd: [bandOf(before, '000040'), bandOf(after, '000040')],
        sameC: same('000030'), sameD: same('000040'), hA: nd.holdings[0], hB: nd.holdings[1], planW: nd.holdings.map((h) => h.planW),
        valid: S.validStore(r.data, T), changes: noId(nd.changes), ids: ids(nd.changes) };""")
    assert got["ok"] is True and got["valid"] is True and got["ids"] is True
    assert got["aBefore"]["status"] == "none"
    assert got["a"]["status"] == "trim", got["a"]                                              # 같은 날 바로: 25% 가 10% 목표의 1.4배를 넘어요
    assert got["oldA"]["status"] == "none"                                                     # plannedQty 를 그대로 두면 안 걸려요 (그 버그)
    assert got["c"][0] == got["c"][1] and got["dd"][0] == got["dd"][1]                        # 다른 종목의 오늘 기준선은 그대로
    assert got["sameC"] and got["sameD"]                                                       # 저장된 규칙 · plannedQty · planPx 도 그대로
    # planW: 안 바꾼 종목은 제 계획 금액(25주 × 100,000원) 그대로, 바꾼 둘은 둘이 가졌던 500만을 새 목표 비율(10 : 40)로
    assert got["planW"] == [1000000, 4000000, 2500000, 2500000]
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
    assert s5["names"] == ["종목2", "종목3", "종목4", "종목5"]                                       # 저장된 종목만 (기다리는 삼성전자는 빼고, round-2)
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
    their own merge rules (removal marks, history). Here only tab A changed targets, so the sum is A's; when both tabs changed
    targets of different holding sets it is not (test_two_tabs_that_both_changed_targets_store_another_sum_safely)."""
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
        // the plan read from plannedQty (an earlier app, or a portfolio without planW): cls as stored, and cls "us" (the bug)
        pwQty: ((cls) => { const x = { ...nd2, holdings: nd2.holdings.map(({ planW, ...y }) => (y.t === '379800' && cls ? { ...y, cls } : y)) };
          const m = Ru.planWeights(x, new Map(x.holdings.map((y) => [y.t, y.target]))); return Math.round(m.get('379800') * 1e4) / 1e4; })(null),
        pwOld: (() => { const x = { ...nd2, holdings: nd2.holdings.map(({ planW, ...y }) => (y.t === '379800' ? { ...y, cls: 'us' } : y)) };
          const m = Ru.planWeights(x, new Map(x.holdings.map((y) => [y.t, y.target]))); return Math.round(m.get('379800') * 1e4) / 1e4; })() };""")
    assert got["planPx"] == 230000 and got["q"] == round(0.2 * 1e7 / 230000)
    assert got["k"] == {"cls": "kr", "planPx": 22680, "q": round(0.1 * 1e7 / 22680)} and got["valid"] is True   # 44주, 0주가 아니에요
    assert got["re"] == round(0.2 * 1e7 / 22680)                                                 # 88주 (× 1,300 이면 0주)
    assert abs(got["pw"] - 0.1) < 0.01 and abs(got["pwQty"] - 0.1) < 0.01                         # 계획 비중 ≈ 10% (planW 로도, plannedQty 로도)
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


def test_d2_counts_a_holding_already_above_the_cap():
    """[S4] D2 shows when every row at its own ceiling (the cap, or its own % when already above it) adds up to less than
    100 — the spec's intent; its literal n × x < 100 ignored a 채권·금 cushion above the cap. Both reviewers' case: a 10% cap,
    seven stocks at 10% and 안전자산 30% (two at 15%): 합계 100%, no D2 line, save on. y stays 100 ÷ n rounded up."""
    got = run("""const mk = (stocks, w, cush) => { const n = stocks + cush.length; const d = deck4({}, n, w, 10);
        d.holdings = d.holdings.map((h, i) => (i < stocks ? h : { ...h, kind: 'cushion', target: cush[i - stocks], rules: band(cush[i - stocks]) }));
        return d; };
      const nine = mk(7, 0.1, [0.15, 0.15]);
      const rows9 = E.editRows(nine, E.emptyDraft());
      // after one stock is taken out: 6 x 10 + 30 = 90 -> D2 is true now (y = 13), and the raise reaches 100
      const dr = E.removeDraft(nine, E.emptyDraft(), '000010', null);
      const rows8 = E.editRows(nine, dr);
      const raised = E.editRows(nine, E.raiseDraft(nine, dr));
      // eight stocks at 8.75% + 30%: one taken out, the seven left reach 10% each: 100 without a raise
      const ten = mk(8, 0.0875, [0.15, 0.15]);
      const dr10 = E.removeDraft(ten, E.emptyDraft(), '000010', null);
      const rows10 = E.editRows(ten, dr10);
      out = { sum9: E.sumPct(rows9), d9: E.d2Of(rows9, 10), lit9: E.capCheck(9, 10), save9: E.applyEdit({ v: 1, decks: [nine] }, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 9), '000020', 10), env),
        d8: E.d2Of(rows8, 10), sum8: E.sumPct(rows8), raised: raised.map((r) => r.pct), rsum: E.sumPct(raised),
        d10: E.d2Of(rows10, 10), sum10: E.sumPct(rows10), pcts10: rows10.map((r) => r.pct),
        sell: E.sellCheck(nine, E.emptyDraft(), '000010'), sellTen: E.sellCheck(ten, E.emptyDraft(), '000010'),
        none: E.d2Of(rows9, null), plain: (() => { const f = deck4({}, 5, 0.2, 20);
          return [E.d2Of(E.editRows(f, E.removeDraft(f, E.emptyDraft(), '000050', null)), 20), E.d2Of(E.editRows(f, E.emptyDraft()), 20)]; })() };""")
    assert got["sum9"] == 100 and got["d9"] == {"low": False, "y": 12} and got["lit9"]["low"] is True   # 9 × 10 = 90 < 100 이지만 닿아요
    assert got["save9"]["ok"] is False and got["save9"]["why"] == "sum"                         # (stepping only one: 99%, the fix button's job)
    assert got["d8"] == {"low": True, "y": 13} and got["sum8"] == 90
    assert sorted(got["raised"][:6]) == [11, 11, 12, 12, 12, 12] and got["raised"][6:] == [15, 15] and got["rsum"] == 100
    assert got["d10"] == {"low": False, "y": 12} and got["sum10"] == 100 and got["pcts10"] == [10] * 7 + [15, 15]
    assert got["sell"]["low"] is True and got["sell"]["y"] == 13 and got["sellTen"]["low"] is False
    assert got["none"] == {"low": False, "y": None}
    assert got["plain"] == [{"low": True, "y": 25}, {"low": False, "y": 20}]                   # 안전자산이 없으면 n × x 그대로


# ---------------- round-2 review ----------------
TABS2 = """const later = { ...env, ts: env.ts + 60000 };
      const base = (cap = 50) => ({ v: 1, decks: [deck4({}, 4, 0.25, cap)] });
      const hy = { t: '000660', nk: 'SK하이닉스', cls: 'kr', ind: 'semi', kind: 'pinned', s: { t: '000660', nk: 'SK하이닉스', cls: 'kr', price: 200000, ind: 'semi', indName: '반도체' } };
      const finite = (x) => (typeof x === 'number' ? Number.isFinite(x) : Array.isArray(x) ? x.every(finite) : x && typeof x === 'object' ? Object.values(x).every(finite) : true);
      const recIds = (d) => [...(d.purchases || []).map((p) => p.id), ...(d.sales || []).map((p) => p.id), ...(d.divs || []).map((p) => p.id),
        ...(d.history || []).flatMap((e) => [...(e.purchases || []), ...(e.sales || []), ...(e.divs || [])].map((p) => p.id))].sort();
      // the next start after two tabs wrote: the one that wrote last is the store, the other's copy is kept aside (.other.)
      const meet = (first, last) => { mem.clear(); mem.set(K + '.other.1700000000000', JSON.stringify(first)); mem.set(K, JSON.stringify(last)); return S.readStore(K, T); };
      const norm = (d) => { const s = d.holdings.reduce((a, h) => a + h.target, 0);
        return { ...d, holdings: d.holdings.map((h) => ({ ...h, target: h.target / s, rules: h.rules.map((r) => (r.id === 'band' ? E.bandRule(h.target / s) : r)) })) }; };
      const daily = (d) => { const e = Ru.evaluateDeck(d, ctxOf()); return e.holdings.map((x) => [x.t, x.status, (x.rules.find((r) => r.id === 'band') || {}).bands?.map((b) => Math.round(b * 1e9) / 1e9)]); };
"""


def test_two_tabs_that_both_changed_targets_store_another_sum_safely():
    """[B-1] a known limit (RUNBOOK): both tabs changed targets and added or took out different stocks, so the later set
    covers only its own holdings and the targets add up to more or less than 100%. Never renormalised; for each case and
    both write orders: no record is lost, no NaN, the 합쳤어요 line (restored), 종목 바꾸기 opens off 100% and its button
    (합계를 100%로 맞추기, or D2 when the cap needs it) reaches 100, and the daily check reads the same as with the targets scaled
    to 100% (each target over the held ones' sum), so the sum alone flags nothing."""
    got = run(TABS2 + """const cases = {};
      { const b0 = base(), d0 = b0.decks[0];
        cases.addStep = [E.applyEdit(b0, 'd1', E.addDraft(d0, E.emptyDraft(), addSam(), 20), env).data, E.applyEdit(b0, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 30), '000020', 20), later).data]; }
      { const b0 = base(), d0 = b0.decks[0];
        cases.removeStep = [E.applyEdit(b0, 'd1', E.removeDraft(d0, E.emptyDraft(), '000040', 'thesis'), env).data, E.applyEdit(b0, 'd1', E.stepDraft(E.stepDraft(E.emptyDraft(), '000010', 30), '000020', 20), later).data]; }
      { const b0 = base(), d0 = b0.decks[0];
        cases.sellAdd = [E.sellAndRemove(sellAll(b0, '000010', 25), 'd1', '000010', { reason: null, raise: null, load, today: T, ts: env.ts }).data, E.applyEdit(b0, 'd1', E.addDraft(d0, E.emptyDraft(), addSam(), 20), later).data]; }
      { const b0 = base(), d0 = b0.decks[0];
        cases.addAdd = [E.applyEdit(b0, 'd1', E.addDraft(d0, E.emptyDraft(), addSam(), 20), env).data, E.applyEdit(b0, 'd1', E.addDraft(d0, E.emptyDraft(), hy, 20), later).data]; }
      const res = {};
      for (const [k, [a, b]] of Object.entries(cases)) {
        for (const [order, x, y] of [['bLast', a, b], ['aLast', b, a]]) {
          const r = meet(x, y);
          const d = r.data.decks[0];
          const rows = E.editRows(d, E.emptyDraft()), cap = E.capOf(d), d2 = E.d2Of(rows, cap);
          const fixed = E.editRows(d, d2.low ? E.raiseDraft(d, E.emptyDraft()) : E.fixDraft(d, E.emptyDraft()));
          // every record either copy holds, except the purchases of a stock one tab took out with 기록 없이 빼기 (they leave with it
          // by the user's choice; its sales and dividends would be in history)
          const out_ = new Set((d.removed || []).map((m) => m.t));
          const gonePurchases = new Set([a, b].flatMap((x) => (x.decks[0].purchases || []).filter((p) => out_.has(p.t)).map((p) => p.id)));
          const want = [...new Set([...recIds(a.decks[0]), ...recIds(b.decks[0])])].filter((id) => !gonePurchases.has(id) || recIds(d).includes(id)).sort();
          res[k + ':' + order] = { restored: r.restored, problems: r.problems.length, locked: r.locked, sum: Math.round(E.sumPct(rows) * 1e6) / 1e6, ok: E.sumOk(E.sumPct(rows)),
            fixed: Math.round(E.sumPct(fixed) * 1e6) / 1e6, d2: d2.low, finite: finite(r.data), recs: JSON.stringify(recIds(d)) === JSON.stringify(want),
            daily: JSON.stringify(daily(d)) === JSON.stringify(daily(norm(d))), held: daily(d).length };
        }
      }
      out = res;""")
    sums = {}
    for k, v in got.items():
        assert v["restored"] is True and v["problems"] == 0 and v["locked"] is False, (k, v)       # 합쳤어요 · 따로 두지 않아요
        assert v["finite"] is True and v["recs"] is True, (k, v)                                    # NaN 없음 · 기록은 모두 그대로
        assert v["fixed"] == 100, (k, v)                                                            # 맞추기(또는 D2)로 100%
        assert v["daily"] is True and v["held"] >= 3, (k, v)                                        # 합계만으로는 아무것도 걸리지 않아요
        sums[k] = v["sum"]
    off = {k: s for k, s in sums.items() if s != 100}
    assert off, sums                                                                                # 알려진 한계: 100% 가 아닌 경우가 있어요
    for k, s in off.items():
        assert got[k]["ok"] is False                                                                # 열면 합계가 주황(저장 꺼짐) · 맞추기 버튼


def test_the_sell_and_remove_quantity_follows_the_sale_date_across_a_split():
    """[B-2] the locked quantity is every share held, on the chosen date's share basis: HON (1:2 on 2026-06-29) bought 2 on
    2026-01-02 sells 2 when dated 06-26 and 1 when dated 07-01; NVDA (10:1 on 2024-06-10) bought 5 sells 5 before and 50
    after. Each takes out exactly the holding. A refusal is said in the console (the old prefill: today's count)."""
    got = run("""const US = { today: T, fx: 1400, fxDate: T, stale: false, fxHist: { asOf: T, final: true, rows: [['2016-01-04', 1100], ['2024-06-03', 1380], ['2024-06-07', 1375],
        ['2024-06-12', 1378], ['2026-01-02', 1450], ['2026-06-26', 1370], ['2026-07-01', 1375], [T, 1400]] } };
      const row = (t, price) => ({ t, nk: t, cls: 'us', ccy: 'USD', price, ind: 'semi', indName: '반도체' });
      const dk = (t, qty, date, split) => ({ id: 'd1', name: 'x', createdAt: '2024-01-02', planFx: 1300, settings: { points: { value: 3 }, maxPct: 100, amountMan: 1000 },
        holdings: [{ t, nk: t, cls: 'us', kind: 'core', target: 0.5, setAt: '2024-01-02', rules: [...band(0.5)] }, { t: '000010', nk: '종목1', cls: 'kr', kind: 'core', target: 0.5, setAt: '2024-01-02', rules: [...band(0.5)] }],
        purchases: [{ id: 'p1aaaaaa', t, qty, price: 100, date, ccy: 'USD', fx: 1300 }, { id: 'p2aaaaaa', t: '000010', qty: 10, price: 100000, date, ccy: 'KRW' }], splits: [split] });
      const go = (d, t, date) => { const q = E.sellAllQty(d, t, date);
        const c = Rc.checkSale(d, t, { qty: String(q), price: '200', date }, row(t, 200), US);
        if (!c.ok) return { q, why: c.why };
        const r = E.sellAndRemove(Rc.withRecord({ v: 2, decks: [d] }, 'd1', 'sales', c.rec, T), 'd1', t, { reason: null, raise: null, load, today: T, ts: env.ts });
        return { q, ok: r.ok, why: r.why, held: r.ok ? r.data.decks[0].holdings.map((h) => h.t) : null, sold: r.ok ? r.data.decks[0].history[0].sales[0].qty : null }; };
      const hon = dk('HON', 2, '2026-01-02', { t: 'HON', date: '2026-06-29', r: 0.5 });
      const nv = dk('NVDA', 5, '2024-06-03', { t: 'NVDA', date: '2024-06-10', r: 10 });
      // the old prefill (today's count) dated before the split
      const oldHon = (() => { const c = Rc.checkSale(hon, 'HON', { qty: '1', price: '200', date: '2026-06-26' }, row('HON', 200), US);
        const n = warns.length; const r = E.sellAndRemove(Rc.withRecord({ v: 2, decks: [hon] }, 'd1', 'sales', c.rec, T), 'd1', 'HON', { reason: null, raise: null, load, today: T, ts: env.ts });
        return { ok: r.ok, why: r.why, warned: warns.slice(n).some((w) => w.includes('refused (partial)') && w.includes('HON')) }; })();
      const oldNv = Rc.checkSale(nv, 'NVDA', { qty: '50', price: '200', date: '2024-06-07' }, row('NVDA', 200), US);
      out = { now: [E.heldShares(hon, 'HON'), E.heldShares(nv, 'NVDA')], hon: [go(hon, 'HON', '2026-06-26'), go(hon, 'HON', '2026-07-01')],
        nv: [go(nv, 'NVDA', '2024-06-07'), go(nv, 'NVDA', '2024-06-12')], oldHon, oldNv: { ok: oldNv.ok, why: oldNv.why }, none: [E.sellAllQty(hon, 'XXX', T), E.sellAllQty(hon, 'HON', '')] };""")
    assert got["now"] == [1, 50]
    assert got["hon"] == [{"q": 2, "ok": True, "held": ["000010"], "sold": 2}, {"q": 1, "ok": True, "held": ["000010"], "sold": 1}]
    assert got["nv"] == [{"q": 5, "ok": True, "held": ["000010"], "sold": 5}, {"q": 50, "ok": True, "held": ["000010"], "sold": 50}]
    assert got["oldHon"] == {"ok": False, "why": "partial", "warned": True}                      # 예전: 조용히 거절 → 이제 console 에 이유
    assert got["oldNv"]["ok"] is False                                                           # 예전: 고칠 수 없는 칸에 '너무 많아요'
    assert got["none"] == [None, None]


def test_round_2_pins_stamps_raise_import_and_lost_set():
    """[B-3] 팔고 빼기 stamps targetsTs · sellCheck counts a cap raise waiting in the draft · a records file's other target
    set comes in stamped with the import time (a copy with an older set never takes it back) · a target set that lost is
    reported (restored), even when nothing else differs."""
    got = run(TABS2 + """const five = deck4({}, 5, 0.2, 20);
      const sr = E.sellAndRemove(sellAll({ v: 1, decks: [five] }, '000010', 20), 'd1', '000010', { reason: null, raise: 25, load, today: T, ts: env.ts + 5 });
      const waiting = E.sellCheck(five, { ...E.emptyDraft(), maxPct: 25 }, '000010'), plain = E.sellCheck(five, E.emptyDraft(), '000010');
      // a records file with another target set (10 / 40 / 25 / 25, stamped 1000) over this device's (25s, stamped 2000)
      const mine = { v: 2, decks: [{ ...deck4(), targetsTs: 2000 }] };
      const other = { v: 2, decks: [{ ...deck4(), holdings: deck4().holdings.map((h, i) => ({ ...h, target: [0.1, 0.4, 0.25, 0.25][i], rules: [pend('audit'), ...band([0.1, 0.4, 0.25, 0.25][i])] })), targetsTs: 1000 }] };
      const inc = S.parseImport(S.exportText(other), T);
      const im = S.mergeStores(mine, inc, 1762900000000, [mine], T);
      const back = S.mergeTabs(mine, im, T);
      const same = S.mergeStores(mine, S.parseImport(S.exportText(mine), T), 1762900000000, [mine], T);
      // the lost set alone: two copies that differ only in their stamped target sets
      const lost = meet(other, mine), kept = meet(mine, mine);
      out = { srTs: sr.ok && sr.data.decks[0].targetsTs, waiting: [waiting.cap, waiting.up, waiting.low], plain: [plain.cap, plain.up, plain.low],
        im: [im.decks[0].targetsTs, im.decks[0].holdings.map((h) => h.target)], back: back.decks[0].holdings.map((h) => h.target), sameTs: same.decks[0].targetsTs,
        lost: [lost.restored, lost.data.decks[0].holdings.map((h) => h.target)], kept: kept.restored, names: plain.names };""")
    assert got["srTs"] == 1762900000005
    assert got["waiting"] == [25, 25, False] and got["plain"] == [20, None, True]
    assert got["im"] == [1762900000000, [0.1, 0.4, 0.25, 0.25]] and got["back"] == [0.1, 0.4, 0.25, 0.25]
    assert got["sameTs"] == 2000                                                                 # 같은 목표: 새 시각을 찍지 않아요
    assert got["lost"] == [True, [0.25, 0.25, 0.25, 0.25]] and got["kept"] is False
    assert got["names"] == ["종목2", "종목3", "종목4", "종목5"]


def test_d2_reads_a_cushion_s_stored_value():
    """[round-2 nit] 7 × 10% + 15% + 15% under a 10% cap: stepping a cushion 15 → 14 shows no D2 (its ceiling is its stored
    15%, as the stepper's); 합계를 100%로 맞추기 then puts it back to 15."""
    got = run("""const d = deck4({}, 9, 0.1, 10);
      d.holdings = d.holdings.map((h, i) => (i < 7 ? h : { ...h, kind: 'cushion', target: 0.15, rules: band(0.15) }));
      const dr = E.stepDraft(E.emptyDraft(), '000080', 14);
      const rows = E.editRows(d, dr);
      const fixed = E.editRows(d, E.fixDraft(d, dr));
      out = { sum: E.sumPct(rows), d2: E.d2Of(rows, 10), fixed: fixed.map((r) => r.pct), fsum: E.sumPct(fixed), ceil: E.ceilingOf(rows[7], 10) };""")
    assert got["sum"] == 99 and got["d2"] == {"low": False, "y": 12} and got["ceil"] == 15
    assert got["fixed"] == [10] * 7 + [15, 15] and got["fsum"] == 100


def test_price_won_goes_by_the_currency():
    """[round-2 nit, Z1] engine.priceWon: dollars by the row's currency, never by cls alone: 379800 (cls "us", priced in won on
    KRX, no ccy) is valued in won; a US row with ccy USD × fx; a row with no currency at all falls back to its market, except a
    six-digit KRX code."""
    got = run("""const k = { t: '379800', cls: 'us', price: 22680, etf: true, fund: true };
      out = { k: En.priceWon(k, 1400), aapl: En.priceWon({ t: 'AAPL', cls: 'us', ccy: 'USD', price: 270 }, 1400), bare: En.priceWon({ t: 'AAPL', cls: 'us', price: 270 }, 1400),
        kr: En.priceWon({ t: '005930', cls: 'kr', price: 100000 }, 1400), krw: En.priceWon({ t: 'X', cls: 'us', ccy: 'KRW', price: 5 }, 1400),
        nofx: En.priceWon({ t: 'AAPL', cls: 'us', ccy: 'USD', price: 270 }, null),
        w: (() => { const m = Ru.deckWeights(new Map([['379800', 10], ['005930', 1]]), { byT: new Map([['379800', k], ['005930', { t: '005930', cls: 'kr', price: 226800 }]]), fx: 1400 }, null);
          return Math.round(m.w.get('379800') * 1e6) / 1e6; })() };""")
    assert got["k"] == 22680 and got["aapl"] == 270 * 1400 and got["bare"] == 270 * 1400 and got["kr"] == 100000 and got["krw"] == 5 and got["nofx"] is None
    assert got["w"] == 0.5                                                                        # 10 × 22,680 = 226,800 원: 반반 (× 1,400 이면 99.9%)


def test_a_share_out_never_raises_a_holding_above_the_cap_or_its_stored_target():
    """[round 3] the ceiling is max(cap, the STORED target), never the value in the draft: a draft value left above both (the
    fuzz's 55.26% against a saved 55% after 팔고 빼기 while a removal waits) is brought down, and the draft after 팔고 빼기
    follows the portfolio as the sale saved it (draftAfterSale), so no row is above max(cap, its stored target)."""
    got = run("""// the fuzz's first case: 000010 (no target), 000020 55.26%, 000030 42.11% under a 20% cap; 000010 waits to be taken out
      const w = [null, 21 / 38, 16 / 38];
      const d = deck4({}, 3, 0.25, 20);
      d.holdings = d.holdings.map((h, i) => { const { target, ...rest } = h; return w[i] == null ? { ...rest, rules: [pend('audit')] } : { ...rest, target: w[i], rules: [pend('audit'), ...band(w[i])] }; });
      d.purchases = [d.purchases[1], d.purchases[2]];
      let dr = E.removeDraft(d, E.emptyDraft(), '000010', null);
      const sc = E.sellCheck(d, dr, '000030');
      const after = sellAll({ v: 2, decks: [d] }, '000030', 25);
      const sr = E.sellAndRemove(after, 'd1', '000030', { reason: null, raise: sc.y, load, today: T, ts: env.ts });
      const nd = sr.data.decks[0];
      const nx = E.draftAfterSale(d, nd, E.rebaseDraft(d, dr), '000030');
      const rows = E.editRows(nd, nx), cap = E.capOf(nd, nx);
      // the ceiling ignores a draft value: a row the draft holds above max(cap, stored) is brought down by any share-out
      const high = E.editRows(nd, { ...E.emptyDraft(), over: { '000020': 70 } });
      const fixed = E.editRows(nd, E.fixDraft(nd, { ...E.emptyDraft(), over: { '000020': 70 } }));
      // nothing else waiting: the draft after the sale is the saved portfolio
      const five = deck4({}, 5, 0.2, 50);
      const s5 = E.sellAndRemove(sellAll({ v: 2, decks: [five] }, '000010', 20), 'd1', '000010', { reason: null, raise: null, load, today: T, ts: env.ts });
      const plain = E.draftAfterSale(five, s5.data.decks[0], E.emptyDraft(), '000010');
      // edits still waiting (000020 stepped to 30, the rest shared out): after the sale they are shared out to 100% again under
      // the new ceilings, the row just changed kept
      const f2 = deck4({}, 5, 0.2, 50);
      const w2 = E.fixDraft(f2, E.stepDraft(E.emptyDraft(), '000020', 30));
      const s2 = E.sellAndRemove(sellAll({ v: 2, decks: [f2] }, '000030', 20), 'd1', '000030', { reason: null, raise: null, load, today: T, ts: env.ts });
      const a2 = E.editRows(s2.data.decks[0], E.draftAfterSale(f2, s2.data.decks[0], E.rebaseDraft(f2, w2), '000030'));
      out = { stored: nd.holdings.map((h) => [h.t, Math.round(h.target * 1e6) / 1e6]), max: nd.settings.maxPct,
        rows: rows.map((r) => [r.t, r.pct, E.storedPct(r)]), cap, above: rows.filter((r) => cap != null && r.pct > Math.max(cap, E.storedPct(r) || 0) + 1e-9).length,
        ceil: E.ceilingOf(high[1], 50), fixed: fixed.map((r) => [r.t, r.pct]), plain: E.pending(s5.data.decks[0], plain),
        waiting: [E.editRows(f2, w2).map((r) => r.pct), a2.map((r) => [r.t, r.pct]), E.sumPct(a2)] };""")
    assert got["max"] == 50 and got["stored"] == [["000010", 0.45], ["000020", 0.55]]
    assert got["above"] == 0, got["rows"]                                                      # 55.26 이 남지 않아요
    assert abs(got["ceil"] - 55) < 1e-9                                                        # 초안의 70 은 천장이 아니에요
    assert dict(got["fixed"])["000020"] <= 55 + 1e-9 and abs(sum(p for _, p in got["fixed"]) - 100) < 1e-9
    assert got["plain"] is False
    before, rows, total = got["waiting"]
    assert before == [18, 30, 18, 17, 17] and dict(rows)["000020"] == 30 and total == 100 and all(p <= 50 for _, p in rows)


# ---------------- planW: each holding's plan weight stored next to it (Jack, 2026-11-13: Q16) ----------------
PLANW = """// seven Korean holdings on a 1,000만원 plan, at prices that leave whole-share rounding gaps; bought as planned
      const P7 = [333000, 127000, 61500, 480000, 91000, 1150000, 77700], W7 = [0.2, 0.2, 0.15, 0.15, 0.1, 0.1, 0.1];
      const q7 = (i) => Math.round(W7[i] * 1e7 / P7[i]);
      const deck7 = (extra = {}) => ({ id: 'd7', name: '일곱 종목', createdAt: '2026-10-01', planFx: 1300, settings: { points: { value: 3 }, maxPct: 50, amountMan: 1000 },
        holdings: CODES.slice(0, 7).map((t, i) => ({ t, nk: '종목' + (i + 1), cls: 'kr', ind: 'semi', kind: 'core', target: W7[i], setAt: '2026-10-01',
          plannedQty: q7(i), planPx: P7[i], rules: [pend('audit'), ...band(W7[i])] })),
        purchases: CODES.slice(0, 7).map((t, i) => ({ id: 'p' + i + 'aaaaaa', t, qty: q7(i), price: P7[i], date: '2026-10-01', ccy: 'KRW' })), ...extra });
      // today's prices have moved (the bands are read at real weights, not at the plan's)
      const ctx7 = { state: { ok: true }, byT: new Map(CODES.slice(0, 7).map((t, i) => [t, stock(t, Math.round(P7[i] * (1 + 0.03 * (i - 3))))])), coByT: new Map(), fx: 1400, pxDate: T };
      const bandsOf = (e) => Object.fromEntries(e.holdings.map((x) => { const r = x.rules.find((y) => y.id === 'band');
        return [x.t, { status: x.status, target: r.target, bands: r.bands, refBands: r.refBands, gap: r.gap, planW: r.planW, scale: r.scale, now: r.now }]; }));
      const steps = (pairs) => pairs.reduce((dr, [t, p]) => E.stepDraft(dr, t, p), E.emptyDraft());
      const noW = (d) => ({ ...d, holdings: d.holdings.map(({ planW, ...h }) => h) });
      const ws = (d) => d.holdings.map((h) => h.planW ?? null);
"""


def test_changing_2_of_7_targets_leaves_every_untouched_band_identical_to_the_last_digit():
    """Q16 (Jack, 2026-11-13). Seven stocks; two targets change (20 → 15, 20 → 25). The save writes every holding's plan weight
    next to it (planW): the five untouched ones keep their plan value to the won, the two changed ones share exactly what the
    two had. Every untouched stock's band (target, the three edges, the gap, the plan weight, today's weight) is the same
    number, digit for digit, before and after — on the first save (the plan read from plannedQty before, from planW after)
    and on a second one. Without planW (how the app read the same save before, and how an earlier app's tab still reads it)
    the untouched edges move: that was the bug. A whole plannedQty is still written for the earlier apps."""
    got = run(PLANW + """const d = deck7();
      const b0 = bandsOf(Ru.evaluateDeck(d, ctx7));
      const r1 = E.applyEdit({ v: 1, decks: [d] }, 'd7', steps([['000010', 15], ['000020', 25]]), env);
      const d1 = r1.data.decks[0], b1 = bandsOf(Ru.evaluateDeck(d1, ctx7)), bOld = bandsOf(Ru.evaluateDeck(noW(d1), ctx7));
      const r2 = E.applyEdit(r1.data, 'd7', steps([['000030', 10], ['000040', 20]]), { ...env, ts: env.ts + 1000 });
      const d2 = r2.data.decks[0], b2 = bandsOf(Ru.evaluateDeck(d2, ctx7));
      out = { ok: [r1.ok, r2.ok], valid: [S.validStore(r1.data, T), S.validStore(r2.data, T)], b0, b1, bOld, b2,
        v0: d.holdings.map((h) => h.plannedQty * h.planPx), w1: ws(d1), w2: ws(d2), q1: d1.holdings.map((h) => h.plannedQty),
        tg: d2.holdings.map((h) => h.target), warns };""")
    assert got["ok"] == [True, True] and got["valid"] == [True, True] and got["warns"] == []
    b0, b1, b2, old = got["b0"], got["b1"], got["b2"], got["bOld"]
    assert all(x["scale"] == 1 for x in b0.values())                                          # 이 포트폴리오의 예전 목표 합은 정확히 1 (첫 저장도 끝자리까지)
    CODES = ["000010", "000020", "000030", "000040", "000050", "000060", "000070"]
    untouched = CODES[2:7]
    for t in untouched:
        assert b1[t] == b0[t], (t, b0[t], b1[t])                                              # 마지막 자리까지 같아요 (첫 저장: plannedQty → planW)
    assert all(b0[t]["gap"] != 0 for t in untouched)                                          # 이 시험의 종목들은 실제로 틈(반올림)이 있어요
    # planW 가 없으면 (예전 방식 · 예전 앱의 창) 안 바꾼 종목의 기준선이 움직여요: 고친 버그
    moved = max(abs(a - b) for t in untouched for a, b in zip(old[t]["bands"], b0[t]["bands"]))
    assert moved > 1e-4, moved
    # 저장된 값: 안 바꾼 다섯은 제 계획 금액 그대로(원 단위), 바꾼 둘은 둘이 가졌던 만큼을 새 목표 비율로 (정수, 합이 정확히 같아요)
    v0, w1 = got["v0"], got["w1"]
    assert w1[2:] == v0[2:] and all(isinstance(x, int) for x in w1) and sum(w1) == sum(v0)
    assert w1[0] + w1[1] == v0[0] + v0[1] and abs(w1[0] / (w1[0] + w1[1]) - 15 / 40) < 1e-6
    assert abs(b1["000010"]["target"] - 0.15) < 1e-12 and abs(b1["000020"]["target"] - 0.25) < 1e-12   # 바꾼 종목은 새 목표를 따라가요
    assert got["q1"][0] == round(0.15 * 1e7 / 333000) and all(isinstance(q, int) for q in got["q1"])   # plannedQty 는 예전 앱을 위해 그대로 써요
    # 두 번째 저장 (planW → planW): 이번에 안 바꾼 다섯 (처음에 바꾼 둘 포함)
    for t in CODES[:2] + CODES[4:7]:
        assert b2[t] == b1[t], (t, b1[t], b2[t])
    w2 = got["w2"]
    assert w2[:2] == w1[:2] and w2[4:] == w1[4:] and sum(w2) == sum(v0) and w2[2] + w2[3] == w1[2] + w1[3]
    assert [round(x, 9) for x in got["tg"]] == [0.15, 0.25, 0.1, 0.2, 0.1, 0.1, 0.1]


def test_untouched_bands_fuzz_first_save_and_later_saves():
    """600 random portfolios (3–8 stocks, whole-% targets, random prices and amounts; one in four holds a dollar stock; in one
    in three, one stock was never bought), each edited twice by moving 1–9 points between two stocks. For every stock whose
    target was not changed, the status is the same and:
    - a plan in won, any save after the first: the band is the same to the last digit, always;
    - a plan in won, the first save (plannedQty before, planW after): the same to the last digit whenever the old sum of the
      held targets was a clean number (the old lines keep that float sum as it was; when its last bit was off, 1e-12 at most);
    - a plan with a dollar stock (its values are not whole numbers): 1e-12 at most.
    The plan's total never changes, and every stored weight is a number.
    Verification S-b (was final review S2 (b): its own whole planned shares over the stored total): a changed held holding
    reads exactly as a brand-new plan with the same targets, prices and amount (the same portfolio read without planW): the
    same status, plan weight (1e-15) and edges (1e-12). The allowance never gives 일부 팔아요 or 먼저 사요 that the plain band
    (no allowance) would not give (c).
    Final review N1: 200 more portfolios with targets that are not whole % (weights like 3/7), moved by a random fraction:
    no status changes and no edge moves by more than 1e-11 (the 12-decimal sum can shift such an edge by about 1e-12)."""
    got = run(PLANW + """let seed = 20261113; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
      const ri = (a, b) => a + Math.floor(rnd() * (b - a + 1));
      const stats = { cases: 0, compared: 0, strict: 0, loose: 0, maxDiff: 0, laterWon: 0, firstWonClean: 0, firstWonOff: 0, usd: 0, changed: 0, eased: 0,
        oddCases: 0, oddCompared: 0, oddMax: 0, bad: [] };
      const clean = (k) => Math.round(k * 1e12) / 1e12 === k;
      // the plain band: the same portfolio with no whole-share allowance at all (every plan weight = its target)
      const plain = (d) => ({ ...d, holdings: d.holdings.map(({ plannedQty, planV, ...h }) => ({ ...h, planW: h.target })) });
      const mk = (odd = false) => {
        const n = ri(3, 8); let left = 100; let w = [];
        for (let i = 0; i < n - 1; i++) { const v = ri(5, Math.max(5, Math.min(40, left - 5 * (n - 1 - i)))); w.push(v); left -= v; }
        w.push(left);
        if (odd) { const raw = w.map(() => ri(3, 19)); const sum = raw.reduce((a, b) => a + b, 0); w = raw.map((x) => (x / sum) * 100); }   // 3/7, 5/31, …
        const usdAt = rnd() < 0.25 ? ri(0, n - 1) : -1, skip = rnd() < 0.33 ? ri(0, n - 1) : -1, A = [300, 500, 1000, 3000][ri(0, 3)] * 10000;
        const px = w.map((_, i) => (i === usdAt ? ri(5000, 90000) / 100 : ri(100, 15000) * 100));
        const q = (i) => Math.round((w[i] / 100) * A / (px[i] * (i === usdAt ? 1300 : 1)));
        const hs = w.map((v, i) => ({ t: i === usdAt ? 'USD' + i : CODES[i], nk: 's' + i, cls: i === usdAt ? 'us' : 'kr', ind: 'semi', kind: 'core', target: v / 100, setAt: '2026-10-01',
          plannedQty: q(i), planPx: px[i], rules: [pend('audit'), ...band(v / 100)] }));
        const d = { id: 'df', name: 'f', createdAt: '2026-10-01', planFx: 1300, settings: { points: { value: 3 }, maxPct: 100, amountMan: A / 10000 }, holdings: hs,
          purchases: hs.filter((h, i) => i !== skip && h.plannedQty > 0).map((h, i) => ({ id: 'p' + i + 'aaaaaa', t: h.t, qty: h.plannedQty, price: h.planPx, date: '2026-10-01',
            ccy: h.cls === 'us' ? 'USD' : 'KRW', ...(h.cls === 'us' ? { fx: 1300 } : {}) })) };
        const ctx = { state: { ok: true }, byT: new Map(hs.map((h, i) => [h.t, { t: h.t, nk: h.nk, cls: h.cls, ccy: h.cls === 'us' ? 'USD' : 'KRW', ind: 'semi', indName: 'x',
          price: h.cls === 'us' ? Math.round(px[i] * (0.8 + 0.4 * rnd()) * 100) / 100 : Math.round(px[i] * (0.8 + 0.4 * rnd())) }])), coByT: new Map(), fx: 1400, pxDate: T };
        return { d, ctx, usd: usdAt >= 0 };
      };
      const edit = (d) => {                                   // move 1–9 points from one stock to another (both stay 1% or more)
        for (let tries = 0; tries < 50; tries++) {
          const i = ri(0, d.holdings.length - 1), j = ri(0, d.holdings.length - 1);
          const pi = Math.round(d.holdings[i].target * 100), pj = Math.round(d.holdings[j].target * 100), k = ri(1, 9);
          if (i !== j && pi - k >= 1) return [[d.holdings[i].t, pi - k], [d.holdings[j].t, pj + k]];
        }
        return null;
      };
      const editOdd = (d) => {                                // move a random fraction of a point (targets stay non-whole; the sum is kept)
        for (let tries = 0; tries < 50; tries++) {
          const i = ri(0, d.holdings.length - 1), j = ri(0, d.holdings.length - 1), k = 0.5 + 3 * rnd();
          const pi = d.holdings[i].target * 100, pj = d.holdings[j].target * 100;
          if (i !== j && pi - k >= 1) return [[d.holdings[i].t, pi - k], [d.holdings[j].t, pj + k]];
        }
        return null;
      };
      const far = (a, b) => Math.max(...['target', 'gap', 'planW', 'now'].map((k) => Math.abs((a[k] ?? 0) - (b[k] ?? 0))), ...a.bands.map((x, i) => Math.abs(x - b.bands[i])));
      for (let c = 0; c < 600; c++) {
        const { d, ctx, usd } = mk();
        let cur = { v: 1, decks: [d] }, ts = env.ts;
        for (const round of ['first', 'later']) {
          const before = cur.decks[0], pairs = edit(before);
          if (!pairs) break;
          const r = E.applyEdit(cur, 'df', steps(pairs), { ...env, ts: (ts += 1000) });
          if (!r.ok) { stats.bad.push(['not saved', c, round, r.why]); break; }
          const after = r.data.decks[0], b0 = bandsOf(Ru.evaluateDeck(before, ctx)), b1 = bandsOf(Ru.evaluateDeck(after, ctx));
          stats.cases++;
          const sum = (x) => x.holdings.reduce((a, h) => a + (round === 'first' && x === before ? h.plannedQty * h.planPx * (h.cls === 'us' ? 1300 : 1) : h.planW), 0);
          if (!after.holdings.every((h) => typeof h.planW === 'number' && Number.isFinite(h.planW) && h.planW >= 0)) stats.bad.push(['weights', c, round]);
          if (usd ? Math.abs(sum(after) / sum(before) - 1) > 1e-12 : sum(after) !== sum(before)) stats.bad.push(['total', c, round, sum(before), sum(after)]);
          if (!S.validStore(r.data, T)) stats.bad.push(['store', c, round]);
          const touched = new Set(pairs.map((p) => p[0]));
          const heldTouched = pairs.filter((p) => b0[p[0]]).length;         // both changed stocks held, or neither: the held targets' sum is the same
          for (const t of Object.keys(b0)) {
            if (touched.has(t) || !b1[t] || heldTouched === 1) continue;
            stats.compared++;
            const same = JSON.stringify(b0[t]) === JSON.stringify(b1[t]), diff = far(b0[t], b1[t]);
            stats.maxDiff = Math.max(stats.maxDiff, diff);
            if (b0[t].status !== b1[t].status) stats.bad.push(['status', c, round, t]);
            if (same) stats.strict++; else stats.loose++;
            if (diff > 1e-12) stats.bad.push(['far', c, round, t, diff]);
            if (usd) stats.usd++;
            else if (round === 'later') { stats.laterWon++; if (!same) stats.bad.push(['later save not identical', c, t, diff]); }
            else if (clean(b0[t].scale)) { stats.firstWonClean++; if (!same) stats.bad.push(['first save not identical', c, t, diff]); }
            else stats.firstWonOff++;
          }
          // S-b: a changed holding reads as a brand-new plan (the same portfolio without planW, read from plannedQty);
          // (c): against the plain band its status only ever eases (never a new 일부 팔아요 or 먼저 사요)
          const fresh = bandsOf(Ru.evaluateDeck(noW(after), ctx)), p1 = bandsOf(Ru.evaluateDeck(plain(after), ctx));
          for (const h of after.holdings) {
            if (!b1[h.t]) continue;
            if (touched.has(h.t)) { stats.changed++;
              const f = fresh[h.t], x = b1[h.t];
              if (!f || f.status !== x.status || Math.abs(x.planW - f.planW) > 1e-15 || x.bands.some((v, i) => Math.abs(v - f.bands[i]) > 1e-12))
                stats.bad.push(['changed vs a brand-new plan', c, round, h.t, f && f.status, x.status, f && f.planW, x.planW]); }
            const a = b1[h.t].status, z = p1[h.t].status;
            if ((a === 'trim' && z !== 'trim') || (a === 'low' && z !== 'low') || (a === 'high' && z === 'none')) stats.bad.push(['allowance tightened', c, round, h.t, z, a]);
            if (a !== z) stats.eased++;
          }
          cur = r.data;
        }
      }
      // N1: targets that are not whole %
      for (let c = 0; c < 200; c++) {
        const { d, ctx } = mk(true);
        let cur = { v: 1, decks: [d] }, ts = env.ts;
        for (const round of ['first', 'later']) {
          const before = cur.decks[0], pairs = editOdd(before);
          if (!pairs) break;
          const r = E.applyEdit(cur, 'df', steps(pairs), { ...env, ts: (ts += 1000) });
          if (!r.ok) { stats.bad.push(['odd not saved', c, round, r.why]); break; }
          const b0 = bandsOf(Ru.evaluateDeck(before, ctx)), b1 = bandsOf(Ru.evaluateDeck(r.data.decks[0], ctx));
          stats.oddCases++;
          const touched = new Set(pairs.map((p) => p[0])), heldTouched = pairs.filter((p) => b0[p[0]]).length;
          for (const t of Object.keys(b0)) {
            if (touched.has(t) || !b1[t] || heldTouched === 1) continue;
            stats.oddCompared++;
            const diff = far(b0[t], b1[t]);
            stats.oddMax = Math.max(stats.oddMax, diff);
            if (b0[t].status !== b1[t].status) stats.bad.push(['odd status', c, round, t]);
            if (diff > 1e-11) stats.bad.push(['odd far', c, round, t, diff]);
          }
          cur = r.data;
        }
      }
      out = { ...stats, bad: stats.bad.slice(0, 5), nBad: stats.bad.length, warns: warns.length };""")
    assert got["nBad"] == 0, got["bad"]
    assert got["cases"] >= 1100 and got["compared"] >= 2000 and got["warns"] == 0, got
    # 세 경우 모두 충분히 봤어요 (이 씨앗: 나중 저장 804 · 첫 저장(깨끗한 합) 482 · 첫 저장(예전 합의 끝자리가 어긋난 경우) 291 · 달러 625)
    assert got["laterWon"] >= 700 and got["firstWonClean"] >= 400 and got["firstWonOff"] >= 100 and got["usd"] >= 300, got
    assert got["maxDiff"] < 1e-15 and got["strict"] / got["compared"] > 0.75, got               # 어긋나도 float 의 끝자리 (2.2e-16)
    assert got["changed"] >= 1500 and got["eased"] >= 100, got                                 # 바꾼 종목의 식 · 여유가 실제로 쓰인 경우도 충분히
    assert got["oddCases"] >= 380 and got["oddCompared"] >= 600 and got["oddMax"] < 1e-11, got  # 정수 % 가 아닌 목표: 1e-12 쯤까지 (상태는 그대로)


def test_an_old_format_portfolio_without_planw_reads_exactly_as_before():
    """A portfolio saved before planW (no holding has one) is read by the same lines as before: each plan weight is
    plannedQty × planPx (a dollar holding × the plan's rate) over their sum, to the last digit. planW is all or nothing: with
    only some holdings carrying a usable one (two copies met through an earlier app, a hand-made file) the plan is read from
    plannedQty as before and the console says so once. The stored weights are the plan's own values: their total is what every
    holding's whole planned shares are measured against (final review S2), so weights three times as large read every plan
    weight at a third."""
    got = run(PLANW + """const d = deck7();
      const us = { ...d, holdings: d.holdings.map((h, i) => (i === 1 ? { ...h, t: 'AAA', cls: 'us', planPx: 97.69, plannedQty: 16 } : h)) };
      const tg = (x) => new Map(x.holdings.map((h) => [h.t, h.target]));
      const hand = (x) => { const v = x.holdings.map((h) => h.plannedQty * h.planPx * (h.cls === 'us' ? x.planFx : 1)); const s = v.reduce((a, b) => a + b, 0); return v.map((y) => y / s); };
      const read = (x) => [...Ru.planWeights(x, tg(x)).values()];
      const some = { ...d, holdings: d.holdings.map((h, i) => (i < 3 ? { ...h, planW: 5 } : h)) };
      const w0 = warns.length; const a1 = read(some), a2 = read(some); const said = warns.slice(w0);
      const bad = { ...d, holdings: d.holdings.map((h, i) => ({ ...h, planW: i === 0 ? 'x' : i === 1 ? -1 : 7 })) };
      const zero = { ...d, holdings: d.holdings.map((h) => ({ ...h, planW: 0 })) };
      const stored = { ...d, holdings: d.holdings.map((h) => ({ ...h, planW: h.plannedQty * h.planPx })) };
      const x3 = { ...d, holdings: d.holdings.map((h) => ({ ...h, planW: 3 * h.plannedQty * h.planPx })) };
      out = { kr: [read(d), hand(d)], us: [read(us), hand(us)], some: [a1, a2], said, bad: read(bad), zero: read(zero), stored: read(stored),
        x3: Math.max(...read(x3).map((v, i) => Math.abs(v - hand(d)[i] / 3))), bandsSame: JSON.stringify(bandsOf(Ru.evaluateDeck(stored, ctx7))) === JSON.stringify(bandsOf(Ru.evaluateDeck(d, ctx7))) };""")
    assert got["kr"][0] == got["kr"][1] and got["us"][0] == got["us"][1]                       # 예전 그대로, 마지막 자리까지
    assert got["some"] == [got["kr"][1]] * 2 and got["bad"] == got["kr"][1] and got["zero"] == got["kr"][1]   # 일부만 · 못 쓰는 값 · 모두 0: plannedQty 로
    assert len(got["said"]) == 1 and "planW" in got["said"][0] and "3 of 7" in got["said"][0] and "plannedQty" in got["said"][0]   # 한 번, 이유와 함께
    assert got["stored"] == got["kr"][1] and got["bandsSame"] is True                         # 계획 금액을 planW 로 두면 같은 숫자
    assert got["x3"] < 1e-15                                                                   # 합이 세 배면 계획 비중은 3분의 1 (합이 기준이에요)


def test_planw_survives_export_import_and_rides_with_the_target_set_between_tabs():
    """기록 내보내기 → 기록 불러오기 keeps every holding's planW (and so the same bands). Two copies: the target set that was
    saved later wins whole (round-1 S1) and its plan weights come with it, never one copy's targets with the other's weights;
    a stale tab without a stamp never takes them back."""
    got = run(PLANW + """const b0 = { v: 1, decks: [deck7()] };
      const a = E.applyEdit(b0, 'd7', steps([['000010', 15], ['000020', 25]]), env).data;
      const file = S.exportText(a), inc = S.parseImport(file, T), back = S.mergeStores({ v: 1, decks: [] }, inc, env.ts + 5, [], T);
      const again = S.parseImport(S.exportText(back), T);
      const set = (x) => x.decks[0].holdings.map((h) => [h.t, h.target, h.plannedQty, h.planW ?? null]);
      // tab B opened before A's edit and writes a note (no stamp); then a tab that edited other targets a minute later
      const stale = { ...b0, notes: { '000010': { text: '메모', at: T } } };
      const b = E.applyEdit(b0, 'd7', steps([['000030', 10], ['000040', 20]]), { ...env, ts: env.ts + 60000 }).data;
      out = { a: set(a), b: set(b), file: file.includes('"planW"'), back: set(back), again: set(again), valid: [S.validStore(back, T), S.validStore(again, T)],
        bands: JSON.stringify(bandsOf(Ru.evaluateDeck(back.decks[0], ctx7))) === JSON.stringify(bandsOf(Ru.evaluateDeck(a.decks[0], ctx7))),
        stale: [set(S.mergeTabs(a, stale, T)), set(S.mergeTabs(stale, a, T))], both: [set(S.mergeTabs(a, b, T)), set(S.mergeTabs(b, a, T))] };""")
    assert got["file"] is True and got["back"] == got["a"] and got["again"] == got["a"] and got["valid"] == [True, True] and got["bands"] is True
    assert all(isinstance(x[3], int) for x in got["a"])
    assert got["stale"] == [got["a"], got["a"]]                                               # 도장 없는 예전 사본은 되돌리지 못해요
    assert got["both"] == [got["b"], got["b"]]                                                # 나중에 저장한 묶음이 통째로 (planW 도 같이)


@pytest.mark.parametrize("old", ["Old6", "OldM"])
def test_an_earlier_app_reads_a_portfolio_with_planw_and_sets_nothing_aside(old):
    """Old tabs keep working the old way. v19.6a and main (v19.3d2, tests/fixtures/old_client_7b5c895) do not know planW: each
    reads the store 종목 바꾸기 saved with nothing set aside and nothing moved to a backup key, still finds a whole plannedQty
    on every holding (what it reads the plan from), and its own write keeps planW, so this app reads the same bands after."""
    got = run(PLANW + f"""const r = E.applyEdit({{ v: 1, decks: [deck7()] }}, 'd7', steps([['000010', 15], ['000020', 25]]), env);
      mem.clear();
      const wroteNew = S.writeStore(r.data, K, T);
      const o = {old}.readStore(K, T);
      const od = o.data.decks[0];
      const wrote = {old}.writeStore({{ ...o.data, notes: {{ '000010': {{ text: '메모', at: T }} }} }}, K, T);
      const keys = [...mem.keys()];
      const back = S.readStore(K, T);
      out = {{ wroteNew, valid: {old}.validStore(r.data, T), locked: o.locked, problems: o.problems, decks: o.data.decks.length, keptW: ws(od), want: ws(r.data.decks[0]),
        qty: od.holdings.every((h) => Number.isInteger(h.plannedQty) && h.planPx > 0), wrote, keys, backLocked: back.locked, backProblems: back.problems,
        backW: ws(back.data.decks[0]), note: !!(back.data.notes && back.data.notes['000010']),
        bands: JSON.stringify(bandsOf(Ru.evaluateDeck(back.data.decks[0], ctx7))) === JSON.stringify(bandsOf(Ru.evaluateDeck(r.data.decks[0], ctx7))),
        merge: [{old}.mergeTabs(r.data, {{ v: 1, decks: [deck7()] }}, T), {old}.mergeTabs({{ v: 1, decks: [deck7()] }}, r.data, T)].map((m) => !!m && S.validStore(m, T) && {old}.validStore(m, T)) }};""")
    assert got["wroteNew"] is True and got["valid"] is True
    assert got["locked"] is False and got["problems"] == [] and got["decks"] == 1                 # 따로 둔 것이 없어요
    # 옆으로 옮긴 사본도 없어요 (.unreadable. · .other. · .restored. 열쇠 없음; .mine 은 새 앱이 마지막에 쓴 글 그대로 두는 열쇠)
    assert [k for k in got["keys"] if k not in ("baepsae2.v1", "baepsae2.v1.mine")] == [], got["keys"]
    assert got["qty"] is True and got["keptW"] == got["want"] and all(isinstance(x, int) for x in got["want"])
    assert got["wrote"] is True and got["backLocked"] is False and got["backProblems"] == [] and got["backW"] == got["want"] and got["note"] is True
    assert got["bands"] is True and got["merge"] == [True, True]


def test_planw_follows_a_removal_an_add_and_a_sale_and_is_never_half_stored():
    """Every save of a target set stores planW on every holding or on none. 기록 없이 빼기, 담기 and 팔고 빼기 change every
    target, so the weights are the plan's total shared by the new targets (the stock that left gives its weight to the ones
    its target went to). The first save of a portfolio whose plan cannot be read (a holding without planPx) stores none, says
    why in the console, and is read from plannedQty as before."""
    got = run(PLANW + """const d = deck7(), total = d.holdings.reduce((a, h) => a + h.plannedQty * h.planPx, 0);
      const rm = E.applyEdit({ v: 1, decks: [d] }, 'd7', E.removeDraft(d, E.emptyDraft(), '000070', 'other'), env).data.decks[0];
      const sam7 = { t: '005930', nk: '삼성전자', cls: 'kr', ind: 'semi', kind: 'pinned', s: sam(50000) };
      const add = E.applyEdit({ v: 1, decks: [d] }, 'd7', E.addDraft(d, E.emptyDraft(), sam7, 10), env).data.decks[0];
      const c = Rc.checkSale(d, '000070', { qty: String(q7(6)), price: '80000', date: T }, stock('000070', 80000), { today: T, fx: 1400 });
      const sold = E.sellAndRemove(Rc.withRecord({ v: 1, decks: [d] }, 'd7', 'sales', c.rec, T), 'd7', '000070', { reason: 'rule', load, today: T, ts: env.ts });
      const prop = (x) => { const s = x.holdings.reduce((a, h) => a + h.planW, 0); return Math.max(...x.holdings.map((h) => Math.abs(h.planW / s - h.target))); };
      const sums = (x) => x.holdings.reduce((a, h) => a + h.planW, 0);
      // a holding without planPx, and no planW stored yet: the plan cannot be read, nothing is stored
      const odd = { ...d, holdings: d.holdings.map((h, i) => { const { planPx, ...r } = h; return i === 6 ? r : h; }) };
      const w0 = warns.length;
      const o = E.applyEdit({ v: 1, decks: [odd] }, 'd7', steps([['000010', 15], ['000020', 25]]), env);
      const said = warns.slice(w0).filter((m) => m.includes('planW'));
      // a save that only raises the cap sets no target: nothing is rewritten
      const capOnly = E.applyEdit({ v: 1, decks: [d] }, 'd7', { ...E.emptyDraft(), maxPct: 60 }, env).data.decks[0];
      out = { total, rm: [sums(rm), prop(rm), rm.holdings.length], add: [sums(add), prop(add), add.holdings.length], sold: [sold.ok, sums(sold.data.decks[0]), prop(sold.data.decks[0]), sold.data.decks[0].holdings.length],
        ints: [rm, add, sold.data.decks[0]].every((x) => x.holdings.every((h) => Number.isInteger(h.planW))),
        odd: [o.ok, ws(o.data.decks[0]), S.validStore(o.data, T)], said, capOnly: [ws(capOnly), capOnly.settings.maxPct] };""")
    total = got["total"]
    assert got["rm"][0] == total and got["rm"][1] < 1e-6 and got["rm"][2] == 6                  # 뺀 종목의 몫은 남은 종목들에게, 합은 그대로
    assert got["add"][0] == total and got["add"][1] < 1e-6 and got["add"][2] == 8
    assert got["sold"][0] is True and got["sold"][1] == total and got["sold"][2] < 1e-6 and got["sold"][3] == 6
    assert got["ints"] is True
    assert got["odd"] == [True, [None] * 7, True]                                              # 계획을 읽을 수 없으면 아무도 planW 가 없어요 (반쪽 저장 없음)
    assert len(got["said"]) == 1 and "not stored" in got["said"][0] and "000070 has no plan price" in got["said"][0]
    assert got["capOnly"] == [[None] * 7, 60]


# ---------------- final review (2026-11-13): S2 the whole-share allowance · S3 a mixed copy · N2 · N3 ----------------
FINAL = PLANW + """// the reviewer's portfolio: a 500만원 plan, five stocks at 20%. A costs 1,500,000원 a share, so the plan itself buys 1 share
      // (150만원, 27.27% of the 550만원 the plan really buys)
      const SP = [{ t: '000010', w: 0.2, px: 1500000 }, { t: '000020', w: 0.2, px: 50000 }, { t: '000030', w: 0.2, px: 25000 }, { t: '000040', w: 0.2, px: 100000 },
        { t: '000050', w: 0.2, px: 200000 }];
      // a built portfolio: specs [{ t, w, px, q (shares bought; the planned count unless given) }], the plan's amount in 만원
      const mkD = (specs, amountMan) => { const A = amountMan * 10000;
        const hs = specs.map((x, i) => ({ t: x.t, nk: '종목' + (i + 1), cls: 'kr', ind: 'semi', kind: 'core', target: x.w, setAt: '2026-10-01',
          plannedQty: Math.round(x.w * A / x.px), planPx: x.px, rules: [pend('audit'), ...band(x.w)] }));
        return { id: 'd1', name: '시험', createdAt: '2026-10-01', planFx: 1300, settings: { points: { value: 3 }, maxPct: 30, amountMan }, holdings: hs,
          purchases: specs.map((x, i) => ({ x, i })).filter(({ x, i }) => (x.q != null ? x.q : hs[i].plannedQty) > 0)
            .map(({ x, i }) => ({ id: 'p' + i + 'aaaaaa', t: x.t, qty: x.q != null ? x.q : hs[i].plannedQty, price: x.px, date: '2026-10-01', ccy: 'KRW' })) }; };
      const ctxS = (specs, k = 1) => ({ state: { ok: true }, byT: new Map(specs.map((x) => [x.t, stock(x.t, Math.round(x.px * k))])), coByT: new Map(), fx: 1400, pxDate: T });
      const envS = (specs) => ({ load: { status: 'ok', data: { fx: 1400, stocks: [] }, coByT: new Map(), byT: new Map(specs.map((x) => [x.t, stock(x.t, x.px)])) }, today: T, ts: env.ts });
      const pct = (v) => Math.round(v * 10000) / 100;
      const rowOf = (d, specs, t) => { const b = bandsOf(Ru.evaluateDeck(d, ctxS(specs)))[t]; return [b.status, pct(b.now), b.bands.map(pct), pct(b.gap)]; };
      const plain = (d) => ({ ...d, holdings: d.holdings.map(({ plannedQty, planV, ...h }) => ({ ...h, planW: h.target })) });
"""


def test_a_changed_holding_keeps_the_whole_share_allowance():
    """Final review S2. A 500만원 plan, five stocks at 20%; stock A costs 150만원 a share, so the plan buys 1 share: 27.27% of
    what the plan really buys. Three rows, and A reads 할 일 없음 in all three (it is one share: the user could never clear a
    더 안 사요):
    - the fresh plan: A's 더 안 사요 edge is 32.27% (25% + the 7.27 points its one share is above its 20%);
    - after A 20 → 19 and B 20 → 21: 31.78% (23.75% + 150만 ÷ 555만 − 19%: a brand-new plan with these targets buys 555만,
      verification S-b; it was 32.02% over the stored 550만). The three untouched stocks read exactly as before;
    - after E is taken out (기록 없이 빼기, and the same through 팔고 빼기; the four left go to 25%): 34.55% (150만 ÷ 530만, the
      brand-new plan) against A's 33.33% (it was 33.52%).
    Without the allowance (the plain band) the two saves read A as 더 안 사요. The allowance never tightens anything."""
    got = run(FINAL + """const d0 = mkD(SP, 500), en = envS(SP);
      const cut = E.applyEdit({ v: 2, decks: [d0] }, 'd1', steps([['000010', 19], ['000020', 21]]), en).data.decks[0];
      const rm = E.applyEdit({ v: 2, decks: [d0] }, 'd1', E.removeDraft(d0, E.emptyDraft(), '000050', 'other'), en).data.decks[0];
      const c = Rc.checkSale(d0, '000050', { qty: '5', price: '200000', date: T }, stock('000050', 200000), { today: T, fx: 1400 });
      const sold = E.sellAndRemove(Rc.withRecord({ v: 2, decks: [d0] }, 'd1', 'sales', c.rec, T), 'd1', '000050', { reason: 'other', load: en.load, today: T, ts: env.ts });
      const all = (d) => Object.values(bandsOf(Ru.evaluateDeck(d, ctxS(SP)))).map((b) => b.status);
      const b0 = bandsOf(Ru.evaluateDeck(d0, ctxS(SP))), b1 = bandsOf(Ru.evaluateDeck(cut, ctxS(SP)));
      out = { plan: d0.holdings.map((h) => h.plannedQty * h.planPx), fresh: rowOf(d0, SP, '000010'), cut: rowOf(cut, SP, '000010'), cutB: rowOf(cut, SP, '000020'),
        rm: rowOf(rm, SP, '000010'), sold: [sold.ok, rowOf(sold.data.decks[0], SP, '000010')], all: [all(d0), all(cut), all(rm), all(sold.data.decks[0])],
        untouched: ['000030', '000040', '000050'].every((t) => JSON.stringify(b0[t]) === JSON.stringify(b1[t])),
        w: [ws(cut), ws(rm)], q: [cut.holdings.map((h) => h.plannedQty), rm.holdings.map((h) => h.plannedQty)],
        plain: [rowOf(plain(d0), SP, '000010')[0], rowOf(plain(cut), SP, '000010'), rowOf(plain(rm), SP, '000010')], warns };""")
    assert got["warns"] == [] and got["plan"] == [1500000, 1000000, 1000000, 1000000, 1000000]
    assert got["fresh"] == ["none", 27.27, [15, 32.27, 35.27], 7.27]
    assert got["cut"] == ["none", 27.27, [14.25, 31.78, 34.63], 8.03]                          # 1주 그대로: 새 계획처럼 150만 ÷ 555만, 목표 19%
    assert got["cutB"] == ["none", 18.18, [13.67, 26.25, 29.4], -2.08]                         # B: 21주 = 105만 ÷ 555만 = 18.92% (목표 21% 아래로 2.08)
    assert got["rm"] == ["none", 33.33, [18.75, 34.55, 38.3], 3.3]                             # 새 계획처럼 150만 ÷ 530만
    assert got["sold"] == [True, got["rm"]]                                                    # 팔고 빼기도 같은 선
    assert got["all"] == [["none"] * 5, ["none"] * 5, ["none"] * 4, ["none"] * 4]              # 세 줄 모두, 모든 종목 할 일 없음
    assert got["untouched"] is True                                                            # 안 바꾼 셋은 마지막 자리까지 그대로
    assert got["w"] == [[1187500, 1312500, 1000000, 1000000, 1000000], [1375000] * 4]          # 저장된 계획 비중: 합은 늘 550만
    assert got["q"] == [[1, 21, 40, 10, 5], [1, 25, 50, 13]]
    # 여유가 없다면 (목표 그대로의 선): 처음 계획도 두 저장도 A 는 더 안 사요 — 1주라 지울 수 없는 말
    assert got["plain"][0] == "high" and got["plain"][1][:2] == ["high", 27.27] and got["plain"][1][2][1] == 23.75
    assert got["plain"][2][:2] == ["high", 33.33] and got["plain"][2][2][1] == 31.25


def test_a_changed_holding_reads_as_a_brand_new_plan_with_the_same_targets_prices_and_total():
    """Final review S2 (b). The same plan with B at 400,000원 a share: 20% and 21% both buy 3 shares and A stays at 1, so a
    brand-new plan with the new targets (19 / 21 / 20 / 20 / 20), the same prices and the same amount adds up to the same
    total (570만원). The edited portfolio then reads A and B digit for digit as that brand-new plan does (same shares held).
    When a new plannedQty changes what the planned values add up to, the changed stocks still read as the brand-new plan
    does (verification S-b, planV) and the untouched ones keep measuring against the total they had."""
    got = run(FINAL + """const sp = SP.map((x) => (x.t === '000020' ? { ...x, px: 400000 } : x));
      const d0 = mkD(sp, 500);
      const cut = E.applyEdit({ v: 2, decks: [d0] }, 'd1', steps([['000010', 19], ['000020', 21]]), envS(sp)).data.decks[0];
      const neu = mkD(sp.map((x, i) => ({ ...x, w: [0.19, 0.21, 0.2, 0.2, 0.2][i], q: d0.holdings[i].plannedQty })), 500);   // never edited: read from plannedQty
      const sum = (d, f) => d.holdings.reduce((a, h) => a + f(h), 0);
      const be = bandsOf(Ru.evaluateDeck(cut, ctxS(sp, 1.04))), bn = bandsOf(Ru.evaluateDeck(neu, ctxS(sp, 1.04)));
      out = { totals: [sum(d0, (h) => h.plannedQty * h.planPx), sum(neu, (h) => h.plannedQty * h.planPx), sum(cut, (h) => h.planW)], hasW: [ws(neu).every((x) => x == null), ws(cut).every((x) => x != null)],
        q: [cut.holdings.map((h) => h.plannedQty), neu.holdings.map((h) => h.plannedQty)], same: Object.keys(be).map((t) => JSON.stringify(be[t]) === JSON.stringify(bn[t])),
        a: [be['000010'].status, pct(be['000010'].planW), pct(be['000010'].gap)] };""")
    assert got["totals"] == [5700000, 5700000, 5700000] and got["hasW"] == [True, True] and got["q"][0] == got["q"][1] == [1, 3, 40, 10, 5]
    assert got["same"] == [True] * 5                                                           # 바꾼 A · B 도, 안 바꾼 셋도 새 계획과 한 글자도 다르지 않아요
    assert got["a"][1:] == [26.32, 7.32]                                                       # A: 150만 ÷ 570만 = 26.32% (목표 19% 위로 7.32)


def test_a_mixed_copy_keeps_the_plan_weights_it_has():
    """Final review S3 (the reviewer's case). Seven stocks, the last never bought. A first save changes two held stocks (planW
    on all seven). Then the never-bought stock loses its planW (as a holding brought back from an older file has none): the
    band rule still reads the six held ones from planW. A second save changing two other held stocks must keep every stored
    planW as it is and work out only the missing one (its plan value), with one console line: the four untouched held stocks
    read the same to the last digit. (Before: the save recomputed all seven from plannedQty × planPx; 000010 went from
    1,390,800 to 1,387,000 and its band moved.)"""
    got = run(FINAL + """const sp = [{ t: '000010', w: 0.20, px: 73000 }, { t: '000020', w: 0.15, px: 251000 }, { t: '000030', w: 0.15, px: 48700 }, { t: '000040', w: 0.15, px: 612000 },
        { t: '000050', w: 0.15, px: 9130 }, { t: '000060', w: 0.10, px: 133500 }, { t: '000070', w: 0.10, px: 87000, q: 0 }];
      const d0 = { ...mkD(sp, 1000), settings: { points: { value: 3 }, maxPct: 50, amountMan: 1000 } }, cx = ctxS(sp, 1.03);
      const s1 = E.applyEdit({ v: 2, decks: [d0] }, 'd1', steps([['000010', 14], ['000020', 21]]), envS(sp)).data;
      const mixed = { ...s1, decks: [{ ...s1.decks[0], holdings: s1.decks[0].holdings.map((h) => { if (h.t !== '000070') return h; const { planW, ...r } = h; return r; }) }] };
      const b0 = bandsOf(Ru.evaluateDeck(mixed.decks[0], cx));
      const held = new Map(mixed.decks[0].holdings.filter((h) => h.t !== '000070').map((h) => [h.t, h.target]));
      const w0 = warns.length;
      const s2 = E.applyEdit(mixed, 'd1', steps([['000030', 10], ['000040', 20]]), { ...envS(sp), ts: env.ts + 1000 }).data;
      const said = warns.slice(w0);
      const b1 = bandsOf(Ru.evaluateDeck(s2.decks[0], cx));
      out = { stored: Ru.planWeights(mixed.decks[0], held).stored === true, before: ws(mixed.decks[0]), after: ws(s2.decks[0]), said,
        same: ['000010', '000020', '000050', '000060'].map((t) => JSON.stringify(b0[t]) === JSON.stringify(b1[t])), valid: S.validStore(s2, T),
        base: (() => { const b = E.planBase(mixed.decks[0]); return [b.had, b.filled, b.unknown]; })() };""")
    assert got["stored"] is True and got["valid"] is True
    assert got["before"][0] == 1390800 and got["before"][6] is None and got["base"] == [6, ["000070"], []]
    after = got["after"]
    assert after[0] == 1390800 and after[1] == got["before"][1] and after[4:6] == got["before"][4:6]   # 있던 값은 그대로 (000010 은 1,390,800 그대로)
    assert after[6] == round(0.10 * 1e7 / 87000) * 87000                                       # 없던 것만 계획 금액으로 (11주 × 87,000원)
    assert after[2] + after[3] == got["before"][2] + got["before"][3]                          # 바꾼 둘은 둘이 가졌던 만큼
    assert got["same"] == [True] * 4                                                           # 안 바꾼 넷의 선은 마지막 자리까지 그대로
    assert len(got["said"]) == 1 and "were stored for 6 of 7" in got["said"][0] and "000070" in got["said"][0] and "kept as they are" in got["said"][0]


def test_a_planw_that_cannot_be_used_counts_as_missing_and_sets_nothing_aside():
    """Final review N2. planW must be a number that adds up: finite, 0 or more, and at most twice the plan's total (verification
    N2; it was 1,000 ×). 1e308,
    NaN, a string, a negative number, an object and a number above the ceiling all count as missing: the store still reads
    (nothing is set aside), the band rule falls back to plannedQty and says so once, 종목 바꾸기 works the weight out again at
    the next save and says so, and no sum ever becomes Infinity or NaN. 0 is a real weight (final review N3): a portfolio
    with one is still read from planW, with no console line. Weights that are numbers but add up to next to nothing under
    real planned values (all 5e-324) are not used either (every band would be widened without end). A plan value that is
    not a usable number (a plan price of 1e308) is never written as a weight."""
    got = run(FINAL + """const d0 = deck7();
      const s1 = E.applyEdit({ v: 1, decks: [d0] }, 'd7', steps([['000010', 15], ['000020', 25]]), env).data, d1 = s1.decks[0];
      const tg = new Map(d1.holdings.map((h) => [h.t, h.target]));
      const hand = (() => { const v = d1.holdings.map((h) => h.plannedQty * h.planPx); const s = v.reduce((a, b) => a + b, 0); return v.map((y) => y / s); })();
      const res = {};
      const limit = S.planWLimit(d1);
      for (const [name, v] of [['huge', 1e308], ['nan', NaN], ['text', '2500000'], ['neg', -1], ['obj', {}], ['over', limit * 1.01]]) {
        const bad = { ...d1, id: 'bad-' + name, holdings: d1.holdings.map((h, i) => (i === 3 ? { ...h, planW: v } : h)) };
        const w0 = warns.length;
        const read = [...Ru.planWeights(bad, tg).values()], again = Ru.planWeights(bad, tg);
        const e = Ru.evaluateDeck(bad, ctx7);
        const saidRead = warns.slice(w0); const w1 = warns.length;
        const r = E.applyEdit({ v: 1, decks: [bad] }, bad.id, steps([['000050', 5], ['000060', 15]]), { ...env, ts: env.ts + 1000 });
        res[name] = { valid: S.validStore({ v: 1, decks: [bad] }, T), fallback: JSON.stringify(read) === JSON.stringify(hand), stored: again.stored === true,
          finite: e.holdings.every((x) => x.rules.filter((y) => y.id === 'band').every((y) => y.bands.every(Number.isFinite) && Number.isFinite(y.planW))),
          saidRead: saidRead.length, saidWhat: saidRead[0] || '', ok: r.ok, fixed: r.data.decks[0].holdings[3].planW, kept: r.data.decks[0].holdings[0].planW,
          saidSave: warns.slice(w1).filter((m) => m.includes('were stored for 6 of 7')).length, validAfter: S.validStore(r.data, T) };
      }
      // every weight a number, their total next to nothing: not used (finite bands), said once
      const tiny = { ...d1, id: 'tiny', holdings: d1.holdings.map((h) => ({ ...h, planW: 5e-324 })) };
      const w3 = warns.length, tinyRead = [...Ru.planWeights(tiny, tg).values()], tinyE = Ru.evaluateDeck(tiny, ctx7), tinySaid = warns.slice(w3);
      // a plan price of 1e308: the plan value overflows; the first save stores no weight and says why
      const inf = { ...d0, id: 'inf', holdings: d0.holdings.map((h, i) => (i === 3 ? { ...h, planPx: 1e308, plannedQty: 1000 } : h)) };
      const w4 = warns.length, infSave = E.applyEdit({ v: 1, decks: [inf] }, 'inf', steps([['000010', 15], ['000020', 25]]), env), infSaid = warns.slice(w4).filter((m) => m.includes('not stored'));
      // 0 is a real weight
      const zero = { ...d1, id: 'zero', holdings: d1.holdings.map((h, i) => (i === 3 ? { ...h, planW: 0 } : h)) };
      const w2 = warns.length, z = Ru.planWeights(zero, tg);
      out = { tiny: [JSON.stringify(tinyRead) === JSON.stringify(hand), tinyE.holdings.every((x) => x.rules.filter((y) => y.id === 'band').every((y) => y.bands.every(Number.isFinite))),
          tinySaid.length, tinySaid[0] || ''], inf: [infSave.ok, ws(infSave.data.decks[0]), infSaid.length, infSaid[0] || ''], res, limit, want3: d1.holdings[3].plannedQty * d1.holdings[3].planPx, w0: d1.holdings[0].planW,
        zero: [z.stored === true, warns.length - w2, Math.abs(z.get('000040') - (d1.holdings[3].plannedQty * d1.holdings[3].planPx) / (d1.holdings.reduce((a, h) => a + h.planW, 0) - d1.holdings[3].planW)) < 1e-15,
          S.planWOk(0, limit), E.planBase(zero).had] };""")
    assert got["limit"] == 2 * 1000 * 10000                                                   # 계획 금액 1,000만원의 두 배 (검증 N2, 전에는 1,000배)
    for name, x in got["res"].items():
        assert x["valid"] is True and x["validAfter"] is True, name                             # 따로 두지 않아요
        assert x["fallback"] is True and x["stored"] is False and x["finite"] is True, name     # plannedQty 로 읽어요 (예전 줄 그대로), 숫자는 모두 유한
        assert x["saidRead"] == 1 and "6 of 7" in x["saidWhat"] and "planW" in x["saidWhat"], (name, x["saidWhat"])   # 한 번, 이유와 함께
        assert ("000040: " + {"huge": "too large", "nan": "not a number", "text": "not a number", "neg": "negative", "obj": "not a number", "over": "too large"}[name]) in x["saidWhat"], x["saidWhat"]
        assert x["ok"] is True and x["fixed"] == got["want3"] and x["kept"] == got["w0"] and x["saidSave"] == 1, name   # 다음 저장: 그 하나만 계획 금액으로, 나머지는 그대로
    assert got["zero"] == [True, 0, True, True, 7]                                             # 0 은 쓸 수 있는 값 (그 종목 몫이 0), 말없이 planW 로 읽어요
    assert got["tiny"][:3] == [True, True, 1] and "far too small" in got["tiny"][3]            # 합이 터무니없이 작으면 쓰지 않아요 (선은 유한한 숫자 그대로)
    assert got["inf"][:3] == [True, [None] * 7, 1] and "000040 has a plan value that is not a usable number" in got["inf"][3]


def test_a_later_target_set_without_planw_takes_this_copys_planw_away():
    """Final review N3 (store.js withTargetSet). When the target set that was saved later carries no planW (a copy from an
    earlier app, or a file from before planW), the holdings it covers lose this copy's planW with it: never the later
    targets with the earlier weights."""
    got = run(PLANW + """const b0 = { v: 1, decks: [deck7()] };
      const a = E.applyEdit(b0, 'd7', steps([['000010', 15], ['000020', 25]]), env).data;                 // this copy: targets A, with planW
      const later = E.applyEdit(b0, 'd7', steps([['000030', 10], ['000040', 20]]), { ...env, ts: env.ts + 60000 }).data;
      const old = { ...later, decks: [noW(later.decks[0])] };                                            // the later set, as a copy without planW holds it
      const set = (x) => x.decks[0].holdings.map((h) => [h.t, h.target, h.planW ?? null]);
      out = { a: set(a), old: set(old), merged: [set(S.mergeTabs(a, old, T)), set(S.mergeTabs(old, a, T))], valid: S.validStore(S.mergeTabs(a, old, T), T) };""")
    assert all(x[2] is not None for x in got["a"]) and all(x[2] is None for x in got["old"])
    assert got["merged"] == [got["old"], got["old"]] and got["valid"] is True                 # 나중 묶음의 목표, planW 는 없음 (앞 사본 것이 남지 않아요)


def test_the_us_date_line_follows_the_records_currency():
    """Final review N3 (records.jsx RecordForm): the line under the date field shows for a dollar record only. Its switch is
    the currency the saved record will carry (records.recordCcy), never a constant. (smoke_v2 scene_v196a checks the screens:
    a Korean stock's forms show no line, a US stock's three forms do.)"""
    with open(os.path.join(ROOT, "src", "v2", "records.jsx"), encoding="utf-8") as f:
        form = f.read().split("function RecordForm", 1)[1].split("function SaleResult", 1)[0]
    assert 'const usd = recordCcy(deck, t, s) === "USD";' in form
    assert form.count("{usd && <p data-ui-v2=\"rec-us-date\"") == 1 and "C.rec.usDateHint" in form


# ---------------- verification (2026-11-13): S-b a changed holding reads as a brand-new plan (planV) · N2 ----------------
def test_a_changed_holding_reads_as_a_brand_new_plan_both_ways():
    """Verification S-b (the verifier's case). A 300만원 plan: A 390,000원 a share at 30% (2 shares), B 1,500,000원 at 20% (the
    plan buys 0: one share is more than its 60만원; the user bought 1 anyway), C 10,000원 at 50% (150 shares). One save: A 30 →
    25, B 20 → 25 (B's plannedQty becomes 1). Every changed stock then reads exactly as a brand-new plan with the same targets,
    prices and amount reads it (the same portfolio without planW), today and with B's price doubled or tripled: at twice the
    price B reads 일부 팔아요 as the brand-new plan does (the rule as built before read 할 일 없음, a hidden warning). C, which the
    save did not touch, reads exactly as before the save. A second save (A 25 → 20, C 50 → 55) leaves B as it was, digit for
    digit (its planV stays)."""
    got = run(FINAL + """const sp = [{ t: '000010', w: 0.30, px: 390000 }, { t: '000020', w: 0.20, px: 1500000, q: 1 }, { t: '000030', w: 0.50, px: 10000 }];
      const d0 = { ...mkD(sp, 300), settings: { points: { value: 3 }, maxPct: 60, amountMan: 300 } };
      const cx = (k) => ({ state: { ok: true }, byT: new Map(sp.map((x) => [x.t, stock(x.t, x.t === '000020' ? x.px * k : x.px)])), coByT: new Map(), fx: 1400, pxDate: T });
      const s1 = E.applyEdit({ v: 2, decks: [d0] }, 'd1', steps([['000010', 25], ['000020', 25]]), envS(sp)).data, d1 = s1.decks[0];
      const s2 = E.applyEdit(s1, 'd1', steps([['000010', 20], ['000030', 55]]), { ...envS(sp), ts: env.ts + 1000 }).data, d2 = s2.decks[0];
      const at = (k) => { const e = bandsOf(Ru.evaluateDeck(d1, cx(k))), f = bandsOf(Ru.evaluateDeck(noW(d1), cx(k))), b = bandsOf(Ru.evaluateDeck(d0, cx(k)));
        return { st: Object.values(e).map((x) => x.status), fresh: Object.values(f).map((x) => x.status),
          changed: ['000010', '000020'].map((t) => e[t].status === f[t].status && Math.abs(e[t].planW - f[t].planW) < 1e-15 && e[t].bands.every((v, i) => Math.abs(v - f[t].bands[i]) < 1e-12)),
          c: JSON.stringify(e['000030']) === JSON.stringify(b['000030']), bAfter: JSON.stringify(bandsOf(Ru.evaluateDeck(d2, cx(k)))['000020']) === JSON.stringify(e['000020']) }; };
      out = { q: d1.holdings.map((h) => h.plannedQty), v: d1.holdings.map((h) => h.planV ?? null), v2: d2.holdings.map((h) => h.planV ?? null), x1: at(1), x2: at(2), x3: at(3), warns };""")
    assert got["warns"] == [] and got["q"] == [2, 1, 150]
    assert got["v"][0] is not None and got["v"][1] is not None and got["v"][2] is None          # 바꾼 둘만 planV
    assert got["v2"][1] == got["v"][1]                                                          # 두 번째 저장이 건드리지 않은 B 는 그대로
    for k in ("x1", "x2", "x3"):
        x = got[k]
        assert x["changed"] == [True, True] and x["c"] is True and x["bAfter"] is True, (k, x)   # 바꾼 둘은 새 계획과 같고, 안 바꾼 C 는 저장 전과 같아요
    assert got["x2"]["st"][1] == "trim" and got["x2"]["fresh"][1] == "trim"                     # B 가격 두 배: 새 계획처럼 일부 팔아요


def test_planv_survives_export_import_merges_and_an_earlier_apps_write():
    """planV (verification S-b) travels with the target set like planW: 기록 내보내기 → 불러오기 keeps it; when two copies meet,
    the later target set wins whole with its planV (never one copy's targets with the other's planV); v19.6a and main
    (fixtures) read a store with it, set nothing aside and keep it when they write."""
    got = run(PLANW + """const b0 = { v: 1, decks: [deck7()] };
      const a = E.applyEdit(b0, 'd7', steps([['000010', 15], ['000020', 25]]), env).data;
      const b = E.applyEdit(b0, 'd7', steps([['000030', 10], ['000040', 20]]), { ...env, ts: env.ts + 60000 }).data;
      const vs = (x) => x.decks[0].holdings.map((h) => h.planV ?? null);
      const back = S.mergeStores({ v: 1, decks: [] }, S.parseImport(S.exportText(a), T), env.ts + 5, [], T);
      const olds = {};
      for (const [name, O] of [['Old6', Old6], ['OldM', OldM]]) {
        mem.clear(); S.writeStore(a, K, T);
        const o = O.readStore(K, T);
        const wrote = O.writeStore({ ...o.data, notes: { '000010': { text: '메모', at: T } } }, K, T);
        const r = S.readStore(K, T);
        olds[name] = { locked: o.locked, problems: o.problems, wrote, v: vs(r.data), backLocked: r.locked };
      }
      out = { a: vs(a), b: vs(b), back: vs(back), merged: [vs(S.mergeTabs(a, b, T)), vs(S.mergeTabs(b, a, T))], olds,
        bands: JSON.stringify(bandsOf(Ru.evaluateDeck(back.decks[0], ctx7))) === JSON.stringify(bandsOf(Ru.evaluateDeck(a.decks[0], ctx7))) };""")
    a, b = got["a"], got["b"]
    assert a[0] is not None and a[1] is not None and a[2:] == [None] * 5 and b[2] is not None and b[3] is not None
    assert got["back"] == a and got["bands"] is True
    assert got["merged"] == [b, b]                                                              # 나중 묶음이 통째로 (planV 도 같이)
    for name, o in got["olds"].items():
        assert o["locked"] is False and o["problems"] == [] and o["wrote"] is True and o["v"] == a and o["backLocked"] is False, (name, o)


def test_one_stored_weight_cannot_put_a_band_edge_below_0_and_bad_weights_are_worked_out_again():
    """Verification N2. (1) A stored planW is unusable above twice the plan's total (it was 1,000 ×). One at that limit on a
    plan bought in full leaves every edge at 0 or more; in a plan only partly bought, where one at the limit would put a held
    stock's 먼저 사요 edge below 0, the stored weights are not used (the bands read plannedQty, said once). (2) Weights that are
    numbers but add up to next to nothing (all 1e-9) are not written back by the next save: every one is worked out again
    from the plan, with a console line. (3) A save over weights none of which can be used (all strings) says so too."""
    got = run(PLANW + """const s1 = E.applyEdit({ v: 1, decks: [deck7()] }, 'd7', steps([['000010', 15], ['000020', 25]]), env).data, d1 = s1.decks[0];
      const lim = S.planWLimit(d1), plan = d1.holdings.map((h) => h.plannedQty * h.planPx);
      const setW = (d, i, v) => ({ ...d, holdings: d.holdings.map((h, j) => (j === i ? { ...h, planW: v } : h)) });
      const lows = (d, cx) => { const w0 = warns.length; const e = Ru.evaluateDeck(d, cx);
        return { low: Math.min(...e.holdings.map((x) => x.rules.find((r) => r.id === 'band').bands[0])), stored: !!Ru.planWeights(d, new Map(e.holdings.map((x) => [x.t, x.planTarget]))).stored, said: warns.slice(w0) }; };
      // partly bought: only the first two stocks held
      const part = { ...d1, id: 'part', purchases: d1.purchases.filter((p) => ['000010', '000020'].includes(p.t)) };
      const tiny = { ...d1, id: 'tiny', holdings: d1.holdings.map((h) => ({ ...h, planW: 1e-9 })) };
      const w1 = warns.length, rt = E.applyEdit({ v: 1, decks: [tiny] }, 'tiny', steps([['000050', 5], ['000060', 15]]), { ...env, ts: env.ts + 1000 }), saidT = warns.slice(w1);
      const text = { ...d1, id: 'text', holdings: d1.holdings.map((h) => ({ ...h, planW: String(h.planW) })) };
      const w2 = warns.length, rx = E.applyEdit({ v: 1, decks: [text] }, 'text', steps([['000050', 5], ['000060', 15]]), { ...env, ts: env.ts + 2000 }), saidX = warns.slice(w2);
      out = { lim, full: lows(setW(d1, 3, lim), ctx7), part: lows(setW(part, 1, lim), ctx7), partOk: lows(part, ctx7), over: S.planWOk(lim * 1.0001, lim), at: S.planWOk(lim, lim),
        tiny: [rt.ok, ws(rt.data.decks[0]), saidT], text: [rx.ok, ws(rx.data.decks[0]), saidX], plan };""")
    assert got["lim"] == 2 * 1000 * 10000 and got["at"] is True and got["over"] is False        # 계획 금액 1,000만원의 두 배까지
    assert got["full"]["stored"] is True and got["full"]["low"] >= 0                             # 다 산 계획: 한계의 값이어도 선은 0 이상
    assert got["partOk"]["stored"] is True and got["partOk"]["low"] >= 0
    assert got["part"]["stored"] is False and got["part"]["low"] >= 0                            # 일부만 산 계획: 0 아래로 갈 값은 쓰지 않아요
    assert len(got["part"]["said"]) == 1 and "below a quarter of its target" in got["part"]["said"][0]
    tiny = got["tiny"]
    assert tiny[0] is True and min(tiny[1]) > 1000                                               # 아주 작은 값은 다시 쓰지 않아요 (계획 금액으로 다시)
    assert sum(tiny[1]) == sum(got["plan"])
    assert any("not kept" in m and "far too small" in m for m in tiny[2]), tiny[2]
    text = got["text"]
    assert text[0] is True and all(isinstance(x, int) for x in text[1]) and sum(text[1]) == sum(got["plan"])
    assert any("not kept" in m and "not a usable number" in m for m in text[2]), text[2]


# ---------------- review (2026-11-13): S1 two pools · N4 an unusable planV ----------------
def test_a_mixed_save_that_keeps_the_held_total_moves_no_untouched_held_band():
    """Review S1 (the reviewer's case and a fuzz). A save that changes held and never-bought stocks together, while the held
    stocks' targets keep their total, used to share the plan weight as one pool, so an untouched held stock's 더 안 사요 edge
    moved (44.05% → 42.82%). Now the changed held stocks share only what they had (the never-bought ones share the rest), so
    every untouched held band stays the same to the last digit, and every changed held stock still reads exactly as a
    brand-new plan (planV). 400 random portfolios (two stocks never bought), each saved twice: weight moved among held stocks,
    then a mixed save (two held, two never bought, the held total unchanged). A save whose held total changes still moves
    them by the existing rule; such saves are not compared."""
    got = run(FINAL + """// the reviewer's case
      const sp = [{ t: '000010', w: 0.20, px: 10000 }, { t: '000020', w: 0.30, px: 1300000 }, { t: '000030', w: 0.10, px: 10000 },
        { t: '000040', w: 0.20, px: 10000, q: 0 }, { t: '000050', w: 0.20, px: 10000, q: 0 }];
      const d0 = { ...mkD(sp, 1000), settings: { points: { value: 3 }, maxPct: 60, amountMan: 1000 } }, cx = ctxS(sp);
      const s1 = E.applyEdit({ v: 2, decks: [d0] }, 'd1', steps([['000020', 29], ['000030', 11]]), envS(sp)).data;
      const s2 = E.applyEdit(s1, 'd1', steps([['000020', 24], ['000030', 16], ['000040', 15], ['000050', 25]]), { ...envS(sp), ts: env.ts + 1000 }).data;
      const u = (s) => bandsOf(Ru.evaluateDeck(s.decks[0], cx))['000010'];
      const res = { case: [JSON.stringify(u(s1)) === JSON.stringify(u(s2)), u(s2).bands.map(pct)], total: [s1, s2].map((s) => s.decks[0].holdings.reduce((a, h) => a + h.planW, 0)) };
      // the fuzz
      let seed = 1113; const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
      const ri = (a, b) => a + Math.floor(rnd() * (b - a + 1));
      const st = { cases: 0, compared: 0, moved: 0, changed: 0, notFresh: 0, statusDiff: 0, bad: [] };
      for (let c = 0; c < 400; c++) {
        const n = ri(5, 8); let left = 100; const w = [];
        for (let i = 0; i < n - 1; i++) { const v = ri(6, Math.max(6, Math.min(30, left - 6 * (n - 1 - i)))); w.push(v); left -= v; }
        w.push(left);
        const specs = w.map((v, i) => ({ t: CODES[i], w: v / 100, px: ri(10, 3000) * 100, ...(i >= n - 2 ? { q: 0 } : {}) }));
        const d = { ...mkD(specs, [300, 1000, 3000][ri(0, 2)]), settings: { points: { value: 3 }, maxPct: 100, amountMan: 1000 } };
        const ctx = { state: { ok: true }, byT: new Map(specs.map((x) => [x.t, stock(x.t, Math.round(x.px * (0.8 + 0.4 * rnd())))])), coByT: new Map(), fx: 1400, pxDate: T };
        const en = { load: { status: 'ok', data: { fx: 1400, stocks: [] }, coByT: new Map(), byT: new Map(specs.map((x) => [x.t, stock(x.t, x.px)])) }, today: T, ts: env.ts + c * 10 };
        const pc = (t) => Math.round(d.holdings.find((h) => h.t === t).target * 100);
        const a = CODES[0], b = CODES[1], cN = CODES[n - 2], dN = CODES[n - 1];
        const k = Math.min(3, pc(a) - 1), m = Math.min(3, pc(cN) - 1);
        const r1 = E.applyEdit({ v: 2, decks: [d] }, 'd1', steps([[a, pc(a) - k], [b, pc(b) + k]]), en);
        if (!r1.ok) { st.bad.push(['first', c, r1.why]); continue; }
        const pc1 = (t) => Math.round(r1.data.decks[0].holdings.find((h) => h.t === t).target * 100);
        const r2 = E.applyEdit(r1.data, 'd1', steps([[a, pc1(a) + k], [b, pc1(b) - k], [cN, pc1(cN) - m], [dN, pc1(dN) + m]]), { ...en, ts: en.ts + 5 });
        if (!r2.ok) { st.bad.push(['mixed', c, r2.why]); continue; }
        st.cases++;
        const B = r1.data.decks[0], A = r2.data.decks[0];
        const b0 = bandsOf(Ru.evaluateDeck(B, ctx)), b1 = bandsOf(Ru.evaluateDeck(A, ctx)), fresh = bandsOf(Ru.evaluateDeck(noW(A), ctx));
        for (const t of Object.keys(b0)) {
          if ([a, b].includes(t)) { st.changed++; const x = b1[t], f = fresh[t];
            if (x.status !== f.status || x.bands.some((v, i) => Math.abs(v - f.bands[i]) > 1e-12)) st.notFresh++; continue; }
          st.compared++;
          if (JSON.stringify(b0[t]) !== JSON.stringify(b1[t])) { st.moved++; if (st.bad.length < 5) st.bad.push(['moved', c, t, b0[t].bands, b1[t].bands]); }
          if (b0[t].status !== b1[t].status) st.statusDiff++;
        }
        if (A.holdings.reduce((x, h) => x + h.planW, 0) !== B.holdings.reduce((x, h) => x + h.planW, 0)) st.bad.push(['total', c]);
      }
      res.fuzz = st;
      out = res;""")
    assert got["case"][0] is True and got["case"][1] == [25.0, 44.05, 49.05], got["case"]          # 44.05% 그대로 (전에는 42.82%)
    assert got["total"][0] == got["total"][1]
    f = got["fuzz"]
    assert f["bad"] == [] and f["cases"] >= 380 and f["compared"] >= 900 and f["changed"] >= 700, f
    assert f["moved"] == 0 and f["statusDiff"] == 0 and f["notFresh"] == 0, f


def test_an_unusable_planv_is_left_out_and_said_once():
    """Review N4: a planV that cannot be used (a string, a negative number, NaN, one above twice the plan's total) is left out:
    that stock reads its own planned shares against the stored weights (as before planV), every other stock reads as it
    did, the stored weights stay in use, and the console names it once."""
    got = run(PLANW + """const s1 = E.applyEdit({ v: 1, decks: [deck7()] }, 'd7', steps([['000010', 15], ['000020', 25]]), env).data, d1 = s1.decks[0];
      const tg = new Map(d1.holdings.map((h) => [h.t, h.target]));
      const good = Ru.planWeights(d1, tg), noV = Ru.planWeights({ ...d1, id: 'nov', holdings: d1.holdings.map(({ planV, ...h }) => h) }, tg);
      const res = {};
      for (const [k, v] of [['text', 'x'], ['neg', -1], ['nan', NaN], ['huge', 1e12]]) {
        const bad = { ...d1, id: 'v-' + k, holdings: d1.holdings.map((h) => (h.t === '000010' ? { ...h, planV: v } : h)) };
        const w0 = warns.length, a = Ru.planWeights(bad, tg), again = Ru.planWeights(bad, tg), said = warns.slice(w0);
        res[k] = { stored: a.stored === true, mine: a.get('000010') === noV.get('000010'), others: [...a.keys()].filter((t) => t !== '000010').every((t) => a.get(t) === good.get(t)),
          said: said.length, what: said[0] || '' };
      }
      out = { hasV: d1.holdings[0].planV != null, res };""")
    assert got["hasV"] is True
    for k, x in got["res"].items():
        assert x["stored"] is True and x["mine"] is True and x["others"] is True, (k, x)        # 그 종목만 계획 수량으로, 나머지는 그대로
        assert x["said"] == 1 and "planV" in x["what"] and "000010" in x["what"], (k, x)
