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
