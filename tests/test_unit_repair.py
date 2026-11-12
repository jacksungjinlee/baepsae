# -*- coding: utf-8 -*-
"""공시 단위 고침 (Jack, 2026-11-13 · 원인 수리 · 리뷰 #116 1차 뒤): 단위를 잘못 적은 올해 분기 보고서를 표마다 증명해 나눠 써요 —
fetch_data.bs_factor · flow_factor · unit_fix_plan · scale_quarter · unit_fix_quarter · enrich_with_dart, 관문의 unitFix 줄.
공시 단위 확인(unit_guard)은 안전망으로 그대로예요: 고치지 못하면 비워요. (네트워크 없음)

리뷰 #116 의 두 막힘을 그대로 시험해요:
  B1 사업보고서가 ÷1,000 이고 분기 보고서는 맞음 → 맞는 분기를 나누면 안 돼요 (지난해 같은 분기도 사업보고서와 달라 고치지 않고 비워요)
  B2 재무상태표만 단위가 틀림 → 맞는 손익 · 현금흐름을 나누면 안 돼요 (표마다 따로 증명)
픽스처는 tests/test_unit_guard.py 와 같은 tests/fixtures/dart_unit_samples.json (2026-11-13 KST 에 받은 실제 재무제표)."""
import copy
import datetime as dt
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_unit_guard import CO, ST, PX, BAD, REAL, rows, company, scaled, only  # noqa: E402
from test_v191f_income import check, comp, fails, pair, rows_of  # noqa: E402,F401  (pair 는 pytest 픽스처)

TODAY = dt.date(2026, 11, 13)
# 표마다 나누는 칸 — 상수를 그대로 돌지 않고 여기 따로 적어요 (리뷰 #116 R4)
BS_KEYS = ["eq", "eqo", "bor", "cash", "ca", "cl", "cs", "nciBs"]
IS_KEYS = ["rev", "op", "ni", "nio", "ie", "nciPl"]
CF_KEYS = ["ocf", "iec", "dep"]


def stock(t, **kw):
    price, shr, cap = PX[t]
    s = {"t": t, "nk": CO[t]["name"], "cls": "kr", "price": price, "shr": shr, "cap": cap}
    s.update(kw)
    return s


def quarters(t, q=None, qp=None, annual=None):
    fin = F.parse_dart_list(annual if annual is not None else rows(t, 2025, "11011"))["_fin"]
    fin["fs"] = CO[t]["fs"]
    return fin, F.parse_dart_quarter(q if q is not None else rows(t, 2026, "11012")), F.parse_dart_quarter(qp if qp is not None else rows(t, 2025, "11012"))


# ── 1. 증명 ─────────────────────────────────────────────────────
def test_the_constants_are_the_lists_written_here():
    assert list(F.UNIT_Q_BS) == BS_KEYS and list(F.UNIT_Q_IS) == IS_KEYS and list(F.UNIT_Q_CF) == CF_KEYS
    assert F.UNIT_FACTORS == (1000.0, 1e6) and F.UNIT_FIX_BAND == 8.0


def test_the_balance_sheet_factor_is_proven_by_the_prior_year_end_column():
    for t in BAD:
        fin, q, qp = quarters(t)
        assert F.bs_factor(q["bal0"], fin["bal"]) == 1000.0                          # 원 단위까지 정확히 1,000 배
        assert F.bs_factor(q["bal0"], None, fin["eq"], fin["li"]) == 1000.0          # 캐시의 사업보고서에 총계가 없을 때 (억원 반올림)
        assert F.bs_factor(qp["bal0"], fin["balP"]) == 1.0                           # 지난해 같은 분기 ↔ 사업보고서의 전기 칸
    for t in REAL:
        fin, q, qp = quarters(t)
        assert F.bs_factor(q["bal0"], fin["bal"]) == 1.0 and F.bs_factor(qp["bal0"], fin["balP"]) == 1.0


def test_the_proof_must_be_exact_and_the_rounded_fallback_needs_1_eok_of_equity():
    ref = [52031249182.0, 33235837973.0, 18795411209.0]
    assert F.bs_factor([x * 1000 for x in ref], ref) == 1000.0 and F.bs_factor([x * 1e6 for x in ref], ref) == 1e6
    assert F.bs_factor(ref, ref) == 1.0
    assert F.bs_factor([ref[0] * 1000 + 5000, ref[1] * 1000, ref[2] * 1000], ref) is None    # 자산이 5원(× 1,000) 어긋나면 아니에요
    # 사업보고서 총계가 있는데 원 단위 증명이 틀리면, 억원 반올림 증명(자본 188.0 · 부채 332.4)이 맞아도 쓰지 않아요 (리뷰 #116 2차)
    assert F.bs_factor([ref[0] * 1000 + 5000, ref[1] * 1000, ref[2] * 1000], ref, 188.0, 332.4) is None
    assert F.bs_factor([ref[0] * 1000, ref[1] * 1000, ref[2] * 999], ref) is None
    assert F.bs_factor([x * 1000 for x in ref], None, 188.0, 332.4) == 1000.0
    assert F.bs_factor([x * 1000 for x in ref], None, 188.2, 332.4) is None                  # 0.05억 밖
    assert F.bs_factor([x * 1000 for x in ref], None, 188.0, 333.4) is None                  # 부채도 맞아야 해요 (자본만으로는 아니에요)
    assert F.bs_factor([x * 1000 for x in ref], None, 188.0, 332.6) is None                  # 부채도 0.05억 안 (0.2억 밖)
    assert F.bs_factor([x * 1000 for x in ref], None, 188.0, 332.35) == 1000.0
    assert F.bs_factor([5.01e13, 4e13, 0.99e8 * 1000], None, 0.99, 400.0) is None            # 자본 1억 미만: 반올림으로는 증명 안 해요
    assert F.bs_factor([5.01e13, 4e13, 1.0e8 * 1000], None, 1.0, 400.0) == 1000.0            # 1억부터
    assert F.bs_factor([5.01e13, 4e13, -1.0e8 * 1000], None, -1.0, 400.0) == 1000.0          # 자본잠식도 크기로
    for bad in (None, [1, 2], [1, None, 3], "x"):
        assert F.bs_factor(bad, ref) is None
    assert F.bs_factor([x * 100 for x in ref], ref) is None and F.bs_factor([x * 100 for x in ref], None, 188.0, 332.4) is None   # 100배는 단위가 아니에요


