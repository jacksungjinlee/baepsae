# -*- coding: utf-8 -*-
"""공시 단위 확인 (Jack, 2026-11-13): 단위를 잘못 적은 재무제표로 만든 숫자를 비워요 — fetch_data.unit_check · unit_guard · build_corp
와 관문(validate_data.check_unit). (네트워크 없음)

픽스처 tests/fixtures/dart_unit_samples.json 은 2026-11-13 (KST) 에 OpenDART 에서 받은 실제 재무제표(fnlttSinglAcntAll)예요 —
2025 사업보고서 · 2026 반기 · 2025 반기, 파서가 읽는 칸만 (자본변동표 줄은 뺐어요 · 빼도 해석이 같은 것을 확인했어요). 인증키는 없어요.
  250030 진코스텍 (OFS) · 002880 디와이에이 (CFS): 2026 반기보고서가 '(단위 : 천원)' 이라 적고 숫자는 원 → 모든 금액이 정확히 1,000배
  040610 SG&G · 109960 앱토크롬 (CFS): PBR 0.09 · 0.07 이지만 공시 그대로 (원으로 공시 · 관계기업 투자 · 금융자산이 커요)
가격 · 주식 수는 2026-11-12 발행본(pxDate 2026-11-11)의 값이에요.
"""
import copy
import datetime as dt
import gzip
import inspect
import json
import math
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_v191f_income import check, comp, fails, pair, rows_of  # noqa: E402,F401  (pair 는 pytest 픽스처)

with open(os.path.join(ROOT, "tests", "fixtures", "dart_unit_samples.json"), encoding="utf-8") as _f:
    FIX = json.load(_f)
CO, ST = FIX["companies"], FIX["statements"]
# 2026-11-12 발행본: 가격 · 보통주 수 · 시가총액(조원)
PX = {"250030": (9200.0, 3786533, 0.035), "002880": (3130.0, 9354799, 0.029), "040610": (2725.0, 17043598, 0.046),
      "109960": (1655.0, 15132233, 0.025)}
