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


# ── v17.5.4: 최종본 = 그날 KRX 마감 + 30분 (특별 거래시간 표, fetch_data.py 와 따로 읽어요) ──
CSAT, CSAT_PREV, CSAT_NEXT = dt.date(2026, 11, 19), dt.date(2026, 11, 18), dt.date(2026, 11, 20)
NOV = [dt.date(2026, 11, d) for d in (2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20)]
SPECIAL_HEAD = "date,open,close,kind,reason,source\n"


def csat_latest(hm, notes=None):
    texts = {CSAT: text_of("2026-10-29_1958"), CSAT_PREV: text_of("2026-10-28_1921")}
    commits = {CSAT: hm, CSAT_PREV: "1921"}
    return V.latest_final(CSAT_NEXT, texts.get, lambda d: kst(d, commits[d]), notes=notes)


def test_latest_final_normal_day_cut_is_still_1600():
    d29, d28 = dt.date(2026, 10, 29), dt.date(2026, 10, 28)
    texts = {d29: text_of("2026-10-29_1958"), d28: text_of("2026-10-28_1921")}
    assert V.final_cut(d29, V.load_special_sessions()) == kst(d29, "1600")
    for hm, want in (("1559", d28), ("1600", d29)):
        commits = {d29: hm, d28: "1921"}
        d, _, how = V.latest_final(dt.date(2026, 10, 30), texts.get, lambda d: kst(d, commits[d]))
        assert d == want and "특별" not in how, hm


@pytest.mark.parametrize("hm", ["1610", "1659"])
def test_latest_final_csat_day_before_1700_is_not_final(hm):
    notes = []
    d, _, _ = csat_latest(hm, notes)
    assert d == CSAT_PREV
    assert any(n.startswith("2026-11-19 최종본 아님") and "특별 거래시간(수능): 마감 16:30 → 최종본은 17:00 이후 커밋만" in n
               for n in notes), notes


def test_latest_final_csat_day_at_1700_is_final():
    d, closes, how = csat_latest("1700")
    assert d == CSAT and closes["005930"] == 232000
    assert how == "11-19 17:00 KST 커밋 · 2026-11-19 특별 거래시간(수능): 마감 16:30 → 최종본은 17:00 이후 커밋만"


def test_csat_day_not_final_is_caught_as_a_missed_session():
    # 11/19 파일이 16:10 커밋뿐이면 최종본은 11/18 → 발행본도 11/18 가격이에요. 11/19 는 끝난 거래일이라 관문이 막아요.
    d, _, how = csat_latest("1610")
    assert d == CSAT_PREV
    fd = __import__("fixture_data")
    cur, closes = fd.build(px_date="2026-11-18", us_date="2026-11-18")
    prev, _ = fd.build(px_date="2026-11-17", us_date="2026-11-17", price_shift=-0.01)
    for s_, p_ in zip(cur["data"]["stocks"], prev["data"]["stocks"]):
        if s_.get("cls") == "kr":
            p_["price"] = round(s_["price"] * 0.99)
    for f in cur.values():
        if "publishedAt" in f:
            f["publishedAt"] = "2026-11-20T09:30:00+09:00"
    final = {"date": d, "closes": closes, "how": how}
    rep = check(cur, prev, final, sessions={"dates": NOV, "src": "시험"}, today=CSAT_NEXT,
                now=dt.datetime(2026, 11, 20, 11, 0, tzinfo=V.KST))
    assert failed_names(rep) == {"pxDate 뒤 끝난 거래일 없음"}, rep.table()
    row = next(r for r in rep.rows if r[0] == "pxDate 뒤 끝난 거래일 없음")
    assert "2026-11-19" in row[1]


def test_special_session_table_is_read_the_same_way_as_the_pipeline():
    sp = V.load_special_sessions()
    assert sp[CSAT] == (dt.time(10), dt.time(16, 30), "수능")
    assert sp[dt.date(2026, 1, 2)] == (dt.time(10), dt.time(15, 30), "연초 개장")
    assert V.final_cut(CSAT, sp) == kst(CSAT, "1700") and V.final_cut(dt.date(2026, 1, 2), sp) == kst(dt.date(2026, 1, 2), "1600")


