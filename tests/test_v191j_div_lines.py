# -*- coding: utf-8 -*-
"""v19.1j 배당 후속 (Jack, 2026-11-15 — 11-15 아침 답 11 · 12 · 13) — 데이터 · 관문 (네트워크 없음).

- 답 12 (안전 규칙 변경 · 늦춤, Jack 의 분명한 yes): 공시가 준 정확한 무상증자 배율은 깨끗한 분할 배율이 아니어도 받아요 — 세 조건을 모두 지킬
  때만: (가) 깨끗하지 않은 배율의 사건은 무상증자 결정 API(fricDecsn · pifricDecsn)의 무상증자이고 r = 1 + x · (나) 그 곱이 dpsF 와 1e-6 안 ·
  (다) dvProof 검사가 맞아요. 그 밖의 깨끗하지 않은 배율(주식 수로 짐작한 배율 · 곱이 다름 · 무상증자가 아닌 사건 · dvProof 없음)은 예전처럼 실패.
- 답 11 · 13: 숨긴 이유마다 앱이 보여 줄 줄을 파이프라인이 한 곳에서 정해요 (data.json dvLine 2 · 3 · divCheck.proofSub) — 줄은 그 말이 그대로
  맞을 때만 (주주배정이고 새 주식이 상장됨 · 배당 표가 회사의 주식 수와 실제로 어긋남). 관문은 표시와 기록이 꼭 맞는지 봐요.

픽스처: tests/fixtures/dvproof/cases.json (v19.1i) 과 cases_1115.json (같은 2026-11-14 조사의 실제 OpenDART 응답을 파이프라인의 해석 함수로
읽은 값 · 키 없음). 종목 값은 2026-11-14 23:08 발행본 (pxDate 2026-11-13)."""
import collections
import copy
import datetime as dt
import json
import os
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_v191b_data import check, rows_of, recount  # noqa: E402
from test_v191h_div_why import recount_why, mirror  # noqa: E402
from test_v191i_div_proof import with_proof, PROOF0, ROWS  # noqa: E402
from fixture_data import good_pair  # noqa: E402


def _load(name):
    with open(os.path.join(ROOT, "tests", "fixtures", "dvproof", name), encoding="utf-8") as f:
        return json.load(f)


FX0, FX1 = _load("cases.json"), _load("cases_1115.json")
assert not set(FX0["cases"]) & set(FX1["cases"])
CASES = {**FX0["cases"], **FX1["cases"]}
PX = dt.date.fromisoformat(FX1["px"])
TODAY = dt.date.fromisoformat(FX1["today"])
RATIO7 = ("000500", "004270", "008830", "032540", "084010", "196170", "472850")        # v19.1i 의 ratio 7곳 (11-14)
RIGHTS_LINE = "유상증자로 주가 기준이 바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요."
DATA_LINE = "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요."
MISSING_LINE = "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요."            # Jack 2026-11-19
DIV_ROW = "국내 dps3a = dps3 ÷ 배율 · divSt 맞음"
WHY_ROWS = ("배당 맞춤 이유 모양 (사건 · 배율 · 날짜 · 접수번호 · a·b · fx)", "배당 맞춤 이유 = 배율 (사건의 곱 = dpsF · 숨긴 수익률 · 날짜는 그 사이)")
SUB_ROW = "숨긴 배당수익률의 줄 (divCheck.proofSub · dvLine 2 · 3 · 4)"


class Client:
    """DartClient 모양의 가짜 (tests/test_v191i_div_proof.py 의 것과 같아요 · 두 픽스처를 함께 써요)."""

    def __init__(self, ts, edit=None):
        self.entries = {}
        self.meta = {"corpMap": {t: CASES[t]["corp"] for t in ts}}
        self.today, self.mode = TODAY, "cache"
        self.status, self.lock = collections.Counter(), threading.Lock()
        self.revalidate_left, self.revalidated, self.down, self.fatal = 300, 0, None, None
        self.started_empty = False
        self.calls = []
        self.t_of = {CASES[t]["corp"]: t for t in ts}
        self.edit = edit or {}

    def seed(self, t, f_key):
        c = CASES[t]
        look = copy.deepcopy(c["look"])
        if t in self.edit:
            self.edit[t](look)
        self.entries[f"{c['corp']}|{F.DVWHY_TAG}"] = {"st": "000", "at": TODAY.isoformat(),
                                                      "d": {"fy": c["s"]["fy"], "F": f_key, "end": TODAY.isoformat(), **look}}

    def get(self, endpoint, params, timeout=25):
        self.calls.append(endpoint)
        self.status["예외"] += 1
        return None

    def get_zip(self, endpoint, params, timeout=40):
        self.calls.append(endpoint)
        self.status["예외"] += 1
        return None

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        self.calls.append(endpoint)
        t = self.t_of[corp]
        c = CASES[t]
        if endpoint != "stockTotqySttus.json":
            return None
        got = copy.deepcopy(c["stk"]) if year == c["s"]["fy"] else None
        self.entries[f"{corp}|{year}|{reprt}|{tag}"] = {"st": "000" if got else "013", "at": TODAY.isoformat(), "d": got}
        return got


