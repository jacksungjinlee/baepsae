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
- #139 의 'BF-B 가 있거나 빠진 이유' 줄: Jack (2026-11-20, verbatim) "Brown-Forman B: no, it becomes a warning; one stock missing from a source
  never holds the publish." — BF-B 가 목록에 없으면 이유가 없어도 경고. 실패는 BF-B 행이 목록에 있는데 가격이 없을 때 · 점이 지워진 꼴(BFB)이
  실려 다른 회사의 숫자를 보일 때 (위 #139 규칙)뿐."""
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
from test_v191b_data import recount  # noqa: E402
from test_v191h_div_why import recount_why, mirror  # noqa: E402

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
    assert "own_div = own_blank_div_lines(kr, div_counts, prev)" in src
    assert '"ownDrop": {US_CLASS_DROP_KEY: own_us, DIV_LINE_DROP_KEY: own_div},' in src
    # 미국 행은 미국 목록이 정해진 바로 뒤에 빼요 (분할 · 업종 · 순위 · 인기 목록 · 종목 수보다 먼저) · 줄은 쓰기 바로 앞에서 비워요
    i_us = src.index("own_drop_us_class(us")
    for later in ("splits_fields(prev", "assign_industries(kr + us", "add_percentiles(us)", "stocks = kr + us + bonds + funds"):
        assert i_us < src.index(later), later
    assert src.index("stocks = kr + us + bonds + funds") < src.index("own_blank_div_lines(kr") < src.index("payload = {") \
        < src.index("write_json(OUT, payload)")
    assert "ownDrop" in F.UNITS


def test_units_has_no_duplicate_keys_and_names_every_own_drop_key():
    """(리뷰 3차 · 더하기만) UNITS 사전에 같은 키가 두 번 있으면 뒤의 설명이 앞을 조용히 덮어써요 → fetch_data.py 의 UNITS 글자 그대로 키가
    한 번씩만 있는지 봐요. 그리고 data.json ownDrop 설명이 지금 쓰는 키(usClass · divLine · indFill)를 모두 적는지 봐요."""
    import ast
    tree = ast.parse(open(os.path.join(os.path.dirname(F.__file__), "fetch_data.py"), encoding="utf-8").read())
    units = [n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "UNITS"
                                                                               for t in n.targets)]
    assert len(units) == 1 and isinstance(units[0], ast.Dict)
    keys = [k.value for k in units[0].keys if isinstance(k, ast.Constant)]
    assert len(keys) == len(units[0].keys) and len(keys) > 30
    dup = sorted({k for k in keys if keys.count(k) > 1})
    assert not dup, dup
    for k in (V.US_CLASS_DROP_KEY, V.DIV_LINE_DROP_KEY, "indFill"):
        assert k in F.UNITS["ownDrop"], k


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
    S&P 목록에서 왔는지 알 수 없어 빼요 (남았으면 발행 실패). mapped 의 틀린 줄은 아래 시험 (리뷰 1차 M1 · 2차: 발행 실패 그대로)."""
    for kw in ({"read": "yes"}, {"noPx": ["XYZA"]}, {"unmapped": {"x": 1}}):
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


@pytest.mark.parametrize("mapped", [
    [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BF-B"], ["S&P500", "ZZZ"]],   # 다른 티커의 틀린 줄도 (리뷰 2차: mapped 에는 바꾼 줄만 들어가요)
    [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB"]],                       # 점이 지워진 꼴이 든 줄인데 어디로 바뀌었는지 없음
    [["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", 3]],                    # 읽을 수 없는 칸
    [["S&P500", "BRKB", "BRK-B"], "BFB→BF-B"],                              # 줄이 목록이 아님
    "BRKB→BRK-B",                                                           # mapped 가 목록이 아님
    None,
])
def test_a_mapped_record_the_gate_cannot_read_for_a_joined_form_still_fails_the_publish(mapped):
    """리뷰 1차 M1 · 2차: mapped 에 모양이 틀린 줄이 하나라도 있으면 (mapped 에는 점이 지워진 꼴을 바꾼 줄만 들어가요) 그 꼴이 어디로 바뀌었는지
    (엉뚱한 회사가 실렸는지) 관문이 맞춰 볼 수 없어요 → 기록이 있어도 발행 실패 · 사이트 점검 경고 (예전 'mapped 모양' 실패와 같아요)."""
    data = {"usListSym": rec(mapped=mapped), "ownDrop": {"usClass": EMPTY}}
    rows, _ = run_us(data, us_rows())
    assert rows[ROW2][3] == "FAIL" and V.US_CLASS_BLIND in rows[ROW2][1], rows[ROW2]
    assert run_us(data, us_rows(), "live")[0][ROW2][3] == "WARN"
    assert V.US_CLASS_BLIND in V.us_class_bad_rows(data["usListSym"], us_rows())[1]


def test_a_malformed_mapped_row_fails_the_publish_but_the_wrong_row_is_still_dropped():
    """리뷰 1차 M1 (probe1) · 2차: mapped 의 다른 줄 하나가 틀려도 (ZZZ) 나머지 줄은 읽어 BFB → BFB-X 의 행은 빼요. 그래도 틀린 줄이 있으면 발행은
    실패 · 사이트 점검은 경고 (예전 규칙과 같은 엄격함)."""
    r = rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BFB-X"], ["S&P500", "ZZZ"]])
    us = us_rows(extra=[{"t": "BFB-X", "cls": "us", "price": 5.0}])
    lines = []
    old_log, F.log = F.log, lines.append
    try:
        kept, own = F.own_drop_us_class(us, {"usListSym": r})
    finally:
        F.log = old_log
    assert own == {"n": 1, "rows": [["BFB-X", "관문 표와 다르게 바꾼 티커 BFB → BFB-X (관문 표 BF-B)"]]} and "BFB-X" not in {x["t"] for x in kept}
    assert any("기록 문제 (관문에서 실패해 발행하지 않아요)" in x and V.US_CLASS_BLIND in x for x in lines)
    rows, _ = run_us({"usListSym": r, "ownDrop": {"usClass": own}}, kept)
    assert rows[ROW2][3] == "FAIL" and "관문 표와 다르게 바꿈: BFB → BFB-X (관문 표 BF-B)" in rows[ROW2][1] and V.US_CLASS_BLIND in rows[ROW2][1]
    assert run_us({"usListSym": r, "ownDrop": {"usClass": own}}, kept, "live")[0][ROW2][3] == "WARN"
    rows, _ = run_us({"usListSym": r, "ownDrop": {"usClass": EMPTY}}, us)              # 빼지 않고 남음 → 발행 실패
    assert rows[ROW2][3] == "FAIL" and "빼야 할 티커가 남아 실림: BFB-X" in rows[ROW2][1]
    assert run_us({"usListSym": r}, us)[0][ROW2][3] == "FAIL"                           # 예전 규칙 그대로


def test_a_dropped_row_leaves_nothing_behind_in_the_run_record():
    """리뷰 1차 S1: 뺀 종목은 미국 외국 회사 기록(usForeign: checked · cut · kind · kept · set · unknown)에서도 빠져요 — 남으면 check_us_foreign 이
    'kind ≠ 종목 표시' 로 발행 전체를 막아요. usInfo 도 뺀 행만큼 줄여요."""
    bfb = {"t": "BFB", "cls": "us", "price": 9.0, "nk": "Big Fun Inc", "dk": "설명", "fgnCut": {"per": "mismatch"}}
    us = us_rows(extra=[bfb])
    uf = {"checked": ["BFB"], "cut": [["BFB", "per", "회사 합계와 맞지 않음"]], "kind": {"BFB": {"per": "mismatch"}}, "kept": [["BFB", "pbr", "x"]],
          "nocmp": V.US_FGN_NOCMP, "set": {"BFB": ["Japan", None, "country"]}, "unknown": ["BFB"], "sp500": {"n": 503, "inList": 500, "ok": True}}
    umeta = {"usListSym": rec(spTickers=sorted({"AAPL", "BFB", "BRK-B", "BF-B"})), "usForeign": copy.deepcopy(uf), "usInfo": [len(us), len(us)]}
    old_log, F.log = F.log, lambda *a: None
    try:
        kept, own = F.own_drop_us_class(us, umeta)
    finally:
        F.log = old_log
    assert own["n"] == 1 and "BFB" not in {x["t"] for x in kept}
    assert umeta["usForeign"] == {**uf, "checked": [], "cut": [], "kind": {}, "kept": [], "set": {}, "unknown": []}
    assert umeta["usInfo"] == [len(us) - 1, len(kept)]                                  # 상세 정보(dk)를 붙인 행이었어요
    bare = {"t": "BFB", "cls": "us", "price": 9.0, "nk": "BFB"}                          # 상세 정보 없는 행 (이름 = 티커 · dk 없음)
    um2 = {"usListSym": umeta["usListSym"], "usInfo": [len(us) - 1, len(us)]}
    old_log, F.log = F.log, lambda *a: None
    try:
        F.own_drop_us_class(us_rows(extra=[bare]), um2)
    finally:
        F.log = old_log
    assert um2["usInfo"] == [len(us) - 1, len(us) - 1]
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": umeta["usForeign"]}, kept, "publish")
    assert not rep.failed, rep.table()
    rep = V.Report()
    V.check_us_foreign(rep, {"usForeign": uf}, kept, "publish")                       # 거르지 않았다면: 발행 실패 (probe2)
    assert rep.failed


def test_this_checks_count_cannot_reach_n_so_a_left_row_is_its_guard():
    """리뷰 1차 S3: 이 검사의 행은 표의 두 꼴(BRKB · BFB)에서만 나와요 — 꼴마다 실린 그 꼴 하나와 다르게 바꾼 티커 하나, 한 실행에 많아야 4건쯤
    (S&P 목록은 꼴마다 한 줄). N(5)은 사양의 바닥값이라 넘기 어려워요: 이 검사를 지키는 것은 '빼야 할 행이 남으면 실패'예요 (위 시험들)."""
    r = rec(mapped=[["S&P500", "BRKB", "XX1"], ["S&P500", "BFB", "XX2"]], spTickers="broken")
    us = us_rows(extra=[{"t": t, "cls": "us", "price": 1.0} for t in ("BRKB", "BFB", "XX1", "XX2")])
    rows, _ = V.us_class_bad_rows(r, us)
    assert len(rows) == 4 <= V.US_CLASS_DROP_MAX


def test_a_same_letters_ticker_from_another_source_is_never_dropped(tmp_path, monkeypatch):
    """리뷰 4 (#139): 나스닥의 진짜 회사 'BFB' 는 빼지 않아요 (S&P 목록의 BFB 는 BF-B 로)."""
    from test_us_share_class import NQ_ROWS, FakeFDR, listing
    nq = listing(NQ_ROWS + [("BFB", "Big Fun Bancorp")], nasdaq=True)
    us, meta, _lines, _dl = _fetch(tmp_path, monkeypatch, fdr=FakeFDR(nq=nq), extra_px={"BFB": 12.0})
    kept, own = F.own_drop_us_class(us, meta)
    assert kept == us and own == EMPTY and {"BFB", "BF-B"} <= {r["t"] for r in kept}


def test_a_malformed_own_drop_object_keeps_the_old_rule_and_warns():
    """리뷰 1차 (nit): ownDrop 이 사전이 아니면 조용히 넘기지 않아요 — 예전 규칙 그대로에 경고를 더해요."""
    for od in ([], "x", 3):
        assert V.own_drop_get({"ownDrop": od}, "usClass") is False and V.own_drop_get({"ownDrop": od}, "divLine") is False
        rows, _ = run_us({"usListSym": rec(), "ownDrop": od}, us_rows())
        assert rows[ROW2][3] == "WARN" and "뺀 행 기록(ownDrop.usClass) 모양이 틀림" in rows[ROW2][1]
    assert V.own_drop_get({"ownDrop": {"divLine": EMPTY}}, "usClass") is None


def test_files_before_the_rule_keep_the_old_rule_and_a_bad_record_warns():
    """ownDrop.usClass 가 없는 파일 (지금 살아 있는 파일 · 예전 발행본): #139 의 규칙 그대로. 기록 모양이 틀리면 예전 규칙에 경고를 더해요."""
    wrong = rec(mapped=[["S&P500", "BRKB", "BRK-B"], ["S&P500", "BFB", "BFB-X"]])
    assert run_us({"usListSym": wrong}, us_rows())[0][ROW2][3] == "FAIL"
    assert run_us({"usListSym": wrong}, us_rows(), "live")[0][ROW2][3] == "WARN"
    rows, _ = run_us({"usListSym": rec(), "ownDrop": {"usClass": {"n": "x"}}}, us_rows())
    assert rows[ROW2][3] == "WARN" and "뺀 행 기록(ownDrop.usClass) 모양이 틀림" in rows[ROW2][1]
    rows, _ = run_us({"usListSym": wrong, "ownDrop": {"usClass": {"n": "x"}}}, us_rows())
    assert rows[ROW2][3] == "FAIL"


def test_the_bf_b_row_warns_when_bf_b_is_missing_without_a_reason():
    """Jack (2026-11-20, verbatim): "Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish."
    'BF-B 가 있거나 빠진 이유' 줄: BF-B 가 목록에 없으면 이유가 없어도 경고 (이름을 적어요) — 기록(ownDrop)이 있든 없든 · 발행이든 사이트 점검이든."""
    for data in ({"usListSym": rec(missing={}), "ownDrop": {"usClass": EMPTY}}, {"usListSym": rec(missing={})}):
        for mode in ("publish", "live"):
            rows, _ = run_us(copy.deepcopy(data), us_rows(drop={"BF-B"}), mode)
            assert rows[ROW1][3] == "WARN" and "이유 없이 빠짐 1: BF-B" in rows[ROW1][1], rows[ROW1]
            assert rows[ROW2][3] == "PASS", rows[ROW2]


def gate_all(cur, prev, final):
    """발행 관문 전체 (test_us_share_class.test_the_rows_run_in_the_publish_gate 와 같은 시험 날짜)."""
    return V.run_checks(cur, prev, final, dt.date(2026, 10, 31), mode="publish", count_between=lambda a, b: 1,
                        sessions={"dates": [dt.date(2026, 10, d) for d in (27, 28, 29, 30)], "src": "시험"},
                        now=dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST), hilo=None)