def test_the_flow_factor():
    assert F.flow_factor([(231928.2, 231.9), (36323.3, 36.3)]) == 1000.0
    assert F.flow_factor([(231.9, 231.9), (36.3, 36.3)]) == 1.0
    assert F.flow_factor([(231928.2, 231.9), (36.3, 36.3)]) is None                          # 표 안에서 배수가 엇갈리면 증명 안 돼요
    assert F.flow_factor([(None, 231.9), (36323.3, None), (5.0, 0.05)]) is None              # 쓸 쌍이 없음
    assert F.flow_factor([(-1200.0, -1.2)]) == 1000.0                                       # 손실도 같은 배수
    assert F.flow_factor([(23190.0, 231.9)]) is None and F.flow_factor([(231.9e6, 231.9)]) == 1e6   # 100배는 단위가 아니에요


def test_the_flow_tolerance_is_what_rounding_can_explain():
    """리뷰 #116 2차 N2: 억원 소수 한 자리끼리라 반올림이 설명할 수 있는 0.05억 + 0.2% 까지만 · 지난해 값이 1억 미만인 줄은 증거가 아니에요."""
    assert (F.UNIT_FLOW_ABS, F.UNIT_FLOW_REL, F.UNIT_FLOW_MIN) == (0.05, 0.002, 1.0)
    assert F.flow_factor([(100250.0, 100.0)]) == 1000.0                                    # 0.25 = 0.05 + 0.2% × 100
    assert F.flow_factor([(100260.0, 100.0)]) is None                                      # 0.26 밖 (2% 면 들어와요)
    assert F.flow_factor([(2054.0, 2.0)]) == 1000.0                                        # 0.054 = 0.05 + 0.2% × 2
    assert F.flow_factor([(2060.0, 2.0)]) is None                                          # 0.06 밖 (1억이면 들어와요)
    assert F.flow_factor([(950.0, 0.9)]) is None                                           # 지난해 0.9억: 증거로 세지 않아요 → 쓸 쌍 없음
    assert F.flow_factor([(950.0, 0.9), (231928.2, 231.9)]) == 1000.0                      # 다른 줄로 증명
    assert F.flow_factor([(1000.0, 1.0)]) == 1000.0                                        # 1억부터


def test_scale_quarter_divides_each_statement_by_its_own_factor():
    q = F.parse_dart_quarter(rows("250030", 2026, "11012"))
    f = F.scale_quarter(q, 1000.0, 1.0, 1e6)
    assert f["unitFix"] == {"bs": 1000.0, "cf": 1e6} and "unitFix" not in q
    for k in BS_KEYS:
        if q.get(k) is not None:
            assert f[k] == round(q[k] / 1000, 1), k
    for k in IS_KEYS:
        assert f.get(k) == q.get(k), k                                                  # 손익은 그대로
    for k in CF_KEYS:
        if q.get(k) is not None:
            assert f[k] == round(q[k] / 1e6, 1), k
    assert f["bal"] == [x / 1000 for x in q["bal"]] and f["bal0"] == [x / 1000 for x in q["bal0"]]
    assert f["p0"]["rev"] == q["p0"]["rev"] and f["p0"]["ocf"] == round(q["p0"]["ocf"] / 1e6, 1)
    assert f["epsYtd"] == q["epsYtd"]                                                      # 주당 금액은 나누지 않아요


# ── 2. 계획: 고칠지 · 무엇을 · 왜 안 되는지 ─────────────────────────────
def test_the_two_real_reports_are_fixed_in_every_statement():
    for t in BAD:
        fin, q, qp = quarters(t)
        assert F.unit_fix_plan(fin, q, qp, stock(t)) == ("fix", 1000.0, 1000.0, 1000.0), t
    for t in REAL:
        fin, q, qp = quarters(t)
        assert F.unit_fix_plan(fin, q, qp, stock(t))[0] == "none", t


def test_b1_an_annual_report_in_the_wrong_unit_never_divides_a_correct_quarter():
    """리뷰 #116 B1: 사업보고서가 ÷1,000 (분기 보고서는 맞음) — 두 분기가 모두 사업보고서와 1,000배 달라 사업보고서 쪽으로 보고 고치지 않아요."""
    for t in ("040610", "109960"):
        fin, q, qp = quarters(t, annual=scaled(rows(t, 2025, "11011"), 0.001))
        plan = F.unit_fix_plan(fin, q, qp, stock(t, _bas={"par3": [1000.0, 1000.0, 1000.0]}))
        assert plan[0] == "left" and "지난해 같은 분기" in plan[1], plan


def test_b2_only_the_balance_sheet_in_the_wrong_unit_never_divides_the_correct_flows():
    t = "040610"
    fin, q, qp = quarters(t, q=only(rows(t, 2026, "11012"), 1000, ("BS",)))
    assert F.unit_fix_plan(fin, q, qp, stock(t))[0] == "left"                              # 액면가가 없으면 재무상태표의 기준값이 없어 고치지 않아요
    plan = F.unit_fix_plan(fin, q, qp, stock(t, _bas={"par3": [1000.0, 1000.0, 1000.0]}))  # SG&G 액면가 1,000원
    assert plan == ("fix", 1000.0, 1.0, 1.0), plan
    f = F.scale_quarter(q, *plan[1:])
    assert f["unitFix"] == {"bs": 1000.0}
    good = F.parse_dart_quarter(rows(t, 2026, "11012"))
    for k in IS_KEYS + CF_KEYS:
        assert f.get(k) == good.get(k), k                                               # 맞는 손익 · 현금흐름은 그대로
    for k in BS_KEYS:
        assert f.get(k) == good.get(k), k                                               # 재무상태표는 원래 값으로


