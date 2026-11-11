# -*- coding: utf-8 -*-
"""2026-11-11 (Jack): 배포는 사이트가 읽지 않는 개발용 폴더 · 파일을 올리지 않아요 (tools/assemble_site.py NOT_SITE_DIRS · NOT_SITE_FILES).
tests/ 의 시험용 데이터(tests/fixtures/v2/data.json 등)가 사이트에 올라가 있었어요 — 진짜 data.json 과 헷갈릴 수 있어요.

- tests/ · tools/ · data/ · styleguide/ 와 맨 위의 개발용 파일은 사이트 목록에 없어요. 규칙이 깨져 들어가면 배포가 멈춰요.
- 사이트가 읽는 것은 그대로 올라가요: 페이지 · 서비스워커 · 매니페스트와 그 안의 주소, 글꼴, 그림, 아이콘, 스모크 테스트가 사이트로
  띄우는 파일. (그래서 읽는 파일을 실수로 목록에 넣으면 여기서 걸려요.)
"""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import assemble_site as AS  # noqa: E402

PAGES = ("index.html", "baepsae.html", "app.html", "app-preview.html", "styleguide.html")
SERVED = PAGES + ("sw.js", "manifest.webmanifest")
LIVE = ("data.json", "corp.json", "disc.json", "macro.json")
# 따옴표(" ' `) 안의 같은 사이트 주소. 묶은 앱은 src:"pictures/x.webp" · loadJson("./x.json") 처럼 쓰기 때문에 (리뷰 2026-11-12)
# href= · fetch( 같은 앞말을 보지 않고, 따옴표 안의 글자만 봐요. 앞의 ./ · / · ../ · /baepsae/ · 사이트 주소, 뒤의 ?… · #… 는 떼요.
SITE_PREFIX = r"""["'`](?:https://jacksungjinlee\.github\.io)?(?:\.{0,2}/|/baepsae/)?"""
LITERAL = re.compile(SITE_PREFIX + r"""([A-Za-z0-9_\-./]+\.[A-Za-z0-9]{2,11})(?:[?#][^"'`\s]*)?["'`]""")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def published():
    return AS.site_files(AS.tracked(ROOT))


def test_development_folders_and_files_are_not_published():
    paths = ["baepsae.html", "app.html", "sw.js", "src/a.js", "fonts/x.woff2", "vendor/phosphor/LICENSE",
             "tests/smoke_app.py", "tests/fixtures/v2/data.json", "Tests/x.json", "tools/assemble_site.py", "data/industry_map.csv",
             "styleguide/main.jsx", "CLAUDE.md", "README.md", "template.html", "fetch_data.py", "validate_data.py", "watchdog.py",
             "already_published.py", "build.sh", "build-app.sh", "build-styleguide.sh", "package.json", "package-lock.json",
             "requirements.txt", "requirements-dev.txt",
             "x/tests/y.js", "tests.js", "data.js", "src/template.html", "pictures/CLAUDE.md"]
    assert AS.site_files(paths) == ["baepsae.html", "app.html", "sw.js", "src/a.js", "fonts/x.woff2", "vendor/phosphor/LICENSE",
                                    "x/tests/y.js", "tests.js", "data.js", "src/template.html", "pictures/CLAUDE.md"]   # 맨 위의 것만 빠져요
    real = published()
    tops = {p.split("/", 1)[0].lower() for p in real if "/" in p}
    assert not tops & set(AS.NOT_SITE_DIRS), tops & set(AS.NOT_SITE_DIRS)
    assert not [p for p in real if p in AS.NOT_SITE_FILES]
    assert "tests" in AS.NOT_SITE_DIRS                                   # 시험용 데이터는 사이트의 데이터가 아니에요
    # 대소문자만 다른 파일 이름도 빠져요 (폴더와 같은 규칙) · 목록의 파일과 이름이 같은 폴더는 파일이 아니라 그대로예요
    assert AS.site_files(["readme.md", "Claude.md", "Template.html", "PACKAGE.JSON", "Tools/a.py", "DATA/a.csv", "StyleGuide/m.jsx",
                          "build.sh/x", "index.html"]) == ["build.sh/x", "index.html"]
    # 사이트에 올라가는 파일 가운데 이름이 data.json · corp.json · disc.json · macro.json 인 것은 없어요 (진짜 네 파일은 data 브랜치에서 와요)
    assert not [p for p in real if os.path.basename(p).lower() in LIVE], [p for p in real if os.path.basename(p).lower() in LIVE]


