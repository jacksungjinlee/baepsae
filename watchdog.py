#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뱁새 감시 — watchdog.py (v17.6 Part 1)
──────────────────────────────────────────────────────────────
매일 실행(시세 데이터 갱신)과 배포(Deploy)를 믿지 않고, 사용자가 실제로 받는 사이트를 밖에서 따로 확인해요.

  python3 watchdog.py                    # 점검 → 문제가 있으면 '뱁새 데이터 경보' 이슈(하나만)를 열거나 댓글, 빨갛게 끝나요.
                                         #        정상이면 열린 경보를 '정상화됐어요'로 닫고 healthchecks.io 에 알려요
  python3 watchdog.py --dry              # 점검만 (이슈·알림 없이) — 로컬 시험용
  python3 watchdog.py --selftest broken  # 사이트 파일을 받은 뒤 일부러 망가뜨려서 (경보가 열리는지 시험, 이슈에 [시험] 표시)
                                         #   healthchecks.io 에 '문제'를 보낸 뒤 진짜 파일로 다시 점검해서, 정상이면 이슈를 닫고 '정상'을 보내요
  python3 watchdog.py --decide           # workflow_run 으로 불렸을 때: 지금 점검할지 (GITHUB_OUTPUT 에 go=true|false)

점검 (하나라도 실패면 경보):
1. 사이트의 네 JSON (…/data.json?t=지금) → validate_data.py --live (절대 기준).
2. 낡은 가격: 15:30 KST 이후에만. 기대 pxDate = 둘 중 늦은 날 — fdr_krx_data_cache 의 오늘 전 마지막 '최종본' 목록 날짜,
   야후 ^KS11 일봉의 오늘 전 마지막 날 (둘 다 발행 파이프라인과 따로 받아요). 사이트 pxDate 가 그보다 이르면 실패.
3. 실행 결과: main 의 시세 데이터 갱신 · Deploy 의 마지막 '끝난' 실행이 성공 (시험 실행 · 돌고 있는 실행 · 시작도 못 하고
   대기 중에 밀려난 실행은 빼요). 정해진 시각 실행이 꺼져 있으면(60일 규칙 등) 실패.
4. 페이지: baepsae.html · app.html · styleguide.html 이 200 이고 같은 빌드. Actions 배포면 빌드 표시
   (<meta name="baepsae-build">)가 main 의 커밋과 같아야 하고, 브랜치 배포면 페이지가 main 의 파일과 한 글자도 같아야 해요
   (main 이 바뀐 지 45분 안이거나 배포가 돌고 있으면 기다려요).
5. 사이트의 data.json 이 발행본과 한 글자도 같아요: 브랜치 배포면 main 의 것, Actions 배포면 data 브랜치 끝의 것
   (그 끝이 바뀐 지 45분 안이면 기다려요). 데이터만 바뀐 날 배포나 Pages 빌드가 실패해도 잡아요.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

import requests

import validate_data as V

KST = ZoneInfo("Asia/Seoul")
SITE = os.environ.get("BAEPSAE_SITE", "https://jacksungjinlee.github.io/baepsae/")
REPO = os.environ.get("GITHUB_REPOSITORY", "jacksungjinlee/baepsae")
API = "https://api.github.com"
PAGES = ("baepsae.html", "app.html", "styleguide.html")
STALE_FROM = dt.time(15, 30)              # 이 시각(KST) 전에는 낡은 가격을 보지 않아요 (그날 실행이 아직 돌 수 있어요)
GRACE = dt.timedelta(minutes=45)          # main 이 바뀐 직후에는 배포가 따라올 시간을 줘요
ISSUE_TITLE = "뱁새 데이터 경보"
LABEL = "data-alert"
MENTION = "@jacksungjinlee"
DATA_WF, DEPLOY_WF, WATCH_WF = "update-data.yml", "deploy.yml", "watchdog.yml"
DATA_NAME, DEPLOY_NAME = "시세 데이터 갱신", "Deploy"
DRY_MARK = "시험 실행"                     # update-data.yml 의 run-name: 시험 실행은 제목에 이 말이 붙어요
PUSH_STEP = "data 브랜치에 올리기"          # update-data.yml 에서 data 브랜치에 실제로 올린 단계
BUILD_RE = re.compile(r'<meta name="baepsae-build" content="([^"]*)">')
SHA_RE = re.compile(r"[0-9a-f]{40}")
UA = {"User-Agent": "baepsae-watchdog"}


