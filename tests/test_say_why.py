# -*- coding: utf-8 -*-
"""say-why 두 줄 (Jack, 2026-11-08: 줄이거나 빼거나 어림한 숫자는 무엇을 왜 그랬는지 한 줄로 말해요).

1. 포트폴리오 만들기 · 기준 단계 · 내 점수 칸 밑: '하루 거래대금 5억원 미만 종목과 우선주는 빼고 셌어요.' (build.s1.remainWhy).
   이 줄이 참인지는 엔진이 정해요: 칸의 수(engine.meterCount, 점수 전 · 후 모두)는 하루 평균 거래대금이 5억원(LIQ_FLOOR_EOK) 밑인
   종목과 우선주(한국: 코드 끝이 0 이 아닌 종목 · 미국: 이름이나 코드로 알아본 우선주 · 예탁증서)를 세지 않아요. 바닥이 바뀌면
   이 검사가 걸려서 줄도 함께 고치게 돼요.
2. 매수 계획 · 연 배당금: 미국 종목을 산 계획에만 점검의 줄 '미국 종목은 최근 배당을 1년치로 환산한 값이에요.' (rpt.divUs) 을
   같은 키로 써요 (문구를 두 벌 두지 않아요).
화면에 그려진 두 줄(320 · 390)은 tests/smoke_v2.py scene_say_why 가 봐요.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copytrace import copy_strings, read  # noqa: E402
from test_v2_engine import run, kr, us, SET, NODE  # noqa: E402,F401

WHY = "하루 거래대금 5억원 미만 종목과 우선주는 빼고 셌어요."
DIV_US = "미국 종목은 최근 배당을 1년치로 환산한 값이에요."


def test_meter_line_is_the_approved_copy_and_is_used_once_under_the_meter():
    c, _ = copy_strings()
    assert c["build"]["s1"]["remainWhy"] == WHY
    src = read("src/v2/build.jsx")
    assert src.count("{s1.remainWhy}") == 1 and '<Note data-ui-v2="meter-why"' in src
    # 내 점수 칸(위에 붙는 칸) 바로 뒤, 깐깐함 칸 앞: 칸 안이 아니에요
    i, j, k = src.index("<Meter st={st}"), src.index('data-ui-v2="meter-why"'), src.index("<Label>{s1.strictLabel}</Label>")
    assert i < j < k, (i, j, k)


def test_meter_count_leaves_out_the_trading_value_floor_and_preferred_shares():
    stocks = [kr("000010"), kr("000020", val20=5.0), kr("000030", val20=4.99), kr("005935", val20=900.0), kr("00680K", val20=900.0),
              us("AAA"), us("BBB", val=4.99), us("CCC", val=5.0), us("PFDX", nk="Pfdco 8% Series A Preferred Stock", val=900.0),
              us("ABCDM", val=900.0)]
    got = run(SET + "const m = (o) => E.meterCount(E.screen(stocks, S(o)));"
              "out = { floor: E.LIQ_FLOOR_EOK, kr: m({ mix: 'kr' }), us: m({ mix: 'us' }), both: m({ mix: 'k55' }),"
              " krPts: m({ mix: 'kr', points: { value: 5 }, strict: 'loose' }), usPts: m({ mix: 'us', points: { value: 5 }, strict: 'loose' }),"
              " list: Object.values(E.screen(stocks, S({ mix: 'k55', points: { value: 5 }, strict: 'loose' })).markets).flatMap((x) => x.survivors.map((s) => s.t)).sort() };",
              stocks=stocks)
    assert got["floor"] == 5 and "5억원" in WHY, got                    # 줄의 '5억원' 은 엔진의 바닥과 같아요
    # 한국: 000010 · 000020(딱 5억) 만. 4.99억 · 우선주 둘은 빠져요. 미국: AAA · CCC(딱 5억) 만. 4.99억 · 우선주 · 예탁증서 코드는 빠져요
    assert got["kr"] == {"pool": True, "n": 2} and got["us"] == {"pool": True, "n": 2} and got["both"] == {"pool": True, "n": 4}, got
    assert got["krPts"] == {"pool": False, "n": 2} and got["usPts"] == {"pool": False, "n": 2}, got
    assert got["list"] == ["000010", "000020", "AAA", "CCC"], got


def test_plan_reuses_the_checkup_us_dividend_line_with_one_key():
    c, flat = copy_strings()
    assert c["rpt"]["divUs"] == DIV_US
    assert [p for p, v in flat if v == DIV_US] == ["rpt.divUs"], "같은 문구를 두 벌 두지 않아요"
    assert read("src/copy/v2.js").count(DIV_US) == 1
    plan = read("src/v2/plan.jsx")
    assert plan.count("{C.rpt.divUs}") == 1 and 'data-ui-v2="div-us"' in plan
    # 미국 종목을 산 계획(주식 수 > 0, 배당을 아는 종목: engine.usDividendCounted)에만 · '세전 금액이에요' 바로 다음 줄
    assert "const usDiv = usDividendCounted(plan.rows);" in plan
    assert plan.index("{C.plan.preTax}</div>") < plan.index("{usDiv && <div data-ui-v2=\"div-us\"") < plan.index("div.unknown > 0 &&")


def test_us_dividend_line_only_when_a_known_us_dividend_is_in_the_total():
    """engine.usDividendCounted: 미국 종목을 사고(주식 수 > 0) 그 배당(dy)을 알 때만 참이에요. 계획의 유일한 미국 종목이 배당을 모르면
    (annualDividend 가 0원으로 세고 '배당 정보가 없는 종목' 줄이 말해요) 미국 배당 줄은 없어요. 채권 · 금 ETF 는 미국 종목이 아니에요."""
    k, u = kr("000010"), us("AAA")
    rows = lambda *xs: [{"s": s, "shares": n, "cost": 1000000} for s, n in xs]
    cases = {
        "kr only": rows((k, 10)),
        "us with dividend": rows((k, 10), (u, 3)),
        "us dividend 0": rows((k, 10), (us("ZERO", dy=0.0), 3)),
        "only us has no dividend": rows((k, 10), (us("NODY", dy=None), 3)),
        "us not bought": rows((k, 10), (u, 0)),
        "bond and gold etfs": rows((k, 10), ({"t": "114260", "cls": "bond", "price": 1.0, "dy": 3.0}, 5), ({"t": "132030", "cls": "metal", "price": 1.0}, 5)),
        "krx-listed us etf without dy": rows((k, 10), ({"t": "379800", "cls": "us", "price": 1.0, "etf": True}, 5)),
    }
    got = run("out = Object.fromEntries(Object.entries(CASES).map(([n, r]) => [n, { line: E.usDividendCounted(r), unknown: E.annualDividend(r, 1400).unknown }]));",
              CASES=cases)
    assert {n: g["line"] for n, g in got.items()} == {
        "kr only": False, "us with dividend": True, "us dividend 0": True, "only us has no dividend": False,
        "us not bought": False, "bond and gold etfs": False, "krx-listed us etf without dy": False}, got
    assert got["only us has no dividend"]["unknown"] == 1, got           # 그 종목은 '배당 정보가 없는 종목' 줄이 말해요
