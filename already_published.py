# -*- coding: utf-8 -*-
"""정해진 시각 실행(schedule)의 첫 단계: 아침 데이터가 이미 다 들어와 있는지, 미국 종가 확정 전인지 보고 실행을 정해요 (v17.5.3).

왜: GitHub 의 정해진 시각 실행은 10월 내내 2시간 15분 ~ 5시간 30분 늦게 시작했어요 (06:30 예정 → 08:44 ~ 12:00 시작).
그래서 같은 매일 실행을 새벽부터 여러 번 걸어 두고:
- 미국 장이 열린 날, 종가 확정(뉴욕 16:30 = 겨울 06:30 · 여름 05:30 KST) 전에 시작한 실행은 확정 + 3분까지 기다렸다가 실행해요
  (최대 MAX_WAIT). 미국 휴장일에는 기다리지 않아요.
- 데이터가 이미 다 들어와 있으면 DART·캐시·데이터 수집 전에 끝나요.
수동 실행(workflow_dispatch)은 이 단계를 쓰지 않아요 (사람이 일부러 누른 실행이에요).

'다 들어와 있음' = main 의 data.json 이
  pxDate   == 한국 거래일 달력에서 오늘(KST) 전의 마지막 거래일 (그날 종가 최종본은 전날 저녁에 나와요), 그리고
  usPxDate == 미국 거래일 달력에서 종가가 확정된(뉴욕 16:30 이 지난) 마지막 거래일.
달력은 발행 관문과 같은 출처예요: 한국 = 네이버 KOSPI 일봉 + 야후 ^KS11 일봉, 미국 = 야후 ^GSPC 일봉 (fetch_data 가 usPxDate 를
정하는 바로 그 지수). 그래서 한국·미국 휴장일에는 그 전 거래일을 기대하고, 빠진 날을 '늦었다'로 보지 않아요.
달력을 받지 못하면 평일 규칙으로 판단해요 (크게 남겨요): 휴장일이면 같은 데이터를 다시 발행할 수 있지만 건너뛰지는 않아요.
어떤 경우에도 읽을 수 없거나 이상하면 '실행'이에요 — 조용히 건너뛰지 않아요. 표준 라이브러리만 써요 (설치 전에 돌아요).

쓰는 법:  python3 already_published.py   → GITHUB_OUTPUT 에 skip=true|false, 이유는 로그와 실행 요약에
"""
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
US_CLOSE_FINAL = dt.time(16, 30)           # fetch_data.us_last_complete_day 와 같은 값 (테스트가 맞춰 봐요)
WAIT_FROM = dt.time(12, 0)                 # 미국 거래일 뉴욕 12:00 이후(= 한국 새벽)에 시작한 실행만 확정까지 기다려요
AFTER_CLOSE = dt.timedelta(minutes=3)      # 확정 시각 + 3분에 시작해요
MAX_WAIT = dt.timedelta(minutes=170)       # 이보다 오래 기다려야 하면 기다리지 않고 끝내요 (뒤의 실행이 해요). job 한도 안
NAVER_KOSPI = "https://fchart.stock.naver.com/sise.nhn?symbol=KOSPI&timeframe=day&count=30&requestType=0"
YAHOO = "https://query{n}.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=1d"
UA = {"User-Agent": "Mozilla/5.0"}


# ── 달력 ─────────────────────────────────────────────────────
def _get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _yahoo_chart(sym, tz, get=_get):
    """야후 일봉의 (날짜들, 정규장 날짜). 날짜는 그 시장 시간대 기준이고, 장중이면 오늘 봉도 들어 있어요.
    정규장 날짜 = meta.currentTradingPeriod.regular 의 시작 날짜 (장 시작 전에도 오늘이 거래일이면 오늘이에요)."""
    last = None
    for n in (2, 1):
        try:
            res = json.loads(get(YAHOO.format(n=n, sym=sym)))["chart"]["result"][0]
            closes = res["indicators"]["quote"][0]["close"]
            days = sorted({dt.datetime.fromtimestamp(t, tz).date() for t, c in zip(res["timestamp"], closes) if c is not None})
            reg = ((res.get("meta") or {}).get("currentTradingPeriod") or {}).get("regular") or {}
            reg_day = dt.datetime.fromtimestamp(reg["start"], tz).date() if isinstance(reg.get("start"), (int, float)) else None
            return days, reg_day
        except Exception as e:
            last = e
    raise RuntimeError(f"야후 {sym}: {type(last).__name__}")


def _yahoo_dates(sym, tz, get=_get):
    return _yahoo_chart(sym, tz, get)[0]


def _naver_kospi_dates(get=_get):
    return sorted({dt.date(int(m[:4]), int(m[4:6]), int(m[6:8])) for m in re.findall(r'data="(\d{8})\|', get(NAVER_KOSPI))})


def calendars(get=_get, sleep=time.sleep):
    """({"kr": [한국 거래일], "us": [미국 거래일]}, 출처 설명). 한쪽이라도 못 받으면 그 시장은 None (평일 규칙으로)."""
    out, notes = {"kr": None, "us": None, "usToday": None}, []
    kr = set()
    for name, fn in (("네이버 KOSPI", lambda: _naver_kospi_dates(get)), ("야후 ^KS11", lambda: _yahoo_dates("%5EKS11", KST, get))):
        for i in range(3):
            try:
                ds = fn()
                if len(ds) >= 10:
                    kr |= set(ds)
                    notes.append(name)
                    break
            except Exception:
                pass
            if i < 2:
                sleep(i + 1)
    out["kr"] = sorted(kr) or None
    for i in range(3):
        try:
            ds, reg_day = _yahoo_chart("%5EGSPC", NY, get)
            if len(ds) >= 10:
                out["us"], out["usToday"] = ds, reg_day
                notes.append("야후 ^GSPC")
                break
        except Exception:
            pass
        if i < 2:
            sleep(i + 1)
    return out, " + ".join(notes) or "없음"


