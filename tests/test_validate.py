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
from fixture_data import good_pair, stock, clone, hilo_of  # noqa: E402

TODAY = dt.date(2026, 10, 31)
NOW = dt.datetime(2026, 10, 31, 11, 0, tzinfo=V.KST)       # 관문 실행 시각 (fixture 의 publishedAt 09:30 + 1.5시간)
FIX = os.path.join(ROOT, "tests", "fixtures", "listing")
# 2026-10 의 실제 KOSPI 거래일 (네이버 일봉): 10/24·25 주말, 10/31(토) 없음
OCT = [dt.date(2026, 10, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30)]
SESSIONS = {"dates": OCT, "src": "시험"}


def check(cur, prev, final, mode="publish", between=lambda a, b: 1, sessions=SESSIONS, today=TODAY, now=NOW, hilo="same"):
    if hilo == "same":                 # 야후 52주 범위가 우리 값과 같은 정상 상황
        hilo = hilo_of(cur, V.MUST)
    return V.run_checks(cur, prev, final, today, mode=mode, count_between=between, sessions=sessions, now=now, hilo=hilo)


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
    rep = V.run_checks(cur, prev, final, TODAY, count_between=lambda a, b: 10, notes=notes, sessions=SESSIONS, now=NOW)
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


def test_previous_is_judged_by_its_data_json_only(tmp_path):
    # 10/17 발행본은 data.json 은 멀쩡하고 disc.json 에만 NaN 이 있어요. 비교는 data.json 만 쓰니 읽혀야 해요.
    _, prev, _ = good_pair()
    (tmp_path / "data.json").write_text(json.dumps(prev["data"], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "disc.json").write_text('{"insider":[{"cap":NaN}]}', encoding="utf-8")
    got = V.load_prev(str(tmp_path), None)
    assert set(got) == {"data"} and got["data"]["pxDate"] == "2026-10-29"
    (tmp_path / "data.json").write_text('{"stocks":[{"price":NaN}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="NaN"):
        V.load_prev(str(tmp_path), None)


def test_must_have_stocks_missing_from_corp_fails():
    # v17.4.1 의 워크플로 검사(corp.json 에 필수 종목)를 그대로 이어받아요
    cur, prev, final = good_pair()
    cur["corp"]["companies"] = [c for c in cur["corp"]["companies"] if c["t"] != "005380"]
    assert "기업분석 필수 종목" in failed_names(check(cur, prev, final))


def test_trading_day_count_failure_is_a_red_check_not_a_crash():
    cur, prev, final = good_pair()

    def boom(a, b):
        raise RuntimeError("network")
    assert "큰 가격 변동 비율" in failed_names(check(cur, prev, final, between=boom))


# ── 마지막 거래일이 빠진 채 하루 물러난 발행 (PR #4 리뷰 1번, 막는 문제) ──────────
def stale_by_one_day():
    """10/30(금) 목록 파일이 없거나 최종본이 아니어서 latest_final 이 10/29 로 물러난 상황.
    최종본·KOSPI·가격이 모두 10/29 끼리는 맞아서, 새 검사 전에는 그대로 통과했어요."""
    cur, closes = __import__("fixture_data").build(px_date="2026-10-29", us_date="2026-10-29")
    prev, _ = __import__("fixture_data").build(px_date="2026-10-28", us_date="2026-10-28", price_shift=-0.01)
    for s_, p_ in zip(cur["data"]["stocks"], prev["data"]["stocks"]):
        if s_.get("cls") == "kr":
            p_["price"] = round(s_["price"] * 0.99)
    final = {"date": dt.date(2026, 10, 29), "closes": closes, "how": "10/30 파일 없음"}
    return cur, prev, final


def test_missing_last_trading_day_fails_only_on_the_session_check():
    cur, prev, final = stale_by_one_day()
    rep = check(cur, prev, final)
    assert failed_names(rep) == {"pxDate 뒤 끝난 거래일 없음"}, rep.table()
    row = next(r for r in rep.rows if r[0] == "pxDate 뒤 끝난 거래일 없음")
    assert "2026-10-30" in str(row[1])


def test_same_data_passes_when_no_session_was_missed():
    # 같은 데이터라도 10/30 이 거래일이 아니었다면(예: 휴장) 통과해야 해요
    cur, prev, final = stale_by_one_day()
    holiday = {"dates": [d for d in OCT if d != dt.date(2026, 10, 30)], "src": "시험"}
    assert not check(cur, prev, final, sessions=holiday).failed


def test_todays_session_is_not_counted():
    # 금요일(10/30) 저녁 실행: 오늘 거래일은 아직 최종본이 없을 수 있어 세지 않아요. 목요일 가격이면 통과.
    cur, prev, final = stale_by_one_day()
    for f in cur.values():
        if "publishedAt" in f:
            f["publishedAt"] = "2026-10-30T20:00:00+09:00"
    rep = check(cur, prev, final, today=dt.date(2026, 10, 30), now=dt.datetime(2026, 10, 30, 21, 0, tzinfo=V.KST))
    assert "pxDate 뒤 끝난 거래일 없음" not in failed_names(rep), rep.table()


def test_kospi_bars_unavailable_fails():
    cur, prev, final = good_pair()
    assert "pxDate 뒤 끝난 거래일 없음" in failed_names(check(cur, prev, final, sessions=None))


def test_pxdate_that_is_not_a_trading_day_fails():
    cur, prev, final = good_pair()
    no_30 = {"dates": [d for d in OCT if d != dt.date(2026, 10, 30)], "src": "시험"}
    assert "pxDate 가 KOSPI 거래일" in failed_names(check(cur, prev, final, sessions=no_30))


def test_completed_sessions_after():
    d = dt.date
    assert V.completed_sessions_after(d(2026, 10, 29), d(2026, 10, 31), OCT) == [d(2026, 10, 30)]
    assert V.completed_sessions_after(d(2026, 10, 30), d(2026, 10, 31), OCT) == []
    assert V.completed_sessions_after(d(2026, 10, 29), d(2026, 10, 30), OCT) == []          # 오늘은 빼요
    assert V.completed_sessions_after(d(2026, 10, 23), d(2026, 10, 27), OCT) == [d(2026, 10, 26)]   # 주말은 거래일 아님


class _Resp:
    def __init__(self, text=None, js=None, status=200):
        self.text, self._js, self.status_code = text, js, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise V.requests.HTTPError(str(self.status_code))

    def json(self):
        return self._js


NAVER_XML = ('<?xml version="1.0" encoding="EUC-KR" ?><protocol><chartdata symbol="KOSPI">'
             + "".join(f'<item data="202610{d:02d}|1|2|0|1|9" />' for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 26, 27, 28, 29, 30))
             + "</chartdata></protocol>")


def yahoo_js(days):
    ts = [int(dt.datetime.combine(d, dt.time(9), V.KST).timestamp()) for d in days]
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{"close": [1.0] * len(ts)}]}}]}}


