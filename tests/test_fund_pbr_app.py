# -*- coding: utf-8 -*-
"""ETF · 펀드의 PBR 과 가치 점수 — 앱 쪽 (Jack, 2026-11-27, answer 12: "Yes, hide them: "ETF는 회사가 아니어서 PBR과 가치 점수를 계산하지
않아요."") · Node 로 진짜 함수와 컴포넌트를 불러요 (react-dom/server).

펀드 (data.json etf 참 또는 fund — validate_data.factor_fund · src/repair.js fundRow) 에는 회사의 장부가가 없어서 야후의 펀드 PBR (SPY 1.70 · 실제
P/B 약 5) 과 그 PBR 로 매긴 가치 점수 vz 는 뜻이 없어요. 파이프라인이 비우고 (tests/test_fund_pbr.py), 두 앱의 불러오기도 펀드 행에서 빼요 — 그
전에 발행된 파일 (다음 발행까지 사이트에 있는 파일) 도 보이지 않게요. 여기서 보는 것:
- 글자: 2.0 co.fundPbr · 예전 뱁새 FIX_FUND_PBR 이 Jack 의 줄 그대로 · 승인 표의 줄 (docs/tasks/v18.3-approved-in-chat.md) · 펀드의 정의가 관문과 같음
- 2.0 불러오기 (load.js resolveLoad → fcur.js fundBookOff): 어느 펀드에도 pbr · vz 가 없고, 회사는 그대로 · console 에 뺀 펀드 · 미리 보기는 조용히
- 2.0 두 종목 비교 (compare.jsx compareCells · oneFundLine): 미국 펀드의 PBR 칸 "–" + 줄 · 표에 한 번 (두 칸 모두 미국 펀드여도) · 국내 펀드 · 회사는
  그대로 · 숫자 옆에는 줄이 없음
- 2.0 관심 종목 (watch.jsx WatchScreen): 미국 펀드의 PBR 조건은 정보 없음 + 카드 밑에 줄 한 번 · 회사 줄 (통화 · 0 에 가까운 PBR) 은 없음 · 국내 펀드 · 회사는
  줄 없음
- 예전 뱁새 (data.js mergeStocks): 펀드 행의 pbr · vz 를 비우고 fundNoBook 표시 · 회사는 그대로 · console 에 뺀 펀드
- 예전 뱁새 종목 고르기 (detail.jsx StockRow): 펼친 미국 펀드의 "PER / PBR" 칸이 "… / –" 이고 칸 밑에 줄 한 번 · 영어 화면 · 간단 모드 · 국내 펀드 ·
  회사는 줄 없음
- 예전 뱁새 내 포트폴리오의 성향 (detail.jsx FactorTiltCard): 담은 미국 펀드가 가치 평균에서 빠지고 줄 한 번 · 펀드가 없으면 줄 없음 · 영어 화면은 줄 없음 ·
  NaN 없음
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import validate_data as V  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
LINE = "ETF는 회사가 아니어서 PBR과 가치 점수를 계산하지 않아요."          # Jack, 2026-11-27 (answer 12), 그대로
MODS = {"R": "src/repair.js", "FC": "src/v2/fcur.js", "LD": "src/v2/load.js", "Cm": "src/v2/compare.jsx", "Wx": "src/v2/watch.jsx",
        "W": "src/v2/watch.js", "Ed": "src/v2/edit.js", "E": "src/v2/engine.js", "CP": "src/copy/v2.js", "D": "src/data.js",
        "OF": "src/fixnote.jsx", "DT": "src/detail.jsx"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-fundpbr-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/b.mjs", "--log-level=error",
                            "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(autouse=True, scope="module")
def cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


def run(body):
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { R, FC, LD, Cm, Wx, W, Ed, E, CP, D, OF, DT } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            f"const LINE = {json.dumps(LINE, ensure_ascii=False)};\n"
            f"const read = (n) => JSON.parse(fs.readFileSync({json.dumps(FIX)} + '/' + n, 'utf8'));\n"
            "const ok = (d) => ({ ok: true, data: d });\n"
            "const NOW = Date.parse('2026-11-28T09:00:00+09:00');\n"
            "const loadOf = (opts = {}) => LD.resolveLoad({ data: ok(read('data.json')), corp: ok(read('corp.json')), macro: ok(read('macro.json')) }, NOW, opts);\n"
            "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    d = bundle_dir()
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=d)          # a file, not -e: the rows can be longer than an argument may be
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        r = subprocess.run([NODE, path], cwd=d, capture_output=True, text=True, timeout=180)
    finally:
        os.unlink(path)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout)


def fixture_rows():
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        return json.load(f)["stocks"]


FUND_WITH_BOOK = sorted(s["t"] for s in fixture_rows() if V.factor_fund(s) and (s.get("pbr") is not None or s.get("vz") is not None))


# ── 1. 글자 · 승인 · 정의 ────────────────────────────────────────────────────────────────────────
def test_the_line_is_jacks_in_both_apps_and_in_the_approved_table():
    got = run("out = { v2: C2.co.fundPbr, old: OF.FIX_FUND_PBR };")
    assert got == {"v2": LINE, "old": LINE}
    with open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8") as f:
        rows = [ln for ln in f if ln.startswith("| `co.fundPbr` |")]
    assert len(rows) == 1 and rows[0].split("|")[2].strip() == LINE and rows[0].split("|")[3].strip().startswith("Jack, 2026-11-27"), rows
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as f:
        assert f.read().count(LINE) == 1                                  # 2.0 의 글은 copy 한 곳에만


def test_the_fund_rule_is_the_gates():
    rows = fixture_rows() + [{"t": "X1", "etf": True}, {"t": "X2", "fund": True}, {"t": "X3", "etf": False}, {"t": "X4"},
                             {"t": "X5", "etf": "true"}, {"t": "X6", "fund": 1}]
    got = run(f"const rows = {json.dumps(rows, ensure_ascii=False)}; out = rows.map((s) => R.fundRow(s)).concat([R.fundRow(null), R.fundRow('x'), FC.fundRow === R.fundRow]);")
    assert got == [bool(V.factor_fund(s)) for s in rows] + [False, False, True]
    assert run("out = [R.FUND_BOOK, FC.FUND_BOOK];") == [list(V.FUND_BOOK_KEYS)] * 2


# ── 2. 2.0 불러오기 ─────────────────────────────────────────────────────────────────────────────
def test_the_2_0_load_drops_every_funds_pbr_and_vz_and_keeps_the_companies():
    assert len(FUND_WITH_BOOK) >= 10 and "SPY" in FUND_WITH_BOOK, FUND_WITH_BOOK          # 시험 데이터에 PBR 이 있는 미국 ETF 가 있어요
    got = run("""
      const raw = read('data.json').stocks;
      const L = loadOf();
      const left = L.data.stocks.filter((s) => R.fundRow(s) && (s.pbr != null || s.vz != null)).map((s) => s.t);
      const same = raw.filter((s) => !R.fundRow(s)).every((s) => { const x = L.byT.get(s.t); return x && x.pbr === s.pbr && x.vz === s.vz; });
      const kept = raw.filter((s) => R.fundRow(s)).every((s) => { const x = L.byT.get(s.t);
        return ['price', 'mz', 'lz', 'per', 'dy', 'vol', 'beta'].every((k) => JSON.stringify(x[k]) === JSON.stringify(s[k])); });
      const w = warns.filter((x) => x.includes('dropped from'));
      warns.length = 0;
      LD.resolveLoad({ data: ok(L.data), corp: ok(L.corp), macro: ok(L.macro) }, NOW);              // the same rows again: nothing left to drop
      const again = warns.filter((x) => x.includes('dropped from')).length;
      warns.length = 0;
      loadOf({ preview: true });
      out = { left, same, kept, w, again, preview: warns.filter((x) => x.includes('dropped from')).length,
        companies: raw.filter((s) => !R.fundRow(s) && s.pbr != null).length };""")
    assert got["left"] == [] and got["same"] is True and got["kept"] is True and got["companies"] > 300
    assert len(got["w"]) == 1 and f"from {len(FUND_WITH_BOOK)} fund rows" in got["w"][0], got["w"]
    assert all(t in got["w"][0] for t in FUND_WITH_BOOK), got["w"]
    assert got["again"] == 0 and got["preview"] == 0


def test_fund_book_off_only_removes_values_and_returns_the_codes():
    got = run("""
      const rows = [{ t: 'A', etf: true, pbr: 1.7, vz: 85, mz: 40 }, { t: 'B', etf: true, pbr: null }, { t: 'C', fund: true, vz: 0 },
                    { t: 'D', etf: false, pbr: 2.0, vz: 50 }, { t: 'E', cls: 'bond', etf: true, pbr: null, per: null }, null, 'x'];
      const off = FC.fundBookOff(rows);
      out = { off, rows: rows.slice(0, 5), none: FC.fundBookOff(null) };""")
    assert got["off"] == ["A", "C"] and got["none"] == []
    assert got["rows"] == [{"t": "A", "etf": True, "mz": 40}, {"t": "B", "etf": True, "pbr": None}, {"t": "C", "fund": True},
                           {"t": "D", "etf": False, "pbr": 2.0, "vz": 50}, {"t": "E", "cls": "bond", "etf": True, "pbr": None, "per": None}]


# ── 3. 2.0 두 종목 비교 ─────────────────────────────────────────────────────────────────────────
CMP = """
  const L = loadOf();
  const ctx = { stocks: L.data.stocks, points: { value: 3, div: 2 }, names: Ed.indNames(L.data.stocks), load: L, groups: null, row: null };
  const cells = (s) => Cm.compareCells(s, s ? L.coByT.get(s.t) || null : null, ctx);
  const pbr = (s) => { const c = cells(s).pbr; return [c.text, c.note, c.data.blank || null]; };
