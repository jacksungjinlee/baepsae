# -*- coding: utf-8 -*-
"""v19.1b 앱 (PR #50 의 데이터를 화면에 쓰기): 분할을 확인한 한국 배당 · 베타 오차 범위 · 재무 경고 — Node 로 직접 돌려봐요.

data.json 에 divCheck 가 있으면(engine.setDataShape) 그 파일은 새 칸을 가진 파일이에요:
- 한국 배당 추세는 dps3a(오늘 주식 수 기준)로 켜져요. divSt 가 nc(비교 불가) · nd(알 수 없음)인 종목은 추세도, 배당 감소도, 삭감 규칙
  점검도 없어요 (짐작하지 않아요). 1/3~3배 대조와 1.8배 분할 안전장치 대신 파이프라인이 확인한 dyt 를 써요 (빈 칸은 빈 칸).
- 배당 카드는 한국 종목을 dyt 로 줄 세우고, 빈 dyt 는 0 이 아니라 빈 칸이에요 (빠지고 세어요).
- 베타는 오차 범위(베타 ∓ 2 × betaSE, 0.1 단위)와 함께만. 양 끝이 같으면 한 숫자, betaSE 가 없거나 0.5 보다 크면 자료가 없어요.
- 2022년 수치는 범위 (작은 하락 먼저 · 작은 쪽이 하락이 아니면 '오차가 너무 커서 추정하지 않았어요.').
divCheck 가 없는 파일(v19.1b 전)은 지금과 똑같이 읽어요: 새 칸이 들어 있어도 쓰지 않아요.
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
_B = {}
MODS = {"E": "src/v2/engine.js", "K": "src/v2/company.js", "R": "src/v2/rules.js", "F": "src/v2/cofmt.js", "D": "src/v2/deckcalc.js",
        "L": "src/v2/load.js", "S": "src/v2/store.js", "CP": "src/copy/v2.js"}
EXACT = "E.setDataShape({ divCheck: { v: 1 } });\n"


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/b.mjs", "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = "import * as T from './b.mjs';\nconst { E, K, R, F, D, L, S, CP } = T;\nconst C = CP.C;\n" + decl + "let out;\n" + body \
        + "\nconsole.log(JSON.stringify(out));"
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def kr(t, **kw):
    s = {"t": t, "nk": "K" + t, "cls": "kr", "price": 10000.0, "etf": False, "val20": 100.0, "vol": 30.0, "beta": 1.0,
         "vz": 50, "lz": 50, "mz": 50, "cap": 5.0, "roe": 10.0, "debt": 80.0, "g3": 5.0, "opm": 8.0, "pbr": 1.0,
         "ind": "machine", "indName": "기계", "fy": 2025, "d1": 0.5, "shr": 1000000}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def us(t, **kw):
    s = {"t": t, "nk": "U " + t, "cls": "us", "price": 100.0, "etf": False, "val": 1000.0, "vol": 25.0, "beta": 1.0,
         "vz": 50, "lz": 50, "mz": 50, "cap": 50.0, "roe": 15.0, "debt": 60.0, "g3": 5.0, "dy": 2.0, "opm": 10.0, "pbr": 2.0,
         "ind": "machine", "indName": "기계", "d1": 0.2}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


# The real cases from PR #50's dry run (2026-11-06): data.json rows as published (the fields the app reads).
DAEHAN = kr("001130", nk="대한제분", price=10750.0, dps=4000.0, dy=2.6, dps3=[4000.0, 3500.0, 2500.0], dps3a=[400.0, 350.0, 250.0],
            dpsF=[10.0, 10.0, 10.0], divSt="adj", dyt=3.72, dz=82, beta=0.16, betaSE=0.0217, betaN=751)
LEENO = kr("058470", nk="리노공업", price=50300.0, dps=800.0, dy=1.31, dps3=[800.0, 3000.0, 3000.0], dps3a=[800.0, 600.0, 600.0],
           dpsF=[1.0, 5.0, 5.0], divSt="adj", dyt=1.59, dz=64, beta=0.89, betaSE=0.0511, betaN=751)
HANWHA = kr("012450", nk="한화에어로스페이스", price=680000.0, dps=7000.0, dy=0.7, dps3=[7000.0, 3500.0, 1800.0],
            dps3a=[7000.0, None, 1800.0], dpsF=[1.0, None, 1.0], divSt="nc", dyt=1.03, dz=60, beta=0.45, betaSE=0.0607, betaN=751)
HIVISION = kr("126700", nk="하이비젼시스템", price=9000.0, dps=80.0, dy=0.8, dps3=[80.0, 400.0, 500.0], dps3a=[80.0, 400.0, 500.0],
              dpsF=[1.0, 1.0, 1.0], divSt="same", dyt=0.89, beta=1.1, betaSE=0.08, betaN=751)
SAMSUNG = kr("005930", nk="삼성전자", price=201500.0, dps=1668.0, dy=1.5, dps3=[1668.0, 1446.0, 1444.0], dps3a=[1668.0, 1446.0, 1444.0],
             dpsF=[1.0, 1.0, 1.0], divSt="same", dyt=0.83, dz=58, beta=1.27, betaSE=0.0236, betaN=751)
AAPL = us("AAPL", nk="Apple Inc.", price=344.17, dy=0.34, beta=1.04, betaSE=0.0511, betaN=779)
NEW_FIELDS = ("dps3a", "dpsF", "divSt", "dyt", "dz", "betaSE", "betaN")


def strip(s):
    return {k: v for k, v in s.items() if k not in NEW_FIELDS}


# ── 파일 모양 ──
def test_the_data_shape_follows_divcheck_and_a_failed_load_resets_it():
    ok = {"pxDate": "2026-11-05", "publishedAt": "2026-11-06T07:00:00+09:00", "stocks": [SAMSUNG]}
    corp = {"pxDate": "2026-11-05", "publishedAt": "2026-11-06T07:00:00+09:00", "companies": []}
    got = run("""
const shapes = [{ divCheck: { v: 1, same: 1 } }, { divCheck: {} }, {}, null, { divCheck: [] }, { divCheck: 1 }, { divCheck: null }, [1]]
  .map((d) => E.setDataShape(d));
const load = (d) => L.resolveLoad({ data: { ok: true, data: d }, corp: { ok: true, data: CORP }, macro: { ok: false, error: 'x' } }, Date.parse('2026-11-06T08:00:00+09:00'));
const a = load({ ...OK, divCheck: { v: 1 } });
const exactAfter = E.exactData();
const b = load(OK);
const plainAfter = E.exactData();
load({ ...OK, divCheck: { v: 1 } });
L.resolveLoad({ data: { ok: false, error: '404' }, corp: { ok: true, data: CORP }, macro: { ok: false } }, 0);
out = { shapes, a: a.exact, exactAfter, b: b.exact, plainAfter, afterFail: E.exactData() };""", OK=ok, CORP=corp)
    assert got["shapes"] == [True, True, False, False, False, False, False, False]
    assert got["a"] is True and got["exactAfter"] is True and got["b"] is False and got["plainAfter"] is False
    assert got["afterFail"] is False                         # 불러오기에 실패하면 새 모양으로 읽지 않아요


def test_older_files_ignore_the_new_fields_and_behave_exactly_as_before():
    """divCheck 가 없는 파일: 새 칸이 종목에 붙어 있어도 결과가 새 칸이 없을 때와 한 글자도 같아요 (지금 사이트의 데이터)."""
    stocks = [DAEHAN, LEENO, HANWHA, HIVISION, SAMSUNG, AAPL]
    got = run("""
