# -*- coding: utf-8 -*-
"""v19.6a 새 파일은 색을 직접 쓰지 않아요 (Jack, 2026-11-13).

새 화면과 부품은 공통 색 설정(src/ui/tokens.js 의 COLOR · CHART · ICON_TONE …)만 써요. 그래야 어두운 화면(v19.6d)이 이 화면들도
저절로 덮어요. 이 검사는 v19.6a 가 더한 파일의 코드(주석은 빼고: esbuild 로 줄인 글)에 #fff · #ffffff 같은 16진 색, rgb( · rgba( ·
hsl( · hsla(, 그리고 이름으로 쓴 색(white · black · transparent …)이 없는지 봐요. 필요한 색이 토큰에 없으면 tokens.js 에 더해요.
"""
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# v19.6a 가 더한 파일 (기록 · 내 수익 · 판 기록 계산 · 기록 내려받기)
NEW_FILES = ["src/v2/records.jsx", "src/v2/returns.jsx", "src/v2/records.js", "src/v2/lots.js", "src/v2/csv.js"]
HEX = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_])")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(", re.I)
NAMED = re.compile(r"""["'`](?:white|black|red|blue|green|gray|grey|silver|navy|orange|yellow|purple|transparent|currentcolor)["'`]""", re.I)


def minified(path):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    if not os.path.exists(exe):
        pytest.skip("node_modules 가 없어요: npm ci 를 먼저 하세요")
    r = subprocess.run([exe, path, "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.mark.parametrize("path", NEW_FILES)
def test_no_literal_colour_in_new_v196a_files(path):
    assert os.path.exists(os.path.join(ROOT, path)), path
    code = minified(path)
    hits = HEX.findall(code) + FUNC.findall(code) + NAMED.findall(code)
    assert not hits, f"{path}: 색을 직접 썼어요 {hits[:5]} (src/ui/tokens.js 의 토큰으로)"


def test_the_check_catches_literal_colours():
    """검사 자체가 잡는지: 16진 · rgb( · 이름 색이 들어간 글은 걸려요."""
    for bad in ['style={{ color: "#1C2B45" }}', "background: 'rgba(28,43,69,0.45)'", 'borderColor: "transparent"', "fill: '#fff'"]:
        assert HEX.findall(bad) or FUNC.findall(bad) or NAMED.findall(bad), bad
    for ok in ["location.hash = '#portfolio'", "x.t + '#1'", "COLOR.ink"]:
        assert not (HEX.findall(ok) or FUNC.findall(ok) or NAMED.findall(ok)), ok
