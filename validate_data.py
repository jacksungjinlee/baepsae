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
규칙: 오늘(KST) 이전, 시가총액 90% 이상, 마지막 커밋이 그 날짜 16:00 KST 이후.
한국 공식 종가 = 시가총액 ÷ 상장주식수 (목록 파일의 Close 열은 저녁엔 시간외 가격이에요).

임계값은 2026-10-17 발행본(DART 정상 마지막 날)에 맞춰 정했어요. 안전 규칙이라 함부로 낮추지 않습니다.
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
FILES = ("data.json", "corp.json", "disc.json", "macro.json")
LIST_URL = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/{d}.csv"
COMMITS_API = "https://api.github.com/repos/FinanceData/fdr_krx_data_cache/commits"
FINAL_HOUR = 16
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


def is_final(d, text, get_text, get_commit, today):
    """(최종본인가, 설명)."""
    closes, share = official_closes(text)
    if share < MIN_CAP_SHARE:
        return False, f"시가총액 {share:.0%}"
    ct = get_commit(d)
    if ct is not None:
        cut = dt.datetime.combine(d, dt.time(FINAL_HOUR), KST)
        return ct >= cut, f"{ct:%m-%d %H:%M} KST 커밋"
    later = [d + dt.timedelta(days=i) for i in range(1, (today - d).days + 1)]
    for e in later:
        t = get_text(e)
        if t is not None and official_closes(t)[1] >= MIN_CAP_SHARE:
            return True, "커밋 시각 확인 불가 · 다음 거래일 파일 있음"
    return False, "커밋 시각 확인 불가 · 다음 거래일 파일 없음"


def latest_final(today, get_text=http_listing, get_commit=http_commit_kst):
    """오늘 이전의 가장 최근 최종본: (날짜, 공식 종가 dict, 설명) 또는 (None, None, 사유)."""
    for back in range(1, LOOKBACK_DAYS + 1):
        d = today - dt.timedelta(days=back)
        text = get_text(d)
        if text is None:
            continue
        ok, how = is_final(d, text, get_text, get_commit, today)
        if ok:
            return d, official_closes(text)[0], how
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


def run_checks(cur, prev, final, today, mode="publish", count_between=None, notes=None):
    """cur/prev: {"data":…, "corp":…, "disc":…, "macro":…} (prev 는 None 가능).
    final: {"date", "closes", "how"} — 비교할 최종본 (None 이면 날짜·가격 검사 실패).
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
    ppx = prev_px_date(pdata, notes) if pdata else None
    if pdata:
        rep.add("pxDate 가 뒤로 가지 않음", px is not None and ppx is not None and px >= ppx, px, f"≥ {ppx}")
    rep.add("KOSPI 마지막 날 = pxDate", day(data.get("ksDate")) == px and px is not None, data.get("ksDate"), px)

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

    # 경고만
    rep.add("공시 목록 조회", True, "성공" if disc.get("listOk") else "실패", "실패면 경고", warn=not disc.get("listOk"))
    return rep


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


def main(argv=None):
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

    try:
        if mode == "live":
            px = day(cur["data"].get("pxDate"))
            text = http_listing(px) if px else None
            ok, how = is_final(px, text, http_listing, http_commit_kst, today) if text else (False, "파일 없음")
            final = {"date": px, "closes": official_closes(text)[0], "how": how} if ok else None
        else:
            d, closes, how = latest_final(today)
            final = {"date": d, "closes": closes, "how": how} if d else None
            if not d:
                print(f"!! 최종본 날짜: {how}")
    except Exception as e:
        print(f"!! 최종본 목록을 확인하지 못했어요: {e}")
        final = None

    rep = run_checks(cur, prev, final, today, mode=mode, count_between=count_final_between, notes=notes)
    for n in notes:
        print(f"· {n}")
    print()
    print(rep.table())
    print()
    bad, warn = rep.failed, rep.warned
    print(f"결과: {'FAIL' if bad else 'PASS'} · 실패 {len(bad)} · 경고 {len(warn)} · 전체 {len(rep.rows)}")
    for r in bad:
        print(f"!! FAIL  {r[0]}: {r[1]} (기준 {r[2]})")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(f"### 뱁새 발행 관문 — {'FAIL' if bad else 'PASS'} ({mode})\n\n{rep.markdown()}\n\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
