# -*- coding: utf-8 -*-
"""v19.1h 배당 맞춤 이유 (dvWhy) — 데이터 쪽 (네트워크 없음).

배당 막대를 오늘 주식 수 기준으로 다시 계산한 해(dpsF ≠ 1)가 있는 국내 종목마다 주식 수가 바뀐 이유 · 날짜 · 배율을 DART 의 결정
공시에서 찾아요 (Jack, 2026-11-08). 공시가 배율과 다르면 다시 계산하지 않고 배당수익률도 숨겨요 (대한제강 · 대동금속 · 티엘비 —
Jack 의 네 가지 답, 2026-11-08).

픽스처 tests/fixtures/dvwhy 는 2026-11-08 에 OpenDART 에서 받은 실제 응답이에요 (키는 응답에 없어요 — 만들 때 확인했어요):
  공시 목록 list.json (I001 · B001 · last_reprt_at=Y, 판단에 쓰는 줄과 앞 3줄만 남김) · fricDecsn · pifricDecsn · crDecsn ·
  주식분할결정·주식병합결정 원문 document.xml (zip 그대로). 종목 값은 그날 발행본 (pxDate 2026-11-06)."""
import collections
import copy
import datetime as dt
import inspect
import io
import json
import math
import os
import sys
import threading
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_v191b_data import check, rows_of, with_new_fields  # noqa: E402
from fixture_data import good_pair  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "dvwhy")
TODAY = dt.date(2026, 11, 8)
PX = dt.date(2026, 11, 6)
CORP = {"084010": "00113225", "020400": "00191287", "356860": "00920379", "001130": "00113243", "183300": "00997812",
        "012280": "00141413", "060560": "00288495", "262840": "01146822"}
T_OF = {v: k for k, v in CORP.items()}
LIVE = {   # 2026-11-08 발행본 (pxDate 2026-11-06) 그대로
    "084010": {"t": "084010", "nk": "대한제강", "fy": 2025, "shr": 34371596, "price": 7430.0, "dps3": [500.0, 500.0, 500.0], "dpsF": [2.0, 2.0, 2.0]},
    "020400": {"t": "020400", "nk": "대동금속", "fy": 2025, "shr": 9073532, "price": 3720.0, "dps3": [60.0, 60.0, 60.0], "dpsF": [3.0, 3.0, 3.0]},
    "356860": {"t": "356860", "nk": "티엘비", "fy": 2025, "shr": 23701260, "price": 26500.0, "dps3": [450.0, 200.0, 200.0], "dpsF": [2.5, 2.5, 2.5]},
    "001130": {"t": "001130", "nk": "대한제분", "fy": 2025, "shr": 16900000, "price": 10600.0, "dps3": [4000.0, 3500.0, 2500.0], "dpsF": [10.0, 10.0, 10.0]},
    "183300": {"t": "183300", "nk": "코미코", "fy": 2025, "shr": 51363275, "price": 16530.0, "dps3": [1400.0, 1000.0, 400.0], "dpsF": [5.0, 5.0, 5.0]},
    "012280": {"t": "012280", "nk": "영화금속", "fy": 2025, "shr": 9716629, "price": 3820.0, "dps3": [35.0, 30.0, 20.0], "dpsF": [0.2, 0.2, 0.2]},
    "060560": {"t": "060560", "nk": "HC홈센타", "fy": 2025, "shr": 25388001, "price": 1840.0, "dps3": [10.0, 30.0, 0.0], "dpsF": [0.2, 0.2, None]},
    "262840": {"t": "262840", "nk": "아이퀘스트", "fy": 2025, "shr": 10249759, "price": 2720.0, "dps3": [70.0, 43.0, 100.0], "dpsF": [0.5, 0.5, None]},
}


