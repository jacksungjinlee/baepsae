# -*- coding: utf-8 -*-
"""2.0: 재무제표 통화가 달러가 아닌 미국 회사 (Jack, 2026-11-12) — src/v2/fcur.js · src/v2/fixnote.jsx FcurNote · src/copy/v2.js co.fcur ·
co.curName, 그리고 그 회사의 빈 PER · PBR · 배당수익률 · 가치 점수를 엔진이 '빈 칸'으로 다루는지 (Node 로 직접 돌려봐요).

- fcurOf: 미국 종목의 fcur 가 세 글자 대문자이고 USD 가 아닐 때만 그 코드 (한국 종목 · 펀드 · 소문자 · USD · 없음 → null)
- curNameOf: co.curName 의 한국어 이름, 없거나 승인 전(null)이면 null 과 console 경고 (코드마다 한 번) — 줄에 날 코드를 쓰지 않아요
- fcurText: Jack 의 줄 "주가는 달러, 재무제표는 {currency} 기준이라 이 숫자는 계산하지 않았어요." 에 이름을 넣어요. 빈 칸이어야 할
  숫자가 남아 있으면 줄이 없어요 (숫자 옆에 '계산하지 않았어요'가 서지 않게)
- 엔진: 가치(vz) · 배당(dy) 카드에서 그 회사는 빈 칸 — 해당 없음(NA)도 0 도 아니에요. 그 카드에 점수가 있으면 '자료가 없어 빠진 종목'으로
  세고 순위에 넣지 않아요. 다른 카드만 쓰면 그대로 남아요. 회사 페이지 '내 기준과 맞는 정도'의 가치 · 배당 줄은 '–'. 1년 배당은 모름
- 문구: co.fcur 는 Jack 의 줄 그대로 (승인 표), co.curName 은 ISO 코드 → null(승인 대기) 또는 한국어, 대기 문서에 제안과 함께
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"FC": "src/v2/fcur.js", "E": "src/v2/engine.js", "K": "src/v2/company.js", "CP": "src/copy/v2.js", "FN": "src/v2/fixnote.jsx",
        "CO": "src/v2/company.jsx"}
LINE = "주가는 달러, 재무제표는 {currency} 기준이라 이 숫자는 계산하지 않았어요."
TODAY_CODES = ["BRL", "CAD", "CNY", "DKK", "EUR", "HKD", "JPY", "KZT", "SEK", "TWD", "VND"]   # 2026-11-12 미국 27곳의 통화
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
            "const { FC, E, K, CP, FN, CO } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m));\n"
            "const text = (html) => html.replace(/<[^>]+>/g, '');\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def us(t, **kw):
    s = {"t": t, "nk": t, "ne": t, "cls": "us", "price": 100.0, "etf": False, "cap": 10.0, "val": 500.0, "ind": "semi", "indName": "반도체",
         "roe": 20.0, "g3": 10.0, "debt": 30.0, "lz": 50, "mz": 50, "beta": 1.0, "vol": 30.0}
    s.update(kw)
    return s


# ── 순수 함수 ──
def test_fcur_of_and_the_currency_name():
    got = run("""
      out = {
        of: [FC.fcurOf({ cls: 'us', fcur: 'TWD' }), FC.fcurOf({ cls: 'us', fcur: 'USD' }), FC.fcurOf({ cls: 'us', fcur: 'twd' }),
          FC.fcurOf({ cls: 'us', fcur: 'TW' }), FC.fcurOf({ cls: 'us' }), FC.fcurOf({ cls: 'kr', fcur: 'TWD' }), FC.fcurOf({ cls: 'us', fcur: 7 }),
          FC.fcurOf(null), FC.fcurOf({ cls: 'us', fcur: 'XXX' })],
        names: [FC.curNameOf('TWD', { TWD: '대만 달러' }), FC.curNameOf('TWD', { TWD: null }), FC.curNameOf('TWD', { TWD: '  ' }),
          FC.curNameOf('ZZZ', { TWD: '대만 달러' }), FC.curNameOf('ZZZ', {}), FC.curNameOf('toString', {}), FC.curNameOf(null, {})],
      };
      out.warns = warns.slice();""")
    assert got["of"] == ["TWD", None, None, None, None, None, None, None, "XXX"]
    assert got["names"] == ["대만 달러", None, None, None, None, None, None]
    # 이름이 없는 코드는 console 에 한 번씩 (같은 코드 두 번 → 한 줄)
    assert len(got["warns"]) == 3 and all("co.curName" in w for w in got["warns"]), got["warns"]
    assert any("TWD" in w for w in got["warns"]) and any("ZZZ" in w for w in got["warns"]) and any("toString" in w for w in got["warns"])


def test_the_reason_line_never_shows_a_raw_code_or_sits_beside_a_number():
    got = run("""
      const N = { TWD: '대만 달러', KZT: '카자흐스탄 텡게' };
      out = [
        FC.fcurText({ t: 'TSM', cls: 'us', fcur: 'TWD' }, LINE, N),
        FC.fcurText({ t: 'KSPI', cls: 'us', fcur: 'KZT' }, LINE, N),
        FC.fcurText({ t: 'X', cls: 'us', fcur: 'SEK' }, LINE, N),                 // 이름 없음 → 줄 없음 (SEK 를 쓰지 않아요)
        FC.fcurText({ t: 'TSM', cls: 'us', fcur: 'TWD', pbr: 78.88 }, LINE, N),   // 숫자가 남아 있으면 줄 없음
        FC.fcurText({ t: 'TSM', cls: 'us', fcur: 'TWD', dy: 0 }, LINE, N),          // 0% (배당 없음) 는 남은 숫자가 아니에요
        FC.fcurText({ t: 'AAPL', cls: 'us' }, LINE, N),
        FC.fcurText({ t: 'TSM', cls: 'us', fcur: 'TWD' }, null, N),
        FC.fcurText({ t: 'TSM', cls: 'us', fcur: 'TWD' }, '이 숫자는 계산하지 않았어요.', N),
        FC.fcurLeftover({ cls: 'us', fcur: 'TWD', per: 1 }), FC.fcurLeftover({ cls: 'us', fcur: 'TWD', per: null }),
        FC.fcurLeftover({ cls: 'us', per: 1 }),
        FC.fcurRowsBlank({ cls: 'us', fcur: 'TWD' }, [{ id: 'value', blank: true }]),
        FC.fcurRowsBlank({ cls: 'us', fcur: 'TWD' }, [{ id: 'growth', blank: true }, { id: 'div', side: 'top', pct: 3 }]),
        FC.fcurRowsBlank({ cls: 'us' }, [{ id: 'value', blank: true }]),
        FC.FCUR_FIELDS, FC.FCUR_CARDS,
      ];""", LINE=LINE)
    assert got[0] == "주가는 달러, 재무제표는 대만 달러 기준이라 이 숫자는 계산하지 않았어요."
    assert got[1] == "주가는 달러, 재무제표는 카자흐스탄 텡게 기준이라 이 숫자는 계산하지 않았어요."
    assert got[2:4] == [None, None] and got[4] == got[0] and got[5:8] == [None] * 3
    assert got[8:14] == [True, False, False, True, False, False]
    assert got[14] == ["per", "pbr", "dy"] and got[15] == ["value", "div"]


def test_the_note_component_reads_the_copy_and_stays_out_without_a_name():
    got = run("""
      const s = { t: 'TSM', cls: 'us', fcur: 'TWD' };
      const keep = C2.co.curName.TWD;                                         // 이 시험 안에서만 바꾸고 되돌려요 (승인 전이든 뒤든)
      C2.co.curName.TWD = null;                                               // 승인 전의 모양: 이름이 null → 아무것도 그리지 않아요
      const before = renderToStaticMarkup(h(FN.FcurNote, { s }));
      C2.co.curName.TWD = '대만 달러';                                         // 승인된 뒤의 모양
      const after = renderToStaticMarkup(h(FN.FcurNote, { s }));
      const kr = renderToStaticMarkup(h(FN.FcurNote, { s: { t: '005930', cls: 'kr', fcur: 'TWD' } }));
      const none = renderToStaticMarkup(h(FN.FcurNote, { s: { t: 'X', cls: 'us', fcur: 'MYR' } }));      // 문구 파일에 없는 통화
      C2.co.curName.TWD = keep;
      out = { before, after: text(after), cur: /data-cur="TWD"/.test(after), ui: /data-ui-v2="fcur"/.test(after), kr, none };""")
    assert got["before"] == ""
    assert got["after"] == "주가는 달러, 재무제표는 대만 달러 기준이라 이 숫자는 계산하지 않았어요." and got["cur"] and got["ui"]
    assert got["kr"] == "" and got["none"] == ""


# ── 엔진: 빈 칸은 빈 칸 (0 도 해당 없음도 아니에요) ──
def test_build_engine_leaves_the_blanked_companies_out_only_where_they_are_blank():
    stocks = [us(f"U{i}", vz=10 * i, dy=float(i), pbr=1.0 + i, per=10.0 + i) for i in range(1, 9)]
    stocks.append(us("TSM", fcur="TWD"))                               # per · pbr · dy · vz 없음 (파이프라인이 비웠어요)
    got = run("""
      const card = (id) => E.CARDS.find((c) => c.id === id);
      const tsm = STOCKS.find((s) => s.t === 'TSM');
      const base = { ...E.defaultSettings(), mix: 'us', strict: 'loose' };
      const res = (points) => { const r = E.screen(STOCKS, { ...base, points }); return { blanks: r.blanks, ts: r.markets.us.survivors.map((x) => x.t) }; };
      out = {
        raw: ['value', 'div', 'growth', 'profit', 'large'].map((id) => E.cardRaw(tsm, card(id))),
        pct: ['value', 'div'].map((id) => { const m = E.percentileScores(E.universe(STOCKS, 'us'), card(id)); return [m.has('TSM'), m.size]; }),
        value: res({ value: 5 }), div: res({ div: 3, growth: 2 }), growth: res({ growth: 5 }),
        ranks: K.cardRanks(tsm, STOCKS, 'market').rows.filter((r) => ['value', 'div', 'growth'].includes(r.id)),
        text: K.cardRanks(tsm, STOCKS, 'market').rows.filter((r) => ['value', 'div'].includes(r.id)).map(CO.rankText),
        dividend: E.annualDividend([{ s: tsm, shares: 10, cost: 1000 }], 1338),
      };""", STOCKS=stocks)
    assert got["raw"][:2] == [None, None] and got["raw"][2:] == [10.0, 20.0, 10.0]   # 빈 칸 (NA 도 0 도 아니에요)
    assert got["pct"] == [[False, 8], [False, 8]]                                     # 순위에 없어요 · 나머지 8곳끼리
    assert got["value"]["blanks"] == 1 and "TSM" not in got["value"]["ts"] and len(got["value"]["ts"]) == 8
    assert got["div"]["blanks"] == 1 and "TSM" not in got["div"]["ts"]
    assert got["growth"]["blanks"] == 0 and "TSM" in got["growth"]["ts"]               # 가치 · 배당을 쓰지 않으면 그대로
    by = {r["id"]: r for r in got["ranks"]}
    assert by["value"] == {"id": "value", "blank": True} and by["div"] == {"id": "div", "blank": True}
    assert by["growth"].get("side") in ("top", "bottom")
    assert got["text"] == ["–", "–"]
    assert got["dividend"] == {"won": 0, "unknown": 1, "unchecked": []}                 # 1년 배당: 모름 (0% 로 세지 않아요)


def test_tiles_and_hiding_are_keyed_on_the_data_not_on_the_line():
    """#114 리뷰: 이름이 있든 없든(MYR 은 문구 파일에 없어요) 같은 화면 — 가치 · 배당 칸은 '–' 와 'PBR –' · '배당수익률 –' (규칙 fcur,
    그림 · 날짜 없음), 실적 · 출렁임 다음에 와요. 줄만 이름이 있을 때 (TWD). PBR 이 0.00 으로 반올림된 종목(pbrZero)은 가치 칸만 (규칙 pbr0),
    배당은 그대로. 0% 를 남긴 통화 회사는 배당 칸이 평소대로."""
    got = run("""
      const load = { status: 'ok', data: { stocks: STOCKS, usPxDate: '2026-11-11', pxDate: '2026-11-12', fx: 1338 }, coByT: new Map(), byT: new Map(STOCKS.map((x) => [x.t, x])) };
      const view = (t) => { const s = STOCKS.find((x) => x.t === t); return { order: CO.orderTiles(CO.tileViews(load, s)).map((x) => [x.topic, x.rule, x.phrase, x.number, x.basis, x.art]),
        line: FN.fcurNoteText(s), blank: FC.fcurBlank(s), dy: FC.fcurDyBlank(s), p0: FC.pbrZeroOf(s) }; };
      out = { myr: view('M'), twd: view('T'), zero: view('Z'), brk: view('BRK-B'), aapl: view('AAPL'), left: view('L') };""",
        STOCKS=[us("M", fcur="MYR"), us("T", fcur="TWD"), us("Z", fcur="CNY", dy=0.0), us("BRK-B", pbrZero=True, per=15.0, dy=0.0),
                us("L", fcur="TWD", pbr=78.88), us("AAPL", pbr=40.0, dy=0.4)] + [us(f"U{i}", pbr=1.0 + i, dy=1.0) for i in range(6)])
    for k in ("myr", "twd"):
        o = got[k]
        assert [x[:4] for x in o["order"][2:]] == [["value", "fcur", "–", "PBR –"], ["div", "fcur", "–", "배당수익률 –"]], o["order"]
        assert [x[0] for x in o["order"][:2]] == ["earn", "risk"] and all(x[4] is None and x[5] is None for x in o["order"][2:])
        assert o["blank"] is True and o["dy"] is True and o["p0"] is False
    assert got["myr"]["line"] is None
    assert got["twd"]["line"] == "주가는 달러, 재무제표는 대만 달러 기준이라 이 숫자는 계산하지 않았어요."
    z = got["zero"]                                                         # 0% (배당 없음) 를 남긴 회사: 배당 칸은 평소대로
    assert [x[0] for x in z["order"]] == ["earn", "div", "risk", "value"] and z["order"][1][1] == "none" and z["dy"] is False
    assert z["blank"] is True and z["line"] == "주가는 달러, 재무제표는 중국 위안화 기준이라 이 숫자는 계산하지 않았어요."
    b = got["brk"]
    assert [x[:2] for x in b["order"]] == [["earn", "up"], ["div", "none"], ["risk", b["order"][2][1]], ["value", "pbr0"]] and b["p0"] is True
    assert b["order"][3][3] == "PBR –" and b["blank"] is False and b["line"] is None
    assert got["left"]["blank"] is False and got["left"]["line"] is None and got["left"]["order"][1][0] == "value"   # 숫자가 남으면 평소대로
    assert all(x[1] not in ("fcur", "pbr0") for x in got["aapl"]["order"])


# ── 문구 ──
def test_copy_line_and_names():
    got = run("out = { line: C2.co.fcur, names: C2.co.curName };")
    assert got["line"] == LINE                                          # Jack, 2026-11-12 그대로 (자리 이름만 {currency})
    names = got["names"]
    assert names and all(re.fullmatch(r"[A-Z]{3}", k) and k != "USD" for k in names), names
    assert all(v is None or (isinstance(v, str) and re.search("[가-힣]", v)) for v in names.values()), names
    assert set(TODAY_CODES) <= set(names), set(TODAY_CODES) - set(names)   # 오늘 나온 통화는 모두 자리가 있어요
    assert "MYR" not in names                                           # 이름 없는 통화의 시험(위 · smoke_v2)이 쓰는 코드
    doc = open(os.path.join(ROOT, "docs", "tasks", "v18.3-new-strings-pending.md"), encoding="utf-8").read()
    src = open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8").read()
    for k, v in names.items():
        if v is None:                                                   # 승인 대기: 제안이 주석과 대기 문서에 같은 글자로
            m = re.search(rf'^\s+{k}: null,\s+// 제안 \(Jack 승인 대기\) "([^"]+)"$', src, flags=re.M)
            assert m, k
            assert f"| `co.curName.{k}` | {m.group(1)} |" in doc, k
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.fcur` | {LINE} | Jack, 2026-11-12" in appr


def test_pbr_zero_line_and_rows():
    got = run("""
      const s = { t: 'BRK-B', cls: 'us', pbrZero: true, per: 15 };
      out = {
        of: [FC.pbrZeroOf(s), FC.pbrZeroOf({ ...s, pbr: 0.01 }), FC.pbrZeroOf({ ...s, fcur: 'TWD' }), FC.pbrZeroOf({ ...s, cls: 'kr' }),
          FC.pbrZeroOf({ t: 'X', cls: 'us' }), FC.pbrZeroOf({ ...s, pbrZero: 1 })],
        rows: [FC.pbrZeroRowsBlank(s, [{ id: 'value', blank: true }]), FC.pbrZeroRowsBlank(s, [{ id: 'div', blank: true }])],
        note: text(renderToStaticMarkup(h(FN.PbrZeroNote, { s }))), none: renderToStaticMarkup(h(FN.PbrZeroNote, { s: { t: 'A', cls: 'us' } })),
        ui: /data-ui-v2="pbr-zero"/.test(renderToStaticMarkup(h(FN.PbrZeroNote, { s }))),
      };""")
    assert got["of"] == [True, False, False, False, False, False] and got["rows"] == [True, False]
    assert got["note"] == "자료상 PBR이 0에 가깝게 나와서 확인하는 동안 비워 두었어요." and got["none"] == "" and got["ui"]


def test_a_zero_yield_is_not_a_leftover():
    got = run("""out = [FC.fcurLeftover({ cls: 'us', fcur: 'CNY', dy: 0 }), FC.fcurLeftover({ cls: 'us', fcur: 'CNY', dy: 0.1 }),
      FC.fcurDyBlank({ cls: 'us', fcur: 'CNY', dy: 0 }), FC.fcurDyBlank({ cls: 'us', fcur: 'CNY' }), FC.fcurBlank({ cls: 'us', fcur: 'CNY', dy: 0 })];""")
    assert got == [False, True, False, True, True]


def test_approved_names_and_lines_word_for_word():
    got = run("out = { names: C2.co.curName, pz: C2.co.pbrZero };")
    n = got["names"]
    assert all(isinstance(v, str) and v for v in n.values()), n                 # Jack, 2026-11-13: 모두 승인
    assert n["JPY"] == "일본 엔화" and n["CNY"] == "중국 위안화" and n["ZAR"] == "남아공 랜드" and n["SEK"] == "스웨덴 크로나" and n["KRW"] == "원화"
    assert got["pz"] == "자료상 PBR이 0에 가깝게 나와서 확인하는 동안 비워 두었어요."
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.pbrZero` | {got['pz']} | Jack, 2026-11-13" in appr
    for k, v in n.items():
        assert f"| `co.curName.{k}` | {v} | Jack, 2026-11-13" in appr, k
