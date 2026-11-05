# -*- coding: utf-8 -*-
"""뱁새 2.0 (app.html · app-preview.html, v18.3 Part A) 검사.

- 2.0 코드(src/v2/)에는 한국어가 없어요 (주석 제외): 화면 문구는 모두 src/copy/v2.js 에서 와요
- src/copy/v2.js 의 한국어는 모두 승인된 출처에서 왔어요 (목업 CSV 최종 문구 · New strings 표 · 고정 문구 · v17.5 승인 문구)
- 승인을 기다리는 문구(null)는 모두 docs/tasks/v18.3-new-strings-pending.md 에 있어요
- 매일 점검을 약속하는 문구는 오늘 화면이 점검할 때만(Part E), 아직 없는 규칙 고치기를 약속하는 문구는 빠져 있어요
- app.html 은 메인 주소가 보여 주는 페이지예요 (Part F, Jack 2026-11-01): 커밋한 파일이 지금 소스로 새로 빌드한 것과 같아요.
  <head> 의 설명·공유 카드 태그와 GoatCounter 는 지금 앱(template.html)과 같고, noindex 가 아니에요
- app-preview.html 은 소스와 같고(빌드를 잊지 않음), noindex, 데이터 파일을 받지 않고, 어디에서도 링크하지 않아요
- 두 페이지 모두 시험용 데이터(tests/fixtures)를 읽지 않고, 다른 사이트에서 아무것도 받지 않아요
- 지금 앱(baepsae.html 의 번들)은 2.0 코드를 가져오지 않아요
"""
import json
import os
import re
import subprocess
import tempfile

from copytrace import ROOT, HANGUL, Matcher, sources, copy_strings, read, V175, SPEC_QUOTES, DERIVED, csv_final, chat_approved
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


def test_chat_approved_strings_are_used_word_for_word():
    """Jack 이 채팅에서 승인한 문구는 그 키에 한 글자도 다르지 않게 들어가요 (비슷하게 고친 문구가 '승인'으로 지나가지 않게)."""
    _, flat = copy_strings()
    vals = dict(flat)
    for key, text in chat_approved().items():
        assert vals.get(key) == text, (key, vals.get(key), text)
    # 안내 문구가 가리키는 머리말 링크 이름이 실제 링크 문구와 같아요 (링크 이름이 바뀌면 여기서 걸려요)
    assert f"'{vals['app.oldApp']}'" in vals["app.oldAppNote"]


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


def test_the_daily_check_promise_comes_only_with_the_daily_check():
    """Part E: 홈(v19.0c 전에는 '오늘 화면')이 매일 점검해요. 기록했어요의 약속(CSV 564 '내일부터 오늘 화면에서 {n}종목을 …')은
    v19.0c 에서 '오늘 화면'이 홈이 되어 바뀌어야 해서 Jack 의 승인을 기다려요: 그동안 값은 null 이고, 승인 대기 문서에 CSV 564 를
    그대로 고친 제안('오늘 화면에서' → '홈에서', PC 에서도 맞게 '이 휴대폰에만' → '이 기기에만')이 있고, 화면에는 그 약속도 '오늘 화면'
    이라는 말도 없어요. 승인되면 승인 표의 문구 그대로이고(test_chat_approved_strings_are_used_word_for_word), 두 페이지에 그 약속이
    나와요. 어느 쪽이든 그 약속을 지키는 홈 판정 띠의 문구가 모두 있어요(빈 값 아님 · 화면 동작은 tests/smoke_v2.py).
    규칙 고치기는 아직 없으니 '매일 이 규칙으로 점검하고, 규칙은 언제든 고칠 수 있어요'(CSV 534)는 여전히 보여 주지 않아요.
    (v19.0c 전에는 doneBody == CSV 564 를 바로 봤어요: 그 문장의 '오늘 화면'이 이제 없는 화면이라 위처럼 바꿨어요.)"""
    c, flat = copy_strings()
    proposal = csv_final()[564].replace("6종목", "{n}종목").replace("오늘 화면에서", "홈에서").replace("이 휴대폰에만", "이 기기에만")
    assert proposal == "내일부터 홈에서 {n}종목을 규칙대로 점검해 드릴게요. 기록은 이 기기에만 저장돼요.", proposal
    body = c["plan"]["doneBody"]
    assert body == proposal == chat_approved()["plan.doneBody"] and "홈에서" in body, body      # Jack, 2026-11-04 승인
    for k in ("todoN", "calmEyebrow", "calmTitle", "brokenTitle", "stale"):
        assert c["today"][k], k
    today = read("src/v2/today.jsx")
    assert "evaluateAll" in today and "today-hero" in today
    assert c["plan"]["rules"]["intro"] is None
    for p, v in flat:
        if isinstance(v, str):
            assert "매일 이 규칙으로" not in v and "언제든 고칠 수" not in v and "오늘 화면" not in v, (p, v)
    for name in ("app.html", "app-preview.html"):
        html = built(name)
        assert "매일 이 규칙으로" not in html and "언제든 고칠 수" not in html and "오늘 화면" not in html, name
        assert "점검해 드릴게요" in html, name