const ctx = E.cautionContext(ALL);
const rows = (xs) => xs.map((s) => ({ s, shares: 10, cost: (s.cls === 'us' ? s.price * 1400 : s.price) * 10 }));
const view = (xs) => ({
  div: xs.map((s) => (s.cls === 'us' ? K.divUs(s) : K.divKr(s, null))),
  y: xs.map((s) => [E.krYieldToday(s), E.krDivYield(s), E.splitGuarded(s), K.perMillionKr(s), K.payout(s, { ni: [100, 90, 80], fy: 2025 })]),
  card: xs.map((s) => E.cardRaw(s, E.CARDS.find((c) => c.id === 'div'))),
  risk: xs.map((s) => [K.riskTile(s), F.riskBandText(s, K.riskTile(s)), F.riskBandText(s, K.riskTile(s), true)]),
  caut: xs.map((s) => E.cautions(s, null, ctx)), book: xs.map((s) => E.ruleBook(s, null, { stable: 3 }, 0.1)),
  est: E.estimate2022(rows(xs)), vol: E.deckVol(rows(xs), { mktVol: 20, usVol: 18 }, 1e8), div$: E.annualDividend(rows(xs), 1400),
  y2022: D.y2022View(E.estimate2022(rows(xs))), guard: K.splitGuardCount(xs, new Map()), check: K.divCheckCount(xs, new Map()),
});
E.setDataShape({});
out = { withNew: view(ALL), without: view(BARE), exact: E.exactData() };""", ALL=stocks, BARE=[strip(s) for s in stocks])
    assert got["exact"] is False
    assert got["withNew"] == got["without"]
    w = got["withNew"]
    assert [d["rule"] for d in w["div"]] == ["pays", "pays", "pays", "pays", "pays", "pays"]   # 한국 배당 추세는 꺼져 있어요
    assert w["y"][0][0] is None and w["y"][0][2] is False                                       # 대한제분: 1/3~3배 대조에서 숨겨요
    assert all(r[1] is None and r[2] is None and "band" not in r[0] for r in w["risk"])          # 베타 숫자 없음
    assert "band" not in w["est"] and w["y2022"] is None                                       # 2022년은 한 숫자
    assert w["check"] is None and not any(x["code"] == "divDrop" for c in w["caut"] for x in c["items"])


# ── 한국 배당: 분할을 확인한 기록 ──
def test_exact_dividend_trend_from_dps3a_never_a_split_as_a_cut():
    nd = dict(SAMSUNG, t="000020", divSt="nd", dps3a=[1668.0, None, None], dpsF=[1.0, None, None], dyt=None)
    zero = kr("000030", dps=0.0, dy=None, dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], divSt="zero", dyt=0.0)
    noprev = dict(SAMSUNG, t="000040", dps3=[1668.0, None, 1444.0], dps3a=[1668.0, None, 1444.0])
    noprev_noy = dict(noprev, t="000050", dyt=None)
    unverified = dict(LEENO, t="000060", dyt=None)
    zero_dy = dict(SAMSUNG, t="000080", dy=0.0)                                         # 보고서 수익률 0%: 분할 확인(dyt)을 따라요
    paid0 = dict(zero, t="000090", dy=1.2)                                              # 0원인데 보고서 수익률 1.2%: 배당이 없어요
    uneven = dict(SAMSUNG, t="000110", divSt="adj", dps=333.0, dps3=[333.0, 1000.0, 900.0], dps3a=[333.0, 333.33, 300.0],
                  dpsF=[1.0, 3.0, 3.0], dyt=0.15)                                       # 3:1 분할: 원 단위로는 333 → 333원 (줄지 않았어요)
    steady = dict(SAMSUNG, t="000100", dps3a=[1450.0, 1446.0, 1500.0], dps3=[1450.0, 1446.0, 1500.0], dps=1450.0)
    cases = {"daehan": DAEHAN, "leeno": LEENO, "hanwha": HANWHA, "hivision": HIVISION, "samsung": SAMSUNG, "nd": nd, "zero": zero,
             "noprev": noprev, "noprevNoY": noprev_noy, "unverified": unverified, "zeroDy": zero_dy, "paid0": paid0,
             "steady": steady, "uneven": uneven}
    got = run(EXACT + """out = Object.fromEntries(Object.entries(CS).map(([k, s]) => [k, { d: K.divKr(s, null), pm: K.perMillionKr(s),
      y: E.krYieldToday(s), g: E.splitGuarded(s), card: E.cardRaw(s, E.CARDS.find((c) => c.id === 'div')),
      po: K.payout(s, { ni: [1e4, 9e3, 8e3], fy: 2025, cash3: [1500, 1400, 1300] }) }]));
    out.flip = [true, false].map((t) => K.divKr(DAEHAN, null, t).rule);""", CS=cases, DAEHAN=DAEHAN)
    d = {k: v["d"] for k, v in got.items() if k != "flip"}
    # 대한제분 10:1 분할 (보고서 뒤): 4,000 → 400원 기준으로 250 → 350 → 400, 2년 연속 늘렸어요 · 수익률 3.72% (보고서의 2.6% 아님)
    assert d["daehan"]["rule"] == "streak" and d["daehan"]["n"] == 2 and d["daehan"]["dps"] == 400 and d["daehan"]["d3"] == [400, 350, 250]
    assert d["daehan"]["yieldPct"] == 3.72 and got["daehan"]["pm"]["won"] == round(1e6 * 400 / 10750 / 1000) * 1000
    assert got["daehan"]["g"] is False and got["daehan"]["card"] == 3.72               # 분할 안전장치 없음 · 순위도 dyt
    # 리노공업 5:1 (2025년): 3,000원은 600원 기준 → 600 → 800, 작년보다 늘렸어요 (예전 기록 그대로면 '줄였어요')
    assert d["leeno"]["rule"] == "raised" and d["leeno"]["d3"] == [800, 600, 600] and d["leeno"]["dps"] == 800
    assert d["hivision"]["rule"] == "cut" and d["hivision"]["d3"] == [80, 400, 500]   # 진짜 삭감은 그대로 삭감
    assert d["samsung"]["rule"] == "streak" and d["samsung"]["dps"] == 1668
    assert d["steady"]["rule"] == "steady"
    # 비교 불가 · 알 수 없음: 추세 없이 '배당을 줘요' (수익률은 올해 기준을 확인했으면 보여요)
    assert d["hanwha"]["rule"] == "pays" and "d3" not in d["hanwha"] and d["hanwha"]["yieldPct"] == 1.03 and d["hanwha"]["dps"] == 7000
    assert d["nd"]["rule"] == "pays" and d["nd"]["yieldPct"] is None and got["nd"]["pm"] is None and got["nd"]["card"] is None
    assert d["zero"]["rule"] == "none" and d["zero"]["yieldPct"] == 0
    assert d["noprev"]["rule"] == "noPrev" and d["noprev"]["yieldPct"] == 0.83
    assert d["noprevNoY"]["rule"] == "na" and d["noprevNoY"]["dps"] is None
    # 확인 못 한 수익률은 빈 칸: 주당 배당 ÷ 종가로 대신 채우지 않아요 (주당 배당 · 100만원어치 · 순위도 없음). 추세는 기록이 비교 가능하면 그대로
    assert d["unverified"]["rule"] == "raised" and d["unverified"]["yieldPct"] is None and d["unverified"]["dps"] is None
    assert d["unverified"]["dpsOk"] is False
    assert got["unverified"]["y"] is None and got["unverified"]["pm"] is None and got["unverified"]["card"] is None
    # 보고서 수익률(dy)은 쓰지 않아요: 0% 라고 적힌 배당 종목도 분할 확인을 따르고, 0원 종목은 수익률이 적혀 있어도 배당이 없어요
    assert d["zeroDy"]["rule"] == "streak" and d["zeroDy"]["yieldPct"] == 0.83 and got["zeroDy"]["card"] == 0.83 and got["zeroDy"]["pm"]
    assert d["paid0"]["rule"] == "none" and d["paid0"]["yieldPct"] == 0 and got["paid0"]["card"] == 0 and got["paid0"]["pm"] is None
    assert got["paid0"]["po"] is None                                                   # 0원: 배당성향 없음
    # 고르지 않은 배율 뒤 소수점: 원 단위로 비교해요 (333.33 → 333 은 '줄였어요'가 아니에요)
    assert d["uneven"]["rule"] == "steady" and d["uneven"]["d3"] == [333, 333, 300], d["uneven"]
    assert got["flip"] == ["streak", "streak"]                                          # 예전 스위치는 이 파일에 쓰이지 않아요
    # 배당성향: 그 사업보고서의 현금배당금총액 ÷ 당기순이익 (주식 수 · 주당 배당 없이)
    assert got["daehan"]["po"] == {"pct": 1500 / 1e4 * 100, "fy": 2025} and got["hanwha"]["po"] == got["daehan"]["po"]


def test_exact_div_card_ranks_korea_on_dyt_and_a_blank_is_never_ranked():
    ks = [kr(f"0001{i}0", dps=100.0 * (i + 1), dps3=[100.0 * (i + 1)] * 3, dps3a=[100.0 * (i + 1)] * 3, divSt="same",
             dyt=(None if i in (2, 5) else float(i + 1))) for i in range(8)]
    ks.append(kr("000200", dps=0.0, dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], divSt="zero", dyt=0.0))
    ks.append(kr("000210", dps=50.0, dy=0.5))                                            # no split check at all: blank
    uss = [us(f"U{i}", dy=float(i)) for i in range(4)]
    got = run(EXACT + """
