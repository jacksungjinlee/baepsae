# -*- coding: utf-8 -*-
"""v19.1f (2026-11-08): 손익 줄은 DART 표준 계정 코드로 먼저 · EPS·BPS 는 지배주주 몫 · 새 관문 줄. (네트워크 없음)

픽스처 tests/fixtures/dart_income_samples.json 은 2026-11-08 에 DART 에서 받은 실제 재무제표(fnlttSinglAcntAll)의 손익 줄과
자본·부채 줄, 그리고 같은 날 받은 DART 의 정규화된 주요 계정(fnlttMultiAcnt)이에요. 인증키는 응답에 없어요.
주식 수 · 가격은 2026-11-06 종가 기준 발행본(data.json, 2026-11-08 01:49 KST)의 값이에요.
"""
import copy
import datetime as dt
import json
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair, hilo_of  # noqa: E402

with open(os.path.join(ROOT, "tests", "fixtures", "dart_income_samples.json"), encoding="utf-8") as _f:
    FIX = json.load(_f)
ST, MULTI = FIX["statements"], FIX["multi"]


def rows(t, y=2025, r="11011", fs="CFS"):
    return copy.deepcopy(ST[f"{t}|{y}|{r}|{fs}"]["rows"])


def annual(t, fs="CFS"):
    return F.parse_dart_list(rows(t, fs=fs))


def eok(won):
    return round(won / 1e8, 1)


def r(sj, nm, aid, a, b=None, c=None, add=None):
    out = {"sj_div": sj, "account_nm": nm, "account_id": aid, "thstrm_amount": str(a)}
    for k, v in (("frmtrm_amount", b), ("bfefrmtrm_amount", c), ("thstrm_add_amount", add)):
        if v is not None:
            out[k] = str(v)
    return out


NO_ID = "-표준계정코드 미사용-"
BS = [r("BS", "자본총계", "ifrs-full_Equity", 4e12), r("BS", "부채총계", "ifrs-full_Liabilities", 2e12)]


# ── 1. 실제 재무제표: DART 의 정규화된 주요 계정과 같아요 ─────────────
@pytest.mark.parametrize("key", sorted(k for k in ST if k.endswith("|2025|11011|CFS") or k.endswith("|2025|11011|OFS")))
def test_every_sampled_annual_statement_matches_darts_own_main_accounts(key):
    t, _, _, fs = key.split("|")
    fin = annual(t, fs)["_fin"]
    want = MULTI[f"{t}|{fs}"]
    for k in ("rev", "op", "ni"):
        if k in want:
            assert fin[k][0] == eok(want[k]), (key, k)
        else:
            assert fin[k][0] is None, (key, k)          # 금융회사: DART 에도 매출 줄이 없어요 (지어내지 않아요)


def test_numbered_and_variant_names_from_the_audit():
    g = annual("010130")["_fin"]                                  # 고려아연: 'Ⅴ.영업이익' · 'XI. 당기순이익'
    assert (g["op"][0], g["ni"][0]) == (12319.3, 7702.5)
    k = annual("120110")["_fin"]                                  # 코오롱인더: 'I. 매출' · 'V. 영업이익' · 'X. 당기순이익'
    assert (k["rev"][0], k["op"][0], k["ni"][0]) == (48734.0, 1089.0, 515.7)
    n = annual("251270")["_fin"]                                  # 넷마블: 'Ⅰ.영업수익' · 'Ⅲ.영업손익' · '당기순손익'
    assert (n["rev"][0], n["op"][0], n["ni"][0]) == (28350.7, 3524.8, 2308.2)
    lc = annual("011170")["_fin"]                                 # 롯데케미칼: '매출' · '영업손실' · '당기순손실' (음수)
    assert (lc["rev"][0], lc["op"][0], lc["ni"][0]) == (184830.1, -9431.2, -24761.8)
    sdi = annual("006400")["_fin"]                                # 삼성SDI: '영업손익' · '당기순손익'
    assert (sdi["op"][0], sdi["ni"][0]) == (-17223.6, -5848.8)
    assert annual("003550")["_fin"]["rev"][0] == 72525.5          # LG: '매출및지분법손익'
    ha = annual("012450")                                         # 한화에어로스페이스: '매출'
    assert ha["_fin"]["rev"][0] == 267029.0 and ha["_inc"]["src"] == {"rev": "id", "op": "id", "ni": "id", "nio": "code"}
    kb = annual("323410", "OFS")["_fin"]                          # 카카오뱅크 (별도만): 'I. 영업수익' · 'IV. 영업이익' · 'IX. 당기순이익'
    assert (kb["rev"][0], kb["op"][0], kb["ni"][0]) == (30862.9, 6493.7, 4802.8)


def test_old_name_rule_differences_are_recorded():
    # 예전 규칙이 읽던 값과 다르면 _inc.old 에 남겨요 (시험 실행 로그에서 확인). 예전에 못 찾던 줄은 '다름'이 아니에요
    out = F.parse_dart_list(BS + [r("IS", "매출액", "ifrs-full_RevenueFromSaleOfGoods", 3e10), r("IS", "수익", "ifrs-full_Revenue", 9e10)])
    assert out["_fin"]["rev"][0] == 900.0 and out["_inc"]["old"] == ["rev"]
    assert "old" not in annual("011170")["_inc"]                  # 롯데케미칼은 예전에 아무것도 못 읽었어요


# ── 2. 코드 · 이름 규칙 ────────────────────────────────────────
def test_names_are_used_only_when_no_line_carries_the_code():
    rows_ = BS + [r("CIS", "Ⅲ.영업손익", NO_ID, -2e9, -1e9, 5e8), r("CIS", "I. 매출", NO_ID, 1e11),
                  r("CIS", "XII. 당기순손실", NO_ID, -3e9), r("CIS", "지배기업 소유주지분 순손실", NO_ID, -2.5e9),
                  r("CIS", "비지배지분", NO_ID, -0.5e9),
                  r("CIS", "지배기업의 소유주", "ifrs-full_ComprehensiveIncomeAttributableToOwnersOfParent", 7e9)]
    out = F.parse_dart_list(rows_)
    fin = out["_fin"]
    assert fin["op"] == [-20.0, -10.0, 5.0] and fin["rev"][0] == 1000.0 and fin["ni"][0] == -30.0
    assert fin["nio"] == -25.0 and fin["nio3"] == [-25.0, None, None]       # −25 + 비지배 −5 = −30 (sum) · 총포괄손익 줄은 아니에요
    assert out["_inc"]["src"] == {"rev": "name", "op": "name", "ni": "name", "nio": "sum"} and fin["nioHow"] == "sum"


