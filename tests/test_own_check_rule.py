# -*- coding: utf-8 -*-
"""Jack 의 상시 규칙 (2026-11-19 ~17:45 KST · 우리 처리를 보는 검사) — #139 · #142 의 검사 (네트워크 없음 · 더하기만).

Jack, verbatim: "Standing rule for checks on our own processing: a single bad row is dropped or blanked with a loud warning and the rest
publishes. Block only when many rows fail in one run (set the number from recent runs and show it in the PR) or when a value would show a
wrong number."

- #139 (미국 주식 종류 티커): S&P 500 목록의 점이 지워진 꼴(BRKB · BFB)이 바뀌지 않고 실린 행 · 출처를 알 수 없는 그 꼴 · 관문 표와 다르게 바꾼
  티커의 행 → 파이프라인이 행을 빼요 (fetch_data.own_drop_us_class · validate_data.us_class_bad_rows · data.json ownDrop.usClass).
- #142 (숨긴 배당수익률의 줄 dvLine 2 · 3 · 4): 기록(divCheck.proofSub)과 맞지 않는 줄 → 파이프라인이 그 종목의 줄을 비워요
  (fetch_data.own_blank_div_lines · validate_data.div_line_bad_rows · data.json ownDrop.divLine).
- 관문: 실패는 둘뿐 — 뺀 · 비운 행이 N(5)을 넘음 · 빼야 할 값이 남아 틀린 숫자나 틀린 이유 줄을 보임. 1~N 은 경고. ownDrop 이 없는 파일은 예전 규칙.
- 소스가 보내는 것을 보는 #139 의 'BF-B 가 있거나 빠진 이유' 줄은 그대로예요 (필수 종목 규칙)."""
import copy
import datetime as dt
import inspect
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402
from test_us_share_class import _fetch, rec, us_rows, ROW1, ROW2  # noqa: E402
from test_us_share_class import run as run_us  # noqa: E402
from test_v191b_data import check, rows_of  # noqa: E402
from test_v191j_div_lines import with_lines, SUB_ROW, run as run_div  # noqa: E402
from test_v191i_div_proof import ROWS as PROOF_ROWS  # noqa: E402

US_LOG = f"{F.US_CLASS_DROP_NAME}: "
DIV_LOG = f"{F.DIV_LINE_DROP_NAME}: "
EMPTY = {"n": 0, "rows": []}


def own_us(rows=(), n=None):
    return {"n": len(rows) if n is None else n, "rows": [list(r) for r in rows]}


# ── 한 곳 · 기준 ─────────────────────────────────────────────
def test_the_pipeline_uses_the_gates_own_functions_and_writes_the_record():
    """논리는 관문 파일에 하나: 파이프라인은 같은 함수를 불러요 (베끼지 않아요) · main 이 그 둘을 부르고 data.json ownDrop 에 적어요."""
    assert F.us_class_bad_rows is V.us_class_bad_rows and F.div_line_bad_rows is V.div_line_bad_rows and F.own_drop_rec is V.own_drop_rec
    src = inspect.getsource(F.main)
    assert "us, own_us = own_drop_us_class(us, umeta)" in src
    assert "own_div = own_blank_div_lines(kr, div_counts)" in src
    assert '"ownDrop": {US_CLASS_DROP_KEY: own_us, DIV_LINE_DROP_KEY: own_div},' in src
    # 미국 행은 미국 목록이 정해진 바로 뒤에 빼요 (분할 · 업종 · 순위 · 인기 목록 · 종목 수보다 먼저) · 줄은 쓰기 바로 앞에서 비워요
    i_us = src.index("own_drop_us_class(us")
    for later in ("splits_fields(prev", "assign_industries(kr + us", "add_percentiles(us)", "stocks = kr + us + bonds + funds"):
        assert i_us < src.index(later), later
    assert src.index("stocks = kr + us + bonds + funds") < src.index("own_blank_div_lines(kr") < src.index("payload = {") \
        < src.index("write_json(OUT, payload)")
    assert "ownDrop" in F.UNITS


