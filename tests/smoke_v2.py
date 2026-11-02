#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뱁새 2.0 미리 보기(app.html) 스모크 테스트 — 사이트를 로컬에서 띄우고 헤드리스 크롬으로 휴대폰 크기(320·390)에서 눌러봐요.

  python tests/smoke_v2.py              # tests/fixtures/v2 의 데이터로 (실제 실행본 + v17.5.1 에 들어올 필드를 합성)
  python tests/smoke_v2.py --shots DIR  # 실패하면 스크린샷

장면(시나리오)마다 새 브라우저 문맥을 열어요.
  정상        모든 탭 · 시작 덱으로 덱 짜기 끝까지 · 빈 덱으로 덱 짜기 끝까지 · 샀어요 → 새로 고침해도 기록이 남음 ·
              기록 내보내기 → 지우기 → 불러오기 · 지킬 수 없는 설정은 막힘 · 화면마다 내용 날짜 · 가로 스크롤 없음
  멈춤        발행 6일 전 → 오늘에 '데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요', 날짜 줄에 멈춤 표시
  옛 형식     pxDate·publishedAt 없는 데이터 → 불러오기 실패 문구 (예시 데이터 없음)
  실패        data.json 404 · corp.json 깨짐 → 불러오기 실패 문구
  필드 없음   ind · val20 이 없는 데이터 → 덱 짜기가 '준비 중'만 보여요 (순위·비중을 만들지 않음)
  저장 불가   브라우저 저장소가 막힘 → '이 기기에서는 기록을 저장할 수 없어요…'
  매일 점검   (Part C) 저장된 덱 + 산 뒤에 나온 2025년 보고서: 매도 조건(실제로 줄였어요 → 규칙 깨짐, 새로 고침해도 남음) ·
              줄인 게 아니에요 → 해제 · 지켜봐요(부채비율) · 확인 필요(배당 감소 · 자료 없음) · 비중 벗어남 · 할 일 없음 ·
              큰 움직임은 표시만 · '아직 자동으로 확인하지 못하는 규칙' 줄 · 멈춘 데이터와 불러오기 실패에서는 판정 없음
  오늘·내 덱  (Part E) 덱 하나씩: 매도 조건(받침 있는 이름 → '…이 매도 조건에 걸렸어요') · 지켜봐요 → 초록 띠 · 확인 필요 →
              살구 띠의 두 버튼 → 답하면 초록 띠 · 줄일 차례 → 초록 띠, '오늘은 할 일이 없어요' 없음 · 큰 움직임(업종이 다 같이
              빠짐) → 자세히 보기 → 왜 움직였나(점 띠 · 규칙 · 데이터 출처) → 오늘 · 내 덱의 평가 금액 · 원금 · 코스피와 비교 ·
              비중 막대 · 추가로 넣을 돈(지켜봐요는 건너뜀) · 옛 형식·불러오기 실패·멈춤이면 할 일 띠 없음 · '못 하는 규칙' 줄
