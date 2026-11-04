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
  빠진 종목   저장한 보유 종목(STRC)이 오늘 데이터에 없음 → ②③④·메모·CSV·JSON·카드에 '…(STRC 200만원)는 빼고 계산했어요',
              위험 계산에서 빠지되 예산 막대·머리말에는 회색으로, 저장본(localStorage)에는 남고, 데이터에 돌아오면 저절로 돌아옴,
              '포트폴리오에서 빼기'를 눌러야만 지워짐 · 전부 빠진 경우 · 고치기 카드·줄 삭제·직접 다시 담기 (v18.5)
  베타→수익률 펼친 종목 줄의 '이론 샤프', 프로필의 '목표 → 베타' 문장, 타임머신의 '끝까지 버텼다면', 위험 나누기 카드의
              '…기대수익으로 돌려받아요'가 없음, 목표 베타는 감당 능력 기준, 과거 값(샤프 3y·α·바닥)은 보임 (v18.5, KO·EN)
  서비스워커  예전 v10 워커의 얼어붙은 corp.json 이 새 워커로 바뀌고 baepsae-v10 캐시가 지워짐
  바로가기    (v19.0c) 2.0 이 여는 #macro · #disc · #corp=코드 · #info=glossary|sources → 그 탭 · 그 회사 · 그 카드, 주소의 # 은 지워지고
              기록이 늘지 않아요(뒤로 한 번이면 온 곳) · 그 뒤 NAV 뒤로 가기는 그대로 · 모르는 # 은 아무것도 안 해요
  2.0 링크    머리말 '뱁새 2.0 보기' (Jack, 2026-11-02): 320 · 390 에서 보임 · 누르는 높이 44 이상 · 다른 머리말 항목과 겹치지 않음 ·
              가로 스크롤 없음 · app.html 로 감 · 영어 화면에는 없음 · 좁은 휴대폰의 모드 안(홈 화면 '뒤로' 포함)에서도 머리말이 넘치지 않음
  파일        (v18.4.1) 'JSON 저장 (백업·공유)' 파일 → 새 브라우저에서 '저장한 파일에서 불러오기' → 같은 종목·금액·예산 ·
              종목 없는 파일 · 깨진 파일 · 줄이 모두 틀린 파일은 '파일을 읽을 수 없어요.' 알림만 (있던 포트폴리오 그대로) · 예전 모양 파일도 열림
  자동 설정   (v18.6) 설정의 '자동' 칸(환율 · 시장 가정)은 저장본을 다시 열 때도 파일을 불러올 때도 오늘 값 · 직접 입력한 칸만 저장된 값('가정') ·
              JSON 저장 → 새 브라우저에서 불러와도 그대로 · 직접 입력 기록이 없는 예전 저장본 · 파일은 오늘 값 (console 에 바꾼 개수) ·
              (v18.6.1) '새로 시작하기' · 읽을 설정이 없는 파일은 기본값 + 오늘 값 (앞 포트폴리오의 설정을 잇지 않아요)
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
SITE_FILES = (["baepsae.html", "index.html", "manifest.webmanifest", "sw.js", "og-v19.png", "icon-192.png", "icon-512.png"]
              + [f"baepi-{i}.png" for i in range(1, 10)])
DATA_FILES = ["data.json", "corp.json", "disc.json", "macro.json"]
WAIT = 20000  # ms
LOAD_FAIL = "데이터를 불러오지 못했어요"
NONLIVE = "일부 종목은 최신 시세가 아니라 예시 가격이에요"          # 일부만 내장 예시 가격
NOLIVE_ALL = "최신 시세를 불러오지 못해 예시 가격으로 보여 드려요"    # data.json 을 못 읽어 전부 예시
GOLD_EST = "금현물은 국제 금값으로 환산한 추정치예요"
RATES_FAIL = "금리 데이터를 불러오지 못했어요"
OFFICIAL = "공식 종가예요. 다른 수치는 추정치예요"
NORISK = "베타·변동성 자료가 없어요. 위험 수치는 나머지 종목으로 계산했어요"
RISK_BLIND = "담은 종목 모두 베타·변동성 자료가 없어 위험 수치를 계산할 수 없어요"
RISK_HALF = "베타·변동성 자료가 없는 종목이 투자금의 절반을 넘어 위험 수치를 계산할 수 없어요"
DY_UNKNOWN = "배당 정보가 없는 종목 {n}개는 0원으로 계산했어요."
MISSING = "오늘 데이터에 없는 종목 {n}개({names})는 빼고 계산했어요."      # v18.5 (Jack 승인 2026-11-04), names = 'STRC 200만원, …'
MISSING_EN = "Left out {n} stock(s) not in today's data ({names})."      # v18.5 승인 · 금액은 앱의 영어 금액 모양 그대로 (₩2,000,000)
MISSING_REMOVE = "포트폴리오에서 빼기"                                     # v18.5 승인 (영어 'Remove from portfolio' 도 승인)
BAR_LEGEND = {"ko": "데이터에 없는 종목", "en": "Not in today's data"}    # 예산 막대 회색 칸 이름표 (v18.5 승인, 2026-11-04)
# 이름표가 회색 칸 바로 아래에서 시작하는지 (왼쪽 끝 차이, px) — 칸이 오른쪽 끝에 가까우면 오른쪽 정렬이라 None
LEGEND_POS = """() => { const g = document.querySelector('[data-bar="missing"]'), l = document.querySelector('.barLegend');
  if (!g || !l) return null; const s = l.querySelector('span'); return [l.innerText.trim(), Math.round(s.getBoundingClientRect().left - g.getBoundingClientRect().left)]; }"""
# 예산 막대의 칸 너비(%): 계산에 든 금액 · 오늘 데이터에 없어 뺀 금액(회색)
BAR = """() => { const b = document.querySelector('.budgetBar'); if (!b) return null; const W = b.getBoundingClientRect().width;
  const w = (k) => { const e = b.querySelector('[data-bar="' + k + '"]'); return e ? Math.round(e.getBoundingClientRect().width / W * 1000) / 10 : null; };
  return { counted: w('counted'), missing: w('missing') }; }"""
# 가장 작은 요소의 글: 그 줄만 정확히 보려고 (부모 상자의 글이 섞이지 않게)
SMALLEST = """(args) => { const [need, also] = args; let best = null;
  for (const e of document.querySelectorAll('body *')) { const t = e.innerText || '';
    if (t.includes(need) && (!also || also.every((x) => t.includes(x))) && (!best || t.length < best.length)) best = t; }
  return best; }"""
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

    def open(self, site, sw=False, local=None, once=False):
        srv, base = serve(site)
        # is_mobile 을 켜면 기업분석 화면이 폭 390px 보다 넓어(약 530px) 크롬이 화면을 축소하고,
        # 그러면 탭 클릭 좌표가 어긋나요. 그래서 크기만 휴대폰(390×844)으로 맞춥니다.
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR",
                                       service_workers="allow" if sw else "block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        if local:
            # once=True: 처음 열 때만 심어요 (다시 불러와도 앱이 저장한 값을 덮어쓰지 않게 — 저장본이 남는지 볼 때)
            ctx.add_init_script("(() => { try { const kv = %s; for (const k in kv) %slocalStorage.setItem(k, kv[k]); } catch (e) {} })();"
                                % (json.dumps(local, ensure_ascii=False), "if (localStorage.getItem(k) === null) " if once else ""))
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
            self.results.append((label, False, ((str(e).splitlines() or [repr(e)])[0])[:160]))   # 글 없는 assert 도 이름이 남게
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


# v19.0 (Jack, 2026-11-03): 푸터에는 만든 사람 줄 대신 2.0 의 소개 페이지로 가는 '소개' 링크 (src/links.js)
ABOUT_HREF = "./app.html#about"
GONE = ["INSEAD", "이성진", "황새 말고, 내 걸음으로", "개인 투자 연구소", "Not the stork's pace", "At my own pace"]


def about_footer(page, label="소개"):
    """이 화면의 푸터: '소개'(영어 화면은 'About') 링크가 ./app.html#about 으로, 만든 사람 줄 · 예전 캐치프레이즈 없음."""
    links = page.locator("a[data-about-link]")
    links.first.wait_for(state="attached", timeout=WAIT)
    for i in range(links.count()):
        assert links.nth(i).inner_text() == label and links.nth(i).get_attribute("href") == ABOUT_HREF, (label, links.nth(i).inner_text())
    body = page.locator("body").inner_text()
    found = [w for w in GONE if w in body]
    assert not found, found


# ── 장면 ────────────────────────────────────────────────────
def scene_normal(R, files, full):
    site = build_site(files)
    srv, ctx, page, _ = R.open(site)
    S = "정상"
    R.check(page, S, "첫 화면이 열림", lambda: see(page, "내 종목, 괜찮은 걸까요?"))

    def gate_footer():
        about_footer(page)
        body = page.locator("body").inner_text()
        assert "교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다. · 소개" in body
        assert "종목 하나로 5초 성적표부터 — 철새처럼 옮겨 다니지 않는 투자" in body
    R.check(page, S, "첫 화면 푸터: 고지문 · '소개'(./app.html#about), 만든 사람 줄 없음 · 새 캐치프레이즈", gate_footer)

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
            about_footer(page)                                     # 탭마다 푸터: 소개 링크, 만든 사람 줄 없음 (v19.0)
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
        about_footer(page)           # 차근차근 만들기 푸터: 캐치프레이즈 · 고지문 · 소개 (만든 사람 줄 없음)
        assert "철새처럼 옮겨 다니지 않는 투자" in page.locator("body").inner_text()
    R.check(page, S, "차근차근 만들기: 실제 시세 + 기준 날짜 + 공식 종가 안내 (KO)", detail_ko)

    def to_en():
        home(page)
        page.get_by_role("button", name="EN", exact=True).first.click()
        see(page, "Is my stock doing okay?")
        about_footer(page, "About")                                # 영어 화면의 푸터 링크는 About
    R.check(page, S, "영어 모드 전환", to_en)

    def detail_en():
        page.get_by_text("Build step by step", exact=True).click()
        page.locator(".dateBadge", has_text="As of").first.wait_for(state="visible", timeout=WAIT)
        see(page, "Prices are official closes from")
        about_footer(page, "About")
        assert "Don't hop from trend to trend" in page.locator("body").inner_text()
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


def scene_no_risk_holding(R, files):
    """내장 목록에 없고 베타·변동성이 빈 종목을 담은 포트폴리오: 사라지지 않고, β 는 '–', 위험 숫자에 NaN 없음, 배너 안내."""
    f = json.loads(json.dumps(files, allow_nan=True))
    f["data.json"]["stocks"].append({"t": "999990", "nk": "시험새종목", "ne": "Test New Co", "cls": "kr", "s": "bank",
                                     "price": 12000, "beta": None, "vol": None, "per": None, "pbr": None, "dy": None,
                                     "cap": 3.1, "val": 120.0})
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000,
            "holdings": [{"t": "999990", "mw": 200}, {"t": "005930", "mw": 300}]}
    blind = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "999990", "mw": 300}]}
    half = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "999990", "mw": 200}, {"t": "005930", "mw": 100}]}
    ref = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "005930", "mw": 500}]}
    local = {"baepsae_v9_seen": "1",
             "baepsae_v10_slots": json.dumps([{"id": "snr", "name": "위험값 없음 시험"}, {"id": "sbl", "name": "위험값 전부 없음"},
                                              {"id": "shf", "name": "위험값 절반 넘게 없음"}, {"id": "srf", "name": "삼성전자만 비교"}],
                                             ensure_ascii=False),
             "baepsae_v10_slot_snr": json.dumps(slot, ensure_ascii=False), "baepsae_v10_slot_sbl": json.dumps(blind, ensure_ascii=False),
             "baepsae_v10_slot_shf": json.dumps(half, ensure_ascii=False), "baepsae_v10_slot_srf": json.dumps(ref, ensure_ascii=False)}
    srv, ctx, page, _ = R.open(build_site(f), local=local)

    risk_line = {}

    def run():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("위험값 없음 시험", exact=False).first.click()
        see(page, NORISK)
        see(page, "(비중 40%)")                    # 200 / 500 만원 = 40%
        see(page, "보통 해 ±")
        row = page.evaluate(SMALLEST, ["시험새종목", ["비중 ", "β "]])
        assert row and "β –" in row and "비중 40.0%" in row, f"장바구니 줄: {row!r}"     # 그 종목 줄에서 직접
        risk_line["partial"] = page.evaluate(SMALLEST, ["보통 해 ±", None])
        body = page.locator("body").inner_text()
        assert "NaN" not in body and "null" not in body, "위험 수치에 NaN/null 이 보여요"
    R.check(page, "위험값 없음", "베타·변동성 없는 종목을 담음 → 그 줄에 'β –'·비중 40%, 배너, NaN 없음", run)
    ctx.close(); srv.shutdown()

    srv, ctx, page, _ = R.open(build_site(f), local=local)

    def same_as_reference():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("삼성전자만 비교", exact=False).first.click()
        see(page, "보통 해 ±")
        ref_line = page.evaluate(SMALLEST, ["보통 해 ±", None])
        assert risk_line.get("partial") and ref_line == risk_line["partial"], f"{risk_line.get('partial')!r} ≠ {ref_line!r}"
    R.check(page, "위험값 없음", "자료 없는 200만원 + 삼성전자 300만원 = 삼성전자 500만원과 같은 위험 수치", same_as_reference)
    ctx.close(); srv.shutdown()

    srv, ctx, page, _ = R.open(build_site(f), local=local)

    def run_blind():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("위험값 전부 없음", exact=False).first.click()
        see(page, RISK_BLIND)
        see(page, "시험새종목")                    # 담은 종목은 그대로 보여요
        page.wait_for_timeout(500)
        body = page.locator("body").inner_text()
        # 화면 전체가 아니라 포트폴리오 쪽만 봐요: 실제 종목 목록에는 베타가 정말 0.00 인 종목(거래정지 등)이 있어요
        for bad in ("보통 해", "변동성 0.0%", "비중 0.0%", "NaN", "null"):
            assert bad not in body, f"위험 수치를 못 만드는데 '{bad}' 가 보여요"
        row = page.evaluate(SMALLEST, ["시험새종목", ["비중 ", "β "]])
        assert row and "비중 100.0%" in row and "β –" in row, f"장바구니 줄: {row!r}"
        assert page.get_by_text(NORISK).count() == 0, "전부 빠졌는데 '일부 종목' 문구"
    R.check(page, "위험값 없음", "담은 종목 모두 베타·변동성 없음 → 위험 수치 대신 안내, 비중은 그대로, 0·NaN 없음", run_blind)
    ctx.close(); srv.shutdown()

    srv, ctx, page, _ = R.open(build_site(f), local=local)

    def run_half():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("위험값 절반 넘게 없음", exact=False).first.click()
        see(page, RISK_HALF)                       # 200 / 300 = 67% > 50% → 계산 안 함 ('모두' 문구 아님)
        page.wait_for_timeout(500)
        body = page.locator("body").inner_text()
        assert "보통 해" not in body and RISK_BLIND not in body and "NaN" not in body, "절반 넘게 빠졌는데 위험 수치/잘못된 문구"
    R.check(page, "위험값 없음", "자료 없는 종목이 투자금의 절반 넘음 → 위험 수치 대신 안내", run_half)
    ctx.close(); srv.shutdown()

    # 모든 자산군(한국·미국·채권·금)을 담은 보통 포트폴리오: 위험 숫자에 NaN 이 없어야 해요
    # (v15.3 부터 채권 칸이 빠져 모든 포트폴리오가 '±NaN만원'으로 보였어요 — v17.5 에서 발견)
    have = {s.get("t") for s in files["data.json"]["stocks"]}
    pick = [t for t in ("005930", "AAPL", "153130", "114260", "132030") if t in have]
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": t, "mw": 150} for t in pick]}
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "sall", "name": "자산군 모두 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_sall": json.dumps(slot, ensure_ascii=False)}
    srv, ctx, page, _ = R.open(build_site(files), local=local)

    def all_classes():
        assert len(pick) >= 3, f"시험할 종목이 부족해요: {pick}"
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("자산군 모두 시험", exact=False).first.click()
        see(page, "보통 해")
        page.wait_for_timeout(500)
        body = page.locator("body").inner_text()
        assert "NaN" not in body, "포트폴리오 숫자에 NaN: " + next((ln for ln in body.splitlines() if "NaN" in ln), "")
    R.check(page, "위험값 없음", f"자산군 모두 담은 포트폴리오 ({', '.join(pick)}) → NaN 없음", all_classes)
    ctx.close(); srv.shutdown()


