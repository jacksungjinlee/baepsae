# -*- coding: utf-8 -*-
"""뱁새 2.0: 임시 환율 줄이 돈을 보여 주는 화면마다 한 번 (#191 round 1 review, Jack 2026-11-27 · say-why 규칙) — react-dom/server 로 그려요.

임시 환율(rateTemp) 기록이 셈에 들어가는 동안, 원화 금액을 보여 주는 화면은 승인된 줄을 그대로 한 번 보여 줘요:
"지금은 최근 환율로 저장했어요. 이 날짜의 환율이 들어오면 자동으로 바꿔요."
- 홈 (새 홈 Home2: 돈 카드 · 이번 주 정리 위) · 예전 홈 (비상 스위치 HOME2 끔) · 포트폴리오 (카드들 위) · 연말에 확인할 숫자 · 종목 바꾸기
  (팔고 빼기 · 팔고 바꾸기 뒤에 돌아오는 화면)
- 임시 기록이 없으면 (또는 그날 환율로 바뀐 뒤면) 없어요. 두 포트폴리오에 임시 기록이 있어도 화면마다 한 번이에요.
(기록 목록 · 다 판 뒤 · 내 수익 · 매수 계획 기록했어요는 tests/test_v2_us_dates_screens.py)
시험 데이터: tests/fixtures/v2, 지금은 2026-11-27 (금) 09:00 KST (연말에 확인할 숫자가 열려 있어요).
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
MODS = {"T": "v2/today.jsx", "P": "v2/portfolio.jsx", "TJ": "v2/tax.jsx", "ED": "v2/editor.jsx", "E": "v2/edit.js", "L": "v2/load.js",
        "CP": "copy/v2.js"}
LINE = "지금은 최근 환율로 저장했어요. 이 날짜의 환율이 들어오면 자동으로 바꿔요."
_B = {}


def bundle_dir(home2=True):
    """home2=True: 커밋한 src 그대로. home2=False: src 를 임시 폴더에 복사해서 today.jsx 의 HOME2 만 끈 것 (tests/test_v2_home_usd.py 처럼)."""
    key = "on" if home2 else "off"
    if key not in _B:
        tmp = tempfile.mkdtemp(prefix=f"baepsae-ratetemp-screens-{key}-")
        _B[key] = tmp
        src = os.path.join(ROOT, "src")
        if not home2:
            src = os.path.join(tmp, "src")
            shutil.copytree(os.path.join(ROOT, "src"), src)
            p = os.path.join(src, "v2", "today.jsx")
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            old = re.findall(r"^export const HOME2 = (?:true|false);$", text, flags=re.M)
            assert old == ["export const HOME2 = true;"], old
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text.replace(old[0], "export const HOME2 = false;"))
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(src, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs", "--log-level=error"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
    return _B[key]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    for k in list(_B):
        shutil.rmtree(_B.pop(k), ignore_errors=True)


HELP = """
const NOW = Date.parse('2026-11-27T09:00:00+09:00'); Date.now = () => NOW;
const C = CP.C;
const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
const logs = []; console.warn = (m) => logs.push(String(m)); console.info = () => {}; console.error = (m) => logs.push('error ' + String(m));
const read = (f) => JSON.parse(fs.readFileSync(FIX + '/' + f, 'utf8'));
// the 11-27 morning publish (after Thanksgiving: Korea 11-26, US 11-25), fresh
const loadOf = () => {
  const files = { data: read('data.json'), corp: read('corp.json'), macro: read('macro.json') };
  Object.assign(files.data, { pxDate: '2026-11-26', usPxDate: '2026-11-25', fxDate: '2026-11-26' });
  for (const f of ['data', 'corp', 'macro']) files[f].publishedAt = new Date(NOW - 3600000).toISOString();
  return L.resolveLoad({ data: { ok: true, data: files.data }, corp: { ok: true, data: files.corp }, macro: { ok: true, data: files.macro } }, NOW);
};
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
// a portfolio made with 포트폴리오 만들기: AAPL and 삼성전자, AAPL bought in March (its rate known) and, with temp, 2 more at 01:00 KST
// today (New York's 11-26, Thanksgiving: no Seoul close of its own yet), saved at the latest rate and marked temporary
const deck = (id, temp, fixed = false) => ({ id, name: id, createdAt: '2026-01-05', planFx: 1450,
  holdings: [{ t: 'AAPL', nk: 'Apple Inc.', cls: 'us', target: 0.5, rules: band(0.5) }, { t: '005930', nk: '삼성전자', cls: 'kr', target: 0.5, rules: band(0.5) }],
  purchases: [{ id: 'p1' + id, t: 'AAPL', qty: 10, price: 200, date: '2026-03-02', ccy: 'USD', fx: 1450 },
    { id: 'p2' + id, t: '005930', qty: 10, price: 60000, date: '2026-03-02', ccy: 'KRW' },
    ...(temp ? [{ id: 'p3' + id, t: 'AAPL', qty: 2, price: 210, date: '2026-11-26', ccy: 'USD', fx: 1338, ...(fixed ? {} : { rateTemp: true }) }] : [])],
  sales: [{ id: 's1' + id, t: 'AAPL', qty: 1, price: 230, date: '2026-09-01', ccy: 'USD', fx: 1400 }] });
