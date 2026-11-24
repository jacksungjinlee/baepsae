# -*- coding: utf-8 -*-
"""뱁새 2.0: 기록 화면이 미국 거래일로 열리고 그 날짜 · 환율로 저장하는지 (#191 round 1, Fable S3) — 화면을 Node 에서 그려 봐요.

react-dom/server 로 기록 양식(records.jsx RecordFlow: 샀어요 · 팔았어요 · 배당 받았어요)과 매수 계획의 샀어요(plan.jsx RecordSheet)를 고정한
시계에서 그리고, 그린 화면의 '저장' 버튼이 가진 함수를 그대로 불러 저장되는 기록을 받아 봐요 (화면을 그릴 때 JSX 를 만드는 함수를
감싸 onClick 을 모아 둬요: tests 의 shim). 확인하는 것:
- 날짜 칸이 열릴 때의 값과 max (max 는 늘 한국 날짜): 달러 종목은 그 거래가 잡히는 미국 날짜 (format.usTradeDay: 뉴욕 날짜, 뉴욕 20:00 부터는
  다음 날 — 겨울 10:00 KST), 한국 종목은 한국 날짜 (main 과 같아요)
- 저장되는 기록의 날짜와 환율: 환율 기록에 그날이 없으면 오늘 환율(data.json fx 1,338원), 있으면 그날 줄 (아침 발행 뒤)
- 매수 계획의 샀어요: 날짜를 비워 두면 줄마다 자기 시장의 날짜 · 환율, 한국 줄은 main 과 같아요 (한국 날짜 · 원 · 환율 없음)
기대값은 손으로 셌어요. 시험 데이터: tests/fixtures/v2 (AAPL $344.63 · 삼성전자 225,000원 · fx 1,338원).
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
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
MODS = {"RJ": "src/v2/records.jsx", "PJ": "src/v2/plan.jsx", "E": "src/v2/engine.js", "UI": "src/ui/components.jsx", "CP": "src/copy/v2.js"}
_B = {}

# JSX through one function that keeps every onClick it is given (the "저장" button's handler is then called after the render)
SHIM = """
import React from "react";
export const CLICKS = [];
export function __h(type, props, ...children) {
  if (props && typeof props.onClick === "function") CLICKS.push({ type, onClick: props.onClick, children: children.flat(Infinity) });
  return React.createElement(type, props, ...children);
}
export const __F = React.Fragment;
"""


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-usdates-screens-")
        entry, shim = os.path.join(tmp, "entry.js"), os.path.join(tmp, "shim.js")
        with open(shim, "w", encoding="utf-8") as f:
            f.write(SHIM)
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
            f.write(f"export {{ CLICKS }} from {json.dumps(shim)};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=transform", "--jsx-factory=__h",
                            "--jsx-fragment=__F", f"--inject:{shim}", "--loader:.js=jsx", "--charset=utf8", f"--outfile={tmp}/b.mjs",
                            "--log-level=error", "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


HELP = """
const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
const logs = []; console.warn = (m) => logs.push(String(m)); console.info = () => {}; console.error = (m) => logs.push('error ' + String(m));
const C = CP.C, h = React.createElement;
const at = (iso) => { const t = Date.parse(iso); Date.now = () => t; return t; };
const D0 = JSON.parse(fs.readFileSync(FIX + '/data.json', 'utf8')), CO0 = JSON.parse(fs.readFileSync(FIX + '/corp.json', 'utf8')), M0 = JSON.parse(fs.readFileSync(FIX + '/macro.json', 'utf8'));
// the data the clock would see: today's fx 1,338원 (data.json fx), the history up to asOf (macro.json fxHist, final), fresh
const HIST = [['2016-01-04', 1172.5], ['2026-11-20', 1336.2], ['2026-11-23', 1345.9], ['2026-11-24', 1344.1]];
const loadOf = (asOf) => {
  const D = { ...D0, fx: 1338.0 }, CO = { ...CO0 };
  const rows = HIST.filter(([d]) => d <= asOf);
  return { status: 'ok', data: D, corp: CO, macro: { ...M0, fxHist: { asOf: rows[rows.length - 1][0], final: true, rows } }, fresh: { md: null, days: 0, stale: false },
    byT: new Map(D.stocks.map((s) => [s.t, s])), coByT: new Map(CO.companies.map((x) => [x.t, x])), preview: false };
};
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deckOf = () => ({ id: 'd1', name: '포트폴리오', createdAt: '2026-06-01', planFx: 1300,
  holdings: [{ t: '005930', nk: '삼성전자', cls: 'kr', target: 0.5, rules: band(0.5) }, { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', target: 0.5, rules: band(0.5) }],
  purchases: [{ id: 'p1aaaaaa', t: '005930', qty: 10, price: 200000, date: '2026-06-02', ccy: 'KRW' }, { id: 'p2aaaaaa', t: 'AAPL', qty: 3, price: 300, date: '2026-06-02', ccy: 'USD', fx: 1300 }] });
const storeOf = (decks) => ({ data: { v: 2, decks }, writable: true, locked: false, key: 'baepsae2.v1' });
const dateInput = (html) => { const m = /<input[^>]*type="date"[^>]*>/.exec(html); if (!m) return null;
  const g = (a) => { const x = new RegExp(' ' + a + '="([^"]*)"').exec(m[0]); return x ? x[1] : null; }; return { value: g('value'), max: g('max') }; };
// render, then press the button whose label is `label` (its own onClick, as the screen would call it); -> what was saved
const press = (el, label) => {
  CLICKS.length = 0;
  const html = renderToStaticMarkup(el);
  // the Button element and the <button> it renders carry the same handler: one handler, one button
  const fns = [...new Set(CLICKS.filter((c) => c.children.includes(label)).map((c) => c.onClick))];
  if (fns.length !== 1) throw new Error('button ' + label + ': ' + fns.length);
  fns[0]();
  return html;
};
// the record form (기록 → 샀어요 · 팔았어요 · 배당 받았어요) of one stock at the clock; -> { input, saved record (id left out) }
const form = (clock, asOf, stage, t, nk) => {
  at(clock);
  let saved = null;
  const store = storeOf([deckOf()]);
  const html = press(h(RJ.RecordFlow, { flow: { stage, deckId: 'd1', t, nk }, setFlow: () => {}, load: loadOf(asOf), store,
    setStoreData: (d) => { saved = d; } }), C.plan.save);
  const d = saved && saved.decks[0];
  const list = stage === 'buy' ? 'purchases' : stage === 'sell' ? 'sales' : 'divs';
  const rec = d ? d[list][d[list].length - 1] : null;
  if (rec) delete rec.id;
  return { input: dateInput(html), rec, logs: logs.splice(0) };
};
// 매수 계획's 샀어요 with the date left blank: one Korean and one US row; -> { input, purchases (id left out) }
const sheet = (clock, asOf) => {
  at(clock);
  const load = loadOf(asOf), st = { ...E.defaultSettings(), points: { value: 3 } };
  const row = (t, w) => ({ t, s: load.byT.get(t), shares: 2, kind: 'core', targetW: w, reasons: [] });
  let saved = null;
  const html = press(h(PJ.RecordSheet, { open: true, stage: 'form', onClose: () => {}, load, st, plan: { rows: [row('005930', 0.5), row('AAPL', 0.5)] },
    ds: { pinned: [], cands: {} }, store: storeOf([]), setStoreData: (d) => { saved = d; }, onDone: () => {}, goToday: () => {} }), C.plan.save);
  const ps = saved ? saved.decks[0].purchases.map(({ id, ...p }) => p) : null;
  return { input: dateInput(html), purchases: ps, createdAt: saved ? saved.decks[0].createdAt : null, logs: logs.splice(0) };
};
"""


def run(body):
    d = bundle_dir()
    code = ("import fs from 'fs'; import React from 'react'; import { renderToStaticMarkup } from 'react-dom/server';\n"
            "import { RJ, PJ, E, UI, CP, CLICKS } from './b.mjs';\n" + f"const FIX = {json.dumps(FIX)};\n" + HELP + "let out;\n" + body
            + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=d, capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "UTC"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# (clock, the history's last day then, the US trade date, Korea's date, the rate a US record of that date saves)
CLOCKS = [
    ("2026-11-24T01:00:00+09:00", "2026-11-20", "2026-11-23", "2026-11-24", 1338.0),   # US session after Korean midnight: today's rate
    ("2026-11-24T09:00:00+09:00", "2026-11-23", "2026-11-23", "2026-11-24", 1345.9),   # the morning after: the history's row of 11-23
    ("2026-11-24T11:00:00+09:00", "2026-11-23", "2026-11-24", "2026-11-24", 1338.0),   # overnight session (주간거래): booked 11-24, as main
    ("2026-11-24T15:00:00+09:00", "2026-11-23", "2026-11-24", "2026-11-24", 1338.0),   # afternoon: both dates the same, as main
]


def test_the_record_form_opens_on_the_us_trade_date_for_a_dollar_stock_and_saves_it_with_that_dates_rate():
    got = run(f"""
      out = {json.dumps(CLOCKS)}.map(([clock, asOf]) => ({{ clock,
        buy: form(clock, asOf, 'buy', 'AAPL', 'Apple Inc.'), sell: form(clock, asOf, 'sell', 'AAPL', 'Apple Inc.'), div: form(clock, asOf, 'div', 'AAPL', 'Apple Inc.'),
        krBuy: form(clock, asOf, 'buy', '005930', '삼성전자'), krSell: form(clock, asOf, 'sell', '005930', '삼성전자'), krDiv: form(clock, asOf, 'div', '005930', '삼성전자') }}));""")
    for (clock, _, us, kr, fx), g in zip(CLOCKS, got):
        for k in ("buy", "sell", "div", "krBuy", "krSell", "krDiv"):
            assert g[k]["input"]["max"] == kr, (clock, k, g[k]["input"])                 # the latest date that can be typed: Korea's, as on main
        assert g["buy"]["input"]["value"] == us and g["sell"]["input"]["value"] == us and g["div"]["input"]["value"] == us, (clock, g["buy"]["input"])
        # nothing typed yet (no quantity or amount): nothing is saved (the saved records are checked below, with the quantity in)
        assert all(g[k]["rec"] is None for k in ("buy", "sell", "div", "krBuy", "krSell", "krDiv")), clock
        for k in ("krBuy", "krSell", "krDiv"):
            assert g[k]["input"]["value"] == kr, (clock, k, g[k]["input"])           # Korean stocks: Korea's date, as on main
        assert all(not any("error" in m for m in g[k]["logs"]) for k in g if k != "clock"), clock


def test_the_record_form_saves_the_date_it_opened_on_with_that_dates_rate():
    """The same forms with the quantity in from the start (flow.prefill, as 팔고 빼기 opens the sale form with every share held): pressing
    저장 saves the date the form opened on and that date's rate; Korean records: Korea's date, no rate, as on main."""
    got = run(f"""
      const typedForm = (clock, asOf, stage, t, nk, prefill) => {{
        at(clock); let saved = null;
        press(h(RJ.RecordFlow, {{ flow: {{ stage, deckId: 'd1', t, nk, prefill }}, setFlow: () => {{}}, load: loadOf(asOf), store: storeOf([deckOf()]),
          setStoreData: (d) => {{ saved = d; }} }}), C.plan.save);
        const d = saved && saved.decks[0], list = stage === 'buy' ? 'purchases' : 'sales';
        const r = d ? {{ ...d[list][d[list].length - 1] }} : null; if (r) delete r.id; return r;
      }};
      out = {json.dumps(CLOCKS)}.map(([clock, asOf]) => [typedForm(clock, asOf, 'buy', 'AAPL', 'Apple Inc.', {{ qty: 2 }}),
        typedForm(clock, asOf, 'sell', 'AAPL', 'Apple Inc.', {{ qty: 1 }}), typedForm(clock, asOf, 'buy', '005930', '삼성전자', {{ qty: 3 }}),
        typedForm(clock, asOf, 'sell', '005930', '삼성전자', {{ qty: 2 }})]);""")
    for (clock, _, us, kr, fx), (buy, sell, krBuy, krSell) in zip(CLOCKS, got):
        assert buy == {"t": "AAPL", "date": us, "qty": 2, "price": 344.63, "ccy": "USD", "fx": fx}, (clock, buy)
        assert sell == {"t": "AAPL", "qty": 1, "price": 344.63, "date": us, "ccy": "USD", "fx": fx}, (clock, sell)
        assert krBuy == {"t": "005930", "date": kr, "qty": 3, "price": 225000, "ccy": "KRW"}, (clock, krBuy)
        assert krSell == {"t": "005930", "qty": 2, "price": 225000, "date": kr, "ccy": "KRW"}, (clock, krSell)


def test_the_plan_sheet_dates_each_row_in_its_own_market_and_saves_each_us_row_with_its_dates_rate():
    got = run(f"out = {json.dumps(CLOCKS)}.map(([clock, asOf]) => sheet(clock, asOf));")
    for (clock, _, us, kr, fx), g in zip(CLOCKS, got):
        assert g["input"] == {"value": "", "max": kr}, (clock, g["input"])              # the sheet's date field stays blank, max Korea's
        assert g["purchases"] == [{"t": "005930", "date": kr, "qty": 2, "price": 225000, "ccy": "KRW"},
                                  {"t": "AAPL", "date": us, "qty": 2, "price": 344.63, "ccy": "USD", "fx": fx}], (clock, g)
        assert g["createdAt"] == kr and not g["logs"], (clock, g)
