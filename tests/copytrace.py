# -*- coding: utf-8 -*-
"""뱁새 2.0 문구 추적 도우미 (tests/test_v2_app.py, tests/smoke_v2.py 가 같이 써요).

승인된 출처(목업 CSV 의 최종 문구 · v18.3 New strings 표 · CLAUDE.md 고정 문구 · 지금 앱의 v17.5 승인 문구 ·
스펙이 그대로 쓰라고 한 말 · Jack 이 채팅에서 승인한 문구 표)에서 '조각'을 만들고, 문구 하나가 그 조각들로 설명되는지 봐요.
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
            out[key] = cells[1]
    assert len(out) >= 3, out
    return out


def footer():
    t = read("CLAUDE.md")
    f = "교육용 도구입니다. 투자 자문이 아니며, 모든 판단과 책임은 본인에게 있습니다."
    assert f in t and "이성진, INSEAD MBA 26J" in t
    return [f, "이성진, INSEAD MBA 26J"]


def sources():
    src = list(csv_final().values()) + new_strings() + footer() + list(V175) + list(SPEC_QUOTES) + list(chat_approved().values())
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
    tmp = tempfile.mkdtemp()
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
