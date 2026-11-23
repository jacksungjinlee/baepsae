# -*- coding: utf-8 -*-
"""PR 규칙 두 가지를 CI 에서 확인해요 (Jack 2026-11-23: "Automate the rules you missed").

  python tools/pr_rules.py                       # CI: ci.yml 의 checks job 마지막 단계 (PR 설명은 이벤트에 실린 것)
  python tools/pr_rules.py --body-file F --base REV --head REV [--today YYYY-MM-DD]   # 시험 · 손으로 돌릴 때

규칙 1 — 사이트가 내보내는 것을 바꾸는 PR (CLAUDE.md § GitHub process):
  PR 설명에 매일 실행의 세 화면 검사를 지금 데이터(data 브랜치) 사본으로 돌린 결과가 있어야 해요:
  `tests/real_data_check.py --data DIR` · `tests/smoke_launch.py --data DIR` · `tests/smoke_app.py --data DIR`,
  각각 "N / N" (모두 통과)으로, 그리고 그 데이터의 날짜(YYYY-MM-DD, 오늘(KST)부터 DATE_MAX_AGE 일 안)를 결과 줄 가까이에.
  셋 중 하나라도 없거나, 검사 이름 뒤에 통과하지 못한 숫자(예: 13 / 14)가 하나라도 적혀 있거나, 날짜가 없으면 실패해요.
  HTML 주석(<!-- … -->) 안의 글은 읽지 않아요.
규칙 2 — src/ 나 데이터 파이프라인을 바꾸는 PR (Jack 2026-11-13: "update § 0 in the same PR as every merge"):
  docs/HANDOFF.md 의 § 0 (`## 0.` 제목부터 다음 `## ` 제목 전까지)이 공백 말고도 바뀌어야 해요.

비교: PR 의 merge 커밋(actions/checkout 의 기본, HEAD)과 그 첫 부모(base = main 의 끝, HEAD^1). main 이 앞서 나갔어도
PR 이 실제로 바꾸는 것만 봐요. PR 설명은 이 실행을 시작한 이벤트에 실린 것이에요 (CI 에는 열쇠를 두지 않아요):
설명만 고친 뒤에는 다음 커밋의 CI 가 새 설명으로 확인해요 ('다시 돌리기'는 처음 이벤트의 옛 설명을 그대로 봐요).
PR 이 아닌 실행: main 에 push · main 에서 손으로 실행만 통과예요. 다른 브랜치에서 돌린 실행(push · workflow_dispatch)은
PR 규칙을 확인하지 못하니 실패해요 — 그 초록이 PR 의 빨강을 덮지 못하게요 (리뷰 2026-11-23).
읽지 못하는 것이 있으면(이벤트 파일 · git) 통과시키지 않고 이유를 찍고 실패해요. 이 도구는 읽기만 해요.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
try:
    import assemble_site  # noqa: E402  (사이트에 올라가는 파일의 기준은 배포가 쓰는 것과 같은 함수)
except Exception as _e:  # noqa: BLE001 — 통과시키지 않고 이유를 찍고 멈춰요
    print(f"!! PR 규칙을 확인하지 못했어요: tools/assemble_site.py 를 불러오지 못했어요 ({type(_e).__name__}: {_e})")
    print("::error title=PR 규칙::PR 규칙을 확인하지 못했어요 — 위 줄을 보세요.")
    sys.exit(1)

KST = ZoneInfo("Asia/Seoul")
HANDOFF = "docs/HANDOFF.md"
CHECKS = ("real_data_check", "smoke_launch", "smoke_app")      # 매일 실행의 발행 전 화면 검사 (update-data.yml)

# 사이트가 내보내는 것을 정하는 빌드 · 배포 입력 (그 자체는 사이트에 올라가지 않아요). 이 파일들이 부르는 tools/ 파일과
# 그 파일들이 불러오는 tools/ 모듈은 build_tools() 가 끝까지 따라가 더해요 (build_tag.py · logos/logo_index.py …).
BUILD_INPUTS = ("template.html", "build.sh", "build-app.sh", "build-styleguide.sh", "package.json", "package-lock.json",
                "tools/assemble_site.py", ".github/workflows/deploy.yml")

# 데이터 파이프라인: 매일 실행 · 발행 관문 · 배포 · 감시와 그 도구들. 아래 세 workflow 가 부르는 tools/ 파일(과 그 모듈)은 자동으로,
# 매일 실행이 발행 전에 돌리는 세 화면 검사와 그 도우미도 (check_helpers) 더해요.
PIPELINE_FILES = ("fetch_data.py", "validate_data.py", "already_published.py", "watchdog.py", "requirements.txt",
                  "requirements-dev.txt", "tests/fonts/install.sh",
                  "tools/push_logos_branch.sh",                    # 로고 발행 (logos 브랜치) — 리뷰 2026-11-23 (Fable)
                  ".github/workflows/ci.yml", "tools/pr_rules.py")  # 이 규칙 자신과 CI 도 § 0 에 적어요
PIPELINE_DIRS = ("data/", "tools/logos/")
PIPELINE_WORKFLOWS = (".github/workflows/update-data.yml", ".github/workflows/deploy.yml",
                      ".github/workflows/watchdog.yml", ".github/workflows/logo-dev-check.yml",
                      ".github/workflows/logo-dev-fetch.yml")

# real_data_check.py 는 --data 로만 돌아요 (필수 인자) → 이름만 적어도 그 결과예요. 나머지 둘은 --data 가 있어야 진짜 데이터 결과예요.
RESULT_RE = re.compile(r"(?<!\w)(?:(real_data_check)(?:\.py)?(?:\s+--data\b)?|(smoke_launch|smoke_app)(?:\.py)?\s+--data\b)")
NAME_RE = re.compile(r"(?<!\w)(?:real_data_check|smoke_launch|smoke_app)(?:\.py)?")   # 어느 이름이든 앞 검사의 결과 부분을 끝내요
# 결과는 "171 / 171" (검사가 찍는 모양). 띄어 쓴 것을 모두 보고, 띄어 쓴 것이 없을 때만 "3/3" 하나 — "11/20" 같은 날짜를 결과로
# 읽지 않게요.
FRACTION_SPACED_RE = re.compile(r"(\d[\d,]*)\s+/\s+(\d[\d,]*)")
FRACTION_RE = re.compile(r"(\d[\d,]*)/(\d[\d,]*)")
DATE_RE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
DATE_LOOKBACK = 3          # 첫 결과 줄 위로 내용이 있는 줄 몇 개까지 날짜를 찾을지 (빈 줄 · 표의 |---| 줄은 세지 않아요 —
                           # "Real data (… pxDate 2026-11-20):" 아래에 결과나 표를 적는 모양)
DATE_MAX_AGE = 14          # 데이터 날짜는 오늘(KST)부터 이 날 수 안 (2017년 같은 열흘 연휴와 주말도 넘게; 그보다 오래면 지금 데이터가 아니에요)
TABLE_RULE_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
EXAMPLE = ("예: - Real data (data 브랜치 사본, pxDate 2026-11-20): `real_data_check.py --data` 3 / 3 · "
           "`smoke_launch.py --data` 14 / 14 · `smoke_app.py --data` 171 / 171")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


class RuleError(Exception):
    """확인에 필요한 것을 읽지 못함 — 통과시키지 않고 이유를 찍어요."""


# ── 바뀐 파일 분류 ──

class Tree:
    """파일을 읽는 곳: 작업 폴더(머리 = PR 을 merge 한 모습) 또는 git 의 한 커밋(base). 지운 파일은 base 에서만 보여요 —
    둘 다 보고 합쳐야 지운 도우미 · 도구도 규칙에 걸려요 (리뷰 2026-11-23, Fable)."""

    def __init__(self, root=ROOT, rev=None):
        self.root, self.rev = root, rev
        self._names = None
        if rev is not None:
            out = git("ls-tree", "-r", "--name-only", "-z", rev, root=root)
            self._names = {p for p in out.split("\0") if p}

    def exists(self, rel):
        return rel in self._names if self.rev is not None else os.path.isfile(os.path.join(self.root, rel))

    def read(self, rel):
        if not self.exists(rel):
            return None
        if self.rev is not None:
            r = subprocess.run(["git", "show", f"{self.rev}:{rel}"], cwd=self.root, capture_output=True)
            if r.returncode != 0:
                raise RuleError(f"git show {self.rev}:{rel} 실패")
            return r.stdout.decode("utf-8", "replace")
        with open(os.path.join(self.root, rel), encoding="utf-8", errors="replace") as f:
            return f.read()

    def subdirs(self, rel):
        """rel 폴더와 그 바로 아래 폴더들 (rel 기준 경로)."""
        if self.rev is not None:
            subs = {n[len(rel) + 1:].split("/", 1)[0] for n in self._names
                    if n.startswith(rel + "/") and "/" in n[len(rel) + 1:]}
        else:
            d = os.path.join(self.root, rel)
            subs = {x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x))} if os.path.isdir(d) else set()
        return [rel] + sorted(f"{rel}/{s}" for s in subs if not s.startswith(("__", ".")))


def _trees(trees):
    return trees if trees else (Tree(),)


def _imports(src):
    out = []
    for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", src, re.M):
        mods = [m.group(1)] if m.group(1) else [x.strip().split(" as ")[0] for x in m.group(2).split(",")]
        out += [x.split(".")[-1] for x in mods if x]
    return out


def check_helpers(*trees):
    """세 화면 검사와, 그것들이 (tests/ 안에서) 불러오는 도우미 파일 — 끝까지 따라가요 (주어진 모든 트리에서)."""
    out = set()
    for tr in _trees(trees):                       # 트리마다 따로 따라가요 (같은 파일도 트리마다 불러오는 것이 달라요)
        todo, seen = [f"tests/{c}.py" for c in CHECKS], set()
        while todo:
            rel = todo.pop()
            if rel in seen or not tr.exists(rel):
                continue
            seen.add(rel)
            for mod in _imports(tr.read(rel) or ""):
                if tr.exists(f"tests/{mod}.py"):
                    todo.append(f"tests/{mod}.py")
        out |= seen
    return sorted(out)


def _tool_closure(start, tr):
    """tools/ 파일들과, 그 파이썬 파일이 불러오는 tools/ (한 단계 아래 폴더 포함) 모듈을 끝까지."""
    dirs = tr.subdirs("tools")
    todo, seen = list(start), set()
    while todo:
        rel = todo.pop()
        if rel in seen or not tr.exists(rel):
            continue
        seen.add(rel)
        if not rel.endswith(".py"):
            continue
        for mod in _imports(tr.read(rel) or ""):
            for d in dirs:
                if tr.exists(f"{d}/{mod}.py"):
                    todo.append(f"{d}/{mod}.py")
    return seen


def _referenced_tools(files, tr):
    found = []
    for rel in files:
        for m in re.finditer(r"tools/[A-Za-z0-9_./-]+\.(?:py|sh)", tr.read(rel) or ""):
            found.append(m.group(0))
    return found


def build_tools(*trees):
    """빌드 · 배포 입력이 부르는 tools/ 파일과 그 모듈 (build_tag.py · assemble_site.py → logos/logo_index.py …)."""
    out = set()
    for tr in _trees(trees):
        start = [p for p in BUILD_INPUTS if p.startswith("tools/")] + _referenced_tools(BUILD_INPUTS, tr)
        out |= _tool_closure(start, tr)
    return sorted(out)


def pipeline_tools(*trees):
    """파이프라인 workflow 들이 부르는 tools/ 파일과 그 모듈 (저장소에 있는 것만)."""
    out = set()
    for tr in _trees(trees):
        out |= _tool_closure(_referenced_tools(PIPELINE_WORKFLOWS, tr), tr)
    return sorted(out)


def site_changes(changed, *trees):
    """사이트가 내보내는 것을 바꾸는 파일: 배포가 올리는 파일 · src/ · 빌드 · 배포 입력과 그 도구 · 세 화면 검사와 그 도우미."""
    extra = set(check_helpers(*trees)) | set(build_tools(*trees)) | set(BUILD_INPUTS)
    served = set(assemble_site.site_files(list(changed)))
    return sorted(p for p in changed if p in served or p.startswith("src/") or p in extra)


def handoff_changes(changed, *trees):
    """HANDOFF § 0 을 고쳐야 하는 파일: src/ · 데이터 파이프라인 (발행 전 화면 검사 · 로고 발행 · 이 규칙과 CI 포함) ·
    사이트가 내보내는 것을 바꾸는 파일 (리뷰 2026-11-23: 배포가 빌드하는 것도 파이프라인이에요)."""
    extra = set(pipeline_tools(*trees)) | set(PIPELINE_FILES) | set(PIPELINE_WORKFLOWS) | set(site_changes(changed, *trees))
    return sorted(p for p in changed
                  if p.startswith("src/") or p in extra or any(p.startswith(d) for d in PIPELINE_DIRS))


# ── 규칙 1: PR 설명의 실제 데이터 검사 결과 ──

def _num(s):
    return int(s.replace(",", ""))


def _valid_date(s):
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def today_kst():
    return dt.datetime.now(KST).date()


def _first_fraction(s):
    return FRACTION_SPACED_RE.search(s) or FRACTION_RE.search(s)


def _result_part(seg):
    """검사 이름 뒤의 글에서 그 검사의 결과를 담은 부분만: 표라면 띄어 쓴 'N / M' 이 처음 나오는 칸(없으면 '3/3' 이 나오는 칸),
    아니면 첫 결과 숫자 뒤의 첫 문장 끝(". ")까지 — 같은 줄 뒤의 다른 숫자(예: "… 171 / 171. 드라이런: 2,341 / 2,476")를 결과로
    읽지 않게요. 결과 숫자 앞의 ". "(예: "Nov. 20", "vs. main")에서는 자르지 않아요 (리뷰 2026-11-23, Fable 2차)."""
    if "|" in seg:
        cells = seg.split("|")
        seg = (next((c for c in cells if FRACTION_SPACED_RE.search(c)), None)
               or next((c for c in cells if FRACTION_RE.search(c)), cells[0]))
    f = _first_fraction(seg)
    if not f:
        return seg
    m = re.search(r"\.\s", seg[f.end():])
    return seg if not m else seg[: f.end() + m.start()]


def real_data_results(body, today=None):
    """(ok, 줄들) — 줄은 화면에 찍을 설명. 세 검사마다 통과한 결과가 하나 이상, 검사 이름 뒤에 통과하지 못한 결과는 하나도 없음,
    결과 줄 가까이에 오늘(KST)부터 DATE_MAX_AGE 일 안의 날짜."""
    today = today or today_kst()
    text = COMMENT_RE.sub("", (body or "").replace("\r\n", "\n"))
    clean = [ln.replace("`", "").replace("**", "") for ln in text.split("\n")]
    found = {c: [] for c in CHECKS}                       # 검사 → [(줄 번호, 통과 수, 전체 수)]
    no_number = {c: [] for c in CHECKS}
    for i, ln in enumerate(clean):
        names = [m.start() for m in NAME_RE.finditer(ln)] + [len(ln)]
        for k in range(len(names) - 1):
            m = RESULT_RE.match(ln, names[k])
            if not m:
                continue                                  # 이름만 (smoke_app 을 --data 없이) — 결과가 아니지만 앞 검사의 부분은 끝내요
            name = m.group(1) or m.group(2)
            seg = _result_part(ln[m.end(): names[k + 1]])
            fr = list(FRACTION_SPACED_RE.finditer(seg)) or list(FRACTION_RE.finditer(seg))[:1]
            if fr:
                found[name] += [(i, _num(f.group(1)), _num(f.group(2))) for f in fr]
            else:
                no_number[name].append(i)
    out, ok = [], True
    result_lines = []
    for c in CHECKS:
        good = [x for x in found[c] if x[1] == x[2] > 0]
        bad = [x for x in found[c] if not (x[1] == x[2] > 0)]
        if bad:
            ok = False
            out.append(f"!! {c} --data: 통과하지 못한 결과가 적혀 있어요 — "
                       + ", ".join(f"{x[1]} / {x[2]} ({x[0] + 1}번째 줄)" for x in bad)
                       + " (고친 뒤 다시 돌린 결과만 적어 주세요)")
        if good:
            out.append(f"· {c} --data: {good[0][1]} / {good[0][2]} ({good[0][0] + 1}번째 줄)")
            result_lines += [x[0] for x in good]
        elif not bad:
            ok = False
            why = " (이름은 있지만 'N / N' 결과가 같은 줄에 없어요)" if no_number[c] else ""
            out.append(f"!! {c} --data: 결과가 없어요{why}")
    if result_lines:
        lo, hi, n = min(result_lines), max(result_lines), 0
        while lo > 0 and n < DATE_LOOKBACK:              # 위로 내용이 있는 줄 DATE_LOOKBACK 개까지 (빈 줄 · 표의 |---| 줄은 빼고)
            lo -= 1
            if clean[lo].strip() and not TABLE_RULE_RE.match(clean[lo]):
                n += 1
        raw = sorted({d for ln in clean[lo: hi + 1] for d in DATE_RE.findall(ln)})
        dates = [d for d in (_valid_date(x) for x in raw) if d is not None]
        fresh = [d for d in dates if dt.timedelta(0) <= today - d <= dt.timedelta(days=DATE_MAX_AGE)]
        if fresh:
            out.append(f"· 데이터 날짜: {max(fresh).isoformat()}")
        else:
            ok = False
            seen = f" (적힌 날짜: {', '.join(raw)})" if raw else ""
            out.append(f"!! 데이터 날짜(YYYY-MM-DD)가 결과 줄 가까이({lo + 1}~{hi + 1}번째 줄)에 없거나, 오늘({today.isoformat()})부터 "
                       f"{DATE_MAX_AGE}일 안이 아니에요{seen} — 지금 data 브랜치 사본으로 다시 돌려 주세요")
    if not ok:
        out.append(EXAMPLE)
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
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuleError(f"git {' '.join(args[:2])} … 실패: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


def changed_files(base, head, root=ROOT):
    out = git("diff", "--name-only", "--no-renames", "-z", base, head, root=root)
    return sorted(p for p in out.split("\0") if p)


def show(rev, path, root=ROOT):
    """rev 의 파일 내용 · 그 커밋에 파일이 없으면 None. 다른 git 오류는 RuleError (조용히 '없음'으로 읽지 않아요)."""
    names = git("ls-tree", "--name-only", rev, "--", path, root=root).split("\n")
    if path not in names:
        return None
    return git("show", f"{rev}:{path}", root=root)


def event_pr():
    """이 실행을 시작한 이벤트의 PR (번호 · 설명 · 머리 커밋) — 열쇠 없이 읽어요 (CI 에는 토큰을 두지 않아요, test_screen_check.py).
    설명만 고친 뒤에는 '다시 돌리기'도 옛 설명을 봐요 (처음 이벤트를 그대로 써요) → 다음 커밋의 CI 가 새 설명으로 확인해요."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    try:
        with open(path, encoding="utf-8") as f:
            pr = json.load(f)["pull_request"]
        return pr["number"], pr.get("body") or "", (pr.get("head") or {}).get("sha")
    except (TypeError, OSError, ValueError, KeyError) as e:
        raise RuleError(f"PR 이벤트({path})를 읽지 못했어요: {type(e).__name__}") from None