"""


def test_compare_shows_a_dash_and_the_line_for_a_us_fund_and_nothing_else_changes():
    got = run(CMP + """
      const raw = Object.fromEntries(read('data.json').stocks.map((s) => [s.t, s]));
      out = { spy: pbr(L.byT.get('SPY')), soxx: pbr(L.byT.get('SOXX')), jepi: pbr(L.byT.get('JEPI')), k379800: pbr(L.byT.get('379800')),
        k069500: pbr(L.byT.get('069500')), bond: pbr(L.byT.get('114260')), gold: pbr(L.byT.get('04020000')),
        aapl: pbr(L.byT.get('AAPL')), sam: pbr(L.byT.get('005930')),
        rawSpy: pbr(raw.SPY),                                                       // a row that still carries the number: the number, no line
        na: C2.co.tiles.na,
        textSpy: JSON.stringify(cells(L.byT.get('SPY'))) };""")
    for t in ("spy", "soxx", "jepi", "k379800"):                            # 미국 ETF (PBR 이 있던 SPY · SOXX, 없던 JEPI) · 379800 (cls us 의 국내 상장 ETF)
        assert got[t] == ["–", LINE, "fund"], (t, got[t])
    for t in ("k069500", "bond", "gold"):                                   # 국내 펀드 · 채권 · 금: PBR 이 원래 없어요 — 예전 그대로 (줄 없음)
        assert got[t][0] == got["na"] and got[t][1] != LINE and got[t][2] is None, (t, got[t])
    assert got["aapl"][0].endswith("배") and got["aapl"][1] is None and got["sam"][0].endswith("배")
    assert got["rawSpy"][0].endswith("배") and got["rawSpy"][1] is None, got["rawSpy"]   # 숫자 옆에는 줄이 없어요 (불러오기가 빼니 화면에는 오지 않아요)
    assert "1.72" not in got["textSpy"]                                    # 시험 데이터의 SPY PBR 1.72 는 어느 칸에도 없어요


def test_compare_gives_the_line_once_per_table():
    got = run(CMP + """
      const two = Cm.oneFundLine(cells(L.byT.get('SPY')), cells(L.byT.get('QQQ')));
      const one = Cm.oneFundLine(cells(L.byT.get('SPY')), cells(L.byT.get('AAPL')));
      const rev = Cm.oneFundLine(cells(L.byT.get('AAPL')), cells(L.byT.get('QQQ')));
      out = { two: two.map((c) => [c.pbr.text, c.pbr.note]), one: one.map((c) => [c.pbr.text, c.pbr.note]), rev: rev.map((c) => [c.pbr.text, c.pbr.note]) };""")
    assert got["two"] == [["–", LINE], ["–", None]]
    assert got["one"][0] == ["–", LINE] and got["one"][1][0].endswith("배") and got["one"][1][1] is None
    assert got["rev"][0][0].endswith("배") and got["rev"][1] == ["–", LINE]
    with open(os.path.join(ROOT, "src", "v2", "compare.jsx"), encoding="utf-8") as f:
        src = f.read()
    i, j = src.index("const B = compareCells(cand"), src.index("oneFundLine(A, B);")
    assert i < j < src.index("const vd = F.verdictOf(")                    # 화면이 표를 그리기 전에 한 번으로 줄여요


# ── 4. 2.0 관심 종목 ────────────────────────────────────────────────────────────────────────────
WATCH = """
  const L = loadOf();
  const watchHtml = (conds) => renderToStaticMarkup(h(Wx.WatchScreen, { load: L, store: { data: { v: 1, decks: [],
    watch: Object.fromEntries(Object.entries(conds).map(([t, cs], i) => [t, { at: '2026-11-01', ts: i + 1, conds: cs }])) }, writable: true },
    setStoreData() {}, pad: 0, onBack() {}, onAdd() {} }));
  const cardOf = (html, t) => { const i = html.indexOf(`data-ui-v2="watch-card" data-t="${t}"`); if (i < 0) return null;
    const j = html.indexOf('</section>', i); return html.slice(i, j); };
  const card = (t, conds) => { const c = cardOf(watchHtml({ [t]: conds }), t);
    return { n: count(c, LINE), ui: (c.match(/data-ui-v2="fund-pbr"/g) || []).length, chip: (c.match(/data-k="pbrBelow" data-state="([a-z]+)"/) || [])[1] || null,
      other: /data-ui-v2="(?:pbr-zero|fcur|fgn-cut|no-stmt|unit-chk|stmt-cur)"/.test(c), nan: /NaN/.test(c) }; };