def kst(t):
    return t.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def parse_time(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


# ── 밖과 이야기하기 (시험에서는 가짜로 바꿔요) ───────────────
class Net:
    def __init__(self, token=None):
        self.token = token
        self.s = requests.Session()

    def get(self, url, timeout=30):
        last = None
        for i in range(3):
            try:
                return self.s.get(url, timeout=timeout, headers=UA)
            except requests.RequestException as e:
                last = e
                time.sleep(2 * (i + 1))
        raise RuntimeError(f"{url.split('?')[0]}: {type(last).__name__}")

    def gh(self, method, path, body=None, ok=(200, 201, 204)):
        """GitHub REST. (상태 코드, JSON 또는 None). ok 밖의 상태는 예외 (404 는 호출한 쪽이 ok 에 넣어서 받아요)."""
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", **UA}
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        r = self.s.request(method, API + path, headers=h, json=body, timeout=30)
        if r.status_code not in ok:
            raise RuntimeError(f"GitHub {method} {path}: {r.status_code} {r.text[:200]}")
        return r.status_code, (r.json() if r.content else None)


class Report:
    def __init__(self):
        self.rows = []          # (이름, 상태 PASS|FAIL|SKIP, 내용)

    def add(self, name, ok, detail):
        self.rows.append((name, "PASS" if ok else "FAIL", detail))

    def skip(self, name, why):
        self.rows.append((name, "SKIP", why))

    @property
    def problems(self):
        return [r for r in self.rows if r[1] == "FAIL"]

    def markdown(self):
        out = ["| 점검 | 결과 | 내용 |", "|---|---|---|"]
        for n, s, d in self.rows:
            out.append(f"| {n} | {s} | {str(d).replace('|', '/')} |")
        return "\n".join(out)


# ── 1. 사이트의 네 파일 → validate_data.py --live ─────────────
def fetch_live(net, out_dir, now):
    """네 JSON 을 out_dir 에 받아요. 반환: 못 받은 파일 설명 목록."""
    bad = []
    for f in V.FILES:
        try:
            r = net.get(f"{SITE}{f}?t={int(now.timestamp())}")
        except RuntimeError as e:
            bad.append(f"{f}: {e}")
            continue
        if r.status_code != 200:
            bad.append(f"{f}: HTTP {r.status_code}")
            continue
        with open(os.path.join(out_dir, f), "wb") as fh:
            fh.write(r.content)
    return bad


def break_for_selftest(out_dir):
    """--selftest broken: 받은 data.json 에서 필수 종목을 모두 빼요 → 관문의 '필수 종목' 검사가 실패해야 해요."""
    p = os.path.join(out_dir, "data.json")
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    data["stocks"] = [s for s in data.get("stocks", []) if s.get("t") not in V.MUST]
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, allow_nan=False)


def run_live_gate(dir_, run=subprocess.run):
    """(통과했나, 관문 결과 markdown). 관문의 출력(알림 포함)은 그대로 이 실행의 로그에 보여요."""
    with tempfile.NamedTemporaryFile("r", suffix=".md", delete=False) as tmp:
        md_path = tmp.name
    env = {**os.environ, "GITHUB_STEP_SUMMARY": md_path}
    here = os.path.dirname(os.path.abspath(__file__))
    r = run([sys.executable, os.path.join(here, "validate_data.py"), "--live", "--dir", dir_], env=env,
            capture_output=True, text=True, cwd=here)
    print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", file=sys.stderr, flush=True)
    try:
        with open(md_path, encoding="utf-8") as fh:
            md = fh.read().strip()
    finally:
        os.unlink(md_path)
    fails = [ln[len("!! FAIL  "):] for ln in r.stdout.splitlines() if ln.startswith("!! FAIL  ")]
    return r.returncode == 0, md, fails


