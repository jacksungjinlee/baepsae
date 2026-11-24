**Track 2 audit: full list, checked and ranked** (5 Fable helpers, one target each; I re-ran or re-read each finding myself)

Serious (7) — each in its own PR:
1. **18 Korean dividend payers shown as paying nothing** (3.1). The DART table has a cash total but "-" in the common per-share cell, which we read as 0. 2.0 said "배당을 주지 않았어요". → #179: unknown + the approved line 4. Waits for your yes (Q6).
2. **SNDK PBR 0.63, about 8× too low after its 8:1 split** (3.2). The cause is Yahoo's stale book value. The audit also found a hidden bug that would make all four numbers 8× off for a cached stock. → #176: fix plus a warning row. Ready; merges after the 08:35 test run.
3. **Korean 실적 stuck on 2Q five days after the 3Q deadline** (3.3). Fixes itself in this morning's run; #180 stops it happening at the next deadline. In review.
4. **Raw DART yields that aren't yields in the old app** (3.4): 흥국 56.0%, 와이엔텍's per-share dividend of 18억원. → in #179.
5. **홈 "오늘" counted shares bought after the last close** (4.2). A purchase recorded Saturday showed "오늘 −17만원" for a loss nobody had. → #177: fixed, waits for your yes on the line (Q7).
6. **The weekly card compares your % (from your buy price) with 코스피's full week** (4.1). A portfolio bought Saturday reads "0.0% · 코스피 −7.9%". → Q5.
7. **A single caught error could stop the whole publish** (5.2). Our own error text wrote "NaN"/"None" into the files, which the word check rejects. → #178: ready; merges after the 08:35 test run.

Serious, rare or not yet happened (2):
8. **Splits with odd ratios (DD 1:3, UL 8:9) break records saved before them** (1.1). A refused save retried endlessly; a valid sale was refused. App PR next.
9. **The pre-publish screen test would hold everyone's publish if a built-in stock's price history is marked broken** (5.1). Fixing it means editing a publish-blocking test → Q4.

Minor (about 25), fix later in small PRs:
- dividends and money: 0.0001주 left after a split sale; fractional US shares shown as whole (7.5 → "8주"); tax screen "약 0원" for small dividends; a deleted record coming back from a second tab;
- dates: a US record typed after midnight KST is refused for its US date; 오늘 볼 것 drops a US earnings date at midnight KST; 내 수익 labels US-only prices with the Korean date after US holidays;
- pipeline: one failed gold download drops all correlations; 13 US ETFs sit in the US percentile base (SOXX 가치 100); "최근 2년 연평균" growth is really 1-year for 32 small companies; data.json's won rate is Yahoo's open bar (0.7% off); a run more than 9 hours late can publish Korea-new/US-old; on a Korean holiday one lost stock can hold US closes;
- missing reason lines: 다가오는 일정 stops at 5 with no "외 n"; the weekly left-out line is untrue for stocks added this week; weekly gain leaves out dividends with no line; 오늘 등락률 rounds two ways (−16.0% vs −16.1%).

Unsure / false alarms (6): 본시스템즈 (KONEX) mom 4,739% matches the source; 업종별 등락 plain average (true as worded); "다음 주" tile on Monday; 49 old corrections left out (waits on your #145 Q3); ~25 gate rows that fail on one row need a new pipeline bug first; implausible-type crashes.

### Found 11-24 (by the #188 Opus reviewer, checked by me) — minor
- **US funds in the US 가치 pool.** 23 US ETFs/trusts carry Yahoo's priceToBook (SOXX 0.37, TLT 0.55, GLD 2.04, SPY 1.76 vs real ~5). It means nothing for a fund. add_percentiles(us) ranks them with companies, so every US company's vz is off by up to 3 points (mean 1.2; checked on the 11-24 file). Funds get vz 100 (SOXX, TLT) but 2.0's lists and company pages leave funds out (isStockLike / isCompany). Order of the 가치 lists is unchanged (they sort on pbr). mz/lz/qz pools include funds too. Fix: percentiles over companies only; small pipeline PR.
