# -*- coding: utf-8 -*-
"""2026-11-23 · DART 배당 표 안의 어긋남과 그럴듯하지 않은 값 (네트워크 없음 · 2026-11-21 발행본 감사).

A. 한 해의 배당 표에 현금배당금총액은 있는데 보통주 주당 현금배당금이 0 ('-') 이면 그해 보통주 배당은 '모름' (빈 칸) 이에요 — 0 (배당 없음) 이
   아니에요. 우선주 · 종류주가 총액을 다 받은 해만 0 이 맞아요. 올해 것을 비운 배당 회사는 증명의 data (nodps) 에 적혀 줄 4 를 받아요.
B. 주당 칸의 값이 주당 금액이 아닌 해 (총액의 1,000배 넘게 · 올해가 종가 이상 — 와이엔텍) 는 그해 주당 배당을 비우고 (올해면 baddps · 줄 4),
   DART 배당수익률(dy)이 오늘 기준 주당 배당 ÷ 52주 범위에서 3배 넘게 벗어나면 비워요 (흥국 56.0 · 지투파워 33.7 · 아비코전자 30.0 · 알피바이오 10.0).
관문: 새 줄 둘은 경고만 (검사가 멈춰도) · nodps · baddps 는 그 종목의 주당 배당이 정말 비었을 때만 줄 4 를 받아요.

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
RAW_ROW, PLAUS_ROW = V.DIV_RAW_ROW, V.DIV_PLAUS_ROW


def _load(name):
    with open(os.path.join(ROOT, "tests", "fixtures", "dvproof", name), encoding="utf-8") as f:
        return json.load(f)


def stock(t, rows, price, shr, hi=None, lo=None, fy=2025, nk=""):
    """parse_dart_dividend (캐시가 담는 해석) 그대로 종목에 붙여요 — enrich_with_dart 와 같은 칸."""
    div = F.parse_dart_dividend(rows)
    s = {"t": t, "nk": nk, "cls": "kr", "price": price, "shr": shr, "fy": fy, "hi": hi or price, "lo": lo or price}
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
    counts, _ = F.apply_div_basis(stocks, {}, pref, why=why)
    counts["raw"] = F.div_dy_guard(stocks, rec)
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
    """상장되지 않은 종류(상환전환우선주 등)가 받았으면 그해 말 주식의 총수 현황의 우선주 · 종류주 수로만 (올해만) · 없으면 모름."""
    paid = [[300.0, 0.0, 0.0]]
    assert V.div_zero_contra([0, 0, 0], [3e8, 0, 0], paid, (), pfo=1_000_000) == ([], [0])
    assert V.div_zero_contra([0, 0, 0], [3e8, 0, 0], paid, (), pfo=None) == ([0], [])
    assert V.div_zero_contra([0, 0, 0], [0, 0, 3e8], [[0.0, 0.0, 300.0]], (), pfo=1_000_000) == ([2], [])   # 앞 해는 그해 말 수가 없어요
    assert V.div_zero_contra([0, 0, 0], [3e8, 0, 0], [[300.0, 0, 0], [0.0, 0, 0]], (), pfo=1_000_000) == ([0], [])   # 받지 않은 종류가 섞임
    # 상장 우선주: 가장 적은 ~ 가장 많은 종목 수 × 주당 배당 ± 15%
    assert V.pref_explains(5.6e8, [500.0], [1_000_000, 2_000_000]) and V.pref_explains(1.15e9, [500.0], [1_000_000, 2_000_000])
    assert not V.pref_explains(1.2e9, [500.0], [1_000_000, 2_000_000]) and not V.pref_explains(4e8, [500.0], [1_000_000, 2_000_000])
    assert not V.pref_explains(5e8, [], [1_000_000]) and not V.pref_explains(0, [500.0], [1_000_000])


def test_the_real_dart_samples_in_the_fixtures_are_unchanged():
    """v19.1i · v19.1j 의 실제 OpenDART 응답 41곳: 와이엔텍 말고는 하나도 바뀌지 않아요 (0 인데 총액이 있는 해 · 1,000배 넘는 주당 배당 · 종가 이상 없음)."""
    cases = {**_load("cases.json")["cases"], **_load("cases_1115.json")["cases"]}
    hit = {}
    for t, c in cases.items():
        b = c.get("bas") or {}
        contra, po = V.div_zero_contra(c["s"]["dps3"], b.get("cash3"), b.get("pdps") or (), c.get("pref") or ())
        far = V.dps_far_years(c["s"]["dps3"], b.get("cash3"), c["s"].get("shr"), c["s"].get("price"))
        if contra or po or far:
            hit[t] = (contra, po, far)
    assert hit == {"067900": ([], [], [0, 1, 2])}


# ── B. 주당 칸의 값이 주당 금액이 아님 · 그럴듯하지 않은 배당수익률 ────────────
def test_a_total_written_in_the_per_share_cell_is_blanked_with_line_four():
    """와이엔텍 067900: 주당 칸에 총액 (1,809,965,900원 · 총액 18.09억원) → 세 해 모두 비우고 줄 4 (baddps). 예전에는 증명이 '배당 표가 주식 수와
    어긋남'(줄 3)으로 숨겼어요 — 그 계산은 이제 주당 배당 없이는 돌지 않아요."""
    c = _load("cases_1115.json")["cases"]["067900"]
    s = {**copy.deepcopy(c["s"]), "cls": "kr", "t": "067900", "_bas": copy.deepcopy(c["bas"]), "dps": c["s"]["dps3"][0]}
    by, counts = run([s])
    s = by["067900"]
    assert "dps" not in s and "dps3" not in s and "divSt" not in s and s["dvLine"] == 4
    assert counts["raw"]["dpsBad"] == {"067900": [0, 1, 2]} and counts["proofSub"]["data"] == {"067900": "baddps"}


