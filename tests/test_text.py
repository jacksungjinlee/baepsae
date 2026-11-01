# -*- coding: utf-8 -*-
"""빌드된 baepsae.html: 이모지 0개, 금지어 0개 (docs/BAEPSAE_VOICE.md). CLAUDE.md 의 PR 전 확인 항목이에요."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍]")


def banned_words():
    with open(os.path.join(ROOT, "docs", "BAEPSAE_VOICE.md"), encoding="utf-8") as f:
        text = f.read()
    line = text.split("## 금지어", 1)[1].split("\n", 2)[1]
    words = [w.strip() for w in line.split("·") if w.strip()]
    assert "잣대" in words and len(words) >= 5, words
    return words


def built():
    with open(os.path.join(ROOT, "baepsae.html"), encoding="utf-8") as f:
        return f.read()


def test_no_emoji_in_build():
    hits = EMOJI.findall(built())
    assert not hits, f"이모지 {len(hits)}개: {sorted(set(hits))}"


def test_no_banned_words_in_build():
    html = built()
    found = {w: html.count(w) for w in banned_words() if w in html}
    assert not found, f"금지어가 들어 있어요: {found}"


# ── 뱁새 2.0 (app.html · app-preview.html, v18.3) ──
# app.html 은 아직 커밋하지 않아서 지금 소스로 임시 빌드해서 봐요 (tests/buildapp.py).
# 화면에 그려지는 글은 smoke_v2.py · smoke_preview.py 가 휴대폰 크기로 열어서 다시 봐요.
# \b 는 'NaN원' 같은 글을 놓쳐요: 앞뒤가 영문자가 아닐 때만 낱말로 봐요.
WHOLE_BAD = re.compile(r"(?<![A-Za-z])(nan|NaN|None|null|undefined)(?![A-Za-z])")
V2_PAGES = ["app.html", "app-preview.html"]


def page(name):
    from buildapp import built
    return built(name)


def test_null_word_pattern_catches_glued_words():
    assert WHOLE_BAD.search("NaN원") and WHOLE_BAD.search("±NaN만원") and WHOLE_BAD.search("값 null")
    assert not WHOLE_BAD.search("Financial Nancy annual")


def test_no_emoji_in_app():
    for name in V2_PAGES:
        hits = EMOJI.findall(page(name))
        assert not hits, f"{name} 이모지 {len(hits)}개: {sorted(set(hits))}"


def test_no_banned_words_in_app():
    for name in V2_PAGES:
        html = page(name)
        found = {w: html.count(w) for w in banned_words() if w in html}
        assert not found, f"{name} 에 금지어가 들어 있어요: {found}"


def test_app_visible_html_has_no_null_words():
    # 스크립트 밖(제목·머리말)에 보이는 글, 그리고 화면 문구 파일의 모든 문장
    for name in V2_PAGES:
        html = re.sub(r"<script>.*?</script>", "", page(name), flags=re.S)
        html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
        assert not WHOLE_BAD.search(re.sub(r"<[^>]+>", " ", html)), name
    html = re.sub(r"<script>.*?</script>", "", page("app.html"), flags=re.S)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", html)
    assert not WHOLE_BAD.search(text), WHOLE_BAD.findall(text)
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as f:
        strings = re.findall(r'"([^"\n]*[가-힣][^"\n]*)"', f.read())
    assert len(strings) > 150
    bad = [s for s in strings if WHOLE_BAD.search(s)]
    assert not bad, bad
