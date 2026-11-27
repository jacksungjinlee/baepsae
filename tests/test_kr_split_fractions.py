# -*- coding: utf-8 -*-
"""팔았어요의 1주가 안 되는 몫 (2026-11-27 · Jack 답 11 · 새 시험 파일 · #186 다시 짓기).

Jack, 2026-11-27 (그대로): "팔았어요 accepts fractions (same unit as the spec, 1/10,000 share)." 스펙 v19.6 A.1: "Quantities are compared in
whole units of 1/10,000 share". 한국 주식병합 · 5:2 분할은 1주가 안 되는 몫을 남겨요 (시큐브 131090 2025-05-20 5:1 병합: 7주 → 1.4주 · 회사가 0.4주를
현금으로 줘요 · 단주 대금). 2.0 (src/v2 · Node 로):
- 입력: 분할이 그 날 몫을 남긴 한국 종목이면 팔았어요가 소수 넷째 자리(1/10,000주)까지 받아요 (records.js fracSaleOk · held.js fracHeld) · 몫이 없는
  종목 · 분할 전 날짜는 예전처럼 온 주만 (tests/test_v2_records.py 그대로) · 다섯째 자리는 받지 않아요.
- 보이는 수: 1.4주 · 0.4주 그대로 (반올림한 2주 · 0주가 아니에요).
- 원 금액: 판 금액 = 수량 × 가격 · 산 가격 = 그 몫의 원가 · 남은 원가 + 판 원가 = 넣은 돈 (만들거나 잃는 돈 없음).
- 기록: 가게(store.js)가 같은 규칙으로 받고, JSON 으로 내보냈다 다시 읽어도 같아요.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None or not os.path.exists(os.path.join(ROOT, "node_modules", ".bin", "esbuild")), reason="node · esbuild 가 없어요")
MODS = (("L", "src/v2/lots.js"), ("H", "src/v2/held.js"), ("S", "src/v2/store.js"), ("Rc", "src/v2/records.js"), ("RJ", "src/v2/records.jsx"),
        ("PV", "src/v2/pfview.jsx"), ("E", "src/v2/edit.js"), ("CP", "src/copy/v2.js"))
_B = {}


def node(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-krfrac-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in MODS:
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, mod))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", f"--outfile={tmp}/m.mjs", "--log-level=error",
                            "--loader:.js=jsx", "--charset=utf8", "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    names = ", ".join(n for n, _ in MODS)
    code = (f"import {{ {names} }} from './m.mjs';\nimport {{ renderToStaticMarkup }} from 'react-dom/server'; import {{ createElement as h }} from 'react';\n"
            "console.warn = () => {}; console.info = () => {};\nconst C = CP.C;\n" + DECK + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


# 시큐브 131090: 2025-03-04 에 7주를 900원에 (6,300원) · 2025-05-20 5:1 병합 (data.json splits 의 한국 줄) → 1.4주 · 평균 단가 4,500원
DECK = """
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deckOf = (t, nk, purchases, sales = [], extra = {}) => ({ id: 'd', name: 'p', createdAt: '2017-03-02', planFx: 1300,
  holdings: [{ t, nk, cls: 'kr', target: 1, rules: band(1) }], purchases, sales, ...extra });
