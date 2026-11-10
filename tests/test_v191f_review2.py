# -*- coding: utf-8 -*-
"""v19.1f 리뷰 2 (2026-11-08 · 2d8d8fa 리뷰 · Jack 의 답): ROE 기준 · 원화가 아닌 재무제표 · 신종자본증권 · 옮겨 온 업종 코드만 든 캐시 ·
관문 새 줄 · FinanceCostsPaid 이자 · 비지배지분이 없으면 당기순이익 = 지배주주 순이익 · 낸 이자가 없으면 이자보상배율 경고 없음.

픽스처 tests/fixtures/dart_review_samples.json 은 그날 받은 실제 연결 재무제표 (KB금융 · 포스코퓨처엠 사업보고서와 반기 · GMI벤처 ·
라이온켐텍 · LG에너지솔루션)의 손익·자본·신종자본증권·이자 지급 줄이에요. (네트워크 없음)"""
import copy
import datetime as dt
import gzip
import json
import os
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from test_v191f_income import check, comp, fails, pair, rows_of  # noqa: E402,F401  (pair 는 pytest 픽스처)

with open(os.path.join(ROOT, "tests", "fixtures", "dart_review_samples.json"), encoding="utf-8") as _f:
    ST = json.load(_f)["statements"]
NO_ID = "-표준계정코드 미사용-"


def rows(t, y="2025", r="11011"):
    return copy.deepcopy(ST[f"{t}|{y}|{r}|CFS"]["rows"])


def r(sj, nm, aid, a, b=None, c=None, add=None, cur=None, detail=None):
    out = {"sj_div": sj, "account_nm": nm, "account_id": aid, "thstrm_amount": str(a)}
    for k, v in (("frmtrm_amount", b), ("bfefrmtrm_amount", c), ("thstrm_add_amount", add), ("currency", cur), ("account_detail", detail)):
        if v is not None:
            out[k] = str(v)
    return out


def kb_fin():
    """KB금융: 2025 사업보고서 + 2026·2025 반기 → TTM (파이프라인과 같은 모양)."""
    fin = dict(F.parse_dart_list(rows("105560"))["_fin"], fs="CFS", bq="2026.2Q")
    t2 = F.compute_ttm(fin, F.parse_dart_quarter(rows("105560", "2026", "11012")), F.parse_dart_quarter(rows("105560", "2025", "11012")))
    fin["ttm"], fin["bs2"] = t2["ttm"], t2["bs"]
    return fin


# ── 1. 신종자본증권 (실제 재무제표) ─────────────────────────────────
def test_hybrid_capital_is_read_from_the_owners_rows_of_the_real_statements():
    kb = F.parse_dart_list(rows("105560"))["_fin"]
    assert kb["hyb"] == {"ok": True, "eq": 43593.9, "dist": 2023.9, "dist3": [2023.9, 1998.0, 1849.2]}
    assert kb["nio"] == 58331.6 and kb["epsRep"] == 15410.0
    pf = F.parse_dart_list(rows("003670"))["_fin"]
    assert pf["hyb"] == {"ok": True, "eq": 5993.7, "dist": 280.7, "dist3": [280.7, 7.6, None]}
    assert pf["nio"] == 322.6 and pf["epsRep"] == 51.0
    # 회사가 낸 기본주당이익과 같은 방식: (지배주주 순이익 − 신종자본증권 분배) ÷ 가중평균 주식 수
    es = F.eps_source(dict(kb, fs="CFS"))
    assert es == (56307.7, "o", "fy", "code", 2023.9)
    assert round(es[0] * 1e8 / 365_400_000) == pytest.approx(15410, rel=0.002)            # KB금융 2025 가중평균 약 3.654억 주
    assert F.eps_source(dict(pf, fs="CFS"))[0] == 41.9                                    # 322.6 − 280.7 → 기본주당이익 51원 (약 8,200만 주)
    q = F.parse_dart_quarter(rows("105560", "2026", "11012"))
    assert q["hyb"] == {"ok": True, "eq": 42067.2, "dist": 868.1}                        # 반기 자본변동표도 같은 줄


def test_hybrid_ttm_eps_bps_and_receipts():
    fin = kb_fin()
    assert fin["ttm"]["hyb"] == {"ok": True, "dist": 1858.8}                             # 2,023.9 + 868.1 − 1,033.2
    assert F.eps_source(fin) == (round(62820.6 - 1858.8, 1), "o", "ttm", "code", 1858.8)
    assert F.bps_source(fin) == (round(608908.4 - 42067.2, 1), "o", "code", "ttm", 42067.2)  # 보통주 자본 (신종자본증권 뺌)
    s = {"t": "105560", "nk": "KB금융", "cls": "kr", "price": 100000.0, "shr": 360_000_000, "cap": 36.0}
    extra = F.fill_multiples([s], {"105560": fin}, {})["105560"]
    assert extra["epsIn"]["hyb"] == 1858.8 and extra["bpsIn"]["hyb"] == 42067.2
    assert s["eps"] == round((62820.6 - 1858.8) * 1e8 / 360_000_000)
    assert extra["epsFy"] == round(56307.7 * 1e8 / 360_000_000) and extra["epsRep"] == 15410.0


def test_hybrid_capital_that_cannot_be_placed_keeps_the_total_basis():
    base = [r("BS", "자본총계", "ifrs-full_Equity", 4e12), r("BS", "부채총계", "ifrs-full_Liabilities", 2e12),
            r("BS", "지배기업 소유주지분", "ifrs-full_EquityAttributableToOwnersOfParent", 4e12),
            r("BS", "신종자본증권", "dart_HybridBonds", 5e11),
            r("CIS", "당기순이익", "ifrs-full_ProfitLoss", 1e11),
            r("CIS", "지배기업 소유주지분", "ifrs-full_ProfitLossAttributableToOwnersOfParent", 1e11)]
    fin = dict(F.parse_dart_list(base)["_fin"], fs="CFS")
    assert fin["hyb"]["ok"] is False and fin["hyb"]["eq"] == 5000.0 and fin["hyb"]["dist"] == 0.0   # 자본변동표가 없어 분배를 몰라요
    assert F.eps_source(fin) == (1000.0, "t", "fy", "hybrid", 0.0)                       # 추측하지 않아요 → '전체'(앱의 '고치는 중' 줄)
    assert F.bps_source(fin) == (40000.0, "t", "hybrid", "fy", 0.0)
    assert F.roe_source(fin) is None
    placed = base + [r("SCE", "신종자본증권 배당", "dart_DividendToHybridBond", -2e10, detail="자본 [member]|지배기업 소유주지분 [member]")]
    fin2 = dict(F.parse_dart_list(placed)["_fin"], fs="CFS")
    assert F.eps_source(fin2) == (800.0, "o", "fy", "code", 200.0) and F.bps_source(fin2)[:2] == (35000.0, "o")
    minority = base + [r("SCE", "신종자본증권 배당", "dart_DividendToHybridBond", -2e10, detail="자본 [member]|비지배지분 [member]")]
    assert F.parse_dart_list(minority)["_fin"]["hyb"]["dist"] == 0.0                      # 비지배 몫 분배는 주주 몫에서 빼지 않아요


