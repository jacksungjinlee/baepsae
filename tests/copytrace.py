# -*- coding: utf-8 -*-
"""뱁새 2.0 문구 추적 도우미 (tests/test_v2_app.py, tests/smoke_v2.py 가 같이 써요).

승인된 출처(목업 CSV 의 최종 문구 · v18.3 New strings 표 · CLAUDE.md 고정 문구 · 지금 앱의 v17.5 승인 문구 ·
스펙이 그대로 쓰라고 한 말 · Jack 이 채팅에서 승인한 문구 표 · 소개 페이지 문구 docs/design/v19/copy/about.md)에서 '조각'을 만들고,
문구 하나가 그 조각들로 설명되는지 봐요.
숫자와 {자리}는 같은 것으로 봐요 (목업의 숫자는 예시라서요).
"""
import csv
import json
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANGUL = re.compile("[가-힣]")
SLOT = re.compile(r"\{[\w.]+\}")
NUM = re.compile(r"[-+−]?\d[\d,.]*")

# 지금 앱(src/detail.jsx)에 이미 있는 승인 문구 (v17.5): 2.0 문구 → detail.jsx 에 있어야 하는 글자들
V175 = {
    "데이터를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요.": ["데이터를 불러오지 못했어요. 잠시 뒤 다시 열어 주세요."],
    "{md} 기준": ['" 기준"'],
    "{n}일째 갱신이 멈췄어요": ['"일째 갱신이 멈췄어요"'],
    "배당 정보가 없는 종목 {n}개는 0원으로 계산했어요.": ["배당 정보가 없는 종목 {n}개는 0원으로 계산했어요."],
    "지금 예산 기준: 보통 해 ±{amt}만원 출렁": ["지금 예산 기준: 보통 해 <b>±", "</b> 출렁"],
    "일부 종목(비중 {pct}%)은 베타·변동성 자료가 없어요. 위험 수치는 나머지 종목으로 계산했어요.":
        ["일부 종목(비중 {pct}%)은 베타·변동성 자료가 없어요. 위험 수치는 나머지 종목으로 계산했어요."],
    "담은 종목 모두 베타·변동성 자료가 없어 위험 수치를 계산할 수 없어요.": ["담은 종목 모두 베타·변동성 자료가 없어 위험 수치를 계산할 수 없어요."],
    "베타·변동성 자료가 없는 종목이 투자금의 절반을 넘어 위험 수치를 계산할 수 없어요.":
        ["베타·변동성 자료가 없는 종목이 투자금의 절반을 넘어 위험 수치를 계산할 수 없어요."],
}
# 스펙 본문이 그대로 쓰라고 한 말: 문구 → (파일, 그 안에 있어야 하는 글자)
SPEC_QUOTES = {"PBR 낮은 순": [("docs/tasks/v18.3-2.0-beta.md", '"PBR 낮은 순"'), ("CLAUDE.md", "가치 / PBR 낮은 순")]}
# CSV 문장 안의 한 부분을 그대로 쓴 것: 문구 → (CSV 번호, 그 줄에 있어야 하는 글자)
DERIVED = {"{m}월 {d}일": (4, "10월 30일")}


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def csv_final():
    """번호 → 최종 문구 (수정안, 비어 있으면 지금 문구)."""
    with open(os.path.join(ROOT, "docs", "design", "mockup-copy.csv"), encoding="utf-8-sig") as f:
        return {int(r["번호"]): (r["수정안"] if r["수정안"].strip() else r["지금 문구"]) for r in csv.DictReader(f)}


def new_strings():
    text = read("docs/tasks/v18.3-2.0-beta.md").split("## New strings", 1)[1].split("\n## ", 1)[0]
    out = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and HANGUL.search(cells[1]):
            out.append(cells[1])
    assert len(out) >= 15, out
    return out


def chat_approved():
    """docs/tasks/v18.3-approved-in-chat.md: 키 → Jack 이 채팅에서 그대로 승인한 문구."""
    out = {}
    for line in read("docs/tasks/v18.3-approved-in-chat.md").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("`") and HANGUL.search(cells[1]):
            key = cells[0].strip("`")
            # 세 번째 칸이 "Jack, 날짜" 로 시작하지 않으면 승인된 문구가 아니에요 (빈칸 · pending 행이 지나가지 않게)
            assert re.match(r"^Jack, \d{4}-\d{2}-\d{2}\b", cells[2]), f"승인 기록이 없는 행: {line}"
            assert key not in out, f"같은 키가 두 번 있어요: {key}"
            out[key] = cells[1].replace("\\n", "\n")          # 표 칸에는 줄바꿈을 못 넣어서 "\n" 으로 적어요
    assert len(out) >= 3, out
    return out


def footer():
    """CLAUDE.md 의 고정 고지문. 만든 사람 줄은 v19.0 에 소개 페이지로 옮겨 가서(Jack, 2026-11-03) 푸터에는 고지문만 남아요."""
    t = read("CLAUDE.md")
    f = "교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다."
    assert f"Footer: {f}" in t, "CLAUDE.md 에 푸터 고지문이 없어요"
    return [f]


ABOUT_MD = "docs/design/v19/copy/about.md"
ABOUT_MAKER = ("뱁새를 만든 사람", "The person behind Baepsae")


