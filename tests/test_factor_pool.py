# -*- coding: utf-8 -*-
"""2026-11-24 (#189, 11-24 발행본 점검): 팩터 점수의 순위는 시장마다 회사 주식끼리만 매기고, 펀드는 그 회사 분포에 견준 자리를 받아요.

11-24 발행본 (pxDate · usPxDate 2026-11-23): 미국 ETF 33곳이 add_percentiles(us) 의 순위에 들어갔고, 그중 23곳은 야후의 priceToBook (펀드에는
뜻이 없어요: SOXX 0.37 · TLT 0.55 · XLY 0.72 · SPY 1.76 · 실제 SPY 의 P/B 는 약 5) 으로 가치 순위에 들어갔어요. 그래서 미국 회사 547곳의
가치 점수(vz)가 최대 3점 (평균 1.2) 틀어졌어요. 추세(mz) · 저변동(lz) 순위에도 ETF 33곳이 섞였고, 국내는 상장 인프라 펀드 3곳(088980 맥쿼리인프라
· 415640 KB발해인프라 · 094800 맵스리얼티, etf 참)이 규모 · 추세 · 저변동 순위에 섞였어요.
리뷰 #189 (S1 · S2): 펀드의 점수를 없애면 예전 뱁새의 '내 포트폴리오의 성향'과 기업분석의 성향 막대에서 숫자가 이유 없이 사라져요 → 펀드는 점수를
그대로 받되, 순위에 들어가지 않고 회사 분포에 견준 자리예요: 회사 값 중 그 값 이하인 곳의 비율 × 100 (규모 · 가치 · 저변동은 100 에서 빼요).

여기서 보는 것 (네트워크 없음 · 새 시험 파일 · 예전 시험은 그대로):
- fetch_data.add_percentiles: 두 시장 모두 회사 점수는 펀드가 없을 때와 같아요 (펀드가 어떤 값이어도) · 펀드 점수는 위 식 그대로 · 입력이 빈
  펀드는 그 점수가 없어요 · 펀드 행에 있던 낡은 점수 칸은 지우고 다시 매겨요 · 펀드가 없는 목록은 예전 셈 그대로 (main 99b5f52 의 식)
- 11-24 발행본의 미국 행 (tests/fixtures/factor_pool_us_1124.json): 예전 식이 발행된 점수를 그대로 다시 만들고 (고정 자료가 진짜라는 확인),
  회사 가치 점수 이동 (최대 3 · 회사 이름별 전 → 후) · 펀드는 점수를 잃지 않고 가까운 값 (SOXX · TLT · SPY · QQQ 전 → 후)
- 로그 한 줄 (factor_pool_line) · main 이 두 시장 모두 그 줄을 남기는지 · roe_moves 가 같은 순위 무리로 견주는지
- 관문 줄 '팩터 점수: 회사끼리 순위 · 펀드는 회사 분포에 견줌 (다시 매겨 맞춰 봄 · 경고만)': 파이프라인이 매긴 파일 → 통과 (pandas 없이 다시 매긴
  값이 한 칸도 다르지 않아요) · #189 전 파일 · 순위 뒤에 바뀐 값 · 점수가 있으면 안 되는 행 → 경고 · 읽지 못함 → 경고 · 실패는 없음
- (선택) BAEPSAE_FACTOR_DATA=발행 파일 폴더 이면 그 data.json 전체 (국내 · 미국) 로 전 → 후와 관문 줄을 다시 봐요
"""
import bisect
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
IN = ("t", "cls", "etf", "cap", "pbr", "mom", "roe", "vol", "dyt")
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


def fund_by_hand(cos, s):
    """펀드 점수를 손으로: 회사 값 중 그 값 이하인 곳의 비율 × 100 (규모 · 가치 · 저변동은 100 에서 뺌) · 반올림. 입력이 빈 칸은 없음."""
    out = {}
    for k, (col, low) in {"pz": ("cap", 1), "vz": ("pbr", 1), "mz": ("mom", 0), "qz": ("roe", 0), "lz": ("vol", 1), "dz": ("dyt", 0)}.items():
        ref = sorted(c[col] for c in cos if F._fin(c.get(col)) is not None)
        x = F._fin(s.get(col))
        if x is None or not ref:
            continue
        p = sum(1 for v in ref if v <= x) / len(ref) * 100
        out[k] = round(100 - p if low else p)
    return out


