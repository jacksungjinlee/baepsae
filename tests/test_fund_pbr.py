# -*- coding: utf-8 -*-
"""ETF · 펀드의 PBR 과 가치 점수 — 파이프라인과 관문 (Jack, 2026-11-27, answer 12: "Yes, hide them: "ETF는 회사가 아니어서 PBR과 가치 점수를
계산하지 않아요."") · 네트워크 없음 · 새 시험 파일 (예전 시험은 그대로).

펀드 (etf 참 또는 fund — validate_data.factor_fund, #189 의 정의) 에는 회사의 장부가가 없어서, 야후의 펀드 PBR (11-24 발행본: SPY 1.76 · 실제 P/B
약 5 · SOXX 0.37 · TLT 0.55) 과 그 PBR 로 매긴 가치 점수 vz (#189 뒤 회사 분포에 견준 자리 · SOXX · TLT 100) 는 뜻이 없어요. 여기서 보는 것:
- fetch_data.fund_book_blank: 펀드 행의 pbr · vz 값만 지우고 (빈 값 칸 · 회사 행은 그대로) data.json fundPb 기록 {v, n, t} 을 돌려줘요
- 그 뒤 add_percentiles (#189): 11-24 발행본의 미국 행으로 — 펀드는 가치 순위에서 그냥 빠지고 (vz 없음), 회사 점수 · 펀드의 다른 점수는 PBR 이 있을
  때와 한 칸도 다르지 않아요 · NaN 없음 (allow_nan=False) · 관문의 '팩터 점수' 줄은 그대로 통과 (다시 매긴 값이 같아요)
- 로그 한 줄 (fund_book_line) · main 이 점수를 매기기 앞에 비우고 기록을 싣는지 · UNITS 설명
- 관문 줄 '펀드에 PBR · 가치 점수 없음 (data.json · corp.json · 경고만)': 비운 파일 → 통과 · 남은 칸 (data.json · corp.json 의 펀드 줄 · 0 도) →
  경고 (칸 이름) · 기록이 없는 예전 파일 → 남은 칸만 봐요 · 기록 모양이 틀림 → 경고 · 읽지 못함 → 경고 · 어떤 모드에서도 실패 없음
"""
import copy
import inspect
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402

FIX_US = os.path.join(ROOT, "tests", "fixtures", "factor_pool_us_1124.json")
IN = ("t", "cls", "etf", "cap", "pbr", "mom", "roe", "vol", "dyt")


def us_1124():
    fx = json.load(open(FIX_US, encoding="utf-8"))
    return [{k: r[k] for k in IN if k in r} for r in (dict(zip(fx["cols"], x), cls="us") for x in fx["rows"])]


def gate(data, corp=None):
    rep = V.Report()
    V.check_fund_book(rep, data, corp)
    rows = [r for r in rep.rows if r[0] == V.FUND_BOOK_ROW]
    assert len(rows) == 1 and rep.failed == [] and len(rep.rows) == 1       # 한 줄 · 실패 없음
    return rows[0][3], rows[0][1]


# ── 1. fund_book_blank ───────────────────────────────────────────────────────────────────────
def test_blank_removes_only_fund_values_and_records_them():
    rows = [{"t": "AAPL", "cls": "us", "etf": False, "pbr": 48.0, "vz": 1},
            {"t": "SPY", "cls": "us", "etf": True, "pbr": 1.7, "vz": 85, "mz": 42, "per": 23.2},
            {"t": "JEPI", "cls": "us", "etf": True, "per": 23.8},
            {"t": "088980", "cls": "kr", "etf": True, "pbr": 1.1},
            {"t": "069500", "cls": "kr", "etf": True, "fund": True, "vz": 0},
            {"t": "153130", "cls": "bond", "etf": True, "pbr": None, "per": None},
            {"t": "005930", "cls": "kr", "etf": False, "pbr": 1.4, "vz": 40}]
    keep = copy.deepcopy(rows)
    rec = F.fund_book_blank(rows)
    assert rec == {"v": 1, "n": 3, "t": ["069500", "088980", "SPY"]}
    assert rows[0] == keep[0] and rows[6] == keep[6]                                         # 회사는 그대로
    assert rows[1] == {"t": "SPY", "cls": "us", "etf": True, "mz": 42, "per": 23.2}          # 다른 칸 (PER · 추세 점수) 은 그대로
    assert rows[2] == keep[2] and rows[5] == keep[5]                                         # 빈 값 칸은 그대로 (채권의 "pbr": null 도)
    assert "pbr" not in rows[3] and "vz" not in rows[4]
    assert F.fund_book_blank(rows) == {"v": 1, "n": 0, "t": []}                              # 두 번째는 할 일이 없어요
    assert F.fund_book_blank([]) == {"v": 1, "n": 0, "t": []}


