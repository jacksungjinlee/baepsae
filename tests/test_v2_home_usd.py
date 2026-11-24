# -*- coding: utf-8 -*-
"""홈의 미국 종가 날짜 줄 (app.usClose "미국 종목은 현지 기준 {md} 종가예요.") — 미국 종목은 달러로 값이 매겨진 종목이에요 (pf.usdOf:
데이터의 통화, cls 가 아니에요). 379800 KODEX 미국S&P500 은 cls 가 "us" 지만 한국 거래소에서 원으로, 한국 종가로 거래돼요.
미국 휴장일 다음 날 (2026-11-26 추수감사절: 11월 27일 아침 발행본은 한국 11월 26일 종가 · 미국 11월 25일 종가) 포트폴리오 만들기로
만든 포트폴리오가 379800 만 가지고 있으면, 예전에는 홈에 "미국 종목은 현지 기준 11월 25일 종가예요." 가 나왔어요 — 그 포트폴리오의
가격 중 미국 종가는 하나도 없는데요. 포트폴리오 · 내 수익은 #187 이 같은 규칙으로 고쳐요.

두 화면을 react-dom/server 로 실제 컴포넌트를 그려서 봐요:
- 홈 (today.jsx Home → home2.jsx Home2, 새 홈 스위치 HOME2 켜짐: 커밋한 빌드)
- 새 홈 스위치를 끈 홈 (today.jsx Home 의 v19.3d 화면, 비상 스위치: tests/smoke_v2.py home2_off_app 처럼 src 를 임시 폴더에 복사해서
  HOME2 만 꺼요. 커밋하지 않아요)
경우: 379800 만 (줄 없음) · 379800 + 삼성전자 (줄 없음) · 애플만 (줄) · 애플 + 379800 (줄) · 애플을 다 판 포트폴리오 (줄 없음) · 평소
(두 날짜가 같은 날: 어디에도 줄 없음). 새 홈은 다 판 애플 + 삼성전자 보유도 봐요 (다 판 종목은 세지 않아요: final review N3).
시험 데이터: tests/fixtures/v2 (379800 은 cls "us" · 통화 없음 = 원, 애플은 ccy "USD").
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
MODS = {"T": "v2/today.jsx", "L": "v2/load.js", "R": "v2/rules.js", "CP": "copy/v2.js"}
US_CLOSE = "미국 종목은 현지 기준 {md} 종가예요."
_B = {}


def _bundle(src_dir, tmp):
    entry = os.path.join(tmp, "entry.js")
    with open(entry, "w", encoding="utf-8") as f:
        for k, v in MODS.items():
            f.write(f"export * as {k} from {json.dumps(os.path.join(src_dir, v))};\n")
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                        "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs", "--log-level=error"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))


def bundle_dir(home2=True):
    """home2=True: 커밋한 src 그대로. home2=False: src 를 임시 폴더에 복사해서 today.jsx 의 HOME2 만 끈 것."""
    key = "on" if home2 else "off"
    if key not in _B:
        tmp = tempfile.mkdtemp(prefix=f"baepsae-home-usd-{key}-")
        _B[key] = tmp
        src = os.path.join(ROOT, "src")
        if not home2:
            src = os.path.join(tmp, "src")
            shutil.copytree(os.path.join(ROOT, "src"), src)
            p = os.path.join(src, "v2", "today.jsx")
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            old = re.findall(r"^export const HOME2 = (?:true|false);$", text, flags=re.M)
            assert old == ["export const HOME2 = true;"], old                 # 커밋한 빌드는 켜져 있어요 (Jack, 2026-11-08)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text.replace(old[0], "export const HOME2 = false;"))
        _bundle(src, tmp)
    return _B[key]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    for k in list(_B):
        shutil.rmtree(_B.pop(k), ignore_errors=True)


# 시험의 '지금'은 2026-11-27 (금) 09:00 KST. 발행은 그 한 시간 전이라 데이터는 새것이에요 (늦지 않음).
HELP = """
const NOW = Date.parse('2026-11-27T09:00:00+09:00'); Date.now = () => NOW;
const C = CP.C;
const logs = []; console.warn = (m) => logs.push(String(m)); console.info = () => {};
const read = (f) => JSON.parse(fs.readFileSync(FIX + '/' + f, 'utf8'));
const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);
// the load 2.0 makes of the fixture files, with the day's two close dates (the 11-27 morning publish after Thanksgiving by default)
const loadOf = (pxDate = '2026-11-26', usPxDate = '2026-11-25') => {
  const files = { data: read('data.json'), corp: read('corp.json'), macro: read('macro.json') };
  Object.assign(files.data, { pxDate, usPxDate, fxDate: pxDate });
  for (const f of ['data', 'corp', 'macro']) files[f].publishedAt = new Date(NOW - 3600000).toISOString();
  return L.resolveLoad({ data: { ok: true, data: files.data }, corp: { ok: true, data: files.corp }, macro: { ok: true, data: files.macro } }, NOW);
};
const usd = (t) => !/^[0-9]/.test(t);
const rec = (id, t, qty, price, date, fx) => ({ id, t, qty, price, date, ccy: usd(t) ? 'USD' : 'KRW', ...(usd(t) && fx ? { fx } : {}) });
const NK = { AAPL: 'Apple Inc.', '005930': '삼성전자', '379800': 'KODEX 미국S&P500' };
// a portfolio made with 포트폴리오 만들기: each holding's cls as the data has it (379800: "us"), its band rule (so a holding sold
// down to 0 and kept is still read, with 0 shares: rules.js SOLD_OUT_BANDS "own"), its purchases (and sales)
const CLS = { AAPL: 'us', '005930': 'kr', '379800': 'us' };
const PX = { AAPL: 200, '005930': 60000, '379800': 20000 };
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deck = (id, ts, sold = []) => ({ id, name: id, createdAt: '2026-01-05', planFx: 1450,
  holdings: ts.map((t) => ({ t, nk: NK[t], cls: CLS[t], target: 1 / ts.length, rules: band(1 / ts.length) })),
  purchases: ts.map((t, i) => rec('p' + i, t, 10, PX[t], '2026-03-02', 1450)),
  sales: sold.map((t, i) => rec('s' + i, t, 10, PX[t] * 1.1, '2026-09-01', 1400)) });
