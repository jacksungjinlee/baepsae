# -*- coding: utf-8 -*-
"""v19.1i 배당 기준 증명 (Jack, 2026-11-14 item 5: '주식 수가 바뀐 뒤 배당수익률이 없는 72곳 — 계산을 고쳐요') — 데이터 · 관문 (네트워크 없음).

div_basis 가 오늘 주식 수 기준을 찾지 못한 해(nc · nd)를 DART 결정 공시(분할 · 병합 · 무상증자)와 주식 수로 증명할 수 있을 때만 되살려요
(fetch_data.DivWhy.prove). 관문(validate_data.check_v191i)은 그 근거를 발행된 숫자로 다시 맞춰 봐요: 되살린 수익률 = 배당 총액 ÷ 시가총액
(자기주식 · 공시된 새 주식만큼만 달라요).

픽스처 tests/fixtures/dvproof/cases.json 은 2026-11-14 에 OpenDART 에서 받은 실제 응답을 파이프라인의 해석 함수로 읽은 값이에요
(배당 표 alotMatter · 재무상태표 자본금 · 주식의 총수 현황 · 결정 공시 목록과 결정 · 원문 · 유상증자/사채 주식 수 — 키는 들어 있지 않아요).
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
    """DartClient 모양의 가짜 (네트워크 없음): 결정 공시 조회는 캐시 항목(실제 응답을 읽은 결과)으로 · 주식의 총수 현황은 실제 표로.
    get · get_zip 을 부르면 실패해요 (캐시를 다시 받지 않는다는 것도 함께 봐요)."""

    def __init__(self, ts, sd=True, net=None):
        self.entries = {}
        self.meta = {"corpMap": {t: CASES[t]["corp"] for t in ts}}
        self.today, self.mode = TODAY, "cache"
        self.status, self.lock = collections.Counter(), threading.Lock()
        self.revalidate_left, self.revalidated, self.down, self.fatal = 300, 0, None, None
        self.started_empty = False
        self.calls, self.net = [], net or {}
        self.t_of = {CASES[t]["corp"]: t for t in ts}
        self.sd = sd

    def seed(self, t, f_key):
        c = CASES[t]
        look = copy.deepcopy(c["look"])
        if not self.sd:
            look.pop("sd", None)
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
        c = CASES[self.t_of[corp]]
        return copy.deepcopy(c["stk"]) if endpoint == "stockTotqySttus.json" and year == c["s"]["fy"] else None


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


def run(*ts, client=None, prove=None, sd=True, net=None):
    """apply_div_basis 를 그대로 (check 다음 prove) → (종목들 {코드: s}, 집계, DivWhy, client)."""
    cl = client or Client(ts, sd=sd, net=net)
    for t in ts:
        cl.seed(t, [F._fin(x) for x in basis_of(t)["dpsF"]])
    why = F.DivWhy(cl, PX, prove=prove)
    stocks = [stock_of(t) for t in ts]
    pref = {t[:5]: CASES[t]["pref"] for t in ts if CASES[t]["pref"]}
    counts, extra = F.apply_div_basis(stocks, {}, pref, why=why)
    return {s["t"]: s for s in stocks}, counts, why, cl


def dyt_of(s):
    return round(s["dps3a"][0] / s["price"] * 100, 2)


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
    assert F.prove_year_end(3_183_333, 2.0, 9_073_532, d, cover=3_000_000) == (True, None)


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


def test_year_end_shares_with_cancelled_treasury_rights_issues_and_preferred_dividends():
    by, counts, why, cl = run("069080", "020400", "356860", "001750")
    wj, dd, tlb, hy = by["069080"], by["020400"], by["356860"], by["001750"]
    assert wj["dvProof"]["y0"] == "yearEnd" and wj["dvProof"]["cv"] == 0 and wj["dyt"] == round(700 / 12020 * 100, 2)
    # 대동금속 · 티엘비: 예전 맞춤(×3 · ×2.5)이 공시와 달라 숨겼던 종목 — 공시의 무상증자 ×2 로 되살리고, 그 뒤 유상증자는 공시가 덮어요
    for s, d0 in ((dd, 60.0), (tlb, 450.0)):
        assert s["dpsF"] == [2.0, 2.0, 2.0] and s["dps3a"][0] == d0 / 2 and s["divSt"] == "adj"
        assert s["dvWhy"]["st"] == "ok" and [(e["k"], e["r"]) for e in s["dvWhy"]["ev"]] == [("bonus", 2.0)]
        assert s["dvProof"]["y0"] == "yearEnd" and s["dvProof"]["cv"] > 0 and s["dvProof"]["fx"]
    assert dd["dyt"] == 0.99 and tlb["dyt"] == 0.52
    assert hy["dvProof"]["pf"] == 472_870 and hy["dvProof"]["pd"] == 1650.0 and hy["dvProof"]["yrs"] == []     # 한양증권: 우선주 몫을 빼요
    assert counts["why"]["nc-mismatch"] == 0 and counts["why"]["ok"] == 2 and counts["proof"]["yearEnd"] == 4
    assert not [c for c in cl.calls if c not in ("stockTotqySttus.json",)]                              # 보관본만 썼어요 (공시 다시 받기 없음)


def test_a_bonus_ratio_that_is_not_a_split_ratio_stays_hidden_with_jacks_line():
    """1.66 · 1.3 같은 무상증자 배율은 공시로 맞지만 관문이 받는 배율이 아니라 숨겨요 (Jack 이 정할 때까지) — 로그에 그 배율로 계산한 값을 남겨요."""
    by, counts, why, _ = run("084010", "196170")
    dj, alt = by["084010"], by["196170"]
    assert dj["dvWhy"] == {"v": 1, "st": "nc-mismatch"} and "dyt" not in dj and dj["dpsF"] == [None] * 3 and "dvProof" not in dj
    assert alt["dvWhy"] == {"v": 1, "st": "nc-mismatch"} and "dyt" not in alt and alt["divSt"] == "nc"
    assert counts["proof"]["hidT"] == ["084010", "196170"] and counts["why"]["nc-mismatch"] == 2
    lines = why.summary()
    assert any("196170" in x and "깨끗하지 않은 배율 ×1.3" in x and "0.16%" in x for x in lines)
    assert any("084010" in x and "그 배율이면 1주 301원" in x for x in lines)


def test_spin_offs_cancellations_and_unexplained_new_shares_stay_hidden_with_jacks_line():
    by, counts, why, _ = run("000880", "049430", "005440")
    for t in ("000880", "049430", "005440"):
        s = by[t]
        assert s["dvWhy"] == {"v": 1, "st": "nc-unexplained"} and "dyt" not in s and "dvProof" not in s, t
        assert all(f is None for f, d in zip(s["dpsF"], s["dps3"]) if (d or 0) > 0), t                  # 배당한 해는 모두 비교 불가
    assert counts["proof"]["hidT"] == ["000880", "005440", "049430"] and counts["why"]["nc-unexplained"] == 3
    lines = " ".join(why.summary())
    assert "000880 한화" in lines and "회사분할" in lines and "049430 코메론" in lines and "005440 현대지에프홀딩스" in lines


def test_dividend_tables_that_disagree_with_their_share_counts_stay_hidden_without_a_line():
    by, counts, why, _ = run("002310", "003380", "086900", "290650")
    for t in ("002310", "003380", "086900"):
        assert "dvWhy" not in by[t] and "dyt" not in by[t] and "dvProof" not in by[t], t                # 이유를 모르니 줄도 없어요
    assert by["290650"]["dvWhy"] == {"v": 1, "st": "nc-mismatch"}                                     # 엘앤씨바이오: 예전 판정(공시와 다름) 그대로
    assert counts["proof"]["dataT"] == ["002310", "003380", "086900", "290650"] and counts["proof"]["hid"] == 0
    assert any("배당 표가 어긋남 002310 아세아제지" in x for x in why.summary())


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
    yrs = collections.Counter(k for k in why.n if k.startswith("pYear:"))
    assert why.n["pYear:block"] >= 2 and yrs


def test_an_unreadable_filing_or_dart_off_changes_nothing():
    by, counts, why, _ = run("010130")
    s = by["010130"]
    assert counts["proof"]["failT"] == ["010130"] and "dvProof" not in s and s["dpsF"][1:] == [None, None]
    assert s["dyt"] == dyt_of(s) and s["divSt"] == "nc" and "dvWhy" not in s                       # 고려아연: 올해 수익률은 예전처럼 · 앞 해는 그대로
    stocks = [stock_of("298040")]
    w = F.DivWhy(None, PX)
    counts, _ = F.apply_div_basis(stocks, {}, {}, why=w)
    assert counts["proof"]["failT"] == ["298040"] and "dyt" not in stocks[0] and "dvProof" not in stocks[0]


def test_old_cache_entries_without_stock_dividends_are_fetched_again_once():
    cl = Client(["298040"], sd=False)
    cl.seed("298040", [F._fin(x) for x in basis_of("298040")["dpsF"]])
    w = F.DivWhy(cl, PX)
    s = stock_of("298040")
    counts, _ = F.apply_div_basis([s], {}, {}, why=w)
    assert "list.json" in cl.calls and counts["proof"]["failT"] == ["298040"] and "dyt" not in s     # 다시 받다 실패 → 그대로
    assert w.prove_left == F.PROVE_PER_RUN - 1 and w.fetch_left == F.DVWHY_PER_RUN                 # 증명의 한도는 따로 (맞춤 이유의 한도는 그대로)
    w2 = F.DivWhy(cl, PX)                                                                                # check 만 쓰는 조회는 sd 가 없어도 보관본
    key = [F._fin(x) for x in basis_of("298040")["dpsF"]]
    look, how = w2._look(CASES["298040"]["corp"], 2025, key)
    assert how == "cache" and "sd" not in look


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
    assert done == ["001230", "001750", "020400", "032960", "064960", "069080", "241560", "257720", "298040", "356860", "443060"]
    assert counts["proof"] == {"v": 1, "today": 4, "yearEnd": 5, "years": 8, "hid": 5, "data": 4, "fail": 1,
                               "hidT": ["000880", "005440", "049430", "084010", "196170"],
                               "dataT": ["002310", "003380", "086900", "290650"], "failT": ["010130"]}
    assert all(V.dvproof_problems(by[t], comps[t], PX) is None for t in done), [(t, V.dvproof_problems(by[t], comps[t], PX)) for t in done]


@pytest.mark.parametrize("t,change,part", [
    ("298040", lambda s, c: s.update(dpsF=[2.0, 1.0, 1.0], dps3a=[3750.0, 5000.0, 2500.0]), "배당 총액 ÷ 시가총액"),     # 틀린 배율 (총액이 잡아요)
    ("001230", lambda s, c: s.update(dpsF=[4.0, 5.0, 5.0], dps3a=[25.0, 100.0, 120.0]), "배당 총액 ÷ 시가총액"),
    ("298040", lambda s, c: c.update(cash3=[700.0, 465.59, 232.79]), "corp.json cash3"),
    ("298040", lambda s, c: s.update(shr=s["shr"] + 1000), "오늘 상장 주식 수"),
    ("069080", lambda s, c: s["dvProof"].update(cmo=27_000_000), "그해 말 유통 주식 수"),
    ("020400", lambda s, c: s["dvProof"].update(cv=s["dvProof"]["cv"] + 500_000), "fx 가 덮는"),
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
        "배당 기준 증명 경고 (숨김 · 배당 표 어긋남 · 조회 실패)")
PROOF0 = {"v": 1, "today": 0, "yearEnd": 0, "years": 0, "hid": 0, "data": 0, "fail": 0, "hidT": [], "dataT": [], "failT": []}


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
    lambda d, s: d["divCheck"]["proof"].update(today=2),
    lambda d, s: d["divCheck"]["proof"].update(years=0),
    lambda d, s: d["divCheck"]["proof"].update(v=2),
    lambda d, s: d["divCheck"]["proof"].update(fail=1),                                              # 이름 없이 수만
    lambda d, s: d["divCheck"]["proof"].update(hid=1, hidT=[s["t"]]),                                  # 되살린 종목을 숨김 목록에
    lambda d, s: d["divCheck"]["proof"].update(data=1, dataT=["999999"]),                               # 없는 종목
])
def test_the_record_must_match_the_stocks(pair, change):
    cur, prev, s = pair
    change(cur["data"], s)
    rep = check(cur, prev)
    assert ROWS[0] in {r[0] for r in rep.failed}, rep.table()


def test_a_hidden_name_needs_jacks_line_and_a_wrong_conversion_fails(pair):
    cur, prev, s = pair
    kr = [x for x in cur["data"]["stocks"] if x.get("cls") == "kr" and not x.get("fund") and x.get("divSt") == "same" and x is not s
          and x["t"] not in V.MUST]
    h = kr[0]
    cur["data"]["divCheck"]["proof"].update(hid=1, hidT=[h["t"]])
    rep = check(cur, prev)
    assert ROWS[0] in {r[0] for r in rep.failed}                                                      # dvWhy nc-* 가 없어요
    fresh, prev2, _ = good_pair()
    cur, s = with_proof(fresh)
    s["dvProof"]["c"] = [x * 2 for x in s["dvProof"]["c"]]                                              # 총액이 두 배 = 배율이 틀린 것
    for c in cur["corp"]["companies"]:
        if c["t"] == s["t"]:
            c["cash3"] = [round(x / 1e8, 2) for x in s["dvProof"]["c"]]
    rep = check(cur, prev2)
    assert ROWS[1] in {r[0] for r in rep.failed}


def test_hidden_data_and_failed_names_warn_and_never_fail(pair):
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
    cur["data"]["divCheck"]["proof"].update(hid=1, hidT=[a["t"]], data=1, dataT=[kr[1]["t"]], fail=1, failT=[kr[2]["t"]])
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert _row(rep, ROWS[2]) == "WARN" and a["t"] in rows_of(rep)[ROWS[2]][1]


def test_gate_and_pipeline_write_the_numbers_separately_but_agree():
    assert V.PROVE_TOL == F.PROVE_TOL and V.PROVE_DRIFT == F.DRIFT_TOL and V.PROVE_KEYS == F.PROVE_KEYS


def test_jacks_line_is_recorded_once_and_built():
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from copytrace import chat_approved
    assert chat_approved()["co.div.shareHidden"] == LINE
    src = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    assert src.count(LINE) == 1
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as f:
        assert f.read().count(LINE) == 1
