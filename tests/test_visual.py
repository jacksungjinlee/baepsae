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
# 살구색을 써도 되는 곳 (데이터 표시): 파일 → 함수 이름
APRICOT_OK = {"src/ui/components.jsx": {"DotStrip", "WeightBar"}, "src/v2/tracking.jsx": {"BandBar"}}


def code_files():
    out = []
    for d in ("src/ui", "src/v2"):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith((".js", ".jsx", ".html")):
                out.append(f"{d}/{f}")
    return out


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in src.splitlines())


def enclosing_function(src, pos):
    names = [(m.start(), m.group(1)) for m in re.finditer(r"function (\w+)", src) if m.start() < pos]
    return names[-1][1] if names else None


def apricot_uses():
    """(파일, 함수, 쓴 것) 목록: COLOR.apricot · COLOR.apricotText · COLOR.heroAlert 와 살구색 값 그대로."""
    out = []
    for f in code_files():
        src = strip_comments(read(f))
        for m in re.finditer(r"COLOR\.(apricot|apricotText|heroAlert)\b|#(?:C97757|A9542F|FBF1EA)", src, flags=re.I):
            out.append((f, enclosing_function(src, m.start()), m.group(0)))
    return out


def test_apricot_only_marks_data():
    uses = apricot_uses()
    assert uses, "살구색 데이터 표시(목표 선 · 내 종목 점)가 하나도 없어요"
    bad = [u for u in uses if u[1] not in APRICOT_OK.get(u[0], set()) and not u[0].endswith("tokens.js")]
    assert not bad, f"살구색이 데이터 표시 밖에 있어요: {bad}"
    tok = strip_comments(read("src/ui/tokens.js"))
    for name in ("ICON_TONE", "ICON_CHIP", "SELECTED", "SELECTED_ROW"):
        block = tok.split(f"export const {name} =", 1)[1].split(";", 1)[0]
        assert not any(a.lower() in block.lower() for a in APRICOT) and "apricot" not in block, name


def test_apricot_check_catches_a_stray_use():
    """위 검사가 정말 걸러내는지: 고른 탭 · 알림 띠 같은 곳에 살구색을 넣으면 걸려요."""
    src = strip_comments(read("src/ui/components.jsx"))
    fake = src.replace("background: on ? SELECTED.background", "background: on ? COLOR.apricot", 1)
    assert fake != src
    hits = [(enclosing_function(fake, m.start()), m.group(0)) for m in re.finditer(r"COLOR\.(apricot|apricotText|heroAlert)\b", fake)]
    assert ("BottomTabBar", "COLOR.apricot") in hits, hits


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
