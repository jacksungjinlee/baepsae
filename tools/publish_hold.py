# -*- coding: utf-8 -*-
"""2차 출처 날의 이른 발행 보류 (2026-11-20 · Jack 의 "5. Yes").

Jack 이 승인한 제안 (2026-11-20, 그대로):
  "Backup days, hold an early publish. Before 08:00 KST on a backup day, publish only when confirmed closes reach at least 97% of
   the last publish's count. Today that means about 80 or fewer missing. Otherwise the run stops and the next one tries again.
   From 08:00, publish what we have; the rest show their last close with your line."

왜: 2차 출처 날(자원봉사 KRX 목록에 그 가격 날짜의 최종본이 없어 다음 × 야후로 종가를 만드는 날 · #137 · #151)에, 야후가 그날 한국 종가를
아직 채우지 않은 새벽(대략 06:30 전)에 돈 실행은 약 240종목을 확인하지 못한 채 발행해요. 그 뒤의 정해진 시각 실행은
already_published.py 가 '이미 발행됨'으로 보고 건너뛰어서, 그 종목들이 하루 종일 빠져 있었어요.

규칙 (hold_decision · 순수 함수 · 매일 실행이 한 번 불러요 — update-data.yml 'update' job 의 단계 id hold):
- 2차 출처 날(오늘 data.json 의 pxSrc.px == daum+yahoo)만 봐요. 1차 출처(KRX 목록 최종본) 날은 예전 그대로예요.
- 이 단계가 도는 시각(KST · 러너 시계는 UTC 라 KST 로 바꿔서 봐요)이 08:00 전이고, 오늘 두 출처로 확인된 종가 수가 직전 발행본의
  수 × 97% 보다 적으면 보류해요. 딱 97% 는 발행해요 (정수로 계산: 오늘 × 100 ≥ 직전 × 97). 08:00 부터는 있는 대로 발행해요.
- 확인된 수 = 코스피 · 코스닥의 두 출처 확인 수: pxSrc.fb.conf (다음 × 야후 종가가 원 단위까지 같은 종목 · fetch_data.kr_fb_confirm 이
  세요) 에서 코넥스 (#158: fb.knx.kept — 야후 × 네이버로 확인해 그날 파일에 넣은 코넥스 · conf 에 더해져 있어요) 를 뺀 수. 오늘과 직전 모두
  같은 범위로 세요. 마지막 확인 종가로 실은 종목 (pxSrc.own · 종목의 pxd · #159) 은 세지 않아요: pxSrc.n 이나 발행한 종목 수는 보지 않고,
  fb 의 칸이 맞아떨어질 때만 (n = 코스피 · 코스닥 확인 + mkt + noDaum + bad + noYahoo + diff — 목록의 종목마다 꼭 한 칸 · 코넥스는 mkt 에
  들어 있어요) 그 수를 써요. 맞지 않으면 그 기록은 비교에 쓰지 않아요.
- 직전 발행본 = 발행 관문이 비교하는 바로 그 파일 (git HEAD:data.json · 시험용 --prev-ref). 직전 발행본이 1차 출처 날 (pxSrc.px listing ·
  또는 pxSrc 가 생기기 전 파일) 이면 기준은 그 파일에서 공식 종가가 있는 코스피 · 코스닥 종목 수 (모두 KRX 최종본 · 코넥스 · 펀드 · 가격 없는
  종목 · 마지막 확인 종가는 빼요 — 발행한 종목만 들어 있어요: 시가총액 상위 약 2,500). 못 읽거나, 기록이 이상하거나, 날짜가 다르거나,
  bootstrap 실행이면 보류하지 않아요 (이유를 크게 남기고 경고 알림) — 비교가 없다고 발행을 막지 않아요.
보류하면: 발행 두 단계('커밋 & 푸시' · 'data 브랜치에 올리기')가 건너뛰어요 (if: steps.hold.outputs.hold != 'true') → main · data 브랜치 ·
사이트 그대로이고, already_published.py 는 '발행 안 됨'으로 봐서 다음 실행이 다시 해요. 실행은 실패가 아니라 초록으로 끝나요. 감시에는
중립이에요 (watchdog.is_held_run: 경보를 열지도 닫지도 않고 발행한 실행으로 세지 않아요 — 그 전의 실행으로 판단해요). 발행으로 헷갈리지
않게 두 단계는 '건너뜀'으로 남고 (배포 · 감시는 그 단계의 결과를 봐요), 로그 · 실행 요약 · 경고 알림에 크게 남겨요.
비교하지 못해 보류 없이 발행할 때도 (2차 출처 날 08:00 전) '!!' 줄과 경고 알림을 남겨요 (09:13 점검이 읽어요). 관문 · 화면 검사는 보류해도 그대로 돌아요. 시험 실행에서도 결정을 남겨요 (어차피 발행하지 않아요).
이 확인이 오류로 멈추면 보류하지 않아요 (크게 남겨요) — 예전처럼 관문과 화면 검사가 발행을 정해요.

쓰는 법: python tools/publish_hold.py [--prev-ref REF] [--bootstrap] [--no-prev]  → GITHUB_OUTPUT 에 hold=true|false (마지막 줄)
"""
import argparse
import collections
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from validate_data import KST, PX_SRC_FB, PX_SRC_LISTING, _gh_escape  # noqa: E402  (관문과 같은 정의)