const storeOf = (decks) => ({ data: { v: 2, decks, notes: {}, assume: {} }, writable: true, locked: false, key: 'baepsae2.v1', preview: false });
const noop = () => {};
const home = (decks, load) => renderToStaticMarkup(h(T.Home, { load, store: storeOf(decks), setStoreData: noop, pad: 16, go: noop, onWhy: noop }));
// the US close-date lines on the screen, which 홈 drew it (the new one marks its root home2) and that it is the returning
// visitor's 홈 with the data loaded (its date line; not the first visit's home-hero, not the load-failure message)
const look = (decks, load) => { const html = home(decks, load); const L = lines(html);
  return { us: L.filter((x) => x.startsWith('미국 종목은')), home2: html.includes('data-ui-v2="home2"'),
    dated: html.includes('data-ui-v2="date-line"') && !html.includes('data-ui-v2="home-hero"') && !html.includes('data-ui-v2="load-fail"') }; };
const CASES = {
  only379: () => [deck('d379', ['379800'])],
  kr379: () => [deck('dkr379', ['005930', '379800'])],
  aapl: () => [deck('daapl', ['AAPL'])],
  aapl379: () => [deck('daapl379', ['AAPL', '379800'])],
  aaplSold: () => [deck('dsold', ['AAPL'], ['AAPL'])],
};
"""


def run(body, home2=True, **data):
    tmp = bundle_dir(home2)
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\nconst { T, L, R, CP } = B;\n" + f"const FIX = {json.dumps(FIX)};\n"
            + HELP + decl + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout)


SCREENS = """
  const after = loadOf(), normal = loadOf('2026-11-26', '2026-11-26');
  const s = after.data.stocks, by = (t) => s.find((x) => x.t === t);
  out = { copy: C.app.usClose, data: ['379800', 'AAPL', '005930'].map((t) => [by(t).cls, by(t).ccy || null]),
    after: Object.fromEntries(Object.entries(CASES).map(([k, f]) => [k, look(f(), after)])),
    normal: Object.fromEntries(Object.entries(CASES).map(([k, f]) => [k, look(f(), normal)])) };
