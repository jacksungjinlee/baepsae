#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뱁새 2.0 미리 보기(app-preview.html) 스모크 테스트 — 지어낸 예시 데이터로 휴대폰 크기(320·390)에서 끝까지 눌러봐요.

  python tests/smoke_preview.py                 # 저장소의 app-preview.html 로
  python tests/smoke_preview.py --shots DIR     # 화면마다 스크린샷을 DIR 에 저장

- 모든 화면에 '예시 데이터' 표시가 보여요 (홈 · 포트폴리오 · 종목 · 시장 · 포트폴리오 만들기 단계마다 · 후보 고르기 · 매수 계획 · 메뉴)
- v19.0c: 미리 보기는 예전 뱁새(실제 데이터)로 가는 길이 하나도 없어요: 메뉴는 소개와 날짜만, 시장에 예전 뱁새 버튼 없음,
  종목의 한국 회사는 링크가 아니에요 (미국 종목은 '기업분석은 한국 상장 기업만 볼 수 있어요.'). 화면 어디에도 '덱'이 없어요
- noindex, 서비스워커 등록 없음, data.json · corp.json · macro.json 을 받지 않음 (요청 0건), 다른 사이트 요청 0건
- 모든 탭 · 시작 덱마다 후보 고르기까지 · 한 덱은 매수 계획 → 샀어요 → 새로 고침해도 내 덱에 남음 (미리 보기 전용 저장 키) ·
  산 뒤에는 오늘에 판정 띠, 내 덱에 평가 금액 (Part E)