def basis_of(t):
    c = CASES[t]
    cap = c["cap"] or {}
    stk = c["stk"] if c["bas"] and F.unlisted_paid(c["bas"], len(c["pref"])) else None
    return F.div_basis(c["s"]["dps3"], c["bas"], cap.get("cs3"), c["s"]["shr"], c["pref"], cap.get("ss3"), cap_k=cap.get("k", "all"),
                       cap_src=cap.get("src"), stk=stk)


def stock_of(t, shr=None):
    c = CASES[t]
    s = dict(copy.deepcopy(c["s"]), cls="kr")
    if shr:
        s["shr"] = shr
    s["_bas"] = copy.deepcopy(c["bas"])
    if c["cap"]:
        s["_cap"] = copy.deepcopy(c["cap"])
    if c["bas"] and F.unlisted_paid(c["bas"], len(c["pref"])):
        s["_stk"] = copy.deepcopy(c["stk"])
    return s


def run(*ts, edit=None, prove=None):
    cl = Client(ts, edit=edit)
    for t in ts:
        cl.seed(t, [F._fin(x) for x in basis_of(t)["dpsF"]])
    why = F.DivWhy(cl, PX, prove=prove)
    stocks = [stock_of(t) for t in ts]
    pref = {t[:5]: CASES[t]["pref"] for t in ts if CASES[t]["pref"]}
    counts, _ = F.apply_div_basis(stocks, {}, pref, why=why)
    return {s["t"]: s for s in stocks}, counts, why, cl


def comp_of(t):
    return {"t": t, "cash3": [round(x / 1e8, 2) if x is not None else None for x in CASES[t]["bas"]["cash3"]]}


# ── 1. 순수 함수 · 두 파일의 같은 값 ───────────────────────────
def test_the_line_for_each_reason_is_decided_in_one_function():
    assert F.prove_line("line") == 1 and F.prove_line("line", None) == 1
    assert F.prove_line("rights", "sh") == 2 and F.prove_line("rights", "shnew") is None and F.prove_line("rights", "unk") is None
    assert F.prove_line("data", "div") == 3
    for sub in ("nototal", "nostk", "pref0", "nopfo", "prefmix"):
        assert F.prove_line("data", sub) == 4, sub                                          # 회사 공시에 조각이 빠졌으면 줄 4 (Jack 2026-11-19)
    for sub in ("neg", "noshr", "other"):
        assert F.prove_line("data", sub) is None, sub                                       # 어긋남인지 모름 · 회사 공시가 아님 · 이름 없는 이유 — 줄 없음
    for reason in ("ratio", "basis", "uncounted", "fail", "today"):
        assert F.prove_line(reason, "div") is None and F.prove_line(reason, "sh") is None
    assert set(F.PROVE_SUB_LINE["data"]) <= set(F.PROVE_SUB["data"]) and set(F.PROVE_SUB_LINE["rights"]) <= set(F.PROVE_SUB["rights"])


def test_every_dividend_table_reason_has_its_own_case():
    """prove_receiving 이 돌려주는 이유 글마다 정해진 경우가 있어요. 모르는 글이면 other — 줄이 없어요 (리뷰 2026-11-19 · 아래
    test_an_unnamed_dividend_table_reason_gets_no_line_and_is_counted)."""
    whys = {F.prove_receiving(0, 100, [])[2], F.prove_receiving(1e9, 100, [120.0, 130.0], 1e6)[2], F.prove_receiving(1e9, 100, [120.0], None)[2],
            F.prove_receiving(1e9, 100, [120.0], 0)[2], F.prove_receiving(1e6, 100, [120.0], 1e6)[2]}
    assert whys == set(F.PROVE_DATA_WHY) and set(F.PROVE_DATA_WHY.values()) <= set(F.PROVE_SUB["data"])
    assert "other" in F.PROVE_SUB["data"] and "other" not in F.PROVE_DATA_WHY.values() and "other" not in F.PROVE_SUB_LINE["data"]
    assert F.prove_line("data", "other") is None
    assert F.PROVE_DATA_WHY[F.prove_receiving(1e9, 100, [120.0], 0)[2]] == "pref0"          # 메디톡스 (의결권 있는 우선주가 한 줄)


def test_gate_and_pipeline_write_the_new_values_separately_but_agree():
    assert V.PROVE_LINE == F.PROVE_LINE and V.PROVE_SUB == F.PROVE_SUB and V.PROVE_SUB_LINE == F.PROVE_SUB_LINE
    assert V.PROVE_SUB_KO == F.PROVE_SUB_KO and V.EXACT_TOL == F.PROVE_EXACT_TOL == 1e-6