def fx_json(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


def fx_zip(rc):
    with open(os.path.join(FX, f"doc_{rc}.zip"), "rb") as f:
        zf = zipfile.ZipFile(io.BytesIO(f.read()))
    return {n: zf.read(n) for n in zf.namelist()}


class FxClient:
    """DartClient 와 같은 모양의 가짜: get · get_zip 은 픽스처(실제 응답), report 는 주식의 총수 현황(stk) 표."""

    def __init__(self, today=TODAY, mode="cache", fail=(), stk=None):
        self.entries, self.meta = {}, {"corpMap": dict(CORP)}
        self.today, self.mode, self.fail = today, mode, set(fail)
        self.status, self.lock = collections.Counter(), threading.Lock()
        self.revalidate_left, self.revalidated, self.down, self.fatal = 300, 0, None, None
        self.started_empty = False
        self.calls, self.stk = [], stk or {}

    def get(self, endpoint, params, timeout=25):
        self.calls.append((endpoint, dict(params)))
        if endpoint in self.fail:
            self.status["예외"] += 1
            return None
        self.status["000"] += 1
        t = T_OF[params["corp_code"]]
        assert params["bgn_de"] == "20230101" and params["end_de"] == self.today.strftime("%Y%m%d")
        if endpoint == "list.json":
            assert params["last_reprt_at"] == "Y" and params["pblntf_detail_ty"] in ("I001", "B001")   # 최종 정정본만
            return fx_json(f"{t}_list_{params['pblntf_detail_ty']}.json")
        return fx_json(f"{t}_{endpoint}")

    def get_zip(self, endpoint, params, timeout=40):
        self.calls.append((endpoint, dict(params)))
        if endpoint in self.fail:
            self.status["예외"] += 1
            return None
        self.status["000"] += 1
        return fx_zip(params["rcept_no"])

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        self.calls.append((endpoint, {"corp_code": corp, "bsns_year": year}))
        rows = self.stk.get((corp, year))
        return parse(rows) if rows else None


def r_of(s):
    """div_basis 결과처럼 (분할 확인을 지난 값)."""
    st3 = [None if d is None else "zero" if d == 0 else ("nc" if f is None else "same" if f == 1 else "adj")
           for d, f in zip(s["dps3"], s["dpsF"])]
    dps3a = [None if d is None else 0.0 if d == 0 else (None if f is None else round(d / f, 2)) for d, f in zip(s["dps3"], s["dpsF"])]
    paid = [x for x in st3 if x in ("same", "adj", "nc", "nd")]
    return {"dps3a": dps3a, "dpsF": list(s["dpsF"]), "st3": st3, "divSt": next(x for x in ("nc", "nd", "adj", "same") if x in paid),
            "f0": s["dpsF"][0] if s["dpsF"][0] is not None else next(f for f in s["dpsF"] if f is not None)}


def run(t, client=None, **kw):
    c = client or FxClient()
    why = F.DivWhy(c, PX, **kw)
    s = copy.deepcopy(LIVE[t])
    r = why.check(s, r_of(LIVE[t]))
    return s, r, why, c


# ── 1. 공시 이름 · 원문 · API 읽기 ─────────────────────────────
def test_filing_names_are_classified_and_subsidiary_and_notice_filings_dropped():
    k = F.dvwhy_kind
    assert k("주식분할결정              ") == ("split", False) and k("[기재정정]주식병합결정") == ("merge", False)
    assert k("주요사항보고서(무상증자결정)") == ("fric", False) and k("[기재정정]주요사항보고서(유무상증자결정)") == ("pifric", False)
    assert k("주요사항보고서(유상증자결정)") == ("rights", False) and k("[기재정정]주요사항보고서(감자결정)") == ("cr", False)
    assert k("주요사항보고서(회사합병결정)") == ("merger", False) and k("주요사항보고서(회사분할결정)") == ("spin", False)
    assert k("주식배당결정") == ("stockdiv", False) and k("주식분할결정((액면분할))")[0] == "split"
    for nm in ("유무상증자결정(종속회사의주요경영사항)", "감자결정(자율공시)(종속회사의주요경영사항)", "회사합병결정(종속회사의주요경영사항)",
               "주권매매거래정지 (주식의 병합, 분할 등 전자등록 변경, 말소)", "권리락 (무상증자)", "주식소각결정", "유상증자1차발행가액결정",
               "주요사항보고서(전환사채권발행결정)(자회사의 주요경영사항)", "주요사항보고서(교환사채권발행결정)", "현금ㆍ현물배당결정"):
        assert k(nm) == (None, False), nm
    assert k("주식분할결정(철회)") == ("split", True) and k("[철회]주요사항보고서(무상증자결정)") == ("fric", True)


def test_the_real_lists_point_to_the_right_decisions():
    def fl(t):
        rows = (fx_json(f"{t}_list_I001.json").get("list") or []) + (fx_json(f"{t}_list_B001.json").get("list") or [])
        return F.dvwhy_filings(rows)
    assert fl("001130")["docs"] == [("split", "20260312802368")] and fl("001130")["api"] == []
    assert fl("012280")["docs"] == [("merge", "20260617800484")]          # 정정본만 (첫 판 20260617800329 는 목록에 없어요)
    k = fl("183300")
    assert k["docs"] == [("split", "20260716900397")] and k["api"] == ["fric"]
    assert k["oth"] == [{"k": "rights", "d": "2023-06-01", "rc": "20230601000160"}]   # 공시일로 놓아요 (2023 → 그 사이 밖)
    assert fl("356860")["api"] == ["pifric"] and fl("356860")["docs"] == []
    d = fl("020400")                                                             # 대동금속: 무상증자 뒤 유상증자 (정정본)
    assert d["api"] == ["fric"] and d["oth"] == [{"k": "rights", "d": "2026-08-12", "rc": "20260812000426"}]
    assert fl("060560")["api"] == ["cr"] and fl("060560")["docs"] == [("merge", "20260316900559")]
    assert [o["k"] for o in fl("084010")["oth"]] == ["spin"] and fl("262840")["api"] == ["fric"]


def test_split_and_merge_documents_are_read_from_the_last_form():
    e, why = F.parse_dvwhy_doc(F.dvwhy_doc_text(fx_zip("20260312802368"), "20260312802368"), "split", "20260312802368")
    assert e == {"k": "split", "d": "2026-04-24", "r": 10.0, "rc": "20260312802368", "src": "doc"} and why is None   # 대한제분
    # 코미코 정정본: 효력발생일 2026-07-30 → 2026-07-31 (정정 표 뒤의 고친 양식을 읽어요)
    e, _ = F.parse_dvwhy_doc(F.dvwhy_doc_text(fx_zip("20260716900397"), "20260716900397"), "split", "20260716900397")
    assert (e["d"], e["r"]) == ("2026-07-31", 2.5)
    # 영화금속: 첫 판은 4:1 (500 → 2,000원), 같은 날 정정본이 5:1 (→ 2,500원). 정정본을 써야 해요
    first, _ = F.parse_dvwhy_doc(F.dvwhy_doc_text(fx_zip("20260617800329"), "20260617800329"), "merge", "20260617800329")
    fixed, _ = F.parse_dvwhy_doc(F.dvwhy_doc_text(fx_zip("20260617800484"), "20260617800484"), "merge", "20260617800484")
    assert first["r"] == 0.25 and fixed["r"] == 0.2 and fixed["d"] == "2026-08-13"
    # LS ELECTRIC 첫 판: 발행주식총수 칸에 수권주식수를 적어 주식 수 비(3.33)가 액면가 비(5)와 달라요 → 읽지 않아요. 정정본은 맞아요
    e, why = F.parse_dvwhy_doc(F.dvwhy_doc_text(fx_zip("20260205800493"), "20260205800493"), "split", "20260205800493")
    assert e is None and "주식 수 비" in why
    e, _ = F.parse_dvwhy_doc(F.dvwhy_doc_text(fx_zip("20260205800571"), "20260205800571"), "split", "20260205800571")
    assert (e["r"], e["d"]) == (5.0, "2026-04-10")


def test_a_document_that_contradicts_its_kind_or_has_no_date_is_not_read():
    txt = F.dvwhy_doc_text(fx_zip("20260312802368"), "20260312802368")
    e, why = F.parse_dvwhy_doc(txt, "merge", "20260312802368")          # 액면가가 줄었는데 '병합'
    assert e is None and "주식병합" in why
    e, why = F.parse_dvwhy_doc(txt.replace("2026-04-24", "미정"), "split", "x")
    assert e is None and "효력발생일" in why
    e, why = F.parse_dvwhy_doc(txt.replace(">500<", ">-<"), "split", "x")
    assert e is None and "1주당 가액" in why
    assert F.parse_dvwhy_doc(None, "split", "x") == (None, "원문 없음") and F.dvwhy_doc_text({}, "x") is None


def test_bonus_issue_rights_issue_and_capital_reduction_apis():
    ev, bad = F.parse_dvwhy_bonus(fx_json("084010_fricDecsn.json")["list"])
    assert bad == [] and ev == [{"k": "bonus", "d": "2026-01-06", "r": 1.6616554, "x": 0.6616554, "rc": "20251222000129", "src": "fric"}]
    pif = fx_json("356860_pifricDecsn.json")["list"]
    ev, bad = F.parse_dvwhy_bonus(pif, pre="fric_")
    assert [(e["d"], e["r"], e["x"], e["rc"]) for e in ev] == [("2026-07-20", 2.0, 1.0, "20260702000142")] and not bad
    assert F.parse_dvwhy_rights(pif) == [{"k": "rights", "d": "2026-07-02", "rc": "20260702000142"}]
    ev, oth, bad = F.parse_dvwhy_cr(fx_json("060560_crDecsn.json")["list"])   # HC홈센타 2024: 액면가만 500 → 100원
    assert ev == [] and oth == [] and bad == []
    row = {"rcept_no": "20260101000001", "bfcr_tisstk_ostk": "10,000,000", "atcr_tisstk_ostk": "1,000,000", "cr_std": "2026년 02월 03일",
           "cr_mth": "보통주 10주를 1주로 주식병합"}
    ev, oth, bad = F.parse_dvwhy_cr([row])
    assert ev == [{"k": "merge", "d": "2026-02-03", "r": 0.1, "rc": "20260101000001", "src": "cr"}] and not oth
    ev, oth, bad = F.parse_dvwhy_cr([{**row, "cr_mth": "자기주식 소각"}])
    assert ev == [] and oth == [{"k": "cr", "d": "2026-02-03", "rc": "20260101000001"}]
    ev, oth, bad = F.parse_dvwhy_cr([{**row, "atcr_tisstk_ostk": "알 수 없음"}])
    assert bad and not ev
    # 우선주만 받는 무상증자는 보통주 수를 바꾸지 않아요 · 읽지 못한 값은 '읽지 못함'(→ 그 종목은 줄 없음)
    ev, bad = F.parse_dvwhy_bonus([{"rcept_no": "20260101000002", "nstk_ascnt_ps_ostk": "-", "nstk_asstd": "2026-01-02"}])
    assert ev == [] and bad == []
    ev, bad = F.parse_dvwhy_bonus([{"rcept_no": "20260101000002", "nstk_ascnt_ps_ostk": "NaN", "nstk_asstd": "2026-01-02"}])
    assert ev == [] and bad


def test_korean_dates_and_receipt_numbers():
    assert F._kdate("2026년 01월 06일") == "2026-01-06" and F._kdate("2026-4-9") == "2026-04-09" and F._kdate("20260715") == "2026-07-15"
    assert F._kdate("2026년 02월 30일") is None and F._kdate("-") is None and F._kdate(None) is None
    assert F._rc_date("20260702000142") == "2026-07-02" and F._rc_date("2026070200014") is None


def test_withdrawn_decisions_are_dropped():
    ev = [{"k": "split", "d": "2026-04-10", "r": 5.0, "rc": "20260201000001"},
          {"k": "bonus", "d": "2026-05-01", "r": 2.0, "x": 1.0, "rc": "20260301000001"}]
    out = F.dvwhy_drop_withdrawn(ev, [{"k": "split", "d": "2026-03-01", "rc": "20260301000009"}])
    assert [e["k"] for e in out] == ["bonus"]
    assert F.dvwhy_drop_withdrawn(ev, [{"k": "split", "d": "2026-01-01", "rc": "20260101000009"}]) == ev   # 결정보다 먼저 낸 철회는 그 결정이 아니에요


# ── 2. 판정 (Jack 의 답 2026-11-08) ──────────────────────────
ZERO = {"v": 1, "ok": 0, "nf": 0, "filed": 0, "nc-mismatch": 0, "nc-unexplained": 0, "fail": 0, "kept": 0, "failT": [], "keptT": []}


def test_daehan_flour_split_is_named_with_its_legal_date():
    """Jack 의 예: 대한제분 2026-04-24 주식 1주를 10주로 (액면분할 · 효력발생일)."""
    s, r, why, c = run("001130")
    assert s["dvWhy"] == {"v": 1, "st": "ok", "ev": [{"k": "split", "d": "2026-04-24", "r": 10.0, "rc": "20260312802368"}]}
    assert r["dpsF"] == [10.0, 10.0, 10.0] and r["divSt"] == "adj"
    assert len(c.calls) == 3                                                    # 목록 2 + 원문 1
    assert why.counts() == {**ZERO, "ok": 1}


def test_comico_bonus_then_split_are_both_recorded_oldest_first():
    """답 3: 한 사이의 두 사건은 둘 다 순서대로 (앱이 Jack 의 두 문장을 하나로 이어요). 무상증자는 신주배정기준일 (답 4)."""
    s, r, why, _ = run("183300")
    assert s["dvWhy"]["ev"] == [{"k": "bonus", "d": "2026-05-27", "r": 2.0, "x": 1.0, "rc": "20260522000156"},
                                {"k": "split", "d": "2026-07-31", "r": 2.5, "rc": "20260716900397"}]     # 2 × 2.5 = 5
    assert r["divSt"] == "adj" and why.n["joined"] == 1 and "사건 둘 이상 1" in why.summary()[0]


@pytest.mark.parametrize("t,why_part", [
    ("084010", "무상증자 ×1.66166 (2026-01-06): 깨끗하지 않은 배율"),       # 공시 1주당 0.6616554주 — 파이프라인은 ×2
    ("020400", "무상증자 ×2 (2026-04-13) = ×2"),                            # 공시 ×2 (그 뒤 유상증자) — 파이프라인은 ×3
    ("356860", "무상증자 ×2 (2026-07-20) = ×2"),                            # 유무상증자 ×2 — 파이프라인은 ×2.5
])
def test_the_three_contradictions_stop_adjusting_and_hide_the_yield(t, why_part):
    """답 1: 공시가 배율과 다른 세 종목 (2026-11-08 사이트에 틀린 숫자) — 다시 계산하지 않고 배당수익률도 숨겨요 (nc-mismatch)."""
    s, r, why, c = run(t)
    assert s["dvWhy"] == {"v": 1, "st": "nc-mismatch"}
    assert r["dpsF"] == [None, None, None] and r["dps3a"] == [None, None, None] and r["st3"] == ["nc"] * 3 and r["divSt"] == "nc"
    assert why.counts() == {**ZERO, "nc-mismatch": 1}
    lines = why.summary()
    assert lines[0].startswith("  !! 배당 맞춤 이유") and "공시와 다름 1" in lines[0]
    assert any(t in x and why_part in x and "배당수익률도 보여 주지 않아요" in x for x in lines)
    assert not any(e in ("piicDecsn.json", "cvbdIsDecsn.json", "bdwtIsDecsn.json") for e, _ in c.calls)   # 사건이 있으면 사채는 안 봐요


def test_a_contradiction_hides_the_yield_even_when_the_latest_year_was_not_adjusted():
    """당기 배율은 1 인데 앞 해의 공시가 배율과 다르면: 앞 해는 다시 계산하지 않고, 당기도 비교 불가로 (배당수익률을 숨겨요)."""
    look = {**LOOK, "ev": [{"k": "split", "d": "2025-04-01", "r": 5.0, "rc": "20250201000001"}]}
    dec = F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, look, "none")
    assert dec["st"] == "nc-mismatch" and dec["hide"] == "nc"
    r = F.dvwhy_apply({"dps3a": [100.0, 100.0, 100.0], "dpsF": [1.0, 2.0, 2.0], "st3": ["same", "adj", "adj"], "divSt": "adj"},
                      [100.0, 200.0, 200.0], dec)
    assert r["dpsF"] == [None] * 3 and r["dps3a"] == [None] * 3 and r["divSt"] == "nc"
    z = F.dvwhy_apply({"dps3a": [0.0, 100.0, 100.0], "dpsF": [None, 2.0, 2.0], "st3": ["zero", "adj", "adj"], "divSt": "adj"},
                      [0.0, 200.0, 200.0], dec)
    assert z["st3"] == ["zero", "nc", "nc"] and z["dps3a"][0] == 0.0          # 배당이 없던 해(0%)는 그대로