const st = { ...E.defaultSettings(), points: { div: 5 }, strict: 'loose', mix: 'k55', count: 6 };
const res = E.screen([...KS, ...US], st);
out = { kr: res.markets.kr.survivors.map((x) => x.t), krBlanks: res.markets.kr.blanks, us: res.markets.us.survivors.map((x) => x.t),
  ranks: K.cardRanks(KS[7], [...KS, ...US]).rows.find((r) => r.id === 'div'), blankRank: K.cardRanks(KS[2], [...KS, ...US]).rows.find((r) => r.id === 'div') };""",
              KS=ks, US=uss)
    assert got["kr"] == ["000170", "000160", "000140", "000130", "000110", "000100", "000200"], got["kr"]   # dyt 높은 순, 0% 는 맨 뒤
    assert got["krBlanks"] == 3                                                           # dyt 빈 칸 2 + 분할 확인 없는 종목 1
    assert got["us"] == ["U3", "U2", "U1", "U0"]                                          # 미국은 그대로 야후 수익률
    assert got["ranks"]["side"] == "top" and got["blankRank"] == {"id": "div", "blank": True}


def test_exact_cautions_and_the_rule_book_read_dps3a():
    got = run(EXACT + """
const ctx = E.cautionContext([]);
const one = (s, co = null) => ({ c: E.cautions(s, co, ctx), r: E.ruleBook(s, co, { stable: 3 }, 0.1).find((x) => x.id === 'divCut') });
out = { daehan: one(DAEHAN), leeno: one(LEENO), hanwha: one(HANWHA), hivision: one(HIVISION), samsung: one(SAMSUNG),
  coOnly: one({ ...LEENO, dps3a: undefined, divSt: undefined }, { dps3a: LEENO.dps3a, divSt: 'adj', fy: 2025 }),
  zero: one({ ...SAMSUNG, dps: 0, dps3a: [0, 0, 0], divSt: 'zero', dyt: 0 }), us: one(AAPL), off: [true, false].map((t) => E.cautions(LEENO, null, ctx, t)) };""",
              DAEHAN=DAEHAN, LEENO=LEENO, HANWHA=HANWHA, HIVISION=HIVISION, SAMSUNG=SAMSUNG, AAPL=AAPL)
    drop = lambda k: [x for x in got[k]["c"]["items"] if x["code"] == "divDrop"]
    # 리노공업: 예전 기록(3,000 → 800원)이면 '배당이 줄었어요'였어요. 오늘 기준(600 → 800원)은 늘었어요: 배당 감소 없음, 배당은 확인했어요
    assert drop("leeno") == [] and "div" in got["leeno"]["c"]["ran"] and drop("coOnly") == [] and "div" in got["coOnly"]["c"]["ran"]
    assert drop("hivision") == [{"code": "divDrop", "a": 400, "b": 80}]
    assert drop("hanwha") == [] and "div" not in got["hanwha"]["c"]["ran"]                # 비교 불가: 확인한 항목으로 말하지 않아요
    assert got["off"][0] == got["off"][1]                                                # 예전 스위치와 상관없어요
    r = got["leeno"]["r"]
    assert r["check"] == "checked" and r["baseline"] == 800 and r["prev"] == 600 and r["dps3"] == [800, 600, 600] and r["basis"] == "today"
    assert r["droppedBefore"] is False and r["since"] == 2025
    assert got["daehan"]["r"]["baseline"] == 400 and got["daehan"]["r"]["streak"] == 2
    assert got["hivision"]["r"]["check"] == "checked" and got["hivision"]["r"]["droppedBefore"] is True
    # 비교 불가: 규칙은 산 때의 보고서 연도와 함께 저장해요 (comparable: false → 매수 계획은 준비 중, 나중 파일이 비교할 수 있으면 점검)
    assert got["hanwha"]["r"] == {"id": "divCut", "kind": "sell", "check": "checked", "input": "dps", "baseline": 7000, "since": 2025,
                                  "dps": 7000, "prev": 3500, "fy": 2025, "basis": "report", "comparable": False}
    assert got["zero"].get("r") is None and got["us"]["r"]["check"] == "pending"


HELPERS = """
const ctxOf = (stocks, corps) => ({ state: { ok: true }, byT: new Map(stocks.map((s) => [s.t, s])), coByT: new Map((corps || []).map((c) => [c.t, c])),
  fx: 1400, pxDate: '2026-11-05' });
// two halves of about 100만원 each (so no weight band fires)
const deckOf = (buy, other, confirms) => ({ id: 'd1', name: 'deck', createdAt: '2026-10-01',
  holdings: [buy, other].map((s) => ({ t: s.t, nk: s.nk, cls: s.cls, kind: 'core', target: 0.5, rules: E.ruleBook(s, null, { stable: 3 }, 0.5) })),
  purchases: [buy, other].map((s) => ({ t: s.t, date: '2026-10-01', qty: Math.max(1, Math.round(1e6 / s.price)), price: s.price, ccy: 'KRW' })),
  ...(confirms ? { confirms } : {}) });
const div = (deck, stocks) => { const h = R.evaluateDeck(deck, ctxOf(stocks)).holdings[0];
  return { status: h.status, res: h.rules.find((r) => r.id === 'divCut'), drops: h.divDrops, codes: h.reasons.map((r) => r.code) }; };
