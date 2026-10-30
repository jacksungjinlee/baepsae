# -*- coding: utf-8 -*-
"""fetch_data.py 단위 테스트 (네트워크 없이). 실행: pytest tests/

listing 픽스처는 FinanceData/fdr_krx_data_cache 실제 파일의 일부(37종목)예요.
같은 2026-10-29.csv 가 하루 세 번 덮어써진 버전을 그대로 잘라 왔습니다.
  2026-10-29_0544  장 시작 전 — 시가총액이 전부 빈 값
  2026-10-29_1319  장중 — 값은 차 있지만 장중 가격
  2026-10-29_1958  장 마감 후 — 최종본
"""
import collections
import datetime as dt
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "listing")
KST = F.KST


def fixture(name):
    with open(os.path.join(FIX, name + ".csv"), encoding="utf-8") as f:
        return F.parse_listing_csv(f.read())


def at(d, hhmm):
    return dt.datetime.combine(d, dt.time(int(hhmm[:2]), int(hhmm[2:])), KST)


D28, D29, D30 = dt.date(2026, 10, 28), dt.date(2026, 10, 29), dt.date(2026, 10, 30)


def sources(files, commits):
    """files: {date: fixture name}, commits: {date: 'HHMM' or None}. 없는 날짜는 404."""
    def fetch_csv(d):
        return fixture(files[d]) if d in files else None

    def commit_kst(d):
        hm = commits.get(d)
        return at(d, hm) if hm else None
    return fetch_csv, commit_kst


# ── _fin ────────────────────────────────────────────────────
@pytest.mark.parametrize("x", [None, float("nan"), float("inf"), float("-inf"), np.float64("nan"),
                               "abc", "", "-", True, False, pd.NA, [1], {}])
def test_fin_rejects_non_numbers(x):
    assert F._fin(x) is None


@pytest.mark.parametrize("x,want", [(0, 0.0), (3, 3.0), (-1.5, -1.5), ("12.5", 12.5), (np.int64(7), 7.0),
                                    (np.float32(2.5), 2.5)])
def test_fin_keeps_finite_numbers(x, want):
    assert F._fin(x) == want


def test_nan_or_zero_is_still_nan():
    # 이 함정 때문에 2026-10 에 NaN 이 JSON 에 들어갔어요. _fin 은 막습니다.
    assert math.isnan(float("nan") or 0)
    assert F._fin(float("nan")) is None


# ── write_json ──────────────────────────────────────────────
def strict_load(path):
    def bad(tok):
        raise ValueError(tok)
    with open(path, encoding="utf-8") as f:
        return json.load(f, parse_constant=bad)


def test_write_json_replaces_nan_and_inf(tmp_path):
    p = str(tmp_path / "x.json")
    obj = {"a": float("nan"), "b": [1.0, float("inf"), {"c": float("-inf"), "d": np.float64("nan")}],
           "e": np.int64(5), "f": np.float64(1.25), "g": "NaN 은 글자로는 괜찮아요", "h": True, "i": None}
    n = F.write_json(p, obj)
    assert n == 4
    got = strict_load(p)  # NaN 이 남아 있으면 여기서 실패
    assert got == {"a": None, "b": [1.0, None, {"c": None, "d": None}], "e": 5, "f": 1.25,
                   "g": "NaN 은 글자로는 괜찮아요", "h": True, "i": None}
    with open(p, encoding="utf-8") as f:
        text = f.read()
    assert "NaN," not in text and "Infinity" not in text
    assert not os.path.exists(p + ".tmp")


def test_write_json_keeps_korean_and_compact(tmp_path):
    p = str(tmp_path / "k.json")
    F.write_json(p, {"nk": "삼성전자", "v": [1, 2]})
    with open(p, encoding="utf-8") as f:
        assert f.read() == '{"nk":"삼성전자","v":[1,2]}'


