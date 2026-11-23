# -*- coding: utf-8 -*-
"""v19.5b 후속 — 종목 순위의 미국 최소 크기 (src/v2/ranks.js · rank.jsx). Jack, 2026-11-13: "v19.5b's US minimum sizes (25억원 of
quarterly revenue, 100억원 of equity, at the day's rate) need a small data PR first."

여기서 보는 것 (더한 시험만 · 예전 시험은 그대로):
- 기준별 수익성 · 미국: 자본(data.json qeq, 달러) × 그날 환율(data.json fx)을 아는 회사 중 100억원 미만(음수 = 자본잠식 포함)만 빠져요 · 딱
  100억원은 들어가요 · 줄은 승인된 그대로 " · 자본 100억원 이상" (빠지는 회사마다 맞는 말)
- 크기를 모르는 회사 (qeq 빈 칸: 달러가 아닌 재무제표 · 분기 표 없음 · 아직 받지 않음)는 예전처럼 목록에 남아요 — 콘솔이 수와 이름을 말해요
  (리뷰 2026-11-23: 새로 조용히 빼는 회사가 없어요)
- 이 칸을 싣기 전의 파일 (미국 종목 중 qeq 가 있는 곳이 없음) · 환율이 없는 파일: 예전 그대로 (최소 크기 없이 · 줄에도 없음) · 콘솔이 말해요
- 기준별 성장 · 미국: 스위치(US_MIN_GROWTH_ON)가 꺼져 있어 예전 그대로 — 줄(rank.p.floorGrowthUs)이 승인되기 전에는 켜지 않아요 (시험이 둘을 묶어요)
- 한국 목록 · 다른 카드는 그대로
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_v2_ranks import run, st  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
PROFIT_FLOOR = "자본 100억원 이상"


def us(t, **kw):
    return st(t, "us", **kw)


# fx 1,000원: 자본 1,000만 달러 = 딱 100억원
STOCKS = [us("AAA", roe=90.0, qeq=50_000_000_000, qeqD="2026-09-30", cap=9.0),
          us("BBB", roe=80.0, qeq=10_000_000, qeqD="2026-09-30", cap=8.0),          # 딱 100억원: 들어가요
          us("CCC", roe=70.0, qeq=9_999_999, qeqD="2026-09-30", cap=7.0),           # 99.99999억원: 빠져요
          us("DDD", roe=60.0, qeq=-34_665_000, qeqD="2026-09-30", cap=6.0),         # 자본잠식 (Gartner 꼴): 빠져요
          us("EEE", roe=50.0, cap=5.0, fcur="EUR"),                                   # 재무제표 통화가 달러가 아님: qeq 빈 칸 → 예전처럼 남아요
          us("FFF", roe=40.0, cap=4.0),                                               # qeq 빈 칸 (분기 표 없음 · 아직 받지 않음) → 남아요
          us("GGG", roe=None, qeq=90_000_000, qeqD="2026-09-30", cap=3.0),          # ROE 빈 칸: 예전처럼 빠져요
          st("000010", roe=30.0, cap=2.0)]                                            # 한국: 이 규칙과 상관없어요
CORP = [{"t": "000010", "roeIn": {"eq": 500.0}, "rev": [300.0, 200.0, 150.0]}]
ALL_ROE = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]                                # 예전 목록 (ROE 순 · 빈 ROE 만 빠져요)


def test_us_profit_leaves_out_only_a_known_equity_under_100_eok_at_the_days_rate():
    got = run("""const CO = new Map(CORP.map((c) => [c.t, c])); const logs = []; console.info = (m) => logs.push(String(m));
out = { p: ts(K.critList(STOCKS, 'us', 'profit', CO, 1000)), kr: ts(K.critList(STOCKS, 'kr', 'profit', CO, 1000)),
  st: [K.critState(STOCKS, 'us', 'profit', CO, 1000), K.critState(STOCKS.slice(2, 4), 'us', 'profit', CO, 1000)],
  big: ts(K.critList(STOCKS, 'us', 'profit', CO, 1001)), small: ts(K.critList(STOCKS, 'us', 'profit', CO, 999)),
  consts: [K.US_MIN_EQ_EOK, K.US_MIN_REV_EOK, K.US_MIN_PROFIT_ON, K.US_MIN_GROWTH_ON, K.MIN_EOK],
  logs: logs.filter((l) => l.includes('profit list') && l.includes('(us)')) };""", STOCKS=STOCKS, CORP=CORP)
    assert got["consts"] == [100, 25, True, False, 100]
    assert got["p"] == ["AAA", "BBB", "EEE", "FFF"], got["p"]                 # CCC 100억 미만 · DDD 자본잠식만 빠져요 · EEE · FFF 크기를 몰라 남아요
    assert got["big"] == ["AAA", "BBB", "CCC", "EEE", "FFF"] and got["small"] == ["AAA", "EEE", "FFF"], got   # 그날 환율로 (1,001원 CCC 100.1억 · 999원 BBB 99.9억)
    assert got["kr"] == ["000010"]                                     # 한국은 예전 규칙 그대로 (corp.json 자본)
    assert got["st"] == ["rows", "none"], got                          # 둘 다 작으면 들어갈 종목 없음
    assert any("leaves out smallEquity 2: CCC CCC, DDD DDD" in l for l in got["logs"]), got["logs"]                 # 빠진 회사는 티커와 이름으로
    assert any("keeps 2 stocks with no qeq" in l and l.endswith(": EEE, FFF") for l in got["logs"]), got["logs"]   # 남긴 회사도 수와 이름으로


def test_a_file_without_the_figures_or_without_fx_keeps_the_lists_as_before_and_says_so():
    old = [{k: v for k, v in s.items() if k not in ("qeq", "qeqD")} for s in STOCKS]
    got = run("""const warns = []; console.warn = (m) => warns.push(String(m));