def co(t, cls, i):
    return {"t": t, "cls": cls, "etf": False, "cap": 0.5 + i, "pbr": 0.6 + 0.3 * i, "mom": -20.0 + 7 * i, "roe": 2.0 + 1.5 * i,
            "vol": 15.0 + 2 * i, **({"dyt": 0.5 + 0.4 * i} if cls == "kr" else {})}


def market(cls):
    """회사 12곳 + 펀드 다섯: 순위를 크게 흔드는 극단값 (PBR 0.01 · 아주 작은 시가총액 · 큰 수익률 · 높은 ROE · 낮은 변동성 · 높은 배당) ·
    etf 참 · fund 참 · 둘 다 · 낡은 점수 칸(77)이 있는 펀드 · 회사 사이 값(어떤 회사와 같은 값 포함)에 빈 칸이 섞인 펀드."""
    cos = [co(f"{cls.upper()}{i:02d}", cls, i) for i in range(12)]
    ext = {"cap": 0.001, "pbr": 0.01, "mom": 900.0, "roe": 500.0, "vol": 0.1, **({"dyt": 50.0} if cls == "kr" else {})}
    funds = [{"t": f"{cls}E", "cls": cls, "etf": True, **ext},
             {"t": f"{cls}F", "cls": cls, "etf": False, "fund": True, **ext},
             {"t": f"{cls}B", "cls": cls, "etf": True, "fund": True, **ext},
             {"t": f"{cls}S", "cls": cls, "etf": True, **ext, **{k: 77 for k in KEYS}},
             {"t": f"{cls}M", "cls": cls, "etf": True, "cap": 3.5, "pbr": 1.65, "mom": -100.0, "roe": None, "vol": float("nan"),
              **{k: 77 for k in KEYS}}]
    return cos, funds


# ── 1. 두 시장 모두: 회사 점수는 펀드가 없을 때와 같고, 펀드는 회사 분포에 견준 자리 ───────────────
@pytest.mark.parametrize("cls", ["kr", "us"])
def test_companies_are_ranked_alone_and_funds_sit_in_their_distribution(cls):
    cos, funds = market(cls)
    mixed = cos[:6] + funds[:2] + cos[6:] + funds[2:]                 # 순서가 섞여도
    F.add_percentiles(mixed)
    alone = before(copy.deepcopy(cos))                                 # 회사끼리만 (예전 셈)
    for a, b in zip(cos, alone):
        assert {k: a.get(k) for k in KEYS} == {k: b.get(k) for k in KEYS}, a["t"]
    # 극단값 펀드가 순위에 섞였다면 회사의 맨 위 점수가 한 칸씩 밀렸을 거예요 (회사 12곳: 100 − 100/12 → 92 · 섞이면 100 − 200/13 → 85)
    assert max(c["vz"] for c in cos) == max(c["pz"] for c in cos) == max(c["lz"] for c in cos) == round(100 - 100 / 12) == 92
    assert max(c["mz"] for c in cos) == max(c["qz"] for c in cos) == 100
    for f in funds:
        want = fund_by_hand(cos, f)
        assert {k: f[k] for k in KEYS if k in f} == want, f["t"]      # 낡은 77 은 남지 않아요 (다시 매기거나, 입력이 비면 칸이 없어요)
    ext = {k: 100 for k in KEYS if cls == "kr" or k != "dz"}           # 회사보다 싸고 작고 많이 오르고 ROE 높고 덜 흔들림 → 모두 100
    for f in funds[:4]:
        assert {k: f[k] for k in KEYS if k in f} == ext, f["t"]
    m = funds[4]                                                       # cap 3.5 = 넷째 회사(3.5)와 같음 · pbr 1.65 = 넷째(1.5)와 다섯째(1.8) 사이
    assert m["pz"] == round(100 - 100 * 4 / 12) == 67 == next(c for c in cos if c["cap"] == 3.5)["pz"]   # 같은 값이면 그 회사와 같은 점수
    assert m["vz"] == round(100 - 100 * 4 / 12) == 67 and m["mz"] == 0
    assert "qz" not in m and "lz" not in m and "dz" not in m           # 입력이 빈 칸 (ROE 없음 · 변동성 NaN · 배당 없음): 점수 없음
    if cls == "us":
        assert not any("dz" in c for c in cos)                         # 미국은 dyt 가 없어 배당 점수도 없어요 (예전 그대로)
    json.dumps([{k: s.get(k) for k in KEYS} for s in mixed], allow_nan=False)   # 점수 칸에 NaN 없음 (입력의 NaN 은 이 시험이 넣은 것)
    assert all(type(s[k]) is int for s in mixed for k in KEYS if k in s)


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