const storeOf = (decks) => ({ data: { v: 2, decks, notes: {}, assume: {} }, writable: true, locked: false, key: 'baepsae2.v1', preview: false });
const noop = () => {};
const count = (html) => html.split(LINE).length - 1;
const screens = (decks, load = loadOf()) => {
  const st = storeOf(decks);
  return {
    home: count(renderToStaticMarkup(h(T.Home, { load, store: st, setStoreData: noop, pad: 16, go: noop, onWhy: noop }))),
    portfolio: count(renderToStaticMarkup(h(P.Portfolio, { load, store: st, setStoreData: noop, pad: 16, go: null }))),
    tax: count(renderToStaticMarkup(h(TJ.Tax, { load, store: st, pad: 16, onBack: noop }))),
    edit: count(renderToStaticMarkup(h(ED.Editor, { deck: decks[0], load, store: st, setStoreData: noop, draft: E.emptyDraft(), setDraft: noop, pad: 16,
      onLeave: noop, onSaved: noop }))),
  };
};
"""


def run(body, home2=True):
    tmp = bundle_dir(home2)
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\nconst { T, P, TJ, ED, E, L, CP } = B;\n" + f"const FIX = {json.dumps(FIX)};\nconst LINE = {json.dumps(LINE, ensure_ascii=False)};\n"
            + HELP + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout)


BODY = """
  out = { copy: C.rec.rateTemp, one: screens([deck('dtemp', true)]), two: screens([deck('dtemp', true), deck('dtemp2', true)]),
    none: screens([deck('dplain', false)]), fixed: screens([deck('dfixed', true, true)]), mixed: screens([deck('dplain', false), deck('dtemp', true)]),
    errors: logs.filter((m) => m.startsWith('error')) };
"""


def check(got):
    assert got["copy"] == LINE
    every = {"home": 1, "portfolio": 1, "tax": 1, "edit": 1}
    assert got["one"] == every, got["one"]                         # once on each screen while a counted record is temporary
    assert got["two"] == every, got["two"]                         # two portfolios with one: still once per screen
    assert got["none"] == {k: 0 for k in every}, got["none"]       # no temporary record: no line
    assert got["fixed"] == {k: 0 for k in every}, got["fixed"]     # replaced by its date's rate: gone
    assert got["mixed"]["home"] == 1 and got["mixed"]["portfolio"] == 1 and got["mixed"]["tax"] == 1, got["mixed"]
    assert got["mixed"]["edit"] == 0, got["mixed"]                 # 종목 바꾸기 of the portfolio without one: no line
    assert got["errors"] == [], got["errors"]


def test_every_screen_showing_won_amounts_at_a_temporary_rate_says_so_once():
    check(run(BODY))


def test_the_old_home_behind_the_switch_says_so_too():
    got = run(BODY, home2=False)
    assert got["one"]["home"] == 1 and got["two"]["home"] == 1 and got["none"]["home"] == 0 and got["fixed"]["home"] == 0, got