def test_app_html_is_committed_and_current():
    """메인 주소가 여는 페이지라 커밋해요. 손으로 고치지 않았는지: 커밋한 파일 = 지금 소스로 새로 빌드한 것 (스타일 페이지 검사와 같아요)."""
    assert "/app.html" not in read(".gitignore")
    assert read("app.html") == built("app.html"), "app.html 이 소스와 달라요: bash build-app.sh 를 다시 하세요"


def test_built_pages_have_title_noindex_and_the_right_service_worker():
    app, prev = built("app.html"), built("app-preview.html")
    # v19.0 Part E (Jack, 2026-11-03): 제목은 '뱁새 — 내 기준으로 만드는 포트폴리오' (예전 '뱁새 2.0 미리 보기')
    assert "<title>뱁새 — 내 기준으로 만드는 포트폴리오</title>" in app and app.count("<title>") == 1
    assert "<title>뱁새 — 내 기준으로 만드는 포트폴리오 · 예시 데이터</title>" in prev and prev.count("<title>") == 1   # 미리 보기 탭 제목에도 예시 데이터
    assert "미리 보기</title>" not in app + prev
    assert "noindex" not in app and '<meta name="robots" content="noindex, nofollow">' in prev   # 메인은 검색에 나와요
    for h in (app, prev):
        assert 'href="fonts/pretendard/pretendard-variable.css"' in h
    assert 'navigator.serviceWorker.register("./sw.js")' in app
    assert "serviceWorker" not in prev                     # 미리 보기는 서비스워커를 등록하지 않아요


def test_live_head_reuses_the_current_apps_meta_and_goatcounter():
    """설명·og·twitter 태그는 지금 앱(template.html)의 승인 문구 그대로, og:url 은 메인 주소. GoatCounter 는 app.html 에만."""
    old = read("template.html")
    meta = [l for l in old.splitlines() if re.match(r'<meta (name="description"|property="og:|name="twitter:)', l)]
    assert len(meta) >= 12
    app, prev = built("app.html"), built("app-preview.html")
    for l in meta:
        assert l in app, l
        assert l not in prev, l
    assert '<meta property="og:url" content="https://jacksungjinlee.github.io/baepsae/">' in app
    gc = re.findall(r"<script>\n\(function\(\)\{try\{\n  var q=new URLSearchParams.*?</script>", old, flags=re.S)
    assert len(gc) == 1 and gc[0] in app and "goatcounter" not in prev and "gc.zgo.at" not in prev


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


# app.html: 지금 앱과 같은 GoatCounter(gc.zgo.at)와 공유 카드 주소만. app-preview.html: 바깥 주소 없음.
# react.dev 오류 안내 주소와 w3.org(SVG namespace 이름)는 문자열일 뿐 요청하지 않아요.
# LinkedIn(v19.0 소개 페이지, about.md): Jack 의 프로필 주소 하나만, 누르면 새 탭으로 여는 링크(href)로만 써요 — 아래에서 확인.
LINKEDIN = "https://www.linkedin.com/in/jacksungjinlee/"
OUTSIDE_ALLOWED = {"app.html": {"https://react.dev", "http://www.w3.org", "https://gc.zgo.at", "https://jacksungjinlee.github.io",
                                "https://www.linkedin.com"},
                   "app-preview.html": {"https://react.dev", "http://www.w3.org", "https://www.linkedin.com"}}