"""


def test_exact_daily_check_on_dps3a_with_old_confirms_still_read():
    other = kr("000200", dps=0.0, dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], divSt="zero", dyt=0.0)
    # 2024 보고서로 샀어요 (since 2024). 오늘 2025 보고서
    leeno_buy = dict(LEENO, fy=2024, dps=3000.0, dps3=[3000.0, 3000.0, 2500.0], dps3a=[600.0, 600.0, 500.0], dpsF=[5.0, 5.0, 5.0])
    hv_buy = dict(HIVISION, fy=2024, dps=400.0, dps3=[400.0, 500.0, 450.0], dps3a=[400.0, 500.0, 450.0])
    nc_today = dict(HIVISION, divSt="nc", dps3a=[80.0, None, 500.0])
    old_cut = [{"t": "126700", "rule": "divCut", "fy": 2025, "a": 400.0, "b": 80.0, "answer": "cut", "at": "2026-11-02"}]
    old_not = [{"t": "126700", "rule": "divCut", "fy": 2025, "a": 400.0, "b": 80.0, "answer": "notCut", "at": "2026-11-02"}]
    raw_not = [{"t": "058470", "rule": "divCut", "fy": 2025, "a": 3000.0, "b": 800.0, "answer": "notCut", "at": "2026-11-02"}]
    got = run(EXACT + HELPERS + """
out = {
  leeno: div(deckOf(LB, O), [LEENO, O]),                       // 5:1 분할: 오늘 기준 600 → 800원, 줄지 않았어요
  leenoRaw: div(deckOf(LB, O, RAWNOT), [LEENO, O]),             // 예전 숫자(3,000 → 800원)에 '줄인 게 아니에요' 답이 있어도 그대로
  hv: div(deckOf(HB, O), [HIVISION, O]),                        // 진짜 삭감 400 → 80원: 확인 필요
  hvCut: div(deckOf(HB, O, CUT), [HIVISION, O]), hvNot: div(deckOf(HB, O, NOT), [HIVISION, O]),
  nc: div(deckOf(HB, O), [NC, O]), ncCut: div(deckOf(HB, O, CUT), [NC, O]),   // 오늘 비교 불가: 준비 중 · 답한 삭감은 그대로 규칙 깨짐
  gone: div(deckOf(HB, O), [O]),                                // 오늘 데이터에 없는 종목: 자료 없음 → 확인 필요
  plain: (() => { E.setDataShape({}); return div(deckOf(HB, O), [HIVISION, O]); })(),
};""", LB=leeno_buy, HB=hv_buy, O=other, LEENO=LEENO, HIVISION=HIVISION, NC=nc_today, CUT=old_cut, NOT=old_not, RAWNOT=raw_not)
    assert got["leeno"]["status"] == "none" and got["leeno"]["res"]["result"] == "ok" and got["leeno"]["drops"] == []
    assert got["leenoRaw"]["status"] == "none"
    assert got["hv"]["status"] == "check" and got["hv"]["res"]["result"] == "check" and got["hv"]["codes"] == ["divDrop"]
    assert [(x["fy"], x["a"], x["b"], x["answer"]) for x in got["hv"]["drops"]] == [(2025, 400, 80, None)]
    assert got["hvCut"]["status"] == "broken" and got["hvNot"]["status"] == "none"          # 같은 숫자의 예전 답은 그대로 읽혀요
    assert got["nc"]["res"]["result"] == "pending" and got["nc"]["status"] == "none" and got["nc"]["drops"] == []
    assert got["ncCut"]["status"] == "broken" and got["ncCut"]["res"]["result"] == "broken"
    assert got["gone"]["status"] == "check" and got["gone"]["res"]["result"] == "missing"
    assert got["plain"]["res"]["result"] == "pending"                                        # 예전 파일: 스위치가 꺼져 있어 준비 중


def test_exact_annual_dividend_uses_dps3a_and_names_what_it_leaves_out():
    nd = dict(SAMSUNG, t="000020", nk="알수없음", divSt="nd", dps3a=[None, None, None], dpsF=[None, None, None], dyt=None)
    zero = kr("000030", dps=0.0, dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], divSt="zero", dyt=0.0)
    nodps = kr("000040")
    rows = [{"s": DAEHAN, "shares": 10, "cost": 107500}, {"s": HANWHA, "shares": 2, "cost": 1360000}, {"s": nd, "shares": 3, "cost": 1},
            {"s": zero, "shares": 5, "cost": 1}, {"s": nodps, "shares": 1, "cost": 1}, {"s": AAPL, "shares": 1, "cost": 481838}]
    got = run(EXACT + "out = E.annualDividend(ROWS, 1400);", ROWS=rows)
    assert abs(got["won"] - (400 * 10 + 7000 * 2 + 0.0034 * 481838)) < 1e-6           # 대한제분은 400원 × 10주 (4,000원 아님)
    assert got["unchecked"] == [{"t": "000020", "nk": "알수없음"}] and got["unknown"] == 1


# ── 베타 오차 범위 (Part O.1) ──
def test_beta_band_text_rounding_minus_sign_equal_ends_and_unreliable():
    cases = {"samsung": SAMSUNG, "aapl": AAPL, "neg": kr("000010", beta=0.2, betaSE=0.2), "one": kr("000011", beta=1.0, betaSE=0.01),
             "zeroLo": kr("000012", beta=0.08, betaSE=0.06), "bothNeg": kr("000013", beta=-0.4, betaSE=0.05),
             "se05": kr("000014", beta=1.0, betaSE=0.5), "big": kr("000015", beta=1.0, betaSE=0.51), "noSe": kr("000016", beta=1.0),
             "noBeta": kr("000017", beta=None, betaSE=0.05), "negSe": kr("000018", beta=1.0, betaSE=-0.1), "usOne": us("U1", beta=1.0, betaSE=0.0)}
    body = """out = Object.fromEntries(Object.entries(CS).map(([k, s]) => { const r = K.riskTile(s);
  return [k, { r, tile: F.riskBandText(s, r), line: F.riskBandText(s, r, true), note: F.riskBandNote(r) }]; }));"""
    got = run(EXACT + body, CS=cases)
    legacy = run(body, CS=cases)
    band, one = C_RISK()
    assert got["samsung"]["tile"] == "코스피 1% → 평균 1.2~1.3%" and got["samsung"]["r"]["rule"] == "big"
    assert got["samsung"]["line"] == "코스피가 1% 움직일 때 평균 1.2~1.3% 움직였어요." and got["samsung"]["note"] == band
    assert got["aapl"]["tile"] == "S&P 500 1% → 평균 0.9~1.1%" and got["aapl"]["line"] == "S&P 500이 1% 움직일 때 평균 0.9~1.1% 움직였어요."
    assert got["neg"]["tile"] == "코스피 1% → 평균 −0.2~0.6%"                         # 빼기는 진짜 빼기 기호
    assert got["bothNeg"]["tile"] == "코스피 1% → 평균 −0.5~−0.3%"
    assert got["zeroLo"]["tile"] == "코스피 1% → 평균 0.0~0.2%"                          # −0.04 → 0.0 (−0.0 아님)
    assert got["one"]["tile"] == "코스피 1% → 평균 1.0%" and got["one"]["line"] == "코스피가 1% 움직일 때 평균 1.0% 움직였어요."
    assert got["one"]["note"] == one and got["usOne"]["tile"] == "S&P 500 1% → 평균 1.0%"
    assert got["se05"]["tile"] == "코스피 1% → 평균 0.0~2.0%"                               # 0.5 는 아직 믿어요 (0.5 보다 클 때만 자료 없음)
    for k in ("big", "noSe", "noBeta", "negSe"):
        assert got[k]["r"]["rule"] == "na" and got[k]["tile"] is None and got[k]["line"] is None and got[k]["note"] is None, k
    # 예전 파일: 문장만 (숫자 없음), betaSE 가 있어도
    for k, v in legacy.items():
        assert v["tile"] is None and v["line"] is None and "band" not in v["r"], k
    assert legacy["big"]["r"]["rule"] == "similar" and legacy["noBeta"]["r"]["rule"] == "na"


def C_RISK():
    got = run("out = [C.co.risk.bandNote, C.co.risk.oneNote];")
    assert got == ["과거 주가로 계산한 범위예요. 앞으로도 같다는 뜻은 아니에요.", "과거 주가로 계산한 값이에요. 앞으로도 같다는 뜻은 아니에요."]
    return got


# ── 2022년 범위 (Part O.1) ──
def test_2022_estimate_is_a_range_from_the_beta_band():
    R = {"kr": -0.25, "usWon": -0.15, "etf": {"114260": -0.02}}
    rows = [{"s": kr("000010", beta=1.2, betaSE=0.1), "shares": 1, "cost": 1000000},          # 1.0 ~ 1.4
            {"s": us("AAA", beta=0.5, betaSE=0.05), "shares": 1, "cost": 1000000},            # 0.4 ~ 0.6
            {"s": {"t": "114260", "cls": "bond", "etf": True}, "shares": 1, "cost": 500000}]   # 실제 2022년 결과, 범위 없음
    shaky = rows + [{"s": kr("000020", beta=1.0, betaSE=0.6), "shares": 1, "cost": 500000}]  # 베타를 믿을 수 없어요: 자료 없음
    wide = [{"s": kr("000030", beta=0.3, betaSE=0.2), "shares": 1, "cost": 1000000}]         # −0.1 ~ 0.7: 작은 쪽이 하락이 아니에요
    tiny = [{"s": kr("000040", beta=0.03, betaSE=0.001), "shares": 1, "cost": 1000000}]       # 0.7% 하락 → 반올림 1%
    tinier = [{"s": kr("000050", beta=0.01, betaSE=0.001), "shares": 1, "cost": 1000000}]     # 0.2% → 0%: 하락이 아니에요
    flat = [{"s": kr("000060", beta=1.0, betaSE=0.0), "shares": 1, "cost": 1000000}]          # 양 끝이 같아요
    rich = [{"s": kr("000070", beta=1.2, betaSE=0.1), "shares": 1, "cost": 4e8}]              # 4억원: 1억 넘는 하락도 만원으로
    small_amt = [{"s": kr("000080", beta=1.2, betaSE=0.1), "shares": 1, "cost": 30000}]       # 3만원: 7,500 ~ 10,500원 (1만원을 사이에 둬요)
    tiny_amt = [{"s": kr("000090", beta=1.2, betaSE=0.1), "shares": 1, "cost": 20000}]        # 2만원: 5,000 ~ 7,000원 (둘 다 1만원 밑)
    got = run(EXACT + """
