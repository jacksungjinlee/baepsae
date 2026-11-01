# 뱁새 changelog

One line per merge: KST date · PR number · plain-English summary. Newest first.
Claude Code adds a line for every merge so Jack and his claude.ai chat can follow the history (`CLAUDE.md` § GitHub process).

| Date (KST) | PR | What changed |
|---|---|---|
| 2026-11-01 | #4 | v17.5: Korean prices are the official KRX close of one date, and a publication gate (`validate_data.py`, about 60 checks incl. a missed trading day) blocks wrong or stale data from going live. The rates tab and the risk-free rate work again; the five fund items and 금현물 are live; US prices, units and dividend yields fixed; DART results saved between runs. Fixes "보통 해 ±NaN만원" for every portfolio; per Jack's Option B, verdicts, the health score and expected-return figures stay hidden until v18. Stocks without data show "–" instead of invented numbers. |
| 2026-11-01 | #3 | v18.1 Parts 1–2: new design building blocks (colours, the Pretendard font, 15 components) and a style page at /baepsae/styleguide.html for Jack to review on his phone. New files only; the live app did not change. Jack's decisions: keep the darker up-red `upOnPage #B4232F`, use the true minus sign "−" everywhere, the public style page address is fine. |
| 2026-10-31 | #1 | v17.4.1 hotfix: the daily update reads yesterday's *final* KRX stock list again, so search finds 현대차 and the other big stocks that had vanished; data files can no longer contain NaN (the 공시·수급 tab loads again); all dates use Korean time. |
