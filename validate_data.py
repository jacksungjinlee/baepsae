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
import io
import json
import math
import os
import re
import subprocess
import sys
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

# v17.5.1 (v18.0 Part A + 추가 4–9). 새 기준은 첫 실제 실행의 숫자를 보고 Jack 이 승인한 뒤 고정돼요.
# 영문자에 붙지 않은 nan·None… — 한글 옆도 잡아요 ("시가총액 nan억원"). \b 는 한글을 낱말 글자로 봐서 놓쳤어요.
BAD_WORD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")
KR_DEPTS = ("우량기업부", "중견기업부", "벤처기업부", "기술성장기업부", "관리종목(소속부없음)", "투자주의환기종목(소속부없음)")
PROD_SAME_MAX = 5.0      # '주요제품'이 업종 이름과 똑같은 국내 설명 비율 상한 (%) — 열이 밀린 사고는 100%였어요
D1_COVER = 95            # 국내 d1 채움 (%)
D1_MAX_KR = 30.0         # 한국 하루 가격 제한폭 — 넘는 값은 파이프라인이 빈 칸으로 둬요
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
# v19.6a (새 줄만 · 늦추는 줄 없음 · docs/tasks/v19.6-records-alerts-dark.md Part I.1 · A.6): macro.json fxHist (원/달러 일별 환율 2016~)
# 와 data.json splits (2016 년부터의 미국 주식 분할). 앱(v19.6a)은 새 미국 기록에 그 날짜의 환율을 저장하고(fxHist), 분할 전 기록을 새 주식
# 수로 맞춰 읽어요(splits). 둘 다 사용자 기록에 영구히 남는 값이라 모양이 틀리면 실패. fxHist 가 없으면 경고 (앱이 지난 날짜의 미국 기록을
# 받지 않고 승인된 줄로 알려요 — 틀린 숫자가 아니에요). splits 는 직전 발행본에 있었는데 빠지거나, 한 번 실은 분할이 사라지거나 배율이
# 바뀌면 실패 (분할 전 기록의 주식 수가 바뀌어 보여요). 파이프라인(fetch_data.py)은 아래 기준값을 읽어 같은 선으로 판단해요 (검사 코드는 따로).
FX_HIST_FROM = "2016-01-01"     # 앱이 환율을 찾는 첫날 (src/v2/records.js FX_FROM) — 그 전 날짜의 미국 기록은 환율 없이 저장돼요
FX_HIST_FIRST_BY = "2016-01-08" # 첫 줄은 2016년 첫 주 안이어야 해요 (앞이 잘린 이력이면 2016년 뒤 날짜의 기록이 환율 없이 저장돼요)
FX_HIST_SOURCES = ("ecos_next", "ecos_close", "ecos", "yahoo_next")   # fetch_data.FX_HIST_SOURCE (Jack 의 답을 기다려요 · 지금 ecos_close):
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
SPLIT_FRESH_MAX_DAYS = 5        # splitsAsOf (야후에서 마지막으로 새로 읽은 날) 가 발행일보다 이만큼 넘게 오래면 실패
SPLIT_NEW_OLD_DAYS = 7          # 어제 목록에 없던 분할이 이보다 오래된 날짜로 새로 나오면 경고 (어제 2016 년부터 읽은 종목만)
SPLIT_NEAR_DAYS = 30            # 한 종목에 분할이 이 기간 안에 둘이면 경고 (야후가 같은 분할의 날짜를 옮겨 적었을 수 있어요 · QQQ 10-15/10-16)
# 꼭 있어야 할 분할 (야후 날짜 · 2026-11-13 확인): 2016 년부터의 이력을 읽지 못하면 실패해요
MUST_SPLITS = (("AAPL", "2020-08-31", 4.0), ("TSLA", "2020-08-31", 5.0), ("TSLA", "2022-08-25", 3.0), ("NVDA", "2021-07-20", 4.0),
               ("NVDA", "2024-06-10", 10.0), ("AMZN", "2022-06-06", 20.0), ("GOOGL", "2022-07-18", 20.0), ("WMT", "2024-02-26", 3.0),
               ("CMG", "2024-06-26", 50.0), ("HLT", "2017-01-04", 1 / 3))


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


def http_commit_kst(d):
    h = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        r = requests.get(COMMITS_API, params={"path": f"data/listing/krx/{d.isoformat()}.csv", "per_page": 1},
                         headers=h, timeout=20)
        if r.status_code != 200 or not r.json():
            return None
        ts = r.json()[0]["commit"]["committer"]["date"]
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST)
    except (requests.RequestException, ValueError, KeyError, IndexError):
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
    later = [d + dt.timedelta(days=i) for i in range(1, (today - d).days + 1)]
    for e in later:
        t = get_text(e)
        if t is not None and official_closes(t)[1] >= MIN_CAP_SHARE:
            return True, "커밋 시각 확인 불가 · 다음 거래일 파일 있음"
    return False, "커밋 시각 확인 불가 · 다음 거래일 파일 없음"


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