def test_an_exact_bonus_is_one_read_from_the_bonus_api_with_r_one_plus_x():
    e = dict(CASES["084010"]["look"]["ev"][0])                                                  # 대한제강 fricDecsn: 1주당 0.6616554주
    assert e["src"] == "fric" and F.prove_exact_bonus(e) and not F.dvwhy_clean(e["r"])
    assert F.prove_exact_bonus({**e, "src": "pifric"})                                          # 유무상증자의 무상 몫도
    assert not F.prove_exact_bonus({k: v for k, v in e.items() if k != "src"})                  # 어디서 읽었는지 모르면
    assert not F.prove_exact_bonus({**e, "src": "doc"}) and not F.prove_exact_bonus({**e, "k": "split"})
    assert not F.prove_exact_bonus({**e, "r": 1.66}) and not F.prove_exact_bonus({k: v for k, v in e.items() if k != "x"})
    assert not F.prove_exact_bonus({**e, "x": 0.0, "r": 1.0})
    assert F.prove_prod([e]) == 1 + 0.6616554 and F.prove_prod([]) == 1.0 and isinstance(F.prove_prod([]), float)
    m = {"k": "merge", "d": "2026-04-15", "r": 0.1, "rc": "20260303800838", "src": "doc"}
    assert F.prove_ev_ok([m, e]) and not F.prove_ev_ok([m, {**e, "src": "doc"}])
    assert F.prove_same(1.6616554, 1.661655, True) and not F.prove_same(1.6616554, 1.66166, True)
    assert F.prove_same(2.0, 2.009, False) and not F.prove_same(2.0, 2.02, False)               # 깨끗한 배율은 예전처럼 ± 0.5%


# ── 2. 실제 종목: 답 12 ─────────────────────────────────────
def test_the_seven_exact_bonus_ratios_come_back_or_meet_the_rights_rule():
    """v19.1i 의 ratio 7곳: 6곳은 공시의 정확한 무상증자 배율로 되살리고, 대동기어는 그 유무상증자의 유상 몫이 주주배정(64%)이라
    권리락 규칙(rights)이 막아요 — 답 11 의 줄."""
    by, counts, why, _ = run(*RATIO7)
    want = {"084010": (3.73, "yearEnd", [1.661655] * 3), "032540": (5.73, "today", [1.5] * 3), "472850": (4.09, "today", [1.780175, 1.780175, None]),
            "004270": (4.18, "yearEnd", [0.13, None, None]), "196170": (0.16, "today", [1.3, None, None]), "000500": (0.03, "today", [1.8, None, None])}
    for t, (y, how, f3) in want.items():
        s = by[t]
        assert s["dyt"] == y and s["dvProof"]["y0"] == how and s["dpsF"] == f3, (t, s["dyt"], s["dpsF"])
        assert s["dvWhy"]["st"] == "ok" and any(e["k"] == "bonus" and not F.dvwhy_clean(e["r"]) for e in s["dvWhy"]["ev"]) and "dvLine" not in s
        assert V.exact_bonus_problem(s, comp_of(t), PX) is None, (t, V.exact_bonus_problem(s, comp_of(t), PX))
        assert V.dvproof_problems(s, comp_of(t), PX, exact=True) is None and V.dvwhy_problems(s, PX, TODAY, exact=True) == (None, None)
    dg = by["008830"]
    assert "dyt" not in dg and "dvProof" not in dg and dg["dvLine"] == 2 and dg["dpsF"] == [None] * 3
    assert counts["proof"]["ratioT"] == [] and counts["proof"]["rightsT"] == ["008830"] and counts["proofSub"]["rights"] == {"008830": "sh"}
    assert any("008830 대동기어" in x and "주주배정 유상증자(2026-07-15 · 증자 전의 64%)" in x for x in why.summary())
    assert counts["proof"]["today"] == 4 and counts["proof"]["yearEnd"] == 2


def test_namsung_keeps_its_whole_merge_next_to_the_exact_bonus():
    """남성: 주식병합 ×0.1 (원문 · 깨끗한 배율) 뒤 무상증자 ×1.3 (API) — 깨끗하지 않은 배율의 사건만 무상증자면 돼요."""
    by, _, _, _ = run("004270")
    s = by["004270"]
    assert [(e["k"], e["r"]) for e in s["dvWhy"]["ev"]] == [("merge", 0.1), ("bonus", 1.3)] and s["dps3a"][0] == round(25 / 0.13, 2)


def test_earlier_bars_come_back_with_exact_bonus_ratios_where_the_same_rule_allows():
    by, counts, _, _ = run("042500", "003690", "032540")
    ln, kr, tj = by["042500"], by["003690"], by["032540"]
    assert ln["dpsF"] == [1.0, 1.2, 1.56] and ln["dvProof"]["yrs"] == [1, 2] and ln["divSt"] == "adj"      # 링네트: 무상증자 ×1.2 · ×1.3
    assert kr["dpsF"] == [1.0, 1.0, 1.2] and kr["dvProof"]["yrs"] == [2]                                  # 코리안리: 2024 무상증자 ×1.2
    assert tj["dpsF"] == [1.5, 1.5, 1.5] and tj["dvProof"]["yrs"] == [1, 2]
    for t, s in by.items():
        assert V.exact_bonus_problem(s, comp_of(t), PX) is None, (t, V.exact_bonus_problem(s, comp_of(t), PX))
    assert counts["proof"]["years"] == 3


