# -*- coding: utf-8 -*-
"""뱁새 2.0 미리 보기 (app.html, v18.3 Part A) 검사.

- 2.0 코드(src/v2/)에는 한국어가 없어요 (주석 제외): 화면 문구는 모두 src/copy/v2.js 에서 와요
- src/copy/v2.js 의 한국어는 모두 승인된 출처에서 왔어요 (목업 CSV 최종 문구 · New strings 표 · 고정 문구 · v17.5 승인 문구)
- 승인을 기다리는 문구(null)는 모두 docs/tasks/v18.3-new-strings-pending.md 에 있어요
- app.html 이 소스와 같아요 (build-app.sh 를 잊지 않음), 제목은 '뱁새 2.0 미리 보기'
- app.html 은 시험용 데이터(tests/fixtures)를 읽지 않고, 다른 사이트에서 아무것도 받지 않아요
- 지금 앱(baepsae.html 의 번들)은 2.0 코드를 가져오지 않아요
"""
import json
import os
import re
import subprocess
import tempfile

import pytest

from copytrace import ROOT, HANGUL, Matcher, sources, copy_strings, read, V175, SPEC_QUOTES, DERIVED, csv_final

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍]")
WHOLE_BAD = re.compile(r"\b(nan|NaN|None|null|undefined)\b")
V2 = os.path.join(ROOT, "src", "v2")


def esbuild(*args):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    assert os.path.exists(exe), "node_modules 가 없어요: npm ci 를 먼저 하세요"
    r = subprocess.run([exe, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def v2_files():
    return sorted(os.path.join("src", "v2", f) for f in os.listdir(V2))


def test_no_hangul_in_v2_code_outside_the_copy_file():
    files = v2_files()
    assert any(f.endswith("main.jsx") for f in files) and len(files) >= 8, files
    for f in files:
        if f.endswith(".html"):
            body = read(f)
        else:
            body = esbuild(f, "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8")  # 주석이 빠져요
        hits = sorted(set(HANGUL.findall(body)))
        assert not hits, f"{f}: 코드 안 한국어 {hits[:10]} (문구는 src/copy/v2.js 로)"


def test_every_copy_string_comes_from_an_approved_source():
    ok = Matcher(sources())
    _, flat = copy_strings()
    ko = [(p, v) for p, v in flat if isinstance(v, str) and HANGUL.search(v)]
    assert len(ko) >= 150, len(ko)
    derived = {k for k in DERIVED}
    stray = [(p, v) for p, v in ko if v not in derived and not ok(v)]
    assert not stray, f"승인된 출처에 없는 문구: {stray}"


def test_named_sources_really_exist():
    detail = read("src/detail.jsx")
    for s, needles in V175.items():
        for n in needles:
            assert n in detail, f"v17.5 승인 문구라고 한 '{s}' 의 '{n}' 가 src/detail.jsx 에 없어요"
    for s, refs in SPEC_QUOTES.items():
        for f, n in refs:
            assert n in read(f), (s, f)
    rows = csv_final()
    for s, (row, sub) in DERIVED.items():
        assert sub in rows[row], (s, row)


def test_copy_has_no_emoji_banned_words_or_null_words():
    voice = read("docs/BAEPSAE_VOICE.md")
    banned = [w.strip() for w in voice.split("## 금지어", 1)[1].split("\n", 2)[1].split("·") if w.strip()]
    assert "잣대" in banned
    _, flat = copy_strings()
    for p, v in flat:
        if not isinstance(v, str):
            continue
        assert not EMOJI.search(v), (p, v)
        assert not any(w in v for w in banned), (p, v)
        assert not WHOLE_BAD.search(v), (p, v)


def test_pending_strings_are_parked_for_jack():
    _, flat = copy_strings()
    pending = [p for p, v in flat if v is None]
    assert pending, "승인을 기다리는 문구가 하나도 없다면 이 검사를 다시 보세요"
    doc = read("docs/tasks/v18.3-new-strings-pending.md")
    missing = [p for p in pending if f"`{p}`" not in doc]
    assert not missing, f"pending 문서에 없는 키: {missing}"


def build_app_html():
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "app.js")
    esbuild("src/v2/main.jsx", "--bundle", "--minify", "--loader:.jsx=jsx", "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8",
            "--define:process.env.NODE_ENV=\"production\"", f"--outfile={out}")
    with open(out, encoding="utf-8") as f:
        js = f.read()
    c, _ = copy_strings()
    return read("src/v2/template.html").replace("/*TITLE*/", c["app"]["title"]).replace("/*BUNDLE*/", js)


def test_app_html_is_current_and_titled():
    have = read("app.html")
    assert have == build_app_html(), "app.html 이 소스와 달라요: bash build-app.sh 를 다시 하세요"
    assert "<title>뱁새 2.0 미리 보기</title>" in have
    assert 'name="robots" content="noindex' in have
    assert 'href="fonts/pretendard/pretendard-variable.css"' in have


def test_app_never_loads_fixtures_or_other_sites():
    html = read("app.html")
    assert "fixtures" not in html and "tests/" not in html
    for f in ["app.html"] + v2_files():
        body = read(f)
        assert "fixtures" not in body, f
    # 데이터는 같은 사이트의 네 파일 중 셋만 (상대 경로)
    src = read("src/v2/load.js")
    assert set(re.findall(r'"\./(\w+\.json)"', src)) == {"data.json", "corp.json", "macro.json"}
    # 바깥 주소: 글꼴·통계·CDN 없음 (React 오류 안내 주소는 문자열일 뿐 요청하지 않아요)
    urls = set(re.findall(r"https?://[\w.-]+", html))
    assert urls <= {"https://react.dev", "http://www.w3.org"}, urls   # w3.org = SVG namespace 이름
    assert "goatcounter.com" not in html and "googleapis" not in html   # data.js 의 window.goatcounter 확인은 요청이 아니에요


def test_old_app_bundle_does_not_include_v2():
    tmp = tempfile.mkdtemp()
    meta = os.path.join(tmp, "meta.json")
    esbuild("src/main.jsx", "--bundle", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8", f"--metafile={meta}",
            f"--outfile={os.path.join(tmp, 'app.js')}")
    with open(meta, encoding="utf-8") as f:
        inputs = list(json.load(f)["inputs"])
    bad = [i for i in inputs if i.startswith(("src/v2/", "src/copy/"))]
    assert not bad, bad
    assert "app.html" not in read("baepsae.html") and "app.html" not in read("index.html")


def test_build_script_matches_the_style_page_pattern():
    sh = read("build-app.sh")
    assert "set -euo pipefail" in sh and "src/v2/main.jsx" in sh and "app.html" in sh
    assert "baepsae.html" not in sh.replace("baepsae.html, build.sh", "")    # 지금 앱은 건드리지 않아요
