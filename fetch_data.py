#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
뱁새(Baepsae) 데이터 수집 스크립트 v17.5
──────────────────────────────────────────────────────────────
매일 GitHub Actions 가 실행해 data.json · corp.json · macro.json · disc.json 을 만들고,
validate_data.py 를 통과해야만 커밋(발행)돼요. 파일은 write_json() 한 곳에서만 씁니다.

날짜 (모두 한국 시간)
  pxDate     한국 가격의 공식 종가 날짜 = 오늘 이전 '최종본' 종목 목록 파일의 날짜
  ksDate     KOSPI 시계열의 마지막 날짜 (pxDate 와 같아야 해요)
  usPxDate   미국 가격의 마지막 완성 봉 (S&P500)
  publishedAt 이 실행의 시각 · asOf 는 실행 날짜(참고용)
  macro.curve.date ECOS 마지막 관측일 · disc.newest 가장 최근 공시일

가격
  한국 price = 시가총액 ÷ 상장주식수 (KRX 공식 종가). 목록 파일의 Close 열은 저녁엔 시간외 가격이라 안 써요.
  모든 시계열은 pxDate 까지 자르고, pxDate 값은 공식 종가로 맞춰요 (베타·변동성·수익률도 같은 날 기준).

단위 (한국·미국 같은 단위)
  cap 조원 · val 억원(거래대금) · price 한국 원 / 미국 달러 / 금현물 원/g · 퍼센트는 숫자(%)

수집·계산하는 값
  기본     price cap val lo/hi(52주)
  위험     beta(자기 시장 대비) vol(연 변동성, 원화 기준) mdd(최대 낙폭) hit(상승 월 비율)
  성과     al(3년 알파 %p) sh(3년 샤프) mom(12개월 수익률)
  가치·질  per pbr dy roe debt opm g3(매출성장) frn(외국인)
  분류     s(업종) dk(사업 개요)
  팩터     pz(규모) vz(가치) mz(모멘텀) qz(퀄리티) lz(저변동) — 같은 시장 안에서의 백분위 0~100

시장 가정(도구의 기본값으로 자동 반영)
  rf 국고채 10년(ECOS, 출처는 settings.rfSrc) · mktVol/usVol/mtVol · rhoKrUs/rhoKrMt/rhoUsMt …

