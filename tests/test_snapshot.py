# -*- coding: utf-8 -*-
"""2026-11-11 (Jack): 예전 뱁새 스모크 테스트(tests/smoke_app.py)는 그날그날의 발행 파일이 아니라 고정 데이터로 돌아요.
PR 의 CI 결과가 그날 아침 발행에 흔들리지 않게요. 여기서 확인하는 것:

- 고정 데이터는 tests/fixtures/snapshot/snap_*.json — 사이트가 읽는 data.json · corp.json · disc.json · macro.json 과 이름이 달라요.
- 배포는 tests/ 를 사이트에 올리지 않아요 (tools/assemble_site.py · tests/test_site_files.py, PR #105). 앱 · 서비스워커 · 빌드한 페이지는 그 파일을 부르지 않아요.
- 고정 데이터는 작고(600KB 이하), 자기 설명(snap_meta.json)과 맞아요. 시험의 시계는 그 데이터를 발행한 날 정오(한국 시간)예요.
- smoke_app.py 는 고정 데이터일 때 진짜 시계를 읽지 않아요 (now_dt 한 곳만).
- smoke_v2.py 는 정해진 날 정오에서 시작해 흐르는 시험의 시계로 돌아요 (파이썬 쪽도, 모든 브라우저 창도). smoke_launch.py 와
  2.0 항목 검사 · 매출 성장 기준 비교는 고정 시험 데이터로 봐요 — 그날의 진짜 데이터로는 매일 실행이 발행 전에 봐요 (PR #106).
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


# ── smoke_v2 · smoke_launch (2026-11-11, Jack): 진짜 시계 · 그날의 발행 파일을 읽지 않아요 ──
def src_of(name):
    with open(os.path.join(ROOT, "tests", name), encoding="utf-8") as f:
        return f.read()


def test_smoke_v2_never_reads_the_real_clock():
    """smoke_v2 의 '지금'은 now_dt() 하나: 정해진 날 정오에서 시작해 흘러요. 진짜 날짜 · 시각을 읽는 곳이 없어요
    (기다리는 시간을 재는 time.time · time.monotonic 은 날짜가 아니에요)."""
    src = src_of("smoke_v2.py")
    assert not re.search(r"datetime\.now\(|date\.today\(|utcnow\(|time\.localtime\(|time\.strftime\(|time\.gmtime\(", src)
    # 진짜 시계는 한 곳에서만, 시험의 시계와의 차이(_SHIFT)를 잴 때 써요: now_dt = 진짜 시계 + _SHIFT
    assert "CLOCK = dt.datetime(" in src and src.count("time.time() + _SHIFT") == 1 and "_SHIFT = CLOCK.timestamp() - time.time()" in src
    m = re.search(r"CLOCK = dt\.datetime\((\d+), (\d+), (\d+), (\d+), (\d+), tzinfo=KST\)", src)
    assert m and (int(m.group(4)), int(m.group(5))) == (12, 0)              # 정오: 한 번 도는 동안 · 시계를 옮기는 장면이 날짜를 넘지 않아요


def test_smoke_v2_every_window_gets_the_test_clock():
    """창은 Runner.new_context 로만 열어요 (그 창의 시계가 now_dt() 에서 시작). clock=False 인 곳은 그 장면이 페이지 시계를 직접
    설치하고 (page.clock.install) 곧바로 saw_clock 으로 알려요 — 끝의 '브라우저 시계' 검사가 모든 창을 세요."""
    src = src_of("smoke_v2.py")
    assert src.count("browser.new_context(") == 1 and "ctx = self.browser.new_context(**kw)" in src
    assert "ctx.add_init_script(DATE_SHIM % round(_SHIFT * 1000))" in src and "window.Date = TestDate;" in src
    assert "ctx.clock.install" not in src                                     # 창 전체에 Playwright 시계를 깔지 않아요 (performance 기록을 지워요)
    lines = src.splitlines()
    own = [i for i, ln in enumerate(lines) if "new_context(clock=" in ln and "def new_context" not in ln]
    assert len(own) == 4, own                                                 # 페이지 시계를 직접 다루는 장면 넷
    for i in own:
        after = "\n".join(lines[i:i + 22])
        assert "page.clock.install(time=" in after and "saw_clock(page, " in after, lines[i].strip()
    opened = len(re.findall(r"\.new_page\(\)", src))
    told = len(re.findall(r"saw_clock\(page", src))
    assert told >= 6 and "self.saw_clock(page)" in src, (opened, told)       # R.open (대부분의 창) + 직접 여는 다섯 곳
    assert "drift_ok = bool(R.clock_drift) and all(-2 <= d < 600 for d in R.clock_drift)" in src


def test_smoke_launch_without_data_option_reads_only_fixed_data():
    """옵션 없이 돌면 고정 시험 데이터(tests/fixtures/v2)만 써요: 저장소의 그날 파일을 읽는 길이 없어요. 진짜 데이터는 --data 로만."""
    src = src_of("smoke_launch.py")
    assert "real_data_missing()" not in src and "def use_root" not in src
    assert 'variants = ("repo",) if args.data else ("fixtures",)' in src
    assert "DATA_DIR = None" in src and 'FIXTURES = os.path.join(ROOT, "tests", "fixtures", "v2")' in src
    assert src.count("os.path.join(DATA_DIR, f)") == 1 and src.count("os.path.join(FIXTURES, f)") == 1
    for f in LIVE:
        assert os.path.isfile(os.path.join(ROOT, "tests", "fixtures", "v2", f)), f


def test_pytest_checks_that_moved_to_fixed_data_do_not_read_the_daily_files():
    """2.0 항목 검사(test_launch)와 매출 성장 기준 비교(test_app_data)는 고정 데이터로 봐요. 그날의 진짜 데이터로는 매일 실행이
    발행 전에 같은 검사를 돌려요 (tests/real_data_check.py — update-data.yml 의 '발행 전 화면 검사')."""
    launch, app = src_of("test_launch.py"), src_of("test_app_data.py")
    body = launch.split("def test_main_address_only_points_to_2_0_when_the_real_fields_are_live():", 1)[1].split("\ndef ", 1)[0]
    assert "real_data_missing()" not in body and body.count("read(FIXED + ") == 3
    growth = app.split("def test_korean_growth_basis_matches_2_0_on_todays_data():", 1)[1].split("\n@pytest", 1)[0]
    assert 'compare("./tests/fixtures/v2/data.json", "./tests/fixtures/v2/corp.json")' in growth and '"./data.json"' not in growth
    wf = open(os.path.join(ROOT, ".github", "workflows", "update-data.yml"), encoding="utf-8").read()
    assert "for t in real_data_check smoke_launch smoke_app; do" in wf and 'python "tests/$t.py" --data .' in wf
    rc = src_of("real_data_check.py")
    assert "real_data_missing(" in rc and "D.krGrowthBasis(s.g3, k ? k.rev : null), b = E.growthBasis(s, k || null)" in rc