def literals(name):
    """사이트가 내보내는 파일 하나에서, 따옴표 안에 적힌 '저장소의 파일 이름' 모두."""
    tracked = set(AS.tracked(ROOT))
    return {m.group(1) for m in LITERAL.finditer(read(name)) if m.group(1) in tracked}


def test_everything_the_site_reads_is_still_published():
    real = set(published())
    need = set(SERVED)
    in_pages = set()
    for f in SERVED:                                                     # 페이지 · 서비스워커 · 매니페스트에 따옴표로 적힌 저장소 파일 전부
        in_pages |= literals(f)
    assert len(literals("app.html")) >= 30 and len(literals("baepsae.html")) >= 8, (len(literals("app.html")), len(literals("baepsae.html")))
    assert {"jack-photo.jpg", "baepi-mark.webp", "fonts/pretendard/pretendard-variable.css", "icon-192.png", "sw.js"} <= in_pages   # 묶은 앱 안의 주소까지 읽어요
    assert any(p.startswith("pictures/") for p in in_pages)
    need |= in_pages
    for icon in json.loads(read("manifest.webmanifest"))["icons"]:        # 홈 화면 아이콘
        need.add(icon["src"].lstrip("./"))
    sw = read("sw.js")
    names = re.search(r"const PICTURES = \[(.*?)\]", sw, re.S).group(1)
    need |= {f"pictures/{n}.webp" for n in re.findall(r'"([a-z0-9\-]+)"', names)}                    # 서비스워커가 미리 받는 그림
    import smoke_app                                                       # 스모크 테스트가 사이트로 띄우는 파일
    need |= {f for f in smoke_app.SITE_FILES if os.path.exists(os.path.join(ROOT, f))}
    # 이름을 이어 붙여 부르는 것("./baepi-" + n + ".png")은 글자로 찾을 수 없어요 → 글꼴 · 그림 폴더 전부와 뱁이 · 아이콘 파일 전부
    need |= {p for p in AS.tracked(ROOT) if p.split("/", 1)[0] in ("fonts", "pictures")}
    need |= {p for p in AS.tracked(ROOT) if re.fullmatch(r"(baepi-|icon-|apple-touch-icon|og-|jack-photo)[^/]*", p)}
    missing = sorted(n for n in need if n not in real and n not in LIVE)
    assert not missing, missing
    assert len(need) > 120 and all(not AS.not_site(n) for n in need)


def test_no_served_file_asks_for_a_development_path():
    """페이지 · 서비스워커 · 매니페스트에 개발용 폴더 · 파일을 가리키는 주소가 없어요: 따옴표(" ' `) 바로 뒤에 개발용 폴더로 시작하는 경로나
    개발용 파일 이름이 오는 곳이 하나도 없어요 (묶은 앱의 src:"…" · loadJson("…") · "./data/" + n 까지). 따옴표 없는 글(주석 · 설명)은 괜찮아요."""
    dirs = "|".join(AS.NOT_SITE_DIRS)
    files = "|".join(re.escape(f) for f in AS.NOT_SITE_FILES)
    url = re.compile(SITE_PREFIX + r"""(?:(?:%s)/|(?:%s)["'`?#])""" % (dirs, files), re.I)
    for f in SERVED:
        hit = url.search(read(f))
        assert not hit, (f, hit.group(0))
    for bad in ('<a href="./tests/x.json">', 'fetch("data/industry_map.csv")', "src='template.html'", 'src:"tools/x.png"',
                'href:"./tests/x.json"', 'vi("./data/x.csv")', 'loadJson("./tests/fixtures/v2/data.json",c)', "fetch(`./tools/x.json`)",
                '"./data/"+n+".csv"', 'href="README.md#x"', 'href="./package.json?v=2"', 'href="./Tests/x.json"',
                'fetch("/baepsae/tests/x.json")', 'new URL("../data/x.csv",location)',
                '"https://jacksungjinlee.github.io/baepsae/tests/smoke_app.py"'):
        assert url.search(bad), bad
    for fine in ('loadJson("./data.json",c)', 'src:"pictures/adobe-bank.webp"', "// tests/smoke_app.py 가 확인해요", 'x="metadata/x"',
                 'href="./app.html"', '"./logos/index.json"'):
        assert not url.search(fine), fine