@pytest.mark.parametrize("own", [None, EMPTY])
@pytest.mark.parametrize("missing", [{}, {"BF-B": ""}, {"BF-B": "오늘 S&P 500 목록에 없음 (지수에서 빠졌는지 확인)"}])
def test_bf_b_missing_warns_and_the_rest_publishes(missing, own):
    """Jack (2026-11-20): 한 종목이 출처에서 빠져도 발행을 막지 않아요. 관문 전체를 돌려요: BF-B 가 없는 파일(이유가 있든 없든 · ownDrop 이 있든
    없든)은 그 줄이 경고이고 실패가 하나도 없어요 (예전 규칙이면 이유 없이 빠진 두 경우는 발행 실패였어요)."""
    cur, prev, final = good_pair()
    assert "BF-B" not in {s["t"] for s in cur["data"]["stocks"]}
    cur["data"]["usListSym"] = rec(missing=missing)
    if own is not None:
        cur["data"]["ownDrop"] = {"usClass": own}
    rep = gate_all(cur, prev, final)
    rows = {r[0]: r for r in rep.rows}
    assert rows[ROW1][3] == "WARN" and "BF-B" in rows[ROW1][1], rows[ROW1]
    assert rep.failed == []


@pytest.mark.parametrize("own", [None, EMPTY])
@pytest.mark.parametrize("mode", ["publish", "live"])
def test_a_broken_bfb_ticker_published_still_fails_while_bf_b_missing_only_warns(own, mode):
    """BF-B 는 빠지고 S&P 500 목록의 점이 지워진 꼴 'BFB' 가 바뀌지 않고 실렸어요 (야후가 그 꼴에 다른 증권으로 답한 것 — 그 행의 가격 ·
    시가총액은 다른 회사의 숫자). BF-B 가 빠진 줄은 경고, 틀린 숫자를 보이는 BFB 행은 그대로 실패 (발행 · 사이트 점검 모두 · ownDrop 이 있든 없든)."""
    us = us_rows(drop={"BF-B"}, extra=[{"t": "BFB", "cls": "us", "price": 9.0}])
    data = {"usListSym": rec(spTickers=sorted({"AAPL", "BFB", "BRK-B"}), missing={})}
    if own is not None:
        data["ownDrop"] = {"usClass": own}
    rows, _ = run_us(data, us, mode)
    assert rows[ROW1][3] == "WARN" and "이유 없이 빠짐 1: BF-B" in rows[ROW1][1], rows[ROW1]
    assert rows[ROW2][3] == "FAIL", rows[ROW2]
    assert ("빼야 할 티커가 남아 실림: BFB" if own is not None else "S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 목록에 있음: BFB") in rows[ROW2][1]