def test_the_thresholds_come_from_the_replay_of_recent_publishes():
    """N = max(5, 3 × 최근 발행본에서 본 가장 큰 수): data 가지의 최근 발행 25회 (2026-11-06 ~ 11-19) 를 같은 함수로 다시 돌리면 두 검사 모두
    0건 → 5 (PR 의 표)."""
    assert V.US_CLASS_DROP_MAX == 5 and V.DIV_LINE_BLANK_MAX == 5 and V.OWN_DROP_SHOW == 30
    assert V.DIV_LINE_OF == {2: "rights", 3: "data", 4: "data"}


def test_the_record_shape_and_no_nan():
    rows = [(f"T{i}", "이유", "sp") for i in range(40)]
    r = V.own_drop_rec(rows)
    assert r["n"] == 40 and len(r["rows"]) == 30 and r["rows"][0] == ["T0", "이유"]
    json.dumps(r, allow_nan=False, ensure_ascii=False)
    assert V.own_drop_get({"ownDrop": {"usClass": r}}, "usClass") == r
    assert V.own_drop_get({}, "usClass") is None and V.own_drop_get({"ownDrop": {}}, "usClass") is None
    for bad in ({"n": "1", "rows": []}, {"n": 1, "rows": []}, {"n": True, "rows": []}, {"n": 0, "rows": [], "x": 1},
                {"n": 1, "rows": [["T", 3]]}, {"n": -1, "rows": []}, []):
        assert V.own_drop_get({"ownDrop": {"usClass": bad}}, "usClass") is False, bad
    assert V.own_drop_text(rows).endswith(" 외 10건") and V.own_drop_text(rows[:2]) == "T0 (이유) · T1 (이유)"


# ── #139: 미국 주식 종류 티커 ───────────────────────────────────
def test_one_unmapped_joined_form_is_dropped_loudly_and_the_rest_publishes(tmp_path, monkeypatch):
    """파이프라인 표에서 BFB 줄을 잃고 야후가 'BFB' 에 다른 증권으로 답했어요 (#139 의 실패 경우). 이제 그 행만 빼고 크게 남기고 나머지는 발행 ·
    관문은 경고 (실패 아님 · 그 행이 남았으면 실패)."""
    monkeypatch.delitem(F.US_CLASS_JOINED, "BFB")
    us, meta, lines, _dl = _fetch(tmp_path, monkeypatch, extra_px={"BFB": 12.0})
    assert "BFB" in {r["t"] for r in us}
    other = [["AAPL", "2026-10-01", 4.0]]
    meta["splits"] = other + [["BFB", "2026-10-01", 2.0]]                       # 그 행의 분할 줄 (목록에 없는 종목의 새 줄이면 관문 실패)
    meta["usInfoPartial"], meta["splitsNoCol"] = ["BFB", "AAPL"], ["BFB"]
    kept, own = F.own_drop_us_class(us, meta)
    assert [r for r in us if r["t"] != "BFB"] == kept and len(kept) == len(us) - 1
    assert meta["splits"] == other and meta["usInfoPartial"] == ["AAPL"] and meta["splitsNoCol"] == []
    assert own == {"n": 1, "rows": [["BFB", V.US_CLASS_WHY_SP]]}
    loud = [x for x in lines if x.startswith(f"  !! {US_LOG}1건 빼고 발행 — BFB ({V.US_CLASS_WHY_SP})")]
    assert len(loud) == 1 and "ownDrop.usClass" in loud[0] and "5건을 넘으면 실패" in loud[0]
    json.dumps(own, allow_nan=False, ensure_ascii=False)
    for mode in ("publish", "live"):
        rows, rep = run_us({"usListSym": meta["usListSym"], "ownDrop": {"usClass": own}}, kept, mode)
        assert rows[ROW2][3] == "WARN" and f"뺀 행 1: BFB ({V.US_CLASS_WHY_SP})" in rows[ROW2][1], rows[ROW2]
        assert ("파이프라인이 뺀 미국 종목 (ownDrop.usClass · 주식 종류 티커)", [f"BFB: {V.US_CLASS_WHY_SP}"]) in rep.details
    # 예전 규칙 (기록 없는 파일 · 빼지 않음): 그대로 실패
    rows, _ = run_us({"usListSym": meta["usListSym"]}, us)
    assert rows[ROW2][3] == "FAIL"


