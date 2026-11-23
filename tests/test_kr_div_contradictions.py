# -*- coding: utf-8 -*-
"""2026-11-23 · DART 배당 표 안의 어긋남과 그럴듯하지 않은 값 (네트워크 없음 · 2026-11-21 발행본 감사).

A. 한 해의 배당 표에 현금배당금총액은 있는데 보통주 주당 현금배당금이 0 ('-') 이면 그해 보통주 배당은 '모름' (빈 칸) 이에요 — 0 (배당 없음) 이
   아니에요. 우선주 · 종류주가 총액을 다 받은 해만 0 이 맞아요. 올해 것을 비운 배당 회사는 증명의 data (nodps) 에 적혀 줄 4 를 받아요.
B. 주당 칸의 값이 주당 금액이 아닌 해 (총액의 1,000배 넘게 — 와이엔텍 · 종가 이상만으로는 아니에요) 는 그해 주당 배당을 비우고 (올해 것이 총액과 1,000배 넘게
   다르면 예전 증명과 같은 div · 줄 3 — '회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 …'),
   DART 배당수익률(dy)이 오늘 기준 주당 배당 ÷ 52주 범위에서 3배 넘게 벗어나면 비워요 (흥국 56.0 · 지투파워 33.7 · 아비코전자 30.0 · 알피바이오 10.0).
관문: 새 줄 둘은 경고만 (검사가 멈춰도) · nodps 는 그 종목의 주당 배당이 정말 비었을 때만 줄 4 를 받아요.

실제 숫자: 2026-11-21 06:41 발행본 (pxDate 2026-11-20) 의 종목 · corp.json cash3 (억원) · 와이엔텍의 배당 표는 tests/fixtures/dvproof/cases_1115.json
(2026-11-15 OpenDART 응답을 파이프라인의 해석 함수로 읽은 값)."""
import copy
import datetime as dt
import inspect
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402
from test_v191b_data import alot, check, rows_of, recount  # noqa: E402
from test_v191h_div_why import mirror, recount_why  # noqa: E402
from test_v191i_div_proof import with_proof, ROWS  # noqa: E402

PX = dt.date(2026, 11, 20)
SUB_ROW = "숨긴 배당수익률의 줄 (divCheck.proofSub · dvLine 2 · 3 · 4)"
ODD_ROW = "주당 배당금·배당수익률 맞음"                  # 예전 실패 줄 (DPS_DY_ODD_MAX 1.0% · 리뷰 #179 B1: 예전 힘 그대로)
RAW_ROW, PLAUS_ROW = V.DIV_RAW_ROW, V.DIV_PLAUS_ROW


def _load(name):
    with open(os.path.join(ROOT, "tests", "fixtures", "dvproof", name), encoding="utf-8") as f:
        return json.load(f)


def stock(t, rows, price, shr, hi=None, lo=None, fy=2025, nk="", stk=None):
    """parse_dart_dividend (캐시가 담는 해석) 그대로 종목에 붙여요 — enrich_with_dart 와 같은 칸 (stk: 주식의 총수 현황 · parse_dart_shares 꼴)."""
    div = F.parse_dart_dividend(rows)
    s = {"t": t, "nk": nk, "cls": "kr", "price": price, "shr": shr, "fy": fy, "hi": hi or price, "lo": lo or price}
    if stk:
        s["_stk"] = dict(stk)
    for k in ("dps", "dps3", "dy"):
        if div.get(k) is not None:
            s[k] = div[k]
    if div.get("bas"):
        s["_bas"] = div["bas"]
    return s


def run(stocks, pref=None):
    """main 과 같은 순서: div_raw_guard → apply_div_basis (DivWhy · DART 없음) → div_dy_guard."""
    pref = pref or {}
    rec = F.div_raw_guard(stocks, pref)
    why = F.DivWhy(None, PX)
    counts, extra = F.apply_div_basis(stocks, {}, pref, why=why)
    counts["raw"] = rec
    F.div_dy_guard(stocks, rec, px=PX)
    counts["_extra"] = extra
    return {s["t"]: s for s in stocks}, counts


# 현대코퍼레이션 011760 (2026-11-21 발행본): 2025 주당 '-' · 총액 84.08억원 · 2024 700원 · 2023 600원 · DART 배당수익률 3.1% · 종가 21,750원
HYUNDAI_CORP = alot([None, 700, 600], cash=[8408, 8408, 7207], par=[5000, 5000, 5000], dy=[3.1, 3.4, 3.2])


# ── A. 0 인데 총액이 있는 해 → 모름 ─────────────────────────────
def test_the_cached_parse_is_unchanged_so_no_dividend_entry_is_fetched_again():
    """해석(parse_dart_dividend)은 그대로예요 — DART 캐시는 해석된 값을 담아서, 해석을 바꾸면 배당 항목 약 2,500건을 다시 받아야 해요."""
    got = F.parse_dart_dividend(HYUNDAI_CORP)
    assert got["dps"] == 0 and got["dps3"] == [0, 700, 600] and got["bas"]["cash3"] == [8408e6, 8408e6, 7207e6]
    assert F.dart_dividend.__code__.co_consts.count("DIV2") == 1                   # 캐시 태그도 그대로


def test_common_zero_with_a_cash_total_becomes_unknown_never_zero():
    by, counts = run([stock("011760", HYUNDAI_CORP, 21750.0, 13228966, hi=32550.0, lo=20450.0, nk="현대코퍼레이션")])
    s = by["011760"]
    assert "dps" not in s and s["dps3"] == [None, 700, 600]                        # 2025 는 모름 · 앞 두 해는 그대로 (만들어 내지 않아요)
    assert s.get("dyt") is None and s.get("dz") is None and s["divSt"] in ("nc", "nd") and s["dps3a"][0] is None
    assert s["dvLine"] == 4 and V.PROVE_SUB_LINE["data"]["nodps"] == 4                # 줄 4: "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 …"
    assert counts["proofSub"]["data"] == {"011760": "nodps"} and counts["proof"]["dataT"] == ["011760"] and counts["proof"]["data"] == 1
    assert counts["raw"]["contra"] == {"011760": [0]} and counts["raw"]["prefOnly"] == {} and counts["raw"]["dpsBad"] == {}
    assert s["dy"] == 3.1 and counts["raw"]["dyNo"] == 1                             # 주당 배당을 모르면 dy 는 견주지 않고 그대로
    assert counts["raw"]["pre"] == {"011760": [0.0, 3.1]}                            # 비우기 전 값 ('주당 배당금·배당수익률 맞음' 줄이 셈)
    assert "_divRaw" not in s and "_bas" not in s
    assert counts["payers"] == 0                                                     # 배당했는지 '모름' — 배당 없음(zero)도 배당한 회사도 아니에요


