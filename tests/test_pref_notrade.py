# -*- coding: utf-8 -*-
"""우선주 · 거래 없음 · 오늘 등락률 줄 (Jack 2026-11-14: design chat 2026-11-08 의 승인 문구, say-why 22 · 23 · 29 · 42 · dart-gaps §9).

파이프라인 (fetch_data.py):
- 기준일 목록 파일의 행이 거래량 0 · 시가 0 · 거래대금 0 이면 그 종목은 noTrade · d1 빈 칸 (0.00% 가 아니에요) · d1Why "noTrade" · 기준가 변화는
  ntD1 (포트폴리오 평가 금액에만). 다른 빈 d1 은 d1Why (range ±30% 밖 · new 직전 행 없음 · prev 직전 파일을 쓸 수 없음). 발행 종목의 이유별 수는
  d1Blank. 거래 없는 행이 너무 많으면 (파일의 잘못) 아무도 표시하지 않고, 필수 종목은 표시하지 않아요 (한 행의 잘못이 모두를 막지 않게).
- 상한가 · 하한가(정확히 ±30%)는 d1 이 남아요 (부동소수점 끝자리 때문에 비던 것: 11-13 디와이에이).
관문 (validate_data.py check_kr_no_trade): 우리 값끼리 어긋날 때만 실패 · 그 전 형식은 경고 · 출처 쪽 문제는 경고.
앱 (src/v2): 회사 페이지 머리 · 홈 가진 종목 · 포트폴리오 가진 종목 · 종목 목록에 "{md} 거래 없음 (거래정지일 수 있어요)" 또는 "오늘 등락률은 받지
못했어요." · 우선주 페이지 머리 밑 "우선주라 회사 숫자는 보통주 페이지에서 볼 수 있어요." · 내 기준과 맞는 정도 밑 "우선주는 순위를 매기지 않아요." ·
점검의 "우선주·ETF처럼 …" (스위치 꺼짐: 기존 시험 한 줄을 바꿔야 해서 Jack 의 답을 기다려요). 거래 없는 종목도 포트폴리오의 '오늘'은 그대로예요.
"""
import collections
import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import fetch_data as F  # noqa: E402
import validate_data as V  # noqa: E402
from fixture_data import good_pair  # noqa: E402

NODE = shutil.which("node")
FIX = os.path.join(ROOT, "tests", "fixtures", "v2")
D12, D13 = dt.date(2026, 11, 12), dt.date(2026, 11, 13)
PREF_LINE = "우선주라 회사 숫자는 보통주 페이지에서 볼 수 있어요."
FIT_LINE = "우선주는 순위를 매기지 않아요."
NT_LINE = "{md} 거래 없음 (거래정지일 수 있어요)"
MISS_LINE = "오늘 등락률은 받지 못했어요."
UNSC_LINE = "우선주·ETF처럼 기준 점수가 없는 종목 {n}개({names})는 비중에만 넣었어요."
COLS = ["Code", "Name", "Market", "Open", "Volume", "Amount", "Marcap", "Stocks"]


def listing(rows):
    """[(코드, 이름, 시가, 거래량, 거래대금, 공식 종가, 주식 수)] → 목록 파일 모양 (Marcap = 종가 × 주식 수)."""
    return pd.DataFrame([[c, n, "KOSPI", o, v, a, px * sh, sh] for c, n, o, v, a, px, sh in rows], columns=COLS)


# ── 파이프라인: 거래 없음 · 빈 d1 의 이유 ──
def test_no_trade_needs_volume_open_and_amount_zero():
    df = listing([("001570", "금양", 0, 0, 0, 9900, 100), ("005930", "삼성전자", 214000, 12829515, 2.6e12, 206000, 100),
                  ("999990", "어긋남", 0, 0, 5e6, 1000, 10), ("888880", "모름", float("nan"), 0, 0, 1000, 10),
                  ("777770", "시가만", 0, 10, 1e4, 1000, 10)])
    nt, cols, odd = F.kr_no_trade(df)
    assert nt == {"001570"} and cols is True and odd == {"999990"}           # 비었거나 숫자가 아니면 모름 · 거래대금이 있으면 어긋난 행
    assert F.kr_no_trade(df.drop(columns=["Volume"])) == (set(), False, set())   # 열이 없으면 누구도 표시하지 않아요
    assert F.kr_no_trade(df.drop(columns=["Amount"]))[0] == {"001570", "999990"}  # 거래대금 칸이 없으면 거래량 · 시가만으로


