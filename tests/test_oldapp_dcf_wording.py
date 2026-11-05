# -*- coding: utf-8 -*-
"""예전 뱁새 문구 (Jack 승인 2026-11-05): 기업분석 리버스 DCF · 3개월 주가 줄 · 주가가 그대로일 때.

- 리버스 DCF 는 '성장률이 5년에 걸쳐 영구성장률로 수렴' 칸이 켜져 있으면(기본) 2.0 '지금 가격이 가정하는 것'과 같은 계산이에요
  (첫해 증가율이 5년에 걸쳐 영구성장률로 바뀌고, 첫해 범위 −30% ~ +60%). 그래서 2.0 의 승인된 문장(src/copy/v2.js co.dcf.headUp ·
  headDown · high · low · note)을 반올림 · 0 · 문장부호까지 그대로 써요. 같은 입력이면 두 앱의 문장이 글자 하나까지 같아요 (예전 카드는
  주식 수를 0.1 백만주로 반올림해서 받아서, 실제 화면에서는 종목에 따라 소수 첫째 자리가 다를 수 있어요: 이 PR 밖). 예전 첫 문장의
  '(이후 2%)' 대신 2.0 처럼 설명 줄이 영구성장률을 보여요. 매출 문장(PR #47)은 남아요. 칸을 끄면(5년 내내 같은 증가율) 예전 문장 그대로.
- 성적표(첫 화면 검색)와 기업분석의 3개월 줄 (실적은 좋아졌는데 주가가 15% 넘게 내렸을 때):
  '실적은 좋아졌는데 3개월간 x% 내렸어요. 시장이 무엇을 걱정하는지 살펴볼 만해요.' x 는 부호 없이, 줄표 없이.
- 보이는 주가 변화가 0 이면 '+0% 올랐어요' 대신 '지난 3년 주가는 거의 변하지 않았어요.'
화면은 react-dom/server 로 실제 컴포넌트(DcfCard · CompanyView · ScoreCard)를 그려서 봐요.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"OLD": "src/corp.jsx", "SH": "src/shell.jsx", "D": "src/data.js", "K": "src/v2/company.js", "F": "src/v2/cofmt.js",
        "CP": "src/copy/v2.js", "FM": "src/v2/format.js"}
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "v2", "corp.json")
DASHES = ("-", "−", "–", "—")                    # 빼기 · 마이너스 · 줄표 어느 것도 없어요

UP = "지금 주가에는 이익이 첫해 {g}% 는다는 가정이 담겨 있어요"
DOWN = "지금 주가에는 이익이 첫해 {g}% 준다는 가정이 담겨 있어요"
HIGH = "지금 주가가 맞으려면 이익이 첫해 60% 넘게 늘어야 해요."
LOW = "지금 주가는 이익이 첫해 30% 넘게 준다고 가정해도 설명되지 않을 만큼 낮아요. 모형 밖의 이유(부채, 소송, 지배구조 등)가 있을 수 있어요."
GROWTH = "이 회사 매출은 최근 2년 동안 연평균 13.5% 늘었어요. 지금 주가가 가정하는 성장률과 비교해 보세요."   # 삼성전자 g3 13.5 (PR #47)
NOTE = "예측이 아니라 지금 가격을 거꾸로 읽은 숫자예요. 증가율은 5년에 걸쳐 {t}%까지 바뀐다고 놓고 계산했어요."
FELL = "실적은 좋아졌는데 3개월간 {x}% 내렸어요. 시장이 무엇을 걱정하는지 살펴볼 만해요."
FELL_EN = "Earnings improved but the stock fell {x}% in 3 months. It may be worth asking what the market is worried about."


@pytest.fixture(scope="module")
def bundle():
    """예전 앱(corp.jsx · shell.jsx · data.js)과 2.0(company.js · cofmt.js · copy)을 한 파일로 묶어요. React 는 밖에 둬요."""
    with tempfile.TemporaryDirectory() as tmp:
        entry = os.path.join(tmp, "entry.js")
        with open(entry, "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", "--jsx=automatic", "--loader:.js=jsx",
                            "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs", "--log-level=error"],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        yield tmp


def run(tmp, body, **data):
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react'; import fs from 'fs';\n"
            "const { OLD, SH, D, K, F, CP, FM } = B; const C2 = CP.C;\n"
            # 2.0 시험 데이터의 corp.json (실제 발행본의 한국 종목 331개): 명령줄에 넣기엔 커서 파일에서 읽어요
            f"const CORP = JSON.parse(fs.readFileSync({json.dumps(FIXTURE)}, 'utf8'));\n"
            # 그린 화면의 글자: 주석(<!-- -->)은 지우고, 태그마다 줄을 나눠요
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const revBox = (html) => { const m = /data-rev-dcf=\"([^\"]+)\"[^>]*>(.*?)<\\/div>/.exec(html); return m ? { kind: m[1], lines: lines(m[2]) } : null; };\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=tmp, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def samsung():
    with open(FIXTURE, encoding="utf-8") as f:
        return next(c for c in json.load(f)["companies"] if c["t"] == "005930")


def no_dash(s):
    for d in DASHES:
        assert d not in s, (d, s)


# ── 리버스 DCF: 2.0 의 승인된 문장 그대로 ──
def test_reverse_dcf_sentence_rounds_like_2_0_for_every_rate(bundle):
    """첫해 증가율을 2.0 처럼 소수 한 자리로 반올림한 뒤 0 이상(−0 포함)이면 '는다는', 0보다 작으면 '준다는' 에 빼기 없이."""
    gs = [41.18, 22.1, 12.34, 12.25, 0.06, 0.05, 0.04, 0, -0.04, -0.05, -0.06, -3.2, -7.86, -12.25, -29.96, -30, 60, 59.99]
    got = run(bundle, "out = G.map((g) => [D.krRevDcfText({ g }), F.dcfHeadText(K.round(g, 1))]).concat("
                      "[[D.krRevDcfText({ g: -0 }), F.dcfHeadText(K.round(-0, 1))], [D.krRevDcfText({ edge: 'high' }), C2.co.dcf.high],"
                      " [D.krRevDcfText({ edge: 'low' }), C2.co.dcf.low], [D.krRevDcfText(null), null], [D.krRevDcfText({ g: NaN }), null],"
                      " [D.krRevDcfText({ g: null }), null], [D.krRevDcfText({}), null]]);", G=gs)
    for old, new in got:
        assert old == new, (old, new)                                            # 2.0 과 글자 하나까지 같아요
    want = [UP.format(g="41.2"), UP.format(g="22.1"), UP.format(g="12.3"), UP.format(g="12.3"), UP.format(g="0.1"), UP.format(g="0.1"),
            UP.format(g="0.0"), UP.format(g="0.0"), UP.format(g="0.0"), UP.format(g="0.0"), DOWN.format(g="0.1"), DOWN.format(g="3.2"),
            DOWN.format(g="7.9"), DOWN.format(g="12.2"), DOWN.format(g="30.0"), DOWN.format(g="30.0"), UP.format(g="60.0"),
            UP.format(g="60.0"), UP.format(g="0.0"), HIGH, LOW, None, None, None, None]
    assert [o for o, _ in got] == want, [o for o, _ in got]
    for s in [o for o, _ in got if o]:
        no_dash(s)
    assert not any(s.endswith(".") for s in want[:19])                           # 첫 문장은 2.0 처럼 마침표 없이 (카드에서 한 줄)


def test_reverse_dcf_note_is_2_0s_note_with_the_same_rate_format(bundle):
    """첫 문장 아래 설명 줄은 2.0 의 co.dcf.note 그대로, {t} 는 2.0 cotabs 의 pctNum 그대로 (2 → 2, 2.5 → 2.5, 0 → 0)."""
    ts = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]
    got = run(bundle, "out = T.map((t) => [D.krRevDcfNote(t), FM.fill(C2.co.dcf.note, { t: FM.nf(t, t % 1 ? 1 : 0) })])"
                      ".concat([[D.krRevDcfNote(NaN), null], [D.krRevDcfNote(null), null], [D.krRevDcfNote(undefined), null]]);", T=ts)
    for old, new in got:
        assert old == new, (old, new)
    assert [o for o, _ in got] == [NOTE.format(t=t) for t in ("0", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4")] + [None] * 3
    for o, _ in got[:-3]:
        no_dash(o)
    tabs = open(os.path.join(ROOT, "src", "v2", "cotabs.jsx"), encoding="utf-8").read()
    assert "const pctNum = (v) => nf(v, v % 1 ? 1 : 0);" in tabs and "<Note>{fill(D.note, { t: pctNum(a.term) })}</Note>" in tabs   # 2.0 이 바뀌면 여기서 알아요


def test_reverse_dcf_card_says_what_2_0_says_for_the_same_stock(bundle):
    """같은 입력(순이익 · 주식 수 · 주가 · 할인율 10% · 영구성장률 2% · 증가율이 5년에 걸쳐 바뀜)이면 예전 카드와 2.0 카드가 같은 문장을
    보여요: 첫해 증가율 > 0 · < 0 · 0 · 범위 위(60% 넘게) · 범위 아래(30% 넘게 줄어도). 예전 카드는 첫 문장 아래에 매출 문장(PR #47)과
    2.0 의 설명 줄. 실제 화면의 예전 카드는 주식 수를 0.1 백만주로 반올림해 받아서 같은 입력이 되도록 주식 수를 100.0 으로 둬요."""
    sam = samsung()
    co = {**sam, "shm": 100.0}                                                   # 예전 카드는 주식 수를 0.1 백만주로 반올림해서 받아요: 같은 입력이 되게
    got = run(bundle, """
      const P = (g1) => OLD.dcfPerShare({ ni0: CO.ni[0], sharesM: CO.shm, g1, fade: true, disc: 10, term: 2 });
      const prices = { up: P(12.34), down: P(-7.86), zero: P(0), high: P(60) * 1.5, low: P(-30) * 0.5 };
      out = {};
      for (const [k, price] of Object.entries(prices)) {
        const c = { ...CO, price };
        const oldRev = OLD.reverseDcf({ price, ni0: c.ni[0], sharesM: c.shm, fade: true, disc: 10, term: 2 });
        const r2 = K.impliedGrowth({ t: c.t, cls: 'kr', price, cap: c.cap }, c);
        const v2 = r2.edge ? C2.co.dcf[r2.edge] : F.dcfHeadText(K.round(r2.g, 1));
        const html = renderToStaticMarkup(h(OLD.DcfCard, { c, sharesM: c.shm, setExplain() {} }));
        out[k] = { helper: D.krRevDcfText(oldRev), v2, edge: r2.edge || null, box: revBox(html), all: lines(html).join('\\n') };
      }""", CO=co)
    want = {"up": UP.format(g="12.3"), "down": DOWN.format(g="7.9"), "zero": UP.format(g="0.0"), "high": HIGH, "low": LOW}
    for k, w in want.items():
        g = got[k]
        assert g["helper"] == w and g["v2"] == w, (k, g)                         # 예전 = 2.0 = Jack 의 문장
        if k in ("high", "low"):
            assert g["edge"] == k and g["box"] == {"kind": k, "lines": [w]}, (k, g)    # 범위 밖: 그 문장 하나만
        else:
            assert g["box"] == {"kind": "g", "lines": [w, GROWTH, NOTE.format(t="2")]}, (k, g)   # 첫 문장 한 줄, 매출 문장, 2.0 의 설명 줄
        for line in g["box"]["lines"]:
            no_dash(line)
        for old in ("향후 5년 연", "(이후", "역성장", "정당화하려면", "근거가 있는지가 질문이에요", "를 봐야 해요."):
            assert old not in g["all"], (k, old)


# ── 3개월 줄: 실적은 좋아졌는데 주가가 내렸을 때만 · 숫자는 부호 없이 ──
def test_three_month_line_after_a_fall_reads_jacks_sentence_on_both_screens(bundle):
    sam = samsung()
    ni = sam["ni"]
    better = [ni[0], round(ni[0] / 1.2, 1), ni[2]]                              # 순이익 1년 +20%
    flat = [ni[0], ni[0], ni[2]]                                                # 순이익 그대로
    cases = {"fell": (-20.5, better), "fell17": (-17.0, better), "edge": (-15.0, better), "small": (-14.9, better),
             "zero": (0.0, better), "rose": (20.5, flat), "fellFlat": (-20.5, flat)}
    got = run(bundle, """
      out = {};
      for (const [k, [r3, ni]] of Object.entries(CASES)) {
        const c = { ...SAM, r3, ni };
        const data = { ...CORP, companies: CORP.companies.map((x) => (x.t === c.t ? c : x)) };
        const corp = lines(renderToStaticMarkup(h(OLD.CompanyView, { data, t: c.t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} })));
        const card = (lang) => lines(renderToStaticMarkup(h(SH.ScoreCard, { c, sectors: CORP.sectors, onOpenCorp() {}, onQuickDiag() {}, lang,
          asOf: { date: CORP.pxDate, publishedAt: CORP.publishedAt } })));
        const pick = (ls) => ls.filter((l) => /3개월간|in 3 months|최근 3개월 (주가는 )?\\+|내렸어요|fell/.test(l));
        out[k] = { corp: pick(corp), ko: pick(card('ko')), en: pick(card('en')) };
      }""", CASES=cases, SAM=sam)
    for k, x in (("fell", "20.5"), ("fell17", "17"), ("edge", "15")):
        assert got[k]["corp"] == [FELL.format(x=x)], (k, got[k])                 # 기업분석
        assert got[k]["ko"] == [FELL.format(x=x)], (k, got[k])                   # 성적표
        assert got[k]["en"] == [FELL_EN.format(x=x)], (k, got[k])                # 영어는 그대로 (이 문장의 짝)
        for line in got[k]["corp"] + got[k]["ko"] + got[k]["en"]:
            no_dash(line)                                                        # 부호도 줄표도 없어요
    for k in ("small", "zero", "fellFlat"):                                      # 15% 넘게 내리지 않았거나 실적이 좋아지지 않았으면 없어요
        assert got[k] == {"corp": [], "ko": [], "en": []}, (k, got[k])
    assert all("3개월간" not in l and "fell" not in l for l in got["rose"]["corp"] + got["rose"]["ko"] + got["rose"]["en"]), got["rose"]
    assert got["rose"]["corp"] and got["rose"]["ko"] and got["rose"]["en"], got["rose"]   # 오른 쪽은 이 PR 밖의 다른 문장 (그대로)


# ── 주가가 그대로일 때: '+0% 올랐어요' 대신 '거의 변하지 않았어요' ──
def test_a_price_change_shown_as_zero_reads_barely_changed(bundle):
    """기업분석 '주가는 무엇으로 움직였나'에서 적자 구간이 있어 나누지 못할 때의 3년 주가 문장. r36 은 소수 한 자리 그대로 보여요.
    0 (−0 도)이면 '지난 3년 주가는 거의 변하지 않았어요.' 하나만: 움직이지 않았으니 뒤 문장('이익 없이 움직인 가격은…')은 빼요
    (Jack, 2026-11-05). 0 이 아니면 예전 그대로 (+x% 올랐어요 · x% 내렸어요) 뒤 문장과 함께."""
    sam = samsung()
    loss = [sam["ni"][0], sam["ni"][1], -100.0]                                 # 3년 전 적자: 이익과 눈높이로 나누지 못해요
    got = run(bundle, """
      out = {};
      for (const [k, r36] of [['zero', 0], ['negZero', -0], ['up', 12.3], ['down', -7], ['tiny', 0.1], ['tinyDown', -0.1]]) {
        const c = { ...SAM, r36, ni: LOSS };
        const data = { ...CORP, companies: CORP.companies.map((x) => (x.t === c.t ? c : x)) };
        const ls = lines(renderToStaticMarkup(h(OLD.CompanyView, { data, t: c.t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} })));
        // 그 줄, 그리고 화면 전체에서 뒤 문장이 몇 번 나오는지 (다른 칸으로 옮겨 가도 잡히게)
        out[k] = { line: ls.filter((l) => l.includes('지난 3년 주가는')), tails: ls.join(' ').split('이익 없이 움직인 가격은').length - 1 };
      }""", SAM=sam, LOSS=loss)
    lead = "적자 구간이 있어서 이익과 눈높이로 나누기 어려워요. "
    tail = " 이익 없이 움직인 가격은 기대와 수급이 만든 거예요."
    same = lead + "지난 3년 주가는 거의 변하지 않았어요."                      # 뒤 문장 없이
    assert got["zero"]["line"] == [same] and got["negZero"]["line"] == [same], got
    assert got["zero"]["tails"] == 0 and got["negZero"]["tails"] == 0, got        # 화면 어디에도 뒤 문장이 없어요
    assert got["up"]["line"] == [lead + "지난 3년 주가는 +12.3% 올랐어요." + tail], got
    assert got["down"]["line"] == [lead + "지난 3년 주가는 7% 내렸어요." + tail], got
    assert got["tiny"]["line"] == [lead + "지난 3년 주가는 +0.1% 올랐어요." + tail], got     # 보이는 숫자가 0 이 아니면 그대로
    assert got["tinyDown"]["line"] == [lead + "지난 3년 주가는 0.1% 내렸어요." + tail], got
    for k in ("up", "down", "tiny", "tinyDown"):                                 # 0 이 아니면 뒤 문장이 한 번 그대로 남아요
        assert got[k]["tails"] == 1, (k, got[k])
    no_dash(same)
    for bad in ("+0%", " 0% "):
        assert bad not in same, bad
    # 이 두 칸은 2.0 처럼 낱말 사이에서만 줄을 바꿔요 ('주가는' · '있어요' 가 두 줄로 갈라지지 않게, 390 px)
    corp = open(os.path.join(ROOT, "src", "corp.jsx"), encoding="utf-8").read()
    assert 'lineHeight: 1.7, wordBreak: "keep-all", overflowWrap: "break-word" }}>\n        적자 구간이 있어서' in corp
    assert 'marginTop: 5, wordBreak: "keep-all", overflowWrap: "break-word" }}>\n                  {rev.edge ? revText' in corp


# 수렴 칸을 끈 경우(5년 내내 같은 증가율)의 예전 문장: 그 계산에는 '첫해' 문장이 맞지 않아서 글자 하나 바꾸지 않고 남겨요
FLAT_BRANCH = """                  {rev.edge === "low" ? "지금 주가는 연 −30% 이하의 역성장을 가정해도 설명되지 않을 만큼 낮아요. 모형 밖의 이유(부채, 소송, 지배구조 등)를 봐야 해요."
                    : rev.edge === "high" ? "지금 주가를 정당화하려면 5년간 연 60%가 넘는 성장이 필요해요. 그만한 근거가 있는지가 질문이에요."
                    : <>지금 주가에는 <b>향후 5년 연 {rev.g.toFixed(1)}% 성장</b>(이후 {term}%)이 담겨 있어요.{growthLine ? " " + growthLine : null}</>}"""


def test_built_old_app_carries_the_new_sentences_and_the_old_ones_only_where_fade_is_off():
    built = open(os.path.join(ROOT, "baepsae.html"), encoding="utf-8").read()
    for s in ("는다는 가정이 담겨 있어요", "준다는 가정이 담겨 있어요", HIGH, LOW, "지금 주가에는 이익이 첫해 ", NOTE.split("{t}")[0],
              "% 내렸어요. 시장이 무엇을 걱정하는지 살펴볼 만해요.", "실적은 좋아졌는데 3개월간 ", "지난 3년 주가는 거의 변하지 않았어요."):
        assert s in built, s
    for old in ("시장이 무엇을 걱정하는지 볼 대목이에요", "시장이 다른 무엇을 걱정하는지 살펴볼 대목이에요", "연간 실적은 개선됐는데 최근 3개월 주가는"):
        assert old not in built, old
    for old in ("향후 5년 연 ", "역성장을 가정해도", "정당화하려면 5년간", "그만한 근거가 있는지가 질문이에요", "(이후 "):
        assert built.count(old) == 1, old                                       # 수렴 칸을 끈 경우의 예전 문장 한 곳에만
    corp = open(os.path.join(ROOT, "src", "corp.jsx"), encoding="utf-8").read()
    assert corp.count(FLAT_BRANCH) == 1                                          # 예전 문장은 글자 그대로
    on, off = corp.index("{fade ? ("), corp.index("data-rev-dcf-flat=")
    assert on < off < corp.index(FLAT_BRANCH)                                    # 그 문장은 수렴 칸을 끈 쪽에만
    fade_on = corp[on:off]
    assert "rev.g" not in fade_on and "revText" in fade_on and "revNote" in fade_on   # 켜진 쪽은 data.js 의 문장만
    assert "const revText = rev0 && fade ? krRevDcfText(rev0) : null;" in corp
    assert "const revNote = rev0 && fade && !rev0.edge ? krRevDcfNote(term) : null;" in corp
    assert "const rev = revBad ? null : rev0;" in corp and "console.warn(`[뱁새] 리버스 DCF 문장을 만들지 못해 칸을 뺐어요" in corp   # 빈 칸 대신 빼고 남겨요