모든 장면에서 페이지 오류 0건, 다른 사이트 요청 0건. 화면에 보이는 한국어는 모두 src/copy/v2.js(또는 데이터의 이름)에서 와요.
"""
import argparse
import datetime as dt
import functools
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copytrace import Matcher, copy_strings, HANGUL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
SITE_FILES = ["baepsae.html", "sw.js", "icon-192.png"] + [f"baepi-{i}.png" for i in range(1, 10)]   # app.html 은 지금 소스로 빌드해요
DATA_FILES = ["data.json", "corp.json", "macro.json"]
WAIT = 15000
KST = dt.timezone(dt.timedelta(hours=9))
WHOLE_BAD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")   # \b 는 'NaN원'을 놓쳐요
SLOT_LEFT = re.compile(r"\{\w+\}")                                                        # 채우지 못한 {자리}
# 오늘 화면이 매일 점검해요(Part E) · 규칙 고치기는 아직 없어서 '매일 이 규칙으로 점검하고, 규칙은 언제든 고칠 수 있어요'는 약속하지 않아요
NO_PROMISE = ["매일 이 규칙으로", "언제든 고칠 수"]

C, _ = copy_strings()
LOAD_FAIL = C["app"]["loadFail"]


def now_kst(days_ago=0):
    return (dt.datetime.now(KST) - dt.timedelta(days=days_ago)).isoformat(timespec="seconds")


def read_fixtures():
    out = {}
    for f in DATA_FILES:
        with open(os.path.join(FIX, f), encoding="utf-8") as fh:
            out[f] = json.load(fh)
    for f in DATA_FILES:
        out[f]["publishedAt"] = now_kst()
    return out


def clone(x):
    return json.loads(json.dumps(x))


def build_site(files, raw=None, drop=()):
    site = tempfile.mkdtemp(prefix="baepsae-v2-")
    for f in SITE_FILES:
        shutil.copy(os.path.join(ROOT, f), site)
    shutil.copy(os.path.join(ROOT, "app.html"), site)     # 커밋한 app.html (test_v2_app 이 소스와 같은지 확인해요)
    shutil.copytree(os.path.join(ROOT, "fonts"), os.path.join(site, "fonts"))
    for name, obj in files.items():
        if name in drop:
            continue
        with open(os.path.join(site, name), "w", encoding="utf-8") as fh:
            fh.write(raw[name] if raw and name in raw else json.dumps(obj, ensure_ascii=False))
    return site


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def serve(site):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def chromium_path():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


class Runner:
    def __init__(self, browser, shots, names):
        self.browser, self.shots = browser, shots
        self.results, self.errors, self.outside = [], [], []
        self.texts = set()
        self.names = sorted({n for n in names if n and HANGUL.search(n)}, key=len, reverse=True)

    def open(self, site, width, init=None, accept_downloads=False):
        srv, base = serve(site)
        ctx = self.browser.new_context(viewport={"width": width, "height": 780}, device_scale_factor=2, locale="ko-KR",
                                       service_workers="block", accept_downloads=accept_downloads)

        def route(r):
            if r.request.url.startswith(base):
                r.continue_()
                return
            try:
                frame = r.request.frame.url
            except Exception:
                frame = ""
            if "/baepsae.html" not in frame:      # 찾기 탭으로 연 지금 앱의 글꼴·통계 요청은 app.html 몫이 아니에요
                self.outside.append(r.request.url)
            r.abort()
        ctx.route("**/*", route)
        if init:
            ctx.add_init_script(init)
        page = ctx.new_page()
        page.set_default_timeout(WAIT)
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(base + "/app.html?dev=1", wait_until="domcontentloaded")
        return srv, ctx, page, base

    def check(self, page, scene, name, fn):
        label = f"[{scene}] {name}"
        try:
            fn()
            self.results.append((label, True, ""))
        except Exception as e:
            msg = (str(e).splitlines() or [type(e).__name__])[0]     # 메시지 없는 assert 도 이름으로 남겨요
            self.results.append((label, False, msg[:200]))
            if self.shots:
                os.makedirs(self.shots, exist_ok=True)
                try:
                    page.screenshot(path=os.path.join(self.shots, f"v2-fail-{len(self.results)}.png"), full_page=True)
                except Exception:
                    pass
        print(f"  {'PASS' if self.results[-1][1] else 'FAIL'}  {label}", flush=True)

    def collect(self, page):
        """지금 화면에 보이는 글(글자 · aria-label · alt · placeholder)을 모아 둬요. 끝에서 한꺼번에 출처를 확인해요."""
        got = page.evaluate("""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (w.nextNode()) { const n = w.currentNode; const e = n.parentElement; if (!e || e.closest('script, style')) continue;
              const r = e.getBoundingClientRect(); if (!r.width && !r.height) continue; const t = n.textContent; if (t.trim()) out.push(t); }
            for (const e of document.querySelectorAll('[aria-label],[alt],[placeholder]'))
              for (const a of ['aria-label', 'alt', 'placeholder']) { const v = e.getAttribute(a); if (v) out.push(v); }
            return out; }""")
        self.texts |= {t.strip() for t in got if t.strip()}
        body = page.locator("body").inner_text()
        bad = WHOLE_BAD.findall(body)
        assert not bad, f"화면에 nan·null 같은 낱말: {bad}"
        left = SLOT_LEFT.findall(body + " ".join(got))
        assert not left, f"채우지 못한 자리: {left}"
        promise = [w for w in NO_PROMISE if w in body]
        assert not promise, f"아직 없는 기능(규칙 고치기)을 약속해요: {promise}"

    def unnamed(self, t):
        for n in self.names:
            if n in t:
                t = t.replace(n, "{}")
        return t


# ── 화면 조작 ──
def see(page, text, timeout=WAIT):
    page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)


def tab(page, label):
    """아래 탭을 눌러요. 첫 화면이 덱 짜기면(저장한 덱이 없는 방문자) 아래 탭이 없어서, 먼저 오늘로 돌아가요."""
    bar = page.locator('nav[data-ui="bottom-tab-bar"]')
    if bar.count() == 0:
        if label == C["app"]["tabs"]["build"]:
            return
        page.get_by_role("button", name=C["build"]["backToday"]).click()
    bar.locator("button", has_text=label).click()


def old_app_link(page):
    link = page.locator('[data-ui-v2="old-app-link"]').first
    link.wait_for(state="visible")
    assert link.inner_text() == C["app"]["oldApp"] and link.get_attribute("href") == "./baepsae.html"


def action(page):
    return page.locator('[data-ui-v2="action-bar"] button')


def no_hscroll(page, width):
    sw = page.evaluate("document.documentElement.scrollWidth")
    assert sw <= width, f"가로 스크롤: scrollWidth {sw} > {width}"


def date_line(page):
    loc = page.locator('[data-ui-v2="date-line"]').first
    loc.wait_for(state="visible")
    return loc.inner_text()


def wait_ready(page):
    page.locator('[data-ui-v2="date-line"], [data-ui-v2="load-fail"]').first.wait_for(state="visible")


def click_next(page):
    b = action(page)
    b.wait_for(state="visible")
    assert b.is_enabled(), f"다음 버튼이 꺼져 있어요: {b.inner_text()}"
    b.click()
    page.wait_for_timeout(150)


# ── 장면 ──
def scene_normal(R, files, width):
    S = f"정상 {width}"
    srv, ctx, page, base = R.open(build_site(files), width, accept_downloads=True)
    md = "10월 30일"

    def landing():
        wait_ready(page)
        see(page, C["build"]["s0"]["title"])                 # 저장한 덱이 없으면 덱 짜기부터
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        old_app_link(page)
        assert page.locator('[data-ui-v2="old-app-note"]').count() == 0, "예전 뱁새 기록이 없는데 안내가 보여요"
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "첫 화면: 저장한 덱이 없으면 덱 짜기 · 머리말에 '예전 뱁새 보기'", landing)

    def today():
        tab(page, C["app"]["tabs"]["today"])
        see(page, C["app"]["title"])
        assert md in date_line(page) and "멈췄어요" not in date_line(page)
        page.locator('[data-ui-v2="today-empty"]').wait_for(state="visible")       # 산 종목이 없으면 판정 없이 덱 짜기로 가는 길만
        assert page.locator('[data-ui-v2="today-hero"]').count() == 0
        assert page.get_by_text("할 일").count() == 0, "점검한 종목이 없는데 '할 일'이 보여요"
        assert page.title() == C["app"]["title"]
        old_app_link(page)
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "오늘: 제목·내용 날짜 · 산 종목이 없으면 판정 없음 (할 일 없음도 아님)", today)

    def my_deck():
        tab(page, C["app"]["tabs"]["deck"])
        see(page, C["store"]["export"])
        assert md in date_line(page)
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "탭: 내 덱 (기록 내보내기·불러오기)", my_deck)

    def build_tab():
        tab(page, C["app"]["tabs"]["build"])
        see(page, C["build"]["s0"]["title"])
        assert md in date_line(page)
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        for hidden in ("steadyDiv", "cheapQuality", "payout", "theme", "divGrowth"):
            assert page.locator(f'[data-deck="{hidden}"]').count() == 0, f"숨겨야 할 시작 덱: {hidden}"
        assert page.locator("[data-deck]").count() == 9
        no_hscroll(page, width)
        R.collect(page)
        page.get_by_role("button", name=C["build"]["backToday"]).click()
        see(page, C["today"]["title"])
    R.check(page, S, "탭: 덱 짜기 (시작 덱 8개 + 처음부터) → 뒤로 → 오늘", build_tab)

    def search_tab():
        with page.expect_navigation():
            tab(page, C["app"]["tabs"]["search"])
        assert page.url.endswith("/baepsae.html"), page.url
        page.goto(base + "/app.html?dev=1", wait_until="domcontentloaded")
        wait_ready(page)
    R.check(page, S, "탭: 찾기 → 지금 앱(baepsae.html)", search_tab)

    def from_starting_deck():
        tab(page, C["app"]["tabs"]["build"])
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        assert page.locator('[data-ui-v2="points-left"]').inner_text() == "0"
        assert page.locator('[data-card="divGrowth"]').get_by_text(C["app"]["pending"]).count() == 1
        assert page.locator('[data-card="div"]').get_by_text("상위 50%").count() == 1
        see(page, C["build"]["s1"]["preview"])
        assert re.search(r"\d", page.locator('[data-ui-v2="match-count"]').inner_text())
        R.collect(page)
        no_hscroll(page, width)
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        assert page.get_by_role("switch", name=C["build"]["s3"]["switches"]["warned"]["name"]).is_disabled()
        R.collect(page)
        no_hscroll(page, width)
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        see(page, C["build"]["s4"]["amountEmpty"])
        page.get_by_role("button", name="+1,000만").first.click()
        see(page, "2022년 같은 해가 오면")
        page.locator('[data-ui-v2="y2022-methods"]').get_by_text("약 ").first.wait_for(state="visible")
        R.collect(page)
        no_hscroll(page, width)
        assert "후보" in action(page).inner_text()
        click_next(page)
        see(page, C["pick"]["title"])
        assert md in date_line(page)
        assert action(page).is_enabled() and action(page).inner_text() == C["pick"]["makePlan"]
        assert page.locator("[data-cand][data-picked='1']").count() == 6
        first_kr = page.locator("section[data-market='kr'] [data-cand]").first
        first_kr.get_by_role("button", name=C["pick"]["receipts"]).click()
        see(page, "2025년 사업보고서 기준")
        R.collect(page)
        no_hscroll(page, width)
        click_next(page)
        see(page, C["plan"]["stocks"])
        assert md in date_line(page)
        assert page.locator("[data-row]").count() == 6
        see(page, C["plan"]["y2022Note"])
        see(page, "종가와 환율")
        rules = page.locator('[data-ui-v2="rules"] [data-ui="collapsible"]')
        assert rules.count() == 6
        for i in range(rules.count()):
            rules.nth(i).locator("button").first.click()
        page.locator("[data-rules-for] [data-check='pending']").first.wait_for(state="visible")
        checked = page.locator("[data-rules-for] [data-check='checked']")
        assert checked.count() >= 1
        assert page.locator("[data-ui-v2='rule-line'][data-icon='check']").count() == 0, "매일 점검 전인데 초록 확인 표시가 있어요"
        for i in range(checked.count()):
            assert re.search(r"\d", checked.nth(i).inner_text()), f"숫자 없는 확인 규칙: {checked.nth(i).inner_text()!r}"
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, S, "시작 덱(배당 생활비)으로 끝까지: 기준 → 빼기 → 조건 → 후보 6개 → 매수 계획·규칙", from_starting_deck)

    def bought():
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        R.collect(page)
        sheet = page.locator('[data-ui-v2="record-form"]')
        date = sheet.locator('input[type="date"]')
        date.fill("2099-01-02")                                       # 미래 날짜는 기록하지 않아요
        page.get_by_role("button", name=C["plan"]["save"]).click()
        assert date.get_attribute("aria-invalid") == "true" and page.get_by_text(C["plan"]["done"]).count() == 0
        date.fill("")
        qty = sheet.locator("[data-record] input").first
        qty.fill("1.5")                                               # 소수 주식도 받지 않아요
        page.get_by_role("button", name=C["plan"]["save"]).click()
        assert qty.get_attribute("aria-invalid") == "true" and page.get_by_text(C["plan"]["done"]).count() == 0
        assert page.evaluate("localStorage.getItem('baepsae2.v1')") is None, "틀린 입력인데 저장했어요"
        qty.fill("")
        page.get_by_role("button", name=C["plan"]["save"]).click()
        see(page, C["plan"]["done"])
        see(page, "내일부터 오늘 화면에서 6종목을 규칙대로 점검해 드릴게요.")          # Part E: 오늘 화면이 정말 점검해요
        R.collect(page)
        page.get_by_role("button", name=C["plan"]["doneLink"]).click()
        see(page, C["today"]["title"])
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        assert stored["v"] == 1 and len(stored["decks"]) == 1 and len(stored["decks"][0]["purchases"]) == 6, stored
        us_buys = [p for p in stored["decks"][0]["purchases"] if p["ccy"] == "USD"]
        assert all(p.get("fx") == files["data.json"]["fx"] for p in us_buys), us_buys      # 미국 매수는 계획의 환율과 함께
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        hero = page.locator('[data-ui-v2="today-hero"]')                      # 저장한 덱이 있으면 오늘부터, 판정 띠와 함께
        hero.wait_for(state="visible")
        assert hero.get_attribute("data-state") == "calm", hero.inner_text()     # 산 날: 매도 조건도 확인할 일도 없어요
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", hero.inner_text()), hero.inner_text()
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 1 and page.get_by_text(C["build"]["s0"]["title"]).count() == 0
        R.collect(page)
        tab(page, C["app"]["tabs"]["deck"])
        see(page, "배당 생활비 덱")
        see(page, "내 종목 6개")
        old_app_link(page)
        assert page.get_by_text("평균 단가").count() == 6
        # 계획대로 산 첫날: 비중 표시 없음 (모두 할 일 없음) · 비중 막대 6개 · 평가 금액 · 원금 · 코스피와 비교
        st = page.locator("[data-holding][data-status]").evaluate_all("els => els.map(e => e.dataset.status)")
        assert st == ["none"] * 6, st
        assert page.locator('[data-ui-v2="weight"]').count() == 6 and page.locator('[data-ui-v2="weight"][data-band]').count() == 0
        page.locator('[data-ui-v2="deck-value"]').wait_for(state="visible")
        assert re.fullmatch(r"원금 [\d,]+만원 · 수익 [+−]?[\d,]+(만원|원) \([+−]?[\d,]+\.\d%\)", page.locator('[data-ui-v2="deck-money"]').inner_text()), \
            page.locator('[data-ui-v2="deck-money"]').inner_text()
        assert page.locator('[data-ui-v2="vs-index"]').inner_text().startswith("코스피 ")
        add = page.locator('[data-ui-v2="add-money"]')
        add.get_by_role("button", name="+100만").click()
        page.locator('[data-ui-v2="add-buys"], [data-ui-v2="add-none"]').first.wait_for(state="visible")
        assert add.locator('[data-ui-v2="add-none-eligible"]').count() == 0      # 첫날 건너뛰는 종목 없음 → 살 수 있는 종목이 있어요
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "샀어요 → 기록하기 → 새로 고침: 오늘 판정 띠 · 내 덱 기록·비중·원금·코스피·추가로 넣을 돈 (첫날 비중 표시 없음)", bought)

    def round_trip():
        with page.expect_download() as d:
            page.get_by_role("button", name=C["store"]["export"]).click()
        path = d.value.path()
        with open(path, encoding="utf-8") as fh:
            exported = json.load(fh)
        assert exported["v"] == 1 and len(exported["decks"]) == 1
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        tab(page, C["app"]["tabs"]["deck"])
        see(page, C["store"]["export"])
        assert page.get_by_text("배당 생활비 덱").count() == 0
        page.locator('[data-ui-v2="import-file"]').set_input_files(path)
        see(page, "배당 생활비 덱")
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        tab(page, C["app"]["tabs"]["deck"])
        see(page, "내 종목 6개")
        bad = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(bad, "w") as fh:
            fh.write('{"hello": 1}')
        page.locator('[data-ui-v2="import-file"]').set_input_files(bad)
        page.locator('[data-ui-v2="import-bad"]').wait_for(state="visible")
        assert page.get_by_text("내 종목 6개").count() == 1, "잘못된 파일이 기록을 지웠어요"
        R.collect(page)
    R.check(page, S, "기록 내보내기 → 지우기 → 불러오기 (잘못된 파일은 기록을 건드리지 않음)", round_trip)

    def from_blank():
        tab(page, C["app"]["tabs"]["build"])
        page.locator('[data-deck="blank"]').click()
        see(page, C["build"]["s1"]["title"])
        assert not action(page).is_enabled() and action(page).inner_text() == C["build"]["pickCardsBtn"]
        for card, n in (("profit", 5), ("stable", 3), ("value", 2)):
            for _ in range(n):
                page.locator(f'[data-card="{card}"] button[aria-label*="점수 더하기"]').click()
        assert page.locator('[data-ui-v2="points-left"]').inner_text() == "0"
        assert page.locator('[data-card="growth"] button[aria-label*="점수 더하기"]').is_disabled()
        see(page, C["build"]["s1"]["finNA"])
        R.collect(page)
        click_next(page)
        page.get_by_role("switch", name=C["build"]["s3"]["switches"]["holding"]["name"]).click()
        assert page.get_by_role("switch", name=C["build"]["s3"]["switches"]["holding"]["name"]).get_attribute("aria-checked") == "true"
        click_next(page)
        page.get_by_role("radio", name="한국만").click()
        grid = page.locator('[data-ui-v2="choice-grid"] button')
        hs = [grid.nth(i).bounding_box()["height"] for i in range(grid.count())]
        assert grid.count() == 5 and max(hs) <= 46, f"한국 : 미국 버튼이 줄을 바꿔요: {hs}"
        page.get_by_role("button", name="+1,000만").first.click()
        pin_box = page.locator('[data-ui-v2="pinned"] input')
        pin_box.fill("005935")                                        # 우선주: 순위에는 없지만 꼭 담을 수 있어요
        page.get_by_role("button", name="삼성전자우 담기").click()
        added = page.locator('[data-ui-v2="pinned"] [data-ui-v2="manual-chip"]')
        added.first.wait_for(state="visible")
        assert added.count() == 1 and added.inner_text() == C["pick"]["manual"], \
            f"조건 단계의 꼭 담을 종목에 '직접 추가' 하나만 있어야 해요: {added.all_inner_texts()}"   # Jack, 2026-11-01
        assert "고정" not in page.locator('[data-ui-v2="pinned"]').inner_text(), "조건 단계에 '고정'이 남아 있어요"
        R.collect(page)
        click_next(page)
        see(page, C["pick"]["title"])
        assert page.locator("section[data-market='us']").count() == 0
        pinned = page.locator("[data-pinned='005935']")
        pinned.wait_for(state="visible")
        assert pinned.locator('[data-ui-v2="manual-chip"]').inner_text() == C["pick"]["manual"], "후보 고르기에 '직접 추가'가 없어요"
        assert "고정" not in pinned.inner_text(), "직접 담은 종목에 '고정'이 남아 있어요"
        assert pinned.locator('[data-ui-v2="manual-note"]').count() == 0, "근거 수치를 열기 전에 문장이 보여요"
        pinned.get_by_role("button", name=C["pick"]["receipts"]).click()
        assert pinned.locator('[data-ui-v2="manual-note"]').inner_text() == C["pick"]["manualNote"]
        scored = page.locator("[data-cand]").first                   # 점수로 고른 후보: 근거 수치를 열어도 그 문장이 없어요
        scored.get_by_role("button", name=C["pick"]["receipts"]).click()
        scored.locator('[data-ui-v2="receipts"]').wait_for(state="visible")
        assert scored.locator('[data-ui-v2="manual-note"]').count() == 0, "점수로 고른 후보에 '직접 담은 종목' 문장이 붙었어요"
        scored.get_by_role("button", name=C["pick"]["receipts"]).click()
        assert page.locator('[data-cand] [data-ui-v2="manual-chip"]').count() == 0, "점수로 고른 후보에 '직접 추가'가 붙었어요"
        assert page.locator("[data-cand][data-picked='1']").count() == 5
        # 빼고 넣기: 하나 빼면 버튼이 꺼지고, 다시 넣으면 켜져요
        first = page.locator("[data-cand][data-picked='1']").first
        t = first.get_attribute("data-cand")
        first.locator("button[aria-pressed='true']").click()
        assert not action(page).is_enabled()
        page.locator(f"[data-cand='{t}'] button[aria-pressed='false']").click()
        assert action(page).is_enabled()
        R.collect(page)
        click_next(page)
        see(page, C["plan"]["stocks"])
        assert page.locator("[data-row]").count() == 6
        assert page.locator('[data-ui-v2="clash"]').count() == 0
        R.collect(page)
    R.check(page, S, "빈 덱으로 끝까지: 카드 10점 → 지주회사 빼기 → 한국만 → 후보 → 매수 계획", from_blank)

    def infeasible():
        page.get_by_role("button", name=C["plan"]["back"]).click()
        page.get_by_role("button", name=C["pick"]["back"]).click()
        see(page, C["build"]["s4"]["title"])
        for _ in range(3):
            dec = page.get_by_role("button", name=C["build"]["s4"]["countDec"])
            if dec.is_enabled():
                dec.click()
        page.locator('[data-ui="segmented"][aria-label="%s"]' % C["build"]["s4"]["maxLabel"]).get_by_role("radio", name="10%").click()
        page.locator('[data-ui-v2="clash"]').wait_for(state="visible")
        txt = page.locator('[data-ui-v2="clash"]').inner_text()
        assert "종목 수" in txt and "한 종목 최대 10%" in txt, txt
        assert not action(page).is_enabled(), "막혔는데 후보 고르기로 갈 수 있어요"
        # 설정이 부딪힌 것이라 '기준을 낮춰 주세요'는 틀린 조언이에요: 버튼은 '후보 n개 보기'(꺼짐), 조건은 위 줄에서
        assert action(page).inner_text() != C["build"]["lowerBtn"] and action(page).inner_text().startswith("후보"), action(page).inner_text()
        R.collect(page)
    R.check(page, S, "지킬 수 없는 설정(5종목 × 최대 10%) → 조건 단계에서 막고 부딪히는 조건을 보여요", infeasible)
    ctx.close()
    srv.shutdown()


def scene_stale(R, files, width):
    f = clone(files)
    for n in DATA_FILES:
        f[n]["publishedAt"] = now_kst(days_ago=6)
    srv, ctx, page, _ = R.open(build_site(f), width)

    def run():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["today"])
        see(page, "데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요")
        dl = page.locator('[data-ui-v2="date-line"]').first
        assert dl.get_attribute("data-stale") == "1" and "6일째 갱신이 멈췄어요" in dl.inner_text(), dl.inner_text()
        assert page.get_by_text("할 일").count() == 0
        R.collect(page)
    R.check(page, f"멈춤 {width}", "발행 6일 전 → 오늘은 점검하지 않았다고 말하고, 날짜 줄에 멈춤 표시", run)
    ctx.close()
    srv.shutdown()


def scene_refused(R, files, width, how):
    f = clone(files)
    raw, drop = None, ()
    if how == "옛 형식":
        for n in ("data.json", "corp.json"):
            f[n].pop("pxDate", None)
            f[n].pop("publishedAt", None)
    elif how == "404":
        drop = ("data.json",)
    else:
        text = json.dumps(f["corp.json"], ensure_ascii=False)
        raw = {"corp.json": text[: len(text) // 2]}
    srv, ctx, page, _ = R.open(build_site(f, raw=raw, drop=drop), width)

    def run():
        see(page, LOAD_FAIL)
        assert page.locator('[data-ui-v2="date-line"]').count() == 0
        tab(page, C["app"]["tabs"]["build"])
        see(page, LOAD_FAIL)
        assert page.locator("[data-deck]").count() == 0, "불러오지 못했는데 덱 짜기가 열려요"
        R.collect(page)
    R.check(page, f"{how} {width}", "불러오기 실패 문구 (오늘 · 덱 짜기), 예시 데이터 없음", run)
    ctx.close()
    srv.shutdown()


def scene_missing_fields(R, files, width, fields):
    f = clone(files)
    for s in f["data.json"]["stocks"]:
        for k in fields:
            s.pop(k, None)
    srv, ctx, page, _ = R.open(build_site(f), width)

    def run():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["build"])
        page.locator('[data-ui-v2="build-not-ready"]').wait_for(state="visible")
        see(page, C["app"]["pending"])
        assert page.locator("[data-deck]").count() == 0 and page.locator("[data-cand]").count() == 0
        R.collect(page)
    R.check(page, f"필드 없음 {width}", f"{', '.join(fields)} 없음 → 덱 짜기는 '준비 중'만", run)
    ctx.close()
    srv.shutdown()


def scene_us_date(R, files, width):
    f = clone(files)
    f["data.json"]["usPxDate"] = "2026-10-29"
    srv, ctx, page, _ = R.open(build_site(f), width)

    def run():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["build"])
        page.locator('[data-deck="quality"]').click()          # 한국 7 : 미국 3 · 미국 종목이 들어가요
        click_next(page)
        click_next(page)
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        see(page, "미국 종목은 현지 기준 10월 29일 종가예요.")
        assert "10월 30일" in date_line(page)
        R.collect(page)
    R.check(page, f"미국 날짜 {width}", "미국 종가 날짜가 다르면 후보 고르기에 '미국 종목은 현지 기준 10월 29일 종가예요.'", run)
    ctx.close()
    srv.shutdown()


def scene_old_app(R, files, width, slots, expect):
    """예전 뱁새(baepsae.html)에 포트폴리오가 있는 방문자: 덱 짜기 첫 화면과 내 덱에 '예전 뱁새 보기' 안내 (Jack, 2026-11-01).
    예전 기록은 읽기만 하고 그대로 둬요."""
    init = f"(() => {{ try {{ localStorage.setItem('baepsae_v10_slots', {json.dumps(slots)}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)

    def run():
        wait_ready(page)
        see(page, C["build"]["s0"]["title"])
        note = page.locator('[data-ui-v2="old-app-note"]')
        if not expect:
            assert note.count() == 0, f"덱 짜기에 안내가 보이면 안 돼요: {slots!r}"
        else:
            assert note.inner_text() == C["app"]["oldAppNote"]
            old_app_link(page)                                       # 안내가 가리키는 머리말 링크
        tab(page, C["app"]["tabs"]["deck"])
        see(page, C["store"]["export"])
        if not expect:
            assert note.count() == 0, f"내 덱에 안내가 보이면 안 돼요: {slots!r}"
        else:
            assert note.inner_text() == C["app"]["oldAppNote"]
        assert page.evaluate("localStorage.getItem('baepsae_v10_slots')") == slots, "예전 기록을 바꿨어요"
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, f"예전 기록 {width}", f"예전 뱁새 기록 {slots[:24]!r} → 안내 {'보임' if expect else '없음'}", run)
    ctx.close()
    srv.shutdown()


def scene_no_storage(R, files, width):
    init = "(() => { const s = Storage.prototype.setItem; Storage.prototype.setItem = function () { throw new Error('blocked'); }; })();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)

    def run():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["deck"])
        see(page, C["store"]["unavailable"])
        assert page.get_by_role("button", name=C["store"]["import"]).is_disabled()
        R.collect(page)
    R.check(page, f"저장 불가 {width}", "저장소가 막히면 '이 기기에서는 기록을 저장할 수 없어요…'", run)
    ctx.close()
    srv.shutdown()


# ── 매일 점검 (Part C) ──
# 산 날(2024년 보고서 기준, since 2024)에 만든 규칙 책을 저장해 두고, 오늘 데이터(2025년 보고서)로 점검해요.
# 규칙 책은 engine.js ruleBook 이 만드는 모양 그대로예요 (같은 칸 이름).
def _pending(*ids):
    return [{"id": i, "kind": "sell", "check": "pending"} for i in ids]


def _band(target):
    return {"id": "band", "kind": "band", "check": "checked", "target": target, "bands": [0.75 * target, 1.25 * target, 1.4 * target]}


def _div(since, dps, prev):
    return {"id": "divCut", "kind": "sell", "check": "checked", "input": "dps", "baseline": dps, "since": since, "dps": dps,
            "prev": prev, "fy": since, "streak": 0, "droppedBefore": dps < prev}


def _debt(since, debt, limit):
    return {"id": "debtCeiling", "kind": "keep", "check": "checked", "input": "debt", "baseline": debt, "since": since, "debt": debt,
            "limit": limit, "fy": since}


def _holding(t, nk, target, rules):
    return {"t": t, "nk": nk, "cls": "kr", "ind": None, "kind": "core", "target": target, "plannedQty": 1,
            "rules": rules + _pending("audit", "embezzle", "acquisition") + [_band(target)]}


def _deck(i, name, rows):
    return {"id": i, "name": name, "createdAt": "2026-10-01", "holdings": [_holding(t, nk, tg, r) for t, nk, tg, r, _ in rows],
            "purchases": [{"t": t, "date": "2026-10-01", "qty": q, "price": 1000, "ccy": "KRW"} for t, _, _, _, q in rows]}


SAMSUNG = ("005930", "삼성전자")
DAILY_DECKS = {"v": 1, "decks": [
    _deck("dcut", "확인 덱", [("005380", "현대차", 0.5, [_div(2024, 12000.0, 11400.0)], 1), (*SAMSUNG, 0.5, [_div(2025, 1668.0, 1446.0)], 1)]),
    _deck("dclear", "해제 덱", [("005380", "현대차", 0.5, [_div(2024, 12000.0, 11400.0)], 1), (*SAMSUNG, 0.5, [_div(2025, 1668.0, 1446.0)], 1)]),
    _deck("dwatch", "부채 덱", [("012450", "한화에어로스페이스", 0.5, [_debt(2024, 150.0, 200)], 1), (*SAMSUNG, 0.5, [], 3)]),
    _deck("dmiss", "자료 덱", [("000270", "기아", 0.5, [_debt(2024, 60.0, 100)], 7), (*SAMSUNG, 0.5, [], 3)]),
    _deck("dband", "비중 덱", [(*SAMSUNG, 0.5, [], 4), ("035420", "NAVER", 0.5, [], 1)]),
    _deck("dcalm", "조용한 덱", [("000660", "SK하이닉스", 0.5, [], 1), (*SAMSUNG, 0.5, [_div(2025, 1668.0, 1446.0)], 6)]),
]}


def daily_files(files, days_ago=0):
    f = clone(files)
    for n in DATA_FILES:
        f[n]["publishedAt"] = now_kst(days_ago=days_ago)
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    for t in ("005930", "005380", "012450", "000270", "035420", "000660"):
        by[t]["d1"] = 0.5                                                   # 큰 움직임은 SK하이닉스 하나만
        by[t]["fy"] = 2025
    by["005380"].update(dps=10000.0, dps3=[10000.0, 12000.0, 11400.0])   # 2025년 보고서: 12,000 → 10,000원
    by["012450"]["debt"] = 221.0                                          # 기준 200% 넘음
    by["000270"].pop("debt", None)                                        # 산 때 있던 부채비율이 오늘 비었어요
    by["000660"]["d1"] = -6.2
    return f


def scene_daily(R, files, width):
    S = f"매일 점검 {width}"
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(daily_files(files)), width, init=init)
    deck = lambda i: page.locator(f'[data-deck-id="{i}"]')
    row = lambda i, t: deck(i).locator(f'[data-holding="{t}"]')

    def open_deck():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["deck"])
        see(page, "조용한 덱")
        page.locator("[data-holding][data-status]").first.wait_for(state="visible")

    def statuses():
        open_deck()
        st = {(i, t): row(i, t).get_attribute("data-status") for i, t in
              (("dcut", "005380"), ("dclear", "005380"), ("dwatch", "012450"), ("dmiss", "000270"), ("dband", "005930"),
               ("dband", "035420"), ("dcalm", "000660"), ("dcalm", "005930"))}
        assert st == {("dcut", "005380"): "check", ("dclear", "005380"): "check", ("dwatch", "012450"): "watch",
                      ("dmiss", "000270"): "check", ("dband", "005930"): "trim", ("dband", "035420"): "low",
                      ("dcalm", "000660"): "none", ("dcalm", "005930"): "none"}, st
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "저장된 덱 6개 → 종목마다 상태 (확인 필요 · 지켜봐요 · 비중 · 할 일 없음)", statuses)

    def check_needed():
        r = row("dcut", "005380")
        line = r.locator('[data-ui-v2="status-line"][data-code="divDrop"]')
        assert "현대차 배당이 줄었어요 · 주당 12,000원 → 10,000원" in line.inner_text(), line.inner_text()
        assert C["pick"]["caution"]["divDropBody"] in line.inner_text() and "2025년 사업보고서 기준" in line.inner_text()
        assert r.locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["watch"]]      # 확인 필요는 지켜봐요로 보여요
        assert C["daily"]["broken"] not in deck("dcut").inner_text(), "확인 전인데 규칙 깨짐이 보여요"
        btns = r.locator('[data-ui-v2="confirm"] button')
        assert btns.all_inner_texts() == [C["daily"]["confirmCut"], C["daily"]["confirmNotCut"]]
        fold = row("dclear", "005380").locator('[data-ui="collapsible"]')
        fold.locator("button").first.click()
        div = fold.locator('[data-rules-today] [data-ui-v2="rule-line"]').first
        assert div.get_attribute("data-state") == "watch" and C["daily"]["broken"] not in fold.inner_text(), div.inner_text()
        R.collect(page)
        fold.locator("button").first.click()
    R.check(page, S, "배당 감소 → 확인 필요: 승인 문장 · 2025년 사업보고서 기준 · 두 버튼 (규칙 깨짐 아님)", check_needed)

    def keep_and_missing():
        w = row("dwatch", "012450")
        assert w.locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["watch"]]
        txt = w.locator('[data-ui-v2="status-line"][data-code="debtOver"]').inner_text()
        assert "부채비율 221% (기준 200%)" in txt and "2025년 사업보고서 기준" in txt, txt
        m = row("dmiss", "000270")
        assert "부채비율 자료를 받지 못해 확인이 필요해요" in m.locator('[data-ui-v2="status-line"][data-code="missing"]').inner_text()
        assert m.locator('[data-ui-v2="confirm"]').count() == 0
        R.collect(page)
    R.check(page, S, "부채비율 기준 넘음 → 지켜봐요 '부채비율 221% (기준 200%)' · 산 때 있던 자료가 비면 확인 필요", keep_and_missing)

    def bands_and_calm():
        hi = row("dband", "005930").locator('[data-ui-v2="status-line"][data-code="band"]').inner_text()
        lo = row("dband", "035420").locator('[data-ui-v2="status-line"][data-code="band"]').inner_text()
        assert "70.0% 넘으면 일부 팔아요" in hi and "37.5% 미만이면 먼저 사요" in lo, (hi, lo)
        assert row("dband", "005930").locator('[data-ui="status-chip"]').count() == 0     # 비중은 칩 없이 비중 줄로
        calm = deck("dcalm")
        assert calm.locator('[data-ui-v2="status-line"]').count() == 0
        assert row("dcalm", "000660").locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["bigMove"]]
        assert row("dcalm", "005930").locator('[data-ui="status-chip"]').count() == 0       # 칩이 없으면 괜찮은 종목
        nc = calm.locator('[data-ui-v2="not-checked"]').inner_text()
        assert re.fullmatch(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", nc), nc
        assert page.locator('[data-ui-v2="not-checked"]').count() == 6
        R.collect(page)
    R.check(page, S, "비중 벗어남 · 할 일 없음(칩 없음) · 큰 움직임은 칩만 · '아직 자동으로 확인하지 못하는 규칙' 줄", bands_and_calm)

    def confirm_cut():
        row("dcut", "005380").get_by_role("button", name=C["daily"]["confirmCut"]).click()
        r = row("dcut", "005380")
        page.wait_for_function("() => document.querySelector('[data-deck-id=\"dcut\"] [data-holding=\"005380\"]').dataset.status === 'broken'")
        assert r.locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["broken"]]
        txt = r.locator('[data-ui-v2="status-line"][data-code="divCut"]').inner_text()
        assert "배당 삭감 · 주당 12,000원 → 10,000원" in txt and C["daily"]["sellNow"] in txt and "2025년 사업보고서 기준" in txt, txt
        assert row("dclear", "005380").get_attribute("data-status") == "check", "다른 덱의 같은 종목까지 바뀌었어요"
        r.locator('[data-ui="collapsible"] button').first.click()
        line = r.locator('[data-rules-today] [data-ui-v2="rule-line"][data-state="broken"]')
        assert line.count() == 1 and C["daily"]["broken"] in line.inner_text()
        assert r.locator('[data-rules-today] [data-check="pending"]').count() >= 2
        R.collect(page)
        page.reload(wait_until="domcontentloaded")
        open_deck()
        assert row("dcut", "005380").get_attribute("data-status") == "broken", "새로 고침하니 답이 사라졌어요"
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        cs = [d.get("confirms") for d in stored["decks"] if d["id"] == "dcut"][0]
        assert len(cs) == 1 and cs[0]["answer"] == "cut" and (cs[0]["fy"], cs[0]["a"], cs[0]["b"]) == (2025, 12000, 10000), cs
    R.check(page, S, "실제로 줄였어요 → 규칙 깨짐 '배당 삭감 · 주당 12,000원 → 10,000원' · 새로 고침해도 남아요", confirm_cut)

    def confirm_clear():
        row("dclear", "005380").get_by_role("button", name=C["daily"]["confirmNotCut"]).click()
        page.wait_for_function("() => document.querySelector('[data-deck-id=\"dclear\"] [data-holding=\"005380\"]').dataset.status === 'none'")
        r = row("dclear", "005380")
        assert r.locator('[data-ui-v2="confirm"]').count() == 0 and r.locator('[data-ui="status-chip"]').count() == 0
        assert row("dcut", "005380").get_attribute("data-status") == "broken"
        R.collect(page)
    R.check(page, S, "줄인 게 아니에요 → 그 보고서의 감소는 해제 (다른 덱은 그대로)", confirm_clear)

    def today_hero():
        tab(page, C["app"]["tabs"]["today"])
        hero = page.locator('[data-ui-v2="today-hero"]')
        hero.wait_for(state="visible")
        # 매도 조건(현대차, 실제로 줄였어요)과 확인 필요(기아, 부채비율 자료 없음)가 오늘 확인할 일이에요
        assert hero.get_attribute("data-state") == "todo", hero.inner_text()
        items = dict(hero.locator('[data-ui-v2="todo-item"]').evaluate_all("els => els.map(e => [e.dataset.t + ':' + e.dataset.status, 1])"))
        assert "005380:broken" in items and "000270:check" in items, items
        assert hero.locator('[data-ui-v2="todo-item"]').first.get_attribute("data-status") == "broken"     # 매도 조건이 맨 위
        txt = hero.inner_text()
        assert txt.startswith(f"오늘 확인할 일 {len(items)}개"), txt
        assert C["daily"]["sellNow"] in txt and C["today"]["sellLabel"] in txt and "배당 삭감 · 주당 12,000원 → 10,000원" in txt, txt
        assert "부채비율 자료를 받지 못해 확인이 필요해요" in txt and C["today"]["calmTitle"].replace("\n", "") not in txt.replace("\n", "")
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", txt)
        big = page.locator('[data-ui-v2="big-moves"]')                 # 큰 움직임은 판정과 따로, 표시만
        assert "SK하이닉스" in big.inner_text() and big.locator('[data-ui-v2="why-link"]').count() == 1
        assert page.locator('[data-ui-v2="deck-strip"]').count() == 6
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "오늘: 살구 띠 '오늘 확인할 일' (매도 조건 먼저 · 확인 필요) · 못 하는 규칙 줄 · 큰 움직임은 따로 · 덱 띠 6개", today_hero)
    ctx.close()
    srv.shutdown()

    for how, f, drop in (("멈춤", daily_files(files, days_ago=6), ()), ("실패", daily_files(files), ("data.json",))):
        srv, ctx, page, _ = R.open(build_site(f, drop=drop), width, init=init)

        def no_status():
            wait_ready(page)
            tab(page, C["app"]["tabs"]["today"])                          # 오늘: 멈춤 띠 또는 불러오기 실패, 할 일 띠는 없음
            if how == "멈춤":
                see(page, "데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요")
            else:
                see(page, LOAD_FAIL)
            for sel in ('[data-ui-v2="today-hero"]', '[data-ui-v2="deck-strip"]', '[data-ui-v2="big-moves"]', '[data-ui-v2="today-not-checked"]'):
                assert page.locator(sel).count() == 0, sel
            assert page.get_by_text("할 일").count() == 0
            R.collect(page)
            tab(page, C["app"]["tabs"]["deck"])
            see(page, "조용한 덱")
            if how == "멈춤":
                assert page.locator('[data-ui-v2="deck-stale"]').inner_text() == "데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요"
            else:
                assert page.locator('[data-ui-v2="deck-stale"]').count() == 0
            assert page.locator("[data-holding][data-status]").count() == 0, "멈춘·실패한 데이터로 판정했어요"
            for sel in ('[data-ui-v2="status-line"]', '[data-ui-v2="confirm"]', '[data-ui-v2="not-checked"]', '[data-holding] [data-ui="status-chip"]', "[data-rules-today]"):
                assert page.locator(sel).count() == 0, sel
            assert page.get_by_text("할 일").count() == 0
            assert page.get_by_text("평균 단가").count() == 12                # 기록은 그대로 보여요
            for sel in ('[data-ui-v2="deck-summary"]', '[data-ui-v2="weight"]', '[data-ui-v2="add-money"]'):
                assert page.locator(sel).count() == 0, sel                     # 평가 금액 · 비중 · 추가로 넣을 돈도 없어요
            R.collect(page)
        R.check(page, f"매일 점검 · {how} {width}", "판정 없음 (상태 · 버튼 · 규칙 결과 모두 없음), 기록은 그대로", no_status)
        ctx.close()
        srv.shutdown()


# ── 오늘 · 내 덱 · 왜 움직였나 (Part E) ──
# 덱 하나씩 저장해서 오늘의 큰 띠가 한 가지 상태만 보이게 해요. 산 가격은 오늘 종가의 95% (수익률이 그럴듯하게).
def _buy(t, nk, target, rules, qty, by):
    return (t, nk, target, rules, qty, round(by[t]["price"] * 0.95))


def _one_deck(i, name, rows, confirms=None):
    d = {"id": i, "name": name, "createdAt": "2026-10-01", "holdings": [_holding(t, nk, tg, r) for t, nk, tg, r, _, _ in rows],
         "purchases": [{"t": t, "date": "2026-10-01", "qty": q, "price": px, "ccy": "KRW"} for t, _, _, _, q, px in rows]}
    if confirms:
        d["confirms"] = confirms
    return {"v": 1, "decks": [d]}


def today_files(files):
    f = daily_files(files)
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    by["105560"].update(dps=3000.0, dps3=[3000.0, 4367.0, 3174.0], fy=2025, d1=0.5)     # KB금융: 2025년 보고서에서 배당 삭감
    for x in f["data.json"]["stocks"]:                                                  # 반도체가 다 같이 빠진 날
        if x.get("cls") == "kr" and x.get("ind") == "semi" and x["t"] != "000660":
            x["d1"] = -1.5
    return f


def scene_today(R, files, width):
    f = today_files(files)
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    sam = lambda q: _buy("005930", "삼성전자", 0.5, [], q, by)
    cut = [{"t": "105560", "rule": "divCut", "fy": 2025, "a": 4367.0, "b": 3000.0, "answer": "cut", "at": "2026-11-01"}]
    decks = {
        "sell": _one_deck("dsell", "매도 덱", [_buy("105560", "KB금융", 0.5, [_div(2024, 4367.0, 3174.0)], 10, by), sam(7)], cut),
        "watch": _one_deck("dwatch", "부채 덱", [_buy("012450", "한화에어로스페이스", 0.5, [_debt(2024, 150.0, 200)], 1, by), sam(3)]),
        "check": _one_deck("dcheck", "확인 덱", [_buy("005380", "현대차", 0.5, [_div(2024, 12000.0, 11400.0)], 2, by), sam(2)]),
        "band": _one_deck("dband", "비중 덱", [sam(20), _buy("035420", "NAVER", 0.5, [], 2, by)]),
        "big": _one_deck("dbig", "반도체 덱", [_buy("000660", "SK하이닉스", 0.5, [_div(2025, 3000.0, 2204.0)], 1, by), sam(6)]),
    }

    def ctx_for(key, site=None):
        init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(decks[key], ensure_ascii=False))}); }} catch (e) {{}} }})();"
        return R.open(site or build_site(f), width, init=init)

    def hero(page):
        h = page.locator('[data-ui-v2="today-hero"]')
        h.wait_for(state="visible")
        return h

    def not_checked(text):
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", text), text

    S = f"오늘·내 덱 {width}"
    srv, ctx, page, _ = ctx_for("sell")

    def sell():
        h = hero(page)
        assert h.get_attribute("data-state") == "todo"
        title = h.locator("h2").inner_text()
        assert title == "KB금융이\n매도 조건에 걸렸어요", repr(title)            # 받침 있는 이름: 승인 문장 그대로
        txt = h.inner_text()
        assert txt.startswith("오늘 확인할 일 1개") and C["daily"]["sellNow"] in txt and "나머지 1종목은 이상 없어요" in txt, txt
        item = h.locator('[data-ui-v2="todo-item"]')
        assert item.count() == 1 and item.get_attribute("data-t") == "105560"
        it = item.inner_text()
        assert C["today"]["sellLabel"] in it and "배당 삭감 · 주당 4,367원 → 3,000원" in it and "2025년 사업보고서 기준" in it, it
        assert it.count(C["daily"]["sellNow"]) == 0, "띠 본문에 있는 말을 또 했어요"
        not_checked(txt)
        assert page.locator('[data-today-holding="105560"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["broken"]]
        assert page.locator('[data-today-holding="005930"] [data-ui="status-chip"]').count() == 0          # 칩 없음 = 괜찮아요
        strip = page.locator('[data-ui-v2="deck-strip"]').inner_text()
        assert "평가 금액" in strip and "수익률" in strip and re.search(r"오늘 [+−]?\d+\.\d%", strip), strip
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "매도 조건 → 살구 띠 'KB금융이 매도 조건에 걸렸어요' · 배당 삭감 숫자 · 보고서 연도 · 나머지 이상 없음", sell)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("watch")

    def watch():
        h = hero(page)
        assert h.get_attribute("data-state") == "calm"
        txt = h.inner_text()
        assert txt.startswith(C["today"]["calmEyebrow"]) and C["today"]["calmTitle"] in txt, txt     # 지켜봐요가 있어도 맞는 말
        not_checked(txt)
        assert page.locator('[data-today-holding="012450"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["watch"]]
        R.collect(page)
        tab(page, C["app"]["tabs"]["deck"])
        add = page.locator('[data-ui-v2="add-money"]')
        add.get_by_role("button", name="+1,000만").click()
        buys = page.locator('[data-ui-v2="add-buys"] [data-add]')
        buys.first.wait_for(state="visible")
        got = buys.evaluate_all("els => els.map(e => e.dataset.add)")
        assert got == ["005930"], got                                                  # 지켜봐요 종목은 사지 않아요
        left = page.locator('[data-ui-v2="add-left"]').inner_text()
        assert re.fullmatch(r"남는 돈 [\d,]+(만원|원) · 살지 말지는 직접 정해 주세요", left), left
        R.collect(page)
    R.check(page, S, "지켜봐요 → 초록 띠 '매도 조건에 걸린 종목이 없어요' · 추가로 넣을 돈은 지켜봐요 종목을 건너뛰고 남는 돈", watch)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("check")

    def check():
        h = hero(page)
        assert h.get_attribute("data-state") == "todo"
        assert h.locator("h2").inner_text() == "현대차"              # 받침 없는 이름: '가' 문장이 승인될 때까지 이름만
        txt = h.inner_text()
        assert "현대차 배당이 줄었어요 · 주당 12,000원 → 10,000원" in txt and C["pick"]["caution"]["divDropBody"] in txt, txt
        assert C["daily"]["sellNow"] not in txt and C["daily"]["broken"] not in txt, "확인 전인데 매도처럼 보여요"
        not_checked(txt)
        R.collect(page)
        h.get_by_role("button", name=C["daily"]["confirmNotCut"]).click()
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"today-hero\"]').dataset.state === 'calm'")
        assert C["today"]["calmTitle"] in hero(page).inner_text()
        R.collect(page)
    R.check(page, S, "확인 필요 → 살구 띠의 두 버튼 → '줄인 게 아니에요' → 초록 띠", check)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("band")

    def band():
        h = hero(page)
        assert h.get_attribute("data-state") == "calm"
        txt = h.inner_text()
        assert C["today"]["calmTitle"] in txt and C["today"]["calmEyebrow"] not in txt, txt        # 줄일 차례는 할 일이 있어요
        not_checked(txt)
        tab(page, C["app"]["tabs"]["deck"])
        page.locator('[data-ui-v2="weight"]').first.wait_for(state="visible")
        bands = dict(page.locator('[data-holding]').evaluate_all("els => els.map(e => [e.dataset.holding, e.querySelector('[data-ui-v2=weight]')?.dataset.band || ''])"))
        assert bands == {"005930": "trim", "035420": "low"}, bands
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "줄일 차례 → 초록 띠, '오늘은 할 일이 없어요'는 없음 · 내 덱 비중 막대가 벗어남을 표시", band)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("big")

    def big_and_why():
        h = hero(page)
        assert h.get_attribute("data-state") == "calm"
        txt = h.inner_text()
        assert txt.startswith(C["today"]["calmEyebrow"]) and "크게 움직인 종목은 1개 있어요" in txt, txt
        inset = h.locator('[data-ui-v2="big-moves"]')
        it = inset.inner_text()
        assert "크게 움직인 종목 1개" in it and "SK하이닉스 −6.2%" in it and C["today"]["together"] in it, it
        assert "뉴스" not in it, "뉴스는 아직 확인하지 않아요"
        not_checked(txt)
        assert page.locator('[data-today-holding="000660"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["bigMove"]]
        R.collect(page)
        inset.locator('[data-ui-v2="why-link"]').click()
        see(page, "SK하이닉스 왜 움직였나")
        head = page.locator('[data-ui-v2="why-head"]').inner_text()
        assert "반도체 · 10월 30일 종가" in head and "1,418,000원" in head and "(−6.2%)" in head, head
        v = page.locator('[data-ui-v2="why-verdict"]')
        assert v.get_attribute("data-status") == "none"
        vt = v.inner_text()
        assert C["why"]["noTodo"] in vt and "업종이 다 같이\n빠진 날이에요" in vt and "규칙 1개가 모두 지켜지고 있어요." in vt, vt
        not_checked(vt)
        peers = page.locator('[data-ui-v2="why-peers"]')
        assert C["why"]["c1Title"] in peers.inner_text() and re.search(r"반도체주 (\d+)개 중 \1개가 빠졌어요", peers.inner_text()), peers.inner_text()
        assert peers.locator('[data-ui="dot-strip"] [data-mine="1"]').count() == 1
        rules = page.locator('[data-ui-v2="why-rules"]').inner_text()
        assert "규칙 1개가 모두 지켜지고 있어요" in rules and C["why"]["alertLine"] in rules and C["app"]["notChecked"] in rules, rules
        assert "뉴스" not in page.locator("main").inner_text() and "다음에 확인할 일" not in page.locator("main").inner_text()
        src = page.locator('[data-ui-v2="why-sources"]')
        src.locator("button").first.click()
        st = src.inner_text()
        assert "한국거래소 10월 30일 종가" in st and re.search(r"반도체 \d+개 종목", st) and "2025년 사업보고서 기준" in st, st
        no_hscroll(page, width)
        R.collect(page)
        page.get_by_role("button", name=C["build"]["backToday"]).click()
        hero(page)
        assert page.get_by_text("SK하이닉스 왜 움직였나").count() == 0
    R.check(page, S, "큰 움직임 → '같은 업종이 다 같이 빠졌어요' → 자세히 보기 → 왜 움직였나(판정 · 점 띠 · 규칙 · 출처) → 오늘", big_and_why)

    def deck_sheet():
        tab(page, C["app"]["tabs"]["deck"])
        page.locator('[data-ui-v2="deck-summary"]').wait_for(state="visible")
        assert re.fullmatch(r"[\d,]+만원", page.locator('[data-ui-v2="deck-value"]').inner_text())
        money = page.locator('[data-ui-v2="deck-money"]').inner_text()
        assert re.fullmatch(r"원금 [\d,]+만원 · 수익 \+[\d,]+만원 \(\+[\d,]+\.\d%\)", money), money
        mine = page.locator('[data-ui-v2="vs-mine"]').inner_text()
        kospi = page.locator('[data-ui-v2="vs-index"]').inner_text()
        assert re.fullmatch(r"내 덱 \+\d+\.\d%", mine) and re.fullmatch(r"코스피 [+−]?\d+\.\d%", kospi), (mine, kospi)
        assert "10월 1일 시작" in page.locator('[data-ui-v2="deck-start"]').inner_text()
        assert page.locator('[data-ui-v2="weight"]').count() == 2
        assert C["deck"]["bandNote"] in page.locator('[data-ui-v2="weight-legend"]').inner_text()
        page.locator('[data-ui-v2="add-empty"]').wait_for(state="visible")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "내 덱: 평가 금액 · 원금 · 수익 · 내 덱 vs 코스피 숫자 두 개 · 시작일 · 비중 막대 · 추가로 넣을 돈", deck_sheet)
    ctx.close()
    srv.shutdown()

    for how in ("옛 형식", "실패"):
        g = clone(f)
        drop = ()
        if how == "옛 형식":
            for n in ("data.json", "corp.json"):
                g[n].pop("pxDate", None)
                g[n].pop("publishedAt", None)
        else:
            drop = ("data.json",)
        srv, ctx, page, _ = ctx_for("sell", site=build_site(g, drop=drop))

        def refused():
            see(page, LOAD_FAIL)
            for sel in ('[data-ui-v2="today-hero"]', '[data-ui-v2="deck-strip"]', '[data-ui-v2="today-not-checked"]'):
                assert page.locator(sel).count() == 0, sel
            assert page.get_by_text("할 일").count() == 0 and page.get_by_text(C["daily"]["sellNow"]).count() == 0
            R.collect(page)
        R.check(page, f"오늘 · {how} {width}", "저장한 덱이 있어도 불러오기 실패 문구만, 할 일 띠 없음", refused)
        ctx.close()
        srv.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    args = ap.parse_args()
    files = read_fixtures()
    names = set()
    for s in files["data.json"]["stocks"]:
        names |= {s.get("nk"), s.get("ne"), s.get("indName")}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path())
        R = Runner(browser, args.shots, names)
        for width in (320, 390):
            scenes = [lambda: scene_normal(R, files, width), lambda: scene_stale(R, files, width),
                      lambda: scene_refused(R, files, width, "옛 형식"), lambda: scene_refused(R, files, width, "404"),
                      lambda: scene_refused(R, files, width, "깨짐"), lambda: scene_missing_fields(R, files, width, ["ind", "indName"]),
                      lambda: scene_missing_fields(R, files, width, ["val20"]), lambda: scene_no_storage(R, files, width),
                      lambda: scene_us_date(R, files, width),
                      lambda: scene_old_app(R, files, width, '[{"id":"s1","name":"포트폴리오 1"}]', True),
                      lambda: scene_old_app(R, files, width, "[]", False),
                      lambda: scene_old_app(R, files, width, "{not json", False),
                      lambda: scene_daily(R, files, width), lambda: scene_today(R, files, width)]
            for fn in scenes:
                try:
                    fn()
                except Exception as e:
                    R.results.append((f"[{width}] 장면 실행", False, str(e).splitlines()[0][:200]))
                    print(f"  FAIL  [{width}] 장면 실행: {e}", flush=True)
        browser.close()

    ok = Matcher([v for _, v in copy_strings()[1] if isinstance(v, str)], loose_slots=True)
    ko = sorted({t for t in R.texts if HANGUL.search(t)})
    stray = [t for t in ko if not ok(R.unnamed(t))]
    R.results.append((f"보이는 한국어 {len(ko)}가지 모두 src/copy/v2.js 또는 데이터 이름에서 왔어요", len(ko) > 120 and not stray, str(stray[:8])))
    R.results.append(("페이지 오류 0건 (모든 장면)", not R.errors, "; ".join(R.errors)[:300]))
    R.results.append(("다른 사이트 요청 0건 (글꼴·통계·CDN 없음)", not R.outside, ", ".join(sorted(set(R.outside)))[:300]))
    w = max(len(n) for n, _, _ in R.results)
    print("\n뱁새 2.0 미리 보기 스모크 테스트 결과 · 데이터: tests/fixtures/v2")
    for name, good, msg in R.results:
        print(f"  {'PASS' if good else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in R.results if not r[1]]
    print(f"\n{len(R.results) - len(bad)} / {len(R.results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