def coverage(arr, key):
    if not arr:
        return 0.0
    return 100.0 * sum(1 for s in arr if num(s.get(key)) is not None) / len(arr)


def us_coverage(arr):
    if not arr:
        return {"이름": 0.0, "설명": 0.0}
    return {"이름": 100.0 * sum(1 for s in arr if s.get("nk") and s.get("nk") != s.get("t")) / len(arr),
            "설명": 100.0 * sum(1 for s in arr if s.get("de")) / len(arr)}


def run_checks(cur, prev, final, today, mode="publish", count_between=None, notes=None, sessions=None, now=None, hilo=None,
               special=None):
    """cur/prev: {"data":…, "corp":…, "disc":…, "macro":…} (prev 는 None 가능).
    final: {"date", "closes", "how"} — 비교할 최종본 (None 이면 날짜·가격 검사 실패).
    sessions: {"dates": [KOSPI 거래일…], "src": 출처} — None 이면 받지 못한 것 → FAIL.
    now: 관문 실행 시각(KST) — publishedAt 12시간 검사용 (없으면 today 정오).
    hilo: {코드: {"hi", "lo", "d1"}} 야후 52주 종가 범위와 d1 — None 이면 받지 못한 것 (경고).
    special: KRX 특별 거래시간 표 — None 이면 표 파일을 읽어요 (못 읽으면 FAIL).
    mode: publish · bootstrap · live.  반환: Report."""
    rep, notes = Report(), (notes if notes is not None else [])
    data, corp, disc, macro = cur["data"], cur["corp"], cur["disc"], cur["macro"]
    rel = mode == "publish"
    if mode == "publish" and prev is None:
        rep.add("직전 발행본 읽기", False, "읽을 수 없음", "있어야 함 (첫 실행이면 bootstrap)")
    pdata = (prev or {}).get("data") if rel else None

    # 날짜
    px = day(data.get("pxDate"))
    if final is None:
        rep.add("최종본 날짜 계산", False, "실패", "최근 10일 안 최종본")
    elif mode == "live":
        rep.add("pxDate 최종본 여부", px == final["date"], px, f"{final['date']} ({final['how']})")
    else:
        rep.add("pxDate = 최종본 날짜", px == final["date"], px, f"{final['date']} ({final['how']})")
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
        inl = [s for s in kr if s.get("t") in cl]
        same = sum(1 for s in inl if num(s.get("price")) is not None and round(num(s["price"])) == cl[s["t"]])
        share = 100.0 * same / len(inl) if inl else 0.0
        rep.pct("한국 가격 = 공식 종가", share, PRICE_MATCH)
        s5 = next((s for s in kr if s.get("t") == "005930"), None)
        want = cl.get("005930")
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
            both = [s for s in us if pp.get(s["t"]) is not None]
            unch = 100.0 * sum(1 for s in both if num(s.get("price")) == pp[s["t"]]) / len(both) if both else 100.0
            rep.add("미국 가격이 바뀌었는지", unch <= US_UNCHANGED, f"그대로 {unch:.1f}%", f"≤ {US_UNCHANGED}%")
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
    rep.add("국내 종목 수", len(kr) >= KR_MIN, f"{len(kr):,}", f"≥ {KR_MIN:,}", warn=len(kr) < KR_MIN * 1.02)
    rep.add("미국 종목 수", len(us) >= US_MIN, f"{len(us):,}", f"≥ {US_MIN}")
    if pdata:
        pk, pu = len(kr_stocks(pdata)), len(us_stocks(pdata))
        rep.add("국내 종목 수 변화", pk > 0 and abs(len(kr) / pk - 1) <= KR_REL, f"{pk:,} → {len(kr):,}", f"±{KR_REL:.0%}")
        rep.add("미국 종목 수 변화", pu > 0 and abs(len(us) / pu - 1) <= US_REL, f"{pu:,} → {len(us):,}", f"±{US_REL:.0%}")
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
    check_v1751(rep, cur, kr, us, by, comps, px, today, hilo)
    check_v1752(rep, data, kr, us, pdata)
    check_foreign(rep, kr, comps)
    if rel:
        check_stmt_marks(rep, comps, prev)      # 경고가 많은 날에도 알림 10개 안에 들도록 앞쪽에 (외국 기업 줄 바로 다음)
    check_v191b(rep, data, kr, us, by, comps, pdata)
    check_v191h(rep, data, kr, by, comps, pdata, today)
    check_v191c(rep, cur, us, mode, today)
    check_v191f(rep, data, corp, kr, by, comps, pdata)
    check_v196a(rep, data, macro, by, pdata, mode, today, pmacro=(prev or {}).get("macro") if rel else None)

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
          f"꼭 있어야 할 분할 {len(MUST_SPLITS)}건 · splitsAsOf ≤ {SPLIT_FRESH_MAX_DAYS}일 (없음 · 지난 발행본에서 이음 · 읽지 못한 종목 · "
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
        if as_of is None or as_of > run_day or (run_day - as_of).days > SPLIT_FRESH_MAX_DAYS:
            probs.append(f"splitsAsOf {data.get('splitsAsOf')!r} (발행일 {run_day} 의 {SPLIT_FRESH_MAX_DAYS}일 안이어야 해요)")
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
    odd = [f"{t} {d} ×{r:g}" for (t, d), r in new if not whole_ratio(r)]
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