# ── 2. 낡은 가격 ─────────────────────────────────────────────
def _retry(fn, n=3, sleep=time.sleep):
    last = None
    for i in range(n):
        try:
            return fn()
        except Exception as e:
            last = e
            if i < n - 1:
                sleep(i + 1)
    raise last


def expected_px(today, final_day=None, ks_days=None, sleep=time.sleep):
    """(기대 pxDate 또는 None, 출처 설명). 두 출처 중 늦은 날. 하나만 답하면 그것으로 (크게 적어요)."""
    final_day = final_day or (lambda t: V.latest_final(t, special=V.load_special_sessions())[0])
    ks_days = ks_days or V._yahoo_kospi_dates
    got, notes = [], []
    try:
        d = _retry(lambda: final_day(today), sleep=sleep)
        if d:
            got.append(d)
            notes.append(f"최종본 목록 {d}")
        else:
            notes.append("최종본 목록: 최근 10일 안에 없음")
    except Exception as e:
        notes.append(f"최종본 목록: 받지 못함 ({type(e).__name__})")
    try:
        past = [d for d in _retry(ks_days, sleep=sleep) if d < today]
        if past:
            got.append(past[-1])
            notes.append(f"야후 ^KS11 {past[-1]}")
        else:
            notes.append("야후 ^KS11: 오늘 전 일봉 없음")
    except Exception as e:
        notes.append(f"야후 ^KS11: 받지 못함 ({type(e).__name__})")
    return (max(got) if got else None), " · ".join(notes)


def check_stale(rep, live_px, now, expect=expected_px):
    name = "낡은 가격 (15:30 KST 이후)"
    if now.astimezone(KST).time() < STALE_FROM:
        rep.skip(name, f"{STALE_FROM:%H:%M} KST 전이라 보지 않아요 (그날 실행이 아직 돌 수 있어요)")
        return
    want, src = expect(now.astimezone(KST).date())
    if want is None:
        rep.add(name, False, f"기대 날짜를 정하지 못했어요 ({src})")
        return
    have = V.day(live_px)
    rep.add(name, have is not None and have >= want, f"사이트 {live_px} · 기대 ≥ {want} ({src})")


# ── 3. 실행 결과 ─────────────────────────────────────────────
def never_started(net, run):
    """취소된 실행이 한 단계도 돌지 않았나 (같은 줄의 새 실행에 밀려난 대기분 — 실패가 아니에요)."""
    _, js = net.gh("GET", f"/repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=50")
    return all(not j.get("steps") for j in (js or {}).get("jobs", []))


def is_noop_deploy(net, run):
    """Deploy 가 아무것도 올리지 않은 실행 (decide 가 go=false → build 가 건너뜀). 성공으로 끝나지만 배포가 아니에요."""
    _, js = net.gh("GET", f"/repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=50")
    jobs = {j.get("name"): j.get("conclusion") for j in (js or {}).get("jobs", [])}
    return run.get("conclusion") == "success" and jobs.get("build") in (None, "skipped")


def check_runs(rep, net, wf, label, skip_noop=False):
    st, info = net.gh("GET", f"/repos/{REPO}/actions/workflows/{wf}", ok=(200, 404))
    if st == 404:
        rep.skip(f"{label} 실행", f"{wf} 가 아직 main 에 없어요")
        return None
    if info.get("state") != "active":
        rep.add(f"{label} 켜짐", False, f"{wf} 가 꺼져 있어요 ({info.get('state')}) — 정해진 시각 실행이 돌지 않아요")
    _, runs = net.gh("GET", f"/repos/{REPO}/actions/workflows/{wf}/runs?branch=main&status=completed&per_page=30")
    for r in (runs or {}).get("workflow_runs", []):
        if DRY_MARK in (r.get("display_title") or ""):
            continue
        c = r.get("conclusion")
        when = kst(parse_time(r.get("run_started_at") or r["created_at"]))
        if c in ("cancelled", "skipped") and never_started(net, r):
            continue
        if skip_noop and is_noop_deploy(net, r):           # 건너뛴 배포가 그 전의 실패한 배포를 가리지 않게
            continue
        rep.add(f"{label} 마지막 실행", c == "success", f"{c} · {when} · {r.get('event')} · {r.get('html_url')}")
        return r
    if skip_noop:
        rep.skip(f"{label} 마지막 실행", "최근 30번 모두 건너뛴 배포예요 (Pages 가 아직 브랜치에서 배포되는 동안은 정상)")
        return None
    rep.add(f"{label} 마지막 실행", False, "main 에서 끝난 실행을 찾지 못했어요")
    return None


