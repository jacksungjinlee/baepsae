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
    # 평일이면 fetch_data.us_last_complete_day 와 같은 날이고, 토·일이면 그 앞 금요일 (S&P500 마지막 봉과 같은 날)
    import fetch_data as F
    starts = [kst(2026, 3, 6, 0, 0), kst(2026, 10, 30, 0, 0)]          # 미국 서머타임 시작(3/8) · 끝(11/1) 앞뒤
    for s in starts:
        for i in range(0, 6 * 24 * 4):                                 # 6일 동안 15분마다
            now = s + dt.timedelta(minutes=15 * i)
            want = F.us_last_complete_day(now)
            while want.weekday() >= 5:
                want -= dt.timedelta(days=1)
            assert A.last_us_cutoff(now).date() == want, now
    assert A.US_CLOSE_FINAL == dt.time(16, 30)


def test_cutoff_in_kst_winter_summer_and_weekend():
    assert A.last_us_cutoff(kst(2026, 11, 4, 7, 0)).astimezone(KST) == kst(2026, 11, 4, 6, 30)    # 겨울: 06:30 KST
    assert A.last_us_cutoff(kst(2026, 11, 4, 6, 29)).astimezone(KST) == kst(2026, 11, 3, 6, 30)   # 아직 전이면 하루 전
    assert A.last_us_cutoff(kst(2026, 7, 8, 7, 0)).astimezone(KST) == kst(2026, 7, 8, 5, 30)      # 여름: 05:30 KST
    assert A.last_us_cutoff(kst(2026, 11, 9, 10, 53)).astimezone(KST) == kst(2026, 11, 7, 6, 30)  # 월요일 아침 → 금요일 종가


def test_wait_only_in_the_hours_before_a_weekday_us_close():
    w = A.wait_until(kst(2026, 11, 4, 3, 47))                       # 수요일 03:47 KST = 화요일 13:47 뉴욕
    assert w.astimezone(KST) == kst(2026, 11, 4, 6, 33)
    assert A.wait_until(kst(2026, 11, 4, 5, 13)).astimezone(KST) == kst(2026, 11, 4, 6, 33)
    assert A.wait_until(kst(2026, 7, 8, 3, 47)).astimezone(KST) == kst(2026, 7, 8, 5, 33)      # 여름은 05:33
    for t in (kst(2026, 11, 4, 6, 43), kst(2026, 11, 4, 8, 17), kst(2026, 11, 4, 10, 53), kst(2026, 11, 9, 10, 53),
              kst(2026, 11, 8, 3, 47), kst(2026, 11, 4, 1, 59)):     # 확정 뒤 · 주말(뉴욕 토·일) · 뉴욕 12:00 전
        assert A.wait_until(t) is None, t
    assert A.MAX_WAIT < dt.timedelta(minutes=180)


def data(pub, us="2026-11-03"):
    return {"publishedAt": pub, "usPxDate": us, "pxDate": "2026-11-03"}


def test_decide_on_the_real_week_of_2026_11_03():
    # 11-03 00:09 의 수동 발행(미국은 10-30 = 하루 전 값)은 아침 실행을 막으면 안 돼요
    skip, why = A.decide(data("2026-11-03T00:09:45+09:00", "2026-10-30"), kst(2026, 11, 3, 6, 45))
    assert skip is False and "아직 발행 전" in why
    # 06:43 실행이 미국 11-02 로 발행했으면 뒤의 실행은 모두 건너뛰어요
    for hh, mm in ((8, 17), (10, 53), (13, 37)):
        skip, why = A.decide(data("2026-11-03T06:43:05+09:00", "2026-11-02"), kst(2026, 11, 3, hh, mm))
        assert skip is True and "이미 발행" in why, (hh, mm)
    # 확정 뒤에 시작했는데 야후가 늦어 미국 기준일이 하루 전이면 다시 해요 (미국 휴장일도 이렇게 돼요 — 해롭지 않아요)
    skip, why = A.decide(data("2026-11-03T06:43:05+09:00", "2026-10-30"), kst(2026, 11, 3, 8, 17))
    assert skip is False and "휴장일" in why
    # 11:59 에 시작한 실행의 발행분은 다음 날 아침 실행을 막지 않아요
    assert A.decide(data("2026-11-03T12:00:02+09:00", "2026-11-02"), kst(2026, 11, 4, 6, 43))[0] is False
    # 06:25 에 시작한 실행은 미국 종가 확정 전이었어요 → 뒤의 실행이 다시 해요
    assert A.decide(data("2026-11-04T06:25:00+09:00", "2026-11-02"), kst(2026, 11, 4, 8, 17))[0] is False
    # 토요일 아침 발행(금요일 미국 종가)이 있으면 월요일 백업은 건너뛰어요
    assert A.decide(data("2026-11-07T06:43:00+09:00", "2026-11-06"), kst(2026, 11, 9, 10, 53))[0] is True


@pytest.mark.parametrize("bad", [None, "", "어제", "2026-11-03", "2026-11-03T06:41:05", 12345, "2026-13-40T00:00:00+09:00"])
def test_unreadable_published_at_always_runs(bad):
    skip, why = A.decide(data(bad, "2026-11-02"), kst(2026, 11, 3, 8, 17))
    assert skip is False and "실행해요" in why


@pytest.mark.parametrize("d", [None, [], "x", {}])
def test_unreadable_data_always_runs(d):
    assert A.decide(d, kst(2026, 11, 3, 8, 17))[0] is False


def test_published_at_in_the_future_runs():
    assert A.decide(data("2026-11-03T09:30:00+09:00", "2026-11-02"), kst(2026, 11, 3, 8, 0))[0] is False