# ── 최종본 목록 고르기 ──────────────────────────────────────
def test_fixtures_are_what_they_claim():
    assert F.listing_cap_share(fixture("2026-10-29_0544")) == 0.0
    assert F.listing_cap_share(fixture("2026-10-29_1319")) == 1.0
    assert F.listing_cap_share(fixture("2026-10-29_1958")) == 1.0
    # 장중 파일과 최종본은 가격이 달라요 (그래서 '차 있음'만으로는 최종본을 알 수 없어요)
    a = fixture("2026-10-29_1319").set_index("Code")["Close"]
    b = fixture("2026-10-29_1958").set_index("Code")["Close"]
    assert (a != b).mean() > 0.5


def test_picks_final_1958_version():
    fetch, commit = sources({D29: "2026-10-29_1958", D28: "2026-10-28_1921"}, {D29: "1958", D28: "1921"})
    d, df, note, _ = F.pick_final_listing(D30, fetch, commit)
    assert d == D29 and "최종본" in note and "19:58" in note
    assert F.listing_cap_share(df) == 1.0


def test_skips_intraday_1319_version():
    fetch, commit = sources({D29: "2026-10-29_1319", D28: "2026-10-28_1921"}, {D29: "1319", D28: "1921"})
    d, _, _, notes = F.pick_final_listing(D30, fetch, commit)
    assert d == D28
    assert any("16시 전" in n for n in notes)


def test_1749_commit_counts_as_final_from_v17_5():
    # 4월 이후 거래일 5일에 하루꼴로 마지막 커밋이 16~18시 사이였어요. 16:00 부터 최종본으로 인정.
    fetch, commit = sources({D29: "2026-10-29_1958", D28: "2026-10-28_1921"}, {D29: "1749", D28: "1921"})
    d, _, note, _ = F.pick_final_listing(D30, fetch, commit)
    assert d == D29 and "17:49" in note
    fetch, commit = sources({D29: "2026-10-29_1958", D28: "2026-10-28_1921"}, {D29: "1559", D28: "1921"})
    assert F.pick_final_listing(D30, fetch, commit)[0] == D28


def test_skips_premarket_0544_version():
    fetch, commit = sources({D29: "2026-10-29_0544", D28: "2026-10-28_1921"}, {D29: "0544", D28: "1921"})
    d, _, _, notes = F.pick_final_listing(D30, fetch, commit)
    assert d == D28
    assert any("시가총액 0%" in n for n in notes)


def test_never_uses_today_even_if_final():
    # 오늘 날짜 파일은 아직 장이 안 끝났을 수 있어요. 항상 '오늘 이전'만.
    fetch, commit = sources({D30: "2026-10-29_1958", D29: "2026-10-29_1958"}, {D30: "1958", D29: "1958"})
    d, _, _, _ = F.pick_final_listing(D30, fetch, commit)
    assert d == D29


def test_weekend_files_are_skipped():
    mon, sun, sat, fri = dt.date(2026, 10, 26), dt.date(2026, 10, 25), dt.date(2026, 10, 24), dt.date(2026, 10, 23)
    fetch, commit = sources({sun: "2026-10-24_0444", sat: "2026-10-24_0444", fri: "2026-10-29_1958"},
                            {sun: "0444", sat: "0444", fri: "2251"})
    d, _, _, _ = F.pick_final_listing(mon, fetch, commit)
    assert d == fri


def test_commit_time_unknown_needs_next_trading_day_file():
    # 커밋 시각을 못 보면: 그 뒤 날짜에 시가총액이 찬 파일이 있어야만 '끝난 날'로 인정
    files = {D30: "2026-10-30_0549", D29: "2026-10-29_1958", D28: "2026-10-28_1921"}
    fetch, commit = sources(files, {})
    d, _, note, _ = F.pick_final_listing(dt.date(2026, 10, 31), fetch, commit)
    # 10/30 파일은 장 전(빈 값) → 10/29 는 확인 불가 → 10/28 (10/29 파일이 차 있으니 끝난 날)
    assert d == D28 and "확인 불가" in note
    files[D30] = "2026-10-29_1319"  # 다음 거래일 장중 파일이 생기면 10/29 도 인정
    d2, _, _, _ = F.pick_final_listing(dt.date(2026, 10, 31), fetch, commit)
    assert d2 == D29


def test_no_final_file_returns_none():
    fetch, commit = sources({D29: "2026-10-29_0544", D28: "2026-10-29_1319"}, {D29: "0544", D28: "1319"})
    d, df, note, _ = F.pick_final_listing(D30, fetch, commit)
    assert d is None and df is None and "최종본이 없어요" in note