"""


def test_a_watched_us_funds_pbr_condition_reads_no_data_with_the_line_once():
    got = run(WATCH + """
      const pb = [{ k: 'pbrBelow', v: 2 }], both = [{ k: 'pxBelow', v: 1000 }, { k: 'pbrBelow', v: 2 }, { k: 'dyAtLeast', v: 1 }];
      out = { spy: card('SPY', pb), spyBoth: card('SPY', both), qqq: card('QQQ', pb), k379800: card('379800', pb),
        spyPx: card('SPY', [{ k: 'pxBelow', v: 1000 }]), aapl: card('AAPL', pb), k069500: card('069500', pb),
        val: [W.watchValue(L.byT.get('SPY'), 'pbrBelow'), W.watchValue(L.byT.get('AAPL'), 'pbrBelow') > 0] };""")
    for k in ("spy", "spyBoth", "qqq", "k379800"):
        assert got[k] == {"n": 1, "ui": 1, "chip": "blank", "other": False, "nan": False}, (k, got[k])
    assert got["spyPx"]["n"] == 0 and got["spyPx"]["chip"] is None                 # PBR 조건이 없으면 줄도 없어요
    assert got["aapl"]["n"] == 0 and got["aapl"]["chip"] in ("met", "not", "stale")    # 회사: 숫자가 있어요 (시험 데이터의 날짜에 따라 '멈춤')
    assert got["k069500"]["n"] == 0                                                 # 국내 펀드: 예전 그대로
    assert got["val"] == [None, True]


# ── 5. 예전 뱁새: 합치기 ────────────────────────────────────────────────────────────────────────
LIVE = [
    {"t": "SPY", "nk": "SPY", "cls": "us", "ccy": "USD", "fxu": True, "s": "etc", "etf": True, "price": 728.32, "beta": 1.01, "vol": 19.6,
     "per": 23.2, "pbr": 1.7, "dy": 0.98, "vz": 85, "mz": 42, "lz": 99, "mom": 8.3},
    {"t": "VOO", "cls": "us", "ccy": "USD", "fxu": True, "etf": True, "price": 670.0, "beta": 1.0, "vol": 19.0, "per": 22.6, "pbr": 1.71, "vz": 85,
     "mz": 41},
    {"t": "379800", "nk": "KODEX 미국S&P500", "cls": "us", "s": "index", "fund": True, "etf": True, "price": 21990.0, "beta": 0.15, "vol": 15.8},
    {"t": "069500", "nk": "KODEX 200", "cls": "kr", "s": "index", "fund": True, "etf": True, "price": 76705.0, "beta": 1.08, "vol": 40.5},
    {"t": "088980", "nk": "맥쿼리인프라", "cls": "kr", "s": "broker", "etf": True, "price": 9630.0, "beta": 0.09, "vol": 11.8, "pbr": 1.1, "vz": 60,
     "pz": 4},
    {"t": "AAPL", "nk": "애플", "cls": "us", "ccy": "USD", "fxu": True, "s": "elec", "etf": False, "price": 230.0, "beta": 1.1, "vol": 26,
     "per": 32.0, "pbr": 48.0, "dy": 0.5, "vz": 1, "mz": 60, "qz": 99},
    {"t": "005930", "nk": "삼성전자", "cls": "kr", "s": "semi", "etf": False, "price": 99000, "beta": 1.1, "vol": 30, "per": 14.0, "pbr": 1.4,
     "vz": 40, "pz": 100, "mz": 70, "qz": 50},
]
MERGE = (f"const LIVE = {json.dumps(LIVE, ensure_ascii=False)};\n"
         "const M = D.mergeStocks(DT.BASE_STOCKS, LIVE); const by = Object.fromEntries(M.map((s) => [s.t, s]));\n")


def test_the_old_app_merge_drops_a_funds_pbr_and_vz_and_marks_it():
    got = run(MERGE + """
      const pick = (t) => { const s = by[t]; return [s.pbr, s.vz == null ? null : s.vz, !!s.fundNoBook, s.per == null ? null : s.per, s.mz == null ? null : s.mz]; };
      out = { rows: Object.fromEntries(['SPY', 'VOO', '379800', '069500', '088980', 'AAPL', '005930'].map((t) => [t, pick(t)])),
        line: Object.fromEntries(['SPY', 'VOO', '379800', '069500', '088980', 'AAPL', '005930'].map((t) => [t, OF.fundPbrRow(by[t])])),
        w: warns.filter((x) => x.includes('PBR')) };""")
    r = got["rows"]
    assert r["SPY"] == [None, None, True, 23.2, 42] and r["VOO"] == [None, None, True, 22.6, 41]      # VOO: 내장 종목 (예시 PBR 5) 도 오늘 데이터의 빈 칸
    assert r["379800"][:3] == [None, None, True] and r["069500"][:3] == [None, None, True] and r["088980"][:3] == [None, None, True]
    assert r["AAPL"] == [48.0, 1, False, 32.0, 60] and r["005930"] == [1.4, 40, False, 14.0, 70]
    assert got["line"] == {"SPY": True, "VOO": True, "379800": True, "069500": False, "088980": False, "AAPL": False, "005930": False}
    assert len(got["w"]) == 1 and "3개" in got["w"][0] and all(t in got["w"][0] for t in ("SPY", "VOO", "088980")), got["w"]


# ── 6. 예전 뱁새: 종목 고르기의 펼친 종목 ───────────────────────────────────────────────────────
ROW = MERGE + """
  const row = (t, lang = 'ko', mode = 'pro', edits = {}) => renderToStaticMarkup(h(DT.StockRow, { s: { ...by[t], ...edits }, lang, t: (k) => k, mode,
    settings: DT.DEFAULT_SETTINGS, loaded: false, onAdd() {}, open: true, onToggle() {}, peers: [], updateStock() {} }));
  const tile = (html) => { const m = text(html).match(/PER \\/ PBR\\n+([^\\n]+)/); return m ? m[1].trim() : null; };
  const view = (t, ...a) => { const html = row(t, ...a); return { n: count(html, LINE), ui: (html.match(/data-fix="fund-pbr"/g) || []).length, tile: tile(html), nan: /NaN/.test(html) }; };
