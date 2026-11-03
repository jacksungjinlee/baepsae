# -*- coding: utf-8 -*-
"""정해진 시각 실행(schedule)의 첫 단계: 오늘 아침 데이터가 이미 발행됐으면 그 실행을 데이터 수집 전에 끝내요 (v17.5.3).

GitHub 의 정해진 시각 실행은 몇 시간씩 늦게 시작하거나 빠지기도 해요 (2026-10-27 ~ 11-03: 06:30 예정이 09:38 ~ 11:59 KST 시작,
11-03 은 11:59). 그래서 같은 매일 실행을 아침 여러 시각에 걸어 두고, 먼저 발행한 실행 뒤의 것은 DART·데이터 수집 전에 끝내요.
수동 실행(workflow_dispatch)은 이 검사를 하지 않아요 (사람이 일부러 누른 실행이에요).

'이미 발행됨' = main 의 data.json publishedAt 이 가장 최근의 미국 종가 확정 시각(뉴욕 16:30, fetch_data.us_last_complete_day 와
같은 기준) 이후예요. publishedAt 은 실행이 시작된 시각이라, 그 뒤에 시작한 실행은 어젯밤 확정된 한국 종가(최종본은 전날 저녁)와
그 미국 종가를 모두 썼어요 (아니면 발행 관문이 막았어요).
읽을 수 없거나 형식이 이상하면 '발행 안 됨'으로 보고 실행을 이어가요 (그다음은 발행 관문이 지켜요). 어느 쪽이든 이유를 로그에 남겨요.

쓰는 법:  python3 already_published.py <main 의 data.json 경로>   → GITHUB_OUTPUT 에 skip=true|false
표준 라이브러리만 써요 (라이브러리 설치 전에 돌아요).
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
US_CLOSE_FINAL = dt.time(16, 30)          # fetch_data.us_last_complete_day 와 같은 값 (테스트가 둘을 맞춰 봐요)
FUTURE_SLACK = dt.timedelta(minutes=10)   # publishedAt 이 지금보다 이만큼 넘게 미래면 이상한 값으로 봐요


def last_us_cutoff(now):
    """지금(now, 시간대 있음) 기준 가장 최근의 '미국 종가 확정' 시각 (뉴욕 16:30). (순수 함수)"""
    t = now.astimezone(NY)
    d = t.date() if t.time() >= US_CLOSE_FINAL else t.date() - dt.timedelta(days=1)
    return dt.datetime.combine(d, US_CLOSE_FINAL, tzinfo=NY)


def decide(published_at, now):
    """(건너뛸지, 이유 한 줄). published_at = main 의 data.json publishedAt 문자열(또는 None). (순수 함수)"""
    cut = last_us_cutoff(now)
    cut_kst = cut.astimezone(KST).strftime("%m-%d %H:%M KST")
    try:
        p = dt.datetime.fromisoformat(str(published_at))
        if p.tzinfo is None:
            raise ValueError("시간대 없음")
    except (TypeError, ValueError) as e:
        return False, f"main 의 publishedAt 을 읽지 못했어요 ({published_at!r}: {e}) → 실행해요"
    p_kst = p.astimezone(KST).strftime("%m-%d %H:%M KST")
    if p > now + FUTURE_SLACK:
        return False, f"main 의 publishedAt {p_kst} 가 지금보다 미래예요 (이상한 값) → 실행해요"
    if p >= cut:
        return True, f"이미 발행됐어요: main 의 publishedAt {p_kst} ≥ 미국 종가 확정 {cut_kst} → 이번 실행은 데이터 수집 전에 끝내요"
    return False, f"아직 발행 전이에요: main 의 publishedAt {p_kst} < 미국 종가 확정 {cut_kst} → 실행해요"


def main(argv, now=None):
    path = argv[1] if len(argv) > 1 else "data.json"
    try:
        with open(path, encoding="utf-8") as f:
            published = json.load(f).get("publishedAt")
    except Exception as e:                       # 파일 없음·깨짐: 실행해요 (발행 관문이 지켜요)
        skip, why = False, f"main 의 data.json 을 읽지 못했어요 ({type(e).__name__}: {e}) → 실행해요"
    else:
        skip, why = decide(published, now or dt.datetime.now(dt.timezone.utc))
    print(("· " if not skip else "· [건너뜀] ") + why)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"skip={'true' if skip else 'false'}\n")
    return skip


if __name__ == "__main__":
    main(sys.argv)