def test_the_record_and_line_read_well():
    rows = [{"t": t, "cls": "us", "etf": True, "pbr": 1.0} for t in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")]
    rows += [{"t": "088980", "cls": "kr", "etf": True, "pbr": 1.0}, {"t": "X", "cls": "us", "etf": False, "pbr": 2.0}]
    rec = F.fund_book_blank(rows)
    assert F.fund_book_line(rec, rows) == ("· 펀드의 PBR · 가치 점수 비움 (Jack 2026-11-27): 11곳 (미국 10 · 그 밖 1) — 펀드에는 회사의 장부가가 없어요 "
                                           "(088980, A, B, C, D, E, F, G 외 3) · 펀드 행 11곳")
    zero = F.fund_book_blank(rows)
    assert F.fund_book_line(zero, rows) == "· 펀드의 PBR · 가치 점수 비움 (Jack 2026-11-27): 0곳 (미국 0 · 그 밖 0) — 펀드에는 회사의 장부가가 없어요 · 펀드 행 11곳"
    assert json.dumps(rec, allow_nan=False)


# ── 2. 그 뒤의 팩터 점수 (#189) ─────────────────────────────────────────────────────────────────
def test_funds_simply_drop_out_of_the_value_ranks_on_the_1124_us_rows():
    plain = us_1124()
    blanked = copy.deepcopy(plain)
    rec = F.fund_book_blank(blanked)
    assert rec["n"] == 23 and {"SPY", "SOXX", "TLT", "QQQ", "GLD"} <= set(rec["t"])          # 11-24: PBR 이 있던 미국 ETF 23곳
    F.add_percentiles(plain)
    F.add_percentiles(blanked)
    by_p, by_b = {r["t"]: r for r in plain}, {r["t"]: r for r in blanked}
    funds = [t for t, r in by_b.items() if V.factor_fund(r)]
    assert len(funds) == 33
    assert [t for t in funds if by_b[t].get("vz") is not None or by_b[t].get("pbr") is not None] == []   # 가치 점수 · PBR 이 있는 펀드 없음
    assert sum(1 for t in funds if by_p[t].get("vz") is not None) == 23                     # (비우지 않았다면 23곳이 가치 점수를 받았어요)
    for t, r in by_b.items():                                                              # 회사 점수 · 펀드의 다른 점수는 한 칸도 다르지 않아요
        for k in V.FACTOR_KEYS:
            if V.factor_fund(r) and k == "vz":
                continue
            assert r.get(k) == by_p[t].get(k), (t, k)
    cos = [r for r in blanked if not V.factor_fund(r)]
    assert sum(1 for r in cos if r.get("vz") is not None) == 665                           # 회사 가치 순위는 #189 그대로 (회사 665곳)
    for r in blanked:
        for k in V.FACTOR_KEYS:
            v = r.get(k)
            assert v is None or (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100), (r["t"], k, v)
    json.dumps(blanked, allow_nan=False)                                                    # NaN · Infinity 없음
    assert F.factor_pool_line("us", blanked).endswith("펀드 33곳은 순위에 넣지 않고 회사 분포에 견줘 매김 (점수 있는 펀드 33) (ARKK, DIA, GLD, IAU, IEF, IVE, IVV, IWM 외 25)")


def test_the_factor_gate_row_still_passes_on_a_blanked_file():
    us = us_1124()
    F.fund_book_blank(us)
    F.add_percentiles(us)
    rep = V.Report()
    V.check_factor_pool(rep, {"stocks": us})
    (row,) = [r for r in rep.rows if r[0] == V.FACTOR_POOL_ROW]
    assert row[3] == "PASS" and row[1].startswith("모두 같음"), row
    assert V.factor_score_diffs({"stocks": us}) == []


def test_only_funds_and_no_pbr_anywhere_does_not_break():
    rows = [{"t": "E1", "cls": "us", "etf": True, "pbr": 0.5, "vol": 10.0}, {"t": "E2", "cls": "us", "etf": True, "pbr": float("nan")}]
    F.fund_book_blank(rows)
    F.add_percentiles(rows)
    assert all(r.get("vz") is None and r.get("pbr") is None for r in rows)
    json.dumps(rows, allow_nan=False)


# ── 3. main · 기록 · UNITS ──────────────────────────────────────────────────────────────────────
def test_main_blanks_before_the_scores_and_publishes_the_record():
    src = inspect.getsource(F.main)
    i = src.index("fund_pb = fund_book_blank(kr + us + bonds + funds)")
    assert src.index("funds = ph.run(") < i < src.index("log(fund_book_line(fund_pb, kr + us + bonds + funds))") < src.index("add_percentiles(kr)")
    assert src.count("fund_book_blank(") == 1 and src.count("add_percentiles(") == 2
    assert "FUND_BOOK_REC: fund_pb," in src and src.index("FUND_BOOK_REC: fund_pb,") < src.index("write_json(OUT, payload)")
    assert i < src.index("corp = build_corp(kr, fin_map")                                  # corp.json 의 펀드 줄도 빈 행을 베껴요
    assert V.FUND_BOOK_REC == "fundPb" and V.FUND_BOOK_KEYS == ("pbr", "vz")
    assert "fundPb" in F.UNITS and "pbr" in F.UNITS["fundPb"] and "vz" in F.UNITS["fundPb"]
    assert [p for p, v in V.text_values(F.UNITS) if V.BAD_WORD.search(v)] == []


def test_corp_rows_copy_the_blank():
    s = {"t": "088980", "nk": "맥쿼리인프라", "cls": "kr", "etf": True, "price": 9630.0, "pbr": 1.1, "vz": 60, "shr": 478921993}
    F.fund_book_blank([s])
    corp = F.build_corp([s], {}, "2026-11-28")
    (c,) = corp["companies"]
    assert c["pbr"] is None and c["vz"] is None


# ── 4. 관문 줄 (경고만) ─────────────────────────────────────────────────────────────────────────
def a_file():
    us = us_1124()
    rec = F.fund_book_blank(us)
    F.add_percentiles(us)
    others = [{"t": "069500", "cls": "kr", "etf": True, "fund": True}, {"t": "153130", "cls": "bond", "etf": True, "pbr": None},
              {"t": "088980", "cls": "kr", "etf": True, "pz": 4}]
    return {"stocks": us + others, "fundPb": rec}, {"companies": [{"t": "088980", "pbr": None, "vz": None}, {"t": "005930", "pbr": 1.4, "vz": 40}]}


def test_gate_passes_on_what_the_pipeline_writes():
    d, c = a_file()
    st, val = gate(d, c)
    assert (st, val) == ("PASS", "없음 (펀드 36곳 · 이번 실행이 비운 펀드 23곳 (DIA, GLD, IAU, IEF, IVE, IVV, IWM, QQQ 외 15))"), val
    del d["fundPb"]                                                                        # 기록이 없는 파일 (이 PR 전): 남은 칸만 봐요
    assert gate(d, c) == ("PASS", "없음 (펀드 36곳 · 기록 없음 (fundPb 전에 발행된 파일))")
    d["fundPb"] = {"v": 1, "n": 0, "t": []}
    assert gate(d, c) == ("PASS", "없음 (펀드 36곳 · 이번 실행이 비운 펀드 0곳)")


def test_gate_warns_naming_every_left_cell():
    d, c = a_file()
    by = {s["t"]: s for s in d["stocks"]}
    by["SPY"]["pbr"] = 1.7
    by["SOXX"]["vz"] = 100
    by["069500"]["pbr"] = 0                                                                 # 0 도 남은 값이에요
    c["companies"][0]["vz"] = 55                                                            # corp.json 의 펀드 줄 (088980)
    c["companies"][1]["pbr"] = 9.9                                                          # 회사 줄은 상관없어요
    st, val = gate(d, c)
    assert st == "WARN" and val.startswith("남은 칸 4 (4곳 · 펀드 36곳 · 이번 실행이 비운 펀드 23곳"), val
    assert set(val.split("): ", 1)[1].split(", ")) == {"SOXX.vz", "SPY.pbr", "069500.pbr", "corp.088980.vz"}, val
    assert val.endswith(", corp.088980.vz"), val                                           # corp.json 칸은 data.json 칸 뒤에
    many = {"stocks": [{"t": f"E{i}", "cls": "us", "etf": True, "pbr": 1.0, "vz": 50} for i in range(8)]}
    st, val = gate(many)
    assert st == "WARN" and val.startswith("남은 칸 16 (8곳 · 펀드 8곳 · 기록 없음") and val.endswith(" 외 6칸"), val


def test_the_live_file_before_this_change_only_warns():
    """11-28 발행본의 모양: 미국 ETF 23곳에 PBR · 가치 점수 (기록 없음) — 배포 · 감시의 관문도 경고만 (다음 발행이 비워요)."""
    us = us_1124()
    F.add_percentiles(us)
    st, val = gate({"stocks": us})
    assert st == "WARN" and val.startswith("남은 칸 46 (23곳 · 펀드 33곳 · 기록 없음 (fundPb 전에 발행된 파일)): "), val


@pytest.mark.parametrize("rec", [{"v": 2, "n": 0, "t": []}, {"v": 1, "n": 1, "t": []}, {"v": 1, "n": "1", "t": ["A"]}, {"v": 1, "n": True, "t": ["A"]},
                                 {"v": 1, "n": 1, "t": [""]}, {"v": 1, "n": 1, "t": [1]}, [], "x", {"v": 1, "n": 0}])
def test_gate_warns_on_a_malformed_record(rec):
    d, c = a_file()
    d["fundPb"] = rec
    st, val = gate(d, c)
    assert st == "WARN" and val == "없음 (펀드 36곳 · 기록 모양이 잘못됨 (fundPb))", (rec, val)


@pytest.mark.parametrize("data", [None, {}, {"stocks": "x"}, {"stocks": None}, [], "x"])
def test_gate_warns_when_it_cannot_read_the_file(data):
    st, val = gate(data)
    assert st == "WARN" and val.startswith("검사가 멈췄어요: "), val
    assert gate({"stocks": [1, None, "a", {"t": "E", "etf": True}]}, corp=[1]) == ("PASS", "없음 (펀드 1곳 · 기록 없음 (fundPb 전에 발행된 파일))")


def test_gate_row_runs_in_every_mode_and_never_fails():
    src = inspect.getsource(V.run_checks)
    i = src.index("check_fund_book(rep, data, corp)")
    assert src.count("check_fund_book(") == 1 and src.index("check_factor_pool(rep, data)") < i
    assert "return" not in src[src.index("check_factor_pool(rep, data)"):i]
    body = inspect.getsource(V.check_fund_book)
    adds = re.findall(r"rep\.add\(FUND_BOOK_ROW, (\w+),", body)
    assert adds == ["True", "True", "True"], adds                                         # 모든 줄이 ok=True: 경고 아니면 통과 (실패 없음)
    assert "경고만" in V.FUND_BOOK_ROW


# ── 5. #203 리뷰 (1차: Opus · Fable) ───────────────────────────────────────────────────────────
def test_gate_counts_a_fund_left_in_both_files_as_one_place():
    """리뷰 nit: data.json 과 corp.json 에 함께 남은 펀드는 한 곳 ('corp.' 을 떼고 세요) — 값 칸의 글만 바뀌고 줄은 여전히 경고만."""
    d, c = a_file()
    by = {s["t"]: s for s in d["stocks"]}
    by["088980"]["pbr"] = 1.1
    by["088980"]["vz"] = 60
    c["companies"][0]["pbr"] = 1.1
    c["companies"][0]["vz"] = 60
    st, val = gate(d, c)
    assert st == "WARN" and val.startswith("남은 칸 4 (1곳 · 펀드 36곳 · "), val
    assert val.split("): ", 1)[1] == "088980.pbr, 088980.vz, corp.088980.pbr, corp.088980.vz", val
    by["SPY"]["pbr"] = 1.7                                                                 # 다른 펀드 하나 더: 두 곳
    st, val = gate(d, c)
    assert st == "WARN" and val.startswith("남은 칸 5 (2곳 · "), val
    dot = {"stocks": [{"t": "BRK.X", "cls": "us", "etf": True, "pbr": 1.0}]}, {"companies": [{"t": "BRK.X", "pbr": 1.0}]}
    st, val = gate(*dot)                                                                   # 점이 든 종목 코드도 한 곳
    assert st == "WARN" and val.startswith("남은 칸 2 (1곳 · "), val


def _split_rows():
    full = {k: 1.0 for k in V.PX_BAD_DATA}
    return [{"t": "088980", "nk": "맥쿼리인프라", "cls": "kr", "etf": True, "price": 9630.0, "shr": 478921993, "pbr": 1.1, "vz": 60, "pz": 4, **full},
            {"t": "000010", "nk": "회사", "cls": "kr", "etf": False, "price": 1000.0, "shr": 1000000, "pbr": 2.0, "vz": 40, **full}]


def test_a_fund_marked_for_an_unconfirmed_split_gets_both_blanks_and_they_do_not_fight():
    """#186 (Jack 답 11) 의 mark_split_nofile 과 이 PR 의 fund_book_blank: 서로 다른 칸 (PX_BAD_DATA · pbr · vz) — main 의 순서 (분할 먼저) 로 둘 다
    그대로 남고, 순서를 바꿔도 같은 행 · corp.json 도 같은 표시와 빈 칸 · 관문의 두 줄 (분할의 숫자 비움 · 펀드에 PBR · 가치 점수 없음) 모두 문제 없음."""
    assert not set(V.FUND_BOOK_KEYS) & set(V.PX_BAD_DATA)                                # 두 단계가 비우는 칸은 겹치지 않아요
    src = inspect.getsource(F.main)
    assert src.index("mark_split_nofile(kr, nf,") < src.index("fund_pb = fund_book_blank(kr + us + bonds + funds)")
    nofile = [["088980", "2026-11-02", 2.0, "nodoc"], ["000010", "2026-11-02", 2.0, "nodoc"]]
    rows = _split_rows()
    F.mark_split_nofile(rows, nofile, {})
    rec = F.fund_book_blank(rows)
    fund, co = rows
    assert rec == {"v": 1, "n": 1, "t": ["088980"]}
    assert fund["spNo"] == "2026-11-02" and fund["spNoF"] == list(V.PX_BAD_DATA)
    assert all(k not in fund for k in V.PX_BAD_DATA + V.FUND_BOOK_KEYS) and fund["pz"] == 4 and fund["price"] == 9630.0
    assert co["spNo"] == "2026-11-02" and co["pbr"] == 2.0 and co["vz"] == 40              # 회사: 분할 표시만 (PBR · 가치 점수는 그대로)
    other = _split_rows()                                                                  # 순서를 바꿔도 (펀드 먼저) 같은 행
    F.fund_book_blank(other)
    F.mark_split_nofile(other, nofile, {})
    assert other == rows
    corp = F.build_corp(rows, {}, "2026-11-28")
    cf = {c["t"]: c for c in corp["companies"]}["088980"]
    assert cf["spNo"] == "2026-11-02" and cf["pbr"] is None and cf["vz"] is None
    data = {"stocks": rows, "pxDate": "2026-11-27", "fundPb": rec}
    rep = V.Report()
    V._check_kr_split_hide(rep, data, corp["companies"], nofile)
    (hide,) = [r for r in rep.rows if r[0] == V.KR_NOFILE_HIDE_ROW]
    assert hide[3] == "PASS" and hide[1] == "2종목 · 문제 0", hide
    assert gate(data, corp) == ("PASS", "없음 (펀드 1곳 · 이번 실행이 비운 펀드 1곳 (088980))")
    json.dumps(rows, allow_nan=False)
