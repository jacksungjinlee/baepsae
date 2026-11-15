# -*- coding: utf-8 -*-
"""v19.1i 배당 기준 증명 (Jack, 2026-11-14 item 5: '주식 수가 바뀐 뒤 배당수익률이 없는 72곳 — 계산을 고쳐요') — 데이터 · 관문 (네트워크 없음).

div_basis 가 오늘 주식 수 기준을 찾지 못한 해(nc · nd)를 DART 결정 공시(분할 · 병합 · 무상증자)와 주식 수로 증명할 수 있을 때만 되살려요
(fetch_data.DivWhy.prove). 관문(validate_data.check_v191i)은 그 근거를 발행된 숫자로 다시 맞춰 봐요: 되살린 수익률 = 배당 총액 ÷ 시가총액
(자기주식 · 공시된 새 주식만큼만 달라요).

픽스처 tests/fixtures/dvproof/cases.json 은 2026-11-14 에 OpenDART 에서 받은 실제 응답을 파이프라인의 해석 함수로 읽은 값이에요
(배당 표 alotMatter · 재무상태표 자본금 · 주식의 총수 현황 · 결정 공시 목록과 결정 · 원문 · 유상증자/사채 주식 수와 유상증자 방식 —
키는 들어 있지 않아요).
종목 값은 2026-11-14 23:08 발행본 (pxDate 2026-11-13)."""
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
from test_v191h_div_why import with_why, recount_why, mirror  # noqa: E402
from fixture_data import good_pair  # noqa: E402

with open(os.path.join(ROOT, "tests", "fixtures", "dvproof", "cases.json"), encoding="utf-8") as _f:
    FX = json.load(_f)
CASES = FX["cases"]
PX = dt.date.fromisoformat(FX["px"])
TODAY = dt.date.fromisoformat(FX["today"])
LINE = "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요."


class Client:
    """DartClient 모양의 가짜 (네트워크 없음): 결정 공시 조회는 캐시 항목(실제 응답을 읽은 결과)으로 · 주식의 총수 현황은 실제 표로
    (DartClient.report 처럼 답을 캐시에 남겨요 — 그 보고서가 없으면 013). get · get_zip 은 net 에 준 응답만, 아니면 실패해요
    (캐시를 다시 받지 않는다는 것도 함께 봐요). old — 증명용 모양 표시(pv) 없는 예전 항목 · edit — 종목마다 조회 결과를 고쳐요 ·
    stk_fail — 주식의 총수 현황을 받지 못하는 종목."""

    def __init__(self, ts, old=False, net=None, edit=None, stk_fail=()):
        self.entries = {}
        self.meta = {"corpMap": {t: CASES[t]["corp"] for t in ts}}
        self.today, self.mode = TODAY, "cache"
        self.status, self.lock = collections.Counter(), threading.Lock()
        self.revalidate_left, self.revalidated, self.down, self.fatal = 300, 0, None, None
        self.started_empty = False
        self.calls, self.net = [], net or {}
        self.t_of = {CASES[t]["corp"]: t for t in ts}
        self.old, self.edit, self.stk_fail = old, edit or {}, set(stk_fail)

    def seed(self, t, f_key):
        c = CASES[t]
        look = copy.deepcopy(c["look"])
        if self.old:
            look.pop("pv", None)
        if t in self.edit:
            self.edit[t](look)
        self.entries[f"{c['corp']}|{F.DVWHY_TAG}"] = {"st": "000", "at": TODAY.isoformat(),
                                                      "d": {"fy": c["s"]["fy"], "F": f_key, "end": TODAY.isoformat(), **look}}

    def get(self, endpoint, params, timeout=25):
        self.calls.append(endpoint)
        got = self.net.get(endpoint)
        if got is None:
            self.status["예외"] += 1
            return None
        self.status["000"] += 1
        return copy.deepcopy(got)

    def get_zip(self, endpoint, params, timeout=40):
        self.calls.append(endpoint)
        self.status["예외"] += 1
        return None

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        self.calls.append(endpoint)
        t = self.t_of[corp]
        c = CASES[t]
        if endpoint != "stockTotqySttus.json" or t in self.stk_fail:
            return None                                                     # 답을 받지 못함 — 캐시에 아무것도 남지 않아요
        got = copy.deepcopy(c["stk"]) if year == c["s"]["fy"] else None
        self.entries[f"{corp}|{year}|{reprt}|{tag}"] = {"st": "000" if got else "013", "at": TODAY.isoformat(), "d": got}
        return got


def stock_of(t):
    c = CASES[t]
    s = dict(copy.deepcopy(c["s"]), cls="kr")
    s["_bas"] = copy.deepcopy(c["bas"])
    if c["cap"]:
        s["_cap"] = copy.deepcopy(c["cap"])
    if c["bas"] and F.unlisted_paid(c["bas"], len(c["pref"])):
        s["_stk"] = copy.deepcopy(c["stk"])
    return s


def basis_of(t):
    """파이프라인과 같은 입력으로 div_basis (증명 전 결과)."""
    c = CASES[t]
    cap = c["cap"] or {}
    stk = c["stk"] if c["bas"] and F.unlisted_paid(c["bas"], len(c["pref"])) else None
    return F.div_basis(c["s"]["dps3"], c["bas"], cap.get("cs3"), c["s"]["shr"], c["pref"], cap.get("ss3"), cap_k=cap.get("k", "all"),
                       cap_src=cap.get("src"), stk=stk)


def run(*ts, client=None, prove=None, **kw):
    """apply_div_basis 를 그대로 (check 다음 prove) → (종목들 {코드: s}, 집계, DivWhy, client)."""
    cl = client or Client(ts, **kw)
    for t in ts:
        cl.seed(t, [F._fin(x) for x in basis_of(t)["dpsF"]])
    why = F.DivWhy(cl, PX, prove=prove)
    stocks = [stock_of(t) for t in ts]
    pref = {t[:5]: CASES[t]["pref"] for t in ts if CASES[t]["pref"]}
    counts, extra = F.apply_div_basis(stocks, {}, pref, why=why)
    return {s["t"]: s for s in stocks}, counts, why, cl


def dyt_of(s):
    return round(s["dps3a"][0] / s["price"] * 100, 2)


def as_on_main(s, t):
    """증명 단계를 끈 것과 같은 결과인지 (되살리지 않은 종목은 '그대로')."""
    off, _, _, _ = run(t, prove=False)
    o = off[t]
    return all(s.get(k) == o.get(k) for k in ("dps3a", "dpsF", "divSt", "dyt", "dvWhy")) and "dvProof" not in s


