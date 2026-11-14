# -*- coding: utf-8 -*-
"""2.0: 넓힌 외국 회사 검사 (Jack, 2026-11-14 Q5) — #126 의 21곳 밖 회사(NBIS · TRI · CRDO)도 비운 칸마다 같은 줄 "자료의 숫자가 회사 전체
재무제표와 맞지 않아서 비워 두었어요." 을 받고 (src/v2/fcur.js fgnCutOf · fixnote.jsx FgnCutNote · company.jsx tileViews), 비운 PBR ·
배당수익률은 종목 순위(src/v2/ranks.js critList 가치 · divList 배당)와 내 기준(mineList)에서 빠져요. 앱은 티커 목록을 보지 않고 종목의 fgnCut 만
봐요 — 새 문구 없음. (Node 로 직접 돌려봐요 · 더하기만)"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"FC": "src/v2/fcur.js", "CP": "src/copy/v2.js", "FN": "src/v2/fixnote.jsx", "CO": "src/v2/company.jsx", "RK": "src/v2/ranks.js"}
LINE = "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요."
_B = {}


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
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { FC, CP, FN, CO, RK } = B; const C2 = CP.C;\n"
            "console.warn = () => {}; console.log = ((log) => (...a) => { if (typeof a[0] === 'string' && a[0].startsWith('{')) log(...a); })(console.log);\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def us(t, **kw):
    s = {"t": t, "nk": t, "ne": t, "cls": "us", "price": 100.0, "etf": False, "cap": 10.0, "val": 500.0, "ind": "semi", "indName": "반도체",
         "roe": 20.0, "g3": 10.0, "debt": 30.0, "lz": 50, "mz": 50, "beta": 1.0, "vol": 30.0, "d1": 0.5}
    s.update(kw)
    return s


# 2026-11-14 로컬 실행 값: NBIS PER · PBR, TRI PER · 배당, CRDO PBR 을 비움 · SHOP 은 그대로
STOCKS = [us("NBIS", dy=0.0, fgnCut={"per": "mismatch", "pbr": "mismatch"}),
          us("TRI", pbr=4.22, vz=40, fgnCut={"per": "mismatch", "dy": "mismatch"}),
          us("CRDO", per=46.6, dy=0.0, fgnCut={"pbr": "mismatch"}),
          us("SHOP", per=90.2, pbr=14.84, dy=0.0, vz=5)] + [us(f"U{i}", per=20.0 + i, pbr=1.0 + i, dy=1.0 + i / 10, vz=50) for i in range(8)]


def test_newly_covered_companies_get_the_same_line_and_tiles():
    got = run("""
      const load = { status: 'ok', data: { stocks: STOCKS, usPxDate: '2026-11-13', pxDate: '2026-11-14', fx: 1333.8 }, coByT: new Map(), byT: new Map(STOCKS.map((x) => [x.t, x])) };
      const view = (t) => { const s = STOCKS.find((x) => x.t === t); return CO.orderTiles(CO.tileViews(load, s)).filter((x) => x.rule === 'fgn').map((x) => [x.topic, x.phrase, x.number]); };
      const note = (t) => renderToStaticMarkup(h(FN.FgnCutNote, { s: STOCKS.find((x) => x.t === t) }));
      out = { cut: ['NBIS', 'TRI', 'CRDO', 'SHOP'].map((t) => FC.fgnCutOf(STOCKS.find((x) => x.t === t))),
              tiles: ['NBIS', 'TRI', 'CRDO', 'SHOP'].map(view), notes: ['NBIS', 'TRI', 'CRDO', 'SHOP'].map(note), line: C2.co.fgnCut };""", STOCKS=STOCKS)
    assert got["cut"] == [["per", "pbr"], ["per", "dy"], ["pbr"], []]
    assert got["tiles"] == [[["value", "–", "PBR –"]], [["div", "–", "배당수익률 –"]], [["value", "–", "PBR –"]], []]
    assert got["line"] == LINE
    for html, fields in zip(got["notes"][:3], ("per,pbr", "per,dy", "pbr")):
        assert LINE in html and f'data-fields="{fields}"' in html, html
    assert got["notes"][3] == ""


def test_blanked_numbers_leave_the_lists():
    got = run("""
      const ts = (rows) => (rows || []).map((r) => r.s.t);
      out = { value: ts(RK.critList(STOCKS, 'us', 'value')), div: ts(RK.divList(STOCKS, 'us')),
              mineValue: ts(RK.mineList(STOCKS, 'us', { points: { value: 3 }, exclude: {} })),
              mineDiv: ts(RK.mineList(STOCKS, 'us', { points: { div: 3 }, exclude: {} })) };""", STOCKS=STOCKS)
    assert not {"NBIS", "CRDO"} & set(got["value"]) and {"TRI", "SHOP"} <= set(got["value"]), got        # 비운 PBR 은 가치 순위 밖
    assert "TRI" not in got["div"] and "TRI" not in got["mineDiv"], got                                     # 비운 배당수익률은 배당 순위 밖
    assert not {"NBIS", "CRDO"} & set(got["mineValue"]) and {"TRI", "SHOP"} <= set(got["mineValue"]), got   # 가치 점수(vz)도 없어요


def test_the_line_follows_the_kind_the_switch_wrote():
    """리뷰 S1: 맞춰 볼 값이 없어 비운 칸(nocompare)도 지금은 승인된 줄 그대로 (#126). 스위치가 own 이면 파이프라인이 nocompare-own 을 적고, 앱은 그
    칸에만 디자인 채팅의 줄(co.fgnNoCmp)을 붙여요 — 그 줄이 없으면 아무 줄도 붙이지 않아요 (사실이 아닌 줄을 붙이지 않게)."""
    got = run("""
      const html = (s, fields) => renderToStaticMarkup(h(FN.FgnCutNote, { s, fields }));
      const alks = { t: 'ALKS', cls: 'us', dy: 0, fgnCut: { pbr: 'nocompare' } };
      const own = { t: 'ALKS', cls: 'us', dy: 0, fgnCut: { pbr: 'nocompare-own' } };
      const bsp = { t: 'BSP', cls: 'us', dy: 0, fgnCut: { per: 'mismatch', pbr: 'nocompare-own' } };
      const before = { alks: html(alks), own: html(own), bsp: html(bsp), ownOf: FC.fgnOwnOf(bsp), blank: FC.fgnCutOf(own), has: 'fgnNoCmp' in C2.co };
      C2.co.fgnNoCmp = '시험 줄';
      out = { before, after: { own: html(own), bsp: html(bsp), bspPer: html(bsp, ['per']) } };""")
    b, a = got["before"], got["after"]
    assert LINE in b["alks"] and 'data-fields="pbr"' in b["alks"]                      # nocompare: 승인된 줄 (지금 그대로)
    assert b["has"] is False and b["own"] == "" and b["blank"] == ["pbr"]                # own 줄이 copy 에 없으면 줄 없음 (칸은 '–')
    assert b["ownOf"] == ["pbr"] and LINE in b["bsp"] and 'data-fields="per"' in b["bsp"] and "pbr" not in b["bsp"].split("data-fields=")[1][:8]
    assert "시험 줄" in a["own"] and 'data-kind="own"' in a["own"] and LINE not in a["own"]
    assert LINE in a["bsp"] and "시험 줄" in a["bsp"] and a["bsp"].count('data-ui-v2="fgn-cut"') == 2   # 종류가 다른 두 칸: 두 줄
    assert LINE in a["bspPer"] and "시험 줄" not in a["bspPer"]
