# -*- coding: utf-8 -*-
"""홈 화면 아이콘 (v19.5a, Jack 2026-11-07): 페이지와 매니페스트가 가리키는 아이콘 파일이 정말 있어요.

app.html · baepsae.html (template.html 에서 만들어요) 의 <link rel="icon"> · <link rel="apple-touch-icon"> 과
manifest.webmanifest 의 icons 가 가리키는 파일마다: 저장소에 올라간(git) PNG 이고, 적어 둔 크기와 같아요. 파일이 빠지면
사이트는 조용히 404 를 내서(스모크 테스트는 자기 파일 목록만 써요) 여기서 잡아요. 아이폰 아이콘(apple-touch-icon)은
180 x 180 이고 투명한 곳이 없어요 (아이폰이 투명한 곳을 검게 칠해요).
"""
import json
import os
import re
import subprocess

import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ("template.html", "baepsae.html", "app.html")
LINK = re.compile(r'<link rel="(icon|apple-touch-icon)"([^>]*)>')


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def tracked(rel):
    r = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def local(href):
    assert href.startswith("./") and "/" not in href[2:] and ".." not in href, f"사이트 맨 위의 파일이 아니에요: {href}"
    return href[2:]


def png(rel):
    path = os.path.join(ROOT, rel)
    assert os.path.isfile(path), f"파일이 없어요: {rel}"
    assert tracked(rel), f"저장소에 올라가지 않은 파일이에요 (배포에 빠져요): {rel}"
    im = Image.open(path)
    assert im.format == "PNG", f"PNG 가 아니에요: {rel} ({im.format})"
    im.load()
    return im


def links(page):
    out = []
    for rel, attrs in LINK.findall(read(page)):
        href = re.search(r'href="([^"]+)"', attrs)
        sizes = re.search(r'sizes="(\d+)x(\d+)"', attrs)
        assert href, f"{page}: href 없는 {rel} 링크"
        out.append((rel, href.group(1), (int(sizes.group(1)), int(sizes.group(2))) if sizes else None))
    return out


@pytest.mark.parametrize("page", PAGES)
def test_page_icon_links_point_at_real_png_files(page):
    found = links(page)
    assert {r for r, _, _ in found} == {"icon", "apple-touch-icon"}, f"{page}: 아이콘 링크 {found}"
    for rel, href, size in found:
        im = png(local(href))
        if size:
            assert im.size == size, f"{page}: {href} 는 {im.size}, 적힌 크기는 {size}"
        if rel == "apple-touch-icon":
            assert im.size == (180, 180), f"{page}: 아이폰 아이콘은 180 x 180 이어야 해요 ({im.size})"
            alpha = im.getchannel("A").getextrema() if "A" in im.getbands() else (255, 255)
            assert im.mode in ("RGB", "RGBA", "P", "L") and alpha[0] == 255, f"{page}: 아이폰 아이콘에 투명한 곳이 있어요 ({href})"


def test_both_pages_use_the_same_icons_as_the_template():
    want = links("template.html")
    for page in ("baepsae.html", "app.html"):
        assert links(page) == want, f"{page} 의 아이콘 링크가 template.html 과 달라요 (bash build.sh · build-app.sh)"


def test_manifest_icons_are_real_png_files_of_their_sizes():
    m = json.loads(read("manifest.webmanifest"))
    icons = m["icons"]
    assert icons, "매니페스트에 아이콘이 없어요"
    purposes = set()
    for ic in icons:
        assert ic.get("type") == "image/png", ic
        w, h = (int(x) for x in ic["sizes"].split("x"))
        im = png(local(ic["src"]))
        assert im.size == (w, h), f"{ic['src']} 는 {im.size}, 매니페스트에는 {ic['sizes']}"
        purposes |= set(ic.get("purpose", "any").split())
    assert {"any", "maskable"} <= purposes, f"매니페스트에 any 와 maskable 아이콘이 다 있어야 해요 ({purposes})"
    assert any(ic["sizes"] == "512x512" and "any" in ic.get("purpose", "any").split() for ic in icons), \
        "안드로이드 설치에는 512 x 512 아이콘(any)이 필요해요"