# ── 4. 페이지와 빌드 ─────────────────────────────────────────
def ref_file(ref, path):
    """지금 origin 의 그 브랜치(main · data)에 있는 파일 (사이트와 비교해요)."""
    subprocess.run(["git", "fetch", "-q", "--depth=1", "origin", f"+refs/heads/{ref}:refs/remotes/origin/{ref}"],
                   check=True, capture_output=True, timeout=120)
    return subprocess.run(["git", "show", f"origin/{ref}:{path}"], check=True, capture_output=True, timeout=60).stdout


def deploy_busy(net):
    for status in ("in_progress", "queued"):
        st, runs = net.gh("GET", f"/repos/{REPO}/actions/workflows/{DEPLOY_WF}/runs?status={status}&per_page=5", ok=(200, 404))
        if st == 200 and (runs or {}).get("total_count"):
            return True
    return False


def check_pages(rep, net, now, read_ref=ref_file):
    """페이지와 빌드. 반환: 배포 방식 "actions" · "branch" (페이지를 하나도 못 받으면 None)."""
    pages, tags = {}, {}
    for p in PAGES:
        try:
            r = net.get(f"{SITE}{p}?t={int(now.timestamp())}")
        except RuntimeError as e:
            rep.add(f"{p} 열림", False, str(e))
            continue
        rep.add(f"{p} 열림", r.status_code == 200, f"HTTP {r.status_code}")
        if r.status_code == 200:
            pages[p] = r.content
            m = BUILD_RE.search(r.content[:4000].decode("utf-8", "replace"))
            tags[p] = m.group(1) if m else None
    if not pages:
        return None
    _, head = net.gh("GET", f"/repos/{REPO}/commits/main")
    head_sha, head_at = head["sha"], parse_time(head["commit"]["committer"]["date"])
    fresh = now - head_at < GRACE
    wait = f"main 이 {int((now - head_at).total_seconds() // 60)}분 전에 바뀌어 배포를 기다려요" if fresh else None
    if any(t and SHA_RE.fullmatch(t) for t in tags.values()):
        shas = set(tags.values())
        if len(shas) > 1:
            rep.add("페이지 빌드가 모두 같음", False, " · ".join(f"{p} {str(t)[:7]}" for p, t in tags.items()))
        live = next(iter(t for t in tags.values() if t))
        ok = live == head_sha
        if not ok and (fresh or deploy_busy(net)):
            rep.skip("사이트 빌드 = main", wait or f"배포가 돌고 있어요 (사이트 {live[:7]} · main {head_sha[:7]})")
            return "actions"
        rep.add("사이트 빌드 = main", ok, f"사이트 {live[:7]} · main {head_sha[:7]} (Actions 배포)")
        return "actions"
    diff = []
    for p, body in pages.items():
        want = read_ref("main", p)
        if hashlib.sha256(body).digest() != hashlib.sha256(want).digest():
            diff.append(p)
    if diff and fresh:
        rep.skip("사이트 페이지 = main", f"{', '.join(diff)} 다름 — {wait}")
        return "branch"
    rep.add("사이트 페이지 = main", not diff,
            "모두 같음 (브랜치 배포)" if not diff else f"다름: {', '.join(diff)} — Pages 가 예전 빌드를 보여 줘요 (main {head_sha[:7]})")
    return "branch"


