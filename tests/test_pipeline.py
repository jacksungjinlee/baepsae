# -*- coding: utf-8 -*-
"""fetch_data.py 단위 테스트 (네트워크 없이). 실행: pytest tests/

listing 픽스처는 FinanceData/fdr_krx_data_cache 실제 파일의 일부(37종목)예요.
같은 2026-10-29.csv 가 하루 세 번 덮어써진 버전을 그대로 잘라 왔습니다.
  2026-10-29_0544  장 시작 전 — 시가총액이 전부 빈 값
  2026-10-29_1319  장중 — 값은 차 있지만 장중 가격
  2026-10-29_1958  장 마감 후 — 최종본
"""
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
    assert any("18시 전" in n for n in notes)


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
    assert "json.dump(" in src and src.count("json.dump(") == 1  # write_json 안의 한 곳뿐


# ── 워크플로 안전장치 ───────────────────────────────────────
def test_workflow_never_hides_failures():
    path = os.path.join(ROOT, ".github", "workflows", "update-data.yml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    wf = yaml.safe_load(text)
    assert "|| true" not in text
    assert "continue-on-error" not in text
    assert "always()" not in text
    steps = wf["jobs"]["update"]["steps"]
    names = [s.get("name") for s in steps]
    fetch, check, commit = names.index("데이터 수집"), names.index("결과 확인"), names.index("커밋 & 푸시")
    assert fetch < check < commit
    # 결과 확인은 조건 없이 항상 돌고, 커밋은 시험 실행이 아닐 때만 · main 에서만
    assert "if" not in steps[check]
    assert steps[commit]["if"].replace(" ", "") == "${{!inputs.dry_run}}"
    assert 'if [ "$GITHUB_REF" != "refs/heads/main" ]' in steps[commit]["run"]
    # DART 끄기는 시험 실행일 때만
    run = steps[fetch]["run"]
    assert 'if [ "$DRY_RUN" != "true" ]' in run and "exit 1" in run.split("unset DART_API_KEY")[0]
    # 결과 확인이 NaN 을 거부하는지 (parse_constant)
    assert "parse_constant" in steps[check]["run"]
    # 시험 실행과 매일 실행은 서로 다른 동시 실행 그룹 (시험 실행이 대기 중인 매일 실행을 취소하지 않게)
    assert "inputs.dry_run" in wf["concurrency"]["group"]


def test_workflow_check_step_rejects_nan_and_missing_stock(tmp_path):
    """워크플로의 '결과 확인' 스크립트를 실제로 돌려봐요."""
    import subprocess
    path = os.path.join(ROOT, ".github", "workflows", "update-data.yml")
    with open(path, encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    script = [s for s in wf["jobs"]["update"]["steps"] if s.get("name") == "결과 확인"][0]["run"]

    must = ["005930", "000660", "005380", "015760", "105560"]
    kr = [{"t": t, "cls": "kr", "price": 1000.0, "cap": 1.0} for t in must]
    kr += [{"t": f"9{i:05d}", "cls": "kr", "price": 1000.0, "cap": 0.1} for i in range(2300)]
    good = {"data.json": {"asOf": "2026-10-31", "stocks": kr},
            "corp.json": {"companies": [{"t": t} for t in must], "sectors": {"semi": {}}},
            "disc.json": {"insider": [], "nps": []}, "macro.json": {"curve": None}}

    def run_with(files):
        for name, obj in files.items():
            F.write_json(str(tmp_path / name), obj)
        return subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)

    assert run_with(good).returncode == 0
    with open(tmp_path / "disc.json", "w", encoding="utf-8") as f:
        f.write('{"insider":[{"cap":NaN}],"nps":[]}')
    r = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 1 and "NaN" in r.stdout
    no_hyundai = dict(good, **{"data.json": {"asOf": "x", "stocks": [s for s in kr if s["t"] != "005380"]}})
    r = run_with(no_hyundai)
    assert r.returncode == 1 and "005380" in r.stdout