def test_d1_split_gives_every_blank_its_reason():
    cur = listing([("001570", "금양", 0, 0, 0, 9900, 100), ("000020", "보통", 1, 1, 1, 10500, 100), ("000030", "재개", 1, 1, 1, 20000, 100),
                   ("000040", "새로", 1, 1, 1, 5000, 100), ("000050", "코넥스", 0, 0, 0, 2895, 100), ("000060", "정지 재평가", 0, 0, 0, 18360, 100)])
    prev = listing([("001570", "금양", 0, 0, 0, 9900, 100), ("000020", "보통", 1, 1, 1, 10000, 100), ("000030", "재개", 1, 1, 1, 10000, 100),
                    ("000050", "코넥스", 0, 0, 0, 2900, 100), ("000060", "정지 재평가", 0, 0, 0, 3530, 100)])
    d1, _, _ = F.kr_d1_val20(cur, [(D12, prev)], prev_final=True)
    nt, _, _ = F.kr_no_trade(cur)
    out, why, ntm, n = F.kr_d1_split(cur, [(D12, prev)], True, d1, nt)
    assert out == {"000020": 5.0}                                              # 거래 없는 종목은 d1 이 빠져요 (0.00 이 아니에요)
    assert why == {"001570": "noTrade", "000030": "range", "000040": "new", "000050": "noTrade", "000060": "noTrade"}
    assert ntm == {"001570": 0.0, "000050": round((2895 / 2900 - 1) * 100, 2)}  # 기준가 변화 (코넥스는 거래 없이 움직여요) · ±30% 밖은 없음
    assert n == collections.Counter({"noTrade": 3, "range": 1, "new": 1})
    out, why, ntm, n = F.kr_d1_split(cur, [(D12, prev)], False, {}, nt)      # 직전 파일을 쓸 수 없으면 모두 prev (거래 없는 종목은 noTrade)
    assert out == {} and ntm == {} and why["000020"] == why["000040"] == "prev" and why["001570"] == "noTrade"
    assert F.kr_d1_split(cur, [], True, {}, set())[1]["000020"] == "prev"


def test_limit_up_and_limit_down_keep_their_d1():
    # 11-13 디와이에이: 3,100 → 4,030 (상한가, 정확히 +30%) 인데 (4030 / 3100 − 1) × 100 = 30.000000000000004 라 빈 칸이 됐어요
    assert (4030 / 3100 - 1) * 100 > 30
    cur = listing([("002880", "디와이에이", 3100, 641665, 2.48e9, 4030, 9354799), ("000070", "하한가", 1, 1, 1, 7000, 10),
                   ("000080", "넘음", 1, 1, 1, 13010, 10)])
    prev = listing([("002880", "디와이에이", 3130, 4439, 1.4e7, 3100, 9354799), ("000070", "하한가", 1, 1, 1, 10000, 10),
                    ("000080", "넘음", 1, 1, 1, 10000, 10)])
    d1, _, cnt = F.kr_d1_val20(cur, [(D12, prev)], prev_final=True)
    assert d1 == {"002880": 30.0, "000070": -30.0} and cnt["d1 범위 밖 → 빈 칸"] == 1    # 30.1% 는 여전히 빈 칸
    assert all(abs(v) <= V.D1_MAX_KR for v in d1.values())                                # 관문의 국내 d1 범위 줄과 같은 값


def test_too_many_no_trade_rows_mark_nobody():
    assert F.no_trade_unseen({str(i) for i in range(66)}, 2474) is None                  # 11-13: 66 / 2,474 (발행) · 135 / 2,877 (파일)
    assert F.no_trade_unseen({str(i) for i in range(700)}, 2474) == "many"
    assert F.NO_TRADE_MAX_SHARE * 2877 > 135 * 4                                         # 오늘의 네 배보다 넉넉해요


def test_d1_blank_counts_only_published_korean_listings():
    rows = [{"t": "001570", "cls": "kr", "d1Why": "noTrade", "noTrade": True}, {"t": "000030", "cls": "kr", "d1Why": "range"},
            {"t": "005930", "cls": "kr", "d1": 1.0}, {"t": "AAPL", "cls": "us"}]
    got = F.d1_blank_counts(rows, True, None, {"001570", "123450"}, {"005930"})
    assert got == {"noTrade": 1, "range": 1, "new": 0, "prev": 0, "seen": True, "odd": ["001570"], "must": ["005930"]}
    assert F.d1_blank_counts([], False, "cols") == {"noTrade": 0, "range": 0, "new": 0, "prev": 0, "seen": False, "unseen": "cols", "odd": [], "must": []}