DART_API_KEY 로 OpenDART 재무지표·공시를, ECOS_API_KEY 로 국고채 금리를 받아요.
DART 결과는 .dart-cache/ 에 보관해 실행 사이에 다시 씁니다 (하루 한도 보호).
"""

import collections
import copy
import gzip
import io
import json
import math
import os
import sys
import threading
import time
import zipfile
import datetime as dt
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
YEARS = 3                 # 베타·변동성·알파·샤프 계산 기간
MIN_DAYS = 250            # 이보다 데이터가 적으면 통계값 생략
MAX_KR = 2500             # 한국 종목 수 상한(시가총액 순). 늘리면 오래 걸립니다
RF_FALLBACK = 0.03        # 국고채 수익률을 못 받아왔을 때 쓸 값
OUT = "data.json"
OUT_CORP = "corp.json"       # v12: 기업분석용 재무 데이터
OUT_DISC = "disc.json"       # v13: 공시·수급 (내부자 거래 + 국민연금)
OUT_MACRO = "macro.json"     # v14: 금리·원자재
ECOS_KEY = os.environ.get("ECOS_API_KEY", "").strip()
DART_KEY = os.environ.get("DART_API_KEY", "").strip()

EXTRA_US = [
    "SPY", "VOO", "QQQ", "SCHD", "VTI", "VT", "IVV", "DIA", "IWM",
    "SOXX", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
    "TLT", "IEF", "SHY", "GLD", "IAU", "SLV", "JEPI", "JEPQ", "VYM",
    "ARKK", "BRK-B", "TSM", "ASML", "BABA", "NVO", "SHOP",
    "MTUM", "QUAL", "VBR", "IVE", "SPHQ",
]

# v17.5.1: 위 목록 중 ETF·펀드 (나머지 BRK-B·TSM·ASML·BABA·NVO·SHOP 은 실제 회사 주식이에요). 종목마다 직접 정해요.
US_ETFS = frozenset({
    "SPY", "VOO", "QQQ", "SCHD", "VTI", "VT", "IVV", "DIA", "IWM",
    "SOXX", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
    "TLT", "IEF", "SHY", "GLD", "IAU", "SLV", "JEPI", "JEPQ", "VYM",
    "ARKK", "MTUM", "QUAL", "VBR", "IVE", "SPHQ",
})
US_NOT_ETF = frozenset({"BRK-B", "TSM", "ASML", "BABA", "NVO", "SHOP"})
assert US_ETFS | US_NOT_ETF == set(EXTRA_US) and not (US_ETFS & US_NOT_ETF), "EXTRA_US 의 모든 종목은 ETF 여부가 정해져 있어야 해요"
# 한국 목록 파일에 섞여 있는 상장 펀드(투자회사). 업종 '신탁업 및 집합투자업'에는 벤처캐피털·신탁회사 같은
# 진짜 회사도 섞여 있어서(2026-11-01 확인: DSC인베스트먼트, 한국토지신탁 등) 업종이 아니라 종목마다 정해요.
KR_LISTED_FUNDS = {"088980": "맥쿼리인프라", "415640": "KB발해인프라", "094800": "맵스리얼티"}
KR_FUND_INDUSTRY = "신탁업 및 집합투자업"     # 이 업종의 새 종목은 로그로 알려요 (목록에 넣을지 사람이 판단)

KR_INDEX = "KS11"
US_INDEX = "^GSPC"
FX_TICKER = "USDKRW=X"

# ────────────────────────────────────────────────────────────
# 업종 매핑 — KRX 업종분류(한글) → 뱁새 업종 키
# 위에서부터 순서대로 검사하므로, 더 구체적인 키워드를 먼저 둡니다.
# ────────────────────────────────────────────────────────────
SECTOR_RULES = [
    ("semi",      ["반도체", "웨이퍼", "집적회로"]),
    ("battery",   ["2차전지", "이차전지", "축전지"]),
    ("elec",      ["전자부품", "전자장비", "디스플레이", "전기장비", "컴퓨터", "영상음향", "광학", "정밀기기", "가전", "전지"]),
    ("auto",      ["자동차", "차체", "타이어"]),
    ("ship",      ["조선", "선박"]),
    # '항공'만으로 잡으면 항공운송업(항공사)까지 방산으로 들어가므로 좁혀 둡니다.
    ("defense",   ["항공우주", "우주", "국방", "방위", "무기", "항공기", "위성", "미사일",
                   "전차", "잠수함", "탄약", "자주포", "방산", "화약"]),
    ("machine",   ["기계", "장비", "공작", "엔진", "펌프", "베어링"]),
    ("steel",     ["철강", "1차금속", "금속가공", "비철", "주조", "제강"]),
    ("chem",      ["화학", "고무", "플라스틱", "비료", "농약", "도료"]),
    # 유틸리티를 정유·가스보다 먼저 검사합니다. KRX 업종명 "전기, 가스, 증기업" 같은
    # 표기가 '가스'만 보고 정유로 분류되는 것을 막기 위한 순서입니다.
    ("utility",   ["증기", "발전", "배관공급", "수도", "폐기물", "환경", "전력", "재생에너지"]),
    ("energy",    ["석유", "가스", "정제", "연료", "석탄", "원자력"]),
    ("bio",       ["의약", "제약", "생물공학", "바이오"]),
    ("health",    ["의료", "병원", "진단", "치과", "건강"]),
    ("platform",  ["소프트웨어", "인터넷", "포털", "정보서비스", "시스템", "데이터", "통신장비", "프로그래밍", "자료처리"]),
    ("game",      ["게임", "오락"]),
    ("media",     ["방송", "영화", "음악", "출판", "광고", "엔터테인먼트", "공연", "매니지먼트"]),
    ("telecom",   ["통신업", "무선통신", "유선통신", "전기통신"]),
    ("bank",      ["은행", "저축"]),
    ("insure",    ["보험"]),
    ("broker",    ["증권", "자산운용", "금융지원", "신용", "여신"]),
    ("holding",   ["지주", "기타금융"]),
    ("build",     ["건설", "토목", "건축", "설비공사", "시멘트", "레미콘", "유리"]),
    ("realestate", ["부동산", "임대"]),
    ("retail",    ["도매", "소매", "유통", "백화점", "판매", "무역", "상사", "전자상거래"]),
    ("food",      ["식료품", "음료", "담배", "농업", "축산", "어업", "수산", "곡물", "제당", "제분"]),
    ("cosmetic",  ["화장품", "생활용품", "세제", "비누"]),
    ("textile",   ["섬유", "의복", "의류", "가죽", "신발", "봉제"]),
    ("transport", ["운송", "운수", "항만", "물류", "창고", "택배", "해운", "육상", "항공사"]),
    ("edu",       ["교육", "학원"]),
    ("paper",     ["종이", "펄프", "목재", "인쇄", "가구"]),
    ("hotel",     ["숙박", "음식점", "호텔", "여행", "레저", "카지노", "스포츠"]),
]
US_GICS = {
    "technology": "platform", "information technology": "platform",
    "communication services": "media", "consumer cyclical": "retail",
    "consumer discretionary": "retail", "consumer defensive": "food",
    "consumer staples": "food", "healthcare": "bio", "health care": "bio",
    "financial services": "bank", "financials": "bank", "financial": "bank",
    "energy": "energy", "basic materials": "chem", "materials": "chem",
    "industrials": "machine", "utilities": "utility", "real estate": "realestate",
}
US_INDUSTRY = [
    ("semi", ["semiconductor"]),
    ("elec", ["hardware", "electronic", "computer"]),
    ("game", ["gaming"]),
    ("media", ["entertainment", "broadcast", "advertis", "publish", "telecom services"]),
    ("telecom", ["telecom"]),
    ("insure", ["insurance"]),
    ("broker", ["capital market", "asset manage", "financial data", "credit services"]),
    ("bank", ["bank"]),
    ("health", ["medical device", "healthcare plan", "diagnostic", "medical instrument"]),
    ("bio", ["drug", "biotech", "pharmac"]),
    ("auto", ["auto"]),
    ("defense", ["aerospace", "defense"]),
    ("transport", ["airline", "railroad", "trucking", "shipping", "logistic", "marine"]),
    ("steel", ["steel", "aluminum", "copper", "gold", "metal", "mining"]),
    ("build", ["engineering & construction", "building"]),
    ("food", ["beverage", "food", "tobacco", "confection", "farm"]),
    ("cosmetic", ["household", "personal product"]),
    ("textile", ["apparel", "footwear", "luxury"]),
    ("hotel", ["restaurant", "lodging", "resort", "travel", "gambling"]),
    ("retail", ["retail", "specialty", "distribution"]),
    ("platform", ["software", "internet content", "information technology service"]),
]


def log(*a):
    print(*a, flush=True)


def map_sector_kr(sector_text, product_text=""):
    blob = f"{sector_text} {product_text}".replace(" ", "")
    for key, words in SECTOR_RULES:
        for w in words:
            if w in blob:
                return key
    return "etc"


def map_sector_us(sector, industry):
    ind = (industry or "").lower()
    for key, words in US_INDUSTRY:
        for w in words:
            if w in ind:
                return key
    return US_GICS.get((sector or "").lower(), "etc")


def _num(x):
    try:
        v = float(str(x).replace(",", "").strip())
        return v if np.isfinite(v) else None
    except Exception:
        return None


# ────────────────────────────────────────────────────────────
# v17.4.1: 한국 시간 · 안전한 숫자 · 안전한 JSON
# ────────────────────────────────────────────────────────────
KST = ZoneInfo("Asia/Seoul")


def today_kst(now=None):
    """GitHub 러너의 시계는 UTC예요. 날짜는 언제나 한국 시간으로 셉니다."""
    return (now or dt.datetime.now(dt.timezone.utc)).astimezone(KST).date()


def _fin(x):
    """유한한 숫자면 float, 아니면 None (None·NaN·±inf·숫자가 아닌 값 모두).
    `float("nan") or 0` 은 여전히 NaN 이라서, 숫자에는 `x or 0` 대신 이 함수를 씁니다."""
    if x is None or isinstance(x, (bool, np.bool_)):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _json_safe(o, bad):
    if isinstance(o, dict):
        return {k: _json_safe(v, bad) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v, bad) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        v = float(o)
        if math.isfinite(v):
            return v
        bad[0] += 1
        return None
    return o


def write_json(path, obj):
    """data/corp/macro/disc.json 을 쓰는 유일한 길입니다.
    브라우저는 NaN 하나만 있어도 파일 전체를 거부해요. 그래서 NaN·Infinity 는 null 로 바꾸고
    (바꾼 개수는 로그로 남김), allow_nan=False 로 한 번 더 막습니다."""
    bad = [0]
    clean = _json_safe(obj, bad)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, path)
    if bad[0]:
        log(f"  !! {path}: 숫자가 아닌 값(NaN·Infinity) {bad[0]:,}개를 빈 값(null)으로 바꿔 저장했어요")
    return bad[0]


# ────────────────────────────────────────────────────────────
# v17.4.1: KRX 종목 목록 — '최종본' 파일만 씁니다
# ────────────────────────────────────────────────────────────
# FinanceData/fdr_krx_data_cache 는 같은 날짜 파일을 하루에 여러 번 덮어써요.
#   ~05시 장 시작 전: 시가총액이 전부 비어 있음
#   ~13시 장중: 값은 차 있지만 장중 가격
#   16~23시 장 마감 후: 시가총액이 공식 종가로 확정 (Close 열은 시간외 가격이라 쓰지 않아요)
# 그래서 오늘(KST) 이전 날짜 중, 시가총액이 90% 이상 차 있고 마지막 커밋이 그 날짜
# 16:00 KST 이후인 가장 최근 파일을 고릅니다. 주말 파일은 시가총액이 비어 있어 걸러져요.
# v17.5: 18시 → 16시. 4월 이후 거래일 138일 중 29일은 마지막 커밋이 16:13~17:59 였고,
# 그 버전의 시가총액은 밤 23시 버전과 100% 같았어요 (10/20·10/23 비교).
LISTING_URL = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/{d}.csv"
LISTING_COMMITS_API = "https://api.github.com/repos/FinanceData/fdr_krx_data_cache/commits"
LISTING_PATH = "data/listing/krx/{d}.csv"
LISTING_MIN_CAP_SHARE = 0.90
LISTING_FINAL_HOUR = 16
LISTING_LOOKBACK_DAYS = 10
MUST_KR = ("005930", "000660", "005380", "015760", "105560")


def listing_cap_share(df):
    """시가총액이 숫자이고 0보다 큰 행의 비율 (0~1)."""
    if df is None or not len(df) or "Marcap" not in df.columns:
        return 0.0
    m = pd.to_numeric(df["Marcap"], errors="coerce")
    return float((m > 0).sum()) / len(df)


def parse_listing_csv(text):
    df = pd.read_csv(io.StringIO(text), dtype={"Code": str})
    return df.drop(columns=[c for c in df.columns if str(c).startswith("Unnamed")])


def _fetch_listing_csv(d):
    """그 날짜 파일. 없으면(404) None, 세 번 시도해도 못 받으면 예외."""
    last = None
    for attempt in range(3):
        try:
            r = requests.get(LISTING_URL.format(d=d.isoformat()), timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return parse_listing_csv(r.content.decode("utf-8-sig"))
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{d} 파일 다운로드 실패: {last}")


def _listing_commit_kst(d):
    """그 날짜 파일의 마지막 커밋 시각(KST). 확인할 수 없으면 None."""
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    try:
        r = requests.get(LISTING_COMMITS_API, params={"path": LISTING_PATH.format(d=d.isoformat()), "per_page": 1},
                         headers=headers, timeout=20)
        if r.status_code != 200:
            log(f"  !! 커밋 시각 확인 실패: {d} · HTTP {r.status_code} (다음 거래일 파일로 판단해요)")
            return None
        js = r.json()
        if not js:
            return None
        ts = js[0]["commit"]["committer"]["date"]
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST)
    except Exception as e:
        log(f"  !! 커밋 시각 확인 실패: {d} · {e} (다음 거래일 파일로 판단해요)")
        return None


def pick_final_listing(today, fetch_csv, commit_kst, lookback=LISTING_LOOKBACK_DAYS):
    """오늘(KST) 이전의 가장 최근 최종본을 고릅니다. (순수 함수 — 받아오는 방법은 인자로)
    반환: (날짜, DataFrame, 설명, 건너뛴 날짜 메모) · 못 찾으면 날짜·DataFrame 이 None."""
    cache, notes = {}, []

    def get(d):
        if d not in cache:
            try:
                cache[d] = fetch_csv(d)
            except Exception as e:
                cache[d] = None
                notes.append(f"!! {d} 받기 실패({e})")
        return cache[d]

    for back in range(1, lookback + 1):
        d = today - dt.timedelta(days=back)
        df = get(d)
        if df is None:
            continue
        share = listing_cap_share(df)
        if share < LISTING_MIN_CAP_SHARE:
            notes.append(f"{d} 시가총액 {share:.0%} (장 전 파일 또는 휴장일) → 건너뜀")
            continue
        ct = commit_kst(d)
        if ct is not None:
            if ct >= dt.datetime.combine(d, dt.time(LISTING_FINAL_HOUR), KST):
                return d, df, f"{d} 최종본 ({ct:%H:%M} KST 커밋, {len(df):,}종목, 시총 {share:.0%})", notes
            notes.append(f"{d} 마지막 커밋 {ct:%m-%d %H:%M} KST — {LISTING_FINAL_HOUR}시 전이라 최종본이 아님 → 건너뜀")
            continue
        # 커밋 시각을 못 봤으면: 그 뒤 날짜(오늘 포함)에 시가총액이 찬 파일이 있을 때만 '끝난 날'로 봐요
        later = [today - dt.timedelta(days=b) for b in range(0, back)]
        if any(listing_cap_share(get(e)) >= LISTING_MIN_CAP_SHARE for e in later):
            return d, df, (f"{d} 최종본으로 판단 (!! 커밋 시각 확인 불가 · 다음 거래일 파일 있음, "
                           f"{len(df):,}종목, 시총 {share:.0%})"), notes
        notes.append(f"{d} 커밋 시각 확인 불가 · 다음 거래일 파일도 아직 없음 → 건너뜀")
    return None, None, f"최근 {lookback}일 안에 최종본이 없어요", notes


D1_MAX_KR = 30.0          # 한국 하루 가격 제한폭이 ±30% 라 그보다 크면 신규 상장·분할·거래 재개 → 빈 칸 (개수는 로그)
VAL20_DAYS = 20           # 평균 거래대금 기간 (거래일)
VAL20_MIN_DAYS = 10       # 이보다 적은 날만 있으면 (신규 상장 등) 비워 둬요


def kr_recent_sessions(px_date, fetch_csv, commit_kst, n=VAL20_DAYS - 1, lookback=45):
    """기준일 앞의 끝난 거래일 목록 파일들 (최신 → 과거, 최대 n개). (순수 함수 — 받아오는 방법은 인자로)
    반환: (세션 [(날짜, DataFrame)], 메모들, 직전 거래일 파일이 최종본인지).
    직전 거래일 파일은 커밋 시각이 16시 전이면 최종본이 아니라 그날 종가를 믿지 않아요 (d1 을 비워요)."""
    out, notes, prev_final = [], [], None
    for back in range(1, lookback + 1):
        if len(out) >= n:
            break
        d = px_date - dt.timedelta(days=back)
        try:
            df = fetch_csv(d)
        except Exception as e:
            notes.append(f"!! {d} 받기 실패({e})")
            continue
        if df is None:
            continue
        if listing_cap_share(df) < LISTING_MIN_CAP_SHARE:
            continue
        if not out:
            ct = commit_kst(d)
            if ct is not None and ct < dt.datetime.combine(d, dt.time(LISTING_FINAL_HOUR), KST):
                prev_final = False
                notes.append(f"!! 직전 거래일 {d} 파일의 마지막 커밋이 {ct:%m-%d %H:%M} KST — 최종본이 아니라 d1 을 비워요")
            else:
                prev_final = True
                if ct is None:
                    notes.append(f"직전 거래일 {d}: 커밋 시각 확인 불가 · 더 뒤 날짜({px_date}) 최종본이 있어 끝난 날로 봐요")
        out.append((d, df))
    return out, notes, bool(prev_final)


def _official_map(df):
    """종목코드 → 공식 종가 (시가총액 ÷ 상장주식수)."""
    out = {}
    for _, r in df.iterrows():
        c = kr_official_close(r)
        if c:
            out[str(r["Code"]).strip()] = c
    return out


def kr_d1_val20(cur_df, sessions, prev_final, max_abs=D1_MAX_KR, min_days=VAL20_MIN_DAYS):
    """d1 (전 거래일 공식 종가 대비 %) 과 val20 (최근 20거래일 평균 거래대금, 억원). (순수 함수)
    반환: (d1 dict, val20 dict, 집계 Counter)."""
    cnt = collections.Counter()
    cur = _official_map(cur_df)
    d1 = {}
    if sessions and prev_final:
        prev = _official_map(sessions[0][1])
        for code, c in cur.items():
            p = prev.get(code)
            if not p:
                cnt["d1 전일 없음"] += 1
                continue
            v = (c / p - 1) * 100
            if abs(v) > max_abs:
                cnt["d1 범위 밖 → 빈 칸"] += 1
                continue
            d1[code] = round(v, 2)
    amounts = collections.defaultdict(list)
    for df in [cur_df] + [x[1] for x in sessions]:
        a = pd.to_numeric(df["Amount"], errors="coerce") if "Amount" in df.columns else None
        if a is None:
            continue
        for code, v in zip(df["Code"].astype(str).str.strip(), a):
            if v is not None and np.isfinite(v) and v >= 0:
                amounts[code].append(float(v))
    val20 = {}
    for code in cur:
        xs = amounts.get(code, [])
        if len(xs) >= min_days:
            val20[code] = round(sum(xs) / len(xs) / 1e8, 1)
        else:
            cnt["val20 날짜 부족 → 빈 칸"] += 1
    return d1, val20, cnt


def _txt(x):
    """원본 표의 글자. 비었거나 nan·None·'-' 면 빈 문자열 (화면에 'nan' 이 나오지 않게)."""
    if x is None:
        return ""
    if isinstance(x, float) and not np.isfinite(x):
        return ""
    t = str(x).strip()
    return "" if t in ("", "nan", "NaN", "None", "null", "undefined") or t in DASHES else t


def kr_desc_text(industry, products, market, cap):
    """국내 종목 한 줄 설명: '업종 · 주요제품: … · 시장 상장 · 시가총액'. 빈 칸·nan 은 건너뛰어요. (순수 함수)"""
    bits = []
    ind, prod, mk = _txt(industry), _txt(products), _txt(market)
    if ind:
        bits.append(ind)
    if prod:
        bits.append(f"주요제품: {prod}")
    if mk:
        bits.append(f"{mk} 상장")
    if cap:
        bits.append(f"시가총액 {cap:,.1f}조원" if cap >= 1 else f"시가총액 {cap * 10000:,.0f}억원")
    return " · ".join(bits) or None


def select_kr_universe(listing, max_n):
    """시가총액 큰 순으로 max_n 개. 꼭 있어야 할 종목이 빠지면 예외. (순수 함수)
    시가총액이 비면 정렬이 안 돼 가나다순이 남아요(2026-10 사고). 그래서 결과를 꼭 확인합니다."""
    listing = listing.copy()
    for c in ("Marcap", "Amount"):
        listing[c] = pd.to_numeric(listing[c], errors="coerce")
    listing = listing.sort_values("Marcap", ascending=False, na_position="last").head(max_n)
    missing = [c for c in MUST_KR if c not in set(listing["Code"])]
    if missing:
        raise RuntimeError(f"!! 꼭 있어야 할 종목이 목록에 없어요: {', '.join(missing)} — 발행하지 않고 중단합니다")
    return listing


def load_kr_listing(today):
    """(목록 날짜, DataFrame). 못 찾으면 (None, None) — 부르는 쪽이 실행을 멈춥니다."""
    d, df, note, notes = pick_final_listing(today, _fetch_listing_csv, _listing_commit_kst)
    for n in notes:
        log(f"  (종목 목록 {n})")
    if d is None:
        log(f"  !! 종목 목록: {note}")
        return None, None
    loud = any(n.startswith("!!") for n in notes) or "!!" in note
    log(f"{'  !! ' if loud else '· '}종목 목록: {note}"
        + (" — 더 최근 날짜 파일을 받지 못해 이전 날짜를 썼어요" if any(n.startswith("!!") for n in notes) else ""))
    age = (today - d).days
    if age > 4:
        log(f"  !! 종목 목록이 {age}일 전 것이에요 (연휴가 아니라면 원본 저장소가 멈췄을 수 있어요)")
    return d, df


# ────────────────────────────────────────────────────────────
# 통계 계산
# ────────────────────────────────────────────────────────────
def ann_vol(returns):
    if len(returns) < MIN_DAYS:
        return None
    v = float(np.nanstd(returns, ddof=1)) * math.sqrt(252) * 100
    return round(v, 1) if np.isfinite(v) and 0 < v < 300 else None


def beta_alpha(stock_ret, bench_ret, rf):
    df = pd.concat([stock_ret, bench_ret], axis=1).dropna()
    if len(df) < MIN_DAYS:
        return None, None
    y, x = df.iloc[:, 0].values, df.iloc[:, 1].values
    vx = np.var(x, ddof=1)
    if vx <= 0:
        return None, None
    b = float(np.cov(y, x, ddof=1)[0, 1] / vx)
    if not np.isfinite(b) or abs(b) > 5:
        return None, None
    rf_d = rf / 252
    a = float(np.mean(y - rf_d) - b * np.mean(x - rf_d)) * 252 * 100
    if not np.isfinite(a) or abs(a) > 200:
        a = None
    return round(b, 2), (round(a, 1) if a is not None else None)


def perf_stats(px, rf):
    """샤프 · 최대낙폭 · 상승 월 비율 · 12개월 수익률"""
    out = {}
    if len(px) < MIN_DAYS:
        return out
    yrs = len(px) / 252
    try:
        first, last = float(px.iloc[0]), float(px.iloc[-1])
        if first <= 0:
            return out
        cagr = (last / first) ** (1 / yrs) - 1
    except Exception:
        return out
    vol = float(np.nanstd(px.pct_change().dropna().values, ddof=1)) * math.sqrt(252)
    if vol > 0 and np.isfinite(cagr):
        sh = (cagr - rf) / vol
        if np.isfinite(sh) and abs(sh) < 10:
            out["sh"] = round(sh, 2)
    dd = (px / px.cummax() - 1).min()
    if np.isfinite(dd):
        out["mdd"] = round(float(dd) * 100, 1)
    try:
        m = px.resample("ME").last().pct_change().dropna()
        if len(m) >= 12:
            out["hit"] = int(round(float((m > 0).mean()) * 100))
    except Exception:
        pass
    if len(px) > 252:
        base = float(px.iloc[-252])
        if base > 0:
            out["mom"] = round((float(px.iloc[-1]) / base - 1) * 100, 1)
    return out


def add_percentiles(stocks):
    """규모·가치·모멘텀·퀄리티·저변동을 시장 내 백분위(0~100)로 환산.
    v17.5: 한 시장씩만 받아요. 한국·미국을 한데 섞으면 단위도 기준도 달라 점수가 틀어져요
    (예전엔 섞여서 한국 899종목의 가치 점수가 10점 넘게 달라졌어요)."""
    mk = {s.get("cls") for s in stocks}
    if len(mk) > 1:
        raise ValueError(f"add_percentiles 에 여러 시장이 섞였어요: {sorted(map(str, mk))}")
    df = pd.DataFrame({k: pd.to_numeric(pd.Series([_fin(s.get(k)) for s in stocks], dtype="object"), errors="coerce")
                       for k in ("cap", "pbr", "mom", "roe", "vol")})

    def pr(col):
        return df[col].rank(pct=True) * 100

    # 규모는 작을수록, 가치는 PBR 낮을수록 높은 점수 (SMB·HML 방향과 일치)
    # 저변동(lz)은 변동성이 낮을수록 높은 점수
    series = {"pz": 100 - pr("cap"), "vz": 100 - pr("pbr"), "mz": pr("mom"), "qz": pr("roe"), "lz": 100 - pr("vol")}
    for i, s in enumerate(stocks):
        for k, ser in series.items():
            v = ser.iloc[i]
            if pd.notna(v):
                s[k] = int(round(v))
    return stocks


# ────────────────────────────────────────────────────────────
# OpenDART — 호출 · 상태 집계 · 캐시 (v17.5)
# ────────────────────────────────────────────────────────────
# 하루 한도(약 20,000회)에 전체 조회 한 번(약 15,000회)이 거의 닿아요. 그래서 결과를 실행 사이에 보관합니다.
#   키: (기업, 사업연도, 보고서, 재무제표 구분)
#   찾은 보고서(000)는 확정. 다만 90일 넘은 것은 하루 300건씩 다시 확인해요 (정정공시 대비).
#   아직 없음(013)은 7일마다 다시 확인. 제출 마감 7일 전부터 마감 2일 뒤까지는 매일.
#   한도 초과(020)·키 오류는 저장하지 않고 실행을 실패로 끝냅니다.
DART_CACHE_PATH = os.environ.get("DART_CACHE", ".dart-cache/dart-v1.json.gz")
DART_CACHE_VERSION = 1   # parse_dart_* 의 결과 모양이나 해석이 바뀌면 올려요 (캐시는 '해석된 값'을 담아서)
DART_REVALIDATE_DAYS = 90
DART_REVALIDATE_PER_RUN = 300
DART_RETRY_DAYS = 7
REPRT_KO = {"11011": "연간", "11013": "1Q", "11012": "2Q", "11014": "3Q"}
Q_NEWEST_FIRST = ("11014", "11012", "11013")
QUARTER_CURRENT_SHARE = 0.70   # 시가총액 상위 100곳 중 이만큼이 제출해야 그 분기를 '현재'로 봐요
DART_FATAL = {"010": "등록되지 않은 키", "011": "사용할 수 없는 키", "012": "접근할 수 없는 IP",
              "020": "일일 한도 초과", "901": "기간이 끝난 키"}


def report_period_end(year, reprt):
    m, d = {"11013": (3, 31), "11012": (6, 30), "11014": (9, 30), "11011": (12, 31)}[reprt]
    return dt.date(year, m, d)


def report_deadline(year, reprt):
    """제출 마감일 (12월 결산 기준: 분기·반기 45일, 사업보고서 90일)."""
    if reprt == "11011":
        return dt.date(year + 1, 3, 31)
    return {"11013": dt.date(year, 5, 15), "11012": dt.date(year, 8, 14), "11014": dt.date(year, 11, 14)}[reprt]


def dart_entry_due(entry, year, reprt, today, revalidate=False):
    """이 캐시 항목을 오늘 다시 조회해야 하는지. (순수 함수)"""
    if today <= report_period_end(year, reprt):
        return False                     # 기간이 끝나지 않은 보고서는 있을 수 없어요
    if entry is None:
        return True
    if entry["st"] == "000":
        return revalidate
    age = (today - dt.date.fromisoformat(entry["at"])).days
    dl = report_deadline(year, reprt)
    if dl - dt.timedelta(days=7) <= today <= dl + dt.timedelta(days=2):
        return age >= 1
    return age >= DART_RETRY_DAYS


class DartClient:
    """OpenDART 호출을 한곳으로 모읍니다: 상태 코드 집계, 한도 초과 감지, 결과 캐시."""
    BASE = "https://opendart.fss.or.kr/api/"

    def __init__(self, key, mode="cache", today=None, path=DART_CACHE_PATH):
        self.key, self.mode, self.path = key, mode, path
        self.today = today or today_kst()
        self.lock = threading.Lock()
        self.save_lock = threading.Lock()     # 중간 저장이 겹치지 않게
        self.status = collections.Counter()
        self.fatal = None
        self.cache_hits = 0
        self.parse_errors = collections.Counter()
        self.revalidate_left = DART_REVALIDATE_PER_RUN
        self.revalidated = 0
        self.entries, self.meta = {}, {}
        self._load()
        if mode == "full":
            if self.meta.get("lastFull") == self.today.isoformat():
                raise RuntimeError("!! 오늘(KST) 이미 dart=full 로 한 번 실행했어요. 하루 한 번만 쓸 수 있어요 (DART 일일 한도)")
            self.meta["lastFull"] = self.today.isoformat()
            log("· DART 모드: full — 캐시를 무시하고 전부 다시 조회해요")
        old = sum(1 for e in self.entries.values() if e["st"] == "000" and self._stale(e))
        if old:
            log(f"· DART 재확인 대상: 90일 지난 {old:,}건 — 이번 실행에서 쓰는 것 중 최대 {DART_REVALIDATE_PER_RUN}건 (정정공시 대비)")

    def _stale(self, e):
        return (self.today - dt.date.fromisoformat(e["at"])).days > DART_REVALIDATE_DAYS

    def _load(self):
        try:
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                js = json.load(f)
            if js.get("v") != DART_CACHE_VERSION:
                log(f"  !! DART 캐시 형식이 달라요(v{js.get('v')}) → 처음부터 조회")
                return
            self.entries, self.meta = js.get("entries", {}), js.get("meta", {})
            log(f"· DART 캐시 {len(self.entries):,}건 불러옴 (저장 {self.meta.get('savedAt', '?')})")
        except FileNotFoundError:
            log("  !! DART 캐시 없음 → 처음부터 조회해요 (약 15,000회 · 하루 한도의 대부분)")
        except Exception as e:
            log(f"  !! DART 캐시를 읽지 못해 처음부터 조회해요: {e}")

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with self.save_lock:                  # 두 저장이 같은 임시 파일에 섞여 쓰이지 않게
            with self.lock:
                self.meta["savedAt"] = dt.datetime.now(KST).isoformat(timespec="seconds")
                js = {"v": DART_CACHE_VERSION, "meta": dict(self.meta), "entries": dict(self.entries)}
            tmp = self.path + ".tmp"
            with gzip.open(tmp, "wt", encoding="utf-8") as f:
                json.dump(js, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            os.replace(tmp, self.path)

    def get(self, endpoint, params, timeout=25):
        """JSON 응답, 또는 실패하면 None. 상태 코드는 모두 집계해요."""
        if self.fatal:
            return None
        try:
            r = requests.get(self.BASE + endpoint, params={"crtfc_key": self.key, **params}, timeout=timeout)
            j = r.json()
        except Exception:
            with self.lock:
                self.status["예외"] += 1
            return None
        st = str(j.get("status"))
        with self.lock:
            self.status[st] += 1
            if st in DART_FATAL and not self.fatal:
                self.fatal = (st, str(j.get("message") or ""))
        return None if st in DART_FATAL else j

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None):
        """캐시를 거쳐 보고서 하나를 조회합니다. 찾으면 parse 결과, 없으면 None."""
        key = f"{corp}|{year}|{reprt}|{tag}"
        with self.lock:
            e = self.entries.get(key)
            # 찾은 보고서도 90일이 지나면 다시 확인 (정정공시). 실행당 300건까지, 실제로 쓰는 항목만.
            reval = bool(e and e["st"] == "000" and self.mode != "full" and self._stale(e) and self.revalidate_left > 0)
            if reval:
                self.revalidate_left -= 1
                self.revalidated += 1
        due = dart_entry_due(None if self.mode == "full" else e, year, reprt, self.today, revalidate=reval)
        if not due:
            with self.lock:
                self.cache_hits += 1
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        j = self.get(endpoint, {"corp_code": corp, "bsns_year": str(year), "reprt_code": reprt, **(extra or {})})
        if j is None:          # 네트워크 문제·한도 초과: 예전에 찾은 값이 있으면 그대로 (집계에 남아요)
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        st = str(j.get("status"))
        if st == "000":
            try:
                d = parse(j.get("list", []))
            except Exception as ex:          # 이상한 응답 하나가 실행 전체를 멈추지 않게 (개수는 로그로)
                with self.lock:
                    self.parse_errors[type(ex).__name__] += 1
                return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        elif st == "013":
            d = None
        else:                  # 그 밖의 상태(점검 등)는 저장하지 않아요
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        with self.lock:
            self.entries[key] = {"st": st, "at": self.today.isoformat(), "d": d}
        return copy.deepcopy(d)

    def summary(self):
        st = ", ".join(f"{k} {v:,}" for k, v in sorted(self.status.items()))
        extra = f" · 재확인 {self.revalidated:,}건" if self.revalidated else ""
        if self.parse_errors:
            extra += " · !! 해석 오류 " + ", ".join(f"{k} {v}" for k, v in self.parse_errors.items())
        return f"호출 {sum(self.status.values()):,}회 (상태 {st or '없음'}) · 캐시 사용 {self.cache_hits:,}건{extra}"

    def raise_if_fatal(self):
        if self.fatal:
            st, msg = self.fatal
            raise RuntimeError(f"!! DART {DART_FATAL.get(st, st)} (상태 {st}: {msg}) — 재무지표가 비어 발행하지 않고 중단합니다")


def dart_corp_map(client):
    """종목코드 → DART 기업코드. 오늘 못 받으면 캐시에 저장해 둔 목록을 (크게 알리고) 씁니다."""
    try:
        r = requests.get(DartClient.BASE + "corpCode.xml", params={"crtfc_key": client.key}, timeout=90)
        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
        except zipfile.BadZipFile:
            # zip 대신 오류 응답이 와요 (2026-10-09·10 에 이것 때문에 재무지표가 통째로 빠졌어요)
            try:
                j = r.json()
                st = str(j.get("status"))
                with client.lock:
                    client.status[st] += 1
                    if st in DART_FATAL:
                        client.fatal = (st, str(j.get("message") or ""))
                raise RuntimeError(f"zip 대신 오류 응답 (상태 {st}: {j.get('message')})")
            except ValueError:
                raise RuntimeError(f"zip 대신 다른 응답: HTTP {r.status_code} {r.text[:120]!r}")
        root = ET.fromstring(zf.read(zf.namelist()[0]))
        m = {}
        for el in root.iter("list"):
            sc = (el.findtext("stock_code") or "").strip()
            cc = (el.findtext("corp_code") or "").strip()
            if sc and len(sc) == 6 and cc:
                m[sc] = cc
        if len(m) < 2000:
            raise RuntimeError(f"기업코드가 {len(m):,}건뿐이에요")
        with client.lock:
            client.meta["corpMap"], client.meta["corpMapAt"] = m, client.today.isoformat()
        log(f"· DART 기업코드 {len(m):,}건 확보")
        return m
    except Exception as e:
        cached = client.meta.get("corpMap")
        client.raise_if_fatal()
        if cached:
            log(f"  !! DART 기업코드 목록을 받지 못했어요({e}) → 캐시({client.meta.get('corpMapAt')}) {len(cached):,}건을 씁니다")
            return cached
        raise RuntimeError(f"!! DART 기업코드 목록을 받지 못했어요({e}) — 재무지표 없이 발행하지 않고 중단합니다") from None


def parse_dart_list(rows):
    """fnlttSinglAcntAll 응답의 계정 목록에서 3개년 주요 항목을 뽑습니다. (순수 함수 — 테스트 가능)"""
    def tri(row):
        return [_num(row.get("thstrm_amount")), _num(row.get("frmtrm_amount")), _num(row.get("bfefrmtrm_amount"))]
    rev = op = ni = None
    eq = li = nio = eqo = cash = ocf = ca = cl = cs = ie = None
    bor, has_bor = 0.0, False
    dep, has_dep = 0.0, False
    BORROW = {"단기차입금", "장기차입금", "사채", "유동성장기부채", "유동성장기차입금", "단기사채", "전환사채", "리스부채"}
    for row in rows:
        nm = (row.get("account_nm") or "").replace(" ", "")
        sj = (row.get("sj_div") or "").strip()
        if nm in ("매출액", "수익(매출액)", "영업수익") and rev is None:
            rev = tri(row)
        elif nm in ("영업이익", "영업이익(손실)") and op is None:
            op = tri(row)
        elif nm in ("당기순이익", "당기순이익(손실)", "연결당기순이익") and ni is None:
            ni = tri(row)
        elif "지배기업" in nm and "당기순이익" in nm and "비지배" not in nm and nio is None:
            nio = _num(row.get("thstrm_amount"))
        elif nm == "자본총계" and eq is None:
            eq = _num(row.get("thstrm_amount"))
        elif "지배기업" in nm and "자본" in nm and "비지배" not in nm and eqo is None:
            eqo = _num(row.get("thstrm_amount"))
        elif nm in BORROW and sj in ("BS", ""):
            v = _num(row.get("thstrm_amount"))
            if v and v > 0:
                bor += v
                has_bor = True
        elif nm in ("현금및현금성자산", "현금및현금성자산등", "기말현금및현금성자산") and cash is None:
            cash = _num(row.get("thstrm_amount"))
        elif nm == "유동자산" and sj in ("BS", "") and ca is None:
            ca = _num(row.get("thstrm_amount"))
        elif nm == "유동부채" and sj in ("BS", "") and cl is None:
            cl = _num(row.get("thstrm_amount"))
        elif nm == "자본금" and sj in ("BS", "") and cs is None:
            cs = _num(row.get("thstrm_amount"))
        elif nm in ("이자비용", "금융비용") and sj in ("IS", "CIS", "") and ie is None:
            ie = _num(row.get("thstrm_amount"))
        elif sj == "CF" and nm in ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로인한순현금흐름") and ocf is None:
            ocf = _num(row.get("thstrm_amount"))
        elif sj == "CF" and nm in ("감가상각비", "유형자산감가상각비", "무형자산상각비", "사용권자산상각비", "투자부동산감가상각비"):
            v = _num(row.get("thstrm_amount"))
            if v and v > 0:
                dep += v
                has_dep = True
        elif nm == "부채총계" and li is None:
            li = _num(row.get("thstrm_amount"))
    rev = rev or [None, None, None]; op = op or [None, None, None]; ni = ni or [None, None, None]

    out = {}
    if li and eq and eq > 0:
        out["debt"] = round(li / eq * 100, 0)
    if ni[0] and eq and eq > 0:
        out["roe"] = round(ni[0] / eq * 100, 1)
    if op[0] and rev[0]:
        out["opm"] = round(op[0] / rev[0] * 100, 1)
    if rev[0] and rev[0] > 0 and rev[2] and rev[2] > 0:      # 음수 매출이면 제곱근이 복소수가 돼요
        out["g3"] = round(((rev[0] / rev[2]) ** 0.5 - 1) * 100, 1)
    elif rev[0] and rev[1] and rev[1] > 0:
        out["g3"] = round((rev[0] / rev[1] - 1) * 100, 1)

    # v12: 기업분석용 원값(억원 단위, 과거→현재가 아닌 [당기, 전기, 전전기] 순서 유지)
    ek = lambda v: round(v / 1e8, 1) if v is not None else None
    fin = {"rev": [ek(x) for x in rev], "op": [ek(x) for x in op], "ni": [ek(x) for x in ni],
           "eq": ek(eq), "li": ek(li), "nio": ek(nio), "eqo": ek(eqo),
           "bor": ek(bor) if has_bor else None, "cash": ek(cash), "ocf": ek(ocf),
           "dep": ek(dep) if has_dep else None,
           "ca": ek(ca), "cl": ek(cl), "cs": ek(cs), "ie": ek(ie)}
    if any(v is not None for a in (fin["rev"], fin["op"], fin["ni"]) for v in a):
        out["_fin"] = fin
    return out


DASHES = {"-", "－", "—", "–", "‐"}


def _num_or_dash0(x):
    """배당 표의 숫자. 표에 줄은 있는데 값이 '-' 면 '없음' = 0 이에요 (v17.5.1: 0 과 '모름'을 구분)."""
    if x is not None and str(x).strip() in DASHES:
        return 0.0
    return _num(x)


def parse_dart_dividend(rows):
    """alotMatter(배당에 관한 사항) 응답에서 보통주 배당 지표를 뽑습니다. (순수 함수)
    v17.5.1: 주당 배당금 0 원(표에 '-')도 '배당 없음'이라는 사실이라 0 으로 남겨요. 줄 자체가 없으면 '모름'(빈 칸)."""
    dy = dps = None
    dps3 = [None, None, None]
    for row in rows:
        knd = (row.get("stock_knd") or "").strip()
        if knd and knd not in DASHES and "보통" not in knd:     # 종류 칸이 '-' 면 종류 구분이 없는 표 (예: HLB)
            continue
        se = (row.get("se") or "").replace(" ", "")
        v = _num_or_dash0(row.get("thstrm"))
        if v is None:
            continue
        if "주당현금배당금" in se and dps is None:
            dps = v
            dps3 = [_num_or_dash0(row.get("thstrm")), _num_or_dash0(row.get("frmtrm")), _num_or_dash0(row.get("lwfr"))]
        elif "현금배당수익률" in se and dy is None:
            dy = v
    out = {}
    if dps is not None and dps >= 0:
        out["dps"] = round(dps, 0)
        out["dps3"] = [round(x, 0) if x is not None and x >= 0 else None for x in dps3]
    if dy is not None and dy >= 0:      # DART 가 숫자로 알려 준 값만 (0% 도 '배당 없음'이라는 사실이라 그대로 둬요)
        out["dy"] = round(dy, 2)
    return out


def _ytd(row):
    """분기 보고서의 누적값: 누적 컬럼(thstrm_add_amount)이 있으면 그것, 없으면 당기값."""
    v = _num(row.get("thstrm_add_amount"))
    return v if v is not None else _num(row.get("thstrm_amount"))


def parse_dart_quarter(rows):
    """분기·반기 보고서에서 손익/현금흐름 누적값과 시점 재무상태를 뽑습니다."""
    ek = lambda w: round(w / 1e8, 1) if w is not None else None
    rev = op = ni = nio = ocf = ie = None
    eq = eqo = cash = ca = cl = cs = None
    bor, has_bor = 0.0, False
    dep, has_dep = 0.0, False
    BORROW = {"단기차입금", "장기차입금", "사채", "유동성장기부채", "유동성장기차입금", "단기사채", "전환사채", "리스부채"}
    for row in rows:
        nm = (row.get("account_nm") or "").replace(" ", "")
        sj = (row.get("sj_div") or "").strip()
        if sj in ("IS", "CIS"):
            if nm in ("매출액", "수익(매출액)", "영업수익") and rev is None: rev = _ytd(row)
            elif nm == "영업이익" and op is None: op = _ytd(row)
            elif nm in ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익") and ni is None: ni = _ytd(row)
            elif "지배기업" in nm and ("순이익" in nm or "당기순이익" in nm) and "비지배" not in nm and nio is None: nio = _ytd(row)
            elif nm in ("이자비용", "금융비용") and ie is None: ie = _ytd(row)
        elif sj == "CF":
            if nm in ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로인한순현금흐름") and ocf is None:
                ocf = _ytd(row)
            elif nm in ("감가상각비", "유형자산감가상각비", "무형자산상각비", "사용권자산상각비", "투자부동산감가상각비"):
                v = _ytd(row)
                if v and v > 0: dep += v; has_dep = True
        elif sj in ("BS", ""):
            v = _num(row.get("thstrm_amount"))
            if nm == "자본총계" and eq is None: eq = v
            elif "지배기업" in nm and "자본" in nm and "비지배" not in nm and eqo is None: eqo = v
            elif nm in BORROW:
                if v and v > 0: bor += v; has_bor = True
            elif nm in ("현금및현금성자산", "현금및현금성자산등", "기말현금및현금성자산") and cash is None: cash = v
            elif nm == "유동자산" and ca is None: ca = v
            elif nm == "유동부채" and cl is None: cl = v
            elif nm == "자본금" and cs is None: cs = v
    if rev is None and ni is None:
        return None
    return {"rev": ek(rev), "op": ek(op), "ni": ek(ni), "nio": ek(nio), "ocf": ek(ocf), "ie": ek(ie),
            "dep": ek(dep) if has_dep else None,
            "eq": ek(eq), "eqo": ek(eqo), "bor": ek(bor) if has_bor else None, "cash": ek(cash),
            "ca": ek(ca), "cl": ek(cl), "cs": ek(cs)}


def compute_ttm(fin, ytd, ytd_prev):
    """TTM = 직전 연간 + 올해 누적 − 전년 동기 누적. 손익·현금흐름만, 재무상태는 최신 분기 시점값."""
    if not (fin and ytd and ytd_prev):
        return None
    def flow(annual, y, yp):
        if annual is None or y is None or yp is None:
            return None
        return round(annual + y - yp, 1)
    ttm = {"rev": flow((fin.get("rev") or [None])[0], ytd.get("rev"), ytd_prev.get("rev")),
           "op": flow((fin.get("op") or [None])[0], ytd.get("op"), ytd_prev.get("op")),
           "ni": flow((fin.get("ni") or [None])[0], ytd.get("ni"), ytd_prev.get("ni")),
           "nio": flow(fin.get("nio"), ytd.get("nio"), ytd_prev.get("nio")),
           "ocf": flow(fin.get("ocf"), ytd.get("ocf"), ytd_prev.get("ocf")),
           "dep": flow(fin.get("dep"), ytd.get("dep"), ytd_prev.get("dep")),
           "ie": flow(fin.get("ie"), ytd.get("ie"), ytd_prev.get("ie"))}
    if ttm["rev"] is None and ttm["ni"] is None:
        return None
    bs = {k: ytd.get(k) for k in ("eq", "eqo", "bor", "cash", "ca", "cl", "cs") if ytd.get(k) is not None}
    return {"ttm": ttm, "bs": bs}


def dart_financials(client, corp_code, year):
    """연결(없으면 별도) 사업보고서에서 주요 지표 + 3개년 원값."""
    for fs in ("CFS", "OFS"):
        d = client.report("fnlttSinglAcntAll.json", corp_code, year, "11011", fs, parse_dart_list, {"fs_div": fs})
        if d:
            return d
    return {}


def dart_dividend(client, corp_code, year):
    # v17.5.1: 0 원을 남기는 새 해석 → 태그 DIV2 (배당 항목만 한 번 다시 받아요, 약 2,500건. 다른 캐시는 그대로)
    return client.report("alotMatter.json", corp_code, year, "11011", "DIV2", parse_dart_dividend) or {}


def dart_quarter(client, corp_code, year, reprt):
    """분기·반기 보고서의 누적값 (연결 우선, 없으면 별도)."""
    for fs in ("CFS", "OFS"):
        d = client.report("fnlttSinglAcntAll.json", corp_code, year, reprt, fs, parse_dart_quarter, {"fs_div": fs})
        if d:
            return d
    return None


def pick_current_quarter(shares):
    """[(보고서, 상위 100곳 제출 비율)] 최신순 → 70% 이상인 가장 최신 분기 (없으면 None). (순수 함수)"""
    for reprt, share in shares:
        if share >= QUARTER_CURRENT_SHARE:
            return reprt
    return None


def enrich_with_dart(kr_stocks, client):
    """사업보고서·배당·분기보고서(TTM)를 붙입니다. 기업마다 분기를 따로 확인해요 (3Q → 2Q → 1Q)."""
    fin_map = {}
    today = client.today
    cmap = dart_corp_map(client)
    year = today.year - 1
    targets = [s for s in kr_stocks if s["t"] in cmap]
    qy = year + 1
    cands = [r for r in Q_NEWEST_FIRST if report_period_end(qy, r) < today]

    # 1) '현재 분기': 시가총액 상위 100곳 중 70% 이상이 낸 가장 최신 분기
    top = sorted(targets, key=lambda s: -(_fin(s.get("cap")) or 0))[:100]
    shares = []
    for r in cands:
        with ThreadPoolExecutor(max_workers=5) as ex:
            got = list(ex.map(lambda s: dart_quarter(client, cmap[s["t"]], qy, r) is not None, top))
        share = sum(got) / max(len(top), 1)
        shares.append((r, share))
        log(f"· 분기 판단: {qy}.{REPRT_KO[r]} — 시가총액 상위 {len(top)}곳 중 {sum(got)}곳 제출 ({share:.0%})")
        if share >= QUARTER_CURRENT_SHARE:
            break
    if client.fatal:
        client.save()                      # 그때까지 받은 결과는 남겨요
        client.raise_if_fatal()
    q_cur = pick_current_quarter(shares)
    order = cands[cands.index(q_cur):] if q_cur else []
    log(f"· DART 재무지표 조회 {len(targets):,}곳 ({year}년 사업보고서, 없으면 {year - 1}년"
        + (f" + {qy}.{REPRT_KO[q_cur]} 기준 TTM, 없으면 기업마다 이전 분기" if q_cur
           else f" · 70% 넘게 낸 {qy}년 분기가 아직 없어 {year}년 사업보고서가 최근 4개 분기예요")
        + ")…")
    done = [0]
    errors = collections.Counter()

    def one(s):
        if client.fatal:
            return s
        try:
            return one_inner(s)
        except Exception as e:             # 한 기업의 이상한 데이터가 실행 전체를 멈추지 않게 — 개수를 남기고, 채움 비율은 검증이 봐요
            with client.lock:
                errors[f"{type(e).__name__}"] += 1
            return s

    def one_inner(s):
        corp = cmap[s["t"]]
        yr = year
        f = dart_financials(client, corp, yr)
        if not f:
            yr = year - 1
            f = dart_financials(client, corp, yr)
        div = dart_dividend(client, corp, yr)
        for k in ("dps", "dps3", "dy"):
            if div.get(k) is not None:
                s[k] = div[k]
        if f or div:
            s["fy"] = yr          # v17.5.1: op·debt·roe·dps·dps3 가 나온 사업보고서의 연도 (bq 는 TTM 분기만 뜻해요)
        if f:
            fin = f.pop("_fin", None)
            if fin:
                qy_c = yr + 1
                order_c = order if qy_c == qy else [r for r in Q_NEWEST_FIRST if report_period_end(qy_c, r) < today]
                for r in order_c:
                    ytd = dart_quarter(client, corp, qy_c, r)
                    if not ytd:
                        continue
                    t2 = compute_ttm(fin, ytd, dart_quarter(client, corp, yr, r))
                    if t2:
                        fin["ttm"], fin["bs2"], fin["bq"] = t2["ttm"], t2["bs"], f"{qy_c}.{REPRT_KO[r]}"
                        break
                if not fin.get("bq") and yr == year and not order:
                    # 봄(사업보고서 제출 뒤 ~ 1분기 보고서 70% 전)과 연초에는 사업보고서 자체가 '최근 4개 분기'예요
                    fin["bq"] = f"{yr}.4Q"
                fin_map[s["t"]] = fin
            s.update(f)
        with client.lock:
            done[0] += 1
            n = done[0]
        if n % 250 == 0:
            log(f"  … {n:,}/{len(targets):,} · {client.summary()}")
            try:
                client.save()
            except Exception as e:
                log(f"  !! DART 캐시 중간 저장 실패: {e}")
        return s

    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(one, targets))
    client.save()
    log(f"· DART: {client.summary()}")
    try:
        log(f"· DART 캐시 저장: {len(client.entries):,}건 · {os.path.getsize(client.path) / 1e6:.1f}MB ({client.path})")
    except OSError as e:
        log(f"  !! DART 캐시 파일을 확인하지 못했어요: {e}")
    if errors:
        log(f"  !! DART 처리 오류 {sum(errors.values()):,}곳 ({dict(errors)}) — 그 기업은 재무지표 없이 진행해요")
    client.raise_if_fatal()
    got = sum(1 for s in targets if s.get("debt") is not None)
    log(f"· DART 완료: {got:,}곳 재무지표 · {len(fin_map):,}곳 3개년 원값")
    bq = collections.Counter(v.get("bq") or "연간만" for v in fin_map.values())
    ttm_n = sum(1 for v in fin_map.values() if v.get("ttm"))
    log(f"· TTM 합성 성공: {ttm_n:,} / {len(fin_map):,} 기업 ("
        + " · ".join(f"{k} {v:,}" for k, v in sorted(bq.items(), reverse=True)) + ")")
    return kr_stocks, fin_map


# ────────────────────────────────────────────────────────────
# v14: 채권 ETF 블록 — 엄선 목록 + 이름·변동성 검증 (잘못된 티커 방어)
# ────────────────────────────────────────────────────────────
BOND_ETFS = [
    # (티커, 이름에 반드시 포함될 키워드, 표기명, 듀레이션(년), 환헤지, 그룹)
    ("153130", ["단기채"], "KODEX 단기채권", 0.6, True, "단기"),
    ("114260", ["국고채", "3"], "KODEX 국고채3년", 2.6, True, "국고채"),
    ("148070", ["국고채", "10"], "KOSEF 국고채10년", 8.5, True, "국고채"),
    ("439870", ["국고채", "30"], "KODEX 국고채30년액티브", 19.0, True, "국고채"),
    ("273130", ["종합채권"], "KODEX 종합채권(AA-이상)액티브", 5.5, True, "종합"),
    ("305080", ["미국채", "10"], "TIGER 미국채10년선물", 8.5, False, "미국채"),
    ("453850", ["미국", "30", "국채"], "ACE 미국30년국채액티브(H)", 18.0, True, "미국채"),
    # v17.5: 실제 이름은 'KODEX 미국30년국채울트라선물(H)' — 예전 키워드 ["미국채","30"] 에 안 맞아 늘 빠졌어요
    ("304660", ["미국", "30", "울트라"], "KODEX 미국30년국채울트라선물(H)", 20.0, True, "미국채"),
]

# v17.5: 앱에 2025년 내장 가격으로만 있던 종목들 (data.json 에 없어서 늘 옛 가격이 보였어요)
KR_FUNDS = [
    # (티커, 이름 키워드, 표기명, 영문, cls, 업종)
    ("069500", ["200"], "KODEX 200", "KODEX 200", "kr", "index"),
    ("379800", ["미국", "S&P500"], "KODEX 미국S&P500", "KODEX US S&P500", "us", "index"),
    ("132030", ["골드"], "KODEX 골드선물(H)", "KODEX Gold Futures(H)", "metal", "metal"),
    ("144600", ["은"], "KODEX 은선물(H)", "KODEX Silver Futures(H)", "metal", "metal"),
]
GOLD_SPOT = "04020000"     # KRX 금시장 금 99.99K (원/g)
GOLD_SPOT_URL = "https://api.stock.naver.com/marketindex/metals/M04020000/prices"
TROY_OZ_G = 31.1034768


def etf_names():
    import FinanceDataReader as fdr
    names = {}
    try:
        lst = fdr.StockListing("ETF/KR")
        for _, row in lst.iterrows():
            names[str(row.get("Symbol") or row.get("Code") or "")] = str(row.get("Name") or "")
        log(f"· ETF 목록 {len(names):,}개 (이름 확인용)")
    except Exception as e:
        log(f"  !! ETF 목록 확인 실패: {e} — 이름 검증 없이 진행")
    return names


def series_stats(px, bench, rf):
    """원화 시계열 하나로 변동성·베타·52주 범위·낙폭·성과."""
    ret = px.pct_change().dropna()
    out = {"price": round(float(px.iloc[-1]), 0), "vol": ann_vol(ret.values),
           "d1": round(float(px.iloc[-1] / px.iloc[-2] - 1) * 100, 2) if len(px) >= 2 else None,
           "lo": round(float(px.tail(252).min()), 0), "hi": round(float(px.tail(252).max()), 0)}
    jb = pd.concat([ret.rename("b"), bench.rename("m")], axis=1).dropna()
    if len(jb) > 60 and jb["m"].var() > 0:
        out["beta"] = round(float(jb["b"].cov(jb["m"]) / jb["m"].var()), 2)
    out["mdd"] = round(float((px / px.cummax() - 1).min()) * 100, 1)
    out.update(perf_stats(px, rf))
    return out


def kr_fund_series(t, start, px_date):
    """국내 ETF 시계열을 기준일까지. 마지막 값이 기준일이 아니면 None (다른 날 가격이 섞이지 않게)."""
    import FinanceDataReader as fdr
    px = cut_at(fdr.DataReader(t, start, px_date)["Close"].dropna(), px_date)
    if len(px) < 60:
        log(f"  !! {t} 시세 {len(px)}일뿐 — 제외")
        return None
    if px.index[-1].date() != px_date:
        log(f"  !! {t} 마지막 시세가 {px.index[-1]:%Y-%m-%d} 라서 기준일 {px_date} 과 달라요 — 제외")
        return None
    return px


def fetch_bonds(start, px_date, kr_bench, names, rf=RF_FALLBACK):
    """상장 채권 ETF 를 받아 채권 블록 레코드와 블록 대표 수익률(10년 국고 기준)을 만듭니다."""
    recs, proxy = [], None
    for t, kws, label, dur, hedged, grp in BOND_ETFS:
        nm = names.get(t, "")
        if nm and not all(k in nm.replace(" ", "") for k in kws):
            log(f"  !! 채권 ETF {t} 이름 불일치(기대 {kws} ↔ 실제 {nm}) — 제외")
            continue
        try:
            px = kr_fund_series(t, start, px_date)
            if px is None:
                continue
            st = series_stats(px, kr_bench, rf)
            if st["vol"] is not None and st["vol"] > 30:
                log(f"  !! 채권 ETF {t} 변동성 {st['vol']:.0f}% — 채권답지 않아 제외")
                continue
            hj = "환헤지형이라 환율 변동은 막혀 있어요." if hedged else "환노출형이라 달러가 오르면 추가 수익, 내리면 손실이 더해져요."
            dk = (f"{grp} 채권 ETF · 듀레이션 약 {dur:g}년. 금리가 1%p 오르면 대략 {dur:g}% 안팎 하락하는 민감도예요. "
                  + (hj if grp == "미국채" else "") + "채권 ETF 매매차익에는 배당소득세 15.4%가 붙어요.")
            recs.append({
                "t": t, "nk": nm or label, "ne": nm or label, "cls": "bond", "s": "bond", "etf": True,
                "price": st["price"], "vol": st["vol"], "beta": st.get("beta", 0.0), "d1": st.get("d1"),
                "lo": st["lo"], "hi": st["hi"], "mdd": st["mdd"],
                "dy": None, "per": None, "pbr": None, "al": 0,
                "dur": dur, "hedged": hedged, "grp": grp, "dk": dk,
                "x": {"dk": dk, "de": ""},
            })
            if t == "148070":
                proxy = px.pct_change().dropna()
        except Exception as e:
            log(f"  !! 채권 ETF {t} 실패: {e}")
    log(f"· 채권 ETF {len(recs)}종 수집 (설정 {len(BOND_ETFS)}종)"
        + ("" if proxy is not None else " · !! 대표 시계열 없음(블록 상관 생략)"))
    return recs, proxy


def krx_gold_series(start, px_date):
    """KRX 금시장 종가 (원/g) — 네이버 증권 '국내 금' 일별 시세. 60일씩, 최신부터."""
    vals, page = {}, 1
    while page <= 20:
        r = requests.get(GOLD_SPOT_URL, params={"page": page, "pageSize": 60},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        for x in rows:
            d = pd.Timestamp(str(x.get("localTradedAt", ""))[:10])
            v = _num(x.get("closePrice"))
            if v and v > 0:
                vals[d] = v
        if min(vals) <= pd.Timestamp(start):
            break
        page += 1
    px = pd.Series(vals).sort_index()
    return cut_at(px[px.index >= pd.Timestamp(start)], px_date)


def fetch_kr_funds(start, px_date, kr_bench, names, rf, gold_usd=None, fx=None):
    """KODEX 200·미국S&P500·골드선물·은선물 + KRX 금현물. 금현물을 못 받으면 국제 금값 환산(추정, 실시간 아님)."""
    recs = []
    for t, kws, label, label_en, cls, sec in KR_FUNDS:
        nm = names.get(t, "")
        if nm and not all(k in nm.replace(" ", "") for k in kws):
            log(f"  !! {t} 이름 불일치(기대 {kws} ↔ 실제 {nm}) — 제외")
            continue
        try:
            px = kr_fund_series(t, start, px_date)
            if px is None:
                continue
            st = series_stats(px, kr_bench, rf)
            recs.append({"t": t, "nk": nm or label, "ne": label_en, "cls": cls, "s": sec, "fund": True, "etf": True,
                         **st, "src": "KRX"})
        except Exception as e:
            log(f"  !! {t} 실패: {e}")

    gold = None
    try:
        px = krx_gold_series(start, px_date)
        if len(px) >= 250 and px.index[-1].date() == px_date:
            gold = {**series_stats(px, kr_bench, rf), "src": "KRX 금시장"}
            log(f"· KRX 금현물 {gold['price']:,.0f}원/g ({px_date}, {len(px):,}일)")
        else:
            log(f"  !! KRX 금현물 시세가 부족하거나 기준일과 달라요 ({len(px)}일, 마지막 {px.index[-1]:%Y-%m-%d})")
    except Exception as e:
        log(f"  !! KRX 금현물 실패: {e}")
    if gold is None and gold_usd is not None and fx is not None:
        g = (gold_usd * fx.reindex(gold_usd.index).ffill() / TROY_OZ_G).dropna()
        g = cut_at(g, px_date)
        if len(g) >= 250:
            gold = {**series_stats(g, kr_bench, rf), "src": "국제 금값 환산", "est": True}
            if g.index[-1].date() != px_date:
                gold.pop("d1", None)      # 기준일이 아닌 날의 변화는 싣지 않아요
            log(f"  !! 금현물은 국제 금값 환산 추정치로 넣어요 ({gold['price']:,.0f}원/g) — 앱에서 '실시간 아님'으로 표시돼요")
    if gold:
        recs.append({"t": GOLD_SPOT, "nk": "KRX 금현물 (99.99K)", "ne": "KRX Gold Spot", "cls": "metal", "s": "metal",
                     "fund": True, "etf": True, **gold})   # 회사 주식이 아니라서 etf=True (순위·덱에서 빠져요)
    log(f"· 국내 ETF·금현물 {len(recs)}종 ({', '.join(r['t'] for r in recs)})")
    return recs


def _monthly(series, months=36):
    try:
        m = series.dropna().resample("ME").last().tail(months)
        return {"m": [d.strftime("%y.%m") for d in m.index], "v": [round(float(v), 2) for v in m.values]}
    except Exception:
        return None


def parse_ecos_items(rows):
    """817Y002 품목 목록에서 국고채 만기별 + 회사채(AA-) 코드 매핑. (순수 함수)"""
    import re
    out = {}
    for r in rows:
        nm = (r.get("ITEM_NAME") or "").replace(" ", "")
        if "물가연동" in nm:
            continue
        if "회사채" in nm and "AA-" in nm and "corp" not in out:
            out["corp"] = r.get("ITEM_CODE")
            continue
        m = re.search(r"국고채.*?(1|2|3|5|10|20|30)년", nm)
        if m:
            out.setdefault(int(m.group(1)), r.get("ITEM_CODE"))
    return out


ECOS_BASE = "https://ecos.bok.or.kr/api"
ECOS_STAT = "817Y002"   # 시장금리(일별)


def ecos_get(url, tries=3):
    """ECOS 는 새벽 점검 등으로 잠깐 응답이 없을 때가 있어요. 쉬었다가 다시 (5초 → 15초)."""
    last = None
    for i in range(tries):
        try:
            return requests.get(url, timeout=30).json()
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(5 if i == 0 else 15)
    raise RuntimeError(f"ECOS 응답 없음 ({tries}번 시도): {type(last).__name__}")


def ecos_items():
    """817Y002 품목: {만기(년): 코드, "corp": 회사채 AA- 코드}."""
    j = ecos_get(f"{ECOS_BASE}/StatisticItemList/{ECOS_KEY}/json/kr/1/200/{ECOS_STAT}")
    if "RESULT" in j:
        raise RuntimeError(f"ECOS 품목 조회 실패: {j['RESULT']}")
    return parse_ecos_items((j.get("StatisticItemList") or {}).get("row") or [])


def ecos_series(code, start, end):
    """일별 시계열 (날짜 → %). 값이 빈 날은 버려요."""
    u = f"{ECOS_BASE}/StatisticSearch/{ECOS_KEY}/json/kr/1/2000/{ECOS_STAT}/D/{start:%Y%m%d}/{end:%Y%m%d}/{code}"
    j = ecos_get(u)
    if "RESULT" in j:
        raise RuntimeError(f"ECOS {code}: {j['RESULT']}")
    rows = (j.get("StatisticSearch") or {}).get("row") or []
    s = pd.Series([_fin(x.get("DATA_VALUE")) for x in rows],
                  index=pd.to_datetime([x["TIME"] for x in rows], format="%Y%m%d"), dtype="float64")
    return s.dropna()


def fetch_rf(today):
    """무위험수익률 = 국고채 10년 (ECOS). 안 되면 FRED 의 OECD 월간 한국 10년, 그것도 안 되면 기본값.
    반환: (소수, 출처). 출처가 'fallback' 이면 검증에서 실패 처리돼요."""
    if ECOS_KEY:
        try:
            code = ecos_items()[10]
            s = ecos_series(code, today - dt.timedelta(days=30), today)
            v, d = float(s.iloc[-1]), s.index[-1]
            if 0 < v < 20:
                log(f"· 무위험수익률: 국고채 10년 {v:.2f}% (ECOS · {d:%Y-%m-%d})")
                return v / 100, f"ECOS 국고채10년 {d:%Y-%m-%d}"
        except Exception as e:
            log(f"  !! 국고채 10년(ECOS) 실패: {e}")
    else:
        log("  !! ECOS_API_KEY 없음")
    try:
        import FinanceDataReader as fdr
        s = fdr.DataReader("FRED:IRLTLT01KRM156N", today - dt.timedelta(days=400), today).iloc[:, 0].dropna()
        v, d = float(s.iloc[-1]), s.index[-1]
        if 0 < v < 20:
            log(f"  !! 무위험수익률: ECOS 대신 FRED(OECD 월간 한국 10년) {v:.2f}% · {d:%Y-%m}")
            return v / 100, f"FRED IRLTLT01KRM156N {d:%Y-%m}"
    except Exception as e:
        log(f"  !! 무위험수익률 FRED 실패: {e}")
    log(f"  !! 무위험수익률을 받지 못해 기본값 {RF_FALLBACK * 100:.1f}% 를 써요 — 검증에서 실패 처리됩니다")
    return RF_FALLBACK, "fallback"


def fetch_macro(start, end, fx=None):
    """금리·원자재 데이터: 국고채 커브(ECOS)·장단기 금리차·금은유가.
    v17.5: curve.date 는 실행일이 아니라 ECOS 의 마지막 관측일이에요."""
    import FinanceDataReader as fdr
    out = {"asOf": end.isoformat(), "curve": None, "sprKr": None, "sprUs": None,
           "gold": None, "silver": None, "wti": None,
           "g10": None, "tenor": None, "credit": None}
    s3 = end - dt.timedelta(days=365 * 3 + 30)

    # 미국 장단기 + 만기별 (FRED, 키 불필요)
    us_t = {}
    for code, key in (("DGS1", 1), ("DGS3", 3), ("DGS5", 5), ("DGS10", 10), ("DGS2", 2)):
        try:
            us_t[key] = fdr.DataReader("FRED:" + code, s3, end).iloc[:, 0].dropna()
        except Exception as e:
            log(f"  !! FRED {code} 실패: {e}")
    if 10 in us_t and 2 in us_t:
        out["sprUs"] = _monthly((us_t[10] - us_t[2]).dropna())

    # 주요국 10년물 (일본·독일: OECD 월간, FRED 경유)
    g10 = {}
    if 10 in us_t:
        g10["us"] = _monthly(us_t[10])
    for code, key in (("IRLTLT01JPM156N", "jp"), ("IRLTLT01DEM156N", "de")):
        try:
            g10[key] = _monthly(fdr.DataReader("FRED:" + code, s3, end).iloc[:, 0].dropna())
        except Exception as e:
            log(f"  !! {key} 10년물 실패: {e}")

    # 원자재 (yfinance 의 end 는 그날을 빼므로 +1일)
    try:
        import yfinance as yf
        def yfc(tk):
            v = yf.download(tk, start=s3, end=end + dt.timedelta(days=1), progress=False, auto_adjust=True)["Close"]
            return v.iloc[:, 0] if isinstance(v, pd.DataFrame) else v
        if fx is not None:
            fxa = fx.reindex(pd.date_range(s3, end)).ffill()
            g = yfc("GC=F"); out["gold"] = _monthly((g * fxa.reindex(g.index).ffill()).dropna())
            sv = yfc("SI=F"); out["silver"] = _monthly((sv * fxa.reindex(sv.index).ffill()).dropna())
    except Exception as e:
        log(f"  !! 금·은 실패: {e}")
    try:
        out["wti"] = _monthly(fdr.DataReader("FRED:DCOILWTICO", s3, end).iloc[:, 0])
    except Exception as e:
        log(f"  !! WTI 실패: {e}")

    # 국고채 커브 + 한국 장단기 (ECOS)
    if not ECOS_KEY:
        log("  !! ECOS_API_KEY 없음 → 국고채 커브 없음 (검증에서 실패 처리돼요)")
    else:
        try:
            items = ecos_items()
            tenor_codes = {k: v for k, v in items.items() if isinstance(k, int)}
            log(f"· ECOS 품목: 국고채 {sorted(tenor_codes)}년 · 회사채 AA- {'있음' if items.get('corp') else '없음'}")
            series = {}
            for yr, code in sorted(tenor_codes.items()):
                try:
                    srs = ecos_series(code, s3, end)
                    if len(srs):
                        series[yr] = srs
                except Exception as e:
                    log(f"  !! ECOS 국고채 {yr}년 실패: {e}")
            if series:
                tenors = sorted(series)
                last = {yr: series[yr].index[-1] for yr in tenors}
                cdate = min(last.values())
                if len(set(last.values())) > 1:
                    log(f"  !! 국고채 만기별 마지막 관측일이 달라요: { {k: f'{v:%m-%d}' for k, v in last.items()} } → 가장 이른 날 기준")
                ago_target = pd.Timestamp(cdate - pd.Timedelta(days=365))
                now, ago = [], []
                for yr in tenors:
                    srs = series[yr][series[yr].index <= cdate]
                    now.append(round(float(srs.iloc[-1]), 2))
                    i = srs.index.get_indexer([ago_target], method="nearest")[0]
                    ago.append(round(float(srs.iloc[i]), 2))
                out["curve"] = {"tenors": tenors, "now": now, "ago": ago, "date": cdate.strftime("%Y-%m-%d")}
                if 3 in series and 10 in series:
                    out["sprKr"] = _monthly((series[10] - series[3]).dropna())
                if 10 in series:
                    g10["kr"] = _monthly(series[10])
                # 만기별 한·미 금리 (지금 값): [만기, 한국, 미국]
                tn = []
                for yr in (1, 3, 5, 10):
                    k = round(float(series[yr].iloc[-1]), 2) if yr in series else None
                    u = round(float(us_t[yr].iloc[-1]), 2) if yr in us_t else None
                    if k is not None or u is not None:
                        tn.append([yr, k, u])
                if tn:
                    out["tenor"] = tn
                # 신용 스프레드: 회사채 AA- − 국고 3년
                if items.get("corp") and 3 in series:
                    try:
                        cs = (ecos_series(items["corp"], s3, end) - series[3]).dropna()
                        if len(cs) > 60:
                            now_cs = float(cs.iloc[-1])
                            pct = int(round(float((cs < now_cs).mean()) * 100))
                            out["credit"] = dict(_monthly(cs), now=round(now_cs, 2), date=cs.index[-1].strftime("%Y-%m-%d"),
                                                 lo=round(float(cs.min()), 2), hi=round(float(cs.max()), 2), pct=pct)
                    except Exception as e:
                        log(f"  !! 신용 스프레드 실패: {e}")
                log(f"· 국고채 커브 {len(tenors)}개 만기 · 기준 {out['curve']['date']}"
                    + (f" · 신용 스프레드 {out['credit']['now']}%p" if out.get("credit") else " · 신용 스프레드 없음"))
            else:
                log("  !! ECOS 국고채 시계열을 하나도 받지 못했어요")
        except Exception as e:
            log(f"  !! ECOS 조회 실패: {e}")
    if out["curve"] is None:
        keep_prev_ecos(out, g10)
    if g10:
        out["g10"] = g10
    return out


def keep_prev_ecos(out, g10, path=OUT_MACRO):
    """ECOS 를 못 받았으면 지난 발행본의 국고채 커브를 그대로 둬요. 날짜(curve.date)도 그대로라
    화면에는 '○월 ○일 기준'으로 옛 날짜가 보이고, 7일이 넘으면 검증에서 실패해요."""
    try:
        with open(path, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        return
    pc = prev.get("curve") or {}
    if not pc.get("date"):
        return
    for k in ("curve", "sprKr", "tenor", "credit"):
        if prev.get(k) is not None:
            out[k] = prev[k]
    if (prev.get("g10") or {}).get("kr"):
        g10["kr"] = prev["g10"]["kr"]
    out["ecosKept"] = True
    log(f"  !! ECOS 를 받지 못해 지난 발행본의 국고채 커브(기준 {pc['date']})를 그대로 둬요")


# ────────────────────────────────────────────────────────────
# v13: disc.json — 공시·수급 (내부자 거래 + 국민연금), 증분 갱신
# ────────────────────────────────────────────────────────────
DISC_DAYS = 90
DISC_CALL_CAP = 1200   # 1회 실행당 상세조회 상한 (백필은 다음 실행이 이어받음)


def parse_elestock_rows(rows):
    """행 묶음(같은 보고서)에서 대표 행(증감 최대)을 뽑습니다. (순수 함수)"""
    best = None
    for r in rows:
        q = _num(r.get("sp_stock_lmp_irds_cnt"))
        if q is None or q == 0:
            continue
        if best is None or abs(q) > abs(best["q"]):
            best = {"q": int(q),
                    "nm": (r.get("repror") or "").strip(),
                    "pos": (r.get("isu_exctv_ofcps") or r.get("isu_main_shrholdr") or "").strip(),
                    "r": _num(r.get("sp_stock_lmp_rate")),
                    "d": (r.get("rcept_dt") or "").replace("-", "")}
    return best


def parse_elestock_corp(rows, bgn):
    """한 회사의 elestock 응답(여러 보고서의 행들)을 보고서 단위 항목으로 묶습니다."""
    groups = {}
    for r in rows:
        key = r.get("rcept_no") or ((r.get("rcept_dt") or "") + "|" + (r.get("repror") or ""))
        groups.setdefault(key, []).append(r)
    out = []
    for key, grp in groups.items():
        b = parse_elestock_rows(grp)
        if not b or (b["d"] and b["d"] < bgn):
            continue
        out.append({"rc": key, "d": b["d"], "nm": b["nm"], "pos": b["pos"], "q": b["q"], "r": b["r"]})
    return out


def fetch_disclosures(kr_stocks, cmap, end, client):
    """최근 90일 내부자 거래 + 국민연금 대량보유 변동. 기존 disc.json에 증분 병합.
    실패는 조용히 넘기지 않고 상태 코드를 로그로 남깁니다.
    v17.5: newest(가장 최근 공시일)·listOk(목록 조회 성공 여부)를 함께 씁니다. 화면은 실행일이 아니라 newest 를 보여줘요."""
    corp2t = {v: k for k, v in cmap.items()}
    info = {s["t"]: s for s in kr_stocks if s.get("cls") == "kr"}

    prev, known = {"insider": [], "nps": []}, set()
    try:
        with open(OUT_DISC, encoding="utf-8") as f:
            prev = json.load(f)
        known = {r.get("rc") for r in prev.get("insider", []) if r.get("rc")}
    except Exception as e:
        log(f"  !! 지난 disc.json 을 읽지 못했어요({e}) → 내부자 거래를 처음부터 모아요")

    bgn = (end - dt.timedelta(days=89)).strftime("%Y%m%d")  # 조회기간 3개월 제한 안전 마진
    fins_by_corp, nps_corps = {}, {}
    page, stat_note = 1, None
    while page <= 30:
        j = client.get("list.json", {"bgn_de": bgn, "end_de": end.strftime("%Y%m%d"),
                                     "pblntf_ty": "D", "page_no": str(page), "page_count": "100"})
        if j is None or j.get("status") != "000":
            stat_note = f"status={j.get('status')} msg={j.get('message')}" if j else "응답 없음"
            break
        for it in j.get("list", []):
            nm = it.get("report_nm") or ""
            if "임원" in nm and "주요주주" in nm:
                fins_by_corp[it["corp_code"]] = fins_by_corp.get(it["corp_code"], 0) + 1
            if "국민연금" in (it.get("flr_nm") or ""):
                nps_corps[it["corp_code"]] = it
        if page * 100 >= int(j.get("total_count", 0)):
            break
        page += 1
    list_ok = stat_note is None
    log(f"· 공시 목록(list.json): 임원·주요주주 보고 기업 {len(fins_by_corp):,}곳 · 국민연금 관련 {len(nps_corps):,}곳"
        + (f"  !! 목록 조회 중단: {stat_note}" if stat_note else ""))

    targets = [c for c in fins_by_corp if c in corp2t][:DISC_CALL_CAP]
    rows = list(prev.get("insider", []))
    stat_cnt = collections.Counter()

    def one(code):
        j = client.get("elestock.json", {"corp_code": code})
        st = j.get("status") if j else "실패"
        stat_cnt[st] += 1
        if st != "000":
            return []
        t = corp2t.get(code)
        s = info.get(t)
        if not t or not s:
            return []
        out = []
        for e in parse_elestock_corp(j.get("list", []), bgn):
            if e["rc"] in known:
                continue
            price = _fin(s.get("price"))
            amt = round(abs(e["q"]) * price / 1e8, 1) if price else None
            out.append({"rc": e["rc"], "d": e["d"], "t": t, "nk": s["nk"], "s": s.get("s") or "etc",
                        "cap": s.get("cap"), "nm": e["nm"], "pos": e["pos"], "q": e["q"], "r": e["r"], "amt": amt})
        return out
    if targets:
        with ThreadPoolExecutor(max_workers=5) as ex:
            for res in ex.map(one, targets):
                rows.extend(res)
    log(f"· 내부자 상세(elestock): 기업 {len(targets):,}곳 조회 · 상태 {dict(stat_cnt)}")

    rows = [r for r in rows if r.get("d", "") >= bgn]
    rows.sort(key=lambda r: r.get("d", ""), reverse=True)
    seen, dedup, refreshed = set(), [], 0
    for r in rows:
        if r["rc"] in seen:
            continue
        seen.add(r["rc"])
        s = info.get(r.get("t"))
        if s and _fin(r.get("cap")) is None and _fin(s.get("cap")) is not None:
            r["cap"] = s["cap"]      # 예전 실행이 남긴 빈 시가총액을 오늘 값으로 채워요
            refreshed += 1
        dedup.append(r)
    if refreshed:
        log(f"· 내부자 거래 {refreshed:,}건의 비어 있던 시가총액을 오늘 값으로 채움")

    nps, nps_stat = [], collections.Counter()
    for code, it in list(nps_corps.items())[:200]:
        j = client.get("majorstock.json", {"corp_code": code})
        st = j.get("status") if j else "실패"
        nps_stat[st] += 1
        if st != "000":
            continue
        cand = [x for x in j.get("list", []) if "국민연금" in (x.get("repror") or "")]
        if not cand:
            continue
        cand.sort(key=lambda x: (x.get("rcept_dt") or "").replace("-", ""), reverse=True)
        x = cand[0]
        t = corp2t.get(code); s = info.get(t)
        d = (x.get("rcept_dt") or "").replace("-", "")
        if not t or not s or d < bgn:
            continue
        nps.append({"d": d, "t": t, "nk": s["nk"], "s": s.get("s") or "etc", "cap": s.get("cap"),
                    "rt": _num(x.get("stkrt")), "chg": _num(x.get("stkrt_irds"))})
    nps.sort(key=lambda r: r.get("d", ""), reverse=True)
    log(f"· 국민연금(majorstock): 상태 {dict(nps_stat)} · 채택 {len(nps):,}건 · 내부자 누적 {len(dedup):,}건"
        + (" · 상한 도달, 다음 실행이 이어받음" if len(targets) >= DISC_CALL_CAP else ""))
    client.raise_if_fatal()
    ds = [r.get("d") for r in dedup + nps if r.get("d")]
    newest = max(ds) if ds else None
    newest = f"{newest[:4]}-{newest[4:6]}-{newest[6:8]}" if newest else None
    return {"asOf": end.isoformat(), "newest": newest, "listOk": list_ok, "insider": dedup, "nps": nps}


# ────────────────────────────────────────────────────────────
# v12: corp.json — 기업분석 데이터 (멀티플 분포·업종 성장·3개년 재무)
# ────────────────────────────────────────────────────────────
def _quart(vals):
    vals = sorted(v for v in vals if v is not None)
    if len(vals) < 5:
        return None
    q = lambda p: round(float(np.percentile(vals, p)), 2)
    return [q(25), q(50), q(75)]


def _median(vals):
    vals = [v for v in vals if v is not None]
    return round(float(np.median(vals)), 1) if len(vals) >= 5 else None


FIN_SECS = {"bank", "insure", "broker", "holding"}


def build_corp(kr_stocks, fin_map, as_of, market=None):
    """기업분석 탭이 쓰는 corp.json 을 만듭니다. (순수 함수 — 테스트 가능)"""
    comps = []
    for s in kr_stocks:
        if s.get("cls") != "kr" or not s.get("price"):
            continue
        fin = fin_map.get(s["t"], {})
        ni = fin.get("ni") or [None, None, None]
        rev = fin.get("rev") or [None, None, None]
        row = {
            "t": s["t"], "nk": s["nk"], "s": s.get("s") or "etc",
            "price": s["price"], "cap": s.get("cap"),
            "per": s.get("per"), "pbr": s.get("pbr"),
            "eps": s.get("eps"), "bps": s.get("bps"),
            "dy": s.get("dy"), "dps": s.get("dps"), "fy": s.get("fy"),
            "roe": s.get("roe"), "opm": s.get("opm"), "g3": s.get("g3"), "debt": s.get("debt"),
            "beta": s.get("beta"), "vol": s.get("vol"), "lo": s.get("lo"), "hi": s.get("hi"),
            "rev": rev, "op": fin.get("op") or [None, None, None], "ni": ni, "eq": fin.get("eq"),
            "shm": round(s["shr"] / 1e6, 2) if s.get("shr") else None,
            "r1": s.get("r1"), "r3": s.get("r3"), "r36": s.get("r36"), "dps3": s.get("dps3"),
            "pz": s.get("pz"), "vz": s.get("vz"), "mz": s.get("mz"), "qz": s.get("qz"), "lz": s.get("lz"),
            "beta": s.get("beta"), "vol": s.get("vol"), "sh": s.get("sh"), "mdd": s.get("mdd"),
        }
        # TTM·최신 분기 재무상태 우선 (없으면 연간)
        _t = fin.get("ttm") or {}
        _b = fin.get("bs2") or {}
        eff = {
            "rev0": _t.get("rev") if _t.get("rev") is not None else rev[0],
            "op0": _t.get("op") if _t.get("op") is not None else (fin.get("op") or [None])[0],
            "ni0": _t.get("ni") if _t.get("ni") is not None else ni[0],
            "ocf": _t.get("ocf") if _t.get("ocf") is not None else fin.get("ocf"),
            "dep": _t.get("dep") if _t.get("dep") is not None else fin.get("dep"),
            "ie": _t.get("ie") if _t.get("ie") is not None else fin.get("ie"),
            "eq": _b.get("eq") if _b.get("eq") is not None else fin.get("eq"),
            "cs": _b.get("cs") if _b.get("cs") is not None else fin.get("cs"),
            "ca": _b.get("ca") if _b.get("ca") is not None else fin.get("ca"),
            "cl": _b.get("cl") if _b.get("cl") is not None else fin.get("cl"),
            "bor": _b.get("bor") if _b.get("bor") is not None else fin.get("bor"),
            "cash": _b.get("cash") if _b.get("cash") is not None else fin.get("cash"),
        }
        if fin.get("bq"):
            row["bq"] = fin["bq"]

        # 재무 건전성 신호 (해당할 때만 필드 존재 — 판단이 아니라 사실 표시)
        fl = {}
        if eff["ca"] and eff["cl"] and eff["cl"] > 0 and row["s"] not in FIN_SECS:
            cr = eff["ca"] / eff["cl"] * 100
            if cr < 100:
                fl["cr"] = round(cr, 0)
        op0f = eff["op0"]
        if op0f is not None and eff["ie"] and eff["ie"] > 0 and row["s"] not in FIN_SECS:
            icr = op0f / eff["ie"]
            if icr < 1:
                fl["icr"] = round(icr, 2)
        if all(v is not None and v < 0 for v in ni):
            fl["l3"] = 1
        if eff["cs"] and eff["eq"] is not None and eff["eq"] < eff["cs"]:
            fl["imp"] = 1
        if fl:
            row["fl"] = fl

        # EV 계열·현금흐름 멀티플 (금융업은 EV 지표가 무의미하므로 제외)
        op0 = eff["op0"]
        ebitda = (op0 + eff["dep"]) if (op0 is not None and eff["dep"] is not None) else None
        if s.get("cap") and fin:
            ev = s["cap"] * 1e4 + (_fin(eff["bor"]) or 0.0) - (_fin(eff["cash"]) or 0.0)
            if row["s"] not in FIN_SECS and ev > 0:
                if ebitda and ebitda > 0:
                    v = ev / ebitda
                    if 0 < v < 200:
                        row["evE"] = round(v, 1)
                if eff["rev0"] and eff["rev0"] > 0:
                    v = ev / eff["rev0"]
                    if 0 < v < 100:
                        row["evR"] = round(v, 2)
            ocf = eff["ocf"]
            if ocf and ocf > 0:
                v = s["cap"] * 1e4 / ocf
                if 0 < v < 200:
                    row["pcf"] = round(v, 1)
        # DCF 자동 채움 가능 여부: 당기 순이익 존재 + 시총(→주식수 역산) 존재
        row["dcfReady"] = bool(ni[0] is not None and (s.get("shr") or s.get("cap")))
        comps.append(row)

    sectors = {}
    by_sec = {}
    for c in comps:
        by_sec.setdefault(c["s"], []).append(c)
    for sec, arr in by_sec.items():
        # 업종 성장률: 개별 평균이 아니라 '합산 매출' 기준 (소형주 과대표집 방지)
        pairs = [(c["rev"][0], c["rev"][2]) for c in arr if c["rev"][0] and c["rev"][2] and c["rev"][2] > 0]
        g = None
        if len(pairs) >= 5:
            r0 = sum(p[0] for p in pairs); r2 = sum(p[1] for p in pairs)
            if r2 > 0 and r0 > 0:      # 합산 매출이 음수면 제곱근이 복소수가 돼요
                g = round(((r0 / r2) ** 0.5 - 1) * 100, 1)
        sectors[sec] = {
            "n": len(arr), "nG": len(pairs), "g": g,
            "rev0": round(sum(c["rev"][0] for c in arr if c["rev"][0]) / 1e4, 1),   # 조원
            "opm": _median([c["opm"] for c in arr]),
            "roe": _median([c["roe"] for c in arr]),
            "perQ": _quart([c["per"] for c in arr if c["per"] and 0 < c["per"] < 200]),
            "pbrQ": _quart([c["pbr"] for c in arr if c["pbr"] and 0 < c["pbr"] < 20]),
            "evEQ": _quart([c.get("evE") for c in arr if c.get("evE") and 0 < c["evE"] < 60]),
            "evRQ": _quart([c.get("evR") for c in arr if c.get("evR") and 0 < c["evR"] < 30]),
            "pcfQ": _quart([c.get("pcf") for c in arr if c.get("pcf") and 0 < c["pcf"] < 60]),
            "mc": round(sum(c["cap"] for c in arr if c["cap"]), 1),                 # 조원
        }
    return {"asOf": as_of, "market": market or {}, "sectors": sectors, "companies": comps}


# ────────────────────────────────────────────────────────────
# 한국
# ────────────────────────────────────────────────────────────
def kr_official_close(row):
    """공식 종가 = 시가총액 ÷ 상장주식수 (원).
    목록 파일의 Close 열은 저녁 버전에서 시간외(넥스트레이드) 가격으로 바뀌어요. 시가총액은 KRX 공식 종가로
    계산돼 있어서, 다음 날 파일의 '전일 대비' 기준가와 정확히 맞아요 (2026-10-27~29 삼성전자로 확인)."""
    mc, sh = _fin(row.get("Marcap")), _fin(row.get("Stocks"))
    if not mc or not sh or mc <= 0 or sh <= 0:
        return None
    return float(round(mc / sh))


def cut_at(px, last_date):
    """last_date 보다 뒤(장중·다음 날) 값을 버려요."""
    return px[px.index <= pd.Timestamp(last_date)]


def pin_close(px, px_date, close):
    """시계열의 px_date 값을 공식 종가로 맞춥니다. 반환: (시계열, 'same'|'fixed'|'added')."""
    px = cut_at(px, px_date)
    ts = pd.Timestamp(px_date)
    if len(px) and px.index[-1] == ts:
        if float(px.iloc[-1]) == close:
            return px, "same"
        px = px.copy()
        px.iloc[-1] = close
        return px, "fixed"
    return pd.concat([px, pd.Series([close], index=[ts])]), "added"


def listing_from_prev(prev):
    """마지막 수단: 지난 data.json 으로 종목 뼈대를 만들어요. 공식 종가는 없으니 검증에서 실패 처리됩니다.
    두 번 연속이면 바로 멈춰요."""
    if not prev:
        raise RuntimeError("!! 최종본 종목 목록도, 지난 data.json 도 없어요 — 발행하지 않고 중단합니다")
    if str(prev.get("listSrc", "")).startswith("prev"):
        raise RuntimeError("!! 지난 실행도 종목 목록 대신 지난 data.json 을 썼어요. 두 번 연속이라 중단합니다")
    rows = []
    for x in prev.get("stocks", []):
        if x.get("cls") != "kr" or not x.get("t"):
            continue
        cap, val = _fin(x.get("cap")), _fin(x.get("val"))
        rows.append({"Code": x["t"], "Name": x.get("nk") or x["t"], "Market": "",
                     "Marcap": cap * 1e12 if cap else None, "Stocks": x.get("shr"),
                     "Amount": val * 1e8 if val is not None else None, "_prev_s": x.get("s")})
    if len(rows) < 300:
        raise RuntimeError(f"!! 지난 data.json 의 국내 종목이 {len(rows)}개뿐이에요 — 중단합니다")
    log(f"  !! 종목 목록 원본을 못 받아 지난 data.json 의 {len(rows):,}개로 대신해요. 공식 종가가 없어 발행되지 않아요")
    return pd.DataFrame(rows)


def fetch_korea(start, today, rf, prev=None):
    """국내 주식: 최종본 목록 → 공식 종가 → pxDate 까지 자른 시계열로 위험·성과 지표.
    반환: (종목들, KOSPI 수익률, 시장 요약, 메타{pxDate, ksDate, listSrc})."""
    import FinanceDataReader as fdr

    log("· KRX 종목 목록…")
    px_date, listing = load_kr_listing(today)
    list_src = "fdr_krx_data_cache"
    if listing is None:
        listing, list_src = listing_from_prev(prev), "prev-data.json"
    code_col = next((c for c in ("Code", "Symbol", "ShortCode", "종목코드") if c in listing.columns), None)
    if code_col is None:
        raise RuntimeError(f"종목코드 열을 못 찾음: {list(listing.columns)}")
    if code_col != "Code":
        listing = listing.rename(columns={code_col: "Code"})
    if "Name" not in listing.columns and "종목명" in listing.columns:
        listing = listing.rename(columns={"종목명": "Name"})
    listing["Code"] = listing["Code"].astype(str).str.strip()
    listing = listing[listing["Code"].str.len() == 6].copy()
    for c in ("Name", "Market", "Marcap", "Amount", "Stocks", "Close"):
        if c not in listing.columns:
            listing[c] = np.nan
    listing["Name"] = listing["Name"].fillna(listing["Code"])

    # 업종·주요제품 (KRX 상장법인 상세). v17.5.1: 열을 바로잡아요 — Sector 는 소속부(우량기업부 등, 코스피는 빈 칸),
    # Industry 가 업종, Products 가 주요제품이에요. 예전엔 Sector→업종, Industry→주요제품으로 읽어서 "nan · 주요제품: <업종>"이 됐어요.
    desc = {}
    for src in ("KRX-DESC",):
        try:
            d = fdr.StockListing(src)
            cc = next((c for c in ("Code", "Symbol") if c in d.columns), None)
            if cc and "Industry" in d.columns:
                has_prod = "Products" in d.columns
                for _, r in d.iterrows():
                    desc[str(r[cc]).strip()] = (_txt(r.get("Industry")), _txt(r.get("Products")) if has_prod else "")
                n_ind = sum(1 for v in desc.values() if v[0])
                n_prod = sum(1 for v in desc.values() if v[1])
                log(f"· 업종 정보 {len(desc):,}건 ({src}) · 업종 {n_ind:,} · 주요제품 {n_prod:,}"
                    + ("" if has_prod else " · !! Products 열이 없어 주요제품은 비워요"))
            else:
                log(f"  !! 업종 정보 {src}: 예상한 열(Industry)이 없어요 {list(d.columns)} — 업종을 비워요")
        except Exception as e:
            log(f"  !! 업종 정보 {src} 실패: {e}")
    if not desc and "_prev_s" in listing.columns:
        log("  !! 업종은 지난 data.json 값을 그대로 사용")
    elif not desc:
        log("  !! 업종 정보를 못 받아왔어요 — 업종이 '기타'로 들어갑니다")

    # v17.5.1: d1 (전 거래일 공식 종가 대비) · val20 (20거래일 평균 거래대금) — 그 전 날짜들의 최종 목록 파일에서
    d1_map, v20_map = {}, {}
    if px_date is not None:
        sessions, snotes, prev_final = kr_recent_sessions(px_date, _fetch_listing_csv, _listing_commit_kst)
        for n in snotes:
            log(f"  ({n})" if not n.startswith("!!") else f"  {n}")
        d1_map, v20_map, dcnt = kr_d1_val20(listing, sessions, prev_final)
        log(f"{'  !! ' if not prev_final else '· '}d1·val20: 앞선 거래일 파일 {len(sessions)}개"
            + (f" (직전 {sessions[0][0]})" if sessions else "") + f" · d1 {len(d1_map):,} · val20 {len(v20_map):,}"
            + (f" · {dict(dcnt)}" if dcnt else ""))

    n_all = len(listing)
    listing = select_kr_universe(listing, MAX_KR)
    if n_all > MAX_KR:
        log(f"  → 전체 {n_all:,}개 중 시가총액 상위 {MAX_KR:,}개 처리 (MAX_KR)")
    log(f"  → {len(listing):,}개 종목 (필수 종목 {len(MUST_KR)}개 확인)")

    # 공식 종가와 파일의 Close(저녁엔 시간외 가격) 비교 — 참고용 로그
    if px_date is not None:
        off = listing.apply(kr_official_close, axis=1)
        cl = pd.to_numeric(listing["Close"], errors="coerce")
        diff = ((cl - off).abs() / off > 0.01).sum()
        log(f"· 공식 종가 = 시가총액 ÷ 상장주식수 (기준일 {px_date}) · 파일의 Close 가 1% 넘게 다른 종목 {int(diff):,}개 (시간외 가격)")

    last = px_date or (today - dt.timedelta(days=1))
    ks_all = fdr.DataReader(KR_INDEX, start, today)["Close"].dropna()
    # 기준일과 오늘 사이에 끝난 거래일이 있으면 가격이 하루 이상 낡았어요 (그날 최종 목록 파일이 없거나 아직 최종본 아님).
    # 관문(validate_data.py)도 KOSPI 일봉을 따로 받아 같은 검사를 하고 실패시켜요. 여기서는 크게 남겨요.
    if px_date is not None:
        missed = sorted({d.date() for d in ks_all.index if px_date < d.date() < today})
        if missed:
            log(f"  !! 기준일 {px_date} 뒤에 이미 끝난 거래일 {len(missed)}일: {', '.join(d.isoformat() for d in missed[:5])} "
                f"— 그날 최종 목록 파일이 없거나 아직 최종본이 아니에요. 가격이 낡아서 관문에서 실패 처리돼요")
        else:
            log(f"· 기준일 {px_date} 뒤에 끝난 거래일 없음 (KOSPI 일봉 {len(ks_all):,}일, 오늘 {today} 은 빼고 봐요)")
    kospi = cut_at(ks_all, last)
    ks_date = kospi.index[-1].date() if len(kospi) else None
    if px_date is not None and ks_date != px_date:
        log(f"  !! KOSPI 마지막 날짜 {ks_date} ≠ 기준일 {px_date} (검증에서 실패 처리돼요)")
    bench = kospi.pct_change().dropna()
    bench.name = "bench"
    mkt = {}
    try:
        mkt = {"kospi": round(float(kospi.iloc[-1]), 2),
               "k1": round(float(kospi.iloc[-1] / kospi.iloc[-22] - 1) * 100, 1),
               "k3": round(float(kospi.iloc[-1] / kospi.iloc[-64] - 1) * 100, 1)}
    except Exception as e:
        log(f"  !! KOSPI 요약 실패: {e}")

    fundamentals, foreign = {}, {}
    try:
        from pykrx import stock as pk
        day = last.strftime("%Y%m%d")
        # 시장별 조회 → 합치기. "ALL" 단일 호출이 pykrx/KRX 사정으로 실패해도 살아남도록
        frames = []
        for mkt_name in ("KOSPI", "KOSDAQ"):   # 'mkt' 는 위의 시장 요약 dict 라서 다른 이름을 써요
            try:
                df = pk.get_market_fundamental_by_ticker(day, market=mkt_name)
                if df is not None and len(df):
                    frames.append(df)
            except Exception as e:
                log(f"  (펀더멘털 {mkt_name} 실패: {e})")
        if frames:
            fundamentals = pd.concat(frames).to_dict("index")
        log(f"· pykrx 펀더멘털 {len(fundamentals):,}건 (0이어도 정상 — DART 기반 계산으로 대체됩니다)")
        try:
            fr = pk.get_exhaustion_rates_of_foreign_investment(day, market="ALL")
            col = next((c for c in fr.columns if "지분" in str(c)), None)
            if col is not None:
                foreign = fr[col].to_dict()
                log(f"· 외국인 지분율 {len(foreign):,}건")
        except Exception as e:
            log(f"  (외국인 지분율 생략: {e})")
    except Exception as e:
        log(f"  (pykrx 생략: {e})")

    out, pin, dropped = [], collections.Counter(), collections.Counter()
    lock = threading.Lock()
    prev_hl = {x["t"]: (_fin(x.get("hi")), _fin(x.get("lo"))) for x in (prev or {}).get("stocks", []) if x.get("cls") == "kr"}
    hl_cnt, hl_other = collections.Counter(), []

    def hilo_note(code, px, rec):
        """v17.5.1: 52주 최고·최저가 지난 발행본보다 1% 넘게 바뀌면 이유별로 세요.
        새 고점·저점 / 기간 밖으로 빠짐(그 값이 252거래일보다 앞에 있음) / 그 밖(분할·수정·잘못된 봉일 수 있어요 → 이름을 남겨요)."""
        old = prev_hl.get(code)
        if not old:
            return
        for key, i in (("hi", 0), ("lo", 1)):
            o, n = old[i], _fin(rec.get(key))
            if not o or not n or abs(n / o - 1) <= 0.01:
                continue
            if (n > o) if key == "hi" else (n < o):
                why = "새 고점" if key == "hi" else "새 저점"
            else:
                before = px.iloc[:-252] if len(px) > 252 else px.iloc[:0]
                why = "기간 밖으로 빠짐" if len(before) and bool(((before / o - 1).abs() <= 0.005).any()) else "그 밖"
            with lock:
                hl_cnt[f"{key} {why}"] += 1
                if why == "그 밖":
                    hl_other.append(f"{code} {key} {o:,.0f}→{n:,.0f}")

    def one(row):
        code = row["Code"]
        try:
            close = kr_official_close(row) if px_date is not None else None
            if px_date is not None and close is None:
                with lock:
                    dropped["공식 종가 없음"] += 1
                return None
            px = None
            for attempt in range(2):
                try:
                    px = fdr.DataReader(code, start, last)["Close"].dropna()
                    break
                except Exception:
                    if attempt == 0:
                        time.sleep(0.3)
                        continue
                    raise
            if px is None:
                return None
            if close is not None:
                px, how = pin_close(px, px_date, close)
                with lock:
                    pin[how] += 1
            else:
                px = cut_at(px, last)
            if len(px) < 60:
                with lock:
                    dropped["시세 60일 미만"] += 1
                return None
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a = beta_alpha(ret, bench, rf)
            f = fundamentals.get(code, {})
            per, pbr = _num(f.get("PER")), _num(f.get("PBR"))
            eps, bps, dps = _num(f.get("EPS")), _num(f.get("BPS")), _num(f.get("DPS"))
            dyv = _num(f.get("DIV"))
            sec_txt, prod_txt = desc.get(code, ("", ""))
            mc = _fin(row.get("Marcap"))
            cap = mc / 1e12 if mc and mc > 0 else None
            amt = _fin(row.get("Amount"))
            shr = _num(row.get("Stocks"))
            rec = {
                "t": code, "nk": str(row["Name"]), "ne": str(row["Name"]), "cls": "kr",
                "s": (row.get("_prev_s") if isinstance(row.get("_prev_s"), str) and row.get("_prev_s") and not sec_txt else map_sector_kr(sec_txt, prod_txt)),
                "price": close if close is not None else float(px.iloc[-1]),
                "vol": ann_vol(ret.values), "beta": b, "al": a,
                "per": round(per, 1) if per and per > 0 else None,
                "pbr": round(pbr, 2) if pbr and pbr > 0 else None,
                "dy": round(dyv, 2) if dyv is not None else None,   # 모르면 빈 칸 (0% 로 보이지 않게). DART 가 나중에 채워요
                "eps": round(eps, 0) if eps else None,
                "bps": round(bps, 0) if bps else None,
                "dps": round(dps, 0) if dps is not None and dps >= 0 else None,   # 0 = 배당 없음 (v17.5.1)
                "cap": round(cap, 3) if cap else None,
                "val": round(amt / 1e8, 1) if amt is not None else None,
                "lo": float(px.tail(252).min()), "hi": float(px.tail(252).max()),
                "d1": d1_map.get(code), "val20": v20_map.get(code),
                "etf": code in KR_LISTED_FUNDS,       # 목록 파일에 섞인 상장 펀드 (인프라 펀드 등)
            }
            hilo_note(code, px, rec)
            if shr and shr > 0:
                rec["shr"] = int(shr)
            if len(px) > 66:
                rec["r1"] = round(float(px.iloc[-1] / px.iloc[-22] - 1) * 100, 1)
                rec["r3"] = round(float(px.iloc[-1] / px.iloc[-64] - 1) * 100, 1)
            if len(px) > 500:
                rec["r36"] = round(float(px.iloc[-1] / px.iloc[0] - 1) * 100, 1)
            fv = _num(foreign.get(code))
            if fv is not None and 0 <= fv <= 100:
                rec["frn"] = round(fv, 1)
            # PER·PBR 로부터 ROE 를 역산 (PBR ÷ PER = 자기자본이익률)
            if rec["per"] and rec["pbr"]:
                rec["roe"] = round(rec["pbr"] / rec["per"] * 100, 1)
            rec.update(perf_stats(px, rf))
            dk = kr_desc_text(sec_txt, prod_txt, row.get("Market"), cap)
            if dk:
                rec["dk"] = dk
            return {k: v for k, v in rec.items() if v is not None}
        except Exception as e:
            with lock:
                dropped[f"오류 {type(e).__name__}"] += 1
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, r) for _, r in listing.iterrows()]
        for i, fu in enumerate(as_completed(futs)):
            r = fu.result()
            if r:
                out.append(r)
            if (i + 1) % 500 == 0:
                log(f"  … {i + 1:,}/{len(futs):,} 처리 (성공 {len(out):,})")

    log(f"· 한국 시세 완료: {len(out):,} / {len(listing):,}개"
        + (f" · 빠짐 {dict(dropped)}" if dropped else ""))
    odd = sorted(f"{r['t']} {r['nk']}" for r in out if r["t"] not in KR_LISTED_FUNDS
                 and (r.get("dk") or "").startswith(KR_FUND_INDUSTRY))
    log(f"· 상장 펀드(etf) {sum(1 for r in out if r.get('etf'))}개 · 업종 '{KR_FUND_INDUSTRY}'인데 회사로 둔 종목 {len(odd)}개"
        + (f": {', '.join(odd[:15])}" if odd else "") + " (새 펀드가 보이면 KR_LISTED_FUNDS 에 넣어요)")
    if hl_cnt:
        log(f"{'  !! ' if hl_other else '· '}52주 최고·최저가 지난 발행본보다 1% 넘게 바뀐 종목: {dict(hl_cnt)}"
            + (f" · 그 밖(확인 필요) {len(hl_other)}건: {', '.join(sorted(hl_other)[:10])}{'…' if len(hl_other) > 10 else ''}" if hl_other else ""))
    if pin:
        loud = pin["added"] > 0.02 * max(sum(pin.values()), 1)   # 시계열이 하루 늦으면 베타·변동성에 가짜 하루 움직임이 끼어요
        log(f"{'  !! ' if loud else '· '}네이버 시계열의 {px_date} 값: 공식 종가와 같음 {pin['same']:,} · "
            f"공식 종가로 교체 {pin['fixed']:,} · 없어서 추가 {pin['added']:,}"
            + (" (네이버 시계열이 기준일보다 늦은 종목이 많아요)" if loud else ""))
    meta = {"pxDate": px_date.isoformat() if px_date else None,
            "ksDate": ks_date.isoformat() if ks_date else None, "listSrc": list_src, "_index": kospi}
    return out, bench, mkt, meta


def fill_multiples(kr_stocks, fin_map):
    """DART 재무(순이익·자본) + 상장주식수로 EPS/BPS/PER/PBR을 직접 계산합니다.
    pykrx는 KRX 로그인이 필요해져 CI에서 동작하지 않으므로, 있으면 쓰고 없으면 이 값으로 채웁니다.
    순이익·자본은 지배주주 귀속분을 우선 사용합니다."""
    n = 0
    for s in kr_stocks:
        fin = fin_map.get(s["t"])
        shr = s.get("shr")
        price = s.get("price")
        if not fin or not shr or not price:
            continue
        _t = fin.get("ttm") or {}
        _b = fin.get("bs2") or {}
        ni = (_t.get("nio") if _t.get("nio") is not None else
              (_t.get("ni") if _t.get("ni") is not None else
               (fin.get("nio") if fin.get("nio") is not None else (fin.get("ni") or [None])[0])))
        eq = (_b.get("eqo") if _b.get("eqo") is not None else
              (_b.get("eq") if _b.get("eq") is not None else
               (fin.get("eqo") if fin.get("eqo") is not None else fin.get("eq"))))
        if ni is not None:
            eps = ni * 1e8 / shr
            if s.get("eps") is None:
                s["eps"] = round(eps, 0)
            if s.get("per") is None and eps > 0:
                s["per"] = round(price / eps, 1)
        if eq and eq > 0:
            bps = eq * 1e8 / shr
            if s.get("bps") is None:
                s["bps"] = round(bps, 0)
            if s.get("pbr") is None:
                s["pbr"] = round(price / bps, 2)
        if s.get("per") is not None or s.get("pbr") is not None:
            n += 1
    log(f"· 멀티플 직접 계산: {n:,}건 (DART 재무 × 상장주식수 기반)")


# ────────────────────────────────────────────────────────────
# 미국
# ────────────────────────────────────────────────────────────
def us_tickers():
    import FinanceDataReader as fdr
    tk = set(EXTRA_US)
    for name in ("S&P500", "NASDAQ"):
        try:
            df = fdr.StockListing(name)
            col = "Symbol" if "Symbol" in df.columns else df.columns[0]
            syms = [str(s) for s in df[col].dropna().tolist()]
            if name == "NASDAQ":
                syms = syms[:400]
            tk.update(syms)
        except Exception as e:
            log(f"  ({name} 목록 실패: {e})")
    return sorted({s.replace(".", "-").strip().upper() for s in tk if s and len(s) <= 6 and s.isascii()})


US_SEC_KO = {"semi": "반도체", "elec": "전자·하드웨어", "battery": "배터리·에너지저장", "auto": "자동차",
    "machine": "산업·기계", "steel": "소재·금속", "chem": "화학", "energy": "에너지", "utility": "유틸리티",
    "bio": "제약·바이오", "health": "의료·헬스케어", "platform": "인터넷·소프트웨어", "game": "게임",
    "media": "미디어·엔터테인먼트", "telecom": "통신", "bank": "은행·금융", "insure": "보험",
    "broker": "금융서비스", "build": "건설·인프라", "retail": "유통·소비재", "food": "식음료",
    "cosmetic": "생활용품", "transport": "운송·물류", "hotel": "호텔·레저", "realestate": "부동산", "etc": ""}


def us_desc(sec_key, industry):
    ko = US_SEC_KO.get(sec_key, "")
    base = f"미국 상장 {ko} 기업이에요." if ko else "미국 상장 기업이에요."
    ind = (industry or "").strip()
    if ind and len(ind) < 40:
        base += f" ({ind})"
    return base


NY = ZoneInfo("America/New_York")


def us_last_complete_day(now=None):
    """뉴욕 장이 끝난 가장 최근 날짜 (16:30 ET 이후면 오늘, 아니면 어제). 장중 봉을 '종가'로 쓰지 않게."""
    t = (now or dt.datetime.now(dt.timezone.utc)).astimezone(NY)
    return t.date() if t.time() >= dt.time(16, 30) else t.date() - dt.timedelta(days=1)


def _yf_close(data, tk=None):
    v = data[tk]["Close"] if tk is not None and isinstance(data.columns, pd.MultiIndex) else data["Close"]
    return (v.iloc[:, 0] if isinstance(v, pd.DataFrame) else v).dropna()


def us_cap_val(market_cap_usd, avg_volume, price_usd, fx):
    """미국 시가총액·거래대금을 한국과 같은 단위로: (조원, 억원). (순수 함수)"""
    mc, av, px, fx = _fin(market_cap_usd), _fin(avg_volume), _fin(price_usd), _fin(fx)
    cap = round(mc * fx / 1e12, 3) if mc and mc > 0 and fx else None
    val = round(av * px * fx / 1e8, 1) if av and px and fx else None
    return cap, val


US_INFO_PATH = os.environ.get("US_INFO_CACHE", ".dart-cache/us-info-v1.json.gz")   # DART 캐시와 같은 폴더 (같이 보관돼요)
US_INFO_FRESH_DAYS = 3
US_INFO_MAX_AGE_DAYS = 14
US_INFO_KEYS = ("shortName", "longName", "quoteType", "sector", "industry", "longBusinessSummary", "trailingPE", "priceToBook",
                "returnOnEquity", "operatingMargins", "revenueGrowth", "debtToEquity", "dividendYield",
                "marketCap", "averageVolume")


def load_us_info(path=None):
    path = path or US_INFO_PATH
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            d = json.load(f)
        log(f"· 미국 상세 정보 보관본 {len(d):,}곳")
        return d
    except FileNotFoundError:
        log("· 미국 상세 정보 보관본 없음 → 모두 새로 받아요")
    except Exception as e:
        log(f"  !! 미국 상세 정보 보관본을 읽지 못했어요({e}) → 모두 새로 받아요")
    return {}


def save_us_info(d, path=None):
    path = path or US_INFO_PATH
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(_json_safe(d, [0]), f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        os.replace(tmp, path)
    except Exception as e:
        log(f"  !! 미국 상세 정보 보관본 저장 실패: {e}")


def apply_us_info(rec, info, px_then, fx):
    """야후 상세 정보를 종목에 붙여요. 받은 날 이후 가격이 움직였으면 PER·PBR·시총·배당률을 오늘 가격에 맞춰요. (순수 함수)"""
    nm = info.get("shortName") or info.get("longName")
    if not nm:
        return False
    rec["nk"] = rec["ne"] = str(nm)
    rec["s"] = map_sector_us(info.get("sector"), info.get("industry"))
    rec["dk"] = us_desc(rec["s"], info.get("industry") or info.get("sector") or "")
    p0, p1 = _fin(px_then), _fin(rec.get("price"))
    k = p1 / p0 if p0 and p1 and p0 > 0 else 1.0
    spec = (("per", "trailingPE", 0, 500, False), ("pbr", "priceToBook", 0, 100, False),
            ("roe", "returnOnEquity", -5, 5, True), ("opm", "operatingMargins", -5, 5, True),
            ("g3", "revenueGrowth", -5, 20, True), ("debt", "debtToEquity", 0, 2000, False))
    for key, src, lo, hi, scale in spec:
        v = _fin(info.get(src))
        if v is None:
            continue
        if key in ("per", "pbr"):
            v *= k
        if not (lo < v < hi):
            continue
        rec[key] = round(v * 100 if scale else v, 2 if key == "pbr" else 1)
    # yfinance 1.x 의 dividendYield 는 이미 % 예요 (0.41 = 0.41%). 예전처럼 1 미만에 100을 곱하면
    # 애플 0.31% 가 31% 가 돼요 (2026-10 발행본에서 확인). 30% 넘는 값은 믿지 않아요.
    dyv = _fin(info.get("dividendYield"))
    if dyv is not None and 0 <= dyv / k < 30:
        rec["dy"] = round(dyv / k, 2)
    mc = _fin(info.get("marketCap"))
    cap, val = us_cap_val(mc * k if mc else None, info.get("averageVolume"), rec.get("price"), fx)
    if cap is not None:
        rec["cap"] = cap
    if val is not None:
        rec["val"] = val
    summ = info.get("longBusinessSummary")
    if summ:
        rec["de"] = str(summ)[:400]
    return True


def fetch_us(start, today, rf):
    """미국 주식 (yfinance). v17.5:
    · end 는 그날을 빼므로 오늘(KST)+1일까지 요청하고, 장이 안 끝난 봉은 버려요 (예전엔 하루 늦었어요).
    · 시가총액(cap)은 조원, 거래대금(val)은 억원 — 한국과 같은 단위 (그날 환율로 환산).
    · 상세 정보(이름·업종·설명)를 못 받은 종목 수를 남기고, 실패분은 한 번 더 천천히 시도해요."""
    import yfinance as yf

    syms = us_tickers()
    log(f"· 미국 {len(syms):,}개 종목…")
    end_x = today + dt.timedelta(days=1)
    last_ok = us_last_complete_day()

    fx = cut_at(_yf_close(yf.download(FX_TICKER, start=start, end=end_x, progress=False, auto_adjust=True)), today)
    spx = cut_at(_yf_close(yf.download(US_INDEX, start=start, end=end_x, progress=False, auto_adjust=True)), last_ok)
    us_px_date = spx.index[-1].date()
    fx = cut_at(fx, max(us_px_date, last_ok))
    fx_last, fx_date = float(fx.iloc[-1]), fx.index[-1].date()
    log(f"· 미국 기준일(S&P500 마지막 봉) {us_px_date} · 환율 {fx_last:,.1f} ({fx_date})")
    bench = spx.pct_change().dropna()
    bench.name = "bench"
    spx_krw = (spx * fx.reindex(spx.index).ffill()).dropna()
    us_vol_krw = ann_vol(spx_krw.pct_change().dropna().values)

    data = yf.download(syms, start=start, end=end_x, progress=False,
                       auto_adjust=True, group_by="ticker", threads=True)

    out, dropped = [], []
    for sym in syms:
        try:
            px = cut_at(_yf_close(data, sym), us_px_date)
            if len(px) < 60:
                continue
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a = beta_alpha(ret, bench, rf)
            krw = (px * fx.reindex(px.index).ffill()).dropna()
            rec = {"t": sym, "nk": sym, "ne": sym, "cls": "us", "ccy": "USD", "fxu": True, "s": "etc",
                   "etf": sym in US_ETFS,
                   "d1": (round(float(px.iloc[-1] / px.iloc[-2] - 1) * 100, 2)
                          if len(px) >= 2 and px.index[-1].date() == us_px_date else None),
                   "price": round(float(px.iloc[-1]), 2),
                   "vol": ann_vol(krw.pct_change().dropna().values), "beta": b, "al": a,
                   "lo": round(float(px.tail(252).min()), 2), "hi": round(float(px.tail(252).max()), 2)}
            rec.update(perf_stats(px, rf))
            out.append({k: v for k, v in rec.items() if v is not None})
        except Exception:
            dropped.append(sym)
    if dropped:
        log(f"  !! 시세를 받지 못해 빠진 미국 종목 {len(dropped)}개: {', '.join(dropped[:8])}{'…' if len(dropped) > 8 else ''}")

    # 상세 정보(이름·업종·설명·기초 지표)는 자주 바뀌지 않아요. 3일 안에 받은 것은 다시 쓰고,
    # 오늘 못 받으면 14일 안의 보관본을 (크게 알리고) 써요. 그보다 오래되면 비워 두고 검증이 잡아요.
    cache = load_us_info()
    tday = today.isoformat()

    def age(t):
        e = cache.get(t)
        return (today - dt.date.fromisoformat(e["at"])).days if e else None

    def fetch_info(rec):
        try:
            info = yf.Ticker(rec["t"]).get_info()
        except Exception:
            return False
        if not (info.get("shortName") or info.get("longName")):
            return False
        cache[rec["t"]] = {"at": tday, "px": rec.get("price"),
                           "info": {k: info.get(k) for k in US_INFO_KEYS if info.get(k) is not None}}
        return True

    need = [r for r in out if age(r["t"]) is None or age(r["t"]) >= US_INFO_FRESH_DAYS]
    failed = need
    for pause, workers in ((0, 10), (20, 3), (60, 1)):   # 야후가 잠깐 막을 때가 많아서, 쉬었다가 더 천천히 다시
        if not failed:
            break
        time.sleep(pause)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            okr = list(ex.map(fetch_info, failed))
        failed = [r for r, k in zip(failed, okr) if not k]
    failed_t = {r["t"] for r in failed}
    reused, fallback, missing, oldest = 0, 0, [], 0
    for rec in out:
        a = age(rec["t"])
        if a is None or a > US_INFO_MAX_AGE_DAYS or not apply_us_info(rec, cache[rec["t"]]["info"], cache[rec["t"]].get("px"), fx_last):
            missing.append(rec["t"])
            continue
        if rec["t"] in failed_t:
            fallback += 1
            oldest = max(oldest, a)
        elif a > 0:
            reused += 1
    save_us_info(cache)
    got = len(need) - len(failed)
    n_ok = len(out) - len(missing)
    log(f"{'  !! ' if failed else '· '}미국 상세 정보(이름·업종·설명): {n_ok:,} / {len(out):,} · 오늘 받음 {got:,} · 3일 안에 받은 것 {reused:,}"
        + (f" · 못 받음 {len(failed):,}곳 → 보관본 {fallback:,}곳(최대 {oldest}일 전) · 없음 {len(missing):,}곳"
           + (f" ({', '.join(missing[:8])}…)" if missing else "") if failed or missing else ""))
    log(f"· 미국 완료: {len(out):,}개")
    # ETF 목록에 없는데 야후가 ETF 라고 하면 ETF 로 두고 크게 알려요 (순위에 섞이지 않게)
    odd = []
    for rec in out:
        qt = ((cache.get(rec["t"]) or {}).get("info") or {}).get("quoteType")
        if qt in ("ETF", "MUTUALFUND") and not rec.get("etf"):
            rec["etf"] = True
            odd.append(rec["t"])
    if odd:
        log(f"  !! 목록엔 회사로 돼 있는데 야후가 ETF·펀드라고 하는 종목 {len(odd)}개 → ETF 로 표시: {', '.join(odd[:10])}")
    n_d1 = sum(1 for r in out if r.get("d1") is not None)
    log(f"· 미국 d1(전 거래일 대비): {n_d1:,} / {len(out):,} · ETF {sum(1 for r in out if r.get('etf')):,}개")
    meta = {"usPxDate": us_px_date.isoformat(), "fxDate": fx_date.isoformat(), "usInfo": [n_ok, len(out)], "_index": spx}
    return out, bench, fx, fx_last, us_vol_krw, meta


# ────────────────────────────────────────────────────────────
class Phases:
    """단계별 소요 시간. 로그 끝에 '⏱ 국내 시세 4m 30s · DART 6m 12s …' 로 남겨요."""
    def __init__(self):
        self.t = {}

    @staticmethod
    def fmt(sec):
        m, s_ = divmod(int(round(sec)), 60)
        return f"{m}m {s_:02d}s" if m else f"{s_}s"

    def run(self, name, fn, *a, **kw):
        t0 = time.time()
        try:
            return fn(*a, **kw)
        finally:
            self.t[name] = self.t.get(name, 0) + time.time() - t0
            log(f"⏱ {name} {self.fmt(self.t[name])}")

    def summary(self):
        return "⏱ " + " · ".join(f"{k} {self.fmt(v)}" for k, v in self.t.items())


def popular_list(kr, us, n_kr=100, n_us=20):
    """거래대금 상위: 시장마다 따로 순위를 매겨요. US 거래대금이 원화라 합쳐 세우면 미국이 다 차지해요. (순수 함수)"""
    def top(arr, n):
        ok = [x for x in arr if _fin(x.get("val")) is not None]
        return [x["t"] for x in sorted(ok, key=lambda x: -_fin(x["val"]))[:n]]
    return top(kr, n_kr) + top(us, n_us)


def read_prev_data(path=OUT):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"  (지난 {path} 없음/못 읽음: {e})")
        return None


UNITS = {"cap": "조원 (한국·미국 모두 · 미국은 그날 환율로 환산)",
         "val": "억원 (거래대금 · 한국은 기준일 하루, 미국은 야후 3개월 평균 거래량 × 가격)",
         "val20": "억원 (한국만 · 최근 20거래일 평균 거래대금, 10일 미만이면 빈 칸)",
         "d1": "% (전 거래일 공식 종가 대비 · 미국은 자기 기준일 · 한국 ±30% 넘으면 빈 칸)",
         "dps": "원 (한국 · 0 = 배당 없음, 빈 칸 = 모름)",
         "fy": "op·debt·roe·opm·g3·dps·dps3 가 나온 사업보고서 연도 (bq 는 TTM 분기)",
         "etf": "true = ETF·펀드·금현물 (회사 주식이 아님)",
         "price": "한국 원 · 미국 달러 · 금현물 원/g", "pct": "% (vol·mdd·r1·r3·r36·mom·al·dy·roe 등)",
         "pxDate": "한국 가격의 공식 종가 날짜", "usPxDate": "미국 가격의 마지막 완성 봉 날짜"}
IDX_YEARS = 3


def idx_hist(series):
    """지수 일별 종가 3년치 (macro.json idxHist). 이미 자기 기준일까지 잘린 시계열을 받아요. (순수 함수)"""
    s = series.dropna()
    last = s.index[-1]
    s = s[s.index > last - pd.DateOffset(years=IDX_YEARS)]
    return {"asOf": last.date().isoformat(), "rows": [[d.date().isoformat(), round(float(v), 2)] for d, v in s.items()]}


def main():
    published_at = dt.datetime.now(KST).isoformat(timespec="seconds")
    today = today_kst()
    start = today - dt.timedelta(days=int(365.25 * YEARS) + 40)
    dart_mode = (os.environ.get("DART_MODE") or "cache").strip()
    selftest = (os.environ.get("BAEPSAE_SELFTEST") or "").strip()
    log(f"뱁새 데이터 수집 v17.5 · {start} ~ {today} (한국 시간) · 발행 시각 {published_at} · "
        f"DART {('꺼짐 (시험 실행)' if dart_mode == 'off' else 'ON · ' + dart_mode) if DART_KEY else '키 없음'}")
    on_main = os.environ.get("GITHUB_REF") == "refs/heads/main"
    if selftest and on_main:
        raise RuntimeError("!! 시험용 입력(selftest)은 main 에서 쓸 수 없어요")
    if dart_mode not in ("cache", "full", "off"):
        raise RuntimeError(f"!! DART_MODE 는 cache·full·off 중 하나여야 해요 (지금: {dart_mode})")
    if dart_mode == "off" and on_main:
        raise RuntimeError("!! dart=off(시험용)는 main 에서 쓸 수 없어요")
    ph = Phases()
    prev = read_prev_data()

    rf, rf_src = ph.run("금리", fetch_rf, today)
    kr, kr_bench, kr_mkt, kmeta = ph.run("국내 시세", fetch_korea, start, today, rf, prev)
    px_date = dt.date.fromisoformat(kmeta["pxDate"]) if kmeta["pxDate"] else today - dt.timedelta(days=1)

    fin_map, client = {}, None
    if dart_mode == "off":
        log("  !! 시험 실행: DART 를 끄고 진행해요 (재무지표·공시 없음 → 검증에서 실패 처리돼요)")
    elif DART_KEY:
        client = DartClient(DART_KEY, mode=dart_mode, today=today)
        kr, fin_map = ph.run("DART", enrich_with_dart, kr, client)
    else:
        log("  !! DART_API_KEY 없음 → 재무지표·공시를 못 받아요 (검증에서 실패 처리돼요)")
    fill_multiples(kr, fin_map)
    n_dy = sum(1 for s in kr if s.get("dy") is not None)
    log(f"· 배당수익률 아는 종목: {n_dy:,} / {len(kr):,} (모르는 종목은 0% 가 아니라 빈 칸 → 앱에 '–')")
    n_dps = sum(1 for s in kr if s.get("dps") is not None)
    n_dps0 = sum(1 for s in kr if s.get("dps") == 0)
    fy_c = collections.Counter(s.get("fy") for s in kr if s.get("fy"))
    log(f"· 주당 배당금 아는 종목: {n_dps:,} / {len(kr):,} (그중 0원 = 배당 없음 {n_dps0:,}) · 사업보고서 연도 {dict(sorted(fy_c.items()))}")

    us, us_bench, fx, fx_last, us_vol_krw, umeta = ph.run("미국", fetch_us, start, today, rf)
    names = etf_names()
    bonds, bd_ret = ph.run("채권", fetch_bonds, start, px_date, kr_bench, names, rf)

    gold_usd = None
    try:
        import yfinance as yf
        gold_usd = _yf_close(yf.download("GC=F", start=start, end=today + dt.timedelta(days=1), progress=False, auto_adjust=True))
    except Exception as e:
        log(f"  !! 국제 금값(GC=F) 실패: {e}")
    funds = ph.run("ETF·금현물", fetch_kr_funds, start, px_date, kr_bench, names, rf, gold_usd, fx)

    if len(kr) < 300 or len(us) < 100:
        log("!! 받아온 종목이 너무 적습니다. 기존 data.json 을 지키기 위해 중단합니다.")
        sys.exit(1)

    settings = {"rf": round(rf * 100, 2), "rfSrc": rf_src}
    try:
        fxr = fx.pct_change()
        us_krw = us_bench + fxr.reindex(us_bench.index).fillna(0)
        cols = [kr_bench.rename("kr"), us_krw.rename("us")]
        if gold_usd is not None:
            cols.append((gold_usd.pct_change() + fxr.reindex(gold_usd.index).fillna(0)).dropna().rename("mt"))
        if bd_ret is not None:
            cols.append(bd_ret.rename("bd"))
        j = cut_at(pd.concat(cols, axis=1).dropna(), px_date)
        if len(j) > MIN_DAYS and "mt" in j.columns:
            c = j.corr()
            settings.update({
                "mktVol": ann_vol(j["kr"].values),
                "usVol": us_vol_krw or ann_vol(j["us"].values),
                "mtVol": ann_vol(j["mt"].values),
                "rhoKrUs": round(float(c.loc["kr", "us"]), 2),
                "rhoKrMt": round(float(c.loc["kr", "mt"]), 2),
                "rhoUsMt": round(float(c.loc["us", "mt"]), 2),
            })
            if "bd" in j.columns:
                settings.update({
                    "bdVol": ann_vol(j["bd"].values),
                    "rhoKrBd": round(float(c.loc["kr", "bd"]), 2),
                    "rhoUsBd": round(float(c.loc["us", "bd"]), 2),
                    "rhoMtBd": round(float(c.loc["mt", "bd"]), 2),
                })
            log(f"· 시장 가정 계산 완료 ({len(j):,}일, ~{px_date}): {settings}")
        else:
            log(f"  !! 시장 가정 계산에 쓸 날이 {len(j)}일뿐 — 기본값을 써요")
    except Exception as e:
        log(f"  !! 상관계수 실패: {e}")

    # 팩터 백분위는 시장 안에서만 (한국은 한국끼리, 미국은 미국끼리)
    add_percentiles(kr)
    add_percentiles(us)
    stocks = kr + us + bonds + funds
    if selftest == "corrupt-price":
        for x in stocks:
            if x["t"] == "005930":
                x["price"] = round(x["price"] * 1.1)
                log(f"  !! 시험용(selftest): 005930 가격을 일부러 {x['price']:,}원으로 틀리게 써요 — 검증이 막아야 합니다")

    payload = {
        "asOf": today.isoformat(), "pxDate": kmeta["pxDate"], "ksDate": kmeta["ksDate"],
        "usPxDate": umeta["usPxDate"], "fxDate": umeta["fxDate"], "publishedAt": published_at,
        "listSrc": kmeta["listSrc"], "fx": round(fx_last, 1), "units": UNITS, "settings": settings,
        "popular": popular_list(kr, us),
        "count": {"kr": len(kr), "us": len(us), "bond": len(bonds), "fund": len(funds), "usInfo": umeta["usInfo"]},
        "stocks": stocks,
    }
    write_json(OUT, payload)
    log(f"✓ {OUT} 저장 — {len(stocks):,}종목, {os.path.getsize(OUT) / 1e6:.1f}MB · 기준일 {kmeta['pxDate']} · "
        f"미국 {umeta['usPxDate']} · 환율 {fx_last:,.1f}")

    kr_mkt.update({"fx": round(fx_last, 1), "rf": round(rf * 100, 2)})
    corp = build_corp(kr, fin_map, today.isoformat(), kr_mkt)
    corp.update({"pxDate": kmeta["pxDate"], "publishedAt": published_at})
    write_json(OUT_CORP, corp)
    dcf_n = sum(1 for c in corp["companies"] if c["dcfReady"])
    log(f"✓ {OUT_CORP} 저장 — 기업 {len(corp['companies']):,} · 업종 {len(corp['sectors'])} · DCF 자동채움 {dcf_n:,}건 · {os.path.getsize(OUT_CORP) / 1e6:.1f}MB")

    macro = ph.run("금리·원자재", fetch_macro, start, today, fx)
    macro["publishedAt"] = published_at
    # v17.5.1: KOSPI·S&P500 일별 종가 3년 (각자 기준일까지) — 2.0 의 '내 덱 vs KOSPI'
    ih = {}
    for name, ser in (("KOSPI", kmeta.get("_index")), ("SP500", umeta.get("_index"))):
        try:
            if ser is not None and len(ser):
                ih[name] = idx_hist(ser)
        except Exception as e:
            log(f"  !! 지수 이력 {name} 실패: {e}")
    if len(ih) == 2:
        macro["idxHist"] = ih
    log(f"{'· ' if len(ih) == 2 else '  !! '}지수 이력: " + " · ".join(f"{k} {len(v['rows']):,}일 (~{v['asOf']})" for k, v in ih.items())
        + ("" if len(ih) == 2 else " — 빠진 것이 있어 싣지 않아요 (검증에서 실패 처리돼요)"))
    write_json(OUT_MACRO, macro)
    log(f"✓ {OUT_MACRO} 저장 — 커브 {macro['curve']['date'] if macro.get('curve') else 'X'} · 원자재 {'O' if macro.get('gold') else 'X'}")

    if client:
        disc = ph.run("공시", fetch_disclosures, kr, client.meta.get("corpMap") or {}, today, client)
        client.save()
        log(f"· DART 전체: {client.summary()}")
    else:
        disc = {"asOf": today.isoformat(), "newest": None, "listOk": False, "insider": [], "nps": []}
    disc["publishedAt"] = published_at
    write_json(OUT_DISC, disc)
    log(f"✓ {OUT_DISC} 저장 — 내부자 {len(disc['insider']):,}건 · 국민연금 {len(disc['nps']):,}건 · 최근 공시 {disc.get('newest')}")
    log(ph.summary())


if __name__ == "__main__":
    main()
