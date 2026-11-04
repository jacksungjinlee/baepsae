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
        "TOK": "src/ui/tokens.js"}


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
    base = {"t": "X", "cls": "kr", "price": 50000, "fy": 2025}
    cases = {"none": {"dps": 0, "dps3": [0, 100, 100]}, "na": {"dps": None}, "noPrev": {"dps": 1000, "dps3": [1000, None, 900]},
             "mismatch": {"dps": 1000, "dps3": [900, 800, 700]}, "cut": {"dps": 900, "dps3": [900, 1000, 1000]},
             "streak": {"dps": 1200, "dps3": [1200, 1100, 1000]}, "raised": {"dps": 1100, "dps3": [1100, 1000, 1000]},
             "steady": {"dps": 1020, "dps3": [1020, 1000, 1000]}, "same": {"dps": 1000, "dps3": [1000, 1000, 1000]},
             "cutThenRaise": {"dps": 1000, "dps3": [1000, 900, 1000]}, "tinyCut": {"dps": 999, "dps3": [999, 1000, 900]},
             "fromZero": {"dps": 100, "dps3": [100, 0, 0]}, "coOnly": {"dps": 1200}}
    got = run("""out = Object.fromEntries(Object.entries(C).map(([k, x]) => [k, K.divKr({ ...B, ...x }, k === 'coOnly' ? { dps3: [1200, 1100, 1000] } : null)]));""",
              B=base, C=cases)
    assert got["none"]["rule"] == "none" and got["none"]["yieldPct"] == 0
    assert got["na"]["rule"] == "na" and got["na"]["yieldPct"] is None
    assert got["noPrev"]["rule"] == "na" and abs(got["noPrev"]["yieldPct"] - 2.0) < 1e-9    # 비교할 해가 없으면 판단 안 함 (수익률은 그대로)
    assert got["mismatch"]["rule"] == "na"
    assert got["cut"]["rule"] == "cut" and got["tinyCut"]["rule"] == "cut"                  # 줄었으면 조금이라도 '줄였어요'
    assert got["streak"]["rule"] == "streak" and got["streak"]["n"] == 2 and got["coOnly"]["rule"] == "streak"
    assert got["raised"]["rule"] == "raised" and got["cutThenRaise"]["rule"] == "raised"    # 한 번 3% 넘게: '비슷하게'가 아니에요
    assert got["fromZero"]["rule"] == "raised"
    assert got["steady"]["rule"] == "steady" and got["same"]["rule"] == "steady"
    assert abs(got["streak"]["yieldPct"] - 1200 / 50000 * 100) < 1e-9                       # 최근 보고서의 주당 배당 ÷ 오늘 종가


def test_dividend_tile_rules_us_missing_is_not_no_dividend():
    got = run("out = [0, 0.32, null].map((dy) => K.divUs({ cls: 'us', dy })).concat([K.divUs({ cls: 'us' })]);")
    assert [g["rule"] for g in got] == ["none", "pays", "na", "na"] and got[1]["yieldPct"] == 0.32


def test_hundred_man_won_is_rounded_to_a_thousand_won():
    got = run("out = [2.4, 0.76, 0.32, 0, null, -1, 1.25].map((y) => K.perMillion(y));")
    assert got == [24000, 8000, 3000, 0, None, None, 13000]       # 12,500 → 13,000 (반올림)


def test_payout_needs_a_profit():
    got = run("out = [K.payout({ dps: 1668, eps: 25780 }), K.payout({ dps: 100, eps: 0 }), K.payout({ dps: 100, eps: -5 }), K.payout({ dps: null, eps: 10 })];")
    assert abs(got[0] - 1668 / 25780 * 100) < 1e-9 and got[1:] == [None, None, None]


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
      us: K.warnings({ t: 'AAPL', cls: 'us' }, { fl: { cr: 50 }, ni: [1, 2, 3], fy: 2025 }) };""", KR=kr)
    assert [f["code"] for f in got["flags"]["flags"]] == ["cr", "icr", "l3", "imp"] and got["flags"]["ran"]
    assert got["flags"]["quarter"] == {"y": 2026, "q": 2} and got["flags"]["fy"] == 2025
    assert got["clean"]["ran"] and got["clean"]["flags"] == []
    for k in ("noNi", "noFy", "noCo", "us"):
        assert not got[k]["ran"] and got[k]["flags"] == [], k


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


def test_implied_growth_uses_a_constant_rate_and_the_old_defaults():
    corp = fixture("corp.json")
    sam = next(c for c in corp["companies"] if c["t"] == "005930")
    got = run("""const s = { t: '005930', cls: 'kr', price: CO.price, cap: CO.cap };
      out = { dflt: K.impliedGrowth(s, CO), check: T.oldRev({ price: CO.price, ni0: CO.ni[0], sharesM: CO.shm, fade: false, disc: 10, term: 2 }),
        mine: K.impliedGrowth(s, CO, { disc: 8, term: 1 }), us: K.impliedGrowth({ ...s, cls: 'us' }, CO), notReady: K.impliedGrowth(s, { ...CO, dcfReady: false }),
        loss: K.impliedGrowth(s, { ...CO, ni: [-5, 1, 1] }), noNi: K.impliedGrowth(s, { ...CO, ni: [null, 1, 1] }), D: K.DCF };""", CO=sam)
    assert got["D"]["disc"] == 10 and got["D"]["term"] == 2 and got["D"]["lo"] == -30 and got["D"]["hi"] == 60
    assert got["dflt"]["g"] == got["check"]["g"] and got["dflt"]["disc"] == 10 and got["dflt"]["term"] == 2
    assert got["mine"]["disc"] == 8 and got["mine"]["g"] != got["dflt"]["g"]
    assert got["us"] == {"why": "us"} and got["notReady"] == {"why": "notReady"} and got["noNi"] == {"why": "notReady"}
    assert got["loss"] == {"why": "loss"}


def test_decomposition_matches_the_old_card():
    corp = fixture("corp.json")
    some = [c for c in corp["companies"] if c.get("r36") is not None][:60]
    got = run("""out = C.map((c) => [K.decompose(c), T.oldDecomp(c)]);""", C=some)
    seen = set()
    for new, old in got:
        if old is None:
            assert new is None
            continue
        assert abs(new["eF"] - old["eF"]) < 1e-12 and abs(new["mF"] - old["mF"]) < 1e-12 and new["priceRatio"] == old["priceRatio"]
        assert abs((1 + new["pricePct"] / 100) - (1 + new["epsPct"] / 100) * (1 + new["perPct"] / 100)) < 1e-9   # 3년 주가 = 이익 × 눈높이
        seen.add(new["head"])
    assert seen <= {"upE", "upM", "downE", "downM"} and len(seen) >= 2, seen


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
