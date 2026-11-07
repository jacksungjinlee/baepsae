# -*- coding: utf-8 -*-
"""v17.5.3: 아침 매일 실행을 여러 시각에 걸고, 이미 발행됐으면 데이터 수집 전에 끝내요 (already_published.py · update-data.yml).

- '다 들어와 있음' = main 의 pxDate · usPxDate 가 한국 · 미국의 마지막 (확정된) 거래일.
- 읽을 수 없거나 이상한 값이면 늘 '실행' (조용히 건너뛰지 않아요) · 수동 실행은 확인하지 않아요.
- 휴장일은 한국·미국 거래일 달력으로 판단해요: 기대 날짜는 마지막 거래일, 미국 휴장일에는 기다리지 않아요.
- 정해진 시각은 모두 정각·30분이 아니고, 새벽 실행은 미국 종가 확정까지 기다려요 (최대 170분).
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


def us_weekdays(start, end, skip=()):
    d, out = start, []
    while d <= end:
        if d.weekday() < 5 and d not in skip:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


D = dt.date
THANKSGIVING = D(2026, 11, 26)
CHUSEOK_SUB = D(2026, 10, 5)            # 시험용 한국 휴장일 (달력에서 빼서 만들어요)


def test_us_rule_without_calendar_matches_the_pipeline_across_both_dst_changes():
    # 달력이 없을 때의 평일 규칙 = fetch_data.us_last_complete_day 의 평일판 (S&P500 마지막 봉과 같은 날)
    import fetch_data as F
    for s0 in (kst(2026, 3, 6, 0, 0), kst(2026, 10, 30, 0, 0)):         # 미국 서머타임 시작(3/8) · 끝(11/1) 앞뒤
        for i in range(0, 6 * 24 * 4):                                 # 6일 동안 15분마다
            now = s0 + dt.timedelta(minutes=15 * i)
            want = F.us_last_complete_day(now)
            while want.weekday() >= 5:
                want -= dt.timedelta(days=1)
            assert A.expected_us(now, None) == want, now
    assert A.US_CLOSE_FINAL == dt.time(16, 30)


def test_expected_dates_follow_the_calendars_on_holidays():
    us = us_weekdays(D(2026, 10, 1), D(2026, 12, 4), skip={THANKSGIVING})
    kr = us_weekdays(D(2026, 9, 1), D(2026, 12, 4), skip={CHUSEOK_SUB})
    # 추수감사절(목) 다음 날 아침: 미국은 수요일이 마지막 거래일 — '늦었다'로 보지 않아요
    assert A.expected_us(kst(2026, 11, 27, 7, 0), us) == D(2026, 11, 25)
    assert A.expected_us(kst(2026, 11, 28, 7, 0), us) == D(2026, 11, 27)
    # 한국 휴장일 다음 날 아침: 한국은 그 전 거래일 (월요일 휴장 → 금요일)
    assert A.expected_kr(kst(2026, 10, 6, 7, 0), kr) == D(2026, 10, 2)
    assert A.expected_kr(kst(2026, 11, 4, 3, 47), kr) == D(2026, 11, 3)
    # 겨울 06:30 KST · 여름 05:30 KST 에 미국 종가가 확정돼요
    assert A.expected_us(kst(2026, 11, 4, 6, 29), us) == D(2026, 11, 2)
    assert A.expected_us(kst(2026, 11, 4, 6, 31), us) == D(2026, 11, 3)
    assert A.expected_us(kst(2026, 7, 8, 5, 31), us_weekdays(D(2026, 6, 1), D(2026, 7, 10))) == D(2026, 7, 7)


def test_wait_only_before_the_close_of_a_us_trading_day():
    us = us_weekdays(D(2026, 10, 1), D(2026, 12, 4), skip={THANKSGIVING})
    assert A.wait_until(kst(2026, 11, 4, 3, 47), us).astimezone(KST) == kst(2026, 11, 4, 6, 33)
    assert A.wait_until(kst(2026, 11, 4, 5, 13), us).astimezone(KST) == kst(2026, 11, 4, 6, 33)
    summer = us_weekdays(D(2026, 6, 1), D(2026, 7, 10))
    assert A.wait_until(kst(2026, 7, 8, 3, 47), summer).astimezone(KST) == kst(2026, 7, 8, 5, 33)
    # 추수감사절 당일(뉴욕 목 13:47 = 한국 금 03:47): 장이 없으니 기다리지 않아요 (야후 정규장 날짜도 금요일)
    assert A.wait_until(kst(2026, 11, 27, 3, 47), us, us_today=D(2026, 11, 27)) is None
    # 오늘 봉이 아직 없어도 야후가 오늘을 정규장 날짜로 주면 거래일이에요
    assert A.wait_until(kst(2026, 11, 4, 3, 47), us_weekdays(D(2026, 10, 1), D(2026, 11, 2)), us_today=D(2026, 11, 3)) is not None
    for t in (kst(2026, 11, 4, 6, 43), kst(2026, 11, 4, 8, 17), kst(2026, 11, 4, 10, 53), kst(2026, 11, 9, 10, 53),
              kst(2026, 11, 8, 3, 47), kst(2026, 11, 4, 1, 59)):     # 확정 뒤 · 주말 · 뉴욕 12:00 전
        assert A.wait_until(t, us) is None, t
    assert A.wait_until(kst(2026, 11, 27, 3, 47), None) is not None    # 달력이 없으면 평일 규칙 (최대 170분이라 끝은 있어요)
    assert A.MAX_WAIT < dt.timedelta(minutes=180)


CAL = {"kr": us_weekdays(D(2026, 10, 1), D(2026, 12, 4), skip={CHUSEOK_SUB}),
       "us": us_weekdays(D(2026, 10, 1), D(2026, 12, 4), skip={THANKSGIVING})}


def data(px, us, pub="2026-11-04T06:40:00+09:00"):
    return {"pxDate": px, "usPxDate": us, "publishedAt": pub}


def test_decide_on_real_and_holiday_mornings():
    # 11-03 00:10 발행분(한국 11-02 · 미국 10-30)은 화요일 아침 실행을 막지 않아요
    skip, why = A.decide(data("2026-11-02", "2026-10-30"), kst(2026, 11, 3, 6, 45), CAL)
    assert skip is False and "기대는 한국 2026-11-02 · 미국 2026-11-02" in why
    # 다 들어온 뒤의 실행은 모두 건너뛰어요
    for hh, mm in ((8, 17), (10, 53), (13, 37)):
        skip, why = A.decide(data("2026-11-03", "2026-11-03"), kst(2026, 11, 4, hh, mm), CAL)
        assert skip is True and "이미 다 들어와" in why and "거래일 달력" in why
    # 야후가 늦어 미국이 하루 전이면 다시 해요
    assert A.decide(data("2026-11-03", "2026-11-02"), kst(2026, 11, 4, 8, 17), CAL)[0] is False
    # 추수감사절 다음 날: 한국 11-26 · 미국 11-25 면 다 들어온 거예요 (뒤의 실행이 같은 데이터를 다시 만들지 않아요)
    assert A.decide(data("2026-11-26", "2026-11-25"), kst(2026, 11, 27, 8, 17), CAL)[0] is True
    assert A.decide(data("2026-11-25", "2026-11-25"), kst(2026, 11, 27, 8, 17), CAL)[0] is False    # 한국 목요일이 빠짐
    # 한국 휴장일 다음 날: 한국 10-02 · 미국 10-05 면 다 들어온 거예요
    assert A.decide(data("2026-10-02", "2026-10-05"), kst(2026, 10, 6, 8, 17), CAL)[0] is True
    # 월요일 백업: 토요일 아침 발행(금요일 종가)이 있으면 건너뛰어요
    assert A.decide(data("2026-11-06", "2026-11-06"), kst(2026, 11, 9, 10, 53), CAL)[0] is True


@pytest.mark.parametrize("d", [None, [], "x", {}, data(None, None), data("2026-11-03", None), data("어제", "2026-11-03")])
def test_unreadable_data_always_runs(d):
    assert A.decide(d, kst(2026, 11, 4, 8, 17), CAL)[0] is False


def test_a_single_korean_calendar_source_never_allows_a_skip():
    # 네이버·야후 중 하나만 답하면 그 출처가 하루 늦을 수 있어요 → 다 들어온 것처럼 보여도 실행해요 (안전한 쪽)
    skip, why = A.decide(data("2026-11-03", "2026-11-03"), kst(2026, 11, 4, 8, 17), {**CAL, "krSources": 1})
    assert skip is False and "한 출처" in why
    assert A.decide(data("2026-11-03", "2026-11-03"), kst(2026, 11, 4, 8, 17), {**CAL, "krSources": 2})[0] is True


def test_without_calendars_the_weekday_rule_never_skips_a_late_day():
    # 달력을 못 받으면 평일 규칙: 추수감사절 다음 날은 미국 목요일을 기대해서 다시 실행해요 (건너뛰지는 않아요)
    skip, why = A.decide(data("2026-11-26", "2026-11-25"), kst(2026, 11, 27, 8, 17), {"kr": None, "us": None})
    assert skip is False and "평일 규칙" in why
    assert A.decide(data("2026-11-03", "2026-11-03"), kst(2026, 11, 4, 8, 17), {"kr": None, "us": None})[0] is True


class Clock:
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, sec):
        self.slept = sec
        self.t += dt.timedelta(seconds=sec)


def fixed_cal(cal=CAL, src="시험 달력"):
    calls = []

    def f():
        calls.append(1)
        return dict(cal), src
    f.calls = calls
    return f


def test_main_waits_then_decides_on_the_fresh_main(tmp_path, monkeypatch, capsys):
    out, summary = tmp_path / "out.txt", tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    c, reads, cal = Clock(kst(2026, 11, 4, 3, 47)), [], fixed_cal()
    assert A.main(c.now, lambda: reads.append(c.t) or data("2026-11-02", "2026-11-02"), cal, c.sleep) is False
    assert c.slept == 166 * 60 and reads == [kst(2026, 11, 4, 6, 33)] and len(cal.calls) == 2   # 기다린 뒤 달력·main 을 다시 읽어요
    assert out.read_text().strip().splitlines()[-1] == "skip=false" and "실행" in summary.read_text()
    assert "기다렸다가" in capsys.readouterr().out
    # 기다리는 동안 다른 실행이 발행했으면 건너뛰어요 (같은 순간에 시작한 두 실행이 둘 다 발행하지 않게)
    c = Clock(kst(2026, 11, 4, 5, 13))
    assert A.main(c.now, lambda: data("2026-11-03", "2026-11-03"), fixed_cal(), c.sleep) is True
    assert out.read_text().strip().splitlines()[-1] == "skip=true" and "건너뜀" in summary.read_text()


def test_main_on_a_us_holiday_does_not_wait(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    c = Clock(kst(2026, 11, 27, 3, 47))                              # 추수감사절 뉴욕 13:47
    cal = fixed_cal({**CAL, "usToday": D(2026, 11, 27)})
    assert A.main(c.now, lambda: data("2026-11-25", "2026-11-25"), cal, c.sleep) is False   # 한국 11-26 이 빠져 실행
    assert not hasattr(c, "slept")
    c = Clock(kst(2026, 11, 27, 3, 47))
    assert A.main(c.now, lambda: data("2026-11-26", "2026-11-25"), fixed_cal({**CAL, "usToday": D(2026, 11, 27)}), c.sleep) is True
    assert not hasattr(c, "slept")


def test_main_never_skips_when_main_cannot_be_read(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    c = Clock(kst(2026, 11, 4, 8, 17))
    assert A.main(c.now, lambda: None, fixed_cal(), c.sleep) is False
    assert out.read_text().strip().splitlines()[-1] == "skip=false" and not hasattr(c, "slept")


def test_main_says_loudly_when_the_calendars_are_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    c = Clock(kst(2026, 11, 4, 8, 17))
    A.main(c.now, lambda: data("2026-11-02", "2026-11-02"), fixed_cal({"kr": None, "us": None}, "없음"), c.sleep)
    assert "!! 거래일 달력을 다 받지 못했어요" in capsys.readouterr().out


def test_main_gives_up_when_the_wait_is_too_long(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    c = Clock(kst(2026, 11, 4, 3, 30))                              # 뉴욕 13:30: 확정까지 183분 > MAX_WAIT
    assert A.main(c.now, lambda: pytest.fail("읽지 않아야 해요"), fixed_cal(), c.sleep) is True
    assert not hasattr(c, "slept") and out.read_text().strip() == "skip=true"


def test_calendars_parse_naver_and_yahoo_and_survive_failures():
    # 시각을 일부러 UTC 날짜가 달라지는 때로: ^KS11 08:00 KST(= 전날 23:00 UTC) · ^GSPC 21:00 뉴욕(= 다음 날 UTC)
    yahoo = lambda days, tz, reg=None: json.dumps({"chart": {"result": [{
        "timestamp": [int(dt.datetime.combine(d, dt.time(8, 0) if tz is KST else dt.time(21, 0), tzinfo=tz).timestamp()) for d in days],
        "indicators": {"quote": [{"close": [1.0] * len(days)}]},
        "meta": {"currentTradingPeriod": {"regular": {"start": int(dt.datetime.combine(reg, dt.time(9, 30), tzinfo=tz).timestamp())}}}
        if reg else {}}]}})
    kr = us_weekdays(D(2026, 10, 1), D(2026, 11, 3), skip={CHUSEOK_SUB})
    us = us_weekdays(D(2026, 10, 1), D(2026, 11, 2))
    naver = "".join(f'<item data="{d:%Y%m%d}|1|1|1|1|1" />' for d in kr)

    def get(url):
        if "naver" in url:
            return naver
        if "KS11" in url:
            return yahoo(kr[:-1], KST)                               # 야후가 하루 늦어도 네이버가 채워요
        return yahoo(us, A.NY, D(2026, 11, 3))
    cal, src = A.calendars(get, sleep=lambda s: None)
    assert cal["kr"] == kr and cal["us"] == us and cal["usToday"] == D(2026, 11, 3) and cal["krSources"] == 2
    assert src == "네이버 KOSPI + 야후 ^KS11 + 야후 ^GSPC"

    def broken(url):
        raise OSError("막힘")
    cal, src = A.calendars(broken, sleep=lambda s: None)
    assert cal == {"kr": None, "us": None, "usToday": None, "krSources": 0} and src == "없음"


def test_read_main_reads_origin_main(monkeypatch):
    seen = []

    class R:
        stdout = json.dumps({"pxDate": "2026-11-03"}).encode()

    def run(cmd, **kw):
        seen.append(cmd)
        return R()
    monkeypatch.setattr(A.subprocess, "run", run)
    assert A.read_main() == {"pxDate": "2026-11-03"}
    assert seen == [["git", "fetch", "--depth=1", "origin", "main"], ["git", "show", "origin/main:data.json"]]


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
        if k < 6 * 60 + 30:                                                 # 기다리는 실행도 MAX_WAIT 안에 (겨울 06:33 KST)
            assert (6 * 60 + 33) - k <= A.MAX_WAIT.total_seconds() / 60, c
        assert k < 15 * 60, c                                              # 한국 장 마감 전
    assert min(kst_starts) < 6 * 60 + 30 and any(6 * 60 + 30 < k < 7 * 60 for k in kst_starts)


def test_check_job_runs_first_and_gates_the_whole_update_job():
    wf = load_workflow()
    check, update = wf["jobs"]["check"], wf["jobs"]["update"]
    assert update["needs"] == "check" and update["if"].replace(" ", "") == "needs.check.outputs.skip!='true'"
    assert check["outputs"]["skip"] == "${{ steps.already.outputs.skip }}"
    assert check["permissions"] == {"contents": "read"}
    assert check["timeout-minutes"] >= A.MAX_WAIT.total_seconds() / 60 + 5
    run = next(s for s in check["steps"] if s.get("id") == "already")["run"]
    assert 'github.event_name }}" != "schedule" ] && [ "${{ inputs.timer }}" != "true"' in run and "skip=false" in run   # 수동 실행은 늘 실행, 바깥 타이머는 확인
    assert "already_published.py" in run
    text = json.dumps(check, ensure_ascii=False)
    for word in ("DART", "secrets", "cache", "git push", "git commit", "fetch_data.py"):
        assert word not in text, word
    assert '|| { echo "!! 확인 스크립트가 실패했어요 → 실행해요"; echo "skip=false" >> "$GITHUB_OUTPUT"; }' in run
    # 같은 그룹(live)에서 하나씩만: 동시에 시작한 두 실행 중 뒤의 것은 기다렸다가 확인 단계에서 끝나요
    assert wf["concurrency"]["cancel-in-progress"] is False and "live" in wf["concurrency"]["group"]
    # 정해진 시각 실행은 지금의 main 을 받아요 (오래된 커밋 위에서 관문·커밋이 돌지 않게)
    co = update["steps"][0]
    assert co["uses"].startswith("actions/checkout") and co["with"]["ref"] == "${{ (github.event_name == 'schedule' || inputs.timer) && 'main' || '' }}"


def test_scheduled_runs_never_start_dart_from_an_empty_cache():
    steps = load_workflow()["jobs"]["update"]["steps"]
    names = [s.get("name") or s.get("uses") for s in steps]
    i_restore, i_guard, i_collect = (names.index("DART 캐시 불러오기"), names.index("DART 캐시 확인 (정해진 시각 실행은 빈 캐시로 시작하지 않아요)"),
                                     names.index("데이터 수집"))
    assert i_restore < i_guard < i_collect
    restore, guard = steps[i_restore], steps[i_guard]
    assert restore["id"] == "dart_cache" and guard["if"] == "github.event_name == 'schedule' || inputs.timer"
    assert '-z "${{ steps.dart_cache.outputs.cache-matched-key }}"' in guard["run"] and "! -s .dart-cache/dart-v3.json.gz" in guard["run"]
    assert "exit 1" in guard["run"]


def test_pipeline_refuses_an_empty_dart_cache_on_scheduled_runs(tmp_path, monkeypatch):
    # 캐시 파일이 있어도 비었거나 형식이 다르면 처음부터 조회 = 전체 DART 실행 → 정해진 시각 실행은 DART 호출 전에 멈춰요
    import fetch_data as F
    import gzip
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    for content in (None, {"v": F.DART_CACHE_VERSION + 1, "entries": {"a|1|2|3": {"st": "000", "at": "2026-11-01", "d": {}}}},
                    {"v": F.DART_CACHE_VERSION, "entries": {}}):
        p = tmp_path / "c.json.gz"
        if p.exists():
            p.unlink()
        if content is not None:
            with gzip.open(p, "wt", encoding="utf-8") as f:
                json.dump(content, f)
        with pytest.raises(RuntimeError, match="DART 캐시가 비어"):
            F.DartClient("k", today=D(2026, 11, 4), path=str(p))
    with gzip.open(tmp_path / "ok.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"v": F.DART_CACHE_VERSION, "entries": {"a|1|2|3": {"st": "000", "at": "2026-11-01", "d": {}}}}, f)
    assert F.DartClient("k", today=D(2026, 11, 4), path=str(tmp_path / "ok.json.gz")).entries
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("BAEPSAE_AUTO_RUN", "1")                                         # 바깥 타이머 실행도 멈춰요 (v17.5.5)
    with pytest.raises(RuntimeError, match="DART 캐시가 비어"):
        F.DartClient("k", today=D(2026, 11, 4), path=str(tmp_path / "none.json.gz"))
    monkeypatch.delenv("BAEPSAE_AUTO_RUN")                                              # 수동 실행은 사람이 정해요
    assert F.DartClient("k", today=D(2026, 11, 4), path=str(tmp_path / "none.json.gz")).entries == {}


def test_outside_timer_runs_follow_the_scheduled_rules():
    """v17.5.5 (Jack, 2026-11-04): cron-job.org 가 workflow_dispatch + timer=true 로 시작한 실행은 정해진 시각 실행과 같아요:
    이미 발행됐으면 확인 단계에서 끝나고, 지금의 main 을 받고, 빈 DART 캐시면 멈추고, main · dart=cache 만 받아요."""
    wf = load_workflow()
    inp = wf[True]["workflow_dispatch"]["inputs"]["timer"]
    assert inp["type"] == "boolean" and inp["default"] is False
    upd = wf["jobs"]["update"]
    assert upd["env"]["TIMER"] == "${{ inputs.timer || false }}"
    check = next(s for s in upd["steps"] if s.get("name") == "입력 확인")["run"]
    for need in ('[ "$TIMER" = "true" ]', '[ "$GITHUB_REF" != "refs/heads/main" ]', '[ "$DART_MODE" != "cache" ]', '[ "$DRY_RUN" = "true" ]',
                 '[ "$BOOTSTRAP" = "true" ]', '[ -n "$PREV_REF" ]', '[ "$SELFTEST" != "none" ]', '[ "$SAMPLE_KR" != "0" ]', "exit 1"):
        assert need in check, need
    collect = next(s for s in upd["steps"] if s.get("name") == "데이터 수집")
    assert collect["env"]["BAEPSAE_AUTO_RUN"] == "${{ (github.event_name == 'schedule' || inputs.timer) && '1' || '' }}"
    # 바깥 타이머는 live 그룹: 정해진 시각 실행과 동시에 시작해도 하나씩 돌고, 뒤의 것은 확인 단계에서 끝나요
    assert "inputs.dry_run" in wf["concurrency"]["group"] and wf["concurrency"]["cancel-in-progress"] is False


def _run_input_check(env):
    """워크플로의 '입력 확인' 단계를 그대로 bash 로 돌려 종료 코드를 봐요 (리뷰 2026-11-04: 문자열만 보면 || 가 && 로 바뀌어도 통과해요)."""
    import subprocess
    step = next(s for s in load_workflow()["jobs"]["update"]["steps"] if s.get("name") == "입력 확인")
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_REF": "refs/heads/main", "GITHUB_REF_NAME": "main",
            "DRY_RUN": "false", "DART_MODE": "cache", "BOOTSTRAP": "false", "PREV_REF": "", "SELFTEST": "none", "SAMPLE_KR": "0",
            "TIMER": "false"}
    return subprocess.run(["bash", "-e", "-c", step["run"]], env={**base, **env}, capture_output=True, text=True).returncode


def test_outside_timer_input_check_really_refuses_everything_but_main_with_cached_dart():
    steps = load_workflow()["jobs"]["update"]["steps"]
    names = [s.get("name") or s.get("uses") for s in steps]
    i_in = names.index("입력 확인")
    assert "if" not in steps[i_in], "입력 확인은 늘 돌아야 해요"
    assert i_in < names.index("DART 캐시 불러오기") < names.index("데이터 수집")
    assert _run_input_check({"TIMER": "true"}) == 0                                    # 바깥 타이머: main · dart=cache
    for bad in ({"GITHUB_REF": "refs/heads/claude/x"}, {"DART_MODE": "full"}, {"DART_MODE": "off"}, {"DRY_RUN": "true"},
                {"BOOTSTRAP": "true"}, {"PREV_REF": "abc"}, {"SELFTEST": "corrupt-price"}, {"SAMPLE_KR": "5"}, {"SAMPLE_KR": "00"}):
        assert _run_input_check({"TIMER": "true", **bad}) == 1, bad
    assert _run_input_check({}) == 0                                                   # 정해진 시각 실행 · 수동 실행은 그대로
    assert _run_input_check({"DART_MODE": "full"}) == 0                                # 수동 dart=full (하루 한 번, 사람이 정해요)

