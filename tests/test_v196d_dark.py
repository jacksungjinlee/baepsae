# -*- coding: utf-8 -*-
"""v19.6d 어두운 화면 (docs/tasks/v19.6-records-alerts-dark.md Part D).

- 색마다 밝은 값과 어두운 값이 있어요 (src/ui/tokens.js PALETTE). 밝은 값은 예전 표 그대로, 어두운 값은 Part D 표 그대로예요.
  화면이 쓰는 토큰은 모두 CSS 변수 "var(--bs-이름, 밝은 값)" 이라 화면 모드를 따라가요.
- 글자 · 바탕 대비(CONTRAST_PAIRS)는 두 화면 모드 모두 4.5:1 이상, 쓰지 않는 조합(AVOID_PAIRS)은 화면 모드마다 따로 있어요.
  홈 남색 띠의 반투명 규칙 칸 위 글도 두 모드 모두 4.5:1 이상 ([Q14] heroAlert 는 어두운 watchBg).
- 2.0 코드(src/v2 · src/ui)에는 고정된 색이 없어요: 아래 ALLOWED 의 것만, 이유와 함께.
- 페이지 머리의 작은 스크립트가 첫 화면을 그리기 전에 화면 모드를 정해요 (저장 · 기기 · 막힌 저장소 → 자동). 그 스크립트는
  theme.js 의 bootTheme 그대로이고, 페이지에 CSP 가 생기면(v19.4) 그 해시가 들어 있어야 해요.
- 화면 모드는 기록과 따로예요: 자기 키 하나, 내보내는 파일에는 없어요.
- 승인된 문구(Appendix 1)와 CLAUDE.md 의 한 줄.
화면에서 실제로 바꿔 보는 검사는 tests/smoke_v2.py 의 '어두운 화면' 장면이에요.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess

import pytest

from buildapp import built

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
HEX = re.compile(r"^#[0-9A-F]{6}$")


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def esbuild(*args):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    assert os.path.exists(exe), "node_modules 가 없어요: npm ci 를 먼저 하세요"
    r = subprocess.run([exe, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def node_value(entry, expr):
    code = esbuild(entry, "--bundle", "--format=iife", "--global-name=M", "--loader:.js=jsx", "--jsx=automatic",
                   "--external:react", "--external:react/jsx-runtime", "--charset=utf8", "--platform=node")
    r = subprocess.run(["node", "-e", code + f"\nprocess.stdout.write(JSON.stringify({expr}));"], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def over(rgba, bg):
    """반투명 색(rgba(r,g,b,a))을 bg(#…) 위에 놓았을 때 보이는 색."""
    r, g, b, a = [float(x) for x in re.fullmatch(r"rgba\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)", rgba.replace(" ", "")).groups()]
    under = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join("%02X" % round(a * f + (1 - a) * u) for f, u in zip((r, g, b), under))


TOKENS = None


def tokens():
    global TOKENS
    if TOKENS is None:
        TOKENS = node_value("src/ui/tokens.js", "{ P: M.PALETTE, COLOR: M.COLOR, OVERLAY: M.OVERLAY, TOPIC_CHIP: M.TOPIC_CHIP, TOPIC_ART: M.TOPIC_ART, "
                            "TOPIC_DOT: M.TOPIC_DOT, HOLDING_SHADES: M.HOLDING_SHADES, HOLDING_TEXT: M.HOLDING_TEXT, CHART: M.CHART, STATUS: M.STATUS, "
                            "ICON_TONE: M.ICON_TONE, ICON_TONE_DARK: M.ICON_TONE_DARK, ICON_CHIP: M.ICON_CHIP, SELECTED: M.SELECTED, "
                            "SELECTED_ROW: M.SELECTED_ROW, PAIRS: M.CONTRAST_PAIRS, AVOID: M.AVOID_PAIRS, AVOID_DARK: M.AVOID_PAIRS_DARK, "
                            "MASCOT: M.MASCOT_CHIP, THEME_COLOR: M.THEME_COLOR, css: M.themeCss(), "
                            "ratios: ['light', 'dark'].map((m) => M.CONTRAST_PAIRS.map(([f, b]) => M.contrast(M.PALETTE[m][f], M.PALETTE[m][b]))) }")
    return TOKENS


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


# ── the two palettes ──
# docs/tasks/v18.1 (light, unchanged) and v19.6 Part D (dark), word for word. New roles (v19.6d) take the light colour they
# replace (primary = ink as a background, onPrimary = surface as text on navy, …).
LIGHT_SPEC = {"ink": "#1C2B45", "text2": "#5B6576", "text3": "#6B7280", "page": "#F5F3EF", "surface": "#FFFFFF", "line": "#F0EDE8",
              "border": "#E8E4DE", "apricot": "#C97757", "apricotText": "#A9542F", "heroCalm": "#EDF4EF", "heroAlert": "#FBF1EA",
              "up": "#D6303F", "down": "#2563EB", "upOnPage": "#B4232F", "ok": "#1F7A4D", "okBg": "#E7F4EC", "watch": "#8A5A00",
              "watchBg": "#FFF3D6", "broken": "#FFFFFF", "brokenBg": "#1C2B45", "neutral": "#3D4B63", "neutralBg": "#EEF0F4", "select": "#F2F0EB",
              "primary": "#1C2B45", "onPrimary": "#FFFFFF", "onPrimary2": "#E3E7EE", "onPrimary3": "#CBD3DF", "highlight": "#FFE2A8",
              "highlightBg": "#FFE2A8", "edge": "#D9D4CC", "edgeStrong": "#C9C2B8", "chipEdge": "#E3DED6", "winEdge": "#ECE8E1", "track": "#ECE8E1"}
DARK_SPEC = {"ink": "#E8ECF2", "primary": "#31456B", "onPrimary": "#FFFFFF", "text2": "#9BA6B7", "text3": "#8E99AA", "page": "#10151E",
             "surface": "#1A2231", "line": "#2A3446", "border": "#3A4558", "select": "#232C3C", "up": "#FF6B75", "down": "#7AA2FF",
             "upOnPage": "#FF6B75", "ok": "#6FD39F", "okBg": "#1C3328", "watch": "#F1C25B", "watchBg": "#3A3018", "broken": "#FFFFFF",
             "brokenBg": "#31456B", "neutral": "#C3CCD9", "neutralBg": "#232C3C", "heroCalm": "#1C3328", "apricot": "#E08E6A",
             "apricotText": "#F0A27F",
             "heroAlert": "#3A3018"}                                          # [Q14]: the dark watchBg
ICON_DARK_SPEC = {"on": ("#E8ECF2", "#4A5872"), "earn": ("#E8ECF2", "#3B5480"), "value": ("#E8ECF2", "#2F6047"), "div": ("#E8ECF2", "#6B5A2A"),
                  "risk": ("#E8ECF2", "#4C4275"), "disc": ("#E8ECF2", "#2C6464"), "ok": ("#6FD39F", "#2E5A44"), "off": ("#8E99AA", "#2E384A"),
                  "onNavy": ("#FFFFFF", "#4A5F87")}
CHIP_DARK_SPEC = {"earn": "#1D2B43", "value": "#1C3328", "div": "#362E1D", "risk": "#2A2541", "disc": "#1B3535"}
SHADES_LIGHT = ["#1C2B45", "#3D4B63", "#5A6B87", "#7C889C", "#9AA3B2", "#C9D0DB"]
SHADES_DARK_SPEC = ["#E8ECF2", "#C3CCD9", "#9BA6B7", "#7C889C", "#5A6B87", "#3D4B63"]


def test_every_token_has_a_light_and_a_dark_value_and_is_a_css_variable():
    t = tokens()
    light, dark = t["P"]["light"], t["P"]["dark"]
    assert set(light) == set(dark) and len(light) >= 90, sorted(set(light) ^ set(dark))
    for k in t["COLOR"]:                                                     # COLOR keys: #RRGGBB both ways (the contrast check reads them)
        assert HEX.match(light[k]) and HEX.match(dark[k]), (k, light[k], dark[k])
    for k, v in list(light.items()) + list(dark.items()):
        assert HEX.match(v) or re.fullmatch(r"rgba\(\d+,\d+,\d+,(0|1|0?\.\d+)\)", v), (k, v)
    # every token the screens use is var(--bs-<name>, <light value>) of a name in the palette
    groups = {g: t[g] for g in ("COLOR", "OVERLAY", "TOPIC_CHIP", "TOPIC_ART", "TOPIC_DOT", "HOLDING_SHADES", "HOLDING_TEXT", "CHART", "STATUS",
                                "ICON_CHIP", "SELECTED", "SELECTED_ROW")}
    seen = 0
    for g, v in groups.items():
        for s in strings(v):
            for name, fallback in re.findall(r"var\(--bs-([\w-]+), ([^)]*\)?)\)", s):
                assert name in light and fallback == light[name], (g, s)
                seen += 1
            if g in ("COLOR", "TOPIC_CHIP", "TOPIC_DOT", "HOLDING_SHADES", "HOLDING_TEXT", "OVERLAY"):
                assert s.startswith("var(--bs-"), (g, s)
    assert seen >= 80, seen
    assert set(t["COLOR"]) <= set(light) and all(t["COLOR"][k] == f"var(--bs-{k}, {light[k]})" for k in t["COLOR"])


# Every light value, word for word as it stood in v19.5b (023785a) before it became a token: the file and the literal it
# replaced. A light value that changes (or a new token without its v19.5b source written here) fails the test below.
LIGHT_V195B = {
    # src/ui/tokens.js COLOR (v18.1 table)
    "ink": "#1C2B45", "text2": "#5B6576", "text3": "#6B7280", "page": "#F5F3EF", "surface": "#FFFFFF", "line": "#F0EDE8", "border": "#E8E4DE",
    "apricot": "#C97757", "apricotText": "#A9542F", "heroCalm": "#EDF4EF", "heroAlert": "#FBF1EA", "up": "#D6303F", "down": "#2563EB",
    "upOnPage": "#B4232F", "ok": "#1F7A4D", "okBg": "#E7F4EC", "watch": "#8A5A00", "watchBg": "#FFF3D6", "broken": "#FFFFFF",
    "brokenBg": "#1C2B45", "neutral": "#3D4B63", "neutralBg": "#EEF0F4", "select": "#F2F0EB",
    # the roles split out of them: COLOR.ink as a background, COLOR.surface as text on navy
    "primary": "#1C2B45", "onPrimary": "#FFFFFF",
    "onPrimary2": "#E3E7EE",                 # src/v2/home2.jsx (rule tile label, broken line)
    "onPrimary3": "#CBD3DF",                 # src/v2/home2.jsx (date, 확인하지 못했어요, notes) and src/v2/build.jsx (처음부터 card body)
    "highlight": "#FFE2A8", "highlightBg": "#FFE2A8",   # src/v2/home2.jsx (detail, '!' badge), src/v2/guide.jsx LIGHT
    "edge": "#D9D4CC",                       # src/v2/build.jsx (empty meter slot), src/v2/guide.jsx (step dots)
    "edgeStrong": "#C9C2B8",                 # src/v2/build.jsx (−/+ ring), src/v2/report.jsx (empty dot)
    "chipEdge": "#E3DED6", "winEdge": "#ECE8E1", "track": "#ECE8E1",   # src/v2/rank.jsx CHIP_LINE, WIN_LINE (edge and switch background)
    # overlays: src/ui/components.jsx (sheet scrim, bar shadow), src/v2/guide.jsx (SHADE, bubble), src/v2/build.jsx (Fan)
    "scrim": "rgba(28,43,69,0.45)", "shadow": "rgba(28,43,69,0.10)", "guide": "rgba(28, 43, 69, 0.55)", "pop": "rgba(28, 43, 69, 0.35)",
    "lift": "rgba(0, 0, 0, 0.25)",
    # src/ui/tokens.js ICON_TONE
    "icon-on-line": "#1C2B45", "icon-on-fill": "#CBD3DF", "icon-off-line": "#6B7280", "icon-off-fill": "#E3E6EB",
    "icon-ok-line": "#1F7A4D", "icon-ok-fill": "#CDEBD9", "icon-onNavy-line": "#FFFFFF", "icon-onNavy-fill": "#5A6B87",
    "icon-earn-line": "#1C2B45", "icon-earn-fill": "#B9CDEB", "icon-value-line": "#1C2B45", "icon-value-fill": "#BFE0CC",
    "icon-div-line": "#1C2B45", "icon-div-fill": "#EBD49A", "icon-risk-line": "#1C2B45", "icon-risk-fill": "#D3C8EC",
    "icon-disc-line": "#1C2B45", "icon-disc-fill": "#B5DDDD",
    # src/ui/tokens.js TOPIC_CHIP and TOPIC_ART (earn: ICON_TONE.earn.fill and TOPIC_CHIP.earn)
    "chip-earn": "#EAF1FB", "chip-value": "#E9F5EE", "chip-div": "#FBF4E1", "chip-risk": "#F1EDF9", "chip-disc": "#E6F4F4",
    "art-earn-ink": "#B9CDEB", "art-earn-light": "#EAF1FB", "art-value-ink": "#4E9A72", "art-value-light": "#DCEFE3",
    "art-div-ink": "#C59A2E", "art-div-light": "#F6EACB", "art-risk-ink": "#8C78C6", "art-risk-light": "#B9C1CE",
    # src/v2/pictures.js TOPIC_DOT and dotColor's fallback; src/v2/build.jsx the start screen's example dots
    "dot-value": "#4E9A72", "dot-div": "#C59A2E", "dot-earn": "#6E93CF", "dot-risk": "#8C78C6", "dot-disc": "#3E9A9A",
    "dot-none": "#5A6B87", "dot-plain": "#7C889C",
    # src/ui/tokens.js HOLDING_SHADES, and src/v2/report.jsx textOn's pick on each (white, navy or black: the first at 4.5:1)
    "shade-0": "#1C2B45", "shade-1": "#3D4B63", "shade-2": "#5A6B87", "shade-3": "#7C889C", "shade-4": "#9AA3B2", "shade-5": "#C9D0DB",
    "shade-text-0": "#FFFFFF", "shade-text-1": "#FFFFFF", "shade-text-2": "#FFFFFF", "shade-text-3": "#000000",
    "shade-text-4": "#1C2B45", "shade-text-5": "#1C2B45",
    # src/ui/tokens.js CHART.compare (HOLDING_SHADES[4]); src/v2/coart.jsx the value scale's grey end; src/v2/report.jsx 2022 bars
    "chart-compare": "#9AA3B2", "chart-scale-mid": "#E3E7EE", "chart-scale-end": "#B9C1CE", "chart-mine-est": "#5A6B87",
}


def rgba_of(c):
    """'#RRGGBB' or 'rgba(r, g, b, a)' → (r, g, b, a) so spacing and '0.10' vs '0.1' do not matter, the colour does."""
    if c.startswith("#"):
        return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + (1.0,)
    r, g, b, a = re.fullmatch(r"rgba\(([^)]*)\)", c.replace(" ", "")).group(1).split(",")
    return (int(r), int(g), int(b), float(a))


def test_every_light_value_is_the_v19_5b_value():
    """Round-1 review: not only COLOR — every light value (≈90 tokens) is the literal v19.5b drew, so the light screen stays as it was."""
    light = tokens()["P"]["light"]
    assert sorted(light) == sorted(LIGHT_V195B), (sorted(set(light) - set(LIGHT_V195B)), sorted(set(LIGHT_V195B) - set(light)))
    wrong = {k: (light[k], v) for k, v in LIGHT_V195B.items() if rgba_of(light[k]) != rgba_of(v)}
    assert not wrong, f"밝은 화면의 색이 v19.5b 와 달라요: {wrong}"
    assert len(LIGHT_V195B) >= 90


def test_light_values_are_unchanged_and_dark_values_follow_part_d():
    t = tokens()
    light, dark = t["P"]["light"], t["P"]["dark"]
    assert {k: light[k] for k in LIGHT_SPEC} == LIGHT_SPEC
    assert {k: dark[k] for k in DARK_SPEC} == DARK_SPEC
    assert dark["heroAlert"] == dark["watchBg"]                               # [Q14]
    assert t["ICON_TONE"] == {"on": {"line": "#1C2B45", "fill": "#CBD3DF"}, "off": {"line": "#6B7280", "fill": "#E3E6EB"},
                              "ok": {"line": "#1F7A4D", "fill": "#CDEBD9"}, "onNavy": {"line": "#FFFFFF", "fill": "#5A6B87"},
                              "earn": {"line": "#1C2B45", "fill": "#B9CDEB"}, "value": {"line": "#1C2B45", "fill": "#BFE0CC"},
                              "div": {"line": "#1C2B45", "fill": "#EBD49A"}, "risk": {"line": "#1C2B45", "fill": "#D3C8EC"},
                              "disc": {"line": "#1C2B45", "fill": "#B5DDDD"}}
    assert {k: (v["line"], v["fill"]) for k, v in t["ICON_TONE_DARK"].items()} == ICON_DARK_SPEC
    for tone in ICON_DARK_SPEC:
        assert light[f"icon-{tone}-line"] == t["ICON_TONE"][tone]["line"] and light[f"icon-{tone}-fill"] == t["ICON_TONE"][tone]["fill"]
        assert (dark[f"icon-{tone}-line"], dark[f"icon-{tone}-fill"]) == ICON_DARK_SPEC[tone]
    assert {k: light[f"chip-{k}"] for k in CHIP_DARK_SPEC} == {"earn": "#EAF1FB", "value": "#E9F5EE", "div": "#FBF4E1", "risk": "#F1EDF9", "disc": "#E6F4F4"}
    assert {k: dark[f"chip-{k}"] for k in CHIP_DARK_SPEC} == CHIP_DARK_SPEC
    assert t["ICON_CHIP"]["bg"] == t["COLOR"]["select"]                       # the default icon chip uses select
    assert [light[f"shade-{i}"] for i in range(6)] == SHADES_LIGHT and [dark[f"shade-{i}"] for i in range(6)] == SHADES_DARK_SPEC
    # chart colours: light as v19.3e (navy, slate), dark: this company in the light text colour
    assert t["CHART"]["mine"] == t["CHART"]["latest"] == t["COLOR"]["ink"] and t["CHART"]["earlier"] == t["CHART"]["compare"]
    assert light["chart-compare"] == "#9AA3B2" and dark["chart-compare"] == "#6F7B8E"
    assert t["MASCOT"] == "#F5F3EF" and t["THEME_COLOR"] == {"light": "#F5F3EF", "dark": "#10151E"}


def test_contrast_pairs_pass_in_both_palettes():
    t = tokens()
    pairs, (lr, dr) = t["PAIRS"], t["ratios"]
    assert len(pairs) >= 31
    low = [(m, f, b, round(r, 2)) for m, rs in (("light", lr), ("dark", dr)) for (f, b), r in zip(pairs, rs) if r < 4.5]
    assert not low, f"4.5:1 미달: {low}"
    # Part D's numbers (two decimals in the spec, rounded to one there)
    got = {(f, b): round(r, 1) for (f, b), r in zip(pairs, dr)}
    for pair, want in {("ink", "surface"): 13.5, ("ink", "page"): 15.4, ("text2", "surface"): 6.5, ("text3", "surface"): 5.5,
                       ("up", "surface"): 5.8, ("down", "surface"): 6.4, ("ok", "okBg"): 7.4, ("watch", "watchBg"): 7.8,
                       ("onPrimary", "primary"): 9.6, ("neutral", "neutralBg"): 8.7, ("apricotText", "surface"): 7.7,
                       ("ink", "heroAlert"): 11.0, ("text2", "heroAlert"): 5.3, ("apricotText", "heroAlert"): 6.3}.items():
        assert abs(got[pair] - want) <= 0.1, (pair, got[pair], want)
    d = t["P"]["dark"]
    for f, b, want in (("text3", "page", 6.4), ("text3", "select", 4.9), ("up", "page", 6.6)):
        assert abs(ratio(d[f], d[b]) - want) <= 0.1, (f, b)


def test_avoid_pairs_are_kept_per_palette():
    t = tokens()
    light, dark = t["P"]["light"], t["P"]["dark"]
    assert t["AVOID"] == [["up", "page"], ["text3", "page"], ["text3", "select"]]
    for f, b in t["AVOID"]:
        assert ratio(light[f], light[b]) < 4.5, (f, b)
    assert t["AVOID_DARK"], "어두운 화면의 쓰지 않는 조합이 없어요"
    for f, b in t["AVOID_DARK"]:
        assert ratio(dark[f], dark[b]) < 4.5 <= ratio(light[f], light[b]), (f, b)
    pairs = [tuple(p) for p in t["PAIRS"]]
    assert not set(pairs) & {tuple(p) for p in t["AVOID"] + t["AVOID_DARK"]}


def test_home_rules_band_tiles_read_in_both_palettes():
    """홈 남색 띠의 규칙 칸은 반투명이에요 (home2.jsx): 그 위의 글 (이름 onPrimary2 · 확인하지 못했어요 onPrimary3 · 깨진 규칙의 숫자
    highlight) 이 두 모드 모두 4.5:1 이상. '!' 동그라미의 글(watch)도 highlightBg 위에서."""
    src = read("src/v2/home2.jsx")
    hero = src.split("function HeroTile(", 1)[1].split("\nfunction ", 1)[0]
    m = re.search(r'background: broken \? "(rgba\([^"]+\))" : "(rgba\([^"]+\))"', hero)
    assert m, "규칙 칸 바탕을 찾지 못했어요"
    hi, plain = m.group(1), m.group(2)
    for mode, p in tokens()["P"].items():
        tile, hot = over(plain, p["primary"]), over(hi, p["primary"])
        for name, fg, bg in (("onPrimary2/tile", p["onPrimary2"], tile), ("onPrimary3/tile", p["onPrimary3"], tile),
                             ("onPrimary2/broken tile", p["onPrimary2"], hot), ("highlight/broken tile", p["highlight"], hot),
                             ("onPrimary/primary", p["onPrimary"], p["primary"]), ("watch/highlightBg", p["watch"], p["highlightBg"])):
            assert ratio(fg, bg) >= 4.5, (mode, name, round(ratio(fg, bg), 2))
    for tok in ("COLOR.onPrimary2", "COLOR.onPrimary3", "COLOR.highlight", "COLOR.highlightBg"):
        assert tok in hero, tok


def test_dark_icons_lines_read_on_their_fills_and_chips():
    t = tokens()
    for tone, v in t["ICON_TONE_DARK"].items():
        assert ratio(v["line"], v["fill"]) >= 3.0, (tone, round(ratio(v["line"], v["fill"]), 2))    # an icon is a graphic: WCAG 1.4.11
    for topic in CHIP_DARK_SPEC:                                              # Part D: line on the topic fill 5.7–7.6 : 1
        r = ratio(t["ICON_TONE_DARK"][topic]["line"], t["ICON_TONE_DARK"][topic]["fill"])
        assert 5.6 <= r <= 7.7, (topic, round(r, 2))
    d = t["P"]["dark"]
    for v in t["ICON_TONE_DARK"].values():                                    # no apricot, no price red or blue
        assert not {v["line"], v["fill"]} & {d["apricot"], d["apricotText"], d["up"], d["down"], d["upOnPage"]}


def test_holding_shades_and_their_text_in_both_palettes():
    t = tokens()
    for mode, p in t["P"].items():
        for i in range(6):
            assert ratio(p[f"shade-text-{i}"], p[f"shade-{i}"]) >= 4.5, (mode, i)
    v = node_value("src/ui/tokens.js", "[M.holdingShades([0.1, 0.5, 0.2]), M.holdingText(M.HOLDING_SHADES[3]), M.HOLDING_TEXT[3], M.holdingText('nope'), M.COLOR.ink]")
    assert v[0] == [t["HOLDING_SHADES"][2], t["HOLDING_SHADES"][0], t["HOLDING_SHADES"][1]] and v[1] == v[2] and v[3] == v[4]
    assert "holdingText(shade)" in read("src/v2/report.jsx")                   # the treemap's text follows the mode with its shade


def test_theme_css_switches_every_token_and_only_dark_puts_baepi_on_a_chip():
    t = tokens()
    css, light, dark = t["css"], t["P"]["light"], t["P"]["dark"]
    root = re.search(r":root\{([^}]*)\}", css).group(1)
    darkb = re.search(r':root\[data-theme="dark"\]\{([^}]*)\}', css).group(1)
    auto = re.search(r"@media \(prefers-color-scheme: dark\)\{:root:not\(\[data-theme\]\)\{([^}]*)\}", css).group(1)
    for k in light:
        assert f"--bs-{k}:{light[k]};" in root + ";" and f"--bs-{k}:{dark[k]};" in darkb + ";" and f"--bs-{k}:{dark[k]};" in auto + ";", k
    assert "color-scheme:light" in root and "color-scheme:dark" in darkb and "color-scheme:dark" in auto
    for tone in ICON_DARK_SPEC:
        assert f'svg[data-tone="{tone}"]>[data-layer="fill"]{{fill:var(--bs-icon-{tone}-fill)}}' in css
        assert f'svg[data-tone="{tone}"]>[data-layer="line"]{{fill:var(--bs-icon-{tone}-line)}}' in css
    chips = re.findall(r'([^{}]*)img\[src\*="baepi-"\]\{([^}]*)\}', css)
    assert len(chips) == 2 and all(sel.strip().endswith(('[data-theme="dark"]', ":root:not([data-theme])")) for sel, _ in chips), chips
    assert all(f"background:{t['MASCOT']}" in body and "filter" not in body for _, body in chips)
    assert "filter" not in css and "invert" not in css and "mix-blend" not in css                       # 뱁이 is never recoloured
    # round-1 review: placeholder text takes text3 in dark only (the browser's grey is 3.5:1 there); the light screen keeps it
    holders = re.findall(r'([^{}]*)::placeholder\{([^}]*)\}', css)
    assert len(holders) == 2 and all(sel.strip().endswith(('[data-theme="dark"]', ":root:not([data-theme])")) for sel, _ in holders), holders
    assert all(body == "color:var(--bs-text3);opacity:1" for _, body in holders)
    assert ratio(t["P"]["dark"]["text3"], t["P"]["dark"]["surface"]) >= 4.5 and ratio("#757575", t["P"]["dark"]["surface"]) < 4.5
    # round-2 review: the device-setting fallback (no data-theme: the head script never ran) applies only on a dark device, so its
    # rules — the dark values, the 뱁이 chip, the placeholder colour — sit inside @media (prefers-color-scheme: dark); the rules for
    # the chosen dark mode sit outside it. Moved the other way, a light device without the script would get the chip.
    media, outside = media_split(css, "@media (prefers-color-scheme: dark)")
    auto_rules = [(sel, body) for sel, body in rules_of(media)]
    assert [sel for sel, _ in auto_rules] == [':root:not([data-theme])', ':root:not([data-theme]) img[src*="baepi-"]',
                                              ':root:not([data-theme]) img[src*="baepi-mark"]', ':root:not([data-theme]) ::placeholder'], auto_rules
    out_rules = rules_of(outside)
    assert not [sel for sel, _ in out_rules if ":not([data-theme])" in sel], out_rules
    dark_sels = [sel for sel, _ in out_rules if sel.startswith(':root[data-theme="dark"]')]
    assert dark_sels == [':root[data-theme="dark"]', ':root[data-theme="dark"] img[src*="baepi-"]',
                         ':root[data-theme="dark"] img[src*="baepi-mark"]', ':root[data-theme="dark"] ::placeholder'], dark_sels
    assert [sel for sel, _ in out_rules if "baepi" in sel or "placeholder" in sel] == dark_sels[1:]


def media_split(css, at):
    """(the text inside the one `at{...}` block, the css without it). Braces counted, so nested rules stay inside."""
    assert css.count(at + "{") == 1, at
    i = css.index(at + "{") + len(at) + 1
    depth, j = 1, i
    while depth:
        depth += {"{": 1, "}": -1}.get(css[j], 0)
        j += 1
    return css[i:j - 1], css[:i - len(at) - 1] + css[j:]


def rules_of(css):
    """[(selector, body)] of plain rules (no @ blocks inside)."""
    assert "@" not in css, css[:80]
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def test_media_split_catches_a_rule_moved_out_of_the_media_block():
    css = tokens()["css"]
    chip = ':root:not([data-theme]) img[src*="baepi-"]{'
    body = css.split(chip, 1)[1].split("}", 1)[0]
    moved = css.replace(chip + body + "}", "", 1) + chip + body + "}"             # the reviewer's mutation: the chip rule after the block
    media, outside = media_split(moved, "@media (prefers-color-scheme: dark)")
    assert any(":not([data-theme])" in sel for sel, _ in rules_of(outside))
    assert chip[:-1] not in [sel for sel, _ in rules_of(media)]


# ── no fixed colour left in 2.0 ──
# (file, literal) → how many times and why it stays. Everything else is a token (src/ui/tokens.js).
ALLOWED = {
    # the coloured letter marks behind company logos (v19.3a): the same in both modes (Part D: "letter marks unchanged")
    **{("src/v2/company.js", c): (1, "letter mark colour") for c in ("#1C2B45", "#2F5D62", "#3D5A3C", "#5B4A8B", "#6B4E3D", "#46536B",
                                                                     "#7A3E5D", "#355C7D", "#5E5A2E", "#4B3F72")},
    ("src/v2/logo.jsx", "#FFFFFF"): (2, "logos stay on their white tile; the letter on a letter mark is white (Part D)"),
    ("src/v2/home2.jsx", "rgba(255,255,255,.08)"): (1, "the rules band's tile: a light veil over the navy band, the same in both modes (Home2Dark)"),
    ("src/v2/home2.jsx", "rgba(255,226,168,.18)"): (1, "a broken rule's tile: a warm veil over the navy band, the same in both modes (Home2Dark)"),
    ("src/v2/guide.jsx", "rgba(255, 226, 168, 0.45)"): (1, "the first-visit ring's pulse: the highlight colour at 45%, the same in both modes"),
    ("src/v2/guide.jsx", "rgba(255, 226, 168, 0.25)"): (1, "the same pulse at 25%"),
}
# the 기준 cards' small pictures, copied from the approved board element by element: BuildCards2Dark keeps their colours (pictures)
ALLOWED_FILES = {"src/v2/cardart.js": "board art (BuildCards2 / BuildCards2Dark), like a picture",
                 "src/ui/tokens.js": "where the colours live", "src/ui/phosphor.js": "icon path data (no colours)"}
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}(?![0-9a-zA-Z_])|\b(?:rgba?|hsla?)\([^)]*\)", re.I)
# named colours; transparent and currentColor are not a colour of their own (they are the same in both modes)
NAMED = re.compile(r"""["'`](?:white|black|red|blue|green|gray|grey|silver|navy|orange|yellow|purple|pink|brown|beige|ivory|gold)["'`]""", re.I)


