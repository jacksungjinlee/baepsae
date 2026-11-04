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
              줄인 게 아니에요 → 해제 · 답은 바꿀 수 있고 바꾼 답이 남아요 · 지켜봐요(부채비율) · 확인 필요(배당 감소 ·
              자료 없음) · 비중 벗어남 · 할 일 없음 · 큰 움직임은 표시만 · '아직 자동으로 확인하지 못하는 규칙' 줄 ·
              멈춘 데이터에서는 판정 없이 멈춤 문장, 불러오기 실패에서는 판정 없이 실패 문구
  정상의 샀어요 뒤 내 덱: 계획대로 산 날에는 모든 종목이 할 일 없음 (비중 때문에 뜨는 것 없음)
  오늘·내 덱  (Part E) 덱 하나씩: 매도 조건(받침 있는 이름 → '…이 매도 조건에 걸렸어요') · 지켜봐요 → 초록 띠 · 확인 필요 →
              살구 띠의 두 버튼 → 답하면 초록 띠 · 줄일 차례 → 초록 띠, '오늘은 할 일이 없어요' 없음 · 큰 움직임(업종이 다 같이
              빠짐) → 자세히 보기 → 왜 움직였나(점 띠 · 규칙 · 데이터 출처) → 오늘 · 내 덱의 평가 금액 · 원금 · 코스피와 비교 ·
              비중 막대 · 추가로 넣을 돈(지켜봐요는 건너뜀) · 옛 형식·불러오기 실패·멈춤이면 할 일 띠 없음 · '못 하는 규칙' 줄
  아이폰      (v18.4.1) 아이폰 사파리 UA 로 샀어요 → 기록 내보내기 → 저장소가 따로인 새 문맥에서 기록 불러오기 → 같은 덱 · 산 기록 ·
              규칙 · 내 덱 · 오늘 화면, 두 번 불러도 덱이 늘지 않음, 미리 보기 기록 파일은 막힘 (scene_iphone_records 설명 참고)
  소개        (v19.0 Part D) 푸터: 고지문 · 소개 링크, 만든 사람 줄 없음 · #about 으로 열면 한국어 · English 로 바꾸면 영어 머리글 ·
              새로 고침해도 그 선택 · 저장소가 막혀도 동작 · 숫자 줄 = 시험 데이터로 센 값(분석 종목 · 업종 그룹) · 멈춘 데이터면
              숫자 줄 없음(문단은 그대로) · data.json 이 없으면 숫자 줄과 숫자 문단 없이 나머지는 그대로 · 뒤로 → 전 화면, # 없음
모든 장면에서 페이지 오류 0건, 다른 사이트 요청 0건. 화면에 보이는 한국어는 모두 src/copy/v2.js(또는 데이터의 이름)에서 와요.
v19.0b (진지한 화면): 글을 모으는 모든 화면에서 (visual_ok) — 그림이 모두 열려요 · 뱁이 그림은 숫자가 있는 카드와 판정 띠에 없어요
(소개 페이지는 규칙이 이름으로 허락한 곳) · 아이콘은 Phosphor 두 층에 표의 색만 · 고른 탭 · 고른 줄 · 고른 칩 · 아이콘 · 판정 띠에
살구색이 없어요. 그리고 판정 띠의 상태 아이콘(할 일 없음 check-circle · 확인할 일 flag, 멈춤은 없음) · 알약 색 · 초점 테두리 남색 ·
로고(뱁이 마크 + '뱁새' 22px/800) · 덱 짜기 첫 화면 · 빈 내 덱 · 불러오기 실패 · 준비 중의 뱁이 · 기록했어요는 그림 대신 아이콘 칩.
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
from visualcheck import V2_IMAGES, NAVY_RGB, SELECT_RGB, visual_ok, placements_table  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
SITE_FILES = ["baepsae.html", "sw.js", "icon-192.png", "baepi-og.webp", "jack-photo.jpg"] + V2_IMAGES + [f"baepi-{i}.png" for i in range(1, 10)]
DATA_FILES = ["data.json", "corp.json", "macro.json"]
WAIT = 15000
KST = dt.timezone(dt.timedelta(hours=9))
WHOLE_BAD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")   # \b 는 'NaN원'을 놓쳐요
SLOT_LEFT = re.compile(r"\{\w+\}")                                                        # 채우지 못한 {자리}
# 오늘 화면이 매일 점검해요(Part E) · 규칙 고치기는 아직 없어서 '매일 이 규칙으로 점검하고, 규칙은 언제든 고칠 수 있어요'는 약속하지 않아요
NO_PROMISE = ["매일 이 규칙으로", "언제든 고칠 수"]

C, _ = copy_strings()
LOAD_FAIL = C["app"]["loadFail"]
TABS = C["app"]["tabs"]
# v19.0c: 승인을 기다리는 이름(null)은 화면이 이미 승인된 이름을 대신 써요 (src/copy/v2.js 의 "승인 전:")
BACK_BUILD = C["build"]["backToday"] or TABS["home"]
DONE_LINK = C["plan"]["doneLink"] or TABS["home"]
PICK_BACK = C["pick"]["back"] or C["build"]["title"]
MENU_LABEL = C["menu"]["label"] or C["app"]["tabsLabel"]
DECK_WORD = re.compile(r"(?<!인)덱")                                                    # v19.0c: 화면 어디에도 '덱'이 없어요
MASCOT_IN_MAIN = "main img[src^='baepi-']:not([data-ui-v2='logo-mark'])"                 # 로고 마크는 그림 자리가 아니에요

def verdict_icon(loc, state):
    """판정 띠의 상태 아이콘: 60px 흰 동그라미, 할 일 없음 = check-circle(초록 · 초록 바탕) · 확인할 일 = flag(남색 · 회청색 바탕)."""
    ic = loc.locator('[data-ui="state-icon"]')
    assert ic.count() == 1, f"상태 아이콘 {ic.count()}개"
    assert ic.get_attribute("data-state") == state, ic.get_attribute("data-state")
    box = ic.bounding_box()
    assert box and abs(box["width"] - 60) < 1 and abs(box["height"] - 60) < 1, box
    assert ic.evaluate("(e) => getComputedStyle(e).backgroundColor") == "rgb(255, 255, 255)"
    svg = ic.locator("svg")
    want = {"calm": ("check-circle", "#CDEBD9", "#1F7A4D"), "alert": ("flag", "#CBD3DF", "#1C2B45")}[state]
    got = (svg.get_attribute("data-ph"), svg.locator('[data-layer="fill"]').get_attribute("fill"), svg.locator('[data-layer="line"]').get_attribute("fill"))
    assert got == want, got
    assert loc.locator("img").count() == 0, "판정 띠에 그림이 있어요"


def hero_colours(loc):
    """(띠 바탕, 알약 바탕, 알약 글자) — 계산된 색."""
    return loc.evaluate("""(e) => { const b = e.querySelector('[data-ui="hero-band"]') || e; const p = b.querySelector('[data-ui-part="pill"]');
        return [getComputedStyle(b).backgroundColor, p ? getComputedStyle(p).backgroundColor : null, p ? getComputedStyle(p).color : null]; }""")


