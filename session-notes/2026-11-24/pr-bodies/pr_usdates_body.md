## What changed

- **A US purchase, sale or dividend now gets the date it is booked on in the US.** Between 23:30 and 06:00 KST in winter (22:30–05:00 in summer) the US market is open, but the Korean date is already "tomorrow" in New York. The record forms (샀어요 · 팔았어요 · 배당 받았어요, also 팔고 빼기) opened on the Korean date. The New York date that the form's own hint asks for ("미국 주식은 미국 현지 날짜로 적어 주세요.") was refused with "이 날짜의 환율이 아직 없어요." (audit 2.1; re-run on live data: refused at 01:00 and 05:30 KST).
- Now a dollar record's form opens on New York's date (`format.usTradeDay`, daylight saving included). The date turns over at 20:00 New York, not midnight: from 20:00 the overnight session (주간거래) books trades on the next US day (round-1 review). So the default differs from Korea's date **only from 00:00 to 10:00 KST in winter (09:00 in summer)**; from 10:00 to 24:00 it is Korea's date, exactly as on main.
- **The rate that date saves.** Before the 06:40 publish (the US session after Korean midnight) the date is not in the history yet, so it saves today's rate (data.json `fx`), where main refused it. After the 06:40 publish it saves that day's rate from the history, the same as main gives that date when it is typed.
- **Records made from 06:40 to 10:00 KST now default to New York's date.** That is the usual time to record last night's trade. They therefore save that date's history rate instead of today's: on 11-24, 1,345.9원 instead of 1,340.7원. So right after 샀어요, 내 수익 shows a small exchange-rate effect on the dollar part (about −0.4% that day) where main showed none. This is by design (#117: a record keeps the rate of its own date).
- Why the date matters beyond the refusal: stock splits are dated in US trading days. A purchase made in New York's 11-23 session but dated 11-24 (the Korean date) would count 10 times too few shares after a 10-for-1 split starting 11-24. Dated 11-23 it counts right.
- 매수 계획's 샀어요 sheet: with the date left blank, its US (dollar) rows get the same US date and its Korean rows Korea's date; a typed New York date is no longer refused there either.
- **오늘 볼 것 · 다가오는 일정** keeps a US earnings or ex-dividend date until midnight in New York (14:00 KST in winter, 13:00 in summer), not midnight in Korea (audit 2.2). Before, NVDA's earnings date dropped off at 00:00 KST, about six hours before its after-close release.
- **Not changed here (follow-up PR): the 코스피 comparison.** A dollar record's 코스피 comparison starts from the last 코스피 close before its date (`lots.js` `closeBefore`). So a record dated New York's date also counts that day's 코스피 move, which happened before the US trade (live 11-24 01:00: "코스피 −3.3%" instead of 0.0%). main already does this for typed US dates and for US records made from 14:00 to 24:00 KST; this PR makes it the default from 00:00 to 10:00 KST too.
- Unchanged: Korean records (checked against main's own code: 309,328 comparisons over 480 clock times, 0 differences), the latest date anyone can type (Korea's today), the store's checks and the records-file import, every other 오늘 볼 것 card, 이번 주 정리. No new Korean text.

## Choices I made

- **Waits for Jack's yes: the US trade date of now saves today's rate before the history has it.** main refused it with Jack's approved line `rec.rateNotYet` (11-13), which was written for "last night's US date before the morning publish"; that date now saves with today's rate (data.json `fx`), as a Korea-dated record always did. If Jack says no, only this part is reverted (one line in `records.rateFor`). The default date, the 20:00 roll and 오늘 볼 것 stay either way. RUNBOOK "Exchange-rate history and stock splits" now describes the rule. One date can then have two rates: typed at 01:00 KST it saves today's rate; typed after the 06:40 publish, that day's history row.
- **Roll at 20:00 New York** (`format.usTradeDay` = New York's date 4 hours from now) for the record default, the blank date in 매수 계획 and the date that gets today's rate. **오늘 볼 것 keeps New York's midnight** (`format.todayNy`). The trade-date rule for the overnight session comes from broker documentation (Alpaca, Webull, IBKR); I did not verify it against a Korean broker.
- **Weekend New York date (Monday 00:00–10:00 KST): the default is Sunday, the calendar date, not stepped back to Friday.** It is the simplest rule and needs no new words or trading calendar. It reads exactly like Friday for splits, because no split is ever dated on a weekend (a split starting Monday counts it before, ×10). It saves today's rate while the history ends on Friday. Once the history passes Sunday, a Sunday date takes the last row before it, Friday's (as any weekend date on main). The same applies to a US holiday (Thanksgiving 11-26).
- **The latest date anyone can type stays Korea's today.** The US trade date is never later than that, so it is always accepted. Capping a dollar record at the US trade date would refuse the Korean date that main saves, and an existing screen check (`smoke_v2` scene v19.6a "fxHist 없음 … 오늘은 저장") types Korea's date for a US sale at 07:00 KST and expects it saved. Typed, Korea's date takes today's rate, as on main.
- **Which rate the US trade date gets:** the history's row when the history has that day, otherwise today's rate. A history whose last row is not final (never under `ecos_close`, the source in use) gives that date today's rate too, as main does for Korea's today (pinned in a test).
- **"A US stock" = priced in dollars** (`records.recordCcy` in the forms, `pf.usdOf` in 매수 계획), never `cls`. In 매수 계획's sheet one rule (`usdOf`) now decides a row's date, its rate, its saved currency and its price label (round-1 nit; before, the last three used `cls`; 379800 is the only stock where they differ and can't be a plan row).
- **Left on Korea's date on purpose:** the split view (`withDataSplits`), the "today's close can stand in for the price" rule (`closeIsDefault`), the store's checks, the records-file import, and 금액으로 넣기 (already dated with the US close date, `usPxDate`).
- **이번 주 정리 · 다음 주 still starts at Korea's date** (round-1 nit). I tried New York's date; an existing test (`tests/test_v196e_weekly.py::test_next_week_never_shows_a_date_before_today`) pins Korea's, so I left it unchanged. Only on a long holiday does the card still show into next week, and then a US date New York still calls today drops a few hours early. Follow-up with Jack's yes to that test.
- **Undated 가진 종목 넣기 rows still count splits from the portfolio's `createdAt` (Korea's date)** (round-1 nit, `pf.js:556`). If a US holding is imported between 00:00 and 10:00 KST, sold the same night on the default date, and a split is then published for the Korean date, the sale counts before the split and the import after it (shown −90 where main showed 0). This needs a data model choice (a date on those rows), so it is a follow-up, not this PR.
- **"{md} 시작" on 포트폴리오** (`portfolio.jsx:174`, round-1 nit) shows the earliest purchase date. A portfolio made through 매수 계획 between 00:00 and 10:00 KST with US rows now starts on New York's date (11월 23일 for one made 11-24 KST), because that is its first purchase's date. I left it as is.
- **홈's 오늘 볼 것 now recomputes when either date turns** (`home2.jsx:415`, `today.jsx:272`: Korea's and New York's dates added to the memo's inputs, round-1 nit). Before, it could stay a day behind until the data or records changed.
- Edges left as is: a US purchase recorded before this release with the Korean date, then sold in the same night after it, needs its sale date typed (the default is earlier than the purchase, refused with the existing "처음 산 날보다 앞선 날짜예요."). Also, a US event already past in New York today (a pre-market release) stays on 오늘 볼 것 until New York's midnight.
- `RecordSheet` in `plan.jsx` is now exported, only so the new screen test can render it.

## 「새 문구」

없음. No user-facing text added or changed. The lines involved are the approved `rec.usDateHint`, `rec.rateNotYet` (now shown in fewer cases) and `rec.noTodayRate`.

## 안전 규칙 변경

없음. No existing test or `validate_data.py` threshold changed.
- **Added:** `tests/test_v2_us_dates.py` (10 tests, Node with a fixed clock):
  - the date helpers: New York's date and the US trade date at every hour of 2026–2027 in five device time zones, both daylight-saving changes, and the 20:00 roll at 09:59/10:00/13:59/14:00 KST in winter and 08:59/09:00/12:59/13:00 in summer;
  - 01:00 and 05:30 KST in winter, in summer and on Thanksgiving: buy · sell · dividend saved with today's rate where main refused "notYet"; Korea's date still saves; stale data gets the today line; the morning after keeps the history's rate (equal to main's for every date since 2016 except the US trade date before the history has it);
  - the overnight window opens on Korea's date with today's rate, exactly as main; Monday morning opens on Sunday;
  - splits: one on the Korean date counts 100 shares (not 10); one on the rolled date leaves the record on the new count;
  - a non-final history; won records equal to main at every clock (also 379800);
  - 오늘 볼 것 keeps a US date until New York's midnight, and every other card is unchanged.