def test_the_mismatch_switch_keeps_the_old_adjustment_without_a_line():
    s, r, why, _ = run("084010", stop_mm=False)
    assert "dvWhy" not in s and r["dpsF"] == [2.0, 2.0, 2.0] and why.counts()["keptT"] == ["084010"]


def test_ten_percent_or_smaller_changes_are_left_out():
    """아이퀘스트: 2025-04-29 무상증자 0.1주(×1.1, 10%)는 이름에도 곱에도 넣지 않아요 → 2026-04-16 병합 ×0.5 로 두 해 모두 설명돼요."""
    s, r, _, _ = run("262840")
    assert s["dvWhy"]["ev"] == [{"k": "merge", "d": "2026-04-16", "r": 0.5, "rc": "20260310900582"}] and r["dpsF"] == [0.5, 0.5, None]
    assert not F.dvwhy_named(1.1) and not F.dvwhy_named(0.9) and F.dvwhy_named(1.1001) and not F.dvwhy_named(float("nan"))


def test_par_only_capital_reduction_is_not_a_share_count_change():
    s, _, _, c = run("060560")                    # HC홈센타: 2024 감자는 액면가만, 2026-04-16 병합 ×0.2
    assert s["dvWhy"]["ev"] == [{"k": "merge", "d": "2026-04-16", "r": 0.2, "rc": "20260316900559"}]
    assert ("crDecsn.json", {"corp_code": "00288495", "bgn_de": "20230101", "end_de": "20261108"}) in c.calls


def test_corrections_decide_the_numbers():
    s, _, _, c = run("012280")                    # 영화금속: 정정본 5:1 (첫 판 4:1 이었으면 ×0.25 ≠ 0.2 로 공시와 다름)
    assert s["dvWhy"]["ev"] == [{"k": "merge", "d": "2026-08-13", "r": 0.2, "rc": "20260617800484"}]
    assert ("document.xml", {"rcept_no": "20260617800329"}) not in c.calls


LOOK = {"ev": [], "oth": [], "wd": [], "bad": []}


def test_events_count_only_after_31_december_and_up_to_px_date():
    split = {"k": "split", "d": "2025-12-31", "r": 5.0, "rc": "20251101000001"}
    assert F.dvwhy_after(5.0, 2025, PX, {**LOOK, "ev": [split]})[0] == "noname"     # 12월 31일 당일은 그해 안
    assert [y["v"] for y in F.dvwhy_years([1.0, 5.0, 5.0], 2025, 1.0, PX, {**LOOK, "ev": [split]}, "none")[1:]] == ["ok", "ok"]
    late = {**split, "d": "2026-11-07"}
    assert F.dvwhy_after(5.0, 2025, PX, {**LOOK, "ev": [late]})[0] == "noname"      # pxDate 뒤는 아직 아니에요
    assert F.dvwhy_after(5.0, 2025, PX, {**LOOK, "ev": [{**split, "d": "2026-03-02"}]}) == ("ok", "")


def test_an_event_after_the_report_while_the_latest_factor_is_one_is_a_contradiction():
    """당기 배율 1 (사업보고서 뒤 주식 수 그대로)인데 그 뒤에 분할이 있으면 믿지 않아요 (날짜를 잘못 읽었거나 새 주식이 아직 상장 전)."""
    look = {**LOOK, "ev": [{"k": "split", "d": "2026-03-02", "r": 2.0, "rc": "20260201000001"}]}
    after, why = F.dvwhy_after(1.0, 2025, PX, look)
    assert after == "mismatch" and "2025년 배율은 1 인데" in why
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, look, after)["st"] == "nc-mismatch"
    inside = {**LOOK, "ev": [{"k": "split", "d": "2025-03-02", "r": 2.0, "rc": "20250201000001"}]}
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, inside, F.dvwhy_after(1.0, 2025, PX, inside)[0])["st"] == "ok"