def test_split_sized_ratios_and_pre_listing_dividends_are_kept():
    """2026-11-21 의 맞는 값: 분할 · 무상증자 · 상장 전 해는 주당 배당 × 오늘 주식 수 ÷ 총액이 70배 아래 (위너스일렉 2023 29,412원 · 69.9배)."""
    assert V.dps_far_years([1085, 2160, 1615], [65e8, 129.4e8, 96.75e8], 60_000_000, 1500.0) == []          # 포스코스틸리온 ×10
    assert V.dps_far_years([0, 0, 29412], [0, 0, 30e8], 7_126_000, 4990.0) == []                             # 위너스일렉 (앞 해는 종가와 견주지 않아요)
    assert V.dps_far_years([1809965900, 1266976130, 904982950], [18.09e8, 12.66e8, 9.04e8], 18199659, 5440.0) == [0, 1, 2]
    assert V.dps_far_years([6000, 0, 0], [None, None, None], 1_000_000, 5440.0) == [0]                        # 올해 주당 배당 ≥ 종가
    assert V.dps_far_years([5000, 0, 0], [None, None, None], 1_000_000, 5440.0) == []
    # 50:1 분할 뒤의 옛 기준 주당 배당 (2,500원 ≥ 종가 2,000원): 총액이 주식 수가 50배 늘었다고 말해요 → 분할 확인이 맞춰요 (비우지 않아요)
    assert V.dps_far_years([2500, 2000, 1500], [25e8, 20e8, 15e8], 50_000_000, 2000.0) == []
    assert V.dps_far_years([2500, 2000, 1500], [25e8 * 50, 20e8, 15e8], 50_000_000, 2000.0) == [0]       # 같은 기준인데 종가 이상


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


