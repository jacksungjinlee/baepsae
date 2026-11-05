# -*- coding: utf-8 -*-
"""v19.1b 데이터 (네트워크 없음): 분할에 안전한 국내 배당 · 베타 표준오차 · flRan · 배당 순위 · DART 캐시 v2 · 새 관문 줄.

실제 숫자 픽스처는 2026-11-05 에 DART 에서 직접 받은 2025 사업보고서의 '배당에 관한 사항'(alotMatter)·재무제표 자본금과
그날 발행본(data.json, pxDate 2026-11-04)의 상장 주식 수예요. 분할 근거 공시: 대한제분 주식분할결정 2026-03-12
(20260312802368) · 리노공업 주식분할결정 2025-02-11 (20250211900303) · 엠앤씨솔루션 주요사항보고서(무상증자결정)
2026-06-12 (20260612000174) · 하이비젼시스템은 같은 기간 분할·증자 공시가 없어요 (진짜 감소)."""
import copy
import datetime as dt
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
OCT = [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)]
SESSIONS = {"dates": OCT, "src": "시험"}


# ── 배당 표 행 만들기 ──────────────────────────────────────
def _fmt(v):
    if v is None:
        return "-"
    return f"{v:,.2f}" if isinstance(v, float) and not float(v).is_integer() else f"{int(v):,}"


def alot(dps, cash=None, par=None, eps=None, ni=None, pdps=None, dy=None, basis="연결", pref_kind="우선주"):
    """alotMatter 응답의 list (당기·전기·전전기). cash·ni 는 백만원, 나머지는 원."""
    def row(se, vals, knd="-"):
        vals = list(vals) + [None] * 3
        return {"se": se, "stock_knd": knd, "thstrm": _fmt(vals[0]), "frmtrm": _fmt(vals[1]), "lwfr": _fmt(vals[2]),
                "stlm_dt": "2025-12-31"}
    out = []
    if par is not None:
        out.append(row("주당액면가액(원)", par))
    if ni is not None:
        out.append(row(f"({basis})당기순이익(백만원)", ni))
    if eps is not None:
        out.append(row(f"({basis})주당순이익(원)", eps))
    if cash is not None:
        out.append(row("현금배당금총액(백만원)", cash))
    if dy is not None:
        out.append(row("현금배당수익률(%)", dy, "보통주"))
    out.append(row("주당 현금배당금(원)", dps, "보통주"))
    if pdps is not None:
        out.append(row("주당 현금배당금(원)", pdps, pref_kind))
    return out


def basis_of(rows, cs3, shr, prefs=()):
    div = F.parse_dart_dividend(rows)
    return div, F.div_basis(div["dps3"], div.get("bas"), cs3, shr, prefs)


# ── 1. 배당 표 읽기 ────────────────────────────────────────
SAMSUNG = alot([1668, 1446, 1444], cash=[11107906, 9810767, 9809438], par=[100, 100, 100], eps=[6605, 4950, 2131],
               ni=[44260956, 33621363, 14473401], pdps=[1669, 1447, 1445], dy=[1.5, 2.7, 1.9])


def test_dividend_table_keeps_totals_eps_and_par_for_each_year():
    got = F.parse_dart_dividend(SAMSUNG)
    assert got["dps"] == 1668 and got["dps3"] == [1668, 1446, 1444] and got["dy"] == 1.5      # 예전 칸은 그대로
    b = got["bas"]
    assert b["cash3"] == [11107906e6, 9810767e6, 9809438e6]           # 백만원 → 원
    assert b["ni3"] == [44260956e6, 33621363e6, 14473401e6] and b["eps3"] == [6605, 4950, 2131] and b["epsB"] == "연결"
    assert b["par3"] == [100, 100, 100] and b["pdps3"] == [1669, 1447, 1445]
    assert set(b) == {"cash3", "ni3", "eps3", "epsB", "par3", "pdps3"}            # 캐시에 쓰지 않는 칸은 담지 않아요


def test_dividend_table_reads_separate_basis_class_shares_and_dashes():
    rows = alot([800, 3000, 3000], cash=[60716, 45537, 45537], par=[100, 500, 500], eps=[2002, 7463, 7308],
                ni=[151961, 113279, 110923], basis="별도")
    rows.append({"se": "주당 현금배당금(원)", "stock_knd": "-", "thstrm": "-", "frmtrm": "-", "lwfr": "-"})   # 리노공업: 빈 둘째 줄
    b = F.parse_dart_dividend(rows)["bas"]
    assert b["epsB"] == "별도" and "pdps3" not in b                  # 종류 칸 '-' 줄은 우선주가 아니에요
    naver = alot([2630, 1130, 1205], cash=[393596, 168437, 181383], par=[100] * 3, pdps=[None, None, None], pref_kind="종류주")
    assert F.parse_dart_dividend(naver)["bas"]["pdps3"] == [0.0, 0.0, 0.0]     # 종류주 '-' = 배당 없음
    loss = alot([0, 0, 0], cash=[None, None, None], par=[5000] * 3, eps=[-15188, None, 48718], ni=[-25264, None, 81201])
    b = F.parse_dart_dividend(loss)["bas"]
    assert b["cash3"] == [0.0, 0.0, 0.0] and b["eps3"] == [-15188, None, 48718] and b["ni3"][1] is None   # 이익의 '-' 는 모름


def test_table_without_basis_rows_gives_no_basis():
    rows = [{"stock_knd": "보통주", "se": "주당 현금배당금(원)", "thstrm": "371", "frmtrm": "-", "lwfr": "-"},
            {"stock_knd": "상환전환우선주", "se": "주당 현금배당금(원)", "thstrm": "999", "frmtrm": "-", "lwfr": "-"}]
    assert F.parse_dart_dividend(rows) == {"dps": 371.0, "dps3": [371.0, 0.0, 0.0]}


