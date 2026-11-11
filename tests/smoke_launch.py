#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""메인 주소 = 뱁새 2.0 (v18.3 Part F) 스모크 테스트: 저장소 맨 위를 그대로 띄우고 '/' 부터 열어봐요. 320 · 390px.

  python tests/smoke_launch.py                 # 고정 시험 데이터(tests/fixtures/v2)로 — 그날의 발행 파일은 읽지 않아요 (Jack 2026-11-11)
  python tests/smoke_launch.py --shots DIR     # 화면 스크린샷
  python tests/smoke_launch.py --data DIR      # DIR 의 진짜 data/corp/macro/disc.json 만으로 (매일 실행의 발행 전 화면 검사 · Jack 2026-11-11)

- '/' (index.html) → app.html 로 가요 (예전처럼 baepsae.html 이 아니에요)
- 저장한 포트폴리오가 없는 방문자는 첫 방문 홈(포트폴리오 만들기)부터, 있는 방문자는 홈(오늘의 판정)부터 봐요 (v19.0c: #home).
  모두 처음 안내를 이미 본 방문자예요 (v19.3c: 처음 안내가 저절로 뜨는 첫 방문은 tests/smoke_v2.py scene_v193c · scene_v193c_first)
- ☰ 메뉴에 '예전 뱁새 보기'가 있고, 누르면 지금 앱(baepsae.html)이 열려요. 종목 탭의 한국 회사는 (v19.1a) 2.0 회사 페이지(#stocks/코드)로
- v19.0c 전에 저장한 기본 이름('배당 생활비 덱')은 화면에서만 새 이름('배당 생활비 포트폴리오'), 저장본은 그대로
- 지금 앱 푸터의 '소개'(v19.0)를 누르면 2.0 의 소개 페이지(app.html#about)가 열리고, 소개의 뒤로(닫기)는 지금 앱으로 돌아가요
- --data DIR (매일 실행의 '발행 전 화면 검사'): 그 폴더의 진짜 데이터로 같은 장면을 봐요 (고정 데이터 장면 · CV 링크 장면은 빼고).
  데이터는 2.0 이 쓰는 항목을 다 가진 것이어야 해요 (아니면 브라우저를 열기 전에 실패). 2026-11-11 까지는 옵션 없이도 저장소의
  그날 파일로 한 번 더 돌았어요 — 그 장면들이 이제 여기로 옮겨 왔어요 (PR 의 CI 가 그날 발행에 흔들리지 않게).
- 페이지 오류 0건, app.html 에서 다른 사이트 요청 0건 (GoatCounter 는 시험에서 꺼요: ?dev=1 과 같은 localStorage 표시)
- CV 링크 (Jack, 2026-11-05; v17.5.1 데이터 · 390px 에서 한 번): baepsae.html 을 2.0 표시(?from=app)도 # 도 없이 열면 app.html 로 가요.
  예전 뱁새는 붙지도 그려지지도 않고(#root 없음 · paint 없음 · 데이터 요청 없음), 기록이 하나만 늘어요(뒤로 → 온 곳).
  ?utm_source · ?trk 는 보내요 · 표시가 있으면 남아요 · # 만 있으면 남고 표시가 붙어요(새로고침해도 남아요) · 2.0 의 예전 뱁새 보기와
  바로가기 다섯 개가 그 화면을 열고 새로고침해도 남아요 · GoatCounter 는 보낼 때 한 번(경로 /baepsae/baepsae.html→app), 로컬 주소와
  개발 표시에서는 0번 · 저장한 예전 포트폴리오는 그대로 있고 2.0 의 링크로 열려요 · 오프라인(서비스워커)에서 두 페이지를 오가지 않아요
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
import threading

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copytrace import copy_strings  # noqa: E402
from test_launch import V175_FORMAT, real_data_missing  # noqa: E402
from visualcheck import V2_IMAGES, visual_ok, copy_pictures  # noqa: E402
import tmpdirs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C, _ = copy_strings()
TABS = C["app"]["tabs"]
APP_URL = re.compile(r"/app\.html#home$")                      # v19.0c: 주소 없이 열면 그 자리에서 #home
DECK_WORD = re.compile(r"(?<!인)덱")
# 저장소의 지금 데이터가 어느 단계인지에 따라 2.0 첫 화면이 달라요 (머지 문 테스트와 같은 판단):
#   old = v17.5 형식 전 → '불러오지 못했어요' · fields = v17.5 형식, v17.5.1 항목 없음 → '준비 중' · live = 덱 짜기가 열려요
REPO_LABELS = {"old": "v17.5 형식 전", "fields": "v17.5.1 항목 없음", "live": "v17.5.1 항목 있음"}


def repo_state(missing):
    return "old" if V175_FORMAT in missing else ("fields" if missing else "live")


FIXTURES = os.path.join(ROOT, "tests", "fixtures", "v2")       # 옵션 없이 돌 때의 데이터 (고정)
DATA_DIR = None                                                # --data DIR 일 때만 (아래 use_data): 진짜 데이터
REPO_STATE = REPO_LABEL = None                                 # --data 일 때만 use_data 가 정해요
WAIT = 15000
KST = dt.timezone(dt.timedelta(hours=9))
SITE = ["index.html", "app.html", "baepsae.html", "sw.js", "manifest.webmanifest", "og-v19.png", "icon-192.png", "icon-512.png",
        "baepi-og.webp", "jack-photo.jpg"] + V2_IMAGES + \
       [f"baepi-{i}.png" for i in range(1, 10)]
DATA = ["data.json", "corp.json", "macro.json", "disc.json"]
SAVED = {"v": 1, "decks": [{"id": "dlaunch", "name": "배당 생활비 덱", "createdAt": "2026-10-31",
                            "holdings": [{"t": "005930", "nk": "삼성전자", "target": 0.2, "plannedQty": 4, "rules": []}],
                            "purchases": [{"t": "005930", "date": "2026-10-31", "qty": 4, "price": 225000, "ccy": "KRW"}]}]}


def use_data(dir_):
    """--data DIR: 고정 시험 데이터 대신 DIR 의 진짜 네 파일만 써요 (매일 실행의 발행 전 화면 검사).
    발행 전 검사라서 데이터는 2.0 이 쓰는 항목을 다 가진 단계('live')여야 해요: 아니면 브라우저를 열기 전에 멈춰요
    ('불러오지 못했어요' · '준비 중' 화면이 맞게 뜨는 것을 '통과'로 치지 않아요)."""
    global DATA_DIR, REPO_STATE, REPO_LABEL
    dir_ = os.path.abspath(dir_)
    read = {}
    for f in DATA:
        with open(os.path.join(dir_, f), encoding="utf-8") as fh:   # 없거나 읽히지 않으면 여기서 멈춰요 (조용히 저장소 파일로 바꾸지 않아요)
            read[f] = json.load(fh)
    missing = real_data_missing(read["data.json"], read["corp.json"], read["macro.json"])
    if missing:
        raise SystemExit(f"!! --data {dir_}: 2.0 이 쓰는 항목이 빠진 데이터예요 ({', '.join(missing)}) → 발행 전 검사는 실패예요")
    DATA_DIR = dir_
    REPO_STATE = repo_state(missing)
    REPO_LABEL = REPO_LABELS[REPO_STATE]


def site(variant):
    d = tmpdirs.make("baepsae-launch-")
    for f in SITE:
        shutil.copy(os.path.join(ROOT, f), d)
    shutil.copytree(os.path.join(ROOT, "fonts"), os.path.join(d, "fonts"))
    copy_pictures(d)                                                 # v19.3b: 기준 · 템플릿 그림
    if variant == "fixtures":                                        # 고정 시험 데이터 네 파일 (v17.5 형식 + v17.5.1 필드) · 발행 시각만 '방금'
        now = dt.datetime.now(KST).isoformat(timespec="seconds")
        for f in DATA:
            with open(os.path.join(FIXTURES, f), encoding="utf-8") as fh:
                j = json.load(fh)
            if f != "disc.json":                                     # (예전 그대로: data · corp · macro 의 발행 시각을 방금으로)
                j["publishedAt"] = now
            with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
                json.dump(j, fh, ensure_ascii=False)
    else:                                                            # --data DIR: 그 폴더의 파일을 한 글자도 바꾸지 않고
        for f in DATA:
            shutil.copy(os.path.join(DATA_DIR, f), d)
    return d


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def chromium_path():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


# ── CV 링크 (Jack, 2026-11-05) ──
LIVE = "https://jacksungjinlee.github.io/baepsae/"     # 실제 주소처럼 보이게 이 시험 안에서만 로컬 파일로 답해요 (인터넷에 나가지 않아요)
OLD_FIRST = "내 종목, 괜찮은 걸까요?"                     # 예전 뱁새 첫 화면
OLD_URL = re.compile(r"/baepsae\.html\?from=app$")
# 예전 뱁새 문서(baepsae.html 주소)에 #root 가 생기거나 화면이 그려지면 알려요. 보낼 때는 둘 다 없어야 해요 (남을 때는 둘 다 있어요).
CV_SEEN = r"""(() => {
  if (!/\/baepsae(\.html)?$/.test(location.pathname)) return;
  const here = location.pathname + location.search;
  const rep = (w) => { try { window.__cvSeen(here + ' ' + w); } catch (e) {} };
  let root = false;
  new MutationObserver(() => { if (!root && document.getElementById('root')) { root = true; rep('root'); } })
    .observe(document, { childList: true, subtree: true });
  try { new PerformanceObserver((l) => l.getEntries().forEach((e) => rep(e.name))).observe({ type: 'paint', buffered: true }); } catch (e) {}
})();"""
ACTIVE_TAB = ("() => { const b = [...document.querySelectorAll('nav.botNav button')].find((x) => getComputedStyle(x.querySelector('span'))"
              ".fontWeight === '800'); return b ? b.innerText.trim() : null; }")
CART_ROWS = """() => [...document.querySelectorAll('input[type=number][step="10"]')].map((i) => {
  const box = i.parentElement; const name = box.children[1] && box.children[1].children[0];
  return [name ? name.textContent : '?', i.value]; })"""
OLD_SLOT = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "005930", "mw": 300}]}
OLD_LOCAL = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "scv", "name": "CV test"}]),
             "baepsae_v10_slot_scv": json.dumps(OLD_SLOT)}