# ── 규칙 (순수 함수) ─────────────────────────────────────────
def _weekdays_before(d, n=40):
    return [d - dt.timedelta(days=i) for i in range(n, 0, -1) if (d - dt.timedelta(days=i)).weekday() < 5]


def expected_kr(now, kr_days):
    """한국 종가 최종본이 있어야 할 날 = 오늘(KST) 전의 마지막 한국 거래일. 달력이 없으면 전 평일."""
    today = now.astimezone(KST).date()
    days = kr_days if kr_days else _weekdays_before(today)
    past = [d for d in days if d < today]
    return past[-1] if past else None


def expected_us(now, us_days):
    """종가가 확정된(뉴욕 16:30 이 지난) 마지막 미국 거래일. 달력이 없으면 평일로."""
    t = now.astimezone(NY)
    days = us_days if us_days else _weekdays_before(t.date() + dt.timedelta(days=1))
    done = [d for d in days if dt.datetime.combine(d, US_CLOSE_FINAL, tzinfo=NY) <= t]
    return done[-1] if done else None


def wait_until(now, us_days, us_today=None):
    """미국 장이 열린 날, 종가 확정 직전(뉴욕 12:00 ~ 16:30)에 시작했으면 기다릴 시각, 아니면 None.
    달력이 있으면 오늘이 거래일일 때만(오늘 봉이 있거나 야후의 정규장 날짜가 오늘), 없으면 평일만. 휴장일에는 기다리지 않아요."""
    t = now.astimezone(NY)
    if not (WAIT_FROM <= t.time() < US_CLOSE_FINAL):
        return None
    is_session = (t.date() in us_days or us_today == t.date()) if us_days else t.weekday() < 5
    if not is_session:
        return None
    return dt.datetime.combine(t.date(), US_CLOSE_FINAL, tzinfo=NY) + AFTER_CLOSE


def decide(data, now, cal):
    """main 의 data.json(dict 또는 None) 과 달력으로 (건너뛸지, 이유)."""
    kr_want, us_want = expected_kr(now, cal.get("kr")), expected_us(now, cal.get("us"))
    basis = "거래일 달력" if cal.get("kr") and cal.get("us") else "평일 규칙(달력 일부를 받지 못함)"
    if not isinstance(data, dict):
        return False, "main 의 data.json 을 읽지 못했어요 → 실행해요"
    px, usd = data.get("pxDate"), data.get("usPxDate")
    if not (kr_want and us_want):
        return False, f"기대 날짜를 정하지 못했어요 ({basis}) → 실행해요"
    if px == kr_want.isoformat() and usd == us_want.isoformat():
        return True, (f"이미 다 들어와 있어요: 한국 {px} · 미국 {usd} = 기대하는 마지막 거래일 ({basis}) "
                      "→ 데이터 수집 전에 끝내요")
    return False, (f"아직이에요: main 은 한국 {px!r} · 미국 {usd!r}, 기대는 한국 {kr_want} · 미국 {us_want} ({basis}) → 실행해요")


# ── 실행 ─────────────────────────────────────────────────────
def read_main():
    """지금의 origin/main 의 data.json (이 실행이 기다리는 동안 다른 실행이 발행했을 수 있어요). 못 읽으면 None."""
    try:
        subprocess.run(["git", "fetch", "--depth=1", "origin", "main"], check=True, capture_output=True, timeout=120)
        out = subprocess.run(["git", "show", "origin/main:data.json"], check=True, capture_output=True, timeout=60)
        return json.loads(out.stdout.decode("utf-8"))
    except Exception as e:
        print(f"!! main 의 data.json 을 받지 못했어요 ({type(e).__name__}) → 발행 안 됨으로 봐요", flush=True)
        return None


def main(now_fn=None, read=read_main, cals=calendars, sleep=time.sleep):
    now_fn = now_fn or (lambda: dt.datetime.now(dt.timezone.utc))
    cal, src = cals()
    if not (cal.get("kr") and cal.get("us")):
        print(f"!! 거래일 달력을 다 받지 못했어요 (받은 것: {src}) → 못 받은 시장은 평일 규칙으로 판단해요", flush=True)
    else:
        print(f"· 거래일 달력: {src}", flush=True)
    now = now_fn()
    until = wait_until(now, cal.get("us"), cal.get("usToday"))
    if until is not None:
        left = until - now
        u_kst = until.astimezone(KST).strftime("%H:%M KST")
        if left > MAX_WAIT:
            return finish(True, f"미국 종가 확정({u_kst})까지 {int(left.total_seconds() // 60)}분 남아 너무 일러요 → 끝내요 (뒤의 실행이 해요)")
        print(f"· 미국 종가가 아직 확정 전이에요 → {u_kst} 까지 {int(left.total_seconds() // 60)}분 기다렸다가 확인해요", flush=True)
        sleep(max(left.total_seconds(), 0))
        now = now_fn()
        cal, src = cals()                     # 기다리는 동안 오늘 봉이 생겼을 수 있어요 (확정된 미국 거래일)
    return finish(*decide(read(), now, cal))


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