def outside_problems(name, html):
    """한 페이지에서 걸리는 것들의 목록 (빈 목록이면 통과): 시험용 데이터 · 허용 밖 주소 · LinkedIn 주소 · 글꼴 CDN."""
    bad = []
    if "fixtures" in html or "tests/" in html:
        bad.append("fixtures")
    extra = set(re.findall(r"https?://[\w.-]+", html)) - OUTSIDE_ALLOWED[name]
    if extra:
        bad.append(("urls", sorted(extra)))
    if re.findall(r"https?://(?:www\.)?linkedin\.com[^\s\"'`]*", html) != [LINKEDIN]:          # 그 주소 하나, 한 번만
        bad.append("linkedin")
    if "googleapis" in html or "jsdelivr" in html:
        bad.append("cdn")
    return bad


def test_pages_never_load_fixtures_or_other_sites():
    for name in ("app.html", "app-preview.html"):
        bad = outside_problems(name, built(name))
        assert not bad, (name, bad)
    # 그 주소는 문구 파일(C.about.linkedInUrl)에만 있고, 화면 코드는 그 값을 <a href> 로만 써요 (새 탭 · noopener)
    c, _ = copy_strings()
    assert c["about"]["linkedInUrl"] == LINKEDIN
    about = read("src/v2/about.jsx")
    assert about.count("C.about.linkedInUrl") == 1 and 'href={C.about.linkedInUrl} target="_blank" rel="noopener"' in about
    for f in v2_files():
        assert "linkedin.com" not in read(f), f
    assert "goatcounter.com" not in built("app-preview.html")
    src = read("src/v2/load.js")
    assert set(re.findall(r'"\./(\w+\.json)"', src)) == {"data.json", "corp.json", "macro.json"}


def test_outside_check_catches_each_problem():
    """위 검사가 두 페이지 모두에서 정말 걸러내는지: 글꼴 CDN(주소 앞 https: 없이도) · 다른 사이트 · 시험용 데이터 · LinkedIn 두 번."""
    for name in ("app.html", "app-preview.html"):
        html = built(name)
        assert outside_problems(name, html) == []
        cases = [(html + '<link href="//fonts.googleapis.com/css2">', "cdn"), (html + '<script src="//cdn.jsdelivr.net/x.js">', "cdn"),
                 (html + '<img src="https://example.com/x.png">', "urls"), (html + "fetch('./tests/fixtures/v2/data.json')", "fixtures"),
                 (html + f'<a href="{LINKEDIN}">', "linkedin")]
        if name == "app-preview.html":
            cases.append((html + '<script src="https://gc.zgo.at/count.js">', "urls"))       # 미리 보기에는 통계도 없어요
        for mutated, want in cases:
            got = [b if isinstance(b, str) else b[0] for b in outside_problems(name, mutated)]
            assert want in got, (name, want, got)


def test_old_app_bundle_does_not_include_v2():
    tmp = tempfile.mkdtemp()
    meta = os.path.join(tmp, "meta.json")
    esbuild("src/main.jsx", "--bundle", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8", f"--metafile={meta}",
            f"--outfile={os.path.join(tmp, 'app.js')}")
    with open(meta, encoding="utf-8") as f:
        inputs = list(json.load(f)["inputs"])
    bad = [i for i in inputs if i.startswith(("src/v2/", "src/copy/", "src/preview/"))]
    assert not bad, bad
    # 지금 앱이 2.0 을 가리키는 곳은 두 가지예요. 2.0 코드는 가져오지 않아요(위).
    #   머리말의 '뱁새 2.0 보기' 링크 (Jack, 2026-11-02) — ./app.html
    #   푸터의 '소개' 링크 (v19.0, Jack 2026-11-03) — ./app.html#about, src/links.js 의 상수 하나 (번들에 한 번)
    old = read("baepsae.html")
    # CV 링크 (Jack, 2026-11-05): template.html 의 첫 스크립트가 표시 없는 방문을 2.0 으로 보내요 (location.replace 한 번, tests/test_cv_link.py).
    # 번들은 그대로 두 군데예요.
    tpl = read("template.html")
    assert tpl.count("app.html") == 1 and tpl.count('L.replace("./app.html"') == 1, tpl.count("app.html")
    assert old.count("app.html") == 2 + tpl.count("app.html"), old.count("app.html")
    assert old.count('href:"./app.html","data-v2-link":"1"') == 1 and old.count('"./app.html#about"') == 1, "app.html 링크 모양이 달라요"
    assert "뱁새 2.0 보기" in read("src/shell.jsx") and "뱁새 2.0 보기" in old
    assert read("src/links.js").count('"./app.html#about"') == 1
    srcs = [f for f in os.listdir(os.path.join(ROOT, "src")) if f.endswith((".js", ".jsx"))]
    assert [f for f in srcs if "app.html#about" in read(os.path.join("src", f))] == ["links.js"], "소개 주소는 src/links.js 에만"


