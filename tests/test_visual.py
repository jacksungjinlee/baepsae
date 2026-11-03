# -*- coding: utf-8 -*-
"""v19.0b '진지한 화면' 검사 (Jack, 2026-11-03 · 11-04; docs/tasks/v19.0-layout-c.md Part B · C).

- 살구색은 데이터 표시에만: 2.0 코드(src/ui · src/v2)에서 살구색이 나오는 곳은 점 띠(DotStrip: 내 종목 점과 이름),
  비중 막대의 목표 선(WeightBar · BandBar)뿐이에요. 아이콘 · 고른 것 · 알림 띠 · 초점 테두리에는 없어요
- 판정 띠(HeroBand)에는 그림 자리가 없고, 상태 아이콘(할 일 없음 check-circle 초록 · 확인할 일 flag 남색)만 있어요
- 확인할 일 띠와 알약은 이미 있는 상태 색(watch · broken)을 써요
- 2.0 이 보여 주는 그림은 Jack 의 원본을 줄인 파일뿐이고(baepi-1 … 9 PNG 는 2.0 에서 더는 쓰지 않아요), 모두 저장소에 있어요
- 숫자는 모두 고정폭(tabular-nums)
화면에서 실제로 보이는 색 · 그림 · 아이콘은 tests/smoke_v2.py 가 휴대폰 크기로 다시 봐요.
"""
import os
import re

from copytrace import ROOT, read

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
    assert tab in comp and "export function RuleRow" in comp and "export function Today" in today
    cases = [
        ("src/ui/components.jsx", comp.replace(tab, "background: on ? COLOR.apricot", 1), ("BottomTabBar", "apricot")),
        ("src/ui/components.jsx", comp.replace(tab, 'background: on ? COLOR["apricot"]', 1), ("BottomTabBar", "apricot")),
        ("src/ui/components.jsx", comp.replace("export function RuleRow", "export const strayPill = { background: COLOR.apricot };\nexport function RuleRow", 1),
         ("strayPill", "apricot")),
        ("src/ui/components.jsx", comp.replace("export function RuleRow", "const KEY = 'apricotText';\nexport function RuleRow", 1), ("KEY", "apricotText")),
        ("src/ui/components.jsx", comp.replace("export function RuleRow", "COLOR.apricot;\nexport function RuleRow", 1), (TOP_LEVEL, "apricot")),
        ("src/v2/today.jsx", today.replace("export function Today", "const PILL_BG = \"#c97757\";\nexport function Today", 1), ("PILL_BG", "#c97757")),
        ("src/v2/today.jsx", today.replace("export function Today", "const SEE = \"#C97757CC\";\nexport function Today", 1), ("SEE", "#C97757CC")),
        ("src/v2/today.jsx", today.replace("export function Today", "const SPACED = \"rgb(201 119 87)\";\nexport function Today", 1), ("SPACED", "rgb(201 119 87")),
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
    for f in ("src/v2/template.html", "styleguide/template.html"):
        html = read(f)
        rings = re.findall(r"outline:\s*2px solid (#[0-9A-Fa-f]{6})", html)
        assert rings == ["#1C2B45"], (f, rings)
        assert not any(a.lower() in html.lower() for a in APRICOT), f


def test_2_0_pictures_are_scaled_copies_and_exist():
    """2.0 코드가 부르는 그림: 줄인 뱁이(IMG) · 소개의 baepi-og · 사진뿐. 예전 baepi-1 … 9 와 icon-192 는 2.0 화면에 없어요
    (예전 뱁새는 CLAUDE.md 의 예외라 그대로예요)."""
    found = set()
    for f in code_files():
        found |= set(re.findall(r'"([\w-]+\.(?:png|webp|jpg))"', strip_comments(read(f))))
    want = {"baepi-mark.webp", "baepi-16-build.webp", "baepi-15-portfolio.webp", "baepi-20-error.webp", "baepi-21-wip.webp",
            "baepi-og.webp", "jack-photo.jpg"}
    assert found == want, (sorted(found - want), sorted(want - found))
    for f in found:
        assert os.path.exists(os.path.join(ROOT, f)), f
    assert '<img src={"./baepi-" + n + ".png"}' in read("src/detail.jsx"), "예전 뱁새의 뱁이 그림은 그대로예요 (CLAUDE.md 예외)"


def test_numbers_use_tabular_figures():
    assert "font-variant-numeric: tabular-nums" in read("src/v2/template.html")
    assert 'fontVariantNumeric: "tabular-nums"' in read("src/v2/ui.jsx") and 'fontVariantNumeric: "tabular-nums"' in read("src/ui/components.jsx")
