#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
뱁새(Baepsae) 데이터 수집 스크립트 v10
──────────────────────────────────────────────────────────────
매일 한 번 GitHub Actions 가 이 파일을 실행해서 data.json 을 만듭니다.
data.json 은 baepsae.html 과 같은 폴더에 놓이며, 도구가 자동으로 읽어갑니다.

수집·계산하는 값
  기본     price(현재가) cap(시가총액) val(거래대금) lo/hi(52주)
  위험     beta(자기 시장 대비) vol(연 변동성, 원화 기준) mdd(최대 낙폭) hit(상승 월 비율)
  성과     al(3년 알파 %p) sh(3년 샤프) mom(12개월 수익률)
  가치·질  per pbr dy roe debt opm g3(매출성장) frn(외국인)
  분류     s(업종 — KRX 업종분류에서 매핑) dk(사업 개요)
  팩터     pz(규모) vz(가치) mz(모멘텀) qz(퀄리티) — 시장 내 백분위 0~100

시장 가정(도구의 기본값으로 자동 반영)
  rf 국고채 10년 · mktVol/usVol/mtVol 지수 변동성 · rhoKrUs/rhoKrMt/rhoUsMt 상관계수

DART_API_KEY 환경변수가 있으면 한국 기업의 재무지표(부채비율·매출성장률·영업이익률·ROE)를
OpenDART 에서 가져옵니다. 없으면 그 항목만 비워두고 나머지는 정상 동작합니다.

