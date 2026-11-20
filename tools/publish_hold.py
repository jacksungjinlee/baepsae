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
2. 같은 날 다시 발행 (same_day_decision): 지난 발행본과 한국 기준일 (pxDate) · 미국 기준일 (usPxDate) 이 같은 실행 (already_published.py 가
   확인 못 한 종가가 남은 날 다시 돌게 해요) 은 더 나을 때만 발행해요 — 확인된 코스피 · 코스닥 종가가 지난 발행본보다 많고, 지난 발행본이 그
   날짜 종가로 실은 종목을 하나도 잃지 않았을 때 (pxSrc.own.reuse.lost == 0 · fetch_data.kr_same_day_reuse). 아니면 발행하지 않아요 (같은 보류 길).
보류하면: 발행 두 단계 ('커밋 & 푸시' · 'data 브랜치에 올리기') 가 건너뛰어요 (if: steps.hold.outputs.hold != 'true') → main · data 브랜치 · 사이트
그대로. 실행은 실패가 아니라 초록으로 끝나요. 감시에는 중립이에요 (watchdog.is_held_run). 관문 · 화면 검사는 보류해도 그대로 돌아요.
비교할 수 없으면: 오늘 기록을 못 읽으면 보류하지 않아요 (크게 · 경고 알림). 지난 발행본을 못 읽으면 같은 날인지 몰라 바닥만 봐요 (크게 · 경고 알림).
같은 날인데 더 나은지 알 수 없으면 (지난 발행본의 기록을 못 읽음 · 이 실행의 다시 쓰기 기록이 없음) 발행하지 않아요 — 그날 데이터는 이미 나가
있어요 (크게 · 알림). 이 확인이 오류로 멈추면 보류하지 않아요 (크게 · 경고 알림) — 예전처럼 관문과 화면 검사가 발행을 정해요.