# ── 2. 원화가 아닌 재무제표 ─────────────────────────────────────
USD = [r("BS", "자본총계", "ifrs-full_Equity", 5.01e9, cur="USD"), r("BS", "부채총계", "ifrs-full_Liabilities", 3e9, cur="USD"),
       r("CIS", "매출액", "ifrs-full_Revenue", 6.18e9, cur="USD"),
       r("CIS", "당기순이익", "ifrs-full_ProfitLoss", 2.8e8, cur="USD"),
       r("CIS", "지배기업 소유주지분", "ifrs-full_ProfitLossAttributableToOwnersOfParent", 2.8e8, cur="USD")]


def test_statements_in_another_currency_are_marked_and_their_amounts_never_reach_the_files(capsys):
    assert F.stmt_currency(USD) == "USD" and F.stmt_currency(rows("105560")) is None   # 실제 재무제표는 KRW
    fin = dict(F.parse_dart_list(USD)["_fin"], fs="CFS")
    q = F.parse_dart_quarter([dict(x, thstrm_add_amount=x["thstrm_amount"]) for x in USD])
    assert fin["cur"] == "USD" and q["cur"] == "USD" and F.compute_ttm(dict(fin, cur=None), q, q)["ttm"]["cur"] == "USD"
    s = {"t": "241560", "nk": "두산밥캣", "cls": "kr", "price": 51700.0, "shr": 95_856_065, "cap": 4.96, "dps": 1700.0, "dy": 3.3,
         "per": 14575.8, "pbr": 971.72, "eps": 4.0, "bps": 53.0, "roe": 5.6}
    other = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0}
    fins = {"241560": fin, "000100": {"ni": [5.0, None, None], "eq": 9.0, "fs": "OFS"}}
    assert F.blank_non_won([s, other], fins) == ["241560 두산밥캣(USD)"]
    assert "!! 원화가 아닌 재무제표로 낸 국내 회사 1곳: 241560 두산밥캣(USD)" in capsys.readouterr().out
    assert not any(k in s for k in ("per", "pbr", "eps", "bps", "roe")) and s["dps"] == 1700.0 and s["dy"] == 3.3   # 배당 표는 원
    extra = F.fill_multiples([s, other], fins, {})
    assert "241560" not in extra and "eps" not in s and "roe" not in s                  # 건너뛰어요 (ROE 도 비워요 · 리뷰 4)
    corp = {c["t"]: c for c in F.build_corp([s, other], fins, "2026-11-08", extra=extra)["companies"]}
    c = corp["241560"]
    assert c["stmtCur"] == "USD" and c["rev"] == [None] * 3 and c["ni"] == [None] * 3 and c["eq"] is None and c["dcfReady"] is False
    assert all(c.get(k) is None for k in ("per", "pbr", "eps", "bps", "roe", "qz")) and not any(k in c for k in V.STMT_AMT_KEYS)
    F.add_percentiles([s, other])                                               # 빈 ROE 는 퀄리티 점수를 매기지 않아요 (오류 없음)
    assert "qz" not in s
    assert "stmtCur" not in corp["000100"]


def test_anam_electronics_files_in_dollars_and_is_blanked_too():
    """008700 아남전자: 2026-11-08 시험 실행에서 매출 1.5억 · PBR 964.92 (달러 금액을 원으로 읽음 — 매출 1억 5,135만 달러)."""
    rows_ = rows("008700")
    assert F.stmt_currency(rows_) == "USD"
    fin = dict(F.parse_dart_list(rows_)["_fin"], fs="CFS")
    assert fin["cur"] == "USD" and fin["rev"][0] == 1.5                       # 151,351,168 달러 → 원으로 읽으면 1.5억
    s = {"t": "008700", "nk": "아남전자", "cls": "kr", "price": 1126.0, "shr": 77_124_820, "cap": 0.087, "pbr": 964.92, "bps": 1.0}
    assert F.blank_non_won([s], {"008700": fin}) == ["008700 아남전자(USD)"] and "pbr" not in s
    c = F.build_corp([s], {"008700": fin}, "2026-11-08", extra=F.fill_multiples([s], {"008700": fin}, {}))["companies"][0]
    assert c["stmtCur"] == "USD" and c["pbr"] is None and c["rev"] == [None] * 3 and not V.stmt_cur_problems(c, s)


def test_main_blanks_other_currencies_before_the_multiples():
    import inspect
    src = inspect.getsource(F.main)
    assert 0 < src.find("blank_foreign_dart(kr)") < src.find("blank_non_won(kr, fin_map)") < src.find("mult_extra = fill_multiples(")


