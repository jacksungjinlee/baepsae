# -*- coding: utf-8 -*-
"""2026-11-11 (Jack): 예전 뱁새 스모크 테스트(tests/smoke_app.py)는 그날그날의 발행 파일이 아니라 고정 데이터로 돌아요.
PR 의 CI 결과가 그날 아침 발행에 흔들리지 않게요. 여기서 확인하는 것:

- 고정 데이터는 tests/fixtures/snapshot/snap_*.json — 사이트가 읽는 data.json · corp.json · disc.json · macro.json 과 이름이 달라요.
- 배포는 tests/ 를 사이트에 올리지 않아요 (tools/assemble_site.py). 앱 · 서비스워커 · 빌드한 페이지는 그 파일을 부르지 않아요.
- 고정 데이터는 작고(600KB 이하), 자기 설명(snap_meta.json)과 맞아요. 시험의 시계는 그 데이터를 발행한 날 정오(한국 시간)예요.
- smoke_app.py 는 고정 데이터일 때 진짜 시계를 읽지 않아요 (now_dt 한 곳만).
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "tests", "fixtures", "snapshot")
LIVE = ("data.json", "corp.json", "disc.json", "macro.json")
NAMES = ["make_snapshot.py", "snap_corp.json", "snap_data.json", "snap_disc.json", "snap_macro.json", "snap_meta.json"]
MAX_BYTES = 600_000
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import assemble_site as AS  # noqa: E402
import smoke_app  # noqa: E402


def snap(name):
    with open(os.path.join(SNAP, name), encoding="utf-8") as f:
        return json.load(f)


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def test_snapshot_files_cannot_be_mistaken_for_the_live_files():
    assert sorted(os.listdir(SNAP)) == NAMES
    assert not [n for n in os.listdir(SNAP) if n in LIVE]
    assert all(n.startswith("snap_") for n in os.listdir(SNAP) if n.endswith(".json"))


def test_deploy_never_publishes_tests_or_the_snapshot():
    paths = ["baepsae.html", "app.html", "src/a.js", "tests/smoke_app.py", "tests/fixtures/snapshot/snap_data.json",
             "tests/fixtures/v2/data.json", "Tests/x.json", "x/tests/y.js", "tests.js"]
    assert AS.site_files(paths) == ["baepsae.html", "app.html", "src/a.js", "x/tests/y.js", "tests.js"]   # 맨 위 tests/ · Tests/ 만 빠져요
    real = AS.site_files(tracked())
    assert real and not [p for p in real if p.split("/", 1)[0].lower() == "tests"]
    assert not [p for p in real if os.path.basename(p).startswith("snap_")]
    assert "baepsae.html" in real and "app.html" in real and "sw.js" in real                          # 사이트 파일은 그대로


def test_deploy_stops_if_tests_gets_in_anyway(tmp_path, monkeypatch):
    """규칙이 깨져 tests/ 가 사이트 폴더에 들어가면 조용히 올리지 않고 멈춰요 (docs/ 와 같은 방식)."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    work = tmp_path / "work"
    git = lambda *a: subprocess.run(["git", *a], cwd=work, check=True, capture_output=True, env=env)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True, capture_output=True, env=env)
    for f in LIVE:
        (work / f).write_text("{}")
    (work / "baepsae.html").write_text("x")
    (work / "tests" / "fixtures" / "snapshot").mkdir(parents=True)
    (work / "tests" / "fixtures" / "snapshot" / "snap_data.json").write_text("{}")
    git("add", "-A"); git("commit", "-q", "-m", "main")
    out = tmp_path / "_site"
    AS.assemble(str(work), str(out), "HEAD")
    got = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    assert got == sorted(["baepsae.html", *LIVE])                                                     # tests/ 는 없어요
    monkeypatch.setattr(AS, "site_files", lambda paths: [p for p in paths if p not in LIVE])
    with pytest.raises(SystemExit, match="tests/ 가 들어갔어요"):
        AS.assemble(str(work), str(tmp_path / "_site2"), "HEAD")


def test_the_app_never_asks_for_the_snapshot():
    files = ([p for p in glob.glob(os.path.join(ROOT, "src", "**", "*.*"), recursive=True)
              if p.endswith((".js", ".jsx", ".html", ".css", ".json"))]                                # 앱 코드 (도구 스크립트 .py 는 아니에요)
             + [os.path.join(ROOT, f) for f in ("baepsae.html", "app.html", "app-preview.html", "index.html", "sw.js", "template.html",
                                                "manifest.webmanifest")])
    assert len(files) > 50
    for p in files:
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            body = f.read()
        assert "snap_" not in body and "fixtures/snapshot" not in body and "tests/fixtures" not in body, p


def test_snapshot_is_small_and_matches_its_own_description():
    meta = snap("snap_meta.json")
    data, corp, disc = snap("snap_data.json"), snap("snap_corp.json"), snap("snap_disc.json")
    sizes = {n: os.path.getsize(os.path.join(SNAP, n)) for n in NAMES if n.startswith("snap_") and n != "snap_meta.json"}
    assert sizes == meta["bytes"] and sum(sizes.values()) <= MAX_BYTES, sizes                         # 작게 (지금 47만 바이트)
    assert meta["kept"] == {"stocks": len(data["stocks"]), "companies": len(corp["companies"]),
                            "insider": len(disc["insider"]), "nps": len(disc["nps"])}
    assert all(meta["kept"][k] <= meta["published"][k] for k in meta["kept"])
    assert meta["publishedAt"] == data["publishedAt"] and meta["pxDate"] == data["pxDate"] == corp["pxDate"]
    by_t = {s["t"] for s in data["stocks"]}
    assert len(by_t) == len(data["stocks"]) and {c["t"] for c in corp["companies"]} <= by_t         # 겹침 없이 · corp ⊂ data
    assert {"005930", "005380"} <= by_t and {"005930", "005380"} <= {c["t"] for c in corp["companies"]}   # 삼성전자 · 현대차 검색
    assert all(x["t"] in by_t for x in disc["insider"] + disc["nps"])


def test_the_test_clock_is_noon_kst_on_the_day_the_snapshot_was_published():
    files, now = smoke_app.read_snapshot()
    assert sorted(files) == sorted(LIVE)
    pub = dt.datetime.fromisoformat(files["data.json"]["publishedAt"])
    assert now.utcoffset() == dt.timedelta(hours=9) and now.date() == pub.date() and (now.hour, now.minute) == (12, 0)
    assert now.isoformat(timespec="seconds") == snap("snap_meta.json")["now"]


def test_smoke_app_reads_the_real_clock_in_one_place_only():
    with open(os.path.join(ROOT, "tests", "smoke_app.py"), encoding="utf-8") as f:
        src = f.read()
    assert len(re.findall(r"datetime\.now\(", src)) == 1 and "return CLOCK or dt.datetime.now(KST)" in src
    assert not re.search(r"date\.today\(|utcnow\(|time\.localtime\(|time\.strftime\(", src)
    assert "browser.new_context(" in src and src.count("browser.new_context(") == 1                  # 창은 Runner.new_context 로만 (시계가 붙어요)
    assert 'ap.add_argument("--data", default=None' in src and "files, CLOCK = read_snapshot()" in src