def test_ties_among_companies_and_a_fund_on_the_tie():
    """회사 넷이 같은 값: 회사는 평균 순위 (pandas) · 펀드는 '그 값 이하' 라 그 묶음의 맨 위 자리예요 (문서의 식 그대로)."""
    cos = [{"t": f"C{i}", "cls": "us", "etf": False, "mom": v} for i, v in enumerate([1.0, 2.0, 2.0, 2.0, 2.0, 3.0, 4.0, 5.0])]
    fd = {"t": "E", "cls": "us", "etf": True, "mom": 2.0}
    F.add_percentiles(cos + [fd])
    assert [c["mz"] for c in cos] == [12, 44, 44, 44, 44, 75, 88, 100]   # (2+5)/2 ÷ 8 = 43.75
    assert fd["mz"] == round(100 * 5 / 8) == 62


def test_only_funds_or_nothing_does_not_break():
    _c, funds = market("us")
    F.add_percentiles(funds)
    assert not any(k in f for f in funds for k in KEYS)                # 견줄 회사 값이 없으면 점수 없음 (낡은 칸도 지워요)
    assert F.add_percentiles([]) == []
    with pytest.raises(ValueError, match="섞였어요"):                   # 시장을 섞으면 예전처럼 멈춰요
        F.add_percentiles(market("kr")[0] + market("us")[1])
    assert F.fund_percentile([], 1.0, False) is None and F.fund_percentile([1.0], None, True) is None


def test_the_fund_rule_is_the_2_0_apps():
    """펀드 = etf 가 참 또는 fund (src/v2/engine.js isStockLike: !s.fund && s.etf !== true). etf 칸이 없거나 거짓이면 회사예요."""
    assert F.factor_fund is V.factor_fund and F.FACTOR_KEYS is V.FACTOR_KEYS == KEYS and F.FACTOR_SRC is V.FACTOR_SRC
    assert V.FACTOR_SRC == {"pz": ("cap", True), "vz": ("pbr", True), "mz": ("mom", False), "qz": ("roe", False), "lz": ("vol", True),
                            "dz": ("dyt", False)}
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


def inputs(rows):
    return [{k: r[k] for k in IN} for r in rows]


def test_the_fixture_is_the_published_us_ranking():
    fx, rows = us_1124()
    assert fx["publishedAt"] == "2026-11-24T06:40:59+09:00" and fx["usPxDate"] == "2026-11-23" and len(rows) == 800
    old = before(copy.deepcopy(inputs(rows)))
    assert [{k: o.get(k) for k in KEYS} for o in old] == [{k: r[k] for k in KEYS} for r in rows]   # 예전 식 = 발행된 점수 (하나도 다르지 않아요)
    etf = [r for r in rows if r["etf"]]
    assert len(etf) == 33 and sum(1 for r in etf if r["pbr"] is not None) == 23
    assert sum(1 for r in etf if r["vz"] is not None) == 23 and sum(1 for r in etf if r["mz"] is not None) == 33
    by = {r["t"]: r for r in rows}
    assert {t: by[t]["pbr"] for t in ("SOXX", "TLT", "XLY", "SPY", "GLD", "VTI")} == {"SOXX": 0.37, "TLT": 0.55, "XLY": 0.72, "SPY": 1.76,
                                                                                      "GLD": 2.04, "VTI": 2.66}
    assert by["SOXX"]["vz"] == by["TLT"]["vz"] == 100


