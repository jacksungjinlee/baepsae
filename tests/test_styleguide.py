# -*- coding: utf-8 -*-
"""v18.1 디자인 시스템 (Part 1·2) 검사.

- 글자·바탕 대비 4.5:1 이상 (tokens.js 의 CONTRAST_PAIRS)
- 스타일 페이지의 한국어는 모두 docs/design/mockup-copy.csv 에서 왔어요 (새 문구를 지어내지 않음)
- src/ui/ 와 styleguide/main.jsx 코드에는 한국어 문자열이 없어요 (주석 제외) — Part 3 문구 파일 준비
- 앱은 아직 src/ui/ 를 쓰지 않고, 스타일 페이지에 링크하지 않아요 (Part 4 게이트: 라이브 화면 그대로)
- styleguide.html 이 소스와 같아요 (빌드를 잊지 않음), 이모지 0개, 금지어 0개
- Pretendard 라이선스와 글꼴 파일이 모두 있어요
"""
import csv
import json
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANGUL = re.compile("[가-힣ㄱ-ㆎ]")
EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍]")
# 목업 문구 속 가짜 회사 이름 (CSV 문장 안에 나와요)
FAKE_NAMES = ["늘봄금융", "솔담정밀", "마루식품"]
UI_FILES = ["src/ui/tokens.js", "src/ui/icons.jsx", "src/ui/components.jsx"]
COMPONENTS = ["hero-band", "button", "stat-strip", "list-row", "status-chip", "segmented", "stepper", "money-input",
              "bottom-action-bar", "bottom-sheet", "collapsible", "bottom-tab-bar", "dot-strip", "weight-bar", "rule-row"]


def path(*p):
    return os.path.join(ROOT, *p)


def read(p):
    with open(path(p), encoding="utf-8") as f:
        return f.read()