def test_download_failure_is_logged_not_hidden():
    def fetch(d):
        if d == D29:
            raise RuntimeError("timeout")
        return fixture("2026-10-28_1921") if d == D28 else None
    d, _, _, notes = F.pick_final_listing(D30, fetch, lambda d: at(d, "1921"))
    assert d == D28
    assert any(n.startswith("!!") and "받기 실패" in n for n in notes)


# ── 종목 선정 ───────────────────────────────────────────────
def test_universe_is_top_by_market_cap():
    # 픽스처 37종목 중 한국전력(015760)이 시총 31위 → 상위 31개면 필수 종목이 다 들어와요
    u = F.select_kr_universe(fixture("2026-10-29_1958"), 31)
    assert len(u) == 31
    caps = pd.to_numeric(u["Marcap"]).tolist()
    assert caps == sorted(caps, reverse=True)
    assert u.iloc[0]["Code"] == "005930"
    assert set(F.MUST_KR) <= set(u["Code"])
    names = list(u["Name"].head(20))
    assert names != sorted(names)  # 가나다순이 아니어야 해요


def test_alphabetical_universe_fails_loudly():
    # 시가총액이 빈 파일 → 정렬이 안 되고 가나다순만 남는 2026-10 사고 재현
    blank = fixture("2026-10-29_0544").sort_values("Name")
    with pytest.raises(RuntimeError, match="꼭 있어야 할 종목"):
        F.select_kr_universe(blank, 10)


# ── 날짜는 한국 시간 ────────────────────────────────────────
def test_today_kst_uses_korean_date_not_utc():
    utc = dt.timezone.utc
    # 예약 실행 시각(UTC 21:30)은 한국으로는 이미 다음 날 06:30 이에요
    assert F.today_kst(dt.datetime(2026, 10, 29, 21, 30, tzinfo=utc)) == dt.date(2026, 10, 30)
    assert F.today_kst(dt.datetime(2026, 10, 29, 14, 59, tzinfo=utc)) == dt.date(2026, 10, 29)
    assert F.today_kst(dt.datetime(2026, 10, 29, 15, 0, tzinfo=utc)) == dt.date(2026, 10, 30)


def test_no_utc_today_left_in_pipeline():
    with open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8") as f:
        src = f.read()
    assert "date.today()" not in src


def test_only_write_json_writes_published_files():
    """data/corp/macro/disc.json 은 write_json 만 써요. json.dump 는 write_json 과 DART 캐시 저장 두 곳뿐."""
    import ast
    with open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    owners = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef,)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and getattr(sub.func, "attr", "") == "dump":
                    owners.append(node.name)
    assert sorted(owners) == ["save", "save_us_info", "write_json"]   # 캐시 파일 둘 + 발행 파일