def test_financial_statements_keep_three_years_of_capital_stock():
    rows = [{"account_nm": "자본금", "sj_div": "BS", "thstrm_amount": "270317005000", "frmtrm_amount": "240405805000",
             "bfefrmtrm_amount": "265650000000"},
            {"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": "1000000000", "frmtrm_amount": "900000000",
             "bfefrmtrm_amount": "800000000"}]
    fin = F.parse_dart_list(rows)["_fin"]
    assert fin["cs"] == 2703.2 and fin["cs3"] == [2703.1701, 2404.0581, 2656.5]


# ── 2. 분할 확인 (Jack 의 픽스처 여섯 가지 + 실제 회사) ────────
CS50 = [50.0, 50.0, 50.0]          # 자본금 50억원 = 액면 5,000원 × 100만 주


def test_split_one_to_two_inside_the_report_is_flat_with_factor_two():
    # 1:2 분할(액면 5,000 → 2,500)이 당기 중에: 주당 배당금 2,000 → 1,000, 주식 수 두 배, 회사가 주는 총액은 같아요
    div, r = basis_of(alot([1000, 2000, 2000], cash=[2000, 2000, 2000], par=[2500, 5000, 5000]), CS50, 2_000_000)
    assert r["dps3a"] == [1000, 1000, 1000] and r["dpsF"] == [1.0, 2.0, 2.0] and r["divSt"] == "adj"


def test_split_after_the_report_adjusts_every_year_and_todays_yield():
    # 보고서 뒤(올해) 1:2 분할: 보고서 세 해 모두 옛 기준 → 모두 2 로 나눠요 (앱의 1.8배 임시 가드가 숨기던 경우)
    div, r = basis_of(alot([2000, 2000, 2000], cash=[2000, 2000, 2000], par=[5000] * 3), CS50, 2_000_000)
    assert r["dps3a"] == [1000, 1000, 1000] and r["dpsF"] == [2.0, 2.0, 2.0] and r["f0"] == 2.0 and r["divSt"] == "adj"


def test_company_restated_last_year_but_not_the_year_before():
    # 당기 중 1:2 분할, 전기 주당 배당금은 회사가 새 기준으로 고쳐 적었고(1,000) 전전기는 옛 기준 그대로(2,000)
    div, r = basis_of(alot([1000, 1000, 2000], cash=[2000, 2000, 2000], par=[2500, 5000, 5000]), CS50, 2_000_000)
    assert r["dps3a"] == [1000, 1000, 1000] and r["dpsF"] == [1.0, 1.0, 2.0] and r["divSt"] == "adj"


def test_real_cut_with_unchanged_shares_stays_a_cut():
    div, r = basis_of(alot([1000, 2000, 2000], cash=[1000, 2000, 2000], par=[5000] * 3), CS50, 1_000_000)
    assert r["dps3a"] == [1000, 2000, 2000] and r["dpsF"] == [1.0, 1.0, 1.0] and r["divSt"] == "same"


def test_rights_issue_of_thirty_percent_is_not_comparable():
    # 당기 중 유상증자로 주식 ×1.3: 전기·전전기와 비교하지 않아요 (추측한 배율로 맞추지 않아요). 당기·오늘은 같은 기준이라 수익률은 있어요
    div, r = basis_of(alot([1000, 1000, 1000], cash=[1300, 1000, 1000], par=[5000] * 3), [65.0, 50.0, 50.0], 1_300_000)
    assert r["dps3a"] == [1000, None, None] and r["dpsF"] == [1.0, None, None] and r["divSt"] == "nc"
    # 보고서 뒤 ×1.3: 오늘 수익률도 확인 못 해요
    div, r = basis_of(alot([1000, 1000, 1000], cash=[1000, 1000, 1000], par=[5000] * 3), CS50, 1_300_000)
    assert r["dps3a"] == [None, None, None] and r["divSt"] == "nc" and r["f0"] is None


def test_missing_eps_is_not_derivable():
    # 올해 배당이 없고 예전엔 있었어요: 오늘 ÷ 당기 기준은 순이익 ÷ 주당순이익으로만 셀 수 있는데 주당순이익이 비었어요
    rows = alot([0, 500, 500], cash=[0, 500, 500], par=[5000] * 3, eps=[None, 600, 550], ni=[-300, 600, 550])
    div, r = basis_of(rows, CS50, 1_000_000)
    assert r["divSt"] == "nd" and r["dps3a"] == [0.0, None, None] and r["st3"] == ["zero", "nd", "nd"]
    # 주당순이익이 있으면 셀 수 있어요 (순이익 −3억 ÷ 주당순이익 −300원 = 100만 주)
    rows = alot([0, 500, 500], cash=[0, 500, 500], par=[5000] * 3, eps=[-300, 600, 550], ni=[-300, 600, 550])
    div, r = basis_of(rows, CS50, 1_000_000)
    assert r["divSt"] == "same" and r["dps3a"] == [0.0, 500, 500]
    # 배당한 해에 총액이 없으면 그해 기준도 알 수 없어요 (주당순이익으로 대신하지 않아요)
    div, r = basis_of(alot([1000, 1000, 1000], cash=[None, 1000, 1000], par=[5000] * 3), CS50, 1_000_000)
    assert r["divSt"] == "nd" and r["dps3a"] == [None, None, None]


def test_non_payer_is_zero_and_needs_no_share_count():
    div, r = basis_of(alot([0, 0, 0], cash=[None] * 3, par=[5000] * 3), None, 1_000_000)
    assert r["divSt"] == "zero" and r["dps3a"] == [0.0, 0.0, 0.0] and r["dpsF"] == [None] * 3


HYUNDAI = alot([10000, 12000, 11400], cash=[2618263, 3147839, 2998657], par=[5000] * 3, pdps=[10100, 12100, 11500])
HYUNDAI_PREFS = (22_839_037, 34_257_047, 2_321_926)


