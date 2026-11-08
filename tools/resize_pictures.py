# -*- coding: utf-8 -*-
"""v19.3 기준 · 템플릿 그림을 앱용으로 줄여요 (docs/tasks/v19.3-portfolio-pictures-accounts.md Part A).

원본: docs/design/v19.3/assets/pictures/ (Adobe Stock 192 px · Microsoft Fluent Emoji 3D 128 px, 투명 PNG).
결과: 저장소 맨 위 pictures/ 에 WebP (품질 90, 투명 배경 그대로). 크기만 바꿔요: 자르기 · 색 바꾸기 · 필터 · 다시 그리기 없음.
- 크기 = 승인된 화면 보드(board version 48)에서 그 그림이 가장 크게 보이는 크기의 2배. 원본보다 크게 만들지 않아요(키우면 멈춰요).
- Adobe 그림은 192 px 보다 큰 파일을 만들지 않아요 (docs/design/v19.3/LICENSES.md).
- Fluent 그림 옆에는 MIT 라이선스 글(pictures/LICENSE-fluent-emoji.txt, Microsoft 의 저작권 표시 포함)을 둬요: 이 스크립트는 그 파일을
  만들지 않고, 있는지만 확인해요.
- 전체 400 KB 아래 (Part A). 서비스워커(sw.js)가 이 파일들을 미리 받아 둬요: 목록은 tests/test_pictures.py 가 맞춰 봐요.

    python3 tools/resize_pictures.py            # 모든 그림
    python3 tools/resize_pictures.py adobe-coins.png
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "design", "v19.3", "assets", "pictures")
OUT = os.path.join(ROOT, "pictures")
LICENSE = "LICENSE-fluent-emoji.txt"
MAX_TOTAL = 400 * 1024
ADOBE_MAX = 192

# 그림이 가장 크게 보이는 곳 (보드 · px). 결과 크기는 그 2배예요.
CARD = (50, "기준 그림: PcStart2 의 기준 그림 부채 50 px (휴대폰 BuildStart2 34 px · 기준 카드 32 px · 점검 24 px · 칸 20 px)")
DECK = (36, "템플릿 그림: BuildStart2 · PcStart2 의 레시피 카드 36 px")
WALLET = (44, "가진 종목으로 시작하기: BuildStart2 44 px (PcStart2 42 px)")
TARGETS = {
    # 기준 (engine.js CARDS)
    "fluent-label.png": CARD, "adobe-coins.png": CARD, "adobe-arrows-coins.png": CARD, "adobe-tree.png": CARD,
    "adobe-profit.png": CARD, "adobe-safe.png": CARD, "fluent-turtle.png": CARD, "adobe-chart.png": CARD,
    "adobe-gift.png": CARD, "adobe-bank.png": CARD,
    # 템플릿 (engine.js DECKS, 보이는 것)
    "fluent-magnifying-glass-tilted-left.png": DECK, "fluent-balance-scale.png": DECK, "fluent-deciduous-tree.png": DECK,
    "fluent-gem-stone.png": DECK, "fluent-umbrella.png": DECK, "fluent-sailboat.png": DECK,
    "fluent-globe-showing-asia-australia.png": DECK, "fluent-shopping-cart.png": DECK,
    # 시작 카드 (v19.3c Part D 에서 보여요)
    "adobe-wallet.png": WALLET,
}


def resize(name, shown):
    src = os.path.join(SRC, name)
    im = Image.open(src)
    if im.mode != "RGBA":
        raise SystemExit(f"!! {name}: 투명 배경 PNG(RGBA)가 아니에요 ({im.mode})")
    w, h = im.size
    side = shown * 2
    if side > max(w, h):
        raise SystemExit(f"!! {name}: 원본({w}×{h})이 목표({side})보다 작아요 — 키우지 않아요")
    if name.startswith("adobe-") and side > ADOBE_MAX:
        raise SystemExit(f"!! {name}: Adobe 그림은 {ADOBE_MAX} px 보다 크게 두지 않아요 (LICENSES.md)")
    k = side / max(w, h)
    out = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
    dst = os.path.join(OUT, name[:-4] + ".webp")
    out.save(dst, "WEBP", quality=90, method=6)
    print(f"· {name} → pictures/{os.path.basename(dst)}: {w}×{h} → {out.size[0]}×{out.size[1]} · {os.path.getsize(dst):,} bytes")


def main(names):
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise SystemExit(f"!! TARGETS 에 없는 파일: {unknown}")
    missing = sorted(set(TARGETS) - set(os.listdir(SRC)))
    if missing:
        raise SystemExit(f"!! 원본이 없어요: {missing}")
    os.makedirs(OUT, exist_ok=True)
    for n in names:
        resize(n, TARGETS[n][0])
    if not os.path.isfile(os.path.join(OUT, LICENSE)):
        raise SystemExit(f"!! pictures/{LICENSE} 가 없어요: Fluent 그림 옆에 MIT 라이선스 글을 둬야 해요")
    total = sum(os.path.getsize(os.path.join(OUT, n)) for n in os.listdir(OUT) if n.endswith(".webp"))
    print(f"· pictures/ 그림 합계 {total:,} bytes (한도 {MAX_TOTAL:,})")
    if total > MAX_TOTAL:
        raise SystemExit("!! 그림 합계가 400 KB 를 넘어요")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(TARGETS)))