class SynthClient(FxClient):
    """공시 목록 · API 응답을 직접 주는 가짜 (종목 999990 · 기업코드 C9)."""

    def __init__(self, b001=(), api=None, stk=None, fail=()):
        super().__init__(stk=stk, fail=fail)
        self.b001, self.api = list(b001), api or {}
        self.meta["corpMap"] = {"999990": "C9"}

    def get(self, endpoint, params, timeout=25):
        self.calls.append((endpoint, dict(params)))
        if endpoint in self.fail:
            return None
        self.status["000"] += 1
        if endpoint == "list.json":
            rows = self.b001 if params["pblntf_detail_ty"] == "B001" else []
            return {"status": "000", "list": rows, "total_page": 1} if rows else {"status": "013"}
        rows = self.api.get(endpoint)
        return {"status": "000", "list": rows} if rows else {"status": "013"}


def stk_rows(n):
    return [{"se": "보통주", "istc_totqy": f"{n:,}", "distb_stock_co": f"{n:,}"}, {"se": "합계", "istc_totqy": f"{n:,}", "distb_stock_co": f"{n:,}"}]


RIGHTS_ROW = {"report_nm": "주요사항보고서(유상증자결정)", "rcept_no": "20260302000001", "rcept_dt": "20260302"}
CB_ROW = {"report_nm": "주요사항보고서(전환사채권발행결정)", "rcept_no": "20250610000002", "rcept_dt": "20250610"}
S9 = {"t": "999990", "nk": "가상", "fy": 2025, "shr": 10_000_000, "dps3": [100.0, 100.0, 100.0]}


def r9(F_=(2.0, 2.0, 2.0)):
    return r_of({**S9, "dpsF": list(F_)})


def test_a_change_after_the_report_explained_by_a_rights_issue_keeps_the_dividend_as_filed():
    """답 2: 사업보고서 뒤 ×2 인데 분할·병합·무상증자 공시가 없고, 유상증자(신주 480만 주)가 500만 → 1,000만 주를 설명 → 공시된 배당 그대로."""
    c = SynthClient(b001=[RIGHTS_ROW], api={"piicDecsn.json": [{"rcept_no": "20260302000001", "nstk_ostk_cnt": "4,800,000"}]},
                    stk={("C9", 2025): stk_rows(5_000_000)})
    why = F.DivWhy(c, PX)
    s = copy.deepcopy(S9)
    r = why.check(s, r9())
    assert s["dvWhy"] == {"v": 1, "st": "filed", "a": 5_000_000, "b": 10_000_000,
                          "fx": [{"k": "rights", "d": "2026-03-02", "n": 4_800_000, "rc": "20260302000001"}]}
    assert r["dpsF"] == [1.0, 1.0, 1.0] and r["dps3a"] == [100.0, 100.0, 100.0] and r["divSt"] == "same"   # 수익률은 보통처럼
    assert why.counts() == {**ZERO, "filed": 1} and any("공시된 배당 그대로" in x for x in why.summary())
    e = c.entries[f"C9|{F.DVWHY_TAG}"]["d"]
    assert e["fx"] and "fxBad" in e                                             # 주식 수도 캐시에 (다음 실행은 호출 없음)
    n = len(c.calls)
    why2 = F.DivWhy(c, PX)
    why2.check(copy.deepcopy(S9), r9())
    assert [x for x in c.calls[n:] if x[0] != "stockTotqySttus.json"] == []


def test_a_convertible_bond_can_explain_the_change_up_to_its_price_floor():
    """전환사채가 만드는 주식 수는 많아야 발행 때의 1/0.7 배 (전환가액 하한 70%) — 350만 주 → 500만 주까지 덮어요."""
    api = {"cvbdIsDecsn.json": [{"rcept_no": "20250610000002", "cvisstk_cnt": "3,500,000"}]}
    c = SynthClient(b001=[CB_ROW], api=api, stk={("C9", 2025): stk_rows(5_000_000)})
    s = copy.deepcopy(S9)
    F.DivWhy(c, PX).check(s, r9())
    assert s["dvWhy"]["st"] == "filed" and s["dvWhy"]["fx"][0]["k"] == "cb"
    api["cvbdIsDecsn.json"][0]["cvisstk_cnt"] = "2,000,000"                    # 286만 + 50만 < 500만 → 설명 못 함
    c = SynthClient(b001=[CB_ROW], api=api, stk={("C9", 2025): stk_rows(5_000_000)})
    s = copy.deepcopy(S9)
    r = F.DivWhy(c, PX).check(s, r9())
    assert s["dvWhy"] == {"v": 1, "st": "nc-unexplained"} and r["dpsF"] == [None] * 3 and r["divSt"] == "nd"


def test_a_change_after_the_report_that_nothing_explains_hides_the_yield():
    """답 2: 아무 공시도 설명하지 못하면 다시 계산하지 않고 배당수익률을 숨겨요 (nc-unexplained · 줄은 답 1 과 같아요)."""
    for b001, api in (([], {}), ([RIGHTS_ROW], {"piicDecsn.json": [{"rcept_no": "20260302000001", "nstk_ostk_cnt": "1,000,000"}]})):
        c = SynthClient(b001=b001, api=api, stk={("C9", 2025): stk_rows(5_000_000)})
        why = F.DivWhy(c, PX)
        s = copy.deepcopy(S9)
        r = why.check(s, r9())
        assert s["dvWhy"] == {"v": 1, "st": "nc-unexplained"} and r["dpsF"] == [None] * 3 and r["st3"] == ["nd"] * 3
        assert why.counts()["nc-unexplained"] == 1 and any("설명 못 함" in x for x in why.summary())
    # 주식 수가 줄었으면 유상증자·사채로는 설명되지 않아요
    c = SynthClient(b001=[RIGHTS_ROW], api={"piicDecsn.json": [{"rcept_no": "20260302000001", "nstk_ostk_cnt": "9,000,000"}]},
                    stk={("C9", 2025): stk_rows(20_000_000)})
    s = copy.deepcopy(S9)
    F.DivWhy(c, PX).check(s, r9((0.5, 0.5, 0.5)))
    assert s["dvWhy"]["st"] == "nc-unexplained"


def test_filed_keeps_an_in_report_change_that_its_filing_explains():
    """사업보고서 뒤는 유상증자(공시 그대로), 사업보고서 안(2024)은 액면분할 ×5 — 2023 년만 ×5 로 다시 계산해요."""
    split = {"report_nm": "주식분할결정", "rcept_no": "20240301000003", "rcept_dt": "20240301"}
    c = SynthClient(b001=[RIGHTS_ROW], api={"piicDecsn.json": [{"rcept_no": "20260302000001", "nstk_ostk_cnt": "5,000,000"}]},
                    stk={("C9", 2025): stk_rows(5_000_000)})
    c.get_zip = lambda e, p, timeout=40: None
    look = {"ev": [{"k": "split", "d": "2024-05-01", "r": 5.0, "rc": "20240301000003", "src": "doc"}],
            "oth": [{"k": "rights", "d": "2026-03-02", "rc": "20260302000001"}], "wd": [], "bad": []}
    c.entries[f"C9|{F.DVWHY_TAG}"] = {"st": "000", "at": "2026-11-08", "d": {"fy": 2025, "F": [2.0, 2.0, 10.0], "end": "2026-11-08", **look}}
    s = copy.deepcopy(S9)
    r = F.DivWhy(c, PX).check(s, r9((2.0, 2.0, 10.0)))
    assert r["dpsF"] == [1.0, 1.0, 5.0] and r["dps3a"] == [100.0, 100.0, 20.0] and r["divSt"] == "adj"
    assert s["dvWhy"]["st"] == "filed" and s["dvWhy"]["ev"] == [{"k": "split", "d": "2024-05-01", "r": 5.0, "rc": "20240301000003"}]
    assert split["rcept_no"] == s["dvWhy"]["ev"][0]["rc"]


def test_a_failed_bond_or_share_report_lookup_is_a_failed_lookup_not_a_hidden_yield():
    """유상증자·사채 조회나 주식의 총수 현황이 실패하면 조회 실패 — '확인하지 못해' 줄도 수익률 숨김도 아니에요 (맞춤은 그대로)."""
    c = SynthClient(b001=[RIGHTS_ROW], fail={"piicDecsn.json"}, stk={("C9", 2025): stk_rows(5_000_000)})
    why = F.DivWhy(c, PX)
    s = copy.deepcopy(S9)
    assert why.check(s, r9()) == r9() and "dvWhy" not in s and why.counts()["failT"] == ["999990"]
    c = SynthClient(b001=[RIGHTS_ROW], api={"piicDecsn.json": [{"rcept_no": "20260302000001", "nstk_ostk_cnt": "4,800,000"}]})
    why = F.DivWhy(c, PX)
    s = copy.deepcopy(S9)
    assert why.check(s, r9()) == r9() and "dvWhy" not in s and why.counts()["failT"] == ["999990"]


