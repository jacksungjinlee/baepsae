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
  v19.1h   dvWhy(배당을 다시 계산한 이유 — DART 결정 공시: st ok · nf · filed · nc-mismatch · nc-unexplained, ok 는 사건 ev) · divCheck.why
  v19.1i   dvProof(오늘 주식 수 기준을 공시와 주식 수로 증명해 되살린 배당의 근거, data.json 만: y0 올해 증명 today · yearEnd · 없음 ·
           yrs 되살린 앞 해 [1 전기 · 2 전전기] · c 현금배당금총액 3년(원) · shr 오늘 상장 주식 수 · yearEnd 는 cmo · cmi 그해 말 보통주 유통 ·
           발행 주식 수, cv 공시된 새 주식(오늘 주식 수로), fx 그 결정들 · ev 올해 배율의 사건 · 우선주 몫 pf 우선주 유통 주식 수 · pd 우선주
           주당 배당) · dvLine(앱이 숨긴 배당수익률 자리에 보여 줄 줄, data.json 만: 1 Jack 의 '주식 수가 바뀐 비율을 공시로 확인하지 못해…' ·
           v19.1j 2 '유상증자로 주가 기준이 바뀌어서…' · 3 '회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서…' ·
           4 '회사 공시에 배당 계산에 필요한 자료가 빠져 있어서…')
           · divCheck.proof(결과마다 수 · 되살리지 않은 이유 line · ratio · basis · rights · uncounted · data · fail 마다 종목 이름)
           · v19.1j divCheck.proofSub(rights · data 로 숨긴 종목마다 그 안의 경우 — rights sh · shnew · unk, data div · pref0 · neg · nototal ·
           prefmix · nopfo · nostk · noshr · other: 줄은 sh → 2 · div → 3 · nototal · nostk · pref0 · nopfo · prefmix → 4 · other(이름을 붙이지
           않은 배당 표 이유)는 줄 없음 · 로그 !! · 관문 경고)

시장 가정(도구의 기본값으로 자동 반영)
  rf 국고채 10년(ECOS, 출처는 settings.rfSrc) · mktVol/usVol/mtVol · rhoKrUs/rhoKrMt/rhoUsMt …

DART_API_KEY 로 OpenDART 재무지표·공시를, ECOS_API_KEY 로 국고채 금리를 받아요.
DART 결과는 .dart-cache/ 에 보관해 실행 사이에 다시 씁니다 (하루 한도 보호).
"""

import collections
import copy
import csv
import decimal
import functools
import gzip
import hashlib
import io
import json
import math
import os
import re
import socket
import sys
import threading
import time
import zipfile
import datetime as dt
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape as html_unescape
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

# v19.1b: 배당 순위·수익률 확인 비율의 관문 기준과 '빠진 이유' 문구는 관문 파일 한곳에 있어요. 파이프라인 로그는 그걸 그대로
# 읽어 관문과 같은 선·같은 말로 알려요 (관문은 이 파일을 읽지 않아요 — 계산은 따로)
from validate_data import DIV_RANK_MISS_FAIL, DYT_COVER_BANDS, floor_1, rank_miss_reason, US_FCUR_KEEP_ZERO_DY
# v19.6a: 환율 이력(fxHist)과 주식 분할(splits)의 기준도 관문 파일에 있어요 (검사 코드는 따로 · 같은 선만 읽어요)
from validate_data import (FX_LO, FX_HI, FX_HIST_FROM, FX_HIST_FIRST_BY, FX_HIST_SOURCES, FX_HIST_ECOS, FX_HIST_GAP_MAX,
                           FX_HIST_JUMP, FX_HIST_REL, SPLITS_FROM, SPLIT_R, SPLIT_SIMPLE_MAX, SPLIT_CLEAN_TOL, MUST_SPLITS)
# 2026-11-14: 국내 시계열의 공식 종가 고정 기준과 하루 가격 제한폭도 관문 파일에 있어요 (관문은 파이프라인의 점검 결과 krSeries 를 봐요)
from validate_data import PIN_PX_TOL, PIN_SHR_TOL, PIN_REF_TOL, KR_DAY_LIMIT, KONEX_DAY_LIMIT, KR_JUMP_WHY
# 2026-11-14: 빈 d1 의 이유 목록도 관문 파일에 있어요 (관문이 같은 목록으로 noTrade · d1Why 를 봐요)
from validate_data import D1_WHY, MUST as GATE_MUST
# 2026-11-19 (Jack 규칙 3): 공식 종가의 두 출처 — 출처 이름 · 야후 접미어 · 1차 출처 표본 (관문 파일에 있어요 · 따로 바뀌지 않게)
from validate_data import PX_SRC_LISTING, PX_SRC_FB, PX_YAHOO_SUFFIX, PX_CHECK_SAMPLE, px_check_sample
# 2026-11-20 (Jack, 2026-11-19 답 5): 코넥스만 야후 .KQ × 네이버 — 출처 이름 · 시장 · 야후 접미어도 관문 파일에서
from validate_data import PX_SRC_KNX, PX_KNX_MARKET, PX_KNX_YAHOO_SUFFIX, KNX_NOYAHOO_WARN, KNX_DIFF_WARN
# 2026-11-14 (Jack, Q2 (a)): 그 움직임이 있는 종목에서 비우는 칸 목록도 관문 파일에 있어요 (관문이 같은 목록으로 비었는지 봐요)
from validate_data import PX_BAD_DATA, PX_BAD_MUST_FAIL, PX_BAD_WIN, PX_BAD_WIN_BARS, PX_BAD_ALWAYS
# 2026-11-14 (Q5 리뷰 S1 · S2): 외국 회사 검사의 '맞춰 볼 값이 없음' 스위치와 그 사유 글, S&P 500 목록을 믿을 최소 겹침도 관문 파일에 있어요
from validate_data import US_FGN_NOCMP, US_FGN_NOCMP_KIND, US_FGN_NOCMP_WHY, US_FGN_NOREC_WHY, US_FGN_NOREC, US_SP500_MIN, US_SP500_MAX
# 2026-11-19 (Jack 의 상시 규칙 · #145 의 네 검사): 빼거나 비울 행을 고르는 함수는 관문 파일에 하나씩 — 파이프라인은 같은 함수를 쓰기 바로 앞의
# 메모리 데이터에 돌려 그 행을 빼거나 비우고, 크게 남기고, 그 파일의 ownDrop 에 적어요 (논리를 베끼지 않아요)
from validate_data import (ISSUE_SHAPE_KEY, ISSUE_BD_KEY, INSIDER_ROLE_KEY, US_DATE_KEY, ISSUE_SHAPE_MAX, ISSUE_BD_MAX, INSIDER_ROLE_MAX,
                           US_DATE_MAX, issue_bad_rows, issue_bd_bad_rows, insider_bad_rows, us_date_bad_rows, own_rows_rec, own_rows_text)
from validate_data import _iso_day as gate_iso_day
# 2026-11-19 (Jack 의 상시 규칙 · 우리 처리를 보는 검사): 빼거나 비울 행을 고르는 함수는 관문 파일에 하나씩 — 파이프라인은 같은 함수를 메모리의
# 데이터에 돌려 그 행을 빼거나 비우고 data.json ownDrop 에 적어요 (논리를 베끼지 않아요)
from validate_data import (US_CLASS_DROP_KEY, US_CLASS_DROP_MAX, DIV_LINE_DROP_KEY, DIV_LINE_BLANK_MAX, US_CLASS_BLIND, us_class_bad_rows,
                           div_line_bad_rows, div_lines_lost, own_drop_rec, own_drop_text, kr_stocks as gate_kr_stocks, us_stocks as gate_us_stocks)
# 2026-11-19 (Jack: "new listings take their industry from DART's company records"): 한국표준산업분류 11차 표를 읽는 코드와 쓰는 단계(소분류)도
# 관문 파일에 있어요 (관문이 같은 표로 채운 값을 확인해요)
from validate_data import load_ksic_names, IND_DART_DIGITS, IND_MISS_KO, IND_MISS_OK, IND_FUND_KSIC, kr_desc_parse, KR_DESC_TAIL
from validate_data import (load_ksic_map_kr, IND_SECTOR_KR, IND_FILL_CHECK, ind_fill_bad, ind_fill_rows, ksic_map_kr_sha,
                           KSIC_LENS_MISFIT)

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
# 2026-11-14 (Jack, 2026-11-13: "Missing US stocks"): S&P 500 · 나스닥 상위 400 밖이라 빠져 있던 회사 28곳. 예탁결제원 SEIBro 의 해외주식 보관
# 순위는 이 실행 환경에서 공개 내려받기로 읽을 수 없어서 (화면이 사이트 내부 호출로만 표를 채워요 · 공개 API 는 키가 필요하고 닿지 않아요) Jack 의
# 대안대로 널리 가진 뉴욕 배당주와 뉴욕 상장 외국 회사로 골랐어요. 고른 이유는 PR 본문의 표 · docs/RUNBOOK.md "US stocks added by hand".
# 새 종목을 넣을 때는 RUNBOOK 의 순서대로 (ETF 여부 · 외국 회사 · 관문의 목록 · 분할 시드).
EXTRA_US_ADDED = [
    "BTI", "ADC", "NNN",                                                  # Jack 이 이름으로 정함
    "MAIN", "WPC", "STAG", "EPR", "OHI", "ENB", "BCE", "TD", "RY",        # 널리 가진 배당주 (O · KO · JNJ · PG · VZ … 는 이미 있어요)
    "SHEL", "BP", "UL", "TM", "SONY", "AZN", "HSBC", "SAP", "NVS",        # 뉴욕 상장 외국 회사 (ADR · 외국 보통주)
    "RIO", "BHP", "TTE", "DEO", "BUD", "SAN", "GSK",
]
EXTRA_US = EXTRA_US + EXTRA_US_ADDED

# v17.5.1: 위 목록 중 ETF·펀드 (나머지 BRK-B·TSM·ASML·BABA·NVO·SHOP 은 실제 회사 주식이에요). 종목마다 직접 정해요.
US_ETFS = frozenset({
    "SPY", "VOO", "QQQ", "SCHD", "VTI", "VT", "IVV", "DIA", "IWM",
    "SOXX", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
    "TLT", "IEF", "SHY", "GLD", "IAU", "SLV", "JEPI", "JEPQ", "VYM",
    "ARKK", "MTUM", "QUAL", "VBR", "IVE", "SPHQ",
})
US_NOT_ETF = frozenset({"BRK-B", "TSM", "ASML", "BABA", "NVO", "SHOP"} | set(EXTRA_US_ADDED))   # 2026-11-14: 더한 28곳은 모두 회사 주식
assert US_ETFS | US_NOT_ETF == set(EXTRA_US) and not (US_ETFS & US_NOT_ETF), "EXTRA_US 의 모든 종목은 ETF 여부가 정해져 있어야 해요"
assert len(EXTRA_US) == len(set(EXTRA_US)), "EXTRA_US 에 같은 티커가 두 번 있어요"
# 2026-11-14: 미국에 상장된 외국 회사 (예탁증서 ADR · 외국 보통주). 야후의 주당 숫자가 회사 합계와 맞는지 따로 봐요 (us_foreign_cuts): ADR 하나가
# 원주 몇 주인지(BP 6주 · HSBC 5주 · 디아지오 4주)를 섞어 계산한 값이 있어요 — 2026-11-14 야후 PBR: BP 7.62 (회사 합계로는 약 1.8) · HSBC 7.07 (약
# 1.6) · 디아지오 93.64 (약 4.9). 재무제표 통화가 달러가 아닌 회사는 #114 가 PER · PBR · 배당수익률을 이미 비워요 (fcur).
# 이 목록은 #126 에서 더한 외국 회사 21곳이에요 (BTI · 캐나다 4곳 · 뉴욕 상장 외국 회사 16곳). 검사 대상은 이제 아래 규칙(us_foreign_set)이
# 찾은 외국 회사 모두이고, 이 21곳은 그 바닥이에요 (Jack 2026-11-14 Q5 — 시험이 이 목록을 그대로 묶어 둬요).
US_FOREIGN = frozenset({"BTI", "ENB", "BCE", "TD", "RY", "SHEL", "BP", "UL", "TM", "SONY", "AZN", "HSBC", "SAP", "NVS", "RIO", "BHP",
                        "TTE", "DEO", "BUD", "SAN", "GSK"})
assert US_FOREIGN <= US_NOT_ETF, "외국 회사 목록(US_FOREIGN)은 EXTRA_US 의 회사 주식이어야 해요"
# 2026-11-14 (Jack, Q5 "넓혀요"): 이 검사는 이제 미국 목록의 외국 회사 모두를 봐요 — 위 21곳만이 아니라 규칙으로 찾아요 (us_foreign_set · 손으로
# 적는 목록이 아니에요). 외국 회사 = ETF · 펀드가 아닌 회사 주식 중
#   ① 재무제표 통화가 달러가 아님 (fcur, #114 — 세 칸은 #114 가 이미 비우고 통화 줄을 붙여요 · 이 검사는 건너뛰어요), 또는
#   ② S&P 500 밖이면서 야후 본사 나라(country)가 미국 밖이거나(US_HOME 밖) 이름이 예탁증서(US_ADR_NAME: ADR · ADS · American Depositary).
# S&P 500 회사는 외국 회사로 보지 않아요: S&P 는 미국 회사만 넣어요 (10-K 를 내는 회사 · 미국 회계 기준 달러 재무제표 · 미국에서 거래되는 그 보통주
# 그대로 — 예탁증서가 아니에요). 세금 때문에 아일랜드 · 스위스 · 영국 · 버뮤다 · 저지에 본사를 둔 미국 회사 (LIN · MDT · ACN · ETN · JCI · STX ·
# CB · TEL · AON …) 의 야후 주당 숫자는 그 보통주 기준이라 ADR 배율이나 통화가 섞이지 않아요 (2026-11-14 야후 값으로 확인: PR 본문 표). 이 회사들을
# 넣으면 이 검사가 맞는 배당수익률을 비워요 (야후 배당 기록이 한 번 빠지면 지난 350일 실제 배당이 모자라요 — 2026-11-14 ACN · JCI · TEL 등 10곳).
# 위 21곳(US_FOREIGN)은 규칙이 모두 찾지만, 야후가 나라를 빼먹은 날에도 빠지지 않게 바닥으로 둬요 (규칙이 못 찾으면 크게 남겨요).
# 야후가 나라를 주지 않은 S&P 500 밖 회사는 외국 회사로 보지 않고 크게 남겨요 (#114 의 '통화 모름'과 같은 뜻 · 관문 경고 · 다음 실행이 다시 물어요).
US_HOME = frozenset({"united states", "united states of america", "usa", "us", "puerto rico"})   # 푸에르토리코: 미국 영토 · 10-K · 달러 (BPOP)
# 야후 짧은 이름은 31자에서 잘려요 ('KANZHUN LIMITED - American D'): 끝에서 잘린 'American Depositary' 의 앞부분도 예탁증서 이름으로 봐요 (리뷰 N4)
# 더 짧게 잘린 ' - Americ' 도 (리뷰 2차 N4) — ' - ' 뒤에서만이라 'Bank of America' 같은 이름은 아니에요.
US_ADR_NAME = re.compile(r"american deposit|american d(?:e(?:p(?:o(?:s(?:i(?:t(?:a(?:r(?:y)?)?)?)?)?)?)?)?)?\s*$"
                         r"|\s-\s+am(?:e(?:r(?:i(?:c(?:a(?:n)?)?)?)?)?)?\s*$|\bADRs?\b|\bADSs?\b", re.I)
# 2026-11-14 (리뷰): 더한 28곳의 이름은 야후 긴 이름(longName)으로 — 짧은 이름은 31자에서 잘리고 'Sponsored' 같은 꼬리가 붙어요 ('British American
# Tobacco  Indus'). 예전부터 있던 종목의 이름은 그대로예요 (짧은 이름).
US_ADDED_LONG_NAME = frozenset(EXTRA_US_ADDED)
# 한국 목록 파일에 섞여 있는 상장 펀드(투자회사). 업종 '신탁업 및 집합투자업'에는 벤처캐피털·신탁회사 같은
# 진짜 회사도 섞여 있어서(2026-11-01 확인: DSC인베스트먼트, 한국토지신탁 등) 업종이 아니라 종목마다 정해요.
KR_LISTED_FUNDS = {"088980": "맥쿼리인프라", "415640": "KB발해인프라", "094800": "맵스리얼티"}
KR_FUND_INDUSTRY = "신탁업 및 집합투자업"     # 이 업종의 새 종목은 로그로 알려요 (목록에 넣을지 사람이 판단)
KR_FUND_KSIC = IND_FUND_KSIC     # 2026-11-19: 같은 업종의 한국표준산업분류 코드 642 (11차 표는 '신탁업 및 집합 투자업' 으로 띄어 써요) — DART 로 채우지 않아요


def is_fund_industry(text):
    """업종 글자(또는 설명 dk)가 '신탁업 및 집합투자업' 으로 시작하는지 — KRX 글자(집합투자업)와 11차 표(집합 투자업) 띄어쓰기 둘 다. (순수 함수)"""
    return (text or "").replace(" ", "").startswith(KR_FUND_INDUSTRY.replace(" ", ""))


KR_INDEX = "KS11"
US_INDEX = "^GSPC"
FX_TICKER = "USDKRW=X"
# v19.6a (docs/tasks/v19.6-records-alerts-dark.md Part I.1): macro.json fxHist = 2016-01-01 부터의 원/달러 일별 환율. 출처 스위치 (Jack 의
# 선택 2026-11-13: "ecos_close" · #117 리뷰 3 의 권고). 기록 날짜 = 사용자가 적은 미국 거래일 D. 미국 D 하루 끝(야후 다음 봉 시가)과의 차이,
# 2016-01 ~ 2026-11 미국 거래일 2,727일 (중앙값 · 99% · 1% 넘는 날) · 아침 06:40 발행에서 어젯밤(D) 기록을 바로 받는 비율:
#   "ecos_close" ECOS 서울 외환시장 15:30 종가 (731Y003 · 0000003), 줄 D = D 의 종가 · 0.25% · 1.44% · 3.5% · 다음 날 아침 94.5%
#   "ecos_next"  ECOS 매매기준율, 줄 D = D 다음에 고시된 값 (= D 하루 서울 거래의 평균) · 0.27% · 1.46% · 5.0% · 다음 날 아침 0%
#                (마지막 고시일엔 아직 줄이 없어 평균 1.59일 더 기다려요 · 금요일 밤 매수는 화요일 아침에야)
#   "ecos"       ECOS 매매기준율, 줄 D = D 에 고시된 값 (전 영업일 서울 거래) · 0.42% · 2.19% · 14.9% · 다음 날 아침 94.7%
#   "yahoo_next" 야후 USDKRW=X, 줄 D = D 다음 봉의 시가 (런던 자정 = 한국 다음 날 08:00~09:00) — 비교 기준 그 자체 · 마지막 줄은 아침
#                발행 때 아직 끝나지 않은 값 (final 거짓) · 야후 일봉의 한 날짜 튐(2021-03-02 · 2022-12-01 · 2024-11-08)이 하루 앞당겨 들어와요
# ECOS 출처는 한국 영업일마다 한 줄이고 끝난 값이에요 (final 참). 15:30 종가는 그날 밤 ECOS 에 올라와요 (다음 날 02:00 KST 쯤엔 있었어요 ·
# 정확한 시각은 몰라요): 아침 실행 때 아직 없으면 이력이 한 영업일 앞에서 끝나고, 관문이 휴장일 표로 보고 경고해요 (앱은 그날 기록을 하루 뒤 받아요).
# 약속 (모든 출처): 줄은 asOf 와 그 전 날짜에만 말해요 — 앱은 asOf 뒤 날짜를 받지 않아요 (오늘만 신선한 data.json fx). 날짜에 줄이 없으면 그 전
# 마지막 줄 (주말 · 한국 휴일). 그 전 줄도 없는 날(ECOS 는 2016-01-01 ~ 03)은 앱이 받지 않아요.
FX_HIST_SOURCE = "ecos_close"
ECOS_FX_ITEMS = {"mbr": ("731Y001", "0000001"),     # 3.1.1.1 주요국 통화의 대원화환율 · 원/미국달러(매매기준율) — 1964 년부터
                 "close": ("731Y003", "0000003")}   # 3.1.1.3 원/달러(종가 15:30) — 1990 년부터 · 2026 년엔 한국 휴일 몇 날에도 줄이 있어요
LONDON = ZoneInfo("Europe/London")  # 야후 USDKRW=X 일봉의 날짜 = 런던 날짜
FX_HIST_TRIES = 2          # 야후 2016년부터 받기: 실패하면 쉬었다가 한 번 더 (ECOS 는 ecos_get 이 세 번)
FX_HIST_PAUSE = 15         # 초
FX_HIST_AGREE = 0.005      # yahoo_next: 2016년부터 받은 종가와 이 실행의 환율(fx)이 겹치는 날 값의 차이 상한 (같은 시계열인지)
FX_HIST_AGREE_MIN = 20     # 겹치는 날이 이만큼은 있어야 해요
FX_HIST_AGREE_SKIP = 5     # 2016년부터 받은 시계열의 마지막 5줄은 비교에서 빼요 (덜 끝난 봉이 바뀌어요)
# 출처를 새로 읽지 못하면 지난 발행본의 이력을 그대로 둬요 (같은 출처 · fxHistFresh 는 그대로 · 며칠이 지나도 — kept_fx_hist).

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
# 2026-11-20 — Jack answered "3. Yes" to this question: "Old app, power-equipment makers. 25 of them (효성중공업, HD현대일렉트릭,
# LS ELECTRIC and others) sit in 전기·가스·환경. They show its line "요금은 정부가 정해요…", which is wrong for them. Move them to 전기전자
# in a small separate PR? (Recommended.)"
# 2.0 이 전력기기·전선(power_eq)으로 묶는 전기장비 제조업 11차 소분류의 업종 글자 (이름 전체 · 띄어쓰기는 빼고 가운뎃점은 · 하나로 맞춰
# 비교해요 · sector_name_key): 281 전동기 · 발전기 및 전기 변환 · 공급 · 제어 장치 · 283 절연선 및 케이블 · 284 전구 및 조명장치 ·
# 289 기타 전기장비 (289 는 이름의 '전기장비' 로 이미 elec 이라 지금은 하는 일이 없지만, 목록을 2.0 의 power_eq 코드와 똑같이 두려고 넣어요 ·
# tests/test_oldapp_power_equip.py 가 그 둘이 같은지 봐요).
# 이 회사들이 utility 키워드에 걸리면 (업종 글자의 '발전기' · 주요제품의 '전력' 같은) utility 가 아니라 elec 이에요 — 2.0 짝
# (validate_data.IND_SECTOR_KR power_eq → elec 만)과 같아요. 주요제품으로 utility 보다 앞 키(반도체 · 2차전지 · 전자 · 기계 …)에 먼저 걸린
# 회사와, 다른 업종 글자의 회사(전기업 · 가스 · 수도 · 폐기물 …)는 그대로예요. 실행마다 옮긴 수와, 2.0 power_eq 인데 utility 로 남은
# 종목을 크게 남겨요 (power_eq_sector_report).
SECTOR_ELEC_NOT_UTILITY = ("전동기,발전기및전기변환·공급·제어장치제조업", "절연선및케이블제조업", "전구및조명장치제조업", "기타전기장비제조업")
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


SECTOR_NAME_DOTS = "·ㆍ・•‧∙･."          # 업종 글자의 가운뎃점 꼴 (U+00B7 · U+318D · U+30FB · U+2022 · U+2027 · U+2219 · U+FF65 · 마침표)


def sector_name_key(text):
    """업종 이름을 비교하는 꼴: 띄어쓰기(보통 · U+00A0 · 전각 U+3000 · 탭)를 빼고 가운뎃점 꼴을 모두 · 하나로 (KRX · 11차 표 · DART 가
    점을 다르게 쓸 수 있어요). (순수 함수)"""
    t = "".join(ch for ch in str(text or "") if ch not in " \u00a0\u3000\t")       # 띄어쓰기 · 줄바꿈 없는 칸 · 전각 칸 · 탭
    return "".join("·" if ch in SECTOR_NAME_DOTS else ch for ch in t)


SECTOR_ELEC_NOT_UTILITY_KEYS = frozenset(sector_name_key(x) for x in SECTOR_ELEC_NOT_UTILITY)


def map_sector_kr_raw(sector_text, product_text=""):
    """키워드 규칙만 (SECTOR_RULES · 위에서부터 처음 걸린 키). 전력기기 · 전선 고침 전의 값 — map_sector_kr 과 로그 · 시험이 써요."""
    blob = f"{sector_text} {product_text}".replace(" ", "")
    for key, words in SECTOR_RULES:
        for w in words:
            if w in blob:
                return key
    return "etc"


def map_sector_kr(sector_text, product_text=""):
    key = map_sector_kr_raw(sector_text, product_text)
    if key == "utility" and sector_name_key(sector_text) in SECTOR_ELEC_NOT_UTILITY_KEYS:
        return "elec"           # 전력기기 · 전선 제조사 (위 SECTOR_ELEC_NOT_UTILITY · Jack 2026-11-20)
    return key


def power_eq_sector_report(stocks):
    """실행마다 남기는 두 목록 (SECTOR_ELEC_NOT_UTILITY · Jack 2026-11-20). (순수 함수)
    moved: 국내 보통주 중 업종 글자(dk)가 그 넷의 이름이고 키워드 규칙만으로는 utility 인데 elec 인 종목 — 이 규칙이 옮긴 종목 [(종목, 이름)]
    stuck: 2.0 그룹이 전력기기·전선(power_eq)인데 예전 뱁새 업종이 utility 인 국내 종목 [(종목, 이름, 업종 글자)] — 있으면 크게 알려요
           (업종 글자가 그 넷의 이름과 다르게 왔는지 · 표가 바뀌었는지 볼 일이에요)."""
    moved, stuck = [], []
    for st in stocks:
        if st.get("cls") != "kr":
            continue
        p = kr_desc_parse(st["dk"]) if isinstance(st.get("dk"), str) and st.get("dk") else None
        words = p[0] if p else ""
        if st.get("ind") == "power_eq" and st.get("s") == "utility":
            stuck.append((st["t"], st.get("nk") or "", words))
        if (not is_preferred(st["t"]) and st.get("s") == "elec" and words
                and sector_name_key(words) in SECTOR_ELEC_NOT_UTILITY_KEYS and map_sector_kr_raw(words, p[1]) == "utility"):
            moved.append((st["t"], st.get("nk") or ""))
    return moved, stuck


def power_eq_sector_lines(moved, stuck):
    """로그 줄 (첫 줄은 늘 · 둘째 줄은 stuck 이 있을 때만 '!!')."""
    names = " · ".join(nk for _, nk in moved[:8]) + (" …" if len(moved) > 8 else "")
    out = [f"· 예전 뱁새 업종: 전력기기 · 전선 제조사 {len(moved):,}종목을 전기·가스·환경(utility) 대신 전자·전기장비(elec)로 "
           f"(SECTOR_ELEC_NOT_UTILITY · 보통주){': ' + names if moved else ''}"]
    if stuck:
        out.append(f"  !! 2.0 업종이 전력기기·전선(power_eq)인데 예전 뱁새 업종이 전기·가스·환경(utility)인 국내 종목 {len(stuck):,}: "
                   + " · ".join(f"{t} {nk} ({w or '업종 글자 없음'})" for t, nk, w in stuck[:10]) + (" …" if len(stuck) > 10 else "")
                   + " — 업종 글자가 SECTOR_ELEC_NOT_UTILITY 의 이름과 다른지 확인")
    return out


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


def _listing_commit_kst(d, sleep=time.sleep):
    """그 날짜 파일의 마지막 커밋 시각(KST). 세 번 시도해도 확인할 수 없으면 None — 2026-11-19 부터 None 은 '최종본 아님'이에요
    (load_kr_listing · kr_recent_sessions · 관문 모두). 그날은 2차 출처(다음 × 야후)가 정해요."""
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    why = None
    for attempt in range(3):
        try:
            r = requests.get(LISTING_COMMITS_API, params={"path": LISTING_PATH.format(d=d.isoformat()), "per_page": 1},
                             headers=headers, timeout=20)
            if r.status_code == 200:
                js = r.json()
                if not js:
                    return None
                ts = js[0]["commit"]["committer"]["date"]
                return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST)
            why = f"HTTP {r.status_code}"
        except Exception as e:
            why = f"{type(e).__name__}: {str(e)[:80]}"
        if attempt < 2:
            sleep(2 * (attempt + 1))
    log(f"  !! 커밋 시각 확인 실패: {d} · {why} (세 번 시도) → 그날 파일은 최종본으로 보지 않아요 (2차 출처가 정해요)")
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


def pick_final_listing(today, fetch_csv, commit_kst, lookback=LISTING_LOOKBACK_DAYS, special=None, unknown_final=True):
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
        # 2026-11-19 (더 엄격하게만): 파이프라인(load_kr_listing)은 unknown_final=False — 커밋 시각을 못 본 파일은 최종본이 아니에요. 캐시가 다음
        # 거래일의 장중 파일을 올리는 지금은 아래 예전 규칙이 장중 파일(11-17 15:29)을 최종본으로 받아들여요. 그날은 2차 출처가 정해요.
        if not unknown_final:
            notes.append(f"!! {d} 커밋 시각 확인 불가 → 최종본으로 보지 않아요 (2차 출처가 정해요)")
            continue
        # 커밋 시각을 못 봤으면: 그 뒤 날짜(오늘 포함)에 시가총액이 찬 파일이 있을 때만 '끝난 날'로 봐요 (예전 규칙 · 파이프라인은 쓰지 않아요)
        later = [today - dt.timedelta(days=b) for b in range(0, back)]
        if any(listing_cap_share(get(e)) >= LISTING_MIN_CAP_SHARE for e in later):
            return d, df, (f"{d} 최종본으로 판단 (!! 커밋 시각 확인 불가 · 다음 거래일 파일 있음, "
                           f"{len(df):,}종목, 시총 {share:.0%})"), notes
        notes.append(f"{d} 커밋 시각 확인 불가 · 다음 거래일 파일도 아직 없음 → 건너뜀")
    return None, None, f"최근 {lookback}일 안에 최종본이 없어요", notes


D1_MAX_KR = KR_DAY_LIMIT  # 한국 하루 가격 제한폭이 ±30% 라 그보다 크면 신규 상장·분할·거래 재개 → 빈 칸 (개수는 로그)
#                            (2026-11-14: 관문 파일의 KR_DAY_LIMIT = D1_MAX_KR 30.0 을 읽어요 — 세 곳이 따로 바뀌지 않게)
D1_LIMIT_EPS = 1e-9      # ±30% 를 볼 때 부동소수점 끝자리만큼 (정확히 ±30% 인 상한가 · 하한가를 남겨요 · 2026-11-14)
VAL20_DAYS = 20           # 평균 거래대금 기간 (거래일)
VAL20_MIN_DAYS = 10       # 이보다 적은 날만 있으면 (신규 상장 등) 비워 둬요


def kr_recent_sessions(px_date, fetch_csv, commit_kst, n=VAL20_DAYS - 1, lookback=45, special=None, known=None):
    """기준일 앞의 끝난 거래일 목록 파일들 (최신 → 과거, 최대 n개). (순수 함수 — 받아오는 방법은 인자로)
    반환: (세션 [(날짜, DataFrame)], 메모들, 직전 거래일 파일이 최종본인지).
    직전 거래일 파일은 커밋 시각이 그날 마감 + 30분(보통 16시 · 수능일 17시) 전이면 최종본이 아니라 그날 종가를 믿지 않아요 (d1 을 비워요).
    special: KRX 특별 거래시간 표 (None 이면 data/krx_special_sessions.csv 를 읽어요).
    known: {날짜: DataFrame} 2차 출처(다음 × 야후 · 마감 + 30분 뒤 · 두 종가가 같은 종목만)로 만든 날 — 캐시 파일 대신 최종본으로 써요 (2026-11-19)."""
    special = load_krx_special_sessions() if special is None else special
    out, notes, prev_final = [], [], None
    for back in range(1, lookback + 1):
        if len(out) >= n:
            break
        d = px_date - dt.timedelta(days=back)
        if known and d in known:
            if prev_final is None:
                prev_final = True
                notes.append(f"직전 거래일 {d}: 2차 출처 (다음 × 야후 · 코넥스는 야후 × 네이버 · 확인된 {len(known[d]):,}종목)")
            out.append((d, known[d]))
            continue
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
        # 2026-11-19 (더 엄격하게만): 커밋 시각을 못 본 파일은 최종본이 아니에요 (예전: 더 뒤 날짜 최종본이 있으면 끝난 날로 봤어요)
        final = ct is not None and ct >= listing_final_cut(d, special)
        when = f"마지막 커밋이 {ct:%m-%d %H:%M} KST" if ct is not None else "커밋 시각을 확인하지 못해"
        if prev_final is None:                      # 기준일 바로 앞의 거래일 (d1 의 전날)
            sp = special_note(d, special)
            if sp:
                notes.append(f"직전 거래일 {sp}")
            prev_final = final
            if not final:
                notes.append(f"!! 직전 거래일 {d} 파일의 {when} — 최종본이 아니라 d1 을 비우고 "
                             "그날 값은 가격 고정·거래대금에 쓰지 않아요")
        elif not final:
            notes.append(f"!! {d} 파일의 {when} — " + ("그날 마감 + 30분 전이라 최종본이 아니에요" if ct is not None else "최종본으로 보지 않아요")
                         + " · 그날 값은 가격 고정·거래대금에 쓰지 않아요")
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


# ────────────────────────────────────────────────────────────
# 2026-11-19: 공식 종가는 늘 두 출처로 (Jack 규칙 3)
# ────────────────────────────────────────────────────────────
# "Permanent two-source rule: official closes always come from two independent sources. If the primary is late or not
#  final, the second one is used automatically after a cross-check. The publish stops only when neither can be confirmed."
#  (Jack, 2026-11-19)
# 사고 (2026-11-18): 자원봉사 캐시(fdr_krx_data_cache)가 11-17 부터 장 마감 뒤 커밋을 하지 않아 최종본이 없었어요 → 발행이 멈췄어요.
# 1차 출처: 그 캐시의 최종본 목록 파일 (예전 그대로). 그 뒤에 이미 끝난 거래일(KOSPI 일봉)이 있으면 그날은 2차 출처:
#   다음(Daum) 일별 시세 — KRX 목록 파일과 같은 칸 (공식 종가 · 전일 대비 · 시가 · 고가 · 저가 · 거래량 · 거래대금(시간외 포함) · 상장주식수)
#   × 야후 .KS/.KQ 일봉 종가 (따로 받는 독립 출처): 두 종가가 원 단위까지 같은 종목만 써요. 한 출처뿐이거나 다르면 그 종목은 빼고
#   이름을 크게 남겨요 (추측하지 않아요 · 필수 종목이 빠지면 관문이 멈춰요).
#   코넥스는 다음에 없어요 (107종목 모두 HTTP 400). 야후에는 {코드}.KQ 로 있어요 (107종목 중 96종목 · 2026-11-19 조사).
# 코스피 · 코스닥: 네이버 일봉 종가는 공식 종가가 아니에요 (시간외 · 넥스트레이드 마지막 체결가 — 11-16: 2,500종목 중 391종목만 같음). 종가 출처로 쓰지 않아요.
# 코넥스만 (2026-11-20 · Jack, 2026-11-19 답 5: "Yes: Naver for KONEX only, always with Yahoo, published only when they agree to the won;
#   daily KONEX checking too."): 코넥스는 시간외 거래가 없어 네이버 일봉 종가 = 공식 종가예요 (최종본 27일 2,881 / 2,881 · 거래 없는 날도).
#   2차 출처 날: 야후 .KQ 일봉 종가 (행의 값) × 네이버 일봉 종가 (확인) 가 원 단위까지 같은 종목만 (kr_knx_confirm) — 다르거나 한쪽뿐이면 빼고
#   이름과 까닭을 크게 남겨요 (거래 없는 날 KRX 가 기준가를 옮기면 야후는 마지막 체결가를 그대로 둬서 달라요 → 빠져요).
#   1차 출처 날: 발행하는 코넥스 종목을 모두 네이버 일봉 종가와 맞춰 봐요 (kr_knx_check · pxSrc.knx.chk · 관문이 경고만 · 빼지 않아요).
# 1차 출처를 쓴 날도 필수 종목 + 표본을 야후 종가와 맞춰 보고 남겨요 (pxSrc.chk · 관문이 경고해요).
KR_FB_DAUM_URL = "https://finance.daum.net/api/quote/A{c}/days"
KR_FB_WORKERS = 4                 # 다음 일별 시세 동시 요청 수 (네이버 시계열은 8 — 더 조심스럽게)
KR_FB_MAX_DAYS = 25               # 다음 · 야후로 만들 수 있는 끝난 거래일 수 상한 (한 번에 받는 날 수)
KR_FB_CHANGE_CODE = {"RISE": 1, "UPPER_LIMIT": 1, "FALL": 2, "LOWER_LIMIT": 2, "EVEN": 3}   # KRX 목록 파일의 ChangeCode (1 상승 · 2 하락 · 3 보합)
KR_FB_COLS = ["Code", "ISU_CD", "Name", "Market", "Dept", "Close", "ChangeCode", "Changes", "ChagesRatio", "Open", "High", "Low",
              "Volume", "Amount", "Marcap", "Stocks", "MarketId"]
KR_FB_CLOSE_TOL = 0.01            # 두 종가 차이 (원) — 부동소수점 끝자리만큼. 같은 호가(원 단위)여야 해요
KR_FB_UNIVERSE_MIN = 1000         # 종목 목록(이름 · 시장)으로 쓸 파일의 최소 행 수
KR_FB_LOUD_COVER = 0.98           # 야후에 있는 종목(코넥스 빼고) 중 이보다 적게 받거나 확인하면 크게 남겨요 (!!)
# 2026-11-20: 종목마다 묻는 세 단계(다음 일별 시세 · 야후 일봉 종가 · 야후 차트 다시 읽기)의 단계마다 시간 한도 (초).
# 사고: 11-19 23:19 · 11-20 00:34 KST 시험 실행 두 번이 이 길에서 61~74분 멈춰 취소됐어요 (같은 입력의 22:59 실행은 3분 40초).
# 요청마다 시간 한도(20초 · 세 번)는 있었지만 단계 전체에는 없어서, 출처가 느려지거나 막으면 몇 시간도 걸릴 수 있었어요
# (예: 다음이 모든 종목에 응답하지 않으면 2,772종목 ÷ 4 × (20초 × 3 + 6초) ≈ 12.7시간).
# 평소 (GitHub 실행 4번, 11-18 03:19 · 06:40 · 11-19 22:59 KST): 다음 108~144초 · 야후 일괄(예전 yfinance) 111~178초 · 차트 다시 읽기 0~41초
# (종목마다 차트 2,764종목도 41초).
# 600초 = 가장 느린 평소 단계(178초)의 3배 넘게 — 조금 느린 밤에는 끊지 않아요.
# 한도가 지나면 새 종목을 묻지 않아요. 묻는 중인 요청은 자기 시간 한도까지: 한 종목 최악 세 번 × (연결 20초 + 읽기 20초) + 쉬는 시간
# 최대 10초 = 130초 (fb_retry_wait · DNS 찾기와 바이트를 아주 천천히 흘리는 서버는 이 한도 밖이에요 — 본 적은 없어요).
# 그래서 단계 하나는 최악 600 + 130초 (약 12분), 세 단계 합 약 37분.
# 묻지 못한 종목은 출처가 답하지 않은 종목과 똑같이 '확인 못 한 종목' → 그날 파일에서 빠져요 (두 출처 규칙 그대로).
# 묻는 순서: 필수 종목 → 1차 출처 최종본의 시가총액 큰 순 → 시가총액을 모르는 종목 (코드 순) — 한도에 걸려도 빠지는 것은 작은 종목부터라,
# 발행하는 상위 MAX_KR 종목은 대개 그대로예요 (fb_order · 리뷰 M1). 한도에 걸린 수는 pxSrc.fb.cut (1차 출처 날은 pxSrc.chk.cut).
# 2026-11-20 (리뷰 S1): 야후 종가는 yfinance 일괄 다운로드 대신 종목마다 차트 (_fetch_yahoo_chart · 같은 v8 chart 응답의 일봉 종가) —
# yfinance 는 묶음 하나를 시간 한도 없이 기다리고 (multi.py while True · 쿠키 잠금), 버린 묶음의 스레드가 프로세스 끝을 막아요.
KR_FB_PHASE_BUDGET_S = 600
KR_INDEX_TIMEOUT = 60             # KOSPI 일봉 (FinanceDataReader KS11 = 캐시 CSV) 소켓 시간 한도 (초) — 그 라이브러리는 시간 한도 없이 받아요


# 2026-11-21 (#161 · 리뷰: 같은 날 다시 도는 실행의 출처 요청 줄이기): 2차 출처 날 마지막 날 두 출처로 확인된 종목의 값 (다음 행 · 야후 종가 ·
# 코넥스는 네이버 행 · 야후 종가) 을 DART 캐시 폴더에 남겨요 (.dart-cache — 'DART 캐시 저장' 단계가 같이 보관해요 · us-info 처럼). 같은 기준일을
# 다시 도는 실행은 발행본(지난 data.json)이 그 날짜 종가로 실은 종목 중 이 보관본의 값이 그 종가와 원 단위까지 같은 종목만 다시 묻지 않아요
# (kr_fb_cache_pick). 나머지 (확인 못 한 · 마지막 확인 종가로 실은 · 빠진 종목) 만 다음 · 야후 · 네이버에 물어요.
KR_FB_CACHE_PATH = os.environ.get("KR_FB_CACHE", ".dart-cache/kr-fb-v1.json")
KR_FB_CACHE_V = 1
# 다음 행에서 남기는 칸 — kr_fb_row 와 그날 상장주식수 (_daumShr) 가 읽는 칸 모두 (시험이 kr_fb_row 결과가 같은지 봐요). 보관본을 작게 해요.
KR_FB_DAUM_KEEP = ("tradePrice", "changePrice", "change", "listedSharesCount", "totalAccTradeVolume", "totalAccTradePrice",
                   "openingPrice", "highPrice", "lowPrice")


def kr_fb_cache_load(path=None):
    """2차 출처 보관본 (kr-fb-v1) 을 읽어요. 없거나 못 읽으면 None (크게 남겨요 · 그러면 모두 물어요)."""
    path = path or KR_FB_CACHE_PATH
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log("· 2차 출처 보관본 없음 → 모두 물어요")
    except Exception as e:
        log(f"  !! 2차 출처 보관본을 읽지 못했어요 ({type(e).__name__}: {str(e)[:120]}) → 모두 물어요")
    return None


def kr_fb_cache_save(keep, path=None):
    """마지막 날 두 출처로 확인된 종목의 값을 보관본에 써요 (write_json — NaN 없이 · 실패해도 발행은 그대로: 크게 남기고 다음 실행이 모두 물어요)."""
    path = path or KR_FB_CACHE_PATH
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        write_json(path, keep)
        log(f"· 2차 출처 보관본 저장: {keep.get('day')} 코스피 · 코스닥 {len(keep.get('kk') or {}):,} · 코넥스 {len(keep.get('knx') or {}):,}종목 ({path})")
    except Exception as e:
        log(f"  !! 2차 출처 보관본 저장 실패 ({type(e).__name__}: {str(e)[:120]}) — 다음 같은 날 실행은 모두 물어요")


def _iso_keys(m):
    out = {}
    for k, v in (m or {}).items() if isinstance(m, dict) else []:
        try:
            out[dt.date.fromisoformat(str(k))] = v
        except ValueError:
            return None
    return out


def kr_fb_cache_pick(cache, prev, day, tol=KR_FB_CLOSE_TOL):
    """같은 날 다시 도는 실행이 다시 묻지 않을 종목 (2026-11-21 · #161 · 순수 함수). 반환: (cached dict 또는 None, 설명).
    모두 맞아야 해요: 보관본의 모양 · 날짜 (cache.day) = 이 실행의 마지막 끝난 거래일 (day) = 발행본(prev)의 pxDate · 발행본이 2차 출처 날.
    종목마다: 발행본이 그 종목을 그 날짜 종가로 실었고 (pxd 없음), 보관본의 그날 다음 종가 (코넥스는 네이버 종가) 와 야후 종가가 그 가격과 원 단위까지
    같아요 (발행된 두 출처 확인 종가). 발행본에 그 날짜 종가로 없는 종목은 보관본을 믿지 않고 다시 물어요 (리뷰: 보관본은 관문 전에 저장돼, 보류 ·
    관문 실패 · 시험 실행의 값일 수 있어요). 그 밖에는 예전처럼 물어요."""
    if not isinstance(cache, dict) or cache.get("v") != KR_FB_CACHE_V:
        return None, "보관본이 없거나 모양이 달라요 → 모두 물어요"
    D = day.isoformat() if isinstance(day, dt.date) else None
    if not isinstance(prev, dict) or prev.get("pxDate") != D or ((prev.get("pxSrc") or {}).get("px") if isinstance(prev.get("pxSrc"), dict) else None) != PX_SRC_FB:
        return None, f"같은 날 다시 도는 실행이 아니에요 (발행본 {(prev or {}).get('pxDate') if isinstance(prev, dict) else None} · 이 실행 {D}) → 모두 물어요"
    if cache.get("day") != D:
        return None, f"보관본 날짜 {cache.get('day')} ≠ {D} → 모두 물어요"
    pst = {}
    for x in prev.get("stocks") or []:
        if isinstance(x, dict) and x.get("cls") == "kr" and not x.get("fund") and x.get("pxd") is None and (_fin(x.get("price")) or 0) > 0:
            pst[str(x.get("t"))] = _fin(x["price"])
    out, same, extra, bad, odd = {"kk": {}, "knx": {}}, 0, 0, 0, 0
    for part, row_key, close_key in (("kk", "d", "tradePrice"), ("knx", "n", "closePrice")):
        for c, v in (cache.get(part) or {}).items() if isinstance(cache.get(part), dict) else []:
            rows, ys = _iso_keys((v or {}).get(row_key)), _iso_keys((v or {}).get("y"))
            r = (rows or {}).get(day)
            a = _fin(r.get(close_key)) if isinstance(r, dict) else None
            y = _fin((ys or {}).get(day))
            if rows is None or ys is None or a is None or y is None or a <= 0 or abs(a - y) > tol:
                odd += 1
                continue
            p = pst.get(str(c))
            if p is None:                           # 리뷰 (#161): 발행본이 그 날짜 종가로 싣지 않은 종목은 보관본을 믿지 않아요 (보류 · 관문 실패 ·
                extra += 1                          # 시험 실행의 값일 수 있어요 — 보관본은 관문 전에 저장돼요) → 다시 물어요
                continue
            if abs(a - p) > tol:
                bad += 1
                continue
            same += 1
            out[part][str(c)] = {row_key: rows, "y": ys}
    n = len(out["kk"]) + len(out["knx"])
    return out, (f"같은 날 다시 도는 실행 ({D}): 발행본이 그 날짜 종가로 실은 종목 중 보관본 값이 그 종가와 같은 {n:,}종목 (코스피 · 코스닥 "
                 f"{len(out['kk']):,} · 코넥스 {len(out['knx']):,}) 은 다시 묻지 않아요 — 발행본에 그 날짜 종가로 없는 보관본 종목 {extra:,}은 다시 물어요"
                 + (f" · 발행본과 다른 {bad:,}종목은 다시 물어요" if bad else "") + (f" · 보관본 값을 읽을 수 없는 {odd:,}종목은 다시 물어요" if odd else ""))


def yahoo_kr_symbol(code, market):
    """다음 × 야후 짝의 야후 심볼: 코스피 .KS · 코스닥 .KQ · 그 밖(코넥스 등)은 None — 다음에 없는 시장이라 이 짝이 될 수 없어요
    (코넥스는 야후에 .KQ 로 있지만 짝은 야후 × 네이버 · yahoo_knx_symbol). (순수 함수)"""
    sfx = PX_YAHOO_SUFFIX.get(str(market or "").strip().upper())
    return f"{code}{sfx}" if sfx else None


def yahoo_knx_symbol(code, market):
    """코넥스의 야후 심볼 {코드}.KQ (2026-11-20 · 코넥스 아닌 시장은 None). (순수 함수)"""
    return f"{code}{PX_KNX_YAHOO_SUFFIX}" if str(market or "").strip().upper() == PX_KNX_MARKET else None


def daum_rows_by_day(js):
    """다음 일별 시세 응답 → {날짜: 행}. 날짜를 읽을 수 없는 행은 빼고, 같은 날짜가 두 번이면 그 날은 통째로 빼요 (어느 쪽인지 몰라요). (순수 함수)"""
    out, dup = {}, set()
    for r in (js or {}).get("data") or []:
        if not isinstance(r, dict):
            continue
        try:
            d = dt.date.fromisoformat(str(r.get("date") or "")[:10])
        except ValueError:
            continue
        if d in out:
            dup.add(d)
        out[d] = r
    for d in dup:
        out.pop(d, None)
    return out


def kr_change_ratio(chg, base):
    """등락률 (%) = 전일 대비 ÷ 기준가 × 100 을 소수 둘째 자리에서 반올림 — 0.5 는 0 에서 먼 쪽 (KRX 목록 파일과 같아요: −0.625 → −0.63 ·
    파이썬 round 는 −0.62 · 2026-11-13 · 11-16 비교에서 12종목). (순수 함수)"""
    q = (decimal.Decimal(int(chg)) * 100 / decimal.Decimal(int(base))).quantize(decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
    return float(q)


def kr_fb_row(u, r):
    """다음의 그날 행(r) → KRX 목록 파일과 같은 칸의 한 행. u: 그날(없으면 가장 가까운 앞 날) 목록 파일의 행 (이름 · 시장 · ISU_CD).
    못 믿을 값이 하나라도 있으면 None (그 종목은 빠져요). (순수 함수)
    거래량은 totalAccTradeVolume · 거래대금은 totalAccTradePrice (시간외 포함 — KRX 목록 파일 최종본과 같은 값 · 2026-11-13 · 11-16 확인).
    거래가 없던 날(거래량 0 · 거래대금 0) 다음은 시가 · 고가 · 저가를 종가로 채우지만 KRX 목록 파일은 0 이라 0 으로 적어요 (거래 없음 표시가 같게).
    전일 대비(Changes)는 다음의 changePrice (거래정지 종목은 prevClosingPrice 가 0 이라 쓰지 않아요) · 기준가 = 종가 − 전일 대비."""
    if not isinstance(r, dict):
        return None
    close, chg, shr = _fin(r.get("tradePrice")), _fin(r.get("changePrice")), _fin(r.get("listedSharesCount"))
    vol, amt = _fin(r.get("totalAccTradeVolume")), _fin(r.get("totalAccTradePrice"))
    op, hi, lo = (_fin(r.get(k)) for k in ("openingPrice", "highPrice", "lowPrice"))
    if close is None or close <= 0 or chg is None or shr is None or shr <= 0 or vol is None or vol < 0 or amt is None or amt < 0:
        return None
    if close != round(close) or chg != round(chg) or shr != round(shr):
        return None
    base = close - chg
    if base <= 0:
        return None
    if vol == 0 and amt == 0:
        op = hi = lo = 0.0
    if op is None or hi is None or lo is None or min(op, hi, lo) < 0:
        return None
    cc = KR_FB_CHANGE_CODE.get(str(r.get("change") or "").strip().upper())
    if cc is None or (cc == 3) != (chg == 0) or (cc == 1 and chg <= 0) or (cc == 2 and chg >= 0):
        return None
    code = str(u.get("Code")).strip()
    return {"Code": code, "ISU_CD": u.get("ISU_CD"), "Name": u.get("Name"), "Market": u.get("Market"), "Dept": u.get("Dept"),
            "Close": int(close), "ChangeCode": cc, "Changes": int(chg), "ChagesRatio": kr_change_ratio(int(chg), int(base)),
            "Open": int(round(op)), "High": int(round(hi)), "Low": int(round(lo)), "Volume": int(round(vol)), "Amount": int(round(amt)),
            "Marcap": int(close) * int(shr), "Stocks": int(shr), "MarketId": u.get("MarketId")}


def kr_fb_confirm(day, universe, daum, yahoo, must=GATE_MUST, tol=KR_FB_CLOSE_TOL):
    """그날(day)의 2차 출처 행: 다음 행 × 야후 종가가 원 단위까지 같은 종목만 (2026-11-19 · 순수 함수).
    universe: 목록 DataFrame (Code · Name · Market …) · daum: {코드: {날짜: 다음 행}} · yahoo: {코드: {날짜: 종가}}.
    반환: (DataFrame — 확인된 종목만 · KR_FB_COLS, 집계 dict):
      n 목록 종목 · conf 확인 · mkt 다음 × 야후 짝이 없는 시장 (코넥스 — 이 짝으로는 묻지 않아요 · 코넥스는 kr_knx_confirm) · noDaum 다음에 그날 행 없음 · bad 다음 행을 믿을 수 없음 ·
      noYahoo 야후에 그날 종가 없음 · diff [(코드, 이름, 다음, 야후)] 두 종가가 다름 · must 확인되지 않은 필수 종목 ·
      shrDiff 목록 파일과 다음의 상장주식수가 다른 종목 (로그만)."""
    rows, st = [], {"n": 0, "conf": 0, "mkt": [], "noDaum": [], "bad": [], "noYahoo": [], "diff": [], "shrDiff": []}
    seen = set()
    for _, u in universe.iterrows():
        code = str(u.get("Code") or "").strip()
        if len(code) != 6 or code in seen:
            continue
        seen.add(code)
        st["n"] += 1
        if not yahoo_kr_symbol(code, u.get("Market")):
            st["mkt"].append(code)                  # 코넥스 등 — 다음에 없는 시장이라 이 짝으로는 묻지 않아요 (코넥스는 야후 × 네이버 · kr_knx_confirm)
            continue
        r = (daum.get(code) or {}).get(day)
        if r is None:
            st["noDaum"].append(code)
            continue
        row = kr_fb_row(u, r)
        if row is None:
            st["bad"].append(code)
            continue
        s0 = _fin(u.get("Stocks"))
        if s0 and s0 > 0 and int(s0) != row["Stocks"]:
            st["shrDiff"].append(code)              # 목록 파일과 다음의 상장주식수가 다름 (확인 여부와 상관없이 · 로그만)
        y = _fin((yahoo.get(code) or {}).get(day))
        if y is None or y <= 0:
            st["noYahoo"].append(code)
            if not yahoo.get(code) and code in getattr(yahoo, "empty", ()):
                st.setdefault("noList", []).append(code)    # 2026-11-21 (#161): 야후가 '자료 없음' 으로 답했어요 (받지 못한 종목은 다시 물어요)
            continue
        if abs(y - row["Close"]) > tol:
            st["diff"].append((code, _txt(u.get("Name")), row["Close"], y))     # 2026-11-20 (검증 리뷰): 빈 이름이 'nan' 글자로 pxSrc 에 가지 않게
            continue
        rows.append(row)
        st["conf"] += 1
    ok = {r["Code"] for r in rows}
    st["must"] = [c for c in must if c not in ok]
    return pd.DataFrame(rows, columns=KR_FB_COLS), st


def kr_fb_one_source(day, st, daum, yahoo):
    """그날 두 출처 중 한 출처만 종가를 준 코스피 · 코스닥 종목 (#161 리뷰 3차 A-S2 · 순수 함수): {코드: (출처, 종가)} — 야후 종가가 없는 종목
    (noYahoo) 은 다음 행의 종가 (tradePrice), 다음 행이 없거나 믿을 수 없는 종목 (noDaum · bad) 은 야후 종가. 확인에는 쓰지 않아요 (한 출처뿐) —
    같은 날 다시 쓰기 (kr_same_day_reuse) 가 지난 발행본의 종가와 다른지 볼 때만 써요. 내부 칸이라 data.json 에 쓰지 않아요 (pxSrc._one · px_src_final 이 빼요)."""
    out = {}
    for c in st.get("noYahoo") or []:
        r = (daum.get(c) or {}).get(day)
        v = _fin(r.get("tradePrice")) if isinstance(r, dict) else None
        if v is not None and v > 0:
            out[str(c)] = ("daum", v)
    for c in list(st.get("noDaum") or []) + list(st.get("bad") or []):
        v = _fin((yahoo.get(c) or {}).get(day))
        if v is not None and v > 0:
            out[str(c)] = ("yahoo", v)
    return out


def kr_fb_final(d, now, special):
    """그날 값을 2차 출처에서 받아도 되는지: 그날 마감 + 30분 (보통 16:00 · 수능일 17:00) 이 지났는지 — 목록 파일 최종본과 같은 기준. (순수 함수)
    야후의 끝나지 않은 날 봉은 장중 값이에요."""
    return now >= listing_final_cut(d, special)


def kr_fb_universe(d, fetch_csv, fallback=None, lookback=LISTING_LOOKBACK_DAYS):
    """그날 종목 목록 (이름 · 시장 · ISU_CD · 상장주식수만 써요 · 가격은 쓰지 않아요): 그날 캐시 파일 (장 전 · 장중 버전도 돼요) →
    그 앞 가장 가까운 날의 캐시 파일 → fallback (1차 출처의 최종본). 반환: (DataFrame, 설명) · 못 찾으면 (None, 이유)."""
    def usable(df):
        return df is not None and {"Code", "Name", "Market"} <= set(df.columns) and len(df) >= KR_FB_UNIVERSE_MIN
    for back in range(0, lookback + 1):
        e = d - dt.timedelta(days=back)
        try:
            df = fetch_csv(e)
        except Exception as ex:
            df = None
            if back == 0:
                log(f"  !! 2차 출처 종목 목록: {e} 캐시 파일 받기 실패 ({ex})")
        if usable(df):
            return df, (f"{e} 캐시 파일 (가격은 쓰지 않아요)" if back == 0 else f"!! {d} 파일이 없어 {e} 캐시 파일의 종목 목록 (그 뒤 새 상장은 빠져요)")
    if usable(fallback):
        return fallback, "!! 캐시 파일이 없어 1차 출처 최종본의 종목 목록 (그 뒤 새 상장은 빠져요)"
    return None, "종목 목록으로 쓸 파일이 없어요"


KR_INDEX_GAP_DAYS = 10            # KOSPI 일봉의 두 날 사이 (또는 시작일 ~ 첫날) 달력 날이 이보다 길면 크게 남겨요 (가장 긴 연휴도 8일 남짓)


def kr_index_note(index, start, px_date, gap_days=KR_INDEX_GAP_DAYS):
    """KOSPI 일봉 (FinanceDataReader KS11) 받은 것 한 줄 (크게?, 글) — 2026-11-20 · 순수 함수 (리뷰 N2).
    그 라이브러리는 받지 못한 해(연도 파일)를 조용히 건너뛰어요 → 마지막 날이 1차 출처 기준일보다 앞이거나, 시작일 ~ 첫날 또는 두 날 사이가
    gap_days 보다 길면 크게 남겨요 (관문이 KOSPI 일봉 · 3년 지수 이력을 따로 확인해요)."""
    ds = sorted({pd.Timestamp(t).date() for t in index})
    if not ds:
        return True, f"KOSPI 일봉 ({KR_INDEX} · FinanceDataReader 캐시): 0일 — 받지 못했어요 (끝난 거래일을 알 수 없어요 · 관문이 따로 확인해요)"
    probs = []
    if px_date is not None and ds[-1] < px_date:
        probs.append(f"마지막 날이 1차 출처 기준일 {px_date} 보다 앞이라 그 뒤 끝난 거래일을 알 수 없어요")
    s0 = pd.Timestamp(start).date() if start is not None else None
    if s0 is not None and (ds[0] - s0).days > gap_days:
        probs.append(f"시작일 {s0} ~ 첫날 {ds[0]} 사이 {(ds[0] - s0).days}일이 비었어요 (한 해 파일을 받지 못했을 수 있어요)")
    gaps = [(a, b) for a, b in zip(ds, ds[1:]) if (b - a).days > gap_days]
    if gaps:
        probs.append("빈 구간 " + ", ".join(f"{a}~{b} ({(b - a).days}일)" for a, b in gaps[:3]) + " (한 해 파일을 받지 못했을 수 있어요)")
    return bool(probs), (f"KOSPI 일봉 ({KR_INDEX} · FinanceDataReader 캐시): {len(ds):,}일 · 마지막 {ds[-1]}"
                         + (" — " + " · ".join(probs) + " (관문이 KOSPI 일봉을 따로 확인해요)" if probs else ""))


def with_socket_timeout(fn, secs):
    """fn() 을 소켓 기본 시간 한도 secs 초로 불러요 (시간 한도 없이 받는 라이브러리용 · 2026-11-20). 끝나면 예전 값으로 돌려놓아요.
    소켓 기본값은 프로세스 전체에 걸려요: 스레드 풀 안이나 다른 스레드가 도는 동안에는 부르지 마세요 (지금은 국내 시세 단계의 첫머리 ·
    다른 스레드가 없을 때 한 번만 불러요)."""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(secs)
    try:
        return fn()
    finally:
        socket.setdefaulttimeout(old)


_DAUM_LOCAL = threading.local()


KR_FB_RETRY_AFTER_MAX = 5         # 429 (너무 많이 물음) 의 Retry-After 를 이만큼(초)까지 따라요 — 한 종목의 쉬는 시간이 길어지지 않게


def fb_retry_wait(attempt, status=None, retry_after=None, tries=3):
    """다시 묻기 전에 쉬는 초 (2026-11-20 · 순수 함수 · 리뷰): 마지막 시도 뒤에는 쉬지 않아요 (None).
    429 는 Retry-After 를 따르되 KR_FB_RETRY_AFTER_MAX 까지 (숫자가 아니면 2 · 4초), 나머지는 1 · 2초."""
    if attempt >= tries - 1:
        return None
    if status == 429:
        try:
            ra = float(retry_after)
        except (TypeError, ValueError):
            ra = None
        return float(min(KR_FB_RETRY_AFTER_MAX, ra if ra is not None and ra >= 0 else 2.0 * (attempt + 1)))
    return 1.0 + attempt


def _fetch_daum_days(code, n):
    """다음 일별 시세 (최근 n 거래일). 세 번 시도해도 못 받으면 예외. 일하는 스레드마다 연결 하나를 다시 써요 (요청마다 새로 잇지 않게)."""
    last = None
    sess = getattr(_DAUM_LOCAL, "s", None)
    if sess is None:
        sess = _DAUM_LOCAL.s = requests.Session()
    for attempt in range(3):
        status = ra = None
        try:
            r = sess.get(KR_FB_DAUM_URL.format(c=code), params={"symbolCode": f"A{code}", "page": 1, "perPage": n, "pagination": "true"},
                             headers={"User-Agent": "Mozilla/5.0", "Referer": f"https://finance.daum.net/quotes/A{code}"}, timeout=20)
            if r.status_code == 200:
                return r.json()
            status, ra = r.status_code, r.headers.get("Retry-After")
            last = f"HTTP {r.status_code}"
            if 400 <= r.status_code < 500 and r.status_code != 429:
                break                                # 없는 종목 등 — 다시 물어도 같아요
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
        wait = fb_retry_wait(attempt, status, ra)
        if wait is None:
            break
        time.sleep(wait)
    raise RuntimeError(last)


def _cap_ok(v):
    v = _fin(v)
    return v is not None and v > 0


def fb_order(codes, first=GATE_MUST, caps=None):
    """묻는 순서 (2026-11-20 · 순수 함수): 필수 종목 먼저 → caps ({코드: 시가총액}) 가 있으면 큰 것부터, 시가총액을 모르는 종목은 그 뒤 코드 순.
    caps 가 없으면 set 은 코드 순, 차례가 있는 것 (list · dict · 생성기) 은 그 차례 그대로 (부르는 쪽이 이미 정한 순서).
    시간 한도에 걸려도 필수 종목과 큰 종목은 이미 물었게 — 한도가 없는 평소에는 같은 종목을 모두 물어서 결과가 같아요.
    caps 는 1차 출처 최종본의 시가총액이에요 (그날 캐시 파일은 장 전 버전이라 시가총액이 빌 수 있어요 — 빈 값으로 줄 세우지 않아요)."""
    seq = sorted(codes) if isinstance(codes, (set, frozenset)) else list(dict.fromkeys(codes))
    have = set(seq)
    head = [c for c in dict.fromkeys(first) if c in have]
    rest = [c for c in seq if c not in set(head)]
    if caps is not None:
        known = sorted((c for c in rest if _cap_ok(caps.get(c))), key=lambda c: (-_fin(caps[c]), c))
        rest = known + sorted(c for c in rest if not _cap_ok(caps.get(c)))
    return head + rest


def kr_fb_caps(listing):
    """1차 출처 최종본의 {코드: 시가총액} — 2차 출처의 묻는 순서에만 써요 (리뷰 M1 · 순수 함수). 시가총액이 비거나 0 이하면 넣지 않아요."""
    if listing is None or not len(listing) or "Marcap" not in listing.columns or "Code" not in listing.columns:
        return {}
    out = {}
    for c, m in zip(listing["Code"].astype(str).str.strip(), pd.to_numeric(listing["Marcap"], errors="coerce")):
        if len(c) == 6 and _cap_ok(m):
            out[c] = float(m)
    return out


def fb_budget(budget_s):
    """단계 시간 한도 (초) — None 이면 지금의 KR_FB_PHASE_BUDGET_S (시험이 모듈 값을 바꿀 수 있게 부를 때 읽어요)."""
    return float(KR_FB_PHASE_BUDGET_S if budget_s is None else budget_s)


def fb_cut_record(cut=None, budget_s=None):
    """pxSrc.fb.cut · pxSrc.chk.cut 모양 (2026-11-20 · 순수 함수): {"s": 단계 시간 한도 초, "daum": n, "yahoo": n, "fill": n} —
    단계마다 시간 한도로 묻지 못한 종목 수 (0 이면 한도에 걸리지 않았어요). 관문과 감시가 봐요 (경고만)."""
    c = cut if isinstance(cut, dict) else {}
    return {"s": int(round(fb_budget(c.get("s", budget_s)))), **{k: int(c.get(k) or 0) for k in ("daum", "yahoo", "fill")}}


def fetch_daum_all(codes, n, fetch=_fetch_daum_days, workers=KR_FB_WORKERS, budget_s=None, clock=time.monotonic, say=log):
    """({코드: {날짜: 다음 행}}, 받지 못한 코드 목록, 시간 한도로 묻지 못한 코드 목록). 필수 종목 먼저 (fb_order).
    2026-11-20: 단계 시간 한도(budget_s · 기본 KR_FB_PHASE_BUDGET_S)가 지나면 새 종목을 묻지 않아요 (묻는 중인 것은 끝까지) — 크게 남겨요."""
    out, failed, cut, lock = {}, [], [], threading.Lock()
    budget = fb_budget(budget_s)
    deadline = clock() + budget

    def one(c):
        if clock() >= deadline:
            with lock:
                if not cut:
                    say(f"  !! 2차 출처 시간 한도 {budget:.0f}초: 다음 일별 시세를 더 묻지 않아요 (받은 {len(out):,} · 못 받음 {len(failed):,} · "
                        f"대상 {len(codes):,}) — 묻지 못한 종목은 확인 못 한 종목이에요")
                cut.append(c)
            return
        try:
            rows = daum_rows_by_day(fetch(c, n))
        except Exception:
            with lock:
                failed.append(c)
            return
        with lock:
            out[c] = rows
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, fb_order(codes)))
    return out, sorted(failed), sorted(cut)


KR_FB_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
KR_FB_YAHOO_CHART_PERIOD = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"
KR_FB_META_WORKERS = 6           # 야후 차트 동시 요청 수 — 시험 실행 44578437586: 2,766종목 31초 ≈ 초당 90번. 429 가 늘면 이 수를 줄여요
KR_META_WINDOW = dt.timedelta(minutes=10)    # regularMarketTime 은 마감 시각 ~ 마감 + 10분 안이어야 해요 (실제: 15:30:01 ~ 15:30:30 · 수능일 16:30)
_YAHOO_LOCAL = threading.local()


def yahoo_chart_close(res, d, close_time):
    """야후 차트 응답(result[0])에서 그날(KST) 종가 (2026-11-19 · 순수 함수 · 관문의 yahoo_day_close 와 같은 규칙, 코드는 따로).
    반환: (값, 'bar' | 'meta') 또는 (None, 까닭). 그날 일봉 종가가 있으면 그것 · 일봉은 있는데 종가가 빈 값이면 meta.regularMarketPrice —
    그 시각(regularMarketTime · KST)이 그날 마감(close_time · 수능일 16:30) ~ 마감 + 10분 안일 때만 (마감 동시호가로 정해진 값 · 시간외 값이 아니게).
    야후는 그날 일봉 종가를 몇 시간 동안 비워 둬요 (11-19 02:15: 005930 11-18 종가 null · regularMarketPrice 194,700 @ 11-18 15:30:16)."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0] or {}
    bars = [c for t, c in zip(ts, q.get("close") or []) if dt.datetime.fromtimestamp(t, KST).date() == d]
    if not bars:
        return None, "그날 일봉 없음"
    c = _fin(bars[-1])
    if c is not None and c > 0:
        return c, "bar"
    meta = res.get("meta") or {}
    p, t = _fin(meta.get("regularMarketPrice")), _fin(meta.get("regularMarketTime"))
    if p is None or p <= 0 or t is None:
        return None, "종가 빈 값 · meta 없음"
    when = dt.datetime.fromtimestamp(t, KST)
    if when.date() != d:
        return None, "meta 시각이 그날이 아님"
    start = dt.datetime.combine(d, close_time, KST)
    if not start <= when < start + KR_META_WINDOW:
        return None, f"meta 시각 {when:%H:%M} 이 마감 {close_time:%H:%M} ~ +{KR_META_WINDOW.seconds // 60}분 밖"
    return p, "meta"


class YahooNotFound(RuntimeError):
    """야후가 그 심볼이 없다고 분명히 답했어요 (HTTP 404 · chart.error.code 'Not Found') — 실패가 아니라 '자료 없음' 답이에요 (#161 리뷰)."""


class YahooAnswers(dict):
    """{코드: {날짜: 종가}} — empty: 야후가 '자료 없음' 으로 분명히 답한 코드 (빈 차트 · Not Found). 받지 못한 (오류 · 시간 초과) 코드는 들어 있지
    않아요 (#161 리뷰: 다시 물어서 바뀔 수 있는 종목과 하루 종일 그대로인 종목을 가려요)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.empty = set()


def _fetch_yahoo_chart(sym, start=None, end=None):
    """야후 차트 응답 result[0] — 최근 5일, 또는 start ≤ 날짜 < end (KST 0시 기준 · 2026-11-20). 세 번 시도해도 못 받으면 예외.
    일하는 스레드마다 연결 하나."""
    sess = getattr(_YAHOO_LOCAL, "s", None)
    if sess is None:
        sess = _YAHOO_LOCAL.s = requests.Session()
    if start is not None and end is not None:
        p1, p2 = (int(dt.datetime.combine(x, dt.time(0), KST).timestamp()) for x in (start, end))
        url = KR_FB_YAHOO_CHART_PERIOD.format(sym=sym, p1=p1, p2=p2)
    else:
        url = KR_FB_YAHOO_CHART.format(sym=sym)
    last = None
    for attempt in range(3):
        status = ra = None
        try:
            r = sess.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if r.status_code == 200:
                return r.json()["chart"]["result"][0]
            status, ra = r.status_code, r.headers.get("Retry-After")
            last = f"HTTP {r.status_code}"
            if r.status_code == 404:
                try:
                    code = (((r.json() or {}).get("chart") or {}).get("error") or {}).get("code")
                except Exception:
                    code = None
                if code == "Not Found":
                    raise YahooNotFound(f"HTTP 404 {code}")
            if 400 <= r.status_code < 500 and r.status_code != 429:
                break
        except YahooNotFound:
            raise                                   # 야후의 '없음' 답은 그대로 (실패로 바꾸지 않아요 · 다시 묻지 않아요)
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
        wait = fb_retry_wait(attempt, status, ra)
        if wait is None:
            break
        time.sleep(wait)
    raise RuntimeError(last)


def yahoo_chart_closes(res, start, end):
    """야후 차트 응답(result[0]) → {날짜(KST): 일봉 종가} · start ≤ 날짜 < end (2026-11-20 · 순수 함수). yfinance 일괄 다운로드의 Close
    (auto_adjust=False) 와 같은 값이에요 (같은 v8 chart 응답의 indicators.quote close). 빈 값 · 0 이하는 빼고, 같은 날짜가 다른 값으로
    두 번이면 그 날은 통째로 빼요 (어느 쪽인지 몰라요). meta(regularMarketPrice)는 쓰지 않아요 — 그것은 yahoo_fill_day 가 규칙대로."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0] or {}
    out, bad = {}, set()
    for t, c in zip(ts, q.get("close") or []):
        v = _fin(c)
        if v is None or v <= 0:
            continue
        d = dt.datetime.fromtimestamp(t, KST).date()
        if not start <= d < end:
            continue
        if d in out and out[d] != v:
            bad.add(d)
        out[d] = v
    for d in bad:
        out.pop(d, None)
    return out


def fetch_yahoo_kr_closes(code_market, start, end, fetch=_fetch_yahoo_chart, workers=KR_FB_META_WORKERS, budget_s=None, clock=time.monotonic,
                          say=log, sym=yahoo_kr_symbol, label="야후 일봉 종가"):
    """({코드: {날짜: 종가}}, 받지 못한 종목 수, 시간 한도로 묻지 못한 종목 수) — 야후 .KS/.KQ 일봉 종가 (수정 안 한 값) · start ≤ 날짜 < end.
    sym (코드, 시장) → 야후 심볼 · None 이면 묻지 않아요 (기본 yahoo_kr_symbol: 코스피 · 코스닥만 · 코넥스는 sym=yahoo_knx_symbol 로 따로 불러요).
    묻는 순서는 code_market 의 차례 (필수 종목 먼저 · fb_order).
    2026-11-20 (리뷰 S1): 종목마다 야후 차트 하나 (예전: yfinance 일괄 다운로드 200종목씩 — 묶음 하나를 시간 한도 없이 기다릴 수 있었어요).
    단계 시간 한도가 지나면 새 종목을 묻지 않아요 (묻는 중인 것은 자기 시간 한도까지 · 요청마다 20초 × 세 번)."""
    order = fb_order(c for c, m in code_market.items() if sym(c, m))
    out, cnt, lock = YahooAnswers(), {"fail": 0, "cut": 0}, threading.Lock()
    budget = fb_budget(budget_s)
    deadline = clock() + budget

    def one(c):
        if clock() >= deadline:
            with lock:
                if not cnt["cut"]:
                    say(f"  !! 2차 출처 시간 한도 {budget:.0f}초: {label}를 더 묻지 않아요 (받은 {len(out):,} · 못 받음 {cnt['fail']:,} · "
                        f"대상 {len(order):,}) — 묻지 못한 종목은 확인 못 한 종목이에요")
                cnt["cut"] += 1
            return
        try:
            closes = yahoo_chart_closes(fetch(sym(c, code_market[c]), start, end), start, end)
        except YahooNotFound:
            with lock:
                cnt["fail"] += 1
                out.empty.add(c)                    # 야후가 '없음' 이라고 답했어요 (다시 물어도 같아요 — 받지 못한 종목과 달라요)
            return
        except Exception:
            with lock:
                cnt["fail"] += 1
            return
        if closes:
            with lock:
                out[c] = closes
        else:
            with lock:
                out.empty.add(c)                    # 잘 된 답인데 그 기간 종가가 없어요
    if order:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, order))
    return out, cnt["fail"], cnt["cut"]


def yahoo_fill_day(yahoo, code_market, d, close_time, fetch=_fetch_yahoo_chart, workers=KR_FB_META_WORKERS, budget_s=None,
                   clock=time.monotonic, say=log, sym=yahoo_kr_symbol, label="야후 차트 다시 읽기"):
    """일봉 종가 받기(fetch_yahoo_kr_closes)에 그날 종가가 없는 종목만 야후 차트(최근 5일 · meta 포함)를 하나씩 다시 읽어 yahoo 에 채워요 (2026-11-19). 반환: 집계 dict
    {need, bar, meta, none, fail, cut, metaCodes} — meta 는 일봉 종가가 비어 마감 뒤 regularMarketPrice 로 읽은 종목.
    2026-11-20: 필수 종목 먼저 (fb_order) · 단계 시간 한도가 지나면 새 종목을 묻지 않아요 (cut · 그 종목은 그날 야후 종가 없음 = 확인 못 함)."""
    need = fb_order(c for c, m in code_market.items() if sym(c, m) and d not in (yahoo.get(c) or {}))
    out = {"need": len(need), "bar": 0, "meta": 0, "none": 0, "fail": 0, "cut": 0, "metaCodes": set()}
    lock = threading.Lock()
    budget = fb_budget(budget_s)
    deadline = clock() + budget

    def one(c):
        if clock() >= deadline:
            with lock:
                if not out["cut"]:
                    say(f"  !! 2차 출처 시간 한도 {budget:.0f}초: {label}를 더 하지 않아요 (읽은 {out['bar'] + out['meta']:,} · "
                        f"대상 {len(need):,}) — 묻지 못한 종목은 확인 못 한 종목이에요")
                out["cut"] += 1
            return
        try:
            v, how = yahoo_chart_close(fetch(sym(c, code_market[c])), d, close_time)
        except Exception:
            with lock:
                out["fail"] += 1
            return
        with lock:
            if v is None:
                out["none"] += 1
                return
            yahoo.setdefault(c, {})[d] = v
            out[how] += 1
            if how == "meta":
                out["metaCodes"].add(c)
    if need:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, need))
    return out


# ────────────────────────────────────────────────────────────
# 2026-11-20: 코넥스의 두 출처 — 야후 .KQ × 네이버 (Jack, 2026-11-19 답 5 그대로:
#   "Yes: Naver for KONEX only, always with Yahoo, published only when they agree to the won; daily KONEX checking too.")
# ────────────────────────────────────────────────────────────
# 다음에는 코넥스가 없어서 (107종목 모두 HTTP 400) 2차 출처 날에는 코넥스 107종목이 모두 빠졌어요. 1차 출처 날에도 코넥스 종가는 확인하지 않았어요
# (kr_primary_check 의 표본은 코스피 · 코스닥만).
# - 야후 .KQ 일봉: 107종목 중 96종목 (KOSDAQ · MUTUALFUND 로 잘못 적혀 있고 meta 시각은 2024-07 에 멈춰 있지만 일봉은 맞아요 — 거래가 있던 날
#   1,988 / 1,988). 거래 없는 날 KRX 가 기준가를 옮기면 야후는 마지막 체결가를 그대로 둬요 (거래 없는 날 496 / 627) → 네이버와 달라 빠져요.
# - 네이버 일봉 (api.stock.naver.com — 금 시세와 같은 곳): 코넥스는 시간외 거래가 없어 (2026-09-14 시간외 시장에 코넥스는 빠짐 · 넥스트레이드도
#   코넥스를 거래하지 않아요) 일봉 종가 = 공식 종가예요: 최종본 27일 (09-15 ~ 11-16) 2,881 / 2,881 (거래 없는 날도). 코스피 · 코스닥은 186 / 1,276 뿐
#   (시간외 체결가) — 그래서 코스피 · 코스닥에는 쓰지 않아요.
# - 2차 출처 날: 두 종가가 원 단위까지 같은 코넥스 종목만 확인 (kr_knx_confirm) — 2026-11-02 ~ 11-16 최종본 11일에서 둘 다 있던 1,056행 중
#   995행이 같았고 그 995행 모두 공식 종가와 같았어요 (다른 61행은 모두 거래 없는 날). 묻는 순서 · 단계 시간 한도 · 크게 남기기는 다음 × 야후와 같아요.
#   그날 파일에는 평소 날 발행하는 코넥스만 넣어요 (리뷰 M1: 1차 출처 최종본 MAX_KR 번째 시가총액 이상 · kr_knx_cap_floor) — '국내 종목 수' 바닥이
#   평소와 같게 (확인된 코넥스 90여 종목이 코스피 · 코스닥의 빈자리를 채워 바닥이 늦게 걸리지 않게).
#   기준일 맞춰 보기 (검증 리뷰 M1): 네이버 일봉을 1차 출처 최종본 날짜(px0)부터 받아, 네이버의 px0 종가가 그 최종본의 공식 종가와 같은 코넥스만
#   확인해요 (kr_knx_anchor · kr_knx_confirm anchor). 야후 종가는 분할 수정 값이고 네이버 일봉도 수정주가일 수 있어, px0 뒤 권리락 · 분할 · 병합이
#   있으면 두 출처가 그날 종가 ÷ 비율로 같아질 수 있어요 — 그런 종목은 빠지고 크게 남아요 (pxSrc.fb.knx.adj · noAnchor · 관문이 경고해요).
# - 1차 출처 날: 발행하는 코넥스 종목의 최종본 종가를 모두 네이버 일봉 종가와 맞춰 봐요 (kr_knx_check · 경고만 · 빼지 않아요).
KR_KNX_NAVER_URL = "https://api.stock.naver.com/chart/domestic/item/{c}/day"
KR_KNX_WORKERS = 4                # 네이버 일봉 동시 요청 수 (다음과 같게 — 조심스럽게)
KR_KNX_CHK_BUDGET_S = 120         # 1차 출처 날 코넥스 네이버 확인의 시간 한도 (초) — 평소 30종목 남짓 · 몇 초. 걸려도 확인만 줄어요 (가격은 최종본 그대로)
_NAVER_LOCAL = threading.local()


def naver_rows_by_day(js):
    """네이버 일봉 응답 (목록 · localDate 'YYYYMMDD') → {날짜: 행}. 날짜를 읽을 수 없는 행은 빼고, 같은 날짜가 두 번이면 그 날은 통째로 빼요
    (어느 쪽인지 몰라요). 목록이 아니면 빈 dict. (순수 함수)"""
    out, dup = {}, set()
    for r in js if isinstance(js, list) else []:
        if not isinstance(r, dict):
            continue
        try:
            d = dt.datetime.strptime(str(r.get("localDate") or ""), "%Y%m%d").date()
        except ValueError:
            continue
        if d in out:
            dup.add(d)
        out[d] = r
    for d in dup:
        out.pop(d, None)
    return out


def _fetch_naver_days(code, start, end):
    """네이버 일봉 (start ~ end 의 거래일 · KST 날짜). 세 번 시도해도 못 받으면 예외 (요청마다 20초 · 다음 · 야후와 같은 쉬는 시간).
    일하는 스레드마다 연결 하나. 없는 코드는 빈 목록 (200 · [])."""
    sess = getattr(_NAVER_LOCAL, "s", None)
    if sess is None:
        sess = _NAVER_LOCAL.s = requests.Session()
    last = None
    for attempt in range(3):
        status = ra = None
        try:
            r = sess.get(KR_KNX_NAVER_URL.format(c=code), params={"startDateTime": f"{start:%Y%m%d}0000", "endDateTime": f"{end:%Y%m%d}2359"},
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if r.status_code == 200:
                return r.json()
            status, ra = r.status_code, r.headers.get("Retry-After")
            last = f"HTTP {r.status_code}"
            if 400 <= r.status_code < 500 and r.status_code != 429:
                break
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
        wait = fb_retry_wait(attempt, status, ra)
        if wait is None:
            break
        time.sleep(wait)
    raise RuntimeError(last)


def fetch_naver_all(codes, start, end, fetch=_fetch_naver_days, workers=KR_KNX_WORKERS, budget_s=None, clock=time.monotonic, say=log,
                    label="코넥스 네이버 일봉"):
    """({코드: {날짜: 네이버 행}}, 받지 못한 코드 목록, 시간 한도로 묻지 못한 코드 목록) — 코넥스만 부르세요 (2026-11-20).
    묻는 순서는 codes 의 차례 (fb_order). 단계 시간 한도(budget_s · 기본 KR_FB_PHASE_BUDGET_S)가 지나면 새 종목을 묻지 않아요
    (묻는 중인 것은 자기 시간 한도까지) — 크게 남겨요 (fetch_daum_all 과 같은 모양)."""
    out, failed, cut, lock = {}, [], [], threading.Lock()
    order = fb_order(codes)
    budget = fb_budget(budget_s)
    deadline = clock() + budget

    def one(c):
        if clock() >= deadline:
            with lock:
                if not cut:
                    say(f"  !! 2차 출처 시간 한도 {budget:.0f}초: {label}을 더 묻지 않아요 (받은 {len(out):,} · 못 받음 {len(failed):,} · "
                        f"대상 {len(order):,}) — 묻지 못한 종목은 확인 못 한 종목이에요")
                cut.append(c)
            return
        try:
            rows = naver_rows_by_day(fetch(c, start, end))
        except Exception:
            with lock:
                failed.append(c)
            return
        with lock:
            out[c] = rows
    if order:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(one, order))
    return out, sorted(failed), sorted(cut)


def kr_knx_row(u, n, close):
    """코넥스 한 종목의 그날 행 — KRX 목록 파일과 같은 칸 (2026-11-20 · 순수 함수). u: 그날 목록 파일의 행 (이름 · 시장 · ISU_CD · 상장주식수),
    n: 네이버의 그날 행, close: 두 출처가 원 단위까지 같다고 확인된 종가 (원 · 정수). 못 믿을 값이 하나라도 있으면 None (그 종목은 빠져요).
    - 종가: close (야후 .KQ 값 · 네이버와 같아요) · 상장주식수: 목록 파일 (다음이 없어 따로 맞춰 볼 출처는 없어요 · 공식 종가 = 시가총액 ÷ 주식 수는
      주식 수와 상관없이 close 예요) · 시가총액 = 종가 × 주식 수.
    - 거래량 · 시가 · 고가 · 저가: 네이버 (코넥스는 KRX 와 같아요 — 최종본 11일 995 / 995). 거래가 없던 날 (거래량 0) 네이버는 시가 · 고가 · 저가를
      종가로 채우지만 KRX 목록 파일은 0 이라 0 으로, 거래대금도 0 (거래가 없으면 거래대금은 정확히 0) — 거래 없음 표시가 목록 파일과 같게.
    - 거래대금: 거래가 있던 날은 빈 값 (야후 · 네이버 일봉에 거래대금이 없어요 · 추측하지 않아요 → 그날 val 은 빈 칸, val20 은 거래대금이 있는 날로).
    - 전일 대비 · 등락 부호 · 등락률: 빈 값 — 코넥스는 거래가 없어도 KRX 가 기준가를 옮겨요 (EMB 11-18: 앞 종가 2,600 · 기준가 2,700). 두 출처 모두
      기준가를 주지 않아서 추측하지 않아요 (기준가 연결은 '확인 못 함' · 그 종목 봉은 주식 수와 값 차이로만 고쳐요 · d1 은 공식 종가끼리라 그대로)."""
    if not isinstance(n, dict):
        return None
    c_n, vol = _fin(n.get("closePrice")), _fin(n.get("accumulatedTradingVolume"))
    op, hi, lo = (_fin(n.get(k)) for k in ("openPrice", "highPrice", "lowPrice"))
    shr = _fin(u.get("Stocks"))
    if close is None or close <= 0 or close != round(close) or c_n is None or c_n != close:
        return None
    if vol is None or vol < 0 or vol != round(vol) or shr is None or shr <= 0 or shr != round(shr):
        return None
    if vol == 0:
        op = hi = lo = amt = 0.0
    else:
        if op is None or hi is None or lo is None or min(op, hi, lo) <= 0:
            return None
        amt = float("nan")
    code = str(u.get("Code")).strip()
    return {"Code": code, "ISU_CD": u.get("ISU_CD"), "Name": u.get("Name"), "Market": u.get("Market"), "Dept": u.get("Dept"),
            "Close": int(close), "ChangeCode": float("nan"), "Changes": float("nan"), "ChagesRatio": float("nan"),
            "Open": int(round(op)), "High": int(round(hi)), "Low": int(round(lo)), "Volume": int(round(vol)), "Amount": amt,
            "Marcap": int(close) * int(shr), "Stocks": int(shr), "MarketId": u.get("MarketId")}


def kr_knx_anchor(listing, px_date):
    """기준일 맞춰 보기의 기준 (리뷰 M1 · 2026-11-20 · 순수 함수): (1차 출처 최종본 날짜, {코넥스 코드: 그날 공식 종가 = 시가총액 ÷ 상장주식수}).
    목록이나 날짜가 없으면 (None, {}) — 그러면 코넥스는 한 종목도 확인되지 않아요 (kr_knx_confirm 'noAnchor' · 더 엄격하게)."""
    if px_date is None or listing is None or not len(listing) or not {"Code", "Market"} <= set(listing.columns):
        return None, {}
    out = {}
    for _, r in listing.iterrows():
        c = str(r.get("Code") or "").strip()
        if len(c) == 6 and yahoo_knx_symbol(c, r.get("Market")):
            v = kr_official_close(r)
            if v is not None and v > 0:
                out[c] = v
    return px_date, out


def kr_knx_confirm(day, universe, yahoo, naver, tol=KR_FB_CLOSE_TOL, anchor=None):
    """그날(day)의 코넥스 2차 출처 행: 야후 .KQ 일봉 종가 (행의 값) × 네이버 일봉 종가 (확인) 가 원 단위까지 같은 종목만 (2026-11-20 · 순수 함수).
    universe: 목록 DataFrame — 시장이 코넥스인 행만 봐요 · yahoo: {코드: {날짜: 종가}} · naver: {코드: {날짜: 네이버 행}}.
    anchor (리뷰 M1 · kr_knx_anchor): (px0, {코드: px0 공식 종가}) — px0 = 1차 출처 최종본 날짜. 주면 네이버의 px0 종가가 그 최종본의 공식 종가와
      원 단위까지 같은 종목만 확인해요. 까닭: 야후 종가는 분할 수정 값이고 (무상증자도 분할로 적어요) 네이버 일봉도 다른 곳에서는 수정주가예요.
      px0 뒤에 권리락 · 분할 · 병합이 있으면 두 출처가 모두 그날 종가 ÷ 비율로 같아질 수 있어요 (그날 공식 종가가 아니에요 — 시가총액 · d1 이 틀려요).
      수정주가는 권리락 앞의 모든 봉을 고치니까, 네이버의 px0 봉이 공식 종가 그대로면 그 뒤 날(day)의 봉도 고쳐지지 않았어요.
      야후의 px0 봉은 보지 않아요: 쓰는 값은 네이버의 그날 값과 원 단위까지 같아야 하고, 그 네이버 값은 위 맞춰 보기로 수정되지 않은 값이에요 —
      야후가 수정했든 아니든 결과는 같아요 (야후만 수정했으면 두 값이 달라 빠져요). 그리고 px0 에 거래 없이 KRX 가 기준가를 옮긴 종목은 야후의
      px0 봉이 마지막 체결가라 (하루 3 ~ 9종목) 그것까지 요구하면 맞는 종목이 더 빠져요.
      None 이면 맞춰 보지 않아요 (시험만 · kr_fallback_days 가 크게 남겨요 · 파이프라인은 늘 줘요).
    반환: (DataFrame — 확인된 코넥스 종목만 · KR_FB_COLS, 집계 dict):
      n 목록의 코넥스 종목 · conf 확인 · noNaver 네이버에 그날 행 없음 · bad 네이버 행 · 목록 행을 믿을 수 없음 · noYahoo 야후에 그날 종가 없음 ·
      diff [(코드, 이름, 네이버, 야후)] 두 종가가 다름 (거래 없는 날 KRX 가 기준가를 옮기면 야후는 마지막 체결가 그대로예요) ·
      adj [(코드, 이름, px0 공식 종가, 네이버 px0 종가)] 두 출처는 같지만 네이버의 px0 종가가 최종본과 달라요 (그 뒤 값이 수정됐을 수 있어요) ·
      noAnchor 두 출처는 같지만 px0 공식 종가나 네이버 px0 행이 없어 맞춰 보지 못함 · anchor px0 · names {코드: 이름}.
    adj · noAnchor 는 두 출처가 같은 종목만 세요 (그 밖의 까닭으로 빠지는 종목은 예전 칸 그대로)."""
    rows, st = [], {"n": 0, "conf": 0, "noNaver": [], "bad": [], "noYahoo": [], "diff": [], "adj": [], "noAnchor": [], "names": {},
                    "anchor": anchor[0] if anchor is not None else None}
    p0, offs = anchor if anchor is not None else (None, {})
    seen = set()
    for _, u in universe.iterrows():
        code = str(u.get("Code") or "").strip()
        if len(code) != 6 or code in seen or not yahoo_knx_symbol(code, u.get("Market")):
            continue
        seen.add(code)
        st["n"] += 1
        st["names"][code] = _txt(u.get("Name"))     # 빈 이름 (NaN) 이 'nan' 글자로 pxSrc.fb.knx.diffEx 에 가지 않게 (관문 글자 검사 · 검증 리뷰)
        nr = (naver.get(code) or {}).get(day)
        if nr is None:
            st["noNaver"].append(code)
            continue
        nc = _fin(nr.get("closePrice")) if isinstance(nr, dict) else None
        if nc is None or nc <= 0 or nc != round(nc):
            st["bad"].append(code)
            continue
        y = _fin((yahoo.get(code) or {}).get(day))
        if y is None or y <= 0:
            st["noYahoo"].append(code)
            if not yahoo.get(code) and code in getattr(yahoo, "empty", ()):
                st.setdefault("noList", []).append(code)    # 2026-11-21 (#161): 야후가 싣지 않는 코넥스 ('자료 없음' 답 · 늘 11종목 남짓)
            continue
        if abs(y - nc) > tol:
            st["diff"].append((code, st["names"][code], nc, y))
            continue
        if anchor is not None:                       # 리뷰 M1: 네이버의 px0 종가 = 1차 출처 최종본의 px0 공식 종가 (그 뒤 값이 수정되지 않았어요)
            off0 = _fin((offs or {}).get(code)) if p0 is not None else None
            n0 = (naver.get(code) or {}).get(p0) if p0 is not None else None
            n0c = _fin(n0.get("closePrice")) if isinstance(n0, dict) else None
            if off0 is None or off0 <= 0 or n0c is None or n0c <= 0:
                st["noAnchor"].append(code)
                continue
            if abs(n0c - off0) > tol:
                st["adj"].append((code, st["names"][code], off0, n0c))
                continue
        row = kr_knx_row(u, nr, float(round(y)))     # 행의 값은 야후 (원 단위로 · 네이버와 같아요)
        if row is None:
            st["bad"].append(code)
            continue
        rows.append(row)
        st["conf"] += 1
    return pd.DataFrame(rows, columns=KR_FB_COLS), st


def kr_knx_cap_floor(caps, n=None):
    """평소 날 발행하는 국내 종목의 시가총액 문턱 (2026-11-20 · 리뷰 M1 · 순수 함수): 1차 출처 최종본 {코드: 시가총액} 의 n번째 (기본 MAX_KR)
    로 큰 값 (원). 평소 날은 select_kr_universe 가 시가총액 상위 MAX_KR 을 내요 — 이 값 이상인 코넥스가 평소 날 발행하는 코넥스예요.
    시가총액을 아는 종목이 n 보다 적으면 None (문턱을 몰라요 → 코넥스를 더하지 않아요 · 더 엄격하게)."""
    n = MAX_KR if n is None else n
    vals = sorted((float(_fin(v)) for v in (caps or {}).values() if _cap_ok(v)), reverse=True)
    return vals[n - 1] if n > 0 and len(vals) >= n else None


def kr_knx_cap_keep(kfr, floor):
    """확인된 코넥스 행 중 그날 파일에 넣을 행 — 시가총액(종가 × 주식 수)이 floor 이상 (리뷰 M1 · 순수 함수). floor 가 None 이면 하나도 넣지 않아요.
    반환: (DataFrame, [시가총액 기준 아래라 뺀 코드 — 시가총액 큰 순])."""
    if kfr is None or not len(kfr):
        return kfr, []
    cap = pd.to_numeric(kfr["Marcap"], errors="coerce")
    keep = cap >= floor if floor is not None else pd.Series(False, index=kfr.index)
    out = kfr[keep.fillna(False)].reset_index(drop=True)
    low = kfr[~keep.fillna(False)].assign(_c=cap).sort_values(["_c", "Code"], ascending=[False, True])
    return out, [str(c) for c in low["Code"]]


def kr_knx_note(d, kst, names=None):
    """코넥스 2차 출처 한 줄 (크게 남길지, 글) — 빠진 종목을 모두 이름과 까닭으로 (코넥스는 많아야 100여 종목). 크게 (!!) 는 예상하지 못한 때만
    (아래 unusual · 관문 줄과 같은 기준). (2026-11-20 · 순수 함수)"""
    nm = dict(kst.get("names") or {})
    nm.update({k: _txt(v) for k, v in (names or {}).items() if _txt(v)})

    def ex(codes):
        return ", ".join(f"{c} {nm.get(c, '')}".strip() for c in codes)
    adj, no_anc = list(kst.get("adj") or []), list(kst.get("noAnchor") or [])
    left = len(kst["noNaver"]) + len(kst["bad"]) + len(kst["noYahoo"]) + len(kst["diff"]) + len(adj) + len(no_anc)
    cut = kst.get("cut") or {}
    hit = sum(int(cut.get(k) or 0) for k in ("yahoo", "fill", "naver"))
    p0 = kst.get("anchor")
    txt = (f"{d} 코넥스 2차 출처(야후 .KQ × 네이버 종가 원 단위까지 같음"
           + (f" · 네이버의 {p0} 종가 = 그날 최종본 공식 종가" if p0 else "") + f"): 확인 {kst['conf']:,} / {kst['n']:,}종목"
           + (f" (그중 야후 값이 마감 뒤 regularMarketPrice {kst['yMeta']:,})" if kst.get("yMeta") else "")
           + f" · 빠짐 {left:,} (네이버 행 없음 {len(kst['noNaver']):,} · 값 못 믿음 {len(kst['bad']):,} · 야후 종가 없음 {len(kst['noYahoo']):,} · "
           f"두 종가가 다름 {len(kst['diff']):,}"
           + (f" · 기준일 종가가 최종본과 다름 {len(adj):,} · 기준일 종가로 맞춰 보지 못함 {len(no_anc):,}" if "adj" in kst else "")
           + ") — 빠진 종목은 그날 파일에 없어요")
    cap_out = list(kst.get("capOut") or [])
    if "kept" in kst:
        fl = kst.get("floor")
        txt += (f" — 그날 파일에 넣은 코넥스 {kst['kept']:,} (평소 날처럼 시가총액 상위 {MAX_KR:,} 안만: "
                + (f"{fl / 1e8:,.0f}억원 이상)" if fl is not None else "기준을 정할 수 없어 넣지 않았어요)")
                + (f" · 확인됐지만 시가총액 기준 아래라 뺀 {len(cap_out):,}: {ex(cap_out[:12])}" + (" …" if len(cap_out) > 12 else "") if cap_out else ""))
    if kst["diff"]:
        txt += " — 다름 (거래 없는 날 기준가가 바뀌면 야후는 마지막 체결가 그대로예요): " + ", ".join(
            f"{c} {n} 네이버 {a:,.0f} · 야후 {b:,.2f}" for c, n, a, b in kst["diff"])
    if kst["noYahoo"]:
        txt += f" — 야후 종가 없음: {ex(kst['noYahoo'])}"
    if kst["noNaver"]:
        txt += f" — 네이버 행 없음: {ex(kst['noNaver'])}"
    if kst["bad"]:
        txt += f" — 값 못 믿음: {ex(kst['bad'])}"
    if adj:
        txt += (f" — !! 기준일 {p0} 종가가 최종본과 다름 (두 출처는 같지만 {p0} 뒤 권리락 · 분할 · 병합 · 무상증자로 값이 수정됐을 수 있어 넣지 않았어요): "
                + ", ".join(f"{c} {n} 최종본 {a:,.0f} · 네이버 {b:,.0f}" for c, n, a, b in adj))
    if no_anc:
        txt += f" — !! 기준일 {p0} 종가로 맞춰 보지 못함 (최종본 공식 종가나 네이버 {p0} 행이 없어요 · 넣지 않았어요): {ex(no_anc)}"
    if hit:
        txt += (f" — !! 시간 한도 {int(cut.get('s') or 0)}초로 묻지 못한 종목 (야후 일봉 {int(cut.get('yahoo') or 0):,} · 야후 다시 읽기 "
                f"{int(cut.get('fill') or 0):,} · 네이버 {int(cut.get('naver') or 0):,}) 이 위 '야후 종가 없음' · '네이버 행 없음' 에 들어 있어요")
    # 크게 (!!) 는 예상하지 못한 때만 (검증 리뷰): 네이버 행 없음 · 값 못 믿음 · 야후 없음이 평소보다 많음 · 다름이 평소보다 많음 · 확인이 절반 아래 ·
    # 시간 한도 · 시가총액 기준을 모름 (관문 '코넥스 종가 두 출처' 줄과 같은 기준). 평소의 빠짐 (야후에 없는 11종목 · 거래 없는 날 다름 3 ~ 9 ·
    # 시가총액 기준 아래) 은 이름과 까닭을 그대로 적고 '·' 줄로 남겨요.
    # 리뷰 M1 (2026-11-20): 기준일 종가가 다르거나 맞춰 보지 못한 종목 (두 출처는 같았는데 넣지 않은 종목) 도 크게.
    unusual = bool(kst["noNaver"] or kst["bad"] or len(kst["noYahoo"]) > KNX_NOYAHOO_WARN or len(kst["diff"]) > KNX_DIFF_WARN
                   or (kst["n"] and kst["conf"] < kst["n"] / 2) or hit or ("kept" in kst and kst.get("floor") is None) or adj or no_anc)
    return unusual, txt


KNX_CUT_KEYS = ("s", "yahoo", "fill", "naver")


def knx_cut_record(cut=None, budget_s=None):
    """pxSrc.fb.knx.cut 모양 (2026-11-20 · 순수 함수): {"s": 단계 시간 한도 초, "yahoo": n, "fill": n, "naver": n} — 코넥스 단계마다 시간 한도로
    묻지 못한 종목 수 (관문 '가격 확인 시간 한도' 줄이 봐요 · 경고만)."""
    c = cut if isinstance(cut, dict) else {}
    return {"s": int(round(fb_budget(c.get("s", budget_s)))), **{k: int(c.get(k) or 0) for k in ("yahoo", "fill", "naver")}}


def px_src_knx_counts(kst):
    """data.json pxSrc.fb.knx — 코넥스 2차 출처 집계 (2026-11-20 · 순수 함수 · 관문이 봐요)."""
    fl = kst.get("floor")
    return {"n": kst["n"], "conf": kst["conf"], "kept": int(kst.get("kept", kst["conf"])), "capOut": len(kst.get("capOut") or []),
            "floor": int(round(fl)) if fl is not None else None,
            "noNaver": len(kst["noNaver"]), "bad": len(kst["bad"]), "noYahoo": len(kst["noYahoo"]),
            "diff": len(kst["diff"]), "yMeta": int(kst.get("yMeta") or 0),
            "diffEx": [f"{c} {n} {a:.0f}/{b:.2f}" for c, n, a, b in kst["diff"][:20]],
            # 리뷰 M1: 기준일 맞춰 보기 — anchor 기준일 (1차 출처 최종본 날짜 · 맞춰 보지 않은 실행은 빈 값) · adj 네이버의 기준일 종가가 최종본과
            # 다름 (그 뒤 값이 수정됐을 수 있어요) · adjEx 예 '코드 이름 최종본/네이버' · noAnchor 기준일 공식 종가나 네이버 기준일 행이 없음
            "anchor": kst["anchor"].isoformat() if isinstance(kst.get("anchor"), dt.date) else None,
            "adj": len(kst.get("adj") or []), "noAnchor": len(kst.get("noAnchor") or []),
            "adjEx": [f"{c} {n} {a:.0f}/{b:.0f}" for c, n, a, b in (kst.get("adj") or [])[:20]],
            "left": sorted(set(kst["noNaver"]) | set(kst["bad"]) | set(kst["noYahoo"]) | {c for c, *_ in kst["diff"]}
                           | {c for c, *_ in (kst.get("adj") or [])} | set(kst.get("noAnchor") or [])),
            # 2026-11-21 (#161): 두 출처가 다르거나 (diff) 네이버의 기준일 종가가 최종본과 다른 (adj) 코넥스 — 같은 날 다시 쓰지 않아요 (kr_same_day_reuse)
            "diffT": sorted({str(c) for c, *_ in kst["diff"]} | {str(c) for c, *_ in (kst.get("adj") or [])}),
            # 2026-11-21 (#161 리뷰): 다시 물으면 바뀔 수 있는 확인 못 한 코넥스 (네이버 행 없음 · 값 못 믿음 · 야후 종가 빈 칸 — 야후가 싣지 않는 종목 빼고)
            "noList": len(kst.get("noList") or []),
            "open": len(kst["noNaver"]) + len(kst["bad"]) + len(kst["noYahoo"]) - len(kst.get("noList") or []),
            "cut": knx_cut_record(kst.get("cut"))}


def kr_knx_check(listing, px_date, naver, codes=None):
    """1차 출처(목록 파일 최종본) 날: 코넥스 종목의 공식 종가를 네이버 일봉 종가와 맞춰 봐요 (2026-11-20 · 순수 함수 · 로그와 pxSrc.knx.chk 만 —
    경고만, 빼지 않아요). codes: 볼 코넥스 종목 (None 이면 listing 의 코넥스 모두). naver: {코드: {날짜: 네이버 행}}.
    반환: {"src": "naver", "n" 맞춰 본 종목, "same", "none" 네이버에 그날 종가가 없거나 공식 종가를 모름, "noneEx" [코드 이름], "diff" ["코드 이름 공식/네이버"]}."""
    rows = {str(r["Code"]).strip(): r for _, r in listing.iterrows() if yahoo_knx_symbol(str(r["Code"]).strip(), r.get("Market"))}
    pick = sorted(rows) if codes is None else [c for c in codes if c in rows]
    out = {"src": "naver", "n": 0, "same": 0, "none": 0, "noneEx": [], "diff": []}
    for c in pick:
        off = kr_official_close(rows[c])
        nr = (naver.get(c) or {}).get(px_date)
        nv = _fin(nr.get("closePrice")) if isinstance(nr, dict) else None
        if off is None or nv is None or nv <= 0:
            out["none"] += 1
            out["noneEx"].append(f"{c} {_txt(rows[c].get('Name'))}".strip())
            continue
        out["n"] += 1
        if abs(nv - off) <= KR_FB_CLOSE_TOL:
            out["same"] += 1
        else:
            out["diff"].append(f"{c} {_txt(rows[c].get('Name'))} {off:.0f}/{nv:.0f}")
    return out


def kr_knx_check_note(ck, n_codes):
    """1차 출처 날 코넥스 네이버 확인 한 줄 (크게 남길지, 글) — 2026-11-20 · 순수 함수. 다르거나 · 네이버 값이 없거나 · 시간 한도 · 받지 못함이면 크게."""
    cut = int((ck.get("cut") or {}).get("naver") or 0)
    loud = bool(ck.get("diff") or ck.get("none") or cut or ck.get("err") or ck.get("fail") or (n_codes and not ck.get("n")))
    txt = (f"코넥스 종가 네이버 확인 (1차 출처 날 · 처리하는 코넥스 {n_codes:,}종목 · 최종본 공식 종가와 네이버 일봉 종가 원 단위까지): "
           f"같음 {ck.get('same', 0):,} / {ck.get('n', 0):,} · 네이버 값 없음 {ck.get('none', 0):,}"
           + (f" ({', '.join(ck.get('noneEx') or [])})" if ck.get("noneEx") else "")
           + (f" · 다름 {len(ck['diff'])}: {', '.join(ck['diff'])}" if ck.get("diff") else "")
           + (f" · 받지 못함 {ck['fail']:,}" if ck.get("fail") else "")
           + (f" · 시간 한도({(ck.get('cut') or {}).get('s')}초)로 묻지 못함 {cut:,}" if cut else "")
           + (f" · 네이버를 받지 못했어요 ({ck['err']})" if ck.get("err") else "")
           + (" — 경고만 (가격은 최종본 그대로 · 빼지 않아요)" if loud else ""))
    return loud, txt


def kr_knx_daily_check(listing, px_date, codes, fetch=fetch_naver_all, budget_s=KR_KNX_CHK_BUDGET_S, say=log):
    """1차 출처 날 코넥스 네이버 확인을 받아서 맞춰 봐요 (2026-11-20). 네트워크가 실패해도 예외를 내지 않아요 — err 로 남겨요 (경고만).
    반환: pxSrc.knx.chk {src, n, same, none, noneEx, diff, fail, cut {s, naver}, err?}."""
    if not codes:
        return {"src": "naver", "n": 0, "same": 0, "none": 0, "noneEx": [], "diff": [], "fail": 0, "cut": {"s": int(budget_s), "naver": 0}}
    try:
        nv, failed, cut = fb_parts(fetch(list(codes), px_date - dt.timedelta(days=7), px_date, budget_s=budget_s, say=say,
                                         label="코넥스 네이버 확인"), 3)
        ck = kr_knx_check(listing, px_date, nv, codes)
        ck["fail"] = len(failed or [])
        ck["cut"] = {"s": int(budget_s), "naver": len(cut or [])}
    except Exception as e:
        # data.json 에는 예외 이름만 (메시지는 로그에만 — 메시지 안의 'None' 같은 낱말이 관문의 글자 검사에 걸리지 않게 · 1차 출처 야후 확인과 같게)
        say(f"  !! 코넥스 네이버 확인 실패: {type(e).__name__}: {str(e)[:120]}")
        ck = {"src": "naver", "n": 0, "same": 0, "none": 0, "noneEx": [], "diff": [], "fail": 0, "cut": {"s": int(budget_s), "naver": 0},
              "err": type(e).__name__}
    return ck


def kr_knx_fetchers():
    """2차 출처 날 코넥스 단계의 진짜 받는 함수들 (kr_fallback_days 의 knx) — 시험은 가짜를 줘요."""
    return {"yahoo": functools.partial(fetch_yahoo_kr_closes, sym=yahoo_knx_symbol, label="코넥스 야후 .KQ 일봉 종가"),
            "fill": functools.partial(yahoo_fill_day, sym=yahoo_knx_symbol, label="코넥스 야후 차트 다시 읽기"),
            "naver": fetch_naver_all}


def fb_parts(res, n):
    """받는 함수의 결과 → n 칸 (2026-11-20). 시간 한도 칸(마지막)이 없는 예전 모양(시험이 주는 가짜 함수 · 두 칸)이면 그 칸은 None —
    부르는 쪽은 None 을 '시간 한도에 걸리지 않음'(0 · 빈 목록)으로 읽어요. 진짜 함수는 늘 그 칸을 채워요."""
    res = tuple(res)
    return res + (None,) * (n - len(res))


def kr_fb_cut_note(what, got, target, cut, budget, more=""):
    """시간 한도에 걸린 단계의 큰 메모 한 줄 (2026-11-20 · 순수 함수)."""
    return (f"!! 2차 출처 시간 한도 {budget:.0f}초 — {what}: 받은 {got:,} / 대상 {target:,} — 나머지 {max(target - got, 0):,}종목은 확인 못 한 종목 "
            f"(시간 한도로 묻지 못함 {cut:,}{more} · 그날 파일에서 빠져요 · 필수 종목이 빠지면 관문이 멈춰요)")


def kr_fallback_days(days, universe_of, now, special, fetch_daum=fetch_daum_all, fetch_yahoo=fetch_yahoo_kr_closes, must=GATE_MUST,
                     fill_day=yahoo_fill_day, say=log, caps=None, knx=None, anchor=None, cached=None, keep=None):
    """끝난 거래일(days)마다 2차 출처 행을 만들어요 (2026-11-19). universe_of(d) → (DataFrame, 설명).
    반환: ({날짜: (DataFrame, 집계)}, 메모들). 마감 + 30분이 지나지 않은 날 · 목록이 없는 날은 빠지고 메모에 남아요.
    2026-11-20: 단계마다 시간 한도 (KR_FB_PHASE_BUDGET_S · 받는 함수 안에서) — 걸리면 크게 남기고 집계 cut (pxSrc.fb.cut) 에 적어요.
    단계를 시작할 때 say 로 바로 한 줄씩 남겨요 (메모는 끝난 뒤에 한꺼번에 나와서, 멈춘 실행의 로그로는 어디인지 몰랐어요).
    caps: 1차 출처 최종본의 {코드: 시가총액} (kr_fb_caps) — 묻는 순서 (필수 종목 → 시가총액 큰 순 → 모르는 종목 코드 순 · 리뷰 M1).
    없으면 필수 종목 → 코드 순.
    knx (2026-11-20 · Jack, 2026-11-19 답 5): 코넥스 단계의 받는 함수들 {"yahoo", "fill", "naver"} (kr_knx_fetchers · 파이프라인은 늘 줘요).
    주면 코스피 · 코스닥 세 단계가 끝난 뒤 코넥스만 따로 세 단계 (네이버 일봉 · 야후 .KQ 일봉 종가 · 야후 차트 다시 읽기 · 같은 단계 시간 한도 ·
    같은 묻는 순서) 를 묻고, 두 종가가 원 단위까지 같은 코넥스 종목을 그날 행에 더해요 (집계 knx · kr_knx_confirm). 코스피 · 코스닥 단계와 그
    집계는 knx 가 있든 없든 같아요. None 이면 코넥스는 예전처럼 묻지 않아요 (시험).
    anchor (리뷰 M1 · kr_knx_anchor): (px0, {코드: px0 공식 종가}) — 1차 출처 최종본의 코넥스 공식 종가. 네이버 일봉을 px0 부터 받아, 네이버의 px0
    종가가 그 공식 종가와 같은 코넥스만 확인해요 (kr_knx_confirm — px0 뒤 권리락 · 분할 · 병합으로 두 출처가 함께 수정된 값을 막아요). 파이프라인은
    늘 줘요 (fetch_korea). knx 를 주고 anchor 를 주지 않으면 맞춰 보지 않고 크게 남겨요 (시험만).
    cached (2026-11-21 · #161 · kr_fb_cache_pick): 같은 날 다시 도는 실행 — 발행본이 이미 두 출처로 확인한 종목의 지난 실행 값 {"kk": {코드: {"d":
    {날짜: 다음 행}, "y": {날짜: 야후 종가}}}, "knx": {코드: {"n": {날짜: 네이버 행}, "y": {날짜: 야후 종가}}}}. 그 종목은 다음 · 야후 · 네이버에
    다시 묻지 않고 그 값으로 확인해요 (확인 · 집계는 물은 종목과 똑같이 · 묻는 수만 줄어요). keep (dict): 주면 마지막 날 두 출처로 확인된 종목의
    값을 같은 모양으로 담아요 (fetch_korea 가 보관본에 써요 — 다음 같은 날 실행이 써요)."""
    notes, unis = [], {}
    for d in sorted(days)[-KR_FB_MAX_DAYS:]:
        if not kr_fb_final(d, now, special):
            notes.append(f"!! {d}: 그날 마감 + 30분 ({listing_final_cut(d, special):%H:%M} KST) 전이라 2차 출처도 쓰지 않아요")
            continue
        uni, how = universe_of(d)
        if uni is None:
            notes.append(f"!! {d}: {how} → 2차 출처로 만들 수 없어요")
            continue
        unis[d] = uni
        notes.append(f"{d} 종목 목록: {how} · {len(uni):,}행")
    if not unis:
        return {}, notes
    cm, n_mkt = {}, set()
    for uni in unis.values():
        for c, m in zip(uni["Code"].astype(str).str.strip(), uni["Market"]):
            if len(c) != 6:
                continue
            if yahoo_kr_symbol(c, m):
                cm.setdefault(c, m)                 # 다음 × 야후 짝이 될 수 있는 종목만 물어요 (코넥스는 다음에 없어요 — 아래 야후 × 네이버)
            else:
                n_mkt.add(c)
    kcm = {}
    for uni in unis.values():
        for c, m in zip(uni["Code"].astype(str).str.strip(), uni["Market"]):
            if len(c) == 6 and yahoo_knx_symbol(c, m):
                kcm.setdefault(c, m)
    if knx is None:
        notes.append(f"다음에 없는 시장(코넥스 등) {len(n_mkt):,}종목은 2차 출처로 확인할 수 없어 묻지 않아요 (코넥스 야후 × 네이버 단계를 부르지 않은 실행)")
    else:
        notes.append(f"다음에 없는 시장 {len(n_mkt):,}종목 (그중 코넥스 {len(kcm):,}종목은 아래 야후 .KQ × 네이버 · 그 밖 {len(n_mkt - set(kcm)):,}종목은 묻지 않아요)")
    ck = (cached or {}).get("kk") if isinstance((cached or {}).get("kk"), dict) else {}
    cx = (cached or {}).get("knx") if isinstance((cached or {}).get("knx"), dict) else {}
    skip_kk = sorted(c for c in cm if c in ck)
    skip_kx = sorted(c for c in kcm if c in cx)
    if cached is not None:
        say(f"  !! 2차 출처 같은 날 다시 쓰기 (#161): 발행본이 이미 두 출처로 확인한 종목은 다시 묻지 않아요 — 코스피 · 코스닥 다시 씀 {len(skip_kk):,} · "
            f"묻는 종목 {len(cm) - len(skip_kk):,} / {len(cm):,} · 코넥스 다시 씀 {len(skip_kx):,} · 묻는 종목 {len(kcm) - len(skip_kx):,} / {len(kcm):,}")
        notes.append(f"!! 2차 출처 같은 날 다시 쓰기: 다음 · 야후 다시 묻지 않음 {len(skip_kk):,}종목 · 묻는 종목 {len(cm) - len(skip_kk):,} — "
                     f"코넥스 네이버 · 야후 다시 묻지 않음 {len(skip_kx):,} · 묻는 종목 {len(kcm) - len(skip_kx):,}")
    cm = {c: m for c, m in cm.items() if c not in ck}
    kcm = {c: m for c, m in kcm.items() if c not in cx}
    order = fb_order(set(cm), first=must, caps=caps)
    cm = {c: cm[c] for c in order}                  # 이 차례로 물어요 (세 단계 모두)
    n_must = sum(1 for c in dict.fromkeys(must) if c in cm)
    rest = order[n_must:]                           # 필수 종목 뒤 (fb_order 가 필수 종목을 맨 앞에 둬요)
    n_cap = sum(1 for c in rest if caps and _cap_ok(caps.get(c)))
    weak = not caps or n_cap < 0.9 * max(len(rest), 1)     # 1차 출처 시가총액을 모르는 종목이 많으면 크게 (큰 종목도 늦게 물어요)
    say(f"{'  !! ' if weak else '· '}2차 출처 묻는 순서: 필수 종목 {n_must} → "
        + (f"1차 출처 최종본 시가총액 큰 순 {n_cap:,} → 시가총액 모름 {len(rest) - n_cap:,} (코드 순)" if caps
           else f"코드 순 {len(rest):,} (1차 출처 시가총액이 없어요)")
        + (" — 시간 한도에 걸리면 큰 종목도 빠질 수 있어요" if weak else ""))
    first = min(unis)
    n_days = min(KR_FB_MAX_DAYS + 15, (now.date() - first).days + 3)    # 달력 날 수 ≥ 거래일 수 — 첫날까지 넉넉히
    budget = fb_budget(None)
    t0 = time.time()
    say(f"· 2차 출처: 다음 일별 시세 묻는 중 — {len(cm):,}종목 (최근 {n_days}거래일 · 단계 시간 한도 {budget:.0f}초)")
    daum, d_fail, d_cut = fb_parts(fetch_daum(list(cm), n_days), 3)
    d_cut = list(d_cut or [])
    notes.append(f"{'!! ' if len(daum) < KR_FB_LOUD_COVER * len(cm) else ''}다음 일별 시세: {len(daum):,} / {len(cm):,}종목 받음 (최근 {n_days}거래일 · {time.time() - t0:.0f}초)"
                 + (f" · 못 받음 {len(d_fail):,}: {', '.join(d_fail[:10])}" if d_fail else "")
                 + (f" · 시간 한도로 묻지 못함 {len(d_cut):,}" if d_cut else ""))
    if d_cut:
        notes.append(kr_fb_cut_note("다음 일별 시세", len(daum), len(cm), len(d_cut), budget, f" · 못 받음 {len(d_fail):,}"))
    t0 = time.time()
    say(f"· 2차 출처: 야후 .KS/.KQ 일봉 종가 묻는 중 (종목마다 차트) — {len(cm):,}종목 (단계 시간 한도 {budget:.0f}초)")
    yahoo, y_fail, y_cut = fb_parts(fetch_yahoo(cm, first - dt.timedelta(days=1), max(unis) + dt.timedelta(days=1)), 3)
    y_cut = int(y_cut or 0)
    notes.append(f"{'!! ' if len(yahoo) < KR_FB_LOUD_COVER * len(cm) else ''}야후 .KS/.KQ 종가: {len(yahoo):,} / {len(cm):,}종목 받음 ("
                 f"{time.time() - t0:.0f}초)" + (f" · 못 받음 {y_fail:,}" if y_fail else "")
                 + (f" · 시간 한도로 묻지 못함 {y_cut:,}" if y_cut else ""))
    if y_cut:
        notes.append(kr_fb_cut_note("야후 일봉 종가", len(yahoo), len(cm), y_cut, budget, f" · 마지막 날 {max(unis)} 은 아래 차트 다시 읽기가 채울 수 있어요"))
    # 야후는 가장 최근 날의 일봉 종가를 몇 시간 비워 둬요 → 그 날 종가가 없고 다음 행은 있는 종목만 차트를 다시 읽어요 (마감 뒤 regularMarketPrice)
    last = max(unis)
    need = {c: m for c, m in cm.items() if last in (daum.get(c) or {})}
    t0 = time.time()
    say(f"· 2차 출처: 야후 {last} 일봉 종가가 빈 종목의 차트를 다시 읽는 중 (단계 시간 한도 {budget:.0f}초)")
    fill = fill_day(yahoo, need, last, krx_close(last, special))
    f_cut = int(fill.get("cut") or 0)
    if fill["need"]:
        notes.append(f"{'!! ' if fill['fail'] + f_cut > (1 - KR_FB_LOUD_COVER) * len(need) else ''}야후 {last} 일봉 종가가 빈 종목 {fill['need']:,} → 차트를 다시 읽음: 일봉 종가 {fill['bar']:,} · "
                     f"마감({krx_close(last, special):%H:%M}) 뒤 regularMarketPrice {fill['meta']:,} · 없음 {fill['none']:,} · 받지 못함 {fill['fail']:,} "
                     + (f"· 시간 한도로 묻지 못함 {f_cut:,} " if f_cut else "") + f"({time.time() - t0:.0f}초)")
    if f_cut:
        notes.append(kr_fb_cut_note(f"야후 {last} 차트 다시 읽기", fill["bar"] + fill["meta"], fill["need"], f_cut, budget,
                                    f" · 받지 못함 {fill['fail']:,} · 없음 {fill['none']:,}"))
    cut = fb_cut_record({"daum": len(d_cut), "yahoo": y_cut, "fill": f_cut}, budget)
    kn, floor = None, None
    if knx is not None:
        # 리뷰 M1 (2026-11-20): 평소 날 발행하는 코넥스만 그날 파일에 — 1차 출처 최종본의 MAX_KR 번째 시가총액 이상인 코넥스만 더해요.
        # 확인된 코넥스를 모두 더하면 코스피 · 코스닥 확인이 MAX_KR 보다 적은 날 코넥스 90여 종목이 빈자리를 채워 '국내 종목 수' 바닥(관문 KR_MIN)이
        # 평소보다 늦게 걸려요 (평소 날 상위 MAX_KR 안 코넥스는 30종목 남짓). 이 기준이면 바닥이 걸리는 때 빠진 '평소 발행 종목' 수가 예전과 같아요.
        floor = kr_knx_cap_floor(caps)
        if floor is None:
            notes.append(f"!! 코넥스 시가총액 기준을 정할 수 없어요 — 1차 출처 최종본에서 시가총액을 아는 종목이 {len([1 for v in (caps or {}).values() if _cap_ok(v)]):,}개로 "
                         f"{MAX_KR:,}개보다 적어요 → 그날 파일에 코넥스를 더하지 않아요 (확인은 그대로 남겨요)")
        else:
            notes.append(f"코넥스 시가총액 기준 (평소 날처럼 시가총액 상위 {MAX_KR:,} 안의 코넥스만 그날 파일에 · 국내 종목 수 바닥이 평소와 같게): "
                         f"1차 출처 최종본의 {MAX_KR:,}번째 시가총액 {floor / 1e8:,.0f}억원 이상 — 날마다 넣은 수와 뺀 종목은 아래 '코넥스 2차 출처' 줄")
        if anchor is None:
            notes.append("!! 코넥스 기준일 맞춰 보기 없이 부른 실행이에요 (anchor 없음 — 1차 출처 최종본의 코넥스 공식 종가와 네이버를 맞춰 보지 않아요 · 시험만)")
        else:
            notes.append(f"{'!! ' if anchor[0] is None or not anchor[1] else ''}코넥스 기준일 맞춰 보기 (리뷰 M1): 네이버의 "
                         f"{anchor[0] if anchor[0] is not None else '기준일'} 종가가 그날 1차 출처 최종본의 공식 종가와 같은 코넥스만 확인해요 — "
                         f"그날 공식 종가를 아는 코넥스 {len(anchor[1]):,}종목"
                         + (" (기준일 최종본이 없어 코넥스는 한 종목도 확인되지 않아요)" if anchor[0] is None or not anchor[1] else ""))
        try:
            if kcm:
                kn = kr_knx_phases(kcm, unis, now, special, knx, must, caps, notes, say, start=anchor[0] if anchor is not None else None)
            else:                                   # 2026-11-21 (#161): 물을 코넥스가 없어요 (모두 보관본) — 묻지 않고 빈 결과
                kn = {"naver": {}, "yahoo": {}, "metaCodes": set(), "cut": knx_cut_record({"yahoo": 0, "fill": 0, "naver": 0})}
            for c in skip_kx:
                kn["naver"][c] = dict(cx[c].get("n") or {})
                kn["yahoo"][c] = dict(cx[c].get("y") or {})
        except Exception as e:                      # 코넥스 단계의 고장이 코스피 · 코스닥 발행을 막지 않게 — 크게 남기고 코넥스만 빠져요 (관문이 경고해요)
            msg = (f"!! 코넥스 2차 출처 단계가 고장 났어요 ({type(e).__name__}: {str(e)[:120]}) — 그날 파일에 코넥스는 없어요 "
                   "(코스피 · 코스닥은 그대로 · 관문 '코넥스 종가 두 출처' 줄이 경고해요)")
            notes.append(msg)
            say(f"  {msg}")
    for c in skip_kk:                               # 2026-11-21 (#161): 다시 묻지 않은 종목은 지난 실행의 그 값으로 (확인은 물은 종목과 똑같이)
        daum[c] = dict(ck[c].get("d") or {})
        yahoo[c] = dict(ck[c].get("y") or {})
    out = {}
    for d, uni in sorted(unis.items()):
        fr, st = kr_fb_confirm(d, uni, daum, yahoo, must=must)
        st["cut"] = cut                             # 2026-11-20: 시간 한도로 묻지 못한 종목 수 (단계마다 · 모든 날에 같은 값)
        st["skip"] = len(skip_kk) if cached is not None else None    # 2026-11-21 (#161): 다시 묻지 않은 코스피 · 코스닥 (pxSrc.fb.skip)
        st["yMeta"] = sum(1 for c in fr["Code"] if c in fill["metaCodes"]) if d == last else 0
        st["_uni"] = uni                            # 그날 전체 종목 목록 (주식 수는 가격과 상관없어요 — 우선주 주식 수에 써요)
        st["_daumShr"] = {c: int(_fin(r[d].get("listedSharesCount")) or 0) for c, r in daum.items() if d in r}
        st["_one"] = kr_fb_one_source(d, st, daum, yahoo)       # #161 리뷰 3차 A-S2: 한 출처만 있는 종가 (같은 날 다시 쓰기가 봐요 · data.json 에는 없어요)
        if kn is not None:                          # 2026-11-20: 코넥스 (야후 .KQ × 네이버) — 확인된 종목만 그날 행에 더해요
            # 검증 리뷰: 확인 · 시가총액 기준도 위 단계와 같이 try 안에서 — 고장이 나면 그날 코넥스만 빠지고 크게 남아요 (st 에 knx 가 없으면
            # pxSrc.knx.px 가 빈 값 → 관문 '코넥스 단계를 묻지 않았어요' 경고). 끝까지 된 뒤에만 그날 행 · 집계에 넣어요 (반쯤 바뀐 값이 남지 않게).
            try:
                kfr, kst = kr_knx_confirm(d, uni, kn["yahoo"], kn["naver"], anchor=anchor)
                kst["cut"] = kn["cut"]
                kst["yMeta"] = sum(1 for c in kfr["Code"] if c in kn["metaCodes"]) if d == last else 0
                kfr, kst["capOut"] = kr_knx_cap_keep(kfr, floor)      # 리뷰 M1: 평소 날 발행하는 코넥스만 (확인 수 conf 는 그대로 · kept 가 그날 파일의 행)
                kst["kept"], kst["floor"] = len(kfr), floor
                fr_k = (pd.concat([fr, kfr], ignore_index=True) if len(fr) else kfr.reset_index(drop=True)) if len(kfr) else fr
            except Exception as e:
                msg = (f"!! {d} 코넥스 2차 출처 확인이 고장 났어요 ({type(e).__name__}: {str(e)[:120]}) — 그날 파일에 코넥스는 없어요 "
                       "(코스피 · 코스닥은 그대로 · 관문 '코넥스 종가 두 출처' 줄이 경고해요)")
                notes.append(msg)
                say(f"  {msg}")
            else:
                st["knx"] = kst
                fr = fr_k
        out[d] = (fr, st)
    if isinstance(keep, dict) and last in out:      # 2026-11-21 (#161): 마지막 날 두 출처로 확인된 종목의 값 (다음 같은 날 실행이 다시 묻지 않게)
        ok = set(out[last][0]["Code"].astype(str).str.strip())
        ud = set(unis)
        kk = {c: {"d": {d.isoformat(): {k: r[k] for k in KR_FB_DAUM_KEEP if k in r} for d, r in daum[c].items() if d in ud and isinstance(r, dict)},
                  "y": {d.isoformat(): v for d, v in yahoo[c].items() if d in ud}}
              for c in sorted(ok) if c in daum and c in yahoo and last in daum[c]}
        kx = {}
        if kn is not None:                          # 그날 파일에 넣은 코넥스 + 확인됐지만 시가총액 기준 아래라 넣지 않은 코넥스 (capOut) — 모두 두 출처 확인
            okx = ok | set(((out[last][1].get("knx") or {}).get("capOut")) or [])
            kx = {c: {"n": {d.isoformat(): r for d, r in kn["naver"][c].items()}, "y": {d.isoformat(): v for d, v in kn["yahoo"][c].items() if d in ud}}
                  for c in sorted(okx) if c in kn["naver"] and c in kn["yahoo"]}
        keep.update({"v": KR_FB_CACHE_V, "day": last.isoformat(), "days": sorted(d.isoformat() for d in ud), "kk": kk, "knx": kx})
    return out, notes


def kr_knx_phases(kcm, unis, now, special, knx, must, caps, notes, say, start=None):
    """2차 출처 날 코넥스 세 단계 (2026-11-20 · kr_fallback_days 가 코스피 · 코스닥 단계 뒤에 불러요): 네이버 일봉 → 야후 .KQ 일봉 종가 →
    마지막 날 야후 종가가 빈 종목의 차트 다시 읽기 (다음 × 야후 의 다음 → 야후 → 다시 읽기와 같은 차례 · 같은 단계 시간 한도 · 같은 묻는 순서).
    start (리뷰 M1): 1차 출처 최종본 날짜 px0 — 네이버 일봉을 그날부터 받아요 (기준일 맞춰 보기 · kr_knx_confirm anchor). None 이면 첫날 하루 전부터.
    반환: {"naver", "yahoo", "metaCodes", "cut"} — notes 에 메모를 더해요."""
    budget = fb_budget(None)
    first, last = min(unis), max(unis)
    n_start = min(start, first - dt.timedelta(days=1)) if start is not None else first - dt.timedelta(days=1)
    order = fb_order(set(kcm), first=must, caps=caps)
    kcm = {c: kcm[c] for c in order}
    t0 = time.time()
    say(f"· 2차 출처 (코넥스): 네이버 일봉 묻는 중 — {len(kcm):,}종목 ({n_start} ~ {last}" + (f" · {start} 는 기준일 맞춰 보기" if start is not None else "")
        + f" · 단계 시간 한도 {budget:.0f}초)")
    nv, n_fail, n_cut = fb_parts(knx["naver"](list(kcm), n_start, last), 3)
    n_cut = list(n_cut or [])
    n_fail = list(n_fail or [])
    notes.append(f"{'!! ' if len(nv) < KR_FB_LOUD_COVER * len(kcm) else ''}코넥스 네이버 일봉: {len(nv):,} / {len(kcm):,}종목 받음 ({time.time() - t0:.0f}초)"
                 + (f" · 못 받음 {len(n_fail):,}: {', '.join(n_fail[:10])}" if n_fail else "")
                 + (f" · 시간 한도로 묻지 못함 {len(n_cut):,}" if n_cut else ""))
    if n_cut:
        notes.append(kr_fb_cut_note("코넥스 네이버 일봉", len(nv), len(kcm), len(n_cut), budget, f" · 못 받음 {len(n_fail):,}"))
    t0 = time.time()
    say(f"· 2차 출처 (코넥스): 야후 .KQ 일봉 종가 묻는 중 (종목마다 차트) — {len(kcm):,}종목 (단계 시간 한도 {budget:.0f}초)")
    yk, y_fail, y_cut = fb_parts(knx["yahoo"](kcm, first - dt.timedelta(days=1), last + dt.timedelta(days=1)), 3)
    y_cut = int(y_cut or 0)
    notes.append(f"코넥스 야후 .KQ 종가: {len(yk):,} / {len(kcm):,}종목 받음 ({time.time() - t0:.0f}초 · 야후에 없는 코넥스 종목이 늘 몇 개 있어요)"
                 + (f" · 못 받음 {y_fail:,}" if y_fail else "") + (f" · 시간 한도로 묻지 못함 {y_cut:,}" if y_cut else ""))
    if y_cut:
        notes.append(kr_fb_cut_note("코넥스 야후 .KQ 일봉 종가", len(yk), len(kcm), y_cut, budget, f" · 마지막 날 {last} 은 아래 차트 다시 읽기가 채울 수 있어요"))
    # 다시 읽기는 네이버 행이 있고, 야후가 앞 단계에서 차트를 준 (다른 날 종가가 있는) 종목만 — 야후에 아예 없는 코넥스 (늘 11종목 남짓 · 404) 는
    # 다시 물어도 같아서 묻지 않아요 (앞 단계 '못 받음' 에 이미 세었어요)
    need = {c: m for c, m in kcm.items() if last in (nv.get(c) or {}) and c in yk}
    t0 = time.time()
    say(f"· 2차 출처 (코넥스): 야후 {last} 일봉 종가가 빈 종목의 차트를 다시 읽는 중 (단계 시간 한도 {budget:.0f}초)")
    fill = knx["fill"](yk, need, last, krx_close(last, special))
    f_cut = int(fill.get("cut") or 0)
    if fill["need"]:
        notes.append(f"{'!! ' if fill['fail'] + f_cut else ''}코넥스 야후 {last} 일봉 종가가 빈 종목 {fill['need']:,} → 차트를 다시 읽음: 일봉 종가 {fill['bar']:,} · "
                     f"마감({krx_close(last, special):%H:%M}) 뒤 regularMarketPrice {fill['meta']:,} · 없음 {fill['none']:,} · 받지 못함 {fill['fail']:,} "
                     + (f"· 시간 한도로 묻지 못함 {f_cut:,} " if f_cut else "") + f"({time.time() - t0:.0f}초 · 야후의 코넥스 meta 시각은 2024-07 에 멈춰 있어 "
                     "regularMarketPrice 로는 거의 채워지지 않아요 — 채워지지 않은 종목은 그날 빠져요)")
    if f_cut:
        notes.append(kr_fb_cut_note(f"코넥스 야후 {last} 차트 다시 읽기", fill["bar"] + fill["meta"], fill["need"], f_cut, budget,
                                    f" · 받지 못함 {fill['fail']:,} · 없음 {fill['none']:,}"))
    return {"naver": nv, "yahoo": yk, "metaCodes": set(fill.get("metaCodes") or ()),
            "cut": knx_cut_record({"yahoo": y_cut, "fill": f_cut, "naver": len(n_cut)}, budget)}


def kr_fb_note(d, st, names):
    """2차 출처 집계 한 줄 (크게 남길지, 글) — 빠진 종목 이름을 모두 셉니다 (예시 12개). (순수 함수)"""
    def ex(codes):
        return ", ".join(f"{c} {names.get(c, '')}".strip() for c in codes[:12]) + (" …" if len(codes) > 12 else "")
    left = len(st["noDaum"]) + len(st["bad"]) + len(st["noYahoo"]) + len(st["diff"])
    base = st["n"] - len(st.get("mkt") or [])
    low = st["conf"] < KR_FB_LOUD_COVER * base
    txt = (f"{d} 2차 출처(다음 × 야후 종가 원 단위까지 같음): 확인 {st['conf']:,} / {base:,}종목 (야후에 있는 시장 · 코넥스 등 {len(st.get('mkt') or []):,}종목 빼고)"
           + (f" (그중 야후 값이 마감 뒤 regularMarketPrice {st['yMeta']:,})" if st.get("yMeta") else "") + f" · 빠짐 {left:,} "
           f"(다음 행 없음 {len(st['noDaum']):,} · 다음 값 못 믿음 {len(st['bad']):,} · 야후 종가 없음 {len(st['noYahoo']):,} · "
           f"두 종가가 다름 {len(st['diff']):,})" + (f" — 확인이 {KR_FB_LOUD_COVER:.0%} 아래예요" if low else ""))
    if st["diff"]:
        txt += " — 다름: " + ", ".join(f"{c} {n} 다음 {a:,.0f} · 야후 {b:,.2f}" for c, n, a, b in st["diff"][:12]) + (" …" if len(st["diff"]) > 12 else "")
    if st["noDaum"]:
        txt += f" — 다음 행 없음: {ex(st['noDaum'])}"
    if st["noYahoo"]:
        txt += f" — 야후 종가 없음: {ex(st['noYahoo'])}"
    if st["bad"]:
        txt += f" — 다음 값 못 믿음: {ex(st['bad'])}"
    if st["shrDiff"]:
        txt += f" — 목록 파일과 상장주식수가 다른 종목 {len(st['shrDiff']):,} (다음 값을 써요): {ex(st['shrDiff'])}"
    if st["must"]:
        txt += f" — !! 확인되지 않은 필수 종목: {', '.join(st['must'])} (관문이 멈춰요)"
    cut = fb_cut_record(st.get("cut"))
    hit = any(cut[k] for k in ("daum", "yahoo", "fill"))
    if hit:
        txt += (f" — !! 시간 한도 {cut['s']}초로 묻지 못한 종목 (다음 {cut['daum']:,} · 야후 일봉 {cut['yahoo']:,} · 야후 다시 읽기 {cut['fill']:,}) 이"
                " 위 '다음 행 없음' · '야후 종가 없음' 에 들어 있어요")
    return bool(st["must"] or st["diff"] or st["bad"] or low or hit), txt


def px_src_counts(st):
    """data.json pxSrc.fb — 2차 출처 집계 (관문이 모양을 봐요). (순수 함수)
    2026-11-20: 코넥스 (야후 .KQ × 네이버) 를 물은 날은 knx (px_src_knx_counts) 가 붙고, conf 는 그날 파일의 행 수 = 두 출처로 확인된 종목
    (다음 × 야후 + 그날 파일에 넣은 코넥스 knx.kept · 리뷰 M1: 시가총액 기준 아래라 뺀 코넥스는 세지 않아요) — 관문이 '확인 종목 수 ≥ 발행한 국내 종목 수' 로 봐요. n · mkt · noDaum · bad · noYahoo · diff · yMeta · diffEx 는
    예전 그대로 다음 × 야후 짝의 수예요 (mkt = 그 짝이 없는 시장 · 코넥스 등)."""
    kst = st.get("knx")
    out = {"n": st["n"], "conf": st["conf"] + (int(kst.get("kept", kst["conf"])) if kst else 0), "mkt": len(st.get("mkt") or []), "noDaum": len(st["noDaum"]),
           "bad": len(st["bad"]), "noYahoo": len(st["noYahoo"]),
           "diff": len(st["diff"]), "yMeta": int(st.get("yMeta") or 0), "diffEx": [f"{c} {n} {a:.0f}/{b:.2f}" for c, n, a, b in st["diff"][:20]], "must": list(st["must"]),
           "cut": fb_cut_record(st.get("cut")),
           # 2026-11-21 (#161): 같은 날 다시 도는 실행이 다시 묻지 않은 코스피 · 코스닥 (발행본이 이미 확인 · 지난 실행의 값으로 확인 · conf 에 들어 있어요)
           "skip": int(st.get("skip") or 0),
           # 2026-11-21 (#161 리뷰): 다시 물으면 바뀔 수 있는 확인 못 한 종목 (다음 행 없음 · 다음 값 못 믿음 · 야후 종가 빈 칸) — 두 종가가 다른 종목과
           # 야후에 차트가 아예 없는 종목 (noList) 은 빼요. already_published.open_closes 가 이 수로 뒤의 실행을 돌릴지 정해요
           "noList": len(st.get("noList") or []),
           "open": len(st["noDaum"]) + len(st["bad"]) + len(st["noYahoo"]) - len(st.get("noList") or []),
           # 2026-11-21 (#161): 두 종가가 다른 종목 코드 모두 — 같은 날 다시 도는 실행이 지난 발행본의 확인 종가를 다시 쓸지 볼 때 (지금 두 출처가
           # 서로 다르면 다시 쓰지 않아요 · kr_same_day_reuse)
           "diffT": sorted(str(c) for c, *_ in st["diff"])}
    if kst:
        out["knx"] = px_src_knx_counts(kst)
    return out


def kr_primary_check(listing, px_date, yahoo, sample=PX_CHECK_SAMPLE, must=GATE_MUST):
    """1차 출처(목록 파일 최종본)의 공식 종가를 야후 종가와 맞춰 봐요 — 필수 종목 + 표본 (2026-11-19 · 순수 함수 · 로그와 pxSrc.chk 만).
    표본: 코스피 · 코스닥 종목을 코드 순으로 늘어놓고 고르게 sample 개. 반환: {"src", "n", "same", "none", "diff": [...]}."""
    rows = {str(r["Code"]).strip(): r for _, r in listing.iterrows()}
    pick = [c for c in must if c in rows]
    pick += [c for c in px_check_sample(sorted(c for c, r in rows.items() if yahoo_kr_symbol(c, r.get("Market"))), sample) if c not in pick]
    out = {"src": "yahoo", "n": 0, "same": 0, "none": 0, "diff": []}
    for c in pick:
        off = kr_official_close(rows[c])
        y = _fin((yahoo.get(c) or {}).get(px_date))
        if off is None or y is None:
            out["none"] += 1
            continue
        out["n"] += 1
        if abs(y - off) <= KR_FB_CLOSE_TOL:
            out["same"] += 1
        else:
            out["diff"].append(f"{c} {_txt(rows[c].get('Name'))} {off:.0f}/{y:.2f}")     # 2026-11-20 (검증 리뷰): 빈 이름이 'nan' 글자로 가지 않게
    return out


def px_src_final(src, stocks):
    """발행 직전의 data.json pxSrc (2026-11-19 · 순수 함수): 발행하는 한국 종목(cls kr · 목록에서 온 것) 수를 출처별로 (n).
    2026-11-20: knx 가 있으면 t 를 발행하는 코넥스 종목으로 줄이고 n 에 출처별 수를 적어요 (그 사이에 빠진 종목이 있어도 발행 목록과 같게)."""
    if not isinstance(src, dict):
        return None
    out = {k: v for k, v in src.items() if not str(k).startswith("_")}     # #161 리뷰 3차: 내부 칸 (_one) 은 data.json 에 쓰지 않아요
    # 2026-11-19 (Jack): 마지막 확인 종가(pxd)로 실은 종목은 이 출처의 pxDate 가격이 아니라 세지 않아요 (그 수는 pxSrc.own)
    out["n"] = {src.get("px") or "none": sum(1 for x in stocks if x.get("cls") == "kr" and x.get("pxd") is None)}
    if isinstance(src.get("knx"), dict):
        k = dict(src["knx"])
        want = set(k.get("t") or [])
        # 2026-11-20 (#159 × #158): 마지막 확인 종가(pxd)로 실은 코넥스는 그날 야후 .KQ × 네이버로 확인한 종목이 아니라 knx.t 에 넣지 않아요
        # (want 는 그날 파일의 코넥스라 그런 종목은 원래 없어요 — 두 번 지켜요)
        pub = sorted(x["t"] for x in stocks if x.get("cls") == "kr" and x.get("t") in want and x.get("pxd") is None)
        k["t"] = pub
        k["n"] = {k.get("px") or "none": len(pub)} if pub else {}
        out["knx"] = k
    return out


def kr_ended_days(px_date, trade_days, today, max_days=KR_FB_MAX_DAYS):
    """기준일(1차 출처) 뒤에 이미 끝난 거래일 (KOSPI 일봉 날짜 · 오늘은 빼요 · 기준일이 없으면 최근 max_days 거래일). (순수 함수)"""
    ds = sorted({pd.Timestamp(t).date() for t in trade_days})
    ended = [d for d in ds if d < today and (px_date is None or d > px_date)]
    return ended[-max_days:]


def kr_second_source(px_date, listing, ended, now, special, universe_of, fallback=kr_fallback_days, names=None):
    """1차 출처 뒤에 끝난 거래일이 있으면 2차 출처로 그날들을 만들어요 (2026-11-19 · Jack 규칙 3).
    반환: (기준일, 목록 DataFrame, {날짜: DataFrame} 기준일 앞 2차 출처 날들 (d1 · val20 · 기준가 연결에 써요), pxSrc dict, 로그 [(크게?, 글)],
    그날 전체 종목 목록 (2차 출처 날이면 확인 못 한 종목까지 · 주식 수에만 써요 · 1차 출처면 목록 그대로) 과 다음 상장주식수 {코드: 주식 수}).
    기준일은 필수 종목이 모두 확인된 가장 최근 날. 그런 날이 없으면 1차 출처 그대로 (관문의 '끝난 거래일' 줄이 멈춰요)."""
    logs = []
    src = {"v": 1, "px": PX_SRC_LISTING if px_date else None, "date": px_date.isoformat() if px_date else None,
           "days": {}, "fb": None, "must": [], "chk": None, "n": {},
           # 2026-11-20: 코넥스 종가의 출처 (px · 1차 출처 날 listing · 2차 출처 날 야후 .KQ × 네이버 · 그날 파일에 코넥스가 없으면 None) ·
           # t 처리하는 코넥스 종목 (fetch_korea) · n 발행한 코넥스 종목 수 (px_src_final) · chk 1차 출처 날 네이버 확인 (kr_knx_check)
           "knx": {"px": PX_SRC_LISTING if px_date else None, "t": [], "n": {}, "chk": None}}
    if not ended:
        return px_date, listing, {}, src, logs, (listing, {})
    fb, notes = fallback(ended, universe_of, now, special)
    for n in notes:
        logs.append((n.startswith("!!"), n.removeprefix("!! ")))
    names = names or {}
    for d, (df, st) in sorted(fb.items()):
        nm = dict(names)
        loud, txt = kr_fb_note(d, st, nm)
        logs.append((loud, txt))
        if st.get("knx"):
            logs.append(kr_knx_note(d, st["knx"], nm))     # 2026-11-20: 코넥스 (야후 .KQ × 네이버) — 빠진 종목을 모두 이름과 까닭으로
    good = [d for d, (df, st) in fb.items() if not st["must"] and len(df)]
    if not good:
        logs.append((True, f"2차 출처로 필수 종목을 모두 확인한 날이 없어요 ({', '.join(d.isoformat() for d in ended)}) — 기준일 {px_date} 그대로 "
                           "(관문의 '끝난 거래일' 줄이 발행을 멈춰요)"))
        last = max(fb) if fb else None
        if last is not None:
            src["fb"] = px_src_counts(fb[last][1])
            src["fbDate"] = last.isoformat()
        return px_date, listing, {}, src, logs, (listing, {})
    pick = max(good)
    df, st = fb[pick]
    known = {d: fb[d][0] for d in fb if d < pick and len(fb[d][0])}
    src.update({"px": PX_SRC_FB, "date": pick.isoformat(), "fb": px_src_counts(st), "must": list(st["must"])})
    src["_one"] = dict(st.get("_one") or {})      # #161 리뷰 3차 A-S2: 내부 칸 (kr_same_day_reuse) — px_src_final 이 빼요
    src["knx"]["px"] = PX_SRC_KNX if st.get("knx") else None     # 코넥스 단계를 묻지 않았으면 그날 파일에 코넥스가 없어요
    src["days"] = {d.isoformat(): PX_SRC_FB for d in sorted(known) + [pick]}
    skipped = [d for d in ended if d > pick]
    nk = int((st.get("knx") or {}).get("kept") or 0)
    logs.append((bool(skipped), f"기준일: {pick} — 2차 출처 (다음 × 야후" + (f" · 코넥스 야후 × 네이버 {nk:,}" if st.get("knx") else "")
                 + f" · 확인된 {len(df):,}종목 · 1차 출처 최종본 {px_date})"
                 + (f" · 그 뒤 확인 못 한 끝난 거래일 {', '.join(d.isoformat() for d in skipped)} (관문이 멈춰요)" if skipped else "")))
    uni = st.get("_uni")
    return pick, df.copy(), known, src, logs, (uni if uni is not None else df, st.get("_daumShr") or {})


# ────────────────────────────────────────────────────────────
# 2026-11-19: 확인 못 한 국내 종목은 마지막 확인 종가로 (Jack)
# ────────────────────────────────────────────────────────────
# "The 129 unconfirmed stocks: stop showing "이 종목의 데이터를 찾지 못했어요." Show each stock's last confirmed close with its own date
#  (the existing own-close mechanism), plus "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." It must never sit under today's date
#  label without that line." (Jack, 2026-11-19)
# 2차 출처 날에 두 출처로 확인하지 못한 종목 (코넥스처럼 두 번째 출처가 없거나 · 다음과 야후가 다르거나 · 한쪽이 없음): 지난 발행본(data.json)에 그
# 종목이 있으면 그 발행본의 가격을 그대로 싣고 pxd = 그 종가의 날짜 (지난 발행본의 pxDate · 그 발행본도 이미 pxd 로 실었으면 같은 pxd · 같은 가격 —
# 날짜를 바꾸지 않아요). 오늘 다음 · 야후 값은 하나도 쓰지 않아요. d1 은 없어요 (미국 pxd 와 같아요). 그 가격으로 만든 시세 숫자 (시가총액 · 52주 ·
# 출렁임 · 베타 · 수익률 · 설명의 시가총액) 는 지난 발행본에서 그대로 옮겨요 — 그 종가까지 자른 시계열로 그날 만든 숫자예요. 재무 · 배당 · 점수 · 업종은
# 다른 종목처럼 오늘 다시 만들어요 (PER · PBR · 배당수익률은 그 가격으로). 점수(백분위)에는 미국 pxd 종목처럼 들어가요.
# 나이 상한 KR_OWN_CLOSE_MAX_DAYS (관문 파일): 그 종가 뒤 pxDate 까지 KOSPI 거래일이 이보다 많으면 싣지 않아요 (예전처럼 빠져요).
from validate_data import KR_OWN_CLOSE_MAX_DAYS, KR_OWN_WHY, KR_OWN_DROP_KEY, kr_own_close_bad, kr_own_age, kr_px_count, KR_MIN as GATE_KR_MIN
KR_OWN_KEYS = ("t", "nk", "ne", "cls", "s", "price", "vol", "beta", "al", "betaSE", "betaN", "cap", "val", "val20", "lo", "hi", "etf",
               "shr", "r1", "r3", "r36", "frn", "dk", "sh", "mdd", "hit", "mom", "pxBad", "pxBadF")
KR_OWN_DROP_KO = {"none": "지난 발행본에 없음", "same": "지난 발행본도 같은 기준일 (확인 못 한 오늘 종가는 쓰지 않아요)",
                  "old": f"그 종가 뒤 거래일 {KR_OWN_CLOSE_MAX_DAYS}일 넘음", "bad": "지난 발행본의 가격 · 날짜를 읽을 수 없음",
                  "jump": "과거 주가 기록 오류 표시인데 지난 발행본의 krSeries.jump 에 없음"}
KR_UNCONF_KO = {"mkt": "두 번째 출처 없음 (코넥스 등)", "conf": "다음 × 야후로 확인 못 함", "knx": "야후 .KQ × 네이버로 확인 못 함 (코넥스)"}
KR_UNCONF_WHY = ("mkt", "conf", "knx")
KR_OWN_SHOW = 30          # 로그 · dropEx 에 이름을 적는 종목 수


def kr_knx_left(px_src):
    """2026-11-20 (#159 × #158): 그날 코넥스 2차 출처 (야후 .KQ × 네이버) 를 물었는지와 확인하지 못한 코넥스 코드 (순수 함수).
    반환: (물었는지, 확인 못 한 코드 set 또는 None). 물었다 = pxSrc.knx.px 가 yahoo+naver (그날 코넥스 단계가 끝까지 돌았어요). 확인 못 한 코드는
    pxSrc.fb.knx.left (#158: 네이버 행 없음 · 값 못 믿음 · 야후 없음 · 다름 · 기준일 종가 다름 · 기준일로 맞춰 보지 못함). 물었는데 그 기록을
    읽을 수 없으면 None — 그때는 그날 파일에 없는 코넥스를 모두 확인 못 한 종목으로 봐요 (kr_unconfirmed)."""
    knx = px_src.get("knx") if isinstance(px_src, dict) else None
    if not isinstance(knx, dict) or knx.get("px") != PX_SRC_KNX:
        return False, None
    fb = px_src.get("fb") if isinstance(px_src.get("fb"), dict) else {}
    left = fb.get("knx").get("left") if isinstance(fb.get("knx"), dict) else None
    if not isinstance(left, list) or not all(isinstance(c, str) for c in left):
        return True, None
    return True, set(left)


def kr_unconfirmed(full_list, conf_codes, knx=(False, None)):
    """2차 출처 날: 그날 전체 목록에 있는데 두 출처로 확인하지 못한 종목 → {코드: (이름, 까닭)} (순수 함수).
    까닭: 'mkt' 두 번째 출처가 없는 시장 (그날 코넥스 단계를 묻지 않았거나 멈춘 날의 코넥스) · 'conf' 다음 × 야후로 확인 못 함 (다름 · 한쪽 없음 ·
    값을 못 믿음) · 'knx' (2026-11-20 · #158) 야후 .KQ × 네이버로 확인 못 한 코넥스 (pxSrc.fb.knx.left).
    knx: kr_knx_left 의 (물었는지, 확인 못 한 코넥스). 물은 날 그 목록에 없는 코넥스는 두 출처로 확인된 종목이에요 — 그날 파일에 있거나 (kept ·
    conf_codes), 평소 날 발행 기준(시가총액) 아래라 그날 파일에 넣지 않았어요 (capOut). 둘 다 확인 못 한 종목이 아니라서 빼요: 확인된 오늘 종가가
    있는데 '오늘 종가를 확인하지 못해서' 로 옛 종가를 싣지 않게. 목록을 읽을 수 없으면 (None) 그날 파일에 없는 코넥스는 모두 'knx'."""
    out = {}
    if full_list is None or "Code" not in full_list.columns:
        return out
    ran, left = knx if isinstance(knx, tuple) and len(knx) == 2 else (False, None)
    mk = full_list["Market"] if "Market" in full_list.columns else [None] * len(full_list)
    nm = full_list["Name"] if "Name" in full_list.columns else [""] * len(full_list)
    for c, m, n in zip(full_list["Code"].astype(str).str.strip(), mk, nm):
        if len(c) != 6 or c in conf_codes or c in out:
            continue
        if yahoo_knx_symbol(c, m):
            if ran and left is not None and c not in left:
                continue
            why = "knx" if ran else "mkt"
        else:
            why = "conf" if yahoo_kr_symbol(c, m) else "mkt"
        out[c] = (str(n) if isinstance(n, str) else "", why)
    return out


def kr_knx_carry_note(full_list, conf_codes, knx, unconf, px_src):
    """2026-11-20 (#159 × #158): 코넥스가 이 단계에서 어디로 갔는지 한 줄 (크게 남길지, 글) — 그날 파일 (두 출처 확인) · 확인됐지만 시가총액 기준
    아래 (capOut · 싣지 않아요) · 확인 못 함 (마지막 확인 종가 단계로). #158 의 기록 (pxSrc.fb.knx kept · capOut · left) 과 수가 다르면 크게."""
    ran, left = knx
    if full_list is None or "Code" not in full_list.columns or "Market" not in full_list.columns:
        return False, "코넥스: 그날 전체 목록을 읽을 수 없어요"
    allk = {c for c, m in zip(full_list["Code"].astype(str).str.strip(), full_list["Market"]) if len(c) == 6 and yahoo_knx_symbol(c, m)}
    inf = allk & set(conf_codes)
    unc = {c for c in allk if c in unconf}
    capo = allk - inf - unc
    if not ran:
        return bool(allk), (f"코넥스 {len(allk):,}종목: 그날 코넥스 2차 출처(야후 .KQ × 네이버)를 묻지 않았거나 멈췄어요 — 모두 확인 못 한 종목 "
                            f"({KR_UNCONF_KO['mkt']}) {len(unc):,} · 마지막 확인 종가 단계로")
    # 리뷰 (#159): pxSrc.fb · fb.knx 가 dict 가 아니면 읽을 수 없는 기록 — 멈추지 않고 (kr_knx_left 가 이미 None 을 줬어요) 크게 남겨요
    fb = px_src.get("fb") if isinstance(px_src, dict) and isinstance(px_src.get("fb"), dict) else {}
    fbk = fb.get("knx") if isinstance(fb.get("knx"), dict) else {}
    want = (fbk.get("kept"), fbk.get("capOut"), len(left) if left is not None else None)
    got = (len(inf), len(capo), len(unc))
    odd = left is None or want != got
    return odd, (f"코넥스 {len(allk):,}종목 (야후 .KQ × 네이버): 그날 파일 {len(inf):,} · 확인됐지만 시가총액 기준 아래라 싣지 않음 {len(capo):,} · "
                 f"확인 못 함 {len(unc):,} (마지막 확인 종가 단계로)"
                 + (" — !! pxSrc.fb.knx.left 를 읽을 수 없어 그날 파일에 없는 코넥스를 모두 확인 못 한 종목으로 봐요" if left is None else "")
                 + (f" — !! #158 기록과 다름 (kept · capOut · left {want})" if left is not None and want != got else ""))


def kr_own_close_carry(prev, unconf, px_date, trade_days, max_days=KR_OWN_CLOSE_MAX_DAYS):
    """확인 못 한 종목(unconf · kr_unconfirmed)을 지난 발행본(prev · data.json)의 마지막 확인 종가로 (2026-11-19 · Jack · 순수 함수).
    반환: (실을 종목들 [기록 — KR_OWN_KEYS + pxd], 과거 주가 기록 오류 종목의 지난 움직임 {코드: [[코드, 날짜, %, 이유]…]}, 싣지 못한 {코드: 까닭}).
    - 지난 발행본에 그 종목이 기준일 종가로 있었으면 그 가격 · pxd = 그 발행본의 pxDate. 이미 pxd 로 있었으면 같은 가격 · 같은 pxd (다시 날짜를 매기지 않아요).
    - 싣지 않아요 (예전처럼 빠져요): 지난 발행본에 없음 (none) · 그 날짜가 오늘 기준일보다 앞이 아님 (same · 오늘 확인 못 한 값을 오늘 날짜로 싣지 않아요) ·
      그 종가 뒤 pxDate 까지 거래일(trade_days: YYYY-MM-DD)이 max_days 보다 많음 (old) · 가격 · 날짜를 읽을 수 없음 (bad) · 과거 주가 기록 오류 표시인데
      지난 krSeries.jump 에 그 움직임이 없음 (jump — 오늘 관문이 표시와 움직임을 맞춰 봐요)."""
    prev = prev or {}
    pst = {str(x.get("t")): x for x in prev.get("stocks") or [] if isinstance(x, dict) and x.get("cls") == "kr" and not x.get("fund")}
    ppx = prev.get("pxDate")
    ppx = ppx if isinstance(ppx, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ppx) else None
    pj = collections.defaultdict(list)
    for j in ((prev.get("krSeries") or {}).get("jump") or []) if isinstance(prev.get("krSeries"), dict) else []:
        if isinstance(j, list) and len(j) == 4:
            pj[str(j[0])].append(list(j))
    today = px_date.isoformat()
    carried, jumps, drop = [], {}, {}
    for code in sorted(unconf):
        p = pst.get(code)
        if p is None:
            drop[code] = "none"
            continue
        own = p.get("pxd") if p.get("pxd") is not None else ppx
        try:
            ok_day = isinstance(own, str) and dt.date.fromisoformat(own).isoformat() == own
        except ValueError:
            ok_day = False
        price = _fin(p.get("price"))
        if not ok_day or (p.get("pxd") is not None and (ppx is None or own >= ppx)) or price is None or price <= 0:
            drop[code] = "bad"
            continue
        if own >= today:
            drop[code] = "same"
            continue
        if kr_own_age(own, today, trade_days) > max_days:
            drop[code] = "old"
            continue
        if p.get("pxBad") and not pj.get(code):
            drop[code] = "jump"
            continue
        rec = {k: p[k] for k in KR_OWN_KEYS if k in p}
        rec["pxd"] = own
        carried.append(rec)
        if p.get("pxBad"):
            jumps[code] = pj[code]
    return carried, jumps, drop


def log_kr_own_close(carried, drop, unconf, names):
    """마지막 확인 종가로 실은 종목 · 싣지 못한 종목을 크게 남기고 data.json pxSrc.own 을 돌려줘요 (2026-11-19). names: {코드: 이름}."""
    def nm(c):
        return f"{c} {names.get(c) or (unconf.get(c) or ('',))[0]}".strip()
    by_day = collections.Counter(r["pxd"] for r in carried)
    days = " · ".join(f"{d} {n}" for d, n in sorted(by_day.items(), reverse=True))
    cn = [f"{nm(r['t'])} ({r['pxd'][5:]})" for r in carried]
    why_u = collections.Counter(w for _, w in unconf.values())
    log(f"{'  !! ' if unconf else '· '}국내 종가 미확인 {len(unconf):,}종목 ("
        + " · ".join(f"{KR_UNCONF_KO[k]} {why_u[k]:,}" for k in KR_UNCONF_WHY if why_u[k]) + ")"
        + (f": 마지막 확인 종가로 실음 {len(carried):,}종목 (pxd {days}) — " + ", ".join(cn[:KR_OWN_SHOW])
           + (f" 외 {len(cn) - KR_OWN_SHOW}종목" if len(cn) > KR_OWN_SHOW else "") if carried else ": 마지막 확인 종가로 실은 종목 0"))
    dc = collections.Counter(drop.values())
    dn = [f"{nm(c)} ({KR_OWN_DROP_KO[w]} · {KR_UNCONF_KO[unconf[c][1]] if c in unconf else '?'})" for c, w in sorted(drop.items())]
    if drop:
        log(f"  !! 마지막 확인 종가로도 싣지 못한 국내 종목 {len(drop):,} (빠져요 · 앱은 '이 종목의 데이터를 찾지 못했어요', 나이 상한을 넘은 종목(old)은 "
            "'며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요.'): "
            + " · ".join(f"{KR_OWN_DROP_KO[k]} {v:,}" for k, v in sorted(dc.items())) + " — " + ", ".join(dn[:KR_OWN_SHOW])
            + (f" 외 {len(dn) - KR_OWN_SHOW}종목" if len(dn) > KR_OWN_SHOW else ""))
    return {"v": 1, "max": KR_OWN_CLOSE_MAX_DAYS, "n": len(carried), "codes": sorted(r["t"] for r in carried), "unconf": len(unconf),
            # 2026-11-20 (#159 × #158): 확인 못 한 종목의 까닭별 수 (mkt · conf · knx — 관문이 knx 를 #158 의 pxSrc.fb.knx.left 와 맞춰 봐요)
            "unconfWhy": {k: int(why_u[k]) for k in KR_UNCONF_WHY},
            "drop": {k: int(v) for k, v in sorted(dc.items())}, "dropEx": dn[:KR_OWN_SHOW], "bad": {"n": 0, "rows": []}}


def kr_own_aged(prev, unconf, drop):
    """2026-11-20 (Jack: "After 5 trading days, show "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요." instead of "데이터를 찾지
    못했어요""): 오늘도 확인 못 한 종목 중 마지막 확인 종가가 나이 상한을 넘어 잠시 뺀 종목 → [{t, nk, pxd}] (코드 순 · data.json pxSrc.own.aged ·
    앱이 그 종목 자리에 이 줄을 보여요). 지난 발행본에 있었는데 나이를 넘은 종목(drop 'old')과, 지난 발행본이 이미 잠시 뺀 종목(pxSrc.own.aged)
    중 오늘도 확인 못 한 종목 (지난 발행본의 stocks 에는 없어요 — drop 'none' 을 'old' 로 고쳐요). 오늘 확인된 종목 · 상장 폐지된 종목(그날 전체
    목록에 없음)은 unconf 에 없어서 저절로 빠져요. drop 을 고쳐요. (순수 함수)"""
    prev = prev or {}
    own = (prev.get("pxSrc") or {}).get("own") if isinstance(prev.get("pxSrc"), dict) else None
    was = {str(a["t"]): a for a in ((own or {}).get("aged") or []) if isinstance(own, dict) and isinstance(a, dict) and a.get("t")}
    pst = {str(x.get("t")): x for x in prev.get("stocks") or [] if isinstance(x, dict) and x.get("cls") == "kr"}
    ppx = prev.get("pxDate") if isinstance(prev.get("pxDate"), str) else None
    out = {}
    for c, w in sorted(drop.items()):
        if c not in unconf:
            continue
        if w == "old":
            p = pst.get(c) or {}
            out[c] = {"t": c, "nk": str(p.get("nk") or unconf[c][0] or c), "pxd": p.get("pxd") or ppx}
        elif w == "none" and c in was:
            a = was[c]
            out[c] = {"t": c, "nk": str(a.get("nk") or unconf[c][0] or c), "pxd": a.get("pxd")}
            drop[c] = "old"
    return [out[c] for c in sorted(out)]


def kr_own_aged_kept(prev, keep_out):
    """단계가 오류로 멈춘 날: 지난 발행본이 잠시 뺀 종목 중 오늘 확인된 종목(keep_out: 오늘 out 의 코드)이 아닌 것 그대로 (확인 못 한 종목을 셀 수
    없어서 · 상장 폐지는 다음 실행이 빼요). 이 함수도 멈추지 않아요 (못 읽으면 빈 목록)."""
    try:
        own = ((prev or {}).get("pxSrc") or {}).get("own") or {}
        return sorted((dict(a) for a in own.get("aged") or [] if isinstance(a, dict) and a.get("t") and str(a["t"]) not in keep_out),
                      key=lambda a: str(a["t"]))
    except Exception:
        return []


def kr_own_close_err(err, unconf_n=None):
    """마지막 확인 종가 단계가 오류로 멈췄을 때의 pxSrc.own (실은 종목 0 · err 에 까닭 — 관문이 경고해요). unconf_n: 확인 못 한 종목 수 — 그 수를
    세기 전에 멈췄으면 None 이고 칸을 빼요 (관문이 '모름'으로 적어요 · 0 으로 보이지 않게)."""
    out = {"v": 1, "max": KR_OWN_CLOSE_MAX_DAYS, "n": 0, "codes": [], "drop": {}, "dropEx": [], "bad": {"n": 0, "rows": []}, "err": str(err)[:300]}
    if isinstance(unconf_n, int):
        out["unconf"] = unconf_n
    return out


def kr_desc_set_ind(dk, ind):
    """설명(dk '업종 · 주요제품: … · 시장 상장 · 시가총액')의 업종 글자만 ind 로 바꾼 글 (ind 가 빈 글이면 업종 글자를 빼요 · 주요제품과 뒤쪽은 그대로).
    dk 가 비었으면 ind 만, 읽지 못하는 dk 면 None. (순수 함수 · validate_data.kr_desc_parse 로 다시 읽혀요)"""
    if dk in (None, ""):
        return ind or None
    p = kr_desc_parse(dk)
    if p is None:
        return None
    s = " · " + dk
    tail = s[KR_DESC_TAIL.search(s).start():]
    head = " · ".join(b for b in (ind, f"주요제품: {p[1]}" if p[1] else "") if b)
    return (head + tail) if head else (tail.removeprefix(" · ") or None)


def kr_own_ind_reset(carried, prev, desc=None):
    """2026-11-20 (리뷰 S1 · #146 과 같은 규칙): 마지막 확인 종가로 실은 종목의 업종 글자. 지난 발행본이 그 종목의 업종 글자를 DART 회사 정보로
    채웠거나(indSrc.dartT) 보통주를 따랐으면(indSrc.prefT) 그 글자를 그대로 옮기지 않아요 — kr_prev_desc 가 그런 종목을 KRX 글자처럼 이어 쓰지 않는
    것과 같아요: 오늘 KRX-DESC(desc)에 업종 글자가 있으면 그 글자로, 없으면 업종 글자를 빼서 오늘 다시 채우게 해요 (돌려준 코드를 업종 글자 없는
    종목 no_ind 에 더하면 main 의 kr_ind_fill 이 오늘 표로 채우고 indSrc.dartT · prefT 에 적어요 → 관문이 오늘 값을 확인하고, 다음 실행도 KRX 글자로
    잘못 이어 쓰지 않아요). 업종 키 s 도 그 글자로 다시 정해요 (map_sector_kr · 다른 종목과 같은 규칙). 그 밖의 종목은 그대로.
    rows(carried)를 고쳐요. 반환: (다시 채울 코드 · 오늘 KRX 글자로 바꾼 코드 · 설명을 읽지 못해 설명을 비운 코드)."""
    src = (prev or {}).get("indSrc") or {}
    filled = {str(t) for key in ("dartT", "prefT") if isinstance(src.get(key), dict) for t in src[key]}
    refill, krx, bad = [], [], []
    for r in carried:
        t = str(r.get("t"))
        if t not in filled:
            continue
        today = ((desc or {}).get(t) or ("", ""))[0]
        dk = kr_desc_set_ind(r.get("dk"), today or "")
        if dk is None and r.get("dk") not in (None, ""):
            bad.append(t)                     # 만든 방법상 생기지 않아요 (DART 채우기 · 우선주 따르기는 읽히는 글만 써요) — 설명을 비우고 다시 채워요
        p = kr_desc_parse(dk) if dk else ("", "")
        if dk is None:
            r.pop("dk", None)
        else:
            r["dk"] = dk
        r["s"] = map_sector_kr(p[0] if p else "", p[1] if p else "")
        (krx if today else refill).append(t)
    return refill, krx, bad


# 2026-11-21 (#161 · Jack: "Later runs update that day's data when more closes are confirmed."): 같은 기준일을 다시 도는 실행.
# 지난 발행본이 같은 기준일 (pxDate) 이고 그 발행본이 그 날짜의 종가로 실은 종목 (pxd 없음 · 두 출처 또는 KRX 최종본으로 확인된 종가) 을 이 실행이
# 확인하지 못했으면, 그 종가를 그대로 다시 써요 — 둘 다 그 날짜의 확인된 종가예요 (지우거나 마지막 확인 종가로 옮기지 않아요). #159 의
# kr_own_close_carry 는 같은 기준일 발행본에서 옮기지 않아요 ('same') — 그래서 여기서 따로, 크게 남기며 해요.
# 다시 쓰지 않는 종목 (잃은 종목 · lost): 지금 두 출처가 서로 달라요 (pxSrc.fb.diffT · 코넥스 fb.knx.diffT — 어느 쪽이 지난 값과 같은지 몰라요) ·
# 오늘 그날 전체 목록에 없어요 · 과거 주가 기록 오류 표시인데 지난 krSeries.jump 에 그 움직임이 없어요. 잃은 종목이 하나라도 있으면 이 실행은
# 지난 발행본보다 낫지 않아서 발행하지 않아요 (tools/publish_hold.py 가 pxSrc.own.reuse.lost 를 봐요).
def kr_same_day_rerun(prev, px_src, px_date, today=None):
    """같은 날 다시 도는 실행인지 (2026-11-21 · #161 리뷰 · 순수 함수): 이 실행과 지난 발행본이 모두 2차 출처 날이고 한국 기준일이 같아요 (발행한 날짜와
    상관없이 — 월요일에 금요일 데이터를 다시 도는 실행도). 반환: (참/거짓, 설명). 참이면 DART 를 부르지 않아요 (재무는 DART 보관본 · 공시는 미국 기준일도
    같고 같은 발행의 disc.json 일 때만 그대로 — main). today 는 쓰지 않아요 (예전 호출 모양)."""
    if not isinstance(prev, dict) or not isinstance(px_src, dict) or px_src.get("px") != PX_SRC_FB or px_date is None:
        return False, "2차 출처 날이 아니거나 지난 발행본이 없어요"
    psrc = prev.get("pxSrc") if isinstance(prev.get("pxSrc"), dict) else {}
    pd_ = px_date.isoformat() if isinstance(px_date, dt.date) else str(px_date)
    if psrc.get("px") != PX_SRC_FB or prev.get("pxDate") != pd_:
        return False, f"지난 발행본 (기준일 {prev.get('pxDate')}) 과 같은 기준일의 2차 출처 날이 아니에요"
    return True, f"같은 기준일을 다시 도는 실행 (기준일 {pd_} · 발행본 {prev.get('publishedAt')})"


def dart_cache_covers(meta, prev):
    """같은 기준일을 다시 도는 실행이 DART 를 부르지 않아도 되는지 (#161 리뷰 3차 A-S3 · 순수 함수). 불러온 DART 보관본의 meta.dartAt = 재무 · 공시를
    이 보관본의 값으로 만든 마지막 실행의 publishedAt (dart_cache_mark — DART 를 예전처럼 불렀거나 발행본을 덮는 보관본만 쓴 같은 날 실행 · DART 가
    멈춘 실행은 빼요). 그 값이 발행본
    (prev.publishedAt) 과 같거나 뒤면 (True, 설명) — 보관본에 발행본을 만든 실행 (또는 그 뒤 실행) 이 받은 값이 다 있어요. 아니면 (False, 설명):
    그 실행의 저장이 실패했거나, 더 앞의 보관본을 불러왔을 수 있어요 — 그 보관본으로 DART 를 부르지 않으면 재무가 발행본보다 옛 값으로 돌아갈 수 있어요."""
    at = (meta or {}).get("dartAt") if isinstance(meta, dict) else None
    pub = prev.get("publishedAt") if isinstance(prev, dict) else None
    try:
        a, p = dt.datetime.fromisoformat(str(at)), dt.datetime.fromisoformat(str(pub))
        if a.tzinfo is None or p.tzinfo is None:
            raise ValueError("시간대 없음")
    except (TypeError, ValueError):
        return False, f"DART 보관본이 어느 발행의 값인지 몰라요 (보관본 dartAt {at!r} · 발행본 publishedAt {pub!r})"
    if a >= p:
        return True, f"DART 보관본 (dartAt {at}) 이 발행본 ({pub}) 을 만든 실행 또는 그 뒤의 값이에요"
    return False, f"DART 보관본 (dartAt {at}) 이 발행본 ({pub}) 보다 앞의 값이에요 (그 실행의 보관본 저장이 실패했거나 더 앞의 보관본을 불러왔어요)"


def dart_cache_mark(client, published_at, env=None):
    """보관본에 dartAt = 이 실행의 publishedAt 을 적어요 (#161 리뷰 3차 A-S3): 이 실행의 재무 · 공시가 이 보관본의 값이에요 — DART 를 예전처럼
    불렀거나, 같은 날 다시 하는 실행이 발행본을 덮는 보관본 (dart_cache_covers) 만 썼어요. DART 가 이 실행 중 멈췄으면 (down · fatal) 적지 않아요 —
    그러면 다음 같은 날 실행은 DART 를 불러요 (크게). 시험 실행 (DRY_RUN) 도 적지 않아요 (#161 리뷰 4차 · kr_rerun_state 와 같게): 그 보관본도 main 의
    캐시로 저장되는데, 06:40 실제 실행과 겹친 시험 실행이 그 실행의 항목이 없는 보관본에 표시하면 뒤의 같은 날 실행이 DART 를 잘못 건너뛰어요."""
    env = os.environ if env is None else env
    if (env.get("DRY_RUN") or "").strip().lower() == "true":
        log("· 시험 실행이라 DART 보관본에 dartAt 을 적지 않아요 (실제 실행의 표시만 믿어요 · 같은 날 다시 하는 실행은 그 표시로 DART 를 건너뛸지 정해요)")
        return False
    if client.down or client.fatal:
        log(f"  !! DART 가 이 실행 중 멈췄어요 ({client.down or client.fatal}) — 보관본의 dartAt 을 고치지 않아요 (같은 날 다시 하는 실행은 DART 를 불러요)")
        return False
    client.meta["dartAt"] = published_at
    return True


def load_morning_disc(path=None, live=None):
    """같은 날 다시 도는 실행이 그대로 쓸 발행본의 disc.json (체크아웃의 파일 · 2026-11-21 · #161 리뷰). live: 지난 발행본 data.json — 주면 disc.json 이
    그 발행과 같은 발행 (publishedAt 같음 · 같은 커밋) 일 때만 써요. 반환: (dict 또는 None, 설명). disc.json 의 내용 날짜 (asOf · newest) 는 그대로라,
    그 뒤에 나온 공시는 다음 새 기준일 발행에 들어가요 (내용 날짜가 그만큼 오래됐다고 파일이 말해요)."""
    path = path or OUT_DISC
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        return None, f"아침 발행본의 {path} 를 읽지 못했어요 ({type(e).__name__})"
    if not isinstance(d, dict) or not all(isinstance(d.get(k), list) for k in ("insider", "nps")):
        return None, f"아침 발행본의 {path} 모양이 달라요"
    if isinstance(live, dict) and (d.get("publishedAt") is None or d.get("publishedAt") != live.get("publishedAt")):
        return None, f"{path} 가 지금 발행본과 다른 발행이에요 (disc {d.get('publishedAt')} · data {live.get('publishedAt')})"
    return d, f"발행본의 {path} (내부자 {len(d['insider']):,}건 · 공시 내용 날짜 {d.get('asOf')})"


# 2026-11-21 (#161 리뷰): 같은 날 다시 돌았는데 더 얻은 것이 없으면, 그 뒤 3시간 안의 정해진 시각 · 바깥 타이머 실행은 데이터를 모으지 않아요.
# 보관본 (.dart-cache/kr-rerun-v1.json · DART 캐시와 같이 보관) 에 그 실행의 날 · 기준일 · 미국 기준일 · 시각 · 늘어난 그 날짜 종가 국내 종목 수를 적어요.
# 2026-11-21 (#161 리뷰 2차): 그 기록은 실제 실행 (시험 실행 아님 · GitHub 실행 번호가 있는 실행) 만 남기고, 다음 실행은 그 실행이 초록으로 끝났을 때만
# (관문과 화면 검사를 통과 · GitHub 의 그 실행 결과 'success' — github_run_succeeded) 믿어요. 기록은 데이터 수집 단계 끝에 써서 DART 캐시와 같이
# 보관돼요 (그 단계 뒤의 관문 · 화면 검사 결과는 그때 아직 몰라요 — 그래서 다음 실행이 확인해요). 확인하지 못하면 쉬지 않고 돌아요.
KR_RERUN_STATE_PATH = os.environ.get("KR_RERUN_STATE", ".dart-cache/kr-rerun-v1.json")
KR_RERUN_QUIET = dt.timedelta(hours=3)
KR_RERUN_QUIET_FROM = dt.time(7, 0)          # 미국 종가 확정 (여름 05:30 · 겨울 06:30 KST) 뒤의 기록만
KR_RERUN_QUIET_BEFORE = dt.time(15, 30)      # 그날 한국 장이 끝나기 전에만 쉬어요 (그 뒤에는 새 거래일이 끝날 수 있어요)
#   (#161 리뷰 3차 nit: 고정 15:30 으로 둬요 — KRX 특별 거래시간 표는 마감을 늦출 수만 있어서 (KRX_CLOSE · 수능일 16:30), 15:30 은 늘 그날 마감과 같거나
#   앞이라 쉬는 창이 짧아지는 쪽 (안전한 쪽) 이에요. 그날 표를 읽으려면 이 순수 함수에 표를 넘겨야 해서 그대로 둬요.)
# #161 리뷰 3차 A-M1: 쉬는 실행은 data.json 을 새로 쓰지 않아 관문이 발행본을 그대로 봐요 — 관문의 'publishedAt 12시간 이내' (PUBLISHED_MAX_HOURS) 가
# 발행본의 나이로 실패해요 (월요일에 토요일 아침 발행본을 다시 돌 때 · 연휴 뒤). 그래서 발행본이 그 한도 − 1시간보다 오래됐으면 쉬지 않아요.
from validate_data import PUBLISHED_MAX_HOURS as GATE_PUBLISHED_MAX_HOURS
KR_RERUN_QUIET_PUB_AGE = dt.timedelta(hours=GATE_PUBLISHED_MAX_HOURS - 1)
QUIET_MARK = "baepsae-quiet.txt"             # 쉬는 실행이 RUNNER_TEMP 에 남기는 표시 (발행 판단 단계가 보고 감시에 중립인 보류로)


def kr_rerun_throttle(state, prev, now, auto=True, run_ok=None):
    """이 실행이 데이터 수집을 건너뛸지 (순수 함수). 반환: 까닭 글 또는 None (예전처럼 돌아요). 모두 맞아야 건너뛰어요:
    정해진 시각 · 바깥 타이머 실행 (auto) · 지난 발행본이 2차 출처 날 · 그 기록의 한국 · 미국 기준일 = 지난 발행본의 것 (발행한 날과 상관없이) ·
    그 실행이 그 날짜 종가 국내 종목을 하나도 늘리지 못함 (gain ≤ 0) · 그 실행과 지금이 같은 날 (KST) 07:00 ~ 15:30 안 (그 사이에는 새 한국 · 미국
    거래일이 끝나지 않아요) · 그 실행 뒤 3시간이 지나지 않음 · 그 실행이 초록으로 끝남 (run_ok(실행 번호) — 관문과 화면 검사를 통과했어요 ·
    run_ok 가 없거나 확인하지 못하면 쉬지 않아요) · 발행본 (prev.publishedAt) 이 KR_RERUN_QUIET_PUB_AGE (관문 한도 − 1시간) 보다 새로움 (#161 리뷰 3차
    A-M1: 쉬는 실행은 관문이 발행본을 그대로 봐요 — 오래된 발행본이면 'publishedAt 12시간 이내' 가 실패해 빨간 실행이 돼요. 그러면 돌아요)."""
    if not auto or not isinstance(state, dict) or state.get("v") != 1 or not isinstance(prev, dict):
        return None
    t = now.astimezone(KST)
    psrc = prev.get("pxSrc") if isinstance(prev.get("pxSrc"), dict) else {}
    try:
        at = dt.datetime.fromisoformat(str(state.get("at"))).astimezone(KST)
        pub = dt.datetime.fromisoformat(str(prev.get("publishedAt")))
        if pub.tzinfo is None:
            return None
    except (TypeError, ValueError):
        return None
    if not dt.timedelta(0) <= t - pub < KR_RERUN_QUIET_PUB_AGE:
        return None
    gain = state.get("gain")
    if (psrc.get("px") != PX_SRC_FB or state.get("pxDate") != prev.get("pxDate") or state.get("usPxDate") != prev.get("usPxDate")
            or not isinstance(gain, int) or isinstance(gain, bool) or gain > 0
            or at.date() != t.date() or at.time() < KR_RERUN_QUIET_FROM or t.time() >= KR_RERUN_QUIET_BEFORE
            or not dt.timedelta(0) <= t - at < KR_RERUN_QUIET):
        return None
    run_id = state.get("run")
    if run_ok is None or not isinstance(run_id, (int, str)) or not str(run_id).isdigit() or run_ok(str(run_id)) is not True:
        return None
    left = KR_RERUN_QUIET - (t - at)
    return (f"같은 기준일을 다시 도는 실행이에요: {at:%H:%M} KST 실행 ({run_id} · 초록) 이 그 날짜 종가 국내 종목을 늘리지 못했어요 (늘어난 수 {gain}) — 3시간이 지나기 "
            f"전이라 ({int(left.total_seconds() // 60)}분 남음) 데이터를 모으지 않아요 (발행본 그대로 · 감시에 중립 · 다음 실행이 다시 봐요)")


def github_run_succeeded(run_id, get=None):
    """GitHub 의 그 매일 실행이 초록 (success) 으로 끝났는지 — 공개 저장소의 실행 결과를 토큰 없이 읽어요 (이 job 의 토큰은 실행 기록을 읽을 권한이
    없어요). 못 읽으면 None (그러면 쉬지 않아요)."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    try:
        r = (get or requests.get)(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", headers={"Accept": "application/vnd.github+json"},
                                  timeout=15)
        if r.status_code != 200:
            log(f"  !! 앞선 실행 {run_id} 의 결과를 읽지 못했어요 (HTTP {r.status_code}) → 쉬지 않고 돌아요")
            return None
        js = r.json()
        return js.get("status") == "completed" and js.get("conclusion") == "success"
    except Exception as e:
        log(f"  !! 앞선 실행 {run_id} 의 결과를 읽지 못했어요 ({type(e).__name__}) → 쉬지 않고 돌아요")
        return None


def kr_rerun_state(prev, payload, now, n_now=None, n_prev=None, env=None):
    """이 실행이 같은 기준일을 다시 돈 결과 (보관본에 적어요 · 순수 함수). 시험 실행 · GitHub 실행 번호가 없는 실행 · 같은 기준일이 아닌 실행은 None
    (쓰지 않아요 — 시험 실행이 실제 실행을 쉬게 하지 않게)."""
    env = os.environ if env is None else env
    if (env.get("DRY_RUN") or "").strip().lower() == "true" or not str(env.get("GITHUB_RUN_ID") or "").isdigit():
        return None
    same = (isinstance(prev, dict) and prev.get("pxDate") == payload.get("pxDate") and prev.get("usPxDate") == payload.get("usPxDate")
            and ((prev.get("pxSrc") or {}).get("px") if isinstance(prev.get("pxSrc"), dict) else None) == PX_SRC_FB
            and ((payload.get("pxSrc") or {}).get("px") if isinstance(payload.get("pxSrc"), dict) else None) == PX_SRC_FB)
    if not same or not isinstance(n_now, int) or not isinstance(n_prev, int):
        return None
    t = now.astimezone(KST)
    return {"v": 1, "at": t.isoformat(timespec="seconds"), "pxDate": payload.get("pxDate"), "usPxDate": payload.get("usPxDate"),
            "gain": n_now - n_prev, "run": str(env.get("GITHUB_RUN_ID"))}


def quiet_mark(why):
    """쉬는 실행의 표시를 RUNNER_TEMP 에 남겨요 (발행 판단 단계가 '쉼' 으로 감시에 중립인 보류를 해요). RUNNER_TEMP 가 없으면 (로컬) 남기지 않아요."""
    d = os.environ.get("RUNNER_TEMP")
    if d:
        with open(os.path.join(d, QUIET_MARK), "w", encoding="utf-8") as f:
            f.write(why + "\n")


def kr_rerun_state_load(path=None):
    try:
        with open(path or KR_RERUN_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        log(f"  !! 같은 날 다시 하기 보관본을 읽지 못했어요 ({type(e).__name__}) → 쉬지 않고 돌아요")
        return None


KR_REUSE_KEYS = KR_OWN_KEYS + ("d1", "d1Why", "noTrade", "ntD1")
KR_REUSE_LOST_KO = {"clash": "지금 두 출처가 서로 다름", "clash1": "지금 한 출처만 종가를 줬는데 지난 발행본의 종가와 다름", "gone": "오늘 그날 전체 목록에 없음", "jump": "과거 주가 기록 오류 표시인데 지난 krSeries.jump 에 없음",
                    "konex": "코넥스 (이 실행의 두 출처 확인 · 보관본으로만 실어요 — 관문의 코넥스 줄이 그날 넣은 수로 맞춰 봐요)",
                    "room": "이 실행의 두 출처 확인 수보다 많이 실을 수 없음 (관문: 확인 종목 수 ≥ 발행한 국내 종목 수)"}


def _one_close(one, c):
    """kr_fb_one_source 의 그 종목 종가 (없거나 모양이 다르면 None)."""
    v = one.get(c) if isinstance(one, dict) else None
    return _fin(v[1]) if isinstance(v, (list, tuple)) and len(v) == 2 else None


def kr_same_day_reuse(prev, unconf, conf_codes, px_date, px_src, room=None):
    """같은 기준일 지난 발행본의 확인 종가 다시 쓰기 (2026-11-21 · #161 · 순수 함수).
    prev: 지난 발행본 data.json · unconf: 이 실행이 확인 못 한 종목 {코드: (이름, 까닭)} (kr_unconfirmed) · conf_codes: 이 실행이 확인한 코드 ·
    px_date: 이 실행의 기준일 · px_src: 이 실행의 pxSrc (fb.diffT · fb.knx.diffT · _one 한 출처만 준 종가 — 지난 발행본 종가와 다르면 'clash1') · room: 다시 쓸 수 있는 종목 수의 상한 (None 이면 없음) —
    관문은 2차 출처 날 '두 출처 확인 수 (pxSrc.fb.conf) ≥ 발행한 그 날짜 종가 종목 수' 를 봐요 (validate_data.px_alt_confirms). 다시 쓴 종목도
    그 날짜 종가라 그 수에 들어가니, 이 실행의 확인 수를 넘지 않게 시가총액 큰 종목부터만 다시 쓰고 나머지는 잃은 종목 'room' 이에요 (그 줄은 그대로).
    반환: (다시 쓸 종목 [기록 — KR_REUSE_KEYS · pxd 없음], 과거 주가 기록 오류 종목의 지난 움직임 {코드: [...]}, 잃은 종목 {코드: 까닭},
    pxSrc.own.reuse 기록 또는 None (지난 발행본이 다른 기준일이면 None — 같은 날 다시 도는 실행이 아니에요))."""
    prev = prev if isinstance(prev, dict) else {}
    today = px_date.isoformat()
    if prev.get("pxDate") != today:
        return [], {}, {}, None
    pst = {str(x.get("t")): x for x in prev.get("stocks") or [] if isinstance(x, dict) and x.get("cls") == "kr" and not x.get("fund")}
    earlier = {c for c, x in pst.items() if x.get("pxd") is None and (_fin(x.get("price")) or 0) > 0}
    fb = (px_src or {}).get("fb") if isinstance((px_src or {}).get("fb"), dict) else {}
    fbk = fb.get("knx") if isinstance(fb.get("knx"), dict) else {}
    clash = {str(c) for c in (fb.get("diffT") or []) + (fbk.get("diffT") or [])}
    one = (px_src or {}).get("_one") if isinstance((px_src or {}).get("_one"), dict) else {}     # #161 리뷰 3차 A-S2: 한 출처만 준 종가
    pj = collections.defaultdict(list)
    for j in ((prev.get("krSeries") or {}).get("jump") or []) if isinstance(prev.get("krSeries"), dict) else []:
        if isinstance(j, list) and len(j) == 4:
            pj[str(j[0])].append(list(j))
    conf = {str(c) for c in conf_codes}
    reused, jumps, lost = [], {}, {}
    for c in sorted(earlier - conf):
        p = pst[c]
        if c not in unconf:
            lost[c] = "gone"
        elif unconf[c][1] != "conf":                # 코넥스 (knx · mkt): 그날 파일의 코넥스는 이 실행이 확인한 것만 (pxSrc.knx.t · fb.knx.kept 와 같게)
            lost[c] = "konex"
        elif c in clash:
            lost[c] = "clash"
        elif _one_close(one, c) is not None and abs(_one_close(one, c) - (_fin(p.get("price")) or 0)) > KR_FB_CLOSE_TOL:
            lost[c] = "clash1"                      # 한 출처뿐이어도 지난 발행본과 다르면 그 종가를 믿을 수 없어요 (다시 쓰지 않아요 · 크게)
        elif p.get("pxBad") and not pj.get(c):
            lost[c] = "jump"
        else:
            reused.append({k: p[k] for k in KR_REUSE_KEYS if k in p})
    if room is not None and len(reused) > max(room, 0):
        reused.sort(key=lambda r: (-(_fin(r.get("cap")) or 0), str(r["t"])))
        for r in reused[max(room, 0):]:
            lost[r["t"]] = "room"
        reused = reused[:max(room, 0)]
    for r in reused:
        if pst[r["t"]].get("pxBad"):
            jumps[r["t"]] = pj[r["t"]]
    reused.sort(key=lambda r: str(r["t"]))
    names = {c: str(pst[c].get("nk") or (unconf.get(c) or ("",))[0] or "") for c in earlier}
    kk = sum(1 for r in reused if (unconf.get(r["t"]) or ("", ""))[1] == "conf")
    rec = {"v": 1, "from": str(prev.get("publishedAt") or ""), "earlier": len(earlier), "n": len(reused), "kk": kk,
           "codes": sorted(r["t"] for r in reused), "lost": len(lost),
           "lostEx": [f"{c} {names.get(c, '')} ({KR_REUSE_LOST_KO[w]})".replace("  ", " ") for c, w in sorted(lost.items())][:KR_OWN_SHOW]}
    return reused, jumps, lost, rec


def log_kr_same_day_reuse(rec):
    """같은 날 다시 쓰기 한 줄 (크게 남겨요 — 같은 날 다시 도는 실행은 드물고, 잃은 종목이 있으면 발행하지 않아요)."""
    if rec is None:
        return
    log(f"  !! 같은 기준일을 다시 도는 실행 (지난 발행본 {rec['from'] or '?'}): 그 발행본이 그 날짜 종가로 실은 국내 종목 {rec['earlier']:,} 중 이 실행이 "
        f"확인하지 못한 종목의 종가를 지난 발행본에서 다시 씀 {rec['n']:,}종목 (코스피 · 코스닥 {rec['kk']:,} · 둘 다 그 날짜의 확인 종가)"
        + (f" — 잃은 종목 {rec['lost']:,} (이 실행은 지난 발행본보다 낫지 않아 발행하지 않아요): " + ", ".join(rec["lostEx"]) if rec["lost"] else
           " — 잃은 종목 0"))


def kr_own_close_step(prev, full_list, conf_codes, px_src, px_date, trade_days, out, krs, prod_map, desc=None, no_ind=None):
    """2차 출처 날의 마지막 확인 종가 단계 (2026-11-19 · fetch_korea 가 부르는 한 곳). 그날 전체 목록(full_list · DataFrame)에서 두 출처로 확인 못 한
    종목을 골라(kr_unconfirmed) 지난 발행본의 마지막 확인 종가로 out 에 더하고, 과거 주가 기록 오류 표시의 지난 움직임을 krs(krSeries)에 · 주요제품을
    prod_map 에 옮기고, px_src["own"] 에 기록해요. trade_days: KOSPI 일봉 날짜들 (Timestamp · date · 'YYYY-MM-DD' 아무거나).
    2026-11-20 (리뷰 S1): 지난 발행본이 DART 로 채운 · 보통주를 따른 업종 글자는 kr_own_ind_reset 으로 (desc: 오늘 KRX-DESC {코드: (업종, 주요제품)} ·
    no_ind: 업종 글자 없는 종목 목록 — 다시 채울 코드를 더해요 · 없으면(None) 업종 글자를 그대로 둬요).
    이 단계의 어떤 오류도 발행을 멈추지 않아요 (Jack 의 규칙 · 2026-11-19 시험 실행이 여기서 멈췄어요): 크게 남기고, 아무것도 싣지 않고 (예전처럼 확인 못 한
    종목은 빠져요), 바꾼 것을 되돌리고, px_src["own"].err 에 까닭을 적어요 (관문이 경고해요). 반환: 실은 종목 수."""
    n0, jump0, hid0 = len(out), list((krs or {}).get("jump") or []), list((krs or {}).get("hidden") or [])
    ni0 = list(no_ind) if isinstance(no_ind, list) else None
    added, unconf = [], None
    try:
        days = [pd.Timestamp(t).date().isoformat() for t in trade_days]
        conf = set(map(str, conf_codes))
        knx = kr_knx_left(px_src)          # 2026-11-20 (#158): 야후 .KQ × 네이버로 확인된 코넥스는 확인 못 한 종목이 아니에요
        unconf = kr_unconfirmed(full_list, conf, knx)
        loud, txt = kr_knx_carry_note(full_list, conf, knx, unconf, px_src)
        log(f"  !! {txt}" if loud else f"· {txt}")
        have = {r.get("t") for r in out}
        # 2026-11-21 (#161): 같은 기준일 지난 발행본의 확인 종가를 먼저 다시 써요 (나머지만 마지막 확인 종가 단계로)
        fbc = (px_src.get("fb") or {}).get("conf") if isinstance(px_src.get("fb"), dict) else None
        n_px = sum(1 for r in out if r.get("cls") == "kr" and not r.get("fund") and r.get("pxd") is None)
        room = fbc - n_px if isinstance(fbc, int) and not isinstance(fbc, bool) else 0      # 기록을 읽지 못하면 다시 쓰지 않아요 (잃은 종목 → 발행 안 함)
        reused, rjumps, _, rrec = kr_same_day_reuse(prev, {c: v for c, v in unconf.items() if c not in have}, conf, px_date, px_src, room=room)
        log_kr_same_day_reuse(rrec)
        have |= {r["t"] for r in reused}
        carried, cjumps, cdrop = kr_own_close_carry(prev, {c: v for c, v in unconf.items() if c not in have}, px_date, days)
        aged = kr_own_aged(prev, unconf, cdrop)
        rec = log_kr_own_close(carried, cdrop, unconf, {r["t"]: r.get("nk", "") for r in carried})
        rec["aged"] = aged
        if rrec is not None:
            rec["reuse"] = rrec         # 2026-11-21 (#161): unconf · unconfWhy 는 이 실행이 확인 못 한 수 그대로 (다시 쓴 종목 포함 · 관문의 코넥스 비교와 같게)
        if aged:
            log(f"  !! 마지막 확인 종가가 {KR_OWN_CLOSE_MAX_DAYS}거래일을 넘어 잠시 뺀 국내 종목 {len(aged):,} (앱은 '며칠째 종가를 확인하지 못해서 이 종목은 "
                f"잠시 빼 두었어요.' · pxSrc.own.aged · 다시 확인되거나 목록에서 사라지면 빠져요): "
                + ", ".join(f"{a['t']} {a['nk']} ({a.get('pxd')})" for a in aged[:KR_OWN_SHOW])
                + (f" 외 {len(aged) - KR_OWN_SHOW}종목" if len(aged) > KR_OWN_SHOW else ""))
        # 리뷰 (2026-11-20): 다시 채울 목록(no_ind)을 받지 않은 호출은 업종 글자를 건드리지 않아요 — 다시 채우지 않고 글자만 빼는 일이 없게
        refill, krx, unread = kr_own_ind_reset(carried, prev, desc) if isinstance(no_ind, list) else ([], [], [])
        if refill or krx or unread:
            nm = {r["t"]: r.get("nk", "") for r in carried}
            log(f"{'  !! ' if unread else '· '}마지막 확인 종가 종목의 업종 글자: 지난 발행본이 DART 회사 정보로 채웠거나 보통주를 따른 "
                f"{len(refill) + len(krx):,}종목은 그 글자를 옮기지 않아요 — 오늘 다시 채움 {len(refill):,} · 오늘 KRX 글자로 {len(krx):,}"
                + (f" · 설명을 읽지 못해 비움 {len(unread):,}" if unread else "") + " — "
                + ", ".join(f"{t} {nm.get(t, '')}" for t in (refill + krx)[:KR_OWN_SHOW]))
            rec["ind"] = {"refill": len(refill), "krx": len(krx), "unread": len(unread)}
            no_ind.extend(t for t in refill if t not in no_ind)
        out.extend(reused + carried)
        for c in sorted({**rjumps, **cjumps}):
            krs["jump"] = list(krs.get("jump") or []) + ({**rjumps, **cjumps})[c]
            krs["hidden"] = list(krs.get("hidden") or []) + [c]
        for r in reused + carried:
            dp = kr_desc_parse(r.get("dk"))
            if dp and dp[1] and r["t"] not in prod_map:
                prod_map[r["t"]] = dp[1]
                added.append(r["t"])
        px_src["own"] = rec
        return len(carried)
    except Exception as e:
        del out[n0:]
        if isinstance(krs, dict):
            krs["jump"], krs["hidden"] = jump0, hid0
        for t in added:
            prod_map.pop(t, None)
        if ni0 is not None:
            no_ind[:] = ni0
        err = f"{type(e).__name__}: {str(e)[:200]}"
        log(f"  !! 마지막 확인 종가 단계가 오류로 멈췄어요 ({err}) — 확인 못 한 국내 종목은 예전처럼 빼고 발행을 이어가요 (실은 종목 0 · "
            "pxSrc.own.err · 관문이 경고해요)")
        px_src["own"] = kr_own_close_err(err, len(unconf) if isinstance(unconf, dict) else None)
        px_src["own"]["aged"] = kr_own_aged_kept(prev, {str(r.get("t")) for r in out})
        return 0


def kr_count_line(payload):
    """발행하는 국내 종목 수 한 줄 (2026-11-20 · #159 리뷰): pxDate 종가로 실은 종목 · 마지막 확인 종가(pxd)로 실은 종목 — 관문의 '국내 종목 수' 두
    줄은 앞의 수만 세요 (validate_data.kr_px_count · 바닥 KR_MIN). 바닥 아래면 크게. (순수 함수)"""
    n_px = kr_px_count(payload)
    n_all = sum(1 for s in payload.get("stocks", []) if s.get("cls") == "kr" and not s.get("fund"))
    return (f"{'  !! ' if n_px < GATE_KR_MIN else '· '}발행하는 국내 종목 {n_all:,}: pxDate 종가 {n_px:,} · 마지막 확인 종가 {n_all - n_px:,} "
            f"(관문 '국내 종목 수' 는 pxDate 종가만 세요 · 바닥 {GATE_KR_MIN:,})")


def kr_own_prune_series(krs, gone):
    """뺀 마지막 확인 종가 종목의 과거 주가 기록 오류 표시를 krSeries 에서도 빼요 (리뷰 N4): hidden 과, 실을 때 옮겨 온 그 종목의 jump 줄 (그 종목은
    오늘 목록 파일에 없어서 오늘 시계열 점검의 jump 에는 없어요)."""
    if not isinstance(krs, dict) or not gone:
        return
    if isinstance(krs.get("hidden"), list):
        krs["hidden"] = [c for c in krs["hidden"] if c not in gone]
    if isinstance(krs.get("jump"), list):
        krs["jump"] = [j for j in krs["jump"] if not (isinstance(j, list) and j and j[0] in gone)]


def kr_own_close_drop_all(kr, src, krs, err, drop_out=None):
    """마지막 확인 종가 점검(kr_own_close_final)이 오류로 멈췄을 때: 국내 pxd 종목을 모두 빼고 (예전처럼 확인 못 한 종목은 빠져요) 크게 남기고 pxSrc.own 에
    err · 뺀 수를 적어요 (관문이 경고해요). drop_out (2026-11-20): 주면 뺀 종목 (코드, 까닭) 을 더해요 (data.json ownDrop.krOwn).
    반환: 남은 국내 종목 목록."""
    gone = {s.get("t") for s in kr if s.get("cls") == "kr" and s.get("pxd") is not None}
    if isinstance(drop_out, list):
        drop_out.extend((str(t), f"err {str(err)[:120]}") for t in sorted(gone, key=str))
    log(f"  !! 마지막 확인 종가 점검이 오류로 멈췄어요 ({err}) — 마지막 확인 종가로 실은 {len(gone):,}종목을 모두 빼고 발행을 이어가요 (pxSrc.own.err)")
    if isinstance(src, dict):
        own = src.get("own") if isinstance(src.get("own"), dict) else kr_own_close_err(err)
        own.update({"codes": [], "n": 0, "err": str(err)[:300], "bad": {"n": len(gone), "rows": sorted(gone)[:KR_OWN_SHOW]}})
        src["own"] = own
    kr_own_prune_series(krs, gone)
    return [s for s in kr if s.get("t") not in gone or s.get("cls") != "kr"]


def kr_own_close_final(kr, src, prev, days, krs=None, drop_out=None):
    """국내 시세 단계 바로 뒤 · 다른 단계보다 먼저 (Jack 의 규칙, 2026-11-19 — 우리 처리의 한 줄이 틀리면 그 줄을 빼고 크게 남기고 나머지는 발행해요.
    이 함수가 보는 칸은 그 뒤 바뀌지 않아요 — 뺀 종목이 집계 · 점수 · corp.json 에 남지 않게 여기서 빼요): 관문과 같은 함수
    (validate_data.kr_own_close_bad)로 마지막 확인 종가 종목을 다시 보고, 맞지 않는 종목은 빼요 (pxd 가 맞지 않는 가격은 싣지 않아요 — 그 종목은
    예전처럼 빠져요). src: 발행할 pxSrc (own 을 고쳐요) · prev: 지난 발행본 · days: 거래일 YYYY-MM-DD 들 · krs: data.json krSeries (뺀 종목을
    hidden 에서도 빼요 — 표시한 종목 = hidden). 반환: 남은 국내 종목 목록."""
    if not any(s.get("pxd") is not None for s in kr if s.get("cls") == "kr"):
        if isinstance((src or {}).get("own"), dict):
            log("· 마지막 확인 종가 점검 (관문과 같은 함수): 0종목 빼고 발행")
        return kr
    bad = kr_own_close_bad({"pxDate": src.get("date") if isinstance(src, dict) else None, "pxSrc": src, "stocks": kr}, prev, days)
    gone = collections.defaultdict(list)
    for t, w in bad:
        gone[t].append(w)
    names = {s.get("t"): s.get("nk", "") for s in kr}
    rows = [f"{t} {names.get(t, '')} ({' · '.join(KR_OWN_WHY.get(w, w) for w in ws)})" for t, ws in sorted(gone.items())]
    log(f"{'  !! ' if gone else '· '}마지막 확인 종가 점검 (관문과 같은 함수): {len(gone):,}종목 빼고 발행" + (" — " + ", ".join(rows[:KR_OWN_SHOW]) if rows else ""))
    if not gone:
        return kr
    own = src.get("own") if isinstance(src, dict) and isinstance(src.get("own"), dict) else None
    if own is not None:
        own["codes"] = [c for c in own.get("codes") or [] if c not in gone]
        own["n"] = len(own["codes"])
        # 2026-11-20 (리뷰 4): 까닭(점검)마다 뺀 수 — 관문은 한 점검에서 5개를 넘을 때만 실패해요 (Jack 의 상시 규칙). 한 종목이 두 점검에 걸리면 둘 다 세요
        own["bad"] = {"n": len(gone), "rows": rows[:KR_OWN_SHOW], "why": dict(sorted(collections.Counter(w for ws in gone.values() for w in set(ws)).items()))}
    if isinstance(drop_out, list):          # 2026-11-20: data.json ownDrop.krOwn (다른 우리 처리 검사와 같은 곳 · 같은 모양 {n, rows [코드, 까닭]})
        drop_out.extend((str(t), " · ".join(KR_OWN_WHY.get(w, w) for w in ws)) for t, ws in sorted(gone.items()))
    kr_own_prune_series(krs, gone)
    return [s for s in kr if not (s.get("cls") == "kr" and s.get("t") in gone)]


# ────────────────────────────────────────────────────────────
# 2026-11-20: 야후 종가가 없는 미국 종목도 마지막 확인 종가로 (Jack)
# ────────────────────────────────────────────────────────────
# "Also: US stocks carry like Korean ones. A US stock with no close from Yahoo carries its last confirmed close with its own date and
#  the same line. Block only if many are missing (set the number from history), so a Yahoo gap never stops the Korean data again."
#  (Jack, 2026-11-20)
# 미국 기준일(usPxDate · S&P 500 의 마지막 끝난 봉) 종가가 야후에 없는 종목 (빈 값 · 무한 · 0 · 음수 봉은 종가가 없는 것으로 봐요 · 가격을 하나도
# 받지 못함 · 받다가 오류): 지난 발행본(data.json)에 그 종목이 기준일 종가로 있었으면 그 가격을 그대로 싣고 pxd = 그 발행본의 usPxDate · pxc = true
# (마지막 확인 종가 표시 — 야후가 그 종목의 마지막 봉을 자기 날짜로 준 '거래 정지' pxd 와 앱 · 관문이 구별해요). 지난 발행본도 pxc 로 실었으면 같은
# 가격 · 같은 pxd (날짜를 바꾸지 않아요). 그 가격으로 만든 시세 숫자(US_OWN_KEYS: 출렁임 · 베타 · 52주 · 샤프 · 최대낙폭 · 상승 월 · 모멘텀)는 지난
# 발행본에서 그대로 옮기고, 상세 정보(이름 · 업종 · PER · PBR · 시가총액 · 배당수익률)는 다른 종목처럼 오늘 그 가격으로 붙여요 (apply_us_info).
# 지난 발행본의 usPxDate 가 오늘과 같으면 (같은 날 다시 발행 · 2026-11-20 의 시험 실행들이 이랬어요) 그 종목의 그날 종가와 d1 을 그대로 실어요
# (그날의 확인된 종가예요 · pxd 없음 · usSrc.own.same). 나이 상한 US_OWN_CLOSE_MAX_DAYS (관문 파일): 그 종가 뒤 usPxDate 까지 미국 거래일(S&P 500
# 일봉)이 이보다 많으면 싣지 않고 빼요 (usSrc.own.aged · 앱은 '며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요.').
# 지난 발행본에 없거나 (새 종목) · 지난 발행본에서도 자기 날짜(pxd · pxc 없음)였거나 · 값을 읽을 수 없으면 예전 그대로예요: 야후의 마지막 봉이 있으면 그
# 날짜(pxd)로 · 없으면 빠져요. 이 단계의 어떤 오류도 발행을 멈추지 않아요 (그때는 예전 그대로).
# 2026-11-22 (Jack): 새 종목(지난 발행본의 미국 종목에도 usSrc.own.aged 에도 없는 티커)은 이 단계 앞에서 빠져요 — 미국 기준일 종가가 확인될 때까지
# 넣지 않아요 (us_new_wait_step · usSrc.newWait). 그래서 drop 'none' 은 기다리지 않는 새 티커에만 남아요: 지난 발행본이 일부러 뺀 티커
# (usLeftOut — 우선주 · 한국 종목 상장분 · 깨진 봉) · 지난 발행본을 읽지 못했거나 미국 종목 행이 없는 날 · 그 단계가 오류로 멈춘 날.
from validate_data import US_OWN_CLOSE_MAX_DAYS, US_OWN_WHY, us_own_close_bad
US_OWN_KEYS = ("price", "vol", "beta", "al", "betaSE", "betaN", "lo", "hi", "sh", "mdd", "hit", "mom")
US_OWN_DROP_KO = {"none": "지난 발행본에 없음 (예전처럼 야후의 마지막 봉 · 없으면 빠짐)",
                  "halted": "지난 발행본에서도 자기 날짜(pxd)로 실림 · 마지막 확인 종가가 아님 (예전처럼 야후의 마지막 봉)",
                  "old": f"그 종가 뒤 미국 거래일 {US_OWN_CLOSE_MAX_DAYS}일 넘음 (빼요)",
                  "bad": "지난 발행본의 가격 · 날짜를 읽을 수 없음 (예전처럼 야후의 마지막 봉)",
                  "split": "그 종가 날짜 뒤에 주식 분할이 있음 (예전처럼 야후의 자기 날짜 봉 · 없으면 빠짐 · usSrc.own.split)",
                  "splitRead": "오늘 다운로드의 분할 칸을 읽지 못함 (분할을 몰라 예전처럼 야후의 자기 날짜 봉 · 없으면 빠짐 · usSrc.own.split)"}
US_NOCL_KO = {"bar": "기준일 종가 없음 (빈 값 · 0 · 음수)", "empty": "쓸 수 있는 가격이 하나도 없음", "err": "시세를 받다가 오류"}
US_OWN_SHOW = 30
# 리뷰 (2026-11-20): 야후 상세 정보 중 그 가격에 맞추는 숫자 (apply_us_info) — 기준 가격을 모르면 비워요
US_PX_ANCHORED = ("per", "pbr", "cap", "dy", "pbrZero")
US_QUOTE_FAR = 0.5        # 리뷰 (2026-11-20, 4): 야후 시세 가격이 실은 종가와 이보다 많이 다르면 기준 가격으로 쓰지 않아요 (보관본 · 없으면 비움)
US_OWN_AGED_LONG = 20     # 리뷰 (2026-11-20): 잠시 뺀 기록이 이 미국 거래일보다 오래되면 크게 적어요 (상장 폐지된 티커가 목록에 남은 것일 수 있어요 · 로그만)


def us_px_tail_clean(px):
    """끝에 붙은 쓸 수 없는 종가(무한 · 0 · 음수 — 야후가 빈 값을 0 으로 주는 날)를 떼요: 그날은 그 종목의 야후 종가가 없는 날이에요 (2026-11-20 ·
    0 종가가 가격 0 인 행으로 나가지 않게 — 관문의 EXTRA_US · 주식 종류 티커 줄이 가격 없는 행으로 봐요). 가운데의 봉은 그대로 (순수 함수)."""
    n = len(px)
    while n:
        v = px.iloc[n - 1]
        try:
            ok = math.isfinite(float(v)) and float(v) > 0
        except (TypeError, ValueError):
            ok = False
        if ok:
            break
        n -= 1
    return px if n == len(px) else px.iloc[:n]


def us_own_close_carry(prev, nocl, us_px_date, trade_days, max_days=US_OWN_CLOSE_MAX_DAYS, etfs=frozenset(), ybar=None, info=None,
                       split_dates=None, split_unread=frozenset()):
    """야후 종가가 없는 미국 종목(nocl {티커: 까닭})을 지난 발행본(prev · data.json)의 마지막 확인 종가로 (2026-11-20 · Jack · 순수 함수).
    반환: (carried [기록 — 마지막 확인 종가 · pxd · pxc], same [기록 — 같은 날 다시 발행: 그날 종가 · d1], drop {티커: 까닭 (US_OWN_DROP_KO)}).
    - 지난 발행본에 그 종목이 usPxDate 종가로 있었으면 (pxd 없음): 그 usPxDate 가 오늘 기준일보다 앞이면 carried (pxd = 그 날짜), 같으면 same.
    - 지난 발행본에 pxc (마지막 확인 종가)로 있었으면 같은 가격 · 같은 pxd (다시 날짜를 매기지 않아요).
    - 리뷰 (2026-11-20, 더 새 야후 종가): ybar {티커: 기록} = 오늘 다운로드에서 그 종목의 마지막 봉(기준일 앞)으로 만든 기록 (예전 '자기 날짜' 길 그대로:
      pxd = 그 봉의 날짜 · 그 가격 · 그 시계열의 숫자 · d1 없음). 그 봉이 마지막 확인 종가의 날짜보다 뒤면 그 기록을 pxc 로 써요 (더 새 종가를 옛 종가로
      덮지 않게 · info["newer"] 에 {t, pxd, px}). 잠시 뺀 종목(지난 usSrc.own.aged)도 그 날짜 뒤의 봉이 있으면 같은 조건으로 돌아와요 (나이는 그 봉부터).
    - 그 종가 뒤 오늘 기준일까지 미국 거래일(trade_days: YYYY-MM-DD)이 max_days 보다 많으면 old (빼요 · 그 날짜는 info["oldPxd"]).
    - none 지난 발행본에 없음 · halted 지난 발행본에서도 pxd 만 (거래 정지 · 마지막 확인 종가 아님) · bad 값을 읽을 수 없음: 예전 그대로 (드롭이 아니에요).
    - 리뷰 (2026-11-20, 분할): split_dates {티커: {분할 날짜}} 에 그 종가 날짜 뒤의 분할이 있으면 싣지 않아요 (split · info["split"]) — 예전 그대로
      (야후의 자기 날짜 봉: 분할을 반영한 야후 시계열이에요 · 없으면 빠져요 · 잠시 뺀 종목에 적지 않아요). 지난 발행본의 가격은 분할 전이라 앱이 주식 수를
      바꾸면 평가액이 배율만큼 틀려요. 더 새 야후 봉은 미국 거래일(trade_days)에 있는 날짜일 때만 써요 (휴장일의 엉뚱한 봉은 쓰지 않아요).
      split_unread: 오늘 다운로드의 분할 칸을 읽지 못한 티커 — 분할을 모르니 싣지 않고 예전 그대로 (splitRead)."""
    prev = prev or {}
    ybar = ybar or {}
    split_dates = split_dates or {}
    info = {} if info is None else info
    newer, old_pxd, split_out = info.setdefault("newer", []), info.setdefault("oldPxd", {}), info.setdefault("split", [])
    tdays = {str(d)[:10] for d in trade_days}
    pst = {str(x.get("t")): x for x in prev.get("stocks") or [] if isinstance(x, dict) and x.get("cls") == "us" and not x.get("fund")}
    pown = (prev.get("usSrc") or {}).get("own") if isinstance(prev.get("usSrc"), dict) else None
    was = {str(a["t"]): a for a in ((pown or {}).get("aged") or []) if isinstance(pown, dict) and isinstance(a, dict) and a.get("t")}
    ppx = prev.get("usPxDate")
    ppx = ppx if isinstance(ppx, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ppx) else None
    today = us_px_date.isoformat() if isinstance(us_px_date, dt.date) else str(us_px_date)
    carried, same, drop = [], [], {}

    def is_day(x):
        try:
            return isinstance(x, str) and dt.date.fromisoformat(x).isoformat() == x
        except ValueError:
            return False

    def later_bar(t, own):
        """오늘 다운로드에 그 종목의 own 뒤 · 기준일 앞 봉이 있으면 그 기록 (가격 > 0)."""
        y = ybar.get(t)
        d = (y or {}).get("pxd")
        return y if (is_day(d) and d in tdays and own < d < today and (_fin(y.get("price")) or 0) > 0 and y.get("d1") is None) else None

    def take(t, own, rec, nw=None):
        if t in split_unread:                         # 분할을 몰라요: 싣지 않아요 (예전 그대로)
            drop[t] = "splitRead"
            split_out.append({"t": t, "pxd": own, "after": [], "unread": True})
            return
        after = sorted(d for d in split_dates.get(t, ()) if d > own)
        if after:                                     # 그 종가 뒤에 분할: 싣지 않아요 (예전 그대로)
            drop[t] = "split"
            split_out.append({"t": t, "pxd": own, "after": after})
            return
        if kr_own_age(own, today, trade_days) > max_days:
            drop[t] = "old"
            old_pxd[t] = own
            return
        carried.append(rec)
        if nw is not None:                            # 실은 것만 newer 에 (나이 상한으로 빠진 봉은 아니에요)
            newer.append(nw)

    for t in sorted(nocl):
        p = pst.get(t)
        if p is None:
            a = was.get(t)                            # 잠시 뺀 종목: 그 날짜 뒤의 야후 봉이 오늘 있으면 돌아와요
            y = later_bar(t, a.get("pxd")) if a and is_day(a.get("pxd")) else None
            if y is not None:
                take(t, y["pxd"], {**y, "pxc": True}, {"t": t, "pxd": y["pxd"], "px": y["price"]})
                continue
            drop[t] = "none"
            continue
        price = _fin(p.get("price"))
        if price is None or price <= 0 or ppx is None:
            drop[t] = "bad"
            continue
        base = {"t": t, "nk": t, "ne": t, "cls": "us", "ccy": "USD", "fxu": True, "s": "etc", "etf": t in etfs}
        base.update({k: p[k] for k in US_OWN_KEYS if k in p and p[k] is not None})
        if p.get("pxd") is None:
            if p.get("pxc") is not None:
                drop[t] = "bad"
                continue
            if ppx == today:
                d1 = _fin(p.get("d1"))
                if d1 is None:
                    drop[t] = "bad"
                    continue
                same.append({**base, "d1": d1})
                continue
            if ppx > today:
                drop[t] = "bad"
                continue
            own = ppx
        else:
            if p.get("pxc") is not True:
                drop[t] = "halted"
                continue
            own = p.get("pxd")
            if not is_day(own) or own >= ppx or own >= today:
                drop[t] = "bad"
                continue
        y = later_bar(t, own)
        if y is not None:                             # 야후에 더 새 종가가 있어요 (그 종목의 마지막 봉 · 기준일 앞 · 미국 거래일)
            take(t, y["pxd"], {**y, "pxc": True}, {"t": t, "pxd": y["pxd"], "px": y["price"]})
            continue
        take(t, own, {**base, "pxd": own, "pxc": True})
    return carried, same, drop


def us_own_aged(prev, nocl, drop, old_pxd=None):
    """2026-11-20 (Jack: 국내와 같게 — "After 5 trading days, show "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요.""): 오늘도 야후 종가가
    없는 종목 중 마지막 확인 종가가 나이 상한을 넘어 잠시 뺀 종목 → [{t, nk, pxd}] (티커 순 · data.json usSrc.own.aged). 지난 발행본에 있었는데 나이를
    넘은 종목(drop 'old')과, 지난 발행본이 이미 잠시 뺀 종목(usSrc.own.aged) 중 오늘도 야후 종가가 없는 종목 (지난 발행본의 stocks 에는 없어요 —
    drop 'none' 을 'old' 로 고쳐요). 오늘 종가가 있는 종목 · 목록에서 사라진 종목은 nocl 에 없어서 저절로 빠져요. drop 을 고쳐요. old_pxd: 그 종목의
    마지막 확인 종가 날짜 (us_own_close_carry 의 info["oldPxd"] · 더 새 야후 봉이 있었으면 그 날짜). 지난 기록의 why (예: split) 는 이어 적어요. (순수 함수)"""
    prev = prev or {}
    old_pxd = old_pxd or {}
    own = (prev.get("usSrc") or {}).get("own") if isinstance(prev.get("usSrc"), dict) else None
    was = {str(a["t"]): a for a in ((own or {}).get("aged") or []) if isinstance(own, dict) and isinstance(a, dict) and a.get("t")}
    pst = {str(x.get("t")): x for x in prev.get("stocks") or [] if isinstance(x, dict) and x.get("cls") == "us"}
    ppx = prev.get("usPxDate") if isinstance(prev.get("usPxDate"), str) else None
    out = {}
    for t, w in sorted(drop.items()):
        if t not in nocl:
            continue
        if w == "old":
            p, a = pst.get(t) or {}, was.get(t) or {}
            out[t] = {"t": t, "nk": str(p.get("nk") or a.get("nk") or t), "pxd": old_pxd.get(t) or p.get("pxd") or a.get("pxd") or ppx}
        elif w == "none" and t in was:
            a = was[t]
            out[t] = {"t": t, "nk": str(a.get("nk") or t), "pxd": a.get("pxd")}
            if isinstance(a.get("why"), str):
                out[t]["why"] = a["why"]
            drop[t] = "old"
    return [out[t] for t in sorted(out)]


def us_own_close_err(err, nocl_n=None):
    """마지막 확인 종가 단계(미국)가 오류로 멈췄을 때의 usSrc.own (실은 종목 0 · err — 관문이 경고해요 · 예전 그대로 야후의 마지막 봉으로 나가요)."""
    out = {"v": 1, "max": US_OWN_CLOSE_MAX_DAYS, "n": 0, "codes": [], "same": [], "from": {}, "newer": [], "split": [], "drop": {}, "dropEx": [],
           "bad": {"n": 0, "rows": []}, "err": str(err)[:300]}
    if isinstance(nocl_n, int):
        out["unconf"] = nocl_n
    return out


def us_own_close_step(prev, nocl, out, us_px_date, trade_days, etfs=frozenset(), split_dates=None, split_unread=frozenset()):
    """미국 마지막 확인 종가 단계 (2026-11-20 · fetch_us 가 시세를 다 받은 바로 뒤 · 상세 정보를 붙이기 전에 부르는 한 곳). nocl {티커: 까닭 (US_NOCL_KO)}:
    오늘 기준일 종가가 야후에 없는 종목. out: 오늘 미국 기록 (야후의 마지막 봉으로 만든 기록이 있으면 바꾸고, 없으면 더해요 · 나이 상한을 넘은 종목은
    빼요). trade_days: 미국 거래일 (S&P 500 일봉 날짜 · Timestamp · date · 'YYYY-MM-DD' 아무거나). 반환: data.json usSrc.own.
    이 단계의 어떤 오류도 발행을 멈추지 않아요 (Jack 의 상시 규칙): 크게 남기고, out 을 되돌리고 (예전 그대로 야후의 마지막 봉), err 에 까닭을 적어요."""
    keep = list(out)
    try:
        days = [pd.Timestamp(t).date().isoformat() for t in trade_days]
        today = us_px_date.isoformat() if isinstance(us_px_date, dt.date) else str(us_px_date)
        # 리뷰 (2026-11-20): 그 종목의 야후 마지막 봉으로 만든 기록 (예전 '자기 날짜' 길) — 마지막 확인 종가보다 새 봉이면 그것을 써요
        ybar = {r["t"]: r for r in out if r.get("t") in nocl and r.get("pxd") is not None and r.get("d1") is None}
        cinfo = {}
        carried, same, drop = us_own_close_carry(prev, nocl, us_px_date, days, etfs=etfs, ybar=ybar, info=cinfo, split_dates=split_dates,
                                                 split_unread=split_unread)
        aged = us_own_aged(prev, nocl, drop, cinfo.get("oldPxd"))
        newer = sorted(cinfo.get("newer") or [], key=lambda x: x["t"])
        split = sorted(cinfo.get("split") or [], key=lambda x: x["t"])
        repl = {r["t"]: r for r in carried + same}
        gone = {a["t"] for a in aged}
        new = []
        for r in out:
            t = r.get("t")
            if t in repl:
                new.append(repl.pop(t))
            elif t not in gone:
                new.append(r)
        new.extend(repl[t] for t in sorted(repl))     # 야후가 가격을 하나도 주지 않은 종목
        out[:] = new
        why = collections.Counter(nocl.values())
        by_day = collections.Counter(r["pxd"] for r in carried)
        log(f"{'  !! ' if nocl else '· '}미국 종가 미확인 {len(nocl):,}종목 (기준일 {today} · "
            + (" · ".join(f"{US_NOCL_KO[k]} {why[k]:,}" for k in ("bar", "empty", "err") if why[k]) or "없음") + ")"
            + (f": 마지막 확인 종가로 실음 {len(carried):,}종목 (pxd " + " · ".join(f"{d} {n}" for d, n in sorted(by_day.items(), reverse=True))
               + ") — " + ", ".join(f"{r['t']} ({r['pxd'][5:]})" for r in carried[:US_OWN_SHOW])
               + (f" 외 {len(carried) - US_OWN_SHOW}종목" if len(carried) > US_OWN_SHOW else "") if carried else "")
            + (f" · 지난 발행본이 같은 기준일이라 그날 종가 · d1 을 그대로 {len(same):,}종목 — " + ", ".join(r["t"] for r in same[:US_OWN_SHOW])
               + (f" 외 {len(same) - US_OWN_SHOW}종목" if len(same) > US_OWN_SHOW else "") if same else ""))
        if newer:
            log(f"  !! 그중 야후에 마지막 확인 종가보다 새 종가(그 종목의 마지막 봉 · 기준일 앞)가 있어 그 종가로 실은 미국 종목 {len(newer):,}: "
                + ", ".join(f"{x['t']} ({x['pxd']} {x['px']})" for x in newer[:US_OWN_SHOW])
                + (f" 외 {len(newer) - US_OWN_SHOW}종목" if len(newer) > US_OWN_SHOW else "") + " (usSrc.own.newer)")
        sp_after = [x for x in split if not x.get("unread")]
        sp_unread = [x for x in split if x.get("unread")]
        if sp_after:
            log(f"  !! 마지막 확인 종가 뒤에 주식 분할이 있어 싣지 않은 미국 종목 {len(sp_after):,} (지난 발행본의 가격은 분할 전 · 앱은 주식 수를 바꿔요 → "
                "예전 그대로: 야후의 자기 날짜 봉 · 없으면 빠짐 · usSrc.own.split): "
                + ", ".join(f"{x['t']} ({x['pxd']} 뒤 분할 {', '.join(x['after'])})" for x in sp_after[:US_OWN_SHOW]))
        if sp_unread:
            log(f"  !! 분할 칸을 읽지 못해 마지막 확인 종가로 싣지 않은 미국 종목 {len(sp_unread):,} (분할을 몰라요 → 예전 그대로: 야후의 자기 날짜 봉 · "
                "없으면 빠짐 · usSrc.own.split unread): " + ", ".join(f"{x['t']} ({x['pxd']})" for x in sp_unread[:US_OWN_SHOW]))
        dc = collections.Counter(drop.values())
        dn = [f"{t} ({US_OWN_DROP_KO[w]} · {US_NOCL_KO.get(nocl.get(t), '?')})" for t, w in sorted(drop.items())]
        if drop:
            log(f"  !! 마지막 확인 종가로 싣지 않은 미국 종목 {len(drop):,}: " + " · ".join(f"{k} {v:,}" for k, v in sorted(dc.items())) + " — "
                + ", ".join(dn[:US_OWN_SHOW]) + (f" 외 {len(dn) - US_OWN_SHOW}종목" if len(dn) > US_OWN_SHOW else ""))
        if aged:
            log(f"  !! 마지막 확인 종가가 {US_OWN_CLOSE_MAX_DAYS}거래일을 넘어 잠시 뺀 미국 종목 {len(aged):,} (앱은 '며칠째 종가를 확인하지 못해서 이 종목은 "
                f"잠시 빼 두었어요.' · usSrc.own.aged · 야후 종가가 다시 오거나 목록에서 사라지면 빠져요): "
                + ", ".join(f"{a['t']} ({a.get('pxd')})" for a in aged[:US_OWN_SHOW]) + (f" 외 {len(aged) - US_OWN_SHOW}종목" if len(aged) > US_OWN_SHOW else ""))
        long_ = [a for a in aged if isinstance(a.get("pxd"), str) and kr_own_age(a["pxd"], today, days) > US_OWN_AGED_LONG]
        if long_:
            log(f"  !! 잠시 뺀 지 {US_OWN_AGED_LONG}거래일이 넘은 미국 종목 {len(long_):,} (상장 폐지 · 티커 변경으로 목록에만 남았는지 확인해 주세요 · "
                "usSrc.own.aged): " + ", ".join(f"{a['t']} ({a.get('pxd')})" for a in long_[:US_OWN_SHOW])
                + (f" 외 {len(long_) - US_OWN_SHOW}종목" if len(long_) > US_OWN_SHOW else ""))
        # 머지 확인 (2026-11-20, 1): 실은 행마다 야후가 무엇을 줬는지 (bar 그 종목의 시계열은 있고 기준일 봉만 없음 · empty 쓸 수 있는 가격이 하나도 없음 ·
        # err 받다가 오류) — 관문의 '미국 종목 수' 두 줄은 bar 만 세요 (예전에도 실렸을 행 · empty · err 는 예전이면 빠졌어요)
        src_of = {r["t"]: nocl.get(r["t"]) for r in carried + same}
        return {"v": 1, "max": US_OWN_CLOSE_MAX_DAYS, "n": len(carried), "codes": sorted(r["t"] for r in carried),
                "same": sorted(r["t"] for r in same), "from": dict(sorted(src_of.items())), "newer": newer, "split": split, "unconf": len(nocl), "why": {k: int(v) for k, v in sorted(why.items())},
                "drop": {k: int(v) for k, v in sorted(dc.items())}, "dropEx": dn[:US_OWN_SHOW], "bad": {"n": 0, "rows": []}, "aged": aged}
    except Exception as e:
        out[:] = keep
        err = f"{type(e).__name__}: {str(e)[:200]}"
        log(f"  !! 마지막 확인 종가 단계(미국)가 오류로 멈췄어요 ({err}) — 야후 종가가 없는 미국 종목은 예전처럼 야후의 마지막 봉으로 내보내요 "
            "(실은 종목 0 · usSrc.own.err · 관문이 경고해요)")
        rec = us_own_close_err(err, len(nocl) if isinstance(nocl, dict) else None)
        try:
            rec["aged"] = [dict(a) for a in (((prev or {}).get("usSrc") or {}).get("own") or {}).get("aged") or []
                           if isinstance(a, dict) and a.get("t") and a["t"] in (nocl or {})]
        except Exception:
            rec["aged"] = []
        return rec


def us_own_drop_rows(us, umeta, bad, why):
    """리뷰 (2026-11-20, 2차 확인 1): 마지막 확인 종가 단계가 뺀 미국 행 (점검이 거른 행 · 점검이 멈춰 모두 뺀 행 · 발행할 splits 로 다시 본 행) —
    #139 처럼 umeta 의 그 종목 기록을 정리하고 (us_meta_drop · 오늘 다운로드의 새 분할 줄 포함) EXTRA_US 의 빠진 까닭을 적어요 (까닭 없이 빠지면
    관문 실패). why: 까닭 글 (티커 → 글 dict 도 돼요). 반환: 남은 미국 목록."""
    bad = set(bad)
    if not bad:
        return us
    us_meta_drop(umeta, us, bad)
    xm = umeta.get("usExtraMissing")
    if not isinstance(xm, dict):
        xm = umeta["usExtraMissing"] = {}
    fallback = "마지막 확인 종가 단계가 뺌 (usSrc.own)"           # 리뷰 B 잔 지적: 까닭이 빈 글이 되지 않게
    for t in sorted(bad):
        if t in EXTRA_US:
            w = why.get(t) if isinstance(why, dict) else why
            xm[t] = w if isinstance(w, str) and w.strip() else fallback
    return [r for r in us if r.get("t") not in bad]


def us_own_from_sync(own):
    """usSrc.own.from (실은 행 · 같은 날 다시 쓴 행마다 야후가 준 것) 을 남은 codes · same 에 맞춰요."""
    keep = set(own.get("codes") or []) | set(own.get("same") or [])
    if isinstance(own.get("from"), dict):
        own["from"] = {t: w for t, w in sorted(own["from"].items()) if t in keep}


def us_carry_splits(recent, prev):
    """{티커: {분할 날짜 ISO}} — 오늘 시세 다운로드의 분할(umeta splits · [[티커, 날짜, 배율]]) · 지난 발행본의 data.json splits · 고정 표
    (SPLIT_OVERRIDES 의 배율 있는 줄). 발행할 splits 는 이 셋으로 만들어요 (splits_fields). (순수 함수)"""
    out = collections.defaultdict(set)
    pr = (prev or {}).get("splits") if isinstance(prev, dict) else None
    for x in list(recent or []) + list(pr if isinstance(pr, list) else []):
        if isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], str) and isinstance(x[1], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x[1]):
            out[x[0]].add(x[1])
    for (t, d), (r, _why) in SPLIT_OVERRIDES.items():
        if r is not None:
            out[t].add(d)
    return out


def us_own_close_final(us, umeta, prev, days):
    """미국 목록이 정해진 바로 뒤 · 다른 단계보다 먼저 (Jack 의 규칙 — 우리 처리의 한 줄이 틀리면 그 줄을 빼고 크게 남기고 나머지는 발행해요): 기록
    (umeta usSrc.own)을 남은 행에 맞추고 (우선주 · 한국 종목의 미국 상장분 · 주식 종류 티커로 뺀 행), 관문과 같은 함수(validate_data.us_own_close_bad)로
    마지막 확인 종가 · 같은 날 다시 쓴 종가를 다시 보고, 맞지 않는 행은 빼요. days: 미국 거래일 YYYY-MM-DD 들. 반환: 남은 미국 종목 목록.
    분할은 단계(us_own_close_carry · split_dates)가 이미 보고 (예전 길로), 발행할 splits 가 정해진 뒤 us_own_split_late 가 한 번 더 봐요."""
    src = umeta.get("usSrc") if isinstance(umeta.get("usSrc"), dict) else None
    own = (src or {}).get("own") if isinstance((src or {}).get("own"), dict) else None
    if own is None:
        return us
    have = {r.get("t") for r in us}
    own["codes"] = sorted(r["t"] for r in us if r.get("pxc"))
    own["n"] = len(own["codes"])
    own["same"] = sorted(t for t in own.get("same") or [] if t in have)
    own["newer"] = [x for x in own.get("newer") or [] if isinstance(x, dict) and x.get("t") in set(own["codes"])]
    us_own_from_sync(own)
    if not own["codes"] and not own["same"]:
        log("· 마지막 확인 종가 점검 (미국 · 관문과 같은 함수): 0종목 빼고 발행")
        return us
    bad = us_own_close_bad({"usPxDate": umeta.get("usPxDate"), "usSrc": src, "stocks": us}, prev, days)
    gone = collections.defaultdict(list)
    for t, w in bad:
        gone[t].append(w)
    rows = [f"{t} ({' · '.join(US_OWN_WHY.get(w, w) for w in ws)})" for t, ws in sorted(gone.items())]
    log(f"{'  !! ' if gone else '· '}마지막 확인 종가 점검 (미국 · 관문과 같은 함수): {len(gone):,}종목 빼고 발행" + (" — " + ", ".join(rows[:US_OWN_SHOW]) if rows else ""))
    if not gone:
        return us
    own["codes"] = [c for c in own["codes"] if c not in gone]
    own["n"] = len(own["codes"])
    own["same"] = [c for c in own["same"] if c not in gone]
    own["newer"] = [x for x in own["newer"] if x.get("t") not in gone]
    us_own_from_sync(own)
    own["bad"] = {"n": len(gone), "rows": rows[:US_OWN_SHOW], "why": dict(sorted(collections.Counter(w for ws in gone.values() for w in set(ws)).items()))}
    return us_own_drop_rows(us, umeta, gone, {t: "마지막 확인 종가 점검(관문과 같은 함수)이 거름: " + " · ".join(US_OWN_WHY.get(w, w) for w in ws)
                                              + " (usSrc.own.bad)" for t, ws in gone.items()})


def us_own_split_late(us, umeta, sp_fields, prev):
    """리뷰 (2026-11-20, 3): 발행할 splits(splits_fields 뒤 · 시드 · 2016년부터 다시 읽은 이력 포함)에 마지막 확인 종가(pxc) 날짜 뒤의 분할이 있는 행 —
    단계가 보지 못한 분할 (예: 오늘 다운로드에 그 종목이 없어 이력에서만 읽힘). 예전 그대로 해요 (2차 확인): 오늘 다운로드에 그 종목의 자기 날짜 봉이
    있었으면 (umeta _usOwnYahoo) 그 행으로 되돌리고 (가격 · 날짜 · 시계열 숫자는 그 봉 · pxc 없음 · PER · PBR · 시가총액 · 배당수익률 · 거래대금은 그
    가격에 맞춰요), 없었으면 빼요 (잠시 뺀 종목에 적지 않아요 · 그 종목의 새 분할 줄(지난 발행본 · 고정 표에 없는 줄)도 splits 에서 빼요 — 목록에 없는
    종목의 새 줄은 관문 실패 · umeta 정리와 EXTRA_US 까닭은 us_own_drop_rows). usSrc.own.split 에 late 로 적고 크게 남겨요. 반환: (미국 목록, splits 칸)."""
    rows = (sp_fields or {}).get("splits")
    if not isinstance(rows, list):
        return us, sp_fields
    sd = collections.defaultdict(set)
    for x in rows:
        if isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], str) and isinstance(x[1], str):
            sd[x[0]].add(x[1])
    hit = [r for r in us if r.get("pxc") and any(d > str(r.get("pxd")) for d in sd.get(r.get("t"), ()))]
    if not hit:
        return us, sp_fields
    stash = umeta.get("_usOwnYahoo") if isinstance(umeta.get("_usOwnYahoo"), dict) else {}
    cut = []
    back = {r["t"]: us_own_restore(r, stash[r["t"]], cut) for r in hit if isinstance(stash.get(r["t"]), dict)}
    back = {t: x for t, x in back.items() if x is not None}
    bad = {r["t"] for r in hit} - set(back)
    pmap = {(x[0], x[1]) for x in ((prev or {}).get("splits") or []) if isinstance(x, (list, tuple)) and len(x) >= 2}
    sp_fields = {**sp_fields, "splits": [x for x in rows if not (x[0] in bad and (x[0], x[1]) not in pmap and (x[0], x[1]) not in SPLIT_OVERRIDES)]}
    us = [back.get(r.get("t"), r) for r in us]
    kept = us_own_drop_rows(us, umeta, bad, {r["t"]: f"마지막 확인 종가({r.get('pxd')}) 뒤에 주식 분할이 있어 뺌 (usSrc.own.split)" for r in hit})
    bad = bad | set(back)                     # 기록에서는 둘 다 마지막 확인 종가가 아니에요
    own = ((umeta.get("usSrc") or {}).get("own")) if isinstance(umeta.get("usSrc"), dict) else None
    recs = [{"t": r["t"], "pxd": r.get("pxd"), "after": sorted(d for d in sd[r["t"]] if d > str(r.get("pxd"))), "late": True} for r in hit]
    if isinstance(own, dict):
        own["codes"] = [c for c in own.get("codes") or [] if c not in bad]
        own["n"] = len(own["codes"])
        own["newer"] = [x for x in own.get("newer") or [] if isinstance(x, dict) and x.get("t") not in bad]
        own["split"] = sorted([x for x in own.get("split") or [] if isinstance(x, dict) and x.get("t") not in bad] + recs, key=lambda x: str(x.get("t")))
        us_own_from_sync(own)
        dr = dict(own.get("drop") or {}) if isinstance(own.get("drop"), dict) else {}      # 2차 확인 잔 지적: 기록의 수가 맞게
        dr["split"] = int(dr.get("split") or 0) + len(hit)
        own["drop"] = dict(sorted(dr.items()))
        own["dropEx"] = (list(own.get("dropEx") or []) + [f"{x['t']} ({US_OWN_DROP_KO['split']} · 발행할 splits 에서 찾음)" for x in recs])[:US_OWN_SHOW]
    log(f"  !! 발행할 분할 목록에 마지막 확인 종가 뒤의 분할이 있어 싣지 않은 미국 종목 {len(hit):,} (단계가 보지 못한 분할 · 시드나 다시 읽은 이력 · "
        f"usSrc.own.split late) — 예전 그대로 야후의 자기 날짜 봉 {len(back):,} · 봉이 없어 뺌 {len(hit) - len(back):,}: "
        + ", ".join(f"{x['t']} ({x['pxd']} 뒤 {', '.join(x['after'])}" + (" → 야후 봉" if x["t"] in back else " → 뺌") + ")" for x in recs[:US_OWN_SHOW]))
    if cut:
        log(f"  !! 예전 길로 되돌린 미국 종목의 PER · PBR · 배당수익률 중 그 가격에 맞추자 범위(apply_us_info 와 같아요)를 벗어나 비운 칸 {len(cut):,}: "
            + ", ".join(cut[:US_OWN_SHOW]))
    return kept, sp_fields


def us_own_restore(row, y, cut=None):
    """마지막 확인 종가 행(row · 상세 정보까지 붙은 것)을 예전 길의 행으로: 야후의 자기 날짜 봉 기록(y · fetch_us 의 시세 기록)의 가격 · 날짜 · 시계열
    숫자를 쓰고 pxc 를 빼요. 그 가격에 맞추는 상세 숫자(PER · PBR · 시가총액 · 배당수익률 · 거래대금)는 가격 비율로 다시 맞춰요 (apply_us_info 와 같은
    자리수 · 같은 범위: PER 0~500 · PBR 0~100 · 0.005 미만 PBR 은 빈 칸 · 배당수익률 0~30% — 벗어나면 그 칸을 비우고 cut 에 '티커 칸' 을 적어요).
    쓸 수 없으면 None. (순수 함수)"""
    yp, cp = _fin(y.get("price")), _fin(row.get("price"))
    if not (yp and yp > 0 and cp and cp > 0 and isinstance(y.get("pxd"), str)):
        return None
    k = yp / cp
    out = {key: v for key, v in row.items() if key not in ("pxc",) and key not in US_OWN_KEYS}
    out.update({key: y[key] for key in US_OWN_KEYS if key in y and y[key] is not None})
    out["pxd"] = y["pxd"]
    out.pop("d1", None)
    cut = [] if cut is None else cut
    t = str(out.get("t"))
    pb = _fin(out.get("pbr"))
    if pb is not None and 0 < pb * k < US_PBR_MIN:      # apply_us_info (us_info_cuts) 처럼: 0.00 으로 반올림되는 PBR 은 빈 칸 · 표시
        out.pop("pbr", None)
        if not out.get("fcur"):
            out["pbrZero"] = True
        cut.append(f"{t} pbr")
    for key, lo, hi in (("per", 0, 500), ("pbr", 0, 100)):          # apply_us_info 처럼: 범위는 반올림 전 값으로 (리뷰 · 머지 확인 2)
        v = _fin(out.get(key))
        if v is not None and not (lo < v * k < hi):
            out.pop(key, None)
            cut.append(f"{t} {key}")
    v = _fin(out.get("dy"))
    if v is not None and not (0 <= v / k < 30):
        out.pop("dy", None)
        cut.append(f"{t} dy")
    for key, nd in (("per", 1), ("pbr", 2), ("cap", 3), ("val", 1)):
        if _fin(out.get(key)) is not None:
            out[key] = round(out[key] * k, nd)
    if _fin(out.get("dy")) is not None:
        out["dy"] = round(out["dy"] / k, 2)
    return out


def us_own_close_drop_all(us, umeta, err):
    """미국 마지막 확인 종가 점검(us_own_close_final)이 오류로 멈췄을 때: pxc 행 · 같은 날 다시 쓴 행을 모두 빼고 크게 남기고 usSrc.own 에 err · 뺀 수를
    적어요 (관문이 경고해요). 반환: 남은 미국 종목 목록."""
    src = umeta.get("usSrc") if isinstance(umeta.get("usSrc"), dict) else {}
    own = src.get("own") if isinstance(src.get("own"), dict) else us_own_close_err(err)
    gone = {r.get("t") for r in us if r.get("pxc")} | set(own.get("same") or [])
    log(f"  !! 마지막 확인 종가 점검(미국)이 오류로 멈췄어요 ({err}) — 마지막 확인 종가 · 같은 날 다시 쓴 {len(gone):,}종목을 모두 빼고 발행을 이어가요 (usSrc.own.err)")
    own.update({"codes": [], "n": 0, "same": [], "from": {}, "newer": [], "err": str(err)[:300], "bad": {"n": len(gone), "rows": sorted(gone)[:US_OWN_SHOW]}})
    src["own"] = own
    umeta["usSrc"] = src
    return us_own_drop_rows(us, umeta, gone, f"마지막 확인 종가 점검이 오류로 멈춰 뺌 ({str(err)[:80]} · usSrc.own.err)")


# ────────────────────────────────────────────────────────────
# 2026-11-22: 새로 들어온 미국 종목은 미국 기준일 종가가 확인된 날부터 (Jack)
# ────────────────────────────────────────────────────────────
# Jack (2026-11-22, verbatim): "2. No relaxation. Instead, a stock newly added to the S&P (or NASDAQ) list joins our list only once it
#  has a confirmed close; until then it isn't added. Nobody can hold it in the app before it joins, so nothing is lost, and the check
#  stays as it is."
# 왜: 지난 발행본에 없는 종목은 마지막 확인 종가(#165)가 없어서 예전처럼 야후의 더 오래된 봉을 자기 날짜(pxd)로 실었어요. 관문의 '미국 d1 채움' 줄은
# 그런 종목이 US_NO_CLOSE_MAX(5)를 넘으면 실패해요 — 야후가 통째로 빈 날에 S&P 목록이 6종목 넘게 바뀌면 그 줄 하나가 국내 데이터까지 발행 전체를
# 멈췄을 거예요 (2026-11-21 시험 실행 44849045557 · 야후 10:00~10:40 KST 빈 시간: 796종목 실음 · 지난 발행본에 없던 LGND · MKTX · SNDK · VRNS 4종목이
# 그 줄의 빠짐).
# 규칙: 오늘 미국 목록(fetch_us 가 야후에 묻는 티커 — S&P 500 · 나스닥 상위 400 · EXTRA_US, 그 ETF 까지) 중 지난 발행본의 미국 종목 행(cls us ·
# 펀드 아님)에도 잠시 뺀 기록(usSrc.own.aged)에도 없는 티커가 미국 기준일(usPxDate) 종가가 야후에 없으면 (fetch_us nocl 'bar': 그 종목의 시계열은
# 있는데 기준일 봉이 없거나 빈 값 · 0 · 음수 · 무한) 오늘은 넣지 않아요: 그 행을 빼고 크게 남기고 data.json usSrc.newWait 에 적고, 빠진 까닭
# (US_NEW_WAIT_WHY)을 손으로 더한 종목(usExtraMissing) · 주식 종류 티커 · S&P 500 중 빠진 종목(usListSym) 기록에 적어요 (손으로 더한 종목 줄은 경고).
# 종가가 확인되는 첫 실행에 다른 종목처럼 들어와요. 기다리는 동안은 넣을 수 없어요 — 앞선 날에 그 종목을 가졌던 사람(티커가 하루 빠졌다 돌아온
# 경우: LGND · SNDK 는 11-06 ~ 11-18 의 발행본에 모두 있었고 11-19 에 빠졌다가 (야후가 SNDK 이력을 3일만 줌) 11-20 에 돌아왔어요)은 지난
# 발행본에서 이미 그 종목이 없는 것을 봤고, 오늘도 같은 줄('이 종목의 데이터를 찾지 못했어요.')만 보고 숫자는 보지 않아요 (틀린 숫자가 없어요).
# - 지난 발행본이 일부러 뺀 티커 (data.json usLeftOut: 우선주 · 한국 종목의 미국 상장분 · 깨진 봉 …) 는 기다리지 않아요: 예전 길 그대로 가서 뒤 단계가
#   예전처럼 빼고 usLeftOut 에 적어요 (기다리게 하면 그날 usLeftOut 이 비고 다음 날 '새로 들어옴' 으로 적혀요 · 리뷰 2026-11-22).
# - 야후가 가격을 하나도 주지 않은 새 티커(empty · err)와 이력 60일 미만 종목은 예전에도 넣지 않았어요 (그대로 · 까닭도 그대로 — usListSym.noPx 가
#   그 글로 골라요).
# - 지난 발행본이 없거나 읽을 수 없으면 (첫 실행) 무엇이 새로 들어왔는지 알 수 없어 예전 그대로예요 (크게 남겨요 · newWait 없음).
# - 국내 상장 펀드 · 채권 ETF · 금 (KR_FUNDS · BOND_ETFS · 금현물)은 고정 목록이고 fetch_us 를 지나지 않아 이 규칙 밖이에요.
# - 관문은 그대로예요 ('미국 d1 채움' N = 5 · 손으로 더한 종목 줄 · 주식 종류 티커 줄 · 미국 종목 수 두 줄).
US_NEW_WAIT_WHY = "새로 들어온 종목 · 확인된 종가를 기다려요 (지난 발행본에 없고 미국 기준일 종가가 야후에 없음 · usSrc.newWait)"


def us_new_wait(prev, nocl, out=()):
    """새로 들어온 미국 종목 중 미국 기준일 종가를 기다릴 티커 (2026-11-22 · Jack · 순수 함수).
    prev: 지난 발행본 data.json · nocl: fetch_us 의 {티커: 'bar' · 'empty' · 'err'} (미국 기준일 종가가 야후에 없는 종목) · out: 오늘 미국 기록 (로그용).
    반환 {"wait": 기다릴 티커 (정렬) — nocl 이 'bar' 이고 지난 발행본의 미국 종목 행(cls us · 펀드 아님)에도 usSrc.own.aged 에도 usLeftOut 에도 없는 티커,
          "left": nocl 이 'bar' 인데 지난 발행본이 일부러 뺀 티커 (usLeftOut 의 목록 칸 모두 — 우선주 · 한국 종목 상장분 · 깨진 봉 …: 기다리지 않고
                  예전 길로 · 로그만),
          "joined": 지난 발행본이 모르던 티커 중 미국 기준일 종가가 있어 오늘 들어가는 티커 (정렬 · 로그만 · usLeftOut 의 티커는 빼요:
                    우선주 · 한국 종목 상장분처럼 날마다 뒤에서 빠지는 티커가 날마다 '새로 들어옴' 으로 적히지 않게),
          "off": None 또는 지난 발행본을 쓸 수 없는 까닭 (그러면 나머지는 비어요 — 예전 그대로)}."""
    if not isinstance(prev, dict):
        return {"wait": [], "left": [], "joined": [], "off": "지난 발행본이 없거나 읽지 못했어요 (첫 실행?)"}
    rows = prev.get("stocks")
    have = {str(x["t"]) for x in rows if isinstance(x, dict) and x.get("cls") == "us" and not x.get("fund") and x.get("t")} \
        if isinstance(rows, list) else set()
    if not have:
        return {"wait": [], "left": [], "joined": [], "off": "지난 발행본에 미국 종목 행이 없어요"}
    src = prev.get("usSrc")
    own = src.get("own") if isinstance(src, dict) else None
    aged = own.get("aged") if isinstance(own, dict) else None
    known = have | ({str(a["t"]) for a in aged if isinstance(a, dict) and a.get("t")} if isinstance(aged, list) else set())
    lo = prev.get("usLeftOut") if isinstance(prev.get("usLeftOut"), dict) else {}
    # 검증 리뷰 (11-22): clean_us_list 가 매일 빼는 목록 (우선주 · 국내 상장) 만 — badBar 는 이 실행에서 'bar' 가 될 수 없고, 앞으로 생길 목록이
    # 저절로 예외가 되지 않게 이름을 적어요 (그 밖의 지난 발행본에 없는 종목은 Jack 의 규칙대로 기다려요)
    left = {str(t) for k in ("preferred", "krListing") for t in (lo.get(k) if isinstance(lo.get(k), list) else []) if isinstance(t, (str, int))}
    nocl = nocl if isinstance(nocl, dict) else {}
    new = sorted(str(t) for t, w in nocl.items() if w == "bar" and str(t) not in known)
    joined = sorted({str(r["t"]) for r in out if isinstance(r, dict) and r.get("t") and str(r["t"]) not in known and r["t"] not in nocl
                     and str(r["t"]) not in left})
    return {"wait": [t for t in new if t not in left], "left": [t for t in new if t in left], "joined": joined, "off": None}


def us_new_wait_step(prev, nocl, out, why, us_px_date):
    """fetch_us 안에서 마지막 확인 종가 단계 바로 앞 (2026-11-22 · Jack): 새로 들어온 종목 중 미국 기준일 종가가 야후에 없는 티커(us_new_wait)의
    행을 out 에서 빼고 nocl 에서도 빼요 — 마지막 확인 종가 단계 · 분할 칸 읽기 · 상세 정보 · 분할 목록 · 발행 파일 어디에도 가지 않게. why (fetch_us
    의 extra_why: usExtraMissing · usListSym 의 빠진 까닭)에 US_NEW_WAIT_WHY 를 적어요. 반환: data.json usSrc.newWait (티커 · 정렬 · 없으면 []).
    이 단계의 어떤 오류도 발행을 멈추지 않아요: 크게 남기고 예전 그대로예요 (out · nocl · why 를 바꾸기 전으로 되돌려요)."""
    usd = us_px_date.isoformat() if isinstance(us_px_date, dt.date) else str(us_px_date)
    keep_out, keep_nocl, keep_why = list(out), dict(nocl), dict(why)
    try:
        r = us_new_wait(prev, nocl, out)
        if r["off"]:
            nb = sum(1 for w in nocl.values() if w == "bar")
            log(f"  !! {r['off']} — 새로 들어온 미국 종목을 가릴 수 없어 예전 그대로예요 (미국 기준일 {usd} 종가가 없는 "
                f"{nb:,}종목은 야후의 마지막 봉 날짜로 · usSrc.newWait 없음)")
            return []
        wait, joined, left = r["wait"], r["joined"], r["left"]
        jtxt = (f"{len(joined):,}" + (": " + ", ".join(joined[:US_OWN_SHOW]) + (f" 외 {len(joined) - US_OWN_SHOW}종목" if len(joined) > US_OWN_SHOW else "")
                                      if joined else ""))
        if left:
            log(f"· 지난 발행본이 일부러 뺀 티커(usLeftOut) 중 미국 기준일 {usd} 종가가 야후에 없는 {len(left):,}: " + ", ".join(left[:US_OWN_SHOW])
                + (f" 외 {len(left) - US_OWN_SHOW}종목" if len(left) > US_OWN_SHOW else "")
                + " — 기다리지 않고 예전 길 그대로 (우선주 · 한국 종목 상장분은 뒤 단계가 예전처럼 빼요)")
        if not wait:
            log(f"· 새로 들어온 미국 종목 (지난 발행본에 없던 티커): 미국 기준일 {usd} 종가가 있어 오늘 들어감 {jtxt} · 종가를 기다림 0")
            return []
        ws = set(wait)
        n0 = len(out)
        out[:] = [x for x in out if x.get("t") not in ws]
        for t in wait:
            nocl.pop(t, None)
            why[t] = US_NEW_WAIT_WHY
        log(f"  !! 새로 들어온 미국 종목 {len(wait):,} (지난 발행본에 없고 미국 기준일 {usd} 종가가 야후에 없음): " + ", ".join(wait[:US_OWN_SHOW])
            + (f" 외 {len(wait) - US_OWN_SHOW}종목" if len(wait) > US_OWN_SHOW else "")
            + " — 오늘은 넣지 않아요 · 미국 기준일 종가가 확인되면 넣어요 (usSrc.newWait · 관문 '미국 d1 채움' 은 그대로)")
        if n0 - len(out) != len(wait):       # 'bar' 종목은 늘 행이 있어요 — 아니면 fetch_us 가 바뀐 거예요 (크게 남겨요 · 기다리는 종목은 그래도 빠져요)
            log(f"  !! 새로 들어온 미국 종목 {len(wait):,} 중 뺀 행이 {n0 - len(out):,}개예요 (종목마다 한 행이어야 해요 — fetch_us 의 nocl · 행을 확인해 주세요)")
        log(f"· 새로 들어온 미국 종목 중 미국 기준일 {usd} 종가가 있어 오늘 들어감 {jtxt}")
        return wait
    except Exception as e:
        out[:] = keep_out
        nocl.clear()
        nocl.update(keep_nocl)
        why.clear()
        why.update(keep_why)
        log(f"  !! 새로 들어온 미국 종목을 가리다 오류로 멈췄어요 ({type(e).__name__}: {str(e)[:160]}) — 예전 그대로예요 (미국 기준일 {usd} 종가가 "
            "없는 새 종목은 야후의 마지막 봉 날짜로 · usSrc.newWait 없음)")
        return []


REF_LINK = ("ok", "new", "unknown", "break")   # KRX 기준가 연결 상태 — 뒤로 갈수록 나빠요 (모을 때 가장 나쁜 것)
REF_EVENTS_LOUD = 100   # 19거래일 사이 기준가가 새로 정해진 종목이 이보다 많으면 크게 남겨요 (2026-11-13: 18종목 · 한 종목에 여러 번이어도 한 종목)
JUMP_LOG_SHOW = 12      # 로그 한 줄에 이름을 적는 종목 수 (나머지는 수만)


def kr_ref_links(files, trade_days=(), codes=None):
    """KRX 기준가로 본 '그날과 오늘이 같은 기준인지' (2026-11-14 · 순수 함수). files: [(날짜, 목록 DataFrame)] 오늘(기준일) 파일이 맨 앞,
    그다음 최근 거래일 파일들 (최신 → 과거, kr_recent_sessions 와 같은 순서). trade_days: 거래일들 (KOSPI 일봉 날짜) — 이웃한 두 파일 사이에
    거래일이 빠져 있으면 그 연결은 확인 못 함. codes: 볼 종목 (None 이면 오늘 파일의 모든 종목).
    연결 하나 = 이웃한 두 파일 (앞 P → 뒤 E): E 의 기준가 (Close − Changes · 목록 파일의 Close 와 Changes 는 같은 가격 기준이에요) 가 P 의 공식 종가와
    1원 안으로 같으면 'ok' (그 사이에 기준이 바뀌지 않았어요), 다르면 'break' (분할 · 병합 · 감자 · 권리락 · 거래정지 뒤 재평가 — KRX 가 기준가를
    새로 정한 날), P 와 그보다 앞 파일 모두에 행이 없으면 'new' (그 뒤에 새로 상장 — 그 앞 날은 공식 종가가 없어 고칠 봉도 없어요 · 리뷰 S1),
    그 밖에 값 · 행이 없거나 (앞 파일에는 있는데 빠짐) 사이에 빠진 거래일이 있으면 'unknown'. pin_why_not 은 'new' 를 'unknown' 처럼 다뤄요.
    반환: (by_day, events) — by_day {pd.Timestamp(D): {코드: 상태}} (D = 맨 앞을 뺀 각 파일의 날짜 · 상태 = D 다음 파일부터 오늘 파일까지 연결 중
    가장 나쁜 것), events [(코드, E 날짜, 앞 파일의 공식 종가, E 의 기준가)] (break 만)."""
    def mp(df):
        out = {}
        if df is None or "Code" not in df.columns:
            return out
        for _, r in df.iterrows():
            cl, ch = _fin(r.get("Close")), _fin(r.get("Changes"))
            out[str(r["Code"]).strip()] = (kr_official_close(r), None if cl is None or ch is None else cl - ch)
        return out
    days = sorted({pd.Timestamp(t).date() for t in trade_days})
    maps = [(d, mp(df)) for d, df in files]
    if codes is None:
        codes = set(maps[0][1]) if maps else set()
    oldest = {}                                       # 종목 → 행이 있는 가장 앞(오래된) 파일의 자리
    for i, (_, m) in enumerate(maps):
        for c in m:
            oldest[c] = i
    acc, by_day, events = {c: "ok" for c in codes}, {}, []
    for i in range(1, len(maps)):
        (de, me), (dp, mprev) = maps[i - 1], maps[i]
        gap = any(dp < t < de for t in days)
        for c in codes:
            a, b = me.get(c), mprev.get(c)
            if b is None and i > oldest.get(c, -1):
                st = "new"
            elif gap or not a or not b or a[1] is None or not b[0]:
                st = "unknown"
            elif abs(a[1] - b[0]) > 1:
                st = "break"
                events.append((c, de, b[0], a[1]))
            else:
                st = "ok"
            if REF_LINK.index(st) > REF_LINK.index(acc[c]):
                acc[c] = st
        by_day[pd.Timestamp(dp)] = dict(acc)
    return by_day, events


def pin_why_not(off, bar, shr_day, shr_now, link="unknown", px_tol=PIN_PX_TOL, shr_tol=PIN_SHR_TOL, ref_tol=PIN_REF_TOL):
    """그날 공식 종가(off)로 네이버 봉(bar)을 고쳐도 되는지 (2026-11-14). None = 고쳐요 · 아니면 고치지 않는 이유 (순수 함수).
    네이버 일봉은 수정주가 (기준이 바뀌면 앞 봉을 모두 새 기준으로 고쳐 둬요) 이고 넥스트레이드까지 합친 마지막 체결가라 같은 기준이어도 공식 종가와
    조금 달라요 (2026-11-13: 같은 기준 날의 99% 가 3.9% 안 · 가장 큰 시간외 하루 21.9%). link: 그날과 오늘 사이 KRX 기준가 연결 (kr_ref_links).
    'break'   → 'basis': 그 사이에 KRX 가 기준가를 새로 정했어요 (분할 · 병합 · 감자 · 권리락) — 그날 공식 종가는 다른 기준이에요
                (에쎈테크 5:1 병합: 그날 591원 · 네이버 수정주가 2,955원). 절대 고치지 않아요.
    'ok'      → 같은 기준이 확인됐어요: 차이가 px_tol 안이면, 또는 상장주식수가 오늘과 shr_tol 안이고 차이가 ref_tol 안이면 고쳐요 (시간외 큰
                움직임 날도 공식 종가로) · 아니면 'far'.
    'unknown' · 'new' → 확인 못 함: 상장주식수가 오늘과 shr_tol 안이고 (모르면 'shr', 다르면 'basis') 차이가 px_tol 안일 때만 (아니면 'far' — 무상증자는
                권리락 뒤 새 주식이 상장되기 전까지 주식 수가 같아요: 코나아이 1.5배). 둘 다 아니면 네이버 봉 그대로 (고쳐서 틀리는 것보다 안전해요)."""
    if link == "break":
        return "basis"
    shr_day, shr_now, off, bar = _fin(shr_day), _fin(shr_now), _fin(off), _fin(bar)
    shr_known = bool(shr_day and shr_now and shr_day > 0 and shr_now > 0)
    same_shr = shr_known and abs(shr_day / shr_now - 1) <= shr_tol
    if link == "ok":
        if off and bar and off > 0 and bar > 0:
            gap = abs(off / bar - 1)
            if gap <= px_tol or (same_shr and gap <= ref_tol):
                return None
        return "far"
    if not shr_known:
        return "shr"
    if not same_shr:
        return "basis"
    if not off or not bar or off <= 0 or bar <= 0 or abs(off / bar - 1) > px_tol:
        return "far"
    return None


def pin_recent(px, off_by_day, code, shr_by_day=None, shr_now=None, kept=None, ref_by_day=None):
    """최근 거래일들의 값을 공식 종가로 맞춰요 (그 날짜 봉이 있을 때만). 반환: (시계열, 고친 개수). (순수 함수)
    2026-11-14: 네이버 일봉은 수정주가라, 다른 기준인 그날 공식 종가를 넣으면 시계열이 깨져요 (pin_why_not). shr_by_day ({날짜: {종목코드: 그날
    상장주식수}}) · shr_now (오늘 상장주식수) · ref_by_day (kr_ref_links 의 by_day) 를 주면 pin_why_not 이 허락한 날만 고쳐요 — 파이프라인은 늘 줘요.
    셋 다 주지 않으면 공식 종가가 네이버 봉과 PIN_PX_TOL 안인 날만 고쳐요 (기준을 볼 수 없어도 큰 기준 차이는 막아요).
    kept: collections.Counter 를 주면 고치지 않은 날을 이유별로 더해요 ('basis' · 'far' · 'shr')."""
    fixed = 0
    px = px.copy()
    for ts, offmap in off_by_day.items():
        v = offmap.get(code)
        if not v or ts not in px.index:
            continue
        bar = float(px.loc[ts])
        if bar == v:
            continue
        if shr_by_day is None and ref_by_day is None:
            why = None if bar > 0 and abs(v / bar - 1) <= PIN_PX_TOL else "far"
        else:
            why = pin_why_not(v, bar, (shr_by_day or {}).get(ts, {}).get(code), shr_now,
                              (ref_by_day or {}).get(ts, {}).get(code, "unknown"))
        if why:
            if kept is not None:
                kept[why] += 1
            continue
        px.loc[ts] = v
        fixed += 1
    return px, fixed


def pin_audit(raw, final, px_date, off_by_day, shr_by_day, shr_now, code, ref_by_day=None):
    """고정 뒤 자기 점검 (2026-11-14 · 관문이 0 이 아니면 실패해요): 기준일(px_date) 봉 말고는 네이버 원래 시계열(raw · 기준일까지 자른 것)과
    달라진 봉이 모두 '허락된 고정'이어야 해요 — 그날 목록의 공식 종가와 같고, pin_why_not 이 그날 · 그 네이버 봉에 허락해요 (그 사이 KRX 기준가가
    바뀌지 않았고 · 주식 수와 값 차이가 기준 안). 네이버 봉이 빠지거나(dropped) 없던 날이 생겨도(added) 어긋남이에요. 고정 단계(pin_recent)가
    아니라 다 만든 시계열을 봐서, 나중에 다른 단계가 봉을 바꿔도 (예: 더 오래된 날의 공식 종가 이력) 여기서 잡혀요.
    반환: [(날짜, 이유)] — 이유 added · dropped · notOfficial · basis · far · shr. (순수 함수)"""
    bad = []
    pxd = pd.Timestamp(px_date)
    raw = raw[raw.index < pxd]
    fin = final[final.index != pxd]
    bad += [(ts, "dropped") for ts in raw.index.difference(fin.index)]
    bad += [(ts, "added") for ts in fin.index.difference(raw.index)]
    rv = raw.astype(float).to_dict()                 # 날짜가 겹치는 네이버 봉은 dict 가 하나로 합쳐요 (아래 비교는 최종 시계열의 봉마다)
    for ts, v in fin.items():
        if ts not in rv:
            continue
        r, v = rv[ts], float(v)
        if r == v:
            continue
        off = (off_by_day.get(ts) or {}).get(code)
        if off is None or v != float(off):
            bad.append((ts, "notOfficial"))
            continue
        why = pin_why_not(off, r, (shr_by_day or {}).get(ts, {}).get(code), shr_now, (ref_by_day or {}).get(ts, {}).get(code, "unknown"))
        if why:
            bad.append((ts, why))
    return bad


def kr_day_limit(market):
    """하루 가격 제한폭 (%): 코넥스 KONEX_DAY_LIMIT (15) · 코스피 · 코스닥 KR_DAY_LIMIT (30). (순수 함수)"""
    return KONEX_DAY_LIMIT if str(market or "").strip().upper() == "KONEX" else KR_DAY_LIMIT


def jump_bounds(limit, tol=PIN_PX_TOL):
    """(아래, 위): 하루 움직임 p1 ÷ p0 − 1 이 이 안이면 가격 제한폭(limit %) 과 봉 하나의 넥스트레이드 차이(tol)로 설명돼요.
    네이버 봉은 넥스트레이드 마지막 체결가라 공식 종가와 tol 까지 다를 수 있고, 다음 날 상한가는 그 전날 '공식 종가'의 1 + limit 이에요
    → 위 (1 + L) ÷ (1 − tol) − 1 · 아래 (1 − L) ÷ (1 + tol) − 1 (30% · 5%: +36.8% · −33.3%). 고친 날(공식 종가)끼리는 limit 안이에요. (순수 함수)"""
    L = limit / 100.0
    return (1 - L) / (1 + tol) - 1, (1 + L) / (1 - tol) - 1


JUMP_FLAT = 3       # 움직임 바로 앞에 같은 값이 이만큼(봉 사이 변화 0 이 이만큼) 이어지면 거래 없는 날들 뒤 재개로 봐요 (거래정지 · 병합 · 감자)
JUMP_GAP_DAYS = 14  # 앞 봉과 달력으로 이만큼 넘게 떨어져 있어도 (네이버에 빈 날이 있는 정지) 재개로 봐요


def kr_jumps(final, raw, limit, tol=PIN_PX_TOL):
    """하루 움직임이 가격 제한폭으로 설명되지 않는 봉 (2026-11-14 · 첫 봉 빼고 시계열 전체 = 52주 · 변동성 · 베타 · 낙폭 · 수익률이 쓰는 기간).
    반환: [(날짜, %, 이유)] — 이유 (KR_JUMP_WHY): 'pin' 네이버 원래 시계열(raw)의 같은 자리에는 없는 움직임 (우리가 고친 봉이 만든 것 ·
    0 이어야 해요) · 'halt' 거래 없는 날들(JUMP_FLAT · JUMP_GAP_DAYS) 뒤 재개 — 기준가가 다시 정해져요 · 'spike' 다음 봉이 제자리(앞 봉의
    제한폭 안)로 돌아온 하루짜리 봉 (네이버의 잘못된 봉) · 'other' 그 밖 (네이버가 고치지 않은 사건일 수 있어요). (순수 함수)"""
    lo, hi = jump_bounds(limit, tol)
    out = []
    if final is None or len(final) < 2:
        return out
    vals = final.astype(float).values
    idx = final.index

    def ok(a, b):
        return a > 0 and b > 0 and lo <= b / a - 1 <= hi

    spike_at = None                                  # 앞 움직임이 하루짜리 봉으로 올라간 것이면 그 봉의 자리
    for i in range(1, len(vals)):
        p0, p1 = vals[i - 1], vals[i]
        if p0 <= 0 or p1 <= 0 or ok(p0, p1):
            continue
        t0, t1 = idx[i - 1], idx[i]
        if t0 in raw.index and t1 in raw.index and ok(float(raw.loc[t0]), float(raw.loc[t1])):
            why = "pin"
        elif spike_at == i - 1:
            why = "spike"                            # 하루짜리 봉에서 제자리로 돌아오는 움직임
        elif (i - 1 >= JUMP_FLAT and all(vals[j] == vals[j - 1] for j in range(i - JUMP_FLAT, i))) or (t1 - t0).days > JUMP_GAP_DAYS:
            why = "halt"
        elif i + 1 < len(vals) and ok(p0, vals[i + 1]):
            why, spike_at = "spike", i
        else:
            why = "other"
        out.append((t1, round((p1 / p0 - 1) * 100, 1), why))
    return out


def _official_map(df):
    """종목코드 → 공식 종가 (시가총액 ÷ 상장주식수)."""
    out = {}
    for _, r in df.iterrows():
        c = kr_official_close(r)
        if c:
            out[str(r["Code"]).strip()] = c
    return out


def _shares_map(df):
    """종목코드 → 그날 상장주식수 (2026-11-14 · 공식 종가 고정의 기준 확인용). 비었거나 0 이하면 빼요."""
    out = {}
    if "Stocks" not in df.columns:
        return out
    for c, s in zip(df["Code"].astype(str).str.strip(), df["Stocks"]):
        v = _fin(s)
        if v and v > 0:
            out[c] = v
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
            # 2026-11-14: 상한가 · 하한가는 정확히 ±30% 인데 (4,030 ÷ 3,100 − 1) × 100 = 30.000000000000004 처럼 부동소수점 끝자리가 붙어
            # 빈 칸이 됐어요 (11-12 베셀 · 모아라이프플러스, 11-13 디와이에이 상한가). 그 끝자리(D1_LIMIT_EPS)만 넘겨요 — 30.004% 는 여전히 빈 칸
            if abs(v) > max_abs + D1_LIMIT_EPS:
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


# 2026-11-14 (Jack, design chat 2026-11-08 · dart-gaps §9): 기준일에 거래가 없던 종목 (거래정지 · 코넥스의 거래 없는 날)은 d1 이 0.00% 가
# 아니라 빈 칸이고 noTrade 표시를 달아요. 앱은 그 자리에 "{md} 거래 없음 (거래정지일 수 있어요)". 다른 이유로 빈 d1 은 d1Why 로 이유를 남겨요
# (앱: "오늘 등락률은 받지 못했어요."). 목록 파일에는 거래정지 표시가 없어요 — 거래 없는 날은 거래량 0 · 시가 0 이에요.
# D1_WHY (관문 파일 validate_data.py 에 있어요): 거래 없음 · ±30% 밖 · 직전 거래일 행 없음 · 직전 거래일 파일을 쓸 수 없음 (그날 모든 종목)
D1_WHY_KO = {"noTrade": "거래 없음", "range": f"±{D1_MAX_KR:g}% 밖", "new": "직전 거래일 행 없음", "prev": "직전 거래일 파일을 쓸 수 없음"}


NO_TRADE_MAX_SHARE = 0.10   # 목록 파일 행 중 거래 없는 행이 이보다 많으면 그 칸을 믿지 않아요 (11-11 ~ 11-13: 4.7 ~ 4.9% · 135 ~ 141 / 2,877행) — 한 파일의 잘못이 모두를 '거래 없음'으로 보이게 하지 않게
NO_TRADE_MIN_READ = 0.90    # 거래량 · 시가가 둘 다 숫자인 행이 이보다 적으면 그 칸을 믿지 않아요 (11-11 ~ 11-13: 모든 행이 숫자) — 칸이 빈 값으로 바뀌면 아무도 표시하지 않고 크게 남겨요


def no_trade_unseen(no_trade, n_rows, max_share=NO_TRADE_MAX_SHARE):
    """거래 없음 칸을 믿지 않는 까닭 (2026-11-14 · 순수 함수) — None 이면 믿어요. 'many': 행의 max_share 넘게 거래가 없어요 (파일 전체가 0 으로
    찬 잘못). 믿지 않으면 누구도 거래 없음으로 표시하지 않아요 (예전처럼 0.00% · 관문이 경고해요)."""
    if n_rows and len(no_trade) > max_share * n_rows:
        return "many"
    return None


def kr_no_trade_read(df):
    """거래량 · 시가가 둘 다 숫자(유한한 값)인 행 수 (2026-11-14 · 순수 함수). 칸이 없으면 0."""
    if df is None or "Volume" not in df.columns or "Open" not in df.columns:
        return 0
    return sum(1 for v, o in zip(df["Volume"], df["Open"]) if _fin(v) is not None and _fin(o) is not None)


def kr_no_trade_plan(df, must=GATE_MUST, max_share=NO_TRADE_MAX_SHARE, min_read=NO_TRADE_MIN_READ):
    """기준일 목록 파일에서 거래 없음으로 표시할 종목과 표시하지 않는 까닭 (2026-11-14 · 리뷰 S1 · S2 · 순수 함수).
    반환: (표시할 코드 set, unseen, odd set, must 목록).
    - unseen: None 이면 가렸어요. 아니면 아무도 표시하지 않아요 (예전처럼 0.00% · 관문이 경고해요):
      'cols' 목록 파일에 거래량(Volume) · 시가(Open) 칸이 없음 (형식이 바뀜 · 지난 data.json 으로 만든 목록) ·
      'blank' 칸은 있는데 둘 다 숫자인 행이 min_read 보다 적음 (칸이 빈 값으로 바뀜 — 그대로 두면 아무도 표시되지 않은 채 '가림'으로 보여요) ·
      'many' 거래 없는 행이 max_share 를 넘음 (파일 전체가 0 으로 찬 잘못).
    - odd: 거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 행 — 그 행이 스스로 어긋나요. 표시하지 않아요 (kr_no_trade).
    - must: 거래가 없다고 나온 관문의 필수 종목 — 표시하지 않아요 (그 행의 잘못이면 필수 종목 d1 이 비어 모두의 발행이 막혀요). 표시할 set 에서 빠져요."""
    nt, cols, odd = kr_no_trade(df)
    if not cols:
        return set(), "cols", set(), []
    n = len(df)
    if n and kr_no_trade_read(df) < min_read * n:
        return set(), "blank", odd, []
    if no_trade_unseen(nt, n, max_share):
        return set(), "many", odd, []
    m = sorted(set(must) & nt)
    return nt - set(m), None, odd, m


def d1_blank_counts(rows, seen=True, unseen=None, odd=(), must=()):
    """발행하는 국내 종목(목록 파일에서 온 cls kr · 펀드 아님)의 빈 d1 이유별 수 (2026-11-14 · 순수 함수) — data.json d1Blank.
    seen: 거래 없는 종목을 가릴 수 있었는지 · unseen: 못 했으면 까닭 ('cols' · 'blank' · 'many' — kr_no_trade_plan)
    · odd: 거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 발행 종목 (출처의 행이 스스로 어긋나요 · 표시하지 않았어요) · must: 거래가 없다고 나온 필수 종목
    (관문의 필수 종목 7개 · 표시하지 않았어요 — 그 행의 잘못이면 필수 종목 d1 이 비어 모두의 발행이 막혀요. 관문이 경고해요)."""
    out = {k: 0 for k in D1_WHY}
    codes = set()
    for r in rows:
        w = r.get("d1Why")
        if r.get("cls") == "kr":
            codes.add(r.get("t"))
            if w in out:
                out[w] += 1
    out["seen"] = bool(seen)
    if not seen:
        out["unseen"] = unseen or "cols"
    out["odd"] = sorted(c for c in odd if c in codes)
    out["must"] = sorted(c for c in must if c in codes)
    return out


def d1_blank_final(stocks, meta):
    """발행 직전의 data.json d1Blank (2026-11-14 · 순수 함수): 이유별 수는 발행하는 종목에서 다시 세고, 가릴 수 있었는지 · 어긋난 행 · 필수 종목은
    국내 시세 단계의 것(meta = fetch_korea 의 d1Blank)을 그대로. meta 가 없으면 가리지 못한 것으로 ('cols')."""
    m = meta if isinstance(meta, dict) else {}
    return d1_blank_counts(stocks, bool(m.get("seen")), m.get("unseen"), m.get("odd") or (), m.get("must") or ())


def kr_no_trade(df):
    """기준일 목록 파일에서 거래가 없던 종목 (2026-11-14 · 순수 함수): 거래량(Volume) 0 이고 시가(Open) 0 인 행 — 거래대금(Amount) 칸이 있으면
    그것도 0 일 때만 (11-11 ~ 11-13 의 거래 없는 행 415개는 모두 0 이에요). 값이 비었거나 숫자가 아니면 거래가 없다고 하지 않아요 (모르는 것).
    반환: (코드 set, 열이 있는지, 어긋난 코드 set — 거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 행: 출처의 한 행이 스스로 어긋나요. 표시하지
    않고 크게 남겨요 · 한 종목의 출처 문제가 그 종목을 거래 없음으로 보이게 하지 않게).
    열이 없으면 (출처의 형식이 바뀜 · 지난 data.json 으로 만든 목록) 빈 set 과 False — 누구도 거래 없음으로 표시하지 않아요 (예전처럼 0.00%)."""
    if df is None or "Code" not in df.columns or "Volume" not in df.columns or "Open" not in df.columns:
        return set(), False, set()
    amt = df["Amount"] if "Amount" in df.columns else [0] * len(df)
    out, odd = set(), set()
    for c, v, o, a in zip(df["Code"].astype(str).str.strip(), df["Volume"], df["Open"], amt):
        if _fin(v) == 0 and _fin(o) == 0:
            if _fin(a) == 0:
                out.add(c)
            else:
                odd.add(c)
    return out, True, odd


def kr_d1_split(cur_df, sessions, ok_prev, d1, no_trade, base_ok=None):
    """d1 을 거래 없는 종목과 나머지로 나누고 빈 d1 의 이유를 달아요 (2026-11-14 · 순수 함수). kr_d1_val20 의 d1 을 그대로 받아요.
    cur_df: 기준일 목록 · sessions · ok_prev: kr_d1_val20 에 준 것 · no_trade: kr_no_trade 의 코드.
    base_ok (2026-11-21): 직전 거래일 파일을 쓸 수 없는 날 KRX 기준가 × 지난 발행본 종가로 확인한 종목 (kr_d1_from_base 의 'ok') — d1 이 빈
    까닭은 ±30% 밖뿐이라 'range'. 그 밖의 종목은 예전처럼 'prev'. None 이면 예전 그대로.
    반환: (d1 {코드: %} — 거래 없는 종목은 빠져요, why {코드: D1_WHY 중 하나} — 빈 d1 마다, nt {코드: %} — 거래 없는 종목의 기준가 변화
    (kr_d1_val20 이 낸 값 · 거래가 없어 등락률로 보이지 않고 포트폴리오 평가 금액의 오늘 변화에만 써요 · 코넥스는 거래 없이도 값이 바뀔 수
    있어요), Counter {이유: 수})."""
    cur = _official_map(cur_df)
    prev = _official_map(sessions[0][1]) if sessions and ok_prev else {}
    out, why, nt = {}, {}, {}
    for code in cur:
        v = d1.get(code)
        if code in no_trade:
            why[code] = "noTrade"
            if v is not None:
                nt[code] = v
        elif v is not None:
            out[code] = v
        elif not (sessions and ok_prev):
            why[code] = "range" if base_ok and code in base_ok else "prev"
        elif not prev.get(code):
            why[code] = "new"
        else:
            why[code] = "range"
    return out, why, nt, collections.Counter(why.values())


# 2026-11-21: 직전 거래일 파일이 최종본이 아니거나 없는 날의 d1 (자원봉사 캐시가 며칠 멈췄다가 오늘 최종본만 올린 날).
# 사고 (시험 실행 44783218618 · 11-21 02:33 KST): 11-17 ~ 19 는 2차 출처(다음 × 야후)로 발행했고 (11-20 06:40 발행 · pxDate 11-19), 캐시에
# 11-20 최종본(23:23 KST 커밋)이 생겨 11-20 은 1차 출처 날이 됐어요. 그런데 11-17 ~ 19 파일의 마지막 커밋은 모두 장 마감 전 (11-19 14:52 ·
# 수능일 마감 16:30) 이라 직전 거래일 파일을 쓸 수 없어 → d1 0.0% · 필수 종목 d1 실패 → 발행이 멈췄어요 (다음 날 06:40 발행도 같았을 거예요).
# 이제: 오늘 최종본의 KRX 기준가 (Close − Changes · kr_ref_links 와 같은 관계) 가 지난 발행본(data.json · 관문이 git show HEAD 로 읽는 것과
# 같은 파일)의 그날 종가와 원 단위까지 같은 종목만 d1 = 오늘 공식 종가 ÷ 그 종가 − 1 (Jack 규칙 3: 두 독립 출처 — KRX 의 기준가와 우리가
# 두 출처로 확인해 발행한 종가). 지난 발행본의 pxDate 가 직전 거래일(KOSPI)일 때만 · 그 종목의 값이 그날 확인된 종가일 때만 (자기 가격 날짜
# pxd 가 있는 행 · 거래 없음 행은 아니에요). 다르면 (KRX 가 기준가를 새로 정한 날 · 잘못) · 지난 발행본에 없으면 · 오늘 파일에 기준가가 없으면
# d1 은 빈 칸 (d1Why prev — 직전 거래일 파일을 쓸 수 없음) 이고 까닭(D1_BASE_WHY)은 로그와 data.json d1Base 에 수와 예로 남아요. 추측하지 않아요.
# ±30% 와 거래 없음 규칙은 그대로예요 (kr_d1_split).
D1_BASE_WHY = ("diff", "noPub", "notConf", "noBase")
D1_BASE_KO = {"diff": "다름", "noPub": "지난 발행본에 없음", "notConf": "지난 발행본 값이 그날 확인된 종가가 아님 (거래 없음 · 자기 가격 날짜)",
              "noBase": "오늘 파일에 기준가 없음"}
D1_BASE_PUB_KO = {"none": "지난 발행본(data.json)을 읽지 못했어요", "day": "지난 발행본의 가격 날짜가 직전 거래일이 아니에요",
                  "src": "지난 발행본의 가격 출처가 공식 종가가 아니에요"}
KR_LIST_SRC_CACHE = "fdr_krx_data_cache"     # fetch_korea 의 list_src (1차 출처 날)
D1_BASE_EX = 12                              # 까닭마다 data.json d1Base.ex 와 로그에 적는 종목 수


def kr_prev_pub_closes(prev, want_prev):
    """지난 발행본(data.json)에서 직전 거래일(want_prev)의 확인된 종가 (2026-11-21 · 순수 함수).
    반환: (closes {코드: 원}, skip {코드} — 그날 확인된 종가가 아닌 행 (자기 가격 날짜 pxd · 거래 없음 noTrade · 같은 코드가 두 번), why).
    why 가 None 이 아니면 그 발행본은 쓸 수 없어요 (closes · skip 은 비어요): 'none' 없음 · 'day' pxDate ≠ want_prev ·
    'src' 가격 출처(listSrc · pxSrc)가 공식 종가 목록(1차 출처 최종본 · 2차 출처 다음 × 야후)이 아님 (지난 data.json 으로 만든 목록 등)."""
    if not isinstance(prev, dict) or not isinstance(prev.get("stocks"), list):
        return {}, set(), "none"
    day = str(prev.get("pxDate") or "")
    if want_prev is None or day != want_prev.isoformat():
        return {}, set(), "day"
    src = prev.get("pxSrc")
    if prev.get("listSrc") not in (KR_LIST_SRC_CACHE, PX_SRC_FB) or (src is not None and (
            not isinstance(src, dict) or src.get("px") not in (PX_SRC_LISTING, PX_SRC_FB) or src.get("date") not in (None, day))):
        return {}, set(), "src"
    closes, skip = {}, set()
    for x in prev["stocks"]:
        if not isinstance(x, dict) or x.get("cls") != "kr" or x.get("fund") or not x.get("t"):
            continue
        t = str(x["t"]).strip()
        if t in closes or t in skip:                 # 같은 코드가 두 번 — 어느 값인지 몰라요
            closes.pop(t, None)
            skip.add(t)
            continue
        if "pxd" in x or x.get("noTrade") is True:
            skip.add(t)
            continue
        p = _fin(x.get("price"))
        if p is not None and p > 0:
            closes[t] = p
    return closes, skip, None


def kr_d1_from_base(cur_df, closes, skip=(), max_abs=D1_MAX_KR, tol=KR_FB_CLOSE_TOL):
    """직전 거래일 파일을 쓸 수 없는 날의 d1 (2026-11-21 · 순수 함수): 오늘 목록 파일의 KRX 기준가 (Close − Changes) 가 지난 발행본의
    그날 종가(closes · kr_prev_pub_closes)와 원 단위까지(tol) 같은 종목만 d1 = 오늘 공식 종가 ÷ 그 종가 − 1 (%, 소수 둘째 자리 · ±max_abs 밖은
    빈 칸 — kr_d1_val20 과 같은 규칙). 오늘 공식 종가가 없는 종목은 보지 않아요 (kr_d1_split 도 그래요).
    반환: (d1 {코드: %}, st {코드: 'ok' 또는 D1_BASE_WHY 중 하나}, ex {까닭: [(코드, 지난 발행본 종가, 기준가)]})."""
    skip = set(skip)
    d1, st, ex = {}, {}, collections.defaultdict(list)
    for _, r in cur_df.iterrows():
        code = str(r["Code"]).strip()
        c = kr_official_close(r)
        if not c:
            continue
        cl, ch = _fin(r.get("Close")), _fin(r.get("Changes"))
        base = None if cl is None or ch is None else cl - ch
        p = closes.get(code)
        if code in skip:
            w = "notConf"
        elif p is None:
            w = "noPub"
        elif base is None or base <= 0:
            w = "noBase"
        elif abs(base - p) > tol:
            w = "diff"
        else:
            w = "ok"
            v = (c / p - 1) * 100
            if abs(v) <= max_abs + D1_LIMIT_EPS:
                d1[code] = round(v, 2)
        st[code] = w
        if w != "ok":
            ex[w].append((code, p, base))
    return d1, st, dict(ex)


def d1_base_record(want_prev, prev, pub_why, st, ex, names=None, n=None, n_ex=D1_BASE_EX):
    """data.json d1Base (2026-11-21 · 순수 함수): 직전 거래일 파일을 쓸 수 없던 날에만 — 직전 거래일 · 지난 발행본의 가격 날짜 ·
    쓸 수 없던 까닭(why · D1_BASE_PUB_KO) · 본 종목 수(n · 처리한 목록의 오늘 공식 종가가 있는 종목 · 주지 않으면 st 의 수) · 확인(ok) ·
    까닭마다의 수 · 예 (ex). 지난 발행본을 쓸 수 없던 날(why)은 st 가 비어 ok 와 까닭마다의 수가 0 이에요."""
    names = names or {}
    cnt = collections.Counter(st.values())
    out = {"v": 1, "day": want_prev.isoformat() if want_prev else None,
           "pub": (str(prev.get("pxDate")) if isinstance(prev, dict) and prev.get("pxDate") else None),
           "why": pub_why, "n": len(st) if n is None else n, "ok": cnt.get("ok", 0)}
    for k in D1_BASE_WHY:
        out[k] = cnt.get(k, 0)
    out["ex"] = {k: [f"{c} {names.get(c, '')}".strip() + (f" {p:,.0f}→{b:,.0f}" if k == "diff" else "")
                     for c, p, b in sorted(v)[:n_ex]] for k, v in sorted((ex or {}).items()) if v}
    return out


def kr_d1_base_day(cur_df, prev, want_prev):
    """직전 거래일 파일을 쓸 수 없는 날의 d1 한 번에 (2026-11-21 · 순수 함수 · fetch_korea 가 ok_prev 가 아닐 때만 불러요).
    반환: (d1 {코드: %}, base_ok {코드} — 두 출처로 기준가를 확인한 종목 (kr_d1_split 의 base_ok · 지난 발행본을 쓸 수 없으면 None),
    data.json d1Base)."""
    closes, skip, why = kr_prev_pub_closes(prev, want_prev)
    d1, st, ex = ({}, {}, {}) if why else kr_d1_from_base(cur_df, closes, skip)
    names = dict(zip(cur_df["Code"].astype(str).str.strip(), cur_df["Name"].astype(str))) if "Name" in cur_df.columns else {}
    rec = d1_base_record(want_prev, prev, why, st, ex, names, n=len(_official_map(cur_df)) if why else None)
    return d1, (None if why else {c for c, w in st.items() if w == "ok"}), rec


# 2026-11-21 (#161 리뷰 M2): 같은 기준일을 다시 도는 실행의 d1. 사고 모양 (리뷰 재현): 06:40 에 기준일 D 를 2차 출처(다음 × 야후)로 발행했고, 그 뒤
# 자원봉사 캐시에 D 최종본이 생겼는데 D−1 파일은 아직 장중 값이에요 → 다음 실행은 1차 출처 날 · 같은 기준일 D 이고 직전 거래일 파일을 쓸 수 없어
# kr_d1_base_day 를 불러요. 그런데 지난 발행본은 그날 아침의 D 발행본이라 (pxDate D · 직전 거래일이 아님) 모든 d1 이 빈 칸 → '필수 종목 d1' 실패 →
# 13:37 · 14:47 · 바깥 타이머 실행마다 빨간 실행이었어요 (3시간 쉼은 2차 출처 날의 다시 도는 실행만 봐요).
# 이제: 지난 발행본의 기준일이 이 실행과 같으면 그 발행본의 d1 (같은 D−1 기준 · 이미 확인돼 관문을 통과한 값) 을, 오늘 공식 종가가 그 발행본의 가격과
# 원 단위까지 같은 종목만 그대로 써요 (그 행에 pxd · noTrade 가 없을 때만 · kr_prev_pub_closes 와 같은 규칙). 가격이 다르거나 · 지난 발행본에 없거나 ·
# 지난 발행본도 d1 이 빈 칸이면 빈 칸 (d1Why prev · 지난 발행본이 ±30% 밖(range)이었으면 range) — 까닭마다 수와 예를 로그와 d1Base 에 (same: 1).
# 지난 발행본의 기준일이 이 실행보다 앞이면 (#163 의 길) 예전 그대로예요.
# #161 리뷰 3차 A-S1: 오늘 목록 파일에 KRX 기준가 (Close − Changes) 가 있으면, 다시 쓰는 d1 이 그 기준가로 본 등락률 (오늘 공식 종가 ÷ 기준가 − 1 ·
# 소수 둘째 자리) 과 0.01 안일 때만 다시 써요. 다르면 (아침의 기준이 두 출처의 직전 거래일 종가였는데 KRX 가 기준가를 새로 정한 날 — 권리락 · 분할 등)
# 빈 칸 (d1Why prev · 까닭 krx · 로그와 d1Base 에 수와 예).
D1_SAME_KRX_TOL = 0.01
D1_SAME_KO = {"diff": "오늘 공식 종가가 앞선 발행본의 가격과 다름", "noPub": "앞선 발행본에 없음",
              "notConf": "앞선 발행본 값이 그날 확인된 종가가 아님 (거래 없음 · 자기 가격 날짜)", "noD1": "앞선 발행본도 d1 빈 칸",
              "krx": "앞선 발행본의 d1 이 오늘 파일의 KRX 기준가로 본 등락률과 다름"}


def kr_d1_same_day(cur_df, prev, px_date, want_prev, max_abs=D1_MAX_KR, tol=KR_FB_CLOSE_TOL):
    """같은 기준일 지난 발행본의 d1 다시 쓰기 (2026-11-21 · #161 리뷰 M2 · 순수 함수 · fetch_korea 가 kr_d1_base_day 의 까닭이 'day' 일 때만 불러요).
    지난 발행본(prev)의 pxDate 가 이 실행의 기준일(px_date)이 아니거나 그 발행본을 쓸 수 없으면 (kr_prev_pub_closes 의 까닭) None — 부르는 쪽은
    kr_d1_base_day 의 결과(모두 빈 칸 · 그 까닭)를 그대로 써요. 반환: (d1 {코드: %}, base_ok {코드} — d1 이 있거나 지난 발행본이 range 였던 종목
    (kr_d1_split 이 빈 d1 을 range 로) · data.json d1Base (same 1 · from 그 발행본의 publishedAt · noD1 수))."""
    closes, skip, why = kr_prev_pub_closes(prev, px_date)
    if why:
        return None
    rows = {str(x["t"]).strip(): x for x in prev["stocks"]
            if isinstance(x, dict) and x.get("cls") == "kr" and not x.get("fund") and x.get("t") and str(x["t"]).strip() in closes}
    d1, base_ok, st, ex = {}, set(), {}, collections.defaultdict(list)
    for _, r in cur_df.iterrows():
        code = str(r["Code"]).strip()
        c = kr_official_close(r)
        if not c:
            continue
        p = closes.get(code)
        if code in skip:
            w = "notConf"
        elif p is None:
            w = "noPub"
        elif abs(c - p) > tol:
            w = "diff"
        else:
            v = _fin(rows[code].get("d1"))
            cl, ch = _fin(r.get("Close")), _fin(r.get("Changes"))
            base = None if cl is None or ch is None or cl - ch <= 0 else cl - ch
            kv = round((c / base - 1) * 100, 2) if base else None       # 오늘 파일의 KRX 기준가로 본 등락률 (없으면 맞춰 보지 않아요)
            in_range = v is not None and abs(v) <= max_abs + D1_LIMIT_EPS
            if in_range and kv is not None and abs(kv - v) > D1_SAME_KRX_TOL + 1e-9:
                w = "krx"
            elif in_range:
                w = "ok"
                d1[code] = v
                base_ok.add(code)
            elif v is not None or rows[code].get("d1Why") == "range":
                if kv is not None and abs(kv) <= max_abs + D1_LIMIT_EPS:
                    w = "krx"                                # 아침은 ±30% 밖인데 KRX 기준가로는 안 — 기준이 달라요
                else:
                    w = "ok"                                 # 지난 발행본도 ±30% 밖 — 같은 기준 · 빈 칸의 까닭은 range
                    base_ok.add(code)
            else:
                w = "noD1"
        st[code] = w
        if w == "krx":
            ex[w].append((code, _fin(rows[code].get("d1")), kv))
        elif w != "ok":
            ex[w].append((code, p, c))
    names = dict(zip(cur_df["Code"].astype(str).str.strip(), cur_df["Name"].astype(str))) if "Name" in cur_df.columns else {}
    rec = d1_base_record(want_prev, prev, None, st, {k: v for k, v in ex.items() if k not in ("noD1", "krx")}, names)
    rec["same"] = 1
    rec["from"] = str(prev.get("publishedAt") or "")
    rec["noD1"] = sum(1 for w in st.values() if w == "noD1")
    rec["krx"] = sum(1 for w in st.values() if w == "krx")
    if ex.get("noD1"):                                       # (다름의 예는 앞선 발행본 가격 → 오늘 공식 종가 · d1_base_record 와 같은 모양)
        rec["ex"]["noD1"] = [f"{c} {names.get(c, '')}".strip() for c, _, _ in sorted(ex["noD1"])[:D1_BASE_EX]]
    if ex.get("krx"):                                        # 앞선 발행본 d1 → KRX 기준가로 본 등락률 (%)
        rec["ex"]["krx"] = [f"{c} {names.get(c, '')}".strip() + (f" {a:+.2f}%→{b:+.2f}%" if a is not None and b is not None else "")
                            for c, a, b in sorted(ex["krx"], key=lambda e: e[0])[:D1_BASE_EX]]
    return d1, base_ok, rec


def d1_base_note(rec):
    """d1Base 한 줄 (2026-11-21 · 순수 함수 · 로그). 반환 (크게 남길지, 글) — 직전 거래일 최종본이 없는 날이라 늘 크게 (!!)."""
    if rec.get("same"):                     # #161 리뷰 M2: 같은 기준일 지난 발행본의 d1 (kr_d1_same_day)
        txt = (f"d1: 직전 거래일 {rec.get('day')} 최종본이 없고 지난 발행본이 같은 기준일 {rec.get('pub')} ({rec.get('from') or '?'}) 이라, 오늘 공식 종가가 "
               f"그 발행본의 가격과 원 단위까지 같은 종목은 그 발행본의 d1 을 그대로 써요 (같은 직전 거래일 기준 · 이미 확인된 값): {rec['ok']:,} / {rec['n']:,}"
               f" · 가격이 다름 {rec['diff']:,} · 앞선 발행본에 없음 {rec['noPub']:,} · 그날 확인된 종가가 아님 {rec['notConf']:,} · 앞선 발행본도 d1 빈 칸 "
               f"{rec.get('noD1', 0):,} · KRX 기준가로 본 등락률과 다름 {rec.get('krx', 0):,} (나머지는 d1 빈 칸 · d1Why prev)")
        for k in ("diff", "noPub", "notConf", "noD1", "krx"):
            if (rec.get("ex") or {}).get(k):
                txt += f" — {D1_SAME_KO[k]}: {', '.join(rec['ex'][k])}{' …' if rec.get(k, 0) > len(rec['ex'][k]) else ''}"
        return True, txt
    if rec.get("why"):
        return True, (f"d1: 직전 거래일 {rec.get('day')} 최종본이 없고 {D1_BASE_PUB_KO.get(rec['why'], rec['why'])} (지난 발행본 pxDate "
                      f"{rec.get('pub')}) — KRX 기준가를 확인할 두 번째 출처가 없어 d1 을 비워요 {rec.get('n', 0):,}종목")
    txt = (f"d1: 직전 거래일 최종본이 없어 KRX 기준가 × 지난 발행본 종가로 확인 {rec['ok']:,} / {rec['n']:,} · 다름 {rec['diff']:,}"
           f" · 지난 발행본에 없음 {rec['noPub']:,} · 그날 확인된 종가가 아님 {rec['notConf']:,} · 기준가 없음 {rec['noBase']:,}"
           f" (직전 거래일 {rec.get('day')} · 지난 발행본 pxDate {rec.get('pub')} · 확인 못 한 종목은 d1 빈 칸 · d1Why prev)")
    for k in D1_BASE_WHY:
        if (rec.get("ex") or {}).get(k):
            txt += f" — {D1_BASE_KO[k]}: {', '.join(rec['ex'][k])}{' …' if rec.get(k, 0) > len(rec['ex'][k]) else ''}"
    return True, txt


def _txt(x):
    """원본 표의 글자. 비었거나 nan·None·'-' 면 빈 문자열 (화면에 'nan' 이 나오지 않게)."""
    if x is None:
        return ""
    if isinstance(x, float) and not np.isfinite(x):
        return ""
    t = str(x).strip()
    return "" if t in ("", "nan", "NaN", "None", "null", "undefined") or t in DASHES else t


IND_CARRY_WARN_DAYS = 14   # 이어 쓴 업종 글자가 이보다 오래되면 관문이 경고해요 (validate_data 와 같은 값 · 2026-11-19)


def kr_prev_desc(prev):
    """지난 발행본(data.json)의 국내 종목 업종 · 주요제품 {코드: (업종, 주요제품)} 과 그 업종 글자의 날짜 (2026-11-19).
    날짜: 지난 발행본이 이미 이어 쓴 글자가 있으면 그 indSrc.asOf (더 오래된 날), 아니면 지난 발행 날짜. 읽지 못한 dk 수도 돌려줘요.
    지난 발행본이 DART 회사 정보로 채운 종목(indSrc.dartT) · 보통주를 따른 우선주(indSrc.prefT)는 빼요 — KRX 글자로 이어 쓴 것처럼 보이지
    않게, 오늘 다시 채우거나 따라요 (그래야 관문이 오늘 값을 확인해요)."""
    out, bad = {}, 0
    src = (prev or {}).get("indSrc") or {}
    dart = {t for key in ("dartT", "prefT") if isinstance(src.get(key), dict) for t in src[key]}
    for x in (prev or {}).get("stocks") or []:
        if x.get("cls") != "kr" or not x.get("t") or not x.get("dk") or str(x["t"]) in dart:
            continue
        p = kr_desc_parse(x["dk"])
        if p is None:
            bad += 1
            continue
        if p[0]:
            out[str(x["t"])] = p
    pi = (prev or {}).get("indSrc") or {}
    day = pi.get("asOf") if pi.get("carried") else str((prev or {}).get("publishedAt") or "")[:10] or None
    return out, day, bad


def kr_desc_carry(desc, prev_desc, codes):
    """KRX-DESC 에 업종이 없는 종목은 지난 발행본의 업종 · 주요제품을 이어 써요 (2026-11-19 · Jack: "carry forward the last known industry,
    with a loud log line" · 순수 함수). 반환: (desc, 이어 쓴 코드들, 업종이 없는데 지난 발행본에도 없는 코드들)."""
    out, carried, none = dict(desc), [], []
    for c in sorted(codes):
        if (out.get(c) or ("", ""))[0]:
            continue
        p = prev_desc.get(c)
        if p and p[0]:
            out[c] = p
            carried.append(c)
        else:
            none.append(c)
    return out, carried, none


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


# ────────────────────────────────────────────────────────────
# 2026-11-19 (Jack: "Later, new listings take their industry from DART's company records." · "move the DART company-record industry
# mapping up" · ~17:45 KST: "don't show 통계청 industry names as new groups. Map each official code to our existing industry groups, so
# 업종 lists, industry averages and 업종별 등락 keep one naming system. Report any codes that don't map cleanly." · Q2 yes: preferred
# shares copy their common stock's industry words and sector):
# KRX-DESC 에도 지난 발행본에도 업종 글자가 없는 국내 보통주는 DART 기업개황 업종 코드(fetch_ksic 가 이미 받은 값 · DART 를 새로 부르지
# 않아요)의 11차 소분류(3자리)가 우리 두 업종 체계에 깔끔히 맞을 때만 (data/ksic_map_kr.csv status ok) 채워요:
#   · 설명(dk) 앞에 그 공식 이름 — KRX 글자도 같은 이름이었고, 그 회사 한 줄 설명에만 보여요 (어느 화면도 dk 로 무리를 짓지 않아요)
#   · 예전 뱁새 업종 키 s 는 표의 키 (기존 SECTORS 키 · 그 종목의 2.0 그룹과 같은 뜻 — validate_data.IND_SECTOR_KR)
#   · 2.0 그룹(ind · indName)은 예전처럼 assign_industries 가 업종 코드로 정해요 (기존 industry_groups.csv 이름)
# 깔끔히 맞지 않는 코드(짝 없음 · 갈림 · 금융 · 집합 투자업)는 채우지 않고 종목 · 코드 · 이름을 크게 남겨요.
# 우선주는 보통주의 업종 글자와 업종 키를 따르고, 2.0 그룹이 보통주와 다르면 맞춰요 (고정표에서 다르게 정한 우선주는 빼요).
# 채운 값은 관문과 같은 함수(validate_data.ind_fill_bad)로 바로 확인해 틀린 행은 되돌리고 data.json ownDrop.indFill 에 남겨요
# (Jack 의 상시 규칙 · corp.json 이 업종 키를 옮겨 쓰기 전이라 여기서 해요 · 그 뒤로 dk · s · ind 를 바꾸는 단계는 없어요).
# ────────────────────────────────────────────────────────────
KSIC_MAP_MISS = {"none": "mapNone", "ambiguous": "mapAmbig", "financial": "mapFin", "fund": "mapFund"}


def ksic_map_kr_rows(names, kmap, groups):
    """data/ksic_map_kr.csv 의 줄 [ksic, name, s, ind, status, why] — 11차 소분류(3자리) 코드마다 (순수 함수 · 표를 다시 만들 때 ·
    tests/test_ind_dart.py 가 커밋한 표와 같은지 봐요). s = map_sector_kr(이름) — KRX 글자를 바꾸던 그 규칙 · ind = 그 코드와 아래 4·5자리
    코드가 가는 2.0 그룹 (industry_map.csv) · groups: industry_groups.csv {그룹: {financial …}}."""
    fin_g = {g for g, r in groups.items() if str(r.get("financial") or "").strip() == "yes"}
    rows = []
    for c in sorted(x for x in names if len(x) == IND_DART_DIGITS):
        n, s = names[c], map_sector_kr(names[c], "")
        reach = sorted({ksic_group(k, kmap) for k in names if k.startswith(c)} - {None})
        odd = [g for g in reach if not IND_SECTOR_KR.get(g)]          # 짝이 () 이거나 없는 그룹
        if c == KR_FUND_KSIC:
            st, why = "fund", "집합 투자업 — 상장 펀드일 수 있어요"
        elif s in FIN_SECS or any(g in fin_g for g in reach):
            st, why = "financial", "금융 — 2.0 의 EV 멀티플 · 금융 문구가 바뀌어요"
        elif s == "etc":
            st, why = "none", "예전 뱁새 업종 키를 찾지 못함 (기타)"
        elif not reach:
            st, why = "none", "2.0 업종 그룹 없음"
        elif odd:
            st, why = "none", f"예전 뱁새에 짝이 없는 2.0 그룹 {'·'.join(odd)}"
        elif c in KSIC_LENS_MISFIT:
            st, why = "ambiguous", KSIC_LENS_MISFIT[c]
        elif any(s not in IND_SECTOR_KR[g] for g in reach):
            st, why = "ambiguous", f"예전 뱁새 {s} 와 2.0 {'·'.join(g for g in reach if s not in IND_SECTOR_KR[g])} 가 다른 업종"
        else:
            st, why = "ok", ""
        rows.append([c, n, s, "·".join(reach), st, why])
    return rows


def kr_ind_dart_plan(stocks, no_text, ksic, kmap_kr, digits=IND_DART_DIGITS):
    """업종 글자를 DART 로 채울 계획 — 보통주만 (우선주는 kr_ind_pref_copy). (순수 함수 · DART 를 부르지 않아요)
    no_text: KRX-DESC 에도 지난 발행본에도 업종 글자가 없는 종목코드 · ksic: {종목코드: DART 업종 코드} (fetch_ksic) · kmap_kr: 11차 소분류 →
    {name, s, status …} (validate_data.load_ksic_map_kr). 2.0 그룹(ind)이 이미 정해진 뒤에 불러요 (assign_industries).
    반환: (fill {종목: (이름, KSIC 코드, 업종 키)}, miss {이유: [종목]}) — 이유 fund 펀드 · noCode 코드 없음 · noName 표에 없는 코드 ·
    mapNone · mapAmbig · mapFin · mapFund 표에서 깔끔히 맞지 않는 코드 · noGroup 2.0 그룹 없음 (발행하지 않는 종목은 건너뛰어요)."""
    by_t = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
    fill, miss = {}, collections.defaultdict(list)
    for t in sorted(set(no_text)):
        s = by_t.get(t)
        if s is None or is_preferred(t):
            continue
        if s.get("etf") or s.get("fund"):
            miss["fund"].append(t)
            continue
        code = str(ksic.get(t) or "").strip()
        if not code:
            miss["noCode"].append(t)
            continue
        row = kmap_kr.get(code[:digits]) if len(code) >= digits else None
        if row is None:
            miss["noName"].append(t)
            continue
        if row["status"] != "ok":
            miss[KSIC_MAP_MISS[row["status"]]].append(t)
            continue
        if not s.get("ind"):
            miss["noGroup"].append(t)
            continue
        ok_s = IND_SECTOR_KR.get(s["ind"], ())          # 고정표 · 주요제품 · 작은 그룹 합치기로 코드와 다른 그룹이 될 수 있어요
        sec = row["s"] if s.get("s") in (None, "", "etc") else s["s"]
        if not ok_s:
            miss["mapNone"].append(t)
            continue
        if sec not in ok_s:
            miss["mapAmbig"].append(t)
            continue
        fill[t] = (row["name"], code, sec)
    return fill, dict(miss)


def kr_ind_dart_apply(stocks, fill):
    """계획(fill)대로 설명(dk) 앞에 업종 이름을 붙이고 업종 키 s 를 정해요 (kr_desc_text 순서). 업종 글자가 이미 있거나 설명을 읽지 못하는
    종목은 그대로 둬요. 바꿀 값을 모두 먼저 계산하고 마지막에 한꺼번에 넣어요 (중간에 멈춰도 일부만 바뀌지 않게). (순수 함수)
    반환: (채운 {종목: KSIC 코드}, 되돌릴 값 {종목: {dk, s}})."""
    todo = []
    for s in stocks:
        v = fill.get(s.get("t")) if s.get("cls") == "kr" else None
        dk = s.get("dk")
        if not v or not (dk is None or isinstance(dk, str)):
            continue
        p = kr_desc_parse(dk) if dk else ("", "")
        if p is None or p[0]:
            continue
        name, code, sec = v
        todo.append((s, name + (" · " + dk if dk else ""), sec, code))
    undo = {s["t"]: {"dk": s.get("dk"), "s": s.get("s")} for s, _, _, _ in todo}
    for s, dk, sec, _ in todo:
        s["dk"], s["s"] = dk, sec
    return {s["t"]: code for s, _, _, code in todo}, undo


def kr_ind_pref_copy(stocks, no_text, over=()):
    """업종 글자가 없는 우선주는 보통주(코드 앞 5자리 + 0)의 업종 글자와 업종 키 s 를 따라요 (Jack Q2, 2026-11-19). 2.0 그룹(ind · indName)이
    보통주와 다르면 맞춰요 — 고정표(over)에서 다르게 정한 우선주는 건드리지 않아요. 모두 계산한 뒤 한꺼번에 넣어요. (순수 함수)
    반환: (따른 {우선주: 보통주}, miss {이유: [우선주]}, 되돌릴 값 {우선주: {dk, s, ind, indName}}, 2.0 그룹을 맞춘 수)."""
    by_t = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
    miss, todo = collections.defaultdict(list), []
    for t in sorted(set(no_text)):
        s = by_t.get(t)
        if s is None or s.get("etf") or s.get("fund") or not is_preferred(t):
            continue
        c = by_t.get(t[:5] + "0")
        if c is None:
            miss["prefNoCommon"].append(t)
            continue
        cp = kr_desc_parse(c["dk"]) if isinstance(c.get("dk"), str) else None
        if not cp or not cp[0]:
            miss["prefCommonNone"].append(t)
            continue
        if t in over and s.get("ind") != c.get("ind"):
            miss["prefOver"].append(t)
            continue
        dk = s.get("dk")
        p = ("", "") if dk in (None, "") else kr_desc_parse(dk)
        if p is None or p[0]:
            miss["noParse"].append(t)
            continue
        todo.append((s, c, cp[0] + (" · " + dk if dk else "")))
    undo = {s["t"]: {k: s.get(k) for k in ("dk", "s", "ind", "indName")} for s, _, _ in todo}
    n_ind = 0
    for s, c, dk in todo:
        s["dk"], s["s"] = dk, c.get("s")
        if s.get("ind") != c.get("ind"):
            n_ind += 1
            for k in ("ind", "indName"):
                if c.get(k) is None:
                    s.pop(k, None)
                else:
                    s[k] = c[k]
    return {s["t"]: c["t"] for s, c, _ in todo}, dict(miss), undo, n_ind


def kr_ind_restore(s, before):
    """되돌리기: before 의 칸을 그대로 (없던 칸은 지워요)."""
    for k, v in before.items():
        if v is None:
            s.pop(k, None)
        else:
            s[k] = v


def kr_ind_own_drop(stocks, ind_src, undo, names=None, kmap_kr=None):
    """Jack 의 상시 규칙 (2026-11-19): 관문과 같은 함수(validate_data.ind_fill_bad)로 채운 값을 확인해 틀린 행은 되돌리고(채우기 전 값) 남은
    것은 발행해요. 되돌린 보통주를 따랐던 우선주도 다음 번 확인에서 되돌려요. 반환: 기록 {n, rows} (data.json ownDrop.indFill) · 되돌린 종목."""
    by_t = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
    dropped, rows = [], []
    for _ in range(3):
        bad = [b for b in ind_fill_bad(stocks, ind_src, names, kmap_kr) if b["t"] in undo and b["t"] not in dropped]      # 엄격 (발행 전)
        if not bad:
            break
        rows += ind_fill_rows(bad, stocks)
        for b in bad:
            kr_ind_restore(by_t[b["t"]], undo[b["t"]])
            for key, n in (("dartT", "dart"), ("prefT", "pref")):
                if isinstance(ind_src.get(key), dict) and ind_src[key].pop(b["t"], None) is not None:
                    ind_src[n] = len(ind_src[key])
            dropped.append(b["t"])
    left = ind_fill_bad(stocks, ind_src, names, kmap_kr)
    log((f"  !! {IND_FILL_CHECK}: {len(dropped)}건 되돌리고 발행 — " + "; ".join(rows[:30]) if dropped else
         f"· {IND_FILL_CHECK}: 0건 되돌림 (DART {len(ind_src.get('dartT') or {}):,} · 우선주 {len(ind_src.get('prefT') or {}):,} 확인)")
        + (f" · !! 되돌리지 못한 틀린 값 {len(left)}: " + "; ".join(ind_fill_rows(left, stocks)[:10]) + " — 관문이 봐요" if left else ""))
    return {"n": len(dropped), "rows": rows[:30]}, dropped


def kr_ind_fill(stocks, no_text, ksic, kmap_kr, ind_src, over=(), names=None, map_sha=None, table_err=None):
    """DART 로 보통주 채우기 → 우선주는 보통주를 따름 → 같은 확인으로 틀린 행 되돌리기 → indSrc 에 출처 (dart · dartT · pref · prefT ·
    prefInd · left · dartMiss) · 크게 남겨요. 반환: data.json ownDrop.indFill 기록 {n, rows}.
    고장 나도 실행은 멈추지 않아요 (업종 글자는 보탬일 뿐 · 멈추면 하루치 가격이 낡아요): 채운 것을 모두 되돌리고 indSrc.dartErr ·
    left 없음 — 관문이 경고해요. 업종 표를 읽지 못한 날(kmap_kr None · table_err): DART 로 채우지 않고 우선주만 따라요 (dartErr).
    names · map_sha: 11차 표 · 업종 표의 판 (indSrc.mapSha 로 남겨 관문이 표가 바뀐 뒤의 옛 채움을 막지 않게)."""
    ind_src = ind_src if isinstance(ind_src, dict) else {}
    undo = {}
    if map_sha is not None:
        ind_src["mapSha"] = map_sha
    try:
        if kmap_kr is None:
            by_t0 = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
            commons = sorted(t for t in set(no_text) if t in by_t0 and not is_preferred(t))
            fill, miss = {}, {"noTable": [t for t in commons if not by_t0[t].get("etf") and not by_t0[t].get("fund")],
                              "fund": [t for t in commons if by_t0[t].get("etf") or by_t0[t].get("fund")]}
            miss = {k: v for k, v in miss.items() if v}
            ind_src["dartErr"] = f"table:{table_err or '없음'}"
        else:
            fill, miss = kr_ind_dart_plan(stocks, no_text, ksic, kmap_kr)
        done, u1 = kr_ind_dart_apply(stocks, fill)
        undo.update(u1)
        pdone, pmiss, u2, n_ind = kr_ind_pref_copy(stocks, no_text, over)
        undo.update(u2)
        for k, v in pmiss.items():
            miss.setdefault(k, []).extend(v)
        # 계획했지만 적용하지 않은 종목 → '설명을 읽지 못함' (크게). 만든 방법상 생기지 않아요: no_text 는 kr_desc_carry 가 업종 글자를
        # 찾지 못한 종목이고 dk 는 그 뒤 kr_desc_text 로 만든 글이라 늘 읽혀요. 업종 글자가 있는 종목이 여기 오면 이름과 달리 '이미 글자 있음' 이에요
        for t in sorted(set(fill) - set(done)):
            miss.setdefault("noParse", []).append(t)
        ind_src.update({"dart": len(done), "dartT": dict(sorted(done.items())), "pref": len(pdone), "prefT": dict(sorted(pdone.items())),
                        "prefInd": n_ind})
        rec, dropped = kr_ind_own_drop(stocks, ind_src, undo, names, kmap_kr)
        if dropped:
            miss.setdefault("dropped", []).extend(dropped)
    except Exception as e:
        by_t = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
        for t, before in undo.items():
            if t in by_t:
                kr_ind_restore(by_t[t], before)
        log(f"  !! 업종 채우기 실패 ({type(e).__name__}: {str(e)[:160]}) — 채운 {len(undo):,}종목을 되돌리고 업종 글자 없이 발행해요 (관문이 경고해요)")
        ind_src.update({"dart": 0, "dartT": {}, "pref": 0, "prefT": {}, "prefInd": 0, "left": None, "dartMiss": {},
                        "dartErr": type(e).__name__})
        return {"n": 0, "rows": [], "err": type(e).__name__}
    left = sum(len(v) for k, v in miss.items() if k not in IND_MISS_OK)
    ind_src.update({"left": left, "dartMiss": {k: len(v) for k, v in sorted(miss.items())}})
    if ind_src["dart"] and "DART" not in str(ind_src.get("from") or ""):
        ind_src["from"] = f"{ind_src.get('from') or 'KRX-DESC'} + DART"
    names_of = {s["t"]: s.get("nk") or "" for s in stocks if s.get("cls") == "kr"}
    by_t = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
    dart_t = ind_src["dartT"]
    n_common = sum(1 for t in set(no_text) if t in by_t and not is_preferred(t) and not by_t[t].get("etf") and not by_t[t].get("fund"))
    why = " · ".join(f"{IND_MISS_KO.get(k, k)} {len(v):,}: " + ", ".join(f"{t} {names_of.get(t, '')}" for t in v[:6])
                     for k, v in sorted(miss.items()) if k not in IND_MISS_OK and v)
    log(f"{'  !! ' if n_common or left else '· '}업종 DART 회사 정보로 채움 {len(dart_t):,} / {n_common:,} · 우선주가 보통주를 따름 "
        f"{ind_src['pref']:,} (2.0 그룹을 맞춘 우선주 {n_ind:,}) · 그래도 업종 글자 없음 {left:,}" + (f" ({why})" if why else "")
        + "".join(f" · {IND_MISS_KO[k]} {len(miss[k]):,}" for k in IND_MISS_OK if miss.get(k))
        + (" — 11차 소분류 이름으로 채우고 업종 키는 우리 업종 표(data/ksic_map_kr.csv)에서. 예: "
           + ", ".join(f"{t} {names_of.get(t, '')} {fill[t][0]} ({c} → {fill[t][2]})" for t, c in list(dart_t.items())[:5]) if dart_t else ""))
    odd = [t for k in KSIC_MAP_MISS.values() for t in miss.get(k, [])]
    if odd:
        log(f"  !! 업종 코드가 우리 업종에 깔끔히 맞지 않아 채우지 않은 종목 {len(odd):,}개 (예전처럼 업종 글자 없이 · 기타): "
            + ", ".join(f"{t} {names_of.get(t, '')} ({ksic.get(t)} {kmap_kr[str(ksic.get(t))[:IND_DART_DIGITS]]['name']} · "
                        f"{kmap_kr[str(ksic.get(t))[:IND_DART_DIGITS]]['status']})" for t in odd[:15])
            + (f" — 집합 투자업 코드: 상장 펀드면 KR_LISTED_FUNDS 에 넣고, 회사면 그대로 둬요 (사람이 판단)" if miss.get("mapFund") else ""))
    try:
        n_chk, diff = kr_ind_word_check(stocks, ksic, {c: v["name"] for c, v in (kmap_kr or {}).items()},
                                        skip=set(dart_t) | set(ind_src["prefT"]))
        log(f"{'  !! ' if diff else '· '}업종 글자 확인 (막지 않아요): KRX · 이어 쓴 업종 글자와 DART 업종 코드의 11차 소분류 이름이 다른 종목 "
            f"{len(diff):,} / {n_chk:,} (띄어쓰기 빼고)"
            + (f" — 예: {'; '.join(diff[:8])}. DART 기록이 예전(10차) 번호이거나 KRX 와 분류가 달라요 — 그런 종목을 DART 로 채우면 이름이 "
               "틀릴 수 있어요 (관문은 잡지 못해요)" if diff else ""))
    except Exception as e:
        log(f"  !! 업종 글자 확인 실패 ({type(e).__name__}: {str(e)[:120]}) — 채우기는 그대로예요")
    return rec


def kr_ind_word_check(stocks, ksic, names, skip=(), digits=IND_DART_DIGITS):
    """2026-11-19 리뷰: DART 업종 코드가 아직 10차 번호이면 11차 표의 같은 번호 이름이 틀려요 (관문은 잡지 못해요). 업종 글자(KRX · 이어 씀)와
    DART 코드가 둘 다 있는 보통주에서 11차 소분류 이름과 글자를 띄어쓰기 빼고 맞춰 봐요 — 다른 종목이 늘면 로그로 보여요 (막지 않아요).
    skip: 이번 실행에 채운 종목 (같은 것끼리 비교). (순수 함수) 반환: (맞춰 본 수, ['종목 이름: 글자 ≠ 이름 (코드)' …])."""
    n, diff = 0, []
    for s in stocks:
        t = s.get("t")
        if s.get("cls") != "kr" or s.get("etf") or s.get("fund") or t in skip or is_preferred(t or "") or not s.get("dk"):
            continue
        p = kr_desc_parse(s["dk"])
        code = str(ksic.get(t) or "").strip()
        if not p or not p[0] or len(code) < digits:
            continue
        n += 1
        name = names.get(code[:digits])
        if not name or name.replace(" ", "") != p[0].replace(" ", ""):
            diff.append(f"{t} {s.get('nk') or ''}: {p[0]} ≠ {name or '표에 없음'} ({code})")
    return n, diff


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


def select_kr_universe(listing, max_n, keep=()):
    """시가총액 큰 순으로 max_n 개. 꼭 있어야 할 종목이 빠지면 예외. (순수 함수)
    시가총액이 비면 정렬이 안 돼 가나다순이 남아요(2026-10 사고). 그래서 결과를 꼭 확인합니다.
    keep (2026-11-21 · #161 리뷰 M1): 상위 max_n 밖이어도 목록에 있으면 처리하는 코드 (같은 기준일 2차 출처 발행본의 국내 종목 · kr_same_day_keep).
    상위 max_n 뒤에 시가총액 순으로 붙여요 (결과도 시가총액 순). 비면 예전 그대로."""
    listing = listing.copy()
    for c in ("Marcap", "Amount"):
        listing[c] = pd.to_numeric(listing[c], errors="coerce")
    listing = listing.sort_values("Marcap", ascending=False, na_position="last")
    keep = {str(c).strip() for c in keep or ()}
    if keep:
        rest = listing.iloc[max_n:]
        listing = pd.concat([listing.head(max_n), rest[rest["Code"].astype(str).str.strip().isin(keep)]])
    else:
        listing = listing.head(max_n)
    missing = [c for c in MUST_KR if c not in set(listing["Code"])]
    if missing:
        raise RuntimeError(f"!! 꼭 있어야 할 종목이 목록에 없어요: {', '.join(missing)} — 발행하지 않고 중단합니다")
    return listing


def kr_same_day_keep(prev, px_date):
    """같은 기준일을 다시 도는 실행이 상위 MAX_KR 밖이어도 처리할 국내 종목 (2026-11-21 · #161 리뷰 M1 · 순수 함수).
    지난 발행본이 2차 출처 날 (pxSrc.px daum+yahoo) 이고 한국 기준일(pxDate)이 이 실행과 같으면, 그 발행본의 국내 종목 코드 모두 (그 날짜 종가 ·
    마지막 확인 종가(pxd) · 펀드 빼고). 아니면 빈 set — 그날의 첫 실행 (06:40 · 지난 발행본은 전날) 과 1차 출처 발행본 뒤의 실행은 예전 그대로예요.
    왜: 2차 출처 날 확인된 종목이 MAX_KR 보다 많으면 (11-20: 2,740) 상위 MAX_KR 로 잘라요. 아침에 마지막 확인 종가로 실은 종목 X 가 나중에 확인되면 X 가
    상위 MAX_KR 에 들어와 아침에 그 날짜 종가로 실은 종목 Y 를 밀어내요 — Y 는 확인됐으니 다시 쓰기(kr_same_day_reuse) · 마지막 확인 종가에도 들지 않아
    빠지고, 같은 날 다시 발행 판단(tools/publish_hold.py)이 '종목을 잃음' 으로 막아요 (X 가 상위 밖이면 X 가 빠져요). 그래서 같은 날의 실행은 지난 발행본의
    종목 중 오늘 목록에 있는 (2차 출처 날이면 확인된 · 1차 출처 날이면 KRX 최종본에 있는) 종목을 모두 처리해요. 확인 못 한 종목은 예전처럼 다시 쓰기 ·
    마지막 확인 종가 단계가 그날 전체 목록에서 골라요 (이 자르기와 상관없어요). 다음 새 기준일은 다시 상위 MAX_KR 이에요."""
    if not isinstance(prev, dict) or px_date is None:
        return set()
    src = prev.get("pxSrc") if isinstance(prev.get("pxSrc"), dict) else {}
    day = px_date.isoformat() if isinstance(px_date, dt.date) else str(px_date)
    if src.get("px") != PX_SRC_FB or prev.get("pxDate") != day:
        return set()
    return {str(x["t"]).strip() for x in prev.get("stocks") or []
            if isinstance(x, dict) and x.get("cls") == "kr" and not x.get("fund") and x.get("t")}


def kr_same_day_keep_note(keep, listing, max_n, n_all):
    """kr_same_day_keep 로 상위 max_n 밖에서 더 처리한 종목 한 줄 (#161 리뷰 M1 · 순수 함수). keep 이 비면 None.
    반환 (크게 남길지, 글) — 더한 종목이 있으면 크게 (!! · 이름과 함께)."""
    if not keep:
        return None
    codes = listing["Code"].astype(str).str.strip().tolist()
    extra = codes[max_n:]
    have = set(codes)
    nm = dict(zip(codes, listing["Name"].astype(str))) if "Name" in listing.columns else {}
    gone = len(keep - have)
    ex = [f"{c} {nm.get(c, '')}".strip() for c in extra[:12]]
    txt = (f"같은 기준일을 다시 도는 실행: 지난 발행본의 국내 종목 {len(keep):,} 중 오늘 목록에 있는 {len(keep & have):,}종목은 시가총액 상위 {max_n:,} 밖이어도 "
           f"처리해요 → 상위 밖에서 더한 종목 {len(extra):,} · 처리하는 종목 {len(codes):,} (오늘 목록 {n_all:,}) — 지난 발행본의 종목을 잃지 않게 (#161)"
           + (f": {', '.join(ex)}{' …' if len(extra) > len(ex) else ''}" if extra else "")
           + (f" · 오늘 목록에 없는 {gone:,}종목은 다시 쓰기 · 마지막 확인 종가 단계가 봐요" if gone else ""))
    return bool(extra), txt


def load_kr_listing(today):
    """(목록 날짜, DataFrame). 못 찾으면 (None, None) — 부르는 쪽이 실행을 멈춥니다."""
    d, df, note, notes = pick_final_listing(today, _fetch_listing_csv, _listing_commit_kst, unknown_final=False)
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
# v19.1f (2026-11-08 시험 실행 뒤): 지배주주 순이익 규칙(owners_profit)을 바꿔서, 연결 재무제표 항목 중 지배주주 순이익이나 당기순이익
# 없이 저장된 것만 한 번 다시 받아요 (사업보고서 needs_owners · 분기·반기 needs_owners_q · 별도는 아님). 캐시를 비우지 않아서 전체 DART
# 실행이 아니에요. 2026-11-08 브랜치 시험 실행의 캐시 기준 약 600건 (사업보고서 약 175 · 분기·반기 약 420) — 실행당 DART_REDO_PER_RUN 안.
# main 의 첫 실행은 빈 캐시라 어차피 전부 새로 읽어요 (그때 붙는 표시가 own1).
OWN_REDO_TAG = "own1"
UNIT_REDO_TAG = "unit1"    # (2026-11-13) 공시 단위 고침: 지난해 칸(bal0 · p0) 없이 저장된 분기 보고서를 그 회사만 한 번 다시 받아요
RP_MARK_TAGS = (CAP_REDO_TAG, UNIT_REDO_TAG)   # 항목에 rp 로 남기는 표시 (own1 은 nciBs 칸이 그 표시예요)
REDO_LABEL = {CAP_REDO_TAG: "자본금", OWN_REDO_TAG: "지배주주 줄", UNIT_REDO_TAG: "공시 단위"}
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
        self.redo_tags = collections.Counter()    # v19.1f: 표시마다 다시 받기 시도 수 (실행당 한도는 함께 써요)
        self.redone_tags = collections.Counter()  # v19.1f: 표시마다 새로 읽은 수
        self.net_streak = 0          # 연달아 난 네트워크 예외 수 (서버가 답하면 0)
        self.down = None             # DART 에 닿지 않아 조회를 멈췄으면 그때의 예외 이름
        self.skipped_down = 0        # 멈춘 뒤 건너뛴 조회 수
        self.no_call = None          # 2026-11-21 (#161 리뷰): 같은 날 다시 도는 실행 — DART 를 부르지 않아요 (까닭 글 · 보관본 값만)
        self.blocked = 0             # 그래서 부르지 않은 조회 수
        self.entries, self.meta = {}, {}
        self.carried = 0                     # v19.1f: 옛 버전 캐시에서 옮긴 업종 코드 항목 수 (adopt_carry)
        self.remove_after_save = []          # v19.1f: 새 캐시를 처음 저장한 뒤에 지울 옛 캐시 파일 (그 전에 멈추면 다시 실행이 또 옮겨 써요)
        self.fetch_done = False              # v19.1f (리뷰): 재무제표 조회를 끝냈는지 — 그 뒤 저장에서만 옛 캐시 파일을 지워요
        self._load()
        # v19.1b: 빈 캐시로 시작 = 전체 DART 실행 (호출 수 어림을 로그로 남겨요). v19.1f (리뷰 2026-11-08): 옛 캐시에서 옮겨 온 업종 코드
        # (CARRY_SUFFIXES)만 있는 캐시도 빈 캐시예요 — 옮겨 쓴 첫 실행이 멈춘 뒤 저장한 v3 파일로 다음 실행이 또 전체 실행이 되지 않게
        self.started_empty = dart_core_entries(self.entries) == 0
        # v17.5.3: 정해진 시각 실행은 하루 여러 번이에요. 캐시가 비었거나(없음·읽지 못함·형식이 다름) 처음부터 조회하면
        # 그게 그날의 전체 DART 실행이 돼요 — 하루 한 번, 사람이(또는 Claude 가 규칙대로) 수동으로만 해요 (CLAUDE.md).
        # v17.5.5: 바깥 타이머(cron-job.org) 실행도 같아요 — 워크플로가 BAEPSAE_AUTO_RUN=1 을 넘겨요
        auto = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("BAEPSAE_AUTO_RUN") == "1"
        if auto and mode != "off" and self.started_empty:
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
        """캐시를 파일에 써요. 옛 캐시 파일(remove_after_save)은 재무제표 조회를 끝낸 뒤(fetch_done — enrich_with_dart 끝)의 저장에서만
        지워요. 중간 저장 · DART 가 멈춘(fatal · down) 실행의 저장은 지우지 않아요 (리뷰 2026-11-08: 덜 찬 v3 캐시만 남고 v2 가 사라지면
        다음 실행이 업종 코드 약 2,400회를 다시 받아요)."""
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
            while self.fetch_done and self.remove_after_save and not (self.fatal or self.down):
                # v19.1f: 새 캐시가 저장됐으니 옛 캐시 파일을 지워요 (캐시 폴더에 실려 가지 않게)
                old = self.remove_after_save.pop()
                try:
                    os.remove(old)
                    log(f"· 새 DART 캐시를 처음 저장해 옛 캐시 파일을 지웠어요 ({old})")
                except FileNotFoundError:
                    pass

    def _request(self, endpoint, params, timeout):
        """HTTP 응답, 또는 못 받으면 None (get · get_zip 이 같이 써요). 키는 params 에만 넣고 어디에도 남기지 않아요.
        v17.5.2: 네트워크 예외가 DART_DOWN_AFTER 번 연달아 나면 그 뒤로는 바로 None (보관본을 써요 · 로그와 summary 에 크게 남아요)."""
        if self.fatal:
            return None
        if self.no_call:             # 2026-11-21 (#161 리뷰): 같은 날 다시 도는 실행은 DART 를 부르지 않아요 (하루 한도 · 보관본 값만)
            with self.lock:
                self.blocked += 1
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
        return r

    def get_zip(self, endpoint, params, timeout=40):
        """v19.1h: zip 으로 오는 응답(공시 원문 document.xml) → {파일 이름: 내용 bytes}, 또는 실패하면 None.
        받은 zip 은 상태 '000' 으로 세요. zip 대신 오류(JSON·XML)가 오면 그 상태 코드를 세고 None — 한도 초과·키 오류는 get 처럼
        fatal 로 남아 실행이 멈춰요."""
        r = self._request(endpoint, params, timeout)
        if r is None:
            return None
        data = r.content or b""
        if data[:2] == b"PK":
            try:
                zf = zipfile.ZipFile(io.BytesIO(data))
                files = {n: zf.read(n) for n in zf.namelist()}
            except Exception:
                with self.lock:
                    self.status["예외"] += 1
                return None
            with self.lock:
                self.status["000"] += 1
            return files
        st, msg = None, ""
        try:
            j = r.json()
            st, msg = str(j.get("status")), str(j.get("message") or "")
        except Exception:
            m = re.search(rb"<status>\s*(\d+)\s*</status>", data)
            st = m.group(1).decode() if m else None
        with self.lock:
            if st is None:
                self.status["예외"] += 1
                return None
            self.status[st] += 1
            if st in DART_FATAL and not self.fatal:
                self.fatal = (st, msg)
        return None

    def get(self, endpoint, params, timeout=25):
        """JSON 응답, 또는 실패하면 None. 상태 코드는 모두 집계해요.
        v17.5.2: 네트워크 예외가 DART_DOWN_AFTER 번 연달아 나면 그 뒤로는 바로 None (보관본을 써요 · 로그와 summary 에 크게 남아요)."""
        r = self._request(endpoint, params, timeout)
        if r is None:
            return None
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
        다시 받은 응답이 000 이 아니면 예전 항목을 그대로 둬요 (찾은 보고서를 '없음'으로 바꾸지 않게).
        v19.1f: redo 는 (표시, 판정 함수) 목록도 돼요 (먼저 걸리는 것 하나로 다시 받아요). 새로 받은 항목에는 RP_MARK_TAGS 의 표시만
        붙여요 (cap1). own1 은 표시가 필요 없어요: 새 해석은 nciBs 칸을 늘 쓰고, 판정 함수가 그 칸이 없는 항목만 골라요."""
        redos = [redo] if redo and isinstance(redo[0], str) else list(redo or [])
        key = f"{corp}|{year}|{reprt}|{tag}"
        with self.lock:
            e = self.entries.get(key)
            # 찾은 보고서도 90일이 지나면 다시 확인 (정정공시). 실행당 300건까지, 실제로 쓰는 항목만.
            # DART 가 멈췄으면(self.down) 재확인하지 않아요: 칸만 쓰고 '재확인 N건'으로 잘못 세지 않게
            reval = bool(e and e["st"] == "000" and self.mode != "full" and self._stale(e) and self.revalidate_left > 0
                         and not self.down and not self.fatal and not self.no_call)    # #161 리뷰: 부르지 않는 실행은 재확인을 세지 않아요
            if reval:
                self.revalidate_left -= 1
                self.revalidated += 1
            rd_tag = None
            if redos and not reval and e and e["st"] == "000" and self.mode != "full" and self.redo_left > 0 \
                    and not self.down and not self.fatal and not self.no_call:
                rd_tag = next((t for t, f in redos if redo_due(e, (t, f), self.today)), None)
            rd = rd_tag is not None
            if rd:
                self.redo_left -= 1
                self.redo_tags[rd_tag] += 1
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
            if redos and st == "000":
                mark = next((t for t, _ in redos if t in RP_MARK_TAGS), None)
                if mark:
                    self.entries[key]["rp"] = mark     # 새 해석으로 읽었어요 (own1 은 표시 없이 nciBs 칸으로 알아봐요)
            if rd:
                self.redone += 1
                self.redone_tags[rd_tag] += 1
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
        if self.redo_tags:
            extra += "".join(f" · {REDO_LABEL.get(t, t)} 다시 읽기 {n:,}건 시도 (실행당 최대 {DART_REDO_PER_RUN:,}): "
                             f"새로 읽음 {self.redone_tags[t]:,}" for t, n in self.redo_tags.items())
            extra += ((f" · !! 찾은 보고서가 없다고 해 예전 값을 둔 {self.redo_kept:,}" if self.redo_kept else "")
                      + (f" · !! 연결 문제·해석 오류 {self.redo_failed:,}" if self.redo_failed else ""))
        if self.parse_errors:
            extra += " · !! 해석 오류 " + ", ".join(f"{k} {v}" for k, v in self.parse_errors.items())
        if self.down:
            extra += (f" · !! DART 연결 안 됨: 연속 {DART_DOWN_AFTER}회 실패({self.down}) → 이번 실행에서 DART 조회를 멈췄어요"
                      f" (건너뛴 조회 {self.skipped_down:,}회 · 보관본 값만 씀)")
        if self.no_call:
            extra += f" · !! {self.no_call} → DART 를 부르지 않았어요 (막은 조회 {self.blocked:,}회 · 보관본 값만 씀)"
        return f"호출 {sum(self.status.values()):,}회 (상태 {st or '없음'}) · 캐시 사용 {self.cache_hits:,}건{extra}"

    def raise_if_fatal(self):
        if self.fatal:
            st, msg = self.fatal
            raise RuntimeError(f"!! DART {DART_FATAL.get(st, st)} (상태 {st}: {msg}) — 재무지표가 비어 발행하지 않고 중단합니다")


CARRY_SUFFIXES = ("|company",)     # 해석(parse)과 상관없는 캐시 항목: 캐시 버전이 바뀌어도 옮겨 써요 (업종 코드 KSIC)
CARRY_META = ("corpMap", "corpMapAt")


def dart_core_entries(entries):
    """캐시 항목 중 옛 캐시에서 옮겨 온 종류(CARRY_SUFFIXES · 업종 코드)가 아닌 것의 수. 0 이면 '빈 캐시'예요 (전체 DART 실행). (순수 함수)"""
    return sum(1 for k in (entries or {}) if not k.endswith(CARRY_SUFFIXES))


def dart_cache_core(path=None):
    """v19.1f (리뷰): 캐시 파일의 dart_core_entries — 워크플로의 'DART 캐시 확인' 단계가 정해진 시각 실행 전에 불러요. 파일이 없거나
    읽지 못하거나 버전이 다르면 0 (DartClient._load 가 처음부터 조회하는 경우와 같아요)."""
    try:
        with gzip.open(path or DART_CACHE_PATH, "rt", encoding="utf-8") as f:
            js = json.load(f)
    except Exception:
        return 0
    if not isinstance(js, dict) or js.get("v") != DART_CACHE_VERSION or not isinstance(js.get("entries"), dict):
        return 0
    return dart_core_entries(js["entries"])


def read_carry(path):
    """옛 버전 DART 캐시 파일에서 해석과 상관없는 항목(CARRY_SUFFIXES · 찾은 것만)과 기업코드 목록(meta)을 읽어요 → (항목, meta)
    또는 None (읽지 못하면 크게 남기고 None — 그러면 업종 코드도 새로 받아요). v19.1f: v2 → v3 에서 업종 코드 약 2,400회를 아껴요."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            js = json.load(f)
        ent = {k: e for k, e in (js.get("entries") or {}).items()
               if k.endswith(CARRY_SUFFIXES) and isinstance(e, dict) and e.get("st") == "000" and e.get("at") and "d" in e}
        meta = {k: js["meta"][k] for k in CARRY_META if k in (js.get("meta") or {})}
        return ent, meta
    except Exception as e:
        log(f"  !! 옛 DART 캐시({os.path.basename(path)})에서 업종 코드를 옮기지 못했어요({type(e).__name__}: {e}) → 업종 코드도 새로 받아요")
        return None


def adopt_carry(client, carry):
    """read_carry 결과를 새 캐시에 넣어요 (이미 있는 항목은 그대로). 넣은 항목 수. client.started_empty 는 바꾸지 않아요
    (재무제표가 없는 캐시라 정해진 시각 실행의 '빈 캐시면 멈춤'과 전체 실행 판단은 그대로)."""
    if not carry:
        return 0
    ent, meta = carry
    n = 0
    with client.lock:
        for k, e in ent.items():
            if k not in client.entries:
                client.entries[k] = e
                n += 1
        for k, v in meta.items():
            client.meta.setdefault(k, v)
    client.carried = n
    return n


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


def needs_owners(d):
    """연결 사업보고서 항목이 v19.1f 손익 줄 해석(_inc 가 있음)으로, 지배주주 규칙(owners_profit · nciBs 칸) 전에, 지배주주 순이익이나
    올해 당기순이익 없이 저장됐는지 (OWN_REDO_TAG). 새 해석은 nciBs 칸을 늘 써서 다시 걸리지 않아요. (순수 함수)"""
    fin = d.get("_fin") if isinstance(d, dict) else None
    return (isinstance(fin, dict) and "_inc" in d and "nciBs" not in fin
            and (fin.get("nio") is None or (fin.get("ni") or [None])[0] is None))


def needs_owners_q(d):
    """연결 분기·반기 항목이 v19.1f 해석(iec 칸이 있음)으로, 지배주주 규칙 전에(nciBs 칸이 없음), 지배주주 순이익이나 당기순이익 없이
    저장됐는지 (OWN_REDO_TAG). (순수 함수)"""
    return (isinstance(d, dict) and "iec" in d and "nciBs" not in d
            and (d.get("nio") is None or d.get("ni") is None))


def _never(d):
    return False


def owners_backlog(entries, today):
    """지배주주 규칙으로 다시 받을 연결 항목 수 → (사업보고서, 분기·반기). 캐시에 있는 것 전부 — 실행에서는 쓰는 항목만 받아요. (순수 함수)"""
    a = q = 0
    for k, e in entries.items():
        parts = k.split("|")
        if len(parts) != 4 or parts[3] != "CFS":
            continue
        if parts[2] == "11011" and redo_due(e, (OWN_REDO_TAG, needs_owners), today):
            a += 1
        elif parts[2] in Q_NEWEST_FIRST and redo_due(e, (OWN_REDO_TAG, needs_owners_q), today):
            q += 1
    return a, q


def capital_backlog(entries, years, today):
    """자본금 없이 저장돼 다시 받을 사업보고서 항목 수 (그 해들의 연결·별도). (순수 함수)"""
    tails = tuple(f"|{y}|11011|{fs}" for y in years for fs in ("CFS", "OFS"))
    return sum(1 for k, e in entries.items() if k.endswith(tails) and redo_due(e, (CAP_REDO_TAG, needs_capital), today))


def needs_capital(d):
    """캐시에 찾은 보고서로 저장된 사업보고서 해석 결과가 배당 분할 확인용 자본금 없이 저장됐는지 (v19.1e 이전 해석). (순수 함수)"""
    return isinstance(d, dict) and "_cap" not in d and not (d.get("_fin") or {}).get("cs3")


# v19.1f (Jack, 2026-11-07 · 2026-11-08): 손익계산서의 매출·영업이익·순이익·지배주주 순이익을 DART 표준 계정 코드로 먼저 찾아요.
# 2026-11-08 감사: 이름이 정확히 같은 줄만 찾던 규칙 때문에 261곳의 손익 줄이 빠졌어요 (앞 번호 'Ⅴ.영업이익' · 'I. 영업수익',
# 다른 이름 '매출' · '영업손익' · '영업손실' · '당기순손익' · '매출및지분법손익'). DART 의 정규화된 주요 계정(fnlttMultiAcnt)은
# 표준 계정 코드 줄의 값과 같았어요 (24개 재무제표 · 0건 다름). 그래서:
#   1. 손익계산서(IS · CIS) 줄 중 표준 코드가 INC_IDS 인 줄 (코드 순서대로: 영업이익은 dart_OperatingIncomeLoss 먼저)
#   2. 그 코드의 줄이 하나도 없을 때만 이름: 앞 번호 · 띄어쓰기 · 주석 번호를 뺀 이름이 INC_NAMES (지배주주 순이익은 표준 코드가
#      없는 줄만 — 포괄손익계산서의 '지배기업의 소유주' 줄은 이름이 같아도 총포괄손익이에요. 그 줄은 표준 코드가 달라요)
# 같은 코드의 줄이 손익계산서(IS)와 포괄손익계산서(CIS)에 다 있으면 IS 줄 (CIS 는 순이익을 한 번 더 적어요). 같은 표에 값이 다른
# 줄이 여럿이면 이름이 INC_NAMES 인 줄이 하나일 때만 그 줄, 아니면 쓰지 않아요 (제품별 매출 같은 아랫줄일 수 있어서 · 로그).
# 금액은 표준 계정의 부호를 그대로 써요: 손실이면 음수. 이름이 손실뿐인 줄('영업손실' · '당기순손실')의 올해 값이 양수면 잘못 적은
# 것으로 보고 쓰지 않아요 (로그).
# 금융회사(은행 · 보험 · 일부 증권)는 매출 줄이 재무제표에 없어요 (KB금융 · 삼성생명 · 삼성증권). 지어내지 않고 빈 칸으로 두고,
# corp.json incNa 에 '그 회사엔 없는 줄'로 적어요 (앱이 나중에 이유를 말할 수 있게 · build_corp).
INC_IDS = {
    "rev": ("ifrs-full_Revenue",),
    "op": ("dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"),
    "ni": ("ifrs-full_ProfitLoss",),
    "nio": ("ifrs-full_ProfitLossAttributableToOwnersOfParent",),
}
_NI_Q = ("당기", "분기", "반기", "연결당기", "연결분기", "연결반기")
INC_NAMES = {
    "rev": ("매출액", "수익(매출액)", "영업수익", "매출", "매출액(영업수익)", "영업수익(매출액)", "매출및지분법손익",
            "매출액및지분법손익"),
    "op": ("영업이익", "영업이익(손실)", "영업손실", "영업손익", "영업손실(이익)", "영업순손익", "영업손익(손실)"),
    "ni": tuple(f"{p}{s}" for p in _NI_Q for s in ("순이익", "순이익(손실)", "순손실", "순손익", "순손실(이익)")),
}
INC_OLD = {"rev": ("매출액", "수익(매출액)", "영업수익"), "op": ("영업이익", "영업이익(손실)"),     # v19.1f 전 규칙 (비교만)
           "ni": ("당기순이익", "당기순이익(손실)", "연결당기순이익")}
# 이름이 손실(을 먼저)인 줄: '영업손실' · '당기순손실' 과 '영업손실(이익)' · '당기순손실(이익)' — 올해 값이 양수면 부호를 믿을 수 없어 안 써요
# (리뷰 2026-11-08: '손실(이익)' 이름의 양수 값이 이익으로 발행될 뻔했어요)
LOSS_ONLY = tuple(f"{p}순손실{x}" for p in _NI_Q for x in ("", "(이익)")) + ("영업손실", "영업손실(이익)")
EQO_ID = "ifrs-full_EquityAttributableToOwnersOfParent"      # 재무상태표의 지배기업 소유주지분 (BPS)
INC_SEEN = collections.Counter()        # 이번 실행에서 받은 재무제표만: 찾은 방법 · 부호가 틀려 버린 줄 · 고르지 못한 줄 (실행 로그용)
_INC_LOCK = threading.Lock()


def _inc_seen(tag):
    with _INC_LOCK:
        INC_SEEN[tag] += 1


def _nio_name_ok(n):
    """표준 코드가 없는 줄의 이름이 지배주주 순이익인지 (포괄손익 · 계속/중단영업 · 비지배 줄은 아니에요). (순수 함수)"""
    return ("지배" in n and "비지배" not in n and any(w in n for w in ("순이익", "순손익", "순손실"))
            and not any(w in n for w in ("포괄", "계속", "중단")))


def _inc_name_ok(key, n):
    return _nio_name_ok(n) if key == "nio" else n in INC_NAMES[key]


def income_line(rows, key, value):
    """손익 항목 하나(key: rev · op · ni · nio)를 손익계산서에서 찾아요 → (value(row), 'id' | 'name') 또는 (None, 이유).
    이유: None 줄 없음 · 'many' 값이 다른 줄이 여럿이라 못 고름 · 'sign' 이름이 손실뿐인데 올해 값이 양수. (순수 함수)"""
    inc = [r for r in rows if (r.get("sj_div") or "").strip() in ("IS", "CIS")]

    def cur(r):
        v = value(r)
        return v[0] if isinstance(v, list) else v

    def pick(cands, how):
        grp = [r for r in cands if (r.get("sj_div") or "").strip() == "IS"] or cands
        grp = [r for r in grp if cur(r) is not None] or grp
        by_v = {}
        for r in grp:
            by_v.setdefault(cur(r), r)              # 값이 같은 줄은 한 줄로
        if len(by_v) > 1:
            by_v = {k: r for k, r in by_v.items() if _inc_name_ok(key, acct_name(r.get("account_nm")))}
            if len(by_v) != 1:
                _inc_seen(f"{key}:many")
                return None, "many"
        r = next(iter(by_v.values()))
        c = cur(r)
        if acct_name(r.get("account_nm")) in LOSS_ONLY and c is not None and c > 0:
            _inc_seen(f"{key}:sign")
            return None, "sign"
        return value(r), how

    for aid in INC_IDS[key]:
        coded = [r for r in inc if (r.get("account_id") or "").strip() == aid]
        if coded:
            return pick(coded, "id")
    named = [r for r in inc if _inc_name_ok(key, acct_name(r.get("account_nm")))
             and (key != "nio" or (r.get("account_id") or "").strip() in _NO_ID)]
    if named:
        return pick(named, "name")
    return None, None


def owners_equity(rows, value):
    """재무상태표의 지배기업 소유주지분: 표준 코드 줄, 없으면 예전 이름 규칙(재무상태표만). (순수 함수)"""
    bs = [r for r in rows if (r.get("sj_div") or "").strip() in ("BS", "")]
    for r in bs:
        if (r.get("account_id") or "").strip() == EQO_ID:
            return value(r)
    for r in bs:
        nm = (r.get("account_nm") or "").replace(" ", "")
        if "지배기업" in nm and "자본" in nm and "비지배" not in nm:
            return value(r)
    return None


# v19.1f (2026-11-08 시험 실행 뒤 · 코디네이터): 지배주주 순이익을 이 순서로 읽어요. 연결 재무제표 160곳이 지배주주 줄을 못 읽어 EPS 가
# 전체 순이익이었어요 (2,351곳 중 93.2% 만 지배주주·별도). 원인을 실제 재무제표 160개로 나눠 보니 70곳은 비지배지분 줄이 아예 없고,
# 25곳은 0, 35곳은 표준 코드 없는 지배주주 줄, 11곳은 다른 코드(계속영업 · OrdinaryEquityHolders)였어요. 각 단계는 확인할 수 있는 값이에요:
#   code   ifrs-full_ProfitLossAttributableToOwnersOfParent (지금까지처럼)
#   alt    ifrs-full_ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity
#   cont   계속영업 지배주주 + 중단영업 지배주주 (중단영업이 없는 회사만 계속영업 줄 하나로)
#   sum    표준 코드 없는 '지배…' 줄 (비지배 · 포괄 · 공동지배 · 관계기업 줄 빼고) 중 그 값 + 비지배지분 순이익(없으면 0) = 당기순이익
#          (±OWN_SUM_TOL 원) 인 줄 하나 — 같은 이름의 순이익 줄과 포괄이익 줄 중 순이익 줄을 골라요
#   minus  당기순이익 − 비지배지분 순이익 (둘 다 재무제표에 적힌 줄)
#   nci0   비지배지분이 없음: 재무상태표·손익계산서에 비지배지분 줄이 없거나 정확히 0 이고, 지배주주 자본 줄이 없거나 자본총계와 같음
#          → 당기순이익 전체가 주주 몫 (IFRS 는 비지배지분이 있으면 두 표에 따로 적게 해요 · IAS 1.54(q) · 81B)
# 증거는 nciBs (재무상태표 비지배지분) · nciPl (비지배지분 순이익) 로 남겨요 (줄이 없으면 None). 어느 단계도 아니면 '전체'(epsIn.b t).
OWN_ALT_ID = "ifrs-full_ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity"
OWN_CONT_ID = "ifrs-full_IncomeFromContinuingOperationsAttributableToOwnersOfParent"
OWN_DISC_ID = "ifrs-full_IncomeFromDiscontinuedOperationsAttributableToOwnersOfParent"
DISC_IDS = ("ifrs-full_ProfitLossFromDiscontinuedOperations", OWN_DISC_ID)
NCI_PL_ID = "ifrs-full_ProfitLossAttributableToNoncontrollingInterests"
NCI_BS_ID = "ifrs-full_NoncontrollingInterests"
OWN_SUM_TOL = 1000.0           # 원 — 지배주주 줄 + 비지배지분 줄 = 당기순이익 확인의 여유
_OWN_NAME_BAD = ("비지배", "포괄", "공동지배", "관계기업")
OWN_HOWS = ("code", "alt", "cont", "sum", "minus", "nci0")


def _cur(v):
    return v[0] if isinstance(v, list) else v


def _plus(a, b, sign=1.0):
    """a + sign × b, 칸마다 (연간 3년 목록이나 숫자 하나). 한쪽이 None 이면 None. (순수 함수)"""
    if isinstance(a, list):
        return [None if x is None or y is None else x + sign * y for x, y in zip(a, b)]
    return None if a is None or b is None else a + sign * b


def _coded_one(inc, aid, value):
    """손익계산서에서 표준 코드 aid 의 줄 하나의 값 (IS 먼저 · 값이 같은 줄은 한 줄로 · 값이 다른 줄이 여럿이면 None). (순수 함수)"""
    rows = [r for r in inc if (r.get("account_id") or "").strip() == aid]
    rows = [r for r in rows if (r.get("sj_div") or "").strip() == "IS"] or rows
    vals = {}
    for r in rows:
        vals.setdefault(_cur(value(r)), r)
    if len(vals) > 1:
        vals = {k: r for k, r in vals.items() if k is not None}
    return value(next(iter(vals.values()))) if len(vals) == 1 else None


def nci_lines(rows, value):
    """비지배지분 증거 → (재무상태표 비지배지분 올해 값 목록, 비지배지분 순이익 후보 값 목록[value 꼴]). 줄이 없으면 빈 목록.
    재무상태표: 코드 ifrs-full_NoncontrollingInterests 또는 코드 없는 '비지배…' 줄 (v19.1f 리뷰: '비지배지분부채'처럼 부채 줄은 아니에요 —
    GMI벤처 '비지배지분부채(유동)' 78.9억은 자본이 아니라 부채예요). 순이익: 코드 줄(하나), 없으면 코드 없는 '비지배…' 줄 중 포괄이
    아닌 것. (순수 함수)"""
    bs = [r for r in rows if (r.get("sj_div") or "").strip() == "BS"]
    inc = [r for r in rows if (r.get("sj_div") or "").strip() in ("IS", "CIS")]
    bs_v = [_num(r.get("thstrm_amount")) for r in bs if (r.get("account_id") or "").strip() == NCI_BS_ID
            or ((r.get("account_id") or "").strip() in _NO_ID and acct_name(r.get("account_nm")).startswith("비지배")
                and "부채" not in acct_name(r.get("account_nm")))]
    coded = [r for r in inc if (r.get("account_id") or "").strip() == NCI_PL_ID]
    if coded:                         # 코드 줄이 있으면 그 줄들만 (IS 먼저 · 값이 다르면 여럿 그대로 → minus 는 안 쓰고 nci0 도 아님)
        return bs_v, [value(r) for r in ([r for r in coded if (r.get("sj_div") or "").strip() == "IS"] or coded)]
    loose = [value(r) for r in inc if (r.get("account_id") or "").strip() in _NO_ID
             and "비지배" in acct_name(r.get("account_nm")) and "포괄" not in acct_name(r.get("account_nm"))]
    return bs_v, loose


def owners_profit(rows, value, total, eq=None, eqo=None):
    """지배주주 순이익 (위 순서) → (value 꼴의 값, how) 또는 (None, None). total = 당기순이익 (value 꼴) · eq · eqo = 재무상태표
    자본총계 · 지배주주 자본(원). (순수 함수)"""
    inc = [r for r in rows if (r.get("sj_div") or "").strip() in ("IS", "CIS")]
    for aid, how in ((INC_IDS["nio"][0], "code"), (OWN_ALT_ID, "alt")):
        v = _coded_one(inc, aid, value)
        if v is not None:
            return v, how
    cont = _coded_one(inc, OWN_CONT_ID, value)
    if cont is not None:
        disc_own = _coded_one(inc, OWN_DISC_ID, value)
        disc_any = any((_num(r.get(k)) or 0) != 0 for r in inc if (r.get("account_id") or "").strip() in DISC_IDS
                       for k in ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount", "thstrm_add_amount"))
        if disc_own is not None:
            zero = [0.0 if x is None else x for x in disc_own] if isinstance(disc_own, list) else (disc_own or 0.0)
            return _plus(cont, zero), "cont"
        if not disc_any:
            return cont, "cont"
    t0 = _cur(total) if total is not None else None
    bs_v, pl = nci_lines(rows, value)
    if t0 is not None:
        cands = [r for r in inc if (r.get("account_id") or "").strip() in _NO_ID and "지배" in acct_name(r.get("account_nm"))
                 and not any(w in acct_name(r.get("account_nm")) for w in _OWN_NAME_BAD)]
        nci0s = [_cur(x) or 0.0 for x in pl] or [0.0]
        hit = {}
        for r in cands:
            o = _cur(value(r))
            if o is not None and any(abs(o + n - t0) <= OWN_SUM_TOL for n in nci0s):
                hit.setdefault(o, r)
        if len(hit) == 1:
            return value(next(iter(hit.values()))), "sum"
        pl_one = {(_cur(x) if _cur(x) is not None else None): x for x in pl}
        if len(pl_one) == 1 and None not in pl_one:
            return _plus(total, next(iter(pl_one.values())), -1.0), "minus"
        no_nci = all(x in (None, 0) for x in bs_v) and all(_cur(x) in (None, 0) for x in pl)
        # 지배주주 몫 줄이 따로 있는데 당기순이익과 맞지 않으면 (비지배지분을 적지 않았을 뿐일 수 있어서) nci0 로 보지 않아요
        split_shown = any(_cur(value(r)) is not None and abs(_cur(value(r)) - t0) > OWN_SUM_TOL for r in cands)
        if no_nci and not split_shown and (eqo is None or eq is None or abs(eq - eqo) < 0.5):
            return total, "nci0"
    return None, None


def no_nci(rows, value, eq=None, eqo=None):
    """비지배지분이 없다는 증거: 재무상태표·손익계산서에 비지배지분 줄이 없거나 정확히 0, 지배주주 자본 줄이 없거나 자본총계와 같음. (순수 함수)"""
    bs_v, pl = nci_lines(rows, value)
    return (all(x in (None, 0) for x in bs_v) and all(_cur(x) in (None, 0) for x in pl)
            and (eqo is None or eq is None or abs(eq - eqo) < 0.5))


# v19.1f (리뷰 2026-11-08): 원화가 아닌 재무제표. DART 줄마다 currency 가 있어요 — 두산밥캣(241560)은 USD 로 내서 매출 61.8억 · EPS 4원 ·
# PER 14,575.8 로 보였어요. 원화가 아니면 금액을 해외 기업(blank_foreign_dart)처럼 비워요 (비율 roe · opm · debt · g3 와 재무 신호는 남겨요).
_CUR_NAMES = {"원": "KRW", "WON": "KRW", "₩": "KRW", "KRW": "KRW", "달러": "USD", "미국달러": "USD", "US$": "USD", "$": "USD",
              "엔": "JPY", "엔화": "JPY", "위안": "CNY", "위안화": "CNY", "유로": "EUR", "€": "EUR"}


def norm_currency(x):
    """DART currency 칸 → ISO 4217 세 글자 대문자 (원화는 'KRW'), 빈 칸이면 None. 알 수 없는 글자면 'XXX' (ISO 의 '통화 없음' — 원화로
    믿지 않고 금액을 비워요 · 리뷰 3: 관문이 철자 때문에 실패하지 않게). (순수 함수)"""
    t = re.sub(r"\s+", "", str(x or "")).upper()
    if not t:
        return None
    t = _CUR_NAMES.get(t, t)
    return t if re.fullmatch(r"[A-Z]{3}", t) else "XXX"


def stmt_currency(rows):
    """재무제표의 통화가 원화가 아니면 그 통화 코드 (ISO 세 글자 · 예: 'USD'), 원화거나 적혀 있지 않으면 None. (순수 함수)"""
    curs = {norm_currency(r.get("currency")) for r in rows or []} - {None}
    other = sorted(curs - {"KRW"})
    return other[0] if other else None


# v19.1f (리뷰 2026-11-08): 신종자본증권. 지배주주 순이익과 자본에는 신종자본증권 몫이 들어 있어요 (포스코퓨처엠 EPS 363 vs 회사 발표 51 ·
# BPS 에 신종자본증권 5,994억). K-IFRS 기본주당이익은 신종자본증권 분배금을 빼고, 보통주 자본은 신종자본증권을 빼요. 재무제표 줄로 정확히:
#   분배금  자본변동표(SCE)의 dart_DividendToHybridBond · dart_InterestExpenseForHybridBond 중 '지배기업 몫' 칸 (account_detail 이 두
#           마디이고 둘째가 지배…: 예 '자본|지배기업주주지분') — 그 기간에 주주 몫 신종자본증권에 나간 분배 (없으면 0)
#   자본    재무상태표 dart_HybridBonds — 자본변동표에 '지배기업 몫|…|신종자본증권' 칸이 있거나 지배기업 몫 분배가 있을 때만 주주 몫으로 봐요
# 어디 몫인지 알 수 없으면(재무상태표에만 있고 자본변동표에 표시가 없음) 빼지 않고 hyb 'unplaced' 로 남겨 EPS 를 '전체'(t)로 둬요 (추측 안 함).
HYB_EQ_ID = "dart_HybridBonds"
HYB_DIST_IDS = ("dart_DividendToHybridBond", "dart_InterestExpenseForHybridBond")


def _detail(r):
    return [x.strip() for x in (r.get("account_detail") or "").split("|") if x.strip()]


def _owners_part(parts):
    return len(parts) >= 2 and "지배" in parts[1] and "비지배" not in parts[1]


_SCE_COLS = ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount")


def hybrid_info(rows):
    """신종자본증권 → None (없음) 또는 {"ok": 주주 몫인지 알 수 있음, "eq": 재무상태표 신종자본증권(원), "dist": 그 기간 주주 몫 분배(원),
    "dist3": [당기, 전기, 전전기] 주주 몫 분배 (원 · 자본변동표에 그 해 칸이 아예 없으면 None — 모름)}. (순수 함수)
    v19.1f (리뷰 3): 자본변동표에 지배·비지배로 나눈 칸이 없고 재무상태표에 비지배지분도 없으면 (별도 재무제표 · 비지배지분이 없는
    연결) 자본 전체가 주주 몫이에요 — 분배는 맨 위(마디가 가장 적은) 칸, 신종자본증권도 주주 몫으로 봐요 (자본변동표가 아예 없으면
    분배를 몰라서 ok 가 아니에요)."""
    eqh = next((_num(r.get("thstrm_amount")) for r in rows if (r.get("sj_div") or "").strip() == "BS"
                and (r.get("account_id") or "").strip() == HYB_EQ_ID), None)
    sce = [r for r in rows if (r.get("sj_div") or "").strip() == "SCE"]
    split = any(len(_detail(r)) >= 2 and "지배" in _detail(r)[1] for r in sce)
    hyb_ids = [r for r in sce if (r.get("account_id") or "").strip() in HYB_DIST_IDS]
    if split:
        dist_rows = [r for r in hyb_ids if len(_detail(r)) == 2 and _owners_part(_detail(r))]
        marker = any(_owners_part(_detail(r)) and len(_detail(r)) >= 3 and "신종자본" in _detail(r)[-1] for r in sce)
    else:
        bs_nci = nci_lines(rows, lambda r: _num(r.get("thstrm_amount")))[0]
        whole = all(x in (None, 0) for x in bs_nci) and not any("비지배" in seg for r in sce for seg in _detail(r))
        top = min((len(_detail(r)) for r in hyb_ids), default=0)
        dist_rows = [r for r in hyb_ids if len(_detail(r)) == top] if whole else []
        marker = whole and bool(eqh) and bool(sce)      # 자본변동표가 없으면 분배를 몰라요 → 어디 몫인지 모름과 같게 (추측 안 함)
    if not dist_rows and not eqh:
        return None
    shown = [any(_num(r.get(col)) is not None for r in sce) for col in _SCE_COLS]   # 자본변동표에 그 해 칸이 있는지
    by_id = {}
    for r in dist_rows:
        by_id.setdefault((r.get("account_id") or "").strip(), r)
    dist3 = []
    for i, col in enumerate(_SCE_COLS):
        if i and not shown[i]:
            dist3.append(None)
        else:
            dist3.append(sum(abs(_num(r.get(col)) or 0.0) for r in by_id.values()))
    return {"ok": bool(marker or dist_rows), "eq": eqh or 0.0, "dist": dist3[0], "dist3": dist3}


def reported_eps(rows):
    """재무제표에 회사가 적은 기본주당이익 (원, 올해) — 우리 EPS 와 견주는 관문 경고용. 없으면 None. (순수 함수)"""
    inc = [r for r in rows if (r.get("sj_div") or "").strip() in ("IS", "CIS")]
    v = _coded_one(inc, "ifrs-full_BasicEarningsLossPerShare", lambda r: _num(r.get("thstrm_amount")))
    return v


def nci_evidence(rows, value):
    """저장할 증거 (nciBs, nciPl): 재무상태표 비지배지분 · 비지배지분 순이익의 올해 값 (원). 줄이 없으면 None, 여럿이면 첫 값. (순수 함수)"""
    bs_v, pl = nci_lines(rows, value)
    return (next((x for x in bs_v if x is not None), None) if bs_v else None,
            next((_cur(x) for x in pl if _cur(x) is not None), None) if pl else None)


# v19.1f (Jack, 2026-11-07): 이자보상배율의 이자. 손익계산서에 '이자비용' 줄이 있으면 그것, 없으면 현금흐름표의 이자 지급 줄을 모두
# 더한 값(양수로)이에요. 예전에는 '금융비용'(환손실·파생상품 손실까지 든 금융원가)도 이자로 읽었어요 — 2026-11-07 경고 505곳 중 502곳.
# 이자 지급 줄: 표준 계정 ifrs-full_InterestPaidClassifiedAs…(영업·투자·재무활동) 줄 모두. 그런 줄이 하나도 없을 때만 표준 계정이
# 없는 줄 중 이름이 '이자(의) 지급 · 지출 · 납부'인 줄 ('지급이자' · '미지급이자' 줄은 아니에요 — 리뷰 2026-11-08).
# 이자의 수취(받은 이자)는 절대 아니에요. 신종자본증권 이자(dart_InterestPaidToHybridBond)는
# 회계상 자본에 대한 분배라 빼요 (HYBRID_INTEREST — Jack 확인 대기).
HYBRID_INTEREST = False
_NO_ID = ("-표준계정코드 미사용-", "")


_INTEREST_PAID_NAME = re.compile(r"이자(의)?(지급|지출|납부)")


def interest_paid_rows(rows):
    """현금흐름표에서 이자 지급 줄들 (위 규칙, 같은 줄이 두 번 나와도 한 번). (순수 함수)"""
    by_id, loose = _interest_paid_parts(rows)
    seen, out = set(), []
    for r in (by_id or loose):
        k = ((r.get("account_id") or "").strip(), acct_name(r.get("account_nm")), r.get("thstrm_amount"))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def interest_paid_dropped(rows):
    """코드가 있는 이자 지급 줄이 있어 더하지 않은, 코드 없는 이자 지급 줄 수 (코드 줄과 이름 · 금액(부호 무시)이 같은 줄은 같은 줄이라
    빼고 셈). 로그만 — 리스 이자처럼 따로 적은 지급이면 이자가 작게 잡혀 이자보상배율이 커 보일 수 있어서 시험 실행에서 재요. (순수 함수)"""
    by_id, loose = _interest_paid_parts(rows)
    if not by_id:
        return 0
    amt = lambda r: abs(_num(r.get("thstrm_amount")) or 0.0)
    coded = {(acct_name(r.get("account_nm")), amt(r)) for r in by_id}
    return len({(acct_name(r.get("account_nm")), amt(r)) for r in loose} - coded)


def _interest_paid_parts(rows):
    """(표준 코드 이자 지급 줄들, 이름으로 고른 코드 없는 이자 지급 줄들) — 규칙은 위 주석."""
    cf = [r for r in rows if (r.get("sj_div") or "").strip() == "CF"]

    def received(n):
        return any(w in n for w in ("수취", "수입", "수령", "수익", "받은"))
    # v19.1f (리뷰 2026-11-08): ifrs-full_FinanceCostsPaidClassifiedAs… 도 이름이 '이자(의) 지급…'이면 이자 지급 (LG에너지솔루션
    # 2025 '이자의 지급' 8,731.5억이 이 코드라 이자 줄 없음(flWhy ie)으로 보였어요). 이름이 이자 지급이 아니면 (금융원가 전체) 안 써요
    by_id = [r for r in cf if ((r.get("account_id") or "").strip().startswith("ifrs-full_InterestPaid")
                               or ((r.get("account_id") or "").strip().startswith("ifrs-full_FinanceCostsPaid")
                                   and _INTEREST_PAID_NAME.search(acct_name(r.get("account_nm")))))
             and not received(acct_name(r.get("account_nm")))]
    if HYBRID_INTEREST:
        by_id += [r for r in cf if (r.get("account_id") or "").strip() == "dart_InterestPaidToHybridBond"]
    # 표준 계정이 없는 줄은 이름이 '이자(의) 지급 · 지출 · 납부'일 때만 (리뷰 2026-11-08: '지급이자'는 간접법의 이자비용 조정 줄,
    # '미지급이자의 증가(감소)'는 운전자본 줄이라 이자 지급이 아니에요). 그리고 코드가 있는 이자 지급 줄이 하나라도 있으면 코드 없는
    # 줄은 더하지 않아요 (같은 지급을 두 번 셀 수 있어서). 코드 줄이 없을 때만 (예: '차입원가 자본화 이자의 지급') 이름으로.
    loose = [r for r in cf if (r.get("account_id") or "").strip() in _NO_ID
             and _INTEREST_PAID_NAME.search(acct_name(r.get("account_nm")))
             and "미지급" not in acct_name(r.get("account_nm")) and not received(acct_name(r.get("account_nm")))
             and "신종자본" not in acct_name(r.get("account_nm"))]
    return by_id, loose


def interest_paid(rows, value):
    """이자 지급 줄들의 합 (양수) → 원, 줄이 없거나 값이 하나도 없으면 None. value(row) 는 그 줄의 값. (순수 함수)"""
    vals = [value(r) for r in interest_paid_rows(rows)]
    vals = [abs(v) for v in vals if v is not None]
    return sum(vals) if vals else None


_BAL_LINES = (("ifrs-full_Assets", "자산총계"), ("ifrs-full_Liabilities", "부채총계"), ("ifrs-full_Equity", "자본총계"))


def balance_totals(rows, col="thstrm_amount"):
    """(2026-11-13) 재무상태표의 [자산총계, 부채총계, 자본총계] (원 · 응답 그대로) — 셋 중 하나라도 없으면 None. 표준 코드 줄 먼저, 없으면
    이름 (띄어쓰기 빼고). 공시 단위 확인(unit_check)의 '자산 = 부채 + 자본' 에만 써요. (순수 함수)"""
    bs = [r for r in rows or [] if (r.get("sj_div") or "").strip() in ("BS", "")]
    out = []
    for aid, nm in _BAL_LINES:
        row = (next((r for r in bs if (r.get("account_id") or "").strip() == aid), None)
               or next((r for r in bs if (r.get("account_nm") or "").replace(" ", "") == nm), None))
        v = _num(row.get(col)) if row else None
        if v is None:
            return None
        out.append(v)
    return out


def parse_dart_list(rows):
    """fnlttSinglAcntAll 응답의 계정 목록에서 3개년 주요 항목을 뽑습니다. (순수 함수 — 테스트 가능)
    v19.1e: 배당 분할 확인용 자본금은 손익 줄과 상관없이 _cap 에 담아요 (parse_capital).
    v19.1f: 매출·영업이익·순이익·지배주주 순이익은 표준 계정 코드 먼저, 없으면 이름 (income_line). 손익 줄을 못 읽어도 재무상태표
    값(자본 · 부채 · 현금 …)은 버리지 않아요 (2026-11-08 전엔 _fin 을 통째로 버렸어요: 카카오뱅크). 지배기업 소유주지분(eqo)도
    표준 코드로. _inc = {"src": 줄마다 찾은 방법, "old": v19.1f 전 이름 규칙과 올해 값이 다른 줄} — enrich_with_dart 가 로그로 세고 지워요.
    이자는 '이자비용'(ie)과 현금흐름표 이자 지급액(iec)."""
    def tri(row):
        return [_num(row.get("thstrm_amount")), _num(row.get("frmtrm_amount")), _num(row.get("bfefrmtrm_amount"))]
    eq = li = cash = ocf = ca = cl = cs = ie = None
    cs3 = ss3 = None
    bor, has_bor = 0.0, False
    dep, has_dep = 0.0, False
    BORROW = {"단기차입금", "장기차입금", "사채", "유동성장기부채", "유동성장기차입금", "단기사채", "전환사채", "리스부채"}
    for row in rows:
        nm = (row.get("account_nm") or "").replace(" ", "")
        sj = (row.get("sj_div") or "").strip()
        if nm == "자본총계" and eq is None:
            eq = _num(row.get("thstrm_amount"))
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
    got, src, old_diff = {}, {}, []
    for key in ("rev", "op", "ni"):
        v, how = income_line(rows, key, tri)
        if v is not None and v[0] is None:
            how = "blank"           # 줄은 있는데 올해 값이 빈 칸: 로그에서는 '없음'으로 세요 (앞 해 값은 그대로 써요)
        got[key] = v
        if v is not None:
            src[key] = how
    eqo = owners_equity(rows, lambda r: _num(r.get("thstrm_amount")))
    # v19.1f: 지배주주 순이익 (owners_profit 의 순서) · 당기순이익 줄이 없으면 지배주주 + 비지배지분 줄 (둘 다 적힌 줄)
    nio3, nio_how = owners_profit(rows, tri, got["ni"], eq, eqo)
    if got["ni"] is None and nio3 is not None:
        pl = {_cur(x): x for x in nci_lines(rows, tri)[1]}
        if len(pl) == 1 and None not in pl:
            got["ni"], src["ni"] = _plus(nio3, next(iter(pl.values()))), "parts"
        elif no_nci(rows, tri, eq, eqo):              # 비지배 순이익 줄이 없거나 값이 비었거나 0
            got["ni"], src["ni"] = list(nio3), "nci0"     # v19.1f (리뷰): 비지배지분이 없으면 당기순이익 = 지배주주 순이익 (GMI벤처 · 라이온켐텍)
    if nio3 is not None and nio3[0] is None:
        nio_how_log = "blank"
    else:
        nio_how_log = nio_how
    if nio3 is not None:
        src["nio"] = nio_how if nio3[0] is not None else "blank"
    for key in ("rev", "op", "ni"):
        _inc_seen(f"a:{key}:{src.get(key)}")
        if key in INC_OLD:          # v19.1f 전 규칙(이름이 똑같은 첫 줄, 어느 표든)이 읽던 값과 다르면 남겨요 (시험 실행에서 확인)
            o = next((tri(r) for r in rows if (r.get("account_nm") or "").replace(" ", "") in INC_OLD[key]), None)
            v = got[key]
            if o is not None and o[0] is not None and (v is None or v[0] != o[0]):
                old_diff.append(key)
    _inc_seen(f"a:nio:{nio_how_log}")
    nci_bs, nci_pl = nci_evidence(rows, tri)
    rev, op, ni = got["rev"], got["op"], got["ni"]
    nio = nio3[0] if nio3 else None
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
    bal = balance_totals(rows)
    if bal:
        fin["bal"] = bal                          # (2026-11-13) 자산·부채·자본총계 (원) — 공시 단위 확인 (unit_check · 캐시에 없으면 '확인 못 함')
    bal_p = balance_totals(rows, col="frmtrm_amount")
    if bal_p:
        fin["balP"] = bal_p                       # (2026-11-13 고침) 지난해 말 자산·부채·자본총계 (원)
    eps_all = eps_reported(rows, lambda r: _num(r.get("thstrm_amount")))
    if eps_all is not None:
        fin["epsAll"] = eps_all                   # (2026-11-13) 재무제표의 기본주당이익 (원 · 계속+중단영업 줄도) — 단위와 상관없는 기준값 (unit_check)
    if nio3 and any(v is not None for v in nio3):
        fin["nio3"] = [ek(x) for x in nio3]       # v19.1f: 지배주주 순이익 3년 (연결) — corp.json nio3
        fin["nioHow"] = nio_how                   # v19.1f: 어떻게 읽었는지 (OWN_HOWS) — epsIn.how
    fin["nciBs"], fin["nciPl"] = ek(nci_bs), ek(nci_pl)   # v19.1f: 비지배지분 증거 (줄이 없으면 None) — nci0 · BPS
    cur = stmt_currency(rows)
    if cur:
        fin["cur"] = cur                          # v19.1f (리뷰): 원화가 아닌 재무제표 — 금액을 비워요 (not_won)
    hyb = hybrid_info(rows)
    if hyb:                                       # v19.1f (리뷰): 신종자본증권 — 주주 몫 분배 · 자본 (EPS · BPS · ROE 에서 빼요)
        fin["hyb"] = {"ok": hyb["ok"], "eq": ek(hyb["eq"]), "dist": ek(hyb["dist"]), "dist3": [ek(x) for x in hyb["dist3"]]}
    rep = reported_eps(rows)
    if rep is not None:
        fin["epsRep"] = rep                       # v19.1f (리뷰): 재무제표의 기본주당이익 (원) — 관문 경고용
    # v19.1f: 손익 줄이 없어도 자본·부채가 있으면 재무상태표 값은 남겨요 (자본금만 있는 표는 예전처럼 '못 찾음')
    if any(v is not None for a in (fin["rev"], fin["op"], fin["ni"]) for v in a) or eq is not None or li is not None:
        out["_fin"] = fin
    cap = parse_capital(rows)
    if cap:
        out["_cap"] = cap
    iec_drop = interest_paid_dropped(rows)        # v19.1f: 코드 줄 옆에서 더하지 않은 코드 없는 이자 지급 줄 수 (로그만)
    iec_fcp = int(any((r.get("account_id") or "").strip().startswith("ifrs-full_FinanceCostsPaid") for r in interest_paid_rows(rows)))
    out["_inc"] = {"src": src, **({"old": old_diff} if old_diff else {}), **({"iecDrop": iec_drop} if iec_drop else {}),
                   **({"iecFcp": 1} if iec_fcp else {})}      # v19.1f (리뷰): 이자 지급을 FinanceCostsPaid 코드 줄로 읽음 (로그만)
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


def _ytd0(row):
    """분기 보고서의 지난해 같은 기간 누적 칸: frmtrm_add_amount 가 있으면 그것, 없으면 frmtrm_amount (현금흐름표는 이 칸이 누적이에요)."""
    v = _num(row.get("frmtrm_add_amount"))
    return v if v is not None else _num(row.get("frmtrm_amount"))


def eps_reported(rows, value):
    """(2026-11-13) 재무제표에 회사가 적은 기본주당이익 (원) — 표준 코드 줄, 없으면 계속영업 + 중단영업(없으면 0) 줄. 없으면 None.
    주당 금액이라 표의 단위를 잘못 적어도 그대로예요 (진코스텍 · 디와이에이 2026 반기: 1,061원 · 385원) — 공시 단위 확인의 기준값. (순수 함수)"""
    inc = [r for r in rows or [] if (r.get("sj_div") or "").strip() in ("IS", "CIS")]
    v = _coded_one(inc, "ifrs-full_BasicEarningsLossPerShare", value)
    if v is not None:
        return v
    c = _coded_one(inc, "ifrs-full_BasicEarningsLossPerShareFromContinuingOperations", value)
    if c is None:
        return None
    d = _coded_one(inc, "ifrs-full_BasicEarningsLossPerShareFromDiscontinuedOperations", value)
    return c + (d or 0.0)


def prior_flows(rows):
    """(2026-11-13) 분기 보고서의 지난해 같은 기간 누적 칸 → {"rev", "ni", "ocf"} (억원 · 있는 것만) 또는 None. 지난해 같은 분기 보고서의
    누적 값과 견줘 손익계산서 · 현금흐름표의 단위를 확인해요 (unit_check is · cf). (순수 함수)"""
    ek = lambda w: round(w / 1e8, 1) if w is not None else None
    out = {}
    for key in ("rev", "ni"):
        v, _ = income_line(rows, key, _ytd0)
        if v is not None:
            out[key] = ek(v)
    ocf = next((_ytd0(r) for r in rows or [] if (r.get("sj_div") or "").strip() == "CF"
                and (r.get("account_nm") or "").replace(" ", "") in ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로인한순현금흐름")), None)
    if ocf is not None:
        out["ocf"] = ek(ocf)
    return out or None


def parse_dart_quarter(rows):
    """분기·반기 보고서에서 손익/현금흐름 누적값과 시점 재무상태를 뽑습니다.
    v19.1f: 매출·영업이익·순이익·지배주주 순이익은 사업보고서와 같은 규칙 (income_line: 표준 코드 먼저 · '연결반기순이익' 같은
    이름도). 지배기업 소유주지분(eqo)도 표준 코드로. 손익 줄을 못 읽어도 자본·부채 값이 있으면 돌려줘요 (그 분기는 TTM 을 못 만들어
    다음 분기로 넘어가요 — 연결이 없다고 별도로 넘어가 둘을 섞지 않게)."""
    ek = lambda w: round(w / 1e8, 1) if w is not None else None
    ocf = ie = None
    eq = cash = ca = cl = cs = None
    bor, has_bor = 0.0, False
    dep, has_dep = 0.0, False
    BORROW = {"단기차입금", "장기차입금", "사채", "유동성장기부채", "유동성장기차입금", "단기사채", "전환사채", "리스부채"}
    for row in rows:
        nm = (row.get("account_nm") or "").replace(" ", "")
        sj = (row.get("sj_div") or "").strip()
        if sj in ("IS", "CIS"):
            if acct_name(nm) == "이자비용" and ie is None: ie = _ytd(row)     # v19.1f: 이자비용만 (금융비용은 이자가 아니에요)
        elif sj == "CF":
            if nm in ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로인한순현금흐름") and ocf is None:
                ocf = _ytd(row)
            elif nm in ("감가상각비", "유형자산감가상각비", "무형자산상각비", "사용권자산상각비", "투자부동산감가상각비"):
                v = _ytd(row)
                if v and v > 0: dep += v; has_dep = True
        elif sj in ("BS", ""):
            v = _num(row.get("thstrm_amount"))
            if nm == "자본총계" and eq is None: eq = v
            elif nm in BORROW:
                if v and v > 0: bor += v; has_bor = True
            elif nm in ("현금및현금성자산", "현금및현금성자산등", "기말현금및현금성자산") and cash is None: cash = v
            elif nm == "유동자산" and ca is None: ca = v
            elif nm == "유동부채" and cl is None: cl = v
            elif nm == "자본금" and cs is None: cs = v
    got = {}
    for key in ("rev", "op", "ni"):
        got[key], how = income_line(rows, key, _ytd)
        _inc_seen(f"q:{key}:{'blank' if got[key] is None and how in ('id', 'name') else how}")
    eqo = owners_equity(rows, lambda r: _num(r.get("thstrm_amount")))
    # v19.1f: 지배주주 순이익은 사업보고서와 같은 순서 (owners_profit) · 당기순이익 줄이 없으면 지배주주 + 비지배지분 줄
    nio, nio_how = owners_profit(rows, _ytd, got["ni"], eq, eqo)
    if got["ni"] is None and nio is not None:
        pl = {x: x for x in nci_lines(rows, _ytd)[1]}
        if len(pl) == 1 and None not in pl:
            got["ni"] = nio + next(iter(pl))
        elif no_nci(rows, _ytd, eq, eqo):
            got["ni"] = nio                       # v19.1f (리뷰): 비지배지분이 없으면 당기순이익 = 지배주주 순이익
    _inc_seen(f"q:nio:{nio_how}")
    nci_bs, nci_pl = nci_evidence(rows, _ytd)
    rev, op, ni = got["rev"], got["op"], got["ni"]
    iec = interest_paid(rows, _ytd)
    if interest_paid_dropped(rows):
        _inc_seen("q:iecDrop")                   # v19.1f: 분기·반기도 같은 수를 로그로 (회사 이름은 사업보고서 쪽에서)
    if rev is None and ni is None and eq is None:
        return None
    return {"rev": ek(rev), "op": ek(op), "ni": ek(ni), "nio": ek(nio), "ocf": ek(ocf), "ie": ek(ie), "iec": ek(iec),
            "dep": ek(dep) if has_dep else None,
            "eq": ek(eq), "eqo": ek(eqo), "bor": ek(bor) if has_bor else None, "cash": ek(cash),
            "ca": ek(ca), "cl": ek(cl), "cs": ek(cs),
            "nioHow": nio_how if nio is not None else None, "nciBs": ek(nci_bs), "nciPl": ek(nci_pl),
            **({"cur": stmt_currency(rows)} if stmt_currency(rows) else {}),
            **({"bal": b} if (b := balance_totals(rows)) else {}),        # (2026-11-13) 자산·부채·자본총계 (원) — 공시 단위 확인
            # (2026-11-13) 공시 단위 확인: 누적 기본주당이익 (원 · 단위를 잘못 적어도 그대로예요) · 이 보고서의 지난해 같은 기간 누적 칸 (억원)
            **({"epsYtd": e} if (e := eps_reported(rows, _ytd)) is not None else {}),
            **({"p0": p0} if (p0 := prior_flows(rows)) else {}),
            # (2026-11-13 고침) 그 보고서의 지난해 말 칸 [자산, 부채, 자본] (원) — 사업보고서 값과 견줘 재무상태표의 단위를 증명해요 (bs_factor)
            **({"bal0": b0} if (b0 := balance_totals(rows, col="frmtrm_amount")) else {}),
            **({"hyb": {"ok": h["ok"], "eq": ek(h["eq"]), "dist": ek(h["dist"])}} if (h := hybrid_info(rows)) else {})}


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
    cur = ytd.get("cur") or ytd_prev.get("cur")
    if cur:
        ttm["cur"] = cur               # v19.1f (리뷰): 분기 재무제표가 원화가 아니면 (not_won)
    if "nciPl" in ytd:
        ttm["nciPl"] = ytd["nciPl"]    # (2026-11-08) 최신 분기 누적 비지배지분 순이익 (줄이 없으면 None) — 증거일 뿐, 합산하지 않아요 (eps_nci)
    if ttm["nio"] is not None:     # v19.1f: 세 보고서에서 지배주주 순이익을 어떻게 읽었는지 (다르면 'code+nci0' 처럼)
        hows = {fin.get("nioHow"), ytd.get("nioHow"), ytd_prev.get("nioHow")} - {None}
        if hows:
            ttm["nioHow"] = "+".join(sorted(hows))
    hs = [x.get("hyb") for x in (fin, ytd, ytd_prev)]
    if any(hs):                    # v19.1f (리뷰): 신종자본증권 분배 TTM (그 보고서에 신종자본증권이 없으면 0) · 셋 다 어디 몫인지 알아야 ok
        d = [(h or {}).get("dist") or 0.0 for h in hs]
        ttm["hyb"] = {"ok": all((h or {}).get("ok", True) for h in hs), "dist": round(d[0] + d[1] - d[2], 1)}
    bs = {k: ytd.get(k) for k in ("eq", "eqo", "bor", "cash", "ca", "cl", "cs") if ytd.get(k) is not None}
    if "nciBs" in ytd:
        bs["nciBs"] = ytd["nciBs"]  # v19.1f: 최신 분기 비지배지분 (줄이 없으면 None) — BPS 의 nci0
    if ytd.get("hyb"):
        bs["hyb"] = ytd["hyb"]      # v19.1f (리뷰): 최신 분기 신종자본증권 (BPS 에서 빼요)
    if ytd.get("bal"):
        bs["bal"] = ytd["bal"]      # (2026-11-13) 최신 분기 자산·부채·자본총계 (원) — 공시 단위 확인
    # (2026-11-13) 지난해 같은 분기의 재무상태표: TTM 에 그 보고서의 누적 손익을 빼서 써요 — 단위가 틀렸는지 같이 봐요 (unit_check · 다른 데엔 안 써요)
    bsp = {k: ytd_prev.get(k) for k in UNIT_SCALE_KEYS + ("bal",) if ytd_prev.get(k) is not None}
    # (2026-11-13) 공시 단위 확인의 손익 쪽: 두 분기 보고서의 누적 순이익 · 매출 · 영업현금흐름 · 기본주당이익 · 지난해 칸 (unit_check)
    chk = {w: {k: x.get(k) for k in UNIT_CHK_KEYS if x.get(k) is not None} for w, x in (("q", ytd), ("qp", ytd_prev))}
    return {"ttm": ttm, "bs": bs, "bsP": bsp, "chk": chk}


def dart_financials(client, corp_code, year):
    """연결(없으면 별도) 사업보고서에서 주요 지표 + 3개년 원값.
    v19.1e: 자본금(_cap)만 읽힌 연결 재무제표는 예전처럼 '못 찾음'으로 보고 별도로 넘어가요 (어느 재무제표를 쓰는지 바뀌지 않게).
    자본금 없이 저장된 예전 항목은 한 번 다시 받아요 (needs_capital · CAP_REDO_TAG).
    v19.1f: _fin.fs = 쓴 재무제표 (CFS 연결 · OFS 별도) — 분기 TTM 은 같은 종류만 써요 (dart_quarter), EPS 기준(fill_multiples)."""
    for fs in ("CFS", "OFS"):
        d = client.report("fnlttSinglAcntAll.json", corp_code, year, "11011", fs, parse_dart_list, {"fs_div": fs},
                          redo=[(CAP_REDO_TAG, needs_capital), (OWN_REDO_TAG, needs_owners if fs == "CFS" else _never)])
        if d and any(k not in ("_cap", "_inc") for k in d):
            if isinstance(d.get("_fin"), dict):
                d["_fin"]["fs"] = fs
            return d
    return {}


# v19.1g (Jack, 2026-11-07): 상장되지 않은 우선주(상환전환우선주 · 종류주식)도 배당을 받으면 현금배당금총액을 보통주 1주 기준으로 나눌 수
# 없어 배당 분할 확인의 위 끝을 셀 수 없었어요 (2026-11-07 30곳: 현대모비스 · 알테오젠 · 키움증권 · 솔루엠 …). 그런 회사만 DART '주식의
# 총수 현황'(stockTotqySttus, 사업보고서)을 받아 그해 말 보통주 유통 주식 수로 위 끝을 세요 (회사당 1회 · 캐시 · 약 30회).
STK_TOTAL = ("합계", "총계", "계", "합", "total")
STK_NOT_COMMON = ("우선", "종류", "전환", "상환", "없는")


def parse_dart_shares(rows):
    """주식의 총수 현황 → {"cmo": 보통주 유통 주식 수, "cmi": 보통주 발행 주식 수, "pfo": 그 밖의 종류 유통 주식 수 합} 또는 None.
    줄 이름은 회사마다 달라요: '보통주' · '보통주식' · '의결권 있는 주식' · '보통주(의결권 있는 주식)' = 보통주. 이름에 우선 · 종류 ·
    전환 · 상환 · 없는 이 들면 보통주가 아니에요 ('의결권 있는 배당우선 전환주'). 주식이 없는 줄('-')과 비고 줄은 빼고, 똑같은 줄이
    두 번 나오면(표를 두 번 실은 보고서) 한 번만. 합계 줄이 하나 있고 보통주 + 그 밖 = 합계(±1주)일 때만 믿어요 — '총계' 같은 다른
    이름의 합계 줄이 우선주로 더해지지 않게 (리뷰 2026-11-07). 아니면 None. (순수 함수)"""
    cm, others, totals, seen = [], [], [], set()
    for r in rows or []:
        se = re.sub(r"\s+", "", r.get("se") or "")
        dist, iss = _num(r.get("distb_stock_co")), _num(r.get("istc_totqy"))
        key = (se, dist, iss)
        if not se or se.startswith("비고") or key in seen:
            continue
        seen.add(key)
        if se.lower() in STK_TOTAL or se.startswith("합계"):
            totals.append(dist)
            continue
        if not (dist and dist > 0) and not (iss and iss > 0):
            continue                                 # 발행하지 않은 종류
        if ("보통주" in se or "의결권있는" in se) and not any(w in se for w in STK_NOT_COMMON):
            cm.append((dist, iss))
        else:
            others.append(dist)
    if len(cm) != 1 or not cm[0][0] or cm[0][0] <= 0 or len(totals) != 1 or totals[0] is None:
        return None
    pfo = sum(x for x in others if x is not None and x > 0)
    if abs(cm[0][0] + pfo - totals[0]) > 1:
        return None
    return {"cmo": cm[0][0], "cmi": cm[0][1], "pfo": pfo}


def dart_shares(client, corp_code, year):
    return client.report("stockTotqySttus.json", corp_code, year, "11011", "STK", parse_dart_shares)


def unlisted_paid(bas, listed):
    """배당 표에서 그해 배당을 받은 우선주·종류주 종류 수가 상장 우선주 종목 수(listed)보다 많은지. (순수 함수)"""
    paid = sum(1 for p in (bas or {}).get("pdps") or [] if isinstance(p, (list, tuple)) and p and _fin(p[0]) and p[0] > 0)
    return paid > listed


def dart_dividend(client, corp_code, year):
    # v17.5.1: 0 원을 남기는 새 해석 → 태그 DIV2 (배당 항목만 한 번 다시 받아요, 약 2,500건. 다른 캐시는 그대로)
    return client.report("alotMatter.json", corp_code, year, "11011", "DIV2", parse_dart_dividend) or {}


def dart_quarter(client, corp_code, year, reprt, fs=None, unit_redo=False):
    """분기·반기 보고서의 누적값 (연결 우선, 없으면 별도).
    v19.1f: fs 를 주면 그 재무제표만 (사업보고서와 같은 종류 — 연결 연간에 별도 분기를 섞은 TTM 을 만들지 않게. 별도만 내는 회사는
    없는 연결 분기를 묻지 않아 호출도 줄어요).
    (2026-11-13) unit_redo: 공시 단위 고침(unit_fix_quarter)이 그 보고서의 지난해 칸(bal0 · p0)을 원할 때만 — 그 칸 없이 저장된 항목을 한 번
    다시 받아요 (UNIT_REDO_TAG 표시 · 실행당 DART_REDO_PER_RUN 안 · 그 회사만)."""
    for fs in ((fs,) if fs in ("CFS", "OFS") else ("CFS", "OFS")):
        redo = [(OWN_REDO_TAG, needs_owners_q if fs == "CFS" else _never)]
        if unit_redo:
            redo = [(UNIT_REDO_TAG, needs_unit0)] + redo
        d = client.report("fnlttSinglAcntAll.json", corp_code, year, reprt, fs, parse_dart_quarter, {"fs_div": fs}, redo=redo)
        if d:
            return d
    return None


def pick_current_quarter(shares):
    """[(보고서, 상위 100곳 제출 비율)] 최신순 → 70% 이상인 가장 최신 분기 (없으면 None). (순수 함수)"""
    for reprt, share in shares:
        if share >= QUARTER_CURRENT_SHARE:
            return reprt
    return None


def dart_full_estimate(n_companies, ksic=True, divwhy=0):
    """v19.1b: 처음부터 받는 전체 DART 실행의 호출 수 어림 → (합계, 설명). (순수 함수)
    재무·배당·분기 기업당 4.8회(지난 전체 실행의 평균) + 업종 코드 기업당 1회(캐시가 비었을 때) + 기업코드 목록 1회 + 공시 최대 1,430회.
    v19.1h: divwhy = 배당 맞춤 이유(결정 공시) 어림 호출 수 (맞춘 회사 × 3 · 파이프라인은 DVWHY_EST_STOCKS × DVWHY_PER_STOCK 을 넘겨요).
    상한이 아니라 어림이에요 — 실제 호출 수는 실행 끝에 남기고, 목표(16,000)를 넘으면 크게 알려요."""
    main_ = math.ceil(n_companies * DART_PER_COMPANY)
    ks = n_companies if ksic else 0
    total = main_ + ks + 1 + DART_DISC_MAX + divwhy
    why = (f"재무·배당·분기 {main_:,} + 업종 코드 {ks:,} + 기업코드 목록 1 + 공시 최대 {DART_DISC_MAX:,}"
           + (f" + 배당 맞춤 이유 약 {divwhy:,}" if divwhy else ""))
    return total, why


INC_KO = {"rev": "매출", "op": "영업이익", "ni": "순이익", "nio": "지배주주 순이익"}


def income_log(inc_by):
    """v19.1f: 손익 줄을 어떻게 읽었는지 크게 남겨요 (사업보고서는 캐시에서 온 것까지 회사마다 · 받은 재무제표의 부호·여러 줄 수).
    inc_by = {코드: (이름, _inc, 재무제표 값 있음)}. 반환: 재무제표는 있는데 손익 줄을 하나도 못 읽은 회사 ["코드 이름", …]."""
    n = len(inc_by)
    cnt = collections.Counter()
    old, none_at_all = collections.defaultdict(list), []
    for t, (nk, inc, has_fin) in sorted(inc_by.items()):
        src = {k: v for k, v in ((inc or {}).get("src") or {}).items() if v in ("id", "name")}   # 'blank' = 올해 값 없음 → 없음
        for k in INC_KO:
            cnt[f"{k}:{src.get(k) or 'none'}"] += 1
        for k in (inc or {}).get("old") or []:
            old[k].append(f"{t} {nk}".strip())
        if has_fin and not any(k in src for k in ("rev", "op", "ni")):
            none_at_all.append(f"{t} {nk}".strip())
    log(f"· 손익 줄 (사업보고서 {n:,}곳 · 표준 코드 / 이름 / 없음): "
        + " · ".join(f"{INC_KO[k]} {cnt[k + ':id']:,} / {cnt[k + ':name']:,} / {cnt[k + ':none']:,}" for k in INC_KO))
    sign = {p: sum(v for k, v in INC_SEEN.items() if k.startswith(p) and k.endswith(":sign")) for p in ("a:", "q:")}
    many = {p: sum(v for k, v in INC_SEEN.items() if k.startswith(p) and k.endswith(":many")) for p in ("a:", "q:")}
    loud = any(sign.values()) or any(many.values())
    log(f"{'  !! ' if loud else '· '}손익 줄을 쓰지 않은 경우 (이번 실행에서 받은 재무제표 · 사업보고서 / 분기·반기): 이름이 손실인데 "
        f"올해 값이 양수 {sign['a:']:,} / {sign['q:']:,} · 값이 다른 같은 코드 줄이 여럿 {many['a:']:,} / {many['q:']:,}")
    n_old = sum(len(v) for v in old.values())
    log(f"{'  !! ' if n_old else '· '}v19.1f 전 이름 규칙과 올해 값이 다른 손익 줄: {n_old:,}"
        + "".join(f" · {INC_KO[k]} {len(v):,}곳 ({', '.join(v[:8])}{'…' if len(v) > 8 else ''})" for k, v in old.items())
        + (" — 표준 코드 줄을 썼어요. 시험 실행에서 값을 확인해요" if n_old else ""))
    drop = [f"{t} {nk}".strip() + f"({inc['iecDrop']})" for t, (nk, inc, _) in sorted(inc_by.items())
            if (inc or {}).get("iecDrop")]
    log(f"{'  !! ' if drop else '· '}코드가 있는 이자 지급 줄 옆에서 더하지 않은 코드 없는 이자 지급 줄이 있는 곳 (사업보고서 · 로그만, "
        f"규칙은 그대로 — 따로 적은 리스 이자 같은 지급이면 이자보상배율이 커 보일 수 있어요): {len(drop):,}"
        + (f" ({', '.join(drop[:20])}{'…' if len(drop) > 20 else ''})" if drop else "")
        + f" · 분기·반기 보고서 {INC_SEEN['q:iecDrop']:,}건 (이번 실행에서 받은 것)")
    fcp = [f"{t} {nk}".strip() for t, (nk, inc, _) in sorted(inc_by.items()) if (inc or {}).get("iecFcp")]
    log(f"· 이자 지급을 ifrs-full_FinanceCostsPaid… 코드의 '이자(의) 지급' 줄로 읽은 곳 (사업보고서 · 리뷰 2026-11-08 — 예전엔 이자 줄 없음 ie): "
        f"{len(fcp):,}" + (f" ({', '.join(fcp[:20])}{'…' if len(fcp) > 20 else ''})" if fcp else ""))
    log(f"{'  !! ' if none_at_all else '· '}재무제표는 있는데 매출·영업이익·순이익을 하나도 못 읽은 곳: {len(none_at_all):,}"
        + (f" ({', '.join(none_at_all[:15])}{'…' if len(none_at_all) > 15 else ''}) — 재무상태표 값은 남겨요" if none_at_all else ""))
    return none_at_all


def enrich_with_dart(kr_stocks, client, pref_shares=None):
    """사업보고서·배당·분기보고서(TTM)를 붙입니다. 기업마다 분기를 따로 확인해요 (3Q → 2Q → 1Q).
    v19.1g: pref_shares (kr_pref_shares) 로 상장 우선주 수를 알아요 — 배당 받은 종류가 더 많은 회사만 주식의 총수 현황을 받아요."""
    fin_map = {}
    stk_n = collections.Counter()
    inc_by = {}                            # v19.1f: {코드: (이름, 손익 줄 _inc, 재무제표 값 있음)} — 로그용
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
    own0 = owners_backlog(client.entries, today) if client.mode != "full" else (0, 0)
    if sum(own0):
        loud = sum(own0) > DART_REDO_PER_RUN
        log(f"{'  !! ' if loud else '· '}DART 지배주주 줄 다시 읽기 대상 (v19.1f · 캐시에 있는 연결 항목): 사업보고서 {own0[0]:,} · "
            f"분기·반기 {own0[1]:,} = {sum(own0):,}건 — 이번 실행에서 쓰는 것만, 자본금 다시 읽기와 합쳐 최대 {DART_REDO_PER_RUN:,}건"
            + (" (한도를 넘어 다음 실행이 이어받아요)" if loud else ""))
    targets = [s for s in kr_stocks if s["t"] in cmap]
    if client.started_empty or client.mode == "full":
        has_ksic = any(k.endswith(CARRY_SUFFIXES) for k in client.entries)   # 옮겨 왔거나 지난 실행이 받은 업종 코드
        est, why = dart_full_estimate(len(targets), ksic=client.started_empty and not has_ksic,
                                      divwhy=DVWHY_EST_STOCKS * DVWHY_PER_STOCK)
        loud = est > DART_FULL_TARGET
        log(f"{'  !! ' if loud else '· '}전체 DART 실행 호출 수 어림: 약 {est:,}회 ({why}) · 하루 한도 {DART_DAY_LIMIT:,} · "
            f"목표 {DART_FULL_TARGET:,} 아래" + (" — 목표를 넘어요" if loud else ""))
        if DIV_PROVE:
            log(f"· 배당 기준 증명(v19.1i)은 위 어림 밖이에요: 약 {PROVE_EST_STOCKS}곳 × {PROVE_PER_STOCK}회 = "
                f"{PROVE_EST_STOCKS * PROVE_PER_STOCK:,}회 더 (실행당 새 조회 {PROVE_PER_RUN}곳까지 · 넘는 곳은 다음 실행이 이어받아요)")
        log(f"· 주요사항 공시(v19.6b · 유상증자 · CB · BW)도 위 어림 밖이에요: 목록 약 {ISSUE_EST_PAGES}쪽 + 상세 최대 {ISSUE_PER_RUN}회 + "
            f"유상증자 원문(결의일) 최대 {ISSUE_BD_PER_RUN}회 = 최대 약 {ISSUE_EST_PAGES + ISSUE_PER_RUN + ISSUE_BD_PER_RUN:,}회 더 "
            f"(상세 · 원문은 캐시에 없는 공시만 · 빈 캐시면 90일치를 한도까지 · 넘는 것은 다음 실행)")
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
    unit_log = {"fixed": [], "left": [], "redo": 0}   # (2026-11-13) 공시 단위 고침 (unit_fix_quarter) — 실행 로그용

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
            if pref_shares is not None and unlisted_paid(div["bas"], len(pref_shares.get(s["t"][:5], ()))):
                stk = dart_shares(client, corp, yr)
                with client.lock:
                    stk_n["got" if stk else "none"] += 1
                if stk:
                    s["_stk"] = stk       # v19.1g: 주식의 총수 현황 — apply_div_basis 가 쓰고 지워요
        cap = f.pop("_cap", None) if f else None
        if cap:
            s["_cap"] = cap               # v19.1e: 분할 확인용 자본금 — apply_div_basis 가 쓰고 지워요 (파일에 나가지 않아요)
        inc = f.pop("_inc", None) if f else None
        if inc is not None:
            with client.lock:
                inc_by[s["t"]] = (s.get("nk") or "", inc, "_fin" in f)   # v19.1f: 손익 줄을 찾은 방법 (로그만 · 파일에 나가지 않아요)
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
                    ytd = dart_quarter(client, corp, qy_c, r, fs=fin.get("fs"))
                    if not ytd:
                        continue
                    prev = dart_quarter(client, corp, yr, r, fs=fin.get("fs"))
                    # (2026-11-13) 공시 단위 고침: 올해 분기 보고서가 단위를 잘못 적었고 표마다 증명이 되면 나눠서 써요 (unit_fix_quarter ·
                    # 못 하면 그대로 → unit_guard 가 숫자를 비워요)
                    ytd = unit_fix_quarter(client, corp, fin, qy_c, r, ytd, prev, s, pref_shares, unit_log)
                    t2 = compute_ttm(fin, ytd, prev)
                    if t2 and ytd and ytd.get("unitFix"):
                        fin["unitFix"] = [{"rep": f"{qy_c}.{REPRT_KO[r]}", **ytd["unitFix"]}]   # corp.json unitFix
                    if t2:
                        fin["ttm"], fin["bs2"], fin["bq"] = t2["ttm"], t2["bs"], f"{qy_c}.{REPRT_KO[r]}"
                        fin["bsP"] = t2["bsP"]          # (2026-11-13) 지난해 같은 분기 재무상태표 — 공시 단위 확인만 (unit_check)
                        fin["qChk"] = t2["chk"]         # (2026-11-13) 두 분기 보고서의 손익 쪽 기준값 — 공시 단위 확인만
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
    client.fetch_done = True              # v19.1f (리뷰): 재무제표 조회를 끝냈어요 — 이 저장부터 (멈추지 않았으면) 옛 캐시 파일을 지워요
    client.save()
    log(f"· DART: {client.summary()}")
    income_log(inc_by)
    if stk_n:
        log(f"{'  !! ' if stk_n['none'] else '· '}상장되지 않은 우선주가 배당을 받은 회사: {sum(stk_n.values()):,}곳 — 주식의 총수 현황 "
            f"받음 {stk_n['got']:,} · 못 받음(보통주 줄을 못 찾음 · 보고서 없음) {stk_n['none']:,}")
    if backlog0:
        left = capital_backlog(client.entries, (year, year - 1), today)
        capped = client.redo_left <= 0
        log(f"{'  !! ' if capped else '· '}DART 자본금 다시 읽기: 대상 {backlog0:,}건 중 남은 {left:,}건"
            + (f" — 실행당 한도({DART_REDO_PER_RUN:,})에 닿았어요. 다음 실행에서 이어서 받아요" if capped
               else " (이번 실행에서 쓰지 않은 항목 · 며칠 뒤 다시 해 볼 항목)" if left else ""))
    if sum(own0):
        left = owners_backlog(client.entries, today)
        capped = client.redo_left <= 0
        log(f"{'  !! ' if capped else '· '}DART 지배주주 줄 다시 읽기: 대상 {sum(own0):,}건 중 이번에 받은 {client.redo_tags[OWN_REDO_TAG]:,}건 "
            f"(새로 읽음 {client.redone_tags[OWN_REDO_TAG]:,}) · 캐시에 남은 {sum(left):,}건"
            + (f" — 실행당 한도({DART_REDO_PER_RUN:,})에 닿았어요. 다음 실행에서 이어서 받아요" if capped
               else " (이번 실행에서 쓰지 않은 항목 · 찾은 보고서가 없다는 답이면 며칠 뒤 다시)" if sum(left) else ""))
    try:
        log(f"· DART 캐시 저장: {len(client.entries):,}건 · {os.path.getsize(client.path) / 1e6:.1f}MB ({client.path})")
    except OSError as e:
        log(f"  !! DART 캐시 파일을 확인하지 못했어요: {e}")
    if errors:
        log(f"  !! DART 처리 오류 {sum(errors.values()):,}곳 ({dict(errors)}) — 그 기업은 재무지표 없이 진행해요")
    unit_fix_log(unit_log)
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


INSIDER_BOTH = "임원·주요주주"    # Jack 2026-11-19 (7c): 임원이면서 주요주주인 사람의 role — 글자 그대로 (스펙 B.2 의 빈 직위 대신 쓰는 말과 같아요)
INSIDER_ROLES = ("임원", "주요주주", INSIDER_BOTH)
# v19.6b (리뷰 2026-11-16 · Jack 의 yes 2026-11-19, Q21): 임원 직위가 없는 주요주주 줄의 직위(pos)에 DART 의 관계 말(10%이상주주 · 사실상지배주주 …)을
# 그대로 써요 — 2.0 공시 탭 · 예전 뱁새 공시·수급에 보여요 (예전엔 '-' 이라 2.0 은 빈 칸, 예전 앱은 ' · -'). False 면 그 줄의 직위는 빈 칸이에요
# (2.0 이 지금 '-' 에 하는 것처럼 · role 은 그대로 주요주주). 한 줄로 바꿔요.
INSIDER_POS_HOLDER_WORDS = True


def _ele_txt(v):
    """elestock 칸의 글자. DART 는 빈 칸을 '-' 로 적어요 — '-' · 빈 칸은 '' (v19.6b: 예전에는 '-' 가 채워진 값으로 남아 직위가 '-' 인 줄이
    951건이었어요). (순수 함수)"""
    s = str(v if v is not None else "").strip()
    return "" if s in DASHES else s


def insider_pos_role(r):
    """elestock 한 행 → (직위 pos, 역할 role). (순수 함수)
    pos: 임원 직위(isu_exctv_ofcps), 없으면 주요주주 관계(isu_main_shrholdr · 10%이상주주 · 사실상지배주주 …), 없으면 ''.
    role (v19.6b Part B.1): 임원 = 직위가 있거나 등기·비등기임원(isu_exctv_rgist_at)으로 적힌 사람 · 주요주주 = 주요주주 칸만 적힌 사람 ·
    둘 다 적힌 사람(2026-11-15 삼성전자 3,378행 중 8행: 상무이면서 10%이상주주)은 '임원·주요주주' (Jack 2026-11-19, 7c) · 둘 다 없으면 None.
    pos 는 임원 직위가 먼저예요 (그대로)."""
    ofc, reg, maj = _ele_txt(r.get("isu_exctv_ofcps")), _ele_txt(r.get("isu_exctv_rgist_at")), _ele_txt(r.get("isu_main_shrholdr"))
    officer = bool(ofc or reg)
    role = (INSIDER_BOTH if maj else "임원") if officer else ("주요주주" if maj else None)
    return (ofc or maj), role


def parse_elestock_rows(rows):
    """행 묶음(같은 보고서)에서 대표 행(증감 최대)을 뽑습니다. (순수 함수)"""
    best = None
    for r in rows:
        q = _num(r.get("sp_stock_lmp_irds_cnt"))
        if q is None or q == 0:
            continue
        if best is None or abs(q) > abs(best["q"]):
            pos, role = insider_pos_role(r)
            best = {"q": int(q),
                    "nm": (r.get("repror") or "").strip(),
                    "pos": pos, "role": role,
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
        out.append({"rc": key, "d": b["d"], "nm": b["nm"], "pos": b["pos"], "role": b["role"], "q": b["q"], "r": b["r"]})
    return out


def insider_fix_roles(rows, fresh):
    """v19.6b: disc.json insider 줄의 pos · role 을 고쳐요 (제자리에서). fresh = {접수번호: (pos, role)} — 오늘 elestock 응답에서 다시 읽은
    값 (지난 실행이 넣은 줄도 그 회사를 오늘 다시 받았으면 있어요 · 호출이 늘지 않아요). 없는 줄은 pos 의 '-' 만 '' 로 바꾸고 role 은
    모름(None, 짐작하지 않아요). → 센 것 {"fresh", "dash", "unknown"}. (순수 함수 · 줄은 고쳐요)"""
    n = collections.Counter()
    for r in rows:
        got = fresh.get(r.get("rc"))
        if got is not None:
            if (r.get("pos"), r.get("role")) != got or "role" not in r:
                n["fresh"] += 1
            r["pos"], r["role"] = got
            continue
        if isinstance(r.get("pos"), str) and r["pos"].strip() in DASHES:
            n["dash"] += 1
            r["pos"] = ""
        if r.get("role") not in INSIDER_ROLES:
            if "role" not in r:
                n["unknown"] += 1
            r["role"] = None
    return n


def carry_prev_nps(fresh, prev_nps, bgn):
    """새로 받은 국민연금 항목 + 그 회사가 없는 지난 발행본 항목(조회 기간 bgn 이후만). 공시일은 그대로 둬요 (다시 날짜를 붙이지 않아요).
    새로 받은 회사는 새 값이 이겨요. (순수 함수) 반환: (합친 목록 최신순, 가져온 지난 항목 수)."""
    have = {r.get("t") for r in fresh}
    old = [r for r in prev_nps if r.get("t") not in have and str(r.get("d") or "") >= bgn]
    return sorted(fresh + old, key=lambda r: r.get("d", ""), reverse=True), len(old)


def disc_rows_sector_now(rows, info):
    """2026-11-20 (리뷰 · 예전 뱁새 전력기기 회사 옮기기): 지난 실행에서 이어 온 공시 줄(내부자 · 국민연금)의 예전 뱁새 업종 키 s 를 오늘
    종목의 값으로 맞춰요 — 새 줄과 같은 규칙 (그 종목의 s, 없으면 etc). 공시·수급 탭이 업종을 줄의 s 로 세고 거르니 (src/disc.jsx), 그대로
    두면 한 회사가 90일 동안 두 업종에 나뉘어 보여요. 오늘 데이터에 없는 종목의 줄은 그대로 둬요 (알 수 없어요).
    오늘 업종이 etc(오늘 업종 글자가 비었을 수 있어요)인데 줄에 진짜 업종이 있으면 그 업종을 둬요 — '오늘 모름' 은 '이제 기타' 가 아니에요
    (리뷰 2026-11-20 · 로그에 '!!' 와 수). 줄을 그 자리에서 바꿔요.
    반환: (바꾼 Counter {(전 키, 오늘 키): 줄 수}, 둔 Counter {줄의 업종 키: 줄 수} — 오늘 etc 라 두었어요). (순수 함수 — 줄만 바꿔요)"""
    ch, kept = collections.Counter(), collections.Counter()
    for r in rows:
        st = info.get(r.get("t"))
        if not st:
            continue
        now = st.get("s") or "etc"
        old = r.get("s")
        if old == now:
            continue
        if now == "etc" and old not in (None, "", "etc"):
            kept[old] += 1
            continue
        ch[(old, now)] += 1
        r["s"] = now
    return ch, kept


def disc_sector_lines(kind, ch, kept):
    """로그 줄: 업종 키를 오늘 값으로 바꾼 지난 공시 줄 수와 많이 바뀐 짝 (앞 8개) · 오늘 업종이 기타라 그대로 둔 줄이 있으면 '!!' 한 줄."""
    n = sum(ch.values())
    top = " · ".join(f"{a or '없음'}→{b} {k:,}" for (a, b), k in ch.most_common(8))
    out = [f"· {kind} 지난 줄 {n:,}건의 업종 키를 오늘 종목 값으로 바꿈" + (f" ({top}{' …' if len(ch) > 8 else ''})" if n else "")]
    if kept:
        out.append(f"  !! {kind} 지난 줄 {sum(kept.values()):,}건은 오늘 업종이 기타(etc)라 원래 업종 키를 그대로 둬요 (오늘 업종 글자가 빈 종목 · "
                   + " · ".join(f"{k} {v:,}" for k, v in kept.most_common(8)) + ")")
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
    fresh = {}       # v19.6b: 접수번호 → (pos, role) — 오늘 응답에서 다시 읽은 직위 · 역할 (지난 실행이 넣은 줄도 고쳐요)

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
            fresh[e["rc"]] = (e["pos"], e["role"])
            if e["rc"] in known:
                continue
            price = _fin(s.get("price"))
            amt = round(abs(e["q"]) * price / 1e8, 1) if price else None
            out.append({"rc": e["rc"], "d": e["d"], "t": t, "nk": s["nk"], "s": s.get("s") or "etc",
                        "cap": s.get("cap"), "nm": e["nm"], "pos": e["pos"], "role": e["role"], "q": e["q"], "r": e["r"], "amt": amt})
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
    for line in disc_sector_lines("내부자 거래", *disc_rows_sector_now(dedup, info)):    # 이어 온 줄의 업종 키 = 오늘 값 (새 줄은 이미 오늘 값)
        log(line)
    # v19.6b (Part B.1): 직위의 '-' 는 빈 칸 · 역할(role) 임원 | 주요주주 | null. 지난 실행이 넣은 줄도 오늘 다시 받은 회사면 같은 응답에서 고쳐요
    fx = insider_fix_roles(dedup, fresh)
    if not INSIDER_POS_HOLDER_WORDS:
        for r in dedup:
            if r.get("role") == "주요주주":
                r["pos"] = ""                  # 주요주주 관계 말을 보이지 않아요 (스위치 · 위 주석)
    rc_ = collections.Counter(r.get("role") for r in dedup)
    words = collections.Counter(r.get("pos") or "(빈 칸)" for r in dedup if r.get("role") == "주요주주")
    log(f"{'  !! ' if fx['unknown'] else '· '}내부자 역할(role): 임원 {rc_['임원']:,} · 주요주주 {rc_['주요주주']:,} · "
        f"{INSIDER_BOTH} {rc_[INSIDER_BOTH]:,} · 없음 {rc_[None]:,} "
        f"(오늘 응답으로 고친 지난 줄 {fx['fresh']:,} · 직위 '-' 를 빈 칸으로 {fx['dash']:,}"
        + (f" · 오늘 다시 받지 못해 역할을 모르는 지난 줄 {fx['unknown']:,} — null 로 둬요" if fx["unknown"] else "") + ")"
        + f" · 주요주주 줄의 직위 (DART 의 말 그대로{'' if INSIDER_POS_HOLDER_WORDS else ' — 스위치가 꺼져 빈 칸'}): "
        + (" · ".join(f"{w} {n:,}" for w, n in words.most_common()) or "없음"))

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
    for line in disc_sector_lines("국민연금", *disc_rows_sector_now(nps, info)):           # 지난 발행본에서 이어 온 줄 (carry_prev_nps)
        log(line)
    log(f"· 국민연금(majorstock): 상태 {dict(nps_stat)} · 채택 {len(nps):,}건 · 내부자 누적 {len(dedup):,}건"
        + (" · 상한 도달, 다음 실행이 이어받음" if len(targets) >= DISC_CALL_CAP else ""))
    client.raise_if_fatal()
    ds = [r.get("d") for r in dedup + nps if r.get("d")]
    newest = max(ds) if ds else None
    newest = f"{newest[:4]}-{newest[4:6]}-{newest[6:8]}" if newest else None
    return {"asOf": end.isoformat(), "newest": newest, "listOk": list_ok, "insider": dedup, "nps": nps}


# ────────────────────────────────────────────────────────────
# v19.6b (Part B.1): disc.json issue — 유상증자 · 전환사채 · 신주인수권부사채 결정 (오늘 볼 것 카드의 데이터)
# ────────────────────────────────────────────────────────────
# 목록   list.json 주요사항보고서 (pblntf_ty B · pblntf_detail_ty B001) · 지분공시와 같은 90일. 철회된 공시(비고 rm '철') · 이름에 '철회'가 든
#        공시 · 종속회사 · 자회사 공시는 빼요. 교환사채 · 그 밖의 결정(무상증자 · 감자 · 합병)은 이번에 다루지 않아요. 유무상증자(유상증자와
#        무상증자를 한 번에 정한 결정)는 넣어요 (Jack 2026-11-19, 7a): 안에서는 종류 pifric 으로 따로 읽고, 줄은 kind rights + bonus: true.
# 상세   piicDecsn · cvbdIsDecsn · bdwtIsDecsn · pifricDecsn (ISSUE_EP). 회사 · 종류마다 한 번 부르면 결정마다 한 줄이 와요 — 그 결정의 마지막
#        판(본문이 바뀐 마지막 공시)의 접수번호로. 2026-11-15 확인: 더코디 유상증자 공시 33건 → 결정 4줄 · 애드바이오텍 CB 21건 → 1줄 ·
#        첨부정정(본문은 그대로)은 앞 판의 접수번호 그대로예요 (케스피온 CB: 2026-11-11 첨부정정 → 2026-01-20 공시 줄).
# 정정   한 결정은 한 줄: 상세 API 가 주는 결정 줄 중 접수번호가 목록 기간 안에 있는 것 (d = 그 공시의 날짜 · cor = 그 공시가 정정 공시인지).
#        목록의 rm '정'(뒤에 정정 공시가 있음)만으로는 빼지 않아요 — 뒤가 첨부정정뿐이면 그 공시가 결정의 마지막 판이에요 (육일씨엔에쓰 2026-08-26).
#        Part B.1 의 '같은 회사 · 종류 · bd 는 한 결정' 규칙은 쓰지 않아요: 이사회 한 번에 여러 회차를 정한 회사가 있어 (서진시스템 2026-08-24
#        CB 네 건 · 아스트 2024-03-04 CB 7회 · 8회) 그 규칙은 다른 결정을 지워요 (Jack 의 yes 2026-11-19, Q19: DART 의 기록을 따라요).
# 캐시   DART 캐시 '{접수번호}|issue|v2': 000 결정의 마지막 판 (읽은 칸) · nh 마지막 판이 아님 (뒤에 정정이 있는 옛 판 · 첨부정정) · nf 마지막 판이어야
#        하는데(rm 이 비었고 첨부정정이 아님) 상세에 없음 → 다음 날(한국 날짜) 다시. 기간 안 공시 중 캐시에 없는 것이 있는 (회사, 종류)만 다시
#        부르고, 부르면 그 쌍의 기간 안 공시를 모두 다시 적어요 (새 정정이 오면 옛 판이 nh 로 바뀌어요). 결정 공시의 칸은 접수번호마다 바뀌지
#        않아서 full 실행에서도 캐시를 써요 (업종 코드처럼). 공시가 목록 기간을 벗어나면 지워요. 실행당 ISSUE_PER_RUN 쌍까지 (최근 공시부터).
# 칸     rc 접수번호 · d 공시일 YYYYMMDD · t 종목코드 · nk 이름 · kind rights | cb | bw · bd 이사회결의일 YYYYMMDD (사채: 상세 API 의 bddd ·
#        유무상증자: pifricDecsn 의 fric_bddd · 유상증자: API 에 칸이 없어 여기서는 null — main 이 fill_issue_bd 로 공시 원문에서 읽어 채워요
#        (Q18 · 못 읽으면 null) · 유상증자 줄의 bd 는 모두 fill_issue_bd 가 공시일과 맞는지 봐요) ·
#        how (유상증자만) holders 주주배정 · 주주우선공모 / others 제3자배정 · 일반공모 / null 그 밖 ·
#        n · p (유상증자 · Jack 2026-11-19, 7b: 같은 종류끼리) n = 새 주식 수 — 보통주를 발행하면 새 보통주, 아니면 새 기타주식 (cls 가 어느
#        쪽인지: common | other) · p = n ÷ 같은 종류의 증자 전 주식 수 % (육일씨엔에쓰 2026-08-26: 2,305,918 ÷ 보통주 11,204,255 = 20.58%) ·
#        그 종류의 증자 전 주식이 '-' 이면(처음 내는 기타주식) p null · 그 칸이 없거나 읽지 못해도 p null (0 으로 치지 않아요 — 둘의 이유는
#        캐시의 pwhy 와 로그에서 따로 세요 · 리뷰 2026-11-19) · 보통주와 기타주식을 함께 내면 n · p 는 보통주, n2 · p2 는 기타주식
#        (그때만 있는 칸) · 사채의 p: 공시의 '전환(행사)에 따라 발행할 주식의 주식총수 대비 비율' · amt 사채 권면(전자등록)총액 원 (bd_fta ·
#        '-' 이면 null) · cor 정정 공시([기재정정] · [첨부정정] …)인지 · bonus 유무상증자면 true (그때만 있는 칸 · n · p · how 는 유상 몫 —
#        무상 몫의 숫자는 싣지 않아요). 유상증자 줄에는 늘 cls 가 있어요 (모르면 · 철회 · 읽는 중이면 null).
#        읽지 못한 칸은 null — 짐작하지 않아요. 주식 수 · 금액은 정수만 읽어요 (소수면 null).
# 철회   (리뷰 2026-11-16 · Jack 의 yes 2026-11-19, Q20) 상세 줄의 숫자 칸이 모두 '-' 인 정정 공시는 철회예요: DART 목록은 철회 표시(rm '철')를 붙이지 않고 '[기재정정]' 으로
#        모든 칸을 지워요 (더코디 2026-11-05 '납입금미납으로 유상증자철회' · 크라우드웍스 2026-08-21 '대체납입자 선정 불능에 따른 철회' · 쏘닉스 CB
#        2026-10-29 결정을 2026-11-10 에 지움). 그 줄은 wd: true 와 빈 숫자로 남겨요 (카드가 건너뛰게 · 데이터는 있는 그대로). 원래 결정이 기간
#        안에 있으면 그 공시는 옛 판(nh)이라 살아 있는 결정 줄이 없어요.
# 읽는 중 상세를 아직 못 읽은 마지막 판 공시(실행당 한도 · nf · 조회 실패)는 pend: true 와 빈 숫자로 넣어요 (공시가 있다는 것은 보여 줘요). 그 (회사,
#        종류)의 '정' 표시 공시는 그동안 넣지 않아요 — 새 판이 바꾼 옛 숫자를 지금 것처럼 보이지 않게 (하루 늦게 보일 수 있어요).
# 실패   DART 가 실행을 멈추는 상태(한도 020 · 키 오류)를 이 단계에서 만나면 지난 발행본의 줄을 두고 issueOk false — 실행은 멈추지 않아요 (아직 어느
#        화면도 이 칸을 읽지 않아요 · 리뷰 2026-11-16). 지분공시(fetch_disclosures)의 규칙은 그대로예요.
ISSUE_TAG = "issue|v4"           # 캐시 키 '{접수번호}|issue|v4' — 읽는 방법이 바뀌면 올려요 (v2: 철회 표시 blank · 정수만 · v3: 같은 종류 n · p ·
                                 # cls · n2 · p2 — Jack 2026-11-19, 7b · v4: 없는 칸 · 빈 글자는 0 이 아니라 읽지 못함 + 비율이 빈 이유 pwhy —
                                 # 리뷰 2026-11-19). 다른 판의 키는 지워요 (한 번 다시 읽어요)
ISSUE_KINDS = ("rights", "cb", "bw")    # 줄의 kind
ISSUE_SRC = ISSUE_KINDS + ("pifric",)   # 목록 · 상세를 읽는 종류 (pifric 유무상증자 → 줄은 kind rights + bonus: true · Jack 2026-11-19, 7a)
ISSUE_RIGHTS = ("rights", "pifric")
ISSUE_KO = {"rights": "유상증자", "cb": "CB", "bw": "BW", "pifric": "유무상증자"}
ISSUE_EP = {"rights": "piicDecsn.json", "cb": "cvbdIsDecsn.json", "bw": "bdwtIsDecsn.json", "pifric": "pifricDecsn.json"}
ISSUE_PRE = {"rights": "", "pifric": "piic_"}   # 유상 몫의 칸 이름 앞머리 (pifricDecsn 은 유상 몫 piic_ · 무상 몫 fric_)
ISSUE_P_KEY = {"cb": "cvisstk_tisstk_vs", "bw": "nstk_isstk_tisstk_vs"}   # 사채: 공시의 '주식총수 대비 비율(%)'
ISSUE_PER_RUN = 150              # 한 실행에서 상세를 새로 부르는 (회사, 종류) 수 상한 — 2026-11-15 의 90일치 약 225쌍은 두 실행에 나눠요
ISSUE_MAX_PAGES = 40             # 목록 100건짜리 쪽 수 상한 (2026-11-15: 2,228건 · 23쪽). 넘으면 목록을 다 읽지 못한 것 (지난 줄을 둬요)
ISSUE_EST_PAGES = 25             # 호출 수 어림용 목록 쪽 수
ISSUE_WD_KEYS = {"rights": ("nstk_ostk_cnt", "nstk_estk_cnt", "fv_ps", "bfic_tisstk_ostk", "bfic_tisstk_estk", "fdpp_fclt", "fdpp_bsninh",
                            "fdpp_op", "fdpp_dtrp", "fdpp_ocsa", "fdpp_etc"),
                 "cb": ("bd_fta", "bddd", "cvisstk_tisstk_vs"), "bw": ("bd_fta", "bddd", "nstk_isstk_tisstk_vs")}   # 모두 '-' 인 정정 = 철회
ISSUE_WD_KEYS["pifric"] = tuple("piic_" + k for k in ISSUE_WD_KEYS["rights"])
ISSUE_DETAIL_FROM = "20150101"   # 상세 API 의 기간 시작 (최초접수일 · DART 는 2015년부터 줘요): 오래전 결정을 오늘 정정한 공시도 찾게 (아스트 2024년
                                 # CB 네 건을 2026-11-06 에 정정 · 730일로는 못 찾았어요) · 호출 수는 그대로


def issue_kind(report_nm):
    """주요사항보고서 이름 → (rights | cb | bw | pifric | None, 정정 공시인지, 첨부만 고친 공시인지). 앞의 [기재정정] · [첨부정정] 표시는
    떼고 종류를 봐요 (dvwhy_kind). pifric = 유무상증자 (Jack 2026-11-19, 7a). 철회 공시 · 종속회사 · 자회사 공시 · 교환사채 · 다른 결정은
    None. (순수 함수)"""
    kind, wd = dvwhy_kind(report_nm)
    head = re.match(r"^((?:\[[^\]]*\])*)", re.sub(r"\s+", "", str(report_nm or ""))).group(1)
    return (kind if kind in ISSUE_SRC and not wd else None), "정정" in head, "첨부" in head


def issue_filings(items, corp2t, bgn):
    """list.json 줄들 → (오늘 국내 종목의 유상증자 · CB · BW 공시 [{rc, d, corp, t, kind, cor, att, sup}], 센 것). (순수 함수)
    att = 첨부만 고친 공시 · sup = 비고(rm)에 '정' (뒤에 정정 공시가 있음). 철회된 공시(rm '철')는 빼요. corp2t 는 기업코드 → 오늘 국내 종목 코드."""
    out, n, seen = [], collections.Counter(), set()
    for it in items or []:
        if not isinstance(it, dict):
            n["bad"] += 1
            continue
        kind, cor, att = issue_kind(it.get("report_nm"))
        if kind is None:
            continue
        rc = str(it.get("rcept_no") or "").strip()
        corp = str(it.get("corp_code") or "").strip()
        t = corp2t.get(corp)
        if not t:
            n["other"] += 1                  # 비상장 · 오늘 국내 목록 밖 회사
            continue
        d = (_kdate(it.get("rcept_dt")) or _rc_date(rc) or "").replace("-", "")
        if not _RCPT.match(rc) or not d:
            n["bad"] += 1
            continue
        if d < bgn or rc in seen:
            continue
        seen.add(rc)
        rm = str(it.get("rm") or "")
        if "철" in rm:
            n["withdrawn"] += 1
            continue
        out.append({"rc": rc, "d": d, "corp": corp, "t": t, "kind": kind, "cor": cor, "att": att, "sup": "정" in rm})
    return out, n


def issue_how(text):
    """유상증자 방식(ic_mthn) → holders (주주배정 · 주주우선공모: 지금 주주가 먼저 살 수 있어요 — 주주배정후 실권주 일반공모 포함) ·
    others (제3자배정 · 일반공모) · None (그 밖이거나 비었음). (순수 함수)"""
    s = re.sub(r"\s+", "", str(text or ""))
    if "주주배정" in s or "주주우선공모" in s:
        return "holders"
    if "제3자배정" in s or "일반공모" in s:
        return "others"
    return None


def _issue_pct(x):
    """양수 % → 소수 둘째 자리 (0.005% 아래는 유효숫자 둘: 0 으로 반올림돼 '없음'처럼 보이지 않게). (순수 함수)"""
    return round(x, 2) if x >= 0.005 else float(f"{x:.2g}")


def _issue_whole(x):
    """주식 수 · 원 금액: 정수인 양수만 (소수면 읽지 못한 것 — int(round()) 가 0 이나 다른 수로 바꾸지 않게). (순수 함수)"""
    return x if isinstance(x, float) and x > 0 and x == int(x) else None


def _issue_count(v):
    """주식 수 칸 → 정수: '-' 는 0 (DART 는 그 종류가 없으면 '-' 로 적어요) · 0 이상의 정수는 그 수. 칸이 없거나(None) 빈 글자 · 소수 · 음수 ·
    글자는 None (읽지 못함 — 0 으로 치지 않아요 · 리뷰 2026-11-19). (순수 함수)"""
    if v is None:
        return None
    t = str(v).strip()
    if t in DASHES:
        return 0
    x = _num(t) if t else None
    return int(x) if isinstance(x, float) and x >= 0 and x == int(x) else None


def issue_rights_numbers(row, pre=""):
    """유상증자(유무상증자의 유상 몫 pre="piic_") 상세 한 줄 → {cls, n, p} (+ 보통주와 기타주식을 함께 내면 n2 · p2), 읽지 못한 칸 [이름].
    Jack 2026-11-19 (7b): 같은 종류끼리 — 새 보통주 ÷ 증자 전 보통주 · 새 기타주식 ÷ 증자 전 기타주식. 보통주를 내면 n · p 는 보통주
    (cls common), 기타주식만 내면 기타주식 (cls other). 비율이 빈 이유는 pwhy {p · p2: zero | unread} 에 적어요 (캐시에만 · 줄에는 싣지 않아요):
    zero = 그 종류의 증자 전 주식이 '-' · 0 (나눌 수 없어요 — 처음 내는 기타주식) · unread = 증자 전 주식 수 칸이 없거나 읽지 못함 (0 으로
    치지 않아요 · 리뷰 2026-11-19). 새 주식 수를 읽지 못하면 셋 다 null. (순수 함수)"""
    on, en = _issue_count(row.get(pre + "nstk_ostk_cnt")), _issue_count(row.get(pre + "nstk_estk_cnt"))
    ob, eb = _issue_count(row.get(pre + "bfic_tisstk_ostk")), _issue_count(row.get(pre + "bfic_tisstk_estk"))
    out = {"cls": None, "n": None, "p": None}
    if on is None or en is None or (on == 0 and en == 0):
        return out, ["n", "p"]
    why, bad = {}, []

    def pct(key, new, before):
        if before is None:
            why[key] = "unread"
            bad.append(key)
            return None
        if before == 0:
            why[key] = "zero"
            return None
        return _issue_pct(new / before * 100)
    if on > 0:
        out.update(cls="common", n=on, p=pct("p", on, ob))
        if en > 0:
            out.update(n2=en, p2=pct("p2", en, eb))
    else:
        out.update(cls="other", n=en, p=pct("p", en, eb))
    if why:
        out["pwhy"] = why
    return out, bad


def issue_blank(row, kind):
    """상세 줄의 숫자 칸(ISSUE_WD_KEYS)이 모두 있고 모두 '-' · 빈 칸인지 — 정정 공시면 철회예요. (순수 함수)"""
    keys = ISSUE_WD_KEYS[kind]
    return all(k in row for k in keys) and all(str(row.get(k) if row.get(k) is not None else "").strip() in DASHES | {""} for k in keys)


def parse_issue_detail(row, kind):
    """상세 API 한 줄 → ({bd, how, n, p, amt, blank} + 유상증자는 cls (· n2 · p2), 읽지 못한 칸 [이름]). 읽지 못한 칸은 None.
    blank = 숫자 칸이 모두 '-'. 유무상증자(pifric)는 유상 몫(piic_)을 읽고 bd 는 fric_bddd (pifricDecsn 의 이사회결의일). (순수 함수)"""
    out = {"bd": None, "how": None, "n": None, "p": None, "amt": None, "blank": issue_blank(row, kind)}
    if kind in ISSUE_RIGHTS:
        pre = ISSUE_PRE[kind]
        got, bad = issue_rights_numbers(row, pre)
        out.update(got)
        out["how"] = issue_how(row.get(pre + "ic_mthn"))
        if kind == "pifric":
            bd = _kdate(row.get("fric_bddd"))
            out["bd"] = bd.replace("-", "") if bd else None
        return out, bad
    bd = _kdate(row.get("bddd"))
    out["bd"] = bd.replace("-", "") if bd else None
    p = _dash_none(row.get(ISSUE_P_KEY[kind]))
    out["p"] = _issue_pct(p) if isinstance(p, float) and p > 0 else None
    amt = _issue_whole(_dash_none(row.get("bd_fta")))
    out["amt"] = int(amt) if amt is not None else None
    return out, [k for k in ("bd", "p", "amt") if out[k] is None]


def issue_label(fs, api_rows, kind):
    """한 (회사, 종류)의 기간 안 공시들 + 상세 API 응답 → {접수번호: (상태, 읽은 칸 · 없으면 None, 읽지 못한 칸)}. (순수 함수)
    000 = 상세에 있는 결정 줄 (그 결정의 마지막 판) · nh = 상세에 없고 마지막 판이 아님 (rm '정' · 첨부정정) · nf = 상세에 없는데 마지막 판이어야 함."""
    by = {}
    for x in api_rows or []:
        if isinstance(x, dict):
            by.setdefault(str(x.get("rcept_no") or "").strip(), x)
    out = {}
    for f in fs:
        row = by.get(f["rc"])
        if row is not None:
            d, bad = parse_issue_detail(row, kind)
            out[f["rc"]] = ("000", d, bad)
        else:
            out[f["rc"]] = ("nh" if f["sup"] or f["att"] else "nf", None, [])
    return out


def issue_rows(filings, label, info):
    """기간 안 공시 + 상태 ({접수번호: (상태, 칸)}) → disc.json issue 줄 (공시일 · 접수번호 최신순). (순수 함수)
    000 은 읽은 칸으로 — 숫자 칸이 모두 '-' 인 정정 공시는 철회라 wd: true (숫자 null). 상태를 아직 모르거나(실행당 한도 · 조회 실패) nf 인
    공시는 마지막 판으로 보이는 것(rm '정' 아님 · 첨부정정 아님)만 pend: true 와 숫자 null 로 넣어요. 그런 공시가 있는 (회사, 종류)의 rm '정'
    공시는 그동안 넣지 않아요 (새 판에 바뀐 옛 결정일 수 있어 옛 숫자가 지금 것처럼 보이지 않게). nh 는 넣지 않아요."""
    def plain(f, st):
        return st not in ("000", "nh") and not f["sup"] and not f["att"]
    waiting = {(f["corp"], f["kind"]) for f in filings if plain(f, (label.get(f["rc"]) or (None,))[0])}
    rows = []
    for f in filings:
        st, g = (label.get(f["rc"]) or (None, None))[:2]
        if st == "nh" or (st != "000" and (f["sup"] or f["att"])):
            continue
        if st == "000" and f["sup"] and (f["corp"], f["kind"]) in waiting:
            continue
        g = g if st == "000" and isinstance(g, dict) else {}
        wd = st == "000" and bool(g.get("blank")) and bool(f["cor"])
        rt = f["kind"] in ISSUE_RIGHTS
        live = not wd
        row = {"rc": f["rc"], "d": f["d"], "t": f["t"], "nk": (info.get(f["t"]) or {}).get("nk") or f["t"], "kind": "rights" if rt else f["kind"],
               "bd": g.get("bd") if live and f["kind"] != "rights" else None, "how": g.get("how") if rt and live else None,
               "n": g.get("n") if rt and live else None, "p": g.get("p") if live else None, "amt": None if rt or wd else g.get("amt"),
               "cor": bool(f["cor"])}
        if rt:
            row["cls"] = g.get("cls") if live else None
            if live and "n2" in g:
                row["n2"], row["p2"] = g["n2"], g.get("p2")
        if f["kind"] == "pifric":
            row["bonus"] = True
        if wd:
            row["wd"] = True
        if st != "000":
            row["pend"] = True
        rows.append(row)
    rows.sort(key=lambda r: (r["d"], r["rc"]), reverse=True)
    return rows


def empty_disc(today):
    """DART 없이 도는 실행(dart=off · 키 없음)의 disc.json: 목록을 못 받은 것으로 적어요 (listOk · issueOk false — 관문이 다른 DART 줄과 함께 막아요)."""
    return {"asOf": today.isoformat(), "newest": None, "listOk": False, "insider": [], "nps": [], "issue": [], "issueOk": False}


def _issue_keep_prev(prev, bgn):
    """목록을 받지 못한 날: 지난 발행본의 issue 줄 중 기간 안의 것 그대로 (자기 공시일 그대로). (순수 함수)"""
    return [r for r in prev if isinstance(r, dict) and isinstance(r.get("d"), str) and r["d"] >= bgn]


def fetch_issues(kr_stocks, cmap, end, client):
    """v19.6b (Part B.1): 최근 90일 유상증자 · 전환사채 · 신주인수권부사채 결정 → {"issue": [...], "issueOk": 목록을 다 읽었는지}.
    목록을 받지 못하면(또는 다 읽지 못하면) 지난 발행본의 줄을 자기 날짜 그대로 두고 issueOk false (국민연금과 같아요 · 앱은 늦음/실패 줄).
    90일에 한 건도 없으면 빈 목록이 맞아요 (issueOk true)."""
    info = {s["t"]: s for s in kr_stocks if s.get("cls") == "kr"}
    corp2t = {v: k for k, v in (cmap or {}).items() if k in info}
    bgn = (end - dt.timedelta(days=DISC_DAYS - 1)).strftime("%Y%m%d")       # 지분공시 목록과 같은 기간
    prev = []
    try:
        with open(OUT_DISC, encoding="utf-8") as f:
            prev = json.load(f).get("issue") or []
        prev = prev if isinstance(prev, list) else []
    except Exception as e:
        log(f"  !! 지난 disc.json 을 읽지 못했어요({e}) → 목록을 못 받는 날 둘 주요사항 공시 줄이 없어요")

    items, page, note = [], 1, None
    while True:
        j = client.get("list.json", {"bgn_de": bgn, "end_de": end.strftime("%Y%m%d"), "pblntf_ty": "B", "pblntf_detail_ty": "B001",
                                     "page_no": str(page), "page_count": "100"})
        st = str(j.get("status")) if j else None
        if st == "013":                       # 그 기간에 공시가 없어요 (조용한 날 — 맞는 빈 목록)
            break
        if st != "000":
            note = f"status={st} msg={j.get('message')}" if j else "응답 없음"
            break
        items += j.get("list") or []
        total = _num(j.get("total_count"))
        if total is None:
            note = f"전체 건수(total_count {j.get('total_count')!r})를 읽지 못해 목록을 다 읽었는지 몰라요"
            break
        if page * 100 >= total:
            break
        if page >= ISSUE_MAX_PAGES:
            note = f"{ISSUE_MAX_PAGES}쪽을 넘어요 (전체 {total:,.0f}건) — 다 읽지 못했어요"
            break
        page += 1
    if note:
        return _issue_failed(prev, bgn, f"주요사항 공시 목록(list.json B001)을 받지 못해 — {note}", client)

    filings, cnt = issue_filings(items, corp2t, bgn)
    today_iso = client.today.isoformat()
    key = lambda rc: f"{rc}|{ISSUE_TAG}"                                       # noqa: E731
    pairs = collections.defaultdict(list)
    for f in filings:
        pairs[(f["corp"], f["kind"])].append(f)
    label, need, cached = {}, [], 0
    with client.lock:
        for pk, fs in pairs.items():
            due = False
            for f in fs:
                e = client.entries.get(key(f["rc"]))
                st = (e or {}).get("st")
                if st == "000" and isinstance(e.get("d"), dict):
                    label[f["rc"]] = ("000", e["d"])
                elif st == "nh":
                    label[f["rc"]] = ("nh", None)
                elif st == "nf" and e.get("at") == today_iso:
                    label[f["rc"]] = ("nf", None)     # 오늘 이미 물었는데 상세에 없었어요 (내일 다시)
                else:
                    due = True
            if due:
                need.append((pk, fs))
            else:
                cached += 1
    need.sort(key=lambda kv: (max(f["d"] for f in kv[1]), kv[0]), reverse=True)
    todo, later = need[:ISSUE_PER_RUN], need[ISSUE_PER_RUN:]
    dend = end.strftime("%Y%m%d")
    calls0 = sum(client.status.values())

    def one(g):
        (corp, kind), _ = g
        j = client.get(ISSUE_EP[kind], {"corp_code": corp, "bgn_de": ISSUE_DETAIL_FROM, "end_de": dend})
        st = str(j.get("status")) if j else None
        if st not in ("000", "013"):
            return g, None
        return g, ((j.get("list") or []) if st == "000" else [])

    n, unread = collections.Counter(), collections.Counter()
    if todo:
        with ThreadPoolExecutor(max_workers=5) as ex:
            res = list(ex.map(one, todo))
        for ((corp, kind), fs), lst in res:
            if lst is None:
                n["fail"] += 1                # 조회 실패 (연결 · 점검 · 한도): 캐시를 고치지 않아요 — 다음 실행이 다시 물어요
                continue
            lab = issue_label(fs, lst, kind)
            with client.lock:
                for rc, (st, d, bad) in lab.items():
                    client.entries[key(rc)] = {"st": st, "at": today_iso, "d": d}
                    label[rc] = (st, d)
                    n[st] += 1
                    for b in bad:
                        unread[b] += 1
    # 목록 기간을 벗어난 공시의 캐시는 지워요 (적은 날 ≥ 공시일이라, 적은 날이 기간 앞이면 공시도 기간 밖이에요) · 다른 판(issue|v1 …)의 키도
    bgn_iso = f"{bgn[:4]}-{bgn[4:6]}-{bgn[6:8]}"
    with client.lock:
        old = [k for k, e in client.entries.items() if "|issue|" in k
               and (not k.endswith("|" + ISSUE_TAG) or str((e or {}).get("at") or "") < bgn_iso)]
        for k in old:
            del client.entries[k]
    if client.fatal:
        return _issue_failed(prev, bgn, f"상세를 읽는 중 DART 가 멈췄어요 (상태 {client.fatal[0]}: {client.fatal[1]}) — 오늘 읽은 상세는 캐시에 남아요",
                             client)

    rows = issue_rows(filings, label, info)
    read = {rc for rc, (st, _d) in label.items() if st == "000"}
    by_kind = collections.Counter(r["kind"] for r in rows)
    no_num = sum(1 for r in rows if r.get("pend"))
    wds = [r for r in rows if r.get("wd")]
    def pwhy(r, k):
        """그 줄의 비율 k (p · p2) 가 빈 이유: zero (그 종류의 증자 전 주식이 없음) · unread (읽지 못함) · None (이유 없음)."""
        g = (label.get(r["rc"]) or (None, None))[1]
        return ((g.get("pwhy") or {}) if isinstance(g, dict) else {}).get(k)

    # 유상증자의 '숫자 못 읽음': n 이 없거나, p · p2 가 비었는데 이유가 '그 종류의 증자 전 주식이 없음'(zero)이 아님 (리뷰 2026-11-19)
    part = sum(1 for r in rows if r["rc"] in read and not r.get("wd")
               and ((r["n"] is None or any(k in r and r[k] is None and pwhy(r, k) != "zero" for k in ("p", "p2")))
                    if r["kind"] == "rights" else any(r[k] is None for k in ("bd", "p", "amt"))))
    other = [r for r in rows if r["kind"] == "rights" and r.get("cls") == "other"]
    bonus = sum(1 for r in rows if r.get("bonus"))
    both = [r for r in rows if "n2" in r]
    nf_all = sum(1 for st, _d in label.values() if st == "nf")
    left = sum(len(fs) for _, fs in later)
    log(f"· 주요사항 공시 목록(list.json B001): {len(items):,}건 ({page}쪽) · 오늘 국내 종목의 유상증자 · CB · BW · 유무상증자 공시 {len(filings):,}건 "
        f"(뒤에 정정이 있는 공시 {sum(1 for f in filings if f['sup']):,} · 첨부정정 {sum(1 for f in filings if f['att']):,} 포함 · 철회 "
        f"{cnt['withdrawn']:,} · 목록 밖 회사 {cnt['other']:,} 뺌" + (f" · !! 읽지 못한 줄 {cnt['bad']:,}" if cnt["bad"] else "") + ")")
    log(f"{'  !! ' if (later or n['fail'] or nf_all) else '· '}주요사항 상세(piicDecsn · cvbdIsDecsn · bdwtIsDecsn · pifricDecsn): (회사, 종류) "
        f"{len(pairs):,}쌍 중 새로 조회 {len(todo):,} (호출 {sum(client.status.values()) - calls0:,}회) · 캐시로 끝 {cached:,}"
        + (f" · 실행당 한도({ISSUE_PER_RUN})에 닿아 다음 실행으로 {len(later):,}쌍 ({left:,}건)" if later else "")
        + (f" · 조회 실패 {n['fail']:,}쌍 (다음 실행이 다시)" if n["fail"] else "")
        + f" — 오늘 적은 공시: 결정 줄 {n['000']:,} · 옛 판 · 첨부정정 {n['nh']:,}"
        + (f" · 마지막 판인데 상세에 없음 {nf_all:,}건 (다음 날 다시)" if nf_all else "")
        + (f" · 지운 캐시 {len(old):,}" if old else ""))
    log(f"{'  !! ' if (no_num or part) else '· '}주요사항 공시: " + " · ".join(f"{ISSUE_KO[k]} {by_kind[k]:,}" for k in ISSUE_KINDS)
        + f" (정정 {sum(1 for r in rows if r['cor']):,}), 숫자 못 읽음 {part:,}"
        + (f" (오늘 읽은 것 중 {' · '.join(f'{k} {v:,}' for k, v in sorted(unread.items()))})" if unread else "")
        + " · 유상증자 방식이 주주배정 · 제3자배정 · 일반공모가 아니거나 모름 "
        + f"{sum(1 for r in rows if r['kind'] == 'rights' and r['rc'] in read and r['how'] is None):,}"
        + (f" · 상세를 아직 못 읽어 숫자 없이 줄만(pend) {no_num:,}" if no_num else "")
        + (f" · 유무상증자(bonus) {bonus:,}" if bonus else "")
        + (f" · 기타주식만 낸 유상증자 {len(other):,} (비율 없음: 증자 전 기타주식이 없어 "
           f"{sum(1 for r in other if r['p'] is None and pwhy(r, 'p') == 'zero'):,} · 증자 전 기타주식 수를 읽지 못해 "
           f"{sum(1 for r in other if r['p'] is None and pwhy(r, 'p') != 'zero'):,})" if other else "")
        + (f" · 보통주와 기타주식을 함께 낸 유상증자 {len(both):,} (n2 · p2 — p2 없음: 증자 전 기타주식이 없어 "
           f"{sum(1 for r in both if r['p2'] is None and pwhy(r, 'p2') == 'zero'):,} · 증자 전 기타주식 수를 읽지 못해 "
           f"{sum(1 for r in both if r['p2'] is None and pwhy(r, 'p2') != 'zero'):,})" if both else ""))
    if wds:
        log(f"  !! 주요사항 공시 철회 (숫자 칸이 모두 '-' 인 정정 공시 · wd: true · 카드가 건너뛰어요) {len(wds):,}건: "
            + ", ".join(f"{r['nk']} {ISSUE_KO['pifric' if r.get('bonus') else r['kind']]} {r['d']}" for r in wds[:40])
            + (" …" if len(wds) > 40 else ""))
    return {"issue": rows, "issueOk": True}


def _issue_failed(prev, bgn, why, client):
    """목록을 못 받았거나 DART 가 멈춘 날: 지난 발행본의 줄을 기간 안의 것만 자기 날짜 그대로 두고 issueOk false. 실행은 멈추지 않아요."""
    keep = _issue_keep_prev(prev, bgn)
    last = max((r["d"] for r in keep), default=None)
    log(f"  !! {why} — 지난 발행본의 주요사항 공시 {len(keep):,}건을 그대로 둬요 "
        f"(최근 공시 {f'{last[:4]}-{last[4:6]}-{last[6:8]}' if last else '없음'} · issueOk false · 실행은 계속해요)")
    return {"issue": keep, "issueOk": False}


# ────────────────────────────────────────────────────────────
# v19.6b Q18 (Jack 2026-11-19 "rights board date from documents: yes"): 유상증자 줄의 bd — 공시 원문(document.xml)의 이사회결의일(결정일)
# ────────────────────────────────────────────────────────────
# 왜     유상증자 상세 API(piicDecsn)에는 이사회결의일 칸이 없어요 (사채는 bddd 가 있어요). 그래서 fetch_issues 뒤에 main 이 유상증자 줄마다
#        (철회 wd · 읽는 중 pend 는 빼고 — 그 줄의 bd 는 늘 빈 칸) 그 공시의 원문을 한 번 읽어요 (fill_issue_bd).
# 읽기   원문 zip 의 본 파일 '{접수번호}.xml' 만 (없으면 첨부를 읽지 않고 못 읽은 것 — 리뷰 2026-11-19). 정정 공시의 앞 부분(<CORRECTION> · 정정 전 · 후 표)은 빼고, 첫 칸이 'N. 이사회결의일(결정일)' 인
#        표 줄의 값 칸 하나를 읽어요. DART 양식은 그 값을 <TU AUNIT="DRC_DT" AUNITVALUE="20261111">2026년 11월 11일</TU> 로 적어요 — 값과
#        글자가 같은 날이어야 해요. 칸 전체가 날짜 하나일 때만 날짜예요 ('2026년 11월 11일' · '2026-11-11' · '2026.11.11' · '20261111').
#        값이 '-' 이거나, 날짜가 아니거나, 값 칸이 여럿이거나, 그런 줄이 여럿인데 같은 날이 아니면 읽지 못한 것이에요 (null · 짐작하지 않아요).
#        조사 2026-11-19: 육일씨엔에쓰 20260826000431 · 뷰노 20261111000261 (정정 — 정정 표의 10-15 → 11-11 은 빼고 양식의 11-11) · STX
#        20261013000428 (회생계획 인가일 09-16 — 본문 문단의 '15. 이사회결의일(결정일)' 은 표 칸이 아니라 읽지 않아요).
# 확인   결의일이 공시일 d 보다 ISSUE_BD_MAX_YEARS 년 넘게 앞이 아니어야 해요 (Jack 2026-11-19, 7d: yes) — 아니면 그 줄의 bd 는 null 로 두고
#        '기간 밖이라 비움' 으로 따로 세요 (이름 · 이유 · 관문의 N 에 들지 않아요 — 관문은 빈 결의일로 경고만). 이 확인은 캐시의 값을 쓸 때마다 해요:
#        캐시에는 원문이 적은 날을 그대로 둬요 (리뷰 2026-11-19 — 한도를 바꿔도 판을 올릴 필요가 없고, 오래 미룬 제3자배정 정정이 '못 읽음'으로
#        굳지 않게). 공시일 뒤인 날은 여기서 쓰고, 쓰기 바로 앞의 own_check_disc 가 관문과 같은 함수(issue_bd_bad_rows)로 비우고 ownDrop.issueBd
#        에 세요 (Jack 의 상시 규칙 2026-11-19 — 한 번에 많이 틀리면 관문 실패).
# 캐시   DART 캐시 '{접수번호}|issuebd|v2': 000 (d = 원문이 적은 결의일) · nf (원문을 받았는데 결의일 칸을 읽지 못함 · zip 에 본 파일이 없음 —
#        why). 공시는 바뀌지 않아서 한 번만 읽어요 (정정은 새 접수번호). 다시 읽는 것은 조회 실패(응답 없음 · 빈 zip · 글자로 바꾸지 못한 본 파일)
#        · 해석 오류(파서가 멈춤) · 실행당 한도 · 시간 한도 · DART 멈춤뿐 — 적지 않고 다음 실행이 다시 읽어요. 공시가 90일 기간을 벗어나면
#        지워요 (다른 판의 키도 · v1 은 기간 밖 날을 nf 로 적었어요). full 실행에서도 캐시를 써요 (fetch_issues 처럼).
# 한도   실행당 원문 ISSUE_BD_PER_RUN 건 (최근 공시부터) · ISSUE_BD_SECONDS 초 (넘으면 남은 것은 다음 실행). 2026-11-16 의 90일치 유상증자
#        줄 약 160건 (169 − 철회): 머지 뒤 첫 실행이 최대 100건, 둘째 실행이 나머지 (첫 실행에 상세를 못 읽은 쌍의 줄 포함) — 그 뒤 하루 3~5건.
# 실패   원문 조회가 실패하거나 느려도 그 줄의 bd 만 null 이에요 — 실행은 계속해요 (issueOk 도 그대로: 줄의 다른 칸은 상세 API 로 다 읽었어요).
#        목록을 받지 못한 날(issueOk false)은 지난 발행본의 줄(그때의 bd)을 그대로 두고 원문을 읽지 않아요.
ISSUE_BD_TAG = "issuebd|v2"      # 캐시 키 '{접수번호}|issuebd|v2' — 읽는 방법이 바뀌면 올려요 (다른 판의 키는 지워요 · v2: 기간 확인은 쓸 때)
ISSUE_BD_PER_RUN = 100           # 한 실행에서 새로 읽는 원문 수 상한 (첫 실행의 약 160건은 두 실행에 나눠요)
ISSUE_BD_SECONDS = 180           # 원문 읽기에 쓰는 시간 상한 (초) — 넘으면 남은 원문은 다음 실행 (DART 가 느린 날 실행을 붙잡지 않게)
ISSUE_BD_TIMEOUT = 20            # 원문 하나의 응답 대기 (초)
ISSUE_BD_WORKERS = 4
ISSUE_BD_MAX_YEARS = 1           # 결의일이 공시일보다 이만큼 넘게 앞이면 bd 를 비워요 (잘못 읽은 날짜일 수 있어요 · 캐시를 쓸 때 확인 · Jack 에게 물어요)
_ISSUE_BD_LABEL = re.compile(r"(?:[0-9]+(?:-[0-9]+)?\.)?이사회결의일(?:[(（]결정일[)）])?")
_ISSUE_TR = re.compile(r"<tr\b[^>]*>([\s\S]*?)</tr\s*>", re.I)
_ISSUE_CELL = re.compile(r"<(td|th|te|tu)\b([^>]*)>([\s\S]*?)</\1\s*>", re.I)


def issue_bd_day(s):
    """원문 칸 글자 → 'YYYYMMDD' — 칸 전체가 날짜 하나일 때만 ('2026년 11월 11일' · '2026-11-11' · '2026.11.11' · '20261111' · 빈칸은
    무시). 아니면 None (아라비아 숫자 0-9 만 · 없는 날짜도 None). (순수 함수)"""
    t = re.sub(r"\s+", "", str(s if s is not None else ""))
    m = (re.fullmatch(r"(?P<y>20[0-9]{2})년(?P<m>[0-9]{1,2})월(?P<d>[0-9]{1,2})일", t)
         or re.fullmatch(r"(?P<y>20[0-9]{2})(?P<s>[-.])(?P<m>[0-9]{1,2})(?P=s)(?P<d>[0-9]{1,2})\.?", t)
         or re.fullmatch(r"(?P<y>20[0-9]{2})(?P<m>[0-9]{2})(?P<d>[0-9]{2})", t))
    if not m:
        return None
    try:
        return dt.date(int(m.group("y")), int(m.group("m")), int(m.group("d"))).strftime("%Y%m%d")
    except ValueError:
        return None


def _issue_cell_text(c):
    s = html_unescape(re.sub(r"<[^>]+>", " ", c)).replace("&cr;", " ")
    return re.sub(r"\s+", " ", s).strip()


def _issue_bd_cell(attrs, txt):
    """결의일 줄의 값 칸 하나 → (bd, 이유). AUNIT="DRC_DT" 칸의 AUNITVALUE 가 있으면 글자와 같은 날이어야 해요. (순수 함수)"""
    av = None
    if re.search(r'\bAUNIT\s*=\s*"DRC_DT"', attrs, re.I):
        m = re.search(r'\bAUNITVALUE\s*=\s*"([^"]*)"', attrs, re.I)
        av = m.group(1).strip() if m else None
    tv = issue_bd_day(txt)
    if av and av not in DASHES:
        a = issue_bd_day(av) if re.fullmatch(r"[0-9]{8}", av) else None
        if a is None:
            return None, f"결의일 칸의 값 '{av[:12]}' 이 날짜가 아니에요"
        if tv != a:
            return None, f"결의일 칸의 값 {a} 와 글자 '{txt[:20]}' 가 달라요"
        return a, None
    if tv:
        return tv, None
    if not txt or txt in DASHES:
        return None, "결의일 칸이 비었어요 ('-')"
    return None, f"결의일 '{txt[:20]}' 을 날짜로 읽지 못했어요"


def parse_issue_bd(text):
    """유상증자결정 원문 → (이사회결의일 'YYYYMMDD', None) 또는 (None, 읽지 못한 이유). 공시일과의 확인은 read_issue_bd. (순수 함수)"""
    if not text:
        return None, "원문 없음"
    body = re.sub(r"<correction\b[\s\S]*?</correction\s*>", " ", str(text), flags=re.I)     # 정정 전 · 후 표는 빼요 (양식 쪽만)
    got, multi = [], 0
    for tr in _ISSUE_TR.findall(body):
        cells = _ISSUE_CELL.findall(tr)
        if not cells or not _ISSUE_BD_LABEL.fullmatch(re.sub(r"\s+", "", _issue_cell_text(cells[0][2]))):
            continue
        vals = [(a, _issue_cell_text(c)) for _tag, a, c in cells[1:]]
        vals = [(a, t) for a, t in vals if t or re.search(r'\bAUNITVALUE\s*=\s*"[^"\s]', a, re.I)]
        if len(vals) > 1:
            multi += 1                     # 값 칸이 여럿인 줄 = 정정 전 · 후 표 (<CORRECTION> 밖에 있는 옛 원문) — 양식의 줄(값 하나)만 읽어요
        else:
            got.append(_issue_bd_cell(*vals[0]) if vals else (None, "결의일 칸이 비었어요 ('-')"))
    if not got:
        return None, (f"이사회결의일 줄 {multi}개가 모두 값 칸이 여럿이에요 (정정 전 · 후 표뿐)" if multi
                      else "원문에 이사회결의일(결정일) 칸이 없어요")
    days = {bd for bd, _ in got}
    if len(got) > 1 and (len(days) > 1 or None in days):
        return None, f"이사회결의일 줄이 {len(got)}개인데 같은 날이 아니에요 ({', '.join(str(bd or why) for bd, why in got[:3])})"
    return got[-1]


def _ymd_date(s):
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8])) if isinstance(s, str) and re.fullmatch(r"[0-9]{8}", s) else None
    except ValueError:
        return None


def issue_bd_window_why(bd, d):
    """결의일 bd 가 날짜이고 공시일 d 보다 ISSUE_BD_MAX_YEARS 년 넘게 앞이 아닌지 (Jack 2026-11-19, 7d) → None (맞음) 또는 이유. 공시일 뒤인지는
    보지 않아요 — 그것은 관문 파일의 issue_bd_bad_rows 가 봐요 (Jack 의 상시 규칙: 같은 함수로 쓰기 앞에서 비우고 ownDrop.issueBd 에 세요). (순수 함수)"""
    b, f = _ymd_date(bd), _ymd_date(d)
    if b is None:
        return f"결의일 {bd!r} 이 날짜가 아니에요"
    if f is None:
        return f"공시일 {d!r} 을 읽지 못했어요"
    lo = dt.date(f.year - ISSUE_BD_MAX_YEARS, f.month, 28 if (f.month, f.day) == (2, 29) else f.day)
    if b < lo:
        return f"결의일 {bd} 이 공시일 {d} 보다 {ISSUE_BD_MAX_YEARS}년 넘게 앞이에요"
    return None


def issue_bd_range_why(bd, d):
    """결의일 bd 가 공시일 d 와 맞는지 (d 이하 · ISSUE_BD_MAX_YEARS 년 넘게 앞이 아님) → None (맞음) 또는 이유. (순수 함수 · read_issue_bd)
    공시일 뒤인지는 관문 파일의 같은 함수(issue_bd_bad_rows)로 봐요."""
    why = issue_bd_window_why(bd, d)
    if why:
        return why
    return f"결의일 {bd} 이 공시일 {d} 뒤예요" if issue_bd_bad_rows([{"kind": "rights", "bd": bd, "d": d}]) else None


def read_issue_bd(text, d):
    """원문 + 공시일 → (결의일 'YYYYMMDD', None) 또는 (None, 이유). (순수 함수)"""
    bd, why = parse_issue_bd(text)
    if bd is None:
        return None, why
    why = issue_bd_range_why(bd, d)
    return (None, why) if why else (bd, None)


def issue_doc_main(files, rc):
    """document.xml zip 의 파일들 → (본 파일 글자, None) 또는 (None, ("fail" | "nf", 이유)). (순수 함수 · 리뷰 2026-11-19)
    본 파일은 '{접수번호}.xml' (dvwhy_doc_text 와 같은 이름 규칙) — 없으면 가장 큰 파일(첨부일 수 있어요 · 다른 날을 읽을 수 있어요)을 읽지 않고
    nf (원문은 바뀌지 않아서 다시 받아도 같아요). 빈 zip · 비었거나 글자로 바꾸지 못한(utf-8 · cp949 · euc-kr) 본 파일은 받기 실패 fail
    (적지 않고 다음 실행이 다시 받아요)."""
    if not files:
        return None, ("fail", "받은 zip 이 비었어요")
    main = [n for n in files if n.rsplit("/", 1)[-1].split(".")[0] == rc]
    if not main:
        return None, ("nf", f"zip 에 본 파일({rc}.xml)이 없어요 (다른 파일 {len(files)}개는 읽지 않아요)")
    text = dvwhy_doc_text({main[0]: files[main[0]]}, rc)
    if text is None or not text.strip():
        return None, ("fail", "본 파일이 비었거나 글자로 바꾸지 못했어요 (utf-8 · cp949 · euc-kr)")
    return text, None


def issue_bd_targets(rows):
    """결의일을 볼 issue 줄: 유상증자(유무상증자 포함) · 철회(wd)도 읽는 중(pend)도 아닌 줄. (순수 함수 — 관문 validate_data 와 같은 기준)
    유무상증자(bonus)는 상세 API 의 결의일(fric_bddd)이 있으면 원문을 읽지 않아요 (fill_issue_bd)."""
    return [r for r in rows or [] if isinstance(r, dict) and r.get("kind") == "rights" and r.get("wd") is not True
            and r.get("pend") is not True and isinstance(r.get("rc"), str) and isinstance(r.get("d"), str)]


def fill_issue_bd(disc, client, end):
    """v19.6b Q18: disc['issue'] 의 유상증자 줄에 bd (원문의 이사회결의일)를 채워요 (줄을 고쳐요) → 센 것 dict. 실행을 멈추지 않아요.
    issueOk 가 참이 아니면(목록을 받지 못한 날) 아무것도 하지 않아요 (지난 발행본의 줄 그대로)."""
    rows = disc.get("issue") if isinstance(disc, dict) else None
    if not isinstance(rows, list) or disc.get("issueOk") is not True:
        log("  !! 유상증자 이사회 결의일: 오늘 주요사항 공시 목록을 받지 못해 원문을 읽지 않아요 (지난 발행본의 줄과 결의일 그대로)")
        return {"skip": True}
    bgn = (end - dt.timedelta(days=DISC_DAYS - 1)).strftime("%Y%m%d")       # fetch_issues 와 같은 기간
    today_iso = client.today.isoformat()
    key = lambda rc: f"{rc}|{ISSUE_BD_TAG}"                                    # noqa: E731
    targets = issue_bd_targets(rows)
    due, nf, lim, cached, api, api_rc = [], [], [], 0, 0, set()

    def use(r, bd8):
        """원문이 적은 결의일을 그 줄에 써요 — 공시일보다 1년 넘게 앞이 아닐 때만 (아니면 bd 는 비우고 '기간 밖이라 비움'). 공시일 뒤인 날은
        여기서 쓰고, 쓰기 바로 앞의 own_check_disc 가 관문과 같은 함수로 비우고 ownDrop.issueBd 에 세요 (Jack 의 상시 규칙 2026-11-19)."""
        why = issue_bd_window_why(bd8, r["d"])
        if why is None:
            r["bd"] = bd8
        else:
            lim.append((r, why))

    with client.lock:
        for r in targets:
            e = client.entries.get(key(r["rc"])) or {}
            given = r.get("bd") if r.get("bonus") is True else None     # 유무상증자: pifricDecsn 의 결의일 (같은 기간 확인)
            r["bd"] = None
            if _ymd_date(given) is not None:
                use(r, given)
                api += 1
                api_rc.add(r["rc"])
            elif e.get("st") == "000" and _ymd_date(e.get("d")) is not None:
                use(r, e["d"])
                cached += 1
            elif e.get("st") == "nf":
                nf.append((r, str(e.get("why") or "?")))
                cached += 1
            else:
                due.append(r)
    due.sort(key=lambda r: (r["d"], r["rc"]), reverse=True)
    todo, later = due[:ISSUE_BD_PER_RUN], due[ISSUE_BD_PER_RUN:]
    calls0, t0 = sum(client.status.values()), time.time()

    def one(r):
        if client.fatal or client.down:
            return r, "stop", None
        if time.time() - t0 > ISSUE_BD_SECONDS:
            return r, "time", None
        try:
            files = client.get_zip("document.xml", {"rcept_no": r["rc"]}, timeout=ISSUE_BD_TIMEOUT)
        except Exception as e:             # get_zip 은 예외를 내지 않지만, 하나가 실행을 멈추지 않게 (센 수로 남겨요)
            return r, "fail", type(e).__name__
        if files is None:
            return r, ("stop" if (client.fatal or client.down) else "fail"), "응답 없음 · 오류 상태"
        try:
            text, bad = issue_doc_main(files, r["rc"])
            if bad:
                return (r,) + bad
            bd, why = parse_issue_bd(text)
        except Exception as e:             # 이상한 원문 하나가 실행을 멈추지 않게 — 적지 않고 다음 실행이 다시 읽어요 (센 수로 남겨요)
            return r, "err", type(e).__name__
        return r, ("000" if bd else "nf"), (bd or why)

    n, errs, fails = collections.Counter(), [], []
    if todo:
        with ThreadPoolExecutor(max_workers=ISSUE_BD_WORKERS) as ex:
            res = list(ex.map(one, todo))
        with client.lock:
            for r, st, v in res:
                n[st] += 1
                if st == "000":
                    client.entries[key(r["rc"])] = {"st": "000", "at": today_iso, "d": v}
                    use(r, v)
                elif st == "nf":
                    client.entries[key(r["rc"])] = {"st": "nf", "at": today_iso, "d": None, "why": v}
                    nf.append((r, v))
                elif st == "err":
                    errs.append(f"{r['nk']} {r['d']} ({v})")
                elif st == "fail":
                    fails.append(f"{r['nk']} {r['d']} {r['rc']} ({v})")
    keep = {key(r["rc"]) for r in targets}
    with client.lock:                       # 오늘 줄이 아닌 키 중 기간을 벗어난 공시(접수번호 앞 8자리 < 기간 시작)의 것 · 다른 판의 키는 지워요
        old = [k for k in client.entries if "|issuebd|" in k and k not in keep and (not k.endswith("|" + ISSUE_BD_TAG) or k[:8] < bgn)]
        for k in old:
            del client.entries[k]

    a = sum(1 for r in targets if r.get("bd"))
    a_api = sum(1 for r in targets if r.get("bd") and r.get("bonus") is True and r["rc"] in api_rc)
    later_n = len(later) + n["time"] + n["stop"] + n["fail"] + n["err"]
    out = {"target": len(targets), "read": a, "unread": len(nf), "limited": len(lim), "later": later_n, "fetched": n["000"] + n["nf"],
           "cached": cached, "api": api, "cap": len(later), "time": n["time"], "stop": n["stop"], "fail": n["fail"], "err": n["err"],
           "calls": sum(client.status.values()) - calls0, "dropped": len(old)}
    log(f"{'  !! ' if (nf or lim or later_n) else '· '}유상증자 이사회 결의일(공시 원문 document.xml): 문서에서 읽음 {a - a_api:,}"
        + (f" · 유무상증자 상세 API {a_api:,}" if api else "") + f" / 대상 {len(targets):,}, "
        f"못 읽음 {len(nf):,}, 기간 밖이라 비움 {len(lim):,}, 다음 실행으로 {later_n:,} — 오늘 원문 조회 {out['calls']:,}회 (새로 읽음 "
        f"{n['000']:,} · 못 읽음 {n['nf']:,}) · 캐시로 끝 {cached:,} · 실행당 {ISSUE_BD_PER_RUN}건 · {ISSUE_BD_SECONDS}초까지"
        + (f" · 유무상증자는 상세 API 의 결의일(fric_bddd)을 같은 기간 확인으로 써요 {api:,}" if api else "")
        + (f" · 실행당 한도에 닿아 {len(later):,}" if later else "")
        + (f" · 시간 한도에 닿아 {n['time']:,}" if n["time"] else "")
        + (f" · 조회 실패 {n['fail']:,} ({', '.join(fails[:5])})" if n["fail"] else "")
        + (f" · 해석 오류 {n['err']:,} ({', '.join(errs[:5])})" if n["err"] else "")
        + (f" · DART 가 멈춰 {n['stop']:,} ({'상태 ' + client.fatal[0] if client.fatal else '연결 안 됨'})" if n["stop"] else "")
        + (f" · 지운 캐시 {len(old):,}" if old else "")
        + " (대상: 철회 · 읽는 중이 아닌 유상증자 줄 · 사채의 결의일은 상세 API 의 것)")
    if nf:
        log(f"  !! 결의일을 못 읽은 유상증자 공시 {len(nf):,}건 (bd 빈 칸 · 같은 공시는 다시 읽지 않아요): "
            + ", ".join(f"{r['nk']} {r['d']} {r['rc']} ({why})" for r, why in nf[:20]) + (" …" if len(nf) > 20 else ""))
    if lim:
        log(f"  !! 결의일이 공시일보다 {ISSUE_BD_MAX_YEARS}년 넘게 앞이라 비운 유상증자 공시 {len(lim):,}건 (bd 빈 칸 · Jack 7d · 원문의 날은 캐시에 "
            "있어요 — 한도를 바꾸면 다시 받지 않고 다음 실행이 써요 · 공시일 뒤인 날은 쓰기 앞의 own_check_disc 가 따로 비우고 세요 · 이 수는 "
            "관문의 N 에 들지 않아요 — 관문은 빈 결의일로 경고만): "
            + ", ".join(f"{r['nk']} {r['d']} {r['rc']} ({why})" for r, why in lim[:20]) + (" …" if len(lim) > 20 else ""))
    return out


# ────────────────────────────────────────────────────────────
# Jack 의 상시 규칙 (2026-11-19 ~17:45 KST, 그대로): "Standing rule for checks on our own processing: a single bad row is dropped or
# blanked with a loud warning and the rest publishes. Block only when many rows fail in one run (set the number from recent runs and show
# it in the PR) or when a value would show a wrong number." — #145 의 네 검사. 나쁜 행은 관문 파일의 함수가 골라요 (같은 함수 · 한 곳).
# 여기서는 쓰기 바로 앞에서 빼거나 비우고, 크게 남기고, 그 파일의 ownDrop[열쇠] = {"n", "rows" 앞 30} 에 적어요 (깨끗한 실행도 0).
# 관문은 n 이 N 을 넘거나 틀린 숫자를 보일 값이 남으면 실패, 1~N 이면 경고예요. 공시 줄(disc.json)만 빼요 — 종목 행은 빼지 않아요 (미국
# 일정은 그 칸만 비워요 · 배당 증명 목록(v19.1i)의 종목은 그대로).
# ────────────────────────────────────────────────────────────
OWN_ISSUE_SHAPE_NAME = "주요사항 공시 줄 모양 (issue)"
OWN_ISSUE_BD_NAME = "유상증자 이사회 결의일이 공시일 뒤 (issue bd)"
OWN_INSIDER_ROLE_NAME = "임원 · 주요주주 역할 (insider role)"
OWN_US_DATE_NAME = "미국 일정 (ed 실적 발표일 · xd 배당락일)"


def _own_log(name, rows, mx, verb, where):
    """검사 한 줄의 로그: 있으면 '!! 이름: n건 빼고 발행 — 이름 (이유) …', 없으면 '· 이름: 0건'."""
    if rows:
        gate = f"{mx}건을 넘어 관문에서 실패해 발행하지 않아요" if len(rows) > mx else f"관문 경고 · {mx}건을 넘으면 실패"
        log(f"  !! {name}: {len(rows):,}건 {verb} — {own_rows_text(rows)} ({where} · {gate})")
    else:
        log(f"· {name}: 0건 {verb}")


def own_check_disc(disc, today):
    """disc.json 을 쓰기 바로 앞: 관문과 같은 함수로 나쁜 공시 줄을 빼거나 값을 비우고 disc["ownDrop"] 에 적어요 (줄을 고쳐요) → disc.
    issueShape 모양이 틀린 issue 줄 · 같은 접수번호가 여러 번 나온 줄 → 줄째 빼요 (그 결정의 숫자를 믿을 수 없어요 — 카드가 없는 것이 틀린 숫자보다
    나아요) · issueBd 공시일 뒤의 유상증자 결의일 → bd 만 비워요 (줄의 다른 칸은 상세 API 로 읽은 것 · 결의일만 우리가 잘못 읽었어요) ·
    insiderRole 객체가 아닌 insider 줄 → 빼요 · 허용하지 않은 role → role 만 비워요 (거래 숫자는 맞아요 · role 은 제목의 글자).
    Jack 의 규칙은 한 줄에 대한 것이에요 — 칸 전체를 바꾸지 않아요 (리뷰 2차 2026-11-19): insider 가 목록이 아니면 그대로 두고 크게 남겨요
    (관문 '임원 · 주요주주 역할' 이 실패해 발행하지 않아요 — 빈 목록으로 바꾸면 공시 탭이 '보고 없음'을 지금 데이터처럼 보여요) · issue 가
    목록이 아니면 빈 목록과 issueOk false 로 써요 (목록을 받지 못한 날과 같아요 — 앱은 실패 줄 · 관문 경고 · 아직 어느 화면도 issue 를 읽지 않아요)."""
    base = gate_iso_day(disc.get("asOf")) or today
    own = disc.get("ownDrop") if isinstance(disc.get("ownDrop"), dict) else {}
    if not isinstance(disc.get("issue"), list):
        log(f"  !! 주요사항 공시(issue)가 목록이 아님 ({type(disc.get('issue')).__name__}) — 우리 처리의 잘못이에요: 빈 목록과 issueOk false 로 "
            "써요 (목록을 받지 못한 날과 같아요 · 앱은 실패 줄 · 관문 경고)")
        disc["issue"], disc["issueOk"] = [], False
    bad = issue_bad_rows(disc["issue"], base)
    drop = {b[0] for b in bad}
    disc["issue"] = [r for i, r in enumerate(disc["issue"]) if i not in drop]
    own[ISSUE_SHAPE_KEY] = own_rows_rec(bad)
    _own_log(OWN_ISSUE_SHAPE_NAME, bad, ISSUE_SHAPE_MAX, "빼고 발행", f"disc.json ownDrop.{ISSUE_SHAPE_KEY}")
    bad = issue_bd_bad_rows(disc["issue"])
    for b in bad:
        disc["issue"][b[0]]["bd"] = None
    own[ISSUE_BD_KEY] = own_rows_rec(bad)
    _own_log(OWN_ISSUE_BD_NAME, bad, ISSUE_BD_MAX, "비움 (bd)", f"disc.json ownDrop.{ISSUE_BD_KEY}")
    if isinstance(disc.get("insider"), list):
        bad = insider_bad_rows(disc["insider"])
        drop = {b[0] for b in bad if b[4] is None}
        for b in bad:
            if b[4] is not None:
                disc["insider"][b[0]][b[4]] = None
        disc["insider"] = [r for i, r in enumerate(disc["insider"]) if i not in drop]
    else:
        bad = []
        log(f"  !! 내부자 거래(insider)가 목록이 아님 ({type(disc.get('insider')).__name__}) — 그대로 둬요: 관문 '임원 · 주요주주 역할' 이 실패해 "
            "발행하지 않아요 (빈 목록으로 바꾸면 공시 탭이 '보고 없음'을 지금 데이터처럼 보여요)")
    own[INSIDER_ROLE_KEY] = own_rows_rec(bad)
    _own_log(OWN_INSIDER_ROLE_NAME, bad, INSIDER_ROLE_MAX, "빼거나 비움", f"disc.json ownDrop.{INSIDER_ROLE_KEY}")
    disc["ownDrop"] = own
    return disc


def own_us_dates(payload):
    """data.json 을 쓰기 바로 앞: 관문과 같은 함수(us_date_bad_rows)로 틀린 미국 ed · xd 를 비우고 payload["ownDrop"]["usDates"] 에 적어요.
    종목 행은 그대로 두고 그 칸만 지워요 (가격 · 배당 숫자는 맞아요 — 행을 빼면 배당 증명 목록(v19.1i) 같은 다른 검사가 깨져요). ownDrop 은
    setdefault 로 더해요 (claude/own-check-rule 의 usClass · divLine 과 한 칸에 같이 들어가요)."""
    stocks = payload.get("stocks") if isinstance(payload.get("stocks"), list) else []
    bad = us_date_bad_rows(stocks)
    for b in bad:
        stocks[b[0]].pop(b[4], None)
    own = payload.get("ownDrop") if isinstance(payload.get("ownDrop"), dict) else {}
    own[US_DATE_KEY] = own_rows_rec(bad)
    payload["ownDrop"] = own
    _own_log(OWN_US_DATE_NAME, bad, US_DATE_MAX, "비움", f"data.json ownDrop.{US_DATE_KEY}")
    return payload


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
# v19.1f (Jack 승인 2026-11-08): EV(기업가치)와 P/영업현금흐름의 시가총액 = 보통주 + 같은 회사 상장 우선주 (회사 전체의 값). False 면
# v19.1f 전처럼 보통주만 (우선주가 있는 회사의 EV 가 작아 보여요 — 삼성전자 약 11%).
COMPANY_CAP_WITH_PREF = True
# v19.1f (리뷰 2026-11-08 · Jack 승인 2026-11-08): EV 에 비지배지분을 더해요 (EBITDA·매출이 연결 100% 라서 — 한화에어로스페이스 약 7.1조).
# False 면 v19.1f 전처럼 시가총액 + 차입금 − 현금만.
EV_WITH_NCI = True
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


CORP_DIV_KEYS = ("dps3a", "dpsF", "divSt", "dyt", "dz", "betaSE", "betaN", "dvWhy")   # v19.1b: data.json 종목에서 그대로 옮기는 칸 (v19.1h dvWhy)


def icr_inputs(fin):
    """이자보상배율 입력 → (영업이익, 이자, 출처 is·cf, 기간 ttm·fy, 못 돌린 이유). 영업이익과 이자는 같은 기간끼리만 써요 (v19.1f 리뷰:
    TTM 영업이익을 연간 이자로 나누지 않게): TTM 영업이익 + TTM 이자, 안 되면 연간 영업이익 + 연간 이자. 이자는 손익계산서
    이자비용(is), 없거나 음수면 현금흐름표 이자 지급액(cf). 이유: op 그 기간의 영업이익 없음 · ie 이자 줄 없음 · neg 이자가 음수뿐. (순수 함수)
    v19.1f (Jack 2026-11-08): 낸 이자가 있을 때만 경고할 수 있어요 — 이자비용이 0 보다 크면 is, 아니면 이자 지급액이 0 보다 크면 cf
    (이자비용 줄이 0 이어도 현금흐름표에 낸 이자가 있으면 그걸로). 둘 다 0 이면 이자 0 (그 줄의 출처 · is 먼저) — build_corp 는 돌렸지만
    경고하지 않고 flSrc.int0 = true 를 남겨요 (영업손실이어도: 낼 이자가 없어요)."""
    _t = fin.get("ttm") or {}
    sets = (("ttm", _t.get("op"), _t.get("ie"), _t.get("iec")),
            ("fy", (fin.get("op") or [None])[0], fin.get("ie"), fin.get("iec")))
    neg = has_int = any_op = False
    for per, op, ie, iec in sets:
        op, ie, iec = _fin(op), _fin(ie), _fin(iec)
        has_int = has_int or ie is not None or iec is not None
        if op is None:
            continue
        any_op = True
        if ie is not None and ie > 0:
            return op, ie, "is", per, None
        if iec is not None and iec > 0:
            return op, iec, "cf", per, None
        if ie == 0 or iec == 0:
            return op, 0.0, ("is" if ie == 0 else "cf"), per, None
        neg = neg or ie is not None or iec is not None
    # 영업이익이 어느 기간에도 없으면 op (이자 줄 탓이 아니에요) · 음수 이자뿐이면 neg · 이자가 영업이익 없는 기간에만 있으면 op · 아니면 ie
    return None, None, None, None, ("op" if not any_op else "neg" if neg else "op" if has_int else "ie")


def corp_sector_stats(comps):
    """기업분석 업종 통계 (corp.json sectors · 예전 뱁새가 업종 중간값 · 사분위 · 성장률 순위에 써요). (순수 함수)
    2026-11-19 (#146 · Jack 답 2): 우선주는 보통주의 업종 키를 따르지만 업종 수 · 중간값 · 사분위 · 성장률에서는 빼요 (같은 회사가 두 번
    들어가지 않게) — 업종 시가총액(mc)에만 넣어요 (실제 시장 가치). 우선주만 있는 업종도 키는 남겨요 (앱이 sectors[c.s] 를 찾아요)."""
    sectors, by_sec = {}, {}
    for c in comps:
        by_sec.setdefault(c["s"], [])
        if not is_preferred(c["t"]):
            by_sec[c["s"]].append(c)
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
            "mc": round(sum(c["cap"] for c in comps if c["s"] == sec and c["cap"]), 1),          # 조원 (우선주 포함)
        }
    return sectors


def build_corp(kr_stocks, fin_map, as_of, market=None, extra=None, pref_caps=None, pref_missing=None):
    """기업분석 탭이 쓰는 corp.json 을 만듭니다. (순수 함수 — 테스트 가능)
    v19.1b: extra = apply_div_basis 의 {코드: 칸} (현금배당금총액 cash3 · 회사가 낸 주당순이익 eps3r · 같은 기준 순이익 epsNi3 · epsB).
    flRan = 실제로 돌린 재무 경고 검사(입력이 다 있었던 것), flNa = 금융업이라 해당 없는 검사. 앱은 네 검사(cr 유동비율 ·
    icr 이자보상배율 · l3 3년 연속 적자 · imp 자본잠식)가 모두 flRan 이나 flNa 에 있을 때만 '재무 경고 신호는 없어요'라고 말할 수 있어요.
    v19.1f: pref_caps = kr_pref_caps (목록 파일 전체의 우선주 시가총액, 조원) — 없으면 kr_stocks 안의 우선주로.
    2026-11-19: pref_missing = 상장 우선주의 공식 종가를 두 출처로 확인하지 못한 회사 (코드 앞 5자리) — 회사 시가총액을 알 수 없어 EV · P/CF 를
    비우고 evNo "prefPx" 를 달아요 (COMPANY_CAP_WITH_PREF 일 때)."""
    extra = extra or {}
    pref_missing = set(pref_missing or ())
    ev_blank = []                                   # 2026-11-19: 우선주 종가를 확인하지 못해 EV · P/CF 를 비운 회사
    comps = []
    hold_log, hold_unknown, hold_bad = [], [], []   # v19.1d: 금융 아닌 지주 (코드, 이름, 유동비율, 이자보상배율) · 그룹 없는 지주 · 금융 지주인데 금융이 아님
    why_n = collections.Counter()                   # v19.1d: 이자보상배율을 못 돌린 이유별 기업 수 (flWhy)
    zero_n = collections.Counter()                  # v19.1f (Jack 2026-11-08): 돌렸지만 낸 이자가 0 인 곳 (flSrc.int0) · 영업손실 · 영업이익
    src_n = collections.Counter()                   # v19.1f: 이자보상배율에 쓴 이자 (is 손익계산서 이자비용 · cf 현금흐름표 이자 지급액) · 기간
    nci_miss = []                                   # v19.1f: 연결인데 지배주주 자본이 없어 EV 에 비지배지분을 못 더한 회사
    # v19.1f: 같은 회사 상장 우선주의 시가총액 (COMPANY_CAP_WITH_PREF 면 EV·P/CF 의 회사 시가총액에 더해요). EPS·BPS 주식 수와 같은
    # 목록(파일 전체)을 써요
    if pref_caps is not None:
        pref_cap = collections.Counter(pref_caps)
    else:
        pref_cap = collections.Counter()
        for s in kr_stocks:
            if s.get("cls") == "kr" and is_preferred(s.get("t") or "") and (_fin(s.get("cap")) or 0) > 0:
                pref_cap[s["t"][:5]] += s["cap"]
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
        if s.get("pxd") is not None:
            row["pxd"] = s["pxd"]                          # 2026-11-19 (Jack): 마지막 확인 종가의 날짜 (예전 뱁새 기업분석이 그 날짜와 Jack 의 줄을 보여요)
        if fin.get("bq"):
            row["bq"] = fin["bq"]
        if fin.get("unitFix") and not s.get("unitChk"):
            row["unitFix"] = fin["unitFix"]                # (2026-11-13) 단위를 잘못 적어 나눠 쓴 분기 보고서 [{rep, bs · is · cf: k}]
        if fin.get("nio3"):
            row["nio3"] = fin["nio3"]                      # v19.1f: 지배주주 순이익 3년 (연결 · 억원). ni 는 전체 순이익 그대로
        if fin and fl_financial(s) and rev[0] is None:
            row["incNa"] = ["rev"]                         # v19.1f: 금융회사 재무제표엔 매출 줄이 없어요 (지어내지 않음 · 앱이 이유를 말할 수 있게)

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
        # v19.1f: 이자 = 손익계산서 이자비용(is), 없거나 음수면 현금흐름표 이자 지급액(cf) · 영업이익과 같은 기간 (icr_inputs).
        # 어느 이자를 썼는지 flSrc 에 남겨요
        op0f, ie_v, ie_src, ie_per, icr_why = icr_inputs(fin)
        icr_ok = op0f is not None and ie_v is not None and not fin_co and not unknown
        if icr_ok and not ICR_OFF:
            ran.append("icr")                                # 이자비용 0 도 돌린 거예요 (갚을 이자가 없으면 경고가 날 수 없어요)
            row["flSrc"] = {"icr": ie_src}
            src_n[ie_src] += 1
            src_n[ie_per] += 1
            src_n["fyBack"] += ie_per == "fy" and _fin((fin.get("ttm") or {}).get("op")) is not None   # TTM 이자가 없어 연간끼리
        if icr_ok and not ICR_OFF and ie_v == 0:
            # v19.1f (Jack 2026-11-08): 낸 이자가 없으면 경고하지 않아요 (영업손실이어도) — 이유를 flSrc.int0 로 남겨 앱이 알 수 있게.
            # icr 는 flRan 에 있어요 (돌렸어요 · flWhy 는 '못 돌린 이유'만이라 쓰지 않아요). flSrc.icr 는 0 이었던 줄 (is · cf)
            row["flSrc"]["int0"] = True
            zero_n["loss" if op0f < 0 else "profit"] += 1
        if icr_ok and not ICR_OFF and ie_v > 0:
            icr = op0f / ie_v
            if icr < 1:
                # v19.1f (코디네이터 2026-11-08): 1 미만이라 경고한 값은 '1.0'으로 보이면 안 돼요 (대창솔루션 0.995 → 예전 1.0).
                # 소수 한 자리로 내림 (0.99 → 0.9 · −0.41 → −0.5)
                fl["icr"] = math.floor(icr * 10 + 1e-9) / 10
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
            # v19.1d (Jack, 2026-11-07): 이자보상배율을 못 돌린 이유. 앱은 'ie'(v19.1f: 손익계산서 이자비용도, 현금흐름표 이자 지급액도 없음)일 때만
            # '재무제표에서 이자 비용을 찾지 못해 확인하지 못했어요'라고 말해요. op = 영업이익이 없음 · neg = 이자비용이 음수 ·
            # off = 잠시 꺼 둠 (ICR_OFF — 앱은 아무 말도 하지 않아요). 꺼진 동안은 이자 줄이 없는 회사도 off: 어떤 회사엔 '확인한 …
            # 없어요' 카드가, 같은 결과의 다른 회사엔 아무것도 없는 차이가 생기지 않게 (리뷰 2026-11-07)
            row["flWhy"] = {"icr": "off" if ICR_OFF else (icr_why or "op")}
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
        pref_gap = COMPANY_CAP_WITH_PREF and not is_preferred(s["t"]) and s["t"][:5] in pref_missing
        # 2026-11-19 (Jack): 마지막 확인 종가(pxd)로 실은 보통주에 오늘 종가의 상장 우선주가 있으면 회사 시가총액이 두 날짜를 섞어요 → 같은 자리에서 비워요
        own_gap = (COMPANY_CAP_WITH_PREF and not is_preferred(s["t"]) and s.get("pxd") is not None and not pref_gap
                   and (pref_cap[s["t"][:5]] or 0) > 0)
        if (pref_gap or own_gap) and s.get("cap") and fin:
            row["evNo"] = "ownPx" if own_gap else "prefPx"   # 회사 시가총액에 더할 우선주 종가를 두 출처로 확인하지 못했어요 (2차 출처 날) · ownPx: 날짜가 달라요
            ev_blank.append(f"{s['t']} {s.get('nk', '')}" + (" (마지막 확인 종가라 오늘 우선주 종가와 날짜가 달라요 · ownPx)" if own_gap else ""))
        pref_gap = pref_gap or own_gap
        if s.get("cap") and fin and not pref_gap:
            co_cap = s["cap"] + (pref_cap[s["t"][:5]] if COMPANY_CAP_WITH_PREF and not is_preferred(s["t"]) else 0.0)   # 조원
            # v19.1f (리뷰 2026-11-08): EBITDA·매출은 연결 100% 라 EV 에 비지배지분(자본총계 − 지배주주 자본)도 더해요. 같은 시점의
            # 두 값이 다 있을 때만 (최신 분기 → 연간). 별도 재무제표는 비지배지분이 없어요. 연결인데 지배주주 자본이 없으면 0 으로 두고 로그
            nci = 0.0
            if fin.get("fs") != "OFS":
                pair = next(((_fin(src.get("eq")), _fin(src.get("eqo"))) for src in (_b, fin)
                             if _fin(src.get("eq")) is not None and _fin(src.get("eqo")) is not None), None)
                bs_nci = next((_fin(src.get("nciBs")) for src in (_b, fin) if "nciBs" in src), "unknown")
                if pair:
                    nci = pair[0] - pair[1]
                elif bs_nci != "unknown":
                    nci = bs_nci or 0.0          # 재무상태표의 비지배지분 줄 (없으면 0 — 비지배지분이 없는 연결)
                elif _fin(eff["eq"]) is not None and row["s"] not in FIN_SECS:
                    nci_miss.append(f"{s['t']} {s['nk']}")
            ev = co_cap * 1e4 + (_fin(eff["bor"]) or 0.0) - (_fin(eff["cash"]) or 0.0) + (nci if EV_WITH_NCI else 0.0)
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
                v = co_cap * 1e4 / ocf
                if 0 < v < 200:
                    row["pcf"] = round(v, 1)
        # DCF 자동 채움 가능 여부: 당기 순이익 존재 + 시총(→주식수 역산) 존재
        row["dcfReady"] = bool(ni[0] is not None and (s.get("shr") or s.get("cap")))
        if s.get("pxBad"):
            # 2026-11-14 (Jack, Q2 (a)): 과거 주가 기록 오류 (mark_px_bad) — 위에서 옮겨 실은 시계열 칸 중 비운 칸(pxBadF)은 이미 빈 칸이에요. 표시와
            # 비운 칸 목록을 그대로 달아요 (예전 뱁새 기업분석이 corp.json 만 읽어요 · 관문이 두 파일이 같은지 봐요)
            row["pxBad"] = s["pxBad"]
            row["pxBadF"] = list(s.get("pxBadF") or [])
        if s.get("unitChk"):
            # (2026-11-13) 공시 단위 확인에 걸린 회사 (unit_guard): 재무제표로 만든 금액·배수·영수증·재무 경고를 모두 비워요. 배당(별도 배당 표)은 남겨요
            row.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False,
                       vz=None, qz=None, **{k: None for k in UNIT_BLANK})
            for k in UNIT_BLANK_CORP:
                row.pop(k, None)
            row["flRan"] = []                        # 돌린 검사 없음 (앱은 '경고 신호는 없어요'라고 말하지 않아요)
            row["unitChk"] = list(s["unitChk"])
        if not_won(s, fin):
            # v17.5.2: 해외 기업 금액은 원화가 아닐 수 있어 비워요 (blank_foreign_dart 참고). 위에서 만든 fl 신호는 비율·부호라 남겨요.
            # v19.1f (리뷰 2026-11-08): 재무제표 통화가 원화가 아닌 국내 회사도 같게 (두산밥캣 USD) · stmtCur 에 통화를 남겨요 (관문이 봐요)
            row.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False,
                       **{k: None for k in FOREIGN_BLANK})                                  # blank_* 가 이미 비웠어도 한 번 더
            for k in ("evE", "evR", "pcf", "bq", "cash3", "eps3r", "epsNi3", "epsB", "nio3", "epsIn", "bpsIn",
                      "roeIn", "epsFy", "epsRep"):                                          # v19.1f: 지배주주 순이익·영수증도
                row.pop(k, None)
            if stmt_cur_of(fin):
                row["stmtCur"] = stmt_cur_of(fin)
                # v19.1f (리뷰 3): 다른 통화의 재무 신호는 0.1억으로 반올림한 값이라 믿을 수 없어요 (아남전자 이자 지급 1,068,247 달러 →
                # 0.0 · 순이익 414만 달러 → 0.0). 신호를 계산하지 않은 것으로 둬요 — 앱은 아무 말도 하지 않아요
                for k in ("fl", "flRan", "flSrc", "flWhy"):
                    row.pop(k, None)
                row["flRan"] = []                    # (2026-11-09) 돌린 검사 없음 — 관문의 '재무 경고 검사 기록' 줄은 목록을 바라요
                row.update(roe=None, qz=None)        # 리뷰 4: ROE 와 그 점수도 보여 주지 않아요 (blank_non_won 이 data.json 쪽을 비워요)
        comps.append(row)

    sectors = corp_sector_stats(comps)
    log(f"· 이자보상배율에 쓴 이자: 손익계산서 이자비용 {src_n['is']:,}곳 · 현금흐름표 이자 지급액 {src_n['cf']:,}곳 (기간: TTM "
        f"{src_n['ttm']:,} · 연간 {src_n['fy']:,}, 그중 TTM 이자가 없어 연간 영업이익·이자끼리 {src_n['fyBack']:,}) · 경고 "
        f"{sum(1 for c in comps if 'icr' in (c.get('fl') or {})):,}곳 (그중 영업손실 "
        f"{sum(1 for c in comps if (c.get('fl') or {}).get('icr', 1) < 0):,})")
    if ev_blank:
        log(f"  !! 상장 우선주의 종가를 두 출처로 확인하지 못했거나 (prefPx) 보통주를 마지막 확인 종가로 실어 (ownPx) 회사 시가총액을 알 수 없는 회사 "
            f"{len(ev_blank)}곳 — EV · P/CF 를 비웠어요: "
            + ", ".join(ev_blank[:15]) + (" …" if len(ev_blank) > 15 else ""))
    n_pc = sum(1 for c in comps if not is_preferred(c["t"]) and pref_cap.get(c["t"][:5]))
    log(f"· EV 회사 시가총액: 상장 우선주를 더한 회사 {n_pc:,}곳 ({'켬' if COMPANY_CAP_WITH_PREF else '끔'} · COMPANY_CAP_WITH_PREF · "
        f"우선주 목록 {'파일 전체' if pref_caps is not None else 'data.json 안'}) · 비지배지분 더하기 {'켬' if EV_WITH_NCI else '끔'}"
        + (f" — 연결인데 지배주주 자본이 없어 비지배지분을 0 으로 둔 곳 {len(nci_miss):,}: {', '.join(nci_miss[:12])}"
           f"{'…' if len(nci_miss) > 12 else ''}" if nci_miss else ""))
    log(f"{'  !! ' if ICR_OFF else '· '}이자보상배율을 못 돌린 기업 (금융 빼고): {sum(why_n.values()):,}곳 — "
        + (f"잠시 꺼 둠(ICR_OFF · 금융비용으로 계산되던 값이라) {why_n['off']:,} · " if ICR_OFF else "")
        + f"이자비용도 이자 지급액도 없음 {why_n['ie']:,} · 영업이익 없음 {why_n['op']:,} · 이자 음수 {why_n['neg']:,} (corp.json flWhy)")
    log(f"· 이자보상배율: 돌렸지만 낸 이자가 0 이라 경고하지 않은 곳 {sum(zero_n.values()):,} (영업손실 {zero_n['loss']:,} · 영업이익 "
        f"{zero_n['profit']:,} · corp.json flSrc.int0 — 이자비용·이자 지급액이 0 보다 클 때만 경고해요)")
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


def naver_clean(px):
    """네이버 일봉을 날짜마다 한 봉 · 날짜 순 · 0 보다 큰 유한한 값만으로 (2026-11-14 · 리뷰 S2 · 순수 함수). 반환: (시계열, 문제 [(날짜, 이유, 값들)]).
    같은 날짜가 같은 값으로 두 번이면 하나만 남기고 문제로 세지 않아요. 다른 값으로 두 번 이상이면 그 날짜를 통째로 빼요 ('dup' — 어느 값이
    맞는지 알 수 없어 둘 다 믿지 않아요. 한 봉만 빠지면 숫자는 거의 같고, 종목을 빼면 필수 종목일 때 모두의 발행이 막혀요). 0 이하이거나 무한대인
    값도 빼요 ('bad'). 2026-11-13 의 2,474종목 · 약 187만 봉에는 셋 다 0 이었어요. 이렇게 해서 자기 점검(pin_audit)과 움직임 검사(kr_jumps)는
    늘 날짜가 하나뿐인 시계열만 봐요 — 출처의 잘못이 관문 실패(우리 코드의 잘못)로 보이지 않게."""
    probs = []
    if px is None or not len(px):
        return px, probs
    vals = pd.to_numeric(px, errors="coerce").astype(float)
    good = vals.notna() & np.isfinite(vals.values) & (vals > 0)
    for ts, v in vals[~good].items():
        probs.append((ts, "bad", [float(v)] if pd.notna(v) else []))
    vals = vals[good]
    if vals.index.has_duplicates:
        g = vals.groupby(level=0)
        nuniq = g.nunique()
        for ts in nuniq[nuniq > 1].index:
            probs.append((ts, "dup", [float(x) for x in vals.loc[[ts]].values]))
        vals = g.first()[nuniq == 1]
    return vals.sort_index(), sorted(probs, key=lambda p: p[0])


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
    # 2026-11-19 (Jack 규칙 3): 1차 출처(캐시 최종본) 뒤에 이미 끝난 거래일이 있으면 2차 출처 (다음 × 야후 · 두 종가가 원 단위까지 같은 종목만)
    # 2026-11-20: FinanceDataReader 는 KOSPI 일봉 캐시 CSV 를 시간 한도 없이 받아요 (pandas read_csv · urllib) — 소켓 시간 한도를 걸고, 받은 것을 바로 남겨요
    # (그 라이브러리는 받지 못한 해를 조용히 건너뛰어요 → 마지막 날이 1차 출처 기준일보다 앞이면 크게 남겨요 · 관문도 KOSPI 일봉을 따로 확인해요)
    t0 = time.time()
    ks_all = with_socket_timeout(lambda: fdr.DataReader(KR_INDEX, start, today), KR_INDEX_TIMEOUT)["Close"].dropna()
    loud, txt = kr_index_note(ks_all.index, start, px_date)
    log(f"{'  !! ' if loud else '· '}{txt} ({time.time() - t0:.0f}초)")
    special = load_krx_special_sessions()
    ended = kr_ended_days(px_date, ks_all.index, today)
    names0 = dict(zip(listing["Code"].astype(str).str.strip(), listing["Name"].astype(str))) if listing is not None and "Name" in listing.columns else {}
    px0 = px_date
    caps0 = kr_fb_caps(listing)     # 리뷰 M1: 2차 출처는 1차 출처 최종본의 시가총액 큰 순으로 물어요 (그날 캐시 파일의 시가총액은 빌 수 있어요)
    # 2026-11-20 (리뷰 M1): 코넥스 기준일 맞춰 보기 — 1차 출처 최종본(px0)의 코넥스 공식 종가. 네이버의 px0 종가가 이 값과 같은 코넥스만 확인해요
    # (px0 뒤 권리락 · 분할 · 병합으로 야후와 네이버가 함께 수정한 값을 그날 공식 종가로 내지 않게 · kr_knx_confirm)
    knx0 = kr_knx_anchor(listing, px_date)
    # 2026-11-21 (#161): 같은 날 다시 도는 실행은 발행본이 이미 두 출처로 확인한 종목을 다시 묻지 않아요 (보관본의 그 값으로 · kr_fb_cache_pick)
    fb_cached, fb_keep = None, {}
    if ended:
        fb_cached, why = kr_fb_cache_pick(kr_fb_cache_load(), prev, max(ended))
        log(f"{'  !! ' if fb_cached else '· '}2차 출처 보관본: {why}")
    px_date, listing, fb_known, px_src, fb_logs, (full_list, daum_shr) = kr_second_source(
        px_date, listing, ended, dt.datetime.now(KST), special,
        lambda d: kr_fb_universe(d, _fetch_listing_csv, fallback=listing), names=names0,
        fallback=lambda *a: kr_fallback_days(*a, caps=caps0, knx=kr_knx_fetchers(), anchor=knx0, cached=fb_cached, keep=fb_keep))   # 2026-11-20: 코넥스는 야후 .KQ × 네이버 (Jack, 11-19 답 5)
    if px_src["px"] == PX_SRC_FB and fb_keep.get("kk"):
        kr_fb_cache_save(fb_keep)
    if ended:
        log(f"  !! 1차 출처(캐시 최종본 {px0}) 뒤에 이미 끝난 거래일 {len(ended)}일: {', '.join(d.isoformat() for d in ended)} — 2차 출처(다음 × 야후 종가 · "
            "코넥스는 야후 .KQ × 네이버 종가)로 확인해요")
    for loud, txt in fb_logs:
        log(f"  !! {txt}" if loud else f"· {txt}")
    if px_src["px"] == PX_SRC_FB:
        list_src = PX_SRC_FB
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
    # 2026-11-19 (Jack): 두 출처로 확인된 종목 코드 (상위 MAX_KR 로 자르기 전) — 아래 마지막 확인 종가 단계(kr_own_close_step)가 그날 전체 목록에서
    # 확인 못 한 종목을 골라요. 이름이 겹치지 않게 따로 둬요 (2026-11-19 시험 실행: 아래 우선주 단계의 'unconf' 목록이 덮어써 멈췄어요)
    kr_own_conf_codes = set(listing["Code"].astype(str).str.strip()) if px_src["px"] == PX_SRC_FB else set()
    # 2026-11-19 (리뷰 B1): 2차 출처 날은 확인된 종목만 목록에 있어요. 우선주 주식 수는 가격과 상관없으니 그날 전체 목록에서 (확인 못 한 우선주도 ·
    # 다음 상장주식수와 맞춰 봐요) — EPS · BPS 주식 수와 상장 안 된 우선주 판단이 빠지지 않게. 우선주 시가총액은 확인된 종가로만 (kr_pref_caps(listing)),
    # 확인 못 한 우선주가 있는 회사는 회사 시가총액을 몰라 EV · P/CF 를 비워요 (build_corp · evNo prefPx).
    pref_list = full_list if px_src["px"] == PX_SRC_FB and full_list is not None else listing
    pref_shares = kr_pref_shares(pref_list)   # v19.1b: 상위 2,500개로 자르기 전 — 작은 우선주도 회사의 주식 수에 들어가야 해요
    pref_caps = kr_pref_caps(listing)         # v19.1f: 같은 목록의 우선주 시가총액 (EV 의 회사 시가총액) — 확인된 종가로만
    pref_cap_missing = set()
    if pref_list is not listing:
        ok_codes = set(listing["Code"].astype(str).str.strip())
        pcodes = [str(c).strip() for c in pref_list["Code"] if is_preferred(str(c).strip())]
        unconf = sorted(c for c in pcodes if c not in ok_codes)
        pref_cap_missing = {c[:5] for c in unconf}
        shr_full = _shares_map(pref_list)
        sdiff = sorted(c for c in pcodes if daum_shr.get(c) and shr_full.get(c) and int(shr_full[c]) != daum_shr[c])
        nm = dict(zip(pref_list["Code"].astype(str).str.strip(), pref_list["Name"].astype(str)))
        log(f"{'  !! ' if unconf or sdiff else '· '}우선주 (2차 출처 날): 주식 수는 그날 전체 목록 {len(pcodes):,}종목에서 · 종가를 확인 못 한 우선주 {len(unconf):,}"
            + (" (" + ", ".join(f"{c} {nm.get(c, '')}" for c in unconf[:12]) + f") → 그 회사 {len(pref_cap_missing):,}곳은 EV · P/CF 를 비워요" if unconf else "")
            + f" · 목록 파일과 다음의 주식 수가 다른 우선주 {len(sdiff):,}" + (f": {', '.join(sdiff[:12])}" if sdiff else ""))
    n_pref = sum(1 for c in pref_list["Code"] if is_preferred(str(c)))
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
    n_all = len(listing)
    # 2026-11-21 (#161 리뷰 M1): 같은 기준일을 다시 도는 실행은 지난 발행본의 국내 종목을 상위 MAX_KR 밖이어도 처리해요 (잃지 않게 · kr_same_day_keep)
    keep_same = kr_same_day_keep(prev, px_date)
    listing = select_kr_universe(listing, MAX_KR, keep=keep_same)
    kn = kr_same_day_keep_note(keep_same, listing, MAX_KR, n_all)
    if kn:
        log(f"  !! {kn[1]}" if kn[0] else f"· {kn[1]}")
    if sample_size():
        listing = sample_universe(listing, sample_size())
        log(f"  !! 표본 실행: 국내 {len(listing):,}종목만 처리해요")
    if n_all > MAX_KR:
        log(f"  → 전체 {n_all:,}개 중 시가총액 상위 {MAX_KR:,}개 처리 (MAX_KR)")
    log(f"  → {len(listing):,}개 종목 (필수 종목 {len(MUST_KR)}개 확인)")
    # 2026-11-19: KRX-DESC 가 이름만 주고 업종을 비운 날 (11-18 · KRX 로그인 필요) — 지난 발행본의 업종 · 주요제품을 이어 써요 (크게 남겨요).
    # 처리하는 종목(시가총액 상위 MAX_KR)만 세요 — 지난 발행본에 없는 종목 = 새로 들어온 종목
    n_desc = sum(1 for v in desc.values() if v[0])
    prev_desc, prev_day, prev_bad = kr_prev_desc(prev)
    codes_all = set(listing["Code"].astype(str).str.strip())
    desc, carried, no_ind = kr_desc_carry(desc, prev_desc, codes_all)
    prev_codes = {str(x.get("t")) for x in (prev or {}).get("stocks") or [] if x.get("cls") == "kr"}
    new_none = sorted(c for c in no_ind if c not in prev_codes)
    names_l = dict(zip(listing["Code"].astype(str).str.strip(), listing["Name"].astype(str)))
    ind_src = {"v": 1, "desc": n_desc, "carried": len(carried), "none": len(no_ind), "newNone": len(new_none),
               "asOf": (prev_day if carried else today.isoformat()), "from": "KRX-DESC" + (" + prev" if carried else "")}
    if carried:
        log(f"  !! 업종: KRX-DESC 에 업종이 없어 지난 발행본({prev_day} 업종 글자)의 업종 · 주요제품을 이어 써요 — {len(carried):,}종목 "
            f"(KRX-DESC 업종 {n_desc:,} · 지난 발행본에서 읽은 업종 {len(prev_desc):,} · 읽지 못한 설명 {prev_bad:,})"
            + (f" · 업종이 없는 새 종목(지난 발행본에 없음) {len(new_none):,}: " + ", ".join(f"{c} {names_l.get(c, '')}" for c in new_none[:12]) if new_none else ""))
    else:
        log(f"· 업종: KRX-DESC {n_desc:,}종목 · 이어 쓴 종목 0 · 업종 없음 {len(no_ind):,} (그중 지난 발행본에 없던 종목 {len(new_none):,})")
    if not n_desc and not carried and "_prev_s" in listing.columns:
        log("  !! 업종은 지난 data.json 값을 그대로 사용")
    elif not n_desc and not carried:
        log("  !! 업종 정보를 못 받아왔어요 — 업종이 '기타'로 들어갑니다")

    # 공식 종가와 파일의 Close(저녁엔 시간외 가격) 비교 — 참고용 로그
    if px_date is not None:
        off = listing.apply(kr_official_close, axis=1)
        cl = pd.to_numeric(listing["Close"], errors="coerce")
        diff = ((cl - off).abs() / off > 0.01).sum()
        log(f"· 공식 종가 = 시가총액 ÷ 상장주식수 (기준일 {px_date}) · 파일의 Close 가 1% 넘게 다른 종목 {int(diff):,}개 (시간외 가격)")
    # 2026-11-19 (Jack 규칙 3): 1차 출처를 쓴 날도 필수 종목 + 표본을 야후 종가와 맞춰 봐요 (로그 · pxSrc.chk · 관문이 경고해요 — 빼지는 않아요)
    if px_date is not None and px_src["px"] == PX_SRC_LISTING:
        try:
            cm = {str(c).strip(): m for c, m in zip(listing["Code"], listing["Market"])}
            pick = [c for c in GATE_MUST if c in cm] + px_check_sample([c for c, m in cm.items() if yahoo_kr_symbol(c, m)])
            pcm = {c: cm[c] for c in dict.fromkeys(pick)}
            ych, _, ycut = fetch_yahoo_kr_closes(pcm, px_date - dt.timedelta(days=7), px_date + dt.timedelta(days=1))
            yfill = yahoo_fill_day(ych, pcm, px_date, krx_close(px_date, special))     # 그날 일봉 종가가 아직 빈 종목 (마감 뒤 regularMarketPrice)
            px_src["chk"] = kr_primary_check(listing, px_date, ych)
            px_src["chk"]["yMeta"] = yfill["meta"]
            px_src["chk"]["cut"] = fb_cut_record({"yahoo": ycut, "fill": yfill.get("cut")})   # 2026-11-20: 시간 한도로 묻지 못한 종목 (경고만)
        except Exception as e:
            px_src["chk"] = {"src": "yahoo", "n": 0, "same": 0, "none": 0, "diff": [], "err": type(e).__name__}
            log(f"  !! 1차 출처 야후 확인 실패: {type(e).__name__}: {str(e)[:120]}")
        ck = px_src["chk"]
        ccut = (ck.get("cut") or {}).get("yahoo", 0) + (ck.get("cut") or {}).get("fill", 0)
        log(f"{'  !! ' if ck['diff'] or not ck['n'] or ccut else '· '}1차 출처 확인 (필수 종목 + 표본 {PX_CHECK_SAMPLE} · 야후 종가와 원 단위까지): 같음 {ck['same']:,} / {ck['n']:,}"
            f" · 야후 값 없음 {ck['none']:,}" + (f" · 다름 {len(ck['diff'])}: {', '.join(ck['diff'][:12])}" if ck["diff"] else "")
            + (f" · 야후를 받지 못했어요 ({ck['err']})" if ck.get("err") else "")
            + (f" · 시간 한도({ck['cut']['s']}초)로 묻지 못함 {ccut:,} (확인만 줄어요 · 가격은 1차 출처 그대로)" if ccut else ""))
    # 2026-11-20 (Jack, 2026-11-19 답 5 "daily KONEX checking too"): 처리하는 코넥스 종목 (pxSrc.knx.t · 발행 직전에 발행하는 종목으로 줄여요) ·
    # 1차 출처 날에는 그 종목의 최종본 공식 종가를 모두 네이버 일봉 종가와 맞춰 봐요 (로그 · pxSrc.knx.chk · 관문이 경고만 — 빼지 않아요)
    knx_codes = sorted({c for c, m in zip(listing["Code"].astype(str).str.strip(), listing["Market"]) if yahoo_knx_symbol(c, m)})
    px_src.setdefault("knx", {"px": None, "t": [], "n": {}, "chk": None})["t"] = knx_codes
    if px_date is not None and px_src["px"] == PX_SRC_LISTING:
        px_src["knx"]["chk"] = kr_knx_daily_check(listing, px_date, knx_codes)
        loud, txt = kr_knx_check_note(px_src["knx"]["chk"], len(knx_codes))
        log(f"  !! {txt}" if loud else f"· {txt}")
    elif px_src["px"] == PX_SRC_FB:
        log(f"· 처리하는 코넥스 {len(knx_codes):,}종목 — 그날 종가는 모두 야후 .KQ × 네이버로 확인한 값이에요 (2차 출처 날 · 위 '코넥스 2차 출처' 줄)")

    last = px_date or (today - dt.timedelta(days=1))
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
    d1_map, v20_map, sessions, ok_prev = {}, {}, [], False
    base_ok, d1_base = None, None
    if px_date is not None:
        sessions, snotes, prev_final = kr_recent_sessions(px_date, _fetch_listing_csv, _listing_commit_kst, special=special, known=fb_known)
        for n in snotes:
            log(f"  ({n})" if not n.startswith("!!") else f"  {n}")
        want_prev = kr_prev_session(px_date, ks_all.index)
        ok_prev = prev_session_ok(sessions, prev_final, want_prev)
        if sessions and not ok_prev and prev_final:
            log(f"  !! 직전 거래일은 {want_prev} (KOSPI)인데 찾은 목록 파일은 {sessions[0][0]} — 그날 파일이 없거나 최종본이 아니라 d1 을 "
                "그 파일로 계산하지 않아요 (아래 'd1:' 줄)")
        d1_map, v20_map, dcnt = kr_d1_val20(listing, sessions, ok_prev)
        log(f"{'  !! ' if not ok_prev else '· '}d1·val20: 앞선 거래일 파일 {len(sessions)}개"
            + (f" (직전 {sessions[0][0]})" if sessions else "") + f" · d1 {len(d1_map):,} · val20 {len(v20_map):,}"
            + (f" · {dict(dcnt)}" if dcnt else ""))
        # 2026-11-21: 직전 거래일 파일을 쓸 수 없는 날 — KRX 기준가 × 지난 발행본 종가 (두 출처가 원 단위까지 같은 종목만 · kr_d1_from_base)
        if not ok_prev and want_prev is not None:
            d1_map, base_ok, d1_base = kr_d1_base_day(listing, prev, want_prev)
            # #161 리뷰 M2: 지난 발행본이 같은 기준일 (그날 아침 발행 · 직전 거래일이 아님) 이면 그 발행본의 d1 을 같은 종가인 종목만 (kr_d1_same_day)
            same_d1 = kr_d1_same_day(listing, prev, px_date, want_prev) if d1_base.get("why") == "day" else None
            if same_d1 is not None:
                d1_map, base_ok, d1_base = same_d1
            loud, txt = d1_base_note(d1_base)
            log(f"  !! {txt}" if loud else f"· {txt}")
    # 2026-11-14 (Jack, design chat 2026-11-08): 기준일에 거래가 없던 종목은 d1 빈 칸 + noTrade · 다른 빈 d1 은 이유(d1Why)를 달아요
    # 표시할 종목 · 표시하지 않는 까닭은 kr_no_trade_plan 한 곳에서 (리뷰 S1: 순수 함수로 시험해요)
    no_trade, nt_unseen, nt_odd, nt_must = kr_no_trade_plan(listing) if px_date is not None else (set(), "cols", set(), [])
    names_of = dict(zip(listing["Code"].astype(str).str.strip(), listing["Name"].astype(str)))
    if nt_unseen:
        why_ko = {"cols": "목록 파일에 거래량(Volume) · 시가(Open) 칸이 없어요",
                  "blank": f"거래량 · 시가가 둘 다 숫자인 행이 {kr_no_trade_read(listing):,} / {len(listing):,} 뿐이에요 (칸이 빈 값으로 바뀌었어요)",
                  "many": f"거래 없는 행이 {NO_TRADE_MAX_SHARE:.0%} 를 넘어요 (파일의 잘못)"}[nt_unseen]
        log(f"  !! 거래 없는 종목을 가리지 않았어요 — {why_ko}. 거래가 없던 종목도 d1 0.00% 로 나가요 (관문이 경고해요)")
    if nt_must:
        must_names = ", ".join(f"{c} {names_of.get(c, '')}" for c in nt_must)
        log(f"  !! 필수 종목 {must_names} 이 거래 없음(거래량 0 · 시가 0)으로 나와요 — "
            "그 행의 잘못일 수 있어 표시하지 않았어요 (d1 은 공식 종가로 계산 · 관문이 경고해요)")
    d1_map, d1_why, nt_map, why_n = kr_d1_split(listing, sessions, ok_prev, d1_map, no_trade, base_ok=base_ok)
    if not nt_unseen:
        nt_names = sorted(f"{c} {names_of.get(c, '')}" for c in no_trade if c in d1_why)
        zero = not why_n["noTrade"]          # 리뷰 S2: 가릴 수 있었는데 한 종목도 없으면 칸의 뜻이 바뀌었을 수 있어요 (보통 날 목록 파일 135 ~ 141행)
        log(f"{'  !! ' if zero else '· '}거래 없는 종목 (기준일 {px_date} 거래량 0 · 시가 0 · 거래대금 0): {why_n['noTrade']:,}종목 → d1 빈 칸 · noTrade"
            f" (기준가 변화 ntD1 {len(nt_map):,}종목 · 0 이 아닌 것 {sum(1 for v in nt_map.values() if v):,})"
            + (f": {', '.join(nt_names[:12])}{' …' if len(nt_names) > 12 else ''}" if nt_names else "")
            + (" — 보통 날에는 목록 파일에 135 ~ 141행이 있어요. 목록 파일의 거래량 · 시가 칸을 확인해요 (관문이 경고해요)" if zero else ""))
    if nt_odd:
        log(f"  !! 거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 행 {len(nt_odd)}개 (출처의 행이 스스로 어긋나요 · 거래 없음으로 표시하지 않았어요): "
            + ", ".join(sorted(f"{c} {names_of.get(c, '')}" for c in nt_odd)[:12]))
    out_range = sorted(f"{c} {names_of.get(c, '')}" for c, w in d1_why.items() if w == "range")
    log(f"{'  !! ' if why_n['prev'] else '· '}국내 d1 빈 칸 이유 (목록 파일): 거래 없음 {why_n['noTrade']:,} · ±{D1_MAX_KR:g}% 밖 {why_n['range']:,}"
        f" · 직전 거래일 행 없음 {why_n['new']:,} · 직전 거래일 파일을 쓸 수 없음 {why_n['prev']:,}"
        + (f" (±{D1_MAX_KR:g}% 밖: {', '.join(out_range[:12])})" if out_range else ""))
    # 네이버 일봉은 넥스트레이드까지 합친 '마지막 체결가'라 공식 종가와 다른 날이 있어요 (리뷰: 300일 중 30일쯤, 최대 4%).
    # 목록 파일을 받은 최근 거래일들은 공식 종가로 고쳐요. 그보다 오래된 날은 v18.0 Part B 에서 공식 종가 이력으로 바꿔요.
    off_by_day = {pd.Timestamp(d): _official_map(df) for d, df in sessions}
    # 2026-11-14: 네이버 일봉은 수정주가라, 그날과 오늘 사이에 KRX 기준가가 바뀐 날(분할 · 병합 · 감자 · 권리락)의 앞 공식 종가는 넣지 않아요.
    # 확인할 수 없는 날은 상장주식수와 값 차이로 (pin_why_not)
    shr_by_day = {pd.Timestamp(d): _shares_map(df) for d, df in sessions}
    shr_now = _shares_map(listing)
    ref_by_day, ref_events = kr_ref_links([(px_date, listing)] + sessions, ks_all.index, set(listing["Code"])) if px_date else ({}, [])
    # 2026-11-20 (검증 리뷰 S3): 2차 출처 날 코넥스 행은 전일 대비(Changes)가 빈 값이라 (두 출처 모두 기준가를 주지 않아요 · kr_knx_row) 늘 '확인 못 함'
    # — 예상한 것이라 따로 세어 '·' 줄로, 그 밖의 확인 못 한 종목만 크게 (!!)
    ref_exp = kr_ref_blank_knx(([listing] if px_src["px"] == PX_SRC_FB else []) + list((fb_known or {}).values()))
    ref_sum = log_ref_links(ref_by_day, ref_events, dict(zip(listing["Code"], listing["Name"].astype(str))), len(sessions), expected=ref_exp)
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
        log(f"· pykrx 펀더멘털 {len(fundamentals):,}건 (0이어도 정상 — PER·PBR·EPS·BPS 는 쓰지 않고 DART 지배주주 몫으로 계산해요 · v19.1f)")
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
    pin_kept, kept_names, pin_bad, jumps = collections.Counter(), {}, [], []    # 2026-11-14: 고치지 않은 봉 · 자기 점검 · 제한폭 넘는 움직임
    win_cut = {}                # 2026-11-14 저녁: 움직임이 있는 종목의 창마다 첫 봉 날짜 (mark_px_bad 가 그 창에 움직임이 드는지 봐요)
    naver_bad = []                                                              # 2026-11-14 (리뷰 S2): 네이버 시계열의 같은 날짜 · 잘못된 값
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
            px, glitch = naver_clean(px)           # 리뷰 S2: 같은 날짜 두 번 · 0 이하 · 무한대 (출처의 잘못 — 크게 남겨요)
            if glitch:
                with lock:
                    naver_bad.append((code, str(row["Name"]), glitch))
            if close is not None:
                raw = cut_at(px, px_date)          # 네이버 원래 시계열 (자기 점검 · 움직임 이유에 써요)
                px, how = pin_close(px, px_date, close)
                kc = collections.Counter()
                px, nfix = pin_recent(px, off_by_day, code, shr_by_day, shr_now.get(code), kept=kc, ref_by_day=ref_by_day)
                bad = pin_audit(raw, px, px_date, off_by_day, shr_by_day, shr_now.get(code), code, ref_by_day=ref_by_day)
                with lock:
                    pin[how] += 1
                    pin["recent_fixed"] += nfix
                    pin["recent_stocks"] += 1 if nfix else 0
                    pin_kept.update(kc)
                    if kc:
                        kept_names[code] = (str(row["Name"]), dict(kc))
                    if bad:
                        pin_bad.append((code, str(row["Name"]), bad))
            else:
                px = cut_at(px, last)
                raw = px
            if len(px) < 60:
                with lock:
                    dropped["시세 60일 미만"] += 1
                return None
            jm = kr_jumps(px, raw, kr_day_limit(row.get("Market")))
            if jm:
                # 2026-11-14 저녁 (Jack): 칸마다 계산 창의 첫 봉 — hi · lo = px.tail(252) · mom = px[-252] · r3 = px[-64] · r1 = px[-22] (아래 계산 그대로).
                # 봉이 모자라면 시계열 전체 (첫 봉). 그 밖의 칸은 시계열 전체예요 (PX_BAD_ALWAYS).
                cut = {w: (px.index[-n] if len(px) >= n else px.index[0]).date().isoformat() for w, n in PX_BAD_WIN_BARS.items()}
                with lock:
                    jumps.append((code, str(row["Name"]), jm))
                    win_cut[code] = cut
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a, bse, bn = beta_fit(ret, bench, rf)
            f = fundamentals.get(code, {})
            # v19.1f (리뷰 2026-11-08): PER·PBR·EPS·BPS 는 pykrx 값을 쓰지 않아요 — 늘 DART 로 계산한 지배주주 몫(fill_multiples ·
            # 영수증 epsIn·bpsIn). KRX 가 다시 답해도 기준이 섞이지 않게 (pykrx 배당 DPS·DIV 는 예전처럼, DART 가 나중에 덮어써요)
            per = pbr = eps = bps = None
            dps = _num(f.get("DPS"))
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
                # 2026-11-14: 기준일에 거래가 없던 종목 (d1 빈 칸) · 빈 d1 의 이유 · 거래 없는 날의 기준가 변화 (포트폴리오 평가 금액에만)
                "noTrade": True if code in no_trade and code in d1_why else None,
                "d1Why": d1_why.get(code), "ntD1": nt_map.get(code),
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
                 and is_fund_industry(r.get("dk")))      # 2026-11-19: 띄어쓰기 둘 다 (DART 로는 이 업종을 채우지 않아요 · kr_ind_dart_plan)
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
    log_naver_clean(naver_bad)
    krs = kr_series_check(pin, pin_kept, kept_names, pin_bad, jumps, {r["t"] for r in out}, len(off_by_day),
                          ref=ref_sum)
    mark_px_bad(out, krs, win_cut)           # 2026-11-14 (Jack): 그 움직임이 계산 창에 든 숫자를 비워요 (점수 · corp.json 보다 먼저)
    # 2026-11-19 (Jack): 확인 못 한 종목은 지난 발행본의 마지막 확인 종가로 (pxd · d1 없음) — 오늘 만든 종목 뒤에 더해요 (그 시세 숫자는 그 종가의
    # 것이라 오늘 시계열 점검 · 비우기를 다시 하지 않아요 · 과거 주가 기록 오류 표시는 지난 움직임과 함께 krSeries 에 옮겨요). 재무 · 배당 · 점수는
    # main 이 다른 종목처럼 그 가격으로 다시 만들어요
    # 2026-11-20 (리뷰 S1): 지난 발행본이 DART 로 채운 업종 글자는 오늘 다시 채워요 (no_ind 에 더해요 · indSrc.none 도 그 수로)
    if px_src["px"] == PX_SRC_FB:
        kr_own_close_step(prev, full_list, kr_own_conf_codes, px_src, px_date, list(ks_all.index), out, krs, prod_map, desc=desc, no_ind=no_ind)
        ind_src["none"] = len(no_ind)
    elif px_date is not None:
        log("· 국내 종가 미확인 0종목 (1차 출처 날 · 마지막 확인 종가로 싣는 종목 없음)")
    # 2026-11-14: 발행하는 종목의 빈 d1 이유 수 (data.json d1Blank · 관문이 종목마다의 noTrade · d1Why 와 맞춰 봐요) · cols: 거래 없음을 가릴 수 있었는지
    d1_blank = d1_blank_counts(out, not nt_unseen, nt_unseen, nt_odd, nt_must)
    log(f"{'  !! ' if d1_blank['prev'] or nt_unseen else '· '}발행하는 국내 종목의 d1 빈 칸: "
        + " · ".join(f"{D1_WHY_KO[k]} {d1_blank[k]:,}" for k in D1_WHY) + (f" · 거래 없음은 가리지 않음 ({nt_unseen})" if nt_unseen else ""))
    meta = {"pxDate": px_date.isoformat() if px_date else None,
            "ksDate": ks_date.isoformat() if ks_date else None, "listSrc": list_src, "_index": kospi, "_prod": prod_map,
            "_prefShares": pref_shares, "_prefCaps": pref_caps, "krSeries": krs, "d1Blank": d1_blank}
    meta["d1Base"] = d1_base                 # 2026-11-21: 직전 거래일 파일을 쓸 수 없던 날에만 (kr_d1_base_day) · 보통 날은 None (data.json 에 칸 없음)
    # 2026-11-19: 공식 종가 출처 · 업종 글자 출처 (data.json · 관문 줄) · 업종 글자가 없는 종목 (main 이 DART 기업개황 업종 코드로 채워요 · kr_ind_fill)
    meta.update({"pxSrc": px_src, "indSrc": ind_src, "_prefCapMissing": sorted(pref_cap_missing), "_noInd": sorted(no_ind)})
    return out, bench, mkt, meta


def kr_ref_blank_knx(frames):
    """2차 출처로 만든 날의 목록(frames)에서 전일 대비(Changes)가 빈 코넥스 종목 (2026-11-20 · 검증 리뷰 S3 · 순수 함수). 코넥스 행 (kr_knx_row) 은
    두 출처 모두 기준가를 주지 않아 Changes 가 늘 빈 값이라 KRX 기준가 연결은 '확인 못 함' 이 돼요 — 예상한 것 (log_ref_links expected)."""
    out = set()
    for df in frames or []:
        if df is None or not len(df) or not {"Code", "Market", "Changes"} <= set(df.columns):
            continue
        for c, m, ch in zip(df["Code"].astype(str).str.strip(), df["Market"], df["Changes"]):
            if yahoo_knx_symbol(c, m) and _fin(ch) is None:
                out.add(c)
    return out


def log_ref_links(by_day, events, names, days, expected=()):
    """kr_ref_links 결과를 한 줄로 남기고 data.json krSeries.ref 를 돌려줘요 (2026-11-14). 크게(!!) 남기는 때: 기준가를 확인 못 한 종목이 있거나
    (앞 파일에는 있는 행 · Changes 값이 빠짐 · 사이에 빠진 거래일), 기준가가 새로 정해진 종목이 REF_EVENTS_LOUD 보다 많을 때. 이 기간에 새로 상장한
    종목('new' — 상장 앞 날은 공식 종가가 없어 고칠 봉도 없어요)은 세기만 하고 크게 남기지 않아요 (리뷰 S1: 매일 몇 종목은 새로 상장해요).
    names: {코드: 이름} · days: 거래일 파일 수. 반환: {breakStocks, unknownStocks, newStocks} (종목 수 — 한 종목에 사건이 여러 번이어도 하나).
    expected (2026-11-20 · 검증 리뷰 S3): 확인 못 함이 예상된 종목 (2차 출처 날 코넥스 · kr_ref_blank_knx) — 그 종목은 따로 '·' 줄에 세고 크게 남기지
    않아요 (그 밖의 확인 못 한 종목이 있으면 그대로 크게). unknownStocks 는 예전처럼 모두 세요 (관문이 보는 data.json 모양 그대로)."""
    oldest = by_day[min(by_day)] if by_day else {}
    unknown_all = sorted(c for c, st in oldest.items() if st == "unknown")
    exp = set(expected or ())
    unknown = [c for c in unknown_all if c not in exp]
    unknown_exp = [c for c in unknown_all if c in exp]
    new = sorted(c for c, st in oldest.items() if st == "new")
    brk = sorted({e[0] for e in events})
    ev_txt = [f"{c} {names.get(c, '')} {d:%m-%d} {p:,.0f}→{r:,.0f}" for c, d, p, r in sorted(events, key=lambda e: (e[1], e[0]))]
    new_txt = [f"{c} {names.get(c, '')}".strip() for c in new]
    many = len(brk) > REF_EVENTS_LOUD
    log(f"{'  !! ' if unknown or many else '· '}KRX 기준가 연결 (목록 파일의 Close − Changes = 앞 파일의 공식 종가): "
        f"최근 {days}거래일 사이 기준가가 새로 정해진 종목 {len(brk):,} ({len(events):,}건)"
        + (f" ({', '.join(ev_txt[:JUMP_LOG_SHOW])}{' 외 ' + str(len(ev_txt) - JUMP_LOG_SHOW) + '건' if len(ev_txt) > JUMP_LOG_SHOW else ''})" if ev_txt else "")
        + f" · 이 기간에 새로 상장한 종목 {len(new):,}"
        + (f" ({', '.join(new_txt[:5])}{' 외 ' + str(len(new_txt) - 5) + '종목' if len(new_txt) > 5 else ''} — 상장 앞 날은 고칠 봉이 없어요)"
           if new_txt else "")
        + f" · 확인 못 한 종목 {len(unknown):,}" + (f" (예: {', '.join(unknown[:5])} — 그 종목은 주식 수와 값 차이로만 고쳐요)" if unknown else "")
        + (f" (2차 출처 날 코넥스 {len(unknown_exp):,}종목은 빼고 셌어요 — 아래 줄)" if unknown_exp else "")
        + (f" — 평소(2026-11-13: 18종목)보다 많아요. 목록 파일의 Changes 칸이 바뀌었을 수 있어요 (고치는 날이 줄 뿐 틀린 값은 들어가지 않아요)"
           if many else ""))
    if unknown_exp:
        ex_txt = [f"{c} {names.get(c, '')}".strip() for c in unknown_exp]
        log(f"· KRX 기준가 연결 — 2차 출처 날 코넥스 (야후 .KQ × 네이버 · 두 출처 모두 기준가를 주지 않아 전일 대비가 빈 값) 확인 못 한 종목 "
            f"{len(unknown_exp):,}: 예상한 것이에요 (그 종목은 주식 수와 값 차이로만 고쳐요)"
            + f" ({', '.join(ex_txt[:5])}{' 외 ' + str(len(ex_txt) - 5) + '종목' if len(ex_txt) > 5 else ''})")
    return {"breakStocks": len(brk), "unknownStocks": len(unknown_all), "newStocks": len(new)}


def log_naver_clean(naver_bad):
    """naver_clean 이 고친 종목을 크게, 이름 · 날짜 · 값과 함께 (없으면 보통 줄). naver_bad: [(코드, 이름, [(날짜, 이유, 값들)])]."""
    if not naver_bad:
        log("· 네이버 시계열 점검: 같은 날짜 두 번 · 0 이하 · 무한대 값 0종목")
        return
    dup = sorted((c, nm, [p for p in g if p[1] == "dup"]) for c, nm, g in naver_bad if any(p[1] == "dup" for p in g))
    bad = sorted((c, nm, [p for p in g if p[1] == "bad"]) for c, nm, g in naver_bad if any(p[1] == "bad" for p in g))

    def txt(items):
        return ", ".join(f"{c} {nm} ({' · '.join(f'{t:%Y-%m-%d} ' + ' / '.join(f'{v:,.0f}' for v in vs) for t, _, vs in g[:2])}"
                         f"{' …' if len(g) > 2 else ''})" for c, nm, g in items[:JUMP_LOG_SHOW]) + (
            f" 외 {len(items) - JUMP_LOG_SHOW}종목" if len(items) > JUMP_LOG_SHOW else "")
    if dup:
        log(f"  !! 네이버 시계열 같은 날짜 두 번 (다른 값): {len(dup)}종목 — 그 날짜를 빼고 계산해요 (어느 값이 맞는지 몰라요): {txt(dup)}")
    if bad:
        log(f"  !! 네이버 시계열 0 이하 · 무한대 값: {len(bad)}종목 — 그 봉을 빼고 계산해요: {txt(bad)}")


def kr_series_check(pin, kept, kept_names, bad, jumps, published, days, ref=None):
    """2026-11-14: 국내 시계열 점검을 크게 남기고 data.json krSeries 를 만들어요 (관문이 읽어요).
    pin: 고정 집계 · kept: 고치지 않은 봉 Counter (basis · far · shr) · kept_names: {코드: (이름, 이유별 수)} · bad: [(코드, 이름, [(날짜, 이유)])]
    (pin_audit) · jumps: [(코드, 이름, [(날짜, %, 이유)])] (kr_jumps) · published: 발행하는 종목 코드 (움직임은 이 종목만 실어요) · days: 고정한 거래일 수.
    ref: {breakStocks 기준가가 새로 정해진 종목 수 · unknownStocks 기준가 연결을 확인 못 한 종목 수 · newStocks 그 기간에 새로 상장한 종목 수}
    (kr_ref_links).
    krSeries: v 1 · days · pinned 고친 봉 · pinStocks · kept {basis · far · shr} 고치지 않은 봉 · keptStocks · bad 자기 점검에 걸린 봉 (0 이어야 해요) ·
    badStocks [코드…] · ref · jump [[코드, 날짜, %, 이유]…] 가격 제한폭 + 넥스트레이드 차이로 설명되지 않는 하루 움직임 (KR_JUMP_WHY)."""
    nbad = sum(len(b) for _, _, b in bad)
    basis = sorted((c, nm) for c, (nm, k) in kept_names.items() if k.get("basis"))
    farn = sum(1 for _, k in kept_names.values() if k.get("far"))
    log(f"{'  !! ' if kept.get('shr') else '· '}최근 {days}거래일 중 고치지 않고 네이버 봉 그대로 둔 봉: {sum(kept.values()):,}개 · "
        f"{len(kept_names):,}종목 — 다른 기준(기준가가 바뀐 날 앞 · 확인 못 한 날은 상장주식수가 {PIN_SHR_TOL:.0%} 넘게 다름) {kept.get('basis', 0):,}개 · "
        f"{len(basis):,}종목 · 공식 종가가 네이버 봉과 멂(확인된 날 {PIN_REF_TOL:.0%} · 확인 못 한 날 {PIN_PX_TOL:.0%} 넘게) {kept.get('far', 0):,}개 · "
        f"{farn:,}종목 · 주식 수 모름 {kept.get('shr', 0):,}개"
        + (f" — 다른 기준인 종목: {', '.join(f'{c} {nm}' for c, nm in basis[:JUMP_LOG_SHOW])}"
           + (f" 외 {len(basis) - JUMP_LOG_SHOW}종목" if len(basis) > JUMP_LOG_SHOW else "") if basis else ""))
    if bad:
        log(f"  !! 공식 종가 고정 자기 점검: 허락되지 않은 봉 {nbad:,}개 · {len(bad):,}종목 — 관문에서 실패해요: "
            + ", ".join(f"{c} {nm} ({', '.join(f'{t:%m-%d} {w}' for t, w in b[:3])})" for c, nm, b in sorted(bad)[:JUMP_LOG_SHOW]))
    else:
        log("· 공식 종가 고정 자기 점검: 네이버 봉과 달라진 봉은 모두 같은 기준이 확인된 그날 공식 종가 (어긋남 0)")
    jm = sorted((c, nm, j) for c, nm, j in jumps if c in published)
    by_why = collections.Counter(w for _, _, j in jm for _, _, w in j)
    names = [f"{c} {nm} ({' · '.join(f'{t:%Y-%m-%d} {p:+.1f}% {KR_JUMP_WHY[w]}' for t, p, w in j[:2])}{' …' if len(j) > 2 else ''})"
             for c, nm, j in jm]
    log(f"{'  !! ' if jm else '· '}한국 시계열 하루 ±{KR_DAY_LIMIT:g}% (코넥스 ±{KONEX_DAY_LIMIT:g}%) 넘는 움직임 (넥스트레이드 차이 {PIN_PX_TOL:.0%} 빼고): "
        f"{len(jm)}종목" + (f" · {', '.join(f'{KR_JUMP_WHY[w]} {n}' for w, n in sorted(by_why.items()))} — "
                            + ", ".join(names[:JUMP_LOG_SHOW]) + (f" 외 {len(names) - JUMP_LOG_SHOW}종목" if len(names) > JUMP_LOG_SHOW else "")
                            + " (이 종목의 숫자 중 계산 창에 그 움직임이 든 것은 다음 줄에서 비워요 · mark_px_bad · 관문이 경고해요)" if jm else ""))
    return {"v": 1, "days": int(days), "pinned": int(pin.get("recent_fixed", 0)), "pinStocks": int(pin.get("recent_stocks", 0)),
            "kept": {k: int(kept.get(k, 0)) for k in ("basis", "far", "shr")}, "keptStocks": len(kept_names),
            "bad": int(nbad), "badStocks": sorted(c for c, _, _ in bad),
            "ref": {k: int((ref or {}).get(k, 0)) for k in ("breakStocks", "unknownStocks", "newStocks")},
            "jump": [[c, t.date().isoformat(), float(p), w] for c, _, j in jm for t, p, w in j]}


# 2026-11-14 (Jack, Q2 (a) "this week"): "For those 18 stocks, hide every number built on the broken price history: the 52-week range,
# 출렁임, 위험, beta, 1-year and other period returns, and the % labels on their charts. Take them out of the 추세 list on 홈 and any
# 출렁임-based list or rule." 그 종목 = 오늘 실행의 krSeries.jump 에 있는 종목 (하루 움직임이 가격 제한폭 + 넥스트레이드 차이로 설명되지 않아요 —
# 대개 네이버가 고치지 않은 감자 · 거래정지 뒤 재개 · 하루만 튄 봉. 날마다 바뀔 수 있어서 코드를 적어 두지 않아요). 저녁 (Jack: "hide only the
# numbers whose calculation window includes the bad day"): 시계열로 만든 칸(관문 파일의 PX_BAD_DATA) 중 계산 창에 그 움직임 날짜가 든 칸만 지워요 —
# 시계열 전체 칸(PX_BAD_ALWAYS: 변동성 · 베타 · 표준오차 · 쓴 날 수 · 알파 · 3년 수익률 · 샤프 · 최대 낙폭 · 상승 월 비율 · 저변동 점수)은 늘,
# 52주 최고 · 최저 · 1년 수익률 · 추세 점수는 마지막 252봉에, 3개월은 64봉에, 1개월은 22봉에 들 때만 (PX_BAD_WIN). pxBad = 가장 최근 움직임 날짜 ·
# pxBadF = 지운 칸. 점수(add_percentiles)는 빈 칸을 빼고 매겨서 다른 종목의 순위도 그 칸 없이 나와요. corp.json(build_corp)은 같은 칸을 이
# 종목에서 옮겨 싣고 pxBad · pxBadF 를 그대로 달아요. 앱은 52주까지 지운 종목에 Jack 의 줄 "과거 주가 기록 일부에 오류가 있어서 52주 범위와
# 출렁임·위험 숫자는 비워 두었어요." 를, 52주는 보이는 종목에는 지운 숫자마다 "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요." 를
# 보여요. 시계열을 고치는 일은 다음 PR 이에요.
def mark_px_bad(stocks, krs, cuts=None):
    """krSeries.jump 에 있는 국내 종목의 시계열 숫자를 비우고 pxBad · pxBadF 를 달아요 · krs["hidden"] = 표시한 종목 코드 (관문이 jump · 표시와 맞춰 봐요).
    2026-11-14 저녁 (Jack: "hide only the numbers whose calculation window includes the bad day"): 시계열 전체 칸(PX_BAD_ALWAYS)은 늘 비우고, 창이
    짧은 칸(PX_BAD_WIN: 252봉 hi · lo · mom · mz · 64봉 r3 · 22봉 r1)은 그 창의 첫 봉(cuts[코드][창], fetch_korea 가 px 에서 읽은 날짜) 이후에
    움직임 날짜가 하나라도 있을 때만 비워요. cuts 에 그 종목이 없으면 (있으면 안 돼요) 모두 비우고 크게 남겨요.
    pxBad = 가장 최근 움직임 날짜 · pxBadF = 비운 칸 목록 (PX_BAD_DATA 순서). stocks: fetch_korea 의 국내 종목 목록 · krs: kr_series_check 결과
    (그 자리에서 고쳐요). jump 에 있는데 목록에 없는 코드는 비울 숫자가 없어요 (크게 남겨요).
    반환: {"hidden": [코드…], "fields": {칸: 비운 종목 수}, "missing": [코드…], "f": {코드: [비운 칸…]}, "noCut": [코드…]}."""
    dates = collections.defaultdict(list)
    for j in (krs or {}).get("jump") or []:
        dates[str(j[0])].append(str(j[1])[:10])
    by = {s["t"]: s for s in stocks if s.get("cls") == "kr"}
    fields, hidden, fmap, no_cut = collections.Counter(), [], {}, []
    for s in by.values():
        s.pop("pxBad", None)                 # 표시는 오늘 실행의 jump 로만 (어제 것이 남지 않게)
        s.pop("pxBadF", None)
    for c in sorted(dates):
        s = by.get(c)
        if s is None:
            continue
        cut = (cuts or {}).get(c)
        if not cut:
            no_cut.append(c)
        hide = set(PX_BAD_ALWAYS)
        for w, ks in PX_BAD_WIN.items():
            if not cut or not cut.get(w) or any(d >= cut[w] for d in dates[c]):
                hide |= set(ks)
        f = [k for k in PX_BAD_DATA if k in hide]
        for k in f:
            if s.pop(k, None) is not None:
                fields[k] += 1
        s["pxBad"] = max(dates[c])
        s["pxBadF"] = f
        fmap[c] = f
        hidden.append(c)
    missing = sorted(set(dates) - set(hidden))
    if isinstance(krs, dict):
        krs["hidden"] = hidden
    full = [c for c in hidden if "hi" in fmap[c]]
    names = [f"{c} {by[c].get('nk', '')} ({by[c]['pxBad']}{'' if c in full else ' · 52주는 보여요'})" for c in hidden]
    log(f"{'  !! ' if hidden or missing else '· '}과거 주가 기록 오류(하루 가격 제한폭 넘는 움직임)로 숫자를 비운 국내 종목: "
        f"{len(hidden)}" + (f" (52주까지 {len(full)} · 52주는 보임 {len(hidden) - len(full)}) — {', '.join(names[:JUMP_LOG_SHOW])}"
                            + (f" 외 {len(names) - JUMP_LOG_SHOW}종목" if len(names) > JUMP_LOG_SHOW else "")
                            + f" · 비운 칸: {' · '.join(f'{k} {fields[k]}' for k in PX_BAD_DATA if fields[k])}"
                            + " (계산 창에 그 움직임이 든 칸만 · 점수와 순위는 그 칸 없이 · 앱은 그 자리에 Jack 의 줄을 보여요)" if hidden else "")
        + (f" · 목록에 없는 종목 {len(missing)}: {', '.join(missing[:JUMP_LOG_SHOW])} (비울 숫자가 없어요 — krSeries 뒤에 종목이 빠졌어요)" if missing else "")
        + (f" · 창을 모르는 종목 {len(no_cut)}: {', '.join(no_cut[:JUMP_LOG_SHOW])} (모두 비웠어요)" if no_cut else ""))
    return {"hidden": hidden, "fields": dict(fields), "missing": missing, "f": fmap, "noCut": no_cut}


def trend_rank_missing(kr_stocks, must=None):
    """추세(mz) · 저변동(lz) 점수가 없는 필수 종목 → [(코드, 이유)] (2026-11-14 · 관문의 '필수 종목 추세 · 저변동 순위' 줄과 같은 종목). (순수 함수)"""
    by = {s.get("t"): s for s in kr_stocks}
    out = []
    for t in (DIV_RANK_MUST if must is None else must):
        s = by.get(t)
        if s is None:
            out.append((t, "데이터에 없음"))
            continue
        gone = [k for k in ("mz", "lz") if _fin(s.get(k)) is None]
        if gone:
            out.append((t, f"{'·'.join(gone)} 없음" + (f" — 과거 주가 기록 오류 (pxBad {s['pxBad']})" if s.get("pxBad") else "")))
    return out


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


def stmt_cur_of(fin):
    """이 회사가 쓴 재무제표(사업보고서 · TTM 분기)가 원화가 아니면 그 통화, 아니면 None. (순수 함수)"""
    fin = fin or {}
    return fin.get("cur") or (fin.get("ttm") or {}).get("cur")


def not_won(s, fin):
    """금액을 원으로 믿을 수 없는 회사: 해외 기업(9…) 이거나 재무제표 통화가 원화가 아님 (v19.1f · 두산밥캣 USD). (순수 함수)"""
    return is_foreign_issuer(s.get("t")) or bool(stmt_cur_of(fin))


def blank_non_won(kr_stocks, fin_map):
    """v19.1f (리뷰 2026-11-08): 원화가 아닌 재무제표로 낸 국내 회사 — 해외 기업처럼 PER·PBR·EPS·BPS 를 비우고 (금액은 build_corp 가
    비워요) 회사와 통화를 크게 남겨요. ROE 도 비워요 (리뷰 4: 앱이 '실적 숫자는 아직 보여 드리지 않아요' 밑에 ROE 를 보여 주지 않게 ·
    퀄리티 점수 qz 도 그래서 안 매겨요). 배당(dps · dy)은 배당 표가 '(원)' 단위라 남겨요. 반환: ["코드 이름(통화)", …].
    해외 기업(9…)도 재무제표 통화가 원화가 아니면 ROE 를 비워요 (2026-11-09 시험 실행: build_corp 는 stmtCur 회사의 corp.json roe·qz 를
    비우는데 data.json 에는 해외 기업 19곳의 roe·qz 가 남아 관문의 두 줄이 어긋났어요 — 두 파일이 같게). 나머지는 blank_foreign_dart 가 해요."""
    hit, fr = [], []
    for s in kr_stocks:
        cur = stmt_cur_of(fin_map.get(s.get("t")))
        if s.get("cls") != "kr" or not cur:
            continue
        if is_foreign_issuer(s.get("t")):
            s.pop("roe", None)
            fr.append(s["t"])
            continue
        for k in FOREIGN_BLANK + ("roe",):
            s.pop(k, None)
        hit.append(f"{s['t']} {s.get('nk', '')}({cur})")
    log(f"{'  !! ' if hit else '· '}원화가 아닌 재무제표로 낸 국내 회사 {len(hit)}곳"
        + (f": {', '.join(sorted(hit))} — 금액·PER·PBR·EPS·BPS·ROE 를 비웠어요 (재무 신호도 비워요 · 배당은 남겨요)" if hit else ""))
    if fr:
        log(f"  !! 원화가 아닌 재무제표로 낸 해외 기업 {len(fr)}곳: ROE 도 비웠어요 (corp.json 과 같게 · 퀄리티 점수 없음)")
    return hit


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


# v19.1f (2026-11-08): EPS·BPS 의 기준. 2026-11-08 감사에서 연결 재무제표 30곳 중 23곳이 지배주주 순이익 줄을 못 읽어 EPS·PER 이
# 비지배지분까지 든 '전체' 순이익으로 계산됐어요 (LG에너지솔루션 EPS +345 · PER 977, 주주 몫은 손실 −1조 728억 · 회사 발표 EPS −4,585).
# 지배기업 소유주지분(자본)도 대부분 못 읽어 BPS·PBR 이 전체 자본이었어요 (한화에어로스페이스 16.8조 vs 주주 몫 9.7조).
# 이제 EPS 는 주주 몫(지배주주) 순이익, BPS 는 주주 몫 자본으로 계산하고, 어느 값을 썼는지 corp.json epsIn · bpsIn 에 남겨요 (영수증).
#   epsIn = {"ni": 억원, "b": 기준, "p": 기간, "sh": 주식 수}   bpsIn = {"eq": 억원, "b": 기준, "sh": 주식 수}
#   b: "o" 연결 재무제표의 지배주주 몫 · "s" 별도 재무제표 (비지배지분이 없어 전체 = 주주 몫) · "t" 연결인데 지배주주 줄이 없어
#      전체 값을 쓴 경우 (로그 · 관문 경고)
#   p: "ttm" 최근 4개 분기 (corp.json bq) · "fy" 사업보고서 한 해 (TTM 지배주주 순이익을 만들 수 없을 때 — 관문이 bq 와 함께 경고)
# 순서: TTM 지배주주 → 연간 지배주주 → (별도 재무제표 · 지배주주 줄 없는 연결) TTM 전체 → 연간 전체. 연결에서 기간보다 기준을 먼저
# 지켜요: EPS 는 정의상 주주 몫이에요 (전체 순이익이면 비지배지분이 큰 회사의 PER 이 크게 틀려요).
# 주식 수 (PER_SHARE_WITH_PREF — Jack 승인 2026-11-08): True = 보통주 + 같은 회사 상장 우선주 (지배주주 순이익·자본은 우선주 몫까지 들어
# 있어요. 회사가 발표하는 기본주당이익과 같은 방식: 삼성전자 2025 지배주주 순이익 44.26조 ÷ 약 67억 주 = 6,605원). False = 보통주만
# (v19.1f 전: 우선주가 있는 회사의 EPS·BPS 가 커 보여요 — 삼성전자 약 14%).
PER_SHARE_WITH_PREF = True
# data.json · corp.json 맨 위 epsBasis — 앱의 'PER·EPS 계산 방법을 고치는 중' 줄이 "owners" 를 보면 사라져요. 이 실행이 정말 주주 몫
# EPS 를 냈을 때만 "owners" (eps_basis_of): 국내 필수 종목이 모두 지배주주 몫(o) 또는 별도 재무제표(s)이고, EPS 가 있는 회사 중
# EPS_BASIS_MIN 이상이 o·s. 아니면 "mixed" — 관문이 실패로 막아요 (리뷰 2026-11-08: 상수로 쓰면 거짓 표시가 될 수 있어서).
EPS_BASIS = "owners"
EPS_BASIS_MIN = 0.95


def eps_basis_of(kr_stocks, mult_extra, must=None):
    """이 실행의 EPS 기준 → ("owners" | "mixed", 설명). (순수 함수)"""
    must = DIV_RANK_MUST if must is None else must
    b = {t: e["epsIn"]["b"] for t, e in mult_extra.items() if "epsIn" in e}
    have = {s["t"] for s in kr_stocks if s.get("cls") == "kr"}
    bad_must = [t for t in must if t in have and not is_foreign_issuer(t) and b.get(t) not in ("o", "s")]
    share = sum(1 for v in b.values() if v in ("o", "s")) / len(b) if b else 0.0
    ok = not bad_must and bool(b) and share >= EPS_BASIS_MIN
    why = (f"EPS 있는 회사 {len(b):,}곳 중 지배주주·별도 {share:.1%} (기준 {EPS_BASIS_MIN:.0%})"
           + (f" · 필수 종목 중 아닌 곳: {', '.join(bad_must)}" if bad_must else ""))
    return (EPS_BASIS if ok else "mixed"), why


def per_share_count(s, pref_shares):
    """EPS·BPS 를 나눌 주식 수: 보통주(shr) + (PER_SHARE_WITH_PREF 면) 같은 회사 상장 우선주. (순수 함수)"""
    shr = _fin(s.get("shr"))
    if not shr or shr <= 0:
        return None
    pref = sum(p for p in (_fin(x) for x in (pref_shares or {}).get(s["t"][:5], ())) if p and p > 0) if PER_SHARE_WITH_PREF else 0
    return int(round(shr + pref))


def _hyb_cut(h):
    """신종자본증권 dict → (뺄 값 억원, 어디 몫인지 알 수 없음). 없으면 (0, False). (순수 함수)"""
    if not h:
        return 0.0, False
    return (_fin(h.get("dist")) or 0.0), not h.get("ok", True)


def eps_source(fin):
    """EPS 에 쓸 순이익 → (억원, 기준 o·s·t, 기간 ttm·fy, how, 뺀 신종자본증권 분배 억원) 또는 None. 위 순서. how: o 는 지배주주 순이익을
    읽은 방법 (owners_profit 의 code · alt · cont · sum · minus · nci0 — TTM 은 세 보고서의 방법을 '+' 로), s 는 ofs, t 는 total.
    v19.1f (리뷰 2026-11-08): o · s 는 그 기간의 주주 몫 신종자본증권 분배를 빼요 (K-IFRS 기본주당이익과 같은 방식). 어디 몫인지 알 수 없는
    신종자본증권이 있으면 빼지 않고 기준을 t (how hybrid) 로 둬요 — 앱의 '고치는 중' 줄이 남아요. (순수 함수)"""
    _t = fin.get("ttm") or {}
    ofs = fin.get("fs") == "OFS"
    picks = []
    if not ofs:
        if _fin(_t.get("nio")) is not None:
            picks.append((_t["nio"], "o", "ttm", _t.get("nioHow") or fin.get("nioHow") or "code", _t.get("hyb")))
        elif _fin(fin.get("nio")) is not None:
            picks.append((fin["nio"], "o", "fy", fin.get("nioHow") or "code", fin.get("hyb")))
    if not picks:
        b, how = ("s", "ofs") if ofs else ("t", "total")
        if _fin(_t.get("ni")) is not None:
            picks.append((_t["ni"], b, "ttm", how, _t.get("hyb")))
        else:
            ni0 = _fin((fin.get("ni") or [None])[0])
            if ni0 is not None:
                picks.append((ni0, b, "fy", how, fin.get("hyb")))
    if not picks:
        return None
    ni, b, p, how, h = picks[0]
    if b == "t":
        return ni, b, p, how, 0.0
    cut, unplaced = _hyb_cut(h)
    if unplaced:
        return ni, "t", p, "hybrid", 0.0
    return round(ni - cut, 1), b, p, how, cut


def eps_nci(fin, p):
    """EPS 순이익을 가져온 재무제표에 비지배지분(소수주주)이 있는지 — 증거 nciBs · nciPl 중 하나가 0 이 아닌 값이면 True. (순수 함수)
    p "ttm": 최신 분기의 증거 먼저 — 재무상태표(bs2.nciBs) 나 분기 누적 손익(ttm.nciPl) 중 하나라도 0 이 아니면 (두 칸이 다 없으면 사업보고서) ·
    "fy": 사업보고서. 앱이 '전체 순이익으로 계산했어요' 줄에 써요 (epsIn.nci)."""
    ann = (fin.get("nciBs"), fin.get("nciPl"))
    if p == "ttm":
        _b, _t = fin.get("bs2") or {}, fin.get("ttm") or {}
        if "nciBs" in _b or "nciPl" in _t:
            ann = (_b.get("nciBs"), _t.get("nciPl"))
    return any(_fin(v) not in (None, 0.0) for v in ann)


def _owners_eq(src, ofs):
    """재무상태표 하나(src: bs2 또는 사업보고서)의 주주 몫 자본 → (억원, 기준, how) 또는 None. (순수 함수)
    연결: 지배주주 자본 줄(code) → 그 줄이 없고 비지배지분 줄이 있으면 자본총계 − 비지배지분 (minus · 리뷰 3: DH오토넥스 ·
    삼기에너지솔루션즈) → 비지배지분 줄이 없거나 0 이면 자본총계 (nci0)."""
    if not ofs:
        if _fin(src.get("eqo")) is not None:
            return src["eqo"], "o", "code"
        if "nciBs" in src and _fin(src.get("eq")) is not None:
            nci = _fin(src.get("nciBs"))
            if nci in (None, 0.0):
                return src["eq"], "o", "nci0"
            return round(src["eq"] - nci, 1), "o", "minus"
        return None
    return (src["eq"], "s", "ofs") if _fin(src.get("eq")) is not None else None


def bps_source(fin):
    """BPS 에 쓸 자본 → (억원, 기준 o·s·t, how, 시점 p, 뺀 신종자본증권 억원) 또는 None. 순서는 재무상태표마다예요 — 최신 분기(bs2)
    먼저, 없으면 사업보고서 — 그 재무상태표로 주주 몫 자본을 정확히 알 수 있으면 그 값 (_owners_eq: 지배주주 자본 줄 code → 자본총계 −
    비지배지분 minus → 비지배지분이 없는 연결의 자본총계 nci0). 셋 다 정확한 값이라 시점을 먼저 지켜요 (리뷰 3: 최신 분기로 정확히 알 수
    있는데 사업보고서 값을 쓰면 PBR 이 낡아요). 어느 재무상태표로도 안 되면 전체 자본 (s: ofs · t: total).
    p: "ttm" = 최신 분기(bq) 재무상태표(bs2)의 자본 · "fy" = 사업보고서의 자본 (리뷰 2026-11-08: 앱의 'PBR 은 그 분기 자본 기준' 줄이
    사업보고서 자본일 때 틀리지 않게). v19.1f (리뷰): o · s 는 그 재무상태표의 주주 몫 신종자본증권을 빼요 (보통주 자본) · 어디 몫인지
    모르면 빼지 않고 t (how hybrid). (순수 함수)"""
    _b = fin.get("bs2") or {}
    ofs = fin.get("fs") == "OFS"
    for src, p in ((_b, "ttm"), (fin, "fy")):
        got = _owners_eq(src, ofs)
        if got:
            eq, b, how = got
            h = src.get("hyb")
            if h and not h.get("ok", True):
                return eq, "t", "hybrid", p, 0.0
            cut = (_fin((h or {}).get("eq")) or 0.0)
            return round(eq - cut, 1), b, how, p, cut
    for src, p in ((_b, "ttm"), (fin, "fy")):
        if _fin(src.get("eq")) is not None:
            return src["eq"], ("s" if ofs else "t"), ("ofs" if ofs else "total"), p, 0.0
    return None


def annual_only(fin):
    """사업보고서 값만 남긴 재무 dict (TTM ttm · 최신 분기 재무상태표 bs2 를 뺌). (순수 함수)"""
    return {k: v for k, v in (fin or {}).items() if k not in ("ttm", "bs2")}


def hybrid_net_series(fin, b):
    """v19.1f (리뷰 3): 신종자본증권 분배를 뺀 3년 주주 몫 순이익 [fy, fy−1, fy−2] (억원) — 그 해 분배를 모르면(자본변동표에 그 해 칸이
    없음) None ('자료가 없어요'). EPS 기준 b 가 o 면 nio3, s(별도)면 ni 에서 빼요. 사업보고서에 주주 몫 신종자본증권이 없거나 (hyb 없음 ·
    어디 몫인지 모름) 세 해 모두 분배가 0 이면 None (그대로 둬요). (순수 함수)"""
    h = fin.get("hyb") or {}
    d3 = h.get("dist3")
    if b not in ("o", "s") or not h.get("ok", True) or not isinstance(d3, list) or len(d3) != 3:
        return None
    if all(x == 0 for x in d3):
        return None
    base = fin.get("nio3") if b == "o" else fin.get("ni")
    if not isinstance(base, list) or len(base) != 3:
        return None
    return [round(v - d, 1) if (_fin(v) is not None and _fin(d) is not None) else None for v, d in zip(base, d3)]


def roe_source(fin):
    """v19.1f (리뷰 2026-11-08): ROE 를 EPS 와 같은 기준(주주 몫)으로 → (%, 순이익 억원, 자본 억원, 기준 o·s, 기간 "fy") 또는 None.
    순이익은 EPS 와 같은 순서·규칙 (eps_source: 지배주주 → 별도 · 신종자본증권 분배를 뺌), 자본은 같은 재무상태표의 주주 몫 자본
    (bps_source 규칙 · 신종자본증권 뺌). 기간은 늘 사업보고서 한 해끼리 — 앱이 ROE 를 '○○년 사업보고서 기준'으로 적고 2.0 의 ROE 하한
    규칙도 그 해(fy)로 비교해서예요 (TTM 이면 꼬리표가 틀려요). 지배주주 순이익이 없는 연결(t)·주주 몫 자본이 없거나 0 이하면 None —
    예전 값(parse_dart_list: 연결 전체 순이익 ÷ 전체 자본, 같은 사업보고서)을 그대로 둬요. (순수 함수)"""
    fy = annual_only(fin)
    es = eps_source(fy)
    if es is None or es[1] == "t":
        return None
    bs = bps_source(fy)
    if bs is None or bs[1] != es[1] or bs[3] != "fy" or bs[0] <= 0:
        return None
    return round(es[0] / bs[0] * 100, 1), es[0], bs[0], es[1], "fy"


ROE_RULE_LINES = (5.0, 10.0, 15.0)     # 'ROE ≥ x%' 규칙이 갈리는지 세는 선 (로그만 · Jack 2026-11-08)


def roe_moves(kr_stocks, old_roe):
    """v19.1f (리뷰 · Jack 2026-11-08): ROE 기준을 바꿔 움직인 것. (순수 함수 · 로그용)
    old_roe = {코드: fill_multiples 전 roe}. 셈: 1%p 넘게 바뀐 곳 · 부호가 바뀐 곳 · 퀄리티 점수(qz — add_percentiles 와 같게 예전 ROE 로
    한 번 더 매겨 견줘요) 바뀐 곳과 5점 이상 · 'ROE ≥ 5 · 10 · 15%' 의 답이 바뀐 곳 · 2.0 ROE 하한(예전 ROE 로 산 사람의 하한
    roeFloorFor = max(0, floor(roe/2)) · roe > 0 일 때만)보다 새 ROE 가 낮아진 곳."""
    kr = [s for s in kr_stocks if s.get("cls") == "kr"]
    old = add_percentiles([{"cls": "kr", "roe": old_roe.get(s["t"])} for s in kr])
    out = {"changed": [], "big": [], "sign": [], "qz": 0, "qz5": [], "floor": [], "new": 0, "gone": 0,
           "line": {x: [] for x in ROE_RULE_LINES}}
    for s, o in zip(kr, old):
        a, b = _fin(old_roe.get(s["t"])), _fin(s.get("roe"))
        nm = f"{s['t']} {s.get('nk', '')}".strip()
        if a is None and b is not None:
            out["new"] += 1
        elif a is not None and b is None:
            out["gone"] += 1
        elif a is not None and abs(a - b) >= 0.05:
            out["changed"].append(nm)
            if abs(a - b) > 1.0:
                out["big"].append(f"{nm} {a:+.1f}→{b:+.1f}")
            if (a > 0) != (b > 0):
                out["sign"].append(f"{nm} {a:+.1f}→{b:+.1f}")
            if a > 0 and b < max(0, math.floor(a / 2)):
                out["floor"].append(f"{nm} {a:.1f}→{b:.1f}")
            for x in ROE_RULE_LINES:
                if (a >= x) != (b >= x):
                    out["line"][x].append(f"{nm} {a:.1f}→{b:.1f}")
        if s.get("qz") != o.get("qz"):
            out["qz"] += 1
            if s.get("qz") is not None and o.get("qz") is not None and abs(s["qz"] - o["qz"]) >= 5:
                out["qz5"].append(f"{nm} {o['qz']}→{s['qz']}")
    log(f"{'  !! ' if out['floor'] else '· '}ROE 기준 (주주 몫 · 사업보고서) 으로 움직인 것: 바뀐 곳 {len(out['changed']):,} (1%p 넘게 "
        f"{len(out['big']):,}) · 부호가 바뀐 곳 {len(out['sign'])} · 새로 생김 {out['new']} · 빠짐 {out['gone']} · 퀄리티 점수(qz) 바뀐 곳 "
        f"{out['qz']:,} (5점 이상 {len(out['qz5']):,}) · 'ROE ≥ x%' 답이 바뀐 곳 "
        + " · ".join(f"{x:g}% {len(v)}" for x, v in out["line"].items())
        + f" · 2.0 ROE 하한(예전 ROE 의 절반) 아래로 내려간 곳 {len(out['floor'])}"
        + (f": {', '.join(out['floor'][:12])}{'…' if len(out['floor']) > 12 else ''}" if out["floor"] else ""))
    if out["sign"]:
        log(f"  · ROE 부호가 바뀐 곳: {', '.join(out['sign'][:20])}{'…' if len(out['sign']) > 20 else ''}")
    if out["big"]:
        log(f"  · ROE 가 1%p 넘게 바뀐 곳 (앞 20): {', '.join(out['big'][:20])}{'…' if len(out['big']) > 20 else ''}")
    return out


def fill_multiples(kr_stocks, fin_map, pref_shares=None):
    """DART 재무(순이익·자본) + 주식 수로 EPS/BPS/PER/PBR을 직접 계산합니다.
    pykrx는 KRX 로그인이 필요해져 CI에서 동작하지 않으므로, 있으면 쓰고 없으면 이 값으로 채웁니다.
    v19.1f: 순이익·자본은 지배주주 몫 (eps_source · bps_source), 주식 수는 per_share_count. 반환: {코드: {"epsIn", "bpsIn"}} —
    corp.json 에 싣는 영수증 (이 함수가 채운 값만)."""
    n = 0
    extra = {}
    cnt = collections.Counter()
    tot_b, fy_q, bps_fy_q, hyb_cut, hyb_t, roe_n, roe_gap, hyb_net = [], [], [], [], [], collections.Counter(), [], []
    top = {s["t"] for s in sorted((x for x in kr_stocks if x.get("cls") == "kr"), key=lambda x: -(_fin(x.get("cap")) or 0))[:200]}
    for s in kr_stocks:
        fin = fin_map.get(s["t"])
        price = s.get("price")
        sh = per_share_count(s, pref_shares)
        if fin and not not_won(s, fin):
            rs = roe_source(fin)
            if rs is not None:                     # v19.1f (리뷰): ROE 도 EPS 와 같은 기준 (주주 몫 ÷ 주주 몫 자본 · 사업보고서 한 해)
                s["roe"] = rs[0]
                extra.setdefault(s["t"], {})["roeIn"] = {"ni": rs[1], "eq": rs[2], "b": rs[3], "p": rs[4]}
                roe_n[rs[3]] += 1
            else:
                roe_n["old"] += 1
        if not fin or not sh or not price or not_won(s, fin):     # v17.5.2 · v19.1f: 금액이 원화가 아닐 수 있으면 건너뛰어요
            continue
        es, bs_ = eps_source(fin), bps_source(fin)
        nm = f"{s['t']} {s.get('nk', '')}".strip()
        if es is not None and s.get("eps") is None:
            ni, b, p, how, cut = es
            eps = ni * 1e8 / sh
            s["eps"] = round(eps, 0)
            if s.get("per") is None and eps > 0:
                s["per"] = round(price / eps, 1)
            extra.setdefault(s["t"], {})["epsIn"] = {"ni": ni, "b": b, "p": p, "sh": sh, "how": how, **({"hyb": cut} if cut else {}),
                                                     **({"nci": True} if b == "t" and how == "total" and eps_nci(fin, p) else {})}
            # nci 는 how "total" (지배주주 줄이 없어 전체 순이익) 에만: how "hybrid" 는 지배주주 순이익이 있어요 — 앱의 '따로 공시하지 않아' 줄이 틀려요
            if b == "t" and how == "total":
                cnt[f"eps:t:nci:{'y' if eps_nci(fin, p) else 'n'}"] += 1
            if cut:
                hyb_cut.append(nm)
            if how == "hybrid":
                hyb_t.append(nm)
            cnt[f"eps:{b}:{p}"] += 1
            if b in ("o", "s") and "roeIn" not in extra[s["t"]] and _fin(s.get("roe")) is not None:
                roe_gap.append(nm)          # EPS 는 주주 몫인데 ROE 는 예전 값 (사업보고서에 주주 몫 자본·순이익이 없음) — 앱의 '고치는 중' 줄은 사라져요
            # v19.1f (리뷰): 사업보고서 한 해 EPS (같은 주식 수) 와 재무제표의 기본주당이익 — 관문이 견줘요 (경고만)
            fy = eps_source(annual_only(fin))
            if fy and fy[1] in ("o", "s"):
                extra[s["t"]]["epsFy"] = round(fy[0] * 1e8 / sh, 0)
            if _fin(fin.get("epsRep")) is not None:
                extra[s["t"]]["epsRep"] = fin["epsRep"]
            net = hybrid_net_series(fin, b)
            if net is not None:             # v19.1f (리뷰 3): 역DCF · 주가 분해가 EPS 와 같은 순이익을 쓰게 (src/repair.js epsBase)
                extra[s["t"]]["nio3"], extra[s["t"]]["nio3Hyb"] = net, fin["hyb"]["dist3"]
                hyb_net.append(nm)
            for h in how.split("+"):
                cnt[f"how:{h}"] += 1
            if b == "t" and s["t"] in top:
                tot_b.append(nm)
            if p == "fy" and fin.get("bq"):
                fy_q.append(nm)
        if bs_ is not None and bs_[0] > 0 and s.get("bps") is None:
            eq, b, bhow, bp, bcut = bs_
            bps = eq * 1e8 / sh
            s["bps"] = round(bps, 0)
            if s.get("pbr") is None:
                s["pbr"] = round(price / bps, 2)
            extra.setdefault(s["t"], {})["bpsIn"] = {"eq": eq, "b": b, "sh": sh, "how": bhow, "p": bp, **({"hyb": bcut} if bcut else {})}
            cnt[f"bps:{b}"] += 1
            if bp == "fy" and fin.get("bq"):
                bps_fy_q.append(f"{s['t']} {s.get('nk', '')}".strip())
        if s.get("per") is not None or s.get("pbr") is not None:
            n += 1
    n_pref = sum(1 for t, e in extra.items() if "epsIn" in e and pref_shares and pref_shares.get(t[:5]) and PER_SHARE_WITH_PREF)
    log(f"· 멀티플 직접 계산: {n:,}건 (DART 재무 × 주식 수 · 주식 수에 상장 우선주 포함 {'켬' if PER_SHARE_WITH_PREF else '끔'}"
        f"(PER_SHARE_WITH_PREF) — 우선주가 있는 회사 {n_pref:,}곳)")
    log(f"· EPS 순이익 기준: 지배주주 TTM {cnt['eps:o:ttm']:,} · 지배주주 연간 {cnt['eps:o:fy']:,} · 별도 TTM {cnt['eps:s:ttm']:,} · "
        f"별도 연간 {cnt['eps:s:fy']:,} · 연결 전체(지배주주 줄 없음) TTM {cnt['eps:t:ttm']:,} · 연간 {cnt['eps:t:fy']:,} (그중 how total 에서 소수주주 있음 epsIn.nci {cnt['eps:t:nci:y']:,} · 없음 {cnt['eps:t:nci:n']:,}) | BPS 자본 기준: "
        f"지배주주 {cnt['bps:o']:,} · 별도 {cnt['bps:s']:,} · 연결 전체 {cnt['bps:t']:,}")
    log("· 지배주주 순이익을 읽은 방법 (EPS 가 지배주주인 회사 · TTM 은 세 보고서 방법을 모두 세요): "
        + " · ".join(f"{h} {cnt['how:' + h]:,}" for h in OWN_HOWS))
    if tot_b:
        log(f"  !! 시가총액 상위 200곳 중 연결인데 지배주주 순이익 줄이 없어 전체 순이익으로 EPS 를 낸 곳 {len(tot_b)}: "
            f"{', '.join(tot_b[:20])}{'…' if len(tot_b) > 20 else ''}")
    if fy_q:
        log(f"  !! TTM(bq) 이 있는데 EPS 는 사업보고서 한 해 지배주주 순이익인 곳 {len(fy_q)} (분기 지배주주 줄이 없음 · epsIn.p fy): "
            f"{', '.join(fy_q[:20])}{'…' if len(fy_q) > 20 else ''}")
    log(f"· ROE 기준 (EPS 와 같은 주주 몫 · 사업보고서 한 해 · roeIn): 지배주주 {roe_n['o']:,} · 별도 {roe_n['s']:,} · 예전 그대로 "
        f"{roe_n['old']:,} (지배주주 순이익이나 주주 몫 자본이 없는 연결 — 전체 순이익 ÷ 전체 자본)")
    log(f"{'  !! ' if roe_gap else '· '}EPS 는 주주 몫인데 ROE 는 예전 값(전체 ÷ 전체)인 곳 {len(roe_gap)}"
        + (f": {', '.join(roe_gap[:20])}{'…' if len(roe_gap) > 20 else ''}" if roe_gap else ""))
    log(f"{'  !! ' if hyb_t else '· '}신종자본증권: 주주 몫 분배를 EPS 에서 뺀 곳 {len(hyb_cut)}"
        + (f" ({', '.join(hyb_cut[:12])}{'…' if len(hyb_cut) > 12 else ''})" if hyb_cut else "")
        + f" · 어디 몫인지 알 수 없어 '전체'(t)로 둔 곳 {len(hyb_t)}" + (f": {', '.join(hyb_t[:12])}" if hyb_t else "")
        + f" · corp.json nio3 를 분배를 뺀 값으로 쓴 곳 {len(hyb_net)} (nio3Hyb · 별도 재무제표(s)면 ni 대신 이 nio3 가 EPS 기준)")
    # v19.1f (리뷰 2026-11-08): BPS 도 같은 숫자 — 분기(bq) 표시인데 자본은 사업보고서 것인 곳 (bpsIn.p fy · 앱은 그 기간으로 적어요)
    log(f"{'  !! ' if bps_fy_q else '· '}TTM(bq) 이 있는데 BPS 는 사업보고서 자본인 곳 {len(bps_fy_q)} (최신 분기 재무상태표에 쓸 자본이 없음 · "
        f"bpsIn.p fy)" + (f": {', '.join(bps_fy_q[:20])}{'…' if len(bps_fy_q) > 20 else ''}" if bps_fy_q else ""))
    return extra


def income_check(kr_stocks, fin_map, mult_extra):
    """v19.1f: data.json incCheck — 관문이 corp.json 과 맞춰 보는 집계. (순수 함수)
    stmts 재무제표를 읽은 회사 · noInc 그중 매출·영업이익·순이익이 모두 빈 곳 · finNoRev 매출 줄이 없는 금융회사(incNa) ·
    eps 기준·기간별 수 (epsIn)."""
    kr = [s for s in kr_stocks if s.get("cls") == "kr" and s["t"] in fin_map and not is_foreign_issuer(s["t"])]
    def blank(fin, k):
        return (fin.get(k) or [None])[0] is None
    no_inc = [s["t"] for s in kr if all(blank(fin_map[s["t"]], k) for k in ("rev", "op", "ni"))]
    fin_no_rev = [s["t"] for s in kr if fl_financial(s) and blank(fin_map[s["t"]], "rev")]
    eb = collections.Counter(e["epsIn"]["b"] for e in mult_extra.values() if "epsIn" in e)
    ep = collections.Counter(e["epsIn"]["p"] for e in mult_extra.values() if "epsIn" in e)
    return {"v": 1, "stmts": len(kr), "noInc": len(no_inc), "finNoRev": len(fin_no_rev),
            "epsB": {k: eb[k] for k in ("o", "s", "t")}, "epsP": {k: ep[k] for k in ("ttm", "fy")}}


# ────────────────────────────────────────────────────────────
# 공시 단위 확인 (Jack, 2026-11-13): 단위를 잘못 적은 재무제표
# ────────────────────────────────────────────────────────────
# 2026-11-12 발행본에서 진코스텍(250030)과 디와이에이(002880)의 PER·PBR 이 0.0, 가치 점수가 100 이었어요. 두 회사의 2026 반기보고서는
# 재무제표 표 머리에 '(단위 : 천원)'이라 적었지만 숫자는 원이었고 (같은 보고서의 요약재무정보는 원·백만원), DART 자료(OpenDART)는 그 보고서의
# 모든 금액을 정확히 1,000배로 담고 있어요 (그 보고서의 2025-12-31 칸 = 2025 사업보고서 값 × 1,000). API 에는 단위 칸이 없어요 (금액은
# 언제나 원). 보고서 전체가 같은 배율이라 그 보고서 안에서는 자산 = 부채 + 자본 이 그대로 맞아요. 그래서 실행마다 국내 회사 모두를 두 가지로
# 봐요 (캐시에 있는 값으로 · DART 호출 없이):
#   bs     자산 ≠ 부채 + 자본: 읽은 재무제표(사업보고서 · 최신 분기 · 지난해 같은 분기) 중 하나라도 |자산 − (부채 + 자본)| 이
#          max(자산 × UNIT_BAL_REL, UNIT_BAL_ABS 원) 보다 커요. 맞는 재무제표는 원 단위까지 맞아요 (2025 사업보고서·반기 753개 모두 차이 0) —
#          천원·백만원으로 낸 표는 총계마다 따로 반올림해 몇 단위 어긋날 수 있어 300만원까지 봐줘요. 한 줄(한 표)만 단위가 틀리면 99.9% 넘게
#          어긋나요. 자산총계는 2026-11-13 부터 읽어요 (balance_totals → bal): 그 전에 캐시에 저장된 재무제표는 '확인 못 함'으로 세요
#          (90일 재확인 · 다시 읽기로 채워져요).
#   scale  보고서 사이 배율: TTM 에 쓴 분기 보고서(최신 분기 bs2 · 지난해 같은 분기 bsP)의 재무상태표가 사업보고서 것의 UNIT_SCALE_MAX 배
#          이상이거나 1/UNIT_SCALE_MAX 이하. 자본총계 · 유동자산 · 유동부채 · 자본금 · 현금 중 두 보고서 모두 양수인 칸들의 배율 중앙값이에요
#          (한 칸의 진짜 큰 변화 — 자본잠식에서 증자한 회사 — 로 걸리지 않게). 2026-11-12 발행본 2,234곳의 최신 분기 주주 몫 자본 ÷
#          사업보고서 것: 진짜 회사는 0.08~14.4배, 두 회사는 1,390 · 1,405배. 천원·백만원을 원으로 읽으면 1,000 · 1,000,000배예요.
#   is · cf  손익계산서 · 현금흐름표: 최신 분기 보고서에 적힌 지난해 같은 기간 누적 칸(p0)이 지난해 같은 분기 보고서의 누적 값의 UNIT_SCALE_MAX
#          배 이상이거나 1/UNIT_SCALE_MAX 이하 (매출 · 순이익의 중앙값 / 영업현금흐름). 같은 숫자라 맞는 보고서는 1배예요 (정정공시면 조금 달라요).
#          재무상태표는 맞고 손익계산서만 단위가 틀린 보고서를 잡아요 (리뷰 #116). 이 칸은 2026-11-13 부터 읽어요 (캐시의 예전 항목은 못 봐요).
#   eps    재무제표에 회사가 적은 기본주당이익(원)은 표의 단위를 잘못 적어도 그대로예요 (진코스텍 · 디와이에이 2026 반기 1,061원 · 385원).
#          주주 몫 순이익 ÷ 오늘 주식 수가 그 값의 UNIT_ANCHOR_MAX 배 이상이거나 1/UNIT_ANCHOR_MAX 이하면 (사업보고서 · 최신 분기 · 지난해 같은
#          분기 · 같은 부호 · 기본주당이익이 UNIT_EPS_MIN 원 이상일 때만). 사업보고서는 캐시에 이미 있는 값이라(epsRep) 분기 보고서가 없는
#          회사(3~5월 · 사업보고서만 있는 회사)도 봐요. 300 배: 2026-11-12 발행본 2,128곳에서 진짜 회사는 0.010배(송우인포텍 · 합병 뒤
#          주식 수) ~ 48배(아이에이 · 병합) — 주식 수 변화예요. 단위를 잘못 적으면 1,000 · 1,000,000 배예요.
#   cap    자본금 ÷ 액면가(배당 표 · 원) = 그해 말 발행 주식 수의 상한이 오늘 주식 수의 UNIT_ANCHOR_MAX 배 이상이거나 1/… 이하 (납입자본으로
#          읽은 자본금은 주식발행초과금이 섞여 빼요). 사업보고서 재무상태표의 단위를 봐요. 액면가가 없거나 0 · '-' 인 회사(무액면주식), 100원
#          미만(UNIT_PAR_MIN · 한국 상장사에 없는 값 — 손으로 적다 틀린 '5.000' 같은 값)인 회사는 안 봐요.
#   eps · cap 은 금액이 원일 때만 (리뷰 #118): 재무제표를 원화가 아닌 통화로 낸 회사(not_won — stmtCur · 해외 기업 9…)는 금액(달러 등)과
#          원으로 적힌 액면가 · 주식 수를 맞대면 안 돼요 (두산밥캣 · 아남전자: 자본금 0.4억 달러 ÷ 500원 → 0.0009배로 잘못 걸렸어요).
#          그런 회사는 bs · scale · is · cf (같은 통화끼리의 비) 만 봐요. 몇 곳인지 unitChkCover.notWon.
# 걸린 회사는 재무제표로 만든 숫자를 모두 비워요 (0 이 아니라 빈 칸 · 어느 재무제표가 맞는지 이 확인만으로는 알 수 없어서): data.json ·
# corp.json 의 UNIT_BLANK, corp.json 의 3개년 금액 · 자본 · UNIT_BLANK_CORP (영수증 · EV 배수 · 재무 경고) · DCF 입력. 가치(vz) · 퀄리티(qz)
# 점수는 add_percentiles 가 빈 칸을 빼고 매겨요 (다른 회사의 순위도 그 회사 없이). 배당(배당 표 — 금액마다 단위가 적힌 별도 표, 원)은 남겨요.
# 두 파일의 unitChk = 걸린 이유 목록 (UNIT_WHY) — 앱이 "공시 자료의 단위를 확인하고 있어서 이 숫자를 잠시 비워 두었어요." 를 보여요.
# PBR 이 UNIT_PBR_LOOK 미만인데 둘 다 아니면 비우지 않고 회사 이름과 증거를 로그로 남겨요 (관문은 그런 회사를 경고로 적어요).
UNIT_BAL_REL = 0.001             # 자산의 0.1%
UNIT_BAL_ABS = 3e6               # 원 (천원·백만원 표의 반올림)
UNIT_SCALE_MAX = 100.0           # 보고서 사이 배율 (이 배 이상 · 이 분의 1 이하면 단위가 다른 보고서)
UNIT_SCALE_KEYS = ("eq", "ca", "cl", "cs", "cash")
UNIT_PBR_LOOK = 0.1              # 이보다 낮은 PBR 은 걸리지 않았어도 이름을 남겨요
UNIT_ANCHOR_MAX = 300.0          # 기본주당이익 · 자본금 ÷ 액면가 기준값과의 차이 (위 eps · cap)
UNIT_EPS_MIN = 10.0              # 원 — 이보다 작은 기본주당이익은 견주지 않아요 (반올림 · 신종자본증권 분배로 비가 흔들려요)
UNIT_PAR_MIN = 100.0             # 원 — 한국 상장사 액면가는 100원 아래가 없어요 (상법). 그 아래 값은 손으로 적다 틀린 값('5.000' → 5원)이라
#                                  견주지 않아요 (리뷰 #118 3차 S-B: 맞는 회사가 1,000배로 보여 비워져요) — 몇 곳인지 로그에 남겨요
UNIT_CHK_KEYS = ("rev", "ni", "nio", "ocf", "epsYtd", "p0")   # compute_ttm 이 분기 보고서마다 넘기는 손익 쪽 기준값
UNIT_WHY = ("bs", "scale", "is", "cf", "eps", "cap")
UNIT_BLANK = ("per", "pbr", "eps", "bps", "roe", "debt", "opm", "g3")      # data.json 종목 · corp.json 회사 모두 빈 칸
UNIT_BLANK_CORP = ("evE", "evR", "pcf", "bq", "nio3", "nio3Hyb", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "fl", "flSrc", "flWhy")
UNIT_EXTRA_KEYS = ("epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "nio3", "nio3Hyb")    # fill_multiples 의 영수증 (corp.json 으로 가요)
UNIT_KO = {"bs": "자산≠부채+자본", "scale": "보고서 사이 배율", "is": "손익계산서 지난해 칸", "cf": "현금흐름표 지난해 칸",
           "eps": "기본주당이익", "cap": "자본금 ÷ 액면가"}
UNIT_SRC_KO = {"fy": "사업보고서", "q": "최신 분기", "qp": "지난해 같은 분기"}


def bal_off(bal):
    """[자산, 부채, 자본] (원) → 맞으면 0.0, 맞지 않으면 어긋난 비율 (|자산 − (부채 + 자본)| ÷ |자산|, 자산이 0 이면 1.0), 모르면 None. (순수 함수)"""
    if not isinstance(bal, (list, tuple)) or len(bal) != 3 or any(_fin(x) is None for x in bal):
        return None
    a, li, e = (float(x) for x in bal)
    gap = abs(a - (li + e))
    if gap <= max(abs(a) * UNIT_BAL_REL, UNIT_BAL_ABS):
        return 0.0
    return gap / abs(a) if a else 1.0


def stmt_scale(q, a, keys=UNIT_SCALE_KEYS):
    """재무상태표 q 가 a 의 몇 배인지 (억원 칸들) — 두 쪽 모두 양수인 칸의 배율 중앙값 (로그로), 칸이 없으면 None. (순수 함수)"""
    logs = sorted(math.log10(q[k] / a[k]) for k in keys
                  if (_fin((q or {}).get(k)) or 0.0) > 0 and (_fin((a or {}).get(k)) or 0.0) > 0)
    if not logs:
        return None
    m = len(logs) // 2
    return 10 ** (logs[m] if len(logs) % 2 else (logs[m - 1] + logs[m]) / 2)


def _ratio(a, b, floor=0.0):
    """|a ÷ b| — 둘 다 0 이 아니고 부호가 같고 |b| ≥ floor 일 때만, 아니면 None. (순수 함수)"""
    a, b = _fin(a), _fin(b)
    if a is None or b is None or a == 0 or b == 0 or (a > 0) != (b > 0) or abs(b) < floor:
        return None
    return abs(a / b)


def _off(r, lim):
    return r is not None and (r >= lim or r <= 1.0 / lim)


def _median_ratio(pairs, floor=0.0):
    """[(a, b)] 의 |a ÷ b| 중앙값 (로그로 · 쓸 수 있는 쌍만), 없으면 None. (순수 함수)"""
    logs = sorted(math.log10(r) for a, b in pairs if (r := _ratio(a, b, floor)) is not None)
    if not logs:
        return None
    m = len(logs) // 2
    return 10 ** (logs[m] if len(logs) % 2 else (logs[m - 1] + logs[m]) / 2)


def cap_ratio(s, fin, pref_shares=None):
    """자본금 ÷ 액면가(그해 말 발행 주식 수의 상한) ÷ 오늘 주식 수 (cap 기준값) 또는 None. 자본금은 parse_capital(_cap) — 없으면 재무제표의
    '자본금'(cs3) — 이고 납입자본(src paid)은 빼요. 액면가는 배당 표(_bas par3, 원) — par_value: 없거나 0 · '-' (무액면주식) · 100원 미만
    (손으로 적다 틀린 값)이면 None. 보통주만의 자본금이면 보통주 수와. 원화가 아닌 재무제표(not_won)면 None (리뷰 #118 — 달러 자본금 ÷ 원
    액면가). (순수 함수)"""
    if not_won(s, fin):
        return None
    cap = s.get("_cap") if isinstance(s.get("_cap"), dict) else None
    if cap and cap.get("src") == "paid":
        return None
    cs3 = (cap or {}).get("cs3") or (fin or {}).get("cs3")
    cs = _fin((cs3 or [None])[0])
    par = par_value(s)
    if not cs or not par or cs <= 0:
        return None
    shares = _fin(s.get("shr")) if (cap or {}).get("k") == "common" else per_share_count(s, pref_shares)
    return _ratio(cs * 1e8 / par, shares)


def par_raw(s):
    """배당 표의 당기 액면가 (원 · 숫자로 읽힌 그대로) 또는 None. (순수 함수)"""
    return _fin((((s or {}).get("_bas") or {}).get("par3") or [None])[0])


def par_value(s):
    """자본금 ÷ 액면가에 쓸 액면가 (원): 없거나 0 · '-' (무액면주식)이면 None, UNIT_PAR_MIN(100원) 미만이면 None (한국 상장사에 없는 값 —
    손으로 적다 틀린 '5.000' · '0.5' · '5'). (순수 함수)"""
    par = par_raw(s)
    return par if par is not None and par >= UNIT_PAR_MIN else None


def unit_check(fin, sh=None, cap=None):
    """회사 하나의 재무(fin_map 값) → {"why": [UNIT_WHY…], "bal": {보고서: bal_off}, "scale": {보고서: 배율}, "flows": {is · cf: 배율},
    "eps": {보고서: 배율}, "cap": 배율}. sh = EPS 주식 수 (per_share_count) · cap = cap_ratio. (순수 함수)
    보고서: fy 사업보고서(fin) · q 최신 분기(bs2 · qChk.q) · qp 지난해 같은 분기(bsP · qChk.qp). 그 보고서가 없으면 칸이 없어요 · 값을 모르면 None."""
    fin = fin or {}
    srcs = {"fy": fin, "q": fin.get("bs2") or {}, "qp": fin.get("bsP") or {}}
    bal = {k: bal_off(v.get("bal")) for k, v in srcs.items() if v}
    scale = {k: stmt_scale(srcs[k], fin) for k in ("q", "qp") if srcs[k]}
    chk = fin.get("qChk") or {}
    q, qp = chk.get("q") or {}, chk.get("qp") or {}
    flows = {}
    if isinstance(q.get("p0"), dict) and qp:
        flows["is"] = _median_ratio([(q["p0"].get(k), qp.get(k)) for k in ("rev", "ni")], floor=0.1)
        flows["cf"] = _ratio(q["p0"].get("ocf"), qp.get("ocf"), 0.1)
    eps = {}
    if _fin(sh) and sh > 0:
        es = eps_source(annual_only(fin))
        rep_fy = fin.get("epsAll") if _fin(fin.get("epsAll")) is not None else fin.get("epsRep")
        if es is not None:
            eps["fy"] = _ratio(es[0] * 1e8 / sh, rep_fy, UNIT_EPS_MIN)
        for k, x in (("q", q), ("qp", qp)):
            prof = x.get("nio") if fin.get("fs") != "OFS" and _fin(x.get("nio")) is not None else x.get("ni")
            if x and _fin(prof) is not None:
                eps[k] = _ratio(prof * 1e8 / sh, x.get("epsYtd"), UNIT_EPS_MIN)
    why = []
    if any(x for x in bal.values()):
        why.append("bs")
    if any(_off(x, UNIT_SCALE_MAX) for x in scale.values()):
        why.append("scale")
    if _off(flows.get("is"), UNIT_SCALE_MAX):
        why.append("is")
    if _off(flows.get("cf"), UNIT_SCALE_MAX):
        why.append("cf")
    if any(_off(x, UNIT_ANCHOR_MAX) for x in eps.values()):
        why.append("eps")
    if _off(cap, UNIT_ANCHOR_MAX):
        why.append("cap")
    return {"why": why, "bal": bal, "scale": scale, "flows": flows, "eps": eps, "cap": cap}


def _unit_ev(u):
    """unit_check 결과 → 로그 한 조각 ('최신 분기 배율 1,405배 · 사업보고서 자산=부채+자본 맞음 …')."""
    bits = [f"{UNIT_SRC_KO[k]} 배율 {v:,.2f}배" if v < 10 else f"{UNIT_SRC_KO[k]} 배율 {v:,.0f}배"
            for k, v in u["scale"].items() if v is not None]
    bal = u["bal"]
    for k, v in bal.items():
        bits.append(f"{UNIT_SRC_KO[k]} 자산=부채+자본 " + ("확인 못 함(예전 캐시)" if v is None else "맞음" if v == 0 else f"{v:.1%} 어긋남"))
    fmt = lambda v: f"{v:,.2f}배" if v < 10 else f"{v:,.0f}배"
    for k, v in (u.get("flows") or {}).items():
        if v is not None:
            bits.append(f"{UNIT_KO[k]} {fmt(v)}")
    for k, v in (u.get("eps") or {}).items():
        if v is not None:
            bits.append(f"{UNIT_SRC_KO[k]} 기본주당이익 대비 {fmt(v)}")
    if u.get("cap") is not None:
        bits.append(f"자본금 ÷ 액면가 대비 {fmt(u['cap'])}")
    return " · ".join(bits) or "확인할 재무제표 없음"


# 공시 단위 고침 (Jack, 2026-11-13 · 원인 수리 · 리뷰 #116 1차 뒤): 분기·반기 보고서가 단위를 잘못 적었으면(천원이라 적고 숫자는 원) 그 표의
# 금액이 정확히 1,000배 (백만원이면 1,000,000배)예요. 고치는 건 올해 분기 보고서(TTM 의 최신 분기)뿐이고, 표마다 따로 증명해요:
#   재무상태표  그 보고서의 지난해 말 칸(bal0)이 사업보고서의 자산총계 · 자본총계의 정확히 k 배 (bs_factor · 원 단위까지 · 캐시의 사업보고서에
#               총계가 없으면 자본총계 · 부채총계를 억원 반올림까지, 자본이 1억 이상일 때만)
#   손익계산서  그 보고서의 지난해 같은 기간 누적 칸(p0 매출 · 순이익)이 지난해 같은 분기 보고서의 누적 값의 k 배 (flow_factor · 금액은
#               억원 소수 한 자리라 반올림이 설명할 수 있는 0.05억 + 0.2% 안 · 지난해 값이 1억 미만인 줄은 증거로 세지 않아요)
#   현금흐름표  같은 방법으로 영업현금흐름
# k 는 1 (그 표는 맞음) · 1,000 · 1,000,000 중 하나예요. 금액이 있는데 증명이 안 되는 표가 하나라도 있으면 고치지 않아요 (unit_guard 가 비워요).
# 1 로 '증명'된 표도 믿지 않아요 (리뷰 #116 2차 S1): 지난해 같은 분기 보고서도 같은 표가 1,000배면 그 표는 1배로 보이거든요. 그래서 무엇이든
# 나눌 때는 표마다 기준값이 있어야 해요 — 손익계산서는 (나누든 1 이든) 기본주당이익 기준값이 맞아야 하고 (기준값이 없으면 같은 배수로 나눈
# 재무상태표의 자본금 기준값에 기대요), 현금흐름표는 기준값이 맞은 표와 같은 배수일 때만, 재무상태표는 1 이거나 기준값이 맞을 때만
# (재무상태표의 1 은 사업보고서 칸과 원 단위까지 같은 증명이라 안전망의 '보고서 사이 배율'이 그대로 봐요). 계산할 수 있는 기준값이 하나라도
# 어긋나면 고치지 않아요 (다른 기준값으로 덮지 않아요 · 리뷰 #116 2차 N3). 원화가 아닌 재무제표는 기준값을 보지 않아요 (#118 과 같게) → 고치지 않아요.
# 신종자본증권 분배(자본변동표)는 증명할 칸이 없어 나눈 보고서에서는 비워요 → EPS · BPS 는 '어디 몫인지 알 수 없는 신종자본증권'과 같은 기준
# (전체 · how hybrid)으로 돌아가요 (리뷰 #116 2차 N1). 재무상태표의 신종자본증권 금액은 재무상태표 배수로 나눠요.
# 어느 쪽이 틀렸는지: 지난해 같은 분기 보고서도 사업보고서와 UNIT_SCALE_MAX 배 넘게 다르면 사업보고서 쪽이 다른 단위일 수 있어 고치지 않아요
# (리뷰 #116 B1 — 사업보고서가 ÷1,000 이면 맞는 분기를 나누게 돼요). 지난해 같은 분기 보고서의 지난해 말 칸이 사업보고서의 전기 칸(balP ·
# 같은 날)과 UNIT_SCALE_MAX 배 넘게 달라도 고치지 않아요. 나눈 뒤에는 공시 단위와 상관없는 기준값과 맞아야 해요: 손익계산서를 나눴으면
# 나눈 누적 주주 몫 순이익 ÷ 그 보고서의 누적 기본주당이익 (= 그 기간의 평균 주식 수), 재무상태표를 나눴으면 나눈 자본금 ÷ 액면가(배당 표)가
# 오늘 주식 수의 1/UNIT_FIX_BAND ~ UNIT_FIX_BAND 배 안. 8 배: 맞게 나눈 두 회사는 0.73 배(진코스텍) · 5.0 배(디와이에이 · 6월 뒤 주식 병합)이고,
# 잘못 나누면 진짜 비의 1/1,000 이라 진짜 비가 50 배 이하인 회사(2026-11-12 발행본 2,128곳 중 2곳 빼고)는 1/20 아래로 떨어져요.
# 현금흐름표만 다른 배수면(손익 · 재무상태표의 배수와 다르면) 기준값이 없어 고치지 않아요. 사업보고서 쪽이 틀린 경우는 고치지 않고 비우기만.
# 알려진 한계: 회사가 그 반기보고서를 끝내 고쳐 내지 않으면, 이듬해 같은 분기(2027.2Q)가 최신일 때 그 보고서는 '지난해 같은 분기'가 돼서
# 두 분기 규칙으로 고치지 않고 안전망이 다시 비워요 (docs/RUNBOOK.md).
UNIT_FACTORS = (1000.0, 1e6)
UNIT_FIX_BAND = 8.0
UNIT_FLOW_ABS = 0.05     # 억원 — 소수 한 자리로 반올림한 값끼리라 반올림만으로 생기는 차이의 최대 (지난해 값 쪽)
UNIT_FLOW_REL = 0.002    # 0.2% — 그 위로 허용하는 차이
UNIT_FLOW_MIN = 1.0      # 억원 — 지난해 값이 이보다 작은 줄은 증거로 세지 않아요 (반올림 0.05억이 5% 넘게 돼요 · 리뷰 #116 2차 N2)
UNIT_Q_BS = ("eq", "eqo", "bor", "cash", "ca", "cl", "cs", "nciBs")    # 재무상태표 칸 (억원)
UNIT_Q_IS = ("rev", "op", "ni", "nio", "ie", "nciPl")                  # 손익계산서 칸 (누적 · 억원)
UNIT_Q_CF = ("ocf", "iec", "dep")                                      # 현금흐름표 칸 (누적 · 억원)


def needs_unit0(d):
    """분기 항목이 지난해 칸(bal0 · p0) 없이 저장됐는지 (UNIT_REDO_TAG — unit_fix_quarter 가 그 회사에만 물어요). (순수 함수)"""
    return isinstance(d, dict) and ("bal0" not in d or "p0" not in d)


def bs_factor(q0, ref=None, eq=None, li=None):
    """재무상태표의 배수: 분기 보고서의 지난해 말 [자산, 부채, 자본] (원) q0 가 같은 날 사업보고서 값의 몇 배인지 → 1 · 1,000 · 1,000,000,
    아니면 None. ref = 사업보고서의 [자산, 부채, 자본] (원): 자산 · 자본 모두 k 배 (±k 원). ref 가 없으면 eq · li = 사업보고서 자본총계 · 부채총계
    (억원 · 소수 한 자리): q0 ÷ k 가 둘 다 ±0.05억 안이고 자본이 1억 이상일 때만. (순수 함수)"""
    if not isinstance(q0, (list, tuple)) or len(q0) != 3 or any(_fin(x) is None for x in q0):
        return None
    ok_ref = isinstance(ref, (list, tuple)) and len(ref) == 3 and all(_fin(x) is not None for x in ref) and ref[0] != 0
    for k in (1.0,) + UNIT_FACTORS:
        if ok_ref:
            if all(abs(q0[i] - k * ref[i]) <= k for i in (0, 2)):
                return k
        elif _fin(eq) is not None and _fin(li) is not None and abs(eq) >= 1.0:
            if abs(q0[2] / k / 1e8 - eq) <= 0.05 + 1e-9 and abs(q0[1] / k / 1e8 - li) <= 0.05 + 1e-9:
                return k
    return None


def flow_factor(pairs):
    """손익 · 현금흐름표의 배수: [(그 보고서의 지난해 칸, 지난해 같은 분기 보고서의 값)] (억원 · 소수 한 자리) 이 모두 같은 k 배인지 → 1 · 1,000 ·
    1,000,000, 아니면 None. 차이는 UNIT_FLOW_ABS (두 값을 따로 0.1억으로 반올림해서 생길 수 있는 최대) + UNIT_FLOW_REL × |지난해 값| 까지.
    지난해 값이 UNIT_FLOW_MIN(1억) 미만이거나 없는 쌍은 증거로 세지 않아요 (그만한 값에서는 반올림 차이가 5% 를 넘어 증명이 약해요) · 쓸 쌍이
    없으면 None. (순수 함수)"""
    use = [(float(a), float(b)) for a, b in pairs if _fin(a) is not None and _fin(b) is not None and abs(b) >= UNIT_FLOW_MIN]
    if not use:
        return None
    for k in (1.0,) + UNIT_FACTORS:
        if all(abs(a / k - b) <= UNIT_FLOW_ABS + 1e-9 + UNIT_FLOW_REL * abs(b) for a, b in use):
            return k
    return None


def _has(q, keys):
    return any(_fin(q.get(k)) is not None for k in keys)


def scale_quarter(q, kb=1.0, ki=1.0, kc=1.0):
    """분기 해석 결과 q 의 금액을 표마다 나눈 새 dict (억원 칸은 소수 한 자리로 다시 반올림 · bal · bal0 은 원 그대로 나눠요) — unitFix =
    {bs · is · cf: 나눈 배수 (1 이 아닌 것만)}. 신종자본증권: 재무상태표 금액(eq)은 kb 로 나누고, 자본변동표의 분배(dist · 0 이 아니면)는 비우고
    ok False (unproven) 로 둬요. (순수 함수)"""
    out = dict(q)
    for keys, k in ((UNIT_Q_BS, kb), (UNIT_Q_IS, ki), (UNIT_Q_CF, kc)):
        if k == 1:
            continue
        for key in keys:
            v = _fin(q.get(key))
            if v is not None:
                out[key] = round(v / k, 1)
    if kb != 1:
        for key in ("bal", "bal0"):
            if isinstance(q.get(key), list):
                out[key] = [x / kb if _fin(x) is not None else x for x in q[key]]
    if isinstance(q.get("p0"), dict):
        p0 = dict(q["p0"])
        for key, k in (("rev", ki), ("ni", ki), ("ocf", kc)):
            if k != 1 and _fin(p0.get(key)) is not None:
                p0[key] = round(p0[key] / k, 1)
        out["p0"] = p0
    if isinstance(q.get("hyb"), dict):
        h = dict(q["hyb"])
        if kb != 1 and _fin(h.get("eq")) is not None:
            h["eq"] = round(h["eq"] / kb, 1)                 # 재무상태표의 신종자본증권 (재무상태표 배수로 증명)
        if (kb, ki, kc) != (1, 1, 1) and _fin(h.get("dist")) not in (None, 0.0):
            # 자본변동표의 분배는 증명할 칸이 없어요 (리뷰 #116 2차 N1): 비우고 '어디 몫인지 알 수 없음'으로 → EPS · BPS 는 전체 기준 (how hybrid)
            h.update(dist=None, ok=False, unproven=True)
        out["hyb"] = h
    out["unitFix"] = {name: int(k) for name, k in (("bs", kb), ("is", ki), ("cf", kc)) if k != 1}     # corp.json 에 1000 · 1000000 (정수)
    return out


def _in_band(r):
    return r is not None and 1.0 / UNIT_FIX_BAND <= r <= UNIT_FIX_BAND


def unit_anchor_eps(fin, q, ki, shares):
    """기본주당이익 기준값: 손익계산서를 ki 로 나눈 누적 주주 몫 순이익 (연결은 지배주주 nio · 별도는 ni) ÷ 그 보고서의 누적 기본주당이익 (원 ·
    단위를 잘못 적어도 그대로) = 그 기간의 평균 주식 수가 오늘 주식 수의 1/UNIT_FIX_BAND ~ UNIT_FIX_BAND 배 안이면 "ok", 밖이면 "fail", 볼 수
    없으면 "none" (주식 수 없음 · 기본주당이익 줄 없음 · |기본주당이익| < UNIT_EPS_MIN · 순이익과 부호가 다름). ki 가 1 이어도 봐요. (순수 함수)"""
    prof = q.get("nio") if fin.get("fs") != "OFS" and _fin(q.get("nio")) is not None else q.get("ni")
    eps = _fin(q.get("epsYtd"))
    if not shares or _fin(prof) is None or eps is None or abs(eps) < UNIT_EPS_MIN:
        return "none"
    r = _ratio(prof / ki * 1e8 / eps, shares)
    return "none" if r is None else "ok" if _in_band(r) else "fail"


def unit_anchor_cap(s, q, kb, shares):
    """자본금 ÷ 액면가 기준값: 재무상태표를 kb 로 나눈 그 보고서의 자본금 ÷ 액면가(배당 표 · 원) = 발행 주식 수의 상한이 오늘 주식 수의
    1/UNIT_FIX_BAND ~ UNIT_FIX_BAND 배 안이면 "ok", 밖이면 "fail", 볼 수 없으면 "none" (주식 수 · 자본금 없음 · 액면가는 안전망과 같은 par_value:
    무액면 · 0 · '-' · 100원 미만(손으로 적다 틀린 '5.000' 같은 값 — #118 3차 S-B)이면 볼 수 없음). (순수 함수)"""
    par = par_value(s)
    cs = _fin(q.get("cs"))
    if not shares or not par or not cs or cs <= 0:
        return "none"
    return "ok" if _in_band(_ratio(cs / kb * 1e8 / par, shares)) else "fail"


def unit_fix_plan(fin, q, prev, s=None, pref_shares=None):
    """올해 분기 보고서 q 를 어떻게 나눌지 → ("fix", kb, ki, kc) · ("none", 이유) (고칠 것이 없음) · ("left", 이유) (고치지 못함 · 비워요) ·
    ("need", 이유) (증명할 지난해 칸이 없음 — unit_fix_quarter 가 그 보고서를 한 번 다시 받아요).
    prev = 지난해 같은 분기 보고서 · s = data.json 종목 (오늘 주식 수 · 배당 표의 액면가 _bas). (순수 함수)"""
    if not q or not fin:
        return ("none", "")
    sq = stmt_scale(q, fin)
    p0 = q.get("p0") if isinstance(q.get("p0"), dict) else {}
    flows_is = _median_ratio([(p0.get(k), (prev or {}).get(k)) for k in ("rev", "ni")], floor=0.1) if p0 and prev else None
    flows_cf = _ratio(p0.get("ocf"), (prev or {}).get("ocf"), 0.1) if p0 and prev else None
    if not (_off(sq, UNIT_SCALE_MAX) or _off(flows_is, UNIT_SCALE_MAX) or _off(flows_cf, UNIT_SCALE_MAX)):
        return ("none", "")
    if not prev:
        return ("left", "지난해 같은 분기 보고서가 없어요")
    sp = stmt_scale(prev, fin)
    if sp is None or _off(sp, UNIT_SCALE_MAX):
        return ("left", "지난해 같은 분기 보고서도 사업보고서와 단위가 달라요 (사업보고서 쪽일 수 있어요)")
    pb0, bal_p = prev.get("bal0"), fin.get("balP")    # 지난해 같은 분기의 지난해 말 칸 ↔ 사업보고서의 전기 칸 (같은 날 · 둘 다 있을 때)
    if isinstance(pb0, list) and isinstance(bal_p, list) and len(pb0) == 3 and len(bal_p) == 3 \
            and any(_off(_ratio(pb0[i], bal_p[i]), UNIT_SCALE_MAX) for i in (0, 2)):
        return ("left", "지난해 같은 분기 보고서의 지난해 말 칸이 사업보고서의 전기 칸과 단위가 달라요 (어느 쪽이 틀렸는지 몰라요)")
    if sq is not None and sq <= 1.0 / UNIT_SCALE_MAX:
        return ("left", "올해 분기 보고서가 사업보고서보다 작아요 (나눌 것이 아니에요)")
    if "bal0" not in q or "p0" not in q:
        return ("need", "그 보고서의 지난해 칸이 캐시에 없어요 (다시 받아야 해요)")
    kb = bs_factor(q.get("bal0"), fin.get("bal"), fin.get("eq"), fin.get("li")) if _has(q, UNIT_Q_BS) else 1.0
    ki = flow_factor([(p0.get(k), prev.get(k)) for k in ("rev", "ni")]) if _has(q, UNIT_Q_IS) else 1.0
    kc = flow_factor([(p0.get("ocf"), prev.get("ocf"))]) if _has(q, UNIT_Q_CF) else 1.0
    if None in (kb, ki, kc):
        miss = [n for n, k in (("재무상태표", kb), ("손익계산서", ki), ("현금흐름표", kc)) if k is None]
        return ("left", f"{'·'.join(miss)}의 배수를 지난해 칸으로 증명하지 못했어요")
    if kb == ki == kc == 1.0:
        return ("left", "지난해 칸으로는 모든 표가 1배예요 (다른 까닭 · 고치지 않아요)")
    s = s or {}
    won = not not_won(s, fin)       # #118: 원화가 아닌 재무제표는 원으로 적힌 액면가 · 주식 수와 견주지 않아요 → 기준값 없음
    shares = per_share_count(s, pref_shares) if won and s.get("shr") else None
    eps_st, cap_st = unit_anchor_eps(fin, q, ki, shares), unit_anchor_cap(s, q, kb, shares)
    if "fail" in (eps_st, cap_st):
        bad = [n for n, st in (("기본주당이익", eps_st), ("자본금 ÷ 액면가", cap_st)) if st == "fail"]
        return ("left", f"나눈 뒤 {'·'.join(bad)} 기준값이 오늘 주식 수와 맞지 않아요")
    is_anch = eps_st == "ok" or (eps_st == "none" and ki == kb and cap_st == "ok")
    bs_anch = cap_st == "ok" or (eps_st == "ok" and kb == ki)
    has_is, has_bs, has_cf = _has(q, UNIT_Q_IS), _has(q, UNIT_Q_BS), _has(q, UNIT_Q_CF)
    ok_is = not has_is or is_anch
    ok_bs = not has_bs or kb == 1 or bs_anch
    ok_cf = not has_cf or (kc == ki and has_is and is_anch) or (kc == kb and has_bs and bs_anch)
    if not (ok_is and ok_bs and ok_cf):
        bad = [n for n, ok in (("손익계산서", ok_is), ("재무상태표", ok_bs), ("현금흐름표", ok_cf)) if not ok]
        return ("left", f"{'·'.join(bad)}에 기준값(기본주당이익 · 자본금 ÷ 액면가 대비 오늘 주식 수)이 없거나 기준값이 있는 표와 배수가 달라요"
                + ("" if won else " — 원화가 아닌 재무제표라 기준값을 보지 않아요"))
    return ("fix", kb, ki, kc)


def unit_fix_quarter(client, corp, fin, year, reprt, q, prev, s=None, pref_shares=None, unit_log=None):
    """enrich_with_dart 안: 올해 분기 보고서 q 를 unit_fix_plan 대로 나눠 돌려줘요 (고치지 않으면 q 그대로). 지난해 칸(bal0 · p0)이 캐시에
    없으면 그 보고서만 한 번 다시 받아요 (unit_redo). unit_log: {"fixed": [...], "left": [...], "redo": n}."""
    plan = unit_fix_plan(fin, q, prev, s, pref_shares)
    if plan[0] == "none":
        return q
    unit_log = unit_log if unit_log is not None else {"fixed": [], "left": [], "redo": 0}
    nm = f"{(s or {}).get('t', corp)} {(s or {}).get('nk', '')}".strip()
    if plan[0] == "need" and client is not None:
        q2 = dart_quarter(client, corp, year, reprt, fs=fin.get("fs"), unit_redo=True)
        if q2 and "bal0" in q2 and "p0" in q2:
            with client.lock:
                unit_log["redo"] += 1
            q = q2
            plan = unit_fix_plan(fin, q, prev, s, pref_shares)
    if plan[0] == "need":
        plan = ("left", plan[1])
    lock = client.lock if client is not None else threading.Lock()
    rep_ = f"{year}.{REPRT_KO.get(reprt, reprt)}"
    with lock:
        if plan[0] == "fix":
            ks = " · ".join(f"{n} ÷ {k:,.0f}" for n, k in (("재무상태표", plan[1]), ("손익계산서", plan[2]), ("현금흐름표", plan[3])) if k != 1)
            unit_log.setdefault("fixed", []).append(f"{nm} {rep_} ({ks})")
        elif plan[0] == "left":
            unit_log.setdefault("left", []).append(f"{nm} {rep_} ({plan[1]})")
    return scale_quarter(q, plan[1], plan[2], plan[3]) if plan[0] == "fix" else q


def unit_fix_log(unit_log):
    """enrich_with_dart 끝의 로그 (공시 단위 고침)."""
    f, left = unit_log["fixed"], unit_log["left"]
    log(f"{'  !! ' if f or left else '· '}공시 단위 고침: 올해 분기 보고서 {len(f)}건을 표마다 증명해 나눠 썼어요 · 다시 받은 보고서 "
        f"{unit_log['redo']}건 · 고치지 못해 그대로 둔 {len(left)}건 (공시 단위 확인이 숫자를 비워요)"
        + (f" — 고침: {'; '.join(f)}" if f else "") + (f" — 그대로: {'; '.join(left)}" if left else ""))


def unit_guard(kr_stocks, fin_map, mult_extra, pref_shares=None):
    """공시 단위 확인 (위 설명) — fill_multiples 뒤, 점수(add_percentiles)·corp.json(build_corp)·incCheck 보다 먼저.
    걸린 회사: data.json 종목의 UNIT_BLANK 를 지우고 unitChk = 이유 목록 · mult_extra 의 영수증(UNIT_EXTRA_KEYS)을 지워요 (build_corp 가 종목의
    unitChk 를 보고 corp.json 금액을 비워요 — 표시는 종목 한 곳에만). 반환: {"hit": {코드: 이유}, "real": [PBR 이 낮지만 맞는 회사],
    "bal": 확인한 재무제표 수 Counter, "cover": data.json unitChkCover}. 로그는 크게, 이름과 함께.
    unitChkCover (회사 수): checked 읽은 재무제표 모두 자산 = 부채 + 자본 을 봄 · unchecked 자산총계 없이 저장된 재무제표가 있음 · noScale 분기
    보고서가 없어 보고서 사이 배율을 못 봄 · anchor 기본주당이익이나 자본금 ÷ 액면가로 봄 · flows 손익 · 현금흐름 지난해 칸으로 봄 · notWon
    원화가 아닌 재무제표라 기준값(eps · cap)을 보지 않음 (리뷰 #118) · parLow 액면가가 100원 미만이라 자본금 ÷ 액면가를 보지 않음.
    한 회사의 캐시 항목이 이상해 확인이 오류를 내면 그 회사 이름과 함께 RuntimeError 로 실행을 멈춰요 (조용히 넘기지 않아요)."""
    hit, real, cnt, names, names_par = {}, [], collections.Counter(), [], []
    for s in kr_stocks:
        if s.get("cls") != "kr":
            continue
        t, fin = s["t"], fin_map.get(s["t"])
        if not fin:
            continue
        won = not not_won(s, fin)          # 리뷰 #118: 원화가 아닌 재무제표는 기준값(eps · cap)을 보지 않아요
        try:
            u = unit_check(fin, per_share_count(s, pref_shares) if won else None, cap_ratio(s, fin, pref_shares) if won else None)
        except Exception as e:             # 감싸서 넘기지 않아요 (리뷰 #118 3차 N-e): 실행을 멈추되 어느 회사인지 말해요
            raise RuntimeError(f"!! 공시 단위 확인: {t} {s.get('nk', '')} 의 재무제표 캐시 항목을 읽지 못했어요 ({type(e).__name__}: {e}) — "
                               "실행을 멈춰요 (그 항목을 확인하세요)") from e
        cnt["cov:notWon"] += not won
        p_raw = par_raw(s)
        if won and p_raw is not None and 0 < p_raw < UNIT_PAR_MIN:
            cnt["cov:parLow"] += 1
            names_par.append(f"{t} {s.get('nk', '')} {p_raw:g}원".strip())
        for k, v in u["bal"].items():
            cnt[f"{k}:{'none' if v is None else 'ok' if v == 0 else 'off'}"] += 1
        cnt["cov:n"] += 1
        cnt["cov:checked" if u["bal"] and all(v is not None for v in u["bal"].values()) else "cov:unchecked"] += 1
        cnt["cov:noScale"] += not any(v is not None for v in u["scale"].values())
        cnt["cov:anchor"] += any(v is not None for v in u["eps"].values()) or u["cap"] is not None
        cnt["cov:eps"] += any(v is not None for v in u["eps"].values())
        cnt["cov:cap"] += u["cap"] is not None
        cnt["cov:flows"] += any(v is not None for v in u["flows"].values())
        nm = f"{t} {s.get('nk', '')}".strip()
        if u["why"]:
            was = {k: s.get(k) for k in UNIT_BLANK if s.get(k) is not None}
            for k in UNIT_BLANK:
                s.pop(k, None)
            s["unitChk"] = list(u["why"])
            e = mult_extra.get(t)
            if e is not None:
                for k in UNIT_EXTRA_KEYS:
                    e.pop(k, None)
                if not e:
                    mult_extra.pop(t)
            hit[t] = list(u["why"])
            for w in u["why"]:
                cnt[f"why:{w}"] += 1
            names.append(f"{nm} [{'·'.join(UNIT_KO[w] for w in u['why'])} — {_unit_ev(u)}] 비운 값: "
                         + (", ".join(f"{k} {v:,}" for k, v in was.items()) or "없음"))
        elif _fin(s.get("pbr")) is not None and s["pbr"] < UNIT_PBR_LOOK:
            real.append(f"{nm} (PBR {s['pbr']:.2f} · {_unit_ev(u)})")
    log(f"{'  !! ' if hit else '· '}공시 단위 확인: {len(hit)}곳 비움 (" + " · ".join(f"{UNIT_KO[w]} {cnt['why:' + w]}" for w in UNIT_WHY) + ")"
        + (" — PER·PBR·EPS·BPS·ROE·부채비율·영업이익률·매출 성장률 · 3년 실적 · 자본 · EV 배수 · 재무 경고 · 영수증을 비웠어요 "
           "(가치·퀄리티 점수는 이 회사 없이 매겨요 · 배당은 남겨요)" if hit else ""))
    for x in names:
        log(f"  !! 공시 단위: {x}")
    log(f"· 공시 단위 — 자산=부채+자본 확인: 사업보고서 맞음 {cnt['fy:ok']:,} · 어긋남 {cnt['fy:off']} · 확인 못 함 {cnt['fy:none']:,} | "
        f"최신 분기 맞음 {cnt['q:ok']:,} · 어긋남 {cnt['q:off']} · 확인 못 함 {cnt['q:none']:,} | 지난해 같은 분기 맞음 {cnt['qp:ok']:,} · "
        f"어긋남 {cnt['qp:off']} · 확인 못 함 {cnt['qp:none']:,} (확인 못 함 = 자산총계를 읽기 전(2026-11-13)에 캐시에 저장된 재무제표)")
    cover = {"v": 1, "companies": cnt["cov:n"], "checked": cnt["cov:checked"], "unchecked": cnt["cov:unchecked"],
             "noScale": cnt["cov:noScale"], "anchor": cnt["cov:anchor"], "eps": cnt["cov:eps"], "cap": cnt["cov:cap"],
             "flows": cnt["cov:flows"], "notWon": cnt["cov:notWon"], "parLow": cnt["cov:parLow"], "hit": len(hit)}
    thin = cover["unchecked"] > cover["checked"]
    log(f"{'  !! ' if thin else '· '}공시 단위 확인이 본 회사 {cover['companies']:,}곳: 자산=부채+자본을 모든 재무제표에서 봄 {cover['checked']:,} · "
        f"못 본 재무제표가 있음 {cover['unchecked']:,}" + (" (대부분 아직 못 봐요 — 자산총계를 읽기 전(2026-11-13)에 캐시에 저장됐어요 · 90일 "
        "재확인으로 채워져요)" if thin else "") + f" · 분기 보고서가 없어 보고서 사이 배율을 못 봄 {cover['noScale']:,} · 기본주당이익으로 봄 "
        f"{cover['eps']:,} · 자본금 ÷ 액면가로 봄 {cover['cap']:,} · 둘 중 하나 {cover['anchor']:,} · 손익·현금흐름 지난해 칸으로 봄 {cover['flows']:,} "
        f"· 원화가 아닌 재무제표라 기준값을 보지 않음 {cover['notWon']:,} (data.json unitChkCover)")
    log(f"{'  !! ' if names_par else '· '}배당 표의 액면가가 {UNIT_PAR_MIN:g}원 미만이라 자본금 ÷ 액면가를 보지 않은 회사 {len(names_par)}곳"
        + (f" (손으로 적다 틀린 값 같아요): {', '.join(names_par[:12])}{' …' if len(names_par) > 12 else ''}" if names_par else ""))
    log(f"{'  !! ' if real else '· '}PBR {UNIT_PBR_LOOK:g} 미만인데 공시 단위 확인을 통과한 회사 {len(real)}곳 (비우지 않았어요 · 확인해 보세요)"
        + (": " + "; ".join(real) if real else ""))
    return {"hit": hit, "real": real, "bal": cnt, "cover": cover}


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


def div_basis(dps3, bas, cs3, shr, prefs=(), ss3=None, cap_k="all", cap_src=None, stk=None):
    """한 회사의 주당 배당금 3년을 오늘 주식 수 기준으로 맞춰요. (순수 함수)
    dps3 보통주 주당 배당금 [당기, 전기, 전전기] (0 = 배당 없음 · None = 모름) · bas = parse_dart_basis 결과 ·
    cs3 자본금 3년 (억원) · shr 오늘 상장 보통주 수 · prefs 같은 회사 상장 우선주들의 오늘 주식 수 ·
    ss3 자본잉여금 3년 (억원 — 액면가가 그대로인데 주식 수가 깨끗한 배율로 바뀐 해가 무상증자인지 확인해요).
    cap_k 자본금의 범위: all = 회사 전체 · common = 보통주만 (v19.1e: 그러면 아래 끝은 오늘 보통주 수 ÷ 보통주 발행 주식 수 상한).
    cap_src paid = 납입자본(주식발행초과금이 섞일 수 있음): 올해 아래 끝에만 쓰고 앞 해 비교에는 쓰지 않아요 (v19.1e).
    stk 주식의 총수 현황 (parse_dart_shares · v19.1g): 상장되지 않은 우선주가 배당을 받아 위 끝을 셀 수 없을 때만 그해 말 보통주 유통
    주식 수로 위 끝을 세요. 배당 표와 맞는지 먼저 확인해요 (stk_upper).
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

    def unlisted_in(i):
        """i 해에 배당을 받은 우선주·종류주 종류가 상장 우선주 종목 수보다 많은지 (상장되지 않은 주식이 총액에 섞임)."""
        return sum(1 for p in pds if p[i] is not None and p[i] > 0) > len(prefs)

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
        elif N[0] and stk:
            hi = stk_upper(shr, stk, cash[0], d[0], [p[0] for p in pds if p[0] is not None])
        elif d[0] == 0 and W[0]:
            hi = (shr + pref_all) / W[0] * (1 + 0.5e6 / abs(ni[0]) + 0.5 / abs(eps[0]))
        if I[0]:
            lo = ((shr + pref_all) if cap_k != "common" else shr) / I[0] * 0.999
    f0, st0 = factor_between(lo, hi)

    def rel(i):
        """당기 기준 ÷ i 해 기준 = gᵢ. 발행 주식 수 상한의 비(q)가 바뀐 배율을, 배당 받은 주식 수의 비(r)가 그해 배당금이
        옛 기준(g = q)인지 회사가 고쳐 적은 새 기준(g = 1)인지 알려 줘요."""
        q = I[0] / I[i] if I[0] and I[i] else None
        # v19.1g: 상장되지 않은 우선주가 배당을 받은 해의 N 에는 그 몫이 섞여 해마다 흔들려요 — 그 해가 끼면 배당 받은 주식 수의 비를
        # 쓰지 않아요 (자본금이 그대로면 '그대로', 아니면 판단하지 않음 · 리뷰 2026-11-07: 지아이텍 N/보통주 2.14 · 1.74 · 1.24)
        r_raw = N[0] / N[i] if N[0] and N[i] else None
        r = r_raw if not unlisted_in(0) and not unlisted_in(i) else None
        # 흔들린 비(r_raw)는 배율을 고르는 데는 쓰지 않지만 '판단하지 않음'을 고르는 데는 그대로 써요 (리뷰 2026-11-07: 지운 비 때문에
        # 예전엔 판단하지 않던 해가 '그대로'가 되지 않게). 섞인 몫은 '판단하지 않음'만 늘릴 수 있어요
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
            kr = clean_factor(r_raw) if r_raw is not None else None
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


STK_AGREE = (0.85, 1.02)    # 배당 표로 센 보통주 수 ÷ 주식의 총수 현황의 보통주 유통 주식 수가 이 안이어야 같은 기준이에요


def stk_upper(shr, stk, cash0, d0, pdps0):
    """상장되지 않은 우선주가 배당을 받은 해의 위 끝: 오늘 보통주 수 ÷ 그해 말 보통주 유통 주식 수. (순수 함수)
    유통 주식 수 ≤ 발행 주식 수라서 위 끝으로 맞아요. 다만 주당 배당금이 같은 주식 기준인지 먼저 확인해요: 총액에서 우선주·종류주 몫
    (유통 주식 수 × 가장 큰 종류 주당 배당)을 뺀 보통주 몫 ÷ 보통주 주당 배당 = 배당 받은 보통주 수가 유통 주식 수의 85~102% 여야 해요
    (가장 큰 주당 배당으로 빼서 조금 작게 나올 수 있고, 기준일까지의 자기주식 매입도 있어서). 아니면 None (판단하지 않아요)."""
    shr, cash0, d0 = _fin(shr), _fin(cash0), _fin(d0)
    cmo, pfo = _fin((stk or {}).get("cmo")), _fin((stk or {}).get("pfo"))
    paid = [p for p in (_fin(x) for x in pdps0 or ()) if p is not None and p > 0]
    if not (shr and shr > 0 and cash0 and cash0 > 0 and d0 and d0 > 0 and cmo and cmo > 0) or pfo is None or not paid:
        return None
    n_common = (cash0 - pfo * max(paid)) / d0
    if not (STK_AGREE[0] * cmo <= n_common <= STK_AGREE[1] * cmo):
        return None
    return shr / cmo * 1.001


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


def kr_pref_caps(listing):
    """목록 파일 전체에서 우선주 시가총액 합: {보통주 코드 앞 5자리: 조원}. kr_pref_shares 와 같은 목록이라 EPS·BPS 의 주식 수와
    EV 의 회사 시가총액이 같은 우선주를 봐요 (v19.1f 리뷰: 상위 2,500개 안의 우선주만 보면 둘이 어긋나요). (순수 함수)"""
    out = collections.Counter()
    if listing is None or "Code" not in getattr(listing, "columns", []) or "Marcap" not in listing.columns:
        return {}
    for code, mc in zip(listing["Code"].astype(str), listing["Marcap"]):
        code = code.strip()
        v = _fin(_num(mc))
        if is_preferred(code) and v and v > 0:
            out[code[:5]] += v / 1e12
    return dict(out)


# ────────────────────────────────────────────────────────────
# v19.1h: 배당 맞춤 이유 (dvWhy) — Jack, 2026-11-08 (네 가지 답도 같은 날: 아래 판정이 그 답이에요)
# ────────────────────────────────────────────────────────────
# 배당 막대를 오늘 주식 수 기준으로 다시 계산한 해(dpsF ≠ 1)가 있는 국내 종목마다, 주식 수가 바뀐 이유 · 날짜 · 배율을 DART 의
# 결정 공시에서 찾아요 (앱의 막대 아래 줄은 다음 PR). 조사: 2026-11-08 (맞춘 63곳 모두 결정 공시가 이유·날짜·배율을 줘요.
# 사업보고서의 '증자(감자) 현황'은 액면분할·병합을 거의 적지 않아 18곳뿐이라 쓰지 않아요).
#   목록    list.json — 회사 · (사업보고서 연도 − 2)년 1월 1일 ~ 오늘 · 거래소 수시공시(I001) + 주요사항보고서(B001) · 최종 정정본만
#           (last_reprt_at=Y: 정정한 공시는 마지막 판만 와요 — 영화금속 4:1 → 5:1 처럼 정정이 숫자를 바꿔요)
#   무상증자 fricDecsn.json · 유무상증자 pifricDecsn.json · 감자 crDecsn.json (구조화된 API · 최종 정정본)
#   액면분할 · 주식병합  주식분할결정 · 주식병합결정 공시 원문(document.xml) — API 가 없어요. 거래소의 정해진 양식이라
#           '1주당 가액 전 · 후'와 '신주의 효력발생일'을 읽어요 (배율은 액면가로: 첫 공시의 주식 총수가 틀린 일이 있었어요)
#   유상증자 · 전환사채 · 신주인수권부사채  piicDecsn · cvbdIsDecsn · bdwtIsDecsn — 사업보고서 뒤 변화에 분할·병합·무상증자 공시가
#           없을 때만 받아요 (늘어난 주식 수를 그 결정들이 덮는지 봐요)
#   빼는 것 종속회사·자회사 공시 · 철회한 결정 · 액면가만 바꾼 감자(주식 수 그대로) · 10% 이하 변화(주식배당 · 작은 무상증자 —
#           파이프라인의 SHARE_SAME 과 같은 기준이라 이름에도 곱에도 넣지 않아요)
#   날짜    법적 날짜 (Jack 답 4): 분할·병합 = 신주의 효력발생일 · 무상증자 = 신주배정기준일 · 감자 = 감자기준일. 그해 12월 31일 뒤부터
#           pxDate 까지의 사건이 그해 배율(dpsF)을 만들어요.
# 판정 → dvWhy.st (절대 짐작하지 않아요):
#   ok              이름 붙일 사건(10% 넘게 바뀐 분할 · 병합 · 무상증자)의 곱이 다시 계산한 해마다 dpsF ± 0.5% → 다시 계산 · 이유 줄.
#                   사건이 둘 이상이면 오래된 것부터 모두 (Jack 답 3 · 코미코: 앱이 Jack 의 두 문장을 하나로 이어요)
#   nf              사업보고서 안의 변화(액면가·자본잉여금 확인을 지난 것)인데 결정 공시가 없음 → 다시 계산 · '이유는 찾지 못했지만' 줄
#                   (그해 말 발행 주식 수 a → 오늘 상장 주식 수 b, 주식의 총수 현황)
#   filed           사업보고서 뒤의 변화에 분할·병합·무상증자 공시가 없고, 유상증자 · 전환사채 · 신주인수권부사채 공시가 늘어난 주식 수를
#                   설명함 → 다시 계산하지 않고 공시된 배당 그대로 · 수익률은 보통처럼 (Jack 답 2)
#   nc-mismatch     공시가 배율과 다름 (곱이 다름 · 깨끗하지 않은 배율 · 사건 없이 유상증자·합병 · 당기 배율 1 인데 그 뒤 사건 · 사건이
#                   섞여 말함) → 다시 계산하지 않고 배당수익률도 숨겨요 (Jack 답 1 · 2026-11-08: 대한제강 · 대동금속 · 티엘비)
#   nc-unexplained  사업보고서 뒤의 변화를 아무 공시도 설명하지 못함 → 다시 계산하지 않고 배당수익률도 숨겨요 (Jack 답 2)
#   nc-* 의 앱 줄 (Jack 2026-11-08 승인, 앱 PR 에서): "주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요."
#   조회 실패 (DART 오류 · 시간 초과 · 한도 · 공시를 읽지 못함) → dvWhy 없음 · 어제 결과(dpsF · fy 가 같을 때) 또는 줄 없음 (맞춤은
#   그대로). '찾지 못했지만' · '확인하지 못해' 줄은 조회가 끝난 경우에만 써요.
# 캐시: DART 캐시의 '{기업코드}|divwhy|v1' — 그 회사의 dpsF 나 사업보고서 연도가 바뀌면 다시 받아요 (90일 지나면 재확인 한도 안에서).
# 호출: 다시 계산한 회사만, 회사당 약 3회 (목록 2 + 결정 1~2). 보관된 캐시(dart=cache)에서는 빠진 회사만 받아요 — 캐시를 비우지 않아서
# 전체 DART 실행이 아니에요 (자본금 다시 읽기와 같은 방식). 빈 캐시의 전체 실행에서는 약 DVWHY_EST_STOCKS × 3 회가 더해져요.
DVWHY_TAG = "divwhy|v1"          # 캐시 키 '{기업코드}|divwhy|v1' — 해석이 바뀌면 v2 로 (그 항목만 다시 받아요)
DVWHY_TOL = 0.005                # 공시 사건 배율의 곱 = dpsF ± 0.5%
DVWHY_CLEAN_TOL = 1e-4           # 사건 하나의 배율은 정확한 값이에요 (액면가의 비 · 1 + 1주당 신주 수) — 깨끗한 배율과 이만큼 안
# Jack 의 답 (2026-11-08) 그대로 켜져 있어요. 끄면 예전처럼 다시 계산하고 줄만 없어요 (divCheck.why.keptT 에 이름이 남아요).
DVWHY_STOP_ON_MISMATCH = True          # 답 1: 공시가 배율과 다르면 다시 계산하지 않고 수익률도 숨겨요 (nc-mismatch)
DVWHY_STOP_ON_NF_AFTER_REPORT = True   # 답 2: 사업보고서 뒤 변화에 분할·병합·무상증자 공시가 없으면 다시 계산하지 않아요 (filed · nc-unexplained)
DVWHY_ST = ("ok", "nf", "filed", "nc-mismatch", "nc-unexplained")
DVWHY_FILED_SLACK = SHARE_SAME   # filed: 늘어난 주식 수 ≤ 결정들이 덮는 수 + 사업보고서 말 주식 수의 10% (스톡옵션 · 작은 발행)
DVWHY_CB_FLOOR = 0.7             # 전환·행사가액은 발행 때의 70% 밑으로 못 내려가요 → 사채가 만드는 주식 수는 많아야 발행 때의 1/0.7 배
DVWHY_PER_RUN = 150              # 한 실행에서 새로 조회하는 회사 수 상한 (넘으면 다음 실행이 이어받아요 · 그동안 줄 없음)
DVWHY_MAX_PAGES = 5              # 목록 한 종류당 100건짜리 쪽 수 상한 (넘으면 다 보지 못해 조회 실패로 봐요)
DVWHY_OTHER_LOOKBACK_DAYS = 183  # 유상증자·합병 같은 결정은 공시일로 놓아요 — 그해 말보다 이만큼 앞의 공시까지 그 사이에 있는 것으로 봐요
DVWHY_EST_STOCKS = 80            # 전체 DART 실행 어림: 맞춘 회사 약 80곳 × DVWHY_PER_STOCK 회
DVWHY_PER_STOCK = 3
DVWHY_NAMES = (                  # 공시 이름(띄어쓰기 · 앞의 [기재정정] 빼고)에 든 말 → 종류. 위에서부터 먼저 맞는 것.
    ("주식분할결정", "split"), ("주식병합결정", "merge"), ("유무상증자결정", "pifric"), ("무상증자결정", "fric"),
    ("유상증자결정", "rights"), ("감자결정", "cr"), ("합병결정", "merger"), ("회사분할결정", "spin"),
    ("포괄적교환", "exchange"), ("포괄적이전", "exchange"), ("주식교환", "exchange"), ("주식이전", "exchange"),
    ("주식배당결정", "stockdiv"), ("신주인수권부사채권발행결정", "bw"), ("전환사채권발행결정", "cb"))
DVWHY_OTHER_KO = {"rights": "유상증자", "merger": "합병", "spin": "회사분할", "exchange": "주식교환·이전", "stockdiv": "주식배당",
                  "cr": "감자", "cb": "전환사채", "bw": "신주인수권부사채"}
DVWHY_KIND_KO = {"split": "액면분할", "merge": "주식병합", "bonus": "무상증자", "reduce": "감자(주식병합)"}
_RCPT = re.compile(r"^\d{14}$")


def _kdate(x):
    """'2026년 01월 06일' · '2026-01-06' · '2026.01.06' · '20260106' → '2026-01-06' (있는 날짜만), 아니면 None. (순수 함수)"""
    s = str(x or "")
    m = (re.search(r"(20\d\d)\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})", s)
         or re.fullmatch(r"\s*(20\d\d)(\d\d)(\d\d)\s*", s))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def _rc_date(rc):
    """접수번호(14자리) 앞 8자리의 날짜, 아니면 None."""
    return _kdate(rc[:8]) if isinstance(rc, str) and _RCPT.match(rc) else None


def dvwhy_clean(r):
    """사건 하나의 배율이 깨끗한 분할 배율(2 · 2.5 · … · 100)이나 그 역수인지 (±DVWHY_CLEAN_TOL). (순수 함수)"""
    r = _fin(r)
    return r is not None and r > 0 and any(abs(r / c - 1) <= DVWHY_CLEAN_TOL for c in DIV_FACTORS if c != 1.0)


def dvwhy_named(r):
    """이름 붙일 만큼(10% 넘게) 주식 수를 바꾼 사건인지. 10% 이하(1.1 · 0.9 포함)는 파이프라인처럼 '그대로' — 1.1 − 1 이 부동소수점으로
    0.1 보다 아주 조금 커서 경계에 작은 여유를 둬요 (아이퀘스트 2025 무상증자 0.1주). (순수 함수)"""
    r = _fin(r)
    return r is not None and r > 0 and abs(r - 1) > SHARE_SAME + 1e-9


def dvwhy_kind(report_nm):
    """공시 이름 → (종류, 철회인지) 또는 (None, False). 종속회사·자회사 공시와 '결정'이 아닌 공시(거래정지·권리락 안내)는 None. (순수 함수)"""
    full = re.sub(r"\s+", "", str(report_nm or ""))
    nm = re.sub(r"^(\[[^\]]*\])+", "", full)
    if "종속회사" in nm or "자회사" in nm or "결정" not in nm:
        return None, False
    for word, kind in DVWHY_NAMES:
        if word in nm:
            return kind, "철회" in full
    return None, False


def dvwhy_filings(rows):
    """list.json 의 줄들 → {"docs": [(종류, 접수번호)], "api": {fric · pifric · cr}, "oth": [{k, d, rc}], "wd": [{k, d, rc, self}]}.
    docs 는 주식분할결정·주식병합결정 (원문을 읽어요), oth 는 이름 붙이지 않는 주식 수 변화 결정(유상증자 · 합병 …, 날짜는 공시일),
    wd 는 철회: 이름에 '철회'가 든 공시(그보다 먼저 낸 같은 종류 결정을 철회) 또는 비고(rm)에 '철'이 붙은 공시(DART: 본 공시는 철회됨 —
    그 공시 자체, self). 주식배당결정은 빼요 (10% 이하 변화가 대부분이고 파이프라인도 그만큼은 '그대로'로 봐요). 같은 접수번호는 한 번만.
    v19.1i: 주식배당결정은 sd [{d, rc}] 에 따로 적어요 — 배당 기준 증명(prove)이 그 사이에 주식배당이 있으면 증명하지 않게 (dvWhy 판정은
    예전처럼 쓰지 않아요). 주식소각결정도 cx [{d, rc}] 에 따로 — 주식 수가 줄어든 것을 설명하는 공시가 있는지만 봐요 (리뷰 2026-11-15).
    (순수 함수)"""
    out = {"docs": [], "api": set(), "oth": [], "wd": [], "sd": [], "cx": []}
    seen = set()
    for it in sorted(rows or [], key=lambda x: str(x.get("rcept_no") or "")):
        rc = str(it.get("rcept_no") or "").strip()
        if not _RCPT.match(rc) or rc in seen:
            continue
        seen.add(rc)
        kind, wd = dvwhy_kind(it.get("report_nm"))
        nm = re.sub(r"\s+", "", str(it.get("report_nm") or ""))
        if not kind and "주식소각결정" in nm and "종속회사" not in nm and "자회사" not in nm:
            if "철회" not in nm and "철" not in str(it.get("rm") or ""):
                out["cx"].append({"d": _kdate(it.get("rcept_dt")) or _rc_date(rc), "rc": rc})   # v19.1i: 소각 (공시일)
            continue
        if not kind:
            continue
        d = _kdate(it.get("rcept_dt")) or _rc_date(rc)
        if kind == "stockdiv":
            if not (wd or "철" in str(it.get("rm") or "")):
                out["sd"].append({"d": d, "rc": rc})     # v19.1i: 증명만 막아요 (공시일 · 철회한 것은 빼요)
            continue
        if wd or "철" in str(it.get("rm") or ""):
            out["wd"].append({"k": kind, "d": d, "rc": rc, "self": not wd})
        elif kind in ("split", "merge"):
            out["docs"].append((kind, rc))
        elif kind in ("fric", "pifric", "cr"):
            out["api"].add(kind)
        else:
            out["oth"].append({"k": kind, "d": d, "rc": rc})
    out["api"] = sorted(out["api"])
    return out


def _dash_none(v):
    """'-' · 빈 칸이면 '없음'(True), 숫자면 그 값, 다른 글자면 None(읽지 못함)."""
    s = str(v if v is not None else "").strip()
    if s in DASHES or s == "":
        return True
    return _num(s)


def parse_dvwhy_bonus(rows, pre=""):
    """fricDecsn (pre="") · pifricDecsn (pre="fric_") → (사건들, 읽지 못한 것들). 보통주에 주는 무상증자만 (우선주만 받는 결정은 빼요).
    r = 1 + 보통주 1주당 신주 수 · d = 신주배정기준일 · rc = 그 결정의 (최종 정정본) 접수번호. (순수 함수)"""
    ev, bad = [], []
    for row in rows or []:
        rc = str(row.get("rcept_no") or "").strip()
        x = _dash_none(row.get(pre + "nstk_ascnt_ps_ostk"))
        if x is True:
            continue                                   # 보통주 신주 없음 (우선주만)
        d = _kdate(row.get(pre + "nstk_asstd"))
        if not _RCPT.match(rc) or x is None or not x > 0 or d is None:
            bad.append({"rc": rc, "why": "무상증자 결정을 읽지 못함"})
            continue
        ev.append({"k": "bonus", "d": d, "r": round(1 + x, 7), "x": x, "rc": rc, "src": "pifric" if pre else "fric"})
    return ev, bad


def parse_dvwhy_rights(rows):
    """pifricDecsn 의 유상증자 몫 → 이름 붙이지 않는 주식 수 변화 (날짜 = 공시일 · n = 보통주 신주 수, 읽지 못하면 없음). (순수 함수)"""
    out = []
    for row in rows or []:
        rc = str(row.get("rcept_no") or "").strip()
        n = _dash_none(row.get("piic_nstk_ostk_cnt"))
        if n is True or (n is not None and n <= 0):
            continue
        out.append({"k": "rights", "d": _rc_date(rc), "rc": rc, **({"n": int(round(n))} if n is not None else {})})
    return out


RIGHTS_SH = ("sh", "?")             # v19.1i: 주주배정(주주배정후 실권주 일반공모 포함) · 방식을 모름 — 권리락으로 주가가 새 기준이 돼요


def parse_rights_terms(rows, pre=""):
    """유상증자 결정 (piicDecsn pre="" · pifricDecsn 의 유상 몫 pre="piic_") → {접수번호: {"m": 방식, "q": 새 보통주 ÷ 증자 전 보통주}}.
    방식 m: sh 주주배정(주주배정후 실권주 일반공모 포함) · tp 제3자배정 · pub 일반공모 · ? 읽지 못함. q 를 읽지 못하면 None. (순수 함수)
    v19.1i (리뷰 2026-11-15): 주주배정 유상증자는 권리락 날 거래소가 그만큼 기준가를 낮춰서, 오늘 주가는 새 기준인데 공시된 1주 배당은 옛 기준이에요."""
    out = {}
    for row in rows or []:
        rc = str(row.get("rcept_no") or "").strip()
        if not _RCPT.match(rc):
            continue
        txt = re.sub(r"\s+", "", str(row.get(pre + "ic_mthn") or ""))
        m = "sh" if "주주배정" in txt else "tp" if "제3자" in txt else "pub" if "일반공모" in txt else "?"
        n, b = _dash_none(row.get(pre + "nstk_ostk_cnt")), _dash_none(row.get(pre + "bfic_tisstk_ostk"))
        q = round(n / b, 6) if isinstance(n, float) and isinstance(b, float) and n > 0 and b > 0 else None
        out[rc] = {"m": m, "q": q}
    return out


def parse_dvwhy_cr(rows):
    """crDecsn → (사건들, 이름 붙이지 않는 변화, 읽지 못한 것들). 주식 수가 그대로면(액면가만 감액) 주식 수 변화가 아니에요.
    감자 방법이 주식병합이면 '주식병합으로 한 감자' 사건 reduce (r = 감자 뒤 ÷ 전 보통주 수, d = 감자기준일 — 액면병합 merge 와 따로 둬서
    앱이 따로 다룰 수 있게 · 승인된 문구는 아직 없어요), 아니면(소각 등) 이름 붙이지 않는 변화. (순수 함수)"""
    ev, oth, bad = [], [], []
    for row in rows or []:
        rc = str(row.get("rcept_no") or "").strip()
        b, a = _dash_none(row.get("bfcr_tisstk_ostk")), _dash_none(row.get("atcr_tisstk_ostk"))
        if b is True and a is True:
            continue                                   # 보통주 감자 없음
        d = _kdate(row.get("cr_std"))
        if not _RCPT.match(rc) or not isinstance(b, float) or not isinstance(a, float) or b <= 0 or a <= 0:
            bad.append({"rc": rc, "why": "감자 결정의 주식 수를 읽지 못함"})
            continue
        if abs(a / b - 1) < 1e-9:
            continue                                   # 액면가만 감액 (HC홈센타 2024)
        if "병합" in re.sub(r"\s+", "", str(row.get("cr_mth") or "")) and d:
            ev.append({"k": "reduce", "d": d, "r": round(a / b, 7), "rc": rc, "src": "cr"})
        else:
            oth.append({"k": "cr", "d": d or _rc_date(rc), "rc": rc})
    return ev, oth, bad


def dvwhy_doc_text(files, rc):
    """document.xml 의 zip 안 파일들 → 본문 글자 (그 접수번호의 본 파일, 없으면 가장 큰 파일). 못 읽으면 None."""
    if not files:
        return None
    name = next((n for n in files if n.rsplit("/", 1)[-1].split(".")[0] == rc), None) or max(files, key=lambda n: len(files[n]))
    raw = files[name]
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass
    return None


def _doc_cells(text):
    body = text[text.find("<body"):] if "<body" in text else text
    body = re.sub(r"<(style|STYLE|script|SCRIPT)[\s\S]*?</(style|STYLE|script|SCRIPT)>", " ", body)
    cells = re.findall(r"<t[dhDH][^>]*>([\s\S]*?)</t[dhDH]>", body)
    out = []
    for c in cells:
        s = html_unescape(re.sub(r"<[^>]+>", " ", c)).replace("&cr;", " ")
        out.append(re.sub(r"\s+", " ", s).strip())
    return out


def parse_dvwhy_doc(text, kind, rc):
    """주식분할결정 · 주식병합결정 원문 → (사건, None) 또는 (None, 읽지 못한 이유). (순수 함수)
    정정 공시는 맨 앞에 정정 전·후 표가 있고 그 뒤에 고친 양식 전체가 와서, 각 칸의 마지막 것을 읽어요 (조사: 60개 원문 모두 읽음).
    배율은 액면가로(분할 = 전 ÷ 후 > 1 · 병합 < 1). 발행주식총수(보통주)가 있으면 그 비가 배율 ± 10% 여야 해요 (병합 때 자기주식 소각
    · 단주 처리로 조금 달라요 — SK증권 2.1%)."""
    if not text:
        return None, "원문 없음"
    tk = _doc_cells(text)
    ns = [re.sub(r"\s+", "", s) for s in tk]

    def last(pred):
        idx = [i for i, s in enumerate(ns) if pred(s)]
        return idx[-1] if idx else None

    def val(i, k):
        return _num(tk[i + k]) if i is not None and i + k < len(tk) else None
    i = last(lambda s: s.startswith("1주당가액"))
    pb, pa = val(i, 1), val(i, 2)
    j = last(lambda s: s.startswith("보통주식"))
    sb, sa = val(j, 1), val(j, 2)
    k = last(lambda s: s.startswith("신주의효력발생일") or s == "효력발생일")
    d = _kdate(tk[k + 1]) if k is not None and k + 1 < len(tk) else None
    if not (pb and pa and pb > 0 and pa > 0):
        return None, "1주당 가액을 읽지 못함"
    if d is None:
        return None, "효력발생일을 읽지 못함"
    r = pb / pa
    if (kind == "split") != (r > 1) or abs(r - 1) < 1e-9:
        return None, f"{DVWHY_KIND_KO[kind]}인데 액면가 {pb:g} → {pa:g}"
    if sb and sa and sb > 0 and sa > 0 and abs((sa / sb) / r - 1) > SHARE_SAME:
        return None, f"주식 수 비 {sa / sb:.3f} 가 액면가 비 {r:g} 와 달라요"
    return {"k": kind, "d": d, "r": round(r, 7), "rc": rc, "src": "doc"}, None


DVWHY_WD_KINDS = ("split", "merge", "fric", "pifric", "cr")   # 이 결정의 철회만 '찾지 못했다'고 하지 않을 이유가 돼요


def dvwhy_drop_withdrawn(ev, wd):
    """철회된 결정을 빼요: 비고 '철'(self)은 그 접수번호의 결정, 이름의 '철회'는 같은 종류(무상·유무상 → 무상증자 · 감자 → 주식병합으로
    한 감자)의 결정 중 철회보다 먼저 낸 가장 늦은 것. (순수 함수)"""
    same = {"split": ("split",), "merge": ("merge",), "fric": ("bonus",), "pifric": ("bonus",), "cr": ("reduce",)}
    ev = list(ev)
    for w in sorted(wd or [], key=lambda x: x["rc"]):
        if w.get("self"):
            ev = [e for e in ev if e["rc"] != w["rc"]]
            continue
        ks = same.get(w["k"])
        cand = [e for e in ev if ks and e["k"] in ks and e["rc"] <= w["rc"]]
        if cand:
            ev.remove(max(cand, key=lambda e: e["rc"]))
    return ev


def dvwhy_fetch(client, corp, fy, today):
    """한 회사의 주식 수를 바꾼 결정 공시 → ({"ev", "oth", "wd", "bad"}, None) 또는 (None, 실패 이유 — 다음 실행에 다시).
    ev 이름 붙일 수 있는 사건(분할 · 병합 · 무상증자) · oth 이름 붙이지 않는 변화 · wd 철회 · bad 읽지 못한 공시(있으면 줄 없음)."""
    bgn, end = dt.date(fy - 2, 1, 1).strftime("%Y%m%d"), today.strftime("%Y%m%d")
    rows, n_i = [], 0
    for ty in ("I001", "B001"):
        page = 1
        while True:
            j = client.get("list.json", {"corp_code": corp, "bgn_de": bgn, "end_de": end, "pblntf_detail_ty": ty,
                                         "last_reprt_at": "Y", "page_count": "100", "page_no": str(page)})
            if j is None:
                return None, f"공시 목록({ty}) 조회 실패"
            st = str(j.get("status"))
            if st == "013":
                break
            if st != "000":
                return None, f"공시 목록({ty}) 상태 {st}"
            rows += j.get("list") or []
            n_i += len(j.get("list") or []) if ty == "I001" else 0
            pages = int(_fin(j.get("total_page")) or 1)
            if page >= pages:
                break
            if page >= DVWHY_MAX_PAGES:
                return None, f"공시 목록({ty})이 {pages}쪽이라 다 보지 못함 (상한 {DVWHY_MAX_PAGES}쪽)"
            page += 1
    fl = dvwhy_filings(rows)
    ev, oth, bad, rt = [], list(fl["oth"]), [], {}
    for kind in fl["api"]:
        ep = {"fric": "fricDecsn.json", "pifric": "pifricDecsn.json", "cr": "crDecsn.json"}[kind]
        j = client.get(ep, {"corp_code": corp, "bgn_de": bgn, "end_de": end})
        if j is None:
            return None, f"{ep} 조회 실패"
        st = str(j.get("status"))
        if st not in ("000", "013"):
            return None, f"{ep} 상태 {st}"
        rows_k = j.get("list") or [] if st == "000" else []
        if kind == "cr":
            e2, o2, b2 = parse_dvwhy_cr(rows_k)
            ev, oth, bad = ev + e2, oth + o2, bad + b2
        else:
            e2, b2 = parse_dvwhy_bonus(rows_k, pre="fric_" if kind == "pifric" else "")
            ev, bad = ev + e2, bad + b2
            if kind == "pifric":
                oth += parse_dvwhy_rights(rows_k)
                rt.update(parse_rights_terms(rows_k, pre="piic_"))     # v19.1i: 유상 몫의 방식 · 크기
        if st == "013":
            bad.append({"rc": "", "why": f"목록에는 있는데 {ep} 가 결정을 주지 않음"})
    for kind, rc in fl["docs"]:
        files = client.get_zip("document.xml", {"rcept_no": rc})
        if files is None:
            return None, f"공시 원문 {rc} 조회 실패"
        e, why = parse_dvwhy_doc(dvwhy_doc_text(files, rc), kind, rc)
        if e:
            ev.append(e)
        else:
            bad.append({"rc": rc, "why": why})
    ev = dvwhy_drop_withdrawn(ev, fl["wd"])
    wd_rc = {w["rc"] for w in fl["wd"] if w.get("self")}
    oth = [o for o in oth if o["rc"] not in wd_rc]                 # 철회된 유상증자 몫은 세지 않아요
    # nI: 거래소 수시공시(I001) 줄 수. 배당하는 회사는 3년 안에 현금배당결정을 I001 로 내요 — 0 이면 목록이 빠졌을 수 있어
    # '공시 없음'으로 결론 내지 않아요 (조회 실패로 봐요)
    return {"ev": sorted(ev, key=lambda e: (e["d"], e["rc"])), "oth": oth, "wd": fl["wd"], "bad": bad, "nI": n_i,
            "sd": fl["sd"], "cx": fl["cx"], "rt": rt}, None


DVWHY_FX_EP = {"rights": ("piicDecsn.json", "nstk_ostk_cnt"), "cb": ("cvbdIsDecsn.json", "cvisstk_cnt"),
               "bw": ("bdwtIsDecsn.json", "nstk_isstk_cnt")}


def parse_dvwhy_fx(rows, kind):
    """유상증자(piicDecsn) · 전환사채(cvbdIsDecsn) · 신주인수권부사채(bdwtIsDecsn) 발행 결정 → (fx [{k, d, n, rc}], 못 읽은 것).
    n = 보통주 신주 수 (유상증자) · 전환·행사로 발행할 주식 수 (발행 때 가액 기준) · d = 공시일(접수번호). '-' 는 보통주 없음이라 빼고,
    읽지 못한 값은 세지 않아요 (덮을 수 있는 주식 수만 줄어서 '설명함'이 되기 어려워질 뿐이에요 — 조심하는 쪽). (순수 함수)"""
    key = DVWHY_FX_EP[kind][1]
    fx, bad = [], []
    for row in rows or []:
        rc = str(row.get("rcept_no") or "").strip()
        n = _dash_none(row.get(key))
        if n is True:
            continue
        if not _RCPT.match(rc) or n is None or not n > 0:
            bad.append({"rc": rc, "why": f"{DVWHY_OTHER_KO[kind]} 주식 수를 읽지 못함"})
            continue
        fx.append({"k": kind, "d": _rc_date(rc), "n": int(round(n)), "rc": rc})
    return fx, bad


def dvwhy_fetch_fx(client, corp, fy, today, oth, terms=None):
    """목록에 있는 유상증자 · 전환사채 · 신주인수권부사채 결정의 주식 수 → ((fx, 못 읽은 것), None) 또는 (None, 실패 이유).
    사업보고서 뒤 변화에 이름 붙일 공시가 없을 때만 불러요 (종류마다 1회). 유무상증자의 유상 몫은 이미 주식 수가 있어 그대로 써요.
    목록에는 있는데 API 가 결정을 주지 않으면(013) '못 읽은 것'으로 남겨요 — 덮는 수가 모자라 '설명 못 함'이 되면 조회 실패로 봐요.
    v19.1i: terms (dict) 를 주면 유상증자 결정의 방식 · 크기 (parse_rights_terms)도 채워요 — 같은 응답이라 호출이 늘지 않아요."""
    bgn, end = dt.date(fy - 2, 1, 1).strftime("%Y%m%d"), today.strftime("%Y%m%d")
    fx = [{"k": o["k"], "d": o["d"], "n": o["n"], "rc": o["rc"]} for o in oth or [] if o.get("k") in DVWHY_FX_EP and o.get("n")]
    bad = []
    for kind in sorted({o["k"] for o in oth or [] if o.get("k") in DVWHY_FX_EP and not o.get("n")}):
        ep = DVWHY_FX_EP[kind][0]
        j = client.get(ep, {"corp_code": corp, "bgn_de": bgn, "end_de": end})
        if j is None:
            return None, f"{ep} 조회 실패"
        st = str(j.get("status"))
        if st not in ("000", "013"):
            return None, f"{ep} 상태 {st}"
        f2, b2 = parse_dvwhy_fx((j.get("list") or []) if st == "000" else [], kind)
        if terms is not None and kind == "rights" and st == "000":
            terms.update(parse_rights_terms(j.get("list") or []))
        if st == "013":
            b2 = b2 + [{"rc": "", "why": f"목록에는 {DVWHY_OTHER_KO[kind]} 결정이 있는데 {ep} 가 주지 않음"}]
        fx, bad = fx + f2, bad + b2
    return (sorted(fx, key=lambda x: (x["d"] or "", x["rc"])), bad), None


def dvwhy_cover(fx, fy, px):
    """사업보고서 말 뒤 늘어날 수 있는 보통주 수의 위 끝 → (주식 수, 쓴 결정들). 유상증자는 그해 말 반년 앞 ~ px 에 낸 결정의 신주,
    전환사채 · 신주인수권부사채는 목록 기간(fy−2 년 1월 1일 ~ px)의 결정이 만들 수 있는 주식 ÷ 0.7 (전환·행사가액은 발행 때의 70% 밑으로
    내려갈 수 없어요 — 증권의 발행 및 공시 등에 관한 규정 5-23조). (순수 함수)"""
    px = px.isoformat() if isinstance(px, dt.date) else str(px)
    lo = (dt.date(fy, 12, 31) - dt.timedelta(days=DVWHY_OTHER_LOOKBACK_DAYS)).isoformat()
    used = [x for x in fx or [] if x.get("d") and x["d"] <= px and (x["k"] != "rights" or x["d"] > lo)]
    return sum(x["n"] if x["k"] == "rights" else x["n"] / DVWHY_CB_FLOOR for x in used), used


def dvwhy_filed_ok(a, b, fx, fy, px):
    """사업보고서 말 발행 주식 수 a → 오늘 b 로 늘어난 만큼을 유상증자 · 전환사채 · 신주인수권부사채가 설명하는지 → (맞는지, 쓴 결정들).
    늘어난 수 ≤ 덮을 수 있는 수 + a 의 10% (스톡옵션 · 작은 발행). 줄었거나 설명할 결정이 없으면 아니에요. (순수 함수)"""
    a, b = _fin(a), _fin(b)
    cover, used = dvwhy_cover(fx, fy, px)
    ok = bool(used) and a is not None and b is not None and a > 0 and b > a and b - a <= cover + DVWHY_FILED_SLACK * a
    return ok, used


def _ev_desc(evs):
    return " · ".join(f"{DVWHY_KIND_KO.get(e['k'], e['k'])} ×{e['r']:g} ({e['d']})" for e in evs)


def dvwhy_after(f0, fy, px, look):
    """사업보고서 뒤(fy 년 12월 31일 뒤 ~ px) 판정 → (none · ok · mismatch · noname, 설명). (순수 함수)
    none = 당기 배율 1 이고 그 뒤 사건 없음 · ok = 이름 붙일 사건의 곱 = 당기 배율 f0 · noname = f0 ≠ 1 인데 분할·병합·무상증자 공시가
    없음 · mismatch = 곱이 다르거나 깨끗하지 않은 배율이거나, 당기 배율 1 인데 그 뒤 사건이 있음 (새 주식이 아직 상장 전이거나 날짜를
    잘못 읽은 것 — 믿지 않아요)."""
    px = px.isoformat() if isinstance(px, dt.date) else str(px)
    after = [e for e in look.get("ev") or [] if f"{fy}-12-31" < e["d"] <= px and dvwhy_named(e["r"])]
    f0 = _fin(f0)
    if f0 is None or f0 == 1.0:
        return ("mismatch", f"{fy}년 배율은 1 인데 그 뒤 공시 {_ev_desc(after)}") if after else ("none", "")
    if not after:
        return "noname", f"사업보고서 뒤 ×{f0:g} 인데 분할·병합·무상증자 공시가 없음"
    prod = math.prod(e["r"] for e in after)
    if any(not dvwhy_clean(e["r"]) for e in after):
        return "mismatch", f"사업보고서 뒤 ×{f0:g} — 공시 {_ev_desc(after)}: 깨끗하지 않은 배율"
    if abs(prod / f0 - 1) > DVWHY_TOL:
        return "mismatch", f"사업보고서 뒤 ×{f0:g} — 공시 {_ev_desc(after)} = ×{prod:.4g}"
    return "ok", ""


def dvwhy_years(F, fy, f0, px, look, after, lookback=DVWHY_OTHER_LOOKBACK_DAYS):
    """사업보고서 뒤 판정(after: none · ok · filed)이 정해진 뒤 해마다 → [None 또는 {"v", "ev", "f", "why"}] (dpsF 가 1 이거나 빈 해는 None).
    v ok (사건의 곱 = 그해 배율 f) · plain (filed 라 그해는 다시 계산하지 않음, f = 1) · mm (공시와 다름) · nf (사업보고서 안의 변화에 공시
    없음) · nd (filed 옆의 사업보고서 안 변화에 공시 없음 — 조용히 맞추지 않아요). none · ok 는 그해 12월 31일 뒤 ~ px 의 사건으로 그해 dpsF 를,
    filed 는 사업보고서 뒤를 1 로 놓고 그해 12월 31일 뒤 ~ fy 년 12월 31일 사건으로 dpsF ÷ f0 를 설명해야 해요. 10% 이하 변화는 빼요. (순수 함수)"""
    px = px.isoformat() if isinstance(px, dt.date) else str(px)
    out = [None] * 3
    for i in range(3):
        f = _fin(F[i]) if i < len(F) else None
        if f is None or f == 1.0:
            continue
        base, hi = (f / f0, f"{fy}-12-31") if after == "filed" else (f, px)
        if after == "filed" and abs(base - 1) <= DVWHY_TOL:
            out[i] = {"v": "plain", "ev": [], "f": 1.0, "why": ""}
            continue
        start = dt.date(fy - i, 12, 31)
        named = [e for e in look.get("ev") or [] if start.isoformat() < e["d"] <= hi and dvwhy_named(e["r"])]
        if named:
            prod = math.prod(e["r"] for e in named)
            if any(not dvwhy_clean(e["r"]) for e in named):
                out[i] = {"v": "mm", "ev": named, "why": f"{fy - i}년 ×{base:g} — 공시 {_ev_desc(named)}: 깨끗하지 않은 배율"}
            elif abs(prod / base - 1) <= DVWHY_TOL:
                out[i] = {"v": "ok", "ev": named, "f": round(base, 6), "why": ""}
            else:
                out[i] = {"v": "mm", "ev": named, "why": f"{fy - i}년 ×{base:g} — 공시 {_ev_desc(named)} = ×{prod:.4g}"}
            continue
        o0 = (start - dt.timedelta(days=lookback)).isoformat()
        oth = [o for o in look.get("oth") or [] if o.get("k") not in ("cb", "bw")     # 사채 발행은 그 자체로 주식 수를 바꾸지 않아요
               and (not o.get("d") or o0 < o["d"] <= hi)]                           # 날짜를 모르면 그 사이에 있다고 봐요
        if oth:
            out[i] = {"v": "mm", "ev": [], "why": f"{fy - i}년 ×{base:g} — 이름 붙일 공시 없이 "
                      + " · ".join(f"{DVWHY_OTHER_KO.get(o['k'], o['k'])}({o['d']})" for o in oth)}
        elif any(w.get("k") in DVWHY_WD_KINDS for w in look.get("wd") or []):     # 분할·병합·무상증자·감자의 철회만 (사채 철회는 상관없어요)
            out[i] = {"v": "mm", "ev": [], "why": f"{fy - i}년 ×{base:g} — 철회한 분할·병합·무상증자·감자 결정이 있어 '찾지 못했다'고 하지 않아요"}
        elif after == "filed":
            out[i] = {"v": "nd", "ev": [], "why": f"{fy - i}년 ×{base:g} — 사업보고서 안의 변화에 공시가 없어 맞추지 않아요"}
        else:
            out[i] = {"v": "nf", "ev": [], "why": f"{fy - i}년 ×{base:g} — 사업보고서 안의 변화인데 결정 공시가 없음"}
    return out


def dvwhy_decide(F, fy, f0, px, look, after, stop_mm=None):
    """종목 하나의 결론 (after = dvwhy_after 결과, noname 은 호출하는 쪽이 filed · unexplained 로 정해서). (순수 함수)
    → {"st": ok · nf · filed · nc-mismatch · nc-unexplained · None(스위치가 꺼져 맞춤 그대로 · 줄 없음), "fac": {해: 새 배율},
       "dem": {해: nc · nd}, "hide": nc · nd · None (배당한 모든 해를 비교 불가로 — 수익률을 숨겨요), "ev", "old", "why": [설명]}"""
    stop_mm = DVWHY_STOP_ON_MISMATCH if stop_mm is None else stop_mm
    out = {"st": None, "fac": {}, "dem": {}, "hide": None, "ev": [], "old": None, "why": []}
    if after == "unexplained":
        return {**out, "st": "nc-unexplained", "hide": "nd"}
    if after not in ("none", "ok", "filed"):            # mismatch
        return {**out, "st": "nc-mismatch" if stop_mm else None, "hide": "nc" if stop_mm else None}
    yr = dvwhy_years(F, fy, f0, px, look, after)
    v = {i: y["v"] for i, y in enumerate(yr) if y}
    out["why"] = [y["why"] for y in yr if y and y["v"] in ("mm", "nd")]
    kinds = set(v.values())
    if after != "filed" and kinds == {"ok", "nf"}:      # 어떤 해는 공시로 설명되는데 다른 해는 공시 없음 — 섞여 말하면 믿지 않아요
        kinds = {"mm"}
        out["why"] = [y["why"] + " (다른 해는 공시로 설명돼요)" for y in yr if y and y["v"] == "nf"]
    if "mm" in kinds:
        return {**out, "st": "nc-mismatch" if stop_mm else None, "hide": "nc" if stop_mm else None}
    oks = [i for i, x in v.items() if x == "ok"]
    out["old"] = max(oks) if oks else (max(v) if v else None)
    out["ev"] = yr[max(oks)]["ev"] if oks else []
    if after == "filed":                                # 사업보고서 뒤는 1 (공시된 배당 그대로) · 사업보고서 안 변화는 공시로 확인한 것만
        out["fac"] = {i: yr[i]["f"] for i, x in v.items() if x in ("ok", "plain")}
        out["dem"] = {i: "nd" for i, x in v.items() if x == "nd"}
        return {**out, "st": "filed"}
    return {**out, "st": "ok" if kinds == {"ok"} else "nf"}


def dvwhy_apply(r, dps3, dec):
    """dvwhy_decide 의 결론을 div_basis 결과 r 에 (새 배율 · 맞추지 않은 해 · 수익률 숨김) 넣고 divSt 를 다시 정해요. (순수 함수)"""
    if not (dec["fac"] or dec["dem"] or dec["hide"]):
        return r
    r = {**r, "dps3a": list(r["dps3a"]), "dpsF": list(r["dpsF"]), "st3": list(r["st3"])}
    d3 = _three(dps3)
    for i, f in dec["fac"].items():
        r["dpsF"][i] = round(f, 6)
        r["dps3a"][i] = round(d3[i] / r["dpsF"][i], 2)
        r["st3"][i] = "same" if r["dpsF"][i] == 1.0 else "adj"
    for i, st in dec["dem"].items():
        r["dps3a"][i], r["dpsF"][i], r["st3"][i] = None, None, st
    if dec["hide"]:
        for i in range(3):
            if r["st3"][i] in ("same", "adj"):
                r["dps3a"][i], r["dpsF"][i], r["st3"][i] = None, None, dec["hide"]
    paid = [x for x in r["st3"] if x in ("same", "adj", "nc", "nd")]
    if paid:
        r["divSt"] = next(x for x in ("nc", "nd", "adj", "same") if x in paid)
    return r


def dvwhy_event_out(e):
    """발행하는 사건 하나: k · d · r (· 무상증자는 x) · rc."""
    o = {"k": e["k"], "d": e["d"], "r": round(e["r"], 6)}
    if e["k"] == "bonus":
        o["x"] = e["x"]
    o["rc"] = e["rc"]
    return o


# ────────────────────────────────────────────────────────────
# v19.1i: 배당 기준 증명 (Jack, 2026-11-14 · '주식 수가 바뀐 뒤 배당수익률이 없는 72곳 — 계산을 고쳐요')
# ────────────────────────────────────────────────────────────
# div_basis 가 오늘 주식 수 기준을 찾지 못한 해(비교 불가 nc · 알 수 없음 nd)를, 어림하지 않고 증명할 수 있을 때만 되살려요.
# 2026-11-14 발행본(pxDate 11-13)으로 시험: 수익률이 없던 배당 회사 72곳 중 되살림 29 (총액 ÷ 오늘 주식 수 16 · 그해 말 주식 수 13) ·
# 그대로: 깨끗하지 않은 무상증자 배율 7 · 회사분할 · 주식배당 결정 4 · 주주배정 유상증자 7 · 수를 읽지 않는 공시(교환 · 소각) 2 · 배당 표 자체가
# 어긋남(중간배당 · 단위 · 총액 없음) 22 · 30% 넘는 수익률 1 (주식 수 문제 아님) — Jack 의 줄이 붙는 종목은 0. 막대가 없던 86곳 중 23곳의 막대를 되살림.
#   배율 F   그해 12월 31일 뒤 ~ pxDate 의 이름 붙일 사건(액면분할 · 주식병합 · 무상증자 · 주식병합으로 한 감자)의 곱 — dvWhy 와 같은
#            DART 결정 공시 조회 · 같은 캐시 항목. 깨끗한 배율만 써요 (관문이 받는 배율 — 1.3 · 1.5 · 1.66 처럼 깨끗하지 않은 무상증자
#            배율을 쓰려면 관문을 바꿔야 해서 Jack 이 정할 때까지 숨겨요 · 로그에 그 배율로 계산한 값을 남겨요).
#   막는 것  그 사이(그해 말 반년 앞부터)의 회사분할 결정(인적분할은 1주의 몫을 바꿔요)과 주식배당 결정 — 있으면 증명하지 않아요.
#   올해(당기): 배당 받은 보통주 수 n = (현금배당금총액 − 우선주 몫) ÷ 보통주 주당 배당. 둘 중 하나로 맞춰 봐요 (± PROVE_TOL 3%).
#     today    배당 총액 ÷ 오늘 상장 주식 수 = 주당 배당 ÷ F — n × F 가 오늘 상장 보통주 수와 같아요 (자기주식이 적고 그 뒤 발행이 없는 회사).
#     yearEnd  n = 그해 말 보통주 유통 주식 수 (주식의 총수 현황 · 배당 기준일이 그해 말) 이고, 오늘 상장 주식 수가
#              그해 말 유통 주식 수 × F × 0.97 이상 (그 뒤 줄어든 만큼은 자기주식 소각만), (그해 말 발행 주식 수 × F + 그 뒤 유상증자 · 전환사채 ·
#              신주인수권부사채가 만들 수 있는 주식 수 — 결정마다 그 뒤의 사건만큼만 늘려서) × 1.03 이하.
#   주주배정 유상증자 (리뷰 2026-11-15): 그해 말 반년 앞 ~ px 에 공시된 유상증자 결정 중 주주배정(주주배정후 실권주 일반공모 포함) · 방식을 모름이
#     새 주식이 증자 전의 10%를 넘으면 되살리지 않아요 (어느 길로 맞췄든 · 방식을 읽지 못하면 조회 실패) — 권리락 날 거래소가 기준가를 낮춰
#     오늘 주가는 새 기준인데 공시된 1주 배당은 옛 기준이라서 (rights). 앞 해 막대도
#     두 해 사이에 그런 유상증자가 있으면 그대로. 제3자배정 · 일반공모 · 사채는 Jack 의 답 2 (2026-11-08) 대로 공시된 배당 그대로 써요.
#   앞 해(전기 · 전전기): 올해 기준이 확인됐고 올해 배율이 공시 사건의 곱과 같을 때만. 두 해 사이의 사건 곱 g 와 배당 받은 주식 수의
#     비 n₀ ÷ nᵢ 가 ± DRIFT_TOL(15%, 자기주식 매입·소각) 안이면 dpsF = 올해 배율 × g. 회사가 새 기준으로 고쳐 적은 해와 헷갈리면
#     (g ≠ 1 인데 그 비가 1 근처) 하지 않아요. 우선주 배당이 있는 해는 하지 않아요.
#   결과: 되살린 종목에 dvProof (관문이 같은 숫자로 다시 맞춰 봐요) · 배율이 1 이 아닌 해가 생기면 dvWhy ok (사건).
#     되살리지 않으면 이유(divCheck.proof)만 남기고 그대로예요 — Jack 의 줄 '주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여
#     드리지 않아요.' 은 그 말이 맞을 때만: 주식 수가 바뀌었는데 그 사이에 주식 수를 바꾸는 공시가 하나도 없을 때 (line → dvWhy
#     nc-unexplained 와 dvLine = 1 · 앱은 dvLine 에만 줄 — 맞춤 이유(#98)의 nc-unexplained 만으로는 줄이 없어요). 공시가 배율을 주는데 깨끗하지 않음(ratio) · 회사분할 · 주식배당(basis) · 주주배정
#     유상증자(rights) · 수를 읽지 않는 공시가 있음(uncounted) · 배당 표 자체가 어긋남(data)은 줄 없이 이름만 크게 · 조회 실패는 아무것도
#     바꾸지 않아요 (fail · 다음 실행이 다시).
# 호출: 다시 계산한 해가 없는 종목도 조회해요 (회사당 목록 2 + 결정 1~2, 그해 말 주식의 총수 현황 1 · 유상증자 · 사채 주식 수 0~2).
# 2026-11-14 데이터로 약 160곳 (72 + 86) — 첫 실행 약 600회 (실행당 PROVE_PER_RUN 곳 · dvWhy 의 한도와 따로 · 넘으면 다음 실행), 그 뒤 하루 0~10회.
DIV_PROVE = True
PROVE_TOL = 0.03
PROVE_KEYS = ("today", "yearEnd", "years", "line", "ratio", "basis", "rights", "uncounted", "data", "fail")
PROVE_HID = PROVE_KEYS[3:]        # 되살리지 않은 이유 (종목 이름도 적어요 · line 만 앱이 Jack 의 줄을 보여 줘요)
PROVE_EST_STOCKS = 160            # 전체 DART 실행 어림: 증명할 종목 약 160곳 × PROVE_PER_STOCK 회
PROVE_PER_STOCK = 4
PROVE_PER_RUN = 150               # 한 실행에서 증명을 위해 새로 조회하는 회사 수 상한 (dvWhy 의 DVWHY_PER_RUN 과 따로 · 넘으면 다음 실행)
PROVE_LOOK_V = 1                  # 증명용 조회 항목의 모양 (sd · cx · rt · shr 를 적은 항목) — 다르면 증명할 때 한 번 다시 받아요
PROVE_SHR_MOVE = 0.03             # 조회 뒤 오늘 상장 주식 수가 이보다 많이 달라지면 공시 목록을 다시 받아요 (그 사이 새 결정이 있을 수 있어요)


# v19.1j (Jack, 2026-11-15 — 11-15 아침 답 11 · 12 · 13):
#   답 12 — 공시가 준 정확한 무상증자 배율은 깨끗한 분할 배율이 아니어도 받아요 (대한제강 ×1.6616554 · TJ미디어 ×1.5 · 알테오젠 ×1.3 …),
#     세 가지를 모두 지킬 때만 (리뷰의 세 조건): (가) 깨끗하지 않은 배율의 사건은 모두 무상증자 결정 API(fricDecsn · pifricDecsn)에서 읽은
#     무상증자이고 r = 1 + x (x = 보통주 1주당 신주 수, API 의 값) · (나) 그 사건들의 곱(1 + x 로 셈)이 발행하는 배율(dpsF)과 1e-6 안 ·
#     (다) 배당 기준 증명(dvProof)이 주식 수로 맞아요 (today · yearEnd 그대로). 파이프라인이 주식 수로 짐작한 배율(div_basis 의 배율)은 예전처럼
#     깨끗한 배율만이고, 공시 원문(분할 · 병합)이나 감자 결정의 깨끗하지 않은 배율은 예전처럼 그대로 숨겨요 (ratio). 관문도 같은 세 조건을 따로 봐요.
#   답 11 · 13 — 숨긴 이유마다 앱이 보여 줄 줄을 여기 한 곳에서 정해요 (prove_line → 종목의 dvLine · divCheck.proofSub):
#     1 line   Jack 의 줄 (2026-11-08) '주식 수가 바뀐 비율을 공시로 확인하지 못해 배당수익률은 보여 드리지 않아요.'
#     2 rights '유상증자로 주가 기준이 바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요.' — 막은 유상증자 중 주주배정(실권주 일반공모
#              포함)이라고 읽은 결정이 있고, 그 새 주식이 오늘 상장 주식 수에 들어 있을 때만 (sh: 권리락이 지났다는 증거 — 상장은 납입 뒤예요).
#              새 주식이 아직 보이지 않으면 (shnew: 권리락 전일 수 있어요) · 방식을 모르는 결정만으로 막았으면 (unk) 줄 없음.
#     3 data   '회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요.' — 배당 표의 총액 ÷ 주당 배당이 회사의 그해 말
#              유통 주식 수(주식의 총수 현황)와도, 오늘 상장 주식 수 ÷ 배율과도 3% 넘게 다를 때만 (div · 2026-11-15 원문 확인: 중간배당이 든 총액 ·
#              주당 배당 칸의 총액 · 우선주 줄 없는 총액 …).
#     4 data   (Jack, 2026-11-19 '이유 없는 빈칸은 없게') '회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요.' — 회사의
#              공시에 계산에 필요한 조각이 빠졌을 때: nototal 배당 표에 총액 없음 · nostk 그해 말 주식의 총수 현황 없음(읽을 표가 없음) · pref0 배당 표에
#              우선주 줄이 있는데 주식의 총수 현황에 우선주 수가 따로 없음 (의결권 있는 우선주는 보통주와 한 줄에 적혀요 — 메디톡스) · nopfo 우선주
#              주식 수를 모름 (주식의 총수 현황 없음) · prefmix 주당 배당이 다른 종류주가 섞였는데 종류마다의 주식 수가 공시에 없음.
#     줄 없음  neg 총액이 우선주 몫보다 작음 (어긋남인지 우리가 종류주를 잘못 묶었는지 몰라요) · noshr 오늘 상장 주식 수 없음 (회사 공시가 아니라
#              거래소 목록) — 2026-11-14 · 11-17 에 0곳 · other prove_receiving 이 PROVE_DATA_WHY 에 없는 이유 글을 돌려줌 (새 글에 이름을 붙이기 전:
#              어느 줄이 맞는지 몰라요 — 리뷰 2026-11-19) → 줄 없음 · 로그에 '!!' 와 수 · 관문의 '숨긴 배당수익률의 줄' 줄이 경고.
PROVE_EXACT_TOL = 1e-6            # 답 12 (나): 정확한 무상증자 배율의 곱(1 + x)과 발행하는 배율(dpsF)의 차이 상한
PROVE_LINE = {"line": 1, "rights": 2, "data": 3, "missing": 4}         # dvLine 값 (앱이 줄을 고르는 표시)
PROVE_SUB = {"rights": ("sh", "shnew", "unk"),
             "data": ("div", "pref0", "neg", "nototal", "prefmix", "nopfo", "nostk", "noshr", "other")}
PROVE_SUB_LINE = {"rights": {"sh": 2},                                 # 경우 → 줄 (말이 그대로 맞을 때만 · 없으면 줄 없음)
                  "data": {"div": 3, "nototal": 4, "nostk": 4, "pref0": 4, "nopfo": 4, "prefmix": 4}}
PROVE_DATA_WHY = {"현금배당금총액 없음": "nototal", "주당 배당이 다른 우선주·종류주가 섞여 있어요": "prefmix",
                  "우선주·종류주 주식 수를 몰라요": "nopfo", "우선주·종류주 배당 줄이 있는데 그해 말 우선주·종류주가 없어요": "pref0",
                  "우선주 몫을 빼면 0 이하": "neg"}
PROVE_SUB_KO = {"sh": "주주배정 (새 주식 상장됨)", "shnew": "주주배정 (새 주식이 아직 상장 전)", "unk": "방식을 모르는 결정만", "div": "총액 ÷ 주당 배당이 주식 수와 다름", "pref0": "우선주 배당 줄이 있는데 주식의 총수 현황에 우선주 수가 따로 없음",
                "neg": "총액이 우선주 몫보다 작음", "nototal": "총액 없음", "prefmix": "주당 배당이 다른 종류주가 섞임", "nopfo": "우선주 주식 수 모름",
                "nostk": "그해 말 주식의 총수 현황 없음", "noshr": "오늘 상장 주식 수 없음", "other": "이름을 붙이지 않은 배당 표 이유"}


def prove_line(reason, sub=None):
    """숨긴 이유(reason)와 그 안의 경우(sub) → 앱이 보여 줄 줄의 표시(dvLine 1 · 2 · 3 · 4) 또는 None (줄 없음). 줄은 그 말이 그대로 맞을 때만:
    line 은 늘(1), rights 는 주주배정이라고 읽은 결정이 있을 때(sh → 2), data 는 배당 표가 회사의 주식 수와 실제로 어긋날 때(div → 3) ·
    회사 공시에 계산에 필요한 조각이 빠졌을 때(nototal · nostk · pref0 · nopfo · prefmix → 4, Jack 2026-11-19). 그 밖(shnew · unk · neg · noshr ·
    other — 이름을 붙이지 않은 배당 표 이유)은 None. (순수 함수)"""
    if reason == "line":
        return PROVE_LINE["line"]
    return PROVE_SUB_LINE.get(reason, {}).get(sub)


def prove_exact_bonus(e):
    """답 12 (가): 무상증자 결정 API(fricDecsn · pifricDecsn)에서 읽은 무상증자 사건이고 r = 1 + x 인지 (x 는 API 의 1주당 신주 수). (순수 함수)"""
    x, r = _fin((e or {}).get("x")), _fin((e or {}).get("r"))
    return (isinstance(e, dict) and e.get("k") == "bonus" and e.get("src") in ("fric", "pifric")
            and x is not None and x > 0 and r is not None and abs(r - (1 + x)) <= PROVE_EXACT_TOL)


def prove_ev_ok(ev):
    """사건마다 깨끗한 분할 배율이거나, 답 12 의 정확한 무상증자(prove_exact_bonus)인지. (순수 함수)"""
    return all(dvwhy_clean(e["r"]) or prove_exact_bonus(e) for e in ev or [])


def prove_prod(ev):
    """사건의 곱 — 정확한 무상증자는 API 의 1 + x 로 (반올림한 r 이 아니라), 다른 사건은 r 로. 사건이 없으면 1. (순수 함수)"""
    return float(math.prod((1 + e["x"]) if prove_exact_bonus(e) else e["r"] for e in ev or []))


def prove_same(prod, f, exact):
    """사건의 곱 prod 와 배율 f 가 같은지: 정확한 무상증자가 끼면 |prod − f| ≤ 1e-6 (답 12 (나)), 아니면 예전처럼 ± DVWHY_TOL. (순수 함수)"""
    if not f:
        return False
    return abs(prod - f) <= PROVE_EXACT_TOL if exact else abs(prod / f - 1) <= DVWHY_TOL


def prove_shr_moved(old, now):
    """조회 뒤 오늘 상장 주식 수가 PROVE_SHR_MOVE(3%) 넘게 달라졌는지. 둘 중 하나라도 모르면 달라지지 않은 것으로 봐요 (주식 수가 없는 종목이
    날마다 다시 받지 않게 · 그런 항목도 90일 재확인은 그대로). (순수 함수)"""
    old, now = _fin(old), _fin(now)
    return bool(old and now and old > 0 and now > 0) and abs(now / old - 1) > PROVE_SHR_MOVE


def prove_window(look, lo, hi, lookback=DVWHY_OTHER_LOOKBACK_DAYS):
    """lo 뒤 ~ hi (날짜 글자)의 이름 붙일 사건 (오래된 것부터)과 막는 결정 종류 [spin · stockdiv] — 결정은 공시일이라 lo 의 반년
    앞부터 봐요 (날짜를 모르면 그 사이에 있다고 봐요). (순수 함수)"""
    ev = [e for e in look.get("ev") or [] if lo < e["d"] <= hi and dvwhy_named(e["r"])]
    o0 = (dt.date.fromisoformat(lo) - dt.timedelta(days=lookback)).isoformat()
    blk = {o["k"] for o in look.get("oth") or [] if o.get("k") == "spin" and (not o.get("d") or o0 < o["d"] <= hi)}
    blk |= {"stockdiv" for x in look.get("sd") or [] if not x.get("d") or o0 < x["d"] <= hi}
    return sorted(ev, key=lambda e: (e["d"], e["rc"])), sorted(blk)


def prove_receiving(cash, d, pds, pfo=None):
    """그해 배당을 받은 보통주 수 n = (현금배당금총액 − 우선주 몫) ÷ 보통주 주당 배당 → (n, 우선주 주당 배당 또는 None, 이유).
    우선주 몫은 그해 말 우선주·종류주 유통 주식 수(pfo, 주식의 총수 현황) × 우선주 주당 배당 — 배당 받은 종류가 모두 같은 주당
    배당일 때만 셀 수 있어요 (0 이나 모르는 종류가 섞이면 None). (순수 함수)"""
    cash, d = _fin(cash), _fin(d)
    if not cash or cash <= 0 or not d or d <= 0:
        return None, None, "현금배당금총액 없음"
    vals = [_fin(x) for x in pds or []]
    paid = [x for x in vals if x is not None and x > 0]
    if not paid:
        return cash / d, None, None
    if len(set(paid)) > 1 or len(paid) != len(vals):
        return None, None, "주당 배당이 다른 우선주·종류주가 섞여 있어요"
    pfo = _fin(pfo)
    if pfo == 0 and paid[0] == d:
        return cash / d, None, None        # 그해 말 우선주·종류주가 없어요 — 보통주와 같은 금액의 줄은 표의 중복 (실리콘투 2025)
    if pfo == 0:                           # v19.1j: 주식의 총수 현황에 그 밖의 종류가 따로 없어요 (의결권 있는 우선주는 보통주와 한 줄 — 메디톡스)
        return None, None, "우선주·종류주 배당 줄이 있는데 그해 말 우선주·종류주가 없어요"
    if not pfo or pfo <= 0:
        return None, None, "우선주·종류주 주식 수를 몰라요"
    n = (cash - pfo * paid[0]) / d
    return (n, paid[0], None) if n > 0 else (None, None, "우선주 몫을 빼면 0 이하")


def prove_today(n, f, shr, tol=PROVE_TOL):
    """배당 총액 ÷ 오늘 주식 수 = 오늘 1주 배당: n × f ÷ 오늘 상장 보통주 수가 1 ± tol. (순수 함수)"""
    n, f, shr = _fin(n), _fin(f), _fin(shr)
    return bool(n and f and shr and n > 0 and f > 0 and shr > 0) and abs(n * f / shr - 1) <= tol


def prove_year_end(n, f, shr, stk, cover=0.0, tol=PROVE_TOL):
    """그해 말 주식의 총수 현황으로 → (맞는지, 이유: nostk 표 없음 · div 배당 받은 주식 수가 유통 주식 수와 다름 · down 오늘이 더 적음 ·
    up 오늘이 더 많음 · 덮는 수 cover 를 더해도). cover 는 오늘 주식 수로 센 수 (prove_cover — 결정마다 그 뒤 사건만큼 늘린 수). (순수 함수)"""
    n, f, shr = _fin(n), _fin(f), _fin(shr)
    cmo, cmi = _fin((stk or {}).get("cmo")), _fin((stk or {}).get("cmi"))
    if not cmo or cmo <= 0 or not cmi or cmi <= 0 or cmi < cmo * (1 - 1e-9):
        return False, "nostk"
    if not n or abs(n / cmo - 1) > tol:
        return False, "div"
    if shr < cmo * f * (1 - tol):
        return False, "down"
    if shr > (cmi * f + (cover or 0.0)) * (1 + tol):
        return False, "up"
    return True, None


def prove_cover(fx, fy, px, ev):
    """dvwhy_cover 와 같은 결정들 (그해 말 반년 앞 ~ px 의 유상증자 · 목록 기간의 사채) → (오늘 주식 수로 센 덮는 수, 쓴 결정들).
    결정마다 그 공시일 뒤(그리고 그해 말 뒤)의 분할 · 병합 · 무상증자(ev)만큼만 늘려요 (리뷰 2026-11-15: 유무상증자의 유상 몫은 그 뒤
    무상증자를 받고, 무상증자 뒤의 유상증자는 받지 않아요). (순수 함수)"""
    _, used = dvwhy_cover(fx, fy, px)
    after0 = f"{fy}-12-31"
    tot = 0.0
    for x in used:
        base = x["n"] if x["k"] == "rights" else x["n"] / DVWHY_CB_FLOOR
        cut = max(x["d"], after0)
        tot += base * prove_prod([e for e in ev or [] if e["d"] > cut])     # v19.1j: 정확한 무상증자는 1 + x 로 (관문과 같은 셈)
    return tot, used


def prove_earlier(d3, cash3, pds, f0, look, fy, i, tol=DRIFT_TOL):
    """앞 해 i (1 전기 · 2 전전기)의 배율 → (f, None) 또는 (None, 이유). 올해 배율 f0 은 확인된 값이에요 (반올림 전의 곱). (순수 함수)
    g = 그해 말 뒤 ~ 올해 말 사건의 곱 (깨끗한 배율 · v19.1j 공시의 정확한 무상증자 1 + x) · 막는 결정 없음 · 우선주 배당 없음 · n₀ ÷ nᵢ 가 g ± tol 이고
    (g ≠ 1 이면) 1 ± tol 이 아니어야 해요 (회사가 그해 배당을 새 기준으로 고쳐 적었는지 알 수 없으면 하지 않아요)."""
    d, c = _three(d3), _three(cash3)
    if any((_fin(x) or 0) > 0 for p in pds or [] for x in (_three(p)[0], _three(p)[i])):
        return None, "pref"
    if not (d[0] and d[0] > 0 and d[i] and d[i] > 0 and c[0] and c[0] > 0 and c[i] and c[i] > 0):
        return None, "div"
    ev, blk = prove_window(look, f"{fy - i}-12-31", f"{fy}-12-31")
    if not prove_ev_ok(ev):                            # v19.1j: 깨끗한 배율 · 공시의 정확한 무상증자(답 12)만
        return None, "nonclean"
    if blk:
        return None, "block"
    g = prove_prod(ev)
    rr = (c[0] / d[0]) / (c[i] / d[i])
    if abs(rr / g - 1) > tol:
        return None, "drift"
    if abs(g - 1) > 1e-9 and abs(rr - 1) <= tol:
        return None, "restated"
    return round(f0 * g, 6), None


class DivWhy:
    """v19.1h: apply_div_basis 가 다시 계산한 해가 있는 종목마다 불러요 (check). 결론을 dvWhy.st 로 달고(ok · nf · filed · nc-mismatch ·
    nc-unexplained), 그에 맞게 배율을 고쳐요. client 가 없으면(DART 꺼짐 · 키 없음) 모두 조회 실패로 세요 (줄 없음 · 맞춤은 그대로)."""

    def __init__(self, client, px_date, cmap=None, stop_mm=None, stop_nfa=None, prove=None):
        self.client, self.px = client, px_date
        self.cmap = cmap if cmap is not None else (((client.meta.get("corpMap") if client else None)) or {})
        self.stop_mm = DVWHY_STOP_ON_MISMATCH if stop_mm is None else stop_mm
        self.stop_nfa = DVWHY_STOP_ON_NF_AFTER_REPORT if stop_nfa is None else stop_nfa
        self.n = collections.Counter()
        self.t = {k: [] for k in DVWHY_ST + ("fail", "kept")}
        self.notes = []                 # 크게 남길 줄 (공시와 다름 · 설명 못 함 · 공시 없음 · 조회 실패)
        self.ok_ex = []                 # 이유를 확인한 종목 (로그에 몇 개)
        self.fetch_left = DVWHY_PER_RUN
        self.calls0 = sum(client.status.values()) if client else 0
        # v19.1i: 배당 기준 증명 (prove). seen = check 가 쓴 조회 {코드: (look, 그때의 dpsF) 또는 None(조회 실패)} — prove 가 같은
        # 캐시 항목을 다시 받지 않게 · pv = 결과마다 종목 (PROVE_KEYS) · pnotes = 크게 남길 줄
        self.prove_on = DIV_PROVE if prove is None else prove
        self.prove_left = PROVE_PER_RUN
        self.seen = {}
        self.pv = {k: [] for k in PROVE_KEYS}
        self.psub = {k: {} for k in PROVE_SUB}        # v19.1j: rights · data 안의 경우 {코드: sub} (divCheck.proofSub · 줄을 고르는 근거)
        self.pnotes, self.p_ex = [], []

    def _fail(self, s, why):
        self.t["fail"].append(s["t"])
        self.notes.append(f"조회 실패 {s['t']} {s.get('nk', '')}: {why} → 이유 줄 없음 (맞춤은 그대로)")

    def _look(self, corp, fy, F, tag="", prove=False, shr=None):
        """캐시를 거친 조회 → (look, 어떻게) 또는 (None, 실패 이유).
        v19.1i: 새로 받은 항목에는 증명용 모양 표시(pv)와 그때의 오늘 상장 주식 수(shr)를 함께 적어요. prove — 배당 기준 증명이 쓸 때:
        표시가 없는 예전 항목(주식배당 · 소각 · 유상증자 방식을 적기 전)이나, 받은 뒤 상장 주식 수가 PROVE_SHR_MOVE(3%) 넘게 달라진
        항목은 다시 받아요 (그 사이 새 공시가 있을 수 있어요 · 같은 키에 저장). 증명의 새 조회는 따로 센 한도(PROVE_PER_RUN)를 써요 —
        맞춤 이유(check)의 한도를 빼앗지 않게."""
        left, cap = ("prove_left", PROVE_PER_RUN) if prove else ("fetch_left", DVWHY_PER_RUN)
        c = self.client
        key = f"{corp}|{DVWHY_TAG}"
        with c.lock:
            e = c.entries.get(key)
        d = (e or {}).get("d") if (e or {}).get("st") == "000" else None
        same = bool(d) and d.get("fy") == fy and d.get("F") == F
        refetch = False
        if same and prove and (d.get("pv") != PROVE_LOOK_V or prove_shr_moved(d.get("shr"), shr)):
            same, refetch = False, True
        if same and c.mode != "full":
            age = (c.today - dt.date.fromisoformat(e["at"])).days
            redo = bool(d.get("bad")) and age >= DART_RETRY_DAYS
            with c.lock:
                reval = (not redo and age > DART_REVALIDATE_DAYS and c.revalidate_left > 0 and not c.down and not c.fatal)
                if reval:
                    c.revalidate_left -= 1
                    c.revalidated += 1
            if not redo and not reval:
                self.n["pCache" if prove else "cache"] += 1
                return d, "cache"
        if getattr(self, left) <= 0:
            if same:
                self.n["pCache" if prove else "cache"] += 1
                return d, "cache"
            self.n["pLimit" if prove else "limit"] += 1
            return None, f"이번 실행의 새 조회 한도({cap}곳)에 닿음 — 다음 실행에서 받아요"
        setattr(self, left, getattr(self, left) - 1)
        self.n["pRefetch"] += refetch           # 다시 받기를 실제로 할 때만 세요 (한도에 막히면 세지 않아요)
        look, why = dvwhy_fetch(c, corp, fy, c.today)
        if look is None:
            if same:
                self.n["stale"] += 1         # 어제(같은 dpsF · fy) 결과를 그대로 써요
                self.notes.append(f"다시 조회 실패 {tag or corp}: {why} → 같은 배율·사업보고서 연도로 확인한 지난 결과를 써요")
                return d, "kept"
            return None, why
        self.n["pFetched" if prove else "fetched"] += 1
        d = {"fy": fy, "F": list(F), "end": c.today.isoformat(), **look, "pv": PROVE_LOOK_V,
             **({"shr": int(round(_fin(shr)))} if _fin(shr) else {})}
        with c.lock:
            c.entries[key] = {"st": "000", "at": c.today.isoformat(), "d": d}
        return d, "fetched"                  # 캐시 항목과 같은 dict — 나중에 붙이는 주식 수(fx)도 함께 저장돼요

    def _fx(self, corp, fy, look, need_terms=False):
        """유상증자 · 전환사채 · 신주인수권부사채의 주식 수 (캐시 항목에 붙여 둬요) → (fx, 못 읽은 것, None) 또는 (None, None, 실패 이유).
        v19.1i: 유상증자 결정의 방식 · 크기(fxT, parse_rights_terms)도 같은 응답에서 적어요. need_terms 인데 fxT 가 없는 예전 항목은 다시 받아요."""
        if "fx" in look and (not need_terms or "fxT" in look):
            return look["fx"], look.get("fxBad") or [], None
        terms = {}
        got, why = dvwhy_fetch_fx(self.client, corp, fy, self.client.today, look.get("oth"), terms=terms)
        if got is None:
            return None, None, why
        fx, bad = got
        look["fx"], look["fxBad"], look["fxT"] = fx, bad, terms   # 캐시 항목의 d 와 같은 dict 라 함께 저장돼요
        return fx, bad, None

    def check(self, s, r):
        """div_basis 결과 r → 결론에 맞게 고친 r. s 에 dvWhy 를 달아요 (조회가 끝났을 때만)."""
        F = [_fin(f) for f in r["dpsF"]]   # NaN 이 캐시·파일에 들어가지 않게 (div_basis 는 늘 유한한 값이지만)
        if not any(f is not None and f != 1.0 for f in F):
            return r
        self.n["adj"] += 1
        t, fy = s["t"], s.get("fy")
        corp = self.cmap.get(t)
        if self.client is None:
            self._fail(s, "DART 꺼짐 · 키 없음")
            return r
        if not corp or not isinstance(fy, int):
            self._fail(s, "DART 기업코드 또는 사업보고서 연도 없음")
            return r
        tag = f"{t} {s.get('nk', '')}".strip()
        look, how = self._look(corp, fy, F, tag, shr=s.get("shr"))
        self.seen[t] = (look, F) if look is not None and not look.get("bad") else None   # v19.1i: prove 가 다시 쓰거나 건너뛰어요
        if look is None:
            self._fail(s, how)
            return r
        if look.get("bad"):
            self._fail(s, "공시를 읽지 못함: " + " · ".join(f"{b.get('rc') or '-'} {b.get('why')}" for b in look["bad"][:3]))
            return r
        f0 = _fin(r.get("f0"))
        after, why_after = dvwhy_after(f0, fy, self.px, look)
        a = b = None
        used = []
        if after == "noname":
            if not self.stop_nfa:
                self.t["kept"].append(t)
                self.notes.append(f"설명 못 함 {tag}: {why_after} → 맞춤은 그대로, 이유 줄 없음 (스위치 꺼짐)")
                return r
            if look.get("nI") == 0:
                self._fail(s, "거래소 수시공시 목록이 비어 있어요 (배당하는 회사는 현금배당결정을 내요) — '설명 못 함'으로 결론 내지 않아요")
                return r
            fx, fx_bad, why = self._fx(corp, fy, look)
            if fx is None:
                self._fail(s, why)
                return r
            stk = dart_shares(self.client, corp, fy)
            a, b = _fin((stk or {}).get("cmi")), _fin(s.get("shr"))
            if not a or a <= 0 or not b or b <= 0:
                self._fail(s, f"{fy}년 말 발행 주식 수(주식의 총수 현황)를 받지 못함")
                return r
            ok, used = dvwhy_filed_ok(a, b, fx, fy, self.px)
            if not ok and fx_bad:                # 못 읽은 결정이 덮었을 수도 있어요 — 수익률을 숨기지 않고 조회 실패로
                self._fail(s, "유상증자·사채 결정의 주식 수를 다 읽지 못해 설명하는지 알 수 없음: "
                           + " · ".join(f"{x['rc'] or '-'} {x['why']}" for x in fx_bad[:3]))
                return r
            after = "filed" if ok else "unexplained"
            if not ok:
                cover, _ = dvwhy_cover(fx, fy, self.px)
                why_after += f" · 발행 주식 수 {a:,.0f} → {b:,.0f}, 유상증자·전환사채·신주인수권부사채로 덮을 수 있는 수 {cover:,.0f}"
        dec = dvwhy_decide(F, fy, f0, self.px, look, after, self.stop_mm)
        if dec["st"] is None:                    # 공시와 다른데 스위치가 꺼져 있음
            self.t["kept"].append(t)
            self.notes.append(f"공시와 다름 {tag}: " + " / ".join([why_after] if why_after else dec["why"])
                              + " → 맞춤은 그대로, 이유 줄 없음 (스위치 꺼짐)")
            return r
        st = dec["st"]
        if st == "nf":
            if look.get("nI") == 0:
                self._fail(s, "거래소 수시공시 목록이 비어 있어요 (배당하는 회사는 현금배당결정을 내요) — '찾지 못했지만'으로 결론 내지 않아요")
                return r
            stk = dart_shares(self.client, corp, fy - dec["old"])
            a, b = _fin((stk or {}).get("cmi")), _fin(s.get("shr"))
            f_old = F[dec["old"]]
            if not a or a <= 0 or not b or b <= 0:
                self._fail(s, f"{fy - dec['old']}년 말 발행 주식 수(주식의 총수 현황)를 받지 못함")
                return r
            if round(a) == round(b) or abs((b / a) / f_old - 1) > SHARE_SAME:
                dec = dvwhy_decide(F, fy, f0, self.px, look, "mismatch", self.stop_mm)
                dec["why"] = [f"공시가 없고 발행 주식 수 {a:,.0f} → {b:,.0f} (×{b / a:.3f})가 ×{f_old:g} 와 달라요"]
                st = dec["st"]
                if st is None:
                    self.t["kept"].append(t)
                    self.notes.append(f"공시와 다름 {tag}: {dec['why'][0]} → 맞춤은 그대로, 이유 줄 없음 (스위치 꺼짐)")
                    return r
        r = dvwhy_apply(r, s.get("dps3"), dec)
        self.t[st].append(t)
        if st == "ok":
            s["dvWhy"] = {"v": 1, "st": "ok", "ev": [dvwhy_event_out(e) for e in dec["ev"]]}
            self.ok_ex.append(f"{tag} " + _ev_desc(dec["ev"]))
            self.n["joined"] += len(dec["ev"]) > 1      # 사건 둘 이상 (코미코) — 앱이 Jack 의 두 문장을 이어요
        elif st == "nf":
            s["dvWhy"] = {"v": 1, "st": "nf", "a": int(round(a)), "b": int(round(b))}
            self.notes.append(f"공시 없음 {tag}: {fy - dec['old']}년 말 {a:,.0f}주 → 오늘 {b:,.0f}주 ('이유는 찾지 못했지만' 줄 · 다시 계산)")
        elif st == "filed":
            s["dvWhy"] = {"v": 1, "st": "filed", "a": int(round(a)), "b": int(round(b)),
                          "fx": [{"k": x["k"], "d": x["d"], "n": x["n"], "rc": x["rc"]} for x in used]}
            if dec["ev"]:
                s["dvWhy"]["ev"] = [dvwhy_event_out(e) for e in dec["ev"]]
            self.notes.append(f"공시된 배당 그대로 {tag}: {fy}년 말 {a:,.0f}주 → 오늘 {b:,.0f}주를 "
                              + " · ".join(f"{DVWHY_OTHER_KO[x['k']]}({x['d']} · {x['n']:,}주)" for x in used)
                              + "가 설명해요 → 다시 계산하지 않아요 (수익률은 보통처럼)" + (" / " + " / ".join(dec["why"]) if dec["why"] else ""))
        else:
            s["dvWhy"] = {"v": 1, "st": st}
            self.notes.append(f"{'공시와 다름' if st == 'nc-mismatch' else '설명 못 함'} {tag}: "
                              + " / ".join(([why_after] if why_after else []) + dec["why"])
                              + " → 다시 계산하지 않고 배당수익률도 보여 주지 않아요")
        return r

    # ── v19.1i: 배당 기준 증명 ──────────────────────────────────
    def _pfail(self, t, tag, why):
        self.pv["fail"].append(t)
        self.pnotes.append(f"증명 조회 실패 {tag}: {why} → 그대로 (다음 실행에 다시)")

    def _move(self, t, st_new):
        """dvWhy 결론 집계(self.t)에서 종목을 옮겨요 (st_new None = 결론 없음)."""
        for k in DVWHY_ST:
            while t in self.t[k]:
                self.t[k].remove(t)
        if st_new:
            self.t[st_new].append(t)

    def _stk(self, corp, fy):
        """그해 말 주식의 총수 현황 → (표, 읽지 못했는지). DART 가 그 보고서가 없다고 답했거나 표를 읽지 못한 것(캐시에 남은 답)은 '없음'
        (배당 표 쪽 문제), 답 자체를 받지 못한 것(연결 실패 · 한도)은 조회 실패예요 (리뷰 2026-11-15)."""
        stk = dart_shares(self.client, corp, fy)
        if stk:
            return stk, False
        with self.client.lock:
            e = self.client.entries.get(f"{corp}|{fy}|11011|STK")
        return None, e is None

    def _prove_look(self, t, corp, fy, r, tag, shr):
        """check 가 받은 조회를 다시 써요 (같은 캐시 키). 증명용 모양(pv)이 아니거나 받은 뒤 상장 주식 수가 3% 넘게 달라졌으면 다시 받아요
        → (look, None) 또는 (None, 이유)."""
        look, f_key = None, None
        if t in self.seen:
            got = self.seen[t]
            if got is None:
                return None, "공시 조회 실패 (check)"
            look, f_key = got
            if look.get("pv") != PROVE_LOOK_V or prove_shr_moved(look.get("shr"), shr):
                look = None
        else:
            f_key = [_fin(f) for f in r["dpsF"]]
        if look is None:
            look, how = self._look(corp, fy, f_key, tag, prove=True, shr=shr)
            if look is None:
                return None, how
            self.seen[t] = (look, f_key)
        if look.get("bad"):
            return None, "공시를 읽지 못함: " + " · ".join(f"{b.get('rc') or '-'} {b.get('why')}" for b in look["bad"][:3])
        if look.get("nI") == 0:
            return None, "거래소 수시공시 목록이 비어 있어요 (배당하는 회사는 현금배당결정을 내요) — 증명하지 않아요"
        return look, None

    def prove(self, s, r, bas):
        """v19.1i: div_basis (+ check) 결과 r 에서 오늘 주식 수 기준을 찾지 못한 해(nc · nd)를 증명할 수 있으면 되살려요 → 고친 r.
        이번 실행에서 증명 단계가 쓴 DART 호출 수를 따로 세요 (self.n pCalls)."""
        c0 = sum(self.client.status.values()) if self.client else 0
        try:
            return self._prove(s, r, bas)
        finally:
            if self.client:
                self.n["pCalls"] += sum(self.client.status.values()) - c0

    def _rights_bad(self, look, xs):
        """xs (유상증자 결정들: rc · n) 중 권리락으로 주가를 새 기준으로 만든 큰 것 → 그 설명들 (없으면 []).
        주주배정(주주배정후 실권주 일반공모 포함) · 방식을 모름 중 새 보통주가 증자 전의 SHARE_SAME(10%)를 넘거나 그 크기를 모르는 것."""
        return [d for d, _ in self._rights_block(look, xs)]

    def _rights_block(self, look, xs, shr=None, px=None):
        """_rights_bad 와 같은 결정들 → [(설명, 경우)] — v19.1j: 경우 sh 주주배정이고 그 새 주식이 오늘 상장 주식 수에 들어 있음 (권리락이 지남) ·
        shnew 주주배정인데 새 주식이 아직 보이지 않음 · ? 방식을 모름. rights 의 줄은 sh 가 하나라도 있을 때만 (답 11 · 말이 맞을 때만)."""
        terms = {**(look.get("rt") or {}), **(look.get("fxT") or {})}
        out = []
        for x in xs:
            tm = terms.get(x.get("rc")) or {"m": "?", "q": None}
            if tm["m"] in RIGHTS_SH and (tm["q"] is None or tm["q"] > SHARE_SAME):
                kind = {"sh": "주주배정", "?": "방식을 모르는"}[tm["m"]]
                how = tm["m"] if tm["m"] != "sh" else ("sh" if self._rights_listed(look, x, tm, shr, px) else "shnew")
                out.append((f"{kind} 유상증자({x.get('d')} · " + (f"증자 전의 {tm['q'] * 100:.0f}%" if tm["q"] is not None else "크기 모름")
                            + (" · 새 주식이 아직 상장 전" if how == "shnew" else "") + ")", how))
        return out

    @staticmethod
    def _rights_listed(look, x, tm, shr, px):
        """v19.1j: 주주배정 결정 x 의 새 주식이 오늘 상장 주식 수에 들어 있는지 — (증자 전 보통주 = 새 주식 ÷ q) + 새 주식을 그 공시일 뒤 ~ px 의
        분할 · 병합 · 무상증자만큼 늘린 수의 97% 이상이면 들어 있어요 (상장은 납입 뒤라 권리락이 지났다는 증거). 새 주식 수 · 크기 · 날짜를 모르면
        아니라고 봐요 (줄 없음 쪽)."""
        q, shr = _fin(tm.get("q")), _fin(shr)
        n = _fin(x.get("n")) or next((_fin(f.get("n")) for f in look.get("fx") or []
                                      if f.get("k") == "rights" and f.get("rc") == x.get("rc") and _fin(f.get("n"))), None)
        if not (q and q > 0 and n and n > 0 and shr and x.get("d") and px):
            return False
        ev = [e for e in look.get("ev") or [] if x["d"] < e["d"] <= str(px) and dvwhy_named(e["r"])]
        return shr >= (n / q + n) * prove_prod(ev) * (1 - PROVE_TOL)

    def _prove(self, s, r, bas):
        """prove 의 본문. 결과 (self.pv): today · yearEnd (올해 수익률 되살림) · years (앞 해 막대) · 되살리지 않으면 하나만 —
          line   주식 수가 바뀌었는데 그 사이에 어떤 공시도 없음 → dvWhy nc-unexplained (배당한 해를 모두 비교 불가로 · 앱이 Jack 의 줄)
          ratio  공시의 배율이 깨끗하지 않음 (1.66 · 1.3 …) — 공시가 배율을 주니 줄 없이 그대로 (관문이 받는 배율이 아니라서)
          basis  그 사이 회사분할 · 주식배당 결정 — 줄 없이 그대로
          rights 그 수를 덮는 유상증자가 주주배정이고 10% 넘게 큼 (권리락으로 주가가 새 기준) — 그대로 · 주주배정이고 새 주식이 상장됐으면
                 줄 2 (sh), 아니면 줄 없음 (shnew · unk)
          uncounted 주식 수가 바뀐 것을 설명하는 공시는 있는데 그 수를 읽지 않음 (주식교환 · 합병 · 감자 · 소각 …) — 줄 없이 그대로
          data   배당 표 자체가 주식 수와 어긋남 (중간배당 · 단위) 또는 계산에 필요한 조각이 빠짐 (총액 없음 · 주식의 총수 현황 없음 …) — 그대로 ·
                 어긋남은 줄 3 (div), 빠진 조각은 줄 4 (nototal · nostk · pref0 · nopfo · prefmix), neg · noshr · other 는 줄 없음 (prove_line)
          fail   조회 실패 (DART · 한도 · 읽지 못한 공시 · 주식의 총수 현황을 받지 못함) — 아무것도 바꾸지 않아요 (다음 실행에 다시)
        '그대로' = 이 단계가 없을 때와 같아요 (check 가 단 dvWhy 도 그대로)."""
        t, fy = s["t"], s.get("fy")
        d3 = _three(s.get("dps3"))
        todo0 = (d3[0] or 0) > 0 and r["st3"][0] in ("nc", "nd")
        todo = [i for i in (1, 2) if (d3[i] or 0) > 0 and r["st3"][i] in ("nc", "nd")]
        if not self.prove_on or not (todo0 or todo) or is_foreign_issuer(t) or not (d3[0] or 0) > 0:
            return r
        w = (s.get("dvWhy") or {}).get("st")
        if t in self.t["fail"] or t in self.t["kept"] or w in ("nf", "filed"):
            return r                                   # check 가 조회를 못 했거나 다른 판정 — 그대로
        tag = f"{t} {s.get('nk', '')}".strip()
        corp = self.cmap.get(t)
        shr = _fin(s.get("shr"))
        if self.client is None or not corp or not isinstance(fy, int):
            self._pfail(t, tag, "DART 꺼짐 · 키 없음 · 기업코드 또는 사업보고서 연도 없음")
            return r
        look, why = self._prove_look(t, corp, fy, r, tag, shr)
        if look is None:
            self._pfail(t, tag, why)
            return r
        px = self.px.isoformat() if isinstance(self.px, dt.date) else str(self.px)
        bas = bas or {}
        cash = _three(bas.get("cash3"))
        pds = [_three(p) for p in bas.get("pdps") or [] if isinstance(p, (list, tuple))]
        new = {"dps3a": list(r["dps3a"]), "dpsF": list(r["dpsF"]), "st3": list(r["st3"])}
        proof = {"v": 1, "y0": None, "yrs": []}

        if todo0:
            ev0, blk0 = prove_window(look, f"{fy}-12-31", px)
            f = prove_prod(ev0)                                 # 정확한 무상증자는 API 의 1 + x 로 (v19.1j · 답 12)
            nonclean = not prove_ev_ok(ev0)                     # 깨끗한 배율도, 공시의 정확한 무상증자(r = 1 + x)도 아닌 사건
            pd0 = [p[0] for p in pds]
            stk, stk_fail = (None, False)
            if any((x or 0) > 0 for x in pd0):
                stk, stk_fail = self._stk(corp, fy)
                if stk_fail:
                    self._pfail(t, tag, f"{fy}년 말 주식의 총수 현황을 받지 못함")
                    return r
            n, pd, why_n = prove_receiving(cash[0], d3[0], pd0, (stk or {}).get("pfo"))
            desc = (f"{fy}년 주당 {d3[0]:,.0f}원 · 배당 받은 주식 {n:,.0f}" if n else f"{fy}년 배당 표 ({why_n})") + \
                   (f" · 사건 {_ev_desc(ev0)}" if ev0 else " · 그 뒤 분할·병합·무상증자 없음") + f" · 오늘 {shr or 0:,.0f}주"
            how, reason, sub, cover, used, note = None, None, None, 0.0, [], ""
            if blk0:
                reason, note = "basis", "그 사이 " + " · ".join({"spin": "회사분할", "stockdiv": "주식배당"}[b] for b in blk0) + " 결정이 있어요"
            elif nonclean:
                agree = bool(n and shr and prove_today(n, f, shr))
                price = _fin(s.get("price"))
                reason = "ratio"
                note = (f"공시 배율 ×{f:.4g} 가 깨끗한 배율도, 무상증자 결정 API 의 정확한 배율(1 + 1주당 신주 수)도 아니에요 (분할 · 병합 원문 · "
                        "감자) · 총액 ÷ 오늘 주식 수 " + ("맞음" if agree else "확인 안 함")
                        + (f" · 그 배율이면 1주 {d3[0] / f:,.0f}원 · {d3[0] / f / price * 100:.2f}%" if price else ""))
            elif n is None or not shr:
                reason = "data"
                # v19.1j: 자료가 빠졌는지 · 어긋나는지. PROVE_DATA_WHY 에 없는 이유 글(prove_receiving 의 새 글)은 other — 어느 줄이 맞는지
                # 모르니 줄 없음 · 로그에 '!!' 와 수 (proof_summary) · 관문 경고 (리뷰 2026-11-19: 다른 경우로 짐작하면 틀린 이유를 말할 수 있어요)
                sub = PROVE_DATA_WHY.get(why_n, "other") if n is None else "noshr"
            elif prove_today(n, f, shr):
                how = "today"
            else:
                stk, stk_fail = (stk, False) if stk else self._stk(corp, fy)
                if stk_fail:
                    self._pfail(t, tag, f"{fy}년 말 주식의 총수 현황을 받지 못함")
                    return r
                ok, reason = prove_year_end(n, f, shr, stk)
                if not ok and reason == "up":
                    fx, fx_bad, why = self._fx(corp, fy, look, need_terms=True)
                    if fx is None:
                        self._pfail(t, tag, why)
                        return r
                    cover, used = prove_cover(fx, fy, self.px, ev0)
                    ok, reason = prove_year_end(n, f, shr, stk, cover)
                    if not ok and fx_bad:
                        self._pfail(t, tag, "유상증자·사채 결정의 주식 수를 다 읽지 못함: "
                                    + " · ".join(f"{x['rc'] or '-'} {x['why']}" for x in fx_bad[:3]))
                        return r
                how = "yearEnd" if ok else None
            if how:
                # 리뷰 2026-11-15 (2차): 어느 길로 맞췄든, 그해 말 반년 앞 ~ px 의 유상증자 결정은 모두 방식 · 크기를 봐요 (접수번호로). 주주배정
                # (실권주 일반공모 포함) · 방식을 모름이 10% 넘으면 되살리지 않아요 (rights). 방식 · 크기를 읽지 못한 결정이 있으면 조회 실패 (fail).
                o0 = (dt.date(fy, 12, 31) - dt.timedelta(days=DVWHY_OTHER_LOOKBACK_DAYS)).isoformat()
                rights = [o for o in look.get("oth") or [] if o.get("k") == "rights" and (not o.get("d") or o0 < o["d"] <= px)]
                known = lambda: {**(look.get("rt") or {}), **(look.get("fxT") or {})}      # noqa: E731
                if any(o["rc"] not in known() for o in rights):
                    fx, _, why = self._fx(corp, fy, look, need_terms=True)
                    if fx is None:
                        self._pfail(t, tag, why)
                        return r
                unread = [o["rc"] for o in rights if o["rc"] not in known()]
                if unread:
                    self._pfail(t, tag, "유상증자 결정의 방식 · 크기를 읽지 못함: " + " · ".join(unread[:3]))
                    return r
                blk_r = self._rights_block(look, rights, shr, px)
                if blk_r:
                    how, reason = None, "rights"
                    ms = {m for _, m in blk_r}                    # v19.1j: 주주배정이고 새 주식이 상장됐을 때만 줄 (답 11 · 말이 맞을 때만)
                    sub = "sh" if "sh" in ms else "shnew" if "shnew" in ms else "unk"
                    note = (" · ".join(d for d, _ in blk_r) + " — 권리락으로 오늘 주가는 새 기준인데 공시된 1주 배당은 옛 기준이라 그대로 "
                            "(권리락 배율로 나누는 건 다음 PR)")
            if how:
                new["dpsF"][0] = round(f, 6)
                new["dps3a"][0] = round(d3[0] / new["dpsF"][0], 2)
                new["st3"][0] = "same" if new["dpsF"][0] == 1.0 else "adj"
                proof["y0"] = how
                if ev0:
                    proof["ev"] = [dvwhy_event_out(e) for e in ev0]   # 배율의 사건 (관문이 이 사건으로 배율과 새 주식 수를 다시 셈 · dvWhy 와 따로)
                if how == "yearEnd":
                    proof.update(cmo=int(round(stk["cmo"])), cmi=int(round(stk["cmi"])), cv=int(round(cover)))
                    if cover:
                        proof["fx"] = [{"k": x["k"], "d": x["d"], "n": x["n"], "rc": x["rc"]} for x in used]
                if pd:
                    proof.update(pf=int(round(_fin(stk["pfo"]))), pd=pd)
            else:
                if reason in ("down", "up"):
                    o0 = (dt.date(fy, 12, 31) - dt.timedelta(days=DVWHY_OTHER_LOOKBACK_DAYS)).isoformat()
                    inw = lambda x: not x.get("d") or o0 < x["d"] <= px                 # noqa: E731 — 그해 말 반년 앞 ~ px (날짜를 모르면 안)
                    filed = sorted({DVWHY_OTHER_KO.get(o.get("k"), str(o.get("k"))) for o in look.get("oth") or [] if inw(o)}
                                   | {"소각" for x in look.get("cx") or [] if inw(x)} | {"주식배당" for x in look.get("sd") or [] if inw(x)}
                                   | {"철회한 결정" for x in look.get("wd") or [] if inw(x)} | {DVWHY_KIND_KO.get(e["k"], e["k"]) for e in ev0})
                    note = {"down": "오늘 주식 수가 그해 말 유통 주식 수 × 배율보다 적어요",
                            "up": "오늘 주식 수가 공시로 덮을 수 있는 수보다 많아요"}[reason]
                    if filed:
                        reason = "uncounted"
                        note += " — 그 사이 수를 읽지 않는 공시가 있어요 (" + " · ".join(filed) + ")"
                    else:
                        reason = "line"
                        note += " — 그 사이 주식 수를 바꾼 공시가 하나도 없어요"
                elif reason in ("div", "nostk", "data"):
                    if reason != "data":
                        sub = reason                                     # 그해 말 표로: div 어긋남 · nostk 표 없음
                    note = ("그해 말 주식의 총수 현황이 없어 맞춰 보지 못했어요" if sub == "nostk"
                            else "배당 표의 총액 ÷ 주당 배당이 그해 말 · 오늘 주식 수와 3% 넘게 달라요 (중간배당 · 단위)" if sub == "div"
                            else f"배당 표: {PROVE_SUB_KO.get(sub, sub)}" + (f" — 이유 글 {why_n!r} 가 PROVE_DATA_WHY 에 없어요 (새 글?)"
                                                                             if sub == "other" else ""))
                    reason = "data"
                # 줄을 정하는 곳은 여기 하나예요 (리뷰 2026-11-15 2차 · v19.1j 답 11 · 13): 이유와 그 안의 경우 → dvLine (prove_line).
                self.pv[reason].append(t)
                if reason in PROVE_SUB:
                    self.psub[reason][t] = sub
                ln = prove_line(reason, sub)
                if ln:
                    s["dvLine"] = ln
                if reason != "line":
                    self.pnotes.append(f"그대로 숨김({reason}) {tag}: {desc} — {note} → " + (f"줄 dvLine {ln}" if ln else "줄 없음")
                                       + (f" ({sub} · {PROVE_SUB_KO[sub]})" if sub else ""))
                    return r
                # line ⟺ dvWhy nc-unexplained 와 dvLine 1. 맞춤 이유(check)가 앞 해 때문에 nc-mismatch 로 숨겼어도 올해 바뀐 주식 수를
                # 설명하는 공시가 하나도 없으면 nc-unexplained 로 바꿔요 (둘 다 숨김).
                self.pnotes.append(f"설명 못 함 {tag}: {desc} — {note} → 배당수익률을 숨겨요 (Jack 의 줄)")
                if not (w or "").startswith("nc-"):
                    r = dvwhy_apply(r, s.get("dps3"), {"fac": {}, "dem": {}, "hide": "nd"})
                s["dvWhy"] = {"v": 1, "st": "nc-unexplained"}
                self._move(t, "nc-unexplained")
                return r

        f0 = new["dpsF"][0]
        if todo and f0 is not None:
            ev_a, blk_a = prove_window(look, f"{fy}-12-31", px)
            prod_a = prove_prod(ev_a)
            exact_a = any(not dvwhy_clean(e["r"]) for e in ev_a)          # v19.1j: 공시의 정확한 무상증자가 끼면 곱 = 배율 ± 1e-6
            if blk_a or not prove_ev_ok(ev_a) or not prove_same(prod_a, f0, exact_a):
                self.n["pYearsSkip"] += 1
                self.pnotes.append(f"앞 해는 그대로 {tag}: " + (
                    "그 뒤 " + " · ".join({"spin": "회사분할", "stockdiv": "주식배당"}[b] for b in blk_a) + " 결정이 있어요" if blk_a
                    else f"{fy}년 배율 ×{f0:g} 가 그 뒤 공시({_ev_desc(ev_a) or '사건 없음'})와 달라요"))
            else:
                # 두 해 사이의 주주배정 유상증자 (리뷰 2026-11-15): 방식 · 크기를 모르는 결정은 그 응답을 한 번 받아요 (유상증자 결정 API)
                o2 = (dt.date(fy - max(todo), 12, 31) - dt.timedelta(days=DVWHY_OTHER_LOOKBACK_DAYS)).isoformat()
                rights = [o for o in look.get("oth") or [] if o.get("k") == "rights" and (not o.get("d") or o2 < o["d"] <= f"{fy}-12-31")]
                known = {**(look.get("rt") or {}), **(look.get("fxT") or {})}
                fx_ok = True
                if any(o["rc"] not in known for o in rights):
                    fx, _, why = self._fx(corp, fy, look, need_terms=True)
                    fx_ok = fx is not None
                    if not fx_ok:
                        self.n["pYear:fail"] += len(todo)
                        self.pnotes.append(f"앞 해는 그대로 {tag}: 유상증자 결정을 받지 못함 ({why})")
                for i in (todo if fx_ok else []):
                    oi = (dt.date(fy - i, 12, 31) - dt.timedelta(days=DVWHY_OTHER_LOOKBACK_DAYS)).isoformat()
                    big = self._rights_bad(look, [o for o in rights if not o.get("d") or oi < o["d"]])
                    if big:
                        self.n["pYear:rights"] += 1
                        self.pnotes.append(f"앞 해 {fy - i} 는 그대로 {tag}: " + " · ".join(big))
                        continue
                    fi, why_i = prove_earlier(d3, cash, pds, prod_a if exact_a else f0, look, fy, i)   # 정확한 배율은 반올림 전의 곱으로
                    if fi is None:
                        self.n[f"pYear:{why_i}"] += 1
                        continue
                    new["dpsF"][i] = fi
                    new["dps3a"][i] = round(d3[i] / fi, 2)
                    new["st3"][i] = "same" if fi == 1.0 else "adj"
                    proof["yrs"].append(i)
        if not proof["y0"] and not proof["yrs"]:
            return r

        r0, r = r, {**r, **new}
        paid = [x for x in r["st3"] if x in ("same", "adj", "nc", "nd")]
        r["divSt"] = next(x for x in ("nc", "nd", "adj", "same") if x in paid)
        F = [_fin(x) for x in r["dpsF"]]
        adj_y = [i for i in range(3) if F[i] is not None and F[i] != 1.0]
        if adj_y:
            ev = [e for e in look.get("ev") or [] if f"{fy - max(adj_y)}-12-31" < e["d"] <= px and dvwhy_named(e["r"])]
            bad = []
            for i in adj_y:                     # v19.1j 답 12 (나): 정확한 무상증자가 낀 해는 곱 = 배율 ± 1e-6, 아니면 예전처럼 ± 0.5%
                evi = [e for e in ev if e["d"] > f"{fy - i}-12-31"]
                if not prove_same(prove_prod(evi), F[i], any(not dvwhy_clean(e["r"]) for e in evi)):
                    bad.append(i)
            if bad or not ev or not prove_ev_ok(ev):     # 위 규칙으로는 생길 수 없어요 — 생기면 되살리지 않아요
                self.pnotes.append(f"되살리지 않음 {tag}: 배율 {F} 를 공시 사건({_ev_desc(ev)})이 설명하지 못해요 — 계산 오류")
                self.pv["fail"].append(t)
                return r0
            s["dvWhy"] = {"v": 1, "st": "ok", "ev": [dvwhy_event_out(e) for e in sorted(ev, key=lambda e: (e["d"], e["rc"]))]}
            self._move(t, "ok")
        elif w:
            s.pop("dvWhy", None)                        # 되살린 해가 모두 그대로(×1) — 숨김 결론(nc-*)은 지워요
            self._move(t, None)
        c3 = [int(round(x)) if x is not None and x > 0 else None for x in cash]
        proof.update(c=c3, shr=int(round(shr)) if shr else None)
        s["dvProof"] = proof
        if proof["y0"]:
            self.pv[proof["y0"]].append(t)
        if proof["yrs"]:
            self.pv["years"].append(t)
        self.p_ex.append(f"{tag} " + (f"올해 {proof['y0']} ×{F[0]:g}" if proof["y0"] else "")
                         + (f" 앞 해 {','.join(str(fy - i) for i in proof['yrs'])}" if proof["yrs"] else ""))
        return r

    def counts(self):
        """data.json divCheck.why — 관문이 종목과 맞춰 봐요. st 마다 종목 수, 줄이 없는 종목(조회 실패 · 스위치가 꺼져 맞춤 그대로)은 이름도."""
        out = {"v": 1}
        for k in DVWHY_ST + ("fail", "kept"):
            out[k] = len(set(self.t[k]))
        for k in ("fail", "kept"):
            out[k + "T"] = sorted(set(self.t[k]))
        return out

    def summary(self):
        calls = (sum(self.client.status.values()) - self.calls0) if self.client else 0
        c = self.counts()
        joined = self.n["joined"]
        loud = any(c[k] for k in ("nf", "filed", "nc-mismatch", "nc-unexplained", "fail", "kept"))
        line = (f"{'  !! ' if loud else '· '}배당 맞춤 이유 (DART 결정 공시): 다시 계산한 해가 있는 종목 {self.n['adj']:,} — 이유 확인 {c['ok']:,}"
                f" (사건 둘 이상 {joined:,}) · 공시 없음('이유는 찾지 못했지만') {c['nf']:,} · 공시된 배당 그대로(유상증자·사채) {c['filed']:,}"
                f" · 수익률 숨김: 공시와 다름 {c['nc-mismatch']:,} · 설명 못 함 {c['nc-unexplained']:,} · 조회 실패(줄 없음) {c['fail']:,}"
                + (f" · 스위치 꺼져 맞춤 그대로 {c['kept']:,}" if c["kept"] else "")
                + f" | 조회 {self.n['fetched']:,}곳 · 보관본 {self.n['cache']:,}곳"
                + (f" · 실패해 지난 결과 {self.n['stale']:,}곳" if self.n["stale"] else "")
                + f" · 이번 DART 호출 {calls:,}회"
                + (" (전체 DART 실행의 일부 · 어림에 들어 있어요)"
                   if self.client and (self.client.mode == "full" or getattr(self.client, "started_empty", False))
                   else " (보관된 캐시에 빠진 회사만 — 전체 DART 실행이 아니에요)"))
        ok = (["· 이유 확인 예: " + " / ".join(self.ok_ex[:8]) + (f" … 외 {len(self.ok_ex) - 8}곳" if len(self.ok_ex) > 8 else "")]
              if self.ok_ex else [])
        return [line] + ok + [f"  !! {x}" for x in self.notes] + (self.proof_summary() if self.prove_on else [])

    def proof_counts(self):
        """v19.1i: data.json divCheck.proof — 관문이 종목의 dvProof · dvWhy 와 맞춰 봐요. 결과마다 종목 수, 되살리지 않은 이유는 이름도."""
        out = {"v": 1}
        for k in PROVE_KEYS:
            out[k] = len(set(self.pv[k]))
        for k in PROVE_HID:
            out[k + "T"] = sorted(set(self.pv[k]))
        return out

    def proof_sub(self):
        """v19.1j: data.json divCheck.proofSub — rights · data 로 숨긴 종목마다 그 안의 경우 (줄을 고른 근거). 관문이 proof 의 이름 목록 ·
        종목의 dvLine 과 맞춰 봐요 (prove_line: rights sh → 2 · data div → 3 · 빠진 자료 → 4 · 나머지는 줄 없음)."""
        return {"v": 1, **{k: dict(sorted(self.psub[k].items())) for k in PROVE_SUB}}

    def proof_summary(self):
        c = self.proof_counts()
        yrs = {k.split(":", 1)[1]: v for k, v in self.n.items() if k.startswith("pYear:")}
        loud = any(c[k] for k in PROVE_HID)
        line = (f"{'  !! ' if loud else '· '}배당 기준 증명 (오늘 주식 수 기준을 찾지 못한 해): 올해 수익률을 되살림 — 총액 ÷ 오늘 주식 수 "
                f"{c['today']:,} · 그해 말 주식 수 {c['yearEnd']:,} · 앞 해 막대를 되살린 종목 {c['years']:,} | 그대로 숨김: 주식 수가 바뀌었는데 "
                f"그 사이 공시가 없음(Jack 의 줄) {c['line']:,} · 깨끗하지 않은 공시 배율 {c['ratio']:,} · 회사분할·주식배당 {c['basis']:,} · "
                f"주주배정 유상증자(권리락) {c['rights']:,} · 수를 읽지 않는 공시 {c['uncounted']:,} · 배당 표가 어긋남 {c['data']:,} · "
                f"조회 실패 {c['fail']:,}"
                + (" | 앞 해를 못 한 이유: " + " · ".join(f"{k} {v}" for k, v in sorted(yrs.items())) if yrs else ""))
        lim = self.n["pLimit"]
        calls = (f"{'  !! ' if lim else '· '}배당 기준 증명 조회: 새로 받음 {self.n['pFetched']:,}곳 (그중 예전 모양 · 주식 수가 바뀌어 다시 받음 "
                 f"{self.n['pRefetch']:,}) · 보관본 {self.n['pCache']:,}곳 · 실행당 한도({PROVE_PER_RUN}곳)에 닿아 못 함 {lim:,}곳"
                 + (" (다음 실행이 이어받아요)" if lim else "") + f" · 이번 증명 단계의 DART 호출 {self.n['pCalls']:,}회")
        ex = (["· 증명 예: " + " / ".join(self.p_ex[:10]) + (f" … 외 {len(self.p_ex) - 10}곳" if len(self.p_ex) > 10 else "")]
              if self.p_ex else [])
        subs = {k: collections.Counter(v.values()) for k, v in self.psub.items()}
        lines = collections.Counter(prove_line(k, sb) for k, v in self.psub.items() for sb in v.values())
        lines[1] += c["line"]
        ln = ("· 숨긴 배당수익률의 줄 (dvLine): Jack 의 줄(1) " + f"{lines[1]:,} · 유상증자 줄(2) {lines[2]:,} · 배당 자료 줄(3) {lines[3]:,} · "
              + f"빠진 자료 줄(4) {lines[4]:,} · rights · data 중 줄 없음 "
              + f"{lines[None]:,} | " + " · ".join(f"{k} " + ", ".join(f"{PROVE_SUB_KO[x]} {v[x]}" for x in PROVE_SUB[k] if v[x])
                                                  for k, v in subs.items() if v))
        oth = sorted(t for t, v in self.psub["data"].items() if v == "other")
        unk = ([f"  !! 배당 표의 이름 없는 이유 (prove_receiving 의 새 글 · PROVE_DATA_WHY 에 없음): {len(oth):,}곳 → 줄 없음 · 관문 경고 — "
                + ", ".join(oth[:10]) + (f" … 외 {len(oth) - 10}곳" if len(oth) > 10 else "")] if oth else [])
        return [line, calls, ln] + unk + ex + [f"  !! {x}" for x in self.pnotes]


def apply_div_basis(kr_stocks, fin_map, pref_shares, why=None):
    """v19.1b: 국내 종목마다 dps3a·dpsF·divSt·dyt 를 붙이고, corp.json 에 실을 원값(총액·주당순이익)을 돌려줘요.
    분할 확인용 임시 칸(_bas)은 여기서 지워요 (파일에 나가지 않게). 반환: (집계 dict, {코드: corp.json 추가 칸}).
    v19.1h: why (DivWhy) 가 있으면 맞춘 해가 있는 종목마다 DART 결정 공시로 이유를 확인해요 — 공시와 다른 해는 수익률·순위를 매기기
    전에 맞추지 않은 것으로 바꿔요(그래서 아래 집계·dyt 가 바꾼 뒤의 값). 집계에 why 칸이 생겨요."""
    cnt = collections.Counter()
    extra, adj_ex, nc_ex, nd_ex, big = {}, [], [], [], []
    srcs = collections.Counter()                 # v19.1e: 분할 확인에 쓴 자본금 줄 (배당 종목만)
    for s in kr_stocks:
        bas = s.pop("_bas", None)
        cap = s.pop("_cap", None)
        stk = s.pop("_stk", None)
        s.pop("dvWhy", None)          # v19.1h: 이번 실행에서 확인한 것만
        s.pop("dvProof", None)        # v19.1i: 이번 실행에서 증명한 것만 (건너뛰는 종목도 — 관문은 기록 없는 dvProof · dvLine 에 실패해요)
        s.pop("dvLine", None)         # v19.1i: Jack 의 줄도 이번 실행에서 정한 것만
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
                      cap_src=(cap or {}).get("src"), stk=stk)
        if stk:
            cnt["stkOk" if r["dpsF"][0] is not None else "stkNo"] += 1
        d0_ = _fin(s["dps3"][0]) if s["dps3"] else None
        if d0_ is not None and d0_ > 0:
            srcs[(cap or {}).get("src") or ("total" if cs3 else "none")] += 1
        if r["divSt"] is None:
            cnt["noDps"] += 1
            continue
        if why is not None:
            r = why.check(s, r)       # v19.1h: 공시와 다른 해는 여기서 맞추지 않은 것으로 (dyt · 순위보다 먼저)
            r = why.prove(s, r, bas)  # v19.1i: 오늘 주식 수 기준을 찾지 못한 해를 공시와 주식 수로 증명할 수 있으면 되살려요 (dyt 보다 먼저)
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
        f"DART 배당 표 없음 {cnt['noDps']:,} · 우선주 {cnt['pref']:,}"
        + (f" · 상장 안 된 우선주가 있어 주식의 총수 현황으로 확인 {cnt['stkOk'] + cnt['stkNo']:,}곳 (확인됨 {cnt['stkOk']:,})"
           if cnt['stkOk'] + cnt['stkNo'] else ""))
    share = 100.0 * cnt["payersDyt"] / cnt["payers"] if cnt["payers"] else 0.0
    band = ("관문 실패" if share < DYT_COVER_BANDS["floor"] else "관문 경고" if share < DYT_COVER_BANDS["seen"] else None)
    log(f"{'  !! ' if band else '· '}오늘 종가 기준 배당수익률(dyt): 배당한 {cnt['payers']:,}종목 중 {cnt['payersDyt']:,} "
        f"({floor_1(share)}%{' · ' + band if band else ''}) + 배당 없음 {cnt['dyt'] - cnt['payersDyt']:,}"
        f" — 확인 못 한 종목은 빈 칸이라 배당 순위에서 빠져요"
        + (f" · 믿지 않아 비운 값(수익률 30% 초과·음수 총액) {len(big)}: {', '.join(big[:5])}" if big else ""))
    counts = {"v": 1, **{k: cnt[k] for k in DIV_STATUS}, "noDps": cnt["noDps"], "pref": cnt["pref"],
              "payers": cnt["payers"], "dyt": cnt["dyt"]}
    if why is not None:
        for line in why.summary():
            log(line)
        counts["why"] = why.counts()  # v19.1h: 관문이 종목의 dvWhy 와 맞춰 봐요
        if why.prove_on:
            counts["proof"] = why.proof_counts()   # v19.1i: 관문이 종목의 dvProof 와 맞춰 봐요
            counts["proofSub"] = why.proof_sub()   # v19.1j: 숨긴 이유 안의 경우 — 관문이 종목의 dvLine 과 맞춰 봐요
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
class UsListNames(dict):
    """us_tickers 가 채우는 목록 이름 (티커 → 이름). 2026-11-14: sp500 = S&P 500 목록에서 읽은 티커 (읽지 못했으면 None) — 외국 회사
    판별(us_foreign_set)이 S&P 500 회사를 빼는 데 써요. us_tickers 의 부르는 모양은 그대로예요 (dict 를 넘기면 이 칸이 없을 뿐)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.sp500 = None
        self.sym = None     # 2026-11-15: us_tickers 가 채우는 출처 티커 기록 {"mapped": [[출처, 원래 티커, 야후 티커]], "unmapped": [[출처, 원래 티커, 이유]]}


# 2026-11-15 (Jack: "fix Brown-Forman B, then check every share-class ticker in the S&P 500 and NASDAQ sources"): 미국 목록 출처의 티커를
# 야후가 쓰는 모양으로 (us_symbol · 한 곳에서만). 야후는 주식 종류를 대시로 적어요 (BRK-B · BF-B). 출처마다 적는 법이 달라요:
#   · S&P 500 (FinanceDataReader 가 읽는 위키백과 표): 표에는 점(BRK.B · BF.B)인데 FinanceDataReader 가 점을 지워요 (Symbol.str.replace('.', ''))
#     → 'BRKB' · 'BFB'. 야후에는 그런 티커가 없어요 (2026-11-15: quoteType NONE · 가격 없음). 그래서 BF-B 는 목록에 한 번도 없었고 BRK-B 는
#     EXTRA_US 로만 들어왔어요 (예전 코드의 점 → 대시는 점이 이미 지워져 한 번도 쓰이지 않았어요).
#   · 나스닥 상위 400 (네이버): 나스닥 자기 티커 그대로예요 (GOOGL · GOOG · FOXA · FOX · NWSA · FWONK · LLYVK — 종류 글자가 티커의 일부라 야후와 같아요).
#   · 점 · 빗금 · 띄어쓰기 · 대시 꼴 (BRK.B · BRK/B · BRK B · BRK-B) 은 어느 출처에서 오든 대시로 바꿔요.
# 점이 지워진 꼴은 모양만으로는 알 수 없어요 (BFB 가 진짜 다른 티커일 수도 있어요 — 끝 글자를 떼어 짐작하지 않아요). 근거를 확인한 것만 이 표로
# 바꿔요: {지워진 꼴: (야후 티커, S&P 500 목록 이름에 들어 있어야 할 글자)}. 근거 (2026-11-15): 위키백과 표의 점 꼴 (BRK.B · BF.B) · S&P 500
# 목록 이름 (Berkshire Hathaway · Brown–Forman) · 야후가 대시 꼴에 그 회사 이름으로 답함 (BRK-B 'Berkshire Hathaway Inc.' · BF-B 'Brown-Forman
# Corporation') · 지워진 꼴에는 답이 없음. 목록 이름이 맞지 않으면 바꾸지 않고 크게 남겨요 (그 티커를 다른 회사가 쓰게 된 날).
# 표에 없는 새 주식 종류 티커가 S&P 500 에 들어오면 (예: 'XYZ.A' → 'XYZA') 야후가 가격을 하나도 주지 않아요: 실행 기록(usListSym.noPx)과
# 관문 경고가 그 이름을 남겨요 → 확인하고 이 표에 한 줄 더해요 (RUNBOOK "US share-class tickers").
US_CLASS_JOINED = {"BRKB": ("BRK-B", "berkshire"), "BFB": ("BF-B", "brownforman")}
# 이 바꾸기로 미국 목록에 새로 들어온 종목 (BRK-B 는 EXTRA_US 로 이미 있었어요). 관문이 따로 적어 맞춰 봐요 (validate_data.US_CLASS_SET):
# 오늘 목록에 있거나 data.json usListSym.missing 에 빠진 이유가 있어야 해요 (#126 의 EXTRA_US 줄과 같은 규칙).
US_CLASS_ADDED = ("BF-B",)
US_SYM_PLAIN = re.compile(r"[A-Z]{1,5}")
US_SYM_CLASS = re.compile(r"([A-Z]{1,5})[./ -]([A-Z]{1,2})")
US_SYM_YAHOO = re.compile(r"[A-Z]{1,5}(?:-[A-Z]{1,2})?")     # 야후 모양 (이 함수가 내놓는 모든 티커)


def us_symbol(raw, src="", name=None):
    """미국 목록 출처의 티커 하나 → (야후 티커 또는 None, 메모). (순수 함수)
    · 바꾸지 않았으면 메모 None · 바꿨으면 바꾼 까닭 · 바꾸지 못했으면 (None, 까닭) — 부르는 쪽이 크게 남기고 기록해요 (조용히 버리지 않아요).
    src: 'S&P500' 일 때만 점이 지워진 꼴 표(US_CLASS_JOINED)를 써요 · name: 목록에 적힌 회사 이름 (점이 지워진 꼴은 이 이름이 있어야 하고 표의
    글자가 들어 있어야 바꿔요 — 이름이 비면 바꾸지 않아요)."""
    if not isinstance(raw, str):
        return None, "티커 칸이 비었거나 글자가 아님"
    s = raw.strip().upper()
    if not s:
        return None, "티커 칸이 비었거나 글자가 아님"
    if not s.isascii():
        return None, "티커에 영문이 아닌 글자"
    m = US_SYM_CLASS.fullmatch(s)
    if m:
        y = f"{m.group(1)}-{m.group(2)}"
        return y, (None if y == s else f"주식 종류 '{s}' → 야후 대시 꼴 {y}")
    if not US_SYM_PLAIN.fullmatch(s):
        return None, "티커 모양이 아님 (영문 1~5자, 또는 그 뒤 점 · 빗금 · 띄어쓰기 · 대시와 종류 글자 1~2자)"
    j = US_CLASS_JOINED.get(s) if src == "S&P500" else None
    if j is None:
        return s, None
    y, key = j
    if not (isinstance(name, str) and name.strip()):    # 리뷰 1: 이름 칸이 비면 맞춰 볼 근거가 없어요 — 바꾸지 않고 크게 남겨요 (열린 채로 두지 않아요)
        return None, f"점이 지워진 주식 종류 표({s} → {y})의 회사인지 S&P 목록에 회사 이름이 없어 맞춰 보지 못함"
    if key not in re.sub(r"[^a-z]", "", name.lower()):
        return None, f"점이 지워진 주식 종류 표({s} → {y})의 회사가 아님: 목록 이름 '{name.strip()[:40]}'"
    return y, f"점이 지워진 S&P 500 표기 '{s}' → {y}"


def us_tickers(names_out=None):
    """S&P500 + NASDAQ 상위 400 + EXTRA_US. names_out(dict)을 주면 목록에 적힌 이름도 담아요 (티커 → 이름):
    야후의 짧은 이름은 31자에서 잘리고 긴 이름은 'Strategy Inc' 처럼 회사 이름뿐일 때가 있어서, 우선주·예탁증서를 알아보는 데
    목록의 이름("… Depositary Shares Each Representing … Preferred Stock")도 써요 (us_preferred_like).
    names_out 이 UsListNames 이면 S&P 500 목록의 티커도 담아요 (names_out.sp500 · 목록을 읽지 못하면 None 그대로).
    2026-11-15: 모든 출처 티커는 us_symbol 로 야후 모양이 돼요 (S&P 500 의 BRKB → BRK-B · BFB → BF-B). 바꾼 것과 바꾸지 못한 것은 크게 남기고
    names_out.sym 에 적어요 (UsListNames 일 때 · fetch_us 가 data.json usListSym 으로 실어요)."""
    import FinanceDataReader as fdr
    tk, mapped, unmapped = set(), [], []

    def put(raw, src, nm=None):
        y, note = us_symbol(raw, src, nm)
        shown = raw.strip().upper() if isinstance(raw, str) else ("" if raw is None else str(raw))
        if y is None:
            unmapped.append([src, shown, note])
            return None
        if note:
            mapped.append([src, shown, y])
        tk.add(y)
        return y

    for t in EXTRA_US:
        put(t, "EXTRA_US")
    for name in ("S&P500", "NASDAQ"):
        try:
            df = fdr.StockListing(name)
            col = "Symbol" if "Symbol" in df.columns else df.columns[0]
            if name == "NASDAQ":
                df = df.head(400)
            nms = df["Name"].tolist() if "Name" in df.columns else [None] * len(df)
            syms = []
            for sym, nm in zip(df[col].tolist(), nms):
                nm = nm.strip() if isinstance(nm, str) and nm.strip() else None
                y = put(None if isinstance(sym, float) and math.isnan(sym) else sym, name, nm)
                if y is None:
                    continue
                syms.append(y)
                if names_out is not None and nm:
                    names_out.setdefault(y, nm)
            if name == "S&P500" and isinstance(names_out, UsListNames) and syms:
                names_out.sp500 = frozenset(syms)
        except Exception as e:
            log(f"  ({name} 목록 실패: {e})")
    if mapped:
        log(f"· 미국 목록 티커를 야후 모양으로 바꿈 {len(mapped)}개: " + " · ".join(f"{s} {a} → {b}" for s, a, b in mapped))
    if unmapped:
        log(f"  !! 미국 목록 티커를 야후 모양으로 바꾸지 못해 요청하지 않은 티커 {len(unmapped)}개 (data.json usListSym.unmapped · 관문 경고): "
            + " · ".join(f"{s} '{a}' ({w})" for s, a, w in unmapped[:20]) + (f" 외 {len(unmapped) - 20}개" if len(unmapped) > 20 else ""))
    if isinstance(names_out, UsListNames):
        names_out.sym = {"mapped": mapped, "unmapped": unmapped}
    if names_out is not None:
        log(f"· 미국 목록 이름 {len(names_out):,}개 (우선주·예탁증서 알아보기용)")
    return sorted(tk)


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
                "marketCap", "averageVolume", "financialCurrency", "currency", "totalRevenue",
                "dividendRate", "trailingAnnualDividendRate", "lastDividendDate", "exDividendDate",
                "netIncomeToCommon", "country",
                "earningsTimestampStart", "earningsTimestampEnd", "isEarningsDateEstimate")
# v19.6b (Part B.1): earningsTimestampStart · earningsTimestampEnd · isEarningsDateEstimate — 다음 실적 발표일(data.json ed, 확정일 때만).
# 배당락일(xd)은 이미 담던 exDividendDate 예요. 모양 표시(US_INFO_SCHEMA)는 그대로예요 (netIncomeToCommon · country 처럼): 보관본 항목은
# 3일(US_INFO_FRESH_DAYS) 안에 다시 받으며 이 칸을 담아요 — 그동안 그 종목의 ed 는 빈 칸(모름)이에요.
# 2026-11-14: netIncomeToCommon (보통주 몫 순이익, 재무제표 통화) — 외국 회사의 PER · PBR 을 회사 합계와 맞춰 보는 데만 써요 (us_foreign_cuts).
# 모양 표시(US_INFO_SCHEMA)는 그대로예요: 보관본 항목은 3일 안에 다시 받으며 이 칸을 담아요. 이 칸이 없는 외국 회사(US_FOREIGN) 항목은 그동안
# PER · PBR 을 비워요 (맞춰 볼 수 없으면 빈 칸). 새로 더한 종목은 보관본에 없어 첫 실행에서 받아요.
# 2026-11-14 (Q5): country (야후 본사 나라) — 외국 회사 판별(us_foreign_set)에만 써요. 모양 표시는 그대로 (770곳을 한꺼번에 다시 받지 않게):
# 이 칸이 없는 S&P 500 밖 회사 항목만 다음 실행에서 한 번 다시 받아요 (us_country_due · 약 270곳). 설명 칸이라 US_INFO_STICKY 에도 있어요.
# 보관본 항목의 모양 (Jack, 2026-11-12: 재무제표 통화). 2 = financialCurrency · currency 를 담기 시작한 모양 · 3 = totalRevenue (매출이 없는
# 회사의 영업이익률 0 을 가리려고, #114 리뷰)와 배당 근거 칸(dividendRate · trailingAnnualDividendRate · lastDividendDate · exDividendDate:
# 배당 없음 0% 를 남길지, Jack 2026-11-13)도. 이 표시("k")가 지금 값이 아닌 항목은 받은 날과 상관없이 다음 실행에서 한 번 다시 받아요 (그 실행은
# 미국 종목 약 770곳을 모두 다시 받아요 — 보관본이 빈 날과 같은 호출 수). 다시 받지 못하면 14일 안의 예전 항목을 그대로 쓰고, 그 종목은
# '재무제표 통화를 모르는 회사'로 크게 남아요 (비우지 않아요 · data.json usFcurUnknown · 관문 경고). 다음 실행이 또 받아요.
# 파일 이름(us-info-v1)은 그대로예요: 이름을 바꾸면 다시 받지 못한 날 이름·업종·설명까지 모두 잃어요.
US_INFO_SCHEMA = 3
# 새 응답에 빠져 있으면 예전 항목의 값을 그대로 쓰는 설명 칸 (#114 리뷰: 야후가 가끔 시세만 담은 응답을 줘요 — 이름은 있는데 financialCurrency ·
# 업종 · 설명이 없는). 재무제표 통화를 잃으면 TSMC PBR 78.88 같은 값이 다시 나가요. 숫자 칸(PER · PBR · 배당 · 시가총액 …)은 절대 옛 값을
# 쓰지 않아요: 이 목록에 넣지 마세요.
US_INFO_STICKY = ("financialCurrency", "currency", "shortName", "longName", "quoteType", "sector", "industry", "longBusinessSummary",
                  "country")
US_INFO_STICKY_DAYS = 14  # 이보다 오래된 예전 항목은 이름이 같을 때만 설명 칸을 채워요 (#114 리뷰 2)
US_PBR_MIN = 0.005       # 이보다 작은 PBR 은 0.00 으로 반올림돼요 — 진짜일 수 없어 빈 칸 (BRK-B 0.0011, 2026-11-12 · Jack 2026-11-13 한국 규칙과 같은 뜻)

# Jack, 2026-11-12: 미국에 상장된 외국 회사 중 재무제표를 달러가 아닌 통화로 내는 곳 (야후 financialCurrency: 대만 TWD · 카자흐스탄 KZT ·
# 스웨덴 SEK …). 야후의 priceToBook · trailingPE 는 달러 주가를 그 통화의 금액으로 나눈 값일 수 있어요 (2026-11-12 발행: Kaspi.kz PBR
# 0.01 (실제 약 3.5) · 에릭슨 0.35 (약 3.1) · TSMC 78.88 (약 11)). 환산을 짐작하지 않고 비워요 (None — 0 이 아니에요): 달러 주가(또는
# 달러 시가총액)를 재무제표 통화 금액으로 나누는 값 PER · PBR · 배당수익률. 배당수익률은 Jack 이 이름으로 정했어요: 야후 수익률이 달러
# 배당으로 맞는 회사도, 0% 도 비워요. 가치 점수(vz)는 PBR 이 비면 add_percentiles 가 매기지 않고, 다른 미국 종목의 가치 순위는 이
# 회사들 없이 매겨요. 남기는 값 (칸마다 확인, 2026-11-12 미국 773종목):
#   · 같은 통화끼리 나눈 비율 — ROE(returnOnEquity) · 영업이익률(operatingMargins) · 매출 증가율(revenueGrowth) · 차입금 비율(debtToEquity)
#   · 가격만으로 만든 값 — 베타 · 변동성 · 알파 · 샤프 · 낙폭 · 12개월 수익률 · 52주 범위 · d1 (그리고 그 점수 mz · lz)
#   · 시가총액(marketCap)과 그 점수 pz · 거래대금 — 야후 marketCap 은 달러 주가 × 주식 수예요 (27곳 모두 marketCap = 주가 ×
#     impliedSharesOutstanding, 차이 0.1% 안). averageVolume 은 주식 수라 × 달러 주가.
# data.json fcur = 그 통화의 ISO 코드 (앱이 '주가는 달러, 재무제표는 {통화} 기준이라 이 숫자는 계산하지 않았어요.' 줄을 붙이고, 관문이
# 그 칸들이 비었는지 봐요). 야후가 financialCurrency 를 주지 않으면 비우지 않고 그 종목과 수를 크게 남겨요 (fetch_us).
US_FCUR_BLANK = ("per", "pbr", "dy")
US_QUOTE_CUR = "USD"     # 미국 종목의 가격 통화 (fetch_us 의 ccy). 야후 currency 가 다르면 크게 남겨요 (비우지는 않아요)
# 배당수익률 0% (배당 없음)를 남길지 — validate_data.US_FCUR_KEEP_ZERO_DY 하나가 정해요 (관문도 같은 값을 봐요). Jack, 2026-11-13: 자료가 지난 12개월
# 배당이 없었다고 분명히 말할 때만 0% 를 보여 줘요 (us_no_dividend_12m) — 조금이라도 불분명하면 빈 칸. False = 0% 도 늘 비워요.
US_DIV_LOOKBACK_DAYS = 365


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


def etf_from_quote_type(out, cache, keep=US_NOT_ETF, skipped=None):
    """ETF 목록에 없는데 야후가 ETF·펀드라고 하면 ETF 로 둬요 (순위에 섞이지 않게). 반환: 바꾼 종목들. (순수 함수)
    2026-11-14 (리뷰): 사람이 회사 주식으로 정한 종목(keep = US_NOT_ETF)은 바꾸지 않아요 — 야후 종류가 하루 틀리면 관문의 'ETF 여부' 줄이 실패해
    모두의 발행이 멈춰요. 그런 종목은 skipped(목록)에 담아 fetch_us 가 크게 남겨요."""
    odd = []
    for rec in out:
        qt = ((cache.get(rec["t"]) or {}).get("info") or {}).get("quoteType")
        if qt in ("ETF", "MUTUALFUND") and not rec.get("etf"):
            if rec["t"] in keep:
                if skipped is not None:
                    skipped.append(f"{rec['t']}({qt})")
                continue
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


def us_fin_currency(info):
    """야후 financialCurrency → ISO 세 글자 대문자 (norm_currency: 'twd' → 'TWD', 읽을 수 없는 글자 → 'XXX' — 달러로 믿지 않아요).
    없거나 글자가 아니면(NaN 포함) None = 모름. (순수 함수)"""
    x = (info or {}).get("financialCurrency")
    if not isinstance(x, str) or not x.strip():
        return None
    return norm_currency(x)


def apply_us_info(rec, info, px_then, fx, today=None):
    """야후 상세 정보를 종목에 붙여요. 받은 날 이후 가격이 움직였으면 PER·PBR·시총·배당률을 오늘 가격에 맞춰요. (순수 함수)
    재무제표 통화가 달러가 아니면(us_fin_currency) rec["fcur"] 에 그 코드를 쓰고 PER · PBR · 배당수익률(US_FCUR_BLANK)을 비워요
    (배당수익률 0% 는 US_FCUR_KEEP_ZERO_DY 이고 us_no_dividend_12m(info, today) 일 때만 남겨요 · today 없으면 비워요). 0.00 으로 반올림되는
    PBR 과 매출이 없는 회사의 영업이익률 0 은 빈 칸이에요 (us_info_cuts, #114 리뷰). 그 PBR 은 rec["pbrZero"] = True 로 표시해요 (Jack,
    2026-11-13: 앱이 '자료상 PBR이 0에 가깝게 나와서 …' 줄을 붙여요 · fcur 회사는 통화 줄이 이미 말해서 표시하지 않아요)."""
    nm = info.get("shortName") or info.get("longName")
    if rec.get("t") in US_ADDED_LONG_NAME and info.get("longName"):
        nm = " ".join(str(info["longName"]).split())   # 2026-11-14: 더한 28곳은 긴 이름 (짧은 이름은 31자에서 잘려요: 'SAP  SE' · 'Anheuser-Busch Inbev SA Sponsor')
    if not nm:
        return False
    fc = us_fin_currency(info)
    for k in ("fcur", "pbrZero", "roe", "opm", "g3", "debt", "ed", "xd") + US_FCUR_BLANK:   # 같은 rec 에 두 번 붙여도 예전 값이 남지 않게
        rec.pop(k, None)
    ed, xd, _ = us_event_dates(info)          # v19.6b: 다음 실적 발표일(확정) · 배당락일 — 미국 현지 날짜, 모르면 칸 없음
    if ed:
        rec["ed"] = ed
    if xd:
        rec["xd"] = xd
    if fc and fc != US_QUOTE_CUR:
        rec["fcur"] = fc
    rec["nk"] = rec["ne"] = str(nm)
    rec["s"] = map_sector_us(info.get("sector"), info.get("industry"))
    if info.get("industry"):
        rec["_yind"] = str(info["industry"])     # 업종 그룹용 (assign_industries 가 쓰고 지워요)
    rec["dk"] = us_desc(rec["s"], info.get("industry") or info.get("sector") or "")
    k = us_rescale(rec.get("price"), px_then)
    cuts = us_info_cuts(info, k)
    if "pbr" in cuts and not rec.get("fcur"):
        rec["pbrZero"] = True
    spec = (("per", "trailingPE", 0, 500, False), ("pbr", "priceToBook", 0, 100, False),
            ("roe", "returnOnEquity", -5, 5, True), ("opm", "operatingMargins", -5, 5, True),
            ("g3", "revenueGrowth", -5, 20, True), ("debt", "debtToEquity", 0, 2000, False))
    for key, src, lo, hi, scale in spec:
        if key in US_FCUR_BLANK and rec.get("fcur"):
            continue                                # 재무제표 통화가 달러가 아님: 달러 주가 ÷ 그 통화 금액일 수 있어 비워요
        if key in cuts:
            continue                                # 0.00 으로 반올림되는 PBR · 매출이 없는데 영업이익률 0
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
    if dyv is not None and 0 <= dyv / k < 30 and (not rec.get("fcur") or (US_FCUR_KEEP_ZERO_DY and dyv == 0 and us_no_dividend_12m(info, today))):
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


US_NY = ZoneInfo("America/New_York")     # 미국 거래소의 날짜 (실적 발표 시각을 현지 날짜로)


def _yahoo_utc_day(v):
    """야후의 '날짜만' 칸 (exDividendDate · lastDividendDate): 그 날짜 0시(UTC)의 초. → 'YYYY-MM-DD' (UTC 날짜 그대로 — 뉴욕 시각으로 바꾸면
    하루 앞 날짜가 돼요). 0시(UTC)가 아니거나 읽지 못하면 None (모양이 바뀐 것: 짐작하지 않아요). (순수 함수)"""
    x = _fin(v)
    if x is None or x <= 0 or x != int(x) or int(x) % 86400:
        return None
    try:
        return dt.datetime.fromtimestamp(int(x), dt.timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _yahoo_ny_day(v):
    """야후의 시각 칸 (earningsTimestampStart · End, 초) → 뉴욕 날짜 'YYYY-MM-DD', 읽지 못하면 None. (순수 함수)"""
    x = _fin(v)
    if x is None or x <= 0:
        return None
    try:
        return dt.datetime.fromtimestamp(x, dt.timezone.utc).astimezone(US_NY).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def us_event_dates(info):
    """v19.6b (Part B.1): 야후 상세 정보 → (ed, xd, 읽지 못한 칸 이름들). 미국 현지 날짜 'YYYY-MM-DD' 또는 None (빈 칸 = 모름). (순수 함수)
    · ed 다음 실적 발표일: isEarningsDateEstimate 가 정확히 false (야후가 추정이 아니라고 적음)이고 earningsTimestampStart 가 있을 때만, 그
      뉴욕 날짜. earningsTimestampEnd 가 다른 날이면 하루가 아닌 기간이라 None. 2026-11-15 확인 (Ticker.calendar 의 Earnings Date 와 같아요):
      AAPL 2027-01-28 추정 → 빈 칸 · JNJ 2027-01-26 확정 · KO 2026-10-27 확정 (발표가 끝났는데 야후가 다음 날을 아직 안 정함 — 지난 날짜예요.
      보관본도 며칠 묵어서 앱은 오늘 이후 날짜만 보여 줘요).
    · xd 배당락일: exDividendDate (0시 UTC 의 날짜 · Ticker.calendar 의 Ex-Dividend Date 와 같아요: KO 2026-12-01 · JNJ 2026-11-24). 지난
      배당락일일 수 있어요."""
    info = info if isinstance(info, dict) else {}
    bad, ed, xd = [], None, None
    if info.get("isEarningsDateEstimate") is False and info.get("earningsTimestampStart") is not None:
        ed = _yahoo_ny_day(info["earningsTimestampStart"])
        end = info.get("earningsTimestampEnd")
        if ed is None:
            bad.append("earningsTimestampStart")
        elif end is not None and _yahoo_ny_day(end) != ed:
            ed = None                            # 하루가 아닌 기간 (또는 끝 날짜를 읽지 못함) — 확정된 날이 아니에요
    if info.get("exDividendDate") is not None:
        xd = _yahoo_utc_day(info["exDividendDate"])
        if xd is None:
            bad.append("exDividendDate")
    return ed, xd, bad


def us_rescale(price_now, px_then):
    """받은 날 가격 대비 오늘 가격 배율 (PER · PBR · 시가총액 · 배당수익률을 오늘 가격에 맞춰요). 모르면 1. (순수 함수)"""
    p0, p1 = _fin(px_then), _fin(price_now)
    return p1 / p0 if p0 and p1 and p0 > 0 else 1.0


def us_info_cuts(info, k=1.0):
    """야후 값이 있어도 빈 칸으로 둘 칸 (#114 리뷰). (순수 함수)
    · pbr: 오늘 가격에 맞춘 PBR 이 0 보다 크고 US_PBR_MIN 보다 작음 — 0.00 으로 반올림돼 진짜일 수 없어요 (BRK-B 0.0011 → 'PBR 0.0' · 가치 100점)
    · opm: 영업이익률이 정확히 0 인데 매출(totalRevenue)이 없거나 0 — 계산할 매출이 없는 0 이에요 (에릭슨 · Kaspi.kz · VinFast · 임상 단계 바이오)
    다른 비율(ROE · 매출 증가율 · 차입금 비율)은 2026-11-12 미국 773종목에 이 모양(정확히 0 · 분모 없음)이 없었어요."""
    out = []
    pb = _fin((info or {}).get("priceToBook"))
    if pb is not None and 0 < pb * k < US_PBR_MIN:
        out.append("pbr")
    om, rev = _fin((info or {}).get("operatingMargins")), _fin((info or {}).get("totalRevenue"))
    if om == 0 and (rev is None or rev == 0):
        out.append("opm")
    return out


def us_no_dividend_12m(info, today):
    """야후 자료가 '지난 12개월 배당 없음'을 분명히 말하는지 (Jack, 2026-11-13: 재무제표 통화가 달러가 아닌 회사의 0% 를 남길 근거). (순수 함수)
    모두 맞아야 True: dividendYield 가 정확히 0 · trailingAnnualDividendRate 가 있고 정확히 0 · dividendRate 가 없거나 0 · lastDividendDate 와
    exDividendDate 가 없거나 today 보다 365일 넘게 앞 (앞으로 올 배당 기준일도 '있음'이에요). 칸이 없거나 날짜를 읽을 수 없거나 today 를 모르면
    False (빈 칸). 파이프라인은 미국 종목의 배당 기록(actions)을 받지 않아서 이 info 칸들이 쓸 수 있는 가장 강한 근거예요."""
    i = info or {}
    if today is None or _fin(i.get("dividendYield")) != 0:
        return False
    if _fin(i.get("trailingAnnualDividendRate")) != 0:          # 없음(None)도 False
        return False
    dr = i.get("dividendRate")
    if dr is not None and _fin(dr) != 0:
        return False
    for k in ("lastDividendDate", "exDividendDate"):
        v = i.get(k)
        if v is None:
            continue
        x = _fin(v)
        if x is None:
            return False
        try:
            d = dt.datetime.fromtimestamp(x, dt.timezone.utc).date()
        except Exception:
            return False
        if d > today - dt.timedelta(days=US_DIV_LOOKBACK_DAYS):
            return False
    return True


def _us_name_key(x):
    """회사 이름 비교용: 소문자 · 글자와 숫자만 (기호 · 띄어쓰기 무시). (순수 함수)"""
    return re.sub(r"[^0-9a-z]+", " ", str(x or "").lower()).strip()


def us_info_merge(new, prev, today=None):
    """오늘 받은 info(new, US_INFO_KEYS 만 · None 없음)에 빠진 설명 칸(US_INFO_STICKY)을 예전 보관본 항목(prev)의 값으로 채워요. 숫자 칸은
    채우지 않아요. 예전 항목이 같은 회사(이름이 같음, _us_name_key)이거나 US_INFO_STICKY_DAYS 일 안일 때만 채워요 — 티커를 다른 회사가 물려받은
    오래된 항목의 통화 · 업종을 쓰지 않게 (#114 리뷰 2). (순수 함수) → (합친 info, 예전 값을 쓴 칸 목록, 예전 항목의 나이(일) 또는 None)"""
    old = ((prev or {}).get("info") or {}) if isinstance(prev, dict) else {}
    age = None
    if isinstance(prev, dict) and today is not None:
        try:
            age = (today - dt.date.fromisoformat(prev.get("at"))).days
        except Exception:
            age = None
    names_new = {_us_name_key(new.get(k)) for k in ("shortName", "longName")} - {""}
    names_old = {_us_name_key(old.get(k)) for k in ("shortName", "longName")} - {""}
    if not (names_new & names_old or (age is not None and 0 <= age <= US_INFO_STICKY_DAYS)):
        return dict(new), [], age
    out, kept = dict(new), []
    for k in US_INFO_STICKY:
        if out.get(k) is None and old.get(k) is not None:
            out[k] = old[k]
            kept.append(k)
    return out, kept, age


def us_info_partial(merged, kept, etf=False):
    """일부만 온 응답인지 (#114 리뷰 2): 예전 값으로 채운 칸이 있거나, 회사 주식(ETF · 펀드가 아님)인데 재무제표 통화가 없음. 그런 항목은
    오늘 받은 것으로 3일 동안 두지 않고 다음 실행에서 다시 물어봐요 (us_info_due · 항목의 "due"). (순수 함수)"""
    if kept:
        return True
    company = not etf and (merged or {}).get("quoteType") not in ("ETF", "MUTUALFUND")
    return company and (merged or {}).get("financialCurrency") is None


def us_info_due(entry, today):
    """이 보관본 항목을 오늘 다시 받아야 하는지: 없음 · 받은 지 US_INFO_FRESH_DAYS 일 이상 · 예전 모양(k 가 US_INFO_SCHEMA 가 아님 —
    financialCurrency 를 담기 전) · 지난번 응답이 일부만 왔음("due", us_info_partial). (순수 함수)"""
    if not entry:
        return True
    try:
        a = (today - dt.date.fromisoformat(entry["at"])).days
    except Exception:
        return True
    return a >= US_INFO_FRESH_DAYS or entry.get("k") != US_INFO_SCHEMA or bool(entry.get("due"))


# 2026-11-14: 미국 상장 외국 회사(US_FOREIGN)의 주당 숫자를 회사 합계 · 실제 배당과 맞춰 봐요 (us_foreign_cuts). 허용 폭 = 큰 값 ÷ 작은 값.
# 2026-11-14 야후 값으로 정했어요 (달러로 보고하는 10곳): 맞는 회사의 PER 은 1.00~1.02 배 · PBR 은 1.04~1.24 배 (ROE 가 평균 자본이라 더 흔들려요)
# · 배당은 1.00~1.03 배였고, 틀린 값은 PER 1.70 배 (BP) · PBR 4.3~19 배 (BP · HSBC · 디아지오) · 배당 1.88 배 (HSBC: 야후 '앞으로 1년' 값이 큰
# 넷째 배당을 빼요)였어요. ADR 배율 실수는 2 배 이상이에요. 배당은 야후 기록이 한 번 빠지면(AZN · TTE) 맞지 않아 비어요 — 틀린 숫자보다 빈 칸.
# PBR 은 1.35 (리뷰 2026-11-14): √2 보다 좁아야 맞는 회사(1.35 배 안)의 2 배 ADR 실수가 언제나 밖으로 나가요 (2 ÷ 1.35 = 1.48). 맞는 회사의 가장 큰
# 차이는 BHP 1.24 배였어요.
US_FOREIGN_BAND = {"per": 1.10, "pbr": 1.35, "dy": 1.10}
US_FOREIGN_CUR_WHY = "재무제표 통화를 모름"   # us_foreign_cuts 의 이유 머리말 — 통화를 확인하지 못해 비운 칸 (data.json fgnCut "currency")
US_FOREIGN_STOP_WHY = "검사가 멈춤"           # 검사가 멈춰 맞춰 보지 못하고 비운 칸의 이유 머리말 (관문 validate_data.US_FGN_STOPPED 와 같은 글자)
US_FOREIGN_DIV_DAYS = 350     # 지난 1년 배당: 365일이면 해마다 같은 때 주는 배당이 며칠 당겨질 때 다섯 번 세요 (셸 2025-11-14 · 2026-11-13)


def _fold(a, b):
    """큰 값 ÷ 작은 값 (둘 다 양수일 때만 · 아니면 None). (순수 함수)"""
    a, b = _fin(a), _fin(b)
    return max(a / b, b / a) if a and b and a > 0 and b > 0 else None


def _div_col(data, t):
    """다운로드 결과에서 티커 t 의 'Dividends' 칸 (_split_col 과 같은 모양들). 없으면 None."""
    cols = getattr(data, "columns", None)
    if cols is None:
        return None
    if isinstance(cols, pd.MultiIndex):
        for k in ((t, "Dividends"), ("Dividends", t)):
            if k in cols:
                return data[k]
        return None
    return data["Dividends"] if "Dividends" in cols else None


def us_div_12m(col, end, days=US_FOREIGN_DIV_DAYS):
    """야후 다운로드의 배당 기록(col)에서 end − days < 날짜 ≤ end 인 배당의 합 — 한 주(ADR 은 ADR 하나)당, 거래 통화(달러). 날짜는 배당락일.
    칸이 없으면 None (모름 · 0 과 달라요). 0 이하 · 숫자가 아닌 값은 배당이 없는 날이에요. (순수 함수)"""
    if col is None:
        return None
    lo, tot = end - dt.timedelta(days=days), 0.0
    for ts, v in col.items():
        x = _fin(v)
        if x is None or x <= 0:
            continue
        if lo < pd.Timestamp(ts).date() <= end:
            tot += x
    return round(tot, 6)


def us_foreign_cuts(rec, info, div12, days=US_FOREIGN_DIV_DAYS):
    """미국 상장 외국 회사의 PER · PBR · 배당수익률이 회사 합계와 실제 배당에 맞는지 → {칸: 이유} (비울 칸만 · 맞으면 빈 dict). (순수 함수)
    rec = apply_us_info 를 지난 종목 (값이 있는 칸만 봐요). 재무제표 통화가 달러가 아닌 회사(fcur)는 그 칸들이 이미 비어 있어요.
      · per: 야후 trailingPE (주가 ÷ 주당순이익) ↔ 시가총액 ÷ 보통주 몫 순이익(netIncomeToCommon) — US_FOREIGN_BAND["per"] 배 안
      · pbr: 야후 priceToBook (주가 ÷ 주당 장부가) ↔ (시가총액 ÷ 순이익) × ROE(returnOnEquity) ≈ 시가총액 ÷ 자본 — US_FOREIGN_BAND["pbr"] 배 안
      · dy: 그날 배당수익률 ↔ 지난 days 일 실제 배당(div12, 야후 다운로드의 배당 기록 · ADR 하나당 달러) ÷ 오늘 종가 — US_FOREIGN_BAND["dy"]
        배 안. 0% 는 그 기간 배당 기록도 0 일 때만. 배당 기록 칸을 읽지 못했으면(div12 None) 맞춰 볼 수 없어요.
    시가총액 · 순이익(0 이하 포함) · ROE · 배당 기록처럼 맞춰 볼 값이 없으면 그 칸도 비워요 — 틀릴 수 있는 숫자보다 빈 칸 (Jack 2026-11-13).
    재무제표 통화가 달러라고 확인되지 않으면(야후 financialCurrency 가 없음 · 달러가 아님) 세 칸을 모두 비워요 (리뷰 2026-11-14): 시가총액(달러)과
    순이익(그 통화)을 나눈 값끼리 맞춰 봐도 통화가 섞인 PBR 을 걸러 내지 못해요 (UL · SAN · TD · RY · ENB · BCE 의 PBR 이 '맞음'으로 남았어요)."""
    i, out = info or {}, {}
    if us_fin_currency(i) != US_QUOTE_CUR:
        why = f"{US_FOREIGN_CUR_WHY} (야후 financialCurrency {i.get('financialCurrency')!r} — 달러로 확인되지 않음)"
        return {k: why for k in ("per", "pbr", "dy") if rec.get(k) is not None}
    mc, ni = _fin(i.get("marketCap")), _fin(i.get("netIncomeToCommon"))
    pe_c = mc / ni if mc and mc > 0 and ni and ni > 0 else None
    if rec.get("per") is not None:
        pe = _fin(i.get("trailingPE"))
        r = _fold(pe, pe_c)
        if pe and pe > 0 and ni is not None and ni <= 0:   # 리뷰 2차 S1: 순이익이 0 이하인데 야후 PER 은 양수 — 부호가 어긋나요 (맞지 않음)
            out["per"] = f"주가 ÷ 주당순이익 {pe:.2f} 인데 보통주 몫 순이익 {ni:,.0f} (0 이하) — 부호가 맞지 않음"
        elif r is None:
            out["per"] = US_FGN_NOCMP_WHY["per"]          # 맞춰 볼 값이 없음 (nocompare)
        elif r > US_FOREIGN_BAND["per"]:
            out["per"] = f"주가 ÷ 주당순이익 {pe:.2f} ↔ 시가총액 ÷ 순이익 {pe_c:.2f} ({r:.2f}배)"
    if rec.get("pbr") is not None:
        pb, roe = _fin(i.get("priceToBook")), _fin(i.get("returnOnEquity"))
        imp = pe_c * roe if pe_c and roe and roe > 0 else None
        r = _fold(pb, imp)
        if r is None:
            out["pbr"] = US_FGN_NOCMP_WHY["pbr"]          # 맞춰 볼 값이 없음 (nocompare)
        elif r > US_FOREIGN_BAND["pbr"]:
            out["pbr"] = f"주가 ÷ 주당 장부가 {pb:.2f} ↔ 시가총액 ÷ 순이익 × ROE {imp:.2f} ({r:.2f}배)"
    dy = _fin(rec.get("dy"))
    if dy is not None:
        px = _fin(rec.get("price"))
        if div12 is None or not (px and px > 0):
            out["dy"] = US_FGN_NOREC_WHY                  # 배당 기록 · 가격을 읽지 못함 (norecord · 0% 도 · 스위치와 상관없이 늘 비워요)
        else:
            tdy = 100.0 * div12 / px
            r = _fold(dy, tdy)
            if dy == 0 and div12 == 0:
                pass
            elif r is None or r > US_FOREIGN_BAND["dy"]:
                out["dy"] = f"배당수익률 {dy:.2f}% ↔ 지난 {days}일 배당 {div12:.4f}달러 ÷ 종가 {px:.2f} = {tdy:.2f}%" + (f" ({r:.2f}배)" if r else "")
    return out


US_FGN_BASIS = ("fcur", "country", "adr", "floor", "prev", "error")   # usForeign.set 의 근거 (관문 validate_data.US_FGN_BASIS 와 같은 글자)


def us_country(info):
    """야후 country (본사 나라) → 앞뒤 빈칸을 정리한 글자 · 없거나 글자가 아니면(NaN 포함) None = 모름. (순수 함수)"""
    x = (info or {}).get("country")
    return " ".join(x.split()) if isinstance(x, str) and x.strip() else None


def us_country_due(entry, t, sp500):
    """보관본 항목에 본사 나라(country)가 없는 S&P 500 밖 회사 → 오늘 다시 받아요 (2026-11-14 Q5: 외국 회사 판별에 필요한 칸 · 모양 표시를
    올리지 않고 그 회사들만). S&P 500 목록을 읽지 못했으면(sp500 None) · ETF · 펀드 · 회사가 아닌 항목(야후 종류가 EQUITY 가 아님)은 아니에요. (순수 함수)"""
    if sp500 is None or t in sp500 or t in US_ETFS or not isinstance(entry, dict):
        return False
    info = entry.get("info") if isinstance(entry.get("info"), dict) else {}
    return info.get("quoteType") == "EQUITY" and us_country(info) is None


def us_foreign_set(us, infos, sp500=None, floor=US_FOREIGN, prev=None):
    """미국 목록(us: apply_us_info · clean_us_list 를 지난 rec)에서 외국 회사를 규칙으로 찾아요 (Jack 2026-11-14 Q5 · US_FOREIGN 위 설명). (순수 함수)
    infos = {티커: 야후 info (listName 포함)} · sp500 = 믿을 수 있는 S&P 500 목록의 티커 (fetch_us 가 오늘 목록과 US_SP500_MIN 곳 넘게 겹칠 때만 줘요).
    ETF · 펀드는 보지 않아요. 근거(US_FGN_BASIS): fcur 재무제표 통화가 달러가 아님 · country S&P 500 밖 · 본사 나라가 미국 밖 · adr S&P 500 밖 ·
    이름이 예탁증서 · floor 규칙은 못 찾았지만 #126 의 21곳 · prev 어제 발행한 set 에서 이어 옴 · error 이 종목을 보다 멈춤 (맞춰 보는 쪽으로 넣어요).
    sp500 이 None 이면 (목록을 읽지 못했거나 믿을 수 없는 날 · 리뷰 S2) 본사 나라 · 이름 규칙을 쓰지 않아요 — S&P 500 회사를 가려내지 못하면 세금
    때문에 밖에 본사를 둔 미국 회사의 맞는 배당수익률이 비어요. 그날은 21곳 · fcur · 어제 발행한 set(prev)만이에요 (us_foreign_fallback).
    반환 {"set": {티커: [본사 나라 | None, 재무제표 통화 | None, 근거]}, "home": {티커: 나라} (S&P 500 이라 뺀 미국 밖 본사 회사),
          "unknown": [티커] (S&P 500 밖 · 나라 모름 · 다른 근거 없음 — 외국 회사로 보지 않았어요), "errors": [(티커, 예외 이름)]}"""
    if sp500 is None:
        return us_foreign_fallback(us, infos, prev, floor=floor)
    found, home, unknown, errors = {}, {}, [], []
    for r in us:
        t = r.get("t")
        if r.get("etf") is True or r.get("fund"):
            continue
        try:
            info = (infos or {}).get(t) or {}
            ctry, fc = us_country(info), us_fin_currency(info)
            names = [x for x in (info.get("shortName"), info.get("longName"), info.get("listName")) if isinstance(x, str)]
            if r.get("fcur"):
                basis = "fcur"
            elif t in sp500 and t not in floor:
                if ctry and ctry.lower() not in US_HOME:
                    home[t] = ctry
                continue
            elif ctry and ctry.lower() not in US_HOME:
                basis = "country"
            elif any(US_ADR_NAME.search(n) for n in names):
                basis = "adr"
            elif t in floor:
                basis = "floor"
            else:
                if ctry is None:
                    unknown.append(t)
                continue
            found[t] = [ctry, r.get("fcur") or fc, basis]
        except Exception as e:      # 이 종목만: 외국 회사로 넣어요 (이 검사가 맞춰 보고 맞는 숫자는 남겨요) — 크게 남겨요
            found[t] = [None, None, "error"]
            errors.append((t, type(e).__name__))
    return {"set": dict(sorted(found.items())), "home": dict(sorted(home.items())), "unknown": sorted(unknown), "errors": errors}


def us_foreign_fallback(us, infos, prev, floor=US_FOREIGN, basis=None):
    """본사 나라 규칙을 쓸 수 없는 날의 외국 회사 (리뷰 S2 · N1): #126 의 21곳 · 재무제표 통화가 달러가 아닌 회사(fcur) · 어제 발행한 set(prev) 에
    있던 회사 중 오늘 목록에 있는 회사. S&P 500 밖 회사 모두로 넓히지 않아요 (맞는 숫자를 비우지 않게). basis 를 주면 모든 근거를 그 글자로 (판별 전체가
    멈춘 날 "error"). 다른 칸이 이상해도 멈추지 않게 글자만 봐요. (순수 함수) → us_foreign_set 과 같은 모양"""
    prev = prev if isinstance(prev, dict) else {}
    found = {}
    for r in us:
        t = r.get("t")
        if not isinstance(t, str) or r.get("etf") is True or r.get("fund"):
            continue
        info = (infos or {}).get(t) if isinstance((infos or {}).get(t), dict) else {}
        if r.get("fcur"):
            b = "fcur"
        elif t in floor:
            b = "floor"
        elif t in prev:
            b = "prev"
        else:
            continue
        try:
            ctry, fc = us_country(info), us_fin_currency(info)
        except Exception:
            ctry, fc = None, None
        found[t] = [ctry, r.get("fcur") or fc, basis or b]
    return {"set": dict(sorted(found.items())), "home": {}, "unknown": [], "errors": []}


def log_us_foreign_set(fs, sp500, floor=US_FOREIGN):
    """us_foreign_set 결과를 크게 남겨요 (CLAUDE.md: 수와 함께 · 이름 전부)."""
    st = fs["set"]
    by = collections.Counter(v[2] for v in st.values())
    log(f"· 미국 상장 외국 회사 (규칙으로 찾음 · S&P 500 {'목록 ' + format(len(sp500), ',') + '곳은 뺌' if sp500 is not None else '목록 없음'}): "
        f"{len(st)}곳 — 재무제표 통화가 달러가 아님 {by['fcur']} (#114 가 이미 비움 · 이 검사는 건너뜀) · 본사가 미국 밖 {by['country']} · "
        f"이름이 예탁증서 {by['adr']} · 규칙이 못 찾은 손으로 정한 곳 {by['floor']} · 어제 목록에서 이어 옴 {by['prev']} · 판별 중 멈춤 {by['error']}: "
        + ", ".join(f"{t}({v[0] or '나라 모름'} · {v[1] or '통화 모름'})" for t, v in st.items()))
    if sp500 is None:
        log(f"  !! 오늘은 S&P 500 목록 없이 정한 외국 회사예요 (본사 나라 · 예탁증서 이름 규칙을 쓰지 않음): 21곳 {by['floor']} · 재무제표 통화 "
            f"{by['fcur']} · 어제 발행한 목록에서 이어 온 곳 {by['prev']} · 판별 중 멈춤 {by['error']}")
    flo = sorted(t for t, v in st.items() if v[2] == "floor")
    if flo and sp500 is not None:
        log(f"  !! 규칙(재무제표 통화 · 본사 나라 · 예탁증서 이름)이 찾지 못해 손으로 정한 목록(US_FOREIGN)으로 넣은 곳 {len(flo)}곳: {', '.join(flo)} "
            "— 야후가 본사 나라를 주지 않았는지 확인")
    if fs["errors"]:
        log(f"  !! 외국 회사인지 보다가 멈춘 종목 {len(fs['errors'])}곳 → 외국 회사로 보고 맞춰 봐요: "
            + ", ".join(f"{t}({e})" for t, e in fs["errors"]))
    h = fs["home"]
    log(f"· S&P 500 회사라 외국 회사로 보지 않은 미국 밖 본사 {len(h)}곳 (10-K · 달러 재무제표 · 미국에서 거래되는 그 보통주)"
        + (": " + ", ".join(f"{t}({c})" for t, c in h.items()) if h else ""))
    u = fs["unknown"]
    log(f"{'  !! ' if u else '· '}S&P 500 밖인데 야후가 본사 나라를 주지 않은 회사 {len(u)}곳 — 외국 회사로 보지 않았어요 (다음 실행이 다시 물어요)"
        + (": " + ", ".join(u[:40]) + (f" 외 {len(u) - 40}곳" if len(u) > 40 else "") if u else ""))


def us_fgn_kind(f, why, mode=None):
    """비운 칸 하나의 종류 (리뷰 S1 · data.json fgnCut 의 값): currency = 재무제표가 달러인지 확인되지 않음 · norecord = 배당 기록이나 가격을
    읽지 못한 배당수익률 (스위치와 상관없이 늘 비워요) · PER · PBR 을 회사 자기 숫자로 맞춰 볼 수 없으면 스위치(validate_data.US_FGN_NOCMP)가
    정한 종류 (line → nocompare · own → nocompare-own · keep → None = 비우지 않아요) · 나머지는 mismatch (맞춰 봤는데 달라요 · 부호가 어긋남). (순수 함수)"""
    mode = US_FGN_NOCMP if mode is None else mode
    if why.startswith(US_FOREIGN_CUR_WHY):
        return "currency"
    if f == "dy" and why == US_FGN_NOREC_WHY:
        return US_FGN_NOREC                        # 리뷰 2차 S1: 우리 쪽 자료가 빠진 날 — 스위치와 상관없이 비워요 (Jack 11-13)
    if why == US_FGN_NOCMP_WHY.get(f):
        return US_FGN_NOCMP_KIND[mode]
    return "mismatch"


def us_foreign_check(out, cache, data, us_px_date, no_info=frozenset(), foreign=US_FOREIGN, done=None, nocmp=None):
    """fetch_us 의 외국 회사 검사: 외국 회사(foreign — fetch_us 는 us_foreign_set 이 찾은 회사 모두 · 기본값은 #126 의 21곳)이고 재무제표 통화가
    달러가 아닌 표시(fcur)가 없는 종목마다 us_foreign_cuts 로 맞지 않는 칸을 비우고
    (pbr 을 비우면 가치 점수 vz 도 매겨지지 않아요) 크게 남겨요. 상세 정보를 붙이지 못한 종목(no_info)은 비울 칸이 없지만 확인한 것으로 세요.
    반환 data.json usForeign = {"checked": [티커], "cut": [[티커, 칸, 이유]]} — 관문이 비운 칸이 비었는지, 외국 회사가 빠짐없이 확인됐는지 봐요.
    비운 종목에는 rec["fgnCut"] = {칸: "mismatch" | "currency"} (Jack, 2026-11-14: 앱이 그 칸 '–' 밑에 '자료의 숫자가 회사 전체 재무제표와 맞지
    않아서 비워 두었어요.' 를 붙여요 · currency = 재무제표 통화를 확인하지 못함).
    done(dict, 리뷰 N1): 끝까지 본 종목(seen) · 확인한 종목(checked) · 비운 칸(cut)을 가면서 담아요 — 중간에 멈추면 fetch_us 가 이것으로 이미 본 종목의
    줄과 표시를 지키고 나머지만 비워요 (us_foreign_stopped).
    2026-11-14 (리뷰 S1): 칸마다 종류(us_fgn_kind)를 표시에 적어요 — mismatch · currency · norecord(배당 기록 · 가격을 읽지 못함 · 늘 비워요) ·
    nocompare(회사 자기 숫자로 PER · PBR 을 맞춰 볼 수 없음). nocompare 칸은 스위치
    nocmp (기본 validate_data.US_FGN_NOCMP) 를 따라요: line · own 은 비우고 표시, keep 은 비우지 않고 반환의 kept 에 적어요.
    반환에 kind = {티커: {칸: 종류}} (표시와 같아요) · kept · nocmp 도 담아요."""
    nocmp = US_FGN_NOCMP if nocmp is None else nocmp
    done = {} if done is None else done
    checked, cut, seen = done.setdefault("checked", []), done.setdefault("cut", []), done.setdefault("seen", set())
    kind, kept = done.setdefault("kind", {}), done.setdefault("kept", [])
    for rec in out:
        t = rec["t"]
        rec.pop("fgnCut", None)
        if t not in foreign or rec.get("fcur"):
            seen.add(t)
            continue
        e = cache.get(t) or {}
        if t in no_info or not e:
            checked.append(t)
            seen.add(t)
            continue
        cuts = us_foreign_cuts(rec, e.get("info"), us_div_12m(_div_col(data, t), us_px_date))
        kinds = {f: us_fgn_kind(f, why, nocmp) for f, why in sorted(cuts.items())}
        for f, why in sorted(cuts.items()):
            if kinds[f] is None:                     # 스위치 keep: 맞춰 볼 값이 없는 칸은 비우지 않아요 (야후 숫자 그대로 · 기록만)
                kept.append([t, f, why])
        cuts = {f: why for f, why in cuts.items() if kinds[f] is not None}
        if cuts:            # 표시 먼저, 그다음 비우기 (어느 칸도 표시 없이 비지 않게)
            rec["fgnCut"] = {f: kinds[f] for f in sorted(cuts)}
            kind[t] = dict(rec["fgnCut"])
        for f, why in sorted(cuts.items()):
            rec.pop(f, None)
            cut.append([t, f, why])
        checked.append(t)
        seen.add(t)
    names = {"per": "PER", "pbr": "PBR", "dy": "배당수익률"}
    by_f = {f: [t for t, g, _ in cut if g == f] for f in names}
    n_fc = sum(1 for r in out if r["t"] in foreign and r.get("fcur"))
    unk = sorted({t for t, _f, w in cut if w.startswith(US_FOREIGN_CUR_WHY)})
    if unk:
        log(f"  !! 미국 상장 외국 회사 중 재무제표 통화가 달러로 확인되지 않아 PER · PBR · 배당수익률을 모두 비운 곳 {len(unk)}곳: {', '.join(unk)}")
    log(f"{'  !! ' if cut else '· '}미국 상장 외국 회사의 주당 숫자 (회사 합계 · 실제 배당과 맞춤): 확인 {len(checked)}곳 · 재무제표 통화가 달러가 "
        f"아니라 이미 비운 곳 {n_fc}곳 · " + " · ".join(f"{names[f]} 비움 {len(ts)}곳" + (f" ({', '.join(ts)})" if ts else "")
                                                for f, ts in by_f.items()))
    for t, f, why in cut:
        log(f"     {t} {names[f]}: {why} [{kind.get(t, {}).get(f, '?')}]")
    nr = sorted(t for t, g in kind.items() if g.get("dy") == US_FGN_NOREC)
    if nr:
        log(f"  !! 배당 기록(다운로드의 Dividends 칸) · 가격을 읽지 못해 비운 배당수익률 {len(nr)}곳 (norecord · 우리 쪽 자료가 빠졌어요 — 관문 경고): "
            + ", ".join(nr))
    nc = sorted(f"{t} {names[f]}" for t, g in kind.items() for f, k in g.items() if k.startswith("nocompare"))
    log(f"{'  !! ' if nc else '· '}그중 맞춰 볼 값이 없어 비운 칸 (nocompare · 스위치 {nocmp}: 야후 숫자가 맞을 수도 있어요 — Jack 에게 묻는 중) "
        f"{len(nc)}칸" + (f": {', '.join(nc)}" if nc else ""))
    if kept:
        log(f"  !! 스위치 keep: 맞춰 볼 값이 없어 비우지 않은 칸 {len(kept)}칸 (야후 숫자 그대로 · 표시 없음): "
            + ", ".join(f"{t} {names[f]}" for t, f, _w in kept))
    return {"checked": sorted(checked), "cut": cut, "kind": {t: dict(g) for t, g in sorted(kind.items())}, "kept": list(kept), "nocmp": nocmp}


def us_foreign_stopped(out, done, err, foreign=US_FOREIGN):
    """us_foreign_check 가 멈췄을 때 (리뷰 N1): 끝까지 본 종목(done["seen"])의 비운 칸 · 표시(fgnCut)는 그대로 두고, 아직 보지 못한 외국 회사
    (fcur 없음)의 PER · PBR · 배당수익률을 모두 비워요 — 맞춰 보지 못한 숫자는 내보내지 않아요. 남아 있던 예전 표시는 지우고, 비운 칸마다 표시
    stopped 를 적어요 (Jack, 2026-11-15 Q10: 앱이 그 칸 밑에 "오늘은 이 숫자를 확인하지 못해서 비워 두었어요." 를 붙여요 — 예전엔 줄 없이
    '자료가 없어요' 였어요 · 관문은 경고). -> data.json usForeign"""
    seen = set(done.get("seen") or ())
    cut = [list(x) for x in done.get("cut") or []]
    kept_n = len(cut)
    why = f"{US_FOREIGN_STOP_WHY} ({type(err).__name__})"
    kind = {t: dict(g) for t, g in sorted((done.get("kind") or {}).items()) if t in seen}
    for r in out:
        if r["t"] not in foreign or r.get("fcur") or r["t"] in seen:
            continue
        r.pop("fgnCut", None)
        blank = [f for f in ("per", "pbr", "dy") if r.get(f) is not None]
        if blank:     # Jack, 2026-11-15 (Q10): 표시 stopped 먼저 — 앱이 그 칸 밑에 '오늘은 이 숫자를 확인하지 못해서 비워 두었어요.' 를 붙여요
            r["fgnCut"] = {f: "stopped" for f in blank}
            kind[r["t"]] = dict(r["fgnCut"])
        for f in blank:
            r.pop(f, None)
            cut.append([r["t"], f, why])
    checked = sorted(r["t"] for r in out if r["t"] in foreign and not r.get("fcur"))
    kept = [list(x) for x in done.get("kept") or [] if x[0] in seen]
    log(f"  !! 미국 상장 외국 회사 검사가 멈췄어요 ({type(err).__name__}: {str(err)[:120]}) → 끝까지 본 {len(seen & set(checked))}곳의 비운 칸 "
        f"{kept_n}칸은 그대로 · 나머지 {len(cut) - kept_n}칸을 맞춰 보지 않고 비웠어요 (줄: 오늘은 확인하지 못함 · 표시 stopped): "
        + (", ".join(f"{t} {f}" for t, f, _w in cut[kept_n:]) or "없음"))
    return {"checked": checked, "cut": cut, "kind": kind, "kept": kept, "nocmp": US_FGN_NOCMP}


def prev_foreign_set(prev):
    """어제 발행한 data.json 의 usForeign.set (티커 → [나라, 통화, 근거]) · 없거나 모양이 다르면 None. (순수 함수)"""
    u = prev.get("usForeign") if isinstance(prev, dict) else None
    st = u.get("set") if isinstance(u, dict) else None
    return {t: v for t, v in st.items() if isinstance(t, str)} if isinstance(st, dict) else None


def us_extra_missing(extra, kept, why):
    """EXTRA_US 중 오늘 발행 목록(kept)에 없는 종목 → {티커: 빠진 이유}. 이유를 적지 못한 종목은 그렇다고 적어요 (관문이 이름과 함께 경고 ·
    기록 자체가 없으면 발행 때 경고 · 목록에도 기록에도 없는 종목은 경고, 5곳 넘으면 실패 — validate_data.check_us_extra). (순수 함수)"""
    return {t: why.get(t) or "발행 목록에 없음 (빠진 까닭을 파이프라인이 적지 못했어요 — 확인 필요)" for t in extra if t not in kept}


US_NO_PX_WHY = "야후가 가격을 하나도 주지 않음 (다운로드에 이 종목의 종가가 없어요)"   # fetch_us 가 적는 이유 (usListSym.noPx 가 이 글로 골라요)
US_NO_PX_ERR = "시세를 받지 못함"     # … 그 종목을 처리하다 오류로 멈춘 경우의 머리말 (usListSym.spErr · 가격이 없다는 뜻이 아니에요 · 리뷰 5)


def joined_in(t, sp500):
    """야후 티커 t 의 점이 지워진 꼴(표 US_CLASS_JOINED 에서 t 로 바뀌는 열쇠, 또는 대시를 뺀 꼴)이 S&P 500 목록 티커(sp500)에 그대로 있으면 그 꼴,
    아니면 None. (순수 함수)"""
    keys = {k for k, (y, _key) in US_CLASS_JOINED.items() if y == t} | {t.replace("-", "")}
    hit = sorted(k for k in keys if k != t and k in (sp500 or ()))
    return hit[0] if hit else None


def us_list_sym(symrec, sp500, sp_ok, asked, kept, why, added=None):
    """data.json usListSym (2026-11-15 · 주식 종류 티커). (순수 함수)
    symrec: us_tickers 가 남긴 {"mapped", "unmapped"} (None = 이 실행에 기록이 없음) · sp500: S&P 500 목록의 티커 (야후 모양 · 못 읽었으면 None) ·
    sp_ok: 그 목록을 믿었는지 (fetch_us · #133) · asked: 야후에 요청한 티커 · kept: 오늘 발행 목록의 티커 · why: 요청한 티커 → 빠진 이유.
    → {"read": 기록이 있었는지, "mapped", "unmapped", "spTickers": S&P 500 목록의 티커 (야후 모양 · 못 읽었으면 None — 관문이 점이 지워진 꼴이
       S&P 500 목록에서 바뀌지 않고 실렸는지 봐요), "spGone": S&P 500 목록 종목 중 오늘 없는 티커 → 이유 (믿지 못한 날 None),
       "noPx": 그중 야후가 가격을 하나도 주지 않은 티커 (점이 지워진 새 주식 종류 티커의 모습 · 믿지 못한 날 None),
       "spErr": 그중 처리하다 오류로 멈춘 티커 (가격이 없다는 뜻이 아니에요 · 믿지 못한 날 None),
       "missing": 더한 종목(US_CLASS_ADDED) 중 오늘 없는 티커 → 이유 (관문: 빠지면 이유가 있든 없든 경고 · Jack 2026-11-20)}"""
    added = US_CLASS_ADDED if added is None else added          # 부를 때의 표 (정의할 때 묶지 않아요)
    read = isinstance(symrec, dict)
    mapped = [list(x) for x in (symrec or {}).get("mapped") or []] if read else []
    unmapped = [list(x) for x in (symrec or {}).get("unmapped") or []] if read else []
    unsure = "발행 목록에 없음 (빠진 까닭을 파이프라인이 적지 못했어요 — 확인 필요)"
    sp_gone = no_px = sp_err = None
    if sp_ok and sp500 is not None:
        sp_gone = {t: (why.get(t) or unsure) if t in asked else "미국 요청 목록에 없음 (확인 필요)" for t in sorted(sp500) if t not in kept}
        no_px = [t for t, w in sp_gone.items() if w == US_NO_PX_WHY]
        sp_err = [t for t, w in sp_gone.items() if w.startswith(US_NO_PX_ERR)]
    missing = {}
    for t in added:
        if t in kept:
            continue
        hit = [w for _s, _a, w in unmapped if isinstance(w, str) and f"→ {t})" in w]
        if t in asked:
            missing[t] = why.get(t) or unsure
        elif hit:
            missing[t] = f"출처 티커를 야후 모양으로 바꾸지 못해 요청하지 않음 ({hit[0]})"
        elif not read:
            missing[t] = "출처 티커 기록이 없음 (미국 목록을 읽은 기록이 없어요 — 확인 필요)"
        elif sp500 is None:
            missing[t] = "S&P 500 목록을 읽지 못해 요청하지 않음"
        elif joined_in(t, sp500):
            # 리뷰 2차 1: 지워진 꼴이 그대로 S&P 500 목록에 있어요 (표의 줄을 잃었거나 바꾸기가 고장) — '지수에서 빠짐'이 아니에요.
            # 표에 줄이 없어도 알아보게 대시를 뺀 꼴(BF-B → BFB)도 봐요 (표의 모든 줄이 그 꼴이에요 · 시험이 지켜요).
            k = joined_in(t, sp500)
            missing[t] = f"S&P 500 목록에 점이 지워진 꼴 {k} 로 있는데 {t} 로 바뀌지 않음 (바꾸기 확인 필요 · RUNBOOK 'US share-class tickers')"
        else:
            missing[t] = "오늘 S&P 500 목록에 없음 (지수에서 빠졌는지 확인)"
    return {"read": read, "mapped": mapped, "unmapped": unmapped, "spTickers": sorted(sp500) if sp500 is not None else None,
            "spGone": sp_gone, "noPx": no_px, "spErr": sp_err, "missing": missing}


def log_us_list_sym(u):
    """us_list_sym 결과를 크게 남겨요 (바꾼 티커 · 바꾸지 못한 티커는 us_tickers 가 이미 남겨요)."""
    if not u["read"]:
        log("  !! 미국 목록 출처 티커 기록이 없어요 (us_tickers 가 기록을 남기지 않음) → 주식 종류 티커를 확인하지 못했어요 (관문 경고)")
    g = u["spGone"]
    if g is None:
        log("· S&P 500 목록을 믿지 못한 날이라 그 목록 종목 중 오늘 없는 종목은 세지 않았어요")
    else:
        log(f"· S&P 500 목록 종목 중 오늘 목록에 없는 종목: {len(g)}개" + (": " + " · ".join(f"{t} ({w})" for t, w in list(g.items())[:30])
                                                                + (f" 외 {len(g) - 30}개" if len(g) > 30 else "") if g else ""))
    if u["noPx"]:
        log(f"  !! S&P 500 목록 종목인데 야후가 가격을 하나도 주지 않은 티커 {len(u['noPx'])}개: {', '.join(u['noPx'])} — 점이 지워진 주식 종류 "
            "티커일 수 있어요 (위키백과 표의 점 꼴 · 야후 대시 꼴의 회사 이름을 확인하고 fetch_data.US_CLASS_JOINED 에 · RUNBOOK · 관문 경고)")
    if u.get("spErr"):
        log(f"  !! S&P 500 목록 종목인데 처리하다 오류로 멈춘 티커 {len(u['spErr'])}개: "
            + " · ".join(f"{t} ({(u['spGone'] or {}).get(t)})" for t in u["spErr"][:20]) + " (관문 경고)")
    m = u["missing"]
    log(f"{'  !! ' if m else '· '}주식 종류 티커를 바꿔 들어온 미국 종목({', '.join(US_CLASS_ADDED)}) 중 오늘 목록에 없는 종목: {len(m)}개"
        + (": " + " · ".join(f"{t} ({w})" for t, w in sorted(m.items())) if m else ""))


def us_fcur_summary(us, infos, no_info=frozenset()):
    """미국 종목 중 재무제표 통화가 달러가 아닌 곳(fcur)과 통화를 모르는 회사. (순수 함수)
    us: 발행할 미국 목록 (apply_us_info 를 지난 rec) · infos: 티커 → 야후 info · no_info: 상세 정보를 붙이지 못한 티커 (셀 것이 없어요).
    hit 은 fcur 가 붙은 모든 종목 (ETF 도 — 관문이 세는 것과 같아요) · unknown 은 회사 주식(ETF · 펀드 빼고)만 (ETF 는 재무제표가 없어요).
    반환 {"hit": [(티커, 통화)], "byCur": {통화: 곳}, "cut": {칸: 야후 값이 있던 곳}, "unknown": [티커], "quoteCur": [(티커, 가격 통화)]}.
    cut 은 야후가 그 칸의 값을 준 곳 수예요 (비우지 않았다면 실렸을 값: 범위 밖 값도 세요). quoteCur: 야후가 가격 통화(currency)를
    달러가 아니라고 한 종목 (가격은 달러로 다뤄요 — 비우지 않고 크게 남겨요)."""
    src = {"per": "trailingPE", "pbr": "priceToBook", "dy": "dividendYield"}
    hit, unknown, quote, zero, cut = [], [], [], [], {k: 0 for k in US_FCUR_BLANK}
    for r in us:
        if r.get("t") in no_info:
            continue
        info = infos.get(r["t"]) or {}
        qc = info.get("currency")
        if isinstance(qc, str) and qc.strip() and qc.strip().upper() != US_QUOTE_CUR:
            quote.append((r["t"], qc.strip()))
        if r.get("fcur"):
            hit.append((r["t"], r["fcur"]))
            if r.get("dy") == 0:
                zero.append(r["t"])                       # 지난 12개월 배당 없음이 분명해 0% 를 남긴 회사 (us_no_dividend_12m)
            for k in US_FCUR_BLANK:
                cut[k] += _fin(info.get(src[k])) is not None and not (k == "dy" and r.get("dy") == 0)
        elif us_fin_currency(info) is None and r.get("etf") is not True and not r.get("fund"):
            unknown.append(r["t"])
    by = collections.Counter(c for _, c in hit)
    return {"hit": sorted(hit), "byCur": dict(sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))), "cut": cut, "unknown": sorted(unknown),
            "quoteCur": sorted(quote), "zeroDy": sorted(zero)}


def log_us_fcur(sm):
    """us_fcur_summary 결과를 크게 남겨요 (CLAUDE.md: 비운 값은 수와 함께)."""
    names = {"per": "PER", "pbr": "PBR", "dy": "배당수익률"}
    if sm["hit"]:
        log(f"· 미국 재무제표 통화가 달러가 아닌 회사: {len(sm['hit'])}곳 (통화별 " + " · ".join(f"{c} {n}" for c, n in sm["byCur"].items())
            + ") — " + "·".join(names[k] for k in US_FCUR_BLANK) + " 비움 (야후 값이 있던 곳: "
            + " · ".join(f"{names[k]} {sm['cut'][k]}" for k in US_FCUR_BLANK) + " · 가치 점수 vz 도 없음): "
            + ", ".join(f"{t}({c})" for t, c in sm["hit"]))
        z = sm.get("zeroDy") or []
        log(f"· 그중 배당수익률 0% 를 남긴 회사 (야후가 지난 12개월 배당 없음을 분명히 말함 · Jack 2026-11-13): {len(z)}곳"
            + (f" ({', '.join(z)})" if z else ""))
    else:
        log("· 미국 재무제표 통화가 달러가 아닌 회사: 없음")
    u = sm["unknown"]
    if u:
        log(f"  !! 미국 재무제표 통화를 모르는 회사 {len(u)}곳 (야후가 financialCurrency 를 주지 않았거나 예전 보관본) — 비우지 않았어요: "
            + ", ".join(u[:40]) + (f" 외 {len(u) - 40}곳" if len(u) > 40 else ""))
    else:
        log("· 미국 재무제표 통화를 모르는 회사: 없음")
    q = sm.get("quoteCur") or []
    if q:
        log(f"  !! 야후가 가격 통화(currency)를 달러가 아니라고 한 미국 종목 {len(q)}곳 — 가격은 달러로 다뤄요 (비우지 않았어요 · 확인 필요): "
            + ", ".join(f"{t}({c})" for t, c in q[:20]) + (f" 외 {len(q) - 20}곳" if len(q) > 20 else ""))


def fetch_us(start, today, rf, kr_codes=frozenset(), dups=None, prev_fgn=None, prev=None):
    """미국 주식 (yfinance). v17.5.2: 우선주·예탁증서와 한국 종목의 미국 상장분(kr_codes · dups)은 빼요 (clean_us_list). v17.5:
    · end 는 그날을 빼므로 오늘(KST)+1일까지 요청하고, 장이 안 끝난 봉은 버려요 (예전엔 하루 늦었어요).
    · 시가총액(cap)은 조원, 거래대금(val)은 억원 — 한국과 같은 단위 (그날 환율로 환산).
    · 상세 정보(이름·업종·설명)를 못 받은 종목 수를 남기고, 실패분은 한 번 더 천천히 시도해요.
    prev_fgn (2026-11-14 Q5 리뷰 S2): 어제 발행한 data.json usForeign.set — S&P 500 목록을 쓸 수 없는 날 외국 회사 판별이 이어 써요.
    prev (2026-11-20 · Jack): 지난 발행본 data.json — 미국 기준일 종가가 야후에 없는 종목을 그 발행본의 마지막 확인 종가로 실어요 (us_own_close_step)."""
    import yfinance as yf

    list_names = UsListNames()
    syms = us_tickers(list_names)
    sp500 = list_names.sp500 if isinstance(getattr(list_names, "sp500", None), frozenset) else None   # 2026-11-14 Q5: 외국 회사 판별용
    symrec = getattr(list_names, "sym", None)   # 2026-11-15: 출처 티커를 야후 모양으로 바꾼 기록 (us_tickers · 가짜 us_tickers 면 None)
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

    # v19.6a: actions=True 는 요청을 늘리지 않아요 (야후 응답에 분할·배당 사건이 늘 들어 있고, 이 값은 그 칸을 버리지 않을 뿐) —
    # 종가(Close)는 그대로예요. 분할 칸(Stock Splits)으로 data.json splits 를 만들어요 (us_splits).
    data = yf.download(syms, start=start, end=end_x, progress=False,
                       auto_adjust=True, group_by="ticker", threads=True, actions=True)

    out, dropped, bad_bar = [], [], []
    nocl = {}            # 2026-11-20 (Jack): 미국 기준일 종가가 야후에 없는 종목 → 까닭 (us_own_close_step 이 마지막 확인 종가로 실어요)
    asked = set(syms)
    extra_why = {t: "미국 요청 목록에 없음 (티커 모양)" for t in EXTRA_US if t not in asked}   # 2026-11-14: EXTRA_US 가 빠진 이유 (usExtraMissing)
    for sym in syms:
        try:
            # 2026-11-20: 끝에 붙은 무한 · 0 · 음수 봉은 종가가 없는 날로 봐요 (가격 0 인 행이 나가지 않게 · 그 종목은 마지막 확인 종가로)
            px = us_px_tail_clean(cut_at(_yf_close(data, sym), us_px_date))
            if len(px) < 60:
                extra_why[sym] = (f"가격 이력 {len(px)}일 (60일 미만이라 넣지 않아요)" if len(px) else US_NO_PX_WHY)
                if not len(px):
                    nocl[sym] = "empty"
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
            if px.index[-1].date() != us_px_date:
                nocl[sym] = "bar"
        except Exception as e:
            dropped.append(sym)
            extra_why[sym] = f"시세를 받지 못함 ({type(e).__name__})"
            nocl[sym] = "err"
    for sym in bad_bar:
        extra_why[sym] = f"미국 기준일 {us_px_date} 봉 앞의 봉이 깨짐 (0 · 무한)"
    if dropped:
        log(f"  !! 시세를 받지 못해 빠진 미국 종목 {len(dropped)}개: {', '.join(dropped[:8])}{'…' if len(dropped) > 8 else ''}")
    if bad_bar:
        log(f"  !! 기준일 {us_px_date} 봉은 있는데 그 전 봉이 깨져(0·무한) 뺀 미국 종목 {len(bad_bar)}개: {', '.join(bad_bar)}")
    # 2026-11-20 (Jack): 야후 종가가 없는 종목 → 지난 발행본의 마지막 확인 종가로 (상세 정보를 붙이기 전에 — 시가총액 · PER 이 그 가격으로 맞춰져요).
    # 가격을 하나도 받지 못한 티커는 지난 발행본에 있었거나 잠시 뺀 종목일 때만 봐요 (야후가 모르는 티커는 예전처럼 빠져요 · 로그가 시끄럽지 않게)
    try:
        pus = {str(x.get("t")) for x in (prev or {}).get("stocks") or [] if isinstance(x, dict) and x.get("cls") == "us"}
        paged = {str(a.get("t")) for a in ((((prev or {}).get("usSrc") or {}).get("own") or {}).get("aged") or []) if isinstance(a, dict)}
    except Exception as e:
        pus, paged = set(), set()
        log(f"  !! 지난 발행본의 미국 종목 · 잠시 뺀 종목을 읽지 못했어요 ({type(e).__name__}) — 가격을 하나도 받지 못한 티커는 마지막 확인 종가로 보지 않아요 "
            "(기준일 봉만 빠진 종목은 그대로 봐요)")
    nocl = {t: w for t, w in nocl.items() if w == "bar" or t in pus or t in paged}
    # 2026-11-22 (Jack): 지난 발행본에 없던(새로 들어온) 종목은 미국 기준일 종가가 확인된 날부터 — 종가가 없으면 그 행을 빼고 usSrc.newWait 에 적어요
    # (마지막 확인 종가가 없어 예전이면 야후의 더 오래된 봉을 자기 날짜로 실었어요 · 아래 분할 칸 읽기 · 마지막 확인 종가 단계 · 상세 정보에도 가지 않아요)
    new_wait = us_new_wait_step(prev, nocl, out, extra_why, us_px_date)
    # 리뷰 (2026-11-20, 분할): 그 종목들의 분할 날짜 — 오늘 다운로드의 분할 칸 · 지난 발행본의 splits · 고정 표. 마지막 확인 종가 뒤에 분할이 있으면
    # 싣지 않아요 (예전 그대로: 야후의 자기 날짜 봉 · 분할을 반영한 야후 시계열)
    # 2차 확인 (2): 읽다가 멈추면 종목마다 다시 읽고, 그래도 읽지 못한 종목은 분할을 모르니 싣지 않아요 (예전 그대로: 야후의 자기 날짜 봉 · 없으면 빠짐)
    nsp, sp_unread = [], set()
    try:
        nsp = us_splits(data, sorted(nocl), today)[0] if nocl else []
    except Exception as e:
        for t in sorted(nocl):
            try:
                nsp += us_splits(data, [t], today)[0]
            except Exception:
                sp_unread.add(t)
        log(f"  !! 야후 종가가 없는 미국 종목의 분할 칸을 한꺼번에 읽지 못했어요 ({type(e).__name__}) — 종목마다 다시 읽음 · 그래도 읽지 못한 "
            f"{len(sp_unread):,}종목은 마지막 확인 종가로 싣지 않아요 (예전 그대로 · usSrc.own.split unread)" + (f": {', '.join(sorted(sp_unread)[:30])}" if sp_unread else ""))
    ybar0 = {r["t"]: dict(r) for r in out if r.get("t") in nocl and r.get("pxd") is not None and r.get("d1") is None}
    us_own = us_own_close_step(prev, nocl, out, us_px_date, list(spx.index), etfs=US_ETFS, split_dates=us_carry_splits(nsp, prev),
                               split_unread=frozenset(sp_unread))
    us_own_yahoo = {t: ybar0[t] for t in us_own.get("codes") or [] if t in ybar0}   # 발행할 splits 로 다시 볼 때 예전 길로 되돌릴 야후의 자기 날짜 봉
    for a in us_own.get("aged") or []:      # EXTRA_US · 주식 종류 티커 줄이 빠진 까닭을 적어요
        extra_why[a["t"]] = f"마지막 확인 종가({a.get('pxd')}) 뒤 미국 거래일 {US_OWN_CLOSE_MAX_DAYS}일이 지나 잠시 뺌 (usSrc.own.aged)"

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
        anchor, no_anchor = rec.get("price"), False
        if rec.get("pxc"):
            # 리뷰 (2026-11-20): 마지막 확인 종가(pxc) 종목의 상세 정보 — 야후의 PER · PBR · 시가총액 · 배당수익률은 야후의 지금 시세 가격 기준이에요.
            # 그 가격을 기준 가격(px)으로 적어야 apply_us_info 가 실은 종가에 맞춰요 (그 종가를 적으면 배율이 1 이라 시세 가격 기준 숫자가 그대로 나가요)
            q = next((v for v in (_fin(info.get("currentPrice")), _fin(info.get("regularMarketPrice"))) if v is not None and v > 0), None)
            cp = _fin(rec.get("price"))
            if q is not None and cp and abs(q / cp - 1) > US_QUOTE_FAR:   # 리뷰 (2026-11-20, 4): 실은 종가와 너무 다른 시세 가격은 쓰지 않아요
                pxc_info["far"].append(rec["t"])
                q = None
            if q is not None:
                anchor = q
                pxc_info["quote"].append(rec["t"])
            else:
                a0 = age(rec["t"])
                if a0 is not None and a0 <= US_INFO_MAX_AGE_DAYS and not (cache.get(rec["t"]) or {}).get("pxBad"):
                    pxc_info["kept"].append(rec["t"])
                    return True                                       # 14일 안의 보관본 그대로 (그날 종가에 맞춘 값)
                no_anchor = True
                pxc_info["blank"].append(rec["t"])
        new = {k: info.get(k) for k in US_INFO_KEYS if info.get(k) is not None}
        merged, kept, kage = us_info_merge(new, cache.get(rec["t"]), today)   # #114 리뷰: 시세만 담은 응답이 통화 · 업종 · 설명을 지우지 않게
        if kept:
            sticky[rec["t"]] = (kept, kage)
        entry = {"at": tday, "px": anchor, "k": US_INFO_SCHEMA, "info": merged}
        if no_anchor:
            entry["pxBad"] = True       # 기준 가격을 몰라요: 이 항목의 PER · PBR · 시가총액 · 배당수익률은 쓰지 않아요 (다음 실행에서 다시 물어봐요)
            entry["due"] = True
        if us_info_partial(merged, kept, rec.get("etf") is True):
            entry["due"] = True                                       # #114 리뷰 2: 일부만 온 응답 — 다음 실행에서 다시 물어봐요
            partial.add(rec["t"])
        cache[rec["t"]] = entry
        return True

    sticky, partial = {}, set()
    pxc_info = {"quote": [], "kept": [], "blank": [], "far": []}
    need = [r for r in out if us_info_due(cache.get(r["t"]), today)]
    # 2026-11-14 (Q5): 본사 나라(country)가 없는 S&P 500 밖 회사 항목도 오늘 다시 받아요 (외국 회사 판별 · 모양 표시는 그대로라 그 회사들만)
    # 2026-11-14 (리뷰 S2): S&P 500 목록은 오늘 가격을 받은 종목과 US_SP500_MIN 곳 넘게 겹칠 때만 믿어요 (목록 칸 이름이 바뀌어 티커 대신 다른
    # 글이 들어오거나 목록이 빈 날 · S&P 500 회사를 가려내지 못하면 미국 밖에 본사를 둔 미국 회사의 맞는 배당수익률이 비어요)
    sp_in = len(sp500 & {r["t"] for r in out}) if sp500 is not None else 0
    sp_ok = sp500 is not None and sp_in >= US_SP500_MIN and len(sp500) <= US_SP500_MAX   # 리뷰 2차 N3: 너무 큰 목록도 믿지 않아요
    sp_use = sp500 if sp_ok else None
    sp_rec = {"n": len(sp500) if sp500 is not None else None, "inList": sp_in, "ok": sp_ok}
    if not sp_ok:
        log(f"  !! S&P 500 목록을 쓸 수 없어요 (" + ("읽지 못함" if sp500 is None else f"목록 {len(sp500):,}곳 · 오늘 미국 목록과 겹침 {sp_in:,}곳")
            + f" — 겹침 {US_SP500_MIN}곳 이상 · 목록 {US_SP500_MAX}곳 이하여야 해요) → 오늘은 본사 나라 규칙을 쓰지 않고 손으로 정한 21곳 · 재무제표 통화가 달러가 아닌 회사 · 어제 발행한 "
            f"외국 회사 목록({len(prev_fgn) if isinstance(prev_fgn, dict) else 0}곳)만 맞춰 봐요 (관문 경고)")
    else:
        log(f"· S&P 500 목록 {len(sp500):,}곳 · 오늘 미국 목록과 겹침 {sp_in:,}곳 (외국 회사 판별에 써요)")
    due_t = {r["t"] for r in need}
    due_c = [r for r in out if r["t"] not in due_t and us_country_due(cache.get(r["t"]), r["t"], sp_use)]
    if due_c:
        need += due_c
        log(f"  !! 미국 상세 정보 보관본에 본사 나라(country)가 없는 S&P 500 밖 회사 {len(due_c):,}곳 → 받은 날과 상관없이 오늘 다시 받아요 "
            f"(외국 회사 판별용 · 오늘 받을 곳 모두 {len(need):,}곳)")
    old_shape = sum(1 for r in out if cache.get(r["t"]) and cache[r["t"]].get("k") != US_INFO_SCHEMA)
    if old_shape:
        log(f"  !! 미국 상세 정보 보관본 중 예전 모양(표시 k 가 {US_INFO_SCHEMA} 이 아님 — 재무제표 통화 · 매출 칸을 담기 전) {old_shape:,}곳 → "
            f"받은 날과 상관없이 오늘 다시 받아요 (한 번만 · 오늘 받을 곳 모두 {len(need):,}곳)")
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
    px_blank = []
    for rec in out:
        a = age(rec["t"])
        if a is None or a > US_INFO_MAX_AGE_DAYS or not apply_us_info(rec, cache[rec["t"]]["info"], cache[rec["t"]].get("px"), fx_last, today=today):
            missing.append(rec["t"])
            continue
        if cache[rec["t"]].get("pxBad"):     # 리뷰 (2026-11-20): 기준 가격을 모르는 항목 — 가격에 맞출 수 없는 네 숫자는 비워요 (틀린 숫자 대신)
            for k in US_PX_ANCHORED:
                rec.pop(k, None)
            px_blank.append(rec["t"])
        if rec["t"] in failed_t:
            fallback += 1
            oldest = max(oldest, a)
        elif a > 0:
            reused += 1
    save_us_info(cache)
    # 리뷰 (2026-11-20, 잔 지적): 마지막 확인 종가 종목마다 한 가지로 세요 (더하면 그 종목 수)
    pcs = [r["t"] for r in out if r.get("pxc")]
    cat = collections.Counter()
    blank_pc = []
    for t in pcs:
        if t in missing:
            cat["none"] += 1
        elif t in px_blank:
            cat["blank"] += 1
            blank_pc.append(t)
        elif t in pxc_info["quote"]:
            cat["quote"] += 1
        elif t in pxc_info["kept"]:
            cat["kept"] += 1
        else:
            cat["cache"] += 1
    if pcs:
        log(f"{'  !! ' if blank_pc or pxc_info['far'] else '· '}마지막 확인 종가 종목 {len(pcs):,}개의 상세 정보: 오늘 받아 야후 시세 가격에 맞춤 "
            f"{cat['quote']:,} · 3일 안에 받은 보관본 (또는 오늘 받지 못해 보관본) {cat['cache']:,} · 시세 가격이 없거나 실은 종가와 "
            f"{US_QUOTE_FAR:.0%} 넘게 달라 {US_INFO_MAX_AGE_DAYS}일 안의 보관본 그대로 {cat['kept']:,} · 기준 가격을 몰라 PER · PBR · 시가총액 · "
            f"배당수익률을 비움 {cat['blank']:,}" + (f" ({', '.join(blank_pc[:30])})" if blank_pc else "") + f" · 상세 정보 없음 {cat['none']:,}"
            + (f" — 시세 가격이 {US_QUOTE_FAR:.0%} 넘게 달라 쓰지 않음 {len(pxc_info['far']):,} ({', '.join(pxc_info['far'][:30])})" if pxc_info["far"] else ""))
    other_blank = [t for t in px_blank if t not in set(pcs)]
    if other_blank:
        log(f"  !! 기준 가격을 모르는 보관본이라 PER · PBR · 시가총액 · 배당수익률을 비운 미국 종목 (마지막 확인 종가가 아님 · 오늘 다시 받지 못함) "
            f"{len(other_blank):,}: {', '.join(other_blank[:30])}")
    if sticky:
        fc_kept = sorted(t for t, (ks, _a) in sticky.items() if "financialCurrency" in ks)
        other = sorted(t for t, (ks, _a) in sticky.items() if any(k != "financialCurrency" for k in ks))
        ages = [a for _ks, a in sticky.values() if a is not None]
        oldest = f" · 가장 오래된 예전 값 {max(ages)}일 전" if ages else ""
        if fc_kept:
            log(f"  !! 야후 응답에 재무제표 통화가 없어 예전 값을 그대로 씀: {len(fc_kept)}곳{oldest} ({', '.join(fc_kept[:30])}"
                + (f" 외 {len(fc_kept) - 30}곳" if len(fc_kept) > 30 else "") + ")")
        if other:
            log(f"  !! 야후 응답에 빠진 설명 칸(이름 · 종류 · 업종 · 설명 · 가격 통화)을 예전 값으로 씀: {len(other)}곳{oldest} ({', '.join(other[:30])}"
                + (f" 외 {len(other) - 30}곳" if len(other) > 30 else "") + ")")
    if partial:
        ps = sorted(partial)
        log(f"  !! 일부만 온 야후 응답(예전 값으로 채움 · 또는 회사인데 재무제표 통화 없음) {len(ps)}곳 → 다음 실행에서 다시 물어봐요: "
            + ", ".join(ps[:30]) + (f" 외 {len(ps) - 30}곳" if len(ps) > 30 else ""))
    cut_t = {}
    for rec in out:
        e = cache.get(rec["t"])
        if rec["t"] in missing or not e:
            continue
        for f in us_info_cuts(e["info"], us_rescale(rec.get("price"), e.get("px"))):
            if not (f in US_FCUR_BLANK and rec.get("fcur")):                  # fcur 회사의 PBR 은 이미 비었어요 (아래 줄이 세요)
                cut_t.setdefault(f, []).append(rec["t"])
    for f, why in (("pbr", "PBR 이 0.00 으로 반올림돼(0.005 미만) 빈 칸 — 가치 점수도 없음"),
                   ("opm", "영업이익률이 정확히 0 인데 매출(totalRevenue)이 없어 빈 칸")):
        ts = sorted(cut_t.get(f, []))
        log(f"{'  !! ' if ts else '· '}미국 {why}: {len(ts)}곳" + (f" ({', '.join(ts[:30])}" + (f" 외 {len(ts) - 30}곳" if len(ts) > 30 else "") + ")" if ts else ""))
    # v19.6b (Part B.1): 미국 일정 — 실적 발표일(ed · 야후가 확정이라고 적은 것만) · 배당락일(xd). 상세 정보가 붙은 종목만 세요
    shown = [r for r in out if r["t"] not in missing and cache.get(r["t"])]
    no_keys = sum(1 for r in shown if "isEarningsDateEstimate" not in (cache[r["t"]].get("info") or {}))
    est = sum(1 for r in shown if (cache[r["t"]].get("info") or {}).get("isEarningsDateEstimate") is True)
    bad_d = sorted({r["t"] for r in shown if us_event_dates(cache[r["t"]].get("info"))[2]})
    log(f"{'  !! ' if bad_d else '· '}미국 일정: 실적 발표일(확정) {sum(1 for r in shown if r.get('ed')):,} · 배당락일 "
        f"{sum(1 for r in shown if r.get('xd')):,} / 상세 정보가 붙은 {len(shown):,}종목 (야후가 추정이라고 적어 빈 칸 {est:,} · 확정 표시가 없어 "
        f"빈 칸 {no_keys:,}: ETF · 야후가 주지 않은 종목 · 이 칸을 담기 전의 보관본 — 보관본은 3일 안에 다시 받아요)"
        + (f" · 날짜를 읽지 못해 빈 칸 {len(bad_d)}곳 ({', '.join(bad_d[:20])})" if bad_d else ""))
    got = len(need) - len(failed)
    n_ok = len(out) - len(missing)
    log(f"{'  !! ' if failed else '· '}미국 상세 정보(이름·업종·설명): {n_ok:,} / {len(out):,} · 오늘 받음 {got:,} · 3일 안에 받은 것 {reused:,}"
        + (f" · 못 받음 {len(failed):,}곳 → 보관본 {fallback:,}곳(최대 {oldest}일 전) · 없음 {len(missing):,}곳"
           + (f" ({', '.join(missing[:8])}…)" if missing else "") if failed or missing else ""))
    log(f"· 미국 완료: {len(out):,}개")
    kept_co = []
    odd = etf_from_quote_type(out, cache, skipped=kept_co)
    if kept_co:
        log(f"  !! 사람이 회사 주식으로 정한 종목(US_NOT_ETF)인데 야후 종류가 ETF·펀드예요 {len(kept_co)}개 → 회사 주식 그대로 둬요 (야후를 확인): "
            + ", ".join(kept_co))
    if odd:
        log(f"  !! 목록엔 회사로 돼 있는데 야후가 ETF·펀드라고 하는 종목 {len(odd)}개 → ETF 로 표시: {', '.join(odd[:10])}")
    infos = {r["t"]: {**((cache.get(r["t"]) or {}).get("info") or {}), "listName": list_names.get(r["t"])} for r in out}
    out, left_out = clean_us_list(out, kr_codes, dups or {}, infos)   # ETF 표시가 끝난 뒤에 (ETF·펀드는 우선주로 보지 않아요)
    no_info = set(missing)
    fsum = us_fcur_summary(out, infos, no_info)                        # Jack, 2026-11-12: 재무제표 통화가 달러가 아닌 회사 (빈 칸은 apply_us_info)
    log_us_fcur(fsum)
    # 2026-11-14: 미국 상장 외국 회사의 PER · PBR · 배당수익률이 회사 합계 · 실제 배당과 맞지 않으면 비워요 (ADR 배율 · 통화 · 야후 '앞으로 1년' 배당)
    # 2026-11-14 (Jack, Q5): 외국 회사는 규칙으로 찾아요 (us_foreign_set: 재무제표 통화 · S&P 500 밖의 미국 밖 본사 · 예탁증서 이름 · 바닥 21곳)
    try:
        fset = us_foreign_set(out, infos, sp_use, prev=prev_fgn)
    except Exception as e:      # 판별 전체가 멈추면 (생기면 안 돼요 · 종목마다 따로 잡아요): 21곳 · fcur · 어제 발행한 set 만 (리뷰 N1 · 관문 경고)
        log(f"  !! 미국 상장 외국 회사를 찾다가 멈췄어요 ({type(e).__name__}: {str(e)[:120]}) → 손으로 정한 21곳 · 재무제표 통화가 달러가 아닌 회사 · "
            f"어제 발행한 외국 회사 목록만 맞춰 봐요 (근거 error · 관문 경고)")
        fset = us_foreign_fallback(out, infos, prev_fgn, basis="error")
        fset["errors"] = [("(전체)", type(e).__name__)]
    try:
        log_us_foreign_set(fset, sp_use)
    except Exception as e:
        log(f"  !! 미국 상장 외국 회사 목록을 적다가 멈췄어요 ({type(e).__name__}) — 외국 회사 {len(fset['set'])}곳 (검사는 그대로 해요)")
    fgn = frozenset(fset["set"])
    fdone = {}
    try:
        ufor = us_foreign_check(out, cache, data, us_px_date, no_info, foreign=fgn, done=fdone)
    except Exception as e:      # 검사가 멈추면: 이미 본 종목은 그대로, 나머지 외국 회사의 세 칸은 비워요 — 크게 남기고 관문이 경고해요
        ufor = us_foreign_stopped(out, fdone, e, foreign=fgn)
    ufor["set"] = fset["set"]               # 관문: 이 회사들(fcur 없음)의 숫자는 모두 checked 에 있어야 하고, 표시(fgnCut)는 이 회사들에만
    ufor["unknown"] = fset["unknown"]       # 관문: 나라를 몰라 외국 회사로 보지 않은 S&P 500 밖 회사 (경고만)
    ufor["sp500"] = sp_rec                  # 관문: S&P 500 목록 크기 · 오늘 목록과 겹침 · 믿었는지 (못 믿은 날은 경고)
    # 2026-11-14: EXTRA_US 중 오늘 목록에 없는 종목과 이유 (data.json usExtraMissing · 관문이 이름과 이유를 남겨요)
    for t in left_out.get("preferred") or []:
        extra_why[t] = "우선주 · 예탁증서로 보고 뺌 (usLeftOut.preferred)"
    for t in left_out.get("krListing") or []:
        extra_why[t] = "한국 종목의 미국 상장분이라 뺌 (usLeftOut.krListing)"
    xmiss = us_extra_missing(EXTRA_US, {r["t"] for r in out}, extra_why)
    log(f"{'  !! ' if xmiss else '· '}손으로 더한 미국 종목(EXTRA_US {len(EXTRA_US)}개) 중 오늘 목록에 없는 종목: {len(xmiss)}개"
        + (": " + " · ".join(f"{t} ({w})" for t, w in sorted(xmiss.items())) if xmiss else ""))
    # 2026-11-15: 출처 티커를 야후 모양으로 바꾼 기록 · S&P 500 목록 종목 중 오늘 없는 것 · 이 바꾸기로 들어온 종목(US_CLASS_ADDED)이 빠진 이유
    usym = us_list_sym(symrec, sp500, sp_ok, asked, {r["t"] for r in out}, extra_why)
    log_us_list_sym(usym)
    n_ok = sum(1 for r in out if r["t"] not in no_info)
    n_d1 = sum(1 for r in out if r.get("d1") is not None)
    log(f"· 미국 d1(전 거래일 대비): {n_d1:,} / {len(out):,} · ETF {sum(1 for r in out if r.get('etf')):,}개")
    no_d1 = [f"{r['t']}({r.get('pxd') or '?'})" for r in out if r.get("d1") is None]
    if no_d1:   # 발행 관문이 98% 아래면 막고 전부 적어요 — 여기서는 앞의 30개 (Jack, 2026-11-07). 괄호 = 그 종목의 자기 가격 날짜(pxd)
        log(f"  !! 미국 d1 없는 종목 {len(no_d1):,}개 (마지막 봉이 미국 기준일 {us_px_date} 이 아님 — 거래 정지이거나 야후가 봉을 "
            f"빠뜨림 · 가격은 괄호 날짜의 종가로 나가요): {', '.join(no_d1[:30])}" + (f" 외 {len(no_d1) - 30:,}개" if len(no_d1) > 30 else ""))
    # v19.6a (A.6): 주식 분할 — 위 다운로드의 분할 칸에서, 목록에 남은 종목만 (새 요청 없음)
    try:
        splits, sinfo = us_splits(data, [r["t"] for r in out], today)
    except Exception as e:
        splits, sinfo = None, {"err": f"{type(e).__name__}: {e}"}
    log_us_splits(splits, sinfo, len(out), today, what=f"미국 주식 분할 (오늘 시세 다운로드 · {start} 부터)")
    meta = {"usPxDate": us_px_date.isoformat(), "fxDate": fx_date.isoformat(), "usInfo": [n_ok, len(out)], "_index": spx,
            "usLeftOut": {**left_out, "badBar": bad_bar},   # v19.1c: 깨진 봉으로 뺀 종목도 관문이 경고로 이름을 남겨요
            "usFcurUnknown": fsum["unknown"],               # #114 리뷰: 재무제표 통화를 모르는 회사 (관문이 경고로 이름을 남겨요)
            "usInfoPartial": sorted(t for t in sticky if t in {r["t"] for r in out}),   # #114 리뷰 2: 오늘 응답이 일부만 와 예전 설명 칸을 쓴 종목
            "usForeign": ufor,                              # 2026-11-14: 외국 회사 주당 숫자 검사 (확인한 종목 · 비운 칸과 이유)
            "usExtraMissing": xmiss,                        # 2026-11-14: EXTRA_US 중 오늘 없는 종목 → 이유 (관문)
            "usListSym": usym,                              # 2026-11-15: 출처 티커 → 야후 모양 · 바꾸지 못한 티커 · S&P 500 중 빠진 종목 (관문)
            # 2026-11-20 (Jack): 야후 종가가 없어 마지막 확인 종가로 실은 종목 (관문 · 앱) · 2026-11-22 (Jack): newWait 새로 들어왔는데 미국
            # 기준일 종가가 없어 오늘 넣지 않은 티커 (있을 때만 — 보통 날의 파일은 예전과 같아요)
            "usSrc": {"v": 1, "own": us_own, **({"newWait": new_wait} if new_wait else {})},
            "_usOwnYahoo": us_own_yahoo,                    # 2차 확인: 실은 종목의 야후 자기 날짜 봉 (us_own_split_late 만 써요 · 파일에 나가지 않아요)
            # v19.6a: None = 분할을 읽다 멈춤 · splitsNoCol = 분할 칸이 없던 종목 (둘 다 main 이 지난 발행본으로 이어요)
            "splits": splits, "splitsNoCol": list(sinfo.get("noCol") or [])}
    return out, bench, fx, fx_last, us_vol_krw, meta


# ────────────────────────────────────────────────────────────
# v19.6a (A.6): data.json splits — 2016-01-01 부터의 미국 주식 분할 [[코드, 날짜, 배율], …]
# ────────────────────────────────────────────────────────────
# 고정 표: 야후 분할 칸이 틀리게 적거나 빠뜨린 진짜 사건(넣어요 · 배율) · 분사인데 깨끗한 배율로 적힌 것(빼요 · None). (코드, 날짜) → (배율 또는
# None, 근거). 날짜 = 새 주식 수로 거래가 시작된 날 (야후 날짜 · 주식배당은 배당락일). 근거를 확인한 줄만 넣어요. data.json splitsInfo.fixed 로
# 실려 관문과 앱이 읽어요 (None 줄 = 앱이 저장해 둔 그 분할을 지워요). 줄을 지우지 마세요 — 지운 줄은 지난 발행본에서 이어 둬요 (RUNBOOK).
SPLIT_OVERRIDES = {
    ("RYAAY", "2024-09-30"): (2.5, "ADS 비율 변경: 1 ADS = 보통주 5주 → 2주, ADS 1개마다 1.5개를 더 받음 (Ryanair SEC 6-K 2024-08-15) — 야후 2499:1000"),
    ("HLT", "2017-01-04"): (1 / 3, "1:3 주식병합 (2017-01-03 효력, 01-04 부터 새 기준 거래 · Hilton SEC 10-K 2017) — 야후는 같은 날 분사(PK · HGV) 조정과 합쳐 250:513"),
    ("DD", "2019-06-03"): (1 / 3, "1:3 주식병합 (2019-06-01 Corteva 분사 직후 효력, 06-03 부터 거래 · DuPont SEC 10-Q 2019) — 야후는 분사 조정과 합쳐 189:400"),
    ("HON", "2026-06-29"): (0.5, "1:2 주식병합 (2026-06-29 00:02 뉴욕 효력, 그날부터 새 기준 거래 · Honeywell 8-K 2026-06-05 · 같은 날 Honeywell "
                                 "Aerospace(HONA) 분사) — 야후는 분사 조정과 합쳐 1907:2000"),
    ("UL", "2025-12-09"): (8 / 9, "8:9 주식 병합 (보통주 · ADS 모두, ADS 1개 = 보통주 1주 그대로 · Magnum Ice Cream Company 분리와 함께 · Unilever RNS "
                               "'Update on share consolidation' 2025-12-08 · 주주 안내서 unilever.com demerger-of-tmicc-and-share-consolidation · "
                               "IRS 8937: 720주 → 640주) — 야후는 분리 조정과 합쳐 ×0.888"),
    ("WTW", "2016-01-05"): (1 / 2.649, "Willis 주식 2.6490주 → 1주 병합 (2016-01-04 Towers Watson 합병 직후 · WTW SEC 10-K 2016) — 야후 151:400"),
    ("TRI", "2018-11-27"): (0.9079, "자본 환급(주당 4.45달러)과 함께 한 주식 병합 1주 → 0.9079주 (2018-11-27 부터 새 기준 거래 · Thomson Reuters 발표 2018-11-26) — 야후에 없음"),
    ("TRI", "2023-06-23"): (0.963957, "자본 환급과 함께 한 주식 병합 1주 → 0.963957주 (2023-06-23 효력 · Thomson Reuters 발표 2023-06-22) — 야후 963:1000"),
    # Commerce Bancshares 해마다 5% 주식배당 (FY2023 10-K: 30년째). 야후에 없는 해만 · 날짜 = 배당락일 (기준일 − 1 영업일, 2016 은 T+3 이라 − 2)
    ("CBSH", "2016-11-30"): (1.05, "5% 주식배당 (지급 2016-12-19 · 회사 주식 기준가 안내 페이지 · 기준일은 12월 현금배당과 같은 날로 봐 배당락 11-30, 배당 사이트) — 야후에 없음"),
    ("CBSH", "2017-11-29"): (1.05, "5% 주식배당 (기준일 2017-11-30 · 지급 12-18 · 회사 발표) — 야후에 없음"),
    ("CBSH", "2019-12-02"): (1.05, "5% 주식배당 (기준일 2019-12-03 · 지급 12-18 · 회사 발표) — 야후에 없음"),
    ("CBSH", "2022-12-01"): (1.05, "5% 주식배당 (기준일 2022-12-02 · 지급 12-16 · 회사 발표 · FY2022 10-K) — 야후에 없음"),
    ("CBSH", "2023-12-01"): (1.05, "5% 주식배당 (기준일 2023-12-04 · 지급 12-19 · 회사 발표) — 야후에 없음"),
}
# FERG 2018-06-11 18:19 병합은 넣지 않아요: 그때 미국에서 거래되던 것은 NYSE 주식(2021-03-08 부터)과 다른 증권(OTC ADR · 2021-03-08 종료)이라
# 미국 FERG 기록이 그 전 날짜일 수 없어요 (야후 값도 깨끗하지 않아 원래 빠져요). GMAB 2018-05-01 5:1 (야후 · 시드)은 둬요: Nasdaq ADS(2019-07-18)는
# 그 전부터 OTC 에서 GMXAY 로 거래되던 같은 ADR 프로그램이라, 2018년 5월 전 보유자의 기록도 같은 증권이에요 (#117 리뷰 4 N-4).
SPLIT_SEED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "us_splits_seed.csv")
SPLIT_SEED_CODES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "us_splits_seed_codes.txt")
# 2026-11-14: 나중에 EXTRA_US 에 더한 종목의 시드 (같은 모양 · 처음 시드는 그대로 두고 따로 — 언제 누가 무엇을 읽어 확인했는지 파일마다 남게).
# 새 종목을 한꺼번에 더할 때 그 종목들의 2016년부터 분할을 미리 읽어 여기 넣어요 (안 넣으면 한 실행에 SPLIT_BACKFILL_MAX 개씩 읽고 나머지는 gap 경고).
SPLIT_SEED_MORE = ((os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "us_splits_seed_more.csv"),
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "us_splits_seed_more_codes.txt")),)
SPLIT_BACKFILL_MAX = 20          # 시드에도 지난 발행본에도 없는 종목의 2016년부터 이력은 한 실행에 이만큼만 읽어요 (나머지는 gap · 다음 실행)
SPLIT_HIST_RETRY_PAUSE = 20      # 받지 못한 종목은 쉬었다가 한 번 더 (천천히)
SPLIT_SAME_EVENT_DAYS = 10       # 같은 종목 · 같은 배율인데 야후 날짜가 이만큼 안에서 달라지면 같은 사건 (실은 날짜를 그대로 두고 diff 에 적어요)


def split_is_clean(r, top=SPLIT_SIMPLE_MAX, tol=SPLIT_CLEAN_TOL):
    """배율이 '깨끗한' 분수인지: q ≤ top 인 p/q (10:1 · 3:2 · 21:20 주식배당) 이거나 그 역수(1:15 병합) — 관문 simple_ratio 와 같은 규칙,
    같은 허용치 (SPLIT_CLEAN_TOL · 배율에 곱해요). 야후는 분사(spin-off)도 분할 칸에 가격 조정 배율로 적어요 (GE 2024-04-02 1253:1000 = 1.253
    · GE 버노바 분사) — 주식 수가 바뀐 게 아니라서 넣으면 앱에서 GE 100주가 125.3주로 보여요. (순수 함수)"""
    if r is None or not (r > 0) or not math.isfinite(r):
        return False
    for x in (r, 1 / r):
        for q in range(1, top + 1):
            p = round(x * q)
            if p >= 1 and abs(x - p / q) <= tol * max(1.0, x):
                return True
    return False


def _same_r(a, b):
    return a is not None and b is not None and abs(a - b) <= SPLIT_CLEAN_TOL * max(1.0, abs(a), abs(b))


def _split_col(data, t):
    """다운로드 결과에서 티커 t 의 'Stock Splits' 칸 (group_by='ticker' 의 (티커, 칸) · 하나만 받았을 때의 (칸, 티커) · 단일 칸). 없으면 None."""
    cols = getattr(data, "columns", None)
    if cols is None:
        return None
    if isinstance(cols, pd.MultiIndex):
        for k in ((t, "Stock Splits"), ("Stock Splits", t)):
            if k in cols:
                return data[k]
        return None
    return data["Stock Splits"] if "Stock Splits" in cols else None


def us_splits(data, codes, today, lo=None):
    """미국 주식 분할 [[티커, 날짜, 배율], …] — 시세 다운로드(actions=True)의 'Stock Splits' 칸에서. (순수 함수)
    날짜 = 야후의 분할 날짜 (미국 현지 날짜 · 새 주식 수로 거래가 시작된 날 · 앱은 이 날짜 앞의 기록을 맞춰요: held.js splitFactor
    `date < s.date`). 배율 = 옛 1주가 새로 몇 주인지 (야후 numerator ÷ denominator 그대로: 10:1 분할 10 · 1:10 병합 0.1 · 앱과 같은 방향).
    lo(SPLITS_FROM) 부터, 오늘(KST) 뒤 날짜는 넣지 않아요 (future). 배율이 앱이 읽는 범위(SPLIT_R) 밖이거나 1 이면 bad, 깨끗한 분수가 아니면
    spin (야후가 분사를 적은 것 — 진짜 사건은 SPLIT_OVERRIDES 로) — 둘 다 넣지 않고 이름을 남겨요. 분할 칸이 없는 종목은 noCol (그 종목의
    분할은 모름 — 빈 목록과 달라요). -> (목록, {"noCol", "future", "bad", "spin"})"""
    lo = dt.date.fromisoformat(SPLITS_FROM) if lo is None else lo
    info = {"noCol": [], "future": [], "bad": [], "spin": []}
    out = []
    for t in codes:
        col = _split_col(data, t)
        if col is None:
            info["noCol"].append(t)
            continue
        got = {}
        for ts, v in col.items():
            r = _fin(v)
            if r is None or r == 0:          # 0 = 그날 분할 없음 (야후 칸의 기본값)
                continue
            d = pd.Timestamp(ts).date()
            if d < lo:
                continue
            if not (SPLIT_R[0] <= r <= SPLIT_R[1]) or r == 1:
                info["bad"].append(f"{t} {d} ×{r:g}")
            elif not split_is_clean(r):
                info["spin"].append(f"{t} {d} ×{r:g}")
            elif d > today:
                info["future"].append(f"{t} {d} ×{r:g}")
            else:
                got[d.isoformat()] = float(r)
        out += [[t, d, r] for d, r in sorted(got.items())]
    return sorted(out), info


def split_ratio_text(r):
    """로그용 배율: 10 → '10:1 분할' · 0.1 → '1:10 병합'. (순수 함수)"""
    return f"{r:g}:1 분할" if r > 1 else f"1:{1 / r:g} 병합"


def log_us_splits(splits, info, n_us, today, what="미국 주식 분할(splits, 야후)"):
    if splits is None:
        log(f"  !! {what}을 읽지 못했어요: {info.get('err')} → 지난 발행본 · 시드의 줄을 그대로 둬요 (관문이 경고해요)")
        return
    recent = sorted(splits, key=lambda x: x[1])[-5:]
    log(f"· {what}: {len(splits):,}건 / {n_us:,}종목 (~ {today})"
        + (" · 최근: " + " · ".join(f"{t} {d} {split_ratio_text(r)}" for t, d, r in reversed(recent)) if recent else ""))
    nc = info.get("noCol") or []
    if nc:
        log(f"  !! 분할 칸을 읽지 못한 종목 {len(nc):,}개 — 이 종목들은 지난 발행본 · 시드의 줄만 써요 (관문이 경고해요): "
            f"{', '.join(nc[:10])}{'…' if len(nc) > 10 else ''}")
    if info.get("spin"):
        def mark(x):     # 2026-11-14: 같은 날의 진짜 사건이 고정 표에 있으면 그렇다고 (UL 2025-12-09 ×0.888 → 고정 표 8:9 병합)
            t, d = x.split(" ")[:2]
            fx = SPLIT_OVERRIDES.get((t, d))
            return x + (f" (고정 표: {'뺌' if fx[0] is None else split_ratio_text(fx[0])})" if fx else "")
        log(f"  !! 야후가 분할 칸에 적은 깨끗하지 않은 배율 {len(info['spin'])}건은 넣지 않았어요 (분사 조정 — 주식 수가 바뀐 게 아니에요 · "
            f"진짜 사건은 SPLIT_OVERRIDES 로 넣어요): {', '.join(mark(x) for x in info['spin'][:20])}{'…' if len(info['spin']) > 20 else ''}")
    if info.get("future"):
        log(f"  !! 오늘({today}) 뒤 날짜의 분할 {len(info['future'])}건은 넣지 않았어요: {', '.join(info['future'][:10])}")
    if info.get("bad"):
        log(f"  !! 배율이 이상한 분할 {len(info['bad'])}건은 넣지 않았어요 (1 이거나 {SPLIT_R[0]:g}~{SPLIT_R[1]:g} 밖): "
            f"{', '.join(info['bad'][:10])}")


def load_split_seed(path=None, codes_path=None):
    """data/us_splits_seed.csv (code,date,ratio,yahoo · # 줄은 설명) · data/us_splits_seed_codes.txt (2016년부터의 이력을 읽어 둔 종목 · # 줄의
    'end=YYYY-MM-DD' 가 읽은 마지막 날). 한 번 받아 검토해 커밋한 야후 분할이에요 — 첫 실행이 미국 종목 770여 개의 이력을 받지 않게 (#117 리뷰 2).
    고정 표(SPLIT_OVERRIDES)는 여기 넣지 않아요 (한 곳). 모양이 틀린 줄이 있으면 RuntimeError. -> ({(코드, 날짜): 배율}, 종목 집합, end 날짜)"""
    path, codes_path = path or SPLIT_SEED_PATH, codes_path or SPLIT_SEED_CODES_PATH
    rows = {}
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines or lines[0].strip() != "code,date,ratio,yahoo":
        raise RuntimeError(f"{os.path.basename(path)} 머리줄이 code,date,ratio,yahoo 가 아니에요")
    for i, ln in enumerate(lines[1:], 2):
        parts = ln.split(",")
        try:
            t, d, r = parts[0].strip(), dt.date.fromisoformat(parts[1].strip()).isoformat(), float(parts[2])
        except (IndexError, ValueError):
            raise RuntimeError(f"{os.path.basename(path)} {i}번째 줄: {ln[:60]}")
        if len(parts) != 4 or not t or not (SPLIT_R[0] <= r <= SPLIT_R[1]) or r == 1 or not split_is_clean(r) or (t, d) in rows \
                or d < SPLITS_FROM:
            raise RuntimeError(f"{os.path.basename(path)} {i}번째 줄: {ln[:60]}")
        rows[(t, d)] = r
    end, codes = None, set()
    with open(codes_path, encoding="utf-8") as f:
        for ln in f.read().splitlines():
            if ln.startswith("#"):
                m = re.search(r"end=(\d{4}-\d{2}-\d{2})", ln)
                end = dt.date.fromisoformat(m.group(1)) if m else end
            elif ln.strip():
                codes.add(ln.strip())
    if end is None or not codes or not {t for t, _ in rows} <= codes:
        raise RuntimeError(f"{os.path.basename(codes_path)}: end= 줄 · 종목 · 시드의 모든 종목이 있어야 해요")
    return rows, codes, end


def add_more_seeds(seed, pairs=None):
    """처음 시드(load_split_seed 결과 · 못 읽었으면 ({}, set(), None))에 나중에 더한 종목의 시드(SPLIT_SEED_MORE)를 합쳐요. 파일마다
    load_split_seed 규칙 그대로. 같은 (종목, 날짜)가 두 파일에 있으면 그 파일은 쓰지 않아요. end = 가장 이른 end (모든 파일이 그날까지는 덮어요).
    읽지 못한 파일은 크게 남기고 빼요 (그 종목들은 한 실행에 SPLIT_BACKFILL_MAX 개씩 2016년부터 다시 읽어요). -> load_split_seed 와 같은 모양"""
    rows, codes, end = dict(seed[0]), set(seed[1]), seed[2]
    for path, codes_path in (SPLIT_SEED_MORE if pairs is None else pairs):
        try:
            r2, c2, e2 = load_split_seed(path, codes_path)
            both = sorted(set(r2) & set(rows))
            if both:
                raise RuntimeError(f"처음 시드와 같은 줄이 있어요: {', '.join(f'{t} {d}' for t, d in both[:5])}")
        except Exception as e:
            log(f"  !! 더한 종목의 분할 시드({os.path.basename(path)})를 읽지 못했어요 ({type(e).__name__}: {str(e)[:120]}) — 빼고 해요 (그 종목들은 "
                f"2016년부터의 분할을 한 실행에 {SPLIT_BACKFILL_MAX}개씩 다시 읽어요)")
            continue
        rows.update(r2)
        codes |= c2
        end = e2 if end is None else min(end, e2)
    return rows, codes, end


def fetch_split_history(codes, today, download=None, sleep=time.sleep):
    """2016-01-01 ~ 오늘 일봉(actions=True)을 이 종목들만 받아 분할을 읽어요 — 종목마다 요청 한 번. 시드에도 지난 발행본에도 없는 종목만
    (목록에 들고 나는 종목 때문에 하루 몇 개 · 한 실행에 SPLIT_BACKFILL_MAX 개까지). 받지 못한 종목은 쉬었다가 한 번 더 (천천히).
    -> (목록, info) — us_splits 와 같아요."""
    codes = sorted(codes)
    if not codes:
        return [], {"noCol": [], "future": [], "bad": [], "spin": []}
    if download is None:
        import yfinance as yf
        download = yf.download

    def once(cs, threads):
        data = download(cs, start=dt.date.fromisoformat(SPLITS_FROM), end=today + dt.timedelta(days=1), progress=False,
                        auto_adjust=True, group_by="ticker", threads=threads, actions=True)
        return us_splits(data, cs, today)
    out, info = once(codes, True)
    if info["noCol"]:
        again = list(info["noCol"])
        log(f"  !! 2016년부터의 분할 이력을 받지 못한 종목 {len(again):,}개 — {SPLIT_HIST_RETRY_PAUSE}초 뒤 한 번 더 (천천히)")
        sleep(SPLIT_HIST_RETRY_PAUSE)
        o2, i2 = once(again, False)
        out += o2
        info = {k: (i2[k] if k == "noCol" else info[k] + i2[k]) for k in info}
    return sorted(out), info


def splits_prev(prev):
    """지난 발행본(data.json)의 분할: (줄 {(코드, 날짜): 배율}, 2016년부터 읽어 둔 종목, splitsAsOf, 고정 줄 {(코드, 날짜): (배율, 근거)},
    풀리지 않은 diff 줄). 줄은 모양이 맞고 배율 > 0 인 것 모두 (종목이 목록에서 빠졌어도 — 한 번 실은 분할은 빼지 않아요). (순수 함수)"""
    entries, fixed, diff = {}, {}, []
    p = prev if isinstance(prev, dict) else {}
    raw = p.get("splits")
    for x in raw if isinstance(raw, list) else []:
        if not (isinstance(x, list) and len(x) == 3 and isinstance(x[0], str) and isinstance(x[1], str)):
            continue
        r = _fin(x[2])
        try:
            d = dt.date.fromisoformat(x[1])
        except ValueError:
            continue
        if r is not None and r > 0 and d.isoformat() == x[1]:
            entries[(x[0], x[1])] = r
    info = p.get("splitsInfo") if isinstance(p.get("splitsInfo"), dict) else {}
    for x in info.get("fixed") or []:
        if isinstance(x, list) and len(x) == 4 and isinstance(x[0], str) and isinstance(x[1], str) and isinstance(x[3], str):
            r = _fin(x[2]) if x[2] is not None else None
            if x[2] is None or (r is not None and r > 0):
                fixed[(x[0], x[1])] = (r, x[3])
    for x in info.get("diff") or []:
        if isinstance(x, list) and len(x) in (4, 5) and isinstance(x[0], str) and isinstance(x[1], str):
            diff.append(list(x))
    covered = set()
    if p.get("splitsFrom") == SPLITS_FROM and isinstance(raw, list):
        us_prev = {s.get("t") for s in p.get("stocks") or [] if s.get("cls") == "us" and not s.get("fund")}
        covered = us_prev - set(info.get("gap") or [])
    return entries, covered, p.get("splitsAsOf"), fixed, diff


def merge_splits(prev, seed, us_codes, recent, recent_info, recent_from, hist, hist_info, need, today):
    """data.json splits 를 정해요. 한 번 실은 분할은 빼지 않아요 (#117 리뷰: '최근 3년' 창이면 분할이 3년 뒤 목록에서 빠져 분할 전 기록의
    주식 수가 조용히 바뀌고, 2016~2023 분할이 없어요 — 스펙의 빈틈이라 Jack 에게 알려요). (순수 함수)
      · 바탕 = 지난 발행본의 줄 + 시드(seed: 커밋한 2016년부터의 야후 분할). 바탕 줄은 모두 남아요 (종목이 목록에서 빠져도).
      · 새로 읽은 것 = recent (오늘 시세 다운로드 · recent_from 부터 모든 미국 종목) + hist (need 종목의 2016년부터).
        야후가 바탕 줄을 빼거나 배율을 바꾸면 바탕 값을 두고 diff 에 적어요. 같은 종목 · 같은 배율인데 날짜가 SPLIT_SAME_EVENT_DAYS 안에서
        달라졌으면 같은 사건으로 보고 바탕 날짜를 둬요 (diff 의 다섯째 칸 = 야후 날짜). 지난 발행본의 diff 는 고정 표가 정리하거나 야후가 다시
        같은 값을 줄 때까지 이어 적어요 (재사용된 티커 · 날짜가 오늘 다운로드 밖이라도 매일 경고).
      · 고정 표 = SPLIT_OVERRIDES + 지난 발행본에만 있는 고정 줄 (지운 줄은 이어 두고 fixedKept 로 경고 — 배율이 깨끗하지 않은 이어 온 줄이
        관문에서 실패하지 않게). 마지막에 적용 (오늘 목록에 있거나 바탕 줄이 있는 종목만 · None = 빼기).
      · 출처: 아무것도 새로 읽지 못함 = kept (splitsAsOf 는 어제 값) · 읽지 못한 종목이 있음 = part · 모두 읽음 = yahoo.
    seed: (줄, 종목, end) 또는 None. -> {"splits": 목록 또는 None, "src", "asOf", "info": {noCol, gap, diff, fixed, fixedKept}, "new"}"""
    carried, _covered, prev_as_of, prev_fixed, prev_diff = splits_prev(prev)
    seed_rows = (seed or ({}, set(), None))[0]
    us = set(us_codes)
    recent_ok = (us - set((recent_info or {}).get("noCol") or [])) if recent is not None else set()
    hist_ok = (set(need) - set((hist_info or {}).get("noCol") or [])) if hist is not None else set()
    # 시드는 오늘 목록에 있는 종목의 줄만 (#117 리뷰 3: 목록에서 잠깐 빠진 종목의 시드 줄이 '새 줄'로 관문에서 실패했어요 — 그 종목이 다시 들면 그날
    # 나타나요). 한 번 실은 줄(carried)은 종목이 빠져도 그대로 · 같은 종목·날짜면 실은 값이 시드보다 앞서요.
    base = {k: v for k, v in seed_rows.items() if k[0] in us}
    base.update(carried)
    fresh, overlap, conflict = {}, 0, []
    for lst in (hist or [], recent or []):
        for t, d, r in lst:
            k = (t, d)
            if k in fresh:
                if not _same_r(fresh[k], r):
                    conflict.append(f"{t} {d} ×{fresh[k]:g}/×{r:g}")
                else:
                    overlap += 1
            fresh[k] = r                     # 오늘 시세 다운로드(recent)가 마지막
    table = {k: v for k, v in prev_fixed.items() if k not in SPLIT_OVERRIDES}
    fixed_kept = sorted([t, d] for t, d in table)
    table.update(SPLIT_OVERRIDES)
    out, diff, moved_seen, both = dict(base), [], set(), []
    by_t = {}
    for (t, d), r in base.items():
        if (t, d) in table and table[(t, d)][0] is None:
            continue                         # 고정 표가 빼는 줄은 '같은 사건' 찾기에 쓰지 않아요 (날짜를 고치는 'out + 새 줄'이 하루 숨지 않게)
        by_t.setdefault(t, []).append((d, r))
    for (t, d), r in sorted(fresh.items()):
        if (t, d) in table:
            continue
        if (t, d) in base:
            if not _same_r(base[(t, d)], r):
                diff.append([t, d, base[(t, d)], r])
            continue
        near = [(bd, br) for bd, br in by_t.get(t, []) if _same_r(br, r)
                and abs((dt.date.fromisoformat(bd) - dt.date.fromisoformat(d)).days) <= SPLIT_SAME_EVENT_DAYS]
        if near:
            bd, br = near[0]
            moved_seen.add((t, bd))
            diff.append([t, bd, br, r, d])              # 야후가 날짜를 옮겼거나(실은 날짜만 둬요) 같은 배율을 두 날짜에 적었어요 (둘째는 넣지 않아요)
            if (t, bd) in fresh:
                both.append(f"{t} {bd} · {d} ×{r:g}")
            continue
        out[(t, d)] = r
    for (t, d), r in sorted(base.items()):
        seen = t in hist_ok or (t in recent_ok and d >= recent_from.isoformat())
        if seen and (t, d) not in fresh and (t, d) not in table and (t, d) not in moved_seen:
            diff.append([t, d, r, None])
    have = {(x[0], x[1]) for x in diff}
    for x in prev_diff:                     # 풀리지 않은 지난 diff 를 이어 적어요
        k = (x[0], x[1])
        if k in have or k in table or k not in out or (k in fresh and _same_r(fresh[k], out[k])):
            continue
        diff.append(x)
        have.add(k)
    fixed = []
    for (t, d), (r, note) in sorted(table.items()):
        fixed.append([t, d, r, note])
        if r is None:
            out.pop((t, d), None)
        elif t in us or any(k[0] == t for k in base):
            out[(t, d)] = r
    read = recent_ok | hist_ok
    gap = [c for c in need if c not in hist_ok]            # 순서 그대로 (splits_fields: 이번에 묻지 않은 종목 먼저, 실패한 종목 뒤)
    unread = sorted(us - read)
    if not read:
        src, as_of = "kept", prev_as_of
    elif gap or unread:
        src, as_of = "part", today.isoformat()
    else:
        src, as_of = "yahoo", today.isoformat()
    new = sorted([t, d, r] for (t, d), r in out.items() if (t, d) not in carried)
    splits = sorted([t, d, r] for (t, d), r in out.items()) if (out or read) else None
    log(f"{'· ' if src == 'yahoo' else '  !! '}주식 분할(splits) {SPLITS_FROM} ~: {len(out):,}건 · 어제에서 이어 옴 {len(carried):,} · 시드 "
        f"{len(seed_rows):,} · 새로 {len(new):,} · 오늘 읽은 종목 {len(read):,} / {len(us):,} · 출처 {src} (마지막으로 새로 읽은 날 {as_of})"
        + (f" · 2016년부터 아직 못 읽은 종목 {len(gap):,}: {', '.join(gap[:10])}" if gap else "")
        + (f" · 오늘 분할 칸이 없는 종목 {len(unread):,}: {', '.join(unread[:10])}" if unread else "")
        + (f" · 두 다운로드가 겹친 줄 {overlap:,}" if overlap else ""))
    if conflict:
        log(f"  !! 같은 종목·날짜인데 두 다운로드의 배율이 달라요 {len(conflict)}건 (오늘 시세 다운로드 값으로): {', '.join(conflict[:10])}")
    if diff:
        log(f"  !! 야후와 다른 분할 {len(diff)}건 — 실은 값을 그대로 둬요 (관문이 경고해요 · 사람이 확인해 고정 표로 정리): "
            + ", ".join(f"{x[0]} {x[1]} ×{x[2]:g}→" + ("없음" if x[3] is None else f"×{x[3]:g}") + (f" ({x[4]})" if len(x) == 5 else "")
                        for x in diff[:10]))
    if both:
        log(f"  !! 야후가 같은 배율의 분할을 {SPLIT_SAME_EVENT_DAYS}일 안의 두 날짜에 적었어요 {len(both)}건 — 둘째는 넣지 않고 diff 에 적어요 "
            f"(진짜 두 번이면 고정 표에 넣어요): {', '.join(both)}")
    if fixed_kept:
        log(f"  !! 고정 표에서 지운 줄 {len(fixed_kept)}개를 지난 발행본에서 이어 둬요 (빼려면 배율을 None 으로): "
            + ", ".join(f"{t} {d}" for t, d in fixed_kept))
    if new and carried:
        log(f"· 새로 실은 분할 {len(new)}건: " + ", ".join(f"{t} {d} {split_ratio_text(r)}" for t, d, r in new[:15]))
    return {"splits": splits, "src": src, "asOf": as_of, "new": new,
            "info": {"noCol": len(unread), "gap": gap, "diff": diff, "fixed": fixed, "fixedKept": fixed_kept}}


def splits_fields(prev, us_codes, recent, recent_no_col, recent_from, today, seed=None, history=None):
    """main 의 주식 분할 부분: data.json 에 더할 칸 {"splits", "splitsFrom", "splitsAsOf", "splitsSrc", "splitsInfo"} (없으면 {}).
    2016년부터의 이력은 시드(커밋한 파일)와 지난 발행본으로 덮고, 둘 다 없는 종목만 SPLIT_BACKFILL_MAX 개까지 읽어요 (나머지 · 실패는 gap).
    지난 발행본에 목록이 없는 날(첫 발행) 꼭 있어야 할 분할(MUST_SPLITS)이 빠지면 그날은 칸을 쓰지 않아요 (관문 경고 '없음' · 발행은 막지 않아요).
    seed: load_split_seed() 결과 (None = 읽어요 · 못 읽으면 크게 남기고 없이) · history: fetch_split_history 대신 (시험용)."""
    if seed is None:
        try:
            seed = load_split_seed()
        except Exception as e:
            seed = ({}, set(), None)
            log(f"  !! 분할 시드(data/us_splits_seed.csv)를 읽지 못했어요 ({type(e).__name__}: {str(e)[:120]}) — 시드 없이 해요")
        seed = add_more_seeds(seed)          # 2026-11-14: 나중에 더한 종목의 시드 (data/us_splits_seed_more.csv)
    _c, covered, _a, _f, _d = splits_prev(prev)
    seed_rows, seed_codes, seed_end = seed
    if seed_end is not None and seed_end >= recent_from - dt.timedelta(days=1):
        covered = covered | seed_codes      # 시드가 오늘 다운로드의 첫날까지 덮을 때만
    # 읽을 차례: 새로 목록에 든 종목 먼저, 어제 gap 은 그 순서대로 뒤에 (계속 실패하는 종목이 다른 종목을 막지 않게 · #117 리뷰 3 N1)
    want = set(us_codes) - covered
    prev_gap = [c for c in (((prev or {}).get("splitsInfo") or {}).get("gap") or []) if c in want] if isinstance(prev, dict) else []
    need_all = sorted(want - set(prev_gap)) + prev_gap
    need = need_all[:SPLIT_BACKFILL_MAX]
    hist, hinfo = [], {"noCol": []}
    if need:
        log(f"· 주식 분할: {SPLITS_FROM} 부터의 이력이 없는 종목 {len(need_all):,}개 중 {len(need):,}개를 읽어요 (야후 요청 {len(need):,}번 · 다시 받기 "
            f"포함 많아야 {2 * len(need):,}번): {', '.join(need[:10])}" + ("…" if len(need) > 10 else "")
            + (f" — 나머지 {len(need_all) - len(need):,}개는 다음 실행에서 (splitsInfo.gap)" if len(need_all) > len(need) else ""))
        try:
            hist, hinfo = (history or fetch_split_history)(need, today)
            log_us_splits(hist, hinfo, len(need), today, what=f"미국 주식 분할 ({SPLITS_FROM} 부터 · 새로 읽은 종목)")
        except Exception as e:
            hist, hinfo = None, {"noCol": list(need)}
            log(f"  !! 주식 분할: {SPLITS_FROM} 부터의 이력을 받다 멈췄어요 ({type(e).__name__}: {str(e)[:120]}) → 그 종목들은 다음 실행에서 다시 "
                "읽어요 (splitsInfo.gap · 관문이 경고해요)")
    if hist is not None:                    # 이번에 묻지 않은 종목(상한 밖)은 읽지 않은 것 → gap (다음 실행)
        hinfo = dict(hinfo, noCol=list(hinfo.get("noCol") or []) + need_all[len(need):])
    order = need_all[len(need):] + need     # gap 순서: 이번에 묻지 않은 종목 먼저, 이번에 실패한 종목 뒤
    sp = merge_splits(prev, seed, us_codes, recent, {"noCol": list(recent_no_col or [])}, recent_from, hist, hinfo, order, today)
    had = isinstance((prev or {}).get("splits"), list)
    if not had and sp["src"] == "kept":
        log("  !! 주식 분할: 첫 발행인데 오늘 야후에서 분할을 하나도 읽지 못해 splits 를 쓰지 않아요 (관문 경고 '없음' · 발행은 막지 않아요)")
        return {}
    if sp["splits"] is None:
        return {}
    have = {(x[0], x[1]): x[2] for x in sp["splits"]}
    miss = [f"{t} {d}" for t, d, r in MUST_SPLITS if not _same_r(have.get((t, d)), r)]
    if miss and not had:
        log(f"  !! 주식 분할: 꼭 있어야 할 분할이 빠져 오늘은 splits 를 쓰지 않아요 (첫 발행 · 관문 경고 '없음' · 발행은 막지 않아요): {', '.join(miss)}")
        return {}
    return {"splits": sp["splits"], "splitsFrom": SPLITS_FROM, "splitsAsOf": sp["asOf"], "splitsSrc": sp["src"], "splitsInfo": sp["info"]}


# ────────────────────────────────────────────────────────────
# v19.6a: macro.json fxHist — 원/달러 일별 환율 2016-01-01 ~ (Part I.1)
# ────────────────────────────────────────────────────────────
def fx_hist_rows(ser):
    """pd.Series → ([[날짜, 소수 첫째 자리 값], …], 버린 줄 수, 겹친 날짜 수). NaN·무한·0 이하는 버리고 세요 (bad). 같은 날짜가 두 번이면 뒤의
    것을 쓰고 세요 (dup — fx_last 와 같은 쪽). 날짜 순서로. 출처마다 bad 가 하나라도 있으면 그 이력을 쓰지 않아요 (빈 날을 만들지 않게). (순수 함수)"""
    by, bad, dup = {}, 0, 0
    for ts, v in ser.items():
        x = _fin(v)
        if x is None or x <= 0:
            bad += 1
            continue
        d = pd.Timestamp(ts).date().isoformat()
        if d in by:
            dup += 1
        by[d] = round(x, 1)
    return [[d, by[d]] for d in sorted(by)], bad, dup


def fx_hist_problems(rows, src):
    """fxHist 줄이 앱이 믿고 쓸 수 있는 모양인지 (관문과 같은 기준 · 코드는 따로). -> 문제 목록 (빈 목록 = 괜찮음). (순수 함수)"""
    if not rows:
        return ["줄이 없어요"]
    probs = []
    if rows[0][0] > FX_HIST_FIRST_BY or rows[0][0] < FX_HIST_FROM:
        probs.append(f"첫날 {rows[0][0]} ({FX_HIST_FROM} ~ {FX_HIST_FIRST_BY} 이어야 해요 — 앞이 잘린 이력)")
    out = [f"{d} {v:g}" for d, v in rows if not (FX_LO < v < FX_HI)]
    if out:
        probs.append(f"범위({FX_LO}~{FX_HI}) 밖 {len(out)}줄: {', '.join(out[:3])}")
    gap_max = FX_HIST_GAP_MAX[src]
    for (d0, v0), (d1, v1) in zip(rows, rows[1:]):
        gap = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days
        if gap <= 0:
            probs.append(f"날짜 순서 {d0} → {d1}")
        elif gap > gap_max:
            probs.append(f"{d0} → {d1} {gap}일 비어요 (≤ {gap_max}일)")
        if v0 > 0 and abs(v1 / v0 - 1) * 100 > FX_HIST_JUMP:
            probs.append(f"{d0} → {d1} {v0:g} → {v1:g} (하루 {FX_HIST_JUMP:g}% 넘게)")
    return probs


def _last_near_fx(rows, fx_last):
    v = rows[-1][1] if rows else None
    return [] if v and fx_last and abs(v / fx_last - 1) <= FX_HIST_REL else [
        f"마지막 값 {v} 이 이 실행의 환율 {fx_last:,.1f} 과 {FX_HIST_REL:.0%} 넘게 달라요"]


def ecos_fx_series(start, end, get=None, item=None):
    """ECOS 일별 환율 한 시계열 (ECOS_FX_ITEMS 의 (통계표, 항목)) — 요청 한 번 (2016년부터 약 2,700 줄, 한 쪽에 10,000 줄까지). 값이 숫자가 아닌
    날은 NaN (fx_hist_rows 가 세요). 받은 줄 수가 ECOS 가 말한 전체 수와 다르면 실패. 키가 든 주소는 어디에도 남기지 않아요."""
    stat, it = item or ECOS_FX_ITEMS["mbr"]
    j = (get or ecos_get)(f"{ECOS_BASE}/StatisticSearch/{ECOS_KEY}/json/kr/1/10000/{stat}/D/{start:%Y%m%d}/{end:%Y%m%d}/{it}")
    if "RESULT" in j:
        raise RuntimeError(f"ECOS 환율 {stat}/{it}: {str(j['RESULT'])[:120]}")
    blk = j.get("StatisticSearch") or {}
    rows = blk.get("row") or []
    n = int(_fin(blk.get("list_total_count")) or 0)
    if not rows or n != len(rows):
        raise RuntimeError(f"ECOS 환율 {stat}/{it}: 받은 줄 {len(rows):,} · 전체 {n:,}")
    return pd.Series([_fin(x.get("DATA_VALUE")) for x in rows],
                     index=pd.to_datetime([x["TIME"] for x in rows], format="%Y%m%d"), dtype="float64")


def fx_hist_ecos(ser, fx_last, today, src="ecos"):
    """ECOS 시계열 → fxHist (끝난 값이라 final 참). 오늘(KST)까지. (순수 함수)
      ecos       : 줄 D = D 에 고시된 매매기준율 (전 영업일 서울 거래의 평균 — 미국 D 의 끝보다 하루 반쯤 늦어요)
      ecos_next  : 줄 D = D 다음에 고시된 매매기준율 (= D 하루 서울 거래의 평균). 마지막 고시일에는 아직 줄이 없어요 (asOf = 그 전 영업일).
                   한국 휴일 H 는 그 전 영업일의 줄(= H 다음 첫 고시)을 써요 — 앱의 '그날 또는 그 전 마지막 줄'과 같아요
      ecos_close : 줄 D = 서울 외환시장 D 의 15:30 종가 (731Y003 · 0000003)"""
    rows, bad, dup = fx_hist_rows(cut_at(ser, today))
    if bad:
        return None, f"값이 숫자가 아닌 날 {bad}줄"
    if src == "ecos_next":
        rows = [[a[0], b[1]] for a, b in zip(rows, rows[1:])]
    probs = fx_hist_problems(rows, src) + _last_near_fx(rows, fx_last)
    if probs:
        return None, " · ".join(probs[:3]) + (f" 외 {len(probs) - 3}개" if len(probs) > 3 else "")
    stat, it = ECOS_FX_ITEMS["close" if src == "ecos_close" else "mbr"]
    return {"asOf": rows[-1][0], "final": True, "rows": rows}, f"ECOS {stat}/{it}" + (f" · 겹친 날짜 {dup}" if dup else "")


def _yf_field(data, field):
    v = data[field]
    return (v.iloc[:, 0] if isinstance(v, pd.DataFrame) else v).dropna()


def london_midnight_after(d):
    """날짜 d(런던)의 다음 자정 — UTC 시각. 야후 USDKRW=X 일봉 d 가 끝나는 때 (한국 시간 다음 날 08:00 여름 · 09:00 겨울)."""
    return dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0), LONDON).astimezone(dt.timezone.utc)


def fx_hist_yahoo_next(raw, fx, fx_last, now):
    """야후 2016년부터 받은 일봉(raw: 시가·종가) → fxHist. 줄 D = D 다음 봉의 시가 (런던 자정, D 가 끝난 값). (순수 함수)
    마지막 줄(이 실행의 환율 날짜 fxDate): 다음 봉이 있고 지금이 런던 자정을 지났으면 그 시가 (final 참), 아니면 이 실행의 환율 fx_last
    (data.json fx · 아직 끝나지 않은 값 · final 거짓 — 다음 실행이 다시 써요). 2016년부터 받은 종가가 이 실행의 환율(fx)과 겹치는 날 같아야 해요."""
    close, opn = _yf_field(raw, "Close"), _yf_field(raw, "Open")
    fxd = fx.index[-1].date().isoformat()
    c_rows, _, _ = fx_hist_rows(cut_at(close, fx.index[-1]))
    rec = dict(map(tuple, fx_hist_rows(fx)[0]))
    common = [(d, v) for d, v in c_rows[:max(0, len(c_rows) - FX_HIST_AGREE_SKIP)] if d in rec]
    if len(common) < FX_HIST_AGREE_MIN:
        return None, f"이 실행의 환율과 겹치는 날이 {len(common)}일뿐이에요 (≥ {FX_HIST_AGREE_MIN}일)"
    worst = max(abs(v / rec[d] - 1) for d, v in common)
    if worst > FX_HIST_AGREE:
        return None, f"이 실행의 환율과 겹치는 날 값이 달라요 (최대 {worst:.2%} · ≤ {FX_HIST_AGREE:.1%})"
    o_rows, bad, dup = fx_hist_rows(opn)
    if bad:
        return None, f"시가가 깨진 줄 {bad}개"
    bars = [d for d, _ in o_rows]
    if fxd not in bars:
        return None, f"환율 날짜 {fxd} 의 봉이 없어요"
    i_last = bars.index(fxd)
    rows = [[bars[i], o_rows[i + 1][1]] for i in range(i_last) if bars[i] >= FX_HIST_FROM]
    final = i_last + 1 < len(bars) and now >= london_midnight_after(dt.date.fromisoformat(fxd))
    rows.append([fxd, o_rows[i_last + 1][1] if final else round(fx_last, 1)])
    probs = fx_hist_problems(rows, "yahoo_next") + _last_near_fx(rows, fx_last)
    if probs:
        return None, " · ".join(probs[:3]) + (f" 외 {len(probs) - 3}개" if len(probs) > 3 else "")
    return ({"asOf": fxd, "final": final, "rows": rows},
            f"야후 {FX_TICKER} 다음 봉 시가 · 겹치는 {len(common):,}일 종가 최대 차이 {worst:.3%}" + (f" · 겹친 날짜 {dup}" if dup else ""))


def _rows_series(rows):
    """[[날짜, 값], …] → pd.Series (모양이 틀린 줄은 NaN — fx_hist_rows 가 세요)."""
    idx, vals = [], []
    for r in rows if isinstance(rows, list) else []:
        try:
            idx.append(pd.Timestamp(dt.date.fromisoformat(str(r[0]))))
        except (TypeError, ValueError, IndexError, KeyError):
            idx.append(pd.Timestamp("1900-01-01"))
        vals.append(r[1] if isinstance(r, list) and len(r) == 2 and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)
                    else float("nan"))
    return pd.Series(vals, index=pd.DatetimeIndex(idx), dtype=float)


def kept_fx_hist(prev_macro, source, fx, fx_last, today):
    """지난 발행본(macro.json)의 fxHist 를 그대로 둘 수 있는지: 같은 출처 · fxHistFresh 가 날짜 · 줄이 지금 기준을 다 통과 · 마지막 값이 이
    실행의 환율과 FX_HIST_REL 안 (야후는 마지막 날 ≤ 이 실행의 환율 날짜). 며칠이 지나도 둬요 (#117 리뷰 2, N4): 줄은 asOf 와 그 전 날짜에
    대해 여전히 맞는 값이고 앱은 asOf 뒤 날짜를 받지 않으니, 빼면 2019년 기록까지 막힐 뿐 틀린 숫자를 막지 않아요 — 관문이 날마다 경고해요.
    단 하나, 마지막 값이 이 실행의 환율과 FX_HIST_REL(10%) 넘게 달라지면 버려요 (관문이 그 이력을 실패로 막을 것이라서) — ECOS 가 오래 멈춘 동안
    환율이 10% 넘게 움직였을 때뿐이에요 (그때는 지난 날짜의 미국 기록을 하루 이틀 받지 못해요).
    -> (fxHist, fxHistFresh) 또는 (None, 이유). 이어 써도 fxHistFresh 는 그대로예요. (순수 함수)"""
    pm = prev_macro if isinstance(prev_macro, dict) else {}
    ph, psrc = pm.get("fxHist"), pm.get("fxHistSrc")
    if not isinstance(ph, dict) or not ph.get("rows"):
        return None, "지난 발행본에 fxHist 없음"
    if psrc != source:
        return None, f"지난 발행본의 출처 {psrc!r} ≠ {source} (출처를 섞지 않아요)"
    try:
        fresh = dt.date.fromisoformat(str(pm.get("fxHistFresh")))
    except ValueError:
        return None, f"지난 발행본의 fxHistFresh {pm.get('fxHistFresh')!r}"
    if fresh > today:
        return None, f"지난 발행본의 fxHistFresh {fresh} 가 오늘 뒤예요"
    rows, bad, dup = fx_hist_rows(_rows_series(ph["rows"]))
    probs = (["모양이 틀린 줄 %d개" % (bad + dup)] if bad or dup else []) + fx_hist_problems(rows, source) + _last_near_fx(rows, fx_last)
    if ph.get("asOf") != (rows[-1][0] if rows else None) or not isinstance(ph.get("final"), bool):
        probs.append("asOf · final 모양")
    if source == "yahoo_next" and rows and rows[-1][0] > fx.index[-1].date().isoformat():
        probs.append("마지막 날이 이 실행의 환율 날짜 뒤")
    if probs:
        return None, "지난 발행본: " + " · ".join(probs[:3])
    return {"asOf": ph["asOf"], "final": ph["final"], "rows": rows}, fresh.isoformat()


def fetch_fx_hist(fx, fx_last, today, prev_macro, source=None, now=None, download=None, ecos=None, sleep=time.sleep):
    """v19.6a Part I.1: macro.json fxHist ({asOf, final, rows: [[날짜, 환율], …]}) 를 FX_HIST_SOURCE 출처로. 순서대로 (출처를 크게 남겨요):
      1. 출처에서 새로 읽기 — ecos · ecos_next: ECOS 매매기준율 · ecos_close: ECOS 15:30 종가 (요청 한 번, ecos_get 이 세 번까지) ·
         yahoo_next: 야후 USDKRW=X 2016년부터 (요청 한 번 · 실패하면 FX_HIST_PAUSE 초 쉬고 한 번 더)
      2. 지난 발행본의 fxHist 그대로 (kept_fx_hist: 같은 출처 — 며칠이 지나도)
      3. 없음: 싣지 않아요 (앱은 지난 날짜의 미국 종목 기록을 받지 않고 승인된 줄로 알려요 · 관문 경고). 만들어 내지 않아요.
    약속: 줄은 asOf 와 그 전 날짜에만 말해요 — 앱은 asOf 뒤 날짜를 받지 않아요 (오늘만 신선한 data.json fx). 한 이력 안에서 출처를 섞지 않아요.
    ecos: (시작, 끝, (통계표, 항목)) → 시계열 (시험용). -> (fxHist 또는 None, 출처 또는 None, fxHistFresh 'YYYY-MM-DD' 또는 None)"""
    source = source or FX_HIST_SOURCE
    if source not in FX_HIST_SOURCES:
        raise ValueError(f"FX_HIST_SOURCE {source!r} 는 {FX_HIST_SOURCES} 중 하나여야 해요")
    now = now or dt.datetime.now(dt.timezone.utc)
    hist, how = None, "?"
    if source in FX_HIST_ECOS:
        if not ECOS_KEY and ecos is None:
            how = "ECOS_API_KEY 없음"
        else:
            item = ECOS_FX_ITEMS["close" if source == "ecos_close" else "mbr"]
            try:
                ser = (ecos or (lambda a, b, it: ecos_fx_series(a, b, item=it)))(dt.date.fromisoformat(FX_HIST_FROM), today, item)
                hist, how = fx_hist_ecos(ser, fx_last, today, source)
            except Exception as e:
                how = f"{type(e).__name__}: {str(e)[:120]}"
    else:
        if download is None:
            import yfinance as yf
            download = yf.download
        raw = None
        for i in range(FX_HIST_TRIES):
            try:
                got = download(FX_TICKER, start=dt.date.fromisoformat(FX_HIST_FROM), end=today + dt.timedelta(days=1),
                               progress=False, auto_adjust=True)
                if len(_yf_field(got, "Close")):
                    raw = got
                    break
                how = "빈 응답"
            except Exception as e:
                how = f"{type(e).__name__}: {str(e)[:120]}"
            if i + 1 < FX_HIST_TRIES:
                log(f"  !! 환율 이력: 야후 {FX_TICKER} {FX_HIST_FROM}부터 받기 실패 ({how}) — {FX_HIST_PAUSE}초 뒤 다시")
                sleep(FX_HIST_PAUSE)
        if raw is not None:
            hist, how = fx_hist_yahoo_next(raw, fx, fx_last, now)
    if hist:
        log(f"· 환율 이력(fxHist, {source}): {hist['rows'][0][0]} ~ {hist['asOf']} · {len(hist['rows']):,}일 · {how} · 마지막 "
            f"{hist['rows'][-1][1]:,.1f}{'' if hist['final'] else ' (아직 끝나지 않은 값 · final 거짓)'} · data.json fx {fx_last:,.1f} · "
            f"약 {len(json.dumps(hist, separators=(',', ':'))) / 1024:.0f}KB")
        return hist, source, today.isoformat()
    kept, why = kept_fx_hist(prev_macro, source, fx, fx_last, today)
    if kept:
        log(f"  !! 환율 이력(fxHist, {source}): 새로 읽지 못했어요 ({how}) → 지난 발행본의 이력을 그대로 둬요 (기준 {kept['asOf']} · "
            f"마지막으로 새로 읽은 날 {why} · 관문이 경고해요 · 앱은 {kept['asOf']} 뒤 날짜를 받지 않아요)")
        return kept, source, why
    log(f"  !! 환율 이력(fxHist, {source})을 만들지 못했어요: {how} · {why} → macro.json 에 싣지 않아요 "
        "(앱은 지난 날짜의 미국 종목 기록을 받지 않고 그렇게 알려요 · 관문이 경고해요)")
    return None, None, None


def fx_hist_fields(fx, fx_last, today, prev_macro, **kw):
    """main 의 환율 이력 부분: macro.json 에 더할 칸 {"fxHist", "fxHistSrc", "fxHistFresh"} (못 만들면 {} · 크게 남겨요)."""
    try:
        hist, src, fresh = fetch_fx_hist(fx, fx_last, today, prev_macro, **kw)
    except Exception as e:
        log(f"  !! 환율 이력(fxHist)을 만들다 멈췄어요 ({type(e).__name__}: {str(e)[:120]}) → macro.json 에 싣지 않아요 (관문이 경고해요)")
        return {}
    return {"fxHist": hist, "fxHistSrc": src, "fxHistFresh": fresh} if hist is not None else {}


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
    # 2026-11-19 (Jack · 리뷰 S2): 마지막 확인 종가(pxd)로 실은 국내 종목의 거래대금은 그날 것이라 오늘의 거래대금 순위에 넣지 않아요 (미국은 예전 그대로)
    return top([x for x in kr if x.get("pxd") is None], n_kr) + top(us, n_us)


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
         "d1": ("% (전 거래일 공식 종가 대비 · 미국은 자기 기준일, 야후 수정 종가라 배당락일엔 배당 포함 · 한국 ±30% 넘거나 직전 거래일 파일이 없으면 빈 칸 · "
                "한국 기준일에 거래가 없던 종목도 빈 칸 (noTrade) · 한국의 빈 칸은 이유가 d1Why)"),
         "noTrade": ("true = 한국 · 기준일(pxDate) 목록 파일의 행이 거래량 0 · 시가 0 · 거래대금 0 (거래정지이거나 코넥스의 거래 없는 날 · 목록 파일에 "
                     "거래정지 표시는 없어요) · d1 은 빈 칸이고 d1Why noTrade · 거래가 있던 종목에는 칸이 없어요"),
         "d1Why": ("한국 · d1 이 빈 까닭 (d1 이 있으면 칸 없음): noTrade 기준일에 거래가 없음 · range 전 거래일 대비 ±30% 밖 (신규 상장 · 분할 · 재개) · "
                   "new 직전 거래일 목록 파일에 그 종목의 공식 종가가 없음 · prev 직전 거래일 파일이 없거나 최종본이 아니거나 KOSPI 의 직전 거래일이 아님 "
                   "(그날 모든 종목 — 2026-11-21 부터 그런 날은 KRX 기준가가 지난 발행본 종가와 원 단위까지 같은 종목만 d1 이 있고, 나머지가 prev · d1Base)"),
         "d1Base": ("한국 · 직전 거래일 목록 파일이 없거나 최종본이 아닌 날에만 (2026-11-21): d1 = 오늘 공식 종가 ÷ 지난 발행본의 그날 종가 − 1, 오늘 목록 "
                    "파일의 KRX 기준가(Close − Changes)가 그 종가와 원 단위까지 같은 종목만 · day 직전 거래일 · pub 지난 발행본 pxDate · why 지난 발행본을 "
                    "쓸 수 없던 까닭 (none 없음 · day pxDate 가 직전 거래일이 아님 · src 가격 출처가 공식 종가 목록이 아님 · 그러면 모두 빈 칸) · n 처리한 "
                    "종목 (발행 종목보다 많을 수 있어요) · ok 확인 · diff 기준가가 다름 · noPub 지난 발행본에 없음 · notConf 지난 발행본 값이 그날 확인된 "
                    "종가가 아님 (거래 없음 · pxd) · noBase 오늘 파일에 기준가 없음 · ex 까닭마다 예. same 1 (#161 리뷰 M2): 지난 발행본이 같은 기준일 "
                    "(그날 앞선 발행) 이라 그 발행본의 d1 을 오늘 공식 종가가 그 가격과 원 단위까지 같은 종목만 그대로 쓴 날 — from 그 발행본의 "
                    "publishedAt · diff 가격이 다름 · noD1 앞선 발행본도 d1 빈 칸 · krx 앞선 발행본의 d1 이 오늘 파일의 KRX 기준가 (Close − Changes) 로 본 "
                    "등락률과 0.01 넘게 다름 (빈 칸) · noBase 0"),
         "ntD1": ("% · noTrade 종목의 기준가(공식 종가) 변화 (d1 을 계산했다면 나왔을 값 · ±30% 밖이거나 직전 파일이 없으면 칸 없음) — 거래가 없어 "
                  "등락률로 보이지 않고, 포트폴리오 평가 금액의 오늘 변화에만 써요 (코넥스는 거래 없이 값이 바뀔 수 있어요)"),
         "d1Blank": ("발행하는 한국 종목(목록 파일에서 온 cls kr)의 빈 d1 이유별 수 {noTrade · range · new · prev} (종목의 d1Why 와 같아요) · "
                     "seen false = 거래 없는 종목을 가리지 않음, unseen 까닭: cols 목록 파일에 거래량 · 시가 칸이 없음 · blank 그 칸이 대부분 빈 값 · many 거래 없는 행이 "
                     "10% 를 넘음 · odd 거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 행 · must 거래가 없다고 나온 관문의 필수 종목 (둘 다 표시하지 않음)"),
         "dps": "원 (한국 · 0 = 배당 없음, 빈 칸 = 모름)",
         "fy": "op·debt·roe·opm·g3·dps·dps3 가 나온 사업보고서 연도 (bq 는 TTM 분기)",
         "dps3a": "원 (한국 · dps3 를 오늘 상장 주식 수 기준으로 맞춘 값 [당기, 전기, 전전기] · 빈 칸 = 그해 기준을 확인하지 못함)",
         "dpsF": "배율 (오늘 주식 수 ÷ 그해 배당금의 기준 주식 수 · 1 = 그대로 · dps3a = dps3 ÷ dpsF · 배당 없는 해는 빈 칸)",
         "divSt": "same 그대로 · adj 분할·무상증자를 맞춤 · nc 비교 불가(어중간한 주식 수 변화) · nd 알 수 없음 · zero 3년 배당 없음",
         "dyt": "% (한국 · 오늘 종가 기준 배당수익률 = dps3a[0] ÷ price · 확인 못 한 종목은 빈 칸 · dz 는 이 값의 시장 내 백분위)",
         "betaSE": "베타의 표준오차 (일별 수익률 회귀) · betaN 은 쓴 일별 수익률 수",
         "dvWhy": ("한국 · 주식 수가 바뀌어 배당을 다시 계산하려 한 종목의 결론 (DART 결정 공시) · st ok = 다시 계산, 사건 ev [k split 액면분할 · "
                   "merge 주식병합 · bonus 무상증자 · reduce 주식병합으로 한 감자, d 법적 날짜(효력발생일 · 신주배정기준일 · 감자기준일), "
                   "r 그 사건의 주식 수 배율, x 1주당 신주 수(무상증자), "
                   "rc 공시 접수번호, 오래된 것부터] · nf = 다시 계산, 공시를 찾지 못함 (a 그해 말 발행 주식 수 → b 오늘 상장 주식 수) · "
                   "filed = 유상증자·전환사채·신주인수권부사채(fx [k rights · cb · bw, d 공시일, n 주식 수, rc])가 a → b 를 설명해 공시된 배당 "
                   "그대로 · nc-mismatch = 공시가 배율과 달라, nc-unexplained = 공시로 설명하지 못해 다시 계산하지 않고 배당수익률도 숨김 · "
                   "조회하지 못했으면 칸이 없어요 (divCheck.why.failT)"),
         "unitChk": ("한국 · 공시 단위 확인에 걸린 회사의 이유 목록 (bs = 읽은 재무제표의 자산 ≠ 부채 + 자본 · scale = 분기 보고서의 재무상태표가 "
                     "사업보고서 것의 100배 이상이거나 1/100 이하 · is · cf = 분기 보고서의 지난해 칸이 지난해 같은 분기 보고서의 손익 · 현금흐름과 "
                     "100배 넘게 다름 · eps = 순이익 ÷ 주식 수가 재무제표의 기본주당이익과 300배 넘게 다름 · cap = 자본금 ÷ 액면가가 주식 수와 "
                     "300배 넘게 다름 · eps · cap 은 원화 재무제표만 — 단위를 잘못 적은 보고서) · 이 회사는 per·pbr·eps·bps·roe·debt·opm·g3 와 "
                     "가치·퀄리티 점수가 빈 칸이고, corp.json 도 같은 칸과 3년 실적·자본·EV 배수·영수증·재무 경고가 빈 칸 (배당은 그대로) · "
                     "칸이 없으면 확인을 통과했거나 재무제표가 없어요"),
         "unitChkCover": ("공시 단위 확인이 본 한국 회사 수: companies · checked 모든 재무제표에서 자산 = 부채 + 자본 · unchecked 자산총계 없이 "
                          "저장된 재무제표가 있음 · noScale 분기 보고서가 없음 · eps · cap · anchor 기준값으로 봄 · flows 지난해 칸으로 봄 · notWon 원화가 "
                          "아닌 재무제표라 기준값을 보지 않음 · parLow 액면가가 100원 미만이라 자본금 ÷ 액면가를 보지 않음 · hit 걸린 곳 "
                          "(data.json unitChk 종목 수와 같아요)"),
         "pxSrc": ("한국 공식 종가의 출처 (2026-11-19 · Jack 규칙 3: 늘 두 출처): px listing = 캐시(fdr_krx_data_cache)의 최종본 목록 파일 · "
                   "daum+yahoo = 그날 최종본이 없어 다음 일별 시세 × 야후 .KS/.KQ 종가가 원 단위까지 같은 종목만 (한 출처뿐이거나 다르면 빠져요) · "
                   "date 그 날짜 (= pxDate) · days d1 · val20 에 쓴 앞 거래일 중 2차 출처 날 · fb {n 목록 종목 · conf 두 출처로 확인된 종목 "
                   "(그날 파일에 넣은 코넥스 knx.kept 포함 · 그날 파일의 행 수) · mkt 다음 × 야후 짝이 없는 시장 (코넥스 등) · noDaum · bad · noYahoo · "
                   "diff 두 종가가 다름 · diffEx 예 · must 확인 못 한 필수 종목 · cut 시간 한도 · knx 코넥스 (2026-11-20 · 야후 .KQ × 네이버 일봉 종가가 원 "
                   "단위까지 같은 종목만) {n 목록의 코넥스 · conf 확인 · kept 그날 파일에 넣은 수 (평소 날처럼 1차 출처 최종본 MAX_KR 번째 시가총액 이상만) · "
                   "capOut 확인됐지만 그 기준 아래라 뺀 수 · floor 그 기준 (원 · 기준을 모르면 빈 값) · noNaver · bad · noYahoo · diff · diffEx · left 빠진 코드 · yMeta · cut {s · yahoo · "
                   "fill · naver}}} · must 확인 못 한 필수 종목 (관문이 실패) · chk 1차 출처를 야후와 맞춘 "
                   "필수 종목 + 표본 {n · same · none · diff} · n 발행한 한국 종목 중 pxDate 종가로 실은 수 (출처별 · pxd 종목 빼고) · "
                   "knx 코넥스 종가 (2026-11-20) {px 출처 (listing · "
                   "yahoo+naver · 그날 파일에 코넥스가 없는 2차 출처 날은 빈 값) · t 발행한 코넥스 코드 (pxd 종목 빼고) · n 출처별 수 · chk 1차 출처 날 네이버 확인 {src naver · n · same · none · noneEx · "
                   "diff · fail · cut {s · naver} · err}} · "
                   "own (2026-11-19 · 2차 출처 날만) 확인 못 한 종목을 지난 발행본의 마지막 확인 종가로 실은 기록 {v · max 나이 상한 (그 종가 뒤 거래일) · "
                   "n 실은 수 · codes 실은 종목 코드 · unconf 확인 못 한 종목 수 (코넥스는 그날 야후 .KQ × 네이버로 확인하지 못한 종목만 · 2026-11-20) · "
                   "unconfWhy 그 까닭별 수 {mkt 두 번째 출처 없음 (코넥스 단계를 묻지 않은 날의 코넥스) · conf 다음 × 야후로 확인 못 함 · knx 야후 .KQ × 네이버로 확인 못 한 "
                   "코넥스 (= pxSrc.fb.knx.left 의 수 · 관문이 맞춰 봐요)} · drop 싣지 못한 까닭별 수 (none 지난 발행본에 없음 · same 같은 기준일 · "
                   "old 나이 상한 넘음 · bad 값을 읽을 수 없음 · jump 과거 주가 기록 오류 기록 없음) · dropEx 예 · bad 파일을 쓰기 직전 관문과 같은 함수로 "
                   "거른 종목 {n · rows · why 까닭(점검)별 수} · ind (2026-11-20 · 있을 때만) 지난 발행본이 DART 로 채웠거나 보통주를 따른 업종 글자를 옮기지 않은 종목 수 "
                   "{refill 오늘 다시 채움 (indSrc.dartT · prefT 에 적혀요) · krx 오늘 KRX-DESC 글자로 · unread 설명을 읽지 못해 비움} · err 이 단계가 오류로 "
                   "멈춘 까닭 (실은 종목 0) · aged (2026-11-20) 마지막 확인 종가가 나이 상한을 넘어 잠시 뺀 종목 [{t · nk · pxd 그 종가 날짜}] — 오늘도 "
                   "확인 못 한 동안 실행마다 이어 적고, 다시 확인되거나 목록에서 사라지면 빼요 (앱은 그 종목 자리에 '며칠째 종가를 확인하지 못해서 이 "
                   "종목은 잠시 빼 두었어요.')}"),
         "indSrc": ("한국 업종 글자의 출처 (2026-11-19): desc KRX-DESC 에서 업종을 받은 종목 · carried 받지 못해 지난 발행본에서 이어 쓴 종목 · "
                    "asOf 이어 쓴 글자의 날짜 · none 업종 없음 · newNone 그중 지난 발행본에도 없던 새 상장 · "
                    "dart none 중 DART 기업개황 업종 코드의 11차 소분류가 우리 업종 표(data/ksic_map_kr.csv)에 깔끔히 맞아 채운 보통주 수 · "
                    "dartT {종목: KSIC 코드} (설명 앞에 공식 이름 · 업종 키 s 는 표에서 · 다음 실행은 이어 쓰지 않고 다시 채워요) · "
                    "pref 보통주의 업종 글자 · 업종 키를 따른 우선주 수 · prefT {우선주: 보통주} · prefInd 2.0 그룹을 보통주에 맞춘 우선주 수 · "
                    "left 그래도 업종 글자 없는 종목 (펀드 빼고) · dartMiss 이유별 수 (fund · noCode · noName · mapNone · mapAmbig · mapFin · "
                    "mapFund · noGroup · noParse · prefNoCommon · prefCommonNone · prefOver · dropped · noTable) · dartErr 채우기가 고장 난 날의 "
                    "예외 이름 (그날 left 는 빈 값) 또는 table:예외 (업종 표를 읽지 못해 DART 로 채우지 않은 날) — 관문 경고 · mapSha 채울 때 쓴 "
                    "업종 표(data/ksic_map_kr.csv)의 판 (sha256 앞 12자리 · 표가 바뀐 뒤의 옛 채움은 관문이 경고만)"),
         "krSeries": ("국내 시계열 점검 (2026-11-14): 최근 거래일(days)의 네이버 일봉(수정주가)을 그날 공식 종가로 고친 봉 pinned · 종목 "
                      "pinStocks — 그날과 오늘 사이에 KRX 기준가(목록 파일의 Close − Changes)가 바뀌지 않았을 때만 (값 차이 "
                      f"{PIN_PX_TOL:.0%} 안, 또는 상장주식수가 오늘과 {PIN_SHR_TOL:.0%} 안이고 {PIN_REF_TOL:.0%} 안) · 기준가를 확인 못 한 날은 "
                      f"상장주식수가 {PIN_SHR_TOL:.0%} 안이고 값 차이 {PIN_PX_TOL:.0%} 안일 때만 · ref {{breakStocks 기준가가 새로 정해진 종목 "
                      "(분할 · 병합 · 감자 · 권리락) · unknownStocks 기준가를 확인 못 한 종목 · newStocks 그 기간에 새로 상장한 종목} · 고치지 않은 봉 kept (basis 다른 기준 · far 값이 멂 · "
                      "shr 주식 수 모름) · keptStocks · bad 자기 점검에 걸린 봉 (0 이어야 해요 · 관문 실패) · badStocks · jump [[종목코드, 날짜, %, "
                      f"이유]] 하루 움직임이 가격 제한폭(코스피 · 코스닥 {KR_DAY_LIMIT:g}% · 코넥스 {KONEX_DAY_LIMIT:g}%)과 넥스트레이드 차이로 "
                      "설명되지 않는 봉 — 이유 " + " · ".join(f"{k} {v}" for k, v in KR_JUMP_WHY.items())
                      + " · hidden [종목코드…] 그 움직임이 있어서 시계열로 만든 숫자를 비운 종목 (2026-11-14 · jump 의 발행 종목과 같아요 · 종목의 pxBad)"),
         "pxBad": ("한국 · 과거 주가 기록 오류 (2026-11-14): 시계열에 가격 제한폭으로 설명되지 않는 하루 움직임이 있는 종목(krSeries.jump)의 가장 "
                   "최근 움직임 날짜 (YYYY-MM-DD). 비운 칸은 pxBadF"),
         "pxBadF": ("한국 · pxBad 종목에서 비운 칸 목록 (2026-11-14 · Jack: 계산 창에 그 움직임이 든 칸만): 시계열 전체 칸 "
                    + " · ".join(PX_BAD_ALWAYS) + " 은 늘 · " + " · ".join(f"{'·'.join(ks)} ({PX_BAD_WIN_BARS[w]}봉)" for w, ks in PX_BAD_WIN.items())
                    + " 은 그 창의 봉에 움직임 날짜가 있을 때만. 비운 칸은 빈 칸이고 점수와 순위는 그 칸 없이 매겨요 (hi 가 들어 있으면 52주까지 비운 종목). "
                    "corp.json 의 그 회사도 같은 pxBad · pxBadF 에 같은 칸이 빈 칸이에요"),
         "unitFix": ("corp.json · 단위를 잘못 적은 분기 보고서를 나눠 쓴 회사: [{rep 보고서 (예 2026.2Q), bs · is · cf 그 표를 나눈 배수 "
                     "(1000 · 1000000, 나누지 않은 표는 칸 없음)}] — 표마다 그 보고서의 지난해 칸이 사업보고서 · 지난해 같은 분기 보고서 값의 정확히 "
                     "k 배이고, 나눈 뒤 기본주당이익 또는 자본금 ÷ 액면가가 오늘 주식 수와 맞을 때만 · 공시 단위 확인에 걸린 회사(unitChk)에는 없어요"),
         "etf": "true = ETF·펀드·금현물 (회사 주식이 아님)",
         "price": "한국 원 · 미국 달러 · 금현물 원/g", "pct": "% (vol·mdd·r1·r3·r36·mom·al·dy·roe 등)",
         "pxDate": "한국 가격의 공식 종가 날짜", "usPxDate": "미국 가격의 마지막 완성 봉 날짜",
         "pxd": ("그 종목의 자기 가격 날짜 · 미국: 그 종목의 마지막 봉이 usPxDate 가 아닐 때만 (2026-11-20: pxc 가 있으면 usPxDate 종가가 야후에 없어 "
                 "지난 발행본의 마지막 확인 종가로 실은 종목 · usSrc.own · 그 종가 뒤 미국 거래일 5일까지) · 한국 (2026-11-19): 2차 출처 날에 두 출처로 확인하지 못해 "
                 "지난 발행본의 마지막 확인 종가로 실은 종목 (pxSrc.own · 그 종가 뒤 거래일 5일까지) · 가격과 그 가격으로 만든 숫자는 이 날짜 기준, d1 은 빈 칸"),
         "ed": ("미국 종목의 다음 실적 발표일 (미국 현지 날짜 YYYY-MM-DD · 야후가 확정이라고 적은 날만 · 모르거나 추정이면 칸 없음 · 야후 상세 정보 "
                "보관본은 며칠 묵고 발표가 끝난 지난 날짜일 수 있어 앱은 오늘 이후 날짜만 써요 · v19.6b)"),
         "xd": ("미국 종목의 배당락일 (미국 현지 날짜 YYYY-MM-DD · 야후 exDividendDate · 그 전날까지 산 주식이 그 배당을 받아요 · 지난 날짜일 수 "
                "있어요 · 모르면 칸 없음 · v19.6b)"),
         "nextPub": "다음 발행 예정일 (한국 날짜 · data/market_holidays.csv 기준 한국·미국 중 먼저 오는 다음 거래일의 다음 날)",
         "staleAfter": "이 시각(한국 시간)이 지나도 새 파일이 없으면 앱이 '갱신이 멈췄어요'를 보여요 (예정일 마지막 정해진 실행 + 2시간)",
         "usLeftOut": "미국 목록에서 뺀 티커: preferred = 우선주·예탁증서(티커·이름·야후 종류로 판단), krListing = 한국 종목의 미국 상장분",
         "fcur": "미국 종목의 재무제표 통화 (ISO 코드, 달러가 아닐 때만 · 야후 financialCurrency). 이 종목은 per · pbr · vz 가 빈 칸이고, dy 는 "
                 "지난 12개월 배당이 없다고 야후가 분명히 말할 때만 0 이에요",
         "pbrZero": "true = 미국 종목의 PBR 이 0.00 으로 반올림돼(0.005 미만) 빈 칸 (vz 도 없음 · 재무제표 통화 문제가 아니에요)",
         "usFcurUnknown": "재무제표 통화를 모르는 미국 회사 주식의 티커 (야후가 financialCurrency 를 주지 않음 · 비우지 않았어요)",
         "usInfoPartial": "오늘 야후 응답이 일부만 와서 이름 · 업종 · 설명 · 재무제표 통화 같은 설명 칸을 예전 값으로 채운 미국 종목의 티커 (다음 실행이 다시 물어요)",
         "usForeign": ("미국에 상장된 외국 회사(ADR · 외국 보통주) 중 재무제표 통화 표시(fcur)가 없는 종목의 주당 숫자 검사: "
                       "checked = 확인한 티커 · cut = 비운 칸 [티커, 칸(per · pbr · dy), 이유] — PER 은 시가총액 ÷ 순이익, PBR 은 그 값 × ROE, "
                       "배당수익률은 지난 350일 실제 배당 ÷ 종가와 맞지 않으면 빈 칸이에요 (pbr 이 비면 vz 도 없음) · set = 규칙으로 찾은 외국 회사 "
                       "{티커: [야후 본사 나라, 재무제표 통화, 근거: fcur 재무제표 통화가 달러가 아님 · country S&P 500 밖이고 본사가 미국 밖 · adr 이름이 "
                       "예탁증서 · floor 손으로 정한 21곳 · prev 어제 발행한 set 에서 이어 옴 (S&P 500 목록을 쓸 수 없던 날) · error 판별 중 멈춤]} "
                       "(fcur 회사는 #114 가 이미 비워 checked 에 없어요) · unknown = 야후가 본사 나라를 주지 않아 외국 회사로 보지 않은 S&P 500 밖 "
                       "회사 · kind = {티커: {칸: 종류}} (종목의 fgnCut 과 같아요) · nocmp = 맞춰 볼 값이 없을 때의 스위치 (line 비우고 승인된 줄 · "
                       "keep 비우지 않음 · own 비우고 새 줄) · kept = 스위치 keep 이라 비우지 않은 칸 [티커, 칸, 이유] · sp500 = {n S&P 500 목록 "
                       "크기, inList 오늘 미국 목록과 겹침, ok 믿었는지 (400곳 아래면 본사 나라 규칙을 쓰지 않은 날)}"),
         "usExtraMissing": "손으로 더한 미국 종목(EXTRA_US) 중 오늘 목록에 없는 티커 → 빠진 이유",
         "usSrc": ("미국 종가의 출처 기록 (2026-11-20 · Jack: 야후 종가가 없는 미국 종목도 마지막 확인 종가로): own {v · max 나이 상한 (그 종가 뒤 미국 "
                   "거래일) · n 실은 수 · codes 마지막 확인 종가(pxc)로 실은 티커 · same 지난 발행본이 같은 usPxDate 라 그날 종가와 d1 을 그대로 실은 티커 "
                   "(pxd 없음) · from (머지 확인) codes · same 의 행마다 야후가 준 것 {티커: bar 시계열은 있고 기준일 봉만 없음 · empty 쓸 수 있는 가격이 "
                   "하나도 없음 · err 받다가 오류} — 관문의 '미국 종목 수' 두 줄은 bar 만 세요 · newer (리뷰) 야후에 그 종목의 더 새 봉(기준일 앞 · 미국 거래일)이 있어 그 종가로 실은 [{t · pxd · px}] · split (리뷰) "
                   "그 종가 뒤 분할이 있어 싣지 않은 종목 [{t · pxd · after 분할 날짜 · late 발행할 splits 에서 찾음}] (예전 그대로: 야후의 자기 날짜 봉 · "
                   "없으면 빠짐) · unconf 미국 기준일 종가가 야후에 없는 종목 수 · why 그 까닭별 수 (bar 기준일 종가 없음 · 빈 값 · 0 · 음수 · empty 쓸 수 있는 "
                   "가격이 하나도 없음 · err 받다가 오류) · drop 싣지 않은 까닭별 수 (none 지난 발행본에 없음 · halted 지난 발행본에서도 자기 날짜 — 둘 다 "
                   "예전처럼 야후의 마지막 봉 · old 나이 상한 넘음 · bad 값을 읽을 수 없음) · dropEx 예 · bad 관문과 같은 함수로 거른 행 {n · rows · why} · "
                   "aged 나이 상한을 넘어 잠시 뺀 종목 [{t · nk · pxd}] (앱은 '며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요.') · err 이 단계가 "
                   "오류로 멈춘 까닭 (실은 종목 0)} · newWait (2026-11-22 · Jack) 지난 발행본의 미국 종목에도 aged 에도 없던(새로 들어온) 티커 중 미국 "
                   "기준일 종가가 야후에 없어 오늘 넣지 않은 티커 (정렬 · 있을 때만 · 종가가 확인되는 날 들어와요 · 지난 발행본이 일부러 뺀 티커(usLeftOut)는 "
                   "기다리지 않아요 · 그래서 drop none 은 그런 티커와 지난 발행본을 쓸 수 없던 날 · 이 단계가 멈춘 날만)"),
         "pxc": ("미국 · true = 미국 기준일 종가가 야후에 없어 지난 발행본의 마지막 확인 종가로 실은 종목 (2026-11-20 · usSrc.own.codes · pxd = 그 "
                 "종가의 날짜 · d1 빈 칸 · 앱은 '오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요.' — pxc 없는 pxd 는 예전처럼 야후의 마지막 봉 날짜)"),
         "usListSym": ("미국 목록 출처의 티커를 야후 모양으로 바꾼 기록 (2026-11-15): mapped = [출처, 출처 티커, 야후 티커] (S&P 500 목록의 BRKB → "
                       "BRK-B · BFB → BF-B: FinanceDataReader 가 위키백과의 점을 지워요 · 점 · 빗금 · 띄어쓰기 꼴 → 대시) · unmapped = [출처, 출처 "
                       "티커, 이유] 바꾸지 못해 요청하지 않은 티커 · spGone = S&P 500 목록 종목 중 오늘 목록에 없는 티커 → 이유 (목록을 믿지 못한 "
                       "날은 빈 값) · noPx = 그중 야후가 가격을 하나도 주지 않은 티커 (점이 지워진 새 주식 종류 티커일 수 있어요) · spErr = 그중 "
                       "처리하다 오류로 멈춘 티커 · spTickers = 그날 S&P 500 목록의 티커 (야후 모양 · 못 읽은 날 빈 값) · missing = 이 "
                       "바꾸기로 들어온 종목(BF-B) 중 오늘 없는 티커 → 빠진 이유 · read = 출처 티커 기록이 있었는지"),
         "ownDrop": ("우리 처리 검사가 빼거나 비우거나 되돌린 행 (Jack 의 상시 규칙 2026-11-19): {검사 열쇠: {n 행 수, rows 앞 30개}} · usClass = "
                     "미국 목록에서 뺀 행 (S&P 500 의 점이 지워진 꼴이 바뀌지 않고 실림 · 관문 표와 다르게 바꾼 티커 · rows [열쇠, 이유]) · divLine = "
                     "기록(divCheck.proofSub)과 맞지 않아 비운 숨긴 배당수익률의 줄 (dvLine 2 · 3 · 4 · 기록은 줄인데 표시가 없던 종목도 수에 들어가요 · "
                     "rows [열쇠, 이유]) · 두 검사의 관문은 n 이 기준을 넘거나 그런 값이 남으면 실패, 1 이상이면 경고 · indFill = 국내 업종 채운 값 중 "
                     "되돌린 행 (DART 로 채운 보통주 · 보통주를 따른 우선주 — validate_data.ind_fill_bad · rows '종목 이름: 이유') · usDates = 틀린 미국 ed · "
                     "xd 를 비운 행 (v19.6b · validate_data.us_date_bad_rows · 그 칸만 비워요) · krOwn = 마지막 확인 종가(pxd)로 실었다가 관문과 같은 함수"
                     "(validate_data.kr_own_close_bad)로 뺀 국내 종목 (2026-11-20 · rows [코드, 까닭] · pxSrc.own.bad 와 같은 수 · 관문은 한 점검에서 "
                     "5개를 넘으면 실패, 있으면 경고)"),
         "fgnCut": ("미국 상장 외국 회사의 종목 칸: 회사 합계와 맞지 않아 비운 칸 {per · pbr · dy: mismatch 맞춰 봤는데 맞지 않음 · currency 재무제표 "
                    "통화를 확인하지 못함 · norecord 배당 기록 · 가격을 읽지 못한 배당수익률 · nocompare 회사 숫자로 PER · PBR 을 맞춰 볼 수 없음 (적자 · ROE 없음) · "
                    "nocompare-own 같은 뜻, 스위치 own 일 때 (지금 · 앱 줄 co.fgnNoCmp) · stopped 검사가 멈춘 날 맞춰 보지 않고 비움 (앱 줄 co.fgnStopped)} "
                    "(usForeign.cut 과 같은 칸 · 앱이 그 칸 '–' 밑에 이유 줄을 붙여요 · 검사가 멈춘 날의 칸은 없어요)"),
         "splits": ("2016-01-01 부터(splitsFrom)의 주식 분할 [종목 코드, 날짜, 배율] · 미국만 (야후 · 날짜는 미국 현지 날짜, 새 주식 수로 거래가 "
                    "시작된 날) · 배율 = 옛 1주가 새로 몇 주인지 (4:1 분할 4 · 1:10 병합 0.1) · 한 번 실은 분할은 빼지 않아요 (종목이 목록에서 빠져도) · "
                    "야후가 분할 칸에 적은 분사 조정(1253:1000 같은 배율)은 넣지 않고, 야후가 틀리게 적는 진짜 사건은 고정 표로 넣어요 (splitsInfo.fixed) · "
                    "야후 + 고침 (커밋한 시드 data/us_splits_seed.csv · 작은 주식배당은 다 들어 있지 않을 수 있어요) · "
                    "한국 종목은 아직 들어 있지 않아요 · splitsAsOf: 야후에서 마지막으로 새로 읽은 날 · splitsSrc: yahoo 모두 읽음 · part 일부 종목을 "
                    "읽지 못함 · kept 하나도 읽지 못해 지난 발행본 그대로 · splitsInfo: noCol 오늘 읽지 못한 종목 수 · gap 2016년부터를 아직 읽지 못한 "
                    "종목 · diff 야후가 빼거나 바꾸거나 날짜를 옮긴 분할 [코드, 날짜, 실은 배율, 야후 배율 또는 빈 값, (야후 날짜)] · fixed 고정 표 "
                    "[코드, 날짜, 배율 또는 빈 값(빼기), 근거] · fixedKept 코드에서 지웠지만 이어 둔 고정 줄")}
IDX_YEARS = 3


def idx_hist(series):
    """지수 일별 종가 3년치 (macro.json idxHist). 이미 자기 기준일까지 잘린 시계열을 받아요. (순수 함수)"""
    s = series.dropna()
    last = s.index[-1]
    s = s[s.index > last - pd.DateOffset(years=IDX_YEARS)]
    return {"asOf": last.date().isoformat(), "rows": [[d.date().isoformat(), round(float(v), 2)] for d, v in s.items()]}


# ── Jack 의 상시 규칙 (2026-11-19 ~17:45 KST · 우리 처리를 보는 검사) ──────────────────────────────
# Jack, verbatim: "Standing rule for checks on our own processing: a single bad row is dropped or blanked with a loud warning and the
# rest publishes. Block only when many rows fail in one run (set the number from recent runs and show it in the PR) or when a value would
# show a wrong number." 나쁜 행은 관문 파일의 함수가 골라요 (같은 함수 · 한 곳). 여기서는 빼거나 비우고, 크게 남기고, data.json ownDrop 에
# 적어요 ({열쇠: {"n", "rows" 앞 30}} · 깨끗한 실행도 0 으로). 관문은 n 이 N 을 넘거나 빼야 할 값이 남으면 실패, 1~N 이면 경고예요.
US_CLASS_DROP_NAME = "미국 주식 종류 티커 (S&P 500 의 점이 지워진 꼴 · 관문 표와 다른 바꾸기)"
DIV_LINE_DROP_NAME = "숨긴 배당수익률의 줄 (dvLine 2 · 3 · 4 가 기록 proofSub 와 맞지 않음)"


def us_meta_drop(umeta, us, bad):
    """뺀 미국 행(bad: 티커들)의 것을 umeta (fetch_us 의 기록) 에서도 빼요 (#139 · 2026-11-20 리뷰 3 이 함께 써요): 오늘 시세 다운로드의 분할 줄
    (splits · 목록에 없는 종목의 새 분할 줄은 관문 실패) · splitsNoCol · usInfoPartial · usFcurUnknown 의 티커 · usForeign 의 그 종목 기록 · usInfo 수.
    us: 빼기 전 목록. umeta 를 고쳐요."""
    row0 = lambda x: isinstance(x, (list, tuple)) and x and x[0] in bad      # noqa: E731 — [티커, …] 줄
    if isinstance(umeta.get("splits"), list):
        umeta["splits"] = [x for x in umeta["splits"] if not row0(x)]
    for k in ("splitsNoCol", "usInfoPartial", "usFcurUnknown"):
        if isinstance(umeta.get(k), list):
            umeta[k] = [t for t in umeta[k] if t not in bad]
    uf = umeta.get("usForeign")
    if isinstance(uf, dict):                       # 리뷰 1차 S1: 뺀 종목의 외국 회사 기록 (관문이 종목의 fgnCut 과 맞춰 봐요)
        for k in ("checked", "unknown"):
            if isinstance(uf.get(k), list):
                uf[k] = [t for t in uf[k] if t not in bad]
        for k in ("cut", "kept"):
            if isinstance(uf.get(k), list):
                uf[k] = [x for x in uf[k] if not row0(x)]
        for k in ("kind", "set"):
            if isinstance(uf.get(k), dict):
                uf[k] = {t: v for t, v in uf[k].items() if t not in bad}
    if isinstance(umeta.get("usInfo"), list) and len(umeta["usInfo"]) == 2:   # [상세 정보를 붙인 종목, 종목] — 뺀 행만큼 줄여요
        info = sum(1 for s in us if s.get("t") in bad and "dk" in s)     # dk 는 상세 정보를 붙인 행에만 (apply_us_info · n_ok 와 같은 행)
        umeta["usInfo"] = [max(0, umeta["usInfo"][0] - info), sum(1 for s in us if s.get("t") not in bad)]


def own_drop_us_class(us, umeta):
    """#139 의 우리 처리 검사 (validate_data.us_class_bad_rows): 발행하면 안 되는 미국 행을 빼요 → (남긴 미국 목록, ownDrop.usClass 의 값).
    빼는 행: S&P 500 목록의 점이 지워진 꼴(BRKB · BFB)이 바뀌지 않고 실린 행 (야후가 그 꼴에 답했다면 다른 증권이에요) · 기록이 깨져 출처를 알 수
    없는 그 꼴 · 관문 표와 다르게 바꾼 티커의 행. 행 통째로 빼요: 가격 · 시가총액 · 점수가 모두 다른 증권의 숫자일 수 있어 값 하나만 비우면 틀린
    숫자가 남아요. 업종 · 순위 · 분할 · 인기 목록보다 먼저 부르면 그 계산에도 들어가지 않아요 (main). umeta (fetch_us 의 기록) 에서 그 행의 것도
    빼요: 오늘 시세 다운로드의 분할 줄(splits · 목록에 없는 종목의 새 분할 줄은 관문 실패) · splitsNoCol · usInfoPartial · usFcurUnknown 의 티커.
    usListSym 은 출처 기록이라 그대로 둬요 (관문이 같은 함수로 남은 행을 다시 봐요)."""
    rows, probs = us_class_bad_rows(umeta.get("usListSym"), gate_us_stocks({"stocks": us}))
    bad = {r[0] for r in rows}
    kept = [s for s in us if s.get("t") not in bad]
    if bad:
        us_meta_drop(umeta, us, bad)
    if rows:
        log(f"  !! {US_CLASS_DROP_NAME}: {len(rows)}건 빼고 발행 — {own_drop_text(rows)} (data.json ownDrop.usClass · 관문 경고 · "
            + (f"{US_CLASS_DROP_MAX}건을 넘어 관문에서 실패해 발행하지 않아요)" if len(rows) > US_CLASS_DROP_MAX else f"{US_CLASS_DROP_MAX}건을 넘으면 실패)"))
    else:
        log(f"· {US_CLASS_DROP_NAME}: 0건 빼고 발행")
    if probs:
        log(f"  !! {US_CLASS_DROP_NAME} — 기록 문제 ({'관문에서 실패해 발행하지 않아요' if US_CLASS_BLIND in probs else '관문 경고'}): "
            + " · ".join(probs))
    return kept, own_drop_rec(rows)


def own_blank_div_lines(kr, div_counts, prev=None):
    """#142 의 우리 처리 검사 (validate_data.div_line_bad_rows): 기록(divCheck.proofSub)과 맞지 않는 숨긴 배당수익률의 줄을 비워요 →
    ownDrop.divLine 의 값. shown (종목에 줄이 있는데 기록이 그 줄을 정하지 않음): 그 종목의 dvLine 만 지워요 — 앱은 그 자리에 이유 줄 없이
    빈 배당수익률을 보여요 (숫자는 그대로 · 틀릴 수 있는 이유를 말하지 않아요). missing (기록은 줄을 정했는데 표시가 없음): 비울 것이 없어요 (이유
    줄 없이 빈칸 그대로). 둘 다 수에 들어가요. 줄 1 (Jack 의 줄) 은 보지 않아요 (예전 규칙 그대로).
    prev (직전 발행본 data.json): 오늘 기록이 없거나 틀려 확인할 수 없는 그 발행본의 줄 2 · 3 · 4 (validate_data.div_lines_lost · 관문과 같은 함수)도
    로그에 세요 — 기록과 줄이 함께 사라진 날 비울 것이 없어도 그 종목들은 이유 줄을 잃고, 관문은 그 수까지 합쳐 N 을 넘으면 실패해요 (리뷰 2차)."""
    kr_g = gate_kr_stocks({"stocks": kr})
    rows, probs, _want, checked = div_line_bad_rows(kr_g, div_counts)
    lost = div_lines_lost(prev, checked)
    total = len({r[0] for r in rows} | set(lost))
    over = max(len(rows), total) > DIV_LINE_BLANK_MAX
    by = {s.get("t"): s for s in kr_g}
    for t, _w, kind in rows:
        if kind == "shown":
            by[t].pop("dvLine", None)
    n_miss = sum(1 for r in rows if r[2] == "missing")
    gate = (f"줄을 잃은 종목 {max(len(rows), total)}곳 — {DIV_LINE_BLANK_MAX}곳을 넘어 관문에서 실패해 발행하지 않아요" if over
            else f"관문 경고 · 줄을 잃은 종목이 {DIV_LINE_BLANK_MAX}곳을 넘으면 실패")
    if rows:
        log(f"  !! {DIV_LINE_DROP_NAME}: {len(rows)}건 비움" + (f" (그중 줄이 원래 없던 종목 {n_miss})" if n_miss else "")
            + f" — {own_drop_text(rows)} (data.json ownDrop.divLine · {gate})")
    else:
        log(f"{'  !! ' if lost else '· '}{DIV_LINE_DROP_NAME}: 0건 비움" + (f" ({gate})" if lost else ""))
    if lost:
        log(f"  !! {DIV_LINE_DROP_NAME}: 직전 발행본에 줄 2 · 3 · 4 가 있던 {len(lost)}곳은 오늘 기록(proofSub)이 없거나 틀려 확인할 수 없어 이유 줄이 "
            f"빠져요 — {', '.join(lost[:30])}{f' 외 {len(lost) - 30}곳' if len(lost) > 30 else ''} ({gate})")
    if probs and isinstance((div_counts or {}).get("proof"), dict):     # 증명이 돌았는데 기록이 맞지 않아요 (증명이 없는 실행은 기록도 없어요)
        log(f"  !! {DIV_LINE_DROP_NAME} — 기록 문제 ({'관문에서 실패해 발행하지 않아요' if over else '관문 경고'}): " + " · ".join(probs))
    return own_drop_rec(rows)


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
    # 2026-11-21 (#161 리뷰): 같은 날 다시 돌았는데 더 얻은 것이 없으면 3시간 안의 정해진 시각 · 바깥 타이머 실행은 데이터를 모으지 않아요
    # (파일을 바꾸지 않아요 — 관문 · 화면 검사는 발행본 그대로를 보고, 발행 판단이 '같은 날 · 더 낫지 않음' 으로 발행하지 않아요)
    auto = os.environ.get("GITHUB_EVENT_NAME") == "schedule" or os.environ.get("BAEPSAE_AUTO_RUN") == "1"
    quiet = kr_rerun_throttle(kr_rerun_state_load(), prev, dt.datetime.now(KST), auto=auto, run_ok=github_run_succeeded)
    if quiet:
        log(f"  !! {quiet}")
        quiet_mark(quiet)
        return
    tables = load_industry_tables()       # 업종 표가 깨졌으면 여기서 바로 멈춰요
    # 2026-11-19: 한국표준산업분류 11차 · 11차 소분류 → 우리 업종 표 (DART 로 업종 글자 채우기). 깨졌으면 크게 남기고 채우기만 건너뛰어요
    # (리뷰: 표 하나 때문에 하루 발행이 멈추지 않게 — 우선주는 그대로 보통주를 따르고 관문이 경고해요)
    ksic_names = ksic_map = ksic_sha = ksic_err = None
    try:
        ksic_names = load_ksic_names()
        ksic_map = load_ksic_map_kr(names=ksic_names)
        ksic_sha = ksic_map_kr_sha()
    except Exception as e:
        ksic_names = ksic_map = ksic_sha = None
        ksic_err = type(e).__name__
        log(f"  !! 업종 표(data/ksic_names.csv · data/ksic_map_kr.csv)를 읽지 못했어요 ({ksic_err}: {str(e)[:160]}) — DART 로 업종 글자를 "
            "채우지 않고 발행해요 (우선주는 보통주를 따라요 · 관문이 경고해요). 표를 고쳐 주세요")
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
    # 2026-11-19 (Jack 의 규칙): 마지막 확인 종가 종목을 관문과 같은 함수로 다시 보고, 맞지 않는 종목은 빼요 (빼면 크게 남기고 pxSrc.own.bad 에 적어요).
    # 국내 시세 단계 바로 뒤 — 이 함수가 보는 칸(가격 · pxd · d1 · 거래 없음 표시 · 기록)은 여기서 정해지고 뒤 단계가 바꾸지 않아요. 그래서 뺀 종목이
    # DART · 배당 · 손익 집계(divCheck · incCheck) · 점수(백분위) · 필수 종목 순위 · corp.json 어디에도 남지 않아요 (리뷰: 집계와 종목이 어긋나지 않게)
    kr_drop = []                          # 2026-11-20: 뺀 종목 (코드, 까닭) → data.json ownDrop.krOwn (다른 우리 처리 검사와 같은 곳)
    try:
        kr = kr_own_close_final(kr, kmeta.get("pxSrc"), prev, [pd.Timestamp(t).date().isoformat() for t in kmeta["_index"].index]
                                if kmeta.get("_index") is not None else None, krs=kmeta.get("krSeries"), drop_out=kr_drop)
    except Exception as e:                # 점검이 오류로 멈추면 확인할 수 없는 마지막 확인 종가는 싣지 않아요 (예전처럼 빠져요) — 발행은 이어가요
        kr_drop.clear()
        kr = kr_own_close_drop_all(kr, kmeta.get("pxSrc"), kmeta.get("krSeries"), f"{type(e).__name__}: {str(e)[:200]}", drop_out=kr_drop)
    px_date = dt.date.fromisoformat(kmeta["pxDate"]) if kmeta["pxDate"] else today - dt.timedelta(days=1)

    fin_map, client, ksic = {}, None, {}
    # v19.1b: v2 캐시가 없던 첫 실행은 워크플로가 v1 폴더를 받아요(미국 상세 정보 보관본을 이어 쓰려고). 옛 DART 파일은 읽지 않으니
    # 지워서 v2 캐시에 실려 가지 않게 해요.
    carry, keep_v2 = None, None
    for old_name in ("dart-v1.json.gz", "dart-v2.json.gz"):      # v19.1f: v2 파일도 (v3 부터 새로 받아요)
        legacy = os.path.join(os.path.dirname(DART_CACHE_PATH) or ".", old_name)
        if os.path.abspath(legacy) != os.path.abspath(DART_CACHE_PATH) and os.path.exists(legacy):
            if old_name == "dart-v2.json.gz":
                # v19.1f: 해석과 상관없는 업종 코드 · 기업코드 목록만 옮겨요. v2 파일은 v3 캐시를 처음 저장한 뒤에 지워요 (리뷰 2026-11-08:
                # 그 전에 실행이 멈추면 다시 실행이 또 옮겨 쓸 수 있게 — 아니면 업종 코드 약 2,400회를 다시 받아요)
                carry, keep_v2 = read_carry(legacy), legacy
                log(f"· 옛 DART 캐시 파일 {legacy}: 업종 코드만 옮기고 재무제표·배당 항목은 읽지 않아요 (v{DART_CACHE_VERSION} 부터 새로 받아요)"
                    " — 새 캐시를 처음 저장하면 지워요")
                continue
            os.remove(legacy)
            log(f"· 옛 DART 캐시 파일을 지웠어요 ({legacy}) — 읽지 않아요 (v{DART_CACHE_VERSION} 부터 새로 받아요)")
    if dart_mode == "off":
        log("  !! 시험 실행: DART 를 끄고 진행해요 (재무지표·공시 없음 → 검증에서 실패 처리돼요)")
    elif DART_KEY:
        client = DartClient(DART_KEY, mode=dart_mode, today=today)
        same_day, why_sd = kr_same_day_rerun(prev, kmeta.get("pxSrc"), kmeta.get("pxDate") and dt.date.fromisoformat(kmeta["pxDate"]))
        if same_day and dart_mode == "cache":           # 2026-11-21 (#161 리뷰): DART 하루 한도 — 같은 기준일을 다시 도는 실행은 보관본 값만
            # #161 리뷰 3차 A-S3: 빈 보관본으로 DART 를 부르면 전체 DART 실행이에요 (하루 한 번 · 수동 · CLAUDE.md) — 같은 날 다시 하는 실행은 그러지
            # 않고 멈춰요 (사이트는 발행본 그대로 · 빨간 실행으로 알려요). 정해진 시각 실행은 그 전에 워크플로 · DartClient 가 멈춰요.
            if client.started_empty:
                raise RuntimeError(f"!! {why_sd} 인데 DART 보관본이 비어 있어요 — 빈 보관본으로 DART 를 부르면 전체 DART 실행이라 (하루 한 번 · 수동) "
                                   "DART 를 부르지 않고 여기서 멈춰요 (발행본의 재무 그대로 · 사이트 그대로)")
            covers, why_cov = dart_cache_covers(client.meta, prev)
            if covers:
                client.no_call = why_sd
                log(f"  !! {why_sd}: DART 를 부르지 않아요 ({why_cov}) — 재무는 보관본, 공시 (지분 · 주요사항) 는 미국 기준일도 같으면 발행본의 disc.json 그대로")
            else:
                log(f"  !! {why_sd} 이지만 {why_cov} → DART 를 예전처럼 불러요 (보관본에 있는 항목은 다시 받지 않아요 · 빈 보관본이 아니라 전체 DART "
                    "실행이 아니에요 · 공시도 DART 로)")
        if carry is not None:
            n_carry = adopt_carry(client, carry)
            log(f"· 옛 v2 캐시에서 옮긴 업종 코드 항목 {n_carry:,}건 (읽은 {len(carry[0]):,}건 · 기업코드 목록 "
                f"{'옮김' if 'corpMap' in carry[1] else '없음'}) — 업종 코드는 보관 기간이 남은 것만 다시 받지 않아요")
        if keep_v2:
            client.remove_after_save.append(keep_v2)
        kr, fin_map = ph.run("DART", enrich_with_dart, kr, client, kmeta.get("_prefShares") or {})
        ksic = ph.run("업종 코드", fetch_ksic, kr, client)
    else:
        log("  !! DART_API_KEY 없음 → 재무지표·공시를 못 받아요 (검증에서 실패 처리돼요)")
    # v19.1f: DART 없이 도는 실행(dart=off · 키 없음)은 옛 v2 파일을 옮길 곳이 없어 예전처럼 바로 지워요 (DART 단계 뒤 · 그 안이 아니에요)
    if keep_v2 and client is None and os.path.exists(keep_v2):
        os.remove(keep_v2)
        log(f"· 옛 DART 캐시 파일을 지웠어요 ({keep_v2}) — 이번 실행은 DART 를 쓰지 않아요")
    blank_foreign_dart(kr)                # v17.5.2: 해외 기업 (점수·corp.json 보다 먼저)
    blank_non_won(kr, fin_map)            # v19.1f (리뷰): 원화가 아닌 재무제표 (두산밥캣 USD) — 같은 자리
    roe_before = {s["t"]: s.get("roe") for s in kr if s.get("cls") == "kr"}   # v19.1f (리뷰): ROE 기준을 바꿔 움직인 것을 세요 (roe_moves)
    mult_extra = fill_multiples(kr, fin_map, kmeta.get("_prefShares") or {})     # v19.1f: 지배주주 몫 · 영수증(epsIn·bpsIn·roeIn)
    unit_cover = unit_guard(kr, fin_map, mult_extra, kmeta.get("_prefShares") or {})["cover"]   # (2026-11-13) 공시 단위 확인 (점수·incCheck·corp.json 보다 먼저)
    # v19.1b: 분할에 안전한 배당 (dps3a·dpsF·divSt·dyt) — 해외 기업 비우기 뒤, 점수(dz)·corp.json 보다 먼저
    # v19.1h: 맞춘 해가 있는 종목은 DART 결정 공시로 이유를 확인해요 (dvWhy · 공시와 다른 해는 맞추지 않아요). DART 가 꺼졌으면 조회 실패로 세요
    why = DivWhy(client, px_date)
    div_counts, corp_extra = apply_div_basis(kr, fin_map, kmeta.get("_prefShares") or {}, why=why)
    if client:
        try:
            client.save()                 # 새로 받은 공시 확인이 뒤 단계 실패로 사라지지 않게
        except Exception as e:
            log(f"  !! DART 캐시 저장 실패(배당 맞춤 이유 뒤): {e}")
    for t, e in mult_extra.items():
        corp_extra.setdefault(t, {}).update(e)
    inc_check = income_check(kr, fin_map, mult_extra)
    log(f"· 손익 줄 집계(incCheck): {inc_check}")
    eps_basis, eps_why = eps_basis_of(kr, mult_extra)
    log(f"{'· ' if eps_basis == EPS_BASIS else '  !! '}EPS 기준 표시(epsBasis): {eps_basis} — {eps_why}"
        + ("" if eps_basis == EPS_BASIS else " — 관문에서 실패해 발행하지 않아요 (앱의 '고치는 중' 줄은 그대로)"))
    n_dy = sum(1 for s in kr if s.get("dy") is not None)
    log(f"· 배당수익률 아는 종목: {n_dy:,} / {len(kr):,} (모르는 종목은 0% 가 아니라 빈 칸 → 앱에 '–')")
    n_dps = sum(1 for s in kr if s.get("dps") is not None)
    n_dps0 = sum(1 for s in kr if s.get("dps") == 0)
    fy_c = collections.Counter(s.get("fy") for s in kr if s.get("fy"))
    log(f"· 주당 배당금 아는 종목: {n_dps:,} / {len(kr):,} (그중 0원 = 배당 없음 {n_dps0:,}) · 사업보고서 연도 {dict(sorted(fy_c.items()))}")

    us, us_bench, fx, fx_last, us_vol_krw, umeta = ph.run("미국", fetch_us, start, today, rf,
                                                          kr_codes=frozenset(s["t"] for s in kr), dups=dups,
                                                          prev_fgn=prev_foreign_set(prev),   # 리뷰 S2: 어제 발행한 외국 회사 목록
                                                          prev=prev)   # 2026-11-20 (Jack): 야후 종가가 없는 종목은 지난 발행본의 마지막 확인 종가로
    # 2026-11-19 (Jack 의 상시 규칙): #139 의 검사가 잡는 미국 행(점이 지워진 꼴 · 관문 표와 다른 바꾸기)은 여기서 빼요 — 미국 목록이 정해진
    # 바로 뒤라 아래 분할 · 업종 · 순위 · 인기 목록 · 종목 수에도 들어가지 않아요 (data.json ownDrop.usClass)
    us, own_us = own_drop_us_class(us, umeta)
    # 2026-11-20 (Jack 의 상시 규칙): 마지막 확인 종가로 실은 미국 행을 관문과 같은 함수로 다시 보고 맞지 않는 행은 빼요 (usSrc.own.bad) — 미국 목록이
    # 정해진 바로 뒤라 아래 단계 어디에도 남지 않아요. 점검이 오류로 멈추면 그 행들을 모두 빼고 발행을 이어가요
    try:
        us = us_own_close_final(us, umeta, prev, [pd.Timestamp(t).date().isoformat() for t in umeta["_index"].index]
                                if umeta.get("_index") is not None else None)
    except Exception as e:
        us = us_own_close_drop_all(us, umeta, f"{type(e).__name__}: {str(e)[:200]}")
    # v19.6a (A.6): 주식 분할 (2016-01-01 부터 · 한 번 실은 분할은 빼지 않아요). 오늘 시세 다운로드가 읽은 분할(umeta) + 커밋한 시드 + 지난
    # 발행본의 줄 (splits_fields · merge_splits). 시드에도 지난 발행본에도 없는 종목만 2016년부터의 이력을 읽어요 (하루 몇 개 · 많아야 20).
    sp_fields = splits_fields(prev, [s["t"] for s in us], umeta.get("splits"), umeta.get("splitsNoCol") or [], start, today)
    # 2026-11-20 (리뷰 3): 발행할 분할에 마지막 확인 종가 뒤의 분할이 있는 행 (단계가 보지 못한 분할) — 빼고 그 종목의 새 분할 줄도 빼요
    try:
        us, sp_fields = us_own_split_late(us, umeta, sp_fields, prev)
    except Exception as e:
        log(f"  !! 마지막 확인 종가의 분할 다시 보기가 오류로 멈췄어요 ({type(e).__name__}: {str(e)[:160]}) — 관문이 그런 행을 막아요")
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
    # 2026-11-19: KRX-DESC · 지난 발행본에 업종 글자가 없는 국내 보통주 → DART 업종 코드가 우리 업종 표에 깔끔히 맞을 때만 (DART 를 새로
    # 부르지 않아요) · 우선주는 보통주를 따라요 · 틀린 행은 되돌려요 (Jack 의 상시 규칙). 2.0 그룹이 정해진 뒤 · corp.json 보다 먼저
    ind_drop = kr_ind_fill(kr, kmeta.get("_noInd") or [], ksic, ksic_map, kmeta.get("indSrc"), over=tables["over"],
                           names=ksic_names, map_sha=ksic_sha, table_err=ksic_err)
    for line in power_eq_sector_lines(*power_eq_sector_report(kr)):     # 2026-11-20: 전력기기 · 전선 제조사의 예전 뱁새 업종 (옮긴 수 · 남은 utility)
        log(line)
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
    # 2026-11-14 (Jack, Q2 (a)): 추세(mz) · 저변동(lz) 점수는 과거 주가 기록 오류로 비운 종목(pxBad) 없이 매겨요 (mom · vol 이 빈 칸이라 빠져요).
    # 빈 칸일 수 있는 값으로 순위를 매기니 필수 종목이 들어 있는지 크게 남겨요 — 빠지면 관문의 '필수 종목 추세 · 저변동 순위' 줄이 실패해요
    # Jack 2026-11-14 저녁 ("warn when one is affected; block the publish when two or more must-haves are affected"): 과거 주가 기록 오류로 맞게
    # 표시한 필수 종목이 하나면 관문의 필수 종목 세 줄(이 줄 · 52주 (야후) · 새 칸)은 경고만, PX_BAD_MUST_FAIL 곳 이상이면 실패 · 표시 없이 빠지면 실패
    miss_tr = trend_rank_missing(kr)
    marked_tr = [t for t, why in miss_tr if "과거 주가 기록 오류" in why]
    log(f"{'  !! ' if miss_tr else '· '}추세(mz) {sum(1 for s in kr if _fin(s.get('mz')) is not None):,} · 저변동(lz) "
        f"{sum(1 for s in kr if _fin(s.get('lz')) is not None):,}종목 (과거 주가 기록 오류로 뺀 "
        f"{sum(1 for s in kr if s.get('pxBad')):,}종목 없이) · 필수 종목 "
        + ("모두 있음" if not miss_tr else "빠짐: " + ", ".join(f"{t}({why})" for t, why in miss_tr)
           + (" — 관문에서 실패해 발행하지 않아요" if len(marked_tr) < len(miss_tr) or len(marked_tr) >= PX_BAD_MUST_FAIL
              else " — 관문의 필수 종목 줄들은 경고만 해요 (둘 이상이면 실패)")))
    roe_moves(kr, roe_before)             # v19.1f (리뷰): 로그만 — 퀄리티 점수(qz) · 2.0 ROE 하한이 얼마나 움직였는지
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

    # 2026-11-19 (Jack 의 상시 규칙): #142 의 검사가 잡는 숨긴 배당수익률의 줄(기록과 맞지 않는 dvLine 2 · 3 · 4)은 쓰기 바로 앞에서 비워요
    # (data.json ownDrop.divLine) — 그 뒤로 줄을 바꾸는 단계가 없어요 (corp.json 은 dvLine 을 싣지 않아요)
    own_div = own_blank_div_lines(kr, div_counts, prev)
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
        "usFcurUnknown": umeta["usFcurUnknown"],   # #114: 재무제표 통화를 모르는 미국 회사 (비우지 않았어요 — 관문이 경고해요)
        "usInfoPartial": umeta["usInfoPartial"],   # #114 리뷰 2: 오늘 야후 응답이 일부만 와 예전 설명 칸을 쓴 미국 종목 (관문이 경고해요)
        "usForeign": umeta["usForeign"],           # 2026-11-14: 미국 상장 외국 회사 주당 숫자 검사 (관문이 비운 칸 · 빠짐없이 확인했는지 봐요)
        "usExtraMissing": umeta["usExtraMissing"], # 2026-11-14: EXTRA_US 중 오늘 없는 종목과 이유 (관문이 이름과 이유를 경고로 · 기록에도 없으면 경고, 5곳 넘으면 실패)
        "usListSym": umeta["usListSym"],           # 2026-11-15: 주식 종류 티커 (BRKB → BRK-B · BFB → BF-B) · 바꾸지 못한 티커 (관문)
        "usSrc": umeta.get("usSrc") or {"v": 1, "own": us_own_close_err("기록 없음")},   # 2026-11-20 (Jack): 마지막 확인 종가로 실은 미국 종목 (관문 · 앱)
        # 2026-11-19 (Jack 의 상시 규칙): 우리 처리 검사가 빼거나 비운 행 — 관문이 수(N)와 남은 값을 봐요 (이 칸이 없는 예전 파일은 예전 규칙)
        "ownDrop": {US_CLASS_DROP_KEY: own_us, DIV_LINE_DROP_KEY: own_div},
        "divCheck": div_counts,              # v19.1b: 배당 분할 확인 집계 (관문이 종목과 맞춰 봐요 · 이 칸이 있으면 새 검사가 다 돌아요)
        "incCheck": inc_check,               # v19.1f: 손익 줄 집계 (관문이 corp.json 과 맞춰 봐요 · 이 칸이 있으면 손익 줄 검사가 다 돌아요)
        "epsBasis": eps_basis,               # v19.1f: EPS·PER 은 지배주주 몫 — 앱의 '계산 방법을 고치는 중' 줄이 이걸 보면 사라져요
        "unitChkCover": unit_cover,          # (2026-11-13) 공시 단위 확인이 몇 곳을 어떤 방법으로 봤는지 (관문 줄이 보여 줘요)
        "krSeries": kmeta.get("krSeries"),   # (2026-11-14) 국내 시계열 공식 종가 고정 · 자기 점검 · 제한폭 넘는 움직임 (관문 줄이 봐요)
        "pxSrc": px_src_final(kmeta.get("pxSrc"), stocks),   # (2026-11-19 · Jack 규칙 3) 공식 종가 출처 · 2차 출처 확인 수 (관문 줄이 봐요)
        "indSrc": kmeta.get("indSrc"),       # (2026-11-19) 국내 업종 글자의 출처 · 이어 쓴 수 (KRX-DESC 가 비면 지난 발행본에서)
        # (2026-11-14) 발행하는 국내 종목의 빈 d1 이유 수 (발행하는 종목 목록에서 다시 세요 — 그 사이에 빠진 종목이 있어도 종목과 같아요) ·
        # 거래 없음을 가릴 수 있었는지 · 어긋난 행 · 표시하지 않은 필수 종목 (관문 줄이 봐요)
        "d1Blank": d1_blank_final(stocks, kmeta.get("d1Blank")),
        "stocks": stocks,
    }
    payload.update(sp_fields)                # v19.6a (A.6): splits · splitsFrom · splitsAsOf · splitsSrc · splitsInfo (UNITS["splits"]) 또는 없음
    if kmeta.get("d1Base"):                  # 2026-11-21: 직전 거래일 파일을 쓸 수 없던 날에만 — KRX 기준가 × 지난 발행본 종가로 확인한 d1 (kr_d1_from_base)
        payload["d1Base"] = kmeta["d1Base"]
    own_us_dates(payload)                    # 2026-11-19 (Jack 의 상시 규칙): 틀린 미국 ed · xd 는 그 칸만 비워요 (data.json ownDrop.usDates)
    payload.setdefault("ownDrop", {})["indFill"] = ind_drop   # 2026-11-19 (Jack 의 상시 규칙): 업종 채운 값 중 되돌린 행 (관문 줄이 봐요)
    # 2026-11-20 (#159): 마지막 확인 종가로 실었다가 관문과 같은 함수로 뺀 국내 종목 (pxSrc.own.bad 와 같은 수 · 관문이 맞춰 봐요 · 깨끗한 실행도 0)
    payload["ownDrop"][KR_OWN_DROP_KEY] = own_drop_rec(kr_drop)
    log(kr_count_line(payload))
    write_json(OUT, payload)
    try:                                     # 2026-11-21 (#161 리뷰): 같은 기준일을 다시 돈 결과 (실제 실행만 · 다음 실행은 이 실행이 초록이었을 때만 믿어요)
        rs = kr_rerun_state(prev, payload, dt.datetime.now(KST), kr_px_count(payload), kr_px_count(prev) if isinstance(prev, dict) else None)
        if rs is not None:
            os.makedirs(os.path.dirname(KR_RERUN_STATE_PATH) or ".", exist_ok=True)
            write_json(KR_RERUN_STATE_PATH, rs)
            log(f"{'  !! ' if rs['gain'] <= 0 else '· '}같은 기준일을 다시 돈 결과: 그 날짜 종가 국내 종목 {rs['gain']:+,} — "
                + ("늘어난 것이 없어, 이 실행이 초록으로 끝나면 3시간 안의 정해진 시각 실행은 데이터를 모으지 않아요" if rs["gain"] <= 0
                   else "뒤의 실행도 그대로 돌아요"))
    except Exception as e:
        log(f"  !! 같은 날 다시 하기 기록을 쓰지 못했어요 ({type(e).__name__}) — 뒤의 실행은 쉬지 않고 돌아요")
    log(f"✓ {OUT} 저장 — {len(stocks):,}종목, {os.path.getsize(OUT) / 1e6:.1f}MB · 기준일 {kmeta['pxDate']} · "
        f"미국 {umeta['usPxDate']} · 환율 {fx_last:,.1f}")

    kr_mkt.update({"fx": round(fx_last, 1), "rf": round(rf * 100, 2)})
    corp = build_corp(kr, fin_map, today.isoformat(), kr_mkt, extra=corp_extra, pref_caps=kmeta.get("_prefCaps"),
                      pref_missing=kmeta.get("_prefCapMissing"))
    corp.update({"pxDate": kmeta["pxDate"], "publishedAt": published_at, "epsBasis": eps_basis})
    write_json(OUT_CORP, corp)
    dcf_n = sum(1 for c in corp["companies"] if c["dcfReady"])
    log(f"✓ {OUT_CORP} 저장 — 기업 {len(corp['companies']):,} · 업종 {len(corp['sectors'])} · DCF 자동채움 {dcf_n:,}건 · {os.path.getsize(OUT_CORP) / 1e6:.1f}MB")

    prev_macro = read_prev_data(OUT_MACRO)       # v19.6a: 지난 발행본의 fxHist (아래에서 덮어쓰기 전에)
    macro = ph.run("금리·원자재", fetch_macro, start, today, fx)
    macro["publishedAt"] = published_at
    # v19.6a Part I.1: 원/달러 일별 환율 2016 ~ (FX_HIST_SOURCE · fxHistSrc 출처 · fxHistFresh 출처에서 마지막으로 새로 읽은 날).
    # 못 만들면 싣지 않아요 (관문 경고). data.json fx 는 이 PR 에서 바꾸지 않아요.
    macro.update(ph.run("환율 이력", fx_hist_fields, fx, fx_last, today, prev_macro))
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

    prev_disc = None
    if client is not None and client.no_call:
        if isinstance(prev, dict) and umeta.get("usPxDate") == prev.get("usPxDate"):
            prev_disc, why_disc = load_morning_disc(live=prev)
        else:
            why_disc = f"미국 기준일이 발행본과 달라요 ({prev.get('usPxDate') if isinstance(prev, dict) else None} → {umeta.get('usPxDate')})"
        if prev_disc is None:
            client.no_call = None
            log(f"  !! {why_disc} → 공시는 예전처럼 DART 로 받아요")
    if prev_disc is not None:
        disc = prev_disc
        dart_cache_mark(client, published_at)
        client.save()
        log(f"  !! 공시: 같은 기준일을 다시 도는 실행이라 발행본의 disc.json 을 그대로 써요 (내부자 {len(disc.get('insider') or []):,}건 · "
            f"주요사항 {len(disc.get('issue') or []):,}건 · 공시 내용 날짜 {disc.get('asOf')} 그대로 — 그 뒤 나온 공시는 다음 새 기준일 발행에) · "
            f"DART 전체: {client.summary()}")
    elif client:
        disc = ph.run("공시", fetch_disclosures, kr, client.meta.get("corpMap") or {}, today, client)
        # v19.6b (Part B.1): 유상증자 · 전환사채 · 신주인수권부사채 결정 (issue · issueOk) — DART 를 쓰는 실행에서만 · 지분공시 뒤
        disc.update(ph.run("주요사항 공시", fetch_issues, kr, client.meta.get("corpMap") or {}, today, client))
        # v19.6b Q18 (Jack 2026-11-19): 유상증자 줄의 이사회결의일(bd)을 공시 원문에서 (실행당 ISSUE_BD_PER_RUN 건 · 실패해도 그 줄의 bd 만 빈 칸)
        ph.run("유상증자 결의일", fill_issue_bd, disc, client, today)
        dart_cache_mark(client, published_at)
        client.save()
        log(f"· DART 전체: {client.summary()}")
        n_calls = sum(client.status.values())
        if n_calls > DART_FULL_TARGET:
            log(f"  !! 이번 실행의 DART 호출 {n_calls:,}회가 목표 {DART_FULL_TARGET:,}회를 넘었어요 (하루 한도 {DART_DAY_LIMIT:,})")
    else:
        disc = empty_disc(today)
    disc["publishedAt"] = published_at
    own_check_disc(disc, today)              # 2026-11-19 (Jack 의 상시 규칙): 나쁜 공시 줄은 빼거나 비워요 (disc.json ownDrop · 관문과 같은 함수)
    write_json(OUT_DISC, disc)
    if "issueOk" not in disc:                # #161 리뷰 3차 nit: 다시 쓴 아침 disc.json 에 칸이 없어도 멈추지 않고 크게 (관문이 그 파일을 봐요)
        log(f"  !! {OUT_DISC} 에 issueOk 칸이 없어요 — 주요사항 공시 목록을 받았는지 몰라요 (관문이 봐요)")
    log(f"✓ {OUT_DISC} 저장 — 내부자 {len(disc.get('insider') or []):,}건 · 국민연금 {len(disc.get('nps') or []):,}건 · 주요사항(유상증자 · CB · BW) "
        f"{len(disc.get('issue') or []):,}건{'' if disc.get('issueOk') else ' (목록 실패 · 지난 줄)'} · 최근 공시 {disc.get('newest')}")
    log(ph.summary())


if __name__ == "__main__":
    main()
