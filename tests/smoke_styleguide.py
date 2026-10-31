# -*- coding: utf-8 -*-
"""스타일 페이지 휴대폰 크기 확인 (v18.1): python tests/smoke_styleguide.py [--shots DIR]

헤드리스 Chromium 으로 styleguide.html 을 320px 와 390px 폭으로 열어요.
- 페이지 오류 0, 콘솔 오류 0, 실패한 요청 0
- 15가지 컴포넌트가 모두 화면에 보이고, "예시 데이터" 표시가 있어요
- Pretendard 한글 조각을 실제로 받아서 써요
- 가로 스크롤 없음, 목록 줄의 칩이 오른쪽 숫자를 덮지 않음, 누르는 곳은 모두 44px 이상
- 컴포넌트 안의 padding·margin·gap 은 모두 4px 격자
- 화면에 보이는 한국어는 모두 docs/design/mockup-copy.csv 에서 왔어요 (숫자만 다를 수 있음)
- 대비 표의 모든 줄이 4.5:1 이상, 뱁이 그림이 모두 열려요
- 눌러 보기: 숫자 늘리기, 금액 더하기·지우기·잘못된 글자·경고 줄, 고르기 버튼(누르기·화살표 키),
  접는 섹션, 목록 줄 키보드, 시트(Esc · X · 바깥 누르기 · 안에서 끌어 바깥에서 놓기 · 포커스 가두기 · 뒤 스크롤 멈춤 ·
  낮은 화면에서 닫기 버튼이 보임), 아래 탭
"""
import argparse
import csv
import functools
import http.server
import os
import re
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPONENTS = ["hero-band", "button", "stat-strip", "list-row", "status-chip", "segmented", "stepper", "money-input",
              "bottom-action-bar", "bottom-sheet", "collapsible", "bottom-tab-bar", "dot-strip", "weight-bar", "rule-row"]
HANGUL = re.compile("[가-힣]")
FAKE_NAMES = {"늘봄금융", "솔담정밀", "마루식품"}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def mockup():
    with open(os.path.join(ROOT, "docs", "design", "mockup-copy.csv"), encoding="utf-8-sig") as f:
        return [r["지금 문구"].strip() for r in csv.DictReader(f) if r["지금 문구"].strip()]


def numless(s):
    """숫자·부호는 예시마다 달라도 돼요: 숫자 덩어리와 빼기 기호를 # 로 바꿔 비교해요."""
    s = s.replace("−", "-").replace("\n", " / ")
    return re.sub(r"[-+]?\d[\d,.]*", "#", s).strip()


def make_matcher(rows):
    exact = set(rows) | FAKE_NAMES
    loose = {numless(r) for r in rows}
    templates = [re.compile("^" + re.sub(r"\\\{[\w.]+\\\}", ".+?", re.escape(r)) + "$") for r in rows if "{" in r]

    def ok(text):
        t = text.strip().replace("\n", " / ")
        if t in exact or numless(t) in loose or any(rx.match(t) for rx in templates):
            return True
        # " · " 는 목업이 쓰는 구분 기호예요: 이어 붙인 조각이 각각 CSV 문구면 괜찮아요 (예: 규칙 줄 "지금 22% · 30% 넘으면 지켜봐요")
        parts = [p for p in t.split(" · ") if p.strip()]
        if len(parts) > 1 and all(ok(p) for p in parts):
            return True
        # 영어 안내 글 속 한국어 낱말 (예: "Amounts in 만원.") — 낱말마다 CSV 의 한 줄이어야 해요
        if re.search(r"[A-Za-z]{3,}", t):
            words = re.findall(r"[가-힣]+(?:\s[가-힣]+)*", t)
            return all(w in exact for w in words)
        return False
    return ok