def check_v1751(rep, cur, kr, us, by, comps, px, today, hilo):
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
    miss_us = [t for t in ("AAPL", "MSFT", "NVDA") if num((usby.get(t) or {}).get("d1")) is None]
    rep.add("미국 필수 종목 d1", not miss_us, "모두 있음" if not miss_us else "없음: " + ",".join(miss_us), "AAPL·MSFT·NVDA")
    # 4b. 미국 d1 채움 (Jack, 2026-11-07). 2026-11-07 야후가 개별 종목의 11-06 봉을 비웠는데(S&P 500 은 있음) 그대로 갔으면
    # 미국 가격이 하루 전 종가로 '11-06 기준'이 될 뻔했어요 — 필수 세 종목이 마침 같이 빠져서 잡혔어요. 이제 일부만 빠져도 잡아요.
    # d1 은 파이프라인이 그 종목의 마지막 봉이 미국 기준일(usPxDate = S&P 500 의 마지막 '끝난' 거래일)일 때만 채워요
    # (fetch_data.us_d1). 미국 휴장일·조기 폐장일에는 기준일이 그 전 거래일 / 그날이라 d1 이 줄지 않아요 (tests/test_pipeline.py).
    us_no_d1 = [str(s.get("t")) for s in us if num(s.get("d1")) is None]
    us_cov = 100.0 * (len(us) - len(us_no_d1)) / len(us) if us else 0.0    # 보여 줄 때는 내림 (97.95% 가 '98.0%' 로 안 보이게)
    shown = ", ".join(us_no_d1[:US_D1_SHOW]) + (f" 외 {len(us_no_d1) - US_D1_SHOW:,}개" if len(us_no_d1) > US_D1_SHOW else "")
    rep.add("미국 d1 채움 (미국 기준일 봉)", us_cov >= US_D1_COVER,
            f"{floor_1(us_cov)}% ({len(us) - len(us_no_d1):,} / {len(us):,})" + (f" · 빠짐: {shown}" if us_no_d1 else ""),
            f"≥ {US_D1_COVER:g}% (미국 기준일 {data.get('usPxDate')} 봉이 있는 종목 · 하나라도 빠지면 경고)",
            warn=bool(us_no_d1))    # v19.1c (Jack, 2026-11-07): 1~15종목만 빠져도 아침 점검이 알림으로 읽어요
    if us_no_d1:
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
        worst, off = 0.0, []
        for t, y in hilo.items():
            s = by.get(t) or {}
            h, lo = num(s.get("hi")), num(s.get("lo"))
            if h is None or lo is None:
                worst = 999.0
                off.append(f"{t} 없음")
                continue
            dmax = max(abs(h / y["hi"] - 1) * 100, abs(lo / y["lo"] - 1) * 100)
            worst = max(worst, dmax)
            if dmax > HILO_TOL:
                off.append(f"{t} {h:,.0f}/{lo:,.0f} vs {y['hi']:,.0f}/{y['lo']:,.0f}")
        rep.add("필수 종목 52주 최고·최저 (야후)", worst <= HILO_FAIL,
                f"{len(hilo)}종목 · 최대 {worst:.2f}%" + (f" · {' · '.join(off)[:70]}" if off else ""),
                f"{HILO_TOL}% 안 (1–{HILO_FAIL:g}% 경고, 넘으면 실패)", warn=bool(off) or len(hilo) < len(must_kr))
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


def div_row_problem(s):
    """한 국내 종목의 dps3 · dps3a · dpsF · divSt 가 서로 맞는지. 맞으면 None, 아니면 이유. (v19.1b)"""
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
            if not _factor_ok(f):
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


