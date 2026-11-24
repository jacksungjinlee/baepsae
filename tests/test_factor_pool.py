# -*- coding: utf-8 -*-
"""2026-11-24 (11-24 발행본 점검): 팩터 점수는 시장마다 회사 주식끼리만 매겨요.

11-24 발행본 (pxDate · usPxDate 2026-11-23): 미국 ETF 33곳이 add_percentiles(us) 의 순위에 들어갔고, 그중 23곳은 야후의 priceToBook (펀드에는
뜻이 없어요: SOXX 0.37 · TLT 0.55 · XLY 0.72 · SPY 1.76 · 실제 SPY 의 P/B 는 약 5) 으로 가치 순위에 들어갔어요. 그래서 미국 회사 547곳의
가치 점수(vz)가 최대 3점 (평균 1.2) 틀어졌고 SOXX · TLT 가 가치 100점이었어요. 추세(mz) · 저변동(lz) 순위에도 ETF 33곳이 섞였고, 국내는 상장
인프라 펀드 3곳(088980 맥쿼리인프라 · 415640 KB발해인프라 · 094800 맵스리얼티, etf 참)이 규모 · 추세 · 저변동 순위에 섞였어요.

여기서 보는 것 (네트워크 없음 · 새 시험 파일 · 예전 시험은 그대로):
- fetch_data.add_percentiles: 두 시장 모두 펀드(etf 참 · fund — validate_data.factor_fund)는 여섯 점수(pz vz mz qz lz dz) 순위에서 빠지고 점수
  칸이 없어요 (미리 있던 칸도 지워요) · 회사 점수는 펀드가 없을 때와 같아요 · 펀드가 없는 목록은 예전 셈 그대로 (main 99b5f52 의 식)
- 11-24 발행본의 미국 행 (tests/fixtures/factor_pool_us_1124.json): 예전 식이 발행된 점수를 그대로 다시 만들고 (고정 자료가 진짜라는 확인),
  새 셈의 가치 점수 이동 (최대 3 · 회사 이름별 전 → 후)
- 로그 한 줄 (factor_pool_line) · main 이 두 시장 모두 그 줄을 남기는지 · roe_moves 가 같은 순위 무리로 견주는지
- 관문 줄 '펀드 팩터 점수 없음 (… · 경고만)': 없음 → 통과 · 남은 펀드 → 경고 (이름과 칸) · 읽지 못함 → 경고 · 어떤 경우에도 실패 없음
- (선택) BAEPSAE_FACTOR_DATA=발행 파일 폴더 이면 그 data.json 전체 (국내 · 미국) 로 전 → 후를 다시 봐요
"""
import copy
import inspect
import json
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

KEYS = ("pz", "vz", "mz", "qz", "lz", "dz")
FIX_US = os.path.join(ROOT, "tests", "fixtures", "factor_pool_us_1124.json")
REAL = os.environ.get("BAEPSAE_FACTOR_DATA")          # 발행 파일 폴더 (data.json): 국내 · 미국 전체로 전 → 후


def before(stocks):
    """main (99b5f52) 의 add_percentiles 셈 그대로 — 받은 행을 모두 한 무리로 매겨요 (펀드도). 이 파일의 '전' 값."""
    df = pd.DataFrame({k: pd.to_numeric(pd.Series([F._fin(s.get(k)) for s in stocks], dtype="object"), errors="coerce")
                       for k in ("cap", "pbr", "mom", "roe", "vol", "dyt")})
    pr = lambda c: df[c].rank(pct=True) * 100   # noqa: E731
    ser = {"pz": 100 - pr("cap"), "vz": 100 - pr("pbr"), "mz": pr("mom"), "qz": pr("roe"), "lz": 100 - pr("vol"), "dz": pr("dyt")}
    for i, s in enumerate(stocks):
        for k, x in ser.items():
            v = x.iloc[i]
            if pd.notna(v):
                s[k] = int(round(v))
    return stocks


