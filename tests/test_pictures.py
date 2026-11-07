# -*- coding: utf-8 -*-
"""v19.3b: 기준 · 템플릿 그림, 12px 글 크기, 그래프 색 (docs/tasks/v19.3-portfolio-pictures-accounts.md Part A · B · C · N.2).

Part A — 그림
- pictures/ 의 그림은 docs/design/v19.3/assets/pictures 의 원본을 tools/resize_pictures.py 가 줄인 것뿐이에요: 크기는 그 표의 크기
  (보드에서 가장 크게 보이는 크기 × 2), 원본보다 크지 않고, Adobe 그림은 192 px 이하, 합계 400 KB 아래, 투명 배경 WebP.
- Fluent 그림 옆에 MIT 라이선스 글(Microsoft 의 저작권 표시)이 있어요.
- 기준(engine.js CARDS) 열 개와 보이는 템플릿(DECKS, hidden 아님) 여덟 개마다 그림이 하나씩, README 의 주제 색 그대로예요.
- 서비스워커가 그림을 모두 미리 받아 둬요 (오프라인). 2.0 코드는 docs/ 의 파일을 쓰지 않아요 (그림은 앱 폴더에서만).
- 데이터 출처(예전 뱁새 src/info.jsx)의 그림 · 로고 출처에 승인된 그림 줄과 라이선스 글로 가는 링크가 있어요.
Part B — 2.0 코드에 12px 아래 글자 크기가 없어요 (화면 검사는 tests/visualcheck.py text_floor, 여기서는 그 검사가 정말 잡는지도).
Part C — 종목 색은 남색 여섯 단계(비중 순), 로고 색(MARK_COLORS)은 회사 표시에만.
"""
import glob
import json
import os
import re
import shutil
import subprocess

import pytest

from copytrace import ROOT, read

NODE = shutil.which("node")
PIC = os.path.join(ROOT, "pictures")
SRC = os.path.join(ROOT, "docs", "design", "v19.3", "assets", "pictures")
LICENSE = os.path.join(PIC, "LICENSE-fluent-emoji.txt")

# README (docs/design/v19.3/README.md) 의 표: 기준 → 그림 · 주제 색, 템플릿 → 그림 (주제 색은 보드 BuildStart2 · VisualKit)
CARD_TABLE = {"value": ("fluent-label", "value"), "div": ("adobe-coins", "div"), "divGrowth": ("adobe-arrows-coins", "div"),
              "growth": ("adobe-tree", "earn"), "profit": ("adobe-profit", "earn"), "stable": ("adobe-safe", "risk"),
              "lowVol": ("fluent-turtle", "risk"), "trend": ("adobe-chart", "disc"), "payout": ("adobe-gift", "div"),
              "large": ("adobe-bank", "disc")}
DECK_TABLE = {"deepValue": ("fluent-magnifying-glass-tilted-left", "value"), "garp": ("fluent-balance-scale", "earn"),
              "quality": ("fluent-deciduous-tree", "earn"), "strict": ("fluent-gem-stone", None), "lowVol": ("fluent-umbrella", "risk"),
              "trend": ("fluent-sailboat", "disc"), "krUs": ("fluent-globe-showing-asia-australia", "disc"),
              "income": ("fluent-shopping-cart", "div")}
TOPIC_CHIP = {"value": "#E9F5EE", "div": "#FBF4E1", "earn": "#EAF1FB", "risk": "#F1EDF9", "disc": "#E6F4F4"}   # CLAUDE.md 칩 바탕