def run_width(pw, base, width, check, shots):
    b = pw.chromium.launch()
    page = b.new_page(viewport={"width": width, "height": 844}, device_scale_factor=2)
    errors, failed = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("requestfailed", lambda r: failed.append(r.url))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.set_default_timeout(15000)
    page.goto(base + "/styleguide.html", wait_until="networkidle")
    page.evaluate("document.fonts.ready.then(() => true)")
    w = f"[{width}px] "

    vis = page.evaluate("""(names) => Object.fromEntries(names.map(n => [n, [...document.querySelectorAll(`[data-ui="${n}"]`)]
        .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }).length]))""", COMPONENTS)
    check(w + "15가지 컴포넌트가 모두 보여요", all(vis[n] > 0 for n in COMPONENTS), str(vis))
    check(w + "'예시 데이터' 표시", page.locator("[data-sample-label]").inner_text().strip() == "예시 데이터")

    font = page.evaluate("""() => {
        const hangul = (ur) => ur.split(',').some(p => { const m = p.trim().replace(/^U\\+/i, '').split('-');
            const a = parseInt(m[0], 16), z = parseInt(m[1] || m[0], 16); return a <= 0xD7A3 && z >= 0xAC00; });
        const faces = [...document.fonts].filter(f => f.family.includes('Pretendard'));
        return { check: document.fonts.check('700 16px "Pretendard Variable"', '가'),
                 hangulLoaded: faces.filter(f => f.status === 'loaded' && hangul(f.unicodeRange || '')).length,
                 family: getComputedStyle(document.querySelector('h1')).fontFamily }; }""")
    fam_ok = font["family"].lstrip("'\"").startswith("Pretendard Variable")
    check(w + "Pretendard 한글 조각을 받아서 써요", font["check"] and font["hangulLoaded"] > 0 and fam_ok, str(font))

    sw = page.evaluate("document.documentElement.scrollWidth")
    check(w + "가로 스크롤 없음", sw <= width, f"scrollWidth {sw}")

    overlap = page.evaluate("""() => [...document.querySelectorAll('[data-ui="list-row"]')].map(r => {
        const side = r.querySelector('[data-ui-part="side"]').getBoundingClientRect();
        const kids = [...r.querySelectorAll('[data-ui-part="main"] *')].map(e => e.getBoundingClientRect().right);
        return Math.max(...kids) - side.left; }).filter(d => d > 0.5)""")
    check(w + "목록 줄: 칩·글이 오른쪽 숫자를 덮지 않아요", not overlap, str(overlap))

    small = page.evaluate("""() => [...document.querySelectorAll('button, [role="button"], input')]
        .map(e => { const r = e.getBoundingClientRect(); return { h: Math.round(r.height), w: Math.round(r.width), t: (e.getAttribute('aria-label') || e.textContent || e.tagName).slice(0, 20) }; })
        .filter(x => x.h > 0 && (x.h < 44 || x.w < 44))""")
    check(w + "누르는 곳은 모두 44px 이상", not small, str(small[:5]))

    grid = page.evaluate("""() => { const bad = [];
        for (const e of document.querySelectorAll('[data-ui], [data-ui] *')) {
          if (e.closest('svg') || e.closest('[data-ui="dot-strip"]')) continue;
          const auto = (e.getAttribute('style') || '').includes('auto');   // margin: 0 auto 가운데 맞춤
          const s = getComputedStyle(e);
          for (const p of ['paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','rowGap','columnGap']) {
            if (auto && p.startsWith('margin')) continue;
            const v = parseFloat(s[p]); if (Number.isFinite(v) && Math.abs(v) % 4 > 0.01) bad.push(e.tagName + '.' + p + '=' + s[p]);
          } }
        return [...new Set(bad)].slice(0, 8); }""")
    check(w + "컴포넌트 간격은 모두 4px 격자", not grid, str(grid))

    if width == 390:
        rows = mockup()
        ok = make_matcher(rows)
        texts = page.evaluate("""() => { const out = []; const it = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (it.nextNode()) { const n = it.currentNode; if (n.parentElement.closest('script, style, noscript')) continue;
              const t = n.textContent; if (t.trim()) out.push(t); }
            for (const e of document.querySelectorAll('[aria-label],[alt],[aria-placeholder]'))
              for (const a of ['aria-label','alt','aria-placeholder']) { const v = e.getAttribute(a); if (v) out.push(v); }
            return out; }""")
        ko = [t for t in texts if HANGUL.search(t)]
        stray = sorted({t.strip() for t in ko if not ok(t)})
        check(w + f"보이는 한국어 {len(ko)}곳 모두 목업 문구에서 왔어요", len(ko) > 150 and not stray, str(stray[:6]))

        ratios = page.evaluate("""() => [...document.querySelectorAll('[data-pair]')].map(e => [e.dataset.pair, +e.dataset.ratio])""")
        check(w + "대비 표 모두 4.5:1 이상", len(ratios) >= 18 and all(r >= 4.5 for _, r in ratios), str([x for x in ratios if x[1] < 4.5]))
        imgs = page.evaluate("""() => [...document.images].map(i => ({ src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0 }))""")
        check(w + "그림이 모두 열려요", imgs and all(i["ok"] for i in imgs), str([i for i in imgs if not i["ok"]]))
        emoji = page.evaluate(r"""() => /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(document.body.innerText)""")
        check(w + "이모지 0개", not emoji)
        interact(page, check, w)

    if shots:
        os.makedirs(shots, exist_ok=True)
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=os.path.join(shots, f"styleguide-{width}.png"), full_page=True)
    check(w + "페이지 오류 0", not errors, str(errors[:3]))
    check(w + "실패한 요청 0", not failed, str(failed[:3]))
    b.close()


