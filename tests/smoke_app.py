#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""앱 스모크 테스트 — 사이트를 로컬에서 띄우고 헤드리스 크롬(휴대폰 크기 390×844)으로 눌러봐요.

  python tests/smoke_app.py                 # 저장소에 있는 JSON 으로
  python tests/smoke_app.py --data DIR      # DIR 의 data/corp/disc/macro.json 으로

장면(시나리오)마다 새 브라우저를 열고, 데이터 사본을 일부러 망가뜨려 맞는 문구가 나오는지 봐요.
  정상        첫 화면 검색(삼성전자·현대차), 모든 탭, 30초 진단·차근차근(KO·EN), 기준 날짜
  멈춤        발행이 6일 전이면 'N일째 갱신이 멈췄어요'
  NaN         따옴표 밖 NaN 을 고쳐 읽고 계속 동작 (console 경고)
  깨짐·404    corp.json 을 못 읽으면 '데이터를 불러오지 못했어요' (검색·기업분석)
  data 없음   포트폴리오: '최신 시세를 불러오지 못해 예시 가격으로 보여 드려요' ('일부 종목' 문구는 안 나옴)
  금 보유     오늘 데이터에 없는 금현물을 담은 포트폴리오 → 배너
  금 추정     국제 금값 환산 추정 → 이름에 '국제 금값 환산' + '금현물은 국제 금값으로 환산한 추정치예요'
  금리        macro.json 의 금리 부분만 빈 날 → 금리 칸에 '금리 데이터를 불러오지 못했어요' (EN 은 영어)
  서비스워커  예전 v10 워커의 얼어붙은 corp.json 이 새 워커로 바뀌고 baepsae-v10 캐시가 지워짐
