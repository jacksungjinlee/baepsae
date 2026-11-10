"""v19.1e: 배당 분할 확인용 자본금을 더 많은 이름으로 읽어요 (Jack, 2026-11-07).

2026-11-07 국내 배당 종목 1,220곳 중 132곳의 배당을 확인하지 못했고, 그중 47곳은 재무상태표의 자본금 줄을 못 읽어서였어요
('보통주자본금' 기아 · '(1) 자본금' 고려아연 · '납입자본' 삼성에스디에스 · 손익 줄을 못 알아봐 3년 원값과 함께 버려진 자본금
카카오뱅크 · 롯데케미칼). 자본금은 이제 _cap 에 따로 담고, 자본금 없이 캐시에 저장된 사업보고서만 한 번 다시 받아요.
"""
import collections
import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_data as F  # noqa: E402


def bs(nm, a, b=None, c=None, aid="ifrs-full_IssuedCapital", sj="BS"):
    b = a if b is None else b
    c = b if c is None else c
    return {"account_nm": nm, "account_id": aid, "sj_div": sj,
            "thstrm_amount": str(a), "frmtrm_amount": str(b), "bfefrmtrm_amount": str(c)}


# ── 1. 이름 ─────────────────────────────────────────────
@pytest.mark.parametrize("nm", ["자본금", "(1) 자본금", "Ⅰ. 자본금", "I. 자본금", "1. 자본금", "IV.자본금", "자본금(주석15)", "자본 금"])
def test_company_capital_under_its_numbered_and_spaced_names(nm):
    got = F.parse_capital([bs(nm, 1e10)])
    assert got == {"cs3": [100.0, 100.0, 100.0], "k": "all", "src": "total"}


def test_common_capital_is_marked_common_and_preferred_capital_is_never_added():
    kia = F.parse_capital([bs("보통주자본금", 2139317000000)])                      # 기아: 보통주자본금 (id IssuedCapital) 뿐
    assert kia["k"] == "common" and kia["src"] == "common" and kia["cs3"][0] == 21393.17
    kt = F.parse_capital([bs("자본금, 보통주", 49019283000, aid="ifrs-full_IssuedCapitalOrdinaryShares")])   # 케이티알파
    assert kt["k"] == "common"
    # 우선주 자본금은 더하지 않아요: 더한 줄이 상장되지 않은 상환전환우선주이거나 상장 우선주가 다른 이름이면 합이 실제보다
    # 작아져요 (리뷰 2026-11-07). 보통주만이면 아래 끝도 오늘 보통주 수로만 계산해서 늘 맞아요
    both = F.parse_capital([bs("보통주자본금", 7.78e11, aid="dart_IssuedCapitalOfCommonStock"),
                            bs("우선주자본금", 1.22e11, aid="dart_IssuedCapitalOfPreferredStock")])
    assert both == {"cs3": [7780.0, 7780.0, 7780.0], "k": "common", "src": "common"}
    rcps = F.parse_capital([bs("보통주자본금", 500e8, aid="x"), bs("상환전환우선주자본금", 5e8, aid="x"), bs("종류주식자본금", 100e8, aid="x")])
    assert rcps["k"] == "common" and rcps["cs3"][0] == 500.0
    assert F.cap_kind("종류주식자본금", "x") == "pref" and F.cap_kind("우선주자본금", "x") == "pref"


def test_paid_in_capital_only_when_nothing_better_and_never_for_the_impairment_check():
    sds = [bs("납입자본", 38688900000), bs("보통주납입자본", 38688900000, aid="dart_IssuedCapitalOfCommonStock")]
    assert F.parse_capital(sds)["src"] == "paid"                                   # 삼성에스디에스: 이름에 납입자본 → 올해만
    tbh = F.parse_capital([bs("보통주납입자본", 10428409500)])                       # TBH글로벌: 보통주 납입자본
    assert tbh["src"] == "paid" and tbh["k"] == "common"
    kc = [bs("납입자본", 122789687434, 192789687434), bs("보통주자본금", 25954226000, aid="dart_IssuedCapitalOfCommonStock")]
    assert F.parse_capital(kc)["cs3"][0] == 259.5423                               # 한국카본: 주식발행초과금이 섞인 납입자본은 안 써요
    both = [bs("납입자본", 4053578000000, aid="-표준계정코드 미사용-"), bs("자본금", 3209820000000)]
    assert F.parse_capital(both)["src"] == "total"
    dongsuh = F.parse_capital([bs("납입자본", 49850000000)])
    assert dongsuh["src"] == "paid" and dongsuh["k"] == "all"
    # 자본잠식 확인(_fin.cs)은 예전처럼 '자본금' 줄만: 납입자본으로 자본잠식을 경고하지 않아요
    rows = [bs("매출액", 1e11, sj="IS"), bs("자본총계", 4e10), bs("납입자본", 5e10)]
    out = F.parse_dart_list(rows)
    assert out["_fin"]["cs"] is None and out["_cap"]["src"] == "paid"


