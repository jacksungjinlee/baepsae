# -*- coding: utf-8 -*-
"""발행 관문의 새 줄 (2026-11-14, Jack Q3 · 리뷰 S4 · 더 엄격하게만): 다시 읽은 뒤(epsBasis "owners")에도 날짜가 지난 '고치는 중' 줄
('PER과 EPS는 계산 방법을 고치는 중이라 11월 10일에 바뀔 수 있어요.')이 보일 국내 회사가 있으면 이름을 대고 경고해요. 앱의 규칙
(src/repair.js epsFixNeeded)과 같은 조건: PER · EPS · ROE 가 보이고, epsIn.b 가 o · s · t 가 아니거나 epsIn 이 없음 (해외 기업 · 원화가 아닌
재무제표 · 공시 단위 확인 회사는 숫자가 없어 빼요)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import validate_data as V  # noqa: E402

IN = lambda b: {"ni": 100.0, "b": b, "p": "ttm", "sh": 1000000}   # noqa: E731


def row(rep):
    return next(r for r in rep.rows if r[0] == V.EPS_LINE_LEFT)


def run(comps, basis="owners"):
    rep = V.Report()
    V.check_eps_line_left(rep, {"epsBasis": basis, "companies": comps} if basis else {"companies": comps}, comps)
    return rep


def test_quiet_when_every_company_with_a_per_eps_or_roe_has_a_receipt():
    comps = [{"t": "005930", "nk": "삼성전자", "eps": 22511.0, "per": 20.1, "roe": 9.0, "epsIn": IN("o")},
             {"t": "005380", "nk": "현대차", "eps": 30000.0, "epsIn": IN("t")},
             {"t": "000020", "nk": "별도", "roe": 3.0, "epsIn": IN("s")},
             {"t": "005935", "nk": "삼성전자우"},                                        # 우선주 · 재무제표 없음: 숫자가 없어요
             {"t": "950250", "nk": "테라뷰", "roe": 5.0},                                 # 해외 기업
             {"t": "241560", "nk": "두산밥캣", "roe": 4.0, "stmtCur": "USD"},             # 원화가 아닌 재무제표
             {"t": "028260", "nk": "단위", "roe": 4.0, "unitChk": ["scale"]}]             # 공시 단위 확인
    rep = run(comps)
    r = row(rep)
    assert r[3] == "PASS" and r[1] == "0곳" and not rep.details and not rep.failed


def test_names_each_company_that_would_show_the_dated_line():
    comps = [{"t": "000010", "nk": "가나", "eps": 100.0},                              # 영수증 없음
             {"t": "000020", "nk": "다라", "roe": 7.0},                                 # ROE 만 (영수증 모양 줄은 못 잡아요)
             {"t": "000030", "nk": "마바", "per": 12.0, "epsIn": IN("x")},              # 모르는 b
             {"t": "000040", "nk": "사아", "eps": 1.0, "epsIn": "o"}]                    # 모양이 틀림
    rep = run(comps)
    r = row(rep)
    assert r[3] == "WARN" and r[1].startswith("4곳: 000010 가나, 000020 다라, 000030 마바, 000040 사아"), r
    assert (V.EPS_LINE_LEFT, ["000010 가나", "000020 다라", "000030 마바", "000040 사아"]) in rep.details
    assert not rep.failed                                                                  # 경고만: 발행을 멈추지 않아요


def test_skipped_before_the_reread():
    rep = run([{"t": "000010", "nk": "가나", "eps": 100.0}], basis=None)
    assert row(rep)[3] == "SKIP"


def test_the_gate_calls_it():
    src = open(os.path.join(ROOT, "validate_data.py"), encoding="utf-8").read()
    assert "    check_eps_line_left(rep, corp, comps)" in src