def test_the_after_report_switch_off_keeps_the_old_adjustment():
    c = SynthClient(stk={("C9", 2025): stk_rows(5_000_000)})
    why = F.DivWhy(c, PX, stop_nfa=False)
    s = copy.deepcopy(S9)
    assert why.check(s, r9()) == r9() and "dvWhy" not in s and why.counts()["keptT"] == ["999990"]


def test_bond_and_rights_amounts_are_read_and_unreadable_ones_never_count():
    fx, bad = F.parse_dvwhy_fx([{"rcept_no": "20260812000426", "nstk_ostk_cnt": "3,000,000"}], "rights")   # 대동금속 (실제 응답 모양)
    assert fx == [{"k": "rights", "d": "2026-08-12", "n": 3000000, "rc": "20260812000426"}] and not bad
    fx, bad = F.parse_dvwhy_fx([{"rcept_no": "20240223002359", "cvisstk_cnt": "16,906,170"}], "cb")         # HC홈센타
    assert fx[0]["n"] == 16906170 and fx[0]["d"] == "2024-02-23"
    fx, bad = F.parse_dvwhy_fx([{"rcept_no": "20240223002359", "cvisstk_cnt": "알 수 없음"}], "cb")
    assert fx == [] and bad
    assert F.parse_dvwhy_fx([{"rcept_no": "20240223002359", "nstk_ostk_cnt": "-"}], "rights") == ([], [])
    cover, used = F.dvwhy_cover([{"k": "rights", "d": "2025-06-30", "n": 100, "rc": "1"}, {"k": "rights", "d": "2025-07-02", "n": 10, "rc": "2"},
                                 {"k": "cb", "d": "2024-01-02", "n": 70, "rc": "3"}, {"k": "bw", "d": "2026-11-07", "n": 7, "rc": "4"}], 2025, PX)
    assert cover == 10 + 100 and [x["rc"] for x in used] == ["2", "3"]      # 반년 넘게 앞의 유상증자 · pxDate 뒤 결정은 빼요
    assert F.dvwhy_filed_ok(100, 210, used, 2025, PX)[0] and not F.dvwhy_filed_ok(100, 221, used, 2025, PX)[0]
    assert not F.dvwhy_filed_ok(100, 90, used, 2025, PX)[0] and not F.dvwhy_filed_ok(None, 210, used, 2025, PX)[0]
    assert F.dvwhy_kind("주요사항보고서(전환사채권발행결정)") == ("cb", False)
    assert F.dvwhy_kind("주요사항보고서(신주인수권부사채권발행결정)") == ("bw", False)
    assert F.dvwhy_kind("주요사항보고서(교환사채권발행결정)") == (None, False)     # 교환사채는 이미 있는 주식이라 빼요


def test_not_found_inside_the_report_uses_the_share_report():
    """사업보고서 안의 변화(f0 = 1)인데 결정 공시가 없으면 '찾지 못했지만' 줄: 그해 말 발행 주식 수 → 오늘 상장 주식 수 (다시 계산)."""
    c = SynthClient(stk={("C9", 2023): stk_rows(2_000_000)})
    why = F.DivWhy(c, PX)
    s = copy.deepcopy(S9)
    r0 = r9((1.0, 1.0, 5.0))
    r = why.check(s, r0)
    assert s["dvWhy"] == {"v": 1, "st": "nf", "a": 2000000, "b": 10000000} and r == r0
    assert why.counts() == {**ZERO, "nf": 1} and any("찾지 못했지만" in x for x in why.summary())
    # 발행 주식 수가 배율과 맞지 않으면(×3 ≠ ×5) 공시와 다름 — 다시 계산하지 않고 수익률도 숨겨요
    c2 = SynthClient(stk={("C9", 2023): stk_rows(3_333_333)})
    s2 = copy.deepcopy(S9)
    r = F.DivWhy(c2, PX).check(s2, r0)
    assert s2["dvWhy"] == {"v": 1, "st": "nc-mismatch"} and r["dpsF"] == [None] * 3 and r["divSt"] == "nc"
    # 주식의 총수 현황을 못 받으면 줄 없음 (조회 실패) — 맞춤은 그대로
    why3 = F.DivWhy(SynthClient(), PX)
    s3 = copy.deepcopy(S9)
    assert why3.check(s3, r0) == r0 and "dvWhy" not in s3 and why3.counts()["failT"] == ["999990"]


def test_a_rights_issue_or_merger_without_a_named_event_inside_the_report_is_a_contradiction():
    look = {**LOOK, "oth": [{"k": "rights", "d": "2025-08-01", "rc": "20250801000001"}]}
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, look, "none")["st"] == "nc-mismatch"
    # 그해 말보다 반년 넘게 앞의 공시는 그 사이로 보지 않아요 · 날짜를 모르는 결정은 그 사이로 봐요 (조심하는 쪽) · 사채 발행은 막지 않아요
    old = {**LOOK, "oth": [{"k": "merger", "d": "2023-05-01", "rc": "20230501000001"}]}
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, old, "none")["st"] == "nf"
    nod = {**LOOK, "oth": [{"k": "merger", "d": None, "rc": "x"}]}
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, nod, "none")["st"] == "nc-mismatch"
    cb = {**LOOK, "oth": [{"k": "cb", "d": "2025-08-01", "rc": "20250801000001"}]}
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, cb, "none")["st"] == "nf"
    wd = {**LOOK, "wd": [{"k": "split", "d": "2025-03-01", "rc": "20250301000001"}]}
    assert F.dvwhy_decide([1.0, 2.0, 2.0], 2025, 1.0, PX, wd, "none")["st"] == "nc-mismatch"   # 철회가 있으면 '찾지 못했다'고 하지 않아요


def test_mixed_evidence_never_gives_a_not_found_line():
    """어떤 해는 공시로 설명되는데 다른 해는 공시가 없으면 공시와 다름 (수익률도 숨겨요)."""
    look = {**LOOK, "ev": [{"k": "split", "d": "2024-04-01", "r": 5.0, "rc": "20240201000001"}]}
    dec = F.dvwhy_decide([1.0, 2.0, 10.0], 2025, 1.0, PX, look, "none")      # 2023 은 ×5 로 맞지 않고, 2024 ×2 는 공시 없음
    assert dec["st"] == "nc-mismatch"
    look = {**LOOK, "ev": [{"k": "split", "d": "2025-04-01", "r": 5.0, "rc": "20250201000001"}]}
    dec = F.dvwhy_decide([1.0, 5.0, 10.0], 2025, 1.0, PX, look, "none")      # 2024 는 ×5 로 설명, 2023 ×10 은 ×5 와 다름
    assert dec["st"] == "nc-mismatch"


# ── 3. 조회 실패 · 캐시 · 호출 수 ───────────────────────────────
@pytest.mark.parametrize("fail", ["list.json", "fricDecsn.json", "document.xml"])
def test_a_failed_lookup_never_produces_the_not_found_line(fail):
    """DART 오류 · 시간 초과: dvWhy 없음 · 맞춤은 그대로 (예전과 같음) · 조회 실패로 세고 크게 남겨요."""
    t = "001130" if fail == "document.xml" else "084010"
    s, r, why, c = run(t, client=FxClient(fail={fail}))
    assert "dvWhy" not in s and r["dpsF"] == LIVE[t]["dpsF"]
    assert why.counts()["failT"] == [t] and why.counts()["nf"] == 0 and why.counts()["nc-mismatch"] == 0
    assert any("조회 실패" in x and t in x for x in why.summary())
    assert f"{CORP[t]}|{F.DVWHY_TAG}" not in c.entries                          # 실패는 저장하지 않아요 (다음 실행에 다시)


