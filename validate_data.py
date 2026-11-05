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
#   ★ 두 값은 자리 표시예요 (지금 제안 85% 를 floor 로). 금요일 시험 실행에서 본 비율을 seen 에, 그 − 10 을 floor 에 넣어요.
#   파이프라인 로그(fetch_data.apply_div_basis)도 이 값을 읽어 같은 기준으로 크게 알려요.
DYT_COVER_BANDS = {"seen": 95.0, "floor": 85.0}
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


# ── 결과 표 ─────────────────────────────────────────────────
class Report:
    def __init__(self):
        self.rows = []

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
    check_v191b(rep, data, kr, us, by, comps, pdata)

    # 경고만
    rep.add("공시 목록 조회", True, "성공" if disc.get("listOk") else "실패", "실패면 경고", warn=not disc.get("listOk"))
    return rep


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
    """직전 발행본은 비교에 쓰는 data.json 만 엄격하게 읽어요 (corp·disc·macro 는 비교에 안 써요)."""
    if prev_dir:
        with open(os.path.join(prev_dir, "data.json"), encoding="utf-8") as fh:
            return {"data": strict_loads(fh.read(), "data.json")}
    return load_git(prev_ref, files=("data.json",))


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