def check_v191b(rep, data, kr, us, by, comps, pdata):
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
    bad = [(s["t"], why) for s in com if s.get("divSt") for why in [div_row_problem(s)] if why]
    rep.add("국내 dps3a = dps3 ÷ 배율 · divSt 맞음", not bad, f"어긋남 {len(bad)}" + (f" (예: {bad[0][0]} {bad[0][1]})" if bad else ""),
            "0 (배율은 1·2·2.5·3·4·5·10·20·25·50·100·그 역수와 곱)")

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
    miss = []
    for t in must_kr:
        s, c = by.get(t) or {}, cby.get(t) or {}
        miss += [f"{t}.{k}" for k in DATA_NEW_MUST if s.get(k) is None]
        miss += [f"corp {t}.{k}" for k in CORP_NEW_MUST if c.get(k) is None]
        miss += [f"corp {t}.{k}≠data" for k in CORP_MIRROR if c.get(k) != s.get(k)]   # 없으면 둘 다 없어야 해요
        if in_div_rank(s):
            miss += [f"corp {t}.{k}" for k in CORP_NEW_MUST_AMT if c.get(k) is None]
    rep.add("필수 종목 새 칸 (배당 분할 확인·베타 표준오차·재무 경고 검사)", not miss,
            "모두 있음" if not miss else "없음: " + ",".join(miss[:6]) + ("…" if len(miss) > 6 else ""),
            "data " + "·".join(DATA_NEW_MUST) + " · corp " + "·".join(CORP_NEW_MUST) + " · corp 배당 칸 = data · "
            + "·".join(CORP_NEW_MUST_AMT) + " ('필수 종목 배당 순위'에서 빠진 종목은 총액·주당순이익 빼고)")

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


def _dvwhy_events(ev, today):
    """사건 목록의 모양 문제 → 이유 또는 None."""
    if not isinstance(ev, list) or not ev:
        return "사건 목록 (비었거나 목록이 아님)"
    prev = None
    for e in ev:
        if not isinstance(e, dict) or e.get("k") not in DVWHY_KINDS:
            return "사건 종류"
        if set(e) != ({"k", "d", "r", "rc", "x"} if e["k"] == "bonus" else {"k", "d", "r", "rc"}):
            return f"사건 칸 {sorted(e)}"
        r = e.get("r")
        if not _isnum(r) or r <= 0 or not _dvwhy_clean(r) or abs(r - 1) <= DVWHY_SAME + 1e-9:
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


def _dvwhy_ratio(ev, fy, f3, adj, px):
    """사건의 곱 = 다시 계산한 해마다 dpsF (그해 12월 31일 뒤 ~ pxDate) · 사건은 가장 오래된 해 12월 31일 뒤 ~ pxDate 안 ·
    당기 배율이 1 이면 그 뒤 사건 없음 → 이유 또는 None."""
    start = dt.date(fy - max(adj), 12, 31)
    out = [e for e in ev if not start < _real_day(e["d"]) <= px]
    if out:
        return f"날짜 {out[0]['d']} 가 {start} 뒤 ~ {px} 밖"
    for i in adj:
        cut = dt.date(fy - i, 12, 31)
        prod = math.prod(e["r"] for e in ev if cut < _real_day(e["d"]) <= px)
        if abs(prod / f3[i] - 1) > DVWHY_TOL:
            return f"{fy - i}년 배율 {f3[i]:g} ≠ 사건의 곱 {prod:.4g}"
    if f3[0] == 1 and any(dt.date(fy, 12, 31) < _real_day(e["d"]) for e in ev):    # 당기 배율 1 = 사업보고서 뒤 사건 없음
        return f"{fy}년 배율 1 인데 그 뒤 사건이 있어요"
    return None


def dvwhy_problems(s, px, today):
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
        bad = _dvwhy_events(w["ev"], today)
        return (bad, None) if bad else (None, _dvwhy_ratio(w["ev"], fy, f3, adj, px))
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
    for s in has:
        a, b = dvwhy_problems(s, px, today)
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
    a = ap.parse_args(argv)
    now = dt.datetime.now(KST)
    today = day(a.today) if a.today else now.date()
    mode = "live" if a.live else ("bootstrap" if a.bootstrap else "publish")
    print(f"뱁새 발행 관문 · 오늘(KST) {today} · 모드 {mode}")
    if mode == "bootstrap":
        print("!! --bootstrap: 직전 발행본과의 비교를 건너뛰어요. 첫 실행 한 번만 써야 해요.")

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
    rep = run_checks(cur, prev, final, today, mode=mode, count_between=count_final_between, notes=notes,
                     sessions=sessions, now=now, hilo=hilo, special=special)
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