"""


def test_the_old_app_stock_picker_row_shows_a_dash_and_the_line_once_for_a_us_fund():
    got = run(ROW + """
      out = { spy: view('SPY'), voo: view('VOO'), k379800: view('379800'), en: view('SPY', 'en'), simple: view('SPY', 'ko', 'simple'),
        k069500: view('069500'), k088980: view('088980'), aapl: view('AAPL'), sam: view('005930'), typed: view('SPY', 'ko', 'pro', { pbr: 2.5 }) };""")
    assert got["spy"] == {"n": 1, "ui": 1, "tile": "23 / –", "nan": False}, got["spy"]
    assert got["voo"] == {"n": 1, "ui": 1, "tile": "23 / –", "nan": False}, got["voo"]
    assert got["k379800"]["n"] == 1 and got["k379800"]["tile"].endswith("/ –")
    assert got["en"]["n"] == 0 and got["en"]["tile"] == "23 / –"                  # 영어 화면: 승인된 영어 글이 없어 '–' 만 (pxBad 줄처럼)
    assert got["simple"]["n"] == 0 and got["simple"]["tile"] is None                # 간단 모드는 칸이 없어요
    for t in ("k069500", "k088980"):                                               # 국내 펀드: 예전 그대로 '–' (줄 없음)
        assert got[t]["n"] == 0 and got[t]["tile"] == "– / –", (t, got[t])
    assert got["aapl"] == {"n": 0, "ui": 0, "tile": "32 / 48.0", "nan": False} and got["sam"]["n"] == 0 and got["sam"]["tile"] == "14 / 1.4"
    assert got["typed"]["n"] == 0 and got["typed"]["tile"] == "23 / 2.5"         # 사용자가 칸에 적은 숫자 옆에는 줄이 없어요


# ── 7. 예전 뱁새: 내 포트폴리오의 성향 ──────────────────────────────────────────────────────────
TILT = MERGE + """
  const card = (rows, lang = 'ko') => { const html = renderToStaticMarkup(h(DT.FactorTiltCard, { lang, t: (k) => k,
    metrics: { empty: false, rows: rows.map(([t, w]) => ({ t, mw: w * 100, wInv: w, stock: by[t] })) } }));
    return { n: count(html, LINE), names: ['가치', '모멘텀', '퀄리티', '규모'].filter((x) => text(html).split('\\n').map((y) => y.trim()).includes(x)),
      none: html.includes('ftNone'), nan: /NaN/.test(html) }; };