def test_lines_that_are_not_capital_are_never_read_as_capital():
    rows = [bs("자본잉여금", 5e10), bs("기타자본", 3e10), bs("자본총계", 9e10), bs("비지배지분자본금", 1e9),
            bs("자본금", 7e10, sj="CF"), bs("자본금", 7e10, sj="IS"), bs("자본금 합계", 1e9)]
    assert F.parse_capital(rows) is None
    assert F.parse_capital([bs("자본금", 0), bs("우선주자본금", 0)]) is None       # 0 원 자본금은 없는 것과 같아요
    ss = F.parse_capital([bs("Ⅰ. 자본금", 1e10), bs("Ⅱ. 자본잉여금", 3e10, 2e10, 1e10)])
    assert ss["ss3"] == [300.0, 200.0, 100.0]                                       # 번호가 붙은 자본잉여금도


def test_the_new_read_equals_the_old_one_wherever_the_old_one_found_capital():
    rows = [bs("매출액", 1e11, sj="IS"), bs("자본금", 897514000000), bs("보통주자본금", 778047000000, aid="dart_IssuedCapitalOfCommonStock"),
            bs("우선주자본금", 119467000000, aid="dart_IssuedCapitalOfPreferredStock"), bs("자본잉여금", 4.4e12)]
    out = F.parse_dart_list(rows)                                                   # 삼성전자처럼 '자본금'과 종류별 줄이 함께
    assert out["_cap"]["cs3"] == out["_fin"]["cs3"] and out["_cap"]["ss3"] == out["_fin"]["ss3"]


def test_paid_in_capital_is_never_used_to_compare_earlier_years():
    """리뷰 2026-11-07 (막는 문제였어요): 주식발행초과금으로 1:1 무상증자를 하면 주식 수는 두 배인데 납입자본(자본금 + 주식발행초과금)은
    그대로예요. 납입자본의 비를 주식 수의 비로 보면 앞 해 배당(옛 기준 1,000원)을 '그대로'로 잘못 봐서 [500, 1000, 1000] — 없는
    배당 삭감이 생겨요. 납입자본은 올해 아래 끝에만 쓰고, 앞 해는 배당 받은 주식 수의 비와 액면분할 확인으로만 판단해요."""
    paid = F.parse_capital([bs("납입자본", 11_000e6)])
    assert paid["src"] == "paid"
    bas = {"cash3": [18e6 * 500, 10e6 * 1000, 10e6 * 1000], "par3": [500.0] * 3, "eps3": [None] * 3, "ni3": [None] * 3}
    r = F.div_basis([500.0, 1000.0, 1000.0], bas, paid["cs3"], 20e6, (), None, cap_k=paid["k"], cap_src=paid["src"])
    assert r["f0"] == 1.0 and r["st3"][0] == "same"
    assert r["dps3a"][1:] != [1000.0, 1000.0] and r["st3"][1] != "same" and r["divSt"] != "same"   # 앞 해는 판단하지 않아요
    exact = F.div_basis([500.0, 1000.0, 1000.0], bas, [100.0, 50.0, 50.0], 20e6, (), [10.0, 60.0, 60.0])
    assert exact["st3"] == ["same", "adj", "adj"] and exact["dps3a"] == [500.0, 500.0, 500.0]      # 진짜 자본금이면 맞춰요
    # 앞 해 현금배당금총액이 비어 있어도 '그대로'로 보지 않아요
    bas2 = {"cash3": [20e6 * 500, None, None], "par3": [500.0] * 3, "eps3": [None] * 3, "ni3": [None] * 3}
    r2 = F.div_basis([500.0, 1000.0, 1000.0], bas2, paid["cs3"], 20e6, (), None, cap_k="all", cap_src="paid")
    assert r2["st3"][1:] == ["nd", "nd"] and r2["dps3a"][1:] == [None, None]
    # 예전처럼 납입자본 비교를 했다면 틀렸을 거예요 (이 시험이 무엇을 막는지)
    wrong = F.div_basis([500.0, 1000.0, 1000.0], bas, paid["cs3"], 20e6, (), None)
    assert wrong["st3"] == ["same", "same", "same"]


