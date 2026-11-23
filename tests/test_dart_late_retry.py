# -*- coding: utf-8 -*-
"""2026-11-24 (#180 · 감사: 11-21 corp.json 의 bq 가 3Q 마감 닷새 뒤에도 2,244곳 모두 2026.2Q · 3Q 0곳): DART 마감 뒤 매일 다시 묻기.

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 시험은 그대로):
- 마감을 다음 한국 거래일로 밀기 (주말 · 휴장일 표 · 표가 덮지 않는 날) — fetch_data.report_deadline_rolled
- 매일 다시 묻는 창의 경계 (마감 7일 전 · 밀린 마감 + 21일 · 휴장일로 밀린 마감 · 사업보고서) — dart_late_window · dart_late_due (예전 규칙
  dart_entry_due 가 묻는 날에는 쓰지 않아요)
- 정말 물을 항목만 (dart_late_want · dart_fin_fs): 사업보고서는 모든 회사 · '현재' 분기는 그 회사의 사업보고서와 같은 재무제표 하나 · '현재'보다
  새 분기는 상위 100곳만
- 실행당 한도는 부른 횟수로 (실패한 답도 · 한 실행에서 한 키는 한 번) · 계획은 시가총액 큰 회사부터 — dart_late_plan · DartClient.report
- DART 를 부르지 않는 실행 · 연결 안 됨 · 020 · 빈 캐시 · full 실행 · 가짜 클라이언트: 늘어난 창으로 부르지 않아요 (전체 DART 실행에 더하지 않아요)
- enrich_with_dart: DART 의 재무제표 API 가 마감 뒤에 채워져도 다음 날 실행이 그 분기를 '현재'로 써요 · '현재'로 쓴 뒤에도 작은 회사를 매일
  다시 물어요 · 한도에 걸리면 다음 실행이 가장 오래전에 물은 것부터 · 로그의 '!!' 와 '남김' 은 정말 물을 항목만 · corp.json qPick 기록
- 예전 규칙(늘어난 창을 끈 실행 = main)과 나란히: 창 안에서는 어느 날에도 예전 규칙보다 늦게 찾지 않아요 (일찍 '현재' · 2Q 창이 끝날 때 ·
  사업보고서 + 점검 중 · 휴장일 주) · lt 가 예전 규칙의 날짜를 밀지 않아요 · 둘째 셈은 계획한 항목만
- 관문 줄 '분기 판단 (corp.json qPick · 경고만)': 마감 + 10일 경계 · 휴장일로 밀린 마감 · qPick 없는 예전 파일 · 모양이 틀린 기록 · 검사가 멈춰도
  경고만 (어느 경우에도 실패 없음) · 올해 1Q~3Q 만 · 관문의 마감 계산이 fetch_data 와 같아요
"""
import collections
import datetime as dt
import inspect
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

D = dt.date
HOL = F.load_market_holidays()
KR, END = HOL["KR"], HOL["end"]
Q3, Q2, Q1, ANN = "11014", "11012", "11013", "11011"


def e013(at):
    return {"st": "013", "at": at, "d": None}


def every(corp, year, reprt, tag):
    return True


# ── 마감 밀기 ────────────────────────────────────────────────
def test_rolled_deadline_weekend_holiday_and_table_end():
    assert F.report_deadline_rolled(2026, Q3, KR, END) == D(2026, 11, 16)      # 토요일 11-14 → 월요일
    assert F.report_deadline_rolled(2026, Q3) == D(2026, 11, 16)               # 표 없이도 주말은 밀어요
    assert F.report_deadline_rolled(2026, Q2, KR, END) == D(2026, 8, 14)       # 금요일 그대로
    assert F.report_deadline_rolled(2026, ANN, KR, END) == D(2027, 3, 31)      # 2026년 사업보고서 마감 (수요일)
    # 2027 반기: 8-14 토 → 8-15 일 → 8-16 광복절 대체 휴일 (표) → 8-17 화
    assert F.report_deadline_rolled(2027, Q2, KR, END) == D(2027, 8, 17)
    assert F.report_deadline_rolled(2027, Q2) == D(2027, 8, 16)                # 표가 없으면 주말만
    # 평일 휴장일 하나 (만든 표)
    assert F.report_deadline_rolled(2026, Q1, {D(2026, 5, 15)}, D(2026, 12, 31)) == D(2026, 5, 18)
    assert F.report_deadline_rolled(2026, Q1, {D(2026, 5, 15)}, D(2025, 12, 31)) == D(2026, 5, 15)   # 표가 덮지 않는 해


# ── 창의 경계 ───────────────────────────────────────────────
@pytest.mark.parametrize("today,want", [
    (D(2026, 11, 6), False),     # 마감 7일 전의 전날
    (D(2026, 11, 7), True),      # 마감 7일 전 (밀지 않은 11-14 기준 · 예전과 같아요)
    (D(2026, 11, 19), True),     # 밀린 마감 11-16 + 3일 (예전 규칙은 7일마다)
    (D(2026, 12, 7), True),      # 밀린 마감 + 21일
    (D(2026, 12, 8), False),     # 그다음 날부터 7일마다
    (D(2026, 9, 30), False),     # 분기가 끝나지 않음
])
def test_late_window_boundaries_3q(today, want):
    assert F.dart_late_window(2026, Q3, today, KR, END) is want


@pytest.mark.parametrize("today,want", [
    (D(2027, 3, 23), False), (D(2027, 3, 24), True),     # 사업보고서: 마감 3-31 의 7일 전
    (D(2027, 4, 21), True), (D(2027, 4, 22), False),     # 3-31 + 21일
])
def test_late_window_boundaries_annual(today, want):
    assert F.dart_late_window(2026, ANN, today, KR, END) is want


def test_late_window_holiday_deadline_uses_the_table():
    # 2027 반기: 밀린 마감 8-17 (휴장일 표) → 9-07 까지 · 표가 없으면 밀린 마감 8-16 → 9-06 까지
    assert F.dart_late_window(2027, Q2, D(2027, 9, 7), KR, END) is True
    assert F.dart_late_window(2027, Q2, D(2027, 9, 8), KR, END) is False
    assert F.dart_late_window(2027, Q2, D(2027, 9, 7)) is False
    assert F.dart_late_window(2027, Q2, D(2027, 9, 6)) is True