# ── 관문: 줄 4 와 기록 · 새 경고 줄 ─────────────────────────────
def with_raw(files, own=True):
    """좋은 픽스처에 파이프라인이 한 일을 그대로: A 한 곳 (0 인데 총액 → 모름 · nodps) · B 한 곳 (픽스처에서 주당 배당 ≥ 종가인 종목 → baddps).
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
    raw = {"v": 1, "contra": {a["t"]: [0]}, "prefOnly": {}, "dpsBad": {b["t"]: [0]}, "dyBad": {}, "dyOk": 0, "dyNo": 0}
    for s in (a, b):
        s.pop("dps")
        s["dps3"] = [None, s["dps3"][1], s["dps3"][2]]
        s.update(dps3a=[None] * 3, dpsF=[None] * 3, divSt="nd", dvLine=4)
        s.pop("dyt", None), s.pop("dz", None)
        mirror(files, s)
        if s["t"] in cby:
            cby[s["t"]].pop("dps", None)
    proof = files["data"]["divCheck"]["proof"]
    recount(files)
    recount_why(files)
    proof.update(data=2, dataT=sorted([a["t"], b["t"]]))
    data["divCheck"].update(proof=proof, proofSub={"v": 1, "rights": {}, "data": {a["t"]: "nodps", b["t"]: "baddps"}}, raw=raw)
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
    assert got[SUB_ROW][3] == "PASS" and "빠진 자료 줄 2" in got[SUB_ROW][1], got[SUB_ROW]
    assert got[ROWS[0]][3] == "PASS", got[ROWS[0]]
    assert got[RAW_ROW][3] == "PASS" and "남은 해 없음" in got[RAW_ROW][1], got[RAW_ROW]
    assert got[PLAUS_ROW][3] == "PASS" and "벗어난 값 없음" in got[PLAUS_ROW][1], got[PLAUS_ROW]
    # 파이프라인의 같은 검사(own_blank_div_lines)도 줄을 그대로 둬요
    kr = [s for s in cur["data"]["stocks"] if s.get("cls") == "kr"]
    assert F.own_blank_div_lines(kr, cur["data"]["divCheck"]) == {"n": 0, "rows": []} and a["dvLine"] == 4 and b["dvLine"] == 4
    assert not check(cur, None, mode="live").failed


def test_line_four_on_a_stock_whose_per_share_dividend_still_shows_is_blanked_or_fails(raw_pair):
    """nodps · baddps 는 그 종목의 주당 배당이 정말 비었을 때만 줄 4 — 값이 남아 있으면 줄의 말이 틀려요: 파이프라인이 줄을 비우고 (ownDrop.divLine),
    파일에 남아 있으면 관문이 실패해요 (기존 상시 규칙 그대로)."""
    cur, prev, a, b = raw_pair
    a["dps"] = 500.0
    rows, _, want, _ = V.div_line_bad_rows([s for s in cur["data"]["stocks"] if s.get("cls") == "kr"], cur["data"]["divCheck"])
    assert [(r[0], r[2]) for r in rows] == [(a["t"], "shown")] and a["t"] not in want and want[b["t"]] == 4
    assert "주당 배당을 비운 종목인데 주당 배당이 있어요" in rows[0][1]
    rep = check(cur, prev)
    assert SUB_ROW in {r[0] for r in rep.failed}, rep.table()
    kr = [s for s in cur["data"]["stocks"] if s.get("cls") == "kr"]
    own = F.own_blank_div_lines(kr, cur["data"]["divCheck"])
    assert own["n"] == 1 and "dvLine" not in a and b["dvLine"] == 4
    cur["data"]["ownDrop"]["divLine"] = own
    rep = check(cur, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN", rep.table()


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
    rep = check(cur, prev)
    got = rows_of(rep)
    assert RAW_ROW not in {r[0] for r in rep.failed} and "기록은 비웠다는데 값이 있음 1" in got[RAW_ROW][1] and got[RAW_ROW][3] == "WARN"
    assert "기록은 비웠다는데 배당수익률이 있음 1" in got[PLAUS_ROW][1] and got[PLAUS_ROW][3] == "WARN"


@pytest.mark.parametrize("change", [
    lambda d: d["divCheck"].pop("raw"),                                        # 이 기록 전 파일
    lambda d: d["divCheck"].update(raw={"v": 2}),
    lambda d: d["divCheck"].update(raw={"v": 1, "contra": {"005930": [3]}, "prefOnly": {}, "dpsBad": {}, "dyBad": {}, "dyOk": 0, "dyNo": 0}),
    lambda d: d["divCheck"].update(raw=[]),
])
def test_a_missing_or_malformed_record_only_warns(raw_pair, change):
    cur, prev, a, b = raw_pair
    change(cur["data"])
    rep = check(cur, prev)
    got = rows_of(rep)
    assert RAW_ROW not in {r[0] for r in rep.failed} and PLAUS_ROW not in {r[0] for r in rep.failed}, rep.table()
    assert got[RAW_ROW][3] == "WARN" and got[PLAUS_ROW][3] == "WARN"


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
    i_raw, i_basis, i_dy = src.index("div_raw_guard(kr,"), src.index("apply_div_basis(kr, fin_map"), src.index("div_dy_guard(kr, div_raw)")
    assert src.index("blank_foreign_dart(kr)") < i_raw < i_basis < i_dy < src.index("add_percentiles(kr)")
    assert 'div_counts["raw"] = div_dy_guard(kr, div_raw)' in src and src.count("except Exception as e:") >= 2


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