def test_an_income_statement_alone_is_fixed_only_with_the_eps_anchor():
    """손익계산서만 1,000배: 기본주당이익 기준값으로 나눠요. 1 로 남는 현금흐름표는 기준값이 있는 표에 기대야 해요 (리뷰 #116 2차 S1) —
    액면가가 있으면 재무상태표(자본금 ÷ 액면가 · 1 배)에, 없으면 기댈 곳이 없어 고치지 않아요."""
    t = "040610"
    fin, q, qp = quarters(t, q=only(rows(t, 2026, "11012"), 1000, ("IS", "CIS")))
    plan = F.unit_fix_plan(fin, q, qp, stock(t, _bas={"par3": [1000.0, 1000.0, 1000.0]}))
    assert plan == ("fix", 1.0, 1000.0, 1.0), plan
    plan = F.unit_fix_plan(fin, q, qp, stock(t))
    assert plan[0] == "left" and "현금흐름표" in plan[1], plan
    q2 = dict(q)
    q2.pop("epsYtd")
    assert F.unit_fix_plan(fin, q2, qp, stock(t, _bas={"par3": [1000.0] * 3}))[0] == "left"   # 기본주당이익이 없으면 기준값이 없어요


def test_a_cash_flow_statement_alone_has_no_anchor_and_is_left():
    t = "040610"
    fin, q, qp = quarters(t, q=only(rows(t, 2026, "11012"), 1000, ("CF",)))
    plan = F.unit_fix_plan(fin, q, qp, stock(t))
    assert plan[0] == "left" and "현금흐름표" in plan[1], plan


def test_last_years_quarter_in_the_wrong_unit_is_never_fixed():
    t = "040610"
    fin, q, qp = quarters(t, qp=scaled(rows(t, 2025, "11012"), 1000))
    plan = F.unit_fix_plan(fin, q, qp, stock(t))
    assert plan[0] == "left", plan
    # 지난해 같은 분기의 지난해 말 칸이 사업보고서의 전기 칸과 1,000배면 (그 보고서만 틀림): 고치지 않아요
    fin, q, qp = quarters(t, q=scaled(rows(t, 2026, "11012"), 1000))
    qp = dict(qp, bal0=[x * 1000 for x in qp["bal0"]])
    plan = F.unit_fix_plan(fin, q, qp, stock(t))
    assert plan[0] == "left" and "전기 칸" in plan[1], plan


def test_a_wrong_division_is_refused_by_the_anchor():
    """나눈 뒤 평균 주식 수(순이익 ÷ 기본주당이익)가 오늘 주식 수의 1/8 ~ 8 배 밖이면 고치지 않아요 (주식 수가 1,000배 달라 보이는 경우)."""
    t = "250030"
    fin, q, qp = quarters(t)
    assert F.unit_fix_plan(fin, q, qp, stock(t))[0] == "fix"
    assert F.unit_fix_plan(fin, q, qp, stock(t, shr=PX[t][1] * 1000))[0] == "left"
    assert F.unit_fix_plan(fin, q, qp, stock(t, shr=round(PX[t][1] / 12)))[0] == "left"    # 비 0.73 × 12 = 8.8 → 8 배 밖
    assert F.unit_fix_plan(fin, q, qp, stock(t, shr=round(PX[t][1] / 10)))[0] == "fix"     # 비 7.3 → 8 배 안
    assert F._in_band(0.126) and not F._in_band(0.124) and F._in_band(7.99) and not F._in_band(8.01) and not F._in_band(None)


def test_the_columns_must_be_there():
    t = "250030"
    fin, q, qp = quarters(t)
    q.pop("bal0")
    assert F.unit_fix_plan(fin, q, qp, stock(t))[0] == "need"
    assert F.unit_fix_quarter(None, CO[t]["corp"], fin, 2026, "11012", q, qp, stock(t), None, {"fixed": [], "left": [], "redo": 0}) is q


# ── 2b. 리뷰 #116 2차: 1 로 '증명'된 표도 기준값이 있어야 · 실패한 기준값은 덮지 않아요 · 경계값 ──────────────
def synth(bs=1, is_=1, cf=1, p_is=1, p_cf=1, p_bs=1, ann=1, eps=550.0, fs="CFS", nio=True, shr=2_000_000, par=None, cur=None,
          pref=None, old=False, prev=True, hyb=None):
    """합성 회사 (진짜 값: 사업보고서 자본 100억 · 자본금 10억 = 액면 500원 × 200만 주 · 올해 누적 지배주주 순이익 11억 = 기본주당이익 550원 ·
    매출 220억 · 영업현금흐름 33억 · 지난해 같은 기간 200 · 10 · 30억). bs · is_ · cf: 올해 분기 보고서의 표마다 배수 · p_*: 지난해 같은 분기 보고서
    · ann: 사업보고서. old: 이 고침 전 캐시처럼 총계(bal · balP · bal0) 없음. → (fin, q, prev, s)"""
    fin = {"fs": fs, "eq": 100.0 * ann, "ca": 60.0 * ann, "cl": 40.0 * ann, "cs": 10.0 * ann, "cash": 20.0 * ann, "li": 80.0 * ann}
    if not old:
        fin.update(bal=[180e8 * ann, 80e8 * ann, 100e8 * ann], balP=[170e8 * ann, 75e8 * ann, 95e8 * ann])
    q = {"eq": 110.0 * bs, "eqo": 110.0 * bs, "ca": 66.0 * bs, "cl": 44.0 * bs, "cs": 10.0 * bs, "cash": 22.0 * bs,
         "rev": 220.0 * is_, "ni": (12.0 if nio else 11.0) * is_, "ocf": 33.0 * cf,
         "p0": {"rev": 200.0 * is_, "ni": (11.0 if nio else 10.0) * is_, "ocf": 30.0 * cf}, "bal0": [180e8 * bs, 80e8 * bs, 100e8 * bs]}
    if nio:
        q["nio"] = 11.0 * is_                                                   # 연결: 지배주주 11억 · 전체 12억 (비지배 1억)
    if eps is not None:
        q["epsYtd"] = eps
    if hyb:
        q["hyb"] = dict(hyb)
    pv = {"eq": 95.0 * p_bs, "ca": 57.0 * p_bs, "cl": 38.0 * p_bs, "cs": 10.0 * p_bs, "cash": 19.0 * p_bs,
          "rev": 200.0 * p_is, "ni": (11.0 if nio else 10.0) * p_is, "ocf": 30.0 * p_cf}
    if nio:
        pv["nio"] = 10.0 * p_is
    if not old:
        pv["bal0"] = [170e8 * p_bs, 75e8 * p_bs, 95e8 * p_bs]
    s = {"t": "200000", "nk": "가", "cls": "kr", "price": 5000.0, "shr": shr}
    if par is not None:
        s["_bas"] = {"par3": [par] * 3}
    if cur:
        fin["cur"] = cur
    return fin, q, (pv if prev else None), s