def check_merge_commit(head_sha, root=ROOT):
    """HEAD 가 GitHub 의 시험 merge 커밋인지: 둘째 부모 = 이벤트의 PR 머리 커밋. 아니면(체크아웃에 ref: 를 주는 등) 첫 부모가 main 이
    아니라 PR 의 이전 커밋이라 마지막 커밋만 보게 돼요 → 멈춰요 (리뷰 2026-11-23, Fable)."""
    if not head_sha:
        raise RuleError("PR 이벤트에 머리 커밋(head.sha)이 없어요")
    got = git("rev-parse", "HEAD^2", root=root).strip()
    if got != head_sha:
        raise RuleError(f"HEAD 가 PR 의 merge 커밋이 아니에요 (HEAD^2 {got[:7]} ≠ PR 머리 {head_sha[:7]})")


# ── 실행 ──

def run(body, base, head, root=ROOT, today=None):
    """(ok, 줄들). 지운 파일도 걸리게 base 와 머리(작업 폴더) 두 트리에서 분류해요."""
    changed = changed_files(base, head, root)
    trees = (Tree(root), Tree(root, base))
    lines = [f"· 이 PR 이 바꾼 파일 {len(changed)}개"]
    ok = True
    site = site_changes(changed, *trees)
    if site:
        lines.append(f"규칙 1 — 사이트가 내보내는 것을 바꿔요 ({len(site)}개: {', '.join(site[:6])}"
                     + (" …" if len(site) > 6 else "") + ") → 실제 데이터 검사 결과가 PR 설명에 있어야 해요")
        r_ok, r_lines = real_data_results(body, today)
        ok &= r_ok
        lines += ["  " + x for x in r_lines]
    else:
        lines.append("규칙 1 — 사이트가 내보내는 것을 바꾸지 않아요 (해당 없음)")
    hand = handoff_changes(changed, *trees)
    if hand:
        lines.append(f"규칙 2 — src/ · 파이프라인 · 사이트를 바꿔요 ({len(hand)}개: {', '.join(hand[:6])}"
                     + (" …" if len(hand) > 6 else "") + f") → {HANDOFF} § 0 을 고쳐야 해요")
        h_ok, h_line = section0_changed(show(base, HANDOFF, root), show(head, HANDOFF, root))
        ok &= h_ok
        lines.append("  " + h_line)
    else:
        lines.append("규칙 2 — src/ 도 파이프라인도 사이트도 바꾸지 않아요 (해당 없음)")
    return ok, lines