@pytest.mark.parametrize("row,why", [
    ("2026-11-19,10:00,16:30,수능,이유", "칸 수"),
    ("2026-11-19,10:00,16:30,수능,이유,출처,더", "칸 수"),
    ("2026/11/19,10:00,16:30,수능,이유,출처", "YYYY-MM-DD"),
    ("2026-02-30,10:00,16:30,수능,이유,출처", "읽을 수 없어요"),
    ("2026-11-19,10시,16:30,수능,이유,출처", "HH:MM"),
    ("2026-11-19,10:00,25:00,수능,이유,출처", "읽을 수 없어요"),
    ("2026-11-19,16:30,10:00,수능,이유,출처", "앞이어야"),
    ("2026-11-19,10:00,14:30,수능,이유,출처", "보통 마감 15:30 보다 일러요"),     # 마감을 앞당기면 규칙이 느슨해져요
    ("2026-11-21,10:00,16:30,수능,이유,출처", "주말"),
    ("2026-01-02,10:00,15:30,연초 개장,이유,출처", "두 번"),
    ("2026-11-19,10:00,16:30,시험,이유,출처", "kind"),
    ("2026-11-19,10:00,16:30,수능,이유,", "출처 없는 줄"),
])
def test_broken_special_session_row_stops_loudly(tmp_path, row, why):
    p = tmp_path / "s.csv"
    p.write_text(SPECIAL_HEAD + "2026-01-02,10:00,15:30,연초 개장,이유,출처\n" + row + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match=f"s.csv 3번째 줄: .*{why}"):
        V.load_special_sessions(str(p))