def co(t, cls, i):
    return {"t": t, "cls": cls, "etf": False, "cap": 0.5 + i, "pbr": 0.6 + 0.3 * i, "mom": -20.0 + 7 * i, "roe": 2.0 + 1.5 * i,
            "vol": 15.0 + 2 * i, **({"dyt": 0.5 + 0.4 * i} if cls == "kr" else {})}


def market(cls):
    """회사 12곳 + 펀드 넷: 순위를 크게 흔드는 극단값 (PBR 0.01 · 아주 작은 시가총액 · 큰 수익률 · 높은 ROE · 낮은 변동성 · 높은 배당) ·
    etf 참 · fund 참 · 둘 다 · 미리 점수 칸이 있는 펀드."""
    cos = [co(f"{cls.upper()}{i:02d}", cls, i) for i in range(12)]
    ext = {"cap": 0.001, "pbr": 0.01, "mom": 900.0, "roe": 500.0, "vol": 0.1, **({"dyt": 50.0} if cls == "kr" else {})}
    funds = [{"t": f"{cls}E", "cls": cls, "etf": True, **ext},
             {"t": f"{cls}F", "cls": cls, "etf": False, "fund": True, **ext},
             {"t": f"{cls}B", "cls": cls, "etf": True, "fund": True, **ext},
             {"t": f"{cls}S", "cls": cls, "etf": True, **ext, **{k: 77 for k in KEYS}}]
    return cos, funds


# ── 1. 두 시장 모두: 펀드는 어느 순위에도 없고, 회사 점수는 펀드가 없을 때와 같아요 ──────────────
@pytest.mark.parametrize("cls", ["kr", "us"])
def test_funds_are_left_out_of_every_pool_in_both_markets(cls):
    cos, funds = market(cls)
    mixed = cos[:6] + funds[:2] + cos[6:] + funds[2:]                 # 순서가 섞여도
    F.add_percentiles(mixed)
    for f in funds:
        assert not any(k in f for k in KEYS), f                        # 미리 있던 칸(77)도 지워요 — 0 점이 아니라 칸이 없어요
    alone = before(copy.deepcopy(cos))                                 # 회사끼리만 (예전 셈)
    for a, b in zip(cos, alone):
        assert {k: a.get(k) for k in KEYS} == {k: b.get(k) for k in KEYS}, a["t"]
    # 극단값 펀드가 섞였다면 회사의 맨 위 점수가 한 칸씩 밀렸을 거예요 (회사 12곳: 가장 싼 · 가장 작은 회사 100 − 100/12 → 92, 펀드 하나가
    # 섞이면 100 − 200/13 → 85 · 수익률 · ROE 가장 높은 회사 100 → 92)
    assert max(c["vz"] for c in cos) == max(c["pz"] for c in cos) == max(c["lz"] for c in cos) == round(100 - 100 / 12) == 92
    assert max(c["mz"] for c in cos) == max(c["qz"] for c in cos) == 100
    if cls == "kr":
        assert max(c["dz"] for c in cos) == 100
    else:
        assert not any("dz" in c for c in cos)                         # 미국은 dyt 가 없어 배당 점수도 없어요 (예전 그대로)
    json.dumps(mixed, allow_nan=False)


@pytest.mark.parametrize("cls", ["kr", "us"])
def test_company_scores_are_unchanged_when_there_are_no_funds(cls):
    cos, _f = market(cls)
    blanks = [{"t": "N1", "cls": cls, "etf": False, "cap": None, "pbr": float("nan"), "mom": None, "roe": float("inf"), "vol": None},
              {"t": "N2", "cls": cls, "cap": 3.3, "pbr": -1.0, "mom": 5.0, "roe": None, "vol": 22.0}]   # etf 칸 없음 = 회사 (2.0 과 같아요)
    rows = cos + blanks
    want = before(copy.deepcopy(rows))
    got = F.add_percentiles(rows)
    assert got is rows
    assert [{k: s.get(k) for k in KEYS} for s in got] == [{k: s.get(k) for k in KEYS} for s in want]
    assert "vz" not in rows[-2] and "qz" not in rows[-2] and "pz" not in rows[-2]    # 빈 값 · NaN · inf 는 예전처럼 점수 없음