def test_late_due_entry_rules():
    due, late = F.dart_entry_due, F.dart_late_due
    e = e013("2026-11-16")
    # 11-17: 예전 규칙은 묻지 않아요 (test_pipeline 의 '마감+3일부턴 다시 7일' 그대로) · 늘어난 창이 물어요
    assert due(e, 2026, Q3, D(2026, 11, 17)) is False
    assert late(e, 2026, Q3, D(2026, 11, 17), KR, END) is True
    assert late(e013("2026-11-19"), 2026, Q3, D(2026, 11, 20), KR, END) is True
    assert late(e013("2026-11-19"), 2026, Q3, D(2026, 11, 19), KR, END) is False   # 오늘 이미 물었어요 (저장된 답 기준 하루 한 번)
    assert late(e013("2026-12-07"), 2026, Q3, D(2026, 12, 8), KR, END) is False    # 창이 끝났어요
    # 예전 규칙이 묻는 날에는 늘어난 창을 쓰지 않아요 (한도를 쓰지 않게): 마감 주간 · 7일 지남
    assert late(e013("2026-11-12"), 2026, Q3, D(2026, 11, 13), KR, END) is False
    assert due(e013("2026-11-12"), 2026, Q3, D(2026, 11, 13)) is True
    assert late(e013("2026-11-16"), 2026, Q3, D(2026, 11, 23), KR, END) is False
    assert due(e013("2026-11-16"), 2026, Q3, D(2026, 11, 23)) is True
    assert late({"st": "000", "at": "2026-11-16", "d": {}}, 2026, Q3, D(2026, 11, 19), KR, END) is False
    assert late(None, 2026, Q3, D(2026, 11, 19), KR, END) is False
    # 사업보고서: 마감 + 2일(4-02) 뒤에도 4-21 까지 매일
    assert late(e013("2027-04-05"), 2026, ANN, D(2027, 4, 6), KR, END) is True
    assert late(e013("2027-04-20"), 2026, ANN, D(2027, 4, 22), KR, END) is False


# ── 정말 물을 항목 ───────────────────────────────────────────
def fin_entry(**d):
    return {"st": "000", "at": "2026-04-01", "d": d}


def test_fin_fs_follows_dart_financials():
    ent = {"A|2025|11011|CFS": fin_entry(_fin={"rev": [1.0]}, debt=1.0),
           "B|2025|11011|CFS": fin_entry(_cap=[1.0]), "B|2025|11011|OFS": fin_entry(_fin={"rev": [1.0]}, debt=1.0),
           "C|2025|11011|CFS": e013("2026-04-01"), "C|2025|11011|OFS": fin_entry(_fin={"rev": [1.0]}),
           "E|2025|11011|CFS": fin_entry(debt=1.0)}
    assert F.dart_fin_fs(ent, "A", 2025) == "CFS"
    assert F.dart_fin_fs(ent, "B", 2025) == "OFS"     # 자본금만 읽힌 연결은 못 찾음 (dart_financials 처럼)
    assert F.dart_fin_fs(ent, "C", 2025) == "OFS"
    assert F.dart_fin_fs(ent, "D", 2025) is None      # 사업보고서가 없으면 그해 분기를 묻지 않아요
    assert F.dart_fin_fs(ent, "E", 2025) is None      # _fin 없음 → 분기를 묻지 않아요
    assert F.dart_fin_fs(ent, "A", 2024) is None


def test_want_picks_only_what_the_run_asks():
    fs = {"A": "CFS", "B": "OFS"}.get
    w = F.dart_late_want(2026, (Q3, Q2, Q1), (), frozenset({"A"}), fs)
    assert w("A", 2026, Q3, "CFS") and not w("A", 2026, Q3, "OFS")
    assert w("B", 2026, Q3, "OFS") and not w("B", 2026, Q3, "CFS")
    assert not w("Z", 2026, Q3, "CFS")                  # 사업보고서가 없는 회사: 분기를 묻지 않아요
    assert w("Z", 2025, ANN, "CFS") and w("Z", 2025, ANN, "OFS")   # 사업보고서는 모든 회사
    assert not w("A", 2025, Q3, "CFS")                  # 다른 해 분기
    n = F.dart_late_want(2026, (Q2, Q1), (Q3,), frozenset({"A"}), fs)
    assert n("A", 2026, Q3, "CFS") and n("A", 2026, Q3, "OFS")    # '현재'보다 새 분기: 상위 100곳만, 연결 · 별도
    assert not n("B", 2026, Q3, "OFS")
    q = F.dart_late_want(2026, (), (Q3,), frozenset({"A"}), None, annual=False)   # 분기 판단의 둘째 셈: 그 분기만
    assert q("A", 2026, Q3, "CFS") and not q("A", 2025, ANN, "CFS")


def test_second_count_in_april_does_not_take_annual_entries(tmp_path, monkeypatch, capsys):
    # 2027-04-10: 1Q 는 창 밖 (5-08 부터) · 사업보고서는 창 안 — 둘째 셈의 계획에 사업보고서가 섞이면 '물음 0회' 줄이 나왔을 거예요
    ent = {f"C{i}|2026|{ANN}|{fs}": e013("2027-04-05") for i in range(6) for fs in ("CFS", "OFS")}
    ent.update({f"C{i}|2027|{Q1}|CFS": e013("2027-04-05") for i in range(6)})
    c, calls = client_with(tmp_path, monkeypatch, D(2027, 4, 10), ent)
    F.dart_late_start(c, TARGETS, CMAP)
    assert F.dart_late_set(c, F.dart_late_want(2027, (), (Q1,), frozenset(CMAP.values()), None, annual=False)) == (0, 0)
    assert F.dart_late_set(c, F.dart_late_want(2027, (), (), frozenset(), None)) == (12, 0)


# ── 계획 ────────────────────────────────────────────────────
def plan_entries():
    ent = {}
    for i in range(6):
        for fs in ("CFS", "OFS"):
            ent[f"C{i}|2026|{Q3}|{fs}"] = e013("2026-11-16")
    ent[f"C5|2026|{Q3}|OFS"] = {"st": "000", "at": "2026-11-17", "d": {"rev": [1.0]}}     # 별도만 내는 회사: 연결은 언제나 없음
    ent[f"C0|2026|{Q3}|DIV2"] = e013("2026-11-16")                                          # 재무제표 항목만
    ent["C9|2026|11014|CFS"] = e013("2026-11-16")                                           # 오늘 조회하지 않는 회사
    ent[f"C1|2025|{Q3}|CFS"] = e013("2025-11-16")                                           # 창 밖
    return ent


def test_plan_caps_by_market_cap_cfs_first_and_skips_asked():
    rank = {f"C{i}": i for i in range(6)}
    ask, rest = F.dart_late_plan(plan_entries(), D(2026, 11, 19), rank, every, KR, END, cap=3)
    assert ask == [f"C0|2026|{Q3}|CFS", f"C0|2026|{Q3}|OFS", f"C1|2026|{Q3}|CFS"]
    assert rest == [f"C1|2026|{Q3}|OFS"] + [f"C{i}|2026|{Q3}|{fs}" for i in (2, 3, 4) for fs in ("CFS", "OFS")]
    ask, rest = F.dart_late_plan(plan_entries(), D(2026, 11, 19), {f"C{i}": 5 - i for i in range(6)}, every, KR, END)
    assert ask[0] == f"C4|2026|{Q3}|CFS" and not rest and len(ask) == 10 and all("C5|" not in k for k in ask)
    ask, _ = F.dart_late_plan(plan_entries(), D(2026, 11, 19), rank, every, KR, END, asked={f"C0|2026|{Q3}|CFS"})
    assert f"C0|2026|{Q3}|CFS" not in ask and len(ask) == 9
    only_cfs = (lambda corp, y, r, tag: tag == "CFS")
    assert len(F.dart_late_plan(plan_entries(), D(2026, 11, 19), rank, only_cfs, KR, END)[0]) == 5
    assert F.DART_LATE_PER_RUN == 300 and F.DART_LATE_DAYS == 21