NO_SLEEP = {"sleep": lambda s: None}


def test_kospi_sessions_from_naver_when_yahoo_is_down(monkeypatch):
    monkeypatch.setattr(V.requests, "get", lambda url, **k: _Resp(text=NAVER_XML) if "naver" in url else _Resp(status=503))
    got = V.http_kospi_sessions(**NO_SLEEP)
    assert got["src"].startswith("네이버") and got["dates"] == OCT and "실패" in got["src"]


def test_kospi_sessions_fall_back_to_yahoo(monkeypatch):
    monkeypatch.setattr(V.requests, "get", lambda url, **k: _Resp(status=503) if "naver" in url else _Resp(js=yahoo_js(OCT)))
    got = V.http_kospi_sessions(**NO_SLEEP)
    assert got["src"].startswith("야후") and got["dates"] == OCT


def test_kospi_sessions_union_catches_a_lagging_source(monkeypatch):
    # 네이버가 10/29 에서 멈춰 있어도 야후에 10/30 이 있으면 10/30 은 거래일이에요
    lag = NAVER_XML.replace('<item data="20261030|1|2|0|1|9" />', "")
    monkeypatch.setattr(V.requests, "get", lambda url, **k: _Resp(text=lag) if "naver" in url else _Resp(js=yahoo_js(OCT)))
    got = V.http_kospi_sessions(**NO_SLEEP)
    assert dt.date(2026, 10, 30) in got["dates"] and "+" in got["src"]


