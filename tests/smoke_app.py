#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""앱 스모크 테스트 — 사이트를 로컬에서 띄우고 헤드리스 크롬(휴대폰 크기 390×844)으로 눌러봐요.

  python tests/smoke_app.py                 # 저장소에 있는 JSON 으로
  python tests/smoke_app.py --data DIR      # DIR 의 data/corp/disc/macro.json 으로

확인하는 것: 첫 화면 검색으로 삼성전자·현대차 찾기 → 성적표, 모든 하단 탭 열기,
30초 진단·차근차근 만들기가 실제 시세(data.json)로 열리는지, 영어 모드, 페이지 오류 0건.
인터넷 요청(폰트·통계)은 막고 localhost 만 허용해요. 결과가 외부 사정에 흔들리지 않게요.
"""
import argparse
import functools
import http.server
import os
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_FILES = (["baepsae.html", "index.html", "manifest.webmanifest", "sw.js", "og.png", "icon-192.png", "icon-512.png"]
              + [f"baepi-{i}.png" for i in range(1, 10)])
DATA_FILES = ["data.json", "corp.json", "disc.json", "macro.json"]
WAIT = 20000  # ms


def build_site(data_dir):
    site = tempfile.mkdtemp(prefix="baepsae-smoke-")
    for f in SITE_FILES:
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy(os.path.join(ROOT, f), site)
    for f in DATA_FILES:
        shutil.copy(os.path.join(data_dir, f), site)
    return site


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(site):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def chromium_path():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=ROOT, help="data/corp/disc/macro.json 이 있는 폴더")
    ap.add_argument("--shots", default=None, help="실패 시 스크린샷을 저장할 폴더")
    args = ap.parse_args()

    site = build_site(args.data)
    srv, base = serve(site)
    results, errors = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path())
        # is_mobile 을 켜면 기업분석 화면이 폭 390px 보다 넓어(약 530px) 크롬이 화면을 축소하고,
        # 그러면 탭 클릭 좌표가 어긋나요. 그래서 크기만 휴대폰(390×844)으로 맞춥니다.
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))

        def see(text, timeout=WAIT):
            page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)

        def check(name, fn):
            try:
                fn()
                results.append((name, True, ""))
            except Exception as e:
                results.append((name, False, str(e).splitlines()[0][:160]))
                if args.shots:
                    os.makedirs(args.shots, exist_ok=True)
                    try:
                        page.screenshot(path=os.path.join(args.shots, f"fail-{len(results)}.png"), full_page=True)
                    except Exception:
                        pass
            print(f"  {'PASS' if results[-1][1] else 'FAIL'}  {name}", flush=True)

        def tab(label):
            page.locator("nav.botNav button", has_text=label).click()

        def home():
            tab("포트폴리오" if page.locator("nav.botNav button", has_text="포트폴리오").count() else "Portfolio")
            if page.get_by_text("모드 선택", exact=True).count():
                page.get_by_text("모드 선택", exact=True).click()
            if page.get_by_text("Back", exact=True).count():
                page.get_by_text("Back", exact=True).click()

        def search(q, code):
            box = page.get_by_placeholder("궁금한 종목이 있나요? — 이름 또는 코드")
            box.fill("")
            box.fill(q)
            page.locator("button", has_text=code).first.wait_for(state="visible", timeout=WAIT)

        def gate_samsung():
            search("삼성전자", "005930")
            page.locator("button", has_text="005930").first.click()
            see("사실의 요약일 뿐")

        def gate_hyundai():
            search("현대차", "005380")

        page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
        check("첫 화면이 열림", lambda: see("내 종목, 괜찮은 걸까요?"))
        check("검색: 삼성전자(005930) 찾기 → 성적표", gate_samsung)
        check("검색: 현대차(005380) 찾기", gate_hyundai)

        def open_tab(label, marker):
            def run():
                tab(label)
                see(marker)
            return run

        check("탭: 기업분석 (corp.json)", open_tab("기업분석", "시장 지도"))
        check("탭: 공시·수급 (disc.json)", open_tab("공시·수급", "내부자 거래"))
        check("탭: 금리·원자재 (macro.json)", open_tab("금리·원자재", "심화 — 채권·환율 연구실"))
        check("탭: 정보", open_tab("정보", "피드백"))
        check("탭: 포트폴리오", open_tab("포트폴리오", "내 종목, 괜찮은 걸까요?"))

        def close_welcome(label):
            # 처음 방문하면 '안녕하세요, 뱁이예요' 안내가 화면을 덮어요. 새 사용자처럼 닫습니다.
            btn = page.get_by_role("button", name=label, exact=True)
            try:
                btn.first.wait_for(state="visible", timeout=4000)
                btn.first.click()
            except Exception:
                pass

        def quick_ko():
            page.get_by_text("30초 진단", exact=True).click()
            close_welcome("시작하기")
            see("빠른 진단")

        def detail_ko():
            home()
            page.get_by_text("차근차근 만들기", exact=True).click()
            see("시세 데이터 기준일")  # data.json 을 읽었을 때만 나와요 (실패하면 '내장 데이터 사용 중')

        check("30초 진단 열림 (KO)", quick_ko)
        check("차근차근 만들기: 실제 시세로 열림 (KO)", detail_ko)

        def to_en():
            home()
            page.get_by_role("button", name="EN", exact=True).first.click()
            see("Is my stock doing okay?")

        def detail_en():
            page.get_by_text("Build step by step", exact=True).click()
            see("Data as of")

        def quick_en():
            home()
            page.get_by_text("30-second checkup", exact=True).click()
            see("Quick check")

        check("영어 모드 전환", to_en)
        check("차근차근 만들기: 실제 시세로 열림 (EN)", detail_en)
        check("30초 진단 열림 (EN)", quick_en)

        def back_ko():
            home()
            page.get_by_role("button", name="한국어", exact=True).first.click()
            see("내 종목, 괜찮은 걸까요?")

        check("한국어로 되돌리기", back_ko)
        page.wait_for_timeout(500)
        results.append(("페이지 오류 0건", not errors, "; ".join(errors)[:300]))
        browser.close()
    srv.shutdown()
    shutil.rmtree(site, ignore_errors=True)

    w = max(len(n) for n, _, _ in results)
    print(f"\n뱁새 스모크 테스트 결과 · 데이터: {os.path.abspath(args.data)}")
    for name, ok, msg in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(w)}  {msg}")
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)} / {len(results)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
