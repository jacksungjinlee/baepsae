# -*- coding: utf-8 -*-
"""예전 뱁새 기업분석의 맞지 않는 두 줄 (Jack, 2026-11-14 Q3 · say-why audit NEW-8 · NEW-9).

1. 'PER과 EPS는 계산 방법을 고치는 중이라 11월 10일에 바뀔 수 있어요.'는 승인된 7일 안내(2.0 fix.owners "{date}부터 EPS와 ROE를 …")가
   아니라 다시 읽기 전의 '고치는 중' 줄(fix.eps)이에요. Jack: 그런 줄이면 지워요. 다시 읽은 뒤(corp.json epsBasis "owners") 그 줄이 남던
   곳은 EPS 가 아예 없는 회사(우선주 · 재무제표 없음)의 04 주가는 무엇으로 움직였나뿐이었어요 (11-14 발행: 102곳). 그 칸은 이제 EPS 가 있을
   때만 그 줄을 보여요 (바뀔 EPS 가 없으니까요). 영어 첫 화면 성적표도 같아요.
회사 줄은 2026-11-14 발행의 실제 값 (tests/fixtures/q3_real_rows.json). 화면은 react-dom/server 로 실제 컴포넌트를 그려서 봐요. 브라우저
화면은 tests/smoke_app.py 장면 '예전줄'이 봐요.
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
MODS = {"OLD": "src/corp.jsx", "OF": "src/fixnote.jsx", "SH": "src/shell.jsx", "RP": "src/repair.js"}
NO_DATA = "재무제표 데이터가 아직 없어요."
NO_DATA_OLD = "재무제표 데이터가 아직 없어요. (파이프라인이 사업보고서를 못 찾은 종목이에요)"
FOREIGN = "외화로 작성된 재무제표라 아직 보여 드리지 않아요."
_TMP = {}


def bundle_dir():
    if "p" not in _TMP:
        tmp = tempfile.mkdtemp(prefix="baepsae-oldlines-")
        with open(os.path.join(tmp, "entry.js"), "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, os.path.join(tmp, "entry.js"), "--bundle", "--format=esm", "--platform=node", "--jsx=automatic",
                            "--loader:.js=jsx", "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs",
                            "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _TMP["p"] = tmp
    return _TMP["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _TMP:
        shutil.rmtree(_TMP["p"], ignore_errors=True)


def corp_with_real_rows():
    """시험 데이터(tests/fixtures/v2/corp.json)에 2026-11-14 발행의 실제 회사 줄을 넣거나 바꿔요."""
    with open(os.path.join(ROOT, "tests", "fixtures", "v2", "corp.json"), encoding="utf-8") as f:
        corp = json.load(f)
    with open(os.path.join(ROOT, "tests", "fixtures", "q3_real_rows.json"), encoding="utf-8") as f:
        real = {c["t"]: c for c in json.load(f)["companies"]}
    corp["companies"] = [real.pop(c["t"], c) for c in corp["companies"]] + list(real.values())
    return corp


def run(body, **data):
    tmp = bundle_dir()
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { OLD, OF, SH, RP } = B;\n"
            "console.warn = () => {}; console.info = () => {}; globalThis.fetch = async () => { throw new Error('offline'); };\n"
            "const ent = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '\"').replace(/&#x27;/g, \"'\").replace(/&amp;/g, '&');\n"
            "const lines = (html) => ent(html.replace(/<!--.*?-->/g, '')).replace(/<[^>]+>/g, '\\n').split('\\n').map((x) => x.trim()).filter(Boolean);\n"
            "const page = (data, t) => renderToStaticMarkup(h(OLD.CompanyView, { data, t, heldInfo: null, onBack() {}, onOpen() {}, onCompare() {}, setExplain() {} }));\n"
            "const live = (corp) => ({ ...corp, epsBasis: 'owners' });\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_the_dated_line_is_the_being_fixed_line_not_the_seven_day_notice():
    """Jack 의 Q3 조건: 그 줄이 승인된 7일 안내면 11-17 까지 두고, 다른 줄이면 지워요. 예전 뱁새의 그 줄은 fix.eps 와 같은 '고치는 중'
    줄이에요 (docs/tasks/v18.3-approved-in-chat.md 의 'Old app … PER/EPS line'). 7일 안내(fix.owners)는 2.0 홈 · 포트폴리오에만 있어요."""
    with open(os.path.join(ROOT, "src", "fixnote.jsx"), encoding="utf-8") as f:
        old = f.read()
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as f:
        v2 = f.read()
    assert 'export const FIX_EPS = "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.";' in old
    assert 'eps: "PER과 EPS는 계산 방법을 고치는 중이라 {date}에 바뀔 수 있어요.",' in v2
    assert 'owners: "{date}부터 EPS와 ROE를 지배주주 몫으로 계산해요. 일부 규칙의 결과가 바뀔 수 있어요.",' in v2
    for name in ("corp.jsx", "shell.jsx", "detail.jsx", "fixnote.jsx"):                # 예전 뱁새에는 7일 안내가 없어요
        with open(os.path.join(ROOT, "src", name), encoding="utf-8") as f:
            assert "지배주주 몫으로 계산해요" not in f.read(), name


def test_no_dated_eps_line_where_there_is_no_eps():
    got = run("""
      const EPS = OF.fixEpsText(), EN = OF.fixEpsText('en');
      const count = (html, x) => lines(html).filter((l) => l === x).length;
      const card = (corp, t, lang) => lines(renderToStaticMarkup(h(SH.ScoreCard, { c: corp.companies.find((x) => x.t === t), sectors: corp.sectors, corp,
        onOpenCorp() {}, onQuickDiag() {}, lang, asOf: { date: corp.pxDate, publishedAt: corp.publishedAt } })));
      out = { text: EPS };
      for (const t of ['005935', '496320', '950250', '000660', '066970']) {
        out[t] = { now: count(page(CORP, t), EPS), live: count(page(live(CORP), t), EPS),
          ko: card(live(CORP), t, 'ko').filter((l) => l === EPS).length, en: card(live(CORP), t, 'en').filter((l) => l === EN).length };
      }
      out.sam = count(page(CORP, '005930'), EPS);""", CORP=corp_with_real_rows())
    assert "바뀔 수 있어요" in got["text"]
    for t in ("005935", "496320", "950250"):                 # EPS 가 없는 회사: 다시 읽기 전이든 뒤든, 기업분석 · 첫 화면 성적표(한국어 · 영어) 어디에도 없어요
        assert got[t] == {"now": 0, "live": 0, "ko": 0, "en": 0}, (t, got[t])
    for t in ("000660", "066970"):                           # 다시 읽은 회사(epsIn "o"): 예전처럼 없어요
        assert got[t]["live"] == 0 and got[t]["ko"] == 0 and got[t]["en"] == 0, (t, got[t])
    assert got["sam"] == 4                                   # 다시 읽기 전 파일의 EPS 가 있는 회사: 예전 그대로 네 칸 (tests/test_fix_notes.py)


# ── 04 주가는 무엇으로 움직였나: '적자 구간이 있어서 …'는 정말 적자일 때만 (Jack Q3 · say-why NEW-8) ──
def test_the_loss_line_only_for_a_real_loss_and_the_data_line_when_there_are_no_statements():
    """재무제표 숫자가 하나도 없으면 02 와 같은 줄 ('재무제표 데이터가 아직 없어요.' · 해외 기업은 '외화로 …'), 나누기를 막는 게 정말 적자면
    (지금 EPS ≤ 0 · 3년 전 순이익 ≤ 0) 예전 '적자' 줄 그대로, 숫자는 있는데 3년 주가나 한 해가 없어 나누지 못하면 틀린 '적자' 줄 대신
    칸이 없어요 (Jack, 2026-11-14: 숨긴 채로)."""
    got = run("""
      const L = (t) => lines(page(live(CORP), t));
      const gap = (t) => OLD.decompGap(CORP.companies.find((x) => x.t === t));
      const block = (t) => { const ls = L(t), i = ls.indexOf('주가는 무엇으로 움직였나');
        return i < 0 ? null : ls.slice(i, i + 8); };                   // 제목 · ? · 부제 · 본문 …
      out = {};
      for (const t of ['005935', '950250', '496320', '066970', '000660', '064400', '489790', '005930']) out[t] = { gap: gap(t), block: block(t) };
      out.prefPage = L('005935');""", CORP=corp_with_real_rows())
    loss = "적자 구간이 있어서 이익과 눈높이로 나누기 어려워요."
    for t in ("005935", "496320"):                           # 삼성전자우 · 본시스템즈 (재무제표 없음)
        assert got[t]["gap"] == "noStatements" and got[t]["block"][3] == NO_DATA, (t, got[t])
    assert not any("적자 구간" in x for x in got["prefPage"])
    assert got["950250"]["gap"] == "noStatements" and got["950250"]["block"][3] == FOREIGN, got["950250"]        # 테라뷰 (해외 기업)
    for t in ("066970", "000660"):                           # 엘앤에프 (지금 적자) · SK하이닉스 (3년 전 적자): 나누기를 막는 건 정말 적자
        assert got[t]["gap"] == "loss" and got[t]["block"][3].startswith(loss), (t, got[t])
    for t in ("064400", "489790"):                           # LG씨엔에스 (3년 주가 없음) · 한화비전 (3년 전 해가 빔): 적자가 아니라 칸이 없어요
        assert got[t]["gap"] is None and got[t]["block"] is None, (t, got[t])
    assert got["005930"]["block"] is not None and "이익(EPS) 변화" in got["005930"]["block"]   # 나눌 수 있는 회사는 그대로 (숫자 칸)