BAD, REAL = ("250030", "002880"), ("040610", "109960")
# 리뷰 #118 N1: 비우는 칸을 상수에서 돌지 않고 여기 따로 적어요 (두 쪽 모두 같은지 시험이 봐요)
DATA_BLANK = ("per", "pbr", "eps", "bps", "roe", "debt", "opm", "g3")
CORP_BLANK = ("evE", "evR", "pcf", "bq", "nio3", "nio3Hyb", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "fl", "flSrc", "flWhy")
EXTRA_BLANK = ("epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "nio3", "nio3Hyb")
ALL4 = ["scale", "is", "cf", "eps"]   # 두 반기보고서: 재무상태표 · 손익 · 현금흐름 지난해 칸 · 기본주당이익 모두 1,000배 (자산=부채+자본은 맞아요)
FILED = {"data": ("per", "pbr", "eps", "bps", "roe", "debt", "opm", "g3", "vz", "qz")}


def rows(t, y, r):
    return copy.deepcopy(ST[f"{t}|{y}|{r}|{CO[t]['fs']}"]["rows"])


def scaled(rs, k):
    """한 보고서의 모든 금액을 k 배 (단위를 잘못 읽은 보고서처럼)."""
    out = []
    for x in rs:
        x = dict(x)
        for c in ("thstrm_amount", "thstrm_add_amount", "frmtrm_amount", "frmtrm_add_amount", "bfefrmtrm_amount"):
            v = F._num(x.get(c))
            if v is not None:
                x[c] = str(int(v * k)) if float(v * k).is_integer() else str(v * k)
        out.append(x)
    return out


def company(t, annual=None, q=None, qp=None):
    """파이프라인과 같은 모양: 사업보고서(_fin + 비율) + TTM(ttm · bs2 · bsP · bq) → (data.json 종목, fin)."""
    out = F.parse_dart_list(annual if annual is not None else rows(t, 2025, "11011"))
    fin = out["_fin"]
    fin["fs"] = CO[t]["fs"]
    t2 = F.compute_ttm(fin, F.parse_dart_quarter(q if q is not None else rows(t, 2026, "11012")),
                       F.parse_dart_quarter(qp if qp is not None else rows(t, 2025, "11012")))
    fin["ttm"], fin["bs2"], fin["bsP"], fin["qChk"], fin["bq"] = t2["ttm"], t2["bs"], t2["bsP"], t2["chk"], "2026.2Q"
    price, shr, cap = PX[t]
    s = {"t": t, "nk": CO[t]["name"], "cls": "kr", "price": price, "shr": shr, "cap": cap, "fy": 2025, "vol": 30.0, "mom": 1.0,
         "dps": 0.0, "dps3": [0.0, 0.0, 0.0], "dy": 0.0}
    s.update({k: out[k] for k in ("debt", "roe", "opm", "g3") if k in out})
    return s, fin


def run_all(cos):
    """[(종목, fin)] → (종목들, fin_map, mult_extra, corp.json) — main() 과 같은 순서 (fill_multiples → unit_guard → 점수 → corp)."""
    kr = [s for s, _ in cos]
    fm = {s["t"]: fin for s, fin in cos}
    extra = F.fill_multiples(kr, fm, {})
    guard = F.unit_guard(kr, fm, extra)
    F.add_percentiles(kr)
    corp = F.build_corp(kr, fm, "2026-11-13", extra=extra)
    return kr, fm, extra, corp, guard


# ── 1. 실제 재무제표: 1,000배 보고서는 걸리고, PBR 이 낮아도 공시 그대로인 회사는 남아요 ──────
def test_the_real_half_year_reports_in_the_wrong_unit_are_caught():
    for t in BAD:
        _, fin = company(t)
        u = F.unit_check(fin)
        assert u["why"] == ["scale", "is", "cf"], (t, u)                 # 손익 · 현금흐름표의 지난해 칸도 1,000배 (주식 수를 안 주면 eps 는 안 봐요)
        assert 1000 <= u["scale"]["q"] <= 1500, u            # 최신 분기(2026 반기)가 사업보고서의 약 1,000배 (진짜 변화 × 1,000)
        assert 0.5 < u["scale"]["qp"] < 2, u                  # 지난해 같은 분기(2025 반기)는 맞아요
        assert u["bal"] == {"fy": 0.0, "q": 0.0, "qp": 0.0}   # 보고서 전체가 같은 배율이라 자산 = 부채 + 자본 은 맞아요


def test_the_real_low_pbr_companies_pass_the_check():
    for t in REAL:
        _, fin = company(t)
        u = F.unit_check(fin)
        assert u["why"] == [], (t, u)
        assert all(0.5 < v < 2 for v in u["scale"].values()), u
        assert u["bal"] == {"fy": 0.0, "q": 0.0, "qp": 0.0}


def test_the_whole_report_really_is_exactly_1000_times():
    """진단의 증거: 그 보고서의 2025-12-31 칸 = 사업보고서 값 × 1,000 (자산총계 · 자본총계)."""
    for t in BAD:
        a = F.balance_totals(rows(t, 2025, "11011"))
        prior = F.balance_totals(rows(t, 2026, "11012"), col="frmtrm_amount")
        assert prior[0] == a[0] * 1000 and prior[2] == a[2] * 1000, (t, a, prior)
    for t in REAL:
        assert F.balance_totals(rows(t, 2026, "11012"), col="frmtrm_amount")[0] == F.balance_totals(rows(t, 2025, "11011"))[0]


def test_end_to_end_the_flagged_companies_lose_every_statement_number_and_the_real_ones_keep_theirs(capsys):
    kr, fm, extra, corp, guard = run_all([company(t) for t in BAD + REAL])
    by = {s["t"]: s for s in kr}
    cby = {c["t"]: c for c in corp["companies"]}
    assert guard["hit"] == {"250030": ALL4, "002880": ALL4}
    assert [x.split(" ")[0] for x in guard["real"]] == ["040610", "109960"]
    for t in BAD:
        s, c = by[t], cby[t]
        assert s["unitChk"] == ALL4 and c["unitChk"] == ALL4
        for k in FILED["data"]:
            assert k not in s, (t, k)                                       # 빈 칸 (0 이 아니에요)
            assert c.get(k) is None, (t, k)
        assert c["rev"] == [None] * 3 and c["op"] == [None] * 3 and c["ni"] == [None] * 3 and c["eq"] is None
        assert c["dcfReady"] is False and c["flRan"] == []
        for k in CORP_BLANK:
            assert k not in c, (t, k)
        assert t not in extra or not any(k in extra[t] for k in EXTRA_BLANK)
        assert s["dps"] == 0.0 and c["dps"] == 0.0 and c["fy"] == 2025      # 배당(별도 배당 표)과 보고서 연도는 남아요
        assert "unitChk" not in fm[t]                                       # 리뷰 #118 N5: 표시는 종목 한 곳 (build_corp 가 종목을 봐요)
    for t in REAL:
        s, c = by[t], cby[t]
        assert "unitChk" not in s and "unitChk" not in c
        assert s["pbr"] < 0.1 and c["pbr"] == s["pbr"] and c["bpsIn"]["eq"] > 1000 and s["vz"] is not None
    # 진짜 값: SG&G BPS = 주주 몫 자본 5,085.1억 ÷ 17,043,598주 · PBR 0.09
    assert by["040610"]["bps"] == round(5085.1e8 / 17043598) and by["040610"]["pbr"] == 0.09
    out = capsys.readouterr().out
    assert "!! 공시 단위 확인: 2곳 비움 (자산≠부채+자본 0 · 보고서 사이 배율 2 · 손익계산서 지난해 칸 2 · 현금흐름표 지난해 칸 2 · 기본주당이익 2 · 자본금 ÷ 액면가 0)" in out
    assert "!! 공시 단위: 250030 진코스텍 [보고서 사이 배율" in out and "비운 값: per 0.0, pbr 0.0, eps 777,569.0" in out
    named = [x for x in out.splitlines() if x.startswith("  !! 공시 단위: ")]                  # 리뷰 #118 S2: 걸린 회사마다 한 줄 (PR 에 옮겨 적어요)
    assert [x.split(" ")[5] for x in named] == ["250030", "002880"], named
    assert "PBR 0.1 미만인데 공시 단위 확인을 통과한 회사 2곳" in out and "040610 SG&G (PBR 0.09" in out and "109960 앱토크롬 (PBR 0.07" in out
    # 파일로 쓸 수 있어요 (NaN · Infinity 없음)
    json.dumps({"stocks": kr, "corp": corp}, allow_nan=False)


def test_scores_are_ranked_without_the_blanked_companies():
    cos = [company(t) for t in BAD + REAL]
    kr, *_ = run_all(cos)
    by = {s["t"]: s for s in kr}
    assert all("vz" not in by[t] and "qz" not in by[t] for t in BAD)
    # 남은 두 회사끼리만: PBR 0.07 (앱토크롬) 이 더 낮아 가치 점수가 높아요 · 두 회사 순위 = 50 · 0
    assert (by["109960"]["vz"], by["040610"]["vz"]) == (50, 0)
    alone = F.add_percentiles([{"cls": "kr", "pbr": by[t]["pbr"], "roe": by[t]["roe"]} for t in REAL])
    assert [x["vz"] for x in alone] == [by[t]["vz"] for t in REAL] and [x["qz"] for x in alone] == [by[t]["qz"] for t in REAL]


# ── 2. 규칙 하나씩 ──────────────────────────────────────────────
def test_a_1000_times_quarter_is_caught_and_so_is_a_1000000_times_one_and_an_annual_off_the_other_way():
    t = "040610"
    for k in (1000, 1e6):
        _, fin = company(t, q=scaled(rows(t, 2026, "11012"), k))
        assert F.unit_check(fin)["why"] == ["scale", "is", "cf"], k
    _, fin = company(t, qp=scaled(rows(t, 2025, "11012"), 1000))             # 지난해 같은 분기가 틀려도
    u = F.unit_check(fin)
    assert u["why"] == ["scale", "is", "cf"] and u["scale"]["qp"] > 100 and u["scale"]["q"] < 2
    _, fin = company(t, annual=scaled(rows(t, 2025, "11011"), 1000))         # 사업보고서가 1,000배면 분기가 1/1,000
    u = F.unit_check(fin)
    assert u["why"] == ["scale"] and u["scale"]["q"] < 0.01


def test_a_balance_sheet_that_does_not_add_up_is_caught():
    t = "040610"
    q = rows(t, 2026, "11012")
    for x in q:
        if x.get("sj_div") == "BS" and x.get("account_id") == "ifrs-full_Liabilities":
            x["thstrm_amount"] = str(int(F._num(x["thstrm_amount"])) * 1000)     # 부채총계 한 줄만 단위가 틀림
    _, fin = company(t, q=q)
    u = F.unit_check(fin)
    assert u["why"] == ["bs"] and u["bal"]["q"] > 0.9 and u["bal"]["fy"] == 0.0


def test_the_balance_tolerance():
    assert F.bal_off([10e9, 6e9, 4e9]) == 0.0
    assert F.bal_off([10e9, 6e9, 4e9 - 2_999_999]) == 0.0                 # 300만원까지는 반올림 (천원·백만원 표)
    assert F.bal_off([10e9, 6e9, 4e9 - 10_000_001]) > 0                     # 1,000만원 넘게 = 0.1% 넘게 어긋남 (100억 회사)
    assert F.bal_off([1e12, 6e11, 4e11 - 9e8]) == 0.0                       # 큰 회사: 자산의 0.1% (10억)까지
    assert F.bal_off([1e12, 6e11, 4e11 - 1.1e9]) == pytest.approx(0.0011)
    assert F.bal_off([0.0, 1e9, -1e9 + 5e6]) == 1.0                         # 자산 0 이면 비율 대신 1
    for bad in (None, [1, 2], [1, None, 3], [1, float("nan"), 3], "x"):
        assert F.bal_off(bad) is None


def test_the_scale_is_a_median_so_one_real_big_move_does_not_trip_it():
    a = {"eq": 100.0, "ca": 50.0, "cl": 40.0, "cs": 10.0, "cash": 0.1}
    q = {"eq": 110.0, "ca": 55.0, "cl": 38.0, "cs": 10.0, "cash": 30.0}       # 현금만 300배 (진짜 일)
    assert 0.9 < F.stmt_scale(q, a) < 1.2
    one = {"eq": 0.5}                                                         # 자본잠식에서 증자: 자본 하나만 있어도 …
    assert F.stmt_scale({"eq": 80.0}, one) == pytest.approx(160.0)            # … 그 칸 하나뿐이면 그 배율 (한 칸으로는 가릴 수 없어요)
    assert F.stmt_scale({"eq": -5.0, "ca": 0.0}, {"eq": 10.0, "ca": 5.0}) is None   # 음수 · 0 은 빼요
    assert F.stmt_scale({}, a) is None and F.stmt_scale(None, a) is None
    two = F.stmt_scale({"eq": 120.0, "ca": 5000.0}, {"eq": 100.0, "ca": 50.0})   # 두 칸이면 로그 평균 (1.2 × 100 → 약 11)
    assert 10 < two < 12


def test_statements_saved_before_the_totals_were_read_are_not_checkable_but_still_scale_checked():
    t = "250030"
    _, fin = company(t)
    for src in (fin, fin["bs2"], fin["bsP"]):
        src.pop("bal", None)                                                   # 예전 캐시 항목처럼
    u = F.unit_check(fin)
    assert u["bal"] == {"fy": None, "q": None, "qp": None} and u["why"] == ["scale", "is", "cf"]
    assert F.unit_check({})["why"] == [] and F.unit_check({"eq": 100.0})["scale"] == {}


def test_parsers_keep_the_totals_and_compute_ttm_hands_over_last_years_quarter():
    t = "040610"
    a = F.parse_dart_list(rows(t, 2025, "11011"))["_fin"]
    q = F.parse_dart_quarter(rows(t, 2026, "11012"))
    qp = F.parse_dart_quarter(rows(t, 2025, "11012"))
    assert a["bal"] == [488759326992.0, 72105910159.0, 416653416833.0]
    assert q["bal"] == [595827600708.0, 87323646374.0, 508503954334.0]
    t2 = F.compute_ttm(dict(a, fs="CFS"), q, qp)
    assert t2["bs"]["bal"] == q["bal"]
    assert t2["bsP"] == {k: qp[k] for k in F.UNIT_SCALE_KEYS + ("bal",) if qp.get(k) is not None} and t2["bsP"]["eq"] == 3895.4
    assert F.balance_totals([{"sj_div": "BS", "account_nm": "자산 총계", "thstrm_amount": "10"}]) is None   # 셋 다 있어야
    named = [{"sj_div": "BS", "account_nm": n, "account_id": "-표준계정코드 미사용-", "thstrm_amount": v}
             for n, v in (("자산 총계", "10"), ("부채총계", "4"), ("자본총계", "6"))]
    assert F.balance_totals(named) == [10.0, 4.0, 6.0]                      # 코드가 없으면 이름으로 (띄어쓰기 빼고)


def test_the_guard_runs_where_main_needs_it():
    src = inspect.getsource(F.main)
    i = src.find("mult_extra = fill_multiples(")
    j = src.find("unit_guard(kr, fin_map, mult_extra, kmeta")
    assert 0 < i < j < src.find("income_check(kr, fin_map, mult_extra)") < src.find("add_percentiles(kr)") < src.find("build_corp(kr,")
    assert j < src.find("eps_basis_of(kr, mult_extra)")


@pytest.mark.parametrize("repair", [False, True])
def test_enrich_keeps_last_years_quarter_for_the_check(tmp_path, monkeypatch, repair):
    """enrich_with_dart (가짜 DART · 진코스텍의 실제 응답) 이 fin 에 bsP 를 남기고, 그 fin 으로 걸려요 — 공시 단위 고침(unit_fix_quarter)을
    끄면 안전망이 걸고, 켜면 표마다 증명해 나눈 숫자가 안전망을 지나요."""
    t, corp_code = "250030", CO["250030"]["corp"]
    if not repair:
        monkeypatch.setattr(F, "unit_fix_quarter", lambda client, corp, fin, year, reprt, q, prev, s=None, pref_shares=None, unit_log=None: q)

    def get(self, endpoint, params, timeout=25):
        key = f"{t}|{params.get('bsns_year')}|{params.get('reprt_code')}|{params.get('fs_div')}"
        with self.lock:
            self.status["000" if key in ST else "013"] += 1
        if endpoint.startswith("fnltt") and key in ST:
            return {"status": "000", "list": copy.deepcopy(ST[key]["rows"])}
        return {"status": "013"}
    monkeypatch.setattr(F.DartClient, "get", get)
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {t: corp_code})
    c = F.DartClient("k", today=dt.date(2026, 11, 13), path=str(tmp_path / "c.json.gz"))
    price, shr, cap = PX[t]
    kr = [{"t": t, "nk": "진코스텍", "cls": "kr", "price": price, "shr": shr, "cap": cap}]
    kr, fm = F.enrich_with_dart(kr, c, {})
    fin = fm[t]
    assert fin["bq"] == "2026.2Q" and fin["bsP"]["eq"] == 60.0 and "bal" in fin["bs2"] and "bal" in fin
    if repair:
        assert F.unit_check(fin)["why"] == [] and fin["bs2"]["eq"] == 264.2 and fin["unitFix"][0]["rep"] == "2026.2Q"
    else:
        assert F.unit_check(fin)["why"] == ["scale", "is", "cf"] and "unitFix" not in fin
    # 캐시에 저장된 해석(새 칸 bal 포함)으로 다음 실행도 같은 판단
    with gzip.open(str(tmp_path / "c.json.gz"), "rt", encoding="utf-8") as f:
        ent = json.load(f)["entries"]
    assert ent[f"{corp_code}|2026|11012|OFS"]["d"]["bal"][0] == 60392733970000.0