def test_dart_off_or_unreadable_filings_count_as_failed_lookups():
    why = F.DivWhy(None, PX)
    s = copy.deepcopy(LIVE["084010"])
    r0 = r_of(LIVE["084010"])
    assert why.check(s, r0) == r0 and why.counts()["failT"] == ["084010"]
    c = FxClient()
    c.entries[f"{CORP['001130']}|{F.DVWHY_TAG}"] = {"st": "000", "at": "2026-11-07", "d": {
        "fy": 2025, "F": [10.0, 10.0, 10.0], "end": "2026-11-07", **LOOK, "bad": [{"rc": "1", "why": "1주당 가액을 읽지 못함"}]}}
    s, r, why, _ = run("001130", client=c)
    assert "dvWhy" not in s and r["dpsF"] == [10.0] * 3 and why.counts()["failT"] == ["001130"] and not c.calls


def test_cache_is_reused_until_the_factor_or_the_report_year_changes():
    c = FxClient()
    run("001130", client=c)
    n = len(c.calls)
    s, _, why, _ = run("001130", client=c)                                       # 같은 dpsF · fy → 호출 없음
    assert len(c.calls) == n and s["dvWhy"]["st"] == "ok" and why.n["cache"] == 1
    e = c.entries[f"{CORP['001130']}|{F.DVWHY_TAG}"]
    assert e["st"] == "000" and e["d"]["F"] == [10.0, 10.0, 10.0] and e["d"]["fy"] == 2025
    json.dumps(e, allow_nan=False)                                               # 캐시 파일은 allow_nan=False 로 저장돼요
    live2 = copy.deepcopy(LIVE["001130"])
    live2["dpsF"] = [5.0, 5.0, 5.0]                                              # 오늘 주식 수가 바뀜 → 다시 받아요
    why2 = F.DivWhy(c, PX)
    why2.check(copy.deepcopy(live2), r_of(live2))
    assert len(c.calls) == n + 3 and why2.n["fetched"] == 1
    c.entries[f"{CORP['001130']}|{F.DVWHY_TAG}"]["d"]["fy"] = 2024               # 사업보고서 연도가 바뀜 → 다시 받아요
    run("001130", client=c)
    assert len(c.calls) == n + 6


def test_a_failed_refetch_keeps_yesterdays_result_for_the_same_factor():
    c = FxClient()
    run("001130", client=c)
    e = c.entries[f"{CORP['001130']}|{F.DVWHY_TAG}"]
    e["at"] = "2026-07-01"                                                       # 90일 지나 재확인할 차례
    c.fail = {"list.json"}
    s, _, why, _ = run("001130", client=c)
    assert s["dvWhy"]["ev"][0]["d"] == "2026-04-24" and why.n["stale"] == 1 and c.revalidated == 1
    c2 = FxClient(mode="full", fail={"list.json"})
    c2.entries = c.entries
    s, _, why, _ = run("001130", client=c2)                                      # dart=full 도 실패하면 어제 결과
    assert s["dvWhy"]["st"] == "ok" and why.n["stale"] == 1


def test_a_cache_run_fetches_only_missing_stocks_and_logs_the_calls(monkeypatch):
    """dart=cache: 이 캐시 항목이 없는 회사만 조회해요 (자본금 다시 읽기처럼). 캐시를 비우거나 판을 바꾸지 않아서 전체 DART 실행이 아니에요."""
    assert F.DART_CACHE_VERSION == 2 and F.DVWHY_TAG == "divwhy|v1"
    c = FxClient()
    why = F.DivWhy(c, PX)
    for t in ("001130", "183300", "084010"):
        why.check(copy.deepcopy(LIVE[t]), r_of(LIVE[t]))
    c.status = collections.Counter({"000": len(c.calls)})
    line = why.summary()[0]
    assert "조회 3곳 · 보관본 0곳" in line and f"이번 DART 호출 {len(c.calls)}회" in line and "전체 DART 실행이 아니에요" in line
    assert len(c.calls) <= 3 * 4
    c.started_empty = True
    assert "전체 DART 실행의 일부" in why.summary()[0]
    # 한 실행의 새 조회 상한: 넘으면 조회 실패(줄 없음)로 세고 다음 실행이 이어받아요
    monkeypatch.setattr(F, "DVWHY_PER_RUN", 1)
    why = F.DivWhy(FxClient(), PX)
    for t in ("001130", "183300"):
        why.check(copy.deepcopy(LIVE[t]), r_of(LIVE[t]))
    assert why.counts()["ok"] == 1 and why.counts()["failT"] == ["183300"]


def test_the_lookup_goes_through_the_real_client_and_its_status_counts(tmp_path, monkeypatch):
    """진짜 DartClient: 목록·API 는 get, 원문은 get_zip (zip 을 '000' 으로 세요 · 오류 XML 은 그 상태로) — 한도 초과는 fatal."""
    class Ans:
        def __init__(self, content, js=None):
            self.content, self.js, self.status_code = content, js, 200

        def json(self):
            if self.js is None:
                raise ValueError("JSON 아님")
            return self.js
    with open(os.path.join(FX, "doc_20260312802368.zip"), "rb") as f:
        zbytes = f.read()
    plan = {"list.json": lambda p: Ans(b"", fx_json(f"001130_list_{p['pblntf_detail_ty']}.json")),
            "document.xml": lambda p: Ans(zbytes)}
    seen = []

    def get(url, params=None, timeout=None):
        ep = url.rsplit("/", 1)[-1]
        seen.append((ep, params.get("crtfc_key")))
        return plan[ep](params)
    monkeypatch.setattr(F.requests, "get", get)
    c = F.DartClient("k", today=TODAY, path=str(tmp_path / "c.json.gz"))
    why = F.DivWhy(c, PX, cmap={"001130": CORP["001130"]})
    s = copy.deepcopy(LIVE["001130"])
    why.check(s, r_of(LIVE["001130"]))
    assert s["dvWhy"]["ev"][0]["r"] == 10.0 and c.status["000"] == 2 and c.status["013"] == 1 and len(seen) == 3
    c.save()                                                                     # allow_nan=False 로 저장돼요
    c2 = F.DartClient("k", today=TODAY, path=str(tmp_path / "c.json.gz"))
    assert f"{CORP['001130']}|{F.DVWHY_TAG}" in c2.entries and not c2.started_empty
    plan["document.xml"] = lambda p: Ans(b"<result><status>020</status><message>limit</message></result>")
    assert c.get_zip("document.xml", {"rcept_no": "1"}) is None and c.fatal and c.fatal[0] == "020"


def test_no_nan_reaches_the_cache_or_the_file():
    c = FxClient()
    why = F.DivWhy(c, PX)
    s = copy.deepcopy(LIVE["001130"])
    r = r_of(s)
    r["dpsF"] = [float("nan"), 10.0, 10.0]
    why.check(s, r)
    json.dumps(s["dvWhy"], allow_nan=False)
    json.dumps(c.entries, allow_nan=False)
    assert c.entries[f"{CORP['001130']}|{F.DVWHY_TAG}"]["d"]["F"] == [None, 10.0, 10.0]
    s2 = copy.deepcopy(LIVE["001130"])
    r2 = r_of(s2)
    r2["dpsF"] = [float("nan"), 1.0, None]
    assert why.check(s2, r2) is r2 and "dvWhy" not in s2                          # 다시 계산한 해가 없으면 조회하지 않아요


# ── 4. 파이프라인 연결 ──────────────────────────────────────────
def test_apply_div_basis_hides_the_yield_before_ranking_and_records_the_counts(monkeypatch):
    stocks = [dict(copy.deepcopy(LIVE[t]), cls="kr") for t in ("084010", "001130")]
    rs = {t: {**r_of(LIVE[t]), "lo": None, "hi": None} for t in ("084010", "001130")}
    monkeypatch.setattr(F, "div_basis", lambda d, *a, **k: copy.deepcopy(next(v for t, v in rs.items() if LIVE[t]["dps3"] == d)))
    counts, _ = F.apply_div_basis(stocks, {}, {}, why=F.DivWhy(FxClient(), PX))
    a, b = stocks
    assert a["divSt"] == "nc" and a["dpsF"] == [None] * 3 and "dyt" not in a and a["dvWhy"] == {"v": 1, "st": "nc-mismatch"}
    assert b["divSt"] == "adj" and b["dyt"] == round(400.0 / 10600.0 * 100, 2) and b["dvWhy"]["st"] == "ok"
    assert counts["nc"] == 1 and counts["adj"] == 1 and counts["dyt"] == 1
    assert counts["why"] == {**ZERO, "ok": 1, "nc-mismatch": 1}
    corp = F.build_corp([dict(s, s="etc") for s in stocks], {}, "2026-11-08")
    by = {c["t"]: c for c in corp["companies"]}
    assert by["001130"]["dvWhy"] == b["dvWhy"] and by["084010"]["dvWhy"] == a["dvWhy"]
    assert "dvWhy" in F.CORP_DIV_KEYS


