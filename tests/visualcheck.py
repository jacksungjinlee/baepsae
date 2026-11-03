# -*- coding: utf-8 -*-
"""v19.0b 화면 규칙을 브라우저에서 보는 도우미 (tests/smoke_v2.py · smoke_preview.py · smoke_launch.py 가 같이 써요).

지금 화면에서 (visual_ok):
- 보이는 그림이 모두 열렸어요 (complete · naturalWidth > 0)
- 뱁이 그림(baepi-*, 로고 마크 제외)은 판정 띠 안에 없고, 숫자(0-9)가 보이는 카드(section · 시트 · 불러오기 실패 칸) 안에도 없어요.
  소개 페이지는 CLAUDE.md 의 뱁이 규칙이 이름으로 허락한 곳이라 빼요 (숫자 줄이 있어도)
- 아이콘은 Phosphor 256 격자의 두 층(바탕 · 선, stroke 없음)이고, 색은 아이콘 표(on · off · ok · 남색 위)의 짝뿐이에요
- 고른 것(고른 탭 · 알약 · 줄 · 칩 · 라디오), 아이콘, 상태 아이콘, 판정 띠와 알약의 계산된 색에 살구색이 없어요
"""

# 살구색(src/ui/tokens.js 의 apricot · apricotText · heroAlert): 데이터 표시에만, 고른 것 · 아이콘 · 알림 띠 · 초점 테두리에는 없어요
APRICOT_RGB = ["rgb(201, 119, 87)", "rgb(169, 84, 47)", "rgb(251, 241, 234)"]
NAVY_RGB = "rgb(28, 43, 69)"
SELECT_RGB = "rgb(242, 240, 235)"
# 아이콘 색 표 (docs/tasks/v19.0-layout-c.md Part B): (바탕 층, 선 층) — on · off · ok · 남색 위
ICON_PAIRS = {("#CBD3DF", "#1C2B45"), ("#E3E6EB", "#6B7280"), ("#CDEBD9", "#1F7A4D"), ("#5A6B87", "#FFFFFF")}
VISUAL = r"""() => {
  const out = { mascot: [], verdictImg: [], badImg: [], icons: [], styles: [], imgs: 0 };
  const shown = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  for (const img of document.querySelectorAll('img')) {
    if (!shown(img)) continue;
    out.imgs++;
    const src = img.getAttribute('src') || '';
    if (!(img.complete && img.naturalWidth > 0)) out.badImg.push(src);
    if (!/baepi-/.test(src) || /baepi-mark/.test(src)) continue;               // 로고 마크는 그림 자리가 아니에요
    if (img.closest('[data-ui="hero-band"], [data-ui-v2="today-hero"], [data-ui-v2="why-verdict"]')) out.verdictImg.push(src);
    if (img.closest('[data-ui-v2="about"]')) continue;                          // 소개 페이지: 규칙이 이름으로 허락한 곳
    const card = img.closest('section, [role="dialog"], [data-ui-v2="load-fail"]');
    const text = card ? card.innerText : '';
    if (!card || /\d/.test(text)) out.mascot.push([src, card ? text.slice(0, 80) : '(카드 없음)']);
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
    if v["mascot"]:
        bad.append(("숫자가 있는 카드의 뱁이", v["mascot"]))
    icons = [i for i in v["icons"] if not i[1] or (i[2], i[3]) not in ICON_PAIRS]
    if icons:
        bad.append(("Phosphor 두 층 · 표의 색이 아닌 아이콘", icons[:4]))
    apricot = [x for x in v["styles"] if any(a in x[1] for a in APRICOT_RGB)]
    if apricot:
        bad.append(("살구색", apricot[:4]))
    return bad


def visual_ok(page):
    """그림이 다 열릴 때까지 기다린 뒤 (최대 5초) 이 화면의 v19.0b 규칙을 봐요."""
    try:
        page.wait_for_function("() => [...document.images].every((i) => i.complete)", timeout=5000)
    except Exception:
        pass
    bad = visual_problems(page.evaluate(VISUAL))
    assert not bad, f"v19.0b 화면 규칙: {bad}"


# 2.0 이 쓰는 v19.0b 뱁이 그림 (Jack 의 원본을 2배 크기로 줄인 것, tools/resize_assets.py) — 시험 사이트에 같이 놓아요
V2_IMAGES = ["baepi-mark.webp", "baepi-16-build.webp", "baepi-15-portfolio.webp", "baepi-20-error.webp", "baepi-21-wip.webp"]