def test_company_with_preferred_shares_counts_them_in_the_total():
    # 현대차: 현금배당금총액에 우선주 세 종류의 배당도 들어 있어요. 우선주 상장 주식 수를 넣어야 '그대로'로 나와요
    cs = [14889.93] * 3
    div, r = basis_of(HYUNDAI, cs, 203_466_492, HYUNDAI_PREFS)
    assert r["divSt"] == "same" and r["dps3a"] == [10000, 12000, 11400] and 0.88 < r["lo"] < 1.0 < r["hi"] < 1.01
    div, r = basis_of(HYUNDAI, cs, 203_466_492, ())          # 우선주를 빼먹으면 확인하지 못해요 (틀린 배율을 쓰지 않아요)
    assert r["dpsF"][0] is None and r["divSt"] in ("nc", "nd")


def test_preferred_share_ticker_is_skipped_and_counted():
    kr = [{"t": "005935", "nk": "삼성전자우", "cls": "kr", "price": 171700.0, "shr": 802371203},
          {"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 218000.0, "shr": 5846278608,
           "dps3": [1668.0, 1446.0, 1444.0], "_bas": F.parse_dart_dividend(SAMSUNG)["bas"]}]
    counts, extra = F.apply_div_basis(kr, {"005930": {"cs3": [8975.14] * 3}}, {"00593": [802371203]})
    pref, com = kr
    assert not {"dps3a", "dpsF", "divSt", "dyt", "_bas"} & set(pref) and "_bas" not in com
    assert com["divSt"] == "same" and com["dyt"] == round(1668 / 218000 * 100, 2)
    assert counts["pref"] == 1 and counts["same"] == 1 and counts["payers"] == 1 and counts["dyt"] == 1
    assert extra["005930"]["cash3"] == [111079.06, 98107.67, 98094.38] and extra["005930"]["eps3r"] == [6605, 4950, 2131]
    assert extra["005930"]["epsNi3"] == [442609.56, 336213.63, 144734.01] and extra["005930"]["epsB"] == "연결"


def test_high_treasury_without_a_split_is_never_read_as_a_split():
    # 자기주식 50%: 배당 받은 주식이 상장 주식의 절반 → '오늘 ÷ 배당 받은 주식'만 보면 2:1 분할처럼 보여요. 범위에 1 과 2 가
    # 함께 걸쳐서 '알 수 없음'이에요 (배율 2 로 맞추지 않아요)
    div, r = basis_of(alot([1000] * 3, cash=[500] * 3, par=[5000] * 3), CS50, 1_000_000)
    assert r["f0"] is None and r["divSt"] == "nd" and r["dps3a"] == [None, None, None]


def test_total_filed_in_the_per_share_row_is_not_derivable():
    # 와이엔텍처럼 주당 배당금 칸에 총액을 적은 표: 배당 받은 주식이 1주로 계산돼 범위가 터무니없이 넓어요
    div, r = basis_of(alot([1809965900, 1266976130, 904982950], cash=[1810, 1267, 905], par=[500] * 3), [56.0] * 3, 11_200_000)
    assert r["divSt"] == "nd" and r["dps3a"] == [None, None, None]


@pytest.mark.parametrize("name, rows, cs3, shr, want_a, want_f, want_st", [
    # 대한제분: 2026-03-12 주식분할결정 (10:1) — 보고서 세 해 모두 옛 기준
    ("대한제분", alot([4000, 3500, 2500], cash=[6599, 5774, 4113], par=[5000] * 3, eps=[-15188, 29257, 48718],
                   ni=[-25264, 48743, 81201]), [84.5] * 3, 16_900_000, [400, 350, 250], [10.0, 10.0, 10.0], "adj"),
    # 리노공업: 2025-02-11 주식분할결정 (5:1, 액면 500 → 100) — 전기·전전기는 회사가 옛 기준 그대로 적었어요
    ("리노공업", alot([800, 3000, 3000], cash=[60716, 45537, 45537], par=[100, 500, 500]), [76.2118] * 3, 76_211_850,
     [800, 600, 600], [1.0, 5.0, 5.0], "adj"),
    # 엠앤씨솔루션: 2026-06-12 무상증자결정 (×3) — 전전기는 상장 전 액면분할·공모라 어중간한 배율 → 비교 불가
    ("엠앤씨솔루션", alot([2491, 1480, 2185], cash=[22802, 13548, 20000], par=[100, 100, 5000]), [9.1539, 9.1539, 5.3026],
     27_461_700, [830.33, 493.33, None], [3.0, 3.0, None], "nc"),
    # 하이비젼시스템: 분할·증자 공시 없음 — 진짜 감소는 감소로 남아요 (자기주식 14%)
    ("하이비젼시스템", alot([80, 400, 500], cash=[1028, 5007, 6420], par=[500] * 3), [74.7106] * 3, 14_942_112,
     [80, 400, 500], [1.0, 1.0, 1.0], "same"),
    # 한화에어로스페이스 (필수 종목): 2024 인적분할 감자·2025 유상증자 → 전기는 비교 불가, 오늘 수익률(당기)은 확인돼요
    ("한화에어로스페이스", alot([7000, 3500, 1800], cash=[360142, 159133, 91025], par=[5000] * 3),
     [2703.1701, 2404.0581, 2656.5], 51_563_401, [7000, None, 1800], [1.0, None, 1.0], "nc"),
])
def test_real_companies_from_dart(name, rows, cs3, shr, want_a, want_f, want_st):
    div, r = basis_of(rows, cs3, shr)
    assert r["dps3a"] == want_a and r["dpsF"] == want_f and r["divSt"] == want_st, (name, r)


