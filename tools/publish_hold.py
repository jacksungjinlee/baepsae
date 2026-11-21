# -*- coding: utf-8 -*-
"""2차 출처 날의 발행 판단: 확인 비율 바닥 · 같은 날 다시 발행 (#161 · Jack 2026-11-21).

Jack (2026-11-21, 그대로): "(c), with no new timer for Jack. KRX's final file has been stuck since 11-16, so treat Daum × Yahoo as the
normal path. Publish at 06:40 with what's confirmed (carries with their date line). Later runs update that day's data when more closes
are confirmed. Hold only if confirmed coverage is below a floor; set it from last week's 06:40 coverage and show the number in the PR."
(이 PR 의 첫 모양 — 08:00 전 · 직전 발행본의 97% — 을 바꿨어요.)

규칙 (decide · 매일 실행이 한 번 불러요 — update-data.yml 'update' job 의 단계 id hold · 몇 시든):
1. 바닥 (floor_decision): 2차 출처 날 (오늘 data.json 의 pxSrc.px == daum+yahoo) 에 코스피 · 코스닥 확인 비율이 COVERAGE_FLOOR_PCT 보다
   낮으면 보류해요. 확인 비율 = (이 실행이 두 출처로 확인한 코스피 · 코스닥 종가 + 같은 날 지난 발행본에서 다시 쓴 확인 종가) ÷ 그날 코스피 ·
   코스닥 목록 (pxSrc.fb: n − mkt · conf − 코넥스 fb.knx.kept · 칸이 맞아떨어질 때만 · pxSrc.own.reuse.kk). 마지막 확인 종가로 실은 종목
   (pxSrc.own · pxd · #159) 은 세지 않아요. 1차 출처 (KRX 목록 최종본) 날은 예전 그대로예요.
2. 같은 날 다시 발행 (same_day_decision): 지난 발행본과 한국 기준일 (pxDate) 이 같은 실행 (already_published.py 가 확인 못 한 국내 종가가 남은 날
   다시 돌게 해요) 은 지난 발행본에서 아무것도 잃지 않을 때만 (lost_stocks: 그 날짜 종가 국내 종목은 그 날짜 종가로 · 마지막 확인 종가 국내 종목은
   그대로 또는 그 날짜 종가로 · 미국 · 펀드 · 금 · 채권 행은 그대로 · 미국 기준일이 같으면 그 날짜 종가 미국 종목은 그 날짜 종가로 · 같은 종가인
   국내 종목은 d1 그대로), 그리고 미국 기준일이 같으면 그 날짜 종가 국내 종목이 지난 발행본보다 많을 때 (validate_data.kr_px_count) · 미국 기준일이
   새로우면 그것만으로 발행해요. 아니면 발행하지 않아요 (같은 보류 길). 같은 날 다시 하는 실행은 국내 종가만 채워요 — 미국 마지막 확인 종가(pxc)는
   다시 돌 까닭이 아니고 (already_published.open_closes 의 미국 칸은 늘 0) 다음 새 미국 기준일 발행에서 채워져요 (#161 리뷰 S4).
'지난 발행본' 은 사이트가 보여 주는 발행본 = data 브랜치의 data.json 이에요 (#161 리뷰 3차 B-M1 · already_published.read_published 와 같은 길 · 그
브랜치가 아직 없으면 main). main 의 HEAD 와 다르면 (지난 발행의 'data 브랜치에 올리기' 가 실패했어요) '같은 날 · 더 낫지 않음' 으로 보류하지 않고
발행해 data 브랜치를 고쳐요 (잃는 것이 있으면 그대로 보류).
보류하면: 발행 두 단계 ('커밋 & 푸시' · 'data 브랜치에 올리기') 가 건너뛰어요 (if: steps.hold.outputs.hold != 'true') → main · data 브랜치 · 사이트
그대로. 실행은 실패가 아니라 초록으로 끝나요. 감시에는 중립이에요 (watchdog.is_held_run). 관문 · 화면 검사는 보류해도 그대로 돌아요.
비교할 수 없으면: 오늘 기록을 못 읽으면 보류하지 않아요 (크게 · 경고 알림 · 관문이 그 파일을 봐요). 오늘 확인 비율을 셀 수 없으면 바닥은 보지 않고
같은 날 규칙은 그대로 봐요 (크게). bootstrap · 비교 커밋을 받지 못한 시험 실행은 바닥만 봐요 (크게).
판단할 수 없는 같은 날 다시 하는 실행 (#161 리뷰 3차 B-S5 · kind stop): 이 확인이 오류로 멈췄거나 data 브랜치를 읽지 못했는데, 오늘 파일의 한국 기준일이
지난 발행본 (못 읽었으면 main 의 HEAD) 과 같거나 같은지 모르면 — 발행하지 않고 (hold=true) 종료 코드 3 으로 끝나요. 워크플로의 단계가 그 코드를
보고 실패로 끝나 (관문 · 화면 검사 · 발행이 모두 건너뛰어요) 빨간 실행이 되고 감시가 알려요 (중립이 아니에요). 그날의 첫 실행 (새 기준일) 은
예전처럼 보류하지 않아요 (크게 · 경고 알림 · 관문과 화면 검사가 발행을 정해요).

쓰는 법: python tools/publish_hold.py [--prev-ref REF] [--bootstrap] [--no-prev]  → GITHUB_OUTPUT 에 hold=true|false (마지막 줄) · 종료 코드 3 = stop
"""
import argparse
import collections
import datetime as dt
import json
import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from validate_data import KST, PX_ALT_TOL, PX_SRC_FB, _gh_escape, kr_px_count  # noqa: E402  (관문과 같은 정의)