def test_owners_line_by_name_never_takes_comprehensive_or_continuing_lines():
    rows_ = BS + [r("CIS", "매출", "ifrs-full_Revenue", 1e11), r("CIS", "당기순이익", "ifrs-full_ProfitLoss", 5e9),
                  r("CIS", "지배기업 소유주지분 총포괄이익", NO_ID, 8e9), r("CIS", "계속영업 지배기업 순이익", NO_ID, 6e9),
                  r("CIS", "비지배지분 순이익", NO_ID, 1e9)]
    fin = F.parse_dart_list(rows_)["_fin"]
    assert fin["nio"] == 40.0 and fin["nioHow"] == "minus"                # 포괄 · 계속영업 줄이 아니라 당기순이익 5 − 비지배 1
    no_nci = [r_ for r_ in rows_ if "비지배" not in r_["account_nm"]]
    assert F.parse_dart_list(no_nci)["_fin"]["nio"] is None                # 맞지 않는 '지배' 줄이 있으면 nci0 로 보지 않아요 (전체 · t)


def test_the_income_statement_wins_over_the_comprehensive_one_and_equal_lines_count_once():
    rows_ = BS + [r("CIS", "당기순이익", "ifrs-full_ProfitLoss", 5e9), r("IS", "당기순이익", "ifrs-full_ProfitLoss", 5e9),
                  r("IS", "매출액", "ifrs-full_Revenue", 1e11), r("IS", "매출액", "ifrs-full_Revenue", 1e11)]
    fin = F.parse_dart_list(rows_)["_fin"]
    assert fin["ni"][0] == 50.0 and fin["rev"][0] == 1000.0


def test_several_different_coded_lines_pick_the_total_by_name_or_none():
    two = [r("IS", "매출액", "ifrs-full_Revenue", 1e11), r("IS", "제품매출", "ifrs-full_Revenue", 6e10)]
    assert F.parse_dart_list(BS + two)["_fin"]["rev"][0] == 1000.0        # 이름이 매출 총계인 줄 하나
    before = F.INC_SEEN["rev:many"]
    bad = [r("IS", "제품매출", "ifrs-full_Revenue", 4e10), r("IS", "상품매출", "ifrs-full_Revenue", 6e10)]
    assert F.parse_dart_list(BS + bad)["_fin"]["rev"][0] is None and F.INC_SEEN["rev:many"] == before + 1


def test_operating_income_code_order_and_financial_companies():
    rows_ = BS + [r("CIS", "영업이익", "ifrs-full_ProfitLossFromOperatingActivities", 7e9),
                  r("CIS", "영업이익(손실)", "dart_OperatingIncomeLoss", 6e9)]
    assert F.parse_dart_list(rows_)["_fin"]["op"][0] == 60.0              # dart_OperatingIncomeLoss 먼저
    for t in ("105560", "032830", "016360"):                              # KB금융 · 삼성생명 · 삼성증권: 매출 줄 없음, 영업이익·순이익 있음
        fin = annual(t)["_fin"]
        assert fin["rev"][0] is None and fin["op"][0] is not None and fin["ni"][0] is not None


# ── 3. 재무상태표는 손익 줄이 없어도 남아요 ─────────────────────
def test_balance_sheet_is_kept_when_no_income_line_is_read():
    rows_ = BS + [r("BS", "지배기업 소유주지분", "ifrs-full_EquityAttributableToOwnersOfParent", 3.5e12),
                  r("BS", "유동자산", "ifrs-full_CurrentAssets", 1e12), r("CIS", "기타수익", "dart_OtherGains", 1e9)]
    out = F.parse_dart_list(rows_)
    assert out["_fin"]["eq"] == 40000.0 and out["_fin"]["eqo"] == 35000.0 and out["debt"] == 50.0
    assert out["_fin"]["rev"] == out["_fin"]["op"] == out["_fin"]["ni"] == [None, None, None]
    q = F.parse_dart_quarter(rows_)
    assert q is not None and q["eq"] == 40000.0 and q["eqo"] == 35000.0 and q["rev"] is None
    assert F.compute_ttm({"rev": [1.0], "ni": [1.0]}, q, q) is None      # 손익이 없는 분기로는 TTM 을 만들지 않아요
    cap_only = F.parse_dart_list([r("BS", "자본금", "ifrs-full_IssuedCapital", 1e10)])
    assert "_fin" not in cap_only                                         # 자본금만 있는 표는 예전처럼 '못 찾음'


class FakeDart:
    def __init__(self, by):
        self.by, self.calls = by, []

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        self.calls.append((year, reprt, tag))
        rows_ = self.by.get((year, reprt, tag))
        return parse(rows_) if rows_ is not None else None


def test_quarters_use_the_same_kind_of_statement_as_the_annual_report():
    q = [r("IS", "매출액", "ifrs-full_Revenue", 1e10, add=3e10)] + BS
    c = FakeDart({(2026, "11012", "OFS"): q})
    assert F.dart_quarter(c, "C", 2026, "11012", fs="CFS") is None and c.calls == [(2026, "11012", "CFS")]
    assert F.dart_quarter(c, "C", 2026, "11012", fs="OFS")["rev"] == 300.0
    assert F.dart_quarter(c, "C", 2026, "11012")["rev"] == 300.0          # 종류를 모를 때(분기 판단)는 예전처럼 연결 → 별도
    d = F.dart_financials(FakeDart({(2025, "11011", "OFS"): q}), "C", 2025)
    assert d["_fin"]["fs"] == "OFS" and "_inc" in d


