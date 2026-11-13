# -*- coding: utf-8 -*-
"""v19.0b '진지한 화면' 검사 (Jack, 2026-11-03 · 11-04; docs/tasks/v19.0-layout-c.md Part B · C).

- 살구색은 데이터 표시에만: 2.0 코드(src/ui · src/v2)에서 살구색이 나오는 곳은 점 띠(DotStrip: 내 종목 점과 이름),
  비중 막대의 목표 선(WeightBar · BandBar)뿐이에요. 아이콘 · 고른 것 · 알림 띠 · 초점 테두리에는 없어요
- 판정 띠(HeroBand)에는 그림 자리가 없고, 상태 아이콘(할 일 없음 check-circle 초록 · 확인할 일 flag 남색)만 있어요
- 확인할 일 띠와 알약은 이미 있는 상태 색(watch · broken)을 써요
- 2.0 이 보여 주는 그림은 Jack 의 원본을 줄인 파일과, 기록했어요의 baepi-5 (돈 금액이 없는 시트, Jack 2026-11-04)뿐이고, 모두
  저장소에 있어요
- 숫자는 모두 고정폭(tabular-nums)
화면에서 실제로 보이는 색 · 그림 · 아이콘은 tests/smoke_v2.py 가 휴대폰 크기로 다시 봐요.
"""
import os
import re

from buildapp import built
from copytrace import ROOT, read
from visualcheck import MASCOT_DIGITS_EXEMPT, mascot_digit_problems

APRICOT = ("#C97757", "#A9542F", "#FBF1EA")
# 살구색을 써도 되는 곳 (데이터 표시): 파일 → 맨 위 선언 이름. tokens.js 는 색을 정의하는 곳이라 통째로 괜찮아요.
APRICOT_OK = {"src/ui/components.jsx": {"DotStrip", "WeightBar"}, "src/v2/tracking.jsx": {"BandBar"}}
# 살구색을 가리키는 것이면 무엇이든: 이름(COLOR.apricot · COLOR["apricot"] · "apricotText" 같은 문자열 키 · heroAlert),
# 색 값(#C97757 · 투명도까지 붙은 #C97757CC, rgb(201, 119, 87) · rgb(201 119 87) · rgba(201, 119, 87, 0.8))
APRICOT_REF = re.compile(r"apricot\w*|heroAlert|#?(?:C97757|A9542F|FBF1EA)(?:[0-9a-f]{2})?\b"
                         r"|rgba?\(\s*(?:201[\s,]+119[\s,]+87|169[\s,]+84[\s,]+47|251[\s,]+241[\s,]+234)", re.I)
# 맨 위(들여쓰기 없는) 선언: export · default · async 를 앞에 둘 수 있어요
TOP_DECL = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?\s+(\w+)|class\s+(\w+)|(?:const|let|var)\s+(\w+))")
TOP_LEVEL = "(맨 위 문장)"


def code_files():
    out = []
    for d in ("src/ui", "src/v2"):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith((".js", ".jsx", ".html")):
                out.append(f"{d}/{f}")
    return out


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)       # 줄 수는 그대로
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in src.splitlines())


def line_owners(src):
    """줄마다 그 줄을 담은 맨 위 선언의 이름. 맨 위 선언 밖(닫는 괄호 뒤의 맨 위 문장, import · export { } 등)은 TOP_LEVEL."""
    owners, cur = [], TOP_LEVEL
    for line in src.splitlines():
        if line[:1] and not line[0].isspace():
            m = TOP_DECL.match(line)
            if m:
                cur = next(g for g in m.groups() if g)
            elif line.lstrip()[:1] in "})]":
                owners.append(cur)                # 닫는 줄은 아직 그 선언 안이에요
                cur = TOP_LEVEL
                continue
            else:
                cur = TOP_LEVEL
        owners.append(cur)
    return owners


def enclosing_function(src, pos):
    """pos 를 담은 맨 위 선언의 이름 (함수 · 상수 · 클래스). 들여쓰기 없는 다른 문장이면 TOP_LEVEL."""
    return line_owners(src)[src.count("\n", 0, pos)]


def apricot_violations(sources):
    """{파일: 소스} 에서 살구색을 가리키는 곳 중 데이터 표시 컴포넌트 밖에 있는 것: [(파일, 선언, 쓴 것)]. 와 함께 전체 쓰임 수."""
    bad, uses = [], 0
    for f, raw in sources.items():
        if f.endswith("tokens.js"):
            continue
        src = strip_comments(raw)
        owners = line_owners(src)
        for m in APRICOT_REF.finditer(src):
            uses += 1
            who = owners[src.count("\n", 0, m.start())]
            if who not in APRICOT_OK.get(f, set()):
                bad.append((f, who, m.group(0)))
    return bad, uses


def test_apricot_only_marks_data():
    bad, uses = apricot_violations({f: read(f) for f in code_files()})
    assert uses >= 4, "살구색 데이터 표시(목표 선 · 내 종목 점)가 없어요"
    assert not bad, f"살구색이 데이터 표시 밖에 있어요: {bad}"
    tok = strip_comments(read("src/ui/tokens.js"))
    for name in ("ICON_TONE", "ICON_CHIP", "SELECTED", "SELECTED_ROW"):
        block = tok.split(f"export const {name} =", 1)[1].split(";", 1)[0]
        assert not APRICOT_REF.search(block), name


