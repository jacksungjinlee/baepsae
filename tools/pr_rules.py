# -*- coding: utf-8 -*-
"""PR 규칙 두 가지를 CI 에서 확인해요 (Jack 2026-11-23: "Automate the rules you missed").

  python tools/pr_rules.py                       # CI (ci.yml 의 pr_rules job): PR 설명은 GitHub 에서 지금 것을 읽어요
  python tools/pr_rules.py --body-file F --base REV --head REV   # 시험 · 손으로 돌릴 때

규칙 1 — 사이트가 내보내는 것을 바꾸는 PR (CLAUDE.md § GitHub process):
  PR 설명에 매일 실행의 세 화면 검사를 지금 데이터(data 브랜치) 사본으로 돌린 결과가 있어야 해요:
  `tests/real_data_check.py --data DIR` · `tests/smoke_launch.py --data DIR` · `tests/smoke_app.py --data DIR`,
  각각 "N / N" (모두 통과)으로, 그리고 그 데이터의 날짜(YYYY-MM-DD)를 결과 줄 가까이에.
  셋 중 하나라도 없거나, 통과하지 못한 숫자(예: 13 / 14)가 적혀 있거나, 날짜가 없으면 실패해요.
규칙 2 — src/ 나 데이터 파이프라인을 바꾸는 PR (Jack 2026-11-13: "update § 0 in the same PR as every merge"):
  docs/HANDOFF.md 의 § 0 (`## 0.` 제목부터 다음 `## ` 제목 전까지)이 공백 말고도 바뀌어야 해요.

비교: PR 의 merge 커밋(actions/checkout 의 기본, HEAD)과 그 첫 부모(base = main 의 끝, HEAD^1). main 이 앞서 나갔어도
PR 이 실제로 바꾸는 것만 봐요. PR 설명은 이 실행을 시작한 이벤트에 실린 것이에요 (CI 에는 열쇠를 두지 않아요):
설명만 고친 뒤에는 다음 커밋의 CI 가 새 설명으로 확인해요 ('다시 돌리기'는 처음 이벤트의 옛 설명을 그대로 봐요).
PR 이 아닌 실행(main 에 push · 손으로 실행)은 확인할 것이 없어서 통과예요. 이 도구는 읽기만 해요.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import assemble_site  # noqa: E402  (사이트에 올라가는 파일의 기준은 배포가 쓰는 것과 같은 함수)

HANDOFF = "docs/HANDOFF.md"
CHECKS = ("real_data_check", "smoke_launch", "smoke_app")      # 매일 실행의 발행 전 화면 검사 (update-data.yml)

# 사이트가 내보내는 것을 정하는 빌드 · 배포 입력 (그 자체는 사이트에 올라가지 않아요)
BUILD_INPUTS = ("template.html", "build.sh", "build-app.sh", "package.json", "package-lock.json",
                "tools/assemble_site.py", ".github/workflows/deploy.yml")

# 데이터 파이프라인: 매일 실행 · 발행 관문 · 배포 · 감시와 그 도구들. 아래 세 workflow 가 부르는 tools/ 파일은 자동으로 더해요.
PIPELINE_FILES = ("fetch_data.py", "validate_data.py", "already_published.py", "watchdog.py", "requirements.txt")
PIPELINE_DIRS = ("data/",)
PIPELINE_WORKFLOWS = (".github/workflows/update-data.yml", ".github/workflows/deploy.yml",
                      ".github/workflows/watchdog.yml")

RESULT_RE = re.compile(r"(?<!\w)(" + "|".join(CHECKS) + r")(?:\.py)?\s+--data\b")
# 결과는 "171 / 171" (검사가 찍는 모양). 띄어 쓴 것을 먼저 찾고, 없을 때만 "3/3" — "11/20" 같은 날짜를 결과로 읽지 않게요.
FRACTION_SPACED_RE = re.compile(r"(\d[\d,]*)\s+/\s+(\d[\d,]*)")
FRACTION_RE = re.compile(r"(\d[\d,]*)/(\d[\d,]*)")
DATE_RE = re.compile(r"\b20\d\d-[01]\d-[0-3]\d\b")
DATE_LOOKBACK = 3          # 결과 줄 위로 몇 줄까지 날짜를 찾을지 ("Real data (… pxDate 2026-11-20):" 아래에 결과를 적는 모양)


# ── 바뀐 파일 분류 ──

def check_helpers(root=ROOT):
    """세 화면 검사와, 그것들이 (tests/ 안에서) 불러오는 도우미 파일 — 끝까지 따라가요."""
    tdir = os.path.join(root, "tests")
    todo = [f"{c}.py" for c in CHECKS]
    seen = set()
    while todo:
        name = todo.pop()
        if name in seen or not os.path.isfile(os.path.join(tdir, name)):
            continue
        seen.add(name)
        with open(os.path.join(tdir, name), encoding="utf-8") as f:
            src = f.read()
        for m in re.finditer(r"^\s*(?:from\s+(\w+)\s+import|import\s+([\w, ]+))", src, re.M):
            mods = [m.group(1)] if m.group(1) else [x.strip().split(" as ")[0] for x in m.group(2).split(",")]
            for mod in mods:
                if mod and os.path.isfile(os.path.join(tdir, mod + ".py")):
                    todo.append(mod + ".py")
    return sorted("tests/" + n for n in seen)


def pipeline_tools(root=ROOT):
    """파이프라인 workflow 셋이 부르는 tools/ 파일 (저장소에 있는 것만)."""
    found = set()
    for wf in PIPELINE_WORKFLOWS:
        p = os.path.join(root, wf)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            for m in re.finditer(r"tools/[A-Za-z0-9_./-]+\.(?:py|sh)", f.read()):
                if os.path.isfile(os.path.join(root, m.group(0))):
                    found.add(m.group(0))
    return sorted(found)


def site_changes(changed, root=ROOT):
    """사이트가 내보내는 것을 바꾸는 파일: 배포가 올리는 파일 · src/ · 빌드 · 배포 입력 · 세 화면 검사와 그 도우미."""
    helpers = set(check_helpers(root))
    served = set(assemble_site.site_files(list(changed)))
    return sorted(p for p in changed
                  if p in served or p.startswith("src/") or p in BUILD_INPUTS or p in helpers)


def handoff_changes(changed, root=ROOT):
    """HANDOFF § 0 을 고쳐야 하는 파일: src/ 와 데이터 파이프라인."""
    tools = set(pipeline_tools(root))
    return sorted(p for p in changed
                  if p.startswith("src/") or p in PIPELINE_FILES or p in PIPELINE_WORKFLOWS or p in tools
                  or any(p.startswith(d) for d in PIPELINE_DIRS))


# ── 규칙 1: PR 설명의 실제 데이터 검사 결과 ──

def _num(s):
    return int(s.replace(",", ""))


def real_data_results(body):
    """(ok, 줄들) — 줄은 화면에 찍을 설명. 세 검사마다 통과한 결과가 하나 이상, 통과하지 못한 결과는 없음, 날짜 있음."""
    lines = (body or "").replace("\r\n", "\n").split("\n")
    clean = [ln.replace("`", "").replace("**", "") for ln in lines]
    found = {c: [] for c in CHECKS}                       # 검사 → [(줄 번호, 통과 수, 전체 수)]
    no_number = {c: [] for c in CHECKS}
    for i, ln in enumerate(clean):
        hits = list(RESULT_RE.finditer(ln))
        for k, m in enumerate(hits):
            seg = ln[m.end(): hits[k + 1].start() if k + 1 < len(hits) else len(ln)]
            f = FRACTION_SPACED_RE.search(seg) or FRACTION_RE.search(seg)
            if f:
                found[m.group(1)].append((i, _num(f.group(1)), _num(f.group(2))))
            else:
                no_number[m.group(1)].append(i)
    out, ok = [], True
    result_lines = []
    for c in CHECKS:
        good = [x for x in found[c] if x[1] == x[2] > 0]
        bad = [x for x in found[c] if not (x[1] == x[2] > 0)]
        if bad:
            ok = False
            out.append(f"!! {c} --data: 통과하지 못한 결과가 적혀 있어요 — "
                       + ", ".join(f"{x[1]} / {x[2]} ({x[0] + 1}번째 줄)" for x in bad))
        if good:
            out.append(f"· {c} --data: {good[0][1]} / {good[0][2]} ({good[0][0] + 1}번째 줄)")
            result_lines += [x[0] for x in good]
        elif not bad:
            ok = False
            why = " (이름은 있지만 'N / N' 결과가 같은 줄에 없어요)" if no_number[c] else ""
            out.append(f"!! {c} --data: 결과가 없어요{why}")
    if result_lines:
        lo, hi = max(0, min(result_lines) - DATE_LOOKBACK), max(result_lines)
        dates = sorted({d for ln in clean[lo: hi + 1] for d in DATE_RE.findall(ln)})
        if dates:
            out.append(f"· 데이터 날짜: {', '.join(dates)}")
        else:
            ok = False
            out.append(f"!! 데이터 날짜(YYYY-MM-DD)가 결과 줄 가까이({lo + 1}~{hi + 1}번째 줄)에 없어요")
    return ok, out


# ── 규칙 2: HANDOFF § 0 ──

def section0(text):
    """`## 0.` 제목부터 다음 `## ` 제목 전까지. 없으면 None."""
    if text is None:
        return None
    m = re.search(r"^## 0[.\s].*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else None


def section0_changed(before, after):
    """(ok, 설명). 공백만 바뀐 것은 바뀐 것으로 세지 않아요."""
    a = section0(after)
    if a is None:
        return False, f"!! {HANDOFF} 에서 '## 0.' 제목을 찾지 못했어요"
    b = section0(before)
    norm = lambda s: re.sub(r"\s+", " ", s or "").strip()   # noqa: E731
    if b is not None and norm(a) == norm(b):
        return False, f"!! {HANDOFF} § 0 이 바뀌지 않았어요 (이번 PR 이 무엇을 바꾸고 다음은 무엇인지 적어 주세요)"
    return True, f"· {HANDOFF} § 0 바뀜"


# ── git · GitHub ──

def git(*args, root=ROOT):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def changed_files(base, head, root=ROOT):
    out = git("diff", "--name-only", "--no-renames", "-z", base, head, root=root)
    return sorted(p for p in out.split("\0") if p)


def show(rev, path, root=ROOT):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=root, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def event_body():
    """(PR 번호, 설명) — 이 실행을 시작한 이벤트에 실린 것 (열쇠 없이 읽어요: CI 에는 토큰을 두지 않아요, test_screen_check.py).
    설명만 고친 뒤에는 '다시 돌리기'도 옛 설명을 봐요 (처음 이벤트를 그대로 써요) → 다음 커밋의 CI 가 새 설명으로 확인해요."""
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        pr = json.load(f)["pull_request"]
    return pr["number"], pr.get("body") or ""


# ── 실행 ──

def run(body, base, head, root=ROOT):
    """(ok, 줄들)."""
    changed = changed_files(base, head, root)
    lines = [f"· 이 PR 이 바꾼 파일 {len(changed)}개"]
    ok = True
    site = site_changes(changed, root)
    if site:
        lines.append(f"규칙 1 — 사이트가 내보내는 것을 바꿔요 ({len(site)}개: {', '.join(site[:6])}"
                     + (" …" if len(site) > 6 else "") + ") → 실제 데이터 검사 결과가 PR 설명에 있어야 해요")
        r_ok, r_lines = real_data_results(body)
        ok &= r_ok
        lines += ["  " + x for x in r_lines]
    else:
        lines.append("규칙 1 — 사이트가 내보내는 것을 바꾸지 않아요 (해당 없음)")
    hand = handoff_changes(changed, root)
    if hand:
        lines.append(f"규칙 2 — src/ 나 파이프라인을 바꿔요 ({len(hand)}개: {', '.join(hand[:6])}"
                     + (" …" if len(hand) > 6 else "") + f") → {HANDOFF} § 0 을 고쳐야 해요")
        h_ok, h_line = section0_changed(show(base, HANDOFF, root), show(head, HANDOFF, root))
        ok &= h_ok
        lines.append("  " + h_line)
    else:
        lines.append("규칙 2 — src/ 도 파이프라인도 바꾸지 않아요 (해당 없음)")
    return ok, lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file")
    ap.add_argument("--base", default="HEAD^1")
    ap.add_argument("--head", default="HEAD")
    a = ap.parse_args(argv)
    if a.body_file is not None:
        with open(a.body_file, encoding="utf-8") as f:
            body, label = f.read(), a.body_file
    else:
        if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
            print(f"· PR 이 아닌 실행({os.environ.get('GITHUB_EVENT_NAME') or '손으로'})이라 확인할 것이 없어요")
            return 0
        number, body = event_body()
        label = f"PR #{number}"
    ok, lines = run(body, a.base, a.head)
    print(f"PR 규칙 확인 · {label}")
    for ln in lines:
        print(ln)
    if not ok:
        print("::error title=PR 규칙::실제 데이터 검사 결과나 HANDOFF § 0 이 빠졌어요 — 위 줄을 보세요. "
              "PR 설명만 고쳤다면 다음 커밋의 CI 가 새 설명으로 확인해요.")
        print("!! PR 규칙을 지키지 않았어요")
        return 1
    print("· PR 규칙 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
