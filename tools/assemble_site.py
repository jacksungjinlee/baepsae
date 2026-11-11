# -*- coding: utf-8 -*-
"""사이트에 올릴 폴더 만들기 (v17.6 Part 3a, deploy.yml).

  python3 tools/assemble_site.py OUT DATA_REF [LOGOS_REF]

- main 의 파일: git 이 관리하는 파일 가운데 사이트가 쓰는 것. 점(.)으로 시작하는 것
  (.github · .gitignore …)과 docs/, 그리고 사이트가 읽지 않는 개발용 폴더 · 파일(NOT_SITE_DIRS · NOT_SITE_FILES)은 빼요. 작업 폴더에서 복사하니 방금 빌드한 페이지(빌드 표시가 달린 것)가 들어가요.
- docs/ 를 빼는 이유 (Jack 2026-11-06): 설계 자료의 Adobe Stock 그림은 라이선스상 따로 내려받는 파일로 내놓으면 안 돼요
  (docs/design/v19.3/LICENSES.md). 사이트 페이지는 docs/ 의 파일을 쓰지 않아요.
- 개발용 폴더 · 파일을 빼는 이유 (Jack 2026-11-11): tests/ 의 시험용 데이터(예: tests/fixtures/v2/data.json)가 사이트에 올라가
  진짜 data.json 과 헷갈릴 수 있었어요. 사이트 페이지 · 서비스워커 · 매니페스트는 이 폴더 · 파일을 부르지 않아요 (tests/test_site_files.py).
  새로 뺄 것이 생기면 아래 두 목록에 더해요. 사이트가 읽는 파일은 여기에 넣지 않아요.
- 데이터: data.json · corp.json · disc.json · macro.json 은 main 의 것을 쓰지 않고 DATA_REF(data 브랜치)에서만 가져와요.
  하나라도 없거나 비었으면 멈춰요 (main 의 파일로 조용히 바꾸지 않아요). 검사(validate_data.py --live)는 이 다음 단계예요.
- 회사 로고 (v19.3a): logos/ 는 LOGOS_REF(logos 브랜치)에서만 가져와요. main 에 logos/ 가 있으면 그건 올리지 않아요.
  로고는 사이트를 멈추게 하지 않아요: 브랜치가 없거나, logos/index.json 과 그림이 서로 맞지 않거나(tools/logos/logo_index.py),
  다른 파일이 섞여 있으면 크게 경고하고 logos/ 없이 사이트를 만들어요 (앱은 글자 표시를 보여 줘요).
  색인의 회사 이름이 오늘 data.json 과 다른 항목(코드가 다른 회사로 바뀐 것)은 빼요. logos/ 는 누구나 읽을 수 있게(0755 · 0644) 둬요.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos"))
import logo_index as LI  # noqa: E402

LOGOS = "logos"

DATA_FILES = ("data.json", "corp.json", "disc.json", "macro.json")
EXCLUDED_DIR = "docs"            # Jack 2026-11-06: docs/ 는 사이트에 올리지 않아요 (Adobe Stock 그림 라이선스)
# Jack 2026-11-11: 사이트가 읽지 않는 개발용 폴더 · 파일. tests/ = 시험 코드와 시험용 데이터 · tools/ = 빌드 · 배포 도구 ·
# data/ = 파이프라인이 읽는 표(csv; 사이트의 data.json 과 다른 것) · styleguide/ = styleguide.html 의 소스.
NOT_SITE_DIRS = ("tests", "tools", "data", "styleguide")
NOT_SITE_FILES = ("CLAUDE.md", "README.md", "template.html",
                  "fetch_data.py", "validate_data.py", "watchdog.py", "already_published.py",
                  "build.sh", "build-app.sh", "build-styleguide.sh",
                  "package.json", "package-lock.json", "requirements.txt", "requirements-dev.txt")


def tracked(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def in_excluded(p):
    """맨 위 폴더가 docs 인 경로 (Docs/ 처럼 대소문자만 다른 것도 — Pages 는 대소문자를 가려서 그대로 올려 버려요)."""
    return p.split("/", 1)[0].lower() == EXCLUDED_DIR


_NOT_SITE_FILES_LOWER = tuple(f.lower() for f in NOT_SITE_FILES)


def not_site(p):
    """사이트가 읽지 않는 개발용 경로: 맨 위 폴더가 NOT_SITE_DIRS 이거나, 맨 위 파일이 NOT_SITE_FILES.
    둘 다 대소문자만 다른 것도 (Tests/ · readme.md) — Pages 는 대소문자를 가려서 그대로 올려 버려요."""
    top, _, rest = p.partition("/")
    return top.lower() in NOT_SITE_DIRS if rest else p.lower() in _NOT_SITE_FILES_LOWER


def not_site_entry(folder, name):
    """사이트 폴더 맨 위의 항목 하나가 개발용인지 (not_site 와 같은 규칙: 폴더는 폴더 목록으로, 파일은 파일 목록으로)."""
    full = os.path.join(folder, name)
    return not_site(name + "/x") if os.path.isdir(full) else not_site(name)


def site_files(paths):
    """올릴 main 파일: 점으로 시작하는 경로 조각이 하나도 없고, 데이터 네 파일도 docs/ 아래 파일도 개발용 폴더 · 파일도 아닌 것."""
    keep = []
    for p in paths:
        if any(part.startswith(".") for part in p.split("/")):
            continue
        if p in DATA_FILES:
            continue
        if in_excluded(p):                                # 설계 자료 (Adobe 그림 포함)는 사이트에 올리지 않아요
            continue
        if not_site(p):                                   # 시험 · 도구 · 파이프라인 파일은 사이트에 올리지 않아요
            continue
        keep.append(p)
    return keep


def no_logos(why):
    """로고 없이 배포한다는 경고: 로그에 크게, GitHub 실행 화면에는 경고 표시로."""
    print(f"!! 회사 로고 없이 배포해요: {why} → 앱은 회사마다 글자 표시를 보여 줘요")
    print(f"::warning title=로고 없이 배포::{why} 이번 배포는 회사 로고 대신 글자 표시를 보여 줘요.")
    return None


def logo_entries(root, ref):
    """ref 의 파일 [(이름, blob, 크기)] — logos/ 바로 아래의 보통 파일만. 다른 것이 하나라도 있으면 (None, 이유)."""
    r = subprocess.run(["git", "ls-tree", "-r", "-l", "-z", "--full-tree", ref], cwd=root, capture_output=True)
    if r.returncode != 0:
        return None, f"{ref} 의 파일 목록을 읽지 못했어요"
    out = []
    for item in (x for x in r.stdout.decode("utf-8", "replace").split("\0") if x):
        meta, _, path = item.partition("\t")
        parts = meta.split()
        if len(parts) != 4:
            return None, f"{ref} 의 파일 목록을 읽지 못했어요 ({meta!r})"
        mode, kind, obj, size = parts
        name = path[len(LOGOS) + 1:] if path.startswith(LOGOS + "/") else ""
        if mode != "100644" or kind != "blob" or not name or "/" in name:
            return None, f"{ref} 에 logos/ 의 보통 파일이 아닌 것이 있어요 ({path!r}, {mode})"
        if name != LI.INDEX and not LI.FILE_RE.match(name):
            return None, f"{ref} 에 그림(.webp · .png)도 index.json 도 아닌 파일이 있어요 ({path!r})"
        limit = LI.MAX_INDEX_BYTES if name == LI.INDEX else LI.MAX_FILE_BYTES
        if not size.isdigit() or int(size) > limit:
            return None, f"{ref} 의 {path} 가 너무 커요 ({size} bytes)"
        out.append((name, obj, int(size)))
    if len(out) > LI.MAX_FILES + 1:
        return None, f"{ref} 에 파일이 너무 많아요 ({len(out):,}개)"
    return out, None


def copy_logos(root, out, ref):
    """logos 브랜치(ref)의 logos/ 를 사이트 폴더에 넣어요. 무엇이 잘못되든 사이트는 멈추지 않아요: 크게 경고하고 로고 없이.
    반환: 넣은 회사 수 (넣지 않았으면 None)."""
    if not ref:
        return no_logos("logos 브랜치를 주지 않았어요.")
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        return no_logos(f"logos 브랜치({ref})가 없어요.")
    sha = r.stdout.strip()
    entries, why = logo_entries(root, sha)
    if why:
        return no_logos(why)
    stage = tempfile.mkdtemp(prefix=".logos-", dir=os.path.dirname(os.path.abspath(out)))
    try:
        for name, obj, size in entries:
            blob = subprocess.run(["git", "cat-file", "blob", obj], cwd=root, capture_output=True)
            if blob.returncode != 0 or len(blob.stdout) != size:
                return no_logos(f"{ref} 의 logos/{name} 를 읽지 못했어요.")
            with open(os.path.join(stage, name), "wb") as fh:
                fh.write(blob.stdout)
        index, bad = LI.validate_dir(stage)
        if bad:
            return no_logos(f"{ref} 의 logos/ 가 검사를 통과하지 못했어요 ({len(bad)}건: " + "; ".join(bad[:3]) + ").")
        # 코드 재사용: 오늘 data.json 의 회사 이름과 다른 항목은 빼요 (코드가 다른 회사로 바뀌면 글자 표시가 안전해요)
        try:
            with open(os.path.join(out, "data.json"), encoding="utf-8") as fh:
                names = LI.stock_names(json.load(fh))
        except (OSError, ValueError) as e:
            return no_logos(f"사이트 폴더의 data.json 을 읽지 못해 로고 이름을 맞춰 보지 못했어요 ({type(e).__name__}).")
        index, gone, unknown = LI.keep_current(index, names)
        if gone:
            print(f"!! 로고 {len(gone)}개는 오늘 data.json 의 회사 이름과 맞지 않아서 뺐어요 (코드가 다른 회사로 바뀌었거나 이름이 "
                  f"바뀜 → 글자 표시): {', '.join(gone[:30])}{' …' if len(gone) > 30 else ''}")
            print(f"::warning title=로고 이름 불일치::로고 {len(gone)}개는 오늘 회사 이름과 달라서 글자 표시로 보여 줘요.")
        if unknown:                                       # 이름이 비었거나 코드뿐이면 같은 회사인지 알 수 없어요
            print(f"!! 로고 {len(unknown)}개는 회사 이름이 비었거나 코드뿐이라 같은 회사인지 확인하지 못해서 뺐어요 (→ 글자 표시): "
                  f"{', '.join(unknown[:30])}{' …' if len(unknown) > 30 else ''}")
            print(f"::warning title=로고 이름 없음::로고 {len(unknown)}개는 회사 이름으로 확인하지 못해 글자 표시로 보여 줘요.")
        if gone or unknown:
            used = {e["file"] for e in index["logos"].values()}
            for n in os.listdir(stage):
                if n != LI.INDEX and n not in used:
                    os.remove(os.path.join(stage, n))
            with open(os.path.join(stage, LI.INDEX), "w", encoding="utf-8") as fh:
                json.dump(index, fh, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            index, bad = LI.validate_dir(stage)
            if bad:
                return no_logos("이름이 맞지 않는 로고를 뺀 뒤 logos/ 가 검사를 통과하지 못했어요 (" + "; ".join(bad[:3]) + ").")
        # Pages 의 artifact 는 모두가 읽을 수 있어야 해요 (mkdtemp 는 0700 이라 그대로 두면 배포가 실패해요)
        os.chmod(stage, 0o755)
        for n in os.listdir(stage):
            os.chmod(os.path.join(stage, n), 0o644)
        dst = os.path.join(out, LOGOS)
        if os.path.exists(dst):
            return no_logos(f"사이트 폴더에 이미 {LOGOS}/ 가 있어요.")
        shutil.move(stage, dst)
        stage = None
        pictures = len(os.listdir(dst)) - 1
        print(f"· 회사 로고: {ref} ({sha[:7]}) 의 logos/ · 회사 {len(index['logos']):,}곳 · 그림 {pictures:,}개 "
              f"({sum(os.path.getsize(os.path.join(dst, n)) for n in os.listdir(dst)) // 1024:,}KB)")
        return len(index["logos"])
    finally:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


def assemble(root, out, data_ref, logos_ref=None):
    if os.path.exists(out):
        raise SystemExit(f"!! {out} 가 이미 있어요 (빈 곳에 새로 만들어요)")
    files = site_files(tracked(root))
    on_main = [p for p in files if p.split("/", 1)[0] == LOGOS]
    if on_main:                                           # 로고는 logos 브랜치에서만 (main 에 들어오면 안 돼요)
        print(f"!! main 에 {LOGOS}/ 파일이 {len(on_main)}개 있어요: 올리지 않아요 (로고는 logos 브랜치에서만 가져와요)")
        print(f"::warning title=main 에 로고 파일::main 의 {LOGOS}/ 파일 {len(on_main)}개는 사이트에 올리지 않았어요. "
              "로고는 logos 브랜치에만 있어야 해요.")
        files = [p for p in files if p not in on_main]
    for p in files:
        src = os.path.join(root, p)
        if not os.path.isfile(src):
            raise SystemExit(f"!! main 의 파일이 작업 폴더에 없어요: {p}")
        dst = os.path.join(out, p)
        os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
        shutil.copyfile(src, dst)
    os.makedirs(out, exist_ok=True)
    sizes = {}
    for f in DATA_FILES:
        r = subprocess.run(["git", "show", f"{data_ref}:{f}"], cwd=root, capture_output=True)
        if r.returncode != 0 or not r.stdout.strip():
            raise SystemExit(f"!! {data_ref} 에 {f} 가 없거나 비었어요 → 배포하지 않아요 (main 의 파일로 바꾸지 않아요)")
        with open(os.path.join(out, f), "wb") as fh:
            fh.write(r.stdout)
        sizes[f] = len(r.stdout)
    if any(in_excluded(n) for n in os.listdir(out)):              # 위 규칙이 깨지면 조용히 올리지 않고 멈춰요
        raise SystemExit(f"!! 사이트 폴더에 {EXCLUDED_DIR}/ 가 들어갔어요 → 배포하지 않아요 (Adobe 그림은 따로 내려받는 파일이 되면 안 돼요)")
    got_in = sorted(n for n in os.listdir(out) if not_site_entry(out, n))   # 같은 뜻: 개발용 폴더 · 파일이 들어가면 조용히 올리지 않고 멈춰요
    if got_in:
        raise SystemExit(f"!! 사이트 폴더에 개발용 폴더 · 파일이 들어갔어요: {', '.join(got_in)} → 배포하지 않아요 "
                         "(사이트가 읽지 않는 것들이에요. 시험용 데이터는 사이트의 데이터와 헷갈리면 안 돼요)")
    skipped = sum(1 for p in tracked(root) if in_excluded(p))
    print(f"· {EXCLUDED_DIR}/ 의 파일 {skipped}개는 올리지 않아요 (설계 자료)")
    dev = [p for p in tracked(root) if not_site(p)]
    print(f"· 개발용 폴더 · 파일 {len(dev)}개는 올리지 않아요 ({' · '.join(d + '/' for d in NOT_SITE_DIRS)} · 맨 위 파일 "
          f"{sum(1 for p in dev if '/' not in p)}개)")
    sha = subprocess.run(["git", "rev-parse", "--short", data_ref], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    print(f"· 사이트 폴더 {out}: main 파일 {len(files)}개 + {data_ref} ({sha}) 의 데이터 네 파일 "
          + " · ".join(f"{k} {v // 1024:,}KB" for k, v in sizes.items()))
    try:
        copy_logos(root, out, logos_ref)
    except Exception as e:                               # noqa: BLE001 — 로고 때문에 사이트 배포가 멈추지 않아요 (크게 남겨요)
        shutil.rmtree(os.path.join(out, LOGOS), ignore_errors=True)
        no_logos(f"로고를 넣다가 오류가 났어요 ({type(e).__name__}: {e}).")
    return files


def main(argv):
    if len(argv) not in (2, 3):
        raise SystemExit("쓰는 법: python3 tools/assemble_site.py OUT DATA_REF [LOGOS_REF]")
    assemble(os.getcwd(), argv[0], argv[1], argv[2] if len(argv) == 3 else None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