def plan(*a, pref=None, **kw):
    fin, q, pv, s = synth(*a, **kw)
    return F.unit_fix_plan(fin, q, pv, s, pref)


def test_the_synthetic_company_is_fixed_whole_and_left_alone_when_right():
    assert plan() == ("none", "")
    assert plan(1000, 1000, 1000) == ("fix", 1000.0, 1000.0, 1000.0)
    assert plan(1000, 1000, 1000, par=500.0) == ("fix", 1000.0, 1000.0, 1000.0)
    assert plan(1e6, 1e6, 1e6) == ("fix", 1e6, 1e6, 1e6)                                     # 백만원으로 읽힌 보고서도 (기본주당이익으로)
    assert plan(1e6, 1e6, 1e6, eps=None, par=500.0) == ("fix", 1e6, 1e6, 1e6)                # 자본금 ÷ 액면가로만 (손익은 그 배수에 기대요)
    assert plan(1000, 1000, 1000, eps=None, par=500.0) == ("fix", 1000.0, 1000.0, 1000.0)


@pytest.mark.parametrize("p_cf", [1, 1000])
@pytest.mark.parametrize("eps", [550.0, None, 5.0, -550.0])
def test_s1_a_statement_proven_at_1_must_pass_its_anchor(p_cf, eps):
    """리뷰 #116 2차 S1: 올해 분기 보고서 전체 1,000배 + 지난해 같은 분기는 손익계산서만(또는 손익 · 현금흐름) 1,000배 → 재무상태표는 1,000,
    손익계산서는 1 로 '증명'돼요. 예전엔 재무상태표만 나눠 EPS 3,999,370 · PER 0.0 을 냈어요 (안전망만이면 비웠을 회사). 이제 1 로 남는
    손익계산서도 기본주당이익 기준값을 지나야 하고, 기준값을 볼 수 없으면(줄 없음 · 10원 미만 · 부호가 다름) 아무것도 나누지 않아요."""
    for par in (None, 500.0):
        got = plan(1000, 1000, 1000, p_is=1000, p_cf=p_cf, eps=eps, par=par)
        assert got[0] == "left", (eps, par, got)
    fin, q, pv, s = synth(1000, 1000, 1000, p_is=1000, p_cf=p_cf, eps=eps)
    assert (F.bs_factor(q["bal0"], fin["bal"]), F.flow_factor([(q["p0"]["rev"], pv["rev"]), (q["p0"]["ni"], pv["ni"])])) == (1000.0, 1.0)


@pytest.mark.parametrize("sjs", [("IS", "CIS"), ("IS", "CIS", "CF")])
@pytest.mark.parametrize("t", ["040610", "250030"])
def test_s1_on_real_statements(t, sjs, tmp_path, monkeypatch):
    """리뷰 #116 2차 S1 (실제 재무제표): 올해 분기 보고서 전체 1,000배 + 지난해 같은 분기는 손익(· 현금흐름)만 1,000배 → 고치지 않고, 안전망이
    비워요 (기본주당이익 줄이 있어도 없어도). 예전 고침은 재무상태표만 나눠 EPS 3,999,370 · PER 0.0 을 냈어요."""
    q_rows = rows(t, 2026, "11012")                                                          # 진코스텍의 2026 반기는 이미 1,000배
    if t != "250030":
        q_rows = only(q_rows, 1000, ("BS", "IS", "CIS", "CF"))                               # 진짜 단위 오류처럼 주당 금액 줄은 그대로
    qp_rows = only(rows(t, 2025, "11012"), 1000, sjs)
    for drop_eps in (False, True):
        qr = [x for x in q_rows if not (drop_eps and "PerShare" in (x.get("account_id") or ""))]
        fin, q, qp = quarters(t, q=qr, qp=qp_rows)
        assert ("epsYtd" in q) is not drop_eps
        got = F.unit_fix_plan(fin, q, qp, stock(t, _bas={"par3": [1000.0 if t == "040610" else 500.0] * 3}))
        assert got[0] == "left", (t, sjs, drop_eps, got)
    over = {f"{t}|2026|11012|{CO[t]['fs']}": q_rows, f"{t}|2025|11012|{CO[t]['fs']}": qp_rows}
    kr, fm, _, _ = enrich(tmp_path, monkeypatch, [t], override=over)
    assert "unitFix" not in fm[t]
    for s_ in kr:
        s_.update(vol=30.0, mom=1.0)
    extra = F.fill_multiples(kr, fm, {})
    assert t in F.unit_guard(kr, fm, extra)["hit"] and kr[0].get("per") is None and kr[0].get("eps") is None


