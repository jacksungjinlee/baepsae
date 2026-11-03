# -*- coding: utf-8 -*-
"""v19.0 이름 · 캐치프레이즈 · 만든 사람 줄 (Jack, 2026-11-03; docs/tasks/v19.0-layout-c.md 수용 조건 5).

예전 이름("개인 투자 연구소"), 예전 캐치프레이즈("황새 말고, 내 걸음으로"와 그 영어), 만든 사람 줄("INSEAD MBA 26J")은
사용자가 여는 페이지(baepsae.html · app.html · app-preview.html · index.html · manifest)와 src/ · styleguide/ · tools/
(링크 미리 보기 그림을 그리는 render_og.py) 의 어떤 파일(주석 포함)에도 없어요.
만든 사람은 소개 페이지(#about)에만 있어요. 커밋한 페이지와, 지금 소스로 새로 빌드한 2.0 페이지를 모두 봐요
(baepsae.html 이 소스와 같은지는 test_launch.py, app.html · app-preview.html 은 test_v2_app.py 가 확인해요).
"""
import json
import os
import re

from buildapp import built
from copytrace import ROOT, read

GONE = ["개인 투자 연구소", "황새 말고, 내 걸음으로", "INSEAD MBA 26J", "Jack (Sung Jin) Lee, INSEAD MBA 26J",
        "Not the stork's pace", "At my own pace"]
PAGES = ["baepsae.html", "app.html", "app-preview.html", "index.html", "manifest.webmanifest",
         "template.html", "styleguide.html"]


def src_files():
    out = []
    for d in ("src", "styleguide", "tools"):
        for base, dirs, files in os.walk(os.path.join(ROOT, d)):
            dirs[:] = [x for x in dirs if x != "__pycache__"]            # 파이썬이 만든 캐시는 소스가 아니에요
            out += [os.path.relpath(os.path.join(base, f), ROOT) for f in files]
    return sorted(out)


def test_old_names_and_credit_are_gone_from_pages_and_sources():
    files = src_files()
    assert len(files) >= 40 and "src/links.js" in files and "src/v2/about.jsx" in files and "tools/render_og.py" in files, files[:5]
    found = []
    for f in PAGES + files:
        if f.endswith((".png", ".jpg", ".woff2")):                      # 그림·글꼴 파일에는 글이 없어요
            continue
        text = read(f)
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


# v19.0c (Jack, 2026-11-03: "덱" sounded like a card game) — 덱 → 포트폴리오 in every word users see. "인덱스" is fine.
DECK = re.compile(r"(?<!인)덱")
LEGACY_START, LEGACY_END = "// legacy-start", "// legacy-end"
DECK_PAGES = ["baepsae.html", "index.html", "manifest.webmanifest", "template.html", "src/v2/template.html"]


def legacy_values():
    """src/copy/v2.js 의 legacy 블록: v19.0c 전에 저장된 기본 이름을 맞춰 보는 두 값 (화면에는 나오지 않아요, src/v2/legacy.js)."""
    from copytrace import copy_strings
    c, _ = copy_strings()
    return [c["legacy"]["deckName"], c["legacy"]["myDeck"]]


def test_the_old_word_for_a_portfolio_is_gone():
    """'덱' 은 사용자가 여는 페이지와 src/ · tools/ 의 어떤 파일(주석 포함)에도 없어요. 하나뿐인 예외는 src/copy/v2.js 의 legacy
    블록(// legacy-start ~ // legacy-end, 두 값)이고, 빌드한 2.0 페이지에서도 그 두 값(각각 한 번)을 빼면 없어요.
    화면에 보이는 글에 없는지는 smoke_v2 · smoke_preview · smoke_launch 가 휴대폰 크기로 열어서 봐요."""
    legacy = legacy_values()
    assert legacy == ["{name} 덱", "내 덱"], legacy
    found = []
    files = [f for f in src_files() if f.startswith(("src/", "tools/")) and not f.endswith((".png", ".jpg", ".woff2"))]
    assert "src/copy/v2.js" in files and "src/v2/legacy.js" in files and "src/v2/nav.jsx" in files, files[:5]
    for f in DECK_PAGES + files:
        text = read(f)
        if f == "src/copy/v2.js":
            assert text.count(LEGACY_START) == 1 and text.count(LEGACY_END) == 1, "legacy 블록 표시가 하나씩이어야 해요"
            head, rest = text.split(LEGACY_START, 1)
            block, tail = rest.split(LEGACY_END, 1)
            assert len(block.strip().splitlines()) == 1 and "legacy:" in block, block   # 블록은 legacy 한 줄뿐
            text = head + tail
        found += [(f, m.start()) for m in DECK.finditer(text)]
    for name in ("app.html", "app-preview.html"):                    # 커밋한 것과 지금 소스로 새로 빌드한 것: 두 값을 빼면 없어요
        for tag, html in (("", read(name)), ("built ", built(name))):
            for v in legacy:
                q = json.dumps(v, ensure_ascii=False)
                assert html.count(q) == 1, (tag + name, v, html.count(q))
                html = html.replace(q, "")
            found += [(tag + name, html[max(0, m.start() - 30):m.start() + 10]) for m in DECK.finditer(html)]
    assert not found, found
    from copytrace import copy_strings
    _, flat = copy_strings()
    stray = [(p, v) for p, v in flat if isinstance(v, str) and DECK.search(v) and not p.startswith("legacy.")]
    assert not stray, stray