def test_a_clean_run_drops_nothing_logs_zero_and_passes(tmp_path, monkeypatch):
    us, meta, lines, _dl = _fetch(tmp_path, monkeypatch)
    kept, own = F.own_drop_us_class(us, meta)
    assert kept == us and own == EMPTY
    assert f"· {US_LOG}0건 빼고 발행" in lines and not any(x.startswith(f"  !! {US_LOG}") for x in lines)
    rows, _ = run_us({"usListSym": meta["usListSym"], "ownDrop": {"usClass": own}}, kept)
    assert rows[ROW1][3] == "PASS" and rows[ROW2][3] == "PASS"


def test_more_than_n_dropped_rows_fail_the_publish(tmp_path, monkeypatch):
    """한 실행에서 많은 행이 틀리면 막아요: 두 꼴(BRKB · BFB)을 다 잃고 야후가 둘 다 답한 날, N 을 1 로 낮추면 실패 (사이트 점검은 경고)."""
    monkeypatch.delitem(F.US_CLASS_JOINED, "BFB")
    monkeypatch.delitem(F.US_CLASS_JOINED, "BRKB")
    us, meta, lines, _dl = _fetch(tmp_path, monkeypatch, extra_px={"BFB": 12.0, "BRKB": 15.0})
    kept, own = F.own_drop_us_class(us, meta)
    assert own["n"] == 2 and not {"BFB", "BRKB"} & {r["t"] for r in kept} and "BRK-B" in {r["t"] for r in kept}
    data = {"usListSym": meta["usListSym"], "ownDrop": {"usClass": own}}
    assert run_us(data, kept)[0][ROW2][3] == "WARN"                       # 2 ≤ N(5)
    monkeypatch.setattr(V, "US_CLASS_DROP_MAX", 1)
    rows, _ = run_us(data, kept)
    assert rows[ROW2][3] == "FAIL" and "뺀 행이 기준 1 을 넘음 (2)" in rows[ROW2][1]
    assert run_us(data, kept, "live")[0][ROW2][3] == "WARN"


@pytest.mark.parametrize("n, status", [(V.US_CLASS_DROP_MAX, "WARN"), (V.US_CLASS_DROP_MAX + 1, "FAIL")])
def test_the_recorded_count_decides(n, status):
    rows_ = [(f"X{i}", "이유") for i in range(n)]
    rows, _ = run_us({"usListSym": rec(), "ownDrop": {"usClass": own_us(rows_)}}, us_rows())
    assert rows[ROW2][3] == status, rows[ROW2]


