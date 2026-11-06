# -*- coding: utf-8 -*-
"""사이트에 올릴 폴더 만들기 (v17.6 Part 3a, deploy.yml).

  python3 tools/assemble_site.py OUT DATA_REF

- main 의 파일: git 이 관리하는 파일 전부 (지금 'main 브랜치에서 배포'가 보여 주는 것과 같게), 점(.)으로 시작하는 것
  (.github · .gitignore …)과 docs/ 는 빼요. 작업 폴더에서 복사하니 방금 빌드한 페이지(빌드 표시가 달린 것)가 들어가요.
- docs/ 를 빼는 이유 (Jack 2026-11-06): 설계 자료의 Adobe Stock 그림은 라이선스상 따로 내려받는 파일로 내놓으면 안 돼요
  (docs/design/v19.3/LICENSES.md). 사이트 페이지는 docs/ 의 파일을 쓰지 않아요.
- 데이터: data.json · corp.json · disc.json · macro.json 은 main 의 것을 쓰지 않고 DATA_REF(data 브랜치)에서만 가져와요.
  하나라도 없거나 비었으면 멈춰요 (main 의 파일로 조용히 바꾸지 않아요). 검사(validate_data.py --live)는 이 다음 단계예요.
"""
import os
import shutil
import subprocess
import sys

DATA_FILES = ("data.json", "corp.json", "disc.json", "macro.json")
EXCLUDED_DIR = "docs"            # Jack 2026-11-06: docs/ 는 사이트에 올리지 않아요 (Adobe Stock 그림 라이선스)


def tracked(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def site_files(paths):
    """올릴 main 파일: 점으로 시작하는 경로 조각이 하나도 없고, 데이터 네 파일도 docs/ 아래 파일도 아닌 것."""
    keep = []
    for p in paths:
        if any(part.startswith(".") for part in p.split("/")):
            continue
        if p in DATA_FILES:
            continue
        if p.split("/", 1)[0] == EXCLUDED_DIR:          # 설계 자료 (Adobe 그림 포함)는 사이트에 올리지 않아요
            continue
        keep.append(p)
    return keep


def assemble(root, out, data_ref):
    if os.path.exists(out):
        raise SystemExit(f"!! {out} 가 이미 있어요 (빈 곳에 새로 만들어요)")
    files = site_files(tracked(root))
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
    if os.path.exists(os.path.join(out, EXCLUDED_DIR)):         # 위 규칙이 깨지면 조용히 올리지 않고 멈춰요
        raise SystemExit(f"!! 사이트 폴더에 {EXCLUDED_DIR}/ 가 들어갔어요 → 배포하지 않아요 (Adobe 그림은 따로 내려받는 파일이 되면 안 돼요)")
    skipped = sum(1 for p in tracked(root) if p.split("/", 1)[0] == EXCLUDED_DIR)
    print(f"· {EXCLUDED_DIR}/ 의 파일 {skipped}개는 올리지 않아요 (설계 자료)")
    sha = subprocess.run(["git", "rev-parse", "--short", data_ref], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    print(f"· 사이트 폴더 {out}: main 파일 {len(files)}개 + {data_ref} ({sha}) 의 데이터 네 파일 "
          + " · ".join(f"{k} {v // 1024:,}KB" for k, v in sizes.items()))
    return files


def main(argv):
    if len(argv) != 2:
        raise SystemExit("쓰는 법: python3 tools/assemble_site.py OUT DATA_REF")
    assemble(os.getcwd(), argv[0], argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