def test_a_broken_bfb_ticker_fails_the_whole_publish_gate_and_only_that_row_fails():
    """관문 전체: 같은 파일(BF-B 없음 · BFB 실림)에서 실패는 출처 티커 줄 하나뿐 — BF-B 가 빠진 줄은 경고예요."""
    cur, prev, final = good_pair()
    src = next(s for s in cur["data"]["stocks"] if s.get("cls") == "us" and s["t"] == "U0000")
    cur["data"]["stocks"].append(dict(copy.deepcopy(src), t="BFB"))
    cur["data"]["usListSym"] = rec(spTickers=sorted({"AAPL", "BFB", "BRK-B"}), missing={})
    rep = gate_all(cur, prev, final)
    rows = {r[0]: r for r in rep.rows}
    assert rows[ROW1][3] == "WARN" and "이유 없이 빠짐 1: BF-B" in rows[ROW1][1]
    assert {r[0] for r in rep.failed} == {ROW2}, rep.failed


@pytest.mark.parametrize("own", [None, EMPTY])
@pytest.mark.parametrize("price", [0, None, -1.0, "x"])
def test_a_listed_bf_b_row_without_a_price_still_fails_to_publish(price, own):
    """BF-B 의 행이 목록에 있는데 가격이 없어요 (0 · 빈 칸 · 음수 · 숫자 아님) — 빠진 것이 아니라 앱이 그 종목을 가격 없이 보여요 (틀린 값).
    발행 실패는 예전 그대로 · 사이트 점검은 예전처럼 경고."""
    us = us_rows(drop={"BF-B"}, extra=[{"t": "BF-B", "cls": "us", "price": price}])
    data = {"usListSym": rec(missing={})}
    if own is not None:
        data["ownDrop"] = {"usClass": own}
    rows, _ = run_us(copy.deepcopy(data), us)
    assert rows[ROW1][3] == "FAIL" and "목록에 있는데 가격이 없음 1: BF-B" in rows[ROW1][1], rows[ROW1]
    rows, _ = run_us(copy.deepcopy(data), us, "live")
    assert rows[ROW1][3] == "WARN", rows[ROW1]