# ── 2b. 리뷰 #116: 손익 · 현금흐름표 · 기준값 (기본주당이익 · 자본금 ÷ 액면가) · 경계값 ──────────────
def only(rs, k, sjs, per_share=False):
    """한 보고서에서 sjs 표의 금액만 k 배 (주당 금액 줄은 그대로 — 진짜 단위 오류처럼)."""
    out = []
    for x in rs:
        x = dict(x)
        if (x.get("sj_div") or "").strip() in sjs and (per_share or "PerShare" not in (x.get("account_id") or "")):
            for c in ("thstrm_amount", "thstrm_add_amount", "frmtrm_amount", "frmtrm_add_amount", "bfefrmtrm_amount"):
                v = F._num(x.get(c))
                if v is not None:
                    x[c] = str(v * k)
        out.append(x)
    return out


def sh_of(t):
    return PX[t][1]


def test_the_scale_line_is_pinned_at_100():
    a = {"eq": 100.0}
    for r, flagged in ((14.4, False), (0.08, False), (99.0, False), (100.0, True), (0.0099, True), (1000.0, True)):
        u = F.unit_check({"eq": 100.0, "bs2": {"eq": 100.0 * r}})
        assert ("scale" in u["why"]) is flagged, (r, u)
    assert F.UNIT_SCALE_MAX == 100.0 and F.UNIT_ANCHOR_MAX == 300.0 and F.UNIT_EPS_MIN == 10.0
    # 2026-11-12 발행본에서 가장 먼 진짜 회사 두 곳 (주주 몫 자본 · 최신 분기 ÷ 사업보고서): 큐로셀 14.4배 · 비트맥스 0.08배
    assert F.unit_check({"eq": 50.3, "bs2": {"eq": 725.2}})["why"] == []
    assert F.unit_check({"eq": 106.1, "bs2": {"eq": 8.9}})["why"] == []


def test_an_income_statement_alone_in_the_wrong_unit_is_caught():
    """재무상태표는 맞고 손익계산서만 1,000배 (주당 금액은 그대로): 지난해 칸(is)과 기본주당이익(eps)이 잡아요."""
    t = "040610"
    s, fin = company(t, q=only(rows(t, 2026, "11012"), 1000, ("IS", "CIS")))
    u = F.unit_check(fin, sh_of(t))
    assert "scale" not in u["why"] and "bs" not in u["why"]
    assert "is" in u["why"] and "eps" in u["why"], u
    assert 900 < u["flows"]["is"] < 1100 and u["eps"]["q"] > 300


def test_a_cash_flow_statement_alone_in_the_wrong_unit_is_caught():
    t = "040610"
    _, fin = company(t, q=only(rows(t, 2026, "11012"), 1000, ("CF",)))
    u = F.unit_check(fin, sh_of(t))
    assert u["why"] == ["cf"], u


def test_last_years_quarter_in_the_wrong_unit_is_caught_by_the_columns_and_the_eps():
    t = "040610"
    _, fin = company(t, qp=only(rows(t, 2025, "11012"), 1000, ("IS", "CIS", "CF")))
    u = F.unit_check(fin, sh_of(t))
    assert {"is", "cf", "eps"} <= set(u["why"]) and u["flows"]["is"] < 0.01 and u["eps"]["qp"] > 300, u


def test_an_annual_only_company_is_checked_by_the_reported_eps():
    """분기 보고서가 없는 회사 (3~5월 · 사업보고서만): 보고서 사이 배율은 못 보지만 사업보고서의 기본주당이익으로 잡아요."""
    t = "040610"
    fin = F.parse_dart_list(only(rows(t, 2025, "11011"), 1000, ("BS", "IS", "CIS", "CF")))["_fin"]
    fin["fs"] = "CFS"
    u = F.unit_check(fin, sh_of(t))
    assert u["scale"] == {} and u["why"] == ["eps"] and u["eps"]["fy"] > 300, u
    good = F.parse_dart_list(rows(t, 2025, "11011"))["_fin"]
    good["fs"] = "CFS"
    assert F.unit_check(good, sh_of(t))["why"] == [] and 0.5 < F.unit_check(good, sh_of(t))["eps"]["fy"] < 3


def test_the_eps_anchor_needs_a_real_eps_and_the_same_sign():
    fin = {"nio": 100.0, "ni": [100.0, 0, 0], "eq": 1000.0, "fs": "CFS"}
    sh = 1_000_000                                    # 100억 ÷ 100만주 = 10,000원
    for rep_eps, flagged in ((10000, False), (40, False), (30, True), (5, False), (-30, False), (-10000, False), (None, False)):
        u = F.unit_check(dict(fin, epsRep=rep_eps), sh)
        assert ("eps" in u["why"]) is flagged, (rep_eps, u)       # 5원 미만(바닥 10원) · 부호가 다르면 견주지 않아요 (−30: 크기는 걸릴 만해도)