def test_only_funds_or_nothing_does_not_break():
    _c, funds = market("us")
    F.add_percentiles(funds)
    assert not any(k in f for f in funds for k in KEYS)
    assert F.add_percentiles([]) == []
    with pytest.raises(ValueError, match="섞였어요"):                   # 시장을 섞으면 예전처럼 멈춰요
        F.add_percentiles(market("kr")[0] + market("us")[1])


def test_the_fund_rule_is_the_2_0_apps():
    """펀드 = etf 가 참 또는 fund (src/v2/engine.js isStockLike: !s.fund && s.etf !== true). etf 칸이 없거나 거짓이면 회사예요."""
    assert F.factor_fund is V.factor_fund and F.FACTOR_KEYS is V.FACTOR_KEYS == KEYS
    assert V.factor_fund({"etf": True}) and V.factor_fund({"fund": True}) and V.factor_fund({"etf": False, "fund": True})
    assert not V.factor_fund({"etf": False}) and not V.factor_fund({}) and not V.factor_fund({"etf": None, "fund": None})
    assert not V.factor_fund(None) and not V.factor_fund("x")
    src = open(os.path.join(ROOT, "src", "v2", "engine.js"), encoding="utf-8").read()
    assert 'export const isStockLike = (s) => (s.cls === "kr" || s.cls === "us") && !s.fund && s.etf !== true;' in src


# ── 2. 11-24 발행본의 미국 행: 전 → 후 ─────────────────────────────────────────────────────────
def us_1124():
    fx = json.load(open(FIX_US, encoding="utf-8"))
    rows = [dict(zip(fx["cols"], r), cls="us") for r in fx["rows"]]
    return fx, rows


def test_the_fixture_is_the_published_us_ranking():
    fx, rows = us_1124()
    assert fx["publishedAt"] == "2026-11-24T06:40:59+09:00" and fx["usPxDate"] == "2026-11-23" and len(rows) == 800
    inputs = [{k: r[k] for k in ("t", "cls", "etf", "cap", "pbr", "mom", "roe", "vol", "dyt")} for r in rows]
    old = before(copy.deepcopy(inputs))
    assert [{k: o.get(k) for k in KEYS} for o in old] == [{k: r[k] for k in KEYS} for r in rows]   # 예전 식 = 발행된 점수 (하나도 다르지 않아요)
    etf = [r for r in rows if r["etf"]]
    assert len(etf) == 33 and sum(1 for r in etf if r["pbr"] is not None) == 23
    assert sum(1 for r in etf if r["vz"] is not None) == 23 and sum(1 for r in etf if r["mz"] is not None) == 33
    by = {r["t"]: r for r in rows}
    assert {t: by[t]["pbr"] for t in ("SOXX", "TLT", "XLY", "SPY", "GLD", "VTI")} == {"SOXX": 0.37, "TLT": 0.55, "XLY": 0.72, "SPY": 1.76,
                                                                                      "GLD": 2.04, "VTI": 2.66}
    assert by["SOXX"]["vz"] == by["TLT"]["vz"] == 100


