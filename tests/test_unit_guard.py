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
    fin["ttm"], fin["bs2"], fin["bsP"], fin["bq"] = t2["ttm"], t2["bs"], t2["bsP"], "2026.2Q"
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
        assert u["why"] == ["scale"], (t, u)
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
    assert guard["hit"] == {"250030": ["scale"], "002880": ["scale"]}
    assert [x.split(" ")[0] for x in guard["real"]] == ["040610", "109960"]
    for t in BAD:
        s, c = by[t], cby[t]
        assert s["unitChk"] == ["scale"] and c["unitChk"] == ["scale"]
        for k in FILED["data"]:
            assert k not in s, (t, k)                                       # 빈 칸 (0 이 아니에요)
            assert c.get(k) is None, (t, k)
        assert c["rev"] == [None] * 3 and c["op"] == [None] * 3 and c["ni"] == [None] * 3 and c["eq"] is None
        assert c["dcfReady"] is False and c["flRan"] == []
        for k in F.UNIT_BLANK_CORP:
            assert k not in c, (t, k)
        assert t not in extra or not any(k in extra[t] for k in F.UNIT_EXTRA_KEYS)
        assert s["dps"] == 0.0 and c["dps"] == 0.0 and c["fy"] == 2025      # 배당(별도 배당 표)과 보고서 연도는 남아요
    for t in REAL:
        s, c = by[t], cby[t]
        assert "unitChk" not in s and "unitChk" not in c
        assert s["pbr"] < 0.1 and c["pbr"] == s["pbr"] and c["bpsIn"]["eq"] > 1000 and s["vz"] is not None
    # 진짜 값: SG&G BPS = 주주 몫 자본 5,085.1억 ÷ 17,043,598주 · PBR 0.09
    assert by["040610"]["bps"] == round(5085.1e8 / 17043598) and by["040610"]["pbr"] == 0.09
    out = capsys.readouterr().out
    assert "!! 공시 단위 확인: 2곳 비움 (자산≠부채+자본 0 · 보고서 사이 배율 2)" in out
    assert "!! 공시 단위: 250030 진코스텍 [보고서 사이 배율" in out and "비운 값: per 0.0, pbr 0.0, eps 777,569.0" in out
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
        assert F.unit_check(fin)["why"] == ["scale"], k
    _, fin = company(t, qp=scaled(rows(t, 2025, "11012"), 1000))             # 지난해 같은 분기가 틀려도
    u = F.unit_check(fin)
    assert u["why"] == ["scale"] and u["scale"]["qp"] > 100 and u["scale"]["q"] < 2
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
    assert u["bal"] == {"fy": None, "q": None, "qp": None} and u["why"] == ["scale"]
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
    j = src.find("unit_guard(kr, fin_map, mult_extra)")
    assert 0 < i < j < src.find("income_check(kr, fin_map, mult_extra)") < src.find("add_percentiles(kr)") < src.find("build_corp(kr,")
    assert j < src.find("eps_basis_of(kr, mult_extra)")


def test_enrich_keeps_last_years_quarter_for_the_check(tmp_path, monkeypatch):
    """enrich_with_dart (가짜 DART · 진코스텍의 실제 응답) 이 fin 에 bsP 를 남기고, 그 fin 으로 걸려요."""
    t, corp_code = "250030", CO["250030"]["corp"]

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
    assert F.unit_check(fin)["why"] == ["scale"]
    # 캐시에 저장된 해석(새 칸 bal 포함)으로 다음 실행도 같은 판단
    with gzip.open(str(tmp_path / "c.json.gz"), "rt", encoding="utf-8") as f:
        ent = json.load(f)["entries"]
    assert ent[f"{corp_code}|2026|11012|OFS"]["d"]["bal"][0] == 60392733970000.0


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
                                           ("corp", "rev", [1.0, None, None]), ("corp", "ni", [None, None, 2.0]),
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
    assert V.PBR_LOW_CHECKED["040610"]["eq"] == 5085.1 and V.PBR_LOW_CHECKED["109960"]["eq"] == 3617.6   # 2026-11-12 발행본 bpsIn.eq
    runbook = open(os.path.join(ROOT, "docs", "RUNBOOK.md"), encoding="utf-8").read()
    assert "PBR_LOW_CHECKED" in runbook


def test_gate_and_pipeline_keep_their_lists_apart_but_in_step():
    """관문은 파이프라인과 따로 적어요. 파이프라인이 비우는 칸이 관문이 보는 칸 안에 모두 있어야 해요."""
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