def test_the_pipeline_passes_the_paid_in_source_through_to_the_check():
    """리뷰 2026-11-07: apply_div_basis 가 _cap 의 src 를 div_basis 에 넘기지 않으면 위의 구멍이 다시 열려요. 파이프라인 경로 그대로 확인."""
    bas = {"cash3": [18e6 * 500, 10e6 * 1000, 10e6 * 1000], "par3": [500.0] * 3, "eps3": [None] * 3, "ni3": [None] * 3}
    s = {"t": "000300", "nk": "가", "cls": "kr", "price": 10000.0, "shr": 20e6, "dps": 500.0, "dps3": [500.0, 1000.0, 1000.0],
         "_bas": bas, "_cap": F.parse_capital([bs("보통주납입자본", 11_000e6)])}
    F.apply_div_basis([s], {}, {})
    assert s["dps3a"] == [500.0, None, None] and s["divSt"] == "nd" and s["dyt"] == 5.0
    assert F.parse_capital([bs("납입자본", 1e10), bs("우선주자본금", 1e9)])["k"] == "common"   # 우선주 줄이 따로 있으면 보통주만으로


def test_common_share_capital_still_compares_earlier_years():
    """보통주자본금은 액면가 × 보통주 수라 해마다의 비가 주식 수의 비예요: 2:1 액면분할도 맞춰요."""
    cap = F.parse_capital([bs("보통주자본금", 1e10, 1e10, 1e10)])
    bas = {"cash3": [20e6 * 500, 10e6 * 1000, 10e6 * 1000], "par3": [500.0, 1000.0, 1000.0], "eps3": [None] * 3, "ni3": [None] * 3}
    r = F.div_basis([500.0, 1000.0, 1000.0], bas, cap["cs3"], 20e6, (), None, cap_k=cap["k"], cap_src=cap["src"])
    assert r["st3"] == ["same", "adj", "adj"] and r["dps3a"] == [500.0, 500.0, 500.0]


# ── 2. 손익 줄 없이도 자본금 ─────────────────────────────
def test_a_bank_statement_keeps_its_capital_without_revenue_lines():
    rows = [bs("자본금", 2385057000000, 2384843000000, 2384361000000), bs("자본총계", 6.5e12), bs("부채총계", 6e13)]
    out = F.parse_dart_list(rows)                                                   # 카카오뱅크: 매출·영업이익·순이익 줄이 없어요
    # v19.1f (2026-11-08): 손익 줄이 없어도 재무상태표 값은 남겨요 (예전엔 _fin 을 통째로 버렸어요) — 손익 칸은 빈 칸 그대로
    assert out["_fin"]["eq"] == 65000.0 and out["_fin"]["rev"] == [None, None, None] and out["debt"] is not None
    assert out["_cap"]["cs3"] == [23850.57, 23848.43, 23843.61]


class FakeDart:
    def __init__(self, by_fs):
        self.by_fs, self.calls = by_fs, []

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        self.calls.append(tag)
        rows = self.by_fs.get(tag)
        return parse(rows) if rows is not None else None


def test_a_capital_only_consolidated_statement_still_falls_through_to_the_separate_one():
    cfs = [bs("자본금", 1e10)]                                                      # 연결: 자본금 말고는 아무것도 못 읽음
    ofs = [bs("매출액", 1e11, sj="IS"), bs("자본총계", 4e10), bs("부채총계", 2e10), bs("자본금", 2e10)]
    d = F.dart_financials(FakeDart({"CFS": cfs, "OFS": ofs}), "C1", 2025)
    assert d["debt"] == 50.0 and d["_cap"]["cs3"][0] == 200.0                       # 예전처럼 별도 재무제표를 써요
    assert F.dart_financials(FakeDart({"CFS": cfs}), "C1", 2025) == {}               # 자본금만으로는 '찾음'이 아니에요