def test_pipeline_writes_the_marks_and_documents_them():
    src = open(os.path.join(ROOT, "fetch_data.py"), encoding="utf-8").read()
    assert '"noTrade": True if code in no_trade and code in d1_why else None' in src
    assert '"d1Why": d1_why.get(code), "ntD1": nt_map.get(code)' in src
    assert '"d1Blank": kmeta.get("d1Blank")' in src and '"krSeries": krs, "d1Blank": d1_blank}' in src
    assert "no_trade -= set(nt_must)" in src                                           # 필수 종목은 표시하지 않아요
    for k in ("noTrade", "d1Why", "ntD1", "d1Blank"):
        assert k in F.UNITS, k
    assert "noTrade" in F.UNITS["d1"] and "d1Why" in F.UNITS["d1"]
    assert F.D1_WHY is V.D1_WHY                                                         # 파이프라인과 관문의 이유 목록은 한 곳


# ── 관문 ──
def kr_row(t, nk="가", d1=1.0, **kw):
    r = {"t": t, "nk": nk, "cls": "kr", "price": 1000.0, "val": 1.0, **kw}
    if d1 is not None:
        r["d1"] = d1
    return r


def good():
    stocks = [kr_row("005930", "삼성전자"), kr_row("001570", "금양", None, val=0.0, noTrade=True, d1Why="noTrade", ntD1=0.0),
              kr_row("000050", "코넥스", None, val=0.0, noTrade=True, d1Why="noTrade", ntD1=-0.17),
              kr_row("000030", "재개", None, d1Why="range"), kr_row("069500", "KODEX 200", None, fund=True, etf=True),
              {"t": "AAPL", "cls": "us", "price": 1.0, "pxd": "2026-11-11"}]
    return {"stocks": stocks, "d1Blank": {"noTrade": 2, "range": 1, "new": 0, "prev": 0, "seen": True, "odd": [], "must": []}}


def gate(data, pdata=None):
    rep = V.Report()
    V.check_kr_no_trade(rep, data, pdata)
    return {r[0]: (r[3], r[1]) for r in rep.rows}, rep


NAME = "국내 거래 없는 종목 · 빈 d1 이유 (noTrade · d1Why)"
WNAME = "국내 거래 없는 종목: 목록 파일의 칸 (경고만)"


def test_gate_passes_consistent_marks():
    rows, rep = gate(good())
    assert rows[NAME][0] == "PASS" and rows[WNAME][0] == "PASS", rows
    assert "거래 없음 2" in rows[NAME][1]
    names = dict(rep.details)
    assert names["기준일에 거래가 없던 국내 종목 (d1 빈 칸 · 앱: '{md} 거래 없음 (거래정지일 수 있어요)')"] == ["001570 금양", "000050 코넥스 (기준가 -0.17%)"]


def bad(fn):
    d = good()
    fn(d)
    return d


BY = lambda d, t: next(s for s in d["stocks"] if s["t"] == t)  # noqa: E731


@pytest.mark.parametrize("why,fn", [
    ("거래 없음인데 d1 숫자 (0.00% 로 보여요)", lambda d: BY(d, "001570").update(d1=0.0)),
    ("거래 없음인데 다른 이유", lambda d: BY(d, "001570").update(d1Why="range")),
    ("이유는 거래 없음인데 표시가 없음", lambda d: BY(d, "001570").pop("noTrade")),
    ("noTrade 가 true 가 아님", lambda d: BY(d, "001570").update(noTrade=1)),
    ("거래 없음인데 거래대금", lambda d: BY(d, "001570").update(val=3.2)),
    ("이유 없는 빈 d1", lambda d: BY(d, "000030").pop("d1Why")),
    ("모르는 이유", lambda d: (BY(d, "000030").update(d1Why="halt"))),
    ("d1 이 있는데 이유", lambda d: BY(d, "005930").update(d1Why="range")),
    ("거래 없음이 아닌데 ntD1", lambda d: BY(d, "005930").update(ntD1=0.0)),
    ("ntD1 ±30% 밖", lambda d: BY(d, "000050").update(ntD1=420.0)),
    ("ntD1 숫자가 아님", lambda d: BY(d, "000050").update(ntD1="0")),
    ("미국 종목에 noTrade", lambda d: BY(d, "AAPL").update(noTrade=True, d1Why="noTrade")),
    ("펀드에 d1Why", lambda d: BY(d, "069500").update(d1Why="range")),
    ("요약 수가 종목과 다름", lambda d: d["d1Blank"].update(noTrade=3)),
    ("요약에 이유 칸이 없음", lambda d: d["d1Blank"].pop("range")),
    ("seen 모양", lambda d: d["d1Blank"].update(seen="yes")),
    ("가리지 않았다면서 표시", lambda d: d["d1Blank"].update(seen=False, unseen="cols")),
    ("odd 모양", lambda d: d["d1Blank"].update(odd="001570")),
    ("표시하지 않았다는 종목에 표시", lambda d: d["d1Blank"].update(must=["001570"])),
    ("요약 없이 표시만", lambda d: d.pop("d1Blank")),
])
def test_gate_fails_on_our_own_inconsistency(why, fn):
    rows, _ = gate(bad(fn))
    assert rows[NAME][0] == "FAIL", (why, rows[NAME])