def test_us_company_value_scores_before_and_after_on_the_1124_publish():
    fx, rows = us_1124()
    inputs = [{k: r[k] for k in ("t", "cls", "etf", "cap", "pbr", "mom", "roe", "vol", "dyt")} for r in rows]
    new = F.add_percentiles(copy.deepcopy(inputs))
    by_old, by_new = {r["t"]: r for r in rows}, {r["t"]: r for r in new}
    funds = [r["t"] for r in rows if r["etf"]]
    assert all(not any(k in by_new[t] for k in KEYS) for t in funds)                    # 33곳 모두 점수 없음
    cos = [r["t"] for r in rows if not r["etf"]]
    for k in KEYS:                                                                       # 회사가 점수를 얻거나 잃지는 않아요
        assert [t for t in cos if (by_old[t][k] is None) != (by_new[t].get(k) is None)] == [], k
    shift = {k: [abs(by_new[t][k] - by_old[t][k]) for t in cos if by_old[t][k] is not None] for k in ("vz", "mz", "lz")}
    assert len(shift["vz"]) == 665 and max(shift["vz"]) == 3 and sum(1 for x in shift["vz"] if x) == 547
    assert round(sum(shift["vz"]) / len(shift["vz"]), 2) == 1.24
    assert max(shift["mz"]) == 2 and max(shift["lz"]) == 3
    assert all(by_new[t]["pz"] == by_old[t]["pz"] and by_new[t].get("qz") == by_old[t]["qz"] for t in cos)   # 미국 ETF 는 시가총액 · ROE 가 없어 그대로
    vz = {t: (by_old[t]["vz"], by_new[t]["vz"]) for t in ("AAPL", "MSFT", "JPM", "XOM", "INTC", "KO", "TDY", "PLD")}
    assert vz == {"AAPL": (1, 1), "MSFT": (24, 24), "JPM": (67, 70), "XOM": (69, 71), "INTC": (59, 61), "KO": (16, 17), "TDY": (62, 65),
                  "PLD": (72, 75)}
    # 가장 싼 회사가 이제 가치 100 이에요 (예전엔 SOXX · TLT 가 100 이었어요)
    assert max(by_new[t]["vz"] for t in cos if by_new[t].get("vz") is not None) == 100


# ── 3. 로그 · main · roe_moves ───────────────────────────────────────────────────────────────
def test_the_log_line_counts_companies_and_names_the_funds():
    _f, rows = us_1124()
    inputs = [{k: r[k] for k in ("t", "cls", "etf", "cap", "pbr", "mom", "roe", "vol", "dyt")} for r in rows]
    F.add_percentiles(inputs)
    line = F.factor_pool_line("us", inputs)
    assert line == ("· 팩터 점수 (미국): 회사 767곳끼리 매겨요 (가치 vz 665 · 추세 mz 755 · 저변동 lz 756) · 펀드 33곳은 빼고 점수 없음 "
                    "(ARKK, DIA, GLD, IAU, IEF, IVE, IVV, IWM 외 25)"), line
    fund = next(r for r in inputs if r["etf"])
    fund["mz"] = 12                                                     # 누가 펀드에 점수를 다시 붙이면 크게
    line = F.factor_pool_line("us", inputs)
    assert line.startswith("  !! 팩터 점수 (미국)") and f"그런데 점수가 남은 펀드 1: {fund['t']} (관문이 경고해요)" in line, line
    cos, _fu = market("kr")
    F.add_percentiles(cos)
    assert F.factor_pool_line("kr", cos).startswith("· 팩터 점수 (국내): 회사 12곳끼리 매겨요") and "펀드 0곳은 빼고 점수 없음" in F.factor_pool_line("kr", cos)


def test_main_ranks_each_market_and_logs_the_pool():
    src = inspect.getsource(F.main)
    i_kr, i_us = src.index("add_percentiles(kr)"), src.index("add_percentiles(us)")
    assert i_kr < i_us < src.index('log(factor_pool_line("kr", kr))') < src.index('log(factor_pool_line("us", us))') \
        < src.index("miss_tr = trend_rank_missing(kr)") < src.index("build_corp(kr, fin_map")
    assert src.count("add_percentiles(") == 2


def test_roe_moves_compares_qz_over_the_same_pool(capsys):
    kr = [dict(co(f"K{i}", "kr", i)) for i in range(6)] + [{"t": "KF", "cls": "kr", "etf": True, "roe": 99.0}]
    old_roe = {s["t"]: s.get("roe") for s in kr}
    F.add_percentiles(kr)
    out = F.roe_moves(kr, old_roe)
    assert out["qz"] == 0 and out["qz5"] == []                         # ROE 가 그대로면 퀄리티 점수도 그대로 (펀드 ROE 가 견주는 쪽에만 섞이지 않게)


# ── 4. 관문 줄 '펀드 팩터 점수 없음' (경고만) ───────────────────────────────────────────────────
def gate(data):
    rep = V.Report()
    V.check_fund_scores(rep, data)
    rows = [r for r in rep.rows if r[0] == V.FUND_SCORE_ROW]
    assert len(rows) == 1 and rep.failed == []
    return rows[0][3], rows[0][1], rep