# ── 3. 캐시: 자본금 없이 저장된 항목만 한 번 다시 받기 ─────────
def counting_get(status="000", rows=None):
    calls = []

    def get(self, endpoint, params, timeout=25):
        calls.append((params["corp_code"], params.get("fs_div")))
        with self.lock:
            self.status[status] += 1
        return {"status": status, "list": rows if rows is not None else [bs("매출액", 1e11, sj="IS"), bs("자본총계", 4e10),
                                                                          bs("부채총계", 2e10), bs("보통주자본금", 1e10)]}
    return get, calls


def seed(c, corp, d, at="2026-11-01", **extra):
    c.entries[f"{corp}|2025|11011|CFS"] = {"st": "000", "at": at, "d": d, **extra}


def test_an_old_entry_without_capital_is_fetched_once_and_marked(tmp_path, monkeypatch):
    get, calls = counting_get()
    monkeypatch.setattr(F.DartClient, "get", get)
    path = str(tmp_path / "c.json.gz")
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=path)
    seed(c, "C1", {"debt": 50.0, "_fin": {"rev": [1000.0, None, None], "cs": None}})       # v19.1e 이전: 보통주자본금을 못 읽음
    seed(c, "C2", {"debt": 50.0, "_fin": {"rev": [1000.0, None, None], "cs3": [100.0, 100.0, 100.0]}})   # '자본금'은 읽었어요
    d1 = F.dart_financials(c, "C1", 2025)
    d2 = F.dart_financials(c, "C2", 2025)
    assert d1["_cap"]["k"] == "common" and "_cap" not in d2
    assert calls == [("C1", "CFS")] and c.redone == 1
    assert c.entries["C1|2025|11011|CFS"]["rp"] == F.CAP_REDO_TAG
    assert "자본금 다시 읽기 1건 시도 (실행당 최대 800): 새로 읽음 1" in c.summary()
    c.save()
    c2 = F.DartClient("k", today=dt.date(2026, 11, 9), path=path)
    F.dart_financials(c2, "C1", 2025)
    assert len(calls) == 1 and c2.redone == 0                                        # 다음 실행엔 다시 받지 않아요


def test_a_refetch_that_finds_nothing_keeps_the_old_entry_and_waits(tmp_path, monkeypatch):
    get, calls = counting_get(status="013", rows=[])
    monkeypatch.setattr(F.DartClient, "get", get)
    path = str(tmp_path / "c.json.gz")
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=path)
    old = {"debt": 50.0, "_fin": {"rev": [1000.0, None, None]}}
    seed(c, "C1", old)
    assert F.dart_financials(c, "C1", 2025)["debt"] == 50.0
    e = c.entries["C1|2025|11011|CFS"]
    assert e["st"] == "000" and e["d"] == old and "rp" not in e and c.redo_kept == 1   # 찾은 보고서를 '없음'으로 바꾸지 않아요
    assert e["rpTry"] == "2026-11-08" and c.redone == 0
    assert "찾은 보고서가 없다고 해 예전 값을 둔 1" in c.summary() and "새로 읽음 0" in c.summary()
    c.save()
    n = len(calls)
    c2 = F.DartClient("k", today=dt.date(2026, 11, 10), path=path)                 # 이틀 뒤: 다시 받지 않아요 (매 실행 호출하지 않게)
    F.dart_financials(c2, "C1", 2025)
    assert len(calls) == n
    c3 = F.DartClient("k", today=dt.date(2026, 11, 15), path=path)                 # 7일 뒤: 다시 해 봐요
    F.dart_financials(c3, "C1", 2025)
    assert len(calls) == n + 1


def test_a_refetch_that_fails_to_connect_keeps_the_old_entry_unmarked(tmp_path, monkeypatch):
    calls = []

    def get(self, endpoint, params, timeout=25):
        calls.append(1)
        return None                                                                   # 연결 문제
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=str(tmp_path / "c.json.gz"))
    old = {"debt": 50.0}
    seed(c, "C1", old)
    assert F.dart_financials(c, "C1", 2025) == old
    e = c.entries["C1|2025|11011|CFS"]
    assert e["d"] == old and "rp" not in e and "rpTry" not in e and c.redo_failed == 1 and c.redone == 0
    assert "연결 문제·해석 오류 1" in c.summary()