# ── 4. 반기 이름 · TTM · 지배주주 EPS (실제 회사) ───────────────
def test_half_year_names_are_read():
    h = F.parse_dart_quarter(rows("005380", 2026, "11012"))              # 현대차 '연결반기순이익' · '지배기업소유주지분'
    assert h["ni"] is not None and h["nio"] is not None and h["rev"] is not None
    lg = F.parse_dart_quarter(rows("373220", 2026, "11012"))             # LG에너지솔루션 '매출액 및 기타수익' · '반기순이익(손실)'
    assert (lg["rev"], lg["ni"], lg["nio"]) == (eok(14115216000000), eok(-1272678000000), eok(-1053435000000))
    sdi = F.parse_dart_quarter(rows("006400", 2026, "11012"))            # 삼성SDI '영업손익' · '반기순손익'
    assert sdi["op"] is not None and sdi["ni"] is not None
    lc = F.parse_dart_quarter(rows("011170", 2026, "11012"))             # 롯데케미칼 '매출' · '영업손익' · '반기순손익'
    assert lc["rev"] is not None and lc["op"] is not None and lc["ni"] is not None


# 2026-11-06 종가 · 상장 주식 수 (data.json 2026-11-08 발행본): 보통주, 같은 회사 상장 우선주
SHARES = {"005930": (188700.0, 5846278608, [802371203]), "005380": (279500.0, 203466492, [22839037, 34257047, 2321926]),
          "373220": (337500.0, 234000000, []), "012450": (660000.0, 51563401, []), "105560": (151000.0, 354687734, []),
          "323410": (20750.0, 477120437, [])}


def eps_case(t, fs="CFS"):
    fin = annual(t, fs)["_fin"]
    fin["fs"] = fs
    t2 = F.compute_ttm(fin, F.parse_dart_quarter(rows(t, 2026, "11012", fs)), F.parse_dart_quarter(rows(t, 2025, "11012", fs)))
    fin["ttm"], fin["bs2"], fin["bq"] = t2["ttm"], t2["bs"], "2026.2Q"
    price, shr, pref = SHARES[t]
    s = {"t": t, "nk": ST[f"{t}|2025|11011|{fs}"]["name"], "cls": "kr", "price": price, "shr": shr, "cap": 1.0}
    extra = F.fill_multiples([s], {t: fin}, {t[:5]: pref} if pref else {})
    return s, extra[t], fin


def test_lg_energy_solution_eps_follows_the_shareholders_loss():
    s, e, fin = eps_case("373220")
    # 예전: EPS +345 · PER 977 (전체 순이익 808억 ÷ 주식 수). 주주 몫은 손실이에요 (2025 회사 발표 EPS −4,585)
    assert fin["nio"] == -10728.1 and fin["ni"][0] == 808.0
    assert e["epsIn"] == {"ni": -16830.6, "b": "o", "p": "ttm", "sh": 234000000, "how": "code"}
    assert s["eps"] == -7193.0 and s.get("per") is None                  # 손실이면 PER 은 빈 칸
    assert s["eps"] < 0 and math.copysign(1, s["eps"]) == math.copysign(1, -4585)


def test_hyundai_eps_is_owners_ttm_over_all_listed_shares():
    s, e, fin = eps_case("005380")
    # 예전: EPS 50,941 = 2025 전체 순이익 ÷ 보통주 (TTM '2026.2Q' 라고 적혀 있었어요: 반기 '연결반기순이익'을 못 읽어서)
    assert e["epsIn"]["b"] == "o" and e["epsIn"]["p"] == "ttm" and e["epsIn"]["sh"] == 203466492 + 22839037 + 34257047 + 2321926
    assert s["eps"] == 30989.0 and s["per"] == 9.0 and e["bpsIn"]["b"] == "o"


def test_samsung_and_hanwha_aerospace_use_owners_profit_and_equity():
    s, e, _ = eps_case("005930")
    assert (s["eps"], s["per"], s["bps"], s["pbr"]) == (22511.0, 8.4, 84989.0, 2.22)   # 예전 25,780 · 7.3 · 99,090 · 1.9
    assert e["epsIn"]["sh"] == 5846278608 + 802371203
    h, he, hf = eps_case("012450")
    assert hf["eqo"] == 96849.1 and hf["eq"] == 167881.8                  # 지배주주 자본 9.7조 vs 전체 16.8조
    assert he["epsIn"] == {"ni": 20161.4, "b": "o", "p": "ttm", "sh": 51563401, "how": "code"} and h["eps"] == 39100.0   # 예전 64,251


def test_separate_statements_use_their_whole_profit():
    s, e, _ = eps_case("323410", "OFS")                                    # 카카오뱅크 (별도만): 비지배지분이 없어 전체 = 주주 몫
    assert e["epsIn"]["b"] == "s" and e["bpsIn"]["b"] == "s" and s["eps"] == 1142.0


def test_eps_source_order():
    base = {"ni": [10.0, None, None], "fs": "CFS"}
    assert F.eps_source(dict(base, nio=8.0, nioHow="code", ttm={"nio": 9.0, "ni": 12.0, "nioHow": "code+nci0"})) == \
        (9.0, "o", "ttm", "code+nci0", 0.0)
    assert F.eps_source(dict(base, nio=8.0, nioHow="alt", ttm={"ni": 12.0})) == (8.0, "o", "fy", "alt", 0.0)   # 기간보다 주주 몫이 먼저
    assert F.eps_source(dict(base, ttm={"ni": 12.0})) == (12.0, "t", "ttm", "total", 0.0)         # 지배주주 줄이 없는 연결
    assert F.eps_source(dict(base, fs="OFS", nio=8.0, ttm={"ni": 12.0})) == (12.0, "s", "ttm", "ofs", 0.0)
    assert F.eps_source({"ni": [float("nan"), None, None]}) is None                        # NaN 은 숫자로 안 써요
    assert F.bps_source({"eq": 9.0, "eqo": 7.0, "bs2": {"eq": 10.0}, "fs": "CFS"}) == (7.0, "o", "code", "fy", 0.0)
    assert F.bps_source({"eq": 9.0, "eqo": 7.0, "fs": "OFS"}) == (9.0, "s", "ofs", "fy", 0.0)
    assert F.bps_source({"eq": 9.0, "nciBs": None, "fs": "CFS"}) == (9.0, "o", "nci0", "fy", 0.0)    # 비지배지분 줄 없음
    assert F.bps_source({"eq": 9.0, "nciBs": 0.5, "fs": "CFS"}) == (9.0, "t", "total", "fy", 0.0)     # 비지배지분이 있으면 아니에요
    assert F.bps_source({"eq": 9.0, "fs": "CFS"}) == (9.0, "t", "total", "fy", 0.0)                   # 증거가 없으면(예전 캐시) 아니에요


