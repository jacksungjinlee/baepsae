# -*- coding: utf-8 -*-
"""정해진 시각 실행(schedule)의 첫 단계: 아침 데이터가 이미 발행됐는지, 미국 종가가 아직 확정 전인지 보고 실행을 정해요 (v17.5.3).

왜: GitHub 의 정해진 시각 실행은 10월 내내 2시간 15분 ~ 5시간 30분 늦게 시작했어요 (06:30 예정 → 08:44 ~ 12:00 시작).
그래서 같은 매일 실행을 새벽부터 여러 번 걸어 두고:
- 미국 종가 확정(뉴욕 16:30 = 겨울 06:30 · 여름 05:30 KST) 전에 시작한 실행은 확정될 때까지 기다렸다가 실행해요 (최대 MAX_WAIT).
- 이미 발행된 뒤에 시작한 실행은 DART·캐시·데이터 수집 전에 끝나요.
수동 실행(workflow_dispatch)은 이 단계를 쓰지 않아요 (사람이 일부러 누른 실행이에요).

'이미 발행됨' = main 의 data.json 이 (1) publishedAt 이 가장 최근 평일의 미국 종가 확정 시각 이후이고 (2) usPxDate 가 그 날짜예요.
publishedAt 은 실행이 시작된 시각이라 (1)이면 어젯밤 확정된 한국 종가와 그 미국 종가를 쓸 수 있었어요. (2)는 야후가 늦게 준 날을
잡아요 (11-03 00:10 실행처럼 미국 하루 전 값이면 '발행 안 됨'). 한국 쪽은 발행 관문이 '끝난 거래일이 빠지지 않음'을 이미 막아요.
미국 휴장일에는 (2)가 맞지 않아 뒤의 실행도 다시 돌아요 — 같은 데이터를 다시 발행할 뿐 해롭지 않아요 (DART 는 캐시).
읽을 수 없거나 이상한 값이면 늘 '실행'이에요. 어느 쪽이든 이유를 로그에 크게 남겨요. 표준 라이브러리만 써요 (설치 전에 돌아요).

쓰는 법:  python3 already_published.py   → GITHUB_OUTPUT 에 skip=true|false
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
US_CLOSE_FINAL = dt.time(16, 30)           # fetch_data.us_last_complete_day 와 같은 값 (테스트가 맞춰 봐요)
WAIT_FROM = dt.time(12, 0)                 # 뉴욕 평일 12:00 이후(= 한국 새벽)에 시작한 실행만 확정까지 기다려요
AFTER_CLOSE = dt.timedelta(minutes=3)      # 확정 시각 + 3분에 시작해요
MAX_WAIT = dt.timedelta(minutes=170)       # 이보다 오래 기다려야 하면 기다리지 않고 끝내요 (뒤의 실행이 해요). job 한도 안
FUTURE_SLACK = dt.timedelta(minutes=10)    # publishedAt 이 지금보다 이만큼 넘게 미래면 이상한 값


def last_us_cutoff(now):
    """지금 기준 가장 최근의 '평일 미국 종가 확정' 시각 (뉴욕 16:30, 토·일 제외). (순수 함수)"""
    t = now.astimezone(NY)
    d = t.date() if t.time() >= US_CLOSE_FINAL else t.date() - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return dt.datetime.combine(d, US_CLOSE_FINAL, tzinfo=NY)


def wait_until(now):
    """미국 종가 확정 직전(뉴욕 평일 12:00 ~ 16:30)에 시작했으면 기다릴 시각, 아니면 None. (순수 함수)"""
    t = now.astimezone(NY)
    if t.weekday() >= 5 or not (WAIT_FROM <= t.time() < US_CLOSE_FINAL):
        return None
    return dt.datetime.combine(t.date(), US_CLOSE_FINAL, tzinfo=NY) + AFTER_CLOSE


def decide(data, now):
    """main 의 data.json(dict 또는 None) 으로 (건너뛸지, 이유). (순수 함수)"""
    cut = last_us_cutoff(now)
    cut_kst = cut.astimezone(KST).strftime("%m-%d %H:%M KST")
    if not isinstance(data, dict):
        return False, "main 의 data.json 을 읽지 못했어요 → 실행해요"
    pub, usd = data.get("publishedAt"), data.get("usPxDate")
    try:
        p = dt.datetime.fromisoformat(str(pub))
        if p.tzinfo is None:
            raise ValueError("시간대 없음")
    except (TypeError, ValueError) as e:
        return False, f"main 의 publishedAt 을 읽지 못했어요 ({pub!r}: {e}) → 실행해요"
    p_kst = p.astimezone(KST).strftime("%m-%d %H:%M KST")
    if p > now + FUTURE_SLACK:
        return False, f"main 의 publishedAt {p_kst} 가 지금보다 미래예요 (이상한 값) → 실행해요"
    if p < cut:
        return False, f"아직 발행 전이에요: main 의 publishedAt {p_kst} < 미국 종가 확정 {cut_kst} → 실행해요"
    if usd != cut.date().isoformat():
        return False, (f"publishedAt {p_kst} 는 확정 뒤인데 미국 기준일이 {usd!r} 예요 (기대 {cut.date()}, 미국 휴장일이면 정상) "
                       "→ 실행해요")
    return True, f"이미 발행됐어요: publishedAt {p_kst} ≥ 미국 종가 확정 {cut_kst} · 미국 기준일 {usd} → 데이터 수집 전에 끝내요"


def read_main():
    """지금의 origin/main 의 data.json (이 실행이 기다리는 동안 다른 실행이 발행했을 수 있어요). 못 읽으면 None."""
    try:
        subprocess.run(["git", "fetch", "--depth=1", "origin", "main"], check=True, capture_output=True, timeout=120)
        out = subprocess.run(["git", "show", "origin/main:data.json"], check=True, capture_output=True, timeout=60)
        return json.loads(out.stdout.decode("utf-8"))
    except Exception as e:
        print(f"!! main 의 data.json 을 받지 못했어요 ({type(e).__name__}) → 발행 안 됨으로 봐요")
        return None


def main(now_fn=None, read=read_main, sleep=time.sleep):
    now_fn = now_fn or (lambda: dt.datetime.now(dt.timezone.utc))
    now = now_fn()
    until = wait_until(now)
    if until is not None:
        left = until - now
        u_kst = until.astimezone(KST).strftime("%H:%M KST")
        if left > MAX_WAIT:
            skip, why = True, f"미국 종가 확정({u_kst})까지 {int(left.total_seconds() // 60)}분 남아 너무 일러요 → 끝내요 (뒤의 실행이 해요)"
            return finish(skip, why)
        print(f"· 미국 종가가 아직 확정 전이에요 → {u_kst} 까지 {int(left.total_seconds() // 60)}분 기다렸다가 확인해요", flush=True)
        sleep(max(left.total_seconds(), 0))
        now = now_fn()
    skip, why = decide(read(), now)
    return finish(skip, why)


def finish(skip, why):
    print(("· [건너뜀] " if skip else "· ") + why, flush=True)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"skip={'true' if skip else 'false'}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(("**건너뜀** · " if skip else "**실행** · ") + why + "\n")
    return skip


if __name__ == "__main__":
    main()