STORAGE = "() => [Object.fromEntries(Object.keys(localStorage).map((k) => [k, localStorage.getItem(k)])), Object.keys(sessionStorage).sort()]"


def wait_until(page, fn, what, tries=100):
    for _ in range(tries):
        if fn():
            return
        page.wait_for_timeout(100)
    assert fn(), what


def cv_link(browser, check, errors):
    """CV 링크 장면들 (v17.5.1 데이터, 390px). check(이름, 함수, 페이지, 표시) 는 main 의 것이에요."""
    root = site("fixtures")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    W = "[CV 링크 · 390px] "
    seen, reqs = [], []

    def context(local=None, live=False):
        # GoatCounter 의 개발 표시(baepsae_dev)를 심지 않아요: 로컬 주소에서 세지 않는 것을 그대로 보려고요 (요청은 모두 여기서 막아요)
        ctx = browser.new_context(viewport={"width": 390, "height": 780}, device_scale_factor=2, locale="ko-KR", service_workers="block")
        ctx.add_init_script("try { localStorage.setItem('baepsae2.v1.guideSeen', '1'); } catch (e) {}")             # v19.3c: 처음 안내를 이미 본 방문자 (Jack, 2026-11-08)
        ctx.expose_binding("__cvSeen", lambda src, w: seen.append(w))
        ctx.add_init_script(CV_SEEN)
        if local:                                                    # 처음 한 번만 심어요 (앱이 바꾼 것을 다시 덮지 않게)
            ctx.add_init_script("(() => { try { if (localStorage.getItem('__cvSeeded')) return; const kv = %s;"
                                " for (const k in kv) localStorage.setItem(k, kv[k]); localStorage.setItem('__cvSeeded', '1'); } catch (e) {} })();"
                                % json.dumps(local, ensure_ascii=False))

        def route(r):
            u = r.request.url
            try:
                frame = r.request.frame.url
            except Exception:
                frame = ""
            reqs.append((u, frame))
            if live and u.startswith(LIVE):
                f = u[len(LIVE):].split("#")[0].split("?")[0] or "index.html"
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    r.fulfill(path=fp)
                else:
                    r.fulfill(status=404, body="")
            elif "goatcounter.com/count" in u:
                r.fulfill(status=204, body="")                        # 세는 요청은 여기서 받아 두기만 해요
            elif u.startswith(base):
                r.continue_()
            else:
                r.abort()
        ctx.route("**/*", route)
        return ctx

    def new_page(ctx):
        page = ctx.new_page()
        page.set_default_timeout(WAIT)
        page.on("pageerror", lambda e: errors.append(f"cv: {e}"))
        return page

    def counted():
        return [u for u, _ in reqs if "goatcounter.com/count" in u]

    def old_doc_requests():                                          # 예전 뱁새 문서(baepsae.html 주소)가 보낸 요청
        return [u for u, f in reqs if re.search(r"/baepsae(\.html)?$", f.split("#")[0].split("?")[0])]

    ctx = context()
    page = new_page(ctx)

    def plain_visit_lands_in_2_0():
        page.goto(base + "/icon-192.png")
        n0 = page.evaluate("history.length")
        seen.clear(), reqs.clear()
        page.goto(base + "/baepsae.html", wait_until="domcontentloaded")
        page.wait_for_url(APP_URL)
        page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        assert page.title() == C["app"]["title"]
        assert page.evaluate("history.length") == n0 + 1, "기록이 하나보다 많이 늘었어요"   # baepsae.html 자리를 app.html 이 차지해요
        assert seen == [], seen                                                          # 예전 뱁새: #root 도 paint 도 없어요
        bad = [u for u in old_doc_requests() if re.search(r"\.json|gc\.zgo\.at|goatcounter", u)]
        assert not bad, bad                                                              # 데이터 · 통계 요청 없음 (앱이 돌지 않았어요)
        assert counted() == [], counted()                                                # 로컬 주소: GoatCounter 0번
        ss = page.evaluate("Object.keys(sessionStorage)")
        assert "baepsae_cv_sent" in ss and "baepsae_old_tab" not in ss, ss
        page.go_back()                                                                   # 뒤로 → 온 곳 (baepsae.html 이 아니에요)
        page.wait_for_url(re.compile(r"/icon-192\.png$"))
        # 리뷰(2026-11-05): 온 곳(링크드인 · PDF)에서 10초 안에 다시 눌러도 2.0 이에요 (되돌이 막기에 걸리지 않아요)
        for ref in (None, "https://www.linkedin.com/"):
            page.goto(base + "/baepsae.html", wait_until="domcontentloaded", referer=ref)
            page.wait_for_url(APP_URL)
            page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        # 되돌이 막기: 보낸 지 10초 안에 이 사이트가 이 탭을 다시 표시 없는 baepsae.html 로 보내면 남아요 (표시를 붙여요)
        with page.expect_navigation():
            page.evaluate("location.href = './baepsae.html'")
        page.wait_for_url(OLD_URL)
        page.get_by_text(OLD_FIRST).wait_for(state="visible")
        assert page.evaluate("sessionStorage.getItem('baepsae_old_tab')") is None    # 막기만으로는 이 탭을 예전 뱁새에 두지 않아요
    check(W + "표시 없이 열면 app.html (예전 뱁새는 붙지도 그려지지도 않음 · 기록 하나 · 뒤로 → 온 곳 · 로컬은 세지 않음 · "
          "곧바로 다시 눌러도 2.0 · 이 사이트에서 10초 안에 되돌아오면 남음)", plain_visit_lands_in_2_0, page, "cv")

    def other_params_are_redirected():
        for q in ("?utm_source=x", "?trk=public_profile&from=linkedin", "?utm_medium=email#"):
            p2 = new_page(ctx)
            p2.goto(base + "/baepsae.html" + q, wait_until="domcontentloaded")
            p2.wait_for_url(APP_URL)
            p2.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
            p2.close()
    check(W + "?utm_source=x · ?trk= · from=linkedin 은 표시가 아니에요 → app.html", other_params_are_redirected, page, "cv")

    def marker_stays():
        p2 = new_page(ctx)
        seen.clear()
        p2.goto(base + "/baepsae.html?from=app", wait_until="domcontentloaded")
        p2.get_by_text(OLD_FIRST).wait_for(state="visible")
        assert p2.url == base + "/baepsae.html?from=app", p2.url
        assert p2.evaluate("sessionStorage.getItem('baepsae_old_tab')") == "1"
        wait_until(p2, lambda: any(w.endswith(" root") for w in seen), seen)          # 감시가 실제로 #root 를 잡아요 (위 검사의 대조군)
        p2.close()
    check(W + "?from=app → 예전 뱁새 그대로", marker_stays, page, "cv")

    def hash_stays_and_gets_the_marker():
        p2 = new_page(ctx)
        p2.goto("about:blank")
        p2.goto(base + "/baepsae.html#macro", wait_until="domcontentloaded")         # 예전에 공유한 링크 (표시 없음)
        p2.wait_for_url(base + "/baepsae.html?from=app")                             # 표시가 붙고, 예전 뱁새가 # 을 읽고 지워요
        wait_until(p2, lambda: p2.evaluate(ACTIVE_TAB) == "금리·원자재", "#macro → 금리·원자재")
        p2.reload(wait_until="domcontentloaded")                                     # 새로고침해도 예전 뱁새
        p2.get_by_text(OLD_FIRST).wait_for(state="visible")
        assert p2.url == base + "/baepsae.html?from=app", p2.url
        p2.go_back()                                                                 # 표시를 붙여도 기록은 늘지 않아요
        p2.wait_for_url("about:blank")
        p2.goto(base + "/baepsae.html#foo", wait_until="domcontentloaded")           # 모르는 # 도 남고, # 은 그대로
        p2.get_by_text(OLD_FIRST).wait_for(state="visible")
        assert p2.url == base + "/baepsae.html?from=app#foo", p2.url
        p2.close()
    check(W + "# 만 있으면 남고 표시가 붙어요 (#macro → 금리·원자재, 새로고침해도 남음, 기록 그대로 · 모르는 # 도 남음)",
          hash_stays_and_gets_the_marker, page, "cv")

    def links_from_2_0_open_the_right_screen():
        p2 = new_page(ctx)
        p2.goto(base + "/app.html", wait_until="domcontentloaded")
        p2.wait_for_url(APP_URL)

        def menu(item):
            p2.locator('[data-ui-v2="menu-button"]').first.click()
            return p2.locator(f'[data-ui-v2="menu"] [data-ui-v2="menu-item"][data-item="{item}"]')

        def tab_link(tab, sel):
            p2.locator('nav[data-ui="bottom-tab-bar"] button', has_text=TABS[tab]).click()
            p2.wait_for_url(re.compile(rf"/app\.html#{tab}$"))
            return p2.locator(sel).first

        def card(card_id, title):
            def ok():
                top = p2.evaluate(f"(() => {{ const e = document.getElementById('{card_id}'); return e ? Math.round(e.getBoundingClientRect().top) : null; }})()")
                return top is not None and 0 <= top <= 120 and p2.locator(f"#{card_id}").inner_text().startswith(title)
            return ok

        def active(label):
            return lambda: p2.evaluate(ACTIVE_TAB) == label

        # v19.1a (#36): 2.0 의 한국 회사 줄은 2.0 회사 페이지를 열어요 (예전 뱁새 기업분석 링크가 없어요: 아래에서 확인)
        cases = [("예전 뱁새 보기", lambda: menu("old-app"), "", lambda: p2.get_by_text(OLD_FIRST).is_visible()),
                 ("용어 사전", lambda: menu("glossary"), "#info=glossary", card("info-glossary", "용어 사전")),
                 ("데이터 출처", lambda: menu("sources"), "#info=sources", card("info-sources", "데이터 출처와 갱신")),
                 ("금리·원자재", lambda: tab_link("market", '[data-ui-v2="old-screen"][data-id="macro"]'), "#macro", active("금리·원자재")),
                 ("공시·수급", lambda: tab_link("market", '[data-ui-v2="old-screen"][data-id="disc"]'), "#disc", active("공시·수급"))]
        for name, find, tail, on_screen in cases:
            link = find()
            link.wait_for(state="visible")
            href = link.get_attribute("href")
            assert href.startswith("./baepsae.html?from=app" + tail), (name, href)
            with p2.expect_navigation():
                link.click()
            p2.wait_for_url(OLD_URL)                                                 # 예전 뱁새: # 은 읽고 지워도 표시는 남아요
            wait_until(p2, on_screen, (name, "그 화면이 아니에요"))
            p2.reload(wait_until="domcontentloaded")                                 # 새로고침해도 예전 뱁새 (2.0 으로 가지 않아요)
            p2.get_by_text(OLD_FIRST).wait_for(state="visible")
            assert OLD_URL.search(p2.url), (name, p2.url)
            p2.go_back()
            p2.wait_for_url(re.compile(r"/app\.html#"))
            p2.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        # 2.0 의 어느 링크도 표시(?from=app) 없이 예전 뱁새로 가지 않아요 · 한국 회사 줄은 예전 뱁새로 가는 링크가 아니에요 (v19.1a)
        tab_link("stocks", '[data-ui-v2="popular-list"][data-market="kr"] [data-ui-v2="stock-row"]').wait_for(state="visible")
        assert p2.locator('[data-ui-v2="popular-list"] [data-ui-v2="stock-row"] a').count() == 0
        hrefs = p2.evaluate("() => [...document.querySelectorAll('a[href*=\"baepsae.html\"]')].map((a) => a.getAttribute('href'))")
        assert all(h.startswith("./baepsae.html?from=app") for h in hrefs), hrefs
        p2.close()
    check(W + "2.0 의 예전 뱁새 보기 · 용어 사전 · 데이터 출처 · 금리·원자재 · 공시·수급 → 예전 뱁새의 그 화면 "
          "(새로고침해도 남음 · 뒤로 → 2.0) · 한국 회사 줄은 2.0 회사 페이지 (예전 뱁새 링크 아님)", links_from_2_0_open_the_right_screen, page, "cv")
    ctx.close()

    def goatcounter_once_on_the_live_address():
        from urllib.parse import parse_qs, urlsplit
        live = context(live=True)
        p2 = new_page(live)
        reqs.clear(), seen.clear()
        p2.goto(LIVE + "baepsae.html", wait_until="domcontentloaded", referer="https://www.linkedin.com/")
        p2.wait_for_url(LIVE + "app.html#home")
        p2.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        p2.wait_for_timeout(500)
        got = counted()
        assert len(got) == 1, got                                                    # 한 번
        q = {k: v[0] for k, v in parse_qs(urlsplit(got[0]).query).items()}
        assert got[0].startswith("https://baepsae.goatcounter.com/count?"), got[0]
        assert q["p"] == "/baepsae/baepsae.html→app" and q["r"] == "https://www.linkedin.com/", q
        assert seen == [], seen
        assert [u for u in old_doc_requests() if "gc.zgo.at" in u] == []            # 예전 뱁새의 원래 페이지뷰는 세지 않아요
        assert [u for u, f in reqs if "gc.zgo.at/count.js" in u and "/app.html" in f], "app.html 은 예전처럼 자기 페이지뷰를 세요"
        # 남을 때: 세지 않고, 예전 뱁새의 원래 페이지뷰(count.js)는 예전 경로 그대로
        reqs.clear()
        p2.goto(LIVE + "baepsae.html?from=app", wait_until="domcontentloaded")
        p2.get_by_text(OLD_FIRST).wait_for(state="visible")
        assert counted() == [], counted()
        assert [u for u in old_doc_requests() if "gc.zgo.at/count.js" in u], "예전 뱁새가 GoatCounter 를 불러오지 않았어요"
        assert p2.evaluate("window.goatcounter.path(location.pathname + location.search)") == "/baepsae/baepsae.html"
        # ?dev=1: 세지 않고, 2.0 이 이 브라우저를 빼 줘요 (HANDOFF 의 ?dev=1 그대로)
        p3 = new_page(live)
        reqs.clear()
        p3.goto(LIVE + "baepsae.html?dev=1", wait_until="domcontentloaded")
        p3.wait_for_url(LIVE + "app.html?dev=1#home")
        p3.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        assert counted() == [] and p3.evaluate("localStorage.getItem('baepsae_dev')") == "1"
        p4 = new_page(live)                                                          # 이제 이 브라우저는 개발 표시: 보내도 세지 않아요
        reqs.clear()
        p4.goto(LIVE + "baepsae.html", wait_until="domcontentloaded")
        p4.wait_for_url(LIVE + "app.html#home")
        p4.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        p4.wait_for_timeout(500)
        assert counted() == [], counted()
        live.close()
    check(W + "GoatCounter: 실제 주소에서 보낼 때 한 번 (/baepsae/baepsae.html→app, 링크드인에서 왔음) · 남을 때는 예전 경로 · 개발 표시는 0번",
          goatcounter_once_on_the_live_address, None, "cv")

    def saved_old_portfolio_is_kept():
        ctl = context(local=OLD_LOCAL)                                               # 대조군: app.html 을 바로 열었을 때의 저장소
        p1 = new_page(ctl)
        p1.goto(base + "/app.html", wait_until="domcontentloaded")
        p1.wait_for_url(APP_URL)
        p1.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        p1.wait_for_timeout(500)
        want_local, want_session = p1.evaluate(STORAGE)
        ctl.close()
        c2 = context(local=OLD_LOCAL)
        p2 = new_page(c2)
        p2.goto(base + "/baepsae.html", wait_until="domcontentloaded")
        p2.wait_for_url(APP_URL)
        p2.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        p2.wait_for_timeout(500)
        got_local, got_session = p2.evaluate(STORAGE)
        for k, v in OLD_LOCAL.items():
            assert got_local.get(k) == v, k                                         # 예전 포트폴리오: 옮기거나 지우지 않아요
        assert sorted(got_local) == sorted(want_local), (sorted(got_local), sorted(want_local))   # 보내기가 더한 것 없음
        assert got_session == sorted(set(want_session) | {"baepsae_cv_sent"}), got_session          # 이 탭의 표시 하나만
        p2.locator('[data-ui-v2="menu-button"]').first.click()
        with p2.expect_navigation():
            p2.locator('[data-ui-v2="menu"] [data-ui-v2="menu-item"][data-item="old-app"]').click()
        p2.wait_for_url(OLD_URL)
        p2.get_by_text("차근차근 만들기", exact=True).click()
        p2.get_by_text("CV test", exact=False).first.click()
        p2.locator("button.openSettings").first.wait_for(state="visible")
        wait_until(p2, lambda: p2.evaluate(CART_ROWS) == [["삼성전자", "300"]], "저장한 포트폴리오의 종목이 보이지 않아요")
        assert json.loads(p2.evaluate("localStorage.getItem('baepsae_v10_slots')"))[0]["id"] == "scv"
        c2.close()
    check(W + "저장한 예전 포트폴리오: 보내도 저장소 그대로 (app.html 을 바로 연 것과 같음) · 2.0 의 예전 뱁새 보기로 열려요",
          saved_old_portfolio_is_kept, None, "cv")
    srv.shutdown()
    srv.server_close()

    def offline_never_loops():
        d = site("fixtures")
        s2 = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=d))
        threading.Thread(target=s2.serve_forever, daemon=True).start()
        b2 = f"http://127.0.0.1:{s2.server_address[1]}"
        c = browser.new_context(viewport={"width": 390, "height": 780}, locale="ko-KR", service_workers="allow")
        c.add_init_script("try { localStorage.setItem('baepsae2.v1.guideSeen', '1'); } catch (e) {}")               # v19.3c: 처음 안내를 이미 본 방문자
        c.route(lambda u: not u.startswith(b2), lambda r: r.abort())
        c.add_init_script("(() => { try { localStorage.setItem('baepsae_dev', '1'); } catch (e) {} })();")
        p1 = new_page(c)
        p1.goto(b2 + "/app.html", wait_until="domcontentloaded")
        wait_until(p1, lambda: p1.evaluate("navigator.serviceWorker.getRegistration().then((r) => !!(r && r.active))"), "서비스워커가 없어요")
        p1.reload(wait_until="domcontentloaded")                                     # 이제 워커가 맡아요: app.html 이 캐시에 들어가요
        p1.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
        p1.goto(b2 + "/baepsae.html?from=app", wait_until="domcontentloaded")
        p1.get_by_text(OLD_FIRST).wait_for(state="visible")
        cached = "() => caches.open('baepsae-v19-cv').then((c) => c.keys()).then((k) => k.map((r) => new URL(r.url).pathname))"
        wait_until(p1, lambda: {"/app.html", "/baepsae.html"} <= set(p1.evaluate(cached)), "캐시에 두 페이지가 없어요")
        s2.shutdown()
        s2.server_close()                                                            # 오프라인
        for drop_app in (False, True):
            if drop_app:                                                             # app.html 을 캐시에서 빼요: 워커는 예전 뱁새를 줘요
                p1.evaluate("caches.open('baepsae-v19-cv').then((c) => c.keys().then((ks) => Promise.all("
                            "ks.filter((r) => new URL(r.url).pathname === '/app.html').map((r) => c.delete(r)))))")
                assert "/app.html" not in p1.evaluate(cached)
            p = new_page(c)
            navs = []
            p.on("framenavigated", lambda f, p=p: navs.append(f.url) if f == p.main_frame else None)
            p.goto(b2 + "/baepsae.html", wait_until="domcontentloaded")
            if drop_app:                                                             # app.html 주소에 예전 뱁새: 거기서 멈춰요
                p.wait_for_url(b2 + "/app.html")
                p.get_by_text(OLD_FIRST).wait_for(state="visible")
            else:
                p.wait_for_url(APP_URL)
                p.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible")
            n = len(navs)
            p.wait_for_timeout(2500)
            assert len(navs) == n, navs                                              # 더 움직이지 않아요
            docs = [u.split("#")[0] for u in navs]
            assert docs.count(b2 + "/baepsae.html") == 1 and set(docs) == {b2 + "/baepsae.html", b2 + "/app.html"}, navs
            p.close()
        c.close()
    check(W + "오프라인(서비스워커): 캐시한 예전 뱁새 → app.html(캐시) · app.html 캐시가 없으면 그 주소에서 예전 뱁새로 멈춤 (오가지 않음)",
          offline_never_loops, None, "cv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    ap.add_argument("--data", default=None, help="이 폴더의 진짜 data/corp/macro/disc.json 만으로 (고정 데이터 장면은 돌리지 않아요)")
    args = ap.parse_args()
    if args.data:
        use_data(args.data)
    variants = ("repo",) if args.data else ("fixtures",)
    results, errors, outside = [], [], []

    def check(label, fn, page, tag):
        try:
            fn()
            results.append((label, True, ""))
        except Exception as e:
            results.append((label, False, str(e).splitlines()[0][:200]))
            if args.shots:
                os.makedirs(args.shots, exist_ok=True)
                try:
                    page.screenshot(path=os.path.join(args.shots, f"launch-fail-{tag}-{len(results)}.png"), full_page=True)
                except Exception:
                    pass
        print(f"  {'PASS' if results[-1][1] else 'FAIL'}  {label}", flush=True)

    def shot(page, name):
        if args.shots:
            os.makedirs(args.shots, exist_ok=True)
            page.screenshot(path=os.path.join(args.shots, name))

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path())
        if not args.data:                                           # CV 링크 장면은 고정 데이터로 봐요 (--data 는 진짜 데이터 장면만)
            cv_link(browser, check, errors)
        for variant in variants:
            root = site(variant)
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            for width in (320, 390):
                tag = f"{variant}-{width}"
                W = f"[{'v17.5.1 데이터' if variant == 'fixtures' else f'저장소 지금 데이터({REPO_LABEL})'} · {width}px] "

                def context(saved=False):
                    ctx = browser.new_context(viewport={"width": width, "height": 780}, device_scale_factor=2, locale="ko-KR",
                                              service_workers="block")
                    ctx.add_init_script("try { localStorage.setItem('baepsae2.v1.guideSeen', '1'); } catch (e) {}")   # v19.3c: 처음 안내를 이미 본 방문자

                    def route(r):
                        if r.request.url.startswith(base):
                            r.continue_()
                            return
                        try:
                            frame = r.request.frame.url
                        except Exception:
                            frame = ""
                        if "/baepsae.html" not in frame:            # 지금 앱의 글꼴·CDN 요청은 그 페이지 몫이에요
                            outside.append(f"{r.request.url} (from {frame})")
                        r.abort()
                    ctx.route("**/*", route)
                    seed = "localStorage.setItem('baepsae_dev','1');"     # GoatCounter 끄기 (지금 앱의 ?dev=1 과 같은 표시)
                    if saved:
                        seed += f"if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(SAVED, ensure_ascii=False))});"
                    ctx.add_init_script(f"(() => {{ try {{ {seed} }} catch (e) {{}} }})();")
                    page = ctx.new_page()
                    page.set_default_timeout(WAIT)
                    page.on("pageerror", lambda e: errors.append(f"{tag}: {e}"))
                    return ctx, page

                ctx, page = context()

                def root_goes_to_app():
                    page.goto(base + "/", wait_until="domcontentloaded")
                    page.wait_for_url(APP_URL, timeout=WAIT)
                    assert page.title() == C["app"]["title"]
                check(W + "'/' (index.html) → app.html", root_goes_to_app, page, tag)

                def no_deck_lands_on_home():
                    page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")       # 첫 방문 홈: 머리글 + 포트폴리오 만들기
                    assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 1
                    assert page.locator('[data-ui-v2="home-start"]').inner_text().strip() == C["build"]["title"]
                    state = "live" if variant == "fixtures" else REPO_STATE
                    if state == "old":                      # v17.5 형식 전 데이터는 받지 않아요
                        page.get_by_text(C["app"]["loadFail"]).wait_for(state="visible")
                    else:
                        page.locator('[data-ui-v2="popular"]').wait_for(state="visible")
                    sw = page.evaluate("document.documentElement.scrollWidth")
                    assert sw <= width, f"가로 스크롤 {sw}"
                    assert not DECK_WORD.search(page.locator("body").inner_text())
                    visual_ok(page)                         # v19.0b: 그림이 모두 열려요 · 뱁이 규칙(숫자 없는 화면) · 아이콘
                    if width == 320 and variant == "fixtures":
                        shot(page, "launch-320-landing-no-deck.png")
                    page.locator('[data-ui-v2="home-start"] button').click()
                    page.wait_for_url(re.compile(r"#portfolio/build$"))
                    assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
                    if state == "live":                     # v17.5 형식 + v17.5.1 항목: 포트폴리오 만들기가 그대로 열려요
                        page.get_by_text(C["build"]["s0"]["title"]).wait_for(state="visible")
                        assert page.locator("[data-deck]").count() == 9
                        assert page.locator('[data-ui-v2="build-not-ready"]').count() == 0
                        assert page.get_by_text(C["app"]["loadFail"]).count() == 0
                    elif state == "fields":                 # v17.5 형식인데 v17.5.1 항목이 없음: '준비 중'만, 순위·비중 없음
                        page.locator('[data-ui-v2="build-not-ready"]').wait_for(state="visible")
                        page.get_by_text(C["app"]["pending"]).first.wait_for(state="visible")
                        assert page.locator("[data-deck]").count() == 0 and page.locator("[data-cand]").count() == 0
                        assert page.get_by_text(C["app"]["loadFail"]).count() == 0
                    else:
                        page.get_by_text(C["app"]["loadFail"]).wait_for(state="visible")
                        assert page.locator("[data-deck]").count() == 0
                    visual_ok(page)
                    page.go_back()                          # 휴대폰 뒤로 → 홈
                    page.wait_for_url(APP_URL)
                    page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")
                check(W + "저장한 포트폴리오가 없는 방문자(처음 안내를 이미 본) → 첫 방문 홈 → 포트폴리오 만들기 → 뒤로 → 홈", no_deck_lands_on_home, page, tag)

                def stocks_open_company():
                    # v19.1a: 종목 탭의 한국 회사는 2.0 회사 페이지로 (#stocks/코드). 예전 뱁새의 기업분석으로 가지 않아요
                    page.locator('nav[data-ui="bottom-tab-bar"] button', has_text=TABS["stocks"]).click()
                    page.wait_for_url(re.compile(r"/app\.html#stocks$"))
                    if (REPO_STATE if variant != "fixtures" else "live") == "old":
                        page.get_by_text(C["app"]["loadFail"]).wait_for(state="visible")
                        return
                    row = page.locator('[data-ui-v2="popular-list"][data-market="kr"] [data-ui-v2="stock-row"]').first
                    row.wait_for(state="visible")
                    t = row.get_attribute("data-t")
                    nk = [x for x in row.inner_text().split("\n") if x.strip()][0]          # 이름 (첫 글자 표시는 CSS 라 글이 아니에요)
                    assert row.locator("a").count() == 0, "한국 회사 줄이 예전 뱁새로 가는 링크예요"
                    box = row.locator("button").bounding_box()                               # 누르는 곳 44px 이상, 화면 안
                    assert box and box["height"] >= 44 and box["x"] + box["width"] <= width, box
                    row.locator("button").click()
                    page.wait_for_url(re.compile(r"/app\.html#stocks/" + re.escape(t) + "$"))
                    page.locator('[data-ui-v2="co-name"]').wait_for(state="visible")
                    assert page.locator('[data-ui-v2="co-name"]').inner_text() == nk          # 2.0 회사 페이지의 그 회사
                    assert page.get_by_text("이 종목의 데이터를 찾지 못했어요.").count() == 0
                    page.go_back()
                    page.wait_for_url(re.compile(r"/app\.html#stocks$"))
                    page.locator('[data-ui-v2="recent"] [data-ui-v2="stock-row"]').first.wait_for(state="visible")
                check(W + "종목 탭 → 한국 회사 → 2.0 회사 페이지 → 뒤로 → 종목 (최근 본 종목에 남아요)", stocks_open_company, page, tag)

                def menu_opens_old_app():
                    page.locator('[data-ui-v2="menu-button"]').click()
                    link = page.locator('[data-ui-v2="menu"] [data-ui-v2="menu-item"][data-item="old-app"]')
                    link.wait_for(state="visible")
                    assert link.inner_text().strip() == C["app"]["oldApp"] and link.get_attribute("href") == "./baepsae.html?from=app"
                    box = link.bounding_box()
                    assert box and box["height"] >= 44 and box["x"] + box["width"] <= width, box
                    with page.expect_navigation():
                        link.click()
                    assert page.url.endswith("/baepsae.html?from=app"), page.url
                    page.get_by_text("내 종목, 괜찮은 걸까요?").wait_for(state="visible")
                    back = page.locator("a[data-v2-link]")                  # 지금 앱 머리말의 '뱁새 2.0 보기' (Jack, 2026-11-02)
                    back.wait_for(state="visible")
                    assert back.inner_text() == "뱁새 2.0 보기"
                    with page.expect_navigation():
                        back.click()
                    page.wait_for_url(APP_URL)
                    page.locator('[data-ui-v2="menu-button"]').wait_for(state="visible")
                check(W + "☰ 메뉴 '예전 뱁새 보기' → 지금 앱 → '뱁새 2.0 보기' → 다시 2.0 (#home)", menu_opens_old_app, page, tag)

                def old_footer_opens_about():
                    page.goto(base + "/baepsae.html?from=app", wait_until="domcontentloaded")   # CV 링크 (2026-11-05): 2.0 표시
                    page.get_by_text("내 종목, 괜찮은 걸까요?").wait_for(state="visible")
                    link = page.locator("a[data-about-link]").first
                    link.wait_for(state="visible")
                    assert link.inner_text() == "소개" and link.get_attribute("href") == "./app.html#about"
                    with page.expect_navigation():
                        link.click()
                    assert page.url.endswith("/app.html#about"), page.url
                    page.locator('[data-ui-v2="about"][data-lang="ko"]').wait_for(state="visible")
                    page.get_by_text(C["about"]["ko"]["maker"]["title"]).wait_for(state="visible")
                    assert page.evaluate("document.activeElement && document.activeElement.dataset.uiV2") == "about-heading"
                    visual_ok(page)
                    with page.expect_navigation():                                       # 뒤로(닫기) → 온 곳(지금 앱)으로 한 걸음
                        page.get_by_role("button", name=C["app"]["close"]).click()
                    assert page.url.endswith("/baepsae.html?from=app"), page.url
                    page.get_by_text("내 종목, 괜찮은 걸까요?").wait_for(state="visible")
                check(W + "지금 앱 푸터 '소개' → app.html#about (소개 페이지) → 뒤로 → 다시 지금 앱", old_footer_opens_about, page, tag)
                ctx.close()

                ctx, page = context(saved=True)

                def saved_deck_lands_on_home():
                    page.goto(base + "/", wait_until="domcontentloaded")
                    page.wait_for_url(APP_URL, timeout=WAIT)
                    page.locator('nav[data-ui="bottom-tab-bar"]').wait_for(state="visible")
                    on = page.locator('nav[data-ui="bottom-tab-bar"] button[aria-current="page"]').inner_text().strip()
                    assert on == TABS["home"], on
                    assert page.locator('[data-ui-v2="home-hero"]').count() == 0            # 다시 온 방문자: 첫 방문 머리글 없음
                    page.locator('[data-ui-v2="menu-button"]').wait_for(state="visible")
                    if width == 320 and variant == "fixtures":
                        shot(page, "launch-320-home-saved.png")
                    page.locator('nav[data-ui="bottom-tab-bar"] button', has_text=TABS["portfolio"]).click()
                    shown = C["app"]["deckName"].replace("{name}", C["build"]["decks"]["income"]["name"])
                    page.get_by_text(shown).wait_for(state="visible")                       # 예전 기본 이름은 화면에서만 새 이름
                    stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
                    assert stored["decks"][0]["name"] == SAVED["decks"][0]["name"], "저장본의 이름을 바꿨어요"
                    assert not DECK_WORD.search(page.locator("body").inner_text())
                    visual_ok(page)
                check(W + "저장한 포트폴리오가 있는 방문자 → 홈 · 포트폴리오에 기록 (예전 이름은 화면에서만 새 이름)", saved_deck_lands_on_home, page, tag)
                ctx.close()
            srv.shutdown()
        browser.close()

    results.append(("페이지 오류 0건 (index.html · app.html · baepsae.html)", not errors, "; ".join(errors)[:300]))
    results.append(("app.html 에서 다른 사이트 요청 0건", not outside, ", ".join(sorted(set(outside)))[:300]))
    w = max(len(n) for n, _, _ in results)
    print("\n메인 주소(Part F) 스모크 테스트 결과" + (f" · 데이터: {DATA_DIR}" if args.data else ""))
    for name, good, msg in results:
        print(f"  {'PASS' if good else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)} / {len(results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(tmpdirs.run(main))        # 통과하면 이번 실행의 임시 폴더를 지우고, 실패하면 남겨요 (tests/tmpdirs.py)