def test_the_capital_anchor():
    t = "040610"
    s, fin = company(t)
    s["_bas"] = {"par3": [1000.0, 1000.0, 1000.0]}
    s["_cap"] = {"cs3": [170.43598, 170.43598, 170.43598], "k": "all", "src": "total"}     # 자본금 170.4억 ÷ 1,000원 = 17,043,598주 (SG&G)
    assert F.cap_ratio(s, fin) == pytest.approx(1.0)
    s["_cap"]["cs3"][0] = 170435.98                                                      # 재무상태표가 1,000배
    assert F.cap_ratio(s, fin) == pytest.approx(1000.0) and "cap" in F.unit_check(fin, sh_of(t), F.cap_ratio(s, fin))["why"]
    assert F.cap_ratio(dict(s, _cap={**s["_cap"], "src": "paid"}), fin) is None           # 납입자본(주식발행초과금 섞임)은 안 봐요
    assert F.cap_ratio(dict(s, _bas={"par3": [None, 1000.0, 1000.0]}), fin) is None       # 액면가를 모르면 (무액면주식)
    s["_cap"]["cs3"][0] = 170.43598 * 14.6                                               # 감자 1/14.6 (앱토크롬처럼) — 300배 안
    assert "cap" not in F.unit_check(fin, sh_of(t), F.cap_ratio(s, fin))["why"]


def test_coverage_is_counted_and_loud_while_most_statements_are_unchecked(capsys):
    cos = [company(t) for t in BAD + REAL]
    for _, fin in cos[2:]:
        for src in (fin, fin["bs2"], fin["bsP"]):
            src.pop("bal", None)                                                         # 두 곳은 예전 캐시처럼
    kr = [s for s, _ in cos]
    fm = {s["t"]: fin for s, fin in cos}
    extra = F.fill_multiples(kr, fm, {})
    g = F.unit_guard(kr, fm, extra)
    assert g["cover"] == {"v": 1, "companies": 4, "checked": 2, "unchecked": 2, "noScale": 0, "anchor": 4, "eps": 4, "cap": 0,
                          "flows": 4, "notWon": 0, "parLow": 0, "hit": 2}
    out = capsys.readouterr().out
    assert "· 공시 단위 확인이 본 회사 4곳" in out                                          # 반반이면 아직 크게 알리지 않아요
    cos[1][1].pop("bal")
    g = F.unit_guard([cos[1][0]], {cos[1][0]["t"]: cos[1][1]}, {})
    assert g["cover"]["unchecked"] == 1 and "  !! 공시 단위 확인이 본 회사 1곳" in capsys.readouterr().out


def test_main_writes_the_coverage_for_the_gate():
    src = inspect.getsource(F.main)
    assert '"unitChkCover": unit_cover' in src and "unit_cover = unit_guard(" in src
    assert "unitChkCover" in F.UNITS


# ── 2c. 리뷰 #118: 원화가 아닌 재무제표 · 무액면주식 · 남은 갈래 ──────────────────────────────
def usd_filer(t, nk, shr, cs, eps_usd, eq, ni, cur="USD"):
    """두산밥캣 · 아남전자 모양 (2025 사업보고서 · 2026-11-13 OpenDART): 재무제표는 달러 (억 달러), 액면가는 배당 표의 원, 주식 수는 오늘 보통주.
    자본금 0.431억 달러 ÷ 500원 = 86,200주 → 오늘 주식 수의 0.0009배 (이 리뷰 전에는 cap 으로 잘못 걸렸어요)."""
    s = {"t": t, "nk": nk, "cls": "kr", "price": 10000.0, "shr": shr, "cap": 1.0, "_bas": {"par3": [500.0, 500.0, 500.0]},
         "_cap": {"cs3": [cs, cs, cs], "k": "all", "src": "total"}}
    fin = {"cur": cur, "fs": "CFS", "eq": eq, "eqo": eq, "ni": [ni, ni, ni], "nio": ni, "cs3": [cs, cs, cs], "epsRep": eps_usd,
           "bal": [eq * 2e8, eq * 1e8, eq * 1e8]}
    return s, fin


def test_usd_filers_are_not_flagged_by_the_won_anchors(capsys):
    cos = [usd_filer("241560", "두산밥캣", 95856065, 0.431, 3.1, 60.0, 3.0),
           usd_filer("008700", "아남전자", 77124820, 0.345, 0.02, 0.8, 0.02)]
    for s, fin in cos:
        assert F.not_won(s, fin) and F.cap_ratio(s, fin) is None                                 # 달러 자본금 ÷ 원 액면가는 안 봐요
        assert F.unit_check(fin, F.per_share_count(s, {}), 0.0009)["why"] == ["cap"]              # 이 리뷰 전의 값이면 걸렸어요
    kr = [s for s, _ in cos]
    g = F.unit_guard(kr, {s["t"]: fin for s, fin in cos}, {})
    assert g["hit"] == {} and all("unitChk" not in s for s in kr)
    assert g["cover"]["notWon"] == 2 and g["cover"]["cap"] == 0 and g["cover"]["eps"] == 0 and g["cover"]["anchor"] == 0
    assert "원화가 아닌 재무제표라 기준값을 보지 않음 2" in capsys.readouterr().out
    # 해외 기업(9…)도: 통화를 모르는 원 재무제표처럼 보여도 기준값은 보지 않아요
    s, fin = usd_filer("900290", "GRT", 92751685, 0.431, 3.1, 60.0, 3.0, cur=None)
    assert F.not_won(s, fin) and F.unit_guard([s], {s["t"]: fin}, {})["hit"] == {}


def test_a_non_won_company_with_a_real_eps_is_not_eps_checked():
    """리뷰 #118 3차 S-A: 기본주당이익이 10 이상인 원화가 아닌 회사(JTC 모양 · 엔화 · 해외 기업, 그리고 엔화로 내는 국내 회사)도 기준값을
    보지 않아요 — 봤다면 1/1,000 로 걸렸을 값이에요."""
    cos = []
    for t, nk, cur in (("950170", "JTC 모양", "JPY"), ("200000", "엔화 국내", "JPY")):
        s = {"t": t, "nk": nk, "cls": "kr", "price": 10000.0, "shr": 46721440, "cap": 0.5}
        fin = {"cur": cur, "fs": "CFS", "eq": 100.0, "eqo": 100.0, "nio": 10.0, "ni": [10.0, 9.0, 8.0], "epsRep": 21000.0,
               "bal": [2e10, 1e10, 1e10]}                                          # 10억 엔 ÷ 4,672만 주 = 21엔 ≠ 21,000 (1,000배)
        assert F.unit_check(fin, F.per_share_count(s, {}))["why"] == ["eps"]          # 원 기준으로 견주면 걸려요
        cos.append((s, fin))
    g = F.unit_guard([s for s, _ in cos], {s["t"]: f for s, f in cos}, {})
    assert g["hit"] == {} and g["cover"]["eps"] == 0 and g["cover"]["anchor"] == 0 and g["cover"]["notWon"] == 2


@pytest.mark.parametrize("typed", ["5.000", "0.5", "5"])
def test_a_hand_typed_par_under_100_won_is_not_compared(typed, capsys):
    """리뷰 #118 3차 S-B: 한국 상장사 액면가는 100원 아래가 없어요. 배당 표에 '5.000' · '0.5' · '5' 처럼 적혀 있으면 (5,000원 · 500원을 잘못 적은
    값) 자본금 ÷ 액면가가 1,000배 넘게 보여 맞는 회사가 비워져요 → 견주지 않고 몇 곳인지 로그에 남겨요."""
    bas = F.parse_dart_basis([{"se": "주당액면가액(원)", "stock_knd": "", "thstrm": typed, "frmtrm": typed, "lwfr": typed}])
    s, fin = usd_filer("200000", "액면가 오기", 95856065, 431.0, 3100.0, 6000.0, 300.0, cur=None)   # 자본금 431억 ÷ 500원 ≈ 오늘 주식 수
    s["_bas"] = bas
    assert 0 < F.par_raw(s) < 100 and F.par_value(s) is None and F.cap_ratio(s, fin) is None
    g = F.unit_guard([s], {s["t"]: fin}, {})
    assert g["hit"] == {} and g["cover"]["parLow"] == 1 and g["cover"]["cap"] == 0
    assert f"!! 배당 표의 액면가가 100원 미만이라 자본금 ÷ 액면가를 보지 않은 회사 1곳 (손으로 적다 틀린 값 같아요): 200000 액면가 오기 {float(typed):g}원" \
        in capsys.readouterr().out
    s["_bas"] = {"par3": [100.0] * 3}                                                          # 100원부터는 봐요
    assert F.par_value(s) == 100.0 and F.cap_ratio(s, fin) is not None
    assert F.UNIT_PAR_MIN == 100.0


