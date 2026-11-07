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
  팩터     pz(규모) vz(가치) mz(모멘텀) qz(퀄리티) lz(저변동) dz(배당, 한국만) — 같은 시장 안에서의 백분위 0~100
  v19.1b   betaSE·betaN(베타의 표준오차·쓴 수익률 수) · 한국 배당: dps3a(오늘 주식 수 기준으로 맞춘 주당 배당금 3년)
           dpsF(해마다 맞춘 배율) divSt(분할 확인 결과) dyt(오늘 종가 기준 배당수익률) · corp.json flRan(실제로 돌린 재무 경고 검사)

시장 가정(도구의 기본값으로 자동 반영)
  rf 국고채 10년(ECOS, 출처는 settings.rfSrc) · mktVol/usVol/mtVol · rhoKrUs/rhoKrMt/rhoUsMt …

DART_API_KEY 로 OpenDART 재무지표·공시를, ECOS_API_KEY 로 국고채 금리를 받아요.
DART 결과는 .dart-cache/ 에 보관해 실행 사이에 다시 씁니다 (하루 한도 보호).
"""

import collections
import copy
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
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

# v19.1b: 배당 순위·수익률 확인 비율의 관문 기준과 '빠진 이유' 문구는 관문 파일 한곳에 있어요. 파이프라인 로그는 그걸 그대로
# 읽어 관문과 같은 선·같은 말로 알려요 (관문은 이 파일을 읽지 않아요 — 계산은 따로)
from validate_data import DIV_RANK_MISS_FAIL, DYT_COVER_BANDS, floor_1, rank_miss_reason

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
#   마감 + 30분 뒤(보통 16~23시 · 수능일은 17시 뒤): 시가총액이 공식 종가로 확정 (Close 열은 시간외 가격이라 쓰지 않아요)
# 그래서 오늘(KST) 이전 날짜 중, 시가총액이 90% 이상 차 있고 마지막 커밋이 그날 KRX 정규장 마감 + 30분
# (보통 날 15:30 → 16:00 KST) 이후인 가장 최근 파일을 고릅니다. 주말 파일은 시가총액이 비어 있어 걸러져요.
# v17.5: 18시 → 16시. 4월 이후 거래일 138일 중 29일은 마지막 커밋이 16:13~17:59 였고,
# 그 버전의 시가총액은 밤 23시 버전과 100% 같았어요 (10/20·10/23 비교).
# v17.5.4: 마감이 늦는 날(수능일 10:00~16:30 등)은 data/krx_special_sessions.csv 의 마감 + 30분 (수능일 17:00).
# 고정 16:00 이면 수능일 16:10 커밋(아직 장중)을 종가로 발행했을 거예요. 이 표는 마감을 늦출 수만 있어요 (15:30 보다 이른 마감을 적으면 멈춰요).
# 야후 ^KS11 분봉으로 마감 시각을 맞춰 보려 했지만 쓸 수 없었어요 (2026-11-03 확인): 야후의 정규장은 매일 09:00~15:00 로 고정이고
# 분봉도 15:00 에서 끝나요 — 2025-11-13 수능일(실제 16:30 마감)에도 똑같이 15:00 이었어요.
LISTING_URL = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/{d}.csv"
LISTING_COMMITS_API = "https://api.github.com/repos/FinanceData/fdr_krx_data_cache/commits"
LISTING_PATH = "data/listing/krx/{d}.csv"
LISTING_MIN_CAP_SHARE = 0.90
KRX_CLOSE = dt.time(15, 30)                       # 보통 날 KRX 정규장 마감
LISTING_FINAL_AFTER = dt.timedelta(minutes=30)    # 마감 30분 뒤 커밋부터 최종본 (보통 날 16:00 — v17.5 와 같아요)
LISTING_LOOKBACK_DAYS = 10
KRX_SPECIAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "krx_special_sessions.csv")
KRX_SPECIAL_HEAD = ["date", "open", "close", "kind", "reason", "source"]
KRX_SPECIAL_KINDS = ("수능", "연초 개장", "기타")
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


def load_krx_special_sessions(path=None):
    """data/krx_special_sessions.csv → {날짜: {"open", "close", "kind", "reason", "source"}} (시각은 dt.time).
    사람이 출처를 확인해 적은 표예요. 이상한 줄이 하나라도 있으면 그 줄 번호와 함께 예외 (조용히 15:30 으로 넘어가지 않게)."""
    path = path or KRX_SPECIAL_PATH
    name = os.path.basename(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or [c.strip() for c in rows[0]] != KRX_SPECIAL_HEAD:
        raise RuntimeError(f"!! {name} 머리줄이 {','.join(KRX_SPECIAL_HEAD)} 이 아니에요: {rows[0] if rows else '빈 파일'}")
    out = {}
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue

        def bad(why, n=n, row=row):
            return RuntimeError(f"!! {name} {n}번째 줄이 이상해요 ({why}): {','.join(row)[:120]}")
        if len(row) != len(KRX_SPECIAL_HEAD):
            raise bad(f"칸 {len(row)}개 — {len(KRX_SPECIAL_HEAD)}개여야 해요 (쉼표가 섞였는지 확인)")
        r = dict(zip(KRX_SPECIAL_HEAD, (c.strip() for c in row)))
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
                raise ValueError(r["date"])
            d = dt.date.fromisoformat(r["date"])
        except ValueError:
            raise bad("날짜는 YYYY-MM-DD") from None
        try:
            if not all(re.fullmatch(r"\d{2}:\d{2}", r[k]) for k in ("open", "close")):
                raise ValueError
            op, cl = (dt.time.fromisoformat(r[k]) for k in ("open", "close"))
        except ValueError:
            raise bad("시각은 HH:MM") from None
        if d in out:
            raise bad(f"{d} 가 두 번 있어요")
        if d.weekday() >= 5:
            raise bad(f"{d} 는 주말이에요")
        if not op < cl:
            raise bad("개장이 마감보다 앞이어야 해요")
        if cl < KRX_CLOSE:
            raise bad(f"마감 {cl:%H:%M} 이 보통 마감 {KRX_CLOSE:%H:%M} 보다 일러요 — 최종본 규칙을 느슨하게 만들어서 이 표에는 못 적어요 (Jack 결정이 필요해요)")
        if r["kind"] not in KRX_SPECIAL_KINDS:
            raise bad(f"kind 는 {' · '.join(KRX_SPECIAL_KINDS)} 중 하나")
        if not r["reason"] or not r["source"]:
            raise bad("reason·source 는 비울 수 없어요")
        out[d] = {"open": op, "close": cl, "kind": r["kind"], "reason": r["reason"], "source": r["source"]}
    return out


def krx_close(d, special):
    """그날 KRX 정규장 마감 시각: 특별 거래시간 표에 있으면 그 마감, 없으면 15:30. (순수 함수)"""
    s = special.get(d)
    return s["close"] if s else KRX_CLOSE


def listing_final_cut(d, special):
    """이 시각(KST) 이후의 커밋이어야 그날 목록 파일을 최종본으로 봐요 = 마감 + 30분 (보통 16:00 · 수능일 17:00). (순수 함수)"""
    return dt.datetime.combine(d, krx_close(d, special), KST) + LISTING_FINAL_AFTER


def special_note(d, special):
    """마감이 보통(15:30)과 다른 날이면 로그 한 줄, 아니면 None. (순수 함수)"""
    s = special.get(d)
    if not s or s["close"] == KRX_CLOSE:
        return None
    return f"{d} 특별 거래시간({s['kind']}): 마감 {s['close']:%H:%M} → 최종본은 {listing_final_cut(d, special):%H:%M} 이후 커밋만"


def _hm_ko(t):
    return f"{t.hour}시" + (f" {t.minute}분" if t.minute else "")


def pick_final_listing(today, fetch_csv, commit_kst, lookback=LISTING_LOOKBACK_DAYS, special=None):
    """오늘(KST) 이전의 가장 최근 최종본을 고릅니다. (순수 함수 — 받아오는 방법은 인자로)
    special: KRX 특별 거래시간 표 (None 이면 data/krx_special_sessions.csv 를 읽어요).
    반환: (날짜, DataFrame, 설명, 건너뛴 날짜 메모) · 못 찾으면 날짜·DataFrame 이 None."""
    special = load_krx_special_sessions() if special is None else special
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
        sp = special_note(d, special)
        if sp:
            notes.append(sp)
        ct = commit_kst(d)
        if ct is not None:
            cut = listing_final_cut(d, special)
            if ct >= cut:
                return d, df, f"{d} 최종본 ({ct:%H:%M} KST 커밋, {len(df):,}종목, 시총 {share:.0%})", notes
            notes.append(f"{d} 마지막 커밋 {ct:%m-%d %H:%M} KST — {_hm_ko(cut.time())} 전이라 최종본이 아님 → 건너뜀")
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


def kr_recent_sessions(px_date, fetch_csv, commit_kst, n=VAL20_DAYS - 1, lookback=45, special=None):
    """기준일 앞의 끝난 거래일 목록 파일들 (최신 → 과거, 최대 n개). (순수 함수 — 받아오는 방법은 인자로)
    반환: (세션 [(날짜, DataFrame)], 메모들, 직전 거래일 파일이 최종본인지).
    직전 거래일 파일은 커밋 시각이 그날 마감 + 30분(보통 16시 · 수능일 17시) 전이면 최종본이 아니라 그날 종가를 믿지 않아요 (d1 을 비워요).
    special: KRX 특별 거래시간 표 (None 이면 data/krx_special_sessions.csv 를 읽어요)."""
    special = load_krx_special_sessions() if special is None else special
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
        # v17.5.4: 모든 날의 파일을 그날 마감 + 30분 기준으로 봐요 (예전에는 직전 거래일만). 최종본이 아닌 날의 값은 가격 고정
        # (공식 종가로 맞추기)·거래대금 평균에 쓰지 않아요 — 수능일처럼 늦게 끝나는 날의 장중 값이 종가 기록에 들어가지 않게.
        ct = commit_kst(d)
        final = not (ct is not None and ct < listing_final_cut(d, special))
        if prev_final is None:                      # 기준일 바로 앞의 거래일 (d1 의 전날)
            sp = special_note(d, special)
            if sp:
                notes.append(f"직전 거래일 {sp}")
            prev_final = final
            if not final:
                notes.append(f"!! 직전 거래일 {d} 파일의 마지막 커밋이 {ct:%m-%d %H:%M} KST — 최종본이 아니라 d1 을 비우고 "
                             "그날 값은 가격 고정·거래대금에 쓰지 않아요")
            elif ct is None:
                notes.append(f"직전 거래일 {d}: 커밋 시각 확인 불가 · 더 뒤 날짜({px_date}) 최종본이 있어 끝난 날로 봐요")
        elif not final:
            notes.append(f"!! {d} 파일의 마지막 커밋이 {ct:%m-%d %H:%M} KST — 그날 마감 + 30분 전이라 최종본이 아니에요 · "
                         "그날 값은 가격 고정·거래대금에 쓰지 않아요")
        if not final:
            continue
        out.append((d, df))
    return out, notes, bool(prev_final)


def kr_prev_session(px_date, index_dates):
    """KOSPI 일봉 날짜들에서 기준일 바로 앞 거래일. 없으면 None. (순수 함수)"""
    ds = sorted({pd.Timestamp(d).date() for d in index_dates if pd.Timestamp(d).date() < px_date})
    return ds[-1] if ds else None


def prev_session_ok(sessions, prev_final, want_prev):
    """d1 을 써도 되는지: 직전 파일이 최종본이고, 그 날짜가 KOSPI 의 직전 거래일과 같아야 해요. (순수 함수)"""
    return bool(sessions) and bool(prev_final) and want_prev is not None and sessions[0][0] == want_prev


def pin_recent(px, off_by_day, code):
    """최근 거래일들의 값을 공식 종가로 맞춰요 (그 날짜 봉이 있을 때만). 반환: (시계열, 고친 개수). (순수 함수)"""
    fixed = 0
    px = px.copy()
    for ts, offmap in off_by_day.items():
        v = offmap.get(code)
        if v and ts in px.index and float(px.loc[ts]) != v:
            px.loc[ts] = v
            fixed += 1
    return px, fixed


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
    cap = _fin(cap)
    if cap and cap > 0:
        bits.append(f"시가총액 {cap:,.1f}조원" if cap >= 1 else f"시가총액 {cap * 10000:,.0f}억원")
    return " · ".join(bits) or None


# ────────────────────────────────────────────────────────────
# v17.5.1 PR 2: 업종 그룹 (ind · indName) — 한국은 DART 업종 코드(KSIC), 미국은 야후 업종 이름
# data/industry_groups.csv (그룹·이름·상위 그룹) · industry_map.csv (KSIC 접두어) · industry_us.csv · industry_overrides.csv
# ────────────────────────────────────────────────────────────
INDUSTRY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GROUP_MIN = 5            # 같은 시장에서 이보다 적으면 상위 그룹으로 합쳐요 (상위가 없으면 그룹 없음)


def _read_csv(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = [i + 2 for i, r in enumerate(rows) if None in r or any(v is None for v in r.values())]
    if bad:
        raise RuntimeError(f"!! {os.path.basename(path)} {bad[:5]}번째 줄의 칸 수가 머리줄과 달라요 (쉼표가 섞였는지 확인)")
    return [{k: v.strip() for k, v in r.items()} for r in rows]


def load_industry_tables(d=INDUSTRY_DIR):
    """업종 표 넷을 읽고 서로 맞는지 확인해요. 틀리면 예외 (조용히 '기타'로 넘어가지 않게)."""
    groups = {r["group"]: r for r in _read_csv(os.path.join(d, "industry_groups.csv"))}
    kmap = {r["ksic"]: r["group"] for r in _read_csv(os.path.join(d, "industry_map.csv"))}
    usmap = {r["yahoo_industry"]: r["group"] for r in _read_csv(os.path.join(d, "industry_us.csv"))}
    over = {r["code"]: (r["group"], r["reason"]) for r in _read_csv(os.path.join(d, "industry_overrides.csv"))}
    refine = [(r["group"], r["field"], r["keyword"], r["to"]) for r in _read_csv(os.path.join(d, "industry_refine.csv"))]
    if any(f not in ("products", "name") for _, f, _, _ in refine):
        raise RuntimeError("!! industry_refine.csv 의 field 는 products 또는 name 이어야 해요")
    used = (set(kmap.values()) | set(usmap.values()) | {g for g, _ in over.values()} | {g["parent"] for g in groups.values() if g["parent"]}
            | {r[0] for r in refine} | {r[3] for r in refine})
    bad = sorted(used - set(groups))
    if bad:
        raise RuntimeError(f"!! 업종 표에 없는 그룹: {bad}")
    if any(not g["name"] for g in groups.values()):
        raise RuntimeError("!! 이름 없는 업종 그룹이 있어요")
    return {"groups": groups, "kmap": kmap, "usmap": usmap, "over": over, "refine": refine}


def ksic_group(code, kmap):
    """가장 긴 접두어가 이겨요 (예: 29271 반도체 장비 > 29 기계)."""
    code = (code or "").strip()
    for n in range(len(code), 1, -1):
        g = kmap.get(code[:n])
        if g:
            return g
    return None


def is_preferred(code):
    """한국 우선주: 보통주 코드의 끝자리를 바꾼 것 (005935, 005387, 00680K). (순수 함수)"""
    return len(code) == 6 and code[-1] != "0"


def assign_industries(stocks, tables, ksic, min_members=GROUP_MIN, products=None):
    """종목에 ind·indName 을 붙여요. (순수 함수)
    순서: 고정표(overrides) → 한국 KSIC 접두어 (+ 주요제품·이름 낱말로 다시 나누기: industry_refine.csv) / 미국 야후 업종(_yind).
    ETF·펀드는 그룹이 없어요. 인원은 보통주만 세고(우선주 빼고), 같은 시장에서 min_members 보다 적은 그룹은
    이름이 그 그룹을 덮는 상위 그룹으로 합쳐요(아래 그룹부터). 상위도 없으면 그룹 없음 — '기타'를 그룹으로 쓰지 않아요.
    우선주는 마지막에 보통주의 그룹을 그대로 따라요. 반환: 집계 Counter (못 맞춘 KSIC·야후 업종은 '없음:…' 으로)."""
    groups, cnt = tables["groups"], collections.Counter()
    pick, prefs = {}, []
    for s in stocks:
        if s.get("cls") not in ("kr", "us") or s.get("etf") or s.get("fund"):
            continue
        if s["cls"] == "kr" and is_preferred(s["t"]) and s["t"] not in tables["over"]:
            prefs.append(s)
            continue
        if s["t"] in tables["over"]:
            g, src = tables["over"][s["t"]][0], "고정표"
        elif s["cls"] == "kr":
            code = ksic.get(s["t"])
            g, src = ksic_group(code, tables["kmap"]), "KSIC"
            if code and not g:
                cnt[f"kr 없음:KSIC {code}"] += 1
            text = {"products": (products or {}).get(s["t"]) or "", "name": s.get("nk") or ""}
            for base, field, kw, to in tables.get("refine", []):
                if g == base and kw in text[field]:
                    g, src = to, f"KSIC+{'주요제품' if field == 'products' else '이름'}"
                    break
        else:
            yi = (s.get("_yind") or "").strip()
            g, src = tables["usmap"].get(yi), "야후"
            if yi and not g:
                cnt[f"us 없음:{yi}"] += 1
        if g:
            pick[s["t"]] = (s["cls"], g)
            cnt[f"{s['cls']} {src}"] += 1
        else:
            cnt[f"{s['cls']} 그룹 없음"] += 1
    for _ in range(len(groups)):              # 작은 그룹을 상위로 — 아래(작은 자식이 없는) 그룹부터 하나씩
        size = collections.Counter(pick.values())
        small = {k for k, n in size.items() if n < min_members and groups[k[1]]["parent"]}
        waiting = {(m, groups[g]["parent"]) for (m, g) in small}
        ready = {k for k in small if k not in waiting}     # 아직 작은 자식이 올라올 그룹은 기다려요
        if not small:
            break
        for t, (m, g) in list(pick.items()):
            if (m, g) in (ready or small):
                pick[t] = (m, groups[g]["parent"])
                cnt[f"{m} {g}→{groups[g]['parent']}"] += 1
    size = collections.Counter(pick.values())  # 그래도 작은 그룹(상위 없음)은 그룹 없음
    for t, (m, g) in list(pick.items()):
        if size[(m, g)] < min_members:
            del pick[t]
            cnt[f"{m} {g} 인원 부족 → 그룹 없음"] += 1
    for s in prefs:                            # 우선주 → 보통주 (005935 → 005930)
        v = pick.get(s["t"][:5] + "0")
        if v:
            pick[s["t"]] = v
            cnt["kr 우선주 → 보통주"] += 1
        else:
            cnt["kr 우선주 (보통주 그룹 없음)"] += 1
    for s in stocks:
        s.pop("_yind", None)
        v = pick.get(s["t"])
        if v and v[0] == s.get("cls"):
            s["ind"], s["indName"] = v[1], groups[v[1]]["name"]
    return cnt


def fetch_ksic(kr_stocks, client):
    """국내 종목의 DART 업종 코드(KSIC). 반환: {종목코드: 코드}."""
    cmap = dart_corp_map(client)
    targets = [s["t"] for s in kr_stocks if s["t"] in cmap and not s.get("etf")]
    with ThreadPoolExecutor(max_workers=5) as ex:
        got = list(ex.map(lambda t: client.company(cmap[t]), targets))
    out = {t: g["induty"] for t, g in zip(targets, got) if g and g.get("induty")}
    try:
        client.save()                  # 새로 받은 업종 코드가 뒤 단계 실패로 사라지지 않게
    except Exception as e:
        log(f"  !! DART 캐시 저장 실패(업종 코드 뒤): {e}")
    log(f"{'· ' if len(out) >= 0.97 * max(len(targets), 1) else '  !! '}DART 업종 코드(KSIC): {len(out):,} / {len(targets):,}곳 "
        f"(DART 기업코드 없는 국내 종목 {sum(1 for s in kr_stocks if s['t'] not in cmap):,}곳) · {client.summary()}")
    return out
SAMPLE_KEEP = ("000270", "086790", "034730", "003550", "088980", "241520")   # 표본에도 꼭: 업종·ETF 검사에 쓰는 종목


def sample_size():
    """시험용 표본 크기 (SAMPLE_KR). 0 이면 전체. 숫자가 아니면 예외 (조용히 전체로 돌지 않게)."""
    v = (os.environ.get("SAMPLE_KR") or "0").strip()
    if not v.isdigit():
        raise RuntimeError(f"!! SAMPLE_KR 은 0 이상의 정수여야 해요 (지금: {v!r})")
    return int(v)


def sample_universe(listing, n):
    """표본: 시가총액 상위 n개 + 필수 종목 + 검사용 종목. 이미 시가총액 순인 표를 받아요. (순수 함수)"""
    keep = set(MUST_KR) | set(SAMPLE_KEEP)
    top = set(listing["Code"].head(n))
    return listing[listing["Code"].isin(top | keep)].copy()


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
        log(f"· {n}" if "특별 거래시간" in n else f"  (종목 목록 {n})")
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


def beta_fit(stock_ret, bench_ret, rf):
    """(베타, 알파, 베타의 표준오차, 쓴 일별 수익률 수). 데이터가 모자라면 모두 None. (순수 함수)
    v19.1b: 베타는 일별 수익률 회귀(절편 포함 최소제곱)의 기울기예요. 표준오차는 같은 회귀의 기울기 표준오차
    √(잔차 제곱합 ÷ (n − 2) ÷ Σ(시장 수익률 − 평균)²) — 앱이 베타를 오차 범위와 함께 보여 줄 때 써요."""
    df = pd.concat([stock_ret, bench_ret], axis=1).dropna()
    n = len(df)
    if n < MIN_DAYS:
        return None, None, None, None
    y, x = df.iloc[:, 0].values, df.iloc[:, 1].values
    vx = np.var(x, ddof=1)
    if vx <= 0:
        return None, None, None, None
    b = float(np.cov(y, x, ddof=1)[0, 1] / vx)
    if not np.isfinite(b) or abs(b) > 5:
        return None, None, None, None
    rf_d = rf / 252
    a = float(np.mean(y - rf_d) - b * np.mean(x - rf_d)) * 252 * 100
    if not np.isfinite(a) or abs(a) > 200:
        a = None
    resid = (y - y.mean()) - b * (x - x.mean())
    sxx = float(np.sum((x - x.mean()) ** 2))
    se = math.sqrt(float(np.sum(resid ** 2)) / (n - 2) / sxx) if sxx > 0 else None
    if se is None or not math.isfinite(se) or se < 0.00005:
        return None, None, None, None     # 잔차가 없는 회귀 (예: 1년 넘게 거래정지라 수익률이 모두 0) — 베타도 비워요
    return round(b, 2), (round(a, 1) if a is not None else None), round(se, 4), n   # 지수 ETF(SPY 등)는 0.001 안팎이라 넷째 자리까지


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
                       for k in ("cap", "pbr", "mom", "roe", "vol", "dyt")})

    def pr(col):
        return df[col].rank(pct=True) * 100

    # 규모는 작을수록, 가치는 PBR 낮을수록 높은 점수 (SMB·HML 방향과 일치)
    # 저변동(lz)은 변동성이 낮을수록 높은 점수
    # v19.1b 배당(dz): 한국만 — 오늘 종가 기준 배당수익률(dyt)이 높을수록. dyt 는 분할을 확인한 주당 배당금으로만 만들어요
    # (확인 못 한 종목은 빈 칸이라 순위에서 빠져요). 미국은 dyt 가 없어 dz 도 없어요 (미국 배당은 그대로 야후 수익률 dy).
    series = {"pz": 100 - pr("cap"), "vz": 100 - pr("pbr"), "mz": pr("mom"), "qz": pr("roe"), "lz": 100 - pr("vol"),
              "dz": pr("dyt")}
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
# v19.1b: v1 → v2. 배당 표(alotMatter)의 현금배당금총액·주당순이익·액면가와 재무제표의 3년 자본금을 새로 담아요.
# 예전 항목에는 이 값이 없어서 캐시를 통째로 새로 받아요 (파일 이름도 바꿔서 v1 파일을 잘못 읽을 일이 없게 · 워크플로 키 dart-cache-v2-).
# v19.1f: v2 → v3. 손익계산서의 이자비용 · 현금흐름표의 이자 지급액 · 손익 줄 이름(영업손실 …)을 새로 읽어요. 예전 재무제표 항목은
# 이 값이 없고 '금융비용'을 이자로 담고 있어서 통째로 새로 받아요 (파일 이름도 바꿔서 v2 파일을 잘못 읽을 일이 없게 · 워크플로 키 dart-cache-v3-).
# 빈 v3 캐시로 시작하는 실행은 그날의 전체 DART 실행이에요 (이틀: 브랜치 시험 실행 하루, main 첫 실행 다음 날).
DART_CACHE_PATH = os.environ.get("DART_CACHE", ".dart-cache/dart-v3.json.gz")
COMPANY_TTL_DAYS = 180   # 기업개황(업종 코드) 보관 기간
DART_CACHE_VERSION = 3   # parse_dart_* 의 결과 모양이나 해석이 바뀌면 올려요 (캐시는 '해석된 값'을 담아서)
# v19.1b: 캐시 없이 처음부터 받는 '전체 DART 실행'의 호출 수 어림 (하루 한도 약 20,000회 · 목표 16,000회 아래).
# 2026-11-01 전체 실행(41319552163): 재무·배당·분기 11,588회 / 2,418곳 = 기업당 4.8회. 업종 코드(company.json)는 그 뒤에 생겨
# 빈 캐시면 기업당 1회 더. 공시는 최대 목록 30쪽 + 내부자 상세 1,200회(DISC_CALL_CAP) + 국민연금 200회 = 1,430회.
DART_PER_COMPANY = 4.8
DART_DISC_MAX = 30 + 1200 + 200
DART_DAY_LIMIT = 20000
DART_FULL_TARGET = 16000
DART_REVALIDATE_DAYS = 90
DART_REVALIDATE_PER_RUN = 300
# v19.1e: 배당 분할 확인에 쓰는 자본금을 더 많은 이름으로 읽어요 (보통주자본금 · (1)자본금 · 납입자본 …). 캐시는 '해석된 값'이라
# 캐시를 통째로 버리지 않고(전체 DART 실행), 자본금을 못 읽은 채 저장된 사업보고서 항목만 한 번 다시 받아요. 실행당 이만큼까지.
DART_REDO_PER_RUN = 800
CAP_REDO_TAG = "cap1"      # 이 표시가 있는 항목은 새 해석으로 읽은 것 (다시 받지 않아요)
DART_RETRY_DAYS = 7
REPRT_KO = {"11011": "연간", "11013": "1Q", "11012": "2Q", "11014": "3Q"}
Q_NEWEST_FIRST = ("11014", "11012", "11013")
QUARTER_CURRENT_SHARE = 0.70   # 시가총액 상위 100곳 중 이만큼이 제출해야 그 분기를 '현재'로 봐요
DART_FATAL = {"010": "등록되지 않은 키", "011": "사용할 수 없는 키", "012": "접근할 수 없는 IP",
              "020": "일일 한도 초과", "901": "기간이 끝난 키"}
# v17.5.2: 2026-11-02 01:44–03:40 KST 에 러너가 opendart.fss.or.kr 에 아예 닿지 못해 모든 호출이 연결 시간 초과(25초)로 끝나고
# 실행이 2시간 동안 기어갔어요. 네트워크 예외(연결·응답 시간 초과, 연결 오류)가 이만큼 연달아 나면 이번 실행에서 DART 조회를 멈추고
# 보관본(캐시) 값만 써요. 서버가 한 번이라도 답하면(상태 코드와 상관없이) 다시 0부터 세요. 빠진 새 값은 검증의 채움 검사가 잡아요.
DART_DOWN_AFTER = 30


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
        self.redo_left = DART_REDO_PER_RUN    # v19.1e: 해석을 고친 항목 다시 받기 (실행당 한도 · 시도할 때 줄여요)
        self.redone = 0                       # 다시 받아 새 해석으로 저장한 수
        self.redo_kept = 0                    # 응답이 000 이 아니어서 예전 항목을 그대로 둔 수 (DART_RETRY_DAYS 뒤에 다시)
        self.redo_failed = 0                  # 연결 문제·해석 오류로 못 한 수 (다음 실행에 다시)
        self.net_streak = 0          # 연달아 난 네트워크 예외 수 (서버가 답하면 0)
        self.down = None             # DART 에 닿지 않아 조회를 멈췄으면 그때의 예외 이름
        self.skipped_down = 0        # 멈춘 뒤 건너뛴 조회 수
        self.entries, self.meta = {}, {}
        self._load()
        self.started_empty = not self.entries      # v19.1b: 빈 캐시로 시작 = 전체 DART 실행 (호출 수 어림을 로그로 남겨요)
        # v17.5.3: 정해진 시각 실행은 하루 여러 번이에요. 캐시가 비었거나(없음·읽지 못함·형식이 다름) 처음부터 조회하면
        # 그게 그날의 전체 DART 실행이 돼요 — 하루 한 번, 사람이(또는 Claude 가 규칙대로) 수동으로만 해요 (CLAUDE.md).
        # v17.5.5: 바깥 타이머(cron-job.org) 실행도 같아요 — 워크플로가 BAEPSAE_AUTO_RUN=1 을 넘겨요
        auto = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("BAEPSAE_AUTO_RUN") == "1"
        if auto and mode != "off" and not self.entries:
            raise RuntimeError("!! 정해진 시각 실행인데 DART 캐시가 비어 있어요 (없음·읽지 못함·형식이 다름). 처음부터 조회하는 "
                               "전체 DART 실행은 하루 한 번 수동으로만 해요 — DART 호출 전에 멈춰요")
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
            log("  !! DART 캐시 없음 → 처음부터 조회해요 (전체 DART 실행 · 호출 수 어림은 조회 직전에 남겨요)")
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
        """JSON 응답, 또는 실패하면 None. 상태 코드는 모두 집계해요.
        v17.5.2: 네트워크 예외가 DART_DOWN_AFTER 번 연달아 나면 그 뒤로는 바로 None (보관본을 써요 · 로그와 summary 에 크게 남아요)."""
        if self.fatal:
            return None
        if self.down:
            with self.lock:
                self.skipped_down += 1
            return None
        try:
            r = requests.get(self.BASE + endpoint, params={"crtfc_key": self.key, **params}, timeout=timeout)
        except Exception as e:
            net = isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
            tripped = False
            with self.lock:
                self.status["예외"] += 1
                if net:
                    self.net_streak += 1
                    if self.net_streak >= DART_DOWN_AFTER and not self.down:
                        self.down = type(e).__name__
                        tripped = True
            if tripped:
                log(f"  !! DART 연결 안 됨: 연속 {DART_DOWN_AFTER}회 실패({self.down}) → 이번 실행에서 DART 조회를 멈췄어요 "
                    "(보관본 값만 써요 · 빠진 새 값은 검증이 잡아요)")
            return None
        with self.lock:
            self.net_streak = 0          # 서버가 답했어요 (상태 코드·내용과 상관없이 연결은 돼요)
        try:
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

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        """캐시를 거쳐 보고서 하나를 조회합니다. 찾으면 parse 결과, 없으면 None.
        v19.1e: redo = (표시, 판정 함수). 해석을 고친 뒤, 찾은 보고서(000)로 저장된 항목이 이 표시 없이 판정 함수에 걸리면 (예: 자본금을
        못 읽은 사업보고서) 한 번 다시 받아 새 해석으로 저장해요 (표시를 붙여서 다시 받지 않아요). 실행당 DART_REDO_PER_RUN 건까지.
        다시 받은 응답이 000 이 아니면 예전 항목을 그대로 둬요 (찾은 보고서를 '없음'으로 바꾸지 않게)."""
        key = f"{corp}|{year}|{reprt}|{tag}"
        with self.lock:
            e = self.entries.get(key)
            # 찾은 보고서도 90일이 지나면 다시 확인 (정정공시). 실행당 300건까지, 실제로 쓰는 항목만.
            # DART 가 멈췄으면(self.down) 재확인하지 않아요: 칸만 쓰고 '재확인 N건'으로 잘못 세지 않게
            reval = bool(e and e["st"] == "000" and self.mode != "full" and self._stale(e) and self.revalidate_left > 0
                         and not self.down and not self.fatal)
            if reval:
                self.revalidate_left -= 1
                self.revalidated += 1
            rd = bool(redo and not reval and e and e["st"] == "000" and self.mode != "full" and redo_due(e, redo, self.today)
                      and self.redo_left > 0 and not self.down and not self.fatal)
            if rd:
                self.redo_left -= 1
        due = dart_entry_due(None if self.mode == "full" else e, year, reprt, self.today, revalidate=reval or rd)
        if not due:
            with self.lock:
                self.cache_hits += 1
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        j = self.get(endpoint, {"corp_code": corp, "bsns_year": str(year), "reprt_code": reprt, **(extra or {})})
        if j is None:          # 네트워크 문제·한도 초과: 예전에 찾은 값이 있으면 그대로 (집계에 남아요)
            if rd:
                with self.lock:
                    self.redo_failed += 1
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        st = str(j.get("status"))
        if rd and st != "000":            # 다시 받기는 찾은 값을 지우지 않아요. 며칠 뒤(DART_RETRY_DAYS) 다시 해 봐요
            with self.lock:
                self.redo_kept += 1
                self.entries[key] = {**e, "rpTry": self.today.isoformat()}   # 바꿔 끼워요 (저장 중인 dict 를 고치지 않게)
            return copy.deepcopy(e["d"])
        if st == "000":
            try:
                d = parse(j.get("list", []))
            except Exception as ex:          # 이상한 응답 하나가 실행 전체를 멈추지 않게 (개수는 로그로)
                with self.lock:
                    self.parse_errors[type(ex).__name__] += 1
                    if rd:
                        self.redo_failed += 1
                        self.entries[key] = {**e, "rpTry": self.today.isoformat()}
                return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        elif st == "013":
            d = None
        else:                  # 그 밖의 상태(점검 등)는 저장하지 않아요
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        with self.lock:
            self.entries[key] = {"st": st, "at": self.today.isoformat(), "d": d}
            if redo and st == "000":
                self.entries[key]["rp"] = redo[0]     # 새 해석으로 읽었어요
            if rd:
                self.redone += 1
        return copy.deepcopy(d)

    def company(self, corp, ttl_days=None):
        """DART 기업개황(company.json)의 업종 코드(KSIC). 업종은 거의 안 바뀌어서 180일(+기업마다 0~59일) 보관해요.
        찾은 값은 {"induty": "264"} · 못 찾으면 None (네트워크 문제면 예전 값)."""
        ttl_days = COMPANY_TTL_DAYS if ttl_days is None else ttl_days
        key = f"{corp}|company"
        with self.lock:
            e = self.entries.get(key)
        if e and e["st"] == "000":     # full 모드에서도 보관본을 써요 (업종은 거의 안 바뀌고, 하루 한도를 아껴요)
            jitter = int(hashlib.md5(corp.encode()).hexdigest(), 16) % 60     # 같은 날 한꺼번에 만료되지 않게
            if (self.today - dt.date.fromisoformat(e["at"])).days < ttl_days + jitter:
                with self.lock:
                    self.cache_hits += 1
                return copy.deepcopy(e["d"])
        j = self.get("company.json", {"corp_code": corp})
        if j is None or str(j.get("status")) != "000":
            return copy.deepcopy(e["d"]) if e and e["st"] == "000" else None
        d = {"induty": str(j.get("induty_code") or "").strip()}
        with self.lock:
            self.entries[key] = {"st": "000", "at": self.today.isoformat(), "d": d}
        return copy.deepcopy(d)

    def summary(self):
        st = ", ".join(f"{k} {v:,}" for k, v in sorted(self.status.items()))
        extra = f" · 재확인 {self.revalidated:,}건" if self.revalidated else ""
        tried = DART_REDO_PER_RUN - self.redo_left
        if tried:
            extra += (f" · 자본금 다시 읽기 {tried:,}건 시도 (실행당 최대 {DART_REDO_PER_RUN:,}): 새로 읽음 {self.redone:,}"
                      + (f" · !! 찾은 보고서가 없다고 해 예전 값을 둔 {self.redo_kept:,}" if self.redo_kept else "")
                      + (f" · !! 연결 문제·해석 오류 {self.redo_failed:,}" if self.redo_failed else ""))
        if self.parse_errors:
            extra += " · !! 해석 오류 " + ", ".join(f"{k} {v}" for k, v in self.parse_errors.items())
        if self.down:
            extra += (f" · !! DART 연결 안 됨: 연속 {DART_DOWN_AFTER}회 실패({self.down}) → 이번 실행에서 DART 조회를 멈췄어요"
                      f" (건너뛴 조회 {self.skipped_down:,}회 · 보관본 값만 씀)")
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


# v19.1e: 배당 분할 확인용 자본금. 2026-11-07 국내 배당 종목 132곳의 배당을 확인하지 못했는데 그중 47곳은 재무상태표의 자본금 줄을
# 못 읽어서였어요: 이름이 '보통주자본금'(기아) · '(1) 자본금'(고려아연) · '납입자본'(삼성에스디에스) · 'Ⅰ. 자본금'이거나, 손익 줄을
# 못 알아본 재무제표(은행·증권 · '영업손실' 이름)는 3년 원값(_fin)을 통째로 버리면서 자본금도 같이 버렸어요(카카오뱅크 · 롯데케미칼).
# 그래서 자본금은 _fin 과 따로 _cap 에 담아요. 고르는 순서 (재무상태표, 이름의 띄어쓰기와 앞 번호 'Ⅰ.' '(1)' '1.' 는 빼고):
#   1. '자본금' — 회사 전체 자본금
#   2. 보통주자본금 — 보통주만이라고 표시해요(k common): 분할 확인의 아래 끝을 오늘 보통주 수로만 계산해요. 우선주자본금을 더하지
#      않아요: 더한 줄이 상장되지 않은 상환전환우선주이거나 상장 우선주가 다른 이름(종류주식자본금 …)이면 합이 실제보다 작아지고,
#      작은 자본금은 아래 끝을 키워 틀린 배율로 맞출 수 있어요 (리뷰 2026-11-07).
#   3. 이름에 '납입자본'이 들어간 줄(납입자본 · 납입자본금 · 보통주납입자본)과 그 밖의 IssuedCapital 줄 — 주식발행초과금이 섞여
#      실제보다 클 수 있어요. 올해 아래 끝에만 써요: 크면 아래 끝이 작아져 범위가 넓어질 뿐이라(후보가 늘면 '알 수 없음') 틀린 배율로
#      맞추지 않아요. 앞 해와의 비교(자본금의 비 = 주식 수의 비)에는 쓰지 않아요: 주식발행초과금으로 한 무상증자는 주식 수를 늘려도
#      납입자본이 그대로라 '그대로'로 잘못 볼 수 있어서 (리뷰 2026-11-07). src paid.
#      자본잠식 확인(_fin.cs)에는 쓰지 않아요: 자본금이 실제보다 크면 없는 자본잠식을 경고할 수 있어서 (그건 예전처럼 '자본금'만).
CAP_COMMON_IDS = ("dart_IssuedCapitalOfCommonStock", "ifrs-full_IssuedCapitalOrdinaryShares")
CAP_PREF_IDS = ("dart_IssuedCapitalOfPreferredStock", "ifrs-full_IssuedCapitalPreferenceShares")
_ACCT_NO = re.compile(r"^(?:\(\d+\)|\d+\.|[IVX]+\.|[\u2160-\u216B]+\.?)")


_ACCT_NOTE = re.compile(r"\((?:주석|주)?[\d,]+\)$")


def acct_name(nm):
    """계정 이름에서 띄어쓰기, 앞 번호(Ⅰ. · I. · (1) · 1.), 끝의 주석 번호('(주석15)' · '(주15)')를 뺀 것. (순수 함수)"""
    return _ACCT_NOTE.sub("", _ACCT_NO.sub("", (nm or "").replace(" ", "")))


def cap_kind(nm, aid):
    """재무상태표 한 줄이 자본금이면 그 종류, 아니면 None. (순수 함수)
    total 회사 전체 자본금 · common 보통주자본금 · pref 우선주 자본금(쓰지 않아요) · paid 납입자본(크게 잡힐 수 있음) ·
    paidCommon 보통주 납입자본."""
    n = acct_name(nm)
    if any(w in n for w in ("잉여", "조정", "총계", "비지배", "기타", "합계")):
        return None
    if n == "자본금":
        return "total"
    capish = "자본금" in n or "납입자본" in n
    if (capish and ("우선주" in n or "종류주" in n)) or aid in CAP_PREF_IDS:
        return "pref"
    if "납입자본" in n:
        return "paidCommon" if "보통주" in n else "paid"
    if (capish and "보통주" in n) or aid in CAP_COMMON_IDS:
        return "common"
    if aid == "ifrs-full_IssuedCapital":
        return "paid"
    return None


def parse_capital(rows):
    """재무상태표에서 배당 분할 확인용 자본금 3년 (위 순서) → {"cs3": [억원 ×3], "k": "all"|"common", "src": total|common|paid}
    또는 None. src paid 는 올해 값만 믿을 수 있어요 (div_basis 가 앞 해 비교에 쓰지 않아요).
    ss3 는 자본잉여금 3년 (이름의 앞 번호를 빼고 '자본잉여금'인 첫 줄). (순수 함수)"""
    first = {}
    ss3 = None
    for row in rows:
        if (row.get("sj_div") or "").strip() not in ("BS", ""):
            continue
        tri = [_num(row.get(k)) for k in ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount")]
        if acct_name(row.get("account_nm")) == "자본잉여금" and ss3 is None:
            ss3 = tri
            continue
        k = cap_kind(row.get("account_nm"), (row.get("account_id") or "").strip())
        if k and k not in first:
            first[k] = tri
    if "total" in first:
        v, kind, src = first["total"], "all", "total"
    elif "common" in first:
        v, kind, src = first["common"], "common", "common"
    elif "paid" in first:
        # 우선주 줄이 따로 있으면 납입자본이 보통주만일 수 있어요: 보통주만으로 보면 아래 끝이 늘 맞아요 (리뷰 2026-11-07)
        v, kind, src = first["paid"], ("common" if "pref" in first else "all"), "paid"
    elif "paidCommon" in first:
        v, kind, src = first["paidCommon"], "common", "paid"
    else:
        return None
    if not any(x is not None and x > 0 for x in v):
        return None
    out = {"cs3": [round(x / 1e8, 4) if x is not None else None for x in v], "k": kind, "src": src}
    if ss3 and any(x is not None for x in ss3):
        out["ss3"] = [round(x / 1e8, 4) if x is not None else None for x in ss3]
    return out


def redo_due(e, redo, today):
    """캐시 항목 e 를 해석을 고친 뒤 다시 받아야 하는지: 표시(rp)가 없고, 판정 함수에 걸리고, 지난번 다시 받기에서 찾은 보고서가
    없다는 답(rpTry)을 받은 지 DART_RETRY_DAYS 가 지났을 때. (순수 함수)"""
    if not e or e.get("st") != "000" or e.get("rp") == redo[0] or not redo[1](e.get("d")):
        return False
    t = e.get("rpTry")
    return not t or (today - dt.date.fromisoformat(t)).days >= DART_RETRY_DAYS


def capital_backlog(entries, years, today):
    """자본금 없이 저장돼 다시 받을 사업보고서 항목 수 (그 해들의 연결·별도). (순수 함수)"""
    tails = tuple(f"|{y}|11011|{fs}" for y in years for fs in ("CFS", "OFS"))
    return sum(1 for k, e in entries.items() if k.endswith(tails) and redo_due(e, (CAP_REDO_TAG, needs_capital), today))


def needs_capital(d):
    """캐시에 찾은 보고서로 저장된 사업보고서 해석 결과가 배당 분할 확인용 자본금 없이 저장됐는지 (v19.1e 이전 해석). (순수 함수)"""
    return isinstance(d, dict) and "_cap" not in d and not (d.get("_fin") or {}).get("cs3")


# v19.1f (Jack, 2026-11-07): 손익계산서의 매출·영업이익·순이익을 예전 이름으로 못 찾으면 이름의 앞 번호(Ⅲ. · V.)를 빼고 더 많은
# 이름('영업손실' · '영업손익' · '당기순손실' …)으로, 그래도 없으면 표준 계정 코드로 찾아요. 2026-11-07 발행본에서 재무제표를 읽고도
# 매출·영업이익·순이익이 모두 빈 회사가 51곳이었어요 (롯데케미칼 '영업손실' · 넷마블 'Ⅲ.영업손익' · 코오롱인더 'V.영업이익').
# 예전 이름으로 찾던 회사는 값이 그대로예요 (먼저 예전 규칙, 못 찾을 때만 새 규칙).
# 금액은 표준 계정(dart_OperatingIncomeLoss · ifrs-full_ProfitLoss)의 부호를 그대로 써요: 손실이면 음수. 2026-11-07 실제 재무제표에서
# '영업손실'(롯데케미칼 −9,431억)과 '당기순손실' 12곳이 모두 음수였어요. 그래서 이름이 손실뿐인 줄('영업손실' · '당기순손실')의 올해
# 값이 양수면 잘못 적은 것으로 보고 쓰지 않아요 (로그에 남겨요).
INC_NAMES = {
    "rev": ("매출액", "수익(매출액)", "영업수익", "매출", "매출액(영업수익)", "영업수익(매출액)"),
    "op": ("영업이익", "영업이익(손실)", "영업손실", "영업손익", "영업손실(이익)"),
    "ni": ("당기순이익", "당기순이익(손실)", "연결당기순이익", "당기순손실", "당기순손익", "당기순손실(이익)",
           "연결당기순이익(손실)", "연결당기순손익", "연결당기순손실"),
}
INC_IDS = {"rev": ("ifrs-full_Revenue",), "op": ("dart_OperatingIncomeLoss",), "ni": ("ifrs-full_ProfitLoss",)}
LOSS_ONLY = ("영업손실", "당기순손실", "연결당기순손실")
INC_SEEN = collections.Counter()        # 새 규칙으로 찾은 줄 · 부호가 틀려 버린 줄 (이번 실행에서 받은 재무제표만 · 실행 로그용)
_INC_LOCK = threading.Lock()


def income_fallback(rows, key, value):
    """예전 이름으로 못 찾은 손익 항목(key: rev · op · ni)을 손익계산서(IS · CIS)에서 다시 찾아요 → value(row) 또는 None.
    1) 앞 번호를 뺀 이름이 INC_NAMES 2) 표준 계정 코드 INC_IDS. 이름이 손실뿐인데 올해 값이 양수면 쓰지 않아요. (거의 순수 함수)"""
    cands = [r for r in rows if (r.get("sj_div") or "").strip() in ("IS", "CIS")]
    hit = next((r for r in cands if acct_name(r.get("account_nm")) in INC_NAMES[key]), None)
    if hit is None:
        # 표준 계정 코드는 그 코드를 단 줄이 하나뿐일 때만 (둘 이상이면 제품별 매출 같은 아랫줄일 수 있어서)
        coded = [r for r in cands if (r.get("account_id") or "").strip() in INC_IDS[key]]
        hit = coded[0] if len(coded) == 1 else None
        if len(coded) > 1:
            with _INC_LOCK:
                INC_SEEN[f"{key}:many"] += 1
    if hit is None:
        return None
    v = value(hit)
    cur = v[0] if isinstance(v, list) else v
    if acct_name(hit.get("account_nm")) in LOSS_ONLY and cur is not None and cur > 0:
        with _INC_LOCK:
            INC_SEEN[f"{key}:sign"] += 1
        return None
    with _INC_LOCK:
        INC_SEEN[key] += 1
    return v


# v19.1f (Jack, 2026-11-07): 이자보상배율의 이자. 손익계산서에 '이자비용' 줄이 있으면 그것, 없으면 현금흐름표의 이자 지급 줄을 모두
# 더한 값(양수로)이에요. 예전에는 '금융비용'(환손실·파생상품 손실까지 든 금융원가)도 이자로 읽었어요 — 2026-11-07 경고 505곳 중 502곳.
# 이자 지급 줄: 표준 계정 ifrs-full_InterestPaidClassifiedAs…(영업·투자·재무활동). 그런 줄이 하나도 없을 때만 표준 계정이 없는 줄 중
# 이름에 '이자'와 '지급'('지출' · '납부')이 든 줄. 이자의 수취(받은 이자)는 절대 아니에요. 신종자본증권 이자(dart_InterestPaidToHybridBond)는
# 회계상 자본에 대한 분배라 빼요 (HYBRID_INTEREST — Jack 확인 대기).
HYBRID_INTEREST = False
_NO_ID = ("-표준계정코드 미사용-", "")


def interest_paid_rows(rows):
    """현금흐름표에서 이자 지급 줄들 (위 규칙, 같은 줄이 두 번 나와도 한 번). (순수 함수)"""
    cf = [r for r in rows if (r.get("sj_div") or "").strip() == "CF"]

    def received(n):
        return any(w in n for w in ("수취", "수입", "수령", "수익", "받은"))
    by_id = [r for r in cf if (r.get("account_id") or "").strip().startswith("ifrs-full_InterestPaid")
             and not received(acct_name(r.get("account_nm")))]
    if HYBRID_INTEREST:
        by_id += [r for r in cf if (r.get("account_id") or "").strip() == "dart_InterestPaidToHybridBond"]
    picked = by_id or [r for r in cf if (r.get("account_id") or "").strip() in _NO_ID
                       and "이자" in acct_name(r.get("account_nm")) and not received(acct_name(r.get("account_nm")))
                       and "신종자본" not in acct_name(r.get("account_nm"))
                       and any(w in acct_name(r.get("account_nm")) for w in ("지급", "지출", "납부"))]
    seen, out = set(), []
    for r in picked:
        k = ((r.get("account_id") or "").strip(), acct_name(r.get("account_nm")), r.get("thstrm_amount"))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def interest_paid(rows, value):
    """이자 지급 줄들의 합 (양수) → 원, 줄이 없거나 값이 하나도 없으면 None. value(row) 는 그 줄의 값. (순수 함수)"""
    vals = [value(r) for r in interest_paid_rows(rows)]
    vals = [abs(v) for v in vals if v is not None]
    return sum(vals) if vals else None


def parse_dart_list(rows):
    """fnlttSinglAcntAll 응답의 계정 목록에서 3개년 주요 항목을 뽑습니다. (순수 함수 — 테스트 가능)
    v19.1e: 배당 분할 확인용 자본금은 손익 줄과 상관없이 _cap 에 담아요 (parse_capital).
    v19.1f: 예전 이름으로 못 찾은 매출·영업이익·순이익은 income_fallback 으로. 이자는 '이자비용'(ie)과 현금흐름표 이자 지급액(iec)."""
    def tri(row):
        return [_num(row.get("thstrm_amount")), _num(row.get("frmtrm_amount")), _num(row.get("bfefrmtrm_amount"))]
    rev = op = ni = None
    eq = li = nio = eqo = cash = ocf = ca = cl = cs = ie = None
    cs3 = ss3 = None
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
            cs3 = tri(row)            # v19.1b: 3년 자본금 — 액면가로 나누면 그해 말 발행 주식 수의 상한 (배당 분할 확인)
        elif nm == "자본잉여금" and sj in ("BS", "") and ss3 is None:
            ss3 = tri(row)            # v19.1b: 3년 자본잉여금 — 무상증자(늘지 않음)와 유상증자(주식발행초과금으로 늚)를 가려요
        elif acct_name(nm) == "이자비용" and sj in ("IS", "CIS") and ie is None:
            ie = _num(row.get("thstrm_amount"))       # v19.1f: 손익계산서의 이자비용만 (금융비용 · 금융원가는 이자가 아니에요)
        elif sj == "CF" and nm in ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로인한순현금흐름") and ocf is None:
            ocf = _num(row.get("thstrm_amount"))
        elif sj == "CF" and nm in ("감가상각비", "유형자산감가상각비", "무형자산상각비", "사용권자산상각비", "투자부동산감가상각비"):
            v = _num(row.get("thstrm_amount"))
            if v and v > 0:
                dep += v
                has_dep = True
        elif nm == "부채총계" and li is None:
            li = _num(row.get("thstrm_amount"))
    if rev is None:
        rev = income_fallback(rows, "rev", tri)
    if op is None:
        op = income_fallback(rows, "op", tri)
    if ni is None:
        ni = income_fallback(rows, "ni", tri)
    iec = interest_paid(rows, lambda r: _num(r.get("thstrm_amount")))
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
           "ca": ek(ca), "cl": ek(cl), "cs": ek(cs), "ie": ek(ie), "iec": ek(iec)}
    if cs3 and any(v is not None for v in cs3):
        fin["cs3"] = [round(v / 1e8, 4) if v is not None else None for v in cs3]     # 억원 · 1만원 단위까지 (주식 수 계산용)
    if ss3 and any(v is not None for v in ss3):
        fin["ss3"] = [round(v / 1e8, 4) if v is not None else None for v in ss3]
    if any(v is not None for a in (fin["rev"], fin["op"], fin["ni"]) for v in a):
        out["_fin"] = fin
    cap = parse_capital(rows)
    if cap:
        out["_cap"] = cap
    return out


G3_MIN_REV = 0.1     # 억원 — 매출 성장률(g3)을 낸 두 해의 매출이 발행되는 값(억원, 소수 한 자리)으로 이 이상일 때만 g3 를 내요


def g3_usable(rev, g3):
    """parse_dart_list 가 낸 g3 를 발행해도 되는지. (순수 함수)
    rev 는 발행되는 매출 [당기, 전기, 전전기] (억원). g3 를 계산한 두 해의 매출이 모두 G3_MIN_REV 이상일 때만 참이에요.
    v17.5.2: 2026-11-03 발행본의 코오롱티슈진은 매출이 [0.0, 0.0, 0.0] 인데 g3 가 13.0 이었어요 — 반올림하면 0 인 아주 작은
    매출(외화로 낸 재무제표)로 계산된 값이에요. DART 캐시는 '해석된 값'을 담고 있어서 parse_dart_list 를 고치면 캐시를 통째로
    버려야 해요(전체 조회 약 15,000회). 그래서 해석은 그대로 두고 캐시 뒤 여기서 걸러요."""
    if _fin(g3) is None:
        return False
    r0, r1, r2 = (list(rev or []) + [None, None, None])[:3]
    ok = lambda x: _fin(x) is not None and x >= G3_MIN_REV
    if not ok(r0):
        return False
    if ok(r2):
        return True                            # 전전기 대비 연평균 (parse_dart_list 의 첫 갈래)
    if not ok(r1):
        return False
    if _fin(r2) is not None and abs(r2) < G3_MIN_REV:
        # 전전기가 0.0 으로 보여요: 0 원이었으면 전기 대비 1년 성장이고, 아주 작은 양수였으면 그 작은 값 대비 연평균이었어요.
        # 전기 대비 1년 성장으로 설명되는 값(발행 값의 반올림 ±0.05억원 안)일 때만 남겨요.
        h = G3_MIN_REV / 2
        lo, hi = ((r0 - h) / (r1 + h) - 1) * 100, ((r0 + h) / (r1 - h) - 1) * 100
        return lo - 0.05 <= g3 <= hi + 0.05
    return True                                # 전전기가 빈 칸·음수 → 전기 대비 1년 성장


DASHES = {"-", "－", "—", "–", "‐"}


def _num_or_dash0(x):
    """배당 표의 숫자. 표에 줄은 있는데 값이 '-' 면 '없음' = 0 이에요 (v17.5.1: 0 과 '모름'을 구분)."""
    if x is not None and str(x).strip() in DASHES:
        return 0.0
    return _num(x)


AMOUNT_UNITS = {"백만원": 1e6, "천원": 1e3, "원": 1.0}


def _amount_unit(se):
    """배당 표 항목 이름 끝의 단위 '(백만원)' → 1e6 (원으로 바꾸는 곱). 단위가 없거나 모르는 단위면 None."""
    m = re.search(r"\((백만원|천원|원)\)$", se)
    return AMOUNT_UNITS[m.group(1)] if m else None


def _tri3(row, conv, mult=1.0):
    return [None if v is None else v * mult for v in (conv(row.get(k)) for k in ("thstrm", "frmtrm", "lwfr"))]


def parse_dart_basis(rows):
    """v19.1b: 같은 배당 표에서 해마다의 '주식 수'를 거꾸로 셀 수 있는 값들 (당기·전기·전전기). (순수 함수)
    cash3 현금배당금총액(원) · pdps 우선주·종류주마다 주당 현금배당금 3년(원) · par3 주당액면가액(원) · eps3 회사가 낸 주당순이익(원) ·
    ni3 그 주당순이익과 같은 기준(연결/별도)의 당기순이익(원) · epsB 그 기준.
    총액의 '-' 는 0(배당 없음), 순이익·주당순이익·액면가의 '-' 는 모름. 하나도 없으면 None."""
    out, eps_by, ni_by = {}, {}, {}
    for row in rows:
        se = (row.get("se") or "").replace(" ", "")
        knd = (row.get("stock_knd") or "").strip()
        unit = _amount_unit(se)
        basis = "연결" if "(연결)" in se else ("별도" if "(별도)" in se else "")
        if se.startswith("주당액면가액") and "par3" not in out:
            out["par3"] = _tri3(row, _num)
        elif se.startswith("현금배당금총액") and unit and "cash3" not in out:
            out["cash3"] = _tri3(row, _num_or_dash0, unit)
        elif "주당현금배당금" in se and knd and knd not in DASHES and "보통" not in knd:
            out.setdefault("pdps", []).append(_tri3(row, _num_or_dash0))   # 우선주·종류주마다 (보통주 1주 기준 무게를 재요)
        elif "주당순이익" in se and "희석" not in se:
            eps_by.setdefault(basis, _tri3(row, _num))
        elif "당기순이익" in se and unit:
            ni_by.setdefault(basis, _tri3(row, _num, unit))
    for b in ("연결", "별도", ""):
        if any(v is not None for v in eps_by.get(b) or []):
            out.update(eps3=eps_by[b], ni3=ni_by.get(b) or [None, None, None])
            if b:
                out["epsB"] = b                            # DART 표의 이름 그대로 (연결 · 별도) — 표에 구분이 없으면 칸 없음
            break
    if not any(k in out for k in ("cash3", "par3", "eps3")):
        return None
    return out


def parse_dart_dividend(rows):
    """alotMatter(배당에 관한 사항) 응답에서 보통주 배당 지표를 뽑습니다. (순수 함수)
    v17.5.1: 주당 배당금 0 원(표에 '-')도 '배당 없음'이라는 사실이라 0 으로 남겨요. 줄 자체가 없으면 '모름'(빈 칸).
    v19.1b: 표에 총액·액면가·주당순이익 줄이 있으면 'bas'(parse_dart_basis)도 함께 담아요 (분할 확인용)."""
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
    bas = parse_dart_basis(rows)
    if bas:
        out["bas"] = bas
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
            elif acct_name(nm) == "이자비용" and ie is None: ie = _ytd(row)     # v19.1f: 이자비용만 (금융비용은 이자가 아니에요)
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
    # v19.1f: 예전 이름으로 못 찾은 매출·영업이익·순이익 (연간과 같은 규칙 · 분기는 '영업이익(손실)'도 예전엔 못 찾았어요)
    if rev is None:
        rev = income_fallback(rows, "rev", _ytd)
    if op is None:
        op = income_fallback(rows, "op", _ytd)
    if ni is None:
        ni = income_fallback(rows, "ni", _ytd)
    iec = interest_paid(rows, _ytd)
    if rev is None and ni is None:
        return None
    return {"rev": ek(rev), "op": ek(op), "ni": ek(ni), "nio": ek(nio), "ocf": ek(ocf), "ie": ek(ie), "iec": ek(iec),
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
           "ie": flow(fin.get("ie"), ytd.get("ie"), ytd_prev.get("ie")),
           "iec": flow(fin.get("iec"), ytd.get("iec"), ytd_prev.get("iec"))}     # v19.1f: 현금흐름표 이자 지급액
    if ttm["rev"] is None and ttm["ni"] is None:
        return None
    bs = {k: ytd.get(k) for k in ("eq", "eqo", "bor", "cash", "ca", "cl", "cs") if ytd.get(k) is not None}
    return {"ttm": ttm, "bs": bs}


def dart_financials(client, corp_code, year):
    """연결(없으면 별도) 사업보고서에서 주요 지표 + 3개년 원값.
    v19.1e: 자본금(_cap)만 읽힌 연결 재무제표는 예전처럼 '못 찾음'으로 보고 별도로 넘어가요 (어느 재무제표를 쓰는지 바뀌지 않게).
    자본금 없이 저장된 예전 항목은 한 번 다시 받아요 (needs_capital · CAP_REDO_TAG)."""
    for fs in ("CFS", "OFS"):
        d = client.report("fnlttSinglAcntAll.json", corp_code, year, "11011", fs, parse_dart_list, {"fs_div": fs},
                          redo=(CAP_REDO_TAG, needs_capital))
        if d and any(k != "_cap" for k in d):
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


def dart_full_estimate(n_companies, ksic=True):
    """v19.1b: 처음부터 받는 전체 DART 실행의 호출 수 어림 → (합계, 설명). (순수 함수)
    재무·배당·분기 기업당 4.8회(지난 전체 실행의 평균) + 업종 코드 기업당 1회(캐시가 비었을 때) + 기업코드 목록 1회 + 공시 최대 1,430회.
    상한이 아니라 어림이에요 — 실제 호출 수는 실행 끝에 남기고, 목표(16,000)를 넘으면 크게 알려요."""
    main_ = math.ceil(n_companies * DART_PER_COMPANY)
    ks = n_companies if ksic else 0
    total = main_ + ks + 1 + DART_DISC_MAX
    why = (f"재무·배당·분기 {main_:,} + 업종 코드 {ks:,} + 기업코드 목록 1 + 공시 최대 {DART_DISC_MAX:,}")
    return total, why


def enrich_with_dart(kr_stocks, client):
    """사업보고서·배당·분기보고서(TTM)를 붙입니다. 기업마다 분기를 따로 확인해요 (3Q → 2Q → 1Q)."""
    fin_map = {}
    today = client.today
    old = [k for k in client.entries if k.endswith("|DIV")]
    for k in old:                       # v17.5.1: 옛 해석('-' = 모름)으로 저장된 배당 항목은 버려요 (DIV2 로 다시 받아요)
        del client.entries[k]
    if old:
        log(f"· DART 캐시: 옛 배당 항목 {len(old):,}건을 지웠어요 (새 해석 DIV2 로 다시 받아요)")
    cmap = dart_corp_map(client)
    year = today.year - 1
    backlog0 = capital_backlog(client.entries, (year, year - 1), today) if client.mode != "full" else 0
    if backlog0:
        log(f"· DART 자본금 다시 읽기 대상: 자본금 없이 저장된 {year - 1}~{year}년 사업보고서 {backlog0:,}건 — 이번 실행에서 쓰는 것 중 "
            f"최대 {DART_REDO_PER_RUN:,}건 (v19.1e · 배당 분할 확인용)")
    targets = [s for s in kr_stocks if s["t"] in cmap]
    if client.started_empty or client.mode == "full":
        est, why = dart_full_estimate(len(targets), ksic=client.started_empty)
        loud = est > DART_FULL_TARGET
        log(f"{'  !! ' if loud else '· '}전체 DART 실행 호출 수 어림: 약 {est:,}회 ({why}) · 하루 한도 {DART_DAY_LIMIT:,} · "
            f"목표 {DART_FULL_TARGET:,} 아래" + (" — 목표를 넘어요" if loud else ""))
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
    g3_cut = []                            # 쓸 만한 매출 없이 계산된 g3 를 비운 종목

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
        if div.get("bas"):
            s["_bas"] = div["bas"]        # v19.1b: 분할 확인용 원값 — apply_div_basis 가 쓰고 지워요 (파일에 나가지 않아요)
        cap = f.pop("_cap", None) if f else None
        if cap:
            s["_cap"] = cap               # v19.1e: 분할 확인용 자본금 — apply_div_basis 가 쓰고 지워요 (파일에 나가지 않아요)
        if f or any(div.get(k) is not None for k in ("dps", "dps3", "dy")):   # 분할 확인용 값(bas)만으로는 fy 를 달지 않아요
            s["fy"] = yr          # v17.5.1: op·debt·roe·dps·dps3 가 나온 사업보고서의 연도 (bq 는 TTM 분기만 뜻해요)
        if f:
            fin = f.pop("_fin", None)
            if f.get("g3") is not None and not g3_usable((fin or {}).get("rev"), f["g3"]):
                f.pop("g3")
                with client.lock:
                    g3_cut.append(f"{s['t']} {s.get('nk', '')}".strip())
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
    log(f"{'  !! ' if any(k.endswith(':sign') for k in INC_SEEN) else '· '}손익 줄 새 규칙 (이번 실행에서 받은 재무제표 · 예전 이름으로 "
        f"못 찾은 줄): 매출 {INC_SEEN['rev']:,} · 영업이익 {INC_SEEN['op']:,} · 순이익 {INC_SEEN['ni']:,} · 이름이 손실인데 올해 값이 "
        f"양수라 버린 줄 {sum(v for k, v in INC_SEEN.items() if k.endswith(':sign')):,} · 같은 코드가 여러 줄이라 안 쓴 항목 "
        f"{sum(v for k, v in INC_SEEN.items() if k.endswith(':many')):,}")
    if backlog0:
        left = capital_backlog(client.entries, (year, year - 1), today)
        capped = client.redo_left <= 0
        log(f"{'  !! ' if capped else '· '}DART 자본금 다시 읽기: 대상 {backlog0:,}건 중 남은 {left:,}건"
            + (f" — 실행당 한도({DART_REDO_PER_RUN:,})에 닿았어요. 다음 실행에서 이어서 받아요" if capped
               else " (이번 실행에서 쓰지 않은 항목 · 며칠 뒤 다시 해 볼 항목)" if left else ""))
    try:
        log(f"· DART 캐시 저장: {len(client.entries):,}건 · {os.path.getsize(client.path) / 1e6:.1f}MB ({client.path})")
    except OSError as e:
        log(f"  !! DART 캐시 파일을 확인하지 못했어요: {e}")
    if errors:
        log(f"  !! DART 처리 오류 {sum(errors.values()):,}곳 ({dict(errors)}) — 그 기업은 재무지표 없이 진행해요")
    n_g3 = sum(1 for s in targets if s.get("g3") is not None)
    log(f"· 매출 성장률(g3): {n_g3:,}곳 · 계산에 쓴 매출이 {G3_MIN_REV:g}억원 미만이라 비운 곳 {len(g3_cut)}"
        + (f": {', '.join(sorted(g3_cut)[:12])}{'…' if len(g3_cut) > 12 else ''}" if g3_cut else ""))
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


def carry_prev_nps(fresh, prev_nps, bgn):
    """새로 받은 국민연금 항목 + 그 회사가 없는 지난 발행본 항목(조회 기간 bgn 이후만). 공시일은 그대로 둬요 (다시 날짜를 붙이지 않아요).
    새로 받은 회사는 새 값이 이겨요. (순수 함수) 반환: (합친 목록 최신순, 가져온 지난 항목 수)."""
    have = {r.get("t") for r in fresh}
    old = [r for r in prev_nps if r.get("t") not in have and str(r.get("d") or "") >= bgn]
    return sorted(fresh + old, key=lambda r: r.get("d", ""), reverse=True), len(old)


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
    # v17.5.2: 공시 목록을 못 받았거나 DART 연결이 끊기면 국민연금 목록이 통째로 비어 앱에 '최근 90일 내 국민연금 보고가 없어요'
    # (사실이 아님)가 떠요. 지난 발행본의 항목을 자기 공시일 그대로 둬요. 내부자 거래는 원래 지난 발행본에 이어 붙여요(위 rows).
    # 화면의 날짜(newest)는 실행일이 아니라 가장 최근 공시일이라, 오래 못 받으면 앱이 '갱신이 멈췄어요'로 알려요.
    if not list_ok or getattr(client, "down", None):
        nps, carried = carry_prev_nps(nps, prev.get("nps", []), bgn)
        n_ins = sum(1 for r in prev.get("insider", []) if str(r.get("d") or "") >= bgn)
        old_ds = [str(r.get("d")) for r in prev.get("nps", []) + prev.get("insider", []) if r.get("d") and str(r["d"]) >= bgn]
        last = max(old_ds) if old_ds else None
        why = "공시 목록을 받지 못해" if not list_ok else "DART 연결이 끊겨"
        log(f"  !! {why} 지난 발행본의 {carried + n_ins:,}건을 그대로 둬요 "
            f"(최근 공시 {f'{last[:4]}-{last[4:6]}-{last[6:8]}' if last else '없음'}) · 국민연금 {carried:,} · 내부자 {n_ins:,}")
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


FIN_SECS = {"bank", "insure", "broker", "holding"}    # EV 계열 멀티플을 빼는 업종 (그대로)
# v19.1d (Jack, 2026-11-07): 유동비율·이자보상배율은 재무제표에 필요한 줄이 있으면 업종과 상관없이 돌려요. 은행·보험·증권과
# 금융 지주(KB금융·신한지주 …: 업종 그룹이 은행·보험·증권·금융)만 해당 없음(flNa). 그 밖의 지주회사(LG·GS·CJ …)는 이제 돌려요.
FL_FIN_SECS = {"bank", "insure", "broker"}
FL_FIN_INDS = {"bank", "insurance", "securities", "finance", "fin"}   # data/industry_groups.csv 의 financial=yes 그룹과 같아요
# 금융 지주 (업종 그룹이 industry_overrides.csv 에서 와요): 이 회사들이 금융으로 잡히지 않으면 크게 남겨요
FL_FIN_HOLDINGS = ("105560", "055550", "086790", "316140", "138930", "139130", "175330", "138040", "071050")
# v19.1d (Jack, 2026-11-07): 이자보상배율을 잠시 모든 회사에서 꺼요. 2026-11-07 경고 505곳 중 502곳이 '이자비용'이 아니라 환손실·
# 파생상품 손실까지 든 '금융비용'으로 계산됐어요 (두산에너빌리티 0.65배 → 실제 이자 지급액으로는 약 2.0배). 이자비용, 없으면
# 현금흐름표의 이자 지급액으로 다시 읽는 PR(v19.1f, 전체 DART 다시 읽기)이 이 스위치를 끄고 바른 값으로 다시 켜요.
# 꺼져 있으면 숫자도, 그 확인에 기대는 '경고 신호는 없어요'도 없어요 (flRan 에 icr 없음 · flWhy.icr "off" — 앱은 아무 말도 안 해요).
# v19.1f: 다시 켜요. 이자는 손익계산서의 '이자비용'(flSrc.icr "is"), 없으면 현금흐름표의 이자 지급액(flSrc.icr "cf").
ICR_OFF = False


def fl_unknown_holding(s):
    """업종 그룹(ind)이 없는 지주회사 — 금융 지주인지 알 수 없어서 두 검사를 돌리지도, 해당 없음으로 치지도 않아요. (순수 함수)"""
    return not s.get("ind") and (s.get("s") or "etc") == "holding"


def fl_financial(s):
    """재무 경고의 유동비율·이자보상배율이 해당 없는 금융회사인지. 업종 그룹(ind)이 있으면 그것으로만, 없을 때만 업종(s)으로 봐요
    (순수 함수). 업종 s 는 거칠어요: 2026-11-06 데이터에서 DB손해보험·현대해상은 s 가 auto(보험인데 두 검사를 돌림), 지씨셀은
    bank, 신원·제이에스티나·한국기업평가는 broker(금융이 아닌데 건너뜀)였어요. 업종 그룹은 둘 다 맞게 잡아요."""
    ind = s.get("ind")
    if ind:
        return ind in FL_FIN_INDS
    return (s.get("s") or "etc") in FL_FIN_SECS


CORP_DIV_KEYS = ("dps3a", "dpsF", "divSt", "dyt", "dz", "betaSE", "betaN")   # v19.1b: data.json 종목에서 그대로 옮기는 칸


def build_corp(kr_stocks, fin_map, as_of, market=None, extra=None):
    """기업분석 탭이 쓰는 corp.json 을 만듭니다. (순수 함수 — 테스트 가능)
    v19.1b: extra = apply_div_basis 의 {코드: 칸} (현금배당금총액 cash3 · 회사가 낸 주당순이익 eps3r · 같은 기준 순이익 epsNi3 · epsB).
    flRan = 실제로 돌린 재무 경고 검사(입력이 다 있었던 것), flNa = 금융업이라 해당 없는 검사. 앱은 네 검사(cr 유동비율 ·
    icr 이자보상배율 · l3 3년 연속 적자 · imp 자본잠식)가 모두 flRan 이나 flNa 에 있을 때만 '재무 경고 신호는 없어요'라고 말할 수 있어요."""
    extra = extra or {}
    comps = []
    hold_log, hold_unknown, hold_bad = [], [], []   # v19.1d: 금융 아닌 지주 (코드, 이름, 유동비율, 이자보상배율) · 그룹 없는 지주 · 금융 지주인데 금융이 아님
    why_n = collections.Counter()                   # v19.1d: 이자보상배율을 못 돌린 이유별 기업 수 (flWhy)
    src_n = collections.Counter()                   # v19.1f: 이자보상배율에 쓴 이자 (is 손익계산서 이자비용 · cf 현금흐름표 이자 지급액)
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
            "iec": _t.get("iec") if _t.get("iec") is not None else fin.get("iec"),
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
        fl, ran = {}, []
        fin_co = fl_financial(s)
        unknown = fl_unknown_holding(s)      # 그룹 없는 지주: 금융 지주일 수도 있어 두 검사를 쉬어요 (앱은 '경고 없음'이라 말하지 않아요)
        if s["t"] in FL_FIN_HOLDINGS and not fin_co:
            hold_bad.append(f"{s['t']} {s['nk']}")
        if eff["ca"] and eff["cl"] and eff["cl"] > 0 and not fin_co and not unknown:
            ran.append("cr")
            cr = eff["ca"] / eff["cl"] * 100
            if cr < 100:
                fl["cr"] = round(cr, 0)
        op0f = eff["op0"]
        # v19.1f: 이자 = 손익계산서 이자비용(is), 없으면 현금흐름표 이자 지급액(cf). 어느 것을 썼는지 flSrc 에 남겨요
        ie_v, ie_src = (eff["ie"], "is") if eff["ie"] is not None else (eff["iec"], "cf") if eff["iec"] is not None else (None, None)
        icr_ok = op0f is not None and ie_v is not None and ie_v >= 0 and not fin_co and not unknown
        if icr_ok and not ICR_OFF:
            ran.append("icr")                                # 이자비용 0 도 돌린 거예요 (갚을 이자가 없으면 경고가 날 수 없어요)
            row["flSrc"] = {"icr": ie_src}
            src_n[ie_src] += 1
        if icr_ok and not ICR_OFF and ie_v > 0:
            icr = op0f / ie_v
            if icr < 1:
                fl["icr"] = round(icr, 2)
        if all(v is not None for v in ni):
            ran.append("l3")
        if all(v is not None and v < 0 for v in ni):
            fl["l3"] = 1
        if eff["cs"] and eff["eq"] is not None:
            ran.append("imp")
        if eff["cs"] and eff["eq"] is not None and eff["eq"] < eff["cs"]:
            fl["imp"] = 1
        if fl:
            row["fl"] = fl
        row["flRan"] = ran                                   # v19.1b: 입력이 다 있어 실제로 돌린 검사 (경고가 없어도 남아요)
        if not fin_co and not unknown and "icr" not in ran:
            # v19.1d (Jack, 2026-11-07): 이자보상배율을 못 돌린 이유. 앱은 'ie'(재무제표에 이자비용·금융비용 줄이 없음)일 때만
            # '재무제표에서 이자 비용을 찾지 못해 확인하지 못했어요'라고 말해요. op = 영업이익이 없음 · neg = 이자비용이 음수 ·
            # off = 잠시 꺼 둠 (ICR_OFF — 앱은 아무 말도 하지 않아요). 꺼진 동안은 이자 줄이 없는 회사도 off: 어떤 회사엔 '확인한 …
            # 없어요' 카드가, 같은 결과의 다른 회사엔 아무것도 없는 차이가 생기지 않게 (리뷰 2026-11-07)
            row["flWhy"] = {"icr": "off" if ICR_OFF else "op" if op0f is None else "ie" if ie_v is None else "neg"}
            why_n[row["flWhy"]["icr"]] += 1
        if fin_co:
            row["flNa"] = ["cr", "icr"]                      # 금융회사(금융 지주 포함)는 유동비율·이자보상배율이 해당 없어요
        elif unknown:
            hold_unknown.append(f"{s['t']} {s['nk']}")
        elif row["s"] == "holding" or s.get("ind") == "holding":   # v19.1d: 금융이 아닌 지주회사 — 몇 곳이 돌았는지 로그로 남겨요
            hold_log.append((s["t"], s["nk"], "cr" in ran, icr_ok))   # 이자보상배율은 '돌릴 수 있었는지' (ICR_OFF 와 상관없이)
        for k in CORP_DIV_KEYS:                              # v19.1b: 분할 확인한 배당 · 베타 표준오차
            if s.get(k) is not None:
                row[k] = s[k]
        row.update(extra.get(s["t"]) or {})

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
        if is_foreign_issuer(s["t"]):
            # v17.5.2: 해외 기업 금액은 원화가 아닐 수 있어 비워요 (blank_foreign_dart 참고). 위에서 만든 fl 신호는 비율·부호라 남겨요.
            row.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False)
            for k in ("evE", "evR", "pcf", "bq", "cash3", "eps3r", "epsNi3", "epsB"):     # v19.1b: 배당 총액·주당순이익도 금액
                row.pop(k, None)
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
    log(f"· 이자보상배율에 쓴 이자: 손익계산서 이자비용 {src_n['is']:,}곳 · 현금흐름표 이자 지급액 {src_n['cf']:,}곳 · 경고 "
        f"{sum(1 for c in comps if 'icr' in (c.get('fl') or {})):,}곳 (그중 영업손실 "
        f"{sum(1 for c in comps if (c.get('fl') or {}).get('icr', 1) < 0):,})")
    log(f"{'  !! ' if ICR_OFF else '· '}이자보상배율을 못 돌린 기업 (금융 빼고): {sum(why_n.values()):,}곳 — "
        + (f"잠시 꺼 둠(ICR_OFF · 금융비용으로 계산되던 값이라) {why_n['off']:,} · " if ICR_OFF else "")
        + f"이자비용·금융비용 줄 없음 {why_n['ie']:,} · 영업이익 없음 {why_n['op']:,} · 이자비용 음수 {why_n['neg']:,} (corp.json flWhy)")
    both = [h for h in hold_log if h[2] and h[3]]
    miss = [h for h in hold_log if not (h[2] and h[3])]
    log(f"· 지주회사(금융 빼고) 재무 경고: {len(hold_log)}곳 중 유동비율 {sum(h[2] for h in hold_log)} · 이자보상배율 "
        f"{sum(h[3] for h in hold_log)} · 둘 다 {len(both)}곳 돌릴 수 있어요" + (" (이자보상배율은 지금 꺼 둠 · ICR_OFF)" if ICR_OFF else ""))
    if hold_unknown:
        log(f"  !! 업종 그룹이 없어 금융 지주인지 알 수 없는 지주회사 {len(hold_unknown)}곳: 두 검사를 쉬어요 — " + ", ".join(hold_unknown))
    if hold_bad:
        log(f"  !! 금융 지주인데 금융으로 잡히지 않은 회사 {len(hold_bad)}곳 (업종 그룹 확인): " + ", ".join(hold_bad))
    if miss:
        log(f"  !! 재무제표에 필요한 줄이 없거나 쓸 수 없어(유동부채 0 이하·이자비용 음수 포함) 못 돌린 지주회사 {len(miss)}곳: " + ", ".join(
            f"{t} {nk}({'유동비율' if not cr else ''}{'·' if not cr and not icr else ''}{'이자보상배율' if not icr else ''} 없음)"
            for t, nk, cr, icr in miss))
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
    pref_shares = kr_pref_shares(listing)     # v19.1b: 상위 2,500개로 자르기 전 — 작은 우선주도 회사의 주식 수에 들어가야 해요
    n_pref = sum(1 for c in listing["Code"] if is_preferred(str(c)))
    n_pref_ok = sum(len(v) for v in pref_shares.values())
    log(f"{'  !! ' if n_pref_ok < n_pref else '· '}우선주 상장 주식 수 (배당 분할 확인용): {n_pref_ok:,} / {n_pref:,}종목 · "
        f"{len(pref_shares):,}개 회사" + (" — 주식 수가 빈 우선주는 그 회사의 배당을 확인하지 못할 수 있어요" if n_pref_ok < n_pref else ""))

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

    n_all = len(listing)
    listing = select_kr_universe(listing, MAX_KR)
    if sample_size():
        listing = sample_universe(listing, sample_size())
        log(f"  !! 표본 실행: 국내 {len(listing):,}종목만 처리해요")
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

    # v17.5.1: d1 (전 거래일 공식 종가 대비) · val20 (20거래일 평균 거래대금) — 그 전 날짜들의 최종 목록 파일에서.
    # 직전 파일이 KOSPI 의 직전 거래일과 다르면(그날 파일이 없거나 미완성이라 건너뛴 것) d1 은 이틀치 변화라 비워요.
    d1_map, v20_map, sessions = {}, {}, []
    if px_date is not None:
        sessions, snotes, prev_final = kr_recent_sessions(px_date, _fetch_listing_csv, _listing_commit_kst)
        for n in snotes:
            log(f"  ({n})" if not n.startswith("!!") else f"  {n}")
        want_prev = kr_prev_session(px_date, ks_all.index)
        ok_prev = prev_session_ok(sessions, prev_final, want_prev)
        if sessions and not ok_prev and prev_final:
            log(f"  !! 직전 거래일은 {want_prev} (KOSPI)인데 찾은 목록 파일은 {sessions[0][0]} — 그날 파일이 없거나 최종본이 아니라 d1 을 비워요")
        d1_map, v20_map, dcnt = kr_d1_val20(listing, sessions, ok_prev)
        log(f"{'  !! ' if not ok_prev else '· '}d1·val20: 앞선 거래일 파일 {len(sessions)}개"
            + (f" (직전 {sessions[0][0]})" if sessions else "") + f" · d1 {len(d1_map):,} · val20 {len(v20_map):,}"
            + (f" · {dict(dcnt)}" if dcnt else ""))
    # 네이버 일봉은 넥스트레이드까지 합친 '마지막 체결가'라 공식 종가와 다른 날이 있어요 (리뷰: 300일 중 30일쯤, 최대 4%).
    # 목록 파일을 받은 최근 거래일들은 공식 종가로 고쳐요. 그보다 오래된 날은 v18.0 Part B 에서 공식 종가 이력으로 바꿔요.
    off_by_day = {pd.Timestamp(d): _official_map(df) for d, df in sessions}
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
    prod_map = {}               # 주요제품 (업종 그룹 나누기용, 파일에는 dk 로만 나가요)
    try:
        prev_px = pd.Timestamp((prev or {}).get("pxDate") or "")
    except (TypeError, ValueError):
        prev_px = None
    prev_px = prev_px if prev_px is not None and not pd.isna(prev_px) else None
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
            win = px.tail(252)
            at = win.idxmax() if key == "hi" else win.idxmin()
            if (n > o) if key == "hi" else (n < o):
                # 지난 발행 뒤에 생긴 봉에서 나온 값이어야 진짜 새 고점·저점 (예전 봉이 바뀐 거면 분할·수정·잘못된 봉)
                new_bar = prev_px is None or at > prev_px
                why = ("새 고점" if key == "hi" else "새 저점") if new_bar else "그 밖"
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
                px, nfix = pin_recent(px, off_by_day, code)
                with lock:
                    pin[how] += 1
                    pin["recent_fixed"] += nfix
                    pin["recent_stocks"] += 1 if nfix else 0
            else:
                px = cut_at(px, last)
            if len(px) < 60:
                with lock:
                    dropped["시세 60일 미만"] += 1
                return None
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a, bse, bn = beta_fit(ret, bench, rf)
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
                "betaSE": bse, "betaN": bn,   # v19.1b: beta_fit 은 넷을 함께 내거나 함께 비워요
                "per": round(per, 1) if per and per > 0 else None,
                "pbr": round(pbr, 2) if pbr and pbr > 0 else None,
                "dy": round(dyv, 2) if dyv is not None else None,   # 모르면 빈 칸 (0% 로 보이지 않게). DART 가 나중에 채워요
                "eps": round(eps, 0) if eps else None,
                "bps": round(bps, 0) if bps else None,
                "dps": round(dps, 0) if dps and dps > 0 else None,   # pykrx 는 모르면 0 을 줘서 0 은 버려요 (0원은 DART 가 채워요)
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
            if prod_txt:
                with lock:
                    prod_map[code] = prod_txt
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
        loud = pin["added"] > 0.02 * max(pin["same"] + pin["fixed"] + pin["added"], 1)   # 시계열이 하루 늦으면 베타·변동성에 가짜 하루 움직임이 끼어요
        log(f"{'  !! ' if loud else '· '}네이버 시계열의 {px_date} 값: 공식 종가와 같음 {pin['same']:,} · "
            f"공식 종가로 교체 {pin['fixed']:,} · 없어서 추가 {pin['added']:,}"
            + (" (네이버 시계열이 기준일보다 늦은 종목이 많아요)" if loud else ""))
        log(f"· 최근 {len(off_by_day)}거래일 네이버 일봉을 공식 종가로 고침: {pin['recent_fixed']:,}개 봉 · {pin['recent_stocks']:,}종목"
            " (넥스트레이드 체결가가 섞인 날)")
    meta = {"pxDate": px_date.isoformat() if px_date else None,
            "ksDate": ks_date.isoformat() if ks_date else None, "listSrc": list_src, "_index": kospi, "_prod": prod_map,
            "_prefShares": pref_shares}
    return out, bench, mkt, meta


# v17.5.2 (Jack 승인 2026-11-03): 해외 기업(종목코드가 9로 시작: 900xxx·950xxx)은 DART 재무제표를 달러·위안·엔 등으로
# 낼 수 있어요. 그걸 원화로 읽으면 PBR 9,085(코오롱티슈진) · PER 수천 같은 값이 나와요. 환산을 추측하지 않고 비워요:
# 금액으로 만든 값(PER·PBR·EPS·BPS)과 0 이 아닌 배당(표의 통화도 불확실). 배당 0 은 어느 통화로도 '배당 없음'이라 남겨요
# (2.0 의 '무배당 빼기'가 dps === 0 을 봐요). corp.json 금액(매출·이익·자본, DCF 입력·EV 배수)은 build_corp 가 비우고,
# fill_multiples 는 이들을 건너뛰어요. 통화와 상관없는 비율(roe·opm·debt·g3)·재무 신호(fl)와 KRX 가격·시가총액(원화)은 남겨요.
# 가치 점수(vz)는 PBR 이 비면 add_percentiles 가 안 매겨요.
FOREIGN_BLANK = ("per", "pbr", "eps", "bps")       # 늘 비워요
FOREIGN_BLANK_NONZERO = ("dps", "dy")              # 0 이 아니면 비워요 (dps3 는 0 이 아닌 해만 빈 칸으로)


def is_foreign_issuer(code):
    """KRX 해외 기업 종목코드인지: 6자리이고 9로 시작 (900xxx 중국 등 · 950xxx 미국·일본 등). (순수 함수)"""
    return isinstance(code, str) and len(code) == 6 and code[0] == "9"


def blank_foreign_dart(kr_stocks):
    """해외 기업의 원화가 아닐 수 있는 값을 비워요: FOREIGN_BLANK 칸, 0 이 아닌 배당(dps·dy·dps3 의 각 해). (순수 함수 + 로그)
    corp.json 금액은 build_corp 가 비워요 (fl 신호는 그 전에 계산해 남아요). 반환: 해당 종목 ["코드 이름", …]."""
    hit = []
    for s in kr_stocks:
        if not is_foreign_issuer(s.get("t")):
            continue
        for k in FOREIGN_BLANK:
            s.pop(k, None)
        for k in FOREIGN_BLANK_NONZERO:
            if s.get(k) is not None and _fin(s[k]) != 0:
                s.pop(k)
        if isinstance(s.get("dps3"), list):
            d3 = [0.0 if _fin(x) == 0 else None for x in s["dps3"]]
            if any(x is not None for x in d3):
                s["dps3"] = d3
            else:
                s.pop("dps3")
        hit.append(f"{s['t']} {s.get('nk', '')}".strip())
    if hit:
        log(f"  !! 해외 기업 {len(hit)}곳: DART 금액이 원화가 아닐 수 있어 PBR·PER·EPS·배당·금액을 비웠어요 (배당 0원 = 배당 없음은 남겨요): "
            f"{', '.join(sorted(hit))}")
    else:
        log("· 해외 기업(종목코드 9…): 없음")
    return hit


def fill_multiples(kr_stocks, fin_map):
    """DART 재무(순이익·자본) + 상장주식수로 EPS/BPS/PER/PBR을 직접 계산합니다.
    pykrx는 KRX 로그인이 필요해져 CI에서 동작하지 않으므로, 있으면 쓰고 없으면 이 값으로 채웁니다.
    순이익·자본은 지배주주 귀속분을 우선 사용합니다."""
    n = 0
    for s in kr_stocks:
        fin = fin_map.get(s["t"])
        shr = s.get("shr")
        price = s.get("price")
        if not fin or not shr or not price or is_foreign_issuer(s["t"]):     # v17.5.2: 해외 기업 금액은 원화가 아닐 수 있어요
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
# v19.1b: 분할에 안전한 한국 배당 (Jack, 2026-11-05)
# ────────────────────────────────────────────────────────────
# 문제: dps3(최근 사업보고서의 당기·전기·전전기 주당 배당금)만으로는 액면분할·무상증자와 진짜 배당 감소를 구별하지 못해요.
# 1:2 분할 뒤에는 회사가 똑같이 줘도 주당 배당금이 반으로 보여요. 그래서 '그해 배당금이 몇 주 기준이었나'를 정확한 값으로 거꾸로 셉니다.
#   N  그해 배당을 받은 주식 수 = 현금배당금총액 ÷ 보통주 주당 배당금 (우선주 배당도 총액에 들어 있어 보통주 1주 기준으로 세요)
#   W  그해 주당순이익 뒤의 평균 주식 수 = 당기순이익 ÷ 주당순이익 (같은 연결/별도 기준) — 그해 배당이 0 일 때만 써요
#   I  그해 말 발행 주식 수의 상한 = 자본금 ÷ 액면가 (이익소각한 주식만큼 실제보다 커요)
# 오늘 상장 주식 수(shr + 같은 회사 우선주)를 그해 기준 주식 수로 나눈 '배율'을 구해요.
#   - 자기주식은 배당을 못 받아서 N 은 상장 주식 수보다 작아요 (3~40%). 그래서 N 과 오늘 주식 수를 바로 맞대면 2:1 분할과
#     자기주식 50% 를 구별할 수 없어요. 대신 정확한 두 끝을 써요: 배율은 '오늘 ÷ I' 이상, '오늘 ÷ N' 이하예요.
#     이 범위에 걸치는 후보(1 또는 깨끗한 분할 배율)가 딱 하나일 때만 그 배율로 맞춰요. 둘 이상이면 '알 수 없음', 없으면 '비교 불가'.
#   - 이전 해(전기·전전기)는 같은 보고서 안에서 비교해요: 발행 주식 수 상한의 비 I₀/Iᵢ 가 바뀐 배율(분할·무상증자는 정확한 배수,
#     유상증자·합병은 어중간한 배수)이고, 배당 받은 주식 수의 비 N₀/Nᵢ 가 그해 배당금이 옛 기준인지(회사가 고치지 않음) 새 기준인지
#     (회사가 고쳐 적음) 알려 줘요. 자기주식 매입·소각은 I 를 바꾸지 않아서 배율로 오해하지 않아요.
#   - 깨끗한 배율: 2, 2.5, 3, 4, 5, 10, 20, 25, 50, 100 과 그 역수 (±5%). 10% 안의 변화는 '그대로' (스톡옵션·전환사채·소각).
#   - 어림한 배율로는 절대 맞추지 않아요. 맞출 수 없으면 그해 dps3a 는 빈 칸이고 이유가 divSt 에 남아요.
# 결과: dps3a(오늘 주식 수 기준 주당 배당금) dpsF(해마다 배율 = 오늘 주식 수 ÷ 그해 기준) divSt(same·adj·nc·nd·zero)
#       dyt(오늘 종가 기준 배당수익률 = dps3a[0] ÷ 종가) → 배당 순위(dz)는 dyt 로만 매겨요.
SPLIT_FACTORS = (2, 2.5, 3, 4, 5, 10, 20, 25, 50, 100)
SHARE_SAME = 0.10        # 주식 수 비가 1 ± 10% 면 같은 기준 (분할 아님)
SPLIT_TOL = 0.05         # 깨끗한 배율 k 의 ±5%
DRIFT_TOL = 0.15         # 발행 주식 수로 배율을 정한 뒤, 배당 받은 주식 수가 해마다 이만큼까지는 흔들려도 돼요 (자기주식 매입·소각)
DYT_MAX = 30.0           # 오늘 종가 기준 배당수익률이 이보다 크면 믿지 않아요 (앱·미국 수익률과 같은 한도)
DIV_FACTORS = (1.0,) + tuple(float(k) for k in SPLIT_FACTORS) + tuple(1.0 / k for k in SPLIT_FACTORS)
DIV_STATUS = ("same", "adj", "nc", "nd", "zero")      # 그대로 · 맞춤 · 비교 불가 · 알 수 없음 · 배당 없음


def _factor_band(c):
    return (1 - SHARE_SAME, 1 + SHARE_SAME) if c == 1.0 else (c * (1 - SPLIT_TOL), c * (1 + SPLIT_TOL))


def clean_factor(x):
    """주식 수 비 x 가 1(±10%)이면 1.0, 깨끗한 분할 배율(±5%)이면 그 배율, 아니면 None. (순수 함수)"""
    x = _fin(x)
    if x is None or x <= 0:
        return None
    for c in DIV_FACTORS:
        lo, hi = _factor_band(c)
        if lo <= x <= hi:
            return c
    return None


def factor_between(lo, hi):
    """배율이 lo 이상 hi 이하라는 것만 알 때: 그 범위에 걸치는 후보가 하나뿐이면 (그 배율, 'ok').
    후보가 없으면 (None, 'nc' 비교 불가), 둘 이상이거나 범위가 이상하면 (None, 'nd' 알 수 없음). (순수 함수)"""
    lo, hi = _fin(lo), _fin(hi)
    if lo is None or hi is None or lo <= 0 or hi <= 0 or lo > hi * 1.02:
        return None, "nd"
    hits = [c for c in DIV_FACTORS if _factor_band(c)[0] <= hi and _factor_band(c)[1] >= lo]
    if len(hits) == 1:
        return hits[0], "ok"
    return None, ("nc" if not hits else "nd")


def _three(v):
    return [_fin(x) for x in (list(v) + [None] * 3)[:3]] if isinstance(v, (list, tuple)) else [None] * 3


def div_basis(dps3, bas, cs3, shr, prefs=(), ss3=None, cap_k="all", cap_src=None):
    """한 회사의 주당 배당금 3년을 오늘 주식 수 기준으로 맞춰요. (순수 함수)
    dps3 보통주 주당 배당금 [당기, 전기, 전전기] (0 = 배당 없음 · None = 모름) · bas = parse_dart_basis 결과 ·
    cs3 자본금 3년 (억원) · shr 오늘 상장 보통주 수 · prefs 같은 회사 상장 우선주들의 오늘 주식 수 ·
    ss3 자본잉여금 3년 (억원 — 액면가가 그대로인데 주식 수가 깨끗한 배율로 바뀐 해가 무상증자인지 확인해요).
    cap_k 자본금의 범위: all = 회사 전체 · common = 보통주만 (v19.1e: 그러면 아래 끝은 오늘 보통주 수 ÷ 보통주 발행 주식 수 상한).
    cap_src paid = 납입자본(주식발행초과금이 섞일 수 있음): 올해 아래 끝에만 쓰고 앞 해 비교에는 쓰지 않아요 (v19.1e).
    반환 {"dps3a", "dpsF", "st3", "divSt", "f0", "lo", "hi"} — divSt 는 배당한 해들 중 가장 나쁜 결과
    (nc 비교 불가 > nd 알 수 없음 > adj 맞춤 > same 그대로), 3년 모두 0 이면 zero."""
    d = _three(dps3)
    bas = bas or {}
    cash, par, eps, ni = _three(bas.get("cash3")), _three(bas.get("par3")), _three(bas.get("eps3")), _three(bas.get("ni3"))
    pds = [_three(v) for v in bas.get("pdps") or [] if isinstance(v, (list, tuple))]
    cs, ss = _three(cs3), _three(ss3)
    if cap_src == "paid":
        cs = [cs[0], None, None]       # 납입자본의 비는 주식 수의 비가 아니에요 (주식발행초과금으로 한 무상증자)
    shr = _fin(shr)
    prefs = [p for p in (_fin(x) for x in prefs or ()) if p and p > 0]
    pref_all = sum(prefs)
    N = [cash[i] / d[i] if d[i] and d[i] > 0 and cash[i] and cash[i] > 0 else None for i in range(3)]
    W = [ni[i] / eps[i] if ni[i] and eps[i] and ni[i] * eps[i] > 0 else None for i in range(3)]
    I = [cs[i] * 1e8 / par[i] if cs[i] and cs[i] > 0 and par[i] and par[i] > 0 else None for i in range(3)]

    def today_w(i):
        """오늘 상장 주식 수를 N 과 같은 셈법으로: 우선주는 그해 (가장 많이 받은 종류의 주당 배당 ÷ 보통주 주당 배당) 만큼.
        가장 큰 무게를 써야 위 끝이 위 끝으로 남아요. 배당을 받은 종류가 상장 우선주 종목 수보다 많으면(상환전환우선주 등
        상장되지 않은 주식이 총액에 섞임) 위 끝을 셀 수 없어요 → None."""
        paid = [p[i] for p in pds if p[i] is not None]
        if sum(1 for x in paid if x > 0) > len(prefs):
            return None
        if not prefs:
            return shr
        w = max(paid) / d[i] if paid and d[i] else 1.0
        return shr + w * pref_all

    # 오늘 ÷ 최근 사업보고서(당기) 기준 = f0. 위 끝(hi)은 배당 받은 주식 수(배당이 없던 해는 주당순이익의 평균 주식 수)로,
    # 아래 끝(lo)은 자본금 ÷ 액면가로. 총액(백만원 단위 반올림)·주당 배당금(원 단위)의 반올림만큼 범위를 넓혀요.
    hi = lo = None
    if shr and shr > 0:
        if N[0] and today_w(0) is not None:
            hi = today_w(0) / N[0] * (1 + 0.5e6 / cash[0] + 0.5 / d[0])
        elif d[0] == 0 and W[0]:
            hi = (shr + pref_all) / W[0] * (1 + 0.5e6 / abs(ni[0]) + 0.5 / abs(eps[0]))
        if I[0]:
            lo = ((shr + pref_all) if cap_k != "common" else shr) / I[0] * 0.999
    f0, st0 = factor_between(lo, hi)

    def rel(i):
        """당기 기준 ÷ i 해 기준 = gᵢ. 발행 주식 수 상한의 비(q)가 바뀐 배율을, 배당 받은 주식 수의 비(r)가 그해 배당금이
        옛 기준(g = q)인지 회사가 고쳐 적은 새 기준(g = 1)인지 알려 줘요."""
        q = I[0] / I[i] if I[0] and I[i] else None
        r = N[0] / N[i] if N[0] and N[i] else None
        p = par[i] / par[0] if par[0] and par[i] else None
        if q is None:
            # 발행 주식 수 상한을 모르면 배당 받은 주식 수만으로: 자기주식 매입·처분 만큼(±15%)은 같은 기준,
            # 깨끗한 배율은 액면가가 같은 배율로 바뀐 것(액면분할)이 확인될 때만. 그 밖은 판단하지 않아요
            if r is None:
                return None, "nd"
            if abs(r - 1) <= DRIFT_TOL:
                return 1.0, "ok"
            kr = clean_factor(r)
            if kr not in (None, 1.0) and p is not None and abs(p / kr - 1) < 1e-6:
                return kr, "ok"
            return None, "nd"
        kq = clean_factor(q)
        if kq is None:
            return None, "nc"                           # 유상증자·합병·인적분할처럼 어중간하게 바뀐 주식 수
        if kq == 1.0:
            kr = clean_factor(r) if r is not None else None
            if (kr is not None and kr != 1.0) or (p is not None and abs(p - 1) > 1e-9):
                return None, "nd"                       # 발행 주식 수는 그대로인데 다른 값이 분할을 말해요 — 판단하지 않아요
            return 1.0, "ok"
        # 발행 주식 수가 깨끗한 배율로 바뀜. 액면가가 같은 배율로 바뀌었으면 액면분할·병합이에요. 액면가가 그대로면 무상증자여야
        # 맞출 수 있어요: 자본잉여금이 늘지 않았을 때만 (주식발행초과금이 늘었으면 깨끗한 배율의 유상증자일 수 있어 판단하지 않아요)
        if not (p is not None and abs(p / kq - 1) < 1e-6):
            if ss[0] is None or ss[i] is None or ss[0] > ss[i] * 1.02 + 0.01:
                return None, "nd"
        if r is None:
            return None, "nd"
        if abs(r / kq - 1) <= DRIFT_TOL:
            return kq, "ok"                             # 그해 배당금이 옛 기준 그대로
        if abs(r - 1) <= DRIFT_TOL:
            return 1.0, "ok"                            # 회사가 새 기준으로 고쳐 적음
        return None, "nd"

    dps3a, dpsF, st3 = [None] * 3, [None] * 3, [None] * 3
    for i in range(3):
        if d[i] is None:
            continue
        if d[i] == 0:
            dps3a[i], st3[i] = 0.0, "zero"
            continue
        if i == 0:
            f, st = f0, st0
        else:
            g, st = rel(i)
            f = f0 * g if g is not None and f0 is not None else None
            if g is not None and f0 is None:
                st = st0
        if f is None:
            st3[i] = st if st in ("nc", "nd") else "nd"
            continue
        dpsF[i] = round(f, 6)
        dps3a[i] = round(d[i] / dpsF[i], 2)     # 발행되는 배율로 나눠요 (관문이 같은 값으로 다시 계산해요 — 1/3 배율도 맞게)
        st3[i] = "same" if f == 1.0 else "adj"
    paid = [x for x in st3 if x in ("same", "adj", "nc", "nd")]
    if not paid:
        # 3년 모두 0 일 때만 '배당 없음'. 모르는 해(빈 칸)가 섞이면 배당했는지도 모르니 '알 수 없음'
        div_st = "zero" if st3.count("zero") == 3 else ("nd" if "zero" in st3 else None)
    else:
        div_st = next(x for x in ("nc", "nd", "adj", "same") if x in paid)
    return {"dps3a": dps3a, "dpsF": dpsF, "st3": st3, "divSt": div_st, "f0": f0, "lo": lo, "hi": hi}


def kr_pref_shares(listing):
    """목록 파일 전체(상위 2,500개로 자르기 전)에서 우선주 상장 주식 수: {보통주 코드 앞 5자리: [주식 수, …]}. (순수 함수)
    우선주 코드는 보통주 코드의 끝자리만 바꾼 것이에요 (005930 → 005935 · 005380 → 005385·005387·005389 · 006800 → 00680K)."""
    out = {}
    if listing is None or "Code" not in getattr(listing, "columns", []):
        return out
    for code, sh in zip(listing["Code"].astype(str), listing.get("Stocks", pd.Series([None] * len(listing)))):
        code = code.strip()
        v = _fin(_num(sh))
        if is_preferred(code) and v and v > 0:
            out.setdefault(code[:5], []).append(v)
    return out


def apply_div_basis(kr_stocks, fin_map, pref_shares):
    """v19.1b: 국내 종목마다 dps3a·dpsF·divSt·dyt 를 붙이고, corp.json 에 실을 원값(총액·주당순이익)을 돌려줘요.
    분할 확인용 임시 칸(_bas)은 여기서 지워요 (파일에 나가지 않게). 반환: (집계 dict, {코드: corp.json 추가 칸})."""
    cnt = collections.Counter()
    extra, adj_ex, nc_ex, nd_ex, big = {}, [], [], [], []
    srcs = collections.Counter()                 # v19.1e: 분할 확인에 쓴 자본금 줄 (배당 종목만)
    for s in kr_stocks:
        bas = s.pop("_bas", None)
        cap = s.pop("_cap", None)
        if s.get("cls") != "kr":
            continue
        t = s["t"]
        if is_preferred(t):
            cnt["pref"] += 1          # 우선주 종목에는 DART 배당 표가 따로 없어요 (보통주의 표에 우선주 줄로 있어요)
            continue
        if not isinstance(s.get("dps3"), list):
            cnt["noDps"] += 1
            continue
        fin = fin_map.get(t) or {}
        cap = cap if isinstance(cap, dict) and cap.get("cs3") else None
        cs3 = cap["cs3"] if cap else fin.get("cs3")
        ss3 = (cap.get("ss3") if cap else None) or fin.get("ss3")
        r = div_basis(s["dps3"], bas, cs3, s.get("shr"), pref_shares.get(t[:5], ()), ss3, cap_k=(cap or {}).get("k", "all"),
                      cap_src=(cap or {}).get("src"))
        d0_ = _fin(s["dps3"][0]) if s["dps3"] else None
        if d0_ is not None and d0_ > 0:
            srcs[(cap or {}).get("src") or ("total" if cs3 else "none")] += 1
        if r["divSt"] is None:
            cnt["noDps"] += 1
            continue
        s["dps3a"], s["dpsF"], s["divSt"] = r["dps3a"], r["dpsF"], r["divSt"]
        cnt[r["divSt"]] += 1
        price = _fin(s.get("price"))
        d0 = _fin(s["dps3"][0]) if s["dps3"] else None
        payer = d0 is not None and d0 > 0
        cnt["payers"] += payer
        if not price or price <= 0:
            pass                      # 종가가 없으면 수익률도 없어요 (국내 종목은 늘 종가가 있어요)
        elif r["st3"][0] == "zero":
            s["dyt"] = 0.0
        elif r["dpsF"][0] is not None:
            y = r["dps3a"][0] / price * 100        # 발행되는 dps3a 로 (관문과 같은 계산 · 30% 경계도 같게)
            if y <= DYT_MAX:
                s["dyt"] = round(y, 2)
            else:
                big.append(f"{t} {s.get('nk', '')} {y:.0f}%")
        if s.get("dyt") is not None:
            cnt["dyt"] += 1
            cnt["payersDyt"] += payer
        tag = f"{t} {s.get('nk', '')}".strip()
        if r["divSt"] == "adj":
            adj_ex.append(f"{tag} ×{'/'.join(f'{x:g}' for x in r['dpsF'] if x is not None)}")
        elif r["divSt"] == "nc":
            nc_ex.append(tag)
        elif r["divSt"] == "nd":
            nd_ex.append(tag)
        if bas and not is_foreign_issuer(t):      # 해외 기업 금액은 원화가 아닐 수 있어 싣지 않아요 (blank_foreign_dart 참고)
            ek2 = lambda v: round(v / 1e8, 2) if _fin(v) is not None else None       # 원 → 억원 (백만원 단위까지)
            e = {}
            if isinstance(bas.get("cash3"), list):
                e["cash3"] = [ek2(v) if (_fin(v) or 0) >= 0 else None for v in bas["cash3"]]   # 음수 총액은 잘못 적은 값 — 비워요
                if any(_fin(v) is not None and v < 0 for v in bas["cash3"]):
                    cnt["negCash"] += 1
                    big.append(f"{t} 음수 현금배당금총액")
            if isinstance(bas.get("eps3"), list):
                e["eps3r"] = [round(v, 0) if _fin(v) is not None else None for v in bas["eps3"]]
                e["epsNi3"] = [ek2(v) for v in bas.get("ni3") or [None] * 3]
                if bas.get("epsB"):
                    e["epsB"] = bas["epsB"]
            if e:
                extra[t] = e

    def ex(arr):
        return f": {', '.join(sorted(arr)[:8])}{'…' if len(arr) > 8 else ''}" if arr else ""
    log(f"{'  !! ' if srcs['none'] else '· '}배당 분할 확인에 쓴 자본금 (배당한 종목): '자본금' {srcs['total']:,} · 보통주자본금 "
        f"{srcs['common']:,} · 납입자본(올해만 · 크게 잡힐 수 있음) {srcs['paid']:,} · 못 읽음 {srcs['none']:,}")
    loud = cnt["nc"] + cnt["nd"] > 0
    log(f"{'  !! ' if loud else '· '}배당 분할 확인: 그대로 {cnt['same']:,} · 맞춤 {cnt['adj']:,}{ex(adj_ex)} · "
        f"비교 불가 {cnt['nc']:,}{ex(nc_ex)} · 알 수 없음 {cnt['nd']:,}{ex(nd_ex)} · 배당 없음 {cnt['zero']:,} · "
        f"DART 배당 표 없음 {cnt['noDps']:,} · 우선주 {cnt['pref']:,}")
    share = 100.0 * cnt["payersDyt"] / cnt["payers"] if cnt["payers"] else 0.0
    band = ("관문 실패" if share < DYT_COVER_BANDS["floor"] else "관문 경고" if share < DYT_COVER_BANDS["seen"] else None)
    log(f"{'  !! ' if band else '· '}오늘 종가 기준 배당수익률(dyt): 배당한 {cnt['payers']:,}종목 중 {cnt['payersDyt']:,} "
        f"({floor_1(share)}%{' · ' + band if band else ''}) + 배당 없음 {cnt['dyt'] - cnt['payersDyt']:,}"
        f" — 확인 못 한 종목은 빈 칸이라 배당 순위에서 빠져요"
        + (f" · 믿지 않아 비운 값(수익률 30% 초과·음수 총액) {len(big)}: {', '.join(big[:5])}" if big else ""))
    counts = {"v": 1, **{k: cnt[k] for k in DIV_STATUS}, "noDps": cnt["noDps"], "pref": cnt["pref"],
              "payers": cnt["payers"], "dyt": cnt["dyt"]}
    return counts, extra


DIV_RANK_MUST = MUST_KR + ("035420", "012450")   # 관문의 필수 종목 중 국내 7개 (NAVER · 한화에어로스페이스 포함)


def dividend_rank_missing(kr_stocks, must=DIV_RANK_MUST):
    """배당 순위(dyt·dz)에 빠진 필수 종목 → [(코드, 이유)]. 관문의 '필수 종목 배당 순위'와 같은 7개, 같은 이유 문구예요.
    목록에 아예 없는 종목은 '데이터에 없음'으로 적어요 (관문은 그 종목을 '필수 종목 (가격·시총)' 줄에서 실패로 막아요). (순수 함수)"""
    by = {s.get("t"): s for s in kr_stocks}
    out = []
    for t in must:
        s = by.get(t)
        if s is not None and _fin(s.get("dyt")) is not None and _fin(s.get("dz")) is not None:
            continue
        out.append((t, rank_miss_reason(s)))
    return out


# ────────────────────────────────────────────────────────────
# 미국
# ────────────────────────────────────────────────────────────
def us_tickers(names_out=None):
    """S&P500 + NASDAQ 상위 400 + EXTRA_US. names_out(dict)을 주면 목록에 적힌 이름도 담아요 (티커 → 이름):
    야후의 짧은 이름은 31자에서 잘리고 긴 이름은 'Strategy Inc' 처럼 회사 이름뿐일 때가 있어서, 우선주·예탁증서를 알아보는 데
    목록의 이름("… Depositary Shares Each Representing … Preferred Stock")도 써요 (us_preferred_like)."""
    import FinanceDataReader as fdr
    tk = set(EXTRA_US)
    for name in ("S&P500", "NASDAQ"):
        try:
            df = fdr.StockListing(name)
            col = "Symbol" if "Symbol" in df.columns else df.columns[0]
            if name == "NASDAQ":
                df = df.head(400)
            syms = [str(s) for s in df[col].dropna().tolist()]
            tk.update(syms)
            if names_out is not None and "Name" in df.columns:
                for sym, nm in zip(df[col].tolist(), df["Name"].tolist()):
                    if isinstance(sym, str) and isinstance(nm, str) and nm.strip():
                        names_out.setdefault(sym.replace(".", "-").strip().upper(), nm.strip())
        except Exception as e:
            log(f"  ({name} 목록 실패: {e})")
    if names_out is not None:
        log(f"· 미국 목록 이름 {len(names_out):,}개 (우선주·예탁증서 알아보기용)")
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


# v19.1c (Jack, 2026-11-07): 다음 발행 예정일과 '늦음' 경고 시각. 앱은 이 시각이 지나도 새 파일이 오지 않으면 갱신이 멈췄다고
# 알려요 (고정 4일 대신). 주말·휴장일에는 다음 거래일까지 조용해요. 휴장일은 사람이 출처를 확인해 적은 표에서만 읽어요.
MARKET_HOLIDAYS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "market_holidays.csv")
MARKET_HOLIDAYS_HEAD = ["date", "market", "name", "source"]
HOLIDAYS_MIN_PER_YEAR = 8     # 한국 평일 휴장은 해마다 12~16일, NYSE 는 9~10일 — 이보다 적으면 반쯤 적은 해예요
# update-data.yml 의 그날 마지막 정해진 시각 실행 (월~토 14:47 KST = cron "47 5 * * 1-6") — 테스트가 workflow 와 맞춰 봐요.
LAST_RETRY_KST = dt.time(14, 47)
# GitHub 의 정해진 시각 실행은 늦게 시작해요: 아침 실행은 2~3시간, 오후 실행은 7~8시간 (2026-11-05·06: 13:37 실행이 21:41 ·
# 21:24 시작). 그래서 이 시각에는 그날 오후 재시도가 아직 돌기 전일 수 있어요 — 아침 발행(06:40 바깥 타이머)이 빠진 것은 맞으니
# 경고는 사실이에요. Jack (2026-11-07): 16:47 (14:47 + 2시간)으로 정했어요 — 늦게 뜨는 쪽보다 일찍 알리는 쪽.
STALE_GRACE = dt.timedelta(hours=2)


def load_market_holidays(path=None):
    """data/market_holidays.csv → {"KR": {날짜: 이름}, "US": {날짜: 이름}, "end": 표가 덮는 마지막 날(마지막 해의 12월 31일)}.
    평일 휴장만 적어요 (주말은 언제나 쉬어요). 이상한 줄이 하나라도 있으면 줄 번호와 함께 예외 — 조용히 '휴장 없음'이 되지 않게.
    표는 해 단위로 빠짐없이 적어요: 적힌 해가 이어지지 않으면 예외."""
    path = path or MARKET_HOLIDAYS_PATH
    name = os.path.basename(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or [c.strip() for c in rows[0]] != MARKET_HOLIDAYS_HEAD:
        raise RuntimeError(f"!! {name} 머리줄이 {','.join(MARKET_HOLIDAYS_HEAD)} 이 아니에요: {rows[0] if rows else '빈 파일'}")
    out = {"KR": {}, "US": {}}
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue

        def bad(why, n=n, row=row):
            return RuntimeError(f"!! {name} {n}번째 줄이 이상해요 ({why}): {','.join(row)[:120]}")
        if len(row) != len(MARKET_HOLIDAYS_HEAD):
            raise bad(f"칸 {len(row)}개 — {len(MARKET_HOLIDAYS_HEAD)}개여야 해요 (쉼표가 섞였는지 확인)")
        r = dict(zip(MARKET_HOLIDAYS_HEAD, (c.strip() for c in row)))
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
                raise ValueError(r["date"])
            d = dt.date.fromisoformat(r["date"])
        except ValueError:
            raise bad("날짜는 YYYY-MM-DD") from None
        if r["market"] not in out:
            raise bad("market 은 KR 또는 US")
        if d.weekday() >= 5:
            raise bad("주말은 적지 않아요 (언제나 쉬어요)")
        if d in out[r["market"]]:
            raise bad(f"{r['market']} {d} 가 두 번 있어요")
        if not r["name"] or not r["source"]:
            raise bad("이름과 출처가 있어야 해요")
        out[r["market"]][d] = r["name"]
    years = sorted({d.year for m in ("KR", "US") for d in out[m]})
    if not years or years != list(range(years[0], years[-1] + 1)) or any(
            not any(d.year == y for d in out[m]) for m in ("KR", "US") for y in years):
        raise RuntimeError(f"!! {name}: 해마다 한국·미국 줄이 다 있어야 해요 (적힌 해: {years})")
    thin = [f"{m} {y}" for m in ("KR", "US") for y in years if sum(1 for d in out[m] if d.year == y) < HOLIDAYS_MIN_PER_YEAR]
    if thin:
        raise RuntimeError(f"!! {name}: 한 해의 평일 휴장일이 {HOLIDAYS_MIN_PER_YEAR}일보다 적어요 ({', '.join(thin)}) — 반쯤 적은 해 같아요")
    out["start"], out["end"] = dt.date(years[0], 1, 1), dt.date(years[-1], 12, 31)
    return out


def next_session(after, closed, end):
    """after 다음의 첫 거래일 (주말·closed 빼고). 표가 덮지 않는 날(end 뒤, 또는 표가 없으면 모두)은 평일 규칙으로만 봐요. (순수 함수)
    표는 '늦음' 경고 시각에만 써요 (어느 날 데이터를 받을지는 최종본 목록·지수 일봉이 정해요) — 그래서 표가 모자라도 멈추지 않아요
    (Jack, 2026-11-07: 멈추면 우리가 경고하려는 낡은 데이터가 생겨요). 휴장일을 모르면 경고가 하루 일찍 뜰 수는 있어도 늦지는 않아요."""
    d = after + dt.timedelta(days=1)
    while d.weekday() >= 5 or (end is not None and d <= end and d in closed):
        d += dt.timedelta(days=1)
    return d


def next_publish(px_date, us_px_date, hol):
    """다음 발행 예정일(한국 날짜) = 한국·미국 중 먼저 오는 다음 거래일의 다음 날. 한국 종가 최종본은 그날 저녁, 미국 종가는
    한국 다음 날 새벽에 확정돼서 둘 다 그다음 날 아침 실행이 발행해요 (화~토). 거래일은 월~금이라 예정일은 늘 화~토예요. (순수 함수)"""
    k = next_session(px_date, hol["KR"], hol.get("end"))
    u = next_session(us_px_date, hol["US"], hol.get("end"))
    return min(k, u) + dt.timedelta(days=1)


def stale_after(next_pub):
    """앱이 '갱신이 멈췄어요'를 보이기 시작하는 시각 = 예정일의 마지막 정해진 시각 실행 + 여유 (한국 시간 ISO). (순수 함수)"""
    return (dt.datetime.combine(next_pub, LAST_RETRY_KST, tzinfo=KST) + STALE_GRACE).isoformat(timespec="seconds")


def us_own_date(px, us_px_date):
    """미국 종목의 자기 가격 날짜: 마지막 봉이 미국 기준일이 아니면 그 날짜(ISO), 같으면 None — data.json 의 pxd 칸이에요.
    가격은 그 날짜의 종가라서, 앱이 '오늘' 날짜가 아니라 이 날짜를 보여 줘요 (Jack, 2026-11-07). (순수 함수)"""
    own = px.index[-1].date()
    return None if own == us_px_date else own.isoformat()


def us_data_date(spx, last_ok):
    """미국 기준일(usPxDate) = S&P 500 일봉에서 장이 끝난 마지막 날(last_ok) 이하의 마지막 봉 날짜. (순수 함수)
    휴장일(추수감사절 등)에는 봉이 없으니 그 전 거래일이에요. 조기 폐장일은 16:30 ET 가 지난 뒤(한국 다음 날 아침)에야 그날이고,
    13:00 폐장 뒤 16:30 전에는 아직 그 전 거래일이에요 (us_last_complete_day 가 16:30 을 봐요). 개별 종목 d1 은
    이 날짜의 봉이 있을 때만 채워요 (us_d1) — 그래서 휴장·조기 폐장은 d1 을 비우지 않고, 발행 관문의 '미국 d1 채움'은 야후가
    기준일 봉을 빠뜨린 종목만 세요."""
    return cut_at(spx, last_ok).index[-1].date()


def us_d1(px, us_px_date):
    """미국 d1: 그 종목의 마지막 봉이 미국 기준일일 때만 마지막 ÷ 그 전 봉 (거래 정지로 낡은 봉이면 빈 칸). (순수 함수)
    야후 수정 종가라 배당락일에는 배당만큼이 더해져 보여요 (작은 차이 — 필드 설명에 적어 둬요)."""
    if len(px) < 2 or px.index[-1].date() != us_px_date:
        return None
    prev, last = float(px.iloc[-2]), float(px.iloc[-1])
    if not (prev > 0 and math.isfinite(prev) and math.isfinite(last)):
        return None                      # 깨진 봉 — fetch_us 가 이 종목을 크게 남기고 빼요 (d1 이 없으면 pxd 가 있어야 하니까요)
    return round((last / prev - 1) * 100, 2)


def etf_from_quote_type(out, cache):
    """ETF 목록에 없는데 야후가 ETF·펀드라고 하면 ETF 로 둬요 (순위에 섞이지 않게). 반환: 바꾼 종목들. (순수 함수)"""
    odd = []
    for rec in out:
        qt = ((cache.get(rec["t"]) or {}).get("info") or {}).get("quoteType")
        if qt in ("ETF", "MUTUALFUND") and not rec.get("etf"):
            rec["etf"] = True
            odd.append(rec["t"])
    return odd


# v17.5.2: 미국 목록 다듬기 — 우선주·예탁증서, 한국 종목의 미국 상장분
US_KR_DUP_PATH = os.path.join(INDUSTRY_DIR, "us_kr_duplicates.csv")
# 우선주·예탁증서는 티커·이름·야후 종류로만 알아봐요. '시가총액이 없다'로는 판단하지 않아요 (Jack, 2026-11-03):
# 진짜 회사의 시가총액이 하루 빠진 것이면 빈 칸으로 남고 검증의 '미국 시가총액 채움'이 세요.
# 2.0 src/v2/engine.js 의 같은 이름 값과 글자 하나까지 같아요 (바꾸면 둘 다 — 테스트가 봐요).
# 2026-11-03 야후: STRC 'Strategy Inc - Variable Rate Se' · STRF·STRD 'Strategy Inc - 10.00% Series A ' (긴 이름은 'Strategy Inc'
# 뿐이고 종류는 EQUITY) · GOOGM·GOOGN 'Alphabet Inc. Depositary Shares representing … Convertible Preferred Stock'.
US_PREF_NAME = re.compile(r"preferred (stock|share|securit)|\bpfd\b|variable rate|fixed[- ]to[- ]floating|[\d.]+%\s*series\b|\bnotes? due\b", re.I)
US_DEPOSITARY = re.compile(r"depositary shar| - deposit", re.I)   # 우선주 예탁증서 (GOOGM, 31자에서 잘린 'AGNC Investment Corp. - Deposit') …
US_ADR = re.compile(r"american deposit", re.I)         # … 단, ADR(진짜 외국 회사의 보통주 예탁증서, 잘린 이름도)은 남겨요
US_PREF_TICKER = re.compile(r"-P[A-Z]?$|^[A-Z]{4}[MNOP]$")   # BAC-PL 꼴 · 나스닥 다섯째 글자 M·N·O·P (우선주 표시)
US_STOCK_TYPES = ("EQUITY", "ETF", "MUTUALFUND")       # 야후 종류가 이 밖이면 회사 주식이 아니에요


def us_preferred_reason(t, names, quote_type=None):
    """우선주·예탁증서(회사 보통주가 아님)로 보는 이유 한 줄, 아니면 None. 이름 → 티커 → 야후 종류 순으로 봐요. (순수 함수)"""
    for n in names:
        if not isinstance(n, str) or not n:
            continue
        m = US_PREF_NAME.search(n)
        if m:
            return f"이름 '{m.group(0)}'"
        if US_DEPOSITARY.search(n) and not US_ADR.search(n):
            return "이름 'Depositary Shares'"
    if US_PREF_TICKER.search(t):
        return "티커"
    if quote_type and quote_type not in US_STOCK_TYPES:
        return f"야후 종류 {quote_type}"
    return None


def us_preferred_like(us, infos=None):
    """미국 목록에 회사처럼 섞여 들어온 우선주·예탁증서 (NASDAQ 상위 400: STRC 는 예전 앱에 배당 12% 소프트웨어 회사로 보였어요).
    ETF·펀드는 보지 않아요. infos = {티커: 야후 정보} (shortName · longName · quoteType, 그리고 목록의 이름 listName). (순수 함수)
    2026-11-03 리뷰: HBANL 은 야후 이름이 'Huntington Bancshares Incorporated' 뿐이라 목록의 이름으로만 알아봐요.
    반환: [(티커, 이유)] 티커 순."""
    infos = infos or {}
    out = []
    for r in us:
        if r.get("etf") is True or r.get("fund"):
            continue
        info = infos.get(r["t"]) or {}
        why = us_preferred_reason(r["t"], (r.get("nk"), r.get("ne"), info.get("shortName"), info.get("longName"),
                                           info.get("listName")), info.get("quoteType"))
        if why:
            out.append((r["t"], why))
    return sorted(out)


def load_us_kr_duplicates(path=None):
    """data/us_kr_duplicates.csv → {미국 티커: (한국 종목코드, 이유)}. 사람이 확인해 적은 표예요. 틀리면 예외 (조용히 넘어가지 않게)."""
    rows = _read_csv(path or US_KR_DUP_PATH)
    out = {}
    for i, r in enumerate(rows):
        t, k, why = r.get("ticker", ""), r.get("krx", ""), r.get("reason", "")
        if not (t and t == t.upper() and t.isascii() and len(t) <= 6) or len(k) != 6 or not why or t in out:
            raise RuntimeError(f"!! us_kr_duplicates.csv {i + 2}번째 줄이 이상해요 (티커 대문자 · 한국 코드 6자리 · 이유 · 티커 한 번만): {r}")
        out[t] = (k, why)
    return out


def drop_us_kr_duplicates(us, kr_codes, dups):
    """미국 목록에서 한국 종목과 같은 회사인 줄을 빼요 (SKHY = SK하이닉스 000660: 덱에 같은 회사가 두 번 들어가지 않게). (순수 함수)
    표에 있어도 그 한국 종목이 이번 국내 목록에 없으면 빼지 않아요 (그 회사가 통째로 사라지지 않게) — 대신 따로 돌려줘서 크게 알려요.
    반환: (남은 미국 목록, 뺀 [(티커, 한국 코드)], 한국 쪽이 없어 남긴 [(티커, 한국 코드)])."""
    keep, dropped, kept = [], [], []
    for r in us:
        hit = dups.get(r["t"])
        if hit and hit[0] in kr_codes:
            dropped.append((r["t"], hit[0]))
            continue
        if hit:
            kept.append((r["t"], hit[0]))
        keep.append(r)
    return keep, dropped, kept


def clean_us_list(us, kr_codes, dups, infos=None):
    """미국 목록에서 한국 종목의 미국 상장분과 우선주·예탁증서를 빼요. 뺀 것은 모두 티커와 함께 로그로 남겨요.
    반환: (남은 미국 목록, {"preferred": [우선주로 뺀 티커], "krListing": [한국 종목이라 뺀 티커]}) — 뒤의 것은 data.json 의
    usLeftOut 으로 나가요 (검증이 우선주로 뺀 수를 세요: 규칙이 진짜 회사를 잡기 시작한 날을 잡으려고)."""
    us, dropped, kept = drop_us_kr_duplicates(us, kr_codes, dups)
    if dropped:
        log(f"  !! 한국 종목과 같은 회사라 미국 목록에서 뺀 종목 {len(dropped)}개: "
            + ", ".join(f"{t}(={k})" for t, k in dropped) + " (data/us_kr_duplicates.csv)")
    if kept:
        log(f"  !! 미국-한국 중복 표에 있지만 그 한국 종목이 이번 국내 목록에 없어 미국 쪽을 남겼어요 {len(kept)}개: "
            + ", ".join(f"{t}(≠{k})" for t, k in kept) + " — 국내 목록이 왜 빠졌는지 확인")
    if not dropped and not kept:
        log(f"· 미국-한국 중복 표 {len(dups)}개 중 이번 미국 목록에 있는 것 없음")
    found = us_preferred_like(us, infos)
    pref = [t for t, _ in found]
    if found:
        gone = set(pref)
        us = [r for r in us if r["t"] not in gone]
        log(f"  !! 미국 우선주·예탁증서로 보고 뺀 종목 {len(found)}개 (티커·이름·야후 종류로 판단): "
            + ", ".join(f"{t}({why})" for t, why in found))
    else:
        log("· 미국 우선주·예탁증서(티커·이름·야후 종류로 판단): 없음")
    no_cap = sorted(r["t"] for r in us if r.get("etf") is not True and not r.get("fund") and (_fin(r.get("price")) or 0) > 0
                    and _fin(r.get("val")) is not None and not ((_fin(r.get("cap")) or 0) > 0))
    if no_cap:
        log(f"  !! 거래대금은 있는데 시가총액이 없는 미국 회사 주식 {len(no_cap)}개 — 빼지 않고 빈 칸으로 둬요 "
            f"(검증의 '미국 시가총액 채움'이 세요): {', '.join(no_cap[:10])}{'…' if len(no_cap) > 10 else ''}")
    return us, {"preferred": list(pref), "krListing": [t for t, _ in dropped]}


def cut_words(text, n):
    """n 글자 안에서 낱말 경계로 잘라요 ("nanometer" 가 잘려 "nan" 이 남지 않게). (순수 함수)"""
    t = " ".join(str(text).split())
    if len(t) <= n:
        return t
    cut = t[:n + 1]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > n * 0.6 else t[:n]).rstrip(" ,;:-")


def apply_us_info(rec, info, px_then, fx):
    """야후 상세 정보를 종목에 붙여요. 받은 날 이후 가격이 움직였으면 PER·PBR·시총·배당률을 오늘 가격에 맞춰요. (순수 함수)"""
    nm = info.get("shortName") or info.get("longName")
    if not nm:
        return False
    rec["nk"] = rec["ne"] = str(nm)
    rec["s"] = map_sector_us(info.get("sector"), info.get("industry"))
    if info.get("industry"):
        rec["_yind"] = str(info["industry"])     # 업종 그룹용 (assign_industries 가 쓰고 지워요)
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
        rec["de"] = cut_words(str(summ), 400)
    return True


def fetch_us(start, today, rf, kr_codes=frozenset(), dups=None):
    """미국 주식 (yfinance). v17.5.2: 우선주·예탁증서와 한국 종목의 미국 상장분(kr_codes · dups)은 빼요 (clean_us_list). v17.5:
    · end 는 그날을 빼므로 오늘(KST)+1일까지 요청하고, 장이 안 끝난 봉은 버려요 (예전엔 하루 늦었어요).
    · 시가총액(cap)은 조원, 거래대금(val)은 억원 — 한국과 같은 단위 (그날 환율로 환산).
    · 상세 정보(이름·업종·설명)를 못 받은 종목 수를 남기고, 실패분은 한 번 더 천천히 시도해요."""
    import yfinance as yf

    list_names = {}
    syms = us_tickers(list_names)
    log(f"· 미국 {len(syms):,}개 종목…")
    end_x = today + dt.timedelta(days=1)
    last_ok = us_last_complete_day()

    fx = cut_at(_yf_close(yf.download(FX_TICKER, start=start, end=end_x, progress=False, auto_adjust=True)), today)
    spx = cut_at(_yf_close(yf.download(US_INDEX, start=start, end=end_x, progress=False, auto_adjust=True)), last_ok)
    us_px_date = us_data_date(spx, last_ok)
    fx = cut_at(fx, max(us_px_date, last_ok))
    fx_last, fx_date = float(fx.iloc[-1]), fx.index[-1].date()
    log(f"· 미국 기준일(S&P500 마지막 봉) {us_px_date} · 환율 {fx_last:,.1f} ({fx_date})")
    bench = spx.pct_change().dropna()
    bench.name = "bench"
    spx_krw = (spx * fx.reindex(spx.index).ffill()).dropna()
    us_vol_krw = ann_vol(spx_krw.pct_change().dropna().values)

    data = yf.download(syms, start=start, end=end_x, progress=False,
                       auto_adjust=True, group_by="ticker", threads=True)

    out, dropped, bad_bar = [], [], []
    for sym in syms:
        try:
            px = cut_at(_yf_close(data, sym), us_px_date)
            if len(px) < 60:
                continue
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a, bse, bn = beta_fit(ret, bench, rf)
            krw = (px * fx.reindex(px.index).ffill()).dropna()
            if us_d1(px, us_px_date) is None and us_own_date(px, us_px_date) is None:
                bad_bar.append(sym)      # 기준일 봉은 있는데 그 전 봉이 깨짐 (0·무한) — 날짜를 말할 수 없는 가격은 내보내지 않아요
                continue
            rec = {"t": sym, "nk": sym, "ne": sym, "cls": "us", "ccy": "USD", "fxu": True, "s": "etc",
                   "etf": sym in US_ETFS,
                   "d1": us_d1(px, us_px_date),
                   "pxd": us_own_date(px, us_px_date),   # v19.1c: 자기 가격 날짜 (기준일과 같으면 None → 칸이 빠져요)
                   "price": round(float(px.iloc[-1]), 2),
                   "vol": ann_vol(krw.pct_change().dropna().values), "beta": b, "al": a,
                   "betaSE": bse, "betaN": bn,   # v19.1b: beta_fit 은 넷을 함께 내거나 함께 비워요
                   "lo": round(float(px.tail(252).min()), 2), "hi": round(float(px.tail(252).max()), 2)}
            rec.update(perf_stats(px, rf))
            out.append({k: v for k, v in rec.items() if v is not None})
        except Exception:
            dropped.append(sym)
    if dropped:
        log(f"  !! 시세를 받지 못해 빠진 미국 종목 {len(dropped)}개: {', '.join(dropped[:8])}{'…' if len(dropped) > 8 else ''}")
    if bad_bar:
        log(f"  !! 기준일 {us_px_date} 봉은 있는데 그 전 봉이 깨져(0·무한) 뺀 미국 종목 {len(bad_bar)}개: {', '.join(bad_bar)}")

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
    odd = etf_from_quote_type(out, cache)
    if odd:
        log(f"  !! 목록엔 회사로 돼 있는데 야후가 ETF·펀드라고 하는 종목 {len(odd)}개 → ETF 로 표시: {', '.join(odd[:10])}")
    infos = {r["t"]: {**((cache.get(r["t"]) or {}).get("info") or {}), "listName": list_names.get(r["t"])} for r in out}
    out, left_out = clean_us_list(out, kr_codes, dups or {}, infos)   # ETF 표시가 끝난 뒤에 (ETF·펀드는 우선주로 보지 않아요)
    no_info = set(missing)
    n_ok = sum(1 for r in out if r["t"] not in no_info)
    n_d1 = sum(1 for r in out if r.get("d1") is not None)
    log(f"· 미국 d1(전 거래일 대비): {n_d1:,} / {len(out):,} · ETF {sum(1 for r in out if r.get('etf')):,}개")
    no_d1 = [f"{r['t']}({r.get('pxd') or '?'})" for r in out if r.get("d1") is None]
    if no_d1:   # 발행 관문이 98% 아래면 막고 전부 적어요 — 여기서는 앞의 30개 (Jack, 2026-11-07). 괄호 = 그 종목의 자기 가격 날짜(pxd)
        log(f"  !! 미국 d1 없는 종목 {len(no_d1):,}개 (마지막 봉이 미국 기준일 {us_px_date} 이 아님 — 거래 정지이거나 야후가 봉을 "
            f"빠뜨림 · 가격은 괄호 날짜의 종가로 나가요): {', '.join(no_d1[:30])}" + (f" 외 {len(no_d1) - 30:,}개" if len(no_d1) > 30 else ""))
    meta = {"usPxDate": us_px_date.isoformat(), "fxDate": fx_date.isoformat(), "usInfo": [n_ok, len(out)], "_index": spx,
            "usLeftOut": {**left_out, "badBar": bad_bar}}   # v19.1c: 깨진 봉으로 뺀 종목도 관문이 경고로 이름을 남겨요
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
         "d1": "% (전 거래일 공식 종가 대비 · 미국은 자기 기준일, 야후 수정 종가라 배당락일엔 배당 포함 · 한국 ±30% 넘거나 직전 거래일 파일이 없으면 빈 칸)",
         "dps": "원 (한국 · 0 = 배당 없음, 빈 칸 = 모름)",
         "fy": "op·debt·roe·opm·g3·dps·dps3 가 나온 사업보고서 연도 (bq 는 TTM 분기)",
         "dps3a": "원 (한국 · dps3 를 오늘 상장 주식 수 기준으로 맞춘 값 [당기, 전기, 전전기] · 빈 칸 = 그해 기준을 확인하지 못함)",
         "dpsF": "배율 (오늘 주식 수 ÷ 그해 배당금의 기준 주식 수 · 1 = 그대로 · dps3a = dps3 ÷ dpsF · 배당 없는 해는 빈 칸)",
         "divSt": "same 그대로 · adj 분할·무상증자를 맞춤 · nc 비교 불가(어중간한 주식 수 변화) · nd 알 수 없음 · zero 3년 배당 없음",
         "dyt": "% (한국 · 오늘 종가 기준 배당수익률 = dps3a[0] ÷ price · 확인 못 한 종목은 빈 칸 · dz 는 이 값의 시장 내 백분위)",
         "betaSE": "베타의 표준오차 (일별 수익률 회귀) · betaN 은 쓴 일별 수익률 수",
         "etf": "true = ETF·펀드·금현물 (회사 주식이 아님)",
         "price": "한국 원 · 미국 달러 · 금현물 원/g", "pct": "% (vol·mdd·r1·r3·r36·mom·al·dy·roe 등)",
         "pxDate": "한국 가격의 공식 종가 날짜", "usPxDate": "미국 가격의 마지막 완성 봉 날짜",
         "pxd": "미국 종목의 자기 가격 날짜 (그 종목의 마지막 봉이 usPxDate 가 아닐 때만 · 가격·d1 은 이 날짜 기준, d1 은 빈 칸)",
         "nextPub": "다음 발행 예정일 (한국 날짜 · data/market_holidays.csv 기준 한국·미국 중 먼저 오는 다음 거래일의 다음 날)",
         "staleAfter": "이 시각(한국 시간)이 지나도 새 파일이 없으면 앱이 '갱신이 멈췄어요'를 보여요 (예정일 마지막 정해진 실행 + 2시간)",
         "usLeftOut": "미국 목록에서 뺀 티커: preferred = 우선주·예탁증서(티커·이름·야후 종류로 판단), krListing = 한국 종목의 미국 상장분"}
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
    sample = sample_size()
    if sample and (on_main or (os.environ.get("DRY_RUN") or "").lower() != "true"):
        raise RuntimeError("!! 표본 실행(SAMPLE_KR)은 main 이 아닌 시험 실행(dry_run=true)에서만 써요 — 발행하면 안 돼요")
    if sample:
        log(f"  !! 표본 실행: 국내 종목을 필수 종목 + 시가총액 상위 {sample}개로 줄여요 (DART 호출 아끼기 · 이 결과는 발행하지 않아요 · "
            "관문의 종목 수 검사는 실패하는 게 정상이에요)")
    ph = Phases()
    prev = read_prev_data()
    tables = load_industry_tables()       # 업종 표가 깨졌으면 여기서 바로 멈춰요
    dups = load_us_kr_duplicates()        # 미국-한국 중복 표도 (v17.5.2)
    special = load_krx_special_sessions() # KRX 특별 거래시간 표도 (v17.5.4) — 최종본 판단에 써요
    try:                                  # 휴장일 표도 (v19.1c) — '늦음' 경고 시각에만 써서, 깨졌거나 모자라도 멈추지 않고 크게 남겨요
        hol = load_market_holidays()
        if hol["end"] < today + dt.timedelta(days=45):
            log(f"  !! 휴장일 표가 {hol['end']} 까지만 있어요 — 그 뒤는 평일 규칙으로 정해요 (휴장일 다음 날 '늦음' 경고가 일찍 뜰 수 있어요). "
                "data/market_holidays.csv 에 다음 해를 넣어 주세요 (RUNBOOK)")
    except Exception as e:
        hol = {"KR": {}, "US": {}, "start": None, "end": None}
        log(f"  !! 휴장일 표를 읽지 못했어요 ({e}) — 평일 규칙으로 정해요 (휴장일 다음 날 '늦음' 경고가 일찍 뜰 수 있어요). 표를 고쳐 주세요")
    soon = [f"{d} {v['kind']} {v['open']:%H:%M}~{v['close']:%H:%M}" for d, v in sorted(special.items())
            if today - dt.timedelta(days=LISTING_LOOKBACK_DAYS) <= d <= today + dt.timedelta(days=60)]
    log(f"· KRX 특별 거래시간 표: {len(special)}줄" + (f" · 최근·다가오는 날: {' · '.join(soon)}" if soon else ""))
    log(f"· 업종 표: 그룹 {len(tables['groups'])} · KSIC 접두어 {len(tables['kmap'])} · 야후 업종 {len(tables['usmap'])} · "
        f"고정 {len(tables['over'])} · 주요제품 나누기 {len(tables['refine'])}")

    rf, rf_src = ph.run("금리", fetch_rf, today)
    kr, kr_bench, kr_mkt, kmeta = ph.run("국내 시세", fetch_korea, start, today, rf, prev)
    px_date = dt.date.fromisoformat(kmeta["pxDate"]) if kmeta["pxDate"] else today - dt.timedelta(days=1)

    fin_map, client, ksic = {}, None, {}
    # v19.1b: v2 캐시가 없던 첫 실행은 워크플로가 v1 폴더를 받아요(미국 상세 정보 보관본을 이어 쓰려고). 옛 DART 파일은 읽지 않으니
    # 지워서 v2 캐시에 실려 가지 않게 해요.
    for old_name in ("dart-v1.json.gz", "dart-v2.json.gz"):      # v19.1f: v2 파일도 (v3 부터 새로 받아요)
        legacy = os.path.join(os.path.dirname(DART_CACHE_PATH) or ".", old_name)
        if os.path.abspath(legacy) != os.path.abspath(DART_CACHE_PATH) and os.path.exists(legacy):
            os.remove(legacy)
            log(f"· 옛 DART 캐시 파일을 지웠어요 ({legacy}) — 읽지 않아요 (v{DART_CACHE_VERSION} 부터 새로 받아요)")
    if dart_mode == "off":
        log("  !! 시험 실행: DART 를 끄고 진행해요 (재무지표·공시 없음 → 검증에서 실패 처리돼요)")
    elif DART_KEY:
        client = DartClient(DART_KEY, mode=dart_mode, today=today)
        kr, fin_map = ph.run("DART", enrich_with_dart, kr, client)
        ksic = ph.run("업종 코드", fetch_ksic, kr, client)
    else:
        log("  !! DART_API_KEY 없음 → 재무지표·공시를 못 받아요 (검증에서 실패 처리돼요)")
    blank_foreign_dart(kr)                # v17.5.2: 해외 기업 (점수·corp.json 보다 먼저)
    fill_multiples(kr, fin_map)
    # v19.1b: 분할에 안전한 배당 (dps3a·dpsF·divSt·dyt) — 해외 기업 비우기 뒤, 점수(dz)·corp.json 보다 먼저
    div_counts, corp_extra = apply_div_basis(kr, fin_map, kmeta.get("_prefShares") or {})
    n_dy = sum(1 for s in kr if s.get("dy") is not None)
    log(f"· 배당수익률 아는 종목: {n_dy:,} / {len(kr):,} (모르는 종목은 0% 가 아니라 빈 칸 → 앱에 '–')")
    n_dps = sum(1 for s in kr if s.get("dps") is not None)
    n_dps0 = sum(1 for s in kr if s.get("dps") == 0)
    fy_c = collections.Counter(s.get("fy") for s in kr if s.get("fy"))
    log(f"· 주당 배당금 아는 종목: {n_dps:,} / {len(kr):,} (그중 0원 = 배당 없음 {n_dps0:,}) · 사업보고서 연도 {dict(sorted(fy_c.items()))}")

    us, us_bench, fx, fx_last, us_vol_krw, umeta = ph.run("미국", fetch_us, start, today, rf,
                                                          kr_codes=frozenset(s["t"] for s in kr), dups=dups)
    names = etf_names()
    bonds, bd_ret = ph.run("채권", fetch_bonds, start, px_date, kr_bench, names, rf)

    gold_usd = None
    try:
        import yfinance as yf
        gold_usd = _yf_close(yf.download("GC=F", start=start, end=today + dt.timedelta(days=1), progress=False, auto_adjust=True))
    except Exception as e:
        log(f"  !! 국제 금값(GC=F) 실패: {e}")
    funds = ph.run("ETF·금현물", fetch_kr_funds, start, px_date, kr_bench, names, rf, gold_usd, fx)

    icnt = assign_industries(kr + us, tables, ksic, products=kmeta.get("_prod"))
    for m in ("kr", "us"):
        arr = kr if m == "kr" else us
        g = collections.Counter(x.get("ind") for x in arr if x.get("ind"))
        log(f"· 업종 그룹 ({m}): {len(g)}개 · 그룹 있음 {sum(g.values()):,} / {len(arr):,} · "
            + " · ".join(f"{k} {v}" for k, v in g.most_common(8)) + " …")
    miss = {k: v for k, v in icnt.items() if "없음:" in k}
    log(f"· 업종 그룹 집계: {dict((k, v) for k, v in icnt.items() if '없음:' not in k)}")
    if miss:
        log(f"  !! 업종 표에 없는 코드·이름 {sum(miss.values())}종목: "
            + " · ".join(f"{k.split('없음:')[1]} {v}" for k, v in sorted(miss.items(), key=lambda kv: -kv[1])[:15])
            + " (industry_map.csv / industry_us.csv 에 넣을지 확인)")

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
    # v19.1b: 배당 순위(dz)는 확인한 배당으로만 매겨요. 필수 종목은 꼭 들어 있어야 해요 (CLAUDE.md: 빈 칸일 수 있는 값으로
    # 고르거나 줄 세우면 꼭 있어야 할 종목이 들어 있는지 확인). 빠지면 여기서 이유와 함께 크게 남겨요. 관문의 '필수 종목 배당 순위'
    # 줄은 1곳이면 경고(종목·이유), 2곳 이상이면 실패로 발행을 막아요 (Jack 2026-11-05: 배당 자료 구멍 하나가 사이트를 멈추지 않게).
    # 여기서 멈추지 않는 건 파일과 관문 표가 남아야 시험 실행에서 원인을 볼 수 있어서예요.
    n_dz = sum(1 for s in kr if _fin(s.get("dz")) is not None)
    miss_dz = dividend_rank_missing(kr)
    log(f"{'  !! ' if miss_dz else '· '}배당 순위(dz): {n_dz:,}종목 · 필수 종목 "
        + ("모두 있음" if not miss_dz else "빠짐: " + ", ".join(f"{t}({why})" for t, why in miss_dz)
           + (" — 관문에서 실패해 발행하지 않아요" if len(miss_dz) >= DIV_RANK_MISS_FAIL
              or any(t not in {s["t"] for s in kr} for t, _ in miss_dz)          # 목록에 없는 필수 종목은 다른 줄이 실패로 막아요
              else " — 관문에서 경고해요 (이 일로는 발행이 막히지 않아요 · 이 종목은 배당 순위에서 빠져요)")))
    stocks = kr + us + bonds + funds
    if selftest == "corrupt-price":
        for x in stocks:
            if x["t"] == "005930":
                x["price"] = round(x["price"] * 1.1)
                log(f"  !! 시험용(selftest): 005930 가격을 일부러 {x['price']:,}원으로 틀리게 써요 — 검증이 막아야 합니다")

    try:      # 여기서 멈추지 않아요: 빈 칸으로 쓰면 관문이 경고하고, 앱은 예전 4일 규칙으로 '늦음'을 봐요 (Jack, 2026-11-07)
        next_pub = next_publish(dt.date.fromisoformat(kmeta["pxDate"]), dt.date.fromisoformat(umeta["usPxDate"]), hol)
        log(f"· 다음 발행 예정일 {next_pub} · 늦음 경고 {stale_after(next_pub)} (휴장일 표 "
            + (f"{hol['end'].year}년까지 · 한국 {len(hol['KR'])}일 · 미국 {len(hol['US'])}일)" if hol.get("end") else "없음 — 평일 규칙)"))
    except Exception as e:
        next_pub = None
        log(f"  !! 다음 발행 예정일을 정하지 못했어요 ({type(e).__name__}: {e}) → 빈 칸으로 써요 (관문이 경고해요 · 앱은 예전 4일 규칙)")
    payload = {
        "asOf": today.isoformat(), "pxDate": kmeta["pxDate"], "ksDate": kmeta["ksDate"],
        "usPxDate": umeta["usPxDate"], "fxDate": umeta["fxDate"], "publishedAt": published_at,
        "nextPub": next_pub.isoformat() if next_pub else None,               # v19.1c: 앱의 '늦음' 판단 (고정 4일 대신)
        "staleAfter": stale_after(next_pub) if next_pub else None,
        "listSrc": kmeta["listSrc"], "fx": round(fx_last, 1), "units": UNITS, "settings": settings,
        "popular": popular_list(kr, us),
        "count": {"kr": len(kr), "us": len(us), "bond": len(bonds), "fund": len(funds), "usInfo": umeta["usInfo"]},
        "usLeftOut": umeta["usLeftOut"],     # v17.5.2: 미국 목록에서 뺀 티커 (우선주·예탁증서 · 한국 종목의 미국 상장분) — 검증이 세요
        "divCheck": div_counts,              # v19.1b: 배당 분할 확인 집계 (관문이 종목과 맞춰 봐요 · 이 칸이 있으면 새 검사가 다 돌아요)
        "stocks": stocks,
    }
    write_json(OUT, payload)
    log(f"✓ {OUT} 저장 — {len(stocks):,}종목, {os.path.getsize(OUT) / 1e6:.1f}MB · 기준일 {kmeta['pxDate']} · "
        f"미국 {umeta['usPxDate']} · 환율 {fx_last:,.1f}")

    kr_mkt.update({"fx": round(fx_last, 1), "rf": round(rf * 100, 2)})
    corp = build_corp(kr, fin_map, today.isoformat(), kr_mkt, extra=corp_extra)
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
        n_calls = sum(client.status.values())
        if n_calls > DART_FULL_TARGET:
            log(f"  !! 이번 실행의 DART 호출 {n_calls:,}회가 목표 {DART_FULL_TARGET:,}회를 넘었어요 (하루 한도 {DART_DAY_LIMIT:,})")
    else:
        disc = {"asOf": today.isoformat(), "newest": None, "listOk": False, "insider": [], "nps": []}
    disc["publishedAt"] = published_at
    write_json(OUT_DISC, disc)
    log(f"✓ {OUT_DISC} 저장 — 내부자 {len(disc['insider']):,}건 · 국민연금 {len(disc['nps']):,}건 · 최근 공시 {disc.get('newest')}")
    log(ph.summary())


if __name__ == "__main__":
    main()