# B안 (Jack 2026-11-01): NaN 고친 뒤 처음 켜지는 판정·조언·예측 문구는 v18 전까지 보이지 않아야 해요 (src/flags.js)
HIDDEN_B = ["기대 +", "적정 기대수익", "세후 기대수익", "기대수익(연", "기대수익률", "E(r)", "복리 수익률", "위험 대비 효율",
            "건강 점수", "베타가 목표보다", "변동성이 상한을 넘어요", "비중만 옮겨서 베타", "늘려 출렁임 낮추기",
            "모든 계기가 초록불이에요", "남은 예산이 맞춰야 할", "남은 예산만으론", "닿을 수 있어요", "이럴 바엔 인덱스 펀드",
            "비중을 줄이는 효과가 가장 커요", "더 나눠 담으면", "비중만 고르게 나눠도", "내 그릇에 맞는 베타를 지켰어요",
            "할 일의 전부예요", "목표까지 갈 수 있을까요", "내 수익은 어디서 나오나요", "원금을 지킬 확률", "원금을 지킬 수 있을까",
            "손실로 끝날 확률", "목표 달성 확률", "보상받지 못한 변화", "값을 치르고 산 위험", "위험을 줄이셨네요",
            "유지하는 것도 훌륭한 선택",
            # v18.4 (Jack 2026-11-03): 기대수익으로 만든 나머지 예측 — VaR·CVaR·2008년급 줄과 그 설명, 미국 매매차익 세금
            "나쁜 해 (하위 5% 경계", "그보다 나쁠 때 평균", "2008년급 (시장", "꼬리가 두꺼워요", "이 금액들을 보고도", "해외주식 양도소득세",
            # v18.5 (Jack 2026-11-03): 베타를 수익률로 바꾸는 줄 — 펼친 종목 줄의 이론 샤프(β × 프리미엄 ÷ σ),
            # 프로필의 '목표는 연 X%라서, 베타 …' · '… 기대하기 어려운 수치예요' · '베타 Y 정도면 충분해요'
            "이론 샤프", "%라서, 베타", "기대하기 어려운 수치", "정도면 충분해요",
            # v18.5 (Jack 2026-11-04): 타임머신의 '끝까지 버텼다면 +Y%'와 '버틴 값어치', 위험 나누기 카드의 '…기대수익으로 돌려받아요'
            "끝까지 버텼다면", "버틴 값어치", "기대수익으로 돌려받아요",
            "NaN"]
# ('초록 구간 = 내 프로필의 목표' 는 남아요: 분산·업종 계기에는 목표 구간이 그대로 있어요. β·σ 계기에서만 구간을 지워요.)
HIDDEN_B_EN = ["expected +", "Expected return", "E(r)", "CAGR", "After-tax return", "Fair E(r)", "Portfolio health", "health score",
               "Beta above target", "Beta below target", "Volatility over ceiling", "All gauges green", "remaining budget",
               "Remaining budget", "Will I reach the goal", "Where do my returns come from", "An index fund would be cheaper",
               "Raise cash to", "odds of keeping your principal", "Will the principal survive", "Chance of ending in loss",
               "Chance of reaching the goal", "Same stocks, evened weights", "helps most", "Three more non-overlapping",
               "Beta matches your capacity", "uncompensated change", "risk you actually got paid for", "You cut risk",
               "holding steady is a fine choice",
               "Bad year (5% VaR)", "Average beyond it (CVaR)", "2008-scale (market", "fatter tails", "stay the course — which",
               "Foreign capital gains",
               "CAPM Sharpe", "goal, aim for beta", "is hard to expect from the risk you can carry", "goal only needs about beta",   # v18.5
               "If you held to the end", "What holding was worth", "pays you back as expected return",                          # v18.5
               "NaN"]
TEAL, TEAL_SOFT, INK = "rgb(46, 158, 143)", "rgb(228, 244, 241)", "rgb(28, 43, 69)"   # src/tokens.js (C.teal, C.tealSoft, C.ink)


def hidden_shown(body, words):
    """보이면 안 되는 문구 목록(먼저) + 그 앞뒤 글자 (어디서 나왔는지 바로 알 수 있게). 없으면 빈 문자열."""
    hit = [(h, body.find(h)) for h in words if h in body]
    if not hit:
        return ""
    ctx = [f"…{body[max(0, i - 25):i + len(h) + 25]}…".replace("\n", " / ") for h, i in hit]
    return f"{[h for h, _ in hit]} · {ctx}"


def scene_option_b(R, files):
    """균형형 프로필(변동성 상한 24%) + 변동성 큰 실제 종목 4개(업종 3곳, 비중 제각각) + 지난달 점검 기록:
    예전 계산이면 '변동성이 상한을 넘어요' 경고, 고치기 카드, 기대수익, 건강 점수, β·σ 초록 구간이 다 떠요.
    B안에서는 위험 수치(보통 해 ±…)만 보이고, 나머지는 첫 화면·②③④ 어디에도, 한국어·영어 어느 쪽에도 없어야 해요."""
    files = json.loads(json.dumps(files))      # 아래에서 배당만 지워요 (다른 장면에 번지지 않게 복사본에서)
    stocks = {s.get("t"): s for s in files["data.json"]["stocks"]}
    want = [("000660", 400), ("005930", 150), ("005380", 100), ("105560", 100)]
    hold = [(t, mw) for t, mw in want if t in stocks and isinstance(stocks[t].get("vol"), (int, float))]
    secs = {stocks[t].get("s") for t, _ in hold}
    assert len(hold) == 4 and len(secs) >= 3, f"시험할 종목이 모자라요: {hold} · 업종 {secs}"
    stocks[hold[0][0]]["dy"] = None     # 배당 정보 없음 → '배당 정보가 없는 종목 1개는 0원으로 계산했어요.' 가 보여야 해요
    profile = {"ready": True, "targetBetaMin": 0.7, "targetBetaMax": 1.1, "targetVolMaxPct": 24, "stocksMin": 8, "stocksMax": 15,
               "maxPositionPct": 100, "maxSectorPct": 100, "cashFloorPct": 0, "riskNeedPct": 7, "riskCapacity": 6, "riskTolerance": 6}
    old = {"d": "2026-10-01", "inv": 5000000, "beta": 0.9, "vol": 30.0, "exp": 8.0, "unpaid": 30.0, "sec": 50.0,
           "secKey": "x", "top3": 80.0, "n": 3}       # 지난번 점검 (숫자가 달라서 변화 칸이 채워져요)
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "profile": profile, "checkins": [old],
            "holdings": [{"t": t, "mw": mw} for t, mw in hold]}
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "sob", "name": "B안 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_sob": json.dumps(slot, ensure_ascii=False)}
    srv, ctx, page, _ = R.open(build_site(files), local=local)

    def body():
        page.wait_for_timeout(600)
        return page.locator("body").inner_text()

    def stage(label):
        page.get_by_role("button", name=label, exact=False).first.click()

    def open_if(text):
        if page.get_by_text(text, exact=False).count():
            page.get_by_text(text, exact=False).first.click()

    def gate():
        see(page, "지금 보유 종목을 넣으면 쏠림과 출렁임을 바로 보여 줘요. 기본 성향으로 시작해요.")   # Jack 승인 문구 (2026-11-01)
        shown = hidden_shown(body(), HIDDEN_B)
        assert not shown, f"첫 화면에 보이면 안 되는 문구: {shown}"
    R.check(page, "B안", "첫 화면: 30초 진단 소개에 '건강 점수' 없음", gate)

    def build():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("B안 시험", exact=False).first.click()
        see(page, "보통 해 ±")
        open_if("이렇게 하면 맞춰져요")        # 접힌 고치기 카드 목록도 펼쳐서 읽어요
        shown = hidden_shown(body(), HIDDEN_B)
        assert not shown, f"② 구성에 보이면 안 되는 문구: {shown}"
        line = page.evaluate(SMALLEST, ["보통 해 ±", None])
        assert line and "기대" not in line and "NaN" not in line, f"위험 줄: {line!r}"
        # 계기판의 초록 목표 구간은 분산·업종 두 개만 (β·σ 에는 없어야 해요)
        zones = page.evaluate("""([teal, soft]) => [...document.querySelectorAll('div')].filter((d) => { const c = getComputedStyle(d);
            return c.height === '9px' && c.borderTopColor === teal && c.backgroundColor === soft; }).length""", [TEAL, TEAL_SOFT])
        assert zones == 2, f"초록 목표 구간 {zones}개 (분산·업종 2개여야 해요)"
    R.check(page, "B안", "② 구성: '보통 해 ±…' 만, β·σ 초록 구간·판정·조언·기대수익·건강 점수 없음", build)

    def open_all(titles, detail):
        for title in titles:
            page.get_by_text(title, exact=False).first.click()     # 접힌 섹션을 모두 열어요
        page.wait_for_timeout(400)
        page.get_by_text(detail, exact=False).first.click()          # 종목별 줄도 열어요 (예전엔 '적정 기대수익 x%')

    def colors():
        # β·σ 변화는 좋고 나쁨 색 없이 (잉크색): 점검 기록의 변동성 줄, 1/N 상자의 β·σ
        ci = page.evaluate("""() => { const row = [...document.querySelectorAll('div')].find((d) => d.children.length === 4
            && d.children[0].textContent === '변동성 (연)'); return row ? [row.children[3].textContent, getComputedStyle(row.children[3]).color] : null; }""")
        assert ci and ci[0] != "–" and ci[1] == INK, f"점검 기록 변동성 변화: {ci}"
        one = page.evaluate("""() => { const box = [...document.querySelectorAll('div')].find((d) => d.children.length >= 2
            && d.children[0].textContent === '같은 종목을 그냥 1/N씩 담았다면'); if (!box) return null;
            return [...box.children[1].children].map((c) => [c.children[0].textContent, c.children[2].textContent, getComputedStyle(c.children[2]).color]); }""")
        assert one, "1/N 상자가 없어요"
        bs = [c for c in one if c[0] in ("β", "σ")]
        assert len(bs) == 2 and all(c[2] == INK or c[1].strip() in ("0.00", "+0.00", "0.0%p") for c in bs), f"1/N β·σ 색: {one}"
        assert any(c[1].strip() not in ("0.00", "+0.00", "0.0%p", "-0.00") for c in bs), f"1/N 변화가 0 이라 색을 못 봐요: {one}"

    def diag():
        stage("③ 진단")
        see(page, "내가 잘하고 있는 것")
        open_all(("내가 잘하고 있는 것", "내 위험은 보상받고 있나요?", "나는 무엇을 들고 있나요?", "폭락하면 얼마나 잃나요?",
                  "시장을 이길 수 있을까요?", "직접 실험해볼까요?"), "종목별로 뜯어보기")
        see(page, "2026-10-01")                 # 심어 둔 지난 점검과 비교 중
        see(page, "내 종목들의 3년 최대낙폭")      # 폭락 섹션: 지난 3년 실제 값은 남아요 (v18.4)
        see(page, "과거 3년 알파 (추정)")          # 알파는 과거 값으로만 남아요 (v18.5: 베타→수익률만 가려요)
        shown = hidden_shown(body(), HIDDEN_B)
        assert not shown, f"③ 진단에 보이면 안 되는 문구: {shown}"
        colors()
        # '그래서, 뭘 하면 좋을까요?' 상자는 줄이 하나라도 있을 때만 (업종 3곳 이상이면 남는 줄이 없어서 상자도 없어야 해요)
        empty = page.evaluate("""() => [...document.querySelectorAll('div')].filter((d) => d.textContent.trim() === '그래서, 뭘 하면 좋을까요?')
            .some((d) => d.parentElement.innerText.trim().length < d.textContent.trim().length + 5)""")
        assert not empty, "빈 '그래서, 뭘 하면 좋을까요?' 상자"
        page.get_by_role("button", name="지금 상태 기록").first.click()   # 오늘 점검도 기록해 봐요
        see(page, "2번째 기록")
        shown = hidden_shown(body(), HIDDEN_B)
        assert not shown, f"③ 점검 기록 뒤 보이면 안 되는 문구: {shown}"
    R.check(page, "B안", "③ 진단: 섹션을 다 열고 점검 기록을 비교해도 판정·조언·기대수익·건강 점수 없음, β·σ 변화는 잉크색", diag)

    def div_unknown():
        # 배당 합계가 보이는 곳(간단 사실 카드)에 '0원으로 계산' 알림도 같이 있어야 해요 (조용히 0원 X)
        see(page, DY_UNKNOWN.replace("{n}", "1"))
        assert page.get_by_text("연 배당 (예상·세전)", exact=False).count() > 0, "배당 합계 줄이 없어요"
    R.check(page, "B안", "③ 진단: 배당 정보 없는 종목 → '0원으로 계산했어요' 알림", div_unknown)

    def export_ko():
        stage("④ 내보내기")
        see(page, "예상 세금")
        see(page, "해외 배당 원천징수")             # 배당 세금 줄은 남아요 (v18.4: 미국 매매차익 추정 줄만 빠져요)
        shown = hidden_shown(body(), HIDDEN_B)
        assert not shown, f"④ 내보내기에 보이면 안 되는 문구: {shown}"
    R.check(page, "B안", "④ 내보내기: 세후·세전 기대수익 없음", export_ko)

    def english():
        page.get_by_role("button", name="EN", exact=True).first.click()
        see(page, "④ Export")
        bad = hidden_shown(body(), HIDDEN_B_EN)
        stage("② Build")
        see(page, "a typical year swings")
        open_if("How to bring it in line")
        bad += hidden_shown(body(), HIDDEN_B_EN)
        stage("③ Diagnose")
        see(page, "What I'm doing right")
        open_all(("What I'm doing right", "Is my risk being paid for?", "What am I actually holding?", "How much would a crash cost?",
                  "Can I beat the market?", "Want to experiment?"), "Per-stock breakdown")
        bad += hidden_shown(body(), HIDDEN_B_EN)
        home(page)
        see(page, "30-second checkup")
        bad += hidden_shown(body(), HIDDEN_B_EN)
        assert not bad, f"영어 화면에 보이면 안 되는 문구: {bad}"
    R.check(page, "B안", "영어 첫 화면·②③④: 판정·조언·기대수익·건강 점수 없음", english)
    ctx.close(); srv.shutdown()


def scene_simple_no_forecast(R, files):
    """성향 테스트(간단 모드, src/simple.jsx)의 '뱁이의 진단'(저장해 둔 마지막 단계)에서 기대수익으로 만든 '아주 나쁜 해' 줄과 '10년 뒤 전망' 카드가 없어요
    (B안, v18.4 · Jack 2026-11-03). 위험 수준 카드와 다른 카드는 그대로예요."""
    saved = {"step": 6, "ans": {"goal": "grow", "horizon": 10, "crash": "hold", "emergency": "enough"}, "eq": 60, "krShare": 0.5,
             "goldOn": True, "amountMw": 1000}
    srv, ctx, page, _ = R.open(build_site(files), local={"baepsae_v9_seen": "1", "baepsae_v11_simple": json.dumps(saved, ensure_ascii=False)})

    def run():
        close_welcome(page, "시작하기")
        page.get_by_text("성향 테스트로 시작", exact=True).click()
        see(page, "뱁이의 진단")
        see(page, "지금 위험 수준")
        see(page, "잘하고 있는 점")
        see(page, "더 깊이 보고 싶다면")
        shown = hidden_shown(page.locator("body").inner_text(),
                             ["10년 뒤 전망", "아주 나쁜 해에는", "아쉬운 경우", "가운데쯤", "10년 두었을 때", "NaN"])
        assert not shown, f"성향 테스트 결과에 보이면 안 되는 문구: {shown}"
    R.check(page, "B안", "성향 테스트 '뱁이의 진단': 아주 나쁜 해 줄 · 10년 뒤 전망 없음, 다른 카드는 그대로", run)
    ctx.close(); srv.shutdown()


# 안내 줄이 아닌 곳(목록 줄)에 need 와 also 가 같이 있는지: 안내를 품은 큰 상자는 skip 글자로 빼요
ROW_WITH = """([need, also, skip]) => [...document.querySelectorAll('body *')].some((e) => { const t = e.innerText || '';
  return t.includes(need) && t.includes(also) && !t.includes(skip); })"""


def slot_local(slots):
    """slots: [(id, 이름, 저장 내용)] → localStorage 에 심을 값."""
    local = {"baepsae_v9_seen": "1",
             "baepsae_v10_slots": json.dumps([{"id": i, "name": n} for i, n, _ in slots], ensure_ascii=False)}
    for i, _, body in slots:
        local["baepsae_v10_slot_" + i] = json.dumps(body, ensure_ascii=False)
    return local


def read_slot(page, sid):
    raw = page.evaluate("(k) => localStorage.getItem(k)", "baepsae_v10_slot_" + sid)
    return json.loads(raw) if raw else None