def interact(page, check, w):
    live = page.locator("[data-stepper-live]")
    live.get_by_role("button", name="종목 수 늘리기").click()
    check(w + "숫자 늘리기: 6개 → 7개", live.locator('[data-ui="stepper-value"]').inner_text() == "7개")
    check(w + "가장 작을 때 줄이기는 꺼져 있어요", page.locator('[data-state-label="At minimum"] button[aria-label="종목 수 줄이기"]').is_disabled())

    money = page.locator("[data-money-live]")
    inp = money.locator("input")
    money.get_by_role("button", name="+100만").click()
    check(w + "금액 +100만: 1,000 → 1,100", inp.input_value() == "1,100")
    inp.click()
    page.keyboard.press("End")
    page.keyboard.press("Backspace")
    check(w + "입력 중 지우기가 먹혀요: 1100 → 110", inp.input_value() == "110")
    page.keyboard.type("1.5")
    check(w + "소수점은 받지 않아요 (만원 단위 정수)", inp.input_value() == "11015" or inp.input_value() == "1105", inp.input_value())
    page.keyboard.press("Tab")
    v = inp.input_value()
    check(w + "칸을 벗어나면 쉼표로 묶어 보여요", re.fullmatch(r"\d{1,3}(,\d{3})*", v) is not None, v)
    money.get_by_role("button", name="지우기").click()
    check(w + "지우기 → 빈 칸과 안내 줄", inp.input_value() == "" and "만원 단위" in money.locator('[data-ui="money-warning"]').inner_text())
    inp.fill("120000")
    check(w + "10억원 넘으면 경고 줄", "10억원" in money.locator('[data-ui="money-warning"]').inner_text())
    fs = inp.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
    check(w + "입력칸 글자 16px 이상 (아이폰 확대 방지)", fs >= 16, str(fs))

    seg = page.locator('[data-ui="segmented"][aria-label="나눠 담는 방식"]')
    seg.get_by_role("radio", name="확신대로").click()
    check(w + "고르기 버튼: 확신대로 선택", seg.get_by_role("radio", name="확신대로").get_attribute("aria-checked") == "true" and
          "흔들림은 보지 않아요" in page.locator("[data-split-note]").inner_text())
    page.keyboard.press("ArrowLeft")
    check(w + "고르기 버튼: 화살표 키로 고르게 선택", seg.get_by_role("radio", name="고르게").get_attribute("aria-checked") == "true")

    col = page.locator('[data-ui="collapsible"]').first
    before = col.get_attribute("data-open")
    col.locator("button").first.click()
    check(w + "접는 섹션 열기", before == "0" and col.get_attribute("data-open") == "1")

    row = page.locator('[data-ui="list-row"]').first
    check(w + "목록 줄은 키보드로 갈 수 있어요", row.get_attribute("tabindex") == "0" and row.get_attribute("role") == "button")

    opener = page.locator("[data-open-sheet]")
    sheet = page.locator('[data-ui="bottom-sheet"]:not([data-inline])')
    dialog = sheet.locator('[role="dialog"]')
    opener.click()
    check(w + "시트가 열려요", dialog.is_visible())
    check(w + "열리면 포커스가 시트 안으로", page.evaluate("() => !!document.activeElement.closest('[role=dialog][aria-modal=true]')"))
    check(w + "열린 동안 뒤 화면 스크롤 멈춤", page.evaluate("() => document.body.style.overflow") == "hidden")
    inside = True
    for _ in range(8):
        page.keyboard.press("Tab")
        inside = inside and page.evaluate("() => !!document.activeElement.closest('[role=dialog][aria-modal=true]')")
    check(w + "Tab 으로 시트 밖에 나가지 않아요", inside)
    page.keyboard.press("Escape")
    check(w + "Esc 로 닫히고 포커스가 돌아와요", dialog.count() == 0 and
          page.evaluate("() => document.activeElement && document.activeElement.querySelector('[data-open-sheet]') !== null"))
    check(w + "닫히면 스크롤이 돌아와요", page.evaluate("() => document.body.style.overflow") != "hidden")

    opener.click()
    page.locator('[data-ui="bottom-sheet"]:not([data-inline]) button[aria-label="닫기"]').click()
    check(w + "X 로 닫혀요", dialog.count() == 0)

    opener.click()
    page.mouse.click(195, 20)          # 위쪽 어두운 곳
    check(w + "바깥을 누르면 닫혀요", dialog.count() == 0)

    opener.click()
    box = dialog.bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + box["height"] - 40)
    page.mouse.down()
    page.mouse.move(195, 10, steps=5)
    page.mouse.up()
    check(w + "시트 안에서 끌어 바깥에서 놓으면 닫히지 않아요", dialog.count() == 1 and dialog.is_visible())
    page.keyboard.press("Escape")

    page.set_viewport_size({"width": 320, "height": 300})
    opener.click()
    close = page.locator('[data-ui="bottom-sheet"]:not([data-inline]) button[aria-label="닫기"]')
    cb = close.bounding_box()
    check(w + "낮은 화면(320×300)에서도 닫기 버튼이 화면 안에 있어요", cb is not None and cb["y"] >= 0 and cb["y"] + cb["height"] <= 300, str(cb))
    close.click()
    page.set_viewport_size({"width": 390, "height": 844})

    tabs = page.locator('[data-ui="bottom-tab-bar"]').first
    tabs.get_by_role("button", name="덱 짜기").click()
    check(w + "아래 탭: 덱 짜기 선택", tabs.get_by_role("button", name="덱 짜기").get_attribute("aria-current") == "page")
    check(w + "찾기 탭은 아직 꺼져 있어요", tabs.locator('button[aria-label="찾기, 이 목업에는 없어요"]').is_disabled())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", help="스크린샷을 저장할 폴더")
    args = ap.parse_args()
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok)))
        print(("PASS " if ok else "FAIL ") + name + (f" · {detail}" if detail and not ok else ""))

    srv, base = serve()
    try:
        with sync_playwright() as pw:
            for width in (320, 390):
                run_width(pw, base, width, check, args.shots)
    finally:
        srv.shutdown()

    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} 통과")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