def test_apricot_check_catches_a_stray_use():
    """위 검사가 정말 걸러내는지 (리뷰가 찾은 두 우회로 포함): 고른 탭에 COLOR.apricot · COLOR["apricot"], RuleRow 앞 맨 위 상수,
    문자열 키, 닫는 괄호 뒤의 맨 위 문장, 색 값을 그대로."""
    real = {f: read(f) for f in code_files()}
    comp, today = real["src/ui/components.jsx"], real["src/v2/today.jsx"]
    tab = "background: on ? SELECTED.background"
    assert tab in comp and "export function RuleRow" in comp and "export function Home" in today
    cases = [
        ("src/ui/components.jsx", comp.replace(tab, "background: on ? COLOR.apricot", 1), ("BottomTabBar", "apricot")),
        ("src/ui/components.jsx", comp.replace(tab, 'background: on ? COLOR["apricot"]', 1), ("BottomTabBar", "apricot")),
        ("src/ui/components.jsx", comp.replace("export function RuleRow", "export const strayPill = { background: COLOR.apricot };\nexport function RuleRow", 1),
         ("strayPill", "apricot")),
        ("src/ui/components.jsx", comp.replace("export function RuleRow", "const KEY = 'apricotText';\nexport function RuleRow", 1), ("KEY", "apricotText")),
        ("src/ui/components.jsx", comp.replace("export function RuleRow", "COLOR.apricot;\nexport function RuleRow", 1), (TOP_LEVEL, "apricot")),
        ("src/v2/today.jsx", today.replace("export function Home", "const PILL_BG = \"#c97757\";\nexport function Home", 1), ("PILL_BG", "#c97757")),
        ("src/v2/today.jsx", today.replace("export function Home", "const SEE = \"#C97757CC\";\nexport function Home", 1), ("SEE", "#C97757CC")),
        ("src/v2/today.jsx", today.replace("export function Home", "const SPACED = \"rgb(201 119 87)\";\nexport function Home", 1), ("SPACED", "rgb(201 119 87")),
        ("src/ui/components.jsx", comp.replace(tab, 'background: on ? "rgba(169, 84, 47, 0.8)"', 1), ("BottomTabBar", "rgba(169, 84, 47")),
    ]
    for f, mutated, (who, what) in cases:
        bad, _ = apricot_violations({**real, f: mutated})
        assert (f, who, what) in bad, (f, who, what, bad)


def hero_source():
    src = read("src/ui/components.jsx")
    return src.split("export function HeroBand", 1)[1].split("\nexport function", 1)[0]


def test_verdict_band_has_a_state_icon_and_no_picture_slot():
    hero = hero_source()
    assert "<img" not in hero and "image" not in hero, "판정 띠에 그림 자리가 있어요 (뱁이는 판정 옆에 놓지 않아요)"
    assert "<StateIcon state={state} />" in hero
    comp = read("src/ui/components.jsx")
    icons = comp.split("const STATE_ICONS =", 1)[1].split(";", 1)[0]
    assert 'calm: { name: "check-circle", tone: "ok"' in icons and 'alert: { name: "flag", tone: "on"' in icons, icons
    assert "width: SPACE(15), height: SPACE(15), borderRadius: 999, background: COLOR.surface" in comp      # 60px 흰 동그라미
    # 알림 띠: 지켜봐요 바탕, 알약은 할 일 없음 = ok · 확인할 일 = watch · 규칙 깨짐 = broken (이미 있는 상태 색)
    assert "const HERO_BG = { calm: COLOR.heroCalm, alert: COLOR.watchBg, stale: COLOR.watchBg };" in comp
    assert ("const PILL = { calm: { bg: COLOR.ok, fg: COLOR.surface }, watch: { bg: COLOR.watch, fg: COLOR.surface }, "
            "broken: { bg: COLOR.brokenBg, fg: COLOR.broken } };") in comp
    for f in ("src/v2/today.jsx", "src/v2/why.jsx"):
        src = strip_comments(read(f))
        assert "image=" not in src and "imageAlt" not in src and "baepi" not in src, f


def test_focus_ring_is_navy():
    # v19.6d: 2.0's ring is the ink token: navy (#1C2B45) on the light screen as before, the light text colour on the dark
    # screen (navy would be 1.3:1 on the dark page). The style page has no dark screen and keeps the navy value.
    for f, want in (("src/v2/template.html", "var(--bs-ink)"), ("styleguide/template.html", "#1C2B45")):
        html = read(f)
        rings = re.findall(r"outline:\s*2px solid (#[0-9A-Fa-f]{6}|var\(--bs-[\w-]+\))", html)
        assert rings == [want], (f, rings)
        assert not any(a.lower() in html.lower() for a in APRICOT), f
    app = built("app.html")
    light = app.split(":root{", 1)[1].split("}", 1)[0]
    dark = app.split(':root[data-theme="dark"]{', 1)[1].split("}", 1)[0]
    assert "--bs-ink:#1C2B45;" in light and "--bs-ink:#E8ECF2;" in dark