def test_gate_only_warns_on_source_problems_and_the_old_format():
    d = good()
    for s in d["stocks"]:
        for k in ("noTrade", "d1Why", "ntD1"):
            s.pop(k, None)
    d.pop("d1Blank")
    rows, _ = gate(d)
    assert rows[NAME][0] == "WARN" and rows[WNAME][0] == "WARN", rows            # 그 전 형식 (지금 사이트 · 시험 데이터)
    rows, _ = gate(d, pdata={"d1Blank": {"noTrade": 0}})
    assert rows[NAME][0] == "FAIL"                                                # 직전 발행본에는 있었어요: 단계가 돌지 않았어요
    unseen = bad(lambda x: [s.pop(k, None) for s in x["stocks"] if s.get("noTrade") for k in ("noTrade", "d1Why", "ntD1")])
    unseen["stocks"] = [dict(s, d1=0.0) if s["t"] in ("001570", "000050") else s for s in unseen["stocks"]]
    unseen["d1Blank"].update(noTrade=0, seen=False, unseen="many")
    rows, _ = gate(unseen)
    assert rows[NAME][0] == "PASS" and rows[WNAME][0] == "WARN" and "너무 많아" in rows[WNAME][1], rows
    odd = bad(lambda x: x["d1Blank"].update(odd=["005930"], must=["005930"]))
    rows, _ = gate(odd)
    assert rows[NAME][0] == "PASS" and rows[WNAME][0] == "WARN" and "005930 삼성전자" in rows[WNAME][1], rows