def test_us_scores_before_and_after_on_the_1124_publish():
    fx, rows = us_1124()
    new = F.add_percentiles(copy.deepcopy(inputs(rows)))
    by_old, by_new = {r["t"]: r for r in rows}, {r["t"]: r for r in new}
    for k in KEYS:                                                                       # 어느 종목도 점수를 얻거나 잃지 않아요 (펀드 포함)
        assert [r["t"] for r in rows if (r[k] is None) != (by_new[r["t"]].get(k) is None)] == [], k
    cos = [r["t"] for r in rows if not r["etf"]]
    shift = {k: [abs(by_new[t][k] - by_old[t][k]) for t in cos if by_old[t][k] is not None] for k in ("vz", "mz", "lz")}
    assert len(shift["vz"]) == 665 and max(shift["vz"]) == 3 and sum(1 for x in shift["vz"] if x) == 547
    assert round(sum(shift["vz"]) / len(shift["vz"]), 2) == 1.24
    assert max(shift["mz"]) == 2 and max(shift["lz"]) == 3
    assert all(by_new[t]["pz"] == by_old[t]["pz"] and by_new[t].get("qz") == by_old[t]["qz"] for t in cos)   # 미국 ETF 는 시가총액 · ROE 가 없어 그대로
    vz = {t: (by_old[t]["vz"], by_new[t]["vz"]) for t in ("AAPL", "MSFT", "JPM", "XOM", "INTC", "KO", "TDY", "PLD")}
    assert vz == {"AAPL": (1, 1), "MSFT": (24, 24), "JPM": (67, 70), "XOM": (69, 71), "INTC": (59, 61), "KO": (16, 17), "TDY": (62, 65),
                  "PLD": (72, 75)}
    funds = {t: {k: (by_old[t][k], by_new[t].get(k)) for k in ("vz", "mz", "lz")} for t in ("SOXX", "TLT", "SPY", "QQQ")}
    assert funds == {"SOXX": {"vz": (100, 100), "mz": (90, 90), "lz": (27, 28)}, "TLT": {"vz": (100, 100), "mz": (23, 24), "lz": (99, 100)},
                     "SPY": {"vz": (82, 83), "mz": (46, 45), "lz": (97, 99)}, "QQQ": {"vz": (77, 79), "mz": (46, 45), "lz": (85, 87)}}
    fshift = [abs(by_new[r["t"]][k] - r[k]) for r in rows if r["etf"] for k in KEYS if r[k] is not None]
    assert len(fshift) == 23 + 33 + 33 and max(fshift) == 3                              # 펀드도 가까운 값 (예전 셈은 회사와 섞인 자리)
    assert all(by_new[r["t"]][k] == F.fund_percentile(sorted(x[V.FACTOR_SRC[k][0]] for x in rows if not x["etf"]
                                                             and x[V.FACTOR_SRC[k][0]] is not None), r[V.FACTOR_SRC[k][0]], V.FACTOR_SRC[k][1])
               for r in rows if r["etf"] for k in ("vz", "mz", "lz") if r[k] is not None)


