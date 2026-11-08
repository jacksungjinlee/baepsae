# -*- coding: utf-8 -*-
"""v19.1f 지배주주 순이익 규칙 (2026-11-08 시험 실행 뒤): code · alt · cont · sum · minus · nci0, 당기순이익 = 지배 + 비지배, 다시 받기.

2026-11-08 브랜치 시험 실행(dart=full)에서 연결 재무제표 160곳의 EPS 가 전체 순이익이었어요 (지배주주·별도 93.2%). 그 160곳의 실제
재무제표를 받아 보니 70곳은 비지배지분 줄이 아예 없고, 25곳은 0, 35곳은 표준 코드 없는 지배주주 줄, 11곳은 다른 코드였어요.
픽스처 tests/fixtures/dart_owners_samples.json 은 그날 받은 실제 연결 재무제표의 손익·지배·비지배·계속/중단영업 줄과 자본 줄이에요.
(네트워크 없음)"""
import copy
import datetime as dt
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402

with open(os.path.join(ROOT, "tests", "fixtures", "dart_owners_samples.json"), encoding="utf-8") as _f:
    ST = json.load(_f)["statements"]
NO_ID = "-표준계정코드 미사용-"


def rows(t, y="2025", r="11011"):
    return copy.deepcopy(ST[f"{t}|{y}|{r}|CFS"]["rows"])


def annual(t):
    return F.parse_dart_list(rows(t))["_fin"]


def r(sj, nm, aid, a, b=None, c=None, add=None):
    out = {"sj_div": sj, "account_nm": nm, "account_id": aid, "thstrm_amount": str(a)}
    for k, v in (("frmtrm_amount", b), ("bfefrmtrm_amount", c), ("thstrm_add_amount", add)):
        if v is not None:
            out[k] = str(v)
    return out


EQ = [r("BS", "자본총계", "ifrs-full_Equity", 4e12), r("BS", "부채총계", "ifrs-full_Liabilities", 2e12)]
PL = r("CIS", "당기순이익", "ifrs-full_ProfitLoss", 1e10)


# ── 1. 실제 재무제표: 규칙마다 ──────────────────────────────────
@pytest.mark.parametrize("t, how, nio0", [
    ("141080", "alt", -742.8),        # 리가켐바이오: ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity
    ("003530", "cont", 1020.1),       # 한화투자증권: 계속영업 지배주주 줄 하나 (중단영업 없음)
    ("036830", "cont", 4873.6),       # 솔브레인홀딩스: 계속영업 421억 + 중단영업 4,452억 (지배주주)
    ("069540", "sum", -196.2),        # 빛과전자: 같은 이름 '지배기업소유주지분' 두 줄 중 + 비지배 = 당기순이익인 줄
    ("290090", "sum", -28.2),         # 트윔
    ("045660", "minus", 4.5),         # 에이텍: 당기순이익 − 비지배지분 순이익
    ("010950", "nci0", 1769.5),       # S-Oil: 비지배지분 줄이 아예 없음
    ("029780", "nci0", 6459.2),       # 삼성카드: 비지배지분 0
    ("277810", "code", 14.2),         # 레인보우로보틱스 (코드 줄 · 당기순이익 줄은 없음)
])
def test_each_rule_on_a_real_statement(t, how, nio0):
    fin = annual(t)
    assert fin["nioHow"] == how and fin["nio"] == nio0 and fin["nio3"][0] == nio0


def test_continuing_plus_discontinued_owners_equals_total_minus_minority():
    fin = annual("036830")                                                # 솔브레인홀딩스 (중단영업 이익 4,452억)
    assert fin["nio"] == round((42116726969 + 445245906229) / 1e8, 1) == round((495558016939 - 8195383741) / 1e8, 1)
    assert fin["ni"][0] == round(495558016939 / 1e8, 1)


def test_the_sum_check_picks_the_profit_row_among_rows_with_the_same_name():
    # 빛과전자: '지배기업소유주지분' −19,619,441,858 (순이익) 와 −20,157,523,009 (포괄이익), 비지배 −31,636,729, 당기순이익 −19,651,078,587
    fin = annual("069540")
    assert fin["nio"] == round(-19619441858 / 1e8, 1)
    swapped = rows("069540")
    for x in swapped:                                                       # 순이익 줄을 지우면 포괄이익 줄을 고르지 않아요
        if x.get("thstrm_amount") == "-19619441858":
            x["thstrm_amount"] = "-19000000000"
    assert F.parse_dart_list(swapped)["_fin"].get("nioHow") != "sum"