HOLD_BEFORE = dt.time(8, 0)          # KST: 이 시각 전에만 보류해요 (Jack 2026-11-20)
HOLD_SHARE_PCT = 97                  # 직전 발행본의 확인 수 대비 % — 이보다 적으면 보류 (정수 계산 · 딱 97% 는 발행)
FB_PARTS = ("mkt", "noDaum", "bad", "noYahoo", "diff")   # 확인 못 한 칸 (fetch_data.px_src_counts) — 코스피 · 코스닥 확인과 합치면 n
KONEX_MARK = re.compile(r"(?:^|· )KONEX[^·]*상장")         # 종목 설명 dk 의 '… · KONEX 상장 · …' (fetch_data 의 '{시장} 상장')
TITLE = "이른 발행 보류 확인 (2차 출처 날 · 08:00 KST 전 · 직전 발행본의 97%)"

Decision = collections.namedtuple("Decision", "hold loud why")


def _count(v):
    """0 이상의 정수만 (True/False 는 아니에요)."""
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _n(v):
    return "?" if v is None else f"{v:,}"


def day_mode(data):
    """data.json 의 pxSrc.px (daum+yahoo = 2차 출처 날 · listing = 1차 출처 날) — 없으면 None. (순수 함수)"""
    src = data.get("pxSrc") if isinstance(data, dict) else None
    return src.get("px") if isinstance(src, dict) else None


