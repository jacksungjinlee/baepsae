# -*- coding: utf-8 -*-
"""뱁새 2.0 의 부호 있는 퍼센트는 반올림이 하나예요 (src/ui/pct.js) — Node 로 돌려봐요.

Track 2 audit 4.10 (2026-11-24): 같은 종목의 오늘 등락률이 화면마다 0.1%p 달랐어요 (11-24 발행본에서 144 종목). 홈 · 종목 페이지 ·
관심 종목 · 순위(deckcalc.signedPct)는 Math.round 라 −3.95 를 −3.9% 로 (반이 0 쪽으로), 포트폴리오 · 오늘 목록 줄과 왜 움직였나의
점 띠(src/ui/components.jsx fmtPct)는 toFixed 라 0.15 를 +0.1% 로 (0.15 는 0.1499… 로 저장돼요) 보였어요. data.json d1 은 소수 둘째
자리라 끝이 5 인 값은 딱 반이고, 파일만으로는 참값이 어느 쪽인지 몰라요 (종가로 되짚으면 양쪽이 거의 반반). 그래서 흔한 규칙 하나:
반은 0 에서 먼 쪽 (+3.95 → +4.0%, −3.95 → −4.0%: 같은 크기의 오름과 내림이 같은 숫자), 부동소수점 끝자리는 결정하지 않아요.

- 모서리 값 (x.x5 · 음수 · 0 근처 · 부동소수점 끝자리 · 천 단위)에서 세 입구 (pct.js signedPct · deckcalc.signedPct ·
  components.jsx fmtPct)가 같은 글자이고, −0.0% 는 없어요.
- −100.00 ~ 100.00 의 소수 둘째 자리 값 모두: 파이썬 Decimal 의 ROUND_HALF_UP (반은 0 에서 먼 쪽)과 같고, 부호는 보이는 값의 부호예요.
- 화면의 길: 목록 줄(ListRow change)과 점 띠(DotStrip)를 그려 본 글자가 signedPct 와 같아요 (시험 데이터의 모든 d1).
  실제 데이터로도: python tests/test_v2_one_rounding.py --data DIR (읽기만 해요).
- 업종별 등락의 두 부분(ranks.indParts)은 보이는 값으로 나눠요: 평균 −0.05 는 '−0.1%' 라 내린 업종, −0.04 는 '0.0%' 라 어디에도 없어요.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_UP

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
MINUS = "\u2212"
MODS = {"PCT": "src/ui/pct.js", "DC": "src/v2/deckcalc.js", "UI": "src/ui/components.jsx", "RK": "src/v2/ranks.js"}
_B = {}

# 모서리 값: (입력, 보일 글자). 계산한 값의 부동소수점 끝자리도: (0.15 + 1) − 1 = 0.1499999999999999 · (2.0435 − 2) × 100 =
# 4.349999999999987 · 1.005 × 10 = 10.049999999999999 (모두 반으로 읽어요) · 0.1 + 0.2 = 0.30000000000000004
EDGES = [
    (0, "0.0%"), (-0.0, "0.0%"), (0.04, "0.0%"), (-0.04, "0.0%"), (0.049, "0.0%"), (-0.049, "0.0%"),
    (0.05, "+0.1%"), (-0.05, f"{MINUS}0.1%"), (0.15, "+0.2%"), (-0.15, f"{MINUS}0.2%"), (0.25, "+0.3%"), (-0.25, f"{MINUS}0.3%"),
    (0.35, "+0.4%"), (-0.35, f"{MINUS}0.4%"), (1.95, "+2.0%"), (-1.95, f"{MINUS}2.0%"), (3.95, "+4.0%"), (-3.95, f"{MINUS}4.0%"),
    (4.35, "+4.4%"), (-4.35, f"{MINUS}4.4%"), (5.35, "+5.4%"), (-8.75, f"{MINUS}8.8%"), (16.05, "+16.1%"), (-16.05, f"{MINUS}16.1%"),
    (-3.06, f"{MINUS}3.1%"), (3.04, "+3.0%"), (-29.95, f"{MINUS}30.0%"), (30, "+30.0%"),
    ((0.15 + 1) - 1, "+0.2%"), (1 - (0.15 + 1), f"{MINUS}0.2%"), ((2.0435 - 2) * 100, "+4.4%"), (-(2.0435 - 2) * 100, f"{MINUS}4.4%"),
    (1.005 * 10, "+10.1%"), (0.15 * 100, "+15.0%"), (0.1 + 0.2, "+0.3%"),
    (1431.55, "+1,431.6%"), (-1234.45, f"{MINUS}1,234.5%"),
]


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", f"--outfile={tmp}/b.mjs", "--log-level=error",
                            "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    """body 가 out 에 담은 값을 돌려줘요. PCT · DC · UI · RK: 위 MODS, h: React.createElement, html(el): 그린 글자."""
    decl = "".join(f"const {k} = JSON.parse({json.dumps(json.dumps(v, ensure_ascii=False))});\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { PCT, DC, UI, RK } = B;\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const parts = (el) => ent(renderToStaticMarkup(el).replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n')).split('\\n').filter(Boolean);\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def half_away(k):
    """소수 둘째 자리 값 k/100 을 한 자리로 (Decimal ROUND_HALF_UP: 반은 0 에서 먼 쪽) → 보일 글자."""
    q = (Decimal(k) / 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return (MINUS if q < 0 else "+" if q > 0 else "") + f"{abs(q):,.1f}%"


# 같은 d1 을 세 입구와 두 화면 부품(목록 줄 · 점 띠)으로: [[signedPct, deckcalc, fmtPct, 목록 줄의 글자, 점 띠의 내 종목 · 평균 글자]]
SCREENS = """
out = VS.map((v) => {
  const row = parts(h(UI.ListRow, { title: 'x', change: v }));
  const dot = parts(h(UI.DotStrip, { items: [{ id: 'a', pct: v }], mine: 'a', avgLabel: 'avg {pct}', mineLabel: 'mine {pct}' }));
  return [PCT.signedPct(v), DC.signedPct(v), UI.fmtPct(v), row[row.length - 1], dot.find((s) => s.startsWith('mine ')).slice(5),
    dot.find((s) => s.startsWith('avg ')).slice(4)];
});"""


def screen_texts(values):
    return run(SCREENS, VS=values)


def test_one_helper_for_every_entry():
    """deckcalc.signedPct 는 pct.js 의 그 함수 자체 (홈 · 종목 · 관심 종목 · 순위 · 시장 · 왜 움직였나 · 이번 주 정리가 이걸 불러요)."""
    assert run("out = [DC.signedPct === PCT.signedPct, typeof PCT.shownPct];") == [True, "function"]


def test_edge_values():
    got = run("out = VS.map((v) => [PCT.signedPct(v), DC.signedPct(v), UI.fmtPct(v), PCT.shownPct(v)]);", VS=[v for v, _ in EDGES])
    for (v, want), (a, b, c, shown) in zip(EDGES, got):
        assert a == b == c == want, (v, a, b, c, want)
        assert f"{MINUS}0.0" not in a and "-" not in a, (v, a)
        assert (shown > 0) == a.startswith("+") and (shown < 0) == a.startswith(MINUS) and (shown == 0) == (a == "0.0%"), (v, shown, a)


def test_shown_value_is_never_minus_zero():
    got = run("out = [-0.04, -0, -0.0001, 0].map((v) => Object.is(PCT.shownPct(v), 0));")
    assert got == [True, True, True, True], got


def test_not_a_number_on_the_list_row_is_a_dash():
    assert run("out = [UI.fmtPct(NaN), UI.fmtPct(null), UI.fmtPct(undefined), UI.fmtPct(Infinity)];") == ["–"] * 4


def test_every_two_decimal_value_rounds_half_away_from_zero():
    """−100.00 ~ 100.00 (data.json d1 의 꼴): 세 입구 모두 Decimal ROUND_HALF_UP 과 같고, 오름과 내림이 같은 숫자예요."""
    ks = list(range(-10000, 10001))
    got = run("out = KS.map((k) => { const v = k / 100; return [PCT.signedPct(v), DC.signedPct(v), UI.fmtPct(v), Math.sign(PCT.shownPct(v))]; });", KS=ks)
    bad = []
    for k, (a, b, c, sign) in zip(ks, got):
        want = half_away(k)
        if not (a == b == c == want) or sign != (1 if want.startswith("+") else -1 if want.startswith(MINUS) else 0):
            bad.append((k / 100, a, b, c, want, sign))
    assert not bad, bad[:10]
    by = dict(zip(ks, (g[0] for g in got)))
    assert all(by[-k] == (by[k].replace("+", MINUS) if k else by[k]) for k in range(0, 10001)), "오름과 내림의 숫자가 달라요"
    assert sum(1 for k in ks if abs(k) % 10 == 5) == 2000                                # 끝이 5 인 값 (딱 반)도 다 들어 있어요


def test_screen_parts_show_the_same_text_for_the_fixture_stocks():
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        vs = [s["d1"] for s in json.load(f)["stocks"] if isinstance(s.get("d1"), (int, float))]
    assert len(vs) >= 300 and sum(1 for v in vs if round(abs(v) * 100) % 10 == 5) >= 20           # 끝이 5 인 d1 이 들어 있어요
    bad = [(v, t) for v, t in zip(vs, screen_texts(vs)) if len(set(t)) != 1]
    assert not bad, bad[:10]


def test_industry_parts_split_by_the_value_as_shown():
    groups = [{"ind": "a", "avg": 0.05}, {"ind": "b", "avg": 0.04}, {"ind": "c", "avg": -0.04}, {"ind": "d", "avg": -0.05}, {"ind": "e", "avg": -3.95}]
    got = run("out = (() => { const p = RK.indParts(G); return [p.up.map((g) => g.ind), p.down.map((g) => g.ind)]; })();", G=groups)
    assert got == [["a"], ["e", "d"]], got                    # −0.05 는 '−0.1%' (내린 업종), ±0.04 는 '0.0%' (어디에도 없음)


def main():
    """실제 데이터 폴더(읽기만)의 모든 d1 으로 화면의 길을 돌려 봐요. 결과 한 줄, 다르면 종료 코드 1."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="data.json 이 있는 폴더 (읽기만 해요)")
    args = ap.parse_args()
    with open(os.path.join(args.data, "data.json"), encoding="utf-8") as f:
        d = json.load(f)
    rows = [s for s in d.get("stocks", []) if isinstance(s.get("d1"), (int, float)) and not isinstance(s.get("d1"), bool)]
    with tempfile.TemporaryDirectory() as tmp:
        tempfile.tempdir = tmp
        try:
            texts = screen_texts([s["d1"] for s in rows])
        finally:
            tempfile.tempdir = None
            _B.clear()
    bad = [(s["t"], s["d1"], t) for s, t in zip(rows, texts) if len(set(t)) != 1]
    halves = sum(1 for s in rows if round(abs(s["d1"]) * 100) % 10 == 5)
    ok = not bad and rows
    print(f"{'OK' if ok else 'FAIL'} · 한 반올림: d1 이 있는 {len(rows):,}종목 (끝이 5 인 값 {halves:,}) — 세 입구 · 목록 줄 · 점 띠가 "
          f"{'모두 같은 글자' if ok else f'{len(bad):,}종목에서 달라요: {bad[:5]}'} · pxDate {d.get('pxDate')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
