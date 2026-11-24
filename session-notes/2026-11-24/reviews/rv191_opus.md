Opus r1 #191 (7a3db75): 0 blockers, 3 should-fix, 3 nits

**Blockers:** none.

**Should-fix**

1. **The overnight session (주간거래) now gets the wrong date by default.** The default is `records.js:82` recordToday / `todayNy`, used at `records.jsx:181` and `plan.jsx:339`. US overnight trades made from 20:00 to 24:00 ET are booked on the *next* US trading day ([Alpaca](https://docs.alpaca.markets/in-giftcity/docs/245-trading), [Webull](https://www.webull.com/help/faq/10988-All-about-overnight-trading=), [IBKR](https://www.interactivebrokers.com/campus/trading-lessons/overnight-trading-in-tws/)). In Korean time that is 10:00–14:00 in winter and 09:00–13:00 in summer.
   - Failing case: a 주간거래 purchase at 11:00 KST on 11-25 now defaults to 11-24. With a 10-for-1 split starting on the 11-25 US trading day, the record would show 10× too many shares. It also gets 11-24's Seoul close instead of today's rate. main's Korean-date default was right in this window.
   - On Monday (KST) before 14:00 the default is Sunday, which is never a trading day.
   - Fix: either use New York's date of (now + 4 h) for the record default and keep `todayNy` for 오늘 볼 것, or list this under Choices.

2. **The 코스피 comparison now includes a 코스피 day that happened before the purchase.** `lots.js:465/478` kospiMirror uses `closeBefore`, the last 코스피 close strictly before the record's date. For a dollar record dated D, 코스피's close on D (15:30 KST) always comes before the US session D.
   - On live data, an AAPL purchase at 01:00 KST 11-24 now defaults to 11-23. indexSince then gives "코스피 −3.3%" (the 11-20 close to the 11-23 close, all before the purchase). With main's date, 11-24, it gives 0.0%. This is the same kind of misleading comparison as audit 4.1.
   - This already happened on main for typed US dates and for US records made from 14:00 to 24:00 KST. This PR makes it the default after Korean midnight too.
   - Fix: say so in the PR, and in a follow-up use the 코스피 close on or before the date for USD records.

3. **The PR body says "exactly as before" for the morning, but the morning changes.** Records made from 06:40 to 14:00 KST (the usual time to record last night's trade) now default to New York's date. They save that date's history row instead of data.json `fx`.
   - Live 11-24: 1,345.9원 instead of 1,340.7원.
   - So right after 샀어요, 내 수익 shows an exchange-rate effect of about −0.4% on the dollar part, where main showed 0.
   - The design behind this is sound (#117: the rate of the record's date), but "What changed" should say it plainly.
   - Also, After merge says "After 01:00 KST"; it should be 00:00.

**Nits**

- In `plan.jsx`, the date is chosen by `usdOf` (line 339), but the rate rows, the saved currency and the price label still use `cls === "us"` (lines 364, 371, 412). Nothing reachable today mixes the two (379800 is an ETF and can't be a plan row), but one rule for all three would be safer.
- `portfolio.jsx:174` "{md} 시작" now shows New York's date for a portfolio made after Korean midnight (11월 23일 for a portfolio made on 11-24 KST).
- `home2.jsx:415` and `today.jsx:272`: the lookModel memo has no date in its deps, so it can go stale across Korean midnight. This is not new, but it now applies to New York's midnight too.

**Found sound**

- Dates and clocks:
  - `todayNy` is right across daylight saving, device time zones and midnight. I checked the edges and the test's hourly sweep.
  - New York's date is never later than Korea's, so the store's checks, `badDate`, `max`, the import, the split view and `closeIsDefault` still accept every record the forms save.
  - Records saved on main keep their dates and counts.
- Rates:
  - The rate rule lets New York's today fall back to today's rate only when the history lacks that day (or the history is non-final or missing). Stale data gets the today line.
  - No record gets a different day's rate beyond main's existing "today" behaviour. A data.json split can't be dated after New York's today.
- Won records: identical at every clock I tried; 379800 keeps Korea's date.
- Splits: after-midnight US-session purchases are now counted correctly.
- 오늘 볼 것: only the dates rows changed. Rows stay until New York's midnight and are never shown after their date. weekly's 다음 주 is unchanged.
- Rules and checks:
  - No existing test edited and no new Korean text. The only ISO date added is in a comment.
  - Tests: the three named files 25 passed; test_v2_records, test_v196e_weekly and test_v196b_cards 69 passed.
  - `build-app.sh` rebuilds app.html and app-preview.html byte-identical; baepsae.html is unchanged.
  - smoke_v2's fixed clock (07:00 KST) already exercises the New York date path.