def check_live_data(rep, net, now, live_sha, mode, read_ref=ref_file):
    """사이트의 data.json = 발행본 (브랜치 배포: main · Actions 배포: data 브랜치 끝). 발행본이 바뀐 지 45분 안이면 기다려요."""
    name = "사이트 data.json = 발행본"
    if live_sha is None or mode is None:
        rep.skip(name, "사이트의 data.json 이나 페이지를 받지 못해 비교하지 않아요 (위 줄에서 실패로 잡아요)")
        return
    ref = "data" if mode == "actions" else "main"
    st, tip = net.gh("GET", f"/repos/{REPO}/commits/{ref}", ok=(200, 404, 422))
    if st != 200:
        rep.add(name, False, f"{ref} 브랜치가 없어요 — 사이트가 어디의 데이터를 보여 주는지 알 수 없어요")
        return
    tip_sha, tip_at = tip["sha"], parse_time(tip["commit"]["committer"]["date"])
    want = hashlib.sha256(read_ref(ref, "data.json")).hexdigest()
    ok = live_sha == want
    if not ok and (now - tip_at < GRACE or (mode == "actions" and deploy_busy(net))):
        rep.skip(name, f"{ref} 가 {int((now - tip_at).total_seconds() // 60)}분 전에 바뀌어 배포를 기다려요")
        return
    rep.add(name, ok, f"같음 ({ref} {tip_sha[:7]})" if ok else
            f"다름: 사이트 {live_sha[:12]} · {ref} {tip_sha[:7]} 의 것 {want[:12]} — 배포나 Pages 빌드가 실패했거나 예전 파일이에요")


# ── 점검 전체 ───────────────────────────────────────────────
def run_all(net, now, selftest="none", gate=run_live_gate, expect=expected_px, read_ref=ref_file):
    rep, ctx = Report(), {"gate_md": "", "px": None, "files_ok": True}
    live_sha = None
    with tempfile.TemporaryDirectory(prefix="baepsae-live-") as d:
        bad = fetch_live(net, d, now)
        if bad:
            rep.add("사이트 데이터 파일 받기", False, " · ".join(bad))
            ctx["files_ok"] = False
        else:
            with open(os.path.join(d, "data.json"), "rb") as fh:
                live_sha = hashlib.sha256(fh.read()).hexdigest()       # 받은 그대로 (시험으로 망가뜨리기 전)
            if selftest == "broken":
                break_for_selftest(d)
                print("!! 시험: 받은 data.json 에서 필수 종목을 뺐어요 (경보가 열려야 해요)", flush=True)
            try:
                with open(os.path.join(d, "data.json"), encoding="utf-8") as fh:
                    ctx["px"] = V.strict_loads(fh.read(), "data.json").get("pxDate")
            except Exception as e:
                print(f"!! 사이트 data.json 을 읽지 못했어요: {e}", flush=True)
            ok, md, fails = gate(d)
            ctx["gate_md"] = md
            ctx["files_ok"] = ok
            names = [f.split(": ", 1)[0] for f in fails]
            rep.add("사이트 파일 발행 관문 (--live)", ok,
                    "PASS" if ok else f"실패 {len(names)}개: " + " · ".join(names[:8]) + (" …" if len(names) > 8 else ""))
    if ctx["px"]:
        check_stale(rep, ctx["px"], now, expect)
    else:
        rep.add("낡은 가격 (15:30 KST 이후)", False, "사이트의 pxDate 를 읽지 못했어요")
    for wf, label, noop in ((DATA_WF, DATA_NAME, False), (DEPLOY_WF, DEPLOY_NAME, True)):
        try:
            check_runs(rep, net, wf, label, skip_noop=noop)
        except Exception as e:
            rep.add(f"{label} 실행", False, f"확인하지 못했어요: {str(e)[:150]}")
    mode = None
    try:
        mode = check_pages(rep, net, now, read_ref)
    except Exception as e:
        rep.add("사이트 빌드", False, f"확인하지 못했어요: {str(e)[:150]}")
    try:
        check_live_data(rep, net, now, live_sha, mode, read_ref)
    except Exception as e:
        rep.add("사이트 data.json = 발행본", False, f"확인하지 못했어요: {str(e)[:150]}")
    return rep, ctx


# ── 경보 이슈 ───────────────────────────────────────────────
PASTE = "뱁새 데이터 경보 이슈 #{n} 이 떴어. 로그를 보고 원인을 찾아서 CLAUDE.md 규칙대로 고치고 PR 열어줘."


