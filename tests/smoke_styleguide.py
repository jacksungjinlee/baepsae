# -*- coding: utf-8 -*-
"""스타일 페이지 휴대폰 크기 확인 (v18.1): python tests/smoke_styleguide.py [--shots DIR]

헤드리스 Chromium 으로 styleguide.html 을 390×844 로 열어요.
- 페이지 오류 0, 콘솔 오류 0, 실패한 요청 0
- 15가지 컴포넌트가 모두 보이고, "예시 데이터" 표시가 있어요
- Pretendard 가 실제로 쓰여요 (글꼴 파일을 받아 왔어요)
- 가로 스크롤 없음, 누르는 곳은 모두 44px 이상, 뱁이 그림이 모두 열려요
- 대비 표의 모든 줄이 4.5:1 이상
- 눌러 보기: 숫자 늘리기, 금액 더하기·지우기와 경고 줄, 고르기 버튼, 접는 섹션, 시트 열기·닫기(Esc), 아래 탭
"""
import argparse
import functools
import http.server
import os
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENTS = ["hero-band", "button", "stat-strip", "list-row", "status-chip", "segmented", "stepper", "money-input",
              "bottom-action-bar", "bottom-sheet", "collapsible", "bottom-tab-bar", "dot-strip", "weight-bar", "rule-row"]


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", help="스크린샷을 저장할 폴더")
    args = ap.parse_args()
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""))

    srv, base = serve()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            errors, failed = [], []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("requestfailed", lambda r: failed.append(r.url))
            page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
            page.set_default_timeout(15000)
            page.goto(base + "/styleguide.html", wait_until="networkidle")
            page.evaluate("document.fonts.ready.then(() => true)")

            counts = page.evaluate("""(names) => Object.fromEntries(names.map(n => [n, document.querySelectorAll(`[data-ui="${n}"]`).length]))""", COMPONENTS)
            check("15가지 컴포넌트가 모두 있어요", all(counts[n] > 0 for n in COMPONENTS), str(counts))
            check("'예시 데이터' 표시", page.locator("[data-sample-label]").inner_text().strip() == "예시 데이터")

            font = page.evaluate("""() => ({ ok: document.fonts.check('700 16px "Pretendard Variable"', '가'),
                loaded: [...document.fonts].filter(f => f.family.includes('Pretendard') && f.status === 'loaded').length,
                family: getComputedStyle(document.querySelector('h1')).fontFamily })""")
            fam_ok = font["family"].lstrip("'\"").startswith("Pretendard Variable")
            check("Pretendard 글꼴을 받아서 써요", font["ok"] and font["loaded"] > 0 and fam_ok, str(font))
            check("Pretendard 한글 조각을 받았어요", font["loaded"] >= 3, str(font["loaded"]))

            sw = page.evaluate("document.documentElement.scrollWidth")
            check("가로 스크롤 없음", sw <= 390, f"scrollWidth {sw}")

            small = page.evaluate("""() => [...document.querySelectorAll('button, [role="button"], input')]
                .map(e => { const r = e.getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), t: (e.getAttribute('aria-label') || e.textContent || e.tagName).slice(0, 20), inSeg: !!e.closest('[data-ui="segmented"]') }; })
                .filter(x => x.h > 0 && (x.h < 44 || x.w < 44))""")
            check("누르는 곳은 모두 44px 이상", not small, str(small[:5]))

            imgs = page.evaluate("""() => [...document.images].map(i => ({ src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0 }))""")
            check("그림이 모두 열려요", imgs and all(i["ok"] for i in imgs), str([i for i in imgs if not i["ok"]]))

            ratios = page.evaluate("""() => [...document.querySelectorAll('[data-pair]')].map(e => [e.dataset.pair, +e.dataset.ratio])""")
            check("대비 표 모두 4.5:1 이상", len(ratios) >= 18 and all(r >= 4.5 for _, r in ratios), str([x for x in ratios if x[1] < 4.5]))

            emoji = page.evaluate(r"""() => /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(document.body.innerText)""")
            check("이모지 0개", not emoji)

            # 눌러 보기
            live = page.locator("[data-stepper-live]")
            live.get_by_role("button", name="종목 수 늘리기").click()
            check("숫자 늘리기: 6개 → 7개", live.locator('[data-ui="stepper-value"]').inner_text() == "7개")
            mini = page.locator('[data-state-label="At minimum"] button[aria-label="종목 수 줄이기"]')
            check("가장 작을 때 줄이기는 꺼져 있어요", mini.is_disabled())

            money = page.locator("[data-money-live]")
            money.get_by_role("button", name="+100만").click()
            check("금액 +100만: 1,000 → 1,100", money.locator("input").input_value() == "1,100")
            money.get_by_role("button", name="지우기").click()
            check("지우기 → 빈 칸과 안내 줄", money.locator("input").input_value() == "" and
                  "만원 단위" in money.locator('[data-ui="money-warning"]').inner_text())
            money.locator("input").fill("120000")
            check("10억원 넘으면 경고 줄", "10억원" in money.locator('[data-ui="money-warning"]').inner_text())

            seg = page.locator('[data-ui="segmented"][aria-label="나눠 담는 방식"]')
            seg.get_by_role("radio", name="확신대로").click()
            check("고르기 버튼: 확신대로 선택", seg.get_by_role("radio", name="확신대로").get_attribute("aria-checked") == "true" and
                  "흔들림은 보지 않아요" in page.locator("[data-split-note]").inner_text())

            col = page.locator('[data-ui="collapsible"]').first
            before = col.get_attribute("data-open")
            col.locator("button").first.click()
            check("접는 섹션 열기", before == "0" and col.get_attribute("data-open") == "1")

            page.locator("[data-open-sheet]").click()
            dialog = page.locator('[data-ui="bottom-sheet"]:not([data-inline]) [role="dialog"]')
            check("시트가 열려요", dialog.is_visible())
            page.keyboard.press("Escape")
            check("Esc 로 시트가 닫혀요", dialog.count() == 0)
            page.locator("[data-open-sheet]").click()
            page.locator('[data-ui="bottom-sheet"]:not([data-inline]) button[aria-label="닫기"]').click()
            check("X 로 시트가 닫혀요", dialog.count() == 0)

            tabs = page.locator('[data-ui="bottom-tab-bar"]').first
            tabs.get_by_role("button", name="덱 짜기").click()
            check("아래 탭: 덱 짜기 선택", tabs.get_by_role("button", name="덱 짜기").get_attribute("aria-current") == "page")
            check("찾기 탭은 아직 꺼져 있어요", tabs.locator('button[aria-label="찾기, 이 목업에는 없어요"]').is_disabled())

            if args.shots:
                os.makedirs(args.shots, exist_ok=True)
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=os.path.join(args.shots, "styleguide-390.png"), full_page=True)

            check("페이지 오류 0", not errors, str(errors[:3]))
            check("실패한 요청 0", not failed, str(failed[:3]))
            b.close()
    finally:
        srv.shutdown()

    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} 통과")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