"""
LINE = US_CLOSE.replace("{md}", "11월 25일")


def check_screens(got, new_home):
    assert got["copy"] == US_CLOSE                                         # 승인된 문장 그대로 (새 낱말 없음)
    assert got["data"] == [["us", None], ["us", "USD"], ["kr", None]]      # 379800: cls "us" · 원 (통화 없음) · 애플: 달러
    for when in ("after", "normal"):
        for k, v in got[when].items():
            assert v["home2"] is new_home and v["dated"], (when, k, v)    # 그 홈을 그렸어요 (데이터를 읽은 돌아온 사람의 홈)
    a = got["after"]
    assert a["only379"]["us"] == [], a["only379"]          # 예전: "미국 종목은 현지 기준 11월 25일 종가예요." — 원 · 한국 종가예요
    assert a["kr379"]["us"] == [], a["kr379"]              # 한국 종목과 함께여도 미국 종가는 없어요
    assert a["aapl"]["us"] == [LINE], a["aapl"]            # 진짜 미국 종목 (달러): 그대로 한 줄
    assert a["aapl379"]["us"] == [LINE], a["aapl379"]      # 애플과 함께면 그대로 한 줄
    assert a["aaplSold"]["us"] == [], a["aaplSold"]        # 다 판 애플은 가진 종목이 아니에요
    for k, v in got["normal"].items():
        assert v["us"] == [], (k, v)                       # 평소 (두 날짜가 같음): 어디에도 없어요


def test_home_names_the_us_close_only_for_dollar_priced_stocks_held():
    check_screens(run(SCREENS), new_home=True)


def test_home_counts_a_sold_out_us_stock_never_beside_shares_held():
    """새 홈: 애플을 다 팔고 남겨 둔 채 삼성전자를 가진 포트폴리오는 홈에 나오고, 다 판 애플은 0주로 점검에 들어가요 (띠 규칙, rules.js
    SOLD_OUT_BANDS "own"). 그래도 미국 날짜 줄은 쓰지 않아요 (x.qty !== 0, final review N3). 애플을 가지고 있으면 줄이 나와요."""
    got = run("""
      const after = loadOf();
      const sold = deck('dmix', ['AAPL', '005930'], ['AAPL']);
      const kept = deck('dmix2', ['AAPL', '005930']);
      const ev = (d) => { const ctx = R.todayCtx(after); const e = R.evaluateAll([d], ctx); return e.decks[0].holdings.map((x) => [x.t, x.qty]); };
      out = { sold: look([sold], after), kept: look([kept], after), soldHoldings: ev(sold), keptHoldings: ev(kept) };""")
    assert got["soldHoldings"] == [["AAPL", 0], ["005930", 10]], got["soldHoldings"]   # 다 판 애플도 점검에 있어요 (0주)
    assert got["keptHoldings"] == [["AAPL", 10], ["005930", 10]], got["keptHoldings"]
    assert got["sold"]["home2"] and got["sold"]["dated"] and got["kept"]["home2"]
    assert got["sold"]["us"] == [], got["sold"]
    assert got["kept"]["us"] == [LINE], got["kept"]


def test_the_old_home_behind_the_switch_follows_the_same_rule():
    """비상 스위치 (HOME2 끔): v19.3d 의 홈도 같은 규칙이에요."""
    check_screens(run(SCREENS, home2=False), new_home=False)