def test_the_anchor_limit_is_300_not_100():
    """리뷰 #118 3차 N-a: 기준값(eps · cap)은 300배부터 (보고서 사이 배율 100배와 따로)."""
    fin = {"nio": 100.0, "ni": [100.0, 0, 0], "eq": 1000.0, "fs": "CFS"}
    for r, flagged in ((150.0, False), (299.0, False), (300.0, True), (1 / 150, False), (1 / 300, True)):
        assert ("cap" in F.unit_check(fin, None, r)["why"]) is flagged, r
        u = F.unit_check(dict(fin, epsRep=10000.0 / r), 1_000_000)                            # 비 = 10,000원 ÷ 기본주당이익
        assert ("eps" in u["why"]) is flagged, (r, u["eps"])


def test_a_malformed_cache_entry_stops_the_run_and_names_the_company():
    """리뷰 #118 3차 N-e: unit_guard 는 감싸서 넘기지 않아요 — 이상한 항목이면 그 회사 이름과 함께 실행을 멈춰요."""
    s, fin = company("040610")
    fin["bs2"] = "oops"
    with pytest.raises(RuntimeError, match="공시 단위 확인: 040610 SG&G 의 재무제표 캐시 항목을 읽지 못했어요"):
        F.unit_guard([s], {"040610": fin}, {})


def test_a_won_company_at_1000_times_is_still_flagged_by_the_capital_anchor():
    s, fin = usd_filer("200000", "원화 회사", 95856065, 431.0 * 1000, 3100.0, 6000.0, 300.0, cur=None)   # 자본금 431억 → 1,000배로 읽힘
    assert not F.not_won(s, fin) and F.cap_ratio(s, fin) == pytest.approx(431e8 * 1000 / 500 / 95856065)
    g = F.unit_guard([s], {s["t"]: fin}, {})
    assert "cap" in g["hit"]["200000"] and g["cover"]["notWon"] == 0
    s, fin = usd_filer("200000", "원화 회사", 95856065, 431.0, 3100.0, 6000.0, 300.0, cur=None)          # 맞게 읽으면 0.9배
    assert 0.8 < F.cap_ratio(s, fin) < 1.0 and F.unit_guard([s], {s["t"]: fin}, {})["hit"] == {}


@pytest.mark.parametrize("par", ["-", "무액면", "0", "", None])
def test_a_no_par_company_is_not_compared(par):
    """무액면주식 · 액면가가 '-' · 0 · 빈 칸이면 자본금 ÷ 액면가를 보지 않아요 (배당 표 해석 parse_dart_basis 부터)."""
    rows_ = [{"se": "주당액면가액(원)", "stock_knd": "", "thstrm": par, "frmtrm": par, "lwfr": par},
             {"se": "현금배당금총액(백만원)", "stock_knd": "", "thstrm": "100", "frmtrm": "100", "lwfr": "100"}]
    bas = F.parse_dart_basis(rows_)
    assert bas["par3"] == [None, None, None] or bas["par3"] == [0.0, 0.0, 0.0], bas
    s, fin = usd_filer("200000", "무액면", 1_000_000, 50.0, 1000.0, 100.0, 10.0, cur=None)
    s["_bas"] = bas
    assert F.cap_ratio(s, fin) is None
    assert F.unit_guard([s], {s["t"]: fin}, {})["cover"]["cap"] == 0


def test_the_capital_anchor_uses_common_shares_when_the_capital_is_common_only():
    """_cap k == "common" (보통주 자본금만): 오늘 보통주 수와 · 아니면 우선주를 더한 주식 수와."""
    s, fin = usd_filer("005380", "현대차 모양", 203466492, 1017.3, 3000.0, 1000.0, 100.0, cur=None)
    s["_bas"] = {"par3": [5000.0] * 3}
    pref = {"00538": [22839037, 34257047, 2321926]}
    s["_cap"] = {"cs3": [1017.3] * 3, "k": "common", "src": "total"}                          # 보통주 자본금 ÷ 5,000원 = 보통주 수
    assert F.cap_ratio(s, fin, pref) == pytest.approx(1017.3e8 / 5000 / 203466492)
    s["_cap"]["k"] = "all"
    assert F.cap_ratio(s, fin, pref) == pytest.approx(1017.3e8 / 5000 / (203466492 + 22839037 + 34257047 + 2321926))


def test_the_quarter_eps_uses_owners_profit_on_consolidated_and_total_on_separate():
    """분기 eps 기준값: 연결(CFS)은 지배주주 순이익(nio), 별도(OFS)는 순이익(ni) — 둘이 다르면 비가 달라져요."""
    q = {"nio": 100.0, "ni": 1e5, "epsYtd": 10000.0}
    base = {"eq": 1000.0, "bs2": {"eq": 1000.0}, "qChk": {"q": q, "qp": {}}}
    sh = 1_000_000                                                                              # 100억 ÷ 100만주 = 10,000원
    u = F.unit_check(dict(base, fs="CFS"), sh)
    assert u["eps"]["q"] == pytest.approx(1.0) and "eps" not in u["why"]
    u = F.unit_check(dict(base, fs="OFS"), sh)
    assert u["eps"]["q"] == pytest.approx(1000.0) and "eps" in u["why"]                        # 별도는 순이익 1,000배
    u = F.unit_check(dict(base, fs="CFS", qChk={"q": {"ni": 100.0, "epsYtd": 10000.0}, "qp": {}}), sh)
    assert u["eps"]["q"] == pytest.approx(1.0)                                                  # 지배주주 줄이 없으면 순이익


def test_the_income_check_is_the_median_of_revenue_and_profit():
    """is: 매출 · 순이익 비의 중앙값 (두 개면 로그 평균) — 한 줄만 1,000배면 약 32배라 안 걸리고, 둘 다면 걸려요. 지난해 값이 0.1억 미만인 줄은 빼요."""
    def u(p0, qp):
        return F.unit_check({"eq": 100.0, "qChk": {"q": {"p0": p0}, "qp": qp}})
    assert u({"rev": 1000.0, "ni": 50.0}, {"rev": 1.0, "ni": 50.0})["flows"]["is"] == pytest.approx(1000 ** 0.5)
    assert "is" not in u({"rev": 1000.0, "ni": 50.0}, {"rev": 1.0, "ni": 50.0})["why"]
    assert "is" in u({"rev": 1000.0, "ni": 50000.0}, {"rev": 1.0, "ni": 50.0})["why"]
    x = u({"rev": 1000.0, "ni": 50.0}, {"rev": 1.0, "ni": 0.05})                              # 순이익 0.05억: 바닥(0.1억) 아래라 빼요
    assert x["flows"]["is"] == pytest.approx(1000.0) and "is" in x["why"]
    assert u({"rev": 0.5, "ni": 0.5}, {"rev": 0.09, "ni": 0.09})["flows"]["is"] is None       # 둘 다 바닥 아래면 볼 줄이 없어요
    assert u({"ocf": 500.0}, {"ocf": 0.09})["flows"]["cf"] is None                             # 현금흐름도 바닥 0.1억
    assert u({"ocf": 500.0}, {"ocf": 0.1})["flows"]["cf"] == pytest.approx(5000.0) and "cf" in u({"ocf": 500.0}, {"ocf": 0.1})["why"]


# ── 3. 관문 ────────────────────────────────────────────────────
UNIT_ROW = "공시 단위 확인 회사의 숫자 비움 (unitChk)"
LOW_ROW = "PBR 0.1 미만 국내 회사 (unitChk 없음 · 경고만)"


def flag(cur, t, why=("scale",)):
    """파이프라인(unit_guard · build_corp)이 하는 대로 한 회사를 비워요 (incCheck 의 영수증 수도)."""
    s = next(x for x in cur["data"]["stocks"] if x["t"] == t)
    c = comp(cur, t)
    for k in F.UNIT_BLANK + ("vz", "qz"):
        s.pop(k, None)
    s["unitChk"] = list(why)
    e = c.get("epsIn")
    if e:
        cur["data"]["incCheck"]["epsB"][e["b"]] -= 1
        cur["data"]["incCheck"]["epsP"][e["p"]] -= 1
    c.update(rev=[None] * 3, op=[None] * 3, ni=[None] * 3, eq=None, dcfReady=False, vz=None, qz=None, **{k: None for k in F.UNIT_BLANK})
    for k in F.UNIT_BLANK_CORP:
        c.pop(k, None)
    c["flRan"] = []
    c["unitChk"] = list(why)
    return s, c