def test_kospi_sessions_too_short_counts_as_failure(monkeypatch):
    short = yahoo_js(OCT[-3:])
    monkeypatch.setattr(V.requests, "get", lambda url, **k: _Resp(status=503) if "naver" in url else _Resp(js=short))
    with pytest.raises(RuntimeError, match="3일뿐"):
        V.http_kospi_sessions(**NO_SLEEP)


def test_kospi_sessions_both_down_raises_after_retries(monkeypatch):
    calls, waits = [], []
    monkeypatch.setattr(V.requests, "get", lambda url, **k: calls.append(url) or _Resp(status=503))
    with pytest.raises(RuntimeError):
        V.http_kospi_sessions(sleep=waits.append)
    assert len(calls) == 6 and waits == [1, 2, 1, 2]       # 각 출처 3번, 사이에 1·2초


# ── publishedAt (PR #4 리뷰 3번) ─────────────────────────
def test_published_at_missing_in_one_file_fails():
    cur, prev, final = good_pair()
    del cur["macro"]["publishedAt"]
    assert "publishedAt 네 파일 모두" in failed_names(check(cur, prev, final))


def test_published_at_not_kst_fails():
    cur, prev, final = good_pair()
    for f in cur.values():
        f["publishedAt"] = "2026-10-31T00:30:00+00:00"
    assert "publishedAt 한국 시간(+09:00)" in failed_names(check(cur, prev, final))


def test_published_at_differs_across_files_fails():
    cur, prev, final = good_pair()
    cur["disc"]["publishedAt"] = "2026-10-31T09:31:00+09:00"
    assert "publishedAt 네 파일이 같음" in failed_names(check(cur, prev, final))


def test_published_at_older_than_12_hours_fails():
    cur, prev, final = good_pair()
    late = dt.datetime(2026, 10, 31, 22, 0, tzinfo=V.KST)       # 09:30 발행 → 12.5시간 뒤 관문
    assert "publishedAt 12시간 이내" in failed_names(check(cur, prev, final, now=late))
    assert "publishedAt 12시간 이내" not in failed_names(check(cur, prev, final, now=NOW))


def test_published_at_in_the_future_fails():
    cur, prev, final = good_pair()
    early = dt.datetime(2026, 10, 31, 8, 0, tzinfo=V.KST)
    assert "publishedAt 12시간 이내" in failed_names(check(cur, prev, final, now=early))


def test_published_at_without_timezone_is_a_fail_row_not_a_crash():
    cur, prev, final = good_pair()
    for f in cur.values():
        f["publishedAt"] = "2026-10-31T09:30:00"
    rep = check(cur, prev, final)
    assert {"publishedAt 한국 시간(+09:00)", "publishedAt 12시간 이내"} <= failed_names(rep)


def test_live_mode_does_not_check_missed_sessions():
    # 사이트 점검은 아침 발행 전에 어제 거래일이 늘 비어 있어요 → v17.6 감시가 따로 봐요
    cur, _, final = stale_by_one_day()
    assert "pxDate 뒤 끝난 거래일 없음" not in failed_names(check(cur, None, final, mode="live", sessions=None))


def test_live_mode_skips_only_the_12_hour_rule():
    cur, _, final = good_pair()
    late = dt.datetime(2026, 11, 2, 9, 0, tzinfo=V.KST)
    rep = check(cur, None, final, mode="live", now=late)
    assert "publishedAt 12시간 이내" not in failed_names(rep)
    del cur["corp"]["publishedAt"]
    assert "publishedAt 네 파일 모두" in failed_names(check(cur, None, final, mode="live", now=late))


