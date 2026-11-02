#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""뱁새 2.0 미리 보기(app-preview.html) 스모크 테스트 — 지어낸 예시 데이터로 휴대폰 크기(320·390)에서 끝까지 눌러봐요.

  python tests/smoke_preview.py                 # 저장소의 app-preview.html 로
  python tests/smoke_preview.py --shots DIR     # 화면마다 스크린샷을 DIR 에 저장

- 모든 화면에 '예시 데이터' 표시가 보여요 (오늘 · 내 덱 · 덱 짜기 단계마다 · 후보 고르기 · 매수 계획)
- noindex, 서비스워커 등록 없음, data.json · corp.json · macro.json 을 받지 않음 (요청 0건), 다른 사이트 요청 0건
- 모든 탭 · 시작 덱마다 후보 고르기까지 · 한 덱은 매수 계획 → 샀어요 → 새로 고침해도 내 덱에 남음 (미리 보기 전용 저장 키)
- 멈춤 경고 없음 (예시 데이터의 발행일은 고정이에요) · 페이지 오류 0건 · 보이는 한국어는 모두 문구 파일 또는 예시 데이터의 이름
"""
import argparse
import functools
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copytrace import Matcher, copy_strings, HANGUL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT = 15000
WHOLE_BAD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")
SLOT_LEFT = re.compile(r"\{\w+\}")
C, FLAT = copy_strings()
DECKS = ["deepValue", "garp", "quality", "strict", "lowVol", "trend", "krUs", "income"]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def site():
    d = tempfile.mkdtemp(prefix="baepsae-preview-")
    for f in ["app-preview.html", "baepsae.html", "icon-192.png"] + [f"baepi-{i}.png" for i in range(1, 10)]:
        shutil.copy(os.path.join(ROOT, f), d)
    shutil.copytree(os.path.join(ROOT, "fonts"), os.path.join(d, "fonts"))
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

            def route(r):
                u = r.request.url
                if u.startswith(base):
                    if re.search(r"/(data|corp|macro)\.json", u):
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
                got = page.evaluate("""() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    while (w.nextNode()) { const n = w.currentNode; const e = n.parentElement; if (!e || e.closest('script, style')) continue;
                      const r = e.getBoundingClientRect(); if (!r.width && !r.height) continue; if (n.textContent.trim()) out.push(n.textContent); }
                    for (const e of document.querySelectorAll('[aria-label],[alt],[placeholder]'))
                      for (const a of ['aria-label', 'alt', 'placeholder']) { const v = e.getAttribute(a); if (v) out.push(v); }
                    return out; }""")
                texts.update(t.strip() for t in got if t.strip())
                body = page.locator("body").inner_text()
                assert not WHOLE_BAD.search(body), WHOLE_BAD.findall(body)
                assert not SLOT_LEFT.findall(body), SLOT_LEFT.findall(body)
                assert "멈췄어요" not in body and "갱신되지 않아" not in body, "예시 데이터에 멈춤 경고가 떠요"

            def tab(label):
                bar = page.locator('nav[data-ui="bottom-tab-bar"]')
                if bar.count() == 0:                  # 저장한 덱이 없으면 첫 화면은 덱 짜기 (아래 탭 없음)
                    if label == C["app"]["tabs"]["build"]:
                        return
                    page.get_by_role("button", name=C["build"]["backToday"]).click()
                bar.locator("button", has_text=label).click()

            def act():
                return page.locator('[data-ui-v2="action-bar"] button')

            def head():
                assert page.locator('meta[name="robots"][content*="noindex"]').count() == 1
                assert page.title() == f'{C["app"]["title"]} · {C["app"]["sample"]}', page.title()   # 탭 제목에도 예시 데이터
                assert page.evaluate("navigator.serviceWorker ? navigator.serviceWorker.getRegistration().then(r => !r) : true")
                page.locator('[data-ui-v2="date-line"]').first.wait_for(state="visible")
                assert "10월 30일" in page.locator('[data-ui-v2="date-line"]').first.inner_text()
                page.get_by_text(C["build"]["s0"]["title"]).wait_for(state="visible")     # 첫 방문: 덱 짜기부터
                label_here()
                # 미리 보기는 Jack 이 혼자 보는 페이지라 머리말에 '예전 뱁새 보기' 링크를 두지 않아요 (예시 데이터 표시 자리)
                assert page.locator('[data-ui-v2="old-app-link"]').count() == 0
                assert page.locator('[data-ui-v2="search-link"]').count() == 0      # 미리 보기는 지금 앱으로 가는 머리말 링크가 없어요
                assert page.locator('[data-ui-v2="old-app-note"]').count() == 0, "미리 보기에 '예전 뱁새' 안내가 떠요"
                assert page.evaluate("localStorage.getItem('baepsae_v10_slots')"), "예전 기록을 미리 넣지 못했어요"
                shot(page, width, "0-landing")
                tab(C["app"]["tabs"]["today"])
                page.get_by_text(C["app"]["pending"]).first.wait_for(state="visible")
                label_here()
                shot(page, width, "1-today")
            check(W + "첫 화면 덱 짜기 → 오늘: 예시 데이터 표시 · noindex · 서비스워커 없음 · 날짜 · 멈춤 경고 없음", head, page, width)

            def deck_tab():
                tab(C["app"]["tabs"]["deck"])
                page.get_by_text(C["store"]["export"]).wait_for(state="visible")
                assert page.locator('[data-ui-v2="old-app-note"]').count() == 0, "미리 보기 내 덱에 '예전 뱁새' 안내가 떠요"
                label_here()
                shot(page, width, "2-mydeck")
            check(W + "탭: 내 덱", deck_tab, page, width)

            def every_deck():
                tab(C["app"]["tabs"]["build"])
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
                    page.get_by_role("button", name=C["pick"]["back"]).click()
                    page.get_by_role("button", name=C["build"]["restart"]).click()
                shot(page, width, "3-start")
            check(W + "시작 덱 8개 모두 예시 데이터로 후보 고르기까지 (막힘 없음)", every_deck, page, width)

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
                page.get_by_role("button", name=C["plan"]["doneLink"]).click()
                stored = page.evaluate("[localStorage.getItem('baepsae2.preview.v1'), localStorage.getItem('baepsae2.v1')]")
                assert stored[0] and stored[1] is None, "미리 보기 기록은 미리 보기 키에만 저장돼요"
                page.reload(wait_until="domcontentloaded")
                tab(C["app"]["tabs"]["deck"])
                page.get_by_text("배당 생활비 덱").wait_for(state="visible")
                label_here()
                shot(page, width, "8-mydeck-after")
            check(W + "배당 생활비: 매수 계획 → 샀어요 → 새로 고침해도 내 덱에 (미리 보기 저장 키만 씀)", plan_and_buy, page, width)

            def search():
                with page.expect_navigation():
                    tab(C["app"]["tabs"]["search"])
                assert page.url.endswith("/baepsae.html")
            check(W + "탭: 찾기 → 지금 앱", search, page, width)
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
    results.append(("data.json · corp.json · macro.json 요청 0건", not json_reqs, ", ".join(json_reqs)[:200]))
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
    sys.exit(main())
