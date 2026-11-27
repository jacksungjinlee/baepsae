# -*- coding: utf-8 -*-
"""#181 켜기 (Jack, 2026-11-27 "#181: yes") — 2.0 과 예전 뱁새가 회사 합계로 다시 계산한 숫자를 어떻게 보이는지 (Node 로 직접 돌려봐요).
src/v2/fcur.js fcurTotOf · fcurNiOf · fcurBlankOf · fcurTotText · fcurTotRowsShown · src/v2/fixnote.jsx FcurTotNote · FcurNiNote ·
src/repair.js fcurTotStrip · src/v2/load.js resolveLoad · 회사 페이지 (요약 · 가치 탭 · 가치 자세히 · 배당 탭) · 두 종목 비교 칸.

- data.json fcurTot (켜진 날 파이프라인이 다시 실은 칸) · fcurNi (두 순이익이 맞지 않아 비운 PER — Sony).
- 바꿔 계산한 PER · PBR 밑에는 영역마다 한 번 "재무제표가 {currency} 기준이라 {md} 미국 장 마감 환율로 달러로 바꿔 계산했어요." (co.fcurTot ·
  Jack 의 승인을 기다려요: 문구 파일에서는 null). 배당수익률은 달러 ÷ 달러 · 야후 값이라 그 줄이 없어요.
- Sony 의 PER: '–' 밑에 Jack 의 줄 "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요." (co.fcurNi · 2026-11-27 승인).
- 남은 빈 칸: #114 의 통화 줄 그대로. 스위치가 꺼진 데이터(fcurTot 없음)는 예전과 한 글자도 다르지 않아요 (tests/test_us_fcur_app.py 그대로).
- 그 줄의 문구가 없으면(null) 앱은 그 숫자를 보지 않아요 (resolveLoad → fcurTotStrip) · 예전 뱁새는 늘 #114 그대로 ('–').
- 스위치(validate_data.US_FCUR_TOT_ON)와 문구(co.fcurTot)는 함께 켜져요 — 하나만 켜지면 이 시험이 걸려요.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import validate_data as V  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"R": "src/repair.js", "FC": "src/v2/fcur.js", "FN": "src/v2/fixnote.jsx", "CO": "src/v2/company.jsx", "CP": "src/copy/v2.js",
        "L": "src/v2/load.js", "CM": "src/v2/compare.jsx"}
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
# Jack 이 아직 승인하지 않은 줄 (2026-11-27 설계 채팅 초안 그대로 · docs/tasks/v18.3-new-strings-pending.md) — 시험 안에서만 넣어 봐요
DRAFT = "재무제표가 {currency} 기준이라 {md} 미국 장 마감 환율로 달러로 바꿔 계산했어요."
NI_LINE = "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요."
CUR_LINE = "주가는 달러, 재무제표는 {currency} 기준이라 이 숫자는 계산하지 않았어요."
MD = "10월 30일"                      # 시험 데이터의 usPxDate 2026-10-30
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


def fixture():
    """2.0 시험 데이터에 켜진 날의 모양: TSM (TWD) 세 칸 모두 되살림 · BABA (CNY) Sony 모양 (PBR 되살림 · PER 은 두 순이익이 맞지 않아 빈 칸 ·
    배당 빈 칸) · ASML (EUR) PER 만 되살림 (PBR 은 빈 칸 — 오래된 자본)."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(FIX, "corp.json"), encoding="utf-8") as f:
        corp = json.load(f)
    by = {s["t"]: s for s in data["stocks"]}
    by["TSM"].update(fcur="TWD", per=21.6, pbr=7.79, dy=1.18, fcurTot=["per", "pbr", "dy"])
    b = by["BABA"]
    b.update(fcur="CNY", pbr=1.15, fcurTot=["pbr"], fcurNi=True)
    b.pop("per"), b.pop("dy")
    a = by["ASML"]
    a.update(fcur="EUR", per=33.0, fcurTot=["per"])
    a.pop("pbr", None), a.pop("dy"), a.pop("vz", None)
    return data, corp


