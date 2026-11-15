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

import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"FC": "src/v2/fcur.js", "CP": "src/copy/v2.js", "FN": "src/v2/fixnote.jsx", "CO": "src/v2/company.jsx", "RK": "src/v2/ranks.js"}
LINE = "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요."
sys.path.insert(0, ROOT)
import validate_data as V  # noqa: E402
CONFIGURED = V.US_FGN_NOCMP          # 스위치의 진짜 값 (이 파일을 읽을 때)
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
      delete C2.co.fgnNoCmp;                       // copy 에 그 줄이 있든 없든 (스위치 own 이 되면 생겨요) 두 경우를 다 봐요
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


def test_switch_own_needs_the_design_chat_line_in_the_copy():
    """리뷰 2차 N2: 스위치가 "own" 이면 앱이 그 칸에 붙일 copy 의 줄 C.co.fgnNoCmp 가 빈 글자가 아닌 글이어야 해요 (node 로 copy 를 읽어요).
    지금 값이 "own" 이 아니면 줄이 없어도 돼요 (copy 에 그 이름이 아직 없어요)."""
    got = run("out = { v: C2.co.fgnNoCmp === undefined ? '__undefined__' : C2.co.fgnNoCmp };")
    if CONFIGURED == "own":
        assert isinstance(got["v"], str) and got["v"].strip() and got["v"] != "__undefined__", got
    else:
        assert CONFIGURED in ("line", "keep")


def test_own_without_the_copy_line_is_a_plain_dash():
    """리뷰 2차 S3: 디자인 채팅의 줄이 오기 전에 스위치를 own 으로 두면 (Jack 의 (c) 사이 기간) 그 칸은 '–' 만 — 줄도 '자료가 없어요' 도 없어요."""
    got = run("""
      const load = { status: 'ok', data: { stocks: STOCKS2, usPxDate: '2026-11-13', pxDate: '2026-11-14', fx: 1333.8 }, coByT: new Map(),
                     byT: new Map(STOCKS2.map((x) => [x.t, x])) };
      const s = STOCKS2.find((x) => x.t === 'ALKS');
      delete C2.co.fgnNoCmp;                       // 디자인 채팅의 줄이 아직 없는 때 (copy 에 이미 있어도 그때를 흉내 내요)
      const tiles = CO.orderTiles(CO.tileViews(load, s)).map((x) => [x.topic, x.rule, x.phrase, x.number]);
      const note = renderToStaticMarkup(h(FN.FgnCutNote, { s }));
      out = { tiles, note, has: 'fgnNoCmp' in C2.co };""",
        STOCKS2=[us("ALKS", dy=0.0, fgnCut={"pbr": "nocompare-own"})] + [us(f"U{i}", pbr=1.0 + i, dy=1.0, vz=50) for i in range(8)])
    assert got["has"] is False and got["note"] == ""
    value = [t for t in got["tiles"] if t[0] == "value"]
    assert value == [["value", "fgn", "–", "PBR –"]], got["tiles"]
    assert not any("자료가 없어요" in str(t) for t in got["tiles"])


NOCMP_LINE = "회사 전체 숫자와 비교할 수 없어서 이 숫자는 비워 두었어요."      # Jack, 2026-11-15 (Q8)
STOPPED_LINE = "오늘은 이 숫자를 확인하지 못해서 비워 두었어요."            # Jack, 2026-11-15 (Q10)


