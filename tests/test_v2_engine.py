# -*- coding: utf-8 -*-
"""뱁새 2.0 덱 엔진 (src/v2/engine.js, v18.3 Part B) — Node 로 직접 돌려봐요.

자료가 빈 종목은 빠지고 개수가 보여요 · 순위는 시장(한국·미국) 안에서만 · ETF·펀드·채권·우선주는 순위에 없어요 ·
깐깐함 기준선 · 비중 한도(한 종목 최대, 업종 1/3, 업종당 2개, 거래대금 한도, 미국 1주 단위) · 0.6~1.4배 기울기 ·
지킬 수 없는 설정은 막아요 · '업종 없음'은 한 업종으로 묶지 않아요 · 배당 감소는 확인 필요(규칙 깨짐 아님) ·
2022년 수치는 저장된 실제 종가로 다시 계산해도 같아요.
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
_BUNDLE = {}


def engine_path():
    if "p" not in _BUNDLE:
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "engine.mjs")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, "src/v2/engine.js", "--bundle", "--format=esm", "--platform=node", f"--outfile={out}",
                            "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _BUNDLE["p"] = tmp
    return _BUNDLE["p"]


def run(body, **data):
    """body 는 E(엔진)와 data 의 값(JSON)을 쓸 수 있어요. 마지막에 out 을 JSON 으로 돌려줘요."""
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = "import * as E from './engine.mjs';\n" + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=engine_path(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def kr(t, **kw):
    s = {"t": t, "nk": "K" + t, "cls": "kr", "price": 10000.0, "etf": False, "val20": 100.0, "vol": 30.0, "beta": 1.0,
         "vz": 50, "lz": 50, "mz": 50, "cap": 5.0, "roe": 10.0, "debt": 80.0, "g3": 5.0, "dps": 300.0, "opm": 8.0,
         "pbr": 1.0, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def us(t, **kw):
    s = {"t": t, "nk": "U " + t, "cls": "us", "price": 100.0, "etf": False, "val": 1000.0, "vol": 25.0, "beta": 1.0,
         "vz": 50, "lz": 50, "mz": 50, "cap": 50.0, "roe": 15.0, "debt": 60.0, "g3": 5.0, "dy": 2.0, "opm": 10.0,
         "pbr": 2.0, "ind": "machine", "indName": "기계"}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


SET = "const S = (o) => ({ ...E.defaultSettings(), ...o });\n"


# ── 대상: 회사 주식만 ──
def test_etfs_funds_bonds_metals_and_preferred_are_never_ranked():
    stocks = [kr("000010", roe=30), kr("005935", roe=99), kr("000020", etf=True, roe=99), kr("000030", fund=True, roe=99),
              {"t": "114260", "cls": "bond", "price": 60000, "etf": True, "roe": 99},
              {"t": "132030", "cls": "metal", "price": 20000, "fund": True, "etf": True},
              us("SPY", etf=True, roe=999), us("AAPL", roe=50)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'k55', points: { profit: 5 }, strict: 'loose' }));"
              "out = { kr: r.markets.kr.survivors.map(x => x.t), us: r.markets.us.survivors.map(x => x.t),"
              " pref: E.isPreferred({ t: '005935', cls: 'kr' }), common: E.isPreferred({ t: '005930', cls: 'kr' }),"
              " prefK: E.isPreferred({ t: '00680K', cls: 'kr' }), newCommon: E.isPreferred({ t: '0126Z0', cls: 'kr' }) };",
              stocks=stocks)
    assert got["kr"] == ["000010"] and got["us"] == ["AAPL"], got
    assert got["pref"] and got["prefK"] and not got["common"] and not got["newCommon"]


def _us_commons(n):
    return [us(f"C{i:03d}", dy=1.0 + i / 100) for i in range(n)]


def test_us_preferred_and_depositary_shares_without_a_market_cap_are_never_ranked():
    # 2026-11-02 실제 데이터: STRC(변동금리 우선주, 소프트웨어 · 배당 12%)·GOOGM·GOOGN(예탁증서)은 거래대금은 있는데
    # 야후에 시가총액이 없어요 (744종목 중 3개). 정보를 아예 못 받은 종목(NOINFO: 거래대금도 없음)은 그대로 빈 칸으로 세요.
    stocks = _us_commons(100) + [us("STRC", cap=None, dy=12.1, ind="software", indName="소프트웨어"),
                                 us("GOOGM", cap=None, dy=3.0), us("ZERO", cap=0, dy=5.0),
                                 us("NOINFO", cap=None, val=None, dy=9.0), kr("000010", cap=5.0)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'k55', points: { div: 5 }, strict: 'loose' }));"
              "const us = r.markets.us.survivors.map(x => x.t);"
              "out = { us, kr: r.markets.kr.survivors.map(x => x.t), blanks: r.blanks,"
              " uni: E.universe(stocks, 'us').map(s => s.t), out: [...E.usPreferredLike(stocks)].sort() };", stocks=stocks)
    assert got["out"] == ["GOOGM", "STRC", "ZERO"], got["out"]
    assert not {"STRC", "GOOGM", "ZERO", "NOINFO"} & set(got["us"]) and len(got["us"]) == 100, got["us"]
    assert "NOINFO" in got["uni"] and len(got["uni"]) == 101, got["uni"]
    assert got["blanks"] == 1 and got["kr"] == ["000010"], got


def test_many_us_stocks_without_a_market_cap_is_a_data_problem_not_preferred_shares():
    # 야후가 시가총액을 안 보내기 시작하면(데이터 문제) 미국 종목이 통째로 사라지면 안 돼요: 이 이유로는 아무것도 빼지 않아요
    stocks = _us_commons(100)
    for s in stocks[:40]:
        s.pop("cap")
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'us', points: { div: 5 }, strict: 'loose' }));"
              "out = { n: r.markets.us.survivors.length, out: E.usPreferredLike(stocks).size,"
              " uni: E.universe(stocks, 'us').length };", stocks=stocks)
    assert got == {"n": 100, "out": 0, "uni": 100}, got


# ── 빈 칸은 빠지고 개수가 보여요 ──
def test_blank_on_a_card_with_points_is_left_out_and_counted():
    stocks = [kr("000010"), kr("000020", roe=None), kr("000030", g3=None), kr("000040", val20=None)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'kr', points: { profit: 5 }, strict: 'loose' }));"
              "out = { surv: r.markets.kr.survivors.map(x => x.t).sort(), blanks: r.blanks };", stocks=stocks)
    # 000020: 수익성(ROE) 빈 칸 → 빠짐 · 000030: 성장은 점수가 없으니 상관없음 · 000040: 거래대금 모름 → 빠짐
    assert got == {"surv": ["000010", "000030"], "blanks": 2}, got


def test_financial_companies_skip_the_stability_card_not_blank():
    stocks = [kr("000010", ind="bank", indName="은행", debt=1200, roe=12), kr("000020", debt=50, roe=5),
              kr("000030", debt=None, roe=20)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'kr', points: { stable: 3, profit: 2 }, strict: 'loose' }));"
              "const b = r.markets.kr.survivors.find(x => x.t === '000010');"
              "out = { surv: r.markets.kr.survivors.map(x => x.t).sort(), blanks: r.blanks, bank: b && b.scores, total: b && b.total };",
              stocks=stocks)
    assert got["surv"] == ["000010", "000020"] and got["blanks"] == 1, got      # 000030 은 부채비율 빈 칸 → 빠짐
    assert got["bank"]["stable"] == "na" and got["total"] == got["bank"]["profit"]   # 은행 점수는 수익성 카드에서만


# ── 시장 안에서만 순위 ──
def test_ranking_is_within_each_market():
    stocks = [kr("000010", roe=5), kr("000020", roe=10), us("AAA", roe=100), us("BBB", roe=200)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'k55', points: { profit: 5 }, strict: 'loose' }));"
              "out = Object.fromEntries(Object.values(r.markets).flatMap(m => m.survivors).map(x => [x.t, x.total]));",
              stocks=stocks)
    # 미국 ROE 가 훨씬 커도 한국 1등은 한국 안에서 100점
    assert got == {"000020": 100, "000010": 50, "BBB": 100, "AAA": 50}, got


def test_kr_dividend_card_is_dps_over_price_and_zero_means_paid_nothing():
    stocks = [kr("000010", dps=500, price=10000), kr("000020", dps=0), kr("000030", dps=None), us("AAA", dy=3.0), us("BBB", dy=None)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'k55', points: { div: 5 }, strict: 'loose' }));"
              "out = { kr: r.markets.kr.survivors.map(x => [x.t, x.total]), us: r.markets.us.survivors.map(x => x.t), blanks: r.blanks,"
              " y: E.cardRaw(stocks[0], E.CARDS.find(c => c.id === 'div')) };", stocks=stocks)
    assert got["y"] == 5.0
    assert got["kr"] == [["000010", 100], ["000020", 50]] and got["us"] == ["AAA"] and got["blanks"] == 2, got


# ── 깐깐함 ──
def test_strictness_cut_offs_apply_to_every_card_with_points():
    stocks = [kr(f"{i:05d}0", roe=float(i), lz=i) for i in range(1, 21)]          # 20 종목, ROE 1..20
    got = run(SET + "out = {}; for (const k of ['loose', 'normal', 'strict', 'very']) {"
              " const r = E.screen(stocks, S({ mix: 'kr', points: { profit: 5 }, strict: k })); out[k] = r.survivors; }"
              "const r2 = E.screen(stocks.map((s, i) => ({ ...s, lz: 20 - i })), S({ mix: 'kr', points: { profit: 3, lowVol: 2 }, strict: 'normal' }));"
              "out.two = r2.survivors;", stocks=stocks)
    assert got["loose"] == 20 and got["normal"] == 10 and got["strict"] == 6 and got["very"] == 2, got
    assert got["two"] == 0      # 수익성 상위 50% 와 낮은 변동성 상위 50% 가 겹치지 않으면 0 (카드마다 기준선)


def test_no_cards_means_no_candidates_and_points_rules():
    got = run(SET + "const r = E.screen([], S({ points: {} }));"
              "out = { n: r.survivors, used: E.pointsUsed({ value: 5, divGrowth: 3, profit: 2 }),"
              " decks: E.DECKS.filter(d => !d.hidden).map(d => d.id), hidden: E.DECKS.filter(d => d.hidden).map(d => d.id),"
              " sums: E.DECKS.map(d => Object.values(d.points).reduce((a, b) => a + b, 0)) };")
    assert got["n"] == 0 and got["used"] == 7               # 준비 중 카드(배당 성장)는 점수에 안 들어가요
    assert set(got["hidden"]) == {"steadyDiv", "cheapQuality", "payout", "theme", "divGrowth"}
    assert set(got["decks"]) == {"deepValue", "garp", "quality", "strict", "lowVol", "trend", "krUs", "income"}
    assert all(s == 10 for s in got["sums"])


# ── 빼기 · 거래대금 바닥 ──
def test_exclusion_switches_and_liquidity_floor():
    stocks = [kr("000010", opm=-3), kr("000020", debt=250), kr("000030", debt=900, ind="bank", indName="은행"),
              kr("000040", dps=0), kr("000050", dps=None), kr("000060", ind="holding", indName="지주회사"),
              kr("000070", val20=4.9), kr("000080"), us("AAA", val=3), us("BBB", dy=0)]
    got = run(SET + "const r = E.screen(stocks, S({ mix: 'k55', points: { value: 5 }, strict: 'loose' }));"
              "const all = E.screen(stocks, S({ mix: 'k55', points: { value: 5 }, strict: 'loose',"
              " exclude: { loss: true, debt: true, noDiv: true, holding: true } }));"
              "out = { counts: r.excludeCounts, liqOut: r.liqOut, left: all.markets.kr.survivors.map(x => x.t).sort(),"
              " us: all.markets.us.survivors.map(x => x.t) };", stocks=stocks)
    assert got["counts"] == {"loss": 1, "debt": 1, "noDiv": 1, "holding": 1}, got   # 금융회사 부채비율 · 미국 무배당은 안 세요
    assert got["liqOut"] == 2                                                         # 4.9억원 · 미국 3억원
    assert got["left"] == ["000030", "000050", "000080"] and got["us"] == ["BBB"], got


def test_features_are_detected_from_the_data():
    d = {"stocks": [kr("000010"), kr("000020", dps=0)]}
    c = {"companies": [{"t": "000010", "fy": 2025}]}
    bare = {"stocks": [{k: v for k, v in kr("000010").items() if k not in ("ind", "indName", "val20", "etf")}]}
    got = run("out = { full: E.detectFeatures(d, c, { idxHist: {} }), bare: E.missingForBuild(E.detectFeatures(bare, { companies: [] }, null)) };",
              d=d, c=c, bare=bare)
    f = got["full"]
    assert f["etf"] and f["ind"] and f["val20"] and f["fy"] and f["dps0"] and f["idxHist"] and not f["d1"]
    assert got["bare"] == ["ind", "dps0", "val20", "fy", "etf"]


# ── 후보: 업종당 2개, '업종 없음'은 한 업종이 아니에요 ──
def test_preselect_takes_at_most_two_per_industry_and_ungrouped_are_not_one_group():
    stocks = [kr(f"0001{i}0", roe=50 - i, ind="semi", indName="반도체") for i in range(4)] + \
             [kr(f"0002{i}0", roe=40 - i, ind=None, indName=None) for i in range(4)]
    got = run(SET + "const st = S({ mix: 'kr', points: { profit: 5 }, strict: 'loose', count: 6 });"
              "const r = E.screen(stocks, st); const counts = E.splitCounts(st); const c = E.candidates(r, counts);"
              "const p = E.preselect(c, counts, []);"
              "const picked = p.map(t => stocks.find(s => s.t === t));"
              "out = { p, add: E.canAdd(stocks[2], picked, [], { kr: 7 }), addFree: E.canAdd(stocks[7], picked.slice(0, 5), [], { kr: 7 }),"
              " full: E.canAdd(stocks[7], picked, [], counts) };", stocks=stocks)
    assert got["p"] == ["000100", "000110", "000200", "000210", "000220", "000230"], got   # 반도체 2개 + 업종 없는 4개
    assert got["add"] == "industry" and got["addFree"] is None and got["full"] == "market"


def test_split_counts_follow_the_mix_within_the_max_per_stock():
    got = run(SET + "out = [S({ count: 6, mix: 'k73' }), S({ count: 5, mix: 'k73', maxPct: 25 }), S({ count: 10, mix: 'k55' }),"
              " S({ count: 6, mix: 'kr', pinned: ['a'] }), S({ count: 6, mix: 'us' })].map(E.splitCounts);")
    assert got == [{"kr": 4, "us": 2}, {"kr": 3, "us": 2}, {"kr": 5, "us": 5}, {"kr": 5, "us": 0}, {"kr": 0, "us": 6}], got


# ── 비중 ──
SIZE_JS = SET + """
const item = (s, total) => ({ t: s.t, s, total });
const sz = (stocks, o, amountMan = 1000, pinned = []) => E.size({ picks: stocks.map((s, i) => item(s, s.score || 80 - i)), pinned,
  cushion: [], settings: S({ mix: 'kr', ...o }), amountWon: amountMan * 10000 });