def test_kospi_sessions_report_disagreement_and_only_final_failures(monkeypatch):
    lag = NAVER_XML.replace('<item data="20261030|1|2|0|1|9" />', "")
    tries = {"n": 0}

    def get(url, **k):
        if "naver" in url:
            return _Resp(text=lag)
        tries["n"] += 1                       # 야후는 첫 시도 실패, 두 번째 성공
        return _Resp(status=503) if tries["n"] == 1 else _Resp(js=yahoo_js(OCT))
    monkeypatch.setattr(V.requests, "get", get)
    got = V.http_kospi_sessions(**NO_SLEEP)
    assert got["disagree"] == [dt.date(2026, 10, 30)]
    assert "실패" not in got["src"]           # 다시 시도해서 받았으면 실패로 적지 않아요


# ── v17.5.1 (v18.0 Part A + 추가 4–9): 새 규칙마다 한 군데씩 망가뜨리면 반드시 실패 ──
def fails_on(name, mutate, hilo="same"):
    cur, prev, final = good_pair()
    mutate(cur)
    rep = check(cur, prev, final, hilo=hilo)
    assert name in failed_names(rep), rep.table()
    return rep


def kr_of(cur):
    return [s for s in cur["data"]["stocks"] if s["cls"] == "kr"]


def test_nan_word_in_description_fails():
    # 2026-10-31 발행본: 867종목이 "nan · 주요제품: …" 로 시작했어요
    fails_on("글자에 nan·None·null·undefined 없음", lambda c: stock(c, "000660").update(dk="nan · 주요제품: 반도체 · KOSPI 상장"))


@pytest.mark.parametrize("word", ["None", "null", "undefined", "NaN"])
def test_other_bad_words_fail_anywhere(word):
    fails_on("글자에 nan·None·null·undefined 없음", lambda c: c["disc"]["insider"].append({"nm": f"홍길동 {word}"}))


def test_bad_word_is_whole_word_only():
    cur, prev, final = good_pair()
    stock(cur, "U0001")["de"] = "Financial services, annual nanotech review, Nonesuch Corp."
    rep = check(cur, prev, final)
    assert "글자에 nan·None·null·undefined 없음" not in failed_names(rep), rep.table()


def test_market_section_in_description_fails():
    # 2026-10-31: 1,470종목이 "우량기업부 · …" 로 시작했어요 (소속부를 업종으로 읽음)
    fails_on("국내 설명에 소속부 없음", lambda c: stock(c, "005930").update(dk="우량기업부 · 주요제품: 반도체 · KOSDAQ 상장"))


def test_products_copied_from_industry_fails():
    # 2026-10-31: 2,476종목 모두 '주요제품: <업종 이름>' (열이 하나씩 밀림)
    def shift(c):
        for s in kr_of(c):
            s["dk"] = "통신 및 방송 장비 제조업 · 주요제품: 통신 및 방송 장비 제조업 · KOSPI 상장"
    fails_on("국내 주요제품 ≠ 업종 이름", shift)


def test_must_have_without_d1_fails():
    fails_on("필수 종목 d1", lambda c: stock(c, "005930").pop("d1"))


def test_d1_coverage_drop_is_a_warning_only():
    # v18.0 추가 4: "The run fails only when must-have stocks lack d1" — 채움이 모자라면 경고
    cur, prev, final = good_pair()
    for s in kr_of(cur)[20::10]:
        s.pop("d1", None)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert any(r[0] == "국내 d1 채움" and r[3] == "WARN" for r in rep.rows)


def test_d1_beyond_price_limit_fails():
    fails_on("국내 d1 범위 (±30%)", lambda c: kr_of(c)[50].update(d1=35.0))


def test_us_must_have_without_d1_fails():
    fails_on("미국 필수 종목 d1", lambda c: stock(c, "AAPL").pop("d1"))


def test_must_have_without_val20_fails():
    fails_on("필수 종목 val20", lambda c: stock(c, "105560").pop("val20"))


def test_val20_coverage_drop_fails():
    def drop(c):
        for s in kr_of(c)[::10]:
            s.pop("val20", None)
    fails_on("국내 val20 채움", drop)