def test_every_year_with_a_total_and_no_per_share_figure_is_unknown_and_an_all_blank_history_is_dropped():
    """케이프 064820: 세 해 모두 0 인데 총액 215.85 · 82.81 · 84.52억원 → dps3 를 지워요 (관문: dps3 가 있는 보통주는 divSt 가 있어야 해요)."""
    rows = alot([0, 0, 0], cash=[21585, 8281, 8452], dy=[6.6, 3.1, 3.4])
    by, counts = run([stock("064820", rows, 5180.0, 30860215, hi=16900.0, lo=5180.0, nk="케이프")])
    s = by["064820"]
    assert "dps" not in s and "dps3" not in s and "divSt" not in s and "dyt" not in s
    assert s["dvLine"] == 4 and counts["proofSub"]["data"] == {"064820": "nodps"} and counts["raw"]["contra"] == {"064820": [0, 1, 2]}
    assert counts["noDps"] == 1 and counts["zero"] == 0


def test_an_earlier_year_only_loses_its_bar_and_this_years_yield_stays():
    """대원 007680 (2026-11-21): 2023 주당 0 인데 총액 40.33억원 → 2023 만 모름 · 올해 수익률과 줄은 그대로 (줄 없음)."""
    rows = alot([200, 120, 0], cash=[2645, 1614, 4033])
    by, counts = run([stock("007680", rows, 2466.0, 13222738, nk="대원")])
    s = by["007680"]
    assert s["dps"] == 200 and s["dps3"] == [200, 120, None] and "dvLine" not in s
    assert counts["raw"]["contra"] == {"007680": [2]} and counts["proofSub"]["data"] == {}


def test_a_true_zero_with_no_total_stays_zero():
    for rows in (alot([0, 0, 0], cash=[0, 0, 0], dy=[0, 0, 0]),            # 총액도 '-' (0)
                 alot([0, 0, 0], dy=[0, 0, 0]),                            # 총액 줄이 없음 — 견줄 게 없어요
                 alot([0, 500, 400], cash=[0, 1000, 800])):                # 올해만 배당 없음
        by, counts = run([stock("000010", rows, 10000.0, 2_000_000)])
        s = by["000010"]
        assert s["dps"] == 0 and s["dps3"][0] == 0 and s["dyt"] == 0.0 and "dvLine" not in s, rows
        assert counts["raw"]["contra"] == {} and counts["proofSub"]["data"] == {}


def test_a_preferred_only_payer_keeps_its_zero():
    """보통주 '-' · 상장 우선주 1,000,000주가 주당 500원 · 총액 5억원 = 우선주 몫 그대로 → 보통주 0 이 맞아요 (배당 없음)."""
    rows = alot([0, 0, 0], cash=[500, 0, 0], pdps=[500, 0, 0])
    pref = {"00001": [1_000_000]}
    by, counts = run([stock("000010", rows, 10000.0, 5_000_000)], pref=pref)
    s = by["000010"]
    assert s["dps"] == 0 and s["dps3"] == [0, 0, 0] and s["dyt"] == 0.0 and "dvLine" not in s
    assert counts["raw"]["prefOnly"] == {"000010": [0]} and counts["raw"]["contra"] == {}
    # 우선주 몫이 총액을 설명하지 못하면 (보통주도 받은 것) → 모름
    rows = alot([0, 0, 0], cash=[2000, 0, 0], pdps=[500, 0, 0])
    by, counts = run([stock("000010", rows, 10000.0, 5_000_000)], pref=pref)
    assert "dps" not in by["000010"] and counts["raw"]["contra"] == {"000010": [0]} and by["000010"]["dvLine"] == 4


def test_an_unlisted_preferred_payer_needs_the_year_end_share_count():
    """상장되지 않은 종류(상환전환우선주 등)가 받았으면 최근 사업보고서의 주식의 총수 현황의 우선주 · 종류주 수로 (앞 해에도 ± 15% · 리뷰 #179) ·
    없으면 모름."""
    paid = [[300.0, 0.0, 0.0]]
    assert V.div_zero_contra([0, 0, 0], [3e8, 0, 0], paid, (), pfo=1_000_000) == ([], [0])
    assert V.div_zero_contra([0, 0, 0], [3e8, 0, 0], paid, (), pfo=None) == ([0], [])
    assert V.div_zero_contra([0, 0, 0], [0, 0, 3e8], [[0.0, 0.0, 300.0]], (), pfo=1_000_000) == ([], [2])   # 앞 해도 같은 수로
    assert V.div_zero_contra([0, 0, 0], [0, 0, 6e8], [[0.0, 0.0, 300.0]], (), pfo=1_000_000) == ([2], [])   # 그 수로 설명 못 하면 모름
    assert V.div_zero_contra([0, 0, 0], [3e8, 0, 0], [[300.0, 0, 0], [0.0, 0, 0]], (), pfo=1_000_000) == ([0], [])   # 받지 않은 종류가 섞임
    # 상장 우선주: 가장 적은 ~ 가장 많은 종목 수 × 주당 배당 ± 15%
    assert V.pref_explains(5.6e8, [500.0], [1_000_000, 2_000_000]) and V.pref_explains(1.15e9, [500.0], [1_000_000, 2_000_000])
    assert not V.pref_explains(1.2e9, [500.0], [1_000_000, 2_000_000]) and not V.pref_explains(4e8, [500.0], [1_000_000, 2_000_000])
    assert not V.pref_explains(5e8, [], [1_000_000]) and not V.pref_explains(0, [500.0], [1_000_000])