const est = (r) => E.estimate2022(r, RR);
const both = (r) => [D.y2022View(est(r)), D.y2022View(est(r), true)];
out = { rows: est(ROWS), shaky: est(SHAKY), wide: D.y2022View(est(WIDE)), tiny: E.band2022(est(TINY)), tinier: D.y2022View(est(TINIER)),
  flat: both(FLAT), view: both(ROWS), rich: both(RICH), straddle: both(SMALL), under: both(UNDER), wideShort: D.y2022View(est(WIDE), true),
  vol: E.deckVol(SHAKY.map((r) => ({ ...r, s: { vol: 30, ...r.s } })), { mktVol: 30, usVol: 18, bdVol: 5, rhoKrUs: 0.3, rhoKrBd: 0.1, rhoUsBd: 0 }, 3e6) };
E.setDataShape({});
out.legacy = est(ROWS); out.legacyView = D.y2022View(out.legacy);""", RR=R, ROWS=rows, SHAKY=shaky, WIDE=wide, TINY=tiny, TINIER=tinier, FLAT=flat,
              RICH=rich, SMALL=small_amt, UNDER=tiny_amt)
    r = got["rows"]
    assert r["ok"] and abs(r["won"] - (-300000 - 75000 - 10000)) < 1e-6
    small = -0.25 * 1.0 * 1e6 - 0.15 * 0.4 * 1e6 - 0.02 * 5e5
    big = -0.25 * 1.4 * 1e6 - 0.15 * 0.6 * 1e6 - 0.02 * 5e5
    assert abs(r["band"]["small"] - small) < 1e-6 and abs(r["band"]["big"] - big) < 1e-6 and r["band"]["base"] == 2500000
    # 믿을 수 없는 베타는 '자료 없음': 나머지처럼 움직인다고 보고(지금 규칙), 빠진 비중을 밝혀요
    s = got["shaky"]
    assert abs(s["missing"] - 0.5 / 3) < 1e-12 and abs(s["band"]["small"] - small / 2.5e6 * 3e6) < 1e-6
    assert abs(got["vol"]["missing"] - 0.5 / 3) < 1e-12                                     # 1년 출렁임도 그 베타를 쓰지 않아요
    # Jack, PR #68: 빼기 없이 하락 폭으로, 작은 하락 먼저, 원으로만, '줄어들 수 있어요' · 4단계의 좁은 칸은 '약' 없이
    want = {"view": ("32~45만원", "약 32~45만원 줄어들 수 있어요", "32~45만원 줄어들 수 있어요"),
            "rich": ("10,000~14,000만원", "약 10,000~14,000만원 줄어들 수 있어요", "10,000~14,000만원 줄어들 수 있어요"),   # 1억 넘어도 만원
            "straddle": ("7,500원~1만원", "약 7,500원~1만원 줄어들 수 있어요", "7,500원~1만원 줄어들 수 있어요"),        # 두 끝 모두 앱의 원 표기
            "under": ("5,000~7,000원", "약 5,000~7,000원 줄어들 수 있어요", "5,000~7,000원 줄어들 수 있어요"),
            "flat": ("25만원", "약 25만원 줄어들 수 있어요", "25만원 줄어들 수 있어요")}                                # 같은 금액이면 한 숫자
    for k, (amount, plan, short) in want.items():
        v, w = got[k]
        assert (v["text"], w["text"]) == (plan, short), (k, v["text"], w["text"])
        assert v["pieces"] == ["약 ", amount, "줄어들 수 있어요"] and w["pieces"] == ["", amount, "줄어들 수 있어요"], (k, v["pieces"], w["pieces"])
        assert "\u2212" not in v["text"] + w["text"] and "-" not in v["text"] + w["text"] and "%" not in v["text"] + w["text"], k
    assert got["view"][0]["pct"] == [13, 18]                                               # 320,000 / 2,500,000 = 12.8% → 13% (화면에는 없어요)
    assert len(got["flat"][0]["parts"]) == 1 and len(got["view"][0]["parts"]) == 2
    assert got["wide"] == {"wide": True} and got["tinier"] == {"wide": True} and got["wideShort"] == {"wide": True}
    assert got["tiny"]["pctSmall"] == 1
    assert "band" not in got["legacy"] and got["legacyView"] is None                         # 예전 파일: 한 숫자 그대로


def test_2022_copy_lines_are_the_approved_ones():
    got = run("out = [C.plan.y2022Wide, C.plan.y2022Range, C.co.risk.noBand === undefined, C.plan.y2022MayRange, C.plan.y2022May,"
              " C.build.s4.y2022MayRange, C.build.s4.y2022May, C.plan.y2022NoteRange, C.plan.y2022Note, C.plan.y2022FallRange === undefined];")
    assert got == ["오차가 너무 커서 추정하지 않았어요.", "범위는 베타를 계산할 때 생기는 오차를 반영했어요.", True, "약 {small}~{big}만원 줄어들 수 있어요",
                   "약 {x} 줄어들 수 있어요", "{small}~{big}만원 줄어들 수 있어요", "{x} 줄어들 수 있어요",
                   "2022년 시장 하락 폭을 바탕으로 어림한 범위예요", "2022년 시장 하락 폭을 바탕으로 어림한 값이에요", True]
    build = open(os.path.join(ROOT, "src", "v2", "build.jsx"), encoding="utf-8").read()
    assert "view: y2022View(r.y2022, true)" in build                                        # 4단계는 '약' 없는 칸 문구


# ── 앞 막대를 다시 계산했을 때 (Jack, PR #68 2022/bars) ──
def test_the_bars_note_only_when_an_earlier_bar_was_recalculated():
    base = dict(SAMSUNG, t="000500", divSt="adj", dps=800.0, dps3=[800.0, 600.0, 500.0], dps3a=[800.0, 600.0, 500.0], dyt=0.4)
    cases = {"leeno": dict(base, dpsF=[1.0, 5.0, 5.0]), "one": dict(base, dpsF=[1.0, 1.0, 10.0]), "all": dict(base, dpsF=[10.0, 10.0, 10.0], dps=8000.0),
             "none": dict(base, divSt="same", dpsF=[1.0, 1.0, 1.0]), "gap": dict(base, dpsF=[1.0, 2.0, None], dps3a=[800.0, 600.0, None]),
             "nc": dict(base, divSt="nc", dpsF=[1.0, None, 5.0], dps3a=[800.0, None, 100.0])}
    got = run(EXACT + """out = Object.fromEntries(Object.entries(CS).map(([k, s]) => { const d = K.divKr(s, null);
  return [k, { rule: d.rule, years: d.adjYears ?? null, adjFrom: d.adjFrom ?? null }]; }));