def esbuild_iife(entry):
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    assert os.path.exists(exe), "node_modules 가 없어요: npm ci 를 먼저 하세요"
    r = subprocess.run([exe, entry, "--bundle", "--format=iife", "--global-name=M", "--loader:.js=jsx", "--jsx=automatic",
                        "--external:react", "--external:react/jsx-runtime", "--charset=utf8", "--platform=node"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def node_value(entry, expr):
    r = subprocess.run([NODE, "-e", esbuild_iife(entry) + f"\nprocess.stdout.write(JSON.stringify({expr}));"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def resize_targets():
    """tools/resize_pictures.py 의 표 {원본 이름: 보이는 크기 px} (그 파일을 실행하지 않고 읽어요)."""
    src = read("tools/resize_pictures.py")
    consts = {k: int(v) for k, v in re.findall(r"^(\w+) = \((\d+), ", src, flags=re.M)}
    table = src.split("TARGETS = {", 1)[1].split("\n}\n", 1)[0]
    out = {name: consts[c] for name, c in re.findall(r'"([\w-]+\.png)": (\w+)', table)}
    assert len(out) == 19, out
    return out


def webps():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(PIC, "*.webp")))


# ── Part A ──

def test_pictures_are_resized_copies_within_the_licence_and_size_limits():
    from PIL import Image
    targets = resize_targets()
    assert webps() == sorted(n[:-4] + ".webp" for n in targets), "pictures/ 와 tools/resize_pictures.py 의 표가 달라요"
    assert sorted(os.listdir(PIC)) == sorted(webps() + ["LICENSE-fluent-emoji.txt"]), sorted(os.listdir(PIC))   # 다른 파일 없음
    total = 0
    for name, shown in targets.items():
        out = os.path.join(PIC, name[:-4] + ".webp")
        src = Image.open(os.path.join(SRC, name))
        im = Image.open(out)
        assert im.format == "WEBP" and im.mode == "RGBA", (name, im.format, im.mode)        # 투명 배경 그대로
        assert max(im.size) == 2 * shown, (name, im.size, shown)                           # 가장 크게 보이는 크기의 2배
        assert im.size[0] * src.size[1] == im.size[1] * src.size[0], (name, im.size, src.size)   # 비율 그대로
        assert max(im.size) <= max(src.size), (name, im.size, src.size)                    # 원본보다 크지 않아요
        if name.startswith("adobe-"):
            assert max(im.size) <= 192 and max(src.size) <= 192, name                      # LICENSES.md: 192 px 넘는 Adobe 파일 없음
        total += os.path.getsize(out)
    assert total < 400 * 1024, total
    for p in glob.glob(os.path.join(ROOT, "**", "adobe-*"), recursive=True):              # 저장소 어디에도 더 큰 Adobe 파일이 없어요
        if "node_modules" in p or not p.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
            continue
        assert max(Image.open(p).size) <= 192, p


def test_fluent_licence_ships_next_to_the_fluent_pictures():
    lic = read("pictures/LICENSE-fluent-emoji.txt")
    for need in ("MIT License", "Copyright (c) Microsoft Corporation.", "Permission is hereby granted, free of charge",
                 "The above copyright notice and this permission notice shall be included in all",
                 'THE SOFTWARE IS PROVIDED "AS IS"', "https://github.com/microsoft/fluentui-emoji"):
        assert need in lic, need
    assert any(n.startswith("fluent-") for n in webps())


def test_every_criterion_and_visible_template_has_its_picture_on_its_tint():
    v = node_value("src/v2/pictures.js", "{ cards: M.CARD_PICS, decks: M.DECK_PICS, start: M.START_PICS, sizes: M.PIC_SIZES }")
    eng = node_value("src/v2/engine.js", "{ cards: M.CARDS.map((c) => c.id), decks: M.DECKS.filter((d) => !d.hidden).map((d) => d.id) }")
    assert sorted(v["cards"]) == sorted(eng["cards"]) == sorted(CARD_TABLE)             # 기준마다 하나
    assert sorted(v["decks"]) == sorted(eng["decks"]) == sorted(DECK_TABLE)             # 보이는 템플릿마다 하나
    for k, (pic, topic) in CARD_TABLE.items():
        assert v["cards"][k] == {"src": f"pictures/{pic}.webp", "topic": topic}, k
    for k, (pic, topic) in DECK_TABLE.items():
        assert v["decks"][k] == {"src": f"pictures/{pic}.webp", "topic": topic}, k
    assert v["start"] == {"holdings": {"src": "pictures/adobe-wallet.webp", "topic": None}}
    used = {x["src"] for grp in (v["cards"], v["decks"], v["start"]) for x in grp.values()}
    assert used == {f"pictures/{n}" for n in webps()}, "쓰지 않는 그림이 있거나, 없는 그림을 불러요"
    assert len({x["src"] for x in v["cards"].values()}) == 10                            # 기준마다 다른 그림
    tok = node_value("src/ui/tokens.js", "M.TOPIC_CHIP")
    assert tok == TOPIC_CHIP
    # 칩 · 그림 크기는 보드의 격자 (그림이 칩 가운데, 칩보다 작아요)
    assert v["sizes"] == {"row": {"chip": 32, "pic": 24}, "fit": {"chip": 40, "pic": 28}, "card": {"chip": 48, "pic": 32},
                          "deck": {"chip": 52, "pic": 36}}
    assert all(z["pic"] >= 24 and z["pic"] < z["chip"] for z in v["sizes"].values())          # 24 px 아래는 흐려요 (Part A)
    ui = read("src/v2/ui.jsx")
    chip = ui.split("export function PicChip(", 1)[1].split("\n}\n", 1)[0]
    assert 'alt=""' in chip and "TOPIC_CHIP[pic.topic]" in chip and "ICON_CHIP.radius" in chip
    assert "filter" not in chip and "grayscale" not in chip and "mixBlendMode" not in chip     # 그림의 색은 바꾸지 않아요


def test_criteria_screens_use_the_pictures():
    """기준이 나오는 화면 코드마다 그림: 기준 카드 · 미리 보기 · 템플릿 (build.jsx), 후보와 근거 수치 (pick.jsx), 매수 계획의 이유
    (plan.jsx), 회사 페이지의 내 기준과 맞는 정도 (company.jsx). 이름만 쓰는 곳(C.build.cards[..].name)은 그림과 같이 있어요."""
    for f, needs in {"src/v2/build.jsx": ['<CardPic id={c.id} size="fit" dim={!!c.pending}', "<CardScores list={[[b.id, b.score]]}",
                                          '<DeckPic id={id} size="deck" />', "<Option key={d.id} id={d.id} pic "],
                     "src/v2/pick.jsx": ["<CardScores list={ranked} />", "<Row key={x.id} card={x.id} k={C.build.cards[x.id].name}"],
                     "src/v2/plan.jsx": ["<CardScores list={b} />"],
                     "src/v2/company.jsx": ['<CardPic id={id} size="fit" />']}.items():
        src = read(f)
        for n in needs:
            assert n in src, (f, n)


SW_HARNESS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const listeners = {}; const opened = []; let added = null;
const self = { addEventListener: (t, f) => { listeners[t] = f; }, location: { origin: 'https://jack.example' }, skipWaiting() {},
  clients: { claim: async () => {} } };
const caches = { open: async (n) => { opened.push(n); return { addAll: async (l) => { added = l; }, put: async () => {} }; },
  keys: async () => [], delete: async () => true, match: async () => undefined };
new Function('self', 'caches', 'fetch', 'Response', 'URL', 'console', src)(self, caches, async () => { throw new Error('x'); }, {}, URL, console);
let wait = null;
listeners.install({ waitUntil: (p) => { wait = p; } });
(async () => { await wait; console.log(JSON.stringify({ opened, added })); })();
"""


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_service_worker_precaches_every_picture_in_its_one_cache():
    r = subprocess.run([NODE, "-e", SW_HARNESS, os.path.join(ROOT, "sw.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["opened"] == ["baepsae-v19-cv"]                                       # 캐시는 하나 그대로 (tests/test_sw.py)
    assert sorted(got["added"]) == sorted(f"./pictures/{n}" for n in webps()), got["added"]
    sw = read("sw.js")
    assert ".catch((err) => console.warn(" in sw.split('self.addEventListener("install"', 1)[1].split("});", 1)[0]   # 실패해도 설치는 돼요 (크게 남겨요)


def test_pictures_come_only_from_the_app_folder():
    """docs/ 는 사이트에 올리지 않아요 (Adobe 그림 라이선스): 2.0 코드 · 빌드한 두 페이지는 docs/ 의 파일을 부르지 않아요."""
    for f in sorted(glob.glob(os.path.join(ROOT, "src", "v2", "*"))) + [os.path.join(ROOT, "src", "ui", "components.jsx"), os.path.join(ROOT, "sw.js")]:
        body = open(f, encoding="utf-8").read()
        assert "docs/" not in re.sub(r"//.*", "", body) and "_blob" not in body, f
    for page in ("app.html", "app-preview.html"):
        html = read(page)
        assert "docs/design" not in html, page
        assert all(f"pictures/{n}" in html for n in webps() if not n.startswith("adobe-wallet")), page   # 지갑 그림은 v19.3c 부터
    assert "docs" in read("tools/assemble_site.py") and 'EXCLUDED_DIR = "docs"' in read("tools/assemble_site.py")


def test_picture_credit_on_the_sources_page():
    """데이터 출처 (예전 뱁새 src/info.jsx; 2.0 의 메뉴가 열어요): Part A · Appendix 1 에서 승인된 그림 줄, "MIT 라이선스"는 우리가 둔
    라이선스 글로 가는 링크 (Part O.7). 로고 줄은 그대로예요 (tests/test_v2_logos.py)."""
    src = read("src/info.jsx")
    card = src.split('<Card id="info-sources">', 1)[1].split("</Card>", 1)[0]
    line = ('기준 카드와 템플릿 그림: Adobe Stock, Microsoft Fluent Emoji (<a href="./pictures/LICENSE-fluent-emoji.txt" target="_blank" '
            'rel="noopener noreferrer" style={{ color: C.blue, fontWeight: 800 }}>MIT 라이선스</a>)')
    assert card.count(line) == 1
    assert card.index(line) < card.index("회사 로고: Logo.dev.")                            # 그림 줄 다음에 로고 줄
    old = read("baepsae.html")
    for text in ("기준 카드와 템플릿 그림: Adobe Stock, Microsoft Fluent Emoji (", "MIT 라이선스", 'href:"./pictures/LICENSE-fluent-emoji.txt"'):
        assert old.count(text) == 1, text
    assert os.path.isfile(LICENSE)


# ── Part B ──

UI_FILES = sorted(glob.glob(os.path.join(ROOT, "src", "v2", "*.jsx"))) + [os.path.join(ROOT, "src", "ui", "components.jsx")]


def test_no_font_size_under_12px_in_2_0_code():
    """2.0 화면 코드: 숫자로 쓴 글자 크기는 12 이상, SIZE 는 12 가 가장 작고, 단위(0.6em)도 12px 아래로 줄지 않아요.
    12px(SIZE.xxs)은 12px 아래였던 줄만 써요 (Part B: 10.5~11.5 → 12, 12~12.5 → 13)."""
    size = node_value("src/ui/tokens.js", "M.SIZE")
    assert min(size.values()) == 12 and size["xxs"] == 12 and size["xs"] == 13
    for f in UI_FILES:
        src = re.sub(r"//.*", "", open(f, encoding="utf-8").read())
        rel = os.path.relpath(f, ROOT)
        lits = [float(x) for x in re.findall(r"\b(?:tx|T)\(\s*(\d+(?:\.\d+)?)\s*,", src)]
        lits += [float(x) for x in re.findall(r"fontSize:\s*(\d+(?:\.\d+)?)\b", src)]
        assert all(x >= 12 for x in lits), (rel, lits)
        assert not re.search(r"fontSize:\s*\"(?!max\(12px,)[^\"]*em\"", src), rel             # em 크기는 max(12px, …) 로만
        assert not re.search(r"font-?[sS]ize=", src), rel                                       # SVG 글 크기 속성 없음
    xxs = {os.path.relpath(f, ROOT): len(re.findall(r"SIZE\.xxs\b", open(f, encoding="utf-8").read())) for f in UI_FILES}
    assert {k: v for k, v in xxs.items() if v} == {"src/v2/cotabs.jsx": 1}, xxs              # 10px 이던 '그때 → 지금' 줄 하나
    comp = read("src/ui/components.jsx")
    assert 'data-unit="1" style={{ fontSize: "max(12px, 0.6em)"' in comp


# ── Part C ──

def test_holding_shades_are_navy_by_weight_rank():
    v = node_value("src/ui/tokens.js", "{ shades: M.HOLDING_SHADES, one: [0, 1, 5, 6, 9, -1].map(M.holdingShade),"
                   " a: M.holdingShades([0.1, 0.3, 0.2]), b: M.holdingShades([0.2, null, 0.2, 0.5]),"
                   " c: M.holdingShades([7, 6, 5, 4, 3, 2, 1, 0.5]), none: M.holdingShades([]) }")
    S = ["#1C2B45", "#3D4B63", "#5A6B87", "#7C889C", "#9AA3B2", "#C9D0DB"]
    assert v["shades"] == S                                                               # Part C 의 여섯 가지, 진한 것부터
    assert v["one"] == [S[0], S[1], S[5], S[5], S[5], S[0]]                                # 일곱 번째부터 가장 옅은 색
    assert v["a"] == [S[2], S[0], S[1]]                                                   # 비중이 큰 종목이 가장 진해요
    assert v["b"] == [S[1], S[3], S[2], S[0]]                                             # 같은 비중은 앞 종목 먼저 · 빈칸은 맨 뒤
    assert v["c"] == S + [S[5], S[5]] and v["none"] == []
    for c in S:                                                                           # 남색 계열: 빨강 · 파랑 · 살구색이 아니에요
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        assert b >= r and b - r <= 0x45 and abs(g - (r + b) / 2) <= 0x14, c
    marks = node_value("src/v2/company.js", "M.MARK_COLORS")
    assert not set(S[1:]) & set(marks)                                                    # 로고 글자 표시 색과 겹치지 않아요


def test_logo_colours_never_colour_a_chart():
    """회사 글자 표시의 색(company.js markColor · MARK_COLORS)은 회사 표시(logo.jsx)에만 써요."""
    hits = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "src", "v2", "*"))) + sorted(glob.glob(os.path.join(ROOT, "src", "ui", "*"))):
        body = re.sub(r"//.*", "", open(f, encoding="utf-8").read())
        n = len(re.findall(r"\bmarkColor\b|\bMARK_COLORS\b", body))
        if n:
            hits[os.path.relpath(f, ROOT)] = n
    assert set(hits) == {"src/v2/company.js", "src/v2/logo.jsx"}, hits


# ── 화면 검사가 정말 잡는지 (tests/visualcheck.py) ──

def chromium():
    p = os.environ.get("PLAYWRIGHT_CHROMIUM") or "/opt/pw-browsers/chromium"
    return p if os.path.exists(p) else None


PAGE = """<!doctype html><html><body style="font-family:sans-serif">
<p id="ok" style="font-size:12px">열두 픽셀</p>
<p style="font-size:11.5px">작은 글</p>
<p style="font-size:10px;visibility:hidden">숨은 글</p>
<p style="font-size:10px;opacity:0">안 보이는 글</p>
<div data-ui-v2="chart"><svg viewBox="0 0 400 100" width="200"><text x="0" y="50" font-size="20">축 이름</text></svg></div>
<svg viewBox="0 0 100 100" width="100"><text x="0" y="50" font-size="14">큰 축</text></svg>
<span data-ui-v2="co-mark" style="background:#2F5D62"></span>
<div data-ui-v2="bar" style="width:40px;height:8px;background:#355C7D"></div>
<div style="width:40px;height:8px;background:#1C2B45"></div>
</body></html>"""


@pytest.mark.skipif(chromium() is None, reason="Chromium 이 없어요")
def test_screen_checks_catch_small_text_and_logo_paint():
    pw = pytest.importorskip("playwright.sync_api")
    import visualcheck as V
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium())
        try:
            page = b.new_page()
            page.set_content(PAGE)
            small = V.text_floor(page)
            assert [(t, px) for t, px, _ in small] == [("작은 글", 11.5), ("축 이름", 10)], small   # SVG 는 그려진 크기(20 × 0.5)
            paint = page.evaluate(V.LOGO_PAINT, V.LOGO_RGB)
            assert [x[1] for x in paint] == ["bar"], paint                                 # 회사 표시 안의 색 · 남색은 괜찮아요
            assert page.evaluate(V.IS_V2) is False
        finally:
            b.close()