def users_line(ctx):
    if not ctx["files_ok"]:
        return ("사이트에 올라간 데이터 파일이 검사를 통과하지 못했어요. 사용자가 틀린 숫자나 '불러오지 못했어요'를 볼 수 있어요. "
                "바로 봐 주세요.")
    return (f"마지막으로 발행된 데이터(한국 종가 {ctx['px']} 기준)가 그 날짜와 함께 보여요. "
            "틀린 데이터가 새로 올라가지는 않았어요.")


def details(rep, ctx):
    out = ["<details><summary>점검 표 전체</summary>", "", rep.markdown(), "", "</details>"]
    if ctx["gate_md"]:
        out += ["", "<details><summary>발행 관문 (--live) 결과</summary>", "", ctx["gate_md"], "", "</details>"]
    return out


def problem_lines(rep):
    return [f"- **{n}**: {d}" for n, _, d in rep.problems]


def issue_body(rep, ctx, now, run_url, number="N", selftest="none"):
    lines = []
    if selftest != "none":
        lines += ["**[시험]** 일부러 망가뜨린 파일로 경보가 열리는지 시험한 거예요. 실제 사이트는 문제가 없어요. "
                  "다음 정상 점검이 이 이슈를 닫아요.", ""]
    lines += [f"{MENTION} 뱁새 감시가 문제를 찾았어요.", "",
              f"**지금 사용자에게 보이는 것:** {users_line(ctx)}", "",
              f"**언제부터:** {kst(now)} 점검부터 (이 이슈가 열린 때)", "",
              f"**점검 실행:** {run_url}", "",
              "### 문제", *problem_lines(rep), "",
              "### 할 일",
              "Claude Code 클라우드 세션에 이렇게 붙여 넣어 주세요:", "",
              "> " + PASTE.format(n=number), "",
              "무엇을 뜻하고 어떻게 되돌리는지: `docs/RUNBOOK.md`", "", *details(rep, ctx)]
    return "\n".join(lines)


def repeat_body(rep, ctx, now, run_url, opened_at, selftest="none"):
    lines = (["**[시험]** 일부러 망가뜨린 파일로 한 점검이에요.", ""] if selftest != "none" else [])
    lines += [f"다시 점검했는데 아직 문제가 있어요 ({kst(now)}, 처음 발견 {kst(opened_at)}).", "",
              f"**지금 사용자에게 보이는 것:** {users_line(ctx)}", "", f"**점검 실행:** {run_url}", "",
              *problem_lines(rep), "", *details(rep, ctx)]
    return "\n".join(lines)


def recovery_body(ctx, now, run_url):
    return (f"정상화됐어요. {kst(now)} 점검에서 문제가 없어요 (사이트 데이터: 한국 종가 {ctx['px']} 기준).\n\n"
            f"**점검 실행:** {run_url}")


def open_alerts(net):
    _, items = net.gh("GET", f"/repos/{REPO}/issues?labels={LABEL}&state=open&per_page=20")
    return sorted([i for i in (items or []) if "pull_request" not in i], key=lambda i: i["number"])


def ensure_label(net):
    st, _ = net.gh("POST", f"/repos/{REPO}/labels", {"name": LABEL, "color": "8A5A00",
                                                    "description": "뱁새 감시(watchdog)가 연 데이터 경보"}, ok=(201, 422))
    return st


def raise_alert(net, rep, ctx, now, run_url, selftest="none"):
    issues = open_alerts(net)
    if issues:
        i = issues[0]
        net.gh("POST", f"/repos/{REPO}/issues/{i['number']}/comments",
               {"body": repeat_body(rep, ctx, now, run_url, parse_time(i["created_at"]), selftest)})
        print(f"· 경보 이슈 #{i['number']} 에 댓글을 달았어요", flush=True)
        return i["number"]
    ensure_label(net)
    _, i = net.gh("POST", f"/repos/{REPO}/issues", {"title": ISSUE_TITLE, "labels": [LABEL],
                                                   "body": issue_body(rep, ctx, now, run_url, "N", selftest)})
    n = i["number"]
    net.gh("PATCH", f"/repos/{REPO}/issues/{n}", {"body": issue_body(rep, ctx, now, run_url, n, selftest)})
    print(f"!! 경보 이슈 #{n} 을 열었어요", flush=True)
    return n


