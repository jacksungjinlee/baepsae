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
LIVE = ("data.json", "corp.json", "disc.json", "macro.json")
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


def test_everything_the_site_reads_is_still_published():
    real = set(published())
    need = set(PAGES) | {"sw.js", "manifest.webmanifest"}
    for page in PAGES:                                                   # 페이지 안의 같은 사이트 주소 (./x · fonts/…)
        for m in re.finditer(r"""(?:href|src)=["'](\./)?([A-Za-z0-9_\-./]+\.(?:png|webp|jpg|css|webmanifest|html|js|woff2))["']""", read(page)):
            need.add(m.group(2))
    for icon in json.loads(read("manifest.webmanifest"))["icons"]:        # 홈 화면 아이콘
        need.add(icon["src"].lstrip("./"))
    sw = read("sw.js")
    names = re.search(r"const PICTURES = \[(.*?)\]", sw, re.S).group(1)
    need |= {f"pictures/{n}.webp" for n in re.findall(r'"([a-z0-9\-]+)"', names)}                    # 서비스워커가 미리 받는 그림
    import smoke_app, smoke_launch                                         # 스모크 테스트가 사이트로 띄우는 파일
    need |= {f for f in smoke_app.SITE_FILES if os.path.exists(os.path.join(ROOT, f))} | set(smoke_launch.SITE)
    need |= {p for p in AS.tracked(ROOT) if p.split("/", 1)[0] in ("fonts", "pictures")}              # 글꼴 · 그림 폴더 전부
    need |= {p for p in AS.tracked(ROOT) if re.fullmatch(r"(baepi-|icon-|apple-touch-icon|og-|jack-photo)[^/]*", p)}
    missing = sorted(n for n in need if n not in real and n not in LIVE)
    assert not missing, missing
    assert len(need) > 120 and all(not AS.not_site(n) for n in need)


def test_no_served_file_asks_for_a_development_path():
    """페이지 · 서비스워커 · 매니페스트에 개발용 폴더 · 파일을 가리키는 주소(href · src · fetch · import)가 없어요. 글 속의 이름(주석 · 설명)은 괜찮아요."""
    dirs = "|".join(AS.NOT_SITE_DIRS)
    files = "|".join(re.escape(f) for f in AS.NOT_SITE_FILES)
    url = re.compile(r"""(?:href|src)=["'](?:\./)?(?:(?:%s)/|(?:%s)["'])|(?:fetch|import|importScripts)\(\s*["'](?:\./)?(?:(?:%s)/|(?:%s)["'])"""
                     % (dirs, files, dirs, files))
    for f in PAGES + ("sw.js", "manifest.webmanifest"):
        hit = url.search(read(f))
        assert not hit, (f, hit.group(0))
    assert url.search('<a href="./tests/x.json">') and url.search('fetch("data/industry_map.csv")') and url.search("src='template.html'")


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
    for leak, name in ((lambda p: p.startswith("tests/"), "tests"), (lambda p: p == "fetch_data.py", "fetch_data.py")):
        monkeypatch.setattr(AS, "site_files", lambda paths, leak=leak: [p for p in paths if p not in LIVE and (leak(p) or not AS.not_site(p))])
        with pytest.raises(SystemExit, match=f"개발용 폴더 · 파일이 들어갔어요: {re.escape(name)}"):
            AS.assemble(str(work), str(tmp_path / f"_site_{name}"), "HEAD")


def test_the_two_lists_only_name_things_that_exist_and_are_not_site_assets():
    tracked = AS.tracked(ROOT)
    for d in AS.NOT_SITE_DIRS:
        assert any(p.startswith(d + "/") for p in tracked), d            # 없는 이름을 적어 두지 않아요
        assert d == d.lower() and d not in ("fonts", "pictures", "logos", "src", "vendor", "docs")
    for f in AS.NOT_SITE_FILES:
        assert f in tracked and "/" not in f, f
        assert not f.endswith((".png", ".webp", ".jpg", ".webmanifest", ".woff2", ".json")) or f.startswith("package"), f
        assert f not in PAGES + ("sw.js",) + LIVE
