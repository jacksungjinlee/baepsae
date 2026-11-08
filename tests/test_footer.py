# -*- coding: utf-8 -*-
"""고지문 (Jack, 2026-11-08): 뱁새를 '교육용'이라고 부르지 않아요. 푸터는 어디서나 CLAUDE.md 의 한 줄이에요.

- 빌드한 페이지(baepsae.html · app.html · app-preview.html · styleguide.html, 저장소에 커밋한 것과 지금 소스로 새로 빌드한 2.0),
  index.html · manifest · 페이지 틀(template.html 들) · 서비스워커 · 링크 미리 보기 그림을 그리는 도구, 그리고 src/ 의 모든 파일에
  '교육용'(영어 'educational')이 0번이에요. 주석도 포함해요: 다음 작업이 주석에서 옛 문구를 다시 가져오지 않게요.
- 새 고지문이 2.0(한국어)과 예전 뱁새(한국어 · 영어)에 들어 있어요. 화면에 그려진 푸터는 smoke_v2.py · smoke_app.py 가 봐요.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOOTER_KO = "뱁새의 정보는 투자 자문이나 투자 권유가 아닙니다. 모든 투자 판단과 책임은 본인에게 있습니다."
FOOTER_EN = "Not investment advice or a solicitation to invest. All investment decisions and responsibility are yours."
BAD = re.compile(r"교육용|educational", re.IGNORECASE)
BUILT = ["baepsae.html", "app.html", "app-preview.html", "styleguide.html"]
OTHER = ["index.html", "manifest.webmanifest", "template.html", os.path.join("src", "v2", "template.html"),
         os.path.join("styleguide", "template.html"), "sw.js", os.path.join("tools", "render_og.py")]


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def hits(text):
    return sorted(set(m.group(0) for m in BAD.finditer(text)))


def source_files():
    out = []
    for top in ("src", "styleguide"):
        for d, _, names in os.walk(os.path.join(ROOT, top)):
            out += [os.path.relpath(os.path.join(d, n), ROOT) for n in names if n.endswith((".js", ".jsx", ".html", ".css"))]
    return sorted(out)


def test_pattern_catches_both_words():
    assert hits("교육용 도구입니다") == ["교육용"] and hits("An Educational tool") == ["Educational"]
    assert not hits("자녀 교육비 · 업종 교육 · Kids' education")      # 업종 이름 '교육', 'education' 은 다른 말이에요


def test_no_educational_tool_wording_in_built_pages_and_shell_files():
    for name in BUILT + OTHER:
        found = hits(read(name))
        assert not found, f"{name}: {found}"


def test_no_educational_tool_wording_in_fresh_2_0_build():
    from buildapp import built
    for name in ("app.html", "app-preview.html"):
        found = hits(built(name))
        assert not found, f"{name} (새 빌드): {found}"


def test_no_educational_tool_wording_anywhere_in_src():
    files = source_files()
    assert len(files) >= 60 and os.path.join("src", "copy", "v2.js") in files and os.path.join("src", "sharecard.js") in files, files
    bad = {f: hits(read(f)) for f in files if hits(read(f))}
    assert not bad, bad


def test_claude_md_footer_is_the_new_line():
    t = read("CLAUDE.md")
    assert f"Footer: {FOOTER_KO}" in t and "Education, not advice." in t
    assert "The product never calls 뱁새 an educational tool, in any language (Jack, 2026-11-08)" in t
    assert "교육용" not in t


def test_new_footer_in_2_0_and_old_app():
    assert f'footer: "{FOOTER_KO}"' in read(os.path.join("src", "copy", "v2.js"))
    assert f'disclaimer: {{ ko:"{FOOTER_KO}", en:"{FOOTER_EN}" }}' in read(os.path.join("src", "detail.jsx"))
    from buildapp import built
    for name in ("app.html", "app-preview.html"):
        assert FOOTER_KO in read(name), f"{name}: 새 고지문이 없어요"
        assert FOOTER_KO in built(name), f"{name} (새 빌드): 새 고지문이 없어요"
    old = read("baepsae.html")
    assert FOOTER_KO in old and FOOTER_EN in old, "예전 뱁새: 한국어 · 영어 고지문"
    assert FOOTER_KO in read("styleguide.html")


def test_old_app_footers_all_use_the_one_line():
    """예전 뱁새의 탭 푸터는 모두 SiteFooterLine (src/detail.jsx T.disclaimer + ' · 소개') 하나를 써요: 문구가 한 곳에만 있어요.
    그 줄은 keep-all 이라 한국어 낱말 중간에서 줄이 바뀌지 않아요 ('본인에 / 게' 처럼)."""
    assert '<span style={{ wordBreak: "keep-all" }}>{T.disclaimer[l]}' in read(os.path.join("src", "detail.jsx"))
    for f in ("shell.jsx", "simple.jsx", "corp.jsx", "disc.jsx", "macro.jsx", "info.jsx"):
        src = read(os.path.join("src", f))
        assert "<SiteFooterLine" in src, f
        assert FOOTER_KO not in src and FOOTER_EN not in src and "투자 자문이 아니" not in src, f"{f}: 고지문을 따로 적었어요"


# 교육이 빠진 네 문구 (Jack, 2026-11-08): 이용약관 제2조 · 산업 읽는 법 안내 · 정보 페이지(영어) · 공유 카드.
# 옛 문구는 사용자가 여는 페이지(커밋한 것 · 지금 소스로 새로 빌드한 2.0)와 src/ · styleguide/ 의 어떤 파일(주석 포함)에도 없어요.
EDU_GONE = ["교육·정보", "교육 자료", "rates·bond education", "투자 자문 아님"]
EDU_NEW = {   # 파일 → 그 파일에 꼭 한 번 있어야 하는 새 문구 (예전 뱁새에 빌드된 baepsae.html 에도)
    os.path.join("src", "info.jsx"): [
        "제2조 (서비스의 성격) 서비스는 정보 제공 목적의 도구이며, 자본시장법상 투자자문업·투자일임업에 해당하는 서비스를 제공하지 않습니다. "
        "서비스가 제공하는 모든 수치·분석·시각화는 투자 판단의 참고 자료일 뿐이며, 투자 권유가 아닙니다.",
        "insider-filing and pension-fund tracking, and plain explanations of rates and bonds. It deliberately does"],
    os.path.join("src", "corp.jsx"): ["업종을 이해하기 위한 자료예요. 특정 종목 추천이 아니에요."],
    os.path.join("src", "sharecard.js"): ["jacksungjinlee.github.io/baepsae · 투자 자문·투자 권유 아님"],
}


def test_no_education_wording_left_in_pages_or_source():
    from buildapp import built
    found = []
    for name in BUILT + OTHER + source_files():
        text = read(name)
        found += [(name, w) for w in EDU_GONE if w in text]
    for name in ("app.html", "app-preview.html"):
        found += [("built " + name, w) for w in EDU_GONE if w in built(name)]
    assert not found, found


def test_the_four_new_lines_are_in_source_and_in_the_old_app():
    old = read("baepsae.html")
    for f, lines in EDU_NEW.items():
        src = read(f)
        for line in lines:
            assert src.count(line) == 1, (f, line)
            assert old.count(line) == 1, ("baepsae.html", line)
    # 공유 카드: 고지 조각은 푸터 줄 하나에 그려요 (같은 자리 · 같은 글꼴)
    assert 'g.fillText("jacksungjinlee.github.io/baepsae · 투자 자문·투자 권유 아님", 100, H - 104);' in read(os.path.join("src", "sharecard.js"))
