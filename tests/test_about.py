# -*- coding: utf-8 -*-
"""뱁새 2.0 소개 페이지 (v19.0 Part D, #about) 검사.

- 소개 문구(src/copy/v2.js 의 about.ko · about.en)는 docs/design/v19/copy/about.md 와 한 글자도 다르지 않아요
  (바뀐 곳은 하나: "3,000개가 넘는" → "{n}개가 넘는", 영어 "more than 3,000" → "more than {n}")
- 숫자 줄은 데이터로 계산해요 (src/v2/aboutstats.js, Node 로 직접 돌려봐요): 분석 종목 = cls 가 kr 또는 us 인 종목(ETF 포함),
  업종 그룹 = 그 종목들의 ind 중 빈 값 · etc · other 를 뺀 서로 다른 개수, n = 분석 종목 수를 백 단위로 내림 (3,256 → 3,200)
- 무엇을 보여 주는지: 새 데이터 → 숫자 줄과 {n} 문단 · 멈춘 데이터 → 숫자 줄 없음, {n} 문단은 그대로 ·
  불러오기 실패 · 불러오는 중 · 미리 보기(지어낸 데이터) → 숫자 줄도 {n} 문단도 없음
- 오늘의 숫자(3,256 · 57 · 3,200)를 코드에 박아 두지 않아요
화면 동작(언어 바꾸기 · 기억 · 저장소 막힘 · 숫자 줄 = 데이터로 센 값 · 실패 때 숨김)은 tests/smoke_v2.py 가 휴대폰 크기로 봐요.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

import pytest

from copytrace import ROOT, about_md, copy_strings, read

NODE = shutil.which("node")
N_KO = ("3,000개가 넘는", "{n}개가 넘는")
N_EN = ("more than 3,000", "more than {n}")


def from_copy(a, url):
    """C.about[lang] 을 about.md 와 같은 순서 · 같은 조각으로 (copytrace.about_md 와 짝)."""
    out = [a["hero"]["name"], a["hero"]["descriptor"], a["hero"]["catch"],
           a["figures"]["stocks"], a["figures"]["groups"], a["figures"]["refresh"]]
    w = a["what"]
    out += [w["title"], w["intro"], w["data"]]
    for it in w["items"]:
        out += [it["title"], it["body"]]
    out += [a["who"]["title"], a["who"]["intro"], *a["who"]["items"]]
    out += [a["why"]["title"], *a["why"]["body"]]
    out.append(a["principles"]["title"])
    for it in a["principles"]["items"]:
        out += [it["title"], it["body"]]
    out += [a["run"]["title"], *a["run"]["items"]]
    out += [a["name"]["title"], *a["name"]["body"]]
    m = a["maker"]
    out += [m["title"], m["name"], m["role"], m["photoAlt"], m["edu"]["label"], m["edu"]["value"], m["career"]["label"]]
    for it in m["career"]["items"]:
        out += [it["org"] + (" · " + it["note"] if it.get("note") else ""), it["what"]]
    out += [m["built"]["label"], *m["built"]["items"], m["langs"]["label"], m["langs"]["value"], m["linkedIn"], url]
    return out


@pytest.mark.parametrize("lang,sub", [("ko", N_KO), ("en", N_EN)])
def test_about_copy_is_about_md_word_for_word(lang, sub):
    c, _ = copy_strings()
    want = about_md(lang)
    hits = [i for i, s in enumerate(want) if sub[0] in s]
    assert len(hits) == 1 and want[hits[0]].count(sub[0]) == 1, hits         # 숫자 문장은 딱 하나
    want[hits[0]] = want[hits[0]].replace(*sub)
    have = from_copy(c["about"][lang], c["about"]["linkedInUrl"])
    assert len(have) == len(want), (len(have), len(want))
    for i, (h, w) in enumerate(zip(have, want)):
        assert h == w, (lang, i, h, w)
    assert c["about"]["ko"]["what"]["data"].count("{n}") == 1 and c["about"]["en"]["what"]["data"].count("{n}") == 1
    # 다른 문장에는 {자리}가 없어요 (채우지 못한 자리가 화면에 나오지 않게)
    assert sum(s.count("{") for s in have) == 1, [s for s in have if "{" in s]


def test_switch_labels_and_link_come_from_about_md():
    c, _ = copy_strings()
    ab = c["about"]
    assert ab["langs"] == {"ko": "한국어", "en": "English"}
    assert ab["linkedInUrl"] == "https://www.linkedin.com/in/jacksungjinlee/"
    assert ab["langLabel"] == "언어" and ab["langLabel"] in about_md("ko")
    assert ab["heroAlt"] is None                                       # 승인 대기 (docs/tasks/v18.3-new-strings-pending.md)
    md = read("docs/design/v19/copy/about.md")
    assert "한국어 / English" in md and ab["linkedInUrl"] in md


def test_page_has_no_hard_coded_counts():
    """오늘의 숫자(3,256 종목 · 57 그룹 · 3,200)는 코드와 문구 어디에도 없어요: 데이터로 계산해요 (주석 제외)."""
    exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
    for f in ("src/v2/about.jsx", "src/v2/aboutstats.js"):
        r = subprocess.run([exe, f, "--minify", "--loader:.js=jsx", "--loader:.jsx=jsx", "--jsx=automatic", "--charset=utf8"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        hits = re.findall(r"(?<![\w.])(3,?256|57|3,?200|3,?000)(?![\w.])", r.stdout)
        assert not hits, (f, hits)
    c, flat = copy_strings()
    digits = [(p, v) for p, v in flat if p.startswith("about.") and isinstance(v, str) and re.search(r"\d", v)]
    # 남는 숫자는 경력 연수뿐이에요 (about.md 그대로)
    assert sorted(v for _, v in digits) == sorted(["경력 · 게임·엔터테인먼트 업계 6~7년", "Experience · 6–7 years in games and entertainment"]), digits
    page = read("src/v2/about.jsx")
    assert "aboutView(load)" in page and "nf(view.figures.count)" in page and "nf(view.figures.groups)" in page and "nf(view.n)" in page


# ── 숫자 줄 계산 (src/v2/aboutstats.js) ──
_B = {}


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp()
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, os.path.join(ROOT, "src/v2/aboutstats.js"), "--bundle", "--format=esm", "--platform=node",
                            f"--outfile={tmp}/aboutstats.mjs", "--log-level=warning"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    return _B["p"]


def run(body, **data):
    if NODE is None:
        pytest.skip("node 가 없어요")
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = "import * as A from './aboutstats.mjs';\n" + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));"
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=bundle_dir())       # 큰 데이터는 명령줄 길이를 넘어서 파일로 돌려요
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=bundle_dir(), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def stocks(n, cls="kr", ind="semi", **kw):
    return [{"t": f"{cls}{i}", "cls": cls, "ind": ind, **kw} for i in range(n)]


def test_counts_kr_and_us_including_etfs_and_rounds_down_to_the_hundred():
    s = stocks(2400, "kr", "semi") + stocks(800, "us", "soft") + stocks(56, "kr", "bank", etf=True) \
        + stocks(8, "bond", "") + stocks(3, "metal", "")
    out = run("out = A.aboutStats({ stocks: S });", S=s)
    assert out == {"count": 3256, "groups": 3, "n": 3200}, out
    assert run("out = A.aboutStats({ stocks: S });", S=stocks(999))["n"] == 900
    assert run("out = A.aboutStats({ stocks: S });", S=stocks(1000))["n"] == 1000
    assert run("out = A.aboutStats({ stocks: S });", S=stocks(100))["n"] == 100
    assert run("out = A.aboutStats({ stocks: S });", S=stocks(99)) == {"count": 99, "groups": 1, "n": None}   # "0개가 넘는" 은 쓰지 않아요


def test_groups_leave_out_blank_and_catch_all_ids():
    s = (stocks(3, "kr", "semi") + stocks(2, "us", "semi") + stocks(4, "kr", "") + stocks(5, "kr", "etc") + stocks(6, "us", "other")
         + [{"t": "x1", "cls": "kr"}, {"t": "x2", "cls": "us", "ind": None}, {"t": "x3", "cls": "kr", "ind": 7}]
         + stocks(2, "bond", "rates"))                                    # 채권 ETF 의 그룹은 세지 않아요 (분석 종목이 아니에요)
    out = run("out = A.aboutStats({ stocks: S });", S=s)
    assert out == {"count": 23, "groups": 1, "n": None}, out


def test_no_data_gives_nothing():
    for body in ("out = A.aboutStats(null);", "out = A.aboutStats({});", "out = A.aboutStats({ stocks: [] });",
                 "out = A.aboutStats({ stocks: 'x' });", "out = A.aboutStats({ stocks: [{ cls: 'bond' }, null] });"):
        assert run(body) is None, body


def test_what_the_page_shows_in_each_state():
    s = stocks(3256, "kr", "semi")
    ok = {"status": "ok", "data": {"stocks": s}, "fresh": {"stale": False, "days": 0}, "preview": False}
    stale = {**ok, "fresh": {"stale": True, "days": 6}}
    prev = {**ok, "preview": True}
    v = run("out = [A.aboutView(OK), A.aboutView(ST), A.aboutView(F), A.aboutView(L), A.aboutView(P), A.aboutView(null)];",
            OK=ok, ST=stale, F={"status": "fail"}, L={"status": "loading"}, P=prev)
    figs = {"count": 3256, "groups": 1, "n": 3200}
    assert v[0] == {"figures": figs, "n": 3200}, v[0]                   # 새 데이터: 숫자 줄 + 문단
    assert v[1] == {"figures": None, "n": 3200}, v[1]                   # 멈춘 데이터: 숫자 줄 없음 ('매 거래일 갱신'이 거짓이 돼요), 문단은 그대로
    for x in v[2:]:
        assert x == {"figures": None, "n": None}, x                       # 실패 · 불러오는 중 · 미리 보기 · 없음: 둘 다 없음