def test_share_count_switch(monkeypatch):
    s = {"t": "005930", "shr": 100}
    assert F.per_share_count(s, {"00593": [30, float("nan")]}) == 130
    monkeypatch.setattr(F, "PER_SHARE_WITH_PREF", False)
    assert F.per_share_count(s, {"00593": [30]}) == 100


def test_nan_amounts_never_reach_the_files():
    rows_ = BS + [r("IS", "매출액", "ifrs-full_Revenue", "NaN", "Infinity", "-"), r("IS", "당기순이익", "ifrs-full_ProfitLoss", "nan"),
                  r("IS", "지배기업 소유주지분", "ifrs-full_ProfitLossAttributableToOwnersOfParent", "")]
    out = F.parse_dart_list(rows_)
    json.dumps(out, allow_nan=False)
    q = F.parse_dart_quarter([dict(x, thstrm_add_amount="NaN") for x in rows_])
    json.dumps(q, allow_nan=False)
    s = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0}
    extra = F.fill_multiples([s], {"000100": dict(out["_fin"], fs="CFS", ttm={"nio": float("nan")})}, {})
    json.dumps([s, extra], allow_nan=False)
    assert "eps" not in s and s["bps"] == 4e12 / 1000                     # 순이익이 없으면 EPS 도 없어요 (자본으로 BPS 는 있어요)


# ── 5. corp.json: nio3 · incNa · 영수증 · 회사 시가총액 ─────────────
def corp_of(stocks, fin, extra=None):
    return {c["t"]: c for c in F.build_corp(stocks, fin, "2026-11-08", extra=extra)["companies"]}


def test_corp_json_carries_owners_profit_receipts_and_says_why_revenue_is_missing():
    kb = annual("105560")["_fin"]
    bank = {"t": "105560", "nk": "KB금융", "cls": "kr", "price": 151000.0, "cap": 53.558, "shr": 354687734, "s": "bank", "ind": "bank"}
    chem = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "cap": 1.0, "shr": 1000, "s": "chem", "ind": "chem"}
    c = corp_of([bank, chem], {"105560": kb, "000100": {"rev": [None] * 3, "ni": [1.0] * 3, "eq": 5.0}},
                {"105560": {"epsIn": {"ni": 1.0, "b": "o", "p": "fy", "sh": 1}}})
    assert c["105560"]["incNa"] == ["rev"] and c["105560"]["nio3"][0] == 58331.6 and c["105560"]["epsIn"]["b"] == "o"
    assert "incNa" not in c["000100"]                                      # 금융이 아닌 회사의 빈 매출은 '없는 줄'이 아니에요 (관문이 봐요)
    foreign = dict(chem, t="900100")
    c = corp_of([foreign], {"900100": dict(kb)}, {"900100": {"epsIn": {"ni": 1.0, "b": "o", "p": "fy", "sh": 1}}})
    assert not {"nio3", "epsIn", "bpsIn"} & set(c["900100"])               # 해외 기업 금액은 비워요


def test_ev_uses_the_whole_company_market_cap(monkeypatch):
    com = {"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 100.0, "cap": 10.0, "shr": 1, "s": "semi"}
    pref = {"t": "005935", "nk": "삼성전자우", "cls": "kr", "price": 80.0, "cap": 2.0, "shr": 1, "s": "semi"}
    fin = {"005930": {"rev": [100000.0, None, None], "op": [10.0, None, None], "ni": [1.0] * 3, "dep": 0.0, "bor": 0.0, "cash": 0.0,
                      "ocf": 120000.0}}
    c = corp_of([com, pref], fin)["005930"]
    assert c["evR"] == 1.2 and c["pcf"] == 1.0                             # (10 + 2)조 ÷ 10조 매출 · 12조 ÷ 12조
    monkeypatch.setattr(F, "COMPANY_CAP_WITH_PREF", False)
    c = corp_of([com, pref], fin)["005930"]
    assert c["evR"] == 1.0                                                 # 보통주만 (v19.1f 전)


def test_pipeline_writes_the_eps_basis_marker_and_income_check():
    import inspect
    src = inspect.getsource(F.main)
    assert '"epsBasis": eps_basis' in src and '"incCheck": inc_check' in src and '"epsBasis": eps_basis})' in src
    assert src.find("eps_basis, eps_why = eps_basis_of(kr, mult_extra)") < src.find("write_json(OUT, payload)")
    assert F.EPS_BASIS == "owners"
    i = src.find("fill_multiples(kr, fin_map, kmeta.get(\"_prefShares\")")
    assert 0 < i < src.find("income_check(kr, fin_map, mult_extra)") < src.find("write_json(OUT, payload)")
    kr = [{"t": "000100", "cls": "kr", "s": "bank", "ind": "bank"}, {"t": "000200", "cls": "kr"}, {"t": "900300", "cls": "kr"}]
    fin = {"000100": {"rev": [None] * 3, "op": [1.0] * 3, "ni": [1.0] * 3}, "000200": {"rev": [None] * 3, "eq": 1.0},
           "900300": {"rev": [None] * 3}}
    ic = F.income_check(kr, fin, {"000100": {"epsIn": {"b": "o", "p": "ttm"}}})
    assert ic == {"v": 1, "stmts": 2, "noInc": 1, "finNoRev": 1, "epsB": {"o": 1, "s": 0, "t": 0}, "epsP": {"ttm": 1, "fy": 0}}


def test_income_log_names_statements_without_any_income_line(capsys):
    got = F.income_log({"000100": ("가", {"src": {}}, True), "000200": ("나", {"src": {"rev": "id", "op": "name"}, "old": ["rev"]}, True)})
    out = capsys.readouterr().out
    assert got == ["000100 가"] and "!! 재무제표는 있는데 매출·영업이익·순이익을 하나도 못 읽은 곳: 1 (000100 가)" in out
    assert "!! v19.1f 전 이름 규칙과 올해 값이 다른 손익 줄: 1 · 매출 1곳 (000200 나)" in out


# ── 6. 관문 새 줄 ─────────────────────────────────────────────
TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)
SESSIONS = {"dates": [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)], "src": "시험"}
NEW_ROWS = ("손익 줄 검사 기록 (incCheck)", "EPS 기준 표시 (epsBasis = owners)", "국내 손익 줄 채움 — 시총 상위 200 (매출은 금융회사 빼고)",
            "필수 종목 손익 3줄 (매출·영업이익·순이익)", "재무제표는 있는데 손익 줄을 하나도 못 읽은 회사",
            "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)", "필수 종목 EPS = 지배주주 순이익 (부호 같음)",
            "EPS 기준이 다른 회사 (상위 200 연결 전체 순이익 · TTM 표시인데 연간)", "incCheck 집계 = corp.json 영수증 수")


