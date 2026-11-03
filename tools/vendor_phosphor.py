# -*- coding: utf-8 -*-
"""Phosphor 아이콘(duotone)을 뱁새 2.0 으로 옮겨 와요 (v19.0b, Jack 2026-11-03: Phosphor duotone, MIT).

npm 패키지 @phosphor-icons/core 2.1.1 의 압축 파일(.tgz)을 한 번 받아서, 쓰는 아이콘의 duotone SVG 만 읽어
src/ui/phosphor.js (이름 → [바탕 층 path, 선 층 path]) 를 만들어요. 화면은 이 값으로 인라인 SVG 를 그려서 실행 중에는
바깥 주소에 아무것도 요청하지 않아요. 패키지는 package.json · node_modules 에 넣지 않아요.
라이선스(MIT) 원문은 vendor/phosphor/LICENSE, 버전 · 무결성 값 · 아이콘 목록은 vendor/phosphor/SOURCE.txt 에 남겨요.

    mkdir -p /home/user/.ttf && npm pack @phosphor-icons/core@2.1.1 --pack-destination /home/user/.ttf
    python3 -I tools/vendor_phosphor.py /home/user/.ttf/phosphor-icons-core-2.1.1.tgz

압축 파일은 풀지 않고 필요한 파일만 읽어요. 받은 파일의 sha1 · sha512 가 npm 이 알려 준 값과 다르면 멈춰요.
SVG 마다 path 가 정확히 둘(첫째 = opacity 0.2 바탕 층, 둘째 = 선 층)이고 다른 요소가 없어야 해요. 아니면 멈춰요.
"""
import base64
import hashlib
import json
import os
import re
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "2.1.1"
# npm view @phosphor-icons/core@2.1.1 dist.shasum dist.integrity
SHASUM = "62a4cfbec9772f1a613a647da214fbb96f3ad39d"
INTEGRITY = "sha512-v4ARvrip4qBCImOE5rmPUylOEK4iiED9ZyKjcvzuezqMaiRASCHKcRIuvvxL/twvLpkfnEODCOJp5dM4eZilxQ=="

# 쓰는 아이콘 (Phosphor 이름). 무엇에 쓰는지는 src/ui/icons.jsx 의 ALIAS 와 docs/tasks/v19.0-layout-c.md Part B.
ICONS = [
    # 지금 2.0 이 쓰는 것 (예전 이름 → src/ui/icons.jsx ALIAS)
    "check", "warning", "info", "x", "plus", "minus", "caret-right", "caret-down", "caret-left",
    "plus-circle", "magnifying-glass", "newspaper", "clipboard-text", "circle-dashed",
    # 탭 (v19.0c): 홈 · 포트폴리오 · 종목 · 시장, 메뉴 버튼
    "house", "chart-pie-slice", "buildings", "chart-line-up", "list",
    # 섹션
    "percent", "coins", "bank", "identification-badge", "fire", "calendar-dots", "basket", "umbrella", "file-text",
    # 메뉴
    "book-open-text", "database", "clock-counter-clockwise",
    # 상태: 할 일 없음 · 확인할 일
    "check-circle", "flag",
]

PATH = re.compile(r'<path d="([^"]+)"( opacity="0\.2")?/>')
SVG = re.compile(r'^<svg xmlns="http://www\.w3\.org/2000/svg" viewBox="0 0 256 256" fill="currentColor">(.*)</svg>\s*$', re.S)
D_OK = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9,.\- ]+$")


def read_member(tar, name):
    m = tar.getmember(name)
    if not m.isfile():
        raise SystemExit(f"!! {name}: 파일이 아니에요")
    return tar.extractfile(m).read().decode("utf-8")


def layers(name, svg):
    m = SVG.match(svg)
    if not m:
        raise SystemExit(f"!! {name}: SVG 머리가 예상과 달라요 (viewBox 0 0 256 256, fill currentColor)")
    body = m.group(1)
    found = PATH.findall(body)
    if len(found) != 2 or PATH.sub("", body).strip():
        raise SystemExit(f"!! {name}: path 가 정확히 둘이 아니거나 다른 요소가 있어요")
    (bg, bg_op), (line, line_op) = found
    if bg_op != ' opacity="0.2"' or line_op:
        raise SystemExit(f"!! {name}: 첫째가 바탕 층(opacity 0.2), 둘째가 선 층이어야 해요")
    for d in (bg, line):
        if not D_OK.match(d):
            raise SystemExit(f"!! {name}: path 에 예상 밖 글자가 있어요")
    return [bg, line]


def main(tgz):
    raw = open(tgz, "rb").read()
    sha1 = hashlib.sha1(raw).hexdigest()
    sri = "sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode()
    if sha1 != SHASUM or sri != INTEGRITY:
        raise SystemExit(f"!! 받은 파일이 npm 의 {VERSION} 과 달라요: sha1 {sha1}")
    with tarfile.open(tgz, "r:gz") as tar:
        pkg = json.loads(read_member(tar, "package/package.json"))
        if pkg.get("name") != "@phosphor-icons/core" or pkg.get("version") != VERSION or pkg.get("license") != "MIT":
            raise SystemExit(f"!! 패키지가 달라요: {pkg.get('name')} {pkg.get('version')} {pkg.get('license')}")
        lic = read_member(tar, "package/LICENSE")
        if not lic.startswith("MIT License") or "Phosphor Icons" not in lic:
            raise SystemExit("!! LICENSE 가 MIT 원문이 아니에요")
        icons = {n: layers(n, read_member(tar, f"package/assets/duotone/{n}-duotone.svg")) for n in ICONS}

    out = ["// ================= Phosphor duotone 아이콘 (자동 생성 — 손으로 고치지 마세요) =================",
           f"// @phosphor-icons/core {VERSION}, MIT 라이선스 (원문: vendor/phosphor/LICENSE, 출처: vendor/phosphor/SOURCE.txt).",
           "// 만드는 법: tools/vendor_phosphor.py. 아이콘마다 [바탕 층, 선 층] 의 path 데이터예요 (256 격자).",
           "// 색은 여기 없어요: src/ui/icons.jsx 가 src/ui/tokens.js 의 ICON_TONE 으로 칠해요.",
           f'export const PHOSPHOR_VERSION = "{VERSION}";',
           "export const PH = {"]
    for n in ICONS:
        out.append(f"  {json.dumps(n)}: [{json.dumps(icons[n][0])}, {json.dumps(icons[n][1])}],")
    out.append("};")
    with open(os.path.join(ROOT, "src", "ui", "phosphor.js"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    vd = os.path.join(ROOT, "vendor", "phosphor")
    os.makedirs(vd, exist_ok=True)
    with open(os.path.join(vd, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(lic)
    src = [f"Package:   @phosphor-icons/core {VERSION} (npm), licence MIT (LICENSE in this folder, copied from the package)",
           f"Tarball:   phosphor-icons-core-{VERSION}.tgz",
           f"shasum:    {SHASUM}",
           f"integrity: {INTEGRITY}",
           "Weight:    duotone (assets/duotone/<name>-duotone.svg), two layers each: background (opacity 0.2) and line",
           "Generated: src/ui/phosphor.js by tools/vendor_phosphor.py (path data only; colours come from src/ui/tokens.js)",
           f"Icons ({len(ICONS)}):"] + [f"  {n}" for n in ICONS]
    with open(os.path.join(vd, "SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(src) + "\n")
    print(f"· Phosphor {VERSION}: 아이콘 {len(ICONS)}개 → src/ui/phosphor.js · vendor/phosphor/LICENSE · SOURCE.txt")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
