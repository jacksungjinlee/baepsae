# -*- coding: utf-8 -*-
"""배포 전 화면 검사 — tools/deploy_check.py (Jack J6, 2026-11-12, deploy.yml)
──────────────────────────────────────────────────────────────
코드가 바뀌는 배포(main 에 머지 · 손으로 누른 배포)는 올리기 전에, 매일 실행의 '발행 전 화면 검사'와 같은 세 검사를
올릴 폴더(_site)의 데이터 그대로 새 코드로 돌려요. Jack 의 규칙: 새 코드가 실패한 검사를 지금 사이트의 코드가 같은 데이터로
통과하면 막아요 (사이트는 그대로). 지금 사이트의 코드도 같은 검사에서 실패하면 올려요 (데이터 문제를 고치는 코드도 올라갈 수
있게) — 그리고 Jack 에게 알려요 (경보 이슈 data-alert + deploy-check 표시 · 경고).
'검사'는 검사 줄 하나예요 (Jack J6 의 'a check' — 세 스크립트의 결과 표 한 줄, 모두 162줄쯤): 새 코드가 실패한 줄이 하나라도 지금
코드에서 통과하면 막아요.

  python3 tools/deploy_check.py need --site _site    # (토큰 있음) 이 배포가 검사해야 하는지 → $RUNNER_TEMP/deploy-need.json · run=yes|no
  python3 tools/deploy_check.py skip                 # 검사하지 않는 배포면 exit 0 (도구를 깔지 않아요). 그 밖에는 exit 1 (깔아요)
  python3 tools/deploy_check.py check --site _site   # (토큰 없음 · 브라우저) 세 검사 → 결정 · 영수증 (막으면 exit 1)
  python3 tools/deploy_check.py report --site _site  # (토큰 있음) 영수증 확인 · 경보 이슈 열기 · 댓글 / 표시 풀기

검사할지 (need):
- push(머지) · workflow_dispatch(손으로) → 늘 검사해요.
- workflow_run(데이터 실행 뒤) → 둘 다 맞을 때만 건너뛰어요. 하나라도 확인하지 못하면 검사해요.
  · 코드: 그 데이터 실행의 커밋(head_sha)에서 지금 올릴 커밋까지 커밋마다 바뀐 파일이 데이터 네 파일뿐 (GitHub compare API ·
    이름 바꾸기는 데이터 파일로 들어와도 코드로 쳐요). 매일 실행은 그 사이의 main 코드로 검사했어요.
  · 데이터: 올릴 폴더의 네 파일 = 이 배포가 받은 data 브랜치 커밋의 네 파일이고, 그 커밋은 baepsae-bot 이 바로 그 데이터 실행
    동안 만든 것 (그 실행은 화면 검사 영수증이 맞는 파일만 data 브랜치에 올려요).

결정 (스크립트마다, 그 안에서는 검사 줄마다):
  새 코드 통과                                          → 됐어요
  지금 코드를 알 수 없음 (빌드 표시를 못 읽음 · 커밋을 받지 못함 · 다시 빌드한 페이지가 사이트의 것과 다름) → 막아요
  지금 코드 통과                                        → 막아요
  지금 코드가 결과 줄 전에 멈춤                          → 막아요 (알 수 없음)
  새 코드가 결과 줄 전에 멈춤 · 지금 코드는 결과 줄까지 감  → 막아요
  어느 쪽이든 실패한 줄을 읽지 못함                      → 막아요
  새 코드가 실패한 줄 가운데 지금 코드가 통과한 줄이 있음   → 막아요 (새로 실패한 줄을 먼저 적어요)
  새 코드가 실패한 줄을 지금 코드도 모두 실패              → 올리고 알려요
  같은 코드(지금 사이트의 커밋과 데이터 네 파일 말고는 똑같음): 막을 검사는 새 코드로 한 번 더 돌려요. 통과하면 됐어요, 또 실패하면
  올리고 알려요 — 같은 코드끼리는 흔들림이나 시계 탓이라, 그걸로 아침 데이터를 막지 않아요.
'멈춤'에서 smoke_launch 가 2.0 이 쓰는 항목이 빠진 데이터라서 일부러 멈추는 것은 실패 줄 하나로 쳐요 (그 데이터를 고치는 코드가
올라갈 수 있게).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import watchdog as W  # noqa: E402  (사이트 주소 · 빌드 표시 · 경보 이슈를 감시와 같은 정의로)

# 매일 실행 update-data.yml '발행 전 화면 검사'와 같은 셋 · 같은 순서 (tests/test_deploy_check.py 가 맞춰 봐요)
CHECKS = ("real_data_check", "smoke_launch", "smoke_app")
DATA_FILES = ("data.json", "corp.json", "disc.json", "macro.json")
# 검사는 저장소 맨 위의 페이지로 시험 사이트를 만들어요 → 그 페이지가 올릴 폴더의 것과 한 글자도 같아야 해요
SAME_PAGES = ("index.html", "app.html", "baepsae.html", "sw.js", "manifest.webmanifest")
LIVE_BUILD = ("build.sh", "build-app.sh", "build-styleguide.sh")
RESULT_RE = re.compile(r"(\d+) / (\d+) 통과")
ROW_RE = re.compile(r"  (PASS|FAIL)  (.*)")
# smoke_launch 가 2.0 이 쓰는 항목이 빠진 데이터에서 브라우저를 열기 전에 일부러 멈출 때의 줄 (tests/smoke_launch.py use_data)
STOP_RE = re.compile(r"!! --data .*: 2\.0 이 쓰는 항목이 빠진 데이터예요 \((.*)\)")
TIMING_RE = re.compile(r"\s*\(\s*\d+(?:\.\d+)?\s*(?:ms|s|초|분)\s*\)$")
SHA_RE = re.compile(r"[0-9a-f]{40}")
PASS, FAIL, CRASH = "pass", "fail", "crash"
MAX_COMMITS = 20                    # 데이터 실행 뒤 커밋이 이보다 많으면 하나하나 보지 않고 검사해요
BOT = "baepsae-bot"                 # tools/push_data_branch.sh 가 data 브랜치 커밋에 쓰는 이름
DATA_REF = "refs/remotes/origin/data"
LABEL = W.DEPLOY_CHECK_LABEL        # 이 표시가 붙은 경보는 감시가 닫지 않아요 (watchdog.clear_alerts)
MARK = "**[배포 화면 검사]**"
OK_MARK = "**[배포 화면 검사 · 통과]**"
NEED_FILE, DECISION_FILE, RECEIPT_FILE = "deploy-need.json", "deploy-check.json", "deploy-check-pass.sha256"
LIVE_DIR, LIVE_REPO = "deploy-live", "deploy-live-repo"


class Unknown(Exception):
    """지금 사이트의 코드를 알 수 없어요 (→ 막아요)."""


def say(msg):
    print(msg, flush=True)


def tmp_dir():
    d = os.environ.get("RUNNER_TEMP")
    if not d:
        raise SystemExit("!! RUNNER_TEMP 가 없어요 (GitHub Actions 밖에서는 RUNNER_TEMP=폴더 를 주세요)")
    return d


def summary(text):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def esc(text):
    return W.V._gh_escape(text)


def kst_now():
    return W.kst(dt.datetime.now(dt.timezone.utc))


def git(*args, cwd=None, timeout=300):
    return subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, timeout=timeout)


def head_sha(cwd=None):
    r = git("rev-parse", "HEAD", cwd=cwd, timeout=60)
    sha = r.stdout.strip()
    if r.returncode != 0 or not SHA_RE.fullmatch(sha):
        raise SystemExit(f"!! 올릴 코드의 커밋을 읽지 못했어요: {r.stderr.strip()[:200]}")
    return sha


def read_px(site):
    try:
        with open(os.path.join(site, "data.json"), encoding="utf-8") as f:
            return json.load(f).get("pxDate")
    except Exception:                   # 날짜는 설명에만 써요 (데이터 검사는 관문과 세 검사가 해요)
        return None


def git_blob(path):
    """git 이 그 파일에 매기는 이름 (git hash-object 와 같아요)."""
    with open(path, "rb") as f:
        body = f.read()
    return hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()


# ── 1. 이 배포가 검사해야 하는지 ──────────────────────────────
def code_changes(net, base, head):
    """base(데이터 실행의 커밋) → head(올릴 커밋) 사이 커밋들이 바꾼 파일 가운데 데이터 네 파일이 아닌 것. 확인하지 못하면 예외.
    이름 바꾸기는 (데이터 파일로 들어와도) 코드로 쳐요."""
    _, cmp = net.gh("GET", f"/repos/{W.REPO}/compare/{base}...{head}")
    status, commits = (cmp or {}).get("status"), (cmp or {}).get("commits") or []
    if status not in ("ahead", "identical"):
        raise RuntimeError(f"{base[:7]} 에서 {head[:7]} 로 곧게 이어지지 않아요 ({status})")
    total = (cmp or {}).get("total_commits", len(commits))
    if total != len(commits) or total > MAX_COMMITS:
        raise RuntimeError(f"그 사이 커밋이 {total}개예요 (하나하나 보지 않아요)")
    other = set()
    for c in commits:
        _, one = net.gh("GET", f"/repos/{W.REPO}/commits/{c['sha']}")
        files = (one or {}).get("files") or []
        if not files or len(files) >= 300:          # 빈 목록 · 잘린 목록(300개)은 무엇이 바뀌었는지 몰라요
            raise RuntimeError(f"커밋 {c['sha'][:7]} 의 바뀐 파일 목록을 다 읽지 못했어요 ({len(files)}개)")
        for f in files:
            name, prev = f.get("filename"), f.get("previous_filename")
            if name not in DATA_FILES:
                other.add(str(name))
            if prev is not None or f.get("status") == "renamed":
                other.add(f"{prev} → {name}")
    return sorted(other), len(commits)


def data_tip_info(root=None, ref=DATA_REF):
    """이 배포가 받은 data 브랜치 커밋: {sha, date, committer, blobs{파일: blob}}. 읽지 못하면 예외."""
    r = git("log", "-1", "--format=%H%x00%cI%x00%cn", ref, cwd=root, timeout=60)
    parts = r.stdout.strip().split("\0")
    if r.returncode != 0 or len(parts) != 3 or not SHA_RE.fullmatch(parts[0]):
        raise RuntimeError(f"{ref} 를 읽지 못했어요")
    ls = git("ls-tree", "-z", parts[0], "--", *DATA_FILES, cwd=root, timeout=60)
    blobs = {}
    for item in ls.stdout.split("\0"):
        if item:
            meta, _, path = item.partition("\t")
            blobs[path] = meta.split()[2]
    return {"sha": parts[0], "date": parts[1], "committer": parts[2], "blobs": blobs}


def data_bound(info, site, started, updated):
    """(맞나, 이유): 올릴 폴더의 네 파일이 그 데이터 실행이 검사하고 올린 파일인지."""
    try:
        t, a, b = (dt.datetime.fromisoformat(str(x).replace("Z", "+00:00")) for x in (info["date"], started, updated))
    except (TypeError, ValueError, KeyError):
        return False, "데이터 실행의 시간이나 data 브랜치 커밋의 시간을 읽지 못했어요"
    slack = dt.timedelta(seconds=90)
    if info.get("committer") != BOT:
        return False, f"data 브랜치 커밋 {info['sha'][:7]} 을 {BOT} 가 아닌 {info.get('committer')!r} 가 만들었어요"
    if not (a - slack <= t <= b + slack):
        return False, f"data 브랜치 커밋 {info['sha'][:7]} 이 그 데이터 실행({started} ~ {updated}) 동안 만든 것이 아니에요 ({info['date']})"
    for f in DATA_FILES:
        p = os.path.join(site, f)
        if not os.path.isfile(p) or info["blobs"].get(f) != git_blob(p):
            return False, f"올릴 폴더의 {f} 가 data 브랜치 커밋 {info['sha'][:7]} 의 것과 달라요"
    return True, f"올릴 데이터 = 그 실행이 올린 data 브랜치 커밋 {info['sha'][:7]}"


def need_checks(event, run_head, head, net, bound=None):
    """(검사할까, 이유). 모르는 것은 모두 '검사해요' 쪽이에요. bound: 데이터가 그 실행의 것인지 → (맞나, 이유)."""
    if event == "push":
        return True, "main 에 코드가 들어왔어요 (머지)"
    if event == "workflow_dispatch":
        return True, "손으로 누른 배포예요"
    if event != "workflow_run":
        return True, f"모르는 계기({event or '없음'})라 검사해요"
    if not SHA_RE.fullmatch(run_head or ""):
        return True, "데이터 실행이 검사한 커밋을 몰라서 검사해요"
    n = 0
    if run_head != head:
        try:
            other, n = code_changes(net, run_head, head)
        except Exception as e:                      # noqa: BLE001 — 확인하지 못하면 검사해요 (건너뛰지 않아요)
            return True, f"데이터 실행({run_head[:7]}) 뒤로 코드가 바뀌었는지 확인하지 못해서 검사해요 ({str(e)[:160]})"
        if other:
            return True, (f"데이터 실행({run_head[:7]}) 뒤로 코드가 바뀌었어요 ({', '.join(other[:5])}"
                          f"{' …' if len(other) > 5 else ''}) → 검사해요")
    try:
        ok, why = bound() if bound else (False, "올릴 데이터를 맞춰 보지 않았어요")
    except Exception as e:                          # noqa: BLE001
        ok, why = False, f"올릴 데이터를 맞춰 보지 못했어요 ({str(e)[:160]})"
    if not ok:
        return True, f"{why} → 검사해요"
    return False, (f"데이터 실행({run_head[:7]})이 이 코드로 같은 파일을 검사하고 올렸어요 "
                   f"(그 뒤 커밋 {n}개는 데이터 네 파일만 바꿨어요 · 올릴 커밋 {head[:7]} · {why})")


def read_need(tmp):
    """(검사할까, 이유). 파일이 없거나 읽지 못하면 검사해요."""
    try:
        with open(os.path.join(tmp, NEED_FILE), encoding="utf-8") as f:
            j = json.load(f)
        if j.get("run") is False:
            return False, str(j.get("why") or "")
        if j.get("run") is True:
            return True, str(j.get("why") or "")
        return True, f"{NEED_FILE} 의 값을 읽지 못해서 검사해요 ({j.get('run')!r})"
    except (OSError, ValueError, AttributeError) as e:
        return True, f"{NEED_FILE} 를 읽지 못해서 검사해요 ({type(e).__name__})"


def cmd_need(site, net=None):
    tmp = tmp_dir()
    head = head_sha()
    net = net or W.Net(os.environ.get("GITHUB_TOKEN"))
    started, updated = os.environ.get("RUN_STARTED", ""), os.environ.get("RUN_UPDATED", "")
    run, why = need_checks(os.environ.get("EVENT", ""), os.environ.get("RUN_HEAD", ""), head, net,
                           bound=lambda: data_bound(data_tip_info(), os.path.abspath(site), started, updated))
    with open(os.path.join(tmp, NEED_FILE), "w", encoding="utf-8") as f:
        json.dump({"run": run, "why": why, "head": head}, f, ensure_ascii=False)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:                                         # 브라우저 보관본 단계가 읽어요 (no → 꺼내지 않고 있는지만 봐요)
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"run={'yes' if run else 'no'}\n")
    say(("· 배포 전 화면 검사를 해요: " if run else "· 배포 전 화면 검사를 하지 않아요: ") + why)
    return 0


def cmd_skip():
    run, why = read_need(tmp_dir())
    if run:
        say(f"· 검사하는 배포예요 → 준비해요 ({why})")
        return 1
    say(f"· 검사하지 않는 배포예요 → 준비하지 않아요 ({why})")
    return 0


# ── 2. 검사 돌리기와 결과 읽기 ─────────────────────────────────
def label_of(text):
    """결과 표 한 줄의 이름 (설명 빼고, 띄어쓰기 · 끝의 시간 표시는 맞춰서).
    smoke 표: 이름을 폭에 맞춰 늘인 뒤 두 칸 띄고 설명 · real_data_check: '이름: 설명'."""
    m = re.search(r" {2,}", text)
    name = text[:m.start()] if m else text.split(": ", 1)[0]
    return TIMING_RE.sub("", " ".join(name.split()))


def table(lines, n, total):
    """결과 줄 바로 앞의 결과 표 → (실패한 줄 이름들, 실패한 줄 그대로). 표의 줄 수가 total 이 아니거나 FAIL 이 total-n 이 아니면
    (None, …) — 읽지 못함. 표와 결과 줄 사이의 알림(!! …)은 건너뛰고, 표 위의 머리줄 · 표 안의 이어진 줄은 세지 않아요."""
    i = len(lines) - 1
    while i >= 0 and not ROW_RE.fullmatch(lines[i]):
        i -= 1
    rows = []
    while i >= 0 and lines[i].strip():
        if ROW_RE.fullmatch(lines[i]):
            rows.append(lines[i])
        i -= 1
    fails = [ROW_RE.fullmatch(r).group(2) for r in reversed(rows) if ROW_RE.fullmatch(r).group(1) == "FAIL"]
    raw = [f.strip()[:300] for f in fails]
    if len(rows) != total or len(fails) != total - n:
        return None, raw
    out = []
    for f in fails:
        lab = label_of(f)
        if lab not in out:
            out.append(lab)
    return out, raw


def parse_run(rc, lines):
    """한 검사 실행 → {outcome PASS|FAIL|CRASH, detail, fails (실패한 줄 이름 · 읽지 못하면 None), raw (실패한 줄 그대로)}."""
    idx = None
    for i, ln in enumerate(lines):
        if RESULT_RE.fullmatch(ln.rstrip("\r\n")):
            idx = i
    if idx is None:
        stop = next((m for m in (STOP_RE.fullmatch(ln.split(" → ")[0].rstrip()) for ln in lines) if m), None)
        if stop and rc not in (0, None):            # 2.0 이 쓰는 항목이 빠진 데이터: 브라우저를 열기 전에 일부러 멈춤 = 실패 줄 하나
            lab = f"[데이터] 2.0 이 쓰는 항목이 빠진 데이터 ({stop.group(1)})"
            return {"outcome": FAIL, "detail": f"검사 전에 멈춤 — 2.0 이 쓰는 항목이 빠졌어요 ({stop.group(1)})",
                    "fails": [lab], "raw": [lab]}
        return {"outcome": CRASH, "detail": f"끝까지 돌지 못했어요 (결과 줄 없음 · 종료 코드 {rc})", "fails": None, "raw": []}
    m = RESULT_RE.fullmatch(lines[idx].rstrip("\r\n"))
    n, total = int(m.group(1)), int(m.group(2))
    count = f"{n} / {total} 통과"
    if rc == 0 and n == total and total > 0:
        return {"outcome": PASS, "detail": count, "fails": [], "raw": []}
    if not (rc not in (0, None) and n < total):
        return {"outcome": CRASH, "detail": f"{count} 인데 종료 코드가 {rc} 라 앞뒤가 맞지 않아요", "fails": None, "raw": []}
    fails, raw = table(lines[:idx], n, total)
    return {"outcome": FAIL, "detail": count, "fails": fails, "raw": raw}


def outcome(rc, lines):
    """(PASS|FAIL|CRASH, 설명)."""
    r = parse_run(rc, lines)
    return r["outcome"], r["detail"]


def run_check(name, root, data, live=False):
    """root 의 tests/<name>.py --data <data> 를 돌려요. 출력은 그대로 이 실행의 로그에. → 결과 dict.
    두 실행 모두 검사 스크립트의 GitHub 알림(::error · ::warning)은 끄고, 결정에 맞는 알림은 이 도구가 남겨요 (초록 실행에 빨간 줄이
    남지 않게)."""
    label = "지금 사이트 코드" if live else "새 코드"
    cmd = [sys.executable, os.path.join("tests", f"{name}.py"), "--data", data]
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    env.pop("GITHUB_ACTIONS", None)
    say(f"::group::{name} · {label}")
    lines, rc = [], None
    try:
        p = subprocess.Popen(cmd, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        for ln in p.stdout:
            print(ln, end="", flush=True)
            lines.append(ln.rstrip("\n"))
        rc = p.wait()
    except OSError as e:
        lines.append(f"!! 시작하지 못했어요: {e}")
        say(lines[-1])
    say("::endgroup::")
    r = parse_run(rc, lines)
    r["unseen"] = [ln.strip() for ln in lines if ln.startswith(("!! 확인 못 함", "!! 알림"))][:10]
    out = {PASS: "통과", FAIL: "실패", CRASH: "끝까지 돌지 못함"}[r["outcome"]]
    say(f"· {name} ({label}): {out} · {r['detail']}" + ("" if r["fails"] is not None else " · 실패한 줄을 읽지 못했어요"))
    return r


def file_tree(dir_):
    """폴더의 모든 파일 '<sha256>  <경로>' 줄 (경로 순). 바로가기는 가리키는 곳으로 적어요."""
    out = []
    for base, dirs, files in os.walk(dir_):
        dirs.sort()
        for name in sorted(files) + sorted(d for d in dirs if os.path.islink(os.path.join(base, d))):
            p = os.path.join(base, name)
            rel = os.path.relpath(p, dir_)
            if os.path.islink(p):
                digest = "link:" + os.readlink(p)
            else:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                digest = h.hexdigest()
            out.append(f"{digest}  {rel}")
    return "\n".join(sorted(out, key=lambda ln: ln.split("  ", 1)[1])) + "\n"


def same_pages(site):
    """검사가 쓰는 저장소 맨 위의 페이지 = 올릴 폴더의 페이지 (다르면 검사한 것과 올리는 것이 달라요 → 멈춰요)."""
    diff = []
    for p in SAME_PAGES:
        a, b = os.path.join(ROOT, p), os.path.join(site, p)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            diff.append(f"{p} 없음")
            continue
        with open(a, "rb") as fa, open(b, "rb") as fb:
            if fa.read() != fb.read():
                diff.append(p)
    if diff:
        raise SystemExit(f"!! 검사할 페이지가 올릴 폴더의 페이지와 달라요: {', '.join(diff)} → 올리지 않아요")


# ── 3. 지금 사이트의 코드 ─────────────────────────────────────
def find_live(net, now=None):
    """(커밋, {페이지: 받은 바이트}). 사이트가 지금 보여 주는 페이지의 빌드 표시 (감시와 같은 페이지 · 같은 표시).
    모든 페이지가 200 이고 같은 40자리 커밋이어야 해요. 아니면 Unknown."""
    now = int(now or time.time())
    tags, served = {}, {}
    for p in W.PAGES:
        try:
            r = net.get(f"{W.SITE}{p}?t={now}")
        except RuntimeError as e:
            raise Unknown(f"사이트의 {p} 를 받지 못했어요 ({e})")
        if r.status_code != 200:
            raise Unknown(f"사이트의 {p}: HTTP {r.status_code}")
        m = W.BUILD_RE.search(r.content[:4000].decode("utf-8", "replace"))
        if not m or not SHA_RE.fullmatch(m.group(1)):
            raise Unknown(f"사이트의 {p} 에 빌드 표시(baepsae-build)가 없어요")
        tags[p], served[p] = m.group(1), r.content
    if len(set(tags.values())) != 1:
        raise Unknown("사이트의 페이지마다 빌드 표시가 달라요: " + " · ".join(f"{p} {t[:7]}" for p, t in tags.items()))
    return next(iter(tags.values())), served


def has_commit(sha, repo=None):
    return git("cat-file", "-e", f"{sha}^{{commit}}", cwd=repo, timeout=60).returncode == 0


def _step(what, cmd, cwd, env=None, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unknown(f"{what}: {type(e).__name__}")
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
        raise Unknown(f"{what} 실패 (종료 코드 {r.returncode}): " + " / ".join(t[:160] for t in tail))
    return r


def get_commit(sha, tmp):
    """그 커밋을 가진 저장소 폴더. 저장소(ROOT)에 이미 있으면 ROOT (읽기만 해요). 없으면 RUNNER_TEMP 의 따로 된 빈 저장소에 그 커밋
    하나만 받아요 — ROOT 의 .git 에는 아무것도 받지 않아요 (얕게 받으면 있는 기록을 그 커밋에서 잘라 버려요)."""
    if has_commit(sha):
        say(f"· 커밋 {sha[:7]} 은 저장소에 이미 있어요 (받지 않아요)")
        return ROOT
    r = git("remote", "get-url", "origin", timeout=60)
    url = r.stdout.strip()
    if r.returncode != 0 or not url:
        raise Unknown("저장소의 origin 주소를 읽지 못했어요")
    repo = os.path.join(tmp, LIVE_REPO)
    shutil.rmtree(repo, ignore_errors=True)
    _step("받을 빈 저장소 만들기 (git init)", ["git", "init", "-q", repo], tmp, timeout=60)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    _step("지금 사이트 커밋 받기 (git fetch, 따로 된 저장소에)", ["git", "-C", repo, "fetch", "-q", "--depth=1", "--no-tags", url, sha],
          tmp, env=env, timeout=300)
    if not has_commit(sha, repo):
        raise Unknown(f"커밋 {sha[:7]} 을 받지 못했어요")
    return repo


def tree_map(repo, sha):
    """{경로: '모드 종류 blob'} — 그 커밋의 모든 파일."""
    r = git("ls-tree", "-r", "-z", "--full-tree", sha, cwd=repo, timeout=120)
    if r.returncode != 0:
        raise Unknown(f"커밋 {sha[:7]} 의 파일 목록을 읽지 못했어요")
    out = {}
    for item in r.stdout.split("\0"):
        if item:
            meta, _, path = item.partition("\t")
            out[path] = meta
    return out


def same_code(repo, sha, head="HEAD"):
    """지금 사이트의 커밋과 올릴 커밋이 데이터 네 파일 말고는 한 글자도 같은지 (같은 코드)."""
    a, b = tree_map(ROOT, head), tree_map(repo, sha)
    for f in DATA_FILES:
        a.pop(f, None)
        b.pop(f, None)
    return a == b


def prepare_live(sha, served, tmp):
    """지금 사이트의 커밋을 따로 된 폴더에 꺼내 빌드해요 (같은 빌드 표시로 · npm 설치 스크립트 없이). 다시 빌드한 페이지가 사이트에서
    받은 것과 한 글자도 같아야 그 폴더가 '지금 사이트의 코드'예요. → {dir, same_code}. 무엇이든 안 되면 Unknown."""
    d = os.path.join(tmp, LIVE_DIR)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    say(f"· 지금 사이트의 코드 {sha[:7]} 를 {d} 에 꺼내 빌드해요")
    repo = get_commit(sha, tmp)
    tar = os.path.join(tmp, LIVE_DIR + ".tar")
    _step("지금 사이트 코드 꺼내기 (git archive)", ["git", "-C", repo, "archive", "--format=tar", "-o", tar, sha], tmp, timeout=300)
    _step("지금 사이트 코드 풀기 (tar)", ["tar", "-x", "-f", tar, "-C", d], tmp, timeout=300)
    if os.path.exists(tar):
        os.unlink(tar)
    _step("지금 사이트 코드의 라이브러리 (npm ci, 설치 스크립트 없이)", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], d,
          timeout=600)
    env = {**os.environ, "BAEPSAE_BUILD": sha}
    for s in LIVE_BUILD:
        _step(f"지금 사이트 코드 빌드 ({s})", ["bash", s], d, env=env, timeout=600)
    for p, body in served.items():
        f, got = os.path.join(d, p), b""
        if os.path.isfile(f):
            with open(f, "rb") as fh:
                got = fh.read()
        if got != body:                             # 바이트 그대로 (길이만이 아니라)
            raise Unknown(f"다시 빌드한 {p} 가 사이트에서 받은 것과 달라요 (커밋 {sha[:7]})")
    say(f"· 다시 빌드한 {' · '.join(served)} 가 사이트의 것과 한 글자도 같아요 → 지금 사이트의 코드예요 ({sha[:7]})")
    same = same_code(repo, sha)
    if same:
        say(f"· 지금 사이트의 코드 {sha[:7]} 와 올릴 코드는 데이터 네 파일 말고는 같아요 (같은 코드)")
    return {"dir": d, "same_code": same}


# ── 4. 결정 ─────────────────────────────────────────────────
def _row(t, verdict, text, new_only=(), both=()):
    return {"check": t, "verdict": verdict, "text": text, "new_only": list(new_only), "both": list(both)}


def decide(new, live, unknown=None, same=False, again=None):
    """new: {검사: 결과} (셋 모두). live: {검사: 결과} (새 코드가 실패한 검사만) 또는 None (지금 코드를 알 수 없음).
    결과 = parse_run 의 dict. same: 지금 사이트와 같은 코드. again: {검사: 같은 코드에서 새 코드로 한 번 더 돌린 결과}.
    → ("pass"|"alert"|"block", [줄 dict: check · verdict ok|alert|block · text · new_only · both])"""
    rows = []
    for t in CHECKS:
        n = (new or {}).get(t) or {"outcome": CRASH, "detail": "돌리지 않았어요", "fails": None}
        if n["outcome"] == PASS:
            rows.append(_row(t, "ok", f"새 코드 {n['detail']}"))
            continue
        lv = None if live is None else live.get(t)
        nf, lf = n.get("fails"), (lv or {}).get("fails")
        if lv is None:
            row = _row(t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드: 알 수 없어요 ({unknown or '돌리지 않았어요'})", nf or ())
        elif lv["outcome"] == PASS:
            row = _row(t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드 {lv['detail']} → 새 코드만 실패해요", nf or ())
        elif lv["outcome"] == CRASH:
            row = _row(t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드의 검사가 결과 줄 전에 멈췄어요 ({lv['detail']}) → 알 수 없어요",
                       nf or ())
        elif n["outcome"] == CRASH:
            row = _row(t, "block", f"새 코드의 검사가 결과 줄 전에 멈췄어요 ({n['detail']}) · 지금 사이트 코드는 끝까지 돌았어요 "
                                   f"({lv['detail']})")
        elif nf is None or lf is None:
            row = _row(t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드 {lv['detail']} · "
                                   f"{'새 코드' if nf is None else '지금 사이트 코드'}의 실패한 줄을 읽지 못해서 맞춰 보지 못했어요", nf or ())
        else:
            only = [x for x in nf if x not in lf]
            common = [x for x in nf if x in lf]
            if only:
                row = _row(t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드 {lv['detail']} → 새 코드만 실패한 줄 {len(only)}개",
                           only, common)
            else:
                row = _row(t, "alert", f"새 코드 {n['detail']} · 지금 사이트 코드도 {lv['detail']} (새 코드가 실패한 줄 {len(nf)}개를 "
                                       "지금 코드도 모두 실패)", (), common)
        if row["verdict"] == "block" and same and live is not None and again is not None and t in again:
            a = again[t]
            if a["outcome"] == PASS:
                row = _row(t, "ok", f"같은 코드 · 처음엔 {n['detail']}, 한 번 더 돌리니 {a['detail']} (흔들림으로 봐요)")
            else:
                row = _row(t, "alert", f"같은 코드(지금 사이트와 데이터 말고는 같아요)라 막지 않아요 — 흔들림이나 시계 탓이에요: "
                                       f"{row['text']} · 한 번 더 돌려도 {a['detail']}", row["new_only"], row["both"])
        rows.append(row)
    verdicts = {r["verdict"] for r in rows}
    return ("block" if "block" in verdicts else "alert" if "alert" in verdicts else "pass"), rows


def cmd_check(site, net=None, run=run_check, find=find_live, prepare=prepare_live):
    tmp = tmp_dir()
    for f in (DECISION_FILE, RECEIPT_FILE):        # 지난 결과 · 영수증은 지워요 (이번 결과만 믿어요)
        if os.path.exists(os.path.join(tmp, f)):
            os.unlink(os.path.join(tmp, f))
    site = os.path.abspath(site)
    head = head_sha()
    px = read_px(site)
    before = file_tree(site)
    need, why = read_need(tmp)
    d = {"head": head, "px": px, "why": why, "checks": {}, "live": None, "unknown": None, "same_code": False}
    if not need:
        d["result"] = "skipped"
        return finish(tmp, site, d, before, [])
    same_pages(site)
    say(f"· 배포 전 화면 검사: 새 코드 {head[:7]} · 올릴 데이터 {site} (한국 종가 {px}) · {why}")
    new = {t: run(t, ROOT, site) for t in CHECKS}
    same_pages(site)                                # 검사가 끝난 뒤에도 검사한 페이지 = 올릴 페이지
    if file_tree(site) != before:
        raise SystemExit("!! 검사하는 동안 올릴 폴더가 바뀌었어요 → 올리지 않아요")
    failing = [t for t in CHECKS if new[t]["outcome"] != PASS]
    live, again = None, {}
    if failing:
        say(f"!! 새 코드가 실패한 검사: {', '.join(failing)} → 지금 사이트의 코드로 같은 데이터에서 돌려 봐요")
        try:
            sha, served = find(net or W.Net())
            d["live"] = sha
            lv = prepare(sha, served, tmp)
            d["same_code"] = bool(lv.get("same_code"))
            live = {t: run(t, lv["dir"], site, live=True) for t in failing}
        except Exception as e:                      # noqa: BLE001 — 무엇이 안 되든 '알 수 없음' → 막아요
            d["unknown"] = str(e)[:300] if isinstance(e, Unknown) else f"{type(e).__name__}: {str(e)[:250]}"
            say(f"!! 지금 사이트의 코드를 알 수 없어요: {d['unknown']}")
            live = None
        if live is not None and d["same_code"]:
            _, rows0 = decide(new, live)
            for t in [r["check"] for r in rows0 if r["verdict"] == "block"]:                       # 같은 코드끼리 다른 결과: 새 코드로 한 번 더 (흔들림인지)
                say(f"!! {t}: 지금 사이트와 같은 코드인데 결과가 달라요 → 새 코드로 한 번 더 돌려 봐요")
                again[t] = run(t, ROOT, site)
        if file_tree(site) != before:
            raise SystemExit("!! 비교하는 동안 올릴 폴더가 바뀌었어요 → 올리지 않아요")
    d["result"], rows = decide(new, live, d["unknown"], same=d["same_code"], again=again)
    for t in CHECKS:
        d["checks"][t] = {"new": new[t], "live": (live or {}).get(t), "again": again.get(t)}
    return finish(tmp, site, d, before, rows)


def finish(tmp, site, d, before, rows):
    """결정을 적고 (요약 · 알림), 올려도 되면 영수증을 써요. 막으면 exit 1."""
    result, head, live = d["result"], d["head"], d.get("live")
    d["rows"] = rows
    with open(os.path.join(tmp, DECISION_FILE), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    title = {"pass": "PASS · 올려요", "skipped": "건너뜀 · 올려요", "alert": "지금 사이트 코드도 실패 · 올리고 알려요",
             "block": "막음 · 올리지 않아요 (사이트는 그대로)"}[result]
    lines = [f"### 뱁새 배포 전 화면 검사 — {title}", "",
             f"새 코드 {head[:7]} · 데이터: 올릴 폴더의 네 파일 (한국 종가 {d.get('px')}) · {d.get('why')}", ""]
    for r in rows:
        lines.append(f"- **{r['check']}**: {'통과' if r['verdict'] == 'ok' else '올림 (지금 코드도 실패)' if r['verdict'] == 'alert' else '막음'}"
                     f" · {r['text']}")
        lines += [f"  - 새 코드만 실패: `{x}`" for x in r["new_only"][:15]]
        lines += [f"  - 두 코드 모두 실패: `{x}`" for x in r["both"][:15]]
    if d.get("unknown"):
        lines += ["", f"지금 사이트의 코드를 알 수 없어요: {d['unknown']}"]
    unseen = [u for c in d["checks"].values() for u in (c["new"] or {}).get("unseen", [])]
    if unseen:
        lines += ["", "**오늘 데이터라서 확인하지 못했거나 다르게 확인한 장면 (통과로 셌어요)**", ""] + [f"- {u}" for u in unseen]
    summary("\n".join(lines) + "\n")
    for r in rows:
        say(f"· {r['check']}: {r['text']}")
        for x in r["new_only"][:15]:
            say(f"    새 코드만 실패: {x}")
    for u in unseen:                                # 검사 스크립트의 알림을 껐으니, 그 경고는 여기서 (매일 실행과 같은 뜻)
        say(f"::warning title=배포 전 화면 검사 · 오늘 데이터라서 다르게 확인한 장면::{esc(u)}")
    if result == "block":
        for r in rows:
            if r["verdict"] == "block":
                only = f" — 새 코드만 실패한 줄: {' · '.join(r['new_only'][:5])}" if r["new_only"] else ""
                say(f"::error title=배포 막음 · 배포 전 화면 검사::{esc(r['check'] + ': ' + r['text'] + only + '. 이 배포는 올리지 않아요 (사이트는 그대로예요).')}")
        say("!! 배포 막음: 새 코드가 지금 데이터에서 검사에 실패했어요 (위 줄) → 올리지 않아요. 사이트는 지금 그대로예요 (docs/RUNBOOK.md)")
        return 1
    if file_tree(site) != before:
        raise SystemExit("!! 올릴 폴더가 바뀌었어요 → 올리지 않아요")
    with open(os.path.join(tmp, RECEIPT_FILE), "w", encoding="utf-8") as f:
        f.write(before)
    if result == "alert":
        bad = ", ".join(r["check"] for r in rows if r["verdict"] == "alert")
        say(f"::warning title=배포 · 지금 사이트 코드도 실패::{esc(bad + ': 새 코드와 지금 사이트의 코드(' + str(live)[:7] + ')가 같은 데이터에서 같은 검사 줄에 실패해요. 데이터 쪽 문제로 보고 올려요 — 경보 이슈로 알려요.')}")
    say(f"· 배포 전 화면 검사: {title}")
    return 0


# ── 5. 영수증 확인 · 경보 이슈 ────────────────────────────────
def labels_of(issue):
    return {(x.get("name") if isinstance(x, dict) else x) for x in (issue or {}).get("labels") or []}


def ensure_label(net):
    W.ensure_label(net)
    net.gh("POST", f"/repos/{W.REPO}/labels", {"name": LABEL, "color": "B60205",
                                               "description": "배포 전 화면 검사: 지금 사이트의 코드도 같은 검사에 실패해요 (감시가 닫지 않아요)"},
           ok=(201, 422))


def check_lines(d):
    """경보 이슈의 검사 목록: 검사마다 한 번, 실패한 줄은 한 번씩 (두 코드 모두 실패한 줄)."""
    out = []
    for r in d.get("rows") or []:
        if r["verdict"] == "ok":
            continue
        out.append(f"- **{r['check']}**: {r['text']}")
        raw = (((d.get("checks") or {}).get(r["check"]) or {}).get("new") or {}).get("raw") or (r["new_only"] + r["both"])
        if raw:                                     # 새 코드의 실패 줄을 설명과 함께 한 번씩 (새 코드만 실패한 줄은 표시)
            out += [f"  <details><summary>실패한 줄 {len(raw)}개</summary>", "", "  ```"]
            out += [f"  {'(새 코드만) ' if label_of(x) in r['new_only'] else ''}{x[:300]}" for x in raw[:30]] + ["  ```", "  </details>"]
    return out


def alert_text(d, run_url, number, first):
    head, live = d["head"][:7], str(d.get("live"))[:7]
    k = sum(1 for r in d.get("rows") or [] if r["verdict"] == "alert")
    lines = [f"{MARK} 새 코드({head})를 지금 사이트에 올리고 있어요. 지금 사이트의 데이터(한국 종가 {d.get('px')} 기준)로 화면 검사 "
             f"{k}개가 실패하는데, 지금 사이트에 있는 코드({live})도 같은 데이터에서 같은 검사 줄에 실패해서 새 코드 탓이 아니라고 보고 "
             "막지 않았어요.", "",
             f"{W.MENTION} 뱁새 배포가 문제를 찾았어요.", "",
             "**지금 사용자에게 보이는 것:** 지금 데이터예요 (이 배포가 끝나면 새 코드로). 검사가 실패한 장면은 사용자 화면에서도 틀리게 "
             "보일 수 있어요. 바로 봐 주세요. 올리기가 실패하면 사이트는 그대로이고, 감시가 따로 알려요.", "",
             f"**언제:** {kst_now()} 배포", "", f"**배포 실행:** {run_url}", "",
             "### 실패한 검사 (같은 데이터 · 새 코드와 지금 사이트에 있는 코드)", *check_lines(d), ""]
    if first:
        lines += ["### 할 일", "Claude Code 클라우드 세션에 이렇게 붙여 넣어 주세요:", "", "> " + W.PASTE.format(n=number), ""]
    lines += [f"이 이슈에는 `{LABEL}` 표시가 붙어 있어서 감시가 '정상화됐어요'로 닫지 않아요. 배포가 세 검사를 다시 모두 통과하면 "
              "(코드 배포, 또는 다음 데이터 발행 뒤의 배포) 표시가 풀리고, 다른 문제가 없으면 감시가 닫아요. "
              "무엇을 뜻하는지: `docs/RUNBOOK.md`"]
    return "\n".join(lines)


def raise_alert(net, d, run_url):
    """경보 이슈: 열린 것이 있으면 표시를 먼저 붙이고 댓글, 없으면 표시를 단 채로 열어요. 번호 넣기(PATCH)가 안 되면 경고만."""
    ensure_label(net)
    issues = W.open_alerts(net)
    if issues:
        n = issues[0]["number"]
        net.gh("POST", f"/repos/{W.REPO}/issues/{n}/labels", {"labels": [LABEL]})
        net.gh("POST", f"/repos/{W.REPO}/issues/{n}/comments", {"body": alert_text(d, run_url, n, first=False)})
        say(f"!! 경보 이슈 #{n} 에 '{LABEL}' 표시를 붙이고 댓글을 달았어요")
        return n
    _, i = net.gh("POST", f"/repos/{W.REPO}/issues", {"title": W.ISSUE_TITLE, "labels": [W.LABEL, LABEL],
                                                      "body": alert_text(d, run_url, "N", first=True)})
    n = i["number"]
    try:
        net.gh("PATCH", f"/repos/{W.REPO}/issues/{n}", {"body": alert_text(d, run_url, n, first=True)})
    except Exception as e:                          # noqa: BLE001 — 이슈는 열렸어요 (Jack 은 알아요). 번호만 못 넣었어요
        say(f"::warning title=경보 이슈 번호 넣기 실패::#{n}: {esc(str(e)[:200])}")
    say(f"!! 경보 이슈 #{n} 을 열었어요 ('{LABEL}' 표시)")
    return n


def resolve_text(d, run_url):
    head, px = d["head"][:7], d.get("px")
    how = (f"이번 데이터는 매일 실행이 같은 코드로 세 검사를 통과한 뒤 발행했어요 ({d.get('why')})" if d["result"] == "skipped"
           else f"세 검사를 모두 통과했어요 (새 코드 {head})")
    return (f"{OK_MARK} {kst_now()} 배포: {how} · 데이터 한국 종가 {px} 기준.\n\n"
            f"`{LABEL}` 표시를 풀었어요. 다른 문제가 없으면 감시가 다음 점검에서 이 이슈를 닫아요.\n\n**배포 실행:** {run_url}")


def resolve_alerts(net, d, run_url):
    """deploy-check 표시가 붙은 열린 경보: 통과 댓글을 달고 표시를 풀어요 (닫는 것은 감시가 해요). 안 되면 크게 알리고 넘어가요."""
    done = []
    try:
        for i in W.open_alerts(net):
            if LABEL not in labels_of(i):
                continue
            n = i["number"]
            net.gh("POST", f"/repos/{W.REPO}/issues/{n}/comments", {"body": resolve_text(d, run_url)})
            net.gh("DELETE", f"/repos/{W.REPO}/issues/{n}/labels/{LABEL}", ok=(200, 204, 404))
            say(f"· 경보 이슈 #{n}: 세 검사를 다시 통과해서 '{LABEL}' 표시를 풀었어요")
            done.append(n)
    except Exception as e:                          # noqa: BLE001 — 표시 풀기는 배포를 멈추지 않아요 (크게 남겨요)
        say(f"::warning title=배포 전 화면 검사 · 경보 표시를 풀지 못함::{esc(str(e)[:300])} — 열린 경보 이슈의 "
            f"'{LABEL}' 표시를 손으로 풀어 주세요 (docs/RUNBOOK.md)")
    return done


def cmd_report(site, net=None):
    tmp = tmp_dir()
    try:
        with open(os.path.join(tmp, DECISION_FILE), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit(f"!! 배포 전 화면 검사의 결과가 없어요 ({type(e).__name__}) → 올리지 않아요")
    if d.get("result") not in ("pass", "skipped", "alert"):
        raise SystemExit(f"!! 배포 전 화면 검사의 결과가 '올려도 돼요'가 아니에요 ({d.get('result')!r}) → 올리지 않아요")
    try:
        with open(os.path.join(tmp, RECEIPT_FILE), encoding="utf-8") as f:
            receipt = f.read()
    except OSError:
        raise SystemExit("!! 배포 전 화면 검사의 통과 영수증이 없어요 → 올리지 않아요")
    if file_tree(os.path.abspath(site)) != receipt:
        raise SystemExit("!! 올릴 폴더가 검사한 것과 달라요 (영수증과 다름) → 올리지 않아요")
    say(f"· 올릴 폴더 = 검사한 폴더 (영수증 {len(receipt.splitlines()):,}개 파일 그대로) · 결과: {d['result']}")
    net = net or W.Net(os.environ.get("GITHUB_TOKEN"))
    run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{W.REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
               if os.environ.get("GITHUB_RUN_ID") else "(로컬 실행)")
    if d["result"] == "alert":
        try:                                        # 알리지 못하면 올리지 않아요: 실패하는 검사 위로 올릴 때는 Jack 이 꼭 알아야 해요
            n = raise_alert(net, d, run_url)
        except Exception as e:                      # noqa: BLE001
            raise SystemExit(f"!! 경보 이슈를 열지 못했어요 ({str(e)[:200]}) → 올리지 않아요 (실패하는 검사 위로 올릴 때는 꼭 알려야 해요). "
                             "Actions → Deploy → Run workflow 로 다시 돌려 주세요")
        summary(f"경보 이슈 #{n} 으로 알렸어요 ('{LABEL}' 표시).\n")
        return 0                                    # 알린 배포는 표시를 풀지 않아요 (아래 resolve 로 가지 않아요)
    resolve_alerts(net, d, run_url)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="뱁새 배포 전 화면 검사 (deploy.yml)")
    ap.add_argument("cmd", choices=("need", "skip", "check", "report"))
    ap.add_argument("--site", default="_site", help="올릴 폴더 (deploy.yml 의 _site)")
    a = ap.parse_args(argv)
    if a.cmd == "need":
        return cmd_need(a.site)
    if a.cmd == "skip":
        return cmd_skip()
    if a.cmd == "check":
        return cmd_check(a.site)
    return cmd_report(a.site)


if __name__ == "__main__":
    sys.exit(main())