def with_income(files):
    """좋은 픽스처에 v19.1f 칸을 파이프라인과 같은 규칙으로: 손익 3줄 · 지배주주 EPS 영수증 · incCheck · epsBasis."""
    data, corp = files["data"], files["corp"]
    by = {s["t"]: s for s in data["stocks"]}
    for c in corp["companies"]:
        s = by[c["t"]]
        c.update(rev=[1000.0, 900.0, 800.0], ni=[50.0, 40.0, 30.0], eq=500.0, debt=50.0, nio3=[45.0, 36.0, 27.0])
        sh = 1_000_000
        ni = 45.0 * (1 if c["t"] != "000660" else 2)
        s["eps"] = c["eps"] = round(ni * 1e8 / sh, 0)
        c["epsIn"] = {"ni": ni, "b": "o", "p": "ttm" if c.get("bq") else "fy", "sh": sh}
        c["bps"] = s["bps"] = round(500.0 * 1e8 / sh, 0)
        c["bpsIn"] = {"eq": 500.0, "b": "o", "sh": sh, "p": "ttm" if c.get("bq") else "fy"}
        # 리뷰 2026-11-08 새 줄: PER·PBR = 종가 ÷ 영수증 · data.json = corp.json (파이프라인처럼 같은 값)
        s["per"] = c["per"] = round(s["price"] / (ni * 1e8 / sh), 1)
        s["pbr"] = c["pbr"] = round(s["price"] / (500.0 * 1e8 / sh), 2)
        c["roeIn"] = {"ni": ni, "eq": 500.0, "b": "o", "p": "fy"}            # ROE 도 같은 주주 몫 (사업보고서)
        s["roe"] = c["roe"] = round(ni / 500.0 * 100, 1)
        if c["t"] == "105560":
            c["rev"] = [None, None, None]
            c["incNa"] = ["rev"]
    data["incCheck"] = {"v": 1, "stmts": len(corp["companies"]), "noInc": 0, "finNoRev": 1,
                        "epsB": {"o": len(corp["companies"]), "s": 0, "t": 0},
                        "epsP": {"ttm": sum(1 for c in corp["companies"] if c.get("bq")),
                                 "fy": sum(1 for c in corp["companies"] if not c.get("bq"))}}
    data["epsBasis"] = corp["epsBasis"] = "owners"
    return files


def check(cur, prev, mode="publish"):
    final = {"date": dt.date(2026, 10, 30), "closes": {s["t"]: round(s["price"]) for s in cur["data"]["stocks"] if s.get("cls") == "kr"},
             "how": "시험"}
    return V.run_checks(cur, prev, final, TODAY, mode=mode, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                        hilo=hilo_of(cur, V.MUST))


def rows_of(rep):
    return {x[0]: x for x in rep.rows}


@pytest.fixture
def pair():
    cur, prev, _ = good_pair()
    return with_income(cur), prev


def comp(files, t):
    return next(c for c in files["corp"]["companies"] if c["t"] == t)


def fails(cur, prev, name):
    rep = check(cur, prev)
    assert name in {x[0] for x in rep.failed}, rep.table()
    return rows_of(rep)[name]


def test_good_income_fields_pass_every_new_row(pair):
    cur, prev = pair
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    got = rows_of(rep)
    assert all(got[n][3] == "PASS" for n in NEW_ROWS), [got[n] for n in NEW_ROWS if got[n][3] != "PASS"]
    assert not check(cur, None, mode="live").failed


def test_data_before_v191f_is_only_a_warning_until_the_new_fields_were_published(pair):
    cur, prev = pair
    old, _, _ = good_pair()
    rep = check(old, prev)
    assert not rep.failed and rows_of(rep)["손익 줄 검사 기록 (incCheck)"][3] == "WARN"
    assert not any(n in rows_of(rep) for n in NEW_ROWS[1:])
    rep = check(old, {"data": cur["data"]})                              # 한 번 발행된 뒤 빠지면 실패
    assert "손익 줄 검사 기록 (incCheck)" in {x[0] for x in rep.failed}


@pytest.mark.parametrize("where", ["data", "corp"])
def test_missing_eps_basis_marker_fails(pair, where):
    cur, prev = pair
    cur[where].pop("epsBasis")
    fails(cur, prev, "EPS 기준 표시 (epsBasis = owners)")


def test_hanwha_aerospace_without_revenue_fails_and_the_re_read_fixes_it(pair):
    cur, prev = pair
    c = comp(cur, "012450")
    c["rev"] = [None, None, None]                                          # 2026-11-08 발행본 그대로: '매출' 이름을 못 읽음
    assert "012450" in fails(cur, prev, "필수 종목 손익 3줄 (매출·영업이익·순이익)")[1]
    fin = annual("012450")["_fin"]                                         # 새 규칙으로 실제 재무제표를 읽으면
    c.update(rev=fin["rev"], op=fin["op"], ni=fin["ni"])
    assert rows_of(check(cur, prev))["필수 종목 손익 3줄 (매출·영업이익·순이익)"][3] == "PASS"


def test_a_bank_without_revenue_is_not_a_must_have_failure(pair):
    cur, prev = pair
    assert comp(cur, "105560")["rev"] == [None, None, None]
    assert rows_of(check(cur, prev))["필수 종목 손익 3줄 (매출·영업이익·순이익)"][3] == "PASS"
    comp(cur, "105560")["ni"] = [None, 1.0, 1.0]
    assert "105560" in fails(cur, prev, "필수 종목 손익 3줄 (매출·영업이익·순이익)")[1]


