#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""메인 주소 = 뱁새 2.0 (v18.3 Part F) 스모크 테스트: 저장소 맨 위를 그대로 띄우고 '/' 부터 열어봐요. 320 · 390px.

  python tests/smoke_launch.py                 # 두 데이터로: 저장소의 지금 파일 · tests/fixtures/v2 (v17.5.1 필드가 들어온 뒤의 모습)
  python tests/smoke_launch.py --shots DIR     # 화면 스크린샷

- '/' (index.html) → app.html 로 가요 (예전처럼 baepsae.html 이 아니에요)
- 저장한 덱이 없는 방문자는 덱 짜기부터, 저장한 덱이 있는 방문자는 오늘부터 봐요
- 머리말에 '예전 뱁새 보기'가 있고, 누르면 지금 앱(baepsae.html)이 열려요
- 저장소의 지금 데이터(v17.5 형식 전)에서는 2.0 이 '불러오지 못했어요'를 보여요 (예시 데이터를 실제처럼 보이지 않음)
- 페이지 오류 0건, app.html 에서 다른 사이트 요청 0건 (GoatCounter 는 시험에서 꺼요: ?dev=1 과 같은 localStorage 표시)
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

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copytrace import copy_strings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C, _ = copy_strings()
WAIT = 15000
KST = dt.timezone(dt.timedelta(hours=9))
SITE = ["index.html", "app.html", "baepsae.html", "sw.js", "manifest.webmanifest", "og.png", "icon-192.png", "icon-512.png"] + \
       [f"baepi-{i}.png" for i in range(1, 10)]
DATA = ["data.json", "corp.json", "macro.json", "disc.json"]
SAVED = {"v": 1, "decks": [{"id": "dlaunch", "name": "배당 생활비 덱", "createdAt": "2026-10-31",
                            "holdings": [{"t": "005930", "nk": "삼성전자", "target": 0.2, "plannedQty": 4, "rules": []}],
                            "purchases": [{"t": "005930", "date": "2026-10-31", "qty": 4, "price": 225000, "ccy": "KRW"}]}]}


def site(variant):
    d = tempfile.mkdtemp(prefix="baepsae-launch-")
    for f in SITE:
        shutil.copy(os.path.join(ROOT, f), d)
    shutil.copytree(os.path.join(ROOT, "fonts"), os.path.join(d, "fonts"))
    for f in DATA:
        shutil.copy(os.path.join(ROOT, f), d)                       # 지금 저장소의 파일 (지금 앱이 쓰는 것)
    if variant == "fixtures":                                        # 월요일 모습: v17.5 형식 + v17.5.1 필드
        now = dt.datetime.now(KST).isoformat(timespec="seconds")
        for f in ("data.json", "corp.json", "macro.json"):
            with open(os.path.join(ROOT, "tests", "fixtures", "v2", f), encoding="utf-8") as fh:
                j = json.load(fh)
            j["publishedAt"] = now
            with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
                json.dump(j, fh, ensure_ascii=False)
    return d


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def chromium_path():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    args = ap.parse_args()
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
        for variant in ("fixtures", "repo"):
            root = site(variant)
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            for width in (320, 390):
                tag = f"{variant}-{width}"
                W = f"[{'v17.5.1 데이터' if variant == 'fixtures' else '저장소 지금 데이터'} · {width}px] "

                def context(saved=False):
                    ctx = browser.new_context(viewport={"width": width, "height": 780}, device_scale_factor=2, locale="ko-KR",
                                              service_workers="block")

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
                    page.wait_for_url("**/app.html", timeout=WAIT)
                    assert page.title() == C["app"]["title"]
                check(W + "'/' (index.html) → app.html", root_goes_to_app, page, tag)

                def no_deck_lands_on_build():
                    page.get_by_text(C["build"]["title"]).first.wait_for(state="visible")
                    assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
                    if variant == "fixtures":
                        page.get_by_text(C["build"]["s0"]["title"]).wait_for(state="visible")
                        assert page.locator("[data-deck]").count() == 9
                    else:
                        page.get_by_text(C["app"]["loadFail"]).wait_for(state="visible")   # v17.5 형식 전 데이터는 받지 않아요
                    sw = page.evaluate("document.documentElement.scrollWidth")
                    assert sw <= width, f"가로 스크롤 {sw}"
                    if width == 320 and variant == "fixtures":
                        shot(page, "launch-320-landing-no-deck.png")
                check(W + "저장한 덱이 없는 방문자 → 덱 짜기", no_deck_lands_on_build, page, tag)

                def header_link_opens_old_app():
                    link = page.locator('[data-ui-v2="old-app-link"]')
                    link.wait_for(state="visible")
                    assert link.inner_text() == C["app"]["oldApp"]
                    box = link.bounding_box()
                    assert box and box["height"] >= 44 and box["x"] + box["width"] <= width, box
                    with page.expect_navigation():
                        link.click()
                    assert page.url.endswith("/baepsae.html"), page.url
                    page.get_by_text("내 종목, 괜찮은 걸까요?").wait_for(state="visible")
                check(W + "머리말 '예전 뱁새 보기' → 지금 앱이 열려요", header_link_opens_old_app, page, tag)
                ctx.close()

                ctx, page = context(saved=True)

                def saved_deck_lands_on_today():
                    page.goto(base + "/", wait_until="domcontentloaded")
                    page.wait_for_url("**/app.html", timeout=WAIT)
                    page.locator('nav[data-ui="bottom-tab-bar"]').wait_for(state="visible")
                    on = page.locator('nav[data-ui="bottom-tab-bar"] button[aria-current="page"]').inner_text()
                    assert on == C["app"]["tabs"]["today"], on
                    page.locator('[data-ui-v2="old-app-link"]').wait_for(state="visible")
                    if width == 320 and variant == "fixtures":
                        shot(page, "launch-320-header-old-app-link.png")
                    page.locator('nav[data-ui="bottom-tab-bar"] button', has_text=C["app"]["tabs"]["deck"]).click()
                    page.get_by_text("배당 생활비 덱").wait_for(state="visible")
                    page.locator('[data-ui-v2="old-app-link"]').wait_for(state="visible")
                check(W + "저장한 덱이 있는 방문자 → 오늘 (내 덱에 기록이 보여요)", saved_deck_lands_on_today, page, tag)
                ctx.close()
            srv.shutdown()
        browser.close()

    results.append(("페이지 오류 0건 (index.html · app.html · baepsae.html)", not errors, "; ".join(errors)[:300]))
    results.append(("app.html 에서 다른 사이트 요청 0건", not outside, ", ".join(sorted(set(outside)))[:300]))
    w = max(len(n) for n, _, _ in results)
    print("\n메인 주소(Part F) 스모크 테스트 결과")
    for name, good, msg in results:
        print(f"  {'PASS' if good else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)} / {len(results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