# ── 1. 순수 함수 ─────────────────────────────────────────────
def test_receiving_shares_take_preferred_dividends_out_only_when_they_can_be_counted():
    assert F.prove_receiving(1_000_000_000, 100, []) == (10_000_000, None, None)
    n, pd, why = F.prove_receiving(98_677_000_000, 1100, [1150.0, 1150.0], 19_603_474)      # 한화 2025: 두 우선주 같은 배당
    assert why is None and pd == 1150.0 and abs(n - 69_211_823) < 1
    assert F.prove_receiving(1e9, 100, [120.0, 130.0], 1e6)[0] is None                                   # 종류마다 다른 배당 — 셀 수 없어요
    assert F.prove_receiving(1e9, 100, [120.0, 0.0], 1e6)[0] is None                                     # 0 인 종류가 섞이면 (유통 주식 수에 섞여요)
    assert F.prove_receiving(1e9, 100, [120.0], None)[0] is None                                         # 우선주 주식 수를 모르면
    assert F.prove_receiving(1e9, 100, [120.0], 0)[0] is None                                            # 우선주가 없는데 다른 금액의 배당 줄 (메디톡스)
    assert F.prove_receiving(1e9, 100, [100.0], 0) == (10_000_000, None, None)                            # 우선주가 없고 같은 금액 — 표의 중복 (실리콘투)
    assert F.prove_receiving(0, 100, [])[0] is None and F.prove_receiving(None, 100, [])[0] is None      # 총액이 없으면 (하림지주)


def test_today_and_year_end_checks():
    assert F.prove_today(9_311_733, 1.0, 9_324_548) and F.prove_today(31_100_000, 5.0, 155_507_715)
    assert not F.prove_today(31_100_000, 4.0, 155_507_715) and not F.prove_today(8_984_286, 1.0, 7_988_324)
    stk = {"cmo": 29_066_815, "cmi": 34_600_884, "pfo": 0}                                               # 웹젠 2025 말
    assert F.prove_year_end(29_065_714, 1.0, 30_966_575, stk) == (True, None)                            # 자기주식 소각만큼 줄었어요
    assert F.prove_year_end(29_065_714, 2.0, 30_966_575, stk) == (False, "down")                         # 배율이 틀리면 오늘이 모자라요
    assert F.prove_year_end(29_065_714, 0.5, 30_966_575, stk) == (False, "up")
    assert F.prove_year_end(48_115_000, 1.0, 39_449_510, {"cmo": 38_417_425, "cmi": 40_482_510}) == (False, "div")   # 아세아제지: 중간배당
    assert F.prove_year_end(1, 1.0, 1, None) == (False, "nostk")
    d = {"cmo": 3_189_166, "cmi": 3_189_166}                                                             # 대동금속: 무상증자 ×2 뒤 유상증자
    assert F.prove_year_end(3_183_333, 2.0, 9_073_532, d) == (False, "up")
    assert F.prove_year_end(3_183_333, 2.0, 9_073_532, d, cover=3_000_000) == (True, None)                # 덮는 수는 오늘 주식 수로


def test_new_shares_count_only_the_events_after_their_own_decision():
    """리뷰 2026-11-15: 유상증자 · 사채가 만드는 주식은 그 공시일 뒤의 분할 · 병합 · 무상증자만큼만 늘려요."""
    lk = CASES["020400"]["look"]                                                                         # 대동금속: 무상증자 ×2 (4월) 뒤 제3자배정 (8월)
    ev = [e for e in lk["ev"] if e["d"] > "2025-12-31"]
    cover, used = F.prove_cover(lk["fx"], 2025, PX, ev)
    assert cover == 3_000_000 and [x["rc"] for x in used] == ["20260812000426"]                         # 그 뒤 사건이 없어 그대로
    assert 3_189_166 * 2 + cover == 9_378_332                                                           # 한도 약 938만 주 (× 1.03)
    assert F.prove_year_end(3_183_333, 2.0, 9_073_532, {"cmo": 3_189_166, "cmi": 3_189_166}, cover) == (True, None)
    lt = CASES["356860"]["look"]                                                                         # 티엘비: 유무상증자 — 유상 몫(7월 2일) 뒤 무상증자 ×2 (7월 20일)
    fx = [{"k": o["k"], "d": o["d"], "n": o["n"], "rc": o["rc"]} for o in lt["oth"] if o.get("k") == "rights" and o.get("n")]
    cover, _ = F.prove_cover(fx, 2025, PX, [e for e in lt["ev"] if e["d"] > "2025-12-31"])
    assert cover == 2_073_000 * 2
    assert F.prove_year_end(9_722_222, 2.0, 23_701_260, CASES["356860"]["stk"], cover) == (True, None)     # 주식 수는 맞아요 (되살리지 않는 이유는 아래 rights)
    assert F.prove_year_end(9_722_222, 2.0, 23_701_260, CASES["356860"]["stk"], 2_073_000) == (False, "up")   # 그 뒤 ×2 를 빼면 모자라요


def test_rights_terms_read_the_method_and_the_size():
    rows = [{"rcept_no": "20260702000142", "piic_ic_mthn": "주주배정후 실권주 일반공모", "piic_nstk_ostk_cnt": "2,073,000",
             "piic_bfic_tisstk_ostk": "9,832,630"}]
    assert F.parse_rights_terms(rows, pre="piic_") == {"20260702000142": {"m": "sh", "q": round(2_073_000 / 9_832_630, 6)}}
    one = lambda m, n="1,000", b="10,000": F.parse_rights_terms([{"rcept_no": "20260101000001", "ic_mthn": m, "nstk_ostk_cnt": n,  # noqa: E731
                                                                   "bfic_tisstk_ostk": b}])["20260101000001"]
    assert one("주주배정증자") == {"m": "sh", "q": 0.1} and one("제3자배정증자")["m"] == "tp" and one("일반공모증자")["m"] == "pub"
    assert one("-")["m"] == "?" and one("주주배정증자", n="-")["q"] is None
    assert F.parse_rights_terms([{"rcept_no": "x", "ic_mthn": "주주배정증자"}]) == {}                      # 접수번호가 이상하면 빼요
    w = F.DivWhy(None, PX)
    x = {"k": "rights", "d": "2026-03-01", "n": 1, "rc": "20260301000002"}
    assert w._rights_bad({"rt": {}, "fxT": {}}, [x]) == ["방식을 모르는 유상증자(2026-03-01 · 크기 모름)"]   # 방식을 모르면 막아요
    assert w._rights_bad({"fxT": {x["rc"]: {"m": "sh", "q": 0.1}}}, [x]) == []                             # 10% 는 그대로
    assert w._rights_bad({"fxT": {x["rc"]: {"m": "tp", "q": 2.0}}}, [x]) == []                             # 제3자배정은 막지 않아요


def test_window_names_events_and_blocks_spin_offs_and_stock_dividends():
    look = {"ev": [{"k": "split", "d": "2026-04-14", "r": 5.0, "rc": "20260301000001"},
                   {"k": "bonus", "d": "2025-04-29", "r": 1.1, "x": 0.1, "rc": "20250401000001"}],
            "oth": [{"k": "spin", "d": "2025-08-01", "rc": "20250801000001"}, {"k": "rights", "d": "2026-03-01", "rc": "20260301000002"}],
            "sd": [{"d": "2024-12-18", "rc": "20241218000001"}]}
    ev, blk = F.prove_window(look, "2025-12-31", "2026-11-13")
    assert [e["k"] for e in ev] == ["split"] and blk == ["spin"]                                         # 반년 앞의 분할 결정은 막아요
    ev, blk = F.prove_window(look, "2024-12-31", "2025-12-31")
    assert ev == [] and blk == ["spin", "stockdiv"]                                                     # 10% 이하 무상증자는 이름 붙이지 않아요
    assert F.prove_window({**look, "oth": [], "sd": []}, "2025-12-31", "2026-11-13")[1] == []


