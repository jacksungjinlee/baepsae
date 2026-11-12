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
    assert F.bs_factor([ref[0] * 1000, ref[1] * 1000, ref[2] * 999], ref) is None
    assert F.bs_factor([x * 1000 for x in ref], None, 188.0, 332.4) == 1000.0
    assert F.bs_factor([x * 1000 for x in ref], None, 188.2, 332.4) is None                  # 0.05억 밖
    assert F.bs_factor([5.01e13, 4e13, 0.99e8 * 1000], None, 0.99, 400.0) is None            # 자본 1억 미만: 반올림으로는 증명 안 해요
    assert F.bs_factor([5.01e13, 4e13, 1.0e8 * 1000], None, 1.0, 400.0) == 1000.0            # 1억부터
    assert F.bs_factor([5.01e13, 4e13, -1.0e8 * 1000], None, -1.0, 400.0) == 1000.0          # 자본잠식도 크기로
    for bad in (None, [1, 2], [1, None, 3], "x"):
        assert F.bs_factor(bad, ref) is None


def test_the_flow_factor():
    assert F.flow_factor([(231928.2, 231.9), (36323.3, 36.3)]) == 1000.0
    assert F.flow_factor([(231.9, 231.9), (36.3, 36.3)]) == 1.0
    assert F.flow_factor([(231928.2, 231.9), (36.3, 36.3)]) is None                          # 표 안에서 배수가 엇갈리면 증명 안 돼요
    assert F.flow_factor([(None, 231.9), (36323.3, None), (5.0, 0.05)]) is None              # 쓸 쌍이 없음 (0.1억 미만도 빼요)
    assert F.flow_factor([(-1200.0, -1.2)]) == 1000.0                                       # 손실도 같은 배수


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
    t = "040610"
    fin, q, qp = quarters(t, q=only(rows(t, 2026, "11012"), 1000, ("IS", "CIS")))
    plan = F.unit_fix_plan(fin, q, qp, stock(t))
    assert plan == ("fix", 1.0, 1000.0, 1.0), plan
    q2 = dict(q)
    q2.pop("epsYtd")
    assert F.unit_fix_plan(fin, q2, qp, stock(t))[0] == "left"                            # 기본주당이익이 없으면 기준값이 없어요


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


def test_the_columns_must_be_there():
    t = "250030"
    fin, q, qp = quarters(t)
    q.pop("bal0")
    assert F.unit_fix_plan(fin, q, qp, stock(t))[0] == "need"
    assert F.unit_fix_quarter(None, CO[t]["corp"], fin, 2026, "11012", q, qp, stock(t), None, {"fixed": [], "left": [], "redo": 0}) is q


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
                                 [{"rep": "2026.2Q", "bs": 100}], [{"rep": "2026.2Q", "xx": 1000}], [{"rep": "2026.2Q", "is": 1.0}]])
def test_gate_fails_a_malformed_record(pair, bad):
    cur, prev = pair
    comp(cur, "200010")["unitFix"] = bad
    fails(cur, prev, SHAPE_ROW)


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