out.note = C.co.div.barsAdjNote;
E.setDataShape({}); out.old = K.divKr(CS.leeno, null).adjYears ?? null;""", CS=cases)
    assert got["leeno"]["years"] == [2023, 2024] and got["leeno"]["adjFrom"] is None              # [1, 5, 5] → "2023·2024", 위 안내 없음
    assert got["one"]["years"] == [2023] and got["one"]["adjFrom"] is None                        # [1, 1, 10] → "2023"
    assert got["all"]["years"] == [2023, 2024] and got["all"]["adjFrom"] == 8000                  # [10, 10, 10] → 두 안내 모두
    assert got["none"]["years"] == [] and got["none"]["adjFrom"] is None                          # [1, 1, 1] → 없음
    assert got["gap"]["years"] == [2024]                                                         # 막대가 없는 해(2023)는 말하지 않아요
    assert got["nc"]["years"] is None and got["nc"]["rule"] == "pays"                            # 비교 불가: 막대도 안내도 없음
    assert got["old"] is None
    assert got["note"] == "주식 수가 달라지기 전인 {years}년 배당은 지금 1주 기준으로 다시 계산했어요."
    tabs = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    assert '<Note data-ui-v2="co-bars-adj">{fill(Dv.barsAdjNote, { years: adjYears.join("·") })}</Note>' in tabs


# ── 배당 감소 안내 (Jack, PR #68 B4) ──
def test_the_dividend_drop_hint_names_splits_only_for_older_files():
    got = run("""
E.setDataShape({ divCheck: { v: 1 } });
const exact = D.divDropBody();
E.setDataShape({});
out = { exact, old: D.divDropBody() };""")
    assert got["exact"] == "지난번 배당에 특별배당이 들어 있었는지 확인해 주세요."
    assert got["old"] == "특별배당이나 액면분할 때문인지 확인해 주세요."
    for f in ("src/v2/deckcalc.js", "src/v2/daily.jsx", "src/v2/plan.jsx"):                  # 세 화면 모두 같은 함수로
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        assert "divDropBody()" in src and "C.pick.caution.divDropBody}" not in src and "K.divDropBody]" not in src, f


# ── 재무 경고 '없어요' 밑 줄 (Jack, PR #68 B7) ──
def test_the_no_warning_sub_line_for_financial_and_holding_companies():
    """Jack, PR #68 B7 · B3/B7: 금융회사(s bank · insure · broker, 또는 업종 ind bank · insurance · securities · finance — 금융지주 포함)는
    금융회사 줄, 그 밖의 지주회사(s holding)는 지주회사 줄, 나머지는 지금 줄. 모두 flNa 가 정확히 cr + icr 이고 flRan 에 l3 + imp 가
    있을 때만이에요: 파이프라인이 지주회사의 두 확인을 돌리면(flNa 없음) 지주회사 줄은 저절로 사라져요."""
    rows = {"bank": {"s": "bank"}, "insure": {"s": "insure"}, "broker": {"s": "broker"}, "holding": {"s": "holding"}, "machine": {"s": "machine"},
            "bankOnlyImp": {"s": "bank", "flRan": ["imp"]}, "bankNa3": {"s": "bank", "flNa": ["cr", "icr", "l3"]}, "bankNoNa": {"s": "bank", "flNa": None},
            "stockSector": {"s": None, "stockS": "insure"},
            "kbHolding": {"s": "holding", "ind": "bank"}, "meritz": {"s": "holding", "ind": "insurance"}, "koreaInv": {"s": "holding", "ind": "securities"},
            "venture": {"s": "etc", "ind": "finance"}, "umbrella": {"s": "holding", "ind": "fin"},
            "holdingRanAll": {"s": "holding", "flRan": ["cr", "icr", "l3", "imp"], "flNa": None},
            "holdingOnlyL3": {"s": "holding", "flRan": ["l3"]}}
    got = run("""out = Object.fromEntries(Object.entries(ROWS).map(([k, r]) => {
  const co = { fy: 2025, flRan: r.flRan || ['l3', 'imp'], ...(r.flNa === null ? {} : { flNa: r.flNa || ['cr', 'icr'] }), ...(r.s ? { s: r.s } : {}) };
  const w = K.warnings({ t: 'X', cls: 'kr', ...(r.stockS ? { s: r.stockS } : {}), ...(r.ind ? { ind: r.ind } : {}) }, co);
  return [k, [w.allRan, w.sub]]; }));