def test_a_failing_eps_anchor_is_never_overridden_by_the_capital_anchor():
    """리뷰 #116 2차 N3: 계산할 수 있는 기준값이 어긋나면 다른 기준값이 맞아도 고치지 않아요."""
    assert plan(1000, 1000, 1000, eps=550.0 * 50, par=500.0)[0] == "left"                  # 기본주당이익이 50배 어긋남 · 자본금은 맞음
    assert plan(1000, 1000, 1000, eps=550.0, par=500.0 * 50)[0] == "left"                  # 거꾸로
    assert "기본주당이익" in plan(1000, 1000, 1000, eps=550.0 * 50, par=500.0)[1]


def test_riding_needs_the_same_factor():
    """기준값이 없는 표는 같은 배수로 나눈, 기준값이 맞은 표에만 기대요 (배수가 다르면 기대지 못해요)."""
    assert plan(1, 1000, 1, par=500.0) == ("fix", 1.0, 1000.0, 1.0)                           # 손익만: 기본주당이익 · 현금흐름은 재무상태표(자본금 · 1)에
    assert plan(1, 1000, 1)[0] == "left"                                                    # 액면가가 없으면 현금흐름표가 기댈 곳이 없어요
    assert plan(1, 1000, 1000) == ("fix", 1.0, 1000.0, 1000.0)                              # 손익 · 현금흐름 1,000 (현금흐름은 손익에)
    assert plan(1000, 1, 1, par=500.0) == ("fix", 1000.0, 1.0, 1.0)                           # 재무상태표만 (B2): 자본금 · 손익 1 은 기본주당이익
    assert plan(1000, 1, 1)[0] == "left"                                                    # 액면가 없음: 재무상태표가 기댈 곳 없음 (손익은 1)
    assert plan(1000, 1000, 1000, eps=None)[0] == "left"                                    # 기준값이 하나도 없음
    assert plan(1000, 1000, 1, par=500.0, eps=None)[0] == "left"                            # 현금흐름 1: 기댈 기준값(1배)이 없어요
    assert plan(1000, 1000, 1000, eps=None, par=500.0) == ("fix", 1000.0, 1000.0, 1000.0)
    assert plan(1000, 1000, 1000, eps=-550.0, par=500.0) == ("fix", 1000.0, 1000.0, 1000.0)   # 부호가 다른 기본주당이익은 '볼 수 없음' (어긋남 아님)
    assert plan(1, 1000, 1000, eps=None, par=500.0)[0] == "left"                            # 손익 1,000 은 자본금(1배)에 기대지 못해요
    assert plan(1000, 1, 1000, eps=None, par=500.0)[0] == "left"                            # 손익 1 은 자본금(1,000배)에 기대지 못해요


def test_the_both_quarters_rule_on_the_next_real_run_shape():
    """사업보고서 ÷1,000 · 분기는 맞음, 캐시가 이 고침 전 모양(총계 없음): 전기 칸 규칙은 볼 수 없고 두 분기 규칙만 걸어요 (그 이유로)."""
    got = plan(1, 1, 1, ann=0.001, old=True)
    assert got[0] == "left" and "지난해 같은 분기 보고서도 사업보고서와" in got[1], got
    fin, q, pv, s = synth(1000, 1000, 1000)
    for k in ("eq", "ca", "cl", "cs", "cash"):
        pv.pop(k)                                                                           # 지난해 같은 분기의 재무상태표가 없음 → 배율 모름
    got = F.unit_fix_plan(fin, q, pv, s)
    assert got[0] == "left" and "지난해 같은 분기 보고서도 사업보고서와" in got[1], got


def test_the_other_reasons_to_leave():
    assert plan(1000, 1000, 1000, prev=False) == ("left", "지난해 같은 분기 보고서가 없어요")
    got = plan(0.001, 0.001, 0.001)
    assert got[0] == "left" and "작아요" in got[1], got                                     # 올해 분기가 1/1,000 — 나눌 것이 아니에요
    fin, q, pv, s = synth(1000, 1000, 1000)
    q["bal0"] = [180e8 * 200, 80e8 * 200, 100e8 * 200]
    got = F.unit_fix_plan(fin, q, pv, s)
    assert got[0] == "left" and "재무상태표의 배수를" in got[1], got                         # 재무상태표 증명이 없으면 (다른 표가 1,000 이어도)
    fin, q, pv, s = synth(1000, 1000, 1000)
    pv["ocf"] = 77.0
    got = F.unit_fix_plan(fin, q, pv, s)
    assert got[0] == "left" and "현금흐름표의 배수를" in got[1], got                          # 증명이 없는 표를 1 로 보지 않아요
    fin, q, pv, s = synth()
    for k in ("eq", "eqo", "ca", "cl", "cash"):
        q[k] = q[k] * 200                                                                   # 진짜 큰 변화 (증자): 지난해 칸은 모두 1배
    got = F.unit_fix_plan(fin, q, pv, s)
    assert got == ("left", "지난해 칸으로는 모든 표가 1배예요 (다른 까닭 · 고치지 않아요)"), got


def test_the_anchors_need_shares_won_and_a_real_eps():
    assert plan(1000, 1000, 1000, shr=None)[0] == "left"                                    # 주식 수가 없으면 기준값이 없어요
    assert plan(1000, 1000, 1000, shr=None, par=500.0)[0] == "left"
    assert plan(1000, 1000, 1000, eps=5.0, shr=200_000_000)[0] == "left"                    # 기본주당이익 5원: 견주지 않아요 (비는 1 이어도)
    got = plan(1000, 1000, 1000, cur="USD")
    assert got[0] == "left" and "원화가 아닌" in got[1], got                                # #118: 원화가 아닌 재무제표는 기준값을 보지 않아요
    got = plan(1000, 1000, 1000, cur="USD", par=500.0)
    assert got[0] == "left", got
    fin, q, pv, s = synth(1000, 1000, 1000)
    s["t"] = "900100"                                                                       # 해외 기업도
    assert F.unit_fix_plan(fin, q, pv, s)[0] == "left"
    assert F.unit_anchor_eps(fin, q, 1000.0, None) == "none" and F.unit_anchor_cap({"_bas": {"par3": [0.0] * 3}}, q, 1000.0, 2e6) == "none"