def scene_missing_holding(R, files):
    """v18.5 (Jack 2026-11-03): 저장한 보유 종목이 오늘 데이터에 없으면(다음 갱신 뒤 STRC·SKHY·GOOGM·GOOGN 처럼)
    위험 계산·목록에서 빼고 ②③④·메모·CSV·JSON·공유 카드에 '오늘 데이터에 없는 종목 1개(STRC 200만원)는 빼고 계산했어요.' 를 보여요.
    예산은 입력한 그대로 맞아떨어져요: 머리말 '500 + 200 / 1,000', 막대 50% + 회색 20%, 남는 현금 300만원, 메모·JSON 의 예산 1,000만원.
    저장본에서는 지우지 않아요: 앱이 다시 저장해도 localStorage 에 STRC 가 남고, 데이터에 돌아오면 저절로 다시 계산돼요.
    내장 예시 목록에만 있는 금현물(예시 가격 배너)은 '빠진 종목'으로 세지 않아요 (두 안내가 같은 종목을 두 번 세지 않게)."""
    f = json.loads(json.dumps(files, allow_nan=True))
    stocks = f["data.json"]["stocks"]
    strc = next((s for s in stocks if s.get("t") == "STRC"), None) or {
        "t": "STRC", "nk": "Strategy Inc 시험", "ne": "Strategy Inc test", "cls": "us", "s": "platform", "ccy": "USD",
        "price": 99.0, "beta": 0.5, "vol": 20.0}
    have = {s.get("t") for s in stocks}
    assert {"005930", "000660"} <= have, "시험할 종목(삼성전자·SK하이닉스)이 데이터에 없어요"
    f["data.json"]["stocks"] = [s for s in stocks if s.get("t") not in ("STRC", "04020000")]   # STRC 는 빠지고, 금현물은 내장 예시로
    hold = [{"t": "STRC", "mw": 200}, {"t": "005930", "mw": 300}, {"t": "000660", "mw": 100}, {"t": "04020000", "mw": 100}]
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": hold}
    # 비교: STRC 없이 같은 종목, 예산은 STRC 200만원을 뺀 800만원 → 위험 줄·현금이 똑같아야 해요 (빠진 돈은 현금이 아니에요)
    ref = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 800, "holdings": hold[1:]}
    local = slot_local([("smiss", "빠진 종목 시험", slot), ("sref", "빠진 종목 비교", ref)])
    site = build_site(f)
    R.console.clear()
    srv, ctx, page, _ = R.open(site, local=local, once=True)    # 다시 불러와도 앱이 저장한 값을 덮어쓰지 않게
    S = "빠진 종목"
    note = MISSING.format(n=1, names="STRC 200만원")
    line = {}

    def stage(label):
        page.get_by_role("button", name=label, exact=False).first.click()

    def build():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("빠진 종목 시험", exact=False).first.click()
        see(page, "보통 해 ±")
        see(page, note)
        see(page, NONLIVE)                                    # 금현물: 예시 가격 배너는 그대로 (빠진 종목 안내와 따로)
        # 입력한 예산 1,000 = 계산에 든 500(300 + 100 + 100) + 빠진 STRC 200(회색) + 남는 현금 300 (Jack 2026-11-04)
        head = page.locator(".cartHead").inner_text()
        assert head.startswith("500 + 200 / 1,000"), f"머리말이 예산과 맞지 않아요: {head!r}"
        bar = page.evaluate(BAR)
        assert bar and abs(bar["counted"] - 50) < 1 and abs(bar["missing"] - 20) < 1, f"예산 막대: {bar}"
        cash = page.evaluate(SMALLEST, ["남는 현금 (무위험)", ["만원"]])
        assert cash and "300만원" in cash, f"빠진 종목의 돈이 현금으로 잡혔어요: {cash!r}"                  # 1,000 − 500 − 200
        assert page.get_by_text("예산 초과").count() == 0, "예산 안인데 '예산 초과'"
        leg = page.evaluate(LEGEND_POS)
        assert leg and leg[0] == BAR_LEGEND["ko"] and abs(leg[1]) <= 2, f"회색 칸 이름표: {leg}"
        assert page.locator(".missingRemove", has_text=MISSING_REMOVE).count() == 1, "'포트폴리오에서 빼기' 버튼이 없어요"
        assert any("계산에서 뺀 보유 종목 1개: STRC" in m for _, m in R.console), "빠진 종목을 console 에 크게 남기지 않았어요"
        assert not page.evaluate(ROW_WITH, ["STRC", "비중 ", "빼고 계산했어요"]), "빠진 STRC 가 목록 줄로 보여요"
        assert page.get_by_text("예시 포트폴리오로 둘러보기").count() == 0, "예시 버튼이 보여요"
        body = page.locator("body").inner_text()
        assert body.count("빼고 계산했어요") == 1 and "2개(" not in body, "안내가 두 번 또는 금현물까지 세었어요"
        line["miss"] = page.evaluate(SMALLEST, ["보통 해 ±", None])
    R.check(page, S, "② 구성: 안내 'STRC 200만원' · 머리말 500 + 200 / 1,000 · 막대 50%+회색 20% + 그 아래 '데이터에 없는 종목' · 현금 300만원 · STRC 줄 없음 · 금현물 배너는 따로 · console 경고", build)

    def diag():
        stage("③ 진단")
        see(page, "내가 잘하고 있는 것")
        see(page, note)
        page.get_by_text("나는 무엇을 들고 있나요?", exact=False).first.click()
        cash = poll(page, "(" + SMALLEST + ")(['현금 비중', ['%']])", bool, "현금 비중 줄이 없어요")
        assert cash.replace("\n", " ").endswith("30%"), f"현금 비중이 예산 1,000만원 기준(30%)이 아니에요: {cash!r}"
    R.check(page, S, "③ 진단: 같은 안내 · 현금 비중 30% (300 / 예산 1,000)", diag)

    def export():
        stage("④ 내보내기")
        see(page, "예상 세금")
        see(page, note)
        assert not page.evaluate(ROW_WITH, ["STRC", "%", "빼고 계산했어요"]), "요약 표에 STRC 줄이 있어요"
        with page.expect_download() as dl:
            page.get_by_role("button", name="JSON 저장 (백업·공유)").click()
        with open(dl.value.path(), encoding="utf-8") as fh:
            j = json.load(fh)
        # 백업(v18.4.1 모양): 목록에 있는 줄 3개 + 빠진 STRC 는 notInData 줄로 (금액만, 가격·비중은 null) — 불러오면 그대로 돌아와요
        listed = [x for x in j["holdings"] if not x.get("notInData")]
        gone = [x for x in j["holdings"] if x.get("notInData")]
        assert "STRC" not in [x["ticker"] for x in listed] and len(listed) == 3, j["holdings"]
        assert [(x["ticker"], x["amountWon"], x["weightPct"]) for x in gone] == [("STRC", 2000000, None)], gone
        assert j.get("notInDataNote") == note, j.get("notInDataNote")
        assert j.get("budgetWon") == 10000000 and j["metrics"]["cashWon"] == 3000000, (j.get("budgetWon"), j["metrics"]["cashWon"])
        with page.expect_download() as dl:
            page.get_by_role("button", name="CSV 저장 (주문표)").click()
        with open(dl.value.path(), encoding="utf-8-sig") as fh:
            rows = fh.read().splitlines()
        assert not any(r.startswith("STRC,") for r in rows) and rows[-1] == '"※ ' + note + '"', rows[-3:]
        assert rows[-2] == "CASH,현금,-,-,3000000,30.00,-,0,0", rows[-2]
        row = page.evaluate(SMALLEST, ["남는 현금 (무위험)", ["%"]])
        assert row and "300만원" in row and "30.0%" in row, f"요약 표 현금 줄: {row!r}"
        page.evaluate("""() => { window.__memo = null; const w = (x) => { window.__memo = x; return Promise.resolve(); };
            try { navigator.clipboard.writeText = w; } catch (e) {}
            if (!navigator.clipboard || navigator.clipboard.writeText !== w) Object.defineProperty(navigator, 'clipboard', { value: { writeText: w }, configurable: true }); }""")
        page.get_by_role("button", name="텍스트 복사 (주문 메모)").click()
        memo = poll(page, "window.__memo", bool, "주문 메모가 복사되지 않았어요")
        assert "※ " + note in memo and "STRC" not in memo.split("※")[0], memo
        assert "예산 1,000만원" in memo and "현금 300만원" in memo, memo                  # 1,000 = 500 + 300 + 빠진 200
        page.evaluate("""() => { window.__drawn = []; const P = CanvasRenderingContext2D.prototype, f = P.fillText;
            P.fillText = function (t, ...a) { window.__drawn.push(String(t)); return f.call(this, t, ...a); }; }""")
        page.get_by_role("button", name="포트폴리오 카드 만들기 (이미지 공유)").click()
        drawn = poll(page, "window.__drawn", lambda d: d and any("뱁새에서 만듦" in x for x in d), "공유 카드를 그리지 않았어요")
        assert any(x.startswith("※ 오늘 데이터에 없는 종목 1개(STRC 200만원)") for x in drawn), drawn
        assert not any("STRC" in x and not x.startswith("※") for x in drawn), f"공유 카드 TOP 에 STRC 가 있어요: {drawn}"
        page.get_by_role("button", name="닫기", exact=True).first.click()
    R.check(page, S, "④ 내보내기: 화면·JSON(notInData · budgetWon 1,000만원)·CSV 마지막 줄·주문 메모(예산 1,000만원)·공유 카드에 같은 안내, STRC 주문 줄 없음", export)

    def english():
        page.get_by_role("button", name="EN", exact=True).first.click()
        stage("② Build")
        see(page, MISSING_EN.format(n=1, names="STRC ₩2,000,000"))
        assert page.locator(".missingRemove", has_text="Remove from portfolio").count() == 1, "영어 'Remove from portfolio' 버튼이 없어요"
        assert page.locator(".barLegend").inner_text().strip() == BAR_LEGEND["en"], page.locator(".barLegend").inner_text()
        page.get_by_role("button", name="한국어", exact=True).first.click()
        see(page, note)
    R.check(page, S, "영어: 'Left out 1 stock(s) not in today's data (STRC ₩2,000,000).' + 'Remove from portfolio' + 'Not in today's data'", english)

    def saved():
        # 앱이 자동 저장(0.8초 뒤)한 저장본: 심어 둔 값에는 없던 settings 가 있어야 '앱이 다시 썼다'는 뜻이에요
        st = poll(page, "localStorage.getItem('baepsae_v10_slot_smiss')", lambda v: v and '"settings"' in v, "앱이 저장하지 않았어요")
        st = json.loads(st)
        assert {"t": "STRC", "mw": 200} in st["holdings"] and len(st["holdings"]) == 4, st["holdings"]
        # 저장할 때 이름이 붙어요 (나중에 빠지면 코드 대신 이름이 나오게). 미국 종목·빠진 종목은 코드 그대로
        named = {h["t"]: h.get("nk") for h in st["holdings"]}
        assert named["005930"] == "삼성전자" and named["STRC"] is None, named
        page.reload(wait_until="domcontentloaded")
        page.get_by_text("차근차근 만들기", exact=True).click()
        see(page, "빠진 종목 시험")
        row = poll(page, "(" + SMALLEST + ")(['빠진 종목 시험', ['β ']])", bool, "저장 목록에 그 포트폴리오 줄이 없어요")
        assert "3종목" in row, f"저장 목록의 종목 수에 빠진 종목이 들어갔어요: {row!r}"
        page.get_by_text("빠진 종목 시험", exact=False).first.click()
        see(page, note)
        page.wait_for_timeout(1500)
        st = read_slot(page, "smiss")
        assert {"t": "STRC", "mw": 200} in st["holdings"], f"다시 연 뒤 저장본에서 STRC 가 사라졌어요: {st['holdings']}"
    R.check(page, S, "다시 불러와도 저장본(localStorage)에 STRC 가 남아 있음, 저장 목록은 '3종목', 담은 종목에 이름이 붙음", saved)

    def same_as_reference():
        srv2, ctx2, p2, _ = R.open(site, local=local)              # 같은 데이터(STRC 없음)를 새 브라우저로
        p2.get_by_text("차근차근 만들기", exact=True).click()
        p2.get_by_text("빠진 종목 비교", exact=False).first.click()
        see(p2, "보통 해 ±")
        ref_line = p2.evaluate(SMALLEST, ["보통 해 ±", None])
        cash = p2.evaluate(SMALLEST, ["남는 현금 (무위험)", ["만원"]])
        ctx2.close(); srv2.shutdown()
        assert line.get("miss") and ref_line == line["miss"], f"{line.get('miss')!r} ≠ {ref_line!r}"
        assert cash and "300만원" in cash, cash
    R.check(page, S, "STRC 200만원 + 나머지(예산 1,000) = STRC 없이 예산 800 과 같은 위험 줄 · 현금", same_as_reference)

    def comes_back():
        f["data.json"]["stocks"].append(strc)
        with open(os.path.join(site, "data.json"), "w", encoding="utf-8") as fh:
            json.dump(f["data.json"], fh, ensure_ascii=False, allow_nan=True)
        page.reload(wait_until="domcontentloaded")
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("빠진 종목 시험", exact=False).first.click()
        see(page, "보통 해 ±")
        page.wait_for_timeout(500)
        assert page.get_by_text("빼고 계산했어요").count() == 0, "STRC 가 돌아왔는데 안내가 남아 있어요"
        head = page.locator(".cartHead").inner_text()
        assert head.startswith("700 / 1,000"), f"돌아온 STRC 가 합계에 없어요: {head!r}"
        assert page.locator('[data-bar="missing"]').count() == 0, "돌아왔는데 회색 칸이 남아 있어요"
        assert page.locator(".barLegend").count() == 0, "회색 칸이 없는데 이름표가 보여요"
        row = page.evaluate(SMALLEST, [strc["nk"], ["비중 "]])
        assert row and "비중 " in row, f"돌아온 STRC 줄이 없어요: {row!r}"
    R.check(page, S, "STRC 가 데이터에 돌아오면 저절로 다시 계산 (안내 없음 · 합계 700 · 목록에 STRC)", comes_back)
    ctx.close(); srv.shutdown()


# 카트 줄의 삭제 버튼 (글자 없는 작은 버튼): 그 종목 이름이 있는 줄(슬라이더가 있는 줄)의 버튼을 눌러요
CART_REMOVE = """(name) => { const row = [...document.querySelectorAll('input[type=range]')].map((r) => r.parentElement)
  .find((d) => (d.innerText || '').includes(name)); const b = row && row.querySelector('button'); if (b) b.click(); return !!b; }"""