out.line = C.co.warn.noneSubFin; out.hold = C.co.warn.noneSubHolding; out.old = C.co.warn.noneSub;""", ROWS=rows)
    assert got["bank"] == got["insure"] == got["broker"] == [True, "fin"]
    assert got["kbHolding"] == got["meritz"] == got["koreaInv"] == got["venture"] == [True, "fin"]   # 금융지주 · 캐피탈도 금융회사
    assert got["holding"] == [True, "holding"] and got["umbrella"] == [True, "holding"]          # 그 밖의 지주회사
    assert got["machine"] == [True, None]
    assert got["holdingRanAll"] == [True, None]                                                # 두 확인을 돌리면 지주회사 줄은 없어요
    assert got["holdingOnlyL3"] == [False, None]
    assert got["bankOnlyImp"] == [False, None] and got["bankNa3"][1] is None and got["bankNoNa"] == [False, None]
    assert got["stockSector"] == [True, "fin"]                                                # corp.json 에 s 가 없으면 data.json 의 s
    assert got["line"] == "금융회사라 유동비율과 이자보상배율은 보지 않고, 3년 연속 순손실과 자본잠식 신호만 확인해요."
    assert got["hold"] == "지주회사라 유동비율과 이자보상배율은 보지 않고, 3년 연속 순손실과 자본잠식 신호만 확인해요."
    assert got["old"] == "3년 연속 순손실, 빚 부담, 자본잠식 같은 신호를 최근 공시로 확인해요."
    src = open(os.path.join(ROOT, "src", "v2", "company.jsx"), encoding="utf-8").read()
    assert '(w.sub === "fin" && W.noneSubFin) || (w.sub === "holding" && W.noneSubHolding) || W.noneSub' in src


def test_the_partial_line_only_when_icr_alone_is_missing_for_want_of_an_interest_line():
    """Jack, PR #68 B7 (2026-11-07, option 1): 유동비율 · 3년 연속 순손실 · 자본잠식은 돌았고 이자보상배율만 못 돌렸는데 그 이유가
    재무제표에 이자비용 줄이 없어서(corp.json flWhy.icr 'ie')일 때만 '확인한 재무 경고 신호는 없어요' + 그 이유 줄. 업종과 상관없어요.
    이유가 다르거나(영업이익 없음 op · 음수 neg) 적혀 있지 않거나, 다른 확인도 빠졌거나, 경고가 하나라도 있으면 그 줄은 없어요."""
    rows = {
        "ie": {"flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "ie"}},
        "holdingIe": {"flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "ie"}, "s": "holding"},
        "op": {"flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "op"}},
        "neg": {"flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "neg"}},
        "noWhy": {"flRan": ["cr", "l3", "imp"]},
        "badWhy": {"flRan": ["cr", "l3", "imp"], "flWhy": "ie"},
        "noCr": {"flRan": ["l3", "imp"], "flWhy": {"icr": "ie"}},
        "all": {"flRan": ["cr", "icr", "l3", "imp"], "flWhy": {"icr": "ie"}},
        "na": {"flRan": ["l3", "imp"], "flNa": ["cr", "icr"], "flWhy": {"icr": "ie"}, "s": "bank"},
        "flag": {"flRan": ["cr", "l3", "imp"], "flWhy": {"icr": "ie"}, "fl": {"cr": 80}},
    }
    got = run("""out = Object.fromEntries(Object.entries(ROWS).map(([k, r]) => {
  const w = K.warnings({ t: 'X', cls: 'kr' }, { fy: 2025, ...r });
  return [k, [w.allRan, w.partial, w.flags.length]]; }));
out.head = C.co.warn.nonePartial; out.sub = C.co.warn.noneSubNoIcr;""", ROWS=rows)
    assert got["ie"] == [False, True, 0] and got["holdingIe"] == [False, True, 0]
    for k in ("op", "neg", "noWhy", "badWhy", "noCr"):
        assert got[k][1] is False, k
    assert got["all"] == [True, False, 0] and got["na"] == [True, False, 0]
    assert got["flag"] == [False, True, 1]                     # 경고가 있으면 화면은 경고 줄 (아래 확인 · '없어요' 아님)
    assert got["head"] == "확인한 재무 경고 신호는 없어요"
    assert got["sub"] == "이자보상배율은 공시에 이자 비용만 따로 나오지 않아 확인하지 못했어요. 나머지 세 가지는 최근 공시로 확인했어요."
    src = open(os.path.join(ROOT, "src", "v2", "company.jsx"), encoding="utf-8").read()
    assert "if (!w.flags.length) {" in src and "if (!w.allRan && !w.partial) return null;" in src
    assert src.index("if (!w.flags.length) {") < src.index("const head = w.partial ? W.nonePartial : W.none;")


# ── 분할 · 무상증자로 다시 계산한 주당 배당 (Jack, PR #68 B3) ──
def test_the_report_figure_note_only_under_a_recalculated_per_share_figure():
    leeno_now = LEENO                                                                     # dpsF [1, 5, 5]: 올해 숫자는 그대로 (앞 막대만 맞춤)
    nc_adj = dict(SAMSUNG, t="484870", divSt="nc", dps=2491.0, dps3=[2491.0, 1480.0, None], dps3a=[830.33, 493.33, None],
                  dpsF=[3.0, 3.0, None], dyt=6.9)                                         # 엠앤씨솔루션처럼: 비교 불가지만 올해 숫자는 맞춤
    unverified = dict(DAEHAN, t="000099", dyt=None)
    corp_only = dict(DAEHAN, t="000098", dpsF=None)
    got = run(EXACT + """
const f = (s, co = null) => { const d = K.divKr(s, co); return [d.rule, d.dps, d.adjFrom ?? null]; };
out = { daehan: f(DAEHAN), leeno: f(LEENO), samsung: f(SAMSUNG), nc: f(NC), unverified: f(UNV), corpOnly: f(CO1, { dpsF: [10, 10, 10], fy: 2025 }),
  note: C.co.div.adjNote };
E.setDataShape({});
out.old = f(DAEHAN);""", DAEHAN=DAEHAN, LEENO=leeno_now, SAMSUNG=SAMSUNG, NC=nc_adj, UNV=unverified, CO1=corp_only)
    assert got["daehan"] == ["streak", 400, 4000]                                          # 400원 밑에: 사업보고서에는 4,000원
    assert got["leeno"][2] is None and got["samsung"][2] is None                             # 올해 숫자가 그대로면 없어요
    assert got["nc"] == ["pays", 830.33, 2491]                                             # 비교 불가여도 보여 주는 숫자가 맞춘 값이면 있어요
    assert got["unverified"][2] is None and got["unverified"][1] is None                     # 숫자를 안 보이면 안내도 없어요
    assert got["corpOnly"][2] == 4000                                                      # corp.json 의 dpsF 로도
    assert got["old"][2] is None                                                           # 예전 파일: 없어요
    assert got["note"] == "주식 수가 달라진 만큼 지금 1주 기준으로 다시 계산한 금액이에요. 사업보고서에는 {x}원으로 나와요."
    tabs = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    assert 'showDps && r.adjFrom != null && Dv.adjNote && <Note data-ui-v2="co-dps-adj">{fill(Dv.adjNote, { x: nf(r.adjFrom) })}</Note>' in tabs


# ── 재무 경고: 확인이 모두 돌았거나 해당 없을 때만 '없어요' ──
def test_no_warning_claim_only_when_every_check_ran_or_does_not_apply():
    kr_ = {"t": "105560", "cls": "kr"}
    got = run("""out = [
  K.warnings(KR, { flRan: ['l3', 'imp'], flNa: ['cr', 'icr'], fy: 2025 }).allRan,                // 금융업: 둘은 돌고 둘은 해당 없음
  K.warnings(KR, { flRan: ['l3'], flNa: ['cr', 'icr'], fy: 2025 }).allRan,                       // 자본잠식 확인이 안 돌았어요
  K.warnings(KR, { flNa: ['cr', 'icr', 'l3', 'imp'], fy: 2025 }).allRan,                          // 돈 기록(flRan)이 없으면 말하지 않아요
  K.warnings(KR, { flRan: ['cr', 'icr', 'l3', 'imp'], fy: 2025 }).allRan,
  K.warnings(KR, { flRan: ['l3', 'imp'], fy: 2025 }).allRan,
  K.warnings(KR, { flRan: ['l3', 'imp', 'x'], flNa: ['cr', 'zz'], fy: 2025 }).allRan,
  K.warnings(KR, { flRan: 'l3', flNa: ['cr', 'icr'], fy: 2025 }).allRan];""", KR=kr_)
    assert got == [True, False, False, True, False, False, False]


# ── 하나의 규칙: 배당을 확인했는가 (리뷰 1) ──
def test_one_rule_for_a_checked_korean_dividend_across_every_reader():
    """보고서 수익률(dy)과 분할 확인(dyt)이 어긋나는 두 줄: 회사 페이지 · 배당 카드 · 후보 고르기 수익률 · 매수 계획 연 배당금 ·
    100만원어치 · 배당성향이 모두 같은 답이에요. 빈 칸은 0 으로 순위에 들거나 더해지지 않아요."""
    payer_dy0 = kr("028100", nk="동아지질", price=20000.0, dps=664.0, dy=0.0, dps3=[664.0, 600.0, 550.0], dps3a=[664.0, 600.0, 550.0],
                   dpsF=[1.0, 1.0, 1.0], divSt="same", dyt=3.32)
    zero_dy = kr("064820", nk="케이프", price=5000.0, dps=0.0, dy=6.6, dps3=[0.0, 300.0, 300.0], dps3a=[0.0, 300.0, 300.0],
                 dpsF=[None, 1.0, 1.0], divSt="same", dyt=0.0)
    blank = kr("000300", nk="빈칸", price=5000.0, dps=100.0, dy=2.0, dps3=[100.0, 100.0, 100.0], dps3a=[None, None, None],
               dpsF=[None, None, None], divSt="nd")
    corp = [{"t": t, "fy": 2025, "ni": [100.0, 90.0, 80.0], "cash3": [30.0, 28.0, 25.0]} for t in ("028100", "064820", "000300")]
    got = run(EXACT + """
