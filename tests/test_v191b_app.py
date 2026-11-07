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
    clash = dict(SAMSUNG, t="000070", dps3=[1500.0, 1446.0, 1444.0])                     # the record says another dps: na
    zero_dy = dict(SAMSUNG, t="000080", dy=0.0)                                         # a payer whose report says 0%: na
    paid0 = dict(zero, t="000090", dy=1.2)                                              # 0원 with a report yield: na
    steady = dict(SAMSUNG, t="000100", dps3a=[1450.0, 1446.0, 1500.0], dps3=[1450.0, 1446.0, 1500.0], dps=1450.0)
    cases = {"daehan": DAEHAN, "leeno": LEENO, "hanwha": HANWHA, "hivision": HIVISION, "samsung": SAMSUNG, "nd": nd, "zero": zero,
             "noprev": noprev, "noprevNoY": noprev_noy, "unverified": unverified, "clash": clash, "zeroDy": zero_dy, "paid0": paid0,
             "steady": steady}
    got = run(EXACT + """out = Object.fromEntries(Object.entries(CS).map(([k, s]) => [k, { d: K.divKr(s, null), pm: K.perMillionKr(s),
      y: E.krYieldToday(s), g: E.splitGuarded(s), card: E.cardRaw(s, E.CARDS.find((c) => c.id === 'div')),
      po: K.payout(s, { ni: [1e4, 9e3, 8e3], fy: 2025 }) }]));
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
    # 확인 못 한 수익률은 빈 칸: 주당 배당 ÷ 종가로 대신 채우지 않아요 (100만원어치 · 배당성향 · 순위도 없음)
    assert d["unverified"]["rule"] == "raised" and d["unverified"]["yieldPct"] is None
    assert got["unverified"]["y"] is None and got["unverified"]["pm"] is None and got["unverified"]["card"] is None and got["unverified"]["po"] is None
    for k in ("clash", "zeroDy", "paid0"):
        assert d[k]["rule"] == "na" and d[k]["yieldPct"] is None and d[k]["dps"] is None, k
    assert got["flip"] == ["streak", "streak"]                                          # 예전 스위치는 이 파일에 쓰이지 않아요
    assert got["daehan"]["po"] == {"pct": 400 * 1e6 / (1e4 * 1e8) * 100, "fy": 2025}       # 배당성향: 오늘 기준 주당 배당 × 오늘 주식 수


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
    assert got["hanwha"]["r"] == {"id": "divCut", "kind": "sell", "check": "pending"}     # 비교 불가: 준비 중
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
    got = run(EXACT + """
const est = (r) => E.estimate2022(r, RR);
out = { rows: est(ROWS), shaky: est(SHAKY), wide: D.y2022View(est(WIDE)), tiny: E.band2022(est(TINY)), tinier: D.y2022View(est(TINIER)),
  flat: D.y2022View(est(FLAT)), view: D.y2022View(est(ROWS)), vol: E.deckVol(SHAKY.map((r) => ({ ...r, s: { vol: 30, ...r.s } })), { mktVol: 30, usVol: 18, bdVol: 5, rhoKrUs: 0.3, rhoKrBd: 0.1, rhoUsBd: 0 }, 3e6) };
E.setDataShape({});
out.legacy = est(ROWS); out.legacyView = D.y2022View(out.legacy);""", RR=R, ROWS=rows, SHAKY=shaky, WIDE=wide, TINY=tiny, TINIER=tinier, FLAT=flat)
    r = got["rows"]
    assert r["ok"] and abs(r["won"] - (-300000 - 75000 - 10000)) < 1e-6
    small = -0.25 * 1.0 * 1e6 - 0.15 * 0.4 * 1e6 - 0.02 * 5e5
    big = -0.25 * 1.4 * 1e6 - 0.15 * 0.6 * 1e6 - 0.02 * 5e5
    assert abs(r["band"]["small"] - small) < 1e-6 and abs(r["band"]["big"] - big) < 1e-6 and r["band"]["base"] == 2500000
    # 믿을 수 없는 베타는 '자료 없음': 나머지처럼 움직인다고 보고(지금 규칙), 빠진 비중을 밝혀요
    s = got["shaky"]
    assert abs(s["missing"] - 0.5 / 3) < 1e-12 and abs(s["band"]["small"] - small / 2.5e6 * 3e6) < 1e-6
    assert abs(got["vol"]["missing"] - 0.5 / 3) < 1e-12                                     # 1년 출렁임도 그 베타를 쓰지 않아요
    assert got["view"]["text"] == "약 −32만원~−45만원" and got["view"]["parts"] == ["−32만원", "−45만원"]
    assert got["view"]["pct"] == [13, 18]                                                  # 320,000 / 2,500,000 = 12.8% → 13%
    assert got["wide"] == {"wide": True} and got["tinier"] == {"wide": True}
    assert got["tiny"]["pctSmall"] == 1
    assert got["flat"]["parts"] == ["−25만원"] and got["flat"]["text"] == "약 −25만원"   # 같은 금액이면 한 숫자
    assert "band" not in got["legacy"] and got["legacyView"] is None                         # 예전 파일: 한 숫자 그대로


def test_2022_copy_lines_are_the_approved_ones():
    got = run("out = [C.plan.y2022Wide, C.plan.y2022Range, C.co.risk.noBand === undefined];")
    assert got == ["오차가 너무 커서 추정하지 않았어요.", "범위는 베타를 계산할 때 생기는 오차를 반영했어요.", True]


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