def test_missing_etf_flag_fails():
    fails_on("etf 표시 (모든 종목)", lambda c: stock(c, "U0001").pop("etf"))


@pytest.mark.parametrize("t, wrong", [("BRK-B", True), ("SPY", False), ("069500", False), ("005930", True), ("B3", False)])
def test_wrong_etf_flag_fails(t, wrong):
    fails_on("etf 표시가 맞음", lambda c: stock(c, t).update(etf=wrong))


def test_negative_dividend_fails():
    fails_on("국내 주당 배당금 ≥ 0", lambda c: kr_of(c)[40].update(dps=-100.0))


def test_samsung_dividend_zero_fails():
    fails_on("005930 주당 배당금", lambda c: stock(c, "005930").update(dps=0.0))


def test_zero_dividend_is_kept_and_passes():
    cur, prev, final = good_pair()
    assert sum(1 for s in kr_of(cur) if s.get("dps") == 0) > 100
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()


def test_annual_numbers_without_report_year_fail():
    fails_on("연간 수치에 사업보고서 연도(fy)", lambda c: c["corp"]["companies"][30].pop("fy"))


def test_report_year_out_of_range_fails():
    fails_on("사업보고서 연도 범위", lambda c: c["corp"]["companies"][30].update(fy=2021))


def test_must_have_without_report_year_fails():
    fails_on("필수 종목 fy", lambda c: next(x for x in c["corp"]["companies"] if x["t"] == "005380").pop("fy"))


def test_missing_index_history_fails():
    fails_on("지수 이력 (KOSPI·S&P500 3년)", lambda c: c["macro"].pop("idxHist"))


def test_short_index_history_fails():
    fails_on("지수 이력 (KOSPI·S&P500 3년)", lambda c: c["macro"]["idxHist"]["SP500"].update(rows=c["macro"]["idxHist"]["SP500"]["rows"][-300:]))


def test_index_history_ending_before_pxdate_fails():
    def stale(c):
        h = c["macro"]["idxHist"]["KOSPI"]
        h["rows"] = h["rows"][:-1]
        h["asOf"] = h["rows"][-1][0]
    fails_on("지수 이력 (KOSPI·S&P500 3년)", stale)


def test_index_history_out_of_order_fails():
    def swap(c):
        r = c["macro"]["idxHist"]["KOSPI"]["rows"]
        r[100], r[101] = r[101], r[100]
    fails_on("지수 이력 (KOSPI·S&P500 3년)", swap)


def test_52_week_high_far_off_from_yahoo_fails():
    cur, prev, final = good_pair()
    hl = hilo_of(cur, V.MUST)
    hl["005380"]["hi"] *= 1.05                                  # 야후 최고가가 5% 달라요
    rep = check(cur, prev, final, hilo=hl)
    assert "필수 종목 52주 최고·최저 (야후)" in failed_names(rep), rep.table()


def test_52_week_high_slightly_off_is_a_warning():
    cur, prev, final = good_pair()
    hl = hilo_of(cur, V.MUST)
    hl["005380"]["lo"] *= 1.02                                  # 2%: 오래된 네이버 봉일 수 있어 경고만
    rep = check(cur, prev, final, hilo=hl)
    assert not rep.failed, rep.table()
    assert any(r[0] == "필수 종목 52주 최고·최저 (야후)" and r[3] == "WARN" for r in rep.rows)


def test_two_day_d1_is_caught_by_yahoo():
    # 리뷰: 수요일 목록 파일이 없으면 금요일 실행이 목요일-화요일 변화를 d1 로 낼 뻔했어요
    cur, prev, final = good_pair()
    hl = hilo_of(cur, V.MUST)
    hl["005930"]["d1"] = stock(cur, "005930")["d1"] + 2.5
    rep = check(cur, prev, final, hilo=hl)
    assert "필수 종목 d1 (야후)" in failed_names(rep), rep.table()