@pytest.mark.parametrize("t, rows, cs3, shr, prefs", [
    ("005930", SAMSUNG, [8975.14] * 3, 5_846_278_608, (802_371_203,)),
    ("005380", HYUNDAI, [14889.93] * 3, 203_466_492, HYUNDAI_PREFS),
    ("000660", alot([3000, 2204, 1200], cash=[2095133, 1520090, 825721], par=[5000] * 3), [36576.52] * 3, 730_492_365, ()),
    ("105560", alot([4367, 3174, 3060], cash=[1577774, 1198257, 1173937], par=[5000] * 3), [20905.58] * 3, 354_687_734, ()),
    ("015760", alot([1542, 213, 0], cash=[989909, 136738, None], par=[5000] * 3), [32098.2] * 3, 641_964_077, ()),
    ("035420", alot([2630, 1130, 1205], cash=[393596, 168437, 181383], par=[100] * 3), [164.8134] * 3, 152_108_892, ()),
])
def test_must_have_companies_keep_their_dividend_unchanged(t, rows, cs3, shr, prefs):
    # 필수 종목은 실제 2025 사업보고서로 모두 '그대로' (배당 순위에 꼭 들어가야 해요)
    div, r = basis_of(rows, cs3, shr, prefs)
    assert r["divSt"] == "same" and r["dpsF"][0] == 1.0 and r["dps3a"] == [x if x else 0.0 for x in div["dps3"]], (t, r)


def test_clean_factors_and_bands():
    assert F.clean_factor(1.08) == 1.0 and F.clean_factor(1.3) is None and F.clean_factor(2.04) == 2.0
    assert F.clean_factor(2.3) is None and F.clean_factor(0.505) == 0.5 and F.clean_factor(None) is None
    assert F.factor_between(0.74, 0.999) == (1.0, "ok")              # 삼성전자 (이익소각으로 자본금 ÷ 액면가가 커요)
    assert F.factor_between(1.25, 1.35) == (None, "nc") and F.factor_between(1.0, 2.0) == (None, "nd")
    assert F.factor_between(None, 1.0) == (None, "nd") and F.factor_between(2.0, 1.0) == (None, "nd")
    bands = sorted(F._factor_band(c) for c in F.DIV_FACTORS)
    assert all(a[1] < b[0] for a, b in zip(bands, bands[1:]))         # 후보끼리 겹치지 않아요 (2 와 2.5, 2.5 와 3 …)


def test_apply_writes_todays_yield_only_from_a_verified_dividend(capsys):
    kr = [{"t": "001130", "nk": "대한제분", "cls": "kr", "price": 10680.0, "shr": 16_900_000, "dps3": [4000.0, 3500.0, 2500.0],
           "_bas": F.parse_dart_dividend(alot([4000, 3500, 2500], cash=[6599, 5774, 4113], par=[5000] * 3))["bas"]},
          {"t": "000010", "nk": "자기주식많음", "cls": "kr", "price": 10000.0, "shr": 1_000_000, "dps3": [1000.0] * 3,
           "_bas": F.parse_dart_dividend(alot([1000] * 3, cash=[500] * 3, par=[5000] * 3))["bas"]},
          {"t": "000020", "nk": "무배당", "cls": "kr", "price": 5000.0, "shr": 1_000_000, "dps3": [0.0, 0.0, 0.0],
           "_bas": F.parse_dart_dividend(alot([0, 0, 0], cash=[None] * 3, par=[500] * 3))["bas"]},
          {"t": "000030", "nk": "DART없음", "cls": "kr", "price": 5000.0, "shr": 1_000_000}]
    fin = {"001130": {"cs3": [84.5] * 3}, "000010": {"cs3": CS50}, "000020": {"cs3": [5.0] * 3}}
    counts, _ = F.apply_div_basis(kr, fin, {})
    a, b, c, d = kr
    assert a["dyt"] == round(400 / 10680 * 100, 2) and a["divSt"] == "adj"         # 분할 뒤 오늘 종가로: 3.75%
    assert "dyt" not in b and b["divSt"] == "nd"                                    # 확인 못 하면 빈 칸 (추측 없음)
    assert c["dyt"] == 0.0 and c["divSt"] == "zero" and not {"divSt", "dyt", "dps3a"} & set(d)
    assert counts == {"v": 1, "same": 0, "adj": 1, "nc": 0, "nd": 1, "zero": 1, "noDps": 1, "pref": 0, "payers": 2, "dyt": 2}
    out = capsys.readouterr().out
    assert "배당 분할 확인: 그대로 0 · 맞춤 1: 001130 대한제분 ×10/10/10" in out and "알 수 없음 1: 000010 자기주식많음" in out
    F.add_percentiles(kr)
    assert a["dz"] > c["dz"] and "dz" not in b and "dz" not in d                  # 순위는 확인한 배당으로만
    assert F.dividend_rank_missing(kr, ("001130", "000010", "000030")) == [("000010", "nd"), ("000030", "DART 배당 표 없음")]
    json.dumps(kr, allow_nan=False)


def test_main_ranks_dividends_after_the_split_check_and_logs_a_missing_must_have():
    # 필수 종목이 배당 순위에서 빠지면 이유와 함께 크게 남기고 관문(필수 종목 배당 순위)이 발행을 막아요. 파이프라인은 멈추지 않아요:
    # 파일과 관문 표가 남아야 시험 실행에서 원인을 볼 수 있어서예요 (리뷰 1)
    import inspect
    src = inspect.getsource(F.main)
    i_basis, i_rank = src.find("apply_div_basis(kr"), src.find("add_percentiles(kr)")
    assert src.find("blank_foreign_dart(kr)") < i_basis < i_rank < src.find("dividend_rank_missing(kr)")
    assert i_basis < src.find("build_corp(kr, fin_map") and '"divCheck": div_counts' in src
    tail = src[src.find("dividend_rank_missing(kr)"):src.find("payload = {")]
    assert "관문에서 실패해 발행하지 않아요" in tail and "raise" not in tail