def test_gate_row_passes_when_no_fund_has_a_score():
    cos, funds = market("us")
    F.add_percentiles(cos + funds)
    st, val, _r = gate({"stocks": cos + funds + [{"t": "BND", "cls": "bond", "etf": True}]})
    assert (st, val) == ("PASS", "없음")


def test_gate_row_warns_and_names_funds_with_a_score():
    _f, rows = us_1124()
    data = {"stocks": [dict(r) for r in rows] + [{"t": "088980", "cls": "kr", "etf": True, "pz": 4, "mz": 66, "lz": 100, "vz": None},
                                                 {"t": "069500", "cls": "kr", "etf": True, "fund": True},
                                                 {"t": "04020000", "cls": "metal", "etf": True, "fund": True, "lz": 0}]}
    st, val, rep = gate(data)
    assert st == "WARN" and val.startswith("35종목: ARKK(mz·lz), DIA(vz·mz·lz), GLD(vz·mz·lz)"), val
    assert val.endswith(" 외 25종목 (회사 점수도 펀드와 함께 매겨졌어요)"), val
    title, items = rep.details[-1]
    assert title == "팩터 점수가 남은 펀드 (etf 참 · fund)" and len(items) == 35
    assert "088980: pz, mz, lz" in items and "04020000: lz" in items and not any(x.startswith("069500") for x in items)


@pytest.mark.parametrize("data", [{"stocks": "x"}, {}, None, "not a dict"])
def test_gate_row_warns_when_it_cannot_read_the_file(data):
    st, val, _r = gate(data)
    assert st == "WARN" and val.startswith("검사가 멈췄어요: ValueError: stocks 가 목록이 아님"), val


def test_gate_row_runs_in_every_mode():
    src = inspect.getsource(V.run_checks)
    i = src.index("check_fund_scores(rep, data)")
    assert src.count("check_fund_scores(") == 1 and src.index("check_us_split_pbr(rep, data)") < i
    # 앞에서 끝나는 모드가 이 줄을 건너뛰지 않는지: 바로 앞 줄들과 같은 자리 (return 없이 이어지는 곳)
    assert "return" not in src[src.index("check_us_split_pbr(rep, data)"):i]


# ── 5. (선택) 발행 파일 전체로 ─────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not REAL, reason="BAEPSAE_FACTOR_DATA 가 없어요 (발행 파일 폴더)")
def test_a_published_file_before_and_after_in_both_markets(capsys):
    d = json.load(open(os.path.join(REAL, "data.json"), encoding="utf-8"))
    seen = {}
    for m in ("kr", "us"):
        rows = [s for s in d["stocks"] if s.get("cls") == m and not s.get("fund")]       # main 이 add_percentiles 에 넘기는 행 (펀드 목록 행 빼고)
        base = [{k: v for k, v in s.items() if k not in KEYS} for s in rows]
        old, new = before(copy.deepcopy(base)), F.add_percentiles(copy.deepcopy(base))
        if not any(any(k in s for k in KEYS) for s in rows if V.factor_fund(s)):
            pass                                                                         # 이 PR 뒤의 발행본: 펀드에 점수가 없어요
        else:
            assert [{k: o.get(k) for k in KEYS} for o in old] == [{k: s.get(k) for k in KEYS} for s in rows]   # 예전 식 = 발행된 점수
        assert not any(k in n for n in new if V.factor_fund(n) for k in KEYS)
        sh = {k: max([abs(n[k] - o[k]) for o, n in zip(old, new) if not V.factor_fund(o) and o.get(k) is not None] or [0]) for k in KEYS}
        seen[m] = (sum(1 for s in rows if V.factor_fund(s)), sh)
        print(m, F.factor_pool_line(m, new), sh)
    assert seen["kr"][1]["vz"] == 0 and max(seen["kr"][1].values()) <= 1      # 국내 펀드는 PBR · ROE · 배당이 없어 가치 · 퀄리티 · 배당은 그대로
    assert max(seen["us"][1].values()) <= 3