# ── 3. 로그 · main · roe_moves ───────────────────────────────────────────────────────────────
def test_the_log_line_counts_stocks_and_names_the_funds():
    _f, rows = us_1124()
    rows = inputs(rows)
    F.add_percentiles(rows)
    line = F.factor_pool_line("us", rows)
    assert line == ("· 팩터 점수 (미국): 회사 주식 767종목끼리 순위 (가치 vz 665 · 추세 mz 755 · 저변동 lz 756) · 펀드 33곳은 순위에 넣지 않고 "
                    "회사 분포에 견줘 매김 (점수 있는 펀드 33) (ARKK, DIA, GLD, IAU, IEF, IVE, IVV, IWM 외 25)"), line
    kr = [dict(co(t, "kr", i)) for i, t in enumerate(("005930", "005935", "000660", "005385"))] + [{"t": "088980", "cls": "kr", "etf": True, "cap": 3.0}]
    F.add_percentiles(kr)
    assert F.factor_pool_line("kr", kr) == ("· 팩터 점수 (국내): 회사 주식 4종목 (우선주 2 포함)끼리 순위 (가치 vz 4 · 추세 mz 4 · 저변동 lz 4) · 펀드 1곳은 "
                                            "순위에 넣지 않고 회사 분포에 견줘 매김 (점수 있는 펀드 1) (088980)")


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


# ── 4. 관문 줄 '팩터 점수: 회사끼리 순위 · 펀드는 회사 분포에 견줌' (경고만) ──────────────────────
def gate(data):
    rep = V.Report()
    V.check_factor_pool(rep, data)
    rows = [r for r in rep.rows if r[0] == V.FACTOR_POOL_ROW]
    assert len(rows) == 1 and rep.failed == []
    return rows[0][3], rows[0][1], rep


def scored_file():
    _f, rows = us_1124()
    us = inputs(rows)
    kr_c, kr_f = market("kr")
    kr = kr_c + [f for f in kr_f if not f.get("fund")]
    F.add_percentiles(us)
    F.add_percentiles(kr)
    others = [{"t": "069500", "cls": "kr", "etf": True, "fund": True, "mom": 5.0}, {"t": "BND", "cls": "bond", "etf": True, "vol": 3.0},
              {"t": "04020000", "cls": "metal", "etf": True, "fund": True}]
    return {"stocks": kr + us + others}


def test_gate_row_passes_on_what_the_pipeline_writes():
    st, val, _r = gate(scored_file())                                  # pandas 로 매긴 값 = 관문이 pandas 없이 다시 매긴 값 (한 칸도 다르지 않아요)
    assert (st, val) == ("PASS", "모두 같음")
    t = {"stocks": [{"t": f"C{i}", "cls": "us", "etf": False, "mom": v} for i, v in enumerate([1.0, 2.0, 2.0, 2.0, 2.0, 3.0, 4.0, 5.0])]
         + [{"t": "E", "cls": "us", "etf": True, "mom": 2.0}]}
    F.add_percentiles(t["stocks"])
    assert gate(t)[:2] == ("PASS", "모두 같음")                       # 같은 값 묶음도 똑같이


def test_gate_row_warns_on_a_file_ranked_with_its_funds():
    _f, rows = us_1124()                                               # #189 전에 발행된 점수 그대로
    data = {"stocks": [dict(r) for r in rows]}
    st, val, rep = gate(data)
    assert st == "WARN" and val.startswith("다른 칸 ") and val.endswith("(펀드가 순위에 섞였거나 순위 뒤에 값이 바뀌었어요)"), val
    assert rep.details == []                                           # 다른 줄의 목록을 흔들지 않아요 (줄에 처음 10칸과 수)
    diffs = V.factor_score_diffs(data)
    assert ("JPM", "vz", 67, 70) in diffs and ("SPY", "lz", 97, 99) in diffs
    assert val.startswith(f"다른 칸 {len(diffs)} ({len({d[0] for d in diffs})}종목): ")


@pytest.mark.parametrize("change, want", [
    (lambda d: d["stocks"][0].__setitem__("vz", d["stocks"][0]["vz"] + 1), "KR00.vz"),                     # 회사 점수 하나가 다름
    (lambda d: d["stocks"][0].__setitem__("pbr", 99.0), "KR00.vz"),                                        # 순위 뒤에 값이 바뀜
    (lambda d: next(s for s in d["stocks"] if s["t"] == "SPY").pop("lz"), "SPY.lz None → 99"),             # 펀드 점수가 빠짐
    (lambda d: next(s for s in d["stocks"] if s["t"] == "069500").__setitem__("mz", 50), "069500.mz 50 → None"),   # 펀드 목록 행에 점수
    (lambda d: next(s for s in d["stocks"] if s["t"] == "BND").__setitem__("lz", 90), "BND.lz 90 → None"),         # 채권에 점수
    (lambda d: next(s for s in d["stocks"] if s["t"] == "AAPL").__setitem__("vz", True), "AAPL.vz True → 1"),     # 숫자가 아닌 점수
])
def test_gate_row_names_each_kind_of_difference(change, want):
    d = scored_file()
    change(d)
    st, val, _r = gate(d)
    items = [f"{t}.{k} {a} → {b}" for t, k, a, b in V.factor_score_diffs(d)]
    assert st == "WARN" and any(x.startswith(want) for x in items), (val, items[:5])