def test_unknown_years_are_never_called_no_dividend():
    # 해외 기업은 0 이 아닌 배당을 비워요 → [빈 칸, 0, 빈 칸] 은 '3년 배당 없음'이 아니라 알 수 없음 (리뷰 1)
    kr = [{"t": "900290", "nk": "GRT", "cls": "kr", "price": 1000.0, "shr": 1_000_000, "dps3": [None, 0.0, None],
           "_bas": F.parse_dart_dividend(alot([50, 0, 30], cash=[50, 0, 30], par=[500] * 3, eps=[10, 5, 3], ni=[10, 5, 3]))["bas"]}]
    counts, extra = F.apply_div_basis(kr, {}, {})
    assert kr[0]["dps3a"] == [None, 0.0, None] and kr[0]["divSt"] == "nd" and "dyt" not in kr[0] and extra == {}
    assert F.div_basis([0.0, 0.0, None], None, None, 1_000_000)["divSt"] == "nd"
    assert F.div_basis([0.0, 0.0, 0.0], None, None, 1_000_000)["divSt"] == "zero"
    assert F.div_basis([0.0, None, None], None, None, 1_000_000)["dps3a"] == [0.0, None, None]   # 올해 0 은 알아요 (수익률 0)


def test_reverse_split_by_three_matches_the_gate_to_the_cent():
    # 3:1 병합 뒤: 배율 1/3 은 소수 여섯째 자리(0.333333)로 발행돼요. dps3a 를 그 발행값으로 나눠야 관문의 다시 계산과 맞아요 (리뷰 1)
    div, r = basis_of(alot([12000] * 3, cash=[12000] * 3, par=[5000] * 3), CS50, 333_334)
    assert r["dpsF"] == [0.333333] * 3 and r["dps3a"] == [round(12000 / 0.333333, 2)] * 3 and r["divSt"] == "adj"
    s = {"t": "000100", "dps3": [12000.0] * 3, "dps3a": r["dps3a"], "dpsF": r["dpsF"], "divSt": r["divSt"]}
    assert V.div_row_problem(s) is None


# ── 3. 베타 표준오차 ──────────────────────────────────────
def test_beta_standard_error_matches_least_squares():
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2023-01-02", periods=740)
    x = pd.Series(rng.normal(0, 0.01, 740), index=idx)
    y = pd.Series(1.2 * x.values + rng.normal(0, 0.02, 740), index=idx)
    b, a, se, n = F.beta_fit(y, x, 0.03)
    X = np.column_stack([np.ones(740), x.values])
    coef, rss, *_ = np.linalg.lstsq(X, y.values, rcond=None)
    want = math.sqrt(rss[0] / (740 - 2) * np.linalg.inv(X.T @ X)[1, 1])
    assert n == 740 and b == round(coef[1], 2) and se == round(want, 4) and 0.05 < se < 0.09
    assert F.beta_fit(y.iloc[:200], x.iloc[:200], 0.03) == (None, None, None, None)     # 250일 미만은 베타도 없어요
    flat = pd.Series(0.0, index=idx)                                                    # 1년 넘게 거래정지: 수익률이 모두 0
    assert F.beta_fit(flat, x, 0.03) == (None, None, None, None)                        # 표준오차 없는 베타는 쓰지 않아요 (리뷰 1)


def test_every_beta_written_by_the_pipeline_carries_its_error_and_count():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert src.count("beta_fit(ret, bench, rf)") == 2 and "beta_alpha" not in src
    assert src.count('"betaSE": bse if b is not None else None, "betaN": bn if b is not None else None') == 2


# ── 4. flRan ─────────────────────────────────────────────
def test_flran_lists_the_checks_that_actually_ran():
    s = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "cap": 1.0, "s": "chem", "shr": 1_000_000,
         "dps3a": [10.0, 10.0, 10.0], "dpsF": [1.0, 1.0, 1.0], "divSt": "same", "dyt": 1.0, "betaSE": 0.07, "betaN": 740}
    fin = {"000100": {"ni": [-1.0, -2.0, -3.0], "ca": 1.0, "cl": 2.0, "cs": 5.0, "eq": 1.0, "op": [-1.0, 0, 0], "ie": 0.5}}
    c = F.build_corp([s], fin, "2026-11-05", extra={"000100": {"cash3": [0.1, 0.1, 0.1]}})["companies"][0]
    assert c["flRan"] == ["cr", "icr", "l3", "imp"] and set(c["fl"]) == {"cr", "icr", "l3", "imp"} and "flNa" not in c
    assert c["dps3a"] == [10.0, 10.0, 10.0] and c["divSt"] == "same" and c["betaSE"] == 0.07 and c["cash3"] == [0.1] * 3
    bank = dict(s, t="000200", s="bank")
    c = F.build_corp([bank], {"000200": {"ni": [1.0, None, 1.0], "eq": 9.0}}, "2026-11-05")["companies"][0]
    assert c["flRan"] == [] and c["flNa"] == ["cr", "icr"] and "fl" not in c      # 3년 순이익·자본금이 비면 그 검사도 안 돌았어요
    ok = F.build_corp([dict(s, t="000300")], {"000300": {"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0,
                                                          "op": [9.0, 0, 0], "ie": 1.0}}, "2026-11-05")["companies"][0]
    assert ok["flRan"] == ["cr", "icr", "l3", "imp"] and "fl" not in ok            # 모두 돌았고 경고 없음
    assert "dz" not in ok                                                           # 배당 점수가 없는 종목은 corp.json 에도 없어요
    free = F.build_corp([dict(s, t="000400", dz=55)], {"000400": {"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0,
                                                                  "eq": 5.0, "op": [9.0, 0, 0], "ie": 0.0}}, "2026-11-05")["companies"][0]
    assert free["flRan"] == ["cr", "icr", "l3", "imp"] and "fl" not in free       # 이자비용 0: 검사는 돌았고 경고는 날 수 없어요 (리뷰 1)
    assert free["dz"] == 55                                                         # 배당 점수도 corp.json 에 (다른 팩터 점수처럼)
    nie = F.build_corp([dict(s, t="000500")], {"000500": {"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0,
                                                          "op": [9.0, 0, 0]}}, "2026-11-05")["companies"][0]
    assert nie["flRan"] == ["cr", "l3", "imp"]                                      # 이자비용 줄이 없으면(모름) 돌지 않은 거예요


