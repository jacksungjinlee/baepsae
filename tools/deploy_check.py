# -*- coding: utf-8 -*-
"""배포 전 화면 검사 — tools/deploy_check.py (Jack J6, 2026-11-12, deploy.yml)
──────────────────────────────────────────────────────────────
코드가 바뀌는 배포(main 에 머지 · 손으로 누른 배포)는 올리기 전에, 매일 실행의 '발행 전 화면 검사'와 같은 세 검사를
올릴 폴더(_site)의 데이터 그대로 새 코드로 돌려요. Jack 의 규칙: 새 코드가 실패한 검사를 지금 사이트의 코드가 같은 데이터로
통과하면 막아요 (사이트는 그대로). 지금 사이트의 코드도 같은 검사에서 실패하면 올려요 (데이터 문제를 고치는 코드도 올라갈 수
있게) — 그리고 Jack 에게 알려요 (경보 이슈 data-alert + deploy-check 표시 · 경고).

  python3 tools/deploy_check.py need                 # (토큰 있음) 이 배포가 검사해야 하는지 → $RUNNER_TEMP/deploy-need.json
  python3 tools/deploy_check.py skip                 # 검사하지 않는 배포면 exit 0 (도구를 깔지 않아요). 그 밖에는 exit 1 (깔아요)
  python3 tools/deploy_check.py check --site _site   # (토큰 없음 · 브라우저) 세 검사 → 결정 · 영수증 (막으면 exit 1)
  python3 tools/deploy_check.py report --site _site  # (토큰 있음) 영수증 확인 · 경보 이슈 열기 · 댓글 / 표시 풀기

검사할지 (need):
- push(머지) · workflow_dispatch(손으로) → 늘 검사해요.
- workflow_run(데이터 실행 뒤) → 그 데이터 실행이 검사한 코드에서 지금 올릴 코드까지 바뀐 것이 데이터 네 파일뿐일 때만 건너뛰어요
  (GitHub compare API: 데이터 실행의 커밋 head_sha … 지금 main 의 커밋마다 바뀐 파일). 매일 실행은 data 브랜치에 올리기 전에
  같은 세 검사를 그 코드로 그 파일에 돌렸어요. 코드가 바뀌었거나 확인하지 못하면 검사해요.

결정 (검사마다 따로):
  새 코드 통과                          → 됐어요
  새 코드 실패 · 지금 코드 통과           → 막아요 (다른 검사에서 둘 다 실패해도)
  새 코드 실패 · 지금 코드도 실패         → 올리고 알려요
  새 코드 실패 · 지금 코드를 알 수 없음    → 막아요 (빌드 표시를 못 읽음 · 커밋을 받지 못함 · 다시 빌드한 페이지가 사이트의 것과 다름 ·
                                         지금 코드의 검사가 끝까지 돌지 못함)
'실패' = 결과 줄(N / M 통과)의 N 이 M 보다 적어요. 새 코드 쪽에서는 검사가 끝까지 돌지 못한 것(결과 줄 없음 · 시작 못 함 ·
종료 코드와 결과 줄이 맞지 않음)도 실패예요. 지금 코드 쪽에서 끝까지 돌지 못한 것은 '알 수 없음'이에요: 그것을 '지금 코드도 실패'로
치면 검사 도구의 고장이 배포를 통과시켜요.
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
SHA_RE = re.compile(r"[0-9a-f]{40}")
PASS, FAIL, CRASH = "pass", "fail", "crash"
MAX_COMMITS = 20                    # 데이터 실행 뒤 커밋이 이보다 많으면 하나하나 보지 않고 검사해요
LABEL = W.DEPLOY_CHECK_LABEL        # 이 표시가 붙은 경보는 감시가 닫지 않아요 (watchdog.clear_alerts)
MARK = "**[배포 화면 검사]**"
OK_MARK = "**[배포 화면 검사 · 통과]**"
NEED_FILE, DECISION_FILE, RECEIPT_FILE = "deploy-need.json", "deploy-check.json", "deploy-check-pass.sha256"
LIVE_DIR = "deploy-live"


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


def kst_now():
    return W.kst(dt.datetime.now(dt.timezone.utc))


def git(*args, cwd=ROOT, timeout=300):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def head_sha(cwd=ROOT):
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


# ── 1. 이 배포가 검사해야 하는지 ──────────────────────────────
def code_changes(net, base, head):
    """base(데이터 실행의 커밋) → head(올릴 커밋) 사이 커밋들이 바꾼 파일 가운데 데이터 네 파일이 아닌 것. 확인하지 못하면 예외."""
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
        files = [f.get("filename") for f in (one or {}).get("files") or []]
        if not files or len(files) >= 300:          # 빈 목록 · 잘린 목록(300개)은 무엇이 바뀌었는지 몰라요
            raise RuntimeError(f"커밋 {c['sha'][:7]} 의 바뀐 파일 목록을 다 읽지 못했어요 ({len(files)}개)")
        other.update(f for f in files if f not in DATA_FILES)
    return sorted(other), len(commits)


def need_checks(event, run_head, head, net):
    """(검사할까, 이유). 모르는 것은 모두 '검사해요' 쪽이에요."""
    if event == "push":
        return True, "main 에 코드가 들어왔어요 (머지)"
    if event == "workflow_dispatch":
        return True, "손으로 누른 배포예요"
    if event != "workflow_run":
        return True, f"모르는 계기({event or '없음'})라 검사해요"
    if not SHA_RE.fullmatch(run_head or ""):
        return True, "데이터 실행이 검사한 커밋을 몰라서 검사해요"
    if run_head == head:
        return False, f"데이터 실행이 이 코드({head[:7]})로 같은 파일을 검사하고 올렸어요"
    try:
        other, n = code_changes(net, run_head, head)
    except Exception as e:                          # noqa: BLE001 — 확인하지 못하면 검사해요 (건너뛰지 않아요)
        return True, f"데이터 실행({run_head[:7]}) 뒤로 코드가 바뀌었는지 확인하지 못해서 검사해요 ({str(e)[:160]})"
    if other:
        return True, (f"데이터 실행({run_head[:7]}) 뒤로 코드가 바뀌었어요 ({', '.join(other[:5])}"
                      f"{' …' if len(other) > 5 else ''}) → 검사해요")
    return False, (f"데이터 실행({run_head[:7]})이 이 코드로 같은 파일을 검사하고 올렸어요 "
                   f"(그 뒤 커밋 {n}개는 데이터 네 파일만 바꿨어요 · 올릴 커밋 {head[:7]})")


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


def cmd_need(net=None):
    tmp = tmp_dir()
    head = head_sha()
    net = net or W.Net(os.environ.get("GITHUB_TOKEN"))
    run, why = need_checks(os.environ.get("EVENT", ""), os.environ.get("RUN_HEAD", ""), head, net)
    with open(os.path.join(tmp, NEED_FILE), "w", encoding="utf-8") as f:
        json.dump({"run": run, "why": why, "head": head}, f, ensure_ascii=False)
    say(("· 배포 전 화면 검사를 해요: " if run else "· 배포 전 화면 검사를 하지 않아요: ") + why)
    return 0


def cmd_skip():
    run, why = read_need(tmp_dir())
    if run:
        say(f"· 검사하는 배포예요 → 준비해요 ({why})")
        return 1
    say(f"· 검사하지 않는 배포예요 → 준비하지 않아요 ({why})")
    return 0


# ── 2. 검사 돌리기 ───────────────────────────────────────────
def outcome(rc, lines):
    """(PASS|FAIL|CRASH, 설명). 결과 줄은 마지막 'N / M 통과' (매일 실행의 요약과 같은 줄)."""
    m = None
    for ln in lines:
        mm = RESULT_RE.fullmatch(ln.rstrip("\r\n"))
        if mm:
            m = mm
    if m:
        n, total = int(m.group(1)), int(m.group(2))
        count = f"{n} / {total} 통과"
        if rc == 0 and n == total and total > 0:
            return PASS, count
        if rc not in (0, None) and n < total:
            return FAIL, count
        return CRASH, f"{count} 인데 종료 코드가 {rc} 라 앞뒤가 맞지 않아요"
    return CRASH, f"끝까지 돌지 못했어요 (결과 줄 없음 · 종료 코드 {rc})"


def run_check(name, root, data, live=False):
    """root 의 tests/<name>.py --data <data> 를 돌려요. 출력은 그대로 이 실행의 로그에. → 결과 dict."""
    label = "지금 사이트 코드" if live else "새 코드"
    cmd = [sys.executable, os.path.join("tests", f"{name}.py"), "--data", data]
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    if live:                                        # 비교용 실행: 그 검사의 실패 알림(::error)은 이 배포의 결론이 아니라서 빼요
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
    out, detail = outcome(rc, lines)
    fails = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("FAIL ") and s not in fails:
            fails.append(s)
    unseen = [ln.strip() for ln in lines if ln.startswith(("!! 확인 못 함", "!! 알림"))]
    say(f"· {name} ({label}): {'통과' if out == PASS else '실패' if out == FAIL else '끝까지 돌지 못함'} · {detail}")
    return {"outcome": out, "detail": detail, "fails": fails[:15], "unseen": unseen[:10]}


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


def has_commit(sha):
    return git("cat-file", "-e", f"{sha}^{{commit}}", timeout=60).returncode == 0


def _step(what, cmd, cwd, env=None, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unknown(f"{what}: {type(e).__name__}")
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
        raise Unknown(f"{what} 실패 (종료 코드 {r.returncode}): " + " / ".join(t[:160] for t in tail))
    return r


def prepare_live(sha, served, tmp):
    """지금 사이트의 커밋을 따로 된 폴더에 받아 빌드해요 (같은 빌드 표시로). 다시 빌드한 페이지가 사이트에서 받은 것과 한 글자도
    같아야 그 폴더가 '지금 사이트의 코드'예요. → 폴더. 무엇이든 안 되면 Unknown."""
    d = os.path.join(tmp, LIVE_DIR)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    say(f"· 지금 사이트의 코드 {sha[:7]} 를 {d} 에 받아 빌드해요")
    if has_commit(sha):                             # 이미 있으면 받지 않아요 (--depth=1 은 있는 기록을 얕게 잘라 버려요)
        say(f"· 커밋 {sha[:7]} 은 이미 있어요 (받지 않아요)")
    else:                                           # 배포의 checkout 은 커밋 하나뿐(얕은 clone): 그 커밋 하나만 더 받아요
        _step("지금 사이트 커밋 받기 (git fetch)", ["git", "fetch", "-q", "--depth=1", "--no-tags", "origin", sha], ROOT, timeout=300)
    tar = os.path.join(tmp, LIVE_DIR + ".tar")
    _step("지금 사이트 코드 꺼내기 (git archive)", ["git", "archive", "--format=tar", "-o", tar, sha], ROOT, timeout=300)
    _step("지금 사이트 코드 풀기 (tar)", ["tar", "-x", "-f", tar, "-C", d], ROOT, timeout=300)
    if os.path.exists(tar):
        os.unlink(tar)
    _step("지금 사이트 코드의 라이브러리 (npm ci)", ["npm", "ci", "--no-audit", "--no-fund"], d, timeout=600)
    env = {**os.environ, "BAEPSAE_BUILD": sha}
    for s in LIVE_BUILD:
        _step(f"지금 사이트 코드 빌드 ({s})", ["bash", s], d, env=env, timeout=600)
    for p, body in served.items():
        f = os.path.join(d, p)
        got = open(f, "rb").read() if os.path.isfile(f) else b""
        if hashlib.sha256(got).digest() != hashlib.sha256(body).digest():
            raise Unknown(f"다시 빌드한 {p} 가 사이트에서 받은 것과 달라요 (커밋 {sha[:7]})")
    say(f"· 다시 빌드한 {' · '.join(served)} 가 사이트의 것과 한 글자도 같아요 → 지금 사이트의 코드예요 ({sha[:7]})")
    return d


# ── 4. 결정 ─────────────────────────────────────────────────
def decide(new, live, unknown=None):
    """new: {검사: 결과} (셋 모두). live: {검사: 결과} (새 코드가 실패한 검사만) 또는 None (지금 코드를 알 수 없음).
    결과 = {"outcome": PASS|FAIL|CRASH, "detail": 설명}. → ("pass"|"alert"|"block", [(검사, "ok"|"alert"|"block", 설명)])"""
    rows = []
    for t in CHECKS:
        n = (new or {}).get(t) or {"outcome": CRASH, "detail": "돌리지 않았어요"}
        if n["outcome"] == PASS:
            rows.append((t, "ok", f"새 코드 {n['detail']}"))
            continue
        lv = None if live is None else live.get(t)
        if lv is None:
            rows.append((t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드: 알 수 없어요 ({unknown or '돌리지 않았어요'})"))
        elif lv["outcome"] == PASS:
            rows.append((t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드 {lv['detail']} → 새 코드만 실패해요"))
        elif lv["outcome"] == FAIL:
            rows.append((t, "alert", f"새 코드 {n['detail']} · 지금 사이트 코드도 {lv['detail']}"))
        else:
            rows.append((t, "block", f"새 코드 {n['detail']} · 지금 사이트 코드의 검사가 끝까지 돌지 못했어요 ({lv['detail']}) → 알 수 없어요"))
    verdicts = {v for _, v, _ in rows}
    return ("block" if "block" in verdicts else "alert" if "alert" in verdicts else "pass"), rows


def cmd_check(site, net=None, run=run_check, find=find_live, prepare=prepare_live):
    tmp = tmp_dir()
    for f in (DECISION_FILE, RECEIPT_FILE):
        if os.path.exists(os.path.join(tmp, f)):
            os.unlink(os.path.join(tmp, f))
    site = os.path.abspath(site)
    head = head_sha()
    px = read_px(site)
    before = file_tree(site)
    need, why = read_need(tmp)
    d = {"head": head, "px": px, "why": why, "checks": {}, "live": None, "unknown": None}
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
    live = None
    if failing:
        say(f"!! 새 코드가 실패한 검사: {', '.join(failing)} → 지금 사이트의 코드로 같은 데이터에서 돌려 봐요")
        try:
            sha, served = find(net or W.Net())
            d["live"] = sha
            live_root = prepare(sha, served, tmp)
            live = {t: run(t, live_root, site, live=True) for t in failing}
        except Exception as e:                      # noqa: BLE001 — 무엇이 안 되든 '알 수 없음' → 막아요
            d["unknown"] = str(e)[:300] if isinstance(e, Unknown) else f"{type(e).__name__}: {str(e)[:250]}"
            say(f"!! 지금 사이트의 코드를 알 수 없어요: {d['unknown']}")
            live = None
        if file_tree(site) != before:
            raise SystemExit("!! 비교하는 동안 올릴 폴더가 바뀌었어요 → 올리지 않아요")
    d["result"], rows = decide(new, live, d["unknown"])
    for t in CHECKS:
        d["checks"][t] = {"new": new[t], "live": (live or {}).get(t)}
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
    for t, v, text in rows:
        lines.append(f"- **{t}**: {'통과' if v == 'ok' else '올림 (지금 코드도 실패)' if v == 'alert' else '막음'} · {text}")
    if d.get("unknown"):
        lines += ["", f"지금 사이트의 코드를 알 수 없어요: {d['unknown']}"]
    unseen = [u for c in d["checks"].values() for u in (c["new"] or {}).get("unseen", [])]
    if unseen:
        lines += ["", "**오늘 데이터라서 확인하지 못했거나 다르게 확인한 장면 (통과로 셌어요)**", ""] + [f"- {u}" for u in unseen]
    summary("\n".join(lines) + "\n")
    for t, v, text in rows:
        say(f"· {t}: {text}")
    if result == "block":
        for t, v, text in rows:
            if v == "block":
                say(f"::error title=배포 막음 · 배포 전 화면 검사::{W.V._gh_escape(f'{t}: {text}. 이 배포는 올리지 않아요 (사이트는 그대로예요).')}")
        say("!! 배포 막음: 새 코드가 지금 데이터에서 검사에 실패했어요 (위 줄) → 올리지 않아요. 사이트는 지금 그대로예요 (docs/RUNBOOK.md)")
        return 1
    if file_tree(site) != before:
        raise SystemExit("!! 올릴 폴더가 바뀌었어요 → 올리지 않아요")
    with open(os.path.join(tmp, RECEIPT_FILE), "w", encoding="utf-8") as f:
        f.write(before)
    if result == "alert":
        bad = ", ".join(t for t, v, _ in rows if v == "alert")
        say(f"::warning title=배포 · 지금 사이트 코드도 실패::{W.V._gh_escape(f'{bad}: 새 코드와 지금 사이트의 코드({str(live)[:7]})가 같은 데이터에서 같은 검사에 실패해요. 데이터 쪽 문제로 보고 올려요 — 경보 이슈로 알려요.')}")
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
    out = []
    for t, v, text in d.get("rows") or []:
        if v == "ok":
            continue
        out.append(f"- **{t}**: {text}")
        c = (d.get("checks") or {}).get(t) or {}
        for who, key in (("새 코드", "new"), ("지금 사이트 코드", "live")):
            fails = (c.get(key) or {}).get("fails") or []
            if fails:
                out += [f"  <details><summary>{who}의 실패 줄 {len(fails)}개</summary>", "", "  ```"]
                out += [f"  {x[:300]}" for x in fails] + ["  ```", "  </details>"]
    return out


def alert_text(d, run_url, number, first):
    head, live = d["head"][:7], str(d.get("live"))[:7]
    k = sum(1 for _, v, _ in d.get("rows") or [] if v == "alert")
    lines = [f"{MARK} 새 코드({head})를 사이트에 올렸지만, 지금 사이트의 데이터(한국 종가 {d.get('px')} 기준)로 화면 검사 {k}개가 "
             f"실패해요. 지금 사이트에 있던 코드({live})도 같은 데이터에서 같은 검사에 실패해서, 새 코드 탓이 아니라고 보고 배포를 "
             "막지 않았어요.", "",
             f"{W.MENTION} 뱁새 배포가 문제를 찾았어요.", "",
             "**지금 사용자에게 보이는 것:** 새 코드와 지금 데이터예요. 검사가 실패한 장면은 사용자 화면에서도 틀리게 보일 수 있어요. "
             "바로 봐 주세요.", "",
             f"**언제:** {kst_now()} 배포", "", f"**배포 실행:** {run_url}", "",
             "### 실패한 검사 (같은 데이터 · 새 코드와 지금 사이트에 있던 코드)", *check_lines(d), ""]
    if first:
        lines += ["### 할 일", "Claude Code 클라우드 세션에 이렇게 붙여 넣어 주세요:", "", "> " + W.PASTE.format(n=number), ""]
    lines += [f"이 이슈에는 `{LABEL}` 표시가 붙어 있어서 감시가 '정상화됐어요'로 닫지 않아요. 배포가 세 검사를 다시 모두 통과하면 "
              "(코드 배포, 또는 다음 데이터 발행 뒤의 배포) 표시가 풀리고, 다른 문제가 없으면 감시가 닫아요. "
              "무엇을 뜻하는지: `docs/RUNBOOK.md`"]
    return "\n".join(lines)


def raise_alert(net, d, run_url):
    ensure_label(net)
    issues = W.open_alerts(net)
    if issues:
        n = issues[0]["number"]
        net.gh("POST", f"/repos/{W.REPO}/issues/{n}/comments", {"body": alert_text(d, run_url, n, first=False)})
        net.gh("POST", f"/repos/{W.REPO}/issues/{n}/labels", {"labels": [LABEL]})
        say(f"!! 경보 이슈 #{n} 에 댓글을 달고 '{LABEL}' 표시를 붙였어요")
        return n
    _, i = net.gh("POST", f"/repos/{W.REPO}/issues", {"title": W.ISSUE_TITLE, "labels": [W.LABEL, LABEL],
                                                      "body": alert_text(d, run_url, "N", first=True)})
    n = i["number"]
    net.gh("PATCH", f"/repos/{W.REPO}/issues/{n}", {"body": alert_text(d, run_url, n, first=True)})
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
        say(f"::warning title=배포 전 화면 검사 · 경보 표시를 풀지 못함::{W.V._gh_escape(str(e)[:300])} — 열린 경보 이슈의 "
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
                             "Deploy 를 다시 돌려 주세요")
        summary(f"경보 이슈 #{n} 으로 알렸어요 ('{LABEL}' 표시).\n")
        return 0
    resolve_alerts(net, d, run_url)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="뱁새 배포 전 화면 검사 (deploy.yml)")
    ap.add_argument("cmd", choices=("need", "skip", "check", "report"))
    ap.add_argument("--site", default="_site", help="올릴 폴더 (deploy.yml 의 _site)")
    a = ap.parse_args(argv)
    if a.cmd == "need":
        return cmd_need()
    if a.cmd == "skip":
        return cmd_skip()
    if a.cmd == "check":
        return cmd_check(a.site)
    return cmd_report(a.site)


if __name__ == "__main__":
    sys.exit(main())