@pytest.mark.parametrize("edit,why", [
    (lambda lk: lk["ev"][0].pop("src"), "어디서 읽었는지 모르는 사건"),
    (lambda lk: lk["ev"][0].update(src="doc", k="split"), "원문의 분할"),
    (lambda lk: lk["ev"][0].update(r=1.67), "r ≠ 1 + x"),
    (lambda lk: lk["ev"][0].pop("x"), "x 없음"),
])
def test_other_non_whole_ratios_stay_hidden_as_before(edit, why):
    by, counts, w, _ = run("084010", edit={"084010": edit})
    s = by["084010"]
    assert counts["proof"]["ratioT"] == ["084010"] and "dyt" not in s and "dvProof" not in s and "dvLine" not in s, why
    assert s["dvWhy"] == {"v": 1, "st": "nc-mismatch"}                                          # 맞춤 이유(#98) 그대로
    assert any("그대로 숨김(ratio) 084010 대한제강" in x and "줄 없음" in x for x in w.summary())


def test_a_split_ratio_guessed_from_share_counts_is_still_whole_only():
    """파이프라인이 주식 수로 짐작하는 배율(div_basis)은 예전처럼 깨끗한 배율만이에요 — 대한제강의 ×1.66 을 주식 수로는 짐작하지 않아요."""
    r = basis_of("084010")
    assert r["dpsF"][0] is None or V._factor_ok(r["dpsF"][0])
    assert all(f is None or V._factor_ok(f) for t in CASES for f in basis_of(t)["dpsF"])


def test_the_switch_off_and_no_nan():
    by, counts, _, _ = run(*RATIO7, prove=False)
    assert all("dyt" not in by[t] for t in RATIO7) and "proofSub" not in counts
    by, counts, _, _ = run(*CASES)
    json.dumps([by, counts], allow_nan=False)


# ── 3. 실제 종목: 답 11 · 13 의 표시 ─────────────────────────
def test_rights_payers_get_line_two_only_when_the_new_shares_are_listed():
    by, counts, why, _ = run("432320", "210980", "356860", "008830")
    assert {t: s.get("dvLine") for t, s in by.items()} == {"432320": 2, "210980": 2, "356860": 2, "008830": 2}
    assert counts["proofSub"]["rights"] == {"008830": "sh", "210980": "sh", "356860": "sh", "432320": "sh"}
    assert all("dyt" not in s and "dvProof" not in s for s in by.values())
    rc = CASES["432320"]["look"]["fxT"]
    k = next(iter(rc))
    by, counts, why, _ = run("432320", edit={"432320": lambda lk: lk["fxT"][k].update(q=0.3)})   # 새 주식이 아직 오늘 수에 없는 모양
    assert counts["proof"]["rightsT"] == ["432320"] and counts["proofSub"]["rights"] == {"432320": "shnew"} and "dvLine" not in by["432320"]
    assert any("새 주식이 아직 상장 전" in x for x in why.summary())


def test_an_unknown_rights_method_blocks_without_a_line():
    rc = CASES["020400"]["look"]["fx"][0]["rc"]
    by, counts, _, _ = run("020400", edit={"020400": lambda lk: lk["fxT"][rc].update(m="?")})
    assert counts["proofSub"]["rights"] == {"020400": "unk"} and "dvLine" not in by["020400"] and "dyt" not in by["020400"]


