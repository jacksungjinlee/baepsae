# -*- coding: utf-8 -*-
"""v17.5.3: 아침 매일 실행을 여러 시각에 걸고, 이미 발행됐으면 데이터 수집 전에 끝내요 (already_published.py · update-data.yml).

- '이미 발행됨' = main 의 publishedAt 이 가장 최근의 미국 종가 확정(뉴욕 16:30, fetch_data 와 같은 기준) 이후.
- 읽을 수 없거나 이상한 값이면 늘 '실행' (조용히 건너뛰지 않아요) · 수동 실행은 확인하지 않아요.
- 정해진 시각은 모두 정각·30분이 아니고, 모두 미국 종가 확정 뒤, 한국 장 시작(09:00 KST) 전이에요.
- 확인은 별도 job 이라 DART 캐시·데이터 수집·발행보다 먼저 끝나고, 건너뛸 때는 update job 전체가 건너뛰어요.
"""
import datetime as dt
import json
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import already_published as A          # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))


def kst(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=KST)


def test_cutoff_matches_the_pipeline_rule_across_both_dst_changes():
    import fetch_data as F
    starts = [kst(2026, 3, 6, 0, 0), kst(2026, 10, 30, 0, 0)]          # 미국 서머타임 시작(3/8) · 끝(11/1) 앞뒤
    for s in starts:
        for i in range(0, 6 * 24 * 4):                                 # 6일 동안 15분마다
            now = s + dt.timedelta(minutes=15 * i)
            assert A.last_us_cutoff(now).date() == F.us_last_complete_day(now), now
    assert A.US_CLOSE_FINAL == dt.time(16, 30)


def test_cutoff_in_kst_winter_and_summer():
    assert A.last_us_cutoff(kst(2026, 11, 4, 7, 0)).astimezone(KST) == kst(2026, 11, 4, 6, 30)    # 겨울: 06:30 KST
    assert A.last_us_cutoff(kst(2026, 11, 4, 6, 29)).astimezone(KST) == kst(2026, 11, 3, 6, 30)   # 아직 전이면 하루 전
    assert A.last_us_cutoff(kst(2026, 7, 8, 7, 0)).astimezone(KST) == kst(2026, 7, 8, 5, 30)      # 여름: 05:30 KST


def test_decide_on_the_real_week_of_2026_11_03():
    # 11-03 00:09 의 수동 발행(한국 11-02 종가, 미국은 그 전날)은 아침 실행을 막으면 안 돼요
    skip, why = A.decide("2026-11-03T00:09:45+09:00", kst(2026, 11, 3, 6, 45))
    assert skip is False and "아직 발행 전" in why
    # 06:41 실행이 발행했으면 07:23 · 08:07 · 08:49 실행은 건너뛰어요
    for hh, mm in ((7, 23), (8, 7), (8, 49), (11, 59)):
        skip, why = A.decide("2026-11-03T06:41:05+09:00", kst(2026, 11, 3, hh, mm))
        assert skip is True and "이미 발행" in why, (hh, mm)
    # 11:59 에 시작한 실행의 발행분은 다음 날 아침 실행을 막지 않아요
    assert A.decide("2026-11-03T12:00:02+09:00", kst(2026, 11, 4, 6, 41))[0] is False
    # 06:25 에 시작한 실행은 미국 종가 확정 전이라 하루 전 미국 값을 썼어요 → 뒤의 실행이 다시 해요
    assert A.decide("2026-11-04T06:25:00+09:00", kst(2026, 11, 4, 7, 23))[0] is False


@pytest.mark.parametrize("bad", [None, "", "어제", "2026-11-03", "2026-11-03T06:41:05", 12345, "2026-13-40T00:00:00+09:00"])
def test_unreadable_published_at_always_runs(bad):
    skip, why = A.decide(bad, kst(2026, 11, 3, 8, 0))
    assert skip is False and "실행해요" in why


def test_published_at_in_the_future_runs():
    assert A.decide("2026-11-03T09:30:00+09:00", kst(2026, 11, 3, 8, 0))[0] is False


def test_main_writes_the_output_and_never_skips_on_a_bad_file(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    good = tmp_path / "data.json"
    good.write_text(json.dumps({"publishedAt": "2026-11-03T06:41:05+09:00"}), encoding="utf-8")
    assert A.main(["x", str(good)], now=kst(2026, 11, 3, 7, 23)) is True
    assert out.read_text().strip().splitlines()[-1] == "skip=true"
    assert "[건너뜀]" in capsys.readouterr().out
    for content in (None, "{ broken", json.dumps({"pxDate": "2026-11-02"})):
        p = tmp_path / "bad.json"
        if content is None:
            p = tmp_path / "missing.json"
        else:
            p.write_text(content, encoding="utf-8")
        assert A.main(["x", str(p)], now=kst(2026, 11, 3, 7, 23)) is False
        assert out.read_text().strip().splitlines()[-1] == "skip=false"
    assert "실행해요" in capsys.readouterr().out


def load_workflow():
    with open(os.path.join(ROOT, ".github", "workflows", "update-data.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_morning_schedule_is_off_round_after_the_us_close_and_before_the_open():
    crons = [c["cron"] for c in load_workflow()[True]["schedule"]]
    assert len(crons) >= 3, crons
    for c in crons:
        minute, hour, dom, mon, dow = c.split()
        m, h = int(minute), int(hour)
        assert m not in (0, 30) and (dom, mon, dow) == ("*", "*", "1-5"), c        # 정각·30분 피하기 · UTC 월~금 = 한국 화~토
        utc = h * 60 + m
        assert 21 * 60 + 30 < utc < 24 * 60, c                                     # 겨울 미국 종가 확정(21:30 UTC) 뒤, 같은 UTC 날
        assert (utc + 9 * 60) % (24 * 60) < 9 * 60, c                              # 한국 장 시작(09:00 KST) 전


def test_check_job_runs_first_and_gates_the_whole_update_job():
    wf = load_workflow()
    check, update = wf["jobs"]["check"], wf["jobs"]["update"]
    assert update["needs"] == "check" and update["if"].replace(" ", "") == "needs.check.outputs.skip!='true'"
    assert check["outputs"]["skip"] == "${{ steps.already.outputs.skip }}"
    run = next(s for s in check["steps"] if s.get("id") == "already")["run"]
    assert 'github.event_name }}" != "schedule"' in run and "skip=false" in run          # 수동 실행은 늘 실행
    assert "already_published.py" in run and "git fetch --depth=1 origin main" in run
    # 확인 job 에는 DART·비밀값·캐시·커밋이 없어요
    text = json.dumps(check, ensure_ascii=False)
    for word in ("DART", "secrets", "cache", "git push", "git commit", "fetch_data.py"):
        assert word not in text, word
    # 확인이 실패해도 '건너뜀'이 되지 않아요: 실패하면 skip=false 를 써요
    assert '|| { echo "!! 확인 스크립트가 실패했어요 → 실행해요"; echo "skip=false" >> "$GITHUB_OUTPUT"; }' in run