# ── DartClient ───────────────────────────────────────────────
def fake_get(filed, status_of=None):
    calls = []

    def get(self, endpoint, params, timeout=25):
        key = (params["corp_code"], params.get("fs_div"))
        calls.append(key)
        st = (status_of or {}).get(key) or ("000" if key in filed else "013")
        with self.lock:
            self.status[st] += 1
            if st in F.DART_FATAL and not self.fatal:
                self.fatal = (st, "test")
        if st in F.DART_FATAL:
            return None
        return {"status": st, "list": [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": "1e10", "thstrm_add_amount": "1e10"}]
                if st == "000" else []}
    return get, calls


def client_with(tmp_path, monkeypatch, today, entries, filed=(), status_of=None):
    get, calls = fake_get(set(filed), status_of)
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=today, path=str(tmp_path / "c.json.gz"))
    c.entries = dict(entries)
    c.started_empty = False
    c.hol = HOL
    return c, calls


TARGETS = [{"t": f"T{i}", "cap": float(10 - i)} for i in range(6)]
CMAP = {f"T{i}": f"C{i}" for i in range(6)}


def test_client_asks_only_planned_entries_once_and_counts(tmp_path, monkeypatch):
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries(), filed={("C0", "CFS")})
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 3)
    assert F.dart_late_start(c, TARGETS, CMAP) is True and c.late_left == 3
    assert F.dart_late_set(c, every) == (3, 7)
    assert c.late_keys == {f"C0|2026|{Q3}|CFS", f"C0|2026|{Q3}|OFS", f"C1|2026|{Q3}|CFS"}
    assert F.dart_quarter(c, "C0", 2026, Q3)["rev"] == 100.0                  # 계획 안 · 이제 나왔어요 (별도는 묻지 않아요)
    assert F.dart_quarter(c, "C1", 2026, Q3) is None                          # 계획 안 (연결) · 아직 없음 · 별도는 계획 밖
    assert F.dart_quarter(c, "C3", 2026, Q3) is None                          # 계획 밖 (한도)
    assert calls == [("C0", "CFS"), ("C1", "CFS")] and c.late_left == 1
    assert c.late_n == {"found": 1, "still": 1}
    assert F.dart_quarter(c, "C1", 2026, Q3) is None and len(calls) == 2      # 하루 한 번
    assert c.entries[f"C0|2026|{Q3}|CFS"]["st"] == "000" and c.entries[f"C0|2026|{Q3}|CFS"]["at"] == "2026-11-19"
    # 아직 없음: 예전 규칙의 날짜(at)는 그대로, 늘어난 창으로 물은 날은 lt (리뷰 2차 S2)
    assert c.entries[f"C1|2026|{Q3}|CFS"]["at"] == "2026-11-16" and c.entries[f"C1|2026|{Q3}|CFS"]["lt"] == "2026-11-19"


def test_failed_answers_use_the_cap_and_are_not_asked_again_in_the_run(tmp_path, monkeypatch):
    # 점검 중(800) 같은 답은 저장하지 않아요 — 예전엔 둘째 셈이 같은 항목을 또 물어 한도의 두 배까지 불렀어요
    st800 = {(f"C{i}", fs): "800" for i in range(6) for fs in ("CFS", "OFS")}
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries(), status_of=st800)
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 4)
    F.dart_late_start(c, TARGETS, CMAP)
    F.dart_late_set(c, every)
    for _ in range(2):
        for i in range(6):
            F.dart_quarter(c, f"C{i}", 2026, Q3)
    assert len(calls) == 4 and c.late_n == {"fail": 4} and c.late_left == 0
    assert F.dart_late_set(c, every) == (0, 6)            # 남은 호출 0 · 이미 물은 4건(C0 · C1 연결 · 별도)은 계획에도 다시 들지 않아요
    assert len(c.late_asked) == 4


def test_a_020_stops_late_calls(tmp_path, monkeypatch):
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries(), status_of={("C0", "CFS"): "020"})
    F.dart_late_start(c, TARGETS, CMAP)
    F.dart_late_set(c, every)
    for i in range(6):
        F.dart_quarter(c, f"C{i}", 2026, Q3)
    assert calls == [("C0", "CFS")] and c.late_n == {"fail": 1} and c.fatal[0] == "020"
    with pytest.raises(RuntimeError, match="일일 한도 초과"):
        c.raise_if_fatal()


def test_no_call_down_full_empty_cache_and_fake_clients_never_use_the_late_window(tmp_path, monkeypatch):
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries(), filed={("C0", "CFS")})
    F.dart_late_start(c, TARGETS, CMAP)
    F.dart_late_set(c, every)
    c.no_call = "같은 기준일 다시 하기"           # DART 를 부르지 않는 실행: 계획이 있어도 묻지 않아요
    assert F.dart_quarter(c, "C0", 2026, Q3) is None and not calls and not c.late_n
    for mode, empty, down in (("full", False, None), ("cache", True, None), ("cache", False, "ConnectTimeout")):
        c2, _ = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries())
        c2.mode, c2.started_empty, c2.down = mode, empty, down
        assert F.dart_late_start(c2, TARGETS, CMAP) is False      # 켜지 않아요 (빈 캐시 · full 은 어차피 모두 물어요)
        assert F.dart_late_set(c2, every) == (0, 0) and c2.late_keys == frozenset() and c2.late_rank is None

    class Fake:
        mode, started_empty, no_call, down, fatal = "cache", False, None, None, None
    assert F.dart_late_start(Fake(), TARGETS, CMAP) is False


def test_plan_failure_is_loud_and_falls_back_to_the_old_rule(tmp_path, monkeypatch, capsys):
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries())

    def boom(*a, **k):
        raise ValueError("깨진 항목")
    F.dart_late_start(c, TARGETS, CMAP)
    monkeypatch.setattr(F, "dart_late_plan", boom)
    assert F.dart_late_set(c, every) == (0, 0)
    assert c.late_keys == frozenset() and "!! DART 마감 뒤 매일 다시 묻기 계획을 세우지 못했어요" in capsys.readouterr().out
    assert F.dart_quarter(c, "C0", 2026, Q3) is None and not calls


# ── enrich_with_dart: DART 의 재무제표 API 가 마감 뒤에 채워지는 분기 ──
N = 150