def test_revalidation_and_full_mode_mark_entries_without_counting_a_redo(tmp_path, monkeypatch):
    get, calls = counting_get()
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=str(tmp_path / "c.json.gz"))
    seed(c, "C1", {"debt": 50.0}, at="2026-07-01")                                  # 90일 지남: 재확인이 받아요
    F.dart_financials(c, "C1", 2025)
    assert len(calls) == 1 and c.revalidated == 1 and c.redone == 0 and c.redo_left == F.DART_REDO_PER_RUN
    assert c.entries["C1|2025|11011|CFS"]["rp"] == F.CAP_REDO_TAG
    full = F.DartClient("k", mode="full", today=dt.date(2026, 11, 8), path=str(tmp_path / "f.json.gz"))
    seed(full, "C2", {"debt": 50.0})
    F.dart_financials(full, "C2", 2025)
    assert full.redone == 0 and full.entries["C2|2025|11011|CFS"]["rp"] == F.CAP_REDO_TAG


def test_the_backlog_counts_only_annual_statements_that_still_need_capital():
    today = dt.date(2026, 11, 8)
    e = lambda d, **x: {"st": "000", "at": "2026-11-01", "d": d, **x}
    entries = {
        "A|2025|11011|CFS": e({"debt": 1.0}),                                  # 다시 받을 것
        "B|2024|11011|OFS": e({"_fin": {"cs": None}}),                         # 다시 받을 것 (앞 해)
        "C|2025|11011|CFS": e({"debt": 1.0}, rp=F.CAP_REDO_TAG),              # 이미 새 해석
        "D|2025|11011|CFS": e({"_fin": {"cs3": [1.0, 1.0, 1.0]}}),            # '자본금'을 읽었어요
        "E|2025|11011|CFS": e({"debt": 1.0}, rpTry="2026-11-06"),             # 며칠 기다려요
        "F|2026|11014|CFS": e({"rev": 1.0}),                                   # 분기 보고서
        "G|2023|11011|CFS": e({"debt": 1.0}),                                  # 쓰지 않는 해
        "H|2025|11011|CFS": {"st": "013", "at": "2026-11-01", "d": None},      # 없음
    }
    assert F.capital_backlog(entries, (2025, 2024), today) == 2


def test_refetches_stay_within_the_per_run_limit_and_new_fetches_are_marked(tmp_path, monkeypatch):
    get, calls = counting_get()
    monkeypatch.setattr(F.DartClient, "get", get)
    monkeypatch.setattr(F, "DART_REDO_PER_RUN", 2)
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=str(tmp_path / "c.json.gz"))
    for i in range(4):
        seed(c, f"C{i}", {"debt": 50.0})
    for i in range(4):
        F.dart_financials(c, f"C{i}", 2025)
    assert c.redone == 2 and len(calls) == 2
    F.dart_financials(c, "NEW", 2025)                                               # 처음 받는 보고서는 새 해석이라 표시가 붙어요
    assert c.entries["NEW|2025|11011|CFS"]["rp"] == F.CAP_REDO_TAG


def test_no_refetch_while_dart_is_down_or_for_other_reports(tmp_path, monkeypatch):
    get, calls = counting_get()
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=dt.date(2026, 11, 8), path=str(tmp_path / "c.json.gz"))
    seed(c, "C1", {"debt": 50.0})
    c.down = "ConnectTimeout"
    F.dart_financials(c, "C1", 2025)
    assert c.redone == 0 and not calls
    c.down = None
    c.entries["C1|2026|11014|CFS"] = {"st": "000", "at": "2026-11-01", "d": {"rev": 1.0}}   # 분기 보고서는 다시 받지 않아요
    F.dart_quarter(c, "C1", 2026, "11014")
    assert not calls


def test_needs_capital():
    assert F.needs_capital({"debt": 1.0}) and F.needs_capital({"_fin": {"cs": None}}) and F.needs_capital({})
    assert not F.needs_capital({"_cap": {"cs3": [1.0, 1.0, 1.0]}}) and not F.needs_capital({"_fin": {"cs3": [1.0, None, None]}})
    assert not F.needs_capital(None)


# ── 4. 분할 확인 ─────────────────────────────────────────
def kia_bas(n=397_000_000, dps=6500.0, par=5000.0):
    return {"cash3": [n * dps] * 3, "par3": [par] * 3, "eps3": [None] * 3, "ni3": [None] * 3}