def fb_confirmed(data):
    """data.json → (코스피 · 코스닥의 두 출처 확인 수 또는 None, 설명). 2차 출처 날의 pxSrc.fb.conf 에서 코넥스 (fb.knx.kept · #158) 를 빼고,
    칸이 맞아떨어질 때만 써요. 마지막 확인 종가로 실은 종목 (pxSrc.own · pxd) 은 conf 에 없어요 — 누가 넣으면 칸이 맞지 않아 None 이에요. (순수 함수)"""
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
    keys = ("n", "conf", *FB_PARTS)
    bad = [k for k in keys if _count(fb.get(k)) is None]
    if bad:
        return None, f"pxSrc.fb 의 칸이 비었거나 이상해요 ({', '.join(bad)} · pxDate {data.get('pxDate')})"
    n, conf, left = fb["n"], fb["conf"], sum(fb[k] for k in FB_PARTS)
    knx, kept = fb.get("knx"), 0
    if knx is not None:                        # #158: 코넥스를 그날 파일에 넣은 날 conf = 다음 × 야후 확인 + knx.kept
        if not isinstance(knx, dict) or _count(knx.get("kept")) is None or knx["kept"] > conf:
            return None, (f"pxSrc.fb.knx (코넥스) 의 kept 가 비었거나 이상해요 ({str(knx)[:80] if not isinstance(knx, dict) else knx.get('kept')!r} · "
                          f"pxDate {data.get('pxDate')}) — 코스피 · 코스닥 확인 수를 알 수 없어 비교에 쓰지 않아요")
        kept = knx["kept"]
    kk = conf - kept
    if kk + left != n:
        return None, (f"pxSrc.fb 의 칸이 맞지 않아요: 코스피 · 코스닥 확인 {kk:,} + 확인 못 한 칸 {left:,} ≠ 목록 {n:,} (pxDate {data.get('pxDate')}"
                      + (f" · conf {conf:,} 에서 코넥스 {kept:,} 를 뺐어요" if knx is not None else "") + ") — "
                      "확인 수에 다른 것(마지막 확인 종가 등)이 섞였을 수 있어 비교에 쓰지 않아요")
    return kk, (f"코스피 · 코스닥 두 출처 확인 {kk:,} / 목록 {n:,}" + (f" (코넥스 {kept:,} 는 빼고 · conf {conf:,})" if knx is not None else "")
                + f" (pxDate {data.get('pxDate')})")


def _price_ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def listing_count(data):
    """1차 출처 날 발행본 (pxSrc.px listing · 또는 pxSrc 가 생기기 전 파일 — 그때는 2차 출처 날이 없었어요) → (공식 종가가 있는 코스피 ·
    코스닥 종목 수 또는 None, 설명). 그 파일의 국내 종목은 모두 KRX 최종본 공식 종가예요. 코넥스 (종목 설명의 'KONEX 상장') · 펀드 · 가격이 없는
    종목 · 마지막 확인 종가 (pxd) 는 빼요 — 오늘 수도 코넥스를 빼니까요. 발행한 종목 (시가총액 상위 약 2,500) 만 들어 있어요. (순수 함수)"""
    if not isinstance(data, dict):
        return None, "data.json 을 읽지 못했어요"
    if "pxSrc" in data:
        src = data["pxSrc"]
        if not isinstance(src, dict) or src.get("px") != PX_SRC_LISTING:
            return None, f"1차 출처 날이 아니에요 (pxSrc {str(src)[:60]})"
        if src.get("date") != data.get("pxDate"):
            return None, f"pxSrc.date {src.get('date')!r} 가 pxDate {data.get('pxDate')!r} 와 달라요"
    stocks = data.get("stocks")
    if not isinstance(stocks, list):
        return None, "stocks 가 없어요"
    n = knx = fund = nopx = carried = 0
    for x in stocks:
        if not isinstance(x, dict) or x.get("cls") != "kr":
            continue
        if x.get("fund"):
            fund += 1
        elif x.get("pxd") is not None:
            carried += 1
        elif not _price_ok(x.get("price")):
            nopx += 1
        elif KONEX_MARK.search(str(x.get("dk") or "")):
            knx += 1
        else:
            n += 1
    if not n:
        return None, f"공식 종가가 있는 코스피 · 코스닥 종목이 없어요 (pxDate {data.get('pxDate')})"
    return n, (f"1차 출처 날 발행본: 공식 종가가 있는 코스피 · 코스닥 종목 {n:,} (발행한 국내 종목만 · 코넥스 {knx:,} · 펀드 {fund:,} · "
               f"가격 없음 {nopx:,}" + (f" · 마지막 확인 종가 {carried:,}" if carried else "") + f" 뺌 · pxDate {data.get('pxDate')})")


def last_count(prev):
    """직전 발행본의 기준 수: 2차 출처 날이면 fb_confirmed, 1차 출처 날 (또는 pxSrc 가 생기기 전 파일) 이면 listing_count. (순수 함수)"""
    if isinstance(prev, dict) and ("pxSrc" not in prev or day_mode(prev) == PX_SRC_LISTING):
        return listing_count(prev)
    return fb_confirmed(prev)