def rows(amount):
    return [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": str(amount), "frmtrm_amount": str(amount * 0.9),
             "bfefrmtrm_amount": str(amount * 0.8), "thstrm_add_amount": str(amount)},
            {"account_nm": "당기순이익", "sj_div": "IS", "thstrm_amount": str(amount / 10), "frmtrm_amount": "1",
             "bfefrmtrm_amount": "1", "thstrm_add_amount": str(amount / 10)},
            {"account_nm": "자본총계", "sj_div": "BS", "thstrm_amount": str(amount * 5)},
            {"account_nm": "부채총계", "sj_div": "BS", "thstrm_amount": str(amount * 2)}]


def lagging_dart(calls, q3_from, fail=None):
    """q3_from(i) → 회사 i 의 2026.3Q 숫자가 DART API 에 뜨는 날 (None = 안 뜸) · fail(오늘, i, 연도, 보고서) → 그 답 상태 (800 · 020 …)."""
    def get(self, endpoint, params, timeout=25):
        i = int(params["corp_code"][1:])
        y, r, fs = int(params["bsns_year"]), params["reprt_code"], params.get("fs_div")
        calls[self.today.isoformat()] += 1
        st = fail(self.today, i, y, r) if fail else None
        if st:
            with self.lock:
                self.status[st] += 1
                if st in F.DART_FATAL and not self.fatal:
                    self.fatal = (st, "test")
            return None if st in F.DART_FATAL else {"status": st, "list": []}
        filed = False
        if endpoint.startswith("fnltt") and fs == "CFS":
            if r == ANN:
                filed = self.today >= D(y + 1, 3, 25)
            elif (y, r) == (2026, Q3):
                d0 = q3_from(i)
                filed = d0 is not None and self.today >= d0
            else:
                filed = i < N * 0.8 and self.today >= F.report_deadline(y, r) - dt.timedelta(days=5)
        st = "000" if filed else "013"
        with self.lock:
            self.status[st] += 1
        return {"status": st, "list": rows(1e11) if filed else []}
    return get


def run_days(monkeypatch, tmp_path, days, q3_from=None, fail=None, caps=None, modes=None, name="c.json.gz"):
    calls = collections.Counter()
    q3_from = q3_from or (lambda i: D(2026, 11, 18) if i < N * 0.8 else None)
    monkeypatch.setattr(F.DartClient, "get", lagging_dart(calls, q3_from, fail))
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {f"{i:06d}": f"C{i}" for i in range(N)})
    out = {}
    for d in days:
        cap = (caps or {}).get(d) or (lambda i: float(N - i))
        stocks = [{"t": f"{i:06d}", "cls": "kr", "cap": cap(i), "shr": 1_000_000, "price": 10000.0} for i in range(N)]
        c = F.DartClient("k", mode=(modes or {}).get(d, "cache"), today=d, path=str(tmp_path / name))
        try:
            _, fin = F.enrich_with_dart(stocks, c)
        except RuntimeError:
            fin = {}
        out[d] = (collections.Counter(v.get("bq") for v in fin.values()), c, calls[d.isoformat()], fin)
    return out


def on_3q(fin, idx):
    return sum(1 for i in idx if (fin.get(f"{i:06d}") or {}).get("bq") == "2026.3Q")


def test_quarter_adopted_the_day_after_dart_fills_in(monkeypatch, tmp_path, capsys):
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 17), D(2026, 11, 19), D(2026, 11, 20)]
    out = run_days(monkeypatch, tmp_path, days)
    bq16, c16, *_ = out[D(2026, 11, 16)]
    assert bq16["2026.3Q"] == 0 and c16.q_pick == {"v": 1, "cur": "2026.2Q", "top": 100, "filed": {"2026.3Q": 0, "2026.2Q": 100}}
    bq17, c17, *_ = out[D(2026, 11, 17)]
    assert c17.late_n == {"still": 200} and bq17["2026.3Q"] == 0       # 상위 100곳 연결 · 별도 다시 물음 (아직 없음)
    bq19, c19, *_ = out[D(2026, 11, 19)]
    # 예전 규칙이면 11-23 까지 묻지 않아 2Q 에 남았어요. 이제 11-19 실행이 상위 회사를 다시 물어 3Q 를 '현재'로 써요
    assert c19.late_n == {"found": 100} and bq19["2026.3Q"] == 120 and c19.q_pick["cur"] == "2026.3Q"
    _, c20, n20, _ = out[D(2026, 11, 20)]
    assert c20.late_n == {"still": 30} and n20 == 30      # '현재'로 쓴 뒤에도 안 낸 30곳(그 회사의 재무제표 하나씩)을 매일
    log = capsys.readouterr().out
    assert "DART 마감 뒤 매일 다시 묻기 창: 2026.3Q 마감 2026-11-14 → 다음 거래일 2026-11-16 · 아직 없는 재무제표 항목을 2026-12-07 까지" in log
    assert "오늘 다시 물음 100회 → 새로 냄 100 · 아직 없음 0 · 다음 실행으로 남김 0건" in log
    assert "계획 200건 · 물음 100회 · 제출 0곳 → 100곳" in log


def test_small_companies_found_the_day_their_numbers_show_up(monkeypatch, tmp_path):
    # 리뷰 (Opus S1 · Fable S2): 큰 회사로 일찍 '현재'가 되면 작은 회사는 그날 처음 묻고 '아직 없음' → 예전엔 7일 뒤. 이제 매일
    def q3(i):                     # 100~119: 작은 회사 20곳은 11-21 에 · 120 부터는 지난 분기도 없어 TTM 을 만들 수 없는 회사 (가짜 DART)
        if i < 100:
            return D(2026, 11, 18)
        if i < 120:
            return D(2026, 11, 21)
        return None
    days = [D(2026, 11, 10)] + [D(2026, 11, d) for d in range(16, 31) if D(2026, 11, d).weekday() != 6]
    out = run_days(monkeypatch, tmp_path, days, q3)
    for d in days[1:]:
        lag = on_3q(out[d][3], range(100, 120))
        assert lag == (20 if d >= D(2026, 11, 21) else 0), (d, lag)     # 숫자가 뜬 날의 실행에 바로 3Q (예전 규칙은 11-25)
        assert sum(out[d][1].late_n.values()) <= F.DART_LATE_PER_RUN + F.DART_LATE_INUSE_PER_RUN


# ── 예전 규칙과 나란히: 창 안에서는 어느 날에도 예전 규칙보다 늦게 찾지 않아요 (리뷰 2차) ──
M = 240


def hh(i, salt):
    import hashlib
    return int(hashlib.md5(f"{salt}:{i}".encode()).hexdigest(), 16) % 10000 / 10000.0


def spread(i, salt, table):
    u, lo = hh(i, salt), 0.0
    for hi, d0, n in table:
        if u < hi:
            return d0 + dt.timedelta(days=int((u - lo) / (hi - lo) * n))
        lo = hi
    return None