out = { p: ts(K.critList(OLD, 'us', 'profit', null, 1000)), st: K.critState(OLD, 'us', 'profit', null, null),
  noFx: [ts(K.critList(NEW, 'us', 'profit', null)), ts(K.critList(NEW, 'us', 'profit', null, 0)), K.critState(NEW, 'us', 'profit', null, null)],
  min: [K.usMinOf(OLD, 'us', 'profit', 1000), (K.usMinOf(NEW, 'us', 'profit', 1000) || {}).field, (K.usMinOf(NEW, 'us', 'profit', 1000) || {}).fx,
        K.usMinOf(NEW, 'us', 'profit', null), K.usMinOf(NEW, 'kr', 'profit', 1000), K.usMinOf(NEW, 'us', 'growth', 1000), K.usMinOf(NEW, 'us', 'value', 1000)],
  warns: warns.filter((w) => w.includes('minimum')) };""", OLD=old, NEW=STOCKS)
    assert got["p"] == ALL_ROE and got["st"] == "rows", got
    assert got["noFx"] == [ALL_ROE, ALL_ROE, "rows"], got                     # 환율이 없으면 예전 그대로 (빼지 않아요)
    assert got["min"] == [None, "qeq", 1000, None, None, None, None], got["min"]   # 한국 · 성장(스위치 꺼짐) · 다른 카드에는 없어요
    assert len(got["warns"]) == 2 and "no US stock of this file has qeq" in got["warns"][0] and "no day's rate" in got["warns"][1], got["warns"]


def test_us_growth_stays_as_before_while_its_switch_is_off():
    stocks = [us("AAA", g3=300.0, qrev=1_000, qrevD="2026-09-30"), us("BBB", g3=200.0, qrev=900_000_000, qrevD="2026-09-30"), us("CCC", g3=100.0)]
    got = run("out = { g: ts(K.critList(STOCKS, 'us', 'growth', null, 1000)), st: K.critState(STOCKS, 'us', 'growth', null, null) };", STOCKS=stocks)
    assert got == {"g": ["AAA", "BBB", "CCC"], "st": "rows"}, got           # 분기 매출 1,000달러인 AAA 도 그대로 (스위치를 켜면 빠져요)


def test_the_card_passes_the_days_rate_from_the_data():
    got = run("""const ld = loadOf(DATA, CORP); const noFx = loadOf({ ...DATA, fx: undefined }, CORP);