def test_build_script_builds_both_pages():
    sh = read("build-app.sh")
    assert "set -euo pipefail" in sh and "src/v2/main.jsx" in sh and "src/v2/main-preview.jsx" in sh
    assert '"app.html"' in sh and '"app-preview.html"' in sh
    assert "build.sh" not in sh.replace("build.sh)", "").replace("build-app.sh", "")   # 지금 앱 빌드는 건드리지 않아요


def test_home_screen_icon_opens_2_0():
    """Jack, 2026-11-02: 홈 화면 아이콘은 Part E 와 함께 2.0 으로. manifest 의 start_url 은 ./app.html, app.html 에는
    template.html 의 manifest · 아이콘 · iOS 홈 화면 태그가 그대로, 미리 보기에는 하나도 없어요. 지금 앱(baepsae.html)은 그대로예요."""
    m = json.loads(read("manifest.webmanifest"))
    assert m["start_url"] == "./app.html" and m["scope"] == "./" and m["display"] == "standalone", m
    # Jack, 2026-11-02: 이미 설치한 안드로이드 아이콘도 2.0 으로. 예전 manifest 에는 id 가 없어서 설치된 앱의 정체는
    # 예전 start_url(./baepsae.html)을 manifest 주소 기준으로 푼 주소예요. 새 id 는 manifest 규격대로 start_url 의
    # origin(사이트 맨 위) 기준으로 풀어요: "./baepsae.html" 은 https://…github.io/baepsae.html 이 돼서 다른 앱이 돼요.
    from urllib.parse import urljoin, urlsplit
    manifest_url = "https://jacksungjinlee.github.io/baepsae/manifest.webmanifest"
    start = urljoin(manifest_url, m["start_url"])
    assert start == "https://jacksungjinlee.github.io/baepsae/app.html", start
    origin = "{0.scheme}://{0.netloc}/".format(urlsplit(start))
    old_identity = urljoin(manifest_url, "./baepsae.html")          # 예전 start_url (id 없음 → start_url 이 정체)
    assert urljoin(origin, m["id"]) == old_identity == "https://jacksungjinlee.github.io/baepsae/baepsae.html", m["id"]
    assert all(os.path.exists(os.path.join(ROOT, i["src"])) for i in m["icons"])
    old = read("template.html")
    tags = [l for l in old.splitlines() if re.match(r'<link rel="(manifest|icon|apple-touch-icon)"|<meta name="apple-mobile-web-app-', l)]
    assert '<link rel="manifest" href="./manifest.webmanifest">' in tags and any("apple-touch-icon" in l for l in tags), tags
    app, prev = built("app.html"), built("app-preview.html")
    head = app.split("</head>", 1)[0]
    for l in tags:
        assert l in head, l
    for needle in ('rel="manifest"', "apple-touch-icon", 'rel="icon"', "apple-mobile-web-app"):
        assert needle not in prev, needle
    assert '<link rel="manifest" href="./manifest.webmanifest">' in read("baepsae.html")      # 같은 manifest: 어디서 설치해도 2.0


def test_the_stable_card_names_no_single_ratio():
    """재무 안정 카드는 한국(부채비율)과 미국(차입금 비율)을 함께 줄 세워서 '부채 부담 낮은 순'이에요 (Jack, 2026-11-02, CSV 223 대신).
    두 페이지 어디에도 '부채비율 낮은 순'이 없고, 미국 근거 수치는 차입금 비율이에요."""
    c, _ = copy_strings()
    assert c["build"]["cards"]["stable"]["basis"] == "부채 부담 낮은 순"
    assert c["pick"]["receipt"]["debtUs"].startswith("차입금 비율") and c["pick"]["receipt"]["debt"] == "부채비율"
    for name in ("app.html", "app-preview.html"):
        assert "부채비율 낮은 순" not in built(name), name