def window_dart(calls, target, appear, fail=None):
    """가짜 DART (회사 M 곳): target (연도, 보고서) 의 숫자는 appear(i) 에 뜨고, 그보다 뒤 분기는 없고, 나머지는 마감 3일 전에 있어요. 60번째부터
    셋에 하나는 별도만 내요. fail(오늘, i, 연도, 보고서) → '800' 이면 그 답은 점검 중."""
    def get(self, endpoint, params, timeout=25):
        i = int(params["corp_code"][1:])
        y, r, fs = int(params["bsns_year"]), params["reprt_code"], params.get("fs_div")
        calls[self.today.isoformat()] += 1
        if fail and fail(self.today, i, y, r):
            with self.lock:
                self.status["800"] += 1
            return {"status": "800", "list": []}
        filed = False
        if endpoint.startswith("fnltt") and fs == ("OFS" if i >= 60 and i % 3 == 0 else "CFS"):
            if (y, r) == target:
                d0 = appear(i)
                filed = d0 is not None and self.today >= d0
            elif r == ANN:
                filed = self.today >= D(y + 1, 3, 25)
            elif y == target[0] and r != ANN and F.report_period_end(y, r) > F.report_period_end(*target):
                filed = False
            else:
                filed = self.today >= F.report_deadline(y, r) - dt.timedelta(days=3)
        st = "000" if filed else "013"
        with self.lock:
            self.status[st] += 1
        return {"status": st, "list": rows(1e11) if filed else []}
    return get


def tue_sat(a, b):
    out, d = [], a
    while d <= b:
        if d.weekday() in (1, 2, 3, 4, 5):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def side_by_side(monkeypatch, tmp_path, target, label, days, appear, fail=None):
    """같은 가짜 DART 로 이 PR 과 예전 규칙(늘어난 창을 끈 실행 = main)을 따로 돌려 → {날: (이 PR 의 회사 집합, 예전 규칙의 회사 집합, 늘어난 창 호출 수)}."""
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {f"{i:06d}": f"C{i}" for i in range(M)})
    stocks = (lambda: [{"t": f"{i:06d}", "cls": "kr", "cap": float(M - i), "shr": 1_000_000, "price": 10000.0} for i in range(M)])
    res = {}
    start = F.dart_late_start
    for name, on in (("pr", True), ("old", False)):
        calls = collections.Counter()
        monkeypatch.setattr(F.DartClient, "get", window_dart(calls, target, appear, fail))
        monkeypatch.setattr(F, "dart_late_start", start if on else (lambda *a, **k: False))
        for d in days:
            c = F.DartClient("k", today=d, path=str(tmp_path / f"{name}.json.gz"))
            _, fin = F.enrich_with_dart(stocks(), c)
            res.setdefault(d, {})[name] = ({t for t, v in fin.items() if v.get("bq") == label}, sum(c.late_n.values()), calls[d.isoformat()])
    monkeypatch.setattr(F, "dart_late_start", start)
    return res


def assert_never_behind(res, cap):
    for d, r in res.items():
        pr, old = r["pr"][0], r["old"][0]
        assert old <= pr, (d, sorted(old - pr)[:10])
        assert r["pr"][1] <= cap and r["old"][1] == 0


@pytest.fixture
def small_caps(monkeypatch):
    # 실제 비율로 줄여요: 회사 2,474곳에 300 · 2,500 → 회사 240곳에 12 · 240 (한도가 늘 걸리는 쪽으로)
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 12)
    monkeypatch.setattr(F, "DART_LATE_INUSE_PER_RUN", M)
    return 12 + M


def test_never_behind_old_rule_when_adopted_early_with_slow_small_companies(monkeypatch, tmp_path, small_caps):
    # 3Q 2026: 상위 100곳은 60% 가 11-14 까지, 나머지는 11-17~20 → 이 PR 은 11-17 쯤, 예전 규칙은 11-24 에 '현재' · 작은 회사는 12-05 까지 천천히
    def appear(i):
        if i < 100:
            return D(2026, 11, 12) if hh(i, "t") < 0.6 else spread(i, "t2", [(1.0, D(2026, 11, 17), 4)])
        return spread(i, "q", [(0.45, D(2026, 11, 12), 5), (0.80, D(2026, 11, 17), 6), (0.97, D(2026, 11, 23), 13)])
    days = [D(2026, 11, 7)] + tue_sat(D(2026, 11, 10), D(2026, 12, 12))
    res = side_by_side(monkeypatch, tmp_path, (2026, Q3), "2026.3Q", days, appear)
    assert_never_behind(res, small_caps)
    assert any(len(r["pr"][0]) > len(r["old"][0]) for r in res.values())


def test_never_behind_old_rule_after_the_window_closes_2q(monkeypatch, tmp_path, small_caps):
    # 2Q 2026 (마감 08-14 금 · 창은 09-04 까지): 창이 끝난 뒤에도 예전 규칙의 7일 주기가 그대로라 늦지 않아요 (at 을 그대로 두니까요)
    def appear(i):
        if i < 100:
            return D(2026, 8, 11)
        return spread(i, "q", [(0.40, D(2026, 8, 11), 5), (0.80, D(2026, 8, 18), 14), (0.95, D(2026, 9, 2), 10)])
    days = [D(2026, 8, 1)] + tue_sat(D(2026, 8, 4), D(2026, 9, 19))
    assert_never_behind(side_by_side(monkeypatch, tmp_path, (2026, Q2), "2026.2Q", days, appear), small_caps)


def test_never_behind_old_rule_for_the_annual_report(monkeypatch, tmp_path, small_caps):
    # 2026 사업보고서 (마감 2027-03-31 수 · 창은 04-21 까지) · 04-08 하루는 점검 중(800)
    def appear(i):
        return spread(i, "q", [(0.80, D(2027, 3, 15), 16), (0.90, D(2027, 4, 1), 7), (0.96, D(2027, 4, 8), 12), (0.99, D(2027, 4, 20), 8)])
    days = [D(2027, 3, 13)] + tue_sat(D(2027, 3, 16), D(2027, 5, 8))
    res = side_by_side(monkeypatch, tmp_path, (2026, ANN), "2026.4Q", days, appear,
                       fail=lambda t, i, y, r: t == D(2027, 4, 8))
    assert_never_behind(res, small_caps)