# ── 워크플로 안전장치 ───────────────────────────────────────
def load_workflow():
    path = os.path.join(ROOT, ".github", "workflows", "update-data.yml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return text, yaml.safe_load(text)


def test_workflow_never_hides_failures():
    text, wf = load_workflow()
    assert "|| true" not in text
    assert "continue-on-error" not in text
    steps = wf["jobs"]["update"]["steps"]
    names = [s.get("name") or s.get("uses") for s in steps]
    order = ["라이브러리 설치", "DART 캐시 불러오기", "데이터 수집", "DART 캐시 저장", "발행 관문 (validate_data.py)", "커밋 & 푸시"]
    idx = [names.index(n) for n in order]
    assert idx == sorted(idx), names                     # 스펙 H 순서
    by = dict(zip(names, steps))
    # always() 는 캐시 저장에만
    for n, st in by.items():
        if "always()" in str(st.get("if", "")):
            assert n == "DART 캐시 저장", n
    assert "if" not in by["발행 관문 (validate_data.py)"]          # 관문은 조건 없이 늘 실행
    assert by["커밋 & 푸시"]["if"].replace(" ", "") == "${{!inputs.dry_run}}"
    assert 'if [ "$GITHUB_REF" != "refs/heads/main" ]' in by["커밋 & 푸시"]["run"]
    assert "validate_data.py" in by["발행 관문 (validate_data.py)"]["run"]
    # 시험용 입력은 main 에서 거부
    guard = by["입력 확인"]["run"]
    assert 'refs/heads/main' in guard and 'DART_MODE" = "off"' in guard and "PREV_REF" in guard and "SELFTEST" in guard
    assert "exit 1" in guard
    # 입력: dry_run · dart(cache/full/off) · bootstrap 은 기본값이 꺼짐/cache
    inp = wf[True]["workflow_dispatch"]["inputs"]
    assert inp["dry_run"]["default"] is False and inp["bootstrap"]["default"] is False
    assert inp["dart"]["default"] == "cache" and inp["dart"]["options"] == ["cache", "full", "off"]
    assert inp["selftest"]["default"] == "none"
    # DART 캐시 키 (스펙 C)
    assert by["DART 캐시 불러오기"]["with"]["restore-keys"] == "dart-cache-v1-"
    assert by["DART 캐시 저장"]["with"]["key"].startswith("dart-cache-v1-${{ github.run_id }}")
    assert wf["jobs"]["update"]["timeout-minutes"] == 300
    assert "inputs.dry_run" in wf["concurrency"]["group"]
    assert wf["concurrency"]["cancel-in-progress"] is False


def test_pipeline_refuses_test_inputs_on_main(monkeypatch):
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("BAEPSAE_SELFTEST", "corrupt-price")
    with pytest.raises(RuntimeError, match="main"):
        F.main()
    monkeypatch.delenv("BAEPSAE_SELFTEST")
    monkeypatch.setenv("DART_MODE", "off")
    with pytest.raises(RuntimeError, match="main"):
        F.main()


# ── v17.5: 공식 종가 · 시계열 자르기 ───────────────────────
def test_official_close_is_marcap_over_stocks_not_close_column():
    df = fixture("2026-10-29_1958").set_index("Code")
    row = df.loc["005930"]
    assert float(row["Close"]) == 230500                 # 저녁 파일의 Close = 시간외 가격
    assert F.kr_official_close(row) == 232000.0          # 시가총액 ÷ 상장주식수 = 공식 종가
    # 다음 날(10/30) 네이버의 '전일 대비' 기준가도 232,000 (220,500 + 11,500)
    assert F.kr_official_close({"Marcap": None, "Stocks": 10}) is None
    assert F.kr_official_close({"Marcap": float("nan"), "Stocks": 10}) is None


def series(pairs):
    return pd.Series([v for _, v in pairs], index=pd.to_datetime([d for d, _ in pairs]))


def test_cut_at_drops_bars_after_pxdate():
    px = series([("2026-10-28", 1), ("2026-10-29", 2), ("2026-10-30", 3)])
    assert list(F.cut_at(px, D29)) == [1, 2]


def test_pin_close_sets_pxdate_bar_to_official_close():
    px = series([("2026-10-28", 100.0), ("2026-10-29", 230500.0), ("2026-10-30", 220500.0)])
    out, how = F.pin_close(px, D29, 232000.0)
    assert how == "fixed" and out.index[-1] == pd.Timestamp(D29) and out.iloc[-1] == 232000.0 and len(out) == 2
    out, how = F.pin_close(px.iloc[:1], D29, 232000.0)
    assert how == "added" and out.iloc[-1] == 232000.0
    out, how = F.pin_close(series([("2026-10-29", 5.0)]), D29, 5.0)
    assert how == "same"


# ── v17.5: 시장별 팩터 · 단위 · 인기 목록 ─────────────────
def test_factors_are_ranked_within_one_market():
    kr = [{"t": f"K{i}", "cls": "kr", "cap": float(i + 1), "pbr": 1.0 + i, "mom": i, "roe": i, "vol": 10 + i} for i in range(10)]
    us = [{"t": f"U{i}", "cls": "us", "cap": 1000.0 * (i + 1), "pbr": 0.1, "mom": 99, "roe": 99, "vol": 1} for i in range(10)]
    with pytest.raises(ValueError, match="섞였어요"):
        F.add_percentiles(kr + us)
    F.add_percentiles(kr)
    assert kr[0]["pz"] == 90 and kr[-1]["pz"] == 0      # 한국 안에서 가장 작은 회사가 규모 점수 최고
    assert kr[0]["vz"] == 90                             # PBR 가장 낮음
    blank = [{"t": "A", "cls": "kr", "cap": None, "pbr": float("nan")}, {"t": "B", "cls": "kr", "cap": None, "pbr": None}]
    F.add_percentiles(blank)                             # 빈 열이 있어도 죽지 않아요
    assert "pz" not in blank[0] and "vz" not in blank[0]


def test_us_cap_and_val_are_in_won():
    cap, val = F.us_cap_val(4.0e12, 50_000_000, 230.0, 1333.3)   # 시총 4조 달러, 하루 5천만 주
    assert cap == round(4.0e12 * 1333.3 / 1e12, 3)               # 5,333.2 조원
    assert 5000 < cap < 5500
    assert val == round(50_000_000 * 230 * 1333.3 / 1e8, 1)      # 억원
    assert F.us_cap_val(None, None, 230.0, 1333.3) == (None, None)
    assert F.us_cap_val(float("nan"), 1, 1, 1333.3)[0] is None


def test_popular_is_ranked_per_market():
    kr = [{"t": "005930", "val": 20000.0}, {"t": "000660", "val": 15000.0}, {"t": "X", "val": None}]
    us = [{"t": "AAPL", "val": 160000.0}]
    assert F.popular_list(kr, us) == ["005930", "000660", "AAPL"]   # 미국 거래대금이 커도 한국이 앞


def test_us_bar_counts_only_after_new_york_close():
    utc = dt.timezone.utc
    # 한국 10:00 = 뉴욕 전날 21:00 → 그날 장은 끝남
    assert F.us_last_complete_day(dt.datetime(2026, 10, 30, 1, 0, tzinfo=utc)) == dt.date(2026, 10, 29)
    # 뉴욕 14:00 (장중) → 전날까지만
    assert F.us_last_complete_day(dt.datetime(2026, 10, 30, 18, 0, tzinfo=utc)) == dt.date(2026, 10, 29)
    # 뉴욕 17:00 → 오늘 봉도 완성
    assert F.us_last_complete_day(dt.datetime(2026, 10, 30, 21, 0, tzinfo=utc)) == dt.date(2026, 10, 30)


# ── v17.5: DART 캐시 ───────────────────────────────────────
def test_report_dates():
    assert F.report_deadline(2026, "11014") == dt.date(2026, 11, 14)
    assert F.report_deadline(2025, "11011") == dt.date(2026, 3, 31)
    assert F.report_period_end(2026, "11012") == dt.date(2026, 6, 30)


def test_dart_entry_due_rules():
    due = F.dart_entry_due
    today = dt.date(2026, 10, 27)
    assert due(None, 2026, "11014", today) is True                    # 처음
    assert due(None, 2026, "11014", dt.date(2026, 9, 30)) is False    # 분기가 안 끝남
    assert due({"st": "000", "at": "2026-01-01", "d": {}}, 2026, "11012", today) is False   # 찾은 건 확정
    assert due({"st": "000", "at": "2026-01-01", "d": {}}, 2026, "11012", today, revalidate=True) is True
    assert due({"st": "013", "at": "2026-10-25"}, 2026, "11014", today) is False   # 7일 안
    assert due({"st": "013", "at": "2026-10-20"}, 2026, "11014", today) is True    # 7일 지남
    assert due({"st": "013", "at": "2026-11-08"}, 2026, "11014", dt.date(2026, 11, 9)) is True   # 마감 주간엔 매일
    assert due({"st": "013", "at": "2026-11-16"}, 2026, "11014", dt.date(2026, 11, 17)) is False  # 마감+3일부턴 다시 7일


def fake_dart(statuses):
    """statuses: {(year, reprt, fs): status} — 없으면 013."""
    calls = []

    def get(self, endpoint, params, timeout=25):
        calls.append(params)
        st = statuses.get((int(params.get("bsns_year", 0)), params.get("reprt_code"), params.get("fs_div")), "013")
        with self.lock:
            self.status[st] += 1
            if st in F.DART_FATAL and not self.fatal:
                self.fatal = (st, "test")
        if st in F.DART_FATAL:
            return None
        return {"status": st, "list": [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": "1e10"}]}
    return get, calls


def test_dart_cache_reuses_found_reports(tmp_path, monkeypatch):
    get, calls = fake_dart({(2026, "11012", "CFS"): "000"})
    monkeypatch.setattr(F.DartClient, "get", get)
    path = str(tmp_path / "c.json.gz")
    c = F.DartClient("k", today=dt.date(2026, 10, 31), path=path)
    assert F.dart_quarter(c, "C1", 2026, "11012")["rev"] == 100.0
    assert F.dart_quarter(c, "C1", 2026, "11014") is None             # 아직 안 냄 (CFS·OFS 둘 다 013)
    n = len(calls)
    c.save()
    c2 = F.DartClient("k", today=dt.date(2026, 11, 1), path=path)
    assert F.dart_quarter(c2, "C1", 2026, "11012")["rev"] == 100.0
    assert F.dart_quarter(c2, "C1", 2026, "11014") is None
    assert len(calls) == n                                            # 다음 날엔 호출 0번
    assert c2.cache_hits >= 2


def test_dart_quota_exceeded_fails_loudly(tmp_path, monkeypatch):
    get, _ = fake_dart({(2026, "11012", "CFS"): "020"})
    monkeypatch.setattr(F.DartClient, "get", get)
    c = F.DartClient("k", today=dt.date(2026, 10, 31), path=str(tmp_path / "c.json.gz"))
    assert F.dart_quarter(c, "C1", 2026, "11012") is None
    with pytest.raises(RuntimeError, match="일일 한도 초과"):
        c.raise_if_fatal()
    assert "020" in c.summary()


def test_dart_full_only_once_per_kst_day(tmp_path, monkeypatch):
    path = str(tmp_path / "c.json.gz")
    c = F.DartClient("k", mode="full", today=dt.date(2026, 10, 31), path=path)
    c.save()
    with pytest.raises(RuntimeError, match="하루 한 번"):
        F.DartClient("k", mode="full", today=dt.date(2026, 10, 31), path=path)
    F.DartClient("k", mode="full", today=dt.date(2026, 11, 1), path=path)   # 다음 날은 괜찮아요


def test_current_quarter_needs_seventy_percent():
    assert F.pick_current_quarter([("11014", 0.64), ("11012", 0.98)]) == "11012"
    assert F.pick_current_quarter([("11014", 0.70)]) == "11014"
    assert F.pick_current_quarter([("11013", 0.2)]) is None


# ── v17.5 리뷰 반영: 계절별 TTM · 오류 내성 · 캐시 저장 · 재확인 ────
def fake_calendar_dart(n=300, filers=0.8):
    """사업보고서는 모두 3/25 에, 분기보고서는 상위 80% 기업이 마감 5일 전에 내는 가짜 DART."""
    def rows(amount):
        return [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": str(amount), "frmtrm_amount": str(amount * 0.9),
                 "bfefrmtrm_amount": str(amount * 0.8), "thstrm_add_amount": str(amount)},
                {"account_nm": "당기순이익", "sj_div": "IS", "thstrm_amount": str(amount / 10), "frmtrm_amount": "1",
                 "bfefrmtrm_amount": "1", "thstrm_add_amount": str(amount / 10)},
                {"account_nm": "자본총계", "sj_div": "BS", "thstrm_amount": str(amount * 5)},
                {"account_nm": "부채총계", "sj_div": "BS", "thstrm_amount": str(amount * 2)}]

    def get(self, endpoint, params, timeout=25):
        i = int(params["corp_code"][1:])
        y, r, fs = int(params["bsns_year"]), params["reprt_code"], params.get("fs_div")
        filed = False
        if endpoint.startswith("fnltt") and fs == "CFS":
            if r == "11011":
                filed = self.today >= dt.date(y + 1, 3, 25)
            else:
                filed = i < n * filers and self.today >= F.report_deadline(y, r) - dt.timedelta(days=5)
        st = "000" if filed else "013"
        with self.lock:
            self.status[st] += 1
        return {"status": st, "list": rows(1e11) if filed else []}
    return get


def run_enrich(monkeypatch, tmp_path, today, n=300):
    monkeypatch.setattr(F.DartClient, "get", fake_calendar_dart(n))
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {f"{i:06d}": f"C{i}" for i in range(n)})
    stocks = [{"t": f"{i:06d}", "cls": "kr", "cap": float(n - i), "shr": 1_000_000, "price": 10000.0} for i in range(n)]
    c = F.DartClient("k", today=today, path=str(tmp_path / f"{today}.json.gz"))
    _, fin = F.enrich_with_dart(stocks, c)
    return collections.Counter(v.get("bq") for v in fin.values())


@pytest.mark.parametrize("today,want", [
    (dt.date(2026, 10, 30), {"2026.2Q": 240}),      # 2Q 가 현재 분기, 안 낸 20% 는 표시 없음
    (dt.date(2027, 2, 1), {"2026.3Q": 240}),        # 사업보고서 전: 2025 연간 + 2026 3Q 누적
    (dt.date(2027, 4, 10), {"2026.4Q": 300}),       # 봄: 2026 사업보고서가 곧 최근 4개 분기 (예전엔 0곳 → 검증 실패)
    (dt.date(2027, 5, 13), {"2027.1Q": 240}),       # 1Q 70% 넘음 → 1Q 기준
])
def test_ttm_basis_through_the_year(monkeypatch, tmp_path, today, want):
    got = run_enrich(monkeypatch, tmp_path, today)
    got.pop(None, None)
    assert dict(got) == want


def test_one_bad_company_does_not_stop_the_run(monkeypatch, tmp_path):
    base = fake_calendar_dart()

    def get(self, endpoint, params, timeout=25):
        j = base(self, endpoint, params, timeout)
        if params["corp_code"] == "C7" and j["list"]:
            j["list"][0]["thstrm_amount"] = "-5"        # 음수 매출 → 예전엔 복소수 TypeError
        return j
    monkeypatch.setattr(F.DartClient, "get", get)
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {f"{i:06d}": f"C{i}" for i in range(20)})
    stocks = [{"t": f"{i:06d}", "cls": "kr", "cap": float(20 - i), "shr": 1000, "price": 1.0} for i in range(20)]
    c = F.DartClient("k", today=dt.date(2026, 10, 30), path=str(tmp_path / "c.json.gz"))
    _, fin = F.enrich_with_dart(stocks, c)
    assert len(fin) >= 19


