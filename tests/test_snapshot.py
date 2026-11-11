# -*- coding: utf-8 -*-
"""2026-11-11 (Jack): 예전 뱁새 스모크 테스트(tests/smoke_app.py)는 그날그날의 발행 파일이 아니라 고정 데이터로 돌아요.
PR 의 CI 결과가 그날 아침 발행에 흔들리지 않게요. 여기서 확인하는 것:

- 고정 데이터는 tests/fixtures/snapshot/snap_*.json — 사이트가 읽는 data.json · corp.json · disc.json · macro.json 과 이름이 달라요.
- 배포는 tests/ 를 사이트에 올리지 않아요 (tools/assemble_site.py · tests/test_site_files.py, PR #105). 앱 · 서비스워커 · 빌드한 페이지는 그 파일을 부르지 않아요.
- 고정 데이터는 작고(600KB 이하), 자기 설명(snap_meta.json)과 맞아요. 시험의 시계는 그 데이터를 발행한 날 07:00(한국 시간)에서 시작해요.
- smoke_app.py 는 고정 데이터일 때 진짜 시계를 읽지 않아요 (now_dt 한 곳만).
- smoke_v2.py 는 정해진 날 07:00 에서 시작해 흐르는 시험의 시계로 돌아요 (파이썬 쪽도, 모든 브라우저 창도). smoke_launch.py 와
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
    names = sorted(n for n in os.listdir(SNAP) if n != "__pycache__")       # (스크립트를 불러오면 생기는 git 밖의 폴더는 빼고)
    assert names == NAMES
    assert not [n for n in names if n in LIVE]
    assert all(n.startswith("snap_") for n in names if n.endswith(".json"))


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


def test_the_test_clock_starts_at_0700_kst_on_the_day_the_snapshot_was_published():
    """07:00 KST: 발행한 날 · 한국 날짜와 UTC 날짜가 다른 시각 (UTC 로는 전날 22시 → '오늘'을 UTC 날짜로 읽는 코드가 드러나요) ·
    한 번 도는 동안(시계를 45분 옮기는 장면까지) 어느 쪽 날짜도 넘지 않아요."""
    files, now = smoke_app.read_snapshot()
    assert sorted(files) == sorted(LIVE)
    pub = dt.datetime.fromisoformat(files["data.json"]["publishedAt"])
    assert now.utcoffset() == dt.timedelta(hours=9) and now.date() == pub.date() and (now.hour, now.minute) == (7, 0)
    assert now.isoformat(timespec="seconds") == snap("snap_meta.json")["now"]
    late = now + dt.timedelta(minutes=45 + 30)                                # 가장 멀리: 30분 걸리는 실행 + 45분 옮기기
    assert late.date() == now.date() and late.astimezone(dt.timezone.utc).date() == now.astimezone(dt.timezone.utc).date()
    assert now.astimezone(dt.timezone.utc).date() != now.date()             # 한국 날짜 ≠ UTC 날짜


def test_smoke_app_uses_the_test_clock_with_the_snapshot_and_the_real_clock_with_real_data():
    src = src_of("smoke_app.py")
    assert not re.search(r"datetime\.now\(|date\.today\(|utcnow\(|time\.localtime\(|time\.strftime\(|time\.gmtime\(", src)
    assert "def now_dt():\n    return TC.now()" in src and src.count("TC.start_at(") == 1
    # 시계는 고정 데이터일 때만 시작해요 (--data 는 진짜 시계)
    assert ("    if args.data is None:\n        files, CLOCK = read_snapshot()\n        TC.start_at(CLOCK)" in src
            and "        files, CLOCK = read_data(args.data), None" in src)
    assert 'ap.add_argument("--data", default=None' in src
    # 창은 Runner.new_context 로만 (시험의 시계가 붙고, 닫을 때 그 창의 시계를 재요). Playwright 의 창 시계는 쓰지 않아요
    assert src.count("browser.new_context(") == 1 and "TC.install(ctx)" in src and "ctx.clock.install" not in src
    lines = src.splitlines()
    own = [i for i, ln in enumerate(lines) if "new_context(clock=False" in ln]
    assert len(own) == 1, own                                                 # 페이지 시계를 직접 다루는 장면 하나 (열어 둔 화면)
    after = "\n".join(lines[own[0]:own[0] + 8])
    assert "page.clock.install(time=now)" in after and "R.saw_clock(page, now)" in after
    assert "not_read = len(R.windows) - len(R.measured)" in src and "not_read == 0 and all(drift_ok(d) for d in R.clock_drift)" in src


# ── smoke_v2 · smoke_launch (2026-11-11, Jack): 진짜 시계 · 그날의 발행 파일을 읽지 않아요 ──
def src_of(name):
    with open(os.path.join(ROOT, "tests", name), encoding="utf-8") as f:
        return f.read()


def test_smoke_v2_never_reads_the_real_clock():
    """smoke_v2 의 '지금'은 now_dt() 하나: 정해진 날 07:00 에서 시작해 흘러요. 진짜 날짜 · 시각을 읽는 곳이 없어요
    (기다리는 시간을 재는 time.time · time.monotonic 은 날짜가 아니에요)."""
    src = src_of("smoke_v2.py")
    assert not re.search(r"datetime\.now\(|date\.today\(|utcnow\(|time\.localtime\(|time\.strftime\(|time\.gmtime\(", src)
    assert "def now_dt():\n    return TC.now()" in src
    # 시계는 main() 이 시작해요 (다른 테스트가 도우미만 빌려 쓸 때는 진짜 시계 그대로)
    assert src.count("TC.start_at(") == 1 and "    args = ap.parse_args()\n    TC.start_at(CLOCK)" in src
    m = re.search(r"CLOCK = dt\.datetime\((\d+), (\d+), (\d+), (\d+), (\d+), tzinfo=KST\)", src)
    assert m
    clock = dt.datetime(*map(int, m.groups()), tzinfo=dt.timezone(dt.timedelta(hours=9)))
    assert (clock.hour, clock.minute) == (7, 0)                               # 07:00 KST: 한국 날짜 ≠ UTC 날짜, 한 번 도는 동안 어느 쪽도 안 넘어요
    assert clock < dt.datetime(2026, 11, 12, tzinfo=dt.timezone.utc)          # 지난 날짜 (진짜 시계와 우연히 겹칠 날이 없어요)


def test_smoke_v2_every_window_gets_the_test_clock():
    """창은 Runner.new_context 로만 열어요 (그 창의 시계가 now_dt() 에서 시작). clock=False 인 곳은 그 장면이 페이지 시계를 직접
    설치하고 (page.clock.install) 곧바로 saw_clock 으로 알려요 — 끝의 '브라우저 시계' 검사가 모든 창을 세요."""
    src = src_of("smoke_v2.py")
    assert src.count("browser.new_context(") == 1 and "ctx = self.browser.new_context(**kw)" in src
    assert "TC.install(ctx)" in src and "ctx.clock.install" not in src        # 창 전체에 Playwright 시계를 깔지 않아요 (performance 기록을 지워요)
    lines = src.splitlines()
    own = [i for i, ln in enumerate(lines) if "new_context(clock=" in ln and "def new_context" not in ln]
    assert len(own) == 4, own                                                 # 페이지 시계를 직접 다루는 장면 넷
    for i in own:
        after = "\n".join(lines[i:i + 22])
        assert "page.clock.install(time=" in after and "saw_clock(page, " in after, lines[i].strip()
    # 창을 여는 곳(new_context 를 부르는 곳)마다 그 창의 시계를 재요: R.open 하나 + 직접 여는 다섯 곳
    assert len(re.findall(r"R\.new_context\(|self\.new_context\(", src)) == len(re.findall(r"(?:R|self)\.saw_clock\(page", src)) == 6
    assert "clock_ok = TC.started and bool(R.clock_drift) and all(drift_ok(d) for d in R.clock_drift)" in src


def test_smoke_launch_without_data_option_reads_only_fixed_data():
    """옵션 없이 돌면 고정 시험 데이터(tests/fixtures/v2)만 써요: 저장소의 그날 파일을 읽는 길이 없어요. 진짜 데이터는 --data 로만."""
    src = src_of("smoke_launch.py")
    assert "real_data_missing()" not in src and "def use_root" not in src
    assert 'variants = ("repo",) if args.data is not None else ("fixtures",)' in src
    assert "if args.data:" not in src and "if not args.data:" not in src       # 빈 값(--data "")이 조용히 고정 데이터로 가지 않아요
    assert 'j["publishedAt"] = now' in src and 'if f != "disc.json"' not in src    # 네 파일 모두 방금 발행한 것으로
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


# ── tests/testclock.py: 시험의 시계 ──
def test_test_clock_is_the_real_clock_until_started_and_then_runs_from_the_start():
    import time
    import testclock
    tc = testclock.TestClock()
    assert not tc.started and abs(tc.now().timestamp() - time.time()) < 1    # 시작 전: 진짜 시계
    start = dt.datetime(2026, 11, 11, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    tc.start_at(start)
    a = tc.now()
    assert tc.started and 0 <= (a - start).total_seconds() < 1 and a.utcoffset() == dt.timedelta(hours=9)
    time.sleep(0.05)
    assert tc.now() > a                                                       # 멈춰 있지 않아요
    assert testclock.drift_ok(0) and testclock.drift_ok(-1) and testclock.drift_ok(599)
    for off in (-3, 600, 3600, -30000, 86400 * 200):                         # 진짜 시계로 돈 창은 여기에 걸려요
        assert not testclock.drift_ok(off), off


def test_test_clock_moves_only_the_date_in_a_browser_window(tmp_path):
    """창에서는 Date 만 옮겨요: 타이머와 performance 기록(받은 파일 목록)은 진짜 그대로. 시작하지 않은 시계는 아무것도 바꾸지 않아요."""
    pw = pytest.importorskip("playwright.sync_api")
    import functools
    import http.server
    import threading
    import time
    import testclock
    assert "clock.install" not in src_of("testclock.py").split('"""', 2)[2]   # Playwright 의 시계 설치(타이머 · performance 까지 바꿈)를 쓰지 않아요
    (tmp_path / "index.html").write_text("<script src='a.js'></script><p>x</p>")
    (tmp_path / "a.js").write_text("window.loaded = 1;")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(tmp_path)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    start = dt.datetime(2026, 11, 11, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch(executable_path=smoke_app.chromium_path())
            tc = testclock.TestClock()
            tc.start_at(start)
            ctx = b.new_context()
            tc.install(ctx)
            page = ctx.new_page()
            page.goto(base + "/index.html")
            assert testclock.drift_ok(tc.drift(page)) and abs(tc.drift(page)) < 2
            got = page.evaluate("""async () => {
              const t0 = performance.now(); await new Promise((r) => setTimeout(r, 30)); const waited = performance.now() - t0;
              return { iso: new Date().toISOString(), plain: typeof Date(), inst: new Date() instanceof Date, parsed: new Date('2026-11-02').toISOString(),
                       utc: Date.UTC(2026, 0, 1), local: new Date(2026, 0, 2).getDate(), waited,
                       fetched: performance.getEntriesByType('resource').map((e) => e.name.split('/').pop()) };
            }""")
            assert got["iso"].startswith("2026-11-10T22:0"), got              # 07:00 KST = UTC 로는 전날 22:00
            assert got["plain"] == "string" and got["inst"] is True and got["parsed"] == "2026-11-02T00:00:00.000Z"
            assert got["utc"] == 1767225600000 and got["local"] == 2 and 20 <= got["waited"] < 2000
            assert "a.js" in got["fetched"], got                              # performance 기록은 진짜 그대로 (받은 파일이 보여요)
            plain = b.new_context()                                           # 시작하지 않은 시계: 진짜 날짜 그대로
            testclock.TestClock().install(plain)
            page2 = plain.new_page()
            page2.goto(base + "/index.html")
            assert abs(page2.evaluate("Date.now()") / 1000 - time.time()) < 5
            assert not testclock.drift_ok(tc.drift(page2))                    # 진짜 시계의 창은 '어긋남'으로 잡혀요
            b.close()
    finally:
        srv.shutdown()


# ── 고정해 둔 진짜 발행본으로도: 머지 전에 진짜 데이터의 모양을 한 번 더 봐요 (날마다 바뀌지 않는 진짜 데이터) ──
def test_the_pinned_real_publish_has_every_field_2_0_needs():
    """tests/fixtures/v2 는 손으로 만든 항목이 섞인 시험 데이터예요. 고정 데이터(snapshot)는 진짜 발행본을 줄인 것이라,
    2.0 이 쓰는 항목이 진짜 발행본에 있는지를 그날의 파일 없이도 여기서 봐요 (그날의 파일은 매일 실행이 발행 전에 봐요)."""
    from test_launch import real_data_missing
    assert real_data_missing(snap("snap_data.json"), snap("snap_corp.json"), snap("snap_macro.json")) == []


def test_growth_basis_agrees_on_the_pinned_real_publish(tmp_path):
    """예전 뱁새와 2.0 의 매출 성장 기준이 진짜 발행본(고정 데이터의 한국 종목 모두)에서도 같아요. 시험 데이터(fixtures/v2)에는
    '기준 없음'인 종목이 없어서, 그 갈래는 여기서만 봐요."""
    import shutil
    if shutil.which("node") is None:
        pytest.skip("node 가 없어요")
    import real_data_check as RC
    for f in ("data.json", "corp.json"):
        shutil.copy(os.path.join(SNAP, "snap_" + f), tmp_path / f)
    got = RC.growth_compare(str(tmp_path))
    assert got["n"] >= 100 and got["diff"] == [] and got["y2"] > got["y1"] >= 0 and got["none"] >= 1, got


def test_every_stock_smoke_app_names_is_in_the_snapshot():
    """smoke_app.py 가 이름으로 부르는 종목은 모두 고정 데이터에 있어요 (일부러 없는 가짜 코드 빼고). 몇몇 장면은 '데이터에 있는
    종목만' 골라 쓰기 때문에, 빠진 종목이 있으면 그 장면이 조용히 덜 보게 돼요."""
    src = src_of("smoke_app.py")
    have = {s["t"] for s in snap("snap_data.json")["stocks"]}
    made_up = {"999990", "999991", "999997", "999998", "999999"}             # 시험이 지어낸 종목 코드 (데이터에 없어야 해요)
    named = set(re.findall(r'"(\d{6})"', src)) | set(re.findall(r'"(0\d{7})"', src))        # 6자리 종목코드 · 8자리(금현물 04020000)
    assert len(named) >= 13 and "04020000" in named and not (made_up & have)
    assert named - made_up <= have, sorted(named - made_up - have)
    for t in ("AAPL", "MSFT", "NVDA"):
        assert f'"{t}"' in src and t in have, t