def test_kia_is_checked_with_its_common_share_capital():
    """기아: 보통주자본금 21,393억 ÷ 액면가 5,000원 = 4.28억 주 (발행), 배당 받은 주식 3.97억, 오늘 상장 3.93억 → 배율 1."""
    cap = F.parse_capital([bs("보통주자본금", 2139317000000)])
    r = F.div_basis([6500.0, 5600.0, 3500.0], kia_bas(), cap["cs3"], 393_000_000, (), None, cap_k=cap["k"])
    assert r["f0"] == 1.0 and r["divSt"] == "same"
    old = F.div_basis([6500.0, 5600.0, 3500.0], kia_bas(), None, 393_000_000, (), None)
    assert old["divSt"] == "nd"                                                     # 예전: 자본금을 못 읽어 확인 못 함


def test_common_only_capital_compares_common_shares_only():
    """보통주자본금만 있고 상장 우선주가 있으면 아래 끝은 오늘 보통주 수 ÷ 보통주 발행 주식 수. 우선주를 더하면 아래 끝이 커져
    맞는 배율 1 이 범위 밖으로 밀려나요."""
    bas = {"cash3": [100e6 * 1000 + 30e6 * 1050] * 3, "par3": [5000.0] * 3, "eps3": [None] * 3, "ni3": [None] * 3,
           "pdps": [[1050.0, 1050.0, 1050.0]]}
    cs3 = [100e6 * 5000 / 1e8] * 3                                                  # 보통주 1억 주 × 5,000원
    common = F.div_basis([1000.0, 1000.0, 1000.0], bas, cs3, 100e6, (30e6,), None, cap_k="common")
    assert common["f0"] == 1.0 and common["divSt"] == "same"
    wrong = F.div_basis([1000.0, 1000.0, 1000.0], bas, cs3, 100e6, (30e6,), None, cap_k="all")
    assert wrong["f0"] is None                                                      # 우선주까지 더하면 1.3 배라 판단 못 해요


def test_apply_div_basis_uses_the_capital_and_never_writes_it_out():
    s = {"t": "000270", "nk": "기아", "cls": "kr", "price": 120000.0, "shr": 393_000_000, "dps": 6500.0,
         "dps3": [6500.0, 5600.0, 3500.0], "_bas": kia_bas(), "_cap": F.parse_capital([bs("보통주자본금", 2139317000000)])}
    other = {"t": "005935", "nk": "삼성전자우", "cls": "kr", "_cap": {"cs3": [1.0, 1.0, 1.0], "k": "all"}}   # 우선주에도 남지 않게
    counts, _ = F.apply_div_basis([s, other], {}, {})
    assert s["divSt"] == "same" and s["dyt"] == round(6500 / 120000 * 100, 2)
    for x in (s, other):
        assert not [k for k in x if k.startswith("_")], x
    assert counts["same"] == 1


def test_the_old_capital_still_works_without_the_new_field():
    """v19.1e 이전 캐시 항목('자본금'을 읽은 _fin.cs3)은 다시 받지 않고 그대로 써요."""
    s = {"t": "000270", "nk": "기아", "cls": "kr", "price": 120000.0, "shr": 393_000_000, "dps": 6500.0,
         "dps3": [6500.0, 5600.0, 3500.0], "_bas": kia_bas()}
    F.apply_div_basis([s], {"000270": {"cs3": [21393.17] * 3}}, {})
    assert s["divSt"] == "same"


def test_capital_sources_are_logged_with_counts(capsys):
    stocks = []
    for i, cap in enumerate([F.parse_capital([bs("자본금", 2139317000000)]), F.parse_capital([bs("보통주자본금", 2139317000000)]), None]):
        stocks.append({"t": f"00{i + 2}270", "nk": "가", "cls": "kr", "price": 120000.0, "shr": 393_000_000, "dps": 6500.0,
                       "dps3": [6500.0, 5600.0, 3500.0], "_bas": kia_bas(), **({"_cap": cap} if cap else {})})
    F.apply_div_basis(stocks, {}, {})
    out = capsys.readouterr().out
    assert "!! 배당 분할 확인에 쓴 자본금 (배당한 종목): '자본금' 1 · 보통주자본금 1 · 납입자본(올해만 · 크게 잡힐 수 있음) 0 · 못 읽음 1" in out