def test_unreadable_special_session_table_is_a_red_check(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("krx_special_sessions.csv 3번째 줄: 주말이에요")
    monkeypatch.setattr(V, "load_special_sessions", boom)
    cur, prev, final = good_pair()
    assert "KRX 특별 거래시간 표" in failed_names(check(cur, prev, final))


def test_csat_missing_from_the_table_is_a_warning_from_september_first():
    sp = V.load_special_sessions()
    assert not V.csat_missing(dt.date(2026, 10, 31), sp)                  # 2026-11-19 줄이 있어요
    assert not V.csat_missing(dt.date(2027, 8, 31), sp)                   # 9월 전에는 안 봐요
    assert V.csat_missing(dt.date(2027, 9, 1), sp)                        # 2027 수능일 줄이 아직 없어요
    assert not V.csat_missing(dt.date(2027, 9, 1), {**sp, dt.date(2027, 11, 18): (dt.time(10), dt.time(16, 30), "수능")})
    cur, prev, final = good_pair()
    row = next(r for r in check(cur, prev, final).rows if r[0] == "올해 수능일 특별 거래시간 (표)")
    assert row[3] == "PASS" and "2026-11-19 10:00~16:30" in row[1]
    no_csat = {d: v for d, v in sp.items() if v[2] != "수능"}
    rep = V.run_checks(cur, prev, final, TODAY, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                       hilo=hilo_of(cur, V.MUST), special=no_csat)
    row = next(r for r in rep.rows if r[0] == "올해 수능일 특별 거래시간 (표)")
    assert row[3] == "WARN" and row[1] == "올해 수능일 특별 거래시간이 표에 없어요"
    assert not rep.failed, rep.table()                                    # 경고만 — 평소 발행을 막지 않아요


def test_csat_missing_from_the_table_fails_from_november_first():
    """Jack, 2026-11-04: 9월 1일부터 경고, 11월 1일부터도 없으면 발행을 막아요."""
    sp = V.load_special_sessions()
    no_csat = {d: v for d, v in sp.items() if v[2] != "수능"}
    assert not V.csat_blocks(dt.date(2027, 10, 31), no_csat) and V.csat_missing(dt.date(2027, 10, 31), no_csat)
    assert V.csat_blocks(dt.date(2027, 11, 1), no_csat) and V.csat_blocks(dt.date(2027, 12, 31), no_csat)
    assert not V.csat_blocks(dt.date(2027, 11, 1), {**no_csat, dt.date(2027, 11, 18): (dt.time(10), dt.time(16, 30), "수능")})
    assert not V.csat_blocks(dt.date(2026, 11, 4), sp)                    # 올해 줄(2026-11-19)이 있어요
    cur, prev, final = good_pair()
    for today, want in ((dt.date(2026, 10, 31), "WARN"), (dt.date(2026, 11, 1), "FAIL")):
        rep = V.run_checks(cur, prev, final, today, count_between=lambda a, b: 1, sessions=SESSIONS, now=NOW,
                           hilo=hilo_of(cur, V.MUST), special=no_csat)
        row = next(r for r in rep.rows if r[0] == "올해 수능일 특별 거래시간 (표)")
        assert row[3] == want and row[1] == "올해 수능일 특별 거래시간이 표에 없어요", (today, row)


def test_gate_warnings_and_failures_become_github_annotations():
    """관문 경고·실패는 GitHub 알림(::warning:: · ::error::)으로도 남아서 매일 아침 점검이 읽어요 (Jack, 2026-11-04)."""
    rep = V.Report()
    rep.add("좋은 줄", True, "1", "1")
    rep.add("경고 줄", True, "93.0%", "≥ 92% (2점 안쪽이면 경고)", warn=True)
    rep.add("실패 줄", False, "50%\r\n둘째 줄", "≥ 99%")
    lines = V.annotations(rep)
    assert lines == ["::error title=발행 관문 실패::실패 줄: 50%25%0D%0A둘째 줄 (기준 ≥ 99%25)",
                     "::warning title=발행 관문 경고::경고 줄: 93.0%25 (기준 ≥ 92%25 (2점 안쪽이면 경고))"], lines
    assert V.annotations(V.Report()) == []
    many = V.Report()
    for i in range(13):
        many.add(f"경고 {i}", True, "x", "y", warn=True)
    w = V.annotations(many)
    assert len(w) == V.ANNOTATE_MAX and w[-1].endswith("외 4개 더 — 실행 요약의 표를 보세요"), w[-2:]
    assert "경고 0:" in w[0] and "경고 8:" in w[8], w[:2]                 # 앞에서부터 9개를 보여 줘요


def test_gate_stopping_before_the_table_still_leaves_an_error_annotation(monkeypatch, capsys, tmp_path):
    """파일을 못 읽거나 관문이 오류로 멈춰도 이유가 알림으로 남아요 (리뷰 2026-11-04). 오류는 삼키지 않아요."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert V.main(["--dir", str(tmp_path), "--bootstrap", "--today", "2026-10-31"]) == 1      # 빈 폴더: data.json 없음
    out = capsys.readouterr().out
    assert "!! FAIL  파일 읽기:" in out and "::error title=발행 관문 실패::파일 읽기: " in out, out[-300:]
    cur, _, _ = good_pair()
    real_load_dir = V.load_dir
    monkeypatch.setattr(V, "load_dir", lambda d: cur)
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (None, None, "시험"))
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: {"dates": [], "src": "시험"})
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: {})

    def crash(*a, **k):
        raise KeyError("stocks")
    monkeypatch.setattr(V, "run_checks", crash)
    with pytest.raises(KeyError):
        V.main(["--dir", "unused", "--bootstrap", "--today", "2026-10-31"])
    assert "::error title=발행 관문 실패::관문이 오류로 멈췄어요: KeyError: 'stocks'" in capsys.readouterr().out
    monkeypatch.delenv("GITHUB_ACTIONS")
    monkeypatch.setattr(V, "load_dir", real_load_dir)
    assert V.main(["--dir", str(tmp_path), "--bootstrap", "--today", "2026-10-31"]) == 1
    assert "::error" not in capsys.readouterr().out                      # GitHub 밖에서는 알림 줄을 쓰지 않아요


def test_gate_prints_annotations_only_inside_github_actions(monkeypatch, capsys):
    rep = V.Report()
    rep.add("경고 줄", True, "x", "y", warn=True)
    cur, _, _ = good_pair()
    monkeypatch.setattr(V, "load_dir", lambda d: cur)                    # 네트워크 없이: 파일·최종본·달력·야후는 가짜
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (None, None, "시험"))
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: {"dates": [], "src": "시험"})
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: {})
    monkeypatch.setattr(V, "run_checks", lambda *a, **k: rep)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    for env, seen in (("true", True), (None, False)):
        if env:
            monkeypatch.setenv("GITHUB_ACTIONS", env)
        else:
            monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        assert V.main(["--dir", "unused", "--bootstrap", "--today", "2026-10-31"]) == 0   # 경고만이면 통과
        out = capsys.readouterr().out
        assert ("::warning title=발행 관문 경고::경고 줄: x (기준 y)" in out) is seen, out[-400:]
        assert "!! 경고  경고 줄: x (기준 y)" in out


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


# ── 미국 d1 채움 (Jack, 2026-11-07): 98% 아래면 실패, 빠진 종목은 값 칸 · 로그 · 실행 요약에 이름으로 ──
US_D1 = "미국 d1 채움 (미국 기준일 봉)"


def us_of(c):
    return [s for s in c["data"]["stocks"] if s.get("cls") == "us" and not s.get("fund")]


def row_of(rep, name):
    return next(r for r in rep.rows if r[0] == name)


def drop_us_d1(cur, n):
    """야후가 미국 기준일 봉을 빠뜨린 종목처럼: d1 이 없고 자기 가격 날짜(pxd)는 그 전 거래일 (파이프라인이 그렇게 써요 · v19.1c)."""
    gone = [s for s in us_of(cur) if s["t"] not in ("AAPL", "MSFT", "NVDA")][:n]
    for s in gone:
        s.pop("d1")
        s["pxd"] = "2026-10-29"
    return [s["t"] for s in gone]


def test_us_d1_coverage_below_98_percent_fails_and_names_the_stocks():
    cur, prev, final = good_pair()
    assert len(us_of(cur)) == 600
    gone = drop_us_d1(cur, 13)                                           # 587 / 600 = 97.8%
    rep = check(cur, prev, final)
    r = row_of(rep, US_D1)
    assert r[3] == "FAIL" and r[1].startswith("97.8% (587 / 600) · 빠짐: " + ", ".join(gone[:10]) + " 외 3개"), r
    assert "2026-10-30" in r[2]                                          # 기준 칸에 미국 기준일
    assert rep.details == [("미국 d1 없는 종목 (마지막 봉이 미국 기준일 2026-10-30 이 아님)", gone)]   # 13개 전부
    assert [x[0] for x in rep.failed] == [US_D1], rep.table()            # 필수 세 종목은 d1 이 있어서 그 줄은 통과


def test_us_d1_coverage_at_98_percent_passes_and_still_names_the_stocks():
    cur, prev, final = good_pair()
    gone = drop_us_d1(cur, 12)                                           # 588 / 600 = 98.0% — 기준선은 통과
    rep = check(cur, prev, final)
    r = row_of(rep, US_D1)
    assert r[3] == "WARN" and r[1] == "98.0% (588 / 600) · 빠짐: " + ", ".join(gone[:10]) + " 외 2개", r   # v19.1c: 빠지면 경고
    assert rep.details[0][1] == gone and not rep.failed, rep.table()
    cur, prev, final = good_pair()                                       # 다 있으면 목록도 없어요
    rep = check(cur, prev, final)
    assert row_of(rep, US_D1)[1:] == ("100.0% (600 / 600)", "≥ 98% (미국 기준일 2026-10-30 봉이 있는 종목 · 하나라도 빠지면 경고)", "PASS")
    assert rep.details == []


def test_us_d1_of_zero_counts_as_present_and_the_shown_share_never_rounds_up_to_the_line():
    cur, prev, final = good_pair()
    for s in us_of(cur)[3:40]:
        s["d1"] = 0.0                                                    # 그대로인 날도 '있음'
    r = row_of(check(cur, prev, final), US_D1)
    assert r[1] == "100.0% (600 / 600)" and r[3] == "PASS", r
    cur, prev, final = good_pair()                                       # 781 중 16 빠짐 = 97.95% → '97.9%' 로 보이고 실패
    us = us_of(cur)
    cur["data"]["stocks"] += [{**clone(us[10]), "t": f"X{i:03d}"} for i in range(181)]
    gone = drop_us_d1(cur, 16)
    assert len(us_of(cur)) == 781
    r = row_of(check(cur, prev, final), US_D1)
    assert r[3] == "FAIL" and r[1].startswith("97.9% (765 / 781)"), r


def test_us_d1_row_passes_after_a_us_holiday_and_a_half_day_and_fails_on_a_yahoo_gap():
    """Jack 2026-11-07 (a): 파이프라인과 같은 함수로 d1 을 만들어 관문에 넣어요. 미국 휴장일 다음 아침과 조기 폐장일 다음
    아침에는 모든 종목에 기준일 봉이 있어서 통과하고, 야후가 기준일 봉을 일부 종목에서 빠뜨린 날은 그 종목들 이름으로 실패해요."""
    import pandas as pd
    import fetch_data as F
    idx = pd.to_datetime(["2026-11-20", "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-27"])   # 11-26 추수감사절 휴장
    spx = pd.Series([6800.0, 6810.0, 6790.0, 6820.0, 6850.0], index=idx)
    utc = dt.timezone.utc
    for now, gap in ((dt.datetime(2026, 11, 26, 22, 0, tzinfo=utc), 0),    # 11-27 07:00 KST (휴장일 다음 아침)
                     (dt.datetime(2026, 11, 27, 22, 0, tzinfo=utc), 0),    # 11-28 07:00 KST (조기 폐장일 다음 아침)
                     (dt.datetime(2026, 11, 27, 22, 0, tzinfo=utc), 15)):  # 같은 아침, 야후가 15종목의 11-27 봉을 빠뜨림
        cur, prev, final = good_pair()
        d = F.us_data_date(spx, F.us_last_complete_day(now))
        missing = []
        for k, s in enumerate(us_of(cur)):
            px = pd.Series([100.0 + k, 101.0 + k, 99.0 + k, 102.0 + k, 103.0 + k], index=idx)
            if k >= 3 and len(missing) < gap:                            # 필수 세 종목(앞의 셋)은 그대로
                px = px.iloc[:-1]
                missing.append(s["t"])
            s["d1"] = F.us_d1(F.cut_at(px, d), d)
        r = row_of(check(cur, prev, final), US_D1)
        if not gap:
            assert r[3] == "PASS" and r[1] == "100.0% (600 / 600)", (now, r)
        else:
            assert r[3] == "FAIL" and r[1].startswith("97.5% (585 / 600) · 빠짐: " + ", ".join(missing[:10])), r


# ── v19.1c (Jack, 2026-11-07): 미국 종목의 자기 가격 날짜 · 1~15종목 경고 · 다음 발행 예정 · 휴장일 표 ──
NEXT = "다음 발행 예정 (nextPub · staleAfter)"
PXD = "미국 자기 가격 날짜 (pxd)"
HOL = "휴장일 표 (data/market_holidays.csv)"


def test_good_data_has_its_next_publish_date_and_no_stale_us_price():
    cur, prev, final = good_pair()
    assert (cur["data"]["nextPub"], cur["data"]["staleAfter"]) == ("2026-11-03", "2026-11-03T16:47:00+09:00")  # 금 → 화
    rep = check(cur, prev, final)
    assert row_of(rep, NEXT)[3] == "PASS" and row_of(rep, PXD)[1:] == (
        "없음 (모두 미국 기준일 종가)", "d1 이 없는 미국 종목은 pxd < 2026-10-30 · d1 이 있으면 pxd 없음", "PASS")
    assert row_of(rep, HOL)[3] == "PASS", row_of(rep, HOL)                     # 지난 90일 일봉과 표가 맞아요


def test_one_us_stock_without_todays_bar_warns_with_its_own_date():
    cur, prev, final = good_pair()
    gone = drop_us_d1(cur, 1)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert row_of(rep, US_D1)[3] == "WARN" and row_of(rep, PXD)[1] == f"1종목: {gone[0]}(2026-10-29)"
    notes = V.annotations(rep)
    assert any(n.startswith("::warning title=발행 관문 경고::미국 d1 채움 (미국 기준일 봉): 99.8%25 (599 / 600) · 빠짐: " + gone[0])
               for n in notes), notes                                        # 아침 점검이 읽는 알림


@pytest.mark.parametrize("mutate, said", [
    (lambda s: s.pop("pxd"), "d1 없음 · pxd None"),                           # 날짜 없이 옛 가격 → 앱이 오늘 날짜를 보여요
    (lambda s: s.update(pxd="2026-10-30"), "d1 없음 · pxd '2026-10-30'"),     # 기준일과 같은 날짜는 말이 안 돼요
    (lambda s: s.update(pxd="10/29"), "d1 없음 · pxd '10/29'"),
    (lambda s: s.update(d1=0.4), "d1 있는데 pxd '2026-10-29'"),
])
def test_stale_us_price_without_a_correct_own_date_fails(mutate, said):
    cur, prev, final = good_pair()
    gone = drop_us_d1(cur, 1)
    mutate(stock(cur, gone[0]))
    rep = check(cur, prev, final)
    r = row_of(rep, PXD)
    assert r[3] == "FAIL" and r[1] == f"{gone[0]}: {said}", r


@pytest.mark.parametrize("field, value, said", [
    ("nextPub", "2026-11-02", "nextPub 2026-11-02 ≠ 표로 계산한 2026-11-03"),
    ("staleAfter", "2026-11-03T18:00:00+09:00", "staleAfter 2026-11-03T18:00:00+09:00 ≠ 2026-11-03T16:47:00+09:00"),
    ("staleAfter", "2026-11-03T07:47:00+00:00", "staleAfter 2026-11-03T07:47:00+00:00 ≠"),   # 같은 순간이라도 한국 시간으로
    ("nextPub", "11월 3일", "날짜를 읽을 수 없어요"),
])
def test_wrong_next_publish_date_fails(field, value, said):
    cur, prev, final = good_pair()
    cur["data"][field] = value
    r = row_of(check(cur, prev, final), NEXT)
    assert r[3] == "FAIL" and said in r[1], r


def test_missing_next_publish_fails_a_publish_but_only_warns_on_the_live_site():
    cur, prev, final = good_pair()
    for k in ("nextPub", "staleAfter"):
        cur["data"].pop(k)
    rep = check(cur, prev, final)
    assert row_of(rep, NEXT)[3] == "FAIL" and row_of(rep, PXD)[3] == "SKIP"
    rep = check(cur, prev, final, mode="live")
    assert row_of(rep, NEXT)[3] == "WARN"                                    # 이 버전의 첫 발행 전 사이트 파일


def test_holiday_table_that_disagrees_with_the_index_bars_warns(monkeypatch):
    cur, prev, final = good_pair()
    rows = cur["macro"]["idxHist"]["KOSPI"]["rows"]
    rows[:] = [r for r in rows if r[0] != "2026-10-21"]                     # 표에 없는 날 봉이 없음 (표가 휴장일을 놓친 것)
    rows.append(["2026-10-09", 2500.0])                                      # 한글날(표의 휴장일)에 봉이 있음
    rows.sort()
    r = row_of(check(cur, prev, final), HOL)
    assert r[3] == "WARN" and "KR 2026-10-09 표엔 휴장·봉 있음" in r[1] and "KR 2026-10-21 봉 없음·표에 없음" in r[1], r
    monkeypatch.setattr(V, "HOL_COVER_WARN_DAYS", 500)                       # 표가 앞으로 500일을 덮지 못함 → 경고
    cur, prev, final = good_pair()
    r = row_of(check(cur, prev, final), HOL)
    assert r[3] == "WARN" and "다음 해 줄을 넣어 주세요" in r[1], r


def test_next_publish_date_already_past_warns_on_a_publish_but_not_on_the_live_site():
    """제때 발행이면 예정일은 늘 내일 이후 — 오늘 이전이면 표에 없는 임시공휴일이거나 날짜가 하루 늦은 것 (아침 점검이 읽어요)."""
    cur, prev, final = good_pair()
    rep = check(cur, prev, final, today=dt.date(2026, 11, 3))               # 예정일(11-03) 당일에 발행
    r = row_of(rep, NEXT)
    assert r[3] == "WARN" and "예정일이 오늘(2026-11-03) 이전이에요" in r[1], r
    assert row_of(check(cur, prev, final), NEXT)[3] == "PASS"               # 10-31 발행: 예정일은 뒤


def test_live_site_file_made_before_a_table_change_only_warns():
    cur, prev, final = good_pair()
    cur["data"]["nextPub"], cur["data"]["staleAfter"] = "2026-11-04", "2026-11-04T16:47:00+09:00"   # 옛 표로 계산된 것처럼
    assert row_of(check(cur, prev, final), NEXT)[3] == "FAIL"               # 발행 관문은 막고
    r = row_of(check(cur, prev, final, mode="live"), NEXT)
    assert r[3] == "WARN" and "사이트 점검: 발행 뒤 표가 바뀐 것" in r[1], r   # 사이트 점검(배포·감시)은 경고만
    cur["data"]["nextPub"] = "11월 4일"                                    # 읽을 수 없는 값은 사이트 점검도 실패
    assert row_of(check(cur, prev, final, mode="live"), NEXT)[3] == "FAIL"


def test_unreadable_holiday_table_fails(monkeypatch, tmp_path):
    p = tmp_path / "h.csv"
    p.write_text("date,market,name,source\n2026-11-07,KR,토요일,x\n", encoding="utf-8")
    monkeypatch.setattr(V, "HOLIDAYS_CSV", str(p))
    monkeypatch.setattr(V.load_holidays, "__defaults__", (str(p),))
    cur, prev, final = good_pair()
    rep = check(cur, prev, final)
    assert row_of(rep, HOL)[3] == "FAIL" and "주말" in row_of(rep, HOL)[1], rep.table()


def test_us_d1_missing_list_goes_to_the_log_and_the_run_summary(monkeypatch, capsys, tmp_path):
    """Jack 2026-11-07 (c): 관문이 막으면 빠진 미국 종목 이름이 로그와 실행 요약(GITHUB_STEP_SUMMARY)에 전부 남아요."""
    cur, _, _ = good_pair()
    gone = drop_us_d1(cur, 25)
    monkeypatch.setattr(V, "load_dir", lambda d: cur)                    # 네트워크 없이 (위 알림 시험과 같은 가짜들)
    monkeypatch.setattr(V, "latest_final", lambda *a, **k: (None, None, "시험"))
    monkeypatch.setattr(V, "http_kospi_sessions", lambda: {"dates": [], "src": "시험"})
    monkeypatch.setattr(V, "http_hilo", lambda *a, **k: {})
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    summ = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summ))
    assert V.main(["--dir", "unused", "--bootstrap", "--today", "2026-10-31"]) == 1
    out = capsys.readouterr().out
    title = "미국 d1 없는 종목 (마지막 봉이 미국 기준일 2026-10-30 이 아님)"
    assert f"!! {title} (25): " + ", ".join(gone) in out                  # 로그: 25개 전부
    assert f"!! FAIL  {US_D1}: 95.8% (575 / 600) · 빠짐: " + ", ".join(gone[:10]) + " 외 15개" in out
    assert f"::error title=발행 관문 실패::{US_D1}: 95.8%" in out          # 실행 화면의 알림
    text = summ.read_text(encoding="utf-8")
    row = next(x for x in text.splitlines() if x.startswith(f"| {US_D1} |"))
    assert row.startswith(f"| {US_D1} | 95.8% (575 / 600) · 빠짐: ") and row.endswith("| **FAIL** |"), row
    assert f"**{title}** (25): " + ", ".join(gone) in text               # 실행 요약: 25개 전부


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


def test_holding_company_in_financial_group_fails():
    def add(c):
        c["data"]["stocks"].append({"t": "004800", "nk": "효성", "ne": "효성", "cls": "kr", "price": 1.0, "cap": 1.0,
                                     "etf": False, "ind": "finance", "indName": "기타 금융"})
    fails_on("지주회사가 금융 그룹이 아님", add)


def test_us_industry_coverage_drop_fails():
    def drop(c):
        for s in c["data"]["stocks"]:
            if s["cls"] == "us" and s.get("ind") and s["t"] < "U0300":
                s.pop("ind")
                s.pop("indName")
    fails_on("미국 업종 그룹 채움", drop)


def test_preferred_shares_do_not_fill_a_small_group():
    def add(c):
        for i in range(4):
            c["data"]["stocks"].append({"t": f"9{i:04d}5", "nk": f"우{i}", "ne": "x", "cls": "kr", "price": 1.0, "cap": 0.1,
                                         "etf": False, "ind": "ship", "indName": "조선"})
        c["data"]["stocks"].append({"t": "990000", "nk": "조선", "ne": "x", "cls": "kr", "price": 1.0, "cap": 0.1,
                                     "etf": False, "ind": "ship", "indName": "조선"})
    fails_on("업종 그룹 인원 (시장마다)", add)


def test_fixture_has_unique_codes():
    cur, _, _ = good_pair()
    codes = [s["t"] for s in cur["data"]["stocks"]]
    assert len(codes) == len(set(codes))


# ── v17.5.2: 미국 시가총액 채움 · 국내 배당 채움 변화 ──
def us_companies(cur):
    return [s for s in cur["data"]["stocks"] if s["cls"] == "us" and not s["etf"]]


def test_us_market_cap_coverage_drop_fails():
    # 야후가 시가총액을 안 보낸 날: 파이프라인은 시가총액이 없다는 이유로는 아무것도 빼지 않아요 (Jack, 2026-11-03) → 여기서 실패
    def blank(c):
        us = us_companies(c)
        for s in us[: int(len(us) * 0.06)]:
            s.pop("cap")
    fails_on("미국 시가총액 채움 (ETF 빼고)", blank)


def test_us_market_cap_coverage_counts_companies_only():
    cur, prev, final = good_pair()
    for t in ("SPY", "QQQ"):                                   # ETF 는 시가총액이 없어도 돼요
        stock(cur, t).pop("cap")
    cur["data"]["stocks"] += [{"t": f"E{i:03d}", "nk": f"ETF {i}", "ne": f"ETF {i}", "cls": "us", "price": 50.0,
                               "val": 100.0, "de": "A fund.", "fxu": True, "etf": True,
                               "d1": 0.5} for i in range(40)]   # 2026-11-03: 33개 · 진짜 ETF 처럼 d1 이 있어요 ('미국 d1 채움')
    for s in us_companies(cur)[10:13]:                         # 회사 주식 3개 빠짐 (2026-11-03 발행본의 우선주 3개처럼)
        s["cap"] = None
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert any(r[0] == "미국 시가총액 채움 (ETF 빼고)" and r[3] == "PASS" for r in rep.rows)


def with_dividends(files):
    for s in kr_of(files):
        if not s.get("fund"):
            s["dy"] = 0.0 if s["dps"] == 0 else 2.5


@pytest.mark.parametrize("key", ["dps", "dy"])
def test_korean_dividend_coverage_drop_fails(key):
    # DART 일부 장애로 배당 표를 못 받으면 주당 배당금·배당수익률이 조용히 비어요
    cur, prev, final = good_pair()
    with_dividends(cur)
    with_dividends(prev)
    assert not check(cur, prev, final).failed
    for s in kr_of(cur)[20::8]:                                # 12.4% 비움 (필수 종목은 건드리지 않아요)
        s.pop(key, None)
    assert f"국내 {key} 채움 변화" in failed_names(check(cur, prev, final))


def test_small_korean_dividend_coverage_dip_passes():
    cur, prev, final = good_pair()
    with_dividends(cur)
    with_dividends(prev)
    for s in kr_of(cur)[20::20]:                               # 5% 비움 → 통과
        s.pop("dps", None)
        s.pop("dy", None)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert {r[0] for r in rep.rows} >= {"국내 dps 채움 변화", "국내 dy 채움 변화"}


@pytest.mark.parametrize("left, ok", [({"preferred": [f"P{i}" for i in range(10)], "krListing": []}, True),
                                      ({"preferred": [f"P{i}" for i in range(11)], "krListing": []}, False),
                                      ({"preferred": [], "krListing": ["SKHY"]}, True),
                                      (None, False), ({"krListing": []}, False), ({"preferred": "STRC"}, False)])
def test_too_many_us_rows_dropped_as_preferred_fails(left, ok):
    # 이름·티커·야후 종류 규칙이 진짜 회사를 잡기 시작하거나 목록에 우선주가 몰려 들어온 날: 시가총액 채움은 통과해요 → 수로 잡아요
    cur, prev, final = good_pair()
    if left is None:
        cur["data"].pop("usLeftOut")
    else:
        cur["data"]["usLeftOut"] = left
    names = failed_names(check(cur, prev, final))
    assert ("미국 우선주·예탁증서로 뺀 종목 수" in names) is (not ok), names


# ── v17.5.2 항목 7 (Jack 승인 2026-11-03): 해외 기업(9…) ──
def add_foreign(c, **extra):
    """2026-11-03 의 코오롱티슈진처럼, 단 원화가 아닐 수 있는 칸은 비운 (파이프라인이 낼) 모양."""
    s = {"t": "950160", "nk": "코오롱티슈진", "ne": "코오롱티슈진", "cls": "kr", "price": 13900.0, "cap": 1.181, "etf": False,
         "roe": -303.2, "opm": -432.7, "debt": 562.0, "g3": 13.0, "fy": 2025, "qz": 0, "pz": 11, "mz": 3, "lz": 6}
    row = {"t": "950160", "nk": "코오롱티슈진", "s": "bio", "price": 13900.0, "cap": 1.181, "per": None, "pbr": None, "eps": None,
           "bps": None, "dps": None, "dy": None, "dps3": None, "fy": 2025, "roe": -303.2, "debt": 562.0, "eq": None,
           "rev": [None, None, None], "op": [None, None, None], "ni": [None, None, None], "dcfReady": False}
    s.update({k: v for k, v in extra.items() if not k.startswith("c_")})
    row.update({k[2:]: v for k, v in extra.items() if k.startswith("c_")})
    c["data"]["stocks"].append(s)
    c["corp"]["companies"].append(row)


@pytest.mark.parametrize("extra", [{}, {"dps": 0.0, "dy": 0.0, "dps3": [0.0, 0.0, None], "c_dps": 0.0, "c_dy": 0.0,
                                         "c_dps3": [0.0, None, None], "c_fl": {"l3": 1, "cr": 35.0}}])
def test_foreign_issuer_with_blanks_passes(extra):
    # 배당 0 (= 배당 없음)과 재무 신호(fl)는 통화와 상관없어 있어도 돼요
    cur, prev, final = good_pair()
    add_foreign(cur, **extra)
    rep = check(cur, prev, final)
    assert not rep.failed, rep.table()
    assert any(r[0] == "해외 기업(9…) 원화 아닐 수 있는 금액 비움" and r[3] == "PASS" and r[1].startswith("1곳") for r in rep.rows)


@pytest.mark.parametrize("extra", [{"pbr": 9085.27}, {"per": 11688.7}, {"eps": -2.0}, {"bps": 2.0}, {"dps": 50.0}, {"dy": 1.2},
                                   {"dps3": [0.0, 50.0, None]}, {"vz": 0}, {"c_pbr": 9085.27}, {"c_rev": [0.0, 0.0, 0.0]},
                                   {"c_ni": [-1.4, None, None]}, {"c_eq": 0.4}, {"c_evR": 3.1}, {"c_dcfReady": True},
                                   {"c_dps": 50.0}, {"c_dy": 1.2}, {"c_dps3": [50.0, None, None]}])
def test_foreign_issuer_with_won_amounts_fails(extra):
    fails_on("해외 기업(9…) 원화 아닐 수 있는 금액 비움", lambda c: add_foreign(c, **extra))


def test_missing_special_sessions_table_stops_loudly_in_the_gate(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError)):
        V.load_special_sessions(str(tmp_path / "nope.csv"))


def test_gate_reads_listing_commit_time_as_kst_for_that_file(monkeypatch):
    # GitHub 의 커밋 시각은 UTC: 07:59Z = 16:59 KST (수능일엔 최종본이 아님) · 08:00Z = 17:00 KST (최종본)
    class R:
        def __init__(self, js):
            self.status_code, self._js = 200, js

        def json(self):
            return self._js
    seen = []
    for utc, kst_hm, final in (("2026-11-19T07:59:00Z", (16, 59), False), ("2026-11-19T08:00:00Z", (17, 0), True)):
        monkeypatch.setattr(V.requests, "get", lambda url, params=None, headers=None, timeout=None, utc=utc:
                            seen.append(params) or R([{"commit": {"committer": {"date": utc}}}]))
        ct = V.http_commit_kst(CSAT)
        assert ct.utcoffset() == dt.timedelta(hours=9) and (ct.hour, ct.minute) == kst_hm, (utc, ct)
        assert (ct >= V.final_cut(CSAT, V.load_special_sessions())) is final, utc
    assert all(p and "2026-11-19" in p["path"] for p in seen), seen