def mascot_img(loc, src, px, alt):
    img = loc.locator(f'img[src="{src}"]')
    img.wait_for(state="visible")
    assert img.evaluate("(i) => i.complete && i.naturalWidth > 0"), f"{src} 가 열리지 않았어요"
    box = img.bounding_box()
    assert box and abs(box["width"] - px) < 1, (src, box)
    assert img.get_attribute("alt") == alt and alt, (src, img.get_attribute("alt"), alt)     # Jack 이 승인한 alt (2026-11-04)


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

    def open(self, site, width, init=None, accept_downloads=False, path="/app.html?dev=1", device=None):
        srv, base = serve(site)
        # device: Playwright 의 기기 설명(사용자 에이전트 · 화면 · 터치)을 그대로 입혀요. 없으면 휴대폰 폭 width × 780.
        screen = dict(device) if device else {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2}
        ctx = self.browser.new_context(**screen, locale="ko-KR", service_workers="block", accept_downloads=accept_downloads)

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
        page.goto(base + path, wait_until="domcontentloaded")
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
        # 큰 숫자(v19.0b [data-ui="amount"]: 단위만 작게 그린 span)는 조각이 아니라 한 덩어리 글로 모아요 ("1,073만원" 그대로 출처 확인)
        got = page.evaluate("""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (w.nextNode()) { const n = w.currentNode; const e = n.parentElement; if (!e || e.closest('script, style, [data-ui="amount"]')) continue;
              const r = e.getBoundingClientRect(); if (!r.width && !r.height) continue; const t = n.textContent; if (t.trim()) out.push(t); }
            for (const a of document.querySelectorAll('[data-ui="amount"]')) { const r = a.getBoundingClientRect(); if ((r.width || r.height) && a.textContent.trim()) out.push(a.textContent); }
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
        deck = sorted({t for t in got + [body] if DECK_WORD.search(t)})
        assert not deck, f"v19.0c: '덱'이 화면에 있어요: {deck[:3]}"
        assert "☰" not in body + " ".join(got), "☰ 글자 대신 Phosphor list 아이콘이에요"
        visual_ok(page)

    def unnamed(self, t):
        for n in self.names:
            if n in t:
                t = t.replace(n, "{}")
        return t


# ── 화면 조작 ──
def has_final(name):
    """받침으로 끝나게 읽히는지 (src/v2/track.js subjectParticle 과 같은 읽기, 이 줄에 들어가는 이름들만큼)."""
    ch = name.rstrip()[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch.upper() in "LMNR013678"


def see(page, text, timeout=WAIT):
    page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)


def tab(page, label):
    """아래 탭을 눌러요 (v19.0c: 홈 · 포트폴리오 · 종목 · 시장). 포트폴리오 만들기 첫 단계 안이면(탭 막대가 없어요) 먼저 뒤로 나와요."""
    bar = page.locator('nav[data-ui="bottom-tab-bar"]')
    if bar.count() == 0:
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()
        bar.wait_for(state="visible")
    bar.locator("button", has_text=label).click()


def route(page):
    return page.locator('[data-ui-v2="screen"]').get_attribute("data-route")


def at(page, r):
    """그 화면(주소)이 될 때까지 기다려요: home · portfolio · stocks · market · portfolio/build · home/why."""
    page.wait_for_function("(r) => { const e = document.querySelector('[data-ui-v2=\"screen\"]'); return !!e && e.dataset.route === r; }", arg=r)


def start_build(page):
    """포트폴리오 만들기를 열어요: 첫 방문 홈의 버튼, 아니면 포트폴리오 탭의 버튼(빈 화면 · 포트폴리오 아래)."""
    if page.locator('[data-ui-v2="screen"][data-route="portfolio/build"]').count():
        return
    tab(page, TABS["home"])
    at(page, "home")
    first = page.locator('[data-ui-v2="home-start"] button')
    if first.count():
        first.click()
    else:
        tab(page, TABS["portfolio"])
        page.locator('[data-ui-v2="deck-empty"] button, [data-ui-v2="build-more"] button').first.click()
    at(page, "portfolio/build")


def open_menu(page):
    page.locator('[data-ui-v2="menu-button"]').first.click()
    m = page.locator('[data-ui-v2="menu"]')
    m.wait_for(state="visible")
    return m


def menu_links(page, live=True):
    """☰ 메뉴: 소개 · 용어 사전 · 데이터 출처 · 예전 뱁새 보기 (예전 뱁새로 가는 셋은 실제 앱에만), 닫기로 닫혀요."""
    m = open_menu(page)
    items = m.locator('[data-ui-v2="menu-item"]')
    want = [("about", C["app"]["aboutLink"], None)]
    if live:
        want += [("glossary", C["menu"]["glossary"], "./baepsae.html#info=glossary"), ("sources", C["menu"]["sources"], "./baepsae.html#info=sources"),
                 ("old-app", C["app"]["oldApp"], "./baepsae.html")]
    got = [(items.nth(i).get_attribute("data-item"), items.nth(i).inner_text().strip(), items.nth(i).get_attribute("href")) for i in range(items.count())]
    assert got == want, got
    m.locator('[data-ui-v2="menu-close"]').click()
    m.wait_for(state="detached")


def fillp(tpl, **kw):
    return re.sub(r"\{(\w+)\}", lambda m: str(kw[m.group(1)]) if m.group(1) in kw else m.group(0), tpl)


def done_body(page, n):
    """기록했어요의 '내일부터 홈에서 {n}종목을 …': v19.0c 문장은 Jack 의 승인 대기라 그동안은 없어요 (tests/test_v2_app.py)."""
    page.locator('[data-ui-v2="record-done"]').wait_for(state="visible")
    body = page.locator('[data-ui-v2="done-body"]')
    assert C["plan"]["doneBody"], "plan.doneBody 는 승인된 문구예요 (Jack, 2026-11-04)"
    assert body.inner_text() == fillp(C["plan"]["doneBody"], n=n), body.inner_text()
    assert "오늘 화면" not in page.locator('[data-ui-v2="record-done"]').inner_text()


def vs_kospi(page):
    """포트폴리오 vs 코스피 두 칸: 첫 칸의 이름(deck.vsMine, v19.0c 제안)이 승인되면 두 칸이 보이고, 그 전에는 둘 다 빠져요."""
    assert C["deck"]["vsMine"], "deck.vsMine 은 승인된 문구예요 (Jack, 2026-11-04)"
    mine, kospi = page.locator('[data-ui-v2="vs-mine"]').inner_text(), page.locator('[data-ui-v2="vs-index"]').inner_text()
    pat = re.escape(fillp(C["deck"]["vsMine"], pct="PCT")).replace("PCT", r"[+−]?\d+\.\d%")
    assert re.fullmatch(pat, mine) and re.fullmatch(r"코스피 [+−]?\d+\.\d%", kospi), (mine, kospi)


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
    page.locator('[data-ui-v2="screen"][data-route]').wait_for(state="attached")


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
        at(page, "home")                                       # 주소 없이 열면 그 자리에서 #home (기록이 늘지 않아요)
        assert page.url.endswith("/app.html?dev=1#home") and page.evaluate("history.state && history.state.v2") == 0, page.url
        hero = page.locator('[data-ui-v2="home-hero"]')         # 첫 방문 홈: 나뭇가지를 나르는 뱁이 92px · 숫자 없는 화면
        mascot_img(hero, "baepi-16-build.webp", 92, C["build"]["s0"]["imgAlt"])
        assert C["about"]["ko"]["hero"]["descriptor"] in hero.inner_text() and C["about"]["ko"]["hero"]["catch"] in hero.inner_text()
        assert page.locator('[data-ui-v2="home-start"]').inner_text().strip() == C["build"]["title"]
        assert page.locator('[data-ui-v2="market-glance"], [data-ui-v2="market-tile"]').count() == 0, "뱁이가 있는 첫 방문 홈에 시장 숫자"
        pop = page.locator('[data-ui-v2="popular"]')            # 거래대금 상위 종목: 한국 · 미국 따로, 날짜, 이름만 (숫자 없음)
        assert pop.locator("h3").inner_text() == C["home"]["popular"] and pop.locator('[data-ui="icon-chip"][data-icon="chart-bar"]').count() == 1
        lists = pop.locator('[data-ui-v2="popular-list"]')
        assert [lists.nth(i).get_attribute("data-market") for i in range(lists.count())] == ["kr", "us"]
        assert lists.nth(0).locator('[data-ui-v2="list-date"]').inner_text() == "10월 30일 기준"
        assert lists.nth(0).locator('[data-ui-v2="stock-row"][data-cls="kr"]').count() == 5 and lists.nth(1).locator('[data-ui-v2="stock-row"][data-cls="us"]').count() == 5
        assert not re.search(r"\d\s*%|\d{6}", pop.inner_text()), pop.inner_text()          # 등락률 · 종목코드 없음
        assert page.locator('svg[data-ph="fire"]').count() == 0
        bar = page.locator('nav[data-ui="bottom-tab-bar"]')
        assert [b.strip() for b in bar.locator("button").all_inner_texts()] == [TABS[k] for k in ("home", "portfolio", "stocks", "market")]
        assert bar.locator('button[aria-current="page"]').inner_text().strip() == TABS["home"]
        btn = page.locator('[data-ui-v2="menu-button"]')
        assert btn.count() == 1 and btn.get_attribute("aria-label") == MENU_LABEL and btn.locator('svg[data-ph="list"]').count() == 1
        assert page.locator('[data-ui-v2="old-app-link"], [data-ui-v2="search-link"]').count() == 0     # 머리말 링크는 메뉴와 종목 탭으로
        assert page.locator('[data-ui-v2="old-app-note"]').count() == 0, "예전 뱁새 기록이 없는데 안내가 보여요"
        assert page.title() == C["app"]["title"]
        word = page.locator('[data-ui-v2="app-bar"] h1').first                # v19.0: 머리말은 '뱁새', 긴 제목은 탭 제목에만
        assert word.inner_text() == C["app"]["brand"] == "뱁새", word.inner_text()
        assert md in date_line(page) and "멈췄어요" not in date_line(page)
        assert page.locator('[data-ui-v2="today-hero"]').count() == 0
        assert page.get_by_text("할 일").count() == 0, "점검한 종목이 없는데 '할 일'이 보여요"
        assert page.locator('[data-ui-v2="ios-hint"]').count() == 0, "아이폰 사파리가 아닌데 홈 화면 안내가 보여요"
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "첫 화면: 저장한 포트폴리오가 없으면 첫 방문 홈(뱁이 · 포트폴리오 만들기 · 거래대금 상위 종목, 숫자 없음) · 탭 넷 · ☰", landing)

    def visual_start():
        bar = page.locator('[data-ui-v2="app-bar"]').first                   # 로고: 뱁이 마크 28px + '뱁새' 22px/800 (뒤로 버튼이 있으면 마크 대신)
        mark = bar.locator('img[data-ui-v2="logo-mark"]')
        assert mark.get_attribute("src") == "baepi-mark.webp" and mark.get_attribute("alt") == "" and mark.evaluate("(i) => i.naturalWidth > 0")
        assert abs(mark.bounding_box()["width"] - 28) < 1
        assert bar.locator("img[src='icon-192.png']").count() == 0
        word = bar.locator('h1[data-ui-v2="wordmark"]')
        assert word.inner_text() == C["app"]["brand"] and word.evaluate("(e) => [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight]") == ["22px", "800"]
        page.locator('[data-ui-v2="home-start"] button').click()
        at(page, "portfolio/build")
        assert page.url.endswith("#portfolio/build") and page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        start = page.locator('[data-ui-v2="build-start"]')                 # 포트폴리오 만들기 첫 카드: 숫자 없음 → 나뭇가지를 나르는 뱁이 92px
        mascot_img(start, "baepi-16-build.webp", 92, C["build"]["s0"]["imgAlt"])
        assert not re.search(r"\d", start.inner_text()), start.inner_text()
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()                 # 뒤로: 열었던 홈으로 (기록 한 칸 뒤)
        at(page, "home")
        start_build(page)
        page.locator('[data-deck="income"]').click()                         # 시작 유형 → 다음 단계 → 뒤로: 표시 없이 그대로 (main 과 같아요)
        see(page, C["build"]["s1"]["title"])
        page.get_by_role("button", name=C["build"]["prevStep"]).click()
        page.locator('[data-deck="income"]').wait_for(state="visible")
        assert page.locator("[data-deck][data-selected], [data-deck][aria-current]").count() == 0, "다시 누르면 1단계 변경이 사라지는 고른 표시가 있어요"
        page.locator("body").click(position={"x": 2, "y": 2})                # 키보드 초점 테두리는 남색 (살구색 아님)
        page.keyboard.press("Tab")
        ring = page.evaluate("() => { const s = getComputedStyle(document.activeElement); return [document.activeElement.tagName, s.outlineColor, s.outlineStyle, s.outlineWidth]; }")
        assert ring[1:] == [NAVY_RGB, "solid", "2px"], ring
        R.collect(page)
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()
        at(page, "home")
    R.check(page, S, "포트폴리오 만들기 첫 화면의 뱁이(날짜 줄 말고 숫자 없음) · 로고 마크 + 워드마크 · 돌아와도 시작 유형 표시 없음 · 초점 테두리 남색 · 뒤로 → 홈", visual_start)

    def my_deck():
        tab(page, TABS["portfolio"])
        at(page, "portfolio")
        see(page, C["store"]["export"])
        assert md in date_line(page)
        empty = page.locator('[data-ui-v2="deck-empty"]')                    # 빈 포트폴리오: 둥지에 앉은 뱁이 + 포트폴리오 만들기 (숫자 없는 카드)
        mascot_img(empty, "baepi-15-portfolio.webp", 112, C["deck"]["emptyAlt"])
        assert empty.inner_text().strip() == C["build"]["title"], empty.inner_text()
        assert page.locator("main h2").first.inner_text() == C["deck"]["title"]
        tabs = page.locator('nav[data-ui="bottom-tab-bar"]')                 # 고른 탭: 아이콘 뒤 회색 알약 + 남색 아이콘
        on = tabs.locator('button[aria-current="page"] [data-ui-part="tab-pill"]')
        assert on.evaluate("(e) => getComputedStyle(e).backgroundColor") == SELECT_RGB
        assert on.locator("svg").get_attribute("data-tone") == "on"
        assert tabs.locator('button:not([aria-current]) svg[data-tone="off"]').count() == 3
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "탭: 포트폴리오 (기록 내보내기·불러오기) · 빈 포트폴리오 카드의 뱁이 · 고른 탭 알약", my_deck)

    def build_tab():
        page.locator('[data-ui-v2="deck-empty"] button').click()            # 빈 포트폴리오의 '포트폴리오 만들기'
        at(page, "portfolio/build")
        see(page, C["build"]["s0"]["title"])
        assert md in date_line(page)
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        for hidden in ("steadyDiv", "cheapQuality", "payout", "theme", "divGrowth"):
            assert page.locator(f'[data-deck="{hidden}"]').count() == 0, f"숨겨야 할 시작 유형: {hidden}"
        assert page.locator("[data-deck]").count() == 9
        no_hscroll(page, width)
        R.collect(page)
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()
        at(page, "portfolio")                                              # 연 곳(포트폴리오)으로 돌아가요
    R.check(page, S, "포트폴리오 → 포트폴리오 만들기 (시작 유형 8개 + 처음부터, 탭 막대 없음) → 뒤로 → 포트폴리오", build_tab)

    def menu_and_back():
        menu_links(page)                                                   # ☰: 네 줄 + 데이터 날짜, 닫기
        m = open_menu(page)
        d = m.locator('[data-ui-v2="menu-date"]').inner_text()
        assert "10월 30일 기준" in d, d
        assert page.locator('[data-ui-v2="menu-button"]').first.get_attribute("aria-expanded") == "true"
        page.go_back()                                                     # 휴대폰 뒤로: 메뉴만 닫혀요
        m.wait_for(state="detached")
        at(page, "portfolio")
        m = open_menu(page)
        page.keyboard.press("Escape")                                       # Esc 도 닫아요
        m.wait_for(state="detached")
        page.wait_for_function("() => document.activeElement && document.activeElement.dataset.uiV2 === 'menu-button'")   # 초점은 ☰ 로
        m = open_menu(page)
        m.locator('[data-ui-v2="menu-item"][data-item="about"]').click()   # 메뉴 → 소개 → 뒤로 → 메뉴 아래 있던 화면
        page.locator('[data-ui-v2="about"]').wait_for(state="visible")
        assert page.url.endswith("#about") and page.locator('[data-ui-v2="menu"]').count() == 0
        page.go_back()
        at(page, "portfolio")
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
        assert page.locator('[data-ui-v2="menu"]').count() == 0 and page.url.endswith("#portfolio"), page.url
        tab(page, TABS["stocks"])                                          # 탭 → 탭 → 뒤로 → 뒤로: 탭마다 한 칸
        at(page, "stocks")
        tab(page, TABS["market"])
        at(page, "market")
        assert page.url.endswith("#market")
        page.go_back()
        at(page, "stocks")
        page.go_back()
        at(page, "portfolio")
        R.collect(page)
    R.check(page, S, "☰ 메뉴(네 줄 · 데이터 날짜 · 닫기 · Esc · 휴대폰 뒤로) · 메뉴 → 소개 → 뒤로 · 탭마다 뒤로 한 칸", menu_and_back)

    def from_starting_deck():
        start_build(page)
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        assert page.locator('[data-ui-v2="menu-button"]').count() == 1      # 탭 막대가 없는 곳에서도 ☰
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
        assert page.locator('[data-ui-v2="y2022-methods"] [data-ui-v2="y2022-source"]').inner_text() == C["plan"]["y2022Source"]
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
        krc = page.locator("section[data-market='kr'] [data-cand]")
        for i in range(1, krc.count()):                                 # 근거 수치를 모두 열어요 (첫 후보는 이미 열림)
            krc.nth(i).get_by_role("button", name=C["pick"]["receipts"]).click()
        rec = page.locator("section[data-market='kr'] [data-ui-v2='receipts']")
        assert rec.count() == krc.count(), (rec.count(), krc.count())
        want = {"y2": C["pick"]["receipt"]["growthKr"], "y1": C["pick"]["receipt"]["growthKr1y"]}     # 계산 방식 → 라벨
        labels = [(g.get_attribute("data-basis"), g.locator("span").first.inner_text()) for g in page.locator(
            "section[data-market='kr'] [data-ui-v2='receipts'] [data-ui-v2='growth']").all()]
        assert labels and all(want.get(b) == t for b, t in labels), labels
        for i in range(1, krc.count()):
            krc.nth(i).get_by_role("button", name=C["pick"]["receipts"]).click()
        names = "|".join(map(re.escape, ["PBR", C["pick"]["receipt"]["debt"], C["pick"]["checks"]["rev"], C["plan"]["rules"]["opProfit"],
                                         C["pick"]["checks"]["vol"], C["plan"]["rules"]["dividend"]]))
        for t in page.locator('[data-ui-v2="caution-none"]').all_inner_texts():
            many = re.fullmatch(rf"(?:{names})(?: · (?:{names}))+ 모두 확인했어요\. 주의할 점은 없어요\.", t)
            one = re.fullmatch(rf"({names})([을를]) 확인했어요\. 주의할 점은 없어요\.", t)     # 하나면 '모두' 없이, 을/를 맞춰서
            assert many or (one and one.group(2) == ("을" if has_final(one.group(1)) else "를")), t
        R.collect(page)
        no_hscroll(page, width)
        click_next(page)
        see(page, C["plan"]["stocks"])
        assert md in date_line(page)
        assert page.locator("[data-row]").count() == 6
        see(page, C["plan"]["y2022Note"])
        assert page.locator('[data-ui-v2="y2022"] [data-ui-v2="y2022-source"]').inner_text() == C["plan"]["y2022Source"]
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
        book = page.locator("[data-rules-for]")
        assert book.get_by_text(C["plan"]["rules"]["embezzle"]).count() == 6, "횡령·배임 줄이 종목마다 있어야 해요"
        op_rows = page.locator("[data-rules-for] [data-ui-v2='rule-line']", has_text=C["plan"]["rules"]["opLimit"])
        assert op_rows.count() >= 1 and re.search(r"[억조]원 → .+[억조]원 → .+[억조]원", op_rows.first.inner_text()), op_rows.first.inner_text()
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
        assert sheet.locator('[data-ui-v2="bad-input"]').inner_text() == C["plan"]["badInput"]
        date.fill("")
        qty = sheet.locator("[data-record] input").first
        qty.fill("1.5")                                               # 소수 주식도 받지 않아요
        page.get_by_role("button", name=C["plan"]["save"]).click()
        assert qty.get_attribute("aria-invalid") == "true" and page.get_by_text(C["plan"]["done"]).count() == 0
        assert page.evaluate("localStorage.getItem('baepsae2.v1')") is None, "틀린 입력인데 저장했어요"
        qty.fill("")
        page.get_by_role("button", name=C["plan"]["save"]).click()
        see(page, C["plan"]["done"])
        done_body(page, 6)                                                  # Part E: 홈이 정말 점검해요 (v19.0c 문장은 승인 대기)
        done = page.locator('[data-ui-v2="record-done"]')                    # 종목 수만 있고 돈은 없어서 기뻐하는 뱁이 그대로 (Jack, 2026-11-04)
        mascot_img(done, "baepi-5.png", 64, C["plan"]["doneAlt"])
        R.collect(page)
        page.get_by_role("button", name=DONE_LINK).click()
        at(page, "home")
        assert page.url.endswith("#home"), page.url                         # 다 만든 포트폴리오 만들기는 홈으로 바뀌어요
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        assert stored["v"] == 1 and len(stored["decks"]) == 1 and len(stored["decks"][0]["purchases"]) == 6, stored
        assert stored["decks"][0]["name"] == "배당 생활비 포트폴리오", stored["decks"][0]["name"]     # 새 기본 이름 (v19.0c)
        d0 = stored["decks"][0]                                    # 계획의 숫자도 저장해요 (비중 점검의 반올림 차이는 이것만 써요)
        assert d0["planFx"] > 0 and all(h["planPx"] > 0 and isinstance(h["plannedQty"], int) for h in d0["holdings"]), d0["holdings"]
        us_buys = [p for p in stored["decks"][0]["purchases"] if p["ccy"] == "USD"]
        assert all(p.get("fx") == files["data.json"]["fx"] == d0["planFx"] for p in us_buys), us_buys   # 미국 매수는 계획의 환율과 함께
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        hero = page.locator('[data-ui-v2="today-hero"]')                      # 저장한 덱이 있으면 오늘부터, 판정 띠와 함께
        hero.wait_for(state="visible")
        assert hero.get_attribute("data-state") == "calm", hero.inner_text()     # 산 날: 매도 조건도 확인할 일도 없어요
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", hero.inner_text()), hero.inner_text()
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 1 and page.get_by_text(C["build"]["s0"]["title"]).count() == 0
        glance = page.locator('[data-ui-v2="market-glance"]')                # 다시 온 방문자의 홈: 시장 한눈에 (뱁이 없음)
        assert glance.locator("h3").inner_text() == (C["home"]["market"] or TABS["market"]) and glance.locator('[data-ui-v2="market-tile"]').count() == 4
        assert page.locator('[data-ui-v2="home-hero"], [data-ui-v2="popular"]').count() == 0 and page.locator(MASCOT_IN_MAIN).count() == 0
        R.collect(page)
        tab(page, C["app"]["tabs"]["portfolio"])
        see(page, "배당 생활비 포트폴리오")
        see(page, "내 종목 6개")
        menu_links(page)
        assert page.locator('[data-ui-v2="build-more"]').inner_text().strip() == C["build"]["title"]     # 포트폴리오가 있어도 새로 만들 수 있어요
        assert page.get_by_text("평균 단가").count() == 6
        # 계획대로 산 날(같은 종가): 매일 점검이 돌고, 비중 때문에 뜨는 것은 없어요 (Part C 리뷰: 첫날 매도 신호)
        page.locator("[data-holding][data-status]").first.wait_for(state="visible")
        st = page.locator("[data-holding]").evaluate_all("(els) => els.map((e) => e.dataset.status)")
        assert len(st) == 6 and set(st) == {"none"}, st
        assert page.locator('[data-ui-v2="status-line"]').count() == 0
        assert page.locator('[data-ui-v2="weight"]').count() == 6 and page.locator('[data-ui-v2="weight"][data-band]').count() == 0
        page.locator('[data-ui-v2="deck-value"]').wait_for(state="visible")
        assert re.fullmatch(r"원금 [\d,]+만원 · 수익 [+−]?[\d,]+(만원|원) \([+−]?[\d,]+\.\d%\)", page.locator('[data-ui-v2="deck-money"]').inner_text()), \
            page.locator('[data-ui-v2="deck-money"]').inner_text()
        vs_kospi(page)
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
        tab(page, C["app"]["tabs"]["portfolio"])
        see(page, C["store"]["export"])
        assert page.get_by_text("배당 생활비 포트폴리오").count() == 0
        page.locator('[data-ui-v2="import-file"]').set_input_files(path)
        see(page, "배당 생활비 포트폴리오")
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        tab(page, C["app"]["tabs"]["portfolio"])
        see(page, "내 종목 6개")
        bad = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(bad, "w") as fh:
            fh.write('{"hello": 1}')
        page.locator('[data-ui-v2="import-file"]').set_input_files(bad)
        page.locator('[data-ui-v2="import-bad"]').wait_for(state="visible")
        assert page.get_by_text("내 종목 6개").count() == 1, "잘못된 파일이 기록을 지웠어요"
        box = page.locator('[data-ui-v2="import-bad"]')
        assert box.get_attribute("data-why") == "bad" and box.inner_text() == C["store"]["importFail"], box.inner_text()
        prev = os.path.join(tempfile.mkdtemp(), "preview.json")
        with open(prev, "w", encoding="utf-8") as fh:
            json.dump({**exported, "preview": True}, fh, ensure_ascii=False)     # 미리 보기에서 내보낸 기록
        page.locator('[data-ui-v2="import-file"]').set_input_files(prev)
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"import-bad\"]').dataset.why === 'preview'")
        assert box.inner_text() == C["store"]["otherKind"] and page.get_by_text("내 종목 6개").count() == 1, box.inner_text()
        R.collect(page)
    R.check(page, S, "기록 내보내기 → 지우기 → 불러오기 (잘못된 파일은 기록을 건드리지 않음)", round_trip)

    def from_blank():
        start_build(page)
        page.locator('[data-deck="blank"]').click()
        see(page, C["build"]["s1"]["title"])
        assert not action(page).is_enabled() and action(page).inner_text() == C["build"]["pickCardsBtn"]
        for card, n in (("profit", 5), ("stable", 3), ("value", 2)):
            for _ in range(n):
                page.locator(f'[data-card="{card}"] button[aria-label*="점수 더하기"]').click()
        assert page.locator('[data-ui-v2="points-left"]').inner_text() == "0"
        assert page.locator('[data-card="growth"] button[aria-label*="점수 더하기"]').is_disabled()
        assert page.locator('[data-card="growth"]').get_by_text(C["build"]["cards"]["growth"]["basis"], exact=True).count() == 1
        stable = page.locator('[data-card="stable"]').inner_text()                              # 두 시장 모두: 어느 한 비율 이름도 아님
        assert C["build"]["cards"]["stable"]["basis"] == "부채 부담 낮은 순" and "부채 부담 낮은 순" in stable and "부채비율" not in stable, stable
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
        rules = page.locator('[data-ui-v2="rules"] [data-ui="collapsible"]')
        for i in range(rules.count()):
            rules.nth(i).locator("button").first.click()
        roe = page.locator("[data-rules-for] [data-ui-v2='rule-line']", has_text="밑으로 떨어지면 지켜봐요")
        assert roe.count() >= 1 and re.search(r"ROE.*지금 [\d.]+% · \d+% 밑으로 떨어지면 지켜봐요", roe.first.inner_text().replace("\n", " ")), roe.first.inner_text()
        R.collect(page)
    R.check(page, S, "빈 덱으로 끝까지: 카드 10점 → 지주회사 빼기 → 한국만 → 후보 → 매수 계획", from_blank)

    def partial_buy():
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        recs = page.locator('[data-ui-v2="record-form"] [data-record]')
        n = recs.count()
        recs.first.locator("input").first.fill("0")                  # 계획한 종목 하나는 사지 않았어요
        page.get_by_role("button", name=C["plan"]["save"]).click()
        done_body(page, n - 1)
        R.collect(page)
        page.get_by_role("button", name=C["app"]["close"]).click()
        see(page, C["plan"]["stocks"])
    R.check(page, S, "샀어요에서 한 종목을 0주로 → 기록했어요는 실제로 산 종목 수만 점검한다고 말해요", partial_buy)

    def infeasible():
        page.get_by_role("button", name=C["plan"]["back"]).click()
        page.get_by_role("button", name=PICK_BACK).click()
        see(page, C["build"]["s4"]["title"])
        for _ in range(3):
            dec = page.get_by_role("button", name=C["build"]["s4"]["countDec"])
            if dec.is_enabled():
                dec.click()
        page.locator('[data-ui="segmented"][aria-label="%s"]' % C["build"]["s4"]["maxLabel"]).get_by_role("radio", name="10%").click()
        page.locator('[data-ui-v2="clash"]').wait_for(state="visible")
        txt = page.locator('[data-ui-v2="clash"]').inner_text()
        assert "종목 수" in txt and "한 종목 최대 10%" in txt, txt
        rows = [x.strip() for x in txt.split("\n") if x.strip()]
        assert rows[0] == C["plan"]["clash"] and "종목 수" in rows[1] and "한 종목 최대 10%" in rows[1], rows   # 문장 → 그 아래 조건 목록
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
        for key, r in (("home", "home"), ("portfolio", "portfolio"), ("stocks", "stocks"), ("market", "market")):
            tab(page, TABS[key])                                          # 탭마다 날짜 줄에 멈춤 표시 (v19.0c: 첫 방문 홈에도)
            at(page, r)
            dl = page.locator('[data-ui-v2="date-line"]').first
            dl.wait_for(state="visible")
            assert dl.get_attribute("data-stale") == "1" and "6일째 갱신이 멈췄어요" in dl.inner_text(), (key, dl.inner_text())
            assert page.get_by_text("할 일").count() == 0, key
            R.collect(page)
    R.check(page, f"멈춤 {width}", "발행 6일 전 → 홈 · 포트폴리오 · 종목 · 시장 모두 날짜 줄에 멈춤 표시 (판정 없음)", run)
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
        see(page, LOAD_FAIL)                                              # 첫 방문 홈: 머리글의 뱁이가 있어서 문구만 (그림 하나)
        assert page.locator('[data-ui-v2="date-line"]').count() == 0 and page.locator('[data-ui-v2="popular"]').count() == 0
        assert page.locator('[data-ui-v2="load-fail"]').first.get_attribute("data-picture") == "0"
        assert page.locator("img[src^='baepi-2.png']").count() == 0
        R.collect(page)
        for key in ("stocks", "market"):                                  # 종목 · 시장: 불러오기 실패 문구, 목록 · 칸 없음
            tab(page, TABS[key])
            at(page, key)
            see(page, LOAD_FAIL)
            assert page.locator('[data-ui-v2="market-tile"], [data-ui-v2="stock-row"], [data-ui-v2="stock-search"]').count() == 0, key
            R.collect(page)
        mascot_img(page.locator('[data-ui-v2="load-fail"]').first, "baepi-20-error.webp", 120, C["app"]["loadFailAlt"])    # 시장(숫자 없음): 빠진 플러그를 든 뱁이
        tab(page, C["app"]["tabs"]["portfolio"])                             # 포트폴리오, 저장한 것 없음: 숫자 없는 화면이라 뱁이 그림 그대로 (v19.0b)
        see(page, LOAD_FAIL)
        fail = page.locator('[data-ui-v2="load-fail"]').first
        assert fail.get_attribute("data-picture") == "1" and page.locator('[data-ui-v2="deck-empty"]').count() == 0
        mascot_img(fail, "baepi-20-error.webp", 120, C["app"]["loadFailAlt"])
        R.collect(page)                                                   # 화면 단위 뱁이 규칙(visual_ok)도 통과
        start_build(page)
        see(page, LOAD_FAIL)
        assert page.locator("[data-deck]").count() == 0, "불러오지 못했는데 덱 짜기가 열려요"
        R.collect(page)
    R.check(page, f"{how} {width}", "불러오기 실패 문구 (오늘 · 내 덱(저장한 덱 없음, 뱁이 그대로) · 덱 짜기), 예시 데이터 없음", run)
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
        start_build(page)
        page.locator('[data-ui-v2="build-not-ready"]').wait_for(state="visible")
        see(page, C["app"]["pending"])
        mascot_img(page.locator('[data-ui-v2="build-not-ready"]'), "baepi-21-wip.webp", 64, C["app"]["pendingAlt"])     # 통째로 준비 중: 안전모 뱁이
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
        start_build(page)
        page.locator('[data-deck="quality"]').click()          # 한국 7 : 미국 3 · 미국 종목이 들어가요
        click_next(page)
        click_next(page)
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        see(page, "미국 종목은 현지 기준 10월 29일 종가예요.")
        assert "10월 30일" in date_line(page)
        us = page.locator("section[data-market='us'] [data-cand]")
        for i in range(us.count()):
            us.nth(i).get_by_role("button", name=C["pick"]["receipts"]).click()
        us_rows = page.locator("section[data-market='us'] [data-ui-v2='debt-us']")
        assert us_rows.count() >= 1 and us_rows.first.inner_text().startswith(C["pick"]["receipt"]["debtUs"]), us_rows.count()
        assert "부채비율" not in page.locator("section[data-market='us']").inner_text(), "미국 종목에 '부채비율'"     # Jack, 2026-11-02
        ug = page.locator("section[data-market='us'] [data-ui-v2='growth']")                      # Jack, 2026-11-02 (야후: 분기 대비)
        assert ug.count() >= 1 and all(g.locator("span").first.inner_text() == C["pick"]["receipt"]["growthUs"] for g in ug.all()), ug.count()
        R.collect(page)
        click_next(page)
        see(page, C["plan"]["stocks"])
        warn = page.locator('[data-ui-v2="deck-warn"]')                 # 장기 우량주 · 미국 30% · 1,000만원: 미국 종목을 사요
        tax = warn.locator('[data-ui-v2="us-tax"]')
        assert tax.count() == 1, "미국 종목을 사는데 세금 줄이 없어요"
        assert tax.inner_text().split("\n") == [C["plan"]["deckWarn"]["usTax"], C["plan"]["deckWarn"]["usTaxSource"]], tax.inner_text()
        knew = warn.get_by_text(C["plan"]["deckWarn"]["knew"])
        assert knew.count() == 0 or knew.bounding_box()["y"] < tax.bounding_box()["y"], "세금 줄이 '알고 시작한 일' 앞에 와요"
        R.collect(page)
    R.check(page, f"미국 날짜 {width}", "미국: 현지 종가 날짜 · 차입금 비율(부채비율 아님) · 세금 줄과 출처(2026년 세법 기준)", run)

    def stocks_us_close():
        page.evaluate("location.hash = '#stocks'")                         # 매수 계획 화면에서 바로 종목으로 (주소로)
        at(page, "stocks")
        note = page.locator('[data-ui-v2="us-close"]')
        box = page.locator('[data-ui-v2="stock-search"] input')
        box.fill("Apple")                                                  # 미국 종목이 보이면: 현지 종가 날짜
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-cls="us"]').first.wait_for(state="visible")
        assert note.inner_text() == "미국 종목은 현지 기준 10월 29일 종가예요.", note.all_inner_texts()
        box.fill("삼성")                                                   # 한국 종목만: 그 줄 없음
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"]').first.wait_for(state="visible")
        assert note.count() == 0
        box.fill("")
        assert note.count() == 0 and page.locator('[data-ui-v2="popular-list"][data-market="us"] [data-ui-v2="list-date"]').inner_text() == "10월 29일 기준"
        R.collect(page)
    R.check(page, f"미국 날짜 {width}", "종목: 미국 종목 줄이 보이면 '미국 종목은 현지 기준 10월 29일 종가예요.' (거래대금 미국 목록은 자기 날짜)", stocks_us_close)
    ctx.close()
    srv.shutdown()


def scene_old_app(R, files, width, slots, expect):
    """예전 뱁새(baepsae.html)에 포트폴리오가 있는 방문자: 덱 짜기 첫 화면과 내 덱에 '예전 뱁새 보기' 안내 (Jack, 2026-11-01).
    예전 기록은 읽기만 하고 그대로 둬요."""
    init = f"(() => {{ try {{ localStorage.setItem('baepsae_v10_slots', {json.dumps(slots)}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)

    def run():
        wait_ready(page)
        start_build(page)
        see(page, C["build"]["s0"]["title"])
        note = page.locator('[data-ui-v2="old-app-note"]')
        if not expect:
            assert note.count() == 0, f"포트폴리오 만들기에 안내가 보이면 안 돼요: {slots!r}"
        else:
            assert note.inner_text() == C["app"]["oldAppNote"]
            menu_links(page)                                          # 안내가 가리키는 메뉴의 '예전 뱁새 보기' (v19.0c)
        tab(page, C["app"]["tabs"]["portfolio"])
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


def scene_growth(R, files, width):
    """성장 라벨은 g3 가 실제로 계산된 방식대로 (Jack, 2026-11-02): 재작년 매출을 비우면 모든 한국 종목이 '최근 1년'이 되고,
    발표된 g3 를 다시 계산한 값과 다르게 바꾼 종목(절반)은 성장 줄이 숨어요 (추측하지 않아요)."""
    f = clone(files)
    co = {c["t"]: c for c in f["corp.json"]["companies"]}
    off = set()
    for i, s in enumerate(x for x in f["data.json"]["stocks"] if x["cls"] == "kr"):
        c = co.get(s["t"])
        rev = c and c.get("rev")
        if not rev or not rev[0] or not rev[1] or rev[1] <= 0:
            continue
        rev[2] = None                                                  # 재작년 매출 없음 → 1년 변화
        s["g3"] = round((rev[0] / rev[1] - 1) * 100, 1)
        if i % 2:
            s["g3"] = round(s["g3"] + 5, 1)                            # 다시 계산한 값과 다름 → 숨김
            off.add(s["t"])
    srv, ctx, page, _ = R.open(build_site(f), width)

    def run():
        wait_ready(page)
        start_build(page)
        page.locator('[data-deck="income"]').click()
        click_next(page)
        click_next(page)
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        krc = page.locator("section[data-market='kr'] [data-cand]")
        for i in range(krc.count()):
            krc.nth(i).get_by_role("button", name=C["pick"]["receipts"]).click()
        seen = {"y1": 0, "hidden": 0}
        for i in range(krc.count()):
            card, t = krc.nth(i), krc.nth(i).get_attribute("data-cand")
            g = card.locator("[data-ui-v2='growth']")
            if t in off:
                assert g.count() == 0, f"{t}: 계산 방식을 알 수 없는데 성장 줄이 보여요"
                seen["hidden"] += 1
            elif g.count():
                assert g.get_attribute("data-basis") == "y1" and g.locator("span").first.inner_text() == C["pick"]["receipt"]["growthKr1y"], t
                seen["y1"] += 1
        assert seen["y1"] >= 1 and seen["hidden"] >= 1, seen
        R.collect(page)
    R.check(page, f"성장 라벨 {width}", "한국 성장 줄: 1년 변화면 '매출 증가율 (최근 1년)', 다시 계산이 맞지 않으면 숨김", run)
    ctx.close()
    srv.shutdown()


def scene_locked(R, files, width):
    init = "(() => { try { if (!sessionStorage.getItem('seeded')) { localStorage.setItem('baepsae2.v1', '{\"v\":9,\"stuff\":[1]}'); sessionStorage.setItem('seeded', '1'); } } catch (e) {} })();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)

    def run():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["portfolio"])
        assert page.locator('[data-ui-v2="store-locked"]').inner_text() == C["store"]["locked"]
        assert page.locator('[data-ui-v2="deck-empty"]').count() == 0, "읽지 못한 기록이 있는데 빈 내 덱 카드(뱁이 + 덱 짜기)가 보여요"
        assert page.evaluate("localStorage.getItem('baepsae2.v1')") == '{"v":9,"stuff":[1]}', "읽지 못한 기록을 바꿨어요"
        R.collect(page)
    R.check(page, f"읽지 못한 기록 {width}", "알 수 없는 형식으로 저장된 기록 → '이전에 저장한 기록을 읽지 못해 따로 보관해 두었어요.'", run)
    ctx.close()
    srv.shutdown()


def scene_no_storage(R, files, width):
    init = "(() => { const s = Storage.prototype.setItem; Storage.prototype.setItem = function () { throw new Error('blocked'); }; })();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)

    def run():
        wait_ready(page)
        tab(page, C["app"]["tabs"]["portfolio"])
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


def _op(since, op):
    return {"id": "opDecline", "kind": "keep", "check": "checked", "input": "op", "baseline": op[0], "since": since, "op": op,
            "fy": since, "fellBefore": False}


def _holding(t, nk, target, rules, planned=1):
    return {"t": t, "nk": nk, "cls": "kr", "ind": None, "kind": "core", "target": target, "plannedQty": planned,
            "rules": rules + _pending("audit", "embezzle", "acquisition") + [_band(target)]}


def _deck(i, name, rows):
    # rows: (t, nk, target, rules, qty[, purchase price]). qty 0 = planned but never bought (no purchase record).
    # Bought as planned (plannedQty = qty). No planPx / planFx: these are launch-night style records (the legacy path).
    return {"id": i, "name": name, "createdAt": "2026-10-01", "holdings": [_holding(r[0], r[1], r[2], r[3], r[4]) for r in rows],
            "purchases": [{"t": r[0], "date": "2026-10-01", "qty": r[4], "price": r[5] if len(r) > 5 else 1000, "ccy": "KRW"}
                          for r in rows if r[4] > 0]}


SAMSUNG = ("005930", "삼성전자")
DAILY_DECKS = {"v": 1, "decks": [
    _deck("dcut", "확인 포트폴리오", [("005380", "현대차", 0.5, [_div(2024, 12000.0, 11400.0)], 1), (*SAMSUNG, 0.5, [_div(2025, 1668.0, 1446.0)], 1)]),
    _deck("dclear", "해제 포트폴리오", [("005380", "현대차", 0.5, [_div(2024, 12000.0, 11400.0)], 1), (*SAMSUNG, 0.5, [_div(2025, 1668.0, 1446.0)], 1)]),
    _deck("dwatch", "부채 포트폴리오", [("012450", "한화에어로스페이스", 0.5, [_debt(2024, 150.0, 200)], 1), (*SAMSUNG, 0.5, [], 3)]),
    _deck("dmiss", "자료 포트폴리오", [("000270", "기아", 0.5, [_debt(2024, 60.0, 100)], 7), (*SAMSUNG, 0.5, [], 3)]),
    # 산 날 반반(삼성전자 4주 43,075원 · NAVER 1주 172,300원), 오늘 삼성전자 225,000원 → 83.9% : 줄일 차례 · NAVER 먼저 살 차례
    _deck("dband", "비중 포트폴리오", [(*SAMSUNG, 0.5, [], 4, 43075), ("035420", "NAVER", 0.5, [], 1, 172300)]),
    _deck("dcalm", "조용한 포트폴리오", [("000660", "SK하이닉스", 0.5, [], 1), (*SAMSUNG, 0.5, [_div(2025, 1668.0, 1446.0)], 6)]),
    _deck("dop", "이익 포트폴리오", [("005380", "현대차", 0.5, [_op(2024, [142395.9, 151269.0, None])], 1), (*SAMSUNG, 0.5, [], 1)]),
    # 계획 3종목(30% · 30% · 40%) 중 기아는 0주: 산 두 종목의 목표는 50% · 50% 로 다시 나눠요. 오늘 종가에 산 날 → 할 일 없음
    _deck("dplan", "계획 포트폴리오", [(*SAMSUNG, 0.3, [], 4, 225000), ("035420", "NAVER", 0.3, [], 5, 172300), ("000270", "기아", 0.4, [], 0)]),
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
        tab(page, C["app"]["tabs"]["portfolio"])
        see(page, "조용한 포트폴리오")
        page.locator("[data-holding][data-status]").first.wait_for(state="visible")

    def statuses():
        open_deck()
        st = {(i, t): row(i, t).get_attribute("data-status") for i, t in
              (("dcut", "005380"), ("dclear", "005380"), ("dwatch", "012450"), ("dmiss", "000270"), ("dband", "005930"),
               ("dband", "035420"), ("dcalm", "000660"), ("dcalm", "005930"), ("dop", "005380"), ("dplan", "005930"), ("dplan", "035420"))}
        assert st == {("dcut", "005380"): "check", ("dclear", "005380"): "check", ("dwatch", "012450"): "watch",
                      ("dmiss", "000270"): "check", ("dband", "005930"): "trim", ("dband", "035420"): "low",
                      ("dcalm", "000660"): "none", ("dcalm", "005930"): "none", ("dop", "005380"): "watch",
                      ("dplan", "005930"): "none", ("dplan", "035420"): "none"}, st
        assert deck("dplan").locator('[data-holding="000270"]').count() == 0            # 사지 않은 종목은 점검하지 않아요
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "저장된 덱 6개 → 종목마다 상태 (확인 필요 · 지켜봐요 · 비중 · 할 일 없음)", statuses)

    def check_needed():
        r = row("dcut", "005380")
        line = r.locator('[data-ui-v2="status-line"][data-code="divDrop"]')
        assert "현대차 배당이 줄었어요 · 주당 12,000원 → 10,000원" in line.inner_text(), line.inner_text()
        assert C["pick"]["caution"]["divDropBody"] in line.inner_text() and "2025년 사업보고서 기준" in line.inner_text()
        assert r.locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["check"]]      # 확인 필요 칩 (Jack, 2026-11-02)
        assert C["daily"]["broken"] not in deck("dcut").inner_text(), "확인 전인데 규칙 깨짐이 보여요"
        btns = r.locator('[data-ui-v2="confirm"] button')
        assert btns.all_inner_texts() == [C["daily"]["confirmCut"], C["daily"]["confirmNotCut"]]
        assert [b.get_attribute("aria-checked") for b in btns.all()] == ["false", "false"]
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
        op = row("dop", "005380").locator('[data-ui-v2="status-line"][data-code="opFell2"]').inner_text()
        assert "영업이익이 2년째 줄고 있어요 · 15.1조원 → 14.2조원 → 11.5조원 · 2년 연속 줄면 지켜봐요" in op and "2025년 사업보고서 기준" in op, op
        m = row("dmiss", "000270")
        assert "부채비율 자료를 받지 못해 확인이 필요해요" in m.locator('[data-ui-v2="status-line"][data-code="missing"]').inner_text()
        assert m.locator('[data-ui-v2="confirm"]').count() == 0
        R.collect(page)
    R.check(page, S, "부채비율·영업이익 기준 어긋남 → 지켜봐요 (숫자 · 보고서 연도) · 산 때 있던 자료가 비면 확인 필요", keep_and_missing)

    def bands_and_calm():
        hi = row("dband", "005930").locator('[data-ui-v2="status-line"][data-code="band"]').inner_text()
        lo = row("dband", "035420").locator('[data-ui-v2="status-line"][data-code="band"]').inner_text()
        assert "70.0% 넘으면 일부 팔아요" in hi and "83.9%" in hi and "37.5% 미만이면 먼저 사요" in lo, (hi, lo)
        fold = row("dplan", "005930").locator('[data-ui="collapsible"]')
        fold.locator("button").first.click()
        assert "목표 50.0%" in fold.inner_text() and "목표 30.0%" not in fold.inner_text(), fold.inner_text()   # 산 종목끼리 다시 나눈 목표
        fold.locator("button").first.click()
        assert row("dband", "005930").locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["band"]["trim"]]   # 비중 칩 (Jack, 2026-11-02)
        assert row("dband", "035420").locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["band"]["low"]]
        calm = deck("dcalm")
        assert calm.locator('[data-ui-v2="status-line"]').count() == 0
        assert row("dcalm", "000660").locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["bigMove"]]
        assert row("dcalm", "005930").locator('[data-ui="status-chip"]').count() == 0       # 칩이 없으면 괜찮은 종목
        nc = calm.locator('[data-ui-v2="not-checked"]').inner_text()
        assert re.fullmatch(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", nc), nc
        folds = calm.locator('[data-ui="collapsible"]')
        for i in range(folds.count()):
            folds.nth(i).locator("button").first.click()
        shown = calm.locator('[data-rules-today] [data-check="pending"]').count()
        assert shown == int(re.search(r"\d+", nc).group()) == 6, (shown, nc)          # 세는 규칙 = 보이는 준비 중 줄
        for i in range(folds.count()):
            folds.nth(i).locator("button").first.click()
        note = page.locator('[data-ui-v2="rebased-note"]')
        assert note.count() == 1 and deck("dplan").locator('[data-ui-v2="rebased-note"]').inner_text() == \
            "계획한 3종목 중 2종목만 샀어요. 목표 비중은 산 종목끼리 다시 나눠 계산해요.", note.all_inner_texts()
        assert page.locator('[data-ui-v2="not-checked"]').count() == 8
        R.collect(page)
    R.check(page, S, "비중 벗어남 · 할 일 없음(칩 없음) · 큰 움직임은 칩만 · '아직 자동으로 확인하지 못하는 규칙' 줄", bands_and_calm)

    def answer(i, which):
        row(i, "005380").get_by_role("radio", name=C["daily"][which]).click()

    def wait_status(i, want):
        page.wait_for_function(f"() => document.querySelector('[data-deck-id=\"{i}\"] [data-holding=\"005380\"]').dataset.status === '{want}'")

    def checked(i):
        return [b.get_attribute("aria-checked") for b in row(i, "005380").locator('[data-ui-v2="confirm"] button').all()]

    def confirm_cut():
        answer("dcut", "confirmCut")
        r = row("dcut", "005380")
        wait_status("dcut", "broken")
        assert r.locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["broken"]]
        assert checked("dcut") == ["true", "false"], "고른 답이 표시되지 않거나 버튼이 사라졌어요"
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
        answer("dclear", "confirmNotCut")
        wait_status("dclear", "none")
        r = row("dclear", "005380")
        assert r.locator('[data-ui="status-chip"]').count() == 0 and checked("dclear") == ["false", "true"]
        assert "현대차 배당이 줄었어요 · 주당 12,000원 → 10,000원" in r.locator('[data-ui-v2="status-line"][data-code="divCleared"]').inner_text()
        assert row("dcut", "005380").get_attribute("data-status") == "broken"
        R.collect(page)
    R.check(page, S, "줄인 게 아니에요 → 그 보고서의 감소는 해제, 두 답은 그대로 보여요 (다른 덱은 그대로)", confirm_clear)

    def switch_answer():
        answer("dclear", "confirmCut")                                 # 잘못 누른 답을 바꿔요
        wait_status("dclear", "broken")
        page.reload(wait_until="domcontentloaded")
        open_deck()
        assert row("dclear", "005380").get_attribute("data-status") == "broken" and checked("dclear") == ["true", "false"]
        answer("dclear", "confirmNotCut")
        wait_status("dclear", "none")
        page.reload(wait_until="domcontentloaded")
        open_deck()
        assert row("dclear", "005380").get_attribute("data-status") == "none" and checked("dclear") == ["false", "true"]
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        cs = [d.get("confirms") for d in stored["decks"] if d["id"] == "dclear"][0]
        assert [c["answer"] for c in cs] == ["notCut"], cs                 # 같은 일의 답은 하나만 남아요
        assert row("dcut", "005380").get_attribute("data-status") == "broken"
        R.collect(page)
    R.check(page, S, "답 바꾸기: 줄인 게 아니에요 → 실제로 줄였어요 → 줄인 게 아니에요, 새로 고침해도 바꾼 답이 남아요", switch_answer)

    def today_hero():
        tab(page, C["app"]["tabs"]["home"])
        hero = page.locator('[data-ui-v2="today-hero"]')
        hero.wait_for(state="visible")
        assert page.locator('[data-ui-v2="home-hero"]').count() == 0, "저장한 포트폴리오가 있는데 첫 방문 머리글이 보여요"
        # 매도 조건(현대차, 실제로 줄였어요)과 확인 필요(기아, 부채비율 자료 없음)가 오늘 확인할 일이에요
        assert hero.get_attribute("data-state") == "todo", hero.inner_text()
        items = hero.locator('[data-ui-v2="todo-item"]').evaluate_all("els => els.map(e => e.dataset.t + ':' + e.dataset.status)")
        assert "005380:broken" in items and "000270:check" in items, items
        assert hero.locator('[data-ui-v2="todo-item"]').first.get_attribute("data-status") == "broken"     # 매도 조건이 맨 위
        txt = hero.inner_text()
        assert txt.startswith(f"오늘 확인할 일 {len(items)}개"), txt
        assert C["daily"]["sellNow"] in txt and C["today"]["sellLabel"] in txt and "배당 삭감 · 주당 12,000원 → 10,000원" in txt, txt
        assert "부채비율 자료를 받지 못해 확인이 필요해요" in txt and C["today"]["calmTitle"].replace("\n", "") not in txt.replace("\n", "")
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", txt)
        big = page.locator('[data-ui-v2="big-moves"]')                 # 큰 움직임은 판정과 따로, 표시만
        assert "SK하이닉스" in big.inner_text() and big.locator('[data-ui-v2="why-link"]').count() == 1
        assert page.locator('[data-ui-v2="deck-strip"]').count() == len(DAILY_DECKS["decks"])
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "오늘: 확인할 일 띠 '오늘 확인할 일' (매도 조건 먼저 · 확인 필요) · 못 하는 규칙 줄 · 큰 움직임은 따로 · 덱마다 띠", today_hero)
    ctx.close()
    srv.shutdown()

    for how, f, drop in (("멈춤", daily_files(files, days_ago=6), ()), ("실패", daily_files(files), ("data.json",))):
        srv, ctx, page, _ = R.open(build_site(f, drop=drop), width, init=init)

        def no_status():
            wait_ready(page)
            tab(page, C["app"]["tabs"]["home"])                          # 오늘: 멈춤 띠 또는 불러오기 실패, 할 일 띠는 없음
            if how == "멈춤":
                see(page, "데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요")
                band = page.locator('[data-ui-v2="today-stale"] [data-ui="hero-band"]')     # 판정이 아니라서 상태 아이콘 없음, 지켜봐요 바탕
                assert band.get_attribute("data-tone") == "stale" and band.locator('[data-ui="state-icon"], img').count() == 0
                assert hero_colours(band)[0] == "rgb(255, 243, 214)"
                dl = page.locator('[data-ui-v2="date-line"]').first
                assert dl.get_attribute("data-stale") == "1" and "6일째 갱신이 멈췄어요" in dl.inner_text(), dl.inner_text()
            else:
                see(page, LOAD_FAIL)
            for sel in ('[data-ui-v2="today-hero"]', '[data-ui-v2="deck-strip"]', '[data-ui-v2="big-moves"]', '[data-ui-v2="today-not-checked"]'):
                assert page.locator(sel).count() == 0, sel
            assert page.get_by_text("할 일").count() == 0
            R.collect(page)
            tab(page, C["app"]["tabs"]["portfolio"])
            see(page, "조용한 포트폴리오")
            if how == "멈춤":
                assert page.locator('[data-ui-v2="deck-stale"]').inner_text() == "데이터가 6일째 갱신되지 않아 오늘은 점검하지 않았어요"
                assert page.locator('[data-ui-v2="load-fail"]').count() == 0
            else:                                                       # 칩 없는 종목이 '괜찮음'으로 읽히지 않게
                assert page.locator('[data-ui-v2="deck-stale"]').count() == 0
                assert page.locator('[data-ui-v2="load-fail"]').inner_text().strip() == LOAD_FAIL
                fail = page.locator('[data-ui-v2="load-fail"]')            # 기록(숫자)이 보이는 화면이라 뱁이 그림 없이 문구만 (v19.0b)
                assert fail.get_attribute("data-picture") == "0" and fail.locator("img").count() == 0
            assert page.locator("[data-holding][data-status]").count() == 0, "멈춘·실패한 데이터로 판정했어요"
            for sel in ('[data-ui-v2="status-line"]', '[data-ui-v2="confirm"]', '[data-ui-v2="not-checked"]', '[data-holding] [data-ui="status-chip"]', "[data-rules-today]"):
                assert page.locator(sel).count() == 0, sel
            assert page.get_by_text("할 일").count() == 0
            assert page.get_by_text("평균 단가").count() == 16                # 기록은 그대로 보여요
            for sel in ('[data-ui-v2="deck-summary"]', '[data-ui-v2="weight"]', '[data-ui-v2="add-money"]'):
                assert page.locator(sel).count() == 0, sel                     # 평가 금액 · 비중 · 추가로 넣을 돈도 없어요
            R.collect(page)
        R.check(page, f"매일 점검 · {how} {width}", "판정 없음 (상태 · 버튼 · 규칙 결과 모두 없음) + 이유 문장, 기록은 그대로", no_status)
        ctx.close()
        srv.shutdown()


# ── 오늘 · 내 덱 · 왜 움직였나 (Part E) ──
# 덱 하나씩 저장해서 오늘의 큰 띠가 한 가지 상태만 보이게 해요. 산 가격은 오늘 종가의 95% (수익률이 그럴듯하게).
def _buy(t, nk, target, rules, qty, by):
    return (t, nk, target, rules, qty, round(by[t]["price"] * 0.95))


def _one_deck(i, name, rows, confirms=None):
    d = {"id": i, "name": name, "createdAt": "2026-10-01", "holdings": [{**_holding(t, nk, tg, r), "plannedQty": q} for t, nk, tg, r, q, _ in rows],
         "purchases": [{"t": t, "date": "2026-10-01", "qty": q, "price": px, "ccy": "KRW"} for t, _, _, _, q, px in rows]}
    if confirms:
        d["confirms"] = confirms
    return {"v": 1, "decks": [d]}


def today_files(files):
    f = daily_files(files)
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    by["105560"].update(dps=3000.0, dps3=[3000.0, 4367.0, 3174.0], fy=2025, d1=0.5)     # KB금융: 2025년 보고서에서 배당 삭감
    by["012450"]["d1"] = -8.0                                                           # 지켜봐요 종목이 크게 움직인 날
    by["003550"].update(dps=2500.0, dps3=[2500.0, 3100.0, 3100.0], fy=2025)              # LG: 2025년 보고서에서 배당 삭감
    by["132030"]["d1"] = -6.0                                                           # 금 안전자산(국내 상장 ETF)이 크게 움직인 날
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
        "sell": _one_deck("dsell", "매도 포트폴리오", [_buy("105560", "KB금융", 0.5, [_div(2024, 4367.0, 3174.0)], 10, by), sam(7)], cut),
        # 영문으로 끝나는 이름의 규칙 깨짐: 'LG가 매도 조건에 걸렸어요' (Jack, 2026-11-02: 이/가 는 마지막 글자의 읽기로)
        "sellEn": _one_deck("dsellen", "지주 포트폴리오", [_buy("003550", "LG", 0.5, [_div(2024, 3100.0, 3100.0)], 20, by), sam(8)],
                            [{"t": "003550", "rule": "divCut", "fy": 2025, "a": 3100.0, "b": 2500.0, "answer": "cut", "at": "2026-11-01"}]),
        "watch": _one_deck("dwatch", "부채 포트폴리오", [_buy("012450", "한화에어로스페이스", 0.5, [_debt(2024, 150.0, 200)], 1, by), sam(1)]),
        "check": _one_deck("dcheck", "확인 포트폴리오", [_buy("005380", "현대차", 0.5, [_div(2024, 12000.0, 11400.0)], 2, by), sam(2)]),
        # 같은 금액(200만원씩)으로 산 뒤 삼성전자만 크게 올라 비중이 벗어난 덱 (산 날의 비중 = 목표: Part C 의 간격 없음)
        "band": _one_deck("dband", "비중 포트폴리오", [("005930", "삼성전자", 0.5, [], 20, 100000), ("035420", "NAVER", 0.5, [], 2, 1000000)]),
        # SK하이닉스: 배당 규칙은 산 뒤 새 보고서(2025)로 확인 · 부채비율 규칙은 산 때 보고서뿐(새로 확인한 것 아님) → '규칙 2개'(배당 + 비중)
        "big": _one_deck("dbig", "반도체 포트폴리오", [_buy("000660", "SK하이닉스", 0.5, [_div(2024, 2204.0, 1200.0), _debt(2025, 46.0, 100)], 1, by), sam(6)]),
    }
    # 안전자산(채권·금) 종목: 국내 상장 ETF 라 가격 출처는 한국거래소 (cls 가 bond · metal 이어도 미국이 아니에요)
    decks["cushion"] = _one_deck("dcushion", "안전자산 포트폴리오", [("132030", "KODEX 골드선물(H)", 0.5, [], 40, round(by["132030"]["price"])), sam(4)])
    # 반도체 포트폴리오은 계획한 기아를 사지 않았어요(0주): 목표는 산 두 종목끼리 다시 나눠요 → 내 덱 · 왜 움직였나에 같은 안내
    decks["big"]["decks"][0]["holdings"].append({**_holding("000270", "기아", 0.2, []), "plannedQty": 1})

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
        verdict_icon(h, "alert")                                                     # 확인할 일: flag, 규칙 깨짐이 있으니 남색 알약
        assert hero_colours(h) == ["rgb(255, 243, 214)", NAVY_RGB, "rgb(255, 255, 255)"], hero_colours(h)
        assert page.locator('[data-today-holding="105560"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["broken"]]
        assert page.locator('[data-today-holding="005930"] [data-ui="status-chip"]').count() == 0          # 칩 없음 = 괜찮아요
        strip = page.locator('[data-ui-v2="deck-strip"]').inner_text()
        assert "평가 금액" in strip and "수익률" in strip and re.search(r"오늘 [+−]?\d+\.\d%", strip), strip
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "매도 조건 → 확인할 일 띠(지켜봐요 바탕 · 규칙 깨짐 남색 알약 · flag) 'KB금융이 매도 조건에 걸렸어요' · 배당 삭감 숫자 · 보고서 연도 · 나머지 이상 없음", sell)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("sellEn")

    def sell_en():
        h = hero(page)
        assert h.get_attribute("data-state") == "todo"
        title = h.locator("h2").inner_text()
        assert title == "LG가\n매도 조건에 걸렸어요", repr(title)                 # 영문 이름 G(지) → 가
        assert "배당 삭감 · 주당 3,100원 → 2,500원" in h.inner_text()
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "영문으로 끝나는 이름의 매도 조건 → 'LG가 매도 조건에 걸렸어요' (이/가 를 바르게)", sell_en)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("watch")

    def watch():
        h = hero(page)
        assert h.get_attribute("data-state") == "calm"
        txt = h.inner_text()
        assert C["today"]["calmTitle"] in txt, txt                     # 지켜봐요가 있어도 맞는 말 (매도 조건에 걸린 종목은 없어요)
        assert C["today"]["calmEyebrow"] not in txt, txt               # 하지만 '오늘은 할 일이 없어요'는 모든 종목이 할 일 없음일 때만
        not_checked(txt)
        verdict_icon(h, "calm")
        assert page.locator('[data-today-holding="012450"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["watch"], C["daily"]["bigMove"]]
        assert "크게 움직인 종목은 1개 있어요" in txt
        R.collect(page)
        # 왜 움직였나는 규칙 판정을 그대로 보여요: 지켜봐요 · 부채비율 221% (기준 200%) · '할 일 없음'이 아님
        h.locator('[data-ui-v2="why-link"]').click()
        v = page.locator('[data-ui-v2="why-verdict"]')
        v.wait_for(state="visible")
        vt = v.inner_text()
        assert v.get_attribute("data-status") == "watch" and vt.startswith(C["daily"]["watch"]), vt
        verdict_icon(v, "alert")
        assert hero_colours(v)[1] == "rgb(138, 90, 0)", hero_colours(v)                   # 지켜봐요 알약 (살구색 아님)
        assert "부채비율 221% (기준 200%)" in vt and C["why"]["noTodo"] not in vt and "지켜지고 있어요" not in vt, vt
        assert "지켜지고 있어요" not in page.locator('[data-ui-v2="why-rules"]').inner_text()
        no_hscroll(page, width)
        R.collect(page)
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()
        hero(page)
        tab(page, C["app"]["tabs"]["portfolio"])
        add = page.locator('[data-ui-v2="add-money"]')
        add.get_by_role("button", name="+1,000만").click()
        buys = page.locator('[data-ui-v2="add-buys"] [data-add]')
        buys.first.wait_for(state="visible")
        got = buys.evaluate_all("els => els.map(e => e.dataset.add)")
        assert got == ["005930"], got                                                  # 지켜봐요 종목은 사지 않아요
        left = page.locator('[data-ui-v2="add-left"]').inner_text()
        assert re.fullmatch(r"남는 돈 [\d,]+(만원|원) · 살지 말지는 직접 정해 주세요", left), left
        # 산 날의 비중이 반올림으로 목표와 달라 경계가 넓어진 덱: '0.75~1.25배' 안내 대신 종목마다 오늘 쓰는 경계
        assert page.locator('[data-ui-v2="band-note"]').count() == 0
        edges = page.locator('[data-holding="012450"] [data-ui-v2="weight-edges"]').inner_text()
        assert re.fullmatch(r"[\d.]+% 미만이면 먼저 사요 · [\d.]+% 넘으면 더 사지 않아요 · [\d.]+% 넘으면 일부 팔아요", edges) and "62.5% 넘으면 더 사지" not in edges, edges
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
        assert page.locator('[data-today-holding="005380"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["check"]]
        not_checked(txt)
        verdict_icon(h, "alert")
        assert hero_colours(h) == ["rgb(255, 243, 214)", "rgb(138, 90, 0)", "rgb(255, 255, 255)"], hero_colours(h)   # 확인 필요만: 지켜봐요 알약
        R.collect(page)
        h.get_by_role("radio", name=C["daily"]["confirmNotCut"]).click()
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"today-hero\"]').dataset.state === 'calm'")
        assert C["today"]["calmTitle"] in hero(page).inner_text()
        verdict_icon(hero(page), "calm")
        R.collect(page)
    R.check(page, S, "확인 필요 → 확인할 일 띠(지켜봐요 알약 · flag)의 두 버튼 → '줄인 게 아니에요' → 초록 띠(check-circle)", check)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("band")

    def band():
        h = hero(page)
        assert h.get_attribute("data-state") == "calm"
        txt = h.inner_text()
        assert C["today"]["calmTitle"] in txt and C["today"]["calmEyebrow"] not in txt, txt        # 줄일 차례는 할 일이 있어요
        not_checked(txt)
        chips = {t: page.locator(f'[data-today-holding="{t}"] [data-ui="status-chip"]').all_inner_texts() for t in ("005930", "035420")}
        assert chips == {"005930": [C["daily"]["band"]["trim"]], "035420": [C["daily"]["band"]["low"]]}, chips   # 비중 칩
        R.collect(page)
        tab(page, C["app"]["tabs"]["portfolio"])
        page.locator('[data-ui-v2="weight"]').first.wait_for(state="visible")
        bands = dict(page.locator('[data-holding]').evaluate_all("els => els.map(e => [e.dataset.holding, e.querySelector('[data-ui-v2=weight]')?.dataset.band || ''])"))
        assert bands == {"005930": "trim", "035420": "low"}, bands
        assert page.locator('[data-ui-v2="band-note"]').count() == 1, "같은 금액으로 산 덱인데 '0.75~1.25배' 안내가 없어요"
        # 같은 금액으로 산 덱이라 경계가 넓어지지 않았어요: '0.75~1.25배' 안내와 종목마다 같은 경계
        assert page.locator('[data-ui-v2="band-note"]').inner_text() == C["deck"]["bandNote"]
        edges = page.locator('[data-holding="005930"] [data-ui-v2="weight-edges"]').inner_text()
        assert edges == "37.5% 미만이면 먼저 사요 · 62.5% 넘으면 더 사지 않아요 · 70.0% 넘으면 일부 팔아요", edges
        bar = page.locator('[data-holding="005930"] [data-ui-v2="band-bar"]')          # 막대는 비중(약 93%)보다 넓은 눈금
        top, now = float(bar.get_attribute("data-top")), float(bar.get_attribute("aria-valuenow")) / 100
        assert top >= 1.1 * now - 0.002, (top, now)
        assert bar.locator("[data-edge]").count() == 3
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
        verdict_icon(h, "calm")
        assert hero_colours(h) == ["rgb(237, 244, 239)", "rgb(31, 122, 77)", "rgb(255, 255, 255)"], hero_colours(h)
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
        assert "반도체 · 10월 30일 종가" in head and "1,418,000원" in head and "−6.2%" in head, head
        v = page.locator('[data-ui-v2="why-verdict"]')
        assert v.get_attribute("data-status") == "none"
        vt = v.inner_text()
        assert C["why"]["noTodo"] in vt and "업종이 다 같이\n빠진 날이에요" in vt and "규칙 2개가 모두 지켜지고 있어요." in vt, vt
        verdict_icon(v, "calm")
        assert page.locator("main img[src^='baepi-']").count() == 0, "왜 움직였나(숫자 화면)에 뱁이가 있어요"
        price = page.locator('[data-ui-v2="why-price"]')                          # 큰 숫자: 단위는 작고 가볍게
        unit = price.locator("[data-unit]")
        assert price.inner_text() == "1,418,000원" and unit.inner_text() == "원"
        fs = price.evaluate("(e) => [parseFloat(getComputedStyle(e).fontSize), parseFloat(getComputedStyle(e.querySelector('[data-unit]')).fontSize), getComputedStyle(e).fontWeight, getComputedStyle(e.querySelector('[data-unit]')).fontWeight]")
        assert fs[1] < fs[0] and int(fs[3]) < int(fs[2]), fs
        not_checked(vt)
        peers = page.locator('[data-ui-v2="why-peers"]')
        assert C["why"]["c1Title"] in peers.inner_text() and re.search(r"반도체 종목 (\d+)개 중 \1개가 빠졌어요", peers.inner_text()), peers.inner_text()
        assert peers.locator('[data-ui="dot-strip"] [data-mine="1"]').count() == 1
        rules = page.locator('[data-ui-v2="why-rules"]').inner_text()
        assert "규칙 2개가 모두 지켜지고 있어요" in rules and C["app"]["notChecked"] in rules, rules
        assert C["why"]["alertLine"] and C["why"]["alertLine"] in rules and "오늘 화면" not in rules, rules   # Jack, 2026-11-04 승인
        assert "뉴스" not in page.locator("main").inner_text() and "다음에 확인할 일" not in page.locator("main").inner_text()
        rebased = "계획한 3종목 중 2종목만 샀어요. 목표 비중은 산 종목끼리 다시 나눠 계산해요."
        assert page.locator('[data-ui-v2="why-rebased"]').inner_text() == rebased
        src = page.locator('[data-ui-v2="why-sources"]')
        src.locator("button").first.click()
        st = src.inner_text()
        assert "한국거래소 10월 30일 종가" in st and re.search(r"반도체 \d+개 종목", st) and "2025년 사업보고서 기준" in st, st
        page.get_by_role("button", name=C["why"]["explainTitle"]).click()        # v18.4: 첫 칩이 비어 있었어요 (daily.ok 없음)
        chips = page.locator('[data-ui-v2="why-explain"] [data-ui="status-chip"]').all_inner_texts()
        assert chips == [C["daily"]["ok"], C["daily"]["watch"], C["daily"]["broken"]] == ["괜찮아요", "지켜봐요", "규칙 깨짐"], chips
        no_hscroll(page, width)
        R.collect(page)
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()
        hero(page)
        assert page.get_by_text("SK하이닉스 왜 움직였나").count() == 0
    R.check(page, S, "큰 움직임 → '같은 업종이 다 같이 빠졌어요' → 자세히 보기 → 왜 움직였나(판정 · 점 띠 · 규칙 · 출처) → 오늘", big_and_why)

    def deck_sheet():
        tab(page, C["app"]["tabs"]["portfolio"])
        page.locator('[data-ui-v2="deck-summary"]').wait_for(state="visible")
        assert re.fullmatch(r"[\d,]+만원", page.locator('[data-ui-v2="deck-value"]').inner_text())
        money = page.locator('[data-ui-v2="deck-money"]').inner_text()
        assert re.fullmatch(r"원금 [\d,]+만원 · 수익 \+[\d,]+만원 \(\+[\d,]+\.\d%\)", money), money
        vs_kospi(page)
        assert "10월 1일 시작" in page.locator('[data-ui-v2="deck-start"]').inner_text()
        assert page.locator('[data-ui-v2="rebased-note"]').inner_text() == "계획한 3종목 중 2종목만 샀어요. 목표 비중은 산 종목끼리 다시 나눠 계산해요."
        assert page.locator('[data-ui-v2="weight"]').count() == 2
        assert page.locator('[data-ui-v2="weight-edges"]').count() == 2               # 종목마다 오늘 쓰는 경계
        page.locator('[data-ui-v2="add-empty"]').wait_for(state="visible")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "내 덱: 평가 금액 · 원금 · 수익 · 내 덱 vs 코스피 숫자 두 개 · 시작일 · 비중 막대 · 추가로 넣을 돈", deck_sheet)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("cushion")

    def cushion_source():
        hero(page)
        page.locator('[data-big-move="132030"] [data-ui-v2="why-link"]').click()
        see(page, "KODEX 골드선물(H) 왜 움직였나")
        src = page.locator('[data-ui-v2="why-sources"]')
        src.locator("button").first.click()
        st = src.inner_text()
        assert "한국거래소 10월 30일 종가" in st and "야후 파이낸스" not in st, st
        assert page.locator('[data-ui-v2="why-peers"]').count() == 0               # 업종 그룹이 없으니 점 띠도 없어요
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "국내 상장 안전자산(금 ETF)의 왜 움직였나 → 가격 출처는 한국거래소", cushion_source)
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


# ── 소개 (v19.0 Part D) ──
ABOUT_KEY = "baepsae_v2_about_lang"
NOT_GROUPS = ("", "etc", "other")                       # src/v2/engine.js NOT_GROUPS + 빈 값


def about_counts(data):
    """about.md 의 숫자 줄 규칙을 파이썬으로 따로 세요: cls kr·us 종목 수, 그 종목들의 업종 그룹 수, 백 단위 내림."""
    covered = [s for s in data["stocks"] if s.get("cls") in ("kr", "us")]
    groups = {s["ind"] for s in covered if isinstance(s.get("ind"), str) and s["ind"] not in NOT_GROUPS}
    return len(covered), len(groups), len(covered) // 100 * 100


def about_page(page):
    box = page.locator('[data-ui-v2="about"]')
    box.wait_for(state="visible")
    return box


def footer_ok(page):
    """보이는 푸터: 고지문 · 소개(#about), 만든 사람 줄 없음."""
    f = page.locator('[data-ui-v2="footer"]:visible').first
    f.wait_for(state="visible")
    text = f.inner_text()
    assert text.replace("\n", " ").strip() == f'{C["app"]["footer"]} · {C["app"]["aboutLink"]}', text
    assert "INSEAD" not in text and "이성진" not in text, text
    link = f.locator('[data-ui-v2="about-link"]')
    assert link.inner_text() == C["app"]["aboutLink"] == "소개" and link.get_attribute("href") == "#about"
    box = link.bounding_box()
    assert box and box["height"] >= 44, box
    return link


def images_loaded(page):
    imgs = page.evaluate("""() => [...document.querySelectorAll('[data-ui-v2="about"] img')].map((i) => [i.getAttribute('src'), i.complete && i.naturalWidth > 0])""")
    assert sorted(i for i, _ in imgs) == ["baepi-og.webp", "jack-photo.jpg"] and all(ok for _, ok in imgs), imgs


def scene_about(R, files, width):
    S = f"소개 {width}"
    count, groups, n = about_counts(files["data.json"])
    assert count > 100 and groups > 5, (count, groups)
    ko, en = C["about"]["ko"], C["about"]["en"]
    srv, ctx, page, base = R.open(build_site(files), width)

    def footer_and_open():
        wait_ready(page)
        at(page, "home")                                                  # 첫 화면 (저장한 포트폴리오 없음: 첫 방문 홈)
        link = footer_ok(page)
        link.focus()
        link.click()
        about_page(page)
        assert page.url.endswith("#about"), page.url
        assert page.evaluate("document.activeElement && document.activeElement.dataset.uiV2") == "about-heading", "소개 제목으로 초점이 가지 않았어요"
        assert page.locator('[data-ui-v2="about"]').get_attribute("data-lang") == "ko"
        assert page.locator('[data-ui-v2="home-hero"]').is_visible() is False, "소개 뒤에 전 화면이 보여요"
        assert page.locator('nav[data-ui="bottom-tab-bar"]:visible').count() == 0
        assert page.locator('[data-ui-v2="about"] [data-ui-v2="menu-button"]').count() == 0      # 소개는 뒤로(닫기)로만 닫아요
        page.get_by_role("button", name=C["app"]["close"]).click()        # 뒤로 → 전 화면 (v19.0c: 그 화면의 주소 #home)
        at(page, "home")
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
        assert page.url.endswith("#home") and page.evaluate("history.state && history.state.v2") == 0, page.url
        assert page.evaluate("document.activeElement && document.activeElement.dataset.uiV2") == "about-link", "초점이 소개 링크로 돌아오지 않았어요"
    R.check(page, S, "푸터: 고지문 · '소개'(#about), 만든 사람 줄 없음 → 소개(초점은 제목) → 뒤로 → 전 화면 (#home, 초점은 링크)", footer_and_open)

    def about_ko():
        page.goto(base + "/app.html?dev=1#about", wait_until="domcontentloaded")
        box = about_page(page)
        assert box.get_attribute("data-lang") == "ko"
        assert page.locator('[data-ui-v2="about-descriptor"]').inner_text() == ko["hero"]["descriptor"]
        for t in (ko["hero"]["catch"], ko["what"]["title"], ko["principles"]["title"], ko["name"]["title"], ko["maker"]["title"]):
            see(page, t)
        assert page.locator('[data-ui-v2="app-bar"] h1:visible').inner_text() == C["app"]["brand"]
        figs = page.locator('[data-ui-v2="about-figures"]')
        figs.wait_for(state="visible")
        st = page.locator('[data-ui-v2="about-stocks"]').inner_text().split("\n")
        gr = page.locator('[data-ui-v2="about-groups"]').inner_text().split("\n")
        assert st == [f"{count:,}", ko["figures"]["stocks"]], (st, count)
        assert gr == [f"{groups:,}", ko["figures"]["groups"]], (gr, groups)
        assert page.locator('[data-ui-v2="about-refresh"]').inner_text() == ko["figures"]["refresh"]
        data = page.locator('[data-ui-v2="about-data"]').inner_text()
        assert data == ko["what"]["data"].replace("{n}", f"{n:,}") and f"{n:,}개가 넘는" in data, data
        photo = page.locator('[data-ui-v2="about-photo"]')
        assert photo.get_attribute("alt") == ko["maker"]["photoAlt"] == "이성진 사진"
        pb = photo.bounding_box()
        assert pb and abs(pb["width"] - 88) < 1 and abs(pb["height"] - 88) < 1, pb
        assert photo.evaluate("(e) => getComputedStyle(e).borderRadius") in ("999px", "50%"), "사진이 동그랗지 않아요"
        li = page.locator('[data-ui-v2="about-linkedin"]')
        assert li.get_attribute("href") == C["about"]["linkedInUrl"] and li.get_attribute("target") == "_blank" and li.get_attribute("rel") == "noopener"
        images_loaded(page)
        footer_ok(page)
        assert "INSEAD MBA 26J" not in page.locator("body").inner_text()
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, f"#about 로 열면 한국어 · 숫자 줄 = 데이터로 센 값({count:,} 종목 · {groups} 그룹) · '{n:,}개가 넘는' · 사진 88px · LinkedIn 새 탭", about_ko)

    def to_english():
        page.get_by_role("radio", name=C["about"]["langs"]["en"]).click()
        page.locator('[data-ui-v2="about"][data-lang="en"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="about-descriptor"]').inner_text() == en["hero"]["descriptor"]
        see(page, en["hero"]["catch"])
        see(page, en["maker"]["name"])
        data = page.locator('[data-ui-v2="about-data"]').inner_text()
        assert data == en["what"]["data"].replace("{n}", f"{n:,}") and f"more than {n:,} " in data, data
        assert page.locator('[data-ui-v2="about-stocks"]').inner_text().split("\n") == [f"{count:,}", en["figures"]["stocks"]]
        assert page.locator('[data-ui-v2="about-photo"]').get_attribute("alt") == en["maker"]["photoAlt"]
        assert page.evaluate(f"localStorage.getItem('{ABOUT_KEY}')") == "en"
        no_hscroll(page, width)
        R.collect(page)
        page.reload(wait_until="domcontentloaded")                         # 새로 고침해도 영어
        page.locator('[data-ui-v2="about"][data-lang="en"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="about-descriptor"]').inner_text() == en["hero"]["descriptor"]
        page.get_by_role("radio", name=C["about"]["langs"]["ko"]).click()
        page.locator('[data-ui-v2="about"][data-lang="ko"]').wait_for(state="visible")
        assert page.evaluate(f"localStorage.getItem('{ABOUT_KEY}')") == "ko"
    R.check(page, S, "English → 영어 머리글 · 'more than N' · 새로 고침해도 영어 → 한국어로 돌아옴", to_english)

    def back_from_direct():
        n = page.evaluate("history.length")
        page.get_by_role("button", name=C["app"]["close"]).click()        # #about 으로 바로 열었으면: 그 자리에서 #home (첫 화면)
        at(page, "home")
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
        assert page.url.endswith("#home") and page.evaluate("history.length") == n, (page.url, n)
        page.evaluate("location.hash = 'about'")                         # 주소의 # 만 바뀌어도 열려요 (예전 뱁새의 링크와 같은 길)
        about_page(page)
        page.go_back()                                                    # 휴대폰의 뒤로 버튼
        at(page, "home")
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
    R.check(page, S, "주소로 바로 연 소개 → 뒤로 → 그 자리에서 #home · # 바뀜으로 열기 · 브라우저 뒤로로 닫기", back_from_direct)
    ctx.close()
    srv.shutdown()

    # 저장소가 막힌 브라우저: 읽기도 쓰기도 안 돼요. 소개는 한국어로 열리고, 영어로 바꾸면 그 화면에서는 영어예요.
    blocked = ("(() => { Object.defineProperty(window, 'localStorage', { configurable: true, "
               "get() { throw new DOMException('blocked', 'SecurityError'); } }); })();")
    srv, ctx, page, base = R.open(build_site(files), width, init=blocked, path="/app.html?dev=1#about")

    def no_storage():
        assert page.evaluate("(() => { try { localStorage.getItem('x'); return 'open'; } catch (e) { return 'blocked'; } })()") == "blocked"
        box = about_page(page)
        assert box.get_attribute("data-lang") == "ko"
        page.get_by_role("radio", name=C["about"]["langs"]["en"]).click()
        page.locator('[data-ui-v2="about"][data-lang="en"]').wait_for(state="visible")
        see(page, en["hero"]["catch"])
        page.locator('[data-ui-v2="about-figures"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, S, "저장소가 막혀도 소개가 열리고 English 로 바뀌어요 (페이지 오류 없음)", no_storage)
    ctx.close()
    srv.shutdown()

    f = clone(files)                                                      # 멈춘 데이터 (발행 6일 전)
    for name in DATA_FILES:
        f[name]["publishedAt"] = now_kst(days_ago=6)
    srv, ctx, page, base = R.open(build_site(f), width, path="/app.html?dev=1#about")

    def stale():
        about_page(page)
        page.locator('[data-ui-v2="about-data"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="about-data"]').inner_text() == ko["what"]["data"].replace("{n}", f"{n:,}")
        assert page.locator('[data-ui-v2="about-figures"]').count() == 0, "멈춘 데이터인데 '매 거래일 데이터 갱신' 줄이 보여요"
        R.collect(page)
    R.check(page, S, "멈춘 데이터(6일 전): 숫자 줄 없음, 숫자 문단은 그대로", stale)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(files, drop=("data.json",)), width, path="/app.html?dev=1#about")

    def failed():
        about_page(page)
        see(page, ko["maker"]["title"])
        page.wait_for_timeout(600)                                        # 불러오기가 끝날 시간
        assert page.locator('[data-ui-v2="about-figures"]').count() == 0 and page.locator('[data-ui-v2="about-data"]').count() == 0
        assert page.get_by_text(ko["what"]["intro"]).is_visible() and page.get_by_text(ko["run"]["title"]).is_visible()
        images_loaded(page)
        footer_ok(page)
        page.get_by_role("button", name=C["app"]["close"]).click()        # 뒤의 화면은 불러오기 실패 문구
        see(page, LOAD_FAIL)
        R.collect(page)
    R.check(page, S, "data.json 없음: 숫자 줄 · 숫자 문단 없이 나머지는 그대로, 뒤로 가면 불러오기 실패 문구", failed)
    ctx.close()
    srv.shutdown()


# ── 아이폰: 사파리에서 기록 내보내기 → 홈 화면 앱에서 기록 불러오기 (v18.4.1, Jack 2026-11-04) ──
# 홈 화면 앱처럼 열기: navigator.standalone(iOS 사파리만 있는 값)과 display-mode: standalone 을 참으로 흉내 내요
# (v19.0c: src/v2 store.js iphoneSafari 가 이 둘을 읽어 홈 화면 앱 안에서는 홈 화면 안내를 숨겨요).
STANDALONE_INIT = """(() => {
  try { Object.defineProperty(Navigator.prototype, 'standalone', { get: () => true, configurable: true }); } catch (e) {}
  const mm = window.matchMedia ? window.matchMedia.bind(window) : null;
  window.matchMedia = (q) => (/display-mode:\\s*standalone/.test(String(q))
    ? { matches: true, media: String(q), onchange: null, addListener() {}, removeListener() {}, addEventListener() {},
        removeEventListener() {}, dispatchEvent() { return false; } }
    : mm(q));
})();"""
OTHER_KEYS = """() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i);
  if (k !== 'baepsae2.v1') o[k] = localStorage.getItem(k); } return o; }"""
STORED = "JSON.parse(localStorage.getItem('baepsae2.v1') || 'null')"
# 받은 파일의 주소(Blob URL)를 언제 지우는지 기록해요: 바로(1초 안에) 지우면 iOS 사파리가 받다가 실패할 수 있어요 (v18.4.1, 60초 뒤)
REVOKE_SPY = """() => { if (window.__revoked) return; window.__revoked = []; const orig = URL.revokeObjectURL.bind(URL);
  URL.revokeObjectURL = (u) => { window.__revoked.push(u); return orig(u); }; }"""


def standalone_ua(ua):
    """홈 화면에 추가한 앱의 사용자 에이전트: 사파리와 같은데 끝의 'Version/…' · 'Safari/…' 가 없어요."""
    return re.sub(r" Safari/\S+$", "", re.sub(r" Version/\S+", "", ua))


def scene_iphone_records(R, files, device):
    """아이폰: 사파리에서 쓴 기록을 홈 화면 앱으로 옮기는 길 (Jack 2026-11-04: 아이폰 계획이 이 길에 기대요).
    iOS 에서 홈 화면에 추가한 앱은 사파리와 저장소를 같이 쓰지 않고 따로 써요. 그래서 옮기는 길은 '기록 내보내기 → 파일 → 기록 불러오기' 하나예요.

    여기에는 진짜 사파리(WebKit)가 설치돼 있지 않아요. 그래서 크롬(Chromium)에 Playwright 의 'iPhone 13' 설명(사용자 에이전트 ·
    390×664 화면 · 터치)을 입혀서 봐요.
      문맥 1 (사파리)    덱 짜기(배당 생활비) → 샀어요(날짜 · 한국 종목 하나와 미국 종목 하나의 수량 · 가격을 바꿔서) → 내 덱 →
                         기록 내보내기 → 받은 파일. 앱(store.js downloadRecords)은 사파리 같은 브라우저에서도 다른 길이 없어요:
                         똑같이 Blob 을 만들어 <a download> 를 눌러요. 다른 점은 '사파리는 7일…' 안내 한 줄뿐이라, 그 줄이 보이는지
                         (= 앱이 사파리로 알아봤는지) 확인하고, 받은 파일이 저장된 기록과 똑같은지, 파일 주소를 1.5초 안에 지우지
                         않는지(일찍 지우면 iOS 사파리가 받다가 실패할 수 있어요) 봐요.
      문맥 2 (새 저장소) 저장소가 빈 새 문맥 = 홈 화면 앱처럼 사파리와 저장소가 따로인 곳. 사용자 에이전트는 홈 화면 앱처럼 'Safari/…'
                         없는 것으로, navigator.standalone 과 display-mode: standalone 도 참으로 흉내 내요. v19.0c 부터 src/v2 는 이 둘로
                         아이폰 홈 화면 안내를 숨겨요(사파리에서만): 사파리 문맥에는 안내 자리가 있고(첫 방문 홈 · 포트폴리오) 여기에는 없어요.
                         기록 불러오기 → 같은 덱 · 종목 · 산 기록(수량 · 가격 · 날짜 · 미국 종목의 환율) · 규칙이 저장되고, 내 덱과
                         오늘 화면의 글이 문맥 1 과 똑같아요 · 다른 저장 값은 그대로 · 새로 고침해도 남아요 · 같은 파일을 두 번 불러도
                         덱이 늘지 않아요 · 미리 보기에서 만든 기록 파일은 '미리 보기에서 만든 기록은…' 으로 막혀요.
    이 시험이 보여 주지 못하는 것 (실제 아이폰에서만 볼 수 있어요): iOS 사파리가 <a download> 로 받은 파일을 '파일' 앱에 저장하는지,
    홈 화면 앱의 파일 고르기 창에서 그 파일을 고를 수 있는지, 홈 화면 모드에서의 동작, WebKit 의 File.text() · 저장소 동작."""
    tmp = tempfile.mkdtemp(prefix="baepsae-records-")       # 받은 파일 · 시험 파일 · 사이트를 한 폴더에 두고 끝나면 지워요
    try:
        _iphone_records(R, files, device, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _iphone_records(R, files, device, tmp):
    S = "아이폰 기록 옮기기"
    dev = {k: v for k, v in device.items() if k != "default_browser_type"}
    width = dev["viewport"]["width"]
    site = os.path.join(tmp, "site")
    shutil.move(build_site(files), site)
    by = {x["t"]: x for x in files["data.json"]["stocks"]}
    day = (dt.date.fromisoformat(files["data.json"]["pxDate"]) - dt.timedelta(days=2)).isoformat()   # 오늘이 아닌 산 날
    keep = {}

    def main_text(page):
        """화면의 글. 아이폰 홈 화면 안내(사파리에서만, v19.0c)는 두 문맥에서 일부러 달라서 빼고 견줘요."""
        return page.evaluate("""() => { const hs = [...document.querySelectorAll('main [data-ui-v2="ios-hint"]')];
            const old = hs.map((h) => h.style.display); hs.forEach((h) => { h.style.display = 'none'; });
            const t = document.querySelector('main').innerText; hs.forEach((h, i) => { h.style.display = old[i]; }); return t; }""")

    def hint_kinds(page):
        return page.locator('[data-ui-v2="ios-hint"]').evaluate_all("(els) => els.map((e) => e.dataset.kind)")

    def open_deck_tab(page):
        tab(page, C["app"]["tabs"]["portfolio"])
        see(page, C["store"]["export"])

    def open_today_tab(page):
        tab(page, C["app"]["tabs"]["home"])
        page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")

    srv, ctx, page, _ = R.open(site, width, accept_downloads=True, device=dev)

    def safari():
        assert "iPhone" in page.evaluate("navigator.userAgent") and page.evaluate("navigator.standalone") is None
        wait_ready(page)
        at(page, "home")                                              # 저장한 포트폴리오가 없으면 첫 방문 홈
        assert hint_kinds(page) == ["first"], hint_kinds(page)        # v19.0c: 아이폰 사파리 · 포트폴리오 전 → 홈 화면 안내 자리
        start_build(page)
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        click_next(page)
        see(page, C["plan"]["stocks"])
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        sheet = page.locator('[data-ui-v2="record-form"]')
        sheet.locator('input[type="date"]').fill(day)
        tickers = [r.get_attribute("data-record") for r in sheet.locator("[data-record]").all()]
        kr = next(t for t in tickers if by[t].get("cls") != "us")
        us = next((t for t in tickers if by[t].get("cls") == "us"), None)
        assert us, f"미국 종목이 계획에 없어요: {tickers}"
        want = {}
        for t, price in ((kr, str(int(by[kr]["price"] * 0.98))), (us, f"{by[us]['price'] * 0.97:.2f}")):
            box = sheet.locator(f'[data-record="{t}"] input')
            planned = int(box.nth(0).get_attribute("placeholder").replace(",", ""))
            box.nth(0).fill(str(planned + 1))                         # 계획보다 한 주 더
            box.nth(1).fill(price)                                    # 계획과 다른 가격
            want[t] = (planned + 1, float(price))
        page.get_by_role("button", name=C["plan"]["save"]).click()
        see(page, C["plan"]["done"])
        page.get_by_role("button", name=DONE_LINK).click()
        at(page, "home")
        stored = page.evaluate(STORED)
        ps = {p["t"]: p for p in stored["decks"][0]["purchases"]}
        assert len(stored["decks"]) == 1 and len(ps) == len(tickers) and all(p["date"] == day for p in ps.values()), stored
        assert all((ps[t]["qty"], ps[t]["price"]) == q for t, q in want.items()), (want, ps)
        assert ps[us]["ccy"] == "USD" and ps[us]["fx"] == files["data.json"]["fx"] and ps[kr]["ccy"] == "KRW", (ps[us], ps[kr])
        assert all(h.get("rules") for h in stored["decks"][0]["holdings"]), "규칙이 저장되지 않았어요"
        open_today_tab(page)
        keep["today"] = main_text(page)
        open_deck_tab(page)
        page.locator("[data-holding][data-status]").first.wait_for(state="visible")
        page.locator('[data-ui-v2="deck-value"]').wait_for(state="visible")
        see(page, C["store"]["safari"])                               # 앱이 사파리 같은 브라우저로 알아봤어요
        assert hint_kinds(page) == ["move"], hint_kinds(page)         # 포트폴리오가 있으면: 내보내기 → 불러오기 안내 자리
        keep["deck"] = main_text(page)
        page.evaluate(REVOKE_SPY)
        with page.expect_download() as dl:
            page.get_by_role("button", name=C["store"]["export"]).click()
        name, url = dl.value.suggested_filename, dl.value.url
        assert url.startswith("blob:"), url
        keep["path"] = os.path.join(tmp, name)                        # 문맥을 닫으면 받은 파일이 지워져서 옮겨 둬요
        dl.value.save_as(keep["path"])
        page.wait_for_timeout(1500)
        assert url not in page.evaluate("window.__revoked"), "받은 파일의 주소를 너무 일찍 지웠어요 (iOS 사파리에서 받기가 실패할 수 있어요)"
        with open(keep["path"], encoding="utf-8") as fh:
            exported = json.load(fh)
        assert re.fullmatch(r"baepsae-records-\d{4}-\d{2}-\d{2}\.json", name), name
        assert exported == {"v": 1, "decks": stored["decks"]}, "받은 파일이 저장된 기록과 달라요"
        keep["file"] = exported
        R.collect(page)
    R.check(page, S, "사파리(아이폰 UA): 샀어요(날짜 · 수량 · 가격 · 미국 종목 환율) → 내 덱 → 기록 내보내기 → 파일 = 저장된 기록 (주소는 늦게 지움)", safari)
    ctx.close()
    srv.shutdown()

    home = {**dev, "user_agent": standalone_ua(dev["user_agent"])}
    srv, ctx, page, _ = R.open(site, width, init=STANDALONE_INIT, device=home)
    imp = page.locator('[data-ui-v2="import-file"]')

    def home_screen():
        assert "path" in keep, "앞 단계에서 파일을 받지 못했어요"
        ua = page.evaluate("navigator.userAgent")
        assert "iPhone" in ua and "Safari/" not in ua, ua
        assert page.evaluate("navigator.standalone === true && matchMedia('(display-mode: standalone)').matches"), "홈 화면 앱 흉내가 안 돼요"
        wait_ready(page)
        assert page.evaluate(STORED) is None, "새 문맥인데 기록이 있어요"
        at(page, "home")                                              # 빈 저장소: 첫 방문 홈
        assert hint_kinds(page) == [], "홈 화면 앱 안에서 홈 화면 안내가 보여요"
        open_deck_tab(page)
        assert page.locator("[data-deck-id]").count() == 0
        others = page.evaluate(OTHER_KEYS)
        imp.set_input_files(keep["path"])
        page.locator("[data-deck-id]").first.wait_for(state="visible")
        assert page.locator('[data-ui-v2="import-bad"]').count() == 0
        assert page.evaluate(STORED) == keep["file"], "불러온 기록이 파일과 달라요 (덱 · 종목 · 산 기록 · 규칙)"
        assert page.evaluate(OTHER_KEYS) == others, "기록 말고 다른 저장 값이 바뀌었어요"
        page.locator("[data-holding][data-status]").first.wait_for(state="visible")
        page.locator('[data-ui-v2="deck-value"]').wait_for(state="visible")
        assert main_text(page) == keep["deck"], "포트폴리오 화면이 사파리에서 본 것과 달라요"
        assert hint_kinds(page) == [], "홈 화면 앱 안에서 홈 화면 안내가 보여요"
        open_today_tab(page)
        assert main_text(page) == keep["today"], "오늘 화면이 사파리에서 본 것과 달라요"
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")         # 저장한 덱이 있으면 오늘부터
        assert main_text(page) == keep["today"] and page.evaluate(STORED) == keep["file"], "새로 고침 뒤에 기록이 달라요"
        R.collect(page)
    R.check(page, S, "새 저장소(홈 화면 앱처럼 따로): 기록 불러오기 → 같은 덱 · 종목 · 산 기록 · 규칙, 내 덱 · 오늘 화면도 같음", home_screen)

    def twice():
        open_deck_tab(page)
        imp.set_input_files(keep["path"])
        page.wait_for_timeout(1000)                                   # 불러오기는 바로 끝나요 (바뀌는 게 없어야 해서 기다려서 봐요)
        assert page.locator("[data-deck-id]").count() == 1 and page.evaluate(STORED) == keep["file"], "같은 파일을 두 번 불러 덱이 늘었어요"
        assert page.locator('[data-ui-v2="import-bad"]').count() == 0
    R.check(page, S, "같은 파일을 한 번 더 불러와도 덱이 늘지 않아요", twice)

    def preview_file():
        prev = os.path.join(tmp, "baepsae-preview-records.json")
        with open(prev, "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "preview": True, "decks": keep["file"]["decks"]}, fh, ensure_ascii=False)   # store.js exportText(…, true) 모양
        imp.set_input_files(prev)
        box = page.locator('[data-ui-v2="import-bad"]')
        box.wait_for(state="visible")
        assert box.get_attribute("data-why") == "preview" and box.inner_text() == C["store"]["otherKind"], box.inner_text()
        assert page.locator("[data-deck-id]").count() == 1 and page.evaluate(STORED) == keep["file"], "막힌 파일이 기록을 바꿨어요"
        R.collect(page)
    R.check(page, S, f"미리 보기에서 만든 기록 파일 → '{C['store']['otherKind']}' (기록은 그대로)", preview_file)
    ctx.close()
    srv.shutdown()


# ── v19.0c: 네 탭의 주소 · 휴대폰 뒤로 · 시장 · 종목 · 빠진 종목 · 아이폰 안내 ──
def scene_routes(R, files, width):
    """주소로 바로 열기(#home #portfolio #stocks #market) · 모르는 주소와 주소 없음은 그 자리에서 #home · #home/why 는 대상이 없으면 #home ·
    #portfolio/build 로 바로 열면 뒤로가 그 자리에서 #portfolio · 고른 탭 표시."""
    S = f"주소 {width}"
    srv, ctx, page, base = R.open(build_site(files), width, path="/app.html?dev=1#market")

    def deep():
        for h, r, cur in (("#market", "market", "market"), ("#stocks", "stocks", "stocks"), ("#portfolio", "portfolio", "portfolio"), ("#home", "home", "home")):
            page.goto("about:blank")                                     # 새 문서로 (주소의 # 만 바꾸면 같은 페이지 안의 이동이에요)
            page.goto(base + "/app.html?dev=1" + h, wait_until="domcontentloaded")
            wait_ready(page)
            at(page, r)
            assert page.url.endswith(h), (h, page.url)
            on = page.locator('nav[data-ui="bottom-tab-bar"] button[aria-current="page"]').inner_text().strip()
            assert on == TABS[cur], (h, on)
            R.collect(page)
        for h in ("#today", "#deck", "#search", "#stocks/x", "#home/build"):     # 예전 탭 이름 · 모르는 주소 → 그 자리에서 #home
            page.goto("about:blank")
            page.goto(base + "/app.html?dev=1" + h, wait_until="domcontentloaded")
            at(page, "home")
            page.wait_for_function("() => location.hash === '#home'")
            assert page.evaluate("history.state && history.state.v2") == 0, h
        page.goto("about:blank")
        page.goto(base + "/app.html?dev=1#home/why", wait_until="domcontentloaded")   # 왜 움직였나는 대상이 있어야 해요
        page.wait_for_function("() => location.hash === '#home'")
        at(page, "home")
    R.check(page, S, "주소로 바로 열기 네 탭 · 예전 이름과 모르는 주소는 그 자리에서 #home · #home/why 만 열면 #home", deep)

    def build_direct():
        page.goto("about:blank")
        page.goto(base + "/app.html?dev=1#portfolio/build", wait_until="domcontentloaded")
        wait_ready(page)
        at(page, "portfolio/build")
        see(page, C["build"]["s0"]["title"])
        n = page.evaluate("history.length")
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=BACK_BUILD).click()               # 앞에 이 페이지의 기록이 없으면: 그 자리에서 #portfolio
        at(page, "portfolio")
        assert page.url.endswith("#portfolio") and page.evaluate("history.length") == n, page.url
        R.collect(page)
    R.check(page, S, "#portfolio/build 로 바로 열기 → 뒤로 → 그 자리에서 포트폴리오", build_direct)
    ctx.close()
    srv.shutdown()


def tile(page, i):
    t = page.locator(f'[data-ui-v2="market-tile"][data-id="{i}"]')
    return {"value": t.locator('[data-ui-v2="tile-value"]').inner_text(), "change": t.locator('[data-ui-v2="tile-change"]').all_inner_texts(),
            "date": t.locator('[data-ui-v2="tile-date"]').all_inner_texts(), "name": t.locator("div").first.inner_text()}


def scene_market(R, files, width):
    """시장 (Jack 승인: 네 칸 + 예전 뱁새로 가는 두 버튼): 코스피 · S&P 500 은 수준과 변화, 국고채 3년 · 원/달러는 수준만(데이터에 하루
    변화가 없어서 지어내지 않아요) · 칸마다 자기 날짜 · 값이 없으면 '–' · macro.json 을 못 읽으면 실패 문구."""
    S = f"시장 {width}"
    f = clone(files)
    hist = f["macro.json"]["idxHist"]
    k, sp = hist["KOSPI"]["rows"], hist["SP500"]["rows"]
    srv, ctx, page, base = R.open(build_site(f), width, path="/app.html?dev=1#market")

    def tiles():
        wait_ready(page)
        at(page, "market")
        assert page.locator("main h2").first.inner_text() == TABS["market"]
        ids = page.locator('[data-ui-v2="market-tile"]').evaluate_all("(els) => els.map((e) => e.dataset.id)")
        assert ids == ["kospi", "sp500", "kr3y", "usdkrw"], ids
        pct = lambda a, b: ("−" if b < a else "+") + f"{abs((b / a - 1) * 100):.1f}%"
        ko = tile(page, "kospi")
        assert ko["name"] == C["market"]["kospi"] and ko["value"] == f"{k[-1][1]:,.2f}" and ko["change"] == [pct(k[-2][1], k[-1][1])], ko
        assert ko["date"] == ["10월 30일 기준"], ko
        s5 = tile(page, "sp500")
        assert s5["name"] == "S&P 500" and s5["value"] == f"{sp[-1][1]:,.2f}" and s5["change"] == [pct(sp[-2][1], sp[-1][1])], s5
        cv = f["macro.json"]["curve"]
        r3 = tile(page, "kr3y")
        assert r3["name"] == C["market"]["kr3y"] and r3["value"] == f"{cv['now'][cv['tenors'].index(3)]:.2f}%" and r3["change"] == [], r3   # 수준만
        fx = tile(page, "usdkrw")
        assert fx["name"] == C["market"]["usdkrw"] and fx["value"] == f"{f['data.json']['fx']:,.1f}원" and fx["change"] == [], fx      # 수준만
        assert r3["date"] == ["10월 30일 기준"] and fx["date"] == ["10월 30일 기준"], (r3, fx)
        links = page.locator('[data-ui-v2="old-screen"]')
        got = [(links.nth(i).inner_text().strip(), links.nth(i).get_attribute("href")) for i in range(links.count())]
        assert got == [(C["market"]["macro"], "./baepsae.html#macro"), (C["market"]["disc"], "./baepsae.html#disc")], got
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "네 칸: 코스피 · S&P 500 수준과 변화 · 국고채 3년 · 원/달러 수준만 · 칸마다 날짜 · 예전 뱁새 두 버튼", tiles)

    def into_old_app():
        with page.expect_navigation():
            page.locator('[data-ui-v2="old-screen"][data-id="macro"]').click()
        page.wait_for_function("() => location.pathname.endsWith('/baepsae.html') && location.hash === ''")   # 예전 뱁새가 읽고 지워요
        page.go_back()
        at(page, "market")
        assert page.url.endswith("/app.html?dev=1#market"), page.url
    R.check(page, S, "금리·원자재 → 예전 뱁새(#macro, 읽고 지움) → 뒤로 → 시장", into_old_app)
    ctx.close()
    srv.shutdown()

    g = clone(files)                                                      # 국고채 날짜 없음 · 코스피 종가 하나 · 원/달러 날짜 없음
    g["macro.json"]["curve"]["date"] = None
    g["macro.json"]["idxHist"]["KOSPI"]["rows"] = k[-1:]
    g["data.json"].pop("fxDate", None)
    srv, ctx, page, base = R.open(build_site(g), width, path="/app.html?dev=1#market")

    def gaps():
        wait_ready(page)
        at(page, "market")
        ko, r3, fx = tile(page, "kospi"), tile(page, "kr3y"), tile(page, "usdkrw")
        assert ko["value"] == f"{k[-1][1]:,.2f}" and ko["change"] == [] and ko["date"] == ["10월 30일 기준"], ko   # 종가 하나: 변화 없음
        assert r3["value"] == "–" and r3["date"] == [] and fx["value"] == "–" and fx["date"] == [], (r3, fx)       # 날짜 없는 값은 보이지 않아요
        R.collect(page)
    R.check(page, S, "값을 날짜에 묶을 수 없으면 '–' · 종가가 하나면 변화 없음", gaps)
    ctx.close()
    srv.shutdown()

    saved = {"v": 1, "decks": [_deck("dm", "시장 포트폴리오", [(*SAMSUNG, 1.0, [], 1, 225000)])]}
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(saved, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, base = R.open(build_site(files, drop=("macro.json",)), width, init=init, path="/app.html?dev=1#market")

    def no_macro():
        wait_ready(page)
        at(page, "market")
        fail = page.locator('[data-ui-v2="load-fail"]')
        fail.wait_for(state="visible")
        assert fail.inner_text().strip() == LOAD_FAIL and fail.get_attribute("data-picture") == "0"      # 숫자(원/달러)가 있는 화면: 그림 없이 문구만
        for i in ("kospi", "sp500", "kr3y"):
            x = tile(page, i)
            assert x["value"] == "–" and x["change"] == [] and x["date"] == [], (i, x)
        assert tile(page, "usdkrw")["value"] == f"{files['data.json']['fx']:,.1f}원"                     # 원/달러는 data.json 에서
        R.collect(page)
        tab(page, TABS["home"])                                           # 홈의 시장 한눈에: 같은 실패 문구, '–' 칸 없음
        at(page, "home")
        glance = page.locator('[data-ui-v2="market-glance"]')
        glance.wait_for(state="visible")
        gf = glance.locator('[data-ui-v2="load-fail"]')
        assert gf.inner_text().strip() == LOAD_FAIL and gf.get_attribute("data-picture") == "0", glance.inner_text()
        assert glance.locator('[data-ui-v2="market-tile"]').count() == 0 and "–" not in glance.inner_text(), glance.inner_text()
        R.collect(page)
    R.check(page, S, "macro.json 을 못 읽으면: 시장은 실패 문구 · 세 칸 '–' · 원/달러 그대로, 홈의 시장 한눈에는 같은 실패 문구만", no_macro)
    ctx.close()
    srv.shutdown()


def scene_stocks(R, files, width):
    """종목: 찾기 · 최근 본 종목 · 거래대금 상위 종목(한국 · 미국 따로, 날짜) · 한국 회사 → 예전 뱁새의 기업분석(#corp=코드) ·
    미국 종목 → '기업분석은 한국 상장 기업만 볼 수 있어요.' (그 자리에서, 다른 곳으로 가지 않아요)."""
    S = f"종목 {width}"
    srv, ctx, page, base = R.open(build_site(files), width, path="/app.html?dev=1#stocks")

    def lists():
        wait_ready(page)
        at(page, "stocks")
        assert page.locator("main h2").first.inner_text() == TABS["stocks"]
        box = page.locator('[data-ui-v2="stock-search"] input')
        assert box.get_attribute("aria-label") == (C["stocks"]["search"] or TABS["stocks"])
        pop = page.locator('[data-ui-v2="popular"]')
        assert pop.locator("h3").inner_text() == C["home"]["popular"] and pop.locator('svg[data-ph="chart-bar"]').count() == 1
        assert page.locator('svg[data-ph="fire"]').count() == 0 and "많이 찾는" not in page.locator("body").inner_text()
        kr = pop.locator('[data-ui-v2="popular-list"][data-market="kr"]')
        us = pop.locator('[data-ui-v2="popular-list"][data-market="us"]')
        assert kr.locator("span").first.inner_text() == C["pick"]["market"]["kr"] and us.locator("span").first.inner_text() == C["pick"]["market"]["us"]
        assert kr.locator('[data-ui-v2="list-date"]').inner_text() == "10월 30일 기준" and us.locator('[data-ui-v2="list-date"]').inner_text() == "10월 30일 기준"
        krs = kr.locator('[data-ui-v2="stock-row"]').evaluate_all("(els) => els.map((e) => e.dataset.t)")
        uss = us.locator('[data-ui-v2="stock-row"]').evaluate_all("(els) => els.map((e) => e.dataset.t)")
        by = {x["t"]: x for x in files["data.json"]["stocks"]}
        want_kr = [t for t in files["data.json"]["popular"] if t in by and by[t]["cls"] == "kr" and not by[t].get("etf")][:5]
        want_us = [t for t in files["data.json"]["popular"] if t in by and by[t]["cls"] == "us" and not by[t].get("etf")][:5]
        assert krs == want_kr and uss == want_us, (krs, uss)                # 거래대금 순서 그대로, 시장마다 따로
        assert re.search(r"[+−]\d+\.\d%", kr.inner_text()), kr.inner_text()  # 종목 탭은 오늘 등락을 보여요 (뱁이 없음)
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "거래대금 상위 종목: 한국 · 미국 따로 · 순서 그대로 · 날짜 · 막대그래프 아이콘 (불 아이콘 · '많이 찾는' 없음)", lists)

    def search():
        box = page.locator('[data-ui-v2="stock-search"] input')
        box.fill("삼성")
        rows = page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"]')
        rows.first.wait_for(state="visible")
        names = rows.all_inner_texts()
        assert len(names) >= 4 and all("삼성" in n for n in names), names
        box.fill("Apple")                                                 # 한국 · 미국 종가 날짜가 같으면 미국 날짜 줄 없음
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-cls="us"]').first.wait_for(state="visible")
        assert page.locator('[data-ui-v2="us-close"]').count() == 0
        assert page.locator('[data-ui-v2="popular"]').count() == 0          # 찾는 동안은 결과만
        box.fill("zzzz없는회사")
        nr = page.locator('[data-ui-v2="no-result"]')
        nr.wait_for(state="attached")
        assert (nr.inner_text() == C["stocks"]["noResult"]) if C["stocks"]["noResult"] else nr.get_attribute("data-pending") == "1"
        box.fill("")
        page.locator('[data-ui-v2="popular"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, S, "찾기: '삼성' → 이름에 삼성이 든 종목 · 없는 이름 → 결과 없음 자리", search)

    def us_line():
        us = page.locator('[data-ui-v2="popular-list"][data-market="us"] [data-ui-v2="stock-row"]').first
        t = us.get_attribute("data-t")
        us.locator("button").click()
        note = us.locator('[data-ui-v2="kr-only"]')
        note.wait_for(state="visible")
        assert note.inner_text().strip() == C["stocks"]["krOnly"] == "기업분석은 한국 상장 기업만 볼 수 있어요.", note.inner_text()
        assert page.url.endswith("#stocks") and us.locator("a").count() == 0, page.url    # 다른 곳으로 가지 않아요
        us.locator("button").click()
        note.wait_for(state="detached")
        R.collect(page)
        keep["us"] = t
    keep = {}
    R.check(page, S, "미국 종목을 누르면 그 자리에 '기업분석은 한국 상장 기업만 볼 수 있어요.' (다시 누르면 닫혀요)", us_line)

    def kr_corp():
        row = page.locator('[data-ui-v2="popular-list"][data-market="kr"] [data-ui-v2="stock-row"]').first
        t = row.get_attribute("data-t")
        link = row.locator("a")
        assert link.get_attribute("href") == f"./baepsae.html#corp={t}", link.get_attribute("href")
        with page.expect_navigation():
            link.click()
        page.wait_for_function("() => location.pathname.endsWith('/baepsae.html') && location.hash === ''")   # 예전 뱁새가 읽고 지워요
        page.go_back()
        at(page, "stocks")
        rec = page.locator('[data-ui-v2="recent"] [data-ui-v2="stock-row"]')
        rec.first.wait_for(state="visible")
        got = rec.evaluate_all("(els) => els.map((e) => e.dataset.t)")
        assert got == [t, keep.get("us")], got                             # 최근 본 종목: 방금 누른 것부터
        if C["stocks"]["recent"]:
            assert page.locator('[data-ui-v2="recent"] h3').inner_text() == C["stocks"]["recent"]
        else:
            assert page.locator('[data-ui-v2="recent"] h3').count() == 0   # 제목은 승인 대기
        R.collect(page)
    R.check(page, S, "한국 회사 → 예전 뱁새 기업분석(#corp=코드, 읽고 지움) → 뒤로 → 종목 · 최근 본 종목에 남아요", kr_corp)
    ctx.close()
    srv.shutdown()


def missing_store(files):
    by = {x["t"]: x for x in files["data.json"]["stocks"]}
    assert "OLDX" not in by                                               # 오늘 데이터에 없는 미국 종목 (지어낸 티커)
    sam, hy = round(by["005930"]["price"]), round(by["000660"]["price"])
    d = _deck("dgone", "빠진 종목 포트폴리오", [(*SAMSUNG, 0.4, [], 2, sam), ("000660", "SK하이닉스", 0.4, [], 1, hy)])
    d["holdings"].append({**_holding("OLDX", "Strategy Inc", 0.2, []), "cls": "us"})
    d["purchases"].append({"t": "OLDX", "date": "2026-10-01", "qty": 10, "price": 150.0, "ccy": "USD", "fx": 1300.0})
    keep = _deck("dkeep", "그대로 포트폴리오", [(*SAMSUNG, 1.0, [], 1, sam)])
    return {"v": 1, "decks": [d, keep]}, 2 * by["005930"]["price"] + by["000660"]["price"]


def man(won):
    return f"{round(won / 10000):,}만원"


def scene_missing(R, files, width):
    """저장한 종목이 오늘 데이터에 없을 때 (Jack 의 설계): 그 줄은 남고(확인 필요 · 포트폴리오에서 빼기), 다른 종목은 자기 점검 그대로,
    합계는 그 종목을 빼고 '오늘 데이터에 없는 종목 1개(OLDX 195만원)는 빼고 계산했어요.', 비중 · 추가로 넣을 돈은 멈춤
    ('빠진 종목이 다시 들어오거나 직접 뺄 때까지 비중은 점검하지 않아요.'). 저절로 지우지 않고, 누를 때만 그 종목 하나를 빼요."""
    S = f"빠진 종목 {width}"
    store, value = missing_store(files)
    line = fillp(C["missing"]["line"], n=1, names="OLDX 195만원")             # 10주 × $150 × 1,300원 = 195만원
    assert line == "오늘 데이터에 없는 종목 1개(OLDX 195만원)는 빼고 계산했어요."
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)
    deck = lambda i: page.locator(f'[data-deck-id="{i}"]')

    def portfolio():
        wait_ready(page)
        tab(page, TABS["portfolio"])
        d = deck("dgone")
        d.locator('[data-holding="OLDX"]').wait_for(state="visible")
        gone = d.locator('[data-holding="OLDX"]')
        assert gone.get_attribute("data-status") == "check" and gone.locator('[data-ui="status-chip"]').all_inner_texts() == [C["daily"]["check"]]
        assert "가격 자료를 받지 못해 확인이 필요해요" in gone.inner_text()
        assert gone.locator('[data-ui-v2="missing-remove"] button').inner_text() == C["missing"]["remove"] == "포트폴리오에서 빼기"
        assert d.locator('[data-ui-v2="missing-line"]').inner_text() == line
        assert d.locator('[data-ui-v2="weights-paused"]').inner_text() == C["missing"]["paused"]
        for sel in ('[data-ui-v2="weight"]', '[data-ui-v2="add-money"]', '[data-ui-v2="weight-legend"]'):
            assert d.locator(sel).count() == 0, sel                         # 비중 · 추가로 넣을 돈은 멈춤
        for t in ("005930", "000660"):                                      # 다른 종목: 자기 점검 그대로 (비중 때문에 확인 필요가 되지 않아요)
            r = d.locator(f'[data-holding="{t}"]')
            assert r.get_attribute("data-status") == "none" and r.locator('[data-ui-v2="status-line"]').count() == 0, t
            assert r.locator('[data-ui-v2="missing-remove"]').count() == 0, t
        assert d.locator('[data-ui-v2="deck-value"]').inner_text() == man(value), d.locator('[data-ui-v2="deck-value"]').inner_text()  # 합계는 빼고
        k = deck("dkeep")                                                   # 다른 포트폴리오는 그대로
        assert k.locator('[data-ui-v2="missing-line"], [data-ui-v2="weights-paused"]').count() == 0 and k.locator('[data-ui-v2="weight"]').count() == 1
        no_hscroll(page, width)
        R.collect(page)
        page.reload(wait_until="domcontentloaded")                         # 저절로 지우지 않아요
        wait_ready(page)
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        assert [h["t"] for h in stored["decks"][0]["holdings"]] == ["005930", "000660", "OLDX"] and len(stored["decks"][0]["purchases"]) == 3, stored
    R.check(page, S, "포트폴리오: 빠진 종목 줄(확인 필요 · 포트폴리오에서 빼기) · 합계는 빼고 그 문장 · 비중 멈춤 문장 · 다른 종목 · 다른 포트폴리오는 그대로", portfolio)

    def home():
        tab(page, TABS["home"])
        at(page, "home")
        strip = page.locator('[data-ui-v2="deck-strip"][data-deck-id="dgone"]')
        strip.wait_for(state="visible")
        assert strip.locator('[data-ui-v2="missing-line"]').inner_text() == line
        assert page.locator('[data-ui-v2="deck-strip"][data-deck-id="dkeep"] [data-ui-v2="missing-line"]').count() == 0
        assert man(value) in strip.inner_text(), strip.inner_text()
        hero = page.locator('[data-ui-v2="today-hero"]')
        assert hero.get_attribute("data-state") == "todo" and "OLDX:check" in hero.locator('[data-ui-v2="todo-item"]').evaluate_all(
            "els => els.map(e => e.dataset.t + ':' + e.dataset.status)")
        R.collect(page)
    R.check(page, S, "홈: 그 포트폴리오 띠에 같은 문장 · 평가 금액은 빼고 · 오늘 확인할 일에 그 종목(확인 필요)", home)

    def remove():
        tab(page, TABS["portfolio"])
        d = deck("dgone")
        d.locator('[data-holding="OLDX"] [data-ui-v2="missing-remove"] button').click()
        d.locator('[data-holding="OLDX"]').wait_for(state="detached")
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        a, b = stored["decks"]
        assert [h["t"] for h in a["holdings"]] == ["005930", "000660"] and [p["t"] for p in a["purchases"]] == ["005930", "000660"], a
        assert b == store["decks"][1], "다른 포트폴리오가 바뀌었어요"
        assert d.locator('[data-ui-v2="missing-line"], [data-ui-v2="weights-paused"]').count() == 0
        assert d.locator('[data-ui-v2="weight"]').count() == 2                # 비중 점검이 다시 돌아요
        R.collect(page)
    R.check(page, S, "포트폴리오에서 빼기 → 그 종목 하나만 저장본에서 빠지고 비중 점검이 다시 돌아요", remove)
    ctx.close()
    srv.shutdown()


