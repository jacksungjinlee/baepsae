# -*- coding: utf-8 -*-
"""v19.0b 화면 규칙을 브라우저에서 보는 도우미 (tests/smoke_v2.py · smoke_preview.py · smoke_launch.py 가 같이 써요).

지금 화면에서 (visual_ok):
- 보이는 그림이 모두 열렸어요 (complete · naturalWidth > 0)
- 뱁이 그림(baepi-*, 로고 마크 제외)은 판정 띠 안에 없어요
- 뱁이 그림이 보이는 '화면'(열린 시트 · 대화 상자 안의 그림이면 그 시트, 아니면 시트를 뺀 페이지 전체)에 '숫자'가 없어요 —
  CLAUDE.md: "never on a screen that shows numbers. Numbers means money, prices, returns, weights and scores. A date label
  or a count of stocks is not one." (Jack, 2026-11-04). 판단은 아래 표 셋으로 해요 (mascot_digit_problems):
    1) NUMBERS: 돈(원 · 천 · 만 · 억 · 조 · 달러 · $ · ₩ · USD · KRW) · %(% · ％ · 퍼센트: 수익률 · 비중) · 점수 · 순위 —
       화면 어디에 있든(예외 칸 안이라도) 실패. 전각 숫자(０-９)도 숫자예요
    2) MASCOT_DIGITS_EXEMPT: 이 칸 안의 숫자는 숫자가 아니에요 (날짜 줄, 소개 페이지의 몇 곳)
    3) NOT_NUMBERS: 칸 밖에서도 숫자가 아닌 꼴 (날짜 · 종목 수). 이 셋으로 설명되지 않는 숫자가 하나라도 남으면 실패
- 아이콘은 Phosphor 256 격자의 두 층(바탕 · 선, stroke 없음)이고, 색은 아이콘 표(on · off · ok · 남색 위 + v19.1 주제 색 다섯)의 짝뿐이에요
- 고른 것(고른 탭 · 알약 · 줄 · 칩 · 라디오), 아이콘, 상태 아이콘, 판정 띠와 알약의 계산된 색에 살구색이 없어요
- v19.3b (docs/tasks/v19.3-portfolio-pictures-accounts.md Part B · C), 2.0 페이지(app.html · app-preview.html)에서만:
  보이는 글은 모두 12px 이상이에요 (SVG 안의 글은 그려진 크기로: 글자 크기 × 화면 배율). 회사 로고 · 글자 표시의 색
  (src/v2/company.js MARK_COLORS 중 남색 #1C2B45 를 뺀 아홉 가지)은 회사 표시 밖의 어디에도(그래프 · 막대 · 글) 칠해지지 않아요.
뱁이가 나온 화면은 PLACEMENTS 에 모여요 (그림 · 화면 · 걸린 숫자 · 쓴 예외 칸과 꼴) — 스모크 결과 끝에 표로 찍어요.
"""
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# 1) 언제나 '숫자' (CLAUDE.md: money, prices, returns, weights and scores) — 뱁이 화면에 있으면 예외 칸 안이라도 실패
#    \d 는 전각 숫자(０-９)도 잡아요. 뒤에 한글이 붙어도("82점이에요" · "1위로" · "5만이" · "12달러를") 걸려요.
NUMBERS = [
    ("돈 · 가격", re.compile(r"\d\s*(?:[천만억조]\s?원|원|천|만|억|조|달러)|[$₩＄￦]\s*\d|\d\s*(?:USD|KRW)|(?:USD|KRW)\s*\d", re.I)),
    ("% (수익률 · 비중)", re.compile(r"\d\s*(?:%|％|퍼센트)")),
    ("점수 · 순위", re.compile(r"\d\s*(?:점|위)")),
]
# 3) 칸 밖에서도 숫자가 아닌 꼴 — 날짜 이름표와 종목 수 (Jack, 2026-11-04). 이 꼴을 지우고도 숫자가 남으면 실패
NOT_NUMBERS = [
    ("날짜", re.compile(r"\d{4}년|\d{1,2}월\s?\d{1,2}일(?:\s?\([월화수목금토일]\))?|\d{4}-\d{2}-\d{2}|\d+일째")),
    ("종목 수", re.compile(r"내 종목\s?\d[\d,]*개|\d[\d,]*\s?종목")),
]
# 2) 뱁이가 있는 화면에서도 숫자가 있어도 되는 칸 — 한 곳에 모아 둬요. Jack 이 빼라고 하면 그 줄만 지우면 돼요.
#    (돈 · % · 점수는 이 칸 안에 있어도 실패해요: 위의 NUMBERS)
MASCOT_DIGITS_EXEMPT = [
    ('[data-ui-v2="date-line"]', "데이터 날짜 줄('10월 30일 기준'): 데이터가 언제 것인지 알리는 날짜일 뿐, 종목·돈의 숫자가 아니에요"),
    ('[data-ui-v2="about-figures"]', "소개의 숫자 줄(분석 종목 수 · 업종 그룹 수): 종목 수예요 (소개 페이지는 규칙이 이름으로 허락한 곳)"),
    ('[data-ui-v2="about-data"]', "소개의 '{n}개가 넘는 … 종목' 문장: 종목 수예요"),
    ('[data-ui-v2="about-years"]', "소개의 경력 줄('6~7년', about.md 그대로): 같은 이유 (소개 페이지)"),
    ('[data-ui-v2="about-principle-n"]', "소개의 원칙 번호(1 · 2 · 3 · 4): 같은 이유 (소개 페이지)"),
]
PLACEMENTS = set()