def test_the_real_dart_samples_in_the_fixtures_are_unchanged():
    """v19.1i · v19.1j 의 실제 OpenDART 응답 41곳: 와이엔텍 말고는 하나도 바뀌지 않아요 (0 인데 총액이 있는 해 · 1,000배 넘는 주당 배당 없음)."""
    cases = {**_load("cases.json")["cases"], **_load("cases_1115.json")["cases"]}
    hit = {}
    for t, c in cases.items():
        b = c.get("bas") or {}
        contra, po = V.div_zero_contra(c["s"]["dps3"], b.get("cash3"), b.get("pdps") or (), c.get("pref") or ())
        far = V.dps_far_years(c["s"]["dps3"], b.get("cash3"), c["s"].get("shr"))
        if contra or po or far:
            hit[t] = (contra, po, far)
    assert hit == {"067900": ([], [], [0, 1, 2])}


# ── B. 주당 칸의 값이 주당 금액이 아님 · 그럴듯하지 않은 배당수익률 ────────────
def test_a_total_written_in_the_per_share_cell_is_blanked_with_line_three():
    """와이엔텍 067900: 주당 칸에 총액 (1,809,965,900원 · 총액 18.09억원) → 세 해 모두 비우고, 예전 증명과 같은 div · 줄 3 ('배당 표가 주식 수와
    어긋남' — 총액 ÷ 주당 배당 = 1주 · 그대로 맞아요). 증명 계산은 이제 주당 배당 없이는 돌지 않아서 div_raw_guard 가 적어요."""
    c = _load("cases_1115.json")["cases"]["067900"]
    s = {**copy.deepcopy(c["s"]), "cls": "kr", "t": "067900", "_bas": copy.deepcopy(c["bas"]), "dps": c["s"]["dps3"][0]}
    by, counts = run([s])
    s = by["067900"]
    assert "dps" not in s and "dps3" not in s and "divSt" not in s and s["dvLine"] == 3
    assert counts["raw"]["dpsBad"] == {"067900": [0, 1, 2]} and counts["proofSub"]["data"] == {"067900": "div"}
    assert counts["proof"]["dataT"] == ["067900"] and counts["raw"]["pre"] == {"067900": [1809965900.0, None]}
    # 리뷰 #179 (S1): 세 해를 모두 비워 dps3 가 없어도 corp.json 의 총액 · 주당순이익은 그대로 (2.0 의 배당성향 고리 · 관문의 총액 줄)
    assert counts["_extra"]["067900"]["cash3"] == [18.09, 12.66, 9.04]


def test_a_per_share_figure_at_or_above_the_close_is_kept():
    """리뷰 #179: 올해 주당 배당 ≥ 종가만으로는 비우지 않아요 — 총액이 그 숫자를 말하면 (주당 × 주식 수 ≈ 총액) 맞는 값이고, 총액이 없으면 증명 단계가
    예전처럼 nototal 줄 4 를 달아요 (이유 줄 없이 비우는 일이 없게)."""
    for rows in (alot([6000, 500, 400], cash=[6000, 500, 400]), alot([6000, 500, 400])):   # 1,000,000주 × 6,000원 = 60억원 · 종가 5,000원
        by, counts = run([stock("000040", rows, 5000.0, 1_000_000)])
        s = by["000040"]
        assert s["dps"] == 6000 and s["dps3"] == [6000, 500, 400] and counts["raw"]["dpsBad"] == {} and counts["raw"]["pre"] == {}


def test_split_sized_ratios_and_pre_listing_dividends_are_kept():
    """2026-11-21 의 맞는 값: 분할 · 무상증자 · 상장 전 해는 주당 배당 × 오늘 주식 수 ÷ 총액이 70배 아래 (위너스일렉 2023 29,412원 · 69.9배)."""
    assert V.dps_far_years([1085, 2160, 1615], [65e8, 129.4e8, 96.75e8], 60_000_000) == []          # 포스코스틸리온 ×10
    assert V.dps_far_years([0, 0, 29412], [0, 0, 30e8], 7_126_000) == []                             # 위너스일렉 2023 (69.9배)
    assert V.dps_far_years([1809965900, 1266976130, 904982950], [18.09e8, 12.66e8, 9.04e8], 18199659) == [0, 1, 2]
    assert V.dps_far_years([6000, 0, 0], [None, None, None], 1_000_000) == []                       # 총액이 없으면 고르지 않아요 (nototal)
    assert V.dps_far_years([2500, 2000, 1500], [25e8, 20e8, 15e8], 50_000_000) == []                # 50:1 분할 뒤의 옛 기준 (분할 확인이 맞춰요)


@pytest.mark.parametrize("t,dy,a0,px,hi,lo,want", [
    ("010240 흥국 (배당 ÷ 액면가)", 56.0, 280.0, 4880.0, 5960.0, 4815.0, True),
    ("388050 지투파워 (배당성향)", 33.7, 100.0, 6080.0, 17250.0, 5630.0, True),
    ("036010 아비코전자", 30.0, 30.0, 5270.0, 13430.0, 4450.0, True),
    ("314140 알피바이오", 10.0, 50.0, 5130.0, 7890.0, 5000.0, True),
    ("002220 한일철강 (5.1배)", 6.0, 30.0, 2645.0, 5900.0, 2550.0, True),
    ("062040 산일전기 (dy '-' → 0)", 0.0, 1250.0, 104800.0, 333500.0, 104800.0, True),
    ("005930 삼성전자", 1.5, 1668.0, 183100.0, 362500.0, 94800.0, False),
    ("018500 동원모빌리티 (2.38배 · 남겨요)", 10.0, 50.0, 1286.0, 1903.0, 1190.0, False),
    ("472850 폰드그룹 (52주 없음)", 2.8, 157.29, 3600.0, None, None, False),
    ("배당 없음 · dy 0", 0.0, 0.0, 5000.0, 6000.0, 4000.0, False),
    ("배당 없음 · dy > 0", 2.0, 0.0, 5000.0, 6000.0, 4000.0, True),
    ("주당 배당 모름", 2.0, None, 5000.0, 6000.0, 4000.0, None),
])
def test_report_yield_is_checked_against_todays_per_share_dividend_over_the_52_week_range(t, dy, a0, px, hi, lo, want):
    assert V.dy_far(dy, a0, px, hi, lo) is want, t