def test_gate_fails_when_amounts_of_another_currency_reach_the_files(pair):
    cur, prev = pair
    name = "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)"
    c = comp(cur, "000270")
    c["stmtCur"] = "USD"                                                       # 금액이 남은 채로
    got = fails(cur, prev, name)
    assert "000270 corp.per" in got[1] or "000270" in got[1]
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    c.update(rev=[None] * 3, op=[None] * 3, ni=[None] * 3, eq=None, dcfReady=False, per=None, pbr=None, eps=None, bps=None, roe=None)
    for k in ("evE", "evR", "pcf", "cash3", "eps3r", "epsNi3", "nio3", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "vz", "qz",
              "fl", "flRan", "flSrc", "flWhy"):
        c.pop(k, None)
    for k in ("per", "pbr", "eps", "bps", "vz", "roe", "qz"):
        by["000270"].pop(k, None)
    cur["data"]["incCheck"]["epsB"]["o"] -= 1
    cur["data"]["incCheck"]["epsP"]["ttm" if c.get("bq") else "fy"] -= 1
    rep = check(cur, prev)
    got = rows_of(rep)
    assert got[name][3] == "PASS", got[name]
    assert got["원화가 아닌 재무제표로 낸 회사 (stmtCur · 금액은 비움)"][1].startswith("1곳: 000270")
    by["000270"]["eps"] = 4.0                                                  # data.json 에 하나라도 남으면
    assert "000270 data.eps" in " ".join(V.stmt_cur_problems(c, by["000270"]))
    fails(cur, prev, name)
    by["000270"].pop("eps")
    c["stmtCur"] = "KRW"                                                       # 원화는 표시하지 않아요
    fails(cur, prev, name)


def test_gate_warns_about_very_high_pbr_only(pair):
    cur, prev = pair
    s = next(x for x in cur["data"]["stocks"] if x["t"] == "000270")
    name = "PBR 100 넘는 국내 회사 (경고만)"
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    s["per"] = 5319.9                                                        # 이익이 아주 작은 회사의 큰 PER 은 경고하지 않아요 (리뷰 3)
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    s["pbr"] = 964.92
    row = rows_of(check(cur, prev))[name]
    assert row[3] == "WARN" and "000270" in row[1] and "PBR 964.92" in row[1]


# ── 리뷰 3 (67750e2 델타 리뷰) ─────────────────────────────────────
def test_hybrid_net_owners_profit_series_matches_the_eps_basis():
    kb = dict(F.parse_dart_list(rows("105560"))["_fin"], fs="CFS")
    assert kb["hyb"]["dist3"] == [2023.9, 1998.0, 1849.2]                     # 자본변동표 당기 · 전기 · 전전기 (지배기업 몫 칸)
    assert F.hybrid_net_series(kb, "o") == [56307.7, 48784.2, 44099.1]
    pf = dict(F.parse_dart_list(rows("003670"))["_fin"], fs="CFS")
    assert pf["hyb"]["dist3"] == [280.7, 7.6, None]                          # 전전기 칸이 없음 → 모름
    assert F.hybrid_net_series(pf, "o") == [41.9, -2130.8, None]              # 그 해는 '자료가 없어요'
    assert F.hybrid_net_series(pf, "t") is None and F.hybrid_net_series({"nio3": [1.0, 1.0, 1.0]}, "o") is None
    assert F.hybrid_net_series({"nio3": [5.0, 4.0, 3.0], "hyb": {"ok": True, "dist3": [0.0, 0.0, 0.0]}}, "o") is None
    assert F.hybrid_net_series({"ni": [5.0, 4.0, 3.0], "hyb": {"ok": True, "dist3": [1.0, 0.5, None]}}, "s") == [4.0, 3.5, None]
    assert F.hybrid_net_series({"nio3": [5.0, 4.0, 3.0], "hyb": {"ok": False, "dist3": [1.0, 0.5, 0.2]}}, "o") is None
    # corp.json 의 nio3 가 EPS 와 같은 순이익 (역DCF · 주가 분해가 epsBase 로 쓰는 값)
    s = {"t": "003670", "nk": "포스코퓨처엠", "cls": "kr", "price": 200000.0, "shr": 82_000_000, "cap": 16.4}
    extra = F.fill_multiples([s], {"003670": pf}, {})
    c = F.build_corp([s], {"003670": pf}, "2026-11-08", extra=extra)["companies"][0]
    assert c["nio3"] == [41.9, -2130.8, None] and c["nio3Hyb"] == [280.7, 7.6, None]
    assert round(c["nio3"][0] * 1e8 / c["epsIn"]["sh"]) == c["epsFy"] == c["eps"]      # 사업보고서 EPS 와 같은 기준
    assert c["nio3"][0] == c["roeIn"]["ni"]


def test_gate_checks_the_hybrid_receipt_shape(pair):
    cur, prev = pair
    name = "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)"
    c = comp(cur, "000270")
    c["nio3Hyb"] = [10.0, 5.0, None]
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    c["nio3Hyb"] = [10.0, 5.0]
    assert "000270.nio3Hyb" in fails(cur, prev, name)[1]
    c["nio3Hyb"] = [10.0, 5.0, None]
    c.pop("nio3")
    fails(cur, prev, name)


def test_statements_in_another_currency_carry_no_financial_signals(pair):
    fin = dict(F.parse_dart_list(rows("008700"))["_fin"], fs="CFS")
    assert fin["iec"] == 0.0 and fin["ni"][0] == 0.0                         # 1,068,247 달러 · 414만 달러를 0.1억으로 반올림하면 0
    s = {"t": "008700", "nk": "아남전자", "cls": "kr", "price": 1126.0, "shr": 77_124_820, "cap": 0.087, "s": "elec", "ind": "elec"}
    c = F.build_corp([dict(s, roe=4.4, qz=55)], {"008700": fin}, "2026-11-08")["companies"][0]   # blank_non_won 전이어도
    assert c["stmtCur"] == "USD" and not any(k in c for k in ("fl", "flSrc", "flWhy")) and c["flRan"] == []   # 돌린 검사 없음
    assert c["roe"] is None and c["qz"] is None                                # ROE 와 그 점수도 보여 주지 않아요 (리뷰 4)
    cur, prev = pair
    k = comp(cur, "000270")
    k.update(stmtCur="USD", rev=[None] * 3, op=[None] * 3, ni=[None] * 3, eq=None, dcfReady=False, per=None, pbr=None, eps=None, bps=None,
             flRan=["cr", "icr", "l3", "imp"])
    assert "000270 corp.flRan" in V.stmt_cur_problems(k, {})
    k.pop("flRan")
    k["flSrc"] = {"icr": "cf", "int0": True}
    got = V.stmt_cur_problems(k, {})
    assert "000270 corp.flSrc" in got and "000270 corp.flRan" not in got
    k["flRan"] = []                                                            # 돌린 검사 없음: 괜찮아요
    assert "000270 corp.flRan" not in V.stmt_cur_problems(k, {})
    k.pop("flRan")
    k.update(roe=5.6)
    assert "000270 corp.roe" in V.stmt_cur_problems(k, {}) and "000270 data.roe" in V.stmt_cur_problems(dict(k, roe=None), {"roe": 5.6})


