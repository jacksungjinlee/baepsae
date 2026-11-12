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
V196A = "0a41deb"        # v19.6a (this branch's base, not merged yet): the app a tab may still run when v19.7a ships
MAIN = "7b5c895"         # main when v19.6a branched (v19.3d2)
V195B = "94eea80"        # v19.5b (claude/v19.5b-rankings): ranks.js criteriaPct


def _git(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _old(tmp, rev, name):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    for f in ("store.js", "held.js", "dcf.js"):
        body = _git(rev, f"src/v2/{f}")
        assert body is not None, (rev, f)
        with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
            fh.write(body)
    return os.path.join(d, "store.js")


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-edit-")
        entry = os.path.join(tmp, "entry.js")
        old6, oldm = _old(tmp, V196A, "old6"), _old(tmp, MAIN, "oldm")
        ranks = _git(V195B, "src/v2/ranks.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("H", "held.js"), ("E", "edit.js"), ("Rc", "records.js"), ("Ru", "rules.js"), ("Dc", "deckcalc.js"),
                              ("F", "fitpct.js"), ("Rt", "routes.js"), ("En", "engine.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export * as Old6 from {json.dumps(old6)};\nexport * as OldM from {json.dumps(oldm)};\n")
            if ranks:
                # v19.5b's ranks.js, its imports pointed at this checkout's modules (engine · track · warn are the same files)
                src = re.sub(r'from "\./([a-z0-9]+\.js)"', lambda m: "from " + json.dumps(os.path.join(ROOT, "src", "v2", m.group(1))), ranks)
                with open(os.path.join(tmp, "ranks.js"), "w", encoding="utf-8") as fh:
                    fh.write(src)
                f.write(f"export * as Rk from {json.dumps(os.path.join(tmp, 'ranks.js'))};\n")
            else:
                f.write("export const Rk = null;\n")
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
const CODES = ['000010', '000020', '000030', '000040', '000050'];
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
        valid: S.validStore(r.data, T), changes: nd.changes };""")
    assert got["ok"] is True and got["valid"] is True
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
          hist: sd.history.map((e) => ({ t: e.t, reason: e.reason, out: e.out, sales: e.sales.length })), changes: sd.changes, planPx: sd.holdings.map((h) => h.planPx) } };""")
    assert got["five"] == {"low": False, "y": 20}                                               # 5 × 20 = 100: 줄 없음
    assert got["chk"] == {"low": True, "y": 25}
    assert got["refused"] == {"ok": False, "why": "sum"}                                       # 합계 80%: 저장 꺼짐
    assert got["rows"] == [25, 25, 25, 25] and got["maxPct"] == 25
    assert got["planPx"] == [100000] * 4 and got["planned"] == [25] * 4 and got["held"] == ["000010", "000020", "000030", "000040"]
    assert got["ys"] == [34, 25, 17, 15, 12, 100] and got["zero"] == {"low": False, "y": None} and got["exact"] == [False, False]
    s = got["sr"]
    assert s["ok"] and s["valid"] and s["max"] == 25 and s["targets"] == [0.25] * 4 and s["planPx"] == [100000] * 4
    assert s["sales"] == 0 and s["hist"] == [{"t": "000010", "reason": "better", "out": "2026-11-12", "sales": 1}]   # 판 기록은 history 로
    assert s["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000010", "nk": "종목1", "reason": "better"}, {"at": "2026-11-12", "kind": "targets"}]