@pytest.mark.parametrize("mode", ["publish", "live"])
def test_a_joined_form_left_in_the_file_still_fails(mode):
    """빼는 단계가 고장 나 S&P 목록의 점이 지워진 꼴이 실린 채 남으면 (다른 증권의 가격 · 시가총액 = 틀린 숫자) 기록이 있어도 실패."""
    bad = us_rows(extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    data = {"usListSym": rec(spTickers=sorted({"AAPL", "BFB", "BRK-B"})), "ownDrop": {"usClass": EMPTY}}
    rows, _ = run_us(data, bad, mode)
    assert rows[ROW2][3] == "FAIL" and f"빼야 할 티커가 남아 실림: BFB ({V.US_CLASS_WHY_SP})" in rows[ROW2][1]


def test_a_mapping_that_differs_from_the_table_drops_its_row_and_only_warns():
    """파이프라인이 BFB 를 관문 표(BF-B)와 다른 티커로 바꿨어요. 그 티커의 행은 빼고 (S&P 목록의 회사가 아닌 증권일 수 있어요), 남은 행이 없으면
    경고 — 예전(#139)에는 발행 실패였어요."""
    r = rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BFB-X"]])
    us = us_rows(extra=[{"t": "BFB-X", "cls": "us", "price": 5.0}])
    lines = []
    kept_log = F.log
    try:
        F.log = lines.append
        kept, own = F.own_drop_us_class(us, {"usListSym": r})
    finally:
        F.log = kept_log
    why = "관문 표와 다르게 바꾼 티커 BFB → BFB-X (관문 표 BF-B)"
    assert own == {"n": 1, "rows": [["BFB-X", why]]} and "BFB-X" not in {x["t"] for x in kept} and "BF-B" in {x["t"] for x in kept}
    assert any(x.startswith(f"  !! {US_LOG}1건 빼고 발행 — BFB-X ({why})") for x in lines)
    assert f"  !! {F.US_CLASS_DROP_NAME} — 기록 문제 (관문 경고): 관문 표와 다르게 바꿈: BFB → BFB-X (관문 표 BF-B)" in lines
    rows, _ = run_us({"usListSym": r, "ownDrop": {"usClass": own}}, kept)
    assert rows[ROW2][3] == "WARN" and "관문 표와 다르게 바꿈: BFB → BFB-X (관문 표 BF-B)" in rows[ROW2][1]
    # 빼지 않고 남았으면: 발행 실패 · 사이트 점검 경고 (예전과 같아요)
    rows, _ = run_us({"usListSym": r, "ownDrop": {"usClass": EMPTY}}, us)
    assert rows[ROW2][3] == "FAIL" and f"빼야 할 티커가 남아 실림: BFB-X ({why})" in rows[ROW2][1]
    assert run_us({"usListSym": r, "ownDrop": {"usClass": EMPTY}}, us, "live")[0][ROW2][3] == "WARN"
    # 표의 맞는 티커(BRK-B · BF-B)로 잘못 바꾼 것은 빼지 않아요 (그 행은 그 티커의 진짜 숫자) — 기록 문제로 경고만
    swap = rec(mapped=[["S&P500", "BRKB", "BF-B"], ["S&P500", "BFB", "BF-B"]])
    assert V.us_class_bad_rows(swap, us_rows())[0] == []
    hand = rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "TM"]])          # 손으로 더한 종목(US_EXTRA_SET · #126)도 빼지 않아요
    assert V.us_class_bad_rows(hand, us_rows(extra=[{"t": "TM", "cls": "us", "price": 200.0}]))[0] == []
    assert run_us({"usListSym": swap, "ownDrop": {"usClass": EMPTY}}, us_rows())[0][ROW2][3] == "WARN"


