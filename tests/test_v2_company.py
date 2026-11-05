# -*- coding: utf-8 -*-
"""뱁새 2.0 회사 페이지 (v19.1a, docs/tasks/v19.1-company-page.md) 의 순수 함수들 — Node 로 직접 돌려봐요.

- 네 칸의 문장 규칙 (Part B): 실적(한국: 영업이익 2년 · 적자가 먼저 · 2년 전 적자면 금액 / 미국: 야후 매출 증가 ±3%) · 가치(업종 중간
  PBR 의 0.8배 · 1.25배, PBR 있는 회사 5개 미만이면 자료 부족) · 배당(0원 · 줄임 · 2년 연속 · 한 번 3% 넘게 늘림 · 비슷 / 미국: 수익률
  0% · 있음) · 출렁임(베타 1.15 · 0.85). 판단에 필요한 숫자가 없으면 언제나 na ('판단할 자료가 없어요'), 짐작하지 않아요
- 재무 경고: 예전 뱁새의 네 신호, 확인을 할 수 있었던 회사만 '없어요' (미국은 v19.2 까지 없음)
- 기준 카드 순위: 시장 안 · 업종 안, 상위/하위, 금융회사 재무 안정은 해당 없음, 빈 칸으로 줄 세우지 않아요
- 지금 가격이 가정하는 것: 예전 DcfCard 계산(src/corp.jsx)과 숫자가 같아요 · 범위 밖 · 적자 · 준비 안 됨
- 주가는 무엇으로 움직였나: 예전 DecompCard 의 decomposeReturn 과 같아요
- 업종과 성장 비교는 같은 계산 기준(engine.growthBasis)끼리만 · 근거 수치는 화면의 숫자를 다시 만들 때만 · 공시 줄(90일, 지금 주가로 어림)
- 100만원어치: 1,000,000 × 수익률 ÷ 100, 1,000원 단위 · 회사 표시 색(흰 글자 4.5:1 이상, 살구 · 빨강 · 파랑 · 호박 없음)
- 기록: 내 메모 · 저장한 가정은 고르게 검사하고 내보내기 · 불러오기 · 합치기에 함께 가요
- 주소: #stocks/<코드>[/<탭>] (코드 모양이 아니면 #home)
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
MODS = {"K": "src/v2/company.js", "S": "src/v2/store.js", "R": "src/v2/routes.js", "E": "src/v2/engine.js", "OLD": "src/corp.jsx",
        "TOK": "src/ui/tokens.js", "F": "src/v2/cofmt.js", "CP": "src/copy/v2.js"}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                if k == "OLD":      # 예전 뱁새의 계산 함수만 (비교용)
                    f.write(f"export {{ dcfPerShare as oldDcf, reverseDcf as oldRev, decomposeReturn as oldDecomp }} from {json.dumps(os.path.join(ROOT, v))};\n")
                else:
                    f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/co.mjs", "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as T from './co.mjs';\nconst { K, S, R, E, TOK } = T;\n"
            "const loadOf = (data, corp = { companies: [] }) => ({ status: 'ok', data, corp, byT: new Map(data.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(corp.companies.map((c) => [c.t, c])) });\n" + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def st(t, nk="회사", cls="kr", **kw):
    s = {"t": t, "nk": nk, "ne": nk, "cls": cls, "price": 1000.0, "etf": False, "cap": 1.0, "ind": "semi", "indName": "반도체"}
    s.update(kw)
    return s


def fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", "v2", name), encoding="utf-8") as f:
        return json.load(f)


# ── 실적 칸 ──
def test_earnings_tile_rules_korea():
    cases = {"up": [300, 200, 100], "down": [100, 200, 300], "loss": [-10, 200, 300], "lossRising": [-5, -10, -20], "mixed": [300, 100, 200],
             "lossBase": [300, 200, -50], "zeroBase": [300, 200, 0], "gap": [300, None, 100]}
    got = run("""out = Object.fromEntries(Object.entries(C).map(([k, op]) => [k, K.earnKr({ op, fy: 2025 })]));
      out.none = K.earnKr(null); out.noOp = K.earnKr({ fy: 2025 }); out.short = K.earnKr({ op: [1, 2] });""", C=cases)
    assert got["up"]["rule"] == "up" and round(got["up"]["pct"], 6) == 200 and got["up"]["amount"] is None
    assert got["down"]["rule"] == "down" and round(got["down"]["pct"], 4) == round((100 / 300 - 1) * 100, 4)
    # 적자가 먼저예요 (줄고 있어도 · 적자가 줄어도), 숫자는 % 대신 그해 금액
    assert got["loss"]["rule"] == "loss" and got["loss"]["pct"] is None and got["loss"]["amount"] == -10
    assert got["lossRising"]["rule"] == "loss" and got["lossRising"]["amount"] == -5
    assert got["mixed"]["rule"] == "mixed" and round(got["mixed"]["pct"], 6) == 50
    for k in ("lossBase", "zeroBase"):                  # 2년 전이 0 이하: 늘었어도 % 없이 금액
        assert got[k]["rule"] == "up" and got[k]["pct"] is None and got[k]["amount"] == 300, k
    for k in ("gap", "none", "noOp", "short"):           # 한 해라도 없으면 판단하지 않아요
        assert got[k]["rule"] == "na", k


def test_earnings_tile_rules_us_use_yahoo_quarterly_growth():
    got = run("""out = [3, 2.9, -3, -2.9, 16.4, null].map((g) => K.earnUs({ cls: 'us', g3: g }).rule).concat([K.earnUs({ cls: 'us' }).rule]);""")
    assert got == ["up", "flat", "down", "flat", "up", "na", "na"]


def test_us_growth_number_always_says_what_it_is():
    """미국 실적 숫자 (Jack, 2026-11-05): 야후의 매출 증가는 최근 분기를 1년 전 같은 분기와 비교한 값이라, 그렇게 말하는 이름
    (co.tiles.usGrowth) 과 함께만 보여요. 그 이름이 승인 전(null)이면 숫자도 빼요. 연 · 3년 같은 말은 붙이지 않아요."""
    copy = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    # 승인 전: null 과 제안 주석 · 승인 뒤: 그 문구 (어느 쪽이든 이 검사는 그대로 통과해요)
    m = re.search(r'usGrowth: (?:null, // 제안 \(Jack 승인 대기\): "([^"]*)"|"([^"]*)",)', copy)
    assert m, "co.tiles.usGrowth 가 없어요"
    label = m.group(1) or m.group(2)
    assert "최근 분기" in label and "1년 전" in label and "{pct}" in label and "연 " not in label and "3년" not in label, label
    cofmt = open(os.path.join(ROOT, "src", "v2", "cofmt.js"), encoding="utf-8").read()
    assert "export function usGrowthText(g)" in cofmt and "C.co.tiles.usGrowth" in cofmt
    # 미국 실적 숫자를 보여 주는 곳(요약 칸 · 실적 탭)은 모두 usGrowthText 를 거쳐요: 예전 이름표를 붙인 맨 숫자는 없어요
    for f in ("company.jsx", "cotabs.jsx"):
        body = open(os.path.join(ROOT, "src", "v2", f), encoding="utf-8").read()
        assert "usGrowthText(r.g)" in body, f
        assert "growthUs" not in body and "signedPct(s.g3)" not in body and "signedPct(r.g)" not in body, f
    got = run("""const { F, CP } = T; const xs = [16.4, -3.24, 0.04, 1234.5, null, NaN, undefined, '5'];
      CP.C.co.tiles.usGrowth = null;
      out = { pending: xs.map((g) => F.usGrowthText(g)) };
      CP.C.co.tiles.usGrowth = M;
      out.filled = xs.map((g) => F.usGrowthText(g));""", M=label)
    assert got["pending"] == [None] * 8                                                # 이름이 승인 전이면 숫자도 없어요
    f = lambda p: label.replace("{pct}", p)
    assert got["filled"] == [f("+16.4%"), f("\u22123.2%"), f("0.0%"), f("+1,234.5%"), None, None, None, None], got["filled"]


# ── 가치 칸 ──
def test_value_tile_compares_pbr_with_the_group_median():
    grp = [st(f"00000{i}", pbr=p) for i, p in enumerate([1.0, 1.5, 2.0, 2.5, 3.0])]       # 중간 2.0
    got = run("""const one = (pbr, g = G) => K.valueTile({ t: 'X', cls: 'kr', pbr }, g);
      out = { cheap: one(1.6), cheapEdge: one(1.6000001), dear: one(2.5), similar: one(2.0), justAbove: one(1.61), justBelow: one(2.49),
        few: one(1.0, G.slice(0, 4)), noGroup: one(1.0, []), na: one(null), zero: one(0), blanks: one(1.0, G.map((x, i) => (i < 2 ? { ...x, pbr: null } : x))) };""",
              G=grp)
    assert got["cheap"]["rule"] == "cheap" and got["cheap"]["med"] == 2.0 and got["cheap"]["n"] == 5      # 1.6 = 0.8 × 2.0
    assert got["dear"]["rule"] == "dear"                                                                  # 2.5 = 1.25 × 2.0
    assert got["similar"]["rule"] == "similar" and got["justAbove"]["rule"] == "similar" and got["justBelow"]["rule"] == "similar"
    for k in ("few", "noGroup", "blanks"):
        assert got[k]["rule"] == "few", k
    assert got["na"]["rule"] == "na" and got["zero"]["rule"] == "na"


def test_value_tile_median_is_the_shown_two_decimals():
    grp = [st(f"00000{i}", pbr=p) for i, p in enumerate([1.111, 1.222, 1.333, 1.444, 1.555, 1.666])]   # 중간 1.3885 → 1.39
    got = run("out = K.valueTile({ t: 'X', cls: 'kr', pbr: 1.112 }, G);", G=grp)
    assert got["med"] == 1.39 and got["rule"] == "cheap", got                 # 1.112 ÷ 1.39 = 0.8 (보이는 두 숫자로 다시 계산해도 같아요)


# ── 배당 칸 ──
def test_dividend_tile_rules_korea():
    base = {"t": "X", "cls": "kr", "price": 50000, "fy": 2025, "dy": 2.0}     # dy: 그 사업보고서의 현금배당수익률 (dps 1,000원과 맞아요)
    cases = {"zeroMismatch": {"dps": 0, "dps3": [0, 100, 100]}, "na": {"dps": None}, "noPrev": {"dps": 1000, "dps3": [1000, None, 900]},
             "mismatch": {"dps": 1000, "dps3": [900, 800, 700]}, "cut": {"dps": 900, "dps3": [900, 1000, 1000]},
             "streak": {"dps": 1200, "dps3": [1200, 1100, 1000]}, "raised": {"dps": 1100, "dps3": [1100, 1000, 1000]},
             "steady": {"dps": 1020, "dps3": [1020, 1000, 1000]}, "same": {"dps": 1000, "dps3": [1000, 1000, 1000]},
             "cutThenRaise": {"dps": 1000, "dps3": [1000, 900, 1000]}, "tinyCut": {"dps": 999, "dps3": [999, 1000, 900]},
             "fromZero": {"dps": 100, "dps3": [100, 0, 0], "dy": 0.2}, "coOnly": {"dps": 1200}, "zero": {"dps": 0, "dy": 0},
             "noFy": {"dps": 1000, "dps3": [1000, 900, 800], "fy": None}}
    got = run("""out = Object.fromEntries(Object.entries(C).map(([k, x]) => [k, K.divKr({ ...B, ...x }, k === 'coOnly' ? { dps3: [1200, 1100, 1000] } : null)]));""",
              B=base, C=cases)
    assert got["zero"]["rule"] == "none" and got["zero"]["yieldPct"] == 0
    assert got["zeroMismatch"]["rule"] == "na"                              # 0원인데 보고서 수익률은 2%: 서로 맞지 않아 판단하지 않아요
    assert got["na"]["rule"] == "na" and got["na"]["yieldPct"] == 2.0
    assert got["noPrev"]["rule"] == "na" and got["noPrev"]["yieldPct"] == 2.0   # 비교할 해가 없으면 판단 안 함 (수익률은 그대로)
    assert got["mismatch"]["rule"] == "na"
    assert got["cut"]["rule"] == "cut" and got["tinyCut"]["rule"] == "cut"  # 줄었으면 조금이라도 '줄였어요'
    assert got["streak"]["rule"] == "streak" and got["streak"]["n"] == 2 and got["coOnly"]["rule"] == "streak"
    assert got["raised"]["rule"] == "raised" and got["cutThenRaise"]["rule"] == "raised"    # 한 번 3% 넘게: '비슷하게'가 아니에요
    assert got["fromZero"]["rule"] == "raised"
    assert got["steady"]["rule"] == "steady" and got["same"]["rule"] == "steady"
    assert got["streak"]["yieldPct"] == 2.0 and got["streak"]["dpsOk"]     # 수익률은 보고서의 dy 그대로 (오늘 종가로 나누지 않아요)
    assert got["noFy"]["yieldPct"] is None                                  # 어느 보고서인지 모르면 수익률을 보이지 않아요

def test_dividend_tile_rules_us_missing_is_not_no_dividend():
    got = run("out = [0, 0.32, null].map((dy) => K.divUs({ cls: 'us', dy })).concat([K.divUs({ cls: 'us' })]);")
    assert [g["rule"] for g in got] == ["none", "pays", "na", "na"] and got[1]["yieldPct"] == 0.32


def test_hundred_man_won_is_rounded_to_a_thousand_won():
    got = run("out = [2.4, 0.76, 0.32, 0, null, -1, 1.25].map((y) => K.perMillion(y));")
    assert got == [24000, 8000, 3000, 0, None, None, 13000]       # 12,500 → 13,000 (반올림)


# 리뷰가 찾은 실제 종목 (2026-11-04 발행본 값): 주식 분할 · 주당 칸에 총액을 적은 공시로 dps ÷ 오늘 종가가 터무니없어요
REAL = {
    "067900": {"t": "067900", "nk": "와이엔텍", "cls": "kr", "price": 6330.0, "fy": 2025, "dy": 1.48, "dps": 1809965900.0,
               "dps3": [1809965900.0, 1266976130.0, 904982950.0], "eps": 1645.0, "shr": 18199659},
    "001130": {"t": "001130", "nk": "대한제분", "cls": "kr", "price": 10730.0, "fy": 2025, "dy": 2.6, "dps": 4000.0,
               "dps3": [4000.0, 3500.0, 2500.0], "eps": -2395.0, "shr": 16900000},
    "134380": {"t": "134380", "nk": "미원화학", "cls": "kr", "price": 11190.0, "fy": 2025, "dy": 4.76, "dps": 4500.0,
               "dps3": [4500.0, 4000.0, 3500.0], "eps": 1869.0, "shr": 21992680},
    "015360": {"t": "015360", "nk": "INVENI", "cls": "kr", "price": 13680.0, "fy": 2025, "dy": 8.1, "dps": 5400.0,
               "dps3": [5400.0, 4000.0, 8750.0], "eps": 3116.0, "shr": 26250000},
    "005930": {"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 219500.0, "fy": 2025, "dy": 1.5, "dps": 1668.0,
               "dps3": [1668.0, 1446.0, 1444.0], "eps": 25780.0, "shr": 5846278608, "cap": 1283.258},
    "005380": {"t": "005380", "nk": "현대차", "cls": "kr", "price": 277500.0, "fy": 2025, "dy": 1.9, "dps": 10000.0, "eps": 50941.0,
               "shr": 203466492, "cap": 56.462},
}
REAL_CO = {"067900": {"ni": [304.3, 313.1, 240.7], "shm": 18.2, "fy": 2025}, "001130": {"ni": [-251.4, 488.3, 812.4], "shm": 16.9, "fy": 2025},
           "134380": {"ni": [247.3, 269.3, 218.1], "shm": 21.99, "fy": 2025}, "015360": {"ni": [867.2, 285.7, 340.5], "shm": 26.25, "fy": 2025},
           "005930": {"ni": [452068.0, 344513.5, 154871.0], "shm": 5846.28, "fy": 2025, "dcfReady": True, "price": 219500.0, "r36": 220.0,
                      "eps": 25780.0, "bq": "2026.2Q"},
           "005380": {"ni": [103647.8, 132299.1, 122723.0], "shm": 203.47, "fy": 2025, "dcfReady": True, "price": 277500.0, "r36": 45.5,
                      "eps": 50941.0, "bq": "2026.2Q"}}


def test_korean_yield_is_the_reports_own_and_per_share_figures_are_cross_checked():
    got = run("""out = Object.fromEntries(Object.entries(RS).map(([t, s]) => [t, { div: K.divKr(s, null), agrees: E.dpsAgrees(s), ky: E.krDivYield(s),
        card: E.cardRaw(s, E.CARDS.find((c) => c.id === 'div')), pm: K.perMillionView(K.divKr(s, null).yieldPct) }]));""", RS=REAL)
    for t in ("067900", "001130", "134380", "015360"):                     # 와이엔텍 · 대한제분 · 미원화학 · INVENI
        g = got[t]
        assert g["div"]["yieldPct"] == REAL[t]["dy"], (t, g["div"])         # 보이는 수익률 = 보고서의 dy (1.48 · 2.6 · 4.76 · 8.1 %)
        assert not g["agrees"] and g["ky"] is None and g["card"] is None    # dps ÷ 종가(28,593,458% · 37.3% · 40.2% · 39.5%)는 쓰지 않아요
        assert g["div"]["rule"] == "na" and not g["div"]["dpsOk"]            # 주당 배당 · 추세 · 배당성향도 보이지 않아요
        assert g["pm"]["won"] == round(1e6 * REAL[t]["dy"] / 100 / 1000) * 1000, (t, g["pm"])
    assert got["067900"]["pm"]["won"] == 15000 and got["134380"]["pm"]["won"] == 48000 and got["015360"]["pm"]["won"] == 81000
    sam = got["005930"]
    assert sam["agrees"] and abs(sam["ky"] - 1668 / 219500 * 100) < 1e-9 and sam["div"]["rule"] == "streak" and sam["div"]["yieldPct"] == 1.5
    edge = run("out = [E.dpsAgrees({ dps: 100, price: 1000, dy: 10 }), E.dpsAgrees({ dps: 100, price: 1000, dy: 3.4 }), E.dpsAgrees({ dps: 100, price: 1000, dy: 3.3 }),"
               " E.dpsAgrees({ dps: 100, price: 1000, dy: 30 }), E.dpsAgrees({ dps: 100, price: 1000, dy: 31 }), E.dpsAgrees({ dps: 100, price: 1000 }),"
               " E.dpsAgrees({ dps: 100, price: 1000, dy: 0 }), E.dpsAgrees({ dps: 0, dy: 0 }), E.dpsAgrees({ dps: 0 }), E.dpsAgrees({ dps: 0, dy: 1 })];")
    assert edge == [True, True, False, True, False, True, False, True, True, False], edge   # 1/3 ~ 3 배 안 · dy 가 없으면 예전처럼
    # 보고서 수익률이 30% 를 넘으면 믿지 않아요 (리뷰 sweep: 지투파워 33.7% · 흥국 56% · 피코그램 100%): 수익률도 · 100만원 줄도 없음
    big = run("out = [33.7, 56, 100, 30].map((dy) => [K.divKr({ t: 'X', cls: 'kr', price: 10000, fy: 2025, dps: 50, dy }, null), K.divUs({ cls: 'us', dy })]);")
    assert all(k["yieldPct"] is None and k["rule"] == "na" and u["rule"] == "na" for k, u in big[:3]) and big[3][1]["yieldPct"] == 30, big


def test_hundred_man_won_for_korea_is_dps_over_todays_close():
    """100만원어치 (한국, Jack 2026-11-05): 1,000,000 ÷ 오늘 종가 × 최근 사업보고서 주당 배당, 1,000원 단위 (세전).
    주당 배당이나 가격이 없거나 가격이 0 이하면 줄을 빼요. 0원이면 '배당이 없어요' 그대로(줄 없음). 주당 배당이 그 보고서의
    수익률과 맞지 않으면(주식 분할 · 총액 공시) 터무니없는 금액 대신 줄을 빼요. 미국은 v19.2 까지 야후 수익률 그대로."""
    sam = REAL["005930"]                                                    # dps 1,668원 · 종가 219,500원 · 보고서 수익률 1.5%
    cases = {"sam": sam, "samToday": {**sam, "price": 218000.0}, "hyundai": REAL["005380"],
             "zero": {**sam, "dps": 0, "dy": 0}, "noDps": {**sam, "dps": None}, "noDps2": {k: v for k, v in sam.items() if k != "dps"},
             "noPrice": {**sam, "price": None}, "zeroPrice": {**sam, "price": 0}, "negPrice": {**sam, "price": -5},
             "split": REAL["067900"], "total": REAL["134380"], "noDyHuge": {**sam, "dy": None, "dps": 80000.0},
             "noDyOk": {**sam, "dy": None}, "tiny": {"t": "X", "cls": "kr", "price": 100000.0, "fy": 2025, "dy": 0.05, "dps": 50.0}}
    got = run("""out = Object.fromEntries(Object.entries(C).map(([k, s]) => [k, { pm: K.perMillionKr(s), rule: K.divKr(s, null).rule }]));""", C=cases)
    raw = 1e6 / 219500 * 1668                                               # 7,599원 → 약 8,000원
    assert abs(got["sam"]["pm"]["raw"] - raw) < 1e-6 and got["sam"]["pm"]["won"] == 8000
    assert got["samToday"]["pm"]["won"] == round(1e6 / 218000 * 1668 / 1000) * 1000 == 8000
    assert got["hyundai"]["pm"]["won"] == round(1e6 / 277500 * 10000 / 1000) * 1000 == 36000
    assert got["zero"]["pm"] is None and got["zero"]["rule"] == "none"     # 0원: 배당이 없어요 (줄 없음)
    for k in ("noDps", "noDps2", "noPrice", "zeroPrice", "negPrice"):
        assert got[k]["pm"] is None, k                                      # 주당 배당 · 가격이 없거나 가격이 0 이하: 줄을 빼요
    assert got["split"]["pm"] is None and got["total"]["pm"] is None        # 와이엔텍(분할) · 미원화학(총액): 터무니없는 금액 없음
    assert got["noDyHuge"]["pm"] is None                                    # 보고서 수익률이 없어도 연 30% 넘으면 믿지 않아요 (DY_MAX)
    assert got["noDyOk"]["pm"]["won"] == 8000                               # 맞춰 볼 수익률이 없으면 주당 배당 ÷ 종가 그대로 (engine.dpsAgrees)
    assert got["tiny"]["pm"] == {"under": True, "raw": 500.0}               # 1,000원이 안 되면 '1년에 1,000원이 안 돼요' (약 0원 없음)
    # 화면: 한국은 perMillionKr, 미국은 야후 수익률 (perMillionView) 그대로 · 근거 문장은 Jack 의 문장
    tabs = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    assert 'const pm = r.rule === "none" ? null : us ? perMillionView(r.yieldPct) : perMillionKr(s);' in tabs
    copy = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    assert 'basisKr: "{fy}년 사업보고서 주당 배당과 오늘 주가로 계산했어요.",' in copy


def test_dcf_headline_says_grows_or_shrinks_without_a_minus_sign():
    """지금 가격이 가정하는 것 첫 문장 (Jack, 2026-11-05): 0 이상이면 '… {g}% 는다는 …', 0보다 작으면 '… {g}% 준다는 …' 에 빼기 없이."""
    got = run("""const { F } = T; out = [22.1, 0, -0, 0.04, -3.2, -30, 60, NaN, null].map((g) => F.dcfHeadText(g));""")
    up = lambda g: f"지금 주가에는 이익이 첫해 {g}% 는다는 가정이 담겨 있어요"
    down = lambda g: f"지금 주가에는 이익이 첫해 {g}% 준다는 가정이 담겨 있어요"
    assert got == [up("22.1"), up("0.0"), up("0.0"), up("0.0"), down("3.2"), down("30.0"), up("60.0"), None, None], got
    assert all("−" not in x and "-" not in x for x in got if x)


def test_sample_cards_line_names_the_first_two_cards():
    """'고른 기준 카드가 없어서 가치·배당 카드를 먼저 보여 드려요.' (Jack, 2026-11-05): 고른 카드가 없을 때 보이는 두 장이 정말 가치 · 배당이에요."""
    got = run("out = [K.myCards([]).ids, T.CP.C.co.fit.sample, T.CP.C.build.cards.value.name, T.CP.C.build.cards.div.name];")
    assert got[0] == ["value", "div"] and got[1] == "고른 기준 카드가 없어서 가치·배당 카드를 먼저 보여 드려요.", got
    assert got[2] == "가치" and got[3] == "배당", got


def test_hundred_man_won_never_shows_zero_for_a_payer():
    # 주성엔지니어링 0.19% · 가온전선 0.1% · 삼천당제약 0.02% · 영풍 0.01% (리뷰: 예전 계산은 '1년에 약 0원')
    got = run("out = [0.19, 0.1, 0.02, 0.01, 0, null].map((y) => K.perMillionView(y));")
    assert got[0]["won"] == 2000 and got[1]["won"] == 1000 and got[2]["under"] and got[3]["under"] and got[4] is None and got[5] is None


def test_payout_is_on_one_basis_and_inside_0_to_100():
    got = run("""out = { sam: K.payout(RS['005930'], RC['005930']), mw: K.payout(RS['134380'], RC['134380']), loss: K.payout(RS['001130'], RC['001130']),
      over: K.payout({ ...RS['005930'], dps: 20000, dy: 9.1 }, RC['005930']), us: K.payout({ ...RS['005930'], cls: 'us' }, RC['005930']),
      noNi: K.payout(RS['005930'], { ...RC['005930'], ni: [null, 1, 1] }) };""", RS=REAL, RC=REAL_CO)
    assert abs(got["sam"]["pct"] - 1668 * 5846278608 / (452068.0 * 1e8) * 100) < 1e-9 and 21 < got["sam"]["pct"] < 22 and got["sam"]["fy"] == 2025
    assert got["mw"] is None and got["loss"] is None                      # 미원화학: dps 가 dy 와 맞지 않음 · 대한제분: 적자
    assert got["over"]["out"] > 100 and "pct" not in got["over"]          # 100% 를 넘으면 보이지 않아요 (화면이 로그를 남겨요)
    assert got["us"] is None and got["noNi"] is None



# ── 출렁임 칸 ──
def test_risk_tile_uses_the_old_apps_thresholds():
    got = run("out = [1.16, 1.15, 0.85, 0.84, 1.0, null].map((b) => K.riskTile({ beta: b }).rule).concat([K.riskTile({}).rule]);")
    assert got == ["big", "similar", "similar", "small", "similar", "na", "na"]


# ── 재무 경고 ──
def test_warning_flags_only_claim_checks_that_ran():
    kr = {"t": "X", "cls": "kr"}
    got = run("""out = {
      flags: K.warnings(KR, { fl: { cr: 77, icr: 0.5, l3: 1, imp: 1 }, ni: [1, 2, 3], fy: 2025, bq: '2026.2Q' }),
      clean: K.warnings(KR, { ni: [1, -2, 3], fy: 2025 }),
      noNi: K.warnings(KR, { ni: [1, null, 3], fy: 2025 }), noFy: K.warnings(KR, { ni: [1, 2, 3] }), noCo: K.warnings(KR, null),
      us: K.warnings({ t: 'AAPL', cls: 'us' }, { fl: { cr: 50 }, ni: [1, 2, 3], fy: 2025 }),
      all: K.warnings(KR, { flRan: ['cr', 'icr', 'l3', 'imp'], ni: [1, 2, 3], fy: 2025 }), fin: K.warnings(KR, { flRan: ['l3', 'imp'], ni: [1, 2, 3], fy: 2025 }) };""", KR=kr)
    assert [f["code"] for f in got["flags"]["flags"]] == ["cr", "icr", "l3", "imp"]
    assert got["flags"]["quarter"] == {"y": 2026, "q": 2} and got["flags"]["fy"] == 2025
    # '없어요'는 네 가지 확인을 모두 했다는 기록(flRan)이 있을 때만: corp.json 은 아직 그걸 적지 않아요 (금융업은 유동비율 · 이자보상배율을 건너뛰어요)
    for k in ("clean", "noNi", "noFy", "noCo", "us", "fin"):
        assert not got[k]["allRan"], k
    assert got["us"]["flags"] == [] and got["all"]["allRan"] and got["fin"]["ran"] == ["l3", "imp"]



# ── 기준 카드 순위 ──
def test_card_ranks_within_market_and_group():
    # 코드는 0 으로 끝나요 (한국 우선주는 0 으로 끝나지 않아서 순위에서 빠져요: engine.isPreferred)
    stocks = [st(f"{i:05d}0", f"회사{i}", vz=i * 10, roe=i, g3=i, debt=100 - i, lz=i, mz=i, cap=float(i), dps=i * 10, price=1000.0)
              for i in range(1, 11)]
    stocks[0]["ind"] = "bank"                          # 금융회사: 재무 안정은 해당 없음
    stocks.append(st("US1", "US One", "us", vz=50))
    got = run("""const L = { stocks: ST };
      out = { top: K.cardRanks(ST.find((s) => s.t === '000100'), ST, 'market'), bottom: K.cardRanks(ST.find((s) => s.t === '000020'), ST, 'market'),
        fin: K.cardRanks(ST[0], ST, 'market'), blank: K.cardRanks({ ...ST[4], roe: null }, ST.map((s, i) => (i === 4 ? { ...s, roe: null } : s)), 'market'),
        ind: K.cardRanks(ST.find((s) => s.t === '000100'), ST, 'ind'), us: K.cardRanks(ST[10], ST, 'market'), cards: K.RANK_CARDS };""", ST=stocks)
    assert got["cards"] == ["value", "div", "growth", "profit", "stable", "lowVol", "trend", "large"]
    top = {r["id"]: r for r in got["top"]["rows"]}
    assert got["top"]["n"] == 10 and top["value"] == {"id": "value", "side": "top", "pct": 10}     # 10개 중 1등 → 상위 10%
    bot = {r["id"]: r for r in got["bottom"]["rows"]}
    assert bot["value"] == {"id": "value", "side": "bottom", "pct": 20}                             # 10개 중 9등 → 하위 20%
    assert {r["id"]: r for r in got["fin"]["rows"]}["stable"] == {"id": "stable", "na": True}
    assert {r["id"]: r for r in got["blank"]["rows"]}["profit"] == {"id": "profit", "blank": True}
    assert got["ind"]["n"] == 9 and {r["id"]: r for r in got["ind"]["rows"]}["value"]["pct"] == 12      # 반도체 9개 중 1등 → 상위 12%
    assert got["us"]["n"] == 1                                                                       # 시장마다 따로 (한국과 섞지 않아요)


def test_my_cards_are_the_latest_portfolios_or_the_first_two():
    got = run("""out = [K.myCards([]), K.myCards([{ settings: { points: { div: 3, value: 2, divGrowth: 5 } } }, { settings: { points: { profit: 4, large: 1 } } }]),
      K.myCards([{ settings: { points: {} } }]), K.myCards(null)];""")
    assert got[0] == {"ids": ["value", "div"], "picked": False} and got[2] == got[0] and got[3] == got[0]
    assert got[1] == {"ids": ["profit", "large"], "picked": True}                 # 가장 최근 포트폴리오, 카드 순서대로, 준비 중 카드 빼고


# ── 실적 탭: 업종과 성장 비교 ──
def test_growth_is_compared_only_within_the_same_basis():
    # g3 = 2년 연평균 (rev0, rev2 로 맞춘 값) 인 회사 6개 + 기준이 1년인 회사 1개
    def two_year(t, g):
        r2 = 1000.0
        r0 = r2 * (1 + g / 100) ** 2
        return st(t, g3=g), {"t": t, "rev": [r0, 1000.0, r2]}
    rows = [two_year(f"0000{i}0", g) for i, g in enumerate([2.0, 4.0, 6.0, 8.0, 10.0])] + [two_year("000090", 20.0)]
    one = (st("000080", g3=50.0), {"t": "000080", "rev": [1500.0, 1000.0, None]})
    stocks = [r[0] for r in rows] + [one[0]]
    corp = [r[1] for r in rows] + [one[1]]
    got = run("""const L = loadOf({ stocks: ST }, { companies: CO });
      const g = (t) => K.growthVsInd(L.byT.get(t), L.coByT.get(t), ST, L.coByT);
      out = { fast: g('000090'), slow: g('000000'), mid: g('000030'), one: g('000080'), us: K.growthVsInd({ cls: 'us', g3: 5 }, null, ST, L.coByT),
        few: K.growthVsInd(L.byT.get('000090'), L.coByT.get('000090'), ST.slice(0, 3).concat([ST[5]]), L.coByT) };""", ST=stocks, CO=corp)
    assert got["fast"]["basis"] == "y2" and got["fast"]["n"] == 6 and got["fast"]["med"] == 7.0 and got["fast"]["rule"] == "faster"
    assert got["slow"]["rule"] == "slower" and got["mid"]["rule"] == "similar"          # 8 vs 7: 1%p 안쪽은 '비슷하게'
    assert got["one"] is None                                                           # 1년 기준 회사는 1년 기준 업종 회사가 5개 안 돼서 없음
    assert got["us"] is None and got["few"] is None


# ── 지금 가격이 가정하는 것 · 주가는 무엇으로 움직였나 (예전 뱁새 계산과 같아요) ──
def test_reverse_dcf_matches_the_old_card():
    cases = [{"price": 219500, "ni0": 452068, "sharesM": 5846.28, "fade": f, "disc": d, "term": t} for f in (False, True)
             for d, t in ((10, 2), (8, 1), (14, 3.5))] + [{"price": 100, "ni0": 452068, "sharesM": 5846.28, "fade": False, "disc": 10, "term": 2},
                                                          {"price": 9e7, "ni0": 452068, "sharesM": 5846.28, "fade": False, "disc": 10, "term": 2}]
    got = run("""out = C.map((c) => [K.reverseDcf(c), T.oldRev(c), K.dcfPerShare({ ...c, g1: 7 }), T.oldDcf({ ...c, g1: 7 })]);""", C=cases)
    for new, old, v1, v0 in got:
        assert new == old and v1 == v0, (new, old, v1, v0)
    assert got[-2][0] == {"edge": "low"} and got[-1][0] == {"edge": "high"}


def test_implied_growth_uses_the_old_cards_defaults():
    corp = fixture("corp.json")
    sam = next(c for c in corp["companies"] if c["t"] == "005930")
    got = run("""const s = { t: '005930', cls: 'kr', price: CO.price, cap: CO.cap };
      out = { dflt: K.impliedGrowth(s, CO), check: T.oldRev({ price: CO.price, ni0: CO.ni[0], sharesM: CO.shm, fade: true, disc: 10, term: 2 }),
        mine: K.impliedGrowth(s, CO, { disc: 8, term: 1 }), us: K.impliedGrowth({ ...s, cls: 'us' }, CO), notReady: K.impliedGrowth(s, { ...CO, dcfReady: false }),
        loss: K.impliedGrowth(s, { ...CO, ni: [-5, 1, 1] }), noNi: K.impliedGrowth(s, { ...CO, ni: [null, 1, 1] }), D: K.DCF };""", CO=sam)
    assert got["D"]["disc"] == 10 and got["D"]["term"] == 2 and got["D"]["fade"] is True and got["D"]["lo"] == -30 and got["D"]["hi"] == 60
    assert got["dflt"]["g"] == got["check"]["g"] and got["dflt"]["disc"] == 10 and got["dflt"]["term"] == 2
    assert got["dflt"]["fy"] == sam["fy"] and got["dflt"]["ni0"] == sam["ni"][0] and got["dflt"]["fade"] is True    # 근거 수치 (시작 순이익 · 그 연도)
    assert got["mine"]["disc"] == 8 and got["mine"]["g"] != got["dflt"]["g"]
    assert got["us"] == {"why": "us"} and got["notReady"] == {"why": "notReady"} and got["noNi"] == {"why": "notReady"}
    assert got["loss"]["why"] == "loss"


def test_implied_growth_matches_what_the_old_app_shows():
    """리뷰: 예전 뱁새의 카드(기본값: 할인율 10% · 영구성장률 2% · 5년에 걸쳐 수렴)와 같은 값 — 삼성전자 41.6%, 현대차 '−30% 이하'."""
    got = run("""const f = (t) => K.impliedGrowth(RS[t], RC[t]);
      const o = (t) => T.oldRev({ price: RS[t].price, ni0: RC[t].ni[0], sharesM: RC[t].shm, fade: true, disc: 10, term: 2 });
      out = { sam: f('005930'), samOld: o('005930'), hd: f('005380'), hdOld: o('005380') };""", RS=REAL, RC=REAL_CO)
    assert got["sam"]["g"] == got["samOld"]["g"] and round(got["sam"]["g"], 1) == 41.6, got["sam"]
    assert got["hd"]["edge"] == got["hdOld"]["edge"] == "low", got["hd"]

def test_decomposition_matches_the_old_card():
    corp = fixture("corp.json")
    some = [c for c in corp["companies"] if c.get("r36") is not None][:60]
    got = run("""out = C.map((c) => [K.decompose(c), T.oldDecomp(c)]);""", C=some)
    seen = set()
    for new, old in got:
        if old is None:
            assert new.get("why") in ("missing", "loss") and "head" not in new
            continue
        assert abs(new["eF"] - old["eF"]) < 1e-12 and abs(new["mF"] - old["mF"]) < 1e-12 and new["priceRatio"] == old["priceRatio"]
        assert abs(new["priceRatio"] - new["eF"] * new["mF"]) < 1e-9                # 3년 주가 배율 = 이익 배율 × 눈높이 배율 (참인 곱셈)
        seen.add(new["head"])
    assert seen <= {"upE", "upM", "downE", "downM"} and len(seen) >= 2, seen
    sam = run("out = K.decompose(RC['005930']);", RC=REAL_CO)
    assert abs(sam["priceRatio"] - 3.2) < 1e-12 and round(sam["eF"], 2) == 9.73 and round(sam["mF"], 2) == 0.33 and sam["fyThen"] == 2023
    assert abs(sam["perNow"] - 219500 / 25780) < 1e-9 and abs(sam["priceThen"] * 3.2 - 219500) < 1e-6    # 상자 밑 근거 수치


def test_decomposition_says_missing_and_loss_apart():
    got = run("""const b = { r36: 20, shm: 100, eps: 1000, ni: [3, 2, 1000], price: 10000, fy: 2025 };
      out = { ok: K.decompose(b), noR36: K.decompose({ ...b, r36: null }), noEps: K.decompose({ ...b, eps: null }), short: K.decompose({ ...b, ni: [1, 2] }),
        noThen: K.decompose({ ...b, ni: [1, 2, null] }), lossNow: K.decompose({ ...b, eps: -5 }), lossThen: K.decompose({ ...b, ni: [1, 2, -3] }),
        noShm: K.decompose({ ...b, shm: null }), none: K.decompose(null) };""")
    assert got["ok"]["head"] in ("upE", "upM")
    for k in ("noR36", "noEps", "short", "noThen", "noShm", "none"):
        assert got[k] == {"why": "missing"}, k                            # 자료가 없을 뿐: '적자인 해가 있어서'가 아니에요
    assert got["lossNow"] == {"why": "loss"} and got["lossThen"] == {"why": "loss"}



# ── 근거 수치 · 띠 · 지도 ──
def test_receipts_only_when_they_give_the_shown_number():
    got = run("out = [K.receipt(219500, 99090, 2.22, 2), K.receipt(219500, 99090, 2.30, 2), K.receipt(219500, 25780, 8.5, 1), K.receipt(0, 1, 1, 1), K.receipt(1, null, 1, 1)];")
    assert got[0] == {"price": 219500, "per": 99090, "value": 2.22} and got[1] is None and got[2]["value"] == 8.5 and got[3] is None and got[4] is None


def test_pbr_strip_and_roe_pbr_map():
    grp = [st(f"00000{i}", pbr=p, roe=r) for i, (p, r) in enumerate([(0.5, 2), (1.0, 5), (1.5, 8), (2.0, 11), (2.5, 14), (30.0, 15)])]
    line = [st(f"0000{i}0", pbr=1.0 + 0.1 * r, roe=r) for i, r in enumerate([2, 4, 6, 8, 10, 12])]        # PBR = 1 + 0.1 × ROE
    got = run("""out = { strip: K.pbrStrip(G[2], G), few: K.pbrStrip(G[0], G.slice(0, 4)), map: K.roePbrMap(G[2], G),
      above: K.roePbrMap({ t: 'X', roe: 7, pbr: 2.5 }, L), below: K.roePbrMap({ t: 'X', roe: 7, pbr: 1.0 }, L), near: K.roePbrMap({ t: 'X', roe: 7, pbr: 1.72 }, L),
      out: K.roePbrMap({ t: 'X', roe: 150, pbr: 45 }, L), self: K.roePbrMap({ ...L[2], pbr: 9 }, L.map((x, i) => (i === 2 ? { ...x, pbr: 9 } : x))),
      fewPeers: K.roePbrMap(L[0], L.slice(0, 5)) };""", G=grp, L=line)
    s = got["strip"]
    assert s["n"] == 6 and s["med"] == 1.75 and all(0 <= d["x"] <= 1 for d in s["dots"]) and sum(d["mine"] for d in s["dots"]) == 1
    assert any(d["over"] for d in s["dots"]) and got["few"] is None                         # 아주 큰 PBR 은 오른쪽 끝에
    assert got["map"]["n"] == 6 and got["map"]["pos"] in ("below", "near", "above")       # 다른 회사 5개 + 이 회사
    assert got["above"]["pos"] == "above" and got["below"]["pos"] == "below" and got["near"]["pos"] == "near"
    assert abs(got["above"]["b"] - 0.1) < 1e-9 and abs(got["above"]["a"] - 1.0) < 1e-9 and got["above"]["n"] == 7
    assert got["out"]["pos"] == "out"                                                     # 업종 ROE 범위 밖: 문장 없음 (선을 늘려 쓰지 않아요)
    assert abs(got["self"]["b"] - 0.1) < 1e-9 and got["self"]["pos"] == "above"            # 회사 자신은 선을 바꾸지 않아요
    assert got["fewPeers"] is None                                                        # 다른 회사 5개 미만


# ── 공시 ──
def test_disclosure_rows_for_one_company():
    disc = {"asOf": "2026-11-04", "insider": [
        {"rc": "1", "d": "20261001", "t": "005930", "nm": "가", "pos": "상무", "q": 100},
        {"rc": "2", "d": "20261103", "t": "005930", "nm": "나", "pos": "-", "q": -50},
        {"rc": "3", "d": "20261102", "t": "000660", "nm": "다", "pos": "상무", "q": 10},
        {"rc": "4", "d": "bad", "t": "005930", "nm": "라", "pos": "상무", "q": 10},
        {"rc": "5", "d": "20261002", "t": "005930", "nm": "마", "pos": "상무", "q": 0}],
        "nps": [{"d": "20261102", "t": "005930", "rt": 7.1, "chg": -0.3}]}
    got = run("""out = { kr: K.discFor(D, { t: '005930', cls: 'kr', price: 1000 }), us: K.discFor(D, { t: 'AAPL', cls: 'us', price: 1 }), none: K.discFor(null, { t: 'X', cls: 'kr' }),
      days: K.DISC_DAYS };""", D=disc)
    kr = got["kr"]
    assert [r["rc"] for r in kr["rows"]] == ["2", "1"] and kr["rows"][0]["date"] == "2026-11-03" and kr["rows"][0]["pos"] == ""
    assert kr["buys"] == {"n": 1, "won": 100000} and kr["sells"] == {"n": 1, "won": 50000}          # 주식 수 × 지금 주가
    assert kr["nps"] == {"rt": 7.1, "chg": -0.3, "date": "2026-11-02"} and kr["asOf"] == "2026-11-04"
    assert got["us"] is None and got["none"] is None
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert re.search(r"^DISC_DAYS = (\d+)$", src, re.M).group(1) == str(got["days"]) == "90"       # '최근 90일' 은 파이프라인과 같아요


def test_dart_link_only_for_an_exact_receipt_number():
    """공시 줄의 DART 링크 (Jack, 2026-11-05: 링크만): disc.json 의 접수번호(rcept_no, 숫자 14자리)가 정확할 때만 그 공시의 원문 주소.
    파이프라인의 대신 열쇠('날짜|이름')나 다른 모양이면 링크가 없어요 (검색 · 이름으로 찾는 링크는 만들지 않아요)."""
    cases = ["20261029000101", "20261029|가나다", "2026102900010", "202610290001011", " 20261029000101", "20261029000101\n",
             "2026102900010a", "", None, 20261029000101]
    got = run("out = C.map((rc) => R.dartFilingUrl(rc)).concat([R.dartFilingUrl(undefined), R.DART_VIEWER]);", C=cases)
    assert got[0] == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000101"
    assert got[1:-1] == [None] * len(cases)
    assert got[-1] == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
    # 파이프라인이 접수번호를 받지 못한 보고서에 쓰는 대신 열쇠는 결코 14자리 숫자가 아니에요 (그래서 그 줄에는 링크가 없어요)
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert 'key = r.get("rcept_no") or ((r.get("rcept_dt") or "") + "|" + (r.get("repror") or ""))' in src
    # 화면의 줄은 disc.json 의 rc 를 그대로 가지고 있어요 (링크는 그 값으로만)
    rows = run("out = K.discFor(D, { t: '005930', cls: 'kr', price: 1000 }).rows.map((r) => [r.rc, R.dartFilingUrl(r.rc)]);",
               D=fixture("disc.json"))
    want = sorted((x for x in fixture("disc.json")["insider"] if x["t"] == "005930"), key=lambda x: x["d"], reverse=True)
    assert rows == [[x["rc"], "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + x["rc"]] for x in want] and len(rows) >= 1


def test_disclosure_date_is_the_newest_filing_and_goes_stale():
    got = run("""const N = Date.parse('2026-11-04T12:00:00+09:00');
      out = { ok: K.discDate({ asOf: '2026-11-04', newest: '2026-11-03', listOk: true, publishedAt: '2026-11-04T07:30:00+09:00' }, N),
        failed: K.discDate({ asOf: '2026-11-04', newest: '2026-10-28', listOk: false, publishedAt: '2026-11-04T07:30:00+09:00' }, N),
        failedToday: K.discDate({ asOf: '2026-11-04', newest: '2026-11-04', listOk: false, publishedAt: '2026-11-04T07:30:00+09:00' }, N),
        old: K.discDate({ asOf: '2026-10-25', newest: '2026-10-24', listOk: true, publishedAt: '2026-10-25T07:30:00+09:00' }, N),
        noPub: K.discDate({ asOf: '2026-11-04', newest: '2026-11-03', listOk: true }, N) };""")
    assert got["ok"] == {"date": "2026-11-03", "stale": False, "days": 0, "listOk": True}             # 실행일(asOf) 말고 가장 최근 공시일
    assert got["failed"] == {"date": "2026-10-28", "stale": True, "days": 7, "listOk": False}         # 오늘 목록을 못 받음 → 멈춤 표시, 오늘 날짜 아님
    assert got["failedToday"]["stale"] and got["failedToday"]["days"] == 1
    assert got["old"]["stale"] and got["old"]["days"] == 10 and got["old"]["date"] == "2026-10-24"      # 발행이 멈춤 (4일 넘게)
    assert got["noPub"]["stale"]


def test_signed_numbers_never_show_minus_zero():
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    tmp = tempfile.mkdtemp()
    entry = os.path.join(tmp, "f.js")
    with open(entry, "w", encoding="utf-8") as f:
        f.write(f"export {{ signedPct }} from {json.dumps(os.path.join(ROOT, 'src/v2/deckcalc.js'))};\n"
                f"export {{ pctText, yieldText }} from {json.dumps(os.path.join(ROOT, 'src/v2/cofmt.js'))};\n")
    r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8", f"--outfile={tmp}/f.mjs",
                        "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    code = ("import { signedPct, pctText, yieldText } from './f.mjs';"
            "console.log(JSON.stringify([signedPct(-0.04), signedPct(0.04), signedPct(-3.21), signedPct(3.2), pctText(-0.04), pctText(-1), pctText(2.25),"
            " yieldText(0.02), yieldText(0.19), yieldText(1.48), yieldText(0)]));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=tmp, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["0.0%", "0.0%", "\u22123.2%", "+3.2%", "0.0%", "\u22121.0%", "2.3%", "0.02%", "0.2%", "1.5%", "0.0%"], r.stdout


def test_holdings_of_a_stock_across_portfolios():
    ev = {"ok": True, "decks": [{"ok": True, "id": "a", "holdings": [{"t": "005930", "w": 0.2}]}, {"ok": True, "id": "b", "holdings": [{"t": "000660"}]},
                                {"ok": False, "id": "c"}]}
    decks = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    got = run("out = [K.holdingsOf(EV, DK, '005930'), K.holdingsOf(EV, DK, 'AAPL'), K.holdingsOf({ ok: false }, DK, '005930')];", EV=ev, DK=decks)
    assert [(h["deckId"], h["name"], h["x"]["w"]) for h in got[0]] == [("a", "A", 0.2)] and got[1] == [] and got[2] == []


# ── 회사 표시 (Part G) ──
def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_mark_colours_are_fixed_readable_and_stable():
    got = run("""out = { colors: K.MARK_COLORS, a: K.markColor('005930'), b: K.markColor('005930'), spread: [...new Set(Array.from({ length: 400 }, (_, i) => K.markColor(String(100000 + i))))].length,
      letters: [K.markLetter('삼성전자', '005930'), K.markLetter('apple Inc.', 'AAPL'), K.markLetter('', 'AAPL'), K.markLetter('  NAVER', 'X')], tok: TOK.COLOR };""")
    cols = got["colors"]
    assert len(cols) == 10 and len(set(cols)) == 10 and got["a"] == got["b"] and got["a"] in cols and got["spread"] == 10
    for c in cols:
        assert (1.05) / (lum(c) + 0.05) >= 4.5, c                                         # 흰 글자 4.5:1 이상
    banned = {got["tok"][k].upper() for k in ("apricot", "apricotText", "up", "down", "upOnPage", "watch", "heroAlert")}
    assert not (set(c.upper() for c in cols) & banned)
    assert got["letters"] == ["삼", "A", "A", "N"]


def test_logo_provider_is_off_and_makes_no_request():
    src = open(os.path.join(ROOT, "src", "v2", "logo.jsx"), encoding="utf-8").read()
    assert "export const LOGO_PROVIDER = null;" in src and "http" not in re.sub(r"//.*", "", src)
    assert "LOGO_TIMEOUT_MS = 3000" in src and "data-initial" in src and 'aria-hidden="true"' in src


# ── 기록: 내 메모 · 저장한 가정 ──
def test_notes_and_assumptions_round_trip_through_the_records():
    got = run("""const base = { v: 1, decks: [] };
      const a = S.withNote(base, '005930', '  장비 수주가 이어진다고 봤어요  ', '2026-11-04');
      const b = S.withAssume(a, 'AAPL', { disc: 9.5, term: 2 }, '2026-11-04');
      const cleared = S.withNote(b, '005930', '   ', '2026-11-05');
      const text = S.exportText(b);
      const back = S.parseImport(text, '2026-11-04');
      const merged = S.mergeStores({ v: 1, decks: [], notes: { '000660': { text: '하이닉스', at: '2026-11-01' } } }, back);
      out = { a, b, cleared, back, merged, note: S.noteOf(b, '005930'), assume: S.assumeOf(b, 'AAPL'),
        long: S.withNote(base, '005930', 'x'.repeat(501), '2026-11-04'), badCode: S.withNote(base, '<x>', 'a', '2026-11-04'),
        badAssume: [S.withAssume(base, 'A', { disc: 5, term: 2 }, '2026-11-04'), S.withAssume(base, 'A', { disc: 10.3, term: 2 }, '2026-11-04'),
          S.withAssume(base, 'A', { disc: 10, term: 4.5 }, '2026-11-04')],
        valid: S.validStore(b, '2026-11-04'), future: S.validStore(b, '2026-11-03'),
        bad: [S.validStore({ ...base, notes: [] }), S.validStore({ ...base, notes: { X: { text: '', at: '2026-11-01' } } }),
          S.validStore({ ...base, notes: { X: { text: 'a', at: 'soon' } } }), S.validStore({ ...base, assume: { X: { disc: 99, term: 1, at: '2026-11-01' } } }),
          S.validStore({ ...base, notes: { 'a b': { text: 'a', at: '2026-11-01' } } })],
        old: S.validStore(base), emptyStore: S.emptyStore() };""")
    assert got["a"]["notes"] == {"005930": {"text": "장비 수주가 이어진다고 봤어요", "at": "2026-11-04"}}
    assert got["b"]["assume"] == {"AAPL": {"disc": 9.5, "term": 2, "at": "2026-11-04"}} and got["b"]["notes"] == got["a"]["notes"]
    assert "notes" not in got["cleared"] and got["cleared"]["assume"] == got["b"]["assume"]                 # 빈 메모 = 지우기
    assert got["back"]["notes"] == got["a"]["notes"] and got["back"]["assume"] == got["b"]["assume"]         # 내보내기 · 불러오기에 함께
    assert set(got["merged"]["notes"]) == {"005930", "000660"}
    assert got["note"]["text"].startswith("장비") and got["assume"]["disc"] == 9.5
    assert got["long"] is None and got["badCode"] is None and got["badAssume"] == [None, None, None]
    assert got["valid"] and not got["future"] and not any(got["bad"]) and got["old"]
    assert got["emptyStore"] == {"v": 1, "decks": []}                                                        # 예전 기록과 같은 모양


# ── 주소 ──
def test_company_routes():
    H = ["#stocks/005930", "#stocks/005930/earn", "#stocks/005930/value", "#stocks/005930/div", "#stocks/005930/disc",
         "#stocks/005930/value-more", "#stocks/005930/earn-more", "#stocks/AAPL", "#stocks/BRK-B/value", "#stocks/x", "#stocks/005930/zzz",
         "#stocks/005930/value/1", "#stocks/%3Cscript%3E", "#stocks/", "#stocks/aapl", "#stocks/%E0%A4%A"]
    got = run("out = { p: Object.fromEntries(H.map((h) => [h, R.parseHash(h)])), sub: [R.companySub('005930'), R.companySub('BRK-B', 'value')], "
              "hash: R.hashOf('stocks', R.companySub('005930', 'div')) };", H=H)
    p = got["p"]
    assert p["#stocks/005930"] == {"tab": "stocks", "sub": "005930", "about": False, "known": True, "code": "005930", "ctab": None}
    for t in ("earn", "value", "div", "disc", "value-more", "earn-more"):
        assert p[f"#stocks/005930/{t}"] == {"tab": "stocks", "sub": f"005930/{t}", "about": False, "known": True, "code": "005930", "ctab": t}, t
    assert p["#stocks/AAPL"]["code"] == "AAPL" and p["#stocks/BRK-B/value"]["code"] == "BRK-B"
    for h in ("#stocks/x", "#stocks/005930/zzz", "#stocks/005930/value/1", "#stocks/%3Cscript%3E", "#stocks/", "#stocks/aapl", "#stocks/%E0%A4%A"):
        assert p[h] == {"tab": "home", "sub": None, "about": False, "known": False}, h        # 코드 모양이 아니면 #home
    assert got["sub"] == ["005930", "BRK-B/value"] and got["hash"] == "#stocks/005930/div"