"""


def test_the_old_app_tilt_card_leaves_a_held_us_fund_out_of_value_and_says_why_once():
    got = run(TILT + """
      out = { mix: card([['SPY', 0.5], ['AAPL', 0.5]]), two: card([['SPY', 0.3], ['VOO', 0.3], ['005930', 0.4]]), en: card([['SPY', 0.5], ['AAPL', 0.5]], 'en'),
        none: card([['AAPL', 0.5], ['005930', 0.5]]), alone: card([['SPY', 1]]), kfund: card([['069500', 0.5], ['005930', 0.5]]),
        bare: card([['379800', 1]]) };""")
    assert got["mix"] == {"n": 1, "names": ["가치", "모멘텀", "퀄리티"], "none": False, "nan": False}, got["mix"]   # 가치는 애플만으로 (펀드는 빠져요)
    assert got["two"]["n"] == 1 and "가치" in got["two"]["names"]
    assert got["en"]["n"] == 0
    assert got["none"]["n"] == 0 and got["kfund"]["n"] == 0                     # 미국 펀드가 없으면 줄도 없어요 (국내 펀드는 원래 가치 점수가 없어요)
    assert got["alone"] == {"n": 1, "names": ["모멘텀"], "none": False, "nan": False}, got["alone"]   # 가치 막대가 없어진 까닭이 보여요
    assert got["bare"] == {"n": 1, "names": [], "none": True, "nan": False}, got["bare"]            # 성향을 낼 수 없는 카드에도 그 까닭


# ── 8. #203 리뷰 (1차: Opus · Fable) ───────────────────────────────────────────────────────────
SHEET = """
  const L = loadOf();
  const sheet = (t, conds = []) => {
    const s = L.byT.get(t);
    const store = { key: 'k', data: { v: 1, decks: [], watch: { [t]: { at: '2026-11-01', ts: 1, conds } } }, writable: true };
    const html = renderToStaticMarkup(h(Wx.CondSheet, { open: { t, name: s.nk, s, us: s.cls === 'us' }, store, setStoreData() {}, onClose() {} }));
    const field = (k) => { const i = html.indexOf(`data-ui-v2="watch-field" data-k="${k}"`); const j = html.indexOf('data-ui-v2="watch-field"', i + 10);
      return html.slice(i, j < 0 ? html.length : j); };
    const pb = field('pbrBelow');
    return { n: count(html, LINE), inPbr: count(pb, LINE), ui: (html.match(/data-ui-v2="fund-pbr"/g) || []).length,
      blank: count(pb, C2.watch.blank), now: /data-ui-v2="watch-now"/.test(pb), chip: (pb.match(/data-k="pbrBelow" data-state="([a-z]+)"/) || [])[1] || null,
      nan: /NaN/.test(html), others: ['pxBelow', 'dyAtLeast'].map((k) => count(field(k), LINE)) };
  };
