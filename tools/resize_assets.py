# -*- coding: utf-8 -*-
"""Jack 의 그림을 사이트용으로 줄여요 (Jack, 2026-11-03: 2배 크기로, 크기만 바꾸기 — 자르기·색 바꾸기·필터 없음).

원본은 docs/design/v19/assets/ 에 그대로 두고, 저장소 맨 위에 '가장 크게 보이는 크기의 2배'로 줄인 파일을 써요.
가로세로 비율은 그대로예요 (긴 쪽을 목표 크기에 맞춰요). 투명 배경 그림은 WebP(품질 90, 60 KB 안 — v19.0 Part C), 사진(JPEG)은 품질 88.
    python3 tools/resize_assets.py                 # 모든 파일
    python3 tools/resize_assets.py baepi-mark.png  # 고른 파일만 (이미 있는 파일을 다시 쓰지 않게)
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
    # v19.0b (Part C): 2.0 화면의 뱁이 — 뱁이 규칙(CLAUDE.md)이 허락하는 자리에만
    "baepi-mark.png": (76, "로고: 휴대폰 28 px · PC 38 px"),
    "baepi-16-build.png": (352, "포트폴리오 만들기 첫 화면 · 첫 방문 홈 (v19.0c): 휴대폰 92 px · PC 176 px"),
    "baepi-15-portfolio.png": (256, "빈 포트폴리오 (v19.0c) · 소개 이름 이야기: 128 px 까지"),
    "baepi-20-error.png": (240, "불러오기 실패: 120 px"),
    "baepi-21-wip.png": (128, "통째로 준비 중인 칸: 64 px"),
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
    names = sys.argv[1:] or list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        raise SystemExit(f"!! TARGETS 에 없는 파일: {unknown}")
    for n in names:
        resize(n, TARGETS[n][0])
    sys.exit(0)