def mascot_digit_problems(items):
    """items: 뱁이 화면의 숫자가 든 글 조각 [(글, 감싼 예외 칸의 선택자 또는 "")]. 돌려줌: (걸린 것 [(이유, 글)], 쓴 예외 · 꼴 이름들)."""
    bad, used = [], set()
    for text, ex in items:
        hit = [name for name, rx in NUMBERS if rx.search(text)]
        if hit:
            bad += [(name, text) for name in hit]
            continue
        if ex:
            used.add(ex)
            continue
        rest = text
        for name, rx in NOT_NUMBERS:
            if rx.search(rest):
                used.add(name)
                rest = rx.sub("", rest)
        if re.search(r"\d", rest):
            bad.append(("설명되지 않는 숫자", text))
    return bad, sorted(used)


# 살구색(src/ui/tokens.js 의 apricot · apricotText · heroAlert): 데이터 표시에만, 고른 것 · 아이콘 · 알림 띠 · 초점 테두리에는 없어요
# 계산된 색에서 살구색 세 값을 찾아요: rgb(…) 이든 투명도가 붙은 rgba(…, 0.8) 이든
APRICOT_RGB = re.compile(r"\(\s*(?:201,\s*119,\s*87|169,\s*84,\s*47|251,\s*241,\s*234)\s*[,)]")
NAVY_RGB = "rgb(28, 43, 69)"
SELECT_RGB = "rgb(242, 240, 235)"
# 아이콘 색 표 (docs/tasks/v19.0-layout-c.md Part B): (바탕 층, 선 층) — on · off · ok · 남색 위
# + v19.1 Part H 주제 색 (Jack 승인 2026-11-05): 실적 · 가치 · 배당 · 출렁임·위험 · 공시 — 선은 남색, 바탕만 주제 색. 그 밖은 없어요.
ICON_PAIRS = {("#CBD3DF", "#1C2B45"), ("#E3E6EB", "#6B7280"), ("#CDEBD9", "#1F7A4D"), ("#5A6B87", "#FFFFFF"),
              ("#B9CDEB", "#1C2B45"), ("#BFE0CC", "#1C2B45"), ("#EBD49A", "#1C2B45"), ("#D3C8EC", "#1C2B45"), ("#B5DDDD", "#1C2B45")}