# ── #142: 숨긴 배당수익률의 줄 ─────────────────────────────────
@pytest.fixture
def line_pair():
    cur, prev, _ = good_pair()
    files, abc = with_lines(cur)
    return files, prev, abc


def blank(cur, monkeypatch, prev=None):
    """파이프라인처럼: 같은 함수로 비우고 data.json ownDrop.divLine 에 적어요 → (기록, 로그). prev: 직전 발행본 data.json (로그가 잃은 줄을 세요)."""
    lines = []
    monkeypatch.setattr(F, "log", lines.append)
    own = F.own_blank_div_lines(cur["data"]["stocks"], cur["data"]["divCheck"], prev)
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
    assert SUB_ROW in {r[0] for r in rep.failed} and "줄을 잃은 종목이 기준 2 을 넘음 (3)" in rows_of(rep)[SUB_ROW][1]


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


def _prev_with_lines(prev, cur, abc):
    """직전 발행본: 오늘과 같은 기록(proofSub)과 줄 2 · 3 · 4 가 있었어요."""
    had = copy.deepcopy(prev)
    had["data"]["divCheck"] = copy.deepcopy(cur["data"]["divCheck"])
    marks = {s["t"]: s["dvLine"] for s in abc}
    for s in had["data"]["stocks"]:
        if s.get("t") in marks:
            s["dvLine"] = marks[s["t"]]
    return had