def test_never_behind_old_rule_in_a_holiday_week(monkeypatch, tmp_path, small_caps):
    # 2Q 2027: 08-14 토 → 08-16 광복절 대체 휴일 → 밀린 마감 08-17 (휴장일 표) · 숫자는 창이 끝나는 09-07 전에 모두 떠요. 창이 끝난 뒤 처음 뜨는
    # 회사는 두 쪽의 7일 주기 요일이 다르면 며칠 늦을 수 있어요 (알려진 예외 · RUNBOOK)
    def appear(i):
        if i < 100:
            return D(2027, 8, 12) if hh(i, "t") < 0.55 else spread(i, "t2", [(1.0, D(2027, 8, 17), 3)])
        return spread(i, "q", [(0.50, D(2027, 8, 12), 6), (0.85, D(2027, 8, 18), 10), (0.96, D(2027, 8, 28), 10)])
    days = [D(2027, 8, 3)] + tue_sat(D(2027, 8, 4), D(2027, 9, 18))
    assert_never_behind(side_by_side(monkeypatch, tmp_path, (2027, Q2), "2027.2Q", days, appear), small_caps)


def test_late_asks_never_move_the_old_rule_date(tmp_path, monkeypatch):
    # 리뷰 2차 S2: lt 는 늘어난 창만 봐요. 예전 규칙(at)은 main 과 같은 날 물어요 · lt 가 없는 예전 캐시도 그대로
    e = {"st": "013", "at": "2026-11-16", "lt": "2026-11-22", "d": None}
    assert F.dart_entry_due(e, 2026, Q3, D(2026, 11, 23)) is True          # at + 7일 = main 과 같은 날
    assert F.dart_late_due(e, 2026, Q3, D(2026, 11, 22), KR, END) is False   # 오늘 이미 늘어난 창으로 물었어요
    assert F.dart_late_due(e, 2026, Q3, D(2026, 11, 23), KR, END) is False   # 예전 규칙이 물어요 (늘어난 창은 쓰지 않아요)
    assert F.dart_late_asked_on(e) == D(2026, 11, 22) and F.dart_late_asked_on(e013("2026-11-16")) == D(2026, 11, 16)
    assert F.dart_late_asked_on({"st": "013", "at": "2026-11-16", "lt": None}) == D(2026, 11, 16)
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 23), {f"C0|2026|{Q3}|CFS": e})
    assert F.dart_quarter(c, "C0", 2026, Q3, fs="CFS") is None and calls == [("C0", "CFS")]
    assert c.entries[f"C0|2026|{Q3}|CFS"] == {"st": "013", "at": "2026-11-23", "d": None}   # 예전 규칙이 물으면 at 만 (lt 는 지나간 날)
    assert not c.late_n


def test_plan_rotates_oldest_first(tmp_path):
    ent = {f"C{i}|2026|{Q3}|CFS": {"st": "013", "at": "2026-11-16", "lt": f"2026-11-{18 if i < 3 else 17}", "d": None} for i in range(6)}
    rank = {f"C{i}": i for i in range(6)}
    ask, rest = F.dart_late_plan(ent, D(2026, 11, 19), rank, every, KR, END, cap=3)
    assert ask == [f"C{i}|2026|{Q3}|CFS" for i in (3, 4, 5)] and rest == [f"C{i}|2026|{Q3}|CFS" for i in (0, 1, 2)]


def test_second_count_asks_only_planned_keys(monkeypatch, tmp_path):
    # 리뷰 2차 S3 (exp_dbl): 상위 99곳은 예전 규칙이 묻는 날 (7일) · 1곳만 늘어난 창 · 3Q 가 모두 점검 중(800) → 예전엔 둘째 셈이 99곳을 또 물어
    # 398회 (main 198). 이제 계획한 1곳의 2회만 더해요
    import gzip
    import json
    out = run_days(monkeypatch, tmp_path, [D(2026, 11, 10), D(2026, 11, 16)], q3_from=lambda i: None)
    path = str(tmp_path / "c.json.gz")
    js = json.load(gzip.open(path, "rt"))
    for k, e in js["entries"].items():
        p = k.split("|")
        if len(p) == 4 and p[1] == "2026" and p[2] == Q3 and e["st"] == "013" and int(p[0][1:]) < 99:
            e["at"] = "2026-11-12"
    json.dump(js, gzip.open(path, "wt"))
    q3 = collections.Counter()

    def get(self, endpoint, params, timeout=25):
        st = "013"
        if (int(params["bsns_year"]), params["reprt_code"]) == (2026, Q3):
            q3["n"] += 1
            st = "800"
        with self.lock:
            self.status[st] += 1
        return {"status": st, "list": []}
    monkeypatch.setattr(F.DartClient, "get", get)
    stocks = [{"t": f"{i:06d}", "cls": "kr", "cap": float(N - i), "shr": 1_000_000, "price": 10000.0} for i in range(N)]
    c = F.DartClient("k", today=D(2026, 11, 19), path=path)
    F.enrich_with_dart(stocks, c)
    assert q3["n"] == 198 + 2 and c.late_n == {"fail": 2} and len(c.late_asked) == 2


def test_cap_counts_calls_and_leaves_the_rest_for_the_next_run(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 50)
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 19), D(2026, 11, 20), D(2026, 11, 21)]
    out = run_days(monkeypatch, tmp_path, days)
    for d in days[2:]:
        assert sum(out[d][1].late_n.values()) <= 50
    # 11-19: 큰 25곳의 연결 · 별도 50건을 계획 → 연결로 25곳 나옴 (25%) · 남은 것은 다음 실행
    assert out[D(2026, 11, 19)][1].q_pick["filed"]["2026.3Q"] == 25 and out[D(2026, 11, 19)][1].q_pick["cur"] == "2026.2Q"
    assert out[D(2026, 11, 20)][1].q_pick["filed"]["2026.3Q"] == 50 and out[D(2026, 11, 20)][1].q_pick["cur"] == "2026.2Q"
    assert out[D(2026, 11, 21)][1].q_pick["filed"]["2026.3Q"] == 75 and out[D(2026, 11, 21)][1].q_pick["cur"] == "2026.3Q"
    log = capsys.readouterr().out
    assert "  !! 분기 판단: 2026.3Q 이 70% 가 안 돼 상위 회사의 아직 없는 항목을 다시 물어요 — 계획 50건 (한도 밖 150건)" in log
    assert "  !! DART 마감 뒤 매일 다시 묻기: 오늘 다시 물음 25회 → 새로 냄 25 · 아직 없음 0 · 다음 실행으로 남김 150건" in log


def test_failures_in_the_quarter_choice_stay_under_the_cap(monkeypatch, tmp_path):
    # 리뷰 (Fable S1): 11-17 에 3Q 가 점검 중(800) — 예전엔 첫 셈 200 + 둘째 셈 200 = 400회 (한도 300)
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 300)
    fail = (lambda t, i, y, r: "800" if t == D(2026, 11, 19) and (y, r) == (2026, Q3) else None)
    out = run_days(monkeypatch, tmp_path, [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 19)], fail=fail)
    c = out[D(2026, 11, 19)][1]
    assert c.late_n == {"fail": 200} and len(c.late_asked) == 200 and c.late_left == 100