def test_data_payers_get_line_three_only_when_the_table_really_disagrees():
    """2026-11-15 원문 확인: 아세아제지 · 엘앤씨바이오 · 와이엔텍(주당 칸에 총액) · 인터로조(우선주 줄 없는 총액)는 배당 표가 회사의 주식 수와
    어긋나요 (줄 3). 하림지주(총액 없음) · 메디톡스(주식의 총수 현황에 우선주 수가 따로 없음) · 대신밸류리츠(그해 말 표를 읽지 못함)는 회사 공시에
    조각이 빠졌어요 (줄 4 — Jack 2026-11-19 '이유 없는 빈칸은 없게')."""
    ts = ("002310", "290650", "067900", "119610", "003380", "086900", "0030R0")
    by, counts, why, _ = run(*ts)
    assert {t: by[t].get("dvLine") for t in ts} == {"002310": 3, "290650": 3, "067900": 3, "119610": 3, "003380": 4, "086900": 4,
                                                    "0030R0": 4}
    assert counts["proofSub"]["data"] == {"002310": "div", "290650": "div", "067900": "div", "119610": "div", "003380": "nototal",
                                          "086900": "pref0", "0030R0": "nostk"}
    assert sorted(counts["proof"]["dataT"]) == sorted(ts) and all("dyt" not in by[t] for t in ts)
    assert by["290650"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"}                              # 맞춤 이유(#98) 그대로 · 줄은 dvLine 하나로
    lines = " ".join(why.summary())
    assert "배당 자료 줄(3) 4 · 빠진 자료 줄(4) 3 · rights · data 중 줄 없음 0" in lines


def test_an_unnamed_dividend_table_reason_gets_no_line_and_is_counted(monkeypatch):
    """리뷰 2026-11-19: prove_receiving 이 PROVE_DATA_WHY 에 없는 새 이유 글을 돌려주면 다른 경우(예전엔 nototal → 줄 4)로 짐작하지 않아요 —
    other 로 적고 줄 없음 · 로그에 '!!' 와 수. 이름이 있는 다른 종목의 줄은 그대로예요."""
    orig = F.prove_receiving

    def new_text(cash, d, pds, pfo=None):
        n, pd, why = orig(cash, d, pds, pfo)
        return (n, pd, "새로 생긴 배당 표 이유" if why == "현금배당금총액 없음" else why)
    monkeypatch.setattr(F, "prove_receiving", new_text)
    by, counts, why, _ = run("003380", "086900", "002310")
    assert "dvLine" not in by["003380"] and "dyt" not in by["003380"] and "dvProof" not in by["003380"]
    assert by["086900"]["dvLine"] == 4 and by["002310"]["dvLine"] == 3
    assert counts["proofSub"]["data"] == {"002310": "div", "003380": "other", "086900": "pref0"}
    assert sorted(counts["proof"]["dataT"]) == ["002310", "003380", "086900"]
    out = why.summary()
    loud = [x for x in out if x.startswith("  !! 배당 표의 이름 없는 이유")]
    assert len(loud) == 1 and "1곳" in loud[0] and "003380" in loud[0], out
    assert any("그대로 숨김(data) 003380" in x and "새로 생긴 배당 표 이유" in x and "줄 없음 (other" in x for x in out)
    assert "배당 자료 줄(3) 1 · 빠진 자료 줄(4) 1 · rights · data 중 줄 없음 1" in " ".join(out)
    monkeypatch.setattr(F, "prove_receiving", orig)
    _, _, why, _ = run("003380")
    assert not any("배당 표의 이름 없는 이유" in x for x in why.summary())                       # 이름이 있으면 그 줄은 없어요


def test_line_one_is_unchanged():
    by, counts, _, _ = run("049430", edit={"049430": lambda lk: lk.update(cx=[])})
    s = by["049430"]
    assert s["dvLine"] == 1 and counts["proof"]["lineT"] == ["049430"] and counts["proofSub"] == {"v": 1, "rights": {}, "data": {}}


def test_old_marks_never_survive_and_the_record_is_shaped():
    a = {"t": "123450", "cls": "kr", "dvLine": 3}
    F.apply_div_basis([a], {}, {}, why=None)
    assert "dvLine" not in a
    _, counts, _, _ = run("002310", "432320")
    assert set(counts["proofSub"]) == {"v", "rights", "data"} and counts["proofSub"]["v"] == 1


# ── 4. 관문: 답 12 의 세 조건 ────────────────────────────────
def with_exact(files):
    """좋은 픽스처의 배당 회사 하나를 대한제강처럼 (공시의 정확한 무상증자 ×1.6616554 로 되살린 종목 · 파이프라인과 같은 칸)."""
    files, s0 = with_proof(files)
    by, counts, _, _ = run("084010")
    dj = by["084010"]
    kr = [s for s in files["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    s = next(x for x in kr if x.get("divSt") == "same" and x["t"] not in V.MUST and x.get("dyt") and x is not s0)
    for k in ("fy", "shr", "price", "dps3", "dps3a", "dpsF", "divSt", "dyt", "dvWhy", "dvProof"):
        s[k] = copy.deepcopy(dj[k])
    for c in files["corp"]["companies"]:
        if c["t"] == s["t"]:
            c["cash3"] = comp_of("084010")["cash3"]
    mirror(files, s)
    recount(files)
    recount_why(files)
    files["data"]["divCheck"]["proof"] = {**PROOF0, "today": 1, "yearEnd": 1, "years": 2}
    files["data"]["divCheck"]["proofSub"] = {"v": 1, "rights": {}, "data": {}}
    return files, s


@pytest.fixture
def exact_pair():
    cur, prev, _ = good_pair()
    files, s = with_exact(cur)
    return files, prev, s


def test_an_exact_filed_bonus_ratio_passes_every_row(exact_pair):
    cur, prev, s = exact_pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert rows_of(rep)[DIV_ROW][3] == "PASS" and "공시의 정확한 무상증자 배율 1곳" in rows_of(rep)[DIV_ROW][1]
    assert V.exact_bonus_set(cur["data"], [x for x in cur["data"]["stocks"] if x.get("cls") == "kr"], cur["corp"]["companies"]) == {s["t"]}


def _drop_proof(cur, s):
    s.pop("dvProof")
    cur["data"]["divCheck"]["proof"] = {**PROOF0, "today": 1, "years": 1}


@pytest.mark.parametrize("change", [
    # 파이프라인이 주식 수로 짐작한 것 같은 배율 (사건 · 증명 없음)
    lambda cur, s: (_drop_proof(cur, s), s.pop("dvWhy"), mirror(cur, s), recount_why(cur)),
    # 증명(dvProof) 없음 (사건은 있어요)
    lambda cur, s: _drop_proof(cur, s),
    # 곱이 dpsF 와 1e-6 넘게 다름
    lambda cur, s: (s.update(dpsF=[1.66166] * 3, dps3a=[round(500 / 1.66166, 2)] * 3), mirror(cur, s)),
    # 무상증자가 아닌 사건 (원문의 분할 · x 없음)
    lambda cur, s: ([e.update(k="split") or e.pop("x") for e in s["dvWhy"]["ev"] + s["dvProof"]["ev"]], mirror(cur, s)),
    # r ≠ 1 + x
    lambda cur, s: ([e.update(x=0.66) for e in s["dvWhy"]["ev"] + s["dvProof"]["ev"]], mirror(cur, s)),
    # 앞 해의 깨끗하지 않은 배율을 이번 증명이 되살리지 않았음
    lambda cur, s: (s["dvProof"].update(yrs=[]), cur["data"]["divCheck"]["proof"].update(years=1)),
    # 증명의 숫자가 틀림 (dvProof 검사 실패 → 예외도 없어요)
    lambda cur, s: s["dvProof"].update(cmo=12_000_000),
])
def test_every_other_non_whole_factor_still_fails(exact_pair, change):
    """예외가 맞지 않으면 예전 규칙 그대로: 깨끗하지 않은 dpsF (배당 줄) · 깨끗하지 않은 사건 (dvWhy 모양 줄 · dvProof 줄) 이 모두 실패해요."""
    cur, prev, s = exact_pair
    change(cur, s)
    rep = check(cur, prev)
    failed = {r[0] for r in rep.failed}
    rows = (DIV_ROW,) + (WHY_ROWS[:1] if "dvWhy" in s else ()) + (ROWS[1:2] if "dvProof" in s else ())
    assert set(rows) <= failed, (rows, rep.table())
    assert any("깨끗하지 않은 배율" in r[1] for r in rep.failed if r[0] == DIV_ROW)
    assert s["t"] not in V.exact_bonus_set(cur["data"], [x for x in cur["data"]["stocks"] if x.get("cls") == "kr"], cur["corp"]["companies"])


def test_each_guard_names_its_own_reason():
    """세 조건을 하나씩 어기면 exact_bonus_problem 이 그 조건의 이유를 말해요 (다른 검사가 함께 잡더라도)."""
    by, _, _, _ = run("084010")
    s0, c = by["084010"], comp_of("084010")
    assert V.exact_bonus_problem(s0, c, PX) is None

    def bad(change):
        s = copy.deepcopy(s0)
        change(s)
        return V.exact_bonus_problem(s, c, PX) or ""
    assert "무상증자(r = 1 + x)가 아니에요" in bad(lambda s: [e.update(k="split") or e.pop("x") for e in s["dvWhy"]["ev"] + s["dvProof"]["ev"]])  # (가)
    assert "무상증자(r = 1 + x)가 아니에요" in bad(lambda s: [e.update(x=0.66) for e in s["dvWhy"]["ev"] + s["dvProof"]["ev"]])
    assert "사건의 곱" in bad(lambda s: s.update(dpsF=[1.66166] * 3, dps3a=[round(500 / 1.66166, 2)] * 3))                       # (나)
    assert "2023년 사건의 곱" in bad(lambda s: s.update(dpsF=[1.661655, 1.661655, 1.66166], dps3a=[300.9, 300.9, round(500 / 1.66166, 2)]))
    assert "이번 증명이 되살리지 않았어요" in bad(lambda s: s["dvProof"].update(yrs=[1]))                                          # (다)
    assert "이번 증명이 되살리지 않았어요" in bad(lambda s: s["dvProof"].update(y0=None))
    assert bad(lambda s: s["dvProof"].update(cmo=12_000_000)).startswith("dvProof:")
    assert bad(lambda s: s["dvWhy"]["ev"][0].update(rc="123")) == "dvWhy: 접수번호 123"                                   # (다) dvWhy 검사
    assert bad(lambda s: s["dvWhy"]["ev"][0].update(src="fric")) == "dvWhy: 사건 칸 ['d', 'k', 'r', 'rc', 'src', 'x']"      # 발행 칸 모양
    assert bad(lambda s: s.pop("dvProof")) == "dvProof 없음" and bad(lambda s: s.pop("dvWhy")) == "dvWhy ok (사건) 없음"
    assert V.exact_bonus_problem({"dpsF": [2.0, 1.0, 1.0]}, {}, PX) == "깨끗한 배율뿐 (필요 없음)"


def test_a_guessed_non_whole_factor_fails_exactly_as_before():
    """예외가 맞지 않는 종목은 예전 글 그대로 실패해요 (div_row_problem · _dvwhy_events)."""
    s = {"dps3": [500.0, 500.0, 500.0], "dps3a": [384.62, 384.62, 384.62], "dpsF": [1.3, 1.3, 1.3], "divSt": "adj"}
    assert V.div_row_problem(s) == "깨끗하지 않은 배율 1.3" == V.div_row_problem(s, exact=False)
    assert V.div_row_problem(s, exact=True) is None
    ev = [{"k": "bonus", "d": "2026-03-02", "r": 1.3, "x": 0.3, "rc": "20260202000123"}]
    assert V._dvwhy_events(ev, TODAY) == "깨끗하지 않은 배율 1.3" and V._dvwhy_events(ev, TODAY, exact=True) is None
    assert V._dvwhy_events([{"k": "split", "d": "2026-03-02", "r": 1.3, "rc": "20260202000123"}], TODAY, exact=True) == "깨끗하지 않은 배율 1.3"
    assert V.exact_bonus_problem({**s, "fy": 2025}, {}, PX) == "dvProof 없음"


# ── 5. 관문: 답 11 · 13 의 표시와 기록 ─────────────────────────
def with_lines(files):
    """숨긴 배당 회사 셋: data 어긋남(줄 3) · data 총액 없음(줄 4) · rights 주주배정(줄 2) — 파이프라인처럼 기록과 표시를 함께."""
    files, s = with_proof(files)
    kr = [x for x in files["data"]["stocks"] if x.get("cls") == "kr" and not x.get("fund") and x.get("divSt") == "nd"]
    a, b, c = kr[:3]
    for x in (a, b, c):
        x["dpsF"] = [None] * 3
        x["dps3a"] = [None if (d or 0) > 0 else d for d in x["dps3"]]
        mirror(files, x)
    a["dvLine"], b["dvLine"], c["dvLine"] = 3, 4, 2
    proof = files["data"]["divCheck"]["proof"]
    recount(files)
    recount_why(files)
    proof.update(data=2, dataT=sorted([a["t"], b["t"]]), rights=1, rightsT=[c["t"]])
    files["data"]["divCheck"]["proof"] = proof
    files["data"]["divCheck"]["proofSub"] = {"v": 1, "rights": {c["t"]: "sh"}, "data": {a["t"]: "div", b["t"]: "nototal"}}
    return files, (a, b, c)


@pytest.fixture
def line_pair():
    cur, prev, _ = good_pair()
    files, abc = with_lines(cur)
    return files, prev, abc


def test_marks_that_match_the_record_pass(line_pair):
    cur, prev, (a, b, c) = line_pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert rows_of(rep)[SUB_ROW][3] == "PASS" and "유상증자 줄 1 · 배당 자료 줄 1 · 빠진 자료 줄 1 · 줄 없음 0" in rows_of(rep)[SUB_ROW][1]
    items = [i for _, xs in rep.details for i in xs]
    assert any(b["t"] in i and "(총액 없음 · 줄)" in i for i in items) and any(a["t"] in i and "주식 수와 다름 · 줄)" in i for i in items)


@pytest.mark.parametrize("change", [
    lambda d, a, b, c: b.update(dvLine=3),                                                        # 총액 없음에 어긋남의 줄
    lambda d, a, b, c: b.pop("dvLine"),                                                           # 총액 없음인데 줄 4 표시 없음 (Jack 2026-11-19)
    lambda d, a, b, c: a.update(dvLine=4),                                                        # 어긋남에 빠진 자료의 줄
    lambda d, a, b, c: (d["divCheck"]["proofSub"]["data"].update({b["t"]: "neg"})),                # 줄 없는 경우인데 줄 4 표시
    lambda d, a, b, c: a.pop("dvLine"),                                                           # 어긋남인데 표시 없음
    lambda d, a, b, c: a.update(dvLine=2),                                                        # 다른 줄
    lambda d, a, b, c: c.update(dvLine=3),
    lambda d, a, b, c: d["divCheck"]["proofSub"]["data"].update({a["t"]: "nototal"}),             # 기록과 표시가 다름
    lambda d, a, b, c: d["divCheck"]["proofSub"]["data"].update({b["t"]: "other"}),               # 이름 없는 이유인데 줄 4 표시 (리뷰 2026-11-19)
    lambda d, a, b, c: d["divCheck"]["proofSub"]["data"].pop(b["t"]),                             # 기록의 종목 ≠ dataT
    lambda d, a, b, c: d["divCheck"]["proofSub"]["rights"].update({c["t"]: "maybe"}),             # 모르는 경우
    lambda d, a, b, c: d["divCheck"]["proofSub"].update(v=2),
    lambda d, a, b, c: d["divCheck"]["proofSub"].update(extra={}),
])
def test_marks_that_disagree_with_the_record_fail(line_pair, change):
    cur, prev, (a, b, c) = line_pair
    change(cur["data"], a, b, c)
    rep = check(cur, prev)
    assert SUB_ROW in {r[0] for r in rep.failed}, rep.table()


def test_an_unnamed_reason_without_a_line_only_warns(line_pair):
    """리뷰 2026-11-19: 이름을 붙이지 않은 배당 표 이유(other)는 줄 없이 발행하되 관문이 경고해요 (이유를 말하지 않는 빈칸이 있다고)."""
    cur, prev, (a, b, c) = line_pair
    cur["data"]["divCheck"]["proofSub"]["data"][b["t"]] = "other"
    b.pop("dvLine")
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    row = rows_of(rep)[SUB_ROW]
    assert row[3] == "WARN" and f"이름 없는 배당 표 이유 1곳 (줄 없음): {b['t']}" in row[1], row
    assert "유상증자 줄 1 · 배당 자료 줄 1 · 줄 없음 1" in row[1]
    items = [i for _, xs in rep.details for i in xs]
    assert any(b["t"] in i and "(이름을 붙이지 않은 배당 표 이유 · 줄 없음)" in i for i in items)


@pytest.mark.parametrize("change", [
    lambda d, a, b, c: a.update(dvLine=5),                                                        # 모르는 줄 값
    lambda d, a, b, c: a.update(dvLine=True),
    lambda d, a, b, c: (a.update(dyt=1.0)),                                                       # 수익률이 보이는 종목에 줄
    lambda d, a, b, c: d["divCheck"].pop("proofSub"),                                             # 기록 없이 줄 2 · 3
])
def test_a_mark_without_its_record_or_on_a_yield_fails(line_pair, change):
    cur, prev, (a, b, c) = line_pair
    change(cur["data"], a, b, c)
    rep = check(cur, prev)
    assert ROWS[0] in {r[0] for r in rep.failed}, rep.table()


def test_data_before_v191j_is_only_a_warning_until_published(line_pair):
    cur, prev, (a, b, c) = line_pair
    cur["data"]["divCheck"].pop("proofSub")
    a.pop("dvLine"), b.pop("dvLine"), c.pop("dvLine")
    rep = check(cur, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN", rep.table()
    had = {"data": copy.deepcopy(cur["data"])}
    had["data"]["divCheck"]["proofSub"] = {"v": 1, "rights": {}, "data": {}}
    rep = check(cur, had)
    assert SUB_ROW in {r[0] for r in rep.failed}                                                  # 한 번 발행된 뒤 빠지면 실패


# ── 6. 문구 ─────────────────────────────────────────────────
def test_the_two_lines_are_recorded_once_and_built_once():
    from copytrace import chat_approved
    ap = chat_approved()
    assert ap["co.div.rightsHidden"] == RIGHTS_LINE and ap["co.div.dataHidden"] == DATA_LINE
    src = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as f:
        app = f.read()
    with open(os.path.join(ROOT, "baepsae.html"), encoding="utf-8") as f:
        old = f.read()
    for line in (RIGHTS_LINE, DATA_LINE):
        assert src.count(line) == 1 and app.count(line) == 1 and old.count(line) == 0               # 예전 뱁새에는 없어요 (dy 그대로)


def test_the_missing_data_line_is_recorded_once_and_built_once():
    """Jack 2026-11-19: '이유 없는 빈칸은 없게' — 회사 공시에 조각이 빠진 배당 회사(하림지주 · 한신기계 · HDC · 토니모리 · 펌텍코리아 ·
    대신밸류리츠 · 메디톡스)의 줄."""
    from copytrace import chat_approved
    assert chat_approved()["co.div.missingHidden"] == MISSING_LINE
    src = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as f:
        app = f.read()
    with open(os.path.join(ROOT, "baepsae.html"), encoding="utf-8") as f:
        old = f.read()
    assert src.count(MISSING_LINE) == 1 and app.count(MISSING_LINE) == 1 and old.count(MISSING_LINE) == 0


def test_every_hidden_data_payer_on_the_real_data_has_a_line():
    """11-14 의 data 22곳 중 우리 fixture 에 있는 7곳: 모두 줄이 있어요 (3 어긋남 · 4 빠진 자료) — 빈칸에 이유가 없는 data 종목은 없어요."""
    ts = ("002310", "290650", "067900", "119610", "003380", "086900", "0030R0")
    by, counts, _, _ = run(*ts)
    assert all(by[t].get("dvLine") in (3, 4) for t in ts)
    assert {t: v for t, v in counts["proofSub"]["data"].items() if F.prove_line("data", v) == 4} == {"003380": "nototal", "086900": "pref0",
                                                                                                      "0030R0": "nostk"}