def test_deploy_stops_if_a_development_path_gets_in_anyway(tmp_path, monkeypatch):
    """목록 규칙이 깨져 tests/ 나 개발용 파일이 사이트 폴더에 들어가면 조용히 올리지 않고 멈춰요 (docs/ 와 같은 방식)."""
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    work = tmp_path / "work"
    git = lambda *a: subprocess.run(["git", *a], cwd=work, check=True, capture_output=True, env=ENV)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True, capture_output=True, env=ENV)
    for f in LIVE:
        (work / f).write_text("{}")
    for rel in ("baepsae.html", "tests/fixtures/v2/data.json", "tools/a.py", "data/a.csv", "styleguide/m.jsx", "fetch_data.py", "CLAUDE.md",
                "src/a.js", "fonts/a.woff2"):
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text("x")
    git("add", "-A")
    git("commit", "-q", "-m", "main")
    out = tmp_path / "_site"
    AS.assemble(str(work), str(out), "HEAD")
    got = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    assert got == sorted(["baepsae.html", "src/a.js", "fonts/a.woff2", *LIVE])                          # 개발용은 없고 나머지는 그대로
    # 목록의 모든 폴더 · 파일 하나하나, 그리고 대소문자만 다른 것: 들어가면 그 이름을 대며 멈춰요
    leaks = [(d + "/a.x", d) for d in AS.NOT_SITE_DIRS] + [(f, f) for f in AS.NOT_SITE_FILES] + [("Tests/a.x", "Tests"), ("readme.md", "readme.md")]
    assert len(leaks) == len(AS.NOT_SITE_DIRS) + len(AS.NOT_SITE_FILES) + 2
    for i, (path, name) in enumerate(leaks):
        w = tmp_path / f"w{i}"
        subprocess.run(["git", "init", "-q", "-b", "main", str(w)], check=True, capture_output=True, env=ENV)
        for f in LIVE + ("baepsae.html", path):
            (w / f).parent.mkdir(parents=True, exist_ok=True)
            (w / f).write_text("{}")
        subprocess.run(["git", "add", "-A"], cwd=w, check=True, capture_output=True, env=ENV)
        subprocess.run(["git", "commit", "-q", "-m", "main"], cwd=w, check=True, capture_output=True, env=ENV)
        AS.assemble(str(w), str(tmp_path / f"ok{i}"), "HEAD")                                          # 규칙이 살아 있으면 빠져서 통과
        assert sorted(os.listdir(tmp_path / f"ok{i}")) == sorted(LIVE + ("baepsae.html",)), (path, os.listdir(tmp_path / f"ok{i}"))
        monkeypatch.setattr(AS, "site_files", lambda paths: [p for p in paths if p not in LIVE])     # 규칙이 깨진 경우
        with pytest.raises(SystemExit, match=f"개발용 폴더 · 파일이 들어갔어요: {re.escape(name)} → 배포하지 않아요"):
            AS.assemble(str(w), str(tmp_path / f"bad{i}"), "HEAD")
        monkeypatch.undo()
        for k, v in ENV.items():
            monkeypatch.setenv(k, v)
    # 목록의 파일과 이름이 같은 '폴더'는 개발용 파일이 아니에요: 그대로 올라가고 멈추지 않아요 (거르는 규칙과 멈추는 규칙이 같아요)
    w = tmp_path / "wdir"
    subprocess.run(["git", "init", "-q", "-b", "main", str(w)], check=True, capture_output=True, env=ENV)
    for f in LIVE + ("baepsae.html", "build.sh/x.txt"):
        (w / f).parent.mkdir(parents=True, exist_ok=True)
        (w / f).write_text("{}")
    subprocess.run(["git", "add", "-A"], cwd=w, check=True, capture_output=True, env=ENV)
    subprocess.run(["git", "commit", "-q", "-m", "main"], cwd=w, check=True, capture_output=True, env=ENV)
    AS.assemble(str(w), str(tmp_path / "okdir"), "HEAD")
    assert (tmp_path / "okdir" / "build.sh" / "x.txt").is_file()


def test_the_two_lists_only_name_things_that_exist_and_are_not_site_assets():
    tracked = AS.tracked(ROOT)
    for d in AS.NOT_SITE_DIRS:
        assert any(p.startswith(d + "/") for p in tracked), d            # 없는 이름을 적어 두지 않아요
        assert d == d.lower() and d not in ("fonts", "pictures", "logos", "src", "vendor", "docs")
    for f in AS.NOT_SITE_FILES:
        assert f in tracked and "/" not in f, f
        assert not f.endswith((".png", ".webp", ".jpg", ".webmanifest", ".woff2", ".json")) or f.startswith("package"), f
        assert f not in PAGES + ("sw.js",) + LIVE
