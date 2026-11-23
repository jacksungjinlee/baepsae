# -*- coding: utf-8 -*-
"""2026-11-24 (감사: 11-21 corp.json 의 bq 가 3Q 마감 닷새 뒤에도 2,244곳 모두 2026.2Q · 3Q 0곳): DART 마감 뒤 매일 다시 묻기.

여기서 보는 것 (네트워크 없음 · 더한 시험만 · 예전 시험은 그대로):
- 마감을 다음 한국 거래일로 밀기 (주말 · 휴장일 표 · 표가 덮지 않는 날) — fetch_data.report_deadline_rolled
- 매일 다시 묻는 창의 경계 (마감 7일 전 · 밀린 마감 + 2일 · 밀린 마감 + 21일 · '현재'로 쓴 분기와 아닌 분기 · 사업보고서) — dart_late_window ·
  dart_late_due (예전 규칙 dart_entry_due 가 묻는 날에는 쓰지 않아요)
- 실행당 한도 (시가총액 큰 회사부터 · 연결 먼저 · 다른 재무제표를 찾은 보고서와 오늘 조회하지 않는 회사는 빼요) — dart_late_plan
- DartClient: 계획에 든 항목만 · DART 를 부르지 않는 실행은 묻지 않아요 · 빈 캐시 · full 실행은 계획을 세우지 않아요 (전체 DART 실행이 아니에요)
- enrich_with_dart: DART 의 재무제표 API 가 마감 뒤에 채워져도 다음 날 실행이 그 분기를 '현재'로 써요 (예전엔 7일 뒤) · 한도에 걸리면 다음 실행이
  이어서 · '현재'로 쓴 뒤로는 7일마다 · corp.json qPick 기록
- 관문 줄 '분기 판단 (corp.json qPick · 경고만)': 마감 + 10일 경계 · 휴장일로 밀린 마감 · qPick 없는 예전 파일 · 모양이 틀린 기록 · 검사가 멈춰도
  경고만 (어느 경우에도 실패 없음) · 관문의 마감 계산이 fetch_data 와 같아요
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
@pytest.mark.parametrize("today,adopted,want", [
    (D(2026, 11, 6), False, False),     # 마감 7일 전의 전날
    (D(2026, 11, 7), False, True),      # 마감 7일 전 (밀지 않은 11-14 기준 · 예전과 같아요)
    (D(2026, 11, 18), True, True),      # 밀린 마감 11-16 + 2일: '현재'로 써도 매일
    (D(2026, 11, 19), True, False),     # 그다음 날: '현재'로 썼으면 7일마다로
    (D(2026, 11, 19), False, True),     # '현재'로 쓰지 않았으면 계속 매일
    (D(2026, 12, 7), False, True),      # 밀린 마감 + 21일
    (D(2026, 12, 8), False, False),     # 그다음 날부터 7일마다
    (D(2026, 9, 30), False, False),     # 분기가 끝나지 않음
])
def test_late_window_boundaries_3q(today, adopted, want):
    assert F.dart_late_window(2026, Q3, today, adopted, KR, END) is want


@pytest.mark.parametrize("today,want", [
    (D(2027, 3, 23), False), (D(2027, 3, 24), True),     # 사업보고서: 마감 3-31 의 7일 전
    (D(2027, 4, 21), True), (D(2027, 4, 22), False),     # 3-31 + 21일 (사업보고서는 '현재' 분기 선택이 없어 늘)
])
def test_late_window_boundaries_annual(today, want):
    assert F.dart_late_window(2026, ANN, today, False, KR, END) is want


def test_late_window_holiday_deadline_uses_the_table():
    # 2027 반기: 밀린 마감 8-17 (휴장일 표) → '현재'로 써도 8-19 까지 매일 · 표가 없으면 밀린 마감 8-16 → 8-18 까지
    assert F.dart_late_window(2027, Q2, D(2027, 8, 19), True, KR, END) is True
    assert F.dart_late_window(2027, Q2, D(2027, 8, 20), True, KR, END) is False
    assert F.dart_late_window(2027, Q2, D(2027, 8, 19), True) is False
    assert F.dart_late_window(2027, Q2, D(2027, 9, 7), False, KR, END) is True       # 8-17 + 21
    assert F.dart_late_window(2027, Q2, D(2027, 9, 8), False, KR, END) is False


def test_late_due_entry_rules():
    due, late = F.dart_entry_due, F.dart_late_due
    e = e013("2026-11-16")
    # 11-17: 예전 규칙은 묻지 않아요 (test_pipeline 의 '마감+3일부턴 다시 7일' 그대로) · 늘어난 창이 물어요 (밀린 마감 + 2일 안)
    assert due(e, 2026, Q3, D(2026, 11, 17)) is False
    assert late(e, 2026, Q3, D(2026, 11, 17), True, KR, END) is True
    assert late(e, 2026, Q3, D(2026, 11, 19), True, KR, END) is False     # '현재'로 썼고 밀린 마감 + 2일 뒤 → 7일마다
    assert late(e, 2026, Q3, D(2026, 11, 19), False, KR, END) is True     # '현재'로 쓰지 않았으면 매일
    assert late(e013("2026-11-19"), 2026, Q3, D(2026, 11, 19), False, KR, END) is False   # 오늘 이미 물었어요 (하루 한 번)
    assert late(e013("2026-12-07"), 2026, Q3, D(2026, 12, 8), False, KR, END) is False    # 창이 끝났어요
    # 예전 규칙이 묻는 날에는 늘어난 창을 쓰지 않아요 (한도를 쓰지 않게): 마감 주간 · 7일 지남
    assert late(e013("2026-11-12"), 2026, Q3, D(2026, 11, 13), False, KR, END) is False
    assert due(e013("2026-11-12"), 2026, Q3, D(2026, 11, 13)) is True
    assert late(e013("2026-11-16"), 2026, Q3, D(2026, 11, 23), False, KR, END) is False
    assert due(e013("2026-11-16"), 2026, Q3, D(2026, 11, 23)) is True
    assert late({"st": "000", "at": "2026-11-16", "d": {}}, 2026, Q3, D(2026, 11, 19), False, KR, END) is False
    assert late(None, 2026, Q3, D(2026, 11, 19), False, KR, END) is False
    # 사업보고서: 마감 + 2일(4-02) 뒤에도 4-21 까지 매일
    assert late(e013("2027-04-05"), 2026, ANN, D(2027, 4, 6), False, KR, END) is True
    assert late(e013("2027-04-20"), 2026, ANN, D(2027, 4, 22), False, KR, END) is False


# ── 실행당 한도 (계획) ───────────────────────────────────────
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


def test_plan_caps_by_market_cap_cfs_first():
    rank = {f"C{i}": i for i in range(6)}
    ask, rest = F.dart_late_plan(plan_entries(), D(2026, 11, 19), rank, closed=KR, end=END, cap=3)
    assert ask == [f"C0|2026|{Q3}|CFS", f"C0|2026|{Q3}|OFS", f"C1|2026|{Q3}|CFS"]
    assert rest == [f"C1|2026|{Q3}|OFS"] + [f"C{i}|2026|{Q3}|{fs}" for i in (2, 3, 4) for fs in ("CFS", "OFS")]
    ask, rest = F.dart_late_plan(plan_entries(), D(2026, 11, 19), {f"C{i}": 5 - i for i in range(6)}, closed=KR, end=END)
    assert ask[0] == f"C4|2026|{Q3}|CFS" and not rest and len(ask) == 10 and all("C5|" not in k for k in ask)
    # '현재'로 쓴 분기는 밀린 마감 + 2일 뒤로는 빠져요
    assert F.dart_late_plan(plan_entries(), D(2026, 11, 19), rank, {(2026, Q3)}, KR, END) == ([], [])
    assert len(F.dart_late_plan(plan_entries(), D(2026, 11, 18), rank, {(2026, Q3)}, KR, END)[0]) == 10
    # 기본 한도
    assert F.DART_LATE_PER_RUN == 300 and F.DART_LATE_DAYS == 21


# ── DartClient ───────────────────────────────────────────────
def fake_get(filed):
    calls = []

    def get(self, endpoint, params, timeout=25):
        calls.append((params["corp_code"], params.get("fs_div")))
        st = "000" if (params["corp_code"], params.get("fs_div")) in filed else "013"
        with self.lock:
            self.status[st] += 1
        return {"status": st, "list": [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": "1e10", "thstrm_add_amount": "1e10"}]
                if st == "000" else []}
    return get, calls


def client_with(tmp_path, monkeypatch, today, entries, filed=()):
    get, calls = fake_get(set(filed))
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=today, path=str(tmp_path / "c.json.gz"))
    c.entries = dict(entries)
    c.started_empty = False
    c.hol = HOL
    return c, calls


def test_client_asks_only_planned_entries_and_counts(tmp_path, monkeypatch):
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries(), filed={("C0", "CFS")})
    targets = [{"t": f"T{i}", "cap": float(10 - i)} for i in range(6)]
    cmap = {f"T{i}": f"C{i}" for i in range(6)}
    monkeypatch.setattr(F, "DART_LATE_PER_RUN", 3)
    F.dart_late_start(c, targets, cmap)
    assert c.late_keys == {f"C0|2026|{Q3}|CFS", f"C0|2026|{Q3}|OFS", f"C1|2026|{Q3}|CFS"} and c.late_rest == 7
    assert F.dart_quarter(c, "C0", 2026, Q3)["rev"] == 100.0                  # 계획 안 · 이제 나왔어요
    assert F.dart_quarter(c, "C1", 2026, Q3) is None                          # 계획 안 (연결) · 아직 없음 · 별도는 계획 밖
    assert F.dart_quarter(c, "C3", 2026, Q3) is None                          # 계획 밖 (한도)
    assert calls == [("C0", "CFS"), ("C1", "CFS")]
    assert c.late_n == {"found": 1, "still": 1}
    assert F.dart_quarter(c, "C1", 2026, Q3) is None and len(calls) == 2      # 하루 한 번
    assert c.entries[f"C0|2026|{Q3}|CFS"]["st"] == "000" and c.entries[f"C1|2026|{Q3}|CFS"]["at"] == "2026-11-19"


def test_no_call_down_full_and_empty_cache_never_use_the_late_window(tmp_path, monkeypatch):
    targets = [{"t": f"T{i}", "cap": float(10 - i)} for i in range(6)]
    cmap = {f"T{i}": f"C{i}" for i in range(6)}
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries(), filed={("C0", "CFS")})
    F.dart_late_start(c, targets, cmap)
    c.no_call = "같은 기준일 다시 하기"           # DART 를 부르지 않는 실행: 계획이 있어도 묻지 않아요
    assert F.dart_quarter(c, "C0", 2026, Q3) is None and not calls and not c.late_n
    for mode, empty in (("full", False), ("cache", True)):
        c2, _ = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries())
        c2.mode, c2.started_empty = mode, empty
        F.dart_late_start(c2, targets, cmap)      # 빈 캐시 · full: 어차피 모두 물어요 — 계획 없음 (전체 DART 실행에 더하지 않아요)
        assert c2.late_keys == frozenset() and c2.late_rank is None
    c3, _ = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries())
    c3.down = "ConnectTimeout"
    F.dart_late_start(c3, targets, cmap)
    assert c3.late_keys == frozenset()


def test_plan_failure_is_loud_and_falls_back_to_the_old_rule(tmp_path, monkeypatch, capsys):
    c, calls = client_with(tmp_path, monkeypatch, D(2026, 11, 19), plan_entries())

    def boom(*a, **k):
        raise ValueError("깨진 항목")
    monkeypatch.setattr(F, "dart_late_plan", boom)
    F.dart_late_start(c, [{"t": "T0", "cap": 1.0}], {"T0": "C0"})
    assert c.late_keys == frozenset() and "!! DART 마감 뒤 매일 다시 묻기 계획을 세우지 못했어요" in capsys.readouterr().out
    assert F.dart_quarter(c, "C0", 2026, Q3) is None and not calls


# ── enrich_with_dart: DART 의 재무제표 API 가 마감 뒤에 채워지는 분기 ──
N = 150
XBRL_FROM = D(2026, 11, 18)      # 3Q 숫자가 DART API 에 뜨는 날 (제출은 11-14 ~ 16)


def rows(amount):
    return [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": str(amount), "frmtrm_amount": str(amount * 0.9),
             "bfefrmtrm_amount": str(amount * 0.8), "thstrm_add_amount": str(amount)},
            {"account_nm": "당기순이익", "sj_div": "IS", "thstrm_amount": str(amount / 10), "frmtrm_amount": "1",
             "bfefrmtrm_amount": "1", "thstrm_add_amount": str(amount / 10)},
            {"account_nm": "자본총계", "sj_div": "BS", "thstrm_amount": str(amount * 5)},
            {"account_nm": "부채총계", "sj_div": "BS", "thstrm_amount": str(amount * 2)}]


def lagging_dart(calls):
    def get(self, endpoint, params, timeout=25):
        i = int(params["corp_code"][1:])
        y, r, fs = int(params["bsns_year"]), params["reprt_code"], params.get("fs_div")
        calls[self.today.isoformat()] += 1
        filed = False
        if endpoint.startswith("fnltt") and fs == "CFS":
            if r == ANN:
                filed = self.today >= D(y + 1, 3, 25)
            elif (y, r) == (2026, Q3):
                filed = i < N * 0.8 and self.today >= XBRL_FROM
            else:
                filed = i < N * 0.8 and self.today >= F.report_deadline(y, r) - dt.timedelta(days=5)
        st = "000" if filed else "013"
        with self.lock:
            self.status[st] += 1
        return {"status": st, "list": rows(1e11) if filed else []}
    return get


def run_days(monkeypatch, tmp_path, days):
    calls = collections.Counter()
    monkeypatch.setattr(F.DartClient, "get", lagging_dart(calls))
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {f"{i:06d}": f"C{i}" for i in range(N)})
    out = {}
    for d in days:
        stocks = [{"t": f"{i:06d}", "cls": "kr", "cap": float(N - i), "shr": 1_000_000, "price": 10000.0} for i in range(N)]
        c = F.DartClient("k", today=d, path=str(tmp_path / "c.json.gz"))
        _, fin = F.enrich_with_dart(stocks, c)
        out[d] = (collections.Counter(v.get("bq") for v in fin.values()), c, calls[d.isoformat()])
    return out


def test_quarter_adopted_the_day_after_dart_fills_in(monkeypatch, tmp_path, capsys):
    days = [D(2026, 11, 10), D(2026, 11, 16), D(2026, 11, 17), D(2026, 11, 19), D(2026, 11, 20)]
    out = run_days(monkeypatch, tmp_path, days)
    bq16, c16, _ = out[D(2026, 11, 16)]
    assert bq16["2026.3Q"] == 0 and c16.q_pick == {"v": 1, "cur": "2026.2Q", "top": 100, "filed": {"2026.3Q": 0, "2026.2Q": 100}}
    bq17, c17, _ = out[D(2026, 11, 17)]
    assert c17.late_n["still"] == 200 and bq17["2026.3Q"] == 0      # 밀린 마감 + 2일 안: 상위 100곳 연결 · 별도 다시 물음 (아직 없음)
    bq19, c19, _ = out[D(2026, 11, 19)]
    # 예전 규칙이면 11-23 까지 묻지 않아 2Q 에 남았어요. 이제 11-19 실행이 상위 회사를 다시 물어 3Q 를 '현재'로 써요
    assert c19.late_n == {"found": 100} and bq19["2026.3Q"] == 120 and c19.q_pick["cur"] == "2026.3Q"
    assert c19.late_cover == {(2026, Q3), (2026, Q2), (2026, Q1)}
    bq20, c20, n20 = out[D(2026, 11, 20)]
    assert not c20.late_n and n20 == 0          # '현재'로 쓴 뒤 (밀린 마감 + 2일 지남): 안 낸 30곳은 7일마다 — 늘어난 창으로 묻지 않아요
    log = capsys.readouterr().out
    assert "DART 마감 뒤 매일 다시 묻기 창: 2026.3Q 마감 2026-11-14 → 다음 거래일 2026-11-16" in log
    assert "오늘 다시 물음 100건 → 새로 냄 100 · 아직 없음 0 · 다음 실행으로 남김 0건" in log


def test_cap_leaves_the_rest_for_the_next_run(monkeypatch, tmp_path, capsys):
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
    assert "  !! DART 마감 뒤 매일 다시 묻기: 오늘 다시 물음 25건 → 새로 냄 25 · 아직 없음 0 · 다음 실행으로 남김 150건" in log


def test_qpick_goes_into_corp_json_and_the_app_is_not_told():
    src = inspect.getsource(F.main) if hasattr(F, "main") else open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert 'corp["qPick"] = client.q_pick' in src
    for folder in ("src",):
        for dp, _, fs in os.walk(os.path.join(ROOT, folder)):
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
