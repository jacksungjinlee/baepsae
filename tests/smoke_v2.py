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
  v19.1b      divCheck 가 있는 파일 (PR #50): 분할 뒤 배당은 오늘 주식 수 기준(dps3a)으로 늘린 기록 · 진짜 삭감은 삭감 · 비교 불가와
              알 수 없음은 추세 없이 · 베타는 오차 범위와 함께(양 끝이 같으면 한 숫자, 표준오차 0.5 초과는 자료가 없어요) · 재무 경고는 확인이
              다 돌았거나 해당 없을 때만 '없어요' · 덱 짜기와 매수 계획의 2022년은 범위(작은 하락 먼저), 작은 쪽이 하락이 아니면 '오차가
              너무 커서 추정하지 않았어요.' · 예전 파일은 출렁임 문장만
  v19.1c      미국 종목의 자기 가격 날짜(pxd): 회사 페이지 '미국 {날짜} 종가' · 목록·합계마다 '{티커} 가격은 {날짜} 종가예요.' (덱 짜기 상위
              3종목 · 후보 · 매수 계획 · 홈 · 포트폴리오 · 추가로 넣을 돈 · 종목) · 샀어요 미국 줄 밑 '미국 {날짜} 종가' · 다른 날의 % 없음 ·
              늦음 시각(staleAfter): 지나면 n ≤ 1 '갱신이 늦어지고 있어요'(홈 띠는 today.staleLate), 2일째부터 '{n}일째 …', 전이면 조용 ·
              홈 '오늘 확인할 일'의 그 종목 안내 · 열어 둔 화면도 시계가 staleAfter 를 지나면(타이머 · 다시 보일 때) 새로 고침 없이 경고
  공시 단위   (Jack, 2026-11-13) 단위를 잘못 적은 재무제표로 숫자를 비운 한국 회사(unitChk): '공시 자료의 단위를 확인하고 있어서 이 숫자를
              잠시 비워 두었어요.' 영역마다 한 번 (요약의 한눈에 칸 위 · 재무 경고 자리 · 내 기준 · 실적 · 가치 · 두 자세히 · 배당성향 자리),
              실적 · 가치 칸과 숫자 없는 카드는 없음, 출렁임 · 배당은 그대로 · 다른 회사에는 없음
  돌아온 화면 (2026-11-08, 390 · 1280) 멈춘 화면이 다시 보이면 파일을 한 번 받아요: 더 새 발행이면 모든 화면이 새 날짜 · 받지 못함 ·
              못 읽음 · 섞인 발행이면 멈춤 표시 그대로 · 멈춘 데이터가 아니면 받지 않음 · 돌아올 때마다 한 번만 · 10분 안에는 다시 받지
              않음 · 첫 불러오기 실패도 한 번 받음 · 후보 고르기 · 매수 계획 · 가진 종목 넣기 위에는 새 데이터가 기다려요
  재무제표 통화 (Jack, 2026-11-12) 재무제표가 달러가 아닌 미국 회사(fcur): PBR · PER · 배당수익률은 이름과 함께 '–', 그 바로 밑에
              '주가는 달러, 재무제표는 {통화} 기준이라 이 숫자는 계산하지 않았어요.' 한 번씩 (요약 · 내 기준 · 시트 · 가치 · 자세히 · 배당),
              통화 이름이 없으면 같은 '–' 에 줄만 없어요
  PC          (v19.0d, 1280 × 800) 왼쪽 메뉴 240px(로고 마크 38px · '뱁새' 24px/800 · 캐치프레이즈 · 탭 넷 · 포트폴리오 만들기 · 날짜 칸 ·
              메뉴 링크 넷) · 아래 탭 막대 · ☰ 없음 · 위 검색 칸(520px 이하) · '/' 가 검색 칸으로(그 글자는 칸에 들어가지 않아요), 다른 칸
              (input · textarea · select · contenteditable · 금액 칸)에 쓰는 중이거나 시트가 열려 있으면 그대로 · 검색 칸에 쓰면 종목 탭에
              결과(소개에서 써도 초점은 칸에 그대로) · 홈(첫 방문: 한국 · 미국 목록 나란히, 뱁이 176px · 다시 온 방문: 포트폴리오 | 시장
              한눈에 · 멈춘 데이터: 시장 한눈에 홀로, 네 칸 한 줄)과 시장(네 칸 | 예전 뱁새
              버튼)은 두 칸, 나머지는 한 칸(720px 이하), 모든 화면의 왼쪽 끝이 같아요 · 아래 버튼 띠 · 시트는 왼쪽 메뉴 오른쪽 ·
              1024 · 1280 · 1440px 에서 가로 스크롤 없음 · 1023px 은 휴대폰 화면 그대로, 창을 넓히고 좁히면 따라 바뀌어요
모든 장면에서 페이지 오류 0건, 다른 사이트 요청 0건. 화면에 보이는 한국어는 모두 src/copy/v2.js(또는 데이터의 이름)에서 와요.
v19.0b (진지한 화면): 글을 모으는 모든 화면에서 (visual_ok) — 그림이 모두 열려요 · 뱁이 그림은 숫자가 있는 카드와 판정 띠에 없어요
(소개 페이지는 규칙이 이름으로 허락한 곳) · 아이콘은 Phosphor 두 층에 표의 색만 · 고른 탭 · 고른 줄 · 고른 칩 · 아이콘 · 판정 띠에
살구색이 없어요. 그리고 판정 띠의 상태 아이콘(할 일 없음 check-circle · 확인할 일 flag, 멈춤은 없음) · 알약 색 · 초점 테두리 남색 ·
로고(뱁이 마크 + '뱁새' 22px/800) · 포트폴리오 만들기 첫 화면(v19.3c 시작 화면)에는 뱁이 없음 · 빈 내 덱 · 불러오기 실패 · 준비 중의 뱁이 ·
기록했어요는 그림 대신 아이콘 칩.
"""
import argparse
import datetime as dt
import functools
import http.server
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time

from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copytrace import Matcher, copy_strings, HANGUL  # noqa: E402
from visualcheck import V2_IMAGES, NAVY_RGB, SELECT_RGB, visual_ok, placements_table, copy_pictures, text_floor  # noqa: E402
import tmpdirs  # noqa: E402
from testclock import TestClock, drift_ok  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
with open(os.path.join(ROOT, "src", "v2", "company.js"), encoding="utf-8") as _f:      # 회사 표시의 열 가지 색 (v19.1a Part G)
    MARK_COLORS = re.findall(r'"(#[0-9A-F]{6})"', _f.read().split("export const MARK_COLORS = [", 1)[1].split("]", 1)[0])
assert len(MARK_COLORS) == 10, MARK_COLORS
# 한국 배당 추세 스위치 (src/v2/engine.js KR_DIV_TREND, company.js 가 다시 내보내요; Jack 2026-11-05: 주식 분할을 배당 삭감으로 말하지
# 않게, 분할을 고친 기록이 생길 때까지 꺼짐). 매일 점검 · 오늘 장면은 두 상태를 모두 화면에서 시험해요: 커밋한 app.html(코드의 값)과,
# 스위치만 반대로 놓고 임시 폴더에 빌드한 app.html (other_trend_app). 회사 페이지 장면은 코드의 값을 따라요.
with open(os.path.join(ROOT, "src", "v2", "engine.js"), encoding="utf-8") as _f:
    _SWITCH = re.findall(r"^export const KR_DIV_TREND = (true|false);$", _f.read(), flags=re.M)
assert len(_SWITCH) == 1, _SWITCH
KR_DIV_TREND = _SWITCH[0] == "true"
_OTHER = {}


def other_trend_app():
    """app.html 을 한국 배당 추세 스위치만 반대로 놓고 임시 폴더에 빌드해요 (커밋하지 않아요). 배당 삭감 화면(확인 필요의 두 버튼 ·
    실제로 줄였어요 → 규칙 깨짐 · 매도 조건 띠)은 스위치가 켜져 있어야 나와서, 꺼져 있는 동안에도 그 화면을 시험하려고요.
    빌드한 페이지는 글로 들고 있고 임시 폴더는 바로 지워요 (돌리는 동안 폴더가 사라져도 상관없게)."""
    if "html" not in _OTHER:
        tmp = tmpdirs.make("baepsae-trendflip-")
        shutil.copytree(os.path.join(ROOT, "src"), os.path.join(tmp, "src"))
        os.makedirs(os.path.join(tmp, "tools"))
        for f in ("template.html", "build-app.sh", "package.json", "package-lock.json", os.path.join("tools", "build_tag.py")):
            shutil.copy(os.path.join(ROOT, f), os.path.join(tmp, f))
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        eng = os.path.join(tmp, "src", "v2", "engine.js")
        with open(eng, encoding="utf-8") as fh:
            src = fh.read()
        old = f"export const KR_DIV_TREND = {'true' if KR_DIV_TREND else 'false'};"
        assert src.count(old) == 1, old
        with open(eng, "w", encoding="utf-8") as fh:
            fh.write(src.replace(old, f"export const KR_DIV_TREND = {'false' if KR_DIV_TREND else 'true'};"))
        out = os.path.join(tmp, "out")
        r = subprocess.run(["bash", "build-app.sh", out], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout + r.stderr
        with open(os.path.join(out, "app.html"), encoding="utf-8") as a, open(os.path.join(ROOT, "app.html"), encoding="utf-8") as b:
            html = a.read()
            assert html != b.read(), "스위치를 바꿔 빌드했는데 app.html 이 같아요"
        shutil.rmtree(tmp, ignore_errors=True)
        _OTHER["html"] = html
    return _OTHER["html"]


def trend_label(trend):
    return "배당 추세 " + ("켜짐" if trend else "꺼짐")
SITE_FILES = ["baepsae.html", "sw.js", "icon-192.png", "baepi-og.webp", "jack-photo.jpg"] + V2_IMAGES + [f"baepi-{i}.png" for i in range(1, 10)]
DATA_FILES = ["data.json", "corp.json", "macro.json", "disc.json"]         # disc.json: v19.1a 공시 탭 (지어낸 시험용)
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


IMG_OK = "(i) => i.complete && i.naturalWidth > 0"
IMG_WAIT_MS = 5000          # Jack 2026-11-06: 그림이 다 열릴 때까지 5초까지 기다려요. 그래도 안 열리면 실패예요


def img_loaded(img):
    """보이는 그림(locator 하나)이 다 열렸는지. 보이자마자 보면 느린 기계에서 아직 받는 중이라 가끔 틀려요 (#53 의 ci)."""
    handle = img.element_handle()        # 그림이 없으면 여기서 바로 실패해요 (기다림 안에 숨기지 않아요)
    try:
        img.page.wait_for_function(IMG_OK, arg=handle, timeout=IMG_WAIT_MS)
    except PWTimeout:
        pass                # 아래에서 다시 보고, 안 열렸으면 부른 쪽의 assert 가 실패로 잡아요
    return img.evaluate(IMG_OK)


def mascot_img(loc, src, px, alt):
    img = loc.locator(f'img[src="{src}"]')
    img.wait_for(state="visible")
    assert img_loaded(img), f"{src} 가 열리지 않았어요 ({IMG_WAIT_MS // 1000}초까지 기다렸어요)"
    box = img.bounding_box()
    assert box and abs(box["width"] - px) < 1, (src, box)
    assert img.get_attribute("alt") == alt and alt, (src, img.get_attribute("alt"), alt)     # Jack 이 승인한 alt (2026-11-04)


# 2026-11-11 (Jack): 이 파일의 모든 '지금'은 now_dt() — 시험의 시계예요 (tests/testclock.py). main() 이 CLOCK 에서 시작시키고,
# 그 뒤로는 평소처럼 흘러요. 모든 브라우저 창의 날짜 · 시각도 같은 만큼 옮겨져요 (Runner.new_context).
# 진짜 날짜 · 시각을 읽으면 그날그날 · 시각마다 결과가 달라질 수 있어요 (예: 23:15~23:20 KST 에 돌리면 '시계를 45분 뒤로' 장면이
# 자정을 넘겨 실패했어요 — 앱은 규칙대로였고 시험만 틀렸어요).
# 07:00 KST 에서 시작해요: 한 번 도는 10여 분과 시계를 45분까지 옮기는 장면이 한국 날짜도 UTC 날짜도 넘지 않고(08:05 쯤까지),
# 한국 날짜와 UTC 날짜가 서로 달라요 (UTC 로는 전날 22시) — '오늘'을 UTC 날짜로 잘못 읽는 코드가 여기서 드러나요.
# 지난 날짜예요 (진짜 시계가 우연히 이 시각과 겹쳐 '창의 시계' 검사가 눈감는 날이 없게). 날짜를 직접 정하는 장면은 자기 날짜를 써요.
# 다른 테스트가 이 파일의 도우미만 빌려 쓸 때(main 을 돌리지 않음)는 시계를 시작하지 않아요: 그때의 '지금'은 진짜 시계예요.
CLOCK = dt.datetime(2026, 11, 11, 7, 0, tzinfo=KST)
TC = TestClock()


def now_dt():
    return TC.now()


def now_kst(days_ago=0):
    return (now_dt() - dt.timedelta(days=days_ago)).isoformat(timespec="seconds")


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


def build_site(files, raw=None, drop=(), app=None):
    site = tmpdirs.make("baepsae-v2-")
    for f in SITE_FILES:
        shutil.copy(os.path.join(ROOT, f), site)
    # 커밋한 app.html (test_v2_app 이 소스와 같은지 확인해요). app: 배당 추세 스위치를 반대로 놓은 빌드의 글 (other_trend_app)
    if app is None:
        shutil.copy(os.path.join(ROOT, "app.html"), os.path.join(site, "app.html"))
    else:
        with open(os.path.join(site, "app.html"), "w", encoding="utf-8") as fh:
            fh.write(app)
    shutil.copytree(os.path.join(ROOT, "fonts"), os.path.join(site, "fonts"))
    copy_pictures(site)                                              # v19.3b: 기준 · 템플릿 그림
    for name, obj in files.items():
        if name in drop:
            continue
        with open(os.path.join(site, name), "w", encoding="utf-8") as fh:
            fh.write(raw[name] if raw and name in raw else json.dumps(obj, ensure_ascii=False))
    return site


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        # A scene can hold back the next answer for one file (2026-11-08, 돌아온 화면 disc-slow): a file ".delay-<name>" in the
        # site holds the seconds; it is used once (removed), the other requests go on meanwhile (a threading server). The
        # file is read when the request arrives and sent after the wait: the late answer is the file as it was then, even
        # if the scene writes a newer one meanwhile (round-4 review).
        name = os.path.basename(self.path.split("?", 1)[0])
        mark = os.path.join(self.directory, ".delay-" + name)
        if name and os.path.isfile(mark):
            try:
                with open(mark, encoding="utf-8") as fh:
                    secs = float(fh.read().strip() or "0")
                os.remove(mark)
            except (OSError, ValueError):
                secs = 0
            try:
                with open(self.translate_path(self.path), "rb") as fh:
                    body = fh.read()
            except OSError:
                self.send_error(404)
                return
            time.sleep(secs)
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(self.path))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

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
        self.clock_drift = []          # 창을 열 때마다 (브라우저 시계 − 그 창이 시작해야 하는 시각) 초 — 끝에서 모두 0 이상 10분 미만인지 봐요
        self.texts = set()
        self.names = sorted({n for n in names if n and HANGUL.search(n)}, key=len, reverse=True)

    def new_context(self, clock=True, **kw):
        """브라우저 창 하나. 창의 날짜 · 시각은 시험의 시계(now_dt)와 같아요 (testclock.DATE_SHIM). clock=False 는 그 장면이 Playwright 의
        페이지 시계를 직접 설치할 때만 (설치한 뒤 saw_clock(page, 그 시각) 으로 알려요)."""
        ctx = self.browser.new_context(**kw)
        if clock:
            TC.install(ctx)
        return ctx

    def saw_clock(self, page, base=None):
        """그 창의 시계가 (base 가 없으면 지금의 now_dt 에서, 있으면 그 시각에서) 시작했는지: 차이(초)를 모아 끝에서 봐요."""
        self.clock_drift.append(TC.drift(page, base))

    def open(self, site, width, init=None, accept_downloads=False, path="/app.html?dev=1", device=None, guide_seen=True):
        srv, base = serve(site)
        # device: Playwright 의 기기 설명(사용자 에이전트 · 화면 · 터치)을 그대로 입혀요. 없으면 휴대폰 폭 width × 780.
        screen = dict(device) if device else {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2}
        ctx = self.new_context(**screen, locale="ko-KR", service_workers="block", accept_downloads=accept_downloads)

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
        if guide_seen:                         # v19.3c GUIDE_FIRST_VISIT (Jack, 2026-11-08): a visitor who has already seen the guide
            ctx.add_init_script("try { localStorage.setItem('baepsae2.v1.guideSeen', '1'); } catch (e) {}")       # (the app reads this flag into its store, store.js readStore)
        if init:
            ctx.add_init_script(init)
        page = ctx.new_page()
        page.set_default_timeout(WAIT)
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(base + path, wait_until="domcontentloaded")
        self.saw_clock(page)
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
    """☰ 메뉴: 소개 · 용어 사전 · 데이터 출처 · 처음 안내 다시 보기 · 예전 뱁새 보기 (예전 뱁새로 가는 셋은 실제 앱에만; v19.3c Part E ·
    O.2: 처음 안내 다시 보기는 예전 뱁새 보기 바로 앞, 미리 보기에서는 소개 바로 뒤), 닫기로 닫혀요."""
    m = open_menu(page)
    items = m.locator('[data-ui-v2="menu-item"]')
    want = [("about", C["app"]["aboutLink"], None)]
    if live:
        want += [("glossary", C["menu"]["glossary"], "./baepsae.html?from=app#info=glossary"), ("sources", C["menu"]["sources"], "./baepsae.html?from=app#info=sources"),
                 ("guide", C["menu"]["guide"], None), ("old-app", C["app"]["oldApp"], "./baepsae.html?from=app")]
    else:
        want += [("guide", C["menu"]["guide"], None)]
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


def disc_settled(page, timeout=None):
    """v19.3e: 홈이 한국 종목을 가지면 공시 목록(disc.json)을 스스로 받아요 (첫 화면 뒤에). 받는 동안('wait')은 '오늘은 할 일이 없어요'를
    말하지 않으니, 홈의 판정을 보는 검사가 받기 전의 화면을 보지 않게 끝날 때까지 기다려요. 끝 = 'wait' 이 아닌 모든 상태 (ok · stale ·
    fail · none · skip): 받지 못한 것(fail)도 끝이에요 (Jack, 2026-11-08: 실패 장면이 기다리다 멈추지 않고 실패 문구까지 가게)."""
    page.wait_for_function("() => { const h = document.querySelector('[data-ui-v2=\"home2\"]'); return !h || h.dataset.disc !== 'wait'; }",
                           **({"timeout": timeout} if timeout else {}))


def disc_fetched(page):
    """이 화면이 disc.json 을 받았는지 (브라우저의 요청 기록)."""
    return page.evaluate("() => performance.getEntriesByType('resource').some((e) => /\\/disc\\.json(\\?|$)/.test(e.name))")


def wait_ready(page):
    page.locator('[data-ui-v2="date-line"], [data-ui-v2="load-fail"]').first.wait_for(state="visible")
    page.locator('[data-ui-v2="screen"][data-route]').wait_for(state="attached")
    disc_settled(page)


# ── v19.5b 홈 · 종목 순위 (src/v2/rank.jsx · ranks.js): 화면을 읽는 도우미와, 파이썬으로 따로 센 기대 목록 ──
NAME_MIN_320 = 120                                             # 320px 화면에서 종목 순위 줄의 회사 이름 칸 (px) 은 이 이상 (v19.5b 리뷰 3차)
RANK_LIST = '[data-ui-v2="rank-window"] [role="list"]'          # 움직이는 창의 첫 벌 (화면 읽기 프로그램이 읽는 목록) · 멈춘 목록은 이것 하나


def rank_ts(page):
    """종목 순위 목록의 줄(첫 벌)마다 종목 코드 (업종별 등락은 업종 id)."""
    return page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').evaluate_all("(els) => els.map((e) => e.dataset.t || e.dataset.ind)")


def rank_market(page, mk):
    page.locator(f'[data-ui-v2="rank-market"] [data-mk="{mk}"]').click()
    page.wait_for_function("(mk) => { const e = document.querySelector('[data-ui-v2=\"rank\"]'); return !!e && e.dataset.mk === mk; }", arg=mk)


def rank_chip(page, chip, crit=None):
    page.locator(f'[data-ui-v2="rank-chips"] [data-chip="{chip}"]').click()
    page.wait_for_function("(c) => { const e = document.querySelector('[data-ui-v2=\"rank\"]'); return !!e && e.dataset.chip === c; }", arg=chip)
    if crit:
        page.locator(f'[data-ui-v2="rank-crit"] [data-chip="{crit}"]').click()
        page.wait_for_function("(c) => { const e = document.querySelector('[data-ui-v2=\"rank\"]'); return !!e && e.dataset.crit === c; }", arg=crit)


def by_t(stocks):
    return {x["t"]: x for x in stocks}


def _js_rx(name):
    """src/v2/engine.js 의 미국 우선주 정규식을 그대로 (문자 하나 다르지 않게: engine 은 fetch_data.py 와 같아요)."""
    with open(os.path.join(ROOT, "src", "v2", "engine.js"), encoding="utf-8") as fh:
        m = re.search(r"^export const %s = /(.+)/([a-z]*);$" % name, fh.read(), flags=re.M)
    return re.compile(m.group(1), re.I if "i" in m.group(2) else 0)


US_PREF_RX = {k: _js_rx(k) for k in ("US_PREF_NAME", "US_DEPOSITARY", "US_ADR", "US_PREF_TICKER")}
FIN_INDS = {"bank", "insurance", "securities", "finance", "fin"}
with open(os.path.join(ROOT, "src", "v2", "pictures.js"), encoding="utf-8") as _f:          # 기준 그림 (CARD_PICS: 기준마다 하나)
    CARD_TABLE_PICS = dict(re.findall(r'^  (\w+): \{ src: "pictures/([\w-]+)\.webp"', _f.read().split("export const CARD_PICS = {", 1)[1].split("};", 1)[0], flags=re.M))
RANK_CRIT = {"value": ("pbr", -1), "profit": ("roe", 1), "stable": ("debt", -1), "lowVol": ("vol", -1), "trend": ("mom", 1), "growth": ("g3", 1)}


def isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def us_pref(s):
    for n in (s.get("nk"), s.get("ne")):
        if isinstance(n, str) and n and (US_PREF_RX["US_PREF_NAME"].search(n) or (US_PREF_RX["US_DEPOSITARY"].search(n) and not US_PREF_RX["US_ADR"].search(n))):
            return True
    return isinstance(s.get("t"), str) and bool(US_PREF_RX["US_PREF_TICKER"].search(s["t"]))


def rank_base(stocks, cls):
    """스펙 Part A: 그 시장의 회사 주식(ETF · 펀드 · 우선주 · 가격 없음 빼고) 중 거래대금 기준(한국 val20 · 미국 val 5억 이상)을 넘는 것."""
    out = []
    for s in stocks:
        if not in_universe(s, cls) or (cls == "us" and us_pref(s)):
            continue
        liq = s.get("val20") if cls == "kr" else s.get("val")
        if isnum(liq) and liq >= 5:
            out.append(s)
    return out


def _same_co(a, b):
    na, nb = (" ".join(str(x.get("nk") or "").split()).lower() for x in (a, b))
    if a.get("cls") != "us" or not na or na != nb:
        return False
    sh = [x["cap"] / x["price"] if isnum(x.get("cap")) and x["cap"] > 0 and isnum(x.get("price")) and x["price"] > 0 else None for x in (a, b)]
    return None not in sh and abs(sh[0] - sh[1]) <= 0.005 * max(sh)


def rank_expect(stocks, cls, chip, crit=None, coby=None):
    """시가총액 · 거래대금 · 거래 급증 · 기준별 목록을 파이썬으로 (src/v2/ranks.js 를 믿지 않고): 빈 칸은 빼고, 같은 값은 시가총액 큰 순,
    미국의 같은 회사 두 종류 주식은 위의 하나만. Jack 2026-11-12: 가치는 PBR 0 이하 · 미국은 PBR < PER × ROE ÷ 100 ÷ 4 를 빼요,
    한국 성장은 2년 연평균(corp rev 당기 · 전전기 0 초과)이고 전전기 매출 100억원 이상, 한국 수익성은 ROE 의 자본(roeIn.eq, 없으면 eq) 100억원 이상."""
    rows = []
    for s in rank_base(stocks, cls):
        if chip in ("cap", "val"):
            v = s.get(chip)
        elif chip == "surge":
            a, b, cap = s.get("val"), s.get("val20"), s.get("cap")
            x = a / b if isnum(a) and a >= 0 and isnum(b) and b > 0 else None
            v = x if x is not None and x >= 2 - 1e-9 and isnum(cap) and cap >= 0.3 - 1e-9 else None
        else:
            f, _ = RANK_CRIT[crit]
            v = None if crit == "stable" and has_group(s) and s.get("ind") in FIN_INDS else s.get(f)
            if crit == "value" and not (isnum(v) and v > 0):
                v = None
            if crit == "value" and cls == "kr" and isnum(v) and v < 0.005:              # 한국 가치: 0.00 으로 반올림되는 PBR 도 빼요 (Jack, 2026-11-13)
                v = None
            if crit == "value" and cls == "us" and isnum(v) and isnum(s.get("per")) and s["per"] > 0 and isnum(s.get("roe")) and s["roe"] > 0 \
                    and v < s["per"] * s["roe"] / 100 / 4:
                v = None
            if cls == "kr" and crit in ("growth", "profit") and isnum(v):
                co = (coby or {}).get(s["t"]) or {}
                if crit == "growth":
                    rev = (list(co.get("rev") or []) + [None, None, None])[:3]
                    if not (isnum(rev[0]) and rev[0] > 0 and isnum(rev[2]) and rev[2] > 0 and rev[2] >= 100):
                        v = None
                else:
                    eq = (co.get("roeIn") or {}).get("eq")
                    eq = eq if isnum(eq) else co.get("eq")
                    if not (isnum(eq) and eq >= 100):
                        v = None
        if isnum(v):
            rows.append((v, s))
    d = RANK_CRIT[crit][1] if chip == "crit" else 1
    rows.sort(key=lambda x: (-d * x[0], -(x[1]["cap"] if isnum(x[1].get("cap")) else -math.inf), x[1]["t"]))
    out, kept = [], []
    for _, s in rows:
        if any(_same_co(s, k) for k in kept):
            continue
        kept.append(s)
        out.append(s["t"])
    return out


def ind_expect(stocks, cls):
    """업종별 등락: 그 시장의 회사 주식 중 오늘 변화가 있는 것을 업종마다 (5곳 이상), 평균은 단순 평균 (왜 움직였나와 같은 셈)."""
    groups = {}
    for s in stocks:
        if in_universe(s, cls) and not (cls == "us" and us_pref(s)) and has_group(s) and s.get("pxd") is None and isnum(s.get("d1")):
            groups.setdefault(s["ind"], []).append(s)
    out = [(ind, len(m), sum(x["d1"] for x in m) / len(m), sum(x["cap"] for x in m if isnum(x.get("cap")))) for ind, m in groups.items() if len(m) >= 5]
    out.sort(key=lambda x: (-x[2], -x[3], x[0]))
    return out


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
        # 첫 방문 홈 (v19.5b): 머리글 · 포트폴리오 만들기 · 종목 순위. 종목 순위가 숫자를 보여서 뱁이가 없어요 (예전: 뱁이 92px + 거래대금
        # 상위 종목 이름만). 뱁이는 v19.3c 의 반기는 화면에 있어요.
        hero = page.locator('[data-ui-v2="home-hero"]')
        hero.wait_for(state="visible")
        assert C["about"]["ko"]["hero"]["descriptor"] in hero.inner_text() and C["about"]["ko"]["hero"]["catch"] in hero.inner_text()
        assert page.locator('[data-ui-v2="home-start"]').inner_text().strip() == C["build"]["title"]
        assert page.locator('[data-ui-v2="market-glance"], [data-ui-v2="market-tile"]').count() == 0, "첫 방문 홈에 시장 칸 (v19.5b 는 종목 순위만 더해요)"
        rank = page.locator('[data-ui-v2="rank"]')               # 거래대금 상위 종목 대신 종목 순위: 처음엔 한국 · 시가총액, 날짜, 숫자와 등락
        rank.wait_for(state="visible")
        assert rank.locator("h3").inner_text() == C["rank"]["title"] and (rank.get_attribute("data-mk"), rank.get_attribute("data-chip")) == ("kr", "cap")
        assert rank.locator('[data-ui-v2="rank-date"]').inner_text() == "10월 30일 종가"
        assert rank_ts(page) == rank_expect(files["data.json"]["stocks"], "kr", "cap")[:10], rank_ts(page)
        assert re.search(r"\d[\d,.]*[조억]원", rank.inner_text()) and re.search(r"[+−]\d+\.\d%", rank.inner_text()), rank.inner_text()
        assert page.locator(MASCOT_IN_MAIN).count() == 0, "숫자가 있는 첫 방문 홈에 뱁이"
        assert page.locator('[data-ui-v2="rank-chip"][data-chip="mine"]').count() == 0, "기준 점수가 있는 포트폴리오가 없는데 내 기준 칩"
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
    R.check(page, S, "첫 화면: 저장한 포트폴리오가 없으면 첫 방문 홈(머리글 · 포트폴리오 만들기 · 종목 순위, 뱁이 없음) · 탭 넷 · ☰", landing)

    def visual_start():
        bar = page.locator('[data-ui-v2="app-bar"]').first                   # 로고: 뱁이 마크 28px + '뱁새' 22px/800 (뒤로 버튼이 있으면 마크 대신)
        mark = bar.locator('img[data-ui-v2="logo-mark"]')
        assert mark.get_attribute("src") == "baepi-mark.webp" and mark.get_attribute("alt") == "" and img_loaded(mark)
        assert abs(mark.bounding_box()["width"] - 28) < 1
        assert bar.locator("img[src='icon-192.png']").count() == 0
        word = bar.locator('h1[data-ui-v2="wordmark"]')
        assert word.inner_text() == C["app"]["brand"] and word.evaluate("(e) => [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight]") == ["22px", "800"]
        page.locator('[data-ui-v2="home-start"] button').click()
        at(page, "portfolio/build")
        assert page.url.endswith("#portfolio/build") and page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        start = page.locator('[data-ui-v2="build-start2"]')                # v19.3c 시작 화면: 템플릿이 점수 · 비중을 보여서 뱁이 없음 (CLAUDE.md)
        start.wait_for(state="visible")
        assert start.locator('img[src^="baepi-"]').count() == 0 and page.locator(MASCOT_IN_MAIN).count() == 0
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
    R.check(page, S, "포트폴리오 만들기 첫 화면(v19.3c 시작 화면)에 뱁이 없음(템플릿이 점수 · 비중을 보여요) · 로고 마크 + 워드마크 · 돌아와도 시작 유형 표시 없음 · 초점 테두리 남색 · 뒤로 → 홈", visual_start)

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
        bad = os.path.join(tmpdirs.make("baepsae-v2-file-"), "bad.json")
        with open(bad, "w") as fh:
            fh.write('{"hello": 1}')
        page.locator('[data-ui-v2="import-file"]').set_input_files(bad)
        page.locator('[data-ui-v2="import-bad"]').wait_for(state="visible")
        assert page.get_by_text("내 종목 6개").count() == 1, "잘못된 파일이 기록을 지웠어요"
        box = page.locator('[data-ui-v2="import-bad"]')
        assert box.get_attribute("data-why") == "bad" and box.inner_text() == C["store"]["importFail"], box.inner_text()
        prev = os.path.join(tmpdirs.make("baepsae-v2-file-"), "preview.json")
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
        new = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")["decks"][-1]
        page.get_by_role("button", name=C["app"]["close"]).click()
        # Jack, 11-10: 기록한 계획은 끝이에요 — 기록했어요를 닫으면 포트폴리오(방금 만든 포트폴리오), 다음 포트폴리오 만들기는 처음부터라서
        # 같은 계획을 샀어요로 두 번 기록할 수 없어요 (예전: 닫으면 그 매수 계획으로 돌아갔어요)
        at(page, "portfolio")
        page.locator(f'[data-deck-id="{new["id"]}"]:has(h3)').wait_for(state="visible")
        start_build(page)
        see(page, C["build"]["s0"]["title"])
        assert page.get_by_role("button", name=C["plan"]["bought"]).count() == 0, "기록한 매수 계획이 다시 열렸어요"
        from_blank()                                                       # 다음 확인(지킬 수 없는 설정)이 쓸 매수 계획을 처음부터 다시 만들어요
    R.check(page, S, "샀어요에서 한 종목을 0주로 → 기록했어요는 실제로 산 종목 수만 점검한다고 말해요 · 닫으면 포트폴리오, 다시 만들기는 처음부터", partial_buy)

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
    R.check(page, f"{how} {width}", "불러오기 실패 문구 (오늘 · 내 덱(저장한 덱 없음, 뱁이 그대로) · 덱 짜기), 예시 데이터 없음 · 처음 안내를 이미 본 방문자", run)
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
        rank = page.locator('[data-ui-v2="rank"]')                         # v19.5b: 종목 순위의 미국 목록은 자기 날짜 (예전: 거래대금 미국 목록)
        rank.wait_for(state="visible")
        assert rank.locator('[data-ui-v2="rank-date"]').inner_text() == "10월 30일 종가"
        rank_market(page, "us")
        assert note.count() == 0 and rank.locator('[data-ui-v2="rank-date"]').inner_text() == "10월 29일 종가 (미국 시간)"
        R.collect(page)
    R.check(page, f"미국 날짜 {width}", "종목: 미국 종목 줄이 보이면 '미국 종목은 현지 기준 10월 29일 종가예요.' (종목 순위의 미국 목록은 자기 날짜)", stocks_us_close)
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


# ── 매수 계획 · 연 배당금 (Jack, 2026-11-05) ──
# 회사 페이지가 배당수익률을 숨기는 한국 종목(보고서 수익률과 1/3~3배 · 연 30% · 임시 분할 안전장치 1.8배: engine.krYieldToday)은
# 연 배당금에서 빼고, 그 밑에 "배당을 확인하지 못한 종목 {n}개({names})는 빼고 계산했어요." 줄로 이름을 밝혀요 (조용히 빼지 않아요).
def plan_files(files, guard=()):
    """한국 배당 종목마다 보고서 수익률(dy)을 오늘 수익률(주당 배당 ÷ 종가)과 같게 놓아요: 빼는 종목이 없어요. guard 의 종목
    (또는 "all" 이면 모두)은 보고서 수익률을 그 절반으로: 오늘 수익률이 2배라 분할 안전장치(1.8배)에 걸리지만 1/3~3배 검사는
    통과해서, 배당 카드 순위(주당 배당 ÷ 종가)와 담는 종목은 그대로예요. 보고서 수익률은 연 30% 까지만 놓아요 (넘으면 1/3~3배
    검사가 어긋나 순위가 달라져요): 오늘 수익률이 30% 를 넘는 종목은 어느 쪽이든 믿지 않는 배당이에요 (연 30% 상한)."""
    f = clone(files)
    for s in f["data.json"]["stocks"]:
        if s.get("cls") == "kr" and (s.get("dps") or 0) > 0 and (s.get("price") or 0) > 0:
            y = s["dps"] / s["price"] * 100
            s["dy"] = round(min(y / 2 if (guard == "all" or s["t"] in guard) else y, 30), 6)
    return f


def unchecked_names(f, rows):
    """engine.annualDividend 를 파이썬으로 따로: 산 한국 종목 중 주당 배당이 있고(0원은 그대로 0원) 회사 페이지가 수익률을 숨기는
    종목(kr_yield_today: 보고서 연도 · 1/3~3배 · 연 30% · 1.8배)의 이름, 화면 순서대로."""
    by = {s["t"]: s for s in f["data.json"]["stocks"]}
    co = {c["t"]: c for c in f["corp.json"]["companies"]}
    out = []
    for t, n in rows:
        s = by.get(t, {})
        if n > 0 and s.get("cls") == "kr" and s.get("dps") is not None and not (s["dps"] == 0 and kr_dps_agrees(s)) \
                and kr_yield_today(s, co.get(t)) is None:
            out.append(s["nk"])
    return out


def won_value(text):
    """'약 32만원' · '약 5,000원' → 원."""
    m = re.search(r"([\d,]+)만원", text)
    if m:
        return int(m.group(1).replace(",", "")) * 10000
    m = re.search(r"([\d,]+)원", text)
    assert m, text
    return int(m.group(1).replace(",", ""))


def to_plan(page):
    """배당 생활비 → 다음 → 다음 → 1,000만원 → 후보 고르기(미리 고른 6종목) → 매수 계획. → [(종목, 주식 수)] 화면 순서대로"""
    wait_ready(page)
    start_build(page)
    page.locator('[data-deck="income"]').click()
    see(page, C["build"]["s1"]["title"])
    click_next(page)
    see(page, C["build"]["s3"]["title"])
    click_next(page)
    see(page, C["build"]["s4"]["title"])
    page.get_by_role("button", name="+1,000만").first.click()
    page.locator('[data-ui-v2="y2022-methods"]').get_by_text("약 ").first.wait_for(state="visible")
    click_next(page)
    see(page, C["pick"]["title"])
    click_next(page)
    see(page, C["plan"]["stocks"])
    rows = page.locator('[data-ui-v2="screen"] [data-row]')
    rows.first.wait_for(state="visible")
    out = []
    for i in range(rows.count()):
        r = rows.nth(i)
        out.append((r.get_attribute("data-row"), int(re.search(r"([\d,]+)주", r.inner_text()).group(1).replace(",", ""))))
    return out


def scene_plan_dividend(R, files, width):
    S = f"매수 계획 · 연 배당금 {width}"
    by = {s["t"]: s for s in files["data.json"]["stocks"]}
    line = lambda page: page.locator('[data-ui-v2="plan-summary"] [data-ui-v2="div-unchecked"]')
    total = lambda page: won_value(page.locator('[data-ui-v2="plan-summary"] [data-ui-v2="big-number"]').nth(1).inner_text())
    got = {}

    def kr_payers(rows):
        return [t for t, n in rows if n > 0 and by.get(t, {}).get("cls") == "kr" and (by[t].get("dps") or 0) > 0]

    f0 = plan_files(files)
    srv, ctx, page, _ = R.open(build_site(f0), width)

    def none():
        rows = to_plan(page)
        got.update(rows=rows, krs=kr_payers(rows), total=total(page))
        assert len(got["krs"]) >= 2 and any(by[t]["cls"] == "us" for t, n in rows if n > 0), rows   # 한국 배당 종목 둘 이상 + 미국
        assert unchecked_names(f0, rows) == [], "이 장면은 빼는 종목이 없는 계획이어야 해요 (시험 데이터를 확인해 주세요)"
        assert line(page).count() == 0, line(page).inner_text()
        # 내 투자 규칙: 배당 삭감은 한국 배당 추세 스위치가 꺼져 있으면 준비 중 (주당 배당 기록이 분할을 고치지 않은 값이에요)
        rules = page.locator('[data-ui-v2="rules"] [data-ui="collapsible"]')
        for i in range(rules.count()):
            rules.nth(i).locator("button").first.click()
        book = page.locator("[data-rules-for]")
        book.first.wait_for(state="visible")
        all_text = "\n".join(book.all_inner_texts())
        divs = book.locator('[data-ui-v2="rule-line"]', has_text=C["plan"]["rules"]["divCut"])
        div_checked = book.locator('[data-ui-v2="rule-line"][data-check="checked"]', has_text=C["plan"]["rules"]["divLimit"])
        if KR_DIV_TREND:
            assert div_checked.count() >= 1, all_text
        else:
            assert div_checked.count() == 0 and divs.count() >= len(got["krs"]), all_text
            assert all(divs.nth(i).get_attribute("data-check") == "pending" for i in range(divs.count()))
            assert "주당" not in all_text and "배당이 줄었어요" not in all_text, all_text
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "한국 종목의 배당을 모두 확인할 수 있으면 '배당을 확인하지 못한 종목' 줄이 없어요 · 배당 삭감 규칙은 스위치를 따라요", none)
    ctx.close()
    srv.shutdown()
    if not got.get("krs"):
        return

    one = got["krs"][0]
    f1 = plan_files(files, guard={one})
    srv, ctx, page, _ = R.open(build_site(f1), width)

    def one_guarded():
        rows = to_plan(page)
        assert rows == got["rows"], (rows, got["rows"])                 # 담은 종목 · 주식 수는 그대로
        assert unchecked_names(f1, rows) == [by[one]["nk"]]
        txt = line(page).inner_text()
        assert txt == fillp(C["plan"]["divUnchecked"], n=1, names=by[one]["nk"]), txt
        shares = dict(rows)[one]
        want = got["total"] - by[one]["dps"] * shares                    # 그 종목의 배당만 빠져요 (한국 다른 종목 · 미국은 그대로)
        assert abs(total(page) - want) <= 10000, (total(page), got["total"], by[one]["dps"], shares)
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "분할 안전장치에 걸린 한국 종목 1개 → 연 배당금에서 빼고 '배당을 확인하지 못한 종목 1개(이름)는 빼고 계산했어요'", one_guarded)
    ctx.close()
    srv.shutdown()

    f2 = plan_files(files, guard="all")
    srv, ctx, page, _ = R.open(build_site(f2), width)

    def all_guarded():
        rows = to_plan(page)
        assert rows == got["rows"], (rows, got["rows"])
        el = line(page)
        names = ", ".join(by[t]["nk"] for t in got["krs"])
        assert unchecked_names(f2, rows) == [by[t]["nk"] for t in got["krs"]]
        assert el.inner_text() == fillp(C["plan"]["divUnchecked"], n=len(got["krs"]), names=names), el.inner_text()
        for t in (t for t, n in rows if n > 0 and by[t]["cls"] != "kr"):
            assert by[t]["nk"] not in el.inner_text() and t not in el.inner_text(), t           # 미국 종목은 빼지 않아요
        box, card = el.bounding_box(), page.locator('[data-ui-v2="plan-summary"]').bounding_box()
        assert box["x"] >= card["x"] - 0.5 and box["x"] + box["width"] <= card["x"] + card["width"] + 0.5, (box, card)   # 카드 안에서 줄을 바꿔요
        assert el.evaluate("(e) => e.scrollWidth <= e.clientWidth"), "이름이 칸 밖으로 나가요"
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "한국 배당 종목 모두 → 이름이 모두 나오고 카드 안에서 줄을 바꿔요 (가로 스크롤 없음) · 미국 종목은 그대로", all_guarded)
    ctx.close()
    srv.shutdown()


# ── say-why 두 줄 (Jack, 2026-11-08) ──
def to_plan_mix(page, mix):
    """to_plan 과 같은 길에서 조건 단계의 한국 : 미국만 mix(버튼 이름, 예: '한국만')로 바꿔요. → [(종목, 주식 수)] 화면 순서대로"""
    wait_ready(page)
    start_build(page)
    page.locator('[data-deck="income"]').click()
    see(page, C["build"]["s1"]["title"])
    click_next(page)
    see(page, C["build"]["s3"]["title"])
    click_next(page)
    see(page, C["build"]["s4"]["title"])
    page.get_by_role("radio", name=mix, exact=True).click()
    assert page.get_by_role("radio", name=mix, exact=True).get_attribute("aria-checked") == "true", mix
    page.get_by_role("button", name="+1,000만").first.click()
    page.locator('[data-ui-v2="y2022-methods"]').get_by_text("약 ").first.wait_for(state="visible")
    click_next(page)
    see(page, C["pick"]["title"])
    click_next(page)
    see(page, C["plan"]["stocks"])
    rows = page.locator('[data-ui-v2="screen"] [data-row]')
    rows.first.wait_for(state="visible")
    out = []
    for i in range(rows.count()):
        r = rows.nth(i)
        out.append((r.get_attribute("data-row"), int(re.search(r"([\d,]+)주", r.inner_text()).group(1).replace(",", ""))))
    return out


def scene_say_why(R, files, width):
    """기준 단계: 내 점수 칸 바로 밑에 '하루 거래대금 5억원 미만 종목과 우선주는 빼고 셌어요.' (점수를 주기 전에도 · 준 뒤에도. 위에 붙는
    칸 안이 아니라 그 밑이라 칸의 높이는 그대로예요) · 12px 이상 · 가로 스크롤 없음. 매수 계획 · 연 배당금: 미국 종목을 산 계획에만
    점검과 같은 줄(같은 키 rpt.divUs) '미국 종목은 최근 배당을 1년치로 환산한 값이에요.' 가 '세전 금액이에요' 바로 밑에, 한국만이면 없어요."""
    S = f"say-why {width}"
    by = {s["t"]: s for s in files["data.json"]["stocks"]}
    why = C["build"]["s1"]["remainWhy"]
    srv, ctx, page, _ = R.open(build_site(files), width)

    def line_geo():
        return page.evaluate("""() => { const l = document.querySelector('[data-ui-v2="meter-why"]'); const b = l.getBoundingClientRect();
            return { bar: document.querySelector('[data-ui-v2="meter-bar"]').getBoundingClientRect().bottom, top: b.top, left: b.left,
              right: b.right, size: parseFloat(getComputedStyle(l).fontSize), inBar: !!l.closest('[data-ui-v2="meter-bar"]'),
              prev: l.previousElementSibling && l.previousElementSibling.dataset.uiV2, next: l.nextElementSibling && l.nextElementSibling.textContent }; }""")

    def meter_line():
        wait_ready(page)
        start_build(page)
        page.locator('[data-deck="blank"]').click()
        see(page, C["build"]["s1"]["title"])
        assert meter(page)["pool"]                                         # 점수 전: 기준 전의 수
        line = page.locator('[data-ui-v2="meter-why"]')
        line.wait_for(state="visible")
        assert why == "하루 거래대금 5억원 미만 종목과 우선주는 빼고 셌어요." and line.inner_text().strip() == why, line.inner_text()
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(100)
        g = line_geo()
        assert not g["inBar"] and g["prev"] == "meter-bar", g                     # 위에 붙는 칸 안이 아니라 바로 밑
        assert g["bar"] - 0.5 <= g["top"] <= g["bar"] + 12, g
        assert C["build"]["s1"]["strictLabel"] in (g["next"] or ""), g           # 그다음은 그대로 깐깐함 칸
        assert g["size"] >= 12 and g["left"] >= 0 and g["right"] <= width + 0.5, g
        page.locator('[data-card="profit"] [data-ui-v2="card-inc"]').click()       # 점수를 준 뒤: 수는 엔진의 목록, 줄은 그대로
        m = meter(page)
        assert not m["pool"] and line.is_visible() and line.inner_text().strip() == why, m
        assert page.locator('[data-ui-v2="meter-why"]').count() == 1
        floor_ok(page, "기준 단계 say-why")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "기준 단계: 내 점수 칸 바로 밑(칸 밖)에 '하루 거래대금 5억원 미만 종목과 우선주는 빼고 셌어요.' · 점수 전 · 후 · 12px 이상", meter_line)
    ctx.close()
    srv.shutdown()

    def div_us(rows):
        el = page.locator('[data-ui-v2="plan-summary"] [data-ui-v2="div-us"]')
        info = page.evaluate("""(t) => { const pre = [...document.querySelectorAll('[data-ui-v2="plan-summary"] div')].find((e) => e.textContent === t);
            const n = pre && pre.nextElementSibling; return { pre: !!pre, next: n ? (n.dataset.uiV2 || '') : null,
              size: n && n.dataset.uiV2 === 'div-us' ? parseFloat(getComputedStyle(n).fontSize) : null }; }""", C["plan"]["preTax"])
        return el, info

    srv, ctx, page, _ = R.open(build_site(files), width)

    def us_plan():
        rows = to_plan(page)
        us = [t for t, n in rows if n > 0 and by[t]["cls"] == "us" and by[t].get("dy") is not None]
        assert us, rows                                                    # 이 계획에는 배당을 아는 미국 종목이 있어요
        el, info = div_us(rows)
        assert el.count() == 1 and el.is_visible() and el.inner_text().strip() == C["rpt"]["divUs"], el.all_inner_texts()
        assert C["rpt"]["divUs"] == "미국 종목은 최근 배당을 1년치로 환산한 값이에요."
        assert info["pre"] and info["next"] == "div-us" and info["size"] >= 12, info     # '세전 금액이에요' 바로 밑
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "매수 계획 · 연 배당금: 미국 종목을 사면 '세전 금액이에요' 밑에 '미국 종목은 최근 배당을 1년치로 환산한 값이에요.'", us_plan)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = R.open(build_site(files), width)

    def kr_plan():
        rows = to_plan_mix(page, C["build"]["s4"]["mix"]["kr"])
        assert rows and all(by[t]["cls"] == "kr" for t, n in rows), rows   # 한국만: 미국 종목이 없어요
        el, info = div_us(rows)
        assert el.count() == 0 and info["pre"] and info["next"] != "div-us", (el.all_inner_texts(), info)
        assert C["rpt"]["divUs"] not in page.locator("body").inner_text()
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "매수 계획 · 연 배당금: 한국만이면 미국 배당 줄이 없어요 ('세전 금액이에요'는 그대로)", kr_plan)
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


def scene_daily(R, files, width, trend=KR_DIV_TREND):
    # trend: 한국 배당 추세 스위치의 상태. 코드의 값이면 커밋한 app.html, 아니면 스위치만 반대로 놓은 빌드
    app = None if trend == KR_DIV_TREND else other_trend_app()
    S = f"매일 점검 {width} · {trend_label(trend)}"
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(daily_files(files), app=app), width, init=init)
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
        # 스위치가 꺼져 있으면 현대차의 배당 감소(12,000 → 10,000원)는 판정하지 않아요 (확인 필요 아님, 할 일 없음)
        drop = "check" if trend else "none"
        assert st == {("dcut", "005380"): drop, ("dclear", "005380"): drop, ("dwatch", "012450"): "watch",
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
    def no_cut_check():
        # 스위치 꺼짐: 주당 배당 기록이 분할을 고치지 않은 값이라 배당 감소를 말하지 않아요. 배당 삭감 규칙은 준비 중 줄로 보여요.
        for i in ("dcut", "dclear"):
            r = row(i, "005380")
            for sel in ('[data-ui-v2="status-line"]', '[data-ui-v2="confirm"]', '[data-ui="status-chip"]'):
                assert r.locator(sel).count() == 0, (i, sel)
            txt = r.inner_text()
            for bad in ("배당이 줄었어요", "주당 12,000원", C["pick"]["caution"]["divDropBody"], C["daily"]["broken"], C["daily"]["confirmCut"]):
                assert bad not in txt, (i, bad, txt)
            fold = r.locator('[data-ui="collapsible"]')
            fold.locator("button").first.click()
            pend = fold.locator('[data-rules-today] [data-ui-v2="rule-line"][data-check="pending"]', has_text=C["plan"]["rules"]["divCut"])
            assert pend.count() == 1, fold.inner_text()
            assert "주당" not in fold.locator("[data-rules-today]").inner_text(), fold.inner_text()
            R.collect(page)
            fold.locator("button").first.click()
    if trend:
        R.check(page, S, "배당 감소 → 확인 필요: 승인 문장 · 2025년 사업보고서 기준 · 두 버튼 (규칙 깨짐 아님)", check_needed)
    else:
        R.check(page, S, "배당 감소(분할일 수도) → 판정 없음: 확인 필요 · 두 버튼 · 감소 문장 없이 '배당 삭감' 준비 중 줄", no_cut_check)

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
        # 세는 규칙 = 보이는 준비 중 줄. 스위치가 꺼져 있으면 삼성전자의 배당 삭감 규칙도 준비 중이에요 (하나 더)
        assert shown == int(re.search(r"\d+", nc).group()) == (6 if trend else 7), (shown, nc)
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
    if trend:                                                           # 꺼져 있으면 답할 감소가 없어요 (반대 상태 빌드에서 시험해요)
        R.check(page, S, "실제로 줄였어요 → 규칙 깨짐 '배당 삭감 · 주당 12,000원 → 10,000원' · 새로 고침해도 남아요", confirm_cut)

    def confirm_clear():
        answer("dclear", "confirmNotCut")
        wait_status("dclear", "none")
        r = row("dclear", "005380")
        assert r.locator('[data-ui="status-chip"]').count() == 0 and checked("dclear") == ["false", "true"]
        assert "현대차 배당이 줄었어요 · 주당 12,000원 → 10,000원" in r.locator('[data-ui-v2="status-line"][data-code="divCleared"]').inner_text()
        assert row("dcut", "005380").get_attribute("data-status") == "broken"
        R.collect(page)
    if trend:
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
    if trend:
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
        assert page.locator('[data-ui-v2="home-block"]').count() == len(DAILY_DECKS["decks"])
        no_hscroll(page, width)
        R.collect(page)
    def today_hero_no_cut():
        # 스위치 꺼짐: 오늘 확인할 일은 기아(부채비율 자료 없음)뿐, 배당 삭감 · 매도 조건은 없어요
        tab(page, C["app"]["tabs"]["home"])
        hero = page.locator('[data-ui-v2="today-hero"]')
        hero.wait_for(state="visible")
        assert hero.get_attribute("data-state") == "todo", hero.inner_text()
        items = hero.locator('[data-ui-v2="todo-item"]').evaluate_all("els => els.map(e => e.dataset.t + ':' + e.dataset.status)")
        assert items == ["000270:check"], items
        txt = hero.inner_text()
        assert txt.startswith("오늘 확인할 일 1개") and "부채비율 자료를 받지 못해 확인이 필요해요" in txt, txt
        for bad in (C["daily"]["sellNow"], C["today"]["sellLabel"], "배당 삭감", "배당이 줄었어요", C["pick"]["caution"]["divDropBody"]):
            assert bad not in txt, (bad, txt)
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", txt)
        assert page.locator('[data-ui-v2="home-block"]').count() == len(DAILY_DECKS["decks"])
        no_hscroll(page, width)
        R.collect(page)
    if trend:
        R.check(page, S, "오늘: 확인할 일 띠 '오늘 확인할 일' (매도 조건 먼저 · 확인 필요) · 못 하는 규칙 줄 · 큰 움직임은 따로 · 덱마다 띠", today_hero)
    else:
        R.check(page, S, "오늘: 확인할 일은 자료 없는 기아뿐 · 배당 삭감 · 매도 조건 없음 · 못 하는 규칙 줄", today_hero_no_cut)
    ctx.close()
    srv.shutdown()

    for how, f, drop in (("멈춤", daily_files(files, days_ago=6), ()), ("실패", daily_files(files), ("data.json",))):
        srv, ctx, page, _ = R.open(build_site(f, drop=drop, app=app), width, init=init)

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
            for sel in ('[data-ui-v2="today-hero"]', '[data-ui-v2="home-block"]', '[data-ui-v2="big-moves"]', '[data-ui-v2="today-not-checked"]'):
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
        R.check(page, f"매일 점검 · {how} {width} · {trend_label(trend)}", "판정 없음 (상태 · 버튼 · 규칙 결과 모두 없음) + 이유 문장, 기록은 그대로", no_status)
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


def scene_today(R, files, width, trend=KR_DIV_TREND):
    # trend: 한국 배당 추세 스위치의 상태. 코드의 값이면 커밋한 app.html, 아니면 스위치만 반대로 놓은 빌드
    app = None if trend == KR_DIV_TREND else other_trend_app()
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
        return R.open(site or build_site(f, app=app), width, init=init)

    def hero(page):
        h = page.locator('[data-ui-v2="today-hero"]')
        h.wait_for(state="visible")
        disc_settled(page)
        return h

    def not_checked(text):
        assert re.search(r"아직 자동으로 확인하지 못하는 규칙이 \d+개 있어요", text), text

    def no_cut(t):
        # 스위치 꺼짐: 기록의 배당 감소(답하지 않은 것)는 판정하지 않아요 (주식 분할일 수 있어요). 배당 삭감 규칙은 준비 중으로
        # '못 하는 규칙' 줄에 들어가요.
        h = hero(page)
        txt = h.inner_text()
        assert h.get_attribute("data-state") == "calm" and C["today"]["calmTitle"] in txt, txt
        for bad in ("매도 조건에 걸렸어요", C["daily"]["sellNow"], C["today"]["sellLabel"], "배당 삭감", "배당이 줄었어요",
                    C["pick"]["caution"]["divDropBody"], C["daily"]["confirmCut"], C["daily"]["confirmNotCut"]):
            assert bad not in txt, (bad, txt)
        assert h.locator('[data-ui-v2="todo-item"]').count() == 0 and h.get_by_role("radio").count() == 0
        assert page.locator(f'[data-home-holding="{t}"] [data-ui="status-chip"]').count() == 0
        not_checked(txt)
        verdict_icon(h, "calm")
        no_hscroll(page, width)
        R.collect(page)

    S = f"오늘·내 덱 {width} · {trend_label(trend)}"
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
        assert page.locator('[data-home-holding="105560"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["broken"]]
        assert page.locator('[data-home-holding="005930"] [data-ui="status-chip"]').count() == 0          # 칩 없음 = 괜찮아요
        strip = page.locator('[data-ui-v2="home-money"]').inner_text()
        assert C["home"]["gain"].split(" {")[0] in strip and re.search(r"오늘 [+−]?[\d,]+(만원|원) \([+−]?\d+\.\d%\)", strip), strip
        no_hscroll(page, width)
        R.collect(page)
    # '실제로 줄였어요'라고 답한 삭감은 사용자가 분할이 아니라고 확인한 것이라, 스위치가 꺼져 있어도 그대로 매도 조건이에요
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
        assert page.locator('[data-home-holding="012450"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["watch"], C["daily"]["bigMove"]]
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
        assert page.locator('[data-home-holding="005380"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["check"]]
        not_checked(txt)
        verdict_icon(h, "alert")
        assert hero_colours(h) == ["rgb(255, 243, 214)", "rgb(138, 90, 0)", "rgb(255, 255, 255)"], hero_colours(h)   # 확인 필요만: 지켜봐요 알약
        R.collect(page)
        h.get_by_role("radio", name=C["daily"]["confirmNotCut"]).click()
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"today-hero\"]').dataset.state === 'calm'")
        assert C["today"]["calmTitle"] in hero(page).inner_text()
        verdict_icon(hero(page), "calm")
        R.collect(page)
    if trend:
        R.check(page, S, "확인 필요 → 확인할 일 띠(지켜봐요 알약 · flag)의 두 버튼 → '줄인 게 아니에요' → 초록 띠(check-circle)", check)
    else:
        R.check(page, S, "배당 감소(현대차 12,000 → 10,000원) → 판정 없음: 초록 띠 · 두 버튼 · 감소 문장 없음", lambda: no_cut("005380"))
    ctx.close()
    srv.shutdown()

    srv, ctx, page, _ = ctx_for("band")

    def band():
        h = hero(page)
        assert h.get_attribute("data-state") == "calm"
        txt = h.inner_text()
        assert C["today"]["calmTitle"] in txt and C["today"]["calmEyebrow"] not in txt, txt        # 줄일 차례는 할 일이 있어요
        not_checked(txt)
        chips = {t: page.locator(f'[data-home-holding="{t}"] [data-ui="status-chip"]').all_inner_texts() for t in ("005930", "035420")}
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
    kept = 2 if trend else 1         # 배당(산 뒤 새 보고서) + 비중 · 스위치가 꺼져 있으면 배당 규칙은 준비 중이라 세지 않아요

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
        assert page.locator('[data-home-holding="000660"] [data-ui="status-chip"]').all_inner_texts() == [C["daily"]["bigMove"]]
        R.collect(page)
        inset.locator('[data-ui-v2="why-link"]').click()
        see(page, "SK하이닉스 왜 움직였나")
        head = page.locator('[data-ui-v2="why-head"]').inner_text()
        assert "반도체 · 10월 30일 종가" in head and "1,418,000원" in head and "−6.2%" in head, head
        v = page.locator('[data-ui-v2="why-verdict"]')
        assert v.get_attribute("data-status") == "none"
        vt = v.inner_text()
        assert C["why"]["noTodo"] in vt and "업종이 다 같이\n빠진 날이에요" in vt and f"규칙 {kept}개가 모두 지켜지고 있어요." in vt, vt
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
        assert f"규칙 {kept}개가 모두 지켜지고 있어요" in rules and C["app"]["notChecked"] in rules, rules
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
        srv, ctx, page, _ = ctx_for("sell", site=build_site(g, drop=drop, app=app))

        def refused():
            see(page, LOAD_FAIL)
            for sel in ('[data-ui-v2="today-hero"]', '[data-ui-v2="home-block"]', '[data-ui-v2="today-not-checked"]'):
                assert page.locator(sel).count() == 0, sel
            assert page.get_by_text("할 일").count() == 0 and page.get_by_text(C["daily"]["sellNow"]).count() == 0
            R.collect(page)
        R.check(page, f"오늘 · {how} {width} · {trend_label(trend)}", "저장한 덱이 있어도 불러오기 실패 문구만, 할 일 띠 없음", refused)
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
    try:
        page.wait_for_function("""() => { const l = [...document.querySelectorAll('[data-ui-v2="about"] img')];
                                          return l.length === 2 && l.every((i) => i.complete && i.naturalWidth > 0); }""",
                               timeout=IMG_WAIT_MS)
    except PWTimeout:
        pass                # 아래 assert 가 어느 그림이 안 열렸는지 보여 줘요
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


def stored_records(page, seen):
    """저장된 기록에서 이 기기의 '처음 안내를 봤어요' 표시(guideSeen: 본 날)를 뺀 나머지. 그 표시는 기록 파일로 옮겨 다니지 않아요
    (store.js: a flag of this device). 표시는 꼭 있어야 하고 seen 과 같아야 해요 (v19.3c 처음 안내가 첫 방문에 저절로 떠요, Jack 2026-11-08)."""
    d = page.evaluate(STORED)
    assert isinstance(d, dict) and d.get("guideSeen") == seen, (d or {}).get("guideSeen") if isinstance(d, dict) else d
    return {k: v for k, v in d.items() if k != "guideSeen"}
# 받은 파일의 주소(Blob URL)를 언제 지우는지 기록해요: 바로(1초 안에) 지우면 iOS 사파리가 받다가 실패할 수 있어요 (v18.4.1, 60초 뒤)
REVOKE_SPY = """() => { if (window.__revoked) return; window.__revoked = []; const orig = URL.revokeObjectURL.bind(URL);
  URL.revokeObjectURL = (u) => { window.__revoked.push(u); return orig(u); }; }"""


def standalone_ua(ua):
    """홈 화면에 추가한 앱의 사용자 에이전트: 사파리와 같은데 끝의 'Version/…' · 'Safari/…' 가 없어요."""
    return re.sub(r" Safari/\S+$", "", re.sub(r" Version/\S+", "", ua))


HOME_SETTLE_S = 15                      # 홈이 공시(disc.json)를 다 받기까지 기다리는 한도 (초): 넘으면 그 검사는 실패해요


def home_settled(page, limit_s=HOME_SETTLE_S):
    """홈(저장한 덱이 있는 오늘 화면)이 다 그려질 때까지: today-hero 가 보이고, 홈이 따로 받는 공시(disc.json)가 끝난 뒤(disc_settled).
    받는 동안은 '오늘은 할 일이 없어요' 줄이 아직 없어서, 두 화면의 글을 견주기 전에 기다려요 (Jack, 2026-11-13: 시간 한도가 있고, 넘으면
    실패). 한도 안에 끝나지 않으면 이유를 말하며 실패해요 — 견주기로 넘어가지 않아요. (앱의 disc.json 한도는 60초: load.REFETCH_TIMEOUT_MS)"""
    ms = int(limit_s * 1000)
    page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible", timeout=ms)
    try:
        disc_settled(page, timeout=ms)
    except PWTimeout:
        raise AssertionError(f"홈의 공시(disc.json)가 {limit_s}초 안에 끝나지 않았어요 (data-disc 'wait'): 화면 글을 견주지 않고 멈춰요") from None


def scene_home_settled_limit(R, files):
    """home_settled 의 시간 한도: disc.json 이 끝내 오지 않는 사이트에서 한도(15초) 안에 이유를 말하며 실패하고, 견주기로 넘어가지 않아요."""
    S = "홈 공시 기다림 한도"
    srv, ctx, page, base = R.open(build_site(files), 390, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")
    held = []
    page.route("**/disc.json", lambda r: held.append(r))                       # 대답하지 않는 disc.json (검사가 끝날 때까지 붙잡아 둬요)

    def never():
        page.reload(wait_until="domcontentloaded")                              # R.open 이 이미 연 첫 화면의 disc.json 은 길을 막기 전이라 다시 열어요
        # (wait_ready 는 쓰지 않아요: 그것도 공시가 끝나기를 15초까지 기다려요. 여기서는 home_settled 의 한도만 봐요)
        t0 = time.monotonic()
        try:
            home_settled(page)
            got = None
        except AssertionError as e:
            got = str(e)
        took = time.monotonic() - t0
        assert got and "disc.json" in got and f"{HOME_SETTLE_S}초" in got, got
        assert HOME_SETTLE_S - 1 <= took <= HOME_SETTLE_S + 5, took                # 한도에서 멈춰요 (끝없이 기다리지 않아요)
        assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "wait"
    R.check(page, S, f"disc.json 이 오지 않으면 home_settled 는 {HOME_SETTLE_S}초 한도에서 이유를 말하며 실패해요 (아이폰 기록 옮기기의 화면 견주기 앞)", never)
    for r in held:                                                              # 붙잡아 둔 요청은 닫기 전에 끊어요 (닫을 때 소음이 없게)
        try:
            r.abort()
        except Exception:
            pass
    ctx.close()
    srv.shutdown()


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
    tmp = tmpdirs.make("baepsae-records-")       # 받은 파일 · 시험 파일 · 사이트를 한 폴더에 두고 끝나면 지워요
    try:
        _iphone_records(R, files, device, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _iphone_records(R, files, device, tmp):
    S = "아이폰 기록 옮기기"
    dev = {k: v for k, v in device.items() if k != "default_browser_type"}
    width = dev["viewport"]["width"]
    site = os.path.join(tmp, "site")
    day = (dt.date.fromisoformat(files["data.json"]["pxDate"]) - dt.timedelta(days=2)).isoformat()   # 오늘이 아닌 산 날
    # v19.6a (A.1): a US purchase dated in the past saves the rate of its own date from macro.json fxHist (before: the data's
    # current rate, the wrong day's). The scene's files carry that day's close (1325.5, not the data's fx).
    files = clone(files)
    files["macro.json"]["fxHist"] = {"asOf": files["data.json"]["fxDate"], "final": True, "rows": [[day, 1325.5], [files["data.json"]["fxDate"], files["data.json"]["fx"]]]}
    shutil.move(build_site(files), site)
    by = {x["t"]: x for x in files["data.json"]["stocks"]}
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

    def first_diff(a, b):
        """두 화면 글이 처음 다른 줄 (실패 메시지에 붙여요)."""
        la, lb = a.splitlines(), b.splitlines()
        i = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y), min(len(la), len(lb)))
        return f"{i + 1}번째 줄: {la[i] if i < len(la) else '(끝)'!r} → {lb[i] if i < len(lb) else '(끝)'!r}"

    def open_today_tab(page):
        tab(page, C["app"]["tabs"]["home"])
        home_settled(page)

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
        assert ps[us]["ccy"] == "USD" and ps[us]["fx"] == 1325.5 and ps[kr]["ccy"] == "KRW", (ps[us], ps[kr])   # 산 날의 환율 (v19.6a)
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
        keep["seen"] = (page.evaluate(STORED) or {}).get("guideSeen")         # 처음 안내를 본 날: 앱이 옛 칸에서 읽어 온 오늘(한국 날짜)
        assert keep["seen"] == now_dt().strftime("%Y-%m-%d"), keep["seen"]
        assert stored_records(page, keep["seen"]) == keep["file"], "불러온 기록이 파일과 달라요 (덱 · 종목 · 산 기록 · 규칙)"
        assert page.evaluate(OTHER_KEYS) == others, "기록 말고 다른 저장 값이 바뀌었어요"
        page.locator("[data-holding][data-status]").first.wait_for(state="visible")
        page.locator('[data-ui-v2="deck-value"]').wait_for(state="visible")
        assert main_text(page) == keep["deck"], "포트폴리오 화면이 사파리에서 본 것과 달라요"
        assert hint_kinds(page) == [], "홈 화면 앱 안에서 홈 화면 안내가 보여요"
        open_today_tab(page)
        t = main_text(page)
        assert t == keep["today"], "오늘 화면이 사파리에서 본 것과 달라요 · " + first_diff(keep["today"], t)
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        home_settled(page)                                                    # 저장한 덱이 있으면 오늘부터
        t = main_text(page)
        assert t == keep["today"] and stored_records(page, keep["seen"]) == keep["file"], "새로 고침 뒤에 기록이 달라요 · " + first_diff(keep["today"], t)
        R.collect(page)
    R.check(page, S, "새 저장소(홈 화면 앱처럼 따로): 기록 불러오기 → 같은 덱 · 종목 · 산 기록 · 규칙, 내 덱 · 오늘 화면도 같음", home_screen)

    def twice():
        open_deck_tab(page)
        imp.set_input_files(keep["path"])
        page.wait_for_timeout(1000)                                   # 불러오기는 바로 끝나요 (바뀌는 게 없어야 해서 기다려서 봐요)
        assert page.locator("[data-deck-id]").count() == 1 and stored_records(page, keep["seen"]) == keep["file"], "같은 파일을 두 번 불러 덱이 늘었어요"
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
        assert page.locator("[data-deck-id]").count() == 1 and stored_records(page, keep["seen"]) == keep["file"], "막힌 파일이 기록을 바꿨어요"
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
        assert got == [(C["market"]["macro"], "./baepsae.html?from=app#macro"), (C["market"]["disc"], "./baepsae.html?from=app#disc")], got
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
    """종목: 찾기 · 최근 본 종목 · 종목 순위(v19.5b: 거래대금 상위 종목의 칩 판 — 한국 · 미국 따로, 날짜, 멈춘 30개) · 한국 · 미국 회사 →
    2.0 회사 페이지(v19.1a, 예전에는 한국 회사는 예전 뱁새 기업분석, 미국 종목은 '기업분석은 한국 상장 기업만 볼 수 있어요.' 줄) → 뒤로 → 종목."""
    S = f"종목 {width}"
    srv, ctx, page, base = R.open(build_site(files), width, path="/app.html?dev=1#stocks")

    def lists():
        wait_ready(page)
        at(page, "stocks")
        assert page.locator("main h2").first.inner_text() == TABS["stocks"]
        box = page.locator('[data-ui-v2="stock-search"] input')
        assert box.get_attribute("aria-label") == (C["stocks"]["search"] or TABS["stocks"])
        rank = page.locator('[data-ui-v2="rank"]')                 # v19.5b: 거래대금 상위 종목 → 종목 순위 (멈춘 30개, 홈의 전체 보기가 여는 곳)
        rank.wait_for(state="visible")
        assert rank.get_attribute("data-full") == "1" and rank.locator("h3").inner_text() == C["rank"]["title"]
        assert page.locator('svg[data-ph="fire"]').count() == 0 and "많이 찾는" not in page.locator("body").inner_text()
        rank_chip(page, "val")                                            # 거래대금 칩: 예전 목록의 순서 기준 (거래대금 큰 순)
        mk = rank.locator('[data-ui-v2="rank-market"] [role="radio"]')
        assert [mk.nth(i).inner_text() for i in range(mk.count())] == [C["pick"]["market"]["kr"], C["pick"]["market"]["us"]]
        stocks = files["data.json"]["stocks"]
        for key, date, line in (("kr", "10월 30일 종가", C["rank"]["line"]["val"]), ("us", "10월 30일 종가 (미국 시간)", C["rank"]["line"]["valUs"])):
            rank_market(page, key)
            got = rank_ts(page)
            assert got == rank_expect(stocks, key, "val")[:30] and len(got) == 30, (key, got)    # 거래대금 큰 순, 시장마다 따로, 펀드 · 우선주 없음
            assert all(by_t(stocks)[t]["cls"] == key and not by_t(stocks)[t].get("etf") for t in got), got
            assert rank.locator('[data-ui-v2="rank-date"]').inner_text() == date and rank.locator('[data-ui-v2="rank-line"]').inner_text() == line
            assert rank.locator('[data-ui-v2="rank-window"]').get_attribute("data-still") == "full" and rank.locator('[data-ui-v2="rank-copy"]').count() == 0
            assert re.search(r"[+−]\d+\.\d%", rank.inner_text()), rank.inner_text()      # 종목 탭은 오늘 등락을 보여요 (뱁이 없음)
        rank_market(page, "kr")
        assert page.locator('[data-ui-v2="rank-all"], [data-ui-v2="rank-hint"]').count() == 0     # 여기가 전체 보기예요 (멈춘 목록)
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "종목 순위(거래대금 상위 종목의 칩 판): 한국 · 미국 따로 · 거래대금 순서 · 날짜 · 멈춘 30개 (불 아이콘 · '많이 찾는' 없음)", lists)

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
        assert page.locator('[data-ui-v2="rank"]').count() == 0             # 찾는 동안은 결과만
        box.fill("zzzz없는회사")
        nr = page.locator('[data-ui-v2="no-result"]')
        nr.wait_for(state="attached")
        assert (nr.inner_text() == C["stocks"]["noResult"]) if C["stocks"]["noResult"] else nr.get_attribute("data-pending") == "1"
        box.fill("")
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, S, "찾기: '삼성' → 이름에 삼성이 든 종목 · 없는 이름 → 결과 없음 자리", search)

    def us_line():
        # v19.1a: 미국 종목도 회사 페이지가 있어요 (예전: '기업분석은 한국 상장 기업만 볼 수 있어요.' 줄)
        rank_market(page, "us")                                            # v19.5b: 종목 순위의 미국 목록
        us = page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').first
        t = us.get_attribute("data-t")
        assert us.get_attribute("data-cls") == "us"
        assert us.locator("a").count() == 0 and us.locator("button").get_attribute("aria-expanded") is None
        us.locator("button").click()
        at(page, f"stocks/{t}")
        page.locator('[data-ui-v2="company"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="company"]').get_attribute("data-cls") == "us" and "/baepsae.html" not in page.url
        assert page.get_by_text(C["stocks"]["krOnly"]).count() == 0
        page.go_back()
        at(page, "stocks")
        R.collect(page)
        keep["us"] = t
    keep = {}
    R.check(page, S, "미국 종목을 누르면 2.0 회사 페이지 (#stocks/티커) → 뒤로 → 종목", us_line)

    def kr_corp():
        rank_market(page, "kr")                                            # v19.5b: 종목 순위의 한국 목록
        row = page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').first
        t = row.get_attribute("data-t")
        assert row.get_attribute("data-cls") == "kr"
        assert row.locator("a").count() == 0, "한국 회사 줄이 예전 뱁새로 가는 링크예요"
        row.locator("button").click()
        at(page, f"stocks/{t}")                                            # v19.1a: 2.0 회사 페이지 (예전 뱁새 기업분석 아님)
        page.locator('[data-ui-v2="company"]').wait_for(state="visible")
        assert "/baepsae.html" not in page.url and page.url.endswith(f"#stocks/{t}"), page.url
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
    R.check(page, S, "한국 회사 → 2.0 회사 페이지(#stocks/코드, 예전 뱁새 아님) → 뒤로 → 종목 · 최근 본 종목에 남아요", kr_corp)
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
        strip = page.locator('[data-ui-v2="home-money"][data-deck-id="dgone"]')
        strip.wait_for(state="visible")
        assert strip.locator('[data-ui-v2="missing-line"]').inner_text() == line
        assert page.locator('[data-ui-v2="home-money"][data-deck-id="dkeep"] [data-ui-v2="missing-line"]').count() == 0
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
        assert page.locator('[data-ui-v2="today-hero"], [data-ui-v2="home-hero"], [data-ui-v2="home-block"]').count() == 0
        assert page.get_by_text("할 일").count() == 0, "점검한 종목이 없는데 '할 일'이 보여요"
        page.locator('[data-ui-v2="market-glance"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, f"산 종목 없음 {width}", "저장한 포트폴리오에 산 종목이 없으면 홈은 판정 없이 '포트폴리오 만들기'만 (첫 방문 머리글 아님)", run)
    ctx.close()
    srv.shutdown()


# ── PC (v19.0d): 1024px 부터 왼쪽 메뉴 · 위 검색 칸 · 두 칸 홈과 시장 ──
PC_W, PC_H = 1280, 800
TAB_KEYS = ("home", "portfolio", "stocks", "market")
TOP_INPUT = '[data-ui-v2="top-search"] input'


def pc_device(width, height=PC_H):
    return {"viewport": {"width": width, "height": height}, "device_scale_factor": 1}


def side_tab(page, key):
    """왼쪽 메뉴의 탭을 눌러요."""
    page.locator(f'[data-ui-v2="side-tab"][data-tab="{key}"]').click()
    at(page, key)


def side_by_side(a, b):
    """a 는 왼쪽 열, b 는 오른쪽 열: 겹치지 않고 윗변이 같아요."""
    ra, rb = a.bounding_box(), b.bounding_box()
    assert ra and rb, (ra, rb)
    assert ra["x"] + ra["width"] <= rb["x"] + 0.5 and abs(ra["y"] - rb["y"]) < 1.5, (ra, rb)
    return ra, rb


def page_box(page):
    """지금 화면의 본문(main) 상자와 칸 수: (x, 내용 폭, 칸 수). 내용 폭은 좌우 여백 32px 씩을 뺀 폭이에요."""
    m = page.locator('main[data-ui-v2="page"]').first
    b = m.bounding_box()
    return b["x"], b["width"] - 64, m.get_attribute("data-cols")


def focused_in(page, sel):
    return page.evaluate("(s) => { const a = document.activeElement; return !!a && !!a.closest(s); }", sel)


def pc_shell(page, width, live=True):
    """PC 틀: 왼쪽 메뉴 240px 고정(로고 마크 38px · '뱁새' 24px/800 · 캐치프레이즈 · 탭 넷 · 포트폴리오 만들기 · 날짜 칸 · 메뉴 링크),
    위 검색 칸(520px 이하, 승인된 '회사 이름이나 종목코드로 찾기'), 아래 탭 막대 · ☰ · ☰ 메뉴 · 머리말 이름 없음, 가로 스크롤 없음."""
    side = page.locator('[data-ui-v2="side-menu"]')
    side.wait_for(state="visible")
    box = side.bounding_box()
    assert box["x"] == 0 and abs(box["width"] - 240) < 0.5 and abs(box["height"] - page.viewport_size["height"]) < 1, box
    assert side.evaluate("(e) => getComputedStyle(e).position") == "fixed"
    mark = side.locator('img[data-ui-v2="logo-mark"]')
    assert mark.get_attribute("src") == "baepi-mark.webp" and mark.get_attribute("alt") == "" and img_loaded(mark)
    assert abs(mark.bounding_box()["width"] - 38) < 0.5
    word = side.locator('h1[data-ui-v2="wordmark"]')
    assert word.inner_text() == C["app"]["brand"] and word.evaluate("(e) => [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight]") == ["24px", "800"]
    assert side.locator('[data-ui-v2="side-catch"]').inner_text() == C["about"]["ko"]["hero"]["catch"]
    nav = side.locator("nav")
    assert nav.get_attribute("aria-label") == C["app"]["tabsLabel"]
    tabs = nav.locator('[data-ui-v2="side-tab"]')
    assert [t.strip() for t in tabs.all_inner_texts()] == [TABS[k] for k in TAB_KEYS]
    assert tabs.locator("svg").evaluate_all("(els) => els.map((e) => e.dataset.ph)") == ["house", "chart-pie-slice", "buildings", "chart-line-up"]
    assert side.locator('[data-ui-v2="side-build"]').inner_text().strip() == C["build"]["title"]
    links = side.locator('[data-ui-v2="side-link"]')
    got = [(links.nth(i).get_attribute("data-item"), links.nth(i).inner_text().strip(), links.nth(i).get_attribute("href")) for i in range(links.count())]
    want = [("about", C["app"]["aboutLink"], None)]
    if live:
        want += [("glossary", C["menu"]["glossary"], "./baepsae.html?from=app#info=glossary"), ("sources", C["menu"]["sources"], "./baepsae.html?from=app#info=sources"),
                 ("guide", C["menu"]["guide"], None), ("old-app", C["app"]["oldApp"], "./baepsae.html?from=app")]
    else:
        want += [("guide", C["menu"]["guide"], None)]
    assert got == want, got
    assert "10월 30일 기준" in side.locator('[data-ui-v2="side-date"] [data-ui-v2="date-line"]').inner_text()
    for gone in ('nav[data-ui="bottom-tab-bar"]', '[data-ui-v2="menu-button"]', '[data-ui-v2="menu"]', '[data-ui-v2="app-bar"] h1'):
        assert page.locator(gone).count() == 0, f"PC 에 {gone}"
    search = page.locator('[data-ui-v2="top-search"]')
    sb = search.bounding_box()
    assert sb["width"] <= 520.5 and sb["x"] >= 240, sb
    inp = search.locator("input")
    assert inp.get_attribute("placeholder") == C["stocks"]["search"] and inp.get_attribute("aria-label") == C["stocks"]["search"]
    x, _, _ = page_box(page)
    assert abs(sb["x"] - (x + 32)) < 0.5, ("검색 칸과 본문의 왼쪽 끝", sb, x)
    no_hscroll(page, width)


def tab_selected(page, key):
    """고른 탭: aria-current 와 따뜻한 회색 바탕(살구색 아님, 나머지 탭은 바탕 없음)."""
    on = page.locator('[data-ui-v2="side-tab"][aria-current="page"]')
    assert on.count() == 1 and on.get_attribute("data-tab") == key, on.count()
    assert on.evaluate("(e) => getComputedStyle(e).backgroundColor") == SELECT_RGB
    off = page.locator('[data-ui-v2="side-tab"]:not([aria-current])').evaluate_all("(els) => els.map((e) => getComputedStyle(e).backgroundColor)")
    assert off == ["rgba(0, 0, 0, 0)"] * 3, off


SLASH_PROBE = """(kind) => { const old = document.getElementById('pc-probe'); if (old) old.remove();
  let e; if (kind === 'contenteditable') { e = document.createElement('div'); e.contentEditable = 'true'; e.textContent = 'x'; }
  else if (kind === 'select') { e = document.createElement('select'); e.innerHTML = '<option>a</option><option>b</option>'; }
  else { e = document.createElement(kind); }
  e.id = 'pc-probe'; document.body.appendChild(e); e.focus(); return document.activeElement === e; }"""


def scene_pc(R, files):
    """첫 방문 PC (1280 × 800): 왼쪽 메뉴 · 첫 방문 홈 두 칸 · '/' · 검색 칸 → 종목 · 시장 두 칸 · 포트폴리오 만들기의 아래 띠와 시트."""
    S = f"PC {PC_W}"
    srv, ctx, page, base = R.open(build_site(files), PC_W, device=pc_device(PC_W))

    def landing():
        wait_ready(page)
        at(page, "home")
        pc_shell(page, PC_W)
        tab_selected(page, "home")
        # 첫 방문 홈 (v19.5b): 머리글이 위, 종목 순위가 그 아래 페이지 폭으로 (오른쪽 칸만 있는 Cols), 창에 7줄. 숫자가 있어서 뱁이 없음
        # (예전: 뱁이 176px + 거래대금 상위 종목 한국 | 미국 이름만)
        hero = page.locator('[data-ui-v2="home-hero"]')
        hero.wait_for(state="visible")
        assert C["about"]["ko"]["hero"]["descriptor"] in hero.inner_text() and C["about"]["ko"]["hero"]["catch"] in hero.inner_text()
        assert hero.locator('[data-ui-v2="home-start"]').inner_text().strip() == C["build"]["title"]
        assert page.locator('[data-ui-v2="market-glance"], [data-ui-v2="market-tile"]').count() == 0, "첫 방문 홈에 시장 칸 (v19.5b 는 종목 순위만 더해요)"
        rank = page.locator('[data-ui-v2="cols"][data-n="1"] [data-ui-v2="rank"]')
        rank.wait_for(state="visible")
        assert rank.locator('[data-ui-v2="rank-window"]').get_attribute("data-rows") == "7"
        assert rank.bounding_box()["y"] > hero.bounding_box()["y"] + hero.bounding_box()["height"]
        assert page.locator(MASCOT_IN_MAIN).count() == 0, "숫자가 있는 첫 방문 홈에 뱁이"
        x, w, cols = page_box(page)
        assert cols == "2" and w <= 1000 and x >= 240, (x, w, cols)
        R.collect(page)
    R.check(page, S, "왼쪽 메뉴(로고 · 탭 넷 · 포트폴리오 만들기 · 날짜 칸 · 메뉴 링크 넷) · 아래 탭 · ☰ 없음 · 위 검색 칸 · 첫 방문 홈(머리글 · 종목 순위 7줄, 뱁이 없음)", landing)

    def slash():
        inp = page.locator(TOP_INPUT)
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.keyboard.press("/")                                           # 아무 칸에도 쓰지 않을 때: 검색 칸으로, '/' 는 들어가지 않아요
        page.wait_for_function("() => document.activeElement && document.activeElement.matches('[data-ui-v2=\"top-search\"] input')")
        assert inp.input_value() == "", inp.input_value()
        page.keyboard.type("삼성")                                          # 쓰면 종목 탭에 결과 (초점은 칸에 그대로)
        at(page, "stocks")
        assert page.url.endswith("#stocks"), page.url
        rows = page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"]')
        rows.first.wait_for(state="visible")
        names = rows.all_inner_texts()
        assert len(names) >= 4 and all("삼성" in n for n in names), names
        assert focused_in(page, '[data-ui-v2="top-search"]') and inp.input_value() == "삼성"
        assert page.locator('[data-ui-v2="stock-search"]').count() == 0, "PC 종목 탭에 검색 칸이 둘"
        tab_selected(page, "stocks")
        x, w, cols = page_box(page)
        assert cols == "1" and w <= 720, (w, cols)
        R.collect(page)
        inp.fill("")                                                       # 비우면 종목 탭의 목록으로 (탭은 그대로)
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        assert route(page) == "stocks"
        inp.fill("Apple")
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-cls="us"]').first.wait_for(state="visible")
        side_tab(page, "home")                                             # 종목을 떠나면 칸이 비어요 (홈에 지난 검색어가 남지 않음)
        # 칸은 화면이 홈으로 바뀐 다음 렌더에서 비워져요 (app.jsx 의 effect). GitHub 의 기계에서는 그 사이에 읽혀 실패했어요 (v17.6 CI,
        # 2026-11-05) — 비워질 때까지 3초 기다린 뒤 똑같이 확인해요. 끝내 안 비면 여전히 실패예요.
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.value === ''; }", arg=TOP_INPUT, timeout=3000)
        assert inp.input_value() == "", inp.input_value()
        for kind in ("input", "textarea", "select", "contenteditable"):    # 다른 칸에 쓰는 중이면 '/' 는 그 칸의 글자
            assert page.evaluate(SLASH_PROBE, kind), kind
            page.keyboard.press("/")
            page.wait_for_timeout(50)
            assert page.evaluate("() => document.activeElement && document.activeElement.id") == "pc-probe", kind
            assert inp.input_value() == "" and route(page) == "home", kind
            typed = page.evaluate("() => { const e = document.getElementById('pc-probe'); return e.value != null ? e.value : e.textContent; }")
            assert kind == "select" or "/" in typed, (kind, typed)
        page.evaluate("() => document.getElementById('pc-probe').remove()")
        page.keyboard.press("Control+/")                                    # 단축키와 같이 누른 '/' 도 아니에요
        page.wait_for_timeout(50)
        assert not focused_in(page, '[data-ui-v2="top-search"]')
    R.check(page, S, "'/' → 검색 칸(글자는 안 들어감) · 쓰면 종목 탭에 결과 · 종목을 떠나면 칸이 비어요 · input · textarea · select · contenteditable 에 쓰는 중이면 그 칸 그대로", slash)

    def market_two():
        side_tab(page, "market")
        tab_selected(page, "market")
        assert page.locator("main h2").first.inner_text() == TABS["market"]
        tiles = page.locator('[data-ui-v2="col-main"] [data-ui-v2="market-tiles-card"]')
        more = page.locator('[data-ui-v2="col-side"] [data-ui-v2="market-more"]')
        side_by_side(tiles, more)
        assert page.locator('[data-ui-v2="market-tile"]').count() == 4 and tiles.locator('[data-ui-v2="market-tiles"]').get_attribute("data-cols") == "2"
        x, w, cols = page_box(page)
        assert cols == "2" and w <= 1000, (w, cols)
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        no_hscroll(page, PC_W)
        R.collect(page)
    R.check(page, S, "시장 두 칸: 네 칸 | 예전 뱁새로 가는 두 버튼", market_two)

    def about_one():
        page.locator('[data-ui-v2="side-link"][data-item="about"]').click()      # 소개: 왼쪽 메뉴는 그대로, 한 칸, 뱁이 210px · 사진 112px
        page.locator('[data-ui-v2="about"]').wait_for(state="visible")
        assert page.url.endswith("#about")
        assert page.locator('[data-ui-v2="side-tab"][aria-current]').count() == 0
        assert page.locator('[data-ui-v2="side-link"][data-item="about"]').get_attribute("aria-current") == "page"
        assert abs(page.locator('img[src="baepi-og.webp"]').bounding_box()["width"] - 210) < 0.5
        assert abs(page.locator('[data-ui-v2="about-photo"]').bounding_box()["width"] - 112) < 0.5
        x, w, cols = page_box(page)
        assert cols == "1" and w <= 720, (w, cols)
        no_hscroll(page, PC_W)
        R.collect(page)
        page.go_back()
        at(page, "market")
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
    R.check(page, S, "소개(왼쪽 메뉴의 링크): 한 칸 · 뱁이 210px · 사진 112px · 뒤로 → 시장", about_one)

    def about_search():
        link = page.locator('[data-ui-v2="side-link"][data-item="about"]')
        link.click()                                                        # 소개를 닫으면(뒤로 버튼) 초점은 연 링크로 돌아와요
        page.locator('[data-ui-v2="about"]').wait_for(state="visible")
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=C["app"]["close"]).click()
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
        page.wait_for_function("() => document.activeElement && document.activeElement.matches('[data-ui-v2=\"side-link\"][data-item=\"about\"]')")
        link.click()                                                        # 소개에서 '/' 와 검색어: 칸에 다 들어가고 초점은 칸에 그대로
        page.locator('[data-ui-v2="about"]').wait_for(state="visible")
        page.keyboard.press("/")
        page.wait_for_function("() => document.activeElement && document.activeElement.matches('[data-ui-v2=\"top-search\"] input')")
        page.keyboard.type("005930")
        at(page, "stocks")
        page.locator('[data-ui-v2="about"]').wait_for(state="detached")
        inp = page.locator(TOP_INPUT)
        assert inp.input_value() == "005930", inp.input_value()
        assert focused_in(page, '[data-ui-v2="top-search"]'), page.evaluate("() => document.activeElement && document.activeElement.outerHTML.slice(0, 120)")
        assert page.url.endswith("#stocks"), page.url
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-t="005930"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, S, "소개 → '/' → 005930: 칸에 005930, 초점은 칸에 그대로, #stocks 에 결과 · 소개를 뒤로 닫으면 초점은 연 링크로", about_search)

    def bars():
        page.locator('[data-ui-v2="side-build"]').click()                  # 포트폴리오 만들기: 왼쪽 메뉴에서, 고른 탭은 포트폴리오
        at(page, "portfolio/build")
        tab_selected(page, "portfolio")
        start = page.locator('[data-ui-v2="build-start2"]')                # v19.3c PcStart2: 뱁이 없음, 시작 카드 | 템플릿 두 칸
        start.wait_for(state="visible")
        assert start.locator('img[src^="baepi-"]').count() == 0 and page_box(page)[2] == "2"
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        x, w, cols = page_box(page)                                        # 기준 단계부터는 한 칸 (720px)
        assert cols == "1" and w <= 720, (w, cols)
        bar = page.locator('[data-ui-v2="action-bar"]')                    # 아래 버튼 띠: 왼쪽 메뉴 오른쪽 끝부터, 안의 줄은 본문과 같은 왼쪽 끝
        bb = bar.bounding_box()
        assert abs(bb["x"] - 240) < 0.5 and abs(bb["x"] + bb["width"] - PC_W) < 0.5, bb
        row = bar.locator(":scope > div > div").first.bounding_box()
        assert abs(row["x"] - (x + 32)) < 0.5 and row["width"] <= 720.5, (row, x)
        click_next(page)
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        money = page.locator('[data-ui="money-input"] input')               # 금액 칸에 쓰는 중: '/' 는 검색 칸으로 가지 않아요
        money.click()
        page.keyboard.press("/")
        page.wait_for_timeout(50)
        assert focused_in(page, '[data-ui="money-input"]') and page.locator(TOP_INPUT).input_value() == ""
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        no_hscroll(page, PC_W)
        R.collect(page)
        click_next(page)
        see(page, C["plan"]["stocks"])
        action(page).click()                                               # 샀어요 시트: 왼쪽 메뉴 폭만큼 오른쪽, 열린 동안 '/' 는 시트 안 그대로
        see(page, C["plan"]["sheetTitle"])
        panel = page.locator('[data-ui="bottom-sheet"] [role="dialog"]')
        pb = panel.bounding_box()
        assert abs(pb["x"] + pb["width"] / 2 - (240 + (PC_W - 240) / 2)) < 1, pb
        page.keyboard.press("/")
        page.wait_for_timeout(50)
        assert focused_in(page, '[data-ui="bottom-sheet"]') and not focused_in(page, '[data-ui-v2="top-search"]')
        R.collect(page)
        page.keyboard.press("Escape")
        panel.wait_for(state="detached")
    R.check(page, S, "포트폴리오 만들기(왼쪽 메뉴, 뱁이 176px) · 아래 버튼 띠는 왼쪽 메뉴 오른쪽 · 금액 칸에서 '/' 그대로 · 샀어요 시트는 본문 가운데, 열린 동안 '/' 그대로", bars)

    def side_menu_over_sheet():
        # 2026-11-10 (Jack: PC 에서 새로 만든 포트폴리오가 왼쪽 메뉴 포트폴리오에서 안 보여요): 시트의 어두운 바탕이 왼쪽 메뉴를 덮어
        # 첫 클릭은 시트만 닫고 매수 계획에 남았어요. 이제 바탕은 왼쪽 메뉴 오른쪽부터 → 기록했어요가 열린 채로 포트폴리오 한 번이면 새 포트폴리오.
        before = len(page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1') || '{\"decks\":[]}')")["decks"])
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        page.get_by_role("button", name=C["plan"]["save"]).click()
        page.locator('[data-ui-v2="record-done"]').wait_for(state="visible")
        dim = page.locator('[data-ui="bottom-sheet"]:not([data-inline])').bounding_box()
        assert abs(dim["x"] - 240) < 1 and abs(dim["x"] + dim["width"] - PC_W) < 1, dim      # 어두운 바탕: 왼쪽 메뉴(240px) 오른쪽만
        panel = page.locator('[data-ui="bottom-sheet"] [role="dialog"]').bounding_box()
        assert abs(panel["x"] + panel["width"] / 2 - (240 + (PC_W - 240) / 2)) < 1, panel  # 시트는 그대로 본문 가운데
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")["decks"]
        assert len(stored) == before + 1, (before, len(stored))
        new = stored[-1]
        side = page.locator('[data-ui-v2="side-tabs"] button').filter(has_text=TABS["portfolio"]).first
        side.click(timeout=5000)                                           # 한 번: 시트에 가로막히지 않아요
        at(page, "portfolio")
        assert page.locator('[data-ui="bottom-sheet"]').count() == 0
        card = page.locator(f'[data-deck-id="{new["id"]}"]:has(h3)')        # 방금 만든 포트폴리오가 보여요 (카드만, 이른 종가 줄 말고)
        card.wait_for(state="visible")
        assert new["name"] in card.inner_text(), (new["name"], card.inner_text()[:200])
        R.collect(page)
    R.check(page, S, "기록했어요가 열린 채로 왼쪽 메뉴 포트폴리오 한 번 → 방금 만든 포트폴리오 (어두운 바탕은 왼쪽 메뉴 오른쪽만)", side_menu_over_sheet)

    def fresh_after_record():
        # Jack, 11-10: 기록한 계획은 끝이에요 — 기록한 뒤 포트폴리오 만들기로 다시 가면(뒤로 · 왼쪽 메뉴) 처음 화면이고, 같은 계획의
        # 샀어요는 없어요 (같은 포트폴리오를 두 번 기록하지 않아요)
        page.go_back()                                                     # 왼쪽 메뉴로 떠난 뒤 뒤로: 그 주소(#portfolio/build)로 돌아와도
        at(page, "portfolio/build")
        see(page, C["build"]["s0"]["title"])
        assert page.get_by_role("button", name=C["plan"]["bought"]).count() == 0, "뒤로 돌아오니 기록한 매수 계획이 다시 열렸어요"
        page.locator('[data-ui-v2="side-tabs"] button').filter(has_text=TABS["portfolio"]).first.click()
        at(page, "portfolio")
        page.locator('[data-ui-v2="side-build"]').click()                  # 왼쪽 메뉴의 포트폴리오 만들기도 처음 화면
        at(page, "portfolio/build")
        see(page, C["build"]["s0"]["title"])
        assert page.get_by_role("button", name=C["plan"]["bought"]).count() == 0, "포트폴리오 만들기에 기록한 매수 계획이 다시 열렸어요"
        R.collect(page)
    R.check(page, S, "기록한 뒤 포트폴리오 만들기(뒤로 · 왼쪽 메뉴)는 처음 화면 — 기록한 계획의 샀어요는 다시 없어요", fresh_after_record)

    def side_build_over_done():
        # 기록했어요가 열린 채로 왼쪽 메뉴의 포트폴리오 만들기(같은 주소): 시트는 닫히고 처음 화면, 포트폴리오는 하나만 늘어요 (리뷰 2026-11-10)
        page.locator('[data-deck="income"]').first.click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        page.locator('[data-ui-v2="y2022-methods"]').get_by_text("약 ").first.wait_for(state="visible")
        click_next(page)
        see(page, C["pick"]["title"])
        click_next(page)
        see(page, C["plan"]["stocks"])
        before = len(page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")["decks"])
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        page.get_by_role("button", name=C["plan"]["save"]).click()
        page.locator('[data-ui-v2="record-done"]').wait_for(state="visible")
        page.locator('[data-ui-v2="side-build"]').click(timeout=5000)
        see(page, C["build"]["s0"]["title"])
        assert page.locator('[data-ui="bottom-sheet"]').count() == 0, "기록했어요 시트가 남아 있어요"
        assert page.get_by_role("button", name=C["plan"]["bought"]).count() == 0, "기록한 매수 계획의 샀어요가 남아 있어요"
        after = len(page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")["decks"])
        assert after == before + 1, (before, after)
        R.collect(page)
    R.check(page, S, "기록했어요가 열린 채로 왼쪽 메뉴 포트폴리오 만들기 → 시트 닫히고 처음 화면, 포트폴리오는 하나만 늘어요", side_build_over_done)
    ctx.close()
    srv.shutdown()


def scene_pc_back(R, files):
    """다시 온 방문 PC: 홈 두 칸(판정 띠는 위 전체, 포트폴리오 | 시장 한눈에) · 한 칸 화면 · 1024 · 1280 · 1440px 에서 가로 스크롤 없음."""
    S = f"PC 다시 온 방문 {PC_W}"
    store, _ = missing_store(files)
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, base = R.open(build_site(files), PC_W, init=init, device=pc_device(PC_W))

    def home_two():
        wait_ready(page)
        at(page, "home")
        pc_shell(page, PC_W)
        strip = page.locator('[data-ui-v2="col-main"] [data-ui-v2="home-block"]').first
        glance = page.locator('[data-ui-v2="col-side"] [data-ui-v2="market-glance"]')
        side_by_side(strip, glance)
        assert glance.locator('[data-ui-v2="market-tiles"]').get_attribute("data-cols") == "1"     # 좁은 오른쪽 칸: 네 칸을 세로로
        assert page.locator('[data-ui-v2="home-block"]').count() == 2 and page.locator('[data-ui-v2="col-side"] [data-ui-v2="home-block"]').count() == 0
        hero = page.locator('[data-ui-v2="today-hero"]').bounding_box()      # 판정 띠는 두 칸 위에 전체 폭으로
        main_col = page.locator('[data-ui-v2="col-main"]').bounding_box()
        side_col = page.locator('[data-ui-v2="col-side"]').bounding_box()
        assert abs(hero["x"] - main_col["x"]) < 0.5 and abs(hero["x"] + hero["width"] - (side_col["x"] + side_col["width"])) < 0.5, (hero, main_col, side_col)
        assert hero["y"] + hero["height"] <= main_col["y"] + 0.5
        x, w, cols = page_box(page)
        assert cols == "2" and w <= 1000, (w, cols)
        verdict_icon(page.locator('[data-ui-v2="today-hero"]'), "alert")
        R.collect(page)
        keep["x"] = x
    keep = {}
    R.check(page, S, "홈 두 칸: 판정 띠는 위 전체 · 포트폴리오 띠 | 시장 한눈에(네 칸 세로) · 내용 폭 1000px 이하", home_two)

    def one_col():
        for key in ("portfolio", "stocks"):
            side_tab(page, key)
            page.locator('[data-ui-v2="date-line"]').nth(1).wait_for(state="visible")
            x, w, cols = page_box(page)
            assert cols == "1" and w <= 720 and abs(x - keep["x"]) < 0.5, (key, x, w, cols, keep)   # 모든 화면의 왼쪽 끝이 같아요
            no_hscroll(page, PC_W)
            R.collect(page)
    R.check(page, S, "포트폴리오 · 종목은 한 칸(720px 이하), 왼쪽 끝은 홈과 같아요", one_col)

    def widths():
        for w in (1024, 1280, 1440):
            page.set_viewport_size({"width": w, "height": PC_H})
            for key in TAB_KEYS:
                side_tab(page, key)
                page.locator('[data-ui-v2="side-menu"]').wait_for(state="visible")
                assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0, (w, key)
                no_hscroll(page, w)
            page.locator('[data-ui-v2="side-link"][data-item="about"]').click()
            page.locator('[data-ui-v2="about"]').wait_for(state="visible")
            no_hscroll(page, w)
            page.go_back()
            page.locator('[data-ui-v2="about"]').wait_for(state="detached")
        page.set_viewport_size({"width": PC_W, "height": PC_H})
    R.check(page, S, "1024 · 1280 · 1440px: 네 탭과 소개에 가로 스크롤 없음 · 왼쪽 메뉴 그대로", widths)
    ctx.close()
    srv.shutdown()


def scene_pc_stale(R, files):
    """멈춘 데이터 PC (발행 6일 전, 저장한 포트폴리오 있음): 홈에 판정 없이 멈춤 띠, 왼쪽 칸이 비어 시장 한눈에가 홀로 전체 폭 → 네 칸을 한 줄로."""
    S = f"PC 멈춤 {PC_W}"
    f = clone(files)
    for n in DATA_FILES:
        f[n]["publishedAt"] = now_kst(days_ago=6)
    store, _ = missing_store(files)
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, base = R.open(build_site(f), PC_W, init=init, device=pc_device(PC_W))

    def run():
        wait_ready(page)
        at(page, "home")
        page.locator('[data-ui-v2="today-stale"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="today-hero"], [data-ui-v2="home-block"]').count() == 0
        assert page.locator('[data-ui-v2="side-date"] [data-ui-v2="date-line"]').get_attribute("data-stale") == "1"
        cols = page.locator('[data-ui-v2="cols"]')
        assert cols.get_attribute("data-n") == "1" and page.locator('[data-ui-v2="col-side"]').count() == 0
        glance = page.locator('[data-ui-v2="market-glance"]')
        assert glance.locator('[data-ui-v2="market-tiles"]').get_attribute("data-cols") == "4"
        _, w, _ = page_box(page)
        assert abs(glance.bounding_box()["width"] - w) < 0.5, (glance.bounding_box(), w)
        t = glance.locator('[data-ui-v2="market-tile"]')
        assert t.count() == 4 and len({round(t.nth(i).bounding_box()["y"]) for i in range(4)}) == 1     # 한 줄
        no_hscroll(page, PC_W)
        R.collect(page)
    R.check(page, S, "멈춘 데이터 · 저장한 포트폴리오: 홈은 멈춤 띠, 시장 한눈에는 홀로 전체 폭 · 네 칸 한 줄 · 가로 스크롤 없음", run)
    ctx.close()
    srv.shutdown()


def scene_pc_edge(R, files):
    """1023px 은 휴대폰 화면 그대로 (왼쪽 메뉴 · 위 검색 칸 · '/' 없음, 아래 탭 · ☰ · 종목 탭의 검색 칸). 창을 1024px 로 넓히면 PC 화면,
    다시 좁히면 휴대폰 화면. ☰ 메뉴를 연 채로 넓히면 메뉴가 닫혀요 (PC 에는 ☰ 이 없어요)."""
    S = "PC 경계 1023"
    srv, ctx, page, base = R.open(build_site(files), 1023, device=pc_device(1023))

    def phone():
        wait_ready(page)
        at(page, "home")
        assert page.locator('[data-ui-v2="side-menu"], [data-ui-v2="top-bar"], [data-ui-v2="top-search"]').count() == 0
        bar = page.locator('nav[data-ui="bottom-tab-bar"]')
        bar.wait_for(state="visible")
        assert [b.strip() for b in bar.locator("button").all_inner_texts()] == [TABS[k] for k in TAB_KEYS]
        assert page.locator('[data-ui-v2="app-bar"] h1').first.inner_text() == C["app"]["brand"]
        page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")         # 첫 방문 홈 (v19.5b: 뱁이 없음, 종목 순위)
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        assert page.locator('[data-ui-v2="rank-window"]').get_attribute("data-rows") == "5"   # 휴대폰 크기: 창에 5줄 (PC 는 7줄)
        assert page.locator("main").first.bounding_box()["width"] <= 520
        menu_links(page)
        tab(page, TABS["stocks"])
        at(page, "stocks")
        page.locator('[data-ui-v2="stock-search"] input').wait_for(state="visible")
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.keyboard.press("/")                                           # 휴대폰 화면에는 '/' 단축키가 없어요
        page.wait_for_timeout(50)
        assert not focused_in(page, '[data-ui-v2="stock-search"]')
        no_hscroll(page, 1023)
        R.collect(page)
    R.check(page, S, "1023px: 휴대폰 화면 그대로(아래 탭 · ☰ · 머리말 · 종목 탭의 검색 칸, 왼쪽 메뉴 · 위 검색 칸 · '/' 없음)", phone)

    def resize():
        open_menu(page)
        page.set_viewport_size({"width": 1024, "height": PC_H})            # 넓히면: PC 화면, 열려 있던 ☰ 메뉴는 닫혀요
        page.locator('[data-ui-v2="side-menu"]').wait_for(state="visible")
        page.locator('[data-ui-v2="menu"]').wait_for(state="detached")
        page.wait_for_function("() => !(history.state && history.state.v2menu)")
        at(page, "stocks")
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        pc_shell(page, 1024)
        tab_selected(page, "stocks")
        page.set_viewport_size({"width": 1023, "height": PC_H})            # 좁히면: 휴대폰 화면
        page.locator('[data-ui-v2="side-menu"]').wait_for(state="detached")
        page.locator('nav[data-ui="bottom-tab-bar"]').wait_for(state="visible")
        page.locator('[data-ui-v2="stock-search"] input').wait_for(state="visible")
        no_hscroll(page, 1023)
        R.collect(page)
    R.check(page, S, "1023 → 1024px: PC 화면(☰ 메뉴는 닫힘) → 1023px: 휴대폰 화면", resize)
    ctx.close()
    srv.shutdown()


# ── v19.5b 홈 · 종목 순위 (docs/tasks/v19.5-home-lists-and-icon.md Part A) ──
RANK_SETTINGS = {"deck": None, "points": {"value": 3, "profit": 4, "stable": 3}, "strict": "very", "mix": "k73", "count": 6, "method": "even",
                 "maxPct": 20, "cushion": 0, "amountMan": 1000, "name": "", "pinned": [],
                 "exclude": {"loss": True, "debt": False, "noDiv": False, "holding": False}}
RANK_DECK = {**_deck("drank", "순위 포트폴리오", [(*SAMSUNG, 1.0, [], 1)]), "settings": RANK_SETTINGS}
RANK_REPORT = re.compile(r"^10월 30일 종가 · \d{4}년 사업보고서 기준$")
RANK_NUM = {"cap": r"[\d,]+(\.\d)?(조|억)원", "val": r"[\d,]+(\.\d)?(조|억)원", "surge": re.escape(C["rank"]["surgeX"]).replace(r"\{x\}", r"\d+\.\d"),
            "value": re.escape(C["rank"]["num"]["pbr"]).replace(r"\{x\}", r"\d+\.\d\d"), "profit": re.escape(C["rank"]["num"]["roe"]).replace(r"\{x\}", r"-?[\d,]+\.\d"),
            "stable-kr": re.escape(C["rank"]["num"]["debt"]).replace(r"\{x\}", r"[\d,]+"), "lowVol": re.escape(C["rank"]["num"]["vol"]).replace(r"\{x\}", r"[\d,]+\.\d"),
            "mine": re.escape(C["rank"]["mineX"]).replace(r"\{x\}", r"\d+"), "div": r"[\d,]+\.\d+%"}
for _k, _key, _n in (("stable-us", "debtUs", r"[\d,]+\.\d"), ("trend", "trend", r"[+−]?[\d,]+\.\d%"), ("growth-kr", "g3Kr", r"[+−]?[\d,]+\.\d%"),
                     ("growth-us", "g3Us", r"[+−]?[\d,]+\.\d%")):
    RANK_NUM[_k] = re.escape(C["rank"]["num"][_key]).replace(r"\{x\}", _n)          # Jack, 2026-11-12 승인


def rank_files(files):
    """거래 급증이 있는 날: 시가총액 1조원 이상 한국 회사 하나는 평소의 3.4배, 1,000억원 회사 하나는 9배(3,000억원 미만이라 빠져요)."""
    f = clone(files)
    stocks = f["data.json"]["stocks"]
    base = rank_base(stocks, "kr")
    big = next(s for s in base if s["t"] != "005930" and isnum(s.get("cap")) and s["cap"] >= 1 and isnum(s.get("val20")) and s["val20"] >= 5)
    small = next(s for s in base if isnum(s.get("cap")) and 0.05 <= s["cap"] < 0.3 and isnum(s.get("val20")) and s["val20"] >= 5)
    big["val"], small["val"] = round(big["val20"] * 3.4, 1), round(small["val20"] * 9, 1)
    return f, big["t"], small["t"]


def rank_store(decks):
    return f"(() => {{ try {{ localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps({'v': 1, 'decks': decks}, ensure_ascii=False))}); }} catch (e) {{}} }})();"


def rank_wait(page, attr, value, timeout=WAIT):
    page.wait_for_function("([a, v]) => { const w = document.querySelector('[data-ui-v2=\"rank-window\"]'); return !!w && w.getAttribute(a) === v; }",
                           arg=[attr, value], timeout=timeout)


def rank_ty(page):
    return page.locator('[data-ui-v2="rank-track"]').evaluate("(e) => { const m = getComputedStyle(e).transform; return m === 'none' ? 0 : new DOMMatrix(m).m42; }")


def rank_check_list(page, stocks, coby, mk, chip, crit=None):
    """한 칩의 목록: 고른 표시 · 줄 · 날짜 · 순서(파이썬으로 센 목록) · 숫자 꼴."""
    rank = page.locator('[data-ui-v2="rank"]')
    on = page.locator('[data-ui-v2="rank-chips"] [data-ui-v2="rank-chip"]')
    assert [on.nth(i).get_attribute("data-chip") for i in range(on.count()) if on.nth(i).get_attribute("aria-pressed") == "true"] == [chip]
    assert page.locator('[data-ui-v2="rank-chips"] [data-selected="1"]').get_attribute("data-chip") == chip
    date = rank.locator('[data-ui-v2="rank-date"]').inner_text()
    line = "\n".join(rank.locator('[data-ui-v2="rank-line"] p').all_inner_texts())
    rows = rank_ts(page)
    # 숫자의 이름표(예: '매출 연평균')는 숫자 위 작은 한 줄 (리뷰 3차): 글을 견줄 때는 한 줄로 이어 읽어요
    nums = [" ".join(n.split()) for n in page.locator(RANK_LIST + ' [data-ui-v2="rank-num"]').all_inner_texts()]
    L = C["rank"]["line"]
    # 날짜 줄 (Jack, 2026-11-12): 사업보고서 숫자 목록은 '{year}년 사업보고서 기준' (보이는 줄이 모두 그 한 해일 때만), 가치(최근 분기 자본으로
    # 계산한 PBR)와 기준 점수가 재무제표 카드 중 가치에만 있는 내 기준은 '각 회사의 최근 분기 재무제표 기준', 나머지는 종가 날짜만
    pts = RANK_SETTINGS["points"]
    report = mk == "kr" and (chip == "div" or (chip == "crit" and crit in ("profit", "stable", "growth"))
                             or (chip == "mine" and any(pts.get(c) for c in ("profit", "stable", "growth", "div"))))
    quarter = mk == "kr" and not report and ((chip == "crit" and crit == "value") or (chip == "mine" and bool(pts.get("value"))))
    # 분기 줄은 보이는 줄이 모두 분기 자본으로 계산한 PBR 일 때만 (corp.json bpsIn.p 가 'fy' 가 아님, 리뷰 3차)
    quarter = quarter and all(((coby.get(t) or {}).get("bpsIn") or {}).get("p") not in (None, "fy") for t in rows)
    years = {by_t(stocks)[t].get("fy") if by_t(stocks)[t].get("fy") is not None else (coby.get(t) or {}).get("fy") for t in rows} if report else set()
    if mk == "us":
        assert date == "10월 30일 종가 (미국 시간)", date
    elif report and rows and len(years) == 1 and None not in years:
        assert date == f"10월 30일 종가 · {years.pop()}년 사업보고서 기준", (chip, crit, date)
    elif quarter and rows:
        assert date == "10월 30일 종가 · " + C["rank"]["quarter"], (chip, crit, date)
    else:
        assert date == "10월 30일 종가", (chip, crit, date, years)
    if chip == "crit":                                                                 # 기준별 줄: 성장은 시장마다 한 잣대, 한국 성장 · 수익성은 최소 크기까지
        basis = (C["rank"]["basis"]["g3Kr"] if mk == "kr" else C["rank"]["p"]["basisG3Us"] or C["rank"]["basis"]["g3Us"]) if crit == "growth" \
            else C["build"]["cards"][crit]["basis"]
        if mk == "kr" and crit in ("growth", "profit"):
            basis += " · " + C["rank"]["floor"][crit]
        assert line == fillp(L["crit"], card=C["build"]["cards"][crit]["name"], basis=basis), line
    empty = page.locator('[data-ui-v2="rank-empty"]')
    if empty.count():                                                                  # 빈 목록: 이유 한 줄 (데이터 없음 · 들어갈 종목 없음), 칩은 그대로
        assert not rows and page.locator('[data-ui-v2="rank-window"], [data-ui-v2="rank-foot"]').count() == 0, rows
        text = empty.inner_text()
        assert text in (C["rank"]["emptyData"], C["rank"]["emptyNone"], C["rank"]["surgeNone"]), text
        if chip in ("cap", "val", "surge", "crit"):
            assert rank_expect(stocks, mk, chip, crit, coby) == [], (chip, crit)
        return text
    assert 0 < len(rows) <= 10, (chip, rows)
    if chip in ("cap", "val", "surge", "crit"):
        want = rank_expect(stocks, mk, chip, crit, coby)[:10]
        assert rows == want, (mk, chip, crit, rows, want)
        key = crit if chip == "crit" else chip
        key = f"{key}-{mk}" if key in ("stable", "growth") else key
        assert all(re.fullmatch(RANK_NUM[key], n) for n in nums), (mk, chip, crit, nums)
        if chip != "crit":
            assert line == (L["valUs"] if chip == "val" and mk == "us" else L[chip]), line
    elif chip == "mine":
        assert all(re.fullmatch(RANK_NUM["mine"], n) for n in nums), nums
        pct = [int(re.search(r"\d+", n).group()) for n in nums]
        assert pct == sorted(pct) and line == L["mine"], (pct, line)                  # 점수가 높은 순서 = '상위' 숫자가 작은 순서
        assert all(by_t(stocks)[t] in rank_base(stocks, mk) for t in rows)
        assert not any(isnum(by_t(stocks)[t].get("opm")) and by_t(stocks)[t]["opm"] < 0 for t in rows), "적자 회사 빼기가 안 됐어요"
        if pts.get("value"):                                                       # 가치에 점수: 가치 목록의 보조 장치가 빼는 행은 내 기준에서도 빠져요 (리뷰 3차)
            def guarded(x):
                v, per, roe = x.get("pbr"), x.get("per"), x.get("roe")
                return isnum(v) and (v <= 0 or (mk == "kr" and v < 0.005) or (mk == "us" and isnum(per) and per > 0 and isnum(roe) and roe > 0 and v < per * roe / 100 / 4))
            assert not any(guarded(by_t(stocks)[t]) for t in rows), [t for t in rows if guarded(by_t(stocks)[t])]
    elif chip == "div":
        vs = page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').evaluate_all("(els) => els.map((e) => Number(e.dataset.v))")
        assert vs == sorted(vs, reverse=True) and all(re.fullmatch(RANK_NUM["div"], n) for n in nums), (vs, nums)
        assert line == L["div"] + ("\n" + C["rpt"]["divUs"] if mk == "us" else ""), line       # 미국 줄은 같은 문구의 rpt.divUs
        for t in rows:
            s = by_t(stocks)[t]
            assert s in rank_base(stocks, mk) and isnum(s.get("dyt" if mk == "kr" else "dy")), t
            co = coby.get(t) or {}
            fl = co.get("fl") or {}
            warn = mk == "kr" and (isnum(fl.get("cr")) or isnum(fl.get("icr")) or bool(fl.get("l3")) or bool(fl.get("imp")))
            row = page.locator(RANK_LIST + f' [data-ui-v2="rank-row"][data-t="{t}"]')
            assert row.locator('[data-ui-v2="rank-warn"]').count() == (1 if warn else 0), (t, fl)
            if warn:
                assert row.locator('[data-ui-v2="rank-warn"]').inner_text() == C["rank"]["warn"]
    elif chip == "ind":
        # 홈 (Jack, 2026-11-12): 많이 오른 업종 다섯(높은 순) · 많이 내린 업종 다섯(낮은 순), 보이는 평균(소수 한 자리)이 0 위 · 아래인 업종만
        groups = ind_expect(stocks, mk)
        r10 = lambda a: math.floor(a * 10 + 0.5)
        up = [x for x in groups if r10(x[2]) > 0][:5]
        down = [x for x in reversed(groups) if r10(x[2]) < 0][:5]
        want = up + down
        assert rows == [x[0] for x in want], (rows, [x[0] for x in want])
        labels = page.locator('[data-ui-v2="rank-window"] [data-ui-v2="rank-part"]:not([data-ui-v2="rank-copy"] *) [data-ui-v2="rank-part-label"]').all_inner_texts()
        assert labels == [C["rank"]["indUp"]] * bool(up) + [C["rank"]["indDown"]] * bool(down), labels
        ranks = page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').evaluate_all("(els) => els.map((e) => Number(e.dataset.rank))")
        assert ranks == list(range(1, len(up) + 1)) + list(range(1, len(down) + 1)), ranks   # 부분마다 1부터
        for (ind, n, avg, _), r in zip(want, page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').all()):
            # data-avg 는 평균을 소수 셋째 자리로 반올림한 값 (JS Math.round: .5 는 위로, 파이썬 round 와 다를 수 있어요): 그 반올림 폭 안
            assert int(r.get_attribute("data-n")) == n and abs(float(r.get_attribute("data-avg")) - avg) <= 0.0005 + 1e-9, (ind, n, avg)
            members = [s for s in stocks if in_universe(s, mk) and not (mk == "us" and us_pref(s)) and s.get("ind") == ind and isnum(s.get("d1"))]
            up, down = sum(1 for s in members if s["d1"] > 0), sum(1 for s in members if s["d1"] < 0)
            text = r.locator('[data-ui-v2="rank-count"]').inner_text()
            assert text == (fillp(C["rank"]["up"], n=n, k=up) if avg >= 0 else fillp(C["rank"]["down"], n=n, k=down)), (ind, text)
        assert line == L["ind"], line


def scene_rank(R, files, width):
    """v19.5b 종목 순위 (기준 점수가 있는 포트폴리오가 있는 홈): 한국 · 미국마다 모든 칩의 목록 (파이썬으로 센 순서 · 숫자 꼴 · 줄 · 날짜) ·
    미국은 거래 급증 없음 · 기준별 그림 칩 여섯 · 업종별 등락 → 업종 안 회사 (시가총액 순) → 돌아가기 · 움직임 (32초 · 7% 멈춤 · 두 벌, 둘째는
    aria-hidden) → 누르는 동안(손가락) · 마우스를 올린 동안 · 초점 · 화면 밖 · 탭 숨김에 멈춤 · 마지막 칩을 기억 · 전체 보기 → 종목 탭(같은 칩, 멈춘
    30개, 제목에 초점) · 뱁이 없음 · 가로 스크롤 없음."""
    S = f"종목 순위 {width}"
    f, surge_big, surge_small = rank_files(files)
    for c in f["corp.json"]["companies"]:                                         # 분기 자본 PBR (bpsIn.p 'ttm'): 가치의 분기 줄이 나와요
        if c["t"][:1].isdigit() and not c.get("bpsIn"):
            c["bpsIn"] = {"p": "ttm"}
    stocks = f["data.json"]["stocks"]
    coby = {c["t"]: c for c in f["corp.json"]["companies"]}
    srv, ctx, page, base = R.open(build_site(f), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def lists():
        wait_ready(page)
        rank = page.locator('[data-ui-v2="rank"]')
        rank.wait_for(state="visible")
        assert rank.locator("h3").inner_text() == C["rank"]["title"] and (rank.get_attribute("data-mk"), rank.get_attribute("data-chip")) == ("kr", "cap")
        glance = page.locator('[data-ui-v2="market-glance"]')                # 휴대폰: 시장 한눈에 바로 밑
        assert glance.bounding_box()["y"] + glance.bounding_box()["height"] <= rank.bounding_box()["y"]
        for mk in ("kr", "us"):
            rank_market(page, mk)
            chips = page.locator('[data-ui-v2="rank-chips"] [data-ui-v2="rank-chip"]').evaluate_all("(els) => els.map((e) => e.dataset.chip)")
            # 목록이 비어도 칩은 그대로 (Jack, 2026-11-12): 확인한 배당(dyt)이 없는 이 파일의 한국 배당수익률은 '필요한 데이터가 아직 없어 …'
            want = [c for c in ("cap", "val", "surge", "crit", "mine", "div", "ind") if not (c == "surge" and mk == "us")]
            assert chips == want, (mk, chips)
            hs = page.locator('[data-ui-v2="rank-chip"], [data-ui-v2="rank-market"] button').evaluate_all("(els) => els.map((e) => e.getBoundingClientRect().height)")
            assert hs and min(hs) >= 44 - 0.5, hs                                   # 칩과 한국/미국은 누르는 곳 44px 이상 (Jack, 2026-11-12)
            assert page.locator('[data-ui-v2="rank-chips"] [data-ui-v2="rank-chip"]').all_inner_texts() == [C["rank"]["chips"][c] for c in want]
            for chip in want:
                for crit in (list(RANK_CRIT) if chip == "crit" else [None]):
                    rank_chip(page, chip, crit)
                    if chip == "crit":
                        crits = page.locator('[data-ui-v2="rank-crit"] [data-ui-v2="rank-chip"]')
                        assert crits.evaluate_all("(els) => els.map((e) => e.dataset.chip)") == list(RANK_CRIT)
                        assert crits.locator("img").evaluate_all("(els) => els.map((e) => e.getAttribute('src'))") == [f"pictures/{CARD_TABLE_PICS[c]}.webp" for c in RANK_CRIT]
                        row, on = page.locator('[data-ui-v2="rank-crit"]').bounding_box(), page.locator(f'[data-ui-v2="rank-crit"] [data-chip="{crit}"]').bounding_box()
                        assert on["x"] >= row["x"] - 0.5 and on["x"] + on["width"] <= row["x"] + row["width"] + 0.5, (crit, row, on)   # 고른 기준이 줄 안에
                    got = rank_check_list(page, stocks, coby, mk, chip, crit)
                    if width == 320:                                               # 회사 이름 칸이 숫자에 밀리지 않아요 (리뷰 3차: '라…' 한 글자)
                        ws = page.locator(RANK_LIST + ' [data-ui-v2="rank-name"]').evaluate_all("(els) => els.map((e) => e.getBoundingClientRect().width)")
                        assert not ws or min(ws) >= NAME_MIN_320, (mk, chip, crit, ws)
                    if chip == "div" and mk == "kr":
                        assert got == C["rank"]["emptyData"], got                       # 이 파일에는 분할 확인(divCheck)이 없어요
                    if chip == "surge":
                        assert surge_big in rank_ts(page) and surge_small not in rank_ts(page), rank_ts(page)
                    R.collect(page)
            no_hscroll(page, width)
        rank_market(page, "kr")
        rank_chip(page, "cap")
        assert page.locator(MASCOT_IN_MAIN).count() == 0, "종목 순위가 있는 홈에 뱁이"
    R.check(page, S, "한국 · 미국 모든 칩: 순서(시장마다 · 우선주 · ETF · 5억 미만 · 빈 칸 빼고 · 같은 값은 시가총액 순) · 숫자 꼴 · 줄 · 날짜 · 미국은 거래 급증 없음", lists)

    def group():
        page.locator('[data-ui-v2="rank-back"]').click() if page.locator('[data-ui-v2="rank-back"]').count() else None
        rank_market(page, "kr")
        rank_chip(page, "ind")
        first = page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').first
        ind = first.get_attribute("data-ind")
        first.locator("button").click()
        head = page.locator('[data-ui-v2="rank-group"]')
        head.wait_for(state="visible")
        members = sorted([s for s in stocks if in_universe(s, "kr") and s.get("ind") == ind and isnum(s.get("d1"))],
                         key=lambda s: (-(s["cap"] if isnum(s.get("cap")) else -math.inf), s["t"]))
        assert page.locator('[data-ui-v2="rank"]').get_attribute("data-group") == ind and rank_ts(page) == [s["t"] for s in members][:10], rank_ts(page)
        nums = page.locator(RANK_LIST + ' [data-ui-v2="rank-num"]').all_inner_texts()
        assert all(re.fullmatch(RANK_NUM["cap"], n) for n in nums[: sum(1 for s in members[:10] if isnum(s.get("cap")))]), nums
        back = page.locator('[data-ui-v2="rank-back"]')
        assert back.get_attribute("aria-label") is None and back.inner_text() == C["rank"]["groupBack"]       # '업종 목록으로' (Jack, 2026-11-12)
        assert page.locator('[data-ui-v2="rank-line"]').inner_text() == C["rank"]["groupLine"]
        assert page.evaluate("() => document.activeElement && document.activeElement.dataset.uiV2") == "rank-back"     # 연 목록의 돌아가기에 초점
        R.collect(page)
        back.click()
        head.wait_for(state="detached")
        assert rank_ts(page)[0] == ind
    R.check(page, S, "업종별 등락: 업종을 누르면 그 업종 회사가 시가총액 순으로 같은 창에 · 돌아가기 (이름: co.back, 초점이 그 버튼에)", group)

    def motion():
        page.locator('[data-ui-v2="rank-back"]').click() if page.locator('[data-ui-v2="rank-back"]').count() else None
        rank_market(page, "kr")
        rank_chip(page, "cap")
        page.mouse.move(2, 2)                                                  # 앞 장면의 마우스가 창 위에 남지 않게
        page.evaluate("() => window.scrollTo(0, 0)")
        win = page.locator('[data-ui-v2="rank-window"]')
        if win.bounding_box()["y"] > page.viewport_size["height"]:
            rank_wait(page, "data-pause", "offscreen")                         # 화면 밖: 멈춤 (IntersectionObserver)
        win.scroll_into_view_if_needed()
        rank_wait(page, "data-moving", "1")
        assert win.get_attribute("aria-label") == C["rank"]["listAria"] and win.get_attribute("tabindex") == "0", (win.get_attribute("aria-label"), win.get_attribute("tabindex"))
        assert win.get_attribute("data-rows") == "5" and abs(win.bounding_box()["height"] - 5 * 58) < 1, (win.get_attribute("data-rows"), win.bounding_box())
        track = page.locator('[data-ui-v2="rank-track"]')
        anim = track.evaluate("(e) => { const s = getComputedStyle(e); return [s.animationName, s.animationDuration, s.animationTimingFunction, s.animationIterationCount, s.animationPlayState]; }")
        assert anim == ["v2-rank-roll", "32s", "linear", "infinite", "running"], anim
        frames = page.evaluate("""() => { for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch (e) { continue; }
            for (const r of rules) if (r.type === CSSRule.KEYFRAMES_RULE && r.name === 'v2-rank-roll') return [...r.cssRules].map((k) => [k.keyText, k.style.transform]); } return null; }""")
        assert frames == [["0%, 7%", "translateY(0px)"], ["100%", "translateY(-50%)"]], frames
        copy = page.locator('[data-ui-v2="rank-copy"]')                       # 두 벌: 둘째는 aria-hidden, 그 버튼은 Tab 으로 가지 않아요
        assert copy.get_attribute("aria-hidden") == "true" and copy.locator("button").count() == 10, ("copy", copy.get_attribute("aria-hidden"), copy.locator("button").count())
        assert copy.locator("button").evaluate_all("(els) => els.every((b) => b.tabIndex === -1)"), "copy buttons reachable by Tab"
        lst = page.locator(RANK_LIST)
        assert lst.count() == 1 and lst.locator('[role="listitem"]').count() == 10 and lst.locator("button").evaluate_all("(els) => els.every((b) => b.tabIndex === 0)"), ("list", lst.count())
        assert page.locator('[data-ui-v2="rank-hint"]').inner_text() == C["rank"]["hint"] and page.locator('[data-ui-v2="rank-all"]').inner_text() == C["rank"]["all"], "hint / all"
        y0 = rank_ty(page)
        page.wait_for_timeout(3200)                                            # 7% (약 2.2초) 멈춘 뒤 위로
        y1 = rank_ty(page)
        assert y1 < y0 - 1, (y0, y1)
        win.hover()                                                            # 마우스를 올린 동안
        rank_wait(page, "data-pause", "hover")
        assert track.evaluate("(e) => getComputedStyle(e).animationPlayState") == "paused", (track.evaluate("(e) => getComputedStyle(e).animationPlayState"), win.get_attribute("data-kb"))
        # 멈춤은 다음 프레임에 걸려요 (Web Animations: 멈추는 동안 pending 이고 그 사이 현재 시각이 한 프레임 더 흘러요). 멈춤이 걸린 뒤에 위치를 봐요
        page.wait_for_function("() => { const t = document.querySelector('[data-ui-v2=\"rank-track\"]'); const a = t && t.getAnimations()[0];"
                               " return !!a && a.playState === 'paused' && !a.pending; }")
        a = rank_ty(page); page.wait_for_timeout(500)
        b = rank_ty(page)
        assert b == a, ("moved while hovered", a, b, win.get_attribute("data-pause"))
        page.mouse.move(2, 2)
        rank_wait(page, "data-moving", "1")
        win.focus()                                                            # 초점
        rank_wait(page, "data-pause", "focus")
        page.evaluate("() => document.activeElement.blur()")
        rank_wait(page, "data-moving", "1")
        for end in ("new PointerEvent('pointerup', { pointerType: 'touch' })", "new PointerEvent('pointercancel', { pointerType: 'touch' })",
                    "new Event('touchend')", "new Event('touchcancel')"):          # 손가락이 닿은 동안 멈추고, 어떻게 끝나든 다시 움직여요
            win.dispatch_event("pointerdown", {"pointerType": "touch", "isPrimary": True, "bubbles": True})
            rank_wait(page, "data-pause", "touch")
            page.evaluate("(e) => window.dispatchEvent(eval(e))", end)
            rank_wait(page, "data-moving", "1")
        page.evaluate("() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' }); document.dispatchEvent(new Event('visibilitychange')); }")
        rank_wait(page, "data-pause", "hidden")                                # 탭이 숨으면
        page.evaluate("() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' }); document.dispatchEvent(new Event('visibilitychange')); }")
        rank_wait(page, "data-moving", "1")
        R.collect(page)
    R.check(page, S, "움직임: 32초 · 0–7% 멈춤 · 두 벌(둘째 aria-hidden, Tab 안 감) · 손가락 · 마우스 · 초점 · 화면 밖 · 탭 숨김에 멈추고 다시 움직여요", motion)

    def remember_and_all():
        rank_market(page, "kr")
        rank_chip(page, "ind")
        page.reload()
        wait_ready(page)
        rank = page.locator('[data-ui-v2="rank"]')
        rank.wait_for(state="visible")
        assert rank.get_attribute("data-chip") == "ind", rank.get_attribute("data-chip")    # 마지막 칩을 이 기기에 기억해요
        row, chip = page.locator('[data-ui-v2="rank-chips"]').bounding_box(), page.locator('[data-ui-v2="rank-chips"] [data-chip="ind"]').bounding_box()
        assert chip["x"] >= row["x"] - 0.5 and chip["x"] + chip["width"] <= row["x"] + row["width"] + 0.5, (row, chip)   # 고른 칩이 줄 안에 보여요
        rank_chip(page, "val")
        page.locator('[data-ui-v2="rank-all"]').click()                        # 전체 보기 → 종목 탭, 같은 칩, 멈춘 30개
        at(page, "stocks")
        full = page.locator('[data-ui-v2="rank"][data-full="1"]')
        full.wait_for(state="visible")
        assert (full.get_attribute("data-mk"), full.get_attribute("data-chip")) == ("kr", "val")
        assert rank_ts(page) == rank_expect(stocks, "kr", "val")[:30]
        assert page.locator('[data-ui-v2="rank-window"]').get_attribute("data-still") == "full" and page.locator('[data-ui-v2="rank-copy"], [data-ui-v2="rank-all"], [data-ui-v2="rank-hint"]').count() == 0
        page.wait_for_function("() => document.activeElement && document.activeElement.tagName === 'H3' && !!document.activeElement.closest('[data-ui-v2=\"rank\"]')")
        top = full.bounding_box()["y"]
        assert 0 <= top < page.viewport_size["height"] / 2, top                 # 종목 순위가 화면에 (맨 위가 아니라)
        no_hscroll(page, width)
        R.collect(page)
        page.go_back()
        at(page, "home")
        assert page.locator('[data-ui-v2="rank"]').get_attribute("data-chip") == "val"
    R.check(page, S, "마지막 칩을 기억 (새로 고침해도) · 고른 칩이 줄 안에 · 전체 보기 → 종목 탭(같은 칩 · 멈춘 30개 · 제목에 초점 · 화면 안) → 뒤로 → 홈", remember_and_all)
    ctx.close()
    srv.shutdown()

    # 확인한 배당(divCheck · dyt)이 있는 파일: 한국 배당수익률 (dyt 큰 순) · 재무 경고 칩 · '{year}년 사업보고서 기준'
    fv = v191b_files(files)
    top = max((s for s in rank_base(fv["data.json"]["stocks"], "kr") if isnum(s.get("dyt"))), key=lambda s: s["dyt"])
    for c in fv["corp.json"]["companies"]:
        if c["t"] == top["t"]:
            c["fl"] = {"cr": 57.0}
    srv, ctx, page, base = R.open(build_site(fv), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def kr_div():
        wait_ready(page)
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        rank_chip(page, "div")
        rank_check_list(page, fv["data.json"]["stocks"], {c["t"]: c for c in fv["corp.json"]["companies"]}, "kr", "div")
        assert rank_ts(page)[0] == top["t"] and page.locator(RANK_LIST + ' [data-ui-v2="rank-warn"]').count() >= 1
        R.collect(page)
    R.check(page, S, "확인한 배당이 있는 파일: 한국 배당수익률(dyt 큰 순, 확인 못 한 종목 빼고) · 재무 경고 칩 · 사업보고서 연도", kr_div)
    ctx.close()
    srv.shutdown()


def scene_rank_still(R, files, width):
    """움직이지 않는 종목 순위: 움직임 줄이기(prefers-reduced-motion) · 멈춘 데이터(날짜 줄은 진짜 날짜) → 5줄 · 두 벌 없음 · 안내 없음 · 전체 보기
    있음. 거래 급증이 없는 날의 승인 문구. 기준 점수가 없는 포트폴리오면 내 기준 칩 없음. 불러오기 실패면 그 문구, 빈 칸 아님."""
    S = f"종목 순위 멈춤 {width}"
    reduced = {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2, "reduced_motion": "reduce"}
    srv, ctx, page, base = R.open(build_site(files), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home", device=reduced)

    def still_reduced():
        wait_ready(page)
        win = page.locator('[data-ui-v2="rank-window"]')
        win.wait_for(state="visible")
        assert win.get_attribute("data-still") == "reduced" and win.get_attribute("data-moving") == "0"
        assert page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').count() == 5 and page.locator('[data-ui-v2="rank-row"]').count() == 5
        assert page.locator('[data-ui-v2="rank-copy"], [data-ui-v2="rank-track"], [data-ui-v2="rank-hint"]').count() == 0
        assert page.locator('[data-ui-v2="rank-all"]').inner_text() == C["rank"]["all"]
        assert page.evaluate("() => document.getAnimations().filter((a) => a.animationName === 'v2-rank-roll').length") == 0
        rank_chip(page, "surge")                                               # 시험 데이터에는 거래 급증이 없어요: 승인 문구 (빈 칸 아님)
        empty = page.locator('[data-ui-v2="rank-empty"]')
        assert empty.inner_text() == C["rank"]["surgeNone"] and page.locator('[data-ui-v2="rank-window"], [data-ui-v2="rank-all"]').count() == 0
        R.collect(page)
    R.check(page, S, "움직임 줄이기: 멈춘 5줄 · 두 벌 · 안내 없음 · 전체 보기 있음 · 거래 급증이 없는 날 승인 문구", still_reduced)
    ctx.close()
    srv.shutdown()

    f = clone(files)
    for n in DATA_FILES:
        f[n]["publishedAt"] = now_kst(days_ago=6)
    srv, ctx, page, base = R.open(build_site(f), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def still_stale():
        wait_ready(page)
        win = page.locator('[data-ui-v2="rank-window"]')
        win.wait_for(state="visible")
        assert page.locator('[data-ui-v2="date-line"]').first.get_attribute("data-stale") == "1"
        assert win.get_attribute("data-still") == "stale" and page.locator('[data-ui-v2="rank-row"]').count() == 5
        assert page.locator('[data-ui-v2="rank-date"]').inner_text() == "10월 30일 종가"          # 진짜 날짜 그대로
        assert page.locator('[data-ui-v2="rank-copy"], [data-ui-v2="rank-hint"]').count() == 0
        R.collect(page)
    R.check(page, S, "멈춘 데이터: 목록이 움직이지 않아요 (5줄) · 날짜 줄은 그 데이터의 날짜", still_stale)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(files), width, init=rank_store(DAILY_DECKS["decks"][:1]), path="/app.html?dev=1#home")

    def no_points():
        wait_ready(page)
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rank-chips"] [data-chip="mine"]').count() == 0, "기준 점수가 없는 포트폴리오인데 내 기준 칩"
        R.collect(page)
    R.check(page, S, "기준 점수가 없는 포트폴리오만 있으면 내 기준 칩이 없어요", no_points)
    ctx.close()
    srv.shutdown()

    for label, init in (("저장한 포트폴리오", rank_store([RANK_DECK])), ("첫 방문", None)):
        srv, ctx, page, base = R.open(build_site(files, drop=("data.json",)), width, init=init, path="/app.html?dev=1#home")

        def failed():
            see(page, LOAD_FAIL)
            assert page.locator('[data-ui-v2="rank"], [data-ui-v2="rank-window"]').count() == 0
            R.collect(page)
        R.check(page, S, f"불러오기 실패 ({label}): 불러오기 실패 문구, 종목 순위 칸 없음", failed)
        ctx.close()
        srv.shutdown()


def scene_rank_r1(R, files, width):
    """v19.5b 리뷰 1차: 오래 누른 뒤 떼면 회사가 열리지 않아요(짧게 누르면 열려요) · 키보드로 간 줄은 창 안에 보이고 테두리가 있어요, 나오면 창이
    맨 위로 · 오늘 거래대금이 없는 파일은 거래 급증 칩 없음(빈 줄 문구 아님) · 목록이 하나도 없는 시장은 빈 칸 대신 불러오기 실패 문구 ·
    '0.0%' 는 빨강 · 파랑이 아니에요 · 미국 업종 안 회사는 같은 회사 한 줄(줄의 n 은 그대로) · 업종 안에서는 전체 보기 없음."""
    S = f"종목 순위 리뷰 {width}"
    f = clone(files)
    by = by_t(f["data.json"]["stocks"])
    by["005930"]["d1"], by["000660"]["d1"] = 0.04, -0.04                       # 둘 다 '0.0%'
    srv, ctx, page, base = R.open(build_site(f), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def hold_and_tap():
        wait_ready(page)
        win = page.locator('[data-ui-v2="rank-window"]')
        for ms in (450, 700):                                                   # 마우스는 천천히 눌러도 그 회사로 (마우스를 올리면 이미 멈춰 있어요)
            win.scroll_into_view_if_needed()
            rank_wait(page, "data-moving", "1")
            box = win.bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2     # 창 가운데의 줄
            page.mouse.move(x, y)
            rank_wait(page, "data-pause", "hover")
            t = page.evaluate("([x, y]) => { const r = document.elementFromPoint(x, y).closest('[data-ui-v2=\"rank-row\"]'); return r && r.dataset.t; }", [x, y])
            assert t, "창 가운데에 종목 줄이 없어요"
            page.mouse.down()
            page.wait_for_timeout(ms)
            page.mouse.up()
            at(page, f"stocks/{t}")
            page.go_back()
            at(page, "home")
            page.mouse.move(2, 2)
        win.scroll_into_view_if_needed()
        rank_wait(page, "data-moving", "1")
        row = page.locator(RANK_LIST + ' [data-ui-v2="rank-row"]').first
        btn = row.locator("button")                                             # 손가락: 500ms 누른 뒤 뗀 click 은 열리지 않아요
        btn.dispatch_event("pointerdown", {"pointerType": "touch", "isPrimary": True, "bubbles": True})
        rank_wait(page, "data-pause", "touch")
        page.wait_for_timeout(500)
        btn.dispatch_event("pointerup", {"pointerType": "touch", "isPrimary": True, "bubbles": True})
        btn.dispatch_event("click")
        page.wait_for_timeout(300)
        assert route(page) == "home", route(page)
        t = row.get_attribute("data-t")
        btn.click()                                                             # 짧게 누르면 그 회사로
        at(page, f"stocks/{t}")
        page.go_back()
        at(page, "home")
        R.collect(page)
    R.check(page, S, "마우스는 천천히 눌러도(450 · 700ms) 그 회사가 열려요 · 손가락으로 500ms 누른 뒤 뗀 click 은 열리지 않아요 · 짧게 누르면 열려요", hold_and_tap)

    def keyboard():
        page.mouse.move(2, 2)
        win = page.locator('[data-ui-v2="rank-window"]')
        win.scroll_into_view_if_needed()
        win.focus()
        for _ in range(7):                                                       # 창 → 1 … 7번째 줄 (Tab)
            page.keyboard.press("Tab")
        active = page.evaluate("() => { const r = document.activeElement.closest('[data-ui-v2=\"rank-row\"]'); return r ? r.dataset.rank : null; }")
        assert active == "7", active
        rank_wait(page, "data-kb", "1")
        assert win.get_attribute("data-pause") == "focus" and win.get_attribute("data-moving") == "0", win.get_attribute("data-pause")   # 키보드 초점은 그대로 멈춰요
        page.wait_for_timeout(300)
        assert page.locator('[data-ui-v2="rank-track"]').evaluate("(e) => getComputedStyle(e).animationName") == "none"
        w, b = win.bounding_box(), page.evaluate("() => { const r = document.activeElement.getBoundingClientRect(); return { y: r.y, h: r.height }; }")
        assert w["y"] - 0.5 <= b["y"] and b["y"] + b["h"] <= w["y"] + w["height"] + 0.5, (w, b)      # 고른 줄이 창 안에 보여요
        ring = page.evaluate("() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, s.outlineWidth, s.outlineColor]; }")
        assert ring == ["solid", "2px", NAVY_RGB], ring
        assert win.evaluate("(e) => e.scrollTop") > 0
        page.evaluate("() => document.activeElement.blur()")
        page.wait_for_function("() => { const w = document.querySelector('[data-ui-v2=\"rank-window\"]'); return w && w.scrollTop === 0 && !w.dataset.kb; }")
        rank_wait(page, "data-moving", "1")                                      # 다시 #1 부터 움직여요
        R.collect(page)
    R.check(page, S, "키보드: 7번째 줄로 가면 줄이 멈춰 제자리 · 그 줄이 창 안에 보이고 남색 테두리 · 나오면 창이 맨 위로, 다시 움직여요", keyboard)

    def zero_and_group():
        rank_chip(page, "cap")
        for t in ("005930", "000660"):                                          # '0.0%' 는 회색 (빨강 · 파랑 아님)
            ch = page.locator(RANK_LIST + f' [data-ui-v2="rank-row"][data-t="{t}"] [data-ui-v2="rank-change"]')
            assert ch.inner_text() == "0.0%" and ch.evaluate("(e) => getComputedStyle(e).color") == "rgb(91, 101, 118)", (t, ch.inner_text())
        rank_market(page, "us")
        rank_chip(page, "ind")
        assert page.locator(RANK_LIST + ' [data-ui-v2="rank-row"][data-ind="platform"]').count() == 0   # 평균 '0.0%' 인 업종은 홈의 두 부분 어디에도 없어요
        page.locator(RANK_LIST + ' [data-ui-v2="rank-row"] button').first.click()
        page.locator('[data-ui-v2="rank-group"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rank-all"]').count() == 0              # 업종 안에서는 전체 보기 없음 (돌아가기가 업종 목록으로)
        page.locator('[data-ui-v2="rank-back"]').click()
        page.locator('[data-ui-v2="rank-all"]').click()                         # 전체 보기: 종목 탭에 모든 업종 (높은 순)
        full = page.locator('[data-ui-v2="rank"][data-full="1"]')
        full.wait_for(state="visible")
        row = full.locator('[data-ui-v2="rank-row"][data-ind="platform"]')
        n, k, avg = int(row.get_attribute("data-n")), int(row.get_attribute("data-k")), float(row.get_attribute("data-avg"))
        assert -0.05 < avg < 0, avg                                             # 시험 데이터: 평균 -0.03 → '0.0%'
        num = row.locator('[data-ui-v2="rank-num"]')                            # 업종 줄의 '0.0%' 도 회색
        assert num.inner_text() == "0.0%" and num.evaluate("(e) => getComputedStyle(e).color") == "rgb(91, 101, 118)", num.inner_text()
        row.locator("button").click()
        full.locator('[data-ui-v2="rank-group"]').wait_for(state="visible")
        head = full.locator('[data-ui-v2="rank-group-avg"]')                    # 연 업종 머리의 '0.0%' 도 회색 (빨강 · 파랑 아님)
        assert head.inner_text() == "0.0%" and head.evaluate("(e) => getComputedStyle(e).color") == "rgb(91, 101, 118)", head.inner_text()
        ts = full.locator('[data-ui-v2="rank-window"] [role="list"] [data-ui-v2="rank-row"]').evaluate_all("(els) => els.map((e) => e.dataset.t)")
        assert "GOOGL" in ts and "GOOG" not in ts and n == 15, (ts, n)           # 같은 회사는 한 줄 · n 은 왜 움직였나 그대로
        assert fillp(C["rank"]["up" if avg >= 0 else "down"], n=n, k=k) in full.locator('[data-ui-v2="rank-group"]').inner_text()
        R.collect(page)
        full.locator('[data-ui-v2="rank-back"]').click()
        page.go_back()
        at(page, "home")
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        rank_market(page, "kr")
    R.check(page, S, "'0.0%' 는 회색(줄 · 연 업종 머리, 전체 보기의 업종) · 미국 업종 안 회사는 회사마다 한 줄(GOOGL 만, n 15 그대로) · 업종 안에서는 전체 보기 없음", zero_and_group)

    def chip_after_market():
        page.set_viewport_size({"width": 360, "height": 780})                  # 칩 줄이 옆으로 밀리는 폭
        try:
            rank_market(page, "kr")
            rank_chip(page, "ind")                                              # 줄 끝으로 밀었다가
            rank_chip(page, "surge")
            rank_market(page, "us")                                             # 미국에는 거래 급증이 없어서 첫 칩(시가총액)으로
            assert page.locator('[data-ui-v2="rank"]').get_attribute("data-chip") == "cap"
            page.wait_for_function("""() => { const row = document.querySelector('[data-ui-v2="rank-chips"]');
                const c = row && row.querySelector('[data-chip="cap"]'); if (!c) return false;
                const r = row.getBoundingClientRect(), b = c.getBoundingClientRect(); return b.left >= r.left - 0.5 && b.right <= r.right + 0.5; }""",
                                   timeout=3000)                                # 고른 칩(첫 칩이어도)이 칩 줄의 보이는 칸 안에
        finally:
            page.set_viewport_size({"width": width, "height": 780})
        rank_market(page, "kr")
        rank_chip(page, "cap")
    R.check(page, S, "시장을 바꿔 고른 칩이 첫 칩(시가총액)으로 돌아가도 칩 줄 안에 보여요 (360px: 업종별 등락 → 거래 급증 → 미국)", chip_after_market)
    ctx.close()
    srv.shutdown()

    # 진짜 손가락(터치 화면, CDP 터치): 브라우저가 누른 줄에 초점을 줘요. 오래 누른 뒤 떼면 열리지 않고, 그 초점도 남지 않아 1초 안에 다시
    # 움직여요 · 짧게 누르면 그 회사로
    touch = {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
    srv, ctx, page, base = R.open(build_site(f), width, device=touch, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def finger():
        wait_ready(page)
        cdp = ctx.new_cdp_session(page)
        win = page.locator('[data-ui-v2="rank-window"]')
        win.scroll_into_view_if_needed()
        rank_wait(page, "data-moving", "1")
        box = win.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        under = "([x, y]) => { const r = document.elementFromPoint(x, y).closest('[data-ui-v2=\"rank-row\"]'); return r && r.dataset.t; }"
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        rank_wait(page, "data-pause", "touch")
        page.wait_for_timeout(700)                                              # 오래 눌러 읽고
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        rank_wait(page, "data-moving", "1", timeout=1000)                      # 떼면 1초 안에 다시 움직여요 (누른 줄의 초점 때문에 멈춰 있지 않아요)
        inside = page.evaluate("() => { const w = document.querySelector('[data-ui-v2=\"rank-window\"]'); return !!w && w.contains(document.activeElement); }")
        assert not inside, "오래 누른 줄에 초점이 남았어요"
        page.wait_for_timeout(300)
        assert route(page) == "home", route(page)                               # 그 줄의 회사는 열리지 않아요
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        rank_wait(page, "data-pause", "touch")
        t = page.evaluate(under, [x, y])
        assert t, "창 가운데에 종목 줄이 없어요"
        page.wait_for_timeout(60)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        at(page, f"stocks/{t}")                                                 # 짧게 누르면 그 회사로
        R.collect(page)
    R.check(page, S, "손가락(터치 화면): 오래(700ms) 누른 뒤 떼면 회사가 열리지 않고 1초 안에 다시 움직여요(줄에 초점이 남지 않아요) · 짧게 누르면 열려요", finger)
    ctx.close()
    srv.shutdown()

    # 오늘 거래대금(val)이 없는 파일 · 한국은 모든 종목이 오늘 +0.01% (업종 평균이 모두 '0.0%') · 미국은 모두 5억 미만이고 오늘 변화도 없음
    f2 = clone(files)
    for x in f2["data.json"]["stocks"]:
        if x["cls"] == "kr":
            x.pop("val", None)
            if isnum(x.get("d1")):
                x["d1"] = 0.01
        elif x["cls"] == "us":
            x["val"], x["d1"] = 1.0, None
    srv, ctx, page, base = R.open(build_site(f2), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def no_figures():
        wait_ready(page)
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        chips = page.locator('[data-ui-v2="rank-chips"] [data-ui-v2="rank-chip"]').evaluate_all("(els) => els.map((e) => e.dataset.chip)")
        assert "surge" in chips and "val" in chips, chips                        # 칩은 그대로, 목록 대신 '필요한 데이터가 아직 없어 …' (Jack, 2026-11-12)
        for c in ("val", "surge"):
            rank_chip(page, c)
            assert page.locator('[data-ui-v2="rank-empty"]').inner_text() == C["rank"]["emptyData"], c
            assert page.locator('[data-ui-v2="rank-window"], [data-ui-v2="rank-foot"]').count() == 0
        assert C["rank"]["surgeNone"] not in page.locator("body").inner_text()   # 숫자가 없는 날은 '오늘은 … 없어요' 가 아니에요
        rank_chip(page, "ind")                                                   # 업종이 모두 '0.0%': 두 부분이 다 비어 '지금은 … 없어요' (리뷰 3차)
        assert page.locator('[data-ui-v2="rank-empty"]').inner_text() == C["rank"]["emptyNone"]
        assert page.locator('[data-ui-v2="rank-fail"], [data-ui-v2="rank-window"]').count() == 0
        rank_chip(page, "cap")
        rank_market(page, "us")                                                  # 종목은 있는데 모두 5억 미만: 칩은 그대로, '지금은 … 없어요' (리뷰 3차)
        chips = page.locator('[data-ui-v2="rank-chips"] [data-ui-v2="rank-chip"]').evaluate_all("(els) => els.map((e) => e.dataset.chip)")
        assert chips == ["cap", "val", "crit", "mine", "div", "ind"], chips
        assert page.locator('[data-ui-v2="rank-empty"]').inner_text() == C["rank"]["emptyNone"] and page.locator('[data-ui-v2="rank-fail"]').count() == 0
        rank_chip(page, "ind")                                                   # 미국은 오늘 변화가 없어요: 데이터 없음
        assert page.locator('[data-ui-v2="rank-empty"]').inner_text() == C["rank"]["emptyData"]
        R.collect(page)
        rank_chip(page, "cap")
        rank_market(page, "kr")
    R.check(page, S, "오늘 거래대금이 없는 파일: 거래대금 · 거래 급증은 '필요한 데이터가 아직 없어 …' · 업종이 모두 0.0% 면 '지금은 … 없어요' · 5억 미만뿐인 시장(미국)도 칩은 그대로", no_figures)
    ctx.close()
    srv.shutdown()

    f3 = clone(files)                     # 미국 종목이 하나도 없는 파일: 미국은 칩 없이 불러오기 실패 문구 (그 시장에 데이터가 아예 없을 때만)
    f3["data.json"]["stocks"] = [x for x in f3["data.json"]["stocks"] if x["cls"] != "us"]
    srv, ctx, page, base = R.open(build_site(f3), width, init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def no_market():
        wait_ready(page)
        page.locator('[data-ui-v2="rank"]').wait_for(state="visible")
        rank_chip(page, "crit", "value")                                         # 시험 데이터에는 bpsIn 이 없어요: 분기 줄 없이 종가 날짜만 (리뷰 3차)
        assert page.locator('[data-ui-v2="rank-date"]').inner_text() == "10월 30일 종가", page.locator('[data-ui-v2="rank-date"]').inner_text()
        rank_chip(page, "cap")
        rank_market(page, "us")
        assert page.locator('[data-ui-v2="rank-chips"] [data-ui-v2="rank-chip"]').count() == 0
        fail = page.locator('[data-ui-v2="rank"] [data-ui-v2="rank-fail"] [data-ui-v2="load-fail"]')
        assert fail.inner_text() == LOAD_FAIL and page.locator('[data-ui-v2="rank-window"], [data-ui-v2="rank-empty"], [data-ui-v2="rank-foot"]').count() == 0
        R.collect(page)
        rank_market(page, "kr")
    R.check(page, S, "미국 종목이 없는 파일: 미국은 칩 없이 불러오기 실패 문구 · 분기 자본이 확인되지 않은 한국 가치는 종가 날짜만", no_market)
    ctx.close()
    srv.shutdown()


def scene_rank_pc(R, files):
    """PC (1280): 다시 온 방문자의 홈 오른쪽 칸, 시장 한눈에 밑에 종목 순위 · 창에 7줄(58px) · 움직여요 · 가로 스크롤 없음 · 전체 보기 → 종목 탭."""
    S = f"종목 순위 PC {PC_W}"
    srv, ctx, page, base = R.open(build_site(files), PC_W, device=pc_device(PC_W), init=rank_store([RANK_DECK]), path="/app.html?dev=1#home")

    def side():
        wait_ready(page)
        rank = page.locator('[data-ui-v2="col-side"] [data-ui-v2="rank"]')
        rank.wait_for(state="visible")
        glance = page.locator('[data-ui-v2="col-side"] [data-ui-v2="market-glance"]')
        assert glance.bounding_box()["y"] + glance.bounding_box()["height"] <= rank.bounding_box()["y"]
        win = rank.locator('[data-ui-v2="rank-window"]')
        assert win.get_attribute("data-rows") == "7" and abs(win.bounding_box()["height"] - 7 * 58) < 1
        win.scroll_into_view_if_needed()
        rank_wait(page, "data-moving", "1")
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        chips = rank.locator('[data-ui-v2="rank-chips"]')                   # PC: 칩 줄은 옆으로 밀지 않고 여러 줄로
        assert chips.evaluate("(e) => [getComputedStyle(e).flexWrap, e.scrollWidth <= e.clientWidth]") == ["wrap", True]
        ys = {round(b["y"]) for b in (c.bounding_box() for c in chips.locator('[data-ui-v2="rank-chip"]').all())}
        assert len(ys) >= 2, ys
        side = page.locator('[data-ui-v2="col-side"]').bounding_box()
        for c in chips.locator('[data-ui-v2="rank-chip"]').all():
            b = c.bounding_box()
            assert side["x"] - 0.5 <= b["x"] and b["x"] + b["width"] <= side["x"] + side["width"] + 0.5, (b, side)
        # Jack, 2026-11-12: '누르고 있으면 멈춰요' 는 휴대폰에서만 (PC 는 마우스를 올리면 멈춰요) · 칩과 한국/미국은 44px 이상
        assert rank.locator('[data-ui-v2="rank-hint"]').count() == 0 and rank.locator('[data-ui-v2="rank-all"]').count() == 1
        hs = rank.locator('[data-ui-v2="rank-chip"], [data-ui-v2="rank-market"] button').evaluate_all("(els) => els.map((e) => e.getBoundingClientRect().height)")
        assert hs and min(hs) >= 44 - 0.5, hs
        # 1200px 아래(1024–1199)에서는 종목 순위가 오른쪽 칸이 아니라 왼쪽(넓은) 칸 끝으로 (Jack, 2026-11-12)
        page.set_viewport_size({"width": 1100, "height": PC_H})
        page.locator('[data-ui-v2="col-main"] [data-ui-v2="rank"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="col-side"] [data-ui-v2="rank"]').count() == 0
        assert page.locator('[data-ui-v2="col-side"] [data-ui-v2="market-glance"]').count() == 1
        last = page.locator('[data-ui-v2="col-main"] > *').last
        assert last.get_attribute("data-ui-v2") == "rank", last.get_attribute("data-ui-v2")
        page.set_viewport_size({"width": PC_W, "height": PC_H})
        rank.wait_for(state="visible")
        for w in (1024, 1280, 1440):
            page.set_viewport_size({"width": w, "height": PC_H})
            page.wait_for_timeout(100)
            no_hscroll(page, w)
        page.set_viewport_size({"width": PC_W, "height": PC_H})
        R.collect(page)
        page.locator('[data-ui-v2="rank-all"]').click()
        at(page, "stocks")
        full = page.locator('[data-ui-v2="rank"][data-full="1"]')
        full.wait_for(state="visible")
        page.wait_for_function("() => document.activeElement && document.activeElement.tagName === 'H3'")
        bar = page.locator('[data-ui-v2="top-bar"]').bounding_box()
        y = full.bounding_box()["y"]
        assert bar["y"] + bar["height"] - 1 <= y < PC_H / 2, (bar, y)            # 위 막대에 가리지 않고 화면 안
        R.collect(page)
    R.check(page, S, "PC: 오른쪽 칸 시장 한눈에 밑 · 창 7줄 · 움직임 · 칩은 여러 줄(칸 안) · 멈춤 안내 없음 · 칩 44px · 1100px 은 왼쪽 칸 끝 · 1024–1440px 가로 스크롤 없음 · 전체 보기 → 종목 탭(위 막대 밑)", side)
    ctx.close()
    srv.shutdown()


# ── v19.6d 어두운 화면 (docs/tasks/v19.6-records-alerts-dark.md Part D) ──
THEME_KEY = "baepsae-theme"
SEGMENTED = '[data-ui="segmented"]:not([data-ui-v2="theme-mode"] *)'           # 고르기 묶음, 화면 모드 스위치는 빼고
PAGE_RGB = {"light": "rgb(245, 243, 239)", "dark": "rgb(16, 21, 30)"}           # tokens.js page (= the theme-color meta)
META = {"light": "#F5F3EF", "dark": "#10151E"}
INK_RGB = {"light": "rgb(28, 43, 69)", "dark": "rgb(232, 236, 242)"}
MASCOT_CHIP_RGB = "rgb(245, 243, 239)"
# The first paint: when <body> arrives (the head, its colour sheet and its small script are done) and at the first frame, the
# page's colour is recorded. If the mode were applied later (by the app), the first paint would flash the light page.
FIRST_PAINT = """(() => {
  const look = () => [document.documentElement.getAttribute('data-theme'), getComputedStyle(document.documentElement).backgroundColor,
    (document.querySelector('meta[name="theme-color"]') || {}).content || null];
  window.__v2paint = { body: null, frame: null };
  const mo = new MutationObserver(() => { if (document.body && !window.__v2paint.body) { window.__v2paint.body = look(); mo.disconnect(); } });
  mo.observe(document, { childList: true, subtree: true });
  requestAnimationFrame(() => { window.__v2paint.frame = look(); });
})();"""
# The placeholder colour of an input as drawn, the browser's own placeholder colour (an input in a shadow root, which the page's
# colour sheet does not reach) and the first background behind the input that is not transparent.
PLACEHOLDER_JS = """(e) => {
  const host = document.createElement('div'); document.body.appendChild(host);
  const probe = document.createElement('input'); probe.placeholder = 'x'; host.attachShadow({ mode: 'open' }).appendChild(probe);
  const browser = getComputedStyle(probe, '::placeholder').color; host.remove();
  let bg = 'rgba(0, 0, 0, 0)', n = e;
  while (n && n.nodeType === 1) { const b = getComputedStyle(n).backgroundColor; if (b !== 'rgba(0, 0, 0, 0)' && b !== 'transparent') { bg = b; break; } n = n.parentElement; }
  return { mine: getComputedStyle(e, '::placeholder').color, browser, bg };
}"""
TEXT3_DARK_RGB, SURFACE_DARK_RGB = "rgb(142, 153, 170)", "rgb(26, 34, 49)"        # tokens.js PALETTE.dark text3 #8E99AA, surface #1A2231


def rgb_ratio(a, b):
    def lum(c):
        v = [int(x) / 255 for x in re.findall(r"\d+", c)[:3]]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


# Storage that refuses everything (a private window with site data blocked): reading the choice throws too.
NO_STORAGE = """(() => { for (const m of ['getItem', 'setItem', 'removeItem']) Storage.prototype[m] = function () { throw new Error('blocked'); }; })();"""


def theme_now(page):
    return page.evaluate("""() => [document.documentElement.dataset.theme, document.documentElement.dataset.themeMode,
        document.querySelector('meta[name="theme-color"]').content, getComputedStyle(document.body).backgroundColor,
        getComputedStyle(document.documentElement).colorScheme]""")


def stored_mode(page):
    return page.evaluate(f"() => {{ try {{ return localStorage.getItem('{THEME_KEY}'); }} catch (e) {{ return 'blocked'; }} }}")


def mode_switch(page, width):
    """The 화면 모드 switch: in the ☰ menu on the phone, in the left menu on PC. Returns its locator (opens the menu on the phone)."""
    if width < 1024 and page.locator('[data-ui-v2="menu"]').count() == 0:
        open_menu(page)
    sw = page.locator('[data-ui-v2="theme-mode"]')
    sw.wait_for(state="visible")
    return sw


def pick_mode(page, width, mode):
    sw = mode_switch(page, width)
    sw.get_by_role("radio", name=C["menu"]["mode"][mode], exact=True).click()
    page.wait_for_function("(m) => document.documentElement.dataset.themeMode === m", arg=mode)


def scene_dark(R, files, width):
    """v19.6d: 화면 모드 자동 · 밝게 · 어둡게 (☰ 메뉴, PC 는 왼쪽 메뉴). 자동은 기기를 따라 바로 바뀌고, 고른 것은 이 기기에만(새로고침해도
    그대로) · 기록은 그대로 · 내보낸 파일에 없어요. 첫 화면부터 그 색(번쩍임 없음) · 브라우저 막대 색(theme-color)도 따라가요.
    저장소가 막히면 자동(오류 없음). 어두운 화면: 아이콘은 어두운 표 · 뱁이는 밝은 칩 위 · 불러오기 실패 문구."""
    S = f"어두운 화면 {width}"
    pc = width >= 1024
    screen = (pc_device(width) if pc else {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2})
    f = daily_files(files)
    d = f["data.json"]
    by = {s["t"]: s for s in d["stocks"]}
    deck = e_imported(by, d["pxDate"], [("005930", 10, 200000), ("000660", 3, None), ("AAPL", 2, 300.0)])
    srv, ctx, page, base = R.open(build_site(f), width, device={**screen, "color_scheme": "light"}, init=e_store([deck]) + FIRST_PAINT,
                                  accept_downloads=True, path="/app.html?dev=1#home")
    M = C["menu"]["mode"]

    def switch():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        assert theme_now(page) == ["light", "auto", META["light"], PAGE_RGB["light"], "light"], theme_now(page)
        assert stored_mode(page) is None
        records = page.evaluate("() => localStorage.getItem('baepsae2.v1')")
        sw = mode_switch(page, width)
        assert sw.locator('[role="radiogroup"]').get_attribute("aria-label") == M["title"]
        radios = sw.get_by_role("radio")
        assert radios.all_inner_texts() == [M["auto"], M["light"], M["dark"]], radios.all_inner_texts()
        assert [radios.nth(i).get_attribute("aria-checked") for i in range(3)] == ["true", "false", "false"]
        for i in range(3):                                                    # 누르는 곳 44px 이상
            box = radios.nth(i).bounding_box()
            assert box["height"] >= 44 - 0.5 and box["width"] >= 44 - 0.5, box
        assert M["title"] in sw.inner_text() and M["hint"] in sw.inner_text()
        if not pc:                                                            # 메뉴 줄 아래, 데이터 날짜 위
            order = page.evaluate("""() => ['menu-item', 'theme-mode', 'menu-date'].map((k) => { const e = document.querySelector(`[data-ui-v2="${k}"]`);
                return e ? e.getBoundingClientRect().top : null; })""")
            assert order[0] < order[1] < order[2], order
        R.collect(page)
        pick_mode(page, width, "dark")
        assert theme_now(page) == ["dark", "dark", META["dark"], PAGE_RGB["dark"], "dark"], theme_now(page)
        assert stored_mode(page) == "dark"
        assert page.evaluate("() => getComputedStyle(document.querySelector('h1, h2, h3')).color") == INK_RGB["dark"]
        R.collect(page)                                                       # 어두운 표의 아이콘 · 뱁이 칩 · 12px · 살구색 (visualcheck)
        assert page.evaluate("() => localStorage.getItem('baepsae2.v1')") == records, "화면 모드를 바꾸니 기록이 바뀌었어요"
        # 새로고침: 첫 화면부터 어두운 색 (번쩍임 없음) · 고른 것 그대로
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        paint = page.evaluate("() => window.__v2paint")
        assert paint["body"] == ["dark", PAGE_RGB["dark"], META["dark"]], paint
        assert paint["frame"] is None or paint["frame"] == ["dark", PAGE_RGB["dark"], META["dark"]], paint
        assert theme_now(page)[:3] == ["dark", "dark", META["dark"]]
        assert mode_switch(page, width).get_by_role("radio", name=M["dark"], exact=True).get_attribute("aria-checked") == "true"
        assert page.evaluate("() => localStorage.getItem('baepsae2.v1')") == records
        # 밝게: 기기가 어두워도 밝게, 새로고침해도
        pick_mode(page, width, "light")
        page.emulate_media(color_scheme="dark")
        page.wait_for_timeout(200)
        assert theme_now(page) == ["light", "light", META["light"], PAGE_RGB["light"], "light"], theme_now(page)
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        assert page.evaluate("() => window.__v2paint.body") == ["light", PAGE_RGB["light"], META["light"]]
        # 자동: 저장한 값이 없어지고, 기기를 따라 그 자리에서 바뀌어요 (새로고침 없이)
        pick_mode(page, width, "auto")
        assert stored_mode(page) is None
        page.wait_for_function("() => document.documentElement.dataset.theme === 'dark'")
        assert theme_now(page) == ["dark", "auto", META["dark"], PAGE_RGB["dark"], "dark"], theme_now(page)
        page.emulate_media(color_scheme="light")
        page.wait_for_function("() => document.documentElement.dataset.theme === 'light'")
        assert theme_now(page) == ["light", "auto", META["light"], PAGE_RGB["light"], "light"], theme_now(page)
        page.emulate_media(color_scheme="dark")
        page.wait_for_function("() => document.documentElement.dataset.theme === 'dark'")
        assert theme_now(page)[2] == META["dark"]
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        assert page.evaluate("() => window.__v2paint.body") == ["dark", PAGE_RGB["dark"], META["dark"]]
        assert page.evaluate("() => localStorage.getItem('baepsae2.v1')") == records
        # 내보낸 기록 파일에는 화면 모드가 없어요
        pick_mode(page, width, "dark")
        if not pc:
            page.locator('[data-ui-v2="menu-close"]').click()
        tab(page, TABS["portfolio"]) if not pc else side_tab(page, "portfolio")
        at(page, "portfolio")
        with page.expect_download() as dl:
            page.get_by_role("button", name=C["store"]["export"]).click()
        with open(dl.value.path(), encoding="utf-8") as fh:
            text = fh.read()
        exported = json.loads(text)
        assert exported["decks"] and exported == json.loads(records), "내보낸 파일이 저장한 기록과 달라요 (화면 모드가 끼었나요?)"
        assert "theme" not in text and THEME_KEY not in text, text[:200]           # 화면 모드는 파일 어디에도 없어요
        R.collect(page)
    R.check(page, S, "화면 모드: 자동(기본) · 밝게 · 어둡게 · 안내 줄 · 44px · 고르면 바로 · 새로고침해도 그대로 · 첫 화면부터 그 색 · "
            "theme-color 도 · 자동은 기기를 따라 그 자리에서 · 기록 그대로 · 내보낸 파일에 없음", switch)
    ctx.close()
    srv.shutdown()

    # 입력칸의 안내 글(placeholder): 어두운 화면에서는 text3 (브라우저의 회색은 어두운 바탕 위 3.5:1), 밝은 화면은 브라우저 그대로
    srv, ctx, page, base = R.open(build_site(files), width, device={**screen, "color_scheme": "light"}, path="/app.html?dev=1#stocks")

    def placeholder():
        wait_ready(page)
        box = page.locator('[data-ui-v2="top-search"] input' if pc else '[data-ui-v2="stock-search"] input').first
        box.wait_for(state="visible")
        assert box.get_attribute("placeholder")
        light = box.evaluate(PLACEHOLDER_JS)
        assert light["mine"] == light["browser"], light                  # 밝은 화면: 바꾸지 않았어요
        pick_mode(page, width, "dark")
        if not pc:
            page.locator('[data-ui-v2="menu-close"]').click()
        dark = box.evaluate(PLACEHOLDER_JS)
        assert dark["mine"] == TEXT3_DARK_RGB and dark["bg"] == SURFACE_DARK_RGB, dark
        assert rgb_ratio(dark["mine"], dark["bg"]) >= 4.5, (dark, rgb_ratio(dark["mine"], dark["bg"]))
        assert rgb_ratio(dark["browser"], dark["bg"]) < 4.5, dark                # 그래서 바꿨어요 (브라우저 회색은 미달)
        pick_mode(page, width, "light")
        assert box.evaluate(PLACEHOLDER_JS) == light
    R.check(page, S, "입력칸 안내 글: 어두운 화면에서 text3 (4.5:1 이상) · 밝은 화면은 브라우저 그대로", placeholder)
    ctx.close()
    srv.shutdown()

    # 저장소가 막힌 기기: 자동(기기를 따라), 오류 없음. 고르면 이번 방문 동안만
    srv, ctx, page, base = R.open(build_site(files), width, device={**screen, "color_scheme": "dark"}, init=NO_STORAGE + FIRST_PAINT)

    def blocked():
        wait_ready(page)
        assert page.evaluate("() => window.__v2paint.body") == ["dark", PAGE_RGB["dark"], META["dark"]]
        assert theme_now(page) == ["dark", "auto", META["dark"], PAGE_RGB["dark"], "dark"], theme_now(page)
        sw = mode_switch(page, width)
        assert sw.get_by_role("radio", name=M["auto"], exact=True).get_attribute("aria-checked") == "true"
        pick_mode(page, width, "light")
        assert theme_now(page)[:3] == ["light", "light", META["light"]]
        R.collect(page)
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        assert theme_now(page)[:2] == ["dark", "auto"], theme_now(page)
    R.check(page, S, "저장소가 막히면 자동(기기 따라 어둡게) · 오류 없음 · 고른 것은 이번 방문 동안만", blocked)
    ctx.close()
    srv.shutdown()

    # 저장한 값이 엉뚱하면 자동
    srv, ctx, page, base = R.open(build_site(files), width, device={**screen, "color_scheme": "light"},
                                  init=f"try {{ localStorage.setItem('{THEME_KEY}', 'purple'); }} catch (e) {{}}")

    def junk():
        wait_ready(page)
        assert theme_now(page)[:2] == ["light", "auto"], theme_now(page)
    R.check(page, S, "저장한 값이 엉뚱하면 자동", junk)
    ctx.close()
    srv.shutdown()

    # 불러오기 실패 (데이터 파일 없음) 를 어두운 화면에서: 문구 · 어두운 page · 뱁이는 밝은 칩 위
    srv, ctx, page, base = R.open(build_site(files, drop=("data.json",)), width, device={**screen, "color_scheme": "light"},
                                  init=f"try {{ localStorage.setItem('{THEME_KEY}', 'dark'); }} catch (e) {{}}" + FIRST_PAINT)

    def fail():
        see(page, LOAD_FAIL)
        assert page.evaluate("() => window.__v2paint.body") == ["dark", PAGE_RGB["dark"], META["dark"]]
        assert theme_now(page)[:4] == ["dark", "dark", META["dark"], PAGE_RGB["dark"]]
        msg = page.get_by_text(LOAD_FAIL).first
        assert msg.evaluate("(e) => getComputedStyle(e).color") == INK_RGB["dark"]
        R.collect(page)
        tab(page, TABS["market"]) if not pc else side_tab(page, "market")
        at(page, "market")
        see(page, LOAD_FAIL)
        img = page.locator('[data-ui-v2="load-fail"] img[src^="baepi-"]').first
        img.wait_for(state="visible")
        assert img.evaluate("(e) => getComputedStyle(e).backgroundColor") == MASCOT_CHIP_RGB
        assert img.evaluate("(e) => getComputedStyle(e).filter") == "none"           # 뱁이는 다시 칠하지 않아요
        R.collect(page)
    R.check(page, S, "불러오기 실패 문구를 어두운 화면에서 (첫 화면부터 어두운 색 · 뱁이는 밝은 칩 위)", fail)
    ctx.close()
    srv.shutdown()


def scene_hint(R, files, devices):
    """아이폰 홈 화면 안내는 아이폰 사파리에서만 (문구는 승인 대기: 그동안은 숨은 자리 표시). 안드로이드 · 홈 화면 앱 안에서는 없어요.
    첫 방문(포트폴리오 전)은 홈과 빈 포트폴리오, 포트폴리오가 있으면 포트폴리오의 기록 칸. 모두 처음 안내를 이미 본 방문자예요
    (Runner.open guide_seen). 처음 안내가 저절로 뜬 첫 방문의 안내 자리는 scene_v193c_first 가 봐요."""
    store, _ = missing_store(files)
    for name, dev, saved, want in (("아이폰 사파리 · 첫 방문(처음 안내를 이미 본 방문자)", devices["iPhone 13"], None, {"home": ["first"], "portfolio": ["first"]}),
                                    ("아이폰 사파리 · 포트폴리오 있음", devices["iPhone 13"], store, {"home": [], "portfolio": ["move"]}),
                                    ("아이폰 홈 화면 앱 · 포트폴리오 있음", {**devices["iPhone 13"], "user_agent": standalone_ua(devices["iPhone 13"]["user_agent"])}, store,
                                     {"home": [], "portfolio": []}),
                                    ("안드로이드 크롬 · 첫 방문(처음 안내를 이미 본 방문자)", devices["Pixel 5"], None, {"home": [], "portfolio": []})):
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


# ── v19.1a 회사 페이지 ──
CO = C["co"]
# 한국 배당 추세 스위치: 위의 KR_DIV_TREND (src/v2/engine.js). 회사 페이지 화면 시험은 코드의 값을 따라요


def kr_dps_agrees(s):
    """engine.dpsAgrees: 주당 배당 ÷ 오늘 종가가 그 보고서 수익률의 1/3 ~ 3 배 (보고서 수익률이 없으면 그대로)."""
    d, y, p = s.get("dps"), s.get("dy"), s.get("price")
    if d is None:
        return False
    if d == 0:
        return y is None or y == 0
    if y is None:
        return True
    if not (y > 0) or y > 30 or not (p and p > 0):
        return False
    return 1 / 3 <= d / p * 100 / y <= 3


def kr_yield_today(s, co):
    """engine.js krYieldToday (회사 페이지는 보고서 연도를 알 때만): 최근 사업보고서 주당 배당 ÷ 오늘 종가, 그 보고서 수익률과 맞춰 본 값만
    (보고서 수익률이 없으면 맞춰 볼 수 없어 없음) · 연 30% 이하만. 0원은 가격이 있을 때 0."""
    fy = s.get("fy") or (co or {}).get("fy")
    if not fy or not kr_dps_agrees(s) or not (s.get("price") or 0) > 0:
        return None
    if s["dps"] > 0 and s.get("dy") is None:
        return None
    y = s["dps"] / s["price"] * 100
    if y > 30:
        return None
    if s["dps"] > 0 and s["dy"] > 0 and y / s["dy"] >= 1.8 - 1e-9:          # 임시 분할 안전장치 (Jack, 2026-11-05): 보고서 수익률의 1.8배 이상
        return None
    return y
MEMO_TEXT = "서비스 매출이 이어지는지 보려고요"
CO_SEL = '[data-ui-v2="company"], [data-ui-v2="co-not-found"], [data-ui-v2="co-value-more"], [data-ui-v2="co-earn-more"]'


def js_round(x, d):
    k = 10 ** d
    return math.floor(x * k + 0.5) / k


def signed_pct(v):
    """deckcalc.signedPct: 한 자리로 반올림, 0 이면 부호 없음, 빼기는 U+2212."""
    r = js_round(v, 1)
    return ("\u2212" if r < 0 else "+" if r > 0 else "") + f"{abs(r):,.1f}%"        # nf: 천 단위 쉼표


def pct_text(v):
    """cofmt.pctText: 한 자리, 부호는 빼기(U+2212)만."""
    r = js_round(v, 1)
    return ("\u2212" if r < 0 else "") + f"{abs(r):,.1f}%"


DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="


def disc_links_ok(page, rows_data):
    """공시 줄의 DART 링크 (Jack, 2026-11-05: 링크만): 정확한 접수번호(14자리)가 있는 줄만 그 공시 원문으로 가는 <a> (새 탭 · noopener),
    없는 줄은 링크 없는 줄. DART 를 가리키는 다른 것(그림 · 스크립트 · 다른 링크)은 없어요. rows_data: 보이는 순서의 disc.json 줄."""
    rows = page.locator('[data-ui-v2="co-disc-row"]')
    assert rows.count() == len(rows_data), (rows.count(), len(rows_data))
    n_links = 0
    for el, x in zip(rows.all(), rows_data):
        tag = el.evaluate("(e) => e.tagName")
        rc = x.get("rc")
        if isinstance(rc, str) and re.fullmatch(r"\d{14}", rc):
            n_links += 1
            assert tag == "A" and el.get_attribute("href") == DART_VIEWER + rc, (tag, el.get_attribute("href"), rc)
            assert el.get_attribute("target") == "_blank" and el.get_attribute("rel") == "noopener"
            assert el.get_attribute("data-rc") == rc
        else:
            assert tag == "DIV" and el.get_attribute("href") is None and el.locator("a").count() == 0, (tag, rc)
    assert page.locator('a[href*="dart.fss.or.kr"]').count() == n_links
    assert page.locator('[src*="dart"], iframe, object, embed').count() == 0
    return n_links


def has_group(s):
    return isinstance(s.get("ind"), str) and bool(s["ind"]) and s["ind"] not in ("etc", "other")


def in_universe(s, cls):
    p = s.get("price")
    return (s.get("cls") == cls and not s.get("fund") and s.get("etf") is not True and isinstance(p, (int, float)) and p > 0
            and not (cls == "kr" and not str(s["t"]).endswith("0")))


def expect_rules(s, co, stocks):
    """네 칸 규칙을 파이썬으로 따로 계산해요 (src/v2/company.js 를 믿지 않고, 스펙 Part B 의 표 그대로)."""
    out = {}
    if s["cls"] == "us":
        g = s.get("g3")
        out["earn"] = "na" if g is None else "up" if g >= 3 else "down" if g <= -3 else "flat"
    else:
        op = list((co or {}).get("op") or [])[:3]
        if len(op) < 3 or any(v is None for v in op):
            out["earn"] = "na"
        else:
            a, b, c = op
            out["earn"] = "loss" if a < 0 else "up" if a > b > c else "down" if a < b < c else "mixed"
    grp = [x for x in stocks if in_universe(x, s["cls"]) and has_group(x) and has_group(s) and x["ind"] == s["ind"]]
    vals = [x["pbr"] for x in grp if isinstance(x.get("pbr"), (int, float)) and x["pbr"] > 0]
    pbr = s.get("pbr")
    med = js_round(statistics.median(vals), 2) if len(vals) >= 5 else None
    if not (isinstance(pbr, (int, float)) and pbr > 0):
        out["value"] = "na"
    elif med is None:
        out["value"] = "few"
    else:
        r = pbr / med
        out["value"] = "cheap" if r <= 0.8 + 1e-9 else "dear" if r >= 1.25 - 1e-9 else "similar"
    out["med"] = med
    if s["cls"] == "us":
        dy = s.get("dy")
        out["div"] = "na" if dy is None else "none" if dy == 0 else "pays"
    elif not KR_DIV_TREND:                                                  # 지금: 추세 없이 줘요 · 없어요 (Jack, 2026-11-05)
        dps, dy = s.get("dps"), s.get("dy")
        if dps is None:
            out["div"] = "na"
        elif not kr_dps_agrees(s):
            out["div"] = "pays" if dps > 0 and (dy is None or dy > 0) else "na"
        else:
            out["div"] = "none" if dps == 0 else "pays"
        out["streak"] = 0
    else:
        dps, d3 = s.get("dps"), s.get("dps3") or (co or {}).get("dps3")
        n = 0
        if dps is None or not kr_dps_agrees(s):
            out["div"] = "na"
        elif dps == 0:
            out["div"] = "none"
        elif not d3 or d3[0] is None or d3[1] is None or d3[0] != dps:
            out["div"] = "noPrev" if kr_yield_today(s, co) is not None else "na"
        elif d3[0] < d3[1]:
            out["div"] = "cut"
        else:
            for i in range(len(d3) - 1):
                if d3[i] is not None and d3[i + 1] is not None and d3[i] > d3[i + 1]:
                    n += 1
                else:
                    break
            out["div"] = "streak" if n >= 2 else "raised" if d3[0] > d3[1] * 1.03 + 1e-9 else "steady"
        out["streak"] = n
    b = s.get("beta")
    out["risk"] = "na" if b is None else "big" if b > 1.15 else "small" if b < 0.85 else "similar"
    return out


def tile_copy(topic, rule, us, n=0):
    T = CO["tiles"]
    label = T["label"][topic]
    if rule == "na":
        phrase = T["na"]
    elif topic == "earn":
        phrase = T["earnUs" if us else "earnKr"].get(rule)
    elif topic == "div" and rule == "streak":
        phrase = fillp(T["div"]["streak"], n=n) if T["div"]["streak"] else None
    else:
        phrase = T[topic].get(rule)
    return label, phrase


def tabs_on(cls):
    ids = ["summary", "earn", "value", "div"] + (["disc"] if cls == "kr" else [])
    return bool(CO["tabsLabel"]) and all(CO["tabs"][i] for i in ids)


def co_wait(page):
    page.locator(CO_SEL).first.wait_for(state="visible")


def co_hash(page, h):
    """회사 페이지 안의 탭을 주소로 열어요 (탭 이름이 승인되기 전에는 탭 막대가 없어요). 탭을 누를 때처럼 기록을 쌓지 않아요
    (location.replace): 뒤로는 회사 페이지를 연 곳으로 가요."""
    page.evaluate("(h) => { location.replace(h); }", h)
    page.wait_for_function("(h) => location.hash === h", arg=h)
    co_wait(page)


def co_open_tab(page, code, ctab, cls):
    if tabs_on(cls):
        page.locator(f'[data-ui-v2="co-tabs"] [data-tab="{ctab or "summary"}"]').click()
    else:
        co_hash(page, f"#stocks/{code}" + (f"/{ctab}" if ctab else ""))
    page.wait_for_function("(t) => { const e = document.querySelector('[data-ui-v2=\"company\"]'); return !!e && e.dataset.tab === t; }", arg=ctab or "summary")


def marks_ok(page):
    """회사 표시: 글자 표시(색은 열 가지 중 하나 · 흰 글자 · data-initial)만, 그림 없음 · 바깥 요청 없음 (Part G, 공급처는 Part L 뒤)."""
    marks = page.locator('[data-ui-v2="co-mark"]')
    assert marks.count() >= 1
    assert page.locator('[data-ui-v2="co-mark"] img').count() == 0, "회사 표시에 그림이 있어요 (공급처가 아직 정해지지 않았어요)"
    got = marks.evaluate_all("""(els) => els.map((e) => { const i = e.querySelector('[data-initial]'); const s = i ? getComputedStyle(i) : null;
        return [e.dataset.t, i ? i.dataset.initial : '', s ? s.backgroundColor : '', s ? s.color : '', e.getAttribute('aria-hidden')]; })""")
    allowed = {"rgb(%d, %d, %d)" % tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in MARK_COLORS}
    for t, letter, bg, fg, hidden in got:
        assert letter and bg in allowed and fg == "rgb(255, 255, 255)" and hidden == "true", (t, letter, bg, fg, hidden)


def no_mascot(page):
    assert page.locator(MASCOT_IN_MAIN).count() == 0, "회사 화면에 뱁이가 있어요 (숫자가 있는 화면)"


def co_files(files):
    f = clone(files)
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    for t in ("005930", "005380", "AAPL"):
        by[t]["d1"] = 0.5                                                   # 오늘 큰 움직임 없음 (홈의 줄은 회사 페이지로)
    return f


def scene_company(R, files, width):
    """v19.1a 회사 페이지 (docs/tasks/v19.1-company-page.md Part K): 종목 탭 · 홈 · 포트폴리오에서 누른 회사는 2.0 회사 페이지로
    (예전 뱁새로 가지 않아요) · 삼성전자 · 현대차 · AAPL 의 요약과 모든 탭 · 네 칸의 문장 = 규칙(파이썬으로 따로 계산) · 미국은 $ 먼저
    (원은 작게) · 칸마다 자기 날짜 · 뱁이 없음 · 주제 색은 Part H 표만(visual_ok) · 회사 표시는 글자 표시 · 다른 사이트 요청 0건 ·
    모르는 코드 → '이 종목의 데이터를 찾지 못했어요.' · 뒤로 → 온 곳 · 펀드는 회사 페이지가 없어요."""
    S = f"회사 {width}"
    f = co_files(files)
    stocks = f["data.json"]["stocks"]
    by = {x["t"]: x for x in stocks}
    coby = {x["t"]: x for x in f["corp.json"]["companies"]}
    md = "10월 30일"
    store = {"v": 1, "decks": [_deck("dco", "회사 포트폴리오", [(*SAMSUNG, 0.4, [_div(2025, 1668.0, 1446.0)], 2), ("005380", "현대차", 0.4, [], 1),
                                                         ("114260", "KODEX 국고채3년", 0.2, [], 3)])]}          # 안전자산 펀드: 회사 페이지가 없어요
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    wide = width >= 1024
    srv, ctx, page, base = R.open(build_site(f), width, init=init, path="/app.html?dev=1#stocks", device=pc_device(width) if wide else None)

    def search(q):
        box = page.locator('[data-ui-v2="top-search"] input' if wide else '[data-ui-v2="stock-search"] input')
        box.fill(q)
        rows = page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"]')
        rows.first.wait_for(state="visible")
        return rows

    def open_from_search(q, code):
        at(page, "stocks")
        rows = search(q)
        row = page.locator(f'[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-t="{code}"]')
        assert row.locator("a").count() == 0, "회사 줄이 예전 뱁새로 가는 링크예요"
        row.locator("button").click()
        at(page, f"stocks/{code}")
        co_wait(page)
        assert "/baepsae.html" not in page.url and page.url.endswith(f"#stocks/{code}"), page.url

    def back_to(r):
        page.locator('[data-ui-v2="app-bar"] button').first.click()
        at(page, r)

    def check_summary(code):
        s, co = by[code], coby.get(code)
        us = s["cls"] == "us"
        head = page.locator('[data-ui-v2="co-head"]')
        assert head.get_attribute("data-t") == code and page.locator('[data-ui-v2="co-name"]').inner_text() == s["nk"]
        price = page.locator('[data-ui-v2="co-price"]').inner_text().replace("\n", "")
        date = page.locator('[data-ui-v2="co-date"]').inner_text()
        if us:                                                               # 미국: 1주 가격은 $ 먼저, 원은 작게 (Jack 결정 7)
            assert re.fullmatch(r"\$[\d,]+\.\d\d", price), price
            won = page.locator('[data-ui-v2="co-won"]').inner_text()
            assert CO["usWon"] == "약 {won} · 환율 {fx}원" and re.fullmatch(r"약 [\d,]+원 · 환율 [\d,]+\.\d원", won), won
            assert date == fillp(CO["usCloseTime"], date=md), date
        else:
            assert re.fullmatch(r"[\d,]+원", price) and page.locator('[data-ui-v2="co-won"]').count() == 0, price
            assert date == fillp(C["why"]["close"], md=md), date
        exp = expect_rules(s, co, stocks)
        tiles = {t.get_attribute("data-topic"): t for t in page.locator('[data-ui-v2="co-tile"]').all()}
        for topic in ("earn", "value", "div", "risk"):
            label, phrase = tile_copy(topic, exp[topic], us, exp.get("streak", 0))
            if topic == "earn" and us and exp["earn"] != "na" and not CO["tiles"]["usGrowth"]:
                phrase = None                                               # 미국 실적 문장은 '최근 분기 …' 숫자와 함께만 (Jack, 2026-11-05)
            if not (label and phrase):
                assert topic not in tiles, (code, topic, "승인 전 문구인데 칸이 보여요")
                continue
            t = tiles[topic]
            assert t.get_attribute("data-rule") == exp[topic], (code, topic, t.get_attribute("data-rule"), exp[topic])
            assert t.locator('[data-ui-v2="tile-phrase"]').inner_text() == phrase, (code, topic)
            if topic == "value" and exp["value"] in ("cheap", "dear", "similar"):
                assert float(t.get_attribute("data-med")) == exp["med"] and float(t.get_attribute("data-pbr")) == s["pbr"]
            if topic == "risk":
                assert t.locator('[data-ui-v2="tile-number"]').count() == 0, "베타 숫자가 오차 범위 없이 보여요"
            if topic == "earn" and us:                                       # 미국 매출 숫자는 무엇인지 말하는 이름과만 (Jack, 2026-11-05)
                num = t.locator('[data-ui-v2="tile-number"]')
                if CO["tiles"]["usGrowth"] and s.get("g3") is not None:
                    assert num.inner_text() == fillp(CO["tiles"]["usGrowth"], pct=signed_pct(s["g3"])), num.inner_text()
                else:
                    assert num.count() == 0, "미국 매출 숫자가 이름 없이 보여요"
        if tiles:
            if us:                                                            # 미국: 모든 칸의 숫자 출처 한 줄
                assert page.locator('[data-ui-v2="co-tiles-source"]').inner_text() == fillp(C["why"]["srcPriceUs"], md=md)
            else:
                assert page.locator('[data-ui-v2="co-tiles-source"]').count() == 0
            # 칸마다 자기 근거: 실적 · 배당은 그 사업보고서, 가치(오늘 종가의 PBR) · 출렁임(그날까지의 베타)은 가격 날짜 (리뷰)
            report = fillp(C["app"]["reportYear"], year=co["fy"]) if co and co.get("fy") else None
            # 한국 배당: 수익률이 보일 때만 그 근거 '{fy}년 사업보고서 주당 배당과 오늘 주가로 계산했어요.' (Jack, 2026-11-05)
            kfy = s.get("fy") or (co or {}).get("fy")
            kdiv = fillp(CO["div"]["basisKr"], fy=kfy) if not us and kfy and kr_yield_today(s, co) is not None else None
            want = {"earn": None if us else report, "div": None if us else kdiv, "value": fillp(C["app"]["asOf"], md=md), "risk": fillp(C["app"]["asOf"], md=md)}
            for topic, t in tiles.items():
                b = t.locator('[data-ui-v2="tile-basis"]')
                if topic == "div" and not us:
                    ky = kr_yield_today(s, co)
                    num_el = t.locator('[data-ui-v2="tile-number"]')
                    if ky is None:
                        assert num_el.count() == 0 and b.count() == 0, ("배당 칸: 믿을 수 있는 수익률이 없으면 숫자 · 근거 없음", code)
                    else:
                        assert abs(float(t.get_attribute("data-y")) - ky) < 1e-9, (t.get_attribute("data-y"), ky)
                        assert b.inner_text() == kdiv, (b.inner_text(), kdiv)
                    if t.get_attribute("data-rule") == "na":
                        assert num_el.count() == 0, "자료가 없어요 옆에 숫자"
                    continue
                if t.get_attribute("data-rule") == "na":
                    assert b.count() == 0, topic
                elif want[topic] or us:
                    assert b.inner_text() == (want[topic] or fillp(C["app"]["asOf"], md=md)), (topic, b.inner_text())
        warn = page.locator('[data-ui-v2="co-warn"]')
        if us:
            assert warn.count() == 0, "미국 종목에 재무 경고 줄 (v19.2 전까지 없어요)"
        if not tabs_on(s["cls"]):
            assert page.locator('[data-ui-v2="co-tabs"][data-pending="1"]').count() == 1 and page.locator('[role="tablist"]').count() == 0
        marks_ok(page)
        no_mascot(page)
        no_hscroll(page, width)
        R.collect(page)

    def check_tabs(code):
        s, co = by[code], coby.get(code)
        us = s["cls"] == "us"
        exp = expect_rules(s, co, stocks)
        co_open_tab(page, code, "earn", s["cls"])
        e = page.locator('[data-ui-v2="co-earn"]')
        assert e.get_attribute("data-cls") == s["cls"] and e.get_attribute("data-rule") == exp["earn"]
        if us:
            assert e.locator('[data-ui-v2="bars"]').count() == 0, "미국 실적에 연도별 막대 (v19.2 전까지 없어요)"
            g = e.locator('[data-ui-v2="co-us-g3"]')
            # 야후 매출 증가는 최근 분기를 1년 전 같은 분기와 비교한 숫자: 그 이름과 함께만 (Jack, 2026-11-05). 이름이 승인 전이면 숫자도 없어요
            if CO["tiles"]["usGrowth"] and s.get("g3") is not None:
                assert g.inner_text() == fillp(CO["tiles"]["usGrowth"], pct=signed_pct(s["g3"])), g.inner_text()
            else:
                assert g.count() == 0, "미국 매출 숫자가 이름 없이 보여요"
            if s.get("g3") is not None:                                         # 그 숫자는 이름이 붙은 그 줄에만 있어요
                bare = signed_pct(s["g3"])
                rest = e.inner_text().replace(g.inner_text(), "", 1) if g.count() else e.inner_text()
                others = {pct_text(s[k]) for k in ("opm", "roe") if s.get(k) is not None}  # 영업이익률 · ROE 가 우연히 같은 글자일 때
                assert bare not in rest or bare in others, (bare, rest)
            # 실적 문장(매출이 늘고 있어요 …)도 그 숫자가 있을 때만 (한 분기 비교라는 걸 말하지 않고는 추세처럼 읽혀요)
            if not (CO["tiles"]["usGrowth"] and s.get("g3") is not None):
                assert e.locator("h3").count() == 0, e.inner_text()
        else:
            bars = e.locator('[data-ui-v2="bars"] [data-year]')
            if bars.count():
                vals = [float(b.get_attribute("data-v")) for b in bars.all()]
                assert vals == [co["op"][2], co["op"][1], co["op"][0]] and [b.get_attribute("data-year") for b in bars.all()] == [str(co["fy"] - 2), str(co["fy"] - 1), str(co["fy"])]
            assert fillp(C["app"]["reportYear"], year=co["fy"]) in e.inner_text()
        eq = page.locator('[data-ui-v2="co-decomp-eq"]')
        if eq.count():                                                      # 3년 주가 = 이익 × 눈높이 (배율이라 참인 식)
            pr, ep, pe = (float(eq.get_attribute(k)) for k in ("data-price", "data-eps", "data-per"))
            assert abs(pr - ep * pe) < 1e-9 and "%" not in eq.inner_text(), eq.inner_text()
        no_mascot(page)
        no_hscroll(page, width)
        R.collect(page)
        co_open_tab(page, code, "value", s["cls"])
        v = page.locator('[data-ui-v2="co-value"]')
        assert v.get_attribute("data-rule") == exp["value"]
        if s.get("pbr"):
            assert page.locator('[data-ui-v2="co-pbr"]').inner_text().split("\n")[1] == fillp(C["pick"]["receipt"]["times"], x=f"{s['pbr']:,.2f}")
        dcf = page.locator('[data-ui-v2="co-dcf"]')
        if us:
            assert dcf.count() == 0, "미국에 '지금 가격이 가정하는 것' (v19.2 전까지 없어요)"
        elif dcf.count():
            assert dcf.get_attribute("data-disc") == "10" and dcf.get_attribute("data-term") == "2"
            if dcf.get_attribute("data-g"):                                  # 첫 문장 (Jack, 2026-11-05): 0 이상 '는다', 0보다 작으면 '준다' (빼기 없이)
                g = float(dcf.get_attribute("data-g"))
                want = fillp(CO["dcf"]["headUp" if g >= 0 else "headDown"], g=f"{abs(g):,.1f}")
                head = dcf.locator('[data-ui-v2="co-dcf-head"]').inner_text()
                assert head == want and "\u2212" not in head and "-" not in head, (head, want)
        assert page.locator('[data-ui-v2="co-risk"] [data-ui-v2="tile-number"]').count() == 0
        assert "%%" not in page.locator("body").inner_text()                   # '해마다 {g}%' 에 % 를 두 번 넣지 않아요
        no_mascot(page)
        no_hscroll(page, width)
        R.collect(page)
        co_open_tab(page, code, "div", s["cls"])
        d = page.locator('[data-ui-v2="co-div"]')
        assert d.get_attribute("data-rule") == exp["div"]
        m = page.locator('[data-ui-v2="co-million"]')
        # 100만원어치, 1,000원 단위 (세전). 한국 (Jack, 2026-11-05): 1,000,000 ÷ 오늘 종가 × 최근 사업보고서 주당 배당 — 그 주당 배당이
        # 보고서 수익률과 맞을 때만 (분할 · 총액 공시는 줄 없음). 미국: 1,000,000 × 야후 수익률 ÷ 100 (v19.2 까지)
        dps, px, dy = s.get("dps"), s.get("price"), s.get("dy")
        if us:
            raw = 1e6 * dy / 100 if isinstance(dy, (int, float)) and 0 < dy <= 30 else None
        else:
            # 오늘 수익률과 같은 입력: 보고서 수익률과 맞춰 본 주당 배당 · 연 30% 이하 · 임시 분할 안전장치(1.8배) 통과 (kr_yield_today)
            ky = kr_yield_today(s, co)
            raw = 1e6 / px * dps if ky is not None and ky > 0 else None
        fy = s.get("fy") or (co or {}).get("fy")
        if raw is None or not (CO["div"]["million"] and CO["div"]["perYear"]) or (not us and not fy):
            assert m.count() == 0, (code, raw)
        else:
            assert m.count() == 1, (code, raw)
            assert abs(float(m.get_attribute("data-raw")) - raw) < 1e-6, (m.get_attribute("data-raw"), raw)
            if m.get_attribute("data-under") == "1":
                assert raw < 1000
            else:
                assert int(m.get_attribute("data-won")) == math.floor(raw / 1000 + 0.5) * 1000 >= 1000, (m.get_attribute("data-won"), raw)  # JS Math.round
            want = CO["div"]["basisUs"] if us else fillp(CO["div"]["basisKr"], fy=fy)
            assert want in m.inner_text(), (want, m.inner_text())
            assert "지난 1년 기준" not in m.inner_text() and "약 0원" not in m.inner_text()
            assert m.locator('[data-ui-v2="date-line"]').first.inner_text().startswith(fillp(C["app"]["asOf"], md=md))   # 어느 날 종가인지
        if not us:                                                           # 한국 수익률 = 100만원 줄과 같은 오늘 주가 기준 (Jack, 2026-11-05)
            ky = kr_yield_today(s, co)
            ys = page.locator('[data-ui-v2="co-yield"]')
            if ky is None:
                assert ys.count() == 0, ("믿을 수 있는 수익률이 없는데 배당수익률이 보여요", code)
            else:
                assert abs(float(ys.get_attribute("data-y")) - ky) < 1e-9 and fillp(CO["div"]["basisKr"], fy=fy) in ys.inner_text()
            if not KR_DIV_TREND:                                             # 추세가 꺼져 있으면 3년 막대도, 늘렸어요 · 줄였어요도 없어요
                assert d.locator('[data-ui-v2="bars"]').count() == 0
                assert d.get_attribute("data-rule") in ("pays", "none", "na"), d.get_attribute("data-rule")
                txt = d.inner_text()
                words = [CO["div"]["head"][k] for k in ("cut", "streak", "raised", "steady")]
                words += [CO["tiles"]["div"][k] for k in ("cut", "streak", "raised", "steady", "noPrev")]
                for w in words:
                    if w:
                        assert w.split("}")[-1] not in txt, w                  # '{n}년 연속 …' 은 {n} 뒤 글자로 찾아요
        if page.locator('[data-ui-v2="co-dps"]').count():                   # 주당 배당은 보고서 수익률과 맞을 때만 (1/3 ~ 3 배)
            assert kr_dps_agrees(s), code
            if s.get("dy"):
                r = s["dps"] / s["price"] * 100 / s["dy"]
                assert 1 / 3 <= r <= 3, r
        pay = page.locator('[data-ui-v2="co-payout"]')
        if pay.count():
            assert 0 < float(pay.get_attribute("data-pct")) <= 100
        if not us and s.get("dps") and s.get("dy") and kr_dps_agrees(s) and s["dps"] / s["price"] * 100 / s["dy"] >= 1.8 - 1e-9:
            assert pay.count() == 0, "분할 안전장치에 걸린 종목의 배당성향 (오늘 주식 수 기준)"
        if us:
            assert page.locator('[data-ui-v2="co-dps"], [data-ui-v2="co-payout"]').count() == 0, "미국 주당 배당 · 배당성향 (자료가 없어요)"
        no_mascot(page)
        no_hscroll(page, width)
        R.collect(page)
        if us:
            co_hash(page, f"#stocks/{code}/disc")                              # 미국: 공시 탭이 없어요 → 요약
            assert page.locator('[data-ui-v2="company"]').get_attribute("data-tab") == "summary"
            assert page.locator('[data-ui-v2="co-tabs"] [data-tab="disc"]').count() == 0
        else:
            co_open_tab(page, code, "disc", s["cls"]) if tabs_on("kr") else co_hash(page, f"#stocks/{code}/disc")
            if tabs_on("kr"):
                ds = page.locator('[data-ui-v2="co-disc"]')
                ds.wait_for(state="attached")
                page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-disc\"]'); return !!e && e.dataset.state === 'ok'; }")
                n = sum(1 for x in f["disc.json"]["insider"] if x["t"] == code)
                assert ds.get_attribute("data-n") == str(n), (ds.get_attribute("data-n"), n)
                # 내용 날짜는 가장 최근 공시일(newest), 실행일(asOf) 아님 · 새로 받은 파일이라 멈춤 표시 없음
                assert ds.get_attribute("data-stale") == "0"
                assert ds.locator('[data-ui-v2="date-line"]').first.inner_text() == fillp(C["app"]["asOf"], md="10월 29일")
                shown = sorted((x for x in f["disc.json"]["insider"] if x["t"] == code), key=lambda x: x["d"], reverse=True)[:10]
                if CO["disc"]["buy"] and CO["disc"]["sell"]:                     # 줄마다 그 공시의 DART 원문 링크 (정확한 접수번호만)
                    assert disc_links_ok(page, shown) == len(shown) >= 1
                else:
                    assert page.locator('a[href*="dart.fss.or.kr"]').count() == 0
                no_mascot(page)
                no_hscroll(page, width)
                R.collect(page)
        co_hash(page, f"#stocks/{code}/value-more")
        if not CO["valueMore"]["title"]:                                      # 승인 전: 자세히 화면 대신 그 탭 (빈 화면 아님)
            assert page.locator('[data-ui-v2="company"]').get_attribute("data-tab") == "value"
            assert page.locator('[data-ui-v2="co-value-more"], [data-ui-v2="co-value-more"]').count() == 0
        vm = page.locator('[data-ui-v2="co-value-more"]')
        for r in vm.locator('[data-ui-v2="co-receipt"]').all():               # 근거 수치는 위의 숫자를 다시 만들어요
            txt = r.inner_text()
            nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]+(?:\.\d+)?", txt)]
            assert len(nums) == 3 and abs(round(nums[0] / nums[1], 2 if "순자산" in txt else 1) - nums[2]) < 1e-9, txt
        no_mascot(page)
        no_hscroll(page, width)
        R.collect(page)
        if not us:
            co_hash(page, f"#stocks/{code}/earn-more")
            if CO["earn"]["moreTitle"]:
                page.locator('[data-ui-v2="co-earn-more"]').wait_for(state="visible")
            else:
                assert page.locator('[data-ui-v2="company"]').get_attribute("data-tab") == "earn"
            no_mascot(page)
            R.collect(page)
        co_hash(page, f"#stocks/{code}")

    def from_stocks():
        wait_ready(page)
        at(page, "stocks")
        for q, code in (("삼성전자", "005930"), ("현대차", "005380"), ("AAPL", "AAPL")):
            open_from_search(q, code)
            check_summary(code)
            check_tabs(code)
            back_to("stocks")                                                 # 뒤로 → 온 곳 (종목, 찾던 결과 그대로)
            box = page.locator('[data-ui-v2="top-search"] input' if wide else '[data-ui-v2="stock-search"] input')
            assert box.input_value() == q, box.input_value()
            box.fill("")
        rec = page.locator('[data-ui-v2="recent"] [data-ui-v2="stock-row"]').evaluate_all("(els) => els.map((e) => e.dataset.t)")
        assert rec[:3] == ["AAPL", "005380", "005930"], rec                   # 최근 본 종목에 남아요
    R.check(page, S, "종목 → 삼성전자 · 현대차 · AAPL 회사 페이지(예전 뱁새 아님) · 요약 네 칸 = 규칙 · 모든 탭 · 자세히 · 날짜 · $ 먼저 · 뱁이 없음 · 뒤로 → 종목", from_stocks)

    def fund_and_unknown():
        at(page, "stocks")
        fund = next(x for x in stocks if x.get("etf") and x["cls"] == "kr")
        search(fund["t"])
        row = page.locator(f'[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-t="{fund["t"]}"]')
        row.locator("button").click()
        page.wait_for_timeout(200)
        at(page, "stocks")                                                    # 펀드는 회사가 아니에요: 그 자리에 머물러요
        note = row.locator('[data-ui-v2="row-note"]')                       # v19.1a 전과 같은 줄 (co.fundNote 가 승인되면 그 줄)
        assert note.inner_text().strip() == (CO["fundNote"] or C["stocks"]["krOnly"])
        page.goto(base + "/app.html?dev=1#stocks/ZZZZ9", wait_until="domcontentloaded")
        page.locator('[data-ui-v2="co-not-found"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="co-not-found"]').inner_text().strip() == CO["notFound"] == "이 종목의 데이터를 찾지 못했어요."
        no_mascot(page)
        R.collect(page)
        back_to("stocks")
    R.check(page, S, "펀드를 누르면 그 자리 (회사 페이지 없음) · 모르는 코드 → '이 종목의 데이터를 찾지 못했어요.' (빈 화면 아님)", fund_and_unknown)

    def from_portfolio_and_home():
        if wide:
            side_tab(page, "portfolio")
        else:
            tab(page, TABS["portfolio"])
        at(page, "portfolio")
        row = page.locator('[data-deck-id="dco"] [data-holding="005930"] [data-ui="list-row"]')
        row.wait_for(state="visible")
        assert row.locator('[data-ui-v2="co-mark"]').count() == 1
        fund = page.locator('[data-deck-id="dco"] [data-holding="114260"] [data-ui="list-row"]')
        assert fund.count() == 1 and fund.get_attribute("role") is None, "펀드 줄이 눌러져요 (회사 페이지가 없는데)"
        row.click()
        at(page, "stocks/005930")
        held = page.locator('[data-ui-v2="co-held-row"][data-deck-id="dco"]')
        held.wait_for(state="visible")                                        # 가진 종목: 포트폴리오 줄
        if CO["memo"]["title"] and CO["memo"]["rules"]:
            assert page.locator('[data-ui-v2="co-memo-rules"] [data-ui-v2="rule-line"]').count() >= 1       # 다시 볼 조건 (읽기만)
        no_mascot(page)
        R.collect(page)
        back_to("portfolio")
        if wide:
            side_tab(page, "home")
        else:
            tab(page, TABS["home"])
        at(page, "home")
        hf = page.locator('[data-home-holding="114260"]').first
        hf.wait_for(state="visible")
        assert hf.get_attribute("role") is None, "홈의 펀드 줄이 눌러져요"
        hrow = page.locator('[data-home-holding="005380"]').first
        hrow.wait_for(state="visible")
        hrow.click()
        at(page, "stocks/005380")
        co_wait(page)
        back_to("home")
    R.check(page, S, "포트폴리오 · 홈의 종목 줄(표시 있음) → 그 회사 페이지 (가진 종목 줄) → 뒤로 → 온 곳", from_portfolio_and_home)

    def memo():
        M = CO["memo"]
        page.goto(base + "/app.html?dev=1#stocks/AAPL", wait_until="domcontentloaded")
        co_wait(page)
        if not (M["title"] and M["add"]):
            assert page.locator('[data-ui-v2="co-memo"]').count() == 0      # 승인 전: 메모 칸 없음
            return
        R.names = sorted(set(R.names) | {MEMO_TEXT}, key=len, reverse=True)      # 사용자가 쓴 글이에요 (문구 파일 밖)
        page.locator('[data-ui-v2="co-memo"] button', has_text=M["add"]).click()
        page.locator('[data-ui-v2="co-memo-form"] textarea').fill(f"  {MEMO_TEXT}  ")
        page.locator('[data-ui-v2="co-memo-form"] button', has_text=C["plan"]["save"]).click()
        page.locator('[data-ui-v2="co-memo-text"]').wait_for(state="visible")
        page.reload(wait_until="domcontentloaded")
        co_wait(page)
        assert page.locator('[data-ui-v2="co-memo-text"]').inner_text() == MEMO_TEXT
        stored = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1'))")
        assert stored["notes"]["AAPL"]["text"] == MEMO_TEXT and len(stored["decks"]) == 1, stored
        R.collect(page)
    R.check(page, S, "내 메모: 남기기 → 새로 고침해도 남아요 (2.0 기록에 저장)", memo)
    ctx.close()
    srv.shutdown()

    def disc_stale():
        # 리뷰: 오늘 공시 목록을 못 받은 파일(listOk false, 가장 최근 공시 10월 20일) → 멈춤 표시, 오늘 날짜를 내용 날짜로 쓰지 않아요
        g = clone(f)
        g["disc.json"].update(listOk=False, newest="2026-10-20", asOf=now_dt().date().isoformat())
        # 접수번호가 없는 줄(파이프라인의 대신 열쇠 '날짜|이름')은 링크가 없어요 (이름으로 찾는 링크도 없어요)
        kr_rows = [x for x in g["disc.json"]["insider"] if x["t"] == "005930"]
        kr_rows[0]["rc"] = kr_rows[0]["d"] + "|" + kr_rows[0]["nm"]
        srv2, ctx2, page2, _ = R.open(build_site(g), width, path="/app.html?dev=1#stocks/005930/disc", device=pc_device(width) if wide else None)
        try:
            page2.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-disc\"]'); return !!e && e.dataset.state === 'ok'; }")
            ds = page2.locator('[data-ui-v2="co-disc"]')
            assert ds.get_attribute("data-stale") == "1"
            line = ds.locator('[data-ui-v2="date-line"]').first
            assert line.get_attribute("data-stale") == "1" and line.inner_text().startswith(fillp(C["app"]["asOf"], md="10월 20일")), line.inner_text()
            assert fillp(C["app"]["stale"], n="").strip() in line.inner_text() or "갱신이 멈췄어요" in line.inner_text()
            today = now_dt()
            assert f"{today.month}월 {today.day}일 기준" not in ds.inner_text()
            if CO["disc"]["buy"] and CO["disc"]["sell"]:
                shown = sorted(kr_rows, key=lambda x: x["d"], reverse=True)[:10]
                assert disc_links_ok(page2, shown) == len(shown) - 1
            else:
                assert page2.locator('a[href*="dart.fss.or.kr"]').count() == 0
            R.collect(page2)
        finally:
            ctx2.close()
            srv2.shutdown()
    R.check(page, S, "공시: 오늘 목록을 못 받은 파일 → 가장 최근 공시일 + 'N일째 갱신이 멈췄어요' (오늘 날짜 아님)", disc_stale)


# ── v19.1b 데이터 (PR #50 의 새 칸: divCheck 가 있는 파일) ──
# data.json 에 divCheck 가 있으면 앱이 분할을 확인한 한국 배당(dps3a · divSt · dyt)과 베타 오차 범위(betaSE)를 써요. 시험 데이터에 그 칸을
# 붙여서 봐요: 분할 뒤의 배당이 '줄였어요'가 아니라 늘린 기록으로 · 진짜 삭감은 그대로 삭감 · 비교 불가(nc)와 알 수 없음(nd)은 추세 없이 ·
# 베타는 범위와 함께(양 끝이 같으면 한 숫자, 믿을 수 없으면 자료가 없어요) · 재무 경고는 확인이 다 돌았거나 해당 없을 때만 '없어요' ·
# 매수 계획과 덱 짜기의 2022년은 범위(작은 하락 먼저)와 그 설명 줄, 작은 쪽이 하락이 아니면 '오차가 너무 커서 추정하지 않았어요.'
# 예전 파일(divCheck 없음)에서는 출렁임에 숫자도 '오차 범위를 계산할 수 있을 때' 줄도 없어요 (Part O.1 이 그 줄을 없앴어요).
V191B_SPLIT = "009150"     # 삼성전기: 2024년 5:1 분할을 지어내요 (보고서 원래 숫자 9,000 · 5,750원 → 오늘 기준 1,800 · 1,150원)
V191B_CUT = "005380"       # 현대차: 같은 기준에서 12,000 → 10,000원 (진짜 삭감) · 베타 양 끝이 같아요
V191B_NC = "000660"        # SK하이닉스: 비교 불가 (유상증자처럼) · 베타 표준오차 0.6 (믿을 수 없어요)
V191B_ND = "105560"        # KB금융: 알 수 없음 · 오늘 기준 수익률 없음 · 금융지주 (유동비율 · 이자보상배율은 해당 없음)
V191B_FIN = "032830"       # 삼성생명: 보험사 (유동비율 · 이자보상배율은 해당 없음) → 금융회사 밑 줄
V191B_HOLD = "402340"      # SK스퀘어: 금융이 아닌 지주회사 → 지주회사 밑 줄 (PR #68 B3/B7)
V191B_PART = "033780"      # KT&G: 이자보상배율만 못 돌림 (재무제표에 이자비용 줄 없음, flWhy ie) → '확인한 …' 줄 (PR #68 B7)
V191B_OPMISS = "035420"    # NAVER: 이자보상배율만 못 돌렸지만 이유가 영업이익 없음(flWhy op) → 아무 말도 하지 않아요
V191B_ICRCF = "034020"     # 두산에너빌리티: 이자보상배율 0.65배를 현금흐름표의 이자 지급액으로 (flSrc cf) → 그 밑 안내 (PR #68)
V191B_ICRLOSS = "005490"   # POSCO홀딩스: 영업손실 (fl.icr 음수) → 숫자 없이 '영업손실이 나서 …' (PR #68)
V191B_SPLIT10 = "028260"   # 삼성물산: 보고서 뒤 10:1 분할을 지어내요 (보고서 28,000원 → 오늘 1주 2,800원) → 사업보고서 숫자 안내 (B3)


def v191b_files(files, se=None, beta=None):
    """divCheck 가 있는 파일처럼: 한국 배당 종목마다 dps3a = dps3 (같은 기준) · dyt = dps3a[0] ÷ 종가 (연 30% 까지), 베타가 있는 종목마다
    betaSE (기본 0.05). 위의 네 종목은 따로. se · beta: 모든 종목에 같은 값 (2022년 범위가 너무 넓은 장면)."""
    f = clone(files)
    d = f["data.json"]
    d["divCheck"] = {"v": 1, "same": 0, "adj": 1, "nc": 1, "nd": 1, "zero": 0, "noDps": 0, "pref": 0, "payers": 0, "dyt": 0}
    for s in d["stocks"]:
        if beta is not None and s.get("beta") is not None:
            s["beta"] = beta
        if s.get("beta") is not None:
            s["betaSE"], s["betaN"] = (0.05 if se is None else se), 750
        if s.get("cls") != "kr" or s.get("dps") is None or s.get("etf") or s["t"][-1] != "0":
            continue
        d3 = s["dps3"] if isinstance(s.get("dps3"), list) else [s["dps"], 0.0, 0.0] if s["dps"] == 0 else [s["dps"], None, None]
        s["dps3"], s["dps3a"], s["dpsF"] = d3, list(d3), [1.0 if x else None for x in d3]
        s["divSt"] = "zero" if all(x == 0 for x in d3) else "same"
        y = d3[0] / s["price"] * 100 if s.get("price") else None
        if y is not None and y <= 30:
            s["dyt"] = round(y, 2)
    by = {s["t"]: s for s in d["stocks"]}
    sp = by[V191B_SPLIT]
    sp.update(dps3=[2350.0, 9000.0, 5750.0], dps3a=[2350.0, 1800.0, 1150.0], dpsF=[1.0, 5.0, 5.0], divSt="adj")
    by[V191B_CUT]["betaSE"] = 0.001 if se is None else se
    nc = by[V191B_NC]
    nc.update(dps3a=[3000.0, None, 1200.0], dpsF=[1.0, None, 1.0], divSt="nc", betaSE=0.6 if se is None else se)
    nd = by[V191B_ND]
    nd.update(dps3a=[None, None, None], dpsF=[None, None, None], divSt="nd")
    nd.pop("dyt", None)
    coby = {c["t"]: c for c in f["corp.json"]["companies"]}
    coby["005930"]["flRan"] = ["cr", "icr", "l3", "imp"]
    coby[V191B_ND].update(flRan=["l3", "imp"], flNa=["cr", "icr"])
    coby[V191B_FIN].update(flRan=["l3", "imp"], flNa=["cr", "icr"])
    coby[V191B_HOLD].update(flRan=["l3", "imp"], flNa=["cr", "icr"])
    coby[V191B_PART].update(flRan=["cr", "l3", "imp"], flWhy={"icr": "ie"})
    coby[V191B_OPMISS].update(flRan=["cr", "l3", "imp"], flWhy={"icr": "op"})
    coby[V191B_ICRCF].update(fl={"icr": 0.65}, flRan=["cr", "icr", "l3", "imp"], flSrc={"icr": "cf"})
    coby[V191B_ICRLOSS].update(fl={"icr": -0.41}, flRan=["cr", "icr", "l3", "imp"], flSrc={"icr": "cf"})   # cf 여도 영업손실엔 안내 없음
    s10 = by[V191B_SPLIT10]
    s10.update(dps=28000.0, dps3=[28000.0, 26000.0, 25500.0], dps3a=[2800.0, 2600.0, 2550.0], dpsF=[10.0, 10.0, 10.0], divSt="adj",
               dyt=round(2800.0 / s10["price"] * 100, 2))
    coby[V191B_CUT]["flRan"] = ["cr", "l3", "imp"]                           # 이자보상배율 확인이 안 돌았어요: '없어요'라고 하지 않아요
    return f


def to_plan_v191b(page):
    """to_plan 과 같은 길 (배당 생활비 → 1,000만원 → 후보 고르기 → 매수 계획). v19.1b 데이터의 4단계 칸은 '약' 없이 하락 폭이라
    (PR #68) 칸 자체가 보일 때까지 기다려요. → [(종목, 주식 수)] 화면 순서대로"""
    wait_ready(page)
    start_build(page)
    page.locator('[data-deck="income"]').click()
    see(page, C["build"]["s1"]["title"])
    click_next(page)
    see(page, C["build"]["s3"]["title"])
    click_next(page)
    see(page, C["build"]["s4"]["title"])
    page.get_by_role("button", name="+1,000만").first.click()
    page.locator('[data-ui-v2="y2022-methods"] [data-method]').first.wait_for(state="visible")
    click_next(page)
    see(page, C["pick"]["title"])
    click_next(page)
    see(page, C["plan"]["stocks"])
    rows = page.locator('[data-ui-v2="screen"] [data-row]')
    rows.first.wait_for(state="visible")
    out = []
    for i in range(rows.count()):
        r = rows.nth(i)
        out.append((r.get_attribute("data-row"), int(re.search(r"([\d,]+)주", r.inner_text()).group(1).replace(",", ""))))
    return out


def scene_v191b(R, files, width):
    S = f"v19.1b 데이터 {width}"
    f = v191b_files(co_files(files))
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    srv, ctx, page, base = R.open(build_site(f), width, path="/app.html?dev=1#stocks")

    def tile(code, topic):
        t = page.locator(f'[data-ui-v2="co-tile"][data-topic="{topic}"]')
        t.first.wait_for(state="visible")
        num = t.locator('[data-ui-v2="tile-number"]')
        return t.get_attribute("data-rule"), t.locator('[data-ui-v2="tile-phrase"]').inner_text(), num.inner_text() if num.count() else None

    def open_co(code):
        co_hash(page, f"#stocks/{code}")
        page.wait_for_function("(t) => { const e = document.querySelector('[data-ui-v2=\"co-head\"]'); return !!e && e.dataset.t === t; }", arg=code)

    def ytext(y):
        r = round(y * 10) / 10
        return f"{C['pick']['receipt']['yield']} " + (f"{y:,.2f}%" if 0 < y < 0.1 else f"{r:,.1f}%")

    def company():
        wait_ready(page)
        T = CO["tiles"]
        # 분할: 예전 기록(9,000 → 2,350원)이면 '배당을 줄였어요'였어요. 오늘 기준 1,150 → 1,800 → 2,350원: 2년 연속 늘렸어요
        open_co(V191B_SPLIT)
        s = by[V191B_SPLIT]
        rule, phrase, num = tile(V191B_SPLIT, "div")
        assert (rule, phrase) == ("streak", fillp(T["div"]["streak"], n=2)), (rule, phrase)
        assert num == ytext(s["dyt"]), (num, s["dyt"])
        co_open_tab(page, V191B_SPLIT, "div", "kr")
        dv = page.locator('[data-ui-v2="co-div"]')
        assert dv.get_attribute("data-rule") == "streak"
        bars = dv.locator('[data-ui-v2="bars"] [data-year]')
        assert [(b.get_attribute("data-year"), float(b.get_attribute("data-v"))) for b in bars.all()] == [("2023", 1150.0), ("2024", 1800.0), ("2025", 2350.0)]
        assert page.locator('[data-ui-v2="co-dps"] [data-ui="amount"]').first.inner_text() == "2,350원"
        m = page.locator('[data-ui-v2="co-million"]')
        assert int(m.get_attribute("data-won")) == math.floor(1e6 * 2350 / s["price"] / 1000 + 0.5) * 1000
        assert abs(float(page.locator('[data-ui-v2="co-yield"]').get_attribute("data-y")) - s["dyt"]) < 1e-9
        no_hscroll(page, width)
        R.collect(page)
        # 진짜 삭감은 그대로 삭감 · 베타 양 끝이 같아요: 한 숫자 · 재무 경고 확인 하나가 안 돌았어요: '없어요' 없음
        open_co(V191B_CUT)
        assert tile(V191B_CUT, "div")[:2] == ("cut", T["div"]["cut"])
        b = by[V191B_CUT]["beta"]
        x = f"{round(b * 10) / 10:.1f}"
        rule, phrase, num = tile(V191B_CUT, "risk")
        assert num == fillp(T["riskOne"]["kr"], x=x), num
        assert page.locator('[data-ui-v2="co-warn"][data-n="0"]').count() == 0
        co_open_tab(page, V191B_CUT, "value", "kr")
        rk = page.locator('[data-ui-v2="co-risk"]')
        assert rk.locator('[data-ui-v2="co-risk-band"]').inner_text() == fillp(CO["risk"]["one"]["kr"], x=x)
        assert CO["risk"]["oneNote"] in rk.inner_text() and CO["risk"]["bandNote"] not in rk.inner_text()
        R.collect(page)
        # 비교 불가: 추세 없이 '배당을 줘요' + 오늘 기준 수익률 · 막대 없음 · 베타를 믿을 수 없어요: 자료가 없어요 (범위도 숫자도 없음)
        open_co(V191B_NC)
        rule, phrase, num = tile(V191B_NC, "div")
        assert (rule, phrase, num) == ("pays", T["div"]["pays"], ytext(by[V191B_NC]["dyt"])), (rule, phrase, num)
        assert tile(V191B_NC, "risk") == ("na", T["na"], None)
        co_open_tab(page, V191B_NC, "div", "kr")
        assert page.locator('[data-ui-v2="co-div"] [data-ui-v2="bars"]').count() == 0
        co_open_tab(page, V191B_NC, "value", "kr")
        # Jack, PR #68 B6: 쓸 수 있는 범위가 없으면 가치 탭의 출렁임 카드는 아예 없어요 (베타가 없는 종목처럼)
        page.locator('[data-ui-v2="co-value"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="co-risk"]').count() == 0
        R.collect(page)
        # 알 수 없음: '배당을 줘요', 숫자 없음 · 금융지주(s holding, 업종 은행): 두 확인은 해당 없고 둘은 돌았어요 → '재무 경고 신호는
        # 없어요' + 금융회사 밑 줄 (PR #68 B3/B7: 업종이 금융이면 금융회사)
        open_co(V191B_ND)
        assert tile(V191B_ND, "div") == ("pays", T["div"]["pays"], None)
        page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")
        assert CO["warn"]["none"] in page.locator('[data-ui-v2="co-warn"]').inner_text()
        sub = page.locator('[data-ui-v2="co-warn-sub"]')
        assert sub.get_attribute("data-sub") == "fin" and sub.inner_text() == CO["warn"]["noneSubFin"], sub.inner_text()
        # 금융이 아닌 지주회사: 지주회사 밑 줄
        open_co(V191B_HOLD)
        page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")
        sub = page.locator('[data-ui-v2="co-warn-sub"]')
        assert sub.get_attribute("data-sub") == "holding" and sub.inner_text() == CO["warn"]["noneSubHolding"], sub.inner_text()
        # 이자보상배율만 이자비용 줄이 없어 못 돌림: '확인한 재무 경고 신호는 없어요' + 그 이유 (Jack, PR #68 B7 · 2026-11-07)
        open_co(V191B_PART)
        page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")
        card = page.locator('[data-ui-v2="co-warn"]')
        assert card.get_attribute("data-partial") == "1"
        assert CO["warn"]["nonePartial"] in card.inner_text() and CO["warn"]["none"] not in card.inner_text().replace(CO["warn"]["nonePartial"], "")
        sub = page.locator('[data-ui-v2="co-warn-sub"]')
        assert sub.get_attribute("data-sub") == "noIcr" and sub.inner_text() == CO["warn"]["noneSubNoIcr"], sub.inner_text()
        no_hscroll(page, width)
        # 이유가 영업이익 없음이면 그 줄은 틀린 말이라 아무것도 말하지 않아요
        open_co(V191B_OPMISS)
        tile(V191B_OPMISS, "div")                                           # 회사 자료가 다 그려질 때까지
        assert page.locator('[data-ui-v2="co-warn"][data-n="0"]').count() == 0
        # 이자보상배율을 현금흐름표의 이자 지급액으로 계산: 경고 밑에 그 안내 (버튼과 목록 모두) · 영업손실: 숫자 없이 (Jack, PR #68)
        open_co(V191B_ICRCF)
        btn = page.locator('[data-ui-v2="co-warn"][data-n="1"]')
        btn.wait_for(state="visible")
        assert fillp(CO["warn"]["icr"], x="0.65") in btn.inner_text()
        assert btn.locator('[data-ui-v2="co-warn-cf"]').inner_text() == CO["warn"]["icrCfNote"]
        btn.click()
        row = page.locator('[data-ui-v2="co-warn-list"] [data-flag="icr"]')
        row.wait_for(state="visible")
        assert row.locator('[data-ui-v2="co-warn-cf"]').inner_text() == CO["warn"]["icrCfNote"]
        floor_ok(page, "회사 재무 경고 (현금흐름 안내)")                     # v19.3b 12px 바닥: #68 의 새 줄도 화면에서 재요 (검사만 추가)
        no_hscroll(page, width)
        page.keyboard.press("Escape")
        open_co(V191B_ICRLOSS)
        btn = page.locator('[data-ui-v2="co-warn"][data-n="1"]')
        btn.wait_for(state="visible")
        assert CO["warn"]["icrLoss"] in btn.inner_text() and not re.search(r"\d배", btn.inner_text()), btn.inner_text()
        assert btn.locator('[data-ui-v2="co-warn-cf"]').count() == 0                   # 숫자가 없으니 '계산했어요' 안내도 없어요
        # 삼성전자: 금융도 지주회사도 아니고 네 확인이 다 돌았어요 → 지금 밑 줄
        open_co("005930")
        page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")
        sub = page.locator('[data-ui-v2="co-warn-sub"]')
        assert sub.get_attribute("data-sub") == "" and sub.inner_text() == CO["warn"]["noneSub"], sub.inner_text()
        # B3: 보고서 뒤 10:1 분할 → 2,800원 밑에 '사업보고서에는 28,000원으로 나와요' · 올해 숫자가 그대로인 분할(삼성전기)은 안내 없음
        open_co(V191B_SPLIT10)
        co_open_tab(page, V191B_SPLIT10, "div", "kr")
        assert page.locator('[data-ui-v2="co-dps"] [data-ui="amount"]').first.inner_text() == "2,800원"
        assert page.locator('[data-ui-v2="co-dps-adj"]').inner_text() == fillp(CO["div"]["adjNote"], x="28,000")
        # 앞 막대도 다시 계산했어요 (dpsF [10, 10, 10]) → 막대 밑 안내도 (PR #68 2022/bars)
        assert page.locator('[data-ui-v2="co-bars-adj"]').inner_text() == fillp(CO["div"]["barsAdjNote"], years="2023·2024")
        floor_ok(page, "회사 배당 (주식 수 맞춤 안내)")                     # v19.3b 12px 바닥: #68 의 새 줄도 화면에서 재요 (검사만 추가)
        no_hscroll(page, width)
        R.collect(page)
        open_co(V191B_SPLIT)
        co_open_tab(page, V191B_SPLIT, "div", "kr")
        assert page.locator('[data-ui-v2="co-dps"]').count() == 1 and page.locator('[data-ui-v2="co-dps-adj"]').count() == 0
        # 2024 · 2023 막대는 5:1 분할 전의 배당을 다시 계산한 값 (dpsF [1, 5, 5]) → 막대 밑 안내 (PR #68 2022/bars)
        assert page.locator('[data-ui-v2="co-bars-adj"]').inner_text() == fillp(CO["div"]["barsAdjNote"], years="2023·2024")
        open_co(V191B_CUT)                                                  # 다시 계산한 막대가 없으면 안내도 없어요
        co_open_tab(page, V191B_CUT, "div", "kr")
        assert page.locator('[data-ui-v2="co-div"] [data-ui-v2="bars"]').count() == 1 and page.locator('[data-ui-v2="co-bars-adj"]').count() == 0
        R.collect(page)
        # 보험사(s insure): 금융회사 밑 줄 (PR #68 B7)
        open_co(V191B_FIN)
        page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")
        sub = page.locator('[data-ui-v2="co-warn-sub"]')
        assert sub.get_attribute("data-sub") == "fin" and sub.inner_text() == CO["warn"]["noneSubFin"], sub.inner_text()
        no_hscroll(page, width)
        R.collect(page)
        # 삼성전자: 베타 범위 + 그 밑 줄 · 재무 경고 없음
        open_co("005930")
        s = by["005930"]
        lo, hi = (f"{round((s['beta'] + k * 2 * s['betaSE']) * 10) / 10:.1f}" for k in (-1, 1))
        assert tile("005930", "risk")[2] == fillp(T["riskBand"]["kr"], lo=lo, hi=hi)
        page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")
        co_open_tab(page, "005930", "value", "kr")
        rk = page.locator('[data-ui-v2="co-risk"]')
        assert rk.locator('[data-ui-v2="co-risk-band"]').inner_text() == fillp(CO["risk"]["band"]["kr"], lo=lo, hi=hi)
        assert CO["risk"]["bandNote"] in rk.inner_text()
        no_hscroll(page, width)
        R.collect(page)
        # 미국: S&P 500 과 비교한 범위
        open_co("AAPL")
        s = by["AAPL"]
        lo, hi = (f"{round((s['beta'] + k * 2 * s['betaSE']) * 10) / 10:.1f}" for k in (-1, 1))
        assert tile("AAPL", "risk")[2] == fillp(T["riskBand"]["us"], lo=lo, hi=hi)
        co_open_tab(page, "AAPL", "value", "us")
        assert page.locator('[data-ui-v2="co-risk-band"]').inner_text() == fillp(CO["risk"]["band"]["us"], lo=lo, hi=hi)
        floor_ok(page, "회사 출렁임 범위 (미국)")                     # v19.3b 12px 바닥: #68 의 새 줄도 화면에서 재요 (검사만 추가)
        no_mascot(page)
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "회사: 분할 뒤 배당은 오늘 기준으로 늘린 기록 · 진짜 삭감 · 비교 불가 · 알 수 없음 · 베타 범위(한 숫자 · 자료 없음) · 재무 경고 '없어요'", company)
    ctx.close()
    srv.shutdown()

    pf = plan_files(f)                                                          # 보고서 수익률만 바꿔요 (dyt 는 그대로)
    srv, ctx, page, _ = R.open(build_site(pf), width)

    def plan():
        rows = to_plan_v191b(page)
        assert rows, rows
        y = page.locator('[data-ui-v2="plan-summary"] [data-ui-v2="y2022"]')
        assert y.get_attribute("data-band") == "range", y.get_attribute("data-band")
        big = y.locator('[data-ui-v2="big-number"]').inner_text().replace("\n", "")
        # Jack, PR #68: 빼기 없이 하락 폭으로, 작은 하락 먼저 ("약 {small}~{big}만원 줄어들 수 있어요")
        m = re.fullmatch(r"약 ([\d,]+)~([\d,]+)만원 줄어들 수 있어요", big)
        assert m and int(m.group(1).replace(",", "")) < int(m.group(2).replace(",", "")), big
        assert big == fillp(C["plan"]["y2022MayRange"], small=m.group(1), big=m.group(2)) and "−" not in y.inner_text()
        assert y.locator('[data-ui-v2="y2022-range-note"]').inner_text() == C["plan"]["y2022Range"]
        # PR #68 B5: 범위 밑에서는 '…어림한 범위예요' ('값이에요' 아님)
        assert y.locator('[data-ui-v2="y2022-note"]').inner_text() == C["plan"]["y2022NoteRange"]
        assert C["plan"]["y2022Note"] not in y.inner_text()
        floor_ok(page, "매수 계획 2022 범위")                     # v19.3b 12px 바닥: #68 의 새 줄도 화면에서 재요 (검사만 추가)
        # 내 투자 규칙: 분할을 확인한 기록이 있는 한국 배당 종목은 배당 삭감 규칙을 점검해요 (준비 중이 아니에요)
        rules = page.locator('[data-ui-v2="rules"] [data-ui="collapsible"]')
        for i in range(rules.count()):
            rules.nth(i).locator("button").first.click()
        book = page.locator("[data-rules-for]")
        book.first.wait_for(state="visible")
        payers = [t for t, n in rows if n > 0 and by.get(t, {}).get("cls") == "kr" and (by[t].get("dps") or 0) > 0 and by[t].get("divSt") in ("same", "adj")]
        if payers:
            checked = book.locator('[data-ui-v2="rule-line"][data-check="checked"]', has_text=C["plan"]["rules"]["divLimit"])
            assert checked.count() >= len(payers), ("\n".join(book.all_inner_texts()), payers)
        # PR #68 B4: 사기 전에 이미 줄어든 배당의 안내는 특별배당만 물어요 (분할은 이미 확인했어요)
        txt = "\n".join(book.all_inner_texts())
        assert C["pick"]["caution"]["divDropBody"] not in page.locator("body").inner_text()
        if "배당이 줄었어요" in txt:
            assert C["pick"]["caution"]["divDropBodyExact"] in txt, txt
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "매수 계획: 2022년은 하락 폭 범위(작은 하락 먼저, 만원, 빼기 없음) + '…어림한 범위예요' · '범위는 베타를 …' 줄 · 배당 삭감 규칙 · 특별배당 안내", plan)
    ctx.close()
    srv.shutdown()

    # 2022년 범위가 너무 넓어요: 모든 베타 0.8 ± 2 × 0.5 → 작은 쪽 끝이 오히려 올라요 → 숫자 대신 '오차가 너무 커서 추정하지 않았어요.'
    wf = plan_files(v191b_files(co_files(files), se=0.5, beta=0.8))
    srv, ctx, page, _ = R.open(build_site(wf), width)

    def wide():
        wait_ready(page)
        start_build(page)
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        w4 = page.locator('[data-ui-v2="y2022-methods"] [data-ui-v2="y2022-wide"]')
        w4.wait_for(state="visible")
        assert w4.inner_text() == C["plan"]["y2022Wide"]
        assert page.locator('[data-ui-v2="y2022-methods"] [data-method]').count() == 0      # 방법별 숫자 없음
        no_hscroll(page, width)
        R.collect(page)
        click_next(page)
        see(page, C["pick"]["title"])
        click_next(page)
        see(page, C["plan"]["stocks"])
        y = page.locator('[data-ui-v2="plan-summary"] [data-ui-v2="y2022"]')
        y.wait_for(state="visible")
        assert y.get_attribute("data-band") == "wide"
        assert y.locator('[data-ui-v2="y2022-wide"]').inner_text() == C["plan"]["y2022Wide"]
        assert y.locator('[data-ui-v2="big-number"]').count() == 0 and C["plan"]["y2022Range"] not in y.inner_text()
        floor_ok(page, "매수 계획 2022 (추정하지 않음)")                     # v19.3b 12px 바닥: #68 의 새 줄도 화면에서 재요 (검사만 추가)
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "2022년 범위의 작은 쪽이 하락이 아니면: 덱 짜기 · 매수 계획 모두 '오차가 너무 커서 추정하지 않았어요.' (숫자 없음)", wide)
    ctx.close()
    srv.shutdown()

    # 덱 짜기 4단계: 방법 셋 모두 범위 + 설명 줄, 좁은 칸에서도 금액 가운데서 줄이 바뀌지 않아요 (가로 스크롤 없음)
    srv, ctx, page, _ = R.open(build_site(pf), width)

    def step4():
        wait_ready(page)
        start_build(page)
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        box = page.locator('[data-ui-v2="y2022-methods"]')
        box.locator('[data-method]').first.wait_for(state="visible")
        cells = box.locator('[data-method]')
        assert cells.count() == 3
        for i in range(3):
            txt = cells.nth(i).inner_text().replace("\n", "")
            m = re.fullmatch(r"([\d,]+)(?:~([\d,]+))?만원 줄어들 수 있어요", txt)       # PR #68: 하락 폭, 빼기 없음, 좁은 칸은 '약' 없이
            assert m and (m.group(2) is None or int(m.group(1).replace(",", "")) < int(m.group(2).replace(",", ""))), txt
            assert cells.nth(i).evaluate("(e) => e.scrollWidth <= e.clientWidth"), txt           # 칸 밖으로 나가지 않아요 (낱말 가운데서 끊지 않음)
        assert box.locator('[data-ui-v2="y2022-range-note"]').inner_text() == C["plan"]["y2022Range"]
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "덱 짜기 4단계: 2022년 같은 해가 오면 = 방법마다 하락 폭 범위(빼기 없음) · 설명 줄 · 칸 밖으로 나가지 않아요", step4)
    ctx.close()
    srv.shutdown()

    # 예전 파일(divCheck 없음): 출렁임은 문장만, 숫자도 '오차 범위를 계산할 수 있을 때' 줄도 없어요
    srv, ctx, page, _ = R.open(build_site(co_files(files)), width, path="/app.html?dev=1#stocks")

    def old():
        wait_ready(page)
        open_co("005930")
        assert tile("005930", "risk")[2] is None
        co_open_tab(page, "005930", "value", "kr")
        rk = page.locator('[data-ui-v2="co-risk"]')
        assert rk.count() == 1 and rk.locator('[data-ui-v2="co-risk-band"]').count() == 0
        assert rk.inner_text().strip() == CO["risk"][rk.get_attribute("data-rule")], rk.inner_text()
        assert "오차 범위" not in page.locator("body").inner_text()
        R.collect(page)
    R.check(page, S, "예전 파일: 출렁임은 문장만 (베타 숫자 · 범위 없음, 예전의 '오차 범위를 …' 줄 없음)", old)
    ctx.close()
    srv.shutdown()


# ── v19.1c: 미국 종목의 자기 가격 날짜(pxd) · 늦음 경고 시각(staleAfter) (Jack, 2026-11-07) ──
# 시험용 데이터(10월 30일 기준)에서 미국 종목 몇 개의 마지막 종가를 앞선 날로 놓아요 (d1 없음 · pxd = 그 날짜, 파이프라인 PR 과 같은 모양).
# 장기 우량주 · 1,000만원으로 고르면 NVDA · MA 를 사요 (후보 NVDA · MA · SKHY · MU, 상위 3종목에 NVDA). SKHY · TSLA 는 기준일 종가.
OWN_PXD = {"NVDA": "2026-10-28", "MA": "2026-10-29", "MU": "2026-10-29", "AAPL": "2026-10-29"}


def own_files(files):
    f = clone(files)
    by = {x["t"]: x for x in f["data.json"]["stocks"]}
    for t, d in OWN_PXD.items():
        assert by[t]["cls"] == "us" and d < f["data.json"]["usPxDate"], t
        by[t]["pxd"] = d
        by[t]["d1"] = -9.0          # 다른 날의 변화가 끼어 있어도 앱은 읽지 않아요 (engine.todayD1): 화면에 % 도 큰 움직임도 없어요
    by["TSLA"]["d1"] = 0.4
    return f


def own_text(ts):
    """화면 순서의 티커들 → 승인 문장 (날짜마다 한 문장, 새 날짜 먼저, 같은 티커는 한 번). 자기 날짜가 없으면 None."""
    groups, seen = {}, set()
    for t in ts:
        if t in OWN_PXD and t not in seen:
            seen.add(t)
            groups.setdefault(OWN_PXD[t], []).append(t)
    md = lambda d: f"{int(d[5:7])}월 {int(d[8:10])}일"
    out = [fillp(C["app"]["ownClose"], names=", ".join(groups[d]), md=md(d)) for d in sorted(groups, reverse=True)]
    return " ".join(out) or None


def own_note(loc, ts, what):
    """loc 안의 안내: 보이는 티커(ts)에 자기 날짜가 있으면 그 문장 하나, 없으면 안내 없음."""
    want = own_text(ts)
    note = loc.locator('[data-ui-v2="own-close"]')
    if want is None:
        assert note.count() == 0, (what, note.all_inner_texts())
    else:
        assert note.count() == 1 and note.inner_text() == want, (what, ts, note.all_inner_texts(), want)
    return want


def scene_own_dates(R, files, width):
    """미국 종목이 앞선 종가(pxd)일 때: 가격은 그대로 보이고 회사 페이지에는 그 종목의 날짜('미국 10월 28일 종가'), 그 종목이 들어간
    목록·합계에는 '{티커} 가격은 {날짜} 종가예요.' 한 줄 — 덱 짜기 상위 3종목 · 후보 고르기 · 매수 계획 · 샀어요(미국 줄 밑 '미국 {날짜} 종가') ·
    홈 포트폴리오 카드 · 포트폴리오 합계 · 추가로 넣을 돈 · 종목(내 포트폴리오 종목 · 종목 순위 미국) · 홈 첫 방문의 종목 순위 미국 (v19.5b).
    다른 날의 변화(d1)는 보이지 않아요 (%, 큰 움직임 없음)."""
    S = f"미국 자기 날짜 {width}"
    f = own_files(files)
    srv, ctx, page, _ = R.open(build_site(f), width)
    have = {"done": False}

    def first_visit_and_build():
        wait_ready(page)
        rank = page.locator('[data-ui-v2="rank"]')                            # 홈 첫 방문 (v19.5b): 종목 순위 — 한국은 안내 없음, 미국은 그 목록 밑에
        rank.wait_for(state="visible")
        assert page.locator('[data-ui-v2="own-close"]').count() == 0
        rank_market(page, "us")
        assert own_note(rank, rank_ts(page), "홈 첫 방문 · 종목 순위 미국")
        for t in OWN_PXD:
            for row in rank.locator(f'[data-ui-v2="rank-row"][data-t="{t}"]').all():
                assert row.locator('[data-ui-v2="rank-change"]').count() == 0 and "%" not in row.inner_text(), (t, row.inner_text())
        rank_market(page, "kr")
        assert page.locator('[data-ui-v2="own-close"]').count() == 0
        start_build(page)
        page.locator('[data-deck="quality"]').click()
        see(page, C["build"]["s1"]["title"])
        prev = page.locator('[data-ui-v2="preview"]')
        prev.wait_for(state="visible")
        shown = prev.locator("[data-preview]").evaluate_all("(els) => els.map((e) => e.dataset.preview)")
        assert "NVDA" in shown, shown
        own_note(prev, shown, "상위 3종목")
        R.collect(page)
        no_hscroll(page, width)
        click_next(page)
        click_next(page)
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        cands = page.locator("[data-cand]").evaluate_all("(els) => els.map((e) => e.dataset.cand)")
        assert {"NVDA", "MA", "MU", "SKHY"} <= set(cands), cands
        want = own_note(page.locator('[data-ui-v2="screen"]'), cands, "후보 고르기")
        assert want == "MA, MU 가격은 10월 29일 종가예요. NVDA 가격은 10월 28일 종가예요.", want      # Jack 의 예와 같은 꼴
        assert "10월 30일" in date_line(page)                                     # 날짜 줄은 그대로 기준일
        R.collect(page)
        no_hscroll(page, width)
        click_next(page)
        see(page, C["plan"]["stocks"])
        rows = page.locator("[data-row]").evaluate_all("(els) => els.map((e) => e.dataset.row)")
        assert "NVDA" in rows and "MA" in rows, rows
        own_note(page.locator('[data-ui-v2="plan-rows"]'), rows, "매수 계획")
        R.collect(page)
        no_hscroll(page, width)
        action(page).click()                                                     # 샀어요: 미국 줄 밑에 그 줄의 날짜
        see(page, C["plan"]["sheetTitle"])
        sheet = page.locator('[data-ui-v2="record-form"]')
        for t in sheet.locator("[data-record]").evaluate_all("(els) => els.map((e) => e.dataset.record)"):
            line = sheet.locator(f'[data-record="{t}"] [data-ui-v2="record-close"]')
            if t in OWN_PXD:
                d = OWN_PXD[t]
                assert line.inner_text() == fillp(C["co"]["usClose"], md=f"{int(d[5:7])}월 {int(d[8:10])}일"), (t, line.all_inner_texts())
            else:                                                                # 한국 줄 · 기준일 종가의 미국 줄(기준일 = 한국 날짜): 없음
                assert line.count() == 0, (t, line.all_inner_texts())
        R.collect(page)
        page.get_by_role("button", name=C["plan"]["save"]).click()
        see(page, C["plan"]["done"])
        page.get_by_role("button", name=DONE_LINK).click()
        at(page, "home")
        have["done"] = True
    R.check(page, S, "덱 짜기 상위 3종목 · 후보 고르기 · 매수 계획에 '{티커} 가격은 {날짜} 종가예요.' · 샀어요의 미국 줄 밑 '미국 {날짜} 종가' · 홈 첫 방문(이름만)에는 없음", first_visit_and_build)

    def home_and_portfolio():
        assert have["done"], "앞 단계(샀어요)가 끝나지 않았어요"
        strip = page.locator('[data-ui-v2="home-block"]')
        strip.wait_for(state="visible")
        held = strip.locator("[data-home-holding]").evaluate_all("(els) => els.map((e) => e.dataset.homeHolding)")
        assert "NVDA" in held and "MA" in held, held
        own_note(strip, held, "홈 포트폴리오 카드")
        for t in ("NVDA", "MA"):                                                 # 다른 날의 변화는 보이지 않아요 (v19.3e: 줄의 % 는 비중이에요)
            assert strip.locator(f'[data-home-holding="{t}"] [data-ui-v2="home-change"]').inner_text().strip() == "", t
        assert page.locator('[data-ui-v2="big-moves"], [data-big-move]').count() == 0
        R.collect(page)
        no_hscroll(page, width)
        tab(page, TABS["portfolio"])
        at(page, "portfolio")
        card = page.locator("[data-deck-id]").first
        card.locator('[data-ui-v2="deck-summary"]').wait_for(state="visible")
        rows = card.locator("[data-holding]").evaluate_all("(els) => els.map((e) => e.dataset.holding)")
        own_note(card, rows, "포트폴리오 합계")
        note = card.locator('[data-ui-v2="own-close"]')
        assert note.bounding_box()["y"] < card.locator("[data-holding]").first.bounding_box()["y"], "안내가 합계 옆(종목 줄 위)에 있어야 해요"
        add = card.locator('[data-ui-v2="add-money"]')
        add.get_by_role("button", name="+1,000만").first.click()                 # 추가로 넣을 돈: 사는 종목에 앞선 종가 종목이 있으면 그 밑에
        add.locator("[data-add]").first.wait_for(state="visible")
        buys = add.locator("[data-add]").evaluate_all("(els) => els.map((e) => e.dataset.add)")
        own_note(add, buys, "추가로 넣을 돈")
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, S, "홈 포트폴리오 카드 · 포트폴리오 합계(종목 줄 위) · 추가로 넣을 돈에 같은 안내 · 그 종목 줄에 % 없음 · 큰 움직임 없음", home_and_portfolio)

    def stocks_and_company():
        tab(page, TABS["stocks"])
        at(page, "stocks")
        mine = page.locator('[data-ui-v2="my-stocks"]')
        mine.wait_for(state="visible")
        ts = mine.locator('[data-ui-v2="stock-row"]').evaluate_all("(els) => els.map((e) => e.dataset.t)")
        want = own_text(ts)
        assert want and "NVDA" in want, (ts, want)
        got = page.locator('[data-ui-v2="own-close"]:not([data-market])').all_inner_texts()      # 날짜 줄 밑 한 줄 (거래대금 목록은 따로)
        assert got == [want], (got, want)
        rank = page.locator('[data-ui-v2="rank"]')                       # v19.5b: 종목 순위 · 미국 (거래대금 상위 미국 대신)
        rank_market(page, "us")
        own_note(rank, rank_ts(page), "종목 순위 · 미국")
        for t in OWN_PXD:
            for row in page.locator(f'[data-ui-v2="stock-row"][data-t="{t}"], [data-ui-v2="rank-row"][data-t="{t}"]').all():
                assert "%" not in row.inner_text(), (t, row.inner_text())
        rank_market(page, "kr")
        box = page.locator('[data-ui-v2="stock-search"] input')
        box.fill("삼성")                                                          # 한국 종목만: 안내 없음
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"]').first.wait_for(state="visible")
        assert page.locator('[data-ui-v2="own-close"]:not([data-market])').count() == 0
        box.fill("NVDA")
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-t="NVDA"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="own-close"]:not([data-market])').all_inner_texts() == ["NVDA 가격은 10월 28일 종가예요."]
        R.collect(page)
        no_hscroll(page, width)
        page.locator('[data-ui-v2="search-results"] [data-ui-v2="stock-row"][data-t="NVDA"] button').click()      # 회사 페이지: 그 종목의 날짜
        page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-head\"]'); return !!e && e.dataset.t === 'NVDA'; }")
        head = page.locator('[data-ui-v2="co-head"]')
        assert head.locator('[data-ui-v2="co-date"]').inner_text() == fillp(C["co"]["usCloseTime"], date="10월 28일"), head.inner_text()
        assert head.locator('[data-ui-v2="co-change"]').count() == 0 and "−9.0%" not in head.inner_text()
        assert "$" in head.locator('[data-ui-v2="co-price"]').inner_text()        # 가격은 숨기지 않아요
        src = page.locator('[data-ui-v2="co-tiles-source"]')
        if src.count():
            assert "10월 28일" in src.inner_text() and "10월 30일" not in src.inner_text(), src.inner_text()
        assert page.locator('[data-ui-v2="co-move"]').count() == 0
        R.collect(page)
        co_open_tab(page, "NVDA", "value", "us")                                 # 가치 탭의 날짜 줄도 그 종목의 날짜
        dl = page.locator('[data-ui-v2="company"] [data-ui-v2="date-line"]').first
        assert dl.inner_text().startswith(fillp(C["app"]["asOf"], md="10월 28일")) and "10월 30일" not in dl.inner_text(), dl.inner_text()
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, S, "종목: 내 포트폴리오 종목 · 거래대금 상위 미국 · 찾기 결과에 안내 (한국만이면 없음) · 회사 페이지 '미국 10월 28일 종가' · 날짜 줄 10월 28일 · % 없음", stocks_and_company)
    ctx.close()
    srv.shutdown()

    # 홈 '오늘 확인할 일': 앞선 종가 종목(NVDA)과 기준일 종가 종목(MSFT)이 둘 다 ROE 자료가 비어 확인 필요 → 띠 안에 NVDA 만 이름이 나와요
    g = own_files(files)
    gby = {x["t"]: x for x in g["data.json"]["stocks"]}
    fx = g["data.json"]["fx"]
    for t in ("NVDA", "MSFT"):
        gby[t].pop("roe", None)
    roe = lambda: {"id": "roeFloor", "kind": "keep", "check": "checked", "input": "roe", "baseline": 20.0, "since": None, "roe": 20.0, "floor": 10, "fy": None}
    rows = [("005930", "삼성전자", "kr", 0.4, 2, "KRW"), ("NVDA", gby["NVDA"]["nk"], "us", 0.3, 3, "USD"), ("MSFT", gby["MSFT"]["nk"], "us", 0.3, 1, "USD")]
    hold = [{**_holding(t, nk, tg, [] if cls == "kr" else [roe()]), "cls": cls, "plannedQty": q} for t, nk, cls, tg, q, _ in rows]
    buys = [{"t": t, "date": "2026-10-01", "qty": q, "price": round(gby[t]["price"] * 0.95, 2), "ccy": c, **({"fx": fx} if c == "USD" else {})}
            for t, _, _, _, q, c in rows]
    store = {"v": 1, "decks": [{"id": "dtodo", "name": "미국 확인 포트폴리오", "createdAt": "2026-10-01", "holdings": hold, "purchases": buys, "planFx": fx}]}
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(g), width, init=init)

    def todo_note():
        hero = page.locator('[data-ui-v2="today-hero"]')
        hero.wait_for(state="visible")
        assert hero.get_attribute("data-state") == "todo", hero.inner_text()
        items = hero.locator('[data-ui-v2="todo-item"]').evaluate_all("(els) => els.map((e) => e.dataset.t)")
        assert set(items) == {"NVDA", "MSFT"}, items
        note = hero.locator('[data-ui-v2="own-close"][data-scope="todo"]')
        assert note.count() == 1 and note.inner_text() == "NVDA 가격은 10월 28일 종가예요.", note.all_inner_texts()   # MSFT 는 기준일 종가라 빠져요
        strip = page.locator('[data-ui-v2="home-money"] [data-ui-v2="own-close"]')
        assert strip.all_inner_texts() == ["NVDA 가격은 10월 28일 종가예요."], strip.all_inner_texts()
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, S, "홈 '오늘 확인할 일': 앞선 종가 종목이 든 항목이면 띠 안에 그 종목만 '… 가격은 10월 28일 종가예요.' (기준일 종가 종목은 이름 없음)", todo_note)
    ctx.close()
    srv.shutdown()


# ── v19.3b (docs/tasks/v19.3-portfolio-pictures-accounts.md Part A · B · N.2) ──
with open(os.path.join(ROOT, "src", "v2", "pictures.js"), encoding="utf-8") as _f:
    _PICS_SRC = _f.read()
PICS = {grp: dict(re.findall(r'(\w+): \{ src: "(pictures/[\w-]+\.webp)"', _PICS_SRC.split(f"export const {grp} = {{", 1)[1].split("};", 1)[0]))
        for grp in ("CARD_PICS", "DECK_PICS")}
assert len(PICS["CARD_PICS"]) == 10 and len(PICS["DECK_PICS"]) == 8, PICS
PIC_STATE = r"""(sel) => [...document.querySelectorAll(sel)].map((c) => { const i = c.querySelector('img'); const r = i ? i.getBoundingClientRect() : null;
  return { id: c.dataset.cardPic || c.dataset.deckPic, dim: c.dataset.dim || '', src: i ? i.getAttribute('src') : '', alt: i ? i.getAttribute('alt') : null,
    ok: !!i && i.complete && i.naturalWidth > 0, w: r ? Math.round(r.width) : 0, bg: getComputedStyle(c).backgroundColor }; })"""


def pics(page, sel, table):
    """sel 의 그림 칩마다: 그 기준 · 템플릿의 그림 · 열림 · alt "" (이름 옆의 장식) · 주제 색 칩. 돌려줌: 칩 목록."""
    try:
        page.wait_for_function("(sel) => [...document.querySelectorAll(sel + ' img')].every((i) => i.complete)", arg=sel, timeout=5000)
    except PWTimeout:
        pass
    got = page.evaluate(PIC_STATE, sel)
    assert got, f"그림이 없어요: {sel}"
    for g in got:
        assert g["src"] == PICS[table][g["id"]] and g["ok"] and g["alt"] == "" and g["w"] >= 20, g
        assert g["bg"] != "rgba(0, 0, 0, 0)", g
    return got


def floor_ok(page, where):
    small = text_floor(page)
    assert not small, f"{where}: 12px 아래 글 {small[:5]}"


def scene_v193b(R, files, width):
    """v19.3b: 홈 · 포트폴리오 · 회사 페이지 · 시장 · 포트폴리오 만들기(시작 · 기준 · 빼기 · 조건 · 후보 고르기)에서 12px 아래 글이 없어요
    (Part B, 휴대폰 390 · PC 1280). 기준이 나오는 곳마다 그 기준의 그림이 주제 색 칩 위에 있어요: 기준 카드 열 장(준비 중인 두 장은
    흐리게) · 미리 보기 · 후보의 점수 줄과 근거 수치 · 회사 페이지의 내 기준과 맞는 정도와 그 시트. 템플릿 여덟 개도 자기 그림 (Part A)."""
    S = f"v19.3b {width}"
    wide = width >= 1024
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, base = R.open(build_site(daily_files(files)), width, init=init, device=pc_device(width) if wide else None)

    def go(h, r):
        page.goto(base + "/app.html?dev=1" + h, wait_until="domcontentloaded")
        if not r.startswith("stocks/"):                                          # 회사 페이지는 날짜 줄 대신 자기 날짜 (co_wait)
            wait_ready(page)
        at(page, r)

    def tabs():
        for h, r, sel in (("#home", "home", '[data-ui-v2="date-line"]'), ("#portfolio", "portfolio", "[data-holding][data-status]"),
                          ("#market", "market", '[data-ui-v2="date-line"]')):
            go(h, r)
            page.locator(sel).first.wait_for(state="visible")
            floor_ok(page, r)
            R.collect(page)
    R.check(page, S, "홈 · 포트폴리오(저장된 포트폴리오) · 시장: 12px 아래 글 없음", tabs)

    def company():
        go("#stocks/005930", "stocks/005930")
        co_wait(page)
        fit = page.locator('[data-ui-v2="co-fit"]')
        fit.wait_for(state="visible")
        rows = fit.locator('[data-ui-v2="rank-row"]')
        got = pics(page, '[data-ui-v2="co-fit"] [data-ui-v2="rank-row"] [data-card-pic]', "CARD_PICS")
        assert [g["id"] for g in got] == [rows.nth(i).get_attribute("data-card") for i in range(rows.count())], got
        floor_ok(page, "회사 요약")
        R.collect(page)
        fit.get_by_role("button", name=C["co"]["fit"]["all"]).click()            # 기준 카드 8개 모두 보기 (시트)
        sheet = page.locator('[data-ui-v2="co-fit-sheet"]')
        sheet.wait_for(state="visible")
        got = pics(page, '[data-ui-v2="co-fit-sheet"] [data-ui-v2="rank-row"] [data-card-pic]', "CARD_PICS")
        assert len(got) == sheet.locator('[data-ui-v2="rank-row"]').count() >= 6, got
        floor_ok(page, "회사 시트")
        R.collect(page)
        page.keyboard.press("Escape")
        sheet.wait_for(state="detached")
        for tab_ in ("earn", "value", "div", "disc"):                             # 회사 페이지의 탭마다
            co_hash(page, f"#stocks/005930/{tab_}")
            page.wait_for_timeout(200)
            floor_ok(page, f"회사 {tab_}")
            R.collect(page)
    R.check(page, S, "회사 페이지(삼성전자 요약 · 시트 · 네 탭): 12px 아래 글 없음 · 내 기준과 맞는 정도의 줄마다 그 기준의 그림", company)

    def build():
        go("#portfolio/build", "portfolio/build")
        see(page, C["build"]["s0"]["title"])
        got = pics(page, "[data-deck] [data-deck-pic]", "DECK_PICS")
        assert sorted(g["id"] for g in got) == sorted(PICS["DECK_PICS"]), got        # 보이는 템플릿 여덟 개 모두 자기 그림
        assert page.locator('[data-deck="blank"] img').count() == 0
        floor_ok(page, "시작")
        R.collect(page)
        page.locator('[data-deck="garp"]').click()
        see(page, C["build"]["s1"]["title"])
        got = pics(page, "[data-card] [data-card-pic]", "CARD_PICS")
        assert [g["id"] for g in got] == list(PICS["CARD_PICS"]), got             # 기준 카드 열 장, 엔진 순서 그대로
        assert {g["id"] for g in got if g["dim"]} == {"divGrowth", "payout"}, got   # 준비 중인 두 장만 흐리게
        see(page, C["build"]["s1"]["preview"])
        prev = pics(page, '[data-ui-v2="preview"] [data-card-pic]', "CARD_PICS")
        assert prev and {g["id"] for g in prev} <= {"growth", "value", "profit"}, prev   # 미리 보기: 점수를 준 기준만
        floor_ok(page, "기준")
        R.collect(page)
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        floor_ok(page, "빼기")
        R.collect(page)
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        page.locator('[data-ui-v2="y2022-methods"]').get_by_text("약 ").first.wait_for(state="visible")
        floor_ok(page, "조건")
        R.collect(page)
        click_next(page)
        see(page, C["pick"]["title"])
        got = pics(page, '[data-cand] [data-ui-v2="card-scores"] [data-card-pic]', "CARD_PICS")
        assert {g["id"] for g in got} <= {"growth", "value", "profit"}, got
        first = page.locator("[data-cand]").first
        first.get_by_role("button", name=C["pick"]["receipts"]).click()
        rec = pics(page, '[data-ui-v2="receipts"] [data-card-pic]', "CARD_PICS")
        assert {g["id"] for g in rec} == {"growth", "value", "profit"}, rec          # 근거 수치: 점수를 준 기준 세 줄
        floor_ok(page, "후보 고르기")
        R.collect(page)
    R.check(page, S, "포트폴리오 만들기(시작 · 기준 · 빼기 · 조건 · 후보 고르기): 12px 아래 글 없음 · 템플릿 여덟 개와 기준 카드 열 장마다 "
            "그림(준비 중 두 장은 흐리게) · 미리 보기 · 후보 · 근거 수치의 기준 그림", build)
    ctx.close()
    srv.shutdown()


def stale_files(files, hours_ago, after_hours, due_days_ago=0, due_at=None):
    """발행 hours_ago 시간 전 · staleAfter 는 지금에서 after_hours 시간 뒤(음수면 이미 지남). 매일 점검 덱과 같이 써요.
    nextPub(발행 예정일) = 오늘(한국)에서 due_days_ago 일 전 — 늦음 경고의 n 은 그 아침부터 세요 (Jack, 2026-11-07). due_at: 그 시각의
    한국 날짜 (시계를 돌리는 장면: 경고를 읽는 때보다 조금 뒤의 시각을 줘요 — 그 날짜라서 자정을 넘겨도 n = 1)."""
    f = daily_files(files)
    now = now_dt()
    for n in DATA_FILES:
        f[n]["publishedAt"] = (now - dt.timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    f["data.json"]["nextPub"] = due_at.date().isoformat() if due_at else (now.date() - dt.timedelta(days=due_days_ago)).isoformat()
    f["data.json"]["staleAfter"] = (now + dt.timedelta(hours=after_hours)).isoformat(timespec="seconds")
    return f


def scene_stale_after(R, files, width):
    """staleAfter (v19.1c): 지나면 경고 — 발행 뒤 하루 이내(n ≤ 1)면 날짜 줄 '갱신이 늦어지고 있어요' · 홈 띠와 포트폴리오 줄은 today.staleLate,
    2일째부터 예전 그대로 '{n}일째 갱신이 멈췄어요' · '데이터가 {n}일째 …'. 아직 지나지 않았으면 3일 전 발행이어도 조용해요 (주말·휴장일)."""
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    # n 은 예정일(nextPub) 아침부터 (Jack, 2026-11-07): n=1 은 오늘이 예정일, n=3 은 예정일이 이틀 전. '토요일 발행 → 화요일': 발행은
    # 3일 전이어도 오늘이 예정일이면 n = 1 이에요 ('3일째' 가 아니에요).
    for label, hours, after, due, n in (("n=1", 30, -1, 0, 1), ("n=3", 75, -2, 2, 3), ("주말 뒤", 75, -0.1, 0, 1), ("조용", 75, 5, 0, None)):
        srv, ctx, page, _ = R.open(build_site(stale_files(files, hours, after, due)), width, init=init)

        def run():
            wait_ready(page)
            dl = page.locator('[data-ui-v2="date-line"]').first
            dl.wait_for(state="visible")
            if n is None:                                                       # 예정 시각 전: 경고 없음, 판정 그대로
                assert dl.get_attribute("data-stale") == "0" and C["app"]["staleLate"] not in dl.inner_text() and "갱신이 멈췄어요" not in dl.inner_text(), dl.inner_text()
                page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")
                assert page.locator('[data-ui-v2="today-stale"]').count() == 0
            else:
                words = C["app"]["staleLate"] if n <= 1 else fillp(C["app"]["stale"], n=n)
                band = C["today"]["staleLate"] if n <= 1 else fillp(C["today"]["stale"], n=n)
                assert dl.get_attribute("data-stale") == "1" and dl.inner_text().endswith(" · " + words), (dl.inner_text(), words)
                assert n > 1 or "일째" not in dl.inner_text(), dl.inner_text()
                see(page, band)
                assert page.locator('[data-ui-v2="today-stale"] [data-ui="hero-band"] h2').inner_text() == band
                assert page.locator('[data-ui-v2="today-hero"], [data-ui-v2="deck-strip"]').count() == 0
                # 새 홈(v19.3e): 점검했다고 말하는 것이 하나도 없어요 — 포트폴리오 칸 · 규칙 띠 · 점검 날짜 줄 · 지킨 규칙 수 · 오늘 볼 것 ·
                # '오늘은 할 일이 없어요' · ✓ (멈춘 데이터로는 점검하지 않아요)
                for sel in ('[data-ui-v2="home-block"]', '[data-ui-v2="home-rules"]', '[data-ui-v2="home-rule"]', '[data-ui-v2="home-checked"]',
                            '[data-ui-v2="home-kept"]', '[data-ui-v2="home-money"]', '[data-ui-v2="home-held"]', '[data-ui-v2="home-look"]',
                            '[data-ui-v2="home-calm"]', '[data-ui-v2="home-conc"]', '[data-ui-v2="status-chips"]', f'[aria-label="{C["daily"]["ok"]}"]'):
                    assert page.locator(sel).count() == 0, sel
                body = page.locator("body").inner_text()
                for claim in (C["today"]["calmEyebrow"], C["today"]["calmTitle"].split("\n")[0], C["pfr"]["checked"].split("{date}")[1],
                              C["pfr"]["kept"].split("{k}")[1]):
                    assert claim not in body, claim
                tab(page, TABS["portfolio"])
                at(page, "portfolio")
                assert page.locator('[data-ui-v2="deck-stale"]').inner_text() == band
                assert page.locator("[data-holding][data-status]").count() == 0
                for key in ("stocks", "market"):
                    tab(page, TABS[key])
                    at(page, key)
                    line = page.locator('[data-ui-v2="date-line"]').first
                    assert line.get_attribute("data-stale") == "1" and line.inner_text().endswith(" · " + words), (key, line.inner_text())
            R.collect(page)
            no_hscroll(page, width)
        R.check(page, f"늦음 시각 {width}", f"{label}: " + ("staleAfter 전 → 3일 전 발행이어도 경고 없음" if n is None
                else f"staleAfter 지남 → 날짜 줄 '{C['app']['staleLate'] if n <= 1 else fillp(C['app']['stale'], n=n)}' · 홈 띠 · 포트폴리오 줄 (판정 없음)"), run)
        ctx.close()
        srv.shutdown()


def scene_stale_recheck(R, files, width):
    """열어 둔 화면 (v19.1c): 아침에 연 2.0 을 새로 고치지 않아도 staleAfter 가 지나면 날짜 줄 · 홈 띠에 늦음 경고가 떠요. 시계를 앞으로
    돌려 (Playwright clock) 타이머로 한 번, 시계만 옮기고 화면이 다시 보일 때(visibilitychange)로 한 번 봐요. 데이터는 다시 받지 않아요."""
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    for how in ("timer", "visible"):
        now = now_dt()
        # 예정일 = 경고를 읽는 때(타이머: 31분 뒤 · 화면이 다시 보일 때: 45분 뒤)보다 9분 뒤의 날짜. 2026-11-12 (Jack): 예전에는 둘 다
        # 40분 뒤의 날짜라, 23:15~23:20 에 돌면 45분 뒤는 다음 날이 되어 앱이 규칙대로 '2일째 갱신이 멈췄어요'라고 했어요 (앱이 맞고 시험이 틀림).
        # 9분의 여유: 페이지 시계는 화면이 뜨는 동안에도 흘러요 (타이머 쪽 예정일은 예전과 같은 40분 뒤 · 앱은 n 을 1 아래로 내리지 않아요).
        jump = dt.timedelta(minutes=31 if how == "timer" else 45)
        f = stale_files(files, 2, 0.5, due_at=now + jump + dt.timedelta(minutes=9))   # 발행 2시간 전 · staleAfter 30분 뒤
        srv, base = serve(build_site(f))
        ctx = R.new_context(clock=False, viewport={"width": width, "height": 780}, device_scale_factor=2, locale="ko-KR", service_workers="block")
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
        ctx.add_init_script(init)
        page = ctx.new_page()
        page.set_default_timeout(WAIT)
        page.on("pageerror", lambda e: R.errors.append(str(e)))
        page.clock.install(time=now)
        R.saw_clock(page, now)
        fetched = []
        page.on("request", lambda r: fetched.append(r.url) if r.url.endswith(".json") else None)
        page.goto(base + "/app.html?dev=1", wait_until="domcontentloaded")

        def run():
            hero = page.locator('[data-ui-v2="today-hero"]')
            hero.wait_for(state="visible")                                        # 아직은 판정 그대로, 경고 없음
            dl = page.locator('[data-ui-v2="date-line"]').first
            assert dl.get_attribute("data-stale") == "0", dl.inner_text()
            n = len(fetched)
            if how == "timer":
                page.clock.fast_forward("31:00")                                  # staleAfter 를 지나 타이머가 돌아요
            else:
                page.clock.set_system_time(now + jump)                            # 타이머는 돌지 않고 시계만
                page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
            page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"date-line\"]'); return !!e && e.dataset.stale === '1'; }")
            assert dl.inner_text().endswith(" · " + C["app"]["staleLate"]), dl.inner_text()          # 발행 2시간 뒤: n = 0 → 늦어지고 있어요
            band = page.locator('[data-ui-v2="today-stale"] [data-ui="hero-band"] h2')
            band.wait_for(state="visible")
            assert band.inner_text() == C["today"]["staleLate"] and hero.count() == 0, band.inner_text()
            assert len(fetched) == n, fetched[n:]                                  # 데이터 파일을 다시 받지 않았어요
            R.collect(page)
        R.check(page, f"열어 둔 화면 {width}", ("시계가 staleAfter 를 지나면 타이머로" if how == "timer" else "화면이 다시 보일 때(visibilitychange)")
                + " 새로 고침 없이 날짜 줄 '갱신이 늦어지고 있어요' · 홈 띠(today.staleLate) · 판정 멈춤, 데이터 다시 받지 않음", run)
        ctx.close()
        srv.shutdown()


# ── 2026-11-08 (Jack, Q9): an old page brought back into view fetches the files once (load.js refetchNewer · returnWatch) ──
# The page is hidden and shown again by hand (headless Chromium is always visible): visibilityState is shadowed on the
# document and the events are dispatched; the back-forward cache return is pagehide + pageshow(persisted).
HIDE_JS = """() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); }"""
SHOW_JS = "() => { delete document.visibilityState; delete document.hidden; document.dispatchEvent(new Event('visibilitychange')); }"
BFCACHE_JS = """() => { window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
  window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); }"""
REFETCH_PX, REFETCH_MD = "2026-11-02", "11월 2일"                      # a later close than the fixture's 10월 30일
DATA_FILE_RX = re.compile(r"/(data|corp|macro|disc)\.json$")
SCREEN_DL = '[data-ui-v2="screen"] [data-ui-v2="date-line"]'           # the screen's own date line (PC: not the left menu's)


def refetch_files(files):
    """A later publish (an hour ago, staleAfter tomorrow): every file carries its publishedAt, prices of 11월 2일."""
    f = stale_files(files, 1, 30)
    f["data.json"]["pxDate"] = REFETCH_PX
    f["corp.json"]["pxDate"] = REFETCH_PX
    f["disc.json"]["newest"] = REFETCH_PX
    return f


def put_files(site, f, names=None, raw=None):
    """Writes the files into the running site (the next request gets them)."""
    for name in names or DATA_FILES:
        with open(os.path.join(site, name), "w", encoding="utf-8") as fh:
            fh.write(raw[name] if raw and name in raw else json.dumps(f[name], ensure_ascii=False))


def scene_stale_refetch(R, files, width):
    """돌아온 화면 (Jack, 2026-11-08 Q9 "Old page brought back into view: yes, fetch once"): 멈춤 표시가 있는 화면이 다시 보이면 파일을
    한 번 받아요. 사이트에 더 새 발행이 있으면 모든 화면이 새 데이터로 (날짜 줄의 새 날짜 · 멈춤 표시와 홈 띠가 사라짐), 받지 못하거나 ·
    못 읽거나 · 발행이 섞였으면 그대로 (멈춤 표시가 남고 불러오기 실패 문구로 바뀌지 않아요 · console 에 이유). 멈춘 데이터가 아니면
    받지 않아요. 돌아올 때마다 한 번만 (다시 받지 않음 · 되풀이 없음)."""
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    wide = width >= 1024
    words3 = fillp(C["app"]["stale"], n=3)
    old_line = fillp(C["app"]["asOf"], md="10월 30일") + " · " + words3
    new_line = fillp(C["app"]["asOf"], md=REFETCH_MD)
    for how in ("newer", "bfcache", "offline", "unreadable", "mixed", "disc-retry", "disc-slow", "disc-older", "disc-older-again", "fresh",
                "failed", "failed-again"):
        if how.startswith("failed"):                             # review 2026-11-08 (5): the first load failed (data.json missing)
            scene_failed_refetch(R, files, width, how == "failed-again")
            continue
        if how in ("disc-slow", "disc-older", "disc-older-again"):   # delta review: 홈's disc.json late, or older than the new data
            scene_disc_refetch(R, files, width, how)
            continue
        if how == "bfcache":                                     # the 4-day backstop (no staleAfter), on a company's 공시 tab
            old = clone(files)
            for n in DATA_FILES:
                old[n]["publishedAt"] = now_kst(days_ago=6)
            path = "/app.html?dev=1#stocks/005930/disc"
        else:
            old = refetch_files(files) if how == "fresh" else stale_files(files, 75, -2, 2)    # n = 3: '3일째 갱신이 멈췄어요'
            path = "/app.html?dev=1"
            if how == "newer":                                   # delta review: the old disc.json's list stopped (listOk false),
                old["disc.json"]["listOk"] = False               # so 홈 would say 'stale', not 'ok', were it left on screen
        site = build_site(old, drop=("disc.json",) if how == "disc-retry" else ())     # disc-retry: 홈's disc.json fails at first
        srv, ctx, page, _ = R.open(site, width, init=init, path=path, device=pc_device(width) if wide else None)
        asked, logs = [], []
        page.on("request", lambda r: asked.append(DATA_FILE_RX.search(r.url).group(0)[1:]) if DATA_FILE_RX.search(r.url) else None)
        page.on("console", lambda m: logs.append(m.text))

        def quiet(n):
            page.wait_for_timeout(1200)
            assert len(asked) == n, asked[n:]

        def run():
            if how == "bfcache":
                ds = page.locator('[data-ui-v2="co-disc"]')
                page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-disc\"]'); return !!e && e.dataset.state === 'ok'; }")
                assert ds.get_attribute("data-stale") == "1"                                       # disc.json 6 days old
                stale_dl = page.locator('[data-ui-v2="date-line"][data-stale="1"]').first
                stale_dl.wait_for(state="visible")
                assert stale_dl.inner_text().endswith(" · " + fillp(C["app"]["stale"], n=6)), stale_dl.inner_text()
            else:
                wait_ready(page)
                at(page, "home")
                dl = page.locator(SCREEN_DL).first
                dl.wait_for(state="visible")
                if how == "fresh":
                    assert dl.get_attribute("data-stale") == "0" and dl.inner_text() == new_line, dl.inner_text()
                    page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")
                else:
                    assert dl.get_attribute("data-stale") == "1" and dl.inner_text() == old_line, dl.inner_text()
                    page.locator('[data-ui-v2="today-stale"]').wait_for(state="visible")
            R.collect(page)
            # v19.3e: 홈 loads disc.json itself (a Korean stock is held in DAILY_DECKS), after the first paint: wait for it
            page.wait_for_function("() => performance.getEntriesByType('resource').some((e) => /\\/disc\\.json$/.test(e.name))")
            page.wait_for_timeout(300)
            n0 = len(asked)
            new = refetch_files(files)
            if how == "offline":
                put_files(site, new)
                page.route("**/data.json", lambda r: r.abort())                                    # the network is gone
            elif how == "unreadable":
                text = json.dumps(new["data.json"], ensure_ascii=False)
                put_files(site, new, raw={"data.json": text[: len(text) // 2]})
            elif how == "mixed":
                put_files(site, new, names=["data.json"])                                          # corp.json · macro.json: the old publish
            else:
                put_files(site, new)
            page.evaluate(BFCACHE_JS if how == "bfcache" else HIDE_JS)
            if how != "bfcache":
                page.evaluate(SHOW_JS)
            if how == "fresh":                                                                     # not stale: nothing is fetched
                quiet(n0)
                assert page.locator(SCREEN_DL).first.get_attribute("data-stale") == "0"
                assert not [x for x in logs if "back in view" in x], logs
                return
            if how in ("newer", "bfcache", "disc-retry"):
                if how == "bfcache":
                    page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-disc\"]'); return !!e && e.dataset.stale === '0'; }")
                    ds = page.locator('[data-ui-v2="co-disc"]')
                    assert ds.locator('[data-ui-v2="date-line"]').first.inner_text() == new_line          # the new disc.json (newest 11월 2일)
                    assert page.locator('[data-ui-v2="date-line"][data-stale="1"]').count() == 0          # the company's stale line is gone
                    want = ["data.json", "corp.json", "disc.json", "macro.json"]
                else:
                    page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
                    dl = page.locator(SCREEN_DL).first
                    assert dl.inner_text() == new_line, dl.inner_text()                                  # the new date, no stale words
                    page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")                  # the 홈 band is gone: today's check runs
                    assert page.locator('[data-ui-v2="today-stale"]').count() == 0
                    # 홈's filings (v19.3e) from the same publish: newer — disc.json fetched with it (it was on screen);
                    # disc-retry — it had failed, so it loads again once the new publish is on screen. Checked, current.
                    page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"home2\"]'); return !!e && e.dataset.disc === 'ok'; }")
                    want = ["data.json", "corp.json", "macro.json", "disc.json"]
                    if how == "disc-retry":
                        wait_log(logs, "had not loaded, not from the publish of", page)
                        assert asked[n0:][-1] == "disc.json", asked[n0:]                                # after the new publish went on screen
                got = asked[n0:]
                assert got[0] == "data.json" and sorted(got) == sorted(want), got                       # each file once, data.json first
                assert any("is ready for every screen" in x and REFETCH_PX in x for x in logs), [x for x in logs if "[v2]" in x][-4:]
                assert any("now shows on every screen" in x for x in logs), [x for x in logs if "[v2]" in x][-4:]
                R.collect(page)
                n1 = len(asked)
                page.evaluate(HIDE_JS)                                                              # back again: not stale any more
                page.evaluate(SHOW_JS)
                quiet(n1)
                if how == "newer":                                                                  # every screen reads the new data
                    for key in ("stocks", "market", "portfolio"):
                        if wide:
                            side_tab(page, key)
                        else:
                            tab(page, TABS[key])
                            at(page, key)
                        line = page.locator(SCREEN_DL).first
                        line.wait_for(state="visible")
                        assert line.get_attribute("data-stale") == "0" and line.inner_text() == new_line, (key, line.inner_text())
                        assert page.locator('[data-ui-v2="date-line"][data-stale="1"]').count() == 0, key
                        R.collect(page)
                no_hscroll(page, width)
                return
            # offline · unreadable · mixed: the data on screen stays, with its stale line (never the load-failure message)
            deadline = time.time() + WAIT / 1000
            while not any("kept the data on screen" in x for x in logs) and time.time() < deadline:
                page.wait_for_timeout(100)
            kept = [x for x in logs if "kept the data on screen" in x]
            reason = {"offline": "data.json: ", "unreadable": "data.json: ", "mixed": "the files are from different publishes"}[how]
            assert len(kept) == 1 and reason in kept[0], kept
            quiet(n0 + (4 if how == "mixed" else 1))                                                # one fetch for this return, no retry
            got = asked[n0:]                                                                        # mixed: 홈's disc.json too (v19.3e)
            assert sorted(got) == (["corp.json", "data.json", "disc.json", "macro.json"] if how == "mixed" else ["data.json"]), got
            dl = page.locator(SCREEN_DL).first
            assert dl.get_attribute("data-stale") == "1" and dl.inner_text() == old_line, dl.inner_text()
            band = page.locator('[data-ui-v2="today-stale"] [data-ui="hero-band"] h2')
            assert band.inner_text() == fillp(C["today"]["stale"], n=3), band.inner_text()
            assert page.locator('[data-ui-v2="load-fail"]').count() == 0 and page.locator('[data-ui-v2="today-hero"]').count() == 0
            if how == "offline":                                    # back again at once: no fetch within 10 minutes (review 2026-11-08, 2)
                n2 = len(asked)
                page.evaluate(HIDE_JS)
                page.evaluate(SHOW_JS)
                quiet(n2)
                assert any("nothing fetched; the last fetch on a return" in x for x in logs), [x for x in logs if "[v2]" in x][-3:]
            R.collect(page)
            no_hscroll(page, width)
        desc = {"newer": "더 새 발행 → 다시 보일 때 data · corp · macro · 홈의 disc 를 한 번씩 받아 모든 화면이 새 날짜(멈춤 표시 · 홈 띠 없음), 또 돌아와도 다시 받지 않음",
                "bfcache": "4일 규칙 · 공시 탭 · 뒤로 가기 캐시(pageshow)에서 돌아옴 → disc.json 도 같은 발행으로 한 번, 공시 탭 · 회사 날짜 줄이 새것",
                "offline": "받지 못함 → data.json 한 번만, 멈춤 표시 · 홈 띠 그대로 (실패 문구 아님) · console 에 이유 · 곧바로 또 돌아와도 10분 안에는 받지 않음",
                "unreadable": "못 읽는 data.json → 한 번만, 멈춤 표시 그대로 (실패 문구 아님) · console 에 이유",
                "mixed": "data.json 만 새 발행 → 넷 다 받고 아무것도 쓰지 않음 (섞이지 않음) · 멈춤 표시 그대로",
                "disc-retry": "홈의 disc.json 이 처음에 실패 → 새 발행이 들어온 뒤 한 번 더 받아 홈 공시도 새 발행 (data-disc ok)",
                "fresh": "멈춘 데이터가 아님 → 다시 보여도 받지 않음"}[how]
        R.check(page, f"돌아온 화면 {width}", f"{how}: {desc}", run)
        ctx.close()
        srv.shutdown()


def wait_log(logs, part, page):
    deadline = time.time() + WAIT / 1000
    while not any(part in x for x in logs) and time.time() < deadline:
        page.wait_for_timeout(100)
    hit = [x for x in logs if part in x]
    assert hit, (part, [x for x in logs if "[v2]" in x][-4:])
    return hit


def scene_disc_refetch(R, files, width, how):
    """돌아온 화면 · 홈의 disc.json (델타 리뷰 2026-11-08). 저장한 포트폴리오에 한국 종목이 있어 홈이 disc.json 을 직접 받아요 (v19.3e).
    disc-slow  첫 disc.json 답이 4초 늦는 사이에 새 발행이 화면에 들어와요 → 늦은 답은 쓰지 않고(console) 다시 받은 것으로 홈 공시 ok.
    disc-older 시장에서 새 발행이 들어왔는데 사이트에는 아직 예전 disc.json → 홈을 열면 실패 문구 (새 데이터 옆에 예전 공시를 두지 않아요).
               곧바로 돌아와도 다시 받지 않고, 사이트에 맞는 disc.json 이 생기고 10분이 지난 뒤 돌아오면 한 번 더 받아 홈 공시 ok · 그 뒤로는 받지 않아요.
    disc-older-again  그 한 번 더도 예전 disc.json → 실패 문구 그대로 · console '마지막' · 30분 뒤 돌아와도 세 번째는 없어요 (리뷰 4차).
    disc-slow 의 늦은 답은 정말 예전 disc.json 이에요 (목록이 멈춘 파일): 홈 공시는 ok 그대로이고 공시 탭은 새 파일의 날짜예요."""
    wide = width >= 1024
    init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(DAILY_DECKS, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    new_line = fillp(C["app"]["asOf"], md=REFETCH_MD)
    old = stale_files(files, 75, -2, 2)
    old["disc.json"]["listOk"] = False                                      # the old list stopped: 홈 would say 'stale' with it
    site = build_site(old)
    again = how == "disc-older-again"
    if how == "disc-slow":
        with open(os.path.join(site, ".delay-disc.json"), "w", encoding="utf-8") as fh:
            fh.write("4")                                                    # the first disc.json answer comes 4 s late
    srv, base = serve(site)
    screen = pc_device(width) if wide else {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2}
    ctx = R.new_context(clock=(how == "disc-slow"), **screen, locale="ko-KR", service_workers="block")   # disc-slow 만 창의 시계 (나머지는 아래에서 페이지 시계)
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else (R.outside.append(r.request.url), r.abort()))
    ctx.add_init_script(init)
    page = ctx.new_page()
    page.set_default_timeout(WAIT)
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    asked, logs = [], []
    page.on("request", lambda r: asked.append(DATA_FILE_RX.search(r.url).group(0)[1:]) if DATA_FILE_RX.search(r.url) else None)
    page.on("console", lambda m: logs.append(m.text))
    now = now_dt()
    if how != "disc-slow":
        page.clock.install(time=now)                                         # the 10 minutes are moved on by hand
    R.saw_clock(page, now)
    page.goto(base + "/app.html?dev=1" + ("" if how == "disc-slow" else "#market"), wait_until="domcontentloaded")
    home_disc = "() => { const e = document.querySelector('[data-ui-v2=\"home2\"]'); return e ? e.dataset.disc : null; }"

    def back():
        page.evaluate(HIDE_JS)
        page.evaluate(SHOW_JS)

    def slow():
        wait_ready(page)
        at(page, "home")
        deadline = time.time() + WAIT / 1000
        while "disc.json" not in asked and time.time() < deadline:            # the first disc.json request is out (held back)
            page.wait_for_timeout(50)
        assert asked.count("disc.json") == 1, asked
        put_files(site, refetch_files(files))
        back()                                                               # the new publish goes on screen before that answer
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
        assert page.locator(SCREEN_DL).first.inner_text() == new_line
        page.wait_for_function(home_disc.replace("return e ? e.dataset.disc : null;", "return !!e && e.dataset.disc === 'ok';"))
        assert asked.count("disc.json") == 2, asked                          # a second request, after the publish went on screen
        wait_log(logs, "disc.json loaded for data that is no longer on screen: not used", page)   # the late answer (about 4 s)
        page.wait_for_timeout(300)
        # the late answer was the old file (its list stopped): it never replaced the new one on screen
        assert page.evaluate(home_disc) == "ok" and asked.count("disc.json") == 2, (page.evaluate(home_disc), asked)
        R.collect(page)
        co_hash(page, "#stocks/005930/disc")
        page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-disc\"]'); return !!e && e.dataset.state === 'ok'; }")
        ds = page.locator('[data-ui-v2="co-disc"]')
        assert ds.get_attribute("data-stale") == "0" and ds.locator('[data-ui-v2="date-line"]').first.inner_text() == new_line, ds.inner_text()
        assert asked.count("disc.json") == 2, asked
        R.collect(page)
        no_hscroll(page, width)

    def older():
        dl = page.locator(SCREEN_DL).first
        dl.wait_for(state="visible")
        at(page, "market")
        assert dl.get_attribute("data-stale") == "1"
        assert "disc.json" not in asked, asked                               # 시장 does not load disc.json
        put_files(site, refetch_files(files), names=["data.json", "corp.json", "macro.json"])   # the site's disc.json: still the old one
        back()
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
        if wide:
            side_tab(page, "home")
        else:
            tab(page, TABS["home"])
            at(page, "home")
        page.wait_for_function(home_disc.replace("return e ? e.dataset.disc : null;", "return !!e && e.dataset.disc === 'fail';"))
        assert asked.count("disc.json") == 1, asked                          # loaded once, older than the data: not shown
        wait_log(logs, "older than the data on screen", page)
        page.locator('[data-ui-v2="home-disc-fail"]').wait_for(state="visible")    # the filings' failure message, never the old list
        R.collect(page)
        back()                                                               # at once: no more try yet (10 minutes)
        page.wait_for_timeout(1000)
        assert asked.count("disc.json") == 1, asked
        if not again:
            put_files(site, refetch_files(files), names=["disc.json"])      # the site serves the matching disc.json now
        page.clock.set_system_time(now + dt.timedelta(minutes=11))
        back()                                                               # 11 minutes on: one more try
        wait_log(logs, "it loads once more", page)
        if again:                                                            # still the old file: the failure message stays
            wait_log(logs, "(it was the one more try: no more)", page)
            page.wait_for_timeout(300)
            assert page.evaluate(home_disc) == "fail", page.evaluate(home_disc)
            page.locator('[data-ui-v2="home-disc-fail"]').wait_for(state="visible")
        else:
            page.wait_for_function(home_disc.replace("return e ? e.dataset.disc : null;", "return !!e && e.dataset.disc === 'ok';"))
        assert asked.count("disc.json") == 2, asked
        page.clock.set_system_time(now + dt.timedelta(minutes=30))
        back()                                                               # and no more after that
        page.wait_for_timeout(1000)
        assert asked.count("disc.json") == 2, asked                          # never a third request
        assert page.evaluate(home_disc) == ("fail" if again else "ok"), page.evaluate(home_disc)
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, f"돌아온 화면 {width}", (
        "disc-slow: 홈의 첫 disc.json 답이 늦는 사이 새 발행이 들어옴 → 늦은 답은 쓰지 않고 다시 받은 것으로 홈 공시 ok" if how == "disc-slow" else
        "disc-older-again: 한 번 더 받아도 예전 disc.json → 실패 문구 그대로 · 30분 뒤 돌아와도 세 번째 요청 없음" if again else
        "disc-older: 새 발행 뒤 사이트의 disc.json 이 예전 것 → 홈 공시는 실패 문구 · 10분 뒤 돌아오면 한 번 더 받아 ok · 그 뒤로는 받지 않음"),
        slow if how == "disc-slow" else older)
    ctx.close()
    srv.shutdown()


# Watches the page from now on: set when at some moment neither the load-failure message nor a date line is on the page
# (the loading screen, or a blank one).
GAP_JS = """() => { window.__gap = false; new MutationObserver(() => {
  if (!document.querySelector('[data-ui-v2="load-fail"], [data-ui-v2="date-line"]')) window.__gap = true; })
  .observe(document.body, { childList: true, subtree: true }); }"""


def scene_failed_refetch(R, files, width, again):
    """돌아온 화면 · 첫 불러오기 실패 (리뷰 2026-11-08, 5): 불러오기 실패 문구가 있는 화면도 다시 보이면 한 번 받아요 (data · corp · macro,
    첫 불러오기와 같은 검사). 이번에는 읽히면 실패 문구 대신 새 데이터 (불러오는 화면을 거치지 않아요), 또 실패하면 실패 문구 그대로 ·
    console 에 이유 · 곧바로 또 돌아와도 10분 안에는 받지 않아요."""
    wide = width >= 1024
    site = build_site(stale_files(files, 75, -2, 2), drop=("data.json",))
    srv, ctx, page, _ = R.open(site, width, device=pc_device(width) if wide else None)
    asked, logs = [], []
    page.on("request", lambda r: asked.append(DATA_FILE_RX.search(r.url).group(0)[1:]) if DATA_FILE_RX.search(r.url) else None)
    page.on("console", lambda m: logs.append(m.text))
    new_line = fillp(C["app"]["asOf"], md=REFETCH_MD)

    def run():
        see(page, LOAD_FAIL)
        assert page.locator(SCREEN_DL).count() == 0
        R.collect(page)
        page.evaluate(GAP_JS)
        n0 = len(asked)
        if not again:
            put_files(site, refetch_files(files))
        page.evaluate(HIDE_JS)
        page.evaluate(SHOW_JS)
        if again:                                                   # data.json still missing: the failure message stays
            wait_log(logs, "they still cannot be used", page)
            page.wait_for_timeout(1200)
            assert sorted(asked[n0:]) == ["corp.json", "data.json", "macro.json"], asked[n0:]
            assert page.locator('[data-ui-v2="load-fail"]').count() >= 1 and page.locator(SCREEN_DL).count() == 0
            n1 = len(asked)
            page.evaluate(HIDE_JS)
            page.evaluate(SHOW_JS)
            page.wait_for_timeout(1200)
            assert len(asked) == n1, asked[n1:]
            wait_log(logs, "nothing fetched; the last fetch on a return", page)
        else:
            page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
            assert page.locator(SCREEN_DL).first.inner_text() == new_line
            assert page.locator('[data-ui-v2="load-fail"]').count() == 0
            assert sorted(asked[n0:]) == ["corp.json", "data.json", "macro.json"], asked[n0:]
            assert wait_log(logs, "replaces the load-failure message", page) and wait_log(logs, "now shows on every screen", page)
            n1 = len(asked)
            page.evaluate(HIDE_JS)                                  # fresh now: nothing more
            page.evaluate(SHOW_JS)
            page.wait_for_timeout(1200)
            assert len(asked) == n1, asked[n1:]
        assert page.evaluate("() => window.__gap") is False, "the loading screen (or a blank one) showed during the fetch"
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, f"돌아온 화면 {width}", ("failed-again: 첫 불러오기 실패 → 다시 보일 때 한 번 받고 또 실패하면 실패 문구 그대로 · 10분 안에는 다시 받지 않음"
            if again else "failed: 첫 불러오기 실패 → 다시 보일 때 한 번 받아 새 데이터 (불러오는 화면 없이), 또 돌아와도 받지 않음"), run)
    ctx.close()
    srv.shutdown()


def scene_refetch_drafts(R, files, width):
    """돌아온 화면 · 만들던 것 (리뷰 2026-11-08, 1): 새 데이터는 만들던 것을 바꿀 수 있는 동안 기다려요.
    A 포트폴리오 만들기의 후보 고르기에서 새 발행에 고른 한국 후보가 없어도 화면은 그대로 (여섯 종목 모두 고른 채로 · 매수 계획도 여섯 줄 ·
      멈춤 표시 그대로 · 또 돌아와도 받지 않음). 기준 단계로 돌아가면 그때 새 데이터가 들어오고, 후보는 새 데이터로 다시 골라요 (조용히
      빠지는 종목 없음).
    C 가진 종목 넣기의 점검에서 새 발행에 넣은 종목이 없어도 점검은 그대로이고, 매일 점검 시작하기는 두 종목을 모두 저장해요. 그다음에 새
      데이터가 들어와요."""
    wide = width >= 1024
    new_line = fillp(C["app"]["asOf"], md=REFETCH_MD)

    def opened():
        site = build_site(stale_files(files, 75, -2, 2))
        srv, ctx, page, _ = R.open(site, width, device=pc_device(width) if wide else None)
        asked, logs = [], []
        page.on("request", lambda r: asked.append(DATA_FILE_RX.search(r.url).group(0)[1:]) if DATA_FILE_RX.search(r.url) else None)
        page.on("console", lambda m: logs.append(m.text))
        return site, srv, ctx, page, asked, logs

    def back_in_view(page):
        page.evaluate(HIDE_JS)
        page.evaluate(SHOW_JS)

    def stale_line(page):
        dl = page.locator(SCREEN_DL).first
        dl.wait_for(state="visible")
        return dl.get_attribute("data-stale") == "1" and dl.inner_text().startswith(fillp(C["app"]["asOf"], md="10월 30일"))

    site, srv, ctx, page, asked, logs = opened()

    def build_hold():
        wait_ready(page)
        to_build_start(page, wide)
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        picked = page.eval_on_selector_all("[data-cand][data-picked='1']", "els => els.map((e) => e.dataset.cand)")
        kr = page.eval_on_selector_all("section[data-market='kr'] [data-cand][data-picked='1']", "els => els.map((e) => e.dataset.cand)")
        assert len(picked) == 6 and kr, picked
        gone = kr[0]
        new = refetch_files(files)
        new["data.json"]["stocks"] = [s for s in new["data.json"]["stocks"] if s["t"] != gone]   # a picked candidate left data.json
        put_files(site, new)
        n0 = len(asked)
        back_in_view(page)
        wait_log(logs, "is held while the portfolio builder is on its pick step", page)
        assert sorted(asked[n0:]) == ["corp.json", "data.json", "macro.json"], asked[n0:]
        now = page.eval_on_selector_all("[data-cand][data-picked='1']", "els => els.map((e) => e.dataset.cand)")
        assert now == picked and stale_line(page), now                                # nothing changed under the draft
        n1 = len(asked)
        back_in_view(page)                                                            # held: nothing more is fetched
        page.wait_for_timeout(1000)
        assert len(asked) == n1 and wait_log(logs, "is already waiting to go on screen", page)
        click_next(page)                                                              # 매수 계획: still the six, still the old data
        see(page, C["plan"]["stocks"])
        assert page.locator("[data-row]").count() == 6 and page.locator(f'[data-row="{gone}"]').count() == 1
        assert stale_line(page)
        R.collect(page)
        page.get_by_role("button", name=C["plan"]["back"]).click()
        see(page, C["pick"]["title"])
        assert stale_line(page)
        page.get_by_role("button", name=PICK_BACK).click()                            # back to the 기준 steps: the new data comes in
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
        assert page.locator(SCREEN_DL).first.inner_text() == new_line
        wait_log(logs, "held until now, now shows on every screen", page)
        click_next(page)                                                              # the candidates again, from the new data
        see(page, C["pick"]["title"])
        again = page.eval_on_selector_all("[data-cand]", "els => els.map((e) => e.dataset.cand)")
        assert gone not in again and page.locator("[data-cand][data-picked='1']").count() == 6, (gone, again)
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, f"돌아온 화면 {width}", "A 후보 고르기에서 고른 후보가 새 발행에 없음 → 그대로 (여섯 종목 · 매수 계획 여섯 줄 · 멈춤 표시), 기준 단계로 "
            "돌아가면 새 데이터 · 후보를 새로 골라요 (조용히 빠지는 종목 없음)", build_hold)
    ctx.close()
    srv.shutdown()

    site, srv, ctx, page, asked, logs = opened()

    def import_hold():
        wait_ready(page)
        to_build_start(page, wide)
        page.locator('[data-ui-v2="start-holdings"]').click()
        at(page, "portfolio/import")
        for t, q in (("005930", "10"), ("000660", "2")):
            page.locator('[data-ui-v2="import-search"] input').fill(t)
            page.locator(f'[data-import-result="{t}"] button').click()
            row = page.locator(f'[data-import-row="{t}"]')
            row.wait_for(state="visible")
            row.locator('input[data-ui-v2="import-qty"]').fill(q)
        action(page).click()
        see(page, C["build"]["s1"]["title"])
        for c in ("value", "value", "div", "div", "stable"):
            page.locator(f'[data-card="{c}"] [data-ui-v2="card-inc"]').click()
        action(page).click()
        page.locator('[data-ui-v2="report"]').wait_for(state="visible")
        assert page.locator('[data-report-row="000660"]').count() == 1
        new = refetch_files(files)
        new["data.json"]["stocks"] = [s for s in new["data.json"]["stocks"] if s["t"] != "000660"]    # a holding left data.json
        put_files(site, new)
        n0 = len(asked)
        back_in_view(page)
        wait_log(logs, "is held while the holdings import is open", page)
        assert sorted(asked[n0:]) == ["corp.json", "data.json", "macro.json"], asked[n0:]
        assert page.locator('[data-report-row="000660"]').count() == 1                # 점검 has no date line: its stale note stays
        assert page.locator('[data-ui-v2="report-stale"]').count() == 1
        R.collect(page)
        page.locator('[data-ui-v2="report-start"]').click()                         # 매일 점검 시작하기: saved with both holdings
        at(page, "portfolio")
        held = [h["t"] for h in page.evaluate(STORED_JS)["decks"][-1]["holdings"]]
        assert sorted(held) == ["000660", "005930"], held
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
        assert page.locator(SCREEN_DL).first.inner_text() == new_line                 # then the new data comes in
        wait_log(logs, "held until now, now shows on every screen", page)
        R.collect(page)
        no_hscroll(page, width)
    R.check(page, f"돌아온 화면 {width}", "C 가진 종목 넣기 점검에서 넣은 종목이 새 발행에 없음 → 점검 그대로 · 매일 점검 시작하기는 두 종목 모두 저장 · "
            "그다음 새 데이터", import_hold)
    ctx.close()
    srv.shutdown()


# ── say-why, second round (Jack, 2026-11-08; tests/test_say_why_2.py has the unit tests) ──
# 1 새 데이터가 만들던 것 밑에서 기다리는 동안 그 화면의 날짜 줄(과 점검의 멈춤 메모)은 '새 데이터가 들어왔어요. 이 화면을 저장하거나
#   나가면 새 데이터로 바뀌어요.' (app.heldNew) · 메뉴의 날짜 줄은 날짜만 · 기다리는 발행이 없으면 절대 없어요 · 화면에 들어가면 사라져요.
# 2 내 점수 칸의 회사 수: 한 회사의 두 주식(시험 데이터의 GOOG · GOOGL)은 한 회사 · 아래 띠는 종목 수 그대로 · 회사 페이지 '업종 {n}개 회사'.
# 3 점검의 미국 배당 줄: 배당을 아는 미국 종목이 있을 때만 · 배당 정보가 없는 미국 종목은 'rpt.divUsGone'.
# 5·6 홈의 오늘 볼 것: 처음 열 때 받은 disc.json 이 화면의 데이터보다 이른 발행이고 아직 4일이 안 됐으면 실패 문구(오늘은 할 일이 없어요
#   아님)와 10분 뒤 한 번 더 · disc.json 이 답하지 않으면 60초 뒤 실패 문구 (기다리기만 하지 않아요).
# 390 의 화면 사진: 환경 변수 SAYWHY2_SHOTS 의 폴더에 (없으면 찍지 않아요).
SHOTS2 = os.environ.get("SAYWHY2_SHOTS")


def shot2(page, name, width, full=False):
    if SHOTS2 and width == 390:
        os.makedirs(SHOTS2, exist_ok=True)
        page.screenshot(path=os.path.join(SHOTS2, f"{name}-{width}.png"), full_page=full)


def open_clock(R, site, width, init=None, path="/app.html?dev=1"):
    """R.open 과 같은데, 페이지의 시계를 지금 시각으로 설치해요 (10분 · 60초를 손으로 옮겨요). 데이터 파일 요청과 console 을 모아요."""
    wide = width >= 1024
    srv, base = serve(site)
    screen = pc_device(width) if wide else {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2}
    ctx = R.new_context(clock=False, **screen, locale="ko-KR", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else (R.outside.append(r.request.url), r.abort()))
    ctx.add_init_script("try { localStorage.setItem('baepsae2.v1.guideSeen', '1'); } catch (e) {}")
    if init:
        ctx.add_init_script(init)
    page = ctx.new_page()
    page.set_default_timeout(WAIT)
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    asked, logs = [], []
    page.on("request", lambda r: asked.append(DATA_FILE_RX.search(r.url).group(0)[1:]) if DATA_FILE_RX.search(r.url) else None)
    page.on("console", lambda m: logs.append(m.text))
    now = now_dt()
    page.clock.install(time=now)
    R.saw_clock(page, now)
    return srv, ctx, page, base, asked, logs, now


def held_parts(page, sel=SCREEN_DL):
    dl = page.locator(sel).first
    dl.wait_for(state="visible")
    return {"stale": dl.get_attribute("data-stale"), "held": dl.get_attribute("data-held"), "lines": dl.inner_text().split("\n"),
            "line": dl.locator('[data-ui-v2="held-line"]').count()}


def held_line_ok(page, width, where):
    """The line under the date: 12px or more, inside the screen, in the warning colour of the stale words it replaces."""
    g = page.evaluate("""(s) => { const l = document.querySelector(s + ' [data-ui-v2="held-line"]'); const b = l.getBoundingClientRect();
        return { size: parseFloat(getComputedStyle(l).fontSize), left: b.left, right: b.right, color: getComputedStyle(l).color,
          stale: getComputedStyle(document.querySelector('[data-ui-v2="screen"] [data-ui-v2="date-line"]')).color }; }""", SCREEN_DL)
    assert g["size"] >= 12 and g["left"] >= 0 and g["right"] <= width + 0.5, (where, g)
    assert g["color"] == g["stale"], (where, g)
    floor_ok(page, where)
    no_hscroll(page, width)


def scene_say_why_2(R, files, width):
    """say-why 2 (Jack, 2026-11-08): 1 새 데이터가 기다릴 때의 줄 (포트폴리오 만들기 · 가진 종목 넣기) · 2 회사 수 · 3 점검의 미국 배당 줄 ·
    5·6 홈의 공시 (이른 발행 · 답 없음). 휴대폰 320 · 390 은 모두, PC 1280 은 1 의 포트폴리오 만들기와 5·6 의 홈."""
    S = f"say-why 2 {width}"
    wide = width >= 1024
    held = C["app"]["heldNew"]
    old_date = fillp(C["app"]["asOf"], md="10월 30일")
    stale3 = fillp(C["app"]["stale"], n=3)
    new_line = fillp(C["app"]["asOf"], md=REFETCH_MD)

    # ── 1A 포트폴리오 만들기: 후보 고르기 · 매수 계획 ──
    site = build_site(stale_files(files, 75, -2, 2))
    srv, ctx, page, base, asked, logs, now = open_clock(R, site, width)
    page.goto(base + "/app.html?dev=1", wait_until="domcontentloaded")

    def build_line():
        wait_ready(page)
        to_build_start(page, wide)
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        click_next(page)
        see(page, C["build"]["s4"]["title"])
        page.get_by_role("button", name="+1,000만").first.click()
        click_next(page)
        see(page, C["pick"]["title"])
        assert held_parts(page) == {"stale": "1", "held": None, "lines": [f"{old_date} · {stale3}"], "line": 0}   # nothing held: the stale words
        # a return that finds nothing newer: the stale words stay and there is no line (it never shows with nothing held)
        back_in_view(page)
        wait_log(logs, "no later publish on the site", page)
        page.wait_for_timeout(300)
        assert held_parts(page) == {"stale": "1", "held": None, "lines": [f"{old_date} · {stale3}"], "line": 0}
        assert held not in page.locator("body").inner_text()
        # a later publish that keeps every pick, 11 minutes on: held on 후보 고르기, the line in place of the stale words
        put_files(site, refetch_files(files))
        page.clock.set_system_time(now + dt.timedelta(minutes=11))
        back_in_view(page)
        wait_log(logs, "is held while the portfolio builder is on its pick step", page)
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.held === '1'; }", arg=SCREEN_DL)
        assert held_parts(page) == {"stale": "1", "held": "1", "lines": [old_date, held], "line": 1}
        main = page.locator('[data-ui-v2="screen"] [data-ui-v2="date-line"]').first.inner_text()
        assert stale3 not in main and C["app"]["staleLate"] not in main, "멈춤 문구가 남았어요"
        assert page.locator("body").inner_text().count(held) == 1
        held_line_ok(page, width, "후보 고르기 · 새 데이터 줄")
        shot2(page, "held-pick", width)
        R.collect(page)
        # the menu's date line (☰ · PC left menu) is as before: the stale words, no line (Jack has not decided on it)
        if wide:
            side = page.locator('[data-ui-v2="side-date"] [data-ui-v2="date-line"]')
            assert side.inner_text() == f"{old_date} · {stale3}" and side.get_attribute("data-held") is None, side.inner_text()
            assert side.locator('[data-ui-v2="held-line"]').count() == 0
        else:
            m = open_menu(page)
            mdl = m.locator('[data-ui-v2="menu-date"] [data-ui-v2="date-line"]')
            assert mdl.inner_text() == f"{old_date} · {stale3}" and mdl.get_attribute("data-held") is None, mdl.inner_text()
            assert mdl.locator('[data-ui-v2="held-line"]').count() == 0
            shot2(page, "held-menu", width)
            R.collect(page)
            m.locator('[data-ui-v2="menu-close"]').click()
            m.wait_for(state="detached")
        # 매수 계획 (the 샀어요 sheet lives there): the same line
        click_next(page)
        see(page, C["plan"]["stocks"])
        assert held_parts(page) == {"stale": "1", "held": "1", "lines": [old_date, held], "line": 1}
        held_line_ok(page, width, "매수 계획 · 새 데이터 줄")
        shot2(page, "held-plan", width)
        R.collect(page)
        page.get_by_role("button", name=C["plan"]["back"]).click()
        see(page, C["pick"]["title"])
        assert held_parts(page)["held"] == "1"
        # back to the 기준 steps: the publish goes on screen and the line goes with the stale words
        page.get_by_role("button", name=PICK_BACK).click()
        page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
        assert held_parts(page) == {"stale": "0", "held": None, "lines": [new_line], "line": 0}
        wait_log(logs, "held until now, now shows on every screen", page)
        assert held not in page.locator("body").inner_text()
        if wide:
            assert page.locator('[data-ui-v2="side-date"] [data-ui-v2="date-line"]').get_attribute("data-held") is None
        R.collect(page)
    R.check(page, S, "1 포트폴리오 만들기: 기다리는 발행이 없으면 멈춤 문구 · 후보 고르기 · 매수 계획에서 새 발행이 기다리면 날짜 밑 "
            "'새 데이터가 들어왔어요. …' (멈춤 문구 없음 · 메뉴의 날짜 줄은 예전 그대로) · 기준 단계로 가면 새 데이터, 줄도 사라져요", build_line)
    ctx.close()
    srv.shutdown()

    if not wide:
        # ── 1C 줄이 약속을 지킬 수 없으면 없어요 (fresh-eyes review): 기다리는 발행이 그 자체로 멈춘 것 · 나가도 들어오지 않을 것 ──
        site = build_site(stale_files(files, 75, -2, 2))
        srv, ctx, page, base = R.open(site, width)
        logs = []
        page.on("console", lambda m: logs.append(m.text))

        def no_promise():
            wait_ready(page)
            to_build_start(page, wide)
            page.locator('[data-deck="income"]').click()
            see(page, C["build"]["s1"]["title"])
            click_next(page)
            see(page, C["build"]["s3"]["title"])
            click_next(page)
            see(page, C["build"]["s4"]["title"])
            page.get_by_role("button", name="+1,000만").first.click()
            click_next(page)
            see(page, C["pick"]["title"])
            stale_words = {"stale": "1", "held": None, "lines": [f"{old_date} · {stale3}"], "line": 0}
            # a later publish that is stale itself (published 30 hours ago, its staleAfter 2 hours ago): held, but no line
            late = stale_files(files, 30, -2, 1)
            for n in ("data.json", "corp.json"):
                late[n]["pxDate"] = REFETCH_PX
            put_files(site, late)
            back_in_view(page)
            wait_log(logs, "is held while the portfolio builder is on its pick step", page)
            page.wait_for_timeout(500)
            assert held_parts(page) == stale_words and held not in page.locator("body").inner_text()
            R.collect(page)
            # a fresh later publish without one of the picks: held, and leaving would not let it in → no line either
            picked = page.eval_on_selector_all("section[data-market='kr'] [data-cand][data-picked='1']", "els => els.map((e) => e.dataset.cand)")
            new = refetch_files(files)
            new["data.json"]["stocks"] = [x for x in new["data.json"]["stocks"] if x["t"] != picked[0]]
            put_files(site, new)
            back_in_view(page)                                                    # the stale held one is dropped, the new one fetched
            wait_log(logs, "is stale itself by now: dropped", page)
            deadline = time.time() + WAIT / 1000
            while sum("is held while the portfolio builder is on its pick step" in x for x in logs) < 2 and time.time() < deadline:
                page.wait_for_timeout(100)
            assert sum("is held while the portfolio builder is on its pick step" in x for x in logs) == 2, [x for x in logs if "[v2]" in x][-4:]
            page.wait_for_timeout(500)
            assert held_parts(page) == stale_words and held not in page.locator("body").inner_text()
            click_next(page)                                                      # 매수 계획: no line there either
            see(page, C["plan"]["stocks"])
            assert held_parts(page) == stale_words
            R.collect(page)
        R.check(page, S, "1 줄이 약속을 지킬 수 없으면 없어요: 기다리는 발행이 그 자체로 멈췄거나 · 나가도 들어오지 않으면(고른 후보가 새 발행에 없음) "
                "멈춤 문구 그대로", no_promise)
        ctx.close()
        srv.shutdown()

    if not wide:
        # ── 1B 가진 종목 넣기: 종목 넣기 · 기준 · 점검 (멈춤 메모 자리) → 매일 점검 시작하기 ──
        site = build_site(stale_files(files, 75, -2, 2))
        srv, ctx, page, base, asked, logs, now = open_clock(R, site, width)
        page.goto(base + "/app.html?dev=1", wait_until="domcontentloaded")

        def import_line():
            wait_ready(page)
            to_build_start(page, wide)
            page.locator('[data-ui-v2="start-holdings"]').click()
            at(page, "portfolio/import")
            for t, q in (("005930", "10"), ("000660", "2")):
                page.locator('[data-ui-v2="import-search"] input').fill(t)
                page.locator(f'[data-import-result="{t}"] button').click()
                row = page.locator(f'[data-import-row="{t}"]')
                row.wait_for(state="visible")
                row.locator('input[data-ui-v2="import-qty"]').fill(q)
            assert held_parts(page) == {"stale": "1", "held": None, "lines": [f"{old_date} · {stale3}"], "line": 0}
            put_files(site, refetch_files(files))
            back_in_view(page)
            wait_log(logs, "is held while the holdings import is open", page)
            page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.held === '1'; }", arg=SCREEN_DL)
            assert held_parts(page) == {"stale": "1", "held": "1", "lines": [old_date, held], "line": 1}
            held_line_ok(page, width, "종목 넣기 · 새 데이터 줄")
            shot2(page, "held-import", width)
            R.collect(page)
            action(page).click()                                                  # 기준
            see(page, C["build"]["s1"]["title"])
            assert held_parts(page) == {"stale": "1", "held": "1", "lines": [old_date, held], "line": 1}
            for c in ("value", "value", "div", "div", "stable"):
                page.locator(f'[data-card="{c}"] [data-ui-v2="card-inc"]').click()
            action(page).click()                                                  # 점검: its stale note says the line instead
            page.locator('[data-ui-v2="report"]').wait_for(state="visible")
            note = page.locator('[data-ui-v2="report-stale"]')
            assert note.count() == 1 and note.get_attribute("data-held") == "1" and note.inner_text().strip() == held, note.inner_text()
            body = page.locator("body").inner_text()
            assert C["rpt"]["stale"].split("{n}")[1].split(".")[0] not in body and body.count(held) == 1, "점검의 멈춤 메모가 남았어요"
            floor_ok(page, "점검 · 새 데이터 줄")
            nb = note.bounding_box()                                              # the note itself fits, and the page (320 too, since #94)
            assert nb["x"] >= 0 and nb["x"] + nb["width"] <= width + 0.5, nb
            no_hscroll(page, width)
            shot2(page, "held-report", width)
            R.collect(page)
            page.locator('[data-ui-v2="report-start"]').click()                  # 매일 점검 시작하기: saved, then the new data
            at(page, "portfolio")
            page.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.dataset.stale === '0'; }", arg=SCREEN_DL)
            assert held_parts(page) == {"stale": "0", "held": None, "lines": [new_line], "line": 0}
            assert held not in page.locator("body").inner_text()
            R.collect(page)
        R.check(page, S, "1 가진 종목 넣기: 종목 넣기 · 기준 · 점검에서 새 발행이 기다리면 그 줄 (점검은 멈춤 메모 자리에) · 매일 점검 시작하기 → "
                "새 데이터, 줄 없음", import_line)
        ctx.close()
        srv.shutdown()

        # ── 2 내 점수 칸의 회사 수 · 회사 페이지의 '업종 {n}개 회사' ──
        srv, ctx, page, base = R.open(build_site(files), width)

        def companies():
            eng = engine_numbers([{"points": {}}, {"points": {"large": 1}}])
            assert eng[0]["poolCo"] == eng[0]["pool"] - 1, eng[0]                 # GOOG · GOOGL: one company in the test data
            assert eng[1]["co"] == eng[1]["n"] - 1 and eng[1]["n"] == eng[1]["list"], eng[1]   # both among the largest: still one company
            wait_ready(page)
            to_build_start(page, wide)
            page.locator('[data-deck="blank"]').click()
            see(page, C["build"]["s1"]["title"])
            mc = page.locator('[data-ui-v2="meter-count"]')
            mc.wait_for(state="visible")
            assert int(mc.get_attribute("data-n")) == eng[0]["pool"] and int(mc.get_attribute("data-co")) == eng[0]["poolCo"]
            assert mc.inner_text().strip() == fillp(C["build"]["s1"]["remain"], n=ko_num(eng[0]["poolCo"])), mc.inner_text()
            assert page.locator('[data-ui-v2="match-count"]').inner_text().endswith(fillp(C["app"]["count"], count=ko_num(eng[0]["pool"])))   # 종목: 그대로
            page.locator('[data-card="large"] [data-ui-v2="card-inc"]').click()
            page.wait_for_function("(n) => document.querySelector('[data-ui-v2=\"meter-count\"]').dataset.co === String(n)", arg=eng[1]["co"])
            assert mc.get_attribute("data-pool") == "0" and int(mc.get_attribute("data-n")) == eng[1]["n"]
            assert mc.inner_text().strip() == fillp(C["build"]["s1"]["remain"], n=ko_num(eng[1]["co"])), mc.inner_text()
            assert page.locator('[data-ui-v2="match-count"]').inner_text().endswith(fillp(C["app"]["count"], count=ko_num(eng[1]["n"])))
            floor_ok(page, "내 점수 칸 · 회사 수")
            no_hscroll(page, width)
            shot2(page, "meter-companies", width)
            R.collect(page)
            # the company page: GOOGL is GOOG's own company in the 인터넷 group
            co_hash(page, "#stocks/GOOG/value")
            cmp = page.locator('[data-ui-v2="co-compare"]')
            cmp.wait_for(state="visible")
            strip = cmp.locator('[data-ui-v2="co-strip"]')
            sn, sco = int(strip.get_attribute("data-n")), int(strip.get_attribute("data-co"))
            assert sco == sn - 1, (sn, sco)
            n = int(cmp.get_attribute("data-n"))
            assert n <= sco and cmp.locator("h3").inner_text() == fillp(CO["value"]["compare"], n=n), (n, sco, cmp.locator("h3").inner_text())
            aria = strip.locator('[role="img"]').get_attribute("aria-label")
            assert aria.startswith(fillp(CO["value"]["stripAria"], ind="인터넷", n=sco, x="X").split(" 이 회사")[0]), aria
            shot2(page, "company-compare", width)
            R.collect(page)
            co_hash(page, "#stocks/GOOG/value-more")
            mp = page.locator('[data-ui-v2="co-map"]')
            mp.wait_for(state="visible")
            assert int(mp.get_attribute("data-co")) == int(mp.get_attribute("data-n")) - 1
            assert fillp(CO["map"]["aria"], ind="인터넷", n=mp.get_attribute("data-co"), roe="R", pbr="P").split(" 이 회사")[0] in mp.locator('svg[role="img"]').get_attribute("aria-label")
            R.collect(page)
        R.check(page, S, "2 회사 수: 내 점수 칸 '지금 기준이면 회사 {n}개가 남아요'는 GOOG · GOOGL 을 한 회사로 (점수 전 · 후) · 아래 띠의 종목 수는 그대로 · "
                "회사 페이지 '업종 {n}개 회사와 비교' · 지도도 회사 수", companies)
        ctx.close()
        srv.shutdown()

        # ── 3 점검의 미국 배당 줄 ──
        f3 = clone(files)
        by3 = {s["t"]: s for s in f3["data.json"]["stocks"]}
        by3["UBER"].pop("dy", None)                                             # a US stock with no dividend data
        srv, ctx, page, base = R.open(build_site(f3), width)

        def report_div():
            wait_ready(page)
            to_build_start(page, wide)
            page.locator('[data-ui-v2="start-holdings"]').click()
            at(page, "portfolio/import")
            for t, q in (("005930", "10"), ("AAPL", "2"), ("UBER", "3")):
                page.locator('[data-ui-v2="import-search"] input').fill(t)
                page.locator(f'[data-import-result="{t}"] button').click()
                row = page.locator(f'[data-import-row="{t}"]')
                row.wait_for(state="visible")
                row.locator('input[data-ui-v2="import-qty"]').fill(q)
            action(page).click()
            see(page, C["build"]["s1"]["title"])
            page.locator('[data-card="large"] [data-ui-v2="card-inc"]').click()
            action(page).click()
            div = page.locator('[data-ui-v2="report-div"]')
            div.wait_for(state="visible")
            assert div.locator('[data-ui-v2="report-div-us"]').inner_text() == C["rpt"]["divUs"]
            assert div.locator('[data-ui-v2="report-div-us-gone"]').inner_text() == fillp(C["rpt"]["divUsGone"], n=1)
            assert C["plan"]["divUnknown"].split("{n}")[0] not in div.inner_text(), "같은 종목을 0원 줄에서 또 말해요"
            div.scroll_into_view_if_needed()
            floor_ok(page, "점검 · 미국 배당 줄")
            no_hscroll(page, width)
            if SHOTS2 and width == 390:
                os.makedirs(SHOTS2, exist_ok=True)
                div.screenshot(path=os.path.join(SHOTS2, f"report-div-{width}.png"))
            R.collect(page)
            # without AAPL: no US stock with a known dividend → no 1년치 line; the one without stays named
            page.locator('[data-ui-v2="report-again"]').click()
            row = page.locator('[data-import-row="AAPL"]')
            row.wait_for(state="visible")
            row.get_by_role("button", name=fillp(C["build"]["s4"]["removeAria"], name=by3["AAPL"]["nk"])).click()
            row.wait_for(state="detached")
            action(page).click()
            see(page, C["build"]["s1"]["title"])
            action(page).click()
            div.wait_for(state="visible")
            assert div.locator('[data-ui-v2="report-div-us"]').count() == 0 and C["rpt"]["divUs"] not in page.locator("body").inner_text()
            assert div.locator('[data-ui-v2="report-div-us-gone"]').inner_text() == fillp(C["rpt"]["divUsGone"], n=1)
            R.collect(page)
        R.check(page, S, "3 점검 · 연 배당: 배당을 아는 미국 종목이 있을 때만 '미국 종목은 최근 배당을 1년치로 환산한 값이에요.' · 배당 정보가 없는 "
                "미국 종목은 '배당 정보가 없는 미국 종목 {n}개는 빼고 계산했어요.' (0원 줄과 겹치지 않아요)", report_div)
        ctx.close()
        srv.shutdown()

    # ── 5·6 홈의 오늘 볼 것: 이른 발행의 disc.json · 답하지 않는 disc.json ──
    f = daily_files(files)
    by = {s["t"]: s for s in f["data.json"]["stocks"]}
    pxd = f["data.json"]["pxDate"]
    calm_ts = ("373220", "207940", "009150", "005380", "105560")
    calm = e_imported(by, pxd, [(t, max(1, round(10000000 / 5 / by[t]["price"])), None) for t in calm_ts], did="dcalm5")
    calm["settings"]["points"] = {"large": 3}
    home_disc = "() => { const e = document.querySelector('[data-ui-v2=\"home2\"]'); return e ? e.dataset.disc : null; }"
    older = clone(f)
    older["disc.json"]["publishedAt"] = now_kst(days_ago=1)                    # an older publish, under 4 days: it would read as current
    site = build_site(older)
    srv, ctx, page, base, asked, logs, now = open_clock(R, site, width, init=e_store([calm]))
    page.goto(base + "/app.html?dev=1#home", wait_until="domcontentloaded")

    def older_disc():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        assert page.evaluate(home_disc) == "fail", page.evaluate(home_disc)
        box = page.locator('[data-ui-v2="home-disc-fail"]')
        box.wait_for(state="visible")
        assert box.locator('[data-ui-v2="load-fail"]').inner_text() == C["app"]["loadFail"]
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0 and C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
        wait_log(logs, "older than the data on screen", page)
        wait_log(logs, "it is tried once more on a return to view at least 10 minutes from now", page)
        floor_ok(page, "홈 · 이른 disc.json")
        no_hscroll(page, width)
        shot2(page, "home-disc-older", width, full=True)
        R.collect(page)
        if not wide:                                                              # the 공시 tab too: the failure message
            co_hash(page, "#stocks/005380/disc")
            page.wait_for_function("() => { const e = document.querySelector('[data-ui-v2=\"co-disc\"]'); return !!e && e.dataset.state === 'fail'; }")
            R.collect(page)
            page.evaluate("() => { location.replace('#home'); }")
            at(page, "home")
            page.locator('[data-ui-v2="home-disc-fail"]').wait_for(state="visible")
        # the site has the matching file now; 11 minutes on, a return to view loads it once more: the filings are checked → calm
        put_files(site, f, names=["disc.json"])
        back_in_view(page)                                                        # at once: no more try yet
        page.wait_for_timeout(500)
        assert asked.count("disc.json") == 1 and page.evaluate(home_disc) == "fail", asked
        page.clock.set_system_time(now + dt.timedelta(minutes=11))
        back_in_view(page)
        wait_log(logs, "it loads once more", page)
        page.wait_for_function(home_disc.replace("return e ? e.dataset.disc : null;", "return !!e && e.dataset.disc === 'ok';"))
        assert page.locator('[data-ui-v2="home-calm"]').inner_text() == C["today"]["calmEyebrow"]
        assert asked.count("disc.json") == 2, asked
        R.collect(page)
    R.check(page, S, "5·6 홈: 처음 연 disc.json 이 화면의 데이터보다 이른 발행(4일 안) → 실패 문구 · '오늘은 할 일이 없어요' 없음 → 10분 뒤 한 번 더 받아 ok · "
            "그때서야 '오늘은 할 일이 없어요'", older_disc)
    ctx.close()
    srv.shutdown()

    site = build_site(f)
    srv, ctx, page, base, asked, logs, now = open_clock(R, site, width, init=e_store([calm]))
    hung = []
    page.route("**/disc.json", lambda r: hung.append(r))                      # disc.json never answers
    page.goto(base + "/app.html?dev=1#home", wait_until="domcontentloaded")

    def hung_disc():
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        deadline = time.time() + WAIT / 1000
        while not hung and time.time() < deadline:
            page.wait_for_timeout(50)
        assert hung, "disc.json 요청이 없어요"
        assert page.evaluate(home_disc) == "wait"
        assert page.locator('[data-ui-v2="home-calm"], [data-ui-v2="home-disc-fail"]').count() == 0
        page.clock.fast_forward("00:59")                                          # 59 s: still waiting
        page.wait_for_timeout(300)
        assert page.evaluate(home_disc) == "wait"
        page.clock.fast_forward("00:02")                                          # past 60 s: a plain failure
        page.wait_for_function(home_disc.replace("return e ? e.dataset.disc : null;", "return !!e && e.dataset.disc === 'fail';"))
        box = page.locator('[data-ui-v2="home-disc-fail"]')
        box.wait_for(state="visible")
        assert box.locator('[data-ui-v2="load-fail"]').inner_text() == C["app"]["loadFail"]
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0 and C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
        wait_log(logs, "disc.json not loaded: no answer in 60 s", page)
        floor_ok(page, "홈 · 답 없는 disc.json")
        no_hscroll(page, width)
        shot2(page, "home-disc-timeout", width, full=True)
        R.collect(page)
    R.check(page, S, "5·6 홈: disc.json 이 답하지 않으면 60초 뒤 실패 문구 (59초엔 아직 기다림 · '오늘은 할 일이 없어요' 없음)", hung_disc)
    for r in hung:                                                             # the page gave up on it: let the held route go quietly
        try:
            r.abort()
        except Exception:
            pass
    page.unroute_all(behavior="ignoreErrors")
    ctx.close()
    srv.shutdown()


def back_in_view(page):
    page.evaluate(HIDE_JS)
    page.evaluate(SHOW_JS)


import random  # noqa: E402  (v19.3c: 무작위 점수 열 가지, 씨앗을 정해 늘 같아요)


# ── v19.3c: 포트폴리오 만들기의 기준 카드 · 내 점수 · 처음 안내 (docs/tasks/v19.3-portfolio-pictures-accounts.md Part D · E · N.3) ──
# 두 스위치(코드의 값을 읽어요): RECIPE_START (새 시작 화면) · GUIDE_FIRST_VISIT (첫 방문에 저절로 뜨는 처음 안내). 둘 다 켜져 있어요
# (Jack, 2026-11-08). v193c_on_app 은 두 스위치를 켜고 임시 폴더에 다시 빌드한 app.html 로 한 장면을 더 돌려요 (커밋하지 않아요; 지금은
# 커밋한 app.html 과 같은 페이지예요). 처음 안내를 보는 장면 말고는 모두 처음 안내를 이미 본 방문자로 열어요 (Runner.open guide_seen).
def _flag(rel, name):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as fh:
        got = re.findall(rf"^export const {name} = (true|false);$", fh.read(), flags=re.M)
    assert len(got) == 1, (rel, name, got)
    return got[0] == "true"


RECIPE_START = _flag("src/v2/build.jsx", "RECIPE_START")
GUIDE_FIRST_VISIT = _flag("src/v2/guide.jsx", "GUIDE_FIRST_VISIT")
# v19.3d (v19.3 Part E "Store the flag in the 2.0 store"): 처음 안내를 본 표시는 저장 기록(store.js guideSeen, 본 날) 안에 있어요.
# 예전 칸(baepsae2.v1.guideSeen)은 한 번 읽어 옮기기만 하고 다시 쓰지 않아요 (tests/test_v2_store_v2.py).
GUIDE_SEEN = "baepsae2.v1"
SEEN_JS = ("() => { try { const d = JSON.parse(localStorage.getItem('baepsae2.v1')); return d && typeof d.guideSeen === 'string' ? '1' : null; }"
           " catch (e) { return null; } }")


def forget_guide(page):
    """처음 안내를 본 표시를 저장 기록에서 지우고 페이지를 다시 열어요 (앱이 기억한 표시도 새로 읽게)."""
    page.evaluate("() => { const k = 'baepsae2.v1'; try { const d = JSON.parse(localStorage.getItem(k)); if (d) { delete d.guideSeen;"
                  " localStorage.setItem(k, JSON.stringify(d)); } } catch (e) { /* 없음 */ } }")
    page.reload(wait_until="domcontentloaded")
    wait_ready(page)


LIVE_CARDS = ("value", "div", "growth", "profit", "stable", "lowVol", "trend", "large")     # 준비 중이 아닌 기준 (engine.js CARDS)
_ON = {}


def v193c_on_app():
    """app.html 을 RECIPE_START · GUIDE_FIRST_VISIT 를 켜고 임시 폴더에 빌드해요 (커밋하지 않아요). 폴더는 바로 지워요."""
    if "html" not in _ON:
        tmp = tmpdirs.make("baepsae-v193c-on-")
        try:
            shutil.copytree(os.path.join(ROOT, "src"), os.path.join(tmp, "src"))
            os.makedirs(os.path.join(tmp, "tools"))
            for f in ("template.html", "build-app.sh", "package.json", "package-lock.json", os.path.join("tools", "build_tag.py")):
                shutil.copy(os.path.join(ROOT, f), os.path.join(tmp, f))
            os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
            for rel, name in (("src/v2/build.jsx", "RECIPE_START"), ("src/v2/guide.jsx", "GUIDE_FIRST_VISIT")):
                p = os.path.join(tmp, *rel.split("/"))
                with open(p, encoding="utf-8") as fh:
                    src = fh.read()
                old = re.findall(rf"^export const {name} = (?:true|false);$", src, flags=re.M)
                assert len(old) == 1, (rel, old)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(src.replace(old[0], f"export const {name} = true;"))
            out = os.path.join(tmp, "out")
            r = subprocess.run(["bash", "build-app.sh", out], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
            assert r.returncode == 0, r.stdout + r.stderr
            with open(os.path.join(out, "app.html"), encoding="utf-8") as fh:
                _ON["html"] = fh.read()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _ON["html"]


def engine_numbers(settings_list):
    """설정마다 엔진의 수 [{pool, n, list}] — node 가 src/v2/engine.js 를 시험 데이터(tests/fixtures/v2/data.json)로 돌려요.
    pool: 기준 전의 수(engine.poolCount) · n: 내 점수 칸의 수(engine.meterCount) · list: screen() 결과 목록의 길이(시장마다 더해서).
    co · poolCo (Jack, 2026-11-08: 회사 하나 = 하나): 내 점수 칸의 글이 말하는 회사 수 (engine.meterCompanies) · 기준 전의 회사 수 (res.poolCo)."""
    tmp = tmpdirs.make("baepsae-v193c-engine-")
    try:
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, "src/v2/engine.js", "--bundle", "--format=esm", "--platform=node", f"--outfile={os.path.join(tmp, 'engine.mjs')}",
                            "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(tmp, "in.json"), "w", encoding="utf-8") as fh:
            json.dump(settings_list, fh)
        code = ("import * as E from './engine.mjs'; import { readFileSync } from 'node:fs';"
                f"const stocks = JSON.parse(readFileSync({json.dumps(os.path.join(FIX, 'data.json'))}, 'utf8')).stocks;"
                "const out = JSON.parse(readFileSync('./in.json', 'utf8')).map((o) => { const s = { ...E.defaultSettings(), ...o };"
                " const r = E.screen(stocks, s); return { pool: E.poolCount(stocks, s), n: E.meterCount(r).n, co: E.meterCompanies(r).n, poolCo: E.screen(stocks, { ...s, points: {} }).poolCo,"
                " list: Object.values(r.markets).reduce((a, m) => a + m.survivors.length, 0) }; });"
                "console.log(JSON.stringify(out));")
        r = subprocess.run(["node", "--input-type=module", "-e", code], cwd=tmp, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ko_num(n):
    return f"{n:,}"


def meter(page):
    m = page.locator('[data-ui-v2="meter-count"]')
    m.wait_for(state="visible")
    return {"pool": m.get_attribute("data-pool") == "1", "n": int(m.get_attribute("data-n")), "text": m.inner_text()}


def bubble(page, step):
    b = page.locator(f'[data-ui-v2="guide-bubble"][data-step="{step}"]')
    b.wait_for(state="visible")
    return b


def guide_gone(page):
    page.locator('[data-ui-v2="guide-bubble"]').wait_for(state="detached")
    assert page.locator('[data-ui-v2="guide-shade"], [data-ui-v2="guide-hole"]').count() == 0


def open_guide(page, wide):
    """메뉴의 '처음 안내 다시 보기' (휴대폰 ☰ · PC 왼쪽 메뉴) → 홈에 반기는 화면."""
    if wide:
        page.locator('[data-ui-v2="side-link"][data-item="guide"]').click()
    else:
        m = open_menu(page)
        m.locator('[data-ui-v2="menu-item"][data-item="guide"]').click()
        m.wait_for(state="detached")
    at(page, "home")
    w = page.locator('[data-ui-v2="guide-welcome"]')
    w.wait_for(state="visible")
    return w


def guide_step1(page, wide):
    """처음 안내 1/3 을 새로 열어요: 만들던 포트폴리오가 있으면 직접 해 보기가 그 자리로 가니까(keeps_draft), 먼저 다시 시작해요."""
    again = page.get_by_role("button", name=C["build"]["restart"], exact=True)
    if page.locator('[data-ui-v2="screen"][data-route="portfolio/build"]').count() and again.count():
        again.click()
        see(page, C["build"]["s0"]["title"])
    w = open_guide(page, wide)
    w.locator('[data-ui-v2="guide-try"] button').click()
    at(page, "portfolio/build")
    return bubble(page, 1)


def to_build_start(page, wide):
    """포트폴리오 만들기의 첫 단계(시작)로: PC 는 왼쪽 메뉴, 휴대폰은 start_build. 만들던 것이 있으면 다시 시작."""
    if wide:
        page.locator('[data-ui-v2="side-build"]').click()
    else:
        start_build(page)
    at(page, "portfolio/build")
    again = page.get_by_role("button", name=C["build"]["restart"], exact=True)
    if again.count():
        again.click()
    see(page, C["build"]["s0"]["title"])


def scene_v193c(R, files, width):
    """v19.3c (Part D · E · N.3): 기준 카드 두 칸(그림 칩 · 작은 그림 · 이름 · 기준 · 쉬운 한 줄 · − 점 다섯 + · 준비 중 둘은 흐리게) ·
    내 점수 칸(열 칸 · '{n}점 남았어요' · '지금 기준이면 회사 {n}개가 남아요'): 점수가 없을 때는 기준 전의 수(pool), 있으면 엔진이 고른
    목록의 길이 — 무작위 점수 열 가지 모두 엔진과 같아요 (휴대폰 390) · 아래 띠의 수도 같은 수 · 깐깐함 그대로. 메뉴의 '처음 안내 다시 보기'
    (예전 뱁새 보기 바로 앞) → 반기는 화면(뱁이 132px, 숫자 없음) → 직접 해 보기 → 1/3 배당 + 만 눌려요(어두운 곳은 안 눌려요) →
    2/3 기준 전의 수 → 엔진의 새 수 (2.5초 또는 누르면) → 3/3 알겠어요 (준 점수는 그대로). 건너뛰기는 세 단계 모두에서, Esc 도 끝내고
    '본 적 있음'을 남겨요. 그냥 둘러볼게요 · 휴대폰 뒤로도 끝내요."""
    S = f"v19.3c {width}"
    wide = width >= 1024
    srv, ctx, page, base = R.open(build_site(files), width, device=pc_device(width) if wide else None, guide_seen=False)
    seen = lambda: page.evaluate(SEEN_JS)

    def first_screen():
        wait_ready(page)
        at(page, "home")
        assert GUIDE_FIRST_VISIT                                           # 켜져 있어요 (Jack, 2026-11-08): 첫 방문 홈 대신 반기는 화면
        page.locator('[data-ui-v2="guide-welcome"]').wait_for(state="visible")
        assert seen() is None
        R.collect(page)
    R.check(page, S, "첫 화면: 처음 안내가 저절로 떠요 (첫 방문 홈 대신 반기는 화면)", first_screen)

    def welcome():
        if GUIDE_FIRST_VISIT:
            page.locator('[data-ui-v2="guide-browse"]').click()            # 그냥 둘러볼게요 → 홈, 본 적 있음
            page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")
        w = open_guide(page, wide)
        mascot_img(w, "baepi-16-build.webp", 132, C["build"]["s0"]["imgAlt"])
        t = w.inner_text()
        assert C["guide"]["title"] in t.replace("\n", " ") and C["guide"]["body"] in t, t
        assert [x.strip() for x in w.locator('[data-ui-v2="guide-steps"] [role="listitem"]').all_inner_texts()] == C["guide"]["steps"]
        assert not re.search(r"\d", t), t                                  # 뱁이 화면: 숫자 없음 (날짜 줄은 카드 밖)
        assert w.locator('[data-ui-v2="guide-try"]').inner_text().strip() == C["guide"]["try"]
        assert w.locator('[data-ui-v2="guide-browse"]').inner_text().strip() == C["guide"]["browse"]
        assert page.locator('[data-ui-v2="today-hero"], [data-ui-v2="home-hero"], [data-ui-v2="popular"]').count() == 0
        floor_ok(page, "반기는 화면")
        no_hscroll(page, width)
        R.collect(page)
        page.locator('[data-ui-v2="guide-browse"]').click()                # 그냥 둘러볼게요: 홈으로, 본 적 있음
        page.locator('[data-ui-v2="guide-welcome"]').wait_for(state="detached")
        at(page, "home")
        assert seen() == "1"
    R.check(page, S, "메뉴 '처음 안내 다시 보기' → 반기는 화면(뱁이 132px · 제목 · 세 단계 · 숫자 없음) → 그냥 둘러볼게요 → 홈 · 본 적 있음", welcome)

    def steps_and_skip():
        forget_guide(page)
        b = guide_step1(page, wide)                                        # 1/3: 배당 카드와 + 만 밝아요
        assert b.locator('[data-ui-v2="guide-count"]').inner_text() == "1/3"
        assert b.inner_text().count(C["guide"]["s1"][0]) == 1 and C["guide"]["s1"][1] in b.inner_text()
        page.wait_for_function("() => document.activeElement && document.activeElement.dataset.uiV2 === 'guide-bubble'")   # 초점은 말풍선에
        assert b.get_attribute("role") == "dialog" and page.locator("#v2-guide-title").inner_text() == C["guide"]["s1"][0]
        assert page.locator('[data-ui-v2="guide-ring"]').count() == 1 and page.locator('[data-ui-v2="guide-hand"] svg[data-ph="hand-pointing"]').count() == 1
        assert meter(page)["pool"]
        box = page.locator('[data-card="value"] [data-ui-v2="card-inc"]').bounding_box()          # 어두운 곳의 + 는 안 눌려요
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(150)
        assert page.locator('[data-card="value"]').get_attribute("data-points") == "0"
        assert page.locator('[data-ui-v2="points-left"]').inner_text() == "10"
        R.collect(page)
        b.locator('[data-ui-v2="guide-skip"]').click()                     # 건너뛰기 (1/3): 끝, 본 적 있음
        guide_gone(page)
        page.wait_for_function("() => !!document.activeElement && document.activeElement.matches('[data-card=\"div\"] [data-ui-v2=\"card-inc\"]')")      # 초점은 배당 카드의 + 로
        assert seen() == "1" and page.locator('[data-ui-v2="points-left"]').inner_text() == "10"
        forget_guide(page)
        bubble_ = guide_step1(page, wide)
        page.keyboard.press("Escape")                                      # Esc (1/3): 건너뛰기와 같아요
        guide_gone(page)
        assert seen() == "1"
        assert bubble_.count() == 0
        guide_step1(page, wide)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()  # 진짜 + → 2/3
        b2 = bubble(page, 2)
        assert b2.locator('[data-ui-v2="guide-count"]').inner_text() == "2/3"
        b2.locator('[data-ui-v2="guide-skip"]').click()                    # 건너뛰기 (2/3)
        guide_gone(page)
        assert page.locator('[data-card="div"]').get_attribute("data-points") == "1"
        guide_step1(page, wide)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()
        bubble(page, 2)
        page.keyboard.press("Escape")                                      # Esc (2/3)
        guide_gone(page)
        guide_step1(page, wide)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()
        bubble(page, 2).click()                                            # 누르면 바로 3/3
        b3 = bubble(page, 3)
        assert b3.locator('[data-ui-v2="guide-count"]').inner_text() == "3/3"
        b3.locator('[data-ui-v2="guide-skip"]').click()                    # 건너뛰기 (3/3)
        guide_gone(page)
        guide_step1(page, wide)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()
        bubble(page, 3)
        page.keyboard.press("Escape")                                      # Esc (3/3)
        guide_gone(page)
        R.collect(page)
    R.check(page, S, "처음 안내 1/3 · 2/3 · 3/3 모두에서 건너뛰기와 Esc 가 끝내요 (본 적 있음) · 1/3 은 배당의 + 만 눌려요 · 초점은 말풍선", steps_and_skip)

    def whole_guide():
        eng = engine_numbers([{"points": {}}, {"points": {"div": 1}}])
        guide_step1(page, wide)
        m0 = meter(page)
        assert m0["pool"] and m0["n"] == eng[0]["pool"] == eng[1]["pool"] and ko_num(eng[0]["poolCo"]) in m0["text"], (m0, eng)
        assert action(page).inner_text() == C["build"]["pickCardsBtn"]
        assert fillp(C["app"]["count"], count=ko_num(eng[0]["pool"])) in page.locator('[data-ui-v2="match-count"]').inner_text()   # 아래 띠도 내 점수 칸과 같은 수 (Jack, 2026-11-08)
        R.collect(page)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()
        b2 = bubble(page, 2)                                               # 2/3: 기준 전의 수를 긋고 → 엔진의 새 수
        m1 = meter(page)
        assert not m1["pool"] and m1["n"] == eng[1]["n"] == eng[1]["list"] < eng[1]["pool"], (m1, eng)
        assert page.locator('[data-ui-v2="meter-pool"]').inner_text() == fillp(C["app"]["count"], count=ko_num(eng[1]["poolCo"]))
        assert page.locator('[data-ui-v2="meter-n"]').inner_text() == ko_num(eng[1]["co"])
        assert fillp(C["guide"]["s2"][0], n=ko_num(eng[1]["co"])) in b2.inner_text()
        assert fillp(C["guide"]["s2"][1], top=50) in b2.inner_text()        # 보통 = 상위 50%
        R.collect(page)
        b3 = bubble(page, 3)                                               # 2.5초 뒤 저절로 3/3
        assert fillp(C["guide"]["s3"][0], n=9) in b3.inner_text() and C["guide"]["s3"][1] in b3.inner_text()
        assert page.locator('[data-ui-v2="meter-pool"]').count() == 0
        R.collect(page)
        b3.get_by_role("button", name=C["guide"]["done"]).click()          # 알겠어요: 끝, 준 점수는 그대로
        guide_gone(page)
        page.wait_for_function("() => !!document.activeElement && document.activeElement.matches('[data-card=\"div\"] [data-ui-v2=\"card-inc\"]')")      # 초점은 배당 카드의 + 로 (페이지로 떨어지지 않아요)
        assert seen() == "1"
        assert page.locator('[data-card="div"]').get_attribute("data-points") == "1" and page.locator('[data-ui-v2="points-left"]').inner_text() == "9"
        click_next(page)                                                   # 그다음은 늘 하던 대로
        see(page, C["build"]["s3"]["title"])
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=C["build"]["prevStep"]).click()
        see(page, C["build"]["s1"]["title"])
        if not wide:                                                       # 휴대폰 뒤로: 안내 중에 포트폴리오 만들기를 떠나면 끝 (본 적 있음)
            forget_guide(page)
            guide_step1(page, wide)
            page.go_back()
            at(page, "home")
            page.wait_for_function(f"() => ({SEEN_JS})() === '1'")
            assert page.locator('[data-ui-v2="guide-bubble"], [data-ui-v2="guide-welcome"]').count() == 0
        R.collect(page)
    R.check(page, S, "처음 안내 끝까지: 기준 전의 수(엔진 poolCount) → 배당 1점 → 엔진의 새 수 · '회사가 {n}개로 줄었어요' · 2.5초 뒤 3/3 · 알겠어요 · 휴대폰 뒤로도 끝",
            whole_guide)

    def cards():
        to_build_start(page, wide)
        page.locator('[data-deck="blank"]').click()
        see(page, C["build"]["s1"]["title"])
        assert C["build"]["s1"]["body"] in page.locator("main").inner_text()
        ids = page.locator("[data-card]").evaluate_all("(els) => els.map((e) => e.dataset.card)")
        assert ids == ["value", "div", "divGrowth", "growth", "profit", "stable", "lowVol", "trend", "payout", "large"], ids
        for cid in ids:
            card = page.locator(f'[data-card="{cid}"]')
            cc = C["build"]["cards"][cid]
            t = card.inner_text()
            assert cc["name"] in t and cc["basis"] in t and cc["plain"] in t, (cid, t)
            assert card.locator('svg[data-ui-v2="card-art"]').count() == 1 and card.locator("svg text").count() == 0
            if cid in ("divGrowth", "payout"):
                assert C["build"]["s1"]["pendingCard"] in t and card.locator("button").count() == 0
                dims = card.evaluate("""(e) => [getComputedStyle(e).opacity, getComputedStyle(e.querySelector('[data-card-pic]')).opacity,
                    e.querySelector('[data-card-pic]').dataset.dim || '', getComputedStyle(e.querySelector('svg[data-ui-v2="card-art"]')).opacity,
                    getComputedStyle(e.querySelector('h3')).color]""")
                assert dims == ["1", "0.45", "1", "0.45", NAVY_RGB], (cid, dims)      # 글은 그대로, 그림 둘만 흐리게
            else:
                assert card.locator('[data-ui-v2="card-inc"]').get_attribute("aria-label") == fillp(C["build"]["s1"]["inc"], card=cc["name"], n=0)
                assert card.locator('[data-ui-v2="card-dec"]').is_disabled()
        cols = page.locator('[data-ui-v2="card-grid"]').evaluate("(e) => getComputedStyle(e).gridTemplateColumns.split(' ').length")
        assert cols == (3 if wide else 2), cols                            # 휴대폰 두 칸 · PC 세 칸
        page.locator('[data-card="profit"] [data-ui-v2="card-inc"]').click()
        sel = page.locator('[data-card="profit"]').evaluate("(e) => [getComputedStyle(e).backgroundColor, getComputedStyle(e).boxShadow]")
        assert sel[0] == SELECT_RGB and NAVY_RGB in sel[1], sel                 # 고른 카드: 따뜻한 바탕 + 남색 테두리 (살구색 아님)
        basis = page.locator('[data-card="profit"] h3 + p').evaluate("(e) => [e.textContent, getComputedStyle(e).color]")
        assert basis == [C["build"]["cards"]["profit"]["basis"], TEXT2_RGB], basis     # 고른 카드의 기준 줄: text2 (text3 은 4.5:1 미달)
        slot = page.locator('[data-ui-v2="meter-slot"][data-slot="profit"]')
        assert slot.count() == 1 and slot.get_attribute("aria-label") == fillp(C["build"]["s1"]["slot"], card=C["build"]["cards"]["profit"]["name"], n=1)
        assert page.locator('[data-ui-v2="meter-slot"][data-empty="1"]').count() == 9
        assert slot.locator("img").get_attribute("src") == PICS["CARD_PICS"]["profit"]
        page.locator('[data-ui-v2="card-grid"]').scroll_into_view_if_needed()
        page.evaluate("() => window.scrollBy(0, 400)")                     # 내 점수 칸은 위에 붙어 있어요
        page.wait_for_timeout(100)
        top = page.locator('[data-ui-v2="meter-bar"]').bounding_box()["y"]
        assert abs(top - (68 if wide else 0)) < 1.5, top
        floor_ok(page, "기준 카드")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "기준 카드: 엔진 순서 열 장 · 그림 · 작은 그림(글 없음) · 기준 · 쉬운 한 줄 · 준비 중 둘은 흐리고 버튼 없음 · 휴대폰 두 칸 / PC 세 칸 · "
            "고른 카드 남색 테두리 · 내 점수 칸(그림 · 화면 읽기 이름) · 위에 붙어요", cards)

    def random_mixes():
        if wide:
            return
        rnd = random.Random(193)
        mixes = []
        for _ in range(10):
            k = rnd.randint(1, 4)
            chosen = rnd.sample(LIVE_CARDS, k)
            pts, left = {}, 10
            for i, cid in enumerate(chosen):
                most = min(5, left - (k - i - 1))
                pts[cid] = rnd.randint(1, max(1, most))
                left -= pts[cid]
            mixes.append({"points": pts, "strict": rnd.choice(["loose", "normal", "strict", "very"])})
        eng = engine_numbers([{"points": {}}] + mixes)
        page.get_by_role("button", name=C["build"]["restart"]).click()
        page.locator('[data-deck="blank"]').click()
        m0 = meter(page)                                                   # 점수 0: 기준 전의 수
        assert m0["pool"] and m0["n"] == eng[0]["pool"] and fillp(C["build"]["s1"]["remain"], n=ko_num(eng[0]["poolCo"])) == m0["text"].strip(), (m0, eng[0])
        got = []
        for mix, e in zip(mixes, eng[1:]):
            page.get_by_role("button", name=C["build"]["restart"]).click()
            page.locator('[data-deck="blank"]').click()
            page.get_by_role("radio", name=C["build"]["s1"]["strict"][mix["strict"]], exact=True).click()
            for cid, n in mix["points"].items():
                for _ in range(n):
                    page.locator(f'[data-card="{cid}"] [data-ui-v2="card-inc"]').click()
            m = meter(page)
            assert not m["pool"] and m["n"] == e["n"] == e["list"], (mix, m, e)
            want = C["build"]["s1"]["remainNone"] if e["co"] == 0 else fillp(C["build"]["s1"]["remain"], n=ko_num(e["co"]))
            assert m["text"].strip() == want, (mix, m["text"], want)
            assert ko_num(e["n"]) in page.locator('[data-ui-v2="match-count"]').inner_text()
            assert page.locator('[data-ui-v2="points-left"]').inner_text() == str(10 - sum(mix["points"].values()))
            got.append(e["n"])
        assert len(set(got)) >= 4, got                                     # 서로 다른 결과가 나오는 섞임이에요
        R.collect(page)
    R.check(page, S, "무작위 점수 열 가지: 내 점수 칸의 수 = 엔진이 고른 목록의 길이 (점수 0 이면 기준 전의 수) · 아래 띠도 같은 수", random_mixes)

    def keeps_draft():
        to_build_start(page, wide)                                         # 만들던 것: 배당 생활비 → 빼기 단계
        page.locator('[data-deck="income"]').click()
        see(page, C["build"]["s1"]["title"])
        click_next(page)
        see(page, C["build"]["s3"]["title"])
        open_guide(page, wide).locator('[data-ui-v2="guide-try"] button').click()     # 직접 해 보기: 처음부터가 아니라 그 자리로
        at(page, "portfolio/build")
        see(page, C["build"]["s3"]["title"])
        page.wait_for_timeout(300)
        assert page.locator('[data-ui-v2="guide-bubble"], [data-ui-v2="guide-shade"]').count() == 0
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=C["build"]["prevStep"]).click()
        see(page, C["build"]["s1"]["title"])
        assert page.locator('[data-card="div"]').get_attribute("data-points") == "5" and page.locator('[data-ui-v2="points-left"]').inner_text() == "0"
        page.get_by_role("button", name=C["build"]["restart"], exact=True).click()   # 다시 시작: 만들던 것 없음 → 직접 해 보기는 새로
        see(page, C["build"]["s0"]["title"])
        open_guide(page, wide).locator('[data-ui-v2="guide-try"] button').click()
        bubble(page, 1).locator('[data-ui-v2="guide-skip"]').click()
        guide_gone(page)
        assert page.locator('[data-ui-v2="points-left"]').inner_text() == "10" and page.locator('[data-card="div"]').get_attribute("data-points") == "0"
        R.collect(page)
    R.check(page, S, "직접 해 보기: 만들던 포트폴리오(점수를 준 것)가 있으면 그 자리로(점수 그대로, 안내 없음) · 없으면 새로 시작해 1/3", keeps_draft)

    def welcome_leaves():
        forget_guide(page)
        open_guide(page, wide)
        if wide:                                                           # PC: 안내가 떠 있는 동안 '/' 는 검색 칸으로 가지 않아요
            page.evaluate("() => document.activeElement && document.activeElement.blur()")
            page.keyboard.press("/")
            page.wait_for_timeout(100)
            assert not focused_in(page, TOP_INPUT), "반기는 화면에서 '/' 가 검색 칸으로 갔어요"
            page.locator('[data-ui-v2="side-tab"][data-tab="stocks"]').click()
        else:
            tab(page, TABS["stocks"])
        at(page, "stocks")                                                 # 홈을 떠나면 반기는 화면은 끝 (본 적 있음)
        page.wait_for_function(f"() => ({SEEN_JS})() === '1'")
        if wide:
            page.locator('[data-ui-v2="side-tab"][data-tab="home"]').click()
        else:
            tab(page, TABS["home"])
        at(page, "home")
        page.wait_for_timeout(200)
        assert page.locator('[data-ui-v2="guide-welcome"]').count() == 0, "홈을 떠났다 돌아왔는데 반기는 화면이 그대로예요"
        if wide:
            guide_step1(page, wide)                                        # 1/3 말풍선이 떠 있는 동안에도 '/' 는 그대로
            page.keyboard.press("/")
            page.wait_for_timeout(100)
            assert not focused_in(page, TOP_INPUT) and page.locator('[data-ui-v2="guide-bubble"]').count() == 1
            page.keyboard.press("Escape")
            guide_gone(page)
        R.collect(page)
    R.check(page, S, "반기는 화면에서 다른 탭으로 가면 안내는 끝(본 적 있음), 홈에 돌아와도 안 떠요 · PC: 안내 중에는 '/' 가 검색 칸으로 가지 않아요", welcome_leaves)
    ctx.close()
    srv.shutdown()


TEXT2_RGB = "rgb(91, 101, 118)"                           # src/ui/tokens.js COLOR.text2 #5B6576


def scene_v193c_landscape(R, files, size, preview=False):
    """v19.3c 처음 안내 1/3 을 옆으로 눕힌 휴대폰에서: 누를 + 는 위에 붙은 내 점수 칸 아래, 말풍선 위(그 틈이 좁으면 말풍선이 위로)에 있고
    눌려요 · 밝은 곳은 내 점수 칸과 말풍선을 덮지 않아요 · 창의 높이만 바뀌어도 어두운 곳은 끝까지 눌리지 않아요(그 아래 페이지는 안 눌려요).
    2/3 · 3/3 (2026-11-08 리뷰): 말풍선은 밝힌 내 점수 칸(빛 테두리까지)을 덮지 않아요 — 칸 열 개와 '지금 기준이면 회사 N개가 남아요' 줄이
    보이고, 말풍선의 글은 12px 이상 · 버튼은 44px 이상, 알겠어요가 화면 안에서 눌려요. preview: 미리 보기(app-preview.html, 내 점수 칸이
    예시 데이터 줄 아래에 붙어요)."""
    w, h = size
    S = f"v19.3c 가로 휴대폰 {w}x{h}" + (" 미리 보기" if preview else "")
    dev = {"viewport": {"width": w, "height": h}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
    site = build_site(files)
    if preview:
        shutil.copy(os.path.join(ROOT, "app-preview.html"), site)
    srv, ctx, page, base = R.open(site, w, device=dev, guide_seen=False, **({"path": "/app-preview.html"} if preview else {}))
    keep = (lambda p: None) if preview else R.collect      # 미리 보기의 지어낸 종목 이름은 smoke_preview 가 출처를 봐요

    def step1_fits():
        wait_ready(page)
        at(page, "home")
        b = guide_step1(page, False)
        page.wait_for_timeout(300)
        g = page.evaluate("""() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
            return { top: b.top, bottom: b.bottom, left: b.left, right: b.right }; };
          const p = r('[data-card="div"] [data-ui-v2="card-inc"]');
          const t = document.elementFromPoint((p.left + p.right) / 2, (p.top + p.bottom) / 2);
          return { plus: p, meter: r('[data-ui-v2="meter-bar"]'), bubble: r('[data-ui-v2="guide-bubble"]'), hole: r('[data-ui-v2="guide-hole"]'),
            at: document.querySelector('[data-ui-v2="guide-bubble"]').dataset.at, hit: t && t.closest('[data-ui-v2="card-inc"]') ? 'plus' : (t && t.dataset.uiV2) }; }""")
        assert g["hit"] == "plus", g                                       # + 가운데를 누르면 + 가 눌려요 (말풍선 · 어두운 곳 아님)
        lo = g["meter"]["bottom"] if g["at"] == "bottom" else max(g["meter"]["bottom"], g["bubble"]["bottom"])
        hi = g["bubble"]["top"] if g["at"] == "bottom" else h
        assert g["plus"]["top"] >= lo - 0.5 and g["plus"]["bottom"] <= hi + 0.5, g     # + 는 내 점수 칸 · 말풍선 사이
        assert g["hole"]["top"] >= g["meter"]["bottom"] - 0.5 or g["at"] == "top", g   # 밝은 곳이 내 점수 칸을 덮지 않아요
        if g["at"] == "bottom":
            assert g["hole"]["bottom"] <= g["bubble"]["top"] + 0.5, g
        else:
            assert g["hole"]["top"] >= g["bubble"]["bottom"] - 0.5, g
        keep(page)
        page.set_viewport_size({"width": w, "height": h + 300})              # 높이만 바뀌어도: 새로 생긴 아래쪽도 어둡고 눌리지 않아요
        page.wait_for_timeout(200)
        hit = page.evaluate(f"() => {{ const e = document.elementFromPoint(3, {h + 290}); return e ? (e.dataset.uiV2 || e.tagName) : null; }}")
        assert hit == "guide-shade", hit
        page.set_viewport_size({"width": w, "height": h})
        page.wait_for_timeout(200)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()  # 진짜 + 를 누르면 2/3
        bubble(page, 2).locator('[data-ui-v2="guide-skip"]').click()
        guide_gone(page)
        keep(page)
    R.check(page, S, "처음 안내 1/3: + 가 내 점수 칸과 말풍선 사이에서 눌려요 · 밝은 곳이 칸 · 말풍선을 덮지 않아요 · 높이만 바뀐 창의 아래쪽도 어둡고 막혀요", step1_fits)

    # 2/3 · 3/3: 말풍선이 밝힌 내 점수 칸을 덮지 않아요 (말풍선 위끝 ≥ 밝은 곳 아래끝 + 빛 테두리 4px) · 칸 열 개와 회사 수 줄의 가운데를
    # 누르면 말풍선 · 어두운 곳이 아니라 밝힌 칸이에요 · 말풍선은 화면 안 · 글 12px 이상 · 버튼 44px 이상 · 알겠어요가 눌려요
    def step23_clear():
        guide_step1(page, False)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()
        for step in (2, 3):
            bubble(page, step)
            page.wait_for_timeout(250)
            g = page.evaluate("""() => { const r = (e) => { const b = e.getBoundingClientRect(); return { top: b.top, bottom: b.bottom, left: b.left, right: b.right }; };
                const q = (s) => document.querySelector(s); const bb = q('[data-ui-v2="guide-bubble"]');
                const spots = [...document.querySelectorAll('[data-ui-v2="meter"] [data-ui-v2="meter-slot"]'), q('[data-ui-v2="meter-count"]')];
                const hits = spots.map((e) => { const b = e.getBoundingClientRect(); const t = document.elementFromPoint((b.left + b.right) / 2, (b.top + b.bottom) / 2);
                  if (!t) return null; if (t.closest('[data-ui-v2="guide-bubble"]')) return 'bubble';
                  return t.closest('[data-ui-v2="meter"]') || t.dataset.uiV2 === 'guide-hole' ? 'lit' : (t.dataset.uiV2 || t.tagName); });
                const fonts = [...bb.querySelectorAll('*')].filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
                  .map((e) => parseFloat(getComputedStyle(e).fontSize));
                return { hole: r(q('[data-ui-v2="guide-hole"]')), bubble: r(bb), slots: spots.length - 1, hits, fonts,
                  buttons: [...bb.querySelectorAll('button')].map((e) => { const b = e.getBoundingClientRect(); return [b.width, b.height]; }) }; }""")
            assert g["bubble"]["top"] >= g["hole"]["bottom"] + 4 - 0.5, (step, g)        # 빛 테두리(4px)까지 덮지 않아요
            assert g["bubble"]["top"] >= -0.5 and g["bubble"]["bottom"] <= h + 0.5, (step, g)
            assert g["slots"] == 10 and all(x == "lit" for x in g["hits"]), (step, g)       # 칸 열 개 · 회사 수 줄이 보여요
            assert g["fonts"] and min(g["fonts"]) >= 12, (step, g)
            assert g["buttons"] and all(bw >= 44 - 0.5 and bh >= 44 - 0.5 for bw, bh in g["buttons"]), (step, g)
            keep(page)
        done = bubble(page, 3).get_by_role("button", name=C["guide"]["done"], exact=True)
        box = done.bounding_box()
        assert box and box["y"] >= 0 and box["y"] + box["height"] <= h + 0.5, box
        assert page.evaluate("""([x, y]) => { const t = document.elementFromPoint(x, y); return !!t && !!t.closest('[data-ui-v2="guide-bubble"] button[data-ui="button"]'); }""",
                             [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2])
        done.click()
        guide_gone(page)
    R.check(page, S, "처음 안내 2/3 · 3/3: 말풍선이 밝힌 내 점수 칸(빛 테두리까지)을 덮지 않아요 · 칸 열 개와 회사 수 줄이 보여요 · 글 12px · 버튼 44px · 알겠어요가 눌려요", step23_clear)
    ctx.close()
    srv.shutdown()


def scene_v193c_offstep(R, files, width=390):
    """v19.3c: 안내 중에 기준 단계를 겹친 화면이 덮지 않는 길로 떠나면(화면 읽기 프로그램이 누른 다음 · 이전 단계 · 다시 시작) 안내는 끝나고
    '본 적 있음'이 남아요. 이전 단계로 돌아와도 말풍선이 다시 뜨지 않아요."""
    S = f"v19.3c 안내 밖 단계 이동 {width}"
    srv, ctx, page, base = R.open(build_site(files), width, guide_seen=False)
    seen = lambda: page.evaluate(SEEN_JS)                              # v19.3d: 본 표시는 저장 기록 안에 있어요
    unseen = lambda: forget_guide(page)

    def off_step():
        wait_ready(page)
        at(page, "home")
        guide_step1(page, False)
        page.locator('[data-card="div"] [data-ui-v2="card-inc"]').click()
        bubble(page, 2).click()
        bubble(page, 3)
        page.evaluate("() => document.querySelector('[data-ui-v2=\"action-bar\"] button:not([disabled])').click()")   # 3/3 에서 아래 띠의 다음
        see(page, C["build"]["s3"]["title"])
        guide_gone(page)
        assert seen() == "1"
        page.locator('[data-ui-v2="app-bar"]').get_by_role("button", name=C["build"]["prevStep"]).click()
        see(page, C["build"]["s1"]["title"])
        page.wait_for_timeout(400)
        assert page.locator('[data-ui-v2="guide-bubble"], [data-ui-v2="guide-shade"]').count() == 0, "이전 단계로 돌아오니 안내가 다시 떠요"
        for name in (C["build"]["restart"], C["build"]["prevStep"]):        # 1/3 에서 다시 시작 · 이전 단계 (말풍선 밖의 단추)
            unseen()
            guide_step1(page, False)
            page.evaluate("(n) => [...document.querySelectorAll('[data-ui-v2=\"app-bar\"] button, main button')].find((b) => (b.getAttribute('aria-label') || b.textContent.trim()) === n).click()", name)
            see(page, C["build"]["s0"]["title"])
            guide_gone(page)
            assert seen() == "1", name
            page.locator('[data-deck="income"]').click()                   # 템플릿을 골라도 2/3 이 저절로 뜨지 않아요
            see(page, C["build"]["s1"]["title"])
            page.wait_for_timeout(400)
            assert page.locator('[data-ui-v2="guide-bubble"]').count() == 0, name
        R.collect(page)
    R.check(page, S, "안내 중 다음(3/3) · 다시 시작 · 이전 단계(1/3)를 겹친 화면 밖에서 누르면 안내는 끝(본 적 있음) · 돌아와도 · 템플릿을 골라도 다시 안 떠요", off_step)
    ctx.close()
    srv.shutdown()


def scene_v193c_narrow(R, files, width=320):
    """v19.3c Part D: 320px 에서도 기준 카드는 두 칸이고, 카드 안의 글 · 버튼이 카드 밖으로 나가지 않아요 (가로 스크롤 없음)."""
    S = f"v19.3c 좁은 화면 {width}"
    srv, ctx, page, base = R.open(build_site(files), width)

    def two_cols():
        wait_ready(page)
        to_build_start(page, False)
        page.locator('[data-deck="krUs"]').click()                         # 고른 카드(상위 50% 칩 · 재무 안정 줄)도 함께
        see(page, C["build"]["s1"]["title"])
        cols = page.locator('[data-ui-v2="card-grid"]').evaluate("(e) => getComputedStyle(e).gridTemplateColumns.split(' ').length")
        assert cols == 2, cols
        spill = page.evaluate("""() => [...document.querySelectorAll('[data-card]')].flatMap((c) => {
            const r = c.getBoundingClientRect(); const out = [];
            if (c.scrollWidth > c.clientWidth + 0.5) out.push([c.dataset.card, 'scroll', c.scrollWidth, c.clientWidth]);
            for (const e of c.querySelectorAll('h3, p, span, button, svg')) { const b = e.getBoundingClientRect();
              if (b.width && (b.left < r.left - 0.5 || b.right > r.right + 0.5)) out.push([c.dataset.card, e.tagName, Math.round(b.left), Math.round(b.right), Math.round(r.left), Math.round(r.right)]); }
            return out; })""")
        assert not spill, spill[:5]
        floor_ok(page, "기준 카드 320")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "320px: 기준 카드 두 칸 · 카드 밖으로 나가는 글 · 버튼 없음 · 가로 스크롤 없음", two_cols)
    ctx.close()
    srv.shutdown()


def scene_v193c_empty(R, files, width=390):
    """v19.3c Part D: 기준 전의 수가 0 이면(모든 종목이 거래대금 바닥 아래) 내 점수 칸은 '지금 기준이면 남는 회사가 없어요'."""
    S = f"v19.3c 남는 회사 없음 {width}"
    low = clone(files)
    for s in low["data.json"]["stocks"]:
        if s.get("cls") == "kr":
            s["val20"] = 1.0
        elif s.get("cls") == "us":
            s["val"] = 1.0
    srv, ctx, page, base = R.open(build_site(low), width)

    def empty_pool():
        wait_ready(page)
        to_build_start(page, False)
        page.locator('[data-deck="blank"]').click()
        m = meter(page)
        assert m["pool"] and m["n"] == 0 and m["text"].strip() == C["build"]["s1"]["remainNone"], m
        R.collect(page)
    R.check(page, S, "기준 전의 수가 0: '지금 기준이면 남는 회사가 없어요' (0개라고 쓰지 않아요)", empty_pool)
    ctx.close()
    srv.shutdown()


def scene_v193c_first(R, files, devices):
    """v19.3c 첫 방문, 처음 안내가 저절로 뜨는 지금 (처음 안내를 본 적 없는 방문자):
    (a) data.json 이 없으면(404) 반기는 화면 없이 첫 방문 홈이 main 그대로 · 불러오기 실패 문구가 아래 탭 막대 위에 보여요 · '본 적 있음'은
        남지 않아요 · 메뉴의 처음 안내 다시 보기도 반기는 화면 없이 같은 화면 (320 × 568).
    (b) 아이폰 사파리 첫 방문(390 × 664): 반기는 화면과 아이폰 홈 화면 안내(첫 방문 꼴)가 같이 있어요.
    (c) 저장한 것 없이 baepsae.html 을 그냥 열면 2.0 의 반기는 화면으로 와요, 페이지 오류 0건."""
    S = "v19.3c 첫 방문"
    errs0 = len(R.errors)
    dev = {"viewport": {"width": 320, "height": 568}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True}
    srv, ctx, page, base = R.open(build_site(files, drop=("data.json",)), 320, device=dev, guide_seen=False)
    old_key = "() => { try { return localStorage.getItem('baepsae2.v1.guideSeen'); } catch (e) { return 'error'; } }"

    def failed_data():
        wait_ready(page)
        at(page, "home")
        page.wait_for_timeout(500)
        assert page.locator('[data-ui-v2="guide-welcome"]').count() == 0, "데이터를 못 읽었는데 반기는 화면이 떠요"
        page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")    # 첫 방문 홈 (main 그대로)
        msg = page.locator('[data-ui-v2="load-fail"] p')
        msg.wait_for(state="visible")
        assert msg.inner_text() == C["app"]["loadFail"]
        bar = page.locator('nav[data-ui="bottom-tab-bar"]').bounding_box()
        mb = msg.bounding_box()
        assert mb["y"] + mb["height"] <= bar["y"] + 0.5, (mb, bar)        # 아래 탭 막대에 가리지 않아요 (스크롤 없이)
        assert page.evaluate(SEEN_JS) is None and page.evaluate(old_key) is None, "보지 않은 안내가 '본 적 있음'으로 남았어요"
        R.collect(page)
        m = open_menu(page)                                                # 처음 안내 다시 보기: 데이터가 없으면 반기는 화면 없이 그대로
        m.locator('[data-ui-v2="menu-item"][data-item="guide"]').click()
        at(page, "home")
        page.wait_for_timeout(500)
        assert page.locator('[data-ui-v2="guide-welcome"]').count() == 0
        page.locator('[data-ui-v2="load-fail"] p').wait_for(state="visible")
        assert page.evaluate(SEEN_JS) is None and page.evaluate(old_key) is None
        R.collect(page)
    R.check(page, S, "(a) data.json 없음 · 320×568: 반기는 화면 없이 첫 방문 홈, 불러오기 실패 문구가 탭 막대 위에 보여요 · '본 적 있음' 없음 · 메뉴에서 다시 보기도 같아요",
            failed_data)
    ctx.close()
    srv.shutdown()

    iph = {k: v for k, v in devices["iPhone 13"].items() if k != "default_browser_type"}
    srv, ctx, page, base = R.open(build_site(files), iph["viewport"]["width"], device=iph, guide_seen=False)

    def iphone_first():
        wait_ready(page)
        at(page, "home")
        page.locator('[data-ui-v2="guide-welcome"]').wait_for(state="visible")
        hint = page.locator('[data-ui-v2="ios-hint"]')
        assert hint.evaluate_all("(els) => els.map((e) => e.dataset.kind)") == ["first"]
        if C["hint"]["first"]:
            assert C["hint"]["first"] in hint.inner_text()
        R.collect(page)
    R.check(page, S, "(b) 아이폰 사파리 첫 방문: 반기는 화면 + 아이폰 홈 화면 안내(첫 방문 꼴)", iphone_first)
    ctx.close()
    srv.shutdown()

    # (c) 는 실제 주소처럼 ?dev=1 없이 열어요: 그래서 app.html 이 자기 페이지뷰(GoatCounter)를 부르는데, 그건 smoke_launch.py 가 보는 일이라
    # 여기서는 바깥 요청을 조용히 막기만 하는 따로 된 문맥으로 열어요 (Runner 의 '다른 사이트 요청' 목록에 넣지 않게).
    srv, cvbase = serve(build_site(files))
    ctx = R.new_context(viewport={"width": 390, "height": 780}, device_scale_factor=2, locale="ko-KR", service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(cvbase) else r.abort())
    page = ctx.new_page()
    page.set_default_timeout(WAIT)
    cv_errors = []
    page.on("pageerror", lambda e: cv_errors.append(str(e)))
    page.goto(cvbase + "/baepsae.html", wait_until="domcontentloaded")
    R.saw_clock(page)

    def cv_link():
        page.wait_for_url("**/app.html**")
        wait_ready(page)
        at(page, "home")
        page.locator('[data-ui-v2="guide-welcome"]').wait_for(state="visible")
        assert "/app.html" in page.url and "from=app" not in page.url, page.url
        R.collect(page)
        assert not cv_errors and len(R.errors) == errs0, (cv_errors, R.errors[errs0:])
    R.check(page, S, "(c) 저장한 것 없이 baepsae.html → 2.0 의 반기는 화면, 페이지 오류 0건", cv_link)
    ctx.close()
    srv.shutdown()


def scene_v193c_on(R, files, width):
    """v19.3c 두 스위치를 켠 빌드(커밋하지 않는 임시 빌드): 첫 방문 홈 대신 반기는 화면이 저절로 → 그냥 둘러볼게요 → 첫 방문 홈 · 다시 열어도
    안 떠요. 새 시작 화면(BuildStart2 · PcStart2): 처음부터 카드(그림 다섯 · 기준 카드 고르기) · 가진 종목으로 시작하기(가진 종목 넣기를
    열어요, v19.3d) · 템플릿 여덟 개가 재료 줄(그림 · 이름 · 점 다섯, 큰 점수부터, 셋까지 + '+ {n}개 더') · 깐깐한 기준 · 한미 반반 표시 ·
    뱁이 없음."""
    S = f"v19.3c 스위치 켠 빌드 {width}"
    wide = width >= 1024
    srv, ctx, page, base = R.open(build_site(files, app=v193c_on_app()), width, device=pc_device(width) if wide else None, guide_seen=False)

    def auto_welcome():
        wait_ready(page)
        at(page, "home")
        page.locator('[data-ui-v2="guide-welcome"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="home-hero"]').count() == 0
        R.collect(page)
        page.locator('[data-ui-v2="guide-browse"]').click()
        page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")
        page.reload()
        wait_ready(page)
        page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="guide-welcome"]').count() == 0, "본 뒤에도 반기는 화면이 다시 떠요"
    R.check(page, S, "첫 방문: 반기는 화면이 저절로 (첫 방문 홈 대신) → 그냥 둘러볼게요 → 첫 방문 홈 · 다시 열면 안 떠요", auto_welcome)

    def start2():
        to_build_start(page, wide)
        st = page.locator('[data-ui-v2="build-start2"]')
        st.wait_for(state="visible")
        assert st.locator('img[src^="baepi-"]').count() == 0 and page.locator('[data-ui-v2="build-start"]').count() == 0     # 뱁이 없음
        blank = st.locator('[data-ui-v2="start-blank"]')
        assert blank.locator("img").count() == 5 and C["build"]["s0"]["blankBody"] in blank.inner_text()
        assert blank.locator('[data-deck="blank"]').inner_text().strip() == C["build"]["s0"]["pickCards"]
        hold = st.locator('[data-ui-v2="start-holdings"]')                # v19.3d: 가진 종목 넣기를 여는 단추 (준비 중 아님)
        assert C["build"]["s0"]["holdings"] in hold.inner_text() and C["build"]["s0"]["holdingsSub"] in hold.inner_text()
        assert C["build"]["s1"]["pendingCard"] not in hold.inner_text() and hold.evaluate("(e) => e.tagName") == "BUTTON"
        assert hold.locator("[data-deck]").count() == 0 and hold.get_attribute("data-deck") is None
        assert page.locator("[data-deck]").count() == 9
        got = pics(page, "[data-deck] [data-deck-pic]", "DECK_PICS")
        assert sorted(g["id"] for g in got) == sorted(PICS["DECK_PICS"]), got
        rows = page.locator('[data-deck="krUs"] [data-ingredient]').evaluate_all("(els) => els.map((e) => e.dataset.ingredient)")
        assert rows == ["profit", "value", "div"], rows                     # 3 · 2 · 2 · (2 · 1): 큰 점수부터, 같으면 엔진 순서
        assert fillp(C["build"]["s0"]["more"], n=2) in page.locator('[data-deck="krUs"]').inner_text()
        assert page.locator('[data-deck="krUs"] [data-ui-v2="recipe-badge"]').inner_text() == fillp(C["build"]["s0"]["badgeMix"], kr=50, us=50)
        assert page.locator('[data-deck="strict"] [data-ui-v2="recipe-badge"]').inner_text() == fillp(C["build"]["s0"]["badgeStrict"], top=30)
        assert page.locator('[data-ui-v2="recipe-badge"]').count() == 2
        assert C["build"]["s0"]["dotsNote"] in st.inner_text() and C["build"]["s0"]["recipes"] in st.inner_text()
        if wide:
            x, w, cols = page_box(page)
            assert cols == "2" and w > 720, (w, cols)
            assert page.locator('[data-ui-v2="recipe-grid"]').evaluate("(e) => getComputedStyle(e).gridTemplateColumns.split(' ').length") == 3
        floor_ok(page, "새 시작 화면")
        no_hscroll(page, width)
        R.collect(page)
        hold.click()                                                       # 가진 종목 넣기가 열려요 → 뒤로 → 시작 화면
        at(page, "portfolio/import")
        see(page, C["imp"]["title"])
        page.go_back()
        at(page, "portfolio/build")
        see(page, C["build"]["s0"]["title"])
        page.locator('[data-deck="strict"]').click()
        see(page, C["build"]["s1"]["title"])
        assert page.locator('[data-card="profit"]').get_attribute("data-points") == "4"
    R.check(page, S, "새 시작 화면: 처음부터 카드 · 가진 종목으로 시작하기(가진 종목 넣기가 열려요) · 템플릿 여덟 개의 재료 줄과 표시 · 뱁이 없음 · PC 두 칸(템플릿 세 칸)", start2)
    ctx.close()
    srv.shutdown()


# ── v19.3d: 가진 종목 넣기 → 기준 → 점검 (v19.3 Parts F · G · N.4) ──
FIN_INDS = ("bank", "insurance", "securities", "finance", "fin")
STORED_JS = "() => JSON.parse(localStorage.getItem('baepsae2.v1'))"


def won_text(won):
    """format.js wonText: 1만원부터 만원 단위 (반올림), 그 아래는 원."""
    a = abs(won)
    if a >= 10000:
        return f"{round(a / 10000):,}만원"
    return f"{round(a):,}원"


def card_raw(s, card):
    """engine.cardRaw (가치 · 배당 · 재무 안정): None = 빈칸, 'na' = 해당 없음 (금융회사의 재무 안정)."""
    if card == "stable" and s.get("ind") in FIN_INDS:
        return "na"
    if card == "value":
        return s.get("vz")
    if card == "stable":
        return s.get("debt")
    if s["cls"] == "us":
        return s.get("dy")
    return s["dps"] / s["price"] * 100 if kr_dps_agrees(s) and s.get("price") else None


def scene_v193d(R, files, width):
    """v19.3d (Part N.4): 포트폴리오 만들기 첫 단계의 '가진 종목으로 시작하기' → 삼성전자(수량 · 평균 단가) · 현대차(금액으로 넣기) · 미국 종목
    (소수 수량) · 우선주 → 붙여 넣기(종목을 못 찾은 줄 · 수량이 둘 이상인 줄 · 여러 종목에 맞는 이름: 확인 전에는 아무것도 넣지 않아요) →
    기준 → 점검(잘 맞아요 / 덜 맞아요 · 점수를 매길 수 없는 우선주의 이름 · 빈칸과 해당 없음은 빈 점이 아니에요 · 2022년 범위 · 규칙 네 칸) →
    매일 점검 시작하기 → 저장 기록 2판(평균 단가는 넣은 것만) → 포트폴리오 · 홈은 확인 필요 대신 포트폴리오 규칙 네 가지."""
    S = f"v19.3d {width}"
    wide = width >= 1024
    data = clone(files)
    by = {s["t"]: s for s in data["data.json"]["stocks"]}
    for t in ("005930", "005380", "AAPL", "005935", "000660"):          # PR #50 의 betaSE (시험 데이터에는 아직 없어요)
        by[t]["betaSE"] = 0.05
    fx = data["data.json"]["fx"]
    srv, ctx, page, base = R.open(build_site(data), width, device=pc_device(width) if wide else None)
    stored = lambda: page.evaluate(STORED_JS)
    picks = {"005930": ("qty", "10"), "005380": ("amount", "500"), "AAPL": ("qty", "3.5"), "005935": ("qty", "20")}

    def add(t, mode, val):
        page.locator('[data-ui-v2="import-search"] input').fill(t)
        page.locator(f'[data-import-result="{t}"] button').click()
        row = page.locator(f'[data-import-row="{t}"]')
        row.wait_for(state="visible")
        assert row.get_attribute("data-mode") == mode, (t, row.get_attribute("data-mode"))
        row.locator(f'input[data-ui-v2="import-{mode}"]').fill(val)

    def holdings():
        wait_ready(page)
        to_build_start(page, wide)
        page.locator('[data-ui-v2="start-holdings"]').click()
        at(page, "portfolio/import")
        assert page.locator('nav[data-ui="bottom-tab-bar"]').count() == 0
        see(page, C["imp"]["title"])
        assert page.locator('[data-ui-v2="import-search"] input').get_attribute("placeholder") == C["imp"]["search"]
        assert not action(page).is_enabled()                            # 아무것도 없으면 점검할 수 없어요
        page.locator('[data-ui-v2="import-search"] input').fill("없는회사이름")
        see(page, C["imp"]["none"])
        for t in ("005930", "AAPL", "005935"):
            add(t, *picks[t])
        page.locator('[data-ui-v2="import-mode"][data-mode="amount"]').click()            # 금액으로 넣기 → 그다음 담는 종목은 금액
        assert page.locator('[data-ui-v2="import-mode"][data-mode="amount"]').get_attribute("aria-pressed") == "true"
        add("005380", *picks["005380"])
        row = page.locator('[data-import-row="005930"]')
        row.locator('[data-ui-v2="import-add-avg"]').click()            # 평균 단가는 넣은 종목만
        row.locator('input[data-ui-v2="import-avg"]').fill("62100")
        page.locator('[data-import-row="AAPL"] input[data-ui-v2="import-qty"]').fill("3.12345")    # 미국 소수 다섯째 자리: 틀린 칸
        assert page.locator('[data-import-row="AAPL"] input[data-ui-v2="import-qty"]').get_attribute("aria-invalid") == "true"
        assert not action(page).is_enabled()
        page.locator('[data-import-row="AAPL"] input[data-ui-v2="import-qty"]').fill("3.5")
        page.locator('[data-import-row="005935"] input[data-ui-v2="import-qty"]').fill("1.5")     # 한국 소수 주식: 틀린 칸
        assert page.locator('[data-import-row="005935"] input[data-ui-v2="import-qty"]').get_attribute("aria-invalid") == "true"
        page.locator('[data-import-row="005935"] input[data-ui-v2="import-qty"]').fill("20")
        total = 10 * by["005930"]["price"] + 5000000 + 3.5 * by["AAPL"]["price"] * fx + 20 * by["005935"]["price"]
        assert page.locator('[data-ui-v2="import-total"]').inner_text() == won_text(total)
        assert page.locator('[data-ui-v2="import-donut"]').inner_text().count("%") == 4
        md = f"{int(data['data.json']['pxDate'][5:7])}월 {int(data['data.json']['pxDate'][8:])}일"
        assert page.locator('[data-ui-v2="import-date"]').inner_text() == fillp(C["imp"]["priceLine"], date=md, fx=f"{round(fx):,}")
        for t in ("005380", "AAPL", "005935"):
            assert page.locator(f'[data-import-row="{t}"] [data-ui-v2="import-add-avg"]').inner_text() == C["imp"]["addAvg"]   # 지어내지 않아요
        floor_ok(page, "가진 종목 넣기")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "가진 종목 넣기: 찾기 · 수량(한국 정수 · 미국 소수 넷째 자리까지) · 금액으로 넣기 · 평균 단가(선택) · 합계와 비중 · 날짜 줄", holdings)

    def paste():
        page.locator('[data-ui-v2="import-mode"][data-mode="paste"]').click()
        lines = ["SK하이닉스 2", "없는회사 5", "삼성전자 10 71,500 715,000", "삼성 3", "현대차 3"]
        text = "\n".join(lines)
        R.names = sorted(set(R.names) | {text, *lines}, key=len, reverse=True)   # 사용자가 붙여 넣은 글이에요 (문구 파일 밖)
        page.locator('[data-ui-v2="paste-panel"] textarea').fill(text)
        prev = page.locator('[data-ui-v2="paste-preview"]')
        prev.wait_for(state="visible")
        assert C["imp"]["previewTitle"] in prev.inner_text()
        assert page.locator("[data-import-row]").count() == 4             # 확인 전에는 아무것도 넣지 않아요
        st = {page.locator("[data-paste-line]").nth(i).get_attribute("data-paste-line"): page.locator("[data-paste-line]").nth(i).get_attribute("data-st")
              for i in range(page.locator("[data-paste-line]").count())}
        assert st == {"1": "ok", "2": "noStock", "3": "noQty", "4": "pick", "5": "amount"}, st      # 금액으로 넣은 현대차: 쓰지 않는 줄로 보여요
        assert fillp(C["imp"]["noStockLine"], n=2) in prev.inner_text() and "없는회사 5" in prev.inner_text()   # 그 줄을 회색으로
        assert fillp(C["imp"]["noQtyLine"], n=3) in prev.inner_text()
        assert fillp(C["imp"]["pick"], q="삼성") in prev.inner_text() and page.locator('[data-paste-line="4"] [data-pick]').count() >= 2
        floor_ok(page, "붙여 넣기 미리 보기")
        R.collect(page)
        page.locator('[data-ui-v2="paste-confirm"]').click()
        page.locator('[data-import-row="000660"]').wait_for(state="visible")
        assert page.locator("[data-import-row]").count() == 5 and page.locator('[data-import-row="000660"] input[data-ui-v2="import-qty"]').input_value() == "2"
        assert page.locator('[data-import-row="005380"]').get_attribute("data-mode") == "amount"
        assert page.locator('[data-import-row="005380"] input[data-ui-v2="import-amount"]').input_value() == "500"     # 금액 줄은 그대로
        assert page.locator('[data-ui-v2="paste-panel"]').count() == 0
    R.check(page, S, "붙여 넣기: 미리 보기 · 종목을 못 찾은 줄 · 수량이 둘 이상인 줄 · 여러 종목에 맞는 이름(고르기) · 이대로 넣기 뒤에만 들어가요", paste)

    def cards_and_report():
        action(page).click()
        see(page, C["build"]["s1"]["title"])
        assert action(page).inner_text() == C["build"]["pickCardsBtn"]
        for c in ("value", "value", "div", "div", "stable"):
            page.locator(f'[data-card="{c}"] [data-ui-v2="card-inc"]').click()
        action(page).click()
        page.locator('[data-ui-v2="report"]').wait_for(state="visible")
        rows = page.locator("[data-report-row]")
        scored = [rows.nth(i).get_attribute("data-report-row") for i in range(rows.count())]
        assert sorted(scored) == sorted(["005930", "005380", "AAPL", "000660"]), scored          # 우선주는 점수를 매길 수 없어요
        fit, less = int(page.locator('[data-ui-v2="report-fit"]').get_attribute("data-n")), int(page.locator('[data-ui-v2="report-less"]').get_attribute("data-n"))
        assert fit + less == 4
        assert page.locator('[data-ui-v2="report-headline"]').inner_text().replace("\n", " ") == fillp(C["rpt"]["head"], a=fit, b=less)
        assert page.locator('[data-ui-v2="report-unscored"]').inner_text() == fillp(C["rpt"]["unscored"], n=1, names="삼성전자우")
        mine = page.locator('[data-ui-v2="report-mine"]').inner_text()
        assert mine.startswith(C["rpt"]["mine"]) and fillp(C["build"]["s1"]["slot"], card=C["build"]["cards"]["value"]["name"], n=2) in mine
        for t in scored:                                                # 빈칸 → '–'(데이터 없음) · 해당 없음 → 글자, 둘 다 빈 점이 아니에요
            for c in ("value", "div", "stable"):
                dot = page.locator(f'[data-report-row="{t}"] [data-cell="{c}"] [data-dot]').get_attribute("data-dot")
                raw = card_raw(by[t], c)
                want = ("blank",) if raw is None else ("na",) if raw == "na" else ("full", "half", "empty")
                assert dot in want, (t, c, raw, dot)
                if dot == "blank":
                    assert page.locator(f'[data-report-row="{t}"] [data-cell="{c}"] [data-dot]').get_attribute("aria-label") == C["rpt"]["noData"]
        avgs = page.locator("[data-report-card]")
        assert avgs.count() == 3 and all(fillp(C["rpt"]["avgTop"], x="") .rstrip("%") in avgs.nth(i).inner_text() for i in range(3))
        line = page.locator('[data-ui-v2="y2022-line"]').inner_text()
        assert "~" in line and line.endswith(C["rpt"]["y2022Range"].rsplit(". ", 1)[1]), line   # Part O.1: 범위
        assert page.locator('[data-y2022="mine"]').count() == 1 and C["rpt"]["sp500Won"] in page.locator('[data-y2022="sp500"]').inner_text()
        tiles = {page.locator('[data-ui-v2="report"] [data-ui-v2="pf-rule"]').nth(i).get_attribute("data-rule"): page.locator('[data-ui-v2="report"] [data-ui-v2="pf-rule"]').nth(i).get_attribute("data-state")
                 for i in range(page.locator('[data-ui-v2="report"] [data-ui-v2="pf-rule"]').count())}
        assert set(tiles) == {"stock", "ind", "fit", "warn"} and tiles["warn"] == "unknown", tiles    # 미국 종목 → 재무 경고는 확인하지 못했어요
        assert C["pfr"]["unknown"] in page.locator('[data-ui-v2="pf-rule"][data-rule="warn"]').inner_text()
        assert page.locator('[data-ui-v2="screen"] img[src^="baepi-"]').count() == 0          # 숫자 화면: 뱁이 없음 (PC 왼쪽 메뉴의 로고 말고)
        floor_ok(page, "점검")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "기준 → 점검: 잘 맞아요 / 덜 맞아요 · 우선주 이름 · 빈칸과 해당 없음은 빈 점이 아님 · 평균 상위 % · 2022년 범위 · 규칙 네 칸", cards_and_report)

    def saved():
        page.locator('[data-ui-v2="report-start"]').click()
        at(page, "portfolio")
        d = stored()
        assert d["v"] == 2 and len(d["decks"]) == 1 and d["decks"][0]["kind"] == "imported"
        imp = {r["t"]: r for r in d["decks"][0]["imported"]}
        assert imp["005930"]["avg"] == 62100 and all("avg" not in imp[t] for t in ("005380", "AAPL", "005935", "000660"))   # 넣은 평균 단가만
        assert imp["005380"]["amountWon"] == 5000000 and imp["005380"]["close"] == by["005380"]["price"] and imp["005380"]["date"] == data["data.json"]["pxDate"]
        assert imp["AAPL"]["qty"] == 3.5 and imp["005935"].get("unscored") is True
        card = page.locator('[data-deck-id][data-kind="imported"]')
        card.wait_for(state="visible")
        assert card.locator('[data-ui-v2="pf-rule"]').count() == 4 and card.locator('[data-ui-v2="pf-kept"]').count() == 1
        assert card.locator("[data-status]").count() == 0 and C["daily"]["check"] not in card.inner_text()     # 확인 필요 대신 포트폴리오 규칙
        assert card.locator("[data-pf-holding]").count() == 5
        R.collect(page)
        tab(page, TABS["home"]) if not wide else side_tab(page, "home")
        at(page, "home")
        strip = page.locator('[data-ui-v2="home-block"]')
        strip.wait_for(state="visible")
        assert strip.locator('[data-ui-v2="home-rules"] [data-ui-v2="home-rule"]').count() == 4 and page.locator('[data-ui-v2="today-hero"]').count() == 0
        assert C["daily"]["check"] not in strip.inner_text() and page.locator('[data-ui-v2="today-empty"]').count() == 0
        floor_ok(page, "홈 (가진 종목)")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "매일 점검 시작하기 → 저장 기록 2판(평균 단가는 넣은 것만) → 포트폴리오 · 홈: 확인 필요 대신 포트폴리오 규칙 네 가지", saved)

    if not wide:
        def welcome_button():
            w = open_guide(page, wide)
            w.locator('[data-ui-v2="guide-holdings"] button').click()     # 반기는 화면의 두 번째 버튼
            at(page, "portfolio/import")
            see(page, C["imp"]["title"])
        R.check(page, S, "반기는 화면의 '가진 종목 넣기' → 가진 종목 넣기", welcome_button)
    ctx.close()
    srv.shutdown()


def scene_v193d_more(R, files, width=390):
    """v19.3d review: 점검 on stale data opens with '데이터가 {n}일째 갱신되지 않았어요. {date} 종가 기준 결과예요.' · 379800 KODEX
    미국S&P500 (cls "us" but a KRX listing in won) is 한국, whole shares, valued without the exchange rate · #portfolio/import with
    data.json missing shows the load-failure message · records an earlier-app tab moved aside are merged back with
    '다른 창에서 저장한 내용과 기록을 합쳤어요. 기록을 한 번 확인해 주세요.' on 포트폴리오 and 홈 · a copy that would not read
    back merged stays where it is, with '이전에 저장한 기록을 읽지 못해 따로 보관해 두었어요.' (review round 3)."""
    S = f"v19.3d 더 {width}"
    stale = clone(files)
    for n in DATA_FILES:
        stale[n]["publishedAt"] = now_kst(days_ago=6)
    by = {s["t"]: s for s in stale["data.json"]["stocks"]}
    srv, ctx, page, base = R.open(build_site(stale), width, path="/app.html?dev=1#portfolio/import")

    def stale_report():
        page.locator('[data-ui-v2="import-search"]').wait_for(state="visible")
        for t, q in (("005930", "10"), ("379800", "10")):
            page.locator('[data-ui-v2="import-search"] input').fill(t)
            page.locator(f'[data-import-result="{t}"] button').click()
            page.locator(f'[data-import-row="{t}"] input[data-ui-v2="import-qty"]').fill(q)
        row = page.locator('[data-import-row="379800"]')
        assert row.locator('[data-ui-v2="import-market"]').inner_text() == C["pick"]["market"]["kr"], row.inner_text()   # 한국 상장
        assert row.locator('[data-ui-v2="import-value"]').inner_text() == won_text(10 * by["379800"]["price"])     # 환율을 곱하지 않아요
        row.locator('input[data-ui-v2="import-qty"]').fill("1.5")                                              # 원화 상장: 정수 주식만
        assert row.locator('input[data-ui-v2="import-qty"]').get_attribute("aria-invalid") == "true"
        row.locator('input[data-ui-v2="import-qty"]').fill("10")
        action(page).click()
        page.locator('[data-card="value"] [data-ui-v2="card-inc"]').click()
        action(page).click()
        note = page.locator('[data-ui-v2="report-stale"]')
        note.wait_for(state="visible")
        md = f"{int(stale['data.json']['pxDate'][5:7])}월 {int(stale['data.json']['pxDate'][8:])}일"
        assert note.inner_text() == fillp(C["rpt"]["stale"], n=6, date=md), note.inner_text()
        floor_ok(page, "점검 (멈춘 데이터)")
        R.collect(page)
        page.locator('[data-ui-v2="report-start"]').click()
        at(page, "portfolio")
        rec = {r["t"]: r for r in page.evaluate(STORED_JS)["decks"][0]["imported"]}
        assert rec["379800"]["ccy"] == "KRW" and rec["379800"]["qty"] == 10 and rec["005930"]["ccy"] == "KRW"
    R.check(page, S, "멈춘 데이터의 점검: 첫 줄이 '데이터가 {n}일째 갱신되지 않았어요…' · 379800 은 한국 · 정수 · 원화 (환율 곱하지 않음)", stale_report)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(files, drop=("data.json",)), width, path="/app.html?dev=1#portfolio/import")

    def import_fail():
        page.locator('[data-ui-v2="load-fail"]').wait_for(state="visible")
        assert C["app"]["loadFail"] in page.locator('[data-ui-v2="load-fail"]').inner_text()
        assert page.locator('[data-ui-v2="import-search"]').count() == 0
        R.collect(page)
    R.check(page, S, "#portfolio/import 에서 data.json 을 못 읽으면 불러오기 실패 문구 (빈 화면 · 예시 없음)", import_fail)
    ctx.close()
    srv.shutdown()

    pxd = files["data.json"]["pxDate"]
    moved = {"v": 2, "decks": [{"id": "dmoved", "name": "포트폴리오", "createdAt": pxd, "kind": "imported",
                                "settings": {"points": {"value": 2}, "strict": "normal"},
                                "holdings": [{"t": "005930", "nk": "삼성전자", "cls": "kr"}], "purchases": [],
                                "imported": [{"t": "005930", "nk": "삼성전자", "ccy": "KRW", "qty": 3}]}]}
    seed = ("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            f" localStorage.setItem('baepsae2.v1.unreadable.1700000000000', {json.dumps(json.dumps(moved, ensure_ascii=False))});"
            " localStorage.setItem('baepsae2.v1', JSON.stringify({ v: 1, decks: [] })); })();")
    srv, ctx, page, base = R.open(build_site(files), width, init=seed, path="/app.html?dev=1#portfolio")

    def merged_notice():
        at(page, "portfolio")
        note = page.locator('[data-ui-v2="store-merged"]')
        note.wait_for(state="visible")
        assert note.inner_text() == C["store"]["merged"]
        assert page.locator('[data-deck-id="dmoved"][data-kind="imported"]').count() == 1
        stored = page.evaluate(STORED_JS)
        assert stored["v"] == 2 and [d["id"] for d in stored["decks"]] == ["dmoved"]
        assert page.evaluate("() => Object.keys(localStorage).filter((k) => k.includes('.restored.')).length") == 1
        R.collect(page)
        tab(page, TABS["home"])
        at(page, "home")
        page.locator('[data-ui-v2="store-merged"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, S, "예전 앱 창이 옮겨 둔 2판 기록: 되돌려 합치고 '다른 창에서 저장한 내용과 기록을 합쳤어요…' (포트폴리오 · 홈)", merged_notice)
    ctx.close()
    srv.shutdown()

    # 리뷰 3차 4: 합치면 읽히지 않는 사본 (한 창에서 뺀 종목을 다른 창에서 또 팔았어요) — 그대로 두고 '따로 보관해 두었어요'
    row = lambda q: {"t": "005930", "nk": "삼성전자", "ccy": "KRW", "qty": q}
    sale1 = {"t": "005930", "qty": 1, "price": 50000, "date": pxd, "ccy": "KRW"}
    deck0 = {"id": "dtk", "name": "포트폴리오", "createdAt": pxd, "kind": "imported", "settings": {"points": {"value": 2}, "strict": "normal"},
            "holdings": [{"t": "005930", "nk": "삼성전자", "cls": "kr"}, {"t": "005380", "nk": "현대차", "cls": "kr"}], "purchases": [],
            "imported": [row(3), {"t": "005380", "nk": "현대차", "ccy": "KRW", "qty": 2}], "sales": [sale1]}
    taken = {**deck0, "holdings": deck0["holdings"][1:], "imported": deck0["imported"][1:], "sales": [],
             "history": [{"t": "005930", "nk": "삼성전자", "out": pxd, "cls": "kr", "imported": row(3), "purchases": [], "sales": [sale1], "divs": []}]}
    stale_copy = {**deck0, "sales": [sale1, {**sale1, "id": "late-sale1"}]}
    seed = ("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            f" localStorage.setItem('baepsae2.v1.other.1700000000000', {json.dumps(json.dumps({'v': 2, 'decks': [stale_copy]}, ensure_ascii=False))});"
            f" localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps({'v': 2, 'decks': [taken]}, ensure_ascii=False))}); }})();")
    srv, ctx, page, base_url = R.open(build_site(files), width, init=seed, path="/app.html?dev=1#portfolio")

    def unmerged_notice():
        at(page, "portfolio")
        note = page.locator('[data-ui-v2="store-unmerged"]')
        note.wait_for(state="visible")
        assert note.inner_text() == C["store"]["locked"]
        assert page.locator('[data-ui-v2="store-merged"]').count() == 0
        assert page.evaluate("() => localStorage.getItem('baepsae2.v1.other.1700000000000') !== null")   # 그대로 남아요
        assert [h["t"] for h in page.evaluate(STORED_JS)["decks"][0]["holdings"]] == ["005380"]
        R.collect(page)
        tab(page, TABS["home"])
        at(page, "home")
        page.locator('[data-ui-v2="store-unmerged"]').wait_for(state="visible")
        R.collect(page)
    R.check(page, S, "합치면 읽히지 않는 다른 창의 사본: 그대로 두고 '이전에 저장한 기록을 읽지 못해 따로 보관해 두었어요' (포트폴리오 · 홈)", unmerged_notice)
    ctx.close()
    srv.shutdown()


def scene_v193d2(R, files, width):
    """v19.3d2: 가진 종목 넣기 단계 표시(종목 넣기 · 기준 · 점검) · 수량과 금액 옆의 − / +(읽기 도우미 이름) · 금액으로 넣은 종목과 같은
    붙여 넣은 줄 · '+ 종목 더하기'(데이터에 없는 종목을 이름과 금액으로) → 점검: 반도체 · 반도체 장비 · 전자부품을 한 묶음(반도체·전자부품)
    으로 · 2022년 주가가 없는 종목을 이름으로 → 포트폴리오: 내 규칙 정하기(한도 저장 · 처음 값으로 되돌리기 · 범위 밖은 저장할 수 없어요)
    → 다 판 종목은 '다 팔고 목표 비중만 남아 있어요.'(계획한 n종목 중 … 은 나오지 않아요). R.shots 가 있으면 화면을 찍어 둬요."""
    S = f"v19.3d2 {width}"
    wide = width >= 1024
    data = clone(files)
    by = {s["t"]: s for s in data["data.json"]["stocks"]}
    by["000990"].update(ind="semi_eq", indName="반도체 장비")              # 시험 데이터에 없는 두 업종을 한 종목씩
    by["080220"].update(ind="elec_parts", indName="전자부품")
    for t in ("005930", "000990", "080220", "005380"):                   # 2022년 추정에 쓰는 betaSE
        by[t]["betaSE"] = 0.05
    # 삼성전자우는 2022년 주가가 있지만 쓸 수 있는 베타가 없어요 (betaSE 없음): #83 의 '베타·변동성 자료가 없어요' 줄(비중)로 빠져요.
    # 2022년 주가가 없는 종목은 이름으로 넣은 '비상장 회사' 하나뿐이에요.
    by["005935"].pop("betaSE", None)
    srv, ctx, page, base = R.open(build_site(data), width, device=pc_device(width) if wide else None)
    stored = lambda: page.evaluate(STORED_JS)

    def shot(name):
        if R.shots:
            os.makedirs(R.shots, exist_ok=True)
            page.screenshot(path=os.path.join(R.shots, f"v193d2-{name}-{width}.png"), full_page=True)

    def add(t, mode, val):
        page.locator('[data-ui-v2="import-search"] input').fill(t)
        page.locator(f'[data-import-result="{t}"] button').click()
        row = page.locator(f'[data-import-row="{t}"]')
        row.wait_for(state="visible")
        assert row.get_attribute("data-mode") == mode, (t, row.get_attribute("data-mode"))
        row.locator(f'input[data-ui-v2="import-{mode}"]').fill(val)

    def holdings():
        wait_ready(page)
        to_build_start(page, wide)
        page.locator('[data-ui-v2="start-holdings"]').click()
        at(page, "portfolio/import")
        steps = page.locator('[data-ui-v2="import-steps"] li')
        assert [steps.nth(i).inner_text() for i in range(steps.count())] == C["imp"]["steps"]
        assert steps.nth(0).get_attribute("aria-current") == "step"
        for t, q in (("005930", "4"), ("000990", "10"), ("080220", "15"), ("005935", "10")):
            add(t, "qty", q)
        row = page.locator('[data-import-row="005930"]')
        plus, minus = row.locator('[data-ui-v2="import-step"]').nth(1), row.locator('[data-ui-v2="import-step"]').nth(0)
        assert plus.get_attribute("aria-label") == fillp(C["imp"]["qtyUp"], name="삼성전자")
        assert minus.get_attribute("aria-label") == fillp(C["imp"]["qtyDown"], name="삼성전자")
        plus.click()
        assert row.locator('input[data-ui-v2="import-qty"]').input_value() == "5"
        minus.click()
        minus.click()
        assert row.locator('input[data-ui-v2="import-qty"]').input_value() == "3"
        plus.click()
        assert row.locator('input[data-ui-v2="import-qty"]').input_value() == "4"
        page.locator('[data-ui-v2="import-mode"][data-mode="amount"]').click()
        add("005380", "amount", "200")
        arow = page.locator('[data-import-row="005380"]')
        aplus = arow.locator('[data-ui-v2="import-step"]').nth(1)
        assert aplus.get_attribute("aria-label") == fillp(C["imp"]["amountUp"], name="현대차")
        assert arow.locator('[data-ui-v2="import-step"]').nth(0).get_attribute("aria-label") == fillp(C["imp"]["amountDown"], name="현대차")
        aplus.click()
        assert arow.locator('input[data-ui-v2="import-amount"]').input_value() == "210"           # 10만원씩
        arow.locator('[data-ui-v2="import-step"]').nth(0).click()
        assert arow.locator('input[data-ui-v2="import-amount"]').input_value() == "200"
        btn = page.locator('[data-ui-v2="import-add-name"] button')
        assert btn.inner_text() == C["imp"]["addName"]
        btn.click()
        nrow = page.locator('[data-import-row="name"]')
        nrow.wait_for(state="visible")
        assert not action(page).is_enabled()                              # 이름과 금액이 없으면 아직 점검할 수 없어요
        # 리뷰: 이름 없이 금액(다섯 자리)만 → 합계 · 고리에서 빠지고, 이름 칸이 표시되고, 버튼 이름은 '종목 …', 다음은 기다려요
        nrow.locator('input[data-ui-v2="import-amount"]').fill("12345")
        name_in = nrow.locator('input[data-ui-v2="import-name"]')
        assert name_in.get_attribute("aria-invalid") == "true" and not action(page).is_enabled()
        assert nrow.locator('[data-ui-v2="import-value"]').count() == 0
        assert re.search(r"\bn[0-9a-z]{6,}", page.locator('[data-ui-v2="import-donut"]').inner_text()) is None     # 내부 키가 보이지 않아요
        word = C["app"]["tabs"]["stocks"]
        assert nrow.locator('[data-ui-v2="import-step"]').nth(0).get_attribute("aria-label") == fillp(C["imp"]["amountDown"], name=word)
        assert nrow.locator('[data-ui-v2="import-step"]').nth(1).get_attribute("aria-label") == fillp(C["imp"]["amountUp"], name=word)
        assert nrow.locator('[data-ui-v2="import-remove"]').get_attribute("aria-label") == fillp(C["build"]["s4"]["removeAria"], name=word)
        # 다섯 자리 금액이 칸 안에 다 보이고, − 칸 + · 만원 · 빼기가 겹치거나 줄 밖으로 나가지 않아요 (320px 에서도)
        amt = nrow.locator('input[data-ui-v2="import-amount"]')
        assert amt.evaluate("e => e.scrollWidth <= e.clientWidth"), "다섯 자리 금액이 잘려요"
        rb = nrow.bounding_box()
        boxes = {k: nrow.locator(f'[data-ui-v2="{k}"]').first.bounding_box() for k in ("import-stepper", "import-unit", "import-remove")}
        for k, b in boxes.items():
            assert b["x"] >= rb["x"] - 0.5 and b["x"] + b["width"] <= rb["x"] + rb["width"] + 0.5, (k, b, rb)
        def apart(a, b):
            return a["x"] + a["width"] <= b["x"] + 0.5 or b["x"] + b["width"] <= a["x"] + 0.5 or a["y"] + a["height"] <= b["y"] + 0.5 or b["y"] + b["height"] <= a["y"] + 0.5
        assert apart(boxes["import-unit"], boxes["import-remove"]) and apart(boxes["import-stepper"], boxes["import-remove"]) and apart(boxes["import-stepper"], boxes["import-unit"]), boxes
        for b in nrow.locator('[data-ui-v2="import-step"]').all():
            bb = b.bounding_box()
            assert bb["width"] >= 44 - 0.5 and bb["height"] >= 44 - 0.5, bb             # 누르는 곳 44px
        # 이미 넣은 종목의 코드: 그 종목으로 바꾸지 않고 이름 칸이 표시돼요 (다음은 기다려요)
        name_in.fill("005930")
        name_in.press("Tab")
        assert page.locator('[data-import-row="name"]').count() == 1 and name_in.get_attribute("aria-invalid") == "true" and not action(page).is_enabled()
        # 데이터에 있는 종목의 코드를 정확히 쓰면, 칸을 떠날 때 그 종목의 줄이 돼요 (금액으로, 쓴 금액 그대로)
        name_in.fill("000660")
        name_in.press("Tab")
        hy = page.locator('[data-import-row="000660"]')
        hy.wait_for(state="visible")
        assert page.locator('[data-import-row="name"]').count() == 0 and hy.get_attribute("data-mode") == "amount"
        assert hy.locator('input[data-ui-v2="import-amount"]').input_value() == "12345"
        hy.locator('[data-ui-v2="import-remove"]').click()                       # 이 장면의 나머지는 그대로 (빼요)
        assert page.locator('[data-import-row="000660"]').count() == 0
        # 리뷰 2: 코드를 쓰고 바로 같은 줄의 금액 칸을 누르면, 줄이 그 종목이 되어도 그 자리에 있고 초점과 쓴 숫자가 남아요
        btn.click()
        nrow = page.locator('[data-import-row="name"]')
        nrow.wait_for(state="visible")
        nrow.locator('input[data-ui-v2="import-name"]').click()
        page.keyboard.type("msft")
        nrow.locator('input[data-ui-v2="import-amount"]').click()
        page.keyboard.type("300")
        ms = page.locator('[data-import-row="MSFT"]')
        ms.wait_for(state="visible")
        assert page.locator('[data-import-row="name"]').count() == 0 and ms.locator('input[data-ui-v2="import-amount"]').input_value() == "300"
        assert ms.locator('input[data-ui-v2="import-amount"]').evaluate("e => e === document.activeElement"), "초점이 금액 칸에 없어요"
        ms.locator('[data-ui-v2="import-remove"]').click()
        assert page.locator('[data-import-row="MSFT"]').count() == 0
        btn.click()
        nrow = page.locator('[data-import-row="name"]')
        nrow.wait_for(state="visible")
        R.names = sorted(set(R.names) | {"비상장 회사"}, key=len, reverse=True)   # 사용자가 넣은 이름이에요 (문구 파일 밖)
        nrow.locator('input[data-ui-v2="import-name"]').fill("비상장 회사")
        nrow.locator('input[data-ui-v2="import-amount"]').fill("100")
        assert nrow.locator('[data-ui-v2="import-add-avg"]').count() == 0     # 이름만 넣은 종목은 금액만
        assert action(page).is_enabled()
        page.locator('[data-ui-v2="import-mode"][data-mode="paste"]').click()
        lines = ["현대차 3"]
        R.names = sorted(set(R.names) | set(lines), key=len, reverse=True)
        page.locator('[data-ui-v2="paste-panel"] textarea').fill("\n".join(lines))
        prev = page.locator('[data-ui-v2="paste-preview"]')
        prev.wait_for(state="visible")
        assert page.locator('[data-paste-line="1"]').get_attribute("data-st") == "amount"
        assert fillp(C["imp"]["amountLine"], n=1) in prev.inner_text() and "현대차 3" in prev.inner_text()
        floor_ok(page, "가진 종목 넣기 (v19.3d2)")
        no_hscroll(page, width)
        R.collect(page)
        shot("holdings")
        page.locator('[data-ui-v2="import-mode"][data-mode="paste"]').click()     # 붙여 넣기를 닫아요 (넣지 않았어요)
    R.check(page, S, "단계 표시 · − / +(1주 · 10만원, 읽기 도우미 이름) · 금액으로 넣은 종목과 같은 줄 · '+ 종목 더하기'(이름과 금액)", holdings)

    def report():
        action(page).click()
        steps = page.locator('[data-ui-v2="import-steps"] li')
        assert steps.nth(1).get_attribute("aria-current") == "step"
        for c in ("value", "value", "div", "div", "stable"):
            page.locator(f'[data-card="{c}"] [data-ui-v2="card-inc"]').click()
        action(page).click()
        page.locator('[data-ui-v2="report"]').wait_for(state="visible")
        legend = page.locator('[data-ui-v2="ind-legend"]').inner_text()
        assert C["rpt"]["chipGroup"] in legend and "반도체 장비" not in legend and "전자부품 " not in legend.replace(C["rpt"]["chipGroup"], ""), legend
        ind = page.locator('[data-ui-v2="report"] [data-ui-v2="pf-rule"][data-rule="ind"]')
        assert C["rpt"]["chipGroup"] in ind.inner_text(), ind.inner_text()
        out = page.locator('[data-ui-v2="y2022-out"]')
        assert out.inner_text() == fillp(C["rpt"]["y2022Out"], n=1, names="비상장 회사"), out.inner_text()
        total = 4 * by["005930"]["price"] + 10 * by["000990"]["price"] + 15 * by["080220"]["price"] + 10 * by["005935"]["price"] + 2000000 + 1000000
        share = 10 * by["005935"]["price"] / total * 100                  # 삼성전자우의 비중 (deckcalc.js missingPct 처럼)
        pct = f"{math.floor(share + 0.5):,}" if share >= 1 else f"{max(share, 0.1):.1f}"
        part = page.locator('[data-ui-v2="y2022-partial"]')
        assert part.inner_text() == fillp(C["plan"]["riskPartial"], pct=pct), (part.inner_text(), pct)
        assert page.locator('[data-ui-v2="report-unscored"]').inner_text() == fillp(C["rpt"]["unscored"], n=2, names="삼성전자우, 비상장 회사")
        floor_ok(page, "점검 (v19.3d2)")
        no_hscroll(page, width)
        R.collect(page)
        shot("report")
    R.check(page, S, "점검: 반도체 · 반도체 장비 · 전자부품 = 반도체·전자부품 한 묶음 · 2022년 주가가 없는 종목 이름 · 이름만 넣은 종목도 비중에", report)

    def limits():
        page.locator('[data-ui-v2="report-start"]').click()
        at(page, "portfolio")
        d = stored()
        named = [r for r in d["decks"][0]["imported"] if "t" not in r]
        assert named == [{"nk": "비상장 회사", "ccy": "KRW", "amountWon": 1000000, "date": named[0]["date"], "unscored": True}], named
        card = page.locator('[data-deck-id][data-kind="imported"]')
        card.wait_for(state="visible")
        assert C["rpt"]["chipGroup"] in card.locator('[data-ui-v2="pf-rule"][data-rule="ind"]').inner_text()
        card.locator('[data-ui-v2="pf-rules-edit"] button').click()
        at(page, "portfolio/rules/" + d["decks"][0]["id"])
        see(page, C["lim"]["title"])
        assert page.locator('[data-ui-v2="app-bar"] button').first.get_attribute("aria-label") == C["co"]["back"]     # 단계가 아니에요
        assert page.locator('[data-ui-v2="store-refused"]').count() == 0
        see(page, C["lim"]["sub"])
        stock, ind = page.locator('[data-ui-v2="limit-stock"]'), page.locator('[data-ui-v2="limit-ind"]')
        assert stock.input_value() == "30" and ind.input_value() == "35"
        assert stock.get_attribute("aria-label") == fillp(C["pfr"]["stock"], x=30)
        assert page.locator('[data-ui-v2="limit-line-ind"]').inner_text() == fillp(C["pfr"]["ind"], x=35)
        R.collect(page)
        shot("limits")
        stock.fill("0")                                                     # 범위 밖: 저장할 수 없어요
        assert stock.get_attribute("aria-invalid") == "true" and page.locator('[data-ui-v2="limits-save"] button').is_disabled()
        stock.fill("40")
        ind.fill("50")
        page.locator('[data-ui-v2="limits-reset"]').click()
        assert stock.input_value() == "30" and ind.input_value() == "35"   # 처음 값 (저장 전)
        stock.fill("40")
        ind.fill("50")
        page.locator('[data-ui-v2="limits-save"] button').click()
        at(page, "portfolio")
        dk = stored()["decks"][0]
        assert dk["limits"] == {"stock": 40, "ind": 50} and isinstance(dk.get("limitsTs"), int) and dk["limitsTs"] > 0, dk.get("limits")
        side = page.evaluate("JSON.parse(localStorage.getItem('baepsae2.v1.limits'))")          # 기록 옆에도 (리뷰 3)
        assert side == {"v": 1, "decks": {dk["id"]: {"limits": {"stock": 40, "ind": 50}, "ts": dk["limitsTs"]}}}, side
        card = page.locator('[data-deck-id][data-kind="imported"]')
        assert fillp(C["pfr"]["stock"], x=40) in card.locator('[data-ui-v2="pf-rule"][data-rule="stock"]').inner_text()
        assert fillp(C["pfr"]["ind"], x=50) in card.locator('[data-ui-v2="pf-rule"][data-rule="ind"]').inner_text()
        # 처음 값으로 되돌리기 → 저장: the values go, the time of the 저장 stays (a merge keeps the latest 저장)
        card.locator('[data-ui-v2="pf-rules-edit"] button').click()
        assert page.locator('[data-ui-v2="limit-stock"]').input_value() == "40"
        page.locator('[data-ui-v2="limits-reset"]').click()
        page.locator('[data-ui-v2="limits-save"] button').click()
        at(page, "portfolio")
        dk2 = stored()["decks"][0]
        assert "limits" not in dk2 and dk2["limitsTs"] >= dk["limitsTs"], dk2.get("limits")
        card = page.locator('[data-deck-id][data-kind="imported"]')
        assert fillp(C["pfr"]["stock"], x=30) in card.locator('[data-ui-v2="pf-rule"][data-rule="stock"]').inner_text()
        # 리뷰 4: 이미 저장된 한도의 시각이 1시간 앞(빨랐던 시계)이면, 다음 저장은 그보다 꼭 1 뒤 (limits.jsx → store.js limitsSaveTime)
        ahead = page.evaluate("""() => { const d = JSON.parse(localStorage.getItem('baepsae2.v1')); const t = Date.now() + 3600 * 1000;
          d.decks[0].limitsTs = t; d.decks[0].limits = { stock: 45 }; delete d.wts; localStorage.setItem('baepsae2.v1', JSON.stringify(d)); return t; }""")
        page.reload(wait_until="domcontentloaded")
        wait_ready(page)
        card = page.locator('[data-deck-id][data-kind="imported"]')
        card.wait_for(state="visible")
        card.locator('[data-ui-v2="pf-rules-edit"] button').click()
        assert page.locator('[data-ui-v2="limit-stock"]').input_value() == "45"
        page.locator('[data-ui-v2="limit-stock"]').fill("50")
        page.locator('[data-ui-v2="limits-save"] button').click()
        at(page, "portfolio")
        dk3 = stored()["decks"][0]
        assert dk3["limits"] == {"stock": 50} and dk3["limitsTs"] == ahead + 1, (dk3.get("limits"), dk3.get("limitsTs"), ahead)
        # a portfolio that is not a 가진 종목 one, or no portfolio: the address opens 포트폴리오
        page.evaluate("location.hash = '#portfolio/rules/nope'")
        page.locator('[data-deck-id][data-kind="imported"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="limits"]').count() == 0
        floor_ok(page, "내 규칙 정하기")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "내 규칙 정하기: 지금 한도 → 범위 밖은 저장 못 함 · 처음 값으로 되돌리기 · 저장 → 규칙이 새 한도로", limits)
    ctx.close()
    srv.shutdown()

    # 다 판 종목 (팔았어요 기록은 v19.6a 부터 화면에서: 여기서는 저장 기록으로)
    pxd = files["data.json"]["pxDate"]
    band = lambda t: [{"id": "band", "kind": "band", "check": "checked", "target": t, "bands": [0.75 * t, 1.25 * t, 1.4 * t]}]
    deck = {"id": "dsold", "name": "배당 생활비 포트폴리오", "createdAt": pxd,
            "holdings": [{"t": "005930", "nk": "삼성전자", "target": 0.5, "plannedQty": 10, "rules": band(0.5)},
                         {"t": "005380", "nk": "현대차", "target": 0.5, "plannedQty": 10, "rules": band(0.5)}],
            "purchases": [{"t": "005930", "date": pxd, "qty": 10, "price": 225000, "ccy": "KRW"},
                          {"t": "005380", "date": pxd, "qty": 10, "price": 282000, "ccy": "KRW"}],
            "sales": [{"t": "005380", "qty": 10, "price": 282000, "date": pxd, "ccy": "KRW"}]}
    seed = ("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            f" localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps({'v': 2, 'decks': [deck], 'guideSeen': pxd}, ensure_ascii=False))}); }})();")
    srv, ctx, page, base = R.open(build_site(files), width, init=seed, path="/app.html?dev=1#portfolio", device=pc_device(width) if wide else None)

    def sold_out():
        at(page, "portfolio")
        line = page.locator('[data-sold-out="005380"]')
        line.wait_for(state="visible")
        assert C["daily"]["soldOut"] in line.inner_text() and "현대차" in line.inner_text()
        assert page.locator('[data-ui-v2="rebased-note"]').count() == 0      # '계획한 n종목 중 m종목만 샀어요' 가 아니에요
        floor_ok(page, "다 판 종목")
        no_hscroll(page, width)
        R.collect(page)
        shot("sold-out")
    R.check(page, S, "다 판 종목: '다 팔고 목표 비중만 남아 있어요.' · 다시 나눈 목표 비중 안내(계획한 n종목 중 …)는 나오지 않아요", sold_out)
    ctx.close()
    srv.shutdown()


# ── v19.3e: 홈 (Part H, board Home2) · 회사 페이지 고침 (Part I) · 수락 조건 5 ──
# Jack (2026-11-08): 새 홈(today.jsx HOME2)과 미국 머리줄(cofmt.js US_HEAD2)을 켰어요. 포트폴리오 규칙 네 가지는 가진 종목 넣기로 만든
# 포트폴리오에만 써요: 포트폴리오 만들기로 만든 포트폴리오는 맨 위 판정 띠(종목별 규칙 · 비중 띠)로 예전처럼 보여요.


def rgb(hexc):
    return "rgb(%d, %d, %d)" % tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5))


with open(os.path.join(ROOT, "src", "ui", "tokens.js"), encoding="utf-8") as _f:
    HOLDING_SHADES = re.findall(r'"(#[0-9A-F]{6})"', _f.read().split("export const HOLDING_SHADES = [", 1)[1].split("]", 1)[0])
assert len(HOLDING_SHADES) == 6, HOLDING_SHADES


def e_store(decks):
    return f"(() => {{ try {{ localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps({'v': 2, 'decks': decks}, ensure_ascii=False))}); }} catch (e) {{}} }})();"


def no_claim_pf(page, head, md):
    """가진 종목 포트폴리오 줄의 규칙 머리(pfview.jsx RulesHead: 포트폴리오 탭 · 스위치를 끈 홈)에서 아무 규칙도 확인하지 못했을 때: 네 칸
    모두 확인하지 못했어요 · '{date} 종가로 점검했어요' · '내 규칙 {n}개 중 {k}개를 지키고 있어요' · ✓ 없음, '…규칙이 4개 있어요'만."""
    st = head.locator('[data-ui-v2="pf-rule"]').evaluate_all("els => els.map((e) => e.dataset.rule + ':' + e.dataset.state)")
    assert st == ["stock:unknown", "ind:unknown", "fit:unknown", "warn:unknown"], st
    assert head.get_attribute("data-checked") == "0" and head.get_attribute("data-kept") == "0"
    assert head.locator('[data-ui-v2="pf-checked"], [data-ui-v2="pf-kept"]').count() == 0
    body = page.locator("body").inner_text()
    assert fillp(C["pfr"]["checked"], date=md) not in body and C["pfr"]["checked"].split("{date}")[1] not in body, "점검하지 못했는데 '점검했어요'"
    assert C["pfr"]["kept"].split("{k}")[1] not in body
    assert head.locator(f'[aria-label="{C["daily"]["ok"]}"]').count() == 0
    assert head.locator('[data-ui-v2="pf-not-checked"]').inner_text() == fillp(C["daily"]["notChecked"], n=4)


def e_imported(by, pxd, rows, did="dimp", name="포트폴리오"):
    """가진 종목 포트폴리오 하나 (store.js kind imported). rows: (t, qty | ('amount', 원), 평균 단가 | None)."""
    imp, hold = [], []
    for t, q, avg in rows:
        s = by[t]
        ccy = "USD" if s.get("ccy") == "USD" else "KRW"
        r = {"t": t, "nk": s["nk"], "ccy": ccy}
        if isinstance(q, tuple):
            r.update(amountWon=q[1], close=s["price"], date=pxd)
        else:
            r["qty"] = q
        if avg is not None:
            r["avg"] = avg
        imp.append(r)
        hold.append({"t": t, "nk": s["nk"], "cls": s["cls"], "ind": s.get("ind")})
    return {"id": did, "name": name, "createdAt": pxd, "pxDate": pxd, "kind": "imported",
            "settings": {"points": {"value": 3, "div": 2}, "strict": "normal"}, "holdings": hold, "purchases": [], "imported": imp}


def scene_v193e_home(R, files, width):
    """v19.3e 홈 (Part H · 수락 조건 5): 가진 종목 포트폴리오에는 남색 규칙 띠('{date} 종가로 점검했어요' · '내 규칙 {n}개 중 {k}개를
    지키고 있어요' · 네 칸 ✓ / ! / 확인하지 못했어요) · 포트폴리오 카드(평가 금액 · '산 가격보다'는 평균 단가를 넣은 종목만 · 미국 평균
    단가는 오늘 환율 줄 · 미국 종목이 있으면 '오늘' 없음 · 3개월 그래프 없음) · 가진 종목(비중 큰 순 · 남색 단계 색 · 막대 = 한 종목 한계
    대비) · 오늘 볼 것(업종 쏠림 카드 · 공시 줄 · 아무것도 없으면 '오늘은 할 일이 없어요'). 포트폴리오 만들기로 만든 포트폴리오는 네
    규칙으로 판정하지 않고 맨 위 판정 띠(예전 그대로). 멈춘 데이터: 멈춤 띠만, ✓ 없음 · 실패: 불러오기 실패 문구('할 일이 없어요' 아님) ·
    첫 방문: 그대로. 뱁이 없음 · 12px 바닥 · 가로 스크롤 없음."""
    S = f"v19.3e 홈 {width}"
    app = None
    f = daily_files(files)
    d = f["data.json"]
    by = {s["t"]: s for s in d["stocks"]}
    fx, pxd = d["fx"], d["pxDate"]
    deck = e_imported(by, pxd, [("005930", 10, 200000), ("000660", 3, None), ("AAPL", 2, 300.0), ("005380", ("amount", 5000000), None)])
    srv, ctx, page, base = R.open(build_site(f, app=app), width, init=e_store([deck]), path="/app.html?dev=1#home")
    md = f"{int(pxd[5:7])}월 {int(pxd[8:])}일"

    def imported():
        wait_ready(page)
        hero = page.locator('[data-ui-v2="home-rules"]')
        hero.wait_for(state="visible")
        assert hero.count() == 1 and page.locator('[data-ui-v2="home-rules-name"]').count() == 0     # 포트폴리오 하나: 이름 줄 없음
        assert fillp(C["pfr"]["checked"], date=md) in hero.inner_text()
        tiles = {t.get_attribute("data-rule"): t for t in hero.locator('[data-ui-v2="home-rule"]').all()}
        assert set(tiles) == {"stock", "ind", "fit", "warn"}, tiles.keys()
        st = {k: t.get_attribute("data-state") for k, t in tiles.items()}
        assert st["warn"] == "unknown", st                                   # 미국 종목이 있어 재무 경고는 확인하지 못했어요
        assert tiles["warn"].locator('[data-ui-v2="home-rule-unknown"]').inner_text() == C["pfr"]["unknown"]
        for k, t in tiles.items():                                           # ✓ 는 지킨 규칙에만, 확인하지 못한 규칙에는 없어요
            assert t.locator(f'[aria-label="{C["daily"]["ok"]}"]').count() == (1 if st[k] == "ok" else 0), (k, st[k])
        checked = sum(1 for v in st.values() if v != "unknown")
        kept = sum(1 for v in st.values() if v == "ok")
        assert int(hero.get_attribute("data-checked")) == checked and int(hero.get_attribute("data-kept")) == kept
        assert page.locator('[data-ui-v2="home-kept"]').inner_text().replace("\n", " ") == fillp(C["pfr"]["kept"], n=checked, k=kept)
        assert page.locator('[data-ui-v2="home-not-checked"]').inner_text() == fillp(C["daily"]["notChecked"], n=4 - checked)
        # 포트폴리오 카드: 평가 금액 · 산 가격보다(평균 단가를 넣은 삼성전자 · AAPL 두 종목만) · 미국 평균 단가는 오늘 환율 · '오늘' 없음
        units = round(5000000 / by["005380"]["price"] * 10000) / 10000
        value = 10 * by["005930"]["price"] + 3 * by["000660"]["price"] + 2 * by["AAPL"]["price"] * fx + units * by["005380"]["price"]
        money = page.locator('[data-ui-v2="home-money"]')
        assert abs(int(money.locator('[data-ui-v2="home-value"]').get_attribute("data-v")) - value) <= 1
        assert money.locator('[data-ui-v2="home-money-date"]').inner_text() == fillp(C["why"]["close"], md=md)
        gain = money.locator('[data-ui-v2="home-gain"]')
        assert gain.get_attribute("data-n") == "2", gain.inner_text()
        cost = 10 * 200000 + 2 * 300.0 * fx
        now = 10 * by["005930"]["price"] + 2 * by["AAPL"]["price"] * fx
        assert abs(float(gain.get_attribute("data-ret")) - (now / cost - 1) * 100) < 0.01, gain.get_attribute("data-ret")
        g_amt = ("+" + won_text(now - cost)) if now > cost else ("\u2212" + won_text(cost - now)) if now < cost else won_text(0)
        want = fillp(C["home"]["gain"], amount=g_amt, pct=signed_pct((now / cost - 1) * 100)) + " · " + fillp(C["home"]["gainBasis"], n=2)
        assert gain.inner_text().replace("\n", " ") == want, (gain.inner_text(), want)
        assert money.locator('[data-ui-v2="usd-today"]').inner_text() == C["pfr"]["usdToday"]
        assert money.locator('[data-ui-v2="home-day"]').count() == 0          # 미국 종목이 있으면 오늘 변화 없음 (환율이 하루 전 것이 없어요)
        assert page.locator('[data-ui-v2="home-block"] polyline, [data-ui-v2="home-money"] svg:not([data-icon])').count() == 0, "3개월 그래프"
        # 가진 종목: 비중 큰 순 · 남색 단계 색 · 오늘 변화(빼기는 U+2212)
        held = page.locator('[data-ui-v2="home-held"]')
        assert held.locator("h3").inner_text() == fillp(C["home"]["held"], n=4) and C["home"]["cols"] in held.inner_text()
        rows = held.locator("[data-home-holding]")
        ws = [float(rows.nth(i).get_attribute("data-weight")) for i in range(rows.count())]
        assert rows.count() == 4 and ws == sorted(ws, reverse=True) and abs(sum(ws) - 100) < 0.5, ws
        bars = held.locator('[data-ui-v2="home-bar"]').evaluate_all("els => els.map((e) => getComputedStyle(e).backgroundColor)")
        assert bars == [rgb(c) for c in HOLDING_SHADES[:4]], bars
        lim = 30
        assert held.get_attribute("data-kind") == "imported" and held.get_attribute("data-full") == str(lim)   # 가진 종목: 한 종목 한계에 대한 막대
        widths = held.locator('[data-ui-v2="home-bar"]').evaluate_all("els => els.map((e) => parseFloat(e.style.width))")
        assert all(abs(w - min(100, x / lim * 100)) < 0.2 for w, x in zip(widths, ws)), (widths, ws)
        for t in ("005930", "000660"):
            ch = held.locator(f'[data-home-holding="{t}"] [data-ui-v2="home-change"]').inner_text()
            assert ch == signed_pct(by[t]["d1"]) and "-" not in ch, ch
        assert page.locator('[data-ui-v2="today-hero"]').count() == 0          # 가진 종목만: 종목별 판정 띠 없음
        assert page.locator(MASCOT_IN_MAIN).count() == 0, "숫자가 있는 홈에 뱁이"
        floor_ok(page, "새 홈 (가진 종목)")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "가진 종목 포트폴리오: 규칙 띠(✓ 는 지킨 규칙만) · 산 가격보다는 평균 단가 넣은 2종목만 · 오늘 환율 줄 · 오늘 없음 · 그래프 없음 · 비중 막대", imported)

    def look():
        ind = page.locator('[data-ui-v2="home-rule"][data-rule="ind"]').get_attribute("data-state")
        conc = page.locator('[data-ui-v2="home-conc"]')
        if ind == "broken":                                                  # 업종 쏠림 카드: '{업종} {x}%' / '{회사들} · 내 규칙은 35%까지'
            assert conc.count() == 1
            title, sub = conc.inner_text().split("\n")[:2]
            assert re.fullmatch(r".+ [\d.]+%", title) and sub.endswith(fillp(C["home"]["concentration"], names="", limit=35)), conc.inner_text()
            assert C["home"]["look"] in page.locator('[data-ui-v2="home-look"]').inner_text()
            assert page.locator('[data-ui-v2="home-calm"]').count() == 0     # 깨진 규칙이 있으면 '오늘은 할 일이 없어요' 없음
            conc.click()
            at(page, "portfolio")
        else:
            assert conc.count() == 0
    R.check(page, S, "오늘 볼 것: 한 업종 규칙이 깨지면 업종 쏠림 카드 → 포트폴리오", look)
    ctx.close()
    srv.shutdown()

    dk = {x["id"]: x for x in DAILY_DECKS["decks"]}
    srv, ctx, page, base = R.open(build_site(f, app=app), width, init=e_store([dk["dmiss"], dk["dcalm"]]), path="/app.html?dev=1#home")

    def built():
        wait_ready(page)
        hero = page.locator('[data-ui-v2="today-hero"]')                    # 만든 포트폴리오: 예전 판정 띠 그대로 (네 규칙으로 판정하지 않아요)
        hero.wait_for(state="visible")
        assert page.locator('[data-ui-v2="home-block"]').count() == 2 and page.locator('[data-ui-v2="home-rules"]').count() == 0
        items = hero.locator('[data-ui-v2="todo-item"]').evaluate_all("els => els.map(e => e.dataset.t + ':' + e.dataset.status)")
        assert "000270:check" in items, items                               # 확인 필요(기아, 부채비율 자료 없음)는 판정 띠에
        assert "SK하이닉스" in page.locator('[data-ui-v2="big-moves"]').inner_text()
        assert page.locator('[data-ui-v2="home-look"]').count() == 0 and C["pfr"]["kept"].split("{")[0] not in page.locator("body").inner_text()
        assert page.locator('[data-ui-v2="home-held"][data-deck-id="dmiss"] [data-home-holding="000270"]').get_attribute("data-status") == "check"
        calm = page.locator('[data-ui-v2="home-money"][data-deck-id="dcalm"]')
        day = calm.locator('[data-ui-v2="home-day"]')                      # 한국 종목만: 오늘 변화 (금액 · %)
        assert re.fullmatch(r"오늘 [+−]?[\d,]+(만원|원) \([+−]?[\d,]+\.\d%\)", day.inner_text()), day.inner_text()
        assert calm.locator('[data-ui-v2="home-gain"]').get_attribute("data-n") == "2"   # 샀어요 기록 = 평균 단가
        # 만든 포트폴리오의 막대는 한 종목 30% 한계가 아니라 전체(100%)에 대한 비중 · 비중은 비중 규칙 줄처럼 소수 한 자리
        for card in page.locator('[data-ui-v2="home-held"]').all():
            assert card.get_attribute("data-kind") == "built" and card.get_attribute("data-full") == "100", card.get_attribute("data-deck-id")
            for r in card.locator("[data-home-holding]").all():
                x = float(r.get_attribute("data-weight"))
                w = float(r.locator('[data-ui-v2="home-bar"]').evaluate("(e) => parseFloat(e.style.width)"))
                assert abs(w - x) < 0.2 and r.locator('[data-ui-v2="home-weight"]').inner_text() == f"{x:,.1f}%", (w, x, r.inner_text())
        assert page.locator(MASCOT_IN_MAIN).count() == 0
        floor_ok(page, "새 홈 (만든 포트폴리오 둘)")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "만든 포트폴리오 둘: 네 규칙 띠 없음 · 판정 띠(확인 필요 · 큰 움직임) 그대로 · 오늘 변화 · 샀어요 기록은 평균 단가", built)
    ctx.close()
    srv.shutdown()

    for how, ff, drop in (("멈춤", daily_files(files, days_ago=6), ()), ("실패", daily_files(files), ("data.json",))):
        srv, ctx, page, base = R.open(build_site(ff, drop=drop, app=app), width, init=e_store([deck]), path="/app.html?dev=1#home")

        def no_check(how=how):
            wait_ready(page)
            if how == "멈춤":
                page.locator('[data-ui-v2="today-stale"]').wait_for(state="visible")
                assert page.locator('[data-ui-v2="today-stale"]').inner_text() == fillp(C["today"]["stale"], n=6)
            else:
                see(page, LOAD_FAIL)
            for sel in ('[data-ui-v2="home-rules"]', '[data-ui-v2="home-money"]', '[data-ui-v2="home-held"]', '[data-ui-v2="home-look"]',
                        '[data-ui-v2="home-calm"]', f'[aria-label="{C["daily"]["ok"]}"]'):
                assert page.locator(sel).count() == 0, sel                   # 멈추거나 실패한 데이터: 점검하지 않아요, ✓ 없음
            assert C["today"]["calmEyebrow"] not in page.locator("body").inner_text()     # 실패를 '할 일이 없어요'로 말하지 않아요
            R.collect(page)
        R.check(page, S, f"{how}: 규칙 띠 · 숫자 · ✓ · '오늘은 할 일이 없어요' 없음 (멈춤 문장 또는 불러오기 실패)", no_check)
        ctx.close()
        srv.shutdown()

    nopx = clone(f)
    for x in nopx["data.json"]["stocks"]:
        if x["t"] == "000660":
            x["price"] = None                                                 # 데이터에는 있지만 오늘 가격이 없어요
    srv, ctx, page, base = R.open(build_site(nopx, app=app), width, init=e_store([deck]), path="/app.html?dev=1#home")

    def nothing_checked():
        """아무 규칙도 확인하지 못한 가진 종목 포트폴리오 (네 칸 모두 확인하지 못했어요): '{date} 종가로 점검했어요' · '내 규칙 {n}개 중' ·
        ✓ · '오늘은 할 일이 없어요' 모두 없어요. '아직 자동으로 확인하지 못하는 규칙이 4개 있어요'만."""
        hero = page.locator('[data-ui-v2="home-rules"]')
        st = hero.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => e.dataset.rule + ':' + e.dataset.state)")
        assert st == ["stock:unknown", "ind:unknown", "fit:unknown", "warn:unknown"], st
        assert hero.get_attribute("data-checked") == "0" and hero.get_attribute("data-kept") == "0"
        body = page.locator("body").inner_text()
        assert page.locator('[data-ui-v2="home-checked"], [data-ui-v2="home-kept"], [data-ui-v2="home-calm"]').count() == 0
        assert fillp(C["pfr"]["checked"], date=md) not in body and C["pfr"]["checked"].split("{date}")[1] not in body, "점검하지 못했는데 '점검했어요'"
        assert C["today"]["calmEyebrow"] not in body, "아무 규칙도 확인하지 못했는데 '오늘은 할 일이 없어요'"
        assert page.locator(f'[aria-label="{C["daily"]["ok"]}"]').count() == 0
        assert page.locator('[data-ui-v2="home-not-checked"]').inner_text() == fillp(C["daily"]["notChecked"], n=4)

    def no_price():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="home-money"]').count() == 0          # 값을 모르면 빈 카드를 그리지 않아요
        st = page.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => e.dataset.rule + ':' + e.dataset.state)")
        assert "stock:unknown" in st and "ind:unknown" in st, st             # 비중을 모르니 확인하지 못했어요 (✓ 아님)
        nothing_checked()                                                     # 미국 종목도 있어 네 칸 모두: '점검했어요' · '할 일이 없어요' 없음
        R.collect(page)
    R.check(page, S, "오늘 가격이 없는 종목 + 미국 종목: 포트폴리오 카드는 빠지고 네 규칙 모두 확인하지 못했어요 · '점검했어요' · '오늘은 할 일이 없어요' 없음", no_price)

    def no_price_portfolio():
        tab(page, TABS["portfolio"]) if width < 1024 else side_tab(page, "portfolio")
        at(page, "portfolio")
        head = page.locator(f'[data-deck-id="{deck["id"]}"] [data-ui-v2="pf-head"]')
        head.wait_for(state="visible")
        no_claim_pf(page, head, md)
        R.collect(page)
    R.check(page, S, "같은 경우 포트폴리오 탭: 네 규칙 모두 확인하지 못했어요 · '{date} 종가로 점검했어요' · '내 규칙 {n}개 중' · ✓ 없음", no_price_portfolio)
    ctx.close()
    srv.shutdown()

    gone = clone(f)
    gone["data.json"]["stocks"] = [x for x in gone["data.json"]["stocks"] if x["t"] != "000660"]     # 오늘 데이터에서 빠진 종목
    srv, ctx, page, base = R.open(build_site(gone, app=app), width, init=e_store([deck]), path="/app.html?dev=1#home")

    def left_data():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        nothing_checked()
        money = page.locator('[data-ui-v2="home-money"]')                     # 값은 나머지 종목으로, 빠진 종목은 이름으로 말해요
        miss = money.locator('[data-ui-v2="missing-line"]')
        assert money.count() == 1 and miss.count() == 1 and by["000660"]["nk"] in miss.inner_text(), money.inner_text()
        R.collect(page)
    R.check(page, S, "오늘 데이터에서 빠진 종목 + 미국 종목: 네 규칙 모두 확인하지 못했어요 · '점검했어요' · '오늘은 할 일이 없어요' 없음", left_data)
    ctx.close()
    srv.shutdown()

    # 아무것도 볼 것이 없는 가진 종목 포트폴리오 (다섯 업종에 고르게, 기준은 대형주: 한 종목 · 한 업종 · 내 기준 모두 확인했고 깨진 규칙
    # 없음) → '오늘은 할 일이 없어요' · 공시 줄: 회사 페이지가 disc.json 을 불러온 뒤에만, 최근 7일 보고만.
    # 고른 기준이 없으면(내 기준을 확인하지 못했어요) '오늘은 할 일이 없어요'가 아니에요 (아래 no_cards).
    calm_ts = ("373220", "207940", "009150", "005380", "105560")
    tot = 10000000
    calm = e_imported(by, pxd, [(t, max(1, round(tot / 5 / by[t]["price"])), None) for t in calm_ts], did="dcalm5")
    calm["settings"]["points"] = {}
    srv, ctx, page, base = R.open(build_site(f, app=app), width, init=e_store([calm]), path="/app.html?dev=1#home")

    def no_cards():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        st = dict(page.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => [e.dataset.rule, e.dataset.state])"))
        assert st["fit"] == "unknown" and "broken" not in st.values(), st
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0 and C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
        R.collect(page)
    R.check(page, S, "고른 기준이 없어 내 기준을 확인하지 못했어요: '오늘은 할 일이 없어요' 없음", no_cards)
    ctx.close()
    srv.shutdown()
    calm["settings"]["points"] = {"large": 3}
    srv, ctx, page, base = R.open(build_site(f, app=app), width, init=e_store([calm]), path="/app.html?dev=1#home")

    def calm_line():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        st = page.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => e.dataset.state)")
        assert "broken" not in st, st
        rs = dict(page.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => [e.dataset.rule, e.dataset.state])"))
        assert [rs[k] for k in ("stock", "ind", "fit")] == ["ok", "ok", "ok"], rs  # 한 종목 · 한 업종 · 내 기준 모두 확인했어요
        assert page.locator('[data-ui-v2="home-checked"]').inner_text() == fillp(C["pfr"]["checked"], date=md)
        # 한국 종목을 가졌으니 홈이 공시 목록을 스스로 받았고(회사 페이지를 열지 않았어요), 최근 7일 보고는 없어요
        assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "ok" and disc_fetched(page)
        c = page.locator('[data-ui-v2="home-calm"]')
        assert c.inner_text() == C["today"]["calmEyebrow"]                    # 오늘 볼 것이 비면 '오늘은 할 일이 없어요'
        assert page.locator('[data-ui-v2="home-filing"]').count() == 0
        R.collect(page)
    R.check(page, S, "볼 것이 없으면 '오늘은 할 일이 없어요' (홈이 받은 공시 목록에 최근 7일 보고 없음)", calm_line)
    ctx.close()
    srv.shutdown()

    # 공시 줄 (Jack, 2026-11-08): 회사 페이지를 열지 않아도 홈이 받아요 · 그 주 보고가 모두 같은 쪽일 때만 방향, 섞이면 '지분 변동 보고'
    ff = clone(f)
    now = now_dt()
    today, yday = now.strftime("%Y%m%d"), (now - dt.timedelta(days=1)).strftime("%Y%m%d")
    ff["disc.json"]["newest"] = now.strftime("%Y-%m-%d")

    def ins(rc, d, t, q):
        return {"rc": rc, "d": d, "t": t, "nk": by[t]["nk"], "s": "auto", "cap": 1.0, "nm": "가나다", "pos": "상무", "q": q, "r": 0.0, "amt": 1.0}
    ff["disc.json"]["insider"] = [ins("20991231000001", today, "005380", 300), ins("20991231000002", yday, "005380", -100),     # 섞임
                                  ins("20991231000003", today, "105560", -50),                                                 # 모두 줄임
                                  ins("20991231000004", yday, "373220", 20), ins("20991231000005", yday, "373220", 5)] + ff["disc.json"]["insider"]   # 모두 늘림
    srv, ctx, page, base = R.open(build_site(ff, app=app), width, init=e_store([calm]), path="/app.html?dev=1#home")

    def filings():
        wait_ready(page)
        rows = page.locator('[data-ui-v2="home-filing"]')
        rows.first.wait_for(state="visible")
        assert route(page) == "home" and disc_fetched(page)                    # 회사 페이지를 열지 않았는데 홈에 공시 줄
        mdx = lambda d: f"{int(d[4:6])}월 {int(d[6:])}일"
        got = {r.get_attribute("data-t"): r.inner_text().strip() for r in rows.all()}
        want = {"005380": fillp(C["home"]["filings"], name=by["005380"]["nk"], n=2, title=C["home"]["filingsBoth"], date=mdx(today)),
                "105560": fillp(C["home"]["filings"], name=by["105560"]["nk"], n=1, title=CO["disc"]["sells"], date=mdx(today)),
                "373220": fillp(C["home"]["filings"], name=by["373220"]["nk"], n=2, title=CO["disc"]["buys"], date=mdx(yday))}
        assert got == want, (got, want)
        assert C["home"]["filingsBoth"] == "지분 변동 보고"
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0          # 볼 것이 있으면 '할 일이 없어요'는 빠져요
        floor_ok(page, "새 홈 (공시 줄)")
        no_hscroll(page, width)
        R.collect(page)
        page.locator('[data-ui-v2="home-filing"][data-t="005380"]').click()
        at(page, "stocks/005380")
    R.check(page, S, "공시 줄: 회사 페이지를 열지 않아도 홈이 받아요 · 모두 늘림 → 지분을 늘린 보고 · 모두 줄임 → 지분을 줄인 보고 · 섞임 → 지분 변동 보고 → 그 회사", filings)
    ctx.close()
    srv.shutdown()

    # 공시 목록을 받지 못했어요: 공시 탭과 같은 실패 문구 · '오늘은 할 일이 없어요' 없음 (가진 종목만 · 만든 포트폴리오만 둘 다)
    for who, decks in (("가진 종목", [calm]), ("만든 포트폴리오", [_one_deck("dsam", "반반 포트폴리오", [(*SAMSUNG, 1.0, [], 1, round(by["005930"]["price"]))])["decks"][0]])):
        srv, ctx, page, base = R.open(build_site(f, drop=("disc.json",), app=app), width, init=e_store(decks), path="/app.html?dev=1#home")

        def disc_fail(who=who):
            wait_ready(page)
            assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "fail"
            box = page.locator('[data-ui-v2="home-disc-fail"]')
            assert box.locator('[data-ui-v2="load-fail"]').inner_text() == C["app"]["loadFail"]     # 공시 탭의 실패 문구 그대로 (그림 없음)
            assert box.locator('[data-ui="icon-chip"][data-icon="file-text"]').count() == 1           # 공시 줄의 칩 옆에 (무엇이 실패했는지)
            assert box.locator("img").count() == 0 and page.locator(MASCOT_IN_MAIN).count() == 0
            assert page.locator('[data-ui-v2="home-calm"]').count() == 0
            assert C["today"]["calmEyebrow"] not in page.locator("body").inner_text(), "공시를 확인하지 못했는데 '오늘은 할 일이 없어요'"
            if who == "만든 포트폴리오":
                assert page.locator('[data-ui-v2="today-hero"]').get_attribute("data-state") == "calm"   # 띠는 그대로, 그 한 줄만 빠져요
            R.collect(page)
        R.check(page, S, f"공시 목록 실패 ({who}): 공시 탭과 같은 실패 문구 · '오늘은 할 일이 없어요' 없음", disc_fail)
        ctx.close()
        srv.shutdown()

    # disc.json 404 (Jack, 2026-11-08): 받지 못한 것도 끝이에요. disc_settled 가 몇 초 안에 끝나고 실패 문구가 보여요 (기다리다 멈추지 않아요)
    srv, ctx, page, base = R.open(build_site(f, drop=("disc.json",), app=app), width, init=e_store([calm]), path="/app.html?dev=1#home")

    def disc_404_settles():
        page.locator('[data-ui-v2="home2"]').wait_for(state="attached")
        t0 = time.monotonic()
        disc_settled(page, timeout=5000)
        took = time.monotonic() - t0
        assert took < 5, took
        assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "fail"
        msg = page.locator('[data-ui-v2="home-disc-fail"] [data-ui-v2="load-fail"]')
        assert msg.is_visible() and msg.inner_text() == C["app"]["loadFail"]
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0
        R.collect(page)
    R.check(page, S, "disc.json 404: 공시 목록 기다림이 몇 초 안에 끝나고(5초 미만) 실패 문구가 보여요", disc_404_settles)
    ctx.close()
    srv.shutdown()

    # 멈춘 공시 목록 (리뷰 2026-11-08): 파일이 오래됐거나(발행 6일 전) 그날 DART 목록을 받지 못했으면(listOk false) 공시 줄도 '할 일이
    # 없어요'도 없이 공시 탭의 날짜 줄 그대로 ('{md} 기준 · {n}일째 갱신이 멈췄어요'), 공시 줄의 file-text 칩 옆에
    kst_now = now_dt()
    newest5 = (kst_now - dt.timedelta(days=5)).date()
    since5 = int((kst_now - dt.datetime.combine(newest5, dt.time(0), KST)).total_seconds() // 86400)
    for how, upd, newest, days in (("발행 6일 전", {"publishedAt": now_kst(days_ago=6)}, f["disc.json"]["newest"], 6),
                                   ("그날 목록 실패", {"listOk": False, "newest": newest5.isoformat()}, newest5.isoformat(), since5)):
        so = clone(f)
        so["disc.json"].update(upd)
        srv, ctx, page, base = R.open(build_site(so, app=app), width, init=e_store([calm]), path="/app.html?dev=1#home")

        def disc_old(newest=newest, days=days):
            wait_ready(page)
            assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "stale"
            box = page.locator('[data-ui-v2="home-disc-old"]')
            assert box.get_attribute("data-date") == newest and box.locator('[data-ui="icon-chip"][data-icon="file-text"]').count() == 1
            line = box.locator('[data-ui-v2="date-line"]')
            want = fillp(C["app"]["asOf"], md=f"{int(newest[5:7])}월 {int(newest[8:])}일") + " · " + (C["app"]["staleLate"] if days <= 1 else fillp(C["app"]["stale"], n=days))
            assert line.get_attribute("data-stale") == "1" and line.inner_text() == want, (line.inner_text(), want)
            assert page.locator('[data-ui-v2="home-filing"], [data-ui-v2="home-calm"], [data-ui-v2="home-disc-fail"]').count() == 0
            assert C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
            floor_ok(page, "새 홈 (멈춘 공시 목록)")
            R.collect(page)
        R.check(page, S, f"멈춘 공시 목록 ({how}): 공시 탭의 날짜 줄('…일째 갱신이 멈췄어요') · 공시 줄 · '할 일이 없어요' 없음", disc_old)
        ctx.close()
        srv.shutdown()

    # 공시 목록을 받는 동안은 '오늘은 할 일이 없어요'가 없어요 (리뷰 2026-11-08): disc.json 응답을 붙잡아 두고 봐요
    srv, ctx, page, base = R.open(build_site(f, app=app), width, init=e_store([calm]), path="/app.html?dev=1#home")
    held_req = []

    def while_loading():
        wait_ready(page)                                                      # 처음 열 때 받은 목록은 버리고, 새로 고친 뒤를 봐요
        page.route("**/disc.json", lambda r: held_req.append(r))
        page.reload(wait_until="domcontentloaded")
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"home2\"]').dataset.disc === 'wait'")
        for _ in range(200):                                                 # 첫 화면 뒤에 보내는 요청이 붙잡힐 때까지
            if held_req:
                break
            page.wait_for_timeout(50)
        assert held_req, "disc.json 요청이 없어요"
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0 and C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
        rs = dict(page.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => [e.dataset.rule, e.dataset.state])"))
        assert [rs[k] for k in ("stock", "ind", "fit")] == ["ok", "ok", "ok"], rs  # 다른 건 다 조용해요: 공시만 기다려요
        for r in held_req:                                                    # 붙잡아 둔 요청을 이제 보내요 (사이트 안 주소)
            r.fallback()
        disc_settled(page)
        assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "ok"
        assert page.locator('[data-ui-v2="home-calm"]').inner_text() == C["today"]["calmEyebrow"]   # 받고 나서야
        R.collect(page)
    R.check(page, S, "공시 목록을 받는 동안: '오늘은 할 일이 없어요' 없음 → 받은 뒤에 나와요", while_loading)
    ctx.close()
    srv.shutdown()

    # 미국 종목만: 공시 목록(disc.json)을 받지 않아요
    us_only = e_imported(by, pxd, [("AAPL", 2, None)], did="dus")
    srv, ctx, page, base = R.open(build_site(f, app=app), width, init=e_store([us_only]), path="/app.html?dev=1#home")

    def us_no_disc():
        wait_ready(page)
        page.locator('[data-ui-v2="home-rules"]').wait_for(state="visible")
        page.wait_for_timeout(400)
        assert page.locator('[data-ui-v2="home2"]').get_attribute("data-disc") == "skip"
        assert not disc_fetched(page), "미국 종목만 가졌는데 disc.json 을 받았어요"
        assert page.locator('[data-ui-v2="home-disc-fail"], [data-ui-v2="home-disc-old"], [data-ui-v2="home-filing"]').count() == 0
        R.collect(page)
    R.check(page, S, "미국 종목만 가진 홈: disc.json 요청 없음", us_no_disc)
    ctx.close()
    srv.shutdown()

    # 만든 포트폴리오 반반 (삼성전자 · 현대차 1주씩, 오늘 같은 가격, 종목별 규칙은 비중 띠뿐: 할 일 없음) · 그리고 가진 종목 포트폴리오와 함께
    hf = clone(f)
    hby = {x["t"]: x for x in hf["data.json"]["stocks"]}
    for t in ("005930", "005380"):
        hby[t]["price"] = 200000.0
    half = _one_deck("dhalf", "반반 포트폴리오", [("005930", "삼성전자", 0.5, [], 1, 200000), ("005380", "현대차", 0.5, [], 1, 200000)])["decks"][0]
    semi_pf = e_imported(hby, pxd, [("005930", 10, None), ("000660", 3, None)], did="dsemi", name="반도체 포트폴리오")     # 한 업종 100%: 깨짐
    quiet_pf = e_imported(hby, pxd, [(t, max(1, round(tot / 5 / hby[t]["price"])), None) for t in calm_ts], did="dquiet", name="조용한 가진 종목")
    quiet_pf["settings"]["points"] = {"large": 3}
    band_text = lambda: page.locator('[data-ui-v2="today-hero"]').inner_text()

    srv, ctx, page, base = R.open(build_site(hf, app=app), width, init=e_store([half]), path="/app.html?dev=1#home")

    def half_bars():
        wait_ready(page)
        page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")
        held = page.locator('[data-ui-v2="home-held"][data-deck-id="dhalf"]')
        assert held.get_attribute("data-kind") == "built" and held.get_attribute("data-full") == "100"
        ws = [float(x) for x in held.locator("[data-home-holding]").evaluate_all("els => els.map((e) => e.dataset.weight)")]
        widths = held.locator('[data-ui-v2="home-bar"]').evaluate_all("els => els.map((e) => parseFloat(e.style.width))")
        assert ws == [50.0, 50.0] and all(abs(w - 50) < 0.2 for w in widths), (ws, widths)     # 반반은 절반 막대 둘 (가득 찬 막대 둘이 아니에요)
        assert held.locator('[data-ui-v2="home-weight"]').all_inner_texts() == ["50.0%", "50.0%"]
        assert band_text().startswith(C["today"]["calmEyebrow"]), band_text()   # 만든 포트폴리오만, 볼 것 없음: 띠의 '오늘은 할 일이 없어요' 그대로
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0          # 띠가 말하니 오늘 볼 것에는 없어요
        R.collect(page)
    R.check(page, S, "만든 포트폴리오 반반: 막대는 전체에 대한 비중(절반 둘, 30% 한계로 가득 찬 막대 둘이 아님) · 비중 50.0% · 띠의 '할 일이 없어요'", half_bars)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(hf, app=app), width, init=e_store([half, semi_pf]), path="/app.html?dev=1#home")

    def mixed_broken():
        wait_ready(page)
        hero = page.locator('[data-ui-v2="today-hero"]')
        hero.wait_for(state="visible")
        assert hero.get_attribute("data-state") == "calm" and C["today"]["calmTitle"] in band_text()   # 만든 포트폴리오의 띠는 그대로
        assert C["today"]["calmEyebrow"] not in band_text(), band_text()      # 깨진 규칙 · 볼 것이 있으면 띠도 '할 일이 없어요'라고 하지 않아요
        rules = page.locator('[data-ui-v2="home-rules"][data-deck-id="dsemi"]')
        assert rules.count() == 1 and rules.locator('[data-ui-v2="home-rule"][data-state="broken"]').count() >= 1
        assert page.locator('[data-ui-v2="home-conc"][data-deck-id="dsemi"]').count() == 1 and page.locator('[data-ui-v2="home-calm"]').count() == 0
        conc_lines = page.locator('[data-ui-v2="home-conc"][data-deck-id="dsemi"]').inner_text().split("\n")   # (포트폴리오 이름) · 제목 · 설명
        conc_title = next((l for l in conc_lines if re.fullmatch(r".+ [\d.]+%", l)), None)
        assert conc_title and conc_title.startswith(C["rpt"]["chipGroup"] + " "), conc_lines    # v19.3d2 (Jack Q8): 삼성전자 + SK하이닉스 = 반도체·전자부품
        assert C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
        assert page.locator('[data-ui-v2="home-rules-name"]').inner_text() == "반도체 포트폴리오"     # 포트폴리오가 둘: 띠마다 이름
        R.collect(page)
    R.check(page, S, "만든 + 가진 종목(한 업종 깨짐): 위 띠는 그대로지만 '오늘은 할 일이 없어요'는 없음 · 업종 쏠림 카드", mixed_broken)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(hf, app=app), width, init=e_store([half, quiet_pf]), path="/app.html?dev=1#home")

    def mixed_quiet():
        wait_ready(page)
        page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")
        rs = dict(page.locator('[data-ui-v2="home-rule"]').evaluate_all("els => els.map((e) => [e.dataset.rule, e.dataset.state])"))
        assert [rs[k] for k in ("stock", "ind", "fit")] == ["ok", "ok", "ok"], rs
        assert band_text().startswith(C["today"]["calmEyebrow"]), band_text()   # 모두 조용하면 띠의 '오늘은 할 일이 없어요' 그대로
        assert page.locator('[data-ui-v2="home-calm"]').count() == 0 and page.locator('[data-ui-v2="home-look"]').count() == 0
        R.collect(page)
    R.check(page, S, "만든 + 조용한 가진 종목: 띠의 '오늘은 할 일이 없어요' 그대로 (한 번만)", mixed_quiet)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(f, app=app), width, path="/app.html?dev=1#home")

    def first():
        page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")       # 첫 방문은 그대로 (뱁이, 숫자 없음)
        assert page.locator('[data-ui-v2="home-rules"], [data-ui-v2="home2"]').count() == 0
        R.collect(page)
    R.check(page, S, "저장한 포트폴리오가 없으면 첫 방문 화면 그대로", first)
    ctx.close()
    srv.shutdown()


_HOME2_OFF = {}


def home2_off_app():
    """app.html 을 새 홈 스위치(today.jsx HOME2)만 끄고 임시 폴더에 빌드해요 (커밋하지 않아요, 폴더는 바로 지워요). 비상 스위치라 꺼진
    상태(v19.3d 의 홈)도 계속 시험해요 (한국 배당 추세 스위치처럼)."""
    if "html" not in _HOME2_OFF:
        tmp = tmpdirs.make("baepsae-home2-off-")
        try:
            shutil.copytree(os.path.join(ROOT, "src"), os.path.join(tmp, "src"))
            os.makedirs(os.path.join(tmp, "tools"))
            for f in ("template.html", "build-app.sh", "package.json", "package-lock.json", os.path.join("tools", "build_tag.py")):
                shutil.copy(os.path.join(ROOT, f), os.path.join(tmp, f))
            os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
            p = os.path.join(tmp, "src", "v2", "today.jsx")
            with open(p, encoding="utf-8") as fh:
                src = fh.read()
            old = re.findall(r"^export const HOME2 = (?:true|false);$", src, flags=re.M)
            assert old == ["export const HOME2 = true;"], old                 # 커밋한 빌드는 켜져 있어요 (Jack, 2026-11-08)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(src.replace(old[0], "export const HOME2 = false;"))
            out = os.path.join(tmp, "out")
            r = subprocess.run(["bash", "build-app.sh", out], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
            assert r.returncode == 0, r.stdout + r.stderr
            with open(os.path.join(out, "app.html"), encoding="utf-8") as a, open(os.path.join(ROOT, "app.html"), encoding="utf-8") as b:
                html = a.read()
                assert html != b.read(), "스위치를 꺼서 빌드했는데 app.html 이 같아요"
            _HOME2_OFF["html"] = html
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _HOME2_OFF["html"]


def scene_home2_off(R, files, width=390):
    """새 홈 스위치(HOME2)를 끈 빌드: 홈은 v19.3d 그대로 — 만든 포트폴리오의 판정 띠와 포트폴리오 줄(deck-strip), 가진 종목 포트폴리오는
    자기 줄(네 규칙 · 비중), 새 홈의 남색 규칙 띠 · 포트폴리오 카드 · 오늘 볼 것은 없음. 불러오기 실패는 실패 문구('할 일이 없어요' 아님)."""
    S = f"새 홈 스위치 끈 빌드 {width}"
    app = home2_off_app()
    f = daily_files(files)
    by = {s["t"]: s for s in f["data.json"]["stocks"]}
    dk = {x["id"]: x for x in DAILY_DECKS["decks"]}
    imp = e_imported(by, f["data.json"]["pxDate"], [("005930", 10, 200000), ("000660", 3, None)], did="dimp")
    for how, drop in (("정상", ()), ("실패", ("data.json",))):
        srv, ctx, page, base = R.open(build_site(f, drop=drop, app=app), width, init=e_store([dk["dcalm"], imp]), path="/app.html?dev=1#home")

        def run(how=how):
            wait_ready(page)
            new = ('[data-ui-v2="home2"], [data-ui-v2="home-block"], [data-ui-v2="home-rules"], [data-ui-v2="home-money"], [data-ui-v2="home-held"], '
                   '[data-ui-v2="home-look"], [data-ui-v2="home-calm"]')
            if how == "정상":
                page.locator('[data-ui-v2="today-hero"]').wait_for(state="visible")
                assert page.locator('[data-ui-v2="deck-strip"]').count() == 2      # 만든 포트폴리오 줄 + 가진 종목 포트폴리오 줄
                strip = page.locator('[data-ui-v2="deck-strip"][data-kind="imported"][data-deck-id="dimp"]')
                assert strip.count() == 1 and strip.locator('[data-ui-v2="pf-rule"]').count() == 4
                assert page.locator('[data-ui-v2="deck-strip"][data-deck-id="dcalm"] [data-today-holding]').count() == 2
                assert page.locator(new).count() == 0, "스위치를 껐는데 새 홈이 보여요"
                assert page.locator(MASCOT_IN_MAIN).count() == 0
                no_hscroll(page, width)
            else:
                see(page, LOAD_FAIL)
                assert page.locator(new + ', [data-ui-v2="deck-strip"], [data-ui-v2="today-hero"]').count() == 0
                assert C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
            R.collect(page)
        R.check(page, S, f"{how}: " + ("v19.3d 의 홈 그대로 (판정 띠 · 포트폴리오 줄 둘, 새 홈 없음)" if how == "정상" else "불러오기 실패 문구, 할 일이 없어요 아님"), run)
        ctx.close()
        srv.shutdown()

    # 오늘 가격이 없는 종목 + 미국 종목: 가진 종목 포트폴리오 줄의 네 규칙 모두 확인하지 못했어요 → '점검했어요' 없음 (pfview RulesHead)
    nopx = clone(f)
    for x in nopx["data.json"]["stocks"]:
        if x["t"] == "000660":
            x["price"] = None
    unk = e_imported(by, f["data.json"]["pxDate"], [("005930", 10, 200000), ("000660", 3, None), ("AAPL", 2, 300.0)], did="dunk")
    srv, ctx, page, base = R.open(build_site(nopx, app=app), width, init=e_store([unk]), path="/app.html?dev=1#home")
    pxd = f["data.json"]["pxDate"]

    def nothing_checked_old_home():
        wait_ready(page)
        head = page.locator('[data-ui-v2="deck-strip"][data-deck-id="dunk"] [data-ui-v2="pf-head"]')
        head.wait_for(state="visible")
        no_claim_pf(page, head, f"{int(pxd[5:7])}월 {int(pxd[8:])}일")
        assert C["today"]["calmEyebrow"] not in page.locator("body").inner_text()
        R.collect(page)
    R.check(page, S, "오늘 가격이 없는 종목 + 미국 종목: 네 규칙 모두 확인하지 못했어요 · '{date} 종가로 점검했어요' · ✓ · '할 일이 없어요' 없음", nothing_checked_old_home)
    ctx.close()
    srv.shutdown()


def div_shape(rule):
    """company.divArt: 늘렸어요(streak · raised)만 올라가는 더미, 작년과 비슷하게(steady)는 같은 높이 셋, 해마다 비교하지 않은 지급
    (pays · noPrev)은 더미 하나(3년 내내 같았다고 그리지 않게), 나머지는 그림 없음."""
    return "rising" if rule in ("streak", "raised") else "even" if rule == "steady" else "one" if rule in ("pays", "noPrev") else None


def scene_v193e_company(R, files, width):
    """v19.3e 회사 페이지 (Part I · 수락 조건 5): 요약 칸의 작은 그림(실적 막대 · 가치 눈금 · 배당 동전 · 출렁임 물결)은 칸의 규칙대로 ·
    재무 경고 칩은 돌았고 걸리지 않은 확인만(해당 없음 · 못 돌린 이자보상배율은 칩 없음) · 가진 포트폴리오가 하나면 '내 포트폴리오의
    {x}%' · 가치: '업종 {n}개 회사와 비교' 카드와 '업종 안 PBR 위치', 지금 가격이 가정하는 것은 순이익끼리(지난 2년 연평균, 둘 다 0보다
    클 때만, 매출 이름표 없음) · 배당: 동전 그림 '1년 동안 → 약 {x}', 배당성향 고리 '이익 100원 중 {x}원' · 오른 날의 업종 줄 ·
    미국 머리줄 '{date} 종가 (미국 시간)' · '약 {won} · 환율 {fx}원'."""
    S = f"v19.3e 회사 {width}"
    f = v191b_files(co_files(files))
    d = f["data.json"]
    by = {s["t"]: s for s in d["stocks"]}
    coby = {c["t"]: c for c in f["corp.json"]["companies"]}
    semi = [s for s in d["stocks"] if s.get("ind") == by["005930"].get("ind") and s.get("cls") == "kr"]
    for s in semi:                                                             # 오른 날: 반도체가 다 같이 올랐어요, 삼성전자는 +6%
        s["d1"] = 6.0 if s["t"] == "005930" else 1.0
    deck = e_imported(by, d["pxDate"], [("005930", 10, None), ("005380", 10, None)])
    srv, ctx, page, base = R.open(build_site(f), width, init=e_store([deck]), path="/app.html?dev=1#stocks")

    def open_co(code):
        co_hash(page, f"#stocks/{code}")
        page.wait_for_function("(t) => { const e = document.querySelector('[data-ui-v2=\"co-head\"]'); return !!e && e.dataset.t === t; }", arg=code)

    def summary():
        wait_ready(page)
        open_co("005930")
        tiles = {t.get_attribute("data-topic"): t for t in page.locator('[data-ui-v2="co-tile"]').all()}
        op = coby["005930"]["op"]
        art = {k: (t.locator('[data-ui-v2="tile-art"]').get_attribute("data-art") if t.locator('[data-ui-v2="tile-art"]').count() else None) for k, t in tiles.items()}
        assert art["earn"] == ("bars" if all(x > 0 for x in op) else None), art
        assert [float(b.get_attribute("data-v")) for b in tiles["earn"].locator('[data-ui-v2="tile-art"] [data-v]').all()] == [op[2], op[1], op[0]]
        assert art["value"] == ("scale" if tiles["value"].get_attribute("data-rule") in ("cheap", "dear", "similar") else None), art
        if art["value"]:                                                      # 눈금 양 끝 '싸게 · 비싸게' (업종 중간 표시 · 업종과 비교하는 숫자 줄과 함께)
            assert tiles["value"].locator('[data-ui-v2="scale-ends"]').inner_text().split("\n") == [CO["tiles"]["scale"]["cheap"], CO["tiles"]["scale"]["dear"]]
            assert " · " in tiles["value"].locator('[data-ui-v2="tile-number"]').inner_text()
        assert art["div"] == ("coins" if div_shape(tiles["div"].get_attribute("data-rule")) else None), art
        if art["div"]:
            assert tiles["div"].locator('[data-art="coins"]').get_attribute("data-shape") == div_shape(tiles["div"].get_attribute("data-rule"))
        keys = page.locator('[data-ui-v2="wave-key"]').evaluate_all("els => els.map((e) => e.getBoundingClientRect().height)")
        assert keys and all(h < 24 for h in keys), keys                       # '이 회사' · '시장' 한 줄씩 (320px 에서도)
        risk = tiles["risk"].get_attribute("data-rule")
        assert art["risk"] == ("waves" if risk != "na" else None) and tiles["risk"].locator(f'[data-art="waves"][data-rule="{risk}"]').count() == (risk != "na")
        chips = page.locator('[data-ui-v2="co-warn-chip"]').evaluate_all("els => els.map(e => e.dataset.check)")
        assert chips == ["l3", "cr", "imp", "icr"], chips                    # 네 확인이 다 돌았고 걸린 게 없어요 (보드 순서)
        assert page.locator('[data-ui-v2="co-warn-chips"]').inner_text().split("\n") == [CO["warn"]["chips"][c] for c in chips]
        # 오른 날: '업종이 다 같이 오른 날이에요' · '{업종} 종목 {n}개 중 {k}개가 올랐어요'
        mv = page.locator('[data-ui-v2="co-move"]')
        assert mv.get_attribute("data-together") == "1" and CO["moveUp"]["together"] in mv.inner_text()
        cnt = re.fullmatch(re.escape(fillp(CO["moveUp"]["body"], ind=by["005930"]["indName"], n="N", k="K")).replace("N", r"(\d+)").replace("K", r"(\d+)"),
                           page.locator('[data-ui-v2="co-move-count"]').inner_text())
        assert cnt and cnt.group(1) == cnt.group(2) and int(cnt.group(1)) >= 5, page.locator('[data-ui-v2="co-move-count"]').inner_text()
        # 가진 포트폴리오 하나: '내 포트폴리오의 {x}%' (삼성전자 10주 · 현대차 10주)
        w = 10 * by["005930"]["price"] / (10 * by["005930"]["price"] + 10 * by["005380"]["price"]) * 100
        line = page.locator('[data-ui-v2="co-held-row"][data-deck-id="dimp"] [data-ui-v2="co-held-line"]').inner_text()
        assert line == fillp(CO["hold"]["mine"], x=f"{round(w)}"), (line, w)
        no_mascot(page)
        floor_ok(page, "회사 요약 (v19.3e)")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "요약: 칸마다 규칙대로 그림 · 재무 경고 칩 넷 · 오른 날 줄 · 내 포트폴리오의 {x}%", summary)

    navy, slate = rgb("#1C2B45"), rgb("#9AA3B2")          # Jack (2026-11-08): 그대로의 값

    def chart_colours():
        """그래프 색 (Jack, 2026-11-08): 실적 막대는 최근 해 남색 · 앞선 해 회청색(파랑 없음), '이 회사'는 어느 그래프에서나 남색(출렁임
        포함) · 비교하는 선은 회청색. 계산된 색으로 봐요."""
        open_co("005930")
        tile = page.locator('[data-ui-v2="co-tile"][data-topic="earn"] [data-art="bars"]')
        tile.wait_for(state="visible")
        # 요약 칸 왼쪽 띠 (Jack, 2026-11-08): 실적은 옅은 실적 주제 색 #B9CDEB (파랑 아님), 다른 칸은 주제의 진한 색 그대로
        stripes = dict(page.locator('[data-ui-v2="co-tile"]').evaluate_all(
            "els => els.map((e) => [e.dataset.topic, ((getComputedStyle(e).boxShadow || '').match(/rgb\\([^)]*\\)/) || [''])[0]])"))
        assert stripes == {"earn": rgb("#B9CDEB"), "value": rgb("#4E9A72"), "div": rgb("#C59A2E"), "risk": rgb("#8C78C6")}, stripes
        got = tile.locator("[data-v]").evaluate_all("els => els.map((e) => getComputedStyle(e).backgroundColor)")
        assert got == [slate, slate, navy], got                                # 요약 칸의 실적 막대 (오래된 해 → 최근 해)
        waves = page.locator('[data-ui-v2="co-tile"][data-topic="risk"] [data-art="waves"]')
        lines = waves.locator("polyline").evaluate_all("els => els.map((e) => e.dataset.line + ' ' + getComputedStyle(e).stroke)")
        assert lines == [f"market {slate}", f"mine {navy}"], lines             # 출렁임: 시장 회청색 · 이 회사 남색
        keys = waves.locator('[data-ui-v2="wave-key"] > span').evaluate_all("els => els.map((e) => getComputedStyle(e).backgroundColor)")
        assert keys == [navy, slate], keys                                     # 범례도 같은 색 ('이 회사' · '시장')
        co_open_tab(page, "005930", "earn", "kr")
        bars = page.locator('[data-ui-v2="co-earn"] [data-ui-v2="bars"] [data-bar]')
        bars.first.wait_for(state="visible")
        got = bars.evaluate_all("els => els.map((e) => e.dataset.bar + ' ' + getComputedStyle(e).backgroundColor)")
        assert got == [f"earlier {slate}", f"earlier {slate}", f"latest {navy}"], got   # 실적 탭의 막대도 같은 단계
        co_open_tab(page, "005930", "value", "kr")
        dcf = page.locator('[data-ui-v2="co-dcf"]')
        dcf.wait_for(state="visible")
        mine = dcf.locator('[data-ui-v2="co-dcf-implied"] [data-bar]')
        if mine.count():
            assert mine.get_attribute("data-bar") == "mine" and mine.evaluate("(e) => getComputedStyle(e).backgroundColor") == navy
        past = dcf.locator('[data-ui-v2="co-dcf-past"] [data-bar]')
        if past.count():                                                        # 지난 2년 실제 이익(비교)은 회청색, 파랑 아님
            assert past.get_attribute("data-bar") == "compare" and past.evaluate("(e) => getComputedStyle(e).backgroundColor") == slate
        R.collect(page)
    R.check(page, S, "그래프 색: 실적 칸 띠 #B9CDEB(파랑 아님) · 실적 막대 남색 · 회청색 단계(요약 칸 · 실적 탭) · 출렁임 이 회사 남색 · 시장 회청색 · 가치의 지난 이익 회청색", chart_colours)

    def div_coins():
        for code in (V191B_CUT, "105560", V191B_SPLIT, "AAPL"):
            open_co(code)
            t = page.locator('[data-ui-v2="co-tile"][data-topic="div"]')
            t.wait_for(state="visible")
            rule, coins = t.get_attribute("data-rule"), t.locator('[data-art="coins"]')
            want = div_shape(rule)
            assert (coins.get_attribute("data-shape") if coins.count() else None) == want, (code, rule, want)
            if rule == "cut":
                assert coins.count() == 0                                     # '배당을 줄였어요' 옆에 올라가는 동전 더미 없음
            if want:                                                          # 더미 수: 하나(pays · noPrev) 또는 셋
                xs = coins.evaluate("(e) => new Set([...e.querySelectorAll('ellipse')].map((c) => c.getAttribute('cx'))).size")
                assert xs == (1 if want == "one" else 3), (code, rule, xs)
            if code == "AAPL":                                                # 미국 '배당을 줘요': 3년 같은 높이 셋이 아니라 더미 하나
                assert rule == "pays" and want == "one", (rule, want)
        R.collect(page)
    R.check(page, S, "배당 칸 동전: 늘렸어요만 올라가는 더미 · 비슷하게 준 해는 같은 높이 셋 · 해마다 비교하지 않은 지급(미국 · 작년 기록 없음)은 더미 하나 · 줄였어요는 그림 없음", div_coins)

    def chips_only_when_ran():
        for code, want in ((V191B_ND, ["l3", "imp"]), (V191B_PART, ["l3", "cr", "imp"]), (V191B_CUT, None), (V191B_OPMISS, None)):
            open_co(code)
            page.locator('[data-ui-v2="co-tile"]').first.wait_for(state="visible")
            got = page.locator('[data-ui-v2="co-warn-chip"]').evaluate_all("els => els.map(e => e.dataset.check)")
            assert got == (want or []), (code, got)                          # 해당 없음 · 못 돌린 확인: 칩 없음 (✓ 없음)
            if want is None:
                assert page.locator('[data-ui-v2="co-warn"][data-n="0"]').count() == 0
        R.collect(page)
    R.check(page, S, "재무 경고 칩: 금융회사는 둘(해당 없음 빼고) · 이자보상배율 못 돌림은 셋 · 확인이 덜 돌면 카드도 칩도 없음", chips_only_when_ran)

    def value_fix():
        for code in ("005930", "000660", "005380"):
            open_co(code)
            co_open_tab(page, code, "value", "kr")
            dcf = page.locator('[data-ui-v2="co-dcf"]')
            dcf.wait_for(state="visible")
            txt = dcf.inner_text()
            for lab in (C["pick"]["receipt"]["growthKr"], C["pick"]["receipt"]["growthKr1y"]):
                assert lab not in txt, (code, lab)                            # 매출과 비교하지 않아요
            ni = coby[code]["ni"]
            if not dcf.get_attribute("data-g"):
                continue
            if ni[0] > 0 and ni[2] > 0:
                x = ((ni[0] / ni[2]) ** 0.5 - 1) * 100
                assert abs(float(dcf.get_attribute("data-past")) - js_round(x, 1)) < 1e-9, (code, dcf.get_attribute("data-past"), x)
                g = float(dcf.get_attribute("data-g"))
                vs = "similar" if abs(g - js_round(x, 1)) <= 3 + 1e-9 else "lower" if g < js_round(x, 1) else "higher"
                assert dcf.get_attribute("data-vs") == vs and CO["dcf"]["vs"][vs] in txt, (code, vs, txt)
                past = dcf.locator('[data-ui-v2="co-dcf-past"]').inner_text()
                assert CO["dcf"]["past"] in past and (CO["dcf"]["pastUp" if js_round(x, 1) >= 0 else "pastDown"].split("{x}")[1] in past), past
                assert "−" not in past and "-" not in past.replace(CO["dcf"]["past"], ""), past
            else:                                                             # 순이익이 0 이하인 해가 있으면 비교를 숨겨요 (카드는 그대로)
                assert dcf.get_attribute("data-vs") == "" and dcf.locator('[data-ui-v2="co-dcf-past"]').count() == 0, code
                assert not any(v in txt for v in CO["dcf"]["vs"].values()), code
            assert CO["dcf"]["impliedNi"] in dcf.locator('[data-ui-v2="co-dcf-implied"]').inner_text()
        cmp = page.locator('[data-ui-v2="co-compare"]')
        if cmp.count():
            assert cmp.locator("h3").inner_text() == fillp(CO["value"]["compare"], n=int(cmp.get_attribute("data-n")))
            assert cmp.locator('[data-ui-v2="co-strip"]').inner_text().split("\n")[0] == CO["value"]["where"]
            assert page.locator('[data-ui-v2="co-pbr"]').inner_text().split("\n")[1] == fillp(C["pick"]["receipt"]["times"], x=f"{by['005380']['pbr']:,.2f}")
        no_mascot(page)
        floor_ok(page, "회사 가치 (v19.3e)")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "가치: 순이익끼리 비교 (지난 2년 연평균 · 3%p 안이면 비슷) · 순이익이 0 이하면 비교 없음 · 매출 이름표 없음 · 업종 비교 카드", value_fix)

    def dividend():
        open_co("005930")
        co_open_tab(page, "005930", "div", "kr")
        m = page.locator('[data-ui-v2="co-million"]')
        m.wait_for(state="visible")
        if m.get_attribute("data-won"):
            flow = m.locator('[data-ui-v2="co-coinflow"]')
            assert flow.locator('[data-ui-v2="co-coinflow-label"]').inner_text() == CO["div"]["coins"]
            won = int(m.get_attribute("data-won"))
            man = f"{won / 10000:,.1f}만원" if won % 10000 else f"{won // 10000:,}만원"
            want = fillp(CO["div"]["pastYear"], x=man if won >= 10000 else f"{won:,}원")      # 지난 1년 배당 (예측이 아니에요)
            assert flow.locator('[data-ui-v2="co-coinflow-text"]').inner_text() == want
        pay = page.locator('[data-ui-v2="co-payout"]')
        if pay.count():
            pct = float(pay.get_attribute("data-pct"))
            x = js_round(pct, 0)
            assert 0 < pct <= 100 and CO["div"]["payoutQ"] in pay.inner_text()
            if 0 < x < 100:
                assert pay.locator('[data-ui-v2="co-payout-of"]').inner_text() == fillp(CO["div"]["payoutOf"], x=int(x))
                assert fillp(CO["div"]["payoutRest"], y=int(100 - x)) in pay.inner_text()
        no_mascot(page)
        floor_ok(page, "회사 배당 (v19.3e)")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "배당: 동전 그림 '1년 동안 → 약 {x}' · 배당성향 '이익 100원 중 {x}원 · 나머지 {y}원'", dividend)
    ctx.close()
    srv.shutdown()

    other = e_imported(by, d["pxDate"], [("005380", 5, None)], did="dother", name="배당 생활비 포트폴리오")
    srv, ctx, page, base = R.open(build_site(f), width, init=e_store([deck, other]), path="/app.html?dev=1#stocks/005930")

    def two_portfolios():
        co_wait(page)
        row = page.locator('[data-ui-v2="co-held-row"][data-deck-id="dimp"] [data-ui-v2="co-held-line"]')
        row.wait_for(state="visible")
        w = 10 * by["005930"]["price"] / (10 * by["005930"]["price"] + 10 * by["005380"]["price"]) * 100
        assert row.inner_text() == fillp(CO["hold"]["weight"], name="포트폴리오", pct=f"{round(w)}%"), row.inner_text()   # 포트폴리오가 둘: 이름과 함께
        assert CO["hold"]["mine"].split("{")[0] not in page.locator('[data-ui-v2="co-held"]').inner_text()
        R.collect(page)
    R.check(page, S, "포트폴리오가 둘이면 이 종목을 하나만 가져도 '{이름}의 {x}%' ('내 포트폴리오의'가 아니에요)", two_portfolios)
    ctx.close()
    srv.shutdown()

    srv, ctx, page, base = R.open(build_site(f), width, path="/app.html?dev=1#stocks/AAPL")

    def us_head():
        co_wait(page)
        md = f"{int(d['usPxDate'][5:7])}월 {int(d['usPxDate'][8:])}일"
        assert page.locator('[data-ui-v2="co-date"]').inner_text() == fillp(CO["usCloseTime"], date=md)
        won = int(js_round(by["AAPL"]["price"] * d["fx"] / 100, 0) * 100)
        fxs = f"{js_round(d['fx'], 1):,.1f}"
        assert page.locator('[data-ui-v2="co-won"]').inner_text() == fillp(CO["usWon"], won=f"{won:,}원", fx=fxs)
        assert page.locator('[data-ui-v2="co-fx"]').count() == 0
        R.collect(page)
    R.check(page, S, "미국 머리줄: '{date} 종가 (미국 시간)' · '약 {won} · 환율 {fx}원'", us_head)
    ctx.close()
    srv.shutdown()

    # 환율이 머리줄의 가격 날짜와 다른 날 것이면 '원화는 {md} 환율 {fx}원으로 바꾼 값이에요.'를 그대로 보여요 (그 날 환율로 읽히지 않게)
    fxo = clone(f)
    fx_day = (dt.date.fromisoformat(d["usPxDate"]) + dt.timedelta(days=1)).isoformat()
    fxo["data.json"]["fxDate"] = fx_day
    srv, ctx, page, base = R.open(build_site(fxo), width, path="/app.html?dev=1#stocks/AAPL")

    def us_head_fx_day():
        co_wait(page)
        md = f"{int(d['usPxDate'][5:7])}월 {int(d['usPxDate'][8:])}일"
        assert page.locator('[data-ui-v2="co-date"]').inner_text() == fillp(CO["usCloseTime"], date=md)
        won = int(js_round(by["AAPL"]["price"] * d["fx"] / 100, 0) * 100)
        fxs = f"{js_round(d['fx'], 1):,.1f}"
        assert page.locator('[data-ui-v2="co-won"]').inner_text() == fillp(CO["usWon"], won=f"{won:,}원", fx=fxs)
        line = page.locator('[data-ui-v2="co-fx"]')
        assert line.count() == 1 and line.get_attribute("data-fx-date") == fx_day
        assert line.inner_text() == fillp(CO["fxWon"], md=f"{int(fx_day[5:7])}월 {int(fx_day[8:])}일", fx=fxs), line.inner_text()
        R.collect(page)
    R.check(page, S, "미국 머리줄: 환율 날짜가 가격 날짜와 다르면 '원화는 {md} 환율 {fx}원으로 바꾼 값이에요.'", us_head_fx_day)
    ctx.close()
    srv.shutdown()


def scene_store_version(R, files, width, seeded):
    """저장 기록의 판(v) 고침 (hotfix): 가진 종목 포트폴리오가 없던 기록(v1: 비어 있거나 만든 포트폴리오만) → 가진 종목 넣기 →
    매일 점검 시작하기 → 새로 고치지 않고 내 메모 남기기 → 저장되고(기록에 메모) '날짜·수량·가격을 다시 확인해 주세요' 줄은 없어요.
    (고치기 전: 메모리의 기록이 v1 로 남아 판 2 부분을 가진 채 검사를 통과하지 못해, 그 뒤의 저장이 모두 거절됐어요.)"""
    S = f"기록 판 {width}" + (" (만든 포트폴리오 있음)" if seeded else " (빈 기록)")
    init = None
    if seeded:
        store = {"v": 1, "decks": [_deck("dcalm", "조용한 포트폴리오", [("000660", "SK하이닉스", 0.5, [], 1), (*SAMSUNG, 0.5, [], 6)])]}
        init = f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"
    srv, ctx, page, _ = R.open(build_site(files), width, init=init)
    stored = lambda: page.evaluate(STORED_JS)
    text = "실적 발표 뒤에 다시 볼게요"
    R.names = sorted(set(R.names) | {text, "조용한 포트폴리오"}, key=len, reverse=True)      # 사용자가 쓴 글 · 시험 기록의 이름 (문구 파일 밖)

    def run():
        wait_ready(page)
        if seeded:
            assert stored()["v"] == 1 and len(stored()["decks"]) == 1
        to_build_start(page, False)
        page.locator('[data-ui-v2="start-holdings"]').click()
        at(page, "portfolio/import")
        page.locator('[data-ui-v2="import-search"] input').fill("005380")
        page.locator('[data-import-result="005380"] button').click()
        page.locator('[data-import-row="005380"] input[data-ui-v2="import-qty"]').fill("3")
        action(page).click()
        see(page, C["build"]["s1"]["title"])
        page.locator('[data-card="value"] [data-ui-v2="card-inc"]').click()
        action(page).click()
        page.locator('[data-ui-v2="report"]').wait_for(state="visible")
        page.locator('[data-ui-v2="report-start"]').click()
        at(page, "portfolio")
        d = stored()
        assert d["v"] == 2 and [x.get("kind") for x in d["decks"]] == ([None] if seeded else []) + ["imported"], d
        page.evaluate("window.__sameVisit = 1")                         # 새로 고치면 사라져요
        page.evaluate("location.hash = '#stocks/005930'")              # 같은 문서 안에서 회사 페이지로
        at(page, "stocks/005930")
        co_wait(page)
        page.locator('[data-ui-v2="co-memo"] button', has_text=CO["memo"]["add"]).click()
        page.locator('[data-ui-v2="co-memo-form"] textarea').fill(text)
        page.locator('[data-ui-v2="co-memo-form"] button', has_text=C["plan"]["save"]).click()
        page.locator('[data-ui-v2="co-memo-text"], [data-ui-v2="store-refused"]').first.wait_for(state="visible")
        assert page.evaluate("window.__sameVisit") == 1, "새로 고쳐졌어요"
        refused = page.locator('[data-ui-v2="store-refused"]')
        assert refused.count() == 0, "저장이 거절됐어요: " + refused.inner_text()
        assert C["plan"]["badInput"] not in page.locator("body").inner_text()
        assert page.locator('[data-ui-v2="co-memo-text"]').inner_text() == text
        d = stored()
        assert d["v"] == 2 and d["notes"]["005930"]["text"] == text and len(d["decks"]) == (2 if seeded else 1), d
        R.collect(page)
    R.check(page, S, "가진 종목 넣기 → 매일 점검 시작하기 → 새로 고치지 않고 내 메모 남기기: 저장되고, 거절 줄 없음", run)
    ctx.close()
    srv.shutdown()


def scene_bystock_fit(R, files, width):
    """v19.3d2 리뷰 2: 점검의 종목별로 보면 — 기준 3 · 4 · 6개에서 페이지는 가로로 넘치지 않고, 이름 칸은 이름에 64px 이상(로고는 그
    자리가 있을 때만), 표가 카드보다 넓으면 카드 안에서 밀리고 오른쪽 끝이 흐려져 더 있다는 것을 보여 줘요(밀어서 끝에 가면 사라져요)."""
    S = f"종목별로 보면 {width}"
    srv, ctx, page, base = R.open(build_site(files), width)
    sets = (("value", "div", "stable"), ("value", "div", "stable", "growth"), ("value", "div", "stable", "growth", "profit", "lowVol"))

    def run():
        for cards in sets:
            page.goto(base + "/app.html?dev=1", wait_until="domcontentloaded")
            wait_ready(page)
            to_build_start(page, False)
            page.locator('[data-ui-v2="start-holdings"]').click()
            at(page, "portfolio/import")
            for t in ("005930", "005380", "000660"):
                page.locator('[data-ui-v2="import-search"] input').fill(t)
                page.locator(f'[data-import-result="{t}"] button').click()
                page.locator(f'[data-import-row="{t}"] input[data-ui-v2="import-qty"]').fill("3")
            action(page).click()
            for c in cards:
                page.locator(f'[data-card="{c}"] [data-ui-v2="card-inc"]').click()
            action(page).click()
            page.locator('[data-ui-v2="report"]').wait_for(state="visible")
            box = page.locator('[data-ui-v2="bystock-scroll"]')
            box.scroll_into_view_if_needed()
            page.wait_for_timeout(100)
            m = box.evaluate("""e => ({ cw: e.clientWidth, sw: e.scrollWidth, logo: e.getAttribute('data-logo'),
              names: [...e.querySelectorAll('[data-report-row]')].map((r) => { const n = [...r.querySelectorAll('span')].find((x) => getComputedStyle(x).textOverflow === 'ellipsis'); return n ? n.clientWidth : 0; }),
              marks: e.querySelectorAll('[data-report-row] [data-ui-v2="co-mark"]').length })""")
            no_hscroll(page, width)
            assert min(m["names"]) >= 64 - 0.5, (cards, m)                   # 이름에 64px 이상
            assert (m["logo"] == "1") == (m["cw"] >= 64 + 40 + len(cards) * 56) and (m["marks"] > 0) == (m["logo"] == "1"), (cards, m)
            more = page.locator('[data-ui-v2="bystock-more"]')
            if m["sw"] > m["cw"] + 1:                                          # 카드 안에서 밀려요: 오른쪽 끝이 흐려요
                assert more.count() == 1, (cards, m)
                box.evaluate("e => { e.scrollLeft = e.scrollWidth; }")
                page.wait_for_timeout(100)
                assert more.count() == 0, "끝까지 밀었는데 흐림이 남아요"
            else:
                assert more.count() == 0, (cards, m)
            R.collect(page)
    R.check(page, S, "기준 3 · 4 · 6개: 페이지 가로 넘침 없음 · 이름 64px 이상 · 로고는 자리가 있을 때만 · 카드 안에서 밀리면 오른쪽 끝 흐림", run)
    ctx.close()
    srv.shutdown()


# ── 2026-11-08 (Jack): DART 다시 읽기 전까지의 두 줄 (src/repair.js · src/v2/fix.js · src/v2/fixnote.jsx) ──
FIX_EPS_TPL = C["fix"]["eps"]
FIX_ICR = C["fix"]["icr"]
FIX_TOTAL = C["fix"]["total"]          # 다시 읽은 뒤 "t" + epsIn.nci (Jack 2026-11-08): 고치는 중 줄 자리에
with open(os.path.join(ROOT, "src", "repair.js"), encoding="utf-8") as _f:
    _FIXD = re.findall(r'^export const EPS_FIX_DATE = "(\d{4})-(\d{2})-(\d{2})";$', _f.read(), flags=re.M)
assert len(_FIXD) == 1, _FIXD
FIX_EPS = FIX_EPS_TPL.replace("{date}", f"{int(_FIXD[0][1])}월 {int(_FIXD[0][2])}일")
FIX_OFF_KR = "005930"          # 걸린 경고 없음 · 이자보상배율 꺼짐 → 재무 경고 카드 자리에 그 줄
FIX_FLAG_KR = "373220"         # LG에너지솔루션: 유동비율 경고 · 이자보상배율 꺼짐 → 목록 밑에 그 줄 (PER 1,041배 · EPS 345원)
FIX_T_KR = "005380"            # 현대차: 다시 읽은 뒤에도 총 순이익 (epsIn.b "t") → 줄이 남고, 주가 분해 · 지금 가격이 가정하는 것은 숫자 대신 그 줄
FIX_PREF = 815974664           # 삼성전자우 상장 주식 수 (다시 읽은 epsIn.sh = 보통주 + 상장 우선주)


def fix_files(files, live):
    """live False: 지금의 발행처럼 (epsBasis 없음 · 두 회사의 flWhy.icr "off" · epsIn 없음). live True: 다시 읽기가 끝난 발행의 모양
    (지어낸 값): epsBasis "owners" · 회사마다 epsIn {ni, b, p, sh} 와 지배주주 순이익 nio3 (억원), 그 기준의 eps (삼성전자 · LG에너지솔루션
    "o", 현대차 "t") · 이자보상배율이 다시 돌아요 (flWhy 없음 · flRan 에 icr)."""
    f = clone(files)
    coby = {x["t"]: x for x in f["corp.json"]["companies"]}
    if live:
        f["corp.json"]["epsBasis"] = "owners"
        coby[FIX_OFF_KR].update(flRan=["cr", "icr", "l3", "imp"])
        coby[FIX_FLAG_KR].update(flRan=["cr", "icr", "l3", "imp"], fl={"cr": 85})
        sam = coby[FIX_OFF_KR]
        sh = round(sam["shm"] * 1e6) + FIX_PREF
        # p "fy": 지배주주 EPS 가 사업보고서 기준 (bq 가 있어도) — 이름표가 '사업보고서'여야 해요 (PR #89 리뷰)
        sam.update(epsIn={"ni": 450000.0, "b": "o", "p": "fy", "sh": sh}, bpsIn={"p": "fy"}, nio3=[442609.56, 336213.63, 144734.01],
                   eps=round(450000.0 * 1e8 / sh))
        coby[FIX_FLAG_KR].update(epsIn={"ni": -8000.0, "b": "o", "p": "2026.2Q", "sh": 234000000}, nio3=[-10728.1, -10187.41, 12371.8],
                                 eps=round(-8000.0 * 1e8 / 234000000))
        hd = coby[FIX_T_KR]
        hd.update(epsIn={"ni": 100000.0, "b": "t", "p": "2026.2Q", "sh": round(hd["shm"] * 1e6), "how": "total", "nci": True})   # 소수주주 있음 (2026-11-08)
    else:
        f["corp.json"].pop("epsBasis", None)
        coby[FIX_OFF_KR].update(flRan=["cr", "l3", "imp"], flWhy={"icr": "off"})
        coby[FIX_FLAG_KR].update(flRan=["cr", "l3", "imp"], flWhy={"icr": "off"}, fl={"cr": 85})
    return f


def fix_store():
    pxd = "2026-10-30"
    deck = {"id": "dfix", "name": "가진 종목", "createdAt": pxd, "kind": "imported", "settings": {"points": {"value": 2}, "strict": "normal"},
            "holdings": [{"t": FIX_OFF_KR, "nk": "삼성전자", "cls": "kr"}], "purchases": [],
            "imported": [{"t": FIX_OFF_KR, "nk": "삼성전자", "ccy": "KRW", "qty": 10}]}
    store = {"v": 2, "decks": [deck]}
    return f"(() => {{ try {{ if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }} catch (e) {{}} }})();"


def scene_fix_notes(R, files, width, live=False, shots=None):
    """2026-11-08 (Jack): 한국 PER · EPS (와 같은 순이익으로 계산한 숫자) 칸마다 'PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수
    있어요.' 한 줄 (미국 종목은 없음), 이자보상배율이 꺼진 회사의 재무 경고에 '이자보상배율은 계산 방법을 고치는 중이라 지금은 확인하지
    않아요.' (경고가 있으면 목록 밑 · 없으면 카드 자리 · 가진 종목 '재무 경고 0개'의 확인하지 못했어요 밑). 12px 이상.
    live: corp.json 에 epsBasis "owners" 가 있고 그 회사의 epsIn.b 가 "o" 이며 이자보상배율이 다시 돌면 그 회사에는 두 줄이 없어요
    (총 순이익 "t" 인 현대차에는 남아요). shots: 스크린샷 폴더 (선택)."""
    S = f"고치는 중 안내 {'끝' if live else '지금'} {width}"
    wide = width >= 1024
    fx = fix_files(files, live)
    coby = {x["t"]: x for x in fx["corp.json"]["companies"]}
    srv, ctx, page, base = R.open(build_site(fx), width, init=fix_store(), path=f"/app.html?dev=1#stocks/{FIX_OFF_KR}/value",
                                  device=pc_device(width) if wide else None)

    def eps_lines(sel):
        loc = page.locator(f'{sel} [data-ui-v2="eps-fix"]')
        return [loc.nth(i).inner_text() for i in range(loc.count())]

    def per_card():
        """PER 이 있는 카드: v19.3e 의 '업종 {n}개 회사와 비교' 카드, 비교할 업종이 없으면 가치 탭의 첫 카드."""
        return '[data-ui-v2="co-compare"]' if page.locator('[data-ui-v2="co-compare"]').count() else '[data-ui-v2="co-value"] > section:first-child'

    def past_want(co):
        """v19.3e '지난 2년 실제 이익' 연평균: EPS 와 같은 기준 (지금: ni · 다시 읽은 뒤 "o": nio3)."""
        ni = co["nio3"] if (co.get("epsIn") or {}).get("b") == "o" else co["ni"]
        return round((math.sqrt(ni[0] / ni[2]) - 1) * 100, 1) if ni[0] > 0 and ni[2] > 0 else None

    def shot(name):
        if shots:
            os.makedirs(shots, exist_ok=True)
            page.screenshot(path=os.path.join(shots, name), full_page=True)

    def value_tab():
        co_wait(page)
        page.locator('[data-ui-v2="co-value"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="co-per"]').count() == 1, "PER 칸이 없어요"
        first = per_card()
        if live:
            assert page.locator('[data-ui-v2="eps-fix"]').count() == 0, eps_lines("body")
        else:
            assert eps_lines(first) == [FIX_EPS], eps_lines(first)
            assert page.locator('[data-ui-v2="co-dcf"]').count() == 1 and eps_lines('[data-ui-v2="co-dcf"]') == [FIX_EPS]   # 같은 순이익
            per_y = page.locator('[data-ui-v2="co-per"]').bounding_box()["y"]
            line_y = page.locator(f'{first} [data-ui-v2="eps-fix"]').bounding_box()["y"]
            assert line_y > per_y, (line_y, per_y)                                        # 숫자 밑
            assert page.locator('[data-ui-v2="eps-fix"]').count() == 2, eps_lines("body")    # 카드마다 한 줄 (줄마다가 아니에요)
        # 근거 줄의 기간: 지금은 bq(최근 4개 분기), 다시 읽은 뒤 epsIn.p · bpsIn.p "fy" 면 사업보고서 (bq 가 있어도)
        vb = page.locator('[data-ui-v2="co-value-basis"]').inner_text()
        co = coby[FIX_OFF_KR]
        assert co.get("bq") == "2026.2Q", co.get("bq")
        want = fillp(C["co"]["value"]["basisY"], fy=co["fy"]) if live else fillp(C["co"]["value"]["basisQ"], y=2026, q=2)
        assert vb == want, (vb, want)
        # v19.3e '지금 주가가 가정하는 이익 증가 / 지난 2년 실제 이익': 지난 2년도 EPS 와 같은 기준 (다시 읽은 뒤 "o" 는 지배주주 순이익)
        dcf = page.locator('[data-ui-v2="co-dcf"]')
        pw = past_want(co)
        if not live or pw is not None:
            assert dcf.get_attribute("data-past") and pw is not None, "지난 2년 비교 막대가 없어요 (이 확인이 뜻이 없어요)"
        if dcf.count() and dcf.get_attribute("data-g") and pw is not None and dcf.get_attribute("data-past"):
            assert abs(float(dcf.get_attribute("data-past")) - pw) < 1e-9, (dcf.get_attribute("data-past"), pw)
        floor_ok(page, "가치 탭")
        no_hscroll(page, width)
        shot("v2-005930-value.png")
        R.collect(page)
    R.check(page, S, f"{FIX_OFF_KR} 가치 탭: PER 카드 · 지금 가격이 가정하는 것에 한 줄씩" + (" — 다시 읽기 뒤에는 없음" if live else ""), value_tab)

    def other_tabs():
        for ctab, sel, why in (("earn", '[data-ui-v2="co-decomp"]', "주가는 무엇으로 움직였나 (EPS · PER)"),
                               ("div", None, "배당성향")):
            co_hash(page, f"#stocks/{FIX_OFF_KR}/{ctab}")
            page.wait_for_function("(t) => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === t", arg=ctab)
            if sel is None:                         # v19.3e: 배당성향은 고리 카드(section co-payout), 문구가 없으면 예전 칸(co-div-stats)
                sel = 'section[data-ui-v2="co-payout"]' if page.locator('section[data-ui-v2="co-payout"]').count() else '[data-ui-v2="co-div-stats"]'
            card = page.locator(sel)
            if live:
                assert page.locator('[data-ui-v2="eps-fix"]').count() == 0, (ctab, eps_lines("body"))
            elif card.count():
                head = card.get_attribute("data-head") or ""
                shown = head in ("upE", "upM", "downE", "downM", "loss") if ctab == "earn" else page.locator('[data-ui-v2="co-payout"]').count() == 1
                assert eps_lines(sel) == ([FIX_EPS] if shown else []), (ctab, why, head, eps_lines(sel))
            floor_ok(page, why)
            R.collect(page)
    R.check(page, S, f"{FIX_OFF_KR} 실적 · 배당 탭: 주가 분해 · 배당성향 칸에 한 줄" + (" — 없음" if live else ""), other_tabs)

    def split_basis():
        """주가는 무엇으로 움직였나: 두 끝이 EPS 와 같은 기준 (지금: 총 순이익 ÷ 보통주 · 다시 읽은 뒤: 지배주주 순이익 ÷ 보통주 + 우선주)."""
        co = coby[FIX_OFF_KR]
        co_hash(page, f"#stocks/{FIX_OFF_KR}/earn")
        card = page.locator('[data-ui-v2="co-decomp"]')
        card.wait_for(state="visible")
        assert card.get_attribute("data-head") in ("upE", "upM", "downE", "downM"), card.get_attribute("data-head")
        then = co["nio3"][2] * 1e8 / co["epsIn"]["sh"] if live else co["ni"][2] * 100 / co["shm"]
        want = co["eps"] / then
        got = float(card.locator('[data-ui-v2="co-decomp-eq"]').get_attribute("data-eps"))
        assert abs(got - want) < 1e-9, (got, want)
        assert f"{round(then):,}원" in card.inner_text(), (round(then), card.inner_text())     # 3년 전 EPS 도 그 기준
        D = C["co"]["decomp"]
        want = fillp(D["basisY"], fy=co["fy"] - 2, fyNow=co["fy"]) if live else fillp(D["basisQ"], y=2026, q=2, fy=co["fy"] - 2)
        assert want in card.inner_text(), (want, card.inner_text())                               # 이름표도 EPS 의 기간대로
        floor_ok(page, "주가 분해")
        R.collect(page)
        # 현대차: 다시 읽은 뒤 총 순이익("t") → 숫자 없이 그 줄 (주가 분해 · 지금 가격이 가정하는 것), 가치 카드의 줄도 남아요
        co_hash(page, f"#stocks/{FIX_T_KR}/earn")
        card = page.locator('[data-ui-v2="co-decomp"]')
        card.wait_for(state="visible")
        if live:
            assert card.get_attribute("data-head") == "basis" and card.locator('[data-ui-v2="co-decomp-eq"]').count() == 0, card.inner_text()
            assert [card.locator('[data-ui-v2="eps-total"]').nth(i).inner_text() for i in range(card.locator('[data-ui-v2="eps-total"]').count())] == [FIX_TOTAL]
            assert card.locator('[data-ui-v2="eps-fix"]').count() == 0
            assert C["co"]["decomp"]["none"] not in card.inner_text() and C["co"]["tiles"]["na"] not in card.inner_text()
        else:
            assert card.get_attribute("data-head") != "basis"
        R.collect(page)
        co_hash(page, f"#stocks/{FIX_T_KR}/value")
        page.locator('[data-ui-v2="co-value"]').wait_for(state="visible")
        dcf = page.locator('[data-ui-v2="co-dcf"]')
        if live:
            assert dcf.get_attribute("data-edge") == "basis" and dcf.locator('[data-ui-v2="co-dcf-inputs"]').count() == 0, dcf.inner_text()
            assert dcf.locator('[data-ui-v2="eps-total"]').count() == 1 and dcf.locator('[data-ui-v2="eps-fix"]').count() == 0
        else:
            assert dcf.count() == 0 or dcf.get_attribute("data-edge") != "basis"
        assert page.locator(f'{per_card()} [data-ui-v2="{"eps-total" if live else "eps-fix"}"]').count() == 1   # 총 순이익 + 소수주주: 다시 읽은 뒤 총 순이익 줄
        floor_ok(page, "현대차 가치 탭")
        R.collect(page)
    R.check(page, S, "주가 분해: 두 끝이 같은 기준 (삼성전자)" + (" · 현대차 't'는 숫자 대신 그 줄 (주가 분해 · 지금 가격이 가정하는 것)" if live else " · 현대차도 숫자"), split_basis)

    def lges():
        co_hash(page, f"#stocks/{FIX_FLAG_KR}/value")
        page.locator('[data-ui-v2="co-per"]').wait_for(state="visible")
        assert "1,041.1" in page.locator('[data-ui-v2="co-per"]').inner_text(), page.locator('[data-ui-v2="co-per"]').inner_text()
        assert eps_lines(per_card()) == ([] if live else [FIX_EPS])
        floor_ok(page, "LG에너지솔루션 가치 탭")
        R.collect(page)
    R.check(page, S, f"{FIX_FLAG_KR} LG에너지솔루션 가치 탭 (PER 1,041배): " + ("줄 없음" if live else "그 줄"), lges)

    def us_stock():
        for ctab in ("value", "earn", "div", None):
            co_hash(page, "#stocks/AAPL" + (f"/{ctab}" if ctab else ""))
            page.wait_for_function("(t) => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === t", arg=ctab or "summary")
            assert page.locator('[data-ui-v2="eps-fix"]').count() == 0, (ctab, eps_lines("body"))     # 미국 종목: SEC · 야후 숫자라 없어요
            assert page.locator('[data-ui-v2="icr-off"]').count() == 0 and page.locator('[data-ui-v2="co-warn-off"]').count() == 0
            if ctab == "value":
                assert page.locator('[data-ui-v2="co-per"]').count() == 1, "미국 PER 칸이 있어야 이 확인이 뜻이 있어요"
        R.collect(page)
    R.check(page, S, "미국 종목(AAPL) 모든 탭: PER 이 보여도 두 줄 다 없음", us_stock)

    def warn_card():
        co_hash(page, f"#stocks/{FIX_OFF_KR}")
        page.locator('[data-ui-v2="co-summary"]').wait_for(state="visible")
        off = page.locator('[data-ui-v2="co-warn-off"]')
        if live:
            page.locator('[data-ui-v2="co-warn"][data-n="0"]').wait_for(state="visible")         # 네 가지가 다 돌면 '재무 경고 신호는 없어요'
            assert off.count() == 0 and page.locator('[data-ui-v2="icr-off"]').count() == 0
        else:
            off.wait_for(state="visible")
            assert off.inner_text().strip() == FIX_ICR, off.inner_text()
            # v19.3e: 확인이 덜 돌면 칩도 없음 (이자보상배율이 꺼져 있으면 그 줄만)
            assert off.locator('[data-ui-v2="co-warn-chip"]').count() == 0 and page.locator('[data-ui-v2="co-warn-chips"]').count() == 0
            assert page.locator('[data-ui-v2="co-warn"]').count() == 0                            # '없어요'라고 말하지 않아요
            assert C["co"]["warn"]["none"] not in page.locator('[data-ui-v2="co-summary"]').inner_text()
            off.scroll_into_view_if_needed()
            if shots:
                os.makedirs(shots, exist_ok=True)
                page.screenshot(path=os.path.join(shots, "v2-005930-warn-card.png"))
        floor_ok(page, "재무 경고 (경고 없음)")
        no_mascot(page)
        R.collect(page)
        co_hash(page, f"#stocks/{FIX_FLAG_KR}")
        btn = page.locator('[data-ui-v2="co-warn"][data-n="1"]')
        btn.wait_for(state="visible")
        assert btn.locator('[data-ui-v2="icr-off"]').count() == (0 if live else 1)
        if not live:
            assert btn.locator('[data-ui-v2="icr-off"]').inner_text() == FIX_ICR
            btn.scroll_into_view_if_needed()
            if shots:
                page.screenshot(path=os.path.join(shots, "v2-373220-warn-row.png"))
        btn.click()
        sheet = page.locator('[data-ui-v2="co-warn-list"]')
        sheet.wait_for(state="visible")
        assert sheet.locator('[data-ui-v2="icr-off"]').count() == (0 if live else 1)
        if not live:
            assert sheet.locator('[data-ui-v2="icr-off"]').inner_text() == FIX_ICR
            assert sheet.locator("[data-flag]").last.bounding_box()["y"] < sheet.locator('[data-ui-v2="icr-off"]').bounding_box()["y"]   # 목록 밑
            if shots:
                page.screenshot(path=os.path.join(shots, "v2-373220-warn-sheet.png"))
        floor_ok(page, "재무 경고 목록")
        R.collect(page)
        page.keyboard.press("Escape")
    R.check(page, S, "재무 경고: 경고 없음이면 카드 자리에 그 줄 · 경고가 있으면 줄과 목록 밑에" + (" — 다시 켜지면 없음" if live else ""), warn_card)

    def holdings_tile():
        page.evaluate("() => { location.hash = '#portfolio'; }")
        at(page, "portfolio")
        tile = page.locator('[data-deck-id="dfix"] [data-ui-v2="pf-rule"][data-rule="warn"]')
        tile.wait_for(state="visible")
        if live:
            assert tile.get_attribute("data-state") == "ok" and tile.locator('[data-ui-v2="icr-off"]').count() == 0, tile.inner_text()
        else:
            assert tile.get_attribute("data-state") == "unknown", tile.get_attribute("data-state")
            assert tile.locator('[data-ui-v2="pf-rule-unknown"]').inner_text() == C["pfr"]["unknown"]
            assert tile.locator('[data-ui-v2="icr-off"]').inner_text() == FIX_ICR, tile.inner_text()
            tile.scroll_into_view_if_needed()
            if shots:
                page.screenshot(path=os.path.join(shots, "v2-holdings-warn-tile.png"))
        floor_ok(page, "가진 종목 규칙 칸")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "가진 종목 '재무 경고 0개': 확인하지 못했어요 밑에 이유" + (" — 다시 켜지면 ✓" if live else ""), holdings_tile)

    def home_hero():
        """v19.3e 새 홈의 네 규칙(남색): '재무 경고 0개 · 확인하지 못했어요' 밑에 이자보상배율 줄 (다시 켜지면 없음)."""
        page.evaluate("() => { location.hash = '#home'; }")
        at(page, "home")
        hero = page.locator('[data-ui-v2="home-rules"][data-deck-id="dfix"]')
        hero.wait_for(state="visible")
        tile = hero.locator('[data-ui-v2="home-rule"][data-rule="warn"]')
        line = hero.locator('[data-ui-v2="icr-off"]')
        if live:
            assert tile.get_attribute("data-state") == "ok" and line.count() == 0, hero.inner_text()
        else:
            assert tile.get_attribute("data-state") == "unknown" and line.inner_text() == FIX_ICR, hero.inner_text()
            assert line.bounding_box()["y"] > tile.bounding_box()["y"]                       # 칸들 밑
            if shots:
                hero.screenshot(path=os.path.join(shots, "v2-home-hero.png"))
        floor_ok(page, "새 홈 규칙")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, "새 홈(v19.3e)의 네 규칙: 재무 경고 0개 밑에 이유" + (" — 다시 켜지면 없음" if live else ""), home_hero)
    ctx.close()
    srv.shutdown()


# ── 공시 단위 확인 (Jack, 2026-11-13 · src/repair.js 5 · src/v2/fixnote.jsx UnitChkNote) ──
UNIT_T = "028260"                 # 시험 데이터의 삼성물산을 단위가 틀린 재무제표로 숫자를 비운 회사로 (배당은 남아요)
UNIT_LINE = C["co"]["unitChk"]
FIX_T = "005930"                  # 시험 데이터의 삼성전자를 공시 단위를 고쳐 읽은 회사로 (corp.json unitFix · 숫자는 그대로)
FIX_LINE = C["co"]["unitFix"]     # Jack 2026-11-13 (Q13): 가치 자세히에만


def unit_files(files):
    """fetch_data.py unit_guard · build_corp 가 하는 대로 한 회사의 재무제표 숫자를 비우고 unitChk ["scale"] (배당은 그대로)."""
    f = clone(files)
    co = next(c for c in f["corp.json"]["companies"] if c["t"] == UNIT_T)
    co.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False, vz=None, qz=None,
              per=None, pbr=None, eps=None, bps=None, roe=None, debt=None, opm=None, g3=None, flRan=[], unitChk=["scale"])
    for k in ("evE", "evR", "pcf", "bq", "nio3", "nio3Hyb", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep", "fl", "flSrc", "flWhy"):
        co.pop(k, None)
    st = next(x for x in f["data.json"]["stocks"] if x["t"] == UNIT_T)
    for k in ("per", "pbr", "eps", "bps", "roe", "debt", "opm", "g3", "vz", "qz"):
        st.pop(k, None)
    st["unitChk"] = ["scale"]
    assert st.get("dps", 0) > 0, "배당을 주는 회사여야 배당성향 자리를 볼 수 있어요"
    return f


def scene_unit_chk(R, files, width, shots=None):
    """공시 단위 확인 (Jack, 2026-11-13): unitChk 회사의 회사 페이지 — 숫자가 비는 영역마다 그 줄 한 번, 비어 있는 실적 · 가치 칸과 숫자 없는
    카드는 없어요 (배당 · 출렁임은 그대로). 다른 회사에는 없어요. 12px 이상 · 가로 스크롤 없음 · 뱁이 없음."""
    S = f"공시 단위 {width}"
    deck = {"id": "dunit", "name": "가진 종목", "createdAt": "2026-10-30", "kind": "imported", "settings": {"points": {"value": 2}, "strict": "normal"},
            "holdings": [{"t": UNIT_T, "nk": "삼성물산", "cls": "kr"}], "purchases": [],
            "imported": [{"t": UNIT_T, "nk": "삼성물산", "ccy": "KRW", "qty": 10}]}
    init = ("(() => { try { if (!localStorage.getItem('baepsae2.v1')) localStorage.setItem('baepsae2.v1', "
            + json.dumps(json.dumps({"v": 2, "decks": [deck]}, ensure_ascii=False)) + "); } catch (e) {} })();")
    site = unit_files(files)
    next(c for c in site["corp.json"]["companies"] if c["t"] == FIX_T)["unitFix"] = [{"rep": "2026.2Q", "bs": 1000, "is": 1000, "cf": 1000}]
    srv, ctx, page, base = R.open(build_site(site), width, init=init)
    page.locator('[data-ui-v2="date-line"], [data-ui-v2="load-fail"]').first.wait_for(state="visible")

    def lines_in(sel=None):
        loc = page.locator((sel + " " if sel else "") + '[data-ui-v2="unit-chk"]')
        return [loc.nth(i).inner_text().strip() for i in range(loc.count())]

    def shot(name):
        if shots:
            os.makedirs(shots, exist_ok=True)
            page.screenshot(path=os.path.join(shots, name), full_page=True)

    def summary():
        co_hash(page, f"#stocks/{UNIT_T}")
        page.locator('[data-ui-v2="co-summary"]').wait_for(state="visible")
        tiles = page.locator('[data-ui-v2="co-tiles"]')
        assert lines_in('[data-ui-v2="co-tiles"]') == [UNIT_LINE], lines_in('[data-ui-v2="co-tiles"]')       # 한눈에: 한 번, 칸들 위
        assert page.locator('[data-ui-v2="co-tiles"] [data-ui-v2="unit-chk"]').bounding_box()["y"] < page.locator('[data-ui-v2="co-tile"]').first.bounding_box()["y"]
        topics = tiles.locator('[data-ui-v2="co-tile"]').evaluate_all("(els) => els.map((e) => e.dataset.topic)")
        assert topics == ["div", "risk"], topics                                                         # 비어 있는 실적 · 가치 칸은 없어요
        assert C["co"]["tiles"]["na"] not in tiles.inner_text(), tiles.inner_text()
        assert lines_in('[data-ui-v2="co-warn-unit"]') == [UNIT_LINE]                                      # 재무 경고 자리: 한 번
        assert page.locator('[data-ui-v2="co-warn"]').count() == 0                                         # '경고 신호는 없어요'라고 말하지 않아요
        fit = page.locator('[data-ui-v2="co-fit"]')
        if fit.count():
            rows = fit.locator('[data-ui-v2="rank-row"]').evaluate_all("(els) => els.map((e) => [e.dataset.card, e.dataset.side])")
            blank = any(c in ("value", "profit", "stable", "growth") and side == "blank" for c, side in rows)
            assert len(lines_in('[data-ui-v2="co-fit"]')) == (1 if blank else 0), (rows, lines_in('[data-ui-v2="co-fit"]'))
        n = sum(1 for x in lines_in() if x == UNIT_LINE)
        assert n == len(lines_in()) == 2 + len(lines_in('[data-ui-v2="co-fit"]')), lines_in()             # 영역마다 한 번씩만
        for x in page.locator('[data-ui-v2="unit-chk"]').evaluate_all("(els) => els.map((e) => parseFloat(getComputedStyle(e).fontSize))"):
            assert x >= 12, x
        floor_ok(page, "공시 단위 요약")
        no_hscroll(page, width)
        no_mascot(page)
        R.collect(page)
        shot(f"unitchk-summary-{width}.png")
    R.check(page, S, f"{UNIT_T} 요약: 한눈에 칸 위 · 재무 경고 자리 · 내 기준에 한 번씩, 실적 · 가치 칸 없음", summary)

    def tabs():
        for ctab, inside in (("earn", '[data-ui-v2="co-earn"]'), ("value", '[data-ui-v2="co-value"]'), ("div", '[data-ui-v2="co-div"]'),
                             ("value-more", '[data-ui-v2="co-value-more"]'), ("earn-more", '[data-ui-v2="co-earn-more"]')):
            co_hash(page, f"#stocks/{UNIT_T}/{ctab}")
            page.locator(inside).first.wait_for(state="visible")
            assert lines_in() == [UNIT_LINE], (ctab, lines_in())                                          # 한 번
            assert len(lines_in(inside)) == 1, ctab
            if ctab == "earn":
                # v19.6d: any picker on the page but the 화면 모드 switch (PC's left menu has it, a segmented control too)
                assert page.locator('[data-ui-v2="co-earn-big"]').count() == 0 and page.locator(SEGMENTED).count() == 0
                assert page.locator('[data-ui-v2="co-decomp"]').count() == 0 and page.locator('[data-ui-v2="co-earn-more"]').count() == 0
            elif ctab == "value":
                for k in ("co-pbr", "co-per", "co-compare", "co-dcf", "co-value-basis", "co-value-more"):
                    assert page.locator(f'[data-ui-v2="{k}"]').count() == 0, k
                assert page.locator('[data-ui-v2="co-risk"]').count() == 1                                   # 출렁임은 그대로
            elif ctab == "div":
                assert page.locator('[data-ui-v2="co-payout"]').count() == 0                                 # 배당성향 자리에 그 줄
                assert page.locator('[data-ui-v2="co-dps"], [data-ui-v2="co-million"], [data-ui-v2="co-div-head"]').count() >= 1   # 배당은 그대로
            elif ctab == "value-more":
                assert page.locator('[data-ui-v2="co-ratios"]').count() == 0 and page.locator('[data-ui-v2="co-map"]').count() == 0
                assert page.locator('[data-ui-v2="co-calc"]').count() == 0
            else:
                assert page.locator('[data-ui-v2="co-earn-more"] [role="table"]').count() == 0
            floor_ok(page, f"공시 단위 {ctab}")
            no_hscroll(page, width)
            no_mascot(page)
            R.collect(page)
            shot(f"unitchk-{ctab}-{width}.png")
    R.check(page, S, f"{UNIT_T} 실적 · 가치 · 배당 · 두 자세히: 한 번씩, 숫자 없는 카드 없음 (출렁임 · 배당은 그대로)", tabs)

    def others():
        for code in ("005930", "AAPL"):
            for ctab in (None, "earn", "value", "div"):
                co_hash(page, f"#stocks/{code}" + (f"/{ctab}" if ctab else ""))
                page.wait_for_function("(t) => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === t", arg=ctab or "summary")
                page.locator('[data-ui-v2="co-summary"], [data-ui-v2="co-earn"], [data-ui-v2="co-value"], [data-ui-v2="co-div"]').first.wait_for(state="visible")
                assert lines_in() == [], (code, ctab, lines_in())
        co_hash(page, "#stocks/005930/value")
        page.locator('[data-ui-v2="co-value"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="co-pbr"]').count() == 1                                      # 다른 회사는 그대로
        R.collect(page)
    R.check(page, S, "다른 회사 (삼성전자 · AAPL): 그 줄 없음 · 숫자 그대로", others)

    def holdings_tile():
        """Jack 2026-11-13 (Q14): 그 회사를 가진 포트폴리오의 '재무 경고 0개 · 확인하지 못했어요' 칸 밑에 같은 줄 한 번 (12px 이상)."""
        page.evaluate("() => { location.hash = '#portfolio'; }")
        at(page, "portfolio")
        tile = page.locator('[data-deck-id="dunit"] [data-ui-v2="pf-rule"][data-rule="warn"]')
        tile.wait_for(state="visible")
        assert tile.get_attribute("data-state") == "unknown", tile.get_attribute("data-state")
        line = tile.locator('[data-ui-v2="unit-chk-tile"]')
        assert line.count() == 1 and line.inner_text().strip() == UNIT_LINE, tile.inner_text()
        assert tile.locator('[data-ui-v2="stmt-cur"]').count() == 0
        assert line.evaluate("(e) => parseFloat(getComputedStyle(e).fontSize)") >= 12
        floor_ok(page, "공시 단위 가진 종목 칸")
        no_hscroll(page, width)
        R.collect(page)
    R.check(page, S, f"{UNIT_T} 을 가진 포트폴리오: '재무 경고 0개' 칸 밑에 그 줄 한 번", holdings_tile)

    def fixed():
        """Jack 2026-11-13 (Q13): 공시 단위를 고쳐 읽은 회사(corp.json unitFix)는 가치 자세히의 영수증 카드 안에만 그 줄 한 번 (12px 이상).
        그 회사의 다른 탭 · 고쳐 읽지 않은 회사 · 미국 종목 · 숫자를 비운 회사에는 없어요."""
        fix = '[data-ui-v2="unit-fix"]'
        more = '[data-ui-v2="co-value-more"][data-t="{}"]'
        assert FIX_LINE == "공시에 단위가 잘못 적혀 있어서 바로잡아 계산했어요.", FIX_LINE
        co_hash(page, f"#stocks/{FIX_T}/value-more")
        page.locator(more.format(FIX_T)).wait_for(state="visible")
        line = page.locator(fix)
        assert line.count() == 1 and line.inner_text().strip() == FIX_LINE, line.count()
        assert page.locator('[data-ui-v2="co-ratios"] ' + fix).count() == 1
        assert line.evaluate("(e) => parseFloat(getComputedStyle(e).fontSize)") >= 12
        floor_ok(page, "공시 단위 고침 가치 자세히")
        no_hscroll(page, width)
        no_mascot(page)
        R.collect(page)
        for ctab in (None, "earn", "value", "div"):                                                      # 그 회사의 다른 탭
            co_hash(page, f"#stocks/{FIX_T}" + (f"/{ctab}" if ctab else ""))
            page.wait_for_function("([t, tab]) => { const e = document.querySelector('[data-ui-v2=\"company\"]');"
                                   " return !!e && e.dataset.t === t && e.dataset.tab === tab; }", arg=[FIX_T, ctab or "summary"])
            page.locator('[data-ui-v2="co-summary"], [data-ui-v2="co-earn"], [data-ui-v2="co-value"], [data-ui-v2="co-div"]').first.wait_for(state="visible")
            assert page.locator(fix).count() == 0, ctab
        for code in ("000660", "AAPL", UNIT_T):                                                          # 다른 회사의 가치 자세히
            co_hash(page, f"#stocks/{code}/value-more")
            page.locator(more.format(code)).wait_for(state="visible")
            assert page.locator(fix).count() == 0, code
        R.collect(page)
    R.check(page, S, f"고쳐 읽은 회사 ({FIX_T}): 가치 자세히의 영수증 카드에만 그 줄 한 번 · 다른 탭과 다른 회사에는 없음", fixed)
    ctx.close()
    srv.shutdown()


# ── 2026-11-08 (Jack): DART 다시 읽기가 끝난 뒤 (src/repair.js 3 · 4, src/v2/fixnote.jsx EpsOwnersNote · StmtCurNote) ──
OWNERS_LINE = C["fix"]["owners"].replace("{date}", f"{int(_FIXD[0][1])}월 {int(_FIXD[0][2])}일")
STMT_T = "241560"              # 두산밥캣: 재무제표를 달러로 공시해요 → 다시 읽은 발행에서 금액이 비고 stmtCur "USD"
STMT_LINE = C["co"]["stmtCur"].replace("{currency}", "USD")


def reread_files(files, when, marker=True):
    """다시 읽은 발행의 모양 (지어낸 값, fix_files live 와 같아요) + 두산밥캣의 원화가 아닌 재무제표 (fetch_data.py v19.1f 처럼 금액 ·
    영수증 · PER · PBR · EPS · BPS 를 비우고 stmtCur "USD"; 배당은 원화 표라 남아요). 모든 파일이 when 한 시간 전에 발행된 것으로.
    marker False: epsBasis 가 없는 발행 (안내가 없어야 해요)."""
    f = fix_files(files, True)
    if not marker:
        f["corp.json"].pop("epsBasis", None)
    co = next(c for c in f["corp.json"]["companies"] if c["t"] == STMT_T)
    co.update(rev=[None, None, None], op=[None, None, None], ni=[None, None, None], eq=None, dcfReady=False, per=None, pbr=None, eps=None, bps=None,
              stmtCur="USD")
    for k in ("evE", "evR", "pcf", "bq", "cash3", "eps3r", "epsNi3", "epsB", "nio3", "epsIn", "bpsIn", "roeIn", "epsFy", "epsRep"):
        co.pop(k, None)
    s = next(x for x in f["data.json"]["stocks"] if x["t"] == STMT_T)
    s.update(per=None, pbr=None, eps=None, bps=None, vz=None)
    # 이자를 내지 않은 회사 (v19.1f flSrc.int0, Jack 2026-11-08): 삼성전자를 그렇게 (지어낸 값) — 확인은 돌았고 경고 없음
    sam = next(c for c in f["corp.json"]["companies"] if c["t"] == FIX_OFF_KR)
    assert sam.get("flRan") == ["cr", "icr", "l3", "imp"] and not sam.get("fl"), (sam.get("flRan"), sam.get("fl"))
    sam["flSrc"] = {"icr": "is", "int0": True}
    pub = (when - dt.timedelta(hours=1)).isoformat(timespec="seconds")
    for name in DATA_FILES:
        f[name]["publishedAt"] = pub
    return f


def reread_open(R, site, width, when, init=None, path="/app.html?dev=1#home"):
    """R.open 과 같지만 페이지의 시계를 when (한국 시간)에 맞춘 뒤 열어요 (Playwright clock: 시간은 그때부터 흘러요). 안내는 오늘 날짜를
    읽으니까요. 처음 안내는 본 것으로 · 다른 사이트 요청은 막고 적어요."""
    srv, base = serve(site)
    screen = pc_device(width) if width >= 1024 else {"viewport": {"width": width, "height": 780}, "device_scale_factor": 2}
    ctx = R.new_context(clock=False, **screen, locale="ko-KR", service_workers="block")     # 이 장면은 자기 날짜(when)로 페이지 시계를 설치해요

    def route(r):
        if r.request.url.startswith(base):
            r.continue_()
        else:
            R.outside.append(r.request.url)
            r.abort()
    ctx.route("**/*", route)
    ctx.add_init_script("try { localStorage.setItem('baepsae2.v1.guideSeen', '1'); } catch (e) {}")
    if init:
        ctx.add_init_script(init)
    page = ctx.new_page()
    page.set_default_timeout(WAIT)
    page.on("pageerror", lambda e: R.errors.append(str(e)))
    page.clock.install(time=when)
    R.saw_clock(page, when)
    page.goto(base + path, wait_until="domcontentloaded")
    return srv, ctx, page, base


def scene_reread_lines(R, files, width, shots=None):
    """다시 읽은 뒤 (Jack 승인 2026-11-08, DeepL 확인):
    - 홈 · 포트폴리오 위쪽(날짜 줄 바로 밑)에 '{date}부터 EPS와 ROE를 지배주주 몫으로 계산해요. 일부 규칙의 결과가 바뀔 수 있어요.' 한 줄:
      corp.json 에 epsBasis "owners" 가 있고 오늘(한국 시간)이 EPS_FIX_DATE 부터 그 + 7일 전까지만. 그날 0시부터 · 표시가 없으면 없어요.
    - 재무제표를 원화가 아닌 통화로 공시한 회사(stmtCur): 회사 페이지 요약(한눈에 칸 위) · 실적 탭 · 가치 탭에 '이 회사는 재무제표를 원화가
      아닌 USD로 공시해서, 실적 숫자는 아직 보여 드리지 않아요.' 한 번씩. 배당 탭 · 다른 회사 · 미국 종목에는 없어요.
    12px 이상 · 가로 스크롤 없음. shots: 스크린샷 폴더 (선택)."""
    S = f"다시 읽은 뒤 {width}"
    y, mo, d = (int(x) for x in _FIXD[0])
    day0 = dt.datetime(y, mo, d, 12, 0, tzinfo=KST)
    when = day0 + dt.timedelta(days=1)                         # 다시 읽은 다음 날 낮 (한 주 안)
    fx = reread_files(files, when)
    fx_corp = fx["corp.json"]
    srv, ctx, page, base = reread_open(R, build_site(fx), width, when, init=fix_store())

    def shot(name, full=False):
        if shots:
            os.makedirs(shots, exist_ok=True)
            page.screenshot(path=os.path.join(shots, name), full_page=full)

    def notice(screen, first_sel):
        loc = page.locator('[data-ui-v2="eps-owners"]')
        loc.first.wait_for(state="visible")
        assert loc.count() == 1, [loc.nth(i).inner_text() for i in range(loc.count())]          # 한 줄
        assert loc.inner_text().strip() == OWNERS_LINE, loc.inner_text()
        dl = page.locator('[data-ui-v2="screen"] [data-ui-v2="date-line"]').first.bounding_box()     # PC: 왼쪽 메뉴에도 날짜 줄이 있어요
        box = loc.bounding_box()
        first = page.locator(first_sel).first.bounding_box()
        assert dl["y"] < box["y"] < first["y"], (screen, dl, box, first)                           # 날짜 줄 밑 · 첫 카드 위
        fs = loc.evaluate("(e) => parseFloat(getComputedStyle(e).fontSize)")
        assert fs >= 12, fs
        floor_ok(page, screen)
        no_hscroll(page, width)
        R.collect(page)

    def home():
        at(page, "home")
        page.locator('[data-ui-v2="home2"]').wait_for(state="visible")
        notice("홈", '[data-ui-v2="home-block"]')
        shot(f"reread-home-{width}.png")
    R.check(page, S, "홈: 날짜 줄 밑에 한 주 동안의 안내 한 줄", home)

    def portfolio():
        page.evaluate("() => { location.hash = '#portfolio'; }")
        at(page, "portfolio")
        page.locator('[data-deck-id="dfix"]').first.wait_for(state="visible")
        notice("포트폴리오", '[data-deck-id="dfix"]')
        shot(f"reread-portfolio-{width}.png")
    R.check(page, S, "포트폴리오: 날짜 줄 밑에 한 주 동안의 안내 한 줄", portfolio)

    def stmt_cur():
        def cur_lines():
            loc = page.locator('[data-ui-v2="stmt-cur"]')
            return [(loc.nth(i).inner_text().strip(), loc.nth(i).get_attribute("data-cur")) for i in range(loc.count())]
        co_hash(page, f"#stocks/{STMT_T}")
        page.locator('[data-ui-v2="co-summary"]').wait_for(state="visible")
        tiles = page.locator('[data-ui-v2="co-tiles"]')
        assert cur_lines() == [(STMT_LINE, "USD")], cur_lines()                                  # 요약: 한 번
        assert tiles.locator('[data-ui-v2="stmt-cur"]').count() == 1, "한눈에 칸 안이 아니에요"
        line_y = page.locator('[data-ui-v2="stmt-cur"]').bounding_box()["y"]
        assert line_y < page.locator('[data-ui-v2="co-tile"]').first.bounding_box()["y"]        # 비어 있는 칸들 위
        # '자료가 없어요' 뿐인 실적 · 가치 칸은 없어요 (숨기기만): 배당 · 출렁임 칸만, 그 위에 이유 한 줄
        topics = tiles.locator('[data-ui-v2="co-tile"]').evaluate_all("(els) => els.map((e) => e.dataset.topic)")
        assert topics == ["div", "risk"], topics
        assert C["co"]["tiles"]["na"] not in tiles.inner_text(), tiles.inner_text()
        assert page.locator('[data-ui-v2="stmt-cur"]').evaluate("(e) => parseFloat(getComputedStyle(e).fontSize)") >= 12
        floor_ok(page, "원화가 아닌 재무제표 요약")
        no_hscroll(page, width)
        no_mascot(page)
        R.collect(page)
        if shots:
            tiles.scroll_into_view_if_needed()
            page.evaluate("() => window.scrollBy(0, -120)")
            shot(f"reread-stmtcur-summary-{width}.png")
        for ctab, inside in (("earn", '[data-ui-v2="co-earn"]'), ("value", '[data-ui-v2="co-value"]'), ("div", None)):
            co_hash(page, f"#stocks/{STMT_T}/{ctab}")
            page.wait_for_function("(t) => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === t", arg=ctab)
            if inside:
                page.locator(inside).wait_for(state="visible")
                assert cur_lines() == [(STMT_LINE, "USD")], (ctab, cur_lines())                  # 실적 · 가치 탭: 한 번
                assert page.locator(f'{inside} [data-ui-v2="stmt-cur"]').count() == 1, ctab
                co_fy = next(x for x in fx_corp["companies"] if x["t"] == STMT_T)["fy"]
                year = fillp(C["app"]["reportYear"], year=co_fy)
                if ctab == "earn":                                                              # 금액 막대 · 큰 숫자 대신, 통화 줄만
                    assert page.locator('[data-ui-v2="co-earn-big"]').count() == 0 and page.locator('[data-ui-v2="bars"]').count() == 0
                    # v19.6d: any on the page but the 화면 모드 switch (PC's left menu has it, a segmented control too)
                    assert page.locator(SEGMENTED).count() == 0, "매출 · 영업이익 · 순이익 고르기가 있어요"
                    assert page.locator('[data-ui-v2="co-decomp"]').count() == 0 and page.locator('[data-ui-v2="co-earn-more"]').count() == 0
                    assert year not in page.locator('[data-ui-v2="co-earn"]').inner_text()
                    assert page.locator('[data-ui-v2="co-earn"] > *').count() == 1, "실적 탭에 통화 줄 카드 말고 다른 것이 있어요"
                else:                                                                           # PBR · PER 대신, 그 기준 · 날짜 줄 없이
                    assert page.locator('[data-ui-v2="co-pbr"]').count() == 0 and page.locator('[data-ui-v2="co-per"]').count() == 0
                    assert page.locator('[data-ui-v2="co-value-basis"]').count() == 0 and page.locator('[data-ui-v2="co-value-more"]').count() == 0
                    assert page.locator('[data-ui-v2="co-value"] [data-ui-v2="date-line"]').count() == 0
                    assert page.locator('[data-ui-v2="co-risk"]').count() == 1                    # 출렁임은 그대로
                if shots:
                    shot(f"reread-stmtcur-{ctab}-{width}.png")
            else:
                page.locator('[data-ui-v2="co-div"]').first.wait_for(state="visible")
                assert cur_lines() == [], cur_lines()                                           # 배당 탭: 원화 표라 그대로
            floor_ok(page, f"원화가 아닌 재무제표 {ctab}")
            no_hscroll(page, width)
            R.collect(page)
        co_hash(page, "#stocks/005930/earn")                                                      # 다른 회사는 그대로 (숨김은 stmtCur 로만)
        page.locator('[data-ui-v2="co-earn"]').wait_for(state="visible")
        assert page.locator(SEGMENTED).count() == 1 and page.locator('[data-ui-v2="co-earn-more"]').count() == 1
        co_hash(page, "#stocks/005930/value")
        page.locator('[data-ui-v2="co-value"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="co-value-basis"]').count() == 1 and page.locator('[data-ui-v2="co-value"] [data-ui-v2="date-line"]').count() >= 1
        for code in ("005930", "AAPL"):                                                          # stmtCur 없는 회사 · 미국 종목: 없어요
            for ctab in (None, "earn", "value"):
                co_hash(page, f"#stocks/{code}" + (f"/{ctab}" if ctab else ""))
                page.wait_for_function("(t) => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === t", arg=ctab or "summary")
                page.locator('[data-ui-v2="co-summary"], [data-ui-v2="co-earn"], [data-ui-v2="co-value"]').first.wait_for(state="visible")
                assert cur_lines() == [], (code, ctab, cur_lines())
        R.collect(page)
    R.check(page, S, f"{STMT_T} 원화가 아닌 재무제표: 요약 · 실적 · 가치에 한 번씩 (배당 · 삼성전자 · AAPL 에는 없음) · '자료가 없어요' 칸 · "
            "고르기 · 보이지 않는 숫자의 기준 줄 · 자세히 링크 없음", stmt_cur)

    def no_interest():
        """이자를 내지 않은 회사(flSrc.int0): '재무 경고 신호는 없어요'와 칩 셋, '이자보상배율 1배 이상' 칩은 없어요. 가진 종목 규칙 칸 ·
        새 홈의 '재무 경고 0개'는 ✓ 그대로 (회사 페이지와 같은 말)."""
        co_hash(page, f"#stocks/{FIX_OFF_KR}")
        card = page.locator('[data-ui-v2="co-warn"][data-n="0"]')
        card.wait_for(state="visible")
        chips = card.locator('[data-ui-v2="co-warn-chip"]').evaluate_all("(els) => els.map((e) => e.dataset.check)")
        assert chips == ["l3", "cr", "imp"], chips
        assert "이자보상배율" not in page.locator('[data-ui-v2="co-summary"]').inner_text()
        floor_ok(page, "이자를 내지 않은 회사의 재무 경고")
        R.collect(page)
        page.evaluate("() => { location.hash = '#home'; }")
        at(page, "home")
        tile = page.locator('[data-ui-v2="home-rules"][data-deck-id="dfix"] [data-ui-v2="home-rule"][data-rule="warn"]')
        tile.wait_for(state="visible")
        assert tile.get_attribute("data-state") == "ok", tile.get_attribute("data-state")
        R.collect(page)
    R.check(page, S, f"{FIX_OFF_KR} 이자를 내지 않은 회사(flSrc.int0): 칩 셋, 이자보상배율 칩 없음 · 새 홈 '재무 경고 0개' ✓ 그대로", no_interest)
    ctx.close()
    srv.shutdown()

    # 이레째 0시 (한국 시간)부터 · 표시가 없는 발행에서는 없어요
    for label, at_time, marker in (("이레가 지난 뒤(그날 0시)", dt.datetime(y, mo, d, 0, 0, tzinfo=KST) + dt.timedelta(days=7), True),
                                   ("표시(epsBasis) 없는 발행", when, False)):
        srv, ctx, page, base = reread_open(R, build_site(reread_files(files, at_time, marker)), width, at_time, init=fix_store())

        def gone():
            at(page, "home")
            page.locator('[data-ui-v2="home-block"]').first.wait_for(state="visible")
            assert page.locator('[data-ui-v2="screen"] [data-ui-v2="date-line"]').count() >= 1
            assert page.locator('[data-ui-v2="eps-owners"]').count() == 0, page.locator('[data-ui-v2="eps-owners"]').inner_text()
            page.evaluate("() => { location.hash = '#portfolio'; }")
            at(page, "portfolio")
            page.locator('[data-deck-id="dfix"]').first.wait_for(state="visible")
            assert page.locator('[data-ui-v2="eps-owners"]').count() == 0
            R.collect(page)
        R.check(page, S, f"{label}: 홈 · 포트폴리오에 안내 없음", gone)
        ctx.close()
        srv.shutdown()

    if width < 1024:                                           # 첫 방문 홈 (뱁이가 있는 화면): 안내의 날짜는 숫자가 아니에요 (v19.0b 규칙)
        srv, ctx, page, base = reread_open(R, build_site(reread_files(files, when)), width, when)

        def first_visit():
            at(page, "home")
            page.locator('[data-ui-v2="home-hero"]').wait_for(state="visible")
            loc = page.locator('[data-ui-v2="eps-owners"]')
            assert loc.count() == 1 and loc.inner_text().strip() == OWNERS_LINE, loc.count()
            visual_ok(page)
            no_hscroll(page, width)
            R.collect(page)
        R.check(page, S, "첫 방문 홈: 안내 한 줄 · 뱁이 화면 규칙 그대로", first_visit)
        ctx.close()
        srv.shutdown()


# ── Jack, 2026-11-12: 재무제표 통화가 달러가 아닌 미국 회사 (data.json fcur · src/v2/fcur.js · fixnote.jsx FcurNote) ──
FCUR_T, FCUR_CODE = "TSM", "TWD"           # 시험 데이터의 TSMC 를 대만 달러 재무제표로 (파이프라인이 PER · PBR · 배당수익률 · 가치 점수를 비운 모양)
FCUR_NONAME = "MYR"                        # 문구 파일에 이름이 없는 통화 (말레이시아 링깃): 줄 없이 빈 칸만, 날 코드도 없이
PBR0_T = "BRK-B"                           # PBR 이 0.00 으로 반올림돼 비운 종목 (data.json pbrZero, Jack 2026-11-13)
FCUR_PENDING = re.compile(r'^(\s+)([A-Z]{3}): null,(\s+// 제안 \(Jack 승인 대기\) "([^"]+)")$', re.M)
_FCUR = {}


def fcur_files(files, code=FCUR_CODE):
    f = clone(files)
    s = next(x for x in f["data.json"]["stocks"] if x["t"] == FCUR_T)
    assert s["cls"] == "us" and s.get("pbr") and s.get("per"), s                     # 시험 데이터: PBR · PER 이 있던 회사
    s["fcur"] = code
    for k in ("per", "pbr", "dy", "vz"):
        s.pop(k, None)
    b = next(x for x in f["data.json"]["stocks"] if x["t"] == PBR0_T)        # 시험 데이터의 BRK-B: PBR 0.0 · 가치 100점 (그 버그 그대로)
    assert b.get("pbr") == 0.0 and b.get("per"), b
    b["pbrZero"] = True                                                      # 파이프라인이 0.00 으로 반올림되는 PBR 을 비운 모양
    for k in ("pbr", "vz"):
        b.pop(k, None)
    return f


def fcur_proposals():
    """src/copy/v2.js co.curName 의 승인 대기 제안 {코드: 이름} (주석의 따옴표 안). 승인되어 값이 들어간 코드는 없어요."""
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as fh:
        block = fh.read().split("    curName: {", 1)[1].split("\n    },", 1)[0]
    return {m.group(2): m.group(4) for m in FCUR_PENDING.finditer(block)}


def fcur_named_app():
    """app.html 을 co.curName 의 승인 대기 이름을 모두 넣고(제안 그대로) 임시 폴더에 빌드해요 (커밋하지 않아요, 폴더는 바로 지워요). 이름이
    승인되기 전에도 이유 줄이 들어갈 자리를 화면에서 시험하려고요. 이미 승인된 이름은 그대로 두어요."""
    if "html" not in _FCUR:
        tmp = tmpdirs.make("baepsae-fcur-")
        try:
            shutil.copytree(os.path.join(ROOT, "src"), os.path.join(tmp, "src"))
            os.makedirs(os.path.join(tmp, "tools"))
            for f in ("template.html", "build-app.sh", "package.json", "package-lock.json", os.path.join("tools", "build_tag.py")):
                shutil.copy(os.path.join(ROOT, f), os.path.join(tmp, f))
            os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
            p = os.path.join(tmp, "src", "copy", "v2.js")
            with open(p, encoding="utf-8") as fh:
                src = fh.read()
            head, rest = src.split("    curName: {", 1)
            block, tail = rest.split("\n    },", 1)
            block, n = FCUR_PENDING.subn(lambda m: f'{m.group(1)}{m.group(2)}: {json.dumps(m.group(4), ensure_ascii=False)},{m.group(3)}', block)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(head + "    curName: {" + block + "\n    }," + tail)
            out = os.path.join(tmp, "out")
            r = subprocess.run(["bash", "build-app.sh", out], cwd=tmp, capture_output=True, text=True, encoding="utf-8")
            assert r.returncode == 0, r.stdout + r.stderr
            with open(os.path.join(out, "app.html"), encoding="utf-8") as fh:
                html = fh.read()
            if n:
                with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as fh:
                    assert html != fh.read(), "이름을 넣어 빌드했는데 app.html 이 같아요"
            _FCUR["html"] = html
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _FCUR["html"]


def scene_us_fcur(R, files, width, named):
    """재무제표 통화가 달러가 아닌 미국 회사 (Jack, 2026-11-12: '주가는 달러, 재무제표는 {통화} 기준이라 이 숫자는 계산하지 않았어요.').
    시험 데이터의 TSM 을 fcur "TWD" 로, PER · PBR · 배당수익률 · 가치 점수를 비운 모양(파이프라인과 같아요)으로 바꿔요.
    #114 리뷰 뒤 (데이터로 정해요 — 이름이 있든 없든 같은 화면, 줄만 이름이 있을 때):
      요약 — 가치 · 배당 칸은 '–' 와 'PBR –' · '배당수익률 –' (그림 · 날짜 · 문장 없음), 실적 · 출렁임 다음 줄에 와요 · 내 기준과 맞는 정도의
      가치 · 배당 줄은 '–' · 가치 탭 — PBR · PER 칸은 '–', 날짜 줄 · 비교 · 자세히 링크 없음, 출렁임 카드는 그대로 · 가치 자세히(주소로) —
      PBR · PER 줄은 '–', 날짜 줄 없음 · 배당 탭 — 배당수익률 '–', '자료가 없어요' · 100만원어치 · 야후 출처 줄 없음 · 실적 탭 그대로.
    named (통화 이름이 있는 빌드: 승인 대기 제안을 넣은 임시 빌드, 이름이 승인되면 커밋한 빌드와 같아요): 줄이 그 '–' 바로 밑에 한 번씩 —
      한눈에 칸 밑 · 내 기준 줄 밑 · 시트 · 가치 탭의 PBR · PER 밑 · 자세히의 배수 목록 안 · 배당수익률 밑 ('대만 달러').
    not named (커밋한 빌드, 문구 파일에 이름이 없는 통화 MYR — 이름이 승인되기 전의 TWD 도 같은 길): 같은 '–' 화면, 줄도 'MYR' 글자도 없고
      console 에 코드. AAPL · 삼성전자에는 줄도 '–' 칸도 없어요. 모두 12px 이상 · 가로 스크롤 없음 · 뱁이 없음."""
    S = f"미국 재무제표 통화 {width}" + (" · 이름 있는 빌드" if named else " · 이름 없는 통화")
    code = FCUR_CODE if named else FCUR_NONAME
    assert FCUR_NONAME not in (CO["curName"] or {}) and FCUR_NONAME not in fcur_proposals(), "이름 없는 통화로 고른 코드에 이름이 생겼어요"
    cur_name = (CO["curName"] or {}).get(FCUR_CODE) or fcur_proposals().get(FCUR_CODE) if named else None
    want = fillp(CO["fcur"], currency=cur_name) if cur_name else None
    assert not named or want, "이름 있는 빌드인데 대만 달러 이름이 없어요"
    n_line = 1 if named else 0
    yld = C["pick"]["receipt"]["yield"]
    wide = width >= 1024
    site = build_site(fcur_files(files, code), app=fcur_named_app() if named else None)
    srv, ctx, page, base = R.open(site, width, path="/app.html?dev=1#home", device=pc_device(width) if wide else None)
    logs = []
    page.on("console", lambda m: logs.append(m.text))
    wait_ready(page)
    lines = lambda sel="": page.locator(f'{sel} [data-ui-v2="fcur"]'.strip())   # noqa: E731

    def common(where):
        assert code not in page.locator("body").inner_text(), f"{where}: 통화 코드가 그대로 보여요"
        if named:
            for i in range(lines().count()):
                assert lines().nth(i).inner_text().strip() == want and lines().nth(i).get_attribute("data-cur") == code
                assert lines().nth(i).evaluate("(e) => parseFloat(getComputedStyle(e).fontSize)") >= 12
        floor_ok(page, where)
        no_hscroll(page, width)
        no_mascot(page)
        R.collect(page)

    def below(a, b):
        """b 의 위쪽이 a 의 아래쪽 바로 밑 (40px 안)."""
        ba, bb = a.bounding_box(), b.bounding_box()
        return ba["y"] + ba["height"] - 1 <= bb["y"] <= ba["y"] + ba["height"] + 40

    def summary():
        co_hash(page, f"#stocks/{FCUR_T}")
        page.locator('[data-ui-v2="co-summary"]').wait_for(state="visible")
        tiles = page.locator('[data-ui-v2="co-tiles"]')
        tiles.wait_for(state="visible")
        tl = tiles.locator('[data-ui-v2="co-tile"]')
        topics = tl.evaluate_all("(els) => els.map((e) => [e.dataset.topic, e.dataset.rule])")
        assert topics == [["earn", "up"], ["risk", topics[1][1]], ["value", "fcur"], ["div", "fcur"]], topics   # 가치 · 배당이 아래 줄
        for topic, num_text in (("value", "PBR –"), ("div", f"{yld} –")):
            t_ = tiles.locator(f'[data-ui-v2="co-tile"][data-topic="{topic}"]')
            assert t_.locator('[data-ui-v2="tile-phrase"]').inner_text().strip() == "–", t_.inner_text()
            assert t_.locator('[data-ui-v2="tile-number"]').inner_text().strip() == num_text, t_.inner_text()
            assert t_.locator('[data-ui-v2="tile-basis"]').count() == 0 and t_.locator("svg[data-art], [data-ui-v2='tile-art']").count() == 0
            assert CO["tiles"]["na"] not in t_.inner_text()
        fit = page.locator('[data-ui-v2="co-fit"]')
        fit.wait_for(state="visible")
        rows = {r.get_attribute("data-card"): r for r in fit.locator('[data-ui-v2="rank-row"]').all()}
        assert set(rows) >= {"value", "div"}, list(rows)                         # 고른 기준이 없으면 가치 · 배당 카드 먼저
        for c in ("value", "div"):
            assert rows[c].get_attribute("data-side") == "blank" and rows[c].inner_text().strip().endswith("–"), rows[c].inner_text()
        assert tiles.locator('[data-ui-v2="fcur"]').count() == n_line and fit.locator('[data-ui-v2="fcur"]').count() == n_line
        assert lines().count() == 2 * n_line
        if named:                                                               # 가치 · 배당 칸 바로 밑 · 내 기준 줄 밑
            assert below(tiles.locator('[data-ui-v2="co-tile"][data-topic="value"]'), tiles.locator('[data-ui-v2="fcur"]'))
            assert lines().nth(1).bounding_box()["y"] > rows["div"].bounding_box()["y"]
        else:
            assert any(f"statement currency {code}" in x and "co.curName" in x for x in logs), logs[-5:]
        common("요약")
        if R.shots:
            tiles.scroll_into_view_if_needed()
            page.screenshot(path=os.path.join(R.shots, f"fcur-summary-{width}-{'named' if named else 'pending'}.png"))
        fit.get_by_role("button", name=CO["fit"]["all"]).click()
        sheet = page.locator('[data-ui-v2="co-fit-sheet"]')
        sheet.wait_for(state="visible")
        assert sheet.locator('[data-ui-v2="fcur"]').count() == n_line
        srow = {r.get_attribute("data-card"): r.get_attribute("data-side") for r in sheet.locator('[data-ui-v2="rank-row"]').all()}
        assert srow.get("value") == "blank" and srow.get("div") == "blank" and srow.get("growth") in ("top", "bottom"), srow
        common("기준 카드 시트")
        page.keyboard.press("Escape")
        sheet.wait_for(state="detached")
    R.check(page, S, f"{FCUR_T} 요약: 가치 · 배당 칸 '–' (PBR – · 배당수익률 –) 아래 줄 · 가치 · 배당 순위 '–'"
            + (" · 줄은 칸 밑 · 내 기준 밑 · 시트에 한 번씩" if named else f" · {code}: 줄 없음 · console 에 코드"), summary)

    def tabs():
        co_hash(page, f"#stocks/{FCUR_T}/value")
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === 'value'")
        val = page.locator('[data-ui-v2="co-value"]')
        val.wait_for(state="visible")
        for sel in ("co-pbr", "co-per"):
            loc = val.locator(f'[data-ui-v2="{sel}"]')
            assert loc.count() == 1 and loc.get_attribute("data-blank") == "fcur" and loc.inner_text().split("\n")[-1].strip() == "–", loc.inner_text()
        for sel in ("co-compare", "co-strip", "co-value-more"):
            assert page.locator(f'[data-ui-v2="{sel}"]').count() == 0, sel
        assert val.locator('[data-ui-v2="date-line"]').count() == 0                # 보이지 않는 숫자의 날짜 없음 (빈 카드도 아니에요)
        assert page.locator('[data-ui-v2="co-risk"]').count() == 1                 # 출렁임은 그대로 (가격으로 만든 값)
        assert lines('[data-ui-v2="co-value"]').count() == n_line and lines().count() == n_line
        if named:
            assert below(val.locator('[data-ui-v2="co-per"]'), lines())
        common("가치 탭")
        co_hash(page, f"#stocks/{FCUR_T}/value-more")
        more = page.locator('[data-ui-v2="co-value-more"]')
        more.wait_for(state="visible")
        ratios = more.locator('[data-ui-v2="co-ratios"]')
        got = ratios.locator('[data-ui-v2="co-ratio"]').evaluate_all("(els) => els.map((e) => e.innerText.split('\\n').map((x) => x.trim()).filter(Boolean))")
        assert [g[0] for g in got] == ["PBR", "PER"] and all("–" in g for g in got), got
        assert ratios.locator('[data-ui-v2="date-line"]').count() == 0 and lines('[data-ui-v2="co-ratios"]').count() == n_line
        common("가치 자세히")
        co_hash(page, f"#stocks/{FCUR_T}/div")
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === 'div'")
        div = page.locator('[data-ui-v2="co-div"]')
        div.wait_for(state="visible")
        y = div.locator('[data-ui-v2="co-yield"]')
        assert y.count() == 1 and y.get_attribute("data-blank") == "fcur" and y.inner_text().split("\n")[-1].strip() == "–", y.inner_text()
        assert page.locator('[data-ui-v2="co-million"]').count() == 0 and CO["tiles"]["na"] not in div.inner_text(), div.inner_text()
        assert lines('[data-ui-v2="co-div-stats"]').count() == n_line and lines().count() == n_line
        if named:
            assert below(y, lines())
        common("배당 탭")
        co_hash(page, f"#stocks/{FCUR_T}/earn")
        page.wait_for_function("() => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === 'earn'")
        page.locator('[data-ui-v2="co-earn"]').wait_for(state="visible")
        assert lines().count() == 0                                               # 실적(ROE · 영업이익률 · 매출)은 그대로
        common("실적 탭")
        for code_ in ("AAPL", "005930"):                                          # fcur 없는 회사: 줄 없음, '–' 칸 없음, PBR 그대로
            for ctab in (None, "value", "div"):
                co_hash(page, f"#stocks/{code_}" + (f"/{ctab}" if ctab else ""))
                page.wait_for_function("(t) => document.querySelector('[data-ui-v2=\"company\"]').dataset.tab === t", arg=ctab or "summary")
                page.locator('[data-ui-v2="co-summary"], [data-ui-v2="co-value"], [data-ui-v2="co-div"]').first.wait_for(state="visible")
                assert lines().count() == 0 and page.locator('[data-blank="fcur"], [data-rule="fcur"]').count() == 0, (code_, ctab)
            co_hash(page, f"#stocks/{code_}/value")
            page.locator('[data-ui-v2="co-value"]').wait_for(state="visible")
            assert page.locator('[data-ui-v2="co-pbr"]').count() == 1 and "–" not in page.locator('[data-ui-v2="co-pbr"]').inner_text(), code_
        R.collect(page)
        if R.shots:
            for ctab in ("value", "div"):
                co_hash(page, f"#stocks/{FCUR_T}/{ctab}")
                page.wait_for_timeout(200)
                page.screenshot(path=os.path.join(R.shots, f"fcur-{ctab}-{width}-{'named' if named else 'pending'}.png"))
    R.check(page, S, f"{FCUR_T} 가치 탭 · 가치 자세히 · 배당 탭: PBR · PER · 배당수익률 '–'" + (" 바로 밑에 줄 한 번씩" if named else ", 줄 없음")
            + " · 날짜 줄 · 자세히 링크 · '자료가 없어요' 없음 · 실적 탭 · AAPL · 삼성전자 그대로", tabs)

    def pbr_zero():
        """Jack, 2026-11-13: PBR 이 0.00 으로 반올림된 BRK-B — 가치 칸 · 가치 탭 · 가치 자세히 · 내 기준의 가치 줄이 'PBR –' 이고 그 바로 밑에
        '자료상 PBR이 0에 가깝게 나와서 확인하는 동안 비워 두었어요.' 한 번씩. PER · 배당 · 날짜 줄은 그대로, 통화 줄은 없어요."""
        zl = lambda sel="": page.locator(f'{sel} [data-ui-v2="pbr-zero"]'.strip())   # noqa: E731
        co_hash(page, f"#stocks/{PBR0_T}")
        tiles = page.locator('[data-ui-v2="co-tiles"]')
        tiles.wait_for(state="visible")
        order = tiles.locator('[data-ui-v2="co-tile"]').evaluate_all("(els) => els.map((e) => [e.dataset.topic, e.dataset.rule])")
        assert [o[0] for o in order] == ["earn", "div", "risk", "value"] and order[3][1] == "pbr0", order
        vt = tiles.locator('[data-ui-v2="co-tile"][data-topic="value"]')
        assert vt.locator('[data-ui-v2="tile-number"]').inner_text().strip() == "PBR –"
        assert tiles.locator('[data-ui-v2="pbr-zero"]').count() == 1 and below(vt, tiles.locator('[data-ui-v2="pbr-zero"]'))
        fit = page.locator('[data-ui-v2="co-fit"]')
        fit.wait_for(state="visible")
        assert fit.locator('[data-ui-v2="rank-row"][data-card="value"]').get_attribute("data-side") == "blank"
        assert fit.locator('[data-ui-v2="pbr-zero"]').count() == 1 and lines().count() == 0
        for i in range(zl().count()):
            assert zl().nth(i).inner_text().strip() == CO["pbrZero"]
        common("PBR 0 요약")
        co_hash(page, f"#stocks/{PBR0_T}/value")
        val = page.locator('[data-ui-v2="co-value"]')
        val.wait_for(state="visible")
        pb, pe = val.locator('[data-ui-v2="co-pbr"]'), val.locator('[data-ui-v2="co-per"]')
        assert pb.get_attribute("data-blank") == "pbr0" and pb.inner_text().split("\n")[-1].strip() == "–"
        assert pe.count() == 1 and pe.get_attribute("data-blank") is None and "–" not in pe.inner_text()   # PER 은 그대로
        assert zl('[data-ui-v2="co-value"]').count() == 1 and zl().inner_text().strip() == CO["pbrZero"]
        assert val.locator('[data-ui-v2="date-line"]').count() >= 1                # PER 의 날짜는 그대로
        common("PBR 0 가치 탭")
        co_hash(page, f"#stocks/{PBR0_T}/value-more")
        ratios = page.locator('[data-ui-v2="co-ratios"]')
        ratios.wait_for(state="visible")
        got = ratios.locator('[data-ui-v2="co-ratio"]').evaluate_all("(els) => els.map((e) => e.innerText.split('\\n').map((x) => x.trim()).filter(Boolean))")
        assert got[0][0] == "PBR" and "–" in got[0] and got[1][0] == "PER" and "–" not in got[1], got
        assert zl('[data-ui-v2="co-ratios"]').count() == 1
        common("PBR 0 가치 자세히")
        if R.shots:
            co_hash(page, f"#stocks/{PBR0_T}")
            page.locator('[data-ui-v2="co-tiles"]').scroll_into_view_if_needed()
            page.screenshot(path=os.path.join(R.shots, f"pbr0-summary-{width}.png"))
    if named:
        R.check(page, S, f"{PBR0_T} PBR 0.00 (pbrZero): 가치 칸 · 내 기준 · 가치 탭 · 자세히에 'PBR –' 와 그 밑 줄 한 번씩 · PER · 날짜 그대로", pbr_zero)
    ctx.close()
    srv.shutdown()


# ── v19.6a: 팔았어요 · 배당 받았어요 · 내 수익 · 기록 내려받기 (docs/tasks/v19.6-records-alerts-dark.md Part A, boards Records2 · Returns2) ──
def v196a_files(files, fx_hist=True, splits=True):
    data = clone(files)
    d = data["data.json"]
    if splits:
        d["splits"] = [["005380", "2026-10-15", 2], ["XXXX", "bad", 0]]                      # 현대차 2:1 (시험용) · 못 읽는 항목 하나
    if fx_hist:
        data["macro.json"]["fxHist"] = {"asOf": d["fxDate"], "final": True, "rows": [["2016-01-04", 1172.5], ["2026-10-01", 1300.0], ["2026-10-20", 1350.0], [d["fxDate"], d["fx"]]]}
    return data


def v196a_store(pxd):
    band = lambda t: [{"id": "band", "kind": "band", "check": "checked", "target": t, "bands": [0.75 * t, 1.25 * t, 1.4 * t]}]
    built = {"id": "dbuilt", "name": "배당 생활비 포트폴리오", "createdAt": "2026-10-01", "planFx": 1300,
             "holdings": [{"t": "005930", "nk": "삼성전자", "target": 0.4, "plannedQty": 10, "rules": band(0.4)},
                          {"t": "005380", "nk": "현대차", "target": 0.3, "plannedQty": 5, "rules": band(0.3)},
                          {"t": "AAPL", "nk": "Apple Inc.", "cls": "us", "target": 0.3, "plannedQty": 3, "rules": band(0.3)}],
             "purchases": [{"id": "p1aaaaaa", "t": "005930", "date": "2026-10-01", "qty": 10, "price": 200000, "ccy": "KRW"},
                           {"id": "p2aaaaaa", "t": "005380", "date": "2026-10-01", "qty": 5, "price": 250000, "ccy": "KRW"},
                           {"id": "p3aaaaaa", "t": "AAPL", "date": "2026-10-01", "qty": 3, "price": 300.0, "ccy": "USD", "fx": 1300},
                           {"id": "p4aaaaaa", "t": "AAPL", "date": "2026-10-15", "qty": 1, "price": 320.0, "ccy": "USD", "fx": 1350}],
             "divs": [{"id": "v1aaaaaa", "t": "005930", "amount": 3610, "ccy": "KRW", "date": "2026-10-25"}]}
    imported = {"id": "dimp", "name": "가진 종목 포트폴리오", "createdAt": "2026-10-02", "kind": "imported", "settings": {"points": {"value": 3}, "strict": "normal"},
                "holdings": [{"t": "000660", "nk": "SK하이닉스", "cls": "kr"}, {"t": "MSFT", "nk": "Microsoft Corporation", "cls": "us"},
                             {"t": "035420", "nk": "NAVER", "cls": "kr"}, {"t": "005930", "nk": "삼성전자", "cls": "kr"}],
                "purchases": [], "imported": [{"t": "000660", "nk": "SK하이닉스", "ccy": "KRW", "qty": 3, "avg": 1200000},
                                                {"t": "MSFT", "nk": "Microsoft Corporation", "ccy": "USD", "qty": 2, "avg": 480},
                                                {"t": "035420", "nk": "NAVER", "ccy": "KRW", "amountWon": 1000000, "close": 172300, "date": pxd},
                                                {"t": "005930", "nk": "삼성전자", "ccy": "KRW", "qty": 1, "avg": 210000}]}
    return {"v": 2, "decks": [built, imported], "guideSeen": pxd}


def scene_v196a_split_price(R, files, width=390):
    """v19.6a round 3: a split between the record's date and today puts today's close on another share basis, so an empty
    price has no default there. 팔았어요 AMD (a stored 1:2 on 10-05) dated 10-02 and 샀어요 NVDA (data.json's 10:1 on 10-10)
    dated 10-01: the '가격을 비워 두면 … 종가로 기록돼요' line and the close as the placeholder are gone, an empty price is refused
    with the existing line (price field marked, nothing saved), a typed price saves. On today's date both are back. 매수 계획's
    샀어요 (every US stock split on 10-20): dated 10-15, the sheet's line is gone and the US rows need a price."""
    S = f"v19.6a split price {width}"
    data = v196a_files(files)
    d = data["data.json"]
    d["splits"] = d["splits"] + [["NVDA", "2026-10-10", 10]]
    by = {x["t"]: x for x in d["stocks"]}
    pxd = d["pxDate"]
    band = lambda t: [{"id": "band", "kind": "band", "check": "checked", "target": t, "bands": [0.75 * t, 1.25 * t, 1.4 * t]}]
    deck = {"id": "dsp", "name": "배당 생활비 포트폴리오", "createdAt": "2026-08-01", "planFx": 1300,
            "holdings": [{"t": "AMD", "nk": by["AMD"]["nk"], "cls": "us", "target": 0.5, "rules": band(0.5)},
                         {"t": "NVDA", "nk": by["NVDA"]["nk"], "cls": "us", "target": 0.5, "rules": band(0.5)}],
            "purchases": [{"id": "p1aaaaaa", "t": "AMD", "qty": 2, "price": 160.0, "date": "2026-09-01", "ccy": "USD", "fx": 1300},
                          {"id": "p2aaaaaa", "t": "NVDA", "qty": 1, "price": 1500.0, "date": "2026-09-01", "ccy": "USD", "fx": 1300}],
            "splits": [{"t": "AMD", "date": "2026-10-05", "r": 0.5}]}
    seed = ("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            f" localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps({'v': 2, 'decks': [deck], 'guideSeen': pxd}, ensure_ascii=False))}); }})();")
    srv, ctx, page, base = R.open(build_site(data), width, init=seed, path="/app.html?dev=1#portfolio")
    stored = lambda: page.evaluate(STORED_JS)
    R_ = C["rec"]
    form = lambda: page.locator('[data-ui-v2="rec-form"]')
    price_in = lambda: form().locator("input").nth(1)

    def open_form(t, label):
        at(page, "portfolio")
        page.locator(f'[data-holding="{t}"] [data-ui-v2="row-actions"] button').first.click()
        page.locator('[data-ui-v2="rec-sheet"]').wait_for(state="visible")
        page.locator('[data-ui-v2="rec-actions"] button', has_text=label).click()
        form().wait_for(state="visible")

    def check_page(where, name):
        floor_ok(page, where)
        no_hscroll(page, width)
        R.collect(page)
        if R.shots:
            os.makedirs(R.shots, exist_ok=True)
            page.screenshot(path=os.path.join(R.shots, f"v196a-{name}-{width}.png"))

    def sale_amd():
        open_form("AMD", R_["sell"])
        assert form().locator('[data-ui-v2="rec-close-line"]').count() == 1                     # 오늘 날짜: 종가 줄 · 자리 글자
        assert price_in().get_attribute("placeholder") == f"{by['AMD']['price']:,.2f}"
        form().locator('input[type="date"]').fill("2026-10-02")                                  # 1:2 (10-05) 전
        form().locator('[data-ui-v2="rec-close-line"]').wait_for(state="detached")
        assert not price_in().get_attribute("placeholder")
        form().locator("input").first.fill("2")
        form().locator("button", has_text=C["plan"]["save"]).click()
        form().locator('[data-ui-v2="bad-input"]').wait_for(state="visible")
        assert form().locator('[data-ui-v2="bad-input"]').inner_text() == C["plan"]["badInput"] and price_in().get_attribute("aria-invalid") == "true"
        assert not stored()["decks"][0].get("sales")                                              # 저장 안 함
        check_page("팔았어요 · 분할 전 날짜", "sell-split-price")
        price_in().fill("250")
        form().locator("button", has_text=C["plan"]["save"]).click()
        page.wait_for_function("() => (JSON.parse(localStorage.getItem('baepsae2.v1')).decks[0].sales || []).length === 1")
        sale = stored()["decks"][0]["sales"][0]
        assert sale["price"] == 250 and sale["qty"] == 2 and sale["date"] == "2026-10-02"
        page.locator('[data-ui-v2="rec-full"] button', has_text=R_["keep"]).click()             # 다 팔았어요: 남겨 두기
        page.locator('[data-ui="bottom-sheet"]').get_by_role("button", name=C["app"]["close"]).first.click()
        page.locator('[data-ui="bottom-sheet"]').wait_for(state="detached")
    R.check(page, S, "팔았어요 AMD: 분할 전 날짜면 '가격을 비워 두면 …' 줄 · 자리 글자 없음 · 빈 가격은 거절(가격 칸) · 적으면 저장", sale_amd)

    def buy_nvda():
        open_form("NVDA", C["plan"]["bought"])
        assert form().locator('[data-ui-v2="rec-close-line"]').count() == 1
        form().locator('input[type="date"]').fill("2026-10-01")                                  # data.json 10:1 (10-10) 전
        form().locator('[data-ui-v2="rec-close-line"]').wait_for(state="detached")
        assert not price_in().get_attribute("placeholder")
        form().locator("input").first.fill("1")
        form().locator("button", has_text=C["plan"]["save"]).click()
        form().locator('[data-ui-v2="bad-input"]').wait_for(state="visible")
        assert price_in().get_attribute("aria-invalid") == "true" and len(stored()["decks"][0]["purchases"]) == 2
        price_in().fill("180")
        form().locator("button", has_text=C["plan"]["save"]).click()
        page.wait_for_function("() => JSON.parse(localStorage.getItem('baepsae2.v1')).decks[0].purchases.length === 3")
        p = stored()["decks"][0]["purchases"][-1]
        assert p["t"] == "NVDA" and p["price"] == 180 and p["date"] == "2026-10-01"
    R.check(page, S, "샀어요 NVDA (data.json 분할): 분할 전 날짜면 줄 · 자리 글자 없음 · 빈 가격 거절 · 적으면 저장", buy_nvda)
    ctx.close()
    srv.shutdown()

    # 매수 계획의 샀어요: 계획의 미국 종목이 모두 10-20 에 나뉘었다고 하면, 10-15 로 적을 때 미국 줄은 가격을 적어야 해요
    plan = v196a_files(files)
    plan["data.json"]["splits"] = [[x["t"], "2026-10-20", 2] for x in plan["data.json"]["stocks"] if x.get("cls") == "us" and x.get("ccy") == "USD"]
    seed2 = ("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
             f" localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(v196a_store(pxd), ensure_ascii=False))}); }})();")
    srv, ctx, page, base = R.open(build_site(plan), width, init=seed2, path="/app.html?dev=1#portfolio")
    pby = {x["t"]: x for x in plan["data.json"]["stocks"]}

    def plan_sheet():
        at(page, "portfolio")
        rows = to_plan(page)
        us = [t for t, _ in rows if pby.get(t, {}).get("ccy") == "USD"]
        assert us, rows
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        sheet = page.locator('[data-ui-v2="record-form"]')
        assert sheet.locator('[data-ui-v2="plan-close-line"]').count() == 1                     # 오늘: '비워 두면 … 종가로 기록돼요'
        sheet.locator('input[type="date"]').fill("2026-10-15")
        sheet.locator('[data-ui-v2="plan-close-line"]').wait_for(state="detached")
        for t in us:
            assert not sheet.locator(f'[data-record="{t}"] input').nth(1).get_attribute("placeholder"), t
        n = len(stored()["decks"])
        page.get_by_role("button", name=C["plan"]["save"]).click()
        sheet.locator('[data-ui-v2="bad-input"]').wait_for(state="visible")
        assert all(sheet.locator(f'[data-record="{t}"] input').nth(1).get_attribute("aria-invalid") == "true" for t in us)
        assert len(stored()["decks"]) == n                                                        # 저장 안 함
        check_page("매수 계획 · 분할 전 날짜", "plan-split-price")
        for t in us:
            sheet.locator(f'[data-record="{t}"] input').nth(1).fill("100")
        page.get_by_role("button", name=C["plan"]["save"]).click()
        page.locator('[data-ui-v2="record-done"]').wait_for(state="visible")
        new = [x for x in stored()["decks"] if x["id"] not in ("dbuilt", "dimp")][0]
        for t in us:
            p = [x for x in new["purchases"] if x["t"] == t][0]
            assert p["price"] == 100 and p["date"] == "2026-10-15", p
    R.check(page, S, "매수 계획의 샀어요: 분할 전 날짜면 '비워 두면 …' 줄 없음 · 미국 줄은 가격을 적어야 저장", plan_sheet)
    ctx.close()
    srv.shutdown()


def scene_v196a_outs(R, files, width=390):
    """v19.6a round 2 (A3): the app's wiring of data.json splitsInfo.fixed "out" rows (app.jsx · lots.withoutOutSplits).
    dfree: NVDA 4 shares and a stored 2:1 split the data marks out → taken out: 8 → 4, one console line, nothing again on
    reload · dneed: MSFT 2 shares, the same out split, a sale of 3 after it → kept (the sale needs it), a console warning ·
    dswap: AMZN 10 shares, a stored 5:1 split on a wrong date (out) and data.json's corrected date 19 days on, a sale of 40
    after both → the stored split moves to the corrected date: 10 shares (210 before: both applied)."""
    S = f"v19.6a splits {width}"
    data = v196a_files(files)
    d = data["data.json"]
    d["splits"] = d["splits"] + [["AMZN", "2026-09-20", 5]]
    d["splitsInfo"] = {"fixed": [["NVDA", "2026-09-15", None, "test"], ["MSFT", "2026-09-15", None, "test"], ["AMZN", "2026-09-01", None, "test"]]}
    pxd = d["pxDate"]
    band = lambda t: [{"id": "band", "kind": "band", "check": "checked", "target": t, "bands": [0.75 * t, 1.25 * t, 1.4 * t]}]
    usd = lambda i, t, q, px, day: {"id": i, "t": t, "qty": q, "price": px, "date": day, "ccy": "USD", "fx": 1300}
    deck = lambda i, t, nk, buys, sells, split: {"id": i, "name": i, "createdAt": "2026-08-01", "planFx": 1300,
                                                "holdings": [{"t": t, "nk": nk, "cls": "us", "target": 1, "rules": band(1)}],
                                                "purchases": buys, "sales": sells, "splits": [split]}
    store = {"v": 2, "guideSeen": pxd, "decks": [
        deck("dfree", "NVDA", "NVIDIA Corporation", [usd("p1aaaaaa", "NVDA", 4, 150.0, "2026-09-01")], [], {"t": "NVDA", "date": "2026-09-15", "r": 2}),
        deck("dneed", "MSFT", "Microsoft Corporation", [usd("p2aaaaaa", "MSFT", 2, 480.0, "2026-09-01")], [usd("s2aaaaaa", "MSFT", 3, 500.0, "2026-10-01")],
             {"t": "MSFT", "date": "2026-09-15", "r": 2}),
        deck("dswap", "AMZN", "Amazon.com, Inc.", [usd("p3aaaaaa", "AMZN", 10, 900.0, "2026-08-03")], [usd("s3aaaaaa", "AMZN", 40, 200.0, "2026-10-01")],
             {"t": "AMZN", "date": "2026-09-01", "r": 5})]}
    # console.warn / info kept in sessionStorage from the first load on (the effects run before a listener could be attached)
    seed = ("(() => { const keep = (f) => function (...a) { try { const l = JSON.parse(sessionStorage.getItem('logs') || '[]'); l.push(a.join(' '));"
            " sessionStorage.setItem('logs', JSON.stringify(l)); } catch (e) {} return f.apply(this, a); };"
            " console.warn = keep(console.warn); console.info = keep(console.info);"
            " if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            f" localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(store, ensure_ascii=False))}); }})();")
    srv, ctx, page, base = R.open(build_site(data), width, init=seed, path="/app.html?dev=1#portfolio")
    stored = lambda: page.evaluate(STORED_JS)
    logs = lambda: page.evaluate("() => JSON.parse(sessionStorage.getItem('logs') || '[]')")
    by_id = lambda: {x["id"]: x for x in stored()["decks"]}

    def outs():
        at(page, "portfolio")
        page.wait_for_function("() => { const s = JSON.parse(localStorage.getItem('baepsae2.v1')); return s.decks.every((d) => !(d.splits || []).some((x) => x.t !== 'MSFT' && x.date !== '2026-09-20')); }")
        x = by_id()
        assert "splits" not in x["dfree"]                                                       # 빠졌어요
        assert x["dneed"]["splits"] == [{"t": "MSFT", "date": "2026-09-15", "r": 2}]             # 판 기록이 필요해 남아요
        assert x["dswap"]["splits"] == [{"t": "AMZN", "date": "2026-09-20", "r": 5}]             # 바른 날짜로 옮겨요
        page.locator('[data-deck-id="dfree"] [data-holding="NVDA"]').wait_for(state="visible")
        for dk, t, q in (("dfree", "NVDA", "4주"), ("dneed", "MSFT", "1주"), ("dswap", "AMZN", "10주")):
            txt = page.locator(f'[data-deck-id="{dk}"] [data-holding="{t}"]').inner_text()
            assert q in txt, (dk, txt)
        L = logs()
        took = [l for l in L if "stored stock splits taken out" in l or "stored stock splits moved" in l]
        assert any("dfree NVDA 2026-09-15 x2, NVDA shares 8 -> 4" in l for l in took), took
        assert any("dswap AMZN 2026-09-01" in l and "AMZN shares 210 -> 10" in l for l in took), took
        assert any("dneed: the stored split of MSFT on 2026-09-15" in l and "it is kept" in l for l in L), L
        n = len(took)
        page.reload(wait_until="domcontentloaded")
        at(page, "portfolio")
        page.locator('[data-deck-id="dfree"] [data-holding="NVDA"]').wait_for(state="visible")
        page.wait_for_timeout(300)
        took2 = [l for l in logs() if "stored stock splits taken out" in l or "stored stock splits moved" in l]
        assert len(took2) == n, took2                                                          # 다시 열어도 또 빼지 않아요
        assert "splits" not in by_id()["dfree"]
        assert page.locator("[data-deck-id]").count() == 3                                     # 다시 읽어도 세 포트폴리오 모두 (따로 두지 않아요)
        floor_ok(page, "포트폴리오 (분할 고침)")
        R.collect(page)
    R.check(page, S, "out 줄: 필요 없는 저장 분할은 빠지고(8 → 4, console 한 줄, 다시 열어도 한 번) · 판 기록이 필요하면 남고(경고) · 바른 날짜로 옮겨요(210 → 10)", outs)
    ctx.close()
    srv.shutdown()


def scene_v196a(R, files, width):
    """v19.6a (390 · 320 · 1280): every holding row has 기록 → '{name} 기록' sheet with 샀어요 · 팔았어요 · 배당 받았어요 above the
    stock's records · 팔았어요: 가진 수량보다 많이(거절) · 처음 산 날보다 앞선 날짜(거절) · 판 금액 · 산 가격보다 · 이동평균 note ·
    a split stock (data.json splits, 현대차 2:1) reads at the new basis with the split line, and a sale of the new count is
    saved with the split in the store · a full sale asks 포트폴리오에서도 뺄까요? → 남겨 두기 (다 판 종목, 기록 stays) and 빼기
    (records into history; 배당 받았어요 still works from the company page) · a past-dated US sale takes the rate of its date
    (macro.json fxHist) · 지우기 + confirm, refused when a later sale would be bigger than the shares held · 내 수익: rows add up,
    the headline is their sum, 미국 종목 수익 어디서 왔나 (주가 + 환율 = total) · 기록 내려받기 CSV (BOM, header, code cells) ·
    a holding put in by amount sells only all at once, by 판 금액 · without fxHist a past-dated US record is not saved (the
    approved line) · stale data: 내 수익 shows the stale line and no number · no 12px text, no sideways scroll, approved words only."""
    S = f"v19.6a {width}"
    wide = width >= 1024
    data = v196a_files(files)
    pxd = data["data.json"]["pxDate"]
    fx = data["data.json"]["fx"]
    today = now_dt().date().isoformat()
    by = {s["t"]: s for s in data["data.json"]["stocks"]}
    seed = ("(() => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            f" localStorage.setItem('baepsae2.v1', {json.dumps(json.dumps(v196a_store(pxd), ensure_ascii=False))}); }})();")
    srv, ctx, page, base = R.open(build_site(data), width, init=seed, path="/app.html?dev=1#portfolio", device=pc_device(width) if wide else None,
                                  accept_downloads=True)
    stored = lambda: page.evaluate(STORED_JS)
    deck = lambda i: stored()["decks"][i]
    R_ = C["rec"]

    def sheet(sel_row):
        page.locator(sel_row).locator('[data-ui-v2="row-actions"] button').first.click()
        page.locator('[data-ui-v2="rec-sheet"]').wait_for(state="visible")

    def act(name):
        page.locator('[data-ui-v2="rec-actions"] button', has_text=name).click()
        page.locator('[data-ui-v2="rec-form"]').wait_for(state="visible")

    def fill_form(*vals):
        inputs = page.locator('[data-ui-v2="rec-form"] input')
        for i, v in enumerate(vals):
            if v is not None:
                inputs.nth(i).fill(v)

    def save():
        page.locator('[data-ui-v2="rec-form"] button', has_text=C["plan"]["save"]).click()

    def close_sheet():
        page.keyboard.press("Escape")
        page.locator('[data-ui="bottom-sheet"]').wait_for(state="detached")

    def check_page(where, name=None):
        floor_ok(page, where)
        no_hscroll(page, width)
        R.collect(page)
        if name and R.shots:                                                       # --shots: every new screen and state
            os.makedirs(R.shots, exist_ok=True)
            page.screenshot(path=os.path.join(R.shots, f"v196a-{name}-{width}.png"), full_page=True)

    def rows_and_split():
        at(page, "portfolio")
        page.locator('[data-deck-id="dbuilt"] [data-holding="005930"]').wait_for(state="visible")
        check_page("포트폴리오", "portfolio")
        btns = page.locator('[data-ui-v2="row-actions"] button', has_text=R_["button"])
        assert btns.count() == 3 + 4, btns.count()                                  # 만든 포트폴리오 3종목 + 가진 종목 4종목
        assert page.get_by_role("button", name=fillp(R_["title"], name="삼성전자")).count() == 2   # 이름: '{name} 기록'
        hy = page.locator('[data-holding="005380"]').inner_text()
        assert "10주" in hy and "125,000원" in hy, hy                                  # 2:1 분할: 5주 × 2, 250,000원 ÷ 2
        sheet('[data-holding="005380"]')
        sp = page.locator('[data-ui-v2="rec-split"]')
        assert sp.count() == 1 and sp.inner_text() == fillp(R_["split"], date=mdtext("2026-10-15"), r="2"), sp.inner_text()
        # 리뷰 1차: 세 버튼 중 어느 것도 두 줄로 접히지 않아요 (320px 에서는 2 + 1)
        hs = page.locator('[data-ui-v2="rec-actions"] button').evaluate_all("(bs) => bs.map((b) => b.getBoundingClientRect().height)")
        assert len(hs) == 3 and max(hs) < 50, hs
        assert page.locator('[data-ui="bottom-sheet"] h3').inner_text() == fillp(R_["title"], name="현대차")
        check_page("기록 시트", "sheet-split")
        close_sheet()
    R.check(page, S, "줄마다 기록 · '{name} 기록' · 분할(현대차 2:1)을 새 기준으로 읽고 분할 줄", rows_and_split)

    def sell_kr():
        sheet('[data-deck-id="dbuilt"] [data-holding="005930"]')
        lst = page.locator('[data-ui-v2="rec-list"] li')
        assert [lst.nth(i).get_attribute("data-rec") for i in range(lst.count())] == ["div", "buy"]
        act(R_["sell"])
        head = page.locator('[data-ui-v2="rec-head"]').inner_text()
        assert head == fillp(R_["head"], qty="10", price="200,000원"), head
        fill_form("11", "240000", today)
        save()
        page.locator('[data-ui-v2="rec-too-many"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-too-many"]').inner_text() == R_["tooMany"]
        check_page("많이 팔기", "sell-too-many")
        fill_form("3", None, "2026-09-01")
        save()
        page.locator('[data-ui-v2="rec-too-early"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-too-early"]').inner_text() == R_["tooEarly"]
        check_page("앞선 날짜", "sell-too-early")
        fill_form(None, None, today)
        if wide:                                                                       # PC 폭 경계(1024px)를 넘나들어도 쓰던 기록은 그대로
            page.set_viewport_size({"width": 900, "height": PC_H})
            page.wait_for_timeout(200)
            vals = [page.locator('[data-ui-v2="rec-form"] input').nth(i).input_value() for i in range(3)]
            page.set_viewport_size({"width": width, "height": PC_H})
            assert vals == ["3", "240000", today], vals
        res = page.locator('[data-ui-v2="rec-result"]')
        res.wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-proceeds"]').inner_text() == "72만원"
        gain = page.locator('[data-ui-v2="rec-gain"]')
        assert gain.get_attribute("data-gain") == "120000" and gain.inner_text() == "+12만원 (+20.0%)", gain.inner_text()
        assert page.locator('[data-ui-v2="rec-result-note"]').inner_text() == R_["note"]
        check_page("팔았어요", "sell-result")
        save()
        page.locator('[data-ui-v2="rec-saved"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-list"] li').first.inner_text().startswith(mdtext(today) + " · " + C["csv"]["kinds"]["sell"] + " · 3주")
        sales = deck(0)["sales"]
        assert len(sales) == 1 and sales[0]["qty"] == 3 and sales[0]["price"] == 240000 and sales[0]["date"] == today and sales[0]["ccy"] == "KRW" and sales[0]["id"]
        close_sheet()
        sub = page.locator('[data-deck-id="dbuilt"] [data-holding="005930"]').inner_text()
        assert "7주 · 평균 단가 200,000원" in sub, sub                                   # 이동평균: 판 뒤에도 평균 단가 그대로
    R.check(page, S, "팔았어요: 많이(거절) · 앞선 날짜(거절) · 판 금액 72만원 · 산 가격보다 +12만원 (+20.0%) · 평균 단가 그대로", sell_kr)

    def sell_split_keep():
        sheet('[data-deck-id="dbuilt"] [data-holding="005380"]')
        act(R_["sell"])
        fill_form("10", "", today)                                                     # 분할 뒤 수량 10주, 가격 빈칸 → 종가
        save()
        page.locator('[data-ui-v2="rec-full"]').wait_for(state="visible")
        q, body = R_["fullSale"].split("? ", 1)
        assert page.locator('[data-ui="bottom-sheet"] h3').inner_text() == q + "?" and page.locator('[data-ui-v2="rec-full"] p').first.inner_text() == body
        check_page("포트폴리오에서도 뺄까요?", "full-sale")
        page.locator('[data-ui-v2="rec-full"] button', has_text=R_["keep"]).click()
        page.locator('[data-ui-v2="rec-sheet"]').wait_for(state="visible")
        acts = page.locator('[data-ui-v2="rec-actions"] button').all_inner_texts()
        assert acts == [C["plan"]["bought"], R_["div"]], acts                         # 다 판 종목: 팔았어요는 없어요
        close_sheet()
        d0 = deck(0)
        assert d0["splits"] == [{"t": "005380", "date": "2026-10-15", "r": 2}] and d0["sales"][-1]["qty"] == 10 and d0["sales"][-1]["price"] == by["005380"]["price"]
        so = page.locator('[data-sold-out="005380"]')
        so.wait_for(state="visible")
        assert C["daily"]["soldOut"] in so.inner_text() and so.locator("button", has_text=R_["button"]).count() == 1
        check_page("다 판 종목", "sold-out-kept")
    R.check(page, S, "분할 뒤 수량 10주를 팔면 저장(분할도 함께) · 다 팔면 뺄까요? → 남겨 두기 → 다 판 종목에 기록", sell_split_keep)

    def sell_us_past():
        sheet('[data-deck-id="dbuilt"] [data-holding="AAPL"]')
        act(R_["sell"])
        assert page.locator('[data-ui-v2="rec-head"]').inner_text() == fillp(R_["head"], qty="4", price="$305.00")
        fill_form("2", "", "2026-10-20")
        res = page.locator('[data-ui-v2="rec-proceeds"]')
        res.wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-proceeds-usd"]').inner_text() == "$" + f"{2 * by['AAPL']['price']:,.2f}"
        check_page("미국 판매", "sell-us")
        save()
        page.locator('[data-ui-v2="rec-saved"]').wait_for(state="visible")
        s = deck(0)["sales"][-1]
        assert s["t"] == "AAPL" and s["fx"] == 1350.0 and s["date"] == "2026-10-20" and s["ccy"] == "USD"   # 그날 환율 (fxHist)
        close_sheet()
    R.check(page, S, "지난 날짜의 미국 판매: fxHist 의 그날 환율 1,350원으로 저장 · 원화 먼저, 달러는 작게", sell_us_past)

    def delete():
        sheet('[data-deck-id="dbuilt"] [data-holding="005930"]')
        buy = page.locator('[data-ui-v2="rec-list"] li[data-rec="buy"]')
        buy.locator("button").click()
        ask = page.locator('[data-ui-v2="rec-del-ask"]')
        ask.wait_for(state="visible")
        check_page("지울까요?", "delete-ask")
        assert ask.locator("p").inner_text() == R_["delAsk"]
        assert ask.locator("button").all_inner_texts() == [R_["del"], R_["cancel"] or C["app"]["close"]]
        ask.locator("button").first.click()
        page.locator('[data-ui-v2="rec-del-refused"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-del-refused"]').inner_text() == R_["delRefused"]
        check_page("지우기 거절", "delete-refused")
        assert len(deck(0)["purchases"]) == 4                                           # 거절: 아무것도 지우지 않아요
        page.locator('[data-ui-v2="rec-list"] li[data-rec="div"] button').click()
        page.locator('[data-ui-v2="rec-del-ask"] button').first.click()
        page.locator('[data-ui-v2="rec-list"] li[data-rec="div"]').wait_for(state="detached")
        assert deck(0)["divs"] == []
        check_page("지우기")
        close_sheet()
    R.check(page, S, "지우기: 묻고 · 뒤의 판매보다 적어지면 거절(아무것도 안 지움) · 배당 기록은 지워져요", delete)

    def divs_again():
        sheet('[data-deck-id="dbuilt"] [data-holding="005930"]')
        act(R_["div"])
        labels = page.locator('[data-ui-v2="rec-form"] label').all_inner_texts()
        assert labels[0].startswith(R_["divWon"]) and labels[1].startswith(R_["divDate"]), labels
        assert R_["divHint"] in page.locator('[data-ui-v2="rec-form"]').inner_text()
        fill_form("abc", today)
        save()
        page.locator('[data-ui-v2="rec-form"] input[aria-invalid="true"]').wait_for(state="visible")
        inv = page.locator('[data-ui-v2="rec-form"] input').evaluate_all("(xs) => xs.map((x) => x.getAttribute('aria-invalid'))")
        assert inv == ["true", None], inv                                              # 금액만 빨갛게, 날짜는 그대로 (리뷰 1차)
        # 리뷰 2차: 수량 · 가격이 없는 양식에는 rec.badAmount 가 승인되기 전 줄이 없어요 ('날짜·수량·가격 …'은 안 나와요)
        bad = page.locator('[data-ui-v2="bad-input"]')
        assert (bad.inner_text() == R_["badAmount"]) if R_["badAmount"] else bad.count() == 0
        check_page("배당 받았어요", "div-bad")
        fill_form("3610", "2026-10-25")
        save()
        page.locator('[data-ui-v2="rec-saved"]').wait_for(state="visible")
        assert [(x["amount"], x["date"]) for x in deck(0)["divs"]] == [(3610, "2026-10-25")]
        close_sheet()
    R.check(page, S, "배당 받았어요: 받은 금액 (원, 세금 뗀 뒤) · 받은 날짜 · 안내 줄 · 잘못 넣으면 거절 · 저장", divs_again)

    def imported_flows():
        # 금액으로 넣은 종목: 판 금액으로 한 번에 모두 → 남겨 두기 → 0주 줄 · SK하이닉스: 다 팔고 빼기
        sheet('[data-pf-holding="035420"]')
        act(R_["sell"])
        assert page.locator('[data-ui-v2="rec-by-amount"]').inner_text() == R_["byAmount"]
        assert page.locator('[data-ui-v2="rec-head"]').count() == 0                     # 금액으로 넣은 종목: 지어낸 주식 수의 머리줄 없음
        labels = page.locator('[data-ui-v2="rec-form"] label').all_inner_texts()
        assert labels[0].startswith(R_["sellAmount"] or R_["proceeds"]), labels
        check_page("금액으로 넣은 종목", "sell-by-amount")
        fill_form("1200000", today)
        save()
        page.locator('[data-ui-v2="rec-full"]').wait_for(state="visible")
        page.locator('[data-ui-v2="rec-full"] button', has_text=R_["keep"]).click()
        page.locator('[data-ui-v2="rec-sheet"]').wait_for(state="visible")
        close_sheet()
        zero = page.locator('[data-deck-id="dimp"] [data-sold-out="035420"]')
        zero.wait_for(state="visible")
        assert "0주" in zero.inner_text() and zero.locator("button", has_text=R_["button"]).count() == 1
        s = deck(1)["sales"][-1]
        assert s["t"] == "035420" and round(s["qty"] * s["price"]) == 1200000
        sheet('[data-pf-holding="000660"]')
        act(R_["sell"])
        assert page.locator('[data-ui-v2="rec-head"]').inner_text() == fillp(R_["head"], qty="3", price="1,200,000원")
        fill_form("3", "", today)
        save()
        page.locator('[data-ui-v2="rec-full"]').wait_for(state="visible")
        page.locator('[data-ui-v2="rec-full"] button', has_text=R_["remove"]).click()
        page.locator('[data-ui="bottom-sheet"]').wait_for(state="detached")
        d1 = deck(1)
        assert not any(h["t"] == "000660" for h in d1["holdings"]) and [e["t"] for e in d1["history"]] == ["000660"]
        assert d1["history"][0]["sales"][0]["qty"] == 3
        check_page("가진 종목: 0주 줄", "portfolio-after")
    R.check(page, S, "금액으로 넣은 종목은 판 금액으로 한 번에 · 남겨 두기 → 0주 줄 · 다 팔고 빼기 → 기록은 history 로", imported_flows)

    def company():
        page.evaluate("location.hash = '#stocks/005930'")
        page.locator('[data-ui-v2="co-record"] button').wait_for(state="visible")
        page.locator('[data-ui-v2="co-record"]').scroll_into_view_if_needed()
        check_page("회사 페이지의 기록", "company")
        page.locator('[data-ui-v2="co-record"] button').click()
        page.locator('[data-ui-v2="rec-which"]').wait_for(state="visible")
        assert page.locator('[data-ui="bottom-sheet"] h3').inner_text() == R_["which"]
        assert page.locator('[data-ui-v2="rec-which"] button').all_inner_texts() == ["배당 생활비 포트폴리오", "가진 종목 포트폴리오"]
        check_page("어느 포트폴리오에 기록할까요?", "which")
        page.locator('[data-ui-v2="rec-which"] button').nth(1).click()
        page.locator('[data-ui-v2="rec-sheet"][data-deck-id="dimp"]').wait_for(state="visible")
        close_sheet()
        # 뺀 종목(history): 회사 페이지에서 배당 받았어요만
        page.evaluate("location.hash = '#stocks/000660'")
        page.locator('[data-ui-v2="co-record"] button').wait_for(state="visible")
        page.locator('[data-ui-v2="co-record"] button').click()
        page.locator('[data-ui-v2="rec-sheet"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-actions"] button').all_inner_texts() == [R_["div"]]
        check_page("뺀 종목의 기록", "history-sheet")
        act(R_["div"])
        fill_form("5000", today)
        save()
        page.locator('[data-ui-v2="rec-saved"]').wait_for(state="visible")
        assert deck(1)["history"][0]["divs"][0]["amount"] == 5000
        close_sheet()
        page.evaluate("location.hash = '#portfolio'")
        at(page, "portfolio")
    R.check(page, S, "회사 페이지의 기록: 두 포트폴리오면 어느 포트폴리오에 · 뺀 종목은 배당 받았어요만 (history 로)", company)

    def returns():
        page.locator('[data-deck-id="dbuilt"] [data-ui-v2="returns-link"]').click()
        at(page, "portfolio/returns/dbuilt")
        page.locator('[data-ui-v2="ret-total"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="ret-date"]').inner_text() == fillp(C["ret"]["date"], date=mdtext(pxd))
        # 손으로 계산: 삼성전자 10주 200,000 → 3주 240,000 판매(+120,000), 남은 7주 × 225,000 − 1,400,000 · 현대차 5주 250,000 (2:1 → 10주
        # 125,000) 10주 × 종가 판매 · AAPL 3주 $300 × 1,300 + 1주 $320 × 1,350 → 10/20 2주 판매($종가 × 1,350), 남은 2주 × 오늘 · 배당 3,610
        p30, p38, pa = by["005930"]["price"], by["005380"]["price"], by["AAPL"]["price"]
        cost_a = 3 * 300 * 1300 + 320 * 1350
        held = (7 * p30 - 1400000) + (2 * pa * fx - cost_a / 2)
        sold = 3 * 40000 + (10 * p38 - 1250000) + (2 * pa * 1350 - cost_a / 2)
        divs = 3610
        rows = [round(held), round(sold), divs]
        got = [int(page.locator(f'[data-ui-v2="ret-row"][data-row="{k}"]').get_attribute("data-v")) for k in ("held", "sold", "divs")]
        assert got == rows, (got, rows)
        assert int(page.locator('[data-ui-v2="ret-total"]').get_attribute("data-v")) == sum(rows)   # 머리 금액 = 세 줄의 합
        # 미국 종목 수익, 어디서 왔나: 남은 묶음 1.5주(1,300) · 0.5주(1,350)
        price_part = (pa - 300) * 1.5 * 1300 + (pa - 320) * 0.5 * 1350
        rate_part = pa * 1.5 * (fx - 1300) + pa * 0.5 * (fx - 1350)
        unit = 10000 if all(abs(v) >= 10000 for v in (price_part, rate_part)) else 1
        r2 = [round(price_part / unit) * unit, round(rate_part / unit) * unit]
        card = page.locator('[data-ui-v2="ret-fx"]')
        assert [int(card.get_attribute("data-price")), int(card.get_attribute("data-rate")), int(card.get_attribute("data-total"))] == r2 + [sum(r2)]
        assert abs(price_part + rate_part - (2 * pa * fx - cost_a / 2)) < 1e-6
        line = page.locator('[data-ui-v2="ret-fx-line"]').inner_text()
        assert line == fillp(C["ret"]["rateAvg"], a=f"{round(cost_a / 2 / 610):,}", b=f"{round(fx):,}"), line
        assert page.locator('[data-ui-v2="ret-fx-bar"]').count() == (1 if min(r2) >= 0 else 0)
        rcpt = page.locator('[data-ui-v2="ret-receipt"]')
        assert rcpt.count() == (1 if C["ret"]["receiptFix"] else 0) and page.locator('[data-ui-v2="ret-pct"]').count() == rcpt.count()
        check_page("내 수익", "returns")
        with page.expect_download() as dl:
            page.locator('[data-ui-v2="ret-csv"] button').click()
        assert dl.value.suggested_filename == f"baepsae-records-{today}.csv", dl.value.suggested_filename
        with open(dl.value.path(), "rb") as fh:
            raw = fh.read()
        assert raw.startswith(b"\xef\xbb\xbf") and raw.endswith(b"\r\n")
        lines = raw.decode("utf-8-sig").split("\r\n")
        assert lines[0] == ",".join(C["csv"]["head"])
        st = stored()
        n = sum(len(d.get(k, [])) for d in st["decks"] for k in ("purchases", "sales", "divs", "imported"))
        n += sum(len(e.get("purchases", [])) + len(e.get("sales", [])) + len(e.get("divs", [])) + (1 if e.get("imported") else 0)
                 for d in st["decks"] for e in d.get("history", []))
        assert len(lines) == n + 2, (len(lines), n)
        assert any(',"=""005930""",' in x for x in lines) and any(x.startswith("가진 종목 포트폴리오,가진 종목,") for x in lines)
        page.locator('[data-ui-v2="app-bar"] button').first.click()
        at(page, "portfolio")
        page.locator('[data-deck-id="dimp"] [data-ui-v2="returns-link"]').click()
        at(page, "portfolio/returns/dimp")
        page.locator('[data-ui-v2="ret-total"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="ret-fx"][data-empty="1"] [data-ui-v2="ret-fx-left"]').inner_text() == C["ret"]["fxLeftOut"]   # MSFT: 달러 평균 단가만
        assert page.locator('[data-ui-v2="usd-today"]').count() == 1
        check_page("내 수익 (가진 종목)", "returns-imported")
    R.check(page, S, "내 수익: 세 줄 = 손으로 계산 · 머리 금액 = 합 · 주가 + 환율 · 평균 환율 줄 · CSV(BOM · 머리줄 · 줄 수 · 코드)", returns)
    ctx.close()
    srv.shutdown()

    # fxHist 가 없으면 지난 날짜의 미국 기록은 저장하지 않아요 · 멈춘 데이터의 내 수익 · 불러오기 실패
    nofx = v196a_files(files, fx_hist=False)
    srv, ctx, page, base = R.open(build_site(nofx), width, init=seed, path="/app.html?dev=1#portfolio", device=pc_device(width) if wide else None)

    def no_rate():
        at(page, "portfolio")
        page.locator('[data-deck-id="dbuilt"] [data-holding="AAPL"]').wait_for(state="visible")
        sheet('[data-deck-id="dbuilt"] [data-holding="AAPL"]')
        act(R_["sell"])
        fill_form("1", "", "2026-10-20")
        page.locator('[data-ui-v2="rec-no-rate"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="rec-no-rate"]').inner_text() == R_["noPastRate"]
        check_page("환율 없음 줄", "no-past-rate-line")
        save()
        page.wait_for_timeout(200)
        assert not stored()["decks"][0].get("sales")                                       # 다른 날 환율로 저장하지 않아요
        fill_form(None, None, today)                                                       # 오늘은 data.json fx
        assert page.locator('[data-ui-v2="rec-no-rate"]').count() == 0
        save()
        page.locator('[data-ui-v2="rec-saved"]').wait_for(state="visible")
        assert stored()["decks"][0]["sales"][0]["fx"] == fx
        check_page("환율 없음", "no-past-rate")
        close_sheet()
    R.check(page, S, "fxHist 없음: 지난 날짜의 미국 판매는 '환율 정보를 불러오지 못해 …' · 저장 안 함 · 오늘은 저장", no_rate)
    ctx.close()
    srv.shutdown()

    stale = v196a_files(files)
    for f in DATA_FILES:
        stale[f]["publishedAt"] = now_kst(6)
    srv, ctx, page, base = R.open(build_site(stale), width, init=seed, path="/app.html?dev=1#portfolio/returns/dbuilt", device=pc_device(width) if wide else None)

    def stale_returns():
        page.locator('[data-ui-v2="ret-stale"]').wait_for(state="visible")
        assert page.locator('[data-ui-v2="ret-total"]').count() == 0 and page.locator('[data-ui-v2="ret-csv"]').count() == 1
        check_page("내 수익 (멈춘 데이터)", "returns-stale")
    R.check(page, S, "멈춘 데이터: 내 수익은 멈춤 줄만(숫자 없음) · 기록 내려받기는 그대로", stale_returns)
    ctx.close()
    srv.shutdown()

    # 리뷰 1차 (오늘 쓰는 macro.json 모양, fxHist 없음): 매수 계획의 샀어요를 지난 날짜로 하면 승인된 거절 줄 · 아무것도 저장하지 않아요.
    # 휴대폰 폭에서만 (to_plan 은 아래 탭 막대로 가요: 같은 화면 · 같은 저장 규칙이라 PC 는 다른 장면이 봐요)
    if wide:
        return
    srv, ctx, page, base = R.open(build_site(nofx), width, init=seed, path="/app.html?dev=1#portfolio")

    def plan_past_no_rate():
        at(page, "portfolio")
        rows = to_plan(page)
        assert any(by.get(t, {}).get("cls") == "us" for t, _ in rows), rows             # 계획에 미국 종목이 있어요
        action(page).click()
        see(page, C["plan"]["sheetTitle"])
        sheet = page.locator('[data-ui-v2="record-form"]')
        sheet.locator('input[type="date"]').fill((dt.date.fromisoformat(pxd) - dt.timedelta(days=2)).isoformat())
        page.get_by_role("button", name=C["plan"]["save"]).click()
        line = page.locator('[data-ui-v2="record-form"] [data-ui-v2="rec-no-rate"]')
        line.wait_for(state="visible")
        assert line.inner_text() == R_["noPastRate"] and line.get_attribute("data-why") == "past"
        assert len(stored()["decks"]) == 2 and page.locator('[data-ui-v2="record-done"]').count() == 0   # 저장 안 함
        check_page("매수 계획 · 환율 없음", "plan-no-rate")
    R.check(page, S, "fxHist 없음: 매수 계획의 샀어요를 지난 날짜로 → '환율 정보를 불러오지 못해 …' · 저장 안 함", plan_past_no_rate)
    ctx.close()
    srv.shutdown()

def mdtext(iso):
    m = int(iso[5:7]); d = int(iso[8:10])
    return fillp(C["app"]["md"], m=m, d=d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    args = ap.parse_args()
    TC.start_at(CLOCK)                                                      # 시험의 시계: 지금 이 순간이 CLOCK (그 뒤로는 흘러요)
    files = read_fixtures()
    names = set()
    for s in files["data.json"]["stocks"]:
        names |= {s.get("nk"), s.get("ne"), s.get("indName")}
    for x in files["disc.json"]["insider"]:                                # v19.1a 공시 탭: 보고한 사람 · 직위는 데이터의 이름이에요
        names |= {x.get("nm"), x.get("pos")}
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
                      lambda: scene_plan_dividend(R, files, width),
                      lambda: scene_say_why(R, files, width),           # say-why 두 줄 (Jack, 2026-11-08): 내 점수 칸 밑 · 미국 배당
                      lambda: scene_say_why_2(R, files, width),         # say-why 2 (Jack, 2026-11-08): 새 데이터 줄 · 회사 수 · 점검 미국 배당 · 홈 공시
                      # 한국 배당 추세 스위치의 반대 상태 (커밋하지 않는 임시 빌드): 두 상태를 모두 화면에서 시험해요
                      lambda: scene_daily(R, files, width, trend=not KR_DIV_TREND), lambda: scene_today(R, files, width, trend=not KR_DIV_TREND),
                      lambda: scene_about(R, files, width), lambda: scene_routes(R, files, width),
                      lambda: scene_market(R, files, width), lambda: scene_stocks(R, files, width),
                      lambda: scene_missing(R, files, width), lambda: scene_no_holding(R, files, width),
                      lambda: scene_v191b(R, files, width),           # v19.1b: divCheck 가 있는 파일 (분할 확인 배당 · 베타 범위 · 2022년 범위)
                      lambda: scene_own_dates(R, files, width),       # v19.1c: 미국 종목의 자기 가격 날짜 (pxd)
                      lambda: scene_stale_after(R, files, width),     # v19.1c: 늦음 경고 시각 (staleAfter)
                      lambda: scene_stale_recheck(R, files, width),   # v19.1c: 열어 둔 화면도 staleAfter 가 지나면 경고
                      lambda: scene_rank(R, files, width),             # v19.5b 홈 · 종목 순위: 칩마다 목록 · 움직임 · 전체 보기
                      lambda: scene_rank_still(R, files, width),       # v19.5b: 움직임 줄이기 · 멈춘 데이터 · 내 기준 칩 · 불러오기 실패
                      lambda: scene_rank_r1(R, files, width)]          # v19.5b 리뷰 1차: 오래 누름 · 키보드 · 빈 목록 · 0.0% · 미국 업종
            for fn in scenes:
                try:
                    fn()
                except Exception as e:
                    R.results.append((f"[{width}] 장면 실행", False, str(e).splitlines()[0][:200]))
                    print(f"  FAIL  [{width}] 장면 실행: {e}", flush=True)
        for fn in (lambda: scene_pc(R, files), lambda: scene_pc_back(R, files), lambda: scene_pc_stale(R, files),
                   lambda: scene_pc_edge(R, files), lambda: scene_company(R, files, 390),
                   lambda: scene_company(R, files, 1280),       # v19.0d PC · v19.1a 회사 페이지 (휴대폰 390 · PC 1280)
                   lambda: scene_v193b(R, files, 390), lambda: scene_v193b(R, files, 1280),     # v19.3b 그림 · 12px
                   lambda: scene_v193c(R, files, 390), lambda: scene_v193c(R, files, 1280),     # v19.3c 기준 카드 · 내 점수 · 처음 안내
                   lambda: scene_v193c_on(R, files, 390), lambda: scene_v193c_on(R, files, 1280),   # v19.3c 두 스위치를 켠 빌드
                   lambda: scene_v193c_narrow(R, files), lambda: scene_v193c_empty(R, files),          # v19.3c 320px · 기준 전의 수 0
                   lambda: scene_v193c_landscape(R, files, (844, 390)), lambda: scene_v193c_landscape(R, files, (568, 320)),   # 가로 휴대폰
                   lambda: scene_v193c_landscape(R, files, (844, 390), preview=True),                     # 가로 휴대폰 · 미리 보기
                   lambda: scene_v193c_landscape(R, files, (568, 320), preview=True),
                   lambda: scene_v193c_offstep(R, files),                                                  # 안내 밖 단계 이동
                   lambda: scene_v193d(R, files, 390), lambda: scene_v193d(R, files, 1280),           # v19.3d 가진 종목 넣기 → 점검
                   lambda: scene_v193d_more(R, files),                                                     # v19.3d 멈춘 데이터 · 379800 · 실패 · 합침
                   lambda: scene_v193d2(R, files, 390), lambda: scene_v193d2(R, files, 1280),           # v19.3d2 단계 · − / + · 이름으로 · 묶음 · 내 규칙 · 다 판 종목
                   lambda: scene_v193d2(R, files, 320),                                                    # v19.3d2 320px (리뷰: 다섯 자리 금액 · 겹침)
                   lambda: scene_bystock_fit(R, files, 320), lambda: scene_bystock_fit(R, files, 360),     # v19.3d2 리뷰 2: 종목별로 보면
                   lambda: scene_bystock_fit(R, files, 390),
                   lambda: scene_v193e_home(R, files, 390), lambda: scene_v193e_home(R, files, 1280),    # v19.3e 새 홈
                   lambda: scene_v193e_home(R, files, 320),
                   lambda: scene_home2_off(R, files),                                                      # 새 홈 비상 스위치를 끈 빌드
                   lambda: scene_v193e_company(R, files, 390), lambda: scene_v193e_company(R, files, 1280),     # v19.3e 회사 페이지
                   lambda: scene_v193e_company(R, files, 320),
                   lambda: scene_store_version(R, files, 390, False), lambda: scene_store_version(R, files, 390, True),   # 기록 판 고침
                   lambda: scene_fix_notes(R, files, 390), lambda: scene_fix_notes(R, files, 1280),             # 2026-11-08 고치는 중 안내
                   lambda: scene_fix_notes(R, files, 390, live=True), lambda: scene_fix_notes(R, files, 1280, live=True),
                   lambda: scene_unit_chk(R, files, 390), lambda: scene_unit_chk(R, files, 1280),             # 2026-11-13 공시 단위 확인
                   lambda: scene_reread_lines(R, files, 390), lambda: scene_reread_lines(R, files, 1280),     # 다시 읽은 뒤: 한 주 안내 · stmtCur
                   lambda: scene_stale_refetch(R, files, 390), lambda: scene_stale_refetch(R, files, 1280),    # 2026-11-08 돌아온 화면은 한 번 받아요
                   lambda: scene_refetch_drafts(R, files, 390), lambda: scene_refetch_drafts(R, files, 1280),   # 만들던 것 위에는 기다려요
                   lambda: scene_say_why_2(R, files, 1280),                                                 # say-why 2: PC 의 새 데이터 줄 · 홈 공시
                   lambda: scene_rank_pc(R, files),                                                        # v19.5b 종목 순위: PC 오른쪽 칸 7줄
                   lambda: scene_us_fcur(R, files, 390, False), lambda: scene_us_fcur(R, files, 390, True),      # 2026-11-12 미국 재무제표 통화
                   lambda: scene_us_fcur(R, files, 1280, True),
                   lambda: scene_dark(R, files, 390), lambda: scene_dark(R, files, 1280),                 # v19.6d 어두운 화면
                   lambda: scene_v196a(R, files, 390), lambda: scene_v196a(R, files, 320),
                   lambda: scene_v196a(R, files, 1280),                                                     # v19.6a 팔았어요 · 배당 받았어요 · 내 수익
                   lambda: scene_v196a_outs(R, files, 390),                                                 # v19.6a 리뷰 2차: splitsInfo.fixed out 줄
                   lambda: scene_v196a_split_price(R, files, 390)):                                         # v19.6a 리뷰 3차: 분할 사이의 빈 가격
            try:
                fn()
            except Exception as e:
                R.results.append(("[PC] 장면 실행", False, str(e).splitlines()[0][:200]))
                print(f"  FAIL  [PC] 장면 실행: {e}", flush=True)
        try:                                                     # v19.3c 첫 방문(데이터 없음 · 아이폰 사파리 · baepsae.html)
            scene_v193c_first(R, files, p.devices)
        except Exception as e:
            R.results.append(("[v19.3c 첫 방문] 장면 실행", False, str(e).splitlines()[0][:200]))
            print(f"  FAIL  [v19.3c 첫 방문] 장면 실행: {e}", flush=True)
        try:                                                     # 아이폰 13 화면(390×664) 하나로만
            scene_iphone_records(R, files, p.devices["iPhone 13"])
        except Exception as e:
            R.results.append(("[아이폰] 장면 실행", False, str(e).splitlines()[0][:200]))
            print(f"  FAIL  [아이폰] 장면 실행: {e}", flush=True)
        try:                                                     # 위 장면이 쓰는 home_settled 의 시간 한도 (Jack, 2026-11-13)
            scene_home_settled_limit(R, files)
        except Exception as e:
            R.results.append(("[홈 공시 기다림 한도] 장면 실행", False, str(e).splitlines()[0][:200]))
            print(f"  FAIL  [홈 공시 기다림 한도] 장면 실행: {e}", flush=True)
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
    # 2026-11-11: 모든 창의 브라우저 시계가 시험의 시계(now_dt)나 그 장면이 정한 날에서 시작했는지 (진짜 시계로 돈 창이 하나도 없어요)
    clock_ok = TC.started and bool(R.clock_drift) and all(drift_ok(d) for d in R.clock_drift)
    R.results.append((f"브라우저 시계는 시험의 날 {CLOCK.date().isoformat()} (또는 장면이 정한 날)에서 시작 (연 창 {len(R.clock_drift)}개)", clock_ok,
                      "" if clock_ok else f"어긋남(초): {[round(d) for d in R.clock_drift if not drift_ok(d)][:5]}"))
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
    sys.exit(tmpdirs.run(main))        # 통과하면 이번 실행의 임시 폴더를 지우고, 실패하면 남겨요 (tests/tmpdirs.py)