@pytest.mark.parametrize("how", ["vanished", "broken"])
def test_lines_lost_with_their_record_count_toward_n(line_pair, monkeypatch, how):
    """리뷰 1차 S2 (probe3): 기록(proofSub)이 사라지거나 모양이 깨지고 줄도 함께 사라지면 비울 것이 없어 0 건이에요 — 그래도 직전 발행본의 줄
    2 · 3 · 4 를 오늘 기록으로 확인할 수 없으니 그 종목들은 이 실행에서 이유 줄을 잃어요. 그 수를 세요: N 이하면 경고, 넘으면 실패 (11-19 의 실제
    발행본은 30곳)."""
    cur, prev, abc = line_pair
    had = _prev_with_lines(prev, cur, abc)
    if how == "vanished":
        cur["data"]["divCheck"].pop("proofSub")
    else:
        cur["data"]["divCheck"]["proofSub"]["v"] = 2
    for s in abc:
        s.pop("dvLine")
    own, lines = blank(cur, monkeypatch, had["data"])
    assert own == EMPTY
    assert any(x.startswith(f"  !! {DIV_LOG}0건 비움 (관문 경고") for x in lines), lines                 # 리뷰 2차: '· 0건' 이 아니에요
    assert any(x.startswith(f"  !! {DIV_LOG}직전 발행본에 줄 2 · 3 · 4 가 있던 3곳은") for x in lines), lines
    rep = check(cur, had)
    row = rows_of(rep)[SUB_ROW]
    assert not rep.failed and row[3] == "WARN" and "오늘 기록으로 확인할 수 없는 직전 발행본의 줄 2 · 3 · 4 3곳" in row[1], rep.table()
    monkeypatch.setattr(V, "DIV_LINE_BLANK_MAX", 2)
    row = rows_of(check(cur, had))[SUB_ROW]
    assert row[3] == "FAIL" and "줄을 잃은 종목이 기준 2 을 넘음 (3)" in row[1], row
    assert rows_of(check(cur, had, mode="live"))[SUB_ROW][3] == "WARN"                  # 사이트 점검은 직전 발행본을 보지 않아요