쓰는 법: python tools/publish_hold.py [--prev-ref REF] [--bootstrap] [--no-prev]  → GITHUB_OUTPUT 에 hold=true|false (마지막 줄)
"""
import argparse
import collections
import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from validate_data import KST, PX_SRC_FB, _gh_escape  # noqa: E402  (관문과 같은 정의)

# 바닥 (Jack 2026-11-21: "set it from last week's 06:40 coverage"). 지난주 06:40 발행 (data 브랜치 · 코스피 · 코스닥 두 출처 확인 ÷ 그날 목록):
#   11-19 (pxDate 11-18) 2,743 / 2,771 = 98.99% · 11-20 (pxDate 11-19) 2,740 / 2,771 = 98.88% — 2차 출처 날은 이 둘뿐이에요.
#   11-13 · 11-14 · 11-17 은 KRX 최종본 날 (목록의 모든 코스피 · 코스닥 종목에 공식 종가 = 100%).
#   제안: 가장 낮은 98.88% 에서 조금 빼고 내림 → 98% (그날 목록 2,771 이면 확인 못 한 종목 55 까지 발행 · 지난주는 31 · 28).
#   정수 % 로 계산해요: 확인 × 100 ≥ 바닥 × 목록 이면 발행 (딱 바닥이면 발행).
COVERAGE_FLOOR_PCT = 98
FB_PARTS = ("mkt", "noDaum", "bad", "noYahoo", "diff")   # 확인 못 한 칸 (fetch_data.px_src_counts) — 코스피 · 코스닥 확인과 합치면 n
TITLE = f"발행 판단 (2차 출처 날 확인 비율 바닥 {COVERAGE_FLOOR_PCT}% · 같은 날 다시 발행은 더 나을 때만)"

Decision = collections.namedtuple("Decision", "hold loud why kind")   # kind: publish · floor · same · unknown · error


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


def same_day(cur, prev):
    """같은 날 다시 도는 실행인지: 지난 발행본과 한국 · 미국 기준일이 모두 같아요. (순수 함수)
    미국 마지막 확인 종가 (US carry) 가 들어오면 여기와 already_published.open_closes 의 미국 칸에서 미국 종가가 늘었는지도 봐요 (지금은 안 봐요)."""
    return (isinstance(cur, dict) and isinstance(prev, dict) and cur.get("pxDate") is not None
            and cur.get("pxDate") == prev.get("pxDate") and cur.get("usPxDate") == prev.get("usPxDate"))


def same_day_decision(cur_mode, prev_mode, cur_n, prev_n):
    """같은 날 다시 발행 (Decision · 순수 함수): 더 나을 때만 발행해요. cur_n · prev_n: kk_counts 의 셈 (모르면 None).
    - 오늘이 1차 출처 (KRX 최종본) 이고 지난 발행본이 2차 출처 → 발행 (최종본이 생겼어요).
    - 둘 다 1차 출처 → 예전 그대로 발행 (손으로 다시 돌린 실행).
    - 오늘 2차 출처 · 지난 발행본 1차 출처 → 발행하지 않아요 (최종본을 2차 출처로 바꾸지 않아요).
    - 둘 다 2차 출처 → 오늘 확인 > 지난 확인 이고 잃은 종목 0 일 때만. 셈을 모르거나 잃은 종목 수를 모르면 발행하지 않아요."""
    if cur_mode != PX_SRC_FB:
        if prev_mode == PX_SRC_FB:
            return Decision(False, False, "같은 기준일인데 오늘은 KRX 최종본 (1차 출처) — 2차 출처 발행본을 최종본으로 바꿔 발행해요", "publish")
        return Decision(False, False, "같은 기준일 · 1차 출처 — 예전 그대로 발행해요", "publish")
    if prev_mode != PX_SRC_FB:
        return Decision(True, True, f"같은 기준일인데 지난 발행본이 2차 출처가 아니에요 (pxSrc.px {prev_mode!r}) — 2차 출처로 바꿔 발행하지 않아요", "same")
    if cur_n is None or prev_n is None:
        return Decision(True, True, "같은 기준일인데 확인 수를 비교할 수 없어요 (기록을 읽지 못함) → 발행하지 않아요 (그날 데이터는 이미 나가 있어요)", "same")
    if cur_n["lost"] is None:
        return Decision(True, True, "같은 기준일인데 이 실행에 같은 날 다시 쓰기 기록 (pxSrc.own.reuse) 이 없어 잃은 종목을 몰라요 → 발행하지 않아요", "same")
    if cur_n["lost"] > 0:
        return Decision(True, True, f"같은 기준일 · 지난 발행본이 그 날짜 종가로 실은 종목 {cur_n['lost']:,}개를 이 실행이 잃었어요 (지금 두 출처가 다름 등) → "
                                    f"더 낫지 않아 발행하지 않아요 (확인 {prev_n['total']:,} → {cur_n['total']:,})", "same")
    if cur_n["total"] > prev_n["total"]:
        return Decision(False, False, f"같은 기준일 · 코스피 · 코스닥 확인 {prev_n['total']:,} → {cur_n['total']:,} (+{cur_n['total'] - prev_n['total']:,}) · "
                                      "잃은 종목 0 → 더 나아서 같은 날 데이터를 고쳐 발행해요", "publish")
    return Decision(True, False, f"같은 기준일 · 코스피 · 코스닥 확인 {prev_n['total']:,} → {cur_n['total']:,} — 더 많지 않아 발행하지 않아요 "
                                 "(지난 발행본 그대로)", "same")


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


# ── 실행 ────────────────────────────────────────────────────
def evaluate(cur, cur_note, prev, prev_note, now):
    """오늘 data.json · 직전 발행본 (dict 또는 None) → (Decision, 로그 줄들). 바닥 → 같은 날 다시 발행 순서로 한 번 정해요."""
    lines = [f"· {TITLE} — {now.astimezone(KST):%Y-%m-%d %H:%M} KST"]
    if cur is None:
        lines.append(f"!! 오늘 data.json: {cur_note}")
        return Decision(False, True, f"오늘 data.json 을 읽지 못했어요 ({cur_note}) → 보류하지 않아요 (관문이 봐요)", "unknown"), lines
    mode = day_mode(cur)
    cn, why_c = kk_counts(cur)
    lines.append(f"{'!! ' if mode == PX_SRC_FB and cn is None else '· '}오늘: pxSrc.px {mode!r} · {why_c} · 미국 기준일 {cur.get('usPxDate')}")
    d = floor_decision(mode, cn and cn["total"], cn and cn["listing"])
    if d.hold or d.kind == "unknown":
        return d, lines
    if prev is None:
        lines.append(f"{'!! ' if mode == PX_SRC_FB else '· '}직전 발행본: {prev_note} — 같은 날 다시 도는 실행인지 몰라 바닥만 봐요")
        return (Decision(False, True, d.why + " (직전 발행본을 읽지 못해 같은 날인지 몰라요 · 바닥만 봤어요)", "unknown") if mode == PX_SRC_FB else d), lines
    pmode = day_mode(prev)
    if not same_day(cur, prev):
        lines.append(f"· 직전 발행본: {prev_note} · 한국 {prev.get('pxDate')} · 미국 {prev.get('usPxDate')} → 새 날 (같은 날 다시 발행 아님)")
        return d, lines
    pn, why_p = kk_counts(prev) if pmode == PX_SRC_FB else (None, f"pxSrc.px {pmode!r}")
    lines.append(f"{'!! ' if pmode == PX_SRC_FB and pn is None else '· '}직전 발행본 (같은 날): {prev_note} · {why_p}")
    return same_day_decision(mode, pmode, cn, pn), lines


def summary_md(d, lines, dry, sample=False):
    head = {"floor": "보류 — 확인 비율이 바닥 아래라 발행하지 않아요", "same": "발행 안 함 — 같은 날 지난 발행본보다 낫지 않아요"}.get(d.kind, "발행 (보류 아님)")
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
            "same": ("notice", "같은 날 다시 발행 안 함 (더 낫지 않음)"),
            "unknown": ("warning", "발행 판단 확인 못 함 (보류 없이 판단)"),
            "error": ("warning", "발행 판단 확인 못 함 (보류 없이 판단)")}


def main(argv=None, now_fn=None, cur_reader=read_cur, prev_reader=read_prev):
    ap = argparse.ArgumentParser(description=f"2차 출처 날 발행 판단 (확인 비율 바닥 {COVERAGE_FLOOR_PCT}% · 같은 날 다시 발행은 더 나을 때만)")
    ap.add_argument("--data", default="data.json", help="오늘 만든 data.json (기본 ./data.json)")
    ap.add_argument("--prev-ref", default="HEAD", help="직전 발행본의 git ref (관문과 같은 기본 HEAD · 시험용으로 바꿔요)")
    ap.add_argument("--bootstrap", action="store_true", help="bootstrap 실행: 직전 발행본과 비교하지 않아요 (바닥만)")
    ap.add_argument("--no-prev", action="store_true", help="직전 발행본을 받지 못함 (워크플로가 넘겨요): 비교 없이 (바닥만)")
    ap.add_argument("--now", default=None, help="로그의 시각 바꾸기 (ISO · 시간대 포함) — 시험용 (결정은 시각과 상관없어요)")
    a = ap.parse_args(argv)
    dry = (os.environ.get("DRY_RUN") or "").strip().lower() == "true"
    sample = (os.environ.get("SAMPLE_KR") or "0").strip() not in ("", "0")
    try:
        now = dt.datetime.fromisoformat(a.now) if a.now else (now_fn() if now_fn else dt.datetime.now(KST))
        if now.tzinfo is None:
            raise ValueError("시각에 시간대가 없어요 (러너 시계는 UTC 예요)")
        cur, cur_note = cur_reader(a.data)
        if a.bootstrap:
            prev, prev_note = None, "bootstrap 실행이라 직전 발행본과 비교하지 않아요"
        elif a.no_prev:
            prev, prev_note = None, "직전 발행본(비교 커밋)을 받지 못했어요"
        else:
            prev, prev_note = prev_reader(a.prev_ref)
        d, lines = evaluate(cur, cur_note, prev, prev_note, now)
    except Exception as e:
        d = Decision(False, True, f"발행 판단이 오류로 멈췄어요 ({type(e).__name__}: {str(e)[:200]}) → 보류하지 않아요 "
                                  "(관문 · 화면 검사가 예전처럼 발행을 정해요)", "error")
        lines = [f"· {TITLE}"]
    for ln in lines:
        print(ln, flush=True)
    tag = {"floor": "!! [보류] ", "same": "!! [같은 날 · 발행 안 함] "}.get(d.kind, "!! " if d.loud else "· ")
    print(tag + d.why + (" (시험 실행: 어차피 발행하지 않아요)" if dry else "") + (" (표본 실행: 이 결정은 뜻이 없어요)" if sample else ""), flush=True)
    # 알림 (실행 화면 · 09:13 점검이 읽어요): 바닥 보류 · 판단을 못 함 · 오류 → 경고, 같은 날 발행 안 함 → 알림 (2차 출처 날에는 흔해요)
    if os.environ.get("GITHUB_ACTIONS") == "true" and (d.hold or d.loud):
        kind, title = ANNOTATE.get(d.kind, ("warning", "발행 판단 확인 못 함 (보류 없이 판단)"))
        print(f"::{kind} title={title}::{_gh_escape(d.why)}", flush=True)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        try:                                  # 요약을 못 써도 결정(아래 출력)은 그대로예요 — 크게 남겨요
            with open(summ, "a", encoding="utf-8") as f:
                f.write(summary_md(d, lines, dry, sample))
        except Exception as e:
            print(f"!! 실행 요약에 쓰지 못했어요 ({type(e).__name__}: {str(e)[:120]}) — 결정은 위 줄 그대로예요", flush=True)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:                                   # 마지막에 써요 — 발행 두 단계가 이 값을 봐요
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"hold={'true' if d.hold else 'false'}\n")
    return d.hold


if __name__ == "__main__":
    main()
    sys.exit(0)
