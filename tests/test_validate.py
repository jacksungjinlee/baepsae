# -*- coding: utf-8 -*-
"""validate_data.py — 좋은 데이터는 통과, 스펙 § E 의 must-fail 데이터는 반드시 실패. (네트워크 없음)"""
import datetime as dt
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import validate_data as V  # noqa: E402
from fixture_data import good_pair, stock, clone  # noqa: E402

TODAY = dt.date(2026, 10, 31)
FIX = os.path.join(ROOT, "tests", "fixtures", "listing")


def check(cur, prev, final, mode="publish", between=lambda a, b: 1):
    return V.run_checks(cur, prev, final, TODAY, mode=mode, count_between=between)


def failed_names(rep):
    return {r[0] for r in rep.failed}


def test_good_data_passes():
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()


# ── 스펙 § E must-fail ────────────────────────────────────
def test_nan_anywhere_fails_parse(tmp_path):
    cur, _, _ = good_pair()
    for name, obj in cur.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    text = (tmp_path / "corp.json").read_text(encoding="utf-8").replace('"per": 8.4', '"per": NaN', 1)
    text = text.replace('"pbr":', '"pbr": NaN, "x":', 1)
    (tmp_path / "corp.json").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="NaN"):
        V.load_dir(str(tmp_path))
    assert V.main(["--dir", str(tmp_path), "--bootstrap", "--today", "2026-10-31"]) == 1


def test_missing_005930_fails():
    cur, prev, final = good_pair()
    cur["data"]["stocks"] = [s for s in cur["data"]["stocks"] if s["t"] != "005930"]
    assert "필수 종목 (가격·시총)" in failed_names(check(cur, prev, final))


def test_alphabetical_universe_fails():
    # 2026-10 사고: 시가총액이 비고, 가나다순 앞쪽만 남음 (현대차 등 빠짐)
    cur, prev, final = good_pair()
    kr = [s for s in cur["data"]["stocks"] if s["cls"] == "kr"]
    keep = sorted(kr, key=lambda s: s["nk"])[:2350]
    for s in keep:
        s["cap"] = None
    cur["data"]["stocks"] = keep + [s for s in cur["data"]["stocks"] if s["cls"] != "kr"]
    bad = failed_names(check(cur, prev, final))
    assert {"필수 종목 (가격·시총)", "국내 cap 채움", "시총 상위 20이 가나다순 아님"} <= bad


def test_per_pbr_collapse_fails():
    cur, prev, final = good_pair()
    for s in cur["data"]["stocks"]:
        if s["cls"] == "kr":
            s["per"] = s["pbr"] = None
    bad = failed_names(check(cur, prev, final))
    assert {"국내 per 채움", "국내 pbr 채움", "국내 per 채움 변화", "국내 pbr 채움 변화"} <= bad


def test_pxdate_one_day_stale_fails():
    cur, prev, final = good_pair()
    final = dict(final, date=dt.date(2026, 10, 30))
    cur["data"]["pxDate"] = cur["data"]["ksDate"] = "2026-10-29"
    assert "pxDate = 최종본 날짜" in failed_names(check(cur, prev, final))


def test_pxdate_backwards_fails():
    cur, prev, final = good_pair()
    prev["data"]["pxDate"] = "2026-10-31"
    assert "pxDate 가 뒤로 가지 않음" in failed_names(check(cur, prev, final))


def test_intraday_prices_fail():
    # 장중·시간외 가격 = 공식 종가와 다름
    cur, prev, final = good_pair()
    for s in cur["data"]["stocks"]:
        if s["cls"] == "kr":
            s["price"] = s["price"] + 500
    bad = failed_names(check(cur, prev, final))
    assert {"한국 가격 = 공식 종가", "005930 = 공식 종가"} <= bad


def test_one_corrupted_samsung_price_fails():
    # 워크플로 selftest=corrupt-price 와 같은 상황
    cur, prev, final = good_pair()
    stock(cur, "005930")["price"] = round(stock(cur, "005930")["price"] * 1.1)
    assert "005930 = 공식 종가" in failed_names(check(cur, prev, final))