- 멈춤 경고 없음 (예시 데이터의 발행일은 고정이에요) · 페이지 오류 0건 · 보이는 한국어는 모두 문구 파일 또는 예시 데이터의 이름
- 소개(v19.0, #about): 푸터의 '소개'로 열려요. 지어낸 데이터라 숫자 줄도 숫자 문단('{n}개가 넘는')도 없어요. 뒤로 → 전 화면
- PC(v19.0d, 1280 × 800): 왼쪽 메뉴의 링크는 소개뿐 · '예시 데이터' 표시는 위 막대에 화면마다 하나 · 네 탭 · '/' 와 검색 칸 →
  종목 결과 · 포트폴리오 만들기 · 가로 스크롤 없음 (데이터 파일 요청 0건은 아래 결과 줄이 함께 봐요)
"""
import argparse
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
from copytrace import Matcher, copy_strings, HANGUL  # noqa: E402
from visualcheck import V2_IMAGES, visual_ok, copy_pictures  # noqa: E402
import tmpdirs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = 15000
WHOLE_BAD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")
SLOT_LEFT = re.compile(r"\{\w+\}")
C, FLAT = copy_strings()
DECKS = ["deepValue", "garp", "quality", "strict", "lowVol", "trend", "krUs", "income"]
TABS = C["app"]["tabs"]
BACK_BUILD = C["build"]["backToday"] or TABS["home"]        # v19.0c: 승인 대기 이름은 승인된 이름으로 (src/copy/v2.js "승인 전:")
DONE_LINK = C["plan"]["doneLink"] or TABS["home"]
PICK_BACK = C["pick"]["back"] or C["build"]["title"]
DECK_WORD = re.compile(r"(?<!인)덱")
SAVED_NAME = C["app"]["deckName"].replace("{name}", C["build"]["decks"]["income"]["name"])   # 배당 생활비 포트폴리오


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def site():
    d = tmpdirs.make("baepsae-preview-")
    for f in ["app-preview.html", "baepsae.html", "icon-192.png", "baepi-og.webp", "jack-photo.jpg"] + V2_IMAGES + [f"baepi-{i}.png" for i in range(1, 10)]:
        shutil.copy(os.path.join(ROOT, f), d)
    shutil.copytree(os.path.join(ROOT, "fonts"), os.path.join(d, "fonts"))
    copy_pictures(d)                                                 # v19.3b: 기준 · 템플릿 그림
    return d


def chromium_path():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    args = ap.parse_args()
    with open(os.path.join(ROOT, "src", "preview", "fictional.json"), encoding="utf-8") as f:
        fic = json.load(f)
    names = sorted({s.get(k) for s in fic["data"]["stocks"] for k in ("nk", "ne", "indName") if s.get(k)}, key=len, reverse=True)
    root = site()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    results, errors, outside, json_reqs, texts = [], [], [], [], set()

    def check(label, fn, page, width):
        try:
            fn()
            results.append((label, True, ""))
        except Exception as e:
            results.append((label, False, str(e).splitlines()[0][:200]))
            if args.shots:
                os.makedirs(args.shots, exist_ok=True)
                try:
                    page.screenshot(path=os.path.join(args.shots, f"preview-fail-{width}-{len(results)}.png"), full_page=True)
                except Exception:
                    pass
        print(f"  {'PASS' if results[-1][1] else 'FAIL'}  {label}", flush=True)

    def shot(page, width, name, full=True):
        if args.shots:
            os.makedirs(args.shots, exist_ok=True)
            page.screenshot(path=os.path.join(args.shots, f"preview-{width}-{name}.png"), full_page=full)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path())
        for width in (320, 390):
            ctx = browser.new_context(viewport={"width": width, "height": 780}, device_scale_factor=2, locale="ko-KR")
            ctx.add_init_script("try { localStorage.setItem('baepsae2.preview.v1.guideSeen', '1'); } catch (e) {}")   # v19.3c: 처음 안내를 이미 본 방문자 (Jack, 2026-11-08)

            def route(r):
                u = r.request.url
                if u.startswith(base):
                    if re.search(r"/(data|corp|macro|disc)\.json", u):           # v19.1a: disc.json 도 (회사 페이지의 공시 탭)
                        json_reqs.append(u)
                    r.continue_()
                    return
                try:
                    frame = r.request.frame.url
                except Exception:
                    frame = ""
                if "/baepsae.html" not in frame:
                    outside.append(u)
                r.abort()
            ctx.route("**/*", route)
            # 지금 앱에 포트폴리오가 있는 브라우저라도 미리 보기에는 '예전 뱁새 보기' 안내가 없어요 (그 링크가 없는 페이지예요)
            ctx.add_init_script("""(() => { try { localStorage.setItem('baepsae_v10_slots', '[{"id":"s1","name":"x"}]'); } catch (e) {} })();""")
            page = ctx.new_page()
            page.set_default_timeout(WAIT)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/app-preview.html", wait_until="domcontentloaded")
            W = f"[{width}px] "

            def label_here():
                page.locator('[data-ui-v2="sample-label"]').first.wait_for(state="visible")
                assert C["app"]["sample"] in page.locator('[data-ui-v2="sample-label"]').first.inner_text()
                sw = page.evaluate("document.documentElement.scrollWidth")
                assert sw <= width, f"가로 스크롤 {sw}"
                # 큰 숫자(v19.0b [data-ui="amount"])는 한 덩어리 글로 모아요 (단위 span 으로 나뉘어도 "1,073만원" 그대로 출처 확인)
                got = page.evaluate("""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    while (w.nextNode()) { const n = w.currentNode; const e = n.parentElement; if (!e || e.closest('script, style, [data-ui="amount"]')) continue;
                      const r = e.getBoundingClientRect(); if (!r.width && !r.height) continue; if (n.textContent.trim()) out.push(n.textContent); }
                    for (const a of document.querySelectorAll('[data-ui="amount"]')) { const r = a.getBoundingClientRect(); if ((r.width || r.height) && a.textContent.trim()) out.push(a.textContent); }
                    for (const e of document.querySelectorAll('[aria-label],[alt],[placeholder]'))
                      for (const a of ['aria-label', 'alt', 'placeholder']) { const v = e.getAttribute(a); if (v) out.push(v); }
                    return out; }""")
                texts.update(t.strip() for t in got if t.strip())
                body = page.locator("body").inner_text()
                assert not WHOLE_BAD.search(body), WHOLE_BAD.findall(body)
                assert not SLOT_LEFT.findall(body), SLOT_LEFT.findall(body)
                assert "멈췄어요" not in body and "갱신되지 않아" not in body, "예시 데이터에 멈춤 경고가 떠요"
                assert not [t for t in got + [body] if DECK_WORD.search(t)], "v19.0c: 화면에 '덱'이 있어요"
                assert page.locator('a[href*="baepsae.html"]').count() == 0, "미리 보기에 예전 뱁새(실제 데이터)로 가는 링크가 있어요"
                visual_ok(page)              # v19.0b: 그림이 모두 열리고, 뱁이 규칙 · 아이콘 두 층 · 살구색 없음 (tests/visualcheck.py)

            def tab(label):
                bar = page.locator('nav[data-ui="bottom-tab-bar"]')
                if bar.count() == 0:                  # 포트폴리오 만들기 첫 단계 안 (아래 탭 없음): 먼저 뒤로
                    page.get_by_role("button", name=BACK_BUILD).click()
                    bar.wait_for(state="visible")
                bar.locator("button", has_text=label).click()

            def at(r):
                page.wait_for_function("(r) => { const e = document.querySelector('[data-ui-v2=\"screen\"]'); return !!e && e.dataset.route === r; }", arg=r)

            def start_build():
                tab(TABS["home"])
                at("home")
                first = page.locator('[data-ui-v2="home-start"] button')
                if first.count():
                    first.click()
                else:
                    tab(TABS["portfolio"])
                    page.locator('[data-ui-v2="deck-empty"] button, [data-ui-v2="build-more"] button').first.click()
                at("portfolio/build")

            def act():
                return page.locator('[data-ui-v2="action-bar"] button')

            def head():
                assert page.locator('meta[name="robots"][content*="noindex"]').count() == 1
                assert page.title() == f'{C["app"]["title"]} · {C["app"]["sample"]}', page.title()   # 탭 제목에도 예시 데이터
                assert page.evaluate("navigator.serviceWorker ? navigator.serviceWorker.getRegistration().then(r => !r) : true")
                page.locator('[data-ui-v2="date-line"]').first.wait_for(state="visible")
                assert "10월 30일" in page.locator('[data-ui-v2="date-line"]').first.inner_text()
                at("home")                                                         # 첫 방문: 첫 방문 홈
                page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")
                page.locator('[data-ui-v2="popular"]').wait_for(state="visible")
                label_here()
                # 미리 보기는 Jack 이 혼자 보는 페이지라 머리말에 '예전 뱁새 보기' 링크를 두지 않아요 (예시 데이터 표시 자리)
                assert page.locator('[data-ui-v2="old-app-link"]').count() == 0
                assert page.locator('[data-ui-v2="search-link"]').count() == 0, "미리 보기에 지금 앱으로 가는 '찾기' 링크가 보여요"
                assert page.locator('[data-ui-v2="old-app-note"]').count() == 0, "미리 보기에 '예전 뱁새' 안내가 떠요"
                assert page.evaluate("localStorage.getItem('baepsae_v10_slots')"), "예전 기록을 미리 넣지 못했어요"
                assert page.locator('[data-ui-v2="today-hero"]').count() == 0 and page.get_by_text("할 일").count() == 0
                shot(page, width, "0-landing")
                page.locator('[data-ui-v2="menu-button"]').click()                   # 메뉴: 소개 · 처음 안내 다시 보기(v19.3c O.2: 소개 바로 뒤)와 날짜만 (예전 뱁새로 가는 줄 없음)
                menu = page.locator('[data-ui-v2="menu"]')
                menu.wait_for(state="visible")
                items = menu.locator('[data-ui-v2="menu-item"]').evaluate_all("(els) => els.map((e) => e.dataset.item)")
                assert items == ["about", "guide"], items
                assert "10월 30일 기준" in menu.locator('[data-ui-v2="menu-date"]').inner_text()
                label_here()
                shot(page, width, "1-menu", full=False)
                menu.locator('[data-ui-v2="menu-close"]').click()
                menu.wait_for(state="detached")
            check(W + "첫 방문 홈 · 메뉴(소개 · 날짜만): 예시 데이터 표시 · noindex · 서비스워커 없음 · 날짜 · 멈춤 경고 없음", head, page, width)

            def stocks_and_market():
                tab(TABS["stocks"])
                at("stocks")
                page.locator('[data-ui-v2="popular-list"][data-market="kr"]').wait_for(state="visible")
                assert page.locator('[data-ui-v2="popular-list"][data-market="us"]').count() == 1
                # v19.1a: 한국 · 미국 회사 모두 2.0 회사 페이지(예시 데이터)로 가요. 예전 뱁새로 가는 링크는 없어요 (label_here 가 봐요)
                kr = page.locator('[data-ui-v2="popular-list"][data-market="kr"] [data-ui-v2="stock-row"]').first
                assert kr.locator("a").count() == 0, "미리 보기의 한국 회사가 링크예요 (예전 뱁새로 가는 길)"
                label_here()
                shot(page, width, "1-stocks")
                for market in ("kr", "us"):
                    row = page.locator(f'[data-ui-v2="popular-list"][data-market="{market}"] [data-ui-v2="stock-row"]').first
                    t = row.get_attribute("data-t")
                    row.locator("button").click()
                    at(f"stocks/{t}")
                    co = page.locator('[data-ui-v2="company"]')
                    co.wait_for(state="visible")
                    assert co.get_attribute("data-cls") == market and page.locator('[data-ui-v2="co-tabs"] [data-tab="disc"]').count() == 0
                    assert page.locator('[data-ui-v2="co-mark"] img').count() == 0 and page.locator('main img[src^="baepi-"]:not([data-ui-v2="logo-mark"])').count() == 0
                    label_here()
                    shot(page, width, f"1-company-{market}")
                    page.go_back()
                    at("stocks")
                tab(TABS["market"])
                at("market")
                page.locator('[data-ui-v2="market-tile"]').first.wait_for(state="visible")
                assert page.locator('[data-ui-v2="market-tile"]').count() == 4 and page.locator('[data-ui-v2="old-screen"]').count() == 0
                label_here()
                shot(page, width, "1-market")
            check(W + "탭: 종목(한국 · 미국 회사 → 예시 데이터 회사 페이지, 공시 탭 없음 · 예전 뱁새 링크 없음) · 시장(네 칸, 예전 뱁새 버튼 없음)", stocks_and_market, page, width)

            def deck_tab():
                tab(TABS["portfolio"])
                page.get_by_text(C["store"]["export"]).wait_for(state="visible")
                assert page.locator('[data-ui-v2="old-app-note"]').count() == 0, "미리 보기 내 덱에 '예전 뱁새' 안내가 떠요"
                live = os.path.join(tmpdirs.make("baepsae-preview-file-"), "live.json")          # 실제 앱에서 내보낸 기록을 미리 보기에서 열면
                with open(live, "w", encoding="utf-8") as fh:
                    json.dump({"v": 1, "decks": []}, fh)
                page.locator('[data-ui-v2="import-file"]').set_input_files(live)
                box = page.locator('[data-ui-v2="import-bad"]')
                box.wait_for(state="visible")
                assert box.get_attribute("data-why") == "live" and box.inner_text().strip() == C["store"]["import"], box.inner_text()
                assert C["store"]["otherKind"] not in page.locator("body").inner_text()      # 그 문장은 실제 앱 전용
                label_here()
                shot(page, width, "2-mydeck")
            check(W + "탭: 포트폴리오", deck_tab, page, width)

            def every_deck():
                start_build()
                for d in DECKS:
                    page.locator(f'[data-deck="{d}"]').click()
                    label_here()
                    act().click()
                    label_here()
                    act().click()
                    label_here()
                    page.get_by_role("button", name="+1,000만").first.click()
                    page.wait_for_timeout(150)
                    assert act().is_enabled(), f"{d}: 조건 단계에서 막혔어요 ({act().inner_text()})"
                    act().click()
                    page.get_by_text(C["pick"]["title"]).first.wait_for(state="visible")
                    label_here()
                    assert act().is_enabled() and act().inner_text() == C["pick"]["makePlan"], f"{d}: 후보 {act().inner_text()}"
                    page.get_by_role("button", name=PICK_BACK).click()
                    page.get_by_role("button", name=C["build"]["restart"]).click()
                shot(page, width, "3-start")
            check(W + "시작 유형 8개 모두 예시 데이터로 후보 고르기까지 (막힘 없음)", every_deck, page, width)

            def plan_and_buy():
                page.locator('[data-deck="income"]').click()
                shot(page, width, "4-cards")
                act().click()
                act().click()
                page.get_by_role("button", name="+1,000만").first.click()
                shot(page, width, "5-terms")
                act().click()
                shot(page, width, "6-pick")
                act().click()
                page.locator("[data-row]").first.wait_for(state="visible")
                label_here()
                page.get_by_text(C["plan"]["y2022Note"]).wait_for(state="visible")
                for i in range(page.locator('[data-ui-v2="rules"] [data-ui="collapsible"]').count()):
                    page.locator('[data-ui-v2="rules"] [data-ui="collapsible"]').nth(i).locator("button").first.click()
                label_here()
                shot(page, width, "7-plan")
                shot(page, width, "7-plan-top", full=False)
                # 맨 아래로 내려도 '예시 데이터' 표시는 화면 안에 있어요 (머리 줄이 붙어 있어요)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(150)
                box = page.locator('[data-ui-v2="sample-label"]').first.bounding_box()
                assert box and 0 <= box["y"] < 120, f"아래로 내리면 예시 데이터 표시가 사라져요: {box}"
                act().click()
                sheet = page.locator('[data-ui="bottom-sheet"]')
                sheet.locator('[data-ui-v2="sample-label"]').wait_for(state="visible")      # 시트에도 표시
                page.wait_for_timeout(200)
                shot(page, width, "9-sheet", full=False)       # what the phone shows with the sheet open
                page.get_by_role("button", name=C["plan"]["save"]).click()
                page.get_by_text(C["plan"]["done"]).wait_for(state="visible")
                assert sheet.locator('[data-ui-v2="sample-label"]').is_visible()
                label_here()
                page.get_by_role("button", name=DONE_LINK).click()
                stored = page.evaluate("[localStorage.getItem('baepsae2.preview.v1'), localStorage.getItem('baepsae2.v1')]")
                assert stored[0] and stored[1] is None, "미리 보기 기록은 미리 보기 키에만 저장돼요"
                page.reload(wait_until="domcontentloaded")
                page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")   # 산 덱이 있으면 오늘의 판정 띠 (Part E)
                assert "멈췄어요" not in page.locator("body").inner_text()
                label_here()
                shot(page, width, "8-today-after")
                tab(TABS["portfolio"])
                page.get_by_text(SAVED_NAME).wait_for(state="visible")
                page.locator('[data-ui-v2="deck-summary"]').wait_for(state="visible")
                label_here()
                shot(page, width, "8-mydeck-after")
            check(W + "배당 생활비: 매수 계획 → 샀어요 → 새로 고침해도 포트폴리오에 (미리 보기 저장 키만 씀)", plan_and_buy, page, width)

            def about():
                foot = page.locator('[data-ui-v2="footer"]:visible').first
                foot.wait_for(state="visible")
                assert "INSEAD" not in foot.inner_text() and "이성진" not in foot.inner_text(), foot.inner_text()
                link = foot.locator('[data-ui-v2="about-link"]')
                assert link.inner_text() == C["app"]["aboutLink"] and link.get_attribute("href") == "#about"
                link.click()
                page.locator('[data-ui-v2="about"]').wait_for(state="visible")
                assert page.url.endswith("/app-preview.html#about"), page.url            # 미리 보기 안에서 열려요 (실제 앱으로 가지 않음)
                page.get_by_text(C["about"]["ko"]["maker"]["title"]).wait_for(state="visible")
                page.wait_for_timeout(300)
                # 지어낸 데이터의 숫자는 실제 분석 종목 수가 아니라서: 숫자 줄도, 숫자 문단도 없어요
                assert page.locator('[data-ui-v2="about-figures"]').count() == 0 and page.locator('[data-ui-v2="about-data"]').count() == 0
                assert page.get_by_text(C["about"]["ko"]["what"]["intro"]).is_visible()
                label_here()
                shot(page, width, "9-about")
                page.get_by_role("button", name=C["app"]["close"]).click()
                page.get_by_text(SAVED_NAME).first.wait_for(state="visible")           # 전 화면(포트폴리오)으로
                page.locator('[data-ui-v2="about"]').wait_for(state="detached")
                assert page.url.endswith("/app-preview.html#portfolio"), page.url
            check(W + "푸터 '소개' → 소개 (예시 데이터 표시 · 숫자 줄과 숫자 문단 없음) → 뒤로 → 포트폴리오", about, page, width)
            ctx.close()

        # v19.0d PC (1280 × 800): the same page with the left menu and the top bar. label_here() above reads `page` and `width`
        # from this function, so they are set to the PC page here.
        width = 1280
        ctx = browser.new_context(viewport={"width": width, "height": 800}, device_scale_factor=1, locale="ko-KR")
        ctx.add_init_script("try { localStorage.setItem('baepsae2.preview.v1.guideSeen', '1'); } catch (e) {}")       # v19.3c: 처음 안내를 이미 본 방문자
        ctx.route("**/*", route)
        page = ctx.new_page()
        page.set_default_timeout(WAIT)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "/app-preview.html#home", wait_until="domcontentloaded")

        def pc():
            page.locator('[data-ui-v2="side-menu"]').wait_for(state="visible")
            at("home")
            assert page.locator('nav[data-ui="bottom-tab-bar"], [data-ui-v2="menu-button"]').count() == 0
            items = page.locator('[data-ui-v2="side-link"]').evaluate_all("(els) => els.map((e) => e.dataset.item)")
            assert items == ["about", "guide"], items                          # 예전 뱁새(실제 데이터)로 가는 줄 없음 · 처음 안내 다시 보기는 소개 뒤 (v19.3c O.2)
            for key in ("home", "portfolio", "stocks", "market"):
                page.locator(f'[data-ui-v2="side-tab"][data-tab="{key}"]').click()
                at(key)
                page.locator('[data-ui-v2="top-bar"] [data-ui-v2="sample-label"]').wait_for(state="visible")
                assert page.locator('[data-ui-v2="sample-label"]:visible').count() == 1, "예시 데이터 표시가 둘이거나 없어요"
                label_here()
                shot(page, width, f"pc-{key}")
            assert page.locator('[data-ui-v2="market-tiles"]').get_attribute("data-cols") == "4"     # 버튼 칸이 없어 네 칸을 한 줄로
            name = fic["data"]["stocks"][0]["nk"]
            page.evaluate("() => document.activeElement && document.activeElement.blur()")
            page.keyboard.press("/")
            page.keyboard.type(name)
            at("stocks")
            page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"]').first.wait_for(state="visible")
            label_here()
            page.locator('[data-ui-v2="side-build"]').click()
            at("portfolio/build")
            page.locator('[data-ui-v2="top-bar"] [data-ui-v2="sample-label"]').wait_for(state="visible")
            label_here()
            shot(page, width, "pc-build")
        check("[1280px] PC: 왼쪽 메뉴(소개만) · 위 막대의 예시 데이터(화면마다 하나) · 네 탭 · '/' 검색 → 종목 · 포트폴리오 만들기 · 가로 스크롤 없음", pc, page, width)
        ctx.close()
        browser.close()
    srv.shutdown()

    ok = Matcher([v for _, v in FLAT if isinstance(v, str)], loose_slots=True)

    def unnamed(t):
        for n in names:
            if n in t:
                t = t.replace(n, "{}")
        return t
    ko = sorted({t for t in texts if HANGUL.search(t)})
    stray = [t for t in ko if not ok(unnamed(t))]
    results.append((f"보이는 한국어 {len(ko)}가지 모두 src/copy/v2.js 또는 예시 데이터 이름에서 왔어요", len(ko) > 100 and not stray, str(stray[:8])))
    results.append(("data.json · corp.json · macro.json · disc.json 요청 0건", not json_reqs, ", ".join(json_reqs)[:200]))
    results.append(("다른 사이트 요청 0건", not outside, ", ".join(sorted(set(outside)))[:200]))
    results.append(("페이지 오류 0건", not errors, "; ".join(errors)[:300]))
    w = max(len(n) for n, _, _ in results)
    print("\n뱁새 2.0 미리 보기(app-preview.html) 스모크 테스트 결과 · 데이터: src/preview/fictional.json (지어낸 예시)")
    for name, good, msg in results:
        print(f"  {'PASS' if good else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)} / {len(results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(tmpdirs.run(main))        # 통과하면 이번 실행의 임시 폴더를 지우고, 실패하면 남겨요 (tests/tmpdirs.py)