def test_sum_tolerance_is_a_thousand_won():
    base = EQ + [PL, r("CIS", "지배기업소유주지분", NO_ID, 1e10 - 400 - 1000), r("CIS", "비지배지분", NO_ID, 400)]
    assert F.parse_dart_list(base)["_fin"]["nioHow"] == "sum"              # 정확히 1,000원 차이
    off = EQ + [PL, r("CIS", "지배기업소유주지분", NO_ID, 1e10 - 400 - 1001), r("CIS", "비지배지분", NO_ID, 400)]
    fin = F.parse_dart_list(off)["_fin"]
    assert fin["nioHow"] == "minus" and fin["nio"] == round((1e10 - 400) / 1e8, 1)   # 맞지 않으면 sum 아님 (당기순이익 − 비지배)


def test_names_that_are_not_owners_profit_are_never_summed():
    for bad in ("비지배지분", "지배기업 소유주지분 총포괄이익", "종속기업,공동지배기업과관계기업으로부터의기타수익", "관계기업 지배력 상실 이익"):
        # 이 줄 + 비지배 2e9 = 당기순이익 1e10 이라 이름을 빼지 않으면 sum 으로 골라질 값이에요
        rows_ = EQ + [PL, r("CIS", bad, NO_ID, 8e9), r("BS", "비지배지분", NO_ID, 5e9), r("CIS", "비지배지분순이익", NO_ID, 2e9)]
        fin = F.parse_dart_list(rows_)["_fin"]
        assert fin.get("nioHow") != "sum", bad


# ── 2. nci0 의 증거 ────────────────────────────────────────────
def test_nci0_needs_no_minority_interest_in_both_statements():
    assert annual("319660").get("nio") is None                              # 피에스케이: 비지배지분 0.9억 (작아도 0 이 아님) → 전체(t)
    assert annual("373200").get("nio") is None                              # 엑스플러스: 비지배지분 1.2억
    base = EQ + [PL]
    assert F.parse_dart_list(base)["_fin"]["nioHow"] == "nci0"               # 줄이 아예 없음
    zero = base + [r("BS", "비지배지분", "ifrs-full_NoncontrollingInterests", 0),
                   r("CIS", "비지배지분", "ifrs-full_ProfitLossAttributableToNoncontrollingInterests", 0)]
    assert F.parse_dart_list(zero)["_fin"]["nioHow"] in ("minus", "nci0")   # 비지배 순이익 0 이 적혀 있으면 당기순이익 − 0
    bs_only = base + [r("BS", "비지배지분", "ifrs-full_NoncontrollingInterests", 3e8)]
    assert F.parse_dart_list(bs_only)["_fin"].get("nio") is None             # 재무상태표에 비지배지분이 있으면 nci0 아님
    eq_gap = base + [r("BS", "지배기업 소유주지분", "ifrs-full_EquityAttributableToOwnersOfParent", 3.9e12)]
    assert F.parse_dart_list(eq_gap)["_fin"].get("nio") is None              # 지배주주 자본 ≠ 자본총계 → nci0 아님
    eq_same = base + [r("BS", "지배기업 소유주지분", "ifrs-full_EquityAttributableToOwnersOfParent", 4e12)]
    assert F.parse_dart_list(eq_same)["_fin"]["nioHow"] == "nci0"


def test_an_owners_line_that_does_not_add_up_blocks_nci0():
    fin = annual("134790")                                                  # 시디즈: 지배 줄이 당기순이익과 다르고 비지배 줄은 없음
    assert fin.get("nio") is None and fin["ni"][0] is not None


def test_nci_evidence_is_stored_for_annual_and_quarterly_statements():
    assert (annual("010950")["nciBs"], annual("010950")["nciPl"]) == (None, None)
    assert annual("029780")["nciBs"] == 0.0 and annual("141080")["nciPl"] == -172.7
    q = F.parse_dart_quarter(rows("043260", "2025", "11012"))
    assert "nciBs" in q and q["nciBs"] == 10.4 and q["nciPl"] == -0.5


# ── 3. 계속영업 줄: 중단영업이 있으면 하나만으로는 안 써요 ────────────
def test_continuing_only_is_not_used_when_there_are_discontinued_operations():
    cont = r("CIS", "지배기업 계속영업이익", "ifrs-full_IncomeFromContinuingOperationsAttributableToOwnersOfParent", 8e9)
    disc = r("CIS", "중단영업이익", "ifrs-full_ProfitLossFromDiscontinuedOperations", 2e9)
    nci_bs = r("BS", "비지배지분", "ifrs-full_NoncontrollingInterests", 1e9)
    assert F.parse_dart_list(EQ + [PL, cont, nci_bs])["_fin"]["nioHow"] == "cont"            # 중단영업 없음
    assert F.parse_dart_list(EQ + [PL, cont, disc, nci_bs])["_fin"].get("nio") is None       # 중단영업 있음 · 지배 몫 줄 없음
    disc_own = r("CIS", "지배기업 중단영업이익", "ifrs-full_IncomeFromDiscontinuedOperationsAttributableToOwnersOfParent", 1.5e9)
    fin = F.parse_dart_list(EQ + [PL, cont, disc, disc_own, nci_bs])["_fin"]
    assert fin["nioHow"] == "cont" and fin["nio"] == 95.0                                    # 계속 + 중단 (지배)