def esbuild(*args):
    exe = path("node_modules", ".bin", "esbuild")
    assert os.path.exists(exe), "node_modules 가 없어요: npm ci 를 먼저 하세요"
    r = subprocess.run([exe, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def node_value(entry, expr):
    """ES 모듈을 하나로 묶어 node 에서 값을 꺼내요 (package.json 에 type:module 이 없어서)."""
    code = esbuild(entry, "--bundle", "--format=iife", "--global-name=M", "--loader:.js=jsx", "--jsx=automatic",
                   "--external:react", "--external:react/jsx-runtime", "--charset=utf8", "--platform=node")
    r = subprocess.run(["node", "-e", code + f"\nprocess.stdout.write(JSON.stringify({expr}));"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def mockup_rows():
    with open(path("docs", "design", "mockup-copy.csv"), encoding="utf-8-sig") as f:
        return [r["지금 문구"].strip() for r in csv.DictReader(f) if r["지금 문구"].strip()]


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


def from_mockup(s, rows, row_set):
    """s 가 목업 CSV 의 한 줄과 같은지: 그대로 · 줄바꿈 \\n = " / " · {자리}는 CSV 의 숫자/이름 자리."""
    norm = s.strip().replace("\n", " / ")
    if norm in row_set:
        return True
    if "{" in norm:
        rx = re.compile("^" + re.sub(r"\\\{\w+\\\}", ".+?", re.escape(norm)) + "$")
        if any(rx.match(r) for r in rows):
            return True
    return norm in FAKE_NAMES


# ── Part 1 ──
def test_contrast_pairs_pass():
    pairs = node_value("src/ui/tokens.js", "M.CONTRAST_PAIRS.map(([f,b]) => [f, b, M.contrast(M.COLOR[f], M.COLOR[b])])")
    assert len(pairs) >= 18
    low = [(f, b, round(r, 2)) for f, b, r in pairs if r < 4.5]
    assert not low, f"4.5:1 미달: {low}"


def test_contrast_formula_and_spec_values():
    v = node_value("src/ui/tokens.js", "{ up: M.contrast(M.COLOR.up, M.COLOR.page), white: M.contrast('#000000', '#FFFFFF'), "
                                       "c: M.COLOR, avoid: M.AVOID_PAIRS }")
    assert abs(v["white"] - 21) < 0.01
    assert abs(v["up"] - 4.35) < 0.01          # 스펙에 적힌 값: 빨강은 page 바탕 위에서 미달
    c = v["c"]
    spec = {"ink": "#1C2B45", "text2": "#5B6576", "text3": "#6B7280", "page": "#F5F3EF", "surface": "#FFFFFF",
            "line": "#F0EDE8", "border": "#E8E4DE", "apricot": "#C97757", "apricotText": "#A9542F",
            "heroCalm": "#EDF4EF", "heroAlert": "#FBF1EA", "up": "#D6303F", "down": "#2563EB", "ok": "#1F7A4D",
            "okBg": "#E7F4EC", "watch": "#8A5A00", "watchBg": "#FFF3D6", "broken": "#FFFFFF", "brokenBg": "#1C2B45",
            "neutral": "#3D4B63", "neutralBg": "#EEF0F4"}
    wrong = {k: (c.get(k), want) for k, want in spec.items() if c.get(k) != want}
    assert not wrong, f"스펙 표와 다른 색: {wrong}"
    assert ["up", "page"] in v["avoid"] and ["text3", "page"] in v["avoid"]


def test_status_colours_are_not_red_or_blue():
    c = node_value("src/ui/tokens.js", "M.STATUS")
    for tone, pair in c.items():
        for hexv in pair.values():
            r, g, b = (int(hexv[i:i + 2], 16) for i in (1, 3, 5))
            assert not (r > 150 and g < 90 and b < 90), f"{tone} 가 빨강이에요: {hexv}"
            assert not (b > 150 and r < 90 and g < 150), f"{tone} 가 파랑이에요: {hexv}"


def test_type_scale_spacing_touch():
    v = node_value("src/ui/tokens.js", "{ size: M.SIZE, weight: M.WEIGHT, radius: M.RADIUS, touch: M.TOUCH, s3: M.SPACE(3) }")
    assert sorted(v["size"].values(), reverse=True) == [28, 22, 18, 16, 15, 13, 12]
    assert sorted(v["weight"].values(), reverse=True) == [800, 700, 600, 400]
    assert sorted(v["radius"].values()) == [12, 14, 20]
    assert v["touch"] >= 44 and v["s3"] == 12


def test_pretendard_licence_and_files():
    lic = read("fonts/pretendard/LICENSE.txt")
    assert "SIL OPEN FONT LICENSE" in lic.upper() and "1.1" in lic
    css = read("fonts/pretendard/pretendard-variable.css")
    assert "Pretendard Variable" in css
    files = re.findall(r"url\(\./([^)]+)\)", css)
    assert len(files) >= 90
    missing = [f for f in files if not os.path.exists(path("fonts", "pretendard", f))]
    assert not missing, missing
    hangul_face = [b for b in css.split("@font-face") if "U+ac" in b.lower() or "u+ac00" in b.lower()]
    assert hangul_face, "한글 글자 범위를 가진 글꼴 조각이 없어요"


def test_icons_are_svg_only():
    names = node_value("src/ui/icons.jsx", "M.ICON_NAMES")
    for n in ["check", "alert", "close", "plus", "minus", "chevronDown", "today", "deck", "build", "search"]:
        assert n in names
    src = read("src/ui/icons.jsx")
    assert 'strokeWidth={2}' in src and 'viewBox="0 0 24 24"' in src


# ── Part 2 ──
def test_no_korean_literals_in_ui_code():
    """주석을 빼면 src/ui/ 와 스타일 페이지 코드에는 한국어가 없어요: 문구는 props / examples.js 로만 들어와요."""
    for f in UI_FILES + ["styleguide/main.jsx"]:
        out = esbuild(f, "--minify", "--loader:.js=jsx", "--jsx=automatic", "--charset=utf8")   # 주석이 빠져요
        hits = sorted(set(HANGUL.findall(out)))
        assert not hits, f"{f}: 코드 안 한국어 {hits[:10]}"


def test_every_korean_example_comes_from_the_mockup():
    rows = mockup_rows()
    row_set = set(rows)
    for name in FAKE_NAMES:
        assert any(name in r for r in rows), name
    ex = node_value("styleguide/examples.js", "M.EX")
    ko = [s for s in strings(ex) if HANGUL.search(s)]
    assert len(ko) >= 120, len(ko)
    stray = [s for s in ko if not from_mockup(s, rows, row_set)]
    assert not stray, f"목업 CSV 에 없는 문구: {stray}"


def test_example_images_are_jacks_artwork():
    ex = node_value("styleguide/examples.js", "M.EX")
    imgs = [s for s in strings(ex) if s.endswith(".png")]
    assert imgs
    for i in imgs:
        assert re.fullmatch(r"baepi-[1-9]\.png", i), i
        assert os.path.exists(path(i)), i


def test_all_components_exported_and_tagged():
    src = read("src/ui/components.jsx")
    for c in COMPONENTS:
        assert f'data-ui="{c}"' in src, c
    for name in ["HeroBand", "StatStrip", "ListRow", "StatusChip", "Segmented", "Stepper", "MoneyInput", "BottomActionBar",
                 "BottomSheet", "Collapsible", "BottomTabBar", "DotStrip", "WeightBar", "RuleRow"]:
        assert re.search(rf"export function {name}\b", src), name


def test_fmt_pct_never_shows_minus_zero():
    v = node_value("src/ui/components.jsx", "[M.fmtPct(-0.04), M.fmtPct(0.04), M.fmtPct(-6.2), M.fmtPct(1.25), M.fill('{count}개', {count: 6})]")
    assert v == ["0.0%", "0.0%", "−6.2%", "+1.3%", "6개"] or v == ["0.0%", "0.0%", "−6.2%", "+1.2%", "6개"], v


# ── Part 4 게이트: 라이브 화면은 그대로 ──
def test_app_does_not_use_the_new_ui_yet():
    for dirpath, _, files in os.walk(path("src")):
        if os.path.abspath(dirpath).startswith(path("src", "ui")):
            continue
        for f in files:
            if f.endswith((".js", ".jsx")):
                s = read(os.path.relpath(os.path.join(dirpath, f), ROOT))
                assert not re.search(r"""from\s+["'][./]*ui/""", s), f"{f} 가 src/ui 를 가져와요"


def test_style_page_not_linked_from_app():
    for f in ["baepsae.html", "template.html", "index.html", "manifest.webmanifest", "sw.js"]:
        if os.path.exists(path(f)):
            assert "styleguide" not in read(f), f
    head = read("styleguide/template.html")
    assert 'name="robots" content="noindex' in head


def test_style_page_build_is_current_and_clean():
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "sg.js")
    esbuild("styleguide/main.jsx", "--bundle", "--minify", "--loader:.jsx=jsx", "--loader:.js=jsx", "--jsx=automatic",
            "--charset=utf8", "--define:process.env.NODE_ENV=\"production\"", f"--outfile={out}")
    with open(out, encoding="utf-8") as f:
        js = f.read()
    want = read("styleguide/template.html").replace("/*BUNDLE*/", js)
    have = read("styleguide.html")
    assert have == want, "styleguide.html 이 소스와 달라요: bash build-styleguide.sh 를 다시 하세요"
    assert not EMOJI.findall(have), sorted(set(EMOJI.findall(have)))
    voice = read("docs/BAEPSAE_VOICE.md")
    words = [w.strip() for w in voice.split("## 금지어", 1)[1].split("\n", 2)[1].split("·") if w.strip()]
    assert "잣대" in words
    for src in ["styleguide.html", "styleguide/examples.js"] + UI_FILES:
        found = [w for w in words if w in read(src)]
        assert not found, f"{src}: 금지어 {found}"