def test_the_filings_list_keeps_stock_dividends_and_cancellations_apart():
    rows = [{"report_nm": "주식소각결정              ", "rcept_no": "20261006900432", "rcept_dt": "20261006", "rm": "유"},    # 코메론
            {"report_nm": "주식소각결정(종속회사의주요경영사항)", "rcept_no": "20261007900001", "rcept_dt": "20261007", "rm": ""},
            {"report_nm": "[기재정정]주식배당결정", "rcept_no": "20251216900851", "rcept_dt": "20251216", "rm": "유"}]
    fl = F.dvwhy_filings(rows)
    assert fl["cx"] == [{"d": "2026-10-06", "rc": "20261006900432"}] and fl["sd"] == [{"d": "2025-12-16", "rc": "20251216900851"}]
    assert fl["oth"] == [] and fl["docs"] == [] and fl["wd"] == []


def test_earlier_years_need_matching_receiving_shares_and_no_restated_doubt():
    look = {"ev": [{"k": "bonus", "d": "2025-03-01", "r": 2.0, "x": 1.0, "rc": "20250201000001"}], "oth": [], "sd": []}
    d3, c3 = [1700.0, 1700.0, 1600.0], [405.19e8, 204.43e8, 210.39e8]                                  # SNT모티브: 2025 무상증자 ×2 (고쳐 적지 않음)
    assert F.prove_earlier(d3, c3, [], 1.0, look, 2025, 1) == (2.0, None)
    assert F.prove_earlier(d3, [405.19e8, 405.19e8, 210.39e8], [], 1.0, look, 2025, 1) == (None, "drift")   # 새 기준으로 고쳐 적은 해 — 하지 않아요
    assert F.prove_earlier(d3, c3, [], 1.0, {**look, "ev": []}, 2025, 1) == (None, "drift")              # 공시 없이 주식 수가 두 배
    assert F.prove_earlier(d3, c3, [[0.0, 10.0, 0.0]], 1.0, look, 2025, 1) == (None, "pref")
    assert F.prove_earlier(d3, [405.19e8, None, 1.0], [], 1.0, look, 2025, 1) == (None, "div")
    nonclean = {**look, "ev": [{"k": "bonus", "d": "2025-03-01", "r": 1.3, "x": 0.3, "rc": "20250201000001"}]}
    assert F.prove_earlier(d3, c3, [], 1.0, nonclean, 2025, 1) == (None, "nonclean")
    assert F.prove_earlier([3950.0, 3150.0, 2500.0], [1770.79e8, 1410.41e8, 1000e8], [], 1.0, {"ev": [], "oth": [], "sd": []},
                           2025, 2) == (1.0, None)                                                     # HD현대마린솔루션 2023 (상장 때 늘어난 12%)


# ── 2. 실제 종목 (원인별) ─────────────────────────────────────
def test_total_over_todays_shares_restores_the_yield():
    by, counts, why, _ = run("298040", "001230", "241560", "257720")
    hy, dk, bob, sil = by["298040"], by["001230"], by["241560"], by["257720"]
    assert hy["dpsF"] == [1.0, 1.0, 1.0] and hy["divSt"] == "same" and hy["dyt"] == dyt_of(hy) == 0.42   # 효성중공업: 액면가 7,500원 오기로 막혔어요
    assert hy["dvProof"]["y0"] == "today" and hy["dvProof"]["yrs"] == [1, 2] and "dvWhy" not in hy
    assert dk["dpsF"] == [5.0, 5.0, 5.0] and dk["dps3a"] == [20.0, 100.0, 120.0] and dk["divSt"] == "adj"   # 동국홀딩스: 액면분할 ×5
    assert dk["dyt"] == 1.15 and dk["dvWhy"]["st"] == "ok" and [(e["k"], e["r"]) for e in dk["dvWhy"]["ev"]] == [("split", 5.0)]
    assert bob["dpsF"] == [1.0, 1.0, 1.0] and bob["dyt"] == 3.21                                        # 두산밥캣: 달러 재무제표의 자본금
    assert sil["dvProof"]["y0"] == "today" and sil["dyt"] == round(306 / 24000 * 100, 2)               # 실리콘투: 우선주가 없는 표의 중복 줄
    assert counts["proof"]["today"] == 4 and counts["proof"]["years"] == 3 and counts["why"]["ok"] == 1


def test_year_end_shares_with_cancelled_treasury_third_party_issues_and_preferred_dividends():
    by, counts, why, cl = run("069080", "020400", "001750", "403550", "036630")
    wj, dd, hy, sc, sj = by["069080"], by["020400"], by["001750"], by["403550"], by["036630"]
    assert wj["dvProof"]["y0"] == "yearEnd" and wj["dvProof"]["cv"] == 0 and wj["dyt"] == round(700 / 12020 * 100, 2)
    # 대동금속: 예전 맞춤(×3)이 공시와 달라 숨겼던 종목 — 공시의 무상증자 ×2 로 되살리고, 그 뒤 제3자배정 유상증자는 Jack 의 답 2 대로 공시된 배당 그대로
    assert dd["dpsF"] == [2.0, 2.0, 2.0] and dd["dps3a"][0] == 30.0 and dd["divSt"] == "adj" and dd["dyt"] == 0.99
    assert dd["dvWhy"]["st"] == "ok" and [(e["k"], e["r"]) for e in dd["dvWhy"]["ev"]] == [("bonus", 2.0)]
    assert dd["dvProof"]["y0"] == "yearEnd" and dd["dvProof"]["cv"] == 3_000_000 and dd["dvProof"]["fx"][0]["rc"] == "20260812000426"
    assert hy["dvProof"]["pf"] == 472_870 and hy["dvProof"]["pd"] == 1650.0 and hy["dvProof"]["yrs"] == []     # 한양증권: 우선주 몫 · 제3자배정
    assert sc["dvProof"]["y0"] == "yearEnd" and sj["dvProof"]["y0"] == "yearEnd"                          # 쏘카 · 세종텔레콤: 제3자배정
    assert counts["why"]["nc-mismatch"] == 0 and counts["why"]["ok"] == 1 and counts["proof"]["yearEnd"] == 5
    assert not [c for c in cl.calls if c != "stockTotqySttus.json"]                                     # 보관본만 썼어요 (공시 다시 받기 없음)


