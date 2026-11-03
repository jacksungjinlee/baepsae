# -*- coding: utf-8 -*-
"""Jack 의 그림을 사이트용으로 줄여요 (Jack, 2026-11-03: 2배 크기로, 크기만 바꾸기 — 자르기·색 바꾸기·필터 없음).

원본은 docs/design/v19/assets/ 에 그대로 두고, 저장소 맨 위에 '가장 크게 보이는 크기의 2배'로 줄인 파일을 써요.
가로세로 비율은 그대로예요 (긴 쪽을 목표 크기에 맞춰요). 투명 배경 그림은 WebP(품질 90, 60 KB 안 — v19.0 Part C), 사진(JPEG)은 품질 88.
    python3 tools/resize_assets.py
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "design", "v19", "assets")
# 파일 → (긴 쪽 픽셀 = 가장 크게 보이는 크기 × 2, 어디에 쓰는지)
TARGETS = {
    "baepi-og.png": (420, "소개 머리글: 휴대폰 108 px · PC 210 px (v19.0 Part C)"),
    "jack-photo.jpg": (224, "소개 사진: 휴대폰 88 px · PC 112 px (v19.0 Part D)"),
}


def resize(name, long_side):
    im = Image.open(os.path.join(SRC, name))
    w, h = im.size
    k = long_side / max(w, h)
    if k >= 1:
        raise SystemExit(f"!! {name}: 원본({w}×{h})이 목표({long_side})보다 작아요 — 키우지 않아요")
    out = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
    if name.endswith(".png"):
        dst = os.path.join(ROOT, name[:-4] + ".webp")
        out.save(dst, "WEBP", quality=90, method=6)
    else:
        dst = os.path.join(ROOT, name)
        out.save(dst, quality=88, optimize=True, progressive=True)
    print(f"· {name} → {os.path.basename(dst)}: {w}×{h} → {out.size[0]}×{out.size[1]} · {os.path.getsize(dst) // 1024} KB")


if __name__ == "__main__":
    for n, (side, _) in TARGETS.items():
        resize(n, side)
    sys.exit(0)