def test_coverage_is_a_warning_now_and_fails_below_the_floor_once_set(pair, monkeypatch):
    cur, prev = pair
    top = sorted((c for c in cur["corp"]["companies"] if c["t"] not in V.MUST), key=lambda c: -c["cap"])[:20]
    for c in top:
        c["op"] = [None, 1.0, 1.0]
    name = "국내 손익 줄 채움 — 시총 상위 200 (매출은 금융회사 빼고)"
    assert V.INC_TOP_FLOOR_APPROVED == 98.0                                # Jack 2026-11-08 (4월 확인을 기다려요 — 아직 꺼 둠)
    monkeypatch.setattr(V, "INC_TOP_FLOOR", None)                          # 꺼져 있는 동안: 경고만
    row = rows_of(check(cur, prev))[name]
    assert row[3] == "WARN" and "영업이익 90.0% (180/200)" in row[1] and "4월 확인을 기다려요" in row[2]
    monkeypatch.setattr(V, "INC_TOP_FLOOR", V.INC_TOP_FLOOR_APPROVED)      # 켜면
    assert "영업이익 90.0% (180/200)" in fails(cur, prev, name)[1]          # 98% 미만 → 발행을 막아요
    for c in top[:17]:
        c["op"] = [1.0, 1.0, 1.0]
    row = rows_of(check(cur, prev))[name]
    assert row[3] == "WARN" and "영업이익 98.5% (197/200)" in row[1]        # 98% 이상이지만 100% 아님 → 경고 (이름과 함께)
    top[16]["op"] = [None, 1.0, 1.0]
    top[15]["op"] = [None, 1.0, 1.0]
    assert "영업이익 97.5% (195/200)" in fails(cur, prev, name)[1]
    monkeypatch.setattr(V, "INC_TOP_FLOOR", 90.0)
    assert rows_of(check(cur, prev))[name][3] == "WARN"


def test_statements_without_any_income_line_are_named(pair):
    cur, prev = pair
    c = comp(cur, "200100")
    c.update(rev=[None] * 3, op=[None] * 3, ni=[None] * 3)
    rep = check(cur, prev)
    row = rows_of(rep)["재무제표는 있는데 손익 줄을 하나도 못 읽은 회사"]
    assert row[3] == "WARN" and "200100" in row[1] and not rep.failed


@pytest.mark.parametrize("change, said", [
    (lambda c: c["epsIn"].update(b="t"), "전체 순이익"),                                  # 연결인데 전체 순이익 (지배주주 아님)
    (lambda c: c["epsIn"].update(ni=-c["epsIn"]["ni"]), None),                            # 부호가 다름 (영수증 모양 줄도 실패)
    (lambda c: c.pop("epsIn"), "영수증 없음"),
    (lambda c: (c["epsIn"].update(p="fy"), c.update(eps3r=[-100.0, 1.0, 1.0])), "회사 발표 EPS"),
])
def test_must_have_eps_must_be_the_owners_profit(pair, change, said):
    cur, prev = pair
    change(comp(cur, "005930"))
    row = fails(cur, prev, "필수 종목 EPS = 지배주주 순이익 (부호 같음)")
    assert "005930" in row[1] and (said is None or said in row[1])


def test_must_have_eps_must_match_data_json(pair):
    cur, prev = pair
    next(s for s in cur["data"]["stocks"] if s["t"] == "005380")["eps"] = 1.0
    assert "data.json eps" in fails(cur, prev, "필수 종목 EPS = 지배주주 순이익 (부호 같음)")[1]


@pytest.mark.parametrize("change", [
    lambda c: c.update(eps=c["eps"] + 5),                                  # EPS ≠ 순이익 ÷ 주식 수
    lambda c: c["epsIn"].update(sh=0),
    lambda c: c["bpsIn"].update(eq=-1.0),
    lambda c: c.update(nio3=[1.0, "x"]),
    lambda c: c.update(incNa=["op"]),
    lambda c: c["epsIn"].update(b="owners"),
    lambda c: c["bpsIn"].update(p="2026.2Q"),                             # 자본의 시점은 ttm · fy 만 (리뷰 2026-11-08)
    lambda c: c["bpsIn"].pop("p"),
])
def test_receipt_shape_problems_fail(pair, change):
    cur, prev = pair
    change(comp(cur, "200200"))
    fails(cur, prev, "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)")


def test_foreign_issuer_with_receipts_fails(pair):
    cur, prev = pair
    c = comp(cur, "200200")
    c["t"] = "950999"
    next(s for s in cur["data"]["stocks"] if s["t"] == "200200")["t"] = "950999"
    assert "950999" in fails(cur, prev, "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)")[1]


def test_eps_basis_differences_are_a_named_warning(pair):
    cur, prev = pair
    c = next(c for c in cur["corp"]["companies"] if c.get("bq") and c["t"] not in V.MUST)
    c["epsIn"]["p"] = "fy"
    cur["data"]["incCheck"]["epsP"] = {"ttm": cur["data"]["incCheck"]["epsP"]["ttm"] - 1, "fy": cur["data"]["incCheck"]["epsP"]["fy"] + 1}
    rep = check(cur, prev)
    row = rows_of(rep)["EPS 기준이 다른 회사 (상위 200 연결 전체 순이익 · TTM 표시인데 연간)"]
    assert row[3] == "WARN" and "TTM 표시인데 연간 1" in row[1] and not rep.failed


def test_income_check_counts_must_match_the_receipts(pair):
    cur, prev = pair
    cur["data"]["incCheck"]["epsB"]["o"] += 1
    fails(cur, prev, "incCheck 집계 = corp.json 영수증 수")


def test_wrong_income_check_version_fails(pair):
    cur, prev = pair
    cur["data"]["incCheck"]["v"] = 2
    fails(cur, prev, "손익 줄 검사 기록 (incCheck)")


# ── 7. 리뷰 고침 (2026-11-08) ─────────────────────────────────
def test_loss_first_names_with_a_positive_figure_are_dropped():
    before_op, before_ni = F.INC_SEEN["op:sign"], F.INC_SEEN["ni:sign"]
    rows_ = BS + [r("CIS", "영업손실(이익)", NO_ID, 5e9), r("CIS", "당기순손실(이익)", NO_ID, 7e9), r("CIS", "매출", NO_ID, 1e11)]
    fin = F.parse_dart_list(rows_)["_fin"]
    assert fin["op"] == [None, None, None] and fin["ni"] == [None, None, None] and fin["rev"][0] == 1000.0
    assert F.INC_SEEN["op:sign"] == before_op + 1 and F.INC_SEEN["ni:sign"] == before_ni + 1
    ok = F.parse_dart_list(BS + [r("CIS", "영업손실(이익)", NO_ID, -5e9), r("CIS", "반기순손실(이익)", NO_ID, -7e9)])["_fin"]
    assert ok["op"][0] == -50.0 and ok["ni"][0] == -70.0                     # 음수면 그대로 손실
    q = F.parse_dart_quarter(BS + [r("IS", "매출액", NO_ID, 1e10, add=3e10), r("IS", "분기순손실(이익)", NO_ID, 1e9, add=2e9)])
    assert q["ni"] is None