const W = (r) => r.ok ? Object.fromEntries(r.items.map(x => [x.t, x.w])) : r;
"""


def test_tilts_stay_within_06_to_14_of_equal_weight():
    stocks = [kr(f"0001{i}0", vol=v, ind=f"g{i}", indName=f"g{i}") for i, v in enumerate([10, 15, 30, 60, 90, 120])]
    for i, s in enumerate(stocks):
        s["score"] = [99, 20, 60, 50, 95, 1][i]
    got = run(SIZE_JS + "out = {}; for (const m of ['calm', 'even', 'conviction']) out[m] = W(sz(stocks, { method: m, maxPct: 25, count: 6 }));"
              "out.bt = E.boundedTilts([1, 1, 1, 100]); out.one = E.boundedTilts([5]);", stocks=stocks)
    e = 1 / 6
    for m in ("calm", "even", "conviction"):
        w = got[m]
        assert abs(sum(w.values()) - 1) < 1e-6, (m, w)
        assert all(0.6 * e - 1e-9 <= x <= 1.4 * e + 1e-9 for x in w.values()), (m, w)
    assert got["calm"]["000100"] > got["calm"]["000150"]               # 차분하게: 변동성 낮은 쪽에 더
    assert got["conviction"]["000100"] > got["conviction"]["000150"]   # 확신대로: 점수 높은 쪽에 더
    assert got["conviction"]["000100"] > got["conviction"]["000110"]
    assert all(0.6 - 1e-9 <= x <= 1.4 + 1e-9 for x in got["bt"]) and abs(sum(got["bt"]) / 4 - 1) < 1e-9 and got["one"] == [1]


def test_max_per_stock_holds_and_impossible_settings_block():
    stocks = [kr(f"0001{i}0", ind=f"g{i}", indName=f"g{i}") for i in range(6)]
    got = run(SIZE_JS + "const ok = sz(stocks, { maxPct: 20, count: 6, method: 'conviction' });"
              "const bad = sz(stocks.slice(0, 5), { maxPct: 10, count: 5 });"
              "const mix = E.size({ picks: stocks.map(s => item(s, 50)), cushion: [], settings: S({ mix: 'k73', count: 6 }), amountWon: 1e7 });"
              "out = { ok: W(ok), bad, mix };", stocks=stocks)
    assert all(x <= 0.2 + 1e-9 for x in got["ok"].values())
    assert got["bad"]["ok"] is False and [p["code"] for p in got["bad"]["clash"]][:2] == ["count", "max"]   # 5개 × 10% = 50%
    assert got["mix"]["ok"] is False and got["mix"]["clash"][0]["code"] == "mix"                          # 미국 30% 인데 미국 종목 없음


def test_industry_capped_at_one_third_including_across_markets():
    stocks = [kr("000010", ind="bank", indName="은행"), kr("000020", ind="bank", indName="은행"), kr("000030", ind="a", indName="a"),
              kr("000040", ind="b", indName="b"), kr("000050", ind="c", indName="c")]
    for s, sc in zip(stocks, [99, 98, 10, 10, 10]):
        s["score"] = sc
    got = run(SIZE_JS + "const r = sz(stocks, { maxPct: 25, count: 5, method: 'conviction' });"
              "out = { w: W(r), why: r.items.filter(x => x.t === '000010')[0].reasons.map(x => x.code) };", stocks=stocks)
    w = got["w"]
    assert w["000010"] + w["000020"] <= 1 / 3 + 1e-7 and abs(sum(w.values()) - 1) < 1e-6, w
    assert "indCap" in got["why"]


def test_missing_group_is_never_treated_as_one_group():
    plain = [kr(f"0001{i}0", ind=None, indName=None) for i in range(4)]
    grouped = [kr(f"0001{i}0", ind="same", indName="같은업종") for i in range(4)]
    got = run(SIZE_JS + "out = { plain: W(sz(plain, { maxPct: 25, count: 4 })), grouped: sz(grouped, { maxPct: 25, count: 4 }),"
              " counts: [...E.indCounts(plain).entries()] };", plain=plain, grouped=grouped)
    assert got["plain"] == {"000100": 0.25, "000110": 0.25, "000120": 0.25, "000130": 0.25}, got["plain"]
    assert got["grouped"]["ok"] is False and any(p["code"] in ("ind", "indCount") for p in got["grouped"]["clash"])   # 한 업종 4개 · 100% 는 안 돼요
    assert got["counts"] == []


def test_liquidity_cap_limits_a_position():
    stocks = [kr("000010", val20=5.0, ind="a", indName="a")] + [kr(f"0002{i}0", ind=f"b{i}", indName="b") for i in range(5)]
    # 1억원 투자, 하루 거래대금 5억원의 10% = 5천만원 → 50% 까지는 괜찮아요 / 10억원이면 5% 로 묶여요
    got = run(SIZE_JS + "const small = sz(stocks, { maxPct: 25, count: 6 }, 10000); const big = sz(stocks, { maxPct: 25, count: 6 }, 100000);"
              "out = { small: W(small)['000010'], big: W(big)['000010'], why: big.items.find(x => x.t === '000010').reasons.map(x => x.code),"
              " sum: Object.values(W(big)).reduce((a, b) => a + b, 0) };", stocks=stocks)
    assert got["small"] > 0.1 and abs(got["big"] - 0.05) < 1e-9 and "liqCap" in got["why"] and abs(got["sum"] - 1) < 1e-6, got


def test_whole_shares_us_at_fx_and_never_over_budget():
    stocks = [kr("000010", price=73000.0, ind="a", indName="a"), us("AAPL", price=344.63, ind="b", indName="b"),
              us("MSFT", price=520.11, ind="c", indName="c"), kr("000020", price=1234.0, ind="d", indName="d"),
              kr("000030", price=550000.0, ind="e", indName="e")]
    got = run(SIZE_JS + "const r = E.size({ picks: stocks.map((s, i) => item(s, 80 - i)), cushion: [], settings: S({ mix: 'k55', count: 5, maxPct: 25 }), amountWon: 5e6 });"
              "const p = E.planShares(r.items, 5e6, 1338);"
              "out = { ok: r.ok, rows: p.rows.map(x => [x.t, x.shares, x.cost, x.px]), spent: p.spent, left: p.left };", stocks=stocks)
    assert got["ok"]
    for t, sh, cost, px in got["rows"]:
        assert sh == int(sh) and sh >= 0 and abs(cost - sh * px) < 1e-6
    by = {t: px for t, _, _, px in got["rows"]}
    assert abs(by["AAPL"] - 344.63 * 1338) < 1e-6
    assert got["spent"] <= 5e6 and abs(got["spent"] + got["left"] - 5e6) < 1e-6


def test_pinned_stocks_bypass_screening_but_stay_capped():
    stocks = [kr(f"0001{i}0", ind=f"g{i}", indName="g") for i in range(4)]
    pref = kr("005935", ind="g9", indName="g", val20=3.0)     # 우선주, 거래대금 바닥 아래여도 꼭 담을 수 있어요
    got = run(SIZE_JS + "const r = sz(stocks, { maxPct: 25, count: 5 }, 100000, [pref]);"
              "out = { w: W(r), why: r.items.find(x => x.t === '005935').reasons.map(x => x.code) };", stocks=stocks, pref=pref)
    w = got["w"]
    assert abs(w["005935"] - 0.03) < 1e-9 and "pinned" in got["why"] and "liqCap" in got["why"], got   # 10% × 3억원 / 10억원
    assert abs(sum(w.values()) - 1) < 1e-6 and all(x <= 0.25 + 1e-9 for x in w.values())


# ── 배당 · 2022 ──
def test_dividends_unknown_counts_as_zero_with_a_count():
    rows = [{"s": kr("000010", dps=500), "shares": 10, "cost": 100000}, {"s": kr("000020", dps=0), "shares": 3, "cost": 30000},
            {"s": kr("000030", dps=None), "shares": 2, "cost": 20000}, {"s": us("AAA", dy=2.0), "shares": 1, "cost": 133800},
            {"s": us("BBB", dy=None), "shares": 1, "cost": 100000}, {"s": kr("000040", dps=None), "shares": 0, "cost": 0}]
    got = run("out = E.annualDividend(rows, 1338);", rows=rows)
    assert got == {"won": 5000 + 2676, "unknown": 2}, got


def test_2022_figures_recompute_from_closes():
    tmp = tempfile.mkdtemp()
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    out = os.path.join(tmp, "y.mjs")
    r = subprocess.run([exe, "src/v2/y2022.js", "--bundle", "--format=esm", "--platform=node", f"--outfile={out}", "--log-level=warning"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([NODE, "--input-type=module", "-e", "import * as Y from './y.mjs'; console.log(JSON.stringify(Y));"],
                       cwd=tmp, capture_output=True, text=True)
    y = json.loads(r.stdout)
    src, R = y["Y2022_SOURCES"], y["R2022"]
    ret = lambda k: src[k]["to"][1] / src[k]["from"][1] - 1
    assert abs(R["kr"] - ret("kospi")) < 1e-12 and abs(R["usWon"] - ((1 + ret("sp500")) * (1 + ret("usdkrw")) - 1)) < 1e-12
    # 저장된 종가가 공개된 2022년 수익률과 맞아요 (소수 둘째 자리 %)
    expect = {"kospi": -24.89, "sp500": -19.44, "usdkrw": 5.91, "114260": -2.46, "132030": -1.65}
    for k, v in expect.items():
        assert round(ret(k) * 100, 2) == v, (k, ret(k))
    assert round(R["usWon"] * 100, 2) == -14.68 and round(R["kr"] * 100, 2) == -24.89
    for t in ("114260", "132030"):
        assert abs(R["etf"][t] - ret(t)) < 1e-12
    for k, v in src.items():   # 2021년 마지막 종가 → 2022년 마지막 종가, 출처 기호가 있어요
        assert v["from"][0].startswith("2021-12-") and v["to"][0].startswith("2022-12-") and v["symbol"], (k, v)
    code = open(os.path.join(ROOT, "src", "v2", "engine.js"), encoding="utf-8").read()
    assert all(f'"{t}"' in code for t in ("114260", "132030")), "안전자산 ETF 와 2022 수치가 같은 종목이어야 해요"


def test_2022_estimate_is_market_times_beta_and_partial_or_none_without_beta():
    rows = [{"s": kr("000010", beta=1.2), "shares": 1, "cost": 1000000}, {"s": us("AAA", beta=0.5), "shares": 1, "cost": 1000000},
            {"s": {"t": "114260", "cls": "bond", "etf": True}, "shares": 1, "cost": 500000}]
    nob = rows + [{"s": kr("000020", beta=None), "shares": 1, "cost": 500000}]
    none = [{"s": kr("000020", beta=None), "shares": 3, "cost": 300000}, {"s": {"t": "999999", "cls": "bond", "etf": True}, "shares": 1, "cost": 10}]
    got = run("const R = { kr: -0.25, usWon: -0.15, etf: { '114260': -0.02 } };"
              "out = [E.estimate2022(rows, R), E.estimate2022(nob, R), E.estimate2022(none, R),"
              " E.deckVol(nob.map(r => ({ ...r, s: { vol: 30, ...r.s } })), { mktVol: 30, usVol: 18, bdVol: 5, mtVol: 20, rhoKrUs: 0.3, rhoKrBd: 0.1, rhoUsBd: 0 }, 3e6),"
              " E.deckVol(none, {}, 3e5)];", rows=rows, nob=nob, none=none)
    assert abs(got[0]["won"] - (-300000 - 75000 - 10000)) < 1e-6 and got[0]["ok"] and got[0]["missing"] == 0
    # 베타 없는 50만원은 나머지처럼 움직인다고 봐요 (지금 앱 v17.5 와 같은 규칙): 손실률 × 전체, 빠진 비중 표시
    assert got[1]["ok"] and abs(got[1]["won"] - (-385000 / 2500000) * 3000000) < 1e-6 and abs(got[1]["missing"] - 0.5 / 3) < 1e-12
    assert got[2] == {"ok": False, "none": True}
    assert got[3]["vol"] > 0 and abs(got[3]["missing"] - 0.5 / 3) < 1e-12 and got[4] is None


# ── 주의할 점 · 규칙 ──
def test_dividend_drop_is_a_check_never_a_broken_rule():
    s = kr("005380", dps=10000, dps3=[10000, 12000, 11400], fy=2025)
    got = run("const ctx = E.cautionContext([]); out = { c: E.cautions(s, null, ctx), rules: E.ruleBook(s, null, {}, 0.1) };", s=s)
    assert {"code": "divDrop", "a": 12000, "b": 10000} in got["c"]["items"]      # 산 날에는 주의할 점(확인 필요)으로
    # 배당 삭감 규칙은 그대로 있어요: 기준은 산 때의 배당(주당 10,000원, 2025년 보고서). Part C 는 그보다 새 보고서만 비교해서
    # 이미 지난 감소로 '깨짐'이 되지 않고, 다음 감소는 잡아요.
    div = [r for r in got["rules"] if r["id"] == "divCut"]
    assert len(div) == 1 and div[0]["check"] == "checked" and div[0]["kind"] == "sell"
    assert div[0]["baseline"] == 10000 and div[0]["since"] == 2025 and div[0]["droppedBefore"] is True
    blob = json.dumps(got, ensure_ascii=False)
    assert "broken" not in blob and "깨짐" not in blob


def test_cautions_debt_not_for_financials_and_pbr_needs_a_real_group():
    peers = [kr(f"0001{i}0", pbr=1.0 + i * 0.1, ind="auto", indName="자동차") for i in range(5)]
    hi = kr("000099", pbr=3.0, ind="auto", indName="자동차", debt=150)
    nog = kr("000098", pbr=9.0, ind=None, indName=None)
    bank = kr("000097", ind="bank", indName="은행", debt=1100)
    co = {"rev": [80.0, 90.0, 100.0], "dps3": [100, 100, 90]}
    got = run("const ctx = E.cautionContext([...peers, hi, nog, bank]);"
              "out = { hi: E.cautions(hi, co, ctx), nog: E.cautions(nog, null, ctx), bank: E.cautions(bank, null, ctx) };",
              peers=peers, hi=hi, nog=nog, bank=bank, co=co)
    codes = [c["code"] for c in got["hi"]["items"]]
    assert "pbrHigh" in codes and "debtHigh" in codes and "revFall" in codes, got["hi"]
    assert set(got["hi"]["ran"]) >= {"pbr", "debt", "rev", "div"}
    assert "pbr" not in got["nog"]["ran"]                       # 업종이 없으면 업종 대비 PBR 은 확인하지 않아요
    assert "debt" not in got["bank"]["ran"] and not any(c["code"] == "debtHigh" for c in got["bank"]["items"])


def test_rule_book_statuses_follow_the_part_c_table():
    s = kr("000010", debt=48, roe=12, dps=500, dps3=[500, 450, 400], fy=2025)
    co = {"op": [120.0, 100.0, 90.0], "fy": 2025}
    bank = kr("000020", ind="bank", indName="은행", debt=1100, roe=9, dps=None)
    ins = kr("000030", ind="insurance", indName="보험", dps=0)
    u = us("AAA", debt=60, roe=30)
    got = run("const p = { stable: 3, profit: 2 };"
              "out = { s: E.ruleBook(s, co, p, 0.12), bank: E.ruleBook(bank, null, p, 0.1), ins: E.ruleBook(ins, null, p, 0.1), u: E.ruleBook(u, null, p, 0.1) };",
              s=s, co=co, bank=bank, ins=ins, u=u)
    st = {r["id"]: r for r in got["s"]}
    assert st["divCut"]["check"] == "checked" and st["divCut"]["streak"] == 2 and st["divCut"]["fy"] == 2025
    assert st["divCut"]["dps"] == 500 and st["divCut"]["prev"] == 450        # 화면: 주당 450원 → 500원
    for k in ("audit", "embezzle", "acquisition"):
        assert st[k]["check"] == "pending"
    assert st["debtCeiling"]["check"] == "checked" and st["debtCeiling"]["limit"] == 100 and st["debtCeiling"]["fy"] == 2025
    assert st["roeFloor"]["check"] == "checked" and st["roeFloor"]["floor"] == 6
    assert st["opDecline"]["check"] == "checked"
    band = st["band"]
    assert band["check"] == "checked" and [round(x, 4) for x in band["bands"]] == [0.09, 0.15, 0.168]
    b = {r["id"]: r for r in got["bank"]}
    assert "debtCeiling" not in b and b["cet1"]["check"] == "pending" and b["divCut"]["check"] == "pending"   # 배당 모름 → 준비 중
    i = {r["id"]: r for r in got["ins"]}
    assert "divCut" not in i and i["kics"]["check"] == "pending"                                              # 무배당 → 삭감 규칙 없음
    uu = {r["id"]: r for r in got["u"]}
    assert uu["divCut"]["check"] == "pending" and "debtCeiling" not in uu     # 미국 부채비율은 다른 비율이라 규칙 없음
    for book in got.values():
        assert all(r["check"] in ("checked", "pending") for r in book)


def test_korean_annual_rules_need_the_report_year():
    s = kr("000010", debt=48, roe=12, dps=500, dps3=[500, 450, 400])     # fy 없음
    got = run("out = E.ruleBook(s, { op: [1, 2, 3] }, { stable: 3, profit: 2 }, 0.1);", s=s)
    by = {r["id"]: r for r in got}
    assert by["divCut"]["check"] == "pending" and by["debtCeiling"]["check"] == "pending"
    assert "roeFloor" not in by and "opDecline" not in by and by["band"]["check"] == "checked"


def test_survivor_warning_and_block_are_per_market_with_that_markets_count():
    stocks = [kr(f"0001{i}0", roe=10 + i) for i in range(9)] + [us("AAA"), us("BBB")]
    got = run(SET + "const st = S({ mix: 'k73', count: 6, points: { profit: 5 }, strict: 'loose' });"
              "const r = E.screen(stocks, st); const counts = E.splitCounts(st);"
              "const none = E.screen(stocks.slice(0, 9), st);"
              "out = { c: E.survivorCheck(r, counts), z: E.survivorCheck(none, counts), counts };", stocks=stocks)
    assert got["counts"] == {"kr": 4, "us": 2}
    assert got["c"]["markets"] == [{"mk": "us", "have": 2, "need": 2, "state": "few"}] and not got["c"]["zero"]   # 한국 9개는 넉넉해요
    assert got["z"]["zero"] and got["z"]["markets"][-1] == {"mk": "us", "have": 0, "need": 2, "state": "zero"}


def test_candidates_extend_when_one_industry_fills_the_top():
    stocks = [kr(f"0001{i}0", roe=90 - i, ind="semi", indName="반도체") for i in range(8)] + \
             [kr(f"0002{i}0", roe=50 - i, ind=f"o{i}", indName="기타") for i in range(4)]
    got = run(SET + "const st = S({ mix: 'kr', count: 5, points: { profit: 5 }, strict: 'loose' });"
              "const r = E.screen(stocks, st); const counts = E.splitCounts(st); const c = E.candidates(r, counts);"
              "out = { n: c.kr.length, picks: E.preselect(c, counts, []) };", stocks=stocks)
    # 위 10개 중 반도체가 8개라 2개만 고를 수 있어요 → 다른 업종이 더 붙어 5개를 고를 수 있어요
    assert got["n"] == 11 and len(got["picks"]) == 5, got


def test_financial_set_is_one_constant_including_the_fin_umbrella():
    """금융회사 = ind 가 정확히 {bank, insurance, securities, finance, fin} (fin = 묶음 그룹 '금융', 데이터 계약 v17.5.1)."""
    ids = ["bank", "insurance", "securities", "finance", "fin"]
    fins = [kr(f"0003{i}0", ind=g, indName="금융", debt=900, roe=10) for i, g in enumerate(ids)]
    plain = kr("000400", ind="holding", indName="지주회사", debt=900, roe=10)
    got = run(SET + "const r = E.screen([...fins, plain], S({ mix: 'kr', points: { stable: 3, profit: 2 }, strict: 'loose' }));"
              "const ctx = E.cautionContext([]);"
              "out = { set: E.FINANCIAL_INDS, isFin: [...fins, plain].map(E.isFin),"
              " na: r.markets.kr.survivors.filter(x => x.scores.stable === 'na').map(x => x.t).sort(),"
              " debtHit: [...fins, plain].map(s => E.exclusionsHit(s).includes('debt')),"
              " caution: [...fins, plain].map(s => E.cautions(s, null, ctx).ran.includes('debt')),"
              " ceiling: [...fins, plain].map(s => E.ruleBook({ ...s, fy: 2025 }, null, { stable: 3 }, 0.1).some(x => x.id === 'debtCeiling')) };",
              fins=fins, plain=plain)
    assert sorted(got["set"]) == sorted(ids)
    assert got["isFin"] == [True] * 5 + [False]
    assert got["na"] == sorted(s["t"] for s in fins)          # 재무 안정 카드는 '해당 없음' (빈 칸 아님)
    assert got["debtHit"] == [False] * 5 + [True]             # 부채비율 200%+ 빼기는 금융회사에 쓰지 않아요
    assert got["caution"] == [False] * 5 + [True]             # 주의할 점의 부채비율도
    assert got["ceiling"] == [False] * 5 + [True]             # 부채비율 상한 규칙도
    src = open(os.path.join(ROOT, "src", "v2", "engine.js"), encoding="utf-8").read()
    assert src.count('"securities"') == 1, "금융회사 목록은 FINANCIAL_INDS 한 곳에만 있어야 해요"



# ── 리뷰(14b9cee) 뒤 추가: 꼭 실패해야 하는 경우들 ──
def test_catch_all_group_ids_are_never_a_group():
    stocks = [kr(f"0005{i}0", ind=g, indName="기타") for i, g in enumerate(["etc", "other", "etc", "other"])]
    got = run(SET + "out = { has: stocks.map(E.hasGroup), counts: [...E.indCounts(stocks).entries()],"
              " size: E.size({ picks: stocks.map((s) => ({ t: s.t, s, total: 50 })), cushion: [], settings: S({ mix: 'kr', count: 4, maxPct: 25 }), amountWon: 1e7 }).ok,"
              " add: E.canAdd(stocks[3], stocks.slice(0, 3), [], { kr: 4 }) };", stocks=stocks)
    assert got == {"has": [False] * 4, "counts": [], "size": True, "add": None}, got


def test_three_pinned_stocks_in_one_group_are_refused():
    pins = [kr(f"0006{i}0", ind="semi", indName="반도체") for i in range(3)]
    others = [kr(f"0007{i}0", ind=f"g{i}", indName="g") for i in range(3)]
    got = run(SET + "out = { pin3: E.canPin(pins[2], pins.slice(0, 2)), pin2: E.canPin(pins[1], pins.slice(0, 1)),"
              " full: E.canPin(others[0], pins),"
              " size: E.size({ picks: others.map((s) => ({ t: s.t, s, total: 50 })), pinned: pins, cushion: [], settings: S({ mix: 'kr', count: 6, maxPct: 25 }), amountWon: 1e7 }) };",
              pins=pins, others=others)
    assert got["pin3"] == "industry" and got["pin2"] is None and got["full"] == "full"
    assert got["size"]["ok"] is False and got["size"]["clash"][0]["code"] == "indCount", got["size"]


def test_fewer_survivors_than_needed_blocks():
    stocks = [kr(f"0008{i}0", roe=10 + i, ind=f"g{i}", indName="g") for i in range(3)]
    got = run(SET + "const st = S({ mix: 'kr', count: 5, points: { profit: 5 }, strict: 'loose' });"
              "const r = E.screen(stocks, st); out = E.survivorCheck(r, E.splitCounts(st));", stocks=stocks)
    assert got["block"] and got["markets"] == [{"mk": "kr", "have": 3, "need": 5, "state": "short"}], got


def test_preselect_keeps_each_industry_under_a_third_at_the_korea_us_split():
    # 추세 추종 기본(6종목, 한국 7 : 미국 3): 같은 업종 2개는 비중을 1/3 에 맞춰 담을 수 있지만, 두 업종이 2개씩이면
    # 한국 70% 를 채울 수 없어요. 판단은 size() 로 해요 (매수 계획과 같은 계산).
    stocks = [kr("000100", roe=99, ind="semi", indName="반도체"), kr("000110", roe=98, ind="semi", indName="반도체"),
              kr("000120", roe=97, ind="machine", indName="기계"), kr("000130", roe=96, ind="machine", indName="기계")] + \
             [kr(f"0002{i}0", roe=50 - i, ind=f"o{i}", indName="기타업종") for i in range(6)] + \
             [us(f"U{c}", roe=80 - i, ind=f"u{i}", indName="미국업종") for i, c in enumerate("ABCDEF")]
    got = run(SET + "const st = S({ mix: 'k73', count: 6, points: { profit: 5 }, strict: 'loose' });"
              "const r = E.screen(stocks, st); const counts = E.splitCounts(st);"
              "const c = E.candidates(r, counts, [], st); const p = E.preselect(c, counts, [], st);"
              "const all = Object.values(c).flat(); const items = [...p].map((t) => all.find((x) => x.t === t));"
              "const sz = E.size({ picks: items, cushion: [], settings: st, amountWon: 1e7 });"
              "const byInd = {}; for (const x of items) byInd[x.s.ind] = (byInd[x.s.ind] || 0) + 1;"
              "const semis = sz.ok ? sz.items.filter((x) => x.s.ind === 'semi').reduce((a, x) => a + x.w, 0) : null;"
              "out = { n: p.length, short: p.short, byInd, ok: sz.ok, semis };", stocks=stocks)
    assert got["n"] == 6 and not got["short"] and got["ok"], got
    assert got["byInd"]["semi"] == 2 and got["byInd"]["machine"] == 1, got["byInd"]      # 반도체 2개는 담고, 기계 2번째는 안 돼요
    assert got["semis"] <= 1 / 3 + 1e-7


def test_second_stock_in_a_group_is_allowed_when_sizing_holds_it():
    # 리뷰 5번: 6종목 7:3 에서 같은 업종 한국 2개는 size() 가 1/3 안으로 맞춰요 (예전 '같은 비중' 계산은 막았어요)
    stocks = [kr("000100", ind="semi", indName="반도체"), kr("000110", ind="semi", indName="반도체"),
              kr("000120", ind="a", indName="가"), kr("000130", ind="b", indName="나"), us("UA", ind="u1", indName="u"), us("UB", ind="u2", indName="u")]
    got = run(SIZE_JS + "const st = S({ mix: 'k73', count: 6 }); const counts = E.splitCounts(st);"
              "const add = E.canAdd(stocks[1], [stocks[0], stocks[4]], [], counts, st);"
              "const r = E.size({ picks: stocks.map((s) => ({ t: s.t, s, total: 50 })), cushion: [], settings: st, amountWon: 1e7 });"
              "out = { add, ok: r.ok, w: Object.fromEntries(r.items.map((x) => [x.t, x.w])) };", stocks=stocks)
    assert got["add"] is None and got["ok"], got
    assert got["w"]["000100"] + got["w"]["000110"] <= 1 / 3 + 1e-7


def test_preselect_that_the_industry_limits_cannot_hold_is_blocked():
    stocks = [kr(f"0009{i}0", roe=90 - i, ind="semi", indName="반도체") for i in range(8)]
    got = run(SET + "const st = S({ mix: 'kr', count: 5, points: { profit: 5 }, strict: 'loose' });"
              "const r = E.screen(stocks, st); const counts = E.splitCounts(st);"
              "const c = E.candidates(r, counts, [], st); const p = E.preselect(c, counts, [], st);"
              "out = { n: p.length, short: p.short, blocked: p.blocked };", stocks=stocks)
    # 반도체 5종목 각 20%: 1/3 을 넘지 않게는 1개만 → 채울 수 없으니 막고, 이유(업종)를 알려요
    assert got["n"] == 1 and got["short"] and got["blocked"] and got["blocked"][0]["ind"] == "semi", got


def test_clash_names_every_group_held_at_a_third():
    stocks = [kr("000300", ind="a", indName="가업종"), kr("000310", ind="a", indName="가업종"),
              kr("000320", ind="b", indName="나업종"), kr("000330", ind="b", indName="나업종"), kr("000340", ind="c", indName="다업종")]
    got = run(SIZE_JS + "out = sz(stocks, { maxPct: 25, count: 5 });", stocks=stocks)
    assert got["ok"] is False
    named = sorted(p["indName"] for p in got["clash"] if p["code"] == "ind")
    assert named == ["가업종", "나업종"] and got["clash"][0]["code"] == "count", got


def test_us_debt_is_a_different_ratio_so_no_debt_rules_for_us():
    u = us("AAA", debt=400.0)
    k = kr("000400", debt=400.0, fy=2025)
    got = run("const ctx = E.cautionContext([]);"
              "out = { ex: [E.exclusionsHit(u), E.exclusionsHit(k)], ca: [E.cautions(u, null, ctx).items.map((x) => x.code), E.cautions(k, null, ctx).items.map((x) => x.code)],"
              " rule: [E.ruleBook(u, null, { stable: 3 }, 0.1).map((r) => r.id), E.ruleBook(k, null, { stable: 3 }, 0.1).map((r) => r.id)] };", u=u, k=k)
    assert got["ex"] == [[], ["debt"]] and got["ca"] == [[], ["debtHigh"]]
    assert "debtCeiling" not in got["rule"][0] and "debtCeiling" in got["rule"][1]


def test_fall_before_purchase_is_a_caution_and_the_rule_keeps_its_baseline():
    s = kr("005380", fy=2025, dps=10000, dps3=[10000, 9000, 8000])
    co = {"op": [115.0, 142.0, 151.0], "fy": 2025}                     # 현대차처럼 2년 연속 감소
    ok_co = {"op": [151.0, 142.0, 115.0], "fy": 2025}
    got = run("const ctx = E.cautionContext([]);"
              "out = { c: E.cautions(s, co, ctx).items, rules: E.ruleBook(s, co, {}, 0.1).map((r) => r.id), okRules: E.ruleBook(s, ok_co, {}, 0.1).map((r) => r.id) };",
              s=s, co=co, ok_co=ok_co)
    fall = [c for c in got["c"] if c["code"] == "opFall"]
    assert fall and round(fall[0]["pct"], 1) == -19.0                 # 산 날에 보여요 (주의할 점)
    assert "opDecline" in got["rules"] and "opDecline" in got["okRules"]   # 규칙은 남아요 (리뷰 2차 1번)



def test_operating_profit_fell_twice_has_one_definition_any_sign_counts():
    # 후보 고르기의 주의할 점 · 규칙의 fellBefore · 매일 점검(rules.js)이 모두 engine.fellTwice 하나를 써요.
    # 이익이 적자로 바뀌거나 적자가 깊어져도 '줄었다'로 세요. 작년이 적자면 '작년 대비 %'는 뜻이 없어서 빼요(pct = null).
    cases = {"profit falls": [80.0, 90.0, 100.0], "into a loss": [-20.0, 30.0, 100.0], "deeper loss": [-50.0, -10.0, 20.0],
             "rises": [100.0, 90.0, 80.0], "loss shrinks": [-10.0, -50.0, -80.0], "flat": [90.0, 90.0, 100.0], "blank": [80.0, None, 100.0]}
    s = kr("000100", fy=2025)
    got = run("const ctx = E.cautionContext([]);"
              "out = Object.fromEntries(Object.entries(CASES).map(([k, op]) => { const co = { op, fy: 2025 };"
              " const c = E.cautions(s, co, ctx).items.find((x) => x.code === 'opFall');"
              " return [k, [E.fellTwice(op), E.opFell2(co), c ? c.pct : 'none', E.ruleBook(s, co, {}, 0.1).find((r) => r.id === 'opDecline').fellBefore]]; }));",
              CASES=cases, s=s)
    assert got["profit falls"][:2] == [True, True] and round(got["profit falls"][2], 1) == -11.1 and got["profit falls"][3] is True
    assert got["into a loss"][:2] == [True, True] and round(got["into a loss"][2], 1) == -166.7 and got["into a loss"][3] is True
    assert got["deeper loss"] == [True, True, None, True], got["deeper loss"]      # 작년이 적자: 주의할 점은 뜨고, % 는 없음
    for k in ("rises", "loss shrinks", "flat", "blank"):
        assert got[k] == [False, False, "none", False], (k, got[k])

def test_rules_carry_their_purchase_baseline_and_are_not_broken_at_purchase():
    s = kr("005380", fy=2025, dps=10000, dps3=[10000, 12000, 11400], debt=150, roe=8.0)
    co = {"op": [115.0, 142.0, 151.0], "fy": 2025}
    got = run("out = E.ruleBook(s, co, { stable: 3, profit: 2 }, 0.1);", s=s, co=co)
    by = {r["id"]: r for r in got}
    for k, base in (("divCut", 10000), ("opDecline", 115.0), ("debtCeiling", 150), ("roeFloor", 8.0)):
        assert by[k]["check"] == "checked" and by[k]["baseline"] == base and by[k]["since"] == 2025, (k, by[k])
    assert by["opDecline"]["fellBefore"] is True and by["divCut"]["droppedBefore"] is True
    assert by["debtCeiling"]["limit"] > by["debtCeiling"]["debt"] and by["roeFloor"]["floor"] < by["roeFloor"]["roe"]
    assert all(r["check"] in ("checked", "pending") for r in got) and "broken" not in json.dumps(got)


def test_clash_without_max_when_only_the_industry_cap_holds_them():
    stocks = [kr("000500", ind="a", indName="가업종"), kr("000510", ind="a", indName="가업종"),
              kr("000520", ind="b", indName="나업종"), kr("000530", ind="b", indName="나업종")]
    got = run(SIZE_JS + "out = sz(stocks, { maxPct: 25, count: 4 });", stocks=stocks)
    codes = [p["code"] for p in got["clash"]]
    assert got["ok"] is False and "max" not in codes and codes.count("ind") == 2, got


def test_half_rule_like_the_current_app():
    """자료 없는 종목이 투자금의 절반을 '넘으면' 위험 수치를 내지 않아요. 딱 절반은 계산해요 (지금 앱의 경계 시험과 같게)."""
    def rows(missing_pct):
        return [{"s": kr("000600", beta=1.0, vol=30.0), "shares": 1, "cost": float(100 - missing_pct)},
                {"s": kr("000610", beta=None, vol=None), "shares": 1, "cost": float(missing_pct)}]
    exact = [{"s": kr("000620", beta=1.0, vol=30.0), "shares": 1, "cost": 300.0}, {"s": kr("000630", beta=None), "shares": 1, "cost": 100.0},
             {"s": kr("000640", beta=None), "shares": 1, "cost": 200.0}]
    st = {"mktVol": 30, "usVol": 18}
    got = run("const R = { kr: -0.25, usWon: -0.15, etf: {} };"
              "out = [49, 50, 51].map((m) => { const r = rows[m]; return { y: E.estimate2022(r, R), v: E.deckVol(r, st, 100) }; });"
              "out.push({ y: E.estimate2022(exact, R), v: E.deckVol(exact, st, 600) });",
              rows={49: rows(49), 50: rows(50), 51: rows(51)}, exact=exact, st=st)
    y49, y50, y51, yx = (g["y"] for g in got)
    assert y49["ok"] and abs(y49["missing"] - 0.49) < 1e-9
    assert y50["ok"] and abs(y50["missing"] - 0.5) < 1e-9
    assert y51 == {"ok": False, "half": True, "missing": y51["missing"]} and y51["missing"] > 0.5
    assert yx["ok"], "300 + 100 + 200 은 딱 절반이에요 (소수점 오차로 넘지 않아요)"
    assert got[2]["v"]["half"] and "vol" not in got[2]["v"] and got[1]["v"]["vol"] > 0


def test_industry_check_counts_the_safety_asset_share():
    # 리뷰 3차: 같은 업종 2 + 2, 안전자산 30% — 실제 sizing 은 업종당 1/3 아래로 담을 수 있는데 검사가 막았어요
    stocks = [kr("000010", ind="semi", indName="반도체"), kr("000020", ind="semi", indName="반도체"),
              kr("000030", ind="machinery", indName="기계"), kr("000040", ind="machinery", indName="기계")]
    # 6종목 7:3 (한국 4 · 미국 2 빈자리): 안전자산 30% 면 종목 몫은 70% → 업종당 약 23%, 안전자산 없으면 1/3 에 걸려요
    got = run(SET + "const st = S({ mix: 'k73', count: 6, maxPct: 25, cushion: 30, method: 'conviction' });"
              "const st0 = S({ mix: 'k73', count: 6, maxPct: 25, cushion: 0, method: 'conviction' });"
              "out = { with30: E.industryFits(stocks, [], { kr: 4, us: 2 }, st), with0: E.industryFits(stocks, [], { kr: 4, us: 2 }, st0) };",
              stocks=stocks)
    assert got == {"with30": True, "with0": False}, got