def test_parse_error_is_counted_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(F.DartClient, "get", lambda self, e, p, timeout=25: {"status": "000", "list": [{}]})
    c = F.DartClient("k", today=dt.date(2026, 10, 30), path=str(tmp_path / "c.json.gz"))

    def boom(rows):
        raise ValueError("이상한 응답")
    assert c.report("x", "C1", 2026, "11012", "CFS", boom) is None
    assert c.parse_errors["ValueError"] == 1 and "해석 오류" in c.summary()
    assert "C1|2026|11012|CFS" not in c.entries


def test_parallel_cache_saves_never_corrupt_the_file(tmp_path):
    import gzip
    import threading as th
    c = F.DartClient("k", today=dt.date(2026, 10, 30), path=str(tmp_path / "c.json.gz"))
    c.entries = {f"K{i}": {"st": "000", "at": "2026-10-30", "d": {"rev": [float(i)] * 50}} for i in range(3000)}
    ts = [th.Thread(target=c.save) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    with gzip.open(str(tmp_path / "c.json.gz"), "rt", encoding="utf-8") as f:
        assert len(json.load(f)["entries"]) == 3000


def test_revalidation_only_for_used_entries_within_budget(tmp_path, monkeypatch):
    calls = []

    def get(self, endpoint, params, timeout=25):
        calls.append(params["corp_code"])
        with self.lock:
            self.status["000"] += 1
        return {"status": "000", "list": [{"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": "1"}]}
    monkeypatch.setattr(F.DartClient, "get", get)
    monkeypatch.setattr(F, "DART_REVALIDATE_PER_RUN", 2)
    c = F.DartClient("k", today=dt.date(2026, 10, 30), path=str(tmp_path / "c.json.gz"))
    old = {"st": "000", "at": "2026-06-01", "d": {"rev": 9.0}}
    c.entries = {f"C{i}|2026|11012|CFS": dict(old) for i in range(5)}
    c.entries["GONE|2020|11012|CFS"] = dict(old)                 # 더는 쓰지 않는 항목은 재확인하지 않아요
    for i in range(5):
        c.report("x", f"C{i}", 2026, "11012", "CFS", F.parse_dart_quarter)
    c.report("x", "C0", 2026, "11012", "CFS", F.parse_dart_quarter)   # 같은 실행에서 두 번째는 다시 안 물어요
    assert calls == ["C0", "C1"]
    assert c.revalidated == 2 and c.entries["GONE|2020|11012|CFS"]["at"] == "2026-06-01"


# ── v17.5: 미국 상세 정보 보관 · ECOS 장애 때 지난 커브 ─────────────
def test_us_info_rescaled_to_todays_price():
    info = {"shortName": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics",
            "trailingPE": 30.0, "priceToBook": 40.0, "marketCap": 4.0e12, "dividendYield": 0.5,
            "averageVolume": 5e7, "longBusinessSummary": "Makes phones.", "returnOnEquity": float("nan")}
    rec = {"t": "AAPL", "nk": "AAPL", "price": 220.0}
    assert F.apply_us_info(rec, info, px_then=200.0, fx=1333.3) is True
    assert rec["nk"] == "Apple Inc." and rec["de"] == "Makes phones."
    assert rec["per"] == 33.0 and rec["pbr"] == 44.0                  # 가격 10% 오름 → 10% 높게
    assert rec["cap"] == round(4.0e12 * 1.1 * 1333.3 / 1e12, 3)
    assert rec["dy"] == round(0.5 / 1.1, 2)                          # 0.5% → 가격이 오르면 낮아져요 (100배 아님)
    r2 = {"t": "X", "price": 10.0}
    F.apply_us_info(r2, {"shortName": "X", "dividendYield": 0.31}, 10.0, 1333.3)
    assert r2["dy"] == 0.31                                          # 애플이 31% 로 나오던 버그
    r3 = {"t": "Y", "price": 10.0}
    F.apply_us_info(r3, {"shortName": "Y", "dividendYield": 45.0}, 10.0, 1333.3)
    assert "dy" not in r3
    assert "roe" not in rec                                          # NaN 은 버려요
    assert F.apply_us_info({"t": "X", "price": 1.0}, {}, None, 1333.3) is False


def test_us_info_cache_refresh_and_max_age(tmp_path, monkeypatch):
    path = str(tmp_path / "us.json.gz")
    F.save_us_info({"AAPL": {"at": "2026-10-29", "px": 1.0, "info": {"shortName": "Apple", "trailingPE": float("nan")}}}, path)
    back = F.load_us_info(path)                                       # NaN 이 있어도 저장·읽기가 돼요
    assert back["AAPL"]["info"]["shortName"] == "Apple" and back["AAPL"]["info"]["trailingPE"] is None
    assert F.US_INFO_FRESH_DAYS == 3 and F.US_INFO_MAX_AGE_DAYS == 14


def test_ecos_outage_keeps_last_published_curve(tmp_path):
    prev = {"curve": {"tenors": [3, 10], "now": [3.1, 4.0], "ago": [3.0, 3.5], "date": "2026-10-29"},
            "sprKr": {"m": ["26.10"], "v": [0.9]}, "credit": {"now": 0.7}, "g10": {"kr": {"m": ["26.10"], "v": [4.0]}}}
    p = tmp_path / "macro.json"
    p.write_text(json.dumps(prev), encoding="utf-8")
    out, g10 = {"curve": None, "sprKr": None, "tenor": None, "credit": None}, {}
    F.keep_prev_ecos(out, g10, path=str(p))
    assert out["curve"]["date"] == "2026-10-29" and out["ecosKept"] is True   # 날짜는 옛 날짜 그대로
    assert g10["kr"]["v"] == [4.0]
    out2 = {"curve": None}
    F.keep_prev_ecos(out2, {}, path=str(tmp_path / "없음.json"))
    assert out2["curve"] is None