def test_currency_codes_are_normalised():
    assert [F.norm_currency(x) for x in ("KRW", " krw ", "원", "USD", "usd", "달러", "엔", "", None, "dollar")] == \
        ["KRW", "KRW", "KRW", "USD", "USD", "USD", "JPY", None, None, "XXX"]
    assert F.stmt_currency([{"currency": "원"}, {"currency": "KRW"}]) is None
    assert F.stmt_currency([{"currency": " usd "}]) == "USD"


def test_separate_statements_with_hybrid_capital_get_the_cut():
    """합성 재무제표 (별도 재무제표에 신종자본증권이 있는 실제 표본이 없어요): 자본변동표에 지배·비지배 칸이 없고 비지배지분도 없어요."""
    base = [r("BS", "자본총계", "ifrs-full_Equity", 4e12), r("BS", "부채총계", "ifrs-full_Liabilities", 2e12),
            r("BS", "신종자본증권", "dart_HybridBonds", 5e11),
            r("CIS", "당기순이익", "ifrs-full_ProfitLoss", 1e11, 9e10),
            r("SCE", "신종자본증권 이자", "dart_InterestExpenseForHybridBond", -2e10, -1e10, detail="별도재무제표 [member]"),
            r("SCE", "신종자본증권 이자", "dart_InterestExpenseForHybridBond", -2e10, -1e10, detail="자본 [member]|이익잉여금 [member]")]
    fin = dict(F.parse_dart_list(base)["_fin"], fs="OFS")
    assert fin["hyb"] == {"ok": True, "eq": 5000.0, "dist": 200.0, "dist3": [200.0, 100.0, None]}
    assert F.eps_source(fin) == (800.0, "s", "fy", "ofs", 200.0) and F.bps_source(fin)[:2] == (35000.0, "s")
    assert F.roe_source(fin) == (round(800.0 / 35000.0 * 100, 1), 800.0, 35000.0, "s", "fy")
    with_nci = base + [r("BS", "비지배지분", "ifrs-full_NoncontrollingInterests", 1e11)]   # 비지배지분이 있는데 나눈 칸이 없으면 추측 안 해요
    assert F.parse_dart_list(with_nci)["_fin"]["hyb"]["ok"] is False


def test_owners_equity_is_equity_minus_minority_when_the_owners_line_is_missing():
    """DH오토넥스 · 삼기에너지솔루션즈 꼴: 지배주주 자본 줄이 없고 비지배지분 줄이 있어요."""
    fin = {"ni": [12.0, None, None], "nio": 10.0, "eq": 200.0, "nciBs": 20.0, "fs": "CFS"}
    assert F.bps_source(fin) == (180.0, "o", "minus", "fy", 0.0)
    assert F.roe_source(fin) == (round(10.0 / 180.0 * 100, 1), 10.0, 180.0, "o", "fy")
    s = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0, "roe": 6.0}
    extra = F.fill_multiples([s], {"000100": fin}, {})["000100"]
    assert extra["roeIn"]["b"] == "o" and s["roe"] == 5.6 and extra["bpsIn"]["how"] == "minus"


def test_bps_uses_the_latest_balance_sheet_that_gives_owners_equity_exactly():
    # 사업보고서엔 지배주주 자본 줄(code), 최신 분기엔 비지배지분이 없음(nci0) → 최신 분기 (시점이 먼저 · 둘 다 정확한 값)
    fin = {"eq": 9.0, "eqo": 7.0, "bs2": {"eq": 10.0, "nciBs": None}, "fs": "CFS"}
    assert F.bps_source(fin) == (10.0, "o", "nci0", "ttm", 0.0)
    fin["bs2"] = {"eq": 10.0, "nciBs": 1.5}                                   # 분기: 자본총계 − 비지배지분
    assert F.bps_source(fin) == (8.5, "o", "minus", "ttm", 0.0)


def test_half_year_without_minority_interest_total_is_the_owners_profit():
    q = [r("BS", "자본총계", "ifrs-full_Equity", 4e12), r("BS", "부채총계", "ifrs-full_Liabilities", 2e12),
         r("CIS", "매출액", "ifrs-full_Revenue", 1e11, add=2e11),
         r("CIS", "지배기업 소유주지분", "ifrs-full_ProfitLossAttributableToOwnersOfParent", 5e9, add=8e9)]
    got = F.parse_dart_quarter(q)
    assert got["nio"] == 80.0 and got["ni"] == 80.0                          # 당기순이익 줄이 없고 비지배지분도 없음 → 같아요
    with_nci = q + [r("BS", "비지배지분", "ifrs-full_NoncontrollingInterests", 3e9)]
    assert F.parse_dart_quarter(with_nci)["ni"] is None


# ── 3. ROE 를 EPS 와 같은 기준으로 (사업보고서 한 해) ─────────────────
def test_roe_is_owners_profit_over_owners_equity_of_the_same_annual_report():
    lg = dict(F.parse_dart_list(rows("373220"))["_fin"], fs="CFS")
    assert F.parse_dart_list(rows("373220"))["roe"] == 0.3                             # 예전: 전체 순이익 ÷ 전체 자본
    assert F.roe_source(lg) == (round(-10728.1 / 202155.5 * 100, 1), -10728.1, 202155.5, "o", "fy")   # 주주 몫은 손실
    kb = kb_fin()
    want = round((58331.6 - 2023.9) / (590482.1 - 43593.9) * 100, 1)
    assert F.roe_source(kb) == (want, 56307.7, round(590482.1 - 43593.9, 1), "o", "fy")   # TTM 이 있어도 사업보고서끼리 (앱의 'fy' 꼬리표)
    assert F.roe_source({"ni": [5.0, None, None], "eq": 50.0, "fs": "OFS"}) == (10.0, 5.0, 50.0, "s", "fy")
    assert F.roe_source({"ni": [5.0, None, None], "eq": 50.0, "fs": "CFS"}) is None      # 지배주주 순이익 없는 연결 → 예전 값 그대로
    assert F.roe_source({"ni": [5.0, None, None], "nio": 4.0, "eq": 50.0, "eqo": -1.0, "fs": "CFS"}) is None   # 주주 몫 자본 ≤ 0


