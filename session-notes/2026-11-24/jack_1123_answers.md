Jack 2026-11-23 (~21:xx KST), verbatim:
Answers: 1 yes. 2 yes. 3 yes. 4 yes, but one decimal only under 10억원; whole 억원 above that; 조원 with one decimal, the same as other amounts.
Around the clock until Wednesday 21:00 KST (Jack, 11-23). Jack has 80% of his weekly usage left. Keep working continuously. Stop new work if he tells you usage has reached 95%. At most four helpers at once. Every CLAUDE.md rule still holds, including the reviewer mix: Opus plus Fable for round 1 on data and publishing PRs, then Fable alone.
Track 1: build, in this order:
1. The v19.6b switch-on (run the real-data checks before merging, results in the PR).
2. Automate the rules you missed: a CI check that blocks merging a PR that changes what the site serves unless its description contains the three real-data check results, and one that requires HANDOFF § 0 to change in any merging PR that changes src/ or the pipeline.
3. v19.3 Part L.
4. Data follow-ups already approved:
 * bring back PER, PBR and yield for the 27 non-dollar US stocks from whole-company totals at the day's exchange rate;
 * US minimum sizes for 종목 순위 (25억원 revenue a quarter, 100억원 equity);
 * Korean stock splits;
 * the 소액주주 yield;
 * repair the broken price history for the 18 stocks (old share consolidations).
Track 2: full-app audit on Fable 5.2 High, side by side. Look for bugs and wrong numbers nobody has caught, ranked by the two disasters. Targets, one helper per target:
1. Money math in records, 내 수익 and 연말에 확인할 숫자.
2. Dates and time zones in both apps and the pipeline.
3. Silent fallbacks and unit or currency mixing in the pipeline.
4. Every number hidden or adjusted without a reason line.
5. Places a single bad row could stop the whole publish.
For each finding, the helper shows the failing case; you check it and rank it serious, minor or false alarm. Serious ones get fixed in their own PRs right away. Send the full list in your morning update. Do not use Jack's Fable reset.
Wording: collect any new Korean lines into one 「새 문구」 message for Jack and keep building other items while you wait.
Still missing, fourth request: attach the say-why audit file and the 10 dark-mode screenshots in your next update.