def clear_alerts(net, ctx, now, run_url):
    closed = []
    for i in open_alerts(net):
        net.gh("POST", f"/repos/{REPO}/issues/{i['number']}/comments", {"body": recovery_body(ctx, now, run_url)})
        net.gh("PATCH", f"/repos/{REPO}/issues/{i['number']}", {"state": "closed", "state_reason": "completed"})
        print(f"· 경보 이슈 #{i['number']} 을 닫았어요 (정상화됐어요)", flush=True)
        closed.append(i["number"])
    return closed


def ping(net, url, fail=False):
    """healthchecks.io: 정상이면 그 주소, 문제면 /fail. 주소가 없으면 경고만 (감시가 멈추면 알려 줄 곳이 없다는 뜻이에요)."""
    url = (url or "").strip()                        # 붙여 넣을 때 따라온 줄바꿈 · 빈칸은 빼요
    if not url:
        print("::warning title=healthchecks.io 없음::HC_PING_URL 비밀 값이 없어요. 감시 자체가 멈추면 알려 줄 곳이 없어요 (docs/RUNBOOK.md).",
              flush=True)
        return False
    try:
        r = net.get(url.rstrip("/") + ("/fail" if fail else ""), timeout=15)
        print(f"· healthchecks.io {'실패' if fail else '정상'} 알림: HTTP {r.status_code}", flush=True)
        return r.status_code == 200
    except RuntimeError as e:
        print(f"::warning title=healthchecks.io 알림 실패::{e}", flush=True)
        return False


# ── workflow_run 으로 불렸을 때: 지금 점검할지 ────────────────
def decide(net, event, name, run_id):
    """(점검할까, 이유). 같은 결과를 두 번 보지 않게: Actions 배포 중이면 데이터 실행 뒤가 아니라 배포 뒤에 봐요."""
    if event != "workflow_run":
        return True, f"{event} 실행"
    try:
        st, pages = net.gh("GET", f"/repos/{REPO}/pages", ok=(200, 404))
        mode = (pages or {}).get("build_type") if st == 200 else None
        _, js = net.gh("GET", f"/repos/{REPO}/actions/runs/{run_id}/jobs?per_page=50")
    except Exception as e:
        return True, f"확인하지 못해서 점검해요 ({str(e)[:100]})"
    steps = {(j.get("name"), s.get("name")): s.get("conclusion") for j in (js or {}).get("jobs", []) for s in j.get("steps") or []}
    jobs = {j.get("name"): j.get("conclusion") for j in (js or {}).get("jobs", [])}
    if name == DATA_NAME and mode == "workflow" and steps.get(("update", PUSH_STEP)) == "success":
        return False, "데이터가 올라갔어요 → 배포(Deploy)가 끝난 뒤에 점검해요"
    if (name == DEPLOY_NAME and jobs.get("decide") == "success"
            and jobs.get("build") in (None, "skipped") and jobs.get("deploy") in (None, "skipped")):
        return False, "배포가 아무것도 올리지 않았어요 (건너뜀) → 점검할 새 것이 없어요"
    return True, f"{name} 실행 {run_id} 뒤 점검 (Pages {mode})"


