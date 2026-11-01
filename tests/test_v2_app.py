# -*- coding: utf-8 -*-
"""뱁새 2.0 (app.html · app-preview.html, v18.3 Part A) 검사.

- 2.0 코드(src/v2/)에는 한국어가 없어요 (주석 제외): 화면 문구는 모두 src/copy/v2.js 에서 와요
- src/copy/v2.js 의 한국어는 모두 승인된 출처에서 왔어요 (목업 CSV 최종 문구 · New strings 표 · 고정 문구 · v17.5 승인 문구)
- 승인을 기다리는 문구(null)는 모두 docs/tasks/v18.3-new-strings-pending.md 에 있어요
- 아직 없는 기능(Part C 매일 점검)을 약속하는 문구는 빠져 있어요
- app.html 은 커밋하지 않아요 (v17.5.1 필드가 실제 데이터에 들어온 뒤에). 테스트는 임시로 빌드해서 봐요
- app-preview.html 은 소스와 같고(빌드를 잊지 않음), noindex, 데이터 파일을 받지 않고, 어디에서도 링크하지 않아요
- 두 페이지 모두 시험용 데이터(tests/fixtures)를 읽지 않고, 다른 사이트에서 아무것도 받지 않아요
- 지금 앱(baepsae.html 의 번들)은 2.0 코드를 가져오지 않아요
"""
import json
import os
import re
import subprocess
import tempfile

from copytrace import ROOT, HANGUL, Matcher, sources, copy_strings, read, V175, SPEC_QUOTES, DERIVED, csv_final
from buildapp import built

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍]")
WHOLE_BAD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")
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
    assert any(f.endswith("main.jsx") for f in files) and any(f.endswith("main-preview.jsx") for f in files), files
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
    stray = [(p, v) for p, v in ko if v not in DERIVED and not ok(v)]
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


def test_no_promise_of_the_daily_check_before_part_c():
    """Part C(매일 점검)가 없는 동안에는 '내일부터 … 점검해 드릴게요' · '매일 이 규칙으로 점검하고' 를 보여 주지 않아요."""
    c, flat = copy_strings()
    assert c["plan"]["doneBody"] is None and c["plan"]["rules"]["intro"] is None
    for p, v in flat:
        if isinstance(v, str):
            assert "점검해 드릴" not in v and "매일 이 규칙으로" not in v, (p, v)
    for name in ("app.html", "app-preview.html"):
        html = built(name)
        assert "점검해 드릴" not in html and "매일 이 규칙으로" not in html, name


def test_app_html_is_not_committed_yet():
    tracked = subprocess.run(["git", "ls-files", "app.html"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert tracked == "", "app.html 은 v17.5.1 필드가 실제 데이터에 들어온 뒤에 커밋해요 (v18.3 머지 조건)"
    assert "/app.html" in read(".gitignore")


def test_built_pages_have_title_noindex_and_the_right_service_worker():
    app, prev = built("app.html"), built("app-preview.html")
    for h in (app, prev):
        assert "<title>뱁새 2.0 미리 보기</title>" in h
        assert '<meta name="robots" content="noindex' in h
        assert 'href="fonts/pretendard/pretendard-variable.css"' in h
    assert 'navigator.serviceWorker.register("./sw.js")' in app
    assert "serviceWorker" not in prev                     # 미리 보기는 서비스워커를 등록하지 않아요


def test_preview_is_current_and_embeds_its_data():
    assert read("app-preview.html") == built("app-preview.html"), "app-preview.html 이 소스와 달라요: bash build-app.sh 를 다시 하세요"
    prev, app = built("app-preview.html"), built("app.html")
    fic = json.loads(read("src/preview/fictional.json"))
    names = [s["nk"] for s in fic["data"]["stocks"]]
    assert all(n in prev for n in names[:20]) and not any(n in app for n in names[:20]), "예시 데이터는 미리 보기에만 들어가요"
    assert "./data.json" not in prev and "./corp.json" not in prev and "./macro.json" not in prev
    assert "./data.json" in app and "./corp.json" in app and "./macro.json" in app
    assert "baepsae2.preview.v1" in prev and "baepsae2.v1" in app


def test_preview_is_linked_from_nowhere():
    pages = ["baepsae.html", "index.html", "template.html", "styleguide.html", "sw.js", "manifest.webmanifest",
             "styleguide/template.html", "styleguide/main.jsx", "styleguide/examples.js", "src/v2/template.html"]
    for f in pages:
        assert "app-preview" not in read(f), f
    for f in v2_files():                                        # code without comments: no link, no navigation to it
        if f.endswith("main-preview.jsx"):
            continue
        body = read(f) if f.endswith(".html") else esbuild(f, "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic")
        assert "app-preview" not in body, f
    assert "app-preview" not in built("app.html")


def test_pages_never_load_fixtures_or_other_sites():
    for name in ("app.html", "app-preview.html"):
        html = built(name)
        assert "fixtures" not in html and "tests/" not in html, name
        urls = set(re.findall(r"https?://[\w.-]+", html))
        assert urls <= {"https://react.dev", "http://www.w3.org"}, (name, urls)      # w3.org = SVG namespace 이름
        assert "goatcounter.com" not in html and "googleapis" not in html, name   # data.js 의 window.goatcounter 확인은 요청이 아니에요
    src = read("src/v2/load.js")
    assert set(re.findall(r'"\./(\w+\.json)"', src)) == {"data.json", "corp.json", "macro.json"}


def test_old_app_bundle_does_not_include_v2():
    tmp = tempfile.mkdtemp()
    meta = os.path.join(tmp, "meta.json")
    esbuild("src/main.jsx", "--bundle", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8", f"--metafile={meta}",
            f"--outfile={os.path.join(tmp, 'app.js')}")
    with open(meta, encoding="utf-8") as f:
        inputs = list(json.load(f)["inputs"])
    bad = [i for i in inputs if i.startswith(("src/v2/", "src/copy/", "src/preview/"))]
    assert not bad, bad
    assert "app.html" not in read("baepsae.html") and "app.html" not in read("index.html")


def test_build_script_builds_both_pages():
    sh = read("build-app.sh")
    assert "set -euo pipefail" in sh and "src/v2/main.jsx" in sh and "src/v2/main-preview.jsx" in sh
    assert '"app.html"' in sh and '"app-preview.html"' in sh
    assert "build.sh" not in sh.replace("build.sh)", "").replace("build-app.sh", "")   # 지금 앱 빌드는 건드리지 않아요