def test_full_and_empty_cache_runs_make_zero_late_calls(monkeypatch, tmp_path):
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 19)]
    out = run_days(monkeypatch, tmp_path, days, modes={D(2026, 11, 19): "full"})
    c = out[D(2026, 11, 19)][1]
    assert c.late_rank is None and not c.late_n and not c.late_asked and c.q_pick["cur"] == "2026.3Q"
    out = run_days(monkeypatch, tmp_path, [D(2026, 11, 19)], name="empty.json.gz")
    c = out[D(2026, 11, 19)][1]
    assert c.started_empty and c.late_rank is None and not c.late_n


def test_a_020_in_the_quarter_choice_stops_the_run(monkeypatch, tmp_path):
    fail = (lambda t, i, y, r: "020" if t == D(2026, 11, 19) and (y, r) == (2026, Q3) else None)
    out = run_days(monkeypatch, tmp_path, [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 19)], fail=fail)
    _, c, n, _ = out[D(2026, 11, 19)]
    assert c.fatal[0] == "020" and c.late_n == {"fail": 1} and n <= 5    # 첫 020 뒤로는 부르지 않아요 (동시에 나간 몇 회만)


def test_logs_only_count_what_a_run_will_ask(monkeypatch, tmp_path, capsys):
    # 리뷰 (Opus S2 · Fable S3): 상위 100곳에서 빠진 회사의 새 분기 항목은 아무 실행도 묻지 않아요 → '남김' · '!!' 에 넣지 않아요
    drop = (lambda i: float(N - i) - (150 if i < 10 else 0))
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 19), D(2026, 11, 20)]
    out = run_days(monkeypatch, tmp_path, days, q3_from=lambda i: None, caps={D(2026, 11, 19): drop, D(2026, 11, 20): drop})
    log = capsys.readouterr().out
    assert out[D(2026, 11, 19)][1].late_n == {"still": 180}    # 지금 상위 100곳 중 3Q 항목이 있는 90곳 (새로 든 10곳은 처음 묻기)
    assert "· DART 마감 뒤 매일 다시 묻기: 오늘 다시 물음 180회 → 새로 냄 0 · 아직 없음 180 · 다음 실행으로 남김 0건" in log
    assert "다음 실행으로 남김 20건" not in log
    # 둘째 셈에 물을 것이 없으면 (오늘 이미 물었으면) 그 줄을 쓰지 않아요 — '0건을 다시 물었어요' 같은 '!!' 가 없어요
    out2 = run_days(monkeypatch, tmp_path, [D(2026, 11, 20)], q3_from=lambda i: None, caps={D(2026, 11, 20): drop})
    log2 = capsys.readouterr().out
    assert "아직 없는 항목을 다시 물어요" not in log2 and not out2[D(2026, 11, 20)][1].late_n


def test_qpick_goes_into_corp_json_and_the_app_is_not_told():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert 'corp["qPick"] = client.q_pick' in src
    for dp, _, fs in os.walk(os.path.join(ROOT, "src")):
        for f in fs:
            if f.endswith((".js", ".jsx")):
                assert "qPick" not in open(os.path.join(dp, f), encoding="utf-8").read()


# ── 관문 줄 ─────────────────────────────────────────────────
def corp_with(cur=None, filed=None, bq=None, qpick=True):
    comps = [{"t": f"{i:06d}", "cap": float(200 - i), "bq": bq} for i in range(150)]
    c = {"companies": comps}
    if qpick:
        c["qPick"] = {"v": 1, "cur": cur, "top": 100, "filed": filed or {}}
    return c


def row(corp, today):
    rep = V.Report()
    V.check_q_pick(rep, corp, today)
    assert len(rep.rows) == 1 and rep.rows[0][0] == V.Q_PICK_ROW and not rep.failed
    return rep.rows[0]


def test_gate_row_boundary_ten_days_after_the_rolled_deadline():
    c = corp_with("2026.2Q", {"2026.3Q": 64, "2026.2Q": 98})
    assert row(c, D(2026, 11, 26))[3] == "PASS"          # 밀린 마감 11-16 + 10일
    r = row(c, D(2026, 11, 27))
    assert r[3] == "WARN" and "2026.3Q 마감 2026-11-14 → 2026-11-16 뒤 11일인데 아직 2026.2Q 기준" in r[1] \
        and "2026.3Q 낸 상위 100곳: 64곳 (64%)" in r[1]
    assert row(corp_with("2026.3Q", {"2026.3Q": 81}), D(2026, 11, 27))[3] == "PASS"
    assert "아직 앞 분기" in row(c, D(2026, 11, 23))[1]     # 마감은 지났지만 10일 전: 글자로만
    assert row(corp_with(None, {"2026.1Q": 10}), D(2026, 5, 20))[3] == "PASS"     # 1Q 마감 + 10일 전 (5-15 + 10)
    assert row(corp_with(None, {"2026.1Q": 10}), D(2026, 5, 26))[3] == "WARN"
    r = row(corp_with(None), D(2026, 2, 1))          # 1월 ~ 5월 말: 볼 분기가 없어요 (사업보고서는 보지 않아요)
    assert r[3] == "PASS" and "확인할 분기 없음 (2026년 1Q 마감 + 10일 전)" in r[1] and "사업보고서는 보지 않아요" in r[2]


def test_gate_row_uses_the_holiday_table():
    # 2027 반기: 8-14 토 → 8-17 (8-16 광복절 대체 휴일) → 8-27 까지 통과, 8-28 경고
    c = corp_with("2027.1Q", {"2027.2Q": 50})
    assert row(c, D(2027, 8, 27))[3] == "PASS"
    assert row(c, D(2027, 8, 28))[3] == "WARN"
    assert V.q_pick_rolled(D(2027, 8, 14), set(), None) == D(2027, 8, 16)


def test_gate_row_old_file_reads_bq_and_bad_records_warn():
    old = corp_with(bq="2026.2Q", qpick=False)
    r = row(old, D(2026, 11, 27))
    assert r[3] == "WARN" and "bq 로 본 2026.3Q: 상위 100곳 중 0곳" in r[1]
    assert row(corp_with(bq="2026.3Q", qpick=False), D(2026, 11, 27))[3] == "PASS"
    for bad in ({"v": 2}, {"v": 1, "cur": "3Q", "top": 100, "filed": {}}, {"v": 1, "cur": None, "top": 0, "filed": {}},
                {"v": 1, "cur": None, "top": 100, "filed": {"2026.3Q": 101}}, "x"):
        c = corp_with()
        c["qPick"] = bad
        r = row(c, D(2026, 11, 27))
        assert r[3] == "WARN" and "모양이 잘못됨" in r[1]


def test_gate_row_only_warns_when_its_own_check_crashes(monkeypatch):
    r = row(corp_with("2026.2Q"), None)              # 날짜가 없으면 검사가 멈춰요
    assert r[3] == "WARN" and "검사가 오류로 멈췄어요" in r[1]

    def boom(*a, **k):
        raise RuntimeError("표 없음")
    monkeypatch.setattr(V, "load_holidays", boom)    # 휴장일 표를 못 읽으면 주말만 봐요 (경고만)
    r = row(corp_with("2026.2Q", {"2026.3Q": 1}), D(2026, 11, 27))
    assert r[3] == "WARN" and "휴장일 표를 읽지 못해 주말만 봤어요" in r[1]