실패에 강하게 만들었습니다. 개별 종목이 실패하면 건너뛰고, 전체의 상당수를 못 받아온
경우에만 오류로 종료합니다(그래야 기존 data.json 이 안 망가집니다).
"""

import io
import json
import math
import os
import sys
import time
import zipfile
import datetime as dt
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
YEARS = 3                 # 베타·변동성·알파·샤프 계산 기간
MIN_DAYS = 250            # 이보다 데이터가 적으면 통계값 생략
MAX_KR = 2000             # 한국 종목 수 상한(시가총액 순). 늘리면 오래 걸립니다
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

KR_INDEX = "KS11"
US_INDEX = "^GSPC"
FX_TICKER = "USDKRW=X"
KR_BOND = "KR10YT=RR"

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
    """규모·가치·모멘텀·퀄리티를 시장 내 백분위(0~100)로 환산"""
    df = pd.DataFrame({
        "cap": [s.get("cap") for s in stocks],
        "pbr": [s.get("pbr") for s in stocks],
        "mom": [s.get("mom") for s in stocks],
        "roe": [s.get("roe") for s in stocks],
    })

    def pr(col):
        return df[col].rank(pct=True) * 100

    # 규모는 작을수록, 가치는 PBR 낮을수록 높은 점수 (SMB·HML 방향과 일치)
    series = {"pz": 100 - pr("cap"), "vz": 100 - pr("pbr"), "mz": pr("mom"), "qz": pr("roe")}
    for i, s in enumerate(stocks):
        for k, ser in series.items():
            v = ser.iloc[i]
            if pd.notna(v):
                s[k] = int(round(v))
    return stocks


# ────────────────────────────────────────────────────────────
# OpenDART — 한국 기업 재무지표
# ────────────────────────────────────────────────────────────
def dart_corp_map():
    if not DART_KEY:
        return {}
    try:
        r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml",
                         params={"crtfc_key": DART_KEY}, timeout=90)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        root = ET.fromstring(zf.read(zf.namelist()[0]))
        m = {}
        for el in root.iter("list"):
            sc = (el.findtext("stock_code") or "").strip()
            cc = (el.findtext("corp_code") or "").strip()
            if sc and len(sc) == 6 and cc:
                m[sc] = cc
        log(f"· DART 기업코드 {len(m):,}건 확보")
        return m
    except Exception as e:
        log(f"  (DART 기업코드 실패: {e})")
        return {}


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
    if rev[0] and rev[2] and rev[2] > 0:
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


def parse_dart_dividend(rows):
    """alotMatter(배당에 관한 사항) 응답에서 보통주 배당 지표를 뽑습니다. (순수 함수)"""
    dy = dps = None
    dps3 = [None, None, None]
    for row in rows:
        knd = (row.get("stock_knd") or "")
        if knd and "보통" not in knd:
            continue
        se = (row.get("se") or "").replace(" ", "")
        v = _num(row.get("thstrm"))
        if v is None:
            continue
        if "주당현금배당금" in se and dps is None:
            dps = v
            dps3 = [_num(row.get("thstrm")), _num(row.get("frmtrm")), _num(row.get("lwfr"))]
        elif "현금배당수익률" in se and dy is None:
            dy = v
    out = {}
    if dps and dps > 0:
        out["dps"] = round(dps, 0)
        out["dps3"] = [round(x, 0) if x is not None else None for x in dps3]
    if dy and dy > 0:
        out["dy"] = round(dy, 2)
    return out


def dart_dividend(corp_code, year):
    try:
        r = requests.get("https://opendart.fss.or.kr/api/alotMatter.json",
                         params={"crtfc_key": DART_KEY, "corp_code": corp_code,
                                 "bsns_year": str(year), "reprt_code": "11011"},
                         timeout=25)
        j = r.json()
        if j.get("status") != "000":
            return {}
        return parse_dart_dividend(j.get("list", []))
    except Exception:
        return {}


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


def dart_quarter(corp_code, year, reprt):
    for fs in ("CFS", "OFS"):
        try:
            r = requests.get("https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
                             params={"crtfc_key": DART_KEY, "corp_code": corp_code,
                                     "bsns_year": str(year), "reprt_code": reprt, "fs_div": fs},
                             timeout=25)
            j = r.json()
            if j.get("status") != "000":
                continue
            out = parse_dart_quarter(j.get("list", []))
            if out:
                return out
        except Exception:
            continue
    return None


def dart_financials(corp_code, year):
    """연결(없으면 별도) 재무제표에서 주요 지표 + 3개년 원값을 뽑습니다."""
    for fs in ("CFS", "OFS"):
        try:
            r = requests.get("https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
                             params={"crtfc_key": DART_KEY, "corp_code": corp_code,
                                     "bsns_year": str(year), "reprt_code": "11011", "fs_div": fs},
                             timeout=25)
            j = r.json()
            if j.get("status") != "000":
                continue
            out = parse_dart_list(j.get("list", []))
            if out:
                return out
        except Exception:
            continue
    return {}


def enrich_with_dart(kr_stocks):
    fin_map = {}
    if not DART_KEY:
        log("· DART_API_KEY 없음 → 재무지표(부채비율·성장률·영업이익률) 생략")
        return kr_stocks, fin_map
    cmap = dart_corp_map()
    if not cmap:
        return kr_stocks, fin_map
    year = dt.date.today().year - 1
    targets = [s for s in kr_stocks if s["t"] in cmap]
    # 올해 어느 분기 보고서까지 나왔는지 삼성전자로 1회 판별 (3Q → 반기 → 1Q)
    cur_year = dt.date.today().year
    Q_ORDER = [("11014", "3Q"), ("11012", "2Q"), ("11013", "1Q")]
    q_code, q_ko = None, None
    probe = cmap.get("005930")
    if probe:
        for code, ko in Q_ORDER:
            if dart_quarter(probe, cur_year, code):
                q_code, q_ko = code, ko
                break
    log(f"· DART 재무지표 조회 {len(targets):,}건 ({year}년 사업보고서"
        + (f" + {cur_year}.{q_ko} TTM 합성" if q_code else " · 분기 미확인 → 연간 기준") + ")…")
    done = [0]

    def one(s):
        yr = year
        f = dart_financials(cmap[s["t"]], yr)
        if not f:
            yr = year - 1
            f = dart_financials(cmap[s["t"]], yr)
        div = dart_dividend(cmap[s["t"]], yr)
        if div.get("dps"):
            s["dps"] = div["dps"]
        if div.get("dps3"):
            s["dps3"] = div["dps3"]
        if div.get("dy"):
            s["dy"] = div["dy"]
        if f:
            fin = f.pop("_fin", None)
            if fin:
                # TTM 합성: 올해 누적 + 전년 동기 누적
                if q_code:
                    ytd = dart_quarter(cmap[s["t"]], cur_year, q_code)
                    ytd_prev = dart_quarter(cmap[s["t"]], cur_year - 1, q_code) if ytd else None
                    t2 = compute_ttm(fin, ytd, ytd_prev)
                    if t2:
                        fin["ttm"] = t2["ttm"]
                        fin["bs2"] = t2["bs"]
                        fin["bq"] = f"{cur_year}.{q_ko}"
                fin_map[s["t"]] = fin
            s.update(f)
        done[0] += 1
        if done[0] % 250 == 0:
            log(f"  … {done[0]:,}/{len(targets):,}")
        return s

    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(one, targets))
    got = sum(1 for s in targets if s.get("debt") is not None)
    log(f"· DART 완료: {got:,}건 재무지표 · {len(fin_map):,}건 3개년 원값")
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
    ("304660", ["미국채", "30"], "KODEX 미국채울트라30년선물(H)", 20.0, True, "미국채"),
]


def fetch_bonds(start, end, kr_bench):
    """상장 채권 ETF를 받아 채권 블록 레코드와 블록 대표 수익률(10년 국고 기준)을 만듭니다."""
    import FinanceDataReader as fdr
    names = {}
    try:
        lst = fdr.StockListing("ETF/KR")
        for _, row in lst.iterrows():
            names[str(row.get("Symbol") or row.get("Code") or "")] = str(row.get("Name") or "")
    except Exception as e:
        log(f"  (ETF 목록 확인 생략: {e} — 이름 검증 없이 진행)")

    recs, proxy = [], None
    for t, kws, label, dur, hedged, grp in BOND_ETFS:
        nm = names.get(t, "")
        if nm and not all(k in nm.replace(" ", "") for k in kws):
            log(f"  !! 채권 ETF {t} 이름 불일치(기대 {kws} ↔ 실제 {nm}) — 제외")
            continue
        try:
            px = fdr.DataReader(t, start, end)["Close"].dropna()
            if len(px) < 60:
                log(f"  (채권 ETF {t} 데이터 부족 — 제외)")
                continue
            ret = px.pct_change().dropna()
            vol = float(np.nanstd(ret.values, ddof=1)) * math.sqrt(252) * 100
            if vol > 30:
                log(f"  !! 채권 ETF {t} 변동성 {vol:.0f}% — 채권답지 않아 제외")
                continue
            jb = pd.concat([ret.rename("b"), kr_bench.rename("m")], axis=1).dropna()
            beta = 0.0
            if len(jb) > 60 and jb["m"].var() > 0:
                beta = round(float(jb["b"].cov(jb["m"]) / jb["m"].var()), 2)
            dd = float((px / px.cummax() - 1).min()) * 100
            hj = "환헤지형이라 환율 변동은 막혀 있어요." if hedged else "환노출형이라 달러가 오르면 추가 수익, 내리면 손실이 더해져요."
            dk = (f"{grp} 채권 ETF · 듀레이션 약 {dur:g}년. 금리가 1%p 오르면 대략 {dur:g}% 안팎 하락하는 민감도예요. "
                  + (hj if grp == "미국채" else "") + "채권 ETF 매매차익에는 배당소득세 15.4%가 붙어요.")
            recs.append({
                "t": t, "nk": nm or label, "ne": nm or label, "cls": "bond", "s": "bond",
                "price": round(float(px.iloc[-1]), 0), "vol": round(vol, 1), "beta": beta,
                "lo": round(float(px.tail(252).min()), 0), "hi": round(float(px.tail(252).max()), 0),
                "mdd": round(dd, 1), "dy": None, "per": None, "pbr": None, "al": 0,
                "dur": dur, "hedged": hedged, "grp": grp, "dk": dk,
                "x": {"dk": dk, "de": ""},
            })
            if t == "148070":
                proxy = ret
        except Exception as e:
            log(f"  (채권 ETF {t} 실패: {e})")
    log(f"· 채권 ETF {len(recs)}종 수집" + ("" if proxy is not None else " · 대표 시계열 없음(블록 상관 생략)"))
    return recs, proxy


def _monthly(series, months=36):
    try:
        m = series.dropna().resample("ME").last().tail(months)
        return {"m": [d.strftime("%y.%m") for d in m.index], "v": [round(float(v), 2) for v in m.values]}
    except Exception:
        return None


def parse_ecos_items(rows):
    """817Y002 품목 목록에서 국고채 만기별 코드 매핑. (순수 함수)"""
    import re
    out = {}
    for r in rows:
        nm = (r.get("ITEM_NAME") or "").replace(" ", "")
        if "물가연동" in nm:
            continue
        m = re.search(r"국고채.*?(1|2|3|5|10|20|30)년", nm)
        if m:
            out.setdefault(int(m.group(1)), r.get("ITEM_CODE"))
    return out


def fetch_macro(start, end, gold_krw_px=None, fx=None):
    """금리·원자재 데이터: 국고채 커브(ECOS)·장단기 금리차·금은유가."""
    import FinanceDataReader as fdr
    out = {"asOf": end.isoformat(), "curve": None, "sprKr": None, "sprUs": None,
           "gold": None, "silver": None, "wti": None}
    s3 = end - dt.timedelta(days=365 * 3 + 30)

    # 미국 장단기 (FRED, 키 불필요)
    try:
        d10 = fdr.DataReader("FRED:DGS10", s3, end).iloc[:, 0]
        d2 = fdr.DataReader("FRED:DGS2", s3, end).iloc[:, 0]
        spr = (d10 - d2).dropna()
        out["sprUs"] = _monthly(spr)
    except Exception as e:
        log(f"  (미국 금리차 생략: {e})")

    # 원자재
    try:
        import yfinance as yf
        def yfc(tk):
            v = yf.download(tk, start=s3, end=end, progress=False, auto_adjust=True)["Close"]
            return v.iloc[:, 0] if isinstance(v, pd.DataFrame) else v
        if fx is not None:
            fxa = fx.reindex(pd.date_range(s3, end)).ffill()
            g = yfc("GC=F"); out["gold"] = _monthly((g * fxa.reindex(g.index).ffill()).dropna())
            sv = yfc("SI=F"); out["silver"] = _monthly((sv * fxa.reindex(sv.index).ffill()).dropna())
    except Exception as e:
        log(f"  (금·은 생략: {e})")
    try:
        w = fdr.DataReader("FRED:DCOILWTICO", s3, end).iloc[:, 0]
        out["wti"] = _monthly(w)
    except Exception as e:
        log(f"  (WTI 생략: {e})")

    # 국고채 커브 + 한국 장단기 (ECOS)
    if not ECOS_KEY:
        log("· ECOS_API_KEY 없음 → 국고채 커브 생략 (설정 방법은 가이드 참고)")
        return out
    try:
        r = requests.get(f"https://ecos.bok.or.kr/api/StatisticItemList/{ECOS_KEY}/json/kr/1/200/817Y002", timeout=25)
        rows = (r.json().get("StatisticItemList") or {}).get("row") or []
        items = parse_ecos_items(rows)
        log(f"· ECOS 국고채 만기 확인: {sorted(items.keys())}")
        series = {}
        for yr, code in sorted(items.items()):
            u = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}/json/kr/1/1200/817Y002/D/"
                 f"{s3.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}/{code}")
            rr = requests.get(u, timeout=30)
            rw = (rr.json().get("StatisticSearch") or {}).get("row") or []
            if not rw:
                continue
            idx = pd.to_datetime([x["TIME"] for x in rw], format="%Y%m%d")
            series[yr] = pd.Series([float(x["DATA_VALUE"]) for x in rw], index=idx).dropna()
        if series:
            tenors = sorted(series.keys())
            now, ago = [], []
            ago_target = pd.Timestamp(end - dt.timedelta(days=365))
            for yr in tenors:
                s = series[yr]
                now.append(round(float(s.iloc[-1]), 2))
                i = s.index.get_indexer([ago_target], method="nearest")[0]
                ago.append(round(float(s.iloc[i]), 2))
            out["curve"] = {"tenors": tenors, "now": now, "ago": ago,
                            "date": series[tenors[0]].index[-1].strftime("%Y-%m-%d")}
            if 3 in series and 10 in series:
                out["sprKr"] = _monthly((series[10] - series[3]).dropna())
            log(f"· 국고채 커브 {len(tenors)}개 만기 · 기준 {out['curve']['date']}")
    except Exception as e:
        log(f"  !! ECOS 조회 실패: {e}")
    return out


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


def fetch_disclosures(kr_stocks, cmap, end):
    """최근 90일 내부자 거래 + 국민연금 대량보유 변동. 기존 disc.json에 증분 병합.
    실패는 조용히 넘기지 않고 상태 코드를 로그로 남깁니다."""
    empty = {"asOf": end.isoformat(), "insider": [], "nps": []}
    if not DART_KEY:
        log("· DART_API_KEY 없음 → 공시 수집 생략")
        return empty
    corp2t = {v: k for k, v in cmap.items()}
    info = {s["t"]: s for s in kr_stocks if s.get("cls") == "kr"}

    prev, known = empty, set()
    try:
        with open(OUT_DISC, encoding="utf-8") as f:
            prev = json.load(f)
        known = {r.get("rc") for r in prev.get("insider", []) if r.get("rc")}
    except Exception:
        pass

    import datetime as _dt
    bgn = (end - _dt.timedelta(days=89)).strftime("%Y%m%d")  # 조회기간 3개월 제한 안전 마진
    fins_by_corp, nps_corps = {}, {}
    page, stat_note = 1, None
    while page <= 30:
        try:
            r = requests.get("https://opendart.fss.or.kr/api/list.json",
                             params={"crtfc_key": DART_KEY, "bgn_de": bgn, "end_de": end.strftime("%Y%m%d"),
                                     "pblntf_ty": "D", "page_no": str(page), "page_count": "100"}, timeout=25)
            j = r.json()
            if j.get("status") != "000":
                stat_note = f"status={j.get('status')} msg={j.get('message')}"
                break
            for it in j.get("list", []):
                nm = it.get("report_nm") or ""
                if "임원" in nm and "주요주주" in nm:
                    fins_by_corp.setdefault(it["corp_code"], 0)
                    fins_by_corp[it["corp_code"]] += 1
                if "국민연금" in (it.get("flr_nm") or ""):
                    nps_corps[it["corp_code"]] = it
            if page * 100 >= int(j.get("total_count", 0)):
                break
            page += 1
        except Exception as e:
            stat_note = f"예외 {e}"
            break
    log(f"· 공시 목록(list.json): 임원·주요주주 보고 기업 {len(fins_by_corp):,}곳 · 국민연금 관련 {len(nps_corps):,}곳"
        + (f"  !! 목록 조회 중단: {stat_note}" if stat_note else ""))

    targets = [c for c in fins_by_corp if c in corp2t][:DISC_CALL_CAP]
    rows = list(prev.get("insider", []))
    stat_cnt = {}
    def one(code):
        try:
            r = requests.get("https://opendart.fss.or.kr/api/elestock.json",
                             params={"crtfc_key": DART_KEY, "corp_code": code}, timeout=25)
            j = r.json()
            st = j.get("status")
            stat_cnt[st] = stat_cnt.get(st, 0) + 1
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
                amt = round(abs(e["q"]) * (s.get("price") or 0) / 1e8, 1)
                out.append({"rc": e["rc"], "d": e["d"], "t": t, "nk": s["nk"], "s": s.get("s") or "etc",
                            "cap": s.get("cap"), "nm": e["nm"], "pos": e["pos"], "q": e["q"], "r": e["r"], "amt": amt})
            return out
        except Exception:
            stat_cnt["예외"] = stat_cnt.get("예외", 0) + 1
            return []
    if targets:
        with ThreadPoolExecutor(max_workers=5) as ex:
            for res in ex.map(one, targets):
                rows.extend(res)
    log(f"· 내부자 상세(elestock): 기업 {len(targets):,}곳 조회 · 상태 {stat_cnt}")

    rows = [r for r in rows if r.get("d", "") >= bgn]
    rows.sort(key=lambda r: r.get("d", ""), reverse=True)
    seen, dedup = set(), []
    for r in rows:
        if r["rc"] in seen:
            continue
        seen.add(r["rc"]); dedup.append(r)

    nps, nps_stat = [], {}
    for code, it in list(nps_corps.items())[:200]:
        try:
            r = requests.get("https://opendart.fss.or.kr/api/majorstock.json",
                             params={"crtfc_key": DART_KEY, "corp_code": code}, timeout=25)
            j = r.json()
            st = j.get("status")
            nps_stat[st] = nps_stat.get(st, 0) + 1
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
        except Exception:
            nps_stat["예외"] = nps_stat.get("예외", 0) + 1
            continue
    nps.sort(key=lambda r: r.get("d", ""), reverse=True)
    log(f"· 국민연금(majorstock): 상태 {nps_stat} · 채택 {len(nps):,}건 · 내부자 누적 {len(dedup):,}건"
        + (" · 상한 도달, 다음 실행이 이어받음" if len(targets) >= DISC_CALL_CAP else ""))
    return {"asOf": end.isoformat(), "insider": dedup, "nps": nps}


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
            "dy": s.get("dy"), "dps": s.get("dps"),
            "roe": s.get("roe"), "opm": s.get("opm"), "g3": s.get("g3"), "debt": s.get("debt"),
            "beta": s.get("beta"), "vol": s.get("vol"), "lo": s.get("lo"), "hi": s.get("hi"),
            "rev": rev, "op": fin.get("op") or [None, None, None], "ni": ni, "eq": fin.get("eq"),
            "shm": round(s["shr"] / 1e6, 2) if s.get("shr") else None,
            "r1": s.get("r1"), "r3": s.get("r3"), "r36": s.get("r36"), "dps3": s.get("dps3"),
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
            ev = s["cap"] * 1e4 + (eff["bor"] or 0) - (eff["cash"] or 0)
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
            if r2 > 0:
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
def fetch_korea(start, end, rf):
    import FinanceDataReader as fdr

    log("· KRX 종목 목록…")
    listing = fdr.StockListing("KRX")
    code_col = next((c for c in ("Code", "Symbol", "ShortCode", "종목코드") if c in listing.columns), None)
    if code_col is None:
        raise RuntimeError(f"종목코드 열을 못 찾음: {list(listing.columns)}")
    if code_col != "Code":
        listing = listing.rename(columns={code_col: "Code"})
    if "Name" not in listing.columns and "종목명" in listing.columns:
        listing = listing.rename(columns={"종목명": "Name"})
    listing["Code"] = listing["Code"].astype(str).str.strip()
    listing = listing[listing["Code"].str.len() == 6].copy()
    for c in ("Name", "Market", "Marcap", "Amount"):
        if c not in listing.columns:
            listing[c] = np.nan
    listing["Name"] = listing["Name"].fillna(listing["Code"])

    # 업종·주요제품 (KRX 상장법인 상세)
    desc = {}
    for src in ("KRX-DESC", "KOSPI-DESC", "KRX"):
        try:
            d = fdr.StockListing(src)
            cc = next((c for c in ("Code", "Symbol") if c in d.columns), None)
            if cc and ("Sector" in d.columns or "Industry" in d.columns):
                for _, r in d.iterrows():
                    desc[str(r[cc]).strip()] = (str(r.get("Sector", "") or ""), str(r.get("Industry", "") or ""))
                log(f"· 업종 정보 {len(desc):,}건 ({src})")
                break
        except Exception:
            continue
    if not desc:
        log("  (업종 정보를 못 받아왔습니다 — 업종이 '기타'로 들어갑니다)")

    if listing["Marcap"].notna().any():
        listing = listing.sort_values("Marcap", ascending=False)
    if len(listing) > MAX_KR:
        log(f"  → 전체 {len(listing):,}개 중 시가총액 상위 {MAX_KR:,}개 처리 (MAX_KR)")
        listing = listing.head(MAX_KR)
    log(f"  → {len(listing):,}개 종목")

    kospi = fdr.DataReader(KR_INDEX, start, end)["Close"]
    bench = kospi.pct_change().dropna()
    bench.name = "bench"
    mkt = {}
    try:
        mkt = {"kospi": round(float(kospi.iloc[-1]), 2),
               "k1": round(float(kospi.iloc[-1] / kospi.iloc[-22] - 1) * 100, 1),
               "k3": round(float(kospi.iloc[-1] / kospi.iloc[-64] - 1) * 100, 1)}
    except Exception:
        pass

    fundamentals, foreign = {}, {}
    try:
        from pykrx import stock as pk
        day = pk.get_nearest_business_day_in_a_week()
        # 시장별 조회 → 합치기. "ALL" 단일 호출이 pykrx/KRX 사정으로 실패해도 살아남도록
        frames = []
        for mkt in ("KOSPI", "KOSDAQ"):
            try:
                df = pk.get_market_fundamental_by_ticker(day, market=mkt)
                if df is not None and len(df):
                    frames.append(df)
            except Exception as e:
                log(f"  (펀더멘털 {mkt} 실패: {e})")
        if frames:
            fundamentals = pd.concat(frames).to_dict("index")
        else:  # 마지막 수단: 예전 방식
            fundamentals = pk.get_market_fundamental(day, market="ALL").to_dict("index")
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
        log(f"  (PER/PBR 생략: {e})")

    out = []

    def one(row):
        code = row["Code"]
        try:
            px = None
            for attempt in range(2):
                try:
                    px = fdr.DataReader(code, start, end)["Close"].dropna()
                    break
                except Exception:
                    if attempt == 0:
                        time.sleep(0.3)
                        continue
                    raise
            if px is None or len(px) < 60:
                return None
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a = beta_alpha(ret, bench, rf)
            f = fundamentals.get(code, {})
            per, pbr = _num(f.get("PER")), _num(f.get("PBR"))
            eps, bps, dps = _num(f.get("EPS")), _num(f.get("BPS")), _num(f.get("DPS"))
            sec_txt, prod_txt = desc.get(code, ("", ""))
            cap = float(row["Marcap"] or 0) / 1e12
            shr = _num(row.get("Stocks"))
            rec = {
                "t": code, "nk": str(row["Name"]), "ne": str(row["Name"]), "cls": "kr",
                "s": map_sector_kr(sec_txt, prod_txt),
                "price": float(px.iloc[-1]),
                "vol": ann_vol(ret.values), "beta": b, "al": a,
                "per": round(per, 1) if per and per > 0 else None,
                "pbr": round(pbr, 2) if pbr and pbr > 0 else None,
                "dy": round(_num(f.get("DIV")) or 0, 2),
                "eps": round(eps, 0) if eps else None,
                "bps": round(bps, 0) if bps else None,
                "dps": round(dps, 0) if dps else None,
                "cap": round(cap, 3) if cap else None,
                "val": round(float(row["Amount"] or 0) / 1e8, 1),
                "lo": float(px.tail(252).min()), "hi": float(px.tail(252).max()),
            }
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
            bits = []
            if sec_txt:
                bits.append(sec_txt)
            if prod_txt:
                bits.append(f"주요제품: {prod_txt}")
            mk = str(row.get("Market") or "").strip()
            if mk and mk.lower() != "nan":
                bits.append(f"{mk} 상장")
            if cap:
                bits.append(f"시가총액 {cap:,.1f}조원" if cap >= 1 else f"시가총액 {cap * 10000:,.0f}억원")
            if bits:
                rec["dk"] = " · ".join(bits)
            return {k: v for k, v in rec.items() if v is not None}
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, r) for _, r in listing.iterrows()]
        for i, fu in enumerate(as_completed(futs)):
            r = fu.result()
            if r:
                out.append(r)
            if (i + 1) % 250 == 0:
                log(f"  … {i + 1:,}/{len(futs):,} 처리 (성공 {len(out):,})")

    log(f"· 한국 시세 완료: {len(out):,}개")
    out, fin_map = enrich_with_dart(out)
    fill_multiples(out, fin_map)
    return out, fin_map, bench, mkt


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


def fetch_us(start, end, rf):
    import yfinance as yf

    syms = us_tickers()
    log(f"· 미국 {len(syms):,}개 종목…")

    fx = yf.download(FX_TICKER, start=start, end=end, progress=False, auto_adjust=True)["Close"]
    if isinstance(fx, pd.DataFrame):
        fx = fx.iloc[:, 0]
    fx = fx.dropna()
    fx_last = float(fx.iloc[-1])

    spx = yf.download(US_INDEX, start=start, end=end, progress=False, auto_adjust=True)["Close"]
    if isinstance(spx, pd.DataFrame):
        spx = spx.iloc[:, 0]
    bench = spx.pct_change().dropna()
    bench.name = "bench"
    spx_krw = (spx * fx.reindex(spx.index).ffill()).dropna()
    us_vol_krw = ann_vol(spx_krw.pct_change().dropna().values)

    data = yf.download(syms, start=start, end=end, progress=False,
                       auto_adjust=True, group_by="ticker", threads=True)

    out = []
    for s in syms:
        try:
            px = (data[s]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"]).dropna()
            if len(px) < 60:
                continue
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a = beta_alpha(ret, bench, rf)
            krw = (px * fx.reindex(px.index).ffill()).dropna()
            rec = {"t": s, "nk": s, "ne": s, "cls": "us", "ccy": "USD", "fxu": True, "s": "etc",
                   "price": round(float(px.iloc[-1]), 2),
                   "vol": ann_vol(krw.pct_change().dropna().values), "beta": b, "al": a,
                   "lo": round(float(px.tail(252).min()), 2), "hi": round(float(px.tail(252).max()), 2)}
            rec.update(perf_stats(px, rf))
            out.append({k: v for k, v in rec.items() if v is not None})
        except Exception:
            continue

    def enrich(rec):
        try:
            info = yf.Ticker(rec["t"]).get_info()
            nm = info.get("shortName") or info.get("longName")
            if nm:
                rec["nk"] = rec["ne"] = str(nm)
            rec["s"] = map_sector_us(info.get("sector"), info.get("industry"))
            spec = (("per", "trailingPE", 0, 500, False), ("pbr", "priceToBook", 0, 100, False),
                    ("roe", "returnOnEquity", -5, 5, True), ("opm", "operatingMargins", -5, 5, True),
                    ("g3", "revenueGrowth", -5, 20, True), ("debt", "debtToEquity", 0, 2000, False))
            for key, src, lo, hi, scale in spec:
                v = info.get(src)
                if v is None:
                    continue
                v = float(v)
                if not (lo < v < hi):
                    continue
                rec[key] = round(v * 100 if scale else v, 2 if key == "pbr" else 1)
            dyv = info.get("dividendYield")
            if dyv is not None:
                dyv = float(dyv)
                rec["dy"] = round(dyv * (100 if dyv < 1 else 1), 2)
            mc = info.get("marketCap")
            if mc:
                rec["cap"] = round(float(mc) / 1e12, 3)
            av = info.get("averageVolume")
            if av and rec.get("price"):
                rec["val"] = round(float(av) * rec["price"] / 1e8, 1)
            summ = info.get("longBusinessSummary")
            if summ:
                rec["de"] = str(summ)[:400]
        except Exception:
            pass
        return rec

    with ThreadPoolExecutor(max_workers=10) as ex:
        out = list(ex.map(enrich, out))

    log(f"· 미국 완료: {len(out):,}개")
    return out, bench, fx, fx_last, us_vol_krw


# ────────────────────────────────────────────────────────────
def fetch_rf():
    try:
        import FinanceDataReader as fdr
        y = fdr.DataReader(KR_BOND).dropna()
        v = float(y.iloc[-1, 0])
        if 0 < v < 20:
            log(f"· 국고채 10년 {v:.2f}%")
            return v / 100
    except Exception as e:
        log(f"  (국고채 수익률 생략: {e})")
    return RF_FALLBACK


def main():
    end = dt.date.today()
    start = end - dt.timedelta(days=int(365.25 * YEARS) + 40)
    log(f"뱁새 데이터 수집 v16 (TTM) · {start} ~ {end} · DART {'ON' if DART_KEY else 'OFF'}")

    rf = fetch_rf()
    kr, fin_map, kr_bench, kr_mkt = fetch_korea(start, end, rf)
    us, us_bench, fx, fx_last, us_vol_krw = fetch_us(start, end, rf)
    bonds, bd_ret = fetch_bonds(start, end, kr_bench)

    if len(kr) < 300 or len(us) < 100:
        log("!! 받아온 종목이 너무 적습니다. 기존 data.json 을 지키기 위해 중단합니다.")
        sys.exit(1)

    settings = {"rf": round(rf * 100, 2)}
    try:
        import yfinance as yf
        gold = yf.download("GC=F", start=start, end=end, progress=False, auto_adjust=True)["Close"]
        if isinstance(gold, pd.DataFrame):
            gold = gold.iloc[:, 0]
        fxr = fx.pct_change()
        us_krw = us_bench + fxr.reindex(us_bench.index).fillna(0)
        gold_krw = (gold.pct_change() + fxr.reindex(gold.index).fillna(0)).dropna()
        cols = [kr_bench.rename("kr"), us_krw.rename("us"), gold_krw.rename("mt")]
        if bd_ret is not None:
            cols.append(bd_ret.rename("bd"))
        j = pd.concat(cols, axis=1).dropna()
        if len(j) > MIN_DAYS:
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
            log(f"· 시장 가정 계산 완료: {settings}")
    except Exception as e:
        log(f"  (상관계수 생략: {e})")

    stocks = add_percentiles(kr + us) + bonds
    popular = [s["t"] for s in sorted(stocks, key=lambda x: -(x.get("val") or 0))[:120]]

    payload = {
        "asOf": end.isoformat(), "fx": round(fx_last, 1), "settings": settings,
        "popular": popular, "count": {"kr": len(kr), "us": len(us), "bond": len(bonds)}, "stocks": stocks,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    log(f"✓ {OUT} 저장 — {len(stocks):,}종목, {os.path.getsize(OUT) / 1e6:.1f}MB, 환율 {fx_last:,.1f}")

    kr_mkt.update({"fx": round(fx_last, 1), "rf": round(rf * 100, 2)})
    corp = build_corp(kr, fin_map, end.isoformat(), kr_mkt)
    with open(OUT_CORP, "w", encoding="utf-8") as f:
        json.dump(corp, f, ensure_ascii=False, separators=(",", ":"))
    dcf_n = sum(1 for c in corp["companies"] if c["dcfReady"])
    log(f"✓ {OUT_CORP} 저장 — 기업 {len(corp['companies']):,} · 업종 {len(corp['sectors'])} · DCF 자동채움 {dcf_n:,}건 · {os.path.getsize(OUT_CORP) / 1e6:.1f}MB")

    macro = fetch_macro(start, end, fx=fx)
    with open(OUT_MACRO, "w", encoding="utf-8") as f:
        json.dump(macro, f, ensure_ascii=False, separators=(",", ":"))
    log(f"✓ {OUT_MACRO} 저장 — 커브 {'O' if macro.get('curve') else 'X'} · 원자재 {'O' if macro.get('gold') else 'X'}")

    disc = fetch_disclosures(kr, dart_corp_map() if DART_KEY else {}, end)
    with open(OUT_DISC, "w", encoding="utf-8") as f:
        json.dump(disc, f, ensure_ascii=False, separators=(",", ":"))
    log(f"✓ {OUT_DISC} 저장 — 내부자 {len(disc['insider']):,}건 · 국민연금 {len(disc['nps']):,}건")


if __name__ == "__main__":
    main()