def scene_missing_all(R, files):
    """v18.5 (Jack 2026-11-04 · 리뷰): ① 담은 종목이 전부 오늘 데이터에 없을 때 — 안내 2개(이름·금액), 머리말 0 + 300 / 1,000,
    예산 초과 아님, 예시 포트폴리오 버튼 숨김(빼기 전), ③④ 빈 화면에도 안내, '포트폴리오에서 빼기'를 누르면 그 종목만 저장본에서 지워지고
    예시 버튼이 다시 보여요. ② 빠진 종목이 있는 채로 고치기 카드 적용·카트 줄 삭제를 해도 빠진 종목은 저장본에 남고, 마지막에 '빼기'로만 지워져요."""
    f = json.loads(json.dumps(files, allow_nan=True))
    f["data.json"]["stocks"] = [s for s in f["data.json"]["stocks"] if s.get("t") not in ("STRC", "999991")]
    have = {s.get("t") for s in f["data.json"]["stocks"]}
    assert {"005930", "000660", "105560"} <= have, "시험할 종목이 데이터에 없어요"
    gone = [{"t": "STRC", "mw": 200}, {"t": "999991", "mw": 100, "nk": "시험빠진종목", "ne": "Test Gone Co"}]   # 이름이 저장된 국내 종목
    allm = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": gone}
    profile = {"ready": True, "targetBetaMin": 0.7, "targetBetaMax": 1.1, "targetVolMaxPct": 24, "stocksMin": 2, "stocksMax": 15,
               "maxPositionPct": 40, "maxSectorPct": 100, "cashFloorPct": 0, "riskNeedPct": 7, "riskCapacity": 6, "riskTolerance": 6}
    fix = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "profile": profile,
           "holdings": [{"t": "STRC", "mw": 200}, {"t": "005930", "mw": 300}, {"t": "000660", "mw": 100}, {"t": "105560", "mw": 100}]}
    readd = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "STRC", "mw": 200}, {"t": "005930", "mw": 300}]}
    local = slot_local([("sall", "전부 빠짐 시험", allm), ("sfix", "빠진 종목 고치기 시험", fix), ("sadd", "직접 다시 담기 시험", readd)])
    srv, ctx, page, _ = R.open(build_site(f), local=local, once=True)
    S = "빠진 종목 전부"
    note = MISSING.format(n=2, names="STRC 200만원, 시험빠진종목 100만원")

    def stage(label):
        page.get_by_role("button", name=label, exact=False).first.click()

    def all_missing():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("전부 빠짐 시험", exact=False).first.click()
        see(page, note)
        head = page.locator(".cartHead")
        assert head.inner_text().startswith("0 + 300 / 1,000"), head.inner_text()
        assert head.evaluate("(e) => getComputedStyle(e).color") == "rgb(92, 107, 128)", "예산 안인데 머리말이 예산 초과 색(산호색)"   # C.sub
        assert page.get_by_text("예산 초과").count() == 0, "예산 안인데 '예산 초과'"
        bar = page.evaluate(BAR)
        assert bar and bar["counted"] == 0 and abs(bar["missing"] - 30) < 1, f"예산 막대: {bar}"
        leg = page.evaluate(LEGEND_POS)
        assert leg and leg[0] == BAR_LEGEND["ko"] and abs(leg[1]) <= 2, f"회색 칸 이름표: {leg}"
        assert page.get_by_text("예시 포트폴리오로 둘러보기").count() == 0, "담아 둔 종목이 있는데 예시 버튼(누르면 통째로 바뀜)이 보여요"
        stage("③ 진단")
        see(page, "② 구성에서 종목을 담으면 진단이 열려요.")
        see(page, note)
        stage("④ 내보내기")
        see(page, "아직 담은 종목이 없어요.")
        see(page, note)
    R.check(page, S, "② 0 + 300 / 1,000 · 예산 초과 아님 · 회색 30% · 예시 버튼 숨김 · ③④ 빈 화면에도 안내(이름 저장된 종목은 이름)", all_missing)

    def remove_all():
        stage("② 구성")
        page.locator(".missingRemove", has_text=MISSING_REMOVE).first.click()
        page.get_by_text("예시 포트폴리오로 둘러보기").first.wait_for(state="visible", timeout=WAIT)   # 이제는 보여요 (위 숨김 확인이 진짜)
        assert page.get_by_text("빼고 계산했어요").count() == 0, "뺐는데 안내가 남아 있어요"
        assert page.locator(".cartHead").inner_text().startswith("0 / 1,000"), page.locator(".cartHead").inner_text()
        assert page.locator(".barLegend").count() == 0, "뺐는데 회색 칸 이름표가 남아 있어요"
        poll(page, "localStorage.getItem('baepsae_v10_slot_sall')", lambda v: v and json.loads(v).get("holdings") == [] and '"settings"' in v,
             "'포트폴리오에서 빼기' 뒤에도 저장본에 빠진 종목이 남아 있어요")
    R.check(page, S, "'포트폴리오에서 빼기' → 안내 사라짐 · 저장본 holdings [] · 예시 버튼 다시 보임", remove_all)

    def fix_and_delete():
        page.locator('button[title="저장하고 나가기"]').first.click()
        page.get_by_text("빠진 종목 고치기 시험", exact=False).first.click()
        see(page, MISSING.format(n=1, names="STRC 200만원"))
        page.get_by_text("이렇게 하면 맞춰져요", exact=False).first.click()        # 한 종목 상한 40% (삼성전자 60%) 고치기
        page.get_by_role("button", name="이대로 적용하기").first.click()   # 고칠 게 없어지면 알림 상자째 사라져요 (저장본으로 확인)
        st = poll(page, "localStorage.getItem('baepsae_v10_slot_sfix')", lambda v: v and '"settings"' in v
                  and next(h for h in json.loads(v)["holdings"] if h["t"] == "005930")["mw"] < 300, "고치기를 적용한 저장본이 없어요")
        hs = json.loads(st)["holdings"]
        assert {"t": "STRC", "mw": 200} in hs, f"고치기 카드를 적용했더니 빠진 종목이 저장본에서 사라졌어요: {hs}"
        assert page.evaluate(CART_REMOVE, "SK하이닉스"), "카트에서 SK하이닉스 줄의 삭제 버튼을 못 찾았어요"
        st = poll(page, "localStorage.getItem('baepsae_v10_slot_sfix')", lambda v: v and "000660" not in v, "카트 줄 삭제가 저장되지 않았어요")
        hs = json.loads(st)["holdings"]
        assert {"t": "STRC", "mw": 200} in hs and len(hs) == 3, f"다른 줄을 지웠더니 빠진 종목도 사라졌어요: {hs}"
        page.locator(".missingRemove", has_text=MISSING_REMOVE).first.click()
        st = poll(page, "localStorage.getItem('baepsae_v10_slot_sfix')", lambda v: v and "STRC" not in v, "'포트폴리오에서 빼기'가 저장되지 않았어요")
        assert sorted(h["t"] for h in json.loads(st)["holdings"]) == ["005930", "105560"], st
    R.check(page, S, "빠진 종목이 있는 채로 고치기 카드 적용 · 카트 줄 삭제 → 빠진 종목은 남음, '빼기'로만 지워짐", fix_and_delete)

    def re_add_by_hand():
        # 빠진 STRC 를 '+ 직접 종목 추가'로 다시 넣으면: 종목만 들어가고 저장해 둔 200만원이 그대로 돌아와요 (두 줄 X)
        page.locator('button[title="저장하고 나가기"]').first.click()
        page.get_by_text("직접 다시 담기 시험", exact=False).first.click()
        see(page, MISSING.format(n=1, names="STRC 200만원"))
        page.get_by_text("+ 직접 종목 추가", exact=True).click()
        form = page.locator("div", has=page.locator("select")).last
        form.locator("label", has_text="종목명").locator("input").fill("STRC 직접")
        form.locator("label", has_text="코드").locator("input").fill("STRC")
        form.locator("button", has_text="담기").click()
        page.wait_for_timeout(300)
        assert page.get_by_text("빼고 계산했어요").count() == 0, "다시 넣었는데 안내가 남아 있어요"
        assert page.locator(".cartHead").inner_text().startswith("500 / 1,000"), page.locator(".cartHead").inner_text()
        st = poll(page, "localStorage.getItem('baepsae_v10_slot_sadd')", lambda v: v and "STRC 직접" in v, "다시 넣은 종목이 저장되지 않았어요")
        strc = [h for h in json.loads(st)["holdings"] if h["t"] == "STRC"]
        assert len(strc) == 1 and strc[0]["mw"] == 200, f"STRC 줄이 {len(strc)}개 / 금액 {strc}"
    R.check(page, S, "빠진 종목을 '직접 종목 추가'로 다시 넣으면 한 줄 그대로 · 저장해 둔 200만원이 돌아옴 (중복 줄 없음)", re_add_by_hand)
    ctx.close(); srv.shutdown()


# 프로필 문장을 만드는 답 (src/detail.jsx scoreProfile): A = 낮은 목표·넉넉한 형편 → '베타 0.45 정도면 충분해요' 팁,
# B = 높은 목표·빠듯한 형편 → '(β 최대 0.7)으로 기대하기 어려운 수치예요' 경고. 둘 다 요약에 '목표는 연 X%라서, 베타 …'.
ANS_A = {"goal": "retire", "horizon": 20, "share": 10, "emergency": 12, "target": 4, "style": ["long"], "crash": ["hold"],
         "exp": ["krstock"], "checking": "monthly", "fear": ["none"], "account": "normal", "interest": ["index"]}
ANS_B = {"goal": "grow", "horizon": 1, "share": 100, "emergency": 0, "target": 15, "style": ["ret"], "crash": ["sellall"],
         "exp": ["newbie"], "checking": "daily", "fear": ["loss"], "account": "normal", "interest": ["semi"]}
# 리뷰 답 (전 재산 100% · 비상금 0개월 · 하루 한 번 확인 · 레버리지 경험): 예전엔 '기대하기 어려운 수치' 경고가 경고 자리(3개)를 차지해
# '비상금이 먼저예요' 경고가 밀려났어요. 이제는 그 줄을 만들지 않아서 비상금 경고가 보여요.
ANS_R = {"goal": "house", "horizon": 20, "share": 100, "emergency": 0, "target": 8, "style": ["long"], "crash": ["sellsome"],
         "exp": ["lev"], "checking": "daily", "fear": ["loss"], "account": "normal", "interest": ["index"]}
# 예전 앱이 저장한 프로필 (v15.3~v18.4 의 문장 틀 그대로): 화면과 JSON 내보내기에서 같이 걸러야 해요
# 목표 베타 0.5–0.8 · 변동성 ≤22% 는 목표 연 6% 로 낮춘 값 그대로 → 화면에는 감당 능력(6·6) 기준 0.7–1.1 · ≤25% (v18.5, Jack 2026-11-04)
LEGACY_PROFILE = {"ready": True, "source": "rules", "title": "차분한 균형형", "riskCapacity": 6, "riskTolerance": 6, "riskNeedPct": 6,
                  "attrs": {"capacity": 6, "tolerance": 6, "horizon": 6, "experience": 5, "knowledge": 5, "discipline": 6, "ambition": 4, "engagement": 5},
                  "targetBetaMin": 0.5, "targetBetaMax": 0.8, "targetVolMaxPct": 22, "stocksMin": 8, "stocksMax": 15,
                  "maxPositionPct": 100, "maxSectorPct": 100, "cashFloorPct": 0, "interestedSectors": [], "checkFreq": "월 1회",
                  "summary": "10년 뒤를 보고 계시고, 전 재산의 40%를 이 투자에 담을 계획이에요. 비상금은 3개월치이고요. 감수 능력 6점, "
                             "감수 의지 6점 중 더 낮은 쪽인 형편(감수 능력)이 기준이 돼요. 목표는 연 6%라서, 베타 0.5~0.8 범위에서 8~15종목쯤으로 나눠 담는 걸 권해요.",
                  "tips": ["목표가 연 6%라면 베타 0.80 정도면 충분해요. 형편상 더 감수할 수 있어도, 필요 없는 위험까지 질 이유는 없어요 — 안 써도 되는 위험은 그냥 떠안은 위험이 되니까요.",
                           "처음이라면 지수 ETF 한두 개로 뼈대를 세우고, 잘 아는 종목을 조금씩 얹어가는 순서가 편해요."],
                  "flags": ["목표 연 6%는 지금 감당 가능한 위험(β 최대 0.8)으로 기대하기 어려운 수치예요. 목표·기간·저축액 셋 중 하나는 조정이 필요해요 — 위험을 억지로 키우는 건 답이 아니고요."]}


# 타임머신 그림: 선(path.tmLine)의 점들과 최저점(circle.tmLow). 가로 끝 = 8 + (W − 16) = 412 (W = 420, 마지막 달)
TM_PATH = """() => { const p = document.querySelector('path.tmLine'), c = document.querySelector('circle.tmLow');
  if (!p || !c) return null; const pts = p.getAttribute('d').trim().split(/[ML]/).filter(Boolean).map((x) => x.split(',').map(Number));
  return { n: pts.length, last: pts[pts.length - 1], low: [+c.getAttribute('cx'), +c.getAttribute('cy')] }; }"""
TM_END_X = 412