def scene_no_holding(R, files, width):
    """저장한 포트폴리오에 산 종목이 하나도 없으면: 홈에 판정 없이(할 일 없음도 아님) 포트폴리오 만들기로 가는 길만 (첫 방문 머리글도 아님)."""
    store = {"v": 1, "decks": [_deck("dnone", "산 것 없는 포트폴리오", [(*SAMSUNG, 1.0, [], 0)])]}
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)

    def run():
        wait_ready(page)
        at(page, "home")
        empty = page.locator('[data-ui-v2="today-empty"]')
        empty.wait_for(state="visible")
        assert empty.inner_text().strip() == C["build"]["title"]
        assert page.locator('[data-ui-v2="today-hero"], [data-ui-v2="home-hero"], [data-ui-v2="deck-strip"]').count() == 0
        assert page.get_by_text("할 일").count() == 0, "점검한 종목이 없는데 '할 일'이 보여요"
        page.locator('[data-ui-v2="market-glance"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, f"산 종목 없음 {width}", "저장한 포트폴리오에 산 종목이 없으면 홈은 판정 없이 '포트폴리오 만들기'만 (첫 방문 머리글 아님)", run)
    ctx.close()
    srv.shutdown()


def scene_hint(R, files, devices):
    """아이폰 홈 화면 안내는 아이폰 사파리에서만 (문구는 승인 대기: 그동안은 숨은 자리 표시). 안드로이드 · 홈 화면 앱 안에서는 없어요.
    첫 방문(포트폴리오 전)은 홈과 빈 포트폴리오, 포트폴리오가 있으면 포트폴리오의 기록 칸."""
    store, _ = missing_store(files)
    for name, dev, saved, want in (("아이폰 사파리 · 첫 방문", devices["iPhone 13"], None, {"home": ["first"], "portfolio": ["first"]}),
                                    ("아이폰 사파리 · 포트폴리오 있음", devices["iPhone 13"], store, {"home": [], "portfolio": ["move"]}),
                                    ("아이폰 홈 화면 앱 · 포트폴리오 있음", {**devices["iPhone 13"], "user_agent": standalone_ua(devices["iPhone 13"]["user_agent"])}, store,
                                     {"home": [], "portfolio": []}),
                                    ("안드로이드 크롬 · 첫 방문", devices["Pixel 5"], None, {"home": [], "portfolio": []})):
        dev = {k: v for k, v in dev.items() if k != "default_browser_type"}
        init = STANDALONE_INIT if "홈 화면 앱" in name else ""
        if saved:
            init += f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(saved, ensure_ascii=False))}); }} catch (e) {{}} }})();"
        srv, ctx, page, _ = R.open(build_site(files), dev["viewport"]["width"], init=init or None, device=dev)

        def run():
            wait_ready(page)
            for key in ("home", "portfolio"):
                tab(page, TABS[key])
                at(page, key)
                page.locator('[data-ui-v2="date-line"]').first.wait_for(state="visible")
                kinds = page.locator('[data-ui-v2="ios-hint"]').evaluate_all("(els) => els.map((e) => e.dataset.kind)")
                assert kinds == want[key], (key, kinds)
                if not C["hint"]["first"]:
                    assert page.locator('[data-ui-v2="ios-hint"]:visible').count() == 0      # 문구 승인 전에는 보이지 않아요
                R.collect(page)
        R.check(page, "아이폰 안내", name, run)
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
                      lambda: scene_locked(R, files, width), lambda: scene_growth(R, files, width),
                      lambda: scene_us_date(R, files, width),
                      lambda: scene_old_app(R, files, width, '[{"id":"s1","name":"포트폴리오 1"}]', True),
                      lambda: scene_old_app(R, files, width, "[]", False),
                      lambda: scene_old_app(R, files, width, "{not json", False),
                      lambda: scene_daily(R, files, width), lambda: scene_today(R, files, width),
                      lambda: scene_about(R, files, width), lambda: scene_routes(R, files, width),
                      lambda: scene_market(R, files, width), lambda: scene_stocks(R, files, width),
                      lambda: scene_missing(R, files, width), lambda: scene_no_holding(R, files, width)]
            for fn in scenes:
                try:
                    fn()
                except Exception as e:
                    R.results.append((f"[{width}] 장면 실행", False, str(e).splitlines()[0][:200]))
                    print(f"  FAIL  [{width}] 장면 실행: {e}", flush=True)
        try:                                                     # 아이폰 13 화면(390×664) 하나로만
            scene_iphone_records(R, files, p.devices["iPhone 13"])
        except Exception as e:
            R.results.append(("[아이폰] 장면 실행", False, str(e).splitlines()[0][:200]))
            print(f"  FAIL  [아이폰] 장면 실행: {e}", flush=True)
        try:                                                     # v19.0c: 아이폰 홈 화면 안내 (아이폰 사파리에서만)
            scene_hint(R, files, p.devices)
        except Exception as e:
            R.results.append(("[아이폰 안내] 장면 실행", False, str(e).splitlines()[0][:200]))
            print(f"  FAIL  [아이폰 안내] 장면 실행: {e}", flush=True)
        browser.close()

    ok = Matcher([v for _, v in copy_strings()[1] if isinstance(v, str)], loose_slots=True)
    ko = sorted({t for t in R.texts if HANGUL.search(t)})
    stray = [t for t in ko if not ok(R.unnamed(t))]
    R.results.append((f"보이는 한국어 {len(ko)}가지 모두 src/copy/v2.js 또는 데이터 이름에서 왔어요", len(ko) > 120 and not stray, str(stray[:8])))
    R.results.append(("페이지 오류 0건 (모든 장면)", not R.errors, "; ".join(R.errors)[:300]))
    R.results.append(("다른 사이트 요청 0건 (글꼴·통계·CDN 없음)", not R.outside, ", ".join(sorted(set(R.outside)))[:300]))
    w = max(len(n) for n, _, _ in R.results)
    print("\n뱁이가 나온 화면 (그림 | 화면 | 걸린 숫자 | 숫자가 아닌 이유: 예외 칸 · 날짜 · 종목 수):")
    print("\n".join(placements_table()))
    print("\n뱁새 2.0 미리 보기 스모크 테스트 결과 · 데이터: tests/fixtures/v2")
    for name, good, msg in R.results:
        print(f"  {'PASS' if good else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in R.results if not r[1]]
    print(f"\n{len(R.results) - len(bad)} / {len(R.results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