def test_the_report_yield_is_only_compared_on_a_verified_share_basis():
    """오늘 주식 수 기준을 확인하지 못한 해(dpsF[0] 없음)는 견주지 않아요 — 분할 뒤의 주당 배당 ÷ 종가는 배율만큼 커요."""
    s = {"dps": 1000.0, "dps3": [1000.0, 900.0, 800.0], "dps3a": [None, None, None], "dpsF": [None, None, None]}
    assert V.dy_base(s) is None
    assert V.dy_base({**s, "dps3a": [100.0, 90.0, 80.0], "dpsF": [10.0, 10.0, 10.0]}) == 100.0
    assert V.dy_base({"dps": 0.0, "dps3": [0.0, 0.0, 0.0]}) == 0.0 and V.dy_base({"dps3": [None, 1.0, 1.0]}) is None


def payer(t, dps3, dy, price, hi, lo, capital=True):
    """주식 수 1,000,000주 · 액면가 500원 · 총액 = 주당 배당 × 주식 수 인 배당 회사 (capital: 자본금이 있어 배율 1 을 확인할 수 있음)."""
    s = stock(t, alot(dps3, cash=list(dps3), par=[500, 500, 500], dy=dy), price, 1_000_000, hi=hi, lo=lo)
    if capital:
        s["_cap"] = {"cs3": [5.0, 5.0, 5.0], "k": "all"}                          # 1,000,000주 × 500원 = 5억원
    return s


def test_the_dy_guard_blanks_only_the_unbelievable_yields_and_counts_the_rest():
    ss = [payer("010240", [280, 220, 240], [56.0, 44.0, 48.0], 4880.0, 5960.0, 4815.0),        # 흥국 (2026-11-21 의 종가 · 52주)
          payer("000020", [1000, 900, 800], [2.0, 2.0, 2.0], 50000.0, 60000.0, 40000.0),
          payer("000030", [1000, 1000, 1000], [2.0, 2.0, 2.0], 5000.0, 6000.0, 4000.0, capital=False)]   # 배율을 확인하지 못함 (nd)
    by, counts = run(ss)
    assert "dy" not in by["010240"] and by["010240"]["dyt"] == 5.74 and by["010240"]["dps"] == 280      # dyt · 주당 배당은 그대로
    assert by["000020"]["dy"] == 2.0 and by["000020"]["dyt"] == 2.0
    assert by["000030"]["dy"] == 2.0 and by["000030"]["divSt"] == "nd" and "dyt" not in by["000030"]
    assert counts["raw"]["dyBad"] == {"010240": 56.0} and counts["raw"]["dyOk"] == 1 and counts["raw"]["dyNo"] == 1
    assert "dvLine" not in by["010240"]                                                  # 2.0 은 dy 를 쓰지 않아요 (줄도 없어요)


def test_samsung_and_hyundai_motor_are_unchanged():
    """2026-11-21 발행본 숫자 그대로 (배당 표 · 종가 · 52주 · 주식 수)."""
    sam = alot([1668, 1446, 1444], cash=[11107906, 9810767, 9809438], pdps=[1669, 1447, 1445], dy=[1.5, 2.7, 1.9])
    hmc = alot([10000, 12000, 11400], cash=[2618263, 3147839, 2998657], dy=[1.9, 4.9, 4.0])
    ss = [stock("005930", sam, 183100.0, 5846278608, hi=362500.0, lo=94800.0), stock("005380", hmc, 255000.0, 203466492, hi=750000.0, lo=254500.0)]
    before = copy.deepcopy([{k: s.get(k) for k in ("dps", "dps3", "dy")} for s in ss])
    rec = F.div_raw_guard(ss, {"00593": [802371203], "00538": [34257047, 22839037, 2321926]})
    assert [{k: s.get(k) for k in ("dps", "dps3", "dy")} for s in ss] == before and not any(rec[k] for k in ("contra", "prefOnly", "dpsBad"))
    assert all("_divRaw" not in s for s in ss)
    for s, a0 in zip(ss, (1668.0, 10000.0)):                                              # 발행본의 dps3a[0] (배율 1)
        assert V.dy_far(s["dy"], a0, s["price"], s["hi"], s["lo"]) is False


# ── 리뷰 #179 (2026-11-23) ─────────────────────────────────────
# 2026-11-23 에 읽은 DART 배당 표 (alotMatter · 2025 사업보고서 · 키 없이 값만): 현대코퍼레이션 · 한텍 · 에코프로머티 · 솔루스첨단소재는 보통주 주당
# 현금배당금 줄이 하나뿐이고 그 당기 칸이 '-' 예요 (다른 보통주 줄 없음 — 줄 4 의 말이 그대로 맞아요). 티에스아이는 보통주 '-' · 우선주 505원 세 해 ·
# 총액 23.60억원 세 해 · 주식의 총수 현황의 우선주 4,673,989주 (× 505원 = 23.60억원) — 우선주만 받은 회사예요.
def test_a_preferred_only_payer_with_unlisted_preferred_shares_keeps_every_zero():
    """티에스아이 277880: 상장되지 않은 우선주가 세 해 모두 총액을 다 받았어요 → 보통주 0 은 그대로 (배당 없음 · 앞 해도 같은 수로)."""
    rows = alot([None, None, None], cash=[2360, 2360, 2360], pdps=[505, 505, 505], dy=[None, None, None])
    stk = {"cmo": 19843212, "cmi": 20206248, "pfo": 4673989}
    by, counts = run([stock("277880", rows, 2555.0, 19843212, stk=stk, nk="티에스아이")])
    s = by["277880"]
    assert s["dps"] == 0 and s["dps3"] == [0, 0, 0] and s["dyt"] == 0.0 and "dvLine" not in s
    assert counts["raw"]["prefOnly"] == {"277880": [0, 1, 2]} and counts["raw"]["contra"] == {} and counts["raw"]["pre"] == {}
    by, counts = run([stock("277880", rows, 2555.0, 19843212, nk="티에스아이")])          # 주식의 총수 현황이 없으면 셀 수 없어 모름
    assert counts["raw"]["contra"] == {"277880": [0, 1, 2]} and by["277880"]["dvLine"] == 4