const co = new Map(CO.map((c) => [c.t, c]));
const card = (s) => E.cardRaw(s, E.CARDS.find((c) => c.id === 'div'));
const one = (s) => { const d = K.divKr(s, co.get(s.t));
  return { rule: d.rule, y: d.yieldPct, dps: d.dps, card: card(s), today: E.krYieldToday(s), pm: K.perMillionKr(s, co.get(s.t)), po: K.payout(s, co.get(s.t)),
    plan: E.annualDividend([{ s, shares: 10, cost: s.price * 10 }], 1400, co) }; };
const st = { ...E.defaultSettings(), points: { div: 5 }, strict: 'loose', mix: 'kr', count: 6 };
const res = E.screen(STOCKS, st);
out = { payer: one(STOCKS[0]), zero: one(STOCKS[1]), blank: one(STOCKS[2]), ranked: res.markets.kr.survivors.map((x) => x.t), blanks: res.markets.kr.blanks };""",
              STOCKS=[payer_dy0, zero_dy, blank], CO=corp)
    p, z, b = got["payer"], got["zero"], got["blank"]
    # 보고서 수익률 0% 인 배당 종목: 페이지 수익률 = 카드 순위 = 후보 고르기 = 3.32% · 100만원어치 · 배당성향 · 연 배당금 모두 있어요
    assert p["rule"] == "streak" and p["y"] == p["card"] == p["today"] == 3.32 and p["dps"] == 664
    assert p["pm"]["won"] == round(1e6 * 664 / 20000 / 1000) * 1000 and p["po"]["pct"] == 30.0
    assert p["plan"] == {"won": 6640, "unknown": 0, "unchecked": []}
    # 0원인데 보고서 수익률 6.6%: 배당이 없어요 = 카드 0% = 연 배당금 0원 · 100만원어치 · 배당성향 없음 (페이지와 카드가 같은 답)
    assert z["rule"] == "none" and z["y"] == z["card"] == z["today"] == 0 and z["pm"] is None and z["po"] is None
    assert z["plan"] == {"won": 0, "unknown": 0, "unchecked": []}
    # 확인하지 못한 배당: 페이지 수익률 · 카드 · 100만원어치 모두 빈 칸, 연 배당금에서는 빼고 이름을 밝혀요 (0 으로 세지 않아요)
    assert b["rule"] == "pays" and b["y"] is None and b["card"] is None and b["today"] is None and b["pm"] is None and b["dps"] is None
    assert b["plan"] == {"won": 0, "unknown": 0, "unchecked": [{"t": "000300", "nk": "빈칸"}]}
    assert got["ranked"] == ["028100", "064820"] and got["blanks"] == 1


def test_a_rule_saved_while_not_comparable_is_checked_once_a_later_file_can_compare():
    """비교 불가(nc)일 때 산 종목: 규칙은 저장해요 (comparable: false, 산 때의 보고서 연도). 그날은 준비 중 · 기록이 비교 가능해진
    다음 보고서에서 줄었으면 확인 필요 · 저장한 기록은 store.validStore 로 그대로 읽혀요."""
    buy = dict(HANWHA, fy=2024, dps=3500.0, dps3=[3500.0, 1800.0, 1500.0], dps3a=[3500.0, None, 1500.0], dpsF=[1.0, None, 1.0], divSt="nc")
    later_cut = dict(HANWHA, fy=2026, dps=6000.0, dps3=[6000.0, 7000.0, 3500.0], dps3a=[6000.0, 7000.0, 3500.0], dpsF=[1.0, 1.0, 1.0],
                     divSt="same", dyt=0.88)
    later_nc = dict(later_cut, divSt="nc", dps3a=[6000.0, None, None])
    other = kr("000200", dps=0.0, dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], divSt="zero", dyt=0.0)
    got = run(EXACT + HELPERS + """
const deck = deckOf(BUY, O);
const rule = deck.holdings[0].rules.find((r) => r.id === 'divCut');
const store = { v: 1, decks: [deck] };
out = { rule, valid: S.validStore(store, '2026-11-07'), today: div(deck, [BUY, O]), cut: div(deck, [LATER, O]), nc: div(deck, [NC, O]),
  roundTrip: S.validStore(JSON.parse(JSON.stringify(store)), '2026-11-07') };""", BUY=buy, O=other, LATER=later_cut, NC=later_nc)
    assert got["rule"]["check"] == "checked" and got["rule"]["comparable"] is False and got["rule"]["since"] == 2024
    assert got["valid"] is True and got["roundTrip"] is True
    assert got["today"]["res"]["result"] == "pending" and got["today"]["status"] == "none"
    assert got["cut"]["res"]["result"] == "check" and [(x["fy"], x["a"], x["b"]) for x in got["cut"]["drops"]] == [(2026, 7000, 6000)]
    assert got["nc"]["res"]["result"] == "pending"


def test_daily_check_compares_whole_won_after_an_uneven_split():
    buy = dict(SAMSUNG, t="000110", fy=2024, divSt="adj", dps=1000.0, dps3=[1000.0, 900.0, 800.0], dps3a=[333.33, 300.0, 266.67],
               dpsF=[3.0, 3.0, 3.0], dyt=0.15)
    now = dict(buy, fy=2025, dps=333.0, dps3=[333.0, 1000.0, 900.0], dps3a=[333.0, 333.33, 300.0], dpsF=[1.0, 3.0, 3.0])
    other = kr("000200", dps=0.0, dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], divSt="zero", dyt=0.0)
    got = run(EXACT + HELPERS + """out = { d: div(deckOf(BUY, O), [NOW, O]), c: E.cautions(NOW, null, E.cautionContext([])) };""",
              BUY=buy, NOW=now, O=other)
    assert got["d"]["res"]["result"] == "ok" and got["d"]["drops"] == []
    assert not any(x["code"] == "divDrop" for x in got["c"]["items"]) and "div" in got["c"]["ran"]


def test_build_and_plan_wide_cells_and_no_partial_line_under_the_wide_line():
    src = open(os.path.join(ROOT, "src", "v2", "build.jsx"), encoding="utf-8").read()
    assert "wideOf(m) ? <span data-ui-v2=\"y2022-wide\">{C.plan.y2022Wide}</span>" in src      # 그 칸에만
    plan = open(os.path.join(ROOT, "src", "v2", "plan.jsx"), encoding="utf-8").read()
    assert "{!(yv && yv.wide) && partial(y2022.missing)}" in plan