def test_fill_multiples_writes_the_roe_receipt_and_keeps_the_old_value_otherwise():
    a = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0, "roe": 9.9}
    b = {"t": "000200", "nk": "나", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0, "roe": 7.7}
    fins = {"000100": {"ni": [5.0, None, None], "nio": 4.0, "eq": 50.0, "eqo": 40.0, "fs": "CFS"},
            "000200": {"ni": [5.0, None, None], "eq": 50.0, "fs": "CFS"}}
    extra = F.fill_multiples([a, b], fins, {})
    assert a["roe"] == 10.0 and extra["000100"]["roeIn"] == {"ni": 4.0, "eq": 40.0, "b": "o", "p": "fy"}
    assert b["roe"] == 7.7 and "roeIn" not in extra["000200"]


def test_roe_moves_counts_what_changes(capsys):
    kr = [{"t": f"{i:06d}", "nk": str(i), "cls": "kr", "roe": v} for i, v in enumerate([20.0, 12.0, 4.0, 0.3, 30.0, None])]
    old = {s["t"]: s["roe"] for s in kr}
    kr[0]["roe"], kr[1]["roe"], kr[3]["roe"], kr[5]["roe"] = 8.0, 12.5, -5.2, 3.0
    F.add_percentiles(kr)
    out = F.roe_moves(kr, old)
    assert len(out["changed"]) == 3 and len(out["big"]) == 2 and out["new"] == 1
    assert out["sign"] == ["000003 3 +0.3→-5.2"]
    assert {k: len(v) for k, v in out["line"].items()} == {5.0: 0, 10.0: 1, 15.0: 1}
    assert [x.split()[0] for x in out["floor"]] == ["000000", "000003"]                # 20 → 8 < 10 · 0.3 → −5.2 < 0
    assert "!! ROE 기준 (주주 몫 · 사업보고서) 으로 움직인 것: 바뀐 곳 3 (1%p 넘게 2)" in capsys.readouterr().out


def test_gate_checks_the_roe_receipt(pair):
    cur, prev = pair
    c = comp(cur, "000270")
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    name = "ROE 영수증 (roeIn: 주주 몫 ÷ 주주 몫 자본 · 사업보고서)"
    c["roeIn"] = {"ni": 45.0, "eq": 450.0, "b": "o", "p": "fy"}
    c["roe"] = by["000270"]["roe"] = 10.0
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    c["roe"] = by["000270"]["roe"] = 11.0
    fails(cur, prev, name)
    c["roe"] = by["000270"]["roe"] = 10.0
    c["roeIn"]["p"] = "ttm"                                                    # 사업보고서 한 해만
    fails(cur, prev, name)
    c["roeIn"]["p"] = "fy"
    by["000270"]["roe"] = 9.0                                                  # 두 파일이 다르면
    fails(cur, prev, "국내 EPS·BPS·PER·PBR·ROE: data.json = corp.json")


def test_gate_and_log_name_companies_whose_eps_is_owners_but_roe_is_not(pair, capsys):
    cur, prev = pair
    name = "EPS 는 주주 몫인데 ROE 는 예전 값인 회사 (경고만)"
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    comp(cur, "000270").pop("roeIn")
    row = rows_of(check(cur, prev))[name]
    assert row[3] == "WARN" and "000270" in row[1]
    s = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0, "roe": 9.9}
    fin = {"ni": [5.0, None, None], "nio": 4.0, "eq": 50.0, "fs": "CFS"}     # 주주 몫 자본 · 비지배지분 증거가 없는 연결
    extra = F.fill_multiples([s], {"000100": fin}, {})["000100"]
    assert extra["epsIn"]["b"] == "o" and "roeIn" not in extra and s["roe"] == 9.9
    assert "!! EPS 는 주주 몫인데 ROE 는 예전 값(전체 ÷ 전체)인 곳 1: 000100 가" in capsys.readouterr().out