def test_a_broken_record_warns_unless_a_joined_form_of_unknown_source_is_published():
    """기록 모양이 틀린 것만으로는 틀린 숫자를 보이지 않아요 → 경고 (예전 발행 실패). 다만 spTickers 를 믿을 수 없는데 점이 지워진 꼴이 실렸으면
    S&P 목록에서 왔는지 알 수 없어 빼요 (남았으면 발행 실패)."""
    for kw in ({"read": "yes"}, {"noPx": ["XYZA"]}, {"mapped": [["S&P500", "BRKB"]]}):
        rows, _ = run_us({"usListSym": rec(**kw), "ownDrop": {"usClass": EMPTY}}, us_rows())
        assert rows[ROW2][3] == "WARN" and "기록 모양이 틀림" in rows[ROW2][1], (kw, rows[ROW2])
        assert run_us({"usListSym": rec(**kw)}, us_rows())[0][ROW2][3] == "FAIL"                 # 예전 규칙 (기록 없는 파일)
    broken = rec(spGone={"VYLR": "가격 이력 32일 (60일 미만이라 넣지 않아요)"})
    del broken["spTickers"]
    bad = us_rows(extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    kept, own = F.own_drop_us_class(bad, {"usListSym": broken})
    assert own == {"n": 1, "rows": [["BFB", V.US_CLASS_WHY_UNSURE]]} and "BFB" not in {x["t"] for x in kept}
    assert run_us({"usListSym": broken, "ownDrop": {"usClass": own}}, kept)[0][ROW2][3] == "WARN"
    rows, _ = run_us({"usListSym": broken, "ownDrop": {"usClass": EMPTY}}, bad)
    assert rows[ROW2][3] == "FAIL" and V.US_CLASS_WHY_UNSURE in rows[ROW2][1]
    assert run_us({"usListSym": broken, "ownDrop": {"usClass": EMPTY}}, bad, "live")[0][ROW2][3] == "WARN"


def test_a_same_letters_ticker_from_another_source_is_never_dropped(tmp_path, monkeypatch):
    """리뷰 4 (#139): 나스닥의 진짜 회사 'BFB' 는 빼지 않아요 (S&P 목록의 BFB 는 BF-B 로)."""
    from test_us_share_class import NQ_ROWS, FakeFDR, listing
    nq = listing(NQ_ROWS + [("BFB", "Big Fun Bancorp")], nasdaq=True)
    us, meta, _lines, _dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(nq=nq), extra_px={"BFB": 12.0})
    kept, own = F.own_drop_us_class(us, meta)
    assert kept == us and own == EMPTY and {"BFB", "BF-B"} <= {r["t"] for r in kept}


def test_files_before_the_rule_keep_the_old_rule_and_a_bad_record_warns():
    """ownDrop.usClass 가 없는 파일 (지금 살아 있는 파일 · 예전 발행본): #139 의 규칙 그대로. 기록 모양이 틀리면 예전 규칙에 경고를 더해요."""
    wrong = rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BFB-X"]])
    assert run_us({"usListSym": wrong}, us_rows())[0][ROW2][3] == "FAIL"
    assert run_us({"usListSym": wrong}, us_rows(), "live")[0][ROW2][3] == "WARN"
    rows, _ = run_us({"usListSym": rec(), "ownDrop": {"usClass": {"n": "x"}}}, us_rows())
    assert rows[ROW2][3] == "WARN" and "뺀 행 기록(ownDrop.usClass) 모양이 틀림" in rows[ROW2][1]
    rows, _ = run_us({"usListSym": wrong, "ownDrop": {"usClass": {"n": "x"}}}, us_rows())
    assert rows[ROW2][3] == "FAIL"


def test_the_bf_b_row_is_a_must_have_rule_and_is_unchanged():
    """'BF-B 가 있거나 빠진 이유' 는 소스가 보낸 것 · 필수 종목을 보는 #126 의 규칙이라 상시 규칙 밖: 이유 없이 빠지면 기록이 있어도 발행 실패."""
    rows, _ = run_us({"usListSym": rec(missing={}), "ownDrop": {"usClass": EMPTY}}, us_rows(drop={"BF-B"}))
    assert rows[ROW1][3] == "FAIL" and "이유 없이 빠짐 1: BF-B" in rows[ROW1][1]


# ── #142: 숨긴 배당수익률의 줄 ─────────────────────────────────
@pytest.fixture
def line_pair():
    cur, prev, _ = good_pair()
    files, abc = with_lines(cur)
    return files, prev, abc


def blank(cur, monkeypatch):
    """파이프라인처럼: 같은 함수로 비우고 data.json ownDrop.divLine 에 적어요 → (기록, 로그)."""
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    own = F.own_blank_div_lines(cur["data"]["stocks"], cur["data"]["divCheck"])
    cur["data"]["ownDrop"] = {"divLine": own}
    return own, lines