# ── 5. DART 캐시 v2 · 호출 수 어림 ────────────────────────
def test_dart_cache_is_version_two_in_the_pipeline_and_the_workflow():
    assert F.DART_CACHE_VERSION == 2 and F.DART_CACHE_PATH.endswith("dart-v2.json.gz")
    with open(os.path.join(ROOT, ".github", "workflows", "update-data.yml"), encoding="utf-8") as f:
        text = f.read()
    assert "dart-cache-v1" not in text and "dart-v1.json.gz" not in text
    steps = {s.get("name"): s for s in yaml.safe_load(text)["jobs"]["update"]["steps"]}
    assert steps["DART 캐시 불러오기"]["with"]["restore-keys"] == "dart-cache-v2-"
    assert steps["DART 캐시 저장"]["with"]["key"].startswith("dart-cache-v2-")
    assert ".dart-cache/" + os.path.basename(F.DART_CACHE_PATH) in steps["DART 캐시 확인 (정해진 시각 실행은 빈 캐시로 시작하지 않아요)"]["run"]


def test_full_refresh_call_estimate_stays_under_the_target():
    # 공시 최대 = 목록 30쪽 + 내부자 상세 1,200 (DISC_CALL_CAP) + 국민연금 200 (리뷰 1)
    assert F.DART_DISC_MAX == 30 + F.DISC_CALL_CAP + 200 == 1430
    total, why = F.dart_full_estimate(2418)
    assert total == math.ceil(2418 * 4.8) + 2418 + 1 + 1430 == 15456 and "공시 최대 1,430" in why
    assert F.dart_full_estimate(F.MAX_KR)[0] == 15931 < F.DART_FULL_TARGET < F.DART_DAY_LIMIT  # 상한 2,500곳이어도 16,000 아래
    assert F.dart_full_estimate(2418, ksic=False)[0] == 15456 - 2418


def test_gate_and_pipeline_share_the_same_dividend_rules():
    # 관문은 일부러 따로 적어요 (같은 실수를 같이 하지 않게). 그래도 값은 같아야 해요 — 한쪽만 바꾸면 여기서 걸려요 (리뷰 1)
    assert V.SPLIT_FACTORS == F.SPLIT_FACTORS and V.DYT_MAX == F.DYT_MAX and V.DIV_STATUS == F.DIV_STATUS
    assert all(V._factor_ok(c) for c in F.DIV_FACTORS) and V._factor_ok(10 * 5) and V._factor_ok(3 * 0.5)   # 당기 × 이전 해
    assert not V._factor_ok(1.3) and not V._factor_ok(1.1) and not V._factor_ok(0.0)


def test_client_knows_it_started_from_an_empty_cache(tmp_path):
    # 빈 캐시로 시작하면 전체 DART 실행이라 호출 수 어림을 남겨요. v1 캐시 파일(버전 1)도 빈 캐시예요 (새 칸이 없어서)
    assert F.DartClient("k", today=dt.date(2026, 11, 5), path=str(tmp_path / "none.json.gz")).started_empty is True
    import gzip
    p = tmp_path / "v1.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump({"v": 1, "entries": {"a|2025|11011|DIV2": {"st": "000", "at": "2026-11-01", "d": {"dps": 1.0}}}}, f)
    assert F.DartClient("k", today=dt.date(2026, 11, 5), path=str(p)).started_empty is True


# ── 6. 관문 새 줄 ─────────────────────────────────────────
NEW_ROWS = ("배당 분할 확인 기록 (divCheck)", "국내 배당 분할 확인 칸 (dps3 있는 보통주 모두)", "국내 dps3a = dps3 ÷ 배율 · divSt 맞음",
            "국내 오늘 배당수익률 dyt = dps3a[0] ÷ 종가 · dz", "배당한 국내 회사 중 오늘 수익률(dyt) 확인",
            "배당한 국내 회사 중 분할·무상증자로 맞춘 비율", "필수 종목 배당 순위 (dyt·dz)",
            "필수 종목 새 칸 (배당 분할 확인·베타 표준오차·재무 경고 검사)", "베타 표준오차 (betaSE·betaN)",
            "재무 경고 검사 기록 (flRan, 국내 기업 모두)", "새 금액 칸 모양 (총액·주당순이익·해외 기업)", "divCheck 집계 = 종목 수")


