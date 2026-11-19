# -*- coding: utf-8 -*-
"""왜 움직였나의 종가 날짜: 미국 종목은 한국 날짜를 쓰지 않아요 (CLAUDE.md: 보여 주는 날짜는 그 내용의 날짜 · 시장을 섞지 않아요).

전에는 pxd 가 없는 미국 종목이 usPxDate 가 없는 파일에서 한국 종가 날짜(pxDate)로 "{md} 종가" 를 달았어요 (why.jsx). 이제 회사 페이지와
같은 규칙(cofmt.priceDate: 한국 pxDate · 미국 usPxDate · 자기 날짜 pxd)으로 읽고, 날짜가 없으면 날짜와 그 날짜가 있어야 하는 말을 빼고
(새 말 없음) 콘솔에 한 번 이유를 적어요 (cofmt.priceMdSaid). Node 로 직접 돌려봐요. 화면은 tests/smoke_v2.py 장면 '왜 움직였나 미국 날짜'.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
_B = {}
MODS = {"CF": "src/v2/cofmt.js", "F": "src/v2/format.js"}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-whyus-")
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            f.write("".join(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n" for k, v in MODS.items()))
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--loader:.js=jsx", "--charset=utf8",
                            f"--outfile={tmp}/own.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B.pop("p"), ignore_errors=True)


def run(body, **data):
    """body 가 out 에 답을 넣어요. -> (out, 콘솔 경고 목록)"""
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as M from './own.mjs';\nconst { CF, F } = M;\n"
            "const WARN = []; console.warn = (...a) => WARN.push(a.map(String).join(' ')); console.info = () => {};\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify({ out, WARN }));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    return got["out"], got["WARN"]


def load(**data):
    return {"status": "ok", "data": {"pxDate": "2026-10-30", **data}}


US = {"t": "AAPL", "nk": "애플", "cls": "us", "price": 344.63, "d1": -6.5}
KR = {"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 98000, "d1": -5.5}

needs_node = pytest.mark.skipif(NODE is None, reason="node 가 없어요")


@needs_node
def test_us_stock_without_usPxDate_gets_no_korean_date_and_one_console_line():
    for data in ({}, {"usPxDate": None}, {"usPxDate": ""}, {"usPxDate": "10/29"}):
        out, warn = run("out = [CF.priceMdSaid(L, s, 'why-it-moved'), CF.priceMdSaid(L, s, 'why-it-moved'), CF.priceMd(L, s)];",
                        L=load(**data), s=US)
        assert out == [None, None, None], (data, out)                         # 한국 날짜(10월 30일)를 쓰지 않아요
        assert len(warn) == 1, (data, warn)                                   # 두 번 그려도 한 번만
        w = warn[0]
        assert w.startswith("[v2] why-it-moved AAPL: the close date and the words that need it are left out"), w
        assert "usPxDate" in w and "never takes the Korean date" in w and "2026-10-30" in w, w


@needs_node
def test_us_stock_with_usPxDate_is_unchanged():
    out, warn = run("out = [CF.priceMdSaid(L, s, 'why-it-moved'), F.mdText(L.data.usPxDate)];", L=load(usPxDate="2026-10-29"), s=US)
    assert out[0] == out[1] == "10월 29일" and not warn, (out, warn)
    out, warn = run("out = CF.priceMdSaid(L, s, 'why-it-moved');", L=load(usPxDate="2026-10-30"), s=US)
    assert out == "10월 30일" and not warn                                    # 두 시장이 같은 날이면 그 날짜 그대로


@needs_node
def test_korean_stock_is_unchanged_with_or_without_usPxDate():
    for data in ({}, {"usPxDate": "2026-10-29"}):
        out, warn = run("out = [CF.priceMdSaid(L, s, 'why-it-moved'), F.mdText(L.data.pxDate)];", L=load(**data), s=KR)
        assert out[0] == out[1] == "10월 30일" and not warn, (data, out, warn)
    for cls in ("bond", "metal"):                                             # 국내 상장 안전자산 ETF 도 한국 종가
        out, warn = run("out = CF.priceMdSaid(L, s, 'why-it-moved');", L=load(usPxDate="2026-10-29"), s={**KR, "t": "132030", "cls": cls})
        assert out == "10월 30일" and not warn, (cls, out)


@needs_node
def test_pxd_stock_is_unchanged():
    s = {**US, "pxd": "2026-10-27"}
    s.pop("d1")
    for data in ({"usPxDate": "2026-10-29"}, {}):                             # 자기 날짜는 usPxDate 가 없어도 그대로
        out, warn = run("out = [CF.priceMdSaid(L, s, 'why-it-moved'), F.mdText(CF.priceDate(L, s))];", L=load(**data), s=s)
        assert out[0] == out[1] == "10월 27일" and not warn, (data, out, warn)
    out, warn = run("out = CF.priceMdSaid(L, s, 'why-it-moved');", L=load(usPxDate="2026-10-29"), s={**s, "pxd": "10월 27일"})
    assert out is None and len(warn) == 1 and 'pxd "10월 27일"' in warn[0] and "cannot be read" in warn[0], warn


@needs_node
def test_each_stock_and_screen_says_it_once():
    out, warn = run("const a = { ...s, t: 'MSFT' };\n"
                    "out = [CF.priceMdSaid(L, s, 'why-it-moved'), CF.priceMdSaid(L, a, 'why-it-moved'), CF.priceMdSaid(L, s, 'why-it-moved'),"
                    " CF.priceMdSaid(L, s, 'other-screen')];", L=load(), s=US)
    assert out == [None] * 4
    assert [w.split(":")[0] for w in warn] == ["[v2] why-it-moved AAPL", "[v2] why-it-moved MSFT", "[v2] other-screen AAPL"], warn


# usPxDate 대신 pxDate 를 쓰는 모양: `usPxDate || …pxDate` · `?? …pxDate` · `usPxDate ? … : …pxDate` (여러 줄에 걸쳐도)
FALLBACK = re.compile(r"usPxDate\s*(\|\||\?\?)\s*[\w.]*\bpxDate\b|usPxDate\s*\?[^:;]{0,200}:\s*[\w.]*\bpxDate\b")


def _code(text):
    """주석을 뺀 코드 (줄 수는 그대로)."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", text)


def test_the_fallback_guard_knows_the_forms():
    for bad in ("load.data.usPxDate || load.data.pxDate", "d.usPxDate ?? d.pxDate", "d.usPxDate\n    || d.pxDate",
                "load.data.usPxDate ? load.data.usPxDate : load.data.pxDate", "d.usPxDate\n  ? mdText(d.usPxDate)\n  : d.pxDate"):
        assert FALLBACK.search(_code(bad)), bad
    for ok in ("usOf(s) ? load.data.usPxDate : load.data.pxDate", "load.data.usPxDate || null",
               "load.data.usPxDate && load.data.usPxDate !== load.data.pxDate ? mdText(load.data.usPxDate) : null",
               "// usPxDate || pxDate (a comment)"):
        assert not FALLBACK.search(_code(ok)), ok


def test_no_us_date_falls_back_to_the_korean_date_anywhere_in_src():
    """2.0 과 예전 앱 모두: usPxDate 가 없을 때 pxDate 로 대신하는 곳이 없어요."""
    hits = []
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.js*"), recursive=True)):
        with open(p, encoding="utf-8") as f:
            code = _code(f.read())
        for m in FALLBACK.finditer(code):
            hits.append(f"{os.path.relpath(p, ROOT)}:{code.count(chr(10), 0, m.start()) + 1}: {m.group(0)[:120]!r}")
    assert not hits, hits