"""


def test_the_2_0_condition_sheet_shows_the_line_once_under_a_us_funds_pbr_field():
    """리뷰 (Opus nit · Fable S2): 관심 종목의 조건 시트 — 미국 펀드의 PBR 칸은 정보 없음이고, 그 칸 밑에 Jack 의 줄 한 번 (빈 칸이어도 · 숫자를 적어
    정보 없음 칩이 보여도) · 다른 칸 밑에는 없음 · 회사 · 국내 펀드는 줄 없음."""
    got = run(SHEET + """
      out = { spy: sheet('SPY'), spyTyped: sheet('SPY', [{ k: 'pbrBelow', v: 2 }]), qqqPx: sheet('QQQ', [{ k: 'pxBelow', v: 1000 }]),
        k379800: sheet('379800'), voo: sheet('VOO'), aapl: sheet('AAPL'), aaplTyped: sheet('AAPL', [{ k: 'pbrBelow', v: 100 }]), k069500: sheet('069500') };""")
    for k in ("spy", "qqqPx", "k379800", "voo"):                         # 빈 PBR 칸: '정보 없음' 과 그 밑의 줄
        assert got[k] == {"n": 1, "inPbr": 1, "ui": 1, "blank": 1, "now": True, "chip": None, "nan": False, "others": [0, 0]}, (k, got[k])
    assert got["spyTyped"] == {"n": 1, "inPbr": 1, "ui": 1, "blank": 1, "now": False, "chip": "blank", "nan": False, "others": [0, 0]}, got["spyTyped"]
    for k in ("aapl", "aaplTyped", "k069500"):
        assert got[k]["n"] == 0 and got[k]["ui"] == 0 and got[k]["nan"] is False, (k, got[k])
    assert got["aapl"]["blank"] == 0 and got["aapl"]["now"] is True                    # 회사: 오늘의 PBR 이 보여요


def test_the_old_app_tilt_card_keeps_the_line_while_a_fund_is_left_out_even_with_a_typed_pbr():
    """리뷰 (Fable S3 · Opus nit): 성향 카드의 줄은 빠지는 가치 점수(vz)로 — 사용자가 종목 데이터 수정에 SPY 의 PBR 을 적어도 (vz 는 여전히 없어)
    SPY 는 가치 평균에서 빠지고 줄도 남아요. 종목 고르기의 줄은 예전 규칙 그대로 (PBR 이 '–' 일 때만 · 적은 숫자 옆에는 없음)."""
    # TILT and ROW both start with MERGE: one merge, both helpers
    got = run(TILT + ROW[len(MERGE):] + """
      const typed = { ...by.SPY, pbr: 2.5 };
      by.SPYT = typed;
      out = { typed: card([['SPYT', 0.5], ['AAPL', 0.5]]), plain: card([['SPY', 0.5], ['AAPL', 0.5]]),
        withVz: (() => { by.SPYV = { ...by.SPY, vz: 50 }; return card([['SPYV', 0.5], ['AAPL', 0.5]]); })(),
        rule: [OF.fundVzOut(typed), OF.fundPbrRow(typed), OF.fundVzOut(by.AAPL), OF.fundVzOut(by['069500']), OF.fundVzOut(null)],
        row: view('SPY', 'ko', 'pro', { pbr: 2.5 }) };""")
    assert got["typed"] == got["plain"] == {"n": 1, "names": ["가치", "모멘텀", "퀄리티"], "none": False, "nan": False}, got
    assert got["withVz"]["n"] == 0                                                         # 가치 점수가 있으면 빠지지 않아요 (줄 없음)
    assert got["rule"] == [True, False, False, False, False]
    assert got["row"]["n"] == 0 and got["row"]["tile"] == "23 / 2.5"                       # 종목 고르기: 적은 숫자 옆에는 줄이 없어요 (그대로)


def test_the_old_app_example_rows_carry_no_fund_pbr():
    """#203 리뷰: 예전 뱁새의 내장 예시 줄 (VOO · QQQ · SCHD · 379800 · 069500 · 금은 셋) 에도 펀드 PBR 이 없어요 — 오늘 데이터에 그 종목이 없어 예시
    값이 보일 때도 'PER / PBR' 은 '… / –' 이고, 미국 펀드는 (fundNoBook) 종목 고르기 · 성향 카드에 Jack 의 줄 한 번 (한국어 화면만) · 회사 줄은 그대로."""
    got = run("""
      const base = DT.BASE_STOCKS;
      const fundT = ['VOO', 'QQQ', 'SCHD', '379800', '069500', '04020000', '132030', '144600'];
      const rows = Object.fromEntries(fundT.map((t) => { const b = base.find((s) => s.t === t); return [t, b ? [b.pbr === null, b.vz == null, b.fundNoBook === true] : null]; }));
      const pbrs = base.filter((s) => s.pbr != null && s.s !== 'index' && s.s !== 'metal').length;
      const M = D.mergeStocks(base, [{ t: 'AAPL', cls: 'us', etf: false, price: 230, beta: 1.1, vol: 26, per: 32, pbr: 48, vz: 1, mz: 60 }]);
      const by = Object.fromEntries(M.map((s) => [s.t, s]));
      const row = (t, lang = 'ko') => renderToStaticMarkup(h(DT.StockRow, { s: by[t], lang, t: (k) => k, mode: 'pro', settings: DT.DEFAULT_SETTINGS,
        loaded: false, onAdd() {}, open: true, onToggle() {}, peers: [], updateStock() {} }));
      const tile = (html) => { const m = text(html).match(/PER \\/ PBR\\n+([^\\n]+)/); return m ? m[1].trim() : null; };
      const tilt = (rows, lang = 'ko') => count(renderToStaticMarkup(h(DT.FactorTiltCard, { lang, t: (k) => k,
        metrics: { empty: false, rows: rows.map(([t, w]) => ({ t, mw: w * 100, wInv: w, stock: by[t] })) } })), LINE);
      out = { rows, pbrs, live: [by.VOO.live, by.AAPL.live],
        tiles: Object.fromEntries(['VOO', 'QQQ', 'SCHD', '379800', '069500', '04020000', 'AAPL'].map((t) => { const x = row(t); return [t, [tile(x), count(x, LINE)]]; })),
        en: count(row('VOO', 'en'), LINE), tilt: [tilt([['VOO', 0.5], ['AAPL', 0.5]]), tilt([['069500', 0.5], ['AAPL', 0.5]]), tilt([['VOO', 0.5], ['AAPL', 0.5]], 'en')] };""")
    r = got["rows"]
    for t in ("VOO", "QQQ", "SCHD", "379800"):
        assert r[t] == [True, True, True], (t, r[t])
    for t in ("069500", "04020000", "132030", "144600"):                                    # 국내 펀드 · 금은: PBR 없음 (줄은 미국 펀드만)
        assert r[t] == [True, True, False], (t, r[t])
    assert got["pbrs"] > 60                                                                 # 회사 예시 줄의 PBR 은 그대로
    assert got["live"] == [False, True]                                                     # VOO 는 오늘 데이터에 없어 예시 줄
    tl = got["tiles"]
    assert tl["VOO"] == ["26 / –", 1] and tl["QQQ"] == ["32 / –", 1] and tl["SCHD"] == ["17 / –", 1] and tl["379800"] == ["26 / –", 1], tl
    assert tl["069500"] == ["12 / –", 0] and tl["04020000"] == ["0 / –", 0] and tl["AAPL"] == ["32 / 48.0", 0], tl
    assert got["en"] == 0 and got["tilt"] == [1, 0, 0]


def test_the_old_app_merge_with_a_fund_marked_for_an_unconfirmed_split():
    """#186 (Jack 답 11) 의 spNo 와 이 PR: 공시로 확인하지 못한 분할로 표시된 펀드 (그 전에 발행된 파일처럼 PBR · 가치 점수가 남은 행) — 합친 줄은
    베타 · 변동성 '–' (noRisk · spNo 의 규칙) 이면서 PBR · 가치 점수도 없고 fundNoBook (두 규칙이 서로 지우지 않아요) · 국내 펀드라 줄은 없음."""
    got = run("""
      const sp = { spNo: '2026-11-02', spNoF: ['vol', 'beta', 'hi', 'lo'] };
      const LIVE = [{ t: '069500', nk: 'KODEX 200', cls: 'kr', s: 'index', fund: true, etf: true, price: 76705, per: 11, pbr: 1.0, vz: 50, mz: 30, ...sp },
                    { t: '088980', nk: '맥쿼리인프라', cls: 'kr', s: 'broker', etf: true, price: 9630, pbr: 1.1, vz: 60, pz: 4, ...sp }];
      const M = D.mergeStocks(DT.BASE_STOCKS, LIVE); const by = Object.fromEntries(M.map((s) => [s.t, s]));
      const pick = (s) => [s.beta == null ? null : s.beta, s.vol == null ? null : s.vol, !!s.noRisk, s.pbr == null ? null : s.pbr, s.vz == null ? null : s.vz,
        !!s.fundNoBook, s.mz == null ? null : s.mz, s.live, OF.fundPbrRow(s), OF.fundVzOut(s)];
      out = { k069500: pick(by['069500']), k088980: pick(by['088980']), w: warns.filter((x) => x.includes('PBR')) };""")
    assert got["k069500"] == [None, None, True, None, None, True, 30, True, False, False], got["k069500"]
    assert got["k088980"] == [None, None, True, None, None, True, None, True, False, False], got["k088980"]
    assert len(got["w"]) == 1 and "2개" in got["w"][0], got["w"]