def test_main_checks_the_reasons_and_saves_the_cache_before_ranking():
    src = inspect.getsource(F.main)
    i = src.find("why = DivWhy(client, px_date)")
    assert 0 < i < src.find("apply_div_basis(kr, fin_map, kmeta.get(\"_prefShares\") or {}, why=why)") < src.find("add_percentiles(kr)")
    assert "client.save()" in src[i:src.find("n_dy = ")]


def test_the_switches_follow_jacks_answers():
    """Jack 의 답 (2026-11-08): 둘 다 켜짐. 관문과 파이프라인은 같은 값을 따로 적어요."""
    assert F.DVWHY_STOP_ON_MISMATCH is True and F.DVWHY_STOP_ON_NF_AFTER_REPORT is True
    assert F.DVWHY_ST == V.DVWHY_ST == ("ok", "nf", "filed", "nc-mismatch", "nc-unexplained")
    assert F.DVWHY_TOL == V.DVWHY_TOL == 0.005 and F.SHARE_SAME == V.DVWHY_SAME == F.DVWHY_FILED_SLACK
    assert F.DVWHY_CLEAN_TOL == V.DVWHY_CLEAN_TOL and F.DVWHY_CB_FLOOR == V.DVWHY_CB_FLOOR
    assert F.DVWHY_OTHER_LOOKBACK_DAYS == V.DVWHY_LOOKBACK_DAYS and set(F.DVWHY_FX_EP) == set(V.DVWHY_FX_KINDS)


def test_full_run_estimate_adds_the_reason_lookups_only_when_asked():
    assert F.dart_full_estimate(2418) == F.dart_full_estimate(2418, divwhy=0)       # 예전 값은 그대로
    total, why = F.dart_full_estimate(2418, divwhy=F.DVWHY_EST_STOCKS * F.DVWHY_PER_STOCK)
    assert total == 15456 + 240 < F.DART_FULL_TARGET and "배당 맞춤 이유 약 240" in why
    assert "divwhy=DVWHY_EST_STOCKS * DVWHY_PER_STOCK" in inspect.getsource(F.enrich_with_dart)


# ── 5. 관문 새 줄 (must-fail) ──────────────────────────────────
NEW_ROWS = ("배당 맞춤 이유 기록 (divCheck.why)", "배당 맞춤 이유 칸 (dvWhy · 다시 계산한 해가 있는 종목)",
            "배당 맞춤 이유 모양 (사건 · 배율 · 날짜 · 접수번호 · a·b · fx)",
            "배당 맞춤 이유 = 배율 (사건의 곱 = dpsF · 숨긴 수익률 · 날짜는 그 사이)",
            "corp.json dvWhy = data.json", "배당 맞춤 이유 경고 (공시 없음 · 공시 그대로 · 수익률 숨김 · 조회 실패)")
BONUS = {"k": "bonus", "d": "2025-05-20", "r": 2.0, "x": 1.0, "rc": "20250425000123"}
FILED = {"v": 1, "st": "filed", "a": 5_000_000, "b": 10_000_000, "fx": [{"k": "rights", "d": "2026-03-02", "n": 4_800_000, "rc": "20260302000001"}]}


