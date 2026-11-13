# -*- coding: utf-8 -*-
"""v18.1 디자인 시스템 (Part 1·2) 검사.

- 글자·바탕 대비 4.5:1 이상 (tokens.js 의 CONTRAST_PAIRS)
- 스타일 페이지의 한국어는 모두 docs/design/mockup-copy.csv 에서 왔어요 (새 문구를 지어내지 않음)
- src/ui/ 와 styleguide/main.jsx 코드에는 한국어 문자열이 없어요 (주석 제외) — Part 3 문구 파일 준비
- 앱은 아직 src/ui/ 를 쓰지 않고, 스타일 페이지에 링크하지 않아요 (Part 4 게이트: 라이브 화면 그대로)
- styleguide.html 이 소스와 같아요 (빌드를 잊지 않음), 이모지 0개, 금지어 0개
- Pretendard 라이선스와 글꼴 파일이 모두 있어요
- v19.0b: 아이콘은 Phosphor duotone (256 격자, 바탕 · 선 두 층, 색은 아이콘 표의 네 가지뿐), MIT 라이선스와 출처가 저장소에 있어요
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
UI_FILES = ["src/ui/tokens.js", "src/ui/icons.jsx", "src/ui/components.jsx", "src/ui/phosphor.js"]
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
    # v19.6d: COLOR holds CSS variables ("var(--bs-ink, #1C2B45)"); the light values are PALETTE.light (the dark ones:
    # tests/test_v196d_dark.py)
    pairs = node_value("src/ui/tokens.js", "M.CONTRAST_PAIRS.map(([f,b]) => [f, b, M.contrast(M.PALETTE.light[f], M.PALETTE.light[b])])")
    assert len(pairs) >= 18
    low = [(f, b, round(r, 2)) for f, b, r in pairs if r < 4.5]
    assert not low, f"4.5:1 미달: {low}"


def test_contrast_formula_and_spec_values():
    v = node_value("src/ui/tokens.js", "{ up: M.contrast(M.PALETTE.light.up, M.PALETTE.light.page), white: M.contrast('#000000', '#FFFFFF'), "
                                       "c: M.PALETTE.light, avoid: M.AVOID_PAIRS, vars: M.COLOR }")
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
    assert all(v["vars"][k] == f"var(--bs-{k}, {want})" for k, want in spec.items()), v["vars"]     # v19.6d: the screens use these
    assert ["up", "page"] in v["avoid"] and ["text3", "page"] in v["avoid"]


def test_status_colours_are_not_red_or_blue():
    # v19.6d: both screen modes (STATUS holds CSS variables; valueOf reads each one's light or dark value)
    both = node_value("src/ui/tokens.js", "['light', 'dark'].map((m) => Object.fromEntries(Object.entries(M.STATUS).map(([k, p]) => "
                                          "[k, { fg: M.valueOf(p.fg, m), bg: M.valueOf(p.bg, m) }])))")
    assert len(both) == 2 and all(len(c) == 4 for c in both)
    for tone, pair in [x for c in both for x in c.items()]:
        for hexv in pair.values():
            r, g, b = (int(hexv[i:i + 2], 16) for i in (1, 3, 5))
            assert not (r > 150 and g < 90 and b < 90), f"{tone} 가 빨강이에요: {hexv}"
            assert not (b > 150 and r < 90 and g < 150), f"{tone} 가 파랑이에요: {hexv}"


def test_type_scale_spacing_touch():
    v = node_value("src/ui/tokens.js", "{ size: M.SIZE, weight: M.WEIGHT, radius: M.RADIUS, touch: M.TOUCH, sp: [1,2,3,5,19].map(M.SPACE) }")
    assert sorted(v["size"].values(), reverse=True) == [28, 22, 18, 16, 15, 13, 12]
    assert sorted(v["weight"].values(), reverse=True) == [800, 700, 600, 400]
    assert sorted(v["radius"].values()) == [12, 14, 20]
    assert v["touch"] >= 44 and v["sp"] == [4, 8, 12, 20, 76]


def test_spacing_stays_on_the_4px_grid_in_source():
    """SPACE(2.5) 같은 소수 간격, 숫자로 바로 쓴 padding·margin·gap 이 없어요 (화면 쪽 검사는 smoke_styleguide.py)."""
    for f in UI_FILES + ["styleguide/main.jsx"]:
        src = read(f)
        assert not re.findall(r"SPACE\(\s*\d+\.\d+", src), f"{f}: 4px 격자 밖 SPACE()"
        raw = re.findall(r"\b(?:padding|margin|gap|rowGap|columnGap)\w*:\s*(\d+)\b", src)
        assert all(int(n) % 4 == 0 for n in raw), f"{f}: 격자 밖 숫자 {raw}"
    assert "RADIUS.md" in read("src/ui/components.jsx"), "스펙의 반경 14 를 쓰는 곳이 없어요"


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


# v19.0b (Jack, 2026-11-03): Phosphor duotone. 아이콘 표(docs/tasks/v19.0-layout-c.md Part B) 그대로의 네 가지 색.
# v19.1 Part H (Jack 승인 2026-11-05): 주제 색 다섯 가지를 표 그대로 더해요 — 선은 남색, 바탕만 주제 색. 이 값들 말고는 없어요.
ICON_TONE_SPEC = {"on": {"line": "#1C2B45", "fill": "#CBD3DF"}, "off": {"line": "#6B7280", "fill": "#E3E6EB"},
                  "ok": {"line": "#1F7A4D", "fill": "#CDEBD9"}, "onNavy": {"line": "#FFFFFF", "fill": "#5A6B87"},
                  "earn": {"line": "#1C2B45", "fill": "#B9CDEB"}, "value": {"line": "#1C2B45", "fill": "#BFE0CC"},
                  "div": {"line": "#1C2B45", "fill": "#EBD49A"}, "risk": {"line": "#1C2B45", "fill": "#D3C8EC"},
                  "disc": {"line": "#1C2B45", "fill": "#B5DDDD"}}
TOPIC_CHIP_SPEC = {"earn": "#EAF1FB", "value": "#E9F5EE", "div": "#FBF4E1", "risk": "#F1EDF9", "disc": "#E6F4F4"}   # Part H 칩 바탕
PH_D = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9,.\- ]+$")


def render_icons():
    """아이콘을 모든 이름 × 모든 색으로 실제로 그려 봐요 (react-dom/server, 주석 없는 정적 HTML)."""
    tmp = tempfile.mkdtemp()
    entry = os.path.join(tmp, "icons-entry.jsx")
    with open(entry, "w", encoding="utf-8") as f:
        f.write("import React from 'react';\nimport { renderToStaticMarkup } from 'react-dom/server';\n"
                f"import {{ Icon, IconChip, ICON_NAMES, ICON_TONES, ALIAS }} from {json.dumps(path('src/ui/icons.jsx'))};\n"
                f"import {{ ICON_TONE, COLOR, TOPIC_CHIP }} from {json.dumps(path('src/ui/tokens.js'))};\n"
                f"import {{ PH, PHOSPHOR_VERSION }} from {json.dumps(path('src/ui/phosphor.js'))};\n"
                "const WARNS = []; console.warn = (...a) => { WARNS.push(a.join(' ')); };\n"
                "export const OUT = { names: ICON_NAMES, tones: ICON_TONES, alias: ALIAS, tone: ICON_TONE, ph: PH, version: PHOSPHOR_VERSION,\n"
                "  select: COLOR.select, unknown: renderToStaticMarkup(<Icon name='no-such-icon' />),\n"
                "  unknownAgain: renderToStaticMarkup(<Icon name='no-such-icon' tone='off' />), warns: WARNS,\n"
                "  chip: renderToStaticMarkup(<IconChip name='umbrella' size={40} />), topicChip: TOPIC_CHIP,\n"
                "  topicChips: Object.fromEntries(Object.keys(TOPIC_CHIP).map((t) => [t, renderToStaticMarkup(<IconChip name='coins' size={32} tone={t} />)])),\n"
                "  svg: Object.fromEntries(ICON_NAMES.flatMap((n) => ICON_TONES.map((t) => [n + '|' + t, renderToStaticMarkup(<Icon name={n} tone={t} />)]))) };\n")
    try:
        code = esbuild(entry, "--bundle", "--format=iife", "--global-name=M", "--jsx=automatic", "--external:react", "--external:react-dom",
                       "--external:react/jsx-runtime", "--charset=utf8", "--platform=node")
        r = subprocess.run(["node", "-e", code + "\nprocess.stdout.write(JSON.stringify(M.OUT));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def icon_problems(markup, d, tone):
    """그린 아이콘 하나에서 걸리는 것 (빈 목록이면 통과): 256 격자 · path 정확히 둘(바탕 층, 선 층) · 다른 요소 없음 · 선(stroke) 없음 ·
    색은 표의 그 색만 · path 데이터는 Phosphor 그대로."""
    bad = []
    if not re.match(r'^<svg [^>]*viewBox="0 0 256 256"[^>]*>', markup) or not markup.endswith("</svg>"):
        bad.append("grid")
    tags = re.findall(r"<(\w+)", markup)
    if tags != ["svg", "path", "path"]:
        bad.append(("tags", tags))
    if "stroke" in markup:
        bad.append("stroke")
    layers = re.findall(r'<path data-layer="(fill|line)" d="([^"]+)" fill="(#[0-9A-F]{6})"(?:/>|></path>)', markup)
    if [x[0] for x in layers] != ["fill", "line"]:
        bad.append(("layers", [x[0] for x in layers]))
    elif [x[1] for x in layers] != d:
        bad.append("path data")
    elif [x[2] for x in layers] != [ICON_TONE_SPEC[tone]["fill"], ICON_TONE_SPEC[tone]["line"]]:
        bad.append(("colours", [x[2] for x in layers]))
    colours = set(re.findall(r"#[0-9A-Fa-f]{6}", markup))
    allowed = {c for t in ICON_TONE_SPEC.values() for c in t.values()}
    if colours - allowed:
        bad.append(("colours outside the table", sorted(colours - allowed)))
    return bad


def test_icons_are_phosphor_duotone_with_two_layers_and_table_colours():
    """v18.1 의 '24 격자 · 2px 선' 검사 대신 (v19.0b): 모든 아이콘이 Phosphor 256 격자에 두 층, 색은 표의 네 가지뿐이에요.
    예전 이름(check · alert · close · plus · minus · chevronDown · today · deck · build · search …)은 그대로 쓸 수 있어요."""
    v = render_icons()
    for n in ["check", "alert", "close", "plus", "minus", "chevronDown", "today", "deck", "build", "search"]:
        assert n in v["names"], n
    for n in ["house", "chart-pie-slice", "buildings", "chart-line-up", "percent", "coins", "bank", "identification-badge", "fire",
              "calendar-dots", "clipboard-text", "basket", "umbrella", "file-text", "info", "book-open-text", "database",
              "clock-counter-clockwise", "check-circle", "flag"]:                    # Part B 의 아이콘 표
        assert n in v["ph"], n
    assert v["tone"] == ICON_TONE_SPEC and sorted(v["tones"]) == sorted(ICON_TONE_SPEC)
    assert v["version"] == "2.1.1"
    assert all(a in v["ph"] for a in v["alias"].values()), v["alias"]
    for k, d in v["ph"].items():
        assert isinstance(d, list) and len(d) == 2 and all(PH_D.match(x) for x in d), k
    assert v["unknown"] == "" and v["unknownAgain"] == ""
    # 없는 이름은 조용히 지나가지 않아요: 이름마다 한 번 console.warn (같은 이름을 두 번 그려도 한 번)
    assert v["warns"] == ["[icons] unknown icon name, nothing drawn: no-such-icon"], v["warns"]
    bad = {}
    for key, markup in v["svg"].items():
        n, tone = key.split("|")
        p = icon_problems(markup, v["ph"][v["alias"].get(n, n)], tone)
        if p:
            bad[key] = p
    assert len(v["svg"]) == len(v["names"]) * len(ICON_TONE_SPEC) and not bad, list(bad.items())[:5]
    chip = v["chip"]
    # v19.6d: the chip colours are CSS variables whose light value is the table's (the dark values: tests/test_v196d_dark.py)
    assert v["select"] == "var(--bs-select, #F2F0EB)" and "background:var(--bs-select, #F2F0EB)" in chip and "border-radius:30%" in chip and "width:40px" in chip, chip
    # v19.1 Part H: 주제 칩 바탕은 표의 다섯 가지 그대로, 그 주제의 아이콘 색과 짝이에요 (기본 칩은 위처럼 따뜻한 회색)
    assert v["topicChip"] == {t: f"var(--bs-chip-{t}, {c})" for t, c in TOPIC_CHIP_SPEC.items()}
    assert sorted(TOPIC_CHIP_SPEC) == sorted(k for k in ICON_TONE_SPEC if ICON_TONE_SPEC[k]["line"] == "#1C2B45" and k != "on")
    for t, m in v["topicChips"].items():
        assert f"background:var(--bs-chip-{t}, {TOPIC_CHIP_SPEC[t]})" in m and f'fill="{ICON_TONE_SPEC[t]["fill"]}"' in m and 'fill="#1C2B45"' in m, (t, m)
    src = "".join(read(f) for f in ("src/ui/icons.jsx", "src/ui/phosphor.js"))
    assert "stroke" not in src and "C97757" not in src.upper() and "A9542F" not in src.upper()


def test_icon_check_catches_each_problem():
    """위 검사가 정말 걸러내는지: 선(stroke) · 층 하나 · 표 밖의 색(살구색) · 24 격자 · 다른 요소."""
    v = render_icons()
    m = v["svg"]["check|on"]
    d = v["ph"]["check"]
    assert icon_problems(m, d, "on") == []
    cases = [(m.replace("<path ", '<path stroke="#1C2B45" ', 1), "stroke"),
             (re.sub(r'<path data-layer="fill"[^>]*>(?:</path>)?', "", m), "layers"),
             (m.replace("#1C2B45", "#C97757"), "colours"),
             (m.replace('viewBox="0 0 256 256"', 'viewBox="0 0 24 24"'), "grid"),
             (m.replace("</svg>", '<circle r="3"/></svg>'), "tags")]
    for mutated, want in cases:
        got = [b if isinstance(b, str) else b[0] for b in icon_problems(mutated, d, "on")]
        assert want in got, (want, got)


def test_phosphor_licence_and_source_are_committed():
    """MIT 라이선스 원문과 출처(버전 · npm 무결성 값 · 아이콘 목록)가 저장소에 있고, 아이콘 목록이 src/ui/phosphor.js 와 같아요."""
    lic = read("vendor/phosphor/LICENSE")
    assert lic.startswith("MIT License") and "Copyright (c) 2023 Phosphor Icons" in lic and "Permission is hereby granted" in lic
    src = read("vendor/phosphor/SOURCE.txt")
    assert "@phosphor-icons/core 2.1.1" in src and "integrity: sha512-" in src and "shasum:    62a4cfbec9772f1a613a647da214fbb96f3ad39d" in src
    listed = [l.strip() for l in src.split("Icons (", 1)[1].splitlines()[1:] if l.strip()]
    ph = node_value("src/ui/phosphor.js", "Object.keys(M.PH)")
    assert listed == ph and len(ph) >= 30, (listed, ph)
    gen = read("src/ui/phosphor.js")
    assert "tools/vendor_phosphor.py" in gen and "vendor/phosphor/LICENSE" in gen
    tool = read("tools/vendor_phosphor.py")
    assert 'VERSION = "2.1.1"' in tool and "SHASUM" in tool and "INTEGRITY" in tool
    assert not re.search(r"https?://", gen), "phosphor.js 에 바깥 주소가 있어요"


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


def scaled_targets():
    """tools/resize_assets.py 의 TARGETS 이름 (Jack 의 원본을 2배 크기로 줄인 파일의 원본 이름)."""
    src = read("tools/resize_assets.py")
    body = src.split("TARGETS = {", 1)[1].split("\n}", 1)[0]
    return re.findall(r'^\s+"([\w.-]+)": \(\d+,', body, flags=re.M)


def test_example_images_are_jacks_artwork():
    """예시 속 그림은 Jack 의 그림뿐이에요: baepi-1 … baepi-9 (PNG), 또는 v19.0b 부터 docs/design/v19/assets 의 원본을
    tools/resize_assets.py 로 줄이기만 한 WebP (원본이 그 폴더에 있고, TARGETS 에 있어야 해요)."""
    ex = node_value("styleguide/examples.js", "M.EX")
    imgs = [s for s in strings(ex) if s.endswith((".png", ".webp", ".jpg"))]
    assert imgs
    targets = scaled_targets()
    assert "baepi-mark.png" in targets and len(targets) >= 7, targets
    for i in imgs:
        if i.endswith(".png"):
            assert re.fullmatch(r"baepi-[1-9]\.png", i), i
        else:
            assert re.fullmatch(r"baepi-[\w-]+\.webp", i), i
            orig = i[:-5] + ".png"
            assert orig in targets and os.path.exists(path("docs", "design", "v19", "assets", orig)), i
        assert os.path.exists(path(i)), i


def test_all_components_exported_and_tagged():
    src = read("src/ui/components.jsx")
    for c in COMPONENTS:
        assert f'data-ui="{c}"' in src, c
    for name in ["HeroBand", "StatStrip", "ListRow", "StatusChip", "Segmented", "Stepper", "MoneyInput", "BottomActionBar",
                 "BottomSheet", "Collapsible", "BottomTabBar", "DotStrip", "WeightBar", "RuleRow"]:
        assert re.search(rf"export function {name}\b", src), name


def test_amount_shrinks_only_the_unit_right_after_the_number():
    """v19.0b 큰 숫자: 숫자 바로 뒤의 정해진 단위(원 · 만원 · 만 원 · 억 · 조 · 만 · % · %p)만 작게. 숫자 앞뒤 낱말("약" · "남는 돈" ·
    "2022년처럼")과 목록에 없는 한글(종목 · 년)은 그대로 (리뷰 2026-11-03)."""
    cases = ["약 −84만원", "남는 돈 3만원", "1,418,000원", "+5.3%", "$12.34", "약 46만원", "12만원 남았어요", "5종목 중 3종목",
             "2022년처럼", "+8.0%p", "3억 2,000만원", "1,500만 원", "2조원", "100원이에요"]
    got = node_value("src/ui/components.jsx", "Object.fromEntries(" + json.dumps(cases, ensure_ascii=False) + ".map((t) => [t, M.amountParts(t)]))")
    want = {
        "약 −84만원": [["약 −84", False], ["만원", True]],
        "남는 돈 3만원": [["남는 돈 3", False], ["만원", True]],
        "1,418,000원": [["1,418,000", False], ["원", True]],
        "+5.3%": [["+5.3", False], ["%", True]],
        "$12.34": [["$12.34", False]],
        "약 46만원": [["약 46", False], ["만원", True]],
        "12만원 남았어요": [["12", False], ["만원", True], [" 남았어요", False]],
        "5종목 중 3종목": [["5종목 중 3종목", False]],
        "2022년처럼": [["2022년처럼", False]],
        "+8.0%p": [["+8.0", False], ["%p", True]],
        "3억 2,000만원": [["3", False], ["억", True], [" 2,000", False], ["만원", True]],
        "1,500만 원": [["1,500", False], ["만 원", True]],
        "2조원": [["2", False], ["조원", True]],
        "100원이에요": [["100원이에요", False]],
    }
    assert got == want, got
    for t, parts in got.items():
        assert "".join(p for p, _ in parts) == t                      # 글자는 그대로 (읽는 순서 · 복사)
        assert not any(small and re.search(r"\d", p) for p, small in parts), parts


def test_fmt_pct_never_shows_minus_zero_or_nan():
    v = node_value("src/ui/components.jsx", "[M.fmtPct(-0.04), M.fmtPct(0.04), M.fmtPct(-6.2), M.fmtPct(2.25), M.fmtPct(NaN), M.fmtPct(null), M.fill('{count}개', {count: 6})]")
    assert v[:3] == ["0.0%", "0.0%", "−6.2%"] and v[3] in ("+2.3%", "+2.2%") and v[4:] == ["–", "–", "6개"], v


# ── Part 4 게이트: 라이브 화면은 그대로 ──
def test_app_does_not_use_the_new_ui_yet():
    """앱 번들(build.sh 와 같은 입구)에 실제로 들어가는 파일 목록에 src/ui · fonts · styleguide 가 없어요."""
    tmp = tempfile.mkdtemp()
    meta = os.path.join(tmp, "meta.json")
    esbuild("src/main.jsx", "--bundle", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8",
            f"--metafile={meta}", f"--outfile={os.path.join(tmp, 'app.js')}")
    with open(meta, encoding="utf-8") as f:
        inputs = list(json.load(f)["inputs"])
    assert any(i.startswith("src/") for i in inputs), inputs[:5]
    bad = [i for i in inputs if i.startswith(("src/ui/", "styleguide/", "fonts/"))]
    assert not bad, f"앱이 새 디자인 파일을 가져와요: {bad}"


def test_style_page_not_linked_from_app():
    for f in ["baepsae.html", "template.html", "index.html", "manifest.webmanifest", "sw.js"]:
        assert os.path.exists(path(f)), f"{f} 가 없어요"
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