def with_more_lines(files):
    """with_lines 에 data 어긋남(줄 3) 종목 d 를 하나 더 (data 3곳 · rights 1곳) — 파이프라인처럼 기록과 표시를 함께."""
    files, (a, b, c) = with_lines(files)
    kr = [x for x in files["data"]["stocks"] if x.get("cls") == "kr" and not x.get("fund") and x.get("divSt") == "nd"]
    d, e = kr[3], kr[4]
    d["dpsF"] = [None] * 3
    d["dps3a"] = [None if (v or 0) > 0 else v for v in d["dps3"]]
    mirror(files, d)
    d["dvLine"] = 3
    dc = files["data"]["divCheck"]
    proof, sub = dc["proof"], dc["proofSub"]
    recount(files)
    recount_why(files)
    proof.update(data=3, dataT=sorted([a["t"], b["t"], d["t"]]))
    sub["data"][d["t"]] = "div"
    files["data"]["divCheck"]["proof"], files["data"]["divCheck"]["proofSub"] = proof, sub
    return files, (a, b, c, d, e)


def test_blanked_lines_and_lines_lost_with_a_broken_part_are_counted_as_distinct_stocks(monkeypatch):
    """리뷰 2차 S-A (p1_union): 오늘 비운 줄(data 쪽 3곳)과 모양이 깨진 rights 기록과 함께 사라진 직전 발행본의 줄(3곳)은 서로 다른 종목이에요 —
    큰 값(3)이 아니라 합친 종목 수(6)로 세요 → 실제 N(5)을 넘어 발행 실패. 파이프라인 로그도 같은 수를 말해요."""
    cur, prev, _ = good_pair()
    cur, (a, b, c, d, e) = with_more_lines(cur)
    assert not check(copy.deepcopy(cur), prev).failed
    f = next(s for s in cur["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund") and s["t"] not in V.MUST
             and s["t"] not in {a["t"], b["t"], c["t"], d["t"], e["t"]})
    had = copy.deepcopy(prev)
    had["data"]["divCheck"] = copy.deepcopy(cur["data"]["divCheck"])
    for s in had["data"]["stocks"]:
        if s.get("t") in {c["t"], e["t"], f["t"]}:
            s["dvLine"] = 2                                                         # 직전 발행본: 유상증자 줄 3곳
    assert sum(1 for s in had["data"]["stocks"] if s.get("dvLine") == 2) == 3
    cur["data"]["divCheck"]["proofSub"]["rights"] = {c["t"]: "sh", "999999": "sh"}   # rights 기록이 깨지고 그 줄도 사라짐
    c.pop("dvLine")
    a["dvLine"], b["dvLine"], d["dvLine"] = 4, 3, 4                                  # data 쪽 틀린 줄 3곳 → 비움
    own, lines = blank(cur, monkeypatch, had["data"])
    assert own["n"] == 3 and {r[0] for r in own["rows"]} == {a["t"], b["t"], d["t"]}
    assert any("줄을 잃은 종목 6곳 — 5곳을 넘어 관문에서 실패해 발행하지 않아요" in x for x in lines), lines
    rep = check(cur, had)
    row = rows_of(rep)[SUB_ROW]
    assert V.DIV_LINE_BLANK_MAX == 5 and row[3] == "FAIL" and "줄을 잃은 종목이 기준 5 을 넘음 (6)" in row[1], row
    assert [r[0] for r in rep.failed] == [SUB_ROW], rep.table()
    assert rows_of(check(cur, had, mode="live"))[SUB_ROW][3] == "WARN"