def share_line(prev):
    """직전 발행본 확인 수의 97% — 오늘 이 수 이상이면 발행해요 (올림 · 정수). (순수 함수)"""
    return -(-prev * HOLD_SHARE_PCT // 100)


def hold_decision(mode, now, conf_today, conf_prev):
    """이 실행을 보류할지 (Decision(hold, loud, why)). (순수 함수 · 규칙은 여기 한 곳)
    mode: 오늘 data.json 의 pxSrc.px · now: 결정 시각 (시간대가 있는 datetime — KST 로 바꿔 봐요) ·
    conf_today · conf_prev: 오늘 · 직전 발행본의 두 출처 확인 수 (모르면 None)."""
    if now.tzinfo is None:
        raise ValueError("결정 시각에 시간대가 없어요 (러너 시계는 UTC 예요)")
    t = now.astimezone(KST)
    at = f"{t:%m-%d %H:%M} KST"
    if mode != PX_SRC_FB:
        return Decision(False, False, f"2차 출처 날이 아니에요 (pxSrc.px {mode!r}) → 보류 규칙 없이 예전 그대로 발행해요 ({at})")
    if t.time() >= HOLD_BEFORE:
        return Decision(False, False, f"{at} — 08:00 KST 부터는 있는 대로 발행해요 (두 출처 확인 {_n(conf_today)} · 직전 발행본 {_n(conf_prev)})")
    if conf_today is None:
        return Decision(False, True, f"오늘 두 출처 확인 수를 몰라요 → 보류하지 않아요 ({at} · 비교가 없다고 발행을 막지 않아요)")
    if conf_prev is None:
        return Decision(False, True, f"직전 발행본의 두 출처 확인 수를 몰라요 → 보류하지 않아요 ({at} · 오늘 {conf_today:,} · "
                                     "비교가 없다고 발행을 막지 않아요)")
    line = share_line(conf_prev)
    if conf_today >= line:
        return Decision(False, False, f"두 출처로 확인된 코스피 · 코스닥 종가 {conf_today:,} ≥ 97% 선 {line:,} (직전 발행본 {conf_prev:,}) · {at} → 발행해요")
    return Decision(True, True, f"두 출처로 확인된 코스피 · 코스닥 종가 {conf_today:,} < 97% 선 {line:,} (직전 발행본 {conf_prev:,} · 모자람 {line - conf_today:,}) · "
                                f"{at} (08:00 전) → 이 실행은 발행하지 않아요. 다음 실행이 다시 해요")


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
    """오늘 data.json · 직전 발행본(dict 또는 None)과 결정 시각 → (Decision, 로그 줄들). 결정은 hold_decision 한 번."""
    lines = [f"· {TITLE} — 결정 시각 {now.astimezone(KST):%Y-%m-%d %H:%M} KST"]
    if cur is None:
        lines.append(f"!! 오늘 data.json: {cur_note}")
        return Decision(False, True, f"오늘 data.json 을 읽지 못했어요 ({cur_note}) → 보류하지 않아요 (관문이 봐요)"), lines
    mode = day_mode(cur)
    today, why_t = fb_confirmed(cur)
    if prev is None:
        last, why_p = None, prev_note
    else:
        last, why_p = last_count(prev)
        why_p = f"{prev_note} · {why_p}"
    d = hold_decision(mode, now, today, last)
    lines.append(f"{'!! ' if mode == PX_SRC_FB and today is None else '· '}오늘: pxSrc.px {mode!r} · {why_t}")
    if mode == PX_SRC_FB:
        lines.append(f"{'!! ' if d.loud and last is None else '· '}직전 발행본: {why_p}")
    return d, lines


def summary_md(d, lines, dry, sample=False):
    head = "보류 — 이 실행은 발행하지 않아요" if d.hold else "발행 (보류 아님)"
    out = [f"### 뱁새 이른 발행 보류 확인 — {head}", ""]
    out += [f"- {ln.removeprefix('· ').removeprefix('!! ')}" for ln in lines[1:]]
    out.append(f"- **결정:** {d.why}")
    if dry:
        out.append("- 시험 실행이라 어차피 발행하지 않아요. 실제 실행이었다면 위 결정대로예요.")
    if sample:
        out.append("- 표본 실행(sample)이에요: 국내 종목을 줄인 실행이라 이 결정은 뜻이 없어요 (실제 실행의 확인 수와 같지 않을 수 있어요).")
    if d.hold:
        out.append("- '커밋 & 푸시' · 'data 브랜치에 올리기' 는 건너뛰어요 (main · data 브랜치 · 사이트 그대로). "
                   "already_published.py 가 발행 안 됨으로 봐서 다음 실행이 다시 해요.")
    return "\n".join(out) + "\n\n"


def main(argv=None, now_fn=None, cur_reader=read_cur, prev_reader=read_prev):
    ap = argparse.ArgumentParser(description="2차 출처 날의 이른 발행 보류 (08:00 KST 전 · 직전 발행본의 97%)")
    ap.add_argument("--data", default="data.json", help="오늘 만든 data.json (기본 ./data.json)")
    ap.add_argument("--prev-ref", default="HEAD", help="직전 발행본의 git ref (관문과 같은 기본 HEAD · 시험용으로 바꿔요)")
    ap.add_argument("--bootstrap", action="store_true", help="bootstrap 실행: 직전 발행본과 비교하지 않아요 (보류 없음)")
    ap.add_argument("--no-prev", action="store_true", help="직전 발행본을 받지 못함 (워크플로가 넘겨요): 비교 없이 (보류 없음)")
    ap.add_argument("--now", default=None, help="결정 시각 바꾸기 (ISO · 시간대 포함) — 시험용")
    a = ap.parse_args(argv)
    dry = (os.environ.get("DRY_RUN") or "").strip().lower() == "true"
    sample = (os.environ.get("SAMPLE_KR") or "0").strip() not in ("", "0")
    try:
        now = dt.datetime.fromisoformat(a.now) if a.now else (now_fn() if now_fn else dt.datetime.now(KST))
        cur, cur_note = cur_reader(a.data)
        if a.bootstrap:
            prev, prev_note = None, "bootstrap 실행이라 직전 발행본과 비교하지 않아요"
        elif a.no_prev:
            prev, prev_note = None, "직전 발행본(비교 커밋)을 받지 못했어요"
        else:
            prev, prev_note = prev_reader(a.prev_ref)
        d, lines = evaluate(cur, cur_note, prev, prev_note, now)
    except Exception as e:
        d = Decision(False, True, f"이른 발행 보류 확인이 오류로 멈췄어요 ({type(e).__name__}: {str(e)[:200]}) → 보류하지 않아요 "
                                  "(관문 · 화면 검사가 예전처럼 발행을 정해요)")
        lines = [f"· {TITLE}"]
    for ln in lines:
        print(ln, flush=True)
    print(("!! [보류] " if d.hold else ("!! " if d.loud else "· ")) + d.why + (" (시험 실행: 어차피 발행하지 않아요)" if dry else "")
          + (" (표본 실행: 이 결정은 뜻이 없어요)" if sample else ""), flush=True)
    # 경고 알림 (실행 화면 · 09:13 점검이 읽어요): 보류했을 때, 그리고 2차 출처 날 08:00 전에 비교하지 못해 보류 없이 발행할 때 · 오류로 멈췄을 때
    if os.environ.get("GITHUB_ACTIONS") == "true" and (d.hold or d.loud):
        title = "발행 보류 (2차 출처 날 · 08:00 KST 전)" if d.hold else "이른 발행 보류 확인 못 함 (보류 없이 발행)"
        print(f"::warning title={title}::{_gh_escape(d.why)}", flush=True)
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