def test_five_percent_jumping_fifty_percent_fails():
    cur, prev, final = good_pair()
    kr = [s for s in cur["data"]["stocks"] if s["cls"] == "kr"]
    for s in kr[: len(kr) // 20]:
        s["price"] = round(s["price"] * 1.5)
        final["closes"][s["t"]] = s["price"]      # 공식 종가 검사와 따로, 변동 검사만 보도록
    assert "큰 가격 변동 비율" in failed_names(check(cur, prev, final))


def test_unchanged_us_prices_with_new_uspxdate_fails():
    cur, prev, final = good_pair()
    pmap = {s["t"]: s["price"] for s in prev["data"]["stocks"] if s["cls"] == "us"}
    for s in cur["data"]["stocks"]:
        if s["cls"] == "us":
            s["price"] = pmap[s["t"]]
    assert "미국 가격이 바뀌었는지" in failed_names(check(cur, prev, final))


def test_fx_zero_fails():
    cur, prev, final = good_pair()
    cur["data"]["fx"] = 0
    bad = failed_names(check(cur, prev, final))
    assert {"환율 범위", "환율 변화"} <= bad


# ── Jack 결정 (2026-10-31) ─────────────────────────────────
def drop_bonds(cur, n):
    bonds = [s for s in cur["data"]["stocks"] if s["cls"] == "bond"]
    gone = {s["t"] for s in bonds[:n]}
    cur["data"]["stocks"] = [s for s in cur["data"]["stocks"] if s["t"] not in gone]


def test_bonds_seven_is_warning_not_failure():
    cur, prev, final = good_pair()
    drop_bonds(cur, 1)
    rep = check(cur, prev, final)
    assert not rep.failed
    assert any(r[0] == "채권 ETF" and r[3] == "WARN" for r in rep.rows)


def test_bonds_six_fails():
    cur, prev, final = good_pair()
    drop_bonds(cur, 2)
    assert "채권 ETF" in failed_names(check(cur, prev, final))


def test_us_detail_coverage_drop_fails():
    # run 85: 780개 중 198개 상세 정보 실패 → 이름이 티커 그대로
    cur, prev, final = good_pair()
    us = [s for s in cur["data"]["stocks"] if s["cls"] == "us"]
    for s in us[: int(len(us) * 0.26)]:
        s["nk"] = s["ne"] = s["t"]
        s.pop("de", None)
    bad = failed_names(check(cur, prev, final))
    assert {"미국 이름 채움", "미국 설명 채움", "미국 이름 채움 변화", "미국 설명 채움 변화"} <= bad


# ── 그 밖의 안전장치 ─────────────────────────────────────
def test_missing_previous_fails_unless_bootstrap():
    cur, _, final = good_pair()
    assert "직전 발행본 읽기" in failed_names(check(cur, None, final))
    rep = check(cur, None, final, mode="bootstrap")
    assert not rep.failed, rep.table()


def test_fallback_risk_free_rate_fails():
    cur, prev, final = good_pair()
    cur["data"]["settings"]["rfSrc"] = "fallback"
    assert "무위험수익률 출처" in failed_names(check(cur, prev, final))


def test_stale_rates_curve_fails():
    cur, prev, final = good_pair()
    cur["macro"]["curve"]["date"] = "2026-10-20"
    assert "국고채 커브 날짜" in failed_names(check(cur, prev, final))


def test_missing_fund_items_fail():
    cur, prev, final = good_pair()
    cur["data"]["stocks"] = [s for s in cur["data"]["stocks"] if s["t"] != "04020000"]
    assert "ETF·금현물 5종" in failed_names(check(cur, prev, final))


def test_kospi_date_must_match():
    cur, prev, final = good_pair()
    cur["data"]["ksDate"] = "2026-10-29"
    assert "KOSPI 마지막 날 = pxDate" in failed_names(check(cur, prev, final))


def test_old_format_previous_uses_asof_minus_one():
    cur, prev, final = good_pair()
    for k in ("pxDate", "usPxDate"):
        prev["data"].pop(k)
    prev["data"]["asOf"] = "2026-10-16"      # 10/17 발행본 형식
    notes = []
    rep = V.run_checks(cur, prev, final, TODAY, count_between=lambda a, b: 10, notes=notes)
    assert not rep.failed, rep.table()
    assert any("예전 형식" in n for n in notes)


def test_live_mode_has_no_relative_checks():
    cur, _, final = good_pair()
    rep = check(cur, None, final, mode="live")
    assert not rep.failed, rep.table()
    assert not any("변화" in r[0] for r in rep.rows)


# ── 최종본 날짜 (validate_data 자체 구현) ───────────────────
def text_of(name):
    with open(os.path.join(FIX, name + ".csv"), encoding="utf-8") as f:
        return f.read()


def test_official_close_is_marcap_over_shares():
    closes, share = V.official_closes(text_of("2026-10-29_1958"))
    assert share == 1.0
    assert closes["005930"] == 232000          # Close 열은 230,500 (시간외 가격)
    assert closes["005380"] == 292500


def kst(d, hm):
    return dt.datetime.combine(d, dt.time(int(hm[:2]), int(hm[2:])), V.KST)


def test_latest_final_16h_rule():
    d29, d28 = dt.date(2026, 10, 29), dt.date(2026, 10, 28)
    texts = {d29: text_of("2026-10-29_1319"), d28: text_of("2026-10-28_1921")}
    commits = {d29: "1319", d28: "1921"}
    d, closes, how = V.latest_final(dt.date(2026, 10, 30), texts.get, lambda d: kst(d, commits[d]))
    assert d == d28                             # 13:19 장중본은 최종본이 아니에요
    texts[d29], commits[d29] = text_of("2026-10-29_1958"), "1749"
    d, closes, how = V.latest_final(dt.date(2026, 10, 30), texts.get, lambda d: kst(d, commits[d]))
    assert d == d29 and closes["005930"] == 232000   # 17:49 도 16시 이후라 인정 (v17.5)


def test_latest_final_skips_blank_premarket_file():
    d29, d28 = dt.date(2026, 10, 29), dt.date(2026, 10, 28)
    texts = {d29: text_of("2026-10-29_0544"), d28: text_of("2026-10-28_1921")}
    d, _, _ = V.latest_final(dt.date(2026, 10, 30), texts.get, lambda d: kst(d, "2000"))
    assert d == d28


def test_count_final_between_counts_trading_days_only():
    days = {dt.date(2026, 10, 24): text_of("2026-10-24_0444"), dt.date(2026, 10, 25): text_of("2026-10-24_0444"),
            dt.date(2026, 10, 26): text_of("2026-10-28_1921"), dt.date(2026, 10, 27): text_of("2026-10-28_1921")}
    assert V.count_final_between(dt.date(2026, 10, 23), dt.date(2026, 10, 27), days.get) == 2