# ── 4. 당기순이익 줄이 없을 때: 지배 + 비지배 ───────────────────────
def test_total_profit_is_owners_plus_minority_when_the_total_row_is_missing():
    out = F.parse_dart_list(rows("277810"))
    assert out["_fin"]["ni"] == [14.2, 21.4, -8.4] and out["_inc"]["src"]["ni"] == "parts"   # 예전엔 빈 칸
    q = F.parse_dart_quarter(rows("251970", "2026", "11012"))                                 # 펌텍코리아 2026 반기: 당기순이익 줄 없음
    assert q["ni"] == round(q["nio"] + q["nciPl"], 1) and q["nioHow"] == "code"
    only = EQ + [r("CIS", "지배기업 소유주지분", "ifrs-full_ProfitLossAttributableToOwnersOfParent", 5e9)]
    assert F.parse_dart_list(only)["_fin"]["ni"] == [None, None, None]                       # 비지배 줄이 없으면 만들지 않아요


# ── 5. 분기·반기도 같은 규칙 → TTM ─────────────────────────────────
@pytest.mark.parametrize("t, y, how", [("043260", "2025", "minus"), ("028670", "2025", "nci0"), ("298380", "2025", "sum")])
def test_half_year_statements_use_the_same_rules(t, y, how):
    assert F.parse_dart_quarter(rows(t, y, "11012"))["nioHow"] == how


def test_half_year_with_minority_interest_and_no_split_stays_without_owners_profit():
    q = F.parse_dart_quarter(rows("196170", "2025", "11012"))                                 # 알테오젠 2025 반기 (비지배 41.7억)
    assert q["nio"] is None and q["nioHow"] is None and q["ni"] is not None


def test_ttm_says_how_each_report_was_read():
    t2 = F.compute_ttm({"rev": [10.0], "ni": [5.0], "nio": 4.0, "nioHow": "code"},
                       {"rev": 6.0, "ni": 3.0, "nio": 3.0, "nioHow": "nci0", "nciBs": None},
                       {"rev": 5.0, "ni": 2.0, "nio": 2.0, "nioHow": "code"})
    assert t2["ttm"]["nio"] == 5.0 and t2["ttm"]["nioHow"] == "code+nci0" and "nciBs" in t2["bs"]


# ── 6. EPS · BPS 영수증의 how ──────────────────────────────────────
def test_every_receipt_says_how_it_was_read():
    base = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "shr": 1000, "cap": 1.0}
    cases = {"o": ({"ni": [5.0, None, None], "nio": 4.0, "nioHow": "nci0", "eq": 9.0, "nciBs": None, "fs": "CFS"}, "nci0", "nci0"),
             "s": ({"ni": [5.0, None, None], "eq": 9.0, "fs": "OFS"}, "ofs", "ofs"),
             "t": ({"ni": [5.0, None, None], "eq": 9.0, "nciBs": 1.0, "fs": "CFS"}, "total", "total")}
    for b, (fin, eh, bh) in cases.items():
        s = dict(base)
        e = F.fill_multiples([s], {"000100": fin}, {})["000100"]
        assert (e["epsIn"]["b"], e["epsIn"]["how"], e["bpsIn"]["how"]) == (b, eh, bh)
        assert e["bpsIn"]["b"] == ("t" if b == "t" else b)


# ── 7. 다시 받기 (dart=cache) ──────────────────────────────────────
def test_owners_refetch_targets_only_consolidated_entries_read_before_the_rule():
    old_a = {"debt": 1.0, "_inc": {"src": {}}, "_fin": {"rev": [1.0, None, None], "ni": [1.0, None, None], "nio": None}}
    assert F.needs_owners(old_a) is True
    assert F.needs_owners(dict(old_a, _fin=dict(old_a["_fin"], nio=1.0))) is False            # 지배주주 순이익도 당기순이익도 있음
    assert F.needs_owners(dict(old_a, _fin=dict(old_a["_fin"], nio=1.0, ni=[None, 1.0, 1.0]))) is True   # 당기순이익 줄이 없었음
    assert F.needs_owners(dict(old_a, _fin=dict(old_a["_fin"], nciBs=None))) is False          # 새 해석으로 읽은 항목 (다시 안 받아요)
    assert F.needs_owners({"debt": 1.0, "_fin": {"nio": None}}) is False                       # v19.1f 전 해석 (v3 캐시엔 없어요)
    old_q = {"rev": 1.0, "ni": 1.0, "nio": None, "iec": None}
    assert F.needs_owners_q(old_q) is True and F.needs_owners_q(dict(old_q, nciBs=None)) is False
    assert F.needs_owners_q({"rev": 7.0}) is False