VISUAL = r"""(exempt) => {
  const out = { verdictImg: [], badImg: [], icons: [], styles: [], imgs: 0, placements: [] };
  const shown = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  // 한 화면의 보이는 글 중 숫자가 있는 조각마다 [글, 감싼 예외 칸] (판단은 파이썬의 mascot_digit_problems)
  const digitsOn = (root, skipDialogs) => {
    const items = [];
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const n = w.currentNode, e = n.parentElement, t = n.textContent;
      if (!e || !/[\d０-９]/.test(t) || e.closest('script, style')) continue;      // 전각 숫자도
      if (skipDialogs && e.closest('[role="dialog"]')) continue;
      if (!shown(e)) continue;
      items.push([t.trim(), exempt.find((sel) => e.closest(sel)) || '']);
    }
    return items;
  };
  const screenName = (root) => {
    if (root !== document.body) return 'sheet: ' + (root.getAttribute('aria-label') || '');
    const about = document.querySelector('[data-ui-v2="about"]');
    if (about && shown(about)) return 'about';
    const h = [...document.querySelectorAll('main h2, main [data-ui-v2="load-fail"]')].find(shown);
    return h ? (h.matches('[data-ui-v2="load-fail"]') ? 'load-fail' : h.innerText.split('\n')[0].slice(0, 30)) : '(no title)';
  };
  for (const img of document.querySelectorAll('img')) {
    if (!shown(img)) continue;
    out.imgs++;
    const src = img.getAttribute('src') || '';
    if (!(img.complete && img.naturalWidth > 0)) out.badImg.push(src);
    if (!/baepi-/.test(src) || /baepi-mark/.test(src)) continue;               // 로고 마크는 그림 자리가 아니에요
    if (img.closest('[data-ui="hero-band"], [data-ui-v2="today-hero"], [data-ui-v2="why-verdict"]')) out.verdictImg.push(src);
    const dialog = img.closest('[role="dialog"]');
    const root = dialog || document.body;
    out.placements.push([src, screenName(root), digitsOn(root, !dialog)]);
  }
  for (const svg of document.querySelectorAll('svg[data-icon]')) {
    const k = [...svg.children];
    const ok = svg.getAttribute('viewBox') === '0 0 256 256' && k.length === 2 && k.every((x) => x.tagName === 'path')
      && k[0].dataset.layer === 'fill' && k[1].dataset.layer === 'line' && !svg.querySelector('[stroke]') && !svg.hasAttribute('stroke');
    out.icons.push([svg.dataset.icon, ok, k[0] ? k[0].getAttribute('fill') : '', k[1] ? k[1].getAttribute('fill') : '']);
  }
  const sel = ['[data-selected="1"]', '[aria-current="page"]', '[aria-current="true"]', '[role="radio"][aria-checked="true"]',
    '[data-ui-part="tab-pill"]', 'nav[data-ui="bottom-tab-bar"] path', '[data-ui="icon-chip"]', '[data-ui="icon-chip"] path',
    '[data-ui="state-icon"]', '[data-ui="state-icon"] path', '[data-ui="hero-band"]', '[data-ui="hero-band"] [data-ui-part="pill"]',
    '[data-ui="hero-band"] h2', '[data-ui="status-chip"] path', '[data-ui-v2="rule-line"] path', 'svg[data-icon] path'].join(', ');
  for (const e of document.querySelectorAll(sel)) {
    const s = getComputedStyle(e);
    out.styles.push([e.tagName + ' ' + (e.dataset.ui || e.dataset.uiPart || e.dataset.uiV2 || e.dataset.layer || ''),
      [s.backgroundColor, s.color, s.borderTopColor, s.borderRightColor, s.borderBottomColor, s.borderLeftColor, s.boxShadow, s.outlineColor, s.fill].join(' | ')]);
  }
  return out; }"""


def visual_problems(v):
    """VISUAL 의 결과에서 걸리는 것 (빈 목록이면 통과)."""
    bad = []
    if v["badImg"]:
        bad.append(("열리지 않은 그림", v["badImg"]))
    if v["verdictImg"]:
        bad.append(("판정 띠 옆 뱁이", v["verdictImg"]))
    for src, screen, items in v["placements"]:
        hit, _ = mascot_digit_problems(items)
        if hit:
            bad.append(("숫자가 있는 화면의 뱁이", [src, screen, hit[:5]]))
    icons = [i for i in v["icons"] if not i[1] or (i[2], i[3]) not in ICON_PAIRS]
    if icons:
        bad.append(("Phosphor 두 층 · 표의 색이 아닌 아이콘", icons[:4]))
    apricot = [x for x in v["styles"] if APRICOT_RGB.search(x[1])]
    if apricot:
        bad.append(("살구색", apricot[:4]))
    return bad


def visual_ok(page):
    """그림이 다 열릴 때까지 기다린 뒤 (최대 5초) 이 화면의 v19.0b 규칙을 봐요."""
    try:
        page.wait_for_function("() => [...document.images].every((i) => i.complete)", timeout=5000)
    except Exception:
        pass
    v = page.evaluate(VISUAL, [sel for sel, _ in MASCOT_DIGITS_EXEMPT])
    for src, screen, items in v["placements"]:
        hit, used = mascot_digit_problems(items)
        PLACEMENTS.add((src, screen, " / ".join(t for _, t in hit[:3]), " · ".join(used)))
    bad = visual_problems(v)
    assert not bad, f"v19.0b 화면 규칙: {bad}"
    if page.evaluate(IS_V2):                                       # v19.3b: 2.0 페이지만 (예전 뱁새는 2.0 으로 옮길 때)
        small = text_floor(page)
        assert not small, f"v19.3b 12px 아래 글: {small[:6]}"
        logo = page.evaluate(LOGO_PAINT, LOGO_RGB)
        assert not logo, f"v19.3b 회사 표시 밖에 로고 색: {logo[:4]}"
    return v