def scene_beta_return(R, files):
    """B안 (v18.5, Jack 2026-11-03): 베타를 수익률로 바꾸는 줄은 SHOW_ER 를 켤 때만.
    ② 종목 줄을 펼쳐 '이론 샤프'(β × 프리미엄 ÷ σ)가 없고 과거 값 '샤프(3y)'·'3y α'·'최대낙폭'은 보이는지,
    ① 프로필(새로 만든 것 KO·EN, 예전에 저장된 것)에 '목표 → 베타'·'β → 기대 수익' 문장이 없고 나머지 문장은 남는지 봐요."""
    hold = [{"t": "005930", "mw": 300}, {"t": "000660", "mw": 200}]
    slots = [("srow", "종목 줄 시험", {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": hold})]
    srv, ctx, page, _ = R.open(build_site(files), local=slot_local(slots))
    S = "베타→수익률"

    def row(ph, code):
        box = page.get_by_placeholder(ph)
        box.fill(code)
        page.get_by_text(code, exact=True).first.click()        # 종목 줄을 눌러 펼쳐요 (예전엔 여기에 '이론 샤프')

    def rows_ko():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("종목 줄 시험", exact=False).first.click()
        see(page, "보통 해 ±")
        row("종목명·코드 검색", "005930")
        for keep in ("샤프(3y)", "3y α", "최대낙폭", "12개월"):     # 과거 가격으로만 만든 값은 그대로
            see(page, keep)
        shown = hidden_shown(page.locator("body").inner_text(), HIDDEN_B)
        assert not shown, f"펼친 종목 줄에 보이면 안 되는 문구: {shown}"
    R.check(page, S, "② 펼친 종목 줄: '이론 샤프' 없음, 샤프(3y)·3y α·최대낙폭 보임 (KO)", rows_ko)

    def rows_en():
        page.get_by_role("button", name="EN", exact=True).first.click()
        see(page, "Sharpe 3y")
        see(page, "3y α")
        shown = hidden_shown(page.locator("body").inner_text(), HIDDEN_B_EN)
        assert not shown, f"펼친 종목 줄(EN)에 보이면 안 되는 문구: {shown}"
    R.check(page, S, "② 펼친 종목 줄: 'CAPM Sharpe' 없음, Sharpe 3y 보임 (EN)", rows_en)

    def tm_card(title, note):
        return page.evaluate(SMALLEST, [title, [note]]) or ""

    def diag_en():
        page.get_by_role("button", name="③ Diagnose", exact=False).first.click()
        see(page, "What I'm doing right")
        page.get_by_text("Is my risk being paid for?", exact=False).first.click()
        see(page, "The orange part (specific risk) pays nothing")               # 뒤 문장은 남아요
        page.get_by_text("Want to experiment?", exact=False).first.click()
        see(page, "Time Machine — live a crash in advance")
        card = tm_card("Time Machine — live a crash in advance", "A simulation")
        assert "₩" not in card and "%" not in card, f"재생 전 타임머신에 금액·% (베타로 만든 경로의 값): {card!r}"
        page.get_by_role("button", name="▶ Play").first.click()
        see(page, "If you sold at the bottom")                                   # 끝까지 재생됐어요 (바닥 칸은 남아요)
        page.wait_for_timeout(400)
        card = tm_card("Time Machine — live a crash in advance", "A simulation")
        # 남는 숫자: 기간 버튼 · '24/24mo' · 바닥 칸의 금액 1개와 % 1개뿐 (끝 값·고점 대비 없음)
        assert card.count("₩") == 1 and card.count("%") == 1 and "From peak" not in card, f"타임머신(끝): {card!r}"
        shown = hidden_shown(page.locator("body").inner_text(), HIDDEN_B_EN)
        assert not shown, f"③ (EN) 보이면 안 되는 문구: {shown}"
    R.check(page, S, "③ 타임머신: 재생 전 금액·% 없음 · 끝까지 재생해도 끝 값·'If you held to the end'·'What holding was worth' 없고 바닥 칸(금액 1·% 1)만 · 위험 나누기 앞 문장 없음 (EN)", diag_en)

    def tm_line_stops_at_low():
        # v18.6 (Jack 2026-11-04): 최저점 뒤의 경로(회복)는 베타로 만든 수익이라 그리지 않아요 — 재생이 끝나도 선은 최저점에서 끝나요
        got = page.evaluate(TM_PATH)
        assert got, "타임머신의 선(path.tmLine)이나 최저점(circle.tmLow)이 없어요"
        assert got["n"] >= 2 and abs(got["last"][0] - got["low"][0]) < 0.01 and abs(got["last"][1] - got["low"][1]) < 0.01, got
        assert got["low"][0] < TM_END_X - 1, f"최저점이 마지막 달이라 이 시험이 아무것도 보지 못해요: {got}"
    R.check(page, S, "③ 타임머신: 재생이 끝나도 선의 마지막 점 = 최저점 (그 뒤 경로는 그리지 않음)", tm_line_stops_at_low)

    def diag_ko():
        page.get_by_role("button", name="한국어", exact=True).first.click()
        see(page, "최저점에서 팔았다면")
        see(page, "주황 부분(개별 위험)은 시장이 한 푼도 쳐주지 않는데")
        see(page, "다른 사람들과 비교하면")                                       # 카드의 나머지(과거 자료로 만든 부분)는 그대로
        card = tm_card("타임머신 — 폭락을 미리 살아보기", "실제 코스피 월별 흐름에")
        assert card.count("만원") == 1 and card.count("%") == 1 and "고점 대비" not in card, f"타임머신(끝): {card!r}"
        shown = hidden_shown(page.locator("body").inner_text(), HIDDEN_B)
        assert not shown, f"③ 보이면 안 되는 문구: {shown}"
    R.check(page, S, "③ 타임머신: 끝 값·'끝까지 버텼다면'·'버틴 값어치'·'고점 대비' 없음, '최저점에서 팔았다면'(금액 1·% 1)만 · 위험 나누기 카드 앞 문장만 없음 (KO)", diag_ko)
    ctx.close(); srv.shutdown()

    def fresh(sid, name, lang, ans):
        # profile 을 비워 둬요: 저장본에 profile 이 없으면 앞서 연 포트폴리오의 프로필이 그대로 남아요 (applyState)
        return (sid, name, {"schema": 10, "lang": lang, "stage": 0, "budgetMw": 1000, "holdings": hold, "answers": ans, "profile": {"ready": False}})
    pslots = [fresh("pka", "프로필 A", "ko", ANS_A), fresh("pkb", "프로필 B", "ko", ANS_B),
              fresh("pea", "Profile A", "en", ANS_A), fresh("peb", "Profile B", "en", ANS_B), fresh("pkr", "프로필 R", "ko", ANS_R),
              ("plg", "예전 프로필", {"schema": 10, "lang": "ko", "stage": 0, "budgetMw": 1000, "holdings": hold, "profile": LEGACY_PROFILE})]
    srv, ctx, page, _ = R.open(build_site(files), local=slot_local(pslots))

    def profile(name, en, make, keep, first=False):
        def run():
            if first:
                page.get_by_text("차근차근 만들기", exact=True).click()
            else:                                                   # 앞 포트폴리오에서 나와 목록으로
                page.locator('button[title="저장하고 나가기"], button[title="Save and exit"]').first.click()
            page.get_by_text(name, exact=True).first.click()
            if make:
                page.get_by_role("button", name="See my profile" if en else "내 프로필 보기").first.click()
            see(page, "My Investor Profile" if en else "나의 투자 프로필")
            for k in keep:
                see(page, k)
            shown = hidden_shown(page.locator("body").inner_text(), HIDDEN_B_EN if en else HIDDEN_B)
            assert not shown, f"{name}: 보이면 안 되는 문구: {shown}"
        return run
    R.check(page, S, "① 새 프로필 A (KO): '…%라서, 베타' · '베타 … 정도면 충분해요' 없음, 감수 능력 문장·목표 베타·필요 수익률은 남음",
            profile("프로필 A", False, True, ("감수 능력 10점", "기준이 돼요.", "목표 베타", "0.9–1.4", "≤29%", "필요 수익률"), first=True))
    R.check(page, S, "① 새 프로필 B (KO): '… 기대하기 어려운 수치예요' 없음, 목표만 말하는 '전설들의 영역' 팁은 남음",
            profile("프로필 B", False, True, ("기준이 돼요.", "전설들의 영역", "목표 베타")))
    R.check(page, S, "① 새 프로필 A (EN): 'goal, aim for beta' · 'goal only needs about beta' 없음",
            profile("Profile A", True, True, ("Between capacity", "binds.", "Target beta", "Required return")))
    R.check(page, S, "① 새 프로필 B (EN): 'is hard to expect from the risk you can carry' 없음",
            profile("Profile B", True, True, ("binds.", "legend territory", "Target beta")))
    R.check(page, S, "① 새 프로필 R (KO, 리뷰 답: 전 재산 100% · 비상금 0개월 · 매일 확인 · 레버리지): '비상금이 먼저예요' 경고가 보임",
            profile("프로필 R", False, True, ("비상금이 먼저예요", "레버리지·인버스 경험이 있으시네요")))

    def legacy():
        profile("예전 프로필", False, False, ("감수 능력 6점", "기준이 돼요.", "처음이라면 지수 ETF", "0.7–1.1", "≤25%"))()
        assert page.get_by_text("0.5–0.8").count() == 0, "예전 프로필에 목표 수익률로 낮춘 목표 베타(0.5–0.8)가 보여요"
    R.check(page, S, "① 예전에 저장된 프로필 (KO): 저장된 세 문장 가려짐 · 목표 베타·변동성은 감당 능력 기준(0.7–1.1 · ≤25%) · 나머지는 보임", legacy)

    def export_json():
        page.get_by_role("button", name="④ 내보내기", exact=False).first.click()
        see(page, "예상 세금")
        with page.expect_download() as dl:
            page.get_by_role("button", name="JSON 저장 (백업·공유)").click()
        with open(dl.value.path(), encoding="utf-8") as fh:
            prof = json.load(fh)["profile"]
        text = json.dumps(prof, ensure_ascii=False)
        assert not hidden_shown(text, HIDDEN_B) and "감수 능력 6점" in text and "처음이라면 지수 ETF" in text, prof
    R.check(page, S, "④ JSON 내보내기의 프로필에도 그 세 문장이 없음", export_json)
    ctx.close(); srv.shutdown()


def scene_foreign_issuer(R, files):
    """해외 기업(종목코드 9…): 파이프라인이 외화일 수 있는 DART 금액을 비우면(v17.5.2), 기업분석의 재무 흐름 자리에
    Jack 이 정한 줄 "외화로 작성된 재무제표라 아직 보여 드리지 않아요." 가 보여요 (2026-11-03). 국내 기업의 빈 칸 문구는 그대로예요."""
    f = json.loads(json.dumps(files, allow_nan=True))
    names = {s.get("t"): s.get("nk") for s in f["data.json"]["stocks"]}
    cos = [c for c in f["corp.json"]["companies"] if str(c.get("t", "")).startswith("9") and len(str(c["t"])) == 6 and names.get(c["t"])]
    assert cos, "시험할 해외 기업(9…)이 데이터에 없어요"
    co = cos[0]
    co.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False)
    srv, ctx, page, _ = R.open(build_site(f))

    def run():
        search(page, co["t"], co["t"])
        page.locator("button", has_text=co["t"]).first.click()
        page.get_by_text("기업분석에서 자세히 보기", exact=True).first.click()
        see(page, "외화로 작성된 재무제표라 아직 보여 드리지 않아요.")
        body = page.locator("body").inner_text()
        assert "파이프라인이 사업보고서를 못 찾은 종목이에요" not in body and "NaN" not in body, "해외 기업에 국내용 빈 칸 문구 또는 NaN"
    R.check(page, "해외 기업", f"{co['t']} {names[co['t']]}: 재무 흐름 자리에 '외화로 작성된 재무제표라…'", run)
    ctx.close(); srv.shutdown()


def scene_rates_fail(R, files):
    """macro.json 은 읽히는데 금리(ECOS) 부분만 빈 날: 금리 칸에만 '금리 데이터를 불러오지 못했어요' (영어 모드는 영어)."""
    # 비교 기준: 커브가 있으면 그 칸에 실패 문구가 없어야 해요 (같은 장면이 언제나 실패 문구만 보여 주는 건 아닌지)
    g = json.loads(json.dumps(files, allow_nan=True))
    g["macro.json"]["curve"] = {"tenors": [1, 3, 5, 10, 30], "now": [2.9, 3.0, 3.2, 3.5, 3.6], "ago": [2.7, 2.8, 3.0, 3.1, 3.3],
                                "date": "2026-10-30"}
    srv, ctx, page, _ = R.open(build_site(g), local={"baepsae_v9_seen": "1"})

    def control():
        tab(page, "금리·원자재")
        see(page, "한국은행 ECOS · 기준 2026-10-30")
        page.wait_for_timeout(300)
        assert page.get_by_text(RATES_FAIL).count() == 0, "커브가 있는데 '금리 데이터를 불러오지 못했어요'"
    R.check(page, "금리 일부 실패", "비교: 커브가 있으면 실패 문구 없음", control)
    ctx.close(); srv.shutdown()

    f = json.loads(json.dumps(files, allow_nan=True))
    for k in ("curve", "sprKr", "tenor", "credit"):
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


IMPORT_FAIL = "파일을 읽을 수 없어요."      # 「저장한 파일에서 불러오기」가 못 읽을 때 (이미 있던 알림 문구)
T_LOAD_FAIL_KO = "데이터를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요."   # src/detail.jsx T_LOAD_FAIL.ko (이미 있던 문구)
# 직접 추가 종목 (CustomStockForm 이 만드는 모양 그대로)
MINE = {"t": "MYCO1", "nk": "내 회사", "ne": "내 회사", "s": "semi", "price": 10000, "beta": 1.0, "vol": 35, "per": 10, "pbr": 1, "dy": 0,
        "al": 0, "custom": True, "x": {}}
CART_ROWS = """() => [...document.querySelectorAll('input[type=number][step="10"]')].map((i) => {
  const box = i.parentElement; const name = box.children[1] && box.children[1].children[0];
  return [name ? name.textContent : '?', i.value]; })"""
BUDGET_BOX = 'input[type=number][step="100"]'


# 받은 파일의 주소(Blob URL)를 언제 지우는지 기록해요: 바로 지우면 iOS 사파리가 받다가 실패할 수 있어요 (v18.4.1, 60초 뒤에 지워요)
# 한 번만 심어요. 받을 때마다 그 파일의 주소가 아직 지워지지 않았는지 봐요 (앞서 받은 파일의 60초 타이머와 섞이지 않게).
REVOKE_SPY = """() => { if (window.__revoked) return; window.__revoked = []; const orig = URL.revokeObjectURL.bind(URL);
  URL.revokeObjectURL = (u) => { window.__revoked.push(u); return orig(u); }; }"""


def scene_json_import(R, files):
    """④ 내보내기의 'JSON 저장 (백업·공유)' 파일을 첫 화면의 '저장한 파일에서 불러오기'로 다시 읽어요 (v18.4.1, Jack 2026-11-04).
    전에는 이 앱이 저장한 파일({ holdings: [{ ticker, amountWon }], budgetWon })이 아무 말 없이 빈 포트폴리오로 열렸어요.
      · 저장: 저장해 둔 포트폴리오(실제 종목 3개)를 열고 화면에서 예산 · 금액을 바꾼 뒤 'JSON 저장'으로 파일을 받아요
        (예산 2,500만원 · 예산 초과(500만원) · 예산 0 세 가지). 받은 파일의 주소는 1.5초 안에 지우지 않아요;
      · 새 브라우저(저장소가 빈 새 문맥)에서 그 파일을 불러오면 같은 종목 · 같은 금액 · 같은 예산 (알림 없음), 예산 초과는 '예산 초과!'까지;
      · 종목이 없는 파일 · 깨진 파일 · 줄이 모두 틀린 파일 → '파일을 읽을 수 없어요.' 알림, 있던 포트폴리오는 그대로;
      · 예전 저장 상태 모양({ state: … }) 파일도 그대로 열려요;
      · 지금 목록에 없는 종목이 섞인 파일: 있는 종목은 보이고, 없는 종목은 저장본에 남아요 (새로 고침 뒤에도)."""
    tmp = tempfile.mkdtemp(prefix="baepsae-json-")          # 받은 파일 · 시험 파일 · 사이트를 한 폴더에 두고 끝나면 지워요
    try:
        _json_import(R, files, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _json_import(R, files, tmp):
    S = "파일 불러오기"
    have = {s.get("t") for s in files["data.json"]["stocks"]}
    pick = [t for t in ("005930", "000660", "AAPL") if t in have]
    gone = next(t for t in ("999999", "999998", "999997") if t not in have)      # 지금 목록에 없는 종목코드
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000,
            "profile": {"ready": True, "source": "preset", "targetBetaMin": 0.6, "targetBetaMax": 1.0, "targetVolMaxPct": 22,
                        "stocksMin": 3, "stocksMax": 10, "maxPositionPct": 60, "maxSectorPct": 60, "cashFloorPct": 5},
            "holdings": [{"t": t, "mw": mw} for t, mw in zip(pick, (300, 200, 150))] + [{"t": MINE["t"], "mw": 100}],
            "customStocks": [MINE]}                                       # 직접 추가 종목도 하나 (정의가 파일에 같이 가야 돌아와요)
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "sjx", "name": "파일 저장 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_sjx": json.dumps(slot, ensure_ascii=False)}
    site = os.path.join(tmp, "site")
    shutil.move(build_site(files), site)
    srv, ctx, page, base = R.open(site, local=local)
    saved = {}

    def stage(label):
        page.get_by_role("button", name=label, exact=False).first.click()

    def download(key):
        """④ 내보내기의 'JSON 저장' → tmp 에 옮겨 둔 파일의 내용. 주소를 1.5초 안에 지우지 않는지도 봐요."""
        stage("④ 내보내기")
        page.evaluate(REVOKE_SPY)
        with page.expect_download() as dl:
            page.get_by_role("button", name="JSON 저장 (백업·공유)").click()
        name, url = dl.value.suggested_filename, dl.value.url
        assert name.startswith("baepsae-portfolio-") and name.endswith(".json") and url.startswith("blob:"), (name, url)
        saved[key] = os.path.join(tmp, key + "-" + name)                    # 문맥을 닫으면 받은 파일이 지워져서 옮겨 둬요
        dl.value.save_as(saved[key])
        page.wait_for_timeout(1500)
        assert url not in page.evaluate("window.__revoked"), "받은 파일의 주소를 너무 일찍 지웠어요 (iOS 사파리에서 받기가 실패할 수 있어요)"
        with open(saved[key], encoding="utf-8") as fh:
            return json.load(fh)

    def export():
        assert len(pick) == 3, f"시험할 종목이 모자라요: {pick}"
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("파일 저장 시험", exact=False).first.click()
        page.locator(BUDGET_BOX).first.wait_for(state="visible", timeout=WAIT)
        page.locator(BUDGET_BOX).first.fill("2500")                       # 기본값(1,000만원)이 아닌 예산
        page.locator('input[type=number][step="10"]').first.fill("450")   # 첫 종목 300 → 450만원
        poll(page, CART_ROWS, lambda v: len(v) == 4 and v[0][1] == "450", "장바구니에 바꾼 금액이 보이지 않아요")
        saved["rows"] = page.evaluate(CART_ROWS)
        assert saved["rows"][3] == [MINE["nk"], "100"], saved["rows"]
        j = download("main")
        got = [(h["ticker"], h["amountWon"]) for h in j["holdings"]]
        assert got == list(zip(pick + [MINE["t"]], (4500000, 2000000, 1500000, 1000000))), got   # 칸 이름은 그대로 (ticker · amountWon)
        assert j["customStocks"] == [MINE], j.get("customStocks")             # 직접 추가 종목의 정의도 같이 (v18.4.1)
        assert j["budgetWon"] == 25000000 and j["profile"]["targetBetaMax"] == 1.0, (j["budgetWon"], j["profile"])
        saved["fx"] = j["settings"]["fx"]
    R.check(page, S, f"저장한 포트폴리오({', '.join(pick)}) · 예산 2,500만원 → 'JSON 저장 (백업·공유)' 파일 받기 (주소는 늦게 지움)", export)

    def export_budgets():
        for budget, key in (("500", "over"), ("0", "zero")):
            stage("② 구성")
            page.locator(BUDGET_BOX).first.fill(budget)
            if key == "over":
                see(page, "예산 초과!")                                     # 450 + 200 + 150 = 800만원 > 500만원
            j = download(key)
            assert j["budgetWon"] == int(budget) * 10000, (key, j["budgetWon"])   # 투자한 돈(800만원)이 아니라 내가 정한 예산
    R.check(page, S, "예산 초과(500만원) · 예산 0 → 파일의 budgetWon 은 내가 정한 예산 그대로 (투자한 돈 아님)", export_budgets)
    ctx.close()

    # 새 브라우저 문맥: 저장소가 비어 있어요 (다른 기기 · 다른 브라우저에서 여는 것과 같아요)
    ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
    page = ctx.new_page()
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
    file_box = page.locator('input[type=file][accept="application/json,.json"]')

    def slots_now():
        return page.evaluate("""() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i);
            if (k.startsWith('baepsae_v10_')) o[k] = localStorage.getItem(k); } return o; }""")

    newest = """() => { const l = JSON.parse(localStorage.getItem('baepsae_v10_slots') || '[]');
        return l.length ? JSON.parse(localStorage.getItem('baepsae_v10_slot_' + l[0].id) || 'null') : null; }"""

    def newest_slot():
        """가장 최근에 저장된 포트폴리오 (자동 저장은 0.8초 뒤에 돌아요)."""
        return page.evaluate(newest)

    def launch_screen():
        see(page, "어떻게 시작할까요?")
        assert page.get_by_role("button", name="② 구성").count() == 0, "첫 화면이 아니라 포트폴리오가 열려 있어요"

    def go_home():
        leave = page.get_by_role("button", name="저장하고 나가기")
        if leave.count():
            leave.first.click()
        launch_screen()

    def round_trip():
        assert "main" in saved, "앞 단계에서 파일을 받지 못했어요"
        assert slots_now() == {}, f"새 문맥인데 포트폴리오가 저장돼 있어요: {list(slots_now())}"
        page.get_by_text("차근차근 만들기", exact=True).click()
        close_welcome(page, "시작하기")
        launch_screen()
        file_box.set_input_files(saved["main"])
        stage("② 구성")
        page.locator(BUDGET_BOX).first.wait_for(state="visible", timeout=WAIT)
        rows = poll(page, CART_ROWS, lambda v: len(v) >= 4, "불러온 포트폴리오에 종목이 없어요")
        assert rows == saved["rows"], f"불러온 종목·금액 {rows} ≠ 저장한 {saved['rows']}"   # 직접 추가 종목도 금액과 함께 보여요
        assert page.locator(BUDGET_BOX).first.input_value() == "2500", page.locator(BUDGET_BOX).first.input_value()
        assert page.get_by_text("예산 초과!").count() == 0
        assert not dialogs, f"제대로 된 파일인데 알림: {dialogs}"
        # 자동 저장(0.8초 뒤)된 새 포트폴리오: 같은 종목코드 · 금액 · 예산, 프로필과 설정도 파일 그대로
        st = poll(page, newest, lambda v: bool(v) and len(v["holdings"]) == 4, "불러온 포트폴리오가 저장되지 않았어요")
        assert [(h["t"], h["mw"]) for h in st["holdings"]] == list(zip(pick + [MINE["t"]], (450, 200, 150, 100))), st["holdings"]
        assert st["customStocks"] == [MINE], st.get("customStocks")
        assert st["budgetMw"] == 2500 and st["profile"]["ready"] is True and st["profile"]["targetBetaMax"] == 1.0, st["profile"]
        assert st["settings"]["fx"] == saved["fx"], st["settings"]
    R.check(page, S, "새 브라우저(빈 저장소)에서 그 파일 불러오기 → 같은 종목 · 같은 금액 · 같은 예산, 알림 없음", round_trip)

    def write(name, text):
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def refused(path, what):
        go_home()
        page.wait_for_timeout(1000)                                    # 자동 저장이 끝난 뒤의 저장소
        before, n = slots_now(), len(dialogs)
        assert before.get("baepsae_v10_slots"), "비교할 포트폴리오가 없어요"
        file_box.set_input_files(path)
        poll(page, "1", lambda _: len(dialogs) > n, f"{what}: 알림이 뜨지 않았어요")
        assert dialogs[n:] == [IMPORT_FAIL], f"{what}: 알림 {dialogs[n:]}"
        page.wait_for_timeout(1200)                                    # 빈 포트폴리오가 열렸다면 자동 저장까지 기다려서 봐요
        launch_screen()
        after = slots_now()
        assert after == before, f"{what}: 저장된 포트폴리오가 바뀌었어요 ({len(before)} → {len(after)})"

    export_head = {"app": "Baepsae 뱁새 v12", "slot": "빈 파일", "date": "2026-11-03", "budgetWon": 10000000}
    bad_files = [
        ("종목이 없는 파일 (JSON 저장 모양)", "empty.json", json.dumps({**export_head, "holdings": []}, ensure_ascii=False)),
        ("종목이 없는 파일 (예전 저장 모양)", "empty-state.json", json.dumps({"state": {"schema": 10, "budgetMw": 1000, "holdings": []}})),
        ("깨진 파일", "garbage.json", '{"app": "Baepsae", "holdings": [{"ticker": "005930", "amou'),
        ("모양이 다른 파일", "other.json", '{"hello": 1}'),
        ("줄이 모두 틀린 파일 (JSON 저장 모양)", "all-bad.json", json.dumps({**export_head, "holdings": [
            {"ticker": "", "amountWon": 1000000}, {"ticker": pick[0] if pick else "005930", "amountWon": 0},
            {"ticker": pick[1] if len(pick) > 1 else "000660", "amountWon": "300만"}, {"ticker": gone, "amountWon": 0}]},
            ensure_ascii=False)),
        ("지금 목록에 있는 종목이 하나도 없는 파일", "none-listed.json", json.dumps({**export_head, "holdings": [
            {"ticker": gone, "name": "없는 회사", "amountWon": 1000000}]}, ensure_ascii=False)),
    ]
    for what, name, text in bad_files:
        R.check(page, S, f"{what} → '{IMPORT_FAIL}' 알림, 있던 포트폴리오 그대로",
                lambda name=name, text=text, what=what: refused(write(name, text), what))

    def still_same():
        launch_screen()
        page.get_by_text("불러온 포트폴리오", exact=False).first.click()
        stage("② 구성")
        rows = poll(page, CART_ROWS, lambda v: len(v) >= 4, "다시 연 포트폴리오에 종목이 없어요")
        assert rows == saved.get("rows") and page.locator(BUDGET_BOX).first.input_value() == "2500", rows
    R.check(page, S, "잘못된 파일들을 불러온 뒤에도 불러온 포트폴리오는 그대로 (종목 · 금액 · 예산)", still_same)

    def old_state_file():
        go_home()
        old = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1500,
               "holdings": [{"t": pick[0], "mw": 500}, {"t": pick[1], "mw": 300}]}
        n = len(dialogs)
        file_box.set_input_files(write("old-state.json", json.dumps({"state": old})))
        page.locator(BUDGET_BOX).first.wait_for(state="visible", timeout=WAIT)       # 파일의 stage 1 (② 구성)로 열려요
        rows = poll(page, CART_ROWS, lambda v: len(v) == 2, "예전 모양 파일의 종목이 보이지 않아요")
        assert [v for _, v in rows] == ["500", "300"] and page.locator(BUDGET_BOX).first.input_value() == "1500", rows
        assert len(dialogs) == n, f"예전 모양 파일인데 알림: {dialogs[n:]}"
    R.check(page, S, "예전 저장 상태 모양({ state: … }) 파일도 그대로 열림", old_state_file)

    def budgets_back():
        for key, want, over in (("over", "500", True), ("zero", "0", False)):
            go_home()
            n = len(dialogs)
            file_box.set_input_files(saved[key])
            stage("② 구성")
            page.locator(BUDGET_BOX).first.wait_for(state="visible", timeout=WAIT)
            rows = poll(page, CART_ROWS, lambda v: len(v) >= 4, f"{key}: 불러온 포트폴리오에 종목이 없어요")
            assert rows == saved["rows"] and page.locator(BUDGET_BOX).first.input_value() == want, (key, rows)
            if over:
                see(page, "예산 초과!")                                     # 예산 초과 경고가 그대로 돌아와요
            else:
                page.wait_for_timeout(300)
                assert page.get_by_text("예산 초과!").count() == 0, "예산 0 인데 '예산 초과!'"
            assert len(dialogs) == n, f"{key}: 알림 {dialogs[n:]}"
    R.check(page, S, "예산 초과 파일 → 예산 500만원 + '예산 초과!' 그대로 · 예산 0 파일 → 예산 0", budgets_back)

    # v18.5: 저장할 때 목록에 있는 (미국 아닌) 종목에는 이름(nk·ne)이 붙어요 — 그 이름은 빼고 견줘요. 없는 종목의 nk 는 그대로 봐요.
    def unnamed(hs):
        return [{k: v for k, v in h.items() if not (k in ("nk", "ne") and h["t"] == pick[0])} for h in hs]

    def unlisted_kept():
        go_home()
        page.wait_for_timeout(1000)
        f = write("with-gone.json", json.dumps({**export_head, "holdings": [
            {"ticker": pick[0], "name": "삼성전자", "amountWon": 3000000}, {"ticker": gone, "name": "없는 회사", "amountWon": 2000000}]},
            ensure_ascii=False))
        n = len(dialogs)
        file_box.set_input_files(f)
        stage("② 구성")
        rows = poll(page, CART_ROWS, lambda v: len(v) >= 1, "목록에 있는 종목이 보이지 않아요")
        assert [v for _, v in rows] == ["300"] and len(dialogs) == n, (rows, dialogs[n:])     # 있는 종목만 보여요
        st = poll(page, newest, lambda v: bool(v) and len(v["holdings"]) == 2 and v["budgetMw"] == 1000,
                  "불러온 포트폴리오가 저장되지 않았어요")
        assert unnamed(st["holdings"]) == [{"t": pick[0], "mw": 300}, {"t": gone, "mw": 200, "nk": "없는 회사"}], st["holdings"]
        page.reload(wait_until="domcontentloaded")                     # 새로 고침 뒤: 저장본에 그대로, 열어도 그대로
        page.get_by_text("차근차근 만들기", exact=True).click()
        launch_screen()
        assert newest_slot()["holdings"] == st["holdings"], newest_slot()
        page.get_by_text("불러온 포트폴리오", exact=False).first.click()
        stage("② 구성")
        rows = poll(page, CART_ROWS, lambda v: len(v) >= 1, "다시 연 포트폴리오에 종목이 없어요")
        assert [v for _, v in rows] == ["300"], rows
        page.wait_for_timeout(1200)                                    # 열면 자동 저장이 다시 돌아도 없는 종목은 남아요
        assert newest_slot()["holdings"] == st["holdings"], newest_slot()
    R.check(page, S, "지금 목록에 없는 종목이 섞인 파일 → 있는 종목은 보이고, 없는 종목은 저장본에 남음 (새로 고침 뒤에도)", unlisted_kept)

    nameless = {"t": "NONK1", "price": 1000}                            # 이름(nk) 없는 직접 추가 종목: 검색이 nk 를 읽다가 멈췄어요

    def custom_without_name():
        go_home()
        page.wait_for_timeout(1000)
        f = write("nameless.json", json.dumps({**export_head, "customStocks": [nameless], "holdings": [
            {"ticker": pick[0], "name": "삼성전자", "amountWon": 3000000}, {"ticker": "NONK1", "name": "이름 없는 회사", "amountWon": 1000000}]},
            ensure_ascii=False))
        n, errs = len(dialogs), len(R.errors)
        file_box.set_input_files(f)
        stage("② 구성")
        rows = poll(page, CART_ROWS, lambda v: len(v) >= 1, "목록에 있는 종목이 보이지 않아요")
        assert [v for _, v in rows] == ["300"] and len(dialogs) == n, (rows, dialogs[n:])     # 이름 없는 정의는 빠지고 그 종목은 저장본에만
        other = next(x.get("nk") for x in files["data.json"]["stocks"] if x.get("t") == pick[1])
        box = page.get_by_placeholder("종목명·코드 검색")
        box.fill(other)                                                 # 검색: 모든 종목의 nk 를 읽어요
        see(page, other)                                                # 담지 않은 종목이 검색 결과에 보여요
        box.fill("NONK")
        page.wait_for_timeout(500)
        assert len(R.errors) == errs, f"검색하다 페이지 오류: {R.errors[errs:]}"
        st = poll(page, newest, lambda v: bool(v) and any(h["t"] == "NONK1" for h in v["holdings"]), "불러온 포트폴리오가 저장되지 않았어요")
        assert st.get("customStocks") == [] and unnamed(st["holdings"]) == [{"t": pick[0], "mw": 300}, {"t": "NONK1", "mw": 100, "nk": "이름 없는 회사"}], \
            (st.get("customStocks"), st["holdings"])
    R.check(page, S, "이름 없는 직접 추가 종목이 든 파일 → 그 정의만 빼고 열림, 검색해도 오류 없음", custom_without_name)
    R.check(page, S, f"이름 없는 직접 추가 종목뿐인 파일 → '{IMPORT_FAIL}' 알림, 있던 포트폴리오 그대로",
            lambda: refused(write("nameless-only.json", json.dumps({**export_head, "customStocks": [nameless], "holdings": [
                {"ticker": "NONK1", "name": "이름 없는 회사", "amountWon": 1000000}]}, ensure_ascii=False)), "이름 없는 직접 추가 종목뿐"))
    ctx.close(); srv.shutdown()