def test_gate_row_runs_in_the_full_check_and_good_data_with_marks_passes():
    import test_validate as TV
    cur, prev, final = good_pair()
    kr = [s for s in cur["data"]["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    t = next(s for s in kr if s["t"] not in V.MUST)
    t.pop("d1")
    t.update(noTrade=True, d1Why="noTrade", ntD1=0.0, val=0.0)
    cur["data"]["d1Blank"] = F.d1_blank_counts(kr, True)
    rep = TV.check(cur, prev, final)
    st = {r[0]: r[3] for r in rep.rows}
    assert not rep.failed, rep.table()
    assert st[NAME] == "PASS" and st[WNAME] == "PASS"
    t["d1"] = 0.0
    assert NAME in TV.failed_names(TV.check(cur, prev, final))


def test_real_listing_files_of_2026_11_13():
    """11-13 의 진짜 목록 파일 (FinanceData 캐시) 두 개: 거래 없는 행 135 · 그중 발행 종목 66 은 사이트에 있어요 (PR 본문). 여기서는 파일이 저장소에
    없어서 같은 모양의 행만 봐요: 금양 · STX (정지) · EMB (코넥스) 는 거래 없음 · 디와이에이 상한가는 d1 30.0."""
    cur = listing([("001570", "금양", 0, 0, 0, 9900, 64100000), ("011810", "STX", 0, 0, 0, 18360, 28666000),
                   ("278990", "EMB", 0, 0, 0, 2895, 5000000), ("002880", "디와이에이", 3100, 641665, 2482588807, 4030, 9354799)])
    prev = listing([("001570", "금양", 0, 0, 0, 9900, 64100000), ("011810", "STX", 0, 0, 0, 18360, 28666000),
                    ("278990", "EMB", 0, 0, 0, 2895, 5000000), ("002880", "디와이에이", 3130, 4439, 13856740, 3100, 9354799)])
    d1, _, _ = F.kr_d1_val20(cur, [(D12, prev)], prev_final=True)
    nt, cols, odd = F.kr_no_trade(cur)
    out, why, ntm, n = F.kr_d1_split(cur, [(D12, prev)], True, d1, nt)
    assert out == {"002880": 30.0} and set(why) == {"001570", "011810", "278990"} and set(why.values()) == {"noTrade"}
    assert ntm == {"001570": 0.0, "011810": 0.0, "278990": 0.0}


# ── 앱 (Node) ──
MODS = {"E": "src/v2/engine.js", "FN": "src/v2/fixnote.jsx", "CO": "src/v2/company.jsx", "CP": "src/copy/v2.js", "Hm": "src/v2/home.js",
        "R": "src/v2/rules.js", "T": "src/v2/track.js", "P": "src/v2/pf.js", "RP": "src/v2/report.jsx", "ST": "src/v2/stocks.jsx",
        "PV": "src/v2/pfview.jsx"}
_B = {}
NT_T, MISS_T, PREF_T = "024060", "396270", "005935"     # 시험 데이터: 흥구석유 (거래 없음으로) · 넥스트칩 (±30% 밖으로) · 삼성전자우


def marked_fixture():
    """2.0 시험 데이터에 파이프라인이 다는 표시를 두 종목에 (흥구석유: 거래 없음 · 넥스트칩: ±30% 밖)."""
    with open(os.path.join(FIX, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    for s in data["stocks"]:
        if s["t"] == NT_T:
            s.pop("d1", None)
            s.update(noTrade=True, d1Why="noTrade", ntD1=0.0)
        if s["t"] == MISS_T:
            s.pop("d1", None)
            s["d1Why"] = "range"
    kr = [s for s in data["stocks"] if s.get("cls") == "kr" and not s.get("fund")]
    data["d1Blank"] = F.d1_blank_counts(kr, True)
    return data


@pytest.fixture(scope="module")
def bundle():
    if NODE is None:
        pytest.skip("node 가 없어요")
    tmp = tempfile.mkdtemp(prefix="baepsae-pref-")
    entry = os.path.join(tmp, "entry.js")
    with open(entry, "w", encoding="utf-8") as f:
        for k, v in MODS.items():
            f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx", "--charset=utf8",
                        f"--outfile={tmp}/b.mjs", "--log-level=error", "--external:react", "--external:react-dom"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
    for name, obj in (("data.json", marked_fixture()),):
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    shutil.copy(os.path.join(FIX, "corp.json"), os.path.join(tmp, "corp.json"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def run(bundle, body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "import fs from 'fs';\nconst { E, FN, CO, CP, Hm, R, T, P, RP, ST, PV } = B; const C2 = CP.C;\n"
            "const warns = []; console.warn = (m) => warns.push(String(m)); console.info = () => {};\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const text = (html) => ent(html.replace(/<!--.*?-->/g, '').replace(/<[^>]+>/g, '\\n'));\n"
            "const count = (html, s) => text(html).split(s).length - 1;\n"
            "const marks = (html, id) => (html.match(new RegExp('data-ui-v2=\"' + id + '\"', 'g')) || []).length;\n"
            "const DATA = JSON.parse(fs.readFileSync('./data.json', 'utf8')); const CORP = JSON.parse(fs.readFileSync('./corp.json', 'utf8'));\n"
            "const LOAD = { status: 'ok', data: DATA, corp: CORP, fresh: { md: null, days: 0, stale: false }, byT: new Map(DATA.stocks.map((s) => [s.t, s])),"
            " coByT: new Map(CORP.companies.map((x) => [x.t, x])), preview: false };\n"
            "const STORE = { data: { decks: [], notes: {}, assume: {} }, writable: false };\n"
            "const page = (code, ctab = null, load = LOAD, store = STORE) => renderToStaticMarkup(h(CO.Company, { load, store, setStoreData() {}, pad: 0, code, ctab,"
            " disc: { status: 'none' }, nav: { setTab() {}, more() {}, back() {}, onWhy() {} } }));\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=bundle, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_five_lines_are_the_approved_words_and_recorded(bundle):
    got = run(bundle, "out = [C2.co.pref, C2.co.fit.pref, C2.co.noTrade, C2.co.d1Missing, C2.rpt.unscoredPref, C2.rpt.unscored];")
    assert got == [PREF_LINE, FIT_LINE, NT_LINE, MISS_LINE, UNSC_LINE, "기준 점수를 매길 수 없는 종목 {n}개({names})는 비중에만 넣었어요."]
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    for key, line in (("co.pref", PREF_LINE), ("co.fit.pref", FIT_LINE), ("co.noTrade", NT_LINE), ("co.d1Missing", MISS_LINE),
                      ("rpt.unscoredPref", UNSC_LINE)):
        assert f"| `{key}` | {line} | Jack, 2026-11-14: design chat 2026-11-08, relayed by Jack 2026-11-14" in appr, key
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as f:
        html = f.read()
    for line in (PREF_LINE, FIT_LINE, NT_LINE, MISS_LINE, UNSC_LINE):
        assert html.count(line) == 1, line                                          # 빌드한 2.0 에 한 번씩 (다시 빌드했어요)
    for name in ("baepsae.html",):
        with open(os.path.join(ROOT, name), encoding="utf-8") as f:
            old = f.read()
        assert not any(x in old for x in (PREF_LINE, FIT_LINE, "거래정지일 수 있어요", MISS_LINE))   # 예전 뱁새에는 아직 없어요 (제안만)


def test_engine_tells_no_trade_from_other_blanks(bundle):
    got = run(bundle, """
      const s = (o) => ({ t: '000010', cls: 'kr', price: 1, ...o });
      const cases = [s({ d1: 1.2 }), s({ noTrade: true, d1Why: 'noTrade', ntD1: 0 }), s({ noTrade: true, ntD1: -0.17 }), s({ d1Why: 'range' }), s({}),
        { t: 'AAPL', cls: 'us', price: 1, pxd: '2026-11-11' }, { t: 'AAPL', cls: 'us', price: 1, noTrade: true }, s({ noTrade: 'yes' }), s({ noTrade: true, d1: 0 })];
      out = cases.map((x) => [E.noTradeOf(x), E.d1MissingOf(x), E.todayD1(x), E.valueD1(x)]);""")
    assert got == [[False, False, 1.2, 1.2], [True, False, None, 0], [True, False, None, -0.17], [False, True, None, None], [False, True, None, None],
                   [False, False, None, None], [False, False, None, None], [False, True, None, None], [True, False, 0, 0]]


def test_day_note_text_and_markup(bundle):
    got = run(bundle, """
      const nt = LOAD.byT.get(NT_T), miss = LOAD.byT.get(MISS_T), sam = LOAD.byT.get('005930'), us = LOAD.byT.get('AAPL');
      const f = (s, md) => FN.dayNoteOf(s, md);
      out = { nt: f(nt, '10월 30일'), ntNoDate: f(nt, null), miss: f(miss, '10월 30일'), sam: f(sam, '10월 30일'), us: f(us, '10월 30일'),
        html: renderToStaticMarkup(h(FN.DayNote, { s: nt, md: '10월 30일' })), span: renderToStaticMarkup(h(FN.DayNote, { s: miss, md: '10월 30일', block: false })),
        none: renderToStaticMarkup(h(FN.DayNote, { s: sam, md: '10월 30일' })) };""", NT_T=NT_T, MISS_T=MISS_T)
    assert got["nt"] == {"kind": "noTrade", "text": "10월 30일 거래 없음 (거래정지일 수 있어요)"} and got["ntNoDate"] is None
    assert got["miss"] == {"kind": "missing", "text": MISS_LINE} and got["sam"] is None and got["us"] is None
    assert got["html"].startswith("<div") and 'data-ui-v2="day-note"' in got["html"] and 'data-kind="noTrade"' in got["html"]
    assert "font-size:13px" in got["html"].replace(" ", "")                          # 12px 이상 · 가격 빨강 · 파랑이 아니에요
    assert got["span"].startswith("<span") and MISS_LINE in got["span"] and got["none"] == ""


def test_company_header_says_why_there_is_no_change(bundle):
    got = run(bundle, """
      const one = (t) => [null, 'earn', 'value', 'div'].map((ct) => { const x = page(t, ct); const i = x.indexOf('data-ui-v2="co-head"'), j = x.indexOf('</section>', i);
        const head = x.slice(i, j); return { nt: count(x, '거래 없음 (거래정지일 수 있어요)'), miss: count(x, C2.co.d1Missing), change: marks(head, 'co-change'),
          date: marks(head, 'co-date'), inHead: marks(head, 'day-note'), pref: count(x, C2.co.pref), fit: count(x, C2.co.fit.pref) }; });
      out = { nt: one(NT_T), miss: one(MISS_T), sam: one('005930'), pref: one(PREF_T), us: one('AAPL') };
      const x = page(NT_T); out.order = [x.indexOf('data-ui-v2="co-price"'), x.indexOf('data-ui-v2="day-note"'), x.indexOf('data-ui-v2="co-tabs"')];
      out.ntText = text(x).split('\\n').filter((l) => l.includes('거래 없음'));""", NT_T=NT_T, MISS_T=MISS_T, PREF_T=PREF_T)
    for tab in got["nt"]:
        assert tab["nt"] == 1 and tab["inHead"] == 1 and tab["change"] == 0 and tab["date"] == 1 and tab["miss"] == 0, tab   # 0.0% 없음 · 종가 날짜는 그대로
    assert got["ntText"] == ["10월 30일 거래 없음 (거래정지일 수 있어요)"]
    for tab in got["miss"]:
        assert tab["miss"] == 1 and tab["inHead"] == 1 and tab["change"] == 0 and tab["nt"] == 0, tab
    for tab in got["sam"] + got["us"]:
        assert tab["nt"] == tab["miss"] == tab["inHead"] == tab["pref"] == 0 and tab["change"] == 1, tab
    assert got["order"][0] < got["order"][1] < got["order"][2]
    assert [t["pref"] for t in got["pref"]] == [1, 1, 1, 1]                           # 우선주: 머리 밑 한 번, 모든 탭
    assert [t["fit"] for t in got["pref"]] == [1, 0, 0, 0]                            # 내 기준 카드는 요약에만 (줄들 밑에 한 번)
    assert all(t["fit"] == 0 for t in got["sam"])


def test_preferred_fit_card_line_replaces_other_row_reasons(bundle):
    """BYC우 처럼 과거 주가 기록 표시도 있는 우선주: 그 줄이 아니라 우선주 줄 하나 (순위가 없는 까닭은 우선주라서예요)."""
    got = run(bundle, """
      const d = JSON.parse(JSON.stringify(DATA)); const c = JSON.parse(JSON.stringify(CORP));
      const s = d.stocks.find((x) => x.t === PREF_T); for (const k of ['vol', 'beta', 'betaSE', 'betaN', 'al', 'r36', 'sh', 'mdd', 'hit', 'lz']) delete s[k];
      s.pxBad = '2024-04-17'; s.pxBadF = ['vol', 'beta', 'betaSE', 'betaN', 'al', 'r36', 'sh', 'mdd', 'hit', 'lz'];
      const co = c.companies.find((x) => x.t === PREF_T); co.pxBad = s.pxBad; co.pxBadF = s.pxBadF;
      const load = { ...LOAD, data: d, corp: c, byT: new Map(d.stocks.map((x) => [x.t, x])), coByT: new Map(c.companies.map((x) => [x.t, x])) };
      const store = { ...STORE, data: { ...STORE.data, decks: [{ id: 'd', name: 'p', kind: 'imported', settings: { points: { lowVol: 2, value: 1 }, strict: 'normal' },
        holdings: [], purchases: [], imported: [] }] } };
      const fitOf = (t) => { const x = page(t, null, load, store); return x.slice(x.indexOf('data-ui-v2="co-fit"')); };
      const fit = fitOf(PREF_T);
      // the same mark on a common stock (제일기획): the short line stays there (its 낮은 변동성 is blank because of the price history)
      const k = d.stocks.find((x) => x.t === '030000'); for (const f of s.pxBadF) delete k[f]; k.pxBad = s.pxBad; k.pxBadF = s.pxBadF;
      const kc = c.companies.find((x) => x.t === '030000'); kc.pxBad = s.pxBad; kc.pxBadF = s.pxBadF;
      out = { pref: count(fit, C2.co.fit.pref), one: count(fit, C2.co.pxBadOne), low: /data-card="lowVol" data-side="blank"/.test(fit),
        common: count(fitOf('030000'), C2.co.pxBadOne), commonPref: count(fitOf('030000'), C2.co.fit.pref) };""",
              PREF_T=PREF_T)
    assert got["pref"] == 1 and got["one"] == 0 and got["low"], got                 # 우선주: 그 줄 하나 (낮은 변동성 '–' 의 까닭도 우선주)
    assert got["common"] == 1 and got["commonPref"] == 0, got                        # 보통주는 예전 그대로


def test_portfolio_today_keeps_a_halted_holding(bundle):
    got = run(bundle, """
      const ctx = { state: { ok: true }, byT: LOAD.byT, coByT: LOAD.coByT, fx: 1400, pxDate: DATA.pxDate };
      const nk = (t) => LOAD.byT.get(t).nk;
      const deck = { id: 'd', name: 'p', kind: 'imported', settings: { points: { value: 3 }, strict: 'normal' },
        holdings: ['005930', NT_T].map((t) => ({ t, nk: nk(t), cls: 'kr' })), purchases: [], imported: ['005930', NT_T].map((t) => ({ t, nk: nk(t), ccy: 'KRW', qty: 10 })) };
      const ev = R.evaluateAll([deck], ctx); const b = Hm.homeBlocks([deck], ev, ctx, DATA.stocks)[0];
      const miss = { ...deck, holdings: ['005930', MISS_T].map((t) => ({ t, nk: nk(t), cls: 'kr' })), imported: ['005930', MISS_T].map((t) => ({ t, nk: nk(t), ccy: 'KRW', qty: 10 })) };
      const ev2 = R.evaluateAll([miss], ctx); const b2 = Hm.homeBlocks([miss], ev2, ctx, DATA.stocks)[0];
      const sam = LOAD.byT.get('005930');
      const exp = 10 * sam.price - 10 * sam.price / (1 + sam.d1 / 100);
      const hold = (dv) => ({ t: 'x', qty: 1, value: 100, cls: 'kr', d1: null, ...(dv === undefined ? {} : { dv }) });
      const de = (hs) => ({ ok: true, weights: { ok: true }, holdings: hs, absent: [] });
      out = { day: b.money.day, exp, rows: b.list.rows.map((r) => [r.t, r.d1]), miss: b2.money.day,
        built: [T.deckDayChange(de([hold(0)])), T.deckDayChange(de([hold(null)])), T.deckDayChange(de([hold()])), T.deckDayChange(de([{ ...hold(), d1: 2 }]))],
      };""", NT_T=NT_T, MISS_T=MISS_T)
    assert got["day"] is not None and abs(got["day"]["amount"] - got["exp"]) < 1e-6, got   # 거래 없는 종목은 기준가 변화(0)로 · 오늘은 그대로
    assert dict(got["rows"])[NT_T] is None                                                  # 그 줄에는 0.0% 가 아니라 빈 칸 (줄은 DayNote)
    assert got["miss"] is None                                                              # 다른 이유로 빈 d1: 예전처럼 오늘 없음
    assert got["built"][:3] == [0, None, None] and abs(got["built"][3] - 2) < 1e-9          # 만든 포트폴리오: dv 를 읽고, 없으면 d1 (예전 호출)


def test_rules_carry_the_value_change(bundle):
    got = run(bundle, """
      const ctx = { state: { ok: true }, byT: LOAD.byT, coByT: LOAD.coByT, fx: 1400, pxDate: DATA.pxDate, usPxDate: DATA.usPxDate };
      const hold = (t) => ({ t, nk: LOAD.byT.get(t).nk, cls: 'kr', target: 0.5, rules: [] });
      const w = { ok: true, w: new Map(), value: new Map(), px: new Map() };
      out = [NT_T, MISS_T, '005930'].map((t) => { const x = R.evaluateHolding(hold(t), {}, ctx, w, 10); return [x.d1, x.dv, x.bigMove]; });""",
              NT_T=NT_T, MISS_T=MISS_T)
    sam_d1 = got[2][0]
    assert got[0] == [None, 0, False] and got[1] == [None, None, False] and got[2] == [sam_d1, sam_d1, abs(sam_d1) >= 5]


def test_unscored_line_matches_the_case(bundle):
    got = run(bundle, """
      const r = (t) => ({ t, nk: t, s: t ? LOAD.byT.get(t) || { t, cls: 'us', nk: t } : null });
      const etf = DATA.stocks.find((s) => s.etf && s.cls === 'kr');
      const cases = { pref: [r(PREF_T)], prefEtf: [r(PREF_T), r(etf.t)], named: [r(PREF_T), { t: null, nk: '비상장 회사', s: null }], none: [],
        common: [r('005930')] };
      out = { all: Object.fromEntries(Object.entries(cases).map(([k, v]) => [k, P.unscoredAllPref(v, DATA.stocks)])),
        keyOff: RP.unscoredKey(cases.pref, DATA.stocks), keyOn: RP.unscoredKey(cases.pref, DATA.stocks, true), keyOnNamed: RP.unscoredKey(cases.named, DATA.stocks, true),
        sw: RP.UNSCORED_PREF };""", PREF_T=PREF_T)
    assert got["all"] == {"pref": True, "prefEtf": True, "named": False, "none": False, "common": False}
    assert got["keyOff"] == "unscored" and got["keyOn"] == "unscoredPref" and got["keyOnNamed"] == "unscored"
    assert got["sw"] is False                                                          # Jack 의 답(기존 시험 한 줄) 전까지 꺼 둬요


def test_stock_rows_say_why_under_the_name(bundle):
    got = run(bundle, """
      const row = (t) => renderToStaticMarkup(h(ST.StockRow, { s: LOAD.byT.get(t), t, cls: LOAD.byT.get(t).cls, md: '10월 30일' }));
      out = { nt: text(row(NT_T)).includes('10월 30일 거래 없음 (거래정지일 수 있어요)'), miss: text(row(MISS_T)).includes(C2.co.d1Missing),
        sam: marks(row('005930'), 'day-note'), ntChange: /[+−-]\\d+\\.\\d%/.test(text(row(NT_T))), plain: marks(renderToStaticMarkup(h(ST.StockRow, { s: LOAD.byT.get(NT_T), t: NT_T, cls: 'kr', md: '10월 30일', plain: true })), 'day-note') };""",
              NT_T=NT_T, MISS_T=MISS_T)
    assert got == {"nt": True, "miss": True, "sam": 0, "ntChange": False, "plain": 0}