out = { rows: ts(K.rankRows(ld, 'us', 'crit', 'profit').rows), st: K.chipState(ld, 'us', null).crit.profit,
  noFx: [ts(K.rankRows(noFx, 'us', 'crit', 'profit').rows), K.chipState(noFx, 'us', null).crit.profit],
  trend: [ts(K.rankRows(ld, 'us', 'crit', 'lowVol').rows), ts(K.rankRows(noFx, 'us', 'crit', 'lowVol').rows)] };""",
              DATA={"fx": 1000.0, "stocks": [dict(s, vol=10.0 + i) for i, s in enumerate(STOCKS)]}, CORP=CORP)
    assert got["rows"] == ["AAA", "BBB", "EEE", "FFF"] and got["st"] == "rows", got
    assert got["noFx"] == [ALL_ROE, "rows"], got                           # 환율 없는 파일: 예전 그대로
    assert got["trend"][0] == got["trend"][1] == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"], got   # 다른 카드는 자본 · 환율을 보지 않아요


def test_the_growth_switch_waits_for_its_line_and_the_profit_line_is_the_approved_one():
    ranks = open(os.path.join(ROOT, "src", "v2", "ranks.js"), encoding="utf-8").read()
    copy = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    on = re.search(r"export const US_MIN_GROWTH_ON = (true|false);", ranks).group(1)
    line = re.search(r"floorGrowthUs: (null|\"[^\"]*\")", copy).group(1)
    assert on == "false" or line != "null", "US_MIN_GROWTH_ON 을 켜려면 rank.p.floorGrowthUs 가 승인된 줄이어야 해요 (CLAUDE.md 새 문구)"
    assert on == "false" and line == "null"                                # 지금: 꺼짐 · 제안은 docs/tasks/v18.3-new-strings-pending.md
    pend = open(os.path.join(ROOT, "docs", "tasks", "v18.3-new-strings-pending.md"), encoding="utf-8").read()
    assert "| `rank.p.floorGrowthUs` | 분기 매출 25억원 이상 |" in pend
    assert f'profit: "{PROFIT_FLOOR}"' in copy and "export const US_MIN_EQ_EOK = 100;" in ranks   # 승인된 말이 미국 규칙에도 맞아요 (100억원)
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `rank.floor.profit` | {PROFIT_FLOOR} | Jack, 2026-11-12 (design chat)." in appr


# ── 화면: 홈의 종목 순위 카드 (rank.jsx RankCard · 미국 · 기준별 · 수익성) ──
@pytest.fixture(scope="module")
def card():
    tmp = tempfile.mkdtemp(prefix="baepsae-usmin-")
    entry = os.path.join(tmp, "entry.js")
    with open(entry, "w", encoding="utf-8") as f:
        f.write(f"export * as RJ from {json.dumps(os.path.join(ROOT, 'src', 'v2', 'rank.jsx'))};\n")
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx", "--charset=utf8",
                        f"--outfile={tmp}/b.mjs", "--log-level=error", "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
    shutil.copy(os.path.join(FIX, "corp.json"), os.path.join(tmp, "corp.json"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def render(card, data, crit="profit", mk="us"):
    with open(os.path.join(card, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    code = ("const kv = {}; globalThis.localStorage = { getItem: (k) => kv[k] ?? null, setItem: (k, v) => { kv[k] = v; } };\n"
            f"kv['baepsae2.rank.v1'] = JSON.stringify({{ mk: '{mk}', chip: 'crit', crit: '{crit}' }});\n"
            "const B = await import('./b.mjs'); const { renderToStaticMarkup } = await import('react-dom/server'); const { createElement: h } = await import('react');\n"
            "const fs = await import('fs'); console.warn = () => {}; console.info = () => {};\n"
            "const DATA = JSON.parse(fs.readFileSync('./data.json', 'utf8')); const CORP = JSON.parse(fs.readFileSync('./corp.json', 'utf8'));\n"
            "const load = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const html = renderToStaticMarkup(h(B.RJ.RankCard, { load, store: { data: { decks: [], notes: {}, assume: {} }, writable: false } }));\n"
            "const rows = [...html.matchAll(/data-ui-v2=\"rank-row\" data-t=\"([^\"]+)\"/g)].map((m) => m[1]);\n"
            "console.log(JSON.stringify({ lines: html.match(/카드와 같은 순서[^<]*/g) || [], rows }));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=card, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def fixture_with_equity(neg=None, blank=None):
    """실행본에서 뽑은 시험 데이터(tests/fixtures/v2/data.json)의 미국 회사에 자본을 붙여요: neg 는 자본잠식, blank 는 빈 칸(크기 모름),
    나머지는 충분히 커요."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    for s in data["stocks"]:
        if s.get("cls") == "us" and not s.get("etf") and s["t"] != blank:
            s["qeq"], s["qeqD"] = (-1_000_000 if s["t"] == neg else 5_000_000_000), "2026-09-30"
    return data


def test_the_us_profit_line_names_the_approved_minimum_only_when_it_applies(card):
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        plain = json.load(f)
    before = render(card, plain)
    top = before["rows"][0]
    data = fixture_with_equity(neg=top)
    after = render(card, data)
    unknown = render(card, fixture_with_equity(blank=top))
    growth = render(card, data, crit="growth")
    kr = render(card, data, mk="kr")
    assert before["lines"] == ["카드와 같은 순서(ROE 높은 순)예요."], before        # 예전 파일: 예전 줄 그대로
    assert after["lines"] == [f"카드와 같은 순서(ROE 높은 순 · {PROFIT_FLOOR})예요."], after["lines"]
    assert top not in after["rows"] and after["rows"][:9] == [t for t in before["rows"] if t != top][:9], (top, after["rows"][:3])   # 자본잠식 회사만 빠지고 줄이 그 까닭을 말해요
    assert unknown["rows"] == before["rows"] and unknown["lines"] == after["lines"], unknown   # 크기를 모르는 회사는 예전 자리에 그대로
    assert growth["lines"] and PROFIT_FLOOR not in growth["lines"][0] and "25억" not in growth["lines"][0], growth["lines"]   # 성장: 스위치 꺼짐
    assert kr["lines"] == [f"카드와 같은 순서(ROE 높은 순 · {PROFIT_FLOOR})예요."], kr["lines"]   # 한국은 예전 그대로
