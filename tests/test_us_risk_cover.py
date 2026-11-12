# -*- coding: utf-8 -*-
"""2026-11-12 (Jack): 관문 줄 '미국 beta 채움' · '미국 vol 채움' (+ 직전 발행 대비 변화) — 더하기만.

국내는 베타 · 변동성 채움을 95% 로 막는데 미국은 줄이 없었어요. 일부만 빠진 날(예: 10%, 예전 앱 내장 종목은 셋 이하)은 그대로
발행됐어요 (#106 화면 검사는 내장 종목이 넷 넘게 빠질 때만 막아요). 같은 규칙을 미국에도 걸어요: 95% 아래면 실패 (97% 아래는 경고,
그때 빈 종목 이름도 적어요), 직전 발행보다 10점 넘게 줄면 실패 (국내 줄과 맞춘 줄이라 바닥보다 먼저 걸리지는 않아요).
7-29 이후 70번 발행에서 베타 97.7~99.1% · 변동성 97.6~99.1%."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402
from test_validate import check, failed_names  # noqa: E402

KEYS = ("beta", "vol")


def us_of(files):
    return [s for s in files["data"]["stocks"] if s.get("cls") == "us" and not s.get("fund")]


def blank(files, key, n):
    """미국 종목 n 개의 key 를 비워요 (칸을 지워요 — 파이프라인이 못 구한 날처럼)."""
    for s in us_of(files)[:n]:
        s.pop(key, None)


def row(rep, name):
    return next(r for r in rep.rows if r[0] == name)


def warned_names(rep):
    return {r[0] for r in rep.warned}


def test_rule_is_the_korean_one():
    """미국 줄은 국내 베타 · 변동성 줄과 같은 95% (이 값은 안전 규칙이에요: 낮추려면 Jack 의 승인이 필요해요)."""
    assert V.COVER_US_RISK == {"beta": 95, "vol": 95}
    assert all(V.COVER_US_RISK[k] >= V.COVER_KR[k] for k in KEYS)


def test_good_data_shows_both_rows_and_passes():
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    for k in KEYS:
        assert row(rep, f"미국 {k} 채움")[3] == "PASS"
        assert row(rep, f"미국 {k} 채움 변화")[3] == "PASS"


@pytest.mark.parametrize("key", KEYS)
def test_all_us_values_gone_fails(key):
    """파이프라인이 미국 베타(또는 변동성)를 통째로 못 구한 날: 발행을 막아요."""
    cur, prev, final = good_pair()
    blank(cur, key, len(us_of(cur)))
    rep = check(cur, prev, final)
    assert f"미국 {key} 채움" in failed_names(rep), rep.table()
    assert f"미국 {key} 채움 변화" in failed_names(rep), rep.table()


@pytest.mark.parametrize("key", KEYS)
def test_below_95_fails(key):
    cur, prev, final = good_pair()
    n = len(us_of(cur))
    blank(cur, key, n * 6 // 100)                    # 600 개 중 36 개 빔 → 94.0%
    rep = check(cur, prev, final)
    assert f"미국 {key} 채움" in failed_names(rep), rep.table()
    assert row(rep, f"미국 {key} 채움")[1] == "94.0% (빈 칸 36 / 600)"


@pytest.mark.parametrize("key", KEYS)
def test_between_95_and_97_warns_but_publishes(key):
    cur, prev, final = good_pair()
    blank(cur, key, 24)                              # 600 개 중 24 개 빔 → 96.0%
    rep = check(cur, prev, final)
    assert f"미국 {key} 채움" not in failed_names(rep), rep.table()
    assert f"미국 {key} 채움" in warned_names(rep), rep.table()


@pytest.mark.parametrize("key", KEYS)
def test_a_few_new_listings_without_history_pass_quietly(key):
    """새로 상장해 이력이 짧은 회사 몇 곳 (지금도 12곳 정도): 경고도 없어요."""
    cur, prev, final = good_pair()
    blank(cur, key, 12)                              # 98.0%
    rep = check(cur, prev, final)
    assert f"미국 {key} 채움" not in failed_names(rep) | warned_names(rep), rep.table()


def test_the_change_row_follows_the_korean_rule():
    """직전보다 10점 넘게 줄면 실패 — 국내 줄과 같은 규칙. 직전이 100% 여도 90% 아래라야 걸리니, 바닥(95%)보다 먼저 걸리지는 않아요."""
    rep = V.Report()
    prev = {"stocks": [{"t": f"P{i}", "cls": "us", "beta": 1.0} for i in range(100)]}
    cur_us = [{"t": f"P{i}", "cls": "us", "beta": 1.0 if i < 89 else None} for i in range(100)]
    V.check_us_risk_cover(rep, cur_us, prev)
    assert row(rep, "미국 beta 채움 변화")[3] == "FAIL" and "100.0 → 89.0" in row(rep, "미국 beta 채움 변화")[1]
    rep2 = V.Report()
    cur_ok = [{"t": f"P{i}", "cls": "us", "beta": 1.0 if i < 90 else None} for i in range(100)]
    V.check_us_risk_cover(rep2, cur_ok, prev)
    assert row(rep2, "미국 beta 채움 변화")[3] == "PASS"


def test_us_listed_funds_are_not_counted_on_either_side():
    """'fund' 표시가 있는 미국 줄은 세지 않아요 — 오늘도 직전도. ETF 는 세요 (두 앱 모두 ETF 베타를 써요)."""
    cur, prev, final = good_pair()
    for files in (cur, prev):
        files["data"]["stocks"] += [{"t": f"F{i:03d}", "nk": f"펀드 {i}", "cls": "us", "price": 10.0, "fund": True, "etf": True}
                                    for i in range(60)]                  # 베타 · 변동성 없는 펀드 60개 (세면 91% 로 떨어져요)
    rep = check(cur, prev, final)
    for k in KEYS:
        assert row(rep, f"미국 {k} 채움")[1].startswith("100.0%"), rep.table()
        assert row(rep, f"미국 {k} 채움 변화")[1] == "100.0 → 100.0", rep.table()


@pytest.mark.parametrize("mode", ["bootstrap", "live"])
def test_the_rows_also_run_without_a_previous_publication(mode):
    """첫 실행(bootstrap)과 사이트 점검(--live · 배포와 감시)에서도 바닥 줄이 돌아요."""
    cur, _, final = good_pair()
    blank(cur, "beta", len(us_of(cur)))
    rep = check(cur, None, final, mode=mode)
    assert "미국 beta 채움" in failed_names(rep), rep.table()


def test_a_beta_of_zero_counts_as_filled():
    rep = V.Report()
    V.check_us_risk_cover(rep, [{"t": "KO", "cls": "us", "beta": 0.0, "vol": 20.0}], None)
    assert row(rep, "미국 beta 채움")[1].startswith("100.0%")


def test_below_97_the_blank_stocks_are_named():
    """경고나 실패면 빈 종목 이름을 적어요 — 새로 상장한 회사인지 파이프라인 문제인지 바로 보이게."""
    rep = V.Report()
    us = [{"t": f"U{i}", "cls": "us", "beta": 1.0, "vol": 20.0} for i in range(96)]
    us += [{"t": f"NEW{i}", "cls": "us", "vol": 20.0} for i in range(4)]
    V.check_us_risk_cover(rep, us, None)
    assert ("미국 beta 빈 종목", ["NEW0", "NEW1", "NEW2", "NEW3"]) in rep.details
    assert not any(t == "미국 vol 빈 종목" for t, _ in rep.details)        # 97% 위면 목록 없음
    rep = V.Report()
    V.check_us_risk_cover(rep, [{"t": f"U{i}", "cls": "us", "beta": 1.0, "vol": 20.0} for i in range(99)] + us[-1:], None)   # 99% — 조용
    assert not rep.details and not rep.warned


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "", None, True])
def test_non_numbers_count_as_blank(bad):
    """숫자가 아닌 값(NaN · 무한대 · 빈 글자 · null · 참거짓)은 빈 칸으로 세요 (국내 줄과 같은 num())."""
    rep = V.Report()
    us = [{"t": f"U{i}", "cls": "us", "beta": 1.0, "vol": 20.0} for i in range(90)]
    us += [{"t": f"X{i}", "cls": "us", "beta": bad, "vol": 20.0} for i in range(10)]
    V.check_us_risk_cover(rep, us, None)
    assert row(rep, "미국 beta 채움")[3] == "FAIL" and row(rep, "미국 beta 채움")[1] == "90.0% (빈 칸 10 / 100)"
    assert row(rep, "미국 vol 채움")[3] == "PASS"


def test_no_us_stocks_fails():
    """미국 종목이 하나도 없으면 0% — 실패 (다른 줄도 막지만 이 줄도 조용히 넘어가지 않아요)."""
    rep = V.Report()
    V.check_us_risk_cover(rep, [], None)
    assert {"미국 beta 채움", "미국 vol 채움"} <= {r[0] for r in rep.failed}


def test_without_a_previous_publish_only_the_floor_rows_run():
    rep = V.Report()
    V.check_us_risk_cover(rep, [{"t": "A", "cls": "us", "beta": 1.0, "vol": 20.0}], None)
    names = [r[0] for r in rep.rows]
    assert names == ["미국 beta 채움", "미국 vol 채움"]
