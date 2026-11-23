#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
뱁새 발행 관문 — validate_data.py (v17.5)
──────────────────────────────────────────────────────────────
fetch_data.py 가 만든 네 파일을 검사해요. 하나라도 FAIL 이면 exit 1 → 워크플로가 커밋하지 않아요.
그러면 지난번 데이터가 날짜와 함께 그대로 남습니다.

  python validate_data.py                     # 이번 파일 vs 직전 발행본(git HEAD)
  python validate_data.py --prev-ref 7890e2b  # 직전 발행본 대신 특정 커밋과 비교 (시험용)
  python validate_data.py --bootstrap         # 직전 발행본을 읽을 수 없을 때 '한 번만' (수동 입력으로만)
  python validate_data.py --live --dir DIR    # 사이트에 올라간 파일 점검 (비교 없이 절대 기준만, v17.6 감시용)
  BAEPSAE_DAUM_LIMIT_S=600 python validate_data.py --live --dir _site   # 배포 (deploy.yml) — 다음 확인 전체에 600초 한도 (Jack 2026-11-20 · 배포만)
  python validate_data.py --live --daum-limit 600 --dir DIR             # 손으로 같은 한도 (600초 이상만 받아요)
  BAEPSAE_DAUM_LIMIT_S=600 BAEPSAE_DAUM_REFUSE_SKIP=1 python validate_data.py --live --dir _site   # 코드 배포 — 다음이 아예 거절하면 경고로 건너뜀
  python validate_data.py --live --daum-limit 600 --daum-refuse-skip --dir DIR   # 손으로 같은 꼴 (Jack 2026-11-21 · PX_ALT_REFUSE_ENV 옆 설명)

'최종본 날짜'는 fetch_data.py 를 쓰지 않고 이 파일의 코드로 따로 계산해요 (같은 실수를 같이 하지 않게).
규칙: 오늘(KST) 이전, 시가총액 90% 이상, 마지막 커밋이 그날 KRX 정규장 마감 + 30분 이후 (보통 15:30 → 16:00 KST).
마감이 늦는 날(수능일 10:00~16:30 → 17:00 등)은 data/krx_special_sessions.csv 에서 읽어요 (fetch_data.py 와 같은 표, 읽는 코드는 따로).
한국 공식 종가 = 시가총액 ÷ 상장주식수 (목록 파일의 Close 열은 저녁엔 시간외 가격이에요).
그 위에 한 겹 더: KOSPI 일봉(네이버 → 야후, 이 파일의 코드로 따로 받음)을 보고, pxDate 와 오늘(KST) 사이에
끝난 거래일이 하나라도 있으면 FAIL 이에요. 마지막 거래일의 목록 파일이 없거나 최종본이 아니어서 하루 전으로
물러난 경우를 잡아요 (publishedAt 은 새것이라 앱에는 경고가 안 뜨니까요).

임계값은 2026-10-17 발행본(DART 정상 마지막 날)에 맞춰 정했어요. 안전 규칙이라 함부로 낮추지 않습니다.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import ssl
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
FILES = ("data.json", "corp.json", "disc.json", "macro.json")
LIST_URL = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/{d}.csv"
COMMITS_API = "https://api.github.com/repos/FinanceData/fdr_krx_data_cache/commits"
NAVER_KOSPI = "https://fchart.stock.naver.com/sise.nhn?symbol=KOSPI&timeframe=day&count=60&requestType=0"
YAHOO_KOSPI = "https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11?range=3mo&interval=1d"
PUBLISHED_MAX_HOURS = 12  # 발행 시각(publishedAt)은 관문 실행 12시간 이내여야 해요
NORMAL_CLOSE = dt.time(15, 30)            # 보통 날 KRX 정규장 마감
FINAL_AFTER = dt.timedelta(minutes=30)    # 마감 30분 뒤 커밋부터 최종본 (보통 날 16:00 — v17.5 와 같아요)
SPECIAL_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "krx_special_sessions.csv")
# v19.1c (Jack, 2026-11-07): 휴장일 표 · 다음 발행 예정일 · 늦음 경고 시각. fetch_data.py 와 같은 표를 따로 읽고 따로 계산해요.
HOLIDAYS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "market_holidays.csv")
SPLIT_SEED_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "us_splits_seed.csv")   # v19.6a: 검토해 커밋한 분할 (fetch_data 와 같은 파일, 읽는 코드는 따로)
HOL_COLS = ["date", "market", "name", "source"]
LAST_RETRY = dt.time(14, 47)              # update-data.yml 의 그날 마지막 정해진 시각 실행 (월~토 14:47 KST)
STALE_GRACE_H = 2                         # GitHub 정해진 시각 실행이 늦게 시작하는 시간 + 실행 시간
HOL_COVER_WARN_DAYS = 45                  # 표가 오늘부터 이만큼 앞을 덮지 못하면 경고 (다음 해 줄을 넣을 때)
HOL_CHECK_DAYS = 90                       # 지수 일봉과 표를 맞춰 보는 지난 날 수 (봉 없는 평일 = 표의 휴장일)
HOL_MIN_PER_YEAR = 8                      # 한 해 평일 휴장이 이보다 적으면 반쯤 적은 해 (한국 12~16일 · NYSE 9~10일)
SPECIAL_COLS = ["date", "open", "close", "kind", "reason", "source"]
SPECIAL_KINDS = {"수능", "연초 개장", "기타"}
CSAT_CHECK_FROM = (9, 1)                  # 이날(KST)부터 올해 수능일 줄이 표에 없으면 경고
CSAT_BLOCK_FROM = (11, 1)                 # 이날(KST)부터는 실패 — 발행을 막아요 (Jack, 2026-11-04: 9월 1일 경고 · 11월 1일 실패)
ANNOTATE_MAX = 10                         # GitHub 은 한 단계에 경고·오류 알림을 종류마다 10개까지만 보여 줘요
MIN_CAP_SHARE = 0.90
LOOKBACK_DAYS = 10

MUST = ("005930", "000660", "005380", "015760", "105560", "035420", "012450")
FUNDS = ("069500", "379800", "04020000", "132030", "144600")
COVER_KR = {"price": 99, "cap": 99, "beta": 95, "vol": 95, "pbr": 85, "roe": 80, "per": 50,
            "vz": 85, "qz": 85, "mz": 85, "pz": 85, "lz": 85}
COVER_US = {"이름": 90, "설명": 90}
# 2026-11-12 (Jack, 더하기만): 미국 베타·변동성 채움 — 국내와 같은 95% (97% 아래 경고). 지금까지는 관문에 미국 줄이 없어,
# 일부만 빠진 날(예: 10%, 예전 앱 내장 종목은 셋 이하)은 그대로 발행됐어요 (#106 화면 검사는 내장 종목이 셋 넘게 빠질 때만 막아요).
# 7-29 이후 발행 70번: 베타 97.69~99.09% · 변동성 97.56~98.96%. 빈 칸은 대부분 상장 1년(250거래일) 안 된 회사예요 (MIN_DAYS) — 경고면 이름을 보세요.
COVER_US_RISK = {"beta": 95, "vol": 95}
BONDS_EXPECTED = 8       # 8 정상 · 7 경고 · 6 이하 실패 (Jack 결정, 2026-10-31)
KR_MIN, US_MIN = 2300, 500
KR_REL, US_REL = 0.10, 0.15
FX_LO, FX_HI, FX_REL = 900, 2000, 0.05
PRICE_MATCH = 99.0       # 한국 가격이 공식 종가와 같은 비율 (%)
MOVE_SHARE = 0.5         # 하루 한도(±30%)를 넘게 움직인 종목 허용 비율 (%)
US_STALE_DAYS, CURVE_STALE_DAYS = 4, 7
US_UNCHANGED = 20.0      # 미국 기준일이 바뀌었는데 가격이 그대로인 종목 허용 비율 (%)
CORP_MIN, SECTOR_MIN = 2000, 20
TTM_HARD, TTM_WARN = 50, 80
NEAR = 2.0               # 기준선에서 2점 안쪽이면 경고
# 2026-11-19 (Jack 규칙 3, 그대로): "Permanent two-source rule: official closes always come from two independent sources. If the
# primary is late or not final, the second one is used automatically after a cross-check. The publish stops only when neither
# can be confirmed." 1차 출처 = 자원봉사 캐시의 최종본 목록 파일 (예전 그대로) · 2차 출처 = 다음(Daum) 일별 시세 × 야후 .KS/.KQ 종가 (원 단위까지
# 같은 종목만). data.json pxSrc 에 어느 출처인지와 수를 적어요. 관문의 날짜 · 가격 줄은 그 날짜의 캐시 최종본이 있으면 예전 그대로 그것과,
# 없으면 관문이 야후에서 따로 받은 공식 종가 (필수 종목 + 표본 PX_CHECK_SAMPLE) 와 원 단위까지 맞춰 봐요 — 받지 못하면 '확인 못 함' → 실패.
PX_SRC_LISTING = "listing"                # 1차 출처: 캐시의 최종본 목록 파일
PX_SRC_FB = "daum+yahoo"                  # 2차 출처: 다음 일별 시세 × 야후 종가 (원 단위까지 같은 종목만)
PX_SRCS = (PX_SRC_LISTING, PX_SRC_FB)
# 코스피 · 코스닥의 다음 × 야후 짝에 쓰는 야후 접미어. 코넥스는 여기 없어요: 야후에는 {코드}.KQ 로 107종목 중 96종목이 있지만 (2026-11-19 조사)
# 다음에는 코넥스가 없어서 다음 × 야후 짝이 될 수 없어요. 코넥스는 따로 야후 .KQ × 네이버 (PX_SRC_KNX · 아래).
PX_YAHOO_SUFFIX = {"KOSPI": ".KS", "KOSDAQ": ".KQ", "KOSDAQ GLOBAL": ".KQ"}
# 2026-11-20 (Jack, 2026-11-19 답 5 그대로): "Yes: Naver for KONEX only, always with Yahoo, published only when they agree to the won;
# daily KONEX checking too." — 코넥스만: 2차 출처 날은 야후 .KQ 일봉 종가 × 네이버 일봉 종가가 원 단위까지 같은 종목만 (코넥스는 시간외 거래가
# 없어 네이버 일봉 종가 = 공식 종가: 2026-09-15 ~ 11-16 최종본 27일 2,881 / 2,881). 1차 출처 날은 발행하는 코넥스 종목을 모두 네이버와 맞춰 봐요 (경고만).
# 코스피 · 코스닥에는 네이버를 쓰지 않아요 (시간외 · 넥스트레이드 체결가라 공식 종가가 아니에요).
PX_SRC_KNX = "yahoo+naver"                # 코넥스 2차 출처: 야후 .KQ 일봉 종가 × 네이버 일봉 종가 (원 단위까지 같은 종목만)
PX_KNX_MARKET = "KONEX"                   # 목록 파일의 Market 값
PX_KNX_YAHOO_SUFFIX = ".KQ"               # 야후의 코넥스 접미어 (야후는 코넥스를 KOSDAQ · MUTUALFUND 로 잘못 적지만 일봉은 맞아요)
PX_CHECK_SAMPLE = 200                     # 관문(2차 출처 날) · 파이프라인(1차 출처 날)이 야후와 맞춰 보는 표본 수 (필수 종목은 따로 모두)
PX_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=1d"
PX_DAUM_DAYS = "https://finance.daum.net/api/quote/A{code}/days?symbolCode=A{code}&page=1&perPage=10&pagination=true"
PX_META_WINDOW = dt.timedelta(minutes=10)   # 야후 regularMarketTime 은 그날 마감 ~ 마감 + 10분 안이어야 해요 (실제 15:30:01 ~ 15:30:30 · 수능일 16:30)
PX_ALT_MIN_SHARE = 0.90                   # 관문이 야후에서 받은 표본 종가가 이 비율보다 적으면 '확인 못 함' (실패) — 받지 못한 채 통과시키지 않아요
PX_ALT_TOL = 0.01                         # 두 종가 차이 (원) — 부동소수점 끝자리만큼. 같은 호가여야 해요
# 2026-11-20 (Jack, 그대로): "Yes to 10 minutes, but a timeout skips the Daum spot-check with a loud warning; the deploy continues
# on the other checks. An outside site must never block a code fix."
# 사고: 11-20 09:03 KST 배포의 발행 관문(--live)이 19분 동안 한 줄도 남기지 않고 멈춰 있었어요 — 관문이 따로 묻는 다음 일별 시세(http_px_alt ·
# 필수 7 + 표본 200, 동시 4)가 느렸던 것으로 보여요. 요청마다 시간 한도(20초 · 세 번)는 있었지만 확인 전체에는 없었어요 (작업 한도 80분만).
# 배포의 관문만 (Jack 의 yes 는 배포만이에요): deploy.yml 의 관문 단계가 환경 변수 PX_ALT_LIMIT_ENV = 이 값을 줘요 (또는 손으로 --daum-limit 초).
# 감시(watchdog.py)는 예전 그대로 한도 없이 불러요 — 감시는 관문이 실패할 때만 경보를 여는데, 경고로 바꾸면 느린 다음이 조용한 통과가 돼요
# (멈추면 감시 job 의 30분 한도가 예전처럼 끝내요). 발행 관문(publish · bootstrap, 매일 실행)도 한도를 받지 않아요 — 발행을 거르는 검사를
# 느슨하게 하는 일이라 Jack 의 yes 가 따로 필요해요. 이 값보다 짧은 한도는 받지 않아요 (더 자주 건너뛰어 느슨해져요 · _main).
# 확인 전체에 600초 (fetch_data.KR_FB_PHASE_BUDGET_S 와 같은 꼴 · #151). 지나면 새 요청을 하지 않아요 (다시 묻기도) — 묻는 중인 요청은
# 자기 시간 한도까지 (연결 20초 + 바이트 사이 20초 ≈ 40초 · DNS 찾기와 바이트를 아주 천천히 흘리는 서버는 이 한도 밖이에요 — 본 적은 없어요)
# → 확인은 최악 약 600 + 40초 (약 10분 40초) 안에 끝나요. 일하는 스레드는 모두 끝난 뒤 돌아와요.
# 걸리면 시간 한도(와 네트워크 오류)로 설명되는 모자람만 경고로 건너뛰어요 (px_alt_cut_gap · 리뷰 2026-11-20): 다음이 분명히 답하지 않은
# 필수 종목(그날 행 없음 · HTTP 4xx · 종가 없음)이 있거나, 그런 종목만으로 표본 90% 를 못 채우면 예전 그대로 실패해요. 파일의 발행
# 기록(pxSrc) 조건도 예전 그대로이고, 받은 종가가 발행 가격과 다르면 가격 줄이 실패해요 (005930 정확히 같음 · 99% 는 묻기로 한 종목 수 기준 —
# 받지 못한 종목이 모두 맞았다고 쳐도 99% 에 못 미칠 때만 실패: 다 받았을 때도 반드시 실패하는 경우).
PX_ALT_LIVE_BUDGET_S = 600
PX_ALT_LIMIT_ENV = "BAEPSAE_DAUM_LIMIT_S"   # deploy.yml 관문 단계의 환경 변수 (그 단계에만 · 시험이 맞춰 봐요)
PX_ALT_REFUSE_ENV = "BAEPSAE_DAUM_REFUSE_SKIP"   # deploy.yml 관문 단계: 코드 배포만 "1" · 데이터 실행 뒤 배포는 "0" (아래 · 시험이 맞춰 봐요)
# 2026-11-21 (Jack, 11-20 질문 3 "Deploy price check when Daum refuses instead of being slow … Skip the Daum check in that case too, with the
# same loud warning? … (Recommended: yes, for code deploys only. …)" → 11-21 "3. Yes."): 다음이 느린 게 아니라 아예 거절하면 (KRX 처럼)
# 시간 한도에 걸리지 않아 배포가 매번 멈춰요. 코드 배포에서만 (Jack 의 yes 는 코드 배포만이에요), 다음이 거절한다고 볼 수 있으면 더 묻지 않고
# 한도에 걸렸을 때와 같이 크게 경고하고 건너뛰어요. 스위치는 따로예요 (리뷰 2026-11-21): 한도를 받은 --live 에 PX_ALT_REFUSE_ENV=1 (또는 손으로
# --daum-refuse-skip) 도 있어야 해요. deploy.yml 관문 단계는 코드 배포(push · 손으로)에만 1 을 주고, 데이터 실행 바로 뒤의 배포(workflow_run)에는
# 0 을 줘요 — 그 배포는 #157 의 시간 한도만 받아요. 감시 · 발행 관문은 예전 그대로예요 (한도도 이 스위치도 없어요).
# 거절 (종목마다 · px_refusal_answer · px_refusal_error): 다음이 HTTP 401 · 403 · 451 로 답함, 또는 세 번 모두 연결 거부 · 연결 끊김(reset ·
# abort · 응답 없이 닫음) · 상대가 TLS 를 끊음 (SSLEOFError · SSLZeroReturnError) 이나 상대가 거절 경보를 보냄 (PX_REFUSE_TLS_ALERTS) · HTTP 429.
# 시간 초과 · 5xx · DNS · 프록시 · 우리 쪽 OpenSSL 이 거절한 TLS (인증서 · WRONG_VERSION_NUMBER · DH_KEY_TOO_SMALL · HANDSHAKE_FAILURE 등) ·
# JSON 이 아닌 200 (차단 쪽 화면일 수도, 주소가 바뀐 것일 수도 있어요) · 404 · 그날 행 없음은 거절이 아니에요 (예전 그대로).
# 다음이 거절한다고 보는 때 (px_alt_refuse_need): 답이 정해진 종목이 모두 거절이고 (종가 · 그날 행 없음 같은 다른 답이 하나도 없음),
# 필수 종목이 모두 그 안에 있고, 그 수가 표본 기준(PX_ALT_MIN_SHARE)을 이미 채울 수 없게 하는 수 이상일 때 (207종목이면 21) — 그때는
# 예전 규칙으로도 이 확인은 통과할 수 없어요. 다른 답이 하나라도 먼저 오면 이 규칙은 그 실행에서 꺼지고 예전 그대로예요 (일부만 거절).
# 건너뛰어도 받은 종가는 가격 줄에서 비교하고 (#157 과 같은 기준), 다음이 분명히 답하지 않은 필수 종목은 예전 그대로 실패해요.
IND_CARRY_WARN_DAYS = 14                  # 지난 발행본에서 이어 쓴 국내 업종 글자가 이보다 오래되면 경고 (fetch_data 와 같은 값)
# 2026-11-19 (Jack, verbatim): "The 129 unconfirmed stocks: stop showing "이 종목의 데이터를 찾지 못했어요." Show each stock's last confirmed
# close with its own date (the existing own-close mechanism), plus "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." It must never sit
# under today's date label without that line."
# 2차 출처 날에 두 출처로 확인하지 못한 국내 종목은 지난 발행본의 마지막 확인 종가로 실어요 (fetch_data.kr_own_close_carry): 가격 · 그 가격으로 만든
# 숫자는 그 종가의 것이고, 종목의 pxd = 그 종가의 날짜 · d1 없음 (미국 pxd 와 같아요). pxSrc.own 에 실은 종목 코드와 수를 적어요.
# 나이 상한: 그 종가 뒤 pxDate 까지의 KRX 거래일 수 (pxd < 거래일 ≤ pxDate)가 이보다 많으면 싣지 않아요 (예전처럼 빠져요). 미국 pxd 에는 나이 상한이
# 없어요 (파이프라인 · 관문 · 앱 모두) — 그래서 Jack 의 늦은 데이터 점검 창(#144: "for up to 5 trading days", src/v2/tradedays.js
# LATE_CHECK_DAYS)과 같은 5 거래일로 제안해요 (PR 의 'Choices made').
KR_OWN_CLOSE_MAX_DAYS = 5
KR_OWN_SHOW = 10                          # 값 칸에 적는 종목 수 (나머지는 수만 · 전체는 요약 목록에)
# kr_own_close_bad 의 까닭: shape · d1 은 미국 pxd 줄과 같은 실패 (국내 자기 가격 날짜 줄) · 나머지는 경고 (마지막 확인 종가 줄)
KR_OWN_WHY = {"shape": "pxd 가 pxDate 보다 앞선 날짜가 아님", "d1": "pxd 인데 d1 이 있음",
              "mark": "pxd 인데 d1Why · noTrade · ntD1 이 있음", "price": "가격이 없음", "src": "2차 출처 날이 아님 (pxSrc.px)",
              "rec": "pxSrc.own 에 적힌 종목이 아님", "old": f"그 종가 뒤 거래일이 {KR_OWN_CLOSE_MAX_DAYS}일 넘음",
              "prev": "지난 발행본의 마지막 확인 종가 · 날짜와 다름"}
KR_OWN_FAIL_WHY = ("shape", "d1")
# 2026-11-20 (Jack, d: "drop a carry with a broken date and warn; block only above 5." · his standing rule for our own processing:
# more than 5 rows fail one check in one run → the gate fails): the pipeline drops a carried row that kr_own_close_bad finds wrong
# (kr_own_close_final · pxSrc.own.bad: n and, per reason, why) and the '국내 자기 가격 날짜 (pxd)' row warns; when more than this many
# rows were dropped for one reason (one check: broken date · d1 · marks · price · source day · record · age · previous publish) in
# one run, it fails (that check is broken, not one stock). Reasons are not added up. N = max(5, 3 × the most dropped in a recent
# run): no publish before this change has a Korean pxd, so every recent count is 0 → 5. A wrong row still in the file (the drop
# failed) fails the row as before. A run whose check itself stopped (own.err: every carry dropped, none judged wrong) and a record
# without the per-reason counts only warn (the carry row says so).
KR_OWN_DROP_MAX = 5
KR_OWN_DROP_KEY = "krOwn"     # 2026-11-20: data.json ownDrop 의 열쇠 (다른 우리 처리 검사와 같은 곳 · {n, rows [코드, 까닭]} · pxSrc.own.bad.n 과 같은 수)
# 2026-11-20 (Jack, verbatim): "Also: US stocks carry like Korean ones. A US stock with no close from Yahoo carries its last confirmed
# close with its own date and the same line. Block only if many are missing (set the number from history), so a Yahoo gap never
# stops the Korean data again."
# 미국 기준일(usPxDate) 종가가 야후에 없는 미국 종목 (빈 값 · 0 · 음수 · 가격을 하나도 받지 못함): 지난 발행본에 그 종목이 기준일 종가로 있었으면 그
# 가격으로 싣고 pxd = 그 발행본의 usPxDate · pxc = true (마지막 확인 종가 표시 — 야후가 그 종목의 마지막 봉을 자기 날짜로 준 '거래 정지' pxd 와
# 앱 · 관문이 구별해요) · d1 없음. 지난 발행본도 pxc 로 실었으면 같은 가격 · 같은 pxd. 지난 발행본의 usPxDate 가 오늘과 같으면 (같은 날 다시 발행)
# 그 종목의 그날 종가와 d1 을 그대로 (pxd 없음 · usSrc.own.same). fetch_data.us_own_close_carry · 기록 data.json usSrc.own.
US_OWN_CLOSE_MAX_DAYS = 5                 # 그 종가 뒤 usPxDate 까지의 미국(NYSE) 거래일이 이보다 많으면 싣지 않아요 (빼고 usSrc.own.aged)
US_OWN_SHOW = 10
US_OWN_WHY = {"shape": "pxd 가 usPxDate 보다 앞선 날짜가 아님", "d1": "마지막 확인 종가(pxc)인데 d1 이 있음",
              "mark": "pxc 표시가 true 가 아니거나 pxd 가 없음", "price": "가격이 없음",
              "rec": "usSrc.own 에 적힌 종목이 아님", "old": f"그 종가 뒤 미국 거래일이 {US_OWN_CLOSE_MAX_DAYS}일 넘음",
              "prev": "지난 발행본의 마지막 확인 종가 · 날짜와 다름",
              "same": "같은 날 다시 쓴 종가(usSrc.own.same)가 지난 발행본의 그날 종가 · d1 과 다름",
              "split": "그 종가 날짜 뒤에 주식 분할이 있음 (data.json splits · 가격은 분할 전인데 앱이 주식 수를 바꿔요)",
              "newer": "더 새 야후 종가(usSrc.own.newer)가 기록 · 지난 발행본의 날짜 · 미국 거래일과 맞지 않음",
              "from": "야후가 무엇을 줬는지(usSrc.own.from: bar · empty · err)가 적혀 있지 않음 (미국 종목 수에 셀지 정할 수 없어요)"}
# 날짜가 깨졌거나 d1 이 옆에 있는 마지막 확인 종가 — 파일에 남아 있으면 실패 (국내와 같아요). 리뷰 (2026-11-20): 같은 날 다시 쓴 종가가 지난 발행본과
# 다르면 (d1 이 있고 날짜가 없어 미국 기준일 종가로 보여요) · 그 종가 뒤에 분할이 있으면 (평가액이 분할 배율만큼 틀려요) 도 실패
US_OWN_FAIL_WHY = ("shape", "d1", "mark", "same", "split", "from")
US_OWN_FROM = ("bar", "empty", "err")     # usSrc.own.from 의 값 — '미국 종목 수' 두 줄은 bar 만 세요 (예전에도 야후의 자기 날짜 봉으로 실렸을 행)
US_OWN_DROP_MAX = 5                       # 파이프라인이 한 점검에서 거른 행이 이보다 많으면 실패 (Jack 의 상시 규칙 · 국내 KR_OWN_DROP_MAX 와 같아요)
# N (Jack: "Block only if many are missing (set the number from history)"): 야후 종가가 없는데 마지막 확인 종가로 싣지 못한 미국 종목
# (d1 이 없고 깨끗한 마지막 확인 종가가 아님 — 예전처럼 야후의 마지막 봉을 자기 날짜로 실은 종목)이 이보다 많으면 '미국 d1 채움' 줄이 실패해요.
# 마지막 확인 종가로 실은 종목은 몇 개든 경고만 (야후가 비어도 국내 데이터가 멈추지 않게). 상시 규칙 max(5, 3 × 최근 발행본에서 본 가장 큰 수):
# data 브랜치의 2026-11-05 ~ 11-20 발행본 27개 모두 야후 종가가 없는 미국 종목 0 → 5 (PR 의 표).
US_NO_CLOSE_MAX = 5
# 2026-11-19 (Jack: "new listings take their industry from DART's company records"): KRX-DESC 에도 지난 발행본에도 업종 글자가 없는 국내 종목은
# DART 기업개황 업종 코드(KSIC)의 앞 3자리(소분류) 이름으로 채워요. 이름은 통계청 한국표준산업분류 11차 표에서만 (fetch_data 와 같은 파일 · 읽는 코드는 여기 하나)
KSIC_NAMES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ksic_names.csv")
IND_MAP_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "industry_map.csv")
IND_GROUPS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "industry_groups.csv")
IND_DART_DIGITS = 3                       # KRX 업종 글자와 같은 단계 (소분류 · 3자리) — 2026-11-19 표본 93종목 모두 KRX 글자 = 이 이름 (띄어쓰기만 다른 19)
IND_FUND_KSIC = "642"                     # '신탁업 및 집합 투자업' — 상장 펀드일 수 있어 DART 로 회사 업종을 채우지 않아요 (fetch_data KR_FUND_KSIC)
KSIC_LEVELS = {1: 21, 2: 77, 3: 234, 4: 501, 5: 1205}   # 11차 개정의 단계별 항목 수 (대 · 중 · 소 · 세 · 세세) — 파일이 바뀌면 예외
# 2026-11-19 (Jack, ~17:45 KST: "don't show 통계청 industry names as new groups. Map each official code to our existing industry
# groups, so 업종 lists, industry averages and 업종별 등락 keep one naming system. Report any codes that don't map cleanly."):
# 11차 소분류(3자리) 코드마다 우리 두 업종 체계로 가는 길을 적은 표 (data/ksic_map_kr.csv · fetch_data.ksic_map_kr_rows 가 만들어요):
#   s       예전 뱁새 업종 키 (detail.jsx SECTORS · KRX 글자를 바꾸던 그 규칙 map_sector_kr 에 11차 이름을 넣은 값)
#   ind     2.0 업종 그룹 (data/industry_map.csv 의 KSIC 접두어 · 그 코드와 아래 4·5자리 코드가 가는 그룹 모두)
#   status  ok 깔끔히 맞음 · none 짝 없음 · ambiguous 두 체계가 갈림 · financial 금융 · fund 집합 투자업 — ok 만 채워요
KSIC_MAP_KR_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ksic_map_kr.csv")
KSIC_MAP_STATUS = ("ok", "none", "ambiguous", "financial", "fund")
# 2.0 업종 그룹 → 그 그룹과 같은 뜻인 예전 뱁새 업종 키 (첫 칸이 대표). 두 체계가 같은 업종을 가리키는지 보는 짝이에요 — 여기 없는 그룹
# (services 기업 서비스 · holding 지주회사 · 금융 그룹)은 예전 뱁새에 짝이 없거나 금융이라 채우지 않아요. 작은 그룹이 합쳐지는 상위 그룹도 적어요.
# 키를 지우지 마세요 — 짝을 없애려면 () 로 두세요 (리뷰 2026-11-19: 라이브 관문이 이미 발행한 채움을 그 그룹으로 다시 봐요). () 인 그룹은 짝이 없어
# 채우지 않아요 (none).
IND_SECTOR_KR = {
    "food": ("food", "hotel"), "textile": ("textile",), "paper": ("paper",), "furniture": (), "services": (), "holding": (),
    "cosmetics": ("cosmetic",), "energy": ("energy",), "chem": ("chem",), "spchem": ("chem",), "rubber": ("chem",),
    "cement": ("build",), "steel": ("steel",), "metal": ("steel",), "metalwork": ("steel",),
    "semi": ("semi",), "semi_eq": ("semi", "machine"), "display": ("elec", "machine"), "elec_parts": ("elec",),
    "telecom_eq": ("elec", "machine"), "appliance": ("elec",), "medical": ("health",), "precision": ("elec", "machine"),
    "power_eq": ("elec",), "battery": ("battery",), "machinery": ("machine",), "robot": ("machine",),
    "defense": ("defense",), "ship": ("ship",), "auto": ("auto",), "auto_parts": ("auto",),
    "pharma": ("bio",), "bio": ("bio",), "healthcare": ("health",), "utility": ("utility",), "construction": ("build",),
    "trading": ("retail",), "retail": ("retail",), "logistics": ("transport",), "shipping": ("transport",),
    "airline": ("transport",), "leisure": ("hotel",), "media": ("media",), "entertainment": ("media",),
    "software": ("platform", "game"), "game": ("game", "platform"), "it_service": ("platform",), "internet": ("platform",),
    "telecom": ("telecom",), "realestate": ("realestate",), "education": ("edu",),
    "chems": ("chem",), "metals": ("steel",), "hardware": ("elec", "machine"), "health": ("bio", "health"),
    "autos": ("auto",), "transport": ("transport",), "mediaent": ("media",), "softnet": ("platform", "game"),
}
# 리뷰 (2026-11-19): 예전 뱁새는 업종 키마다 '업종 읽는 법'(detail.jsx LENS)을 보여요. 규칙: 그 글이 그 코드 회사들의 것을 맞게 짚을 때만
# 채워요 — 글이 이름 붙인 매출원 · 원재료 · 값을 정하는 쪽이 그 회사들의 것이어야 해요 (일반적인 경향 '경기 방어력' · '경우가 많아요' 는 따지지 않아요).
#   furniture (가구 · 기타 제조) — 예전 뱁새에 가구 키가 없고 paper 의 '원재료(펄프)' 가 가구 회사의 것이 아니라 짝이 없어요
#   cosmetics — chem 의 '정제마진 · 스프레드' 가 화장품 회사의 것이 아니라 짝에서 뺐어요
#   power_eq — utility 의 '요금은 정부가 정해요' 가 전동기 · 변압기 회사의 것이 아니라 짝에서 뺐어요
#   281 — 2026-11-20 (Jack "3. Yes") KRX 글자 길이 utility 에서 elec 으로 바뀌었어요 (fetch_data.SECTOR_ELEC_NOT_UTILITY). 표의 키도 elec 이지만
#         DART 로 새 상장사를 채우는 건 그 답에 없어서 그대로 채우지 않아요 (채우려면 이 줄을 빼요 · Jack 의 답 먼저)
KSIC_LENS_MISFIT = {
    "161": "예전 뱁새 paper 의 '원재료(펄프)' — 제재 · 목재 회사의 원재료는 원목이에요",
    "231": "예전 뱁새 build 의 '수주와 분양 · PF' — 유리 회사의 매출은 제품 판매예요",
    "233": "예전 뱁새 build 의 '수주와 분양 · PF' — 시멘트 회사의 매출은 제품 판매예요",
    "281": "KRX 글자 길을 2026-11-20 utility 에서 elec 으로 옮겼어요 (그 전엔 utility 의 '요금은 정부가 정해요' 가 맞지 않아 채우지 않았어요) — "
           "DART 로 채우는 건 Jack 의 답을 기다려요",
    "319": "예전 뱁새 machine 의 '고객 산업의 설비투자 사이클' — 자전거 · 이륜차 · 전투차량 · 수소탱크는 설비투자로 팔리지 않아요",
    "381": "예전 뱁새 utility 의 '요금은 정부가 정해요' — 폐기물 수집 · 운반 요금은 계약으로 정해요",
    "382": "예전 뱁새 utility 의 '요금은 정부가 정해요' — 폐기물 처리 요금은 계약으로 정해요",
    "390": "예전 뱁새 utility 의 '요금은 정부가 정해요' — 환경 정화는 계약 공사예요",
    "682": "예전 뱁새 realestate 의 '임대수익률과 금리 차이' — 부동산 관련 서비스(중개 · 관리 · 감정)의 매출은 수수료예요",
    "713": "예전 뱁새 media 의 '구독자 증가율과 편당 수익성' — 광고 회사의 매출은 광고 대행 수수료예요",
}
IND_FIN_SECS = ("bank", "insure", "broker", "holding")
IND_FIN_GROUPS = ("bank", "insurance", "securities", "finance", "fin")   # 2.0 금융 그룹 (industry_groups.csv financial=yes) — 채우지 않아요
# 예전 뱁새의 업종 키 (src/detail.jsx SECTORS — tests/test_ind_dart.py 가 같은지 봐요). 여기 없는 키는 앱이 모르는 키예요
OLD_SECTOR_KEYS = ("bond", "semi", "elec", "battery", "auto", "ship", "defense", "machine", "steel", "chem", "energy", "utility", "bio", "health",
                   "platform", "game", "media", "telecom", "bank", "insure", "broker", "holding", "build", "realestate", "retail", "food",
                   "cosmetic", "textile", "transport", "edu", "paper", "hotel", "index", "metal", "etc")   # 예전 뱁새의 금융 업종 키 (fetch_data.FIN_SECS 와 같아요 · EV 계열 멀티플을 빼요)
# Jack 의 상시 규칙 (2026-11-19): 우리 처리 단계에서 틀린 행은 빼고(되돌리고) 크게 알린 뒤 나머지를 발행해요. 한 실행에서 이보다 많이
# 되돌리면 관문이 실패해요. data 브랜치의 최근 발행본 20개에 새 채우기를 다시 돌려 본 되돌림 수가 모두 0 이라 max(5, 3 × 0) = 5
# (PR #146 의 표 · Jack 의 2026-11-19 답 1 "#146's one").
IND_FILL_MAX = 5


def load_ksic_names(path=KSIC_NAMES_CSV):
    """한국표준산업분류(11차) 코드 → 이름 {코드: 이름} (data/ksic_names.csv · '#' 줄은 출처 설명). 머리줄 · 칸 수 · 빈 이름 · 겹친 코드 ·
    단계별 항목 수(KSIC_LEVELS)가 다르면 예외 — 조용히 이름 없이 넘어가지 않게."""
    with open(path, encoding="utf-8") as f:
        lines = [x for x in f.read().splitlines() if x.strip() and not x.startswith("#")]
    rows = list(csv.reader(lines))
    if not rows or rows[0] != ["분류", "코드값", "상세설명"]:
        raise ValueError(f"!! {os.path.basename(path)} 머리줄이 '분류,코드값,상세설명' 이 아니에요: {rows[:1]}")
    out = {}
    for r in rows[1:]:
        if len(r) != 3 or r[0] != "산업" or not r[1].strip() or not r[2].strip() or r[1] in out:
            raise ValueError(f"!! {os.path.basename(path)} 이상한 줄: {r}")
        out[r[1]] = r[2]
    lv = dict(collections.Counter(len(c) for c in out))
    if lv != KSIC_LEVELS:
        raise ValueError(f"!! {os.path.basename(path)} 단계별 항목 수 {lv} ≠ 11차 {KSIC_LEVELS}")
    return out


def load_ksic_map_kr(path=KSIC_MAP_KR_CSV, names=None):
    """11차 소분류 코드 → {name, s, ind (2.0 그룹 튜플), status, why} (data/ksic_map_kr.csv · '#' 줄은 설명). 머리줄 · 칸 수 · 상태 ·
    빈 칸이 이상하거나, names(11차 표)와 코드 · 이름이 다르면 예외 — 조용히 넘어가지 않게."""
    with open(path, encoding="utf-8") as f:
        lines = [x for x in f.read().splitlines() if x.strip() and not x.startswith("#")]
    rows = list(csv.reader(lines))
    if not rows or rows[0] != ["ksic", "name", "s", "ind", "status", "why"]:
        raise ValueError(f"!! {os.path.basename(path)} 머리줄이 'ksic,name,s,ind,status,why' 가 아니에요: {rows[:1]}")
    out = {}
    for r in rows[1:]:
        if len(r) != 6 or len(r[0]) != IND_DART_DIGITS or r[0] in out or not r[1] or not r[2] or r[4] not in KSIC_MAP_STATUS \
                or (r[4] == "ok" and (not r[3] or r[2] == "etc" or r[2] in IND_FIN_SECS
                                      or any(r[2] not in IND_SECTOR_KR.get(g, ()) for g in r[3].split("·")))):
            raise ValueError(f"!! {os.path.basename(path)} 이상한 줄: {r}")
        out[r[0]] = {"name": r[1], "s": r[2], "ind": tuple(x for x in r[3].split("·") if x), "status": r[4], "why": r[5]}
    if names is not None:
        want = {c: n for c, n in names.items() if len(c) == IND_DART_DIGITS}
        if {c: v["name"] for c, v in out.items()} != want:
            raise ValueError(f"!! {os.path.basename(path)} 의 코드 · 이름이 11차 표(소분류 {len(want)}개)와 달라요")
    return out


def load_ksic_map(map_path=IND_MAP_CSV, groups_path=IND_GROUPS_CSV):
    """관문이 따로 읽는 업종 표: (KSIC 접두어 → 그룹, 그룹 이름 집합). fetch_data.load_industry_tables 와 같은 파일."""
    with open(map_path, encoding="utf-8") as f:
        kmap = {r["ksic"].strip(): r["group"].strip() for r in csv.DictReader(f)}
    with open(groups_path, encoding="utf-8") as f:
        groups = {r["group"].strip() for r in csv.DictReader(f)}
    return kmap, groups


def ksic_prefix_group(code, kmap):
    """가장 긴 접두어의 그룹 (fetch_data.ksic_group 과 같은 규칙 · 관문은 따로 계산해요). 없으면 None."""
    code = (code or "").strip()
    for n in range(len(code), 1, -1):
        g = kmap.get(code[:n])
        if g:
            return g
    return None


def px_check_sample(codes, n=PX_CHECK_SAMPLE):
    """표본: 코드 순으로 늘어놓은 종목에서 고르게 n개 (같은 목록이면 늘 같은 표본 · 코스피 · 코스닥이 섞여요). (순수 함수)"""
    codes = sorted(set(codes))
    if len(codes) <= n:
        return codes
    step = len(codes) / n
    return [codes[int(i * step)] for i in range(n)]

# v17.5.1 (v18.0 Part A + 추가 4–9). 새 기준은 첫 실제 실행의 숫자를 보고 Jack 이 승인한 뒤 고정돼요.
# 영문자에 붙지 않은 nan·None… — 한글 옆도 잡아요 ("시가총액 nan억원"). \b 는 한글을 낱말 글자로 봐서 놓쳤어요.
BAD_WORD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")
KR_DEPTS = ("우량기업부", "중견기업부", "벤처기업부", "기술성장기업부", "관리종목(소속부없음)", "투자주의환기종목(소속부없음)")
PROD_SAME_MAX = 5.0      # '주요제품'이 업종 이름과 똑같은 국내 설명 비율 상한 (%) — 열이 밀린 사고는 100%였어요
D1_COVER = 95            # 국내 d1 채움 (%)
D1_MAX_KR = 30.0         # 한국 하루 가격 제한폭 — 넘는 값은 파이프라인이 빈 칸으로 둬요
# 국내 시계열의 공식 종가 고정 (2026-11-14 · Jack: "52주 숫자부터" · 새 줄만, 늦추는 줄 없음). 네이버 일봉은 수정주가예요 (분할 · 병합 ·
# 감자 · 무상증자 · 유상증자가 있으면 그 앞 봉을 모두 새 기준으로 고쳐 둬요). 그런데 최근 거래일들을 그날 목록 파일의 공식 종가(그날 기준)로
# 덮어서, 기준이 바뀐 날 앞 봉에 옛 기준 값이 들어갔어요 — 에쎈테크 · 인지디스플레(5:1 병합: 591 · 726원), STX(감자 뒤 기준가 3,530 → 18,360),
# 엘앤씨바이오(1:1 무상증자) · 코나아이(무상증자, 새 주식 상장 전) 들 18종목의 52주 최저 · 최고 · 낙폭 · 변동성 · 베타가 틀렸어요.
# 파이프라인(fetch_data.pin_why_not)은 이제 KRX 기준가로 그날과 오늘이 같은 기준인지 봐요: 목록 파일마다 기준가 = Close − Changes 가 바로 앞
# 파일의 공식 종가와 같으면 그 사이에 기준이 바뀌지 않은 거예요 (분할 · 병합 · 감자 · 권리락 날에는 KRX 가 기준가를 새로 정해요).
#   - 그날과 오늘 사이에 기준가가 바뀐 날이 있으면: 고치지 않아요 (네이버 봉 그대로).
#   - 모두 이어지면: 공식 종가가 네이버 봉과 PIN_PX_TOL 안이거나, 상장주식수가 오늘과 PIN_SHR_TOL 안이고 PIN_REF_TOL 안이면 고쳐요
#     (시간외 큰 움직임이 있던 날도 공식 종가로).
#   - 확인할 수 없으면 (파일 · 칸이 빠짐 · 사이에 빠진 거래일): 상장주식수가 오늘과 PIN_SHR_TOL 안이고 공식 종가가 네이버 봉과 PIN_PX_TOL 안일
#     때만 고쳐요. 무상증자는 권리락 날 값이 바뀌고 새 주식은 몇 주 뒤에 상장돼 그사이 주식 수가 같아서 (코나아이) 값도 봐요.
# 2026-11-13 (19거래일 · 2,474종목): 기준가가 바뀐 종목 18 (병합 · 감자 13 · 무상 · 유상증자 권리락 5) · 새로 상장 14 · 확인 못 한 연결 0 · 넥스트레이드
# 차이는 같은 기준 날의 99% 가 3.9% 안 · 가장 큰 시간외 하루 21.9%.
PIN_PX_TOL = 0.05        # 공식 종가 ↔ 네이버 봉 차이 상한 (비율) — 기준가로 확인하지 못한 날은 넘으면 고치지 않아요
PIN_SHR_TOL = 0.02       # 그날 상장주식수 ↔ 오늘 상장주식수 차이 상한 (비율) — 기준가로 확인하지 못한 날은 넘으면 고치지 않아요
PIN_REF_TOL = 0.30       # 기준가로 같은 기준임을 확인한 날 (주식 수도 같을 때): 공식 종가 ↔ 네이버 봉 차이 상한 — 시간외 큰 움직임까지
KR_DAY_LIMIT = D1_MAX_KR  # 한국 하루 가격 제한폭 (%) — 코스피 · 코스닥 (d1 줄과 같은 값 · 따로 바뀌지 않게)
# 2026-11-14 (Jack, design chat 2026-11-08 · dart-gaps §9 · 새 줄만, 늦추는 줄 없음): 기준일에 거래가 없던 한국 종목 (목록 파일의 거래량 0 · 시가 0 ·
# 거래대금 0)은 d1 이 0.00% 가 아니라 빈 칸이고 noTrade 표시를 달아요. 다른 이유로 빈 d1 은 d1Why 에 이유 (fetch_data.kr_no_trade · kr_d1_split):
# noTrade 거래 없음 · range ±30% 밖 · new 직전 거래일 행 없음 · prev 직전 거래일 파일을 쓸 수 없음 (그날 모든 종목). 파이프라인이 이 목록을 읽어요.
D1_WHY = ("noTrade", "range", "new", "prev")
NO_TRADE_SHOW = 12       # 값 칸에 적는 종목 수 (나머지는 수만 · 전체는 요약 목록에)
KONEX_DAY_LIMIT = 15.0   # 코넥스 하루 가격 제한폭 (%)
KR_JUMP_WHY = {"pin": "우리 고정이 만든 움직임", "halt": "거래정지 뒤 재개", "spike": "하루만 튄 봉", "other": "그 밖"}
# 2026-11-14 (Jack, Q2 (a) "this week" · 새 줄만, 늦추는 줄 없음): 하루 움직임이 가격 제한폭으로 설명되지 않는 종목(krSeries.jump)은 그 시계열로
# 만든 숫자를 모두 비워요 — 파이프라인(fetch_data.mark_px_bad)이 이 목록을 읽어요. data.json: 52주 최고 · 최저, 변동성, 베타와 그 표준오차 ·
# 쓴 날 수 · 알파, 1 · 3개월 · 3년 수익률, 1년 수익률(모멘텀), 샤프, 최대 낙폭, 상승 월 비율, 그리고 그 숫자로 매기는 추세(mz) · 저변동(lz) 점수.
# corp.json: build_corp 가 data.json 에서 옮겨 싣는 같은 칸. 그 종목에는 pxBad (가장 최근 움직임 날짜)를 달고, krSeries.hidden 에 코드를 적어요.
# 앱은 그 자리에 Jack 의 줄 "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워 두었어요." (시계열을 고치는 일은 다음 PR).
PX_BAD_DATA = ("hi", "lo", "vol", "beta", "betaSE", "betaN", "al", "r1", "r3", "r36", "mom", "sh", "mdd", "hit", "mz", "lz")
# (pxBad 리뷰 S1: build_corp 는 betaSE · betaN 을 CORP_DIV_KEYS 로도 옮겨요 — 두 길 모두)
PX_BAD_CORP = ("hi", "lo", "vol", "beta", "betaSE", "betaN", "r1", "r3", "r36", "sh", "mdd", "mz", "lz")
PX_BAD_SHOW = 10         # 값 칸에 적는 문제 · 종목 수 (나머지는 수만 · 전체는 요약 목록에)
# 2026-11-14 저녁 (Jack: "Old bad days: hide only the numbers whose calculation window includes the bad day"). 칸마다 계산 창 — fetch_data.fetch_korea ·
# perf_stats 의 실제 계산 그대로, 봉 수로 (짐작하지 않아요):
#   'y' 마지막 252봉: hi · lo (px.tail(252)) · mom (px[-1] ÷ px[-252], 252봉 넘을 때) · mz (mom 의 백분위)
#   'q' 마지막 64봉: r3 (px[-1] ÷ px[-64])
#   'm' 마지막 22봉: r1 (px[-1] ÷ px[-22])
#   그 밖은 시계열 전체 (약 3년 + 40일, fetch_data.YEARS): vol · beta · betaSE · betaN · al (일별 수익률 전체) · r36 (px[0]) · sh · mdd · hit (시계열 전체) ·
#   lz (vol 의 백분위). 움직임은 시계열 전체에서 찾으니 표시된 종목이면 이 칸들은 늘 비어요 (PX_BAD_ALWAYS).
# 그 창 안에 움직임 날짜(krSeries.jump 의 날짜 — 움직임이 일어난 봉)가 하나라도 있으면 그 창의 칸을 비워요. 비운 칸은 종목의 pxBadF 에 적어요.
PX_BAD_WIN = {"y": ("hi", "lo", "mom", "mz"), "q": ("r3",), "m": ("r1",)}
PX_BAD_WIN_BARS = {"y": 252, "q": 64, "m": 22}
PX_BAD_ALWAYS = tuple(k for k in PX_BAD_DATA if not any(k in v for v in PX_BAD_WIN.values()))
# 관문의 달력 점검 (파이프라인은 봉으로 정확히 · 관문은 거래일 달력이 없어서): 기준일(pxDate)에서 이 일수 안의 움직임은 그 창 안에 있어요 — 거래일은
# 한 주에 많아야 5일이라 251봉은 351일 · 63봉은 87일 · 21봉은 29일보다 짧을 수 없어요 (휴장일 · 네이버의 빈 날은 창을 더 길게만 해요). 그래서 이 안의
# 움직임이면 그 창의 칸은 꼭 비어 있어야 해요. 반대쪽(오래된 움직임이면 보여야 함)은 달력으로 말할 수 없어요 (거래정지로 빈 날이 있으면 252봉이 더
# 오래 거슬러 가요) — 대신 비우지 않은 52주는 있어야 해요.
PX_BAD_WIN_IN = {"y": 340, "q": 85, "m": 28}
# 필수 종목 (Jack, 2026-11-14 저녁: "warn when one is affected; block the publish when two or more must-haves are affected"): 표시가 맞는(px_bad_valid)
# 필수 종목이 하나면 '필수 종목 추세 · 저변동 순위' · '필수 종목 52주 최고·최저 (야후)' · '필수 종목 새 칸' 줄은 경고 (그 종목의 비운 칸만 넘겨요),
# 이만큼이면 실패. 표시 없이 빠지면 예전처럼 늘 실패 (11-05 배당 순위와 같은 틀).
PX_BAD_MUST_FAIL = 2
# 한 실행에 새로 생긴 움직임 종목 (Jack, 2026-11-14 저녁: "or when many stocks newly break in one run"): 오늘 krSeries.jump 에 있고 직전 발행본의
# jump 에는 없는 종목이 이만큼이면 실패. 근거: 2026-11-14 의 21개 움직임(18종목)은 지난 3년의 20개 날짜에 있고 한 날에 많아야 2종목
# (2026-05-08 에이프로젠 · 에이프로젠바이오로직스, 같은 그룹의 감자) — 날마다 실행했다면 새로 생긴 종목은 0~2. 10 은 그 5배예요. 그보다 많으면 출처
# (네이버 수정주가)나 우리 고정이 한꺼번에 깨졌을 수 있어요 (2026-11-13 의 고정 문제는 18종목을 한꺼번에 틀리게 했어요).
PX_BAD_NEW_FAIL = 10
US_D1_COVER = 98.0       # 미국 d1 채움 (%) — 아래면 실패 (Jack, 2026-11-07). 11-02 부터 매일 99.9~100%
US_D1_SHOW = 10          # 표의 값 칸에 적는 빠진 종목 수 — 전부는 로그와 실행 요약에 따로 적어요
VAL20_COVER = 95         # 국내 val20 채움 (%)
IDX_MIN_ROWS = 700       # 지수 이력 3년 ≈ 740 (한국) · 752 (미국) 거래일
IDX_MIN_DAYS = 3 * 365 - 30
HILO_TOL = 1.0           # 필수 종목 52주 최고·최저가 야후와 1% 안 (넘으면 경고)
HILO_FAIL = 3.0          # 3% 넘게 다르면 실패 — 252거래일 중 오래된 날은 아직 네이버 일봉이라.
# !! 임시 (Jack 승인 2026-11-01): v18.0 Part B 가 공식 종가 이력으로 바꾸면 1% 실패로 다시 조여요 (HILO_FAIL = HILO_TOL).
D1_YAHOO_TOL = 0.3       # 필수 종목 d1 이 야후 종가로 계산한 값과 0.3%p 안 (이틀치 변화를 잡아요)
DPS_DY_ODD_MAX = 1.0     # 주당 배당금 0 인데 배당수익률 > 0 (또는 반대) 인 국내 종목 비율 상한 (%)
# ETF 여부는 종목마다 직접 정해요 (fetch_data.py 와 따로 적어 같은 실수를 같이 하지 않게)
US_ETF_SET = {"SPY", "VOO", "QQQ", "SCHD", "VTI", "VT", "IVV", "DIA", "IWM", "SOXX", "SMH", "XLK", "XLF", "XLE", "XLV",
              "XLY", "XLP", "XLI", "TLT", "IEF", "SHY", "GLD", "IAU", "SLV", "JEPI", "JEPQ", "VYM", "ARKK", "MTUM", "QUAL",
              "VBR", "IVE", "SPHQ"}
US_COMPANY_SET = {"BRK-B", "TSM", "ASML", "BABA", "NVO", "SHOP", "AAPL", "MSFT", "NVDA"}
# 2026-11-14 (Jack, 2026-11-13 "Missing US stocks" · 더하기만): 손으로 더한 미국 회사 28곳 (fetch_data.EXTRA_US_ADDED 와 따로 적어요 · 테스트가 맞춰 봐요).
# 모두 회사 주식이라 위 줄(ETF 여부)이 etf false 를 봐요. 아래 두 줄이 더 봐요: 손으로 더한 종목(US_EXTRA_SET)은 목록에 있거나 빠진 이유가 있어야 하고
# (check_us_extra), 미국 상장 외국 회사(US_FOREIGN_SET)의 PER · PBR · 배당수익률은 파이프라인이 회사 합계와 맞춰 본 뒤에만 나가요 (check_us_foreign).
US_ADDED_SET = {"BTI", "ADC", "NNN", "MAIN", "WPC", "STAG", "EPR", "OHI", "ENB", "BCE", "TD", "RY", "SHEL", "BP", "UL", "TM", "SONY",
                "AZN", "HSBC", "SAP", "NVS", "RIO", "BHP", "TTE", "DEO", "BUD", "SAN", "GSK"}
US_COMPANY_SET |= US_ADDED_SET
US_EXTRA_SET = US_ETF_SET | {"BRK-B", "TSM", "ASML", "BABA", "NVO", "SHOP"} | US_ADDED_SET     # = fetch_data.EXTRA_US
# 2026-11-21 (Jack: "Yes, warn." · "one stock missing from a source never holds the publish"): 손으로 더한 종목이 목록에 없고 usExtraMissing 에도
# 없으면 경고 (이름을 적어요). 이런 종목이 이 수를 넘으면 한 종목이 빠진 것이 아니라 두 목록이 어긋났거나 기록이 깨진 것이라 발행 실패 (check_us_extra).
# Jack 의 상시 규칙 기본값 "more than 5" (2026-11-20) · 데이터 브랜치 발행 27번 (11-06 ~ 11-20 KST): 기록이 있는 11번 (11-14 부터) 모두 0곳 ·
# 그 전 16번은 그때 목록의 39곳 모두 있음 → max(5, 3 × 0) = 5. 그 16번 파일에는 11-14 에 더한 28곳이 없어요 (이 실패가 잡는 목록 어긋남의 모습).
US_EXTRA_QUIET_MAX = 5
# 2026-11-15 (Jack: "fix Brown-Forman B …" · 더하기만): S&P 500 목록(FinanceDataReader)이 점을 지운 주식 종류 티커 → 야후 대시 꼴
# (= fetch_data.US_CLASS_JOINED 의 바꾸기 · 따로 적어 테스트가 맞춰 봐요). 이 꼴은 야후에 없는 티커라 발행 목록에 있으면 안 돼요.
US_CLASS_JOINED_SET = {"BRKB": "BRK-B", "BFB": "BF-B"}
# 이 바꾸기로 새로 들어온 종목 (= fetch_data.US_CLASS_ADDED · BRK-B 는 EXTRA_US 로 이미 있었어요): 목록에 없으면 이름과 data.json
# usListSym.missing 의 빠진 이유를 적고 경고만 해요 (Jack 2026-11-20: "one stock missing from a source never holds the publish" ·
# check_us_share_class ①). 실패는 그 종목의 행이 목록에 있는데 가격이 없고 빠진 이유도 없을 때뿐이에요 (틀린 값이 보여요).
US_CLASS_SET = {"BF-B"}
US_FOREIGN_SET = {"BTI", "ENB", "BCE", "TD", "RY", "SHEL", "BP", "UL", "TM", "SONY", "AZN", "HSBC", "SAP", "NVS", "RIO", "BHP", "TTE",
                  "DEO", "BUD", "SAN", "GSK"}                                                     # = fetch_data.US_FOREIGN (더한 외국 회사)
US_FOREIGN_KEYS = ("per", "pbr", "dy")
US_FGN_WHY = ("mismatch", "currency")      # data.json fgnCut 의 값 (Jack 2026-11-14: 앱이 그 칸 '–' 밑에 이유 줄을 붙여요)
US_FGN_STOPPED = "검사가 멈춤"              # usForeign.cut 의 이유 머리말: 파이프라인 검사가 멈춰 비운 칸 (이유 줄 없음 · 그날은 경고) — fetch_data.US_FOREIGN_STOP_WHY
# 2026-11-14 (Jack, Q5 — 더하기만): 파이프라인은 외국 회사를 규칙으로 찾아 usForeign.set = {티커: [본사 나라, 재무제표 통화, 근거]} 로 적어요
# (fetch_data.us_foreign_set). 이 줄은 위 21곳에 그 회사들을 더해 같은 규칙(맞춰 본 숫자만 · 비운 칸 · 표시)으로 봐요. 근거 글자는 fetch_data.US_FGN_BASIS 와 같아요.
US_FGN_BASIS = ("fcur", "country", "adr", "floor", "prev", "error")   # prev: S&P 500 목록을 쓸 수 없던 날 어제 발행한 set 에서 이어 온 회사
US_SP500_MIN = 400       # S&P 500 목록이 오늘 미국 목록과 이만큼 안 겹치면 그 목록을 믿지 않아요 (본사 나라 규칙을 쓰지 않는 날 · 경고)
US_SP500_MAX = 550       # … 목록이 이보다 크면 (S&P 500 이 아닌 다른 목록이 온 날) 그것도 믿지 않아요 (리뷰 2차 N3)
# 2026-11-14 (리뷰 S1): 비운 칸의 종류. mismatch = 맞춰 봤는데 달라요 (순이익이 0 이하인데 야후 PER 이 양수인 것처럼 부호가 어긋난 것도) ·
# currency = 재무제표가 달러인지 확인되지 않음 (#126) · norecord = 배당 기록이나 가격을 읽지 못해 배당수익률을 맞춰 보지 못함 (파이프라인 쪽 자료가
# 빠진 날 · 리뷰 2차 S1) · nocompare = 회사 자기 숫자로 PER · PBR 을 맞춰 볼 수 없어요 (적자 · ROE 없음 — 야후 숫자가 맞을 수도 있어요).
# 아래 사유 글은 fetch_data us_foreign_cuts 가 쓰는 글 그대로예요 (관문이 이 글로 종류를 맞춰 봐요).
US_FGN_NOCMP_WHY = {"per": "맞춰 볼 시가총액 · 보통주 몫 순이익(netIncomeToCommon)이 없거나 순이익이 0 이하",
                    "pbr": "맞춰 볼 시가총액 ÷ 순이익 · ROE 가 없거나 0 이하"}
US_FGN_NOREC_WHY = "배당 기록(야후 다운로드의 Dividends 칸) · 가격을 읽지 못함"   # 배당수익률만 · 종류 norecord
US_FGN_NOREC = "norecord"
US_FGN_CUR_WHY = "재무제표 통화를 모름"     # currency 사유의 머리말 (fetch_data.US_FOREIGN_CUR_WHY)
# 스위치 하나 (Jack 에게 묻는 중, 2026-11-14: 회사 자기 숫자로 맞춰 볼 수 없는 PER · PBR 밑에 그 줄을 보일지). Jack 의 11-13 규칙 '맞춰 볼 값이 없으면
# 그 칸도 비워요 — 틀릴 수 있는 숫자보다 빈 칸' 은 "line" 이 지켜요: 이 값을 바꾸는 것은 안전 규칙 변경이에요 (Jack 의 '예' 와 따로 PR).
# 파이프라인과 관문이 이 값을 따르고, 앱은 파이프라인이 종목에 적은 종류(fgnCut)를 따라요:
#   "line" (지금) = 비우고 종목 표시 nocompare → 앱이 승인된 줄 co.fgnCut 을 붙여요 (#126 그대로)
#   "keep"        = 비우지 않아요 (야후 숫자가 그대로 보여요 · 표시 없음 · usForeign.kept 에 적어요) — 11-13 규칙을 PER · PBR 에서 풀어요
#   "own"         = 비우고 종목 표시 nocompare-own → 앱이 디자인 채팅의 새 줄 co.fgnNoCmp 를 붙여요 (그 줄이 copy 에 없으면 줄 없이 '–' 만 ·
#                   시험이 copy 의 줄을 요구해요). own → line 으로 되돌린 뒤에도 line 실행이 한 번 발행될 때까지 그 copy 줄은 두세요 (어제 파일의 표시)
# norecord · currency 는 이 스위치와 상관없이 늘 비워요.
US_FGN_NOCMP = "own"    # Jack, 2026-11-15 (Q8): "own" — 그 줄 "회사 전체 숫자와 비교할 수 없어서 이 숫자는 비워 두었어요." (co.fgnNoCmp) · 숫자는 그대로 비워요
US_FGN_NOCMP_KIND = {"line": "nocompare", "keep": None, "own": "nocompare-own"}
# 검사가 멈춘 날 비운 칸의 종류 (Jack, 2026-11-15 Q10: 그 칸 밑 줄 "오늘은 이 숫자를 확인하지 못해서 비워 두었어요." · co.fgnStopped). 이 칸 전 기록
# (nocmp 없음)은 예전처럼 표시 없이 비어 있어요 (그날 앱은 '자료가 없어요' 였어요).
US_FGN_STOPPED_KIND = "stopped"
US_FGN_HOME = {"united states", "united states of america", "usa", "us", "puerto rico"}   # 근거 country 인데 이 나라면 기록이 틀린 것 (fetch_data.US_HOME)
US_FGN_NAMED = {"TSM", "ASML", "BABA", "NVO", "SHOP"}    # Jack 이 이름으로 넓힌 회사: 목록에 있는데 set 에 없으면 경고 (규칙이 못 찾은 날)
KR_FUND_SET = {"088980", "415640", "094800"}              # 상장 인프라·부동산 펀드 (투자회사)
KR_COMPANY_SET = {"241520", "034830", "123890"}           # 같은 업종이지만 회사 (벤처캐피털·신탁회사)
# v17.5.1 PR 2: 업종 그룹 (ind · indName)
IND_MUST = {"005930": "semi", "000660": "semi", "005380": "auto", "000270": "auto",
            "105560": "bank", "086790": "bank", "034730": "holding", "003550": "holding"}
IND_UNGROUPED_MAX = 2.0  # 거래가 활발한(val20 ≥ 5억원) 국내 회사 주식 중 그룹 없는 비율 상한 (%)
IND_LIQUID_VAL20 = 5.0   # 억원
IND_GROUP_MIN = 5        # 시장마다 그룹 인원 하한 (비교에 쓰니까요) — 보통주만 세요
IND_US_COVER = 90.0      # 미국 회사 주식 중 그룹이 있는 비율 하한 (%) — 야후 업종 이름이 바뀌면 잡아요
IND_NOT_FIN = ("004800", "012630")    # 효성·HDC: 지주회사지 금융회사가 아니에요 (KSIC 649 함정)
FIN_INDS = {"bank", "insurance", "securities", "finance", "fin"}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=2y&interval=1d"
# v17.5.2 (Jack 승인 2026-11-02). 숫자는 2026-11-03 발행본 기준이에요.
US_CAP_COVER = 95.0      # 미국 회사 주식(ETF 빼고) 중 시가총액(cap > 0)이 있는 비율 하한 (%) — 그날 99.6%, 우선주 3개를 빼면 100%.
#                          파이프라인은 시가총액이 없다는 이유로는 아무것도 빼지 않으니, 야후가 시가총액을 안 보내면 여기서 실패해요.
DIV_COVER_KEYS = ("dps", "dy")   # 국내 주당 배당금·배당수익률 — 그날 둘 다 96.7%
DIV_COVER_DROP = 10.0    # 점 — 직전 발행본보다 이만큼 넘게 줄면 실패 (DART 일부 장애로 배당이 조용히 비는 것)
US_PREF_DROP_MAX = 10    # 우선주·예탁증서로 보고 미국 목록에서 뺀 종목 수 상한 (data.json usLeftOut.preferred) — 그날 3개 (STRC·GOOGM·GOOGN).
#                          파이프라인은 티커·이름·야후 종류로만 판단해요 (Jack, 2026-11-03). 많으면 그 규칙이 진짜 회사를 잡은 날이에요.
# v17.5.2 (Jack 승인 2026-11-03): 해외 기업(종목코드 9…)은 DART 금액이 원화가 아닐 수 있어 비워야 해요 (2026-11-03 발행본 20곳, 코오롱티슈진 PBR 9,085)
# 2026-11-12 (Jack): 원화가 아닌 재무제표 표시(corp.json stmtCur)를 직전 발행과 비교해요 (check_stmt_marks). 실패: 어제 표시가 있던
# 국내 회사(9… 가 아닌)가 오늘 표시를 잃고 금액이 차 있으면 (하나뿐이어도 — 달러 금액이 원으로 나가는 경우), 또는 절반 넘게 사라지면
# (DART 통화 칸을 못 읽은 날). 그 밖의 사라짐 · 국내 회사가 목록에서 빠진 날은 경고.
STMT_MARK_MIN = 3        # 직전 발행에 표시된 회사(오늘도 목록에 있는)가 이만큼 있을 때만 '절반' 비교
# 정말 원화로 바꿔 공시하는 국내 회사: {코드: "날짜 · 근거 (Jack 의 yes)"}. 여기 있는 회사는 표시를 잃어도 실패가 아니라 경고예요.
# 비어 있는 게 정상이에요 — 한 줄 더하는 것은 Jack 의 yes 가 있어야 해요 (tests/test_stmt_marks.py 가 지켜봐요).
STMT_WON_SWITCH = {}
FOREIGN_BLANK = ("per", "pbr", "eps", "bps", "vz")      # data.json·corp.json 모두 빈 칸 (vz 는 PBR 로 매긴 점수)
FOREIGN_ZERO_OK = ("dps", "dy", "dps3")                  # 빈 칸이거나 0 (0 = 배당 없음은 어느 통화로도 같은 뜻)
FOREIGN_BLANK_CORP = ("eq", "evE", "evR", "pcf")                          # corp.json 금액·금액으로 만든 배수
FOREIGN_BLANK_LISTS = ("rev", "op", "ni")                                 # corp.json 3개년 금액
# Jack, 2026-11-12 (새 줄, 더하기만): 미국 상장 회사 중 재무제표 통화가 달러가 아닌 곳 (data.json fcur = 야후 financialCurrency 의 ISO 코드,
# fetch_data.py US_FCUR_BLANK). 달러 주가 ÷ 그 통화 금액일 수 있는 PER · PBR · 배당수익률과 PBR 로 매긴 가치 점수가 빈 칸이어야 해요
# (0 도 남은 칸으로 봐요). fcur 가 있는 회사끼리의 일관성만 봐요 — 야후가 financialCurrency 를 주지 않아 fcur 가 없으면 이 줄은 실패하지 않아요.
US_FCUR_BLANK = ("per", "pbr", "dy", "vz")
# 배당수익률 0% (배당 없음)를 fcur 회사에도 남길지 — 파이프라인(fetch_data.py)이 이 값을 가져다 써요 (하나의 스위치). Jack, 2026-11-13: 남겨요,
# 단 야후 자료가 지난 12개월 배당 없음을 분명히 말할 때만 (fetch_data.py us_no_dividend_12m · 아니면 빈 칸). 관문은 그래서 0 만은 받아요
# (0 이 아닌 배당수익률은 언제나 실패). False 로 바꾸면 0% 도 늘 비우고 관문도 0 을 남은 칸으로 봐요.
US_FCUR_KEEP_ZERO_DY = True
US_FCUR_SHOW = 10        # 관문 값 칸에 적는 티커 수 (나머지는 rep.detail 에 모두)
# v19.1b (새 줄 — Jack 의 승인이 있어야 머지해요 · PR 의 '안전 규칙 변경'): 분할에 안전한 국내 배당 · 베타 표준오차 · 재무 경고 검사 기록.
# data.json 에 divCheck 가 있으면(v19.1b 파이프라인이 늘 써요) 아래 검사가 모두 돌아요. 없으면 v19.1b 전 데이터라 경고 한 줄만 —
# 단, 직전 발행본에 있었는데 빠졌으면 실패. 기준은 첫 시험 실행의 숫자를 Jack 이 보고 승인한 뒤 고정돼요.
DIV_STATUS = ("same", "adj", "nc", "nd", "zero")        # 그대로 · 맞춤 · 비교 불가 · 알 수 없음 · 배당 없음
SPLIT_FACTORS = (2, 2.5, 3, 4, 5, 10, 20, 25, 50, 100)  # 깨끗한 분할 배율 (fetch_data.py 와 같은 목록을 따로 적어요)
# 행 4 (배당한 국내 회사 중 오늘 수익률 dyt 를 확인한 비율, %) — Jack 2026-11-05: 배당 자료 구멍이 사이트 전체를 멈추면 안 돼요.
#   floor 아래 = 실패 · floor ~ seen 사이 = 경고 · seen 이상 = 통과. floor = seen − 10%p.
#   2026-11-06 시험 실행(run 42145175627, dart=full)에서 본 비율 89.1% (1,088 / 1,220) → 정수로 내림해 seen 89, floor 79
#   (Jack 2026-11-05: 본 비율을 정수로 내리고, floor = seen − 10).
#   파이프라인 로그(fetch_data.apply_div_basis)도 이 값을 읽어 같은 기준으로 크게 알려요.
DYT_COVER_BANDS = {"seen": 89.0, "floor": 79.0}
DIV_RANK_MISS_FAIL = 2   # 행 6: 배당 순위(dyt·dz)에서 빠진 필수 종목이 이만큼이면 실패. 1곳은 이름·이유와 함께 경고 (Jack 2026-11-05)
DIV_ADJ_MAX = 10.0       # 배당한 국내 회사 중 분할·무상증자로 맞춘(adj) 비율 상한 (%) — 넘으면 배율을 대량으로 잘못 읽은 날
DYT_MAX = 30.0           # 이보다 큰 배당수익률은 믿지 않아요 (파이프라인이 빈 칸으로 둬요)
DIV_TOL = 0.011          # dps3a = dps3 ÷ dpsF · dyt = dps3a[0] ÷ 종가 × 100 — 둘 다 소수 둘째 자리 반올림
BETA_SE_WILD = 0.5       # 이보다 큰 베타 표준오차는 '흔들리는 베타' (일별 3년 회귀는 보통 0.03~0.15 · 가격 이력이 깨진 종목은 0.5~0.9)
BETA_SE_WILD_MAX = 2.0   # 흔들리는 베타 종목 비율 상한 (%) — 몇 개는 진짜로 있어요(분할을 못 고친 이력). 많으면 계산이 틀린 날
BETA_SE_MED = (0.02, 0.2)   # 회사 주식(ETF 빼고) 베타 표준오차 중앙값의 범위 — 계산이 통째로 틀린 날을 잡아요
BETA_N = (250, 800)      # 베타에 쓴 일별 수익률 수. 아래 끝 = 파이프라인의 실제 최소(fetch_data.MIN_DAYS = 250: 그보다 적으면
                         # 베타·표준오차를 비워요 — 신규 상장은 베타 없이 발행). 위 끝: 3년 + 40일 창(1,135일)의 평일은 최대 812일
                         # (수익률 811), 휴장일(미국 평일 연 10일 안팎 · 국내 더 많음)을 빼면 미국 ≤ 약 783 · 국내는 그보다 적어요
FL_KEYS = ("cr", "icr", "l3", "imp")                    # 재무 경고 검사 (corp.json fl · flRan · flNa)
# '필수 종목 새 칸' 줄: 필수 종목은 언제나 data betaSE·betaN · corp flRan, 그리고 corp.json 의 배당 칸이 data.json 과 같아야
# 해요 (있으면 같은 값, 없으면 둘 다 없음 — 두 파일이 어긋나지 않게). 총액·주당순이익(cash3·eps3r)은 배당 순위에 든
# 필수 종목만 봐요 — 순위에서 빠진 종목의 배당 자료 구멍은 '필수 종목 배당 순위 (dyt·dz)' 줄이 1곳은 경고 · 2곳부터 실패로 알려요.
# (data 쪽 divSt·dps3a·dpsF 는 '국내 배당 분할 확인 칸' 줄이 모든 보통주에 대해 봐요.)
DATA_NEW_MUST = ("betaSE", "betaN")
CORP_NEW_MUST = ("flRan",)
CORP_MIRROR = ("divSt", "dps3a", "dpsF", "dyt", "dz")
CORP_NEW_MUST_AMT = ("cash3", "eps3r")
# v19.1f (2026-11-08 · 새 줄만, 늦추는 줄 없음): 손익 줄 (매출·영업이익·순이익)과 EPS 기준 (지배주주 몫). data.json 에 incCheck 가
# 있으면(v19.1f 파이프라인이 늘 써요) 아래 검사가 모두 돌아요. 없으면 v19.1f 전 데이터라 경고 한 줄만 — 직전 발행본에 있었는데
# 빠졌으면 실패. 2026-11-08 발행본(재읽기 전): 시총 상위 200 매출 88.4% · 영업이익 93.0% · 순이익 90.5%, 한화에어로스페이스 매출 없음.
INC_TOP_N = 200            # 손익 줄 채움을 보는 시가총액 상위 국내 회사 수 (보통주 · 해외 기업과 펀드 빼고 · 사업보고서 연도 fy 있는 곳)
# 손익 줄 채움 실패 기준 (%): 98% approved by Jack 2026-11-08 on condition of an April back-test; no April data exists; off (WARN only) until Jack decides.
# (98% 는 4월 데이터로 막지 않았는지 확인하는 조건으로 승인했는데, 저장소에 4월 데이터가 없어요 — Jack 이 정할 때까지 꺼 둠 · 경고만.)
# 켜면 시총 상위 200 의 매출·영업이익·순이익 중 하나라도 INC_TOP_FLOOR 미만일 때 발행을 막아요 (지금은 100% 가 아니면 경고만 · 빠진 회사
# 이름과 함께). 켜는 건 INC_TOP_FLOOR = INC_TOP_FLOOR_APPROVED 한 줄이에요. 2026-11-08 재읽기 시험 실행: 매출 100.0% · 영업이익 100.0% ·
# 순이익 99.5%.
#  - '올해' = 회사마다 가장 최근에 낸 사업보고서의 해 (corp.json fy · rev/op/ni 의 첫 칸). 달력의 해가 아니에요 — 새 사업보고서를 아직
#    안 낸 회사는 그 전 해 보고서로 세요 (파이프라인이 그 해 → 전 해 순서로 읽어요).
#  - 금융회사(은행·보험·증권·금융 지주)는 매출 요구에서 빼요 (영업수익을 매출로 세지 않아요): 재무제표에 매출 한 줄이 없고 (은행은
#    이자수익·수수료수익, 보험은 보험수익) 파이프라인이 영업수익을 만들어 읽지 않아서, 빼는 쪽이 지금 데이터로 정확해요. 영업이익·순이익은 세요.
INC_TOP_FLOOR_APPROVED = 98.0
INC_TOP_FLOOR = None
EPS_B = ("o", "s", "t")    # epsIn.b: 지배주주 몫(연결) · 별도 재무제표 · 연결인데 지배주주 줄 없음(전체)
EPS_P = ("ttm", "fy")      # epsIn.p: 최근 4개 분기 · 사업보고서 한 해
ICR_WARN_SHARE = 10.0      # 이자보상배율을 돌린 회사 중 경고(1배 미만) 비율이 이보다 크면 경고 (실패 아님 · 2026-11-07 옛 값은 약 25%)
CORP_FIN_SECS = ("bank", "insure", "broker")   # 업종 그룹(ind)이 없을 때 금융회사로 보는 corp.json 업종 (매출 줄이 없을 수 있어요)
# v19.1f (리뷰 2026-11-08 · 새 줄만, 늦추는 줄 없음): 파이프라인과 따로 적어요 (같은 실수를 같이 하지 않게 · 값이 같은지는 테스트가 봐요)
EPS_OWNERS_MIN = 95.0      # EPS 영수증 중 주주 몫(o) · 별도(s) 비율(%)이 이보다 낮으면 실패 (fetch_data EPS_BASIS_MIN 0.95 와 같아요)
PER_TOL, PBR_TOL = 0.06, 0.006   # PER 은 소수 첫째 · PBR 은 둘째 자리 반올림이라 (영수증으로 다시 나눈 값과의 차이)
PBR_WARN = 100.0          # 국내 PBR 이 이보다 크면 경고 (단위·통화가 틀렸을 수 있어요 — 아남전자 USD 를 원으로 읽어 PBR 964.92). PER 은 이익이
                          # 아주 작은 회사가 날마다 걸려서 (지엘팜텍 5,319.9 · 레인보우로보틱스 4,385.5) 보지 않아요 (리뷰 3)
EPS_REP_BAND = (0.67, 1.5)   # 사업보고서 한 해 EPS ÷ 재무제표 기본주당이익이 이 밖이거나 부호가 다르면 경고 (평균 주식 수가 달라 조금은 달라요)
STMT_AMT_KEYS = ("evE", "evR", "pcf", "cash3", "eps3r", "epsNi3", "nio3", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep")
# v19.1h (새 줄만 · Jack 의 답 2026-11-08 · PR 의 '안전 규칙 변경'): 배당 맞춤 이유 (data.json 종목의 dvWhy · divCheck.why).
# 주식 수가 바뀌어 배당을 다시 계산하려 한 국내 종목마다 DART 결정 공시로 찾은 결론이에요 (ok 다시 계산 · nf 공시 없이 다시 계산 ·
# filed 유상증자·사채가 설명해 공시 그대로 · nc-mismatch / nc-unexplained 다시 계산하지 않고 배당수익률을 숨김). 이 값들은 fetch_data.py 와
# 일부러 따로 적어요. 모양이 틀리거나 배율·날짜·숨김이 맞지 않으면 실패. nf · filed · nc-* · 조회 실패 · 스위치 꺼짐은 경고만 (이름을
# 적어요) — DART 장애가 발행을 막지 않게. divCheck.why 가 없으면 v19.1h 전 데이터라 경고 한 줄만 — 직전 발행본에 있었는데 빠지면 실패.
DVWHY_KINDS = ("split", "merge", "bonus", "reduce")   # 액면분할 · 주식병합 · 무상증자 · 주식병합으로 한 감자
DVWHY_ST = ("ok", "nf", "filed", "nc-mismatch", "nc-unexplained")
DVWHY_FX_KINDS = ("rights", "cb", "bw")     # 유상증자 · 전환사채 · 신주인수권부사채
DVWHY_TOL = 0.005        # 공시 사건 배율의 곱 = 그해 dpsF ± 0.5%
DVWHY_CLEAN_TOL = 1e-4   # 사건 하나의 배율은 깨끗한 분할 배율(SPLIT_FACTORS · 역수)과 이만큼 안
DVWHY_SAME = 0.10        # 10% 이하 변화는 이름 붙이지 않아요 · filed 의 여유 (fetch_data.SHARE_SAME 과 같은 값)
DVWHY_CB_FLOOR = 0.7     # 전환·행사가액의 하한 (발행 때의 70%) → 사채가 만드는 주식 수는 많아야 1/0.7 배
DVWHY_LOOKBACK_DAYS = 183   # filed 의 유상증자 결정은 사업보고서 말보다 이만큼 앞부터
# v19.1i (새 줄만 · 늦추는 줄 없음 · Jack 2026-11-14 item 5): 배당 기준 증명 (data.json 종목의 dvProof · divCheck.proof).
# 주식 수가 바뀐 뒤 오늘 주식 수 기준을 찾지 못해 숨겼던 배당수익률을 파이프라인이 되살릴 때마다 근거(배당 총액 · 주식 수 · 공시가 덮는 새 주식)를
# 적어요. 관문은 그 근거를 발행된 숫자로 다시 맞춰 봐요: 되살린 수익률이 배당 총액 ÷ 시가총액과 맞는지 (자기주식 · 공시된 새 주식만큼만
# 다를 수 있어요). 맞지 않으면 우리 계산이 틀린 것이라 실패. 숨긴 종목 · 배당 표가 어긋난 종목 · 조회 실패는 경고만 (이름을 적어요).
# divCheck.proof 가 없으면 v19.1i 전 데이터라 경고 한 줄만 — 직전 발행본에 있었는데 빠지면 실패. fetch_data.py 와 일부러 따로 적어요.
PROVE_TOL = 0.03         # 배당 받은 주식 수 · 오늘 주식 수 맞춤의 여유 (± 3%)
PROVE_DRIFT = 0.15       # 앞 해: 두 해의 배당 받은 주식 수 비가 그 사이 사건의 곱 ± 15% (fetch_data.DRIFT_TOL — 자기주식 매입·소각)
PROVE_HOW = ("today", "yearEnd")
PROVE_KEYS = ("today", "yearEnd", "years", "line", "ratio", "basis", "rights", "uncounted", "data", "fail")
PROVE_HID = PROVE_KEYS[3:]   # 되살리지 않은 이유 (이름 목록 · line 은 Jack 의 줄이 붙는 종목: dvWhy nc-unexplained)
PROVE_HID_KO = {"line": "주식 수가 바뀌었는데 공시 없음 (Jack 의 줄)", "ratio": "깨끗하지 않은 공시 배율", "basis": "회사분할 · 주식배당",
                "rights": "주주배정 유상증자 (권리락)", "uncounted": "수를 읽지 않는 공시", "data": "배당 표가 어긋남", "fail": "조회 실패"}
PROVE_EPS = 0.002        # 반올림 여유 (dps3a 원 둘째 자리 · 총액 원 단위)
# v19.1j — 안전 규칙 변경 (늦춤 · Jack 의 분명한 yes, 2026-11-15 답 12: "accepting exact non-whole bonus ratios from the filing when the
# share counts confirm them, with the reviewer's three guards"). 깨끗한 분할 배율만 받던 두 규칙(_factor_ok 의 dpsF · v19.1h _dvwhy_clean 의 사건
# 배율)이 이 경우에만 깨끗하지 않은 배율을 받아요 (exact_bonus_problem 이 None 인 종목): (가) 깨끗하지 않은 배율의 사건은 모두 무상증자 —
# k bonus · x(1주당 신주 수) > 0 · r = 1 + x ± 1e-6 (파이프라인은 무상증자 사건을 fricDecsn · pifricDecsn API 에서만 만들어요) · (나) 그 배율의
# 해마다 사건의 곱(무상증자는 1 + x 로)이 dpsF 와 1e-6 안 · (다) dvWhy ok 와 dvProof 검사(아래 dvproof_problems)를 모두 지나고, 그 해를 이번
# 증명이 되살렸어요 (올해 dvProof.y0 · 앞 해 dvProof.yrs). 그 밖의 깨끗하지 않은 배율 — 파이프라인이 주식 수로 짐작한 배율 · 사건이 없거나
# 무상증자가 아닌 사건 · 곱이 1e-6 넘게 다름 · dvProof 없음 — 은 예전과 똑같이 실패해요.
EXACT_TOL = 1e-6
# v19.1j (Jack 2026-11-15 답 11 · 13 · 2026-11-19 · 새 줄만): 숨긴 배당수익률의 줄 — 종목의 dvLine 2 · 3 · 4 는 divCheck.proofSub(rights · data 안의 경우)와
# 꼭 맞아요. fetch_data.py 와 같은 값을 따로 적어요. data 의 other (리뷰 2026-11-19) = 파이프라인이 이름을 붙이지 않은 배당 표 이유 — 줄이
# 있으면 실패 (PROVE_SUB_LINE 에 없어요), 있기만 해도 그 줄이 경고 (새 이유 글에 이름을 붙일 때까지 이유를 말하지 않는 종목).
PROVE_LINE = {"line": 1, "rights": 2, "data": 3, "missing": 4}
PROVE_SUB = {"rights": ("sh", "shnew", "unk"),
             "data": ("div", "pref0", "neg", "nototal", "prefmix", "nopfo", "nostk", "noshr", "other")}
PROVE_SUB_LINE = {"rights": {"sh": 2}, "data": {"div": 3, "nototal": 4, "nostk": 4, "pref0": 4, "nopfo": 4, "prefmix": 4}}   # 경우 → 줄 (Jack 2026-11-19: 4)
PROVE_SUB_KO = {"sh": "주주배정 (새 주식 상장됨)", "shnew": "주주배정 (새 주식이 아직 상장 전)", "unk": "방식을 모르는 결정만", "div": "총액 ÷ 주당 배당이 주식 수와 다름", "pref0": "우선주 배당 줄이 있는데 주식의 총수 현황에 우선주 수가 따로 없음",
                "neg": "총액이 우선주 몫보다 작음", "nototal": "총액 없음", "prefmix": "주당 배당이 다른 종류주가 섞임", "nopfo": "우선주 주식 수 모름",
                "nostk": "그해 말 주식의 총수 현황 없음", "noshr": "오늘 상장 주식 수 없음", "other": "이름을 붙이지 않은 배당 표 이유"}
# ── Jack 의 상시 규칙 (2026-11-19 ~17:45 KST · 우리 처리를 보는 검사) ── Jack, verbatim: "Standing rule for checks on our own processing: a
# single bad row is dropped or blanked with a loud warning and the rest publishes. Block only when many rows fail in one run (set the number
# from recent runs and show it in the PR) or when a value would show a wrong number."
# 나쁜 행을 고르는 함수는 이 파일에 하나씩 (us_class_bad_rows · div_line_bad_rows). 파이프라인(fetch_data.py)은 같은 함수를 메모리의 데이터에
# 돌려 그 행을 빼거나(미국 행) 비우고(dvLine) 크게 남기며, data.json ownDrop[열쇠] = {"n": 수, "rows": [[열쇠, 이유]] 앞 OWN_DROP_SHOW 개} 에
# 적어요. 관문: 실패는 둘뿐 — n 이 그 검사의 N 을 넘음 (한 실행에서 많은 행이 틀림) · 빼야 할 값이 파일에 남아 틀린 숫자나 틀린 이유 줄을
# 보임 (빼는 단계가 고장). 1~N 이면 그 행 이름과 경고 · 0 이면 그대로. ownDrop 에 그 열쇠가 없는 파일 (이 규칙 전): 그 줄은 예전 규칙 그대로.
# 소스가 보내는 것을 보는 검사 (신선도 · 덮는 비율 · 두 출처 · 필수 종목)는 그대로예요. #139 의 'BF-B 가 있거나 빠진 이유' 줄은 Jack 의 답
# (2026-11-20, verbatim: "Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish.")으로 BF-B 가
# 목록에 없으면 경고예요 (check_us_share_class ① · 실패는 목록에 있는 행에 가격이 없을 때뿐).
# N = max(5, 3 × 최근 발행본에서 본 가장 큰 수): data 가지의 최근 발행 25회 (2026-11-06 ~ 11-19)를 같은 함수로 다시 돌린 표는 PR 에 있어요
# (두 검사 모두 25회 내내 0건 → N = 5).
OWN_DROP_SHOW = 30                 # 기록 · 로그 · 관문 값 칸에 이름을 적는 행 수
US_CLASS_DROP_KEY = "usClass"      # #139: S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 실림 · 관문 표와 다르게 바꾼 티커 → 미국 행을 빼요
US_CLASS_DROP_MAX = 5              # N (PR 의 표: 최근 발행 25회 모두 0)
DIV_LINE_DROP_KEY = "divLine"      # #142: 기록(proofSub)과 맞지 않는 숨긴 배당수익률의 줄 (dvLine 2 · 3 · 4) → 그 종목의 줄을 비워요
DIV_LINE_BLANK_MAX = 5             # N (PR 의 표: 최근 발행 25회 모두 0)
DIV_LINE_OF = {v: k for k, m in PROVE_SUB_LINE.items() for v in m.values()}   # 줄 → 그 줄을 정하는 기록 (2 rights · 3 · 4 data)
# v19.6a (새 줄만 · 늦추는 줄 없음 · docs/tasks/v19.6-records-alerts-dark.md Part I.1 · A.6): macro.json fxHist (원/달러 일별 환율 2016~)
# 와 data.json splits (2016 년부터의 미국 주식 분할). 앱(v19.6a)은 새 미국 기록에 그 날짜의 환율을 저장하고(fxHist), 분할 전 기록을 새 주식
# 수로 맞춰 읽어요(splits). 둘 다 사용자 기록에 영구히 남는 값이라 모양이 틀리면 실패. fxHist 가 없으면 경고 (앱이 지난 날짜의 미국 기록을
# 받지 않고 승인된 줄로 알려요 — 틀린 숫자가 아니에요). splits 는 직전 발행본에 있었는데 빠지거나, 한 번 실은 분할이 사라지거나 배율이
# 바뀌면 실패 (분할 전 기록의 주식 수가 바뀌어 보여요). 파이프라인(fetch_data.py)은 아래 기준값을 읽어 같은 선으로 판단해요 (검사 코드는 따로).
FX_HIST_FROM = "2016-01-01"     # 앱이 환율을 찾는 첫날 (src/v2/records.js FX_FROM) — 그 전 날짜의 미국 기록은 환율 없이 저장돼요
FX_HIST_FIRST_BY = "2016-01-08" # 첫 줄은 2016년 첫 주 안이어야 해요 (앞이 잘린 이력이면 2016년 뒤 날짜의 기록이 환율 없이 저장돼요)
FX_HIST_SOURCES = ("ecos_next", "ecos_close", "ecos", "yahoo_next")   # fetch_data.FX_HIST_SOURCE (Jack 의 선택 2026-11-13: ecos_close):
#                                 다음 날 매매기준율 · 15:30 종가 · 그날 매매기준율 (ECOS) · 야후 다음 봉 시가 — 무엇을 뜻하는지는 fetch_data.py 와 RUNBOOK
# 약속 (모든 출처): fxHist 의 줄은 asOf 와 그 전 날짜에만 말해요. 앱은 asOf 뒤 날짜를 받지 않아요 — 오늘만 예외 (신선한 data.json fx).
FX_HIST_ECOS = ("ecos_next", "ecos_close", "ecos")
FX_HIST_GAP_MAX = {"ecos_next": 14, "ecos_close": 14, "ecos": 14, "yahoo_next": 7}   # 줄 사이 달력 날짜 상한. ECOS (한국 영업일)
#                                 2016-01 ~ 2026-11 가장 긴 것 11일 (2017-09-29 → 10-10 추석 연휴) · 야후 (런던 거래일) 가장 긴 것 5일 (2025 부활절)
FX_HIST_JUMP = 10.0             # 줄 사이 변화 상한 (%) — 2016-01 ~ 2026-11 가장 큰 날: ECOS 3.42% (2020-03-20) · 야후 3.4%. 넘으면 깨진 값
FX_HIST_REL = 0.10              # 마지막 줄 값 ↔ data.json fx 차이 상한 (10%). 출처·시각이 달라 같지 않아요 (ECOS ↔ 야후 미국 하루 끝: 중앙값
#                                 0.25~0.42% · 가장 큰 날 4.35%). 이 줄은 엉뚱한 시계열(다른 통화 · 오래 멈춘 값)을 잡는 줄이고, 단위가 틀린 값
#                                 (100엔 · 위안 · 역수)은 범위 900~2,000 이 잡아요 — 5% 로 두면 큰 날 하나에 발행 전체가 막힐 수 있어요 (#117 리뷰 2)
FX_HIST_ECOS_TAIL = 14          # 휴장일 표가 덮지 못하는 날: ECOS 이력의 마지막 날이 발행일보다 이만큼 넘게 오래면 경고. 표가 덮으면 영업일로 봐요
#                                 (ecos · ecos_close: 발행일 전 마지막 한국 영업일 · ecos_next: 그 전 영업일 — 그보다 앞이면 경고)
SPLITS_FROM = "2016-01-01"      # splits 는 2016-01-01 부터 (fxHist 와 같은 첫날 · data.json splitsFrom) — 앱은 그 전 날짜의 기록을 맞추지 못해요
SPLIT_R = (0.001, 1000.0)       # 앱(src/v2/held.js okSplit)이 읽는 배율 범위 — 밖이면 앱이 그 줄을 버려요 (배율 1 도)
SPLIT_SIMPLE_MAX = 20           # 배율은 기약분수 p/q 에서 min(p, q) ≤ 20 인 '깨끗한' 값만 (10:1 · 1:15 · 3:2 · 105:100 = 21:20 주식배당).
#                                 야후는 분사(spin-off)도 분할 칸에 1253:1000 (GE · GE 버노바 분사) 같은 가격 조정 배율로 적어요 — 주식 수가
#                                 바뀐 게 아니라서 앱이 쓰면 사용자 주식 수가 늘어 보여요. 깨끗하지 않은 진짜 사건(병합 + 분사를 한 날 한 HLT ·
#                                 RYAAY ADS 비율 변경 …)은 파이프라인의 고정 표(fetch_data.SPLIT_OVERRIDES)로 넣고 splitsInfo.fixed 에 실어요
SPLIT_CLEAN_TOL = 1e-9          # 깨끗한 분수와의 차이 허용 (배율 × 이 값 · 파이프라인도 이 값을 읽어요)
SPLIT_FRESH_MAX_DAYS = 5        # splitsAsOf (야후에서 마지막으로 새로 읽은 날) 가 발행일보다 이만큼 넘게 오래면 큰 경고 — 실패 아님
                                # (Jack, 2026-11-13: 작은 출처 장애가 모두의 데이터 발행을 막으면 안 돼요). 없거나 오늘 뒤면 실패.
SPLIT_NEW_OLD_DAYS = 7          # 어제 목록에 없던 분할이 이보다 오래된 날짜로 새로 나오면 경고 (어제 2016 년부터 읽은 종목만)
SPLIT_NEAR_DAYS = 30            # 한 종목에 분할이 이 기간 안에 둘이면 경고 (야후가 같은 분할의 날짜를 옮겨 적었을 수 있어요 · QQQ 10-15/10-16)
# 꼭 있어야 할 분할 (야후 날짜 · 2026-11-13 확인): 2016 년부터의 이력을 읽지 못하면 실패해요
MUST_SPLITS = (("AAPL", "2020-08-31", 4.0), ("TSLA", "2020-08-31", 5.0), ("TSLA", "2022-08-25", 3.0), ("NVDA", "2021-07-20", 4.0),
               ("NVDA", "2024-06-10", 10.0), ("AMZN", "2022-06-06", 20.0), ("GOOGL", "2022-07-18", 20.0), ("WMT", "2024-02-26", 3.0),
               ("CMG", "2024-06-26", 50.0), ("HLT", "2017-01-04", 1 / 3))
# 공시 단위 확인 (Jack 2026-11-13 · 새 줄만, 늦추는 줄 없음): 단위를 잘못 적은 재무제표 (진코스텍 · 디와이에이 2026 반기보고서 — '천원'이라
# 적고 숫자는 원이라 DART 금액이 1,000배 → PER·PBR 0.0 · 가치 점수 100). 파이프라인(fetch_data.unit_guard)이 걸린 회사에 unitChk(이유 목록)를
# 달고 재무제표로 만든 숫자를 비워요. 관문: unitChk 회사에 비운 칸이 남으면 실패 · unitChk 없이 PBR 이 UNIT_PBR_LOOK 미만인 국내 회사는
# 이름과 함께 경고 (사람이 공시를 확인해요). 파이프라인과 따로 적어요 (같은 실수를 같이 하지 않게).
# 리뷰 #118 (새 줄만): 확인 기록 unitChkCover 가 직전 발행본에 있었는데 없으면 실패 · 그 hit 가 unitChk 종목 수와 다르면 실패 (둘 다 바깥
# 장애로는 생기지 않아요 — check_unit_ran) · 걸린 회사가 직전 발행본과 달라지면 이름과 함께 경고 (check_unit_moved) · 그중 새로 걸린 회사가
# UNIT_NEW_FLAGS_FAIL 곳 이상이면 실패 (Jack 2026-11-13).
UNIT_WHY = ("bs", "scale", "is", "cf", "eps", "cap")   # bs 자산 ≠ 부채 + 자본 · scale 보고서 사이 배율 · is · cf 분기 보고서의 지난해 칸 ·
#                                                         eps 재무제표의 기본주당이익 · cap 자본금 ÷ 액면가 (fetch_data.unit_check)
UNIT_PER_LOOK = 0.1                         # 리뷰 #116: PER 도 같은 경고 줄 (손익계산서만 단위가 틀리면 PBR 은 멀쩡해요) — 확인 목록은 아직 없어요
UNIT_BLANK_DATA = ("per", "pbr", "eps", "bps", "roe", "debt", "opm", "g3", "vz", "qz")       # data.json 종목 · corp.json 회사 모두
UNIT_BLANK_CORP = ("eq", "evE", "evR", "pcf", "nio3", "nio3Hyb", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "fl", "flSrc", "flWhy")
UNIT_BLANK_LISTS = ("rev", "op", "ni")      # corp.json 3개년 금액
UNIT_PBR_LOOK = 0.1
UNIT_MOVE_SHOW = 10                         # 리뷰 #118 S1: 바뀐 회사 이름은 앞에서부터 이만큼 (나머지는 수만 · 전체는 요약 목록에)
UNIT_NEW_FLAGS_FAIL = 20                    # Jack, 2026-11-13 (Q5): 한 번에 20곳 이상 새로 걸리면 실패 — 우리 읽기가 깨졌을 가능성이 커요
# PBR 이 UNIT_PBR_LOOK 미만이지만 사람이 공시를 보고 확인한 회사 (docs/RUNBOOK.md '확인한 낮은 PBR 회사'). 경고 줄은 매일 아침 확인(09:13)이
# Jack 에게 알려서, 확인된 회사를 날마다 다시 부르지 않게 해요. 그 회사의 지금 주주 몫 자본(corp.json bpsIn.eq, 억원)이 확인한 값의
# ±PBR_LOW_BAND 안이고 unitChk 가 없을 때만 조용히 넘겨요 (값 칸에 '확인된 회사 N곳 조용히 넘김'으로 수를 남겨요). 밖이거나 목록에 없는
# 회사는 예전처럼 이름과 함께 경고. 실패 줄과는 상관없어요 (이 목록은 경고만 조용히 해요). 목록과 회사마다 Jack 의 승인이 필요해요 (회사 하나를
# 경고에서 빼는 일이라 안전 규칙 변경 · RUNBOOK) — 목록과 아래 두 곳: Jack's yes, 2026-11-13.
PBR_LOW_CHECKED = {
    "040610": {"date": "2026-11-13", "eq": 5085.1, "yes": "Jack's yes, 2026-11-13",
               "why": "SG&G · 관계기업투자 5,007억 · 공시 rcept 20260814001690 (2026 반기, 단위 원) · 20260319000627 (2025 사업보고서) 확인"},
    "109960": {"date": "2026-11-13", "eq": 3617.6, "yes": "Jack's yes, 2026-11-13",
               "why": "앱토크롬 · 기타 비유동 금융자산 2,155억 · 공시 rcept 20260813001440 (2026 반기, 단위 원) · 20260320000910 (2025 사업보고서) 확인"},
}
PBR_LOW_BAND = 0.20
# 공시 단위 고침 (리뷰 #116 R3 · 새 줄만): 파이프라인(fetch_data.unit_fix_quarter)이 단위를 잘못 적은 분기 보고서를 표마다 나눠 쓴 회사 —
# corp.json unitFix [{rep "2026.2Q", bs · is · cf: 1000 · 1000000}]. 모양이 틀리거나 공시 단위 확인(unitChk)과 같이 있으면 실패, 고친 회사는 이름 ·
# 보고서 · 배수와 함께 경고 (사람이 공시를 보게). UNIT_FIX_CHECKED 에 같은 보고서 · 배수로 적힌 회사만 조용히 — 목록과 회사마다 Jack 의 승인이
# 필요해요 (RUNBOOK "Companies read with a corrected unit" · 비어 있어요).
UNIT_FIX_K = (1000, 1000000)
UNIT_FIX_PARTS = ("bs", "is", "cf")
UNIT_FIX_CHECKED = {}


# ── 결과 표 ─────────────────────────────────────────────────
class Report:
    def __init__(self):
        self.rows = []
        self.details = []     # (제목, [항목…]) — 값 칸에 다 들어가지 않는 목록. 로그와 실행 요약에 표 아래로 적어요

    def detail(self, title, items):
        self.details.append((str(title), [str(x) for x in items]))

    def add(self, name, ok, value, threshold, warn=False):
        st = "FAIL" if not ok else ("WARN" if warn else "PASS")
        self.rows.append((name, str(value), str(threshold), st))
        return ok

    def skip(self, name, why):
        self.rows.append((name, "—", why, "SKIP"))

    def pct(self, name, value, minimum):
        """value ≥ minimum (퍼센트). 2점 안쪽이면 경고."""
        return self.add(name, value >= minimum, f"{value:.1f}%", f"≥ {minimum}%",
                        warn=value < minimum + NEAR and value < 100.0)

    @property
    def failed(self):
        return [r for r in self.rows if r[3] == "FAIL"]

    @property
    def warned(self):
        return [r for r in self.rows if r[3] == "WARN"]

    def table(self):
        w = [max(len(r[i]) for r in self.rows + [("검사", "값", "기준", "결과")]) for i in range(3)]
        lines = [f"{'검사'.ljust(w[0])}  {'값'.ljust(w[1])}  {'기준'.ljust(w[2])}  결과", "-" * (sum(w) + 12)]
        lines += [f"{a.ljust(w[0])}  {b.ljust(w[1])}  {c.ljust(w[2])}  {d}" for a, b, c, d in self.rows]
        return "\n".join(lines)

    def markdown(self):
        out = ["| 검사 | 값 | 기준 | 결과 |", "|---|---|---|---|"]
        out += [f"| {a} | {b} | {c} | {'**FAIL**' if d == 'FAIL' else d} |" for a, b, c, d in self.rows]
        for title, items in self.details:
            out += ["", f"**{title}** ({len(items):,}): " + ", ".join(items)]
        return "\n".join(out)


# ── 엄격한 JSON ─────────────────────────────────────────────
def strict_loads(text, name):
    """NaN·Infinity 가 하나라도 있으면 실패 (브라우저가 파일 전체를 거부하니까요)."""
    def bad(tok):
        raise ValueError(f"{name} 안에 {tok} 값이 있어요")
    return json.loads(text, parse_constant=bad)


def num(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def day(s):
    return dt.date.fromisoformat(str(s)[:10]) if s else None


def is_day(s):
    """YYYY-MM-DD 로 읽히는 값인지 (읽지 못하면 False — 경고만 하는 검사가 관문을 멈추지 않게)."""
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s)[:10])) and day(s) is not None
    except ValueError:
        return False


# ── KRX 특별 거래시간 표 (v17.5.4, fetch_data.py 와 별개 구현) ──
def load_special_sessions(path=SPECIAL_CSV):
    """data/krx_special_sessions.csv → {날짜: (개장, 마감, 종류)}. 마감이 늦는 날만 최종본 기준이 늦어져요.
    이상한 줄이 하나라도 있으면 RuntimeError (줄 번호와 함께) → 관문은 최종본을 판단하지 못해 실패해요."""
    name = os.path.basename(path)
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f, restkey="_more")
        if rd.fieldnames != SPECIAL_COLS:
            raise RuntimeError(f"{name} 머리줄 {rd.fieldnames} — {','.join(SPECIAL_COLS)} 이어야 해요")
        for r in rd:
            where = f"{name} {rd.line_num}번째 줄"
            if "_more" in r or any(v is None for v in r.values()):
                raise RuntimeError(f"{where}: 칸 수가 머리줄과 달라요 (쉼표가 섞였는지 확인)")
            v = {k: r[k].strip() for k in SPECIAL_COLS}
            if not re.fullmatch(r"20\d\d-[01]\d-[0-3]\d", v["date"]) or not all(re.fullmatch(r"[0-2]\d:[0-5]\d", v[k]) for k in ("open", "close")):
                raise RuntimeError(f"{where}: 날짜 YYYY-MM-DD · 시각 HH:MM 이어야 해요 ({v['date']} {v['open']} {v['close']})")
            try:
                d = dt.date.fromisoformat(v["date"])
                op, cl = dt.time.fromisoformat(v["open"]), dt.time.fromisoformat(v["close"])
            except ValueError as e:
                raise RuntimeError(f"{where}: 날짜·시각을 읽을 수 없어요 ({e})") from None
            if d in out:
                raise RuntimeError(f"{where}: {d} 가 두 번 있어요")
            if d.weekday() >= 5:
                raise RuntimeError(f"{where}: {d} 는 주말이에요")
            if op >= cl:
                raise RuntimeError(f"{where}: 개장 {op:%H:%M} 이 마감 {cl:%H:%M} 보다 앞이어야 해요")
            if cl < NORMAL_CLOSE:
                raise RuntimeError(f"{where}: 마감 {cl:%H:%M} 이 보통 마감 {NORMAL_CLOSE:%H:%M} 보다 일러요 — 최종본 기준이 느슨해져서 못 받아요")
            if v["kind"] not in SPECIAL_KINDS:
                raise RuntimeError(f"{where}: kind '{v['kind']}' — {'·'.join(sorted(SPECIAL_KINDS))} 중 하나여야 해요")
            if not v["reason"] or not v["source"]:
                raise RuntimeError(f"{where}: reason·source 가 비었어요 (출처 없는 줄은 받지 않아요)")
            out[d] = (op, cl, v["kind"])
    return out


def load_holidays(path=HOLIDAYS_CSV):
    """data/market_holidays.csv → ({"KR": {날짜}, "US": {날짜}}, 표가 덮는 마지막 날). 이상한 줄이면 RuntimeError (줄 번호와 함께)."""
    name = os.path.basename(path)
    out = {"KR": set(), "US": set()}
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f, restkey="_more")
        rd.fieldnames = [c.strip() for c in (rd.fieldnames or [])]      # fetch_data 와 같은 파일을 받아요 (머리줄 공백)
        if rd.fieldnames != HOL_COLS:
            raise RuntimeError(f"{name} 머리줄 {rd.fieldnames} — {','.join(HOL_COLS)} 이어야 해요")
        for r in rd:
            where = f"{name} {rd.line_num}번째 줄"
            if "_more" not in r and not any((v or "").strip() for v in r.values()):
                continue                                              # 빈 줄(,,,)은 건너뛰어요 (fetch_data 와 같아요)
            if "_more" in r or any(v is None for v in r.values()):
                raise RuntimeError(f"{where}: 칸 수가 머리줄과 달라요")
            v = {k: r[k].strip() for k in HOL_COLS}
            if not re.fullmatch(r"20\d\d-[01]\d-[0-3]\d", v["date"]) or v["market"] not in out or not v["name"] or not v["source"]:
                raise RuntimeError(f"{where}: 날짜 YYYY-MM-DD · market KR/US · 이름·출처가 있어야 해요 ({','.join(v.values())[:80]})")
            d = dt.date.fromisoformat(v["date"])
            if d.weekday() >= 5 or d in out[v["market"]]:
                raise RuntimeError(f"{where}: {d} 는 주말이거나 두 번 있어요")
            out[v["market"]].add(d)
    years = sorted({d.year for m in out.values() for d in m})
    if not years or years != list(range(years[0], years[-1] + 1)) or any(
            sum(1 for d in out[m] if d.year == y) < HOL_MIN_PER_YEAR for m in out for y in years):
        raise RuntimeError(f"{name}: 해마다 한국·미국 줄이 {HOL_MIN_PER_YEAR}개 이상 있어야 해요 (적힌 해: {years})")
    out["start"] = dt.date(years[0], 1, 1)
    return out, dt.date(years[-1], 12, 31)


def expected_next_pub(px, usd, hol, end):
    """다음 발행 예정일 = 한국·미국 중 먼저 오는 다음 거래일의 다음 날 (fetch_data.next_publish 와 따로 구현).
    표가 덮지 않는 날은 평일 규칙으로 봐요 (fetch_data 와 같아요)."""
    firsts = []
    for start, closed in ((px, hol["KR"]), (usd, hol["US"])):
        d = start + dt.timedelta(days=1)
        while d.weekday() >= 5 or (end is not None and d <= end and d in closed):    # 표 밖은 평일 규칙
            d += dt.timedelta(days=1)
        firsts.append(d)
    return min(firsts) + dt.timedelta(days=1)


def final_cut(d, special):
    """그날 목록 파일의 마지막 커밋이 이 시각(KST) 이후여야 최종본 = 그날 마감(표에 없으면 15:30) + 30분."""
    s = special.get(d)
    return dt.datetime.combine(d, s[1] if s else NORMAL_CLOSE, KST) + FINAL_AFTER


def csat_missing(today, special):
    """9월 1일(KST)부터 올해 수능일 줄이 표에 없으면 True — 표가 소리 없이 끝나지 않게."""
    if (today.month, today.day) < CSAT_CHECK_FROM:
        return False
    return not any(d.year == today.year and v[2] == "수능" for d, v in special.items())


def csat_blocks(today, special):
    """11월 1일(KST)부터도 올해 수능일 줄이 없으면 True → 관문 실패 (그 전 9월 1일부터는 경고만)."""
    return csat_missing(today, special) and (today.month, today.day) >= CSAT_BLOCK_FROM


def _gh_escape(text):
    """GitHub Actions 알림(::warning::) 메시지에 넣을 수 있게 % · 줄바꿈을 바꿔요."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotations(rep):
    """실패·경고 줄 → GitHub Actions 알림 줄들. 실행 화면과 check-run 알림 API 에 남아서, 매일 아침 점검이 로그인 없이 읽어요
    (Jack, 2026-11-04: 관문 경고가 매일 점검으로 나에게 와야 해요). 종류마다 10개까지만 보이니 넘치면 마지막 줄에 남은 개수를 적어요."""
    out = []
    for kind, title, rows in (("error", "발행 관문 실패", rep.failed), ("warning", "발행 관문 경고", rep.warned)):
        shown = rows if len(rows) <= ANNOTATE_MAX else rows[:ANNOTATE_MAX - 1]
        out += [f"::{kind} title={title}::" + _gh_escape(f"{r[0]}: {r[1]} (기준 {r[2]})") for r in shown]
        if len(rows) > len(shown):
            out.append(f"::{kind} title={title}::" + _gh_escape(f"외 {len(rows) - len(shown)}개 더 — 실행 요약의 표를 보세요"))
    return out


# ── 최종본 목록 (fetch_data.py 와 별개 구현) ─────────────────
def official_closes(text):
    """목록 CSV → ({종목코드: 공식 종가}, 시가총액이 찬 비율)."""
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    closes, filled = {}, 0
    for r in rows:
        code = (r.get("Code") or "").strip()
        mc, sh = num(r.get("Marcap")), num(r.get("Stocks"))
        if mc and mc > 0:
            filled += 1
            if sh and sh > 0 and len(code) == 6:
                closes[code] = round(mc / sh)
    return closes, (filled / len(rows) if rows else 0.0)


def http_listing(d):
    for _ in range(3):
        try:
            r = requests.get(LIST_URL.format(d=d.isoformat()), timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content.decode("utf-8-sig")
        except requests.RequestException:
            continue
    raise RuntimeError(f"목록 파일 {d} 을 받지 못했어요")


def http_commit_kst(d, sleep=time.sleep):
    """그 날짜 파일의 마지막 커밋 시각(KST). 세 번 시도해도 확인하지 못하면 None (= 최종본 아님 · 2026-11-19)."""
    h = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    for i in range(3):
        try:
            r = requests.get(COMMITS_API, params={"path": f"data/listing/krx/{d.isoformat()}.csv", "per_page": 1},
                             headers=h, timeout=20)
            if r.status_code == 200:
                js = r.json()
                if not js:
                    return None
                ts = js[0]["commit"]["committer"]["date"]
                return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST)
        except (requests.RequestException, ValueError, KeyError, IndexError):
            pass
        if i < 2:
            sleep(2 * (i + 1))
    return None


def is_final(d, text, get_text, get_commit, today, special=None):
    """(최종본인가, 설명). special: KRX 특별 거래시간 표 (None 이면 표 파일을 읽어요)."""
    special = load_special_sessions() if special is None else special
    closes, share = official_closes(text)
    if share < MIN_CAP_SHARE:
        return False, f"시가총액 {share:.0%}"
    ct = get_commit(d)
    if ct is not None:
        cut = final_cut(d, special)
        s = special.get(d)
        tag = (f" · {d} 특별 거래시간({s[2]}): 마감 {s[1]:%H:%M} → 최종본은 {cut:%H:%M} 이후 커밋만"
               if s and s[1] != NORMAL_CLOSE else "")
        return ct >= cut, f"{ct:%m-%d %H:%M} KST 커밋{tag}"
    # 2026-11-19 (더 엄격하게만): 커밋 시각을 확인하지 못한 파일은 최종본으로 보지 않아요. 예전에는 뒤 날짜 파일에 시가총액이 차 있으면 최종본으로
    # 봤는데, 캐시가 다음 거래일의 장중 파일을 올리는 지금은 그 규칙이 장중 파일(11-17 15:29: 삼성전자 190,200 · 공식 종가 190,300)을 최종본으로
    # 받아들여요. 그날은 2차 출처(다음 × 야후)가 정해요.
    return False, "커밋 시각 확인 불가 → 최종본으로 보지 않아요 (2차 출처가 정해요)"


def latest_final(today, get_text=http_listing, get_commit=http_commit_kst, special=None, notes=None):
    """오늘 이전의 가장 최근 최종본: (날짜, 공식 종가 dict, 설명) 또는 (None, None, 사유).
    notes(리스트)를 주면 최종본이 아니어서 건너뛴 날짜와 이유를 적어요."""
    special = load_special_sessions() if special is None else special
    for back in range(1, LOOKBACK_DAYS + 1):
        d = today - dt.timedelta(days=back)
        text = get_text(d)
        if text is None:
            continue
        ok, how = is_final(d, text, get_text, get_commit, today, special)
        if ok:
            return d, official_closes(text)[0], how
        if notes is not None:
            notes.append(f"{d} 최종본 아님 ({how}) → 그 전 날짜로")
    return None, None, f"최근 {LOOKBACK_DAYS}일 안에 최종본이 없어요"


def count_final_between(after, upto, get_text=http_listing):
    """after < d ≤ upto 인 거래일(시가총액이 찬 파일) 수 = 그사이 지나간 거래일."""
    n, d = 0, after + dt.timedelta(days=1)
    while d <= upto:
        t = get_text(d)
        if t is not None and official_closes(t)[1] >= MIN_CAP_SHARE:
            n += 1
        d += dt.timedelta(days=1)
    return n


# ── KOSPI 거래일 (fetch_data.py 와 별개 구현: fetch 는 FinanceDataReader, 여기는 직접 HTTP) ──
def _naver_kospi_dates():
    r = requests.get(NAVER_KOSPI, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return sorted({dt.date(int(m[:4]), int(m[4:6]), int(m[6:8])) for m in re.findall(r'data="(\d{8})\|', r.text)})


def _yahoo_kospi_dates():
    r = requests.get(YAHOO_KOSPI, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    closes = res["indicators"]["quote"][0]["close"]
    return sorted({dt.datetime.fromtimestamp(t, KST).date() for t, c in zip(res["timestamp"], closes) if c is not None})


def http_kospi_sessions(sleep=time.sleep):
    """최근 KOSPI 거래일 목록: {"dates": [...], "src": 출처}. 네이버와 야후를 둘 다 받아 합쳐요
    (한쪽이 하루 늦게 갱신돼도 다른 쪽이 잡도록). 각각 3번까지, 사이에 1·2초 쉬며 시도해요.
    둘 다 실패하면 예외 → 관문은 FAIL (확인하지 못한 채 통과시키지 않아요)."""
    errs, got = [], {}
    for name, fn in (("네이버 KOSPI 일봉", _naver_kospi_dates), ("야후 ^KS11 일봉", _yahoo_kospi_dates)):
        last = None
        for i in range(3):
            try:
                ds = fn()
                if len(ds) >= 10:
                    got[name], last = ds, None
                else:
                    last = f"{name}: {len(ds)}일뿐"
                break
            except Exception as e:
                last = f"{name}: {str(e)[:80]}"
                if i < 2:
                    sleep(i + 1)
        if last:
            errs.append(last)          # 마지막 시도까지 실패한 출처만 적어요
    if not got:
        raise RuntimeError(" · ".join(errs))
    dates = sorted(set().union(*got.values()))
    src = " + ".join(got) + (f" (실패: {' · '.join(errs)})" if errs else "")
    out = {"dates": dates, "src": src}
    if len(got) == 2:               # 두 출처가 다르게 말하는 날짜 (겹치는 기간만) — 로그로 남겨요
        a, b = (set(v) for v in got.values())
        lo = max(min(a), min(b))
        diff = sorted(d for d in a ^ b if d >= lo)
        if diff:
            out["disagree"] = diff
    return out


def _yahoo_closes(sym):
    r = requests.get(YAHOO_CHART.format(sym=sym), timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    closes = res["indicators"]["quote"][0]["close"]
    return [(dt.datetime.fromtimestamp(t, KST).date(), float(c)) for t, c in zip(res["timestamp"], closes) if c is not None]


def http_hilo(codes, px_date, sleep=time.sleep):
    """필수 종목의 52주(252거래일, pxDate 까지) 종가 최고·최저와 d1 — 야후 차트 (이 파일의 코드로 따로 받아요).
    야후의 마지막 날이 pxDate 가 아니면(하루 늦음) 그 종목은 빼요 — 기간이 하루 밀려 엉뚱하게 비교되지 않게.
    반환: {코드: {"hi", "lo", "d1"}}."""
    out = {}
    for code in codes:
        for i in range(3):
            try:
                rows = [(d, c) for d, c in _yahoo_closes(f"{code}.KS") if d <= px_date][-252:]
                if len(rows) >= 200 and rows[-1][0] == px_date:
                    cs = [c for _, c in rows]
                    out[code] = {"hi": max(cs), "lo": min(cs), "d1": (cs[-1] / cs[-2] - 1) * 100}
                break
            except Exception:
                if i < 2:
                    sleep(i + 1)
    return out


def text_values(obj, path=""):
    """JSON 안의 모든 글자 값 (경로, 값)."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from text_values(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from text_values(v, f"{path}[{i}]")


def completed_sessions_after(px, today, sessions):
    """pxDate < d < 오늘(KST) 인 KOSPI 거래일 = 이미 끝났는데 반영되지 않은 거래일. 오늘 거래일은 아직 최종본이
    없을 수 있어서 넣지 않아요 (다음 날 아침 실행이 잡아요)."""
    return [d for d in sessions if px < d < today]


# ── 2026-11-19 (Jack 규칙 3): 캐시 최종본이 없는 날의 관문 기준 — 관문이 야후에서 따로 받은 공식 종가 ──
def px_alt_symbol(s):
    """data.json 종목의 야후 심볼 — 설명(dk)의 '시장 상장' 으로 (코스피 .KS · 코스닥 .KQ · 그 밖은 None). (순수 함수)"""
    m = re.search(r"(?:^| · )(KOSPI|KOSDAQ GLOBAL|KOSDAQ|KONEX) 상장(?: · |$)", str(s.get("dk") or ""))
    sfx = PX_YAHOO_SUFFIX.get(m.group(1)) if m else None
    return f"{s.get('t')}{sfx}" if sfx else None


def px_alt_pick(data):
    """관문이 야후와 맞춰 볼 종목: 필수 종목 전부 + 표본 PX_CHECK_SAMPLE (코스피 · 코스닥 · 코드 순으로 고르게). 반환: {코드: 심볼}. (순수 함수)
    필수 종목은 설명이 없어도 코스피(.KS)로 물어요 (일곱 종목 모두 코스피).
    2026-11-19 (Jack): 기록대로 마지막 확인 종가(pxd)로 실린 국내 종목(kr_own_codes)은 표본에서 빼요 — 그 가격은 pxDate 의 종가가 아니에요."""
    own = kr_own_codes(data)
    kr = {s.get("t"): s for s in kr_stocks(data) if s.get("t") and s.get("t") not in own}
    out = {c: (px_alt_symbol(kr[c]) if c in kr else None) or f"{c}.KS" for c in MUST}
    for c in px_check_sample([c for c, s in kr.items() if px_alt_symbol(s)]):
        out.setdefault(c, px_alt_symbol(kr[c]))
    return out


def yahoo_day_close(res, d, close_time=NORMAL_CLOSE):
    """야후 차트 응답(result[0])에서 그날(KST) 종가 (2026-11-19 · 순수 함수). 반환: (값, 'bar' | 'meta') 또는 (None, 까닭).
    그날 일봉의 종가가 있으면 그것. 일봉은 있는데 종가가 빈 값이면 (야후는 그날 일봉 종가를 몇 시간 동안 비워 둬요 — 11-19 02:15 에 005930 11-18
    종가 null) meta.regularMarketPrice 를 써요 — 그 시각(regularMarketTime · KST)이 그날 마감(close_time · 수능일 16:30) ~ 마감 + 10분 안일 때만
    (마감 동시호가로 정해진 값). 마감 전 · 그 뒤 · 다른 날의 시각이면 확인 못 함."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0] or {}
    closes = q.get("close") or []
    bars = [c for t, c in zip(ts, closes) if dt.datetime.fromtimestamp(t, KST).date() == d]
    if not bars:
        return None, "그날 일봉 없음"
    c = bars[-1]
    if c is not None and isinstance(c, (int, float)) and math.isfinite(c) and c > 0:
        return float(c), "bar"
    meta = res.get("meta") or {}
    p, t = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    if not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0 or not isinstance(t, (int, float)):
        return None, "종가 빈 값 · meta 없음"
    when = dt.datetime.fromtimestamp(t, KST)
    if when.date() != d:
        return None, f"종가 빈 값 · meta 시각 {when:%m-%d %H:%M} 이 그날이 아님"
    start = dt.datetime.combine(d, close_time, KST)
    if not start <= when < start + PX_META_WINDOW:
        return None, f"종가 빈 값 · meta 시각 {when:%H:%M} 이 마감 {close_time:%H:%M} ~ +10분 밖"
    return float(p), "meta"


def _yahoo_day_close(sym, d, get=None, close_time=NORMAL_CLOSE):
    """야후 일봉에서 그날(KST) 종가: (값, 'bar' | 'meta') 또는 (None, 까닭) · 받지 못하면 예외."""
    get = get or (lambda u: requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0"}))
    r = get(PX_YAHOO_CHART.format(sym=sym))
    r.raise_for_status()
    return yahoo_day_close(r.json()["chart"]["result"][0], d, close_time)


def _daum_day_close(code, d, get=None):
    """다음 일별 시세에서 그날 종가 (tradePrice). 반환: (값, 'daum') 또는 (None, 까닭) · 받지 못하면 예외 (4xx 는 다시 묻지 않게 까닭으로)."""
    get = get or (lambda u: requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0", "Referer": f"https://finance.daum.net/quotes/A{code}"}))
    r = get(PX_DAUM_DAYS.format(code=code))
    if 400 <= r.status_code < 500 and r.status_code != 429:
        return None, f"HTTP {r.status_code}"
    r.raise_for_status()
    rows = [x for x in (r.json().get("data") or []) if str(x.get("date") or "")[:10] == d.isoformat()]
    if len(rows) != 1:
        return None, f"그날 행 {len(rows)}개"
    v = rows[0].get("tradePrice")
    return (float(v), "daum") if isinstance(v, (int, float)) and math.isfinite(v) and v > 0 else (None, "종가 없음")


def px_alt_budget(mode, budget_s=None):
    """관문 두 출처 확인 전체의 시간 한도 (초 · 2026-11-20 Jack) — 사이트 점검(live)에서 한도를 받았을 때만 (배포: _main 이 deploy.yml 의
    PX_ALT_LIMIT_ENV 나 --daum-limit 에서 줘요). 한도를 받지 않으면 None — 감시(watchdog)는 예전 그대로 한도 없이. 발행(publish) · bootstrap 은
    늘 None — 한도 없이 예전 그대로. 인자만 읽어요 (모듈 값은 읽지 않아요 · 순수 함수)."""
    if mode != "live" or budget_s is None:
        return None
    return float(budget_s)


def px_alt_secs(x):
    """한도 초를 로그 · 표에 쓰는 꼴: 600 → '600' · 0.5 → '0.5' (1초 아래가 '0초'로 보이지 않게 · 순수 함수)."""
    return f"{x:g}" if isinstance(x, (int, float)) else "?"


def px_alt_was_cut(alt):
    """관문 두 출처 확인이 사이트 점검(live)의 시간 한도에 걸렸는지 — 묻지 못한 종목이 하나라도 있으면 참. (순수 함수)"""
    cut = alt.get("cut") if isinstance(alt, dict) else None
    return isinstance(alt, dict) and alt.get("mode") == "live" and isinstance(cut, int) and not isinstance(cut, bool) and cut > 0


def _count(v):
    """기록의 종목 수 — 0 이상의 정수가 아니면 0 (모르면 설명해 주지 않는 쪽으로 · 순수 함수)."""
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def px_alt_cut_gap(alt):
    """시간 한도에 걸린 확인(live)에서 시간 한도 · 네트워크 오류로 설명할 수 없는 모자람 (2026-11-20 리뷰 · 순수 함수).
    반환: (hard, reach) — hard: 받지 못한 필수 종목 가운데 시간 한도로 건너뛰지도, 네트워크 오류로 끝나지도 않은 종목 (다음이 분명히 답하지
    않았어요: 그날 행 없음 · HTTP 4xx · 종가 없음 — 기록이 없는 종목도 여기에 넣어요) · reach: 받은 + 시간 한도로 건너뜀 + 네트워크 오류 종목 수
    (= 모두 제때 답했다면 받을 수 있었던 가장 많은 수). hard 가 있거나 reach 가 표본 기준에 못 미치면 한도와 상관없이 실패예요.
    2026-11-21: 다음이 거절해 멈춘 확인 (px_alt_was_refused) 이면 거절 종목(refMust)도 설명된 것으로 보고, reach 에 거절 · 거절 뒤 묻지 않은 종목을
    더해요. 그렇지 않으면 예전과 같아요."""
    refd = px_alt_was_refused(alt)
    expl = set(alt.get("cutMust") or []) | set(alt.get("netMust") or []) | (set(alt.get("refMust") or []) if refd else set())
    hard = [c for c in (alt.get("mustMissing") or []) if c not in expl]
    reach = _count(alt.get("got")) + _count(alt.get("cut")) + _count(alt.get("net"))
    return hard, reach + ((_count(alt.get("ref")) + _count(alt.get("rskip"))) if refd else 0)


def px_net_error(e):
    """관문 두 출처 확인에서 난 예외가 네트워크 오류인지 (2026-11-20 리뷰 · 순수 함수). 네트워크 오류는 연결 · 시간 초과
    (requests 의 ConnectionError · Timeout, 파이썬의 ConnectionError · TimeoutError) 와 HTTP 429 · 5xx 뿐이에요. 그 밖의 예외 — 200 인데
    JSON 이 아니거나 모양이 다른 응답 (차단 · 확인 쪽), 다른 4xx 등 — 은 출처가 분명히 답하지 않은 것으로 세요 (시간 한도로 건너뛰지 않아요)."""
    if isinstance(e, (requests.ConnectionError, requests.Timeout, ConnectionError, TimeoutError)):
        return True
    if isinstance(e, requests.HTTPError):
        st = getattr(getattr(e, "response", None), "status_code", None)
        if not isinstance(st, int):                  # 응답이 붙지 않은 HTTPError: 맨 앞의 세 자리 상태 코드로
            m = re.match(r"\s*(\d{3})\b", str(e))
            st = int(m.group(1)) if m else None
        return isinstance(st, int) and (st == 429 or 500 <= st <= 599)
    return False


PX_REFUSE_HTTP = re.compile(r"HTTP (401|403|451)")          # _daum_day_close 가 4xx 에 돌려주는 까닭 그대로 ('HTTP 403')
_PX_REFUSE_OS = (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


def px_refusal_answer(why):
    """다음의 답(값 없음)이 거절인지 (2026-11-21 · 순수 함수): HTTP 401 · 403 · 451 (들어오지 못하게 함)만. 404 · 그날 행 없음 · 종가 없음은
    다음이 답한 거예요 (거절이 아니에요)."""
    return isinstance(why, str) and PX_REFUSE_HTTP.fullmatch(why) is not None


def _exc_chain(e, depth=8):
    """예외와 그 안의 예외들 (args · reason · __cause__ · __context__ — requests 가 urllib3 · 소켓 오류를 감싸는 꼴) · 순수 함수."""
    out, todo, seen = [], [e], set()
    while todo and len(out) < 4 * depth:
        x = todo.pop(0)
        if not isinstance(x, BaseException) or id(x) in seen:
            continue
        seen.add(id(x))
        out.append(x)
        todo += [a for a in (getattr(x, "args", None) or ()) if isinstance(a, BaseException)]
        todo += [getattr(x, "reason", None), x.__cause__, x.__context__]
    return out


# 상대(다음 쪽)가 보낸 TLS 경보 가운데 '들이지 않겠다'는 뜻인 것만 (OpenSSL 이 받은 경보에 붙이는 이름 · 리뷰 2026-11-21). 상대의 internal_error ·
# decode_error 같은 경보는 고장이라 (5xx 처럼) 거절로 세지 않아요. 우리 쪽 OpenSSL 이 스스로 거절한 것 (WRONG_VERSION_NUMBER ·
# UNSAFE_LEGACY_RENEGOTIATION_DISABLED · DH_KEY_TOO_SMALL · HANDSHAKE_FAILURE · 인증서) 은 이 이름이 아니에요.
PX_REFUSE_TLS_ALERTS = ("SSLV3_ALERT_HANDSHAKE_FAILURE", "TLSV1_ALERT_ACCESS_DENIED", "TLSV1_ALERT_PROTOCOL_VERSION",
                        "TLSV1_ALERT_INSUFFICIENT_SECURITY", "TLSV1_UNRECOGNIZED_NAME")


def _ssl_reason(x):
    """ssl 오류의 OpenSSL 까닭 이름 ('WRONG_VERSION_NUMBER' 등) — reason 이 없으면 글의 '[SSL: …]' 에서. (순수 함수)"""
    r = getattr(x, "reason", None)
    if isinstance(r, str) and r:
        return r
    m = re.search(r"\[SSL: ([A-Z0-9_]+)\]", str(x))
    return m.group(1) if m else None


def _tls_refusal(x):
    """ssl 오류 하나가 상대의 거절인지: 상대가 TLS 를 끊음 (SSLEOFError · SSLZeroReturnError) 이나 PX_REFUSE_TLS_ALERTS 경보. (순수 함수)"""
    if isinstance(x, (ssl.SSLEOFError, ssl.SSLZeroReturnError)):
        return True
    return isinstance(x, ssl.SSLError) and not isinstance(x, ssl.SSLCertVerificationError) and _ssl_reason(x) in PX_REFUSE_TLS_ALERTS


def _http_status(e):
    """requests.HTTPError 의 상태 코드 — 응답이 없으면 글 맨 앞의 세 자리. (순수 함수)"""
    st = getattr(getattr(e, "response", None), "status_code", None)
    if not isinstance(st, int):
        m = re.match(r"\s*(\d{3})\b", str(e))
        st = int(m.group(1)) if m else None
    return st


def px_refusal_error(e):
    """관문 두 출처 확인에서 난 예외가 다음의 거절인지 (2026-11-21 · 순수 함수). 거절: 연결 거부 · 연결 끊김 (reset · abort · 응답 없이 닫음 ·
    broken pipe) · 상대가 TLS 를 끊음 (SSLEOFError · SSLZeroReturnError) · 상대가 거절 경보를 보냄 (PX_REFUSE_TLS_ALERTS) · HTTP 429 (요청이
    너무 많다며 받지 않음). 거절이 아님: 시간 초과 (requests 의 ConnectTimeout 은 ConnectionError 이기도 해요) · 5xx · DNS 찾기 실패 ·
    프록시 오류 · 우리 쪽 OpenSSL 이 거절한 TLS (인증서 확인 · WRONG_VERSION_NUMBER · DH_KEY_TOO_SMALL 등 — 안에 그런 ssl 오류가 하나라도
    있으면) · 무엇 때문인지 적히지 않은 ConnectionError · JSON 이 아닌 응답 등. 거절은 모두 px_net_error 의 네트워크 오류 안이에요."""
    if isinstance(e, (requests.Timeout, TimeoutError, requests.exceptions.ProxyError)):
        return False
    if isinstance(e, requests.HTTPError):
        return _http_status(e) == 429
    if not isinstance(e, (requests.ConnectionError, ConnectionError, ssl.SSLError)):
        return False
    chain = _exc_chain(e)
    tls = [x for x in chain if isinstance(x, ssl.SSLError)]
    if any(isinstance(x, TimeoutError) for x in chain) or "CERTIFICATE_VERIFY_FAILED" in str(e) or not all(_tls_refusal(x) for x in tls):
        return False
    return any(isinstance(x, _PX_REFUSE_OS) for x in chain) or bool(tls)


def px_refusal_name(e):
    """거절 예외의 짧은 이름 — 보기에 써요 (리뷰 2026-11-21: 겉의 'HTTPSConnectionPool(host=…' 글은 잘려 까닭이 보이지 않았어요 · 순수 함수).
    HTTP 429 · 가장 바깥에 가까운 연결 · TLS 까닭 (ConnectionRefusedError · RemoteDisconnected · SSLEOFError · SSLError TLSV1_ALERT_ACCESS_DENIED)."""
    if isinstance(e, requests.HTTPError):
        return f"HTTP {_http_status(e)}"
    for x in _exc_chain(e):
        if isinstance(x, ssl.SSLError) and _tls_refusal(x):
            return type(x).__name__ + ("" if isinstance(x, (ssl.SSLEOFError, ssl.SSLZeroReturnError)) else f" {_ssl_reason(x)}")
        if isinstance(x, _PX_REFUSE_OS):
            return type(x).__name__
    return type(e).__name__


def px_alt_refuse_need(asked):
    """다음이 거절한다고 볼 거절 종목 수 (2026-11-21 · 순수 함수): 그만큼 빠지면 나머지가 모두 답해도 표본 기준(PX_ALT_MIN_SHARE)을 채울 수
    없는 가장 작은 수 — 예전 규칙으로도 그 확인은 이미 통과할 수 없어요 (207종목 → 21 · 206 → 21 · 200 → 21). 필수 종목 수보다 작지 않아요
    (필수 종목도 모두 거절이어야 해요 · http_px_alt)."""
    n = _count(asked)
    k = 0
    while k < n and n - k >= PX_ALT_MIN_SHARE * n:
        k += 1
    return max(k, len(MUST))


def px_alt_was_refused(alt):
    """관문 두 출처 확인을 다음이 거절해 그만 물었는지 (코드 배포의 사이트 점검만 · 2026-11-21 · 순수 함수). 기록이 맞아야 해요: refStop 이 참 ·
    거절 종목 수 ≥ refNeed (정수 · 필수 종목 수 이상) · 필수 종목이 모두 거절."""
    if not (isinstance(alt, dict) and alt.get("mode") == "live" and alt.get("refStop") is True):
        return False
    need = alt.get("refNeed")
    return (isinstance(need, int) and not isinstance(need, bool) and need >= len(MUST) and _count(alt.get("ref")) >= need
            and set(alt.get("refMust") or []) == set(MUST))


def px_alt_stop_why(alt):
    """확인을 일찍 멈춘 까닭 (로그 · 표에 쓰는 말): 시간 한도 · 다음이 거절 · 둘 다. (순수 함수)"""
    cut, ref = px_alt_was_cut(alt), px_alt_was_refused(alt)
    return "시간 한도 · 다음이 거절" if cut and ref else ("다음이 거절" if ref else "시간 한도")


def http_px_alt(data, px, fetch=_yahoo_day_close, sleep=time.sleep, workers=4, special=None, mode="publish", fetch_daum=_daum_day_close,
                budget_s=None, clock=time.monotonic, say=None, refuse_skip=False):
    """관문이 따로 받은 두 출처 공식 종가 (2026-11-19 · 리뷰): 필수 종목 + 표본마다 다음 tradePrice 와 야후 종가(일봉 · 비면 마감 직후 meta).
    publish: 두 값이 원 단위까지 같아야 확인 (closes 에는 확인된 값 · 다른 종목은 발행 가격과 같아질 수 없는 값 — 가격 줄이 실패로 세요).
    live (배포 · 감시, 다음 날 아침에는 야후 그날 일봉이 비고 meta 가 새 날로 넘어가요): 다음 값 + data.json pxSrc 의 발행 때 다음 × 야후 확인 기록.
    2026-11-20 (Jack): budget_s 를 받은 live 만 (배포 · px_alt_budget) 확인 전체에 시간 한도 — 지나면 새 요청(다시 묻기도)을 하지 않고 크게
    남겨요. 묻는 중인 요청은 자기 시간 한도까지 끝나고, 일하는 스레드는 모두 끝난 뒤 돌아와요. 한도가 있을 때는 필수 종목을 먼저 물어요.
    시작할 때 한 줄 (종목 수 · 한도) 을 남겨요 (두 모드 모두 · 로그만).
    반환: {"date", "mode", "closes", "asked", "got", "meta", "disagree", "mustMissing", "err", "cut", "cutMust", "limit", "secs",
           "no", "noMust", "noEx", "net", "netMust"}
    (cut: 시간 한도로 건너뛴 종목 수 — 묻지 않았거나 다시 묻지 못한 종목 · cutMust: 그중 필수 종목 · limit: 한도 초 또는 None · secs: 걸린 초 ·
    다음 단계에서 (리뷰 2026-11-20 — 한도에 걸린 날 무엇을 건너뛸 수 있는지 가려요): no: 다음이 분명히 답하지 않은 종목 수 (그날 행 없음 · HTTP 4xx ·
    종가 없음 · 마지막 오류가 네트워크 오류가 아님 — px_net_error: JSON 이 아닌 응답 등. 그런 답 뒤 다시 묻기 전에 한도가 지난 종목도) ·
    noMust: 그중 필수 종목 · noEx: 보기 다섯 · net: 마지막 오류가 네트워크 오류(연결 · 시간 초과 · HTTP 429 · 5xx)로 세 번을 다 쓴 종목 수 ·
    netMust: 그중 필수 종목 · cutErr / cutErrN: 네트워크 오류 뒤 다시 묻기 전에 한도가 지난 종목의 마지막 오류 (보기 다섯 · 수) — err 에도 남지만
    err 은 처음 다섯만이라 따로 둬요).
    2026-11-21 (Jack "3. Yes." · 코드 배포만: 한도를 받은 live 에 refuse_skip=True 일 때만 — _main 이 PX_ALT_REFUSE_ENV 나 --daum-refuse-skip 에서
    줘요 · 데이터 실행 뒤 배포 · 감시 · 발행 관문은 False): 다음이 아예 거절하면 (px_refusal_answer · px_refusal_error) 더 묻지 않아요 — 답이 정해진
    종목이 모두 거절이고, 필수 종목이 모두 그 안에 있고, 그 수가 px_alt_refuse_need 이상일 때 (다른 답이 하나라도 먼저 오면 그 실행에서는 꺼져요).
    그 순간 크게 한 줄 남기고, 남은 종목은 묻지 않아요 (묻는 중인 요청은 끝까지). 더한 기록: refStop (그렇게 멈췄는지) · ref: 거절로 끝난 종목 수
    (멈췄을 때만 — 그 종목은 no · net 에서 빼요 · 멈추지 않았으면 0 이고 no · net 은 예전 그대로) · refMust: 그중 필수 종목 · refEx: 보기 다섯 ·
    rskip: 거절로 멈춘 뒤 묻지 않은 종목 수 · refNeed: 거절로 볼 종목 수 (이 규칙이 꺼져 있으면 None) · refEx 의 까닭은 짧은 이름
    (HTTP 403 · ConnectionRefusedError · SSLEOFError … — px_refusal_name). 종목마다 got · cut · no · net · ref · rskip 하나로만 세요.
    예외를 내지 않아요 — 못 받은 종목은 확인 못 함."""
    from concurrent.futures import ThreadPoolExecutor
    say = say or (lambda line: print(line, flush=True))
    pick = px_alt_pick(data)
    closes, errs, meta, dis, ok = {}, [], [], [], set()
    no, net = {}, set()                          # 다음 단계: 분명히 답하지 않음 (코드 → 까닭) · 네트워크 오류 (세 번 모두)
    sp = (special or {}).get(px)
    close_time = sp[1] if sp else NORMAL_CLOSE
    limit = px_alt_budget(mode, budget_s)
    # 2026-11-21 (Jack "3. Yes."): 다음이 아예 거절하는지 — 코드 배포만 (한도를 받은 live + refuse_skip). 그 밖에는 need 가 None 이라 예전 그대로예요.
    need = px_alt_refuse_need(len(pick)) if limit is not None and mode == "live" and refuse_skip is True else None
    t0 = clock()
    deadline = None if limit is None else t0 + limit
    cut, lock = set(), threading.Lock()
    order = sorted(pick.items())
    if limit is not None:                        # 한도에 걸려도 필수 종목은 이미 물었게 (발행 관문은 한도가 없어 예전 순서 그대로)
        order = [(c, pick[c]) for c in MUST if c in pick] + [x for x in order if x[0] not in MUST]
    say(f"· 관문의 두 출처 확인 시작 ({px} · {'다음 일별 시세 + 발행 기록' if mode == 'live' else '다음 × 야후'}): {len(pick)}종목 · 동시 {workers} · "
        + (f"시간 한도 {px_alt_secs(limit)}초 (배포 — 넘으면 새로 묻지 않고, 시간 한도로 못 받은 부분만 경고로 건너뛰어요)" if limit is not None
           else ("시간 한도 없음" + (" (발행 관문 · 예전 그대로)" if mode != "live" else " (예전 그대로)")))
        + (f" · 다음이 거절하면 (답이 정해진 {need}종목 이상이 모두 거절 · 필수 종목 모두) 그만 묻고 경고로 건너뛰어요 (코드 배포만)"
           if need is not None else ""))

    cut_errs = []                                # 네트워크 오류 뒤 다시 묻기 전에 한도가 지난 종목의 마지막 오류 (리뷰: err 다섯에 묻히지 않게)
    ref, rskip, rstate = {}, set(), {"other": False, "stop": False}   # 거절로 끝난 종목 (코드 → 까닭) · 거절로 멈춘 뒤 묻지 않은 종목

    def late():
        """시간 한도가 지났는지."""
        return deadline is not None and clock() >= deadline

    def settle(code, refused, why):
        """다음 단계의 답이 정해진 종목을 적어요 (거절인지) — 거절로 멈출 때가 되면 그 순간 크게 한 번 남겨요."""
        if need is None:
            return
        with lock:
            if refused:
                ref[code] = str(why)[:60]             # 짧은 이름 (px_refusal_name · 가장 긴 것 41자) 이 잘리지 않게
            else:
                rstate["other"] = True               # 거절이 아닌 답이 왔어요 — 이 실행에서는 거절로 멈추지 않아요 (일부만 거절 · 예전 그대로)
            if (not rstate["stop"] and not rstate["other"] and len(ref) >= need
                    and all(c in ref for c in MUST if c in pick)):
                rstate["stop"] = True
                ex = "; ".join(f"{c} {ref[c]}" for c in [c for c in MUST if c in ref][:3])
                say(f"!! 관문의 두 출처 확인: 다음이 거절해요 — 답이 정해진 {len(ref)}종목이 모두 거절 (필수 종목 "
                    f"{sum(1 for c in MUST if c in ref)} / {len(MUST)} · 보기: {ex}) · 다음 일별 시세를 더 묻지 않아요 (확인 {len(ok)} / 대상 "
                    f"{len(pick)} · Jack 2026-11-21 · 코드 배포만) — 묻는 중인 요청은 끝까지 · 남은 종목은 건너뛰어요")

    def mark_cut(code):
        """그 종목을 '시간 한도로 건너뜀'으로 적어요 (처음 한 번 크게 남겨요)."""
        with lock:
            first = not cut
            cut.add(code)                        # 먼저 적고 (남기다 잘못돼도 건너뛴 종목은 세요) 처음 한 번 크게 남겨요
            if first:
                say(f"!! 관문의 두 출처 확인 시간 한도 {px_alt_secs(limit)}초: 다음 일별 시세를 더 묻지 않아요 (확인 {len(ok)} / 대상 {len(pick)}) — "
                    "묻는 중인 요청은 자기 시간 한도(약 40초)까지 · 남은 종목은 건너뛰어요")

    def get(fn, code, *a, **k):
        """(값, 까닭, 어떻게): 어떻게 = 'ans' (출처가 답했어요 — 값이 None 이면 분명히 답하지 않음) · 'no' (마지막 오류가 네트워크 오류가
        아니에요 — px_net_error · 분명히 답하지 않음) · 'net' (마지막 오류가 네트워크 오류로 세 번을 다 썼어요) · 'cut' (시간 한도).
        다시 묻는 횟수와 쉬는 시간은 오류 종류와 상관없이 예전 그대로예요.
        2026-11-21: 'ref' (세 번 모두 거절 쪽 네트워크 오류 — px_refusal_error · net 의 한 갈래) · 'rskip' (다음이 거절해 멈춘 뒤라 묻지 않음)."""
        last, last_net, all_ref, last_e = None, True, True, None
        for i in range(3):
            stop = "cut" if late() else ("rskip" if rstate["stop"] else None)
            if stop:
                if last is not None:             # 오류 뒤 다시 묻기 전에 한도가 지났어요 — 왜 못 받았는지 (시간 초과 · 거절 · 차단 쪽) 남겨요
                    note = f"{a[0]}: {last} ({'시간 한도로' if stop == 'cut' else '다음이 거절해'} 다시 묻지 않음)"
                    errs.append(note)
                    if not last_net:             # 네트워크 오류가 아닌 답 (차단 쪽 · JSON 이 아님) 이었어요 — 시간 한도 탓이 아니에요
                        return None, last, "no"
                    if stop == "cut":
                        cut_errs.append(note)
                if stop == "rskip":              # 다음이 거절해 멈췄어요 (2026-11-21) — 시간 한도와 따로 세요
                    with lock:
                        rskip.add(code)
                    return None, "다음이 거절", "rskip"
                mark_cut(code)
                return None, "시간 한도", "cut"
            try:
                r = fn(*a, **k)
            except Exception as e:
                last, last_net, last_e = str(e)[:60], px_net_error(e), e
                all_ref = all_ref and px_refusal_error(e)
                if i == 2:
                    errs.append(f"{a[0]}: {last}")
                elif (deadline is None or clock() < deadline) and not rstate["stop"]:   # 한도가 지났거나 거절로 멈췄으면 쉬지 않고 바로 건너뛰어요
                    sleep(i + 1)
                continue
            v, why = r
            return v, why, "ans"
        if last_net and all_ref:                 # 거절: 보기에는 짧은 이름 (겉 글은 'HTTPSConnectionPool(host=…' 로 잘려요 · 리뷰 2026-11-21)
            return None, px_refusal_name(last_e), "ref"
        return None, last, ("net" if last_net else "no")

    def one(item):
        code, sym = item
        dv, dwhy, dhow = get(fetch_daum, code, code, px)
        if dhow in ("net", "ref"):
            net.add(code)
        if dhow in ("ans", "no", "net", "ref"):   # 다음 단계의 답이 정해졌어요 (시간 한도 · 거절로 묻지 않은 종목은 빼고)
            settle(code, dhow == "ref" or (dhow == "ans" and dv is None and px_refusal_answer(dwhy)), dwhy)
        if dv is None or not math.isfinite(dv) or dv <= 0:
            if dhow in ("ans", "no"):
                no[code] = str(dwhy)[:40]
            return
        if mode == "live":
            closes[code] = dv
            ok.add(code)
            return
        yv, how, _ = get(fetch, code, sym, px, close_time=close_time)
        if yv is None or not math.isfinite(yv) or yv <= 0:
            return
        if abs(dv - yv) <= PX_ALT_TOL:
            closes[code] = dv
            ok.add(code)
            if how == "meta":
                meta.append(code)
        else:
            closes[code] = dv + 0.5                  # 두 출처가 다르면 어느 발행 가격과도 같지 않아요 (확인 못 함)
            dis.append(f"{code} 다음 {dv:,.0f} · 야후 {yv:,.2f}")
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:     # with: 묻는 중인 요청이 끝날 때까지 기다려요 (남는 스레드 없음)
            list(ex.map(one, order))
    except Exception as e:                       # 관문은 네트워크 때문에 멈추지 않아요 — 확인 못 함으로 실패해요
        errs.append(f"{type(e).__name__}: {str(e)[:80]}")
    # 2026-11-21: 거절로 멈췄을 때만 거절 종목을 따로 세요 (no · net 에서 빼요). 멈추지 않았으면 no · net 은 예전 그대로예요.
    rf = dict(ref) if rstate["stop"] else {}
    no = {c: w for c, w in no.items() if c not in rf}
    net = {c for c in net if c not in rf}
    return {"date": px, "mode": mode, "closes": closes, "asked": len(pick), "got": len(ok), "meta": len(meta), "disagree": sorted(dis),
            "mustMissing": [c for c in MUST if c not in ok], "err": errs[:5], "cut": len(cut), "cutMust": [c for c in MUST if c in cut],
            "limit": limit, "secs": round(clock() - t0, 1),
            "no": len(no), "noMust": [c for c in MUST if c in no], "noEx": [f"{c} {no[c]}" for c in ([c for c in MUST if c in no] + sorted(c for c in no if c not in MUST))[:5]],
            "net": len(net), "netMust": [c for c in MUST if c in net], "cutErr": cut_errs[:5], "cutErrN": len(cut_errs),
            "refStop": rstate["stop"], "ref": len(rf), "refMust": [c for c in MUST if c in rf],
            "refEx": [f"{c} {rf[c]}" for c in ([c for c in MUST if c in rf] + sorted(c for c in rf if c not in MUST))[:5]],
            "rskip": len(rskip), "refNeed": need}


def px_alt_confirms(data, alt, px, final, mode="publish", today=None, now=None, special=None, cover=True, own=None):
    """2차 출처 날의 관문 기준을 쓸 수 있는지 (2026-11-19 · Jack 규칙 3 · 순수 함수). 반환: (쓸 수 있는지, 설명).
    모두 맞아야 해요: 캐시에 pxDate 의 최종본이 없음 (최종본이 있으면 예전 그대로 그것과 비교) · data.json pxSrc 가 2차 출처 · 그 날짜가 pxDate ·
    확인되지 않은 필수 종목 없음 · 2차 출처 확인 종목 수 ≥ 발행한 국내 종목 수 · 관문이 따로 받은 두 출처(http_px_alt — 발행은 다음 × 야후,
    배포 · 감시는 다음 + 발행 기록)가 필수 종목을 모두, 표본을 PX_ALT_MIN_SHARE 넘게 확인 · pxDate 가 오늘(KST) 전이고 지금이 그날 마감 + 30분 뒤.
    cover=False (2026-11-20 Jack · 배포의 확인이 시간 한도에 걸렸을 때만 — px_alt_was_cut): 마지막 '받은 종목 수' 조건(필수 종목 모두 ·
    표본 PX_ALT_MIN_SHARE)에서 시간 한도(와 네트워크 오류)로 설명되는 모자람만 건너뛰어요 (px_alt_cut_gap · 리뷰) — 다음이 분명히 답하지 않은
    필수 종목이 있거나, 건너뜀 · 네트워크 오류 종목을 모두 받았다고 쳐도 표본 기준에 못 미치면 거짓이에요. 나머지 조건은 모두 그대로예요.
    한도에 걸리지 않은 확인이나 발행 관문에는 참을 주지 않아요."""
    src = data.get("pxSrc")
    if alt is None:
        return False, "관문이 두 출처 종가를 받지 않았어요"
    if final is not None and final.get("date") is not None and final["date"] >= px:
        return False, f"캐시 최종본 {final['date']} 이 있어요 (그것과 비교)"
    if today is None or px is None or not px < today:
        return False, f"pxDate {px} 가 오늘({today}) 전이 아니에요 — 끝나지 않은 날"
    try:
        sp = load_special_sessions() if special is None else special
    except Exception as e:
        return False, f"KRX 특별 거래시간 표를 읽지 못했어요 ({str(e)[:40]})"
    ref = now or dt.datetime.combine(today, dt.time(0), KST)
    if ref < final_cut(px, sp):
        return False, f"지금({ref:%m-%d %H:%M}) 이 {px} 마감 + 30분 ({final_cut(px, sp):%H:%M}) 전이에요"
    if not isinstance(src, dict) or src.get("px") != PX_SRC_FB:
        return False, "data.json pxSrc 가 2차 출처가 아니에요"
    if day(src.get("date")) != px or alt.get("date") != px:
        return False, f"pxSrc 날짜 {src.get('date')} · 관문 확인 날짜 {alt.get('date')} ≠ pxDate {px}"
    if src.get("must"):
        return False, f"확인되지 않은 필수 종목: {', '.join(map(str, src['must']))}"
    fb = src.get("fb") if isinstance(src.get("fb"), dict) else {}
    own = kr_own_codes(data) if own is None else own   # 2026-11-19 (Jack): 마지막 확인 종가(pxd)로 맞게 실린 종목은 pxDate 의 가격이 아니라 세지 않아요
    nk = len([s for s in kr_stocks(data) if s.get("t") not in own])
    if not isinstance(fb.get("conf"), int) or fb["conf"] < nk:
        return False, f"2차 출처 확인 {fb.get('conf')}종목 < 발행한 국내 종목 {nk:,}" + (f" (마지막 확인 종가로 실은 {len(own)}종목 빼고)" if own else "")
    want = "live" if mode == "live" else "publish"
    if alt.get("mode", "publish") != want:
        return False, f"관문 확인 방식 {alt.get('mode')} ≠ {want}"
    how = "다음 × 야후" if want == "publish" else "다음 + 발행 때 다음 × 야후 기록"
    if not cover:
        refd = px_alt_was_refused(alt)           # 2026-11-21 (Jack "3. Yes."): 다음이 거절해 멈춘 확인도 같은 길로 (한도를 받은 사이트 점검만)
        if want != "live" or not (px_alt_was_cut(alt) or refd):
            return False, "시간 한도나 다음의 거절로 건너뛸 수 있는 확인이 아니에요 (사이트 점검에서 한도에 걸렸거나 다음이 거절한 확인만)"
        asked, got, cut, net, nno = _count(alt.get("asked")), _count(alt.get("got")), _count(alt.get("cut")), _count(alt.get("net")), _count(alt.get("no"))
        ex = f" (보기: {'; '.join(map(str, alt['noEx'][:3]))})" if alt.get("noEx") else ""
        # 2026-11-20 리뷰: 시간 한도(와 네트워크 오류)로 설명되는 모자람만 건너뛰어요 — 다음이 분명히 답하지 않은 몫은 한도와 상관없이 예전 그대로 실패
        # 2026-11-21: 다음의 거절로 멈췄으면 거절 · 거절 뒤 묻지 않은 몫도 설명돼요 (px_alt_cut_gap) — 다음이 분명히 답하지 않은 몫은 그대로 실패
        hard, reach = px_alt_cut_gap(alt)
        nref, nrskip = _count(alt.get("ref")), _count(alt.get("rskip"))
        if hard:
            return False, (f"관문이 두 출처({how})로 필수 종목을 확인하지 못했어요: {', '.join(hard)} — 다음이 그날 종가를 주지 않았어요{ex} "
                           + ("(시간 한도에 걸렸지만 이 종목들은 시간 한도 때문이 아니에요)" if not refd
                              else "(다음이 거절해 멈췄지만 이 종목들은 거절 때문이 아니에요)"))
        if not asked or reach < PX_ALT_MIN_SHARE * asked:
            return False, (f"관문이 두 출처({how})로 확인한 종가 {got} / {asked} — "
                           + (f"다음의 거절 {nref} · 거절 뒤 묻지 않음 {nrskip} · " if refd else "")
                           + f"시간 한도로 건너뜀 {cut} · 네트워크 오류 {net} 을 모두 받았다고 쳐도 "
                           f"{reach} / {asked} (기준 {PX_ALT_MIN_SHARE:.0%}) · 다음이 그날 종가를 주지 않은 종목 {nno}{ex} "
                           + ("(시간 한도 때문이 아니에요)" if not refd else "(거절 · 시간 한도 때문이 아니에요)"))
        nm = len(MUST) - len(alt.get("mustMissing") or [])
        lim = alt.get("limit")
        if refd:
            rex = f" · 보기: {'; '.join(map(str, alt['refEx'][:3]))}" if alt.get("refEx") else ""
            return True, (f"관문의 두 출처 확인({how})을 다음이 거절해 건너뜀 (Jack 2026-11-21 · 코드 배포만) — 거절 {nref}종목 (필수 종목 "
                          f"{len(alt.get('refMust') or [])} / {len(MUST)}{rex}) · 거절 뒤 묻지 않음 {nrskip} · 확인 {got} / {asked}종목 "
                          f"(네트워크 오류 {net} · 다음이 그날 종가를 주지 않음 {nno}" + (f" · 시간 한도로 건너뜀 {cut}" if cut else "") + ") · "
                          f"발행 때 2차 출처(다음 × 야후) 확인 {fb['conf']:,}종목 · 받은 종가는 가격 줄에서 비교")
        return True, (f"관문의 두 출처 확인({how})을 시간 한도{f' {px_alt_secs(lim)}초' if isinstance(lim, (int, float)) else ''}로 건너뜀 (Jack 2026-11-20) — "
                      f"한도 전에 확인 {got} / {asked}종목 (시간 한도로 건너뜀 {cut} · 네트워크 오류 {net} · 다음이 그날 종가를 주지 않음 {nno}) · "
                      f"필수 종목 {nm} / {len(MUST)} · 발행 때 2차 출처(다음 × 야후) 확인 {fb['conf']:,}종목 · 받은 종가는 가격 줄에서 비교")
    if alt.get("mustMissing"):
        return False, f"관문이 두 출처({how})로 필수 종목을 확인하지 못했어요: {', '.join(alt['mustMissing'])}" + (f" ({alt['err'][0]})" if alt.get("err") else "")
    asked, got = alt.get("asked") or 0, alt.get("got") or 0
    if not asked or got < PX_ALT_MIN_SHARE * asked:
        return False, f"관문이 두 출처({how})로 확인한 종가 {got} / {asked} (기준 {PX_ALT_MIN_SHARE:.0%})" + (f" ({alt['err'][0]})" if alt.get("err") else "")
    kk = fb.get("knx") if isinstance(fb.get("knx"), dict) else None
    return True, (f"캐시 최종본 없음 · 관문이 따로 받은 공식 종가 ({how}) {got}/{asked}종목 · 2차 출처 확인 {fb['conf']:,}종목 (다음 × 야후"
                  + (f" + 코넥스 야후 × 네이버 {kk.get('kept', kk.get('conf'))}" if kk else "") + ")")


def px_alt_closes(alt):
    """관문의 야후 종가 → 비교용 값: 원 단위(PX_ALT_TOL 안)면 정수, 아니면 그대로 (정수인 발행 가격과 같아질 수 없어요). (순수 함수)"""
    out = {}
    for c, v in (alt or {}).get("closes", {}).items():
        out[c] = round(v) if abs(v - round(v)) <= PX_ALT_TOL else v
    return out


PX_CUT_KEYS = ("s", "daum", "yahoo", "fill")
KNX_CUT_KEYS = ("s", "yahoo", "fill", "naver")      # 2026-11-20: 코넥스 2차 출처 단계 (pxSrc.fb.knx.cut)
KNX_CHK_CUT_KEYS = ("s", "naver")                    # 2026-11-20: 1차 출처 날 코넥스 네이버 확인 (pxSrc.knx.chk.cut)


def check_px_cut(rep, src):
    """2026-11-20 (새 줄 · 경고만): 파이프라인이 두 출처 종가를 묻다가 단계 시간 한도(fetch_data.KR_FB_PHASE_BUDGET_S)에 걸렸는지.
    pxSrc.fb.cut (2차 출처를 돌린 날 — 쓸 날을 찾지 못해 1차 출처 그대로인 날도 · 리뷰 N1) · pxSrc.chk.cut (1차 출처 날의 야후 확인):
    단계마다 시간 한도로 묻지 못한 종목 수. 2차 출처 날 걸린 종목은 확인 못 한 종목이라 그날 파일에서 빠져요 (필수 종목이 빠지면 다른 줄이
    멈춰요) — 이 줄은 알리기만 해요. 기록이 하나도 없으면 (이 줄 전 발행본) 건너뛰어요.
    2026-11-20 (더한 기록만 · 경고만): 코넥스 단계 pxSrc.fb.knx.cut (야후 .KQ · 다시 읽기 · 네이버) 와 1차 출처 날 코넥스 네이버 확인
    pxSrc.knx.chk.cut 도 같은 줄에 적어요 (그 기록이 없으면 이 줄은 예전과 같아요)."""
    name = "가격 확인 시간 한도 (경고만)"
    if not isinstance(src, dict) or src.get("px") not in (PX_SRC_FB, PX_SRC_LISTING):
        return
    recs = []
    fb = src.get("fb")
    fb_what = "2차 출처" + (" (쓸 날 없음 · 1차 출처 그대로)" if src.get("px") == PX_SRC_LISTING else "")
    if isinstance(fb, dict) and "cut" in fb:
        recs.append((fb_what, fb["cut"], PX_CUT_KEYS))
    ck = src.get("chk")
    if src.get("px") == PX_SRC_LISTING and isinstance(ck, dict) and "cut" in ck:
        recs.append(("1차 출처 야후 확인", ck["cut"], PX_CUT_KEYS))
    knx_recs = []
    if isinstance(fb, dict) and isinstance(fb.get("knx"), dict) and "cut" in fb["knx"]:
        knx_recs.append(("코넥스 " + fb_what, fb["knx"]["cut"], KNX_CUT_KEYS))
    kk = src.get("knx")
    kc = kk.get("chk") if isinstance(kk, dict) else None
    if src.get("px") == PX_SRC_LISTING and isinstance(kc, dict) and "cut" in kc:
        knx_recs.append(("1차 출처 코넥스 네이버 확인", kc["cut"], KNX_CHK_CUT_KEYS))
    recs += knx_recs
    if not recs:
        rep.skip(name, "기록 없음 (시간 한도 전 발행본이거나 1차 출처 야후 확인을 못 한 날)")
        return
    word = {"daum": "다음", "yahoo": "야후 일봉", "fill": "야후 다시 읽기", "naver": "네이버"}
    vals, rules, hit, odd = [], set(), 0, False
    for what, cut, keys in recs:
        if not (isinstance(cut, dict) and all(isinstance(cut.get(k), int) and not isinstance(cut.get(k), bool) and cut[k] >= 0 for k in keys)):
            vals.append(f"{what}: 기록 모양이 이상해요 {str(cut)[:60]}")
            odd = True
            continue
        n = sum(cut[k] for k in keys if k != "s")
        hit += n
        rules.add(cut["s"])
        if keys is PX_CUT_KEYS:
            vals.append(f"{what}: " + ("없음" if not n else f"묻지 못함 다음 {cut['daum']:,} · 야후 일봉 {cut['yahoo']:,} · 야후 다시 읽기 {cut['fill']:,}종목"))
        else:
            vals.append(f"{what}: " + ("없음" if not n else "묻지 못함 " + " · ".join(f"{word[k]} {cut[k]:,}" for k in keys if k != "s") + "종목"))
    rule = ("0 (단계마다 " + "·".join(f"{x}초" for x in sorted(rules)) + " · 2차 출처 날 묻지 못한 종목은 확인 못 해 빠져요 · "
            "1차 출처 날은 야후 확인만 줄어요)" if rules else "s · daum · yahoo · fill 모두 0 이상의 정수")
    if knx_recs and rules:
        rule = rule[:-1] + " · 코넥스도 같아요: 2차 출처 날은 빠지고 1차 출처 날은 네이버 확인만 줄어요)"
    rep.add(name, True, " / ".join(vals), rule, warn=bool(hit) or odd)


KNX_ROW = "코넥스 종가 두 출처 (경고만)"
KNX_FB_KEYS = ("n", "conf", "kept", "capOut", "noNaver", "bad", "noYahoo", "diff")
# 2차 출처 날 코넥스 줄이 경고하는 때 (리뷰 S1 · 2026-11-20 · 경고만):
# - 야후에 없는 코넥스는 11-10 ~ 11-19 여덟 날 모두 같은 11종목이었어요 (496320 본시스템즈 · 0203K0 송우인포텍 …). 새로 상장해 야후가 아직 싣지 않은
#   종목이 몇 개 더해질 수 있어 15 까지는 평소로 봐요. 그보다 많으면 야후가 그날 코넥스 종가를 비워 둔 거예요 (마감 뒤 몇 시간 · 코넥스는 meta 로 채울 수 없어요).
KNX_NOYAHOO_WARN = 15
# - 두 종가가 다른 코넥스는 하루 3 ~ 9종목이었어요 (같은 여덟 날 · 모두 거래 없는 날 KRX 가 기준가를 옮겨 야후가 마지막 체결가로 남은 종목).
#   평소의 다름은 값 칸에 늘 보이고 경고하지 않아요 (매일 켜지는 경고는 아무도 보지 않아요). 20 을 넘으면 한 출처가 바뀐 것이라 경고해요.
KNX_DIFF_WARN = 20
# 2026-11-20 (검증 리뷰 M1 · 더한 기록만 · 경고만): 기준일 맞춰 보기 — 두 출처는 같았지만 네이버의 기준일(1차 출처 최종본 날짜) 종가가 최종본 공식
# 종가와 달라 (adj · 그 뒤 값이 수정됐을 수 있어요) 또는 맞춰 볼 수 없어 (noAnchor) 넣지 않은 코넥스. 이 기록 전 파일에는 없어요 (없으면 0 으로 읽어요).
KNX_FB_ANCHOR_KEYS = ("adj", "noAnchor")
_KNX_TAIL = re.compile(r"(?:^| · )KONEX 상장(?: · |$)")


def knx_published(data):
    """발행한 코넥스 종목 코드 (설명 dk 의 'KONEX 상장' 으로 · fetch_data.kr_desc_text 가 만드는 글). (순수 함수)"""
    return sorted(s.get("t") for s in kr_stocks(data) if s.get("t") and _KNX_TAIL.search(str(s.get("dk") or "")))


def _nonneg_ints(d, keys):
    return isinstance(d, dict) and all(isinstance(d.get(k), int) and not isinstance(d.get(k), bool) and d[k] >= 0 for k in keys)


def check_px_knx(rep, data, src, own=None):
    """2026-11-20 (새 줄 · 경고만 · Jack, 2026-11-19 답 5: "Naver for KONEX only, always with Yahoo, published only when they agree to the won;
    daily KONEX checking too."): 코넥스 종가의 출처와 확인 (data.json pxSrc.knx · pxSrc.fb.knx).
    - 2차 출처 날 (px daum+yahoo · knx.px yahoo+naver): 야후 .KQ × 네이버 일봉 종가가 원 단위까지 같고 시가총액이 평소 날 발행 기준 (1차 출처 최종본
      MAX_KR 번째) 이상인 코넥스만 그날 파일에 있어요. 경고 (리뷰 S1): 네이버 행이 없는 종목이 있음 · 야후 없음이 KNX_NOYAHOO_WARN 보다 많음 ·
      확인이 절반 아래 · 값을 못 믿은 종목 · 다름이 KNX_DIFF_WARN 보다 많음 · 시가총액 기준을 모름. 평소의 다름 (거래 없는 날 기준가 · 하루 3 ~ 9) 은
      값 칸에 보이고 그것만으로는 경고하지 않아요. 빠진 종목은 그날 파일에 없어요.
      검증 리뷰 (2026-11-20 · 더한 경고만): 기준일 맞춰 보기로 넣지 않은 코넥스 (adj · noAnchor) 가 있으면 · 시가총액 기준(floor)이 숫자가 아니면 경고.
    - 1차 출처 날 (px listing): 발행한 코넥스의 최종본 종가를 모두 네이버와 맞춘 결과 (knx.chk). 다르거나 · 네이버 값이 없거나 · 시간 한도 ·
      받지 못함이면 경고 (가격은 최종본 그대로 · 빼지 않아요 — 발행을 멈추는 조건은 Jack 의 답이 있어야 해요).
    - 기록의 모양이 이상하거나 발행한 코넥스 (dk 'KONEX 상장') 와 knx.t 가 다르면 경고. pxSrc.knx 가 없으면 (이 줄 전 발행본) 건너뛰어요.
    이 줄은 발행을 멈추지 않아요.
    own (2026-11-20 · #159): 마지막 확인 종가(pxd)로 맞게 실린 국내 종목 (kr_own_codes — run_checks 는 지난 발행본 · 거래일까지 본 것을 줘요). 그런
    코넥스는 그날 야후 .KQ × 네이버로 확인한 종목이 아니라 pxSrc.knx.t 에 없어요 — '발행한 코넥스' 에서 빼고 맞춰 봐요 (그 종목은 '국내 자기 가격
    날짜 (pxd)' · '국내 마지막 확인 종가' 줄이 봐요). 맞지 않게 실린 pxd 코넥스는 빼지 않아요 (예전처럼 어긋남으로 경고)."""
    if not isinstance(src, dict) or src.get("px") not in PX_SRCS:
        return
    k = src.get("knx")
    if k is None:
        rep.skip(KNX_ROW, "pxSrc.knx 없음 (2026-11-20 전 발행본)")
        return
    own = kr_own_codes(data) if own is None else own
    pub = [t for t in knx_published(data) if t not in own]
    odd = []
    if not isinstance(k, dict):
        rep.add(KNX_ROW, True, f"기록 모양이 이상해요 {str(k)[:60]}", "pxSrc.knx {px · t · n · chk}", warn=True)
        return
    t = k.get("t") if isinstance(k.get("t"), list) else None
    if t is None:
        odd.append("t 모양")
    elif sorted(map(str, t)) != pub:
        odd.append(f"발행한 코넥스 {len(pub):,} · 기록 {len(t):,}")
    n = k.get("n")
    if not isinstance(n, dict) or not all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in n.values()) \
            or (t is not None and sum(n.values()) != len(t)):
        odd.append("n 모양")
    warn = False
    if src.get("px") == PX_SRC_FB:
        fbk = (src.get("fb") or {}).get("knx") if isinstance(src.get("fb"), dict) else None
        if k.get("px") == PX_SRC_KNX:
            if not _nonneg_ints(fbk, KNX_FB_KEYS):
                odd.append("fb.knx 모양")
                fbk = {}
            elif t is not None and len(t) > fbk["kept"]:
                odd.append(f"발행 {len(t):,} > 그날 파일에 넣은 코넥스 {fbk['kept']:,}")
            dex = fbk.get("diffEx", [])
            if not isinstance(dex, list):
                odd.append("diffEx 모양")
                dex = []
            anc = {x: fbk[x] for x in KNX_FB_ANCHOR_KEYS if x in fbk}
            if anc and not _nonneg_ints(anc, tuple(anc)):
                odd.append("adj · noAnchor 모양")
                anc = {}
            aex = fbk.get("adjEx", [])
            if not isinstance(aex, list):
                odd.append("adjEx 모양")
                aex = []
            fl = fbk.get("floor")
            fl_ok = isinstance(fl, (int, float)) and not isinstance(fl, bool) and math.isfinite(fl) and fl > 0
            if fl is not None and not fl_ok:
                odd.append(f"floor 모양 {str(fl)[:20]}")      # 검증 리뷰: 숫자가 아닌 기준은 '기준 모름' 으로만 보이지 않고 경고해요
            left = sum(fbk.get(x) or 0 for x in ("noNaver", "bad", "noYahoo", "diff")) + sum(anc.values())
            val = (f"2차 출처 날 · 야후 .KQ × 네이버: 확인 {fbk.get('conf', '?')} / {fbk.get('n', '?')} · 빠짐 {left:,} (네이버 행 없음 {fbk.get('noNaver', '?')}"
                   f" · 값 못 믿음 {fbk.get('bad', '?')} · 야후 없음 {fbk.get('noYahoo', '?')} · 다름 {fbk.get('diff', '?')}"
                   + (f" · 기준일 {fbk['anchor'] if isinstance(fbk.get('anchor'), str) and fbk['anchor'] else '모름'} 종가 다름 {anc.get('adj', 0)}"
                      f" · 기준일 맞춰 보지 못함 {anc.get('noAnchor', 0)}" if anc else "")
                   + f") · 그날 파일에 {fbk.get('kept', '?')}"
                   f" (시가총액 기준 아래 {fbk.get('capOut', '?')}"
                   + (f" · 기준 {fl / 1e8:,.0f}억원" if fl_ok else " · 기준 모름") + f") · 발행 {len(t or []):,}"
                   + (f" 예: {'; '.join(map(str, dex[:3]))}" if dex else "")
                   + (f" · 기준일 종가 다름 예: {'; '.join(map(str, aex[:3]))}" if aex else ""))
            n_ = fbk.get("n") or 0
            why = ([f"네이버 행 없음 {fbk['noNaver']}"] if fbk.get("noNaver") else []) \
                + ([f"야후 없음 {fbk['noYahoo']} > {KNX_NOYAHOO_WARN}"] if (fbk.get("noYahoo") or 0) > KNX_NOYAHOO_WARN else []) \
                + (["확인이 절반 아래"] if n_ and (fbk.get("conf") or 0) < n_ / 2 else []) \
                + ([f"값 못 믿음 {fbk['bad']}"] if fbk.get("bad") else []) \
                + ([f"다름 {fbk['diff']} > {KNX_DIFF_WARN}"] if (fbk.get("diff") or 0) > KNX_DIFF_WARN else []) \
                + (["시가총액 기준 모름"] if fbk and fl is None else []) \
                + ([f"기준일 종가 다름 {anc['adj']}"] if anc.get("adj") else []) \
                + ([f"기준일 맞춰 보지 못함 {anc['noAnchor']}"] if anc.get("noAnchor") else [])
            if why:
                val += f" — 경고: {', '.join(why)}"
            warn = bool(why)
        elif k.get("px") is None:
            val = "2차 출처 날 · 코넥스 단계를 묻지 않았어요 (그날 파일에 코넥스 없음)"
            warn = True
            if pub:
                odd.append(f"출처 없이 발행한 코넥스 {len(pub):,}")
        else:
            val = f"2차 출처 날인데 코넥스 출처가 {k.get('px')!r}"
            odd.append("px")
    else:
        ck = k.get("chk")
        if k.get("px") != PX_SRC_LISTING:
            odd.append(f"px {k.get('px')!r}")
        if not isinstance(ck, dict):
            val = "1차 출처 날 · 네이버 확인 기록 없음"
            warn = bool(pub)
        else:
            if not _nonneg_ints(ck, ("n", "same", "none")):
                odd.append("chk 모양")
            diff = ck.get("diff", [])
            nex = ck.get("noneEx", [])
            if not isinstance(diff, list) or not isinstance(nex, list):
                odd.append("diff · noneEx 모양")
                diff, nex = (diff if isinstance(diff, list) else []), (nex if isinstance(nex, list) else [])
            cut = (ck.get("cut") or {}).get("naver") if isinstance(ck.get("cut"), dict) else 0
            val = (f"1차 출처 날 · 네이버 확인: 같음 {ck.get('same', '?')} / {ck.get('n', '?')} · 네이버 값 없음 {ck.get('none', '?')}"
                   + (f" ({'; '.join(map(str, nex[:3]))})" if nex else "")
                   + (f" · 다름 {len(diff)}: {'; '.join(map(str, diff[:5]))}" if diff else "")
                   + (f" · 받지 못함 {ck['fail']}" if ck.get("fail") else "") + (f" · 시간 한도로 묻지 못함 {cut}" if cut else "")
                   + (f" · {ck['err']}" if ck.get("err") else "") + f" · 발행 {len(t or []):,}")
            warn = bool(diff or ck.get("none") or cut or ck.get("err") or ck.get("fail") or (pub and not ck.get("n")))
    if odd:
        val += f" (이상: {', '.join(odd)})"
    rep.add(KNX_ROW, True, val, "다름 0 (2차 출처 날: 야후 .KQ × 네이버가 원 단위까지 같은 코넥스만 · 1차 출처 날: 발행한 코넥스를 모두 네이버와 맞춰 봐요 "
            "· 경고만)", warn=warn or bool(odd))


def check_px_src(rep, data, today, mode="publish", own=None):
    """data.json pxSrc · indSrc 줄 (2026-11-19 · 더한 줄만). pxSrc 가 없으면 (예전 발행본 · 시험 데이터) 건너뛰어요.
    own (2026-11-20): 마지막 확인 종가로 맞게 실린 국내 종목 (run_checks 의 kr_own_codes) — 코넥스 줄에 넘겨요 (check_px_knx)."""
    src = data.get("pxSrc")
    if src is None:
        rep.skip("국내 가격 출처 (pxSrc)", "pxSrc 없음 (2026-11-19 전 발행본)")
    else:
        bad = []
        if not isinstance(src, dict) or src.get("v") != 1:
            bad.append("모양")
        else:
            if src.get("px") not in PX_SRCS:
                bad.append(f"px {src.get('px')}")
            if day(src.get("date")) != day(data.get("pxDate")):
                bad.append(f"date {src.get('date')}")
            if not isinstance(src.get("n"), dict) or not all(isinstance(v, int) and v >= 0 for v in src["n"].values()):
                bad.append("n")
            if not isinstance(src.get("must"), list):
                bad.append("must")
            fb = src.get("fb")
            if src.get("px") == PX_SRC_FB and not (isinstance(fb, dict) and all(isinstance(fb.get(k), int) and fb[k] >= 0
                                                                               for k in ("n", "conf", "noDaum", "bad", "noYahoo", "diff"))):
                bad.append("fb")
        n = (src.get("n") or {}) if isinstance(src, dict) else {}
        rep.add("국내 가격 출처 (pxSrc)", not bad, " · ".join(f"{k} {v:,}" for k, v in n.items() if isinstance(v, int)) or "?",
                f"{' · '.join(PX_SRCS)} 중 하나 · pxDate 와 같은 날" + (f" (이상: {', '.join(bad)})" if bad else ""))
        if isinstance(src, dict) and src.get("px") == PX_SRC_FB:
            fb = src.get("fb") if isinstance(src.get("fb"), dict) else {}
            must = src.get("must") if isinstance(src.get("must"), list) else ["?"]
            rep.add("필수 종목 두 출처 확인", not must, "모두 확인" if not must else "확인 못 함: " + ",".join(map(str, must)), ",".join(MUST))
            left = sum(fb.get(k) or 0 for k in ("noDaum", "bad", "noYahoo", "diff"))
            rep.add("2차 출처 두 종가가 다른 종목 (경고만)", True,
                    f"다름 {fb.get('diff', '?')} · 빠짐 모두 {left:,} (다음 행 없음 {fb.get('noDaum', '?')} · 야후 없음 {fb.get('noYahoo', '?')})"
                    + (f" 예: {'; '.join(map(str, (fb.get('diffEx') or [])[:3]))}" if fb.get("diffEx") else ""), "0", warn=bool(fb.get("diff")))
        elif isinstance(src, dict) and src.get("px") == PX_SRC_LISTING:
            ck = src.get("chk")
            if not isinstance(ck, dict):
                rep.add("1차 출처 야후 확인 (경고만)", True, "확인하지 않음", "필수 종목 + 표본", warn=True)
            else:
                diff = ck.get("diff") or []
                rep.add("1차 출처 야후 확인 (경고만)", True,
                        f"같음 {ck.get('same', 0)} / {ck.get('n', 0)}" + (f" · 다름 {len(diff)}: {'; '.join(map(str, diff[:3]))}" if diff else "")
                        + (f" · {ck['err']}" if ck.get("err") else ""), "다름 0", warn=bool(diff) or not (ck.get("n") or 0))
    check_px_knx(rep, data, src, own=own)   # 2026-11-20: 코넥스 종가 두 출처 (경고만 · 마지막 확인 종가로 맞게 실린 코넥스는 빼고 맞춰 봐요)
    check_px_cut(rep, src)
    ind = data.get("indSrc")
    if not isinstance(ind, dict):
        rep.skip("국내 업종 이어 쓴 종목 (경고만)", "indSrc 없음 (2026-11-19 전 발행본)")
    else:
        carried = ind.get("carried") if isinstance(ind.get("carried"), int) else None
        asof = day(ind.get("asOf"))
        age = (today - asof).days if asof else None
        old = carried and (age is None or age > IND_CARRY_WARN_DAYS)
        # 2026-11-19: DART 로 채운 종목도 이 줄에 이름을 적고 경고해요 (채운 것 자체가 KRX 글자가 없다는 뜻 · 더 엄격하게만)
        dart = ind.get("dart") if isinstance(ind.get("dart"), int) else None
        dnames = ind_dart_names(data, ind)
        rep.add("국내 업종 이어 쓴 종목 (경고만)", True,
                f"이어 씀 {carried} · 업종 글자 날짜 {ind.get('asOf')}" + (f" ({age}일 전)" if age is not None else "")
                + f" · 업종 없는 새 상장 {ind.get('newNone')}"
                + (f" · DART 회사 정보로 채움 {dart}" + (f" ({', '.join(dnames[:5])}{' …' if len(dnames) > 5 else ''})" if dnames else "")
                   if dart is not None else ""),
                f"0 (이어 쓰거나 DART 로 채우면 경고 · {IND_CARRY_WARN_DAYS}일 넘으면 더 오래됨)",
                warn=bool(carried) or carried is None or bool(dart))
        if old:
            notes_ = f"이어 쓴 업종 글자가 {age}일 전 것이에요"
            rep.detail("국내 업종 글자가 오래됨", [notes_])
        check_ind_dart(rep, data, ind, mode=mode)


IND_MISS_KO = {"noCode": "DART 업종 코드 없음", "noName": "11차 산업분류표에 없는 코드", "noGroup": "2.0 업종 그룹 없음",
               "mapNone": "우리 업종에 짝이 없는 코드", "mapAmbig": "두 업종 체계가 갈리는 코드", "mapFin": "금융 업종 코드 (채우지 않음)",
               "mapFund": "집합 투자업 코드 (펀드일 수 있어 채우지 않음)", "noParse": "설명을 읽지 못함",
               "prefNoCommon": "우선주의 보통주가 목록에 없음", "prefCommonNone": "보통주도 업종 글자 없음",
               "prefOver": "고정표에서 보통주와 다른 그룹으로 정한 우선주", "dropped": "검사에서 되돌림",
               "noTable": "업종 표를 읽지 못해 채우지 않음",
               "fund": "펀드"}   # indSrc.dartMiss 의 이유
IND_MISS_OK = ("fund",)   # 업종 글자가 없는 게 맞는 종류 — left 에 세지 않아요
IND_FILL_CHECK = "국내 업종 DART 로 채운 값"    # 관문 줄 · 파이프라인 로그의 이름 (DART 로 채운 보통주 + 보통주를 따른 우선주)


def ind_dart_names(data, ind):
    """indSrc.dartT 종목의 '코드 이름' (로그 · 관문 줄에 적어요)."""
    dt_ = ind.get("dartT") if isinstance(ind.get("dartT"), dict) else {}
    nk = {s.get("t"): s.get("nk") for s in data.get("stocks", []) if s.get("cls") == "kr"}
    return [f"{t} {nk.get(t) or '?'}" for t in sorted(dt_)]


# 국내 종목 한 줄 설명 '업종 · 주요제품: … · 시장 상장 · 시가총액' 의 뒤쪽 (2026-11-19 · fetch_data.kr_desc_text 가 만드는 글 · 읽는 코드는 여기 하나)
KR_DESC_TAIL = re.compile(r"(?: · (?:KOSPI|KOSDAQ|KOSDAQ GLOBAL|KONEX) 상장)?(?: · 시가총액 [0-9,.]+(?:조원|억원))?$")


def kr_desc_parse(dk):
    """지난 발행본의 dk ('업종 · 주요제품: … · 시장 상장 · 시가총액') → (업종, 주요제품). kr_desc_text 로 다시 만들어 같은 글이 나올 때만
    (업종 이름에 ' · ' 가 들어 있어도 돼요 — '전동기, 발전기 및 전기 변환 · 공급 · 제어 장치 제조업'). 못 읽으면 None. (순수 함수)"""
    if not isinstance(dk, str):
        return None
    s = " · " + dk
    m = KR_DESC_TAIL.search(s)
    head, tail = s[:m.start()].removeprefix(" · "), s[m.start():]
    if head.startswith("주요제품: "):
        ind, prod = "", head[len("주요제품: "):]
    elif " · 주요제품: " in head:
        ind, prod = head.split(" · 주요제품: ", 1)
    else:
        ind, prod = head, ""
    back = (" · " + " · ".join(b for b in (ind, f"주요제품: {prod}" if prod else "") if b) if (ind or prod) else "") + tail
    return (ind, prod) if back.removeprefix(" · ") == dk else None


def _ind_words(dk):
    """설명(dk)의 업종 글자 (kr_desc_parse 의 첫 칸 · 못 읽으면 빈 글)."""
    p = kr_desc_parse(dk) if dk else None
    return p[0] if p else ""


def ksic_map_kr_sha(path=KSIC_MAP_KR_CSV, names_path=KSIC_NAMES_CSV, pairs=None):
    """채우기 규칙의 판 — 11차 표 · 업종 표(data/ksic_map_kr.csv) · 두 체계의 짝(IND_SECTOR_KR)을 함께 넣은 sha256 앞 12자리. 채울 때
    indSrc.mapSha 에 남겨요: 규칙이 바뀐 뒤 라이브 관문이 옛 발행본을 새 규칙으로 막지 않게 (리뷰 2026-11-19)."""
    h = hashlib.sha256()
    for p in (names_path, path):
        with open(p, "rb") as f:
            h.update(f.read())
    h.update(json.dumps({k: list(v) for k, v in (IND_SECTOR_KR if pairs is None else pairs).items()}, sort_keys=True).encode())
    return h.hexdigest()[:12]


def ind_fill_bad(stocks, ind, names=None, kmap_kr=None, older=False):
    """2026-11-19 (Jack 의 상시 규칙): 국내 업종을 채운 행 중 틀린 것 [{t, kind, why, num}] — 파이프라인(되돌려요)과 관문이 같은 함수를 써요.
    파일 안에서 틀릴 수 있는 것만 봐요 (리뷰 2026-11-19 · 라이브 관문이 지난 발행본을 다시 볼 때도 같게):
      kind dart (indSrc.dartT {종목: DART 업종 코드}): 발행하는 국내 보통주 · 집합 투자업(642) 코드가 아님 · 업종 키 s 가 그 종목의 2.0 그룹(ind)과
        같은 업종 (IND_SECTOR_KR — 금융 그룹 · 금융 키는 짝이 없어 여기서 걸려요) · 설명의 업종 글자 = 그 코드의 11차 소분류 이름 (names).
        업종 표의 상태(status) · 표에 없는 코드 · 짝이 안 맞음도 '숫자가 틀림' — 단 older (라이브 관문이 본 파일이 지금과 다른 규칙 판으로
        채웠다고 적혀 있을 때만 · 리뷰 2026-11-19)이면 경고만. 기타 · 금융 키 · 앱이 모르는 키 · 금융 그룹 · 그룹 없음은 늘 '숫자가 틀림'.
      kind pref (indSrc.prefT {우선주: 보통주}): 같은 회사 · 보통주와 같은 업종 키 · 2.0 그룹 · 업종 글자 (표가 필요 없어요).
    num: 남아 있으면 틀린 숫자가 보이는지 (업종 키 · 2.0 그룹 → 업종 평균 · 중간값 · EV 멀티플 · 업종별 등락) — 글자 · 기록만 틀리면 False.
    names · kmap_kr 가 None 이면 (표를 읽지 못함) 그 표가 필요한 확인만 건너뛰어요. (순수 함수)"""
    by_t = {s.get("t"): s for s in stocks if s.get("cls") == "kr"}
    out = []
    strict = not older
    later = "" if strict else " — 채운 뒤 규칙이 바뀌었어요"

    def bad(t, kind, why, num):
        out.append({"t": t, "kind": kind, "why": why, "num": num})
    for key, kind in (("dartT", "dart"), ("prefT", "pref")):
        m = ind.get(key)
        if key in ind and not isinstance(m, dict):
            bad(key, kind, f"{key} 모양", False)
            continue
        m = m or {}
        n = ind.get(kind)
        if key in ind and n != len(m):
            bad(key, kind, f"{kind} {n} ≠ {key} {len(m)}", False)
        for t, v in sorted(m.items()):
            s = by_t.get(t)
            if s is None or s.get("etf") or s.get("fund"):
                bad(t, kind, "발행한 국내 주식이 아님", False)
                continue
            pref = len(t) == 6 and t[-1] != "0"
            words = _ind_words(s.get("dk"))
            if kind == "dart":
                code = v if isinstance(v, str) else ""
                c3 = code[:IND_DART_DIGITS] if len(code) >= IND_DART_DIGITS else ""
                row = (kmap_kr or {}).get(c3)
                if pref:
                    bad(t, kind, "우선주 (DART 로 채우지 않아요)", True)
                elif c3.startswith(IND_FUND_KSIC):
                    bad(t, kind, f"코드 {code} 는 집합 투자업 (채우지 않아요)", True)
                elif s.get("s") not in IND_SECTOR_KR.get(s.get("ind"), ()):
                    # 기타 · 금융 키 · 앱이 모르는 키 · 금융 그룹 · 그룹 없음은 늘 실패 (규칙이 바뀌어도 틀린 값). 보통 키 · 보통 그룹이 짝만 안
                    # 맞으면 발행 때는 실패, 라이브 관문이 옛 판의 채움을 볼 때(older)만 경고 — 나중에 짝을 좁히거나 () 로 둬도 지난 파일로 배포가 막히지 않게
                    hard = (s.get("s") not in OLD_SECTOR_KEYS or s.get("s") == "etc" or s.get("s") in IND_FIN_SECS
                            or not s.get("ind") or s.get("ind") in IND_FIN_GROUPS)
                    bad(t, kind, f"업종 키 {s.get('s')} 가 2.0 그룹 {s.get('ind')} 와 맞지 않음" + ("" if hard else later), hard or strict)
                elif names is not None and c3 not in names:
                    bad(t, kind, f"코드 {code or '없음'} 이 산업분류표에 없음" + later, strict)
                elif names is not None and words != names[c3]:
                    bad(t, kind, f"설명 업종 '{words[:30]}' ≠ {names[c3]}", False)
                elif kmap_kr is not None and (row is None or row["status"] != "ok"):
                    st = row["status"] if row else "표에 없음"
                    bad(t, kind, f"코드 {code} 는 깔끔히 맞지 않음 ({st})" + later, strict)
            else:
                c = by_t.get(v) if isinstance(v, str) else None
                if not pref or v != t[:5] + "0" or c is None:
                    bad(t, kind, f"보통주 {v} 가 이 우선주의 보통주가 아님", True)
                elif s.get("s") != c.get("s") or s.get("ind") != c.get("ind"):
                    bad(t, kind, f"업종 키 · 2.0 그룹 {s.get('s')}/{s.get('ind')} ≠ 보통주 {c.get('s')}/{c.get('ind')}", True)
                elif not words or words != _ind_words(c.get("dk")):
                    bad(t, kind, f"업종 글자 '{words[:30]}' ≠ 보통주 '{_ind_words(c.get('dk'))[:30]}'", False)
    return out


def ind_fill_rows(bad, stocks):
    """로그 · 기록에 쓰는 '종목 이름: 이유' (앞 30개)."""
    nk = {s.get("t"): s.get("nk") for s in stocks if s.get("cls") == "kr"}
    return [f"{b['t']} {nk.get(b['t']) or ''}: {b['why']}".replace("  ", " ") for b in bad[:30]]


def check_ind_dart(rep, data, ind, names=None, kmap_kr=None, map_sha=None, mode="publish"):
    """2026-11-19: 국내 업종을 채운 값 (DART 로 채운 보통주 indSrc.dartT · 보통주를 따른 우선주 indSrc.prefT) — Jack 의 상시 규칙 (답 1,
    "#146's one"): 파이프라인이 같은 함수(ind_fill_bad)로 틀린 행을 되돌리고 ownDrop.indFill {n, rows} 에 남겨요. 실패는 두 가지뿐: 되돌린 수가
    IND_FILL_MAX 보다 많을 때 · 틀린 행이 남아 있고 그게 틀린 숫자를 보여 줄 때 (num). 경고: 1~N 행을 되돌림 · 숫자와 상관없는 틀린 행이
    남음 · 기록이 없음 · 표를 읽지 못함 · 채우기 고장(dartErr). 업종 글자 없는 종목은 다음 줄 (경고만). dartT 가 없으면 (예전 발행본 · 시험
    데이터) 예전처럼 건너뛰어요.
    mode: 발행 전(publish)에는 늘 엄격해요. 라이브(live)에서 파일이 지금과 다른 규칙 판(indSrc.mapSha)을 적었고 관문이 지금 판을 알 때만
    (표를 읽었을 때) 짝 · 표 상태 · 표에 없는 코드를 경고로 봐요 — 판이 없거나 표를 읽지 못하면 엄격해요 (리뷰 2026-11-19)."""
    if "dartT" not in ind:
        rep.skip(IND_FILL_CHECK, "indSrc.dartT 없음 (DART 채우기 전 발행본)")
        rep.skip("국내 업종 글자 없는 종목 (경고만)", "indSrc.left 없음 (DART 채우기 전 발행본)")
        return
    want = f"되돌림 ≤ {IND_FILL_MAX} · 숫자가 틀리는 값 0 (11차 코드 → 우리 업종 표 · 우선주 = 보통주)"
    stocks = data.get("stocks", [])
    rec = (data.get("ownDrop") or {}).get("indFill") if isinstance(data.get("ownDrop"), dict) else None
    n_drop = rec.get("n") if isinstance(rec, dict) and isinstance(rec.get("n"), int) else None
    table_ok = True
    try:
        if names is None or kmap_kr is None or map_sha is None:
            names = load_ksic_names() if names is None else names
            kmap_kr = load_ksic_map_kr(names=names) if kmap_kr is None else kmap_kr
            map_sha = ksic_map_kr_sha() if map_sha is None else map_sha
    except Exception as e:
        table_ok, names, kmap_kr, map_sha = False, None, None, None
        rep.detail(f"{IND_FILL_CHECK}: 표를 읽지 못했어요", [f"{type(e).__name__}: {str(e)[:120]}"])
    older = mode == "live" and table_ok and map_sha is not None and bool(ind.get("mapSha")) and ind.get("mapSha") != map_sha
    bad = ind_fill_bad(stocks, ind, names, kmap_kr, older=older)      # 표가 없어도 우선주 · 짝 확인은 해요 (엄격)
    n_dart = len(ind.get("dartT") or {}) if isinstance(ind.get("dartT"), dict) else 0
    n_pref = len(ind.get("prefT") or {}) if isinstance(ind.get("prefT"), dict) else 0
    num = [b for b in bad if b["num"]]
    fail = (n_drop is not None and n_drop > IND_FILL_MAX) or bool(num)
    warn = not fail and (bool(bad) or n_drop is None or n_drop > 0 or not table_ok or bool(ind.get("dartErr")))
    value = (f"DART {n_dart}종목 · 우선주 {n_pref} · 되돌림 {n_drop if n_drop is not None else '기록 없음'}"
             + (f" · 남은 틀린 값 {len(bad)} (숫자가 틀림 {len(num)}): " + "; ".join(ind_fill_rows(bad, stocks)[:4]) if bad else "")
             + ("" if table_ok else " · 표를 읽지 못해 우선주 · 짝만 확인")
             + (f" · 옛 규칙 판 {ind.get('mapSha')} (지금 {map_sha}) — 짝 · 표는 경고만" if older else "")
             + (f" · 채우기 고장 {ind.get('dartErr')}" if ind.get("dartErr") else ""))
    rep.add(IND_FILL_CHECK, not fail, value, want, warn=warn)
    if bad:
        rep.detail(f"{IND_FILL_CHECK}: 남은 틀린 값", ind_fill_rows(bad, stocks))
    if n_drop:
        rep.detail(f"{IND_FILL_CHECK}: 파이프라인이 되돌린 행 {n_drop}", [str(x) for x in (rec.get("rows") or [])][:30])
    left = ind.get("left")
    miss = ind.get("dartMiss") if isinstance(ind.get("dartMiss"), dict) else {}
    why = " · ".join(f"{IND_MISS_KO.get(k, k)} {v}" for k, v in sorted(miss.items()) if k not in IND_MISS_OK and v)
    ok_ = " · ".join(f"{IND_MISS_KO[k]} {miss[k]}" for k in IND_MISS_OK if miss.get(k))
    rep.add("국내 업종 글자 없는 종목 (경고만)", True,
            f"{left}" + (f" ({why})" if why else "") + (f" · 세지 않음: {ok_} (업종이 없는 게 맞아요)" if ok_ else "")
            + (f" · 채우기 실패 {ind.get('dartErr')}" if ind.get("dartErr") else ""),
            "0 (KRX · 지난 발행본 · DART · 보통주 모두 없음 · 펀드 빼고)",
            warn=not isinstance(left, int) or left > 0 or bool(ind.get("dartErr")))


# ── 검사 ────────────────────────────────────────────────────
def prev_px_date(prev, notes):
    """직전 발행본의 가격 날짜. 예전 형식(pxDate 없음)이면 asOf − 1일 (실행일 아침 기준이라 하루 전 가격)."""
    if prev.get("pxDate"):
        return day(prev["pxDate"])
    if prev.get("asOf"):
        notes.append(f"직전 발행본에 pxDate 가 없어(예전 형식) asOf {prev['asOf']} − 1일을 가격 날짜로 봐요")
        return day(prev["asOf"]) - dt.timedelta(days=1)
    return None


def kr_stocks(data):
    return [s for s in data.get("stocks", []) if s.get("cls") == "kr" and not s.get("fund")]


def us_stocks(data):
    return [s for s in data.get("stocks", []) if s.get("cls") == "us" and not s.get("fund")]


# ── 2026-11-19 (Jack): 국내 종목의 마지막 확인 종가 (pxd) — 파이프라인(fetch_data.kr_own_close_carry)이 같은 함수로 거르고 관문이 줄을 만들어요 ──
def kr_pxd_shape_ok(s, px):
    """국내 종목의 pxd 가 진짜 날짜(YYYY-MM-DD)이고 pxDate(px: 'YYYY-MM-DD' 또는 date)보다 앞인지. (순수 함수)"""
    d = _iso_day(s.get("pxd")) if isinstance(s, dict) else None
    p = px if isinstance(px, dt.date) else _iso_day(px)
    return d is not None and p is not None and d < p


def kr_px_count(data):
    """pxDate 종가로 실은 국내 종목 수 (2026-11-20 · #159 리뷰): 국내 종목 중 pxd 가 없는 것 — 마지막 확인 종가(pxd)로 실은 종목은 깨끗하든 아니든
    세지 않아요 ('국내 종목 수' 두 줄 · 늦추지 않게). (순수 함수)"""
    return sum(1 for s in kr_stocks(data) if s.get("pxd") is None)


def kr_own_rec(data):
    """data.json pxSrc.own (2차 출처 날에 마지막 확인 종가로 실은 국내 종목의 기록) — 모양이 맞으면 dict, 아니면 None. (순수 함수)"""
    src = (data or {}).get("pxSrc")
    own = src.get("own") if isinstance(src, dict) else None
    if not (isinstance(own, dict) and own.get("v") == 1 and isinstance(own.get("codes"), list)
            and all(isinstance(c, str) and c for c in own["codes"]) and len(set(own["codes"])) == len(own["codes"])
            and isinstance(own.get("n"), int) and not isinstance(own.get("n"), bool) and own["n"] == len(own["codes"])):
        return None
    return own


def kr_own_codes(data, pdata=None, days=None):
    """기록대로 마지막 확인 종가(pxd)로 실린 국내 종목 코드 set. 이 종목들의 가격은 pxDate 의 종가가 아니라서 pxDate 공식 종가와 맞춰 보는 줄
    (한국 가격 = 공식 종가 · 2차 출처 확인 수 · 관문 표본)에서 빠져요. kr_own_close_bad 가 아무 까닭도 대지 않는 종목만: 국내 종목 · pxd 가
    pxDate 보다 앞선 날짜 · d1 · d1Why · noTrade · ntD1 없음 · 가격 있음 · pxSrc 가 2차 출처 · pxSrc.own 에 그 코드가 있음 · (days 가 있으면) 나이
    상한 안 · (pdata 가 있으면) 지난 발행본의 가격과 날짜 그대로. 하나라도 아니면 예전 그대로 pxDate 의 가격으로 봐요 (틀린 가격이면 그 줄들이
    잡아요 — 늦추는 곳이 없어요). pdata: 지난 발행본 data.json · days: 거래일 YYYY-MM-DD 들. (순수 함수)"""
    src = data.get("pxSrc") if isinstance(data.get("pxSrc"), dict) else {}
    if kr_own_rec(data) is None or src.get("px") != PX_SRC_FB:
        return set()
    mine = {s.get("t") for s in kr_stocks(data) if s.get("pxd") is not None}
    return mine - {t for t, _ in kr_own_close_bad(data, pdata, days)} if mine else set()


def kr_own_pick_data(data, pdata=None, days=None):
    """관문 표본(px_alt_pick · http_px_alt)이 읽을 data: pxSrc.own.codes 에 맞게 실린 종목(kr_own_codes — 지난 발행본 · 거래일까지 본 것)만 남긴
    얕은 사본 (2026-11-19). 어긋난 종목은 표본에 들어가 pxDate 의 가격으로 맞춰 봐요. 기록이 없거나 모두 맞으면 data 그대로. (순수 함수)"""
    own = kr_own_rec(data)
    if own is None:
        return data
    ok = kr_own_codes(data, pdata, days)
    codes = [c for c in own["codes"] if c in ok]
    if len(codes) == len(own["codes"]):
        return data
    return {**data, "pxSrc": {**data["pxSrc"], "own": {**own, "codes": codes, "n": len(codes)}}}


def kr_days_of(macro):
    """macro.json 의 KOSPI 일봉 날짜들 (YYYY-MM-DD · 거래일) — 마지막 확인 종가의 나이를 세요. 없으면 None. (순수 함수)"""
    rows = (((macro or {}).get("idxHist") or {}).get("KOSPI") or {}).get("rows") or []
    ds = sorted({str(r[0]) for r in rows if isinstance(r, (list, tuple)) and r and is_day(r[0])})
    return ds or None


def kr_own_age(pxd, px, days):
    """그 종가(pxd) 뒤 pxDate(px)까지의 거래일 수 (pxd < 거래일 ≤ px · days: 거래일 YYYY-MM-DD 들). (순수 함수)"""
    a, b = str(pxd), str(px)
    return sum(1 for d in days if a < str(d)[:10] <= b)


def kr_own_close_bad(data, pdata=None, days=None, max_days=KR_OWN_CLOSE_MAX_DAYS):
    """마지막 확인 종가(pxd)로 실린 국내 종목 중 맞지 않는 것 → [(코드, 까닭)] (까닭은 KR_OWN_WHY 의 키 · 한 종목에 여럿일 수 있어요).
    파이프라인이 파일을 쓰기 직전에 같은 함수로 거르고 (그 종목은 빼고 크게 남겨요), 관문이 남은 것을 줄로 만들어요 (Jack 의 규칙, 2026-11-19).
    shape · d1 은 미국 pxd 줄과 같은 실패, 나머지는 경고예요.
    pdata: 지난 발행본 data.json (있으면 그 가격 · 날짜를 이어 받았는지 봐요 — 그 발행본에 기준일 종가로 있었으면 pxd = 그 pxDate, 이미 pxd 로
    있었으면 같은 pxd · 같은 가격) · days: 거래일 YYYY-MM-DD 들 (없으면 나이를 보지 않아요). (순수 함수)"""
    out = []
    px = data.get("pxDate")
    src = data.get("pxSrc") if isinstance(data.get("pxSrc"), dict) else {}
    own = kr_own_rec(data)
    rec = set(own["codes"]) if own else set()
    fb = src.get("px") == PX_SRC_FB
    pby = {x.get("t"): x for x in kr_stocks(pdata)} if isinstance(pdata, dict) else None
    ppx = str(pdata.get("pxDate")) if isinstance(pdata, dict) else None
    for s in kr_stocks(data):
        if s.get("pxd") is None:
            continue
        t, why = s.get("t"), []
        shape = kr_pxd_shape_ok(s, px)
        if not shape:
            why.append("shape")
        if s.get("d1") is not None:
            why.append("d1")
        if any(k in s for k in ("d1Why", "noTrade", "ntD1")):
            why.append("mark")
        if not (num(s.get("price")) or 0) > 0:
            why.append("price")
        if not fb:
            why.append("src")
        elif t not in rec:
            why.append("rec")
        if shape and days is not None and kr_own_age(s["pxd"], px, days) > max_days:
            why.append("old")
        if pby is not None:
            p = pby.get(t)
            same_px = p is not None and num(p.get("price")) is not None and num(p.get("price")) == num(s.get("price"))
            same_day = p is not None and (s.get("pxd") == p.get("pxd") if p.get("pxd") is not None else s.get("pxd") == ppx)
            if not (same_px and same_day):
                why.append("prev")
        out += [(t, w) for w in why]
    return out


def check_kr_own_close(rep, data, macro, pdata):
    """2026-11-19 (Jack): 국내 종목의 마지막 확인 종가 (pxd). 두 줄:
    - '국내 자기 가격 날짜 (pxd)' — 미국 pxd 줄과 같은 규칙 · 같은 실패: pxd 가 있는 국내 종목은 pxd 가 pxDate 보다 앞선 날짜이고 d1 이 없어야 해요
      (앱이 그 날짜와 Jack 의 줄을 보여요). 새 실패 조건을 더하지 않았어요 — 미국 줄이 이미 실패시키는 것과 같은 것만.
    - '국내 마지막 확인 종가 (pxSrc.own · 경고만)' — 기록에 있는 종목인지 · 2차 출처 날인지 · 나이 상한 · 지난 발행본의 가격 · 날짜를 이어 받았는지 ·
      파이프라인이 거른 종목 (Jack 의 규칙 2026-11-19: 한 줄이 틀리면 그 줄을 빼고 크게 남겨요). 경고만이에요: 그런 종목은 kr_own_codes 에 들지 않아서
      pxDate 의 가격으로 보고 '한국 가격 = 공식 종가' 줄들이 예전 그대로 맞춰 봐요.
    pdata: 지난 발행본 (발행 모드에서만, 아니면 None)."""
    name, oname = "국내 자기 가격 날짜 (pxd)", "국내 마지막 확인 종가 (pxSrc.own · 경고만)"
    px = str(data.get("pxDate") or "")
    kr = kr_stocks(data)
    by = {s.get("t"): s for s in kr}
    mine = [s for s in kr if s.get("pxd") is not None]
    bad = kr_own_close_bad(data, pdata, kr_days_of(macro))

    def nm(t):
        return f"{t} {(by.get(t) or {}).get('nk', '')}".strip()

    def listed(pairs):
        items = [f"{nm(t)}: {KR_OWN_WHY.get(w, w)}" for t, w in pairs]
        return " · ".join(items[:KR_OWN_SHOW]) + (f" 외 {len(items) - KR_OWN_SHOW}건" if len(items) > KR_OWN_SHOW else "")
    hard = [(t, w) for t, w in bad if w in KR_OWN_FAIL_WHY]
    soft = [(t, w) for t, w in bad if w not in KR_OWN_FAIL_WHY]
    days = collections.Counter(str(s.get("pxd")) for s in mine)
    shown = " · ".join(f"{d} {n}종목" for d, n in sorted(days.items(), reverse=True))
    src = data.get("pxSrc") if isinstance(data.get("pxSrc"), dict) else {}
    raw = src.get("own")
    own = kr_own_rec(data)
    # 2026-11-20 (Jack, d): the rows the pipeline dropped in this run (pxSrc.own.bad) — warn, fail only above KR_OWN_DROP_MAX
    obad = own.get("bad") if own is not None and isinstance(own.get("bad"), dict) else {}
    dropped = obad["n"] if isinstance(obad.get("n"), int) and not isinstance(obad.get("n"), bool) and obad["n"] > 0 else 0
    drows = obad.get("rows") if isinstance(obad.get("rows"), list) else []
    why = obad.get("why") if isinstance(obad.get("why"), dict) else {}
    per = {str(k): v for k, v in why.items() if isinstance(v, int) and not isinstance(v, bool) and v > 0}
    counted = per if dropped and not (own or {}).get("err") else {}
    worst = max(counted.items(), key=lambda kv: kv[1]) if counted else None
    over = bool(worst) and worst[1] > KR_OWN_DROP_MAX
    value = listed(hard) if hard else (f"{len(mine)}종목 ({shown})" if mine else "없음 (모두 기준일 종가)")
    if dropped:
        value += (f" · 파이프라인이 거른 종목 {dropped}"
                  + (" (" + " · ".join(f"{KR_OWN_WHY.get(k, k)} {v}" for k, v in sorted(counted.items())) + ")" if counted
                     else " (단계가 멈춰 모두 뺌 · 세지 않음)" if (own or {}).get("err") else " (까닭별 수 없음 · 세지 않음)")
                  + ": " + ", ".join(map(str, drows[:KR_OWN_SHOW])))
    rep.add(name, not hard and not over, value,
            f"pxd 가 있는 국내 종목은 pxd < {px} · d1 없음 (미국 pxd 줄과 같아요) · 파이프라인이 한 점검에서 거른 종목 {KR_OWN_DROP_MAX}개 이하 (넘으면 실패 · 있으면 경고)",
            warn=bool(dropped) and not hard and not over)
    if hard:
        rep.detail("국내 자기 가격 날짜가 맞지 않는 종목 (우리 코드의 잘못)", [f"{nm(t)}: {KR_OWN_WHY.get(w, w)}" for t, w in hard])
    if over:
        rep.detail(f"파이프라인이 한 점검('{KR_OWN_WHY.get(worst[0], worst[0])}')에서 거른 마지막 확인 종가 종목이 {KR_OWN_DROP_MAX}개를 넘어요 ({worst[1]}) — "
                   "한 종목이 아니라 그 점검이 고장 났어요", [str(x) for x in drows])
    orule = (f"pxd 가 있는 국내 종목은 2차 출처 날 · pxSrc.own 에 있는 종목 · 그 종가 뒤 거래일 {KR_OWN_CLOSE_MAX_DAYS}일 이하 · 지난 발행본의 가격과 날짜 "
             "그대로 · 파이프라인이 거른 종목 0 (어긋나면 경고 · 그 종목은 pxDate 의 가격으로 보고 가격 줄들이 맞춰 봐요)")
    # 2026-11-20: data.json ownDrop.krOwn (다른 우리 처리 검사와 같은 곳) 이 pxSrc.own.bad 와 같은 수인지 (경고만 · 없으면 이 기록 전 파일).
    # 리뷰 (#159): 기록 · pxd 종목이 없는 날 (평소 날) 에도 봐요 — 그날은 0 이어야 해요
    od = own_drop_get(data, KR_OWN_DROP_KEY)
    od_part = (f"ownDrop.{KR_OWN_DROP_KEY} 모양이 잘못됨" if od is False
               else f"ownDrop.{KR_OWN_DROP_KEY} {od['n']} ≠ pxSrc.own.bad {dropped}" if isinstance(od, dict) and od["n"] != dropped else None)
    if raw is None and not mine:
        rep.add(oname, True, "없음 (모두 기준일 종가)" + (f" · {od_part}" if od_part else ""), orule, warn=bool(od_part))
        return
    parts, warn = [], bool(soft)
    if raw is not None and own is None:
        parts.append("pxSrc.own 모양이 잘못됨")
        warn = True
    if own is not None:
        drop = own.get("drop") if isinstance(own.get("drop"), dict) else {}
        parts.append(f"실음 {own['n']}종목" + (f" ({shown})" if shown else "")
                     + f" · 확인 못 한 종목 {own['unconf'] if isinstance(own.get('unconf'), int) else '모름'}"
                     + (" · 싣지 못함 " + " · ".join(f"{k} {v}" for k, v in sorted(drop.items())) if drop else ""))
        if own.get("err"):                 # 파이프라인의 마지막 확인 종가 단계가 오류로 멈춤 → 실은 종목 없이 발행 (예전처럼 빠져요)
            parts.append(f"단계가 오류로 멈춤 (실은 종목 없음): {str(own['err'])[:120]}")
            warn = True
        pbad = own.get("bad") if isinstance(own.get("bad"), dict) else {}
        if isinstance(pbad.get("n"), int) and pbad["n"] > 0:
            rows = pbad.get("rows") if isinstance(pbad.get("rows"), list) else []
            parts.append(f"파이프라인이 거른 종목 {pbad['n']}: " + ", ".join(map(str, rows[:KR_OWN_SHOW])))
            warn = True
        # 2026-11-20 (Jack, a): 나이 상한을 넘어 잠시 뺀 종목 (pxSrc.own.aged · 앱이 그 종목 자리에 Jack 의 줄) — 모양이 틀리거나 발행하는 종목이면 경고
        aged = own.get("aged")
        if aged is not None:
            ok_a = isinstance(aged, list) and all(isinstance(a, dict) and isinstance(a.get("t"), str) and a["t"] for a in aged)
            inside = sorted({a["t"] for a in aged if a["t"] in by}) if ok_a else []
            parts.append(f"{KR_OWN_CLOSE_MAX_DAYS}거래일이 지나 잠시 뺀 종목 {len(aged) if ok_a else '?'}"
                         + (f" ({', '.join(a['t'] + ' ' + str(a.get('nk') or '') for a in aged[:KR_OWN_SHOW])})" if ok_a and aged else "")
                         + ("" if ok_a else " · 모양이 잘못됨") + (f" · 그런데 발행하는 종목: {', '.join(inside)}" if inside else ""))
            warn = warn or not ok_a or bool(inside)
        # 2026-11-20 (#159 × #158 · 경고만): 확인 못 한 코넥스 수 (unconfWhy.knx) 가 #158 의 기록 (pxSrc.fb.knx.left) 과 같은지 — 야후 .KQ × 네이버로
        # 확인된 코넥스는 마지막 확인 종가 단계로 가지 않아요 (fetch_data.kr_unconfirmed)
        uw = own.get("unconfWhy")
        fbk = (src.get("fb") or {}).get("knx") if isinstance(src.get("fb"), dict) else None
        kk = src.get("knx") if isinstance(src.get("knx"), dict) else {}
        if uw is not None and not (isinstance(uw, dict) and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in uw.values())):
            parts.append("unconfWhy 모양이 잘못됨")
            warn = True
        elif isinstance(uw, dict) and kk.get("px") == PX_SRC_KNX and isinstance(fbk, dict) and isinstance(fbk.get("left"), list):
            if uw.get("knx", 0) != len(fbk["left"]) or uw.get("mkt", 0):
                parts.append(f"확인 못 한 코넥스 {uw.get('knx', 0)} · 그 밖 시장 {uw.get('mkt', 0)} ≠ 코넥스 2차 출처의 빠진 종목 {len(fbk['left'])} (pxSrc.fb.knx.left)")
                warn = True
    if od_part:
        parts.append(od_part)
        warn = True
    if soft:
        parts.append(f"어긋남 {len(soft)}: {listed(soft)}")
        rep.detail("마지막 확인 종가 기록과 어긋난 국내 종목 (pxDate 의 가격으로 보고 맞춰 봐요)", [f"{nm(t)}: {KR_OWN_WHY.get(w, w)}" for t, w in soft])
    rep.add(oname, True, " · ".join(parts) or "?", orule, warn=warn)


# ── 2026-11-20 (Jack): 미국 종목의 마지막 확인 종가 (pxd · pxc) — 파이프라인(fetch_data.us_own_close_carry)이 같은 함수로 거르고 관문이 줄을 만들어요 ──
def us_own_rec(data):
    """data.json usSrc.own (야후 종가가 없어 마지막 확인 종가로 실은 미국 종목의 기록) — 모양이 맞으면 dict, 아니면 None. (순수 함수)"""
    src = (data or {}).get("usSrc")
    own = src.get("own") if isinstance(src, dict) else None
    if not (isinstance(own, dict) and own.get("v") == 1 and isinstance(own.get("codes"), list)
            and all(isinstance(c, str) and c for c in own["codes"]) and len(set(own["codes"])) == len(own["codes"])
            and isinstance(own.get("n"), int) and not isinstance(own.get("n"), bool) and own["n"] == len(own["codes"])
            and isinstance(own.get("same", []), list) and all(isinstance(c, str) and c for c in own.get("same", []))
            and isinstance(own.get("newer", []), list) and all(isinstance(x, dict) and isinstance(x.get("t"), str) for x in own.get("newer", []))
            and isinstance(own.get("split", []), list) and all(isinstance(x, dict) and isinstance(x.get("t"), str) for x in own.get("split", []))
            and isinstance(own.get("from", {}), dict)):
        return None
    return own


def us_days_of(macro):
    """macro.json 의 S&P 500 일봉 날짜들 (YYYY-MM-DD · 미국 거래일 · 휴장일엔 봉이 없어요) — 마지막 확인 종가의 나이를 세요. 없으면 None. (순수 함수)"""
    rows = (((macro or {}).get("idxHist") or {}).get("SP500") or {}).get("rows") or []
    ds = sorted({str(r[0]) for r in rows if isinstance(r, (list, tuple)) and r and is_day(r[0])})
    return ds or None


def us_own_close_bad(data, pdata=None, days=None, max_days=US_OWN_CLOSE_MAX_DAYS):
    """마지막 확인 종가로 실린 미국 종목(pxc · usSrc.own.codes)과 같은 날 다시 쓴 종가(usSrc.own.same) 중 맞지 않는 것 → [(티커, 까닭)]
    (까닭은 US_OWN_WHY 의 키 · 한 종목에 여럿일 수 있어요). 파이프라인이 파일을 쓰기 전에 같은 함수로 거르고 (그 행은 빼고 크게 남겨요), 관문이
    남은 것을 줄로 만들어요 (Jack 의 상시 규칙). shape · d1 · mark 는 실패 (국내 pxd 줄과 같아요), 나머지는 경고예요.
    pdata: 지난 발행본 (있으면 그 가격 · 날짜를 이어 받았는지 봐요 — 그 발행본에 usPxDate 종가로 있었으면 pxd = 그 usPxDate, 이미 pxc 로 있었으면
    같은 pxd · 같은 가격 · same 은 지난 발행본의 usPxDate 가 오늘과 같고 그 종목의 가격 · d1 이 그대로) · days: 미국 거래일 YYYY-MM-DD 들
    (없으면 나이를 보지 않아요). 야후의 마지막 봉을 자기 날짜로 실은 종목(pxd 만 · pxc 없음 — 거래 정지)은 여기서 보지 않아요 ('미국 자기 가격 날짜'
    줄이 봐요). (순수 함수)"""
    out = []
    usd = str((data or {}).get("usPxDate") or "")
    own = us_own_rec(data)
    rec = set(own["codes"]) if own else set()
    same = set(own.get("same") or []) if own else set()
    newer = {x["t"]: x for x in (own.get("newer") or [])} if own else {}
    frm = own.get("from") if own and isinstance(own.get("from"), dict) else {}
    pby = {x.get("t"): x for x in us_stocks(pdata)} if isinstance(pdata, dict) else None
    ppx = str(pdata.get("usPxDate")) if isinstance(pdata, dict) else None
    paged = {}
    if isinstance(pdata, dict):
        po = us_own_rec(pdata) or ((pdata.get("usSrc") or {}).get("own") if isinstance(pdata.get("usSrc"), dict) else None)
        paged = {a["t"]: a for a in ((po or {}).get("aged") or []) if isinstance(po, dict) and isinstance(a, dict) and isinstance(a.get("t"), str)}
    splits = collections.defaultdict(set)                 # 리뷰 (2026-11-20): data.json splits [[티커, 날짜, 배율]]
    for x in (data or {}).get("splits") or [] if isinstance((data or {}).get("splits"), list) else []:
        if isinstance(x, (list, tuple)) and len(x) >= 2 and isinstance(x[0], str) and _iso_day(x[1]) is not None:
            splits[x[0]].add(x[1])
    dayset = set(days) if days is not None else None
    for s in us_stocks(data or {}):
        t = s.get("t")
        if t in same and "pxc" not in s:
            p = (pby or {}).get(t)
            ok = (s.get("pxd") is None and num(s.get("d1")) is not None and (num(s.get("price")) or 0) > 0
                  and (pby is None or (ppx == usd and p is not None and p.get("pxd") is None and p.get("pxc") is None
                                       and num(p.get("price")) == num(s.get("price")) and num(p.get("d1")) == num(s.get("d1")))))
            if not ok:
                out.append((t, "same"))
            if own and frm.get(t) not in US_OWN_FROM:
                out.append((t, "from"))
            continue
        if "pxc" not in s and t not in rec:
            continue
        why = []
        if s.get("pxc") is not True or s.get("pxd") is None:
            why.append("mark")
        d, u = _iso_day(s.get("pxd")), _iso_day(usd)
        shape = d is not None and u is not None and d < u
        if s.get("pxd") is not None and not shape:
            why.append("shape")
        if s.get("d1") is not None:
            why.append("d1")
        if not (num(s.get("price")) or 0) > 0:
            why.append("price")
        if t not in rec:
            why.append("rec")
        if own and frm.get(t) not in US_OWN_FROM:
            why.append("from")
        if shape and days is not None and kr_own_age(s["pxd"], usd, days) > max_days:
            why.append("old")
        if isinstance(s.get("pxd"), str) and any(d > s["pxd"] for d in splits.get(t, ())):
            why.append("split")
        if t in newer:
            # 리뷰 (2026-11-20): 야후의 더 새 종가 (그 종목의 마지막 봉) — 기록한 날짜 · 가격 그대로 · 미국 거래일 · 지난 발행본의 그 종목 종가 날짜
            # (pxc 면 그 pxd, 아니면 그 발행본의 usPxDate · 잠시 뺀 종목이면 그 기록의 pxd) 보다 뒤
            x = newer[t]
            ok = x.get("pxd") == s.get("pxd") and num(x.get("px")) is not None and num(x.get("px")) == num(s.get("price"))
            if ok and dayset is not None:
                ok = s.get("pxd") in dayset
            if ok and pby is not None:
                p = pby.get(t)
                base = (p.get("pxd") if p.get("pxc") is True else (None if p.get("pxd") is not None else ppx)) if p is not None \
                    else (paged.get(t) or {}).get("pxd")
                ok = isinstance(base, str) and isinstance(s.get("pxd"), str) and base < s["pxd"]
            if not ok:
                why.append("newer")
        elif pby is not None:
            p = pby.get(t)
            same_px = p is not None and num(p.get("price")) is not None and num(p.get("price")) == num(s.get("price"))
            same_day = p is not None and (s.get("pxd") == p.get("pxd") and p.get("pxc") is True if p.get("pxd") is not None
                                          else s.get("pxd") == ppx)
            if not (same_px and same_day):
                why.append("prev")
        out += [(t, w) for w in why]
    return out


def us_px_count(data):
    """머지 확인 (2026-11-20, 1 · 예전보다 늦추지 않아요): '미국 종목 수' 두 줄이 세는 미국 종목 → (센 수, 세지 않은 마지막 확인 종가 수). 예전에도 실렸을
    행만 세요: pxc 가 없는 행 · 마지막 확인 종가(pxc)와 같은 날 다시 쓴 행(same) 중 야후에 그 종목의 시계열이 있던 것 (usSrc.own.from 'bar' — 예전이면
    야후의 자기 날짜 봉으로 실렸어요). 야후가 아무것도 주지 않은 행(empty · err — 예전이면 빠졌어요)과 까닭이 적혀 있지 않은 행은 세지 않아요 (야후
    다운로드가 통째로 고장 난 날은 예전처럼 이 줄들이 막아요). (순수 함수)"""
    own = us_own_rec(data)
    frm = own.get("from") if own and isinstance(own.get("from"), dict) else {}
    same = set(own.get("same") or []) if own else set()
    n = nc = 0
    for s in us_stocks(data or {}):
        if "pxc" in s or s.get("t") in same:
            if frm.get(s.get("t")) == "bar":
                n += 1
            else:
                nc += 1
        else:
            n += 1
    return n, nc


def check_us_counts(rep, data, pdata):
    """'미국 종목 수' · '미국 종목 수 변화' (기준 그대로 · 머지 확인 2026-11-20: us_px_count 로 세요 — 지난 발행본도 같은 방법)."""
    n, nc = us_px_count(data)
    note = (f" (야후가 아무것도 주지 않아 마지막 확인 종가로 실은 {nc:,}종목은 세지 않아요)" if nc else "")
    rep.add("미국 종목 수", n >= US_MIN, f"{n:,}" + note, f"≥ {US_MIN} (예전에도 실렸을 종목)")
    if pdata:
        pu, pnc = us_px_count(pdata)
        rep.add("미국 종목 수 변화", pu > 0 and abs(n / pu - 1) <= US_REL, f"{pu:,} → {n:,}"
                + (f" (세지 않은 마지막 확인 종가 {pnc:,} → {nc:,})" if pnc or nc else ""), f"±{US_REL:.0%} (예전에도 실렸을 종목)")


def us_own_codes(data, pdata=None, days=None):
    """기록대로 마지막 확인 종가(pxc · pxd)로 실린 미국 종목 티커 set — us_own_close_bad 가 아무 까닭도 대지 않는 종목만 (미국 종목 · pxc true ·
    pxd 가 usPxDate 보다 앞선 날짜 · d1 없음 · 가격 있음 · usSrc.own.codes 에 있음 · (days 가 있으면) 나이 상한 안 · (pdata 가 있으면) 지난 발행본의
    가격과 날짜 그대로). 이 종목들은 오늘(usPxDate) 가격을 보는 줄('미국 d1 채움' 의 빠진 수 · 필수 종목 d1 · 가격이 바뀌었는지)에서 빠져요.
    하나라도 아니면 예전 그대로 봐요. (순수 함수)"""
    mine = {s.get("t") for s in us_stocks(data or {}) if "pxc" in s}
    return mine - {t for t, _ in us_own_close_bad(data, pdata, days)} if mine else set()


def check_us_own_close(rep, data, macro, pdata):
    """2026-11-20 (Jack): 미국 종목의 마지막 확인 종가 (usSrc.own · pxc). 한 줄 '미국 마지막 확인 종가 (usSrc.own · pxc)':
    - 실패: 날짜가 깨졌거나(shape) d1 이 옆에 있거나(d1) 표시가 맞지 않는(mark) 마지막 확인 종가가 파일에 남음 (국내 pxd 줄과 같아요 — 파이프라인이
      같은 함수로 거르니 남으면 그 단계가 고장 났어요) · 파이프라인이 한 점검에서 거른 행이 US_OWN_DROP_MAX 를 넘음 (Jack 의 상시 규칙).
    - 경고: 실은 종목 · 같은 날 다시 쓴 종가 · 거른 행 · 나이 상한을 넘어 잠시 뺀 종목 · 기록과 어긋남 (그 종목은 오늘 가격으로 보고 가격 줄들이 봐요)
      · 단계가 오류로 멈춤. pdata: 지난 발행본 (발행 모드에서만)."""
    name = "미국 마지막 확인 종가 (usSrc.own · pxc)"
    rule = (f"야후 종가가 없는 미국 종목은 지난 발행본의 마지막 확인 종가 (pxc · pxd < usPxDate · d1 없음 · 그 종가 뒤 미국 거래일 "
            f"{US_OWN_CLOSE_MAX_DAYS}일 이하 · 지난 발행본의 가격과 날짜 그대로 — 어긋나면 경고) · 날짜가 깨졌거나 d1 이 옆에 있으면 실패 · "
            f"파이프라인이 한 점검에서 거른 행 {US_OWN_DROP_MAX}개 이하 (넘으면 실패 · 있으면 경고)")
    us = us_stocks(data)
    by = {s.get("t"): s for s in us}
    raw = (data.get("usSrc") or {}).get("own") if isinstance(data.get("usSrc"), dict) else None
    own = us_own_rec(data)
    mine = [s for s in us if "pxc" in s]
    if raw is None and not mine:
        if "usSrc" in data:
            rep.add(name, True, "없음 (모두 미국 기준일 종가)", rule)
        else:
            rep.skip(name, "기록 없음 (data.json usSrc 가 없는 발행본 · 이 칸 전)")
        return
    bad = us_own_close_bad(data, pdata, us_days_of(macro))
    hard = [(t, w) for t, w in bad if w in US_OWN_FAIL_WHY]
    soft = [(t, w) for t, w in bad if w not in US_OWN_FAIL_WHY]

    def listed(pairs):
        items = [f"{t}: {US_OWN_WHY.get(w, w)}" for t, w in pairs]
        return " · ".join(items[:US_OWN_SHOW]) + (f" 외 {len(items) - US_OWN_SHOW}건" if len(items) > US_OWN_SHOW else "")
    obad = own.get("bad") if own is not None and isinstance(own.get("bad"), dict) else {}
    dropped = obad["n"] if isinstance(obad.get("n"), int) and not isinstance(obad.get("n"), bool) and obad["n"] > 0 else 0
    drows = obad.get("rows") if isinstance(obad.get("rows"), list) else []
    per = {str(k): v for k, v in (obad.get("why") or {}).items() if isinstance(v, int) and not isinstance(v, bool) and v > 0} \
        if isinstance(obad.get("why"), dict) else {}
    counted = per if dropped and not (own or {}).get("err") else {}
    worst = max(counted.items(), key=lambda kv: kv[1]) if counted else None
    over = bool(worst) and worst[1] > US_OWN_DROP_MAX
    days = collections.Counter(str(s.get("pxd")) for s in mine)
    parts = []
    if raw is not None and own is None:
        parts.append("usSrc.own 모양이 잘못됨")
    if own is not None:
        dc = own.get("drop") if isinstance(own.get("drop"), dict) else {}
        parts.append(f"실음 {len(mine)}종목" + (" (" + " · ".join(f"{d} {n}종목" for d, n in sorted(days.items(), reverse=True)) + ")" if mine else "")
                     + (f" · 같은 날 지난 발행본 종가 그대로 {len(own.get('same') or [])}" if own.get("same") else "")
                     + (f" · 그중 야후의 더 새 종가 {len(own.get('newer') or [])}" if own.get("newer") else "")
                     + (" · 그 종가 뒤 분할이 있어 싣지 않음 (예전 그대로) " + ", ".join(str(x.get("t")) for x in own.get("split") or []
                                                                       if isinstance(x, dict) and not x.get("unread"))
                        if any(isinstance(x, dict) and not x.get("unread") for x in own.get("split") or []) else "")
                     + (" · 분할 칸을 읽지 못해 싣지 않음 (분할을 몰라요 · 예전 그대로) " + ", ".join(str(x.get("t")) for x in own.get("split") or []
                                                                             if isinstance(x, dict) and x.get("unread"))
                        if any(isinstance(x, dict) and x.get("unread") for x in own.get("split") or []) else "")
                     + f" · 야후 종가 없음 {own['unconf'] if isinstance(own.get('unconf'), int) else '모름'}"
                     + (" · 싣지 못함 " + " · ".join(f"{k} {v}" for k, v in sorted(dc.items())) if dc else ""))
        if own.get("err"):
            parts.append(f"단계가 오류로 멈춤 (실은 종목 없음): {str(own['err'])[:120]}")
        if dropped:
            parts.append(f"파이프라인이 거른 행 {dropped}"
                         + (" (" + " · ".join(f"{US_OWN_WHY.get(k, k)} {v}" for k, v in sorted(counted.items())) + ")" if counted
                            else " (단계가 멈춰 모두 뺌 · 세지 않음)" if own.get("err") else " (까닭별 수 없음 · 세지 않음)")
                         + ": " + ", ".join(map(str, drows[:US_OWN_SHOW])))
        aged = own.get("aged")
        if aged is not None:
            ok_a = isinstance(aged, list) and all(isinstance(a, dict) and isinstance(a.get("t"), str) and a["t"] for a in aged)
            inside = sorted({a["t"] for a in aged if a["t"] in by}) if ok_a else []
            parts.append(f"{US_OWN_CLOSE_MAX_DAYS}거래일이 지나 잠시 뺀 종목 {len(aged) if ok_a else '?'}"
                         + (f" ({', '.join(a['t'] for a in aged[:US_OWN_SHOW])})" if ok_a and aged else "")
                         + ("" if ok_a else " · 모양이 잘못됨") + (f" · 그런데 발행하는 종목: {', '.join(inside)}" if inside else ""))
            if not ok_a or inside:
                soft.append(("aged", "rec"))
    if hard:
        parts.insert(0, f"맞지 않음 {len(hard)}: {listed(hard)}")
        rep.detail("미국 마지막 확인 종가가 맞지 않는 종목 (우리 코드의 잘못)", [f"{t}: {US_OWN_WHY.get(w, w)}" for t, w in hard])
    if over:
        rep.detail(f"파이프라인이 한 점검('{US_OWN_WHY.get(worst[0], worst[0])}')에서 거른 미국 마지막 확인 종가 행이 {US_OWN_DROP_MAX}개를 넘어요 "
                   f"({worst[1]}) — 한 종목이 아니라 그 점검이 고장 났어요", [str(x) for x in drows])
    if soft:
        real = [(t, w) for t, w in soft if t != "aged"]
        if real:
            parts.append(f"어긋남 {len(real)}: {listed(real)}")
            rep.detail("미국 마지막 확인 종가 기록과 어긋난 종목 (오늘 가격으로 보고 가격 줄들이 봐요)", [f"{t}: {US_OWN_WHY.get(w, w)}" for t, w in real])
    warn = bool(mine or soft or dropped or (own is not None and (own.get("same") or own.get("err") or own.get("aged") or own.get("split")))
                or (raw is not None and own is None))
    rep.add(name, not hard and not over, " · ".join(parts) or "?", rule, warn=warn and not hard and not over)


US_NEW_WAIT_ROW = "미국 새 종목 확인 종가 기다림 (usSrc.newWait · 경고만)"


def us_new_wait_list(data):
    """data.json usSrc.newWait → (티커 목록 또는 None (칸 없음), 모양이 맞는지). 맞는 모양 = 빈 글이 아닌 글자의 목록. (순수 함수)"""
    src = (data or {}).get("usSrc") if isinstance(data, dict) else None
    if not isinstance(src, dict) or "newWait" not in src:
        return None, True
    nw = src["newWait"]
    ok = isinstance(nw, list) and all(isinstance(t, str) and t.strip() for t in nw)
    return (nw if ok else None), ok


def check_us_new_wait(rep, data, pdata):
    """2026-11-22 (Jack, verbatim: "2. No relaxation. Instead, a stock newly added to the S&P (or NASDAQ) list joins our list only once it
    has a confirmed close; until then it isn't added. Nobody can hold it in the app before it joins, so nothing is lost, and the check
    stays as it is."): 파이프라인(fetch_data.us_new_wait_step)은 지난 발행본에 없던 미국 티커가 미국 기준일 종가가 없으면 넣지 않고 data.json
    usSrc.newWait 에 적어요. 이 줄은 **경고만** 해요 — 실패하지 않아요 (발행 · 사이트 점검 모두): 기다리는 티커가 있으면 이름을 적고, 그중 지난
    발행본도 기다리던 티커(두 발행본 넘게 이어서 기다림 — 출처 목록에 남은 죽은 티커일 수 있어요 · 발행 모드에서만 지난 발행본을 봐요)를 따로
    적어요. 모양이 틀린 기록(글자 목록이 아님) · 기다린다면서 발행하는 티커도 경고. 칸이 없거나 비면 통과. (리뷰 2026-11-22: 예전에는 '미국 d1 채움'
    줄이 그런 티커를 이름으로 적었어요 — 기다리는 동안 아무도 모르게 남지 않게)"""
    rule = "새로 들어온 미국 종목은 미국 기준일 종가가 확인되면 들어와요 (기다리는 종목 · 이어서 기다리는 종목 · 모양이 틀린 기록은 경고 · 실패 없음)"
    nw, ok = us_new_wait_list(data)
    if not ok:
        raw = ((data or {}).get("usSrc") or {}).get("newWait")
        rep.add(US_NEW_WAIT_ROW, True, f"usSrc.newWait 모양이 잘못됨 (빈 글이 아닌 글자 목록이어야 해요: {str(raw)[:80]})", rule, warn=True)
        return
    if not nw:
        rep.add(US_NEW_WAIT_ROW, True, "없음", rule)
        return
    pnw, _pok = us_new_wait_list(pdata) if isinstance(pdata, dict) else (None, True)
    pset = set(pnw or [])
    again = [t for t in nw if t in pset]
    listed = {s.get("t") for s in us_stocks(data)}
    inside = [t for t in nw if t in listed]
    parts = [f"{len(nw)}종목: " + ", ".join(nw[:US_OWN_SHOW]) + (f" 외 {len(nw) - US_OWN_SHOW}종목" if len(nw) > US_OWN_SHOW else "")]
    if again:
        parts.append(f"지난 발행본부터 이어서 기다림 {len(again)}: " + ", ".join(again[:US_OWN_SHOW])
                     + (f" 외 {len(again) - US_OWN_SHOW}종목" if len(again) > US_OWN_SHOW else "") + " (출처 목록의 티커가 살아 있는지 확인)")
    if inside:
        parts.append(f"그런데 발행하는 종목: {', '.join(inside[:US_OWN_SHOW])}")
    rep.add(US_NEW_WAIT_ROW, True, " · ".join(parts), rule, warn=True)
    rep.detail("미국 기준일 종가를 기다리는 새 미국 종목 (usSrc.newWait · 목록에 넣지 않았어요)",
               [t + (" (지난 발행본부터 이어서)" if t in again else "") for t in nw])


def coverage(arr, key):
    if not arr:
        return 0.0
    return 100.0 * sum(1 for s in arr if num(s.get(key)) is not None) / len(arr)


def us_coverage(arr):
    if not arr:
        return {"이름": 0.0, "설명": 0.0}
    return {"이름": 100.0 * sum(1 for s in arr if s.get("nk") and s.get("nk") != s.get("t")) / len(arr),
            "설명": 100.0 * sum(1 for s in arr if s.get("de")) / len(arr)}


def check_us_risk_cover(rep, us, pdata):
    """2026-11-12 (Jack, 더하기만): 미국 베타·변동성 채움 — 국내 줄과 같은 규칙 (95% 아래면 실패, 97% 아래면 경고 · 직전보다 10점
    넘게 줄면 실패). 값 칸에 빈 칸 수, 97% 아래면 빈 종목 앞 10개(US_D1_SHOW, 아침 점검 알림에도 보이게)와 로그·실행 요약에 전부를
    적어요: 새로 상장한 회사(이력 250거래일 미만)인지 파이프라인 문제인지 바로 보이게 (docs/RUNBOOK.md). 변화 줄은 국내 줄과 맞춘 것이라 바닥 95% 보다 먼저 걸리지는 않아요."""
    for k, lo in COVER_US_RISK.items():
        v = coverage(us, k)
        blank = [str(s.get("t")) for s in us if num(s.get(k)) is None]
        named = bool(blank) and v < lo + NEAR       # 경고·실패일 때: 아침 점검은 알림(이름: 값)만 읽으니 값 칸에도 앞의 몇 개를 적어요
        shown = ", ".join(blank[:US_D1_SHOW]) + (f" 외 {len(blank) - US_D1_SHOW:,}개" if len(blank) > US_D1_SHOW else "")
        rep.add(f"미국 {k} 채움", v >= lo,
                f"{floor_1(v)}% (빈 칸 {len(blank)} / {len(us):,})" + (f" · 빈 종목: {shown}" if named else ""),
                f"≥ {lo}% ({lo + NEAR:g}% 아래 경고)", warn=v < lo + NEAR and v < 100.0)
        if named:
            rep.detail(f"미국 {k} 빈 종목", blank)
        if pdata:
            pv = coverage(us_stocks(pdata), k)
            rep.add(f"미국 {k} 채움 변화", v >= pv - 10, f"{pv:.1f} → {v:.1f}", "10점 넘게 줄면 실패")


def run_checks(cur, prev, final, today, mode="publish", count_between=None, notes=None, sessions=None, now=None, hilo=None,
               special=None, alt=None):
    """cur/prev: {"data":…, "corp":…, "disc":…, "macro":…} (prev 는 None 가능).
    final: {"date", "closes", "how"} — 비교할 최종본 (None 이면 날짜·가격 검사 실패).
    sessions: {"dates": [KOSPI 거래일…], "src": 출처} — None 이면 받지 못한 것 → FAIL.
    now: 관문 실행 시각(KST) — publishedAt 12시간 검사용 (없으면 today 정오).
    hilo: {코드: {"hi", "lo", "d1"}} 야후 52주 종가 범위와 d1 — None 이면 받지 못한 것 (경고).
    special: KRX 특별 거래시간 표 — None 이면 표 파일을 읽어요 (못 읽으면 FAIL).
    mode: publish · bootstrap · live.  반환: Report.
    alt: (2026-11-19 · Jack 규칙 3) 캐시에 pxDate 최종본이 없을 때 관문이 야후에서 따로 받은 공식 종가 (http_px_alt) — px_alt_confirms 가 허락하면
    날짜 · 가격 줄의 기준이 이것이 돼요 (같은 줄 · 같은 정확히 같음 · 같은 비율 기준). None 이면 예전 그대로."""
    rep, notes = Report(), (notes if notes is not None else [])
    data, corp, disc, macro = cur["data"], cur["corp"], cur["disc"], cur["macro"]
    rel = mode == "publish"
    if mode == "publish" and prev is None:
        rep.add("직전 발행본 읽기", False, "읽을 수 없음", "있어야 함 (첫 실행이면 bootstrap)")
    pdata = (prev or {}).get("data") if rel else None

    # 날짜
    px = day(data.get("pxDate"))
    # 2026-11-19 (Jack 규칙 3): 캐시에 pxDate 의 최종본이 있으면 예전 그대로 그것이 기준이에요. 없으면 관문이 야후에서 따로 받은 공식 종가와
    # data.json pxSrc 의 2차 출처 확인 (px_alt_confirms) — 둘 다 안 되면 예전처럼 실패해요.
    # 2026-11-19 (Jack): 마지막 확인 종가(pxd)로 맞게 실린 국내 종목 (기록 · 나이 · 지난 발행본의 가격과 날짜까지 맞는 것만) — pxDate 의 가격 줄에서 빠져요
    own_ok = kr_own_codes(data, pdata, kr_days_of(macro))
    # 2026-11-20 (Jack): 마지막 확인 종가(pxc · pxd)로 맞게 실린 미국 종목 (기록 · 나이 · 지난 발행본의 가격과 날짜까지 맞는 것만) — 오늘(usPxDate)
    # 가격을 보는 줄(미국 d1 채움의 빠진 수 · 미국 필수 종목 d1 · 미국 가격이 바뀌었는지)에서 빠져요
    us_own = us_own_codes(data, pdata, us_days_of(macro))
    use_alt, alt_how = (False, None) if alt is None else px_alt_confirms(data, alt, px, final, mode, today=today, now=now, special=special, own=own_ok)
    # 2026-11-20 (Jack: "a timeout skips the Daum spot-check with a loud warning; the deploy continues on the other checks"): 배포의 관문(live ·
    # 한도를 받았을 때만)의 확인이 시간 한도에 걸려 받은 종목 수가 모자라면, 시간 한도(와 네트워크 오류)로 설명되는 몫만 건너뛰고 경고해요 —
    # 다음이 분명히 답하지 않은 필수 종목이 있거나 그런 종목만으로 표본 기준에 못 미치면 예전 그대로 실패 (px_alt_cut_gap · 리뷰). 다른 조건(발행
    # 기록 · 날짜 · 마감 뒤)은 그대로 보고, 받은 종가는 아래 가격 줄에서 비교해요 (다르면 실패). 발행 관문(publish)은 예전 그대로.
    # 2026-11-21 (Jack, 11-20 질문 3 → "3. Yes."): 같은 배포에서 다음이 아예 거절해 멈춘 확인 (px_alt_was_refused) 도 같은 길로 — 거절로
    # 설명되는 몫만 건너뛰고 같은 줄을 경고로 (받은 종가 비교 · 다음이 분명히 답하지 않은 필수 종목 · 발행 기록은 그대로).
    skip_alt = False
    stop_why = px_alt_stop_why(alt)
    if alt is not None and not use_alt and mode == "live" and (px_alt_was_cut(alt) or px_alt_was_refused(alt)):
        skip_alt, alt_how = px_alt_confirms(data, alt, px, final, mode, today=today, now=now, special=special, cover=False, own=own_ok)
    if alt is not None:
        notes.append(f"2차 출처 관문 기준 (야후): {'씀' if use_alt else ((('시간 한도로' if stop_why == '시간 한도' else '다음이 거절해') + ' 확인을 건너뜀 (경고)') if skip_alt else '쓰지 않음')} — {alt_how}")
    if use_alt:
        cutn = px_alt_was_cut(alt)               # 한도에 걸렸지만 그 전에 예전 기준을 채운 확인 — 통과 그대로, 한도에 걸린 것은 경고로 알려요
        rep.add("pxDate 최종본 여부" if mode == "live" else "pxDate = 최종본 날짜", True, px,
                f"{px} ({alt_how}" + (f" · 시간 한도로 건너뜀 {alt['cut']}종목 (Jack 2026-11-20)" if cutn else "") + ")", warn=cutn)
        final = {"date": px, "closes": px_alt_closes(alt), "how": alt_how}
        if cutn:                                 # 리뷰 2: 이 길도 일부만 받았어요 — 가격 줄은 아래 '한도에 걸린 날' 기준 (묻기로 한 종목 수로 나눠요)
            final.update(cut=True, asked=alt.get("asked"))
    elif skip_alt:
        rep.add("pxDate 최종본 여부", True, px, f"{px} ({alt_how})", warn=True)
        final = {"date": px, "closes": px_alt_closes(alt), "how": alt_how, "cut": True, "asked": alt.get("asked"), "why": stop_why}
    elif final is None:
        rep.add("최종본 날짜 계산", False, "실패", "최근 10일 안 최종본" + (f" (2차 출처: {alt_how})" if alt is not None else ""))
    elif mode == "live":
        rep.add("pxDate 최종본 여부", px == final["date"], px, f"{final['date']} ({final['how']})" + (f" · 2차 출처: {alt_how}" if alt is not None else ""))
    else:
        rep.add("pxDate = 최종본 날짜", px == final["date"], px, f"{final['date']} ({final['how']})" + (f" · 2차 출처: {alt_how}" if alt is not None else ""))
    check_px_src(rep, data, today, mode, own=own_ok)
    # KRX 특별 거래시간 표 (v17.5.4): 최종본 기준에 써요. 읽을 수 있어야 하고, 올해 수능일 줄이 있어야 해요
    # (없으면 9월 1일부터 경고, 11월 1일부터 실패 — Jack, 2026-11-04)
    try:
        sp = load_special_sessions() if special is None else special
    except Exception as e:
        sp = None
        rep.add("KRX 특별 거래시간 표", False, str(e)[:90], "읽을 수 있어야 함 (data/krx_special_sessions.csv)")
    if sp is not None:
        miss, block = csat_missing(today, sp), csat_blocks(today, sp)
        have = sorted(d for d, v in sp.items() if d.year == today.year and v[2] == "수능")
        rep.add("올해 수능일 특별 거래시간 (표)", not block,
                "올해 수능일 특별 거래시간이 표에 없어요" if miss
                else (" · ".join(f"{d} {sp[d][0]:%H:%M}~{sp[d][1]:%H:%M}" for d in have) or "9월 1일 전이라 아직 안 봐요"),
                "올해 수능일 줄 (9월 1일부터 없으면 경고 · 11월 1일부터 없으면 실패)", warn=miss)
    ppx = prev_px_date(pdata, notes) if pdata else None
    if pdata:
        rep.add("pxDate 가 뒤로 가지 않음", px is not None and ppx is not None and px >= ppx, px, f"≥ {ppx}")
    rep.add("KOSPI 마지막 날 = pxDate", day(data.get("ksDate")) == px and px is not None, data.get("ksDate"), px)
    # pxDate 와 오늘 사이에 끝난 거래일이 있으면 낡은 가격 (최종본 목록이 하루 물러난 경우).
    # 사이트 점검(live)은 매일 아침 발행 전까지 어제 거래일이 늘 '아직 없음'이라 여기서 보지 않아요 (v17.6 감시가 따로 봐요).
    if mode == "live":
        rep.skip("pxDate 뒤 끝난 거래일 없음", "사이트 점검은 발행 전 시간대가 있어 v17.6 감시가 따로 봐요")
    elif sessions is None:
        rep.add("pxDate 뒤 끝난 거래일 없음", False, "KOSPI 일봉을 받지 못했어요", "네이버 또는 야후 KOSPI 일봉으로 확인")
    elif px is None:
        rep.add("pxDate 뒤 끝난 거래일 없음", False, "pxDate 없음", "있어야 함")
    else:
        later = completed_sessions_after(px, today, sessions["dates"])
        rep.add("pxDate 뒤 끝난 거래일 없음", not later,
                "없음" if not later else f"{len(later)}일: " + ", ".join(d.isoformat() for d in later[:5]),
                f"{px} < 거래일 < {today} 이 0일 ({sessions['src']})")
        if sessions["dates"] and px >= sessions["dates"][0]:
            rep.add("pxDate 가 KOSPI 거래일", px in sessions["dates"], px, sessions["src"])

    # 발행 시각: 네 파일 모두 같은 값, 한국 시간(+09:00), 관문 실행 12시간 이내
    pubs = {k: (cur.get(k) or {}).get("publishedAt") for k in ("data", "corp", "disc", "macro")}
    missing = [k for k, v in pubs.items() if not v]
    rep.add("publishedAt 네 파일 모두", not missing, "모두 있음" if not missing else "없음: " + ",".join(missing), "data·corp·disc·macro")
    parsed = {}
    for k, v in pubs.items():
        try:
            parsed[k] = dt.datetime.fromisoformat(str(v)) if v else None
        except ValueError:
            parsed[k] = None
    off = [k for k, v in parsed.items() if v is None or v.utcoffset() != dt.timedelta(hours=9)]
    rep.add("publishedAt 한국 시간(+09:00)", not off, "모두 +09:00" if not off else "아님: " + ",".join(off), "+09:00")
    vals = {str(v) for v in pubs.values() if v}
    rep.add("publishedAt 네 파일이 같음", len(vals) == 1 and not missing, " · ".join(sorted(vals))[:80] or "없음", "한 값")
    pub = parsed.get("data")
    if mode == "live":
        rep.skip("publishedAt 12시간 이내", "사이트 점검은 발행 뒤 시간이 지나 있어요 (신선도는 v17.6 감시가 따로 봐요)")
    else:
        ref = now or dt.datetime.combine(today, dt.time(12), KST)
        age = (ref - pub) if pub is not None and pub.utcoffset() is not None else None   # 시간대 없는 값은 비교 불가 → 실패
        ok = age is not None and dt.timedelta(0) <= age <= dt.timedelta(hours=PUBLISHED_MAX_HOURS)
        rep.add("publishedAt 12시간 이내", ok,
                f"{age.total_seconds() / 3600:.1f}시간 전" if age is not None else "읽을 수 없음",
                f"0 ~ {PUBLISHED_MAX_HOURS}시간 전 (관문 {ref:%m-%d %H:%M} KST)")

    # 가격 = 공식 종가
    kr = kr_stocks(data)
    if final is not None:
        cl = final["closes"]
        part = bool(final.get("cut"))            # 2026-11-20: 배포의 두 출처 확인이 시간 한도에 걸린 날 — 받은 종가만 비교해요
        stop = final.get("why") or "시간 한도"     # 2026-11-21: 다음이 거절해 멈춘 날도 같은 비교 (표의 말만 달라요)
        own = own_ok                    # 2026-11-19 (Jack): 마지막 확인 종가(pxd)로 맞게 실린 종목은 pxDate 의 종가와 맞춰 보지 않아요 (그날 가격이 아니에요)
        inl = [s for s in kr if s.get("t") in cl and s.get("t") not in own]
        same = sum(1 for s in inl if num(s.get("price")) is not None and round(num(s["price"])) == cl[s["t"]])
        share = 100.0 * same / len(inl) if inl else 0.0
        if not part:
            rep.pct("한국 가격 = 공식 종가", share, PRICE_MATCH)
        elif inl:
            # 2026-11-20 리뷰: 같은 99% 를 묻기로 한 종목 수(asked)로 나눠요 — 받은 종목에서 본 다른 종가 수만 빼고, 받지 못한 종목은 맞았다고 쳐요.
            # 그래서 여기서 실패하면 다 받았을 때도 반드시 실패해요 (받은 종목만으로 나누면 60종목 중 1개가 98.3% 로 실패 — 다 받은 날보다 엄했어요).
            # asked 를 읽을 수 없으면 받은 종목 수로 (더 엄한 쪽).
            asked = final.get("asked")
            n = asked if isinstance(asked, int) and not isinstance(asked, bool) and asked >= len(inl) else len(inl)
            bad = len(inl) - same
            share = 100.0 * (n - bad) / n
            shown = f"{share:.1f}%"
            if share < PRICE_MATCH and shown == f"{PRICE_MATCH:.1f}%":     # 실패인데 반올림으로 기준과 같아 보이면 한 자리 더 (내림)
                shown = f"{math.floor(share * 100) / 100:.2f}%"
            rep.add("한국 가격 = 공식 종가", share >= PRICE_MATCH, shown,
                    f"≥ {PRICE_MATCH}% ({stop}: 받은 {len(inl)}종목만 비교 · 다름 {bad} · 비율은 묻기로 한 {n}종목 기준 · 나머지는 건너뜀)", warn=True)
        else:
            rep.add("한국 가격 = 공식 종가", True, "비교 못 함", f"≥ {PRICE_MATCH}% ({stop}: 받은 종가 없음 · 건너뜀)", warn=True)
        s5 = next((s for s in kr if s.get("t") == "005930"), None)
        want = cl.get("005930")
        if part and want is None:
            rep.add("005930 = 공식 종가", True, f"{num((s5 or {}).get('price')):,.0f}" if s5 and num(s5.get("price")) else "없음",
                    f"? ({stop}: 다음 값을 받지 못해 건너뜀)", warn=True)
        else:
            rep.add("005930 = 공식 종가", bool(s5) and want is not None and round(num(s5.get("price")) or -1) == want,
                    f"{num((s5 or {}).get('price')):,.0f}" if s5 and num(s5.get("price")) else "없음", f"{want:,}" if want else "?")

    # 미국 신선도
    us = us_stocks(data)
    usd = day(data.get("usPxDate"))
    rep.add("미국 기준일", usd is not None and (today - usd).days <= US_STALE_DAYS, usd, f"{US_STALE_DAYS}일 이내")
    if pdata:
        pus = day(pdata.get("usPxDate")) or day(pdata.get("asOf"))
        if usd and pus and usd > pus:
            pp = {s["t"]: num(s.get("price")) for s in us_stocks(pdata)}
            # 2026-11-20 (Jack): 마지막 확인 종가로 맞게 실린 종목(us_own)은 지난 발행본의 가격 그대로가 맞아요 — 빼고 세요
            both = [s for s in us if pp.get(s["t"]) is not None and s.get("t") not in us_own]
            unch = 100.0 * sum(1 for s in both if num(s.get("price")) == pp[s["t"]]) / len(both) if both else 100.0
            nown = sum(1 for s in us if s.get("t") in us_own)
            if not both and nown:
                rep.add("미국 가격이 바뀌었는지", True, f"견줄 종목 없음 (마지막 확인 종가 {nown}종목 빼고)", f"≤ {US_UNCHANGED}% (마지막 확인 종가는 빼고)",
                        warn=True)
            else:
                rep.add("미국 가격이 바뀌었는지", unch <= US_UNCHANGED, f"그대로 {unch:.1f}%" + (f" (마지막 확인 종가 {nown}종목 빼고)" if nown else ""),
                        f"≤ {US_UNCHANGED}%" + (" (마지막 확인 종가는 빼고)" if nown else ""))
        else:
            rep.skip("미국 가격이 바뀌었는지", "미국 기준일이 그대로")

    # 환율·금리
    fx = num(data.get("fx"))
    rep.add("환율 범위", fx is not None and FX_LO < fx < FX_HI, fx, f"{FX_LO} ~ {FX_HI}")
    if pdata and num(pdata.get("fx")):
        dfx = abs(fx / num(pdata["fx"]) - 1) * 100 if fx else 999
        rep.add("환율 변화", dfx <= FX_REL * 100, f"{dfx:.1f}%", f"≤ {FX_REL * 100:.0f}%")
    src = (data.get("settings") or {}).get("rfSrc")
    rep.add("무위험수익률 출처", bool(src) and src != "fallback", src or "없음", "기본값(fallback) 아님")
    cdate = day((macro.get("curve") or {}).get("date"))
    rep.add("국고채 커브 날짜", cdate is not None and (today - cdate).days <= CURVE_STALE_DAYS, cdate or "없음",
            f"{CURVE_STALE_DAYS}일 이내")

    # 종목 수
    # 2026-11-20 (#159 리뷰 · 늦추지 않아요): 국내 종목 수 두 줄은 pxDate 종가로 실은 국내 종목만 세요 (kr_px_count). 마지막 확인 종가(pxd)로 실은
    # 종목은 세지 않아요 — 세면 2차 출처가 시간 한도로 많은 종목을 묻지 못한 날 그 종목들이 옛 종가로 돌아와 바닥(KR_MIN)이 걸리지 않아요 (main 은
    # 멈춰요). main 의 국내 종목에는 pxd 가 없어서 이 두 줄은 main 과 똑같이 움직여요. 값 칸에 둘 다 적어요.
    nk_px, nk_own = kr_px_count(data), len(kr) - kr_px_count(data)
    rep.add("국내 종목 수", nk_px >= KR_MIN, f"{nk_px:,}" + (f" (pxDate 종가 · 그 밖에 마지막 확인 종가 {nk_own:,}종목은 세지 않아요)" if nk_own else ""),
            f"≥ {KR_MIN:,} (pxDate 종가로 실은 종목)", warn=nk_px < KR_MIN * 1.02)
    check_us_counts(rep, data, pdata)     # 머지 확인 (2026-11-20, 1): 예전에도 실렸을 미국 행만 세요 (us_px_count)
    if pdata:
        pk = kr_px_count(pdata)
        pk_own = len(kr_stocks(pdata)) - pk
        rep.add("국내 종목 수 변화", pk > 0 and abs(nk_px / pk - 1) <= KR_REL, f"{pk:,} → {nk_px:,}"
                + (f" (pxDate 종가 · 마지막 확인 종가 {pk_own:,} → {nk_own:,}종목은 세지 않아요)" if pk_own or nk_own else ""),
                f"±{KR_REL:.0%} (pxDate 종가로 실은 종목)")
    nb = sum(1 for s in data.get("stocks", []) if s.get("cls") == "bond")
    rep.add("채권 ETF", nb >= BONDS_EXPECTED - 1, nb, f"{BONDS_EXPECTED} (7 경고 · 6 이하 실패)", warn=nb < BONDS_EXPECTED)

    # 꼭 있어야 할 종목
    by = {s.get("t"): s for s in data.get("stocks", [])}
    miss = [t for t in MUST if not (by.get(t) and (num(by[t].get("price")) or 0) > 0 and (num(by[t].get("cap")) or 0) > 0)]
    rep.add("필수 종목 (가격·시총)", not miss, "모두 있음" if not miss else "없음: " + ",".join(miss), ",".join(MUST))
    missf = [t for t in FUNDS if not (by.get(t) and (num(by[t].get("price")) or 0) > 0)]
    rep.add("ETF·금현물 5종", not missf, "모두 있음" if not missf else "없음: " + ",".join(missf), ",".join(FUNDS))

    # 항목 채움 (한국)
    for k, lo in COVER_KR.items():
        v = coverage(kr, k)
        rep.pct(f"국내 {k} 채움", v, lo)
        if pdata:
            pv = coverage(kr_stocks(pdata), k)
            rep.add(f"국내 {k} 채움 변화", v >= pv - 10, f"{pv:.1f} → {v:.1f}", "10점 넘게 줄면 실패")
    # 미국 상세 정보 (이름·설명)
    uc = us_coverage(us)
    for k, lo in COVER_US.items():
        rep.pct(f"미국 {k} 채움", uc[k], lo)
        if pdata:
            pv = us_coverage(us_stocks(pdata))[k]
            rep.add(f"미국 {k} 채움 변화", uc[k] >= pv - 10, f"{pv:.1f} → {uc[k]:.1f}", "10점 넘게 줄면 실패")
    check_us_risk_cover(rep, us, pdata)

    # 가격 움직임
    if pdata and ppx and px and count_between is not None:
        try:
            n = max(1, count_between(ppx, px))
        except Exception as e:
            rep.add("큰 가격 변동 비율", False, f"거래일 수 계산 실패: {str(e)[:60]}", "계산할 수 있어야 함")
            n = None
    else:
        n = None
    if n is not None:
        lim = (1.3 ** n - 1) * 100
        pp = {s["t"]: num(s.get("price")) for s in kr_stocks(pdata)}
        both = [s for s in kr if pp.get(s["t"]) and num(s.get("price"))]
        big = sum(1 for s in both if abs(num(s["price"]) / pp[s["t"]] - 1) * 100 > lim)
        share = 100.0 * big / len(both) if both else 0.0
        rep.add("큰 가격 변동 비율", share <= MOVE_SHARE, f"{share:.2f}% ({big}종목, {n}거래일)",
                f"±{lim:.0f}% 넘는 종목 ≤ {MOVE_SHARE}%")

    # 순서
    pop = data.get("popular") or []
    rep.add("인기 상위 20에 005930", "005930" in pop[:20], "있음" if "005930" in pop[:20] else "없음", "있어야 함")
    top = [s.get("nk") or "" for s in sorted(kr, key=lambda s: -(num(s.get("cap")) or 0))[:20]]
    rep.add("시총 상위 20이 가나다순 아님", top != sorted(top), " · ".join(top[:3]) + " …", "시가총액 순")

    # corp.json
    comps = corp.get("companies") or []
    rep.add("기업분석 기업 수", len(comps) >= CORP_MIN, f"{len(comps):,}", f"≥ {CORP_MIN:,}")
    rep.add("기업분석 업종 수", len(corp.get("sectors") or {}) >= SECTOR_MIN, len(corp.get("sectors") or {}), f"≥ {SECTOR_MIN}")
    cset = {c.get("t") for c in comps}
    missc = [t for t in MUST if t not in cset]
    rep.add("기업분석 필수 종목", not missc, "모두 있음" if not missc else "없음: " + ",".join(missc), ",".join(MUST))
    sam = next((c for c in comps if c.get("t") == "005930"), {})
    rep.add("005930 PER 또는 PBR", num(sam.get("per")) is not None or num(sam.get("pbr")) is not None,
            f"PER {sam.get('per')} · PBR {sam.get('pbr')}", "하나는 있어야 함")
    ttm = 100.0 * sum(1 for c in comps if c.get("bq")) / len(comps) if comps else 0.0
    rep.add("TTM 반영 비율", ttm >= TTM_HARD, f"{ttm:.1f}%", f"≥ {TTM_HARD}% (80% 아래면 경고)", warn=ttm < TTM_WARN)

    # ── v17.5.1 (v18.0 Part A + 추가 4–9) ──
    check_v1751(rep, cur, kr, us, by, comps, px, today, hilo, us_own=us_own)
    check_v1752(rep, data, kr, us, pdata)
    check_us_fcur(rep, us)                # Jack, 2026-11-12: 재무제표 통화가 달러가 아닌 미국 회사
    check_us_fcur_more(rep, data, us, pdata)   # #114 리뷰: 통화를 모르는 회사 (경고) · 어제 있던 통화가 사라짐
    check_us_extra(rep, data, us, mode)   # 2026-11-14: 손으로 더한 미국 종목이 있거나 빠진 이유가 있는지
    check_us_share_class(rep, data, us, mode)   # 2026-11-15: 주식 종류 티커 (BF-B) 가 있거나 빠진 이유 · 바꾸지 못한 티커 (경고)
    check_us_foreign(rep, data, us, mode) # 2026-11-14: 미국 상장 외국 회사의 PER·PBR·배당수익률은 회사 합계와 맞춘 것만
    check_foreign(rep, kr, comps)
    if rel:
        check_stmt_marks(rep, comps, prev)      # 경고가 많은 날에도 알림 10개 안에 들도록 앞쪽에 (외국 기업 줄 바로 다음)
    check_v191b(rep, data, kr, us, by, comps, pdata, today)
    check_v191h(rep, data, kr, by, comps, pdata, today)
    check_v191i(rep, data, kr, by, comps, pdata, today, mode)   # Jack 2026-11-14 (item 5): 되살린 배당수익률 = 배당 총액 ÷ 시가총액
    check_v191c(rep, cur, us, mode, today)
    check_kr_own_close(rep, data, macro, pdata)   # 2026-11-19 (Jack): 국내 종목의 마지막 확인 종가 (pxd · 미국 pxd 줄과 같은 실패 + 경고 줄)
    check_us_own_close(rep, data, macro, pdata)   # 2026-11-20 (Jack): 미국 종목의 마지막 확인 종가 (pxc · 날짜가 깨졌거나 d1 이 옆에 있으면 실패 · 나머지는 경고)
    check_us_new_wait(rep, data, pdata)   # 2026-11-22 (Jack): 미국 기준일 종가를 기다리는 새 미국 종목 (usSrc.newWait · 경고만 · 실패 없음)
    check_v191f(rep, data, corp, kr, by, comps, pdata)
    check_eps_line_left(rep, corp, comps)   # 2026-11-14 (Jack Q3 · 리뷰 S4): 다시 읽은 뒤에도 날짜가 지난 '고치는 중' 줄이 남을 회사 (경고)
    check_v196a(rep, data, macro, by, pdata, mode, today, pmacro=(prev or {}).get("macro") if rel else None)
    check_unit(rep, data, kr, by, comps, pdata)
    check_kr_series(rep, data, kr, pdata)  # 2026-11-14 (Jack: "52주 숫자부터"): 다른 기준의 공식 종가 고정 (실패) · 제한폭 넘는 움직임 (경고)
    check_px_bad(rep, data, comps, pdata)  # 2026-11-14 (Jack, Q2 (a)): 그 움직임이 있는 종목은 52주 · 출렁임 · 위험 숫자를 비워요 (실패) · 필수 종목 추세 · 저변동 순위 (실패)
    check_kr_no_trade(rep, data, pdata, macro)    # 2026-11-14 (Jack, design chat 2026-11-08): 거래 없는 종목은 d1 빈 칸 + noTrade · 빈 d1 은 이유 (실패: 우리 값끼리 어긋날 때만)
    check_v196b(rep, data, disc, by, today)   # v19.6b (Part B.1): 주요사항 공시 · 내부자 역할 · 미국 일정 (모양 · 칸이 없는 예전 파일은 경고만)
    check_issue_bd(rep, disc)                 # v19.6b Q18 (Jack 2026-11-19): 유상증자 이사회 결의일 (공시일 뒤면 실패 · 빈 줄은 경고)
    check_v196e(rep, data, macro)             # v19.6e (Part I.2): 이번 주 시작 종가 c1w · wkFrom · usWkFrom (경고만)
    check_small_div(rep, data, corp, pdata)   # 2026-11-23 (Jack 11-19 Q6): 차등배당 회사의 소액주주 배당수익률 (경고만 · 실패 없음)

    # 경고만
    rep.add("공시 목록 조회", True, "성공" if disc.get("listOk") else "실패", "실패면 경고", warn=not disc.get("listOk"))
    return rep


def check_v191c(rep, cur, us, mode, today):
    """v19.1c (Jack, 2026-11-07): 휴장일 표 · 다음 발행 예정일(nextPub · staleAfter) · 미국 종목의 자기 가격 날짜(pxd)."""
    data, macro = cur["data"], cur.get("macro") or {}
    # Jack (2026-11-07): 휴장일 표와 예정일은 '늦음' 경고 시각에만 써요. 무엇이 어긋나도 경고만 — 발행을 막으면 우리가 경고하려는
    # 낡은 데이터가 생겨요. 지수 일봉과 표가 다르면 일봉이 맞아요 (임시공휴일·미국 애도일은 갑자기 정해져요). 아침 점검이 경고를 읽어요.
    try:
        hol, end = load_holidays()
    except Exception as e:
        rep.add("휴장일 표 (data/market_holidays.csv)", True, f"읽지 못함: {e} — 평일 규칙으로 봐요"[:140],
                "읽을 수 있어야 함 (못 읽으면 경고 · 발행은 막지 않아요)", warn=True)
        hol, end = {"KR": set(), "US": set(), "start": None}, None
    # 1. 다음 발행 예정일 — 파이프라인이 늘 써요. 없거나 어긋나도 경고만 (앱은 없으면 예전 4일 규칙으로 돌아가요)
    npub, sa = data.get("nextPub"), data.get("staleAfter")
    TH = "휴장일 표로 다시 계산한 값과 같음 (한국·미국 다음 거래일 중 먼저 + 1일 · 그날 14:47 + 2시간 · 예정일은 오늘 뒤 · 어긋나면 경고)"
    if npub is None and sa is None:
        rep.add("다음 발행 예정 (nextPub · staleAfter)", True, "없음 (앱은 예전 4일 규칙으로 '늦음'을 봐요)", TH, warn=True)
    else:
        why = []
        try:
            got_np = dt.date.fromisoformat(str(npub))
            got_sa = dt.datetime.fromisoformat(str(sa))
            px, usd = dt.date.fromisoformat(data.get("pxDate")), dt.date.fromisoformat(data.get("usPxDate"))
        except (TypeError, ValueError) as e:
            why.append(f"날짜를 읽을 수 없어요 ({e})"[:80])
        else:
            want = expected_next_pub(px, usd, hol, end)
            if got_np != want:
                why.append(f"nextPub {got_np} ≠ 표로 계산한 {want}" + (" (사이트 점검: 발행 뒤 표가 바뀌었을 수 있어요)" if mode == "live" else ""))
            want_sa = dt.datetime.combine(got_np, LAST_RETRY, KST) + dt.timedelta(hours=STALE_GRACE_H)
            if got_sa.utcoffset() != dt.timedelta(hours=9) or got_sa != want_sa:
                why.append(f"staleAfter {sa} ≠ {want_sa.isoformat()}")
            if got_np <= max(px, usd):
                why.append(f"nextPub {got_np} 가 기준일 뒤가 아니에요")
            if not why and mode != "live" and got_np <= today:
                # 제때 발행이면 예정일은 늘 내일 이후 — 표에 없는 임시공휴일이거나 미국 날짜가 하루 늦은 것
                why.append(f"예정일 {got_np} 이 오늘({today}) 이전이에요 — 표에 없는 휴장일(임시공휴일 등)이나 하루 늦은 날짜인지 확인")
        rep.add("다음 발행 예정 (nextPub · staleAfter)", True, f"{npub} · {sa}" + (" · " + " · ".join(why) if why else ""), TH,
                warn=bool(why))
    # 2. 휴장일 표: 앞으로 45일을 덮는지, 지난 90일의 지수 일봉과 맞는지 (봉 없는 평일 = 표의 휴장일) — 어긋나면 경고, 일봉이 맞아요
    if end is not None:
        probs = []
        for key, mk in (("KOSPI", "KR"), ("SP500", "US")):
            rows = ((macro.get("idxHist") or {}).get(key) or {}).get("rows") or []
            bars = {str(r[0]) for r in rows if isinstance(r, (list, tuple)) and r and is_day(r[0])}   # 날짜가 아닌 줄은 빼요
            if not bars:
                continue
            last = dt.date.fromisoformat(max(bars))
            d = last - dt.timedelta(days=HOL_CHECK_DAYS)
            while d <= last:
                if d.weekday() < 5 and hol["start"] <= d <= end:
                    iso = d.isoformat()
                    if iso not in bars and d not in hol[mk]:
                        probs.append(f"{mk} {iso} 봉 없음·표에 없음")
                    elif iso in bars and d in hol[mk]:
                        probs.append(f"{mk} {iso} 표엔 휴장·봉 있음")
                d += dt.timedelta(days=1)
        short = end < today + dt.timedelta(days=HOL_COVER_WARN_DAYS)
        rep.add("휴장일 표 (data/market_holidays.csv)", True,
                f"{end.year}년까지 · 한국 {len(hol['KR'])}일 · 미국 {len(hol['US'])}일"
                + (" · " + " · ".join(probs[:4]) if probs else "") + (" · 다음 해 줄을 넣어 주세요" if short else ""),
                f"앞으로 {HOL_COVER_WARN_DAYS}일을 덮고 지난 {HOL_CHECK_DAYS}일 지수 일봉과 맞음 (어긋나면 경고)",
                warn=bool(probs) or short)
    # 3. 미국 종목의 자기 가격 날짜: d1 이 없는 종목(마지막 봉이 기준일이 아님)은 pxd 가 있고 기준일보다 앞이어야, 앱이 그 날짜를 보여요
    if "nextPub" not in data and "staleAfter" not in data:      # 이 버전 전의 파일만 (파이프라인은 값이 없어도 칸은 늘 써요)
        rep.skip("미국 자기 가격 날짜 (pxd)", "이 버전 전의 파일 (pxd 를 쓰지 않았어요)")
        return
    usd = str(data.get("usPxDate") or "")
    bad, own = [], []
    for s in us:
        t, pxd = s.get("t"), s.get("pxd")
        if num(s.get("d1")) is None:
            if not (isinstance(pxd, str) and re.fullmatch(r"20\d\d-[01]\d-[0-3]\d", pxd) and pxd < usd):
                bad.append(f"{t}: d1 없음 · pxd {pxd!r}")
            else:
                own.append(f"{t}({pxd})")
        elif pxd is not None:
            bad.append(f"{t}: d1 있는데 pxd {pxd!r}")
    rep.add("미국 자기 가격 날짜 (pxd)", not bad,
            (" · ".join(bad[:5]) + (f" 외 {len(bad) - 5}개" if len(bad) > 5 else "")) if bad
            else (f"{len(own)}종목: " + ", ".join(own[:US_D1_SHOW]) + (f" 외 {len(own) - US_D1_SHOW}개" if len(own) > US_D1_SHOW else "")
                  if own else "없음 (모두 미국 기준일 종가)"),
            f"d1 이 없는 미국 종목은 pxd < {usd} · d1 이 있으면 pxd 없음")


def _iso_day(s):
    """'YYYY-MM-DD' 로 적힌 진짜 날짜면 date, 아니면 None (2026-02-30 · '2026-1-5' · 숫자는 None)."""
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def json_num(x):
    """JSON 숫자(정수·실수, 참/거짓 아님, 유한)면 float, 아니면 None — 앱은 글자 "1180.5" 를 숫자로 읽지 않아요 (typeof number)."""
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def simple_ratio(r, top=None):
    """배율이 기약분수 p/q 로 min(p, q) ≤ top 인지 (분할·병합·주식배당은 그래요 · 야후가 분사를 적은 1253:1000 같은 값은 아니에요).
    fetch_data.split_is_clean 과 같은 규칙 · 같은 허용치(SPLIT_CLEAN_TOL), 코드는 따로: p/q 를 분수로 바로 찾아요."""
    from fractions import Fraction
    top = SPLIT_SIMPLE_MAX if top is None else top
    if r is None or not (r > 0):
        return False
    f = Fraction(r).limit_denominator(10 ** 6)
    return abs(float(f) - r) <= SPLIT_CLEAN_TOL * max(1.0, r) and min(f.numerator, f.denominator) <= top


def whole_ratio(r):
    """정수(2:1 · 10:1)이거나 1/정수(1:5 병합)인 배율 — 아니면(3:2 · 21:20 …) 새로 생길 때 사람이 한 번 봐요."""
    if r is None or not (r > 0):
        return False
    x = r if r >= 1 else 1 / r
    return abs(x - round(x)) <= SPLIT_CLEAN_TOL * max(1.0, x)


def same_ratio(a, b):
    return a is not None and b is not None and abs(a - b) <= SPLIT_CLEAN_TOL * max(1.0, abs(a), abs(b))


def _split_map(raw):
    """splits 목록 → {(코드, 날짜): 배율} (모양이 맞고 배율 > 0 인 줄만 · 직전 발행본 비교용)."""
    out = {}
    for x in raw if isinstance(raw, list) else []:
        if isinstance(x, list) and len(x) == 3 and isinstance(x[0], str) and _iso_day(x[1]) and (json_num(x[2]) or 0) > 0:
            out[(x[0], x[1])] = json_num(x[2])
    return out


def _fixed_map(info):
    """splitsInfo.fixed ([[코드, 날짜, 배율 또는 null, 근거]]) → ({(코드, 날짜): 배율 또는 None}, 모양이 틀린 줄 수)."""
    out, bad = {}, 0
    for x in (info.get("fixed") if isinstance(info, dict) else None) or []:
        ok = (isinstance(x, list) and len(x) == 4 and isinstance(x[0], str) and _iso_day(x[1]) and isinstance(x[3], str) and x[3]
              and (x[2] is None or (json_num(x[2]) or 0) > 0))
        if ok:
            out[(x[0], x[1])] = json_num(x[2]) if x[2] is not None else None
        else:
            bad += 1
    return out, bad


def load_split_seed_rows(path=None):
    """data/us_splits_seed.csv (code,date,ratio,yahoo · # 줄은 설명) → {(코드, 날짜): 배율}. 이 파일의 코드로 따로 읽어요 (fetch_data.load_split_seed 와
    같은 파일). '정수가 아닌 새 배율' 경고에서 이미 검토한 줄을 빼는 데만 써요 — 읽지 못하면 한 줄 남기고 빈 표 (그날은 그 줄들도 경고해요)."""
    path = path or SPLIT_SEED_CSV
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip() and not ln.startswith("#")]
        if not lines or lines[0].strip() != "code,date,ratio,yahoo":
            raise ValueError("머리줄이 code,date,ratio,yahoo 가 아니에요")
        for ln in lines[1:]:
            t, d, r = ln.split(",")[:3]
            if not _iso_day(d.strip()) or not (float(r) > 0):
                raise ValueError(f"줄 {ln[:40]}")
            out[(t.strip(), d.strip())] = float(r)
    except Exception as e:
        print(f"· 분할 시드({os.path.basename(path)})를 읽지 못해 '정수가 아닌 새 배율' 경고에서 검토한 줄을 빼지 못해요: {type(e).__name__}: {str(e)[:100]}")
        return {}
    return out


def _diff_text(x):
    """splitsInfo.diff 한 줄 [코드, 날짜, 실은 배율, 야후 배율 또는 null, (야후 날짜)] → 글자 (모양이 틀리면 그대로)."""
    if not (isinstance(x, list) and len(x) in (4, 5) and json_num(x[2]) and (x[3] is None or json_num(x[3]))):
        return json.dumps(x, ensure_ascii=False)[:40]
    return (f"{x[0]} {x[1]} ×{x[2]:g}→" + ("없음" if x[3] is None else f"×{x[3]:g}")
            + (f" ({x[4]})" if len(x) == 5 and x[4] else ""))


def _us_codes(d):
    return {s.get("t") for s in (d or {}).get("stocks") or [] if s.get("cls") == "us" and not s.get("fund")}


def _fx_hist_vs_yesterday(ds, vs, src, pmacro):
    """v19.6a (#117 리뷰 3 N7 · 경고만): 어제 발행본의 fxHist 와 비교 — 지난 줄(어제 마지막까지, 어제 마지막 줄이 끝나지 않은 값이면 그 전까지)이
    바뀌었거나 빠졌으면, 어제 마지막 날 앞에 어제 없던 줄이 끼어들었으면, asOf 가 어제보다 앞이면, 출처가 바뀌었으면. 사용자 기록에 저장된 환율은 바뀌지 않지만 같은 날짜의 새 기록이 다른 값을
    받게 돼요. -> 경고 글 목록."""
    pfh = pmacro.get("fxHist") if isinstance(pmacro, dict) else None
    if not isinstance(pfh, dict) or not isinstance(pfh.get("rows"), list):
        return []
    if pmacro.get("fxHistSrc") != src:
        return [f"출처가 어제 {pmacro.get('fxHistSrc')!r} 에서 바뀌었어요 (같은 날짜의 값이 달라져요)"]
    prev = {}
    for r in pfh["rows"]:
        if isinstance(r, list) and len(r) == 2 and _iso_day(r[0]) and (json_num(r[1]) or 0) > 0:
            prev[r[0]] = json_num(r[1])
    if not prev:
        return []
    keys = sorted(prev)
    cut = keys[-2] if pfh.get("final") is False and len(keys) > 1 else keys[-1]
    cur = {d.isoformat(): v for d, v in zip(ds, vs)}
    changed = [d for d in keys if d <= cut and (d not in cur or abs(cur[d] - prev[d]) > 1e-9)]
    added = [d for d in sorted(cur) if d < keys[-1] and d not in prev]      # 어제 마지막 날 앞에 새로 끼어든 줄
    out = [f"지난 줄이 어제와 달라요 {len(changed)}: {', '.join(changed[:5])}"] if changed else []
    if added:
        out.append(f"어제 없던 지난 줄이 생겼어요 {len(added)}: {', '.join(added[:5])}")
    p_as_of = _iso_day(pfh.get("asOf"))
    if p_as_of and ds and ds[-1] < p_as_of:
        out.append(f"asOf {ds[-1]} 가 어제 {p_as_of} 보다 앞이에요")
    return out


def _ecos_tail_min(run_day, src):
    """휴장일 표(data/market_holidays.csv)로 본 ECOS fxHist 의 마지막 날 하한: ecos · ecos_close = 발행일 전 마지막 한국 영업일 (그날 아침
    고시 · 그날 15:30 마감은 다음 날 아침에 있어요), ecos_next = 그 전 영업일 (다음 날 매매기준율이 있어야 줄이 생겨요). 표가 덮지 못하거나
    읽지 못하면 None (그때는 FX_HIST_ECOS_TAIL 일 기준)."""
    try:
        hol, end = load_holidays()
    except Exception:
        return None
    if not (hol["start"] <= run_day - dt.timedelta(days=20) and run_day <= end):
        return None

    def prev_bd(d):
        d -= dt.timedelta(days=1)
        while d.weekday() >= 5 or d in hol["KR"]:
            d -= dt.timedelta(days=1)
        return d
    m = prev_bd(run_day)
    return prev_bd(m) if src == "ecos_next" else m


def check_v196a(rep, data, macro, by, pdata, mode, today, pmacro=None):
    """v19.6a (Part I.1 · A.6): macro.json fxHist 와 data.json splits. 세 줄."""
    run_day = _iso_day(data.get("asOf")) or today          # 발행일 (이 실행의 한국 날짜)
    # 1. 환율 이력 — 앱이 새 미국 기록에 그 날짜의 환율로 저장해요 (records.js rateFor: 그날 줄, 없으면 그 전 마지막 줄). 약속: 줄은 asOf 와 그 전
    #    날짜에만 말해요 (앱은 asOf 뒤 날짜를 받지 않아요 — 오늘만 신선한 data.json fx). asOf 가 마지막 줄과 다르면 앱이 통째로 안 써요.
    #    final = 마지막 줄이 끝난 값인지 (ECOS 출처는 늘 참 · 야후는 런던 자정이 지났는지). fxHistFresh = 출처에서 마지막으로 새로 읽은 날 —
    #    그보다 뒤 발행은 지난 발행본을 그대로 둔 것이라 경고 (줄은 그 날짜들에 대해 여전히 맞아요 · 앱은 asOf 뒤를 받지 않아요).
    name = "환율 이력 (fxHist)"
    th = (f"{FX_HIST_FROM} 부터 (첫 줄 ≤ {FX_HIST_FIRST_BY}) · 날짜 차례대로 · 줄 사이 ≤ {FX_HIST_GAP_MAX['ecos_next']}일(ECOS)/"
          f"{FX_HIST_GAP_MAX['yahoo_next']}일(야후) · 줄 사이 변화 ≤ {FX_HIST_JUMP:g}% · {FX_LO}~{FX_HI} · asOf = 마지막 날 ≤ 오늘(ecos · ecos_close)"
          f"/< 오늘(ecos_next · 야후) · 야후는 = fxDate · 마지막 값 = data.json fx ± {FX_HIST_REL:.0%} · final 참/거짓 · fxHistFresh ≤ 발행일 "
          "(없거나 · 출처 표시가 없거나 · 지난 발행본을 그대로 뒀거나 · ECOS 마지막 날이 늦으면 경고)")
    fh = macro.get("fxHist")
    src = macro.get("fxHistSrc")
    if fh is None:
        rep.add(name, True, "없음 — 앱은 지난 날짜의 미국 종목 기록을 받지 않고 그렇게 알려요", th, warn=True)
    else:
        probs, warns, ds, vs, bad = [], [], [], [], 0
        if src not in FX_HIST_SOURCES:
            warns.append(f"출처 표시 {src!r}")
        gap_max = FX_HIST_GAP_MAX.get(src, max(FX_HIST_GAP_MAX.values()))
        rows = fh.get("rows") if isinstance(fh, dict) else None
        if not isinstance(rows, list) or not rows:
            probs.append("rows 가 비었거나 목록이 아니에요")
            rows = []
        for r in rows:
            two = isinstance(r, list) and len(r) == 2
            d, v = (_iso_day(r[0]), json_num(r[1])) if two else (None, None)
            if d is None or v is None or v <= 0:
                bad += 1
                continue
            ds.append(d)
            vs.append(v)
        if bad:
            probs.append(f"모양이 틀린 줄 {bad:,}개")
        if isinstance(fh, dict) and not isinstance(fh.get("final"), bool):
            probs.append(f"final {fh.get('final')!r} (참/거짓이어야 해요)")
        if ds and not bad:
            if ds[0] < day(FX_HIST_FROM) or ds[0] > day(FX_HIST_FIRST_BY):
                probs.append(f"첫날 {ds[0]}")
            order = [f"{a}→{b}" for a, b in zip(ds, ds[1:]) if b <= a]
            if order:
                probs.append(f"날짜 차례·겹침 {len(order)}곳 ({order[0]})")
            gaps = [f"{a}→{b} {(b - a).days}일" for a, b in zip(ds, ds[1:]) if (b - a).days > gap_max]
            if gaps:
                probs.append(f"빈 날 {len(gaps)}곳 ({', '.join(gaps[:2])})")
            jumps = [f"{a} {x:g}→{y:g}" for a, b, x, y in zip(ds, ds[1:], vs, vs[1:]) if abs(y / x - 1) * 100 > FX_HIST_JUMP]
            if jumps:
                probs.append(f"큰 변화 {len(jumps)}곳 ({', '.join(jumps[:2])})")
            out = [f"{d} {v:g}" for d, v in zip(ds, vs) if not (FX_LO < v < FX_HI)]
            if out:
                probs.append(f"범위 밖 {len(out)}줄 ({', '.join(out[:2])})")
            if _iso_day(fh.get("asOf")) != ds[-1]:
                probs.append(f"asOf {fh.get('asOf')} ≠ 마지막 날 {ds[-1]}")
            same_day_ok = src in ("ecos", "ecos_close")          # 그날 고시·마감된 끝난 값이라 오늘 줄이 있을 수 있어요
            if ds[-1] > today or (not same_day_ok and ds[-1] >= today):
                probs.append(f"마지막 날 {ds[-1]} 가 오늘({today}) " + ("뒤" if ds[-1] > today else "(아직 없어야 할 줄)"))
            fxd = _iso_day(data.get("fxDate"))
            fresh = _iso_day(macro.get("fxHistFresh"))
            if src == "yahoo_next" and (fxd is None or ds[-1] > fxd or (fresh == run_day and ds[-1] != fxd)):
                probs.append(f"마지막 날 {ds[-1]} ≠ data.json fxDate {data.get('fxDate')}")
            fx = num(data.get("fx"))
            if fx is None or abs(vs[-1] / fx - 1) > FX_HIST_REL:
                probs.append(f"마지막 값 {vs[-1]:g} 이 data.json fx {data.get('fx')} 와 {FX_HIST_REL:.0%} 넘게 달라요")
            if fresh is None:
                warns.append(f"fxHistFresh {macro.get('fxHistFresh')!r}")
            elif fresh > run_day:
                probs.append(f"fxHistFresh {fresh} 가 발행일 {run_day} 뒤예요")
            elif fresh < run_day:
                warns.append(f"출처를 {fresh} 뒤로 새로 읽지 못해 지난 발행본의 이력을 그대로 뒀어요 ({(run_day - fresh).days}일째 · "
                             "asOf 뒤 날짜는 앱이 받지 않아요)")
            warns += _fx_hist_vs_yesterday(ds, vs, src, pmacro)
            if src in FX_HIST_ECOS:
                want = _ecos_tail_min(run_day, src)
                if want is not None and ds[-1] < want:
                    warns.append(f"ECOS 마지막 날 {ds[-1]} (휴장일 표로 보면 {want} 까지 있어야 해요)")
                elif want is None and (run_day - ds[-1]).days > FX_HIST_ECOS_TAIL:
                    warns.append(f"ECOS 마지막 날 {ds[-1]} 이 {FX_HIST_ECOS_TAIL}일 넘게 전이에요")
        if probs:
            rep.add(name, False, " · ".join(probs)[:200], th)
        else:
            rep.add(name, True, f"{ds[0]} ~ {ds[-1]} · {len(ds):,}일 · 마지막 {vs[-1]:,.1f}"
                    + ("" if fh.get("final") else " (아직 끝나지 않은 값)") + f" · fx {num(data.get('fx')):,.1f} · 출처 {src}"
                    + (" · " + " · ".join(warns) if warns else ""), th, warn=bool(warns))

    # 2. 주식 분할 — 앱이 분할 날짜 앞의 기록을 새 주식 수로 맞춰 읽어요 (held.js splitFactor). 배율·날짜가 틀리면 사용자의 주식 수가 틀려 보이고,
    #    한 종목의 기록이 분할 앞뒤에 걸치면 그 분할이 포트폴리오에 저장돼 남아요 (lots.js splitsToStore). 직전 발행본에서 이어 온 줄
    #    (어제도 있던 줄)은 종목이 오늘 목록에서 빠져도 남아요 (그 종목을 가진 사람이 있어요) — 그런 줄은 경고만, 새 줄은 실패.
    name = "주식 분할 목록 (splits)"
    th = (f"[코드, 날짜, 배율] · splitsFrom = {SPLITS_FROM} · {SPLITS_FROM} ≤ 날짜 ≤ 오늘 · 배율 {SPLIT_R[0]:g}~{SPLIT_R[1]:g}, 1 아님, 기약분수 "
          f"p/q 의 min(p, q) ≤ {SPLIT_SIMPLE_MAX} (splitsInfo.fixed 의 줄은 그 배율 그대로) · 같은 종목·날짜 한 번 · 새 줄은 오늘 목록의 종목 · "
          f"꼭 있어야 할 분할 {len(MUST_SPLITS)}건 · splitsAsOf 있고 오늘 뒤 아님 ({SPLIT_FRESH_MAX_DAYS}일 넘게 오래면 큰 경고 · 없음 · 지난 발행본에서 이음 · 읽지 못한 종목 · "
          f"야후와 다름 · 지운 고정 줄 · {SPLIT_NEAR_DAYS}일 안에 둘 · 오늘 목록에서 빠짐(첫날) · 미국 기준일 뒤 날짜면 경고 · "
          "직전 발행본에 있었는데 빠지면 실패)")
    sp = data.get("splits")
    prev_map = _split_map(pdata.get("splits")) if mode == "publish" and pdata and isinstance(pdata.get("splits"), list) else None
    cur = {}
    info = data.get("splitsInfo")
    fixed, fbad = _fixed_map(info)
    if sp is None:
        had = bool(pdata) and "splits" in pdata
        rep.add(name, not had, "없음" + (" — 직전 발행본에는 있었어요: 분할 전 기록이 옛 주식 수로 보여요" if had
                                        else " — 앱은 분할 전 기록을 맞추지 못해요"), th, warn=True)
    else:
        probs, warns, late, gone_code, gone_today = [], [], [], [], []
        usd = _iso_day(data.get("usPxDate"))
        if data.get("splitsFrom") != SPLITS_FROM:
            probs.append(f"splitsFrom {data.get('splitsFrom')!r}")
        if not isinstance(info, dict):
            warns.append("splitsInfo 없음")
            info = {}
        if fbad:
            probs.append(f"splitsInfo.fixed 모양이 틀린 줄 {fbad}개")
        if not isinstance(sp, list):
            probs.append("목록이 아니에요")
            sp = []
        for x in sp:
            shape = isinstance(x, list) and len(x) == 3 and isinstance(x[0], str) and bool(x[0])
            d, r = (_iso_day(x[1]), json_num(x[2])) if shape else (None, None)
            if d is None or r is None:
                probs.append(f"모양 {json.dumps(x, ensure_ascii=False)[:30]}")
                continue
            t, k = x[0], (x[0], x[1])
            fx_r = fixed.get(k, "-")
            if fx_r is None:
                probs.append(f"{t} {d} 고정 표에서 뺀 줄인데 있어요")
            elif fx_r != "-":
                if not same_ratio(r, fx_r):
                    probs.append(f"{t} {d} 배율 {r:g} ≠ 고정 표 {fx_r:g}")
            elif not (SPLIT_R[0] <= r <= SPLIT_R[1]) or r == 1:
                probs.append(f"{t} {d} 배율 {r:g}")
            elif not simple_ratio(r):
                probs.append(f"{t} {d} 배율 {r:g} (깨끗한 분수가 아니에요 — 분사 조정?)")
            if d > today:
                probs.append(f"{t} {d} 오늘 뒤")
            if d < day(SPLITS_FROM):
                probs.append(f"{t} {d} {SPLITS_FROM} 앞")
            if t not in by:
                fixed_row = fx_r not in ("-", None) and same_ratio(r, fx_r)
                if mode == "publish" and (prev_map is None or k not in prev_map) and not fixed_row:
                    probs.append(f"{t} 오늘 목록에 없음 (새 줄)")
                elif mode == "publish" and pdata and t in {s.get("t") for s in pdata.get("stocks") or []}:
                    gone_today.append(f"{t} {d}")         # 오늘 처음 목록에서 빠진 종목 (경고 · 다음 날부터는 확인 목록에만)
                else:
                    gone_code.append(f"{t} {d}")
            if k in cur:
                probs.append(f"{t} {d} 두 번")
            cur[k] = r
            if usd and d > usd and (by.get(t) or {}).get("cls") == "us":
                late.append(f"{t} {d}")
        miss = [f"{t} {d} ×{r:g}" for t, d, r in MUST_SPLITS if not same_ratio(cur.get((t, d)), r)]
        if miss:
            probs.append(f"꼭 있어야 할 분할 없음: {', '.join(miss)}")
        as_of = _iso_day(data.get("splitsAsOf"))
        if as_of is None or as_of > run_day:
            probs.append(f"splitsAsOf {data.get('splitsAsOf')!r} (있어야 하고 발행일 {run_day} 뒤면 안 돼요)")
        elif (run_day - as_of).days > SPLIT_FRESH_MAX_DAYS:      # 큰 경고 (Jack, 2026-11-13) — 발행은 해요. 그동안 새 분할은 목록에 없어요
            warns.insert(0, f"!! 야후 분할을 {(run_day - as_of).days}일째 새로 읽지 못했어요 (마지막 {as_of}): 그 뒤 새 분할은 목록에 없어요")
            print(f"!! 주식 분할: 야후 분할을 {(run_day - as_of).days}일째 새로 읽지 못했어요 (splitsAsOf {as_of}, 발행일 {run_day}) "
                  "— 발행은 막지 않아요 (Jack, 2026-11-13). 야후가 돌아오는지 확인하세요 (RUNBOOK '주식 분할').", flush=True)
        elif as_of < run_day:
            warns.append(f"야후에서 마지막으로 새로 읽은 날 {as_of}")
        src = data.get("splitsSrc")
        if src != "yahoo":                      # 값 칸에 '출처 …' 가 이미 있어요 — 경고 이유만 적어요 (#117 리뷰 4 N-7)
            warns.append({"kept": "오늘 새로 읽지 못해 지난 발행본 그대로", "part": "일부 종목을 오늘 읽지 못함"}.get(src, "출처 표시가 이상해요"))
        gap = info.get("gap") if isinstance(info.get("gap"), list) else []
        if gap:
            warns.append(f"2016년부터의 분할을 아직 읽지 못한 종목 {len(gap)}: {', '.join(map(str, gap[:5]))}")
        if (json_num(info.get("noCol")) or 0) > 0:
            warns.append(f"오늘 분할 칸을 읽지 못한 종목 {int(json_num(info.get('noCol')))}")
        diff = info.get("diff") if isinstance(info.get("diff"), list) else []
        if diff:
            warns.append(f"야후와 다름(실은 값 그대로) {len(diff)}: " + ", ".join(_diff_text(x) for x in diff[:3]))
        kept_fixed = info.get("fixedKept") if isinstance(info.get("fixedKept"), list) else []
        if kept_fixed:
            warns.append(f"고정 표에서 지운 줄을 지난 발행본에서 이어 둠 {len(kept_fixed)}: "
                         + ", ".join(" ".join(map(str, x)) for x in kept_fixed[:3]) + " (빼려면 배율을 None 으로)")
        by_t = {}
        for (t, d), r in sorted(cur.items()):
            by_t.setdefault(t, []).append(d)
        near = [f"{t} {a}·{b}" for t, l in by_t.items() for a, b in zip(l, l[1:])
                if (day(b) - day(a)).days <= SPLIT_NEAR_DAYS]
        if near:
            warns.append(f"{SPLIT_NEAR_DAYS}일 안에 분할이 둘 {len(near)}: {', '.join(near[:3])} (같은 분할이 두 번?)")
        if gone_today:
            warns.append(f"오늘 목록에서 빠진 종목의 분할(이어 둠) {len(gone_today)}: {', '.join(gone_today[:3])}")
        if late:
            warns.append(f"미국 기준일 {usd} 뒤 날짜: {', '.join(late)}")
        if probs:
            rep.add(name, False, f"{len(probs)}곳: " + " · ".join(probs[:5]), th)
        else:
            newest = sorted(cur.items(), key=lambda kv: kv[0][1])[-3:]
            rep.add(name, True, f"{len(cur):,}건 ({SPLITS_FROM} ~)" + (" · 최근 " + " · ".join(f"{t} {d} ×{r:g}" for (t, d), r in reversed(newest))
                                                                     if newest else "")
                    + f" · 고정 표 {len(fixed)}줄 · 출처 {src}" + (" · " + " · ".join(warns) if warns else ""), th, warn=bool(warns))
        if diff or gap or gone_code or gone_today:
            rep.detail("주식 분할 목록 (splits) 확인할 것", [f"야후와 다름 {_diff_text(x)}" for x in diff] + [f"아직 못 읽음 {t}" for t in gap]
                       + [f"목록에 없는 종목 {x}" for x in gone_today + gone_code])

    # 3. 직전 발행본과 비교 (발행 때만). 한 번 실은 분할은 빼지 않아요: 사라지거나 배율이 바뀌면 실패 (고정 표가 뺐거나 고친 줄은 경고).
    #    파이프라인은 야후가 어제의 분할을 빼거나 배율을 바꾸면 어제 값을 그대로 두고 splitsInfo.diff 에 적어요 (위 줄이 경고).
    #    새 줄 중 정수·1/정수가 아닌 배율(3:2 · 21:20 …)과, 어제 2016년부터 읽은 종목에 오래된 날짜로 새로 생긴 줄은 경고 (사람이 한 번 봐요).
    name = "주식 분할 목록 변화 (직전 발행본과)"
    th = ("어제 분할이 사라지거나 배율이 바뀌면 실패 (고정 표가 뺐거나 고친 줄은 경고) · 새 줄의 배율이 정수·1/정수가 아니거나, 어제 읽은 종목에 "
          f"{SPLIT_NEW_OLD_DAYS}일 넘게 지난 분할이 새로 생기면 경고")
    if mode != "publish" or not pdata:
        return                      # 사이트 점검(live) · bootstrap 은 비교 줄을 두지 않아요 (다른 '변화' 줄과 같아요)
    if prev_map is None:
        rep.skip(name, "직전 발행본에 splits 가 없어요 (첫 발행)")
        return
    if not isinstance(data.get("splits"), list):
        rep.skip(name, "이번 파일에 splits 목록이 없어요 (위 줄)")
        return
    pcov = (_us_codes(pdata) - set((pdata.get("splitsInfo") or {}).get("gap") or [])) if pdata.get("splitsFrom") == SPLITS_FROM else set()
    dropped, dropped_ok, changed, changed_ok = [], [], [], []
    for (t, d), r in sorted(prev_map.items()):
        f = fixed.get((t, d), "-")
        if (t, d) not in cur:
            (dropped_ok if f is None else dropped).append(f"{t} {d} ×{r:g}")
        elif not same_ratio(cur[(t, d)], r):
            (changed_ok if f not in ("-", None) and same_ratio(cur[(t, d)], f) else changed).append(f"{t} {d} ×{r:g}→×{cur[(t, d)]:g}")
    new = [(k, r) for k, r in sorted(cur.items()) if k not in prev_map]
    # 정수가 아닌 배율의 새 줄은 사람이 한 번 봐요 — 단 이미 검토한 줄은 빼요: 커밋한 시드(data/us_splits_seed.csv)의 줄이나 고정 표의 줄이 같은 배율로
    # 나온 것 (그 종목이 목록에 다시 들 때 · AAON 3:2). 야후에서 새로 온 줄만 경고해요 (#117 · 아침 점검이 매번 노랗지 않게).
    seed = load_split_seed_rows()
    reviewed = lambda t, d, r: same_ratio(seed.get((t, d)), r) or same_ratio(fixed.get((t, d)), r)     # noqa: E731
    odd = [f"{t} {d} ×{r:g}" for (t, d), r in new if not whole_ratio(r) and not reviewed(t, d, r)]
    old_new = [f"{t} {d} ×{r:g}" for (t, d), r in new if t in pcov and d < (run_day - dt.timedelta(days=SPLIT_NEW_OLD_DAYS)).isoformat()]
    fails = ([f"사라짐 {len(dropped)}: {', '.join(dropped[:3])}"] if dropped else []) + \
            ([f"배율 바뀜 {len(changed)}: {', '.join(changed[:3])}"] if changed else [])
    warns = ([f"고정 표가 뺌 {len(dropped_ok)}: {', '.join(dropped_ok[:3])}"] if dropped_ok else []) + \
            ([f"고정 표가 고침 {len(changed_ok)}: {', '.join(changed_ok[:3])}"] if changed_ok else []) + \
            ([f"새 줄 정수 아닌 배율 {len(odd)}: {', '.join(odd[:3])}"] if odd else []) + \
            ([f"지난 날짜로 새로 {len(old_new)}: {', '.join(old_new[:3])}"] if old_new else [])
    parts = fails + warns
    rep.add(name, not fails, " · ".join(parts) if parts else f"그대로 (어제 {len(prev_map):,}건 → 오늘 {len(cur):,}건 · 새 {len(new)}건)", th,
            warn=bool(warns))
    if parts:
        rep.detail("주식 분할 목록 변화 (직전 발행본과)", [f"사라짐 {x}" for x in dropped] + [f"배율 바뀜 {x}" for x in changed]
                   + [f"고정 표가 뺌 {x}" for x in dropped_ok] + [f"고정 표가 고침 {x}" for x in changed_ok]
                   + [f"새 줄 정수 아닌 배율 {x}" for x in odd] + [f"지난 날짜로 새로 {x}" for x in old_new])


# ── v19.6b (Part B.1 · 오늘 볼 것 데이터): disc.json issue · insider role · data.json 미국 ed · xd — 새 줄 셋 (v19.6 스펙 'Test changes',
#    Jack 의 yes). 파이프라인(fetch_data.fetch_issues · insider_pos_role · us_event_dates)과 따로 적어요. 칸이 아예 없는 파일(v19.6b 전 —
#    머지 직후의 배포 · 감시 --live 가 보는 사이트 파일)은 경고만, 모양이 틀린 값은 실패, 빈 issue 목록은 경고만 (발행을 막지 않아요).
#    어떤 JSON 값이 와도 검사가 멈추지 않아요 (멈추면 관문이 발행을 막아요): 예상하지 못한 오류는 그 줄의 실패로 적어요 (표는 그대로 나와요).
ISSUE_KINDS = ("rights", "cb", "bw")
ISSUE_HOW = ("holders", "others")
ISSUE_KEYS = ("rc", "d", "t", "nk", "kind", "bd", "how", "n", "p", "amt", "cor")
ISSUE_CLS = ("common", "other")   # Jack 2026-11-19 (7b): 유상증자 n · p 의 주식 종류 (보통주 · 기타주식 — 같은 종류끼리 비율)
ISSUE_DAYS = 90             # fetch_data.DISC_DAYS — 공시일 d 는 disc.json asOf 를 포함한 90일 안
ISSUE_P_WARN = 3000.0       # % — 새 주식이 증자 전 주식 수의 30배를 넘는 줄은 이름과 함께 경고 (2026-11-15 가장 큰 값: STX 유상증자 1,855.66%)
ISSUE_BLANK_WARN = 10.0     # % — 숫자가 하나도 없는 줄(n · p · amt 모두 빈 칸)이 이보다 많으면 경고 (상세를 다 읽지 못한 날 · 첫 실행은 약 28%,
#                             다 읽은 날 2026-11-16 은 13 / 295 = 4.4% — DART 상세 API 가 '-' 만 주는 정정 공시)
INSIDER_ROLES = ("임원", "주요주주", "임원·주요주주")   # Jack 2026-11-19 (7c): 임원이면서 주요주주 → '임원·주요주주' (글자 그대로)
POS_DASHES = ("-", "－", "—", "–", "‐")
US_DATE_FAR_DAYS = 400      # 실적 발표일 · 배당락일이 발행일보다 이만큼 넘게 뒤면 이름과 함께 경고 (야후 값이 틀렸을 수 있어요)
US_DATE_MIN_US = 100        # 미국 종목이 이만큼 넘는데 실적 발표일이나 배당락일이 하나도 없으면 경고 (야후 칸 이름이 바뀐 날)
ISSUE_NUM_KEYS = ("d", "kind", "bd", "n", "p", "amt")   # 없으면 틀린 숫자를 보일 수 있는 칸 (_issue_row_bad 의 wrong)

# ── Jack 의 상시 규칙 (2026-11-19 ~17:45 KST, 그대로): "Standing rule for checks on our own processing: a single bad row is dropped or
#    blanked with a loud warning and the rest publishes. Block only when many rows fail in one run (set the number from recent runs and show
#    it in the PR) or when a value would show a wrong number." — #145 의 네 검사 (issue 모양 · insider role · 미국 ed · xd · 유상증자 bd).
#    나쁜 행은 아래 함수가 골라요 (파이프라인과 관문이 같은 함수 · 한 곳). 파이프라인은 쓰기 바로 앞에서 그 행을 빼거나 값을 비우고, 크게 남기고,
#    그 파일의 ownDrop[열쇠] = {"n", "rows" 앞 30} 에 적어요 (깨끗한 실행도 0). 관문: n 이 N 을 넘거나 틀린 숫자를 보일 값이 남으면 실패 ·
#    1~N 또는 숫자를 보이지 않는 값이 남으면 경고 · 0 이면 통과. 기록이 없는 예전 파일은 예전 규칙 그대로 (--live · 감시).
#    N 은 최근 실행에서 (PR #145 의 표: data 브랜치 발행 25번 + 이 브랜치 시험 실행 5번 — 모두 0) max(5, 3 × 가장 큰 수) = 5.
OWN_ROWS_SHOW = 30                 # 기록 · 로그 · 관문 값 칸에 이름을 적는 행 수
ISSUE_SHAPE_KEY = "issueShape"     # disc.json ownDrop: 모양이 틀린 issue 줄 (뺐어요)
ISSUE_BD_KEY = "issueBd"           # disc.json ownDrop: 공시일 뒤의 유상증자 결의일 (bd 를 비웠어요)
INSIDER_ROLE_KEY = "insiderRole"   # disc.json ownDrop: 허용하지 않은 insider role (비웠어요) · 객체가 아닌 insider 줄 (뺐어요)
US_DATE_KEY = "usDates"            # data.json ownDrop: 틀린 미국 ed · xd (비웠어요)
ISSUE_SHAPE_MAX = 5                # PR #145 표 (최근 실행 0) — max(5, 3 × 0)
ISSUE_BD_MAX = 5                   # PR #145 표 (최근 실행 0)
INSIDER_ROLE_MAX = 5               # PR #145 표 (최근 실행 0)
US_DATE_MAX = 5                    # PR #145 표 (최근 실행 0)


def _ymd8(x):
    """'YYYYMMDD' 로 적힌 진짜 날짜면 date, 아니면 None (어떤 값이 와도 예외 없음 · 아라비아 숫자 0-9 만)."""
    if not isinstance(x, str) or not re.fullmatch(r"[0-9]{8}", x):
        return None
    try:
        return dt.date(int(x[:4]), int(x[4:6]), int(x[6:8]))
    except ValueError:
        return None


def _short(x, n=16):
    """값을 표에 적을 짧은 글 (어떤 값이든)."""
    try:
        s = json.dumps(x, ensure_ascii=False)
    except (TypeError, ValueError):
        s = repr(x)
    return s if len(s) <= n else s[:n] + "…"


def _issue_row_bad(r, base):
    """disc.json issue 한 줄의 모양 문제 [(글, 틀린 숫자를 보일 수 있는지)] — 비면 괜찮아요. base = 목록의 날짜 (disc.json asOf).
    어떤 JSON 값이 와도 예외 없이 답해요. 둘째 값(wrong)은 Jack 의 상시 규칙(2026-11-19)의 '틀린 숫자를 보일 값' — 날짜(d · bd) · 숫자(n · p ·
    amt · n2 · p2) · 숫자를 읽는 법을 바꾸는 표시(kind · cls · bonus · wd · pend)의 문제예요. 접수번호 · 종목 · 이름 · 방식(how) · 정정 표시(cor)의
    문제는 숫자를 보이지 않아요 (틀린 링크 · 글자 · 빈 카드)."""
    if not isinstance(r, dict):
        return [(f"줄이 객체가 아님 {_short(r)}", False)]
    p = []
    miss = [k for k in ISSUE_KEYS if k not in r]
    if miss:
        p.append(("칸 없음 " + ",".join(miss), any(k in ISSUE_NUM_KEYS for k in miss)))
    if not _rc_ok(r.get("rc"), base):
        p.append((f"rc {_short(r.get('rc'))}", False))
    d = _ymd8(r.get("d"))
    if d is None:
        p.append((f"d {_short(r.get('d'))}", True))
    elif d > base or (base - d).days >= ISSUE_DAYS:
        p.append((f"d {r['d']} 가 {ISSUE_DAYS}일 기간 밖 (asOf {base})", True))
    for k in ("t", "nk"):
        if not (isinstance(r.get(k), str) and r[k].strip()):
            p.append((f"{k} {_short(r.get(k))}", False))
    kind = r.get("kind")
    if not (isinstance(kind, str) and kind in ISSUE_KINDS):
        p.append((f"kind {_short(kind)}", True))
    rights = kind == "rights"
    if r.get("bd") is not None and _ymd8(r.get("bd")) is None:
        p.append((f"bd {_short(r.get('bd'))}", True))
    how = r.get("how")
    if how is not None and not (rights and isinstance(how, str) and how in ISSUE_HOW):
        p.append((f"how {_short(how)}" + ("" if rights else " (유상증자만)"), False))
    n = r.get("n")
    if n is not None and not (rights and _posint(n)):
        p.append((f"n {_short(n)}" + ("" if rights else " (유상증자만)"), True))
    pv = json_num(r.get("p"))
    if r.get("p") is not None and (pv is None or pv <= 0):
        p.append((f"p {_short(r.get('p'))}", True))
    amt = json_num(r.get("amt"))
    if r.get("amt") is not None and (rights or amt is None or amt <= 0):
        p.append((f"amt {_short(r.get('amt'))}" + (" (사채만)" if rights else ""), True))
    if not isinstance(r.get("cor"), bool):
        p.append((f"cor {_short(r.get('cor'))}", False))
    # 리뷰 2026-11-16: wd (철회 — 숫자 칸이 모두 '-' 인 정정) · pend (상세를 아직 못 읽음) 는 있을 때만, 참/거짓이고 그 줄의 숫자는 비어 있어요
    for k in ("wd", "pend"):
        if k in r and not isinstance(r[k], bool):
            p.append((f"{k} {_short(r[k])}", True))
    if r.get("wd") is True and r.get("pend") is True:
        p.append(("wd 와 pend 가 함께 참", True))
    for k in ("wd", "pend"):
        if r.get(k) is True:
            full = [f for f in ("bd", "how", "n", "p", "amt", "cls", "n2", "p2") if r.get(f) is not None]
            if full:
                p.append((f"{k} 인데 {','.join(full)} 이 있어요", True))
    # Jack 2026-11-19 (7a · 7b): 유상증자 줄의 cls (n · p 의 주식 종류) · n2 · p2 (보통주와 함께 낸 기타주식) · bonus (유무상증자) — 새 검사
    if "cls" in r and not (rights and (r["cls"] is None or (isinstance(r["cls"], str) and r["cls"] in ISSUE_CLS))):
        p.append((f"cls {_short(r['cls'])}" + ("" if rights else " (유상증자만)"), True))
    if rights and r.get("n") is not None and not isinstance(r.get("cls"), str):
        p.append(("n 이 있는데 cls 가 없어요", True))
    if "n2" in r or "p2" in r:
        if not (rights and r.get("cls") == "common" and _posint(r.get("n2"))):
            p.append((f"n2 {_short(r.get('n2'))} (보통주 줄의 기타주식 수만)", True))
        pv2 = json_num(r.get("p2"))
        if r.get("p2") is not None and (pv2 is None or pv2 <= 0):
            p.append((f"p2 {_short(r.get('p2'))}", True))
    if "bonus" in r and not (rights and r["bonus"] is True):
        p.append((f"bonus {_short(r['bonus'])}" + ("" if rights else " (유상증자만)"), True))
    return p


def issue_row_problems(r, base):
    """disc.json issue 한 줄의 모양 문제 (글) 목록 — 비면 괜찮아요 (_issue_row_bad 의 글만). 어떤 JSON 값이 와도 예외 없이 답해요."""
    return [t for t, _w in _issue_row_bad(r, base)]


def _own_key(r, i):
    """나쁜 행의 이름: 접수번호(글자)면 그것, 아니면 '#순번'."""
    return r["rc"] if isinstance(r, dict) and isinstance(r.get("rc"), str) and r["rc"].strip() else f"#{i}"


def issue_bad_rows(rows, base):
    """Jack 의 상시 규칙 (2026-11-19) · 주요사항 공시 (issue) 줄 모양: 뺄 줄 [(순번, 이름, 이유, 틀린 숫자를 보일 수 있는지, None)].
    파이프라인(fetch_data.own_check_disc — 줄을 빼요)과 관문(_check_issue)이 같은 함수를 써요. 모양이 틀린 줄 + 같은 접수번호가 여러 번 나온
    줄(모두 — 어느 쪽이 맞는지 몰라요). (순수 함수 · 어떤 JSON 값에도 예외 없음)"""
    out, ok = [], []
    for i, r in enumerate(rows if isinstance(rows, list) else []):
        pr = _issue_row_bad(r, base)
        if pr:
            out.append((i, _own_key(r, i), "; ".join(t for t, _w in pr), any(w for _t, w in pr), None))
        else:
            ok.append((i, r))
    seen = collections.Counter(r["rc"] for _i, r in ok)
    # 리뷰 2차 (2026-11-19): 같은 접수번호의 두 줄은 n · p 가 다를 수 있어요 — B.2 카드가 issue 를 읽으면 틀린 숫자예요 (wrong)
    out += [(i, r["rc"], f"같은 접수번호가 {seen[r['rc']]}번", True, None) for i, r in ok if seen[r["rc"]] > 1]
    return sorted(out)


def issue_bd_bad_rows(rows):
    """Jack 의 상시 규칙 · 유상증자 이사회 결의일: 비울 bd [(순번, 접수번호, 이유, True, "bd")] — 철회 · 읽는 중이 아닌 유상증자 줄의 결의일이 공시일
    뒤 (공시는 결의 뒤에 내요 — 원문 · 상세를 우리가 잘못 읽은 것). 파이프라인(bd 를 비워요)과 관문(check_issue_bd)이 같은 함수를 써요.
    결의일은 그 결정의 숫자에 붙는 날짜라 남으면 틀린 숫자를 보일 값이에요. (순수 함수)"""
    out = []
    for i, r in enumerate(rows if isinstance(rows, list) else []):
        if not (isinstance(r, dict) and r.get("kind") == "rights" and r.get("wd") is not True and r.get("pend") is not True):
            continue
        b, d = _ymd8(r.get("bd")), _ymd8(r.get("d"))
        if b is not None and d is not None and b > d:
            out.append((i, _own_key(r, i), f"bd {r['bd']} > d {r['d']}", True, "bd"))
    return out


def insider_bad_rows(rows):
    """Jack 의 상시 규칙 · 임원 · 주요주주 역할: [(순번, 이름, 이유, 틀린 숫자를 보일 수 있는지, 비울 칸 · 줄째 빼면 None)].
    객체가 아닌 줄은 빼요 — 남으면 실패 (wrong): 예전 뱁새가 줄마다 칸을 읽다가 멈춰요 (src/disc.jsx 업종 칸 x.s · src/corp.jsx 종목 칸 x.t —
    null 줄에서 오류 · 화면이 깨져요) · 2.0 공시 탭도 그 줄의 주식 수 · 금액을 읽어요. 허용하지 않은 role 은 비워요 (role 은 글자 — 숫자가
    아니에요 · 아직 어느 화면도 읽지 않아요). 파이프라인(fetch_data.own_check_disc)과 관문(_check_roles)이 같은 함수를 써요. (순수 함수)"""
    out = []
    for i, r in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(r, dict):
            out.append((i, f"#{i}", f"객체가 아닌 줄 {_short(r)}", True, None))
        elif "role" in r and r["role"] is not None and not (isinstance(r["role"], str) and r["role"] in INSIDER_ROLES):
            out.append((i, _own_key(r, i), f"role {_short(r['role'])}", False, "role"))
    return out


def us_date_bad_rows(stocks):
    """Jack 의 상시 규칙 · 미국 일정 (ed · xd): 비울 값 [(순번, '티커 칸', 이유, False, 칸)] — 미국 종목이 아닌데 있는 날짜 · YYYY-MM-DD 진짜
    날짜가 아닌 값. 종목 행은 그대로 두고 그 칸만 비워요 (가격 · 배당 숫자는 맞아요 · 행을 빼면 다른 검사(v19.1i 배당 증명 목록)가 깨져요).
    실적 발표일 · 배당락일은 일정의 날짜라 숫자에 붙는 날짜가 아니에요 (남아도 틀린 숫자는 아니에요). 파이프라인(fetch_data.own_us_dates)과
    관문(_check_us_dates)이 같은 함수를 써요. (순수 함수)"""
    out = []
    for i, s in enumerate(stocks if isinstance(stocks, list) else []):
        if not isinstance(s, dict):
            continue
        for k in ("ed", "xd"):
            v = s.get(k)
            if v is None or v == "":
                continue                       # 빈 칸 (모름)
            t = s.get("t") if isinstance(s.get("t"), str) else _short(s.get("t"))
            if s.get("cls") != "us":
                out.append((i, f"{t} {k}", f"{_short(v)} (미국 종목이 아님)", False, k))
            elif _iso_day(v) is None:
                out.append((i, f"{t} {k}", f"{_short(v)} (YYYY-MM-DD 날짜가 아님)", False, k))
    return out


def own_rows_rec(rows):
    """나쁜 행 [(순번, 이름, 이유, …)] → 발행 파일의 ownDrop[열쇠] 값 {"n": 수, "rows": [[이름, 이유]] 앞 OWN_ROWS_SHOW 개}. (순수 함수)
    모양은 #149 (claude/own-check-rule) 의 data.json ownDrop (own_drop_rec · own_drop_text · own_drop_get) 과 같아요. 지금은 도우미가 두 벌이에요
    (own_rows_* · #149 의 own_drop_*) — 둘 다 들어오면 하나로 합쳐요 (기록 모양 · 읽는 규칙은 같아요)."""
    return {"n": len(rows), "rows": [[str(r[1]), str(r[2])] for r in rows[:OWN_ROWS_SHOW]]}


def own_rows_text(rows, n=None):
    """[[이름, 이유]] 또는 [(순번, 이름, 이유, …)] → '이름 (이유) · …' 앞 OWN_ROWS_SHOW 개 (+ ' 외 N건')."""
    pick = [(r[0], r[1]) if len(r) == 2 else (r[1], r[2]) for r in rows[:OWN_ROWS_SHOW]]
    n = len(rows) if n is None else n
    return " · ".join(f"{a} ({b})" for a, b in pick) + (f" 외 {n - OWN_ROWS_SHOW}건" if n > OWN_ROWS_SHOW else "")


def own_rows_get(doc, key):
    """발행 파일의 ownDrop[key] → ("none", None) 기록이 없음 (예전 파일 — 예전 규칙) · ("bad", 글) 기록의 모양이 틀림 (예전 규칙 + 경고) ·
    ("ok", (n, rows)). 어떤 JSON 값이 와도 예외 없음."""
    if not isinstance(doc, dict) or "ownDrop" not in doc:
        return "none", None
    own = doc["ownDrop"]
    if not isinstance(own, dict):          # 리뷰 2차: 칸은 있는데 객체가 아님 — 조용히 넘기지 않고 예전 규칙 + 경고 (#149 의 own_drop_get 과 같아요)
        return "bad", f"ownDrop 이 객체가 아님 {_short(own, 40)}"
    if key not in own:
        return "none", None
    rec = own[key]
    n, rows = (rec.get("n"), rec.get("rows")) if isinstance(rec, dict) else (None, None)
    if not (isinstance(rec, dict) and set(rec) == {"n", "rows"} and isinstance(n, int) and not isinstance(n, bool) and n >= 0 and isinstance(rows, list)
            and len(rows) == min(n, OWN_ROWS_SHOW)
            and all(isinstance(x, list) and len(x) == 2 and all(isinstance(v, str) for v in x) for x in rows)):
        return "bad", f"ownDrop.{key} 기록 모양이 틀림 {_short(rec, 40)}"
    return "ok", (n, rows)


def own_verdict(state, rec, remaining, mx, what):
    """Jack 의 상시 규칙의 판정 (새 파일만): → (실패 글 목록, 경고 글 목록). 실패 = 이번 실행에 빼거나 비운 행이 mx 를 넘음 · 빼야 할 값이 남았고
    틀린 숫자를 보일 수 있음. 경고 = 1~mx 행을 빼거나 비움 · 남은 값이 숫자를 보이지 않음. what = '뺀 줄' · '비운 값' 같은 말."""
    fails, warns = [], []
    if state != "ok":
        return fails, warns
    n, rows = rec
    if n > mx:
        fails.append(f"이번 실행에 {what} {n:,}개 — {mx}개를 넘어요 (한 번에 많은 행이 틀림 · {own_rows_text(rows, n)[:120]})")
    elif n:
        warns.append(f"파이프라인이 {what} {n:,}개 ({own_rows_text(rows, n)[:150]})")
    wrong = [r for r in remaining if r[3]]
    rest = [r for r in remaining if not r[3]]
    if wrong:
        fails.append(f"빼거나 비워야 할 값이 남았어요 {len(wrong):,}개 — 틀린 숫자를 보일 수 있어요 ({wrong[0][1]} {wrong[0][2]})"[:200])
    if rest:
        warns.append(f"빼거나 비워야 할 값이 남았어요 {len(rest):,}개 — 숫자를 보이지 않아요 ({rest[0][1]} {rest[0][2]})"[:200])
    return fails, warns


def _check_issue(rep, disc, by, base):
    name = "주요사항 공시 (issue · 유상증자 · CB · BW)"
    th = (f"줄마다 {'·'.join(ISSUE_KEYS)} · rc 접수번호 · d YYYYMMDD 가 asOf 까지 {ISSUE_DAYS}일 안 · kind {'|'.join(ISSUE_KINDS)} · bd 빈 칸 "
          f"또는 YYYYMMDD · how 빈 칸 또는 {'|'.join(ISSUE_HOW)} (유상증자만) · n 양의 정수 (유상증자만) · p 양수 · amt 양수 (사채만) · cor 참/거짓 · "
          f"접수번호 한 번 · issueOk 참/거짓 · wd · pend 는 있으면 참/거짓이고 그 줄의 숫자는 빈 칸 · 유상증자의 cls 는 {'|'.join(ISSUE_CLS)}|null "
          f"(n 이 있으면 꼭) · n2 · p2 는 보통주 줄만 · bonus 는 유상증자에 true 만 (실패) — 칸이 없음(v19.6b 전 파일) · "
          f"issueOk false · 0건 · 오늘 국내 목록 밖 종목 · p · p2 > {ISSUE_P_WARN:,.0f}% · 숫자 없는 줄(철회 빼고) > {ISSUE_BLANK_WARN:g}% 는 경고 · "
          f"새 파일(ownDrop.{ISSUE_SHAPE_KEY} 있음 · Jack 의 상시 규칙 2026-11-19): 파이프라인이 뺀 줄이 {ISSUE_SHAPE_MAX}개를 넘거나 틀린 숫자를 "
          "보일 줄이 남으면 실패, 그 밖의 모양 문제 · 목록 · issueOk 모양은 경고")
    if "issue" not in disc:
        rep.add(name, True, "없음 — v19.6b 전 파일이에요 (DART 를 쓴 실행은 늘 써요)", th, warn=True)
        return
    state, rec = own_rows_get(disc, ISSUE_SHAPE_KEY)
    new = state == "ok"
    rows, flag = disc.get("issue"), disc.get("issueOk")
    probs, warns = [], []
    if state == "bad":
        warns.append(f"{rec} — 예전 규칙으로 봐요")
    if not isinstance(rows, list):
        (warns if new else probs).append(f"목록이 아님 {_short(rows)}")       # 새 파일: 숫자를 보이지 않아요 (아직 어느 화면도 issue 를 읽지 않아요)
        rows = []
    if not isinstance(flag, bool):
        (warns if new else probs).append(f"issueOk {_short(flag)}")
    elif not flag:
        warns.append("목록을 받지 못해 지난 발행본의 줄을 그대로 뒀어요 (issueOk false — 앱은 늦음 · 실패 줄)")
    if new:                                # Jack 의 상시 규칙: 같은 함수(issue_bad_rows)로 남은 줄을 봐요
        left = issue_bad_rows(rows, base)
        drop = {x[0] for x in left}
        good = [r for i, r in enumerate(rows) if i not in drop]
        f2, w2 = own_verdict(state, rec, left, ISSUE_SHAPE_MAX, "뺀 줄")
        probs += f2
        warns += w2
        if rec[1]:
            rep.detail("주요사항 공시 (issue) 파이프라인이 뺀 줄", [f"{a} ({b})" for a, b in rec[1]])
        if left:
            rep.detail("주요사항 공시 (issue) 남은 모양 문제", [f"{x[1]} {x[2]}" + (" (틀린 숫자)" if x[3] else "") for x in left[:50]])
    else:                                  # 예전 파일 (기록 없음): 예전 규칙 그대로
        bad, good = [], []
        for r in rows:
            pr = issue_row_problems(r, base)
            if pr:
                bad.append(f"{_short(r.get('rc')) if isinstance(r, dict) else '?'} {'; '.join(pr)}")
            else:
                good.append(r)
        if bad:
            probs.append(f"모양이 틀린 줄 {len(bad):,}개 ({bad[0][:120]})")
            rep.detail("주요사항 공시 (issue) 모양이 틀린 줄", bad[:50])
        seen = collections.Counter(r["rc"] for r in good)
        dup = sorted(rc for rc, c in seen.items() if c > 1)
        if dup:
            probs.append(f"같은 접수번호 {len(dup)}개 ({', '.join(dup[:3])})")
    gone = sorted({r["t"] for r in good if (by.get(r["t"]) or {}).get("cls") != "kr"})
    if gone:
        warns.append(f"오늘 국내 목록에 없는 종목 {len(gone)}곳 ({', '.join(gone[:5])})")
    # 리뷰 2026-11-19: 보통주와 함께 낸 기타주식의 비율(p2)도 같은 경고 (더하기만)
    big = [f"{r['nk']} " + " · ".join(f"{r[k]:,.2f}%" + (" (p2)" if k == "p2" else "") for k in ("p", "p2")
                                      if r.get(k) is not None and r[k] > ISSUE_P_WARN)
           for r in good if any(r.get(k) is not None and r[k] > ISSUE_P_WARN for k in ("p", "p2"))]
    if big:
        warns.append(f"p 가 {ISSUE_P_WARN:,.0f}% 넘는 줄 {len(big)}개 ({', '.join(big[:3])} — 공시를 확인해요)")
    live = [r for r in good if r.get("wd") is not True]               # 철회 줄은 숫자가 없는 게 맞아요
    blank = sum(1 for r in live if r.get("n") is None and r.get("p") is None and r.get("amt") is None)
    if live and 100.0 * blank / len(live) > ISSUE_BLANK_WARN:
        warns.append(f"숫자가 하나도 없는 줄 {blank:,} / {len(live):,} ({100.0 * blank / len(live):.1f}% — 상세를 다 읽지 못했어요 · 앱은 '숫자를 못 "
                     "읽은' 줄)")
    if not rows and flag is True:
        warns.append("0건 — 90일 동안 한 건도 없는 건 드물어요 (발행은 막지 않아요 · 목록 읽기를 확인해요)")
    kinds = collections.Counter(r["kind"] for r in good)
    val = (" · ".join(f"{ko} {kinds[k]:,}" for k, ko in zip(ISSUE_KINDS, ("유상증자", "CB", "BW"))) + f" (정정 {sum(1 for r in good if r['cor']):,} · 철회 {len(good) - len(live):,} · 읽는 중 "
           f"{sum(1 for r in good if r.get('pend') is True):,} · 숫자 없는 줄 {blank:,})"
           + (f" · 유무상증자 {sum(1 for r in good if r.get('bonus') is True):,}" if any(r.get("bonus") is True for r in good) else "")
           + (f" · 기타주식 줄 {sum(1 for r in good if r.get('cls') == 'other'):,}" if any(r.get("cls") == "other" for r in good) else "")
           + (" · " + " · ".join(probs) if probs else "") + (" · " + " · ".join(warns) if warns else ""))
    rep.add(name, not probs, val[:300], th, warn=bool(warns))


def _check_roles(rep, disc):
    name = "임원 · 주요주주 역할 (insider role)"
    th = (f"role 은 {' | '.join(INSIDER_ROLES)} | null (실패) — role 칸이 없는 줄(v19.6b 전) · 직위(pos)가 '-' 인 줄은 경고 "
          f"(DART 의 '-' 는 빈 칸이에요) · 새 파일(ownDrop.{INSIDER_ROLE_KEY} 있음 · Jack 의 상시 규칙 2026-11-19): 파이프라인이 빼거나 비운 줄이 "
          f"{INSIDER_ROLE_MAX}개를 넘거나 객체가 아닌 줄이 남으면 실패 (예전 뱁새가 그 줄의 칸을 읽다가 멈춰요 — disc.jsx x.s · corp.jsx x.t), 남은 "
          "틀린 role 은 경고 · insider 가 목록이 아니면 실패 (칸 전체 — 공시 탭이 '보고 없음'을 지금 데이터처럼 보이면 안 돼요)")
    ins = disc.get("insider")
    if not isinstance(ins, list):
        rep.add(name, False, f"insider 가 목록이 아님 {_short(ins)}", th)
        return
    state, rec = own_rows_get(disc, INSIDER_ROLE_KEY)
    nokey, dash, cnt = 0, 0, collections.Counter()
    for r in ins:
        if not isinstance(r, dict):
            continue
        if "role" not in r:
            nokey += 1
        elif r["role"] is None or (isinstance(r["role"], str) and r["role"] in INSIDER_ROLES):
            cnt[r["role"]] += 1
        if isinstance(r.get("pos"), str) and r["pos"].strip() in POS_DASHES:
            dash += 1
    left = insider_bad_rows(ins)
    warns = ([f"role 칸이 없는 줄 {nokey:,} (v19.6b 전 줄)"] if nokey else []) + ([f"직위가 '-' 인 줄 {dash:,}"] if dash else [])
    if state == "ok":                      # Jack 의 상시 규칙 (새 파일)
        fails, w2 = own_verdict(state, rec, left, INSIDER_ROLE_MAX, "빼거나 비운 줄")
        warns += w2
        bad = []
        if rec[1]:
            rep.detail("임원 · 주요주주 역할 (insider role) 파이프라인이 빼거나 비운 줄", [f"{a} ({b})" for a, b in rec[1]])
        if left:
            rep.detail("임원 · 주요주주 역할 (insider role) 남은 문제", [f"{x[1]} {x[2]}" for x in left[:50]])
    else:                                  # 예전 파일: 예전 규칙 그대로 (틀린 줄은 실패)
        fails = []
        if state == "bad":
            warns.append(f"{rec} — 예전 규칙으로 봐요")
        bad = [x[2] if x[4] is None else f"{_short(ins[x[0]].get('rc'))} {x[2]}" for x in left]
        if bad:
            rep.detail("임원 · 주요주주 역할 (insider role) 틀린 줄", bad[:50])
    rep.add(name, not (bad or fails), (f"틀린 줄 {len(bad):,} ({bad[0][:80]}) · " if bad else "")
            + (" · ".join(fails) + " · " if fails else "")
            + f"임원 {cnt['임원']:,} · 주요주주 {cnt['주요주주']:,} · "
            + (f"임원·주요주주 {cnt['임원·주요주주']:,} · " if cnt["임원·주요주주"] else "")
            + f"없음 {cnt[None]:,} / {len(ins):,}줄" + (" · " + " · ".join(warns) if warns else ""),
            th, warn=bool(warns))


def _check_us_dates(rep, data, base):
    name = "미국 일정 (ed 실적 발표일 · xd 배당락일)"
    th = (f"미국 종목만 · 빈 칸 또는 YYYY-MM-DD 진짜 날짜 (실패) — 둘 다 하나도 없음(v19.6b 전 파일 · 미국 {US_DATE_MIN_US}종목 넘을 때) · "
          f"발행일보다 {US_DATE_FAR_DAYS}일 넘게 뒤는 경고 · 새 파일(ownDrop.{US_DATE_KEY} 있음 · Jack 의 상시 규칙 2026-11-19): 파이프라인이 비운 "
          f"값이 {US_DATE_MAX}개를 넘으면 실패, 남은 틀린 값은 경고 (일정의 날짜 — 숫자에 붙는 날짜가 아니에요)")
    stocks = data.get("stocks")
    stocks = [s for s in stocks if isinstance(s, dict)] if isinstance(stocks, list) else []
    state, rec = own_rows_get(data, US_DATE_KEY)
    left = us_date_bad_rows(stocks)
    bad_i = {(x[0], x[4]) for x in left}
    far, n = [], collections.Counter()
    for i, s in enumerate(stocks):
        for k in ("ed", "xd"):
            v = s.get(k)
            if v is None or v == "" or (i, k) in bad_i:
                continue                       # 빈 칸 (모름) · 틀린 값 (위)
            d = _iso_day(v)
            n[k] += 1
            if (d - base).days > US_DATE_FAR_DAYS:
                t = s.get("t") if isinstance(s.get("t"), str) else _short(s.get("t"))
                far.append(f"{t} {k} {v}")
    us = sum(1 for s in stocks if s.get("cls") == "us")
    warns = []
    if state == "ok":                      # Jack 의 상시 규칙 (새 파일): 남은 틀린 값은 경고 · 비운 수가 N 을 넘으면 실패
        fails, w2 = own_verdict(state, rec, left, US_DATE_MAX, "비운 값")
        warns += w2
        bad = []
        if rec[1]:
            rep.detail("미국 일정 (ed · xd) 파이프라인이 비운 값", [f"{a} ({b})" for a, b in rec[1]])
        if left:
            rep.detail("미국 일정 (ed · xd) 남은 틀린 값", [f"{x[1]} {x[2]}" for x in left[:50]])
    else:                                  # 예전 파일: 예전 규칙 그대로 (틀린 값은 실패)
        fails = []
        if state == "bad":
            warns.append(f"{rec} — 예전 규칙으로 봐요")
        bad = [f"{x[1]} {x[2]}".replace(" (YYYY-MM-DD 날짜가 아님)", "") for x in left]
    if us > US_DATE_MIN_US and not (n["ed"] or n["xd"]):
        warns.append("둘 다 하나도 없음 (v19.6b 전 파일이거나 야후 칸 이름이 바뀌었어요)")
    else:
        warns += [f"{'실적 발표일' if k == 'ed' else '배당락일'}이 하나도 없음" for k in ("ed", "xd") if us > US_DATE_MIN_US and not n[k]]
    if far:
        warns.append(f"{US_DATE_FAR_DAYS}일 넘게 뒤 {len(far)}개 ({', '.join(far[:3])})")
    if bad:
        rep.detail("미국 일정 (ed · xd) 틀린 값", bad[:50])
    rep.add(name, not (bad or fails), (f"틀린 값 {len(bad):,} ({bad[0][:60]}) · " if bad else "") + (" · ".join(fails) + " · " if fails else "")
            + f"실적 발표일 {n['ed']:,} · 배당락일 {n['xd']:,} / 미국 {us:,}종목" + (" · " + " · ".join(warns) if warns else ""),
            th, warn=bool(warns))


def check_v196b(rep, data, disc, by, today):
    """v19.6b (Part B.1): 세 줄 — 주요사항 공시 (issue) · 임원 · 주요주주 역할 (insider role) · 미국 일정 (ed · xd)."""
    disc = disc if isinstance(disc, dict) else {}
    data = data if isinstance(data, dict) else {}
    by = by if isinstance(by, dict) else {}
    for name, fn, args in (("주요사항 공시 (issue · 유상증자 · CB · BW)", _check_issue, (disc, by, _iso_day(disc.get("asOf")) or today)),
                           ("임원 · 주요주주 역할 (insider role)", _check_roles, (disc,)),
                           ("미국 일정 (ed 실적 발표일 · xd 배당락일)", _check_us_dates, (data, _iso_day(data.get("asOf")) or today))):
        try:
            fn(rep, *args)
        except Exception as e:             # 검사 코드의 잘못 — 표는 나오고 이 줄은 실패예요 (확인하지 못한 것을 통과라고 하지 않아요)
            rep.add(name, False, f"검사가 오류로 멈췄어요: {type(e).__name__}: {str(e)[:120]}", "오류 없이 끝나야 함")


# ── v19.6b Q18 (Jack 2026-11-19 "rights board date from documents: yes"): 유상증자 줄의 bd — 파이프라인(fetch_data.fill_issue_bd)이 공시
#    원문의 이사회결의일(결정일)을 읽어 채워요. 새 줄 하나 (더하기만 · check_v196b 의 세 줄은 그대로). 대상은 철회(wd)도 읽는 중(pend)도 아닌
#    유상증자 줄. 실패: 결의일이 공시일 뒤 (공시는 결의 뒤에 내요 — 우리 읽기의 잘못). 경고: 결의일이 빈 줄 (원문을 아직 다 읽지 못했거나 원문에서
#    읽지 못했어요 — 머지 뒤 첫 실행은 실행당 100건 한도로 남아요). issue 가 없는 파일(v19.6b 전)은 SKIP (위 '주요사항 공시' 줄이 경고해요).
ISSUE_BD_ROW = "유상증자 이사회 결의일 (issue bd · 공시 원문)"


def _check_issue_bd(rep, disc):
    th = ("철회 · 읽는 중이 아닌 유상증자 줄의 bd 가 공시일 d 뒤면 실패 — bd 가 빈 줄이 있으면 경고 (원문을 아직 다 읽지 못했거나 원문에서 "
          f"읽지 못했어요 · 실행 로그의 '유상증자 이사회 결의일' 줄) · 새 파일(ownDrop.{ISSUE_BD_KEY} 있음 · Jack 의 상시 규칙 2026-11-19): "
          f"파이프라인이 비운 결의일이 {ISSUE_BD_MAX}개를 넘거나 공시일 뒤 결의일이 남으면 실패, 1개 이상 비웠으면 경고")
    rows = disc.get("issue")
    if not isinstance(rows, list):
        rep.skip(ISSUE_BD_ROW, "issue 가 없거나 목록이 아니에요 (v19.6b 전 파일 — 위 '주요사항 공시' 줄이 봐요)")
        return
    state, rec = own_rows_get(disc, ISSUE_BD_KEY)
    left = issue_bd_bad_rows(rows)           # 공시일 뒤 결의일 (파이프라인과 같은 함수)
    after_i = {x[0] for x in left}
    tg = [(i, r) for i, r in enumerate(rows)
          if isinstance(r, dict) and r.get("kind") == "rights" and r.get("wd") is not True and r.get("pend") is not True]
    have, miss = 0, []
    for i, r in tg:
        if _ymd8(r.get("bd")) is None:
            miss.append(r)                 # 빈 칸 (모양이 틀린 bd 는 '주요사항 공시' 줄이 잡아요)
        elif i not in after_i:
            have += 1
    after = [f"{_short(rows[x[0]].get('nk'))} {_short(rows[x[0]].get('rc'))} {x[2]}" for x in left]
    fails, warns = own_verdict(state, rec, [], ISSUE_BD_MAX, "비운 결의일")     # 남은 값은 아래 (공시일 뒤 결의일은 늘 실패 — 틀린 숫자)
    if state == "bad":
        warns.append(f"{rec} — 예전 규칙으로 봐요")
    if state == "ok" and rec[1]:
        rep.detail("유상증자 이사회 결의일 파이프라인이 비운 값", [f"{a} ({b})" for a, b in rec[1]])
    if after:
        rep.detail("유상증자 이사회 결의일이 공시일 뒤인 줄", after[:50])
    if miss:
        rep.detail("유상증자 이사회 결의일이 빈 줄", [f"{_short(r.get('nk'))} {_short(r.get('d'))} {_short(r.get('rc'))}" for r in miss[:50]])
    val = (f"결의일 있음 {have:,} / 대상 {len(tg):,}"
           + (f" · 공시일 뒤 결의일 {len(after):,} ({after[0][:80]})" if after else "")
           + (f" · 결의일 빈 줄 {len(miss):,} (원문을 아직 다 읽지 못했거나 원문에서 못 읽음)" if miss else "")
           + (" · " + " · ".join(fails + warns) if fails or warns else ""))
    rep.add(ISSUE_BD_ROW, not (after or fails), val[:300], th, warn=bool(miss or warns))


def check_issue_bd(rep, disc):
    """v19.6b Q18: 한 줄 — 유상증자 이사회 결의일 (issue bd). 어떤 JSON 값이 와도 표는 나와요 (예상하지 못한 오류는 이 줄의 실패)."""
    try:
        _check_issue_bd(rep, disc if isinstance(disc, dict) else {})
    except Exception as e:
        rep.add(ISSUE_BD_ROW, False, f"검사가 오류로 멈췄어요: {type(e).__name__}: {str(e)[:120]}", "오류 없이 끝나야 함")


# ── v19.6e (Part I.2): data.json c1w · wkFrom · usWkFrom — 이번 주 정리 (Part E) 가 쓰는 그 주 시작 종가 ──────────────────────────────────────
#    파이프라인(fetch_data.c1w_fields)이 종목마다 '그 시장의 이번 주(기준일이 든 월 ~ 일) 앞 마지막 거래일' 종가를 c1w 로 실어요 — 한국 주식은 그날
#    최종본 목록 파일의 공식 종가 (가격과 같은 출처) · 미국 주식은 가격과 같은 야후 수정 종가 · 채권 · ETF · 금은 가격과 같은 시계열. 그 날짜는
#    wkFrom (한국 · 채권 · ETF · 금) · usWkFrom (미국 주식). 자기 가격 날짜(pxd · pxc · 금 추정)인 종목 · 그 사이 KRX 기준가가 새로 정해졌거나 상장
#    주식 수가 20% 넘게 바뀐 한국 종목은 빈 칸이에요. 이 줄은 경고만 해요 (발행을 멈추는 줄은 Jack 의 답이 있어야 해요 · 화면 PR 에서 물어요).
C1W_ROW = "이번 주 시작 종가 (c1w · wkFrom · usWkFrom · 경고만)"
C1W_COVER_MIN = 95.0        # % — 그 시장 기준일 종가 종목 중 c1w 가 있는 비율이 이보다 낮으면 경고 (보통 주의 빈 칸은 새 상장 · 분할 · 권리락 ·
#                             주식 수 변화로 국내 수십 종목 = 1 ~ 2% · 미국은 새 종목뿐). 파이프라인도 이 값 아래면 크게 남겨요
C1W_FROM_MAX_DAYS = 12      # wkFrom · usWkFrom 은 기준일보다 이 날 수 안 (휴장일 표 2026 ~ 2027 의 가장 긴 사이 9일: 추석 2026-09-23 → 10-02 ·
#                             연말 2026-12-30 → 2027-01-08 — 갑자기 정해지는 임시공휴일 몫으로 3일 더). 파이프라인도 넘으면 그 주 날짜를 쓰지 않아요
C1W_RATIO_BAND = (0.5, 2.0) # price ÷ c1w 가 이 밖이면 (한 주에 반 넘게 내림 · 두 배 넘게 오름) 이름을 적어요 — 진짜 움직임일 수 있어요 (확인용).
#                             미국 주식 · 채권 · ETF · 금은 경고. 한국 주식은 가격 제한폭(코스피 · 코스닥 30% · 코넥스 15%)을 그 주 거래일 수만큼 곱한
#                             범위 안이면 이름만 (경고 아님 — 테마주의 진짜 움직임이 한 달에 몇 번 있어요 · 알림 소음), 그 범위 밖이면 '제한폭 밖'으로 경고
#                             (제한폭이 없는 정리매매 날 말고는 보통 파이프라인이 놓친 기준가 재설정이에요)
C1W_SHOW = 10               # 값 칸에 적는 종목 수 (나머지는 요약 목록에)
C1W_GROUPS = ("kr", "us", "fund")
C1W_GROUP_KO = {"kr": "국내", "us": "미국", "fund": "채권·ETF·금"}


def c1w_group(s):
    """c1w 의 시장 (파이프라인과 관문이 같은 함수 · 순수 함수): 'fund' 채권 · ETF · 금 (fund 표시 · cls bond — 한국 상장이라 wkFrom) ·
    'us' 미국 주식 (usWkFrom) · 'kr' 한국 주식 (wkFrom) · 그 밖은 None (c1w 를 싣지 않아요)."""
    if not isinstance(s, dict):
        return None
    if s.get("fund") or s.get("cls") == "bond":
        return "fund"
    return s.get("cls") if s.get("cls") in ("kr", "us") else None


def c1w_own_date(s):
    """그 종목의 가격이 그 시장 기준일의 종가가 아니면 True — 마지막 확인 종가 · 거래 정지(pxd · pxc) · 금현물 추정 가격(est). 이 종목들은 c1w 가 빈
    칸이에요: price ÷ c1w − 1 이 그 주 전체가 아니라 그 종목 날짜까지의 움직임이 돼요 (Part E: 그 주 전체를 확인하지 않은 말은 하지 않아요). (순수 함수)"""
    return isinstance(s, dict) and (s.get("pxd") is not None or bool(s.get("pxc")) or bool(s.get("est")))


def c1w_week_expect(px, closed, start=None, end=None):
    """휴장일 표로 본 '기준일(px)이 든 주의 월요일 앞 마지막 거래일' (주말 · 표의 휴장일 빼고 · 표가 덮지 않는 날은 평일 규칙). (순수 함수 · 관문의 따로 된 계산)"""
    d = px - dt.timedelta(days=px.weekday() + 1)
    for _ in range(40):
        covered = (start is None or d >= start) and (end is None or d <= end)
        if d.weekday() < 5 and not (covered and d in closed):
            return d
        d -= dt.timedelta(days=1)
    return None


def _c1w_idx_days(macro, name):
    """macro.json idxHist[name] 의 거래일들 (YYYY-MM-DD · 정렬) — 어느 칸이든 모양이 틀리면 None (이 줄 전체가 멈추지 않게). (순수 함수)"""
    ih = macro.get("idxHist") if isinstance(macro, dict) else None
    one = ih.get(name) if isinstance(ih, dict) else None
    rows = one.get("rows") if isinstance(one, dict) else None
    if not isinstance(rows, list):
        return None
    ds = sorted({str(r[0]) for r in rows if isinstance(r, (list, tuple)) and r and is_day(r[0])})
    return ds or None


def _check_v196e(rep, data, macro):
    th = (f"경고만 (발행을 막지 않아요) — wkFrom · usWkFrom: YYYY-MM-DD · 기준일(pxDate · usPxDate)이 든 주의 월요일 앞 · 기준일과 {C1W_FROM_MAX_DAYS}일 안 · "
          "휴장일 표 · 지수 일봉(idxHist)으로 본 그 주 앞 마지막 거래일과 같음 · c1w: 빈 칸 또는 0 보다 큰 유한한 숫자 · 자기 가격 날짜(pxd · pxc · est) "
          f"종목은 빈 칸 · 기준일 종가 종목 중 채움 ≥ {C1W_COVER_MIN:g}% (국내 · 미국) · 채권·ETF·금 모두 · price ÷ c1w 가 "
          f"{C1W_RATIO_BAND[0]:g} ~ {C1W_RATIO_BAND[1]:g} 밖이면 이름 (미국 · 채권·ETF·금은 경고 · 한국은 그 주 거래일만큼 곱한 가격 제한폭 밖일 때만 경고 — 제한폭을 모르면 경고) · "
          "c1wSrc (목록 + KRX + 지난 발행본 + 네이버 = 국내 c1w 수 · 네이버 = c1wv nv 행 수) · c1wv 는 한국 주식 c1w 옆의 nv 만")
    stocks = [s for s in data.get("stocks") or [] if isinstance(s, dict)] if isinstance(data.get("stocks"), list) else []
    n_c1w = sum(1 for s in stocks if s.get("c1w") is not None)
    if "wkFrom" not in data and "usWkFrom" not in data and not n_c1w:
        rep.add(C1W_ROW, True, "없음 — v19.6e 전 파일 (이번 주 정리 화면은 아직 이 칸을 읽지 않아요)", th, warn=True)
        return
    warns = []
    try:
        hol, end = load_holidays()
    except Exception as e:
        hol, end = None, None
        warns.append(f"휴장일 표를 읽지 못해 날짜를 표와 맞춰 보지 않았어요 ({type(e).__name__})")
    dates = {}
    kdays, udays = _c1w_idx_days(macro, "KOSPI"), _c1w_idx_days(macro, "SP500")
    notes = [f"{n} 없어 지수 일봉 확인{' · 한국 제한폭 확인' if n == 'idxHist KOSPI' else ''} 건너뜀" for n, d in (("idxHist KOSPI", kdays), ("idxHist SP500", udays))
             if d is None]
    for g, key, pkey, mk, days in (("kr", "wkFrom", "pxDate", "KR", kdays), ("us", "usWkFrom", "usPxDate", "US", udays)):
        dates[g] = None
        raw = data.get(key)
        if key not in data:
            warns.append(f"{key} 칸 없음")
            continue
        if raw is None:
            warns.append(f"{key} 빈 값 (파이프라인이 그 주 시작 날짜를 정하지 못했어요 · 실행 로그의 'c1w' 줄)")
            continue
        wk = _iso_day(raw)
        if wk is None:
            warns.append(f"{key} {_short(raw)} (YYYY-MM-DD 날짜가 아님)")
            continue
        dates[g] = wk
        px = _iso_day(data.get(pkey))
        if px is None:
            warns.append(f"{pkey} 가 없어 {key} 를 맞춰 보지 못했어요")
            continue
        mon = px - dt.timedelta(days=px.weekday())
        if wk >= mon:
            warns.append(f"{key} {wk} 가 {pkey} {px} 의 주 월요일({mon}) 앞이 아님")
        elif (px - wk).days > C1W_FROM_MAX_DAYS:
            warns.append(f"{key} {wk} 가 {pkey} {px} 보다 {(px - wk).days}일 앞 (> {C1W_FROM_MAX_DAYS}일)")
        if wk.weekday() >= 5:
            warns.append(f"{key} {wk} 가 주말")
        if hol is not None:
            exp = c1w_week_expect(px, hol[mk], hol.get("start"), end)
            if exp != wk:
                warns.append(f"{key} {wk} ≠ 휴장일 표로 본 그 주 앞 마지막 거래일 {exp}")
        before = [d for d in (days or []) if d < mon.isoformat()]
        if before and before[-1] != wk.isoformat():
            warns.append(f"{key} {wk} ≠ 지수 일봉(idxHist {'KOSPI' if g == 'kr' else 'SP500'})으로 본 {before[-1]}")
    # 한국 주식의 제한폭 범위: 그 주 거래일 수 (wkFrom < 날 ≤ pxDate · 지수 일봉) — 모르면 이 범위는 보지 않아요 (값 칸에 적어요)
    px_kr = _iso_day(data.get("pxDate"))
    n_kr = (sum(1 for d in kdays if dates["kr"].isoformat() < d <= px_kr.isoformat())
            if kdays and dates["kr"] is not None and px_kr is not None else 0)
    knx = {s.get("t") for s in stocks if c1w_group(s) == "kr" and _KNX_TAIL.search(str(s.get("dk") or ""))}
    cnt = {g: [0, 0] for g in C1W_GROUPS}          # [c1w 있음, 기준일 종가 종목]
    bad, own, nodate, odd, far, lim, kr_far, badv = [], [], [], [], [], [], [], []
    n_nv = 0
    for s in stocks:
        g = c1w_group(s)
        t, nk = s.get("t"), s.get("nk")
        nm = (f"{t if isinstance(t, str) else _short(t)} " + (nk[:12] if isinstance(nk, str) else "")).strip()
        v0 = s.get("c1w")
        if "c1wv" in s:                       # 4차 (S1): 네이버 수정주가로 확인한 한국 주식의 c1w 에만 "nv"
            if s.get("c1wv") == "nv" and g == "kr" and json_num(v0) is not None and not c1w_own_date(s):
                n_nv += 1
            else:
                badv.append(f"{nm} {_short(s.get('c1wv'))}")
        if g is None:
            if v0 is not None:
                odd.append(nm)
            continue
        if not c1w_own_date(s):
            cnt[g][1] += 1
        if v0 is None:
            continue
        v = json_num(v0)
        if v is None or v <= 0:
            bad.append(f"{nm} {_short(v0)}")
            continue
        if c1w_own_date(s):
            own.append(nm)
            continue
        if dates["us" if g == "us" else "kr"] is None:
            nodate.append(nm)
            continue
        cnt[g][0] += 1
        p = json_num(s.get("price"))
        if p is None or p <= 0:
            continue
        r = p / v
        if not math.isfinite(r):
            bad.append(f"{nm} {_short(v0)} (price ÷ c1w 가 무한대)")
            cnt[g][0] -= 1
            continue
        txt = f"{nm} {(r - 1) * 100:+.0f}%"
        if g == "kr" and n_kr:
            k = (KONEX_DAY_LIMIT if s.get("t") in knx else KR_DAY_LIMIT) / 100.0
            if r < (1 - k) ** n_kr * (1 - 1e-9) or r > (1 + k) ** n_kr * (1 + 1e-9):
                lim.append(txt)
                continue
        if not (C1W_RATIO_BAND[0] <= r <= C1W_RATIO_BAND[1]):     # 3차 (검증): 제한폭을 모르는 날 (idxHist KOSPI 없음) 은 한국도 경고
            (kr_far if g == "kr" and n_kr else far).append(txt)
    parts = []
    src = data.get("c1wSrc")
    # 5차 (Jack, 2026-11-22): pub — 지난 발행본 종가와 KRX 기준가로 확인한 국내 c1w (지난 발행본을 볼 수 있던 실행에만 · 없으면 0 으로 셈)
    src_ok = isinstance(src, dict) and all(isinstance(src.get(k), int) and not isinstance(src.get(k), bool) and src[k] >= 0
                                            for k in ("listing", "krx", "naver") + (("pub",) if "pub" in src else ()))
    n_pub = src.get("pub", 0) if src_ok else 0
    for g, key in (("kr", "wkFrom"), ("us", "usWkFrom")):
        k, n = cnt[g]
        how = (f" · 목록 {src['listing']:,} · KRX {src['krx']:,}" + (f" · 지난 발행본 {n_pub:,}" if "pub" in src else "")
               + f" · 네이버 {src['naver']:,}" if g == "kr" and src_ok else "")
        parts.append(f"{C1W_GROUP_KO[g]} {k:,} / {n:,} ({key} {dates[g] or '없음'}{how})")
        if dates[g] is not None and n and 100.0 * k / n < C1W_COVER_MIN:      # 내림으로 적어요 (94.96% 가 95.0% 로 보이지 않게)
            warns.append(f"{C1W_GROUP_KO[g]} 채움 {math.floor(1000.0 * k / n) / 10:.1f}% (< {C1W_COVER_MIN:g}%)")
    if not src_ok and src is not None:
        warns.append(f"c1wSrc 모양이 틀림 ({_short(src, 40)})")
    elif src is None and ("wkFrom" in data or n_c1w):
        warns.append("c1wSrc 없음 (국내 c1w 를 어떻게 확인했는지 몰라요)")
    elif src_ok and (src["listing"] + src["krx"] + n_pub + src["naver"] != cnt["kr"][0] or src["naver"] != n_nv):
        warns.append(f"c1wSrc (목록 {src['listing']:,} + KRX {src['krx']:,}" + (f" + 지난 발행본 {n_pub:,}" if "pub" in src else "")
                     + f" + 네이버 {src['naver']:,}) 가 종목과 다름 (국내 c1w {cnt['kr'][0]:,} · c1wv nv {n_nv:,})")
    k, n = cnt["fund"]
    parts.append(f"{C1W_GROUP_KO['fund']} {k} / {n}")
    if dates["kr"] is not None and k < n:
        warns.append(f"{C1W_GROUP_KO['fund']} 빈 칸 {n - k}")
    for title, items, what in (("c1w 가 숫자가 아니거나 0 이하", bad, "숫자가 아님"), ("자기 가격 날짜 종목에 c1w", own, "자기 가격 날짜 종목에 있음"),
                               ("c1wv 가 한국 주식 c1w 옆의 nv 가 아님", badv, "c1wv 이상"),
                               ("그 시장 날짜(wkFrom · usWkFrom) 없이 c1w", nodate, "그 시장 날짜 없이 있음"),
                               ("시장을 모르는 행에 c1w", odd, "시장을 모르는 행에 있음"),
                               (f"price ÷ c1w 가 {C1W_RATIO_BAND[0]:g} ~ {C1W_RATIO_BAND[1]:g} 밖 (확인 · 미국 · 채권·ETF·금 · 제한폭을 모르는 날의 한국)", far,
                                f"{C1W_RATIO_BAND[0]:g} ~ {C1W_RATIO_BAND[1]:g} 밖"),
                               (f"한국 주식 price ÷ c1w 가 가격 제한폭 {n_kr}거래일 밖", lim, "제한폭 밖")):
        if items:
            rep.detail(title, items[:50])
            warns.append(f"{what} {len(items):,} ({', '.join(items[:C1W_SHOW])}{' …' if len(items) > C1W_SHOW else ''})")
    info = list(notes)
    if kr_far:                                # 한국 주식 · 제한폭 안: 이름만 (경고 아님)
        rep.detail(f"한국 주식 price ÷ c1w 가 {C1W_RATIO_BAND[0]:g} ~ {C1W_RATIO_BAND[1]:g} 밖 (제한폭 안 · 확인용)", kr_far[:50])
        info.append(f"한국 {C1W_RATIO_BAND[0]:g} ~ {C1W_RATIO_BAND[1]:g} 밖 {len(kr_far):,} (경고 아님 · {', '.join(kr_far[:C1W_SHOW])}"
                    f"{' …' if len(kr_far) > C1W_SHOW else ''})")
    rep.add(C1W_ROW, True, (" · ".join(parts + warns + info))[:600], th, warn=bool(warns))


def check_v196e(rep, data, macro):
    """v19.6e (Part I.2): 한 줄 — 이번 주 시작 종가 (c1w · wkFrom · usWkFrom). 경고만: 검사 코드가 멈춰도 실패가 아니라 경고예요 (이 줄은 발행을
    멈추지 않아요 — 멈추는 줄은 Jack 의 답을 받아서)."""
    try:
        _check_v196e(rep, data if isinstance(data, dict) else {}, macro if isinstance(macro, dict) else {})
    except Exception as e:
        rep.add(C1W_ROW, True, f"검사가 오류로 멈췄어요: {type(e).__name__}: {str(e)[:120]}", "오류 없이 끝나야 함 (경고만 · 발행을 막지 않아요)", warn=True)


# ── 2026-11-23 (Jack, 11-19 Q6 · 11-23): 차등배당 회사의 소액주주 배당 — data.json 종목 dpsSmall · dytSmall · 기록 divSmall · corp.json 같은 두 칸 ──
#    파이프라인(fetch_data.small_holder_div)이 배당 기준 증명이 data/div 로 숨긴 종목 중, 사업보고서 원문이 차등배당이라고 적고 그 1주 배당을 소액주주 몫이라고
#    적는 종목에만 실어요 (dpsSmall = 배당 표의 1주 배당 그대로 · dytSmall = dpsSmall ÷ 오늘 종가). 이 줄은 경고만 해요 (발행을 멈추는 줄은 Jack 의 답이
#    있어야 해요): 실은 회사와 숫자를 적고, 숫자끼리 · 기록과 어긋나거나 조회가 실패했으면 경고해요. 앱은 스위치와 승인한 말이 있을 때만 보여 줘요.
SMALL_DIV_ROW = "소액주주 배당수익률 (dpsSmall · dytSmall · divSmall · 경고만)"
SMALL_DIV_SHOW = 10


def _sn(x):
    """숫자 칸만 숫자로 (글자 '550' · 참거짓 · NaN 은 아니에요 — #183 리뷰)."""
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def _check_small_div(rep, data, corp, pdata=None):
    kr = [s for s in data.get("stocks") or [] if isinstance(s, dict)]
    comps = {c.get("t"): c for c in (corp or {}).get("companies") or [] if isinstance(c, dict)}
    rec = data.get("divSmall")
    prev = (pdata or {}).get("divSmall") if isinstance(pdata, dict) else None
    has = [s for s in kr if "dpsSmall" in s or "dytSmall" in s]
    th = "숫자끼리 · 기록과 맞아야 함 · 새로 실은 회사는 근거 문장을 사람이 봐요 (경고만 · 발행을 막지 않아요)"
    if rec is None:
        why = []
        if has:
            why.append(f"기록(divSmall) 없이 칸이 있는 종목 {len(has):,}: " + ", ".join(str(s.get("t")) for s in has[:SMALL_DIV_SHOW]))
        if prev is not None:
            why.append("지난 발행본에는 기록(divSmall)이 있었는데 이번에는 없어요")
        rep.add(SMALL_DIV_ROW, True, " · ".join(why) if why else "기록 없음 (이 단계 전의 파일)", th, warn=bool(why))
        return
    if not isinstance(rec, dict) or rec.get("v") != 1 or not isinstance(rec.get("on"), dict):
        rep.add(SMALL_DIV_ROW, True, f"기록(divSmall) 모양이 달라요: {str(rec)[:120]}", th, warn=True)
        return
    on = rec["on"]
    bad = []
    for s in has:
        t = s.get("t")
        d, y, p = _sn(s.get("dpsSmall")), _sn(s.get("dytSmall")), _sn(s.get("price"))
        d3 = s.get("dps3") if isinstance(s.get("dps3"), list) and s.get("dps3") else [None]
        why = []
        if s.get("cls") != "kr" or is_pref(str(t)):
            why.append("국내 보통주가 아님")
        if d is None or d <= 0:
            why.append(f"dpsSmall {s.get('dpsSmall')!r}")
        elif _sn(d3[0]) is None or abs(_sn(d3[0]) - d) > 1e-6:
            why.append(f"dpsSmall {d:,.2f} ≠ 배당 표 {d3[0]!r}")
        if y is None or not (0.01 <= y <= DYT_MAX):
            why.append(f"dytSmall {s.get('dytSmall')!r}")
        elif d is not None and p and p > 0 and abs(round(d / p * 100, 2) - y) > 0.006:
            why.append(f"dytSmall {y} ≠ {d:,.2f} ÷ {p:,.0f}")
        if num(s.get("dyt")) is not None:
            why.append("dyt 가 보이는 종목")
        if s.get("dvLine") not in (None, 3):
            why.append(f"dvLine {s.get('dvLine')!r}")
        r = on.get(t)
        if not isinstance(r, dict) or _sn(r.get("d")) != d or _sn(r.get("y")) != y:
            why.append("기록(divSmall.on)과 다름")
        elif not isinstance(r.get("q"), str) or not r["q"].strip():
            why.append("근거 문장(q) 없음")
        c = comps.get(t)
        if c is not None and (_sn(c.get("dpsSmall")) != d or _sn(c.get("dytSmall")) != y):
            why.append("corp.json 과 다름")
        if why:
            bad.append(f"{t} {' · '.join(why)}")
    seen = {s.get("t") for s in has}
    bad += [f"{t} 기록에만 있음" for t in on if t not in seen]
    bad += [f"{t} corp.json 에만 있음" for t, c in comps.items() if ("dpsSmall" in c or "dytSmall" in c) and t not in seen]
    fail = rec.get("fail") if isinstance(rec.get("fail"), dict) else {}
    pon = prev.get("on") if isinstance(prev, dict) and isinstance(prev.get("on"), dict) else {}
    new = sorted(t for t in on if t not in pon)
    names = [f"{t} {(r or {}).get('nk', '')} {_sn((r or {}).get('d')) or 0:,.0f}원 {_sn((r or {}).get('y')) or 0:.2f}%".replace("  ", " ")
             for t, r in sorted(on.items())]
    parts = [f"실음 {len(on):,}" + (": " + ", ".join(names[:SMALL_DIV_SHOW]) + (" …" if len(names) > SMALL_DIV_SHOW else "") if names else ""),
             f"대상 {rec.get('cand', '?')} · 그대로 {len(rec.get('no') or {}):,}"]
    if rec.get("skip"):
        parts.append(f"건너뜀: {str(rec['skip'])[:120]}")
    warns = []
    if bad:
        warns.append(f"어긋남 {len(bad):,}: " + "; ".join(bad[:5]))
        rep.detail("소액주주 배당수익률 어긋남", bad)
    if new:
        # #183 리뷰 (Fable S2): 지난 발행본에 없던 회사 — 원문의 근거 문장을 사람이 읽어요 (스위치를 켜기 전 · 켠 뒤에도 새 회사마다)
        warns.append(f"새로 실은 회사 {len(new):,} (근거 문장을 확인하세요): " + ", ".join(new[:5]))
        rep.detail("소액주주 배당수익률 새로 실은 회사의 근거 문장",
                   [f"{t} {(on[t] or {}).get('nk', '')}: {str((on[t] or {}).get('q') or '(없음)')[:300]}" for t in new])
    if fail:
        warns.append(f"조회 실패 {len(fail):,}: " + ", ".join(f"{t} {w}" for t, w in sorted(fail.items())[:3]))
    if rec.get("err"):
        warns.append(f"단계 오류: {str(rec['err'])[:120]}")
    if names:
        rep.detail("소액주주 배당수익률 (차등배당 · 실은 회사)", names)
    rep.add(SMALL_DIV_ROW, True, (" · ".join(parts + warns))[:600], th, warn=bool(warns))


def check_small_div(rep, data, corp, pdata=None):
    """2026-11-23: 한 줄 — 소액주주 배당수익률 (경고만: 검사 코드가 멈춰도 실패가 아니라 경고예요)."""
    try:
        _check_small_div(rep, data if isinstance(data, dict) else {}, corp if isinstance(corp, dict) else {}, pdata)
    except Exception as e:
        rep.add(SMALL_DIV_ROW, True, f"검사가 오류로 멈췄어요: {type(e).__name__}: {str(e)[:120]}",
                "오류 없이 끝나야 함 (경고만 · 발행을 막지 않아요)", warn=True)


def check_v1751(rep, cur, kr, us, by, comps, px, today, hilo, us_own=frozenset()):
    data, macro = cur["data"], cur["macro"]
    must_kr = [t for t in MUST if (by.get(t) or {}).get("cls") == "kr"]

    # 1. 화면에 나가는 글자에 nan·None·null·undefined 가 낱말로 없어야 해요 (설명 열 밀림 사고: "nan · 주요제품: …")
    bad = []
    for name in ("data", "corp", "disc", "macro"):
        for path, v in text_values(cur.get(name) or {}):
            if BAD_WORD.search(v):
                bad.append(f"{name}.{path}={v[:30]}")
    rep.add("글자에 nan·None·null·undefined 없음", not bad, f"{len(bad):,}곳" + (f" (예: {bad[0]})" if bad else ""), "0곳")
    # 파이프라인 안에서만 쓰는 임시 칸(_로 시작)이 파일에 새어 나가지 않았는지
    leak = sorted({k for name in ("data", "corp") for x in ((cur.get(name) or {}).get("stocks") or (cur.get(name) or {}).get("companies") or [])
                   for k in x if str(k).startswith("_")})
    rep.add("임시 칸(_…) 없음", not leak, "없음" if not leak else ",".join(leak[:5]), "0개")

    # 1b. 국내 설명: 소속부(우량기업부 등)가 업종 자리에 들어가지 않고, 주요제품이 업종 이름의 복사가 아니어야 해요
    dept = [s["t"] for s in kr if any(d in (s.get("dk") or "") for d in KR_DEPTS)]
    rep.add("국내 설명에 소속부 없음", not dept, f"{len(dept):,}종목" + (f" (예: {dept[0]})" if dept else ""), "0종목")
    same = 0
    for s in kr:
        parts = [x.strip() for x in (s.get("dk") or "").split(" · ")]
        prod = next((x[len("주요제품: "):] for x in parts if x.startswith("주요제품: ")), None)
        if prod is not None and parts and parts[0] == prod:
            same += 1
    share = 100.0 * same / len(kr) if kr else 0.0
    rep.add("국내 주요제품 ≠ 업종 이름", share <= PROD_SAME_MAX, f"{share:.1f}% ({same:,}종목)", f"≤ {PROD_SAME_MAX}%")

    # 4. d1: 전 거래일 공식 종가 대비 %
    miss = [t for t in must_kr if num((by.get(t) or {}).get("d1")) is None]
    rep.add("필수 종목 d1", not miss, "모두 있음" if not miss else "없음: " + ",".join(miss), ",".join(must_kr))
    cov = coverage(kr, "d1")       # 스펙: d1 이 빠진다고 실패하는 건 필수 종목뿐 — 채움은 경고로만
    rep.add("국내 d1 채움", True, f"{cov:.1f}%", f"≥ {D1_COVER}% (모자라면 경고)", warn=cov < D1_COVER)
    out = [s["t"] for s in kr if num(s.get("d1")) is not None and abs(num(s["d1"])) > D1_MAX_KR]
    rep.add("국내 d1 범위 (±30%)", not out, f"넘는 종목 {len(out)}" + (f" (예: {out[0]})" if out else ""), "0 (넘으면 빈 칸이어야 해요)")
    usby = {s.get("t"): s for s in us}
    # 2026-11-20 (Jack: "A US stock with no close from Yahoo carries its last confirmed close … so a Yahoo gap never stops the Korean
    # data again"): 마지막 확인 종가로 맞게 실린 필수 종목(us_own)은 d1 이 없는 게 맞아요 — 경고 (이름 · 그 날짜), 실패는 그 밖에 d1 이 없을 때만
    miss_us = [t for t in ("AAPL", "MSFT", "NVDA") if num((usby.get(t) or {}).get("d1")) is None and t not in us_own]
    own_us = [t for t in ("AAPL", "MSFT", "NVDA") if num((usby.get(t) or {}).get("d1")) is None and t in us_own]
    rep.add("미국 필수 종목 d1", not miss_us,
            ("모두 있음" if not miss_us else "없음: " + ",".join(miss_us))
            + (" · 마지막 확인 종가: " + ", ".join(f"{t}({usby[t].get('pxd')})" for t in own_us) if own_us else ""),
            "AAPL·MSFT·NVDA" + (" (마지막 확인 종가는 경고)" if own_us else ""), warn=bool(own_us) and not miss_us)
    # 4b. 미국 d1 채움 (Jack, 2026-11-07). 2026-11-07 야후가 개별 종목의 11-06 봉을 비웠는데(S&P 500 은 있음) 그대로 갔으면
    # 미국 가격이 하루 전 종가로 '11-06 기준'이 될 뻔했어요 — 필수 세 종목이 마침 같이 빠져서 잡혔어요. 이제 일부만 빠져도 잡아요.
    # d1 은 파이프라인이 그 종목의 마지막 봉이 미국 기준일(usPxDate = S&P 500 의 마지막 '끝난' 거래일)일 때만 채워요
    # (fetch_data.us_d1). 미국 휴장일·조기 폐장일에는 기준일이 그 전 거래일 / 그날이라 d1 이 줄지 않아요 (tests/test_pipeline.py).
    us_no_d1 = [str(s.get("t")) for s in us if num(s.get("d1")) is None]
    us_cov = 100.0 * (len(us) - len(us_no_d1)) / len(us) if us else 0.0    # 보여 줄 때는 내림 (97.95% 가 '98.0%' 로 안 보이게)
    shown = ", ".join(us_no_d1[:US_D1_SHOW]) + (f" 외 {len(us_no_d1) - US_D1_SHOW:,}개" if len(us_no_d1) > US_D1_SHOW else "")
    urec = us_own_rec(data)
    if "usSrc" not in data:
        # usSrc 가 없는 파일 (2026-11-20 전 발행본): 예전 규칙 그대로
        rep.add("미국 d1 채움 (미국 기준일 봉)", us_cov >= US_D1_COVER,
                f"{floor_1(us_cov)}% ({len(us) - len(us_no_d1):,} / {len(us):,})" + (f" · 빠짐: {shown}" if us_no_d1 else ""),
                f"≥ {US_D1_COVER:g}% (미국 기준일 {data.get('usPxDate')} 봉이 있는 종목 · 하나라도 빠지면 경고)",
                warn=bool(us_no_d1))    # v19.1c (Jack, 2026-11-07): 1~15종목만 빠져도 아침 점검이 알림으로 읽어요
    else:
        # 2026-11-20 (Jack, verbatim: "Also: US stocks carry like Korean ones. A US stock with no close from Yahoo carries its last confirmed
        # close with its own date and the same line. Block only if many are missing (set the number from history), so a Yahoo gap never
        # stops the Korean data again."): 마지막 확인 종가로 맞게 실린 종목(us_own · 그 날짜와 Jack 의 줄)은 빠진 것으로 세지 않아요 (몇 개든
        # 경고). 실패는 기준일 봉이 없는데 마지막 확인 종가로 싣지 못한 종목(야후의 마지막 봉을 자기 날짜로 · 깨진 기록)이 US_NO_CLOSE_MAX
        # 를 넘을 때 (N = max(5, 3 × 최근 발행본의 가장 큰 수) = 5 · 기록이 깨졌으면 모두 빠진 것으로 세요)
        carried = [t for t in us_no_d1 if t in us_own]
        missing = [t for t in us_no_d1 if t not in us_own]
        same = list((urec or {}).get("same") or [])
        mshown = ", ".join(missing[:US_D1_SHOW]) + (f" 외 {len(missing) - US_D1_SHOW:,}개" if len(missing) > US_D1_SHOW else "")
        cshown = ", ".join(carried[:US_D1_SHOW]) + (f" 외 {len(carried) - US_D1_SHOW:,}개" if len(carried) > US_D1_SHOW else "")
        rep.add("미국 d1 채움 (미국 기준일 봉)", len(missing) <= US_NO_CLOSE_MAX,
                f"{floor_1(us_cov)}% ({len(us) - len(us_no_d1):,} / {len(us):,})"
                + (f" · 마지막 확인 종가 {len(carried):,}: {cshown}" if carried else "")
                + (f" · 같은 날 지난 발행본 종가 그대로 {len(same):,}" if same else "")
                + (f" · 빠짐 {len(missing):,}: {mshown}" if missing else "")
                + (" · usSrc.own 모양이 잘못됨" if urec is None else ""),
                f"미국 기준일 {data.get('usPxDate')} 봉이 없는데 마지막 확인 종가로 싣지 못한 종목 ≤ {US_NO_CLOSE_MAX} "
                "(Jack 2026-11-20 · 마지막 확인 종가는 몇 개든 경고 · 하나라도 있으면 경고)",
                warn=bool(us_no_d1 or same or urec is None))
        if carried:
            rep.detail(f"미국 마지막 확인 종가로 실은 종목 (미국 기준일 {data.get('usPxDate')} 종가가 야후에 없음)",
                       [f"{t}({(usby.get(t) or {}).get('pxd')})" for t in carried])
        if missing:
            rep.detail(f"미국 d1 없는 종목 (마지막 확인 종가가 아님 · 마지막 봉이 미국 기준일 {data.get('usPxDate')} 이 아님)", missing)
    if us_no_d1 and "usSrc" not in data:
        rep.detail(f"미국 d1 없는 종목 (마지막 봉이 미국 기준일 {data.get('usPxDate')} 이 아님)", us_no_d1)

    # 8. val20: 20거래일 평균 거래대금 (억원)
    miss = [t for t in must_kr if not ((num((by.get(t) or {}).get("val20")) or 0) > 0)]
    rep.add("필수 종목 val20", not miss, "모두 있음" if not miss else "없음: " + ",".join(miss), ",".join(must_kr))
    rep.pct("국내 val20 채움", coverage(kr, "val20"), VAL20_COVER)
    neg = sum(1 for s in kr if num(s.get("val20")) is not None and num(s["val20"]) < 0)
    rep.add("국내 val20 ≥ 0", neg == 0, f"음수 {neg}", "0")

    # 9. etf: 모든 종목에 참/거짓, 정해 둔 종목은 맞게
    stocks = data.get("stocks", [])
    nobool = [s.get("t") for s in stocks if not isinstance(s.get("etf"), bool)]
    rep.add("etf 표시 (모든 종목)", not nobool, "모두 있음" if not nobool else f"없음 {len(nobool)} (예: {nobool[0]})", "참/거짓")
    wrong = [t for t in US_ETF_SET if t in by and by[t].get("etf") is not True]
    wrong += [t for t in US_COMPANY_SET | set(MUST) if t in by and by[t].get("etf") is not False]
    wrong += [t for t in set(FUNDS) | KR_FUND_SET if t in by and by[t].get("etf") is not True]
    wrong += [t for t in KR_COMPANY_SET if t in by and by[t].get("etf") is not False]
    wrong += [s["t"] for s in stocks if s.get("cls") == "bond" and s.get("etf") is not True]
    rep.add("etf 표시가 맞음", not wrong, "맞음" if not wrong else "틀림: " + ",".join(sorted(wrong)[:8]),
            "미국 ETF·국내 ETF·채권·금현물 참, 회사 주식 거짓")

    # 6. 주당 배당금: 0 = 배당 없음 (빈 칸 = 모름). 음수는 없어야 해요
    negd = [s["t"] for s in kr if num(s.get("dps")) is not None and num(s["dps"]) < 0]
    zero = sum(1 for s in kr if num(s.get("dps")) == 0)
    rep.add("국내 주당 배당금 ≥ 0", not negd, f"음수 {len(negd)} · 0원(배당 없음) {zero:,}", "음수 0")
    s5 = by.get("005930") or {}
    rep.add("005930 주당 배당금", (num(s5.get("dps")) or 0) > 0, s5.get("dps"), "> 0")
    # '-' 를 0 으로 읽는 새 해석의 맞춤 검사: 같은 DART 표에서 나온 주당 배당금과 배당수익률은 함께 0 이거나 함께 0 보다 커야 해요
    both = [s for s in kr if num(s.get("dps")) is not None and num(s.get("dy")) is not None]
    odd = [s["t"] for s in both if (num(s["dps"]) == 0) != (num(s["dy"]) == 0)]
    share = 100.0 * len(odd) / len(kr) if kr else 0.0
    rep.add("주당 배당금·배당수익률 맞음", share <= DPS_DY_ODD_MAX, f"어긋남 {len(odd)} ({share:.1f}%)" + (f" 예: {odd[0]}" if odd else ""),
            f"≤ {DPS_DY_ODD_MAX}% (0 원인데 수익률 > 0, 또는 반대)")

    # 7. fy: 연간 DART 수치(op·debt·roe·dps3)가 나온 사업보고서 연도
    y = (px or today).year
    has_annual = [c for c in comps if num(c.get("debt")) is not None or any(num(v) is not None for v in (c.get("op") or []))]
    nofy = [c["t"] for c in has_annual if not isinstance(c.get("fy"), int)]
    rep.add("연간 수치에 사업보고서 연도(fy)", not nofy, f"없음 {len(nofy)}" + (f" (예: {nofy[0]})" if nofy else ""),
            f"연간 수치가 있는 {len(has_annual):,}곳 모두")
    badfy = sorted({c.get("fy") for c in comps if isinstance(c.get("fy"), int) and not (y - 2 <= c["fy"] <= y - 1)})
    rep.add("사업보고서 연도 범위", not badfy, "모두 범위 안" if not badfy else f"범위 밖: {badfy[:5]}", f"{y - 2}–{y - 1}")
    cby = {c.get("t"): c for c in comps}
    miss = [t for t in must_kr if not isinstance((cby.get(t) or {}).get("fy"), int)]
    rep.add("필수 종목 fy", not miss, "모두 있음" if not miss else "없음: " + ",".join(miss), ",".join(must_kr))

    # 5. idxHist: KOSPI·S&P500 일별 종가 3년, 각자 기준일까지
    ih = macro.get("idxHist") or {}
    probs = []
    for name, want in (("KOSPI", day(data.get("ksDate"))), ("SP500", day(data.get("usPxDate")))):
        h = ih.get(name) or {}
        rows = h.get("rows") or []
        ds = [day(r[0]) if isinstance(r, list) and len(r) == 2 else None for r in rows]
        vs = [num(r[1]) if isinstance(r, list) and len(r) == 2 else None for r in rows]
        if len(rows) < IDX_MIN_ROWS:
            probs.append(f"{name} {len(rows)}일")
            continue
        if None in ds or any(v is None or v <= 0 for v in vs):
            probs.append(f"{name} 잘못된 줄")
            continue
        if ds != sorted(set(ds)):
            probs.append(f"{name} 날짜 순서·중복")
        if day(h.get("asOf")) != ds[-1] or ds[-1] != want:
            probs.append(f"{name} 마지막 {ds[-1]} (asOf {h.get('asOf')}, 기준일 {want})")
        if (ds[-1] - ds[0]).days < IDX_MIN_DAYS:
            probs.append(f"{name} {ds[0]}부터라 3년이 안 돼요")
    rep.add("지수 이력 (KOSPI·S&P500 3년)", not probs, "정상" if not probs else " · ".join(probs)[:90],
            f"각 {IDX_MIN_ROWS}일 이상 · 마지막 = 각자 기준일")

    # PR 2. 업종 그룹: 필수 종목이 맞는 그룹, 거래 활발한 국내 종목은 거의 다 그룹, 그룹마다 5명 이상, 이름 일관
    wrong = [f"{t}={(by.get(t) or {}).get('ind')}" for t, g in IND_MUST.items() if (by.get(t) or {}).get("ind") != g]
    rep.add("업종 그룹 필수 종목", not wrong, "맞음" if not wrong else "틀림: " + ",".join(wrong),
            "삼성전자·SK하이닉스 반도체 · 현대차·기아 자동차 · KB·하나 은행 · SK·LG 지주회사")
    liq = [s for s in kr if s.get("etf") is not True and (num(s.get("val20")) or 0) >= IND_LIQUID_VAL20]
    no = [s["t"] for s in liq if not s.get("ind")]
    share = 100.0 * len(no) / len(liq) if liq else 100.0
    rep.add("업종 그룹 없는 국내 종목 (거래 활발)", share <= IND_UNGROUPED_MAX, f"{share:.1f}% ({len(no)} / {len(liq):,})"
            + (f" 예: {','.join(no[:3])}" if no else ""), f"≤ {IND_UNGROUPED_MAX}% (val20 ≥ {IND_LIQUID_VAL20:g}억원)")
    size = {}
    names = {}
    for s in kr + us:
        g = s.get("ind")
        if g:
            if not (s["cls"] == "kr" and len(s["t"]) == 6 and s["t"][-1] != "0"):     # 우선주는 인원에 안 세요
                size[(s["cls"], g)] = size.get((s["cls"], g), 0) + 1
            names.setdefault(g, set()).add(s.get("indName") or "")
    finbad = [t for t in IND_NOT_FIN if (by.get(t) or {}).get("ind") in FIN_INDS]
    rep.add("지주회사가 금융 그룹이 아님", not finbad, "맞음" if not finbad else "금융으로 잘못: " + ",".join(finbad), "효성·HDC 는 금융 아님")
    usco = [s for s in us if s.get("etf") is not True]
    ucov = 100.0 * sum(1 for s in usco if s.get("ind")) / len(usco) if usco else 0.0
    rep.pct("미국 업종 그룹 채움", ucov, IND_US_COVER)
    small = sorted(f"{m}:{g}({n})" for (m, g), n in size.items() if n < IND_GROUP_MIN)
    rep.add("업종 그룹 인원 (시장마다)", bool(size) and not small, f"{len(size)}개 그룹" if not small else "적음: " + ",".join(small[:5]),
            f"≥ {IND_GROUP_MIN}종목")
    badn = sorted(g for g, ns in names.items() if len(ns) != 1 or "" in ns or not re.fullmatch(r"[a-z_]+", g))
    etfg = [s["t"] for s in data.get("stocks", []) if s.get("ind") and (s.get("etf") is True or s.get("cls") not in ("kr", "us"))]
    rep.add("업종 그룹 이름·형식", not badn and not etfg, "정상" if not (badn or etfg) else f"이름 {badn[:3]} · ETF에 그룹 {etfg[:3]}",
            "그룹마다 한 이름 · ETF·채권은 그룹 없음")

    # 3. 52주 최고·최저 · d1: 필수 종목을 야후 종가로 따로 계산한 값과 비교 (야후 마지막 날 = pxDate 인 종목만)
    if hilo is None or not hilo:
        rep.add("필수 종목 52주 최고·최저 (야후)", True, "야후를 받지 못해 확인 못 함", f"{HILO_TOL}% 안 (못 받으면 경고)", warn=True)
        rep.add("필수 종목 d1 (야후)", True, "야후를 받지 못해 확인 못 함", f"{D1_YAHOO_TOL}%p 안 (못 받으면 경고)", warn=True)
    else:
        worst, off, held = 0.0, [], []
        # Jack 2026-11-14 저녁: 과거 주가 기록 오류로 52주를 맞게 비운(px_bad_must) 필수 종목이 하나뿐이면 그 종목은 경고로 넘겨요 (이름과 함께).
        # 둘 이상이면 넘기지 않아요 (예전처럼 '없음' → 실패). 표시 없이 비었으면 예전처럼 실패.
        pm = px_bad_must(cur.get("data") or {}, comps)
        for t, y in hilo.items():
            s = by.get(t) or {}
            h, lo = num(s.get("hi")), num(s.get("lo"))
            if h is None or lo is None:
                if t in pm and {"hi", "lo"} <= pm[t] and len(pm) < PX_BAD_MUST_FAIL:
                    held.append(f"{t} 과거 주가 기록 오류로 비움 (pxBad {s.get('pxBad')})")
                    continue
                worst = 999.0
                off.append(f"{t} 없음")
                continue
            dmax = max(abs(h / y["hi"] - 1) * 100, abs(lo / y["lo"] - 1) * 100)
            worst = max(worst, dmax)
            if dmax > HILO_TOL:
                off.append(f"{t} {h:,.0f}/{lo:,.0f} vs {y['hi']:,.0f}/{y['lo']:,.0f}")
        rep.add("필수 종목 52주 최고·최저 (야후)", worst <= HILO_FAIL,
                f"{len(hilo)}종목 · 최대 {worst:.2f}%" + (f" · {' · '.join(off)[:70]}" if off else "") + (f" · {' · '.join(held)}" if held else ""),
                f"{HILO_TOL}% 안 (1–{HILO_FAIL:g}% 경고, 넘으면 실패 · 과거 주가 기록 오류로 맞게 비운 필수 종목은 하나만 경고, "
                f"{PX_BAD_MUST_FAIL}곳 이상이면 실패 — Jack 2026-11-14)", warn=bool(off) or bool(held) or len(hilo) < len(must_kr))
        bad1 = [f"{t} {num((by.get(t) or {}).get('d1'))} vs {y['d1']:.2f}" for t, y in hilo.items()
                if num((by.get(t) or {}).get("d1")) is None or abs(num(by[t]["d1"]) - y["d1"]) > D1_YAHOO_TOL]
        rep.add("필수 종목 d1 (야후)", not bad1, f"{len(hilo)}종목 맞음" if not bad1 else " · ".join(bad1)[:90],
                f"{D1_YAHOO_TOL}%p 안 (이틀치 변화를 잡아요)", warn=len(hilo) < len(must_kr))


def check_v1752(rep, data, kr, us, pdata):
    # 미국 시가총액: ETF 가 아닌 미국 종목은 거의 모두 시가총액이 있어야 해요 (우선주·예탁증서는 파이프라인이 빼요)
    usco = [s for s in us if s.get("etf") is not True]
    have = sum(1 for s in usco if (num(s.get("cap")) or 0) > 0)
    share = 100.0 * have / len(usco) if usco else 0.0
    rep.pct("미국 시가총액 채움 (ETF 빼고)", share, US_CAP_COVER)
    # 우선주로 뺀 수: 진짜 우선주는 몇 개뿐이에요. 많으면 이름·티커 규칙이 진짜 회사를 잡은 거예요 (기록이 없어도 실패)
    lo = data.get("usLeftOut")
    pref = lo.get("preferred") if isinstance(lo, dict) else None
    ok = isinstance(pref, list) and all(isinstance(t, str) for t in pref) and len(pref) <= US_PREF_DROP_MAX
    bad = lo.get("badBar") if isinstance(lo, dict) else None
    if isinstance(bad, list) and bad:      # v19.1c: 기준일 봉은 있는데 그 전 봉이 깨져(0·무한) 뺀 종목 — 경고로 이름을 남겨요
        rep.add("미국 깨진 봉으로 뺀 종목", True, f"{len(bad)}개: {', '.join(map(str, bad[:US_D1_SHOW]))}"
                + (f" 외 {len(bad) - US_D1_SHOW}개" if len(bad) > US_D1_SHOW else ""), "없어야 함 (있으면 경고)", warn=True)
    rep.add("미국 우선주·예탁증서로 뺀 종목 수", ok,
            (f"{len(pref)}개" + (f": {', '.join(map(str, pref[:6]))}{'…' if len(pref) > 6 else ''}" if pref else ""))
            if isinstance(pref, list) else "기록 없음 (data.json usLeftOut)",
            f"≤ {US_PREF_DROP_MAX}개 (많으면 이름·티커 규칙이 진짜 회사를 잡은 것)")
    # 국내 배당: 주당 배당금·배당수익률 채움이 직전 발행본보다 크게 줄면 실패 (0 = 배당 없음도 채움으로 세요)
    if pdata:
        pkr = kr_stocks(pdata)
        for k in DIV_COVER_KEYS:
            v, pv = coverage(kr, k), coverage(pkr, k)
            rep.add(f"국내 {k} 채움 변화", v >= pv - DIV_COVER_DROP, f"{pv:.1f} → {v:.1f}", f"{DIV_COVER_DROP:g}점 넘게 줄면 실패")


def check_us_fcur(rep, us):
    """Jack, 2026-11-12: 재무제표 통화가 달러가 아닌 미국 회사(fcur)는 PER · PBR · 배당수익률 · 가치 점수가 비어 있어야 해요. fcur 는 세 글자
    대문자이고 USD 가 아니어야 해요 (XXX = 파이프라인이 읽지 못한 통화 · 그래도 비워요). 값: fcur 회사 수 (통화별) · 남은 칸."""
    bad, by = [], collections.Counter()
    for s in us:
        if "fcur" not in s:
            continue
        t, fc = s.get("t"), s.get("fcur")
        if not (isinstance(fc, str) and re.fullmatch(r"[A-Z]{3}", fc) and fc != "USD"):
            bad.append(f"{t}.fcur {fc!r}")
            continue
        by[fc] += 1
        bad += [f"{t}.{k}" for k in US_FCUR_BLANK if s.get(k) is not None and not (k == "dy" and US_FCUR_KEEP_ZERO_DY and s.get(k) == 0)]
    n = sum(by.values())
    rep.add("미국 재무제표 통화가 달러가 아닌 회사: PER·PBR·배당수익률·가치 점수 빈 칸", not bad,
            f"{n}곳" + (f" ({' · '.join(f'{c} {k}' for c, k in sorted(by.items(), key=lambda kv: (-kv[1], kv[0])))})" if by else "")
            + f" · 남은 칸 {len(bad)}" + (f" (예: {', '.join(bad[:4])})" if bad else ""),
            "fcur 가 있는 회사는 per·pbr·dy·vz 없음 (0 도 안 됨" + (", 배당 0% 는 됨" if US_FCUR_KEEP_ZERO_DY else "") + ") · fcur 는 USD 가 아닌 세 글자")


def _tickers(ts):
    return ", ".join(map(str, ts[:US_FCUR_SHOW])) + (f" 외 {len(ts) - US_FCUR_SHOW}곳" if len(ts) > US_FCUR_SHOW else "")


def check_us_fcur_more(rep, data, us, pdata):
    """#114 리뷰 (더하기만): ① 재무제표 통화를 모르는 회사(data.json usFcurUnknown) — 경고만, 이름을 남겨요. ② 직전 발행본에서 fcur 가 있던
    미국 종목이 오늘도 목록에 있는데 fcur 가 없으면 (코디네이터 결정 2026-11-13 — 야후가 달러로 바뀌었다고 하면 발행을 막지 않아요):
      · 야후가 이제 달러 재무제표라고 함 (usFcurUnknown 이 있고 그 안에 없음 · 오늘 상세 정보가 붙음 = 이름이 티커가 아님) → 경고, 숫자가
        있든 없든 ('숫자를 확인하세요')
      · 오늘 통화 정보가 없음 (usFcurUnknown 안 · 그 칸이 없는 발행 · 상세 정보 없음) 인데 PER · PBR · 배당수익률이 있음 → 실패. 파이프라인은
        예전 통화를 그대로 쓰니(us_info_merge) 일어날 수 없는 일이라, 실패는 무언가 고장 났다는 뜻이에요
      · 통화 정보가 없고 숫자도 없음 → 경고"""
    unk = data.get("usFcurUnknown")
    if isinstance(unk, list):
        rep.add("미국 재무제표 통화를 모르는 회사 (경고만)", True, f"{len(unk)}곳" + (f": {_tickers(unk)}" if unk else ""),
                "없어야 함 (있으면 경고 · 비우지 않았어요)", warn=bool(unk))
        if unk:
            rep.detail("재무제표 통화를 모르는 미국 회사 (usFcurUnknown)", unk)
    else:
        rep.add("미국 재무제표 통화를 모르는 회사 (경고만)", True, "기록 없음 (이 칸 전 발행본)", "없어야 함 (있으면 경고)")
    # #114 리뷰 2: 야후 응답이 일부만 와 이름 · 업종 · 설명 · 재무제표 통화를 예전 값으로 채운 종목 (data.json usInfoPartial). 예전 값이 '미국 설명
    # 채움' 줄을 채워 주니, 나쁜 야후 날이 그 줄에 보이지 않아요 — 그래서 이 줄이 이름을 남겨요. 경고만 (다음 실행이 다시 물어요).
    part = data.get("usInfoPartial")
    if isinstance(part, list):
        n_us = len(us) or 1
        rep.add("미국 상세 정보가 일부만 온 종목 (예전 값으로 채움 · 경고만)", True,
                f"{len(part)}곳 ({100.0 * len(part) / n_us:.1f}%)" + (f": {_tickers(part)}" if part else ""),
                "없어야 함 (있으면 경고 · 다음 실행이 다시 물어요)", warn=bool(part))
        if part:
            rep.detail("야후 응답이 일부만 와 예전 설명 칸을 쓴 미국 종목 (usInfoPartial)", part)
    else:
        rep.add("미국 상세 정보가 일부만 온 종목 (예전 값으로 채움 · 경고만)", True, "기록 없음 (이 칸 전 발행본)", "없어야 함 (있으면 경고)")
    # Jack, 2026-11-13: PBR 이 0.00 으로 반올림돼 비운 종목(pbrZero) — PBR · 가치 점수가 비어 있어야 해요 (true 말고 다른 값도 실패)
    pz = [s for s in us if "pbrZero" in s]
    badz = [f"{s.get('t')}.pbrZero {s.get('pbrZero')!r}" for s in pz if s.get("pbrZero") is not True]
    badz += [f"{s.get('t')}.{k}" for s in pz if s.get("pbrZero") is True for k in ("pbr", "vz") if s.get(k) is not None]
    rep.add("미국 PBR 0 근처라 비운 종목: PBR·가치 점수 빈 칸", not badz,
            f"{len(pz)}곳" + (f": {_tickers([s.get('t') for s in pz])}" if pz else "") + f" · 남은 칸 {len(badz)}" + (f" (예: {', '.join(badz[:4])})" if badz else ""),
            "pbrZero 종목은 pbr · vz 없음")
    if not pdata:
        return
    had = {s.get("t") for s in us_stocks(pdata) if s.get("fcur")}
    lost = [s for s in us if s.get("t") in had and not s.get("fcur")]
    unk_set = set(unk) if isinstance(unk, list) else None
    has_num = lambda s: any(s.get(k) is not None for k in US_FCUR_BLANK[:3])          # noqa: E731
    said_usd = lambda s: unk_set is not None and s.get("t") not in unk_set and bool(s.get("nk")) and s.get("nk") != s.get("t")   # noqa: E731
    usd = [s["t"] for s in lost if said_usd(s)]
    broken = [s["t"] for s in lost if not said_usd(s) and has_num(s)]
    quiet = [s["t"] for s in lost if not said_usd(s) and not has_num(s)]
    parts = [f"통화 정보 없이 숫자 있음 {len(broken)}곳: {_tickers(broken)}" if broken else None,
             f"달러로 바뀜 {len(usd)}곳 (야후가 이제 달러 재무제표라고 함 — 숫자를 확인하세요): {_tickers(usd)}" if usd else None,
             f"통화 정보 · 숫자 없음 {len(quiet)}곳: {_tickers(quiet)}" if quiet else None]
    rep.add("어제 재무제표 통화가 있던 미국 종목이 오늘 통화 없음", not broken,
            f"{len(lost)}곳" + "".join(f" · {x}" for x in parts if x),
            "없어야 함 (통화 정보 없이 PER·PBR·배당이 다시 나가면 실패 · 야후가 달러라고 하거나 숫자가 없으면 경고)",
            warn=bool(lost) and not broken)
    for title, ts in (("어제 fcur 가 있었는데 오늘 통화 정보 없이 PER·PBR·배당이 나간 미국 종목 (고장)", broken),
                      ("어제 fcur 가 있었는데 야후가 이제 달러 재무제표라고 하는 미국 종목 (숫자를 확인하세요)", usd),
                      ("어제 fcur 가 있었는데 오늘 통화 정보도 숫자도 없는 미국 종목", quiet)):
        if ts:
            rep.detail(title, ts)


def check_us_extra(rep, data, us, mode):
    """2026-11-14 (Jack, 2026-11-13 "Missing US stocks" · 더하기만): 손으로 더한 미국 종목(US_EXTRA_SET = fetch_data.EXTRA_US)은 오늘 목록에 있거나
    (가격 > 0) data.json usExtraMissing 에 빠진 이유가 있어야 해요 — 조용히 사라지지 않게. 이유가 있으면 경고 (이름 · 이유).
    2026-11-21 (Jack: "Yes, warn." · "one stock missing from a source never holds the publish" · BF-B 줄(#149)과 같은 꼴): 목록에 행이 없고
    usExtraMissing 에도 없는 종목은 경고 (이름 · '이유 없음') — 빠진 종목은 틀린 숫자를 보이지 않아요. 발행 실패는 그대로 셋:
    ① 그런 종목이 US_EXTRA_QUIET_MAX(5)곳 넘게 (두 목록이 어긋났거나 기록이 깨짐 · 한 종목이 빠진 것이 아니에요),
    ② 목록에 행이 있는데 가격이 없고 (0 · 빈 칸 · 숫자 아님) 이유도 없음 (앱이 그 종목을 가격 없이 보여요 · 파이프라인은 목록에 있는 종목에 이유를
       적지 않아요) — data.json stocks 에 그 티커의 행이 있는데 미국 종목 행이 아닌 것 (cls 가 us 가 아님 · fund) 도 같아요 (빠진 것이 아니라 틀린
       행이에요), ③ usExtraMissing 에 그 종목이 있는데 이유가 글이 아님 (null · 빈 글 · 숫자: 파이프라인은 늘 글을 적어요 — 기록이 깨짐).
    사이트 점검(live)은 실패 대신 경고예요: 종목을 더한 코드가 그 종목이 아직 없는 어제 파일 그대로 배포될 때 막지 않게. usExtraMissing 이 없는
    파일(이 칸 전 발행본)은 발행 때 경고 · 점검 때 건너뛰어요 (그대로)."""
    name = "손으로 더한 미국 종목 (EXTRA_US): 목록에 있거나 빠진 이유"
    th = (f"모두 있어야 함 (빠지면 이유가 있든 없든 경고 · 실패는 이유 없이 빠진 종목 > {US_EXTRA_QUIET_MAX} · 목록에 있는데 가격이 없거나 "
          "미국 종목 행이 아님 · 이유가 글이 아님, 사이트 점검은 경고)")
    rec = data.get("usExtraMissing")
    have = {s.get("t") for s in us if (num(s.get("price")) or 0) > 0}
    tickers = {s.get("t") for s in us}
    rows_t = tickers | {s.get("t") for s in data.get("stocks") or [] if isinstance(s, dict)}     # 미국 행이 아닌 행도 (cls · fund)
    gone = sorted(t for t in US_EXTRA_SET if t not in have)
    if not isinstance(rec, dict):
        if mode == "live":
            rep.skip(name, "기록 없음 (data.json usExtraMissing 이 없는 발행본)")
        else:
            rep.add(name, True, f"기록 없음 (data.json usExtraMissing) · 오늘 없는 종목 {len(gone)}" + (f": {_tickers(gone)}" if gone else ""),
                    th, warn=True)
        return
    why = {t: rec.get(t) for t in gone}
    told = [t for t in gone if isinstance(why[t], str) and why[t].strip()]
    silent = [t for t in gone if t not in told]
    no_px_row = [t for t in silent if t in tickers]                     # ② 목록에 행이 있는데 가격이 없고 이유도 없음 → 발행 실패 (그대로)
    not_us_row = [t for t in silent if t in rows_t and t not in tickers]   # ② 그 티커의 행이 미국 종목 행이 아님 → 발행 실패 (그대로)
    bad_why = [t for t in silent if t not in rows_t and t in rec]       # ③ 기록에 있는데 이유가 글이 아님 (기록이 깨짐) → 발행 실패 (그대로)
    quiet = [t for t in silent if t not in rows_t and t not in rec]     # 목록에도 기록에도 없음 → 경고 (Jack 2026-11-21) · ① 5곳 넘으면 발행 실패
    many = len(quiet) > US_EXTRA_QUIET_MAX
    odd = sorted(str(t) for t in rec if t not in US_EXTRA_SET)          # 관문 목록에 없는 티커 (두 목록이 어긋남)
    parts = ([f"목록에 있는데 가격이 없음 {len(no_px_row)}: {_tickers(no_px_row)}"] if no_px_row else []) \
        + ([f"행이 미국 종목 행이 아님 {len(not_us_row)}: {_tickers(not_us_row)}"] if not_us_row else []) \
        + ([f"이유가 글이 아님 {len(bad_why)}: {_tickers(bad_why)}"] if bad_why else []) \
        + ([f"이유 없이 빠짐 {len(quiet)}" + (f" (> {US_EXTRA_QUIET_MAX})" if many else "") + f": {_tickers(quiet)}"] if quiet else []) \
        + ([f"빠짐 {len(told)}: " + " · ".join(f"{t} ({why[t]})" for t in told[:US_FCUR_SHOW])
            + (f" 외 {len(told) - US_FCUR_SHOW}곳" if len(told) > US_FCUR_SHOW else "")] if told else []) \
        + ([f"관문 목록에 없는 티커 {len(odd)}: {_tickers(odd)}"] if odd else [])
    rep.add(name, not (no_px_row or not_us_row or bad_why or many) or mode == "live",
            f"{len(US_EXTRA_SET) - len(gone)} / {len(US_EXTRA_SET)} 있음" + "".join(f" · {x}" for x in parts), th, warn=bool(gone or odd))
    if gone:
        rep.detail("손으로 더한 미국 종목 중 오늘 없는 종목 (usExtraMissing)",
                   [f"{t}: " + (why[t] if t in told else '목록에 있는데 가격이 없음 · 이유 없음' if t in no_px_row
                                else '행이 미국 종목 행이 아님 · 이유 없음' if t in not_us_row
                                else '이유가 글이 아님' if t in bad_why else '이유 없음') for t in gone])


def own_drop_get(data, key):
    """data.json ownDrop[key] (Jack 의 상시 규칙 2026-11-19) → None (기록 없음: 이 규칙 전 파일 — 그 줄은 예전 규칙 그대로) · False (기록 모양이
    틀림: 예전 규칙 그대로에 경고를 더해요) · {"n": 파이프라인이 빼거나 비운 행 수, "rows": [[열쇠, 이유]] 앞 OWN_DROP_SHOW 개}."""
    if not isinstance(data, dict) or "ownDrop" not in data:
        return None
    od = data["ownDrop"]
    if not isinstance(od, dict):                       # 리뷰 1차: 칸은 있는데 모양이 틀림 — 조용히 넘기지 않고 예전 규칙 + 경고
        return False
    if key not in od:
        return None
    r = od[key]
    n = r.get("n") if isinstance(r, dict) else None
    rows = r.get("rows") if isinstance(r, dict) else None
    ok = (isinstance(r, dict) and set(r) == {"n", "rows"} and isinstance(n, int) and not isinstance(n, bool) and n >= 0
          and isinstance(rows, list) and len(rows) == min(n, OWN_DROP_SHOW)
          and all(isinstance(x, list) and len(x) == 2 and all(isinstance(v, str) for v in x) for x in rows))
    return r if ok else False


def own_drop_rec(rows):
    """나쁜 행 [(열쇠, 이유, …)] → data.json ownDrop[열쇠] 의 값 {"n", "rows" (앞 OWN_DROP_SHOW 개 · [열쇠, 이유])}. (순수 함수 · 파이프라인이 써요)"""
    return {"n": len(rows), "rows": [[str(r[0]), str(r[1])] for r in rows[:OWN_DROP_SHOW]]}


def own_drop_text(rows, n=None):
    """[(열쇠, 이유, …)] → '열쇠 (이유) · …' 앞 OWN_DROP_SHOW 개 (+ ' 외 N건')."""
    n = len(rows) if n is None else n
    return " · ".join(f"{r[0]} ({r[1]})" for r in rows[:OWN_DROP_SHOW]) + (f" 외 {n - OWN_DROP_SHOW}건" if n > OWN_DROP_SHOW else "")


def _us_sym_parse(rec):
    """usListSym 기록 → 읽은 칸과 모양 문제 (check_us_share_class · us_class_bad_rows 가 같은 규칙을 써요 · 한 곳).
    unsure: spTickers 를 믿을 수 없는 모양 (그날 S&P 500 목록에서 온 티커인지 알 수 없어요 — #139 리뷰 2차 2 의 '검사가 조용히 꺼짐').
    mapped: 예전 규칙 그대로 (한 줄이라도 틀리면 비워요 · 'mapped 모양'). 상시 규칙 쪽은 줄마다 읽어요 (리뷰 1차 M1): mapped_ok = 모양이 맞는 줄 ·
    wrong_all = 그중 관문 표와 다르게 바꾼 줄 (그 행은 빼요) · map_blind = 모양이 틀린 줄이 하나라도 있음 (리뷰 2차: mapped 에는 점이 지워진 꼴을
    바꾼 줄만 들어가요 — 틀린 줄이 있으면 그 꼴이 어디로 바뀌었는지 관문 표와 맞춰 볼 수 없어 틀린 회사가 실렸는지도 몰라요 → 발행 실패 · 사이트
    점검 경고 · 예전 'mapped 모양' 과 같은 엄격함)."""
    row3 = lambda x: isinstance(x, list) and len(x) == 3 and all(isinstance(v, str) for v in x)   # noqa: E731
    strs = lambda x: isinstance(x, list) and all(isinstance(t, str) for t in x)                    # noqa: E731
    mapped, unmapped, sp_t = rec.get("mapped"), rec.get("unmapped"), rec.get("spTickers")
    sp_gone, no_px, sp_err = rec.get("spGone"), rec.get("noPx"), rec.get("spErr")
    bad, unsure = [], False
    if not isinstance(rec.get("read"), bool):
        bad.append("read 가 참 · 거짓이 아님")
    mapped_ok = [x for x in mapped if row3(x)] if isinstance(mapped, list) else []
    map_blind = not (isinstance(mapped, list) and len(mapped_ok) == len(mapped))
    if not (isinstance(mapped, list) and all(row3(x) for x in mapped)):
        bad.append("mapped 모양")
        mapped = []
    if not (isinstance(unmapped, list) and all(row3(x) for x in unmapped)):
        bad.append("unmapped 모양")
        unmapped = []
    if not (isinstance(rec.get("missing"), dict) and all(isinstance(t, str) for t in rec["missing"])):
        bad.append("missing 모양")
    if sp_t is not None and not strs(sp_t):
        bad.append("spTickers 모양")
        sp_t, unsure = [], True
    if sp_gone is not None and not (isinstance(sp_gone, dict) and all(isinstance(t, str) and isinstance(w, str) for t, w in sp_gone.items())):
        bad.append("spGone 모양")
        sp_gone = {}
    for key, val in (("noPx", no_px), ("spErr", sp_err)):
        if val is not None and not strs(val):
            bad.append(f"{key} 모양")
        elif (val is None) != (sp_gone is None) or (val and not set(val) <= set(sp_gone or {})):
            bad.append(f"{key} 가 spGone 안에 있지 않음")
    no_px = no_px if strs(no_px) else []
    sp_err = sp_err if strs(sp_err) else []
    if no_px and sp_err and set(no_px) & set(sp_err):
        bad.append("noPx 와 spErr 가 겹침")
    if sp_gone is not None and not strs(rec.get("spTickers")):          # 리뷰 2차 2: spTickers 가 없으면 아래 실패 검사가 조용히 꺼져요
        bad.append("spGone 이 있는데 spTickers 가 목록이 아님")
        unsure = True
    elif sp_gone and not set(sp_gone) <= set(sp_t or []):
        bad.append("spGone 이 spTickers 안에 있지 않음")
        unsure = True
    wrong = [(a, b) for _s, a, b in mapped if a in US_CLASS_JOINED_SET and b != US_CLASS_JOINED_SET[a]]
    wrong_all = [(a, b) for _s, a, b in mapped_ok if a in US_CLASS_JOINED_SET and b != US_CLASS_JOINED_SET[a]]
    return {"mapped": mapped, "unmapped": unmapped, "sp_t": sp_t, "sp_gone": sp_gone, "no_px": no_px, "sp_err": sp_err, "bad": bad,
            "unsure": unsure, "wrong": wrong, "mapped_ok": mapped_ok, "wrong_all": wrong_all, "map_blind": map_blind}


US_CLASS_WHY_SP = "S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 실림 (야후가 이 꼴에 답한 다른 증권일 수 있어요)"
US_CLASS_WHY_UNSURE = "기록(spTickers) 모양이 틀려 S&P 500 목록에서 왔는지 확인할 수 없는 점이 지워진 꼴"
US_CLASS_BLIND = "mapped 에 모양이 틀린 줄이 있어 점이 지워진 꼴의 바꾸기를 관문 표와 맞춰 볼 수 없음 (발행 실패)"


def us_class_bad_rows(rec, us):
    """Jack 의 상시 규칙 (2026-11-19) · #139 의 우리 처리 검사: 발행 목록에서 빼야 할 미국 행 → (행 [(티커, 이유, 종류)], 기록 문제 [글]).
    파이프라인(fetch_data.own_drop_us_class)과 관문(check_us_share_class)이 같은 함수를 써요. (순수 함수)
    종류 sp — 점이 지워진 꼴(BRKB · BFB)이 그날 S&P 500 목록(spTickers)에 그대로 있는데 그 티커로 실림: 야후는 그 꼴의 티커가 없으니 실렸다면
              야후가 다른 증권으로 답한 것 (그 행의 가격 · 시가총액이 다른 회사의 숫자). 다른 출처(나스닥)의 같은 글자는 다른 회사일 수 있어 빼지 않아요.
    종류 unsure — 같은 꼴이 실렸는데 spTickers 모양이 틀려 출처를 알 수 없음 (틀린 숫자일 수 있어 빼요 · 기록이 깨진 날만).
    종류 wrong — 파이프라인이 점이 지워진 꼴을 관문 표(US_CLASS_JOINED_SET)와 다른 티커로 바꿨고 그 티커가 실림 (S&P 목록의 회사가 아닌 증권이
              S&P 500 회사로 들어와 외국 회사 검사(#133)를 건너뛸 수 있어요). mapped 는 줄마다 읽어요 (틀린 줄 하나가 이 검사를 끄지 않게 · 리뷰 1차
              M1). 표의 맞는 티커(BRK-B · BF-B)와 손으로 더한 종목(US_EXTRA_SET · #126: 손 목록이 넣은 종목이라 그 행은 그 티커의 야후 숫자예요)은
              빼지 않아요 (기록 문제로 경고만).
    기록 문제에는 US_CLASS_BLIND 가 들 수 있어요: mapped 에 모양이 틀린 줄 → 관문은 발행 실패 (사이트 점검 경고 · 맞는 줄의 다르게 바꾼 행은 그래도 빼요).
    기록이 없으면 ([], []) — 출처를 알 수 없어 빼지 않아요 (예전 규칙: 이름만 · 경고)."""
    if not isinstance(rec, dict):
        return [], []
    p = _us_sym_parse(rec)
    tickers = {s.get("t") for s in us if isinstance(s, dict)}
    sp_set = set(p["sp_t"] or [])
    rows = []
    for t in sorted(k for k in US_CLASS_JOINED_SET if k in tickers):
        if t in sp_set:
            rows.append((t, US_CLASS_WHY_SP, "sp"))
        elif p["unsure"]:
            rows.append((t, US_CLASS_WHY_UNSURE, "unsure"))
    good = set(US_CLASS_JOINED_SET.values()) | US_EXTRA_SET
    for a, b in p["wrong_all"]:
        if b in tickers and b not in good and b not in {r[0] for r in rows}:
            rows.append((b, f"관문 표와 다르게 바꾼 티커 {a} → {b} (관문 표 {US_CLASS_JOINED_SET[a]})", "wrong"))
    probs = ([f"관문 표와 다르게 바꿈: {' · '.join(f'{a} → {b} (관문 표 {US_CLASS_JOINED_SET[a]})' for a, b in p['wrong_all'])}"]
             if p["wrong_all"] else []) \
        + ([f"기록 모양이 틀림: {' · '.join(p['bad'])}"] if p["bad"] else []) + ([US_CLASS_BLIND] if p["map_blind"] else [])
    return rows, probs


def check_us_share_class(rep, data, us, mode):
    """2026-11-15 (Jack: "fix Brown-Forman B, then check every share-class ticker in the S&P 500 and NASDAQ sources" · 더하기만). 두 줄:
    ① '주식 종류 티커로 들어온 미국 종목': 이 바꾸기로 들어온 종목(US_CLASS_SET = fetch_data.US_CLASS_ADDED)은 오늘 목록에 있어야 해요 (가격 > 0).
       Jack (2026-11-20, verbatim): "Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish."
       그래서 목록에 그 종목의 행이 없으면 — data.json usListSym.missing 에 이유가 있든 없든 — 경고로 이름과 이유(없으면 '이유 없이 빠짐')를
       적어요 (빠진 종목은 틀린 숫자를 보이지 않아요). 실패는 하나뿐: 그 종목의 행이 목록에 있는데 가격이 없음 (0 · 빈 칸 · 숫자 아님) 이고 빠진
       이유도 없음 — 앱이 그 종목을 가격 없이 보여 틀린 값이에요 (예전과 같은 실패 · 사이트 점검(live)은 예전처럼 경고 · 파이프라인은 목록에 있는
       종목에 이유를 적지 않아요). 기록이 없는 파일은 발행 때 경고 · 점검 때 건너뜀 (그대로). 손으로 더한 종목 줄(check_us_extra · #126)은 바꾸지
       않았어요.
    ② '미국 목록 출처 티커 (주식 종류 · 점이 지워진 꼴)': 실패 — 점이 지워진 꼴(BRKB · BFB)이 S&P 500 목록에서 바뀌지 않은 채 발행 목록의 티커로 있음 (그날
       기록의 spTickers 에 그 꼴이 있음). 야후에는 그 꼴의 티커가 없어서 보통은 가격이 없어 빠지고 (아래 경고), 이 실패는 야후가 그 꼴에 다른 증권으로
       답해 엉뚱한 회사가 실리는 경우를 잡아요. 파이프라인이 바꾼 꼴이 이 파일의 표(US_CLASS_JOINED_SET)와 다르거나 기록 모양이 틀려도 실패 — 단
       사이트 점검(live)에서는 경고 (리뷰 2차 3: 칸을 더하는 다음 PR 이 아직 살아 있는 예전 파일 때문에 배포 점검에서 막히지 않게 · 이 줄은 이 PR 에서
       새로 생겼어요). 다른 출처(나스닥 등)에서 온 같은 글자의 티커는 다른 회사일 수 있어 이름만 적어요 (리뷰 4: 진짜 회사가 그 티커를 쓰게 되면
       날마다 발행이 막혀 사이트가 멈추지 않게) · 기록이 없는 파일에서는 출처를 알 수 없어 경고만. 경고 — 점이 지워진 꼴이 그날 S&P 500 목록 티커
       (spTickers)에 그대로 있음 (실리지 않았어도 · 바꾸기 표의 줄을 잃었거나 바꾸기가 고장: 리뷰 2차 1), 바꾸지 못한 출처 티커(unmapped), S&P
       500 목록 종목인데 야후가 가격을 하나도 주지 않은 티커(noPx: 점이 지워진 새 주식 종류 티커의 모습), 처리하다 오류로 멈춘 S&P 500 티커(spErr),
       출처 티커 기록이 없는 실행(read false). S&P 500 목록 종목 중 오늘 없는 다른 종목(spGone: 가격 이력이 60일이 안 된 새 상장 등)은 이름만
       적어요 (경고 아님).
       Jack 의 상시 규칙 (2026-11-19 · 우리 처리를 보는 검사): data.json ownDrop.usClass 가 있는 파일은 파이프라인이 빼야 할 행(us_class_bad_rows ·
       같은 함수)을 빼고 발행했어요. 그 파일에서 실패는 둘뿐 — 뺀 행이 US_CLASS_DROP_MAX 를 넘음 (발행 · 사이트 점검은 경고) · 빼야 할 행이 남아
       실림 (S&P 목록의 꼴은 늘 실패 · 출처를 알 수 없는 꼴과 관문 표와 다른 티커는 발행 실패 · 사이트 점검 경고 — 예전과 같아요). 그리고 mapped 에
       모양이 틀린 줄이 있어 그 바꾸기를 관문 표와 맞춰 볼 수 없으면 발행 실패 · 사이트 점검 경고 (리뷰 1차 M1 · 2차 · 예전 'mapped 모양' 실패와 같아요). 뺀 행 1~N · 관문 표와 다른 바꾸기 · 그 밖의 기록 모양은 경고 (남은 행이 없으면 틀린 숫자를 보이지 않아요). 이 검사의 행은 표의
       두 꼴에서만 나와 한 실행에 많아야 4건쯤이라 N(5)을 넘기 어려워요 — 이 검사를 지키는 것은 '빼야 할 행이 남으면 실패'예요. ownDrop.usClass 가
       없는 파일은 예전 규칙 그대로."""
    name = f"주식 종류 티커로 들어온 미국 종목 ({', '.join(sorted(US_CLASS_SET))}): 목록에 있거나 빠진 이유"
    th = "모두 있어야 함 (빠지면 이유가 있든 없든 경고 · 목록에 있는데 가격이 없으면 실패, 사이트 점검은 경고)"
    name2 = "미국 목록 출처 티커 (주식 종류 · 점이 지워진 꼴)"
    th2 = ("S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 목록에 실리지 않음 · 바꾼 꼴이 관문 표와 같음 · 기록 모양 (사이트 점검에서는 표 · 모양은 경고) "
           "(바꾸지 않은 지워진 꼴 · 바꾸지 못한 티커 · 가격 없는 · 오류 난 S&P 500 티커는 경고)")
    th2own = (f"Jack 의 상시 규칙 (2026-11-19): 파이프라인이 빼고 발행 (ownDrop.usClass) · 실패는 뺀 행 > {US_CLASS_DROP_MAX} (사이트 점검은 경고) 또는 "
              "빼야 할 행이 남아 실림 (S&P 목록의 꼴 · 출처를 알 수 없는 꼴 · 관문 표와 다른 티커 — 뒤 둘은 사이트 점검에서 경고) 또는 mapped 에 모양이 틀린 "
              "줄 (사이트 점검은 경고) · 뺀 행 · 관문 표와 다른 바꾸기 · 그 밖의 기록 모양 · 바꾸지 않은 지워진 꼴 · "
              "바꾸지 못한 티커 · 가격 없는 · 오류 난 S&P 500 티커는 경고")
    rec = data.get("usListSym")
    have = {s.get("t") for s in us if (num(s.get("price")) or 0) > 0}
    tickers = {s.get("t") for s in us}
    joined = sorted(t for t in US_CLASS_JOINED_SET if t in tickers)
    gone = sorted(t for t in US_CLASS_SET if t not in have)
    own = own_drop_get(data, US_CLASS_DROP_KEY)
    if isinstance(own, dict) and own["n"]:
        rep.detail("파이프라인이 뺀 미국 종목 (ownDrop.usClass · 주식 종류 티커)", [f"{t}: {w}" for t, w in own["rows"]]
                   + ([f"… 외 {own['n'] - len(own['rows'])}건"] if own["n"] > len(own["rows"]) else []))
    if not isinstance(rec, dict):
        if mode == "live":
            rep.skip(name, "기록 없음 (data.json usListSym 이 없는 발행본)")
        else:
            rep.add(name, True, f"기록 없음 (data.json usListSym) · 오늘 없는 종목 {len(gone)}" + (f": {_tickers(gone)}" if gone else ""), th, warn=True)
        if isinstance(own, dict):          # 상시 규칙 뒤 파일인데 usListSym 이 없음: 뺀 수는 그대로 봐요 (출처는 알 수 없어 이름만 · 경고)
            many = own["n"] > US_CLASS_DROP_MAX
            rep.add(name2, not (many and mode != "live"), (f"뺀 행 {own['n']}: {own_drop_text(own['rows'], own['n'])} · " if own["n"] else "")
                    + (f"점이 지워진 꼴과 같은 티커가 목록에 있음 (출처 모름): {_tickers(joined)} · " if joined else "")
                    + "기록 없음 (data.json usListSym)", th2own, warn=True)
        elif joined or mode != "live":       # 기록이 없으면 출처를 알 수 없어요: 점이 지워진 꼴과 같은 티커는 경고로 이름만 · 발행 때 경고, 점검 때 건너뜀
            rep.add(name2, True, (f"점이 지워진 꼴과 같은 티커가 목록에 있음 (출처 모름): {_tickers(joined)} · " if joined else "")
                    + "기록 없음 (data.json usListSym)" + (" · 뺀 행 기록(ownDrop.usClass) 모양이 틀림" if own is False else ""), th2, warn=True)
        else:
            rep.skip(name2, "기록 없음 (data.json usListSym 이 없는 발행본)")
        return
    # ① 들어온 종목: 있거나 빠진 이유 — Jack (2026-11-20): 한 종목이 출처에서 빠져도 발행을 막지 않아요 (이유가 있든 없든 경고 · 이름을 적어요).
    # 실패는 목록에 행이 있는데 가격이 없는 종목뿐 (빠진 이유도 없음 · 틀린 값이 보여요 · 예전과 같은 실패 · 사이트 점검은 경고).
    miss = rec.get("missing")
    miss = miss if isinstance(miss, dict) else {}
    why = {t: miss.get(t) for t in gone}
    told = [t for t in gone if isinstance(why[t], str) and why[t].strip()]
    silent = [t for t in gone if t not in told]
    no_px_row = [t for t in silent if t in tickers]      # 목록에 행이 있는데 가격이 없음 (0 · 빈 칸 · 숫자 아님) → 발행 실패
    quiet = [t for t in silent if t not in tickers]      # 목록에 없고 이유도 없음 → 경고 (Jack 2026-11-20)
    odd = sorted(str(t) for t in miss if t not in US_CLASS_SET)
    parts = ([f"목록에 있는데 가격이 없음 {len(no_px_row)}: {_tickers(no_px_row)}"] if no_px_row else []) \
        + ([f"이유 없이 빠짐 {len(quiet)}: {_tickers(quiet)}"] if quiet else []) \
        + ([f"빠짐 {len(told)}: " + " · ".join(f"{t} ({why[t]})" for t in told)] if told else []) \
        + ([f"관문 목록에 없는 티커 {len(odd)}: {_tickers(odd)}"] if odd else [])
    rep.add(name, not no_px_row or mode == "live", f"{len(US_CLASS_SET) - len(gone)} / {len(US_CLASS_SET)} 있음" + "".join(f" · {x}" for x in parts),
            th, warn=bool(gone or odd))
    if gone:
        rep.detail("주식 종류 티커로 들어온 미국 종목 중 오늘 없는 종목 (usListSym.missing)",
                   [f"{t}: {why[t] if t in told else ('목록에 있는데 가격이 없음 · 이유 없음' if t in tickers else '이유 없음')}" for t in gone])
    # ② 출처 티커: 모양 · 표 · 바꾸지 못한 티커 · 가격 없는 · 오류 난 S&P 500 티커
    p = _us_sym_parse(rec)
    mapped, unmapped, sp_t, sp_gone, no_px, sp_err, bad = (p[k] for k in ("mapped", "unmapped", "sp_t", "sp_gone", "no_px", "sp_err", "bad"))
    sp_set = set(sp_t or [])
    joined_sp = [t for t in joined if t in sp_set]                # S&P 500 목록에서 바뀌지 않고 실린 꼴 (실패)
    joined_other = [t for t in joined if t not in sp_set]         # 다른 출처의 같은 글자 티커 (다른 회사일 수 있어요 · 이름만)
    joined_left = sorted(k for k in US_CLASS_JOINED_SET if k in sp_set)   # 리뷰 2차 1: 바꾸지 않은 지워진 꼴이 S&P 목록에 (실렸든 아니든 · 경고)
    soft = mode == "live"                                         # 리뷰 2차 3: 사이트 점검에서는 표 · 모양 문제는 경고 (실린 엉뚱한 회사는 실패 그대로)
    wrong = [f"{a} → {b} (관문 표 {US_CLASS_JOINED_SET[a]})" for a, b in (p["wrong_all"] if isinstance(own, dict) else p["wrong"])]
    shown = " · ".join(f"{a} → {b}" for _s, a, b in mapped[:US_FCUR_SHOW]) + (f" 외 {len(mapped) - US_FCUR_SHOW}개" if len(mapped) > US_FCUR_SHOW else "")
    own_parts, left = [], []
    if isinstance(own, dict):                                     # Jack 의 상시 규칙: 파이프라인이 뺀 행 · 그래도 남은 행
        left, _probs = us_class_bad_rows(rec, us)
        n = max(own["n"], len(left))
        own_parts = ([f"뺀 행 {own['n']}: {own_drop_text(own['rows'], own['n'])}"] if own["n"] else []) \
            + ([f"뺀 행이 기준 {US_CLASS_DROP_MAX} 을 넘음 ({n})"] if n > US_CLASS_DROP_MAX else []) \
            + ([f"빼야 할 티커가 남아 실림: {own_drop_text(left)}"] if left else []) \
            + ([US_CLASS_BLIND if not soft else US_CLASS_BLIND.replace("발행 실패", "사이트 점검은 경고")] if p["map_blind"] else [])
    parts = own_parts \
        + ([f"S&P 500 목록의 점이 지워진 꼴이 바뀌지 않고 목록에 있음: {_tickers(joined_sp)}"] if joined_sp else []) \
        + ([f"관문 표와 다르게 바꿈: {' · '.join(wrong)}"] if wrong else []) \
        + ([f"기록 모양이 틀림: {' · '.join(bad)}"] if bad else []) \
        + ([f"S&P 500 목록에 점이 지워진 꼴이 바뀌지 않고 그대로 있음 (바꾸기 확인 필요): {_tickers(joined_left)}"] if joined_left else []) \
        + [f"바꿈 {len(mapped)}" + (f" ({shown})" if mapped else "")] \
        + ([f"바꾸지 못함 {len(unmapped)}: " + " · ".join(f"{s0} '{a}' ({w})" for s0, a, w in unmapped[:US_FCUR_SHOW])] if unmapped else []) \
        + ([f"S&P 500 티커인데 야후 가격이 없음 {len(no_px)}: {_tickers(no_px)} (점이 지워진 새 주식 종류 티커일 수 있어요)"] if no_px else []) \
        + ([f"S&P 500 티커를 처리하다 오류 {len(sp_err)}: {_tickers(sp_err)}"] if sp_err else []) \
        + ([f"S&P 500 중 오늘 없음 {len(sp_gone)}: " + " · ".join(f"{t} ({w})" for t, w in list(sp_gone.items())[:US_FCUR_SHOW])
            + (f" 외 {len(sp_gone) - US_FCUR_SHOW}곳" if len(sp_gone) > US_FCUR_SHOW else "")] if sp_gone else []) \
        + (["S&P 500 목록을 믿지 못한 날 (빠진 종목을 세지 않음)"] if sp_gone is None else []) \
        + ([f"다른 출처의 같은 글자 티커 (S&P 500 목록 밖 · 다른 회사일 수 있어요): {_tickers(joined_other)}"] if joined_other else []) \
        + (["출처 티커 기록이 없는 실행 (read false)"] if rec.get("read") is False else []) \
        + (["뺀 행 기록(ownDrop.usClass) 모양이 틀림"] if own is False else [])
    warn2 = bool(joined_left or unmapped or no_px or sp_err or rec.get("read") is False or wrong or bad or own is False)
    if isinstance(own, dict):
        left_sp = [t for t, _w, k in left if k == "sp"]
        left_other = [t for t, _w, k in left if k != "sp"]
        ok2 = not (left_sp or ((left_other or p["map_blind"] or max(own["n"], len(left)) > US_CLASS_DROP_MAX) and not soft))
        rep.add(name2, ok2, " · ".join(parts), th2own, warn=warn2 or bool(own["n"] or left))
    else:                                                         # 상시 규칙 전 파일 (ownDrop.usClass 없음): 예전 규칙 그대로
        rep.add(name2, not (joined_sp or ((wrong or bad) and not soft)), " · ".join(parts), th2, warn=warn2)
    if unmapped:
        rep.detail("야후 모양으로 바꾸지 못해 요청하지 않은 미국 목록 티커 (usListSym.unmapped)", [f"{s0} '{a}': {w}" for s0, a, w in unmapped])
    if sp_gone:
        rep.detail("S&P 500 목록 종목 중 오늘 미국 목록에 없는 종목 (usListSym.spGone)", [f"{t}: {w}" for t, w in sp_gone.items()])


def check_us_foreign(rep, data, us, mode):
    """2026-11-14 (더하기만): 미국 상장 외국 회사(US_FOREIGN_SET = fetch_data.US_FOREIGN) 중 재무제표 통화 표시(fcur)가 없는 종목의 PER · PBR ·
    배당수익률은 파이프라인이 회사 합계 · 실제 배당과 맞춰 본 뒤에만 나가요 (data.json usForeign = {checked, cut [[티커, 칸, 이유]]}). 실패: ① 그런
    종목에 세 칸 중 하나라도 있는데 checked 에 없음 (맞춰 보지 않은 숫자) ② cut 에 적힌 칸이 남아 있음 (pbr 이면 가치 점수 vz 도) ③ 기록 모양이 틀림.
    ④ (2026-11-14, Jack 의 이유 줄) 종목의 fgnCut 이 틀린 모양이거나 그 칸이 남아 있음, 또는 cut 줄(검사가 멈춘 날 빼고)의 칸이 그 종목의 fgnCut 에
    없음 (앱이 이유 줄 대신 '자료가 없어요' 를 보여요), 또는 fgnCut 의 칸에 맞는 cut 줄이 없음 (리뷰 N3). 기록이 없는 파일(이 칸 전 발행본): 종목에
    fgnCut 이 있으면 실패 (기록 없이 표시만) · 맞춰 볼 숫자가 없으면 통과 · 있으면 발행 때 실패, 사이트 점검(live) 때 경고.
    경고 (리뷰 S1, 발행은 막지 않아요): 검사가 멈춘 날 (cut 줄의 이유가 '검사가 멈춤 …') — 그 칸은 이유 줄 없이 비어 앱의 요약 칸 · 배당 머리가
    '자료가 없어요' 예요.
    2026-11-14 (Jack, Q5 · 더하기만): 기록에 set(규칙으로 찾은 외국 회사)이 있으면 위 규칙을 US_FOREIGN_SET ∪ set 의 회사 모두에 적용해요 — set 의
    회사(fcur 없음)에 숫자가 있는데 checked 에 없으면 실패 (우리 기록이 어긋난 것 · 시장 탓일 수 없어요), 표시(fgnCut)는 그 회사들에만. 더 보는 것
    (실패): set 모양 · 근거 글자(US_FGN_BASIS) · 근거가 기록과 어긋남 (fcur 인데 종목에 fcur 없음 · country 인데 나라가 없거나 미국 · floor 인데 21곳
    밖) · 목록에 있는 21곳이나 fcur 회사가 set 에 없음. 경고만: unknown(나라를 몰라 보지 않은 회사) · 근거 error · 목록에 있는 US_FGN_NAMED 가
    set 에 없음. set 이 없는 기록(이 칸 전 발행본)은 예전 그대로 21곳만 봐요."""
    name = "미국 상장 외국 회사: 회사 합계와 맞춘 PER·PBR·배당수익률만"
    th = ("fcur 없는 외국 회사(21곳 + usForeign.set)는 usForeign.checked 에 · cut 의 칸은 빈 칸 (pbr 이면 vz 도) · 그 칸마다 종목의 fgnCut · "
          "set 은 규칙의 근거와 맞아야 함")
    by = {s.get("t"): s for s in us}
    rec = data.get("usForeign")
    mode_strict = mode != "live"     # 발행: 파일의 스위치가 관문의 스위치와 같아야 해요 · 사이트 점검: 그 파일이 만들어진 때의 스위치를 그대로 봐요
    has_set = isinstance(rec, dict) and "set" in rec            # 이 칸이 있으면 (null 이어도) 넓힌 기록이에요 — 모양까지 봐요
    fset = rec.get("set") if has_set else None
    # 리뷰 S1: 칸의 종류. 기록에 nocmp(스위치)가 있으면 그 스위치의 nocompare 종류도 표시로 받아요 (없는 기록 = 예전 두 가지만)
    nmode = rec.get("nocmp") if isinstance(rec, dict) and "nocmp" in rec else None
    nmode_ok = isinstance(nmode, str) and nmode in US_FGN_NOCMP_KIND    # 리뷰 2차 N1: 목록 · dict 가 와도 멈추지 않고 실패 줄로
    kinds_ok = set(US_FGN_WHY) | ({US_FGN_NOCMP_KIND[nmode], US_FGN_NOREC, US_FGN_STOPPED_KIND} - {None} if nmode_ok else set())
    foreign = set(US_FOREIGN_SET) | (set(fset) if isinstance(fset, dict) else set())
    want = sorted(t for t, s in by.items() if t in foreign and not s.get("fcur") and any(s.get(k) is not None for k in US_FOREIGN_KEYS))
    marked = sorted(str(s.get("t")) for s in us if "fgnCut" in s)
    if not isinstance(rec, dict):
        if marked:
            rep.add(name, False, f"기록 없음 (data.json usForeign) 인데 fgnCut 표시가 있는 종목 {len(marked)}곳: {_tickers(marked)}", th)
            return
        if not want:
            rep.add(name, True, "기록 없음 (data.json usForeign) · 맞춰 볼 외국 회사 숫자 없음", th)
        else:
            rep.add(name, mode == "live", f"기록 없음 (data.json usForeign) · 맞춰 보지 않은 숫자 {len(want)}곳: {_tickers(want)}", th, warn=True)
        return
    checked, cut, bad, left, n_by = rec.get("checked"), rec.get("cut"), [], [], collections.Counter()
    if not (isinstance(checked, list) and all(isinstance(t, str) for t in checked)):
        bad.append("checked 모양")
        checked = []
    if not isinstance(cut, list):
        bad.append("cut 모양")
        cut = []
    rows = []
    for x in cut:
        if not (isinstance(x, list) and len(x) == 3 and isinstance(x[0], str) and x[1] in US_FOREIGN_KEYS and isinstance(x[2], str) and x[2]):
            bad.append(f"cut 줄 {json.dumps(x, ensure_ascii=False)[:30]}")
            continue
        rows.append(x)
        n_by[x[1]] += 1
        s = by.get(x[0])
        if s is not None:
            left += [f"{x[0]}.{k}" for k in ((x[1], "vz") if x[1] == "pbr" else (x[1],)) if s.get(k) is not None]
    unchecked = [t for t in want if t not in set(checked)]
    cutset, nocut = {(x[0], x[1]) for x in rows}, []
    # 2026-11-14 (Jack 의 이유 줄): 종목마다 fgnCut = {칸: mismatch | currency}. 적힌 칸은 비어 있어야 하고 (pbr 이면 vz 도), usForeign.cut 의
    # 줄(검사가 멈춘 날 빼고)마다 그 종목에 fgnCut 이 있어야 해요 — 없으면 앱이 이유 줄 대신 '자료가 없어요' 를 보여요.
    for s in us:
        if "fgnCut" not in s:
            continue
        g, t = s.get("fgnCut"), s.get("t")
        if not (isinstance(g, dict) and g and all(k in US_FOREIGN_KEYS and v in kinds_ok for k, v in g.items())):
            bad.append(f"{t}.fgnCut {json.dumps(g, ensure_ascii=False)[:30]}")
            continue
        if t not in foreign or s.get("fcur"):
            bad.append(f"{t}.fgnCut (외국 회사 목록 밖이거나 fcur)")
        left += [f"{t}.{k}" for f in g for k in ((f, "vz") if f == "pbr" else (f,)) if s.get(k) is not None]
        nocut += [f"{t}.{f}" for f in g if (t, f) not in cutset]
    left = list(dict.fromkeys(left))
    # 2026-11-14 (Q5): 규칙으로 찾은 외국 회사 (set) — 모양 · 근거가 기록과 맞는지 · 빠진 회사 (실패), 나라 모름 · 멈춤 · 이름으로 넓힌 회사 (경고)
    notes, fwarn = [], False
    if has_set:
        sbad, miss = [], []
        if not isinstance(fset, dict):
            sbad.append("set 모양")
            fset = {}
        for t, v in fset.items():
            if not (isinstance(t, str) and isinstance(v, list) and len(v) == 3 and v[2] in US_FGN_BASIS
                    and all(x is None or (isinstance(x, str) and x.strip()) for x in v[:2])):
                sbad.append(f"set {t} {json.dumps(v, ensure_ascii=False)[:30]}")
                continue
            s = by.get(t)
            if v[2] == "fcur" and s is not None and not s.get("fcur"):
                sbad.append(f"set {t} (근거 fcur 인데 종목에 fcur 없음)")
            if v[2] == "country" and not (v[0] and v[0].strip().lower() not in US_FGN_HOME):
                sbad.append(f"set {t} (근거 country 인데 나라 {v[0]!r})")
            if v[2] == "floor" and t not in US_FOREIGN_SET:
                sbad.append(f"set {t} (근거 floor 인데 21곳 밖)")
        listed = {t for t, s in by.items() if s.get("etf") is not True and not s.get("fund")}
        miss = sorted(t for t in listed if t not in fset and (t in US_FOREIGN_SET or by[t].get("fcur")))
        if miss:
            sbad.append(f"set 에 없는 21곳 · fcur 회사 {len(miss)}: {', '.join(miss[:6])}")
        bad += sbad
        unk = rec.get("unknown", [])
        if not (isinstance(unk, list) and all(isinstance(t, str) for t in unk)):
            bad.append("unknown 모양")
            unk = []
        by_b = collections.Counter(v[2] for v in fset.values() if isinstance(v, list) and len(v) == 3)
        notes.append(f"외국 회사 {len(fset)}곳 (재무제표 통화가 달러가 아님 {by_b['fcur']} · 본사 미국 밖 {by_b['country']} · 예탁증서 이름 "
                     f"{by_b['adr']} · 손으로 정한 곳 {by_b['floor']})")
        err = sorted(t for t, v in fset.items() if isinstance(v, list) and len(v) == 3 and v[2] == "error")
        named = sorted(t for t in US_FGN_NAMED if t in listed and t not in fset)
        if err:
            notes.append(f"외국 회사인지 보다가 멈춰 맞춰 본 곳 {len(err)}: {_tickers(err)}")
        if unk:
            notes.append(f"나라를 몰라 외국 회사로 보지 않은 S&P 500 밖 회사 {len(unk)}곳: {_tickers(unk)}")
        if named:
            notes.append(f"외국 회사로 보지 않은 {'·'.join(sorted(US_FGN_NAMED))} 중 {len(named)}곳: {_tickers(named)}")
        fwarn = bool(err or unk or named)
        # 리뷰 S1: 스위치 · 종류 · 비우지 않은 칸 (kept) — 모두 우리 기록이 맞는지예요
        kbad = []
        if not nmode_ok:
            kbad.append(f"nocmp {json.dumps(nmode, ensure_ascii=False)[:30]}")
        elif nmode != US_FGN_NOCMP and mode_strict:
            kbad.append(f"nocmp {nmode} (관문 스위치 {US_FGN_NOCMP})")
        nk = US_FGN_NOCMP_KIND.get(nmode) if nmode_ok else None
        for x in rows:
            if x[2].startswith(US_FGN_STOPPED):                 # Q10: 멈춘 날 비운 칸에도 표시 stopped (앱이 그날의 줄을 붙여요)
                g = (by.get(x[0]) or {}).get("fgnCut")
                if x[0] in by and nmode_ok and not (isinstance(g, dict) and g.get(x[1]) == US_FGN_STOPPED_KIND):
                    kbad.append(f"멈춘 날 표시 {x[0]}.{x[1]} {json.dumps(g.get(x[1]) if isinstance(g, dict) else None)} ≠ stopped")
                continue
            want_k = ("currency" if x[2].startswith(US_FGN_CUR_WHY) else
                      US_FGN_NOREC if x[1] == "dy" and x[2] == US_FGN_NOREC_WHY else
                      (nk or "비우면 안 됨 (keep)") if x[2] == US_FGN_NOCMP_WHY.get(x[1]) else "mismatch")
            got_k = (by.get(x[0]) or {}).get("fgnCut", {}).get(x[1]) if isinstance((by.get(x[0]) or {}).get("fgnCut"), dict) else None
            if got_k is not None and got_k != want_k:
                kbad.append(f"종류 {x[0]}.{x[1]} {got_k} ≠ {want_k}")
        kmap = rec.get("kind")
        marks = {str(s.get("t")): s["fgnCut"] for s in us if isinstance(s.get("fgnCut"), dict)}
        if not (isinstance(kmap, dict) and all(isinstance(v, dict) for v in kmap.values())):
            kbad.append("kind 모양")
        elif kmap != marks:
            diff = sorted(set(kmap) ^ set(marks) | {t for t in set(kmap) & set(marks) if kmap[t] != marks[t]})
            kbad.append(f"kind ≠ 종목 표시 {len(diff)}: {', '.join(diff[:4])}")
        kept_ = rec.get("kept", [])
        if not isinstance(kept_, list):
            kbad.append("kept 모양")
            kept_ = []
        for x in kept_:
            if not (isinstance(x, list) and len(x) == 3 and isinstance(x[0], str) and x[1] in US_FOREIGN_KEYS
                    and x[2] == US_FGN_NOCMP_WHY.get(x[1])):
                kbad.append(f"kept 줄 {json.dumps(x, ensure_ascii=False)[:30]}")
            elif nmode != "keep":
                kbad.append(f"kept {x[0]}.{x[1]} (스위치 {nmode})")
            elif x[1] in (marks.get(x[0]) or {}):
                kbad.append(f"kept {x[0]}.{x[1]} 인데 표시가 있음")
        nc = sorted(f"{t}.{f}" for t, g in marks.items() for f, k in g.items() if str(k).startswith("nocompare"))
        if nc:
            notes.append(f"맞춰 볼 값이 없어 비운 칸 {len(nc)} (스위치 {nmode}): {', '.join(nc[:8])}" + (f" 외 {len(nc) - 8}" if len(nc) > 8 else ""))
        if kept_ and nmode == "keep":
            notes.append(f"맞춰 볼 값이 없어 비우지 않은 칸 {len(kept_)} (스위치 keep)")
        # 리뷰 S2: S&P 500 목록 — 믿었는지와 그 근거가 맞는지 · 못 믿은 날은 본사 나라 · 이름 근거가 없어야 해요 (경고)
        sp = rec.get("sp500")
        if not (isinstance(sp, dict) and (sp.get("n") is None or (isinstance(sp.get("n"), int) and not isinstance(sp.get("n"), bool)))
                and isinstance(sp.get("inList"), int) and not isinstance(sp.get("inList"), bool) and isinstance(sp.get("ok"), bool)):
            kbad.append(f"sp500 모양 {json.dumps(sp, ensure_ascii=False)[:40]}")
        else:
            okw = sp["n"] is not None and sp["inList"] >= US_SP500_MIN and sp["n"] <= US_SP500_MAX
            if sp["ok"] != okw:
                kbad.append(f"sp500 ok {sp['ok']} (목록 {sp['n']} · 겹침 {sp['inList']} · 기준 겹침 {US_SP500_MIN} 이상 · 목록 {US_SP500_MAX} 이하)")
            bases = {v[2] for v in fset.values() if isinstance(v, list) and len(v) == 3}
            if not sp["ok"]:
                fwarn = True
                notes.append(f"S&P 500 목록을 쓸 수 없던 날 (목록 {sp['n'] if sp['n'] is not None else '없음'} · 겹침 {sp['inList']}): 본사 나라 규칙 없이 "
                             f"21곳 · 재무제표 통화 · 어제 목록만 맞춰 봄")
                if bases & {"country", "adr"}:
                    kbad.append("sp500 을 못 믿은 날인데 근거 country · adr")
            elif "prev" in bases:
                kbad.append("sp500 을 믿은 날인데 근거 prev")
        bad += kbad
    # 리뷰 2차 S1: 배당 기록 · 가격을 읽지 못해 비운 배당수익률 — 우리 쪽 자료가 빠진 날이에요 (하루 통째로 빠지면 40곳쯤): 늘 경고 (이 칸 전 기록도)
    norec = sorted({x[0] for x in rows if x[1] == "dy" and x[2] == US_FGN_NOREC_WHY})
    if norec:
        notes.append(f"배당 기록 · 가격을 읽지 못해 비운 배당수익률 {len(norec)}곳: {_tickers(norec)} (다운로드의 배당 칸 확인)")
        fwarn = True
    nomark = [f"{x[0]}.{x[1]}" for x in rows if not x[2].startswith(US_FGN_STOPPED) and x[0] in by
              and not (isinstance(by[x[0]].get("fgnCut"), dict) and x[1] in by[x[0]]["fgnCut"])]
    probs = ([f"맞춰 보지 않은 숫자 {len(unchecked)}곳: {_tickers(unchecked)}"] if unchecked else []) \
        + ([f"이유 표시(fgnCut) 없음 {len(nomark)}: {', '.join(nomark[:6])}"] if nomark else []) \
        + ([f"cut 줄 없는 표시 {len(nocut)}: {', '.join(nocut[:6])}"] if nocut else []) \
        + ([f"남은 칸 {len(left)}: {', '.join(left[:6])}"] if left else []) + ([f"모양 {len(bad)}: {', '.join(bad[:3])}"] if bad else [])
    names = sorted({x[0] for x in rows})
    stopped = sorted({x[0] for x in rows if x[2].startswith(US_FGN_STOPPED)})
    st_marked = bool(stopped) and nmode_ok and all(isinstance((by.get(t) or {}).get("fgnCut"), dict) for t in stopped if t in by)
    rep.add(name, not probs, f"확인 {len(checked)}곳 · 비운 칸 PER {n_by['per']} · PBR {n_by['pbr']} · 배당 {n_by['dy']}"
            + (f" ({_tickers(names)})" if names else "") + "".join(f" · {p}" for p in probs)
            + (f" · 검사가 멈춰 맞춰 보지 않고 비운 회사 {len(stopped)}곳: {_tickers(stopped)} "
               + ("(이유 줄: 오늘은 확인하지 못함 · co.fgnStopped)" if st_marked else "(이유 줄 없음 · 앱은 '자료가 없어요')") if stopped else "")
            + "".join(f" · {n}" for n in notes),
            th, warn=bool(stopped) or fwarn)
    if rows:
        rep.detail("미국 상장 외국 회사: 회사 합계 · 실제 배당과 맞지 않아 비운 칸 (usForeign.cut)", [f"{t} {f}: {w}" for t, f, w in rows])


def is_foreign(code):
    return isinstance(code, str) and len(code) == 6 and code[0] == "9"


def check_foreign(rep, kr, comps):
    # 해외 기업: PBR·PER·EPS·BPS·배당·금액·DCF 입력이 모두 빈 칸 (통화와 상관없는 비율과 KRX 가격·시가총액은 있어도 돼요)
    def has(v):
        return any(num(x) is not None for x in v) if isinstance(v, list) else num(v) is not None

    def nonzero(v):
        return any(num(x) not in (None, 0) for x in v) if isinstance(v, list) else num(v) not in (None, 0)
    bad = []
    for s in kr:
        if is_foreign(s.get("t")):
            bad += [f"{s['t']}.{k}" for k in FOREIGN_BLANK if has(s.get(k))]
            bad += [f"{s['t']}.{k}" for k in FOREIGN_ZERO_OK if nonzero(s.get(k))]
    for c in comps:
        if is_foreign(c.get("t")):
            bad += [f"corp {c['t']}.{k}" for k in FOREIGN_BLANK + FOREIGN_BLANK_CORP + FOREIGN_BLANK_LISTS if has(c.get(k))]
            bad += [f"corp {c['t']}.{k}" for k in FOREIGN_ZERO_OK if nonzero(c.get(k))]
            if c.get("dcfReady") is not False:
                bad.append(f"corp {c['t']}.dcfReady")
    n = sum(1 for s in kr if is_foreign(s.get("t")))
    rep.add("해외 기업(9…) 원화 아닐 수 있는 금액 비움", not bad, f"{n}곳 · 남은 칸 {len(bad)}" + (f" (예: {', '.join(bad[:3])})" if bad else ""),
            "PBR·PER·EPS·BPS·금액·DCF 빈 칸 · 배당은 빈 칸 또는 0")


def is_pref(code):
    return isinstance(code, str) and len(code) == 6 and code[-1] != "0"


_BASE_FACTORS = [1.0] + [float(k) for k in SPLIT_FACTORS] + [1.0 / k for k in SPLIT_FACTORS]
_OK_FACTORS = sorted({a * b for a in _BASE_FACTORS for b in _BASE_FACTORS})   # 당기 배율 × 이전 해 배율


def _factor_ok(f):
    """배율이 1 · 깨끗한 분할 배율 · 그 역수, 또는 그 둘의 곱인지 (발행값은 소수 여섯째 자리 반올림)."""
    return f > 0 and any(abs(f / g - 1) < 1e-4 for g in _OK_FACTORS)


def _isnum(x):
    """JSON 숫자인지 (글자 '0.07'·참/거짓·NaN 은 아니에요) — v19.1b 새 칸은 모양까지 엄격하게 봐요."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _nums3(v):
    """길이 3 목록이고 칸마다 숫자 또는 빈 칸이면 그 숫자들, 아니면 None."""
    if not isinstance(v, list) or len(v) != 3 or any(x is not None and not _isnum(x) for x in v):
        return None
    return [float(x) if x is not None else None for x in v]


def div_row_problem(s, exact=False):
    """한 국내 종목의 dps3 · dps3a · dpsF · divSt 가 서로 맞는지. 맞으면 None, 아니면 이유. (v19.1b)
    v19.1j: exact — 답 12 의 세 조건을 모두 지킨 종목(exact_bonus_problem 이 None)만 깨끗하지 않은 배율을 받아요."""
    d3, a3, f3 = _nums3(s.get("dps3")), _nums3(s.get("dps3a")), _nums3(s.get("dpsF"))
    st = s.get("divSt")
    if d3 is None or a3 is None or f3 is None or st not in DIV_STATUS:
        return "칸 모양"
    paying = []
    for d, a, f in zip(d3, a3, f3):
        if d is None:
            if a is not None or f is not None:
                return "모르는 해에 값"
        elif d == 0:
            if a != 0 or f is not None:
                return "배당 없는 해"
        elif f is None:
            paying.append(None)
            if a is not None:
                return "배율 없이 맞춘 값"
        else:
            paying.append(f)
            if not _factor_ok(f) and not exact:
                return f"깨끗하지 않은 배율 {f:g}"
            if a is None or a < 0 or abs(a - d / f) > DIV_TOL:
                return f"dps3a {a} ≠ {d:g} ÷ {f:g}"
    if not paying:          # 3년 모두 0 이면 배당 없음, 모르는 해가 섞이면 알 수 없음
        want = "zero" if all(d == 0 for d in d3) else "nd"
    else:
        want = "nc/nd" if None in paying else ("same" if all(f == 1 for f in paying) else "adj")
    if (want == "nc/nd" and st not in ("nc", "nd")) or (want != "nc/nd" and st != want):
        return f"divSt {st} (값으로는 {want})"
    return None


def floor_1(x):
    """소수 첫째 자리까지 내림한 글자 — 84.96% 가 '85.0%' 로 보여 '85% 미만 실패' 옆에 서지 않게."""
    return f"{math.floor(x * 10 + 1e-9) / 10:.1f}"


def in_div_rank(s):
    """배당 순위에 든 종목인지 (dyt·dz 가 모두 숫자)."""
    return bool(s) and num(s.get("dyt")) is not None and num(s.get("dz")) is not None


def rank_miss_reason(s):
    """필수 종목이 배당 순위(dyt·dz)에 없는 이유 — 경고·실패 줄에 그대로 적어요. (v19.1b)"""
    if not s:
        return "데이터에 없음"
    st = s.get("divSt")
    if not st:
        return "DART 배당 표 없음"
    a3 = _nums3(s.get("dps3a"))
    if a3 is None or a3[0] is None:
        return {"nc": "비교 불가 (유상증자·합병 등으로 오늘 주식 수 기준을 확인 못 함)",
                "nd": "알 수 없음 (오늘 주식 수 기준을 확인 못 함)"}.get(st, f"올해 배당 기준 없음 ({st})")
    if num(s.get("dyt")) is None:
        return "수익률 없음 (종가 없음 또는 30% 초과)"
    return "배당 점수(dz) 없음"


def check_v191b(rep, data, kr, us, by, comps, pdata, today=None):
    """v19.1b 새 줄 (Jack 승인 필요): 분할에 안전한 국내 배당 · 배당 순위 · 베타 표준오차 · 재무 경고 검사 기록."""
    dc = data.get("divCheck")
    if not isinstance(dc, dict):
        # v19.1b 전 데이터: 머지 뒤 첫 발행 전까지의 사이트(--live)와 시험 데이터에는 경고 한 줄만. 직전 발행본에 있었는데 빠지면
        # 실패 — 발행은 언제나 이 관문을 지나니, 한 번 새 칸으로 발행된 뒤에는 옛 형식이 다시 발행될 수 없어요
        had = isinstance((pdata or {}).get("divCheck"), dict)
        rep.add("배당 분할 확인 기록 (divCheck)", not had,
                "없음 — 직전 발행본에는 있었어요" if had else "없음 (v19.1b 전 형식이라 새 검사를 건너뛰어요)",
                "있어야 함 (v19.1b 전 데이터만 경고)", warn=not had)
        return
    rep.add("배당 분할 확인 기록 (divCheck)", dc.get("v") == 1, f"v{dc.get('v')}", "v1")
    must_kr = [t for t in MUST if (by.get(t) or {}).get("cls") == "kr"]
    com = [s for s in kr if not is_pref(s.get("t"))]

    # 1. 칸 채움: dps3 가 있는 보통주는 모두 divSt · dps3a · dpsF 를 갖고, 없는 종목은 갖지 않아요
    miss = [s["t"] for s in com if isinstance(s.get("dps3"), list) and not s.get("divSt")]
    extra = [s["t"] for s in kr if s.get("divSt") and (is_pref(s["t"]) or not isinstance(s.get("dps3"), list))]
    rep.add("국내 배당 분할 확인 칸 (dps3 있는 보통주 모두)", not miss and not extra,
            f"빠짐 {len(miss)} · 엉뚱한 종목 {len(extra)}" + (f" (예: {(miss + extra)[0]})" if miss or extra else ""), "0 · 0")

    # 2. dps3a = dps3 ÷ dpsF (배율은 1 · 깨끗한 분할 배율 · 그 곱), divSt 가 값과 맞음
    ex = exact_bonus_set(data, kr, comps, today)          # v19.1j 답 12: 공시의 정확한 무상증자 배율 (세 조건을 모두 지킨 종목만)
    bad = [(s["t"], why) for s in com if s.get("divSt") for why in [div_row_problem(s, exact=s["t"] in ex)] if why]
    rep.add("국내 dps3a = dps3 ÷ 배율 · divSt 맞음", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0][0]} {bad[0][1]})" if bad else "")
            + (f" · 공시의 정확한 무상증자 배율 {len(ex)}곳" if ex else ""),
            "0 (배율은 1·2·2.5·3·4·5·10·20·25·50·100·그 역수와 곱 · 공시의 정확한 무상증자 배율은 답 12 의 세 조건을 지킬 때만)")

    # 3. dyt = dps3a[0] ÷ 종가 × 100 (0~30%), dz 는 dyt 가 있는 종목에만 (0~100)
    bad = []
    for s in kr:
        a3 = _nums3(s.get("dps3a")) if s.get("divSt") else None
        a0, p, y, z = (a3[0] if a3 else None), num(s.get("price")), s.get("dyt"), s.get("dz")
        if (y is not None and not _isnum(y)) or (z is not None and not _isnum(z)):
            bad.append(f"{s['t']} 숫자 아님")
            continue
        want = None if a0 is None or not p or p <= 0 else a0 / p * 100
        if y is not None:
            if want is None or not (0 <= y <= DYT_MAX) or abs(y - want) > DIV_TOL:
                bad.append(f"{s['t']} dyt {y}")
        elif want is not None and want <= DYT_MAX:
            bad.append(f"{s['t']} dyt 빈 칸 (계산하면 {want:.2f})")
        if (y is None) != (z is None) or (z is not None and not 0 <= z <= 100):
            bad.append(f"{s['t']} dz {z}")
    rep.add("국내 오늘 배당수익률 dyt = dps3a[0] ÷ 종가 · dz", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else ""),
            f"0 (dyt 0~{DYT_MAX:g}% · dz 는 dyt 있는 종목에만)")

    # 4·5. 배당한 국내 회사(외국 기업 빼고) 중 오늘 수익률을 확인한 비율 · 분할로 맞춘 비율
    payers = [s for s in com if not is_foreign(s.get("t")) and (_nums3(s.get("dps3")) or [None])[0] and _nums3(s["dps3"])[0] > 0]
    n_ok = sum(1 for s in payers if num(s.get("dyt")) is not None)
    share = 100.0 * n_ok / len(payers) if payers else 0.0
    seen, floor = DYT_COVER_BANDS["seen"], DYT_COVER_BANDS["floor"]
    rep.add("배당한 국내 회사 중 오늘 수익률(dyt) 확인", bool(payers) and share >= floor,
            f"{floor_1(share)}% ({n_ok:,} / {len(payers):,})",
            f"{floor:g}% 미만 실패 · {seen:g}% 미만 경고 (기준: DYT_COVER_BANDS)", warn=share < seen)
    adj = sum(1 for s in payers if s.get("divSt") == "adj")
    ashare = 100.0 * adj / len(payers) if payers else 0.0
    rep.add("배당한 국내 회사 중 분할·무상증자로 맞춘 비율", bool(payers) and ashare <= DIV_ADJ_MAX,
            f"{ashare:.1f}% ({adj} / {len(payers):,})", f"≤ {DIV_ADJ_MAX:g}% (많으면 배율을 잘못 읽은 날)")

    # 6. 배당 순위: 필수 종목의 dyt·dz. 2곳 이상 빠지면 실패, 빠진 종목이 있으면 종목·이유를 적은 경고
    #    (Jack 2026-11-05: 배당 자료 구멍 하나가 사이트 전체를 멈추지 않게)
    rank_miss = [(t, rank_miss_reason(by.get(t))) for t in must_kr if not in_div_rank(by.get(t))]
    rep.add("필수 종목 배당 순위 (dyt·dz)", len(rank_miss) < DIV_RANK_MISS_FAIL,
            "모두 있음" if not rank_miss else f"빠짐 {len(rank_miss)}: " + " · ".join(f"{t} {why}" for t, why in rank_miss),
            f"{','.join(must_kr)} (빠지면 경고 · {DIV_RANK_MISS_FAIL}곳 이상 실패)", warn=bool(rank_miss))

    # 7. 필수 종목의 새 칸 (data.json · corp.json) — 위 DATA_NEW_MUST · CORP_NEW_MUST · CORP_MIRROR · CORP_NEW_MUST_AMT 설명
    cby = {c.get("t"): c for c in comps}
    miss, held = [], []
    pm = px_bad_must(data, comps)
    for t in must_kr:
        s, c = by.get(t) or {}, cby.get(t) or {}
        # Jack 2026-11-14 저녁: 과거 주가 기록 오류로 맞게 비운(px_bad_must) 필수 종목이 하나뿐이면 그 종목의 비운 칸(betaSE · betaN)은 경고로 넘겨요
        excuse = pm.get(t, set()) if len(pm) < PX_BAD_MUST_FAIL else set()
        held += [f"{t}.{k}" for k in DATA_NEW_MUST if s.get(k) is None and k in excuse]
        miss += [f"{t}.{k}" for k in DATA_NEW_MUST if s.get(k) is None and k not in excuse]
        miss += [f"corp {t}.{k}" for k in CORP_NEW_MUST if c.get(k) is None]
        miss += [f"corp {t}.{k}≠data" for k in CORP_MIRROR if c.get(k) != s.get(k)]   # 없으면 둘 다 없어야 해요
        if in_div_rank(s):
            miss += [f"corp {t}.{k}" for k in CORP_NEW_MUST_AMT if c.get(k) is None]
    rep.add("필수 종목 새 칸 (배당 분할 확인·베타 표준오차·재무 경고 검사)", not miss,
            ("모두 있음" if not miss else "없음: " + ",".join(miss[:6]) + ("…" if len(miss) > 6 else ""))
            + (f" · 과거 주가 기록 오류로 비운 칸 (경고): {','.join(held)}" if held else ""),
            "data " + "·".join(DATA_NEW_MUST) + " · corp " + "·".join(CORP_NEW_MUST) + " · corp 배당 칸 = data · "
            + "·".join(CORP_NEW_MUST_AMT) + " ('필수 종목 배당 순위'에서 빠진 종목은 총액·주당순이익 빼고 · 과거 주가 기록 오류로 맞게 비운 필수 종목 "
            f"하나의 {'·'.join(DATA_NEW_MUST)} 는 경고, {PX_BAD_MUST_FAIL}곳 이상이면 실패 — Jack 2026-11-14)", warn=bool(held))

    # 8. 베타 표준오차: 베타가 있는 종목은 모두 (SE > 0, 250 ≤ n ≤ 800), 회사 주식의 중앙값이 그럴듯한 범위,
    #    흔들리는 베타(SE > 0.5 — 가격 이력이 깨진 종목)는 2% 이하. 종목 하나가 발행 전체를 막지 않게 상한은 비율로 봐요
    bad, ses = [], []
    for s in kr + us:
        b, se, n = num(s.get("beta")), s.get("betaSE"), s.get("betaN")
        if b is None:
            if se is not None or n is not None:
                bad.append(f"{s['t']} 베타 없이 SE")
            continue
        if not _isnum(se) or not se > 0 or not isinstance(n, int) or isinstance(n, bool) or not BETA_N[0] <= n <= BETA_N[1]:
            bad.append(f"{s['t']} SE {s.get('betaSE')} n {n}")
        elif s.get("etf") is not True:
            ses.append(se)
    med = sorted(ses)[len(ses) // 2] if ses else None
    wild = 100.0 * sum(1 for x in ses if x > BETA_SE_WILD) / len(ses) if ses else 0.0
    ok = not bad and med is not None and BETA_SE_MED[0] <= med <= BETA_SE_MED[1] and wild <= BETA_SE_WILD_MAX
    rep.add("베타 표준오차 (betaSE·betaN)", ok,
            f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else "")
            + (f" · 회사 중앙값 {med:.3f} · SE > {BETA_SE_WILD:g} {wild:.1f}%" if med is not None else " · 값 없음"),
            f"SE > 0 · n {BETA_N[0]}~{BETA_N[1]} · 중앙값 {BETA_SE_MED[0]:g}~{BETA_SE_MED[1]:g} · SE > {BETA_SE_WILD:g} 는 "
            f"{BETA_SE_WILD_MAX:g}% 이하")

    # 9. 재무 경고 검사 기록: 모든 기업에 flRan, 켜진 경고는 실제로 돌린 검사여야 해요
    bad = []
    for c in comps:
        ran, na, fl = c.get("flRan"), c.get("flNa", []), c.get("fl") or {}
        if not isinstance(ran, list) or not isinstance(na, list) or not set(ran) | set(na) <= set(FL_KEYS) \
                or len(set(ran)) != len(ran) or set(ran) & set(na) or not set(fl) <= set(ran):
            bad.append(c.get("t"))
    rep.add("재무 경고 검사 기록 (flRan, 국내 기업 모두)", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else ""),
            f"0 ({'·'.join(FL_KEYS)} 중 · 켜진 경고는 flRan 안)")

    # 10. 새 금액 칸 모양: 숫자 3개 · 총액은 0 이상 · 해외 기업(9…)은 총액·주당순이익을 싣지 않고 배당은 0 또는 빈 칸
    bad = []
    for c in comps:
        for k in ("cash3", "eps3r", "epsNi3"):
            if k in c and _nums3(c[k]) is None:
                bad.append(f"{c.get('t')}.{k}")
        if any(x is not None and x < 0 for x in _nums3(c.get("cash3")) or []):
            bad.append(f"{c.get('t')}.cash3 음수")
        if "epsB" in c and c["epsB"] not in ("연결", "별도"):
            bad.append(f"{c.get('t')}.epsB")
        if is_foreign(c.get("t")) and any(k in c for k in ("cash3", "eps3r", "epsNi3", "epsB")):
            bad.append(f"{c.get('t')} 해외 기업 금액")
    for s in kr:
        if is_foreign(s.get("t")) and (any(x not in (None, 0) for x in _nums3(s.get("dps3a")) or [])
                                       or s.get("dyt") not in (None, 0)):
            bad.append(f"{s['t']} 해외 기업 배당")
    rep.add("새 금액 칸 모양 (총액·주당순이익·해외 기업)", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else ""), "0")

    # 11. divCheck 집계가 종목과 맞음 (이 칸이 낡거나 다른 실행 것이면 잡아요)
    got = {k: sum(1 for s in com if s.get("divSt") == k) for k in DIV_STATUS}
    got.update(pref=sum(1 for s in kr if is_pref(s.get("t"))), noDps=sum(1 for s in com if not s.get("divSt")),
               payers=sum(1 for s in com if s.get("divSt") and ((_nums3(s.get("dps3")) or [None])[0] or 0) > 0),
               dyt=sum(1 for s in kr if num(s.get("dyt")) is not None))
    off = [f"{k} {dc.get(k)}≠{v}" for k, v in got.items() if dc.get(k) != v]
    rep.add("divCheck 집계 = 종목 수", not off, "맞음" if not off else " · ".join(off[:4]), "같아야 함")


def _first(v):
    return num(v[0]) if isinstance(v, list) and v else None


def _sign(x):
    return (x > 0) - (x < 0)


def is_fin_co(s, c):
    """금융회사인지 (매출 줄이 재무제표에 없을 수 있어요): 업종 그룹이 있으면 그것으로, 없으면 corp.json 업종으로. (파이프라인과 따로)"""
    ind = (s or {}).get("ind")
    return ind in FIN_INDS if ind else (c or {}).get("s") in CORP_FIN_SECS


def check_v191f(rep, data, corp, kr, by, comps, pdata):
    """v19.1f 새 줄: 손익 줄 채움 · 필수 종목 손익 3줄 · 재무제표는 있는데 손익 줄이 없는 회사 · EPS 기준(지배주주 몫)과 영수증."""
    ic = data.get("incCheck")
    if not isinstance(ic, dict):
        had = isinstance((pdata or {}).get("incCheck"), dict)
        rep.add("손익 줄 검사 기록 (incCheck)", not had,
                "없음 — 직전 발행본에는 있었어요" if had else "없음 (v19.1f 전 형식이라 새 검사를 건너뛰어요)",
                "있어야 함 (v19.1f 전 데이터만 경고)", warn=not had)
        return
    rep.add("손익 줄 검사 기록 (incCheck)", ic.get("v") == 1, f"v{ic.get('v')}", "v1")
    corp_basis = (corp or {}).get("epsBasis")
    rep.add("EPS 기준 표시 (epsBasis = owners)", data.get("epsBasis") == "owners" and corp_basis == "owners",
            f"data {data.get('epsBasis')} · corp {corp_basis}", "둘 다 owners (재읽기가 돈 발행본 — 앱의 '고치는 중' 줄이 이걸 봐요)")
    cby = {c.get("t"): c for c in comps}
    must_kr = [t for t in MUST if (by.get(t) or {}).get("cls") == "kr" and not is_foreign(t)]

    # 1. 시가총액 상위 200 (보통주 · 해외 기업과 펀드 빼고 · fy 있는 회사)의 최근 사업보고서(fy) 매출(금융회사 빼고) · 영업이익 · 순이익 채움
    pool = [s for s in kr if not is_pref(s.get("t")) and not is_foreign(s.get("t")) and not s.get("etf") and not s.get("fund")
            and s.get("t") not in KR_FUND_SET and isinstance((cby.get(s.get("t")) or {}).get("fy"), int)]
    top = sorted(pool, key=lambda s: -(num(s.get("cap")) or 0))[:INC_TOP_N]
    parts, miss_all, worst = [], [], 100.0
    for k, ko in (("rev", "매출"), ("op", "영업이익"), ("ni", "순이익")):
        base = [s for s in top if not (k == "rev" and is_fin_co(s, cby.get(s["t"])))]
        miss = [s for s in base if _first(cby[s["t"]].get(k)) is None]
        share = 100.0 * (len(base) - len(miss)) / len(base) if base else 0.0
        worst = min(worst, share)
        parts.append(f"{ko} {floor_1(share)}% ({len(base) - len(miss)}/{len(base)})")
        miss_all += [f"{s['t']} {s.get('nk', '')} {ko}" for s in miss]
    floor = INC_TOP_FLOOR
    rep.add(f"국내 손익 줄 채움 — 시총 상위 {INC_TOP_N} (매출은 금융회사 빼고)", bool(top) and (floor is None or worst >= floor),
            " · ".join(parts),
            (f"{floor:g}% 미만 실패 · 100% 아니면 경고" if floor is not None
             else f"100% 아니면 경고 (실패 기준 {INC_TOP_FLOOR_APPROVED:g}% 는 Jack 승인 · 4월 확인 조건 · 4월 데이터 없음 → Jack 이 정할 때까지 꺼 둠)"),
            warn=worst < 100.0)
    if miss_all:
        rep.detail(f"시총 상위 {INC_TOP_N} 중 최근 사업보고서 손익 줄이 빈 회사", miss_all)

    # 2. 필수 종목은 손익 3줄 (금융회사는 매출 빼고)
    bad = []
    for t in must_kr:
        c = cby.get(t) or {}
        for k, ko in (("rev", "매출"), ("op", "영업이익"), ("ni", "순이익")):
            if k == "rev" and is_fin_co(by.get(t), c):
                continue
            if _first(c.get(k)) is None:
                bad.append(f"{t} {by[t].get('nk', '')} {ko}")
    rep.add("필수 종목 손익 3줄 (매출·영업이익·순이익)", not bad, "모두 있음" if not bad else "없음: " + ", ".join(bad),
            ",".join(must_kr) + " (금융회사는 매출 빼고)")

    # 3. 재무제표(자본·부채)는 있는데 매출·영업이익·순이익이 모두 빈 회사 — 경고 (이름과 함께)
    noinc = [f"{c.get('t')} {c.get('nk', '')}" for c in comps if not is_foreign(c.get("t")) and isinstance(c.get("fy"), int)
             and (num(c.get("eq")) is not None or num(c.get("debt")) is not None)
             and all(_first(c.get(k)) is None for k in ("rev", "op", "ni"))]
    rep.add("재무제표는 있는데 손익 줄을 하나도 못 읽은 회사", True, f"{len(noinc)}곳" + (f": {', '.join(noinc[:6])}…" if len(noinc) > 6
            else f": {', '.join(noinc)}" if noinc else ""), "0 (있으면 경고)", warn=bool(noinc))
    if noinc:
        rep.detail("재무제표는 있는데 손익 줄을 못 읽은 회사", noinc)

    # 4. 영수증 모양: epsIn · bpsIn · nio3 · incNa. 해외 기업(9…)은 금액 영수증을 싣지 않아요
    bad = []
    for c in comps:
        t = c.get("t")
        e, b = c.get("epsIn"), c.get("bpsIn")
        if is_foreign(t) and any(k in c for k in ("epsIn", "bpsIn", "nio3")):
            bad.append(f"{t} 해외 기업 금액")
        if e is None and not is_foreign(t) and num(c.get("eps")) is not None:
            bad.append(f"{t} EPS 영수증 없음")                     # 국내 EPS 는 모두 DART 지배주주 몫 계산이에요 (pykrx 값 안 씀)
        if b is None and not is_foreign(t) and num(c.get("bps")) is not None:
            bad.append(f"{t} BPS 영수증 없음")
        if e is not None:
            if not (isinstance(e, dict) and _isnum(e.get("ni")) and e.get("b") in EPS_B and e.get("p") in EPS_P
                    and isinstance(e.get("sh"), int) and e["sh"] > 0 and _isnum(c.get("eps"))):
                bad.append(f"{t}.epsIn")
            elif "nci" in e and not (e["nci"] is True and e.get("b") == "t" and e.get("how") == "total"):   # (2026-11-08, 더하기만): 소수주주가 있는 '전체' 회사 표시
                bad.append(f"{t}.epsIn.nci")
            elif abs(c["eps"] - e["ni"] * 1e8 / e["sh"]) > 0.5 + 1e-6 * abs(c["eps"]):
                bad.append(f"{t} eps ≠ ni ÷ 주식 수")
        if b is not None:
            if not (isinstance(b, dict) and _isnum(b.get("eq")) and b["eq"] > 0 and b.get("b") in EPS_B
                    and isinstance(b.get("sh"), int) and b["sh"] > 0 and _isnum(c.get("bps"))):
                bad.append(f"{t}.bpsIn")
            elif b.get("p") not in EPS_P:      # v19.1f (리뷰 2026-11-08, 더하기만): 자본의 시점 — ttm 최신 분기 · fy 사업보고서
                bad.append(f"{t}.bpsIn.p")
            elif abs(c["bps"] - b["eq"] * 1e8 / b["sh"]) > 0.5 + 1e-6 * abs(c["bps"]):
                bad.append(f"{t} bps ≠ 자본 ÷ 주식 수")
        if "nio3" in c and _nums3(c["nio3"]) is None:
            bad.append(f"{t}.nio3")
        if "nio3Hyb" in c and (_nums3(c["nio3Hyb"]) is None or "nio3" not in c):   # 리뷰 3: 신종자본증권 분배를 뺀 nio3 의 영수증
            bad.append(f"{t}.nio3Hyb")
        if "incNa" in c and (c["incNa"] != ["rev"] or _first(c.get("rev")) is not None):
            bad.append(f"{t}.incNa")
        if "stmtCur" in c:                 # v19.1f (리뷰 · Jack 2026-11-08, 더하기만): 원화가 아닌 재무제표는 금액이 모두 빈 칸
            bad += stmt_cur_problems(c, by.get(t))
    rep.add("EPS·BPS 영수증 모양 (epsIn·bpsIn·nio3·incNa·stmtCur)", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else ""),
            "0 (국내 EPS·BPS 는 모두 영수증 · eps = 순이익 ÷ 주식 수 · bps = 자본 ÷ 주식 수 · 해외 기업과 원화가 아닌 재무제표(stmtCur)는 "
            "금액 없음)")

    # 4b. 이자보상배율 경고 수와 쓴 이자 (경고만 — 실패하지 않아요): 경고 비율이 ICR_WARN_SHARE 를 넘으면 이자를 잘못 읽은 날일 수 있어요
    #     (2026-11-07: 금융비용을 이자로 읽어 505곳이 경고였어요)
    ran = [c for c in comps if "icr" in (c.get("flRan") or [])]
    warn_n = sum(1 for c in ran if "icr" in (c.get("fl") or {}))
    src = {k: sum(1 for c in ran if (c.get("flSrc") or {}).get("icr") == k) for k in ("is", "cf")}
    why = {k: sum(1 for c in comps if (c.get("flWhy") or {}).get("icr") == k) for k in ("ie", "op", "neg", "off")}
    int0 = sum(1 for c in ran if (c.get("flSrc") or {}).get("int0") is True)   # v19.1f (Jack 2026-11-08): 낸 이자 0 — 경고 없음
    share = 100.0 * warn_n / len(ran) if ran else 0.0
    rep.add("이자보상배율 경고 수 · 쓴 이자 (경고만)", True,
            f"경고 {warn_n:,} / 돌린 {len(ran):,} ({share:.1f}%) · 이자비용 {src['is']:,} · 이자 지급액 {src['cf']:,} · 못 돌린 이유 "
            + " ".join(f"{k} {v:,}" for k, v in why.items()) + f" · 낸 이자 0 {int0:,}",
            f"경고 비율 {ICR_WARN_SHARE:g}% 넘으면 경고", warn=share > ICR_WARN_SHARE)

    # 5. 필수 종목 EPS: 지배주주(또는 별도) 순이익으로, 부호가 그 순이익과 같고, 사업보고서 한 해 기준이면 회사가 낸 주당순이익과도 부호가 같음
    bad = []
    for t in must_kr:
        s, c = by.get(t) or {}, cby.get(t) or {}
        e, eps = c.get("epsIn"), num(c.get("eps"))
        if eps is None or not isinstance(e, dict) or not _isnum(e.get("ni")):
            bad.append(f"{t} EPS·영수증 없음")
            continue
        if e.get("b") not in ("o", "s"):
            bad.append(f"{t} 전체 순이익(지배주주 아님)")
        if _sign(eps) != _sign(e["ni"]):
            bad.append(f"{t} 부호 다름 (EPS {eps:,.0f} · 순이익 {e['ni']:,.1f}억)")
        r0 = _first(c.get("eps3r"))
        if e.get("p") == "fy" and r0 is not None and _sign(r0) != _sign(eps):
            bad.append(f"{t} 회사 발표 EPS({r0:,.0f})와 부호 다름")
        if num(s.get("eps")) != eps:
            bad.append(f"{t} data.json eps ≠ corp.json")
    rep.add("필수 종목 EPS = 지배주주 순이익 (부호 같음)", not bad, "모두 맞음" if not bad else " · ".join(bad[:4]),
            ",".join(must_kr) + " (epsIn.b o·s · 부호 = 순이익 · 연간이면 회사 발표 EPS 와도)")

    # 6. EPS 기준 경고: 시총 상위 200 중 연결인데 전체 순이익(b t) · TTM(bq) 표시인데 사업보고서 한 해(p fy)
    tops = {s["t"] for s in top}
    tb = [f"{c['t']} {c.get('nk', '')}" for c in comps if c.get("t") in tops and (c.get("epsIn") or {}).get("b") == "t"]
    fq = [f"{c['t']} {c.get('nk', '')}" for c in comps if c.get("bq") and (c.get("epsIn") or {}).get("p") == "fy"]
    rep.add("EPS 기준이 다른 회사 (상위 200 연결 전체 순이익 · TTM 표시인데 연간)", True,
            f"전체 순이익 {len(tb)} · TTM 표시인데 연간 {len(fq)}", "0 · 0 (있으면 경고)", warn=bool(tb or fq))
    if tb or fq:
        rep.detail("EPS 기준이 다른 회사", [f"{x} 전체 순이익" for x in tb] + [f"{x} 연간" for x in fq])

    # 7. incCheck 집계 = corp.json 영수증 수 (이 칸이 낡거나 다른 실행 것이면 잡아요)
    eb = {k: sum(1 for c in comps if (c.get("epsIn") or {}).get("b") == k) for k in EPS_B}
    ep = {k: sum(1 for c in comps if (c.get("epsIn") or {}).get("p") == k) for k in EPS_P}
    off = [f"epsB.{k} {(ic.get('epsB') or {}).get(k)}≠{v}" for k, v in eb.items() if (ic.get("epsB") or {}).get(k) != v]
    off += [f"epsP.{k} {(ic.get('epsP') or {}).get(k)}≠{v}" for k, v in ep.items() if (ic.get("epsP") or {}).get(k) != v]
    rep.add("incCheck 집계 = corp.json 영수증 수", not off, "맞음" if not off else " · ".join(off[:4]), "같아야 함")
    check_v191f_review(rep, data, corp, kr, by, comps)


def _stmt_marked(c):
    """원화가 아닌 재무제표 표시가 있는지 — 앱과 같은 규칙 (src/repair.js stmtNotWon: stmtCur 가 null 이 아니고 KRW 가 아니면).
    'XXX' 처럼 읽을 수 없는 통화도 표시예요."""
    return isinstance(c, dict) and c.get("stmtCur") is not None and c.get("stmtCur") != "KRW"


STMT_AMOUNT_FIELDS = FOREIGN_BLANK_LISTS + FOREIGN_BLANK_CORP + FOREIGN_BLANK + STMT_AMT_KEYS   # 표시가 없으면 원으로 읽히는 금액 칸


def check_stmt_marks(rep, comps, prev):
    """2026-11-12 (Jack, 더하기만): 직전 발행에서 원화가 아닌 재무제표 표시(stmtCur)가 있던 회사가 오늘도 목록에 있는데 표시가 사라졌는지.
    실패: (1) 국내 회사(9… 가 아닌)가 직전 발행에는 표시가 있었는데 오늘 표시가 사라졌고 금액 칸이 차 있으면 — 달러 금액이 원으로 나가는 바로
    그 경우예요 (Jack, 2026-11-12: 이름 목록이 아니라 직전 발행과 비교해서). 회사가 정말 원화로 바꿨다면 Jack 의 yes 로 예외를 한 줄 더해요.
    (2) 오늘도 목록에 있는 회사가 STMT_MARK_MIN 곳 이상이고 그 절반 넘게 사라지면 (DART 통화 칸을 못 읽은 날). (3) 직전 corp.json 이 없거나
    못 읽었으면 (비교할 수 없어요). 그 밖에 하나라도 사라지면 경고 (금액이 비어 있는 회사 · 9… 외국 기업은 금액을 코드 규칙으로 비워요).
    경고는 그날 한 번만 떠요: 경고로 발행되면 다음 날 비교 대상(직전 발행)에서 그 회사의 표시가 이미 빠져 있어요 (docs/RUNBOOK.md)."""
    name = "원화가 아닌 재무제표 표시가 직전 발행보다 사라지지 않음 (stmtCur)"
    rule = ("국내 회사가 표시를 잃고 금액이 차 있으면 실패 · "
            f"오늘도 목록에 있는 회사가 {STMT_MARK_MIN}곳 이상이고 그 절반 넘게 사라지면 실패 (DART 통화 칸을 못 읽은 날) · "
            "하나라도 사라지면 경고 · 직전 corp.json 이 없으면 실패")
    if prev is None:
        rep.skip(name, "직전 발행본이 없어요 ('직전 발행본 읽기' 줄이 실패해요)")
        return
    if prev.get("corpError"):
        rep.add(name, False, f"직전 corp.json 을 읽지 못했어요: {prev['corpError'][:160]}", rule)
        return
    pcorp = prev.get("corp")
    if not isinstance(pcorp, dict) or not isinstance(pcorp.get("companies"), list):
        rep.add(name, False, "직전 corp.json 이 없거나 회사 목록이 없어요 (비교할 수 없어요)", rule)
        return
    rows = {}                                       # 코드 → 오늘의 줄들 (같은 코드가 두 번이면 둘 다: 예전 앱은 앞의 것, 2.0 은 뒤의 것을 써요)
    for c in comps:
        if isinstance(c, dict) and c.get("t") is not None:
            rows.setdefault(c.get("t"), []).append(c)
    marked = list(dict.fromkeys(c.get("t") for c in pcorp["companies"] if _stmt_marked(c) and c.get("t") is not None))
    still = [t for t in marked if t in rows]
    lost = [t for t in still if not all(_stmt_marked(c) for c in rows[t])]   # 한 줄이라도 표시가 없으면 사라진 거예요
    gone_kr = [t for t in marked if t not in rows and not is_foreign(t)]     # 국내 회사가 오늘 목록에 없음: 다음 날 다시 확인
    gone_many = len(marked) >= STMT_MARK_MIN and 2 * len(still) < len(marked)   # 표시된 회사가 한꺼번에 목록에서 빠졌어요

    def has_amt(t):
        return any(_has_amount(c.get(k)) for c in rows[t] for k in STMT_AMOUNT_FIELDS)

    def label(t):
        nk = next((c.get("nk") for c in rows[t] if c.get("nk")), None)
        return " ".join(x for x in (t, nk, "(금액 있음)" if has_amt(t) else None) if x)
    # 해로운 것: 금액이 찬 국내 회사(9… 가 아닌) — 외국 기업은 코드 규칙으로 금액을 비우는 줄이 따로 있어요. 맨 앞에 적어요
    harmful = [t for t in lost if not is_foreign(t) and has_amt(t) and t not in STMT_WON_SWITCH]
    fail = bool(harmful) or (len(still) >= STMT_MARK_MIN and 2 * len(lost) > len(still))
    lost.sort(key=lambda t: (is_foreign(t), not has_amt(t)))
    if lost:
        rep.detail("표시가 사라진 회사 (stmtCur)", [label(t) for t in lost])
    value = f"직전 {len(marked)}곳 · 오늘도 목록에 {len(still)}곳 · 표시가 사라짐 {len(lost)}"
    if harmful:
        value += f" (그중 금액이 찬 국내 회사 {len(harmful)})"
    if lost:
        value += f": {', '.join(label(t) for t in lost[:4])}{' …' if len(lost) > 4 else ''}"
    elif gone_many:
        value += " (직전에 표시된 회사의 절반 넘게 오늘 목록에 없어요)"
    if gone_kr:
        value += f" · 오늘 목록에 없는 국내 회사: {', '.join(gone_kr[:4])}{' …' if len(gone_kr) > 4 else ''} (다음 발행에서 다시 확인)"
    rep.add(name, not fail, value, rule, warn=(bool(lost) or gone_many or bool(gone_kr)) and not fail)


def _has_amount(v):
    """금액 칸이 차 있는지: 목록이면 숫자가 하나라도, dict(영수증)면 있으면, 아니면 숫자면."""
    if isinstance(v, list):
        return any(num(x) is not None for x in v)
    return isinstance(v, dict) or num(v) is not None


def stmt_cur_problems(c, s):
    """stmtCur 가 있는 corp.json 회사(c)와 data.json 종목(s)의 문제 목록: 통화 코드가 세 글자 대문자이고 KRW 가 아니어야 하고, 금액
    (매출·이익·자본 · EV 배수 · 영수증 · PER·PBR·EPS·BPS · 가치 점수)이 두 파일 모두 비어 있고 DCF 입력이 꺼져 있어야 해요."""
    t, sc = c.get("t"), c.get("stmtCur")
    bad = []
    if not (isinstance(sc, str) and re.fullmatch(r"[A-Z]{3}", sc) and sc != "KRW"):
        bad.append(f"{t}.stmtCur {sc!r}")
    bad += [f"{t} corp.{k}" for k in FOREIGN_BLANK + FOREIGN_BLANK_CORP + FOREIGN_BLANK_LISTS + STMT_AMT_KEYS if _has_amount(c.get(k))]
    bad += [f"{t} data.{k}" for k in FOREIGN_BLANK if _has_amount((s or {}).get(k))]
    if c.get("dcfReady") is not False:
        bad.append(f"{t} corp.dcfReady")
    bad += [f"{t} corp.{k}" for k in ("fl", "flSrc", "flWhy") if k in c]   # 리뷰 3: 다른 통화로 만든 재무 신호도 없어야 해요
    if "flRan" in c and c["flRan"] != []:          # (2026-11-09) 돌린 검사 없음 = flRan [] (재무 경고 검사 기록 줄이 목록을 바라요)
        bad.append(f"{t} corp.flRan")
    bad += [f"{t} {w}.{k}" for w, src in (("corp", c), ("data", s or {})) for k in ("roe", "qz") if _has_amount(src.get(k))]   # 리뷰 4
    return bad


def check_v191f_review(rep, data, corp, kr, by, comps):
    """v19.1f 리뷰 (2026-11-08) 새 줄 — 더하기만: EPS 주주 몫 비율 · 두 파일 같은 값 · PER·PBR = 종가 ÷ 영수증 · 주식 수 같음 ·
    원화가 아닌 재무제표 · PER·PBR 너무 큼 · 연간 EPS 와 재무제표 주당이익 · ROE 영수증."""
    cby = {c.get("t"): c for c in comps}
    kr_c = [c for c in comps if not is_foreign(c.get("t"))]

    # 8. 주주 몫 EPS 비율을 corp.json 에서 다시 세요 (epsBasis 표시만 믿지 않게)
    eb = [(c.get("epsIn") or {}).get("b") for c in comps if isinstance(c.get("epsIn"), dict)]
    share = 100.0 * sum(1 for b in eb if b in ("o", "s")) / len(eb) if eb else 0.0
    rep.add("EPS 주주 몫 비율 (corp.json 에서 다시 셈 · o+s)", bool(eb) and share >= EPS_OWNERS_MIN,
            f"{floor_1(share)}% ({sum(1 for b in eb if b in ('o', 's')):,}/{len(eb):,})", f"{EPS_OWNERS_MIN:g}% 이상")

    # 9. data.json 과 corp.json 의 EPS·BPS·PER·PBR·ROE 가 같아요 (국내 모두)
    bad = []
    for c in comps:
        s = by.get(c.get("t"))
        if not s:
            continue
        bad += [f"{c['t']}.{k}" for k in ("eps", "bps", "per", "pbr", "roe") if num(s.get(k)) != num(c.get(k))]
    rep.add("국내 EPS·BPS·PER·PBR·ROE: data.json = corp.json", not bad, f"어긋남 {len(bad)}" + (f" (예: {', '.join(bad[:3])})" if bad else ""),
            "0")

    # 10. PER = 종가 ÷ EPS · PBR = 종가 ÷ BPS (영수증의 순이익·자본 ÷ 주식 수로 다시 나눠요) · EPS 가 0 이하면 PER 없음 · 두 영수증의 주식 수 같음
    bad, sh_bad = [], []
    for c in kr_c:
        t, price = c.get("t"), num(c.get("price"))
        e, b = c.get("epsIn"), c.get("bpsIn")
        per, pbr = num(c.get("per")), num(c.get("pbr"))
        e_ok = isinstance(e, dict) and _isnum(e.get("ni")) and isinstance(e.get("sh"), int) and e["sh"] > 0
        b_ok = isinstance(b, dict) and _isnum(b.get("eq")) and isinstance(b.get("sh"), int) and b["sh"] > 0
        if per is not None:
            ex = e["ni"] * 1e8 / e["sh"] if e_ok else None
            if ex is None or ex <= 0 or price is None:
                bad.append(f"{t} PER 인데 EPS 영수증이 없거나 0 이하")
            elif abs(per - price / ex) > PER_TOL + 1e-6 * per:
                bad.append(f"{t} PER {per:,.1f} ≠ {price / ex:,.1f}")
        elif e_ok and e["ni"] > 0 and price:
            bad.append(f"{t} EPS 가 0 보다 큰데 PER 없음")
        if pbr is not None:
            bx = b["eq"] * 1e8 / b["sh"] if b_ok else None
            if bx is None or bx <= 0 or price is None:
                bad.append(f"{t} PBR 인데 BPS 영수증이 없거나 0 이하")
            elif abs(pbr - price / bx) > PBR_TOL + 1e-6 * pbr:
                bad.append(f"{t} PBR {pbr:,.2f} ≠ {price / bx:,.2f}")
        if e_ok and b_ok and e["sh"] != b["sh"]:
            sh_bad.append(f"{t} {e['sh']:,}≠{b['sh']:,}")
    rep.add("PER = 종가 ÷ EPS · PBR = 종가 ÷ BPS (영수증으로)", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else ""),
            f"0 (반올림 PER ±{PER_TOL:g} · PBR ±{PBR_TOL:g})")
    rep.add("EPS·BPS 영수증의 주식 수가 같음 (epsIn.sh = bpsIn.sh)", not sh_bad,
            f"어긋남 {len(sh_bad)}" + (f" (예: {sh_bad[0]})" if sh_bad else ""), "0")

    # 11. 원화가 아닌 재무제표로 낸 국내 회사 (stmtCur) — 이름만 (금액이 남았는지는 '영수증 모양' 줄이 실패로 봐요)
    cur = [f"{c.get('t')} {c.get('nk', '')}({c.get('stmtCur')})" for c in comps if "stmtCur" in c]
    rep.add("원화가 아닌 재무제표로 낸 회사 (stmtCur · 금액은 비움)", True, f"{len(cur)}곳" + (f": {', '.join(cur[:6])}" if cur else ""),
            "알림 (금액이 남으면 '영수증 모양' 줄이 실패)")

    # 12. PBR 이 너무 큰 국내 회사 (경고만 — 단위·통화가 틀렸을 수 있어요)
    big = []
    for s in kr:
        if is_foreign(s.get("t")):
            continue
        pbr = num(s.get("pbr"))
        if pbr is not None and pbr > PBR_WARN:
            big.append(f"{s['t']} {s.get('nk', '')} PBR {pbr:,.2f}")
    rep.add(f"PBR {PBR_WARN:g} 넘는 국내 회사 (경고만)", True, f"{len(big)}곳" + (f": {', '.join(big[:4])}" if big else ""),
            "0 (있으면 경고 · 단위나 통화를 확인)", warn=bool(big))
    if big:
        rep.detail(f"PBR {PBR_WARN:g} 넘는 국내 회사", big)

    # 13. 사업보고서 한 해 EPS (epsFy · 오늘 주식 수) 와 재무제표의 기본주당이익 (epsRep) — 부호가 다르거나 0.67~1.5배 밖이면 경고
    lo, hi = EPS_REP_BAND
    n_cmp, off = 0, []
    for c in kr_c:
        a, r = c.get("epsFy"), c.get("epsRep")
        if not (_isnum(a) and _isnum(r)):
            continue
        n_cmp += 1
        if _sign(a) != _sign(r) or (r != 0 and not lo <= a / r <= hi):
            off.append(f"{c['t']} {c.get('nk', '')} 우리 {a:,.0f} · 재무제표 {r:,.0f}")
    rep.add(f"연간 EPS 와 재무제표 기본주당이익 (부호 · {lo:g}~{hi:g}배 · 경고만)", True, f"다름 {len(off)} / 견준 {n_cmp:,}"
            + (f" (예: {off[0]})" if off else ""), "0 (있으면 경고 · 주식 수 변화·신종자본증권·지배주주 줄을 확인)", warn=bool(off))
    if off:
        rep.detail("연간 EPS 가 재무제표 기본주당이익과 다른 회사", off)

    # 14. ROE 영수증 (roeIn): 주주 몫 순이익 ÷ 주주 몫 자본 (사업보고서 한 해) — 모양과 값
    bad = []
    for c in kr_c:
        ri = c.get("roeIn")
        if ri is None:
            continue
        t = c.get("t")
        if not (isinstance(ri, dict) and _isnum(ri.get("ni")) and _isnum(ri.get("eq")) and ri["eq"] > 0 and ri.get("b") in ("o", "s")
                and ri.get("p") == "fy" and _isnum(c.get("roe"))):
            bad.append(f"{t}.roeIn")
        elif abs(c["roe"] - ri["ni"] / ri["eq"] * 100) > 0.05 + 1e-9 * abs(c["roe"]):
            bad.append(f"{t} roe ≠ 순이익 ÷ 자본")
    rep.add("ROE 영수증 (roeIn: 주주 몫 ÷ 주주 몫 자본 · 사업보고서)", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0]})" if bad else ""),
            "0")
    # 15. EPS 는 주주 몫(o·s)인데 ROE 영수증이 없는 곳 (ROE 는 예전처럼 전체 ÷ 전체 — 앱의 '고치는 중' 줄은 EPS 기준으로 사라져요) — 경고만
    gap = [f"{c['t']} {c.get('nk', '')}" for c in kr_c if (c.get("epsIn") or {}).get("b") in ("o", "s") and "roeIn" not in c
           and num(c.get("roe")) is not None]
    rep.add("EPS 는 주주 몫인데 ROE 는 예전 값인 회사 (경고만)", True, f"{len(gap)}곳" + (f": {', '.join(gap[:4])}" if gap else ""),
            "0 (있으면 경고)", warn=bool(gap))
    if gap:
        rep.detail("EPS 는 주주 몫인데 ROE 는 예전 값인 회사", gap)


def unit_problems(s, c):
    """공시 단위 확인에 걸린 회사의 문제 목록 (s: data.json 종목 · c: corp.json 회사, 없으면 None): unitChk 가 이유 목록(UNIT_WHY, 겹치지 않게)이고
    두 파일이 같아야 하고, 재무제표로 만든 숫자(UNIT_BLANK_DATA · UNIT_BLANK_CORP · 3개년 금액 · 최신 분기 bq)가 모두 비어 있고 DCF 입력이 꺼져
    있고, 재무 경고는 돌린 검사가 없어야(flRan []) 해요. 배당은 보지 않아요 (별도 배당 표라 남겨요)."""
    s = s or {}
    t = s.get("t") or (c or {}).get("t")
    bad = []
    for w, src in (("data", s), ("corp", c)):
        if src is None:
            continue
        u = src.get("unitChk")
        if not (isinstance(u, list) and u and all(x in UNIT_WHY for x in u) and len(set(u)) == len(u)):
            bad.append(f"{t} {w}.unitChk {u!r}")
    if c is None:
        bad.append(f"{t} corp.json 에 없음")
        c = {}
    elif s and s.get("unitChk") != c.get("unitChk"):
        bad.append(f"{t} unitChk data {s.get('unitChk')!r} ≠ corp {c.get('unitChk')!r}")
    bad += [f"{t} data.{k}" for k in UNIT_BLANK_DATA if _has_amount(s.get(k))]
    bad += [f"{t} corp.{k}" for k in UNIT_BLANK_DATA + UNIT_BLANK_CORP + UNIT_BLANK_LISTS if _has_amount(c.get(k))]
    if c.get("bq"):
        bad.append(f"{t} corp.bq")
    if c and c.get("dcfReady") is not False:
        bad.append(f"{t} corp.dcfReady")
    if c and c.get("flRan") != []:
        bad.append(f"{t} corp.flRan")
    return bad


def check_unit(rep, data, kr, by, comps, pdata=None):
    """공시 단위 확인 (2026-11-13 · 새 줄만): 걸린 회사(unitChk)는 숫자를 모두 비웠는지 (실패) · unitChk 없이 PBR 이 아주 낮은 국내 회사 (경고) ·
    리뷰 #118: 확인이 돌았는지 (unitChkCover — 직전 발행본에 있었는데 없으면 실패 · hit 가 unitChk 종목 수와 다르면 실패) · 걸린 회사가 직전
    발행본과 달라졌는지 (경고 — 새로 걸린 회사 · 풀린 회사를 이름과 함께). pdata: 직전 발행본 data.json (발행 모드에서만, 아니면 None)."""
    cby = {c.get("t"): c for c in comps}
    hit = [s for s in kr if "unitChk" in s]
    bad = []
    for s in hit:
        bad += unit_problems(s, cby.get(s.get("t")))
    for c in comps:                                  # corp.json 에만 표시가 있는 회사 (두 파일이 어긋남)
        if "unitChk" in c and "unitChk" not in (by.get(c.get("t")) or {}):
            bad.append(f"{c.get('t')} corp.json 에만 unitChk")
    names = [f"{s['t']} {s.get('nk', '')} ({'·'.join(map(str, s.get('unitChk') or []))})" for s in hit]
    # 리뷰 #116: 확인이 몇 곳을 어떤 방법으로 봤는지 (data.json unitChkCover) — 값 칸에만 (실패 기준은 그대로)
    cov = data.get("unitChkCover") if isinstance(data.get("unitChkCover"), dict) else None
    cov_txt = (f" · 본 회사 {cov.get('companies')} (자산=부채+자본 모두 봄 {cov.get('checked')} · 못 본 재무제표 있음 {cov.get('unchecked')} · "
               f"분기 비교 없음 {cov.get('noScale')} · 기본주당이익·자본금으로 봄 {cov.get('anchor')} · 지난해 칸으로 봄 {cov.get('flows')}"
               + (f" · 원화 아님(기준값 안 봄) {cov.get('notWon')}" if "notWon" in cov else "") + ")"
               if cov else " · 확인 범위 기록(unitChkCover) 없음")
    rep.add("공시 단위 확인 회사의 숫자 비움 (unitChk)", not bad,
            f"{len(hit)}곳 · 남은 칸 {len(bad)}" + (f" (예: {', '.join(bad[:3])})" if bad else "") + (f" — {', '.join(names[:4])}" if names else "")
            + cov_txt,
            "0 (unitChk 회사는 PER·PBR·EPS·BPS·ROE·부채비율·영업이익률·성장률·점수·3년 실적·자본·EV 배수·영수증·재무 경고 빈 칸 · 두 파일 같게)")
    if names:
        rep.detail("공시 단위 확인으로 숫자를 비운 회사", names)
    check_unit_ran(rep, data, hit, pdata)
    check_unit_moved(rep, hit, pdata)
    low, quiet = [], []
    for s in kr:
        if is_foreign(s.get("t")) or "unitChk" in s or num(s.get("pbr")) is None or num(s.get("pbr")) >= UNIT_PBR_LOOK:
            continue
        nm = f"{s['t']} {s.get('nk', '')} PBR {num(s.get('pbr')):.2f}"
        ck = PBR_LOW_CHECKED.get(s.get("t"))
        eq = num(((cby.get(s.get("t")) or {}).get("bpsIn") or {}).get("eq"))
        if ck and eq is not None and num(ck.get("eq")) and abs(eq / ck["eq"] - 1) <= PBR_LOW_BAND:
            quiet.append(f"{nm} (자본 {eq:,.1f}억 · 확인 {ck['date']} {ck['eq']:,.1f}억)")
        elif ck:
            low.append(f"{nm} (확인한 자본 {ck['eq']:,.1f}억 → 지금 " + (f"{eq:,.1f}억" if eq is not None else "없음") + ")")
        else:
            low.append(nm)
    rep.add(f"PBR {UNIT_PBR_LOOK:g} 미만 국내 회사 (unitChk 없음 · 경고만)", True,
            f"{len(low)}곳" + (f": {', '.join(low[:4])}" if low else "") + (f" · 확인된 회사 {len(quiet)}곳 조용히 넘김" if quiet else ""),
            f"0 (있으면 경고 · 공시의 단위를 사람이 확인 · 확인된 회사(PBR_LOW_CHECKED)는 자본이 ±{PBR_LOW_BAND:.0%} 안이면 조용히)", warn=bool(low))
    if low:
        rep.detail(f"PBR {UNIT_PBR_LOOK:g} 미만인데 공시 단위 확인을 통과한 국내 회사", low)
    if quiet:
        rep.detail(f"PBR {UNIT_PBR_LOOK:g} 미만 · 사람이 공시를 확인해 조용히 넘긴 회사 (PBR_LOW_CHECKED)", quiet)
    check_unit_fix(rep, kr, by, comps)
    lowp = [f"{s['t']} {s.get('nk', '')} PER {num(s.get('per')):.1f}" for s in kr
            if not is_foreign(s.get("t")) and "unitChk" not in s and num(s.get("per")) is not None and 0 <= num(s.get("per")) < UNIT_PER_LOOK]
    rep.add(f"PER {UNIT_PER_LOOK:g} 미만 국내 회사 (unitChk 없음 · 경고만)", True, f"{len(lowp)}곳" + (f": {', '.join(lowp[:4])}" if lowp else ""),
            "0 (있으면 경고 · 손익계산서의 단위를 사람이 확인)", warn=bool(lowp))
    if lowp:
        rep.detail(f"PER {UNIT_PER_LOOK:g} 미만인데 공시 단위 확인을 통과한 국내 회사", lowp)


def check_unit_ran(rep, data, hit, pdata):
    """리뷰 #118 S3: '확인이 돌지 않음'과 '확인했는데 걸린 회사 없음'을 나눠요 (새 실패 줄 둘 · Jack's yes, 2026-11-13).
    파이프라인(fetch_data.main)은 DART 가 꺼지거나 멈춰도, 캐시가 없어도, 야후가 멈춰도 unit_guard 를 늘 불러 unitChkCover 를 써요
    (DART 없이 돌면 companies 0 · hit 0). DART 치명 오류 · 국내 시세 실패는 실행 전체를 멈춰 파일이 나오지 않아요 (관문까지 오지 않아요).
    그래서 두 줄은 바깥 장애로는 실패하지 않고, 기록을 쓰는 코드가 빠졌거나 unit_guard 뒤에 종목이 바뀐 코드 문제에서만 실패해요."""
    cov = data.get("unitChkCover")
    had = isinstance((pdata or {}).get("unitChkCover"), dict)
    if not isinstance(cov, dict):
        rep.add("공시 단위 확인 기록 (unitChkCover)", not had,
                "없음 — 직전 발행본에는 있었어요 (확인이 돌지 않았어요)" if had else "없음 (2026-11-13 전 형식 · 직전 발행본에도 없어요)",
                "있어야 함 (그 전 형식만 경고)", warn=not had)
        return
    rep.add("공시 단위 확인 기록 (unitChkCover)", cov.get("v") == 1, f"v{cov.get('v')} · 본 회사 {cov.get('companies')}", "v1")
    h = cov.get("hit")
    ok = isinstance(h, int) and not isinstance(h, bool) and h == len(hit)
    rep.add("unitChkCover.hit = unitChk 종목 수", ok, f"기록 {h!r} · data.json {len(hit)}곳", "같아야 함 (다르면 확인 뒤에 종목이 바뀐 거예요)")


def check_unit_moved(rep, hit, pdata):
    """리뷰 #118 S1 (경고만): 걸린 회사(unitChk)가 직전 발행본과 다르면 이름과 함께 — 새로 걸린 회사(숫자가 새로 비어요) · 풀린 회사.
    통과(PASS) 줄은 아침 확인(09:13)에 가지 않아서, 새로 비운 회사를 사람이 알게 해요. 직전 발행본이 없으면(발행 모드가 아니거나 못 읽음)
    비교하지 않아요. Jack 2026-11-13 (Q5): 새로 걸린 회사가 UNIT_NEW_FLAGS_FAIL(20)곳 이상이면 따로 실패 줄 (풀린 회사는 세지 않아요 ·
    직전 발행본이 없으면 실패하지 않아요)."""
    name = "공시 단위 확인 회사 바뀜 (unitChk · 경고만)"
    many = f"공시 단위 확인에 새로 걸린 회사 수 ({UNIT_NEW_FLAGS_FAIL}곳 이상이면 실패)"
    if not isinstance(pdata, dict):
        rep.add(name, True, "직전 발행본 없음 (비교 안 함)", "0 (바뀌면 경고)")
        rep.add(many, True, "직전 발행본 없음 (비교 안 함)", f"{UNIT_NEW_FLAGS_FAIL}곳 미만")
        return
    before = {x.get("t"): x for x in (pdata.get("stocks") or []) if isinstance(x, dict) and "unitChk" in x}
    now = {x.get("t"): x for x in hit}
    new = [f"{t} {now[t].get('nk', '')}".strip() for t in sorted(set(now) - set(before), key=str)]
    gone = [f"{t} {before[t].get('nk', '')}".strip() for t in sorted(set(before) - set(now), key=str)]

    def few(xs):
        return (": " + ", ".join(xs[:UNIT_MOVE_SHOW]) + (f" 외 {len(xs) - UNIT_MOVE_SHOW}곳" if len(xs) > UNIT_MOVE_SHOW else "")) if xs else ""
    rep.add(name, True, f"새로 {len(new)}곳{few(new)} · 풀림 {len(gone)}곳{few(gone)}",
            "0 (바뀌면 경고 · 새로 걸린 회사는 숫자가 비어요 — 그 공시를 사람이 확인)", warn=bool(new or gone))
    rep.add(many, len(new) < UNIT_NEW_FLAGS_FAIL, f"새로 {len(new)}곳",
            f"{UNIT_NEW_FLAGS_FAIL}곳 미만 (Jack 2026-11-13 — 그 이상이면 우리 읽기가 깨졌을 수 있어요 · 실행 로그의 '!! 공시 단위:' 줄을 보세요)")
    if new:
        rep.detail("공시 단위 확인에 새로 걸린 회사 (숫자를 새로 비웠어요)", new)
    if gone:
        rep.detail("공시 단위 확인이 풀린 회사 (직전 발행본에는 걸려 있었어요)", gone)


KR_SERIES_SHOW = 10      # 값 칸에 적는 종목 수 (나머지는 수만 · 전체는 요약 목록에)


def _nonneg_int(x):
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def kr_series_problems(ks, px=None):
    """data.json krSeries 의 모양 문제 목록 (빈 목록 = 정상). 파이프라인(fetch_data.kr_series_check)이 쓰는 모양과 따로 적어요.
    px: pxDate (움직임 날짜는 그날이나 그 전이어야 해요)."""
    out = []
    if ks.get("v") != 1:
        out.append(f"v {ks.get('v')!r}")
    for k in ("days", "pinned", "pinStocks", "keptStocks", "bad"):
        if not _nonneg_int(ks.get(k)):
            out.append(f"{k} {ks.get(k)!r}")
    kept = ks.get("kept")
    if not isinstance(kept, dict) or set(kept) != {"basis", "far", "shr"} or not all(_nonneg_int(v) for v in kept.values()):
        out.append(f"kept {kept!r}"[:60])
    ref = ks.get("ref")
    if not isinstance(ref, dict) or set(ref) != {"breakStocks", "unknownStocks", "newStocks"} or not all(_nonneg_int(v) for v in ref.values()):
        out.append(f"ref {ref!r}"[:60])
    bs = ks.get("badStocks")
    if not isinstance(bs, list) or not all(isinstance(c, str) and c for c in bs):
        out.append("badStocks 목록 아님")
    elif _nonneg_int(ks.get("bad")) and (len(bs) > ks["bad"] or (ks["bad"] > 0) != bool(bs)):
        out.append(f"badStocks {len(bs)}종목 ↔ bad {ks['bad']}")
    jm = ks.get("jump")
    if not isinstance(jm, list):
        out.append("jump 목록 아님")
    else:
        for j in jm:
            ok = (isinstance(j, list) and len(j) == 4 and isinstance(j[0], str) and j[0] and is_day(j[1])
                  and num(j[2]) is not None and j[3] in KR_JUMP_WHY and (px is None or day(j[1]) <= px))
            if not ok:
                out.append(f"jump {str(j)[:40]}")
                break
    return out


def check_kr_series(rep, data, kr, pdata):
    """국내 시계열 점검 (2026-11-14 · Jack: "52주 숫자부터" · 새 줄만, 늦추는 줄 없음). 네이버 수정주가에 다른 기준의 공식 종가를 넣어
    에쎈테크 · 인지디스플레 · STX 들의 52주 최저 · 낙폭 · 변동성 · 베타가 틀렸어요 (PIN_PX_TOL 위 설명). 관문은 파일만 보니 파이프라인이
    krSeries 에 점검 결과를 실어요 (fetch_data.kr_series_check).
    실패: krSeries.bad (자기 점검 — 네이버 봉과 달라진 봉 중 허락된 고정이 아닌 수: 그날 공식 종가가 아니거나, 그날과 오늘 사이에 KRX 기준가가
    바뀌었거나, 확인 못 한 날인데 주식 수 · 값 차이가 기준 밖) 가 0 이 아니거나 모양이 틀리면. 바깥 출처의 잘못(네이버 · 목록 파일)으로는 생기지
    않고 (고치는 날이 줄 뿐 · 네이버의 같은 날짜 두 번 · 잘못된 값은 점검 전에 빼요) 우리 코드가 봉을 잘못 바꿨을 때만 생겨요 (Jack 2026-11-13: 한
    종목의 출처 문제가 모두의 발행을 막으면 안 돼요). 다만 우리 잘못이 모두 여기 걸리지는 않아요: 점검이 파이프라인의 규칙 · 기준가 연결을 다시 써서,
    나중 단계가 봉을 바꾸거나 고정이 규칙과 어긋나면 잡지만 기준가 연결 자체의 잘못은 시험(tests/test_kr_pin_basis.py)이 지켜요.
    krSeries 가 없으면 직전 발행본에 있었을 때만 실패 (그 전 형식은 경고).
    경고: 하루 움직임이 가격 제한폭 + 넥스트레이드 차이로 설명되지 않는 종목 (krSeries.jump) — 그 종목의 숫자에 그 움직임이 들어가요
    (대개 네이버가 고치지 않은 감자 · 거래정지 뒤 재개 · 하루만 튄 봉). pdata: 직전 발행본 data.json (발행 모드에서만, 아니면 None)."""
    name = "국내 시계열 공식 종가 고정 자기 점검 (krSeries.bad)"
    jname = "국내 시계열 하루 가격 제한폭 넘는 움직임 (경고만)"
    rule = (f"0 (네이버 수정주가와 달라진 봉은 모두 그날 공식 종가 · 그 뒤 KRX 기준가가 바뀌지 않음 · 기준가를 확인 못 한 날은 상장주식수가 "
            f"오늘과 {PIN_SHR_TOL:.0%} 안 · 네이버 봉과 {PIN_PX_TOL:.0%} 안)")
    jrule = (f"0 (있으면 경고 · 하루 ±{KR_DAY_LIMIT:g}% · 코넥스 ±{KONEX_DAY_LIMIT:g}% 와 넥스트레이드 차이 {PIN_PX_TOL:.0%} 로 설명되지 않는 움직임 — "
             "그 종목의 52주 · 변동성 · 베타 · 낙폭에 들어가요)")
    ks = data.get("krSeries")
    had = isinstance((pdata or {}).get("krSeries"), dict)
    if not isinstance(ks, dict):
        rep.add(name, not had, "없음 — 직전 발행본에는 있었어요 (점검이 돌지 않았어요)" if had else "없음 (2026-11-14 전 형식 · 직전 발행본에도 없어요)",
                "있어야 함 (그 전 형식만 경고)", warn=not had)
        rep.add(jname, True, "krSeries 없음 (확인 못 함)", jrule, warn=True)
        return
    probs = kr_series_problems(ks, day(data.get("pxDate")))
    bad = ks.get("bad")
    kept = ks.get("kept") if isinstance(ks.get("kept"), dict) else {}
    ref = ks.get("ref") if isinstance(ks.get("ref"), dict) else {}
    bs = ks.get("badStocks") if isinstance(ks.get("badStocks"), list) else []
    by = {s.get("t"): s for s in kr}

    def nm(c):
        return f"{c} {(by.get(c) or {}).get('nk', '')}".strip()
    rep.add(name, not probs and bad == 0,
            f"걸린 봉 {bad!r}" + (f" ({', '.join(nm(c) for c in bs[:KR_SERIES_SHOW])})" if bs else "")
            + f" · 최근 {ks.get('days')}거래일 고친 봉 {ks.get('pinned')!r} ({ks.get('pinStocks')!r}종목) · 기준가가 바뀐 종목 "
            f"{ref.get('breakStocks')!r} · 확인 못 한 종목 {ref.get('unknownStocks')!r} · 새로 상장 {ref.get('newStocks')!r} · 그대로 둔 봉 "
            f"다른 기준 {kept.get('basis')!r} · "
            f"값이 멂 {kept.get('far')!r} · 주식 수 모름 {kept.get('shr')!r} ({ks.get('keptStocks')!r}종목)"
            + (f" · 모양: {', '.join(probs[:3])}" if probs else ""), rule)
    if bs:
        rep.detail("공식 종가 고정 자기 점검에 걸린 국내 종목 (우리 코드가 봉을 잘못 바꿨어요)", [nm(c) for c in bs])
    jm = ks.get("jump") if isinstance(ks.get("jump"), list) else []
    per = {}
    for j in jm:
        if isinstance(j, list) and len(j) == 4:
            pct = f"{num(j[2]):+.1f}%" if num(j[2]) is not None else str(j[2])[:10]
            per.setdefault(str(j[0]), []).append(f"{j[1]} {pct} {KR_JUMP_WHY.get(j[3], j[3])}")
    items = [f"{nm(c)} ({' · '.join(v)})" for c, v in sorted(per.items())]
    rep.add(jname, True, f"{len(items)}종목" + (": " + ", ".join(items[:KR_SERIES_SHOW]) + (f" 외 {len(items) - KR_SERIES_SHOW}종목"
                                                 if len(items) > KR_SERIES_SHOW else "") if items else ""), jrule, warn=bool(items))
    if items:
        rep.detail("하루 가격 제한폭으로 설명되지 않는 움직임이 시계열에 있는 국내 종목 (날짜 · 움직임 · 이유)", items)


def px_bad_fields_problems(t, f, d, px):
    """pxBadF (비운 칸 목록) 의 모양 문제 (빈 목록 = 정상): PX_BAD_DATA 안의 칸 · 두 번 없음 · 시계열 전체 칸(PX_BAD_ALWAYS)은 모두 · 창은 같이 (52주 · 1년
    수익률 · 추세 점수는 함께) · 짧은 창을 비우면 긴 창도 (1개월 ⇒ 3개월 ⇒ 1년) · 기준일(px)에서 PX_BAD_WIN_IN 일 안의 움직임(d: 가장 최근)이면 그 창도."""
    if not (isinstance(f, list) and all(isinstance(k, str) for k in f) and len(set(f)) == len(f) and set(f) <= set(PX_BAD_DATA)):
        return [f"{t} pxBadF 모양이 잘못됨 ({str(f)[:40]})"]
    out = []
    fs = set(f)
    if not set(PX_BAD_ALWAYS) <= fs:
        out.append(f"{t} pxBadF 에 시계열 전체 칸이 빠짐 ({'·'.join(k for k in PX_BAD_ALWAYS if k not in fs)})")
    on = {w: set(ks) <= fs for w, ks in PX_BAD_WIN.items()}
    for w, ks in PX_BAD_WIN.items():
        if not on[w] and fs & set(ks):
            out.append(f"{t} pxBadF 의 {w} 창 칸이 일부만 ({'·'.join(k for k in ks if k in fs)})")
    if (on["m"] and not on["q"]) or (on["q"] and not on["y"]):
        out.append(f"{t} pxBadF 의 짧은 창만 비웠어요 (1개월 ⇒ 3개월 ⇒ 1년)")
    if px is not None and isinstance(d, str) and is_day(d):
        age = (px - day(d)).days
        for w, n in PX_BAD_WIN_IN.items():
            if age <= n and not on[w]:
                out.append(f"{t} 움직임 {d} 가 기준일에서 {age}일 — {w} 창 칸을 비워야 해요")
    return out


def px_bad_problems(stocks, comps, ks, px=None):
    """과거 주가 기록 오류 종목의 숫자 비움 (2026-11-14) — 문제 목록 (빈 목록 = 정상). 파이프라인(fetch_data.mark_px_bad)과 따로 적어요.
    stocks: data.json 의 국내 종목 모두 (cls kr · 펀드 포함) · comps: corp.json companies · ks: krSeries (hidden 이 있는 형식).
    - krSeries.hidden: 코드 목록 (같은 코드 두 번 없음).
    - 발행한 국내 종목 중 krSeries.jump 에 있는 종목 = hidden = pxBad 를 단 종목 (jump 에만 있고 발행하지 않은 코드는 비울 숫자가 없어요).
    - pxBad: 그 종목의 가장 최근 움직임 날짜 (YYYY-MM-DD) · pxBadF: 비운 칸 목록 (px_bad_fields_problems · px = pxDate).
    - 그 종목은 pxBadF 칸이 없어요 (빈 칸) · 비우지 않은 52주(hi · lo)는 있어요 · corp.json 의 그 회사도 같은 pxBad · pxBadF 이고 그 칸(PX_BAD_CORP 중)이
      비어요 · corp.json 에만 있는 표시도 안 돼요. 2026-11-14 저녁 (Jack): 계산 창에 움직임이 든 칸만 비워요 (PX_BAD_WIN)."""
    out = []
    hid = ks.get("hidden")
    if not isinstance(hid, list) or not all(isinstance(c, str) and c for c in hid) or len(set(hid)) != len(hid):
        return [f"krSeries.hidden 모양이 잘못됨 ({str(hid)[:40]})"]
    by = {s.get("t"): s for s in stocks}
    last = {}
    for j in ks.get("jump") if isinstance(ks.get("jump"), list) else []:
        if isinstance(j, list) and len(j) == 4 and isinstance(j[0], str) and is_day(j[1]):
            last[j[0]] = max(last.get(j[0], ""), str(j[1])[:10])
    jset = {c for c in last if c in by}
    hset = set(hid)
    marked = {t: s for t, s in by.items() if "pxBad" in s}
    out += [f"{c} 비우지 않음 (krSeries.jump 에 있어요)" for c in sorted(jset - hset)]
    out += [f"{c} krSeries.jump 에 없는데 비웠어요" for c in sorted(hset - set(last))]
    out += [f"{c} pxBad 표시 없음" for c in sorted(hset - set(marked))]
    out += [f"{c} pxBad 인데 krSeries.hidden 에 없음" for c in sorted(set(marked) - hset, key=str)]
    cby = {c.get("t"): c for c in comps}
    for t in sorted(marked, key=str):
        s, d = marked[t], marked[t].get("pxBad")
        if not (isinstance(d, str) and len(d) == 10 and is_day(d)):
            out.append(f"{t} pxBad 모양이 잘못됨 ({d!r})")
        elif t in last and d != last[t]:
            out.append(f"{t} pxBad {d} ≠ 가장 최근 움직임 {last[t]}")
        f = s.get("pxBadF")
        fp = px_bad_fields_problems(t, f, d, px)
        out += fp
        hide = set(f) if isinstance(f, list) and not (fp and fp[0].startswith(f"{t} pxBadF 모양")) else set(PX_BAD_DATA)
        left = [k for k in PX_BAD_DATA if k in hide and s.get(k) is not None]
        if left:
            out.append(f"{t} 남은 칸 {'·'.join(left)}")
        gone = [k for k in ("hi", "lo") if k not in hide and num(s.get(k)) is None]
        if gone:
            out.append(f"{t} 비우지 않았는데 없는 칸 {'·'.join(gone)}")
        c = cby.get(t)
        if c is not None:
            if c.get("pxBad") != d or c.get("pxBadF") != f:
                out.append(f"corp {t} pxBad · pxBadF {c.get('pxBad')!r} {str(c.get('pxBadF'))[:30]} ≠ data.json {d!r}")
            leftc = [k for k in PX_BAD_CORP if k in hide and c.get(k) is not None]
            if leftc:
                out.append(f"corp {t} 남은 칸 {'·'.join(leftc)}")
            gonec = [k for k in ("hi", "lo") if k not in hide and num(c.get(k)) is None]
            if gonec:
                out.append(f"corp {t} 비우지 않았는데 없는 칸 {'·'.join(gonec)}")
    out += [f"corp {c.get('t')} 에만 pxBad" for c in comps if ("pxBad" in c or "pxBadF" in c) and c.get("t") not in marked]
    out += [f"{t} pxBadF 만 있어요" for t, s in by.items() if "pxBadF" in s and "pxBad" not in s]
    return out


def px_bad_valid(t, s, c, ks, px=None):
    """t 종목의 과거 주가 기록 오류 표시가 맞는지 (pxBad 리뷰): krSeries.hidden 에 있고, 그 종목 하나만 놓고 본 px_bad_problems 가 비어요 (jump 의
    가장 최근 날짜 · 남은 칸 없음 · corp.json 의 표시와 칸도 같음). s: data.json 종목 · c: corp.json 회사 (없으면 None) · ks: krSeries."""
    hid = ks.get("hidden") if isinstance(ks, dict) else None
    if not (isinstance(hid, list) and t in hid and isinstance(s, dict) and "pxBad" in s):
        return False
    jm = [j for j in (ks.get("jump") if isinstance(ks.get("jump"), list) else []) if isinstance(j, list) and j and j[0] == t]
    return not px_bad_problems([s], [c] if isinstance(c, dict) else [], {**ks, "hidden": [t], "jump": jm}, px)


def px_bad_must(data, comps):
    """표시가 맞는 필수 종목 → {코드: 비운 칸 set} (pxBad 리뷰 · Jack 2026-11-14 저녁). 필수 종목 세 줄이 같은 답을 써요."""
    ks = data.get("krSeries") if isinstance(data.get("krSeries"), dict) else None
    by = {s.get("t"): s for s in data.get("stocks", [])}
    cby = {c.get("t"): c for c in comps}
    px = day(data.get("pxDate")) if is_day(data.get("pxDate")) else None
    out = {}
    for t in MUST:
        s = by.get(t)
        if isinstance(s, dict) and s.get("cls") == "kr" and "pxBad" in s and px_bad_valid(t, s, cby.get(t), ks, px):
            out[t] = set(s.get("pxBadF") or [])
    return out


def kr_no_trade_problems(data, pdata=None, days=None):
    """거래 없는 종목 표시(noTrade) · 빈 d1 의 이유(d1Why) · 거래 없는 날의 기준가 변화(ntD1) · 요약(d1Blank)이 서로 맞지 않는 곳 (빈 목록 = 정상).
    우리 파이프라인이 쓴 값끼리만 봐요 — 출처(목록 파일)를 다시 보지 않으니 출처의 잘못으로는 생기지 않아요 (Jack 2026-11-13: 한 종목의 출처 문제가
    모두의 발행을 막으면 안 돼요). 목록 파일에서 온 국내 종목 = cls kr · 펀드(fund) 아님 (펀드는 다른 길로 와요)."""
    out = []
    stocks = data.get("stocks") or []
    listed = [s for s in stocks if s.get("cls") == "kr" and not s.get("fund")]
    for s in stocks:
        t = s.get("t")
        mine = s.get("cls") == "kr" and not s.get("fund")
        nt, why = s.get("noTrade"), s.get("d1Why")
        if "noTrade" in s and nt is not True:
            out.append(f"{t} noTrade 가 true 가 아니에요 ({str(nt)[:10]})")
        if any(k in s for k in ("noTrade", "d1Why", "ntD1")) and not mine:
            out.append(f"{t} 목록 파일의 국내 종목이 아닌데 noTrade · d1Why · ntD1")
        if nt is True:
            if s.get("d1") is not None:
                out.append(f"{t} 거래 없음인데 d1 {s.get('d1')}")
            if why != "noTrade":
                out.append(f"{t} 거래 없음인데 d1Why {why!r}")
            if (num(s.get("val")) or 0) > 0:
                out.append(f"{t} 거래 없음인데 거래대금 {s.get('val')}억원")
        if why == "noTrade" and nt is not True:
            out.append(f"{t} d1Why noTrade 인데 noTrade 표시가 없어요")
        if "d1Why" in s and why not in D1_WHY:
            out.append(f"{t} d1Why 를 모르는 값 {str(why)[:12]!r}")
        if "d1Why" in s and s.get("d1") is not None:
            out.append(f"{t} d1 {s.get('d1')} 이 있는데 d1Why {why!r}")
        if "ntD1" in s:
            raw = s.get("ntD1")
            v = num(raw) if isinstance(raw, (int, float)) else None           # JSON 숫자만 (글자 "0" 은 숫자가 아니에요)
            if nt is not True:
                out.append(f"{t} 거래 없음이 아닌데 ntD1")
            if v is None or abs(v) > KR_DAY_LIMIT:
                out.append(f"{t} ntD1 {str(s.get('ntD1'))[:12]} (±{KR_DAY_LIMIT:g}% 안의 숫자여야 해요)")
    # 2026-11-19 (Jack): 마지막 확인 종가로 맞게 실린 종목(kr_own_codes — 기록 · 2차 출처 날 · pxDate 보다 앞선 날짜 · 나이 상한 · 지난 발행본의
    # 가격과 날짜까지 맞는 것)만 pxd(그 종가의 날짜)가 빈 d1 의 이유예요 — 미국 pxd 와 같아요. 그 밖에 pxd 가 있는 국내 종목은 예전 그대로 실패해요
    # (리뷰 M1: 지난 발행본과 가격이 다른 종목 · 1차 출처 날의 pxd). pdata: 지난 발행본 · days: 거래일 YYYY-MM-DD 들 (없으면 그 둘은 보지 않아요)
    own = kr_own_codes(data, pdata, days)
    for s in listed:
        if s.get("d1") is None and "d1Why" not in s and s.get("t") not in own:
            out.append(f"{s.get('t')} d1 이 빈 칸인데 이유(d1Why)가 없어요")
    db = data.get("d1Blank")
    cnt = collections.Counter(s.get("d1Why") for s in listed if "d1Why" in s)
    for k in D1_WHY:
        if db.get(k) != cnt.get(k, 0):
            out.append(f"d1Blank.{k} {db.get(k)!r} ≠ 종목 {cnt.get(k, 0)}")
    if not isinstance(db.get("seen"), bool):
        out.append(f"d1Blank.seen 모양이 잘못됨 ({str(db.get('seen'))[:10]})")
    elif not db["seen"]:
        if cnt.get("noTrade"):
            out.append("d1Blank.seen false (거래 없음을 가리지 않았어요) 인데 noTrade 표시가 있어요")
        if db.get("unseen") not in ("cols", "blank", "many"):
            out.append(f"d1Blank.unseen 모양이 잘못됨 ({str(db.get('unseen'))[:10]})")
    codes = {s.get("t") for s in listed}
    for k in ("odd", "must"):
        v = db.get(k)
        if not isinstance(v, list) or any(c not in codes for c in v):
            out.append(f"d1Blank.{k} 모양이 잘못됨 ({str(v)[:30]})")
    by = {s.get("t"): s for s in listed}
    for c in (db.get("odd") if isinstance(db.get("odd"), list) else []) + (db.get("must") if isinstance(db.get("must"), list) else []):
        if (by.get(c) or {}).get("noTrade") is True:
            out.append(f"{c} 표시하지 않았다는(d1Blank.odd · must) 종목에 noTrade 가 있어요")
    return out


def check_kr_no_trade(rep, data, pdata, macro=None):
    """기준일에 거래가 없던 한국 종목 (2026-11-14 · Jack, design chat 2026-11-08 · dart-gaps §9 "거래량 0 종목 = noTrade 표시 · d1 빈 칸" · 새 줄만,
    늦추는 줄 없음). 거래가 없던 날을 0.00% 로 보이지 않게 파이프라인(fetch_data.kr_no_trade · kr_d1_split)이 d1 을 비우고 noTrade 를 달아요.
    실패: 우리 값끼리 어긋날 때만 (kr_no_trade_problems — 거래 없음인데 d1 숫자 · 이유 없는 빈 d1 · 요약 d1Blank 이 종목과 다름 …). d1Blank 이 없으면
    직전 발행본에 있었거나 종목에 표시가 있을 때만 실패 (그 전 형식은 경고 — 머지 뒤 첫 발행 전까지의 사이트 --live 와 시험 데이터).
    경고 (출처 쪽 · 발행은 막지 않아요, Jack 2026-11-13): 거래 없음을 가리지 못한 날 (목록 파일에 칸이 없음 · 칸이 대부분 빈 값 · 거래 없는 행이
    너무 많음 — 그날은 예전처럼 0.00%) · 가렸는데 거래 없는 종목이 0 (리뷰 S2: 보통 날 목록 파일 135 ~ 141행 — 칸의 뜻이 바뀌었을 수 있어요) ·
    거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 행 (odd) · 거래가 없다고 나온 필수 종목 (must — 표시하지 않고 d1 은 공식 종가로).
    pdata: 직전 발행본 data.json (발행 모드에서만, 아니면 None)."""
    name = "국내 거래 없는 종목 · 빈 d1 이유 (noTrade · d1Why)"
    wname = "국내 거래 없는 종목: 목록 파일의 칸 (경고만)"
    rule = (f"0 (거래 없는 종목은 d1 빈 칸 · d1Why noTrade · 거래대금 0 · ntD1 은 그 종목만 ±{KR_DAY_LIMIT:g}% 안 · 목록 파일 종목의 빈 d1 은 "
            "모두 d1Why · d1Blank 수 = 종목 · 그 전 형식만 경고)")
    wrule = "거래 없음을 가림 · 거래 없는 종목 1 이상 · 어긋난 행 0 · 거래 없다고 나온 필수 종목 0 (아니면 경고 · 그 종목은 표시하지 않아요)"
    stocks = data.get("stocks") or []
    db = data.get("d1Blank")
    marks = [s.get("t") for s in stocks if any(k in s for k in ("noTrade", "d1Why", "ntD1"))]
    if not isinstance(db, dict):
        had = isinstance((pdata or {}).get("d1Blank"), dict)
        why = ("직전 발행본에는 있었어요 (거래 없음 단계가 돌지 않았어요)" if had else
               f"표시 {len(marks)}곳이 있는데 요약이 없어요" if marks else
               "2026-11-14 전 형식 · 직전 발행본에도 없어요 — 거래가 없던 종목도 d1 0.00% 로 나가요")
        rep.add(name, not had and not marks, f"d1Blank 없음 ({why})", rule, warn=not had and not marks)
        rep.add(wname, True, "d1Blank 없음 (확인 못 함)", wrule, warn=True)
        return
    probs = kr_no_trade_problems(data, pdata, kr_days_of(macro))   # 2026-11-19: 맞게 실린 마지막 확인 종가만 빈 d1 의 이유 (macro: 거래일)
    nts = [s for s in stocks if s.get("noTrade") is True]
    rep.add(name, not probs,
            f"거래 없음 {db.get('noTrade')!r} · ±{KR_DAY_LIMIT:g}% 밖 {db.get('range')!r} · 직전 거래일 행 없음 {db.get('new')!r} · 직전 거래일 파일 없음 "
            f"{db.get('prev')!r}" + (f" · 문제 {len(probs)}: {', '.join(probs[:3])}" if probs else ""), rule)
    if probs:
        rep.detail("거래 없는 종목 · 빈 d1 이유가 어긋난 곳 (우리 코드의 잘못)", probs)
    if nts:
        rep.detail("기준일에 거래가 없던 국내 종목 (d1 빈 칸 · 앱: '{md} 거래 없음 (거래정지일 수 있어요)')",
                   [f"{s.get('t')} {s.get('nk', '')}" + (f" (기준가 {num(s.get('ntD1')):+.2f}%)" if num(s.get("ntD1")) else "") for s in nts])
    odd = db.get("odd") if isinstance(db.get("odd"), list) else []
    must = db.get("must") if isinstance(db.get("must"), list) else []
    by = {s.get("t"): s.get("nk", "") for s in stocks}
    parts = []
    if db.get("seen") is False:
        parts.append({"cols": "목록 파일에 거래량 · 시가 칸이 없어", "blank": "거래량 · 시가 칸이 대부분 빈 값이라",
                      "many": "거래 없는 행이 너무 많아 (파일의 잘못)"}.get(db.get("unseen"), "까닭 모름 ·")
                     + " 거래 없음을 가리지 않았어요 — 거래가 없던 종목도 d1 0.00%")
    elif db.get("seen") is True and not nts:
        parts.append("가렸는데 거래 없는 종목이 0 (보통 날 목록 파일 135 ~ 141행 · 거래량 · 시가 칸의 뜻이 바뀌었을 수 있어요)")
    if odd:
        parts.append(f"거래량 · 시가는 0 인데 거래대금이 0 이 아닌 (값이 있거나 빈) 행 {len(odd)}: " + ", ".join(f"{c} {by.get(c, '')}" for c in odd[:NO_TRADE_SHOW]))
    if must:
        parts.append(f"거래가 없다고 나온 필수 종목 {len(must)} (표시하지 않음 · d1 은 공식 종가로): " + ", ".join(f"{c} {by.get(c, '')}" for c in must))
    rep.add(wname, True, " · ".join(parts) if parts else f"가림 · 거래 없는 종목 {len(nts)}", wrule, warn=bool(parts))


def check_px_bad(rep, data, comps, pdata):
    """과거 주가 기록 오류 종목의 숫자 비움 (2026-11-14 · Jack, Q2 (a) · 새 줄만, 늦추는 줄 없음). 하루 움직임이 가격 제한폭으로 설명되지 않는
    종목(krSeries.jump)은 계산 창에 그 움직임이 든 칸(pxBadF · PX_BAD_WIN — Jack 2026-11-14 저녁)이 비었는지 (px_bad_problems) — 실패.
    krSeries.hidden 이 없으면 (2026-11-14 숨김 전 형식): 직전 발행본에 있었거나 pxBad 표시가 있으면 실패 (비우는 단계가 돌지 않았어요),
    아니면 경고만 (머지 뒤 첫 발행 전까지의 사이트 --live 와 시험 데이터 — 그 종목들의 숫자가 그대로 나가요).
    새로 생긴 움직임 종목 수 (Jack 2026-11-14 저녁): 직전 발행본의 jump 에 없던 종목이 PX_BAD_NEW_FAIL 이상이면 실패.
    필수 종목 추세 · 저변동 순위 (mz · lz): 빈 칸일 수 있는 값으로 순위를 매기니 필수 종목이 들어 있는지 (표시가 맞는 필수 종목 하나는 경고 ·
    PX_BAD_MUST_FAIL 곳 이상이면 실패 · 표시 없이 빠지면 실패). pdata: 직전 발행본 data.json (발행 모드에서만, 아니면 None)."""
    name = "과거 주가 기록 오류 종목의 숫자 비움 (pxBad)"
    rule = ("0 (krSeries.jump 의 발행 종목 = krSeries.hidden = pxBad 표시 종목 · 그 종목은 pxBadF 칸 빈 칸 (계산 창에 움직임이 든 칸: 시계열 전체 "
            + "·".join(PX_BAD_ALWAYS) + " 은 늘 · 252봉 " + "·".join(PX_BAD_WIN["y"]) + " · 64봉 r3 · 22봉 r1 은 그 창에 들 때) · 비우지 않은 52주는 있음 · "
            "corp.json 도 같은 표시와 칸 · 그 전 형식만 경고)")
    stocks = [s for s in data.get("stocks", []) if s.get("cls") == "kr"]
    ks = data.get("krSeries") if isinstance(data.get("krSeries"), dict) else None
    px = day(data.get("pxDate")) if is_day(data.get("pxDate")) else None
    marked = [s for s in stocks if "pxBad" in s or "pxBadF" in s] + [c for c in comps if "pxBad" in c or "pxBadF" in c]
    pks = (pdata or {}).get("krSeries")
    had = isinstance(pks, dict) and "hidden" in pks
    if ks is None or "hidden" not in ks:
        why = ("직전 발행본에는 있었어요 (비우는 단계가 돌지 않았어요)" if had else
               f"pxBad 표시 {len(marked)}곳이 있는데 목록이 없어요" if marked else
               "2026-11-14 숨김 전 형식 · 직전 발행본에도 없어요 — krSeries.jump 종목의 숫자가 그대로 나가요")
        rep.add(name, not had and not marked, ("krSeries 없음" if ks is None else "krSeries.hidden 없음") + f" ({why})", rule,
                warn=not had and not marked)
    else:
        probs = px_bad_problems(stocks, comps, ks, px) + [f"{x.get('t')} 국내 종목이 아닌데 pxBad" for x in data.get("stocks", [])
                                                            if x.get("cls") != "kr" and ("pxBad" in x or "pxBadF" in x)]
        hid = ks.get("hidden") if isinstance(ks.get("hidden"), list) else []
        by = {s.get("t"): s for s in stocks}

        def nm(c):
            x = by.get(c) or {}
            full = isinstance(x.get("pxBadF"), list) and "hi" in x["pxBadF"]
            return f"{c} {x.get('nk', '')} ({x.get('pxBad', '?')} · {'52주까지' if full else '52주는 보여요'})"
        names = [nm(c) for c in hid]
        n52 = sum(1 for c in hid if isinstance((by.get(c) or {}).get("pxBadF"), list) and "hi" in by[c]["pxBadF"])
        rep.add(name, not probs,
                f"{len(hid)}종목 (52주까지 비움 {n52} · 52주는 보임 {len(hid) - n52}) · 문제 {len(probs)}"
                + (f" ({', '.join(probs[:3])}{' …' if len(probs) > 3 else ''})" if probs else "")
                + (f" — {', '.join(names[:PX_BAD_SHOW])}" + (f" 외 {len(names) - PX_BAD_SHOW}종목" if len(names) > PX_BAD_SHOW else "")
                   if names else ""), rule)
        if probs:
            rep.detail("과거 주가 기록 오류 종목의 숫자 비움 — 문제", probs)
        if names:
            rep.detail("과거 주가 기록 오류로 숫자를 비운 국내 종목 (가장 최근 움직임 날짜 · 52주를 비웠는지)", names)
    # 새로 생긴 움직임 종목 수 (Jack 2026-11-14 저녁)
    nname = f"새로 생긴 과거 주가 기록 오류 종목 수 ({PX_BAD_NEW_FAIL}종목 이상이면 실패)"
    nrule = (f"{PX_BAD_NEW_FAIL}종목 미만 (오늘 krSeries.jump 에 있고 직전 발행본의 jump 에 없는 종목 · 지난 3년 날마다 0~2 — 그보다 훨씬 많으면 출처나 "
             "우리 고정이 한꺼번에 깨졌을 수 있어요)")
    pj = pks.get("jump") if isinstance(pks, dict) else None
    if not isinstance(pdata, dict):
        rep.add(nname, True, "직전 발행본 없음 (비교 안 함)", nrule)
    elif ks is None or not isinstance(pj, list):
        rep.add(nname, True, "직전 발행본 또는 오늘 파일에 krSeries.jump 없음 (비교 안 함)", nrule)
    else:
        def codes(jm):
            return {j[0] for j in jm if isinstance(j, list) and j and isinstance(j[0], str)}
        new = sorted(codes(ks.get("jump") if isinstance(ks.get("jump"), list) else []) - codes(pj))
        allby = {s.get("t"): s for s in data.get("stocks", [])}
        txt = [f"{c} {(allby.get(c) or {}).get('nk', '')}".strip() for c in new]
        rep.add(nname, len(new) < PX_BAD_NEW_FAIL, f"새로 {len(new)}종목" + (f": {', '.join(txt[:PX_BAD_SHOW])}"
                                                                              + (f" 외 {len(txt) - PX_BAD_SHOW}종목" if len(txt) > PX_BAD_SHOW else "")
                                                                              if txt else ""), nrule)
        if txt:
            rep.detail("오늘 새로 생긴 과거 주가 기록 오류 종목 (직전 발행본의 jump 에 없음)", txt)
    allby = {s.get("t"): s for s in data.get("stocks", [])}
    pm = px_bad_must(data, comps)
    src = {"mz": ("mom", "1년 수익률(mom) 없음"), "lz": ("vol", "변동성(vol) 없음")}
    miss, held = [], []                 # held: 표시가 맞는 필수 종목 (과거 주가 기록 오류로 점수를 비움 · 경고) · miss: 그 밖에 빠진 것 (실패)
    for t in MUST:
        s = allby.get(t)
        if s is None:
            miss.append(f"{t} 데이터에 없음")
            continue
        if s.get("cls") != "kr":
            continue
        gone = [k for k in ("mz", "lz") if num(s.get(k)) is None]
        if not gone:
            continue
        if t in pm and set(gone) <= pm[t]:
            held.append(f"{t} {s.get('nk', '')} {'·'.join(gone)} — 과거 주가 기록 오류 (pxBad {s.get('pxBad')})")
            continue
        why = (f"pxBad {s.get('pxBad')!r} 인데 표시가 맞지 않아요" if "pxBad" in s else
               " · ".join(src[k][1] if num(s.get(src[k][0])) is None else f"{k} 없음 ({src[k][0]} 있음)" for k in gone))
        miss.append(f"{t} {s.get('nk', '')} {'·'.join(gone)} — {why}")
    value = " · ".join(([f"빠짐: {' · '.join(miss[:4])}"] if miss else [])
                       + ([f"과거 주가 기록 오류로 뺀 필수 종목 {len(held)}: {' · '.join(held[:4])}"] if held else []))
    rep.add("필수 종목 추세 · 저변동 순위 (mz · lz)", not miss and len(pm) < PX_BAD_MUST_FAIL, value or "모두 있음",
            f"{','.join(MUST)} (국내 · 표시 없이 빠지면 실패 · 과거 주가 기록 오류로 맞게 표시한 필수 종목은 경고, {PX_BAD_MUST_FAIL}곳 이상이면 실패 — "
            "빈 칸일 수 있는 값으로 순위를 매기니 꼭 있어야 할 종목을 확인해요)", warn=bool(held or pm))


def unit_fix_problems(c):
    """corp.json 회사의 unitFix 문제 목록: [{rep: "YYYY.nQ", bs · is · cf 중 하나 이상: 1000 · 1000000}] 꼴 (목록이 아니거나 비었으면 · 숫자 · None
    도 '모양이 잘못됨') · rep 은 bq (TTM 의 최신 분기 — 파이프라인이 고치는 유일한 보고서)와 같아야 · unitChk 와 같이 있으면 안 돼요 (걸린 회사는
    고친 숫자도 비워요). 리뷰 #116 2차 N4: 이상한 값으로 관문이 멈추지 않고 실패 줄이 돼요."""
    t, u = c.get("t"), c.get("unitFix")
    bad = []
    if not (isinstance(u, list) and u):
        return [f"{t} unitFix 모양이 잘못됨 ({u!r})"]
    for x in u:
        parts = {k: v for k, v in (x or {}).items() if k != "rep"} if isinstance(x, dict) else None
        if not (isinstance(x, dict) and isinstance(x.get("rep"), str) and re.fullmatch(r"\d{4}\.[1-4]Q", x["rep"]) and parts
                and set(parts) <= set(UNIT_FIX_PARTS) and all(v in UNIT_FIX_K for v in parts.values())):
            bad.append(f"{t} unitFix 모양이 잘못됨 ({x!r})")
        elif x["rep"] != c.get("bq"):
            bad.append(f"{t} unitFix 보고서 {x['rep']} ≠ bq {c.get('bq')!r} (고친 보고서는 TTM 의 최신 분기여야 해요)")
    if "unitChk" in c:
        bad.append(f"{t} unitFix 와 unitChk 가 같이 있어요")
    if not c.get("bq"):
        bad.append(f"{t} unitFix 인데 bq 없음")
    return bad


EPS_LINE_LEFT = "다시 읽은 뒤 '고치는 중' 줄이 남을 국내 회사 (경고만)"


def check_eps_line_left(rep, corp, comps):
    """2026-11-14 (Jack Q3 · 리뷰 S4, 새 줄 · 더 엄격하게만): 다시 읽은 뒤(corp.json epsBasis "owners") 두 앱의 'PER과 EPS는 계산 방법을
    고치는 중이라 11월 10일에 바뀔 수 있어요.' 줄은 어디에도 없어야 해요 (날짜가 지났어요). 앱(src/repair.js epsFixNeeded)은 그 회사의
    epsIn.b 가 o · s (고쳐짐) 이거나 t (총 순이익) · 해외 기업이면 줄을 빼요. 그래서 PER · EPS · ROE 가 보이는 국내 회사(원화 재무제표 ·
    단위 확인 아님)에 그런 epsIn 이 없으면 사용자는 지난 날짜의 줄을 봐요. EPS 가 있는데 영수증이 없으면 'EPS·BPS 영수증 모양' 줄이 이미
    실패해요 — 이 줄은 ROE 만 있는 회사까지 이름을 대요. 경고만: 날짜가 지난 안내 한 줄 때문에 발행 전체를 멈추면(어제 데이터) 더 나빠요."""
    if (corp or {}).get("epsBasis") != "owners":
        rep.skip(EPS_LINE_LEFT, "corp.json epsBasis 가 owners 가 아니에요 (다시 읽기 전 발행본 — 'EPS 기준 표시' 줄이 말해요)")
        return
    left = []
    for c in comps:
        t = c.get("t")
        if is_foreign(t) or c.get("stmtCur") or c.get("unitChk"):
            continue
        if all(num(c.get(k)) is None for k in ("eps", "per", "roe")):
            continue
        e = c.get("epsIn")
        if not (isinstance(e, dict) and e.get("b") in EPS_B):
            left.append(f"{t} {c.get('nk', '')}")
    rep.add(EPS_LINE_LEFT, True, f"{len(left)}곳" + (f": {', '.join(left[:4])}" if left else ""),
            "0 (있으면 경고 · 앱이 날짜가 지난 '… 11월 10일에 바뀔 수 있어요' 줄을 보여요: 그 회사의 epsIn 을 확인)", warn=bool(left))
    if left:
        rep.detail(EPS_LINE_LEFT, left)


def check_unit_fix(rep, kr, by, comps):
    """공시 단위 고침 (리뷰 #116 R3 · 새 줄만): unitFix 모양 (실패) · 고친 회사 목록 (경고, UNIT_FIX_CHECKED 의 같은 기록은 조용히)."""
    fixed = [c for c in comps if "unitFix" in c]
    bad = [p for c in fixed for p in unit_fix_problems(c)]
    rep.add("공시 단위 고침 기록 모양 (unitFix)", not bad, f"{len(fixed)}곳 · 어긋남 {len(bad)}" + (f" (예: {', '.join(bad[:3])})" if bad else ""),
            "0 ([{rep, bs·is·cf: 1000 · 1000000}] · unitChk 회사에는 없음)")
    loud, quiet = [], []
    for c in fixed:
        uf = c["unitFix"] if isinstance(c["unitFix"], list) else []          # 모양이 틀린 값은 위 실패 줄이 말해요 (여기서 멈추지 않게)
        desc = "; ".join(f"{x.get('rep')} " + " · ".join(f"{k} ÷{num(v):,.0f}" if num(v) is not None else f"{k} {v!r}" for k, v in x.items() if k != "rep")
                         for x in uf if isinstance(x, dict)) or repr(c["unitFix"])
        nm = f"{c.get('t')} {c.get('nk', '')} ({desc})"
        ck = UNIT_FIX_CHECKED.get(c.get("t"))
        (quiet if ck and ck.get("unitFix") == c["unitFix"] else loud).append(nm)
    rep.add("공시 단위를 고쳐 읽은 회사 (unitFix · 경고만)", True, f"{len(loud)}곳" + (f": {', '.join(loud[:4])}" if loud else "")
            + (f" · 확인된 회사 {len(quiet)}곳 조용히 넘김" if quiet else ""), "0 (있으면 경고 · 그 보고서의 단위를 사람이 확인)", warn=bool(loud))
    if loud:
        rep.detail("공시 단위를 고쳐 읽은 회사 (그 보고서의 지난해 칸으로 증명 · 나눈 뒤 기준값과 맞음)", loud)


def _dvwhy_clean(r):
    """사건 하나의 배율이 깨끗한 분할 배율이나 그 역수인지 (±DVWHY_CLEAN_TOL)."""
    return any(abs(r / c - 1) <= DVWHY_CLEAN_TOL for k in SPLIT_FACTORS for c in (float(k), 1.0 / k))


def _real_day(x):
    """YYYY-MM-DD 이고 있는 날짜면 그 날짜, 아니면 None."""
    if not isinstance(x, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", x):
        return None
    try:
        return dt.date.fromisoformat(x)
    except ValueError:
        return None


def _rc_ok(rc, today):
    """DART 접수번호: 14자리이고 앞 8자리가 2000-01-01 ~ 오늘의 날짜."""
    rd = _real_day(f"{rc[:4]}-{rc[4:6]}-{rc[6:8]}") if isinstance(rc, str) and re.fullmatch(r"\d{14}", rc) else None
    return rd is not None and dt.date(2000, 1, 1) <= rd <= today


def _posint(x):
    return isinstance(x, int) and not isinstance(x, bool) and x > 0


def dvwhy_adj_years(s):
    """배당을 다시 계산한 해 (dpsF 가 1 이 아닌 숫자인 해) 의 번호 [0 당기 · 1 전기 · 2 전전기]."""
    f3 = _nums3(s.get("dpsF"))
    return [i for i in range(3) if f3[i] is not None and f3[i] != 1] if f3 else []


def _exact_bonus(e):
    """v19.1j 답 12 (가): 무상증자 사건이고 r = 1 + x (x = 1주당 신주 수 > 0, ± 1e-6)."""
    return isinstance(e, dict) and e.get("k") == "bonus" and _isnum(e.get("r")) and _isnum(e.get("x")) and e["x"] > 0 \
        and abs(e["r"] - (1 + e["x"])) <= EXACT_TOL


def _ev_r(e, exact=False):
    """사건 하나의 배율 — exact 인 종목의 무상증자는 1 + x 로 (반올림한 r 이 아니라 · 답 12 (나))."""
    return 1 + e["x"] if exact and _exact_bonus(e) else e["r"]


def _same_f(prod, f, evs, exact=False):
    """사건의 곱 prod = 배율 f: 깨끗하지 않은 배율의 사건이 끼면(exact 인 종목만) |prod − f| ≤ 1e-6, 아니면 ± DVWHY_TOL."""
    if exact and any(not _dvwhy_clean(e["r"]) for e in evs):
        return abs(prod - f) <= EXACT_TOL
    return abs(prod / f - 1) <= DVWHY_TOL


def _dvwhy_events(ev, today, exact=False):
    """사건 목록의 모양 문제 → 이유 또는 None. v19.1j: exact 인 종목은 깨끗하지 않은 배율의 무상증자(r = 1 + x)도 받아요 (답 12 (가))."""
    if not isinstance(ev, list) or not ev:
        return "사건 목록 (비었거나 목록이 아님)"
    prev = None
    for e in ev:
        if not isinstance(e, dict) or e.get("k") not in DVWHY_KINDS:
            return "사건 종류"
        if set(e) != ({"k", "d", "r", "rc", "x"} if e["k"] == "bonus" else {"k", "d", "r", "rc"}):
            return f"사건 칸 {sorted(e)}"
        r = e.get("r")
        if not _isnum(r) or r <= 0 or not (_dvwhy_clean(r) or (exact and _exact_bonus(e))) or abs(r - 1) <= DVWHY_SAME + 1e-9:
            return f"깨끗하지 않은 배율 {r}"
        if (e["k"] == "split" and not r > 1) or (e["k"] in ("merge", "reduce") and not r < 1):
            return f"{e['k']} 배율 {r:g}"
        if e["k"] == "bonus" and (not _isnum(e.get("x")) or not e["x"] > 0 or abs(r - (1 + e["x"])) > 1e-6):
            return f"무상증자 배율 {r:g} ≠ 1 + {e.get('x')}"
        if _real_day(e.get("d")) is None:
            return f"날짜 {e.get('d')}"
        if not _rc_ok(e.get("rc"), today):
            return f"접수번호 {e.get('rc')}"
        if prev is not None and (e["d"], e["rc"]) < prev:
            return "사건 순서 (오래된 것부터)"
        prev = (e["d"], e["rc"])
    return None


def _dvwhy_ratio(ev, fy, f3, adj, px, exact=False):
    """사건의 곱 = 다시 계산한 해마다 dpsF (그해 12월 31일 뒤 ~ pxDate) · 사건은 가장 오래된 해 12월 31일 뒤 ~ pxDate 안 ·
    당기 배율이 1 이면 그 뒤 사건 없음 → 이유 또는 None."""
    start = dt.date(fy - max(adj), 12, 31)
    out = [e for e in ev if not start < _real_day(e["d"]) <= px]
    if out:
        return f"날짜 {out[0]['d']} 가 {start} 뒤 ~ {px} 밖"
    for i in adj:
        cut = dt.date(fy - i, 12, 31)
        evi = [e for e in ev if cut < _real_day(e["d"]) <= px]
        prod = math.prod(_ev_r(e, exact) for e in evi)
        if not _same_f(prod, f3[i], evi, exact):
            return f"{fy - i}년 배율 {f3[i]:g} ≠ 사건의 곱 {prod:.7g}" if exact else f"{fy - i}년 배율 {f3[i]:g} ≠ 사건의 곱 {prod:.4g}"
    if f3[0] == 1 and any(dt.date(fy, 12, 31) < _real_day(e["d"]) for e in ev):    # 당기 배율 1 = 사업보고서 뒤 사건 없음
        return f"{fy}년 배율 1 인데 그 뒤 사건이 있어요"
    return None


def dvwhy_problems(s, px, today, exact=False):
    """한 종목의 dvWhy → (모양 문제, 배율·날짜 문제) — 없으면 None. (v19.1h)
    ok    사건 목록(깨끗한 배율 · 10% 넘는 변화 · 분할 > 1 · 병합 < 1 · 무상증자 = 1 + x · 날짜 · 접수번호 · 오래된 것부터) · 다시 계산한
          해가 있고, 해마다 그해 12월 31일 뒤 ~ pxDate 사건의 곱 = dpsF ± 0.5%.
    nf    a · b 양의 정수 · a ≠ b · b = 오늘 상장 주식 수(shr) · b ÷ a 가 가장 오래된 다시 계산한 해 dpsF ± 10%.
    filed a · b · fx(유상증자 · 전환사채 · 신주인수권부사채: 공시일 · 주식 수 · 접수번호) · b = shr · a < b ≤ a + 덮는 수 + a 의 10% ·
          당기 배율 1 (또는 당기 배당 없음) · 남은 다시 계산한 해는 사업보고서 안 사건(ev)으로 설명돼요.
    nc-*  칸은 v · st 만 · 다시 계산한 해가 없고 배당한 해는 모두 비교 불가(배당수익률이 숨겨져요)."""
    w = s.get("dvWhy")
    if not isinstance(w, dict) or w.get("v") != 1 or isinstance(w.get("v"), bool) or w.get("st") not in DVWHY_ST:
        return "칸 모양 (v · st)", None
    st, fy, f3, adj = w["st"], s.get("fy"), _nums3(s.get("dpsF")), dvwhy_adj_years(s)
    keys = {"ok": ({"v", "st", "ev"}, set()), "nf": ({"v", "st", "a", "b"}, set()), "filed": ({"v", "st", "a", "b", "fx"}, {"ev"}),
            "nc-mismatch": ({"v", "st"}, set()), "nc-unexplained": ({"v", "st"}, set())}[st]
    if not keys[0] <= set(w) <= keys[0] | keys[1]:
        return f"{st} 칸 {sorted(w)}", None
    if not isinstance(fy, int) or isinstance(fy, bool) or not 2000 <= fy <= today.year or f3 is None or px is None:
        return None, "사업보고서 연도 · dpsF · pxDate 없음"
    d3 = _nums3(s.get("dps3")) or [None] * 3
    if st.startswith("nc-"):
        shown = [i for i in range(3) if (d3[i] or 0) > 0 and f3[i] is not None]
        if adj or shown or s.get("divSt") not in ("nc", "nd"):
            return None, f"{st} 인데 다시 계산했거나 배당한 해의 배율이 남았어요 (배당수익률을 숨겨야 해요)"
        return None, None
    if st in ("ok", "nf") and not adj:
        return None, f"{st} 인데 다시 계산한 해가 없어요"
    if st == "ok":
        bad = _dvwhy_events(w["ev"], today, exact)
        return (bad, None) if bad else (None, _dvwhy_ratio(w["ev"], fy, f3, adj, px, exact))
    a, b = w.get("a"), w.get("b")
    if not _posint(a) or not _posint(b) or a == b:
        return f"{st} 의 a · b (양의 정수 · a ≠ b)", None
    shr = num(s.get("shr"))
    if shr is None or b != shr:
        return None, f"b {b} ≠ 오늘 상장 주식 수 {s.get('shr')}"
    if st == "nf":
        old = max(adj)
        if abs((b / a) / f3[old] - 1) > DVWHY_SAME:
            return None, f"b ÷ a = {b / a:.3f} 가 {fy - old}년 배율 {f3[old]:g} 와 달라요"
        return None, None
    fx = w.get("fx")                                                        # filed
    if not isinstance(fx, list) or not fx:
        return "filed 의 fx (비었거나 목록이 아님)", None
    lo_r = dt.date(fy, 12, 31) - dt.timedelta(days=DVWHY_LOOKBACK_DAYS)
    cover = 0.0
    for x in fx:
        if not isinstance(x, dict) or set(x) != {"k", "d", "n", "rc"} or x.get("k") not in DVWHY_FX_KINDS or not _posint(x.get("n")) \
                or _real_day(x.get("d")) is None or not _rc_ok(x.get("rc"), today):
            return f"filed 의 fx 칸 {x}", None
        d = _real_day(x["d"])
        if d > px or (x["k"] == "rights" and d <= lo_r) or d < dt.date(fy - 2, 1, 1):
            return None, f"fx 날짜 {x['d']} 가 기간 밖"
        cover += x["n"] if x["k"] == "rights" else x["n"] / DVWHY_CB_FLOOR
    if not a < b <= a + cover + DVWHY_SAME * a:
        return None, f"늘어난 주식 수 {b - a:,} 를 공시({cover:,.0f})가 설명하지 못해요"
    if f3[0] not in (1, None) or (f3[0] is None and (d3[0] or 0) > 0):
        return None, "filed 인데 당기 배당이 공시 그대로가 아니에요"
    if adj:
        bad = _dvwhy_events(w.get("ev"), today)
        if bad:
            return bad, None
        if any(_real_day(e["d"]) > dt.date(fy, 12, 31) for e in w["ev"]):
            return None, "filed 의 사건은 사업보고서 안이어야 해요"
        return None, _dvwhy_ratio(w["ev"], fy, f3, adj, px)
    if "ev" in w:
        return "filed 인데 다시 계산한 해 없이 사건이 있어요", None
    return None, None


def check_v191h(rep, data, kr, by, comps, pdata, today):
    """v19.1h 새 줄 (Jack 의 답 2026-11-08): 배당 맞춤 이유 (dvWhy · divCheck.why)."""
    dc = data.get("divCheck")
    if not isinstance(dc, dict):
        return                                    # v19.1b 전 데이터 — '배당 분할 확인 기록' 줄이 알려요
    why = dc.get("why")
    name = "배당 맞춤 이유 기록 (divCheck.why)"
    if not isinstance(why, dict):
        had = isinstance(((pdata or {}).get("divCheck") or {}).get("why"), dict)
        rep.add(name, not had, "없음 — 직전 발행본에는 있었어요" if had else "없음 (v19.1h 전 형식이라 새 검사를 건너뛰어요)",
                "있어야 함 (v19.1h 전 데이터만 경고)", warn=not had)
        return
    px = day(data.get("pxDate")) if is_day(data.get("pxDate")) else None
    com = [s for s in kr if not is_pref(s.get("t"))]
    kr_t = {s.get("t") for s in kr}
    has = [s for s in kr if "dvWhy" in s]
    adj = {s["t"] for s in com if dvwhy_adj_years(s)}
    st_of = {s["t"]: s["dvWhy"].get("st") for s in has if isinstance(s.get("dvWhy"), dict) and s["dvWhy"].get("st") in DVWHY_ST}
    st_n = collections.Counter(st_of.values())

    # 1. 기록: v1 · 결론마다 종목 수 = dvWhy 가 그 결론인 종목 · 줄이 없는 종목(failT 조회 실패 · keptT 스위치가 꺼져 맞춤 그대로)은
    #    그 수만큼, 실제 종목이고, dvWhy 가 없고, 다시 계산한 해가 있어요
    bad = []
    if why.get("v") != 1:
        bad.append(f"v{why.get('v')}")
    for k in DVWHY_ST + ("fail", "kept"):
        if not isinstance(why.get(k), int) or isinstance(why.get(k), bool) or why[k] < 0:
            bad.append(f"{k} {why.get(k)}")
    for k in DVWHY_ST:
        if why.get(k) != st_n.get(k, 0):
            bad.append(f"{k} {why.get(k)}≠{st_n.get(k, 0)}")
    for k in ("fail", "kept"):
        lst = why.get(k + "T")
        if not isinstance(lst, list) or not all(isinstance(t, str) for t in lst) or len(set(lst)) != len(lst) \
                or len(lst) != why.get(k) or any(t not in kr_t for t in lst):
            bad.append(f"{k}T")
        elif any("dvWhy" in by[t] or t not in adj for t in lst):
            bad.append(f"{k}T 인데 dvWhy 가 있거나 다시 계산한 해가 없음")
    rep.add(name, not bad, "맞음" if not bad else " · ".join(bad[:4]),
            "v1 · 결론마다 수 = dvWhy 종목 · failT·keptT = 그 수의 줄 없는 종목")

    # 2. 칸: 다시 계산한 해가 있는 보통주는 dvWhy(ok · nf · filed)가 있거나 조회 실패(failT) · 스위치 꺼짐(keptT)으로 적혀 있어요.
    #    ok · nf 는 다시 계산한 해가 있는 종목에만, nc-* 는 다시 계산한 해가 없는 종목에만. 이유 없이 빠지거나 엉뚱하면 실패
    known = set(why.get("failT") or []) | set(why.get("keptT") or [])
    miss = sorted(t for t in adj if "dvWhy" not in by[t] and t not in known)
    extra = sorted(s["t"] for s in has if is_pref(s["t"]) or (st_of.get(s["t"]) in ("ok", "nf") and s["t"] not in adj)
                   or (str(st_of.get(s["t"])).startswith("nc-") and s["t"] in adj))
    left = sorted(t for t in adj if "dvWhy" not in by[t] and t in known)
    rep.add("배당 맞춤 이유 칸 (dvWhy · 다시 계산한 해가 있는 종목)", not extra and not miss,
            f"엉뚱한 종목 {len(extra)} · 이유 없이 빠짐 {len(miss)}" + (f" (예: {(extra + miss)[0]})" if extra or miss else "")
            + f" · 조회 실패·스위치 꺼짐으로 빠짐 {len(left)}",
            "0 · 0 (조회 실패는 경고 줄이 이름을 적어요)")

    # 3·4. 모양 · 배율과 날짜
    shape, ratio = [], []
    ex = exact_bonus_set(data, kr, comps, today)          # v19.1j 답 12
    for s in has:
        a, b = dvwhy_problems(s, px, today, exact=s["t"] in ex)
        if a:
            shape.append(f"{s['t']} {a}")
        if b:
            ratio.append(f"{s['t']} {b}")
    rep.add("배당 맞춤 이유 모양 (사건 · 배율 · 날짜 · 접수번호 · a·b · fx)", not shape,
            f"어긋남 {len(shape)}" + (f" (예: {shape[0]})" if shape else ""),
            "0 (결론별 칸 · 분할·병합·무상증자 · 10% 넘는 깨끗한 배율 · 접수번호 14자리)")
    rep.add("배당 맞춤 이유 = 배율 (사건의 곱 = dpsF · 숨긴 수익률 · 날짜는 그 사이)", not ratio,
            f"어긋남 {len(ratio)}" + (f" (예: {ratio[0]})" if ratio else ""),
            f"0 (해마다 사건의 곱 = dpsF ± {DVWHY_TOL:.1%} · nf·filed 는 b = shr · filed 는 늘어난 수를 공시가 덮음 · nc-* 는 배율 없음)")

    # 5. corp.json 의 dvWhy 는 data.json 과 같아요 (없으면 둘 다 없음)
    off = [c.get("t") for c in comps if c.get("dvWhy") != (by.get(c.get("t")) or {}).get("dvWhy")]
    rep.add("corp.json dvWhy = data.json", not off, f"다름 {len(off)}" + (f" (예: {off[0]})" if off else ""), "0")

    # 6. 경고만 (발행은 막지 않아요): 공시를 찾지 못함(nf) · 공시된 배당 그대로(filed) · 수익률을 숨김(nc-mismatch · nc-unexplained) ·
    #    조회 실패(이유 줄 없음 · 맞춤 그대로) · 스위치 꺼짐. Jack 이 하나하나 볼 수 있게 이름을 적어요
    def nm(t):
        return f"{t} {(by.get(t) or {}).get('nk') or ''}".strip()
    groups = [("공시 없음", sorted(t for t, st in st_of.items() if st == "nf")),
              ("공시된 배당 그대로", sorted(t for t, st in st_of.items() if st == "filed")),
              ("공시와 달라 수익률 숨김", sorted(t for t, st in st_of.items() if st == "nc-mismatch")),
              ("설명 못 해 수익률 숨김", sorted(t for t, st in st_of.items() if st == "nc-unexplained")),
              ("조회 실패", [t for t in why.get("failT") or [] if isinstance(t, str)]),
              ("스위치 꺼짐", [t for t in why.get("keptT") or [] if isinstance(t, str)])]
    named = [(g, ts) for g, ts in groups if ts]
    for g, ts in named:
        rep.detail(f"배당 맞춤 이유 {g}", [nm(t) for t in ts])
    rep.add("배당 맞춤 이유 경고 (공시 없음 · 공시 그대로 · 수익률 숨김 · 조회 실패)", True,
            "없음" if not named else " · ".join(f"{g} {len(ts)}: {', '.join(nm(t) for t in ts[:4])}{'…' if len(ts) > 4 else ''}"
                                               for g, ts in named),
            f"있으면 경고 (발행은 막지 않아요) · 이유 확인 {why.get('ok')}", warn=bool(named))


def _prove_cover(fx, fy, px, ev=(), exact=False):
    """dvProof.fx 가 덮을 수 있는 새 보통주 수 (유상증자는 주식 수, 사채는 ÷ 0.7) — 결정마다 그 공시일 뒤(그리고 그해 말 뒤)의 분할 · 병합 ·
    무상증자(ev: dvWhy 사건)만큼 늘려서, 오늘 주식 수로 → (수, 문제 또는 None)."""
    lo_r = dt.date(fy, 12, 31) - dt.timedelta(days=DVWHY_LOOKBACK_DAYS)
    cover = 0.0
    for x in fx:
        if not isinstance(x, dict) or set(x) != {"k", "d", "n", "rc"} or x.get("k") not in DVWHY_FX_KINDS or not _posint(x.get("n")) \
                or _real_day(x.get("d")) is None or not re.fullmatch(r"\d{14}", str(x.get("rc"))):
            return None, f"fx 칸 {x}"
        d = _real_day(x["d"])
        if d > px or (x["k"] == "rights" and d <= lo_r) or d < dt.date(fy - 2, 1, 1):
            return None, f"fx 날짜 {x['d']} 가 기간 밖"
        cut = max(d, dt.date(fy, 12, 31))
        scale = math.prod(_ev_r(e, exact) for e in ev if isinstance(e, dict) and _isnum(e.get("r")) and (_real_day(e.get("d")) or cut) > cut)
        cover += (x["n"] if x["k"] == "rights" else x["n"] / DVWHY_CB_FLOOR) * scale
    return cover, None


def dvproof_problems(s, c, px, today=None, exact=False):
    """한 종목의 dvProof → 문제 또는 None. (v19.1i — fetch_data.DivWhy.prove 의 규칙을 발행된 숫자로 다시)
    모양: v 1 · y0 (today · yearEnd · 없음) · yrs (1 · 2) 중 하나는 있어야 · c 배당 총액 3년 (원) · shr = 오늘 상장 주식 수 · yearEnd 는
    cmo · cmi · cv (· cv > 0 이면 fx) · 우선주 몫 pf · pd 는 함께 · 올해 배율의 사건 ev (있으면: 그해 말 뒤 ~ pxDate · 깨끗한 배율 ·
    곱 = dpsF[0] ± 0.5%, 없으면 dpsF[0] = 1). 새 주식 수(cv)는 dvWhy 가 아니라 이 ev 로 다시 세요 (리뷰 2026-11-15 2차: 사건의 곱이 1 이라
    dvWhy 가 없어도 같은 셈).
    올해: n = (c₀ − pf × pd) ÷ 주당 배당 · f = dpsF[0] · 되살린 해의 dps3a = 주당 배당 ÷ 배율 (원 둘째 자리) — 그래서 되살린 수익률과
    배당 총액 ÷ 시가총액의 비는 n × f ÷ shr (반올림한 dps3a 로 셈하지 않아요: 작은 배당에서 반올림만으로 경계를 넘지 않게).
      today    n × f ÷ shr = 1 ± 3% — 배당 총액 ÷ 시가총액 = 되살린 수익률 ± 3%.
      yearEnd  n ÷ cmo = 1 ± 3% · shr ≥ cmo × f × 0.97 · shr ≤ (cmi × f + cv) × 1.03 · cv = fx 가 덮는 수 (결정마다 그 뒤 사건만큼 늘린,
               오늘 주식 수) — 배당 총액 ÷ 시가총액 ÷ 되살린 수익률(= n × f ÷ shr)이 그 사이 (자기주식과 공시된 새 주식만큼만 낮을 수 있어요).
               이 시가총액 줄은 위 주식 수 부등식을 수익률 꼴로 다시 쓴 것이에요 (따로 하는 재확인은 n ÷ cmo 와 총액 c 의 대조).
    앞 해 i: dpsF[i] 가 있고 g = dpsF[i] ÷ dpsF[0] · (c₀ ÷ 주당 배당₀) ÷ (cᵢ ÷ 주당 배당ᵢ) = g ± 15% · g ≠ 1 이면 그 비가 1 ± 15% 가 아니에요.
    corp.json cash3 가 있으면 c 와 같아야 해요 (억원 둘째 자리)."""
    p = s.get("dvProof")
    base = {"v", "y0", "yrs", "c", "shr"}
    if not isinstance(p, dict) or p.get("v") != 1 or isinstance(p.get("v"), bool):
        return "칸 모양 (v)"
    y0, yrs = p.get("y0"), p.get("yrs")
    extra = (({"cmo", "cmi", "cv"} | ({"fx"} if (p.get("cv") or 0) > 0 else set())) if y0 == "yearEnd" else set()) \
        | ({"pf", "pd"} if "pf" in p or "pd" in p else set()) | ({"ev"} if y0 and "ev" in p else set())
    if set(p) != base | extra:
        return f"칸 {sorted(p)}"
    if y0 not in (None,) + PROVE_HOW or not isinstance(yrs, list) or any(i not in (1, 2) or isinstance(i, bool) for i in yrs) \
            or yrs != sorted(set(yrs)) or (y0 is None and not yrs):
        return f"y0 {y0} · yrs {yrs}"
    cc = p.get("c")
    if not isinstance(cc, list) or len(cc) != 3 or any(x is not None and not _posint(x) for x in cc):
        return "c (배당 총액 3년)"
    shr = num(s.get("shr"))
    if not _posint(p.get("shr")) or shr is None or p["shr"] != round(shr):
        return f"shr {p.get('shr')} ≠ 오늘 상장 주식 수 {s.get('shr')}"
    if is_pref(s.get("t")) or is_foreign(s.get("t")):
        return "우선주 · 해외 기업에 dvProof"
    d3, f3, a3 = _nums3(s.get("dps3")), _nums3(s.get("dpsF")), _nums3(s.get("dps3a"))
    if d3 is None or f3 is None or a3 is None or not (d3[0] or 0) > 0 or f3[0] is None or not cc[0]:
        return "배당 · 배율 칸 (올해 배당 · 배율 · 총액이 있어야 해요)"
    for i in range(3):
        cv3 = (c.get("cash3") or [None] * 3)[i] if isinstance(c.get("cash3"), list) and len(c["cash3"]) == 3 else None
        if cv3 is not None and cc[i] is not None and abs(cv3 * 1e8 - cc[i]) > 0.5e6 + 1:
            return f"c[{i}] {cc[i]:,} ≠ corp.json cash3 {cv3}억원"
    pf, pd = p.get("pf"), p.get("pd")
    if ("pf" in p) and (not _posint(pf) or not _isnum(pd) or not pd > 0 or yrs):
        return "우선주 몫 (pf 양의 정수 · pd > 0 · 우선주 배당이 있으면 앞 해는 하지 않아요)"
    n = (cc[0] - (pf * pd if "pf" in p else 0)) / d3[0]
    f = f3[0]
    if n <= 0 or not f > 0:
        return f"배당 받은 주식 수 {n:,.0f} · 배율 {f}"
    if y0:
        ev = p.get("ev") or []
        fy = s.get("fy")
        if "ev" in p:
            bad = _dvwhy_events(ev, today or px, exact)
            if bad:
                return f"ev {bad}"
            fyend = dt.date(fy, 12, 31) if isinstance(fy, int) and not isinstance(fy, bool) else None
            if fyend is None or any(not fyend < _real_day(e["d"]) <= px for e in ev):
                return f"ev 날짜가 {fy}년 말 뒤 ~ {px} 밖"
            prod = math.prod(_ev_r(e, exact) for e in ev)
            if not _same_f(prod, f, ev, exact):
                return f"ev 의 곱 {prod:.7g} ≠ 올해 배율 {f:g}" if exact else f"ev 의 곱 {prod:.4g} ≠ 올해 배율 {f:g}"
        elif abs(f - 1) > 1e-9:
            return f"올해 배율 {f:g} 인데 사건(ev)이 없어요"
        # 되살린 1주 배당 = 주당 배당 ÷ 배율 (원 둘째 자리 반올림 그대로) — 그래서 되살린 수익률(dps3a[0] ÷ 종가)과 배당 총액 ÷ 시가총액의 비는
        # n × f ÷ 오늘 주식 수예요. 반올림한 dps3a 로 비를 셈하면 아주 작은 배당(배율 뒤 2.5원 밑)에서 반올림만으로 경계를 넘을 수 있어
        # (리뷰 2026-11-15 2차: 새 실패 줄은 우리 기록이 서로 어긋날 때만) 파이프라인이 정한 그 비로 보고, dps3a 는 따로 정확히 봐요.
        if a3[0] is None or abs(a3[0] - d3[0] / f) > 0.005 + 1e-9:
            return f"dps3a[0] {a3[0]} ≠ 주당 배당 {d3[0]:g} ÷ 배율 {f:g} (원 둘째 자리)"
        rho = n * f / shr                      # = 배당 총액 ÷ 시가총액 ÷ (주당 배당 ÷ 배율 ÷ 종가)
        if y0 == "today":
            if abs(rho - 1) > PROVE_TOL + PROVE_EPS:
                return f"배당 총액 ÷ 시가총액 ÷ 되살린 수익률 {rho:.3f} (1 ± {PROVE_TOL:.0%} 이어야 · today)"
        else:
            cmo, cmi, cv = p.get("cmo"), p.get("cmi"), p.get("cv")
            if not _posint(cmo) or not _posint(cmi) or cmi < cmo or not isinstance(cv, int) or isinstance(cv, bool) or cv < 0:
                return f"cmo {cmo} · cmi {cmi} · cv {cv}"
            got = 0.0
            if cv > 0:
                got, why = _prove_cover(p.get("fx") if isinstance(p.get("fx"), list) and p.get("fx") else [None], s.get("fy"), px, ev, exact)
                if why:
                    return why
                if abs(got - cv) > 1.5:
                    return f"cv {cv:,} ≠ fx 가 덮는 수 {got:,.0f}"
            if abs(n / cmo - 1) > PROVE_TOL + PROVE_EPS:
                return f"배당 받은 주식 수 {n:,.0f} ÷ 그해 말 유통 주식 수 {cmo:,} = {n / cmo:.3f}"
            if shr < cmo * f * (1 - PROVE_TOL) - 1 or shr > (cmi * f + cv) * (1 + PROVE_TOL) + 1:
                return f"오늘 주식 수 {shr:,.0f} 가 {cmo * f:,.0f} ~ {cmi * f + cv:,.0f} 밖 (그해 말 유통 · 발행 × {f:g} + 새 주식)"
            # 배당 총액 ÷ 시가총액 ÷ 되살린 수익률 = n × f ÷ 오늘 주식 수: 자기주식(그해 말 발행 − 유통)과 공시된 새 주식(cv)만큼만 1 보다 낮아요
            lo, hi = n * f / ((cmi * f + cv) * (1 + PROVE_TOL)), n / (cmo * (1 - PROVE_TOL))
            if not lo - PROVE_EPS <= rho <= hi + PROVE_EPS:
                return f"배당 총액 ÷ 시가총액 ÷ 되살린 수익률 {rho:.3f} 가 {lo:.3f} ~ {hi:.3f} 밖 (자기주식 · 새 주식으로 설명되지 않아요)"
    for i in yrs:
        if f3[i] is None or not (d3[i] or 0) > 0 or not cc[i]:
            return f"앞 해 {i} 의 배율 · 배당 · 총액"
        if a3[i] is None or abs(a3[i] - d3[i] / f3[i]) > 0.005 + 1e-9:
            return f"앞 해 {i}: dps3a {a3[i]} ≠ 주당 배당 {d3[i]:g} ÷ 배율 {f3[i]:g} (원 둘째 자리)"
        g = f3[i] / f
        rr = (cc[0] / d3[0]) / (cc[i] / d3[i])
        if abs(rr / g - 1) > PROVE_DRIFT + PROVE_EPS or (abs(g - 1) > 1e-6 and abs(rr - 1) <= PROVE_DRIFT):
            return f"앞 해 {i}: 배당 받은 주식 수의 비 {rr:.3f} 와 배율의 비 {g:g}"
    return None


def exact_bonus_problem(s, c, px, today=None):
    """v19.1j (안전 규칙 변경 · Jack 의 yes 2026-11-15 답 12): 이 종목의 깨끗하지 않은 배율을 받아도 되는지 → None (받아요) 또는 이유.
    깨끗하지 않은 배율 = 관문이 받는 배율(_factor_ok)이 아닌 dpsF, 또는 깨끗한 분할 배율(_dvwhy_clean)이 아닌 사건 (×1.5 처럼 dpsF 로는 받는
    배율이어도 사건 하나로는 아니에요). 그런 해마다 세 조건을 모두: (가) dvWhy ok 의 사건과 dvProof 의 사건 중 깨끗하지 않은 배율은 모두 무상증자
    (k bonus · x > 0 · r = 1 + x ± 1e-6) · (나) 그해 12월 31일 뒤 ~ pxDate 사건의 곱(무상증자는 1 + x)이 dpsF 와 1e-6 안 (올해는 dvProof 의 사건으로도)
    · (다) 그 해를 이번 증명이 되살렸고 (올해 y0 · 앞 해 yrs) dvWhy · dvProof 검사를 모두 지나요. 깨끗한 배율뿐이면 '필요 없음'."""
    f3 = _nums3(s.get("dpsF"))
    if f3 is None or px is None:
        return "dpsF · pxDate 없음"
    p, w, fy = s.get("dvProof"), s.get("dvWhy"), s.get("fy")
    evw = w.get("ev") if isinstance(w, dict) and isinstance(w.get("ev"), list) else []
    evp = p.get("ev") if isinstance(p, dict) and isinstance(p.get("ev"), list) else []
    odd_ev = [e for e in evw + evp if not (isinstance(e, dict) and _isnum(e.get("r")) and _dvwhy_clean(e["r"]))]
    if not odd_ev and all(f is None or _factor_ok(f) for f in f3):
        return "깨끗한 배율뿐 (필요 없음)"
    if not isinstance(p, dict):
        return "dvProof 없음"
    if not isinstance(w, dict) or w.get("st") != "ok" or not evw:
        return "dvWhy ok (사건) 없음"
    if not isinstance(fy, int) or isinstance(fy, bool):
        return "사업보고서 연도 없음"
    for e in evw + evp:
        if not isinstance(e, dict) or not _isnum(e.get("r")) or _real_day(e.get("d")) is None:
            return "사건 모양"
        if not _dvwhy_clean(e["r"]) and not _exact_bonus(e):
            return f"깨끗하지 않은 배율 {e['r']} 의 사건이 무상증자(r = 1 + x)가 아니에요 ({e.get('k')})"
    yrs = p.get("yrs") if isinstance(p.get("yrs"), list) else []
    for i in range(3):
        if f3[i] is None or f3[i] == 1 and not odd_ev:
            continue
        cut = dt.date(fy - i, 12, 31)
        evi = [e for e in evw if cut < _real_day(e["d"]) <= px]
        if _factor_ok(f3[i]) and all(_dvwhy_clean(e["r"]) for e in evi):
            continue                                       # 이 해는 깨끗한 배율 — 예전 규칙 그대로
        if (i == 0 and p.get("y0") not in PROVE_HOW) or (i > 0 and i not in yrs):
            return f"{fy - i}년 배율 {f3[i]:g} 을 이번 증명이 되살리지 않았어요"
        prod = math.prod(_ev_r(e, True) for e in evi)
        if abs(prod - f3[i]) > EXACT_TOL:
            return f"{fy - i}년 사건의 곱 {prod:.7g} ≠ 배율 {f3[i]:g} (± {EXACT_TOL:g})"
    if p.get("y0") and any(not _dvwhy_clean(e["r"]) for e in evp) and abs(math.prod(_ev_r(e, True) for e in evp) - f3[0]) > EXACT_TOL:
        return f"dvProof 사건의 곱 ≠ 올해 배율 {f3[0]:g} (± {EXACT_TOL:g})"
    a, b = dvwhy_problems(s, px, today or px, exact=True)
    if a or b:
        return f"dvWhy: {a or b}"
    q = dvproof_problems(s, c, px, today, exact=True)
    return f"dvProof: {q}" if q else None


def exact_bonus_set(data, kr, comps, today=None):
    """답 12 의 예외를 받는 국내 종목 코드 (exact_bonus_problem 이 None). 깨끗하지 않은 dpsF 나 사건이 있는 종목만 봐요."""
    px = day(data.get("pxDate")) if is_day(data.get("pxDate")) else None
    cby = {c.get("t"): c for c in comps or []}
    out = set()
    for s in kr:
        if ("dvProof" in s or "dvWhy" in s or "dpsF" in s) and exact_bonus_problem(s, cby.get(s.get("t")) or {}, px, today) is None:
            out.add(s["t"])
    return out


def check_v191i(rep, data, kr, by, comps, pdata, today=None, mode="publish"):
    """v19.1i 새 줄 (Jack 2026-11-14 item 5): 배당 기준 증명 (dvProof · divCheck.proof).
    mode: Jack 의 상시 규칙 (2026-11-19) 의 '비운 줄이 N 을 넘음' 실패는 발행 때만 (사이트 점검 live 는 경고 · check_v191j_lines)."""
    dc = data.get("divCheck")
    own = own_drop_get(data, DIV_LINE_DROP_KEY)
    if not isinstance(dc, dict):
        if isinstance(own, dict) and own["n"]:            # 상시 규칙: 기록이 없어도 비운 수는 봐요 (줄을 맞춰 볼 기록이 없어요)
            check_v191j_lines(rep, {}, {}, kr, by, pdata, data=data, mode=mode)
        return
    pf = dc.get("proof")
    name = "배당 기준 증명 기록 (divCheck.proof)"
    if not isinstance(pf, dict):
        had = isinstance(((pdata or {}).get("divCheck") or {}).get("proof"), dict)
        rep.add(name, not had, "없음 — 직전 발행본에는 있었어요" if had else "없음 (v19.1i 전 형식이라 새 검사를 건너뛰어요)",
                "있어야 함 (v19.1i 전 데이터만 경고)", warn=not had)
        stray = [s["t"] for s in kr if "dvProof" in s or "dvLine" in s]
        if stray:
            rep.add("되살린 배당수익률 = 배당 총액 ÷ 시가총액 (dvProof)", False, f"기록 없이 dvProof · dvLine {len(stray)} (예: {stray[0]})", "0")
        if isinstance(own, dict) and own["n"]:            # 상시 규칙: 기록이 없어도 비운 수는 봐요
            check_v191j_lines(rep, dc, {}, kr, by, pdata, data=data, mode=mode)
        return
    px = day(data.get("pxDate")) if is_day(data.get("pxDate")) else None
    kr_t = {s.get("t") for s in kr}
    has = [s for s in kr if "dvProof" in s]
    cby = {c.get("t"): c for c in comps}

    # 1. 기록: v1 · 결과마다 수 = 종목 · 이름 목록은 실제 종목이고 dvProof 가 없어요 · 숨긴 종목(hidT)은 dvWhy nc-*
    bad = []
    if pf.get("v") != 1:
        bad.append(f"v{pf.get('v')}")
    for k in PROVE_KEYS:
        if not isinstance(pf.get(k), int) or isinstance(pf.get(k), bool) or pf[k] < 0:
            bad.append(f"{k} {pf.get(k)}")
    y0n = collections.Counter((s.get("dvProof") or {}).get("y0") for s in has if isinstance(s.get("dvProof"), dict))
    yrsn = sum(1 for s in has if isinstance(s.get("dvProof"), dict) and (s["dvProof"].get("yrs") or []))
    for k, v in (("today", y0n.get("today", 0)), ("yearEnd", y0n.get("yearEnd", 0)), ("years", yrsn)):
        if pf.get(k) != v:
            bad.append(f"{k} {pf.get(k)}≠{v}")
    seen = collections.Counter()
    for k in PROVE_HID:
        lst = pf.get(k + "T")
        if not isinstance(lst, list) or not all(isinstance(t, str) for t in lst) or len(set(lst)) != len(lst) \
                or len(lst) != pf.get(k) or any(t not in kr_t for t in lst):
            bad.append(f"{k}T")
            continue
        seen.update(lst)
        if any("dvProof" in by[t] or (k != "fail" and num(by[t].get("dyt")) is not None) for t in lst):
            bad.append(f"{k}T 인데 dvProof 나 배당수익률이 있어요")       # 조회 실패는 앞 해만 못 한 종목일 수 있어요 (올해 수익률은 있어요)
        elif k == "line" and any((by[t].get("dvWhy") or {}).get("st") != "nc-unexplained" for t in lst):
            bad.append("lineT 인데 dvWhy nc-unexplained 가 없어요 (Jack 의 줄)")
    if any(v > 1 for v in seen.values()):
        bad.append("한 종목이 이유 목록 둘 이상에")
    # Jack 의 줄 (dvLine = 1): 앱이 읽는 표시 — lineT 의 종목에만, 그리고 그 종목엔 꼭 (리뷰 2026-11-15 2차: 줄은 증명이 line 이라고 한 종목에만)
    # v19.1j: dvLine 2 · 3 · 4 (답 11 · 13 · Jack 2026-11-19 의 줄)은 divCheck.proofSub 가 있을 때만 — 그 맞춤은 아래 '숨긴 배당수익률의 줄' 줄이 봐요. 1 의 규칙은 그대로.
    sub_ok = isinstance(dc.get("proofSub"), dict)
    vals = (1, 2, 3, 4) if sub_ok else (1,)
    marked = {s2["t"] for s2 in kr if s2.get("dvLine") == 1 and not isinstance(s2.get("dvLine"), bool)}
    odd = [s2["t"] for s2 in kr if "dvLine" in s2 and (s2["dvLine"] not in vals or isinstance(s2["dvLine"], bool) or is_pref(s2["t"])
                                                         or num(s2.get("dyt")) is not None or "dvProof" in s2
                                                         or (s2["dvLine"] == 1 and (s2.get("dvWhy") or {}).get("st") != "nc-unexplained"))]
    lst = pf.get("lineT") if isinstance(pf.get("lineT"), list) else []
    if odd or marked != set(lst):
        bad.append(f"Jack 의 줄 표시(dvLine) {len(marked)} · lineT {len(lst)} 가 다르거나 맞지 않는 종목에 있어요"
                   + (f" (예: {(odd or sorted(marked ^ set(lst)))[0]})" if odd or marked ^ set(lst) else ""))
    rep.add(name, not bad, "맞음" if not bad else " · ".join(bad[:4]),
            "v1 · today·yearEnd·years = dvProof 종목 · 되살리지 않은 이유(" + "·".join(PROVE_HID) + ")마다 그 수의 이름 · "
            "그 종목은 dvProof 없음 · 조회 실패 말고는 배당수익률도 없음 · line 은 dvWhy nc-unexplained · dvLine = lineT")

    # 2. 근거를 발행된 숫자로 다시: 되살린 수익률 = 배당 총액 ÷ 시가총액 (자기주식 · 공시된 새 주식만큼만 달라요) · 앞 해 배율
    probs = []
    ex = exact_bonus_set(data, kr, comps, today)          # v19.1j 답 12
    for s in has:
        why = dvproof_problems(s, cby.get(s.get("t")) or {}, px, today, exact=s["t"] in ex) if px else "pxDate 없음"
        if why:
            probs.append(f"{s['t']} {why}")
    rep.add("되살린 배당수익률 = 배당 총액 ÷ 시가총액 (dvProof)", not probs,
            f"되살림 {len(has)} · 어긋남 {len(probs)}" + (f" (예: {probs[0]})" if probs else ""),
            f"0 (today: 총액 ÷ 시가총액 = 수익률 ± {PROVE_TOL:.0%} · yearEnd: 그해 말 유통 주식 수 ± {PROVE_TOL:.0%} · 오늘 주식 수는 "
            f"그 수 × 배율 ~ (발행 주식 수 + 공시된 새 주식) × 배율 · 앞 해 ± {PROVE_DRIFT:.0%})")
    if probs:
        rep.detail("배당 기준 증명이 어긋난 종목", probs)

    # 3. 경고만: 숨긴 종목(공시로 맞추지 못함) · 배당 표가 어긋난 종목 · 조회 실패 — 이름과 함께 (발행은 막지 않아요)
    def nm(t):
        return f"{t} {(by.get(t) or {}).get('nk') or ''}".strip()
    groups = [(PROVE_HID_KO[k], [t for t in pf.get(k + "T") or [] if isinstance(t, str) and t in kr_t]) for k in PROVE_HID]
    named = [(g, ts) for g, ts in groups if ts]
    psub = dc.get("proofSub") if isinstance(dc.get("proofSub"), dict) else {}
    for g, ts in named:
        k = next((k for k in PROVE_HID if PROVE_HID_KO[k] == g), None)
        sub = psub.get(k) if isinstance(psub.get(k), dict) else {}
        rep.detail(f"배당 기준 증명 {g}", [nm(t) + (f" ({PROVE_SUB_KO.get(sub[t], sub[t])}"
                                                    + (" · 줄" if sub[t] in PROVE_SUB_LINE.get(k, ()) else " · 줄 없음") + ")"
                                                    if isinstance(sub.get(t), str) else "") for t in ts])
    rep.add("배당 기준 증명 경고 (되살리지 않은 이유 · 조회 실패)", True,
            "없음" if not named else " · ".join(f"{g} {len(ts)}: {', '.join(nm(t) for t in ts[:4])}{'…' if len(ts) > 4 else ''}"
                                               for g, ts in named),
            f"있으면 경고 (발행은 막지 않아요) · 되살림 {len(has)}", warn=bool(named))
    check_v191j_lines(rep, dc, pf, kr, by, pdata, data=data, mode=mode)


def _line_ko(v):
    return f"줄 {v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else "줄 없음"


def div_line_bad_rows(kr, dc):
    """Jack 의 상시 규칙 (2026-11-19) · #142 의 우리 처리 검사: 숨긴 배당수익률의 줄 (dvLine 2 · 3 · 4) 중 기록(divCheck.proofSub)과 맞지 않는 종목
    → (행 [(코드, 이유, 종류)], 기록 문제 [글], 기록이 정한 줄 {코드: 줄}, 확인한 기록 {rights · data 중 모양이 맞아 줄을 정할 수 있었던 것}).
    파이프라인(fetch_data.own_blank_div_lines)과 관문(check_v191j_lines)이 같은 함수를 써요. (순수 함수)
    종류 shown — 종목에 줄 2 · 3 · 4 가 있는데 기록이 그 줄을 정하지 않음: 다른 줄 · 기록이 줄 없는 경우 · 기록에 없는 종목 · 그 줄을 정하는
                기록(2 → rights · 3 · 4 → data)이 없거나 모양이 틀려 확인할 수 없음 · 우선주 · 배당수익률(dyt)이 보이는 종목 · 되살린(dvProof) 종목.
                앱이 그 자리에 틀릴 수 있는 이유 줄을 보여요 → 파이프라인은 그 종목의 줄(dvLine)만 비워요 (숫자는 그대로 · 빈 배당수익률에 이유 줄이
                없을 뿐 틀린 말은 없어요). 관문: 남아 있으면 실패 (틀린 이유 줄 = 틀린 것으로 봐요).
    종류 missing — 기록은 줄 2 · 3 · 4 를 정했는데 종목에 그 줄이 없음: 빈 배당수익률에 이유 줄이 없을 뿐 틀린 것을 보이지 않아요 (비울 것이
                없어요 · 수에는 들어가요). 관문: 경고.
    줄 1 (Jack 의 줄 · v19.1i) · 다른 값의 줄은 '배당 기준 증명 기록' 줄의 예전 규칙 그대로 (이 함수는 보지 않아요)."""
    dc = dc if isinstance(dc, dict) else {}
    sub, pf = dc.get("proofSub"), dc.get("proof")
    pf = pf if isinstance(pf, dict) else {}
    kr_t = {s.get("t") for s in kr}
    probs, want, ok_k = [], {}, set()
    if not isinstance(sub, dict):
        probs.append("기록 없음 (divCheck.proofSub)")
    else:
        top = sub.get("v") == 1 and not isinstance(sub.get("v"), bool) and set(sub) == {"v"} | set(PROVE_SUB)
        if not top:
            probs.append(f"모양 {sorted(map(str, sub))} · v{sub.get('v')}")
        for k, subs in PROVE_SUB.items():
            m = sub.get(k)
            lst = pf.get(k + "T")
            lst = lst if isinstance(lst, list) and all(isinstance(t, str) for t in lst) else None
            if not isinstance(m, dict) or lst is None or set(m) != set(lst) or any(t not in kr_t for t in m):
                probs.append(f"{k}: proof 의 {k}T 와 다른 종목")
                continue
            odd = [t for t, v in m.items() if not isinstance(v, str) or v not in subs]
            if odd:
                probs.append(f"{k}: 모르는 경우 {m[odd[0]]!r} ({odd[0]})")
            if top:
                ok_k.add(k)
                want.update({t: PROVE_SUB_LINE[k][v] for t, v in m.items() if isinstance(v, str) and v in PROVE_SUB_LINE[k]})
    rows = []
    for s in kr:
        v, t = s.get("dvLine"), s.get("t")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v not in DIV_LINE_OF:
            continue
        why = ("우선주에 줄" if is_pref(t) else "배당수익률(dyt)이 보이는 종목에 줄" if num(s.get("dyt")) is not None
               else "되살린 배당수익률(dvProof)이 있는 종목에 줄" if "dvProof" in s
               else f"기록(proofSub.{DIV_LINE_OF[v]})으로 확인할 수 없는 {_line_ko(v)}" if DIV_LINE_OF[v] not in ok_k
               else None if want.get(t) == v else f"기록은 {_line_ko(want.get(t))} 인데 {_line_ko(v)}")
        if why:
            rows.append((t, why, "shown"))
    shown = {r[0] for r in rows}
    have = {s.get("t"): s.get("dvLine") for s in kr}
    for t, v in sorted(want.items()):
        if t not in shown and (have.get(t) != v or isinstance(have.get(t), bool)):
            rows.append((t, f"기록은 {_line_ko(v)} 인데 줄 표시 없음 (이유 줄 없이 빈칸)", "missing"))
    return rows, probs, want, ok_k


def check_v191j_lines(rep, dc, pf, kr, by, pdata, data=None, mode="publish"):
    """v19.1j 새 줄 (Jack 2026-11-15 답 11 · 13 · 2026-11-19): 숨긴 배당수익률의 줄 — divCheck.proofSub 와 종목의 dvLine 2 · 3 · 4 가 꼭 맞아요 (우리 기록끼리).
    proofSub: v1 · rights · data 마다 {코드: 경우} 이고, 그 코드들 = divCheck.proof 의 rightsT · dataT, 경우는 정해진 것 (PROVE_SUB) ·
    dvLine 2 = rights 중 주주배정(sh) · dvLine 3 = data 중 배당 표가 회사의 주식 수와 실제로 어긋남(div) · dvLine 4 = data 중 회사 공시에 조각이
    빠짐(nototal · nostk · pref0 · nopfo · prefmix) — 그 종목엔 꼭, 다른 종목엔 없음 (PROVE_SUB_LINE). data 의 other (파이프라인이 이름을
    붙이지 않은 배당 표 이유 · 리뷰 2026-11-19)는 줄이 없어야 하고, 하나라도 있으면 맞더라도 이 줄이 경고예요. 없으면 v19.1j 전
    데이터라 경고 한 줄만 — 직전 발행본에 있었는데 빠지면 실패 (줄 표시 2 · 3 · 4 는 위 '배당 기준 증명 기록' 줄이 이 기록 없이는 막아요).
    Jack 의 상시 규칙 (2026-11-19 · 우리 처리를 보는 검사): data.json ownDrop.divLine 이 있는 파일은 파이프라인이 같은 함수(div_line_bad_rows)로
    맞지 않는 줄을 비우고 발행했어요 → _div_lines_own. ownDrop.divLine 이 없는 파일은 아래 예전 규칙 그대로 (모양이 틀린 기록이면 경고를 더해요)."""
    name = "숨긴 배당수익률의 줄 (divCheck.proofSub · dvLine 2 · 3 · 4)"
    own = own_drop_get(data, DIV_LINE_DROP_KEY)
    if isinstance(own, dict):
        _div_lines_own(rep, name, own, dc, kr, pdata, mode)
        return
    n0 = len(rep.rows)
    _div_lines_old(rep, name, dc, pf, kr, pdata)
    if own is False:                                       # 기록 모양이 틀림: 예전 규칙 그대로에 경고를 더해요
        for i in range(n0, len(rep.rows)):
            a, b, c, st = rep.rows[i]
            if a == name:
                rep.rows[i] = (a, b + " · 비운 줄 기록(ownDrop.divLine) 모양이 틀림", c, "WARN" if st == "PASS" else st)


def div_lines_lost(pdata, checked):
    """직전 발행본(pdata)의 줄 2 · 3 · 4 중 오늘 기록으로 확인할 수 없는 것 (그 줄을 정하는 기록 부분이 checked 에 없음 · 기록이 없거나 모양이
    틀림) → 그 종목 코드 [정렬]. 그 종목은 이번 실행에서 이유 줄을 잃어요 (리뷰 1차 S2). 관문(_div_lines_own)과 파이프라인 로그
    (fetch_data.own_blank_div_lines)가 같이 써요. 줄 값은 숫자만 봐요 (리뷰 2차: 목록 같은 값으로 관문이 멈추지 않게). (순수 함수)"""
    blind = set(PROVE_SUB) - set(checked or ())
    if not isinstance(pdata, dict) or not blind:
        return []
    out = []
    for s in kr_stocks(pdata):
        v = s.get("dvLine")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v in DIV_LINE_OF and DIV_LINE_OF[v] in blind:
            out.append(s.get("t"))
    return sorted(t for t in out if isinstance(t, str))


def _div_lines_own(rep, name, own, dc, kr, pdata, mode):
    """check_v191j_lines 의 상시 규칙 줄 (ownDrop.divLine 이 있는 파일). 실패: 맞지 않는 줄이 남음 (shown · 틀린 이유 줄) · 이 실행에서 줄을 잃은
    종목이 DIV_LINE_BLANK_MAX 를 넘음 (발행 때만 · 사이트 점검은 경고). 그 수 = 서로 다른 종목 수: 비운 줄 (ownDrop.divLine.rows) · 남은 나쁜 행 ·
    오늘 기록(proofSub)이 없거나 그 부분의 모양이 틀려 줄을 정할 수 없는데 직전 발행본에 있던 그 부분의 줄 2 · 3 · 4 (리뷰 1차 S2: 기록과 줄이 함께
    사라지면 비울 것이 없어 0 으로 세어졌어요 · 리뷰 2차: 둘은 보통 다른 종목이라 큰 값이 아니라 합쳐 세요). 기록에 이름이 30개까지만 있어 ownDrop n
    과도 견줘 큰 값 (n ≤ 30 이면 정확). 경고: 그 수 1~N · 기록은 줄을 정했는데 표시가 없음 (missing) · 기록 문제 · 기록이 없음 · 이름 없는 이유(other)."""
    dc = dc if isinstance(dc, dict) else {}
    left, probs, want, checked = div_line_bad_rows(kr, dc)
    shown = [r for r in left if r[2] == "shown"]
    missing = [r for r in left if r[2] == "missing"]
    sub = dc.get("proofSub")
    had = not isinstance(sub, dict) and isinstance(((pdata or {}).get("divCheck") or {}).get("proofSub"), dict)
    blind = set(PROVE_SUB) - checked                                       # 오늘 기록으로 줄을 정할 수 없는 부분 (rights · data)
    lost = div_lines_lost(pdata, checked)
    n = max(own["n"], len(left), len(set(lost) | {r[0] for r in own["rows"]} | {r[0] for r in left}))
    many = n > DIV_LINE_BLANK_MAX
    n2, n3, n4 = (sum(1 for v in want.values() if v == x) for x in (2, 3, 4))
    dm = sub.get("data") if isinstance(sub, dict) and isinstance(sub.get("data"), dict) else {}
    oth = sorted(t for t, v in dm.items() if v == "other")
    rest = sum(len(sub[k]) for k in checked) - n2 - n3 - n4               # 확인한 기록만 세요 (리뷰 1차: 모양이 틀린 기록의 종목을 '줄 없음'으로 세지 않게)
    parts = ([f"비운 줄 {own['n']}: {own_drop_text(own['rows'], own['n'])}"] if own["n"] else []) \
        + ([f"줄을 잃은 종목이 기준 {DIV_LINE_BLANK_MAX} 을 넘음 ({n})"] if many else []) \
        + ([f"기록과 맞지 않는 줄이 남음 {len(shown)}: {own_drop_text(shown)}"] if shown else []) \
        + ([f"기록은 줄인데 표시 없음 {len(missing)} (이유 줄 없이 빈칸): {own_drop_text(missing)}"] if missing else []) \
        + (["기록 없음 — 직전 발행본에는 있었어요"] if had else []) \
        + ([f"오늘 기록으로 확인할 수 없는 직전 발행본의 줄 2 · 3 · 4 {len(lost)}곳: {', '.join(lost[:10])}{'…' if len(lost) > 10 else ''}"]
           if lost else []) \
        + [x for x in probs if not (x.startswith("기록 없음") and had)] \
        + [f"유상증자 줄 {n2} · 배당 자료 줄 {n3} · " + (f"빠진 자료 줄 {n4} · " if n4 else "") + f"줄 없음 {rest}"
           + (f" (확인하지 못한 기록: {' · '.join(sorted(blind))})" if blind else "")] \
        + ([f"이름 없는 배당 표 이유 {len(oth)}곳 (줄 없음): {', '.join(oth[:4])}{'…' if len(oth) > 4 else ''}"] if oth else [])
    rep.add(name, not (shown or (many and mode != "live")), " · ".join(parts),
            f"Jack 의 상시 규칙 (2026-11-19): 기록과 맞지 않는 줄은 파이프라인이 비우고 발행 (ownDrop.divLine) · 실패는 줄을 잃은 종목 > {DIV_LINE_BLANK_MAX} "
            "(비운 줄 · 기록이 없거나 틀려 확인할 수 없는 직전 발행본의 줄 · 사이트 점검은 경고) 또는 맞지 않는 줄이 남음 · 비운 줄 · 표시 없는 줄 · 기록 문제 · "
            "이름 없는 이유(other)는 경고 · dvLine 2 = 주주배정(sh) · "
            "3 = 배당 표가 주식 수와 실제로 어긋남(div) · 4 = 회사 공시에 조각이 빠짐(nototal · nostk · pref0 · nopfo · prefmix)",
            warn=bool(own["n"] or missing or probs or oth or many or lost))
    if own["n"]:
        rep.detail("파이프라인이 비운 숨긴 배당수익률의 줄 (ownDrop.divLine)", [f"{t}: {w}" for t, w in own["rows"]]
                   + ([f"… 외 {own['n'] - len(own['rows'])}건"] if own["n"] > len(own["rows"]) else []))


def _div_lines_old(rep, name, dc, pf, kr, pdata):
    """check_v191j_lines 의 예전 규칙 (ownDrop.divLine 이 없는 파일 · #142 그대로)."""
    sub = dc.get("proofSub")
    if not isinstance(sub, dict):
        had = isinstance(((pdata or {}).get("divCheck") or {}).get("proofSub"), dict)
        rep.add(name, not had, "없음 — 직전 발행본에는 있었어요" if had else "없음 (v19.1j 전 형식이라 새 검사를 건너뛰어요)",
                "있어야 함 (v19.1j 전 데이터만 경고)", warn=not had)
        return
    kr_t = {s.get("t") for s in kr}
    bad, want = [], {}
    if sub.get("v") != 1 or isinstance(sub.get("v"), bool) or set(sub) != {"v"} | set(PROVE_SUB):
        bad.append(f"모양 {sorted(sub)} · v{sub.get('v')}")
    for k, subs in PROVE_SUB.items():
        m = sub.get(k)
        lst = pf.get(k + "T") if isinstance(pf.get(k + "T"), list) else None
        if not isinstance(m, dict) or lst is None or set(m) != set(lst) or any(t not in kr_t for t in m):
            bad.append(f"{k}: proof 의 {k}T 와 다른 종목")
            continue
        odd = [t for t, v in m.items() if v not in subs]
        if odd:
            bad.append(f"{k}: 모르는 경우 {m[odd[0]]!r} ({odd[0]})")
        want.update({t: PROVE_SUB_LINE[k][v] for t, v in m.items() if v in PROVE_SUB_LINE[k]})
    got = {s["t"]: s["dvLine"] for s in kr if s.get("dvLine") in (2, 3, 4) and not isinstance(s.get("dvLine"), bool)}
    if not bad and got != want:
        diff = sorted(set(got.items()) ^ set(want.items()))
        bad.append(f"줄 표시 {len(got)} · 기록 {len(want)} 가 달라요 (예: {diff[0][0]} {diff[0][1]})")
    n2, n3, n4 = (sum(1 for v in want.values() if v == n) for n in (2, 3, 4))
    dm = sub.get("data") if isinstance(sub.get("data"), dict) else {}
    oth = sorted(t for t, v in dm.items() if v == "other")                     # 리뷰 2026-11-19: 이름을 붙이지 않은 배당 표 이유 → 경고
    rep.add(name, not bad, (f"유상증자 줄 {n2} · 배당 자료 줄 {n3} · " + (f"빠진 자료 줄 {n4} · " if n4 else "") + "줄 없음 "
                            f"{sum(len(sub.get(k) or {}) for k in PROVE_SUB if isinstance(sub.get(k), dict)) - n2 - n3 - n4}"
                            + (f" · 이름 없는 배당 표 이유 {len(oth)}곳 (줄 없음): {', '.join(oth[:4])}{'…' if len(oth) > 4 else ''}" if oth else ""))
            if not bad else " · ".join(bad[:3]),
            "v1 · rights · data 의 종목 = proof 의 rightsT · dataT · dvLine 2 = 주주배정(sh) · 3 = 배당 표가 주식 수와 실제로 어긋남(div) · "
            "4 = 회사 공시에 조각이 빠짐(nototal · nostk · pref0 · nopfo · prefmix) — 그 종목에만 · 이름 없는 이유(other)는 경고",
            warn=bool(oth))


# ── 파일 읽기 ───────────────────────────────────────────────
def load_dir(path):
    out = {}
    for f in FILES:
        with open(os.path.join(path, f), encoding="utf-8") as fh:
            out[f[:-5]] = strict_loads(fh.read(), f)
    return out


def load_git(ref, files=FILES):
    out = {}
    for f in files:
        text = subprocess.run(["git", "show", f"{ref}:{f}"], capture_output=True, text=True, check=True).stdout
        out[f[:-5]] = strict_loads(text, f"{ref}:{f}")
    return out


def load_prev(prev_dir, prev_ref):
    """직전 발행본의 data.json 을 엄격하게 읽어요. corp.json 은 표시(stmtCur) 비교에만 따로 느슨하게 읽어요 (load_prev_corp).
    v19.6a: macro.json 은 환율 이력 비교(경고만)에만 써서, 읽지 못하면 없이 해요 (그 때문에 관문이 멈추거나 다른 줄이 바뀌지
    않아요). disc 는 비교에 안 써요."""
    if prev_dir:
        with open(os.path.join(prev_dir, "data.json"), encoding="utf-8") as fh:
            out = {"data": strict_loads(fh.read(), "data.json")}
        try:
            with open(os.path.join(prev_dir, "macro.json"), encoding="utf-8") as fh:
                out["macro"] = strict_loads(fh.read(), "macro.json")
        except Exception as e:
            print(f"· 직전 발행본의 macro.json 을 읽지 못해 환율 이력 비교(경고 줄) 없이 해요: {type(e).__name__}: {str(e)[:120]}")
        return out
    out = load_git(prev_ref, files=("data.json",))
    try:
        out.update(load_git(prev_ref, files=("macro.json",)))
    except Exception as e:
        print(f"· 직전 발행본의 macro.json 을 읽지 못해 환율 이력 비교(경고 줄) 없이 해요: {type(e).__name__}: {str(e)[:120]}")
    return out


def load_prev_corp(prev_dir, prev_ref):
    """직전 발행본의 corp.json — 원화가 아닌 재무제표 표시(stmtCur) 비교에만 써요 (check_stmt_marks). 비교에 필요한 칸만 보니 느슨하게
    읽어요 (NaN 이 있어도 읽혀요): 직전 발행본의 다른 문제로 오늘 발행이 막히지 않게요 (load_prev 와 같은 생각)."""
    if prev_dir:
        with open(os.path.join(prev_dir, "corp.json"), encoding="utf-8") as fh:
            return json.loads(fh.read())
    r = subprocess.run(["git", "show", f"{prev_ref}:corp.json"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git show {prev_ref}:corp.json → {r.returncode}: {(r.stderr or '').strip()[:160]}")
    return json.loads(r.stdout)


def _annotate_error(text):
    """GitHub Actions 안에서만: 관문이 표를 만들기 전에 멈춘 이유도 알림(::error::)으로 남겨요 (매일 아침 점검이 읽어요)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::error title=발행 관문 실패::" + _gh_escape(text), flush=True)


def main(argv=None):
    """관문 실행. 예상하지 못한 오류로 멈추면 알림을 하나 남기고 그 오류를 그대로 다시 던져요 (삼키지 않아요)."""
    try:
        return _main(argv)
    except Exception as e:
        _annotate_error(f"관문이 오류로 멈췄어요: {type(e).__name__}: {str(e)[:300]}")
        raise


def _main(argv=None):
    ap = argparse.ArgumentParser(description="뱁새 발행 관문")
    ap.add_argument("--dir", default=".", help="검사할 네 파일이 있는 폴더")
    ap.add_argument("--prev-ref", default="HEAD", help="직전 발행본의 git ref (기본 HEAD)")
    ap.add_argument("--prev-dir", default=None, help="직전 발행본 폴더 (git 대신)")
    ap.add_argument("--bootstrap", action="store_true", help="직전 발행본 비교를 건너뜀 — 첫 실행 한 번만")
    ap.add_argument("--live", action="store_true", help="사이트 점검: 절대 기준만")
    ap.add_argument("--today", default=None, help="오늘 날짜(KST) 바꾸기 — 시험용")
    ap.add_argument("--daum-limit", type=float, default=None, metavar="SECONDS",
                    help=f"--live 에서 관문의 다음 확인 전체 시간 한도 (초 · {PX_ALT_LIVE_BUDGET_S} 이상 · Jack 2026-11-20 · 배포만). "
                         f"없으면 환경 변수 {PX_ALT_LIMIT_ENV} (deploy.yml 관문 단계), 그것도 없으면 한도 없음 (감시 · 예전 그대로). 발행 관문은 쓰지 않아요")
    ap.add_argument("--daum-refuse-skip", action="store_true",
                    help=f"--live 에 한도도 있을 때만: 다음이 아예 거절하면 그만 묻고 경고로 건너뛰어요 (Jack 2026-11-21 · 코드 배포만). "
                         f"없으면 환경 변수 {PX_ALT_REFUSE_ENV} (deploy.yml 관문 단계 · 코드 배포만 1)")
    a = ap.parse_args(argv)
    now = dt.datetime.now(KST)
    today = day(a.today) if a.today else now.date()
    mode = "live" if a.live else ("bootstrap" if a.bootstrap else "publish")
    print(f"뱁새 발행 관문 · 오늘(KST) {today} · 모드 {mode}")
    if mode == "bootstrap":
        print("!! --bootstrap: 직전 발행본과의 비교를 건너뛰어요. 첫 실행 한 번만 써야 해요.")
    # 2026-11-20 (Jack: "Yes to 10 minutes" — 배포만): 다음 확인의 시간 한도는 받았을 때만 (deploy.yml 관문 단계의 환경 변수 · 또는 --daum-limit).
    # 감시(watchdog.py)는 받지 않아요 (예전 그대로 한도 없이). 발행 · bootstrap 은 받아도 쓰지 않아요. 짧은 한도(더 자주 건너뜀)는 받지 않아요.
    raw_limit = a.daum_limit if a.daum_limit is not None else (os.environ.get(PX_ALT_LIMIT_ENV) or "").strip() or None
    daum_limit = None
    if raw_limit is not None and mode != "live":
        print(f"· 다음 확인 시간 한도({raw_limit})는 사이트 점검(--live)에서만 써요 — 이 실행({mode})은 한도 없이 예전 그대로")
    elif raw_limit is not None:
        try:
            daum_limit = float(raw_limit)
        except ValueError:
            daum_limit = math.nan
        if not math.isfinite(daum_limit) or daum_limit < PX_ALT_LIVE_BUDGET_S:
            msg = (f"다음 확인 시간 한도 {str(raw_limit)[:20]}초를 쓸 수 없어요 — {PX_ALT_LIVE_BUDGET_S}초 이상의 숫자여야 해요 "
                   f"(Jack 2026-11-20 · 짧으면 더 자주 건너뛰어 느슨해져요 · --daum-limit 또는 {PX_ALT_LIMIT_ENV})")
            print(f"!! FAIL  {msg}")
            _annotate_error(msg)
            return 1
    # 2026-11-21 (Jack "3. Yes." · 코드 배포만 · 리뷰): 다음의 거절로 건너뛰기는 따로 된 스위치 — deploy.yml 관문 단계가 코드 배포(push · 손으로)에만
    # PX_ALT_REFUSE_ENV=1 을 주고 데이터 실행 뒤 배포(workflow_run)에는 0 을 줘요. 한도도 받은 --live 에서만 써요 (발행 · bootstrap 은 받아도 쓰지
    # 않아요). --live 에서 1 · 0 · 빈 값이 아닌 값은 실패해요 (켜졌는지 모르는 채 돌지 않게).
    raw_ref = (os.environ.get(PX_ALT_REFUSE_ENV) or "").strip()
    if mode == "live" and raw_ref not in ("", "0", "1"):
        msg = f"{PX_ALT_REFUSE_ENV}={raw_ref[:20]} 을 읽을 수 없어요 — 1 (코드 배포) · 0 · 빈 값만 받아요 (Jack 2026-11-21)"
        print(f"!! FAIL  {msg}")
        _annotate_error(msg)
        return 1
    refuse_skip = bool(a.daum_refuse_skip) or raw_ref == "1"
    if refuse_skip and daum_limit is None:
        print(f"· 다음의 거절로 건너뛰기는 한도를 받은 사이트 점검(--live)에서만 써요 — 이 실행({mode})은 예전 그대로")
        refuse_skip = False
    elif refuse_skip:
        print("· 다음의 거절로 건너뛰기: 켜짐 (코드 배포 · Jack 2026-11-21)")

    try:
        cur = load_dir(a.dir)
    except Exception as e:
        print(f"!! FAIL  파일 읽기: {e}")
        _annotate_error(f"파일 읽기: {str(e)[:300]}")
        return 1
    # 자정을 넘긴 실행: 수집을 시작한 날(publishedAt, 12시간 이내일 때만)을 '오늘'로 봐요
    try:
        pub = dt.datetime.fromisoformat(str(cur["data"].get("publishedAt"))).astimezone(KST)
        if not a.today and dt.timedelta(0) <= now - pub <= dt.timedelta(hours=12) and pub.date() != today:
            print(f"· 수집이 {pub:%m-%d %H:%M} KST 에 시작돼 그날({pub.date()})을 오늘로 봐요")
            today = pub.date()
    except (TypeError, ValueError):
        pass
    prev, notes = None, []
    if mode == "publish":
        try:
            prev = load_prev(a.prev_dir, a.prev_ref)
            print(f"· 직전 발행본: {a.prev_dir or a.prev_ref} (pxDate {prev['data'].get('pxDate')} · asOf {prev['data'].get('asOf')})")
        except Exception as e:
            print(f"!! 직전 발행본을 읽을 수 없어요 ({a.prev_dir or a.prev_ref}): {str(e)[:200]}")
        if prev is not None:
            try:
                prev["corp"] = load_prev_corp(a.prev_dir, a.prev_ref)
                print(f"· 직전 corp.json: 원화가 아닌 재무제표 표시 {sum(1 for c in prev['corp'].get('companies') or [] if _stmt_marked(c))}곳")
            except Exception as e:
                prev["corpError"] = f"{type(e).__name__}: {str(e)[:200]}"
                print(f"!! 직전 corp.json 을 읽을 수 없어요 ({a.prev_dir or a.prev_ref}): {prev['corpError']}")

    special = None
    try:
        special = load_special_sessions()
        print(f"· KRX 특별 거래시간 표: {len(special)}줄 ({os.path.basename(SPECIAL_CSV)})")
    except Exception as e:
        print(f"!! KRX 특별 거래시간 표를 읽지 못했어요: {e}")
    try:
        if special is None:
            raise RuntimeError("KRX 특별 거래시간 표가 없으면 그날 마감 시각을 몰라 최종본을 판단하지 않아요")
        if mode == "live":
            px = day(cur["data"].get("pxDate"))
            text = http_listing(px) if px else None
            ok, how = is_final(px, text, http_listing, http_commit_kst, today, special) if text else (False, "파일 없음")
            final = {"date": px, "closes": official_closes(text)[0], "how": how} if ok else None
        else:
            fnotes = []
            d, closes, how = latest_final(today, special=special, notes=fnotes)
            for n in fnotes:
                print(f"· {n}")
            final = {"date": d, "closes": closes, "how": how} if d else None
            if not d:
                print(f"!! 최종본 날짜: {how}")
    except Exception as e:
        print(f"!! 최종본 목록을 확인하지 못했어요: {e}")
        final = None

    sessions = None
    if mode != "live":              # 사이트 점검은 이 검사를 하지 않아요 (run_checks 참고)
        try:
            sessions = http_kospi_sessions()
            print(f"· KOSPI 거래일 {len(sessions['dates'])}일 ({sessions['src']}, 마지막 {sessions['dates'][-1]})")
            if sessions.get("disagree"):
                print(f"!! 네이버·야후 KOSPI 거래일이 다른 날: {', '.join(d.isoformat() for d in sessions['disagree'][:5])} (합쳐서 써요)")
        except Exception as e:
            print(f"!! KOSPI 일봉을 받지 못했어요: {e}")
    hilo = None
    try:
        px = day(cur["data"].get("pxDate"))
        if px:
            hilo = http_hilo([t for t in MUST], px)
            print(f"· 야후 52주 종가 범위: {len(hilo)}/{len(MUST)}종목")
    except Exception as e:
        print(f"!! 야후 52주 범위를 받지 못했어요: {e}")
    # 2026-11-19 (Jack 규칙 3): 파이프라인이 2차 출처(다음 × 야후)를 썼고 캐시에 그날 최종본이 없으면, 관문이 야후 종가를 따로 받아요 (실패해도 멈추지 않고 '확인 못 함')
    alt = None
    try:
        pxd = day(cur["data"].get("pxDate"))
        psrc = cur["data"].get("pxSrc")
        if pxd and isinstance(psrc, dict) and psrc.get("px") == PX_SRC_FB and (final is None or final["date"] < pxd):
            # 2026-11-19 (Jack): 표본에서는 마지막 확인 종가로 맞게 실린 종목만 빠져요 (지난 발행본의 가격 · 날짜 · 나이까지 — kr_own_pick_data)
            pick_data = kr_own_pick_data(cur["data"], (prev or {}).get("data") if mode == "publish" else None, kr_days_of(cur.get("macro")))
            lim_kw = {"budget_s": daum_limit} if daum_limit is not None else {}     # 한도가 없으면 예전과 같은 꼴로 불러요
            if refuse_skip:                      # 2026-11-21: 코드 배포만 (위) — 아니면 예전과 같은 꼴로 불러요
                lim_kw["refuse_skip"] = True
            alt = http_px_alt(pick_data, pxd, special=special, mode="live" if mode == "live" else "publish", **lim_kw)
            print(f"{'· ' if not alt['mustMissing'] and alt['got'] >= PX_ALT_MIN_SHARE * max(alt['asked'], 1) else '!! '}"
                  f"관문의 두 출처 공식 종가 ({pxd} · {'다음 + 발행 기록' if alt.get('mode') == 'live' else '다음 × 야후'}): 확인 {alt['got']} / {alt['asked']}종목"
                  f" (야후 일봉 종가가 비어 마감 직후 regularMarketPrice 로 읽은 종목 {alt.get('meta', 0)})"
                  + (f" · 두 출처가 다름 {len(alt['disagree'])}: {'; '.join(alt['disagree'][:5])}" if alt.get("disagree") else "")
                  + (f" · 필수 종목 못 받음 {', '.join(alt['mustMissing'])}" if alt["mustMissing"] else "")
                  + (f" · 오류 예: {alt['err'][0]}" if alt["err"] else "")
                  + (f" · 걸린 시간 {alt['secs']:.0f}초" if isinstance(alt.get("secs"), (int, float)) else ""))
            if px_alt_was_refused(alt):          # 2026-11-21 (Jack "3. Yes."): 배포만 — 다음이 아예 거절하면 그 몫만 건너뛰고 크게 경고해요
                hard, reach = px_alt_cut_gap(alt)
                print(f"!! 관문의 두 출처 확인을 다음이 거절했어요 (Jack 2026-11-21 · 코드 배포만): 거절 {alt['ref']}종목 (필수 종목 "
                      f"{len(alt.get('refMust') or [])} / {len(MUST)}" + (f" · 보기: {'; '.join(alt.get('refEx') or [])}" if alt.get("refEx") else "")
                      + f") · 거절 뒤 묻지 않음 {alt.get('rskip', 0)} · 확인 {alt['got']} / {alt['asked']}종목 · 네트워크 오류 {alt.get('net', 0)}"
                      + f" · 다음이 그날 종가를 주지 않음 {alt.get('no', 0)}" + (f" (보기: {'; '.join(alt.get('noEx') or [])})" if alt.get("noEx") else "")
                      + (f" · 시간 한도로 건너뜀 {alt['cut']}" if alt.get("cut") else "")
                      + (f" — 거절 때문이 아닌 모자람이 있어 예전 그대로 실패해요 (필수 종목 {', '.join(hard)}) ('최종본 날짜 계산' 줄)" if hard
                         else (f" — 거절 때문이 아닌 모자람이 있어 예전 그대로 실패해요 (모두 받았다고 쳐도 {reach} / {alt['asked']} < "
                               f"{PX_ALT_MIN_SHARE:.0%}) ('최종본 날짜 계산' 줄)" if reach < PX_ALT_MIN_SHARE * max(alt["asked"], 1)
                               else " — 다음의 확인을 건너뛰고 경고 ('pxDate 최종본 여부' 줄) · 나머지 검사는 예전 그대로 · 받은 종가가 발행 가격과 "
                                    "다르면 가격 줄은 실패 · 감시는 한도 없이 모든 종목을 예전 그대로 물어요")))
            elif alt.get("cut"):                 # 2026-11-20 (Jack): 배포만 — 시간 한도에 걸린 확인은 그 몫만 건너뛰고 크게 경고해요
                hard, reach = px_alt_cut_gap(alt)
                print(f"!! 관문의 두 출처 확인이 시간 한도 {px_alt_secs(alt.get('limit'))}초에 걸렸어요 (Jack 2026-11-20): 확인 {alt['got']} / {alt['asked']}종목 · "
                      f"시간 한도로 건너뜀 {alt['cut']}" + (f" (필수 종목 {', '.join(alt.get('cutMust') or [])})" if alt.get("cutMust") else "")
                      + f" · 네트워크 오류 {alt.get('net', 0)}" + (f" (필수 종목 {', '.join(alt.get('netMust') or [])})" if alt.get("netMust") else "")
                      + f" · 다음이 그날 종가를 주지 않음 {alt.get('no', 0)}" + (f" (보기: {'; '.join(alt.get('noEx') or [])})" if alt.get("noEx") else "")
                      + (f" · 네트워크 오류 뒤 다시 묻지 못한 종목 {alt.get('cutErrN', 0)} (마지막 오류: {'; '.join(alt.get('cutErr') or [])})"
                         if alt.get("cutErr") else "")
                      + (" — 한도 전에 받은 종목으로 예전 기준(필수 종목 모두 · 표본 90%)을 채웠어요"
                         if not alt["mustMissing"] and alt["got"] >= PX_ALT_MIN_SHARE * max(alt["asked"], 1)
                         else (f" — 시간 한도 때문이 아닌 모자람이 있어 예전 그대로 실패해요 (필수 종목 {', '.join(hard)}) ('최종본 날짜 계산' 줄)" if hard
                               else (f" — 시간 한도 때문이 아닌 모자람이 있어 예전 그대로 실패해요 (모두 받았다고 쳐도 {reach} / {alt['asked']} < "
                                     f"{PX_ALT_MIN_SHARE:.0%}) ('최종본 날짜 계산' 줄)" if reach < PX_ALT_MIN_SHARE * max(alt["asked"], 1)
                                     else " — 시간 한도(와 네트워크 오류)로 못 받은 몫만 건너뛰고 경고 ('pxDate 최종본 여부' 줄) · 나머지 검사는 "
                                          "예전 그대로 · 받은 종가가 발행 가격과 다르면 가격 줄은 실패"))))
    except Exception as e:
        print(f"!! 관문의 야후 공식 종가를 받지 못했어요: {type(e).__name__}: {str(e)[:120]} (확인 못 함 → 날짜 · 가격 줄 실패)")
        alt = {"date": None, "mode": None, "closes": {}, "asked": 0, "got": 0, "mustMissing": list(MUST), "err": [str(e)[:80]]}
    rep = run_checks(cur, prev, final, today, mode=mode, count_between=count_final_between, notes=notes,
                     sessions=sessions, now=now, hilo=hilo, special=special, alt=alt)
    for n in notes:
        print(f"· {n}")
    print()
    print(rep.table())
    print()
    for title, items in rep.details:
        print(f"!! {title} ({len(items):,}): {', '.join(items)}")
    if rep.details:
        print()
    bad, warn = rep.failed, rep.warned
    print(f"결과: {'FAIL' if bad else 'PASS'} · 실패 {len(bad)} · 경고 {len(warn)} · 전체 {len(rep.rows)}")
    for r in bad:
        print(f"!! FAIL  {r[0]}: {r[1]} (기준 {r[2]})")
    for r in warn:
        print(f"!! 경고  {r[0]}: {r[1]} (기준 {r[2]})")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for line in annotations(rep):
            print(line)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(f"### 뱁새 발행 관문 — {'FAIL' if bad else 'PASS'} ({mode})\n\n{rep.markdown()}\n\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