class Clock:
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, sec):
        self.slept = sec
        self.t += dt.timedelta(seconds=sec)


def test_main_waits_then_decides_on_the_fresh_main(tmp_path, monkeypatch, capsys):
    out, summary = tmp_path / "out.txt", tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    c = Clock(kst(2026, 11, 4, 3, 47))
    reads = []
    stale = data("2026-11-03T06:43:05+09:00", "2026-11-02")       # 어제 아침 발행분
    assert A.main(c.now, lambda: reads.append(c.t) or stale, c.sleep) is False
    assert c.slept == (166 * 60) and reads == [kst(2026, 11, 4, 6, 33)]        # 기다린 뒤에 main 을 읽어요
    assert out.read_text().strip().splitlines()[-1] == "skip=false" and "실행" in summary.read_text()
    assert "기다렸다가" in capsys.readouterr().out
    # 기다린 뒤 다른 실행이 이미 발행했으면 건너뛰어요
    c = Clock(kst(2026, 11, 4, 5, 13))
    fresh = data("2026-11-04T06:33:30+09:00", "2026-11-03")
    assert A.main(c.now, lambda: fresh, c.sleep) is True
    assert out.read_text().strip().splitlines()[-1] == "skip=true" and "건너뜀" in summary.read_text()


def test_main_never_skips_when_main_cannot_be_read(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    c = Clock(kst(2026, 11, 4, 8, 17))
    assert A.main(c.now, lambda: None, c.sleep) is False
    assert out.read_text().strip().splitlines()[-1] == "skip=false"
    assert not hasattr(c, "slept")


def test_main_gives_up_when_the_wait_is_too_long(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    c = Clock(kst(2026, 11, 4, 3, 30))                              # 13:30 뉴욕: 확정까지 183분 > MAX_WAIT
    assert A.main(c.now, lambda: pytest.fail("읽지 않아야 해요"), c.sleep) is True
    assert not hasattr(c, "slept") and out.read_text().strip() == "skip=true"


def load_workflow():
    with open(os.path.join(ROOT, ".github", "workflows", "update-data.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_schedule_times():
    crons = [c["cron"] for c in load_workflow()[True]["schedule"]]
    assert len(crons) >= 4, crons
    kst_starts = []
    for c in crons:
        minute, hour, dom, mon, dow = c.split()
        m, h = int(minute), int(hour)
        assert m not in (0, 30) and (dom, mon) == ("*", "*"), c          # 정각·30분 피하기
        utc = h * 60 + m
        k = (utc + 9 * 60) % (24 * 60)
        kst_starts.append(k)
        # UTC 15:00 뒤는 한국 날짜가 다음 날: 한국 화~토 = UTC 월~금 · UTC 15:00 전은 한국 날짜와 같아요 (월~토)
        assert dow == ("1-5" if utc >= 15 * 60 else "1-6"), c
        # 기다리는 실행(뉴욕 12:00 전에 시작하면 기다리지 않아요)이라도 MAX_WAIT 안에 확정돼요: 겨울 06:30 KST 기준
        if k < 6 * 60 + 30:
            assert (6 * 60 + 33) - k <= A.MAX_WAIT.total_seconds() / 60, c
        assert k < 15 * 60, c                                              # 한국 장 마감 전에 끝 (다음 날 데이터와 안 섞이게)
    assert min(kst_starts) < 6 * 60 + 30 and any(6 * 60 + 30 < k < 7 * 60 for k in kst_starts)   # 확정 전에 미리 · 확정 직후


def test_check_job_runs_first_and_gates_the_whole_update_job():
    wf = load_workflow()
    check, update = wf["jobs"]["check"], wf["jobs"]["update"]
    assert update["needs"] == "check" and update["if"].replace(" ", "") == "needs.check.outputs.skip!='true'"
    assert check["outputs"]["skip"] == "${{ steps.already.outputs.skip }}"
    assert check["timeout-minutes"] >= A.MAX_WAIT.total_seconds() / 60 + 5
    run = next(s for s in check["steps"] if s.get("id") == "already")["run"]
    assert 'github.event_name }}" != "schedule"' in run and "skip=false" in run          # 수동 실행은 늘 실행
    assert "already_published.py" in run
    # 확인 job 에는 DART·비밀값·캐시·커밋이 없어요
    text = json.dumps(check, ensure_ascii=False)
    for word in ("DART", "secrets", "cache", "git push", "git commit", "fetch_data.py"):
        assert word not in text, word
    # 확인이 실패해도 '건너뜀'이 되지 않아요: 실패하면 skip=false 를 써요
    assert '|| { echo "!! 확인 스크립트가 실패했어요 → 실행해요"; echo "skip=false" >> "$GITHUB_OUTPUT"; }' in run


def test_scheduled_runs_never_start_dart_from_an_empty_cache():
    # 하루 한 번 규칙: 빈 캐시로 시작하는 DART 실행 = 전체 DART 실행. 정해진 시각 실행은 그 전에 멈춰요 (실패로 크게)
    steps = load_workflow()["jobs"]["update"]["steps"]
    names = [s.get("name") or s.get("uses") for s in steps]
    i_restore, i_guard, i_collect = (names.index("DART 캐시 불러오기"), names.index("DART 캐시 확인 (정해진 시각 실행은 빈 캐시로 시작하지 않아요)"),
                                     names.index("데이터 수집"))
    assert i_restore < i_guard < i_collect
    restore, guard = steps[i_restore], steps[i_guard]
    assert restore["id"] == "dart_cache"
    assert guard["if"] == "github.event_name == 'schedule'"
    assert '-z "${{ steps.dart_cache.outputs.cache-matched-key }}"' in guard["run"] and "exit 1" in guard["run"]