# Hex digits glued to a token, as an alpha suffix: `${COLOR.surface}00`, COLOR.surface + "cc", `${COLOR.x}` + "cc", (COLOR.x) + "cc",
# `${COLOR.x}${"cc"}`, COLOR.x.concat("cc"). A token is a CSS variable, so this makes an invalid colour (and it was a fixed alpha
# anyway): use transparent, or a token of its own.
_HEX2 = r"""["'`]\s*[0-9a-fA-F]{2}(?:[0-9a-fA-F]{2})?\s*["'`]"""
SUFFIX = re.compile("|".join([
    r"\$\{[^{}]*\}[0-9a-fA-F]{2}(?:[0-9a-fA-F]{2})?(?![0-9a-zA-Z_])",       # `${COLOR.x}cc`
    r"\$\{[^{}]*\}\$\{\s*" + _HEX2 + r"\s*\}",                              # `${COLOR.x}${"cc"}`
    r"[\w.\])`]\s*\+\s*" + _HEX2,                                            # COLOR.x + "cc", (COLOR.x) + "cc", `${COLOR.x}` + "cc"
    r"\.concat\(\s*" + _HEX2,                                                  # COLOR.x.concat("cc")
]))


def v2_sources():
    out = []
    for d in ("src/v2", "src/ui"):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith((".js", ".jsx")):
                out.append(f"{d}/{f}")
    return out