def about_md(lang="ko"):
    """소개 페이지 문구(about.md, Jack 승인 2026-11-03)를 화면에 나오는 순서대로 한 조각씩: 머리글 · 숫자 줄 이름 · 소제목 ·
    문단 · 목록(굵은 제목과 본문은 따로) · 만든 사람(이름 · 하는 일 · 사진 alt · '이름: 값' 줄 · 경력의 '회사 — 한 일').
    머리말의 안내 문단 · '←' 뒤의 메모 · '(사진: 파일, alt …)' 같은 설명은 빼요. 숫자 줄의 숫자(3,256 · 57)는 예시라서 빼요.
    lang: "ko"(## 한국어) 또는 "en"(## English). 영어 쪽에도 '뱁새' · '뱁이' 가 들어 있어서 둘 다 출처로 써요."""
    text = read(ABOUT_MD)
    head = "\n## 한국어\n" if lang == "ko" else "\n## English\n"
    assert text.count(head) == 1, (lang, "about.md 에 언어 제목이 하나여야 해요")
    sec = text.split(head, 1)[1]
    if lang == "ko":
        sec = sec.split("\n## English\n", 1)[0]
    out, maker = [], False
    for raw in sec.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            out.append(line[4:].strip())
            maker = out[-1] in ABOUT_MAKER
            continue
        if line.startswith("- 머리글 (hero): "):
            out += [p.strip().strip("*") for p in line.split(": ", 1)[1].split(" / ")]
            continue
        if line.startswith("- 숫자 줄 (live figures): "):
            body = line.split(": ", 1)[1].split("←", 1)[0].strip()
            out += [re.sub(r"^[\d,]+\s+", "", p.strip()) for p in body.split(" · ")]
            continue
        m = re.match(r'^\*\*(.+?)\*\* · (.+?) \(사진: [^,]+, alt "(.+)"\)$', line)
        if m:
            out += [m.group(1), m.group(2), m.group(3)]
            continue
        m = re.match(r"^(?:- |\d+\. )\*\*(.+?)\*\* (.+)$", line)
        if m:
            out += [m.group(1), m.group(2)]
            continue
        if raw.startswith("    - "):
            out += [x for x in line[2:].split(" — ", 1)]
            continue
        if line.startswith("- "):
            item = line[2:]
            if maker and item.endswith(":"):
                out.append(item[:-1])
            elif maker:
                out += item.split(": ", 1)
            else:
                out.append(item)
            continue
        out.append(line)
    assert len(out) >= 50 and "**" not in "".join(out) and "←" not in "".join(out), out
    return out


def sources():
    src = (list(csv_final().values()) + new_strings() + footer() + list(V175) + list(SPEC_QUOTES) + list(chat_approved().values())
           + about_md("ko") + about_md("en"))
    return [s for s in src if s and HANGUL.search(s)]


def pieces(srcs):
    out = set()
    for s in srcs:
        s = s.replace("\n", " / ")
        cand = {s, s.strip()}
        for part in re.split(r" · | / ", s):
            cand.add(part.strip())
            for sent in re.split(r"(?<=[.?])\s+", part.strip()):
                cand.add(sent.strip())
        out |= {c for c in cand if c and HANGUL.search(c)}
    return out


def numless(s):
    return NUM.sub("{}", SLOT.sub("{}", s))


class Matcher:
    """문구 하나가 승인된 조각으로 설명되면 True."""

    def __init__(self, srcs, loose_slots=False):
        # loose_slots: 출처가 우리 문구 파일일 때 {자리}에는 날짜·이름 같은 한국어도 들어가요 (smoke_v2.py)
        self.raw = pieces(srcs)
        self.norm = {numless(p).strip() for p in self.raw}
        self.items = sorted({p for p in self.norm if len(p.replace(" ", "")) >= 2}, key=len, reverse=True)
        # 출처 쪽 {자리}는 숫자·기호만 대신해요 (한국어 낱말을 삼키지 않게)
        fill = ".+?" if loose_slots else "[^가-힣]+?"
        self.rx = [re.compile("^" + re.escape(p).replace(r"\{\}", fill) + "$") for p in self.norm if "{}" in p]

    def _template(self, x):
        rx = re.compile("^" + re.escape(x).replace(r"\{\}", ".+?") + "$")
        return any(rx.match(p) for p in self.raw) or any(r.match(x) for r in self.rx)

    def _segment(self, x):
        n = len(x)
        ok = [False] * (n + 1)
        ok[0] = True
        for i in range(n):
            if not ok[i]:
                continue
            if x[i] in " ·/":
                ok[i + 1] = True
                continue
            if x.startswith("{}", i):
                ok[i + 2] = True
            for p in self.items:
                if x.startswith(p, i):
                    ok[i + len(p)] = True
            if not HANGUL.search(x[i]) and x[i] not in "{}":
                ok[i + 1] = True      # 숫자·기호·영문 한 글자
        return ok[n]

    def __call__(self, s):
        x = numless(s.replace("\n", " / ")).strip()
        if not HANGUL.search(x):
            return True
        if x in self.norm or self._template(x):
            return True
        return self._segment(x)


def copy_strings():
    """src/copy/v2.js 의 C 를 [(경로, 값)] 으로 (값이 null 이면 None)."""
    with tempfile.TemporaryDirectory() as tmp:                       # 묶음 파일은 읽고 나면 지워요
        out = os.path.join(tmp, "copy.cjs")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, "src/copy/v2.js", "--bundle", "--format=cjs", "--platform=node", "--charset=utf8", f"--outfile={out}",
                            "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        r = subprocess.run(["node", "-e", f"process.stdout.write(JSON.stringify(require({json.dumps(out)}).C))"],
                           capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
    c = json.loads(r.stdout)
    flat = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        else:
            flat.append((path, v))
    walk(c, "")
    return c, flat