def write_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main(argv=None, net=None, now=None, **kw):
    ap = argparse.ArgumentParser(description="뱁새 감시")
    ap.add_argument("--dry", action="store_true", help="점검만 (이슈·알림 없이)")
    ap.add_argument("--selftest", choices=("none", "broken"), default=os.environ.get("WATCHDOG_SELFTEST") or "none")
    ap.add_argument("--decide", action="store_true", help="workflow_run 계기: 지금 점검할지만 정해요")
    a = ap.parse_args(argv)
    net = net or Net(os.environ.get("GITHUB_TOKEN"))
    if a.decide:
        go, why = decide(net, os.environ.get("GITHUB_EVENT_NAME", ""), os.environ.get("TRIGGER_NAME", ""),
                         os.environ.get("TRIGGER_RUN_ID", ""))
        print(("· 점검해요: " if go else "· 지금은 점검하지 않아요: ") + why, flush=True)
        write_output("go", "true" if go else "false")
        return 0
    now = now or dt.datetime.now(dt.timezone.utc)
    run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
               if os.environ.get("GITHUB_RUN_ID") else "(로컬 실행)")
    print(f"뱁새 감시 · {kst(now)} · 사이트 {SITE} · 시험 {a.selftest}{' · 점검만' if a.dry else ''}", flush=True)
    rep, ctx = run_all(net, now, a.selftest, **kw)
    print()
    for n, s, d in rep.rows:
        print(f"  {s:4}  {n}: {d}")
    bad = rep.problems
    print(f"\n결과: {'문제 ' + str(len(bad)) + '개' if bad else '정상'} · 점검 {len(rep.rows)}개", flush=True)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(f"### 뱁새 감시 — {'문제 ' + str(len(bad)) + '개' if bad else '정상'}\n\n{rep.markdown()}\n\n")
    for n, _, d in bad:
        print(f"::error title=뱁새 감시::{V._gh_escape(f'{n}: {d}')}", flush=True)
    if a.dry:
        return 1 if bad else 0
    hc = os.environ.get("HC_PING_URL", "").strip()
    if bad:
        try:
            raise_alert(net, rep, ctx, now, run_url, a.selftest)
        finally:                            # 이슈를 못 열어도(GitHub 장애) healthchecks.io 는 알아요
            ping(net, hc, fail=True)        # 시험도 보내요: 알림이 Jack 에게 닿는지까지 시험해요 (Jack, 2026-11-05)
        if a.selftest != "none":
            finish_selftest(net, now, run_url, hc, kw)
        return 1
    clear_alerts(net, ctx, now, run_url)
    ping(net, hc)
    return 0


def finish_selftest(net, now, run_url, hc, kw):
    """시험 경보 뒤: 진짜 사이트를 다시 점검해요. 문제가 없으면 [시험] 이슈를 닫고 정상 알림을 보내요 — Jack 은 '문제' 메일
    뒤에 바로 '정상' 메일을 받아요 (Jack, 2026-11-05). 진짜 문제가 있으면 진짜 경보로 남겨요 (healthchecks.io 는 이미 '문제')."""
    print("\n· 시험 끝: 망가뜨리지 않은 사이트 파일로 다시 점검해요", flush=True)
    rep, ctx = run_all(net, now, "none", **kw)
    for n, s, d in rep.rows:
        print(f"  {s:4}  {n}: {d}")
    bad = rep.problems
    print(f"\n다시 점검: {'문제 ' + str(len(bad)) + '개' if bad else '정상'} · 점검 {len(rep.rows)}개", flush=True)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(f"### 시험 뒤 다시 점검 (망가뜨리지 않은 파일) — {'문제 ' + str(len(bad)) + '개' if bad else '정상'}\n\n"
                    f"{rep.markdown()}\n\n")
    if bad:
        for n, _, d in bad:
            print(f"::error title=뱁새 감시::{V._gh_escape(f'{n}: {d}')}", flush=True)
        num = raise_alert(net, rep, ctx, now, run_url, "none")
        # 방금 연 [시험] 이슈 안에 진짜 문제가 남지 않게: 첫 줄이 [시험]이면 진짜 경보 본문으로 바꿔요 (그 전부터 열린 진짜 이슈는 그대로)
        for i in open_alerts(net):
            if i.get("number") == num and str(i.get("body") or "").startswith("**[시험]**"):
                net.gh("PATCH", f"/repos/{REPO}/issues/{num}", {"body": issue_body(rep, ctx, now, run_url, num, "none")})
                print(f"!! 경보 이슈 #{num}: 시험이 아니라 진짜 문제예요 — 본문을 진짜 경보로 바꿨어요", flush=True)
        return
    clear_alerts(net, ctx, now, run_url)
    ping(net, hc)


if __name__ == "__main__":
    sys.exit(main())
