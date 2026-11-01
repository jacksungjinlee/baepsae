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


# ── 뱁새 2.0 미리 보기 (app.html, v18.3) ──
# 화면에 그려지는 글은 smoke_v2.py 가 휴대폰 크기로 열어서 다시 봐요 (nan·NaN·None·null·undefined 낱말 포함).
WHOLE_BAD = re.compile(r"\b(nan|NaN|None|null|undefined)\b")


def app_html():
    with open(os.path.join(ROOT, "app.html"), encoding="utf-8") as f:
        return f.read()


def test_no_emoji_in_app():
    hits = EMOJI.findall(app_html())
    assert not hits, f"app.html 이모지 {len(hits)}개: {sorted(set(hits))}"


def test_no_banned_words_in_app():
    html = app_html()
    found = {w: html.count(w) for w in banned_words() if w in html}
    assert not found, f"app.html 에 금지어가 들어 있어요: {found}"


def test_app_visible_html_has_no_null_words():
    # 스크립트 밖(제목·머리말)에 보이는 글, 그리고 화면 문구 파일의 모든 문장
    html = re.sub(r"<script>.*?</script>", "", app_html(), flags=re.S)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", html)
    assert not WHOLE_BAD.search(text), WHOLE_BAD.findall(text)
    with open(os.path.join(ROOT, "src", "copy", "v2.js"), encoding="utf-8") as f:
        strings = re.findall(r'"([^"\n]*[가-힣][^"\n]*)"', f.read())
    assert len(strings) > 150
    bad = [s for s in strings if WHOLE_BAD.search(s)]
    assert not bad, bad