def test_the_eps_anchor_uses_owners_profit_and_the_preferred_shares():
    # 연결은 지배주주 순이익(nio), 별도는 순이익(ni) — 둘이 크게 다르면 결과가 달라요
    fin, q, pv, s = synth(1000, 1000, 1000)
    q["ni"] = 12.0 * 1000 * 9                                                               # 전체 순이익이 크게 달라도 연결은 지배주주로
    assert F.unit_anchor_eps(fin, q, 1000.0, 2_000_000) == "ok"
    fin["fs"] = "OFS"                                                                       # 별도는 순이익(ni)으로 → 9배 어긋남
    assert F.unit_anchor_eps(fin, q, 1000.0, 2_000_000) == "fail"
    # 우선주: 오늘 주식 수 = 보통주 + 같은 회사 상장 우선주 (per_share_count) — 보통주 20만 + 우선주 180만 = 200만
    assert plan(1000, 1000, 1000, shr=200_000, pref={"20000": [1_800_000]}) == ("fix", 1000.0, 1000.0, 1000.0)
    assert plan(1000, 1000, 1000, shr=200_000)[0] == "left"                                # 우선주를 빼면 10배 → 밖


def test_needs_unit0():
    assert F.needs_unit0({"bal0": [1, 2, 3]}) and F.needs_unit0({"p0": {}}) and F.needs_unit0({})
    assert not F.needs_unit0({"bal0": [1, 2, 3], "p0": {}}) and not F.needs_unit0(None)


def test_a_hybrid_distribution_in_a_divided_report_is_blanked():
    """리뷰 #116 2차 N1: 자본변동표의 신종자본증권 분배는 증명할 칸이 없어 나눈 보고서에서는 비우고 '어디 몫인지 알 수 없음'으로 둬요 —
    EPS · BPS 는 전체 기준 (how hybrid) 으로 돌아가요. 재무상태표의 신종자본증권 금액은 재무상태표 배수로 나눠요."""
    q = {"eq": 110000.0, "hyb": {"ok": True, "eq": 5000.0, "dist": 300.0}}
    f = F.scale_quarter(q, 1000.0, 1000.0, 1000.0)
    assert f["hyb"] == {"ok": False, "eq": 5.0, "dist": None, "unproven": True} and q["hyb"]["dist"] == 300.0
    f = F.scale_quarter({"hyb": {"ok": True, "eq": 5000.0, "dist": 0.0}}, 1000.0, 1000.0, 1000.0)
    assert f["hyb"] == {"ok": True, "eq": 5.0, "dist": 0.0}                                 # 분배 0 은 어느 배수로도 0
    f = F.scale_quarter({"hyb": {"ok": True, "eq": 5.0, "dist": 0.3}}, 1.0, 1000.0, 1.0)
    assert f["hyb"]["dist"] is None and f["hyb"]["eq"] == 5.0                               # 손익만 나눠도 분배는 비워요
    assert F.scale_quarter({"hyb": {"ok": True, "eq": 5.0, "dist": 0.3}})["hyb"] == {"ok": True, "eq": 5.0, "dist": 0.3}
    fin = {"fs": "CFS", "nio": 100.0, "hyb": {"ok": True, "dist": 3.0}}
    t2 = {"nio": 120.0, "hyb": {"ok": False, "dist": 3.0}}
    assert F.eps_source(dict(fin, ttm=t2))[1:4] == ("t", "ttm", "hybrid")                  # 분배를 모르면 전체 기준


# ── 3. 파이프라인 (가짜 DART · 실제 응답) ──────────────────────────────
class FakeDart:
    def __init__(self, override=None):
        self.calls, self.override = [], override or {}

    def get(self, client, endpoint, params, timeout=25):
        t = next(x for x, c in CO.items() if c["corp"] == params.get("corp_code"))
        key = f"{t}|{params.get('bsns_year')}|{params.get('reprt_code')}|{params.get('fs_div')}"
        self.calls.append(key)
        rows_ = self.override.get(key, (ST.get(key) or {}).get("rows"))
        with client.lock:
            client.status["000" if rows_ else "013"] += 1
        if endpoint.startswith("fnltt") and rows_:
            return {"status": "000", "list": copy.deepcopy(rows_)}
        return {"status": "013"}


def enrich(tmp_path, monkeypatch, codes, pre=None, override=None):
    fake = FakeDart(override)
    monkeypatch.setattr(F.DartClient, "get", lambda self, ep, params, timeout=25: fake.get(self, ep, params, timeout))
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {t: CO[t]["corp"] for t in codes})
    c = F.DartClient("k", today=TODAY, path=str(tmp_path / "c.json.gz"))
    for k, v in (pre or {}).items():
        c.entries[k] = v
    kr = [stock(t) for t in codes]
    kr, fm = F.enrich_with_dart(kr, c, {})
    return kr, fm, fake, c


def old_entry(t, y, r):
    """이번 고침 전에 저장된 분기 항목 (지난해 칸 bal0 · p0 · 기본주당이익이 없어요 · 2026-11-12 에 받은 것)."""
    d = F.parse_dart_quarter(rows(t, y, r))
    for k in ("bal0", "p0", "epsYtd"):
        d.pop(k, None)
    return {"st": "000", "at": "2026-11-12", "d": d}