def test_a_dash_read_as_zero_yield_is_blanked_with_the_unknown_dividend():
    """한텍 098070 (2026-11-23 의 DART 표): 2025 보통주 주당 배당 '-' · 배당수익률 '-' (0 으로 읽음) · 총액 41.70억원 → 주당 배당과 dy 0 을 함께 비워요
    (예전 뱁새가 0.0% 를 보이지 않게) · 비우기 전 값은 pre 에."""
    rows = alot([None, 450, 350], cash=[4170, 3970, 3088], dy=[None, 0.09, 0.07])
    by, counts = run([stock("098070", rows, 13930.0, 11121141, nk="한텍")])
    s = by["098070"]
    assert "dps" not in s and "dy" not in s and s["dvLine"] == 4
    assert counts["raw"]["dyBad"] == {"098070": 0.0} and counts["raw"]["pre"] == {"098070": [0.0, 0.0]}


def test_foreign_issuers_are_never_blanked_without_a_line(capsys):
    """해외 기업 (9…): 증명 단계가 이유 줄을 달지 않아서 비우지 않아요 (예전 그대로) · 이름은 로그에 크게."""
    rows = alot([None, 700, 600], cash=[8408, 8408, 7207], dy=[3.1, 3.4, 3.2])
    by, counts = run([stock("900140", rows, 5000.0, 10_000_000, nk="해외기업")])
    s = by["900140"]
    assert s["dps"] == 0 and s["dps3"][0] == 0 and "dvLine" not in s and counts["raw"]["contra"] == {} and counts["raw"]["pre"] == {}
    assert "해외 기업 1곳은 예전 값 그대로" in capsys.readouterr().out


def test_the_guard_changes_nothing_when_it_stops_half_way(monkeypatch):
    """리뷰 #179: 다 하거나 아무것도 안 해요 — 둘째 종목에서 멈추면 첫째 종목도 그대로 (기록도 없어요)."""
    ss = [stock("011760", HYUNDAI_CORP, 21750.0, 13228966), stock("000020", alot([100, 100, 100], cash=[100, 100, 100]), 5000.0, 1_000_000)]
    real, seen = F.dps_far_years, []

    def boom(*a, **k):
        seen.append(1)
        if len(seen) == 2:
            raise RuntimeError("시험")
        return real(*a, **k)
    monkeypatch.setattr(F, "dps_far_years", boom)
    before = copy.deepcopy([{k: v for k, v in s.items() if not k.startswith("_")} for s in ss])
    with pytest.raises(RuntimeError):
        F.div_raw_guard(ss, {})
    assert [{k: v for k, v in s.items() if not k.startswith("_")} for s in ss] == before and "_divRaw" not in ss[0]


def test_the_report_yield_is_not_compared_outside_its_52_week_window():
    """리뷰 #179: dy 는 보고서 해 말 주가로 셌어요 — 그때가 오늘의 52주 창 밖이면 (1월 ~ 새 사업보고서 · 지난해 보고서를 쓰는 회사) 값은 견주지 않아요.
    0 과의 어긋남은 그대로."""
    assert V.dy_window_ok(2025, "2026-11-20") and not V.dy_window_ok(2025, "2027-02-15") and not V.dy_window_ok(2024, "2026-11-20")
    assert not V.dy_window_ok(None, "2026-11-20") and not V.dy_window_ok(2025, None)
    assert V.dy_far(56.0, 280.0, 4880.0, 5960.0, 4815.0, window=False) is None
    assert V.dy_far(0.0, 280.0, 4880.0, window=False) is True and V.dy_far(2.0, 0.0, 4880.0, window=False) is True
    s = payer("010240", [280, 220, 240], [56.0, 44.0, 48.0], 4880.0, 5960.0, 4815.0)
    s["fy"] = 2024
    by, counts = run([s])
    assert by["010240"]["dy"] == 56.0 and counts["raw"]["dyBad"] == {} and counts["raw"]["dyNo"] == 1