# 바닥 (Jack 2026-11-21: "set it from last week's 06:40 coverage"). 지난주 06:40 발행 (data 브랜치 · 코스피 · 코스닥 두 출처 확인 ÷ 그날 목록):
#   11-19 (pxDate 11-18) 2,743 / 2,771 = 98.99% · 11-20 (pxDate 11-19) 2,740 / 2,771 = 98.88% — 2차 출처 날은 이 둘뿐이에요.
#   11-13 · 11-14 · 11-17 은 KRX 최종본 날 (목록의 모든 코스피 · 코스닥 종목에 공식 종가 = 100%).
#   정한 값 97% (2026-11-21 · Jack 이 지난주 수로 정하라고 맡긴 결정): 98% 는 지난주 가장 낮은 98.88% (11-17 ~ 11-19 실행은 98.7%) 에서 0.7점쯤만
#   남겨요. #159 로 확인 못 한 종목은 마지막 확인 종가와 Jack 의 줄로 보이니, 조금 약한 아침이 발행 전체를 막으면 안 돼요. 97% 도 야후가 빈 아침
#   (약 91%) 은 막고, 그날 목록 2,771 이면 확인 못 한 종목 83 까지 발행해요 (지난주는 28 · 31).
#   정수 % 로 계산해요: 확인 × 100 ≥ 바닥 × 목록 이면 발행 (딱 바닥이면 발행).
COVERAGE_FLOOR_PCT = 97
FB_PARTS = ("mkt", "noDaum", "bad", "noYahoo", "diff")   # 확인 못 한 칸 (fetch_data.px_src_counts) — 코스피 · 코스닥 확인과 합치면 n
TITLE = f"발행 판단 (2차 출처 날 확인 비율 바닥 {COVERAGE_FLOOR_PCT}% · 같은 날 다시 발행은 더 나을 때만)"

Decision = collections.namedtuple("Decision", "hold loud why kind")   # kind: publish · floor · back · loss · same · unknown · error · stop
# 감시 (watchdog.is_held_run) 에 중립인 보류: 바닥 아래 · 날짜가 뒤로 감 · 잃은 종목 · 비교할 수 없음. '같은 날 · 더 낫지 않음' (관문 · 화면 검사를
# 통과 · 한국 · 미국 기준일이 발행본과 같음) 은 건강한 실행으로 세요 (#161 리뷰 7: 앞선 빨간 실행의 경보가 닫혀요).
NEUTRAL = ("floor", "back", "loss", "unknown", "quiet")   # quiet: 데이터를 모으지 않은 실행 (3시간 쉼 · 시험한 것이 없어 건강하다고 세지 않아요)


def _count(v):
    """0 이상의 정수만 (True/False 는 아니에요)."""
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def day_mode(data):
    """data.json 의 pxSrc.px (daum+yahoo = 2차 출처 날 · listing = 1차 출처 날) — 없으면 None. (순수 함수)"""
    src = data.get("pxSrc") if isinstance(data, dict) else None
    return src.get("px") if isinstance(src, dict) else None


def kk_counts(data):
    """2차 출처 날 data.json → (셈 dict 또는 None, 설명). (순수 함수)
    셈: conf 이 실행이 두 출처로 확인한 코스피 · 코스닥 (pxSrc.fb.conf − 코넥스 fb.knx.kept · #158) · listing 그날 코스피 · 코스닥 목록 (n − mkt) ·
    reuse 같은 날 지난 발행본에서 다시 쓴 코스피 · 코스닥 확인 종가 (pxSrc.own.reuse.kk · 없으면 0) · total conf + reuse ·
    lost 지난 발행본이 그 날짜 종가로 실었는데 잃은 종목 수 (pxSrc.own.reuse.lost · 다시 쓰기 기록이 없으면 None).
    fb 의 칸이 맞아떨어질 때만 (n = conf + mkt + noDaum + bad + noYahoo + diff) — 마지막 확인 종가 (pxSrc.own · pxd) 를 conf 에 섞으면 맞지 않아 None."""
    if not isinstance(data, dict):
        return None, "data.json 을 읽지 못했어요"
    src = data.get("pxSrc")
    if not isinstance(src, dict):
        return None, "pxSrc 가 없어요"
    if src.get("px") != PX_SRC_FB:
        return None, f"2차 출처 날이 아니에요 (pxSrc.px {src.get('px')!r} · pxDate {data.get('pxDate')})"
    if src.get("date") != data.get("pxDate"):
        return None, f"pxSrc.date {src.get('date')!r} 가 pxDate {data.get('pxDate')!r} 와 달라요"
    fb = src.get("fb")
    if not isinstance(fb, dict):
        return None, f"pxSrc.fb 가 없어요 (pxDate {data.get('pxDate')})"
    bad = [k for k in ("n", "conf", *FB_PARTS) if _count(fb.get(k)) is None]
    if bad:
        return None, f"pxSrc.fb 의 칸이 비었거나 이상해요 ({', '.join(bad)} · pxDate {data.get('pxDate')})"
    n, conf, left = fb["n"], fb["conf"], sum(fb[k] for k in FB_PARTS)
    knx, kept = fb.get("knx"), 0
    if knx is not None:                        # #158: 코넥스를 그날 파일에 넣은 날 conf = 다음 × 야후 확인 + knx.kept
        if not isinstance(knx, dict) or _count(knx.get("kept")) is None or knx["kept"] > conf:
            return None, (f"pxSrc.fb.knx (코넥스) 의 kept 가 비었거나 이상해요 (pxDate {data.get('pxDate')}) — 코스피 · 코스닥 확인 수를 알 수 없어요")
        kept = knx["kept"]
    kk = conf - kept
    if kk + left != n:
        return None, (f"pxSrc.fb 의 칸이 맞지 않아요: 코스피 · 코스닥 확인 {kk:,} + 확인 못 한 칸 {left:,} ≠ 목록 {n:,} (pxDate {data.get('pxDate')}) — "
                      "확인 수에 다른 것(마지막 확인 종가 등)이 섞였을 수 있어 쓰지 않아요")
    listing = n - fb["mkt"]
    if listing <= 0:
        return None, f"그날 코스피 · 코스닥 목록이 0 이에요 (pxDate {data.get('pxDate')})"
    own = src.get("own") if isinstance(src.get("own"), dict) else {}
    rr = own.get("reuse") if isinstance(own.get("reuse"), dict) else None
    reuse, lost = 0, None
    if rr is not None:
        if _count(rr.get("kk")) is None or _count(rr.get("lost")) is None or kk + rr["kk"] > listing:
            return None, f"pxSrc.own.reuse (같은 날 다시 쓴 확인 종가) 기록이 이상해요 (pxDate {data.get('pxDate')})"
        reuse, lost = rr["kk"], rr["lost"]
    total = kk + reuse
    return ({"conf": kk, "listing": listing, "reuse": reuse, "total": total, "lost": lost, "kept": kept},
            f"코스피 · 코스닥 확인 {total:,} / 목록 {listing:,} = {100 * total / listing:.2f}%"
            + (f" (이 실행 {kk:,} + 같은 날 지난 발행본에서 다시 씀 {reuse:,})" if rr is not None else "")
            + (f" · 코넥스 {kept:,} 는 빼고" if knx is not None else "") + f" (pxDate {data.get('pxDate')})")