def test_interest_paid_names_need_interest_before_paid_and_never_add_to_a_coded_line():
    base = BS + [r("IS", "매출액", "ifrs-full_Revenue", 1e11)]
    coded = r("CF", "이자의 지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -3e9)
    assert F.parse_dart_list(base + [coded, r("CF", "지급이자", NO_ID, 3e9)])["_fin"]["iec"] == 30.0     # 예전엔 60
    assert F.parse_dart_list(base + [coded, r("CF", "이자의지급", NO_ID, -1e9)])["_fin"]["iec"] == 30.0  # 코드 줄이 있으면 이름 줄은 안 더해요
    loose = [r("CF", "지급이자", NO_ID, 3e9), r("CF", "미지급이자의 증가(감소)", NO_ID, 1e9), r("CF", "이자지급액의 미지급", NO_ID, 4e9)]
    assert F.parse_dart_list(base + loose)["_fin"]["iec"] is None                                       # 간접법 조정 · 운전자본 줄
    ok = [r("CF", "차입원가 자본화 이자의 지급", NO_ID, -2e9), r("CF", "이자 납부", NO_ID, -1e9)]
    assert F.parse_dart_list(base + ok)["_fin"]["iec"] == 30.0                                          # 코드 줄이 없을 때만 이름으로


def test_eps_basis_marker_is_owners_only_when_the_run_really_used_owners_profit():
    kr = [{"t": t, "cls": "kr"} for t in F.DIV_RANK_MUST] + [{"t": f"{i:05d}0", "cls": "kr"} for i in range(1, 41)]
    ext = {s["t"]: {"epsIn": {"b": "o" if i % 2 else "s"}} for i, s in enumerate(kr)}
    assert F.eps_basis_of(kr, ext)[0] == "owners"
    bad = copy.deepcopy(ext)
    bad["005930"]["epsIn"]["b"] = "t"                                     # 필수 종목이 전체 순이익
    basis, why = F.eps_basis_of(kr, bad)
    assert basis == "mixed" and "005930" in why
    many = copy.deepcopy(ext)
    for t in list(many)[10:14]:
        many[t]["epsIn"]["b"] = "t"                                       # 47곳 중 4곳 = 91.5% < 95%
    assert F.eps_basis_of(kr, many)[0] == "mixed"
    assert F.eps_basis_of(kr, {})[0] == "mixed"                           # EPS 를 하나도 못 냈으면 표시하지 않아요


def test_pykrx_multiples_are_never_used_for_korean_stocks():
    import inspect
    src = inspect.getsource(F.fetch_korea)
    assert "per = pbr = eps = bps = None" in src and '_num(f.get("PER"))' not in src and '_num(f.get("EPS"))' not in src


def test_a_korean_eps_without_its_receipt_fails_the_gate(pair):
    cur, prev = pair
    c = comp(cur, "200300")
    p = c.pop("epsIn")["p"]
    cur["data"]["incCheck"]["epsB"]["o"] -= 1
    cur["data"]["incCheck"]["epsP"][p] -= 1
    assert "EPS 영수증 없음" in fails(cur, prev, "EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)")[1]


def test_mixed_eps_basis_marker_fails_the_gate(pair):
    cur, prev = pair
    cur["data"]["epsBasis"] = cur["corp"]["epsBasis"] = "mixed"
    fails(cur, prev, "EPS 기준 표시 (epsBasis = owners)")


def write_cache(path, v, entries, meta=None):
    import gzip
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump({"v": v, "meta": meta or {}, "entries": entries}, f)


def test_industry_codes_and_the_corp_map_carry_over_from_the_v2_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    old = tmp_path / "dart-v2.json.gz"
    write_cache(old, 2, {"C1|company": {"st": "000", "at": "2026-11-01", "d": {"induty": "264"}},
                         "C2|company": {"st": "013", "at": "2026-11-01", "d": None},
                         "C1|2025|11011|CFS": {"st": "000", "at": "2026-11-01", "d": {"debt": 1.0}},
                         "C1|2025|11011|DIV2": {"st": "000", "at": "2026-11-01", "d": {"dps": 1.0}}},
                {"corpMap": {"005930": "00126380"}, "corpMapAt": "2026-11-07", "lastFull": "2026-11-06"})
    carry = F.read_carry(str(old))
    assert set(carry[0]) == {"C1|company"} and carry[1] == {"corpMap": {"005930": "00126380"}, "corpMapAt": "2026-11-07"}
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=str(tmp_path / "dart-v3.json.gz"))
    assert c.started_empty and F.adopt_carry(c, carry) == 1 and c.carried == 1
    assert c.started_empty                                                 # 재무제표가 없는 캐시: 전체 실행 판단은 그대로
    assert c.company("C1") == {"induty": "264"} and not c.status           # 업종 코드는 호출 없이
    assert "lastFull" not in c.meta and c.meta["corpMap"] == {"005930": "00126380"}
    assert F.read_carry(str(tmp_path / "none.json.gz")) is None
    import inspect
    src = inspect.getsource(F.main)
    i = src.find("carry, keep_v2 = read_carry(legacy), legacy")
    assert 0 < i < src.find("adopt_carry(client, carry)") < src.find("client.remove_after_save.append(keep_v2)")
    assert "ksic=client.started_empty and not has_ksic" in inspect.getsource(F.enrich_with_dart)