def with_new_fields(files):
    """좋은 픽스처에 v19.1b 칸을 파이프라인과 같은 규칙으로 채워요 (배당주 30곳 중 하나꼴로 1:2 분할 맞춤 · 다섯 곳은 알 수 없음)."""
    data, corp = files["data"], files["corp"]
    kr = [s for s in data["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    nd_left = 5
    for i, s in enumerate(kr):
        d = s["dps"]
        if d > 0 and i % 30 == 7:
            s.update(dps3=[d, 2 * d, 2 * d], dps3a=[d, d, d], dpsF=[1.0, 2.0, 2.0], divSt="adj")
        elif d > 0 and nd_left and s["t"] not in V.MUST:
            nd_left -= 1
            s.update(dps3=[d, d, d], dps3a=[None, None, None], dpsF=[None, None, None], divSt="nd")
        elif d > 0:
            s.update(dps3=[d, d, d], dps3a=[d, d, d], dpsF=[1.0, 1.0, 1.0], divSt="same")
        else:
            s.update(dps3=[0.0, 0.0, 0.0], dps3a=[0.0, 0.0, 0.0], dpsF=[None, None, None], divSt="zero")
        if s["dps3a"][0] is not None and s["dps3a"][0] / s["price"] * 100 <= F.DYT_MAX:      # 30% 넘으면 파이프라인처럼 빈 칸
            s["dyt"] = round(s["dps3a"][0] / s["price"] * 100, 2)
        s.update(betaSE=0.07, betaN=740)
    F.add_percentiles(kr)
    for s in kr:
        for k in ("pz", "vz", "mz", "qz", "lz"):
            s[k] = 50                                             # 원래 픽스처 값 그대로 (dz 만 새로)
    for s in data["stocks"]:
        if s.get("cls") == "us" and s.get("beta") is None:
            s.update(beta=1.0, betaSE=0.05, betaN=740)
    by = {s["t"]: s for s in kr}
    for c in corp["companies"]:
        s = by[c["t"]]
        c.update(flRan=["cr", "icr", "l3", "imp"], dps3a=s["dps3a"], dpsF=s["dpsF"], divSt=s["divSt"],
                 cash3=[1.0, 1.0, 1.0], eps3r=[100.0, 90.0, 80.0], epsNi3=[1.0, 0.9, 0.8], epsB="연결")
        if s.get("dyt") is not None:
            c["dyt"] = s["dyt"]
    st = [s.get("divSt") for s in kr]
    data["divCheck"] = {"v": 1, **{k: st.count(k) for k in V.DIV_STATUS}, "noDps": 0, "pref": 0,
                        "payers": sum(1 for s in kr if s["dps3"][0] > 0), "dyt": sum(1 for s in kr if s.get("dyt") is not None)}
    return files


def check(cur, prev, mode="publish"):
    final = {"date": dt.date(2026, 10, 30), "closes": {s["t"]: round(s["price"]) for s in cur["data"]["stocks"] if s.get("cls") == "kr"},
             "how": "시험"}
    return V.run_checks(cur, prev, final, TODAY, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                        hilo=hilo_of(cur, V.MUST))


def rows_of(rep):
    return {r[0]: r for r in rep.rows}


@pytest.fixture
def pair():
    cur, prev, _ = good_pair()
    return with_new_fields(cur), prev


def kr_of(files):
    return [s for s in files["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]


def test_good_new_fields_pass_every_new_row(pair):
    cur, prev = pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    got = rows_of(rep)
    assert all(got[n][3] == "PASS" for n in NEW_ROWS), [got[n] for n in NEW_ROWS if got[n][3] != "PASS"]
    assert not check(cur, None, mode="live").failed                    # 사이트 점검(--live)도 같은 절대 기준


def test_data_before_v191b_is_only_a_warning_until_the_new_fields_were_published(pair):
    cur, prev = pair
    old, _, _ = good_pair()
    rep = check(old, prev)                                              # 직전도 새 칸이 없으면 경고 한 줄만
    assert not rep.failed and rows_of(rep)["배당 분할 확인 기록 (divCheck)"][3] == "WARN"
    assert not any(n in rows_of(rep) for n in NEW_ROWS[1:])
    rep = check(old, None, mode="live")                                 # 머지 직후 사이트의 옛 데이터도 경고만
    assert not rep.failed and rows_of(rep)["배당 분할 확인 기록 (divCheck)"][3] == "WARN"
    rep = check(old, {"data": cur["data"]})                             # 한 번 발행된 뒤 빠지면 실패
    assert "배당 분할 확인 기록 (divCheck)" in {r[0] for r in rep.failed}
    late = V.run_checks(old, None, None, V.DIVCHECK_REQUIRED_FROM, mode="live", sessions=SESSIONS, now=NOW, hilo=hilo_of(old, V.MUST))
    assert "배당 분할 확인 기록 (divCheck)" in {r[0] for r in late.failed}   # 12월 1일부터는 옛 형식도 실패 (기한 없는 예외 없음, 리뷰 1)
    early = V.run_checks(old, None, None, V.DIVCHECK_REQUIRED_FROM - dt.timedelta(days=1), mode="live", sessions=SESSIONS,
                         now=NOW, hilo=hilo_of(old, V.MUST))
    assert next(r for r in early.rows if r[0] == "배당 분할 확인 기록 (divCheck)")[3] == "WARN"


def _fails(cur, prev, name):
    rep = check(cur, prev)
    assert name in {r[0] for r in rep.failed}, rep.table()


def test_wrong_divcheck_version_fails(pair):
    cur, prev = pair
    cur["data"]["divCheck"]["v"] = 2
    _fails(cur, prev, "배당 분할 확인 기록 (divCheck)")


def test_dps3_without_split_check_fails(pair):
    cur, prev = pair
    s = next(s for s in kr_of(cur) if s["divSt"] == "same")
    for k in ("divSt", "dps3a", "dpsF", "dyt", "dz"):
        s.pop(k, None)
    _fails(cur, prev, "국내 배당 분할 확인 칸 (dps3 있는 보통주 모두)")


@pytest.mark.parametrize("change", ["value", "factor", "status", "zero", "unclean"])
def test_adjusted_dividend_inconsistent_with_its_factor_fails(pair, change):
    cur, prev = pair
    s = next(s for s in kr_of(cur) if s["divSt"] == "adj")
    if change == "value":
        s["dps3a"][1] = s["dps3"][1]                   # 배율 2 인데 나누지 않음
    elif change == "factor":
        s["dpsF"][1] = 1.0                             # 값은 맞췄는데 배율은 1
    elif change == "status":
        s["divSt"] = "same"
    elif change == "zero":
        z = next(x for x in kr_of(cur) if x["divSt"] == "zero")
        z["dpsF"][0] = 1.0
    else:
        s["dpsF"][1], s["dps3a"][1] = 1.3, round(s["dps3"][1] / 1.3, 2)   # 어중간한 배율로 맞추면 안 돼요
    _fails(cur, prev, "국내 dps3a = dps3 ÷ 배율 · divSt 맞음")


@pytest.mark.parametrize("change", ["unadjusted", "missing", "dz_without_dyt", "dz_range", "dyt_for_nd"])
def test_todays_yield_must_come_from_the_adjusted_dividend(pair, change):
    cur, prev = pair
    s = next(s for s in kr_of(cur) if s["divSt"] == "adj")
    if change == "unadjusted":
        s["dyt"] = round(s["dps3"][1] / s["price"] * 100, 2)   # 옛 기준 배당으로 계산한 수익률
    elif change == "missing":
        s.pop("dyt", None), s.pop("dz", None)
    elif change == "dz_without_dyt":
        z = next(x for x in kr_of(cur) if x["divSt"] == "nd")
        z["dz"] = 50
    elif change == "dz_range":
        s["dz"] = 101
    else:
        z = next(x for x in kr_of(cur) if x["divSt"] == "nd")
        z["dyt"], z["dz"] = 1.0, 50
    _fails(cur, prev, "국내 오늘 배당수익률 dyt = dps3a[0] ÷ 종가 · dz")


def test_too_few_verified_yields_fail(pair):
    cur, prev = pair
    payers = [s for s in kr_of(cur) if s["divSt"] in ("same", "adj") and s["t"] not in V.MUST]
    for s in payers[:int(len(payers) * 0.2)]:
        s.update(dps3a=[None] * 3, dpsF=[None] * 3, divSt="nd")
        s.pop("dyt", None), s.pop("dz", None)
    _fails(cur, prev, "배당한 국내 회사 중 오늘 수익률(dyt) 확인")


def test_too_many_adjusted_dividends_fail(pair):
    cur, prev = pair
    for s in [s for s in kr_of(cur) if s["divSt"] == "same"][:200]:
        d = s["dps3"][0]
        s.update(dps3=[d, 2 * d, 2 * d], dpsF=[1.0, 2.0, 2.0], divSt="adj")
    _fails(cur, prev, "배당한 국내 회사 중 분할·무상증자로 맞춘 비율")


@pytest.mark.parametrize("t", ["005930", "015760"])
def test_must_have_out_of_the_dividend_rank_fails(pair, t):
    cur, prev = pair
    s = next(s for s in kr_of(cur) if s["t"] == t)
    s.update(dps3a=[None] * 3, dpsF=[None] * 3, divSt="nd")
    s.pop("dyt", None), s.pop("dz", None)
    _fails(cur, prev, "필수 종목 배당 순위 (dyt·dz)")


@pytest.mark.parametrize("where, key", [("data", "betaSE"), ("data", "betaN"), ("corp", "flRan"), ("corp", "eps3r")])
def test_must_have_without_new_fields_fails(pair, where, key):
    cur, prev = pair
    arr = kr_of(cur) if where == "data" else cur["corp"]["companies"]
    next(x for x in arr if x["t"] == "005380").pop(key)
    _fails(cur, prev, "필수 종목 새 칸 (배당 분할 확인·베타 표준오차·재무 경고 검사)")


@pytest.mark.parametrize("se, n", [(0.0, 740), (-0.1, 740), (0.6, 740), ("0.07", 740), (0.07, 120), (0.07, 900), (0.07, 740.5), (None, 740)])
def test_bad_beta_standard_error_fails(pair, se, n):
    cur, prev = pair
    s = kr_of(cur)[50]
    s["betaSE"], s["betaN"] = se, n
    _fails(cur, prev, "베타 표준오차 (betaSE·betaN)")


def test_implausible_median_beta_standard_error_fails(pair):
    cur, prev = pair
    for s in cur["data"]["stocks"]:
        if s.get("betaSE") is not None:
            s["betaSE"] = 0.3                              # 하나하나는 범위 안이지만 전체가 이상한 날
    _fails(cur, prev, "베타 표준오차 (betaSE·betaN)")
    cur2, prev2 = good_pair()[:2]
    cur2 = with_new_fields(cur2)
    s = next(s for s in kr_of(cur2) if s.get("beta") is not None)
    s.pop("beta")                                          # 베타 없이 표준오차만
    _fails(cur2, prev2, "베타 표준오차 (betaSE·betaN)")


@pytest.mark.parametrize("change", ["missing", "warning_not_run", "unknown_key", "overlap"])
def test_financial_warning_record_must_match(pair, change):
    cur, prev = pair
    c = cur["corp"]["companies"][3]
    if change == "missing":
        c.pop("flRan")
    elif change == "warning_not_run":
        c["flRan"], c["fl"] = ["l3"], {"cr": 80.0}
    elif change == "unknown_key":
        c["flRan"] = ["cr", "zz"]
    else:
        c["flRan"], c["flNa"] = ["cr", "icr"], ["cr"]
    _fails(cur, prev, "재무 경고 검사 기록 (flRan, 국내 기업 모두)")


@pytest.mark.parametrize("change", ["foreign_amount", "negative_total", "string_eps", "basis_name", "foreign_dividend"])
def test_new_amount_fields_shape(pair, change):
    cur, prev = pair
    c = cur["corp"]["companies"][20]                   # 필수 종목이 아닌 회사
    if change == "foreign_amount":
        c["t"] = "950160"                              # 해외 기업 코드인데 총액·주당순이익이 남음
    elif change == "negative_total":
        c["cash3"] = [-1.0, 1.0, 1.0]
    elif change == "string_eps":
        c["eps3r"] = ["100", 90.0, 80.0]
    elif change == "basis_name":
        c["epsB"] = "consolidated"
    else:
        s = next(s for s in kr_of(cur) if s["divSt"] == "same" and s["t"] not in V.MUST)
        s["t"] = "950170"
    _fails(cur, prev, "새 금액 칸 모양 (총액·주당순이익·해외 기업)")


@pytest.mark.parametrize("key", ["same", "nd", "payers", "dyt", "pref"])
def test_divcheck_counts_must_match_the_stocks(pair, key):
    cur, prev = pair
    cur["data"]["divCheck"][key] += 1
    _fails(cur, prev, "divCheck 집계 = 종목 수")
