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
  서비스워커  예전 v10 워커의 얼어붙은 corp.json 이 새 워커로 바뀌고 baepsae-v10 캐시가 지워짐
  2.0 링크    머리말 '뱁새 2.0 보기' (Jack, 2026-11-02): 320 · 390 에서 보임 · 누르는 높이 44 이상 · 다른 머리말 항목과 겹치지 않음 ·
              가로 스크롤 없음 · app.html 로 감 · 영어 화면에는 없음 · 좁은 휴대폰의 모드 안(홈 화면 '뒤로' 포함)에서도 머리말이 넘치지 않음
  파일        (v18.4.1) 'JSON 저장 (백업·공유)' 파일 → 새 브라우저에서 '저장한 파일에서 불러오기' → 같은 종목·금액·예산 ·
              종목 없는 파일 · 깨진 파일 · 줄이 모두 틀린 파일은 '파일을 읽을 수 없어요.' 알림만 (있던 포트폴리오 그대로) · 예전 모양 파일도 열림
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

    def open(self, site, sw=False, local=None):
        srv, base = serve(site)
        # is_mobile 을 켜면 기업분석 화면이 폭 390px 보다 넓어(약 530px) 크롬이 화면을 축소하고,
        # 그러면 탭 클릭 좌표가 어긋나요. 그래서 크기만 휴대폰(390×844)으로 맞춥니다.
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="ko-KR",
                                       service_workers="allow" if sw else "block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        if local:
            ctx.add_init_script("(() => { try { const kv = %s; for (const k in kv) localStorage.setItem(k, kv[k]); } catch (e) {} })();"
                                % json.dumps(local, ensure_ascii=False))
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
            self.results.append((label, False, str(e).splitlines()[0][:160]))
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
               "Foreign capital gains", "NaN"]
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
        assert st["holdings"] == [{"t": pick[0], "mw": 300}, {"t": gone, "mw": 200, "nk": "없는 회사"}], st["holdings"]
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
        assert st.get("customStocks") == [] and st["holdings"] == [{"t": pick[0], "mw": 300}, {"t": "NONK1", "mw": 100, "nk": "이름 없는 회사"}], \
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
        assert "30%" in drawn and "70%" in drawn and "50%" not in drawn and "20%" not in drawn, drawn   # 국내 30% · 현금 70% (1,000만원 중)
        assert any("공유 카드: 오늘 종목 목록에 없는 종목 1개는 빼고 만들었어요" in t for _, t in R.console[n:]), R.console[n:]
        page.get_by_role("button", name="닫기", exact=True).first.click()
    R.check(page, S, "삼성전자 300만원 + 없는 종목 200만원 → 공유 카드는 TOP 1 · 현금 70%, console 에 뺐다고 남김", card)

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
        assert lines[2] == f"{gone},없어진 회사,,,2000000,,,," and lines[1].startswith("005930,"), lines   # 금액만, 나머지 칸은 비워요
    R.check(page, S, "JSON 저장: 없는 종목도 백업에 (종목코드 · 이름 · 금액 · notInData, 나머지 null) · CSV 에도 금액만 · NaN 없음", backup)
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
        assert st["holdings"] == [{"t": "005930", "mw": 300}, {"t": gone, "mw": 200, "nk": "없어진 회사"}], st["holdings"]   # 둘 다 남아요
        assert "NaN" not in page.locator("body").inner_text()
        page.evaluate("""() => { window.__drawn = []; const f = CanvasRenderingContext2D.prototype.fillText;
            CanvasRenderingContext2D.prototype.fillText = function (t, ...a) { window.__drawn.push(String(t)); return f.call(this, t, ...a); }; }""")
        page.get_by_role("button", name="포트폴리오 카드 만들기", exact=True).click()
        see(page, "이렇게 저장돼요")
        drawn = page.evaluate("window.__drawn")
        assert "담은 종목 TOP 1" in drawn and "70%" in drawn and "없어진 회사" not in drawn and gone not in drawn, drawn
        page.get_by_role("button", name="닫기", exact=True).first.click()
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="저장하고 나가기").first.click()
        see(page, "어떻게 시작할까요?")
        line = page.evaluate(SMALLEST, ["불러온 포트폴리오", ["β "]])
        assert line and "· 1종목 ·" in line, line
    R.check(page, S, "그 백업을 새 브라우저에서 불러오기 → 저장본에 두 종목 그대로(없는 종목은 숨김) · 카드 TOP 1 · '1종목' · NaN 없음", restore)
    ctx.close(); srv.shutdown()
    shutil.rmtree(site, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)


def scene_import_while_loading(R, files):
    """'저장한 파일에서 불러오기'와 오늘 데이터 읽기 (v18.4.1, Jack 2026-11-04).
      · data.json 이 늦게 오는 동안에는 파일 고르기가 화면에 없어요(부팅 화면). 다 읽은 바로 뒤에 고른 파일은 종목 · 직접 추가 종목 ·
        환율까지 파일 그대로 열려요 (부팅이 파일 내용을 덮지 않아요).
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
    fx = 1234.5                                                         # 오늘 환율과 다른 값: 부팅이 덮으면 바뀌어요
    assert files["data.json"].get("fx") != fx
    backup = {"app": "Baepsae 뱁새 v12", "budgetWon": 20000000, "settings": {"fx": fx}, "customStocks": [MINE],
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
        assert st["settings"]["fx"] == fx, st["settings"]["fx"]                 # 환율도 파일 그대로 (지금 규칙)
    R.check(page, S, "data.json 이 4초 늦음 → 그동안 파일 고르기 없음, 다 읽은 뒤 고른 파일은 종목 · 직접 추가 종목 · 환율 그대로", slow)
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


HEADER_ITEMS = """() => [...document.querySelector('.mastRow').children].filter((e) => getComputedStyle(e).display !== 'none'
  && e.getBoundingClientRect().width).map((e) => { const r = e.getBoundingClientRect(); return [e.dataset.v2Link ? 'v2' : e.tagName, r.left, r.right]; })"""


def scene_v2_link(R, files):
    site = build_site(files)
    shutil.copy(os.path.join(ROOT, "app.html"), site)            # 링크가 여는 2.0 (커밋한 빌드 결과)
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
            assert page.url.endswith("/app.html"), page.url
            page.locator('[data-ui-v2="app-bar"]').first.wait_for(state="visible", timeout=WAIT)
        R.check(page, S, "누르면 app.html (뱁새 2.0)", opens)
        ctx.close()
    srv.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=ROOT, help="data/corp/disc/macro.json 이 있는 폴더")
    ap.add_argument("--shots", default=None, help="실패 시 스크린샷을 저장할 폴더")
    ap.add_argument("--only", default=None, help="이 장면만 (정상·멈춤·NaN·corp·data·금·금리·위험값·B안·서비스워커·2.0링크·파일)")
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
                  ("금", lambda: scene_gold_estimate(R, fresh)), ("금리", lambda: scene_rates_fail(R, fresh)), ("위험값", lambda: scene_no_risk_holding(R, fresh)), ("B안", lambda: scene_option_b(R, fresh)), ("해외", lambda: scene_foreign_issuer(R, fresh)), ("B안", lambda: scene_simple_no_forecast(R, fresh)),
                  ("서비스워커", lambda: scene_service_worker(R, fresh)), ("2.0링크", lambda: scene_v2_link(R, fresh)),
                  ("파일", lambda: scene_json_import(R, fresh)), ("파일", lambda: scene_ghost_holding(R, fresh)),
                  ("파일", lambda: scene_import_while_loading(R, fresh))]
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