def with_why(files):
    """v19.1b 칸을 채운 픽스처(맞춘 종목은 dpsF [1, 2, 2] · fy 2025 · pxDate 2026-10-30)에 dvWhy 와 divCheck.why 를 파이프라인처럼."""
    with_new_fields(files)
    kr = [s for s in files["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    for s in kr:
        if s.get("divSt") == "adj":
            s["dvWhy"] = {"v": 1, "st": "ok", "ev": [dict(BONUS)]}
    for s in kr:
        mirror(files, s)
    recount_why(files)
    return files


def recount_why(files, fail=(), kept=()):
    kr = [s for s in files["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    st = collections.Counter(s["dvWhy"]["st"] for s in kr if isinstance(s.get("dvWhy"), dict) and s["dvWhy"].get("st") in V.DVWHY_ST)
    files["data"]["divCheck"]["why"] = {"v": 1, **{k: st[k] for k in V.DVWHY_ST}, "fail": len(fail), "kept": len(kept),
                                        "failT": sorted(fail), "keptT": sorted(kept)}


def adj_of(files):
    return [s for s in files["data"]["stocks"] if s.get("cls") == "kr" and s.get("divSt") == "adj"]


def mirror(files, s):
    for c in files["corp"]["companies"]:
        if c["t"] == s["t"]:
            for k in ("dvWhy", "dps3a", "dpsF", "divSt", "dyt", "dz"):
                if k in s:
                    c[k] = copy.deepcopy(s[k])
                else:
                    c.pop(k, None)


def hide(files, s, st="nc-mismatch"):
    """파이프라인처럼: 다시 계산하지 않고 배당한 모든 해를 비교 불가로 (배당수익률 · 순위 없음)."""
    from test_v191b_data import recount
    s.update(dps3a=[None if (d or 0) > 0 else d for d in s["dps3"]], dpsF=[None] * 3,
             divSt="nc" if st == "nc-mismatch" else "nd", dvWhy={"v": 1, "st": st})
    s.pop("dyt", None), s.pop("dz", None)
    mirror(files, s)
    recount(files)


def make_filed(files, s):
    s.update(shr=10_000_000, dvWhy=copy.deepcopy(FILED))
    mirror(files, s)


@pytest.fixture
def pair():
    cur, prev, _ = good_pair()
    return with_why(cur), prev


def _fails(cur, prev, name):
    rep = check(cur, prev)
    assert name in {r[0] for r in rep.failed}, rep.table()
    return rep


def test_good_reasons_pass_every_new_row(pair):
    cur, prev = pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    got = rows_of(rep)
    assert all(got[n][3] == "PASS" for n in NEW_ROWS), [got[n] for n in NEW_ROWS if got[n][3] != "PASS"]
    assert not check(cur, None, mode="live").failed


def test_data_before_v191h_is_only_a_warning_until_published(pair):
    cur, prev = pair
    old, _, _ = good_pair()
    with_new_fields(old)                                                         # v19.1b 칸은 있고 why 는 없음
    rep = check(old, prev)
    assert not rep.failed and rows_of(rep)[NEW_ROWS[0]][3] == "WARN" and not any(n in rows_of(rep) for n in NEW_ROWS[1:])
    rep = check(old, {"data": cur["data"]})                                      # 한 번 발행된 뒤 빠지면 실패
    assert NEW_ROWS[0] in {r[0] for r in rep.failed}


def test_hidden_filed_and_failed_stocks_pass_and_warn_by_name(pair):
    """수익률을 숨긴 종목(nc-mismatch · nc-unexplained) · 공시 그대로(filed) · 조회 실패는 발행을 막지 않고 이름과 함께 경고해요."""
    cur, prev = pair
    a1, a2, a3 = adj_of(cur)[:3]
    hide(cur, a1, "nc-mismatch")
    hide(cur, a2, "nc-unexplained")
    a3.pop("dvWhy")
    mirror(cur, a3)
    same = next(s for s in cur["data"]["stocks"] if s.get("divSt") == "same" and s["t"] not in V.MUST)
    make_filed(cur, same)
    recount_why(cur, fail=[a3["t"]])
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    row = rows_of(rep)[NEW_ROWS[5]]
    assert row[3] == "WARN" and all(t in row[1] for t in (a1["t"], a2["t"], a3["t"], same["t"]))
    assert {t for t, _ in rep.details} >= {"배당 맞춤 이유 공시와 달라 수익률 숨김", "배당 맞춤 이유 설명 못 해 수익률 숨김",
                                           "배당 맞춤 이유 조회 실패", "배당 맞춤 이유 공시된 배당 그대로"}


@pytest.mark.parametrize("change", ["version", "count", "fail_list", "unknown_ticker", "fail_with_line", "kept_count"])
def test_the_record_must_match_the_stocks(pair, change):
    cur, prev = pair
    w = cur["data"]["divCheck"]["why"]
    s = adj_of(cur)[0]
    if change == "version":
        w["v"] = 2
    elif change == "count":
        w["ok"] += 1
    elif change == "fail_list":
        w["failT"] = [s["t"]]                                                    # fail 1 이어야 하는데 0
    elif change == "unknown_ticker":
        w.update(fail=1, failT=["999999"])
    elif change == "fail_with_line":
        w.update(fail=1, failT=[s["t"]])                                         # 조회 실패라면서 이유 줄이 있음
    else:
        w["kept"] = "1"
    _fails(cur, prev, NEW_ROWS[0])


def test_a_reason_on_a_stock_without_an_adjusted_year_fails(pair):
    cur, prev = pair
    s = next(x for x in cur["data"]["stocks"] if x.get("divSt") == "same")
    s["dvWhy"] = {"v": 1, "st": "ok", "ev": [dict(BONUS)]}
    mirror(cur, s)
    recount_why(cur)
    _fails(cur, prev, NEW_ROWS[1])


def test_an_adjusted_stock_without_a_reason_fails_unless_its_lookup_failed(pair):
    cur, prev = pair
    s = adj_of(cur)[0]
    s.pop("dvWhy")
    mirror(cur, s)
    recount_why(cur)
    _fails(cur, prev, NEW_ROWS[1])
    recount_why(cur, fail=[s["t"]])                                              # 조회 실패로 적혀 있으면 경고만
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert rows_of(rep)[NEW_ROWS[5]][3] == "WARN" and s["t"] in rows_of(rep)[NEW_ROWS[5]][1]


def test_a_hidden_reason_on_a_still_adjusted_stock_fails(pair):
    cur, prev = pair
    s = adj_of(cur)[0]
    s["dvWhy"] = {"v": 1, "st": "nc-mismatch"}                                  # 수익률을 숨긴다면서 아직 다시 계산함
    mirror(cur, s)
    recount_why(cur)
    rep = _fails(cur, prev, NEW_ROWS[1])
    assert NEW_ROWS[3] in {r[0] for r in rep.failed}


@pytest.mark.parametrize("change", ["kind", "unclean", "small", "split_down", "bonus_x", "date", "rc", "rc_future", "order",
                                    "extra_key", "st", "nf_shape", "empty", "not_dict", "st_list", "nc_extra", "filed_fx"])
def test_malformed_reasons_fail(pair, change):
    cur, prev = pair
    s = adj_of(cur)[0]
    e = s["dvWhy"]["ev"][0]
    if change == "not_dict":
        s["dvWhy"] = ["split"]                                                   # 관문이 멈추지 않고 실패로 적어요
    elif change == "st_list":
        s["dvWhy"]["st"] = ["ok"]
    elif change == "kind":
        e["k"] = "rights"
    elif change == "unclean":
        e.update(r=1.6616554, x=0.6616554)
    elif change == "small":
        e.update(r=1.1, x=0.1)
    elif change == "split_down":
        s["dvWhy"]["ev"] = [{"k": "split", "d": e["d"], "r": 0.5, "rc": e["rc"]}]
    elif change == "bonus_x":
        e["x"] = 2.0
    elif change == "date":
        e["d"] = "2025-02-30"
    elif change == "rc":
        e["rc"] = "2025042500012"
    elif change == "rc_future":
        e["rc"] = "20270101000001"
    elif change == "order":
        s["dvWhy"]["ev"] = [dict(e), {"k": "split", "d": "2025-01-10", "r": 2.0, "rc": "20241201000001"}]
    elif change == "extra_key":
        e["note"] = "x"
    elif change == "st":
        s["dvWhy"]["st"] = "mm"
    elif change == "nf_shape":
        s["dvWhy"] = {"v": 1, "st": "nf", "a": 5, "b": 5}
    elif change == "empty":
        s["dvWhy"]["ev"] = []
    elif change == "nc_extra":
        hide(cur, s)
        s["dvWhy"]["ev"] = [dict(BONUS)]
    else:
        same = next(x for x in cur["data"]["stocks"] if x.get("divSt") == "same" and x["t"] not in V.MUST)
        make_filed(cur, same)
        same["dvWhy"]["fx"][0]["k"] = "merger"
        s = same
    mirror(cur, s)
    recount_why(cur)
    _fails(cur, prev, NEW_ROWS[2])


@pytest.mark.parametrize("change", ["ratio", "missing_event", "before_window", "after_px", "wrong_gap", "nf_b", "nf_ratio",
                                    "nc_shown", "filed_cover", "filed_b", "filed_fx_date", "filed_adjusted_now"])
def test_reasons_that_do_not_explain_the_factor_fail(pair, change):
    cur, prev = pair
    s = adj_of(cur)[0]                                                           # dpsF [1, 2, 2] · fy 2025 · pxDate 2026-10-30
    e = s["dvWhy"]["ev"][0]
    same = next(x for x in cur["data"]["stocks"] if x.get("divSt") == "same" and x["t"] not in V.MUST)
    if change == "ratio":
        e.update(r=3.0, x=2.0)
    elif change == "missing_event":
        s["dvWhy"]["ev"] = [{"k": "split", "d": "2026-03-02", "r": 2.0, "rc": "20260201000001"}]   # 2025 년 배율 1 과 맞지 않아요
    elif change == "before_window":
        e["d"] = "2023-12-31"
    elif change == "after_px":
        e["d"] = "2026-10-31"
    elif change == "wrong_gap":
        e["d"] = "2024-06-01"                                                    # 2024 년 안: 2024 년 배율 2 를 설명하지 못해요
    elif change == "nf_b":
        s["dvWhy"] = {"v": 1, "st": "nf", "a": 500, "b": 999}
    elif change == "nf_ratio":
        s["shr"] = 10_000_000
        s["dvWhy"] = {"v": 1, "st": "nf", "a": 2_000_000, "b": 10_000_000}       # ×5 ≠ 2
    elif change == "nc_shown":
        s["dvWhy"] = {"v": 1, "st": "nc-mismatch"}
        s.update(dpsF=[1.0, None, None], dps3a=[s["dps3"][0], None, None], divSt="nc")   # 당기 수익률이 아직 보여요
        from test_v191b_data import recount
        recount(cur)
    else:
        make_filed(cur, same)
        s = same
        if change == "filed_cover":
            s["dvWhy"]["fx"][0]["n"] = 1_000_000                                 # 100만 + 50만 < 500만
        elif change == "filed_b":
            s["dvWhy"]["b"] = 9_999_999
        elif change == "filed_fx_date":
            s["dvWhy"]["fx"][0]["d"] = "2025-03-02"                              # 사업보고서 말보다 반년 넘게 앞의 유상증자
        else:
            s.update(dpsF=[None, None, None], dps3a=[None, None, None], divSt="nd")
            from test_v191b_data import recount
            recount(cur)
    mirror(cur, s)
    recount_why(cur)
    _fails(cur, prev, NEW_ROWS[3])


def test_a_not_found_reason_that_fits_passes_and_warns(pair):
    cur, prev = pair
    s = adj_of(cur)[0]
    s["shr"] = 10_000_000
    s["dvWhy"] = {"v": 1, "st": "nf", "a": 5_000_000, "b": 10_000_000}
    mirror(cur, s)
    recount_why(cur)
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert rows_of(rep)[NEW_ROWS[5]][3] == "WARN" and "공시 없음 1" in rows_of(rep)[NEW_ROWS[5]][1]


def test_corp_must_mirror_data(pair):
    cur, prev = pair
    s = adj_of(cur)[0]
    for c in cur["corp"]["companies"]:
        if c["t"] == s["t"]:
            c["dvWhy"]["ev"][0]["r"] = 3.0
    _fails(cur, prev, NEW_ROWS[4])


def test_gate_reads_the_numbers_separately_but_agrees_with_the_pipeline():
    assert V.DVWHY_KINDS == ("split", "merge", "bonus")
    for r in (2.0, 2.5, 10.0, 0.2, 0.5, 0.1, 1 / 3):
        assert V._dvwhy_clean(r) and F.dvwhy_clean(r)
    for r in (1.6616554, 1.5, 6.0, 1.1):
        assert not V._dvwhy_clean(r) and not F.dvwhy_clean(r)