@pytest.mark.parametrize("data", [{"stocks": "x"}, {}, None, "not a dict"])
def test_gate_row_warns_when_it_cannot_read_the_file(data):
    st, val, _r = gate(data)
    assert st == "WARN" and val.startswith("검사가 멈췄어요: ValueError: stocks 가 목록이 아님"), val


def test_gate_row_runs_in_every_mode_and_needs_no_pandas():
    src = inspect.getsource(V.run_checks)
    i = src.index("check_factor_pool(rep, data)")
    assert src.count("check_factor_pool(") == 1 and src.index("check_us_split_pbr(rep, data)") < i
    assert "return" not in src[src.index("check_us_split_pbr(rep, data)"):i]
    body = inspect.getsource(V.factor_score_diffs) + inspect.getsource(V.check_factor_pool)
    assert "pd." not in body and "np." not in body                    # 관문은 pandas · numpy 없이 다시 매겨요 (파이프라인의 셈을 빌리지 않아요)
    assert "import pandas" not in open(V.__file__, encoding="utf-8").read() and "import numpy" not in open(V.__file__, encoding="utf-8").read()


# ── 5. (선택) 발행 파일 전체로 ─────────────────────────────────────────────────────────────────
@pytest.mark.skipif(not REAL, reason="BAEPSAE_FACTOR_DATA 가 없어요 (발행 파일 폴더)")
def test_a_published_file_before_and_after_in_both_markets(capsys):
    d = json.load(open(os.path.join(REAL, "data.json"), encoding="utf-8"))
    seen, after = {}, []
    for m in ("kr", "us"):
        rows = [s for s in d["stocks"] if s.get("cls") == m and not s.get("fund")]       # main 이 add_percentiles 에 넘기는 행 (펀드 목록 행 빼고)
        base = [{k: v for k, v in s.items() if k not in KEYS} for s in rows]
        old, new = before(copy.deepcopy(base)), F.add_percentiles(copy.deepcopy(base))
        after += new
        for o, n in zip(old, new):                                                       # 어느 종목도 점수를 얻거나 잃지 않아요
            assert all((o.get(k) is None) == (n.get(k) is None) for k in KEYS), o["t"]
        sh = {k: max([abs(n[k] - o[k]) for o, n in zip(old, new) if not V.factor_fund(o) and o.get(k) is not None] or [0]) for k in KEYS}
        fsh = max([abs(n[k] - o[k]) for o, n in zip(old, new) if V.factor_fund(o) for k in KEYS if o.get(k) is not None] or [0])
        seen[m] = (sh, fsh)
        print(m, F.factor_pool_line(m, new), sh, "funds", fsh,
              {o["t"]: {k: (o.get(k), n.get(k)) for k in KEYS if o.get(k) is not None} for o, n in zip(old, new) if V.factor_fund(o)} if m == "kr" else "")
    assert seen["kr"][0]["vz"] == 0 and max(seen["kr"][0].values()) <= 1      # 국내 펀드는 PBR · ROE · 배당이 없어 가치 · 퀄리티 · 배당은 그대로
    assert max(seen["us"][0].values()) <= 3 and max(seen["kr"][1], seen["us"][1]) <= 3
    rest = [s for s in d["stocks"] if not (s.get("cls") in ("kr", "us") and not s.get("fund"))]
    assert gate({"stocks": after + rest})[:2] == ("PASS", "모두 같음")