def test_the_v2_file_is_kept_until_the_v3_cache_has_been_saved_once(tmp_path, monkeypatch):
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    old = tmp_path / "dart-v2.json.gz"
    write_cache(old, 2, {"C1|company": {"st": "000", "at": "2026-11-01", "d": {"induty": "264"}}})
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=str(tmp_path / "dart-v3.json.gz"))
    F.adopt_carry(c, F.read_carry(str(old)))
    c.remove_after_save.append(str(old))
    c.save()                                                               # 중간 저장 (재무제표 조회 전): 지우지 않아요 (리뷰 2026-11-08)
    assert old.exists()
    c.fetch_done = True                                                    # enrich_with_dart 가 조회를 끝냈어요
    real_dump = json.dump
    monkeypatch.setattr(F.json, "dump", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        c.save()                                                           # 첫 저장이 실패하면 (실행이 멈추면)
    assert old.exists()                                                    # v2 는 남아 다시 실행이 또 옮겨 써요
    assert F.read_carry(str(old))[0] == {"C1|company": {"st": "000", "at": "2026-11-01", "d": {"induty": "264"}}}
    monkeypatch.setattr(F.json, "dump", real_dump)
    c.save()
    assert not old.exists() and (tmp_path / "dart-v3.json.gz").exists() and c.remove_after_save == []
    c.save()                                                               # 두 번째 저장은 아무것도 지우지 않아요


def test_dropped_uncoded_interest_lines_are_counted_by_name(capsys):
    base = BS + [r("IS", "매출액", "ifrs-full_Revenue", 1e11),
                 r("CF", "이자의 지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -3e9)]
    lease = base + [r("CF", "리스부채 이자의 지급", NO_ID, -1e9), r("CF", "이자의 지급", NO_ID, 3e9)]   # 같은 이름·금액 줄은 같은 줄
    out = F.parse_dart_list(lease)
    assert out["_fin"]["iec"] == 30.0 and out["_inc"]["iecDrop"] == 1        # 규칙은 그대로 (코드 줄만) · 버린 줄 1개를 세요
    assert "iecDrop" not in F.parse_dart_list(base)["_inc"]
    assert F.interest_paid_dropped(lease) == 1 and F.interest_paid_dropped(base) == 0
    F.income_log({"000100": ("가", out["_inc"], True), "000200": ("나", {"src": {"rev": "id"}}, True)})
    assert "더하지 않은 코드 없는 이자 지급 줄이 있는 곳 (사업보고서 · 로그만" in capsys.readouterr().out
    F.income_log({"000100": ("가", out["_inc"], True)})
    assert ": 1 (000100 가(1))" in capsys.readouterr().out


def test_ev_adds_minority_interest_and_uses_the_full_listing_for_preferred_caps(monkeypatch):
    com = {"t": "012450", "nk": "한화에어로스페이스", "cls": "kr", "price": 100.0, "cap": 10.0, "shr": 1, "s": "defense"}
    fin = {"012450": {"rev": [100000.0, None, None], "op": [10.0, None, None], "ni": [1.0] * 3, "dep": 0.0, "bor": 0.0,
                      "cash": 0.0, "ocf": 100000.0, "eq": 9e4, "eqo": 5e4, "bs2": {"eq": 3e4, "eqo": 2e4}, "fs": "CFS"}}
    c = corp_of([com], fin)["012450"]
    assert c["evR"] == 1.1 and c["pcf"] == 1.0                             # (10조 + 최신 분기 비지배지분 1조) ÷ 10조 · P/CF 엔 안 더해요
    c = corp_of([com], {"012450": dict(fin["012450"], fs="OFS")})["012450"]
    assert c["evR"] == 1.0                                                 # 별도 재무제표엔 비지배지분이 없어요
    monkeypatch.setattr(F, "EV_WITH_NCI", False)
    assert corp_of([com], fin)["012450"]["evR"] == 1.0
    monkeypatch.setattr(F, "EV_WITH_NCI", True)
    out = {x["t"]: x for x in F.build_corp([com], fin, "2026-11-08", pref_caps={"01245": 2.0})["companies"]}
    assert out["012450"]["evR"] == 1.3                                     # 목록 파일의 우선주 시가총액 2조 (data.json 에 없어도)
    import pandas as pd
    listing = pd.DataFrame({"Code": ["005930", "005935", "00680K", "006800"], "Marcap": [1e15, 1.2e14, 5e11, 3e12]})
    assert F.kr_pref_caps(listing) == {"00593": 120.0, "00680": 0.5}


def corp_one(fin, **s):
    base = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "cap": 1.0, "shr": 1_000_000, "s": "chem", "ind": "chem"}
    return F.build_corp([dict(base, **s)], {"000100": fin}, "2026-11-10")["companies"][0]


def test_icr_never_mixes_ttm_operating_profit_with_annual_interest():
    fin = {"op": [50.0, None, None], "ie": 10.0, "ttm": {"op": 5.0}}
    assert F.icr_inputs(fin) == (50.0, 10.0, "is", "fy", None)            # TTM 이자가 없으면 연간끼리 (예전: 5 ÷ 10 = 0.5배 경고)
    assert F.icr_inputs({"op": [50.0], "ie": 10.0, "ttm": {"op": 5.0, "iec": 2.0}}) == (5.0, 2.0, "cf", "ttm", None)
    assert F.icr_inputs({"op": [None], "ie": 3.0})[4] == "op"
    assert F.icr_inputs({"op": [5.0], "ie": -1.0})[4] == "neg"
    assert F.icr_inputs({"op": [5.0]})[4] == "ie"
    c = corp_one({"ni": [1.0] * 3, "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0, **fin})
    assert "fl" not in c and c["flSrc"] == {"icr": "is"}


def test_icr_warning_row_counts_warnings_and_never_fails(pair):
    cur, prev = pair
    comps = cur["corp"]["companies"]
    for i, c in enumerate(comps[:100]):
        c.update(flRan=["icr"], flSrc={"icr": "is" if i % 2 else "cf"}, fl={"icr": 0.5} if i < 20 else {})
    rep = check(cur, prev)
    row = rows_of(rep)["이자보상배율 경고 수 · 쓴 이자 (경고만)"]
    assert row[3] == "WARN" and "경고 20 / 돌린 100 (20.0%)" in row[1] and "이자비용 50" in row[1], row
    assert "이자보상배율 경고 수 · 쓴 이자 (경고만)" not in {x[0] for x in rep.failed}


def test_a_coded_line_with_a_blank_current_year_counts_as_not_found_in_the_log(capsys):
    out = F.parse_dart_list(BS + [r("IS", "매출액", "ifrs-full_Revenue", "", 9e10), r("IS", "영업이익", "dart_OperatingIncomeLoss", 1e9)])
    assert out["_fin"]["rev"] == [None, 900.0, None] and out["_inc"]["src"]["rev"] == "blank"
    F.income_log({"000100": ("가", out["_inc"], True)})
    assert "매출 0 / 0 / 1" in capsys.readouterr().out