def test_gate_row_is_in_run_checks_and_matches_fetch_data_deadlines():
    assert "check_q_pick(rep, corp, today)" in inspect.getsource(V.run_checks)
    hol, end = V.load_holidays()
    for y in (2026, 2027, 2028):
        for n, r in ((1, Q1), (2, Q2), (3, Q3)):
            assert D(y, *V.Q_PICK_DEADLINE[n]) == F.report_deadline(y, r)
            assert V.q_pick_rolled(F.report_deadline(y, r), hol["KR"], end) == F.report_deadline_rolled(y, r, KR, END)
    assert V.Q_PICK_SHARE == round(F.QUARTER_CURRENT_SHARE * 100)


# ── 하루 DART 호출 수 (리뷰 3차 S1) ─────────────────────────────
def test_dry_runs_get_only_the_300_cap(monkeypatch, tmp_path, capsys):
    # 시험 실행은 '현재' 분기의 더한 호출 수를 쓰지 않아요 — 같은 날 발행할 몫을 쓰지 않게 (길은 그대로 지나요)
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 5)
    monkeypatch.setattr(F, "DART_LATE_INUSE_PER_RUN", N)
    q3 = (lambda i: D(2026, 11, 14) if i < 100 else (D(2026, 11, 21) if i < 120 else None))   # 11-16 에 예전 규칙으로 '현재'
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 17)]
    live = run_days(monkeypatch, tmp_path, days, q3)
    assert live[D(2026, 11, 16)][1].q_pick["cur"] == "2026.3Q"
    assert sum(live[D(2026, 11, 17)][1].late_n.values()) == 50          # 아직 없는 50곳 모두 (5 + 150 안)
    capsys.readouterr()
    monkeypatch.setenv("DRY_RUN", "true")
    dry = run_days(monkeypatch, tmp_path, days, q3, name="dry.json.gz")
    assert sum(dry[D(2026, 11, 17)][1].late_n.values()) == 5 and dry[D(2026, 11, 17)][1].late_dry
    assert "시험 실행(DRY_RUN): '현재' 분기 2026.3Q 의 더한 호출" in capsys.readouterr().out


def test_day_count_survives_save_and_load_and_restarts_after_midnight_kst(tmp_path, monkeypatch):
    path = str(tmp_path / "c.json.gz")
    days = iter([D(2026, 11, 24), D(2026, 11, 24), D(2026, 11, 25)])
    c = F.DartClient("k", today=D(2026, 11, 24), path=path)
    assert "dartDay" not in c.meta and c.day_calls() == {"d": "2026-11-24", "n": 0}   # 예전 보관본: 0 부터 (날짜 = 실행을 시작한 한국 날짜)
    c.now_day = lambda: next(days)
    c.status["000"] += 7
    c.save()                                                       # 11-24: 7
    c.status["013"] += 3
    c.save()                                                       # 11-24: 7 + 3
    assert c.meta["dartDay"] == {"d": "2026-11-24", "n": 10}
    c2 = F.DartClient("k", today=D(2026, 11, 24), path=path)
    c2.now_day = lambda: D(2026, 11, 24)
    assert c2.day_calls() == {"d": "2026-11-24", "n": 10}          # 저장 · 읽기 뒤에도
    c2.status["000"] += 4
    assert c2.day_calls() == {"d": "2026-11-24", "n": 14}          # 이 실행의 아직 적지 않은 수까지
    c.status["000"] += 5
    c.save()                                                       # 한국 자정을 넘긴 저장: 새 날짜에서 0 부터 + 5
    assert c.meta["dartDay"] == {"d": "2026-11-25", "n": 5}
    c3 = F.DartClient("k", today=D(2026, 11, 26), path=path)
    c3.now_day = lambda: D(2026, 11, 26)
    assert c3.day_calls()["n"] == 0
    for bad in ({"d": "2026-11-26", "n": -3}, {"d": "2026-11-26", "n": "9"}, {"d": "2026-11-26", "n": True}, "x"):
        c3.meta["dartDay"] = bad
        assert c3.day_calls()["n"] == 0                            # 읽지 못하는 기록은 0 부터 (많게 세지도 막지도 않아요)


def test_a_busy_day_turns_late_asks_off_but_not_the_old_rule(tmp_path, monkeypatch, capsys):
    ent = dict(plan_entries())
    ent[f"C0|2026|{Q3}|CFS"] = e013("2026-11-12")                  # 예전 규칙이 오늘 물어요 (7일)
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), ent)
    c.now_day = lambda: D(2026, 11, 19)
    c.meta["dartDay"] = {"d": "2026-11-19", "n": F.DART_LATE_DAY_STOP + 1}
    assert F.dart_late_start(c, TARGETS, CMAP) is False and c.late_rank is None
    assert "!! DART 마감 뒤 매일 다시 묻기를 이번 실행에서 쉬어요: 오늘(KST 2026-11-19) 이 보관본의 DART 호출이 벌써 10,001회" in capsys.readouterr().out
    F.dart_quarter(c, "C0", 2026, Q3)
    F.dart_quarter(c, "C1", 2026, Q3)
    assert calls == [("C0", "CFS")] and not c.late_n                # 예전 규칙의 조회만
    c.meta["dartDay"] = {"d": "2026-11-18", "n": 50_000}            # 어제의 수는 오늘을 막지 않아요
    assert F.dart_late_start(c, TARGETS, CMAP) is True
    c.meta["dartDay"] = {"d": "2026-11-19", "n": F.DART_LATE_DAY_STOP - 5}
    c.status["013"] += 10                                           # 이 실행이 벌써 부른 수도 세요
    assert F.dart_late_start(c, TARGETS, CMAP) is False


def test_full_and_empty_cache_runs_still_count_the_day(monkeypatch, tmp_path):
    # 빈 캐시 · full 실행은 늘어난 창을 쓰지 않아 기준이 필요 없지만, 그 호출은 그날의 수에 들어가요 (뒤의 실행이 봐요)
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 19)]
    out = run_days(monkeypatch, tmp_path, days, modes={D(2026, 11, 19): "full"})
    c = out[D(2026, 11, 19)][1]
    assert c.late_rank is None and c.meta["dartDay"]["n"] == out[D(2026, 11, 19)][2] > 0
    out = run_days(monkeypatch, tmp_path, [D(2026, 11, 19)], name="empty.json.gz")
    c = out[D(2026, 11, 19)][1]
    assert c.started_empty and c.late_rank is None and c.meta["dartDay"]["n"] == out[D(2026, 11, 19)][2] > 0