def test_owners_refetch_runs_once_in_a_cache_run_and_counts(tmp_path, monkeypatch):
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    calls = []

    def get(self, endpoint, params, timeout=25):
        calls.append((params["corp_code"], params["reprt_code"], params.get("fs_div")))
        with self.lock:
            self.status["000"] += 1
        return {"status": "000", "list": rows("010950") if params["reprt_code"] == "11011" else rows("028670", "2025", "11012")}
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=dt.date(2026, 11, 9), path=str(tmp_path / "c.json.gz"))
    old_a = {"debt": 1.0, "_inc": {"src": {}}, "_fin": {"rev": [1.0, None, None], "ni": [1.0, None, None], "nio": None, "iec": None}}
    c.entries["C1|2025|11011|CFS"] = {"st": "000", "at": "2026-11-08", "d": old_a, "rp": F.CAP_REDO_TAG}
    c.entries["C1|2025|11011|OFS"] = {"st": "000", "at": "2026-11-08", "d": old_a, "rp": F.CAP_REDO_TAG}
    c.entries["C1|2026|11012|CFS"] = {"st": "000", "at": "2026-11-08", "d": {"rev": 1.0, "ni": 1.0, "nio": None, "iec": None}}
    assert F.owners_backlog(c.entries, c.today) == (1, 1)                                     # 별도(OFS)는 대상이 아니에요
    d = F.dart_financials(c, "C1", 2025)
    q = F.dart_quarter(c, "C1", 2026, "11012", fs="CFS")
    assert d["_fin"]["nioHow"] == "nci0" and q["nioHow"] == "nci0" and len(calls) == 2
    assert c.redo_tags[F.OWN_REDO_TAG] == 2 and c.redone_tags[F.OWN_REDO_TAG] == 2
    assert c.entries["C1|2025|11011|CFS"]["rp"] == F.CAP_REDO_TAG                              # 자본금 표시는 그대로
    assert F.owners_backlog(c.entries, c.today) == (0, 0)
    F.dart_financials(c, "C1", 2025)
    F.dart_quarter(c, "C1", 2026, "11012", fs="CFS")
    assert len(calls) == 2                                                                    # 한 번만
    assert "지배주주 줄 다시 읽기 2건 시도 (실행당 최대 800): 새로 읽음 2" in c.summary()


def test_owners_refetch_shares_the_per_run_cap(tmp_path, monkeypatch):
    monkeypatch.delenv("BAEPSAE_AUTO_RUN", raising=False)
    monkeypatch.setattr(F.DartClient, "get", lambda self, e, p, timeout=25: {"status": "000", "list": rows("010950")})
    c = F.DartClient("k", today=dt.date(2026, 11, 9), path=str(tmp_path / "c.json.gz"))
    c.redo_left = 1
    old_a = {"debt": 1.0, "_inc": {"src": {}}, "_fin": {"rev": [1.0, None, None], "ni": [1.0, None, None], "nio": None}}
    for i in range(3):
        c.entries[f"C{i}|2025|11011|CFS"] = {"st": "000", "at": "2026-11-08", "d": copy.deepcopy(old_a), "rp": F.CAP_REDO_TAG}
    got = [F.dart_financials(c, f"C{i}", 2025)["_fin"].get("nioHow") for i in range(3)]
    assert got == ["nci0", None, None] and c.redo_tags[F.OWN_REDO_TAG] == 1 and F.owners_backlog(c.entries, c.today) == (2, 0)


# ── 8. 이자보상배율: 1 미만이면 '1.0' 으로 보이지 않게 ─────────────────
def test_icr_below_one_never_reads_one():
    def corp(fin):
        base = {"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "cap": 1.0, "shr": 1_000_000, "s": "chem", "ind": "chem"}
        return F.build_corp([base], {"000100": fin}, "2026-11-10")["companies"][0]
    common = {"ni": [1.0] * 3, "ca": 3.0, "cl": 1.0, "cs": 1.0, "eq": 5.0}
    assert corp(dict(common, op=[9.95, 0, 0], iec=10.0))["fl"]["icr"] == 0.9                 # 0.995 → 예전 1.0
    assert corp(dict(common, op=[9.9, 0, 0], iec=10.0))["fl"]["icr"] == 0.9
    assert corp(dict(common, op=[3.0, 0, 0], iec=10.0))["fl"]["icr"] == 0.3                   # 0.3 은 0.3 (부동소수 오차로 0.2 가 되지 않게)
    assert corp(dict(common, op=[-4.1, 0, 0], iec=10.0))["fl"]["icr"] == -0.5                 # 내림
    assert "fl" not in corp(dict(common, op=[10.0, 0, 0], iec=10.0))                           # 1.0 이면 경고 아님