def floor_decision(mode, total, listing, floor=COVERAGE_FLOOR_PCT):
    """바닥 (Decision · 순수 함수): 2차 출처 날 확인 비율 total ÷ listing 이 floor% 보다 낮으면 보류. 1차 출처 날은 보지 않아요.
    total · listing 을 모르면 (None) 보류하지 않아요 (크게)."""
    if mode != PX_SRC_FB:
        return Decision(False, False, f"2차 출처 날이 아니에요 (pxSrc.px {mode!r}) → 바닥 없이 예전 그대로", "publish")
    if total is None or listing is None or listing <= 0:
        return Decision(False, True, "오늘 코스피 · 코스닥 확인 비율을 몰라요 → 보류하지 않아요 (비교가 없다고 발행을 막지 않아요)", "unknown")
    need = -(-floor * listing // 100)                     # 바닥에 닿는 가장 작은 확인 수 (올림)
    pct = f"{100 * total / listing:.2f}%"
    if total * 100 >= floor * listing:
        return Decision(False, False, f"코스피 · 코스닥 확인 {total:,} / {listing:,} = {pct} ≥ 바닥 {floor}% ({need:,}) → 발행해요", "publish")
    return Decision(True, True, f"코스피 · 코스닥 확인 {total:,} / {listing:,} = {pct} < 바닥 {floor}% ({need:,} · 모자람 {need - total:,}) → "
                                "이 실행은 발행하지 않아요. 다음 실행이 다시 해요", "floor")


def _day(v):
    try:
        return dt.date.fromisoformat(str(v)) if v is not None else None
    except ValueError:
        return None


def dates_back(cur, prev):
    """날짜가 뒤로 가는지 (#161 리뷰 1 · 순수 함수): 이 실행의 한국 기준일 (pxDate) 이나 미국 기준일 (usPxDate) 이 지난 발행본보다 앞이면 그 이유.
    (예: 08:17 실행이 10:15 쯤 시작해 야후가 비는 10:00 ~ 10:40 에 걸리면 미국 기준일이 하루 앞으로 가요 — 한국은 그대로.) 아니면 None."""
    if not isinstance(cur, dict) or not isinstance(prev, dict):
        return None
    out = []
    for k, name in (("pxDate", "한국"), ("usPxDate", "미국")):
        c, p = _day(cur.get(k)), _day(prev.get(k))
        if c is not None and p is not None and c < p:
            out.append(f"{name} 기준일 {c} < 발행본 {p}")
    return " · ".join(out) or None


def stock_sets(data):
    """발행 파일의 종목 (순수 함수): (그 날짜 종가 국내 코드, 마지막 확인 종가 (pxd) 국내 코드, 그 밖 종목 (종류, 코드) — 미국 · 펀드 · 금 · 채권)."""
    kr_px, kr_own, other = set(), set(), set()
    for x in (data or {}).get("stocks") or [] if isinstance(data, dict) else []:
        if not isinstance(x, dict) or x.get("t") is None:
            continue
        t = str(x["t"])
        if x.get("cls") == "kr" and not x.get("fund"):
            (kr_own if x.get("pxd") is not None else kr_px).add(t)
        else:
            other.add((str(x.get("cls")), t))      # 있는지만 봐요 — 미국 행의 날짜는 us_date_sets 가 따로 나눠요 (#161 리뷰 S3)
    return kr_px, kr_own, other


def us_date_sets(data):
    """발행 파일의 미국 종목 (#161 리뷰 S3 · 순수 함수): (미국 기준일 종가 티커 — pxd 없음, 자기 날짜 티커 — pxd 있음: 마지막 확인 종가 pxc 든 야후의
    옛 봉이든)."""
    at, own = set(), set()
    for x in (data or {}).get("stocks") or [] if isinstance(data, dict) else []:
        if isinstance(x, dict) and x.get("t") is not None and x.get("cls") == "us" and not x.get("fund"):
            (own if x.get("pxd") is not None else at).add(str(x["t"]))
    return at, own


def _num(v):
    """유한한 숫자만 (True/False 는 아니에요) — 아니면 None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def kr_d1_lost(cur, prev, tol=PX_ALT_TOL):
    """같은 날 다시 발행에서 d1 을 잃은 국내 종목 (#161 리뷰 S5 · 순수 함수): 지난 발행본이 그 날짜 종가와 d1 으로 실은 국내 종목이 이 실행에도 그 날짜
    종가로, 같은 가격 (원 단위까지 · tol) 인데 d1 이 없음. 거래 없음 (noTrade) 으로 바뀐 종목은 빼요 (빈 d1 의 까닭이 있어요). 가격이 달라진 종목은 d1 도
    달라질 수 있어 세지 않아요. 이 실행에 없거나 마지막 확인 종가로 바뀐 종목은 lost_stocks 의 kr 이 세요. 반환: 코드 목록 (정렬)."""
    cur_by, dup = {}, set()
    for x in (cur or {}).get("stocks") or [] if isinstance(cur, dict) else []:
        if isinstance(x, dict) and x.get("t") is not None and x.get("cls") == "kr" and not x.get("fund") and x.get("pxd") is None:
            t = str(x["t"])
            if t in cur_by:                    # 같은 코드가 두 번 — 어느 값인지 몰라요 (잃은 것으로)
                dup.add(t)
            cur_by[t] = x
    out = set()
    for x in (prev or {}).get("stocks") or [] if isinstance(prev, dict) else []:
        if not isinstance(x, dict) or x.get("t") is None or x.get("cls") != "kr" or x.get("fund") or x.get("pxd") is not None:
            continue
        t = str(x["t"])
        c = cur_by.get(t)
        if c is None or _num(x.get("d1")) is None or c.get("noTrade") is True:
            continue
        pp, cp = _num(x.get("price")), _num(c.get("price"))
        if pp is None or cp is None or abs(pp - cp) > tol:
            continue
        if _num(c.get("d1")) is None or t in dup:
            out.add(t)
    return sorted(out)


def lost_stocks(cur, prev):
    """같은 날 다시 발행에서 잃는 것 (#161 리뷰 2 · S3 · S5 · 순수 함수): 지난 발행본의 모든 종목이 있어야 해요 — 그 날짜 종가 국내 종목은 그 날짜 종가로
    (마지막 확인 종가로 바뀌거나 빠지면 잃음) · 마지막 확인 종가 국내 종목은 그대로 또는 그 날짜 종가로 · 미국 · 펀드 · 금 · 채권은 그대로 (kr · own ·
    other). 미국 기준일이 같으면 그 날짜 종가 미국 종목이 자기 날짜 (pxd · 마지막 확인 종가든 야후의 옛 봉이든) 로 바뀌면 잃음 (us · 빠진 종목은 other
    에서 세요 · 미국 기준일이 새로우면 마지막 확인 종가로 넘어가는 것이 정상이라 보지 않아요). 같은 가격인 국내 종목이 d1 을 잃으면 잃음 (d1 ·
    kr_d1_lost). 반환: {kr, own, other, us, d1}."""
    cp, co, cx = stock_sets(cur)
    pp, po, px = stock_sets(prev)
    us = []
    cu, pu = _day((cur or {}).get("usPxDate")), _day((prev or {}).get("usPxDate"))
    if cu is not None and cu == pu:
        us = sorted(us_date_sets(prev)[0] & us_date_sets(cur)[1])
    return {"kr": sorted(pp - cp), "own": sorted(po - cp - co), "other": sorted(f"{c} {t}" for c, t in px - cx), "us": us,
            "d1": kr_d1_lost(cur, prev)}


def same_day_decision(cur_mode, prev_mode, cur, prev):
    """같은 한국 기준일 다시 발행 (Decision · 순수 함수 · #161 리뷰 2). 지난 발행본에서 아무것도 잃지 않을 때만 (lost_stocks: 종목 · 미국 기준일 종가 ·
    같은 종가의 d1), 그리고
    - 미국 기준일이 같으면: 그 날짜 종가 국내 종목 수 (발행 파일 · validate_data.kr_px_count) 가 지난 발행본보다 많을 때만 발행해요.
    - 미국 기준일이 새로우면: 국내를 잃지 않으면 발행해요 (미국 종가를 막지 않아요).
    - 오늘 2차 출처 · 지난 발행본 1차 출처 (KRX 최종본) → 발행하지 않아요. 둘 다 1차 출처 → 예전 그대로 발행 (손으로 다시 돌린 실행)."""
    if cur_mode != PX_SRC_FB and prev_mode != PX_SRC_FB:
        return Decision(False, False, "같은 기준일 · 1차 출처 — 예전 그대로 발행해요", "publish")
    if cur_mode == PX_SRC_FB and prev_mode != PX_SRC_FB:
        return Decision(True, True, f"같은 기준일인데 지난 발행본이 2차 출처가 아니에요 (pxSrc.px {prev_mode!r}) — 2차 출처로 바꿔 발행하지 않아요", "loss")
    lost = lost_stocks(cur, prev)
    us_new = (_day(cur.get("usPxDate")) or dt.date.min) > (_day(prev.get("usPxDate")) or dt.date.min)
    us_gone = []
    if us_new:
        # #161 리뷰 3차 B-S3: 미국 기준일이 새로우면 미국 목록이 바뀌는 것은 정상이에요 (S&P 500 편입 · 편출 · 마지막 확인 종가가 5 미국 거래일을 넘어 잠시 뺌)
        # — 미국 종목이 빠진 것으로 보류하지 않아요 (그러면 한국 휴장일 (설 · 추석) 에 미국 종가가 며칠 멈춰요 · 미국 종목 수는 관문의 줄이 봐요).
        # 펀드 · 금 · 채권 행은 정해진 목록이라 그대로 세요 (빠지면 데이터 문제예요 · 한국 휴장일과 상관없어요).
        us_gone = [x for x in lost["other"] if x.startswith("us ")]
        lost["other"] = [x for x in lost["other"] if not x.startswith("us ")]
    n_lost = sum(len(v) for v in lost.values())
    try:
        n_cur, n_prev = kr_px_count(cur), kr_px_count(prev)
    except Exception as e:
        return Decision(True, True, f"같은 기준일인데 종목 수를 셀 수 없어요 ({type(e).__name__}) → 발행하지 않아요 (그날 데이터는 이미 나가 있어요)", "unknown")
    if n_lost:
        ex = ", ".join((lost["kr"] + lost["own"] + lost["other"] + [f"미국 {t} (옛 날짜로)" for t in lost["us"]]
                        + [f"{t} (d1 빈 칸)" for t in lost["d1"]])[:12])
        return Decision(True, True, f"같은 기준일 · 지난 발행본의 종목을 잃어요 — 그 날짜 종가 국내 {len(lost['kr']):,} · 마지막 확인 종가 국내 "
                                    f"{len(lost['own']):,} · 미국 등 {len(lost['other']):,} · 미국 기준일 종가가 옛 날짜로 {len(lost['us']):,} · "
                                    f"같은 종가인데 d1 을 잃은 국내 {len(lost['d1']):,} ({ex}) → 발행하지 않아요 (그 날짜 종가 국내 {n_prev:,} → {n_cur:,})",
                        "loss")
    if us_new:
        return Decision(False, bool(us_gone), f"같은 한국 기준일 · 미국 기준일 {prev.get('usPxDate')} → {cur.get('usPxDate')} · 잃은 종목 0"
                        + (f" (미국 목록에서 빠진 {len(us_gone):,}종목은 새 미국 기준일이라 세지 않아요: {', '.join(t.split(' ', 1)[1] for t in us_gone[:12])})"
                           if us_gone else "") + " → 발행해요", "publish")
    if n_cur > n_prev:
        return Decision(False, False, f"같은 기준일 · 그 날짜 종가 국내 종목 {n_prev:,} → {n_cur:,} (+{n_cur - n_prev:,}) · 잃은 종목 0 → 더 나아서 "
                                      "같은 날 데이터를 고쳐 발행해요", "publish")
    return Decision(True, False, f"같은 기준일 · 그 날짜 종가 국내 종목 {n_prev:,} → {n_cur:,} — 더 많지 않아 발행하지 않아요 (지난 발행본 그대로)", "same")


# ── 읽기 ────────────────────────────────────────────────────
def read_cur(path):
    """오늘 만든 data.json (데이터 수집 단계가 쓴 것). 못 읽으면 (None, 이유)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), path
    except Exception as e:
        return None, f"{path} 을 읽지 못했어요 ({type(e).__name__}: {str(e)[:120]})"


def read_prev(ref="HEAD", run=subprocess.run):
    """직전 발행본 data.json — 관문과 같은 곳 (git {ref}:data.json). 못 읽으면 (None, 이유)."""
    try:
        r = run(["git", "show", f"{ref}:data.json"], capture_output=True, timeout=120)
    except Exception as e:
        return None, f"git show {ref}:data.json 을 하지 못했어요 ({type(e).__name__})"
    if r.returncode != 0:
        return None, f"git show {ref}:data.json → 종료 코드 {r.returncode}"
    try:
        return json.loads(r.stdout.decode("utf-8")), f"git {ref}:data.json"
    except Exception as e:
        return None, f"git {ref}:data.json 을 읽지 못했어요 ({type(e).__name__})"


def read_live(run=None):
    """사이트가 보여 주는 발행본 = data 브랜치의 data.json (#161 리뷰 3차 B-M1) — already_published.read_published 와 같은 길 (그 브랜치가 아직 없으면
    main · 못 읽으면 크게 남기고 None). 반환: (dict 또는 None, 설명)."""
    import already_published as A
    d = A.read_published(run) if run else A.read_published()
    if isinstance(d, dict):
        return d, "data 브랜치의 data.json (사이트가 보여 주는 발행본)"
    return None, "data 브랜치의 data.json 을 받지 못했어요"


def _kr_px(data):
    """로그용 그 날짜 종가 국내 종목 수 — 셀 수 없으면 '?' (#161 리뷰 3차 nit: 로그 줄이 판단을 멈추지 않게)."""
    try:
        return f"{kr_px_count(data):,}"
    except Exception:
        return "?"


# ── 실행 ────────────────────────────────────────────────────
def evaluate(cur, cur_note, prev, prev_note, now, head=None, live_failed=False):
    """오늘 data.json · 지난 발행본 (사이트의 발행본 = data 브랜치 · dict 또는 None) → (Decision, 로그 줄들). 날짜가 뒤로 가는지 → 바닥 → 같은 날 다시
    발행 순서로 한 번 정해요. head: main 의 HEAD data.json (live_failed 일 때 같은 날인지 · 지난 발행이 data 브랜치에 다 올랐는지 볼 때 · 없으면 None).
    live_failed (#161 리뷰 3차 B-M1): data 브랜치를 읽지 못했어요 — 오늘 파일의 한국 기준일이 main HEAD 와 같거나 HEAD 도 모르면 판단할 수 없는 같은 날
    다시 하는 실행이라 stop (발행하지 않고 빨간 실행), 아니면 (새 날) 바닥만 봐요."""
    lines = [f"· {TITLE} — {now.astimezone(KST):%Y-%m-%d %H:%M} KST"]
    if cur is None:
        lines.append(f"!! 오늘 data.json: {cur_note}")
        return Decision(False, True, f"오늘 data.json 을 읽지 못했어요 ({cur_note}) → 보류하지 않아요 (관문이 봐요)", "unknown"), lines
    mode = day_mode(cur)
    cn, why_c = kk_counts(cur)
    lines.append(f"{'!! ' if mode == PX_SRC_FB and cn is None else '· '}오늘: pxSrc.px {mode!r} · {why_c} · 한국 {cur.get('pxDate')} · 미국 {cur.get('usPxDate')}")
    if live_failed and prev is None:
        hp = head.get("pxDate") if isinstance(head, dict) else None
        lines.append(f"!! 지난 발행본: {prev_note} · main HEAD 한국 기준일 {hp!r}")
        if hp is None or hp == cur.get("pxDate"):
            return Decision(True, True, f"사이트의 발행본 (data 브랜치) 을 읽지 못했는데 오늘 파일 (한국 {cur.get('pxDate')}) 이 같은 날 다시 하는 실행"
                                        f"{'일 수 있어요 (main HEAD 도 읽지 못함)' if hp is None else '이에요 (main HEAD 와 같은 한국 기준일)'} → 판단할 수 없어 발행하지 "
                                        "않고 이 실행을 실패로 끝내요 (감시가 알려요 · 다음 실행이 다시 해요)", "stop"), lines
    if isinstance(prev, dict):
        back = dates_back(cur, prev)
        if back:
            lines.append(f"!! 직전 발행본: {prev_note} · 한국 {prev.get('pxDate')} · 미국 {prev.get('usPxDate')}")
            return Decision(True, True, f"날짜가 뒤로 가요 ({back}) → 이 실행은 발행하지 않아요 (사이트는 더 새 발행본 그대로)", "back"), lines
    d = floor_decision(mode, cn and cn["total"], cn and cn["listing"])
    if d.hold:
        return d, lines
    floor_unknown = d.kind == "unknown"        # #161 리뷰 3차 B-S4: 바닥을 볼 수 없어도 같은 날 규칙 (잃는 것 · 더 나음) 은 그대로 봐요
    if prev is None:
        lines.append(f"{'!! ' if mode == PX_SRC_FB else '· '}직전 발행본: {prev_note} — 같은 날 다시 도는 실행인지 몰라 바닥만 봐요")
        return (Decision(False, True, d.why + " (직전 발행본을 읽지 못해 같은 날인지 몰라요 · 바닥만 봤어요)", "unknown")
                if mode == PX_SRC_FB and not floor_unknown else d), lines
    pmode = day_mode(prev)
    if cur.get("pxDate") != prev.get("pxDate"):
        lines.append(f"· 직전 발행본: {prev_note} · 한국 {prev.get('pxDate')} · 미국 {prev.get('usPxDate')} → 새 날 (같은 날 다시 발행 아님)")
        return d, lines
    lines.append(f"· 직전 발행본 (같은 한국 기준일): {prev_note} · pxSrc.px {pmode!r} · 미국 {prev.get('usPxDate')} · 그 날짜 종가 국내 "
                 f"{_kr_px(prev)} → 이 실행 {_kr_px(cur)}")
    sd = same_day_decision(mode, pmode, cur, prev)
    if sd.kind == "same" and isinstance(head, dict) and head != prev:
        # #161 리뷰 3차 B-M1: main 의 HEAD 가 사이트의 발행본과 달라요 — 지난 발행의 'data 브랜치에 올리기' 가 실패했어요. 보류하면 사이트가 main 보다
        # 뒤인 채로 '건강한' 실행이 경보를 닫아요. 잃는 것이 없으니 발행해 data 브랜치를 고쳐요.
        lines.append(f"!! main HEAD 의 data.json (한국 {head.get('pxDate')} · 발행 {head.get('publishedAt')}) 이 사이트의 발행본 (data 브랜치 · 발행 "
                     f"{prev.get('publishedAt')}) 과 달라요 — 지난 발행이 data 브랜치에 다 오르지 못했어요")
        sd = Decision(False, True, sd.why.replace(" — 더 많지 않아 발행하지 않아요 (지난 발행본 그대로)", "")
                      + " — 더 많지 않지만 main 이 사이트의 발행본과 달라 (지난 data 브랜치 올리기 실패) 발행해서 data 브랜치를 고쳐요", "publish")
    if floor_unknown and not sd.hold:
        return Decision(False, True, d.why + " · 같은 날 규칙: " + sd.why, "unknown"), lines
    return sd, lines


def summary_md(d, lines, dry, sample=False):
    head = {"floor": "보류 — 확인 비율이 바닥 아래라 발행하지 않아요", "same": "발행 안 함 — 같은 날 지난 발행본보다 낫지 않아요",
            "back": "보류 — 날짜가 지난 발행본보다 앞이에요", "loss": "보류 — 지난 발행본의 종목을 잃어요",
            "quiet": "쉼 — 데이터를 모으지 않은 실행 (발행본 그대로)",
            "stop": "멈춤 — 같은 날 다시 하는 실행인데 판단할 수 없어 발행하지 않고 실패로 끝내요"}.get(d.kind)
    if head is None:                          # #161 리뷰 3차 nit: 보류한 '비교할 수 없음' 을 '발행' 으로 적지 않게
        head = ("보류 — 비교할 수 없어 발행하지 않아요" if d.hold else
                "발행 (보류 아님 · 판단을 다 하지 못했어요 — 아래 결정)" if d.kind in ("unknown", "error") else "발행 (보류 아님)")
    out = [f"### 뱁새 발행 판단 — {head}", ""]
    out += [f"- {ln.removeprefix('· ').removeprefix('!! ')}" for ln in lines[1:]]
    out.append(f"- **결정:** {d.why}")
    if dry:
        out.append("- 시험 실행이라 어차피 발행하지 않아요. 실제 실행이었다면 위 결정대로예요.")
    if sample:
        out.append("- 표본 실행(sample)이에요: 국내 종목을 줄인 실행이라 이 결정은 뜻이 없어요 (실제 실행의 확인 수와 같지 않을 수 있어요).")
    if d.hold:
        out.append("- '커밋 & 푸시' · 'data 브랜치에 올리기' 는 건너뛰어요 (main · data 브랜치 · 사이트 그대로 · 감시에는 중립). "
                   + ("already_published.py 가 발행 안 됨으로 봐서 다음 실행이 다시 해요." if d.kind == "floor"
                      else "확인 못 한 종가가 남아 있으면 다음 실행이 또 해 봐요."))
    return "\n".join(out) + "\n\n"


ANNOTATE = {"floor": ("warning", "발행 보류 (2차 출처 확인 비율 바닥 아래)"),
            "back": ("warning", "발행 보류 (날짜가 뒤로 감)"),
            "loss": ("warning", "같은 날 다시 발행 안 함 (지난 발행본의 종목을 잃음)"),
            "quiet": ("notice", "쉬는 실행 (같은 기준일 · 3시간 안 · 데이터 수집 없음)"),
            "same": ("notice", "같은 날 다시 발행 안 함 (더 낫지 않음)"),
            "unknown": ("warning", "발행 판단 확인 못 함 (보류 없이 판단)"),
            "stop": ("error", "발행 판단 못 함 (같은 날 다시 하는 실행 · 발행하지 않고 실패로 끝내요)"),
            "error": ("warning", "발행 판단 확인 못 함 (보류 없이 판단)")}


def _same_day_or_unknown(cur, prev, head):
    """오류로 멈춘 판단 (#161 리뷰 3차 B-S5): 오늘 파일의 한국 기준일이 지난 발행본 (없으면 main HEAD) 과 같거나, 같은지 모르면 True."""
    cp = cur.get("pxDate") if isinstance(cur, dict) else None
    ref = prev if isinstance(prev, dict) else head if isinstance(head, dict) else None
    pp = ref.get("pxDate") if isinstance(ref, dict) else None
    return cp is None or pp is None or cp == pp


def decide(argv=None, now_fn=None, cur_reader=read_cur, prev_reader=read_prev, live_reader=read_live):
    """한 번의 판단 (main 이 부르고 결과를 출력 · 요약 · GITHUB_OUTPUT 에 남겨요). 반환: Decision."""
    ap = argparse.ArgumentParser(description=f"2차 출처 날 발행 판단 (확인 비율 바닥 {COVERAGE_FLOOR_PCT}% · 같은 날 다시 발행은 더 나을 때만)")
    ap.add_argument("--data", default="data.json", help="오늘 만든 data.json (기본 ./data.json)")
    ap.add_argument("--prev-ref", default=None, help="지난 발행본의 git ref (시험 실행의 비교 커밋 · 주지 않으면 사이트의 발행본 = data 브랜치)")
    ap.add_argument("--bootstrap", action="store_true", help="bootstrap 실행: 직전 발행본과 비교하지 않아요 (바닥만)")
    ap.add_argument("--no-prev", action="store_true", help="직전 발행본을 받지 못함 (워크플로가 넘겨요): 비교 없이 (바닥만)")
    ap.add_argument("--now", default=None, help="로그의 시각 바꾸기 (ISO · 시간대 포함) — 시험용 (결정은 시각과 상관없어요)")
    ap.add_argument("--quiet", default=None, metavar="FILE", help="데이터 수집 단계가 쉬었다는 표시 파일 (있으면 그 까닭으로 감시에 중립인 보류)")
    a = ap.parse_args(argv)
    dry = (os.environ.get("DRY_RUN") or "").strip().lower() == "true"
    sample = (os.environ.get("SAMPLE_KR") or "0").strip() not in ("", "0")
    cur = prev = head = None
    try:
        now = dt.datetime.fromisoformat(a.now) if a.now else (now_fn() if now_fn else dt.datetime.now(KST))
        if now.tzinfo is None:
            raise ValueError("시각에 시간대가 없어요 (러너 시계는 UTC 예요)")
        cur, cur_note = cur_reader(a.data)
        live_failed = False
        if a.bootstrap:
            prev, prev_note = None, "bootstrap 실행이라 직전 발행본과 비교하지 않아요"
        elif a.no_prev:
            prev, prev_note = None, "직전 발행본(비교 커밋)을 받지 못했어요"
        elif a.prev_ref:
            prev, prev_note = prev_reader(a.prev_ref)
        else:                                 # #161 리뷰 3차 B-M1: 사이트의 발행본 (data 브랜치) 과 비교 · main HEAD 는 같은 날인지 · 다 올랐는지 볼 때만
            prev, prev_note = live_reader()
            head, _ = prev_reader("HEAD")
            live_failed = prev is None
        quiet = None
        if a.quiet and os.path.exists(a.quiet):
            with open(a.quiet, encoding="utf-8") as f:
                quiet = f.read().strip() or "데이터 수집 단계가 쉬었어요"
        if quiet:                             # 데이터를 모으지 않은 실행: 발행본 그대로라 발행할 것이 없고, 시험한 것도 없어 감시에 중립
            d, lines = Decision(True, False, f"{quiet}", "quiet"), [f"· {TITLE} — {now.astimezone(KST):%Y-%m-%d %H:%M} KST"]
        else:
            d, lines = evaluate(cur, cur_note, prev, prev_note, now, head=head, live_failed=live_failed)
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:200]}"
        lines = [f"· {TITLE}"]
        try:
            if cur is None:
                cur, _ = cur_reader(a.data)
            if prev is None and head is None and not (a.bootstrap or a.no_prev):
                head, _ = prev_reader(a.prev_ref or "HEAD")
            same = _same_day_or_unknown(cur, prev, head)
        except Exception:
            same = True
        if same and not (a.bootstrap or a.no_prev):
            # #161 리뷰 3차 B-S5: 같은 날 다시 하는 실행 (또는 같은지 모름) 의 판단이 멈추면 발행하지 않고 빨간 실행으로 (감시가 알려요 · 중립 아님)
            d = Decision(True, True, f"발행 판단이 오류로 멈췄어요 ({err}) — 같은 날 다시 하는 실행이거나 같은 날인지 몰라요 → 발행하지 않고 이 실행을 "
                                     "실패로 끝내요 (감시가 알려요)", "stop")
        else:
            d = Decision(False, True, f"발행 판단이 오류로 멈췄어요 ({err}) → 보류하지 않아요 (그날의 첫 실행 · 관문 · 화면 검사가 예전처럼 "
                                      "발행을 정해요)", "error")
    for ln in lines:
        print(ln, flush=True)
    tag = {"floor": "!! [보류] ", "same": "!! [같은 날 · 발행 안 함] ", "quiet": "!! [쉼] ", "stop": "!! [멈춤] "}.get(d.kind, "!! " if d.loud else "· ")
    print(tag + d.why + (" (시험 실행: 어차피 발행하지 않아요)" if dry else "") + (" (표본 실행: 이 결정은 뜻이 없어요)" if sample else ""), flush=True)
    # 알림 (실행 화면 · 09:13 점검이 읽어요): 바닥 보류 · 판단을 못 함 · 오류 → 경고, 같은 날 발행 안 함 → 알림 (2차 출처 날에는 흔해요)
    if os.environ.get("GITHUB_ACTIONS") == "true" and (d.hold or d.loud):
        kind, title = ANNOTATE.get(d.kind, ("warning", "발행 판단 확인 못 함 (보류 없이 판단)"))
        if d.kind == "unknown" and d.hold:
            title = "발행 판단 확인 못 함 (발행하지 않음)"
        print(f"::{kind} title={title}::{_gh_escape(d.why)}", flush=True)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        try:                                  # 요약을 못 써도 결정(아래 출력)은 그대로예요 — 크게 남겨요
            with open(summ, "a", encoding="utf-8") as f:
                f.write(summary_md(d, lines, dry, sample))
        except Exception as e:
            print(f"!! 실행 요약에 쓰지 못했어요 ({type(e).__name__}: {str(e)[:120]}) — 결정은 위 줄 그대로예요", flush=True)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:                                   # hold 를 마지막에 써요 — 발행 두 단계가 이 값을 봐요 (neutral: 감시에 중립인 보류 · 아래 표시 단계)
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"kind={d.kind}\nneutral={'true' if d.hold and d.kind in NEUTRAL else 'false'}\nhold={'true' if d.hold else 'false'}\n")
    return d


def main(argv=None, now_fn=None, cur_reader=read_cur, prev_reader=read_prev, live_reader=read_live):
    """decide 의 hold (참 · 거짓) — 시험이 부르는 모양."""
    return decide(argv, now_fn, cur_reader, prev_reader, live_reader).hold


STOP_EXIT = 3     # 판단할 수 없는 같은 날 다시 하는 실행 (kind stop) — 워크플로 단계가 이 코드를 보고 실패로 끝내요 (hold=true 는 이미 썼어요)


if __name__ == "__main__":
    sys.exit(STOP_EXIT if decide().kind == "stop" else 0)