def test_a_clean_file_blanks_nothing_and_passes(line_pair, monkeypatch):
    cur, prev, (a, b, c) = line_pair
    own, lines = blank(cur, monkeypatch)
    assert own == EMPTY and f"· {DIV_LOG}0건 비움" in lines and (a["dvLine"], b["dvLine"], c["dvLine"]) == (3, 4, 2)
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    assert rows_of(rep)[SUB_ROW][3] == "PASS" and rows_of(rep)[SUB_ROW][1] == "유상증자 줄 1 · 배당 자료 줄 1 · 빠진 자료 줄 1 · 줄 없음 0"


def test_one_wrong_line_is_blanked_loudly_and_the_rest_publishes(line_pair, monkeypatch):
    """총액이 없는 종목(기록 nototal → 줄 4)에 어긋남의 줄 3: 그 종목의 줄만 비워요 (빈 배당수익률에 이유 줄이 없을 뿐 · 틀린 이유를 말하지 않아요).
    다른 줄은 그대로 · 관문은 경고 (예전에는 실패)."""
    cur, prev, (a, b, c) = line_pair
    b["dvLine"] = 3
    old = check(copy.deepcopy(cur), prev)
    assert SUB_ROW in {r[0] for r in old.failed}                                   # 예전 규칙 (기록 없는 파일)
    own, lines = blank(cur, monkeypatch)
    why = "기록은 줄 4 인데 줄 3"
    assert own == {"n": 1, "rows": [[b["t"], why]]} and "dvLine" not in b and (a["dvLine"], c["dvLine"]) == (3, 2)
    loud = [x for x in lines if x.startswith(f"  !! {DIV_LOG}1건 비움 — {b['t']} ({why})")]
    assert len(loud) == 1 and "ownDrop.divLine" in loud[0]
    rep = check(cur, prev)
    assert not rep.failed, rep.table()
    row = rows_of(rep)[SUB_ROW]
    assert row[3] == "WARN" and f"비운 줄 1: {b['t']} ({why})" in row[1], row
    assert f"기록은 줄인데 표시 없음 1 (이유 줄 없이 빈칸): {b['t']} (기록은 줄 4 인데 줄 표시 없음" in row[1]
    assert ("파이프라인이 비운 숨긴 배당수익률의 줄 (ownDrop.divLine)", [f"{b['t']}: {why}"]) in rep.details
    json.dumps(cur["data"]["ownDrop"], allow_nan=False, ensure_ascii=False)


def test_a_wrong_line_left_in_the_file_still_fails(line_pair):
    """빼는 단계가 고장 나 틀린 이유 줄이 남으면 (틀린 이유 줄 = 틀린 것으로 봐요) 기록이 있어도 실패."""
    cur, prev, (a, b, c) = line_pair
    b["dvLine"] = 3
    cur["data"]["ownDrop"] = {"divLine": EMPTY}
    rep = check(cur, prev)
    assert SUB_ROW in {r[0] for r in rep.failed} and "기록과 맞지 않는 줄이 남음 1" in rows_of(rep)[SUB_ROW][1]
    assert rows_of(check(cur, prev, mode="live"))[SUB_ROW][3] == "FAIL"