def test_the_two_new_lines_word_for_word_and_approved():
    got = run("out = { n: C2.co.fgnNoCmp, s: C2.co.fgnStopped, c: C2.co.fgnCut };")
    assert got == {"n": NOCMP_LINE, "s": STOPPED_LINE, "c": LINE}
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.fgnNoCmp` | {NOCMP_LINE} | Jack, 2026-11-15" in appr
    assert f"| `co.fgnStopped` | {STOPPED_LINE} | Jack, 2026-11-15" in appr


def test_each_kind_gets_its_own_line_and_never_beside_the_currency_line():
    """Q8 · Q10: nocompare-own → co.fgnNoCmp, stopped → co.fgnStopped, 나머지 → co.fgnCut. 한 칸 묶음에 종류가 섞이면 줄마다 자기 칸만
    (data-fields). 재무제표 통화 회사(fcur)는 #114 의 통화 줄 하나만 — 이 줄은 붙지 않아요."""
    got = run("""
      const html = (s, fields) => renderToStaticMarkup(h(FN.FgnCutNote, { s, fields }));
      const cur = (s) => renderToStaticMarkup(h(FN.FcurNote, { s }));
      const alks = { t: 'ALKS', cls: 'us', dy: 0, fgnCut: { pbr: 'nocompare-own' } };
      const crash = { t: 'SHEL', cls: 'us', fgnCut: { per: 'stopped', pbr: 'stopped', dy: 'stopped' } };
      const bsp = { t: 'BSP', cls: 'us', dy: 0, fgnCut: { per: 'mismatch', pbr: 'nocompare-own' } };
      const tsm = { t: 'TSM', cls: 'us', fcur: 'TWD', fgnCut: { pbr: 'stopped', per: 'nocompare-own' } };
      out = { alks: html(alks), crash: html(crash), crashDy: html(crash, ['dy']), bsp: html(bsp), bspPer: html(bsp, ['per']),
              tsmFgn: html(tsm), tsmCur: cur(tsm), crashCut: FC.fgnCutOf(crash) };""")
    assert NOCMP_LINE in got["alks"] and LINE not in got["alks"] and 'data-kind="own"' in got["alks"]
    assert STOPPED_LINE in got["crash"] and LINE not in got["crash"] and 'data-fields="per,pbr,dy"' in got["crash"]
    assert 'data-kind="stopped"' in got["crash"] and got["crash"].count('data-ui-v2="fgn-cut"') == 1
    assert STOPPED_LINE in got["crashDy"] and 'data-fields="dy"' in got["crashDy"] and got["crashCut"] == ["per", "pbr", "dy"]
    assert got["bsp"].index(LINE) < got["bsp"].index(NOCMP_LINE) and got["bsp"].count('data-ui-v2="fgn-cut"') == 2
    assert LINE in got["bspPer"] and NOCMP_LINE not in got["bspPer"]
    assert got["tsmFgn"] == "" and "fgn-cut" not in got["tsmCur"]                                  # 통화 회사: 통화 줄만


def test_a_crash_day_company_page_says_why_instead_of_no_data():
    """Q10: 검사가 멈춘 날의 요약 칸 · 배당 머리는 '–' 와 그날의 줄 — '자료가 없어요' 가 아니에요."""
    got = run("""
      const load = { status: 'ok', data: { stocks: STOCKS3, usPxDate: '2026-11-13', pxDate: '2026-11-14', fx: 1333.8 }, coByT: new Map(),
                     byT: new Map(STOCKS3.map((x) => [x.t, x])) };
      const s = STOCKS3.find((x) => x.t === 'SHEL');
      out = { tiles: CO.orderTiles(CO.tileViews(load, s)).map((x) => [x.topic, x.rule, x.phrase, x.number]),
              note: renderToStaticMarkup(h(FN.FgnCutNote, { s, fields: ['pbr', 'dy'] })), na: C2.co.tiles ? C2.co.tiles.na : null };""",
        STOCKS3=[us("SHEL", fgnCut={"per": "stopped", "pbr": "stopped", "dy": "stopped"})]
        + [us(f"U{i}", pbr=1.0 + i, dy=1.0, vz=50) for i in range(8)])
    held = [t for t in got["tiles"] if t[1] == "fgn"]
    assert sorted(t[0] for t in held) == ["div", "value"] and all(t[2] == "–" for t in held), got["tiles"]
    assert STOPPED_LINE in got["note"] and 'data-fields="pbr,dy"' in got["note"]
    assert not any("자료가 없어요" in str(t) for t in got["tiles"])
