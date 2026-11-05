# -*- coding: utf-8 -*-
"""빌드 표시 (v17.6 Part 1): 배포할 때만 페이지 <head> 에 <meta name="baepsae-build" content="커밋"> 를 넣어요.

  BAEPSAE_BUILD=<40자리 커밋> python3 tools/build_tag.py baepsae.html [app.html …]

build.sh · build-app.sh · build-styleguide.sh 가 BAEPSAE_BUILD 가 있을 때만 불러요 (사이트 배포 deploy.yml 이 넣어요).
없으면 아무것도 하지 않아서, 저장소에 커밋하는 빌드 결과는 지금과 한 글자도 다르지 않아요 ('소스와 같은지' 검사 그대로).
감시(watchdog.py)는 이 표시로 사이트가 어느 커밋을 보여 주는지 확인해요 (Pages 가 예전 빌드를 보여 주면 잡아요).
"""
import os
import re
import sys

CHARSET = '<meta charset="utf-8">'
NAME = "baepsae-build"


def tag(html, sha):
    """CHARSET 바로 뒤에 표시를 하나 넣은 html. 형식이 다르면 멈춰요 (조용히 넘어가지 않아요)."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        raise SystemExit(f"!! BAEPSAE_BUILD 는 40자리 커밋이어야 해요: {sha!r}")
    if f'name="{NAME}"' in html:
        raise SystemExit("!! 이미 빌드 표시가 있어요")
    i, head = html.find(CHARSET), html.find("</head>")
    if i < 0 or head < 0 or i > head:
        raise SystemExit(f"!! <head> 안에 {CHARSET} 가 없어요")
    j = i + len(CHARSET)
    return html[:j] + f'\n<meta name="{NAME}" content="{sha}">' + html[j:]


def main(paths):
    sha = os.environ.get("BAEPSAE_BUILD", "")
    if not sha:
        return 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            html = f.read()
        out = tag(html, sha)
        with open(p, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"· 빌드 표시 {sha[:7]} → {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