모든 장면에서 페이지 오류(pageerror) 0건. 인터넷 요청(글꼴·통계)은 막고 localhost 만 허용해요.
"""
import argparse
import datetime as dt
import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_FILES = (["baepsae.html", "index.html", "manifest.webmanifest", "sw.js", "og.png", "icon-192.png", "icon-512.png"]
              + [f"baepi-{i}.png" for i in range(1, 10)])
DATA_FILES = ["data.json", "corp.json", "disc.json", "macro.json"]
WAIT = 20000  # ms
LOAD_FAIL = "데이터를 불러오지 못했어요"
NONLIVE = "일부 종목은 최신 시세가 아니라 예시 가격이에요"          # 일부만 내장 예시 가격
NOLIVE_ALL = "최신 시세를 불러오지 못해 예시 가격으로 보여 드려요"    # data.json 을 못 읽어 전부 예시
GOLD_EST = "금현물은 국제 금값으로 환산한 추정치예요"
RATES_FAIL = "금리 데이터를 불러오지 못했어요"
OFFICIAL = "공식 종가예요. 다른 수치는 추정치예요"
KST = dt.timezone(dt.timedelta(hours=9))


def now_kst(days_ago=0):
    return (dt.datetime.now(KST) - dt.timedelta(days=days_ago)).isoformat(timespec="seconds")


def read_data(data_dir):
    out = {}
    for f in DATA_FILES:
        with open(os.path.join(data_dir, f), encoding="utf-8") as fh:
            out[f] = json.load(fh)   # 파이썬은 NaN 을 읽어줘요 (원본이 망가져 있어도 사본을 만들 수 있게)
    return out


def build_site(files, raw=None, drop=()):
    """files: {이름: 객체} 를 쓰고, raw: {이름: 그대로 쓸 글자}, drop: 빼둘 파일(→ 404)."""
    site = tempfile.mkdtemp(prefix="baepsae-smoke-")
    for f in SITE_FILES:
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy(os.path.join(ROOT, f), site)
    for name, obj in files.items():
        if name in drop:
            continue
        with open(os.path.join(site, name), "w", encoding="utf-8") as fh:
            if raw and name in raw:
                fh.write(raw[name])
            else:
                json.dump(obj, fh, ensure_ascii=False, allow_nan=True)
    return site


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def serve(site):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def chromium_path():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


class Runner:
    def __init__(self, browser, shots):
        self.browser, self.shots = browser, shots
        self.results, self.errors, self.console = [], [], []

    def open(self, site, sw=False, local=None):
        srv, base = serve(site)
        # is_mobile 을 켜면 기업분석 화면이 폭 390px 보다 넓어(약 530px) 크롬이 화면을 축소하고,
        # 그러면 탭 클릭 좌표가 어긋나요. 그래서 크기만 휴대폰(390×844)으로 맞춥니다.
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR",
                                       service_workers="allow" if sw else "block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        if local:
            ctx.add_init_script("(() => { try { const kv = %s; for (const k in kv) localStorage.setItem(k, kv[k]); } catch (e) {} })();"
                                % json.dumps(local, ensure_ascii=False))
        page = ctx.new_page()
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("console", lambda m: self.console.append((m.type, m.text)))
        page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
        return srv, ctx, page, base

    def check(self, page, scene, name, fn):
        label = f"[{scene}] {name}"
        try:
            fn()
            self.results.append((label, True, ""))
        except Exception as e:
            self.results.append((label, False, str(e).splitlines()[0][:160]))
            if self.shots:
                os.makedirs(self.shots, exist_ok=True)
                try:
                    page.screenshot(path=os.path.join(self.shots, f"fail-{len(self.results)}.png"), full_page=True)
                except Exception:
                    pass
        print(f"  {'PASS' if self.results[-1][1] else 'FAIL'}  {label}", flush=True)


# ── 화면 조작 ───────────────────────────────────────────────
def see(page, text, timeout=WAIT):
    page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)


def tab(page, label):
    page.locator("nav.botNav button", has_text=label).click()


def home(page):
    tab(page, "포트폴리오" if page.locator("nav.botNav button", has_text="포트폴리오").count() else "Portfolio")
    for back in ("모드 선택", "Back"):
        if page.get_by_text(back, exact=True).count():
            page.get_by_text(back, exact=True).click()


def search(page, q, code):
    box = page.get_by_placeholder("궁금한 종목이 있나요? — 이름 또는 코드")
    box.fill("")
    box.fill(q)
    page.locator("button", has_text=code).first.wait_for(state="visible", timeout=WAIT)


def close_welcome(page, label):
    # 처음 방문하면 '안녕하세요, 뱁이예요' 안내가 화면을 덮어요. 새 사용자처럼 닫습니다.
    btn = page.get_by_role("button", name=label, exact=True)
    try:
        btn.first.wait_for(state="visible", timeout=4000)
        btn.first.click()
    except Exception:
        pass


def badge_text(page):
    return page.locator(".dateBadge").first.inner_text(timeout=WAIT)


def poll(page, js, ok, what, timeout=WAIT / 1000, every=None):
    """브라우저 값이 ok 가 될 때까지 파이썬에서 직접 기다려요 (wait_for_function 은 Promise 를 '참'으로 봐서 못 믿어요)."""
    deadline = time.time() + timeout
    v = None
    while time.time() < deadline:
        if every:
            every()
        v = page.evaluate(js)
        if ok(v):
            return v
        time.sleep(0.3)
    raise AssertionError(f"{what} — 마지막 값: {v!r}")


FUNDS = [("069500", "KODEX 200", "kr", "index"), ("379800", "KODEX 미국S&P500", "us", "index"),
         ("132030", "KODEX 골드선물(H)", "metal", "metal"), ("144600", "KODEX 은선물(H)", "metal", "metal"),
         ("04020000", "KRX 금현물 (99.99K)", "metal", "metal")]


def upgrade(files):
    """예전 형식(10/17 등) 데이터를 v17.5 모양으로: pxDate 와 ETF·금현물 5종을 넣어요 (내장 종목이 모두 실시간이 되게)."""
    d = files["data.json"]
    for name in ("data.json", "corp.json"):
        if not files[name].get("pxDate"):
            files[name]["pxDate"] = files[name].get("asOf")
    have = {x.get("t") for x in d["stocks"]}
    for t, nk, cls, sec in FUNDS:
        if t not in have:
            d["stocks"].append({"t": t, "nk": nk, "ne": nk, "cls": cls, "s": sec, "fund": True,
                                "price": 10000.0, "vol": 20.0, "beta": 0.5, "lo": 9000.0, "hi": 11000.0})
    return files


# ── 장면 ────────────────────────────────────────────────────
def scene_normal(R, files, full):
    site = build_site(files)
    srv, ctx, page, _ = R.open(site)
    S = "정상"
    R.check(page, S, "첫 화면이 열림", lambda: see(page, "내 종목, 괜찮은 걸까요?"))

    def gate_samsung():
        search(page, "삼성전자", "005930")
        page.locator("button", has_text="005930").first.click()
        see(page, "사실의 요약일 뿐")
        assert "기준" in badge_text(page), "성적표에 기준 날짜가 없어요"
    R.check(page, S, "검색: 삼성전자(005930) → 성적표 + 기준 날짜", gate_samsung)
    R.check(page, S, "검색: 현대차(005380) 찾기", lambda: search(page, "현대차", "005380"))

    def open_tab(label, marker):
        def run():
            tab(page, label)
            see(page, marker)
        return run
    R.check(page, S, "탭: 기업분석 (corp.json)", open_tab("기업분석", "시장 지도"))

    def corp_date():
        t = badge_text(page)
        assert "기준" in t and "멈췄어요" not in t, t
    R.check(page, S, "기업분석: '○월 ○일 기준' (멈춤 경고 없음)", corp_date)
    R.check(page, S, "탭: 공시·수급 (disc.json)", open_tab("공시·수급", "내부자 거래"))
    R.check(page, S, "탭: 금리·원자재 (macro.json)", open_tab("금리·원자재", "심화 — 채권·환율 연구실"))
    if full:   # 국고채 커브가 들어 있는 데이터일 때만
        R.check(page, S, "금리·원자재: 국고채 커브가 보임", lambda: see(page, "만기별 금리를 이은 선이에요"))
    R.check(page, S, "탭: 정보", open_tab("정보", "피드백"))
    R.check(page, S, "탭: 포트폴리오", open_tab("포트폴리오", "내 종목, 괜찮은 걸까요?"))

    def quick_ko():
        page.get_by_text("30초 진단", exact=True).click()
        close_welcome(page, "시작하기")
        see(page, "빠른 진단")
    R.check(page, S, "30초 진단 열림 (KO)", quick_ko)

    def detail_ko():
        home(page)
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.locator(".dateBadge", has_text="기준").first.wait_for(state="visible", timeout=WAIT)  # data.json 을 읽었을 때만
        page.wait_for_timeout(300)
        assert page.locator(".nonLiveBanner").count() == 0, "실시간 데이터인데 '최신 시세가 아니에요' 배너가 보여요"
        see(page, OFFICIAL)          # "가격은 {M월 D일} 공식 종가예요. 다른 수치는 추정치예요."
    R.check(page, S, "차근차근 만들기: 실제 시세 + 기준 날짜 + 공식 종가 안내 (KO)", detail_ko)

    def to_en():
        home(page)
        page.get_by_role("button", name="EN", exact=True).first.click()
        see(page, "Is my stock doing okay?")
    R.check(page, S, "영어 모드 전환", to_en)

    def detail_en():
        page.get_by_text("Build step by step", exact=True).click()
        page.locator(".dateBadge", has_text="As of").first.wait_for(state="visible", timeout=WAIT)
        see(page, "Prices are official closes from")
    R.check(page, S, "차근차근 만들기: 실제 시세 + 기준 날짜 (EN)", detail_en)

    def quick_en():
        home(page)
        page.get_by_text("30-second checkup", exact=True).click()
        see(page, "Quick check")
    R.check(page, S, "30초 진단 열림 (EN)", quick_en)

    def back_ko():
        home(page)
        page.get_by_role("button", name="한국어", exact=True).first.click()
        see(page, "내 종목, 괜찮은 걸까요?")
    R.check(page, S, "한국어로 되돌리기", back_ko)
    ctx.close(); srv.shutdown()


def scene_stale(R, files):
    f = json.loads(json.dumps(files, allow_nan=True))
    for name in DATA_FILES:
        f[name]["publishedAt"] = now_kst(days_ago=6)
    srv, ctx, page, _ = R.open(build_site(f))

    def run():
        tab(page, "기업분석")
        see(page, "시장 지도")
        assert "6일째 갱신이 멈췄어요" in badge_text(page), badge_text(page)
    R.check(page, "멈춤", "발행 6일 전 → '6일째 갱신이 멈췄어요'", run)
    ctx.close(); srv.shutdown()


def scene_nan(R, files):
    f = json.loads(json.dumps(files, allow_nan=True))
    f["corp.json"]["companies"][0]["per"] = float("nan")
    f["corp.json"]["companies"][1]["nk"] = f["corp.json"]["companies"][1]["nk"]  # 글자 안의 NaN 은 그대로
    f["corp.json"]["note"] = "NaN 과 Infinity 는 글자로는 괜찮아요"
    f["data.json"]["stocks"][0]["vol"] = float("inf")
    R.console.clear()
    srv, ctx, page, _ = R.open(build_site(f))

    def run():
        search(page, "삼성전자", "005930")
        tab(page, "기업분석")
        see(page, "시장 지도")
        assert any("NaN·Infinity" in t for _, t in R.console), "고쳐 읽었다는 console 경고가 없어요"
    R.check(page, "NaN", "따옴표 밖 NaN 을 고쳐 읽고 계속 동작", run)
    ctx.close(); srv.shutdown()


def scene_corp_fail(R, files, how):
    if how == "깨짐":
        text = json.dumps(files["corp.json"], ensure_ascii=False)
        site = build_site(files, raw={"corp.json": text[: len(text) // 2]})
    else:
        site = build_site(files, drop=("corp.json",))
    srv, ctx, page, _ = R.open(site)

    def gate():
        box = page.get_by_placeholder("궁금한 종목이 있나요? — 이름 또는 코드")
        box.fill("삼성전자")
        see(page, LOAD_FAIL)
        assert page.get_by_text("찾지 못했어요").count() == 0
    R.check(page, f"corp {how}", "첫 화면 검색 → '불러오지 못했어요' (찾지 못했어요 아님)", gate)

    def corp_tab():
        tab(page, "기업분석")
        see(page, LOAD_FAIL)
        assert page.get_by_text("GitHub").count() == 0
    R.check(page, f"corp {how}", "기업분석 탭 → '불러오지 못했어요'", corp_tab)
    ctx.close(); srv.shutdown()


def scene_no_data(R, files):
    srv, ctx, page, _ = R.open(build_site(files, drop=("data.json",)))

    def run():
        page.get_by_text("차근차근 만들기", exact=True).click()
        see(page, NOLIVE_ALL)
        page.wait_for_timeout(300)
        assert page.get_by_text(NONLIVE).count() == 0, "전부 예시인데 '일부 종목은…' 이 보여요"
    R.check(page, "data 없음", "포트폴리오 → '최신 시세를 불러오지 못해 예시 가격으로…' ('일부 종목' 아님)", run)
    ctx.close(); srv.shutdown()


def scene_gold_holding(R, files):
    f = json.loads(json.dumps(files, allow_nan=True))
    f["data.json"]["stocks"] = [s for s in f["data.json"]["stocks"] if s.get("t") != "04020000"]
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "04020000", "mw": 300}]}
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "sgold", "name": "금 보유 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_sgold": json.dumps(slot, ensure_ascii=False)}
    srv, ctx, page, _ = R.open(build_site(f), local=local)

    def run():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("금 보유 시험", exact=False).first.click()
        see(page, NONLIVE)
    R.check(page, "금 보유", "오늘 데이터에 없는 금현물을 담음 → 배너", run)
    ctx.close(); srv.shutdown()


def scene_gold_estimate(R, files):
    f = json.loads(json.dumps(files, allow_nan=True))
    g = next((s for s in f["data.json"]["stocks"] if s.get("t") == "04020000"), None)
    if g is None:
        g = {"t": "04020000", "nk": "KRX 금현물 (99.99K)", "cls": "metal", "s": "metal", "price": 171000, "vol": 20, "beta": 0.1}
        f["data.json"]["stocks"].append(g)
    g.update({"est": True, "src": "국제 금값 환산"})
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "04020000", "mw": 300}]}
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "sest", "name": "금 추정 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_sest": json.dumps(slot, ensure_ascii=False)}
    srv, ctx, page, _ = R.open(build_site(f), local=local)

    def run():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("금 추정 시험", exact=False).first.click()
        see(page, GOLD_EST)
        assert page.get_by_text("국제 금값 환산").count() > 0, "금현물 이름에 '국제 금값 환산'이 없어요"
        assert page.get_by_text("KRX 금현물").count() == 0, "추정치인데 KRX 금현물로 보여요"
    R.check(page, "금 추정", "국제 금값 환산 → 이름에 표시 + '금현물은 … 추정치예요', KRX 이름 안 보임", run)
    ctx.close(); srv.shutdown()


def scene_rates_fail(R, files):
    """macro.json 은 읽히는데 금리(ECOS) 부분만 빈 날: 금리 칸에만 '금리 데이터를 불러오지 못했어요' (영어 모드는 영어)."""
    f = json.loads(json.dumps(files, allow_nan=True))
    for k in ("curve", "sprKr", "tenor", "credit"):
        if k in f["macro.json"]:
            f["macro.json"][k] = None
    srv, ctx, page, _ = R.open(build_site(f), local={"baepsae_v9_seen": "1"})

    def ko():
        tab(page, "금리·원자재")
        see(page, RATES_FAIL)
        whole = "데이터를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요."      # 탭 전체 실패 문구 (정확히 이 문장)
        assert page.get_by_text(whole, exact=True).count() == 0, "금리만 빈 날인데 탭 전체가 '불러오지 못했어요'"
    R.check(page, "금리 일부 실패", "금리 칸만 '금리 데이터를 불러오지 못했어요' (KO)", ko)
    ctx.close(); srv.shutdown()
    srv, ctx, page, _ = R.open(build_site(f), local={"baepsae_v9_seen": "1", "baepsae_lang": "en"})

    def en():
        tab(page, "Rates")
        see(page, "We couldn't load the interest-rate data.")
    R.check(page, "금리 일부 실패", "금리 칸 실패 문구 (EN)", en)
    ctx.close(); srv.shutdown()


def scene_service_worker(R, files):
    f = json.loads(json.dumps(files, allow_nan=True))
    f["corp.json"]["__v"] = "A"
    site = build_site(f)
    shutil.copy(os.path.join(ROOT, "tests", "fixtures", "sw", "sw-v10.js"), os.path.join(site, "sw.js"))
    srv, ctx, page, base = R.open(site, sw=True)
    get_v = "fetch('./corp.json', {cache: 'no-store'}).then(r => r.json()).then(j => j.__v)"
    keys = "caches.keys()"

    def old_worker():
        # 페이지가 ./sw.js 를 등록해야 해요 (template.html)
        poll(page, "navigator.serviceWorker.getRegistration().then(r => !!(r && r.active))", bool, "서비스워커가 등록되지 않았어요")
        page.reload(wait_until="domcontentloaded")
        poll(page, "navigator.serviceWorker.controller !== null", bool, "페이지가 서비스워커의 관리를 받지 않아요")
        assert page.evaluate(get_v) == "A"
        f["corp.json"]["__v"] = "B"
        with open(os.path.join(site, "corp.json"), "w", encoding="utf-8") as fh:
            json.dump(f["corp.json"], fh, ensure_ascii=False, allow_nan=True)
        assert page.evaluate(get_v) == "A", "v10 워커가 예전 corp.json 을 계속 줘야 사고 재현이에요"
        assert "baepsae-v10" in page.evaluate(keys)
    R.check(page, "서비스워커", "예전 v10 워커: corp.json 이 얼어붙음 (재현)", old_worker)

    def new_worker():
        shutil.copy(os.path.join(ROOT, "sw.js"), os.path.join(site, "sw.js"))
        last = [0.0]

        def nudge():   # 업데이트 확인이 이미 진행 중이면 합쳐지므로, 새 워커가 잡힐 때까지 몇 번 다시 요청해요
            if time.time() - last[0] > 2:
                last[0] = time.time()
                page.evaluate("navigator.serviceWorker.getRegistration().then(r => r && r.update()).then(() => 1, () => 0)")
        poll(page, "caches.keys()", lambda k: "baepsae-v10" not in k, "baepsae-v10 캐시가 지워지지 않았어요", every=nudge)
        page.reload(wait_until="domcontentloaded")
        assert page.evaluate(get_v) == "B", "새 워커인데도 예전 corp.json 이에요"
        k = page.evaluate(keys)
        assert "baepsae-v10" not in k and all(x == "baepsae-v17-5" for x in k), k
    R.check(page, "서비스워커", "새 워커: 새 corp.json + baepsae-v10 캐시 삭제", new_worker)
    ctx.close(); srv.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=ROOT, help="data/corp/disc/macro.json 이 있는 폴더")
    ap.add_argument("--shots", default=None, help="실패 시 스크린샷을 저장할 폴더")
    ap.add_argument("--only", default=None, help="이 장면만 (정상·멈춤·NaN·corp·data·금·금리·서비스워커)")
    args = ap.parse_args()
    files = read_data(args.data)
    # 정상 장면은 '방금 발행된' 것으로 맞춰요 (원본이 며칠 지난 파일이어도 멈춤 경고가 끼지 않게)
    fresh = upgrade(json.loads(json.dumps(files, allow_nan=True)))
    for name in DATA_FILES:
        fresh[name]["publishedAt"] = now_kst()
    full = bool((fresh["macro.json"].get("curve") or {}).get("date"))   # 국고채 커브가 있는 데이터면 커브까지 확인

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path())
        R = Runner(browser, args.shots)
        scenes = [("정상", lambda: scene_normal(R, fresh, full)), ("멈춤", lambda: scene_stale(R, fresh)),
                  ("NaN", lambda: scene_nan(R, fresh)),
                  ("corp", lambda: scene_corp_fail(R, fresh, "깨짐")), ("corp", lambda: scene_corp_fail(R, fresh, "404")),
                  ("data", lambda: scene_no_data(R, fresh)), ("금", lambda: scene_gold_holding(R, fresh)),
                  ("금", lambda: scene_gold_estimate(R, fresh)), ("금리", lambda: scene_rates_fail(R, fresh)),
                  ("서비스워커", lambda: scene_service_worker(R, fresh))]
        for key, fn in scenes:
            if args.only and key != args.only:
                continue
            try:
                fn()
            except Exception as e:
                R.results.append((f"[{key}] 장면 실행", False, str(e).splitlines()[0][:160]))
                print(f"  FAIL  [{key}] 장면 실행: {e}", flush=True)
        R.results.append(("페이지 오류 0건 (모든 장면)", not R.errors, "; ".join(R.errors)[:300]))
        browser.close()

    w = max(len(n) for n, _, _ in R.results)
    print(f"\n뱁새 스모크 테스트 결과 · 데이터: {os.path.abspath(args.data)}" + ("" if full else " (국고채 커브 없는 데이터)"))
    for name, ok, msg in R.results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in R.results if not r[1]]
    print(f"\n{len(R.results) - len(bad)} / {len(R.results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