def not_a_pr():
    """PR 이 아닌 실행: (통과?, 줄). main 에 push 와 main 에서 손으로 실행만 통과예요."""
    ev, ref = os.environ.get("GITHUB_EVENT_NAME") or "", os.environ.get("GITHUB_REF") or ""
    if ev in ("push", "workflow_dispatch") and ref == "refs/heads/main":
        return True, f"· PR 이 아닌 실행({ev} · {ref})이라 확인할 것이 없어요"
    return False, (f"!! PR 이 아닌 실행({ev or '?'} · {ref or '?'})이라 PR 규칙을 확인하지 못했어요 — 브랜치에서 돌린 실행은 "
                   "PR 의 결과를 대신하지 못해요. PR 에 커밋을 하나 더 올려 PR 의 CI 로 확인해 주세요")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file")
    ap.add_argument("--base", default="HEAD^1")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--today", help="데이터 날짜를 잴 오늘 (YYYY-MM-DD, 다시 돌려 볼 때) — 없으면 오늘(KST)")
    a = ap.parse_args(argv)
    try:
        today = dt.date.fromisoformat(a.today) if a.today else None
        if a.body_file is not None:
            try:
                with open(a.body_file, encoding="utf-8") as f:
                    body, label = f.read(), a.body_file
            except OSError as e:
                raise RuleError(f"설명 파일({a.body_file})을 읽지 못했어요: {type(e).__name__}") from None
        elif os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
            good, line = not_a_pr()
            print(line)
            if not good:
                print("::error title=PR 규칙::" + line.lstrip("! "))
            return 0 if good else 1
        else:
            number, body, head_sha = event_pr()
            check_merge_commit(head_sha)
            label = f"PR #{number}"
        ok, lines = run(body, a.base, a.head, today=today)
    except (RuleError, ValueError, OSError) as e:
        print(f"!! PR 규칙을 확인하지 못했어요: {e}")
        print("::error title=PR 규칙::PR 규칙을 확인하지 못했어요 — 위 줄을 보세요.")
        return 1
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