def test_a_large_shareholder_rights_issue_keeps_the_stock_as_it_is():
    """리뷰 2026-11-15: 그 수를 덮는 유상증자가 주주배정(실권주 일반공모 포함)이고 10% 넘게 크면 권리락으로 오늘 주가는 새 기준인데 공시된 1주
    배당은 옛 기준이에요 — 되살리지 않고, 줄도 없이 그대로 (이유 rights). 티엘비는 유무상증자의 유상 몫(21%)이에요."""
    by, counts, why, _ = run("432320", "210980", "356860")
    for t in ("432320", "210980", "356860"):
        assert as_on_main(by[t], t), t
    assert "dyt" not in by["432320"] and "dvWhy" not in by["432320"] and by["356860"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"}
    assert counts["proof"]["rightsT"] == ["210980", "356860", "432320"] and counts["proof"]["yearEnd"] == 0
    lines = " ".join(why.summary())
    assert "210980 SK디앤디" in lines and "주주배정 유상증자(2026-10-07 · 증자 전의 240%)" in lines and "그대로 숨김(rights)" in lines


def test_a_shareholder_rights_issue_between_two_years_keeps_the_older_bar():
    by, counts, why, _ = run("003670", "064400")
    pf, lg = by["003670"], by["064400"]                                                                  # 포스코퓨처엠 2025 주주배정 15% · LG씨엔에스 상장 공모 11%
    assert pf["dpsF"][2] is None and pf["divSt"] == "nc" and why.n["pYear:rights"] == 1
    assert lg["dpsF"] == [1.0, 1.0, 1.0] and lg["divSt"] == "same"                                      # 일반공모는 막지 않아요


def test_a_bonus_ratio_that_is_not_a_split_ratio_is_restored_from_the_filing():
    """1.66 · 1.3 같은 무상증자 배율은 공시로 맞아요 — v19.1j (Jack 의 yes 2026-11-15 답 12): 무상증자 결정 API 의 정확한 배율(r = 1 + x)이고
    주식 수가 확인해 주면 되살려요 (예전 v19.1i 에서는 관문이 받는 배율이 아니라 그대로 · ratio 였어요). Jack 의 줄은 여전히 없어요."""
    by, counts, why, _ = run("084010", "196170")
    dj, alt = by["084010"], by["196170"]
    assert dj["dpsF"] == [1.661655] * 3 and dj["dyt"] == 3.73 and dj["dvProof"]["y0"] == "yearEnd" and dj["dvWhy"]["st"] == "ok"
    assert alt["dpsF"][0] == 1.3 and alt["dyt"] == 0.16 and alt["dvProof"]["y0"] == "today" and "dvLine" not in dj and "dvLine" not in alt
    assert counts["proof"]["ratioT"] == [] and counts["why"]["nc-mismatch"] == 0 and counts["why"]["nc-unexplained"] == 0


def test_spin_offs_stock_dividends_and_uncounted_filings_stay_as_they_are_without_a_line():
    by, counts, why, _ = run("000880", "045300", "049430", "005440")
    for t in ("000880", "045300", "049430", "005440"):
        assert as_on_main(by[t], t) and "dvWhy" not in by[t], t
    assert counts["proof"]["basisT"] == ["000880", "045300"] and counts["proof"]["uncountedT"] == ["005440", "049430"]
    assert counts["proof"]["line"] == 0 and counts["why"]["nc-unexplained"] == 0
    lines = " ".join(why.summary())
    assert "회사분할" in lines and "주식배당" in lines and "소각" in lines and "주식교환·이전" in lines


def test_jacks_line_only_where_no_filing_explains_the_change():
    """코메론에서 소각 결정을 지우면 (주식 수가 줄었는데 그 사이 공시가 하나도 없는 모양) — 그때만 nc-unexplained (Jack 의 줄)."""
    by, counts, why, _ = run("049430", edit={"049430": lambda lk: lk.update(cx=[])})
    s = by["049430"]
    assert s["dvWhy"] == {"v": 1, "st": "nc-unexplained"} and "dyt" not in s and s["dpsF"] == [None, None, None]
    assert counts["proof"]["lineT"] == ["049430"] and counts["why"]["nc-unexplained"] == 1
    assert any("공시가 하나도 없어요" in x and "Jack 의 줄" in x for x in why.summary())


def test_dividend_tables_that_disagree_with_their_share_counts_stay_as_they_are():
    by, counts, why, _ = run("002310", "003380", "086900", "290650")
    for t in ("002310", "003380", "086900", "290650"):
        assert as_on_main(by[t], t), t                                                                 # 이유를 모르니 줄도 없어요
    assert by["290650"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"}                                     # 엘앤씨바이오: 맞춤 이유(#98) 그대로
    assert counts["proof"]["dataT"] == ["002310", "003380", "086900", "290650"]
    assert any("그대로 숨김(data) 002310 아세아제지" in x for x in why.summary())


def test_earlier_years_restore_the_trend_only_when_proven():
    by, counts, why, _ = run("443060", "064960", "004800", "007340", "083550", "032960")
    assert by["443060"]["dpsF"] == [1.0, 1.0, 1.0] and by["443060"]["divSt"] == "same"               # 상장 때 늘어난 주식 (12%)
    snt = by["064960"]
    assert snt["dpsF"] == [1.0, 2.0, 2.0] and snt["dps3a"] == [1700.0, 850.0, 800.0] and snt["divSt"] == "adj"
    assert snt["dvWhy"]["st"] == "ok" and snt["dvProof"]["y0"] is None and snt["dvProof"]["yrs"] == [1, 2]
    assert by["004800"]["dpsF"][2] is None and by["004800"]["divSt"] == "nc"                         # 효성: 2024 회사분할
    assert by["007340"]["dpsF"][2] is None                                                             # DN오토모티브: 분할 + 합병 (주식 수가 맞지 않아요)
    assert by["083550"]["divSt"] == "nc" and "dvProof" not in by["083550"]                           # 케이엠: 주식배당이 해마다 있어요
    il = by["032960"]                                                                                   # 동일기연: 올해 ×5 (분할) · 앞 해는 주식배당이 있어 그대로
    assert il["dpsF"][0] == 5.0 and il["dvProof"]["y0"] == "yearEnd" and il["dvProof"]["yrs"] == [] and il["dpsF"][1:] == [None, None]
    assert why.n["pYear:block"] >= 2


def test_failed_reads_change_nothing():
    by, counts, why, _ = run("010130")                                                                  # 고려아연: 읽지 못한 공시 원문
    s = by["010130"]
    assert counts["proof"]["failT"] == ["010130"] and "dvProof" not in s and s["dpsF"][1:] == [None, None]
    assert s["dyt"] == dyt_of(s) and s["divSt"] == "nc" and "dvWhy" not in s                           # 올해 수익률은 예전처럼 · 앞 해는 그대로
    by, counts, why, _ = run("069080", stk_fail=["069080"])                                            # 주식의 총수 현황을 받지 못함 → 배당 표 문제가 아니라 조회 실패
    assert counts["proof"]["failT"] == ["069080"] and counts["proof"]["data"] == 0 and as_on_main(by["069080"], "069080")
    by, counts, why, _ = run("069080", edit={"069080": lambda lk: lk.update(nI=0)})                     # 거래소 수시공시 목록이 빔 → 결론 내지 않아요
    assert counts["proof"]["failT"] == ["069080"] and "dvProof" not in by["069080"]
    stocks = [stock_of("298040")]
    w = F.DivWhy(None, PX)
    counts, _ = F.apply_div_basis(stocks, {}, {}, why=w)
    assert counts["proof"]["failT"] == ["298040"] and "dyt" not in stocks[0] and "dvProof" not in stocks[0]


def test_a_missing_share_report_is_a_dividend_table_case_not_a_failure():
    cl = Client(["069080"])
    cl.report = lambda endpoint, corp, year, reprt, tag, parse, extra=None, redo=None: (
        cl.entries.__setitem__(f"{corp}|{year}|{reprt}|{tag}", {"st": "013", "at": TODAY.isoformat(), "d": None}))
    by, counts, why, _ = run("069080", client=cl)
    assert counts["proof"]["dataT"] == ["069080"] and counts["proof"]["fail"] == 0


def test_old_or_stale_cache_entries_are_fetched_again_and_the_limit_is_its_own():
    by, counts, why, cl = run("298040", old=True)                                                       # 증명용 모양 표시가 없는 예전 항목
    assert "list.json" in cl.calls and counts["proof"]["failT"] == ["298040"] and "dyt" not in by["298040"]
    assert why.prove_left == F.PROVE_PER_RUN - 1 and why.fetch_left == F.DVWHY_PER_RUN and why.n["pRefetch"] == 1
    moved = int(CASES["298040"]["s"]["shr"] * 0.965)                                                    # 받은 뒤 상장 주식 수가 3.5% 달라짐
    by, counts, why, cl = run("298040", edit={"298040": lambda lk: lk.update(shr=moved)})
    assert "list.json" in cl.calls and counts["proof"]["failT"] == ["298040"] and why.n["pRefetch"] == 1
    near = int(CASES["298040"]["s"]["shr"] * 0.98)                                                      # 2% 는 그대로 보관본
    by, counts, why, cl = run("298040", edit={"298040": lambda lk: lk.update(shr=near)})
    assert "list.json" not in cl.calls and by["298040"]["dvProof"]["y0"] == "today" and why.n["pCache"] == 1
    look, how = why._look(CASES["298040"]["corp"], 2025, [F._fin(x) for x in basis_of("298040")["dpsF"]])
    assert how == "cache"                                                                               # 맞춤 이유(check)는 주식 수와 상관없이 보관본
    lim = F.DivWhy(Client(["298040"], old=True), PX)
    lim.prove_left = 0
    assert lim._look(CASES["298040"]["corp"], 2025, [None, None, None], prove=True, shr=1)[0] is None and lim.n["pLimit"] == 1


def test_the_proof_stage_has_its_own_log_line():
    by, counts, why, cl = run("298040", "432320")
    lines = why.summary()
    one = next(x for x in lines if "배당 기준 증명 조회:" in x)
    assert "새로 받음 0곳" in one and "보관본 2곳" in one and "한도(150곳)에 닿아 못 함 0곳" in one and "DART 호출 0회" in one
    assert any("주주배정 유상증자(권리락) 1" in x for x in lines)


def _check_then(st, hide):
    """맞춤 이유(check)가 그 종목을 st 로 숨긴 것처럼 (앞 해 때문에 · #98) — 리뷰 2026-11-15 2차의 재현."""
    orig = F.DivWhy.check

    def check(self, s, r):
        r = orig(self, s, r)
        if s["t"] == "049430":
            r = F.dvwhy_apply(r, s.get("dps3"), {"fac": {}, "dem": {}, "hide": hide})
            s["dvWhy"] = {"v": 1, "st": st}
            self.t[st].append(s["t"])
        return r
    return check


def test_the_line_is_decided_in_one_place_even_after_a_mismatch(monkeypatch):
    """리뷰 2차 B (차단): 맞춤 이유가 nc-mismatch 로 숨겼는데 올해 바뀐 주식 수를 설명하는 공시가 하나도 없으면 — lineT 와 dvWhy nc-unexplained ·
    dvLine 이 늘 함께예요 (예전 코드는 lineT 에 넣고 nc-mismatch 를 남겨 관문이 매일 실패했어요)."""
    monkeypatch.setattr(F.DivWhy, "check", _check_then("nc-mismatch", "nc"))
    by, counts, why, _ = run("049430", edit={"049430": lambda lk: lk.update(cx=[])})
    s = by["049430"]
    assert counts["proof"]["lineT"] == ["049430"] and s["dvWhy"] == {"v": 1, "st": "nc-unexplained"} and s["dvLine"] == 1
    assert counts["why"]["nc-unexplained"] == 1 and counts["why"]["nc-mismatch"] == 0 and "dyt" not in s


def test_a_check_unexplained_on_a_spin_off_gets_no_line(monkeypatch):
    """리뷰 2차 C: 맞춤 이유(#98)는 유상증자 · 사채만 보고 nc-unexplained 라고 해요. 증명이 회사분할을 찾으면 그대로 두되 줄은 없어요 (dvLine 없음)."""
    monkeypatch.setattr(F.DivWhy, "check", _check_then("nc-unexplained", "nd"))
    spin = {"k": "spin", "d": "2026-05-01", "rc": "20260501000999"}
    by, counts, why, _ = run("049430", edit={"049430": lambda lk: lk.update(cx=[], oth=list(lk.get("oth") or []) + [spin])})
    s = by["049430"]
    assert counts["proof"]["basisT"] == ["049430"] and counts["proof"]["lineT"] == []
    assert s["dvWhy"] == {"v": 1, "st": "nc-unexplained"} and "dvLine" not in s and "dyt" not in s and "dvProof" not in s


def _with_rights(lk, rc, d, n, terms, fx=True):
    lk["oth"] = list(lk.get("oth") or []) + [{"k": "rights", "d": d, "rc": rc}]
    if fx:
        lk["fx"] = list(lk.get("fx") or []) + [{"k": "rights", "d": d, "n": n, "rc": rc}]
    lk["fxT"] = {**(lk.get("fxT") or {}), **terms}
    lk["fxBad"] = list(lk.get("fxBad") or [])


def test_the_rights_rule_covers_every_restore_path():
    """리뷰 2차 A · A2: 덮는 수가 필요 없는 길(자기주식 소각과 겹친 주주배정)도, 방식을 읽지 못한 결정이 사채에 덮이는 길도 되살리지 않아요."""
    rc = "20260302000111"
    shr0 = CASES["069080"]["s"]["shr"]
    new = 4_500_000

    def a(lk):
        _with_rights(lk, rc, "2026-03-02", new, {rc: {"m": "sh", "q": round(new / shr0, 6)}})
        lk["shr"] = shr0 + new
    CASES_A = copy.deepcopy(CASES["069080"])
    try:
        CASES["069080"]["s"]["shr"] = shr0 + new
        by, counts, why, _ = run("069080", edit={"069080": a})
        assert counts["proof"]["rightsT"] == ["069080"] and "dyt" not in by["069080"] and "dvProof" not in by["069080"]

        def a2(lk):
            _with_rights(lk, rc, "2026-03-02", 0, {}, fx=False)                      # 목록에는 있는데 API 가 방식 · 주식 수를 주지 않음
            lk["oth"].append({"k": "cb", "d": "2026-02-01", "rc": "20260201000222"})
            lk["fx"] = [{"k": "cb", "d": "2026-02-01", "n": 1_400_000, "rc": "20260201000222"}]
            lk["fxT"], lk["fxBad"] = {}, [{"rc": "", "why": "목록에는 유상증자 결정이 있는데 piicDecsn.json 가 주지 않음"}]
            lk["shr"] = 36_500_000
        CASES["069080"]["s"]["shr"] = 36_500_000
        by, counts, why, _ = run("069080", edit={"069080": a2})
        assert counts["proof"]["failT"] == ["069080"] and counts["proof"]["rights"] == 0 and "dyt" not in by["069080"]
        assert any("방식 · 크기를 읽지 못함" in x for x in why.summary())
    finally:
        CASES["069080"] = CASES_A


def test_an_unknown_rights_method_blocks_end_to_end():
    """대동금속의 제3자배정 결정을 방식을 모르는 것으로 바꾸면 (ic_mthn 이 비었거나 낯선 글) 되살리지 않아요 (rights)."""
    rc = CASES["020400"]["look"]["fx"][0]["rc"]
    by, counts, why, _ = run("020400", edit={"020400": lambda lk: lk["fxT"][rc].update(m="?")})
    assert counts["proof"]["rightsT"] == ["020400"] and by["020400"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"}
    assert as_on_main(by["020400"], "020400") and any("방식을 모르는 유상증자" in x for x in why.summary())


def test_new_shares_are_scaled_by_the_proofs_own_events_when_they_multiply_to_one():
    """리뷰 2차: 올해 사건의 곱이 1 (병합 ×0.5 뒤 분할 ×2) 이면 dvWhy 가 없어요 — 관문도 dvProof 에 적은 사건으로 새 주식 수를 다시 세요."""
    ev = [{"k": "merge", "d": "2026-03-01", "r": 0.5, "rc": "20260201000301", "src": "doc"},
          {"k": "split", "d": "2026-06-01", "r": 2.0, "rc": "20260501000302", "src": "doc"}]
    by, counts, why, _ = run("403550", edit={"403550": lambda lk: lk.update(ev=list(lk.get("ev") or []) + ev)})
    s = by["403550"]                                                                                   # 쏘카: 제3자배정 (5월 18일) 은 분할 앞
    assert s["dpsF"][0] == 1.0 and "dvWhy" not in s and s["dvProof"]["cv"] == 5_098_040 * 2
    assert [e["k"] for e in s["dvProof"]["ev"]] == ["merge", "split"]
    c = {"t": "403550", "cash3": [round(x / 1e8, 2) if x is not None else None for x in CASES["403550"]["bas"]["cash3"]]}
    assert V.dvproof_problems(s, c, PX) is None
    s["dvProof"]["cv"] = 5_098_040                                                                     # 사건을 모르고 센 수 — 관문이 잡아요
    assert "fx 가 덮는" in V.dvproof_problems(s, c, PX)


def test_the_gate_uses_the_pipelines_ratio_not_the_rounded_dps3a():
    """리뷰 2차 (새 실패 줄은 우리 기록이 어긋날 때만): 배율 뒤 0.67원 같은 아주 작은 배당은 dps3a 반올림만으로 1 ± 3% 경계를 넘을 수
    있어요. 관문은 파이프라인이 정한 n × f ÷ 오늘 주식 수로 보고, dps3a 는 주당 배당 ÷ 배율 (원 둘째 자리) 그대로인지 따로 봐요."""
    shr, f = 30_000_000, 3.0
    n = 0.9701 * shr / f                                    # 파이프라인: n × f ÷ shr = 0.9701 (받아요)
    assert F.prove_today(n, f, shr)
    s = {"t": "123450", "fy": 2025, "price": 1000.0, "shr": shr, "dps3": [2.0, 0.0, 0.0], "dpsF": [f, None, None],
         "dps3a": [round(2.0 / f, 2), 0.0, 0.0],
         "dvProof": {"v": 1, "y0": "today", "yrs": [], "c": [int(round(n * 2.0)), None, None], "shr": shr,
                     "ev": [{"k": "split", "d": "2026-03-02", "r": f, "rc": "20260202000123"}]}}
    assert V.dvproof_problems(s, {}, PX) is None             # 반올림한 0.67 로 셈하면 0.965 라 예전엔 실패였어요
    s["dps3a"][0] = 0.68
    assert "dps3a[0]" in V.dvproof_problems(s, {}, PX)


def test_a_stock_through_check_refetches_when_its_shares_moved():
    """리뷰 2차 SF3: 맞춤 이유(check)를 거친 종목(대동금속)이 쓰는 같은 항목도, 받은 뒤 상장 주식 수가 3% 넘게 달라졌으면 증명 전에 다시 받아요."""
    moved = int(CASES["020400"]["s"]["shr"] * 0.95)
    by, counts, why, cl = run("020400", edit={"020400": lambda lk: lk.update(shr=moved)})
    assert "list.json" in cl.calls and counts["proof"]["failT"] == ["020400"] and why.n["pRefetch"] == 1
    assert by["020400"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"} and "dyt" not in by["020400"]


def test_refetch_is_counted_only_when_it_happens_and_no_shares_means_no_daily_refetch():
    cl = Client(["298040"], old=True)
    cl.seed("298040", [F._fin(x) for x in basis_of("298040")["dpsF"]])
    w = F.DivWhy(cl, PX)
    w.prove_left = 0
    s = stock_of("298040")
    counts, _ = F.apply_div_basis([s], {}, {}, why=w)
    assert w.n["pRefetch"] == 0 and w.n["pLimit"] == 1 and counts["proof"]["failT"] == ["298040"]
    assert not F.prove_shr_moved(None, 100) and not F.prove_shr_moved(100, None) and F.prove_shr_moved(100, 104)
    by, counts, why, cl = run("298040", edit={"298040": lambda lk: lk.pop("shr")})        # 받을 때 주식 수를 몰랐던 항목
    assert "list.json" not in cl.calls and by["298040"]["dvProof"]["y0"] == "today" and why.n["pRefetch"] == 0


def test_old_proof_fields_never_survive_a_stock_the_stage_skips():
    """어제 줄을 그대로 받은 종목이 이번엔 건너뛰어져도 (우선주 · 배당 표 없음) 지난 dvProof · dvLine 이 남지 않아요 — 관문은 기록 없는 칸에 실패해요."""
    a = {"t": "005935", "cls": "kr", "dvProof": {"v": 1}, "dvLine": 1}
    b = {"t": "123450", "cls": "kr", "dvProof": {"v": 1}, "dvLine": 1}
    F.apply_div_basis([a, b], {}, {}, why=None)
    assert not any(k in x for x in (a, b) for k in ("dvProof", "dvLine", "dvWhy"))


def test_switch_off_keeps_the_old_behaviour():
    by, counts, why, _ = run("298040", "020400", prove=False)
    assert "dyt" not in by["298040"] and by["020400"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"} and "proof" not in counts


def test_no_nan_reaches_the_file():
    by, counts, _, _ = run(*CASES)
    json.dumps([by, counts], allow_nan=False)


# ── 3. 관문이 같은 숫자로 다시 맞춰 봐요 ──────────────────────
def gate_files(*ts):
    """증명한 종목들을 data.json · corp.json 모양으로 (관문의 dvproof_problems 가 보는 칸)."""
    by, counts, _, _ = run(*ts)
    comps = {t: {"t": t, "cash3": [round(x / 1e8, 2) if x is not None else None for x in CASES[t]["bas"]["cash3"]]} for t in ts}
    return by, comps, counts


def test_the_gate_agrees_with_every_real_proof():
    by, comps, counts = gate_files(*CASES)
    done = sorted(t for t, s in by.items() if "dvProof" in s)
    assert done == ["001230", "001750", "020400", "032960", "036630", "064400", "064960", "069080", "084010", "196170", "241560",
                    "257720", "298040", "403550", "443060"]                                            # v19.1j 답 12: 대한제강 · 알테오젠
    assert counts["proof"] == {"v": 1, "today": 5, "yearEnd": 7, "years": 9, "line": 0, "ratio": 0, "basis": 2, "rights": 3,
                               "uncounted": 2, "data": 4, "fail": 1, "lineT": [], "ratioT": [],
                               "basisT": ["000880", "045300"], "rightsT": ["210980", "356860", "432320"], "uncountedT": ["005440", "049430"],
                               "dataT": ["002310", "003380", "086900", "290650"], "failT": ["010130"]}
    ex = {"084010", "196170"}                                                                         # 공시의 정확한 무상증자 배율 (세 조건)
    assert all(V.exact_bonus_problem(by[t], comps[t], PX) is None for t in ex)
    assert all(V.dvproof_problems(by[t], comps[t], PX, exact=t in ex) is None for t in done), \
        [(t, V.dvproof_problems(by[t], comps[t], PX, exact=t in ex)) for t in done]


def test_the_gate_scales_new_shares_by_the_events_after_their_own_date():
    ev = [{"k": "bonus", "d": "2026-07-20", "r": 2.0, "x": 1.0, "rc": "20260702000142"}]
    fx = [{"k": "rights", "d": "2026-07-02", "n": 2_073_000, "rc": "20260702000142"}]
    assert V._prove_cover(fx, 2025, PX, ev) == (4_146_000, None)                                          # 티엘비: 유상 몫 뒤 무상증자 ×2
    fx2 = [{"k": "rights", "d": "2026-08-12", "n": 3_000_000, "rc": "20260812000426"}]
    ev2 = [{"k": "bonus", "d": "2026-04-13", "r": 2.0, "x": 1.0, "rc": "20260326001131"}]
    assert V._prove_cover(fx2, 2025, PX, ev2) == (3_000_000, None)                                        # 대동금속: 무상증자가 먼저라 그대로
    assert V._prove_cover([{**fx2[0], "k": "cb"}], 2025, PX, [])[0] == pytest.approx(3_000_000 / 0.7)
    old = [{"k": "split", "d": "2025-06-01", "r": 2.0, "rc": "20250501000001"}]                           # 그해 말 전 사건은 늘리지 않아요
    assert V._prove_cover([{**fx2[0], "d": "2025-08-01"}], 2025, PX, old) == (3_000_000, None)


@pytest.mark.parametrize("t,change,part", [
    ("298040", lambda s, c: s.update(dpsF=[2.0, 1.0, 1.0], dps3a=[3750.0, 5000.0, 2500.0]), "사건(ev)이 없어요"),       # 사건 없는 배율
    ("001230", lambda s, c: s.update(dpsF=[4.0, 5.0, 5.0], dps3a=[25.0, 100.0, 120.0]), "ev 의 곱"),                 # 사건과 다른 배율
    ("001230", lambda s, c: (s.update(dpsF=[4.0, 5.0, 5.0], dps3a=[25.0, 100.0, 120.0]), s["dvProof"]["ev"][0].update(r=4.0)),
     "배당 총액 ÷ 시가총액"),                                                                     # 사건까지 틀려도 총액이 잡아요
    ("001230", lambda s, c: s["dvProof"]["ev"][0].update(d="2025-06-01"), "ev 날짜"),
    ("298040", lambda s, c: c.update(cash3=[700.0, 465.59, 232.79]), "corp.json cash3"),
    ("298040", lambda s, c: s.update(shr=s["shr"] + 1000), "오늘 상장 주식 수"),
    ("069080", lambda s, c: s["dvProof"].update(cmo=27_000_000), "그해 말 유통 주식 수"),
    ("020400", lambda s, c: s["dvProof"].update(cv=6_000_000), "fx 가 덮는"),                    # 그 앞 무상증자 ×2 까지 곱한 수 — 틀려요
    ("020400", lambda s, c: (s["dvProof"].update(cv=0), s["dvProof"].pop("fx")), "밖"),
    ("064960", lambda s, c: s.update(dpsF=[1.0, 1.0, 2.0], dps3a=[1700.0, 1700.0, 800.0]), "앞 해 1"),
    ("298040", lambda s, c: s["dvProof"].update(y0="guess"), "y0"),
    ("298040", lambda s, c: s["dvProof"].update(c=[1.5, None, None]), "c (배당 총액"),
    ("001750", lambda s, c: s["dvProof"].update(yrs=[1]), "우선주 몫"),
])
def test_the_gate_catches_a_wrong_proof(t, change, part):
    by, comps, _ = gate_files(t)
    s, c = by[t], comps[t]
    assert V.dvproof_problems(s, c, PX) is None
    change(s, c)
    why = V.dvproof_problems(s, c, PX)
    assert why and part in why, why


ROWS = ("배당 기준 증명 기록 (divCheck.proof)", "되살린 배당수익률 = 배당 총액 ÷ 시가총액 (dvProof)",
        "배당 기준 증명 경고 (되살리지 않은 이유 · 조회 실패)")
PROOF0 = {"v": 1, **{k: 0 for k in V.PROVE_KEYS}, **{k + "T": [] for k in V.PROVE_HID}}


def with_proof(files):
    """좋은 픽스처의 배당 회사 하나를 '총액 ÷ 오늘 주식 수'로 되살린 종목처럼 (파이프라인과 같은 칸)."""
    with_why(files)
    kr = [s for s in files["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    s = next(x for x in kr if x.get("divSt") == "same" and x["t"] not in V.MUST and x.get("dyt"))
    shr = 10_000_000
    cash = int(s["dps3"][0] * shr)
    s.update(shr=shr, dvProof={"v": 1, "y0": "today", "yrs": [1, 2], "c": [cash, cash, cash], "shr": shr})
    for c in files["corp"]["companies"]:
        if c["t"] == s["t"]:
            c["cash3"] = [round(cash / 1e8, 2)] * 3
    files["data"]["divCheck"]["proof"] = {**PROOF0, "today": 1, "years": 1}
    return files, s


@pytest.fixture
def pair():
    cur, prev, _ = good_pair()
    files, s = with_proof(cur)
    return files, prev, s


def _row(rep, name):
    return rows_of(rep)[name][3]


def test_good_proofs_pass_every_new_row(pair):
    cur, prev, s = pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert [_row(rep, n) for n in ROWS] == ["PASS", "PASS", "PASS"]
    assert not check(cur, None, mode="live").failed


def test_data_before_v191i_is_only_a_warning_until_published(pair):
    cur, prev, s = pair
    cur["data"]["divCheck"].pop("proof")
    s.pop("dvProof")
    rep = check(cur, prev)
    assert not rep.failed and _row(rep, ROWS[0]) == "WARN"
    rep = check(cur, {"data": copy.deepcopy(cur["data"]) | {"divCheck": {**cur["data"]["divCheck"], "proof": dict(PROOF0)}}})
    assert ROWS[0] in {r[0] for r in rep.failed}                                                      # 한 번 발행된 뒤 빠지면 실패


def test_a_proof_without_the_record_fails(pair):
    cur, prev, s = pair
    cur["data"]["divCheck"].pop("proof")
    rep = check(cur, prev)
    assert ROWS[1] in {r[0] for r in rep.failed}


@pytest.mark.parametrize("change", [
    lambda d, s, o: d["divCheck"]["proof"].update(today=2),
    lambda d, s, o: d["divCheck"]["proof"].update(years=0),
    lambda d, s, o: d["divCheck"]["proof"].update(v=2),
    lambda d, s, o: d["divCheck"]["proof"].update(fail=1),                                             # 이름 없이 수만
    lambda d, s, o: d["divCheck"]["proof"].update(rights=1, rightsT=[s["t"]]),                          # 되살린 종목을 이유 목록에
    lambda d, s, o: d["divCheck"]["proof"].update(data=1, dataT=["999999"]),                             # 없는 종목
    lambda d, s, o: d["divCheck"]["proof"].update(ratio=1, ratioT=[o["t"]]),                             # 수익률이 보이는 종목을 숨김 목록에
    lambda d, s, o: d["divCheck"]["proof"].update(ratio=1, ratioT=[o["t"]], fail=1, failT=[o["t"]]),    # 한 종목이 두 목록에
])
def test_the_record_must_match_the_stocks(pair, change):
    cur, prev, s = pair
    other = next(x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and x.get("dyt") and x is not s and "dvProof" not in x)
    change(cur["data"], s, other)
    rep = check(cur, prev)
    assert ROWS[0] in {r[0] for r in rep.failed}, rep.table()


def test_a_line_name_needs_jacks_line_and_a_wrong_conversion_fails(pair):
    cur, prev, s = pair
    nd = next(x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and not x.get("fund") and x.get("divSt") == "nd")
    cur["data"]["divCheck"]["proof"].update(line=1, lineT=[nd["t"]])
    rep = check(cur, prev)
    assert ROWS[0] in {r[0] for r in rep.failed}                                                      # dvWhy nc-unexplained 가 없어요
    fresh, prev2, _ = good_pair()
    cur, s = with_proof(fresh)
    s["dvProof"]["c"] = [x * 2 for x in s["dvProof"]["c"]]                                              # 총액이 두 배 = 배율이 틀린 것
    for c in cur["corp"]["companies"]:
        if c["t"] == s["t"]:
            c["cash3"] = [round(x / 1e8, 2) for x in s["dvProof"]["c"]]
    rep = check(cur, prev2)
    assert ROWS[1] in {r[0] for r in rep.failed}


@pytest.mark.parametrize("case", ["mark_without_line", "line_without_mark", "mark_on_yield"])
def test_jacks_line_mark_must_match_the_line_list(pair, case):
    """dvLine (앱이 줄을 보여 주는 표시) 은 lineT 의 종목에만, 그 종목엔 꼭 · dvWhy nc-unexplained · 수익률 없음."""
    cur, prev, s = pair
    kr = [x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and not x.get("fund") and x.get("divSt") == "nd"]
    a = kr[0]
    a["dvWhy"] = {"v": 1, "st": "nc-unexplained"}
    a["dpsF"] = [None] * 3
    a["dps3a"] = [None if (d or 0) > 0 else d for d in a["dps3"]]
    mirror(cur, a)
    proof = cur["data"]["divCheck"]["proof"]
    recount(cur)
    recount_why(cur)
    cur["data"]["divCheck"]["proof"] = proof
    if case == "mark_without_line":
        a["dvLine"] = 1
    elif case == "line_without_mark":
        proof.update(line=1, lineT=[a["t"]])
    else:
        y = next(x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and x.get("dyt") and x is not s)
        y["dvLine"] = 1
    rep = check(cur, prev)
    assert ROWS[0] in {r[0] for r in rep.failed}, rep.table()
    if case == "line_without_mark":
        a["dvLine"] = 1
        assert not check(cur, prev).failed


def test_hidden_and_failed_names_warn_and_never_fail(pair):
    cur, prev, s = pair
    kr = [x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and not x.get("fund") and x.get("divSt") == "nd"]
    a = kr[0]
    a["dvWhy"] = {"v": 1, "st": "nc-unexplained"}
    a["dvLine"] = 1
    a["dpsF"] = [None] * 3
    a["dps3a"] = [None if (d or 0) > 0 else d for d in a["dps3"]]
    mirror(cur, a)
    proof = cur["data"]["divCheck"]["proof"]
    recount(cur)
    recount_why(cur)
    cur["data"]["divCheck"]["proof"] = proof
    with_yield = next(x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and x.get("dyt") and x is not s)
    proof.update(line=1, lineT=[a["t"]], rights=1, rightsT=[kr[1]["t"]], data=1, dataT=[kr[2]["t"]], fail=1, failT=[with_yield["t"]])
    rep = check(cur, prev)
    assert not rep.failed, rep.table()                                                                # 조회 실패는 수익률이 있는 종목일 수 있어요
    assert _row(rep, ROWS[2]) == "WARN" and a["t"] in rows_of(rep)[ROWS[2]][1] and "주주배정 유상증자" in rows_of(rep)[ROWS[2]][1]


def test_gate_and_pipeline_write_the_numbers_separately_but_agree():
    assert V.PROVE_TOL == F.PROVE_TOL and V.PROVE_DRIFT == F.DRIFT_TOL and V.PROVE_KEYS == F.PROVE_KEYS and V.PROVE_HID == F.PROVE_HID


def test_jacks_line_is_recorded_once_and_built():
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from copytrace import chat_approved
    assert chat_approved()["co.div.shareHidden"] == LINE
    src = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    assert src.count(LINE) == 1
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as f:
        assert f.read().count(LINE) == 1