def test_a_missing_line_only_warns(line_pair, monkeypatch):
    """기록은 줄 3 인데 표시가 없음: 틀린 것을 보이지 않아요 (이유 줄 없는 빈칸) → 비울 것이 없고 수에 들어가요 · 경고 (예전에는 실패)."""
    cur, prev, (a, b, c) = line_pair
    a.pop("dvLine")
    own, lines = blank(cur, monkeypatch)
    assert own["n"] == 1 and own["rows"][0][0] == a["t"] and any(x.startswith(f"  !! {DIV_LOG}1건 비움 (그중 줄이 원래 없던 종목 1)") for x in lines)
    rep = check(cur, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN", rep.table()


@pytest.mark.parametrize("n, status", [(V.DIV_LINE_BLANK_MAX, "WARN"), (V.DIV_LINE_BLANK_MAX + 1, "FAIL")])
def test_the_recorded_count_decides_for_lines(line_pair, n, status):
    cur, prev, _abc = line_pair
    cur["data"]["ownDrop"] = {"divLine": {"n": n, "rows": [[f"00000{i}", "이유"] for i in range(n)]}}
    assert rows_of(check(cur, prev))[SUB_ROW][3] == status
    assert rows_of(check(cur, prev, mode="live"))[SUB_ROW][3] == "WARN"                 # 사이트 점검은 경고


def test_a_broken_record_blanks_every_line_it_cannot_back(line_pair, monkeypatch):
    """기록(proofSub)의 모양이 틀리면 줄 2 · 3 · 4 를 하나도 확인할 수 없어 모두 비워요 (3건 ≤ N: 경고 · 틀린 이유 줄은 없어요). 한 실행에서
    N 을 넘게 비우면 실패 (N 을 2 로 낮춰 봐요)."""
    cur, prev, (a, b, c) = line_pair
    cur["data"]["divCheck"]["proofSub"]["v"] = 2
    work = copy.deepcopy(cur)
    own, lines = blank(work, monkeypatch)
    assert own["n"] == 3 and all("dvLine" not in s for s in work["data"]["stocks"] if s["t"] in {a["t"], b["t"], c["t"]})
    assert {r[1] for r in own["rows"]} == {"기록(proofSub.data)으로 확인할 수 없는 줄 3", "기록(proofSub.data)으로 확인할 수 없는 줄 4",
                                           "기록(proofSub.rights)으로 확인할 수 없는 줄 2"}
    assert any(x.startswith(f"  !! {F.DIV_LINE_DROP_NAME} — 기록 문제 (관문 경고): 모양") for x in lines)
    rep = check(work, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN", rep.table()
    monkeypatch.setattr(V, "DIV_LINE_BLANK_MAX", 2)
    rep = check(work, prev)
    assert SUB_ROW in {r[0] for r in rep.failed} and "비운 줄이 기준 2 을 넘음 (3)" in rows_of(rep)[SUB_ROW][1]


def test_lines_without_their_record_are_blanked_and_the_lost_record_warns(line_pair, monkeypatch):
    """proofSub 가 빠진 파일: 줄 2 · 3 · 4 를 맞춰 볼 기록이 없어 모두 비워요. 직전 발행본에 있었어도 남은 줄이 없으면 경고 (예전에는 실패 —
    '배당 기준 증명 기록' 줄도 줄이 남아 실패했어요)."""
    cur, prev, (a, b, c) = line_pair
    cur["data"]["divCheck"].pop("proofSub")
    had = copy.deepcopy(prev)                                                     # 직전 발행본에는 proofSub 가 있었어요
    had["data"]["divCheck"] = {**copy.deepcopy(cur["data"]["divCheck"]), "proofSub": {"v": 1, "rights": {}, "data": {}}}
    old = check(copy.deepcopy(cur), had)
    assert {SUB_ROW, PROOF_ROWS[0]} <= {r[0] for r in old.failed}                     # 예전 규칙
    own, _lines = blank(cur, monkeypatch)
    assert own["n"] == 3
    rep = check(cur, had)
    assert not rep.failed, rep.table()
    assert rows_of(rep)[SUB_ROW][3] == "WARN" and "기록 없음 — 직전 발행본에는 있었어요" in rows_of(rep)[SUB_ROW][1]


def test_a_line_on_a_stock_whose_yield_shows_is_blanked(line_pair, monkeypatch):
    """배당수익률이 보이는 종목(기록에 없는 종목)에 줄 2: 그 줄만 비워요 (수익률은 그대로) · 경고. 예전 규칙은 '배당 기준 증명 기록' 줄의 실패."""
    cur, prev, (a, b, c) = line_pair
    kr = [s for s in cur["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    x = next(s for s in kr if V.num(s.get("dyt")) is not None and not V.is_pref(s["t"]) and "dvProof" not in s and s["t"] not in V.MUST)
    x["dvLine"] = 2
    assert PROOF_ROWS[0] in {r[0] for r in check(copy.deepcopy(cur), prev).failed}
    dyt = x["dyt"]
    own, _lines = blank(cur, monkeypatch)
    assert own == {"n": 1, "rows": [[x["t"], "배당수익률(dyt)이 보이는 종목에 줄"]]} and "dvLine" not in x and x["dyt"] == dyt
    rep = check(cur, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN", rep.table()


def test_an_unknown_case_blanks_only_its_line(line_pair, monkeypatch):
    cur, prev, (a, b, c) = line_pair
    cur["data"]["divCheck"]["proofSub"]["rights"][c["t"]] = "maybe"
    own, _lines = blank(cur, monkeypatch)
    assert own == {"n": 1, "rows": [[c["t"], "기록은 줄 없음 인데 줄 2"]]} and (a["dvLine"], b["dvLine"]) == (3, 4) and "dvLine" not in c
    rep = check(cur, prev)
    assert not rep.failed and rows_of(rep)[SUB_ROW][3] == "WARN" and "rights: 모르는 경우 'maybe'" in rows_of(rep)[SUB_ROW][1], rep.table()


def test_line_one_and_odd_values_keep_the_v191i_rule(line_pair, monkeypatch):
    """줄 1 (Jack 의 줄) · 모르는 값의 줄은 이 규칙 밖 (v19.1i 의 '배당 기준 증명 기록' 줄 그대로 실패) — 파이프라인도 건드리지 않아요."""
    cur, prev, (a, b, c) = line_pair
    a["dvLine"] = 5
    own, _lines = blank(cur, monkeypatch)
    assert a["dvLine"] == 5 and own["n"] == 1 and own["rows"][0] == [a["t"], "기록은 줄 3 인데 줄 표시 없음 (이유 줄 없이 빈칸)"]
    assert PROOF_ROWS[0] in {r[0] for r in check(cur, prev).failed}


def test_files_before_the_rule_keep_the_old_rule_for_lines(line_pair):
    cur, prev, (a, b, c) = line_pair
    b.pop("dvLine")
    assert SUB_ROW in {r[0] for r in check(copy.deepcopy(cur), prev).failed}
    cur["data"]["ownDrop"] = {"divLine": {"n": 2, "rows": []}}                       # 모양이 틀린 기록: 예전 규칙에 경고를 더해요
    rep = check(cur, prev)
    assert SUB_ROW in {r[0] for r in rep.failed} and "비운 줄 기록(ownDrop.divLine) 모양이 틀림" in rows_of(rep)[SUB_ROW][1]


def test_without_the_proof_record_only_the_count_is_checked(line_pair):
    """divCheck.proof 가 없는 파일에도 비운 수가 있으면 그 수만 봐요 (N 을 넘으면 실패)."""
    cur, prev, (a, b, c) = line_pair
    for s in (a, b, c):
        s.pop("dvLine")
    cur["data"]["divCheck"].pop("proof")
    cur["data"]["divCheck"].pop("proofSub")
    cur["data"]["ownDrop"] = {"divLine": {"n": V.DIV_LINE_BLANK_MAX + 1, "rows": [["000001", "이유"]] * (V.DIV_LINE_BLANK_MAX + 1)}}
    rep = check(cur, None, mode="bootstrap")
    assert rows_of(rep)[SUB_ROW][3] == "FAIL"


def test_the_real_pipeline_output_blanks_nothing(monkeypatch):
    """실제 DART 응답으로 만든 픽스처 (11-14 의 줄 3 · 4 · 1 종목): 파이프라인이 만든 줄과 기록은 늘 맞아요 → 0건."""
    by, counts, _why, _cl = run_div("002310", "290650", "003380", "086900", "0030R0", "049430",
                                    edit={"049430": lambda lk: lk.update(cx=[])})
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    before = {t: s.get("dvLine") for t, s in by.items()}
    assert {v for v in before.values() if v} >= {3, 4}
    own = F.own_blank_div_lines(list(by.values()), counts)
    assert own == EMPTY and {t: s.get("dvLine") for t, s in by.items()} == before and f"· {DIV_LOG}0건 비움" in lines
