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