def scene_ghost_holding(R, files):
    """오늘 종목 목록에 없는 종목(저장본에만 남은 종목)은 합계 · 목록 어디에서나 빠져요 (Jack 의 규칙, v18.4.1):
    담기 화면 · 공유 카드(종목 TOP · 현금 비율) · 첫 화면의 저장 목록('n종목'). 공유 카드를 만들 때는 console 에 뺐다고 남겨요."""
    have = {s.get("t") for s in files["data.json"]["stocks"]}
    gone = next(t for t in ("999999", "999998", "999997") if t not in have)
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000,
            "profile": {"ready": True, "source": "preset", "targetBetaMin": 0.6, "targetBetaMax": 1.2, "targetVolMaxPct": 40,
                        "stocksMin": 1, "stocksMax": 10, "maxPositionPct": 100, "maxSectorPct": 100, "cashFloorPct": 0},
            "holdings": [{"t": "005930", "mw": 300}, {"t": gone, "mw": 200, "nk": "없어진 회사"}]}
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "sgh", "name": "없는 종목 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_sgh": json.dumps(slot, ensure_ascii=False)}
    site = build_site(files)
    srv, ctx, page, base = R.open(site, local=local)
    S = "없는 종목"

    def card():
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.get_by_text("없는 종목 시험", exact=False).first.click()
        poll(page, CART_ROWS, lambda v: v == [["삼성전자", "300"]], "담기 화면에 삼성전자만 보여야 해요")
        page.evaluate("""() => { window.__drawn = []; const f = CanvasRenderingContext2D.prototype.fillText;
            CanvasRenderingContext2D.prototype.fillText = function (t, ...a) { window.__drawn.push(String(t)); return f.call(this, t, ...a); }; }""")
        n = len(R.console)
        page.get_by_role("button", name="포트폴리오 카드 만들기", exact=True).click()
        see(page, "이렇게 저장돼요")
        drawn = page.evaluate("window.__drawn")
        assert "담은 종목 TOP 1" in drawn and "삼성전자" in drawn, drawn                   # 없는 종목은 TOP 에 없어요
        assert gone not in drawn and "없어진 회사" not in drawn, drawn
        # v18.5 (Jack 2026-11-04): 없는 종목의 돈은 현금도 아니에요 → 국내 300 · 현금 500 (= 1,000 − 200 − 300) 으로 38% · 63%, 아래에 안내 줄
        assert "38%" in drawn and "63%" in drawn and "70%" not in drawn and "20%" not in drawn, drawn
        assert any(x.startswith("※ 오늘 데이터에 없는 종목 1개(없어진 회사 200만원)") for x in drawn), drawn
        assert any("공유 카드: 오늘 종목 목록에 없는 종목 1개는 빼고 만들었어요" in t for _, t in R.console[n:]), R.console[n:]
        page.get_by_role("button", name="닫기", exact=True).first.click()
    R.check(page, S, "삼성전자 300만원 + 없는 종목 200만원 → 공유 카드는 TOP 1 · 국내 38% · 현금 63% · 안내 줄, console 에 뺐다고 남김", card)

    def launch_count():
        page.wait_for_timeout(1200)                                    # 자동 저장(0.8초 뒤)이 목록의 'n종목'을 써요
        page.get_by_role("button", name="저장하고 나가기").first.click()
        see(page, "어떻게 시작할까요?")
        p = page.evaluate("JSON.parse(localStorage.getItem('baepsae_v10_slots'))[0].p")
        assert p["n"] == 1 and p["inv"] == 3000000, p
        line = page.evaluate(SMALLEST, ["없는 종목 시험", ["β "]])               # 이름 + '날짜 · n종목 · β … · 금액' 줄
        assert line and "· 1종목 ·" in line and "2종목" not in line, line
        slot_now = json.loads(page.evaluate("localStorage.getItem('baepsae_v10_slot_sgh')"))
        assert {"t": gone, "mw": 200, "nk": "없어진 회사"} in slot_now["holdings"], slot_now["holdings"]   # 저장본에는 그대로 남아요
    R.check(page, S, "첫 화면 저장 목록: '1종목' (없는 종목은 세지 않음), 저장본에는 그대로", launch_count)

    tmp = tempfile.mkdtemp(prefix="baepsae-ghost-")
    got = {}
    ghost_row = {"ticker": gone, "name": "없어진 회사", "sector": None, "priceAssumed": None, "amountWon": 2000000, "weightPct": None,
                 "approxShares": None, "beta": None, "volPct": None, "notInData": True}

    def backup():
        page.get_by_text("없는 종목 시험", exact=False).first.click()
        page.get_by_role("button", name="④ 내보내기", exact=False).first.click()
        with page.expect_download() as dl:
            page.get_by_role("button", name="JSON 저장 (백업·공유)").click()
        got["json"] = os.path.join(tmp, "ghost.json")
        dl.value.save_as(got["json"])
        text = open(got["json"], encoding="utf-8").read()
        j = json.loads(text)
        assert "NaN" not in text and "Infinity" not in text, "백업 파일에 NaN"
        assert [h["ticker"] for h in j["holdings"]] == ["005930", gone] and j["holdings"][1] == ghost_row, j["holdings"]
        assert j["holdings"][0]["weightPct"] == 100.0, j["holdings"][0]              # 비중 · 위험 수치는 목록에 있는 종목만으로
        assert all(isinstance(v, (int, float)) for v in j["metrics"].values()), j["metrics"]
        with page.expect_download() as dl:
            page.get_by_role("button", name="CSV 저장 (주문표)").click()
        csv = os.path.join(tmp, "ghost.csv")
        dl.value.save_as(csv)
        lines = open(csv, encoding="utf-8-sig").read().splitlines()
        assert lines[1].startswith("005930,") and lines[2].startswith("CASH,") and not any(gone in ln for ln in lines), lines   # 주문표는 목록에 있는 종목만
    R.check(page, S, "JSON 저장: 없는 종목도 백업에 (종목코드 · 이름 · 금액 · notInData, 나머지 null) · CSV 주문표에는 없음 · NaN 없음", backup)
    ctx.close()

    ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
    ctx.add_init_script("(() => { try { localStorage.setItem('baepsae_v9_seen', '1'); } catch (e) {} })();")
    page = ctx.new_page()
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    page.on("console", lambda m: R.console.append((m.type, m.text)))
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))

    def restore():
        assert "json" in got, "앞 단계에서 파일을 받지 못했어요"
        page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
        page.get_by_text("차근차근 만들기", exact=True).click()
        see(page, "어떻게 시작할까요?")
        page.locator('input[type=file][accept="application/json,.json"]').set_input_files(got["json"])
        page.get_by_role("button", name="② 구성", exact=False).first.click()
        poll(page, CART_ROWS, lambda v: v == [["삼성전자", "300"]], "불러온 뒤 담기 화면에 삼성전자만 보여야 해요")
        assert not dialogs, dialogs
        st = poll(page, """() => { const l = JSON.parse(localStorage.getItem('baepsae_v10_slots') || '[]');
            return l.length ? JSON.parse(localStorage.getItem('baepsae_v10_slot_' + l[0].id) || 'null') : null; }""",
                  lambda v: bool(v), "불러온 포트폴리오가 저장되지 않았어요")
        # 둘 다 남아요 (v18.5: 저장할 때 목록에 있는 국내 종목에는 이름이 붙어요)
        assert [(h["t"], h["mw"], h.get("nk")) for h in st["holdings"]] == [("005930", 300, "삼성전자"), (gone, 200, "없어진 회사")], st["holdings"]
        assert "NaN" not in page.locator("body").inner_text()
        page.evaluate("""() => { window.__drawn = []; const f = CanvasRenderingContext2D.prototype.fillText;
            CanvasRenderingContext2D.prototype.fillText = function (t, ...a) { window.__drawn.push(String(t)); return f.call(this, t, ...a); }; }""")
        page.get_by_role("button", name="포트폴리오 카드 만들기", exact=True).click()
        see(page, "이렇게 저장돼요")
        drawn = page.evaluate("window.__drawn")
        assert "담은 종목 TOP 1" in drawn and "63%" in drawn and "없어진 회사" not in drawn and gone not in drawn, drawn
        page.get_by_role("button", name="닫기", exact=True).first.click()
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="저장하고 나가기").first.click()
        see(page, "어떻게 시작할까요?")
        line = page.evaluate(SMALLEST, ["불러온 포트폴리오", ["β "]])
        assert line and "· 1종목 ·" in line, line
    R.check(page, S, "그 백업을 새 브라우저에서 불러오기 → 저장본에 두 종목 그대로(없는 종목은 숨김) · 카드 TOP 1 · '1종목' · NaN 없음", restore)

    def restored_notice():
        # v18.5: 불러온 백업의 notInData 줄도 '빠진 종목' 안내에 이름·금액으로 나오고, '포트폴리오에서 빼기'로만 저장본에서 지워져요
        page.get_by_text("불러온 포트폴리오", exact=False).first.click()
        page.get_by_role("button", name="② 구성", exact=False).first.click()
        see(page, MISSING.format(n=1, names="없어진 회사 200만원"))
        assert page.locator(".cartHead").inner_text().startswith("300 + 200 / 1,000"), page.locator(".cartHead").inner_text()
        page.locator(".missingRemove", has_text=MISSING_REMOVE).first.click()
        st = poll(page, """() => { const l = JSON.parse(localStorage.getItem('baepsae_v10_slots') || '[]');
            const s = l.find((x) => x.name === '불러온 포트폴리오'); return s ? localStorage.getItem('baepsae_v10_slot_' + s.id) : null; }""",
                  lambda v: v and gone not in v, "'포트폴리오에서 빼기' 뒤에도 저장본에 없는 종목이 남아 있어요")
        assert [h["t"] for h in json.loads(st)["holdings"]] == ["005930"], st
        assert page.get_by_text("빼고 계산했어요").count() == 0, "뺐는데 안내가 남아 있어요"
    R.check(page, S, "불러온 백업의 없는 종목: 안내 '없어진 회사 200만원' · 머리말 300 + 200 / 1,000 → '포트폴리오에서 빼기' → 저장본에서 빠짐", restored_notice)
    ctx.close(); srv.shutdown()
    shutil.rmtree(site, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)