def test_a_cached_report_without_the_columns_is_read_again_once_and_fixed(tmp_path, monkeypatch, capsys):
    pre = {f"{CO[t]['corp']}|2026|11012|{CO[t]['fs']}": old_entry(t, 2026, "11012") for t in BAD}
    kr, fm, fake, client = enrich(tmp_path, monkeypatch, list(BAD + REAL), pre)
    again = [k for k in fake.calls if k in ("250030|2026|11012|OFS", "002880|2026|11012|CFS")]
    assert sorted(again) == ["002880|2026|11012|CFS", "250030|2026|11012|OFS"], fake.calls      # 그 두 보고서만 한 번씩
    for t in BAD:
        assert F.unit_check(fm[t], PX[t][1])["why"] == [], (t, F.unit_check(fm[t], PX[t][1]))   # 안전망은 아무것도 걸지 않아요
        assert fm[t]["unitFix"] == [{"rep": "2026.2Q", "bs": 1000.0, "is": 1000.0, "cf": 1000.0}]
        e = client.entries[f"{CO[t]['corp']}|2026|11012|{CO[t]['fs']}"]
        assert "bal0" in e["d"] and "p0" in e["d"] and e["rp"] == F.UNIT_REDO_TAG
    out = capsys.readouterr().out
    assert "!! 공시 단위 고침: 올해 분기 보고서 2건을 표마다 증명해 나눠 썼어요 · 다시 받은 보고서 2건" in out
    assert "250030 진코스텍 2026.2Q (재무상태표 ÷ 1,000 · 손익계산서 ÷ 1,000 · 현금흐름표 ÷ 1,000)" in out
    # 같은 캐시로 다음 실행: DART 를 부르지 않고 같은 고침
    fake2 = FakeDart()
    monkeypatch.setattr(F.DartClient, "get", lambda self, ep, params, timeout=25: fake2.get(self, ep, params, timeout))
    client.save()
    c2 = F.DartClient("k", today=TODAY, path=str(tmp_path / "c.json.gz"))
    _, fm2 = F.enrich_with_dart([stock(t) for t in BAD], c2, {})
    assert not [k for k in fake2.calls if k in ("250030|2026|11012|OFS", "002880|2026|11012|CFS")], fake2.calls
    assert fm2["250030"]["bs2"]["eq"] == 264.2 and fm2["002880"]["bs2"]["eqo"] == 646.4


def test_after_the_fix_the_published_numbers_are_the_filings(tmp_path, monkeypatch):
    kr, fm, fake, _ = enrich(tmp_path, monkeypatch, list(BAD + REAL))
    by = {s["t"]: s for s in kr}
    for s in kr:
        s.update(vol=30.0, mom=1.0)
    extra = F.fill_multiples(kr, fm, {})
    guard = F.unit_guard(kr, fm, extra)
    assert guard["hit"] == {}
    corp = F.build_corp(kr, fm, "2026-11-13", extra=extra)
    cby = {c["t"]: c for c in corp["companies"]}
    # 진코스텍: TTM 순이익 53.3억 (공시: 60.17 + 29.42 − 36.32 = 53.27억 · 보고서마다 0.1억으로 반올림해 더해요) ÷ 3,786,533주 = EPS 1,408 ·
    # PER 6.5 · 자본 264.2억 → BPS 6,977 · PBR 1.32 (예전 발행: PER 0.0 · PBR 0.0 · EPS 777,569 · BPS 6,977,676)
    assert extra["250030"]["epsIn"]["ni"] == 53.3 and extra["250030"]["bpsIn"]["eq"] == 264.2
    assert (by["250030"]["eps"], by["250030"]["per"], by["250030"]["bps"], by["250030"]["pbr"]) == (1408.0, 6.5, 6977.0, 1.32)
    # 디와이에이: TTM 지배주주 순이익 131.2억 → EPS 1,402 · PER 2.2 · 지배주주 자본 646.4억 → BPS 6,910 · PBR 0.45
    assert extra["002880"]["epsIn"]["ni"] == 131.2 and extra["002880"]["bpsIn"]["eq"] == 646.4
    assert (by["002880"]["eps"], by["002880"]["per"], by["002880"]["bps"], by["002880"]["pbr"]) == (1402.0, 2.2, 6910.0, 0.45)
    assert by["040610"]["pbr"] == 0.09 and by["109960"]["pbr"] == 0.07
    assert cby["250030"]["unitFix"] == [{"rep": "2026.2Q", "bs": 1000, "is": 1000, "cf": 1000}] and "unitFix" not in cby["040610"]
    assert all(type(v) is int for k, v in cby["250030"]["unitFix"][0].items() if k != "rep")     # corp.json 에 1000 (1000.0 아님)
    assert not V.unit_fix_problems(cby["250030"]) and not V.unit_fix_problems(cby["002880"])


@pytest.mark.parametrize("t", ["040610", "109960"])
def test_b1_end_to_end_hides_and_never_publishes_the_divided_numbers(tmp_path, monkeypatch, t):
    """리뷰 #116 B1 (사업보고서 ÷ 1,000 · 분기는 맞음): 예전 고침은 맞는 분기를 나눠 SG&G 에 PER 464 · PBR 91 을 냈어요. 이제 나누지 않고 비워요."""
    over = {f"{t}|2025|11011|{CO[t]['fs']}": scaled(rows(t, 2025, "11011"), 0.001)}
    kr, fm, _, _ = enrich(tmp_path, monkeypatch, [t], override=over)
    assert "unitFix" not in fm[t]
    for s in kr:
        s.update(vol=30.0, mom=1.0)
    extra = F.fill_multiples(kr, fm, {})
    guard = F.unit_guard(kr, fm, extra)
    assert t in guard["hit"] and "scale" in guard["hit"][t]
    assert all(kr[0].get(k) is None for k in ("per", "pbr", "eps", "bps"))


def test_b2_end_to_end_without_a_par_value_hides_and_keeps_the_flows_untouched(tmp_path, monkeypatch):
    t = "040610"
    over = {f"{t}|2026|11012|CFS": only(rows(t, 2026, "11012"), 1000, ("BS",))}
    kr, fm, _, _ = enrich(tmp_path, monkeypatch, [t], override=over)
    assert "unitFix" not in fm[t]                                                         # 가짜 DART 에 배당 표가 없어 액면가를 몰라요
    assert F.unit_check(fm[t], PX[t][1])["why"] == ["scale"]                              # → 비워요 (손익은 맞아 is · eps 는 조용해요)