def thirty_dash(files, a, b, dy=2.0):
    """관문 픽스처의 배당 회사 30곳을 파이프라인이 '-' + 총액으로 비운 꼴로 (주당 배당 없음 · 줄 4 · 기록) — DART dy 는 dy."""
    data, corp = files["data"], files["corp"]
    kr = [s for s in data["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    cby = {c["t"]: c for c in corp["companies"]}
    picks = [s for s in kr if (s.get("dps") or 0) > 0 and s["t"] not in V.MUST and s["t"] not in (a["t"], b["t"]) and "dvProof" not in s
             and s.get("divSt") == "same" and s["t"] in cby][:30]
    assert len(picks) == 30
    raw, proof, sub = data["divCheck"]["raw"], data["divCheck"]["proof"], data["divCheck"]["proofSub"]
    for s in picks:
        s.pop("dps")
        s.update(dps3=[None] + s["dps3"][1:], dps3a=[None] * 3, dpsF=[None] * 3, divSt="nd", dvLine=4, dy=dy)
        s.pop("dyt", None), s.pop("dz", None)
        mirror(files, s)
        raw["contra"][s["t"]] = [0]
        raw["pre"][s["t"]] = [0.0, dy]
        sub["data"][s["t"]] = "nodps"
    proof["dataT"] = sorted(set(proof["dataT"]) | {s["t"] for s in picks})
    proof["data"] = len(proof["dataT"])
    keep = {k: data["divCheck"][k] for k in ("proof", "proofSub", "raw", "why")}
    recount(files)
    data["divCheck"].update(keep)
    return picks


def test_the_odd_row_keeps_its_full_strength_after_the_pipeline_blanks(raw_pair):
    """리뷰 #179 B1: 30곳이 주당 배당 '-' + 총액 + DART 배당수익률 2.0% 이면 #179 전에는 '주당 배당금·배당수익률 맞음' 이 실패했어요 (30 / 2,400 =
    1.25% > 1%). 파이프라인이 그 주당 배당을 비운 뒤에도 비우기 전 값(divCheck.raw.pre)으로 같은 수를 세어 실패해요 · DART dy 가 0 이었다면 (어긋남
    없음) 그대로 통과해요."""
    cur, prev, a, b = raw_pair
    raw_in = copy.deepcopy(cur)
    picks = thirty_dash(cur, a, b)
    rep = check(cur, prev)
    row = rows_of(rep)[ODD_ROW]
    assert ODD_ROW in {r[0] for r in rep.failed} and row[1].startswith("어긋남 30 (1.2%)") and "비우기 전 값으로 센 30" in row[1], row
    # #179 전의 파이프라인이 같은 DART 입력으로 냈을 파일: 주당 배당 0 · dy 2.0 → 같은 수로 실패
    by = {s["t"]: s for s in raw_in["data"]["stocks"]}
    for s in picks:
        by[s["t"]].update(dps=0.0, dy=2.0)
    raw_in["data"]["divCheck"].pop("raw")
    row0 = rows_of(check(raw_in, prev))[ODD_ROW]
    assert row0[3] == "FAIL" and row0[1].startswith("어긋남 30 (1.2%)"), row0
    cur2, prev2, a2, b2 = None, None, None, None
    files, prev2, a2, b2 = (lambda c: (lambda f: (f[0], c[1], f[1], f[2]))(with_raw(c[0])))(good_pair())
    thirty_dash(files, a2, b2, dy=0.0)
    for s in files["data"]["stocks"]:
        if s["t"] in files["data"]["divCheck"]["raw"]["pre"] and s.get("dy") == 0.0:
            s.pop("dy")                                                            # 파이프라인처럼: 그 A 의 dy 0 ('-') 도 비워요
    row = rows_of(check(files, prev2))[ODD_ROW]
    assert row[3] == "PASS" and row[1].startswith("어긋남 0"), row


@pytest.mark.parametrize("change", [
    lambda d, c, a: d["divCheck"]["raw"]["contra"].update({a["t"]: [1]}),     # 기록이 올해를 비웠다고 하지 않음
    lambda d, c, a: c[a["t"]].update(cash3=[0.0, 1.0, 1.0]),                   # corp.json 의 그해 총액이 0
    lambda d, c, a: c[a["t"]].pop("cash3"),                                     # corp.json 에 총액이 없음
    lambda d, c, a: a.update(dps3=[300.0] + a["dps3"][1:]),                    # dps 는 없는데 dps3[0] 이 있음
])
def test_line_four_needs_a_blank_figure_the_record_and_a_positive_total(raw_pair, change):
    """리뷰 #179 (S1 · S3): nodps 는 세 가지가 모두 맞을 때만 줄 4 — 주당 배당이 비어 있고 · divCheck.raw.contra 가 올해를 비웠다고 하고 · corp.json 의
    그해 총액이 0 보다 커요. 하나라도 아니면 관문이 그 줄을 받지 않아요 (파일에 남으면 실패 · 파이프라인은 그 줄을 비워요)."""
    cur, prev, a, b = raw_pair
    cby = {c["t"]: c for c in cur["corp"]["companies"]}
    change(cur["data"], cby, a)
    rep = check(cur, prev)
    assert SUB_ROW in {r[0] for r in rep.failed}, rep.table()
    rows, _, want, _ = V.div_line_bad_rows([s for s in cur["data"]["stocks"] if s.get("cls") == "kr"], cur["data"]["divCheck"],
                                           comps=cur["corp"]["companies"])
    assert (a["t"], "shown") in [(r[0], r[2]) for r in rows] and a["t"] not in want and want[b["t"]] == 3


# ── 관문: 줄 4 와 기록 · 새 경고 줄 ─────────────────────────────
def with_raw(files, own=True):
    """좋은 픽스처에 파이프라인이 한 일을 그대로: A 한 곳 (0 인데 총액 → 모름 · nodps · 줄 4) · B 한 곳 (픽스처에서 주당 배당 ≥ 종가인 종목을
    주당 칸에 총액을 적은 회사로 · div · 줄 3).
    픽스처는 모든 회사에 총액 1억원을 줘서, 배당 없는 회사의 총액은 0 으로 (진짜 표처럼)."""
    files, _ = with_proof(files)
    data, corp = files["data"], files["corp"]
    kr = [s for s in data["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    by = {s["t"]: s for s in kr}
    for c in corp["companies"]:
        if (by[c["t"]].get("dps3") or [None])[0] == 0:
            c["cash3"] = [0.0, 0.0, 0.0]
    cby = {c["t"]: c for c in corp["companies"]}
    a = next(s for s in kr if s.get("divSt") == "same" and s["t"] not in V.MUST and s.get("dyt") and "dvProof" not in s and s["t"] in cby)
    b = next(s for s in kr if (s.get("dps") or 0) >= s["price"])
    raw = {"v": 1, "contra": {a["t"]: [0]}, "prefOnly": {}, "dpsBad": {b["t"]: [0]}, "dyBad": {}, "dyOk": 0, "dyNo": 0,
           "pre": {a["t"]: [0.0, None], b["t"]: [b["dps"], None]}}
    for s, ln in ((a, 4), (b, 3)):
        s.pop("dps")
        s["dps3"] = [None, s["dps3"][1], s["dps3"][2]]
        s.update(dps3a=[None] * 3, dpsF=[None] * 3, divSt="nd", dvLine=ln)
        s.pop("dyt", None), s.pop("dz", None)
        mirror(files, s)
        if s["t"] in cby:
            cby[s["t"]].pop("dps", None)
    proof = files["data"]["divCheck"]["proof"]
    recount(files)
    recount_why(files)
    proof.update(data=2, dataT=sorted([a["t"], b["t"]]))
    data["divCheck"].update(proof=proof, proofSub={"v": 1, "rights": {}, "data": {a["t"]: "nodps", b["t"]: "div"}}, raw=raw)
    if own:
        data["ownDrop"] = {"divLine": {"n": 0, "rows": []}}
    return files, a, b


@pytest.fixture
def raw_pair():
    cur, prev, _ = good_pair()
    files, a, b = with_raw(cur)
    return files, prev, a, b


def test_line_four_for_a_blanked_per_share_dividend_is_accepted_by_the_record_check(raw_pair):
    cur, prev, a, b = raw_pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    got = rows_of(rep)
    assert got[SUB_ROW][3] == "PASS" and "배당 자료 줄 1 · 빠진 자료 줄 1 · 줄 없음 0" in got[SUB_ROW][1], got[SUB_ROW]
    assert got[ROWS[0]][3] == "PASS", got[ROWS[0]]
    assert got[RAW_ROW][3] == "PASS" and "남은 해 없음" in got[RAW_ROW][1], got[RAW_ROW]
    assert got[PLAUS_ROW][3] == "PASS" and "벗어난 값 없음" in got[PLAUS_ROW][1], got[PLAUS_ROW]
    # 파이프라인의 같은 검사(own_blank_div_lines)도 줄을 그대로 둬요
    kr = [s for s in cur["data"]["stocks"] if s.get("cls") == "kr"]
    assert F.own_blank_div_lines(kr, cur["data"]["divCheck"]) == {"n": 0, "rows": []} and a["dvLine"] == 4 and b["dvLine"] == 3
    assert not check(cur, None, mode="live").failed


def test_line_four_on_a_stock_whose_per_share_dividend_still_shows_is_blanked_or_fails(raw_pair):
    """nodps 는 그 종목의 주당 배당이 정말 비었을 때만 줄 4 — 값이 남아 있으면 줄의 말이 틀려요: 파이프라인이 줄을 비우고 (ownDrop.divLine),
    파일에 남아 있으면 관문이 실패해요 (기존 상시 규칙 그대로)."""
    cur, prev, a, b = raw_pair
    a["dps"] = 500.0
    rows, _, want, _ = V.div_line_bad_rows([s for s in cur["data"]["stocks"] if s.get("cls") == "kr"], cur["data"]["divCheck"])
    assert [(r[0], r[2]) for r in rows] == [(a["t"], "shown")] and a["t"] not in want and want[b["t"]] == 3
    assert "줄 4 를 받을 수 없어요: 주당 배당이 있어요" in rows[0][1]
    rep = check(cur, prev)
    assert SUB_ROW in {r[0] for r in rep.failed}, rep.table()
    kr = [s for s in cur["data"]["stocks"] if s.get("cls") == "kr"]
    own = F.own_blank_div_lines(kr, cur["data"]["divCheck"])
    assert own["n"] == 1 and "dvLine" not in a and b["dvLine"] == 3
    cur["data"]["ownDrop"]["divLine"] = own
    rep = check(cur, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN", rep.table()


@pytest.mark.parametrize("change", [
    lambda d, a, b: d["divCheck"]["proofSub"]["data"].pop(a["t"]),                             # 기록 없이 줄 4 (dataT 와도 달라요)
    lambda d, a, b: (d["divCheck"]["proofSub"]["data"].pop(b["t"]), d["divCheck"]["proof"]["dataT"].remove(b["t"]),
                     d["divCheck"]["proof"].update(data=1)),                                      # 기록에서 빠진 B 에 줄 3
    lambda d, a, b: d["divCheck"]["proofSub"]["data"].update({a["t"]: "div"}),                    # 기록은 줄 3 인데 줄 4
    lambda d, a, b: d["divCheck"]["proofSub"]["data"].update({b["t"]: "nodps"}),                  # 기록은 줄 4 인데 줄 3
    lambda d, a, b: a.update(dvLine=3),
    lambda d, a, b: b.update(dvLine=4),
])
def test_a_line_on_a_blanked_per_share_dividend_that_no_record_backs_still_fails(raw_pair, change):
    """주당 배당을 비운 종목에도 기록이 정하지 않은 줄은 예전처럼 관문이 막아요 (파일에 남으면 실패)."""
    cur, prev, a, b = raw_pair
    change(cur["data"], a, b)
    rep = check(cur, prev)
    assert {SUB_ROW, ROWS[0]} & {r[0] for r in rep.failed}, rep.table()


def test_remaining_contradictions_and_unbelievable_values_only_warn(raw_pair):
    cur, prev, a, b = raw_pair
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    cby = {c["t"]: c for c in cur["corp"]["companies"]}
    z = next(s for s in cur["data"]["stocks"] if s.get("cls") == "kr" and s.get("dps") == 0 and s["t"] in cby and s["t"] not in V.MUST)
    cby[z["t"]]["cash3"] = [5.0, 0.0, 0.0]                                    # 0 인데 그해 총액 5억원이 남음
    y = next(s for s in cur["data"]["stocks"] if s.get("cls") == "kr" and s.get("divSt") == "same" and s.get("dyt") and s["t"] not in (a["t"],))
    y["dy"] = round(y["dyt"] * 10, 2)                                          # 오늘 기준 주당 배당 ÷ 52주 범위의 10배
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    got = rows_of(rep)
    assert got[RAW_ROW][3] == "WARN" and f"남은 해 1: {z['t']}" in got[RAW_ROW][1], got[RAW_ROW]
    assert got[PLAUS_ROW][3] == "WARN" and f"배당수익률 1: {y['t']}" in got[PLAUS_ROW][1], got[PLAUS_ROW]
    assert not check(cur, prev, mode="live").failed
    # 우선주 · 종류주만 받은 해로 적힌 0 은 이름을 적지 않아요
    cur["data"]["divCheck"]["raw"]["prefOnly"] = {z["t"]: [0]}
    got = rows_of(check(cur, prev))
    assert "남은 해 없음" in got[RAW_ROW][1] and "우선주 · 종류주만 받아 0 으로 둔 해 1" in got[RAW_ROW][1], got[RAW_ROW]
    # 기록은 비웠다는데 값이 있음 → 경고
    a["dps3"][0] = 100.0
    cur["data"]["divCheck"]["raw"]["dyBad"] = {y["t"]: 99.0}
    cur["data"]["divCheck"]["raw"]["pre"][y["t"]] = [y["dps"], 99.0]
    rep = check(cur, prev)
    got = rows_of(rep)
    assert RAW_ROW not in {r[0] for r in rep.failed} and "기록은 비웠다는데 값이 있음 1" in got[RAW_ROW][1] and got[RAW_ROW][3] == "WARN"
    assert "기록은 비웠다는데 배당수익률이 있음 1" in got[PLAUS_ROW][1] and got[PLAUS_ROW][3] == "WARN"


@pytest.mark.parametrize("change", [
    lambda d: d["divCheck"].pop("raw"),                                        # 이 기록 전 파일
    lambda d: d["divCheck"].update(raw={"v": 2}),
    lambda d: d["divCheck"].update(raw={"v": 1, "contra": {"005930": [3]}, "prefOnly": {}, "dpsBad": {}, "dyBad": {}, "dyOk": 0, "dyNo": 0, "pre": {}}),
    lambda d: d["divCheck"].update(raw=[]),
    lambda d: d["divCheck"]["raw"].pop("pre"),                                 # 비우기 전 값이 없음
    lambda d: d["divCheck"]["raw"]["pre"].pop(sorted(d["divCheck"]["raw"]["contra"])[0]),   # 비운 종목이 pre 에 없음
])
def test_a_missing_or_malformed_record_only_warns_in_the_new_rows(raw_pair, change):
    """새 두 줄은 경고만. 기록이 있는데 모양이 틀리면 '주당 배당금·배당수익률 맞음' 줄은 비우기 전 값으로 셀 수 없어 실패해요 (#179 전보다 받아들이는
    것이 없게 · 기록이 아예 없는 파일은 비운 것이 없어서 예전 그대로)."""
    cur, prev, a, b = raw_pair
    gone = "raw" in cur["data"]["divCheck"]
    change(cur["data"])
    rep = check(cur, prev)
    got = rows_of(rep)
    assert RAW_ROW not in {r[0] for r in rep.failed} and PLAUS_ROW not in {r[0] for r in rep.failed}, rep.table()
    assert got[RAW_ROW][3] == "WARN" and got[PLAUS_ROW][3] == "WARN"
    odd_failed = ODD_ROW in {r[0] for r in rep.failed}
    assert odd_failed is ("raw" in cur["data"]["divCheck"]), (got[ODD_ROW], gone)


def test_the_new_rows_only_warn_when_the_check_itself_crashes(raw_pair, monkeypatch):
    cur, prev, a, b = raw_pair

    def boom(*a, **k):
        raise ZeroDivisionError("시험")
    monkeypatch.setattr(V, "_check_div_raw", boom)
    for mode in ("publish", "live"):
        rep = check(cur, prev, mode=mode)
        got = rows_of(rep)
        assert not rep.failed, rep.table()
        assert all(got[n][3] == "WARN" and "검사가 오류로 멈췄어요: ZeroDivisionError" in got[n][1] for n in (RAW_ROW, PLAUS_ROW))


def test_the_pipeline_runs_the_guards_around_the_split_check_and_writes_the_record():
    """main: div_raw_guard 는 apply_div_basis 앞 (그 해의 주당 배당 없이 수익률 · 순위를 셈) · div_dy_guard 는 뒤 (dps3a · dpsF) · 기록은 divCheck.raw ·
    두 단계가 멈춰도 발행은 이어가요 (크게 남기고 기록 없이 → 관문 경고). 고르는 함수는 관문 파일의 것 하나."""
    assert F.div_zero_contra is V.div_zero_contra and F.dps_far_years is V.dps_far_years and F.dy_far is V.dy_far and F.dy_base is V.dy_base
    assert F.PROVE_SUB == V.PROVE_SUB and F.PROVE_SUB_LINE == V.PROVE_SUB_LINE and F.PROVE_SUB_KO == V.PROVE_SUB_KO
    src = inspect.getsource(F.main)
    i_raw, i_basis, i_dy = src.index("div_raw_guard(kr,"), src.index("apply_div_basis(kr, fin_map"), src.index("div_dy_guard(kr, div_raw, px=px_date)")
    assert src.index("blank_foreign_dart(kr)") < i_raw < i_basis < src.index('div_counts["raw"] = div_raw') < i_dy < src.index("add_percentiles(kr)")
    assert src.count("except Exception as e:") >= 2


def test_crashed_guards_leave_the_old_values_and_no_record():
    """div_raw_guard 가 멈추면 main 은 예전 값 그대로 발행을 이어가요 — 그때 apply_div_basis 는 _divRaw 없이 예전처럼 (줄 없음)."""
    s = stock("011760", HYUNDAI_CORP, 21750.0, 13228966)
    counts, _ = F.apply_div_basis([s], {}, {}, why=F.DivWhy(None, PX))
    assert s["dps"] == 0 and s["dyt"] == 0.0 and "dvLine" not in s and "raw" not in counts


def test_no_new_korean_ui_text():
    """새 화면 문구 없음: 줄 4 는 Jack 이 2026-11-19 에 승인한 그대로 (src 는 바꾸지 않아요)."""
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as f:
        src = f.read()
    assert src.count("회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요.") == 1