def minified(path):
    return esbuild(path, "--minify-whitespace", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8")


def colour_hits(sources):
    """{파일: 코드} → 허락되지 않은 고정 색 [(파일, 색)] 과 허락된 것의 셈."""
    bad, seen = [], {}
    for f, code in sources.items():
        if f in ALLOWED_FILES:
            continue
        hits = COLOUR.findall(code) + [m.strip("\"'`") for m in NAMED.findall(code)] + SUFFIX.findall(code)
        for h in hits:
            key = (f, h)
            if key in ALLOWED:
                seen[key] = seen.get(key, 0) + 1
            else:
                bad.append(key)
    return bad, seen


def test_no_fixed_colour_in_2_0_source_outside_the_allow_list():
    files = v2_sources()
    assert len(files) >= 50 and "src/v2/theme.js" in files and "src/ui/components.jsx" in files
    bad, seen = colour_hits({f: minified(f) for f in files})                 # comments drop out
    assert not bad, f"고정된 색 (src/ui/tokens.js 의 토큰으로): {bad[:8]}"
    wrong = {k: (seen.get(k, 0), n) for k, (n, _) in ALLOWED.items() if seen.get(k, 0) != n}
    assert not wrong, f"허락 목록과 실제 쓰임 수가 달라요 (없어졌으면 목록에서도 지워요): {wrong}"
    # the page template: its style uses the tokens; the one fixed colour is the theme-color meta's first value (the light page),
    # which the head script replaces before the first paint
    tpl = read("src/v2/template.html")
    left = [c for c in COLOUR.findall(tpl)]
    assert left == ["#F5F3EF"] and '<meta name="theme-color" content="#F5F3EF">' in tpl, left
    assert "background: var(--bs-page); color: var(--bs-ink);" in tpl and "outline: 2px solid var(--bs-ink);" in tpl


def test_the_colour_check_catches_fixed_colours():
    real = {"src/v2/today.jsx": minified("src/v2/today.jsx")}
    assert colour_hits(real)[0] == []
    for bad in ['style={{ color: "#1C2B45" }}', "background: 'rgba(28,43,69,0.45)'", "fill: '#fff'", 'color: "white"',
                "boxShadow: `0 0 0 1px hsl(0 0% 50%)`", "background: 'rgb(255 255 255)'",
                "background: `linear-gradient(to right, ${COLOR.surface}00, ${COLOR.surface})`", "color: `${A.ink}cc`",
                "background: COLOR.surface + 'cc'", 'border: `1px solid ${COLOR.ink}80`',
                'color: `${COLOR.ink}` + "cc"', 'color: (COLOR.ink) + "cc"', 'color: `${COLOR.ink}${"cc"}`', 'color: COLOR.ink.concat("cc")',
                "color: (COLOR.ink)+'80cc'", 'color: COLOR.ink.concat( "80" )']:
        assert colour_hits({"src/v2/today.jsx": real["src/v2/today.jsx"] + bad})[0], bad
    for ok in ["location.hash = '#portfolio'", "x.t + '#1'", "COLOR.ink", 'background: "transparent"', "borderColor: 'currentColor'",
               "`${SPACE(2)}px ${SPACE(3)}px`", "`${n}px`", "`linear-gradient(${COLOR.surface}, transparent)`", "`${p1(x)}%`"]:
        assert not colour_hits({"src/v2/x.jsx": ok})[0], ok
    # an allowed literal in another file is caught too
    assert colour_hits({"src/v2/today.jsx": 'color: "#FFFFFF"'})[0] == [("src/v2/today.jsx", "#FFFFFF")]


# ── the head script: the mode before the first paint ──
HARNESS = r"""
const SRC = process.argv[1];
const cases = JSON.parse(process.argv[2]);
const out = {};
for (const [name, c] of Object.entries(cases)) {
  const attrs = {};
  const meta = { content: '#F5F3EF', setAttribute(k, v) { this[k] = v; } };
  const document = { documentElement: { setAttribute: (k, v) => { attrs[k] = v; }, style: {} },
                     querySelector: (s) => (s === 'meta[name="theme-color"]' && !c.noMeta ? meta : null) };
  const window = {};
  Object.defineProperty(window, 'localStorage', { get() { if (c.storage === 'throw') throw new Error('denied');
    return { getItem: (k) => { if (c.storage === 'getThrows') throw new Error('blocked'); return k === 'baepsae-theme' && c.storage != null ? c.storage : null; } }; } });
  if (c.device !== 'none') window.matchMedia = (q) => { if (c.device === 'throw') throw new Error('x'); return { matches: q === '(prefers-color-scheme: dark)' && c.device === 'dark' }; };
  new Function('window', 'document', SRC)(window, document);
  out[name] = [attrs['data-theme'], attrs['data-theme-mode'], meta.content];
}
console.log(JSON.stringify(out));
"""


def head_script(html):
    """The head's own small script (the app bundle further down carries the same function, minified)."""
    head = html.split("</head>", 1)[0]
    found = [s for s in re.findall(r"<script>(.*?)</script>", head, flags=re.S) if "baepsae-theme" in s and "data-theme" in s]
    assert len(found) == 1 and found[0].startswith("(function bootTheme("), len(found)
    return found[0]


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_head_script_picks_the_mode_before_the_first_paint():
    cases = {"none-light": {"storage": None, "device": "light"}, "none-dark": {"storage": None, "device": "dark"},
             "auto-dark": {"storage": "auto", "device": "dark"}, "light-on-dark": {"storage": "light", "device": "dark"},
             "dark-on-light": {"storage": "dark", "device": "light"}, "junk": {"storage": "purple", "device": "dark"},
             "blocked": {"storage": "throw", "device": "dark"}, "getThrows": {"storage": "getThrows", "device": "light"},
             "noMatchMedia": {"storage": None, "device": "none"}, "mmThrows": {"storage": None, "device": "throw"},
             "dark-noMedia": {"storage": "dark", "device": "none"}, "noMeta": {"storage": "dark", "device": "light", "noMeta": True}}
    want = {"none-light": ["light", "auto", "#F5F3EF"], "none-dark": ["dark", "auto", "#10151E"], "auto-dark": ["dark", "auto", "#10151E"],
            "light-on-dark": ["light", "light", "#F5F3EF"], "dark-on-light": ["dark", "dark", "#10151E"], "junk": ["dark", "auto", "#10151E"],
            "blocked": ["dark", "auto", "#10151E"], "getThrows": ["light", "auto", "#F5F3EF"], "noMatchMedia": ["light", "auto", "#F5F3EF"],
            "mmThrows": ["light", "auto", "#F5F3EF"], "dark-noMedia": ["dark", "dark", "#10151E"], "noMeta": ["dark", "dark", "#F5F3EF"]}
    for page in ("app.html", "app-preview.html"):
        src = head_script(built(page))
        r = subprocess.run([NODE, "-e", HARNESS, src, json.dumps(cases)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout) == want, (page, r.stdout)


def test_head_script_and_colour_sheet_come_before_anything_is_drawn():
    # the way build-app.sh makes them (the same esbuild options: whitespace removed, nothing renamed)
    code = esbuild("src/v2/theme.js", "--bundle", "--format=cjs", "--platform=node", "--charset=utf8", "--minify-whitespace")
    r = subprocess.run(["node", "-e", "const module = { exports: {} };" + code + "\nconst t = module.exports;"
                        "process.stdout.write(JSON.stringify([t.themeHeadScript(), t.themeCss()]));"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stderr
    js, css = json.loads(r.stdout)
    assert "build-app.sh" in read("src/v2/theme.js") and "--minify-whitespace" in read("build-app.sh")
    for page in ("app.html", "app-preview.html"):
        html = built(page)
        head = html.split("</head>", 1)[0]
        assert head_script(html) == js and f"<script>{js}</script>" in head      # the same function the app runs (theme.js bootTheme)
        assert head.index('<meta name="theme-color"') < head.index(js) < head.index("<style>")
        assert head.count(css) == 1 and head.index(css) > head.index("<style>")
        assert head.count('<meta name="theme-color"') == 1 and "<body" not in head
    assert read("app.html") == built("app.html")


def test_any_csp_on_app_html_allows_the_head_script():
    """v19.3 Part O: inline scripts are allowed by their hash. app.html has no CSP yet (it comes with v19.4); once it has one, the
    head script's hash must be in its script-src, or the browser would block the mode (and fall back to the device setting)."""
    for page in ("app.html", "app-preview.html"):
        html = built(page)
        h = "'sha256-" + base64.b64encode(hashlib.sha256(head_script(html).encode("utf-8")).digest()).decode() + "'"
        for csp in csp_metas(html):
            script_src = next((d for d in csp.split(";") if d.strip().startswith("script-src")), "")
            assert h in script_src or "'unsafe-inline'" in script_src, (page, script_src)


def csp_metas(html):
    """The content of every <meta http-equiv="Content-Security-Policy"> tag, whatever the attribute order or quote style (double,
    single or none)."""
    out = []
    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.I):
        attrs = {}
        for m in re.finditer(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""", tag):
            attrs[m.group(1).lower()] = next(v for v in m.groups()[1:] if v is not None)
        if attrs.get("http-equiv", "").lower() == "content-security-policy":
            out.append(attrs.get("content", ""))
    return out


def test_csp_reader_finds_any_spelling():
    h = "'sha256-abc='"
    for tag in (f'<meta http-equiv="Content-Security-Policy" content="script-src {h}">', f"<meta content=\"script-src {h}\" http-equiv='content-security-policy'>",
                f"<META HTTP-EQUIV='Content-Security-Policy' CONTENT=\"default-src 'self'; script-src {h}\">",
                f"<meta http-equiv=Content-Security-Policy content=\"script-src {h}\">",
                f"<meta content=\"script-src {h}\" http-equiv=content-security-policy>"):
        assert [c for c in csp_metas("<head>" + tag + "</head>") if h in c], tag
    assert csp_metas('<meta name="theme-color" content="#F5F3EF">') == [] and csp_metas("<meta name=theme-color content=#F5F3EF>") == []
    assert csp_metas("<meta http-equiv=Content-Security-Policy content=script-src>") == ["script-src"]


def test_mode_choice_is_its_own_key_and_never_part_of_the_records():
    v = node_value("src/v2/theme.js", "{ key: M.THEME_KEY, modes: M.MODES }")
    store = node_value("src/v2/store.js", "{ a: M.STORE_KEY, b: M.PREVIEW_STORE_KEY }")
    assert v == {"key": "baepsae-theme", "modes": ["auto", "light", "dark"]}
    assert not any(v["key"].startswith(k) or k.startswith(v["key"]) for k in store.values())
    for f in ("src/v2/store.js", "src/v2/app.jsx", "src/v2/import.jsx"):
        assert "THEME_KEY" not in read(f) and "baepsae-theme" not in read(f), f
    theme = read("src/v2/theme.js")
    assert "STORE_KEY" not in theme and "exportText" not in theme
    assert theme.count("localStorage.setItem(") == 1 and theme.count("localStorage.removeItem(") == 1 and "sessionStorage" not in theme


def test_mode_switch_text_is_the_approved_text():
    v = node_value("src/copy/v2.js", "M.C.menu.mode")
    assert v == {"title": "화면 모드", "auto": "자동", "light": "밝게", "dark": "어둡게", "hint": "자동은 기기 설정을 따라요."}
    spec = read("docs/tasks/v19.6-records-alerts-dark.md").split("| **어두운 화면** | |", 1)[1]
    assert "| menu | 화면 모드 · 자동 · 밝게 · 어둡게 |" in spec and "| hint | 자동은 기기 설정을 따라요. |" in spec
    nav = read("src/v2/nav.jsx")
    assert nav.count("<ThemeSwitch theme={theme}") == 2                       # the ☰ menu and the PC left menu


def test_claude_md_has_the_dark_mode_rule():
    assert ("- Dark mode: 2.0 only, with the tokens in v19.6 Part D. Icon lines turn light (`#E8ECF2`) on darker topic fills. 뱁이 is\n"
            "  never recoloured and sits on a light chip in dark mode.") in read("CLAUDE.md")


def test_old_app_and_share_card_stay_as_they_are():
    """Part D: 2.0 only. The old app (baepsae.html), its template and the share card have no theme sheet or switch."""
    for f in ("template.html", "baepsae.html", "src/sharecard.js", "manifest.webmanifest"):
        body = read(f)
        assert "--bs-" not in body and "data-theme" not in body and "baepsae-theme" not in body, f


def test_screen_check_catches_light_icons_and_a_bare_baepi_on_the_dark_screen():
    """tests/visualcheck.py (smoke_v2 · smoke_preview · smoke_launch): on the dark screen the painted icon colours must be the dark
    table and every 뱁이 picture must sit on the light chip; on the light screen the painted colours are the light table and there
    is no chip."""
    import visualcheck as V
    base = {"badImg": [], "verdictImg": [], "placements": [], "icons": [["check", True, "#CBD3DF", "#1C2B45"]], "styles": []}
    dark_ok = {**base, "theme": "dark", "painted": [["check", V._rgb("#4A5872"), V._rgb("#E8ECF2")]],
               "mascotChip": [["baepi-mark.webp", "rgb(245, 243, 239)"]]}
    light_ok = {**base, "theme": "light", "painted": [["check", V._rgb("#CBD3DF"), V._rgb("#1C2B45")]], "mascotChip": [["baepi-mark.webp", "rgba(0, 0, 0, 0)"]]}
    assert V.visual_problems(dark_ok) == [] and V.visual_problems(light_ok) == []
    kinds = lambda v: [b[0] for b in V.visual_problems(v)]                    # noqa: E731
    assert kinds({**dark_ok, "painted": light_ok["painted"]}) == ["그려진 아이콘 색이 dark 표가 아니에요"]
    assert kinds({**light_ok, "painted": dark_ok["painted"]}) == ["그려진 아이콘 색이 light 표가 아니에요"]
    assert kinds({**dark_ok, "mascotChip": [["baepi-20-error.webp", "rgba(0, 0, 0, 0)"]]}) == ["뱁이 칩 (어두운 화면에서만 밝은 칩)"]
    assert kinds({**light_ok, "mascotChip": [["baepi-20-error.webp", "rgb(245, 243, 239)"]]}) == ["뱁이 칩 (어두운 화면에서만 밝은 칩)"]
    assert kinds({**dark_ok, "styles": [["SPAN pill", "rgb(224, 142, 106) | x"]]}) == ["살구색"]   # the dark apricot is caught too
    assert len(V.ICON_PAIRS_DARK) == len(V.ICON_PAIRS) == 9
    assert {(f, l) for f, l in V.ICON_PAIRS_DARK} == {(v[1], v[0]) for v in ICON_DARK_SPEC.values()}