# ── v19.3b Part B: 12px 아래 글이 없어요 ──
TEXT_FLOOR_PX = 12
IS_V2 = r"() => /\/app(-preview)?\.html$/.test(location.pathname)"
# 보이는 글 조각마다 그려진 글자 크기. 조각의 상자가 1px 아래이거나 숨은 것(visibility · display · opacity 0 인 조상)은 빼요.
# SVG 안의 글은 화면 배율(getScreenCTM)을 곱해요. 회사 글자 표시는 CSS 의 ::before 로 그린 장식이라 글 조각이 아니에요.
TEXT_SIZES = r"""(floor) => {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, e = n.parentElement, t = n.textContent.trim();
    if (!e || !t || e.closest('script, style, noscript, template')) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (e.checkVisibility && !e.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
    let px = parseFloat(getComputedStyle(e).fontSize);
    if (e instanceof SVGElement && e.getScreenCTM) { const m = e.getScreenCTM(); if (m) px *= Math.hypot(m.a, m.b); }
    if (px < floor - 0.01) out.push([t.slice(0, 40), Math.round(px * 100) / 100, e.closest('[data-ui-v2]') ? e.closest('[data-ui-v2]').dataset.uiV2 : e.tagName]);
  }
  return out; }"""


def text_floor(page, floor=TEXT_FLOOR_PX):
    """지금 화면에서 floor(12px) 아래로 그려진 보이는 글 [(글, px, 가까운 data-ui-v2)] — 빈 목록이면 통과."""
    return page.evaluate(TEXT_SIZES, floor)


# ── v19.3b Part C: 로고 색은 그래프를 칠하지 않아요 ──
def _logo_colours():
    with open(os.path.join(ROOT, "src", "v2", "company.js"), encoding="utf-8") as fh:
        body = fh.read().split("export const MARK_COLORS = [", 1)[1].split("]", 1)[0]
    cols = re.findall(r'"(#[0-9A-Fa-f]{6})"', body)
    assert len(cols) == 10 and cols[0].upper() == "#1C2B45", cols
    return cols[1:]                                                # 남색(글자 · 선의 색)은 어디에나 있어요


LOGO_RGB = ["rgb(%d, %d, %d)" % tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in _logo_colours()]
LOGO_PAINT = r"""(cols) => {
  const out = [];
  for (const e of document.body.querySelectorAll('*')) {
    if (e.closest('[data-ui-v2="co-mark"]')) continue;
    const s = getComputedStyle(e);
    for (const v of [s.backgroundColor, s.color, s.fill, s.stroke, s.borderTopColor, s.borderBottomColor, s.borderLeftColor, s.borderRightColor, s.backgroundImage])
      if (v && cols.some((c) => v.includes(c))) { out.push([e.tagName, e.dataset.uiV2 || e.dataset.ui || '', v]); break; }
  }
  return out; }"""


# v19.3b: 기준 · 템플릿 그림 (tools/resize_pictures.py) — 시험 사이트에 폴더째 같이 놓아요
PICTURE_DIR = "pictures"


def copy_pictures(site):
    shutil.copytree(os.path.join(ROOT, PICTURE_DIR), os.path.join(site, PICTURE_DIR))


def placements_table():
    """뱁이가 나온 화면들 (그림 · 화면 · 걸린 숫자 · 쓴 예외 칸과 꼴) — 결과 끝에 찍어요."""
    rows = sorted(PLACEMENTS)
    return ["  " + " | ".join([src, screen, digits or "걸린 숫자 없음", used or "숫자 없음"]) for src, screen, digits, used in rows]


# 2.0 이 쓰는 v19.0b 뱁이 그림 (Jack 의 원본을 2배 크기로 줄인 것, tools/resize_assets.py) — 시험 사이트에 같이 놓아요
V2_IMAGES = ["baepi-mark.webp", "baepi-16-build.webp", "baepi-15-portfolio.webp", "baepi-20-error.webp", "baepi-21-wip.webp"]