const data = { splits: [['131090', '2025-05-20', 0.2], ['000020', '2026-01-05', 1 / 3], ['000030', '2026-01-05', 2.5]] };
const view = (d, today = '2026-11-23') => L.withDataSplits({ v: 2, decks: [d] }, L.dataSplits(data).list, today).decks[0];
const env = { today: '2026-11-23' };
const S131 = { t: '131090', cls: 'kr', price: 5000 };
const buy = { id: 'p1aaaaaa', t: '131090', date: '2025-03-04', qty: 7, price: 900, ccy: 'KRW' };
const sell = (d, qty, price, date) => Rc.checkSale(d, d.holdings[0].t, { qty, price, date }, { t: d.holdings[0].t, cls: 'kr', price: 5000 }, env);
const saved = (d, rec) => { const n = Rc.withRecord({ v: 2, decks: [d] }, 'd', 'sales', rec, '2026-11-23'); return n ? n.decks[0] : null; };
"""


def test_entry_accepts_a_part_of_a_share_only_where_a_split_left_one():
    got = node("""
      const v = view(deckOf('131090', '시큐브', [buy]));
      const w = view(deckOf('005930', '삼성전자', [{ id: 'p2aaaaaa', t: '005930', date: '2026-01-05', qty: 10, price: 100000, ccy: 'KRW' }]));
      const r = (x) => (x.ok ? { ok: true, qty: x.rec.qty, price: x.rec.price, date: x.rec.date } : { ok: false, why: x.why, field: x.field });
      out = { held: H.heldQty(v).get('131090'), frac: [Rc.fracSaleOk(v, '131090', '2026-11-20'), Rc.fracSaleOk(v, '131090', '2025-05-19'),
          Rc.fracSaleOk(w, '005930', '2026-11-20'), H.fracHeld(v, '131090', '2025-05-20')],
        part: r(sell(v, '0.4', '5000', '2026-11-20')), all: r(sell(v, '1.4', '5000', '2026-11-20')), tiny: r(sell(v, '0.0001', '5000', '2026-11-20')),
        five: r(sell(v, '0.00001', '5000', '2026-11-20')), more: r(sell(v, '1.5', '5000', '2026-11-20')),
        before: r(sell(v, '0.4', '900', '2025-05-19')), beforeWhole: r(sell(v, '3', '900', '2025-05-19')),
        whole: r(sell(w, '1.5', '100000', '2026-11-20')), wholeOk: r(sell(w, '2', '100000', '2026-11-20')) };""")
    assert got["held"] == 1.4
    assert got["frac"] == [True, False, False, True]                               # 병합 날부터 몫 · 그 전 날 (15주 온 주) · 몫이 없는 종목
    assert got["part"] == {"ok": True, "qty": 0.4, "price": 5000, "date": "2026-11-20"}           # 단주 대금으로 0.4주
    assert got["all"]["ok"] and got["all"]["qty"] == 1.4 and got["tiny"]["ok"] and got["tiny"]["qty"] == 0.0001
    assert got["five"] == {"ok": False, "why": "input", "field": "qty"}            # 1/10,000주보다 작은 단위는 받지 않아요
    assert got["more"] == {"ok": False, "why": "tooMany", "field": "qty"}
    assert got["before"] == {"ok": False, "why": "input", "field": "qty"}          # 병합 전 날짜: 그때는 7주 (온 주만)
    assert got["beforeWhole"]["ok"] and got["beforeWhole"]["qty"] == 3
    assert got["whole"] == {"ok": False, "why": "input", "field": "qty"} and got["wholeOk"]["ok"]   # 몫이 없는 한국 종목은 예전처럼 온 주만


def test_the_sheet_takes_decimals_and_shows_the_part_as_it_is():
    got = node("""
      const d = deckOf('131090', '시큐브', [buy]);
      const store = { data: { v: 2, decks: [view(d)] }, writable: false, key: 'x' };
      const load = { status: 'ok', data: { stocks: [S131], fx: 1400, splits: data.splits }, byT: new Map([['131090', S131]]), fresh: { md: null, stale: false } };
      const sheet = (stage, deck) => renderToStaticMarkup(h(RJ.RecordFlow, { flow: { stage, deckId: 'd', t: '131090', nk: '시큐브' }, setFlow() {}, load,
        store: { ...store, data: { v: 2, decks: [deck] } }, setStoreData() {} }));
      const sellForm = sheet('sell', view(d));
      const after = saved(view(d), sell(view(d), '0.4', '5000', '2026-11-20').rec);
      const list = sheet('list', view(after));
      const wform = sheet('sell', view(deckOf('131090', '시큐브', [{ ...buy, date: '2025-06-02', qty: 2, price: 4000 }])));
      const qtyBox = (html) => (html.match(/<input[^>]*>/g) || [])[0] || '';           // 첫 칸이 수량 (수량 · 가격 · 날짜)
      out = { decimal: qtyBox(sellForm).includes('inputMode="decimal"'), head: sellForm.includes('1.4주'),
        list: list.includes('0.4주') && !list.includes('· 0주'), left: Rc.stockState(view(after), '131090').qty, text: [PV.qtyText(1.4), PV.qtyText(0.4), PV.qtyText(0.0001)],
        whole: qtyBox(wform).includes('inputMode="numeric"') };""")
    assert got["decimal"] and got["head"], got                                     # 1.4주를 가진 종목의 수량 칸은 소수 입력
    assert got["list"] and got["left"] == 1 and got["text"] == ["1.4", "0.4", "0.0001"]
    assert got["whole"]                                                             # 병합 뒤에 산 2주 (몫 없음): 예전처럼 온 주 입력


def test_won_amounts_never_create_or_lose_money():
    got = node("""
      const v0 = view(deckOf('131090', '시큐브', [buy]));
      const a = sell(v0, '0.4', '5000', '2026-11-20').rec;                         // 단주 대금 0.4주 × 5,000원
      const pre = Rc.salePreview(v0, a);
      const d1 = saved(v0, a);
      const b = sell(view(d1), '1', '6000', '2026-11-21').rec;
      const d2 = saved(view(d1), b);
      const L2 = L.ledger(view(d2), '131090');
      // 1:3 병합 (0.3333… 의 몫): 10주 × 1,001원 → 3.3333주 · 0.3333 · 3 으로 나눠 팔아요
      const t = { id: 'p3aaaaaa', t: '000020', date: '2025-12-01', qty: 10, price: 1001, ccy: 'KRW' };
      const u0 = view(deckOf('000020', 'x', [t]));
      const u1 = saved(u0, sell(u0, '0.3333', '1000', '2026-11-20').rec);
      const u2 = saved(view(u1), sell(view(u1), '3', '3100', '2026-11-21').rec);
      const LU = L.ledger(view(u2), '000020');
      const mid = L.ledger(view(u1), '000020');
      out = { pre: [pre.proceedsWon, pre.gain, Math.round(pre.pct * 10) / 10], sales: L2.sales.map((s) => [s.proceedsWon, s.removedWon, s.gain]),
        held: L2.held, putIn: L2.putIn.won, removed: L2.removedWon, open: L.openValue(L.ledger(view(d1), '131090'), 5000, 1400),
        u: { putIn: LU.putIn.won, removed: LU.removedWon, held: LU.held, sumGain: LU.sales.reduce((x, s) => x + s.gain, 0),
          proceeds: LU.sales.reduce((x, s) => x + s.proceedsWon, 0), midHeld: mid.held, midCost: L.openValue(mid, 3100, 1400).cost,
          midRemoved: mid.removedWon } };""")
    assert got["pre"] == [2000, 200, 11.1]                                          # 판 금액 2,000원 · 그 몫의 원가 1,800원 (6,300 × 0.4 ÷ 1.4) · +200원
    assert got["sales"] == [[2000, pytest.approx(1800), pytest.approx(200)], [6000, pytest.approx(4500), pytest.approx(1500)]]
    assert got["held"] == 0 and got["putIn"] == 6300 and got["removed"] == pytest.approx(6300, abs=1e-6)
    assert got["open"]["value"] == 5000 and got["open"]["cost"] == pytest.approx(4500) and got["open"]["gain"] == pytest.approx(500)
    u = got["u"]
    assert u["held"] == 0 and u["putIn"] == 10010 and u["removed"] == pytest.approx(10010, abs=1e-6)   # 넣은 돈 = 판 원가의 합 (남는 0.0001주 · 1원도 없이)
    assert u["proceeds"] == pytest.approx(0.3333 * 1000 + 3 * 3100) and u["sumGain"] == pytest.approx(u["proceeds"] - 10010, abs=1e-6)
    assert u["midHeld"] == 30000 and u["midCost"] + u["midRemoved"] == pytest.approx(10010, abs=1e-6)   # 중간에도 남은 원가 + 판 원가 = 넣은 돈


def test_the_record_round_trips_through_the_store_and_its_check_matches_held_js():
    got = node("""
      const v0 = view(deckOf('131090', '시큐브', [buy]));
      const d1 = saved(v0, sell(v0, '0.4', '5000', '2026-11-20').rec);
      const store = { v: 2, decks: [d1] };
      const back = JSON.parse(JSON.stringify(store));
      const plain = JSON.parse(JSON.stringify({ ...d1, splits: [] }));                // 저장한 병합이 없는 같은 기록 (화면의 data.json 분할도 없이)
      const noSplit = JSON.parse(JSON.stringify({ v: 2, decks: [{ ...d1, splits: [] }] }));
      const cases = [[d1, '2026-11-20'], [d1, '2025-05-19'], [d1, '2025-05-20'], [{ ...d1, sales: [] }, '2026-11-20'], [plain, '2026-11-20']];
      out = { splits: d1.splits, sale: d1.sales[0].qty, problem: S.deckProblem(d1, '2026-11-23'), valid: S.validStore(back, '2026-11-23'),
        same: JSON.stringify(back) === JSON.stringify(store), read: S.checkStore(back, '2026-11-23').problems,
        noSplit: S.checkStore(noSplit, '2026-11-23').problems.map(String),
        held: H.heldQty(back.decks[0]).get('131090'),
        agree: cases.map(([d, date]) => H.fracHeld({ ...d, sales: (d.sales || []).filter((s) => s.date !== date) }, '131090', date)),
        all: E.sellAllQty(view(deckOf('131090', '시큐브', [buy])), '131090', '2026-11-20') };""")
    assert got["splits"] == [{"t": "131090", "date": "2025-05-20", "r": 0.2}]       # 몫을 만든 병합이 기록과 함께 저장돼요 (가게가 같은 수를 읽게)
    assert got["sale"] == 0.4 and got["problem"] is None and got["valid"] is True and got["same"] is True and got["read"] == []
    assert got["held"] == 1.0
    assert any("a Korean sale is whole shares" in p for p in got["noSplit"])        # 몫을 남긴 분할이 저장돼 있지 않으면 예전처럼 거절해요
    assert got["agree"] == [True, False, True, True, False]
    assert got["all"] == 1.4                                                       # 팔고 빼기: 가진 1.4주를 모두


def test_the_store_and_held_js_agree_and_main_s_held_js_has_the_parts():
    """store.js 는 held.js 의 fracHeld 를 v19.6a 부터 있던 부분으로 다시 적어요 (tests/test_v2_split_round.py 가 store.js 를 main 의 511fd6f held.js 와
    함께 읽어요). 같은 답인지 많은 경우로 봐요: 가게가 몫 판매를 받는지 = held.fracSalesOk."""
    got = node("""
      const cases = [];
      for (const r of [0.1, 0.2, 1 / 3, 1 / 6, 1 / 7, 0.4, 2.5]) for (const qty of [5, 7, 10, 11]) for (const sq of ['0.1', '0.3333', '0.5', '1', '1.5'])
        for (const sd of ['2025-12-20', '2026-02-01']) {
          const sp = [{ t: '000020', date: '2026-01-05', r }];
          const d = deckOf('000020', 'x', [{ id: 'p3aaaaaa', t: '000020', date: '2025-12-01', qty, price: 1000, ccy: 'KRW' }],
            [{ id: 's3aaaaaa', t: '000020', qty: Number(sq), price: 1000, date: sd, ccy: 'KRW' }], { splits: sp });
          const store = S.deckProblem(d, '2026-11-23');
          const held = H.fracSalesOk(d, '000020');
          const below = !!H.belowZero(d);
          cases.push([r, qty, sq, sd, !store, held, below]);
        }
      out = cases;""")
    bad = [c for c in got if not c[6] and c[4] != (c[5] or float(c[2]).is_integer())]
    assert not bad, bad[:5]
    assert any(c[4] and not float(c[2]).is_integer() for c in got) and any(not c[4] for c in got)
    src = open(os.path.join(ROOT, "src", "v2", "store.js"), encoding="utf-8").read()
    assert "fracHeld" not in src.split('from "./held.js"')[0].rsplit("import", 1)[1]
    old = open(os.path.join(ROOT, "tests", "fixtures", "count_before_split_round_511fd6f", "held.js"), encoding="utf-8").read()
    for name in ("splitsOf", "splitFactor", "splitDateOf", "toUnits", "okUnits", "importedUnits", "UNIT"):
        assert f"export function {name}" in old or f"export const {name}" in old


@pytest.mark.parametrize("r", [1 / 3, 1 / 6, 1 / 7])
def test_no_part_before_the_merge_a_part_after_it(r):
    """1차 리뷰 (Opus S4): 10주를 산 뒤 1:3 · 1:6 · 1:7 병합 — 병합 전 날짜의 판매는 온 주만 (예전: 오늘의 반올림한 수를 배율로 되돌려 9.9999주처럼
    보여 2.5주를 받았어요) · 병합 뒤에는 몫 (1/10,000주) · 몫이 없는 한국 종목은 예전처럼 1.5주를 받지 않아요."""
    got = node("""
      const sp = [['000020', '2026-01-05', R]];
      const v = L.withDataSplits({ v: 2, decks: [deckOf('000020', 'x', [{ id: 'p3aaaaaa', t: '000020', date: '2025-12-01', qty: 10, price: 1000, ccy: 'KRW' }])] },
        L.dataSplits({ splits: sp }).list, '2026-11-23').decks[0];
      const w = view(deckOf('005930', '삼성', [{ id: 'p2aaaaaa', t: '005930', date: '2026-01-05', qty: 10, price: 100000, ccy: 'KRW' }]));
      const r = (x) => (x.ok ? 'ok' : x.why);
      out = { before: [H.fracHeld(v, '000020', '2025-12-20'), r(sell(v, '2.5', '1000', '2025-12-20')), r(sell(v, '0.0001', '1000', '2025-12-20')),
          r(sell(v, '3', '1000', '2025-12-20'))],
        after: [H.fracHeld(v, '000020', '2026-02-01'), r(sell(v, '0.' + '1'.repeat(4), '1000', '2026-02-01'))],
        whole: r(sell(w, '1.5', '100000', '2026-11-20')) };""".replace("R]", repr(r) + "]"))
    assert got["before"] == [False, "input", "input", "ok"]
    assert got["after"] == [True, "ok"] and got["whole"] == "input"


def test_a_part_sale_dated_before_an_existing_one_is_refused_by_the_form_as_the_store_would():
    """1차 리뷰 (Fable): 27주 → 5:1 병합 뒤 5.4주. 0.4주를 11-20 에 판 뒤, 11-10 날짜로 또 0.4주 — 양식이 받고 가게가 거절했어요 (일반 실패 줄). 이제 양식이
    같은 검사로 거절해요 (수량 칸 · 기존 줄 '날짜·수량·가격을 다시 확인해 주세요')."""
    got = node("""
      const v = view(deckOf('131090', '시큐브', [{ ...buy, qty: 27 }]));
      const a = sell(v, '0.4', '5000', '2026-11-20');
      const d1 = saved(v, a.rec);
      const b = sell(view(d1), '0.4', '5000', '2026-11-10');
      const c = sell(view(d1), '1', '5000', '2026-11-10');
      const forced = { ...d1, sales: [...d1.sales, { id: 's9aaaaaa', t: '131090', qty: 0.4, price: 5000, date: '2026-11-10', ccy: 'KRW' }] };
      out = { a: a.ok, b: b.ok ? 'ok' : [b.why, b.field], c: c.ok, store: S.deckProblem(forced, '2026-11-23') ? 'refused' : 'ok' };""")
    assert got == {"a": True, "b": ["input", "qty"], "c": True, "store": "refused"}


def test_the_keypad_follows_a_cleared_date_as_today():
    src = open(os.path.join(ROOT, "src", "v2", "records.jsx"), encoding="utf-8").read()
    assert 'fracSaleOk(deck, t, v.date || today)' in src