# ── 4. 옮겨 온 업종 코드만 든 캐시는 빈 캐시 ───────────────────────────
def write_cache(path, entries, v=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump({"v": F.DART_CACHE_VERSION if v is None else v, "meta": {}, "entries": entries}, f)


KSIC_ONLY = {"C1|company": {"st": "000", "at": "2026-11-08", "d": {"induty": "264"}}}
WITH_FS = dict(KSIC_ONLY, **{"C1|2025|11011|CFS": {"st": "000", "at": "2026-11-08", "d": {"_fin": {"eq": 1.0}}}})


def test_a_cache_with_only_carried_industry_codes_is_an_empty_cache(tmp_path, monkeypatch):
    p = str(tmp_path / ".dart-cache" / "dart-v3.json.gz")
    write_cache(p, KSIC_ONLY)
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    assert F.DartClient("k", today=dt.date(2026, 11, 9), path=p).started_empty is True
    assert F.dart_cache_core(p) == 0
    monkeypatch.setenv("BAEPSAE_AUTO_RUN", "1")
    with pytest.raises(RuntimeError, match="DART 캐시가 비어 있어요"):
        F.DartClient("k", today=dt.date(2026, 11, 9), path=p)                            # 정해진 시각 실행은 DART 호출 전에 멈춰요
    write_cache(p, WITH_FS)
    assert F.DartClient("k", today=dt.date(2026, 11, 9), path=p).started_empty is False and F.dart_cache_core(p) == 1
    write_cache(p, WITH_FS, v=F.DART_CACHE_VERSION - 1)
    assert F.dart_cache_core(p) == 0 and F.dart_cache_core(str(tmp_path / "none.json.gz")) == 0
    with open(p, "w") as f:
        f.write("not gzip")
    assert F.dart_cache_core(p) == 0


def test_a_branch_full_run_reuses_the_cached_industry_codes(tmp_path, monkeypatch):
    """코디네이터 계획 (2026-11-08): 월요일 브랜치 시험 실행은 dart=full. 업종 코드는 full 에서도 보관본을 써요 (약 2,400회 아낌)."""
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    p = str(tmp_path / ".dart-cache" / "dart-v3.json.gz")
    write_cache(p, WITH_FS)
    c = F.DartClient("k", mode="full", today=dt.date(2026, 11, 9), path=p)
    monkeypatch.setattr(c, "get", lambda *a, **k: pytest.fail("업종 코드를 다시 받으면 안 돼요"))
    assert c.company("C1") == {"induty": "264"} and c.meta["lastFull"] == "2026-11-09" and not c.started_empty
    c.save()
    with pytest.raises(RuntimeError, match="이미 dart=full"):
        F.DartClient("k", mode="full", today=dt.date(2026, 11, 9), path=p)          # 하루 한 번만


def guard_script():
    with open(os.path.join(ROOT, ".github", "workflows", "update-data.yml"), encoding="utf-8") as f:
        steps = {s.get("name"): s for s in yaml.safe_load(f)["jobs"]["update"]["steps"]}
    run = steps["DART 캐시 확인 (정해진 시각 실행은 빈 캐시로 시작하지 않아요)"]["run"]
    return run.replace("${{ steps.dart_cache.outputs.cache-matched-key }}", "dart-cache-v3-1-1")


@pytest.mark.parametrize("entries, code", [(KSIC_ONLY, 1), (WITH_FS, 0), (None, 1)])
def test_the_workflow_guard_uses_the_same_rule(tmp_path, entries, code):
    p = str(tmp_path / ".dart-cache" / "dart-v3.json.gz")
    if entries is not None:
        write_cache(p, entries)
    else:
        os.makedirs(os.path.dirname(p))
        with open(p, "w") as f:
            f.write("x")                                                       # 비어 있지 않지만 읽을 수 없는 파일
    env = dict(os.environ, PYTHONPATH=ROOT)
    for k in ("DART_API_KEY", "DART_CACHE"):
        env.pop(k, None)
    out = subprocess.run(["bash", "-c", guard_script()], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert out.returncode == code, out.stdout + out.stderr
    if code:
        assert "재무제표 항목이 없어요" in out.stdout


def test_the_v2_file_is_kept_after_mid_run_fatal_or_down_saves(tmp_path, monkeypatch):
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    for stop in ("fatal", "down", None):
        old = tmp_path / f"dart-v2-{stop}.json.gz"
        write_cache(str(old), KSIC_ONLY, v=2)
        c = F.DartClient("k", today=dt.date(2026, 11, 9), path=str(tmp_path / f"v3-{stop}.json.gz"))
        c.remove_after_save.append(str(old))
        c.save()                                                               # 중간 저장: 지우지 않아요
        assert old.exists()
        if stop == "fatal":
            c.fatal = ("020", "한도 초과")
        elif stop == "down":
            c.down = "ConnectionError"
        c.fetch_done = True
        c.save()
        assert old.exists() == (stop is not None), stop                       # 멈춘 실행은 남겨요 → 다음 실행이 또 옮겨 써요


# ── 5. 관문 새 줄 (더하기만) ───────────────────────────────────────
def test_gate_constants_match_the_pipeline():
    assert V.EPS_OWNERS_MIN == F.EPS_BASIS_MIN * 100
    assert V.STMT_AMT_KEYS == ("evE", "evR", "pcf", "cash3", "eps3r", "epsNi3", "nio3", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep")


def test_gate_recounts_the_owners_share_from_corp(pair):
    cur, prev = pair
    name = "EPS 주주 몫 비율 (corp.json 에서 다시 셈 · o+s)"
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    comps = [c for c in cur["corp"]["companies"] if isinstance(c.get("epsIn"), dict)]
    n_t = len(comps) // 20 + 1                                                 # 5% 넘게 '전체'
    for c in comps[-n_t:]:
        c["epsIn"]["b"] = "t"
    cur["data"]["incCheck"]["epsB"].update(o=len(comps) - n_t, t=n_t)
    assert fails(cur, prev, name)[1].startswith(f"{V.floor_1(100.0 * (len(comps) - n_t) / len(comps))}%")


def test_gate_checks_data_equals_corp_and_per_pbr_from_the_receipts(pair):
    cur, prev = pair
    by = {s["t"]: s for s in cur["data"]["stocks"]}
    same, per_row, sh_row = ("국내 EPS·BPS·PER·PBR·ROE: data.json = corp.json", "PER = 종가 ÷ EPS · PBR = 종가 ÷ BPS (영수증으로)",
                             "EPS·BPS 영수증의 주식 수가 같음 (epsIn.sh = bpsIn.sh)")
    got = rows_of(check(cur, prev))
    assert got[same][3] == got[per_row][3] == got[sh_row][3] == "PASS"
    c = comp(cur, "000270")
    by["000270"]["eps"] = c["eps"] + 1
    assert "000270.eps" in fails(cur, prev, same)[1]
    by["000270"]["eps"] = c["eps"]
    keep = c["per"]
    c["per"] = by["000270"]["per"] = round(keep + 0.2, 1)                     # 반올림보다 큰 차이
    assert "000270 PER" in fails(cur, prev, per_row)[1]
    c["per"] = by["000270"]["per"] = None                                      # EPS 가 0 보다 큰데 PER 없음
    assert "000270 EPS 가 0 보다 큰데 PER 없음" in fails(cur, prev, per_row)[1]
    c["per"] = by["000270"]["per"] = keep
    c["pbr"] = by["000270"]["pbr"] = round(c["pbr"] + 0.02, 2)
    assert "000270 PBR" in fails(cur, prev, per_row)[1]
    c["pbr"] = by["000270"]["pbr"] = round(c["price"] / (c["bpsIn"]["eq"] * 1e8 / c["bpsIn"]["sh"]), 2)
    c["bpsIn"]["sh"] += 1
    fails(cur, prev, sh_row)


def test_gate_warns_when_annual_eps_and_the_statement_eps_disagree(pair):
    cur, prev = pair
    name = "연간 EPS 와 재무제표 기본주당이익 (부호 · 0.67~1.5배 · 경고만)"
    c = comp(cur, "000270")
    c.update(epsFy=4500.0, epsRep=4400.0)
    row = rows_of(check(cur, prev))[name]
    assert row[3] == "PASS" and row[1].startswith("다름 0 / 견준 1")
    c["epsRep"] = 2000.0                                                       # 2.25배
    rep = check(cur, prev)
    assert rows_of(rep)[name][3] == "WARN" and "000270" in rows_of(rep)[name][1] and "우리 4,500 · 재무제표 2,000" in rows_of(rep)[name][1]
    assert not rep.failed
    c["epsRep"] = -100.0                                                       # 부호
    assert rows_of(check(cur, prev))[name][3] == "WARN"
    c["epsRep"] = 0.0                                                          # 재무제표 0 · 우리 4,500 → 부호가 달라요 (배수로는 못 봐요)
    assert rows_of(check(cur, prev))[name][3] == "WARN"
    c["epsRep"] = 3000.0                                                       # 1.5배 → 안
    assert rows_of(check(cur, prev))[name][3] == "PASS"


# ── 6. 이자 지급이 FinanceCostsPaid 코드인 줄 (LG에너지솔루션) ──────────────
def test_interest_paid_coded_as_finance_costs_paid_is_read_when_named_interest():
    out = F.parse_dart_list(rows("373220"))
    assert out["_fin"]["iec"] == 8731.5 and out["_inc"]["iecFcp"] == 1                  # 예전엔 이자 줄 없음 (flWhy ie)
    eq = [r("BS", "자본총계", "ifrs-full_Equity", 4e12), r("CIS", "영업이익", "dart_OperatingIncomeLoss", 1e10)]
    other = eq + [r("CF", "금융원가의 지급", "ifrs-full_FinanceCostsPaidClassifiedAsFinancingActivities", -3e9)]
    assert F.parse_dart_list(other)["_fin"]["iec"] is None                               # 이름이 이자 지급이 아니면 (금융원가 전체) 아니에요


# ── 7. 비지배지분이 없으면 당기순이익 = 지배주주 순이익 (Jack 2026-11-08) ─────────
@pytest.mark.parametrize("t, ni", [("019570", [28.5, -2.1, -115.5]), ("171120", [85.0, 88.2, 70.8])])
def test_no_minority_interest_means_the_whole_profit_is_the_owners(t, ni):
    out = F.parse_dart_list(rows(t))
    assert out["_fin"]["ni"] == ni and out["_fin"]["nio3"] == ni and out["_inc"]["src"]["ni"] == "nci0"
    if t == "019570":                                                          # '비지배지분부채(유동)' 78.9억은 부채 — 비지배지분이 아니에요
        assert F.nci_lines(rows(t), lambda x: F._num(x.get("thstrm_amount")))[0] == [0.0]


# ── 8. 낸 이자가 없으면 이자보상배율 경고 없음 (영업손실이어도 · Jack 2026-11-08) ────
def test_icr_warns_only_when_interest_was_actually_paid(monkeypatch):
    monkeypatch.setattr(F, "ICR_OFF", False)
    assert F.icr_inputs({"op": [-5.0, 0, 0], "ie": 0.0, "iec": 2.0}) == (-5.0, 2.0, "cf", "fy", None)   # 이자비용 0 이어도 낸 이자
    assert F.icr_inputs({"op": [-5.0, 0, 0], "ie": 0.0, "iec": 0.0}) == (-5.0, 0.0, "is", "fy", None)
    assert F.icr_inputs({"op": [-5.0, 0, 0], "iec": 0.0}) == (-5.0, 0.0, "cf", "fy", None)
    base = {"cls": "kr", "price": 1000.0, "cap": 1.0, "shr": 1000, "s": "chem", "ind": "chem"}
    full = {"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0}
    cases = {"000100": dict(full, op=[-5.0, 0, 0], ie=0.0, iec=0.0),      # 영업손실 · 낸 이자 없음
             "000200": dict(full, op=[-5.0, 0, 0], ie=0.0, iec=2.0),      # 영업손실 · 이자 지급 2
             "000300": dict(full, op=[5.0, 0, 0], ie=0.0)}                # 영업이익 · 이자 0
    out = {c["t"]: c for c in F.build_corp([dict(base, t=t, nk=t) for t in cases], cases, "2026-11-08")["companies"]}
    a, b, c = out["000100"], out["000200"], out["000300"]
    assert "fl" not in a and a["flSrc"] == {"icr": "is", "int0": True} and "icr" in a["flRan"] and "flWhy" not in a
    assert b["fl"]["icr"] == -2.5 and b["flSrc"] == {"icr": "cf"}                        # '영업손실이 나서 …' 줄은 그대로
    assert "fl" not in c and c["flSrc"]["int0"] is True


def test_gate_counts_zero_interest_in_the_icr_row(pair):
    cur, prev = pair
    c = comp(cur, "000270")
    c.update(flRan=["cr", "icr", "l3", "imp"], flSrc={"icr": "is", "int0": True})
    assert "낸 이자 0 1" in rows_of(check(cur, prev))["이자보상배율 경고 수 · 쓴 이자 (경고만)"][1]


# ── 2026-11-08: '전체'(t) 회사 중 소수주주(비지배지분)가 있는 곳 — epsIn.nci (앱의 '전체 순이익으로 계산했어요' 줄) ──
def _eps_in(fin, t="000100"):
    s = {"t": t, "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0}
    return F.fill_multiples([s], {t: fin}, {})[t]["epsIn"]


def test_total_basis_with_minority_shareholders_is_marked_nci():
    fy = {"ni": [12.0, None, None], "eq": 200.0, "nciBs": 20.0, "nciPl": None, "fs": "CFS"}
    e = _eps_in(fy)
    assert e["b"] == "t" and e["p"] == "fy" and e["nci"] is True
    fy_pl = {"ni": [12.0, None, None], "eq": 200.0, "nciBs": None, "nciPl": -3.0, "fs": "CFS"}
    assert _eps_in(fy_pl)["nci"] is True
    # TTM 은 최신 분기 재무상태표(bs2)의 증거가 먼저예요: 사업보고서엔 있어도 최신 분기에 비지배지분이 없으면 nci 없음
    ttm = {"ni": [12.0, None, None], "eq": 200.0, "nciBs": 20.0, "nciPl": 1.0, "fs": "CFS",
           "ttm": {"ni": 15.0}, "bs2": {"eq": 210.0, "nciBs": None}}
    e = _eps_in(ttm)
    assert e["b"] == "t" and e["p"] == "ttm" and "nci" not in e
    ttm["bs2"]["nciBs"] = 5.0
    assert _eps_in(ttm)["nci"] is True
    ttm["bs2"] = {"eq": 210.0}                     # 최신 분기에 증거 칸이 없으면 사업보고서 증거
    assert _eps_in(ttm)["nci"] is True


def test_total_basis_from_the_mismatch_guard_without_minority_has_no_nci():
    from test_v191f_owners import annual
    fin = annual("134790")                         # 시디즈: 지배 줄이 당기순이익과 달라 '전체' · 비지배지분 줄은 없음
    assert fin.get("nio") is None and _fin0(fin)
    e = _eps_in(dict(fin, fs="CFS"), "134790")
    assert e["b"] == "t" and "nci" not in e
    zero = {"ni": [12.0, None, None], "eq": 200.0, "nciBs": 0.0, "nciPl": 0.0, "fs": "CFS"}
    assert "nci" not in _eps_in(zero)


def _fin0(fin):
    return not any(F._fin(fin.get(k)) not in (None, 0.0) for k in ("nciBs", "nciPl"))


def test_owners_basis_never_carries_nci():
    fin = {"ni": [12.0, None, None], "nio": 10.0, "eq": 200.0, "nciBs": 20.0, "nciPl": 2.0, "fs": "CFS"}
    e = _eps_in(fin)
    assert e["b"] == "o" and "nci" not in e
    sep = {"ni": [12.0, None, None], "eq": 200.0, "nciBs": 20.0, "fs": "OFS"}
    assert "nci" not in _eps_in(sep)


def test_gate_checks_the_nci_mark_shape(pair):
    cur, prev = pair
    name = "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)"
    c = next(x for x in cur["corp"]["companies"] if isinstance(x.get("epsIn"), dict))
    c["epsIn"]["b"], c["epsIn"]["how"], c["epsIn"]["nci"] = "t", "total", True
    assert rows_of(check(cur, prev))[name][3] == "PASS"
    c["epsIn"]["b"] = "o"
    assert f"{c['t']}.epsIn.nci" in fails(cur, prev, name)[1]
    c["epsIn"]["b"], c["epsIn"]["nci"] = "t", False
    assert f"{c['t']}.epsIn.nci" in fails(cur, prev, name)[1]
    c["epsIn"]["nci"], c["epsIn"]["how"] = True, "hybrid"         # 지배주주 순이익이 있는 "t" (신종자본증권): nci 아님
    assert f"{c['t']}.epsIn.nci" in fails(cur, prev, name)[1]


def test_hybrid_total_basis_with_minority_shareholders_has_no_nci():
    """리뷰 2: eps_source 의 b "t" · how "hybrid" 는 지배주주 순이익이 있어요 (어디 몫인지 모르는 신종자본증권) — 앱의 '지배주주 몫 순이익을
    따로 공시하지 않아' 줄은 틀려요. nci 는 how "total" 에만."""
    fin = {"ni": [12.0], "nio": 10.0, "nciBs": 20.0, "nciPl": 2.0, "fs": "CFS", "hyb": {"dist": 1.0, "ok": False}}
    e = _eps_in(fin)
    assert e["b"] == "t" and e["how"] == "hybrid" and "nci" not in e


def test_ttm_carries_the_quarters_minority_profit_as_evidence():
    """분기 누적 손익의 비지배지분 순이익(nciPl)도 TTM 증거: 최신 분기 재무상태표에 비지배지분 줄이 없어도 손익에 있으면 nci."""
    fin = {"rev": [10.0], "ni": [5.0]}
    q = {"rev": 3.0, "ni": 1.0, "nciPl": 0.4, "nciBs": None}
    t2 = F.compute_ttm(fin, q, dict(q, nciPl=0.2))
    assert t2["ttm"]["nciPl"] == 0.4 and t2["bs"]["nciBs"] is None
    full = {"ni": [5.0, None, None], "eq": 50.0, "fs": "CFS", "nciBs": None, "nciPl": None, "ttm": t2["ttm"], "bs2": t2["bs"]}
    e = _eps_in(full)
    assert e["b"] == "t" and e["p"] == "ttm" and e["nci"] is True
    full["ttm"] = dict(t2["ttm"], nciPl=0.0)
    assert "nci" not in _eps_in(full)
    assert "nciPl" not in F.compute_ttm(fin, {"rev": 3.0, "ni": 1.0}, {"rev": 3.0, "ni": 1.0})["ttm"]



# ── 2026-11-09 full DART dry run (run 42536189571): the gate's three FAIL rows ──
def test_foreign_issuers_with_statements_in_another_currency_carry_no_roe_in_either_file(capsys):
    """원인 1 (영수증 모양 38 · 두 파일 같은 값 19): build_corp 는 stmtCur 회사의 corp.json roe·qz 를 비우는데, blank_non_won 이 해외 기업(9…)을
    건너뛰어 data.json 에 해외 기업 19곳의 roe 와 그 점수 qz 가 남았어요 (예: 950160 코오롱티슈진 roe −303.2)."""
    fin = dict(F.parse_dart_list(USD)["_fin"], fs="CFS")
    s = {"t": "950160", "nk": "코오롱티슈진", "cls": "kr", "price": 30000.0, "shr": 1000, "cap": 1.0, "roe": -303.2}
    plain = {"t": "950250", "nk": "테라뷰", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0, "roe": 3.0}
    fins = {"950160": fin, "950250": {"ni": [5.0, None, None], "eq": 9.0, "fs": "CFS"}}
    F.blank_foreign_dart([s, plain])
    assert F.blank_non_won([s, plain], fins) == []                                  # 국내 회사 목록에는 없어요
    assert "!! 원화가 아닌 재무제표로 낸 해외 기업 1곳" in capsys.readouterr().out
    assert "roe" not in s and plain["roe"] == 3.0                                    # stmtCur 가 없는 해외 기업은 그대로
    extra = F.fill_multiples([s, plain], fins, {})
    F.add_percentiles([s, plain])
    assert "roe" not in s and "qz" not in s
    corp = {c["t"]: c for c in F.build_corp([s, plain], fins, "2026-11-09", extra=extra)["companies"]}
    c = corp["950160"]
    assert c["stmtCur"] == "USD" and not V.stmt_cur_problems(c, s)
    assert all(V.num(s.get(k)) == V.num(c.get(k)) for k in ("eps", "bps", "per", "pbr", "roe"))