@pytest.mark.parametrize("text", ["시가총액 nan억원", "None년 사업보고서 기준", "주요제품: undefined"])
def test_bad_word_next_to_korean_fails(text):
    fails_on("글자에 nan·None·null·undefined 없음", lambda c: stock(c, "000660").update(dk=text))


def test_dividend_and_yield_disagreeing_fails():
    def odd(c):
        for s in kr_of(c)[100:160]:
            s.update(dps=0.0, dy=2.5)
    fails_on("주당 배당금·배당수익률 맞음", odd)


def test_internal_field_leak_fails():
    fails_on("임시 칸(_…) 없음", lambda c: stock(c, "U0001").update(_yind="Semiconductors"))


def test_missing_us_must_have_fails():
    fails_on("미국 필수 종목 d1", lambda c: c["data"]["stocks"].remove(stock(c, "NVDA")))


def test_52_week_check_unavailable_is_a_warning_not_a_failure():
    cur, prev, final = good_pair()
    rep = check(cur, prev, final, hilo=None)
    assert not rep.failed, rep.table()
    assert any(r[0] == "필수 종목 52주 최고·최저 (야후)" and r[3] == "WARN" for r in rep.rows)


def test_http_hilo_uses_closes_up_to_pxdate(monkeypatch):
    days = [dt.date(2025, 1, 1) + dt.timedelta(days=i) for i in range(400)]
    rows = [(d, 100.0 + i) for i, d in enumerate(days)]
    monkeypatch.setattr(V, "_yahoo_closes", lambda sym: rows)
    px = days[299]
    got = V.http_hilo(["005930"], px, sleep=lambda s: None)["005930"]
    assert (got["hi"], got["lo"]) == (100.0 + 299, 100.0 + 299 - 251)     # 마지막 252거래일, pxDate 뒤는 빼요
    assert abs(got["d1"] - (399 / 398 - 1) * 100) < 1e-9


def test_http_hilo_skips_a_lagging_yahoo(monkeypatch):
    days = [dt.date(2025, 1, 1) + dt.timedelta(days=i) for i in range(300)]
    monkeypatch.setattr(V, "_yahoo_closes", lambda sym: [(d, 100.0) for d in days])
    assert V.http_hilo(["005930"], days[-1] + dt.timedelta(days=1), sleep=lambda s: None) == {}


@pytest.mark.parametrize("t, wrong", [("088980", False), ("241520", True)])
def test_korean_listed_fund_flags(t, wrong):
    # 맥쿼리인프라는 펀드(etf=참), DSC인베스트먼트는 같은 업종이지만 회사(etf=거짓)
    def add(c):
        c["data"]["stocks"].append({"t": t, "nk": t, "ne": t, "cls": "kr", "price": 10000.0, "cap": 1.0, "etf": wrong})
    fails_on("etf 표시가 맞음", add)


# ── v17.5.1 PR 2: 업종 그룹 ──
@pytest.mark.parametrize("t, g", [("005930", "telecom_eq"), ("105560", "holding"), ("034730", "finance"), ("000270", None)])
def test_must_have_in_wrong_industry_group_fails(t, g):
    def wrong(c):
        s = stock(c, t)
        if g:
            s.update(ind=g, indName="이름")
        else:
            s.pop("ind")
            s.pop("indName")
    fails_on("업종 그룹 필수 종목", wrong)


def test_many_liquid_stocks_without_group_fail():
    def drop(c):
        for s in kr_of(c)[20:80]:
            s.pop("ind")
            s.pop("indName")
    fails_on("업종 그룹 없는 국내 종목 (거래 활발)", drop)


def test_tiny_industry_group_fails():
    fails_on("업종 그룹 인원 (시장마다)", lambda c: kr_of(c)[300].update(ind="ship", indName="조선"))


def test_two_names_for_one_group_fails():
    fails_on("업종 그룹 이름·형식", lambda c: kr_of(c)[301].update(indName="반도체·장비"))


def test_etf_with_industry_group_fails():
    fails_on("업종 그룹 이름·형식", lambda c: stock(c, "SPY").update(ind="semi", indName="반도체"))