- **Added:** `tests/test_v2_us_dates_screens.py` (3 tests, the screens rendered in Node with react-dom/server; the 저장 button's own handler is called). At 01:00, 09:00, 11:00 and 15:00 KST it checks:
  - the record form's date field: its value and its max;
  - the saved purchase and sale, with date and rate (1,338원 today, or 1,345.9원 from the history at 09:00), and Korean records unchanged;
  - 매수 계획's 샀어요 with a blank date: the Korean row keeps Korea's date in won with no rate, and the US row gets the US date and that date's rate.
  - The tests fail when the default is set back to Korea's date (checked).

## Test evidence

- `bash build.sh && bash build-app.sh`: OK. `app.html` and `app-preview.html` rebuilt and committed; `baepsae.html` unchanged.
- `python -m pytest tests/ -q -p no:cacheprovider`: 5380 passed, 1 skipped in 544.94s.
- `python -m pytest tests/test_v2_us_dates.py tests/test_v2_us_dates_screens.py -q`: 13 passed.
- Main vs this branch (scratch script bundling `origin/main`'s `src/v2` beside this branch's): 309,328 comparisons, 0 differences. It ran 480 clock times (every 30 minutes on 10 days, including both 2026 daylight-saving changes, Thanksgiving and 12-31), 3 history cut-offs, fresh and stale data, and covered:
  - won records (005930, 379800): buy · sell · dividend on a blank, Korea's, the US trade date's and past dates;
  - every dollar call without the US trade date (and weekly's env), and every typed dollar date other than the US trade date;
  - `rateFor` without usDay;
  - 오늘 볼 것 except the dates rows, and the dates rows whenever New York's date is Korea's.
- Auditor's repro on live data (11-24 publish, history to 11-23), rebuilt on this branch:
  - 09:00 KST 11-24: the form opens on 11-23 and saves 1,345.9 (Korea's 11-24 typed: 1,340.7);
  - 10:30 KST 11-24: opens on 11-24, saves 1,340.7, as on main;
  - 01:00 and 05:30 KST 11-25: opens on 11-24, saves 1,340.7.
  - The auditor's run on main refused New York's date (`notYet`).
- `python tests/smoke_v2.py`: 942 / 942 통과
- `python tests/smoke_app.py`: 176 / 176 통과
- `python tests/check_text.py`: 글자 점검: 페이지 4개 · JSON 87개 · 문제 0개
- Real data (data branch copy of the 11-24 publish, pxDate 2026-11-23, published 2026-11-24 06:40 KST): `real_data_check.py --data` 3 / 3 통과 · `smoke_launch.py --data` 14 / 14 통과 · `smoke_app.py --data` 171 / 171 통과

## Fresh-eyes review

The PR touches the exchange rate and share count on records (money), so round 1 had two independent reviewers (Opus 5.5 Extra high, Fable 5.2 High). Later rounds use Fable alone.

Round 1: no blockers from either reviewer.
- Both, S1: the default was a day early for overnight-session trades, 10:00–14:00 KST winter (09:00–13:00 summer). **Fixed:** the record date rolls at 20:00 New York (`usTradeDay`), with tests at the edges, for a split on the rolled date, and for Monday morning.
- Fable S2: the rate rule reverses Jack's approved `rec.rateNotYet` for one date, and the RUNBOOK was not updated. **RUNBOOK updated; the rule is listed above as waiting for Jack's yes.**
- Fable S3: the screen wiring was untested. **Added** `tests/test_v2_us_dates_screens.py`.
- Opus S2: the 코스피 comparison now includes the record day's 코스피 move by default. **Stated above; follow-up PR.**
- Opus S3: the body said the morning was unchanged; it isn't (06:40–10:00 KST, history rate). **Fixed in What changed; After merge now says 00:00 KST.**
- Nits:
  - `plan.jsx` one rule (`usdOf`): **fixed**;
  - 홈 memo dates: **fixed**;
  - non-final history: **pinned in a test**;
  - `portfolio.jsx` "{md} 시작", `pf.js` undated rows, `weekly.js` 다음 주, the sheet's unsaid day gap, pre-market events: **listed under Choices**.

## After merge

- Watch the deploy; check the live site: search 005930 and 현대차, open every tab, check the dates.
- After 00:00 KST and before 10:00 KST (09:00 in summer): a US stock's 샀어요 form opens on yesterday's date in Korea (New York's date) and saves. From 10:00 KST it opens on today's date, as before. A Korean stock's form opens on Korea's date at any time.
- For Jack (phone): nothing to look at unless you record US trades between midnight and 10:00; then the form's date is the US date, as its hint says. Question for Jack, asked separately: may that date save with today's rate before the morning publish (instead of "이 날짜의 환율이 아직 없어요")?

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