def plain(cur):
    """가짜 데이터의 아주 낮은 PBR (가격 ÷ 5만원 BPS) 은 자본을 늘려 PBR 1 로 (경고 줄을 보려고 · 가격은 그대로 · PBR = 종가 ÷ 영수증)."""
    for s in cur["data"]["stocks"]:
        if s.get("cls") == "kr" and V.num(s.get("pbr")) is not None and s["pbr"] < 0.1:
            c = next((x for x in cur["corp"]["companies"] if x["t"] == s["t"]), None)
            if c:
                c["bpsIn"]["eq"] = round(s["price"] * c["bpsIn"]["sh"] / 1e8, 1)
                c["bps"] = s["bps"] = round(c["bpsIn"]["eq"] * 1e8 / c["bpsIn"]["sh"], 0)
                c["pbr"] = s["pbr"] = round(s["price"] / c["bps"], 2)
    return cur


def test_gate_passes_a_flagged_company_whose_numbers_are_all_blank(pair):
    cur, prev = pair
    plain(cur)
    flag(cur, "200000")
    rep = check(cur, prev)
    got = rows_of(rep)
    assert got[UNIT_ROW][3] == "PASS" and got[UNIT_ROW][1].startswith("1곳 · 남은 칸 0"), got[UNIT_ROW]
    assert got[LOW_ROW][3] == "PASS" and got[LOW_ROW][1] == "0곳"
    assert not rep.failed, rep.table()
    assert any(t.startswith("공시 단위 확인으로 숫자를 비운 회사") for t, _ in rep.details)


@pytest.mark.parametrize("where,key,val", [("data", "per", 0.0), ("data", "pbr", 0.0), ("data", "eps", 1.0), ("data", "bps", 1.0),
                                           ("data", "roe", 3.0), ("data", "debt", 10.0), ("data", "opm", 1.0), ("data", "g3", 1.0),
                                           ("data", "vz", 100), ("data", "qz", 5), ("corp", "pbr", 0.0), ("corp", "eq", 1.0),
                                           ("corp", "rev", [1.0, None, None]), ("corp", "op", [None, 1.0, None]),
                                           ("corp", "ni", [None, None, 2.0]),
                                           ("corp", "bpsIn", {"eq": 1.0}), ("corp", "epsIn", {"ni": 1.0}), ("corp", "roeIn", {}),
                                           ("corp", "evR", 0.45), ("corp", "pcf", 1.0), ("corp", "fl", {"cr": 57.0}),
                                           ("corp", "bq", "2026.2Q"), ("corp", "dcfReady", True), ("corp", "flRan", ["cr"])])
def test_gate_fails_when_a_flagged_company_still_carries_a_blanked_number(pair, where, key, val):
    cur, prev = pair
    plain(cur)
    s, c = flag(cur, "200000")
    (s if where == "data" else c)[key] = val
    row = fails(cur, prev, UNIT_ROW)
    assert "200000" in row[1], row


def test_gate_fails_when_the_mark_is_missing_odd_or_on_one_file_only(pair):
    cur, prev = pair
    plain(cur)
    s, c = flag(cur, "200000")
    c["unitChk"] = ["scale", "bs"]                                    # 두 파일이 달라요
    fails(cur, prev, UNIT_ROW)
    c["unitChk"] = s["unitChk"] = ["oops"]                            # 모르는 이유
    fails(cur, prev, UNIT_ROW)
    c["unitChk"] = s["unitChk"] = []                                  # 빈 목록
    fails(cur, prev, UNIT_ROW)
    s["unitChk"] = ["scale"]
    c.pop("unitChk")                                                  # corp.json 에 표시가 없음
    fails(cur, prev, UNIT_ROW)
    c["unitChk"] = ["scale"]
    s.pop("unitChk")                                                  # corp.json 에만
    row = fails(cur, prev, UNIT_ROW)
    assert "corp.json 에만 unitChk" in row[1]


def test_gate_warns_by_name_about_low_pbr_companies_that_were_not_flagged(pair):
    cur, prev = pair
    plain(cur)
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "200010")
    c = comp(cur, "200010")
    s["pbr"] = c["pbr"] = 0.09                                         # SG&G 처럼
    c["bpsIn"]["eq"] = round(s["price"] / 0.09 * c["bpsIn"]["sh"] / 1e8, 1)
    c["bps"] = s["bps"] = round(c["bpsIn"]["eq"] * 1e8 / c["bpsIn"]["sh"])
    rep = check(cur, prev)
    row = rows_of(rep)[LOW_ROW]
    assert row[3] == "WARN" and row[1].startswith("1곳: 200010") and "PBR 0.09" in row[1], row
    assert not rep.failed, rep.table()                                # 경고만 (발행은 막지 않아요)
    flag(cur, "200010")                                               # 걸린 회사는 경고 목록에 없어요
    assert rows_of(check(cur, prev))[LOW_ROW][3] == "PASS"


def low_pbr(cur, t, pbr=0.09):
    """한 가짜 회사를 PBR 0.09 로 (자본을 늘려 · PBR = 종가 ÷ 영수증이 맞게) → 그 회사의 bpsIn.eq."""
    s = next(x for x in cur["data"]["stocks"] if x["t"] == t)
    c = comp(cur, t)
    c["bpsIn"]["eq"] = round(s["price"] / pbr * c["bpsIn"]["sh"] / 1e8, 1)
    c["bps"] = s["bps"] = round(c["bpsIn"]["eq"] * 1e8 / c["bpsIn"]["sh"])
    c["pbr"] = s["pbr"] = round(s["price"] / c["bps"], 2)
    assert s["pbr"] < 0.1
    return c["bpsIn"]["eq"]


def test_gate_stays_quiet_for_a_checked_company_while_its_equity_stays_in_the_band(pair, monkeypatch):
    cur, prev = pair
    plain(cur)
    eq = low_pbr(cur, "200010")
    monkeypatch.setattr(V, "PBR_LOW_CHECKED", {"200010": {"date": "2026-11-13", "eq": eq, "why": "시험 · 공시 rcept 20260814001690 확인"}})
    rep = check(cur, prev)
    row = rows_of(rep)[LOW_ROW]
    assert row[3] == "PASS" and row[1] == "0곳 · 확인된 회사 1곳 조용히 넘김", row        # 목록 + 자본이 그대로 → 경고 없음, 수는 남겨요
    assert any(t.startswith("PBR 0.1 미만 · 사람이 공시를 확인해 조용히 넘긴 회사") and "200010" in " ".join(x) for t, x in rep.details)
    monkeypatch.setattr(V, "PBR_LOW_CHECKED", {"200010": {"date": "2026-11-13", "eq": round(eq * 1.19, 1), "why": "시험"}})
    assert rows_of(check(cur, prev))[LOW_ROW][3] == "PASS"                              # ±20% 안 (19%)
    assert not check(cur, prev).failed


def test_gate_warns_when_a_checked_companys_equity_moved_or_the_company_is_not_listed(pair, monkeypatch):
    cur, prev = pair
    plain(cur)
    eq = low_pbr(cur, "200010")
    low_pbr(cur, "200020")
    monkeypatch.setattr(V, "PBR_LOW_CHECKED", {"200010": {"date": "2026-11-13", "eq": round(eq / 1.25, 1), "why": "시험"}})   # 자본이 25% 움직였어요
    row = rows_of(check(cur, prev))[LOW_ROW]
    assert row[3] == "WARN" and row[1].startswith("2곳: 200010") and "확인한 자본" in row[1] and "200020" in row[1], row
    assert "조용히 넘김" not in row[1]
    monkeypatch.setattr(V, "PBR_LOW_CHECKED", {"200010": {"date": "2026-11-13", "eq": eq, "why": "시험"}})
    row = rows_of(check(cur, prev))[LOW_ROW]
    assert row[3] == "WARN" and row[1].startswith("1곳: 200020") and row[1].endswith("확인된 회사 1곳 조용히 넘김"), row   # 목록에 없는 회사는 그대로 경고
    monkeypatch.setattr(V, "PBR_LOW_CHECKED", {"200020": {"date": "2026-11-13", "eq": 1.0, "why": "시험"}})          # 다른 회사의 자본 (밴드 밖)
    assert rows_of(check(cur, prev))[LOW_ROW][1].startswith("2곳:")


def test_checked_company_with_unitchk_is_never_on_the_quiet_list(pair, monkeypatch):
    cur, prev = pair
    plain(cur)
    eq = low_pbr(cur, "200010")
    monkeypatch.setattr(V, "PBR_LOW_CHECKED", {"200010": {"date": "2026-11-13", "eq": eq, "why": "시험"}})
    flag(cur, "200010")                                                                 # 걸렸으면 실패 줄이 봐요 (조용히 넘기지 않아요)
    got = rows_of(check(cur, prev))
    assert got[LOW_ROW][1] == "0곳" and got[UNIT_ROW][3] == "PASS" and got[UNIT_ROW][1].startswith("1곳")