def scene_import_while_loading(R, files):
    """'저장한 파일에서 불러오기'와 오늘 데이터 읽기 (v18.4.1, Jack 2026-11-04).
      · data.json 이 늦게 오는 동안에는 파일 고르기가 화면에 없어요(부팅 화면). 다 읽은 바로 뒤에 고른 파일은 종목 · 직접 추가 종목이
        파일 그대로 열려요 (부팅이 파일 내용을 덮지 않아요). 이 파일의 환율은 직접 입력한 값(typedKeys ["fx"])이라 그대로여야 해요.
        typedKeys 가 없는 파일의 '자동' 칸은 오늘 값으로 열려요 (Jack 2026-11-04 승인, 장면 '자동 설정').
      · data.json 을 못 읽은 날: 파일을 불러오지 않고 '데이터를 불러오지 못했어요…' 알림('파일을 읽을 수 없어요.' 아님), 저장본은 그대로."""
    tmp = tempfile.mkdtemp(prefix="baepsae-boot-")
    try:
        _import_while_loading(R, files, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class SlowData(QuietHandler):
    """data.json 만 DELAY 초 늦게 줘요 (다른 파일은 바로)."""
    DELAY = 4

    def do_GET(self):
        if self.path.split("?")[0].endswith("/data.json"):
            time.sleep(self.DELAY)
        return super().do_GET()


def _import_while_loading(R, files, tmp):
    S = "불러오기 · 데이터 읽기"
    have = {s.get("t") for s in files["data.json"]["stocks"]}
    pick = [t for t in ("005930", "000660") if t in have]
    fx = 1234.5                                                         # 오늘 환율과 다른, 직접 입력한 값 (typedKeys ["fx"]) — 부팅이 덮으면 오늘 값이 돼요
    today = files["data.json"].get("fx")
    assert isinstance(today, (int, float)) and today != fx, today
    backup = {"app": "Baepsae 뱁새 v12", "budgetWon": 20000000, "settings": {"fx": fx}, "typedKeys": ["fx"], "customStocks": [MINE],
              "holdings": [{"ticker": pick[0], "amountWon": 3000000}, {"ticker": pick[1], "amountWon": 2000000},
                           {"ticker": MINE["t"], "amountWon": 1000000}]}
    path = os.path.join(tmp, "backup.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(backup, fh, ensure_ascii=False)
    site = os.path.join(tmp, "site")
    shutil.move(build_site(files), site)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(SlowData, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
    ctx.add_init_script("(() => { try { localStorage.setItem('baepsae_v9_seen', '1'); } catch (e) {} })();")
    page = ctx.new_page()
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    box = page.locator('input[type=file][accept="application/json,.json"]')

    def slow():
        t0 = time.time()
        page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
        page.get_by_text("차근차근 만들기", exact=True).click()
        page.wait_for_timeout(1000)
        assert time.time() - t0 < SlowData.DELAY - 1, "data.json 이 늦게 오는 동안을 보지 못했어요"
        assert box.count() == 0 and page.get_by_text("저장한 파일에서 불러오기").count() == 0, "데이터를 읽기 전에 파일 고르기가 보여요"
        box.wait_for(state="attached", timeout=WAIT)                    # 다 읽은 뒤에 나와요
        box.set_input_files(path)                                       # 나오자마자 골라요
        page.get_by_role("button", name="② 구성", exact=False).first.click()
        rows = poll(page, CART_ROWS, lambda v: len(v) == 3, "불러온 종목이 다 보이지 않아요")
        assert [v for _, v in rows] == ["300", "200", "100"] and rows[2][0] == MINE["nk"], rows
        assert not dialogs, dialogs
        st = poll(page, """() => { const l = JSON.parse(localStorage.getItem('baepsae_v10_slots') || '[]');
            return l.length ? JSON.parse(localStorage.getItem('baepsae_v10_slot_' + l[0].id) || 'null') : null; }""",
                  lambda v: bool(v), "불러온 포트폴리오가 저장되지 않았어요")
        assert st["customStocks"] == [MINE] and len(st["holdings"]) == 3, st     # 부팅이 직접 추가 종목을 덮지 않았어요
        # 직접 입력한 환율은 파일 그대로: 부팅이 오늘 환율로 덮지 않았어요 (리뷰 2026-11-04). typedKeys 없는 파일 → 오늘 값은 '자동 설정' 장면이 봐요
        assert st["settings"]["fx"] == fx and st["typedKeys"] == ["fx"], (st["settings"]["fx"], st.get("typedKeys"))
    R.check(page, S, "data.json 이 4초 늦음 → 그동안 파일 고르기 없음, 다 읽은 뒤 고른 파일은 종목 · 직접 추가 종목 · 직접 입력한 환율 그대로", slow)
    ctx.close(); srv.shutdown()

    # data.json 을 못 읽은 날 (404)
    os.remove(os.path.join(site, "data.json"))
    srv, base = serve(site)
    slot = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": [{"t": "005930", "mw": 300}]}
    local = {"baepsae_v9_seen": "1", "baepsae_v10_slots": json.dumps([{"id": "skeep", "name": "그대로 시험"}], ensure_ascii=False),
             "baepsae_v10_slot_skeep": json.dumps(slot, ensure_ascii=False)}
    ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
    ctx.add_init_script("(() => { try { if (!sessionStorage.getItem('seeded')) { const kv = %s; for (const k in kv) localStorage.setItem(k, kv[k]);"
                        " sessionStorage.setItem('seeded', '1'); } } catch (e) {} })();" % json.dumps(local, ensure_ascii=False))
    page = ctx.new_page()
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    dialogs.clear()
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    box = page.locator('input[type=file][accept="application/json,.json"]')
    stored = """() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i);
        if (k.startsWith('baepsae_v10_')) o[k] = localStorage.getItem(k); } return o; }"""

    def failed():
        page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
        page.get_by_text("차근차근 만들기", exact=True).click()
        see(page, NOLIVE_ALL)                                            # 오늘 데이터를 못 읽었다는 안내 (이미 있던 것)
        box.wait_for(state="attached", timeout=WAIT)
        before = page.evaluate(stored)
        box.set_input_files(path)
        poll(page, "1", lambda _: len(dialogs) > 0, "알림이 뜨지 않았어요")
        assert dialogs == [T_LOAD_FAIL_KO], dialogs                      # '파일을 읽을 수 없어요.'가 아니에요
        page.wait_for_timeout(1200)
        see(page, "어떻게 시작할까요?")
        assert page.evaluate(stored) == before, "데이터를 못 읽은 날 저장본이 바뀌었어요"
    R.check(page, S, "data.json 을 못 읽은 날 → 불러오지 않고 '데이터를 불러오지 못했어요…' 알림, 저장본 그대로", failed)
    ctx.close(); srv.shutdown()


def scene_auto_settings(R, files):
    """'자동' 설정은 오늘 값으로 (v18.6, Jack 2026-11-04). 전에는 지난달 저장본이 지난달 환율을 '자동' 칩과 함께 보여 줬어요.
      · 자동으로 둔 환율 1,300 으로 저장한 포트폴리오, 오늘 환율 1,450 → 다시 열면 1,450 · '자동';
      · 예전 저장본(직접 입력 기록 typedKeys 없음) → 오늘 값 · '자동', console 에 바꾼 개수;
      · 설정에서 직접 입력한 1,234.5 → '가정', 새로 고침 뒤 다시 열어도 · JSON 저장 → 새 브라우저에서 불러와도 1,234.5 · '가정';
      · typedKeys 없는 예전 파일을 불러오면 오늘 값 · '자동';
      · (v18.6.1) '새로 시작하기'와 읽을 설정이 없는 파일은 앞 포트폴리오의 설정 · 직접 입력 기록을 잇지 않고 기본값 + 오늘 값 · '자동'."""
    tmp = tempfile.mkdtemp(prefix="baepsae-auto-")
    try:
        _auto_settings(R, files, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


AUTO_TAG, ASSUME_TAG = "자동", "가정"          # 설정 화면의 칩 (이미 있는 문구)
NEWEST_SLOT = """() => { const l = JSON.parse(localStorage.getItem('baepsae_v10_slots') || '[]');
  return l.length ? [l[0].name, JSON.parse(localStorage.getItem('baepsae_v10_slot_' + l[0].id) || 'null')] : null; }"""   # 맨 앞 = 방금 저장한 것


def _auto_settings(R, files, tmp):
    S = "자동 설정"
    today, old, typed = 1450.0, 1300.0, 1234.5
    data = json.loads(json.dumps(files, allow_nan=True))
    data["data.json"]["fx"] = today
    rf = (data["data.json"].get("settings") or {}).get("rf")
    hold = [{"t": "005930", "mw": 300}]
    body = {"schema": 10, "lang": "ko", "stage": 1, "budgetMw": 1000, "holdings": hold}
    slots = [("sauto", "자동 환율 시험", {**body, "settings": {"fx": old, "rf": 9.9}, "typedKeys": []}),
             ("slegacy", "예전 저장본 시험", {**body, "settings": {"fx": old, "rf": 9.9}})]
    site = os.path.join(tmp, "site")
    shutil.move(build_site(data), site)
    srv, ctx, page, base = R.open(site, local=slot_local(slots), once=True)
    logs = []
    page.on("console", lambda m: logs.append(m.text))

    def field(k):
        """설정 화면의 한 칸: (입력값, 칩)."""
        row = page.locator(f'[data-set="{k}"]').first
        row.wait_for(state="visible", timeout=WAIT)
        chip = AUTO_TAG if row.get_by_text(AUTO_TAG, exact=True).count() else ASSUME_TAG if row.get_by_text(ASSUME_TAG, exact=True).count() else None
        return float(row.locator("input").input_value()), chip

    def settings_shown(k="fx"):
        page.locator("button.openSettings").first.click()
        v = field(k)
        return v

    def close_settings():
        # 바깥(위쪽 어두운 곳)을 눌러 닫아요: 휴대폰 크기에서는 맨 아래 '닫기' 버튼이 아래 탭 막대에 가려져요 (따로 고칠 일)
        page.mouse.click(195, 40)
        page.locator('[data-set="fx"]').first.wait_for(state="detached", timeout=WAIT)

    def open_slot(name):
        page.get_by_text(name, exact=False).first.click()
        page.locator("button.openSettings").first.wait_for(state="visible", timeout=WAIT)

    def go_home():
        page.locator('button[title="저장하고 나가기"]').first.click()
        see(page, "어떻게 시작할까요?")

    def saved_auto():
        page.get_by_text("차근차근 만들기", exact=True).click()
        open_slot("자동 환율 시험")
        assert settings_shown() == (today, AUTO_TAG), field("fx")
        if isinstance(rf, (int, float)):
            assert field("rf") == (rf, AUTO_TAG), field("rf")                    # 시장 가정도 오늘 값
        assert field("mrp")[1] == ASSUME_TAG, field("mrp")                       # 오늘 데이터가 주지 않는 칸은 '가정'
        close_settings()
        st = poll(page, f"() => JSON.parse(localStorage.getItem('baepsae_v10_slot_sauto'))", lambda v: v and v["settings"]["fx"] == today,
                  "다시 연 저장본에 오늘 환율이 저장되지 않았어요")
        assert st["typedKeys"] == [], st.get("typedKeys")
        assert any("자동 설정" in x and "fx 1300 → 1450" in x for x in logs), logs     # 바꾼 값을 console 에 남겨요
    R.check(page, S, "자동으로 둔 환율 1,300 으로 저장 · 오늘 1,450 → 다시 열면 1,450 '자동' (rf 도 오늘 값, mrp 는 '가정') · console 에 바꾼 값", saved_auto)

    def legacy_slot():
        go_home()
        logs.clear()
        open_slot("예전 저장본 시험")
        assert settings_shown() == (today, AUTO_TAG), field("fx")
        close_settings()
        line = next((x for x in logs if "typedKeys" in x and "예전 저장본" in x), None)
        assert line and "바뀐 값" in line and "fx 1300 → 1450" in line, logs
    R.check(page, S, "예전 저장본(typedKeys 없음) → 오늘 환율 1,450 '자동' · console 에 바꾼 개수", legacy_slot)

    def type_fx():
        go_home()
        open_slot("자동 환율 시험")
        settings_shown()
        page.locator('[data-set="fx"] input').first.fill(str(typed))
        assert field("fx") == (typed, ASSUME_TAG), field("fx")                   # 직접 입력하면 '가정'
        close_settings()
        st = poll(page, "() => JSON.parse(localStorage.getItem('baepsae_v10_slot_sauto'))", lambda v: v and v["settings"]["fx"] == typed,
                  "직접 입력한 환율이 저장되지 않았어요")
        assert st["typedKeys"] == ["fx"], st.get("typedKeys")
        page.reload(wait_until="domcontentloaded")                              # 새로 고침 뒤 다시 열어도 그대로
        page.get_by_text("차근차근 만들기", exact=True).click()
        open_slot("자동 환율 시험")
        assert settings_shown() == (typed, ASSUME_TAG), field("fx")
        close_settings()
    R.check(page, S, "설정에서 환율 1,234.5 직접 입력 → '가정' · typedKeys ['fx'] 저장 · 새로 고침 뒤 다시 열어도 1,234.5 '가정'", type_fx)

    got = {}

    def export():
        page.get_by_role("button", name="④ 내보내기", exact=False).first.click()
        with page.expect_download() as dl:
            page.get_by_role("button", name="JSON 저장 (백업·공유)").click()
        got["json"] = os.path.join(tmp, "typed.json")
        dl.value.save_as(got["json"])
        with open(got["json"], encoding="utf-8") as fh:
            j = json.load(fh)
        assert j["settings"]["fx"] == typed and j["typedKeys"] == ["fx"], (j["settings"].get("fx"), j.get("typedKeys"))
    R.check(page, S, "JSON 저장 파일에 환율 1,234.5 와 typedKeys ['fx']", export)

    def new_slot():
        # v18.6.1 (Jack 2026-11-04): 새 포트폴리오는 앞 포트폴리오의 설정 · 직접 입력 기록을 잇지 않고 기본값 + 오늘 값으로 시작해요
        go_home()
        logs.clear()
        page.get_by_text("새로 시작하기", exact=False).first.click()
        page.locator("button.openSettings").first.wait_for(state="visible", timeout=WAIT)
        assert settings_shown() == (today, AUTO_TAG), field("fx")
        close_settings()
        name, st = poll(page, NEWEST_SLOT, lambda v: v and v[0] not in ("자동 환율 시험", "예전 저장본 시험") and v[1],
                        "새 포트폴리오가 저장되지 않았어요")
        assert st["settings"]["fx"] == today and st["typedKeys"] == [], (name, st["settings"]["fx"], st.get("typedKeys"))
        assert any("새로 시작하기" in x and "fx 1234.5 → 1450" in x for x in logs), logs     # 바꾼 것을 console 에 남겨요
    R.check(page, S, "환율 1,234.5 를 입력한 포트폴리오에서 나와 '새로 시작하기' → 오늘 1,450 '자동' · typedKeys [] 저장 · console 에 바꾼 값", new_slot)
    ctx.close(); srv.shutdown()

    # 새 브라우저 (빈 저장소)
    srv, ctx, page, base = R.open(site, local={"baepsae_v9_seen": "1"})
    logs = []
    page.on("console", lambda m: logs.append(m.text))
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    box = page.locator('input[type=file][accept="application/json,.json"]')
    oldfile = os.path.join(tmp, "old.json")
    with open(oldfile, "w", encoding="utf-8") as fh:
        json.dump({"app": "Baepsae 뱁새 v12", "budgetWon": 10000000, "settings": {"fx": old},
                   "holdings": [{"ticker": "005930", "amountWon": 3000000}]}, fh, ensure_ascii=False)

    def import_typed():
        assert "json" in got, "앞 단계에서 파일을 받지 못했어요"
        page.get_by_text("차근차근 만들기", exact=True).click()
        see(page, "어떻게 시작할까요?")
        box.set_input_files(got["json"])
        page.locator("button.openSettings").first.wait_for(state="visible", timeout=WAIT)
        assert settings_shown() == (typed, ASSUME_TAG), field("fx")
        close_settings()
        assert not dialogs, dialogs
        st = poll(page, """() => { const l = JSON.parse(localStorage.getItem('baepsae_v10_slots') || '[]');
            return l.length ? JSON.parse(localStorage.getItem('baepsae_v10_slot_' + l[0].id) || 'null') : null; }""",
                  lambda v: bool(v), "불러온 포트폴리오가 저장되지 않았어요")
        assert st["settings"]["fx"] == typed and st["typedKeys"] == ["fx"], (st["settings"]["fx"], st.get("typedKeys"))
    R.check(page, S, "그 파일을 새 브라우저에서 불러오기 → 1,234.5 '가정' (typedKeys 도 저장본에)", import_typed)

    nosettings = os.path.join(tmp, "nosettings.json")
    with open(nosettings, "w", encoding="utf-8") as fh:                  # 설정 칸이 있지만 읽을 수 없어요 (숫자가 아님)
        json.dump({"app": "Baepsae 뱁새 v12", "budgetWon": 10000000, "settings": {"fx": "1300"}, "typedKeys": ["fx"],
                   "holdings": [{"ticker": "005930", "amountWon": 3000000}]}, fh, ensure_ascii=False)

    def import_no_settings():
        # v18.6.1: 읽을 설정이 없는 파일 → 앞 포트폴리오(직접 입력 1,234.5)의 설정 · 기록을 잇지 않고 기본값 + 오늘 값
        go_home()
        logs.clear()
        box.set_input_files(nosettings)
        page.locator("button.openSettings").first.wait_for(state="visible", timeout=WAIT)
        assert settings_shown() == (today, AUTO_TAG), field("fx")
        close_settings()
        assert not dialogs, dialogs
        name, st = poll(page, NEWEST_SLOT, lambda v: v and v[1] and v[1]["settings"]["fx"] != typed, "불러온 포트폴리오가 저장되지 않았어요")
        assert st["settings"]["fx"] == today and st["typedKeys"] == [], (name, st["settings"]["fx"], st.get("typedKeys"))
        assert any("읽을 설정이 없는 파일" in x and "fx 1234.5 → 1450" in x for x in logs), logs
    R.check(page, S, "읽을 설정이 없는 파일 불러오기 (앞 포트폴리오는 1,234.5 직접 입력) → 오늘 1,450 '자동' · typedKeys [] · console 에 바꾼 값", import_no_settings)

    def import_old():
        go_home()
        logs.clear()
        box.set_input_files(oldfile)
        page.locator("button.openSettings").first.wait_for(state="visible", timeout=WAIT)
        assert settings_shown() == (today, AUTO_TAG), field("fx")
        close_settings()
        assert not dialogs, dialogs
        line = next((x for x in logs if "typedKeys" in x and "예전 저장본" in x), None)
        assert line and "fx 1300 → 1450" in line, logs
    R.check(page, S, "typedKeys 없는 예전 파일(환율 1,300) 불러오기 → 오늘 1,450 '자동' · console 에 바꾼 개수", import_old)
    ctx.close(); srv.shutdown()


HEADER_ITEMS = """() => [...document.querySelector('.mastRow').children].filter((e) => getComputedStyle(e).display !== 'none'
  && e.getBoundingClientRect().width).map((e) => { const r = e.getBoundingClientRect(); return [e.dataset.v2Link ? 'v2' : e.tagName, r.left, r.right]; })"""


# v19.0c: 뱁새 2.0 이 여는 바로가기 (src/deeplink.js): #macro · #disc · #corp=코드 · #info=glossary|sources 를 처음 열 때 한 번 읽고
# 주소에서 지워요 (기록을 늘리지 않아서 그 화면에서 뒤로 가면 온 곳으로). 그 뒤의 뒤로 가기는 예전처럼 NAV 가 맡아요.
ACTIVE_TAB = "() => { const b = [...document.querySelectorAll('nav.botNav button')].find((x) => getComputedStyle(x.querySelector('span')).fontWeight === '800'); return b ? b.innerText.trim() : null; }"


def scene_deep_links(R, files):
    site = build_site(files)
    srv, ctx, page, base = R.open(site)
    S = "2.0 바로가기"
    co = next(c for c in files["corp.json"]["companies"] if c.get("t") == "005930")

    def fresh(h):
        page.goto("about:blank")                                         # 새 문서로 열어요 (주소의 # 만 바꾸면 같은 페이지 안의 이동)
        page.goto(base + "/baepsae.html?dev=1" + h, wait_until="domcontentloaded")

    def tabs():
        for h, label, marker in (("#macro", "금리·원자재", "국고채"), ("#disc", "공시·수급", "국민연금")):
            fresh(h)
            page.wait_for_function("() => location.hash === ''")           # 읽고 지워요
            poll(page, ACTIVE_TAB, lambda v: v == label, f"{h} → {label} 탭")
            see(page, marker)
            assert page.get_by_text("내 종목, 괜찮은 걸까요?").count() == 0, h
            page.go_back()                                                # 뒤로 한 번 → 온 곳 (바로가기는 기록을 쌓지 않아요)
            page.wait_for_url("about:blank")
    R.check(page, S, "#macro → 금리·원자재 · #disc → 공시·수급 (주소의 # 은 지워지고, 뒤로 한 번이면 온 곳으로)", tabs)

    def corp():
        fresh("#corp=005930")
        page.wait_for_function("() => location.hash === ''")
        poll(page, ACTIVE_TAB, lambda v: v == "기업분석", "#corp → 기업분석 탭")
        see(page, co["nk"])
        see(page, "밸류에이션 멀티플 · 업종 사분위 대비")                       # 그 회사 화면의 01 투자지표 (시장 지도가 아니라)
        assert page.get_by_text("이 종목의 데이터를 찾지 못했어요.").count() == 0
        tab(page, "정보")                                                 # 그 뒤로는 예전처럼: 탭을 바꾸면 뒤로가 그 탭을 되돌려요
        poll(page, ACTIVE_TAB, lambda v: v == "정보", "정보 탭")
        page.go_back()                                                    # (다시 연 기업분석은 예전처럼 시장 지도부터)
        poll(page, ACTIVE_TAB, lambda v: v == "기업분석", "뒤로 → 기업분석")
        page.go_back()                                                    # 그 회사 화면이 첫 화면이었어요: 한 번 더 뒤로 → 온 곳
        page.wait_for_url("about:blank")
        fresh("#corp=999999")                                             # 없는 코드: 기업분석이 '찾지 못했어요' (지어내지 않아요)
        poll(page, ACTIVE_TAB, lambda v: v == "기업분석", "없는 코드 → 기업분석 탭")
        see(page, "이 종목의 데이터를 찾지 못했어요.")
    R.check(page, S, "#corp=005930 → 기업분석의 삼성전자 화면 (그 뒤 NAV 뒤로 가기는 그대로, 뒤로 두 번 → 온 곳) · 없는 코드는 '찾지 못했어요'", corp)

    def info():
        for h, card, title in (("#info=glossary", "info-glossary", "용어 사전"), ("#info=sources", "info-sources", "데이터 출처와 갱신")):
            fresh(h)
            page.wait_for_function("() => location.hash === ''")
            poll(page, ACTIVE_TAB, lambda v: v == "정보", f"{h} → 정보 탭")
            top = poll(page, f"(() => {{ const e = document.getElementById('{card}'); return e ? Math.round(e.getBoundingClientRect().top) : null; }})()",
                       lambda v: v is not None and 0 <= v <= 120, f"{h} → {title} 카드가 맨 위로")
            assert page.locator(f"#{card}").inner_text().startswith(title), (h, page.locator(f"#{card}").inner_text()[:20])
            assert page.evaluate("window.scrollY") > 0 and top is not None
    R.check(page, S, "#info=glossary → 용어 사전 카드 · #info=sources → 데이터 출처 카드 (정보 탭, 그 카드로 스크롤)", info)

    def unknown():
        for h in ("#foo", "#corp=", "#info=terms", "#about"):
            fresh(h)
            see(page, "내 종목, 괜찮은 걸까요?")                            # 모르는 # 은 아무것도 하지 않고 그대로 둬요
            assert page.evaluate("location.hash") == h, (h, page.evaluate("location.hash"))
            assert page.evaluate(ACTIVE_TAB) == "포트폴리오", h
    R.check(page, S, "모르는 # (#foo · #corp= · #info=terms · #about) → 예전처럼 첫 화면, 주소도 그대로", unknown)
    ctx.close()
    srv.shutdown()


def scene_v2_link(R, files):
    site = build_site(files)
    shutil.copy(os.path.join(ROOT, "app.html"), site)            # 링크가 여는 2.0 (커밋한 빌드 결과)
    for f in ("baepi-mark.webp", "baepi-16-build.webp", "baepi-15-portfolio.webp", "baepi-20-error.webp", "baepi-21-wip.webp"):
        shutil.copy(os.path.join(ROOT, f), site)                 # 그 2.0 이 보여 주는 그림 (v19.0b)
    srv, base = serve(site)
    for w in (320, 390):
        ctx = R.browser.new_context(viewport={"width": w, "height": 844}, device_scale_factor=2, locale="ko-KR", service_workers="block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        page = ctx.new_page()
        page.on("pageerror", lambda e: R.errors.append(str(e)))
        page.goto(base + "/baepsae.html?dev=1", wait_until="domcontentloaded")
        S = f"2.0 링크 {w}"
        link = page.locator("a[data-v2-link]")

        def shown():
            see(page, "내 종목, 괜찮은 걸까요?")
            link.wait_for(state="visible")
            assert link.inner_text() == "뱁새 2.0 보기" and link.get_attribute("href") == "./app.html"
            box = link.bounding_box()
            assert box and box["height"] >= 44 and box["x"] >= 0 and box["x"] + box["width"] <= w, box
            items = sorted(page.evaluate(HEADER_ITEMS), key=lambda x: x[1])
            assert all(a[2] <= b[1] + 0.5 for a, b in zip(items, items[1:])) and items[-1][2] <= w, items   # 겹치지 않고 화면 안
            assert page.evaluate("document.documentElement.scrollWidth") <= w
        R.check(page, S, "첫 화면 머리말에 '뱁새 2.0 보기' (높이 44 이상 · 겹침 없음 · 가로 스크롤 없음)", shown)

        def in_mode():
            page.get_by_text("차근차근 만들기", exact=True).click()
            close_welcome(page, "시작하기")
            page.get_by_text("모드 선택", exact=True).first.wait_for(state="visible", timeout=WAIT)
            page.add_style_tag(content=".pwaBack { display: inline-flex !important }")   # 홈 화면 앱의 '뒤로'까지 있는 머리말
            page.wait_for_timeout(150)
            items = page.evaluate(HEADER_ITEMS)
            assert max(r for _, _, r in items) <= w, items
            assert page.evaluate("document.documentElement.scrollWidth") <= w
            page.get_by_text("모드 선택", exact=True).first.click()
            link.wait_for(state="visible")                                              # 첫 화면으로 오면 다시 보여요
        R.check(page, S, "모드 안(모드 선택 · 뒤로)에서도 머리말이 화면을 넘지 않고, 첫 화면에서 다시 보여요", in_mode)

        def english():
            page.get_by_role("button", name="EN", exact=True).first.click()
            see(page, "Is my stock doing okay?")
            assert link.count() == 0, "2.0 은 한국어만 있어요: 영어 화면에는 링크가 없어요"
            page.get_by_role("button", name="한국어", exact=True).first.click()
            link.wait_for(state="visible")
        R.check(page, S, "영어 화면에는 없음 (2.0 은 한국어만)", english)

        def opens():
            with page.expect_navigation():
                link.click()
            page.wait_for_function("() => location.pathname.endsWith('/app.html') && location.hash === '#home'")   # v19.0c: 2.0 이 그 자리에서 #home
            page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible", timeout=WAIT)
        R.check(page, S, "누르면 app.html (뱁새 2.0, 그 자리에서 #home)", opens)
        ctx.close()
    srv.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=ROOT, help="data/corp/disc/macro.json 이 있는 폴더")
    ap.add_argument("--shots", default=None, help="실패 시 스크린샷을 저장할 폴더")
    ap.add_argument("--only", default=None, help="이 장면만 (정상·멈춤·NaN·corp·data·금·금리·위험값·B안·빠진·베타·서비스워커·2.0링크·바로가기·파일·자동)")
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
                  ("금", lambda: scene_gold_estimate(R, fresh)), ("금리", lambda: scene_rates_fail(R, fresh)), ("위험값", lambda: scene_no_risk_holding(R, fresh)), ("B안", lambda: scene_option_b(R, fresh)), ("해외", lambda: scene_foreign_issuer(R, fresh)), ("B안", lambda: scene_simple_no_forecast(R, fresh)), ("빠진", lambda: scene_missing_holding(R, fresh)), ("빠진", lambda: scene_missing_all(R, fresh)), ("베타", lambda: scene_beta_return(R, fresh)),
                  ("서비스워커", lambda: scene_service_worker(R, fresh)), ("2.0링크", lambda: scene_v2_link(R, fresh)), ("바로가기", lambda: scene_deep_links(R, fresh)),
                  ("파일", lambda: scene_json_import(R, fresh)), ("파일", lambda: scene_ghost_holding(R, fresh)),
                  ("파일", lambda: scene_import_while_loading(R, fresh)), ("자동", lambda: scene_auto_settings(R, fresh))]
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