def test_a_list_valued_line_never_crashes_the_count():
    """리뷰 2차 (nit 5): 직전 발행본의 줄 값이 목록 같은 값이어도 관문이 멈추지 않아요 (숫자만 봐요)."""
    prev = {"stocks": [{"t": "000010", "cls": "kr", "dvLine": [2]}, {"t": "000020", "cls": "kr", "dvLine": {"x": 3}},
                       {"t": "000030", "cls": "kr", "dvLine": True}, {"t": "000040", "cls": "kr", "dvLine": 2}]}
    assert V.div_lines_lost(prev, set()) == ["000040"] and V.div_lines_lost(prev, {"rights", "data"}) == []
    assert V.div_lines_lost(None, set()) == []
    kr = [{"t": "000010", "cls": "kr", "dvLine": [2]}, {"t": "000020", "cls": "kr", "dvLine": {"x": 3}}]
    assert V.div_line_bad_rows(kr, {})[0] == []


def test_a_broken_record_is_not_counted_as_stocks_without_a_line(line_pair, monkeypatch):
    """리뷰 1차 (nit): 모양이 틀린 기록의 종목을 '줄 없음' 으로 세지 않아요 — 확인하지 못한 기록이라고 적어요."""
    cur, prev, _abc = line_pair
    cur["data"]["divCheck"]["proofSub"]["v"] = 2
    blank(cur, monkeypatch)
    row = rows_of(check(cur, prev))[SUB_ROW]
    assert "유상증자 줄 0 · 배당 자료 줄 0 · 줄 없음 0 (확인하지 못한 기록: data · rights)" in row[1], row


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
