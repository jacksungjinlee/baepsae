#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""글자 점검 (v17.6 Part 2, CI 가 PR 마다 돌려요): python tests/check_text.py

- 빌드한 네 페이지(baepsae.html · app.html · app-preview.html · styleguide.html, 저장소에 커밋한 것): 이모지 0개, 금지어 0개
  (docs/BAEPSAE_VOICE.md 의 '## 금지어' 줄 — tests/test_text.py 와 같은 규칙)
- 저장소의 모든 .json: 따옴표 밖 NaN · Infinity 0개 (브라우저는 그런 파일을 통째로 거부해요 — validate_data.strict_loads 그대로)
하나라도 걸리면 무엇이 어디에 몇 개인지 적고 exit 1.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_text import EMOJI, banned_words            # noqa: E402
from validate_data import strict_loads              # noqa: E402

PAGES = ("baepsae.html", "app.html", "app-preview.html", "styleguide.html")


def check(root=ROOT):
    problems = []
    words = banned_words()
    for name in PAGES:
        with open(os.path.join(root, name), encoding="utf-8") as f:
            html = f.read()
        emoji = EMOJI.findall(html)
        if emoji:
            problems.append(f"{name}: 이모지 {len(emoji)}개 {sorted(set(emoji))}")
        found = {w: html.count(w) for w in words if w in html}
        if found:
            problems.append(f"{name}: 금지어 {found}")
    out = subprocess.run(["git", "ls-files", "-z", "*.json"], cwd=root, check=True, capture_output=True).stdout
    files = [p for p in out.decode("utf-8").split("\0") if p]
    for p in files:
        with open(os.path.join(root, p), encoding="utf-8") as f:
            text = f.read()
        try:
            strict_loads(text, p)
        except ValueError as e:
            problems.append(f"{p}: {e}")
    return problems, len(files)


def main():
    problems, n = check()
    for p in problems:
        print("!! " + p)
    print(f"글자 점검: 페이지 {len(PAGES)}개 · JSON {n}개 · 문제 {len(problems)}개")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