def test_unitfix_is_kept_only_with_the_ttm_it_fixed(tmp_path, monkeypatch):
    """나눈 보고서로 TTM 을 만들지 못하면 (그 보고서를 쓰지 않으면) unitFix 도 없어요."""
    monkeypatch.setattr(F, "compute_ttm", lambda *a, **k: None)
    kr, fm, fake, _ = enrich(tmp_path, monkeypatch, ["250030"])
    assert "unitFix" not in fm["250030"] and "bq" not in fm["250030"]


def test_last_years_quarter_is_handed_to_the_ttm_undivided(tmp_path, monkeypatch):
    """지난해 같은 분기 보고서는 나누지 않아요 (TTM 에서 빼는 값 · 안전망의 '지난해 같은 분기' 그대로)."""
    seen = []
    real = F.compute_ttm
    monkeypatch.setattr(F, "compute_ttm", lambda fin, ytd, prev: seen.append((ytd, prev)) or real(fin, ytd, prev))
    enrich(tmp_path, monkeypatch, ["250030"])
    ytd, prev = next((y, p) for y, p in seen if y and y.get("unitFix"))
    assert prev == F.parse_dart_quarter(rows("250030", 2025, "11012")) and "unitFix" not in prev


def test_unitfix_never_rides_with_unitchk():
    t = "250030"
    s, fin = company(t)
    fin["unitFix"] = [{"rep": "2026.2Q", "bs": 1000.0, "is": 1000.0, "cf": 1000.0}]
    s["unitChk"] = ["scale"]
    corp = F.build_corp([s], {t: fin}, "2026-11-13")
    assert "unitFix" not in corp["companies"][0]


# ── 4. 관문 ────────────────────────────────────────────────────
FIX_ROW = "공시 단위를 고쳐 읽은 회사 (unitFix · 경고만)"
SHAPE_ROW = "공시 단위 고침 기록 모양 (unitFix)"


def test_gate_lists_every_repaired_company_and_checks_the_record(pair, monkeypatch):
    cur, prev = pair
    c = comp(cur, "200010")
    assert c.get("bq")
    c["unitFix"] = [{"rep": "2026.2Q", "bs": 1000, "is": 1000, "cf": 1000}]
    rep = check(cur, prev)
    got = rows_of(rep)
    assert got[SHAPE_ROW][3] == "PASS" and got[SHAPE_ROW][1] == "1곳 · 어긋남 0"
    assert got[FIX_ROW][3] == "WARN" and got[FIX_ROW][1].startswith("1곳: 200010") and "2026.2Q bs ÷1,000 · is ÷1,000 · cf ÷1,000" in got[FIX_ROW][1]
    assert not rep.failed, rep.table()
    monkeypatch.setattr(V, "UNIT_FIX_CHECKED", {"200010": {"unitFix": c["unitFix"], "date": "2026-11-13", "why": "시험"}})
    got = rows_of(check(cur, prev))
    assert got[FIX_ROW][3] == "PASS" and got[FIX_ROW][1] == "0곳 · 확인된 회사 1곳 조용히 넘김"
    monkeypatch.setattr(V, "UNIT_FIX_CHECKED", {"200010": {"unitFix": [{"rep": "2026.3Q", "bs": 1000}], "date": "2026-11-13", "why": "시험"}})
    assert rows_of(check(cur, prev))[FIX_ROW][3] == "WARN"                                 # 다른 보고서를 고치면 다시 경고


@pytest.mark.parametrize("bad", [[], {"rep": "2026.2Q", "bs": 1000}, [{"rep": "2026-06", "bs": 1000}], [{"rep": "2026.2Q"}],
                                 [{"rep": "2026.2Q", "bs": 100}], [{"rep": "2026.2Q", "xx": 1000}], [{"rep": "2026.2Q", "is": 1.0}],
                                 None, 1000, "2026.2Q", [None], [{"rep": "2026.1Q", "bs": 1000}], [{"rep": "2026.2Q", "bs": True}]])
def test_gate_fails_a_malformed_record(pair, bad):
    """리뷰 #116 2차 N4: None · 숫자도 관문을 멈추지 않고 실패 줄 ('모양이 잘못됨') · 보고서는 bq (2026.2Q) 와 같아야 해요."""
    cur, prev = pair
    comp(cur, "200010")["unitFix"] = bad
    row = fails(cur, prev, SHAPE_ROW)
    assert "모양이 잘못됨" in row[1] or "≠ bq" in row[1], row


def test_gate_checks_the_report_name_even_when_bq_has_the_same_odd_name(pair):
    cur, prev = pair
    c = comp(cur, "200010")
    c["bq"] = "2026-06"
    c["unitFix"] = [{"rep": "2026-06", "bs": 1000}]
    assert any("모양이 잘못됨" in x for x in V.unit_fix_problems(c))


def test_gate_fails_unitfix_with_unitchk_or_without_a_quarter(pair):
    cur, prev = pair
    c = comp(cur, "200010")
    c["unitFix"] = [{"rep": "2026.2Q", "is": 1000}]
    c["unitChk"] = ["scale"]
    assert "200010 unitFix 와 unitChk 가 같이 있어요" in V.unit_fix_problems(c)
    c.pop("unitChk")
    c.pop("bq", None)
    assert "200010 unitFix 인데 bq 없음" in V.unit_fix_problems(c)


def test_the_checked_list_is_empty_and_needs_jacks_yes():
    assert V.UNIT_FIX_CHECKED == {} and V.UNIT_FIX_K == (1000, 1000000) and V.UNIT_FIX_PARTS == ("bs", "is", "cf")
    runbook = open(os.path.join(ROOT, "docs", "RUNBOOK.md"), encoding="utf-8").read()
    assert "UNIT_FIX_CHECKED" in runbook and "only with Jack's yes" in runbook
