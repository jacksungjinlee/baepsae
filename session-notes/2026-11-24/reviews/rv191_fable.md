Fable r1 #191 (7a3db75): 0 blockers, 3 should-fix, 6 nits

## Should-fix

1. **Default date is a day early for trades made 10:00–14:00 KST (09:00–13:00 summer), where main was right** — `records.js:82`, `format.js:112`, `records.jsx:181`, `plan.jsx:339`.
   - New York is then 20:00–24:00 of the day before. Only the overnight session (주간거래) is open, and trades after 20:00 New York carry the next trade date, the Korean date.
   - Repro: 10:30 KST 11-24, buy 10 AAPL, date as opened → saved 11-23. After a 10-for-1 split dated 11-24 it counts 100 shares; main's default counts 10: the PR's own case, mirrored.
   - Trade-date rule confirmed from one US broker's documentation only.
   - Fix: roll the dollar-record default at 20:00 New York; 오늘 볼 것 can keep midnight.

2. **The rate rule reverses an approved refusal; RUNBOOK not updated** — `records.js:45-49`.
   - `RUNBOOK.md:2606` still says the app refuses dates after `asOf` "except today". Jack's `rec.rateNotYet` (11-13) was for "last night's US date before the morning publish" (`smoke_v2.py:11673`), which now saves.
   - One date, two rates: 11-23 typed at 01:00 KST saves 1,345.7 (Saturday's publish, `fxDate` 11-20); from 06:40, 1,345.9.
   - No worse than main's Korea-today default, but users can now save what was refused: cite Jack's yes or ask; update the RUNBOOK.

3. **Screen wiring untested.** `test_v2_us_dates.py` bundles pure modules only. Nothing checks the form opening on `day` (`records.jsx:184`) or `plan.jsx:339-373` (per-row date, rates map, `ratePart`). `smoke_v2` never asserts a default US date.

## Nits

- `records.js:48`: with `final` not true and the last row equal to New York's today, it saves `data.json` `fx` where main refused "past" (repro'd; untested; production is always final).
- `pf.js:556`: undated 가진 종목 넣기 rows still count from `createdAt` (Korean date), so the 2.1 miscount remains there. Import 10 at 01:00 KST, sell 10 on the default date, split published on the Korean date: held −90 (main 0).
- `weekly.js:298`: 다음 주 starting "today" is still Korea's, so it drops a US event 오늘 볼 것 keeps (repro'd: 1 row vs 0).
- `plan.jsx:339`: a blank date puts US rows a day before Korean rows, unsaid on the sheet.
- `records.js:150`: the default "처음 산 날보다 앞선 날짜예요" refusal also hits purchases typed with Korea's date, still allowed.
- `look.js:233`: an event already past in New York today (pre-market earnings, ex-dividend) stays until 13:00/14:00 KST next day. Nothing dated before New York's today shows.

## Sound

- `todayNy` / `todayKst`: daylight saving, five device zones, midnight edges; never later than Korea's.
- A date the history has always takes that row; rates differ from main only where main refused.
- Stale data and load failure give the "today" line. Won records, 379800, `weekly`'s env, store checks and Korean 오늘 볼 것 cards unchanged.
- No new Korean; no existing test edited.
- Tests: the three named files 25 passed; records, lots, tax, weekly, v196b, footer 486 passed. Both builds reproduce the committed pages.
- `smoke_v2` not completed: stopped at 343 passed, 0 failed.

## Check on your side

I stopped my `smoke_v2` with `pkill -f tests/smoke_v2.py`, which matches any session's run. If another was running at about 11:21 KST, it was killed and needs a rerun. Worktree `rv191_fable` removed.
