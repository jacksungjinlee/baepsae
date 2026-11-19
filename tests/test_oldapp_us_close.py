# -*- coding: utf-8 -*-
"""예전 뱁새의 미국 종가 날짜 (Jack, 2026-11-19 · 답 6 "Yes") — Node 로 실제 컴포넌트를 그려서 봐요.

예전 뱁새 포트폴리오 첫 화면(어떻게 시작할까요?)의 데이터 칸: '가격은 {md} 공식 종가예요. 다른 수치는 추정치예요.'(T_PX_OFFICIAL)의 {md} 는
한국 종가 날짜(data.json pxDate)예요. 미국 종목 가격은 미국 종가 날짜(usPxDate)의 것이라, 두 날짜가 다른 날(미국 휴장 뒤 · 늦은 미국 종가)에는
그 문단 바로 아래에 2.0 의 승인 문장 '미국 종목은 현지 기준 {md} 종가예요.'(src/copy/v2.js app.usClose, CSV 26)를 글자 그대로 한 줄.

- 날짜가 다르고 오늘 데이터에 달러 가격 종목(ccy "USD")이 있을 때만 · {md} 는 usPxDate (예전 뱁새의 월 · 일, data.js mdOf)
- 같은 날 · 달러 종목 없음(379800 KODEX 미국S&P500 은 cls "us" 지만 원화라 세지 않아요) · 못 읽는 날짜 · 못 불러온 날: 예전과 글자 하나 다르지 않아요
- 영어 화면: 승인된 영어 문장이 없어 예전 그대로
- 문단은 언제나 예전 글자 그대로 (smoke_app.py 의 '공식 종가예요. 다른 수치는 추정치예요' 확인이 발행 전 화면 검사에서도 그대로 통과해요)
- data.json 을 읽을 때(loadLiveData) usPxDate 와 달러 종목 여부를 실어 보내고, 달러 종목이 있는데 usPxDate 를 못 읽으면 console 에 크게
브라우저 화면은 tests/smoke_app.py 장면 '미국종가'가 봐요.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

from copytrace import copy_strings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"DT": "src/detail.jsx", "CP": "src/copy/v2.js"}
US_CLOSE = "미국 종목은 현지 기준 {md} 종가예요."
OFFICIAL = "공식 종가예요. 다른 수치는 추정치예요"          # tests/smoke_app.py OFFICIAL (발행 전 화면 검사가 찾는 글자)
KR, US = "2026-11-26", "2026-11-25"                     # 추수감사절 다음 날처럼: 한국 11-26 · 미국 11-25
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-usclose-")
        with open(os.path.join(tmp, "entry.js"), "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, os.path.join(tmp, "entry.js"), "--bundle", "--format=esm", "--platform=node", "--jsx=automatic",
                            "--loader:.js=jsx", "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs",
                            "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


def run(body, **data):
    tmp = bundle_dir()
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { DT } = B; const C2 = B.CP.C;\n"
            "const WARN = []; console.warn = (m) => WARN.push(String(m)); console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const PUB = new Date().toISOString();\n"
            "const info = (o) => ({ live: true, failed: false, asOf: '2026-11-27', pxDate: KR, publishedAt: PUB, staleAfter: null, nextPub: null,"
            " usPxDate: US, usStocks: true, ...o });\n"
            "const before = (o) => { const x = info(o); delete x.usPxDate; delete x.usStocks; return x; };   // 이 PR 전의 모양 (두 칸 없음)\n"
            "const screen = (dataInfo, lang = 'ko') => renderToStaticMarkup(h(DT.LaunchScreen, { lang, t: (k) => k, slots: [], onNew() {}, onOpen() {},"
            " onDelete() {}, onRename() {}, onImport() {}, dataInfo }));\n"
            f"const KR = {json.dumps(KR)}, US = {json.dumps(US)};\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


# ── 글자: 2.0 의 승인 문장 그대로 · 승인 기록 · 예전 문장은 그대로 ──
def test_the_line_is_the_approved_2_0_line_word_for_word():
    c, _ = copy_strings()
    assert c["app"]["usClose"] == US_CLOSE
    got = run("out = { ko: DT.T_US_CLOSE.ko, en: DT.T_US_CLOSE.en, px: DT.T_PX_OFFICIAL };")
    assert got["ko"] == US_CLOSE                                    # 예전 뱁새의 글자 = 2.0 app.usClose
    assert got["en"] is None                                        # 승인된 영어가 없어요: 영어 화면은 예전 그대로
    assert got["px"] == {"ko": "가격은 {md} 공식 종가예요. 다른 수치는 추정치예요.",
                         "en": "Prices are official closes from {md}. Other figures are estimates."}   # 예전 문장은 손대지 않아요
    with open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8") as f:
        rows = [ln for ln in f.read().splitlines() if ln.startswith("| Old app") and US_CLOSE in ln]
    assert len(rows) == 1 and "| Jack, 2026-11-19" in rows[0] and "T_US_CLOSE" in rows[0], rows   # 승인 기록 (예전 뱁새는 키 대신 자리)


# ── 규칙: usCloseLine ──
def test_the_rule_dates_differ_and_dollar_stocks_in_todays_data():
    got = run("""
      const L = (o, lang = 'ko') => DT.usCloseLine(info(o), lang);
      out = {
        differ: L({}), later: L({ usPxDate: '2026-11-27' }), same: L({ usPxDate: KR }), noUsd: L({ usStocks: false }),
        en: L({}, 'en'), failed: L({ live: false, failed: true }), notLive: L({ live: false }), noUs: L({ usPxDate: null }),
        badUs: L({ usPxDate: '11/25/2026' }), stampUs: L({ usPxDate: '2026-11-25T06:00:00+09:00' }), noKr: L({ pxDate: null }),
        before: DT.usCloseLine(before({}), 'ko'), none: DT.usCloseLine(null, 'ko'),
      };""")
    assert got["differ"] == "미국 종목은 현지 기준 11월 25일 종가예요.", got["differ"]
    assert got["later"] == "미국 종목은 현지 기준 11월 27일 종가예요."      # 한국이 쉰 날 (미국이 더 새 날짜): 그래도 맞는 말
    for k in ("same", "noUsd", "en", "failed", "notLive", "noUs", "badUs", "stampUs", "noKr", "before", "none"):
        assert got[k] is None, (k, got[k])


# ── 화면: 첫 화면 데이터 칸 (LaunchScreen) ──
def test_launch_screen_adds_one_line_right_under_the_unchanged_paragraph():
    got = run("""
      const ls = lines(screen(info({})));
      out = { ls, base: lines(screen(info({ usPxDate: KR }))), html: screen(info({})) };""")
    para = "가격은 11월 26일 공식 종가예요. 다른 수치는 추정치예요. 주문 전엔 증권사 앱에서 실제 시세를 확인하세요."
    ls = got["ls"]
    assert ls.count(para) == 1 and OFFICIAL in para, ls             # 문단은 예전 그대로 (발행 전 화면 검사의 글자도 그대로)
    i = ls.index(para)
    assert ls[i - 1] == "11월 26일 기준" and ls[i + 1] == "미국 종목은 현지 기준 11월 25일 종가예요.", ls[i - 1:i + 2]
    assert sum("미국 종목은" in x for x in ls) == 1
    assert ls[:i + 1] + ls[i + 2:] == got["base"]                   # 그 한 줄 말고는 같은 날의 화면과 똑같아요
    assert 'data-us-close="1"' in got["html"] and "font-size:12px" in got["html"].split('data-us-close="1"', 1)[1].split(">", 1)[0]


def test_launch_screen_is_unchanged_when_the_line_does_not_apply():
    """같은 날 · 달러 종목 없음 · 못 읽는 미국 날짜 · 영어 화면 · 못 불러온 날: 이 PR 전의 화면과 글자 하나 다르지 않아요 (HTML 그대로)."""
    got = run("""
      const pair = (now, old, lang = 'ko') => [screen(now, lang), screen(old, lang)];
      out = {
        same: pair(info({ usPxDate: KR }), before({})),
        noUsd: pair(info({ usStocks: false }), before({})),
        badUs: pair(info({ usPxDate: null }), before({})),
        en: pair(info({}), before({}), 'en'),
        enSame: pair(info({ usPxDate: KR }), before({}), 'en'),
        failed: pair(info({ live: false, failed: true, pxDate: null, usPxDate: null, usStocks: false }), before({ live: false, failed: true, pxDate: null })),
      };
      out.en.push(lines(out.en[0]));""")
    for k, v in got.items():
        assert v[0] == v[1], k                                       # 그대로
        assert "미국 종목은" not in v[0] and "data-us-close" not in v[0], k
    assert "Prices are official closes from Nov 26. Other figures are estimates. Check real quotes in your brokerage app before ordering." in got["en"][2]


# ── 읽기: loadLiveData 가 usPxDate · 달러 종목 여부를 실어 보내요 ──
def test_load_live_data_carries_the_us_date_and_whether_dollar_stocks_are_in():
    usd = {"t": "AAPL", "nk": "Apple Inc.", "cls": "us", "ccy": "USD", "price": 230.0, "beta": 1.1, "vol": 25.0}
    kr = {"t": "005930", "nk": "삼성전자", "cls": "kr", "price": 70000.0, "beta": 1.0, "vol": 25.0}
    fund = {"t": "379800", "nk": "KODEX 미국S&P500", "cls": "us", "price": 22000.0, "beta": 1.0, "vol": 16.0}   # cls us · 원화 (ccy 없음)
    head = {"asOf": "2026-11-27", "pxDate": KR, "publishedAt": "2026-11-27T06:40:00+09:00", "staleAfter": "2026-11-28T16:47:00+09:00",
            "nextPub": "2026-11-28"}
    files = {"both": {**head, "usPxDate": US, "stocks": [kr, usd, fund]},
             "krOnly": {**head, "usPxDate": US, "stocks": [kr, fund]},
             "noUsDate": {**head, "stocks": [kr, usd]},
             "badUsDate": {**head, "usPxDate": "11/25", "stocks": [kr, usd]},
             "krOnlyNoUsDate": {**head, "stocks": [kr, fund]}}
    got = run("""
      out = {};
      for (const [k, j] of Object.entries(FILES)) {
        globalThis.fetch = async () => ({ ok: true, status: 200, text: async () => JSON.stringify(j) });
        WARN.length = 0;
        const L = await DT.loadLiveData();
        out[k] = { us: L.usPxDate, usd: L.usStocks, px: L.pxDate, line: DT.usCloseLine({ live: true, failed: false, ...L }, 'ko'),
          warn: WARN.filter((w) => w.includes('usPxDate')) };
      }""", FILES=files)
    assert got["both"] == {"us": US, "usd": True, "px": KR, "line": "미국 종목은 현지 기준 11월 25일 종가예요.", "warn": []}, got["both"]
    assert got["krOnly"] == {"us": US, "usd": False, "px": KR, "line": None, "warn": []}, got["krOnly"]   # 379800 은 달러 종목이 아니에요
    for k in ("noUsDate", "badUsDate"):                              # 달러 종목이 있는데 날짜를 못 읽으면: 줄 없음 · console 에 크게
        assert got[k]["us"] is None and got[k]["usd"] is True and got[k]["line"] is None, (k, got[k])
        assert len(got[k]["warn"]) == 1 and "첫 화면 데이터 칸에 미국 종목의 종가 날짜를 말하지 않아요" in got[k]["warn"][0], (k, got[k])
        assert "달러 종목 1개" in got[k]["warn"][0], got[k]["warn"]
    assert got["krOnlyNoUsDate"]["warn"] == [] and got["krOnlyNoUsDate"]["line"] is None    # 달러 종목이 없으면 알릴 것도 없어요