def test_the_checked_list_names_its_filings():
    assert set(V.PBR_LOW_CHECKED) == {"040610", "109960"} and V.PBR_LOW_BAND == 0.20
    for t, ck in V.PBR_LOW_CHECKED.items():
        assert dt.date.fromisoformat(ck["date"]) and ck["eq"] > 0, t
        assert re.search(r"rcept \d{14}", ck["why"]), t                                  # 확인한 공시의 접수번호
        assert re.fullmatch(r"Jack's yes, \d{4}-\d{2}-\d{2}", ck.get("yes") or ""), t      # 회사마다 Jack 의 승인 (Jack 2026-11-13)
    assert V.PBR_LOW_CHECKED["040610"]["eq"] == 5085.1 and V.PBR_LOW_CHECKED["109960"]["eq"] == 3617.6   # 2026-11-12 발행본 bpsIn.eq
    runbook = open(os.path.join(ROOT, "docs", "RUNBOOK.md"), encoding="utf-8").read()
    assert "PBR_LOW_CHECKED" in runbook and "SG&G and 앱토크롬: Jack's yes, 2026-11-13" in runbook


PER_ROW = "PER 0.1 미만 국내 회사 (unitChk 없음 · 경고만)"


def test_gate_warns_by_name_about_per_under_0_1_that_was_not_flagged(pair):
    cur, prev = pair
    plain(cur)
    assert rows_of(check(cur, prev))[PER_ROW][1] == "0곳"
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "200010")
    c = comp(cur, "200010")
    c["epsIn"]["ni"] = round(s["price"] / 0.02 * c["epsIn"]["sh"] / 1e8, 1)             # 손익계산서만 1,000배처럼: PER 0.0
    c["eps"] = s["eps"] = round(c["epsIn"]["ni"] * 1e8 / c["epsIn"]["sh"])
    c["per"] = s["per"] = round(s["price"] / c["eps"], 1)
    rep = check(cur, prev)
    row = rows_of(rep)[PER_ROW]
    assert row[3] == "WARN" and row[1].startswith("1곳: 200010") and "PER 0.1" not in row[1] and f"PER {s['per']:.1f}" in row[1], row
    assert not rep.failed, rep.table()
    flag(cur, "200010")
    assert rows_of(check(cur, prev))[PER_ROW][1] == "0곳"                              # 걸린 회사는 실패 줄이 봐요


def test_gate_shows_the_coverage_in_the_value_of_the_blanking_row(pair):
    """확인 범위는 비움 줄의 값 칸에 (그 줄은 범위로 실패하지 않아요). 리뷰 #118 S3 전에는 이 시험이 '기록이 없어도 통과'까지 고정했어요 —
    이제 기록이 없는 경우는 아래 기록 줄(unitChkCover)이 봐요 (직전 발행본에 있었으면 실패 · 둘 다 없으면 경고)."""
    cur, prev = pair
    plain(cur)
    row = rows_of(check(cur, prev))[UNIT_ROW]
    assert row[3] == "PASS" and row[1].endswith("확인 범위 기록(unitChkCover) 없음"), row
    cur["data"]["unitChkCover"] = {"v": 1, "companies": 2400, "checked": 30, "unchecked": 2370, "noScale": 145, "anchor": 2128,
                                   "eps": 2128, "cap": 2300, "flows": 0, "notWon": 21, "hit": 0}
    row = rows_of(check(cur, prev))[UNIT_ROW]
    assert row[3] == "PASS" and "본 회사 2400 (자산=부채+자본 모두 봄 30 · 못 본 재무제표 있음 2370 · 분기 비교 없음 145 · 기본주당이익·자본금으로 봄 2128 · " \
        "지난해 칸으로 봄 0 · 원화 아님(기준값 안 봄) 21)" in row[1], row


COV_ROW = "공시 단위 확인 기록 (unitChkCover)"
HIT_ROW = "unitChkCover.hit = unitChk 종목 수"
MOVE_ROW = "공시 단위 확인 회사 바뀜 (unitChk · 경고만)"


def cover(hit=0):
    return {"v": 1, "companies": 2400, "checked": 30, "unchecked": 2370, "noScale": 145, "anchor": 2128, "eps": 2128, "cap": 2300,
            "flows": 0, "notWon": 21, "hit": hit}


def test_gate_fails_when_the_check_stopped_writing_its_record(pair):
    """리뷰 #118 S3(a) · 새 실패 줄 (Jack's yes, 2026-11-13): 직전 발행본에 unitChkCover 가 있었는데 이번 파일에 없으면 '확인이 돌지 않음' — 실패.
    둘 다 없으면 그 전 형식 (경고만 · incCheck 와 같은 방식). 있으면 통과."""
    cur, prev = pair
    plain(cur)
    got = rows_of(check(cur, prev))
    assert got[COV_ROW][3] == "WARN" and "직전 발행본에도 없어요" in got[COV_ROW][1] and HIT_ROW not in got
    prev["data"]["unitChkCover"] = cover()
    row = fails(cur, prev, COV_ROW)
    assert "직전 발행본에는 있었어요" in row[1], row
    cur["data"]["unitChkCover"] = cover()
    rep = check(cur, prev)
    got = rows_of(rep)
    assert got[COV_ROW][3] == "PASS" and got[HIT_ROW][3] == "PASS" and not rep.failed, rep.table()
    cur["data"]["unitChkCover"] = dict(cover(), v=2)
    fails(cur, prev, COV_ROW)
    cur["data"].pop("unitChkCover")                                                     # 발행 모드가 아니면 직전 발행본을 보지 않아요 → 경고만
    assert rows_of(check(cur, prev, mode="live"))[COV_ROW][3] == "WARN"


@pytest.mark.parametrize("hit", [1, None, "0", True, 0.0])
def test_gate_fails_when_the_records_count_differs_from_the_flagged_stocks(pair, hit):
    """리뷰 #118 S3(b) · 새 실패 줄 (Jack's yes, 2026-11-13): unitChkCover.hit 는 data.json 의 unitChk 종목 수와 같아야 해요 (확인 뒤에 종목이 바뀌었으면
    실패). 바깥 장애(DART · 캐시 · 야후)로는 다를 수 없어요 — validate_data.check_unit_ran 설명."""
    cur, prev = pair
    plain(cur)
    cur["data"]["unitChkCover"] = dict(cover(), hit=hit)
    fails(cur, prev, HIT_ROW)


def test_gate_fails_a_record_without_a_version_and_a_true_count(pair):
    """리뷰 #118 3차 N-a: 기록에 v 가 없으면 실패 · 걸린 종목 1곳에 hit: true 도 실패 (True 는 1 이 아니에요)."""
    cur, prev = pair
    plain(cur)
    cur["data"]["unitChkCover"] = {k: v for k, v in cover().items() if k != "v"}
    row = fails(cur, prev, COV_ROW)
    assert row[1].startswith("vNone"), row
    flag(cur, "200000")
    cur["data"]["unitChkCover"] = dict(cover(), hit=True)
    row = fails(cur, prev, HIT_ROW)
    assert row[1] == "기록 True · data.json 1곳", row


def test_gate_counts_the_flagged_stocks_for_the_record(pair):
    cur, prev = pair
    plain(cur)
    flag(cur, "200000")
    cur["data"]["unitChkCover"] = cover(hit=1)
    got = rows_of(check(cur, prev))
    assert got[HIT_ROW][3] == "PASS" and got[HIT_ROW][1] == "기록 1 · data.json 1곳", got[HIT_ROW]
    cur["data"]["unitChkCover"] = cover(hit=0)
    fails(cur, prev, HIT_ROW)