def test_2_0_pictures_are_scaled_copies_and_exist():
    """2.0 코드가 부르는 그림: 줄인 뱁이(IMG) · 소개의 baepi-og · 사진, 그리고 기록했어요의 baepi-5 (Jack 2026-11-04). 다른 예전
    baepi-1 … 9 와 icon-192 는 2.0 화면에 없어요 (예전 뱁새는 CLAUDE.md 의 예외라 그대로예요)."""
    found = set()
    for f in code_files():
        found |= set(re.findall(r'"([\w-]+\.(?:png|webp|jpg))"', strip_comments(read(f))))
    want = {"baepi-mark.webp", "baepi-16-build.webp", "baepi-15-portfolio.webp", "baepi-20-error.webp", "baepi-21-wip.webp",
            "baepi-og.webp", "jack-photo.jpg", "baepi-5.png"}
    assert found == want, (sorted(found - want), sorted(want - found))
    for f in found:
        assert os.path.exists(os.path.join(ROOT, f)), f
    assert '<img src={"./baepi-" + n + ".png"}' in read("src/detail.jsx"), "예전 뱁새의 뱁이 그림은 그대로예요 (CLAUDE.md 예외)"


def test_numbers_use_tabular_figures():
    assert "font-variant-numeric: tabular-nums" in read("src/v2/template.html")
    assert 'fontVariantNumeric: "tabular-nums"' in read("src/v2/ui.jsx") and 'fontVariantNumeric: "tabular-nums"' in read("src/ui/components.jsx")


def test_mascot_screen_numbers_follow_jacks_definition():
    """CLAUDE.md (Jack, 2026-11-04): 뱁이 화면에는 '숫자'(돈 · 가격 · 수익률 · 비중 · 점수)가 없어요. 날짜 이름표와 종목 수는 숫자가
    아니에요. 돈 · % · 점수는 예외 칸 안에 있어도 걸리고, 날짜 · 종목 수로 설명되지 않는 숫자도 걸려요 (tests/visualcheck.py)."""
    date, figures = MASCOT_DIGITS_EXEMPT[0][0], '[data-ui-v2="about-figures"]'
    assert date == '[data-ui-v2="date-line"]' and figures in [s for s, _ in MASCOT_DIGITS_EXEMPT]
    fine = [("10월 30일 기준", date), ("6일째 갱신이 멈췄어요", date), ("내일부터 오늘 화면에서 6종목을 규칙대로 점검해 드릴게요.", ""),
            ("내 종목 2개", ""), ("10월 1일 시작", ""), ("2025년 사업보고서 기준", ""), ("3,256", figures), ("배당 생활비 덱 · 6종목", "")]
    for item in fine:
        assert mascot_digit_problems([item])[0] == [], item
    caught = {("평균 단가 1,000원", ""): "돈 · 가격", ("1주 · 평균 단가 1,000원", ""): "돈 · 가격", ("19.0%", ""): "% (수익률 · 비중)",
              ("약 46만원", ""): "돈 · 가격", ("1,500만 원", ""): "돈 · 가격", ("3억", ""): "돈 · 가격", ("$12.34", ""): "돈 · 가격",
              ("+5.3%", ""): "% (수익률 · 비중)", ("점수 5위", ""): "점수 · 순위", ("62점", ""): "점수 · 순위",
              ("19.0%", date): "% (수익률 · 비중)", ("1,000원", figures): "돈 · 가격",               # 예외 칸 안이라도 돈 · % 는 걸려요
              ("1주", ""): "설명되지 않는 숫자", ("48,300", ""): "설명되지 않는 숫자", ("１２", ""): "설명되지 않는 숫자"}
    # 리뷰가 찾은 틈 (2026-11-04): 뒤에 한글이 붙은 꼴 · 천 · 퍼센트 · 전각 ％ · USD 앞에 — 예외 칸 안이라도 걸려요
    gaps = {"82점이에요": "점수 · 순위", "1위로": "점수 · 순위", "상위 10위권": "점수 · 순위", "5만이": "돈 · 가격", "12달러를": "돈 · 가격",
            "1천만원": "돈 · 가격", "5천원": "돈 · 가격", "5퍼센트": "% (수익률 · 비중)", "12％": "% (수익률 · 비중)", "USD 12": "돈 · 가격",
            "１２만원": "돈 · 가격", "usd 12": "돈 · 가격", "KRW 1,000": "돈 · 가격"}
    for text, why in gaps.items():
        for box in ("", date, figures):
            caught[(text, box)] = why
    for item, why in caught.items():
        bad, _ = mascot_digit_problems([item])
        assert why in [b[0] for b in bad], (item, bad)
    for item in [("10월 30일 기준", ""), ("6일째 갱신이 멈췄어요", date), ("6일째 갱신이 멈췄어요", ""), ("6종목", ""), ("내 종목 12개", "")]:
        assert mascot_digit_problems([item])[0] == [], item