@pytest.fixture(autouse=True, scope="module")
def files():
    tmp = tempfile.mkdtemp()
    d, c = fixture()
    for name, obj in (("data", d), ("corp", c)):
        p = os.path.join(tmp, f"{name}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        _B[name] = p
    yield
    shutil.rmtree(tmp, ignore_errors=True)


def run(body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\n"
            "const { R, FC, FN, CO, CP, L, CM } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            f"const DATA = JSON.parse(fs.readFileSync({json.dumps(_B['data'])}, 'utf8')); const CORP = JSON.parse(fs.readFileSync({json.dumps(_B['corp'])}, 'utf8'));\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            f"const DRAFT = {json.dumps(DRAFT, ensure_ascii=False)};\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle_dir(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def filled(line, cur):
    return line.replace("{currency}", cur).replace("{md}", MD)


# ── 순수 함수 ──
def test_fields_put_back_the_sony_mark_and_each_blank_on_its_own():
    got = run("""
      const s = (t) => LOAD.byT.get(t);
      const f = (x) => ({ tot: FC.fcurTotOf(x), ni: FC.fcurNiOf(x), left: FC.fcurLeftover(x),
        blank: ['per', 'pbr', 'dy'].map((k) => FC.fcurBlankOf(x, k)), both: FC.fcurBlank(x), dy: FC.fcurDyBlank(x) });
      out = {
        tsm: f(s('TSM')), baba: f(s('BABA')), asml: f(s('ASML')),
        off: f({ t: 'X', cls: 'us', fcur: 'TWD' }), offZero: f({ t: 'X', cls: 'us', fcur: 'TWD', dy: 0 }),
        notMarked: f({ t: 'X', cls: 'us', fcur: 'TWD', pbr: 7.79 }),                              // 표시 없는 숫자: 예전처럼 남은 숫자
        zeroMarked: f({ t: 'X', cls: 'us', fcur: 'TWD', pbr: 0, fcurTot: ['pbr'] }),               // 0 은 되살린 숫자가 아니에요
        dollar: f({ t: 'AAPL', cls: 'us', pbr: 46, fcurTot: ['pbr'] }), kr: f({ t: '005930', cls: 'kr', fcur: 'TWD', fcurTot: ['pbr'], pbr: 1 }),
        niWithPer: FC.fcurNiOf({ t: 'X', cls: 'us', fcur: 'JPY', per: 20, fcurNi: true }),
        rows: [FC.fcurRowsBlank(s('ASML'), [{ id: 'value', blank: true }]), FC.fcurRowsBlank(s('TSM'), [{ id: 'value', rank: 3 }]),
          FC.fcurRowsBlank(s('BABA'), [{ id: 'div', blank: true }]), FC.fcurRowsBlank(s('BABA'), [{ id: 'value', blank: true }])],
        shown: [FC.fcurTotRowsShown(s('TSM'), [{ id: 'value', rank: 3 }]), FC.fcurTotRowsShown(s('TSM'), [{ id: 'value', blank: true }]),
          FC.fcurTotRowsShown(s('ASML'), [{ id: 'value', rank: 3 }])],
      };""")
    assert got["tsm"] == {"tot": ["per", "pbr", "dy"], "ni": False, "left": False, "blank": [False, False, False], "both": False, "dy": False}
    assert got["baba"] == {"tot": ["pbr"], "ni": True, "left": False, "blank": [False, False, True], "both": False, "dy": True}
    assert got["asml"] == {"tot": ["per"], "ni": False, "left": False, "blank": [False, True, True], "both": False, "dy": True}
    # 스위치가 꺼진 데이터(표시 없음): 예전 그대로 (세 칸 모두 #114 의 빈 칸 · 0% 는 남은 숫자가 아님)
    assert got["off"] == {"tot": [], "ni": False, "left": False, "blank": [True, True, True], "both": True, "dy": True}
    assert got["offZero"]["blank"] == [True, True, False] and got["offZero"]["both"] is True and got["offZero"]["left"] is False
    assert got["notMarked"]["left"] is True and got["notMarked"]["blank"] == [False, False, False]
    assert got["zeroMarked"]["tot"] == [] and got["zeroMarked"]["left"] is True               # 0 은 되살린 숫자가 아니라 남은 숫자 (관문이 막아요)
    assert got["dollar"]["tot"] == [] and got["kr"]["tot"] == [] and got["niWithPer"] is False
    assert got["rows"] == [True, False, True, False]
    assert got["shown"] == [True, False, False]


def test_the_converted_line_needs_its_words_a_name_a_date_and_a_converted_number():
    got = run("""
      const N = C2.co.curName, s = LOAD.byT.get('TSM');
      out = [
        FC.fcurTotText(s, DRAFT, N, '10월 30일'), FC.fcurTotText(s, DRAFT, N, '10월 30일', ['pbr']),
        FC.fcurTotText(s, null, N, '10월 30일'), FC.fcurTotText(s, DRAFT, N, null), FC.fcurTotText(s, DRAFT, N, ''),
        FC.fcurTotText({ ...s, fcur: 'MYR' }, DRAFT, N, '10월 30일'),                                 // 이름 없는 통화 → 줄 없음
        FC.fcurTotText({ ...s, fcurTot: ['dy'] }, DRAFT, N, '10월 30일'),                              // 배당수익률만: 바꿔 계산한 숫자가 아님
        FC.fcurTotText(LOAD.byT.get('ASML'), DRAFT, N, '10월 30일', ['pbr']),                          // 이 영역에 바꾼 숫자가 없음
        FC.fcurTotText(s, '재무제표를 바꿔 계산했어요.', N, '10월 30일'),
      ];""")
    want = filled(DRAFT, "대만 달러")
    assert got[0] == got[1] == want == "재무제표가 대만 달러 기준이라 10월 30일 미국 장 마감 환율로 달러로 바꿔 계산했어요."
    assert got[2:] == [None] * 7


def test_strip_drops_the_marked_numbers_and_their_value_score():
    got = run("""
      const st = [{ t: 'TSM', cls: 'us', fcur: 'TWD', per: 21.6, pbr: 7.79, dy: 1.18, vz: 12, fcurTot: ['per', 'pbr', 'dy'] },
        { t: 'ASML', cls: 'us', fcur: 'EUR', per: 33, vz: 40, fcurTot: ['per'] },
        { t: 'SONY', cls: 'us', fcur: 'JPY', pbr: 2.95, vz: 30, fcurTot: ['pbr'], fcurNi: true, dy: 0 },
        { t: 'ODD', cls: 'us', fcur: 'EUR', per: 9, pbr: 1, vz: 9, fcurTot: 'per' },
        { t: 'AAPL', cls: 'us', per: 38.9, pbr: 46.03, dy: 0.31, vz: 1 }];
      const cut = R.fcurTotStrip(st);
      out = { cut, st, none: R.fcurTotStrip(null) };""")
    assert got["cut"] == ["TSM", "ASML", "SONY", "ODD"] and got["none"] == []
    tsm, asml, sony, odd, aapl = got["st"]
    assert tsm == {"t": "TSM", "cls": "us", "fcur": "TWD"}
    assert asml == {"t": "ASML", "cls": "us", "fcur": "EUR", "vz": 40}                          # PBR 을 되살리지 않았으면 vz 는 그대로
    assert sony == {"t": "SONY", "cls": "us", "fcur": "JPY", "fcurNi": True, "dy": 0}            # #114 의 0% 와 Sony 표시는 그대로
    assert odd == {"t": "ODD", "cls": "us", "fcur": "EUR"}                                      # 읽을 수 없는 표시: 세 칸 모두 비워요
    assert aapl == {"t": "AAPL", "cls": "us", "per": 38.9, "pbr": 46.03, "dy": 0.31, "vz": 1}


def test_resolve_load_hides_them_while_the_line_waits_and_shows_them_with_it():
    got = run("""
      const files = () => ({ data: { ok: true, data: JSON.parse(JSON.stringify(DATA)) }, corp: { ok: true, data: CORP }, macro: { ok: false, error: 'x' } });
      const keep = C2.co.fcurTot;
      C2.co.fcurTot = null;
      const a = L.resolveLoad(files(), Date.parse('2026-10-31T12:00:00+09:00'));
      const w1 = warns.filter((x) => x.includes('fcurTot'));
      C2.co.fcurTot = DRAFT;
      const b = L.resolveLoad(files(), Date.parse('2026-10-31T12:00:00+09:00'));
      C2.co.fcurTot = keep;
      const pick = (l, t) => { const s = l.byT.get(t); return [s.per ?? null, s.pbr ?? null, s.dy ?? null, s.vz ?? null, s.fcurTot ?? null, s.fcurNi ?? null]; };
      out = { a: ['TSM', 'BABA', 'ASML'].map((t) => pick(a, t)), b: ['TSM', 'BABA', 'ASML'].map((t) => pick(b, t)), w1,
        w2: warns.filter((x) => x.includes('fcurTot')).length - w1.length, aapl: pick(a, 'AAPL') };""")
    vz = {t: next(s for s in json.load(open(_B["data"], encoding="utf-8"))["stocks"] if s["t"] == t).get("vz") for t in ("TSM", "BABA")}
    # 문구가 없으면: TSM 은 #114 그대로 (vz 도) · BABA 는 Sony 표시만 남아요 (PER 은 원래 빈 칸) · ASML 은 PER 만 빠져요
    assert got["a"] == [[None] * 6, [None, None, None, None, None, True], [None] * 6], got["a"]
    assert len(got["w1"]) == 1 and "3 US companies" in got["w1"][0] and all(t in got["w1"][0] for t in ("TSM", "BABA", "ASML")), got["w1"]
    assert got["b"] == [[21.6, 7.79, 1.18, vz["TSM"], ["per", "pbr", "dy"], None], [None, 1.15, None, vz["BABA"], ["pbr"], True],
                        [33.0, None, None, None, ["per"], None]], got["b"]
    assert got["w2"] == 0 and got["aapl"][:3] == [38.9, 46.03, 0.31]


# ── 화면: 영역마다 한 번 ──
PAGES = """
  const nav = { setTab() {}, more() {}, back() {}, onWhy() {} };
  const store = { data: { v: 2, decks: [] }, writable: false, key: 'baepsae2.v1', preview: false };
  const page = (code, ctab) => renderToStaticMarkup(h(CO.Company, { load: LOAD, store, setStoreData() {}, pad: 0, code, ctab, disc: null, nav }));
  const tabs = [null, 'value', 'value-more', 'div'];
  const lines = (code, words) => tabs.map((ctab) => count(page(code, ctab), words));
"""


def test_company_pages_say_each_line_once_where_it_belongs():
    got = run(PAGES + """
      const keep = C2.co.fcurTot;
      C2.co.fcurTot = DRAFT;
      const conv = (code, cur) => DRAFT.split('{currency}').join(cur).split('{md}').join('10월 30일');
      const curl = (cur) => C2.co.fcur.split('{currency}').join(cur);
      out = {
        tsm: { conv: lines('TSM', conv('TSM', '대만 달러')), cur: lines('TSM', curl('대만 달러')), ni: lines('TSM', C2.co.fcurNi) },
        baba: { conv: lines('BABA', conv('BABA', '중국 위안화')), cur: lines('BABA', curl('중국 위안화')), ni: lines('BABA', C2.co.fcurNi) },
        asml: { conv: lines('ASML', conv('ASML', '유로')), cur: lines('ASML', curl('유로')), ni: lines('ASML', C2.co.fcurNi) },
        aapl: lines('AAPL', '미국 장 마감 환율로'),
        tsmValue: /data-ui-v2="co-pbr"[^>]*>/.test(page('TSM', 'value')) && !/data-blank="fcur"/.test(page('TSM', 'value')),
        babaPer: (page('BABA', 'value').match(/data-ui-v2="co-per"[^>]*data-blank="fcurNi"/g) || []).length,
        asmlPbr: (page('ASML', 'value').match(/data-ui-v2="co-pbr"[^>]*data-blank="fcur"/g) || []).length,
        tsmDate: /data-ui-v2="date-line"/.test(page('TSM', 'value')),
      };
      C2.co.fcurTot = null;
      out.waiting = { tsm: lines('TSM', '미국 장 마감 환율로'), baba: lines('BABA', '미국 장 마감 환율로') };
      C2.co.fcurTot = keep;""")
    # 쪽마다 줄 수: 요약 (한눈에 칸 밑 + 내 기준과 맞는 정도 카드 — 영역 둘) · 가치 탭 · 가치 자세히 · 배당 탭
    assert got["tsm"] == {"conv": [2, 1, 1, 0], "cur": [0, 0, 0, 0], "ni": [0, 0, 0, 0]}, got["tsm"]
    assert got["baba"] == {"conv": [2, 1, 1, 0], "cur": [2, 0, 0, 1], "ni": [0, 1, 1, 0]}, got["baba"]   # 배당 빈 칸: 통화 줄 (요약 둘 · 배당 탭)
    assert got["asml"] == {"conv": [0, 1, 1, 0], "cur": [2, 1, 1, 1], "ni": [0, 0, 0, 0]}, got["asml"]   # PBR 빈 칸: 통화 줄 · PER 은 바꾼 줄
    assert got["aapl"] == [0, 0, 0, 0]
    assert got["tsmValue"] and got["babaPer"] == 1 and got["asmlPbr"] == 1 and got["tsmDate"]
    assert got["waiting"] == {"tsm": [0, 0, 0, 0], "baba": [0, 0, 0, 0]}            # 줄의 문구가 없으면 그 줄도 없어요 (숫자는 resolveLoad 가 빼요)


def test_compare_cell_carries_the_line_with_a_converted_pbr():
    got = run("""
      const keep = C2.co.fcurTot;
      C2.co.fcurTot = DRAFT;
      const ctx = { stocks: DATA.stocks, points: null, names: {}, load: LOAD, groups: null, row: null, betaShort: false };
      const cell = (t) => { const c = CM.compareCells(LOAD.byT.get(t), null, ctx); return { pbr: [c.pbr.text, c.pbr.note, c.pbr.data], dy: [c.dy.text, c.dy.note] }; };
      out = { tsm: cell('TSM'), baba: cell('BABA'), asml: cell('ASML'), aapl: cell('AAPL') };
      C2.co.fcurTot = keep;""")
    assert got["tsm"]["pbr"][0] == "7.79배" and got["tsm"]["pbr"][1] == filled(DRAFT, "대만 달러") and got["tsm"]["pbr"][2]["conv"] == "1"
    assert got["tsm"]["dy"][1] is None                                                # 배당수익률은 줄 없음
    assert got["baba"]["pbr"][1] == filled(DRAFT, "중국 위안화") and got["baba"]["dy"] == ["–", CUR_LINE.replace("{currency}", "중국 위안화")]
    assert got["asml"]["pbr"] == ["–", CUR_LINE.replace("{currency}", "유로"), {"blank": "fcur"}]
    assert got["aapl"]["pbr"][1] is None and "conv" not in got["aapl"]["pbr"][2]


# ── 문구 · 스위치 · 예전 뱁새 ──
def test_the_switch_and_the_line_go_together():
    got = run("out = { tot: C2.co.fcurTot, ni: C2.co.fcurNi, fgn: C2.co.fgnCut };")
    assert got["ni"] == NI_LINE == got["fgn"]
    assert (got["tot"] is not None) == V.US_FCUR_TOT_ON, "스위치와 바꿔 계산한 줄은 함께 켜요 (승인된 문구를 넣고 스위치를 켜요)"
    if got["tot"] is not None:
        assert got["tot"] == DRAFT or "{currency}" in got["tot"] and "{md}" in got["tot"]
    with open(os.path.join(ROOT, "docs", "tasks", "v18.3-new-strings-pending.md"), encoding="utf-8") as f:
        pending = f.read()
    with open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8") as f:
        approved = f.read()
    if got["tot"] is None:
        assert f"| `co.fcurTot` | {DRAFT} |" in pending
    assert f"| `co.fcurNi` | {NI_LINE} | Jack, 2026-11-27" in approved


def test_the_old_app_keeps_the_114_blanks():
    with open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8") as f:
        src = f.read()
    load = src.split("async function loadLiveData()", 1)[1].split("\n}\n", 1)[0]
    assert "fcurTotStrip(j.stocks)" in load and load.index("fcurTotStrip(j.stocks)") < load.index("warnStaleFields(j")
    assert "fcurTot" not in src.replace("fcurTotStrip", "") .replace("(fcurTot)", "")


def test_a_split_mark_never_takes_over_a_non_dollar_filer():
    """#188 (splCut: 최근 분할한 달러 회사의 숫자를 맞춰 보고 비운 칸)는 fcur 회사에 붙지 않아요 (파이프라인 · 관문이 건너뛰어요). 남은 표시가 있어도
    앱은 fcur 회사의 줄만 말해요: 바꿔 계산한 숫자에는 바꾼 줄, 빈 칸에는 #114 · Sony 줄 — fgnCut 류의 줄은 없어요."""
    got = run("""
      const s = { ...LOAD.byT.get('TSM'), splCut: { per: 'mismatch', pbr: 'currency' } };
      const b = { ...LOAD.byT.get('BABA'), splCut: { per: 'mismatch', dy: 'norecord' } };
      out = {
        cut: [FC.fgnCutOf(s), FC.fgnCutOf(b)], blank: [FC.fgnBlank(s, 'per'), FC.fgnBlank(b, 'per'), FC.fgnBlank(b, 'dy')],
        tot: FC.fcurTotText(s, DRAFT, C2.co.curName, '10월 30일'), ni: FC.fcurNiOf(b), dy: FC.fcurBlankOf(b, 'dy'),
        note: [renderToStaticMarkup(h(FN.FgnCutNote, { s })), renderToStaticMarkup(h(FN.FgnCutNote, { s: b }))],
        dollar: FC.fgnCutOf({ t: 'DOLL', cls: 'us', splCut: { per: 'mismatch' } }),
      };""")
    assert got["cut"] == [[], []] and got["blank"] == [False, False, False] and got["note"] == ["", ""]
    assert got["tot"] == filled(DRAFT, "대만 달러") and got["ni"] is True and got["dy"] is True
    assert got["dollar"] == ["per"]                                                  # 달러 회사의 splCut 은 그대로 읽어요 (#188)
