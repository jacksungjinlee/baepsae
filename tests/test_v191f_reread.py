"""v19.1f: 이자보상배율의 이자와 손익 줄 이름을 다시 읽어요 (Jack, 2026-11-07).

- 이자 = 손익계산서의 '이자비용', 없으면 현금흐름표의 이자 지급 줄을 모두 더한 값(양수). 이자의 수취는 절대 아니에요.
  예전에는 '금융비용'(환손실·파생상품 손실이 든 금융원가)을 이자로 읽어서 2026-11-07 경고 505곳 중 502곳이 그 값이었어요.
- 매출 · 영업이익 · 순이익을 예전 이름으로 못 찾으면 앞 번호를 빼고 더 많은 이름('영업손실' · 'Ⅲ.영업손익' · 'V.영업이익'),
  그래도 없으면 표준 계정 코드로. 2026-11-07 재무제표를 읽고도 셋 다 빈 회사가 51곳이었어요 (롯데케미칼 · 넷마블 · 코오롱인더).
- 손실 이름의 줄은 음수로 나와야 해요: 이름이 손실뿐인데 올해 값이 양수면 쓰지 않아요.
시험의 줄은 2026-11-07 에 받은 실제 사업보고서(2025) 줄을 그대로 옮겼어요 (이름 · 계정 코드 · 금액).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_data as F  # noqa: E402


def row(sj, nm, aid, a, b=None, c=None, add=None):
    r = {"sj_div": sj, "account_nm": nm, "account_id": aid, "thstrm_amount": str(a)}
    if b is not None:
        r["frmtrm_amount"] = str(b)
    if c is not None:
        r["bfefrmtrm_amount"] = str(c)
    if add is not None:
        r["thstrm_add_amount"] = str(add)
    return r


BS = [row("BS", "자본총계", "ifrs-full_Equity", 1.0e13), row("BS", "부채총계", "ifrs-full_Liabilities", 1.0e13)]

LOTTE_CHEM = BS + [                                           # 롯데케미칼 011170 (연결)
    row("CIS", "영업손실", "dart_OperatingIncomeLoss", -943115729953, -914535316186),
    row("CIS", "당기순손실", "ifrs-full_ProfitLoss", -2476176326250, -1825555752135),
    row("CIS", "계속영업당기순손실", "ifrs-full_ProfitLossFromContinuingOperations", -2483480325529, -1838484803080),
    row("CIS", "매출", "ifrs-full_Revenue", 18483005314922, 19894809600093),
    row("CIS", "금융비용", "ifrs-full_FinanceCosts", 1.2e12),
    row("CF", "이자의 지급", "ifrs-full_InterestPaidClassifiedAsFinancingActivities", 418142626955, 448938494556),
    row("CF", "이자의 수취", "ifrs-full_InterestReceivedClassifiedAsInvestingActivities", 137864790986, 178173247713),
]
NETMARBLE = BS + [                                            # 넷마블 251270 (연결)
    row("CIS", "Ⅲ.영업손익", "dart_OperatingIncomeLoss", 352478352483, 215627215188),
    row("CIS", "당기순손익", "ifrs-full_ProfitLoss", 230818642770, 3216188118),
    row("CIS", "Ⅰ.영업수익", "ifrs-full_Revenue", 2835074411896, 2663783169910),
    row("CF", "3.이자의 지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", 63673067845, 88939547403),
    row("CF", "2.이자의 수취", "ifrs-full_InterestReceivedClassifiedAsOperatingActivities", -14951211925, -19347820157),
]
KOLON = BS + [                                                # 코오롱인더 120110 (연결)
    row("CIS", "V. 영업이익", "dart_OperatingIncomeLoss", 108896018558, 158723468850),
    row("CIS", "X. 당기순이익", "ifrs-full_ProfitLoss", 51573520480, 110628722171),
    row("CIS", "VIII. 계속영업이익", "ifrs-full_ProfitLossFromContinuingOperations", 51777149790, 110798245333),
    row("CIS", "I. 매출", "ifrs-full_Revenue", 4873399491952, 4843003131269),
    row("CF", "신종자본증권이익분배금", "dart_InterestPaidToHybridBond", 32079176025, 19430825000),
    row("CF", "이자의지급", "ifrs-full_InterestPaidClassifiedAsFinancingActivities", 114729032495, 104988247349),
    row("CF", "이자의수취", "ifrs-full_InterestReceivedClassifiedAsInvestingActivities", 13896675711, 13995975743),
    row("CF", "이자비용", "dart_AdjustmentsForInterestExpenses", 117025602677, 108077550486),   # 간접법 조정 줄 (지급 아님)
]
eok = lambda v: round(v / 1e8, 1)


# ── 1. 손익 줄 이름 ───────────────────────────────────────
def test_loss_named_lines_are_read_and_come_out_negative():
    fin = F.parse_dart_list(LOTTE_CHEM)["_fin"]
    assert fin["op"][:2] == [eok(-943115729953), eok(-914535316186)] and fin["op"][0] < 0          # 영업손실 −9,431억
    assert fin["ni"][:2] == [eok(-2476176326250), eok(-1825555752135)] and fin["ni"][0] < 0       # 당기순손실 (계속영업 줄 아님)
    assert fin["rev"][0] == eok(18483005314922)                                                   # '매출'


def test_numbered_names_are_read():
    nm = F.parse_dart_list(NETMARBLE)["_fin"]
    assert nm["op"][0] == eok(352478352483) and nm["ni"][0] == eok(230818642770) and nm["rev"][0] == eok(2835074411896)
    kl = F.parse_dart_list(KOLON)["_fin"]
    assert kl["op"][0] == eok(108896018558) and kl["ni"][0] == eok(51573520480) and kl["rev"][0] == eok(4873399491952)
    out = F.parse_dart_list(KOLON)                                                                 # 이제 비율도 나와요
    assert out["opm"] == round(108896018558 / 4873399491952 * 100, 1) and "roe" in out


def test_a_loss_only_name_with_a_positive_figure_is_not_used():
    bad = BS + [row("CIS", "영업손실", "dart_OperatingIncomeLoss", 5e9), row("CIS", "매출", "ifrs-full_Revenue", 1e11),
                row("CIS", "당기순손실", "ifrs-full_ProfitLoss", 3e9)]
    before = dict(F.INC_SEEN)
    fin = F.parse_dart_list(bad)["_fin"]
    assert fin["op"] == [None, None, None] and fin["ni"] == [None, None, None] and fin["rev"][0] == 1000.0
    assert F.INC_SEEN["op:sign"] == before.get("op:sign", 0) + 1 and F.INC_SEEN["ni:sign"] == before.get("ni:sign", 0) + 1
    # 손익(profit/loss) 이름은 부호를 그대로: 양수면 이익
    ok = F.parse_dart_list(BS + [row("CIS", "영업손익", "dart_OperatingIncomeLoss", 5e9), row("CIS", "매출", "ifrs-full_Revenue", 1e11)])
    assert ok["_fin"]["op"][0] == 50.0


def test_companies_read_before_keep_exactly_the_same_values():
    rows = BS + [row("IS", "매출액", "ifrs-full_Revenue", 1e11), row("IS", "영업이익", "dart_OperatingIncomeLoss", 2e10),
                 row("IS", "당기순이익", "ifrs-full_ProfitLoss", 1e10),
                 row("IS", "Ⅲ.영업손익", "x", 9e10), row("IS", "매출", "y", 7e11), row("IS", "당기순손익", "z", 8e10)]
    fin = F.parse_dart_list(rows)["_fin"]
    assert (fin["rev"][0], fin["op"][0], fin["ni"][0]) == (1000.0, 200.0, 100.0)                  # 예전 이름이 먼저예요


def test_the_standard_code_is_not_used_when_several_lines_carry_it():
    rows = BS + [row("CIS", "제품 매출", "ifrs-full_Revenue", 3e10), row("CIS", "상품 매출", "ifrs-full_Revenue", 2e10),
                 row("CIS", "영업에서 생긴 이익", "dart_OperatingIncomeLoss", 3e9)]
    fin = F.parse_dart_list(rows)["_fin"]
    assert fin["rev"] == [None, None, None] and fin["op"][0] == 30.0          # 아랫줄일 수 있는 매출은 쓰지 않아요


def test_the_standard_code_is_only_taken_from_the_income_statement():
    rows = BS + [row("CF", "당기순이익조정", "ifrs-full_ProfitLoss", 9e9), row("CIS", "회사 순이익", "ifrs-full_ProfitLoss", 2e9),
                 row("CIS", "영업에서 생긴 이익", "dart_OperatingIncomeLoss", 3e9), row("CIS", "합계 매출", "ifrs-full_Revenue", 2e10)]
    fin = F.parse_dart_list(rows)["_fin"]
    assert fin["ni"][0] == 20.0 and fin["op"][0] == 30.0 and fin["rev"][0] == 200.0


# ── 2. 이자 ───────────────────────────────────────────────
def test_finance_costs_are_no_longer_interest():
    fin = F.parse_dart_list(LOTTE_CHEM)["_fin"]
    assert fin["ie"] is None                                                       # 금융비용 1.2조는 이자가 아니에요
    assert fin["iec"] == eok(418142626955)                                         # 현금흐름표의 이자 지급 (수취 아님)


def test_interest_expense_on_the_income_statement_comes_first():
    rows = BS + [row("IS", "매출액", "ifrs-full_Revenue", 1e11), row("IS", "금융비용", "ifrs-full_FinanceCosts", 9e9),
                 row("IS", "이자비용", "dart_InterestExpenseFinanceExpense", 4e9),
                 row("CF", "이자의지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -3e9)]
    fin = F.parse_dart_list(rows)["_fin"]
    assert fin["ie"] == 40.0 and fin["iec"] == 30.0                                # 금융비용이 먼저 나와도 이자비용을 써요


def test_cash_interest_paid_adds_every_paid_line_as_a_positive_amount():
    rows = BS + [row("IS", "매출액", "ifrs-full_Revenue", 1e11),
                 row("CF", "이자의지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -3e9),
                 row("CF", "이자지급", "ifrs-full_InterestPaidClassifiedAsFinancingActivities", 2e9),
                 row("CF", "차입원가자본화 이자의 지급", "ifrs-full_InterestPaidClassifiedAsInvestingActivities", -1e9),
                 row("CF", "이자의 지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -3e9),   # 같은 줄이 두 번: 한 번만
                 row("CF", "이자의 수취", "ifrs-full_InterestReceivedClassifiedAsOperatingActivities", 7e9),
                 row("CF", "이자수취", "-표준계정코드 미사용-", 7e9),
                 row("CF", "이자비용", "dart_AdjustmentsForInterestExpenses", 9e9),
                 row("CF", "신종자본증권이자지급", "dart_InterestPaidToHybridBond", 5e9)]
    assert F.parse_dart_list(rows)["_fin"]["iec"] == 60.0
    kl = F.parse_dart_list(KOLON)["_fin"]
    assert kl["iec"] == eok(114729032495)                                          # 신종자본증권 분배금 · 간접법 조정 줄 · 수취 빼고
    assert F.parse_dart_list(NETMARBLE)["_fin"]["iec"] == eok(63673067845)          # 음수로 적힌 수취도 빼요


def test_lines_without_a_standard_code_are_used_only_when_no_coded_line_exists():
    loose = BS + [row("IS", "매출액", "ifrs-full_Revenue", 1e11), row("CF", "이자의 지급", "-표준계정코드 미사용-", -2e9),
                  row("CF", "이자수익의 수취", "-표준계정코드 미사용-", 5e9), row("CF", "신종자본증권 이자 지급", "-표준계정코드 미사용-", 4e9)]
    assert F.parse_dart_list(loose)["_fin"]["iec"] == 20.0
    both = loose + [row("CF", "이자지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -1e9)]
    assert F.parse_dart_list(both)["_fin"]["iec"] == 10.0                           # 코드가 있는 줄이 있으면 그것만 (두 번 세지 않게)
    none = BS + [row("IS", "매출액", "ifrs-full_Revenue", 1e11)]
    assert F.parse_dart_list(none)["_fin"]["iec"] is None


def test_the_quarter_reads_the_same_way_and_the_ttm_uses_the_cash_figure():
    q = F.parse_dart_quarter([row("IS", "매출액", "ifrs-full_Revenue", 3e10, add=9e10),
                              row("IS", "영업이익(손실)", "dart_OperatingIncomeLoss", 1e9, add=4e9),      # 예전 분기는 못 찾았어요
                              row("IS", "금융비용", "ifrs-full_FinanceCosts", 5e9, add=8e9),
                              row("CF", "이자의지급", "ifrs-full_InterestPaidClassifiedAsOperatingActivities", -2e9)])
    assert q["op"] == 40.0 and q["ie"] is None and q["iec"] == 20.0
    q2 = F.parse_dart_quarter([row("CIS", "Ⅰ.영업수익", "ifrs-full_Revenue", 1e10), row("CIS", "Ⅲ.영업손익", "dart_OperatingIncomeLoss", -2e9)])
    assert q2["rev"] == 100.0 and q2["op"] == -20.0
    ttm = F.compute_ttm({"rev": [100.0], "op": [10.0], "ni": [5.0], "ie": None, "iec": 12.0},
                        {"rev": 90.0, "op": 9.0, "ni": 4.0, "iec": 10.0}, {"rev": 80.0, "op": 8.0, "ni": 3.0, "iec": 7.0})
    assert ttm["ttm"]["iec"] == 15.0 and ttm["ttm"]["ie"] is None


# ── 3. 이자보상배율 ───────────────────────────────────────
def corp(fin, **s):
    base = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "cap": 1.0, "shr": 1_000_000, "s": "chem", "ind": "chem"}
    return F.build_corp([dict(base, **s)], {"000100": fin}, "2026-11-10")["companies"][0]


def test_icr_is_on_again_and_says_which_interest_it_used():
    assert F.ICR_OFF is False
    common = {"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0, "op": [5.0, 0, 0]}
    c = corp(dict(common, ie=10.0, iec=2.0))
    assert c["flSrc"] == {"icr": "is"} and c["fl"]["icr"] == 0.5 and "icr" in c["flRan"]   # 이자비용이 있으면 그것
    c = corp(dict(common, iec=2.0))
    assert c["flSrc"] == {"icr": "cf"} and "fl" not in c and c["flRan"] == ["cr", "icr", "l3", "imp"]   # 5 ÷ 2 = 2.5배: 경고 없음
    c = corp(dict(common, op=[-3.0, 0, 0], iec=2.0))
    assert c["fl"]["icr"] == -1.5 and c["flSrc"] == {"icr": "cf"}                  # 영업손실 (앱은 숫자 없이 말해요)
    c = corp(common)
    assert c["flWhy"] == {"icr": "ie"} and "flSrc" not in c and "icr" not in c["flRan"]   # 둘 다 없음: '찾지 못해' 줄
    bank = corp(dict(common, ie=10.0), s="bank", ind="bank")
    assert "flSrc" not in bank and bank["flNa"] == ["cr", "icr"]


def test_the_switch_still_turns_it_off(monkeypatch):
    monkeypatch.setattr(F, "ICR_OFF", True)
    c = corp({"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0, "op": [5.0, 0, 0], "iec": 20.0})
    assert c["flWhy"] == {"icr": "off"} and "flSrc" not in c and "icr" not in c["flRan"]


def test_the_cash_figure_reaches_the_check_through_the_quarter_ttm():
    fin = {"ni": [1.0, 1.0, 1.0], "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0, "op": [5.0, 0, 0], "iec": 100.0,
           "ttm": {"op": 5.0, "iec": 10.0}}
    c = corp(fin)
    assert c["flSrc"] == {"icr": "cf"} and c["fl"]["icr"] == 0.5                   # TTM 이자 지급액(10)이 연간(100)보다 먼저