def test_add_takes_the_build_steps_rules_and_a_planned_qty_from_its_target():
    got = run("""const d = deck4({}, 4, 0.25, 30);
      const s = { t: '005930', nk: '삼성전자', cls: 'kr', price: 225000, ind: 'semi', indName: '반도체', dps: 1444, fy: 2025, debt: 30, roe: 9 };
      const add = { t: s.t, nk: s.nk, cls: 'kr', ind: 'semi', kind: 'core', s };
      const def = E.addDefault(4, 30);
      const dr = E.addDraft(d, E.emptyDraft(), add, def);
      const r = E.applyEdit({ v: 1, decks: [d] }, 'd1', dr, env);
      const nd = r.data.decks[0], h = nd.holdings.find((x) => x.t === '005930');
      const want = Dc.rulesFor(load, { s, kind: 'core', targetW: 0.2 }, { points: d.settings.points });
      // an ETF (no score) is added as 직접 추가 (kind pinned), and a US stock goes into a Korea-only portfolio
      const us = { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', ccy: 'USD', price: 270, ind: 'elec', indName: '전자부품' };
      const r2 = E.applyEdit({ v: 1, decks: [d] }, 'd1', E.addDraft(d, E.emptyDraft(), { t: 'AAPL', nk: us.nk, cls: 'us', ind: 'elec', kind: 'pinned', s: us }, 10), env);
      const hu = r2.data.decks[0].holdings.find((x) => x.t === 'AAPL');
      out = { def, pcts: E.editRows(d, dr).map((r) => r.pct), ok: r.ok, valid: S.validStore(r.data, T), h, rulesSame: JSON.stringify(h.rules) === JSON.stringify(want),
        others: nd.holdings.filter((x) => x.t !== '005930').map((x) => [x.target, x.plannedQty, x.planPx]), changes: nd.changes, purchases: nd.purchases.length,
        us: { kind: hu.kind, planPx: hu.planPx, plannedQty: hu.plannedQty, cls: hu.cls }, unheld: Ru.evaluateDeck(nd, ctxOf()).unheld };""")
    assert got["def"] == 20 and got["pcts"] == [20, 20, 20, 20, 20]                              # 100 ÷ (4 + 1)
    assert got["ok"] and got["valid"] and got["rulesSame"]                                      # 빌드 단계의 rulesFor 그대로
    h = got["h"]
    assert h["planPx"] == 225000 and h["plannedQty"] == round(0.2 * 1e7 / 225000) and h["setAt"] == "2026-11-12" and h["kind"] == "core"
    assert h["target"] == 0.2 and h["ts"] == 1762900000000 and h["ind"] == "semi"
    assert got["others"] == [[0.2, 20, 100000]] * 4                                             # 나머지는 비율대로, planPx 그대로
    assert got["purchases"] == 4 and got["unheld"] == ["005930"]                               # 산 기록 없이 담아요 (계획한 종목)
    assert got["changes"] == [{"at": "2026-11-12", "kind": "targets"}, {"at": "2026-11-12", "kind": "add", "t": "005930", "nk": "삼성전자"}]
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
        removed: nd.removed.map((m) => m.t), changes: nd.changes, last: last === E.emptyDraft() ? 'same' : JSON.stringify(last), lastRows: E.editRows(one, last).length,
        list: E.changeList(nd).map((c) => c.kind) };""")
    assert got["ok"] and got["valid"]
    assert got["held"] == [["000010", 0.5], ["000030", 0.5]]                                    # 25 + 25 를 비율대로 나눠 50 · 50
    h = got["hist"]
    assert len(h) == 1 and h[0]["t"] == "000020" and h[0]["reason"] == "rule" and len(h[0]["sales"]) == 1 and len(h[0]["purchases"]) == 1
    assert got["sales"] == [] and got["purchases"] == ["000010", "000030"] and got["removed"] == ["000020", "000040"]
    assert got["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000020", "nk": "종목2", "reason": "rule"},
                              {"at": "2026-11-12", "kind": "remove", "t": "000040", "nk": "종목4"}, {"at": "2026-11-12", "kind": "targets"}]
    assert got["lastRows"] == 1 and json.loads(got["last"]) == {"over": {}, "adds": [], "removed": [], "maxPct": None, "last": None}   # 마지막 한 종목은 못 빼요
    assert got["list"] == ["targets", "remove", "remove"]                                       # 화면은 최신부터


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
    assert got["rb"] == {"over": {"000030": 30}, "adds": [], "removed": [], "maxPct": None, "last": None}
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
        back: JSON.stringify(back.decks[0].changes) === JSON.stringify(r.data.decks[0].changes) && back.decks[0].history[0].reason === 'thesis',
        version: S.versionFor({ v: 1, decks: [{ ...deck4(), changes: [{ at: T, kind: 'targets' }] }] }) };""")
    assert got["good"] is True
    assert got["futureAt"] is False and got["noKind"] is False and got["badT"] is False and got["notList"] is False and got["tooMany"] is False
    assert got["later"] is True                                                                  # 나중 판의 종류는 남겨 두고 보여 주지 않아요
    assert got["badHist"] is False
    assert got["merged"] == ["2026-11-09 add", "2026-11-10 add", "2026-11-12 remove", "2026-11-12 targets", "2026-11-12 targets"]
    assert got["bigN"] == 200 and got["bigOld"] is True                                          # 300 → 최신 200
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
    assert [c["kind"] for c in got["changes"]] == ["remove", "targets"] and got["reason"] == "thesis" and got["note"] is True


def test_the_edit_address_names_one_portfolio():
    got = run("""out = Object.fromEntries(['#portfolio/edit/d1', '#portfolio/edit/d_1-x', '#portfolio/edit/', '#portfolio/edit/a b', '#portfolio/edit'].map((h) => [h, Rt.parseHash(h)]));""")
    assert got["#portfolio/edit/d1"] == {"tab": "portfolio", "sub": "edit/d1", "about": False, "known": True, "edit": "d1"}
    assert got["#portfolio/edit/d_1-x"]["edit"] == "d_1-x"
    for h in ("#portfolio/edit/", "#portfolio/edit/a b", "#portfolio/edit"):
        assert got[h]["known"] is False and "edit" not in got[h], h


def test_criteria_pct_is_v195b_s_one_number_per_stock():
    got = run("""if (!Rk) { out = null; } else {
        const fix = JSON.parse(require('fs').readFileSync(%s, 'utf8'));
        const res = {};
        for (const [mk, pts] of [['kr', { value: 3, div: 2 }], ['us', { profit: 2, lowVol: 1 }], ['kr', { stable: 1, growth: 3, trend: 2 }]]) {
          const a = F.criteriaPct(fix.stocks, mk, pts), b = Rk.criteriaPct(fix.stocks, mk, pts);
          res[mk + JSON.stringify(pts)] = { n: a.size, same: a.size === b.size && [...a].every(([t, v]) => b.get(t) === v), min: Math.min(...a.values()), max: Math.max(...a.values()) };
        }
        out = res; }""".replace("require('fs')", "(await import('fs'))") % json.dumps(os.path.join(ROOT, "tests", "fixtures", "v2", "data.json")))
    if got is None:
        pytest.skip("v19.5b 의 ranks.js 를 git 에서 읽지 못했어요")
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
      out = { changes, same: JSON.stringify(rest) === JSON.stringify(b.decks[0]), valid: S.validStore(a, T), none: E.withRemoval({ v: 1, decks: [d] }, 'd1', 'XXXX', T, env.ts) };""")
    assert got["changes"] == [{"at": "2026-11-12", "kind": "remove", "t": "000020", "nk": "종목2"}] and got["same"] is True and got["valid"] is True
    assert got["none"] is None