def test_gate_warns_by_name_when_the_flagged_set_changes(pair, monkeypatch):
    """리뷰 #118 S1 (경고만): 통과 줄은 아침 확인에 가지 않아서, 새로 걸린 회사 · 풀린 회사를 이름과 함께 경고해요 (앞에서 10곳 + 수)."""
    cur, prev = pair
    plain(cur)
    got = rows_of(check(cur, prev))
    assert got[MOVE_ROW][3] == "PASS" and got[MOVE_ROW][1] == "새로 0곳 · 풀림 0곳"
    flag(cur, "200000")
    rep = check(cur, prev)
    row = rows_of(rep)[MOVE_ROW]
    assert row[3] == "WARN" and row[1].startswith("새로 1곳: 200000") and row[1].endswith("풀림 0곳"), row
    assert not rep.failed, rep.table()
    assert any(t.startswith("공시 단위 확인에 새로 걸린 회사") for t, _ in rep.details)
    p = next(x for x in prev["data"]["stocks"] if x["t"] == "200000")
    p["unitChk"] = ["scale"]
    assert rows_of(check(cur, prev))[MOVE_ROW][1] == "새로 0곳 · 풀림 0곳"                    # 어제도 걸렸으면 같아요
    q = next(x for x in prev["data"]["stocks"] if x["t"] == "200010")
    q["unitChk"] = ["eps"]
    row = rows_of(check(cur, prev))[MOVE_ROW]
    assert row[3] == "WARN" and row[1].startswith("새로 0곳 · 풀림 1곳: 200010"), row
    for x in cur["data"]["stocks"]:                                                       # 열두 곳이 새로 걸리면: 앞의 10곳 + 수
        if x["t"] in [f"2{n:05d}" for n in range(20, 140, 10)]:
            flag(cur, x["t"])
    row = rows_of(check(cur, prev))[MOVE_ROW]
    assert row[1].startswith("새로 12곳: ") and " 외 2곳 · 풀림 1곳" in row[1] and row[1].count(", ") == 9, row
    assert rows_of(check(cur, None, mode="live"))[MOVE_ROW][1] == "직전 발행본 없음 (비교 안 함)"
    assert V.UNIT_MOVE_SHOW == 10


MANY_ROW = "공시 단위 확인에 새로 걸린 회사 수 (20곳 이상이면 실패)"


def test_gate_fails_when_20_or_more_companies_are_newly_flagged(pair):
    """Jack 2026-11-13 (Q5): 한 번에 20곳 이상 새로 걸리면 실패 (19곳은 경고만) · 풀린 회사는 세지 않아요 · 직전 발행본이 없으면 실패하지 않아요."""
    assert V.UNIT_NEW_FLAGS_FAIL == 20
    cur, prev = pair
    plain(cur)
    codes = [x["t"] for x in cur["data"]["stocks"] if x["t"].startswith("2") and x.get("cls") == "kr"][:20]
    assert len(codes) == 20
    for t in codes[:19]:
        flag(cur, t)
    rep = check(cur, prev)
    got = rows_of(rep)
    assert got[MANY_ROW][3] == "PASS" and got[MANY_ROW][1] == "새로 19곳" and got[MOVE_ROW][3] == "WARN", got[MANY_ROW]
    assert MANY_ROW not in {x[0] for x in rep.failed}
    flag(cur, codes[19])
    row = fails(cur, prev, MANY_ROW)
    assert row[1] == "새로 20곳", row
    assert rows_of(check(cur, None, mode="live"))[MANY_ROW][3] == "PASS"                   # 직전 발행본 없음 → 실패하지 않아요
    assert rows_of(check(cur, prev, mode="bootstrap"))[MANY_ROW][3] == "PASS"
    # 풀린 회사는 세지 않아요: 어제는 그 20곳 + 다른 20곳이 걸렸고 오늘은 그 20곳만 → 새로 0 · 풀림 20 → 통과 (경고는 남아요)
    more = [x["t"] for x in cur["data"]["stocks"] if x["t"].startswith("2") and x.get("cls") == "kr"][20:40]
    assert len(more) == 20
    for x in prev["data"]["stocks"]:
        if x["t"] in codes or x["t"] in more:
            x["unitChk"] = ["scale"]
    got = rows_of(check(cur, prev))
    assert got[MANY_ROW][3] == "PASS" and got[MANY_ROW][1] == "새로 0곳", got[MANY_ROW]
    assert got[MOVE_ROW][3] == "WARN" and "풀림 20곳" in got[MOVE_ROW][1], got[MOVE_ROW]


def test_gate_leaves_foreign_issuers_out_of_the_low_pbr_row():
    """리뷰 #118 N1: 해외 기업(9…)은 PBR 이 낮아도 이 줄에 없어요 (금액이 원화가 아닐 수 있어 다른 줄이 봐요)."""
    kr = [{"t": "900290", "nk": "GRT", "cls": "kr", "pbr": 0.05, "per": 0.05}, {"t": "200010", "nk": "가", "cls": "kr", "pbr": 0.05, "per": 0.05}]
    rep = V.Report()
    V.check_unit(rep, {}, kr, {s["t"]: s for s in kr}, [], None)
    got = rows_of(rep)
    assert got[LOW_ROW][1] == "1곳: 200010 가 PBR 0.05" and got[LOW_ROW][3] == "WARN", got[LOW_ROW]
    assert got[PER_ROW][1] == "1곳: 200010 가 PER 0.1" and got[PER_ROW][3] == "WARN", got[PER_ROW]      # 0.05 를 한 자리로


def test_gate_and_pipeline_keep_their_lists_apart_but_in_step():
    """관문은 파이프라인과 따로 적어요. 파이프라인이 비우는 칸이 관문이 보는 칸 안에 모두 있어야 해요.
    리뷰 #118 N1: 두 쪽 목록을 시험에 그대로 적어 맞대요 (칸이 빠져도 늘어도 걸려요)."""
    assert F.UNIT_BLANK == DATA_BLANK and F.UNIT_BLANK_CORP == CORP_BLANK and F.UNIT_EXTRA_KEYS == EXTRA_BLANK
    assert V.UNIT_BLANK_DATA == DATA_BLANK + ("vz", "qz")
    assert V.UNIT_BLANK_CORP == ("eq", "evE", "evR", "pcf", "nio3", "nio3Hyb", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "fl", "flSrc", "flWhy")
    assert V.UNIT_BLANK_LISTS == ("rev", "op", "ni")
    assert set(F.UNIT_BLANK) <= set(V.UNIT_BLANK_DATA)
    assert set(F.UNIT_BLANK_CORP) - {"bq"} <= set(V.UNIT_BLANK_CORP)       # bq 는 관문이 따로 봐요
    assert set(F.UNIT_WHY) == set(V.UNIT_WHY) and F.UNIT_PBR_LOOK == V.UNIT_PBR_LOOK
    assert "unitChk" in F.UNITS


def test_the_served_files_shape_passes_the_gate_rows_once_blanked():
    """2026-11-12 발행본의 진코스텍 줄 (corp.json · data.json 그대로) 을 파이프라인처럼 비우면 관문 줄 문제가 없어요."""
    s = {"t": "250030", "nk": "진코스텍", "cls": "kr", "price": 9200.0, "pbr": 0.0, "per": 0.0, "eps": 777569.0, "bps": 6977676.0,
         "roe": 32.0, "debt": 177.0, "opm": 10.0, "g3": 57.9, "vz": 100, "qz": 99, "dps": 0.0}
    c = dict(s, rev=[486.5, 298.4, 195.2], op=[48.5, 11.5, -26.1], ni=[60.2, -0.4, -34.7], eq=188.0, bq="2026.2Q", dcfReady=True,
             flRan=["cr", "icr", "l3", "imp"], flSrc={"icr": "cf"}, evR=0.45, cash3=[0.0, 0.0, 0.0], eps3r=[2324.0, -16.0, -1340.0],
             roeIn={"ni": 60.2, "eq": 188.0, "b": "s", "p": "fy"}, epsIn={"ni": 29442.9, "b": "s", "p": "ttm", "sh": 3786533, "how": "ofs"},
             bpsIn={"eq": 264212.0, "b": "s", "sh": 3786533, "how": "ofs", "p": "ttm"}, epsFy=1590.0, epsRep=2324.0)
    assert V.unit_problems(dict(s, unitChk=["scale"]), dict(c, unitChk=["scale"]))           # 비우지 않았으면 문제
    for k in F.UNIT_BLANK + ("vz", "qz"):
        s.pop(k)
    s["unitChk"] = ["scale"]
    c.update(rev=[None] * 3, op=[None] * 3, ni=[None] * 3, eq=None, dcfReady=False, vz=None, qz=None, unitChk=["scale"],
             **{k: None for k in F.UNIT_BLANK})
    for k in F.UNIT_BLANK_CORP:
        c.pop(k, None)
    c["flRan"] = []
    assert V.unit_problems(s, c) == []
    assert c["cash3"] == [0.0, 0.0, 0.0] and c["eps3r"] == [2324.0, -16.0, -1340.0]        # 배당 표의 값은 남아요
