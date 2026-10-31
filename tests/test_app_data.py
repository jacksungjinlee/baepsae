# -*- coding: utf-8 -*-
"""src/data.js (앱의 데이터 읽기) — Node 로 직접 돌려봐요. 따옴표 안의 'NaN' 글자는 그대로 두고,
따옴표 밖의 NaN·Infinity 만 null 로 고쳐야 해요 (미국 기업 설명에 그런 낱말이 들어갈 수 있어서)."""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")


def run_js(body):
    code = "import * as D from './src/data.js';\n" + body
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_repair_only_outside_strings():
    raw = '{"a":NaN,"b":[1,Infinity,-Infinity],"de":"NaN and Infinity are words here \\" NaN","c":{"d":NaN}}'
    out = run_js(f"const r = D.repairJsonText({json.dumps(raw)}); console.log(JSON.stringify({{n: r.n, v: JSON.parse(r.text)}}));")
    assert out["n"] == 4   # a · Infinity · -Infinity · d (글자 안의 NaN·Infinity 는 세지 않아요)
    assert out["v"] == {"a": None, "b": [1, None, None], "de": 'NaN and Infinity are words here " NaN', "c": {"d": None}}


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_clean_json_is_untouched():
    raw = '{"nk":"삼성전자","x":[1.5,-2,"Infinity"]}'
    out = run_js(f"const r = D.repairJsonText({json.dumps(raw)}); console.log(JSON.stringify({{n: r.n, same: r.text === {json.dumps(raw)}}}));")
    assert out == {"n": 0, "same": True}


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_freshness_counts_from_published_at():
    out = run_js(
        "const now = Date.parse('2026-11-06T10:00:00+09:00');"
        "console.log(JSON.stringify(["
        "D.freshness('2026-10-30', '2026-10-31T09:30:00+09:00', 'ko', now),"
        "D.freshness('2026-10-30', '2026-11-03T09:30:00+09:00', 'ko', now),"
        "D.freshness('2026-10-30', '2026-11-03T09:30:00+09:00', 'en', now),"
        "D.freshness('2026-10-30', null, 'ko', now)]));")
    assert out[0] == {"md": "10월 30일", "days": 6, "stale": True}     # 발행 6일 전 → 멈춤
    assert out[1] == {"md": "10월 30일", "days": 3, "stale": False}    # 긴 연휴: 가격 날짜는 오래돼도 발행은 3일 전
    assert out[2]["md"] == "Oct 30"
    assert out[3]["stale"] is False and out[3]["days"] is None


# ── mergeStocks: 내장 목록에 없는 종목에 숫자를 지어내지 않아요 (PR #4 리뷰 3번) ──
@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_auto_stocks_keep_blanks_and_flag_missing_risk_inputs():
    base = [{"t": "005930", "nk": "삼성전자", "ne": "Samsung", "s": "semi", "price": 78000, "beta": 1.1, "vol": 30,
             "per": 14, "pbr": 1.4, "dy": 1.8, "al": -6}]
    live = [
        {"t": "005930", "price": 225000, "beta": 1.2, "vol": 33, "per": None, "pbr": 2.1, "dy": None},
        {"t": "111111", "nk": "새종목", "cls": "kr", "price": 5000, "beta": 0.9, "vol": 40, "per": None, "pbr": None, "dy": None},
        {"t": "222222", "nk": "베타없음", "cls": "kr", "price": 7000, "beta": None, "vol": 35},
        {"t": "333333", "nk": "변동성없음", "cls": "kr", "price": 7000, "beta": 1.0, "vol": None},
        {"t": "444444", "nk": "가격없음", "cls": "kr", "price": None, "beta": 1.0, "vol": 30},
    ]
    code = (f"const warn = []; console.warn = (m) => warn.push(m);"
            f"const out = D.mergeStocks({json.dumps(base, ensure_ascii=False)}, {json.dumps(live, ensure_ascii=False)});"
            "console.log(JSON.stringify({out, warn}));")
    got = run_js(code)
    by = {s["t"]: s for s in got["out"]}
    assert set(by) == {"005930", "111111", "222222", "333333"}, by.keys()   # 가격이 없는 종목만 빼요
    n = by["111111"]
    assert n["live"] is True and n["beta"] == 0.9 and n["vol"] == 40 and not n.get("noRisk")
    assert n["per"] is None and n["pbr"] is None and n["dy"] is None        # 0 이 아니라 빈 칸 → 화면에 '–'
    for t in ("222222", "333333"):                                          # 이미 담은 종목이 사라지지 않게 목록에 둬요
        x = by[t]
        assert x["noRisk"] is True and x["beta"] is None and x["vol"] is None and x["live"] is True and x["price"] == 7000
    s = by["005930"]
    assert s["price"] == 225000 and s["per"] is None and s["dy"] is None and s["live"] is True
    assert any("가격이 없어" in w and "444444" in w for w in got["warn"]), got["warn"]
    assert any("위험 계산에서 빼는 종목 2개" in w for w in got["warn"]), got["warn"]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_merge_without_live_data_marks_everything_not_live():
    base = [{"t": "005930", "nk": "삼성전자", "price": 78000, "beta": 1.1, "vol": 30}]
    got = run_js(f"console.log(JSON.stringify(D.mergeStocks({json.dumps(base, ensure_ascii=False)}, null)));")
    assert got[0]["live"] is False
