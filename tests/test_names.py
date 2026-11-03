# -*- coding: utf-8 -*-
"""v19.0 이름 · 캐치프레이즈 · 만든 사람 줄 (Jack, 2026-11-03; docs/tasks/v19.0-layout-c.md 수용 조건 5).

예전 이름("개인 투자 연구소"), 예전 캐치프레이즈("황새 말고, 내 걸음으로"와 그 영어), 만든 사람 줄("INSEAD MBA 26J")은
사용자가 여는 페이지(baepsae.html · app.html · app-preview.html · index.html · manifest)와 src/ 의 어떤 파일(주석 포함)에도 없어요.
만든 사람은 소개 페이지(#about)에만 있어요. 커밋한 페이지와, 지금 소스로 새로 빌드한 2.0 페이지를 모두 봐요
(baepsae.html 이 소스와 같은지는 test_launch.py, app.html · app-preview.html 은 test_v2_app.py 가 확인해요).
"""
import os

from buildapp import built
from copytrace import ROOT, read

GONE = ["개인 투자 연구소", "황새 말고, 내 걸음으로", "INSEAD MBA 26J", "Jack (Sung Jin) Lee, INSEAD MBA 26J",
        "Not the stork's pace", "At my own pace"]
PAGES = ["baepsae.html", "app.html", "app-preview.html", "index.html", "manifest.webmanifest",
         "template.html", "styleguide.html"]


def src_files():
    out = []
    for d in ("src", "styleguide"):
        for base, _, files in os.walk(os.path.join(ROOT, d)):
            out += [os.path.relpath(os.path.join(base, f), ROOT) for f in files]
    return sorted(out)


def test_old_names_and_credit_are_gone_from_pages_and_sources():
    files = src_files()
    assert len(files) >= 40 and "src/links.js" in files and "src/v2/about.jsx" in files, files[:5]
    found = []
    for f in PAGES + files:
        text = read(f) if not f.endswith((".png", ".jpg", ".woff2")) else ""
        found += [(f, w) for w in GONE if w in text]
    for name in ("app.html", "app-preview.html"):                      # 지금 소스로 새로 빌드한 것도
        found += [("built " + name, w) for w in GONE if w in built(name)]
    assert not found, found


def test_new_title_and_catchphrase_are_in_place():
    title, catch = "뱁새 — 내 기준으로 만드는 포트폴리오", "철새처럼 옮겨 다니지 않는 투자"
    for f in ("template.html", "index.html", "baepsae.html"):
        h = read(f)
        assert f"<title>{title}</title>" in h, f
        assert f'<meta property="og:title" content="{title}">' in h and f'<meta name="twitter:title" content="{title}">' in h, f
    assert f"<title>{title}</title>" in built("app.html")
    assert f'"name": "{title}"' in read("manifest.webmanifest")
    for f in ("src/shell.jsx", "src/detail.jsx", "src/info.jsx", "src/sharecard.js"):
        assert catch in read(f), f
    old = read("baepsae.html")
    assert old.count(catch) >= 3 and "Don't hop from trend to trend" in old
