## What changed
- **From the Track 2 audit (11-23), finding 3.3.** On 11-21 every Korean company's 실적 figures (TTM) were still on 2026.2Q (2,244 companies, none on 3Q), five days after the 3Q filing deadline.
  - **Why:**
    - a "not filed yet" answer from DART on the deadline days waited 7 days before it was asked again;
    - DART's statement API runs a day or two behind the filings;
    - 11-14 was a Saturday, so the legal deadline was Monday 11-16.
  - The top 100 never reached the 70% that switches the quarter.
  - Under the old rule the 7 days were up on 11-23. PR #176's dry run that evening, on the old DART code, already showed `분기 판단: 2026.3Q — 시가총액 상위 100곳 중 99곳 제출`, so the 11-24 publish should move to 3Q by itself. This PR is for the next deadlines.
- **Now:**
  - filing deadlines roll to the next KRX trading day;
  - still-missing statements are asked again every day from the deadline − 7 until the rolled deadline + 21 days, both before and after the run switches to that quarter (사업보고서 too). After that, the old every-7-days rule applies again;
  - the old rule is untouched: an entry keeps its old-rule date, and a late ask writes its own date (`lt`), so every old-rule ask happens on the same day as on `main` and the late asks come on top.
- **Only what a run really asks is planned:**
  - for the quarter in use, the one statement the main loop asks for that company;
  - for a newer quarter not yet in use, only the current top 100, in the quarter choice's second count, which asks only those planned entries.
- **Budget:**
  - at most 300 extra DART calls a run, plus up to 2,500 while the quarter in use is inside its window. 2,500 + 300 is more than the 2,474 listed companies, so in effect every company still missing the quarter in use is asked once a run. Calls are counted as they are made (failed answers count too, and a key is asked at most once a run). Entries asked longest ago go first, then the biggest companies, so under the cap every missing entry gets its turn within a few runs;
  - only on ordinary `dart=cache` runs with a cache: never a full-DART run, never a run that starts with an empty cache, and a 020 (DART's daily limit) stops these calls like every other call;
  - dry runs (`DRY_RUN=true`) get only the 300, never the 2,500, and the log says so. The path is still exercised;
  - day guard: the DART cache keeps that KST day's call count (added at every save). When it is already past 10,000, the run skips its late asks with a loud "!!" line naming the count. The old rule's calls are never limited by it. The count lives in each cache, so a run sees the earlier runs that saved into the cache it restored (on `main`, that day's earlier `main` runs), not other branches' dry runs;
  - each company newly found for the quarter in use also makes one first-time call for last year's same quarter, the same call `main` makes when it finds it;
  - a second start on the same day (after a failed publish) can ask again what the first start couldn't store or left under the cap;
  - the busiest runs are the same as on `main`. A switch day costs about 5,000–8,700 calls for the publish alone: this year's and last year's same quarter for every company not yet asked (about 4,800), plus its usual calls. Other window days cost about 750–1,800. All stay under the 16,000 a run target;
  - a switch-day publish plus a full-DART run, or plus several branch dry runs started before it, can pass DART's 20,000 daily limit, with or without this PR. The RUNBOOK says to avoid a full-DART run in the week after a quarter deadline, and during a deadline window to start branch dry runs only after that KST day's publish, on a branch with no older DART cache of its own (a branch restores its own older cache first and then redoes everything since).
- **Offline replay on the 11-21 company list** (2,474 companies, 3Q showing up in DART's API from 11-10 to 11-25):
  - this PR switches to 3Q on 11-17, against 11-23 under the old rule;
  - late calls a run: 69, 604, 424, 259, 209, 144, 0, 62 (0 on 11-24, the old rule's 7-day day);
  - every company whose 3Q had shown up was on 3Q the same day.
- **Side by side with `main` on twelve offline cases** (the reviewers' cases: 3Q adopted early, an 800 day, two runs skipped, 2Q 2026 window close, the 2027-08 holiday week, 사업보고서 2026 with and without an 800 day, top-100 churn with and without an 800 day, three replays on the live list): no company was behind `main` on any day, except in one known case below.
  - **Known exception:** after the rolled deadline + 21, when this PR switched to the quarter on a different weekday than `main` would have, both ask a still-missing company once a week on different weekdays. A company whose numbers first show up after that point can switch up to 6 days later than on `main`. In the 2027-08 holiday case that was 21 of 1,200 companies for one publish (3 days). Closing it would mean asking the quarter in use's missing companies every day for as long as the quarter is in use (about 35–100 calls a day after the window). I left the 21-day limit from the brief as it is.
- The quarter choice is now written into `corp.json` as `qPick` (quarter, top-100 count, how many filed). The app doesn't read it.
- **New warning-only gate row** "분기 판단 (corp.json qPick · 경고만)": warns when the quarter in use is still the previous one more than 10 days after a rolled deadline. It checks this year's 1Q–3Q only, never the 사업보고서.
- RUNBOOK section "DART: asking again after a filing deadline"; HANDOFF § 0 and CHANGELOG updated.

## Choices I made
- **Daily re-asks continue after the quarter switch, up to + 21 days.** Both reviewers simulated the first version, which stopped at the switch: it left smaller companies on the old quarter for up to four publishes longer than `main`.
- **The quarter in use gets up to 2,500 extra calls (one per company) for its whole window, not just its first week.** Round 2 showed the 300 cap alone kept re-asking the same big companies, so smaller ones fell behind `main` (151 companies on 11-21 in the slower-fill replay). Rotation alone can't guarantee "never behind" on the day `main` first asks every company; asking each missing company once a day can. The window version needs no stored adoption date, and its cost shrinks as companies file (the most was 886 late calls a run on the live list).
- **Late asks keep the old rule's date and write their own (`lt`).** Otherwise a late ask pushed the old 7-day rhythm back, and after the window some companies switched later than on `main` (2Q 2026 and 사업보고서 2026 cases).
- **Day guard at 10,000 calls, counted per KST day in the DART cache.** Late asks are the only thing it turns off, so a busy day can delay a re-ask by a day but never stops the old rule or the publish. The day is the run's start day plus any midnight it crosses, so a run past midnight counts toward the new day (counting high, not low).
- **Dry runs get only the 300.** They still exercise the late path, but can't use the allowance meant for the publish.
- **사업보고서 always gets the full 21 days.** There is no market-wide switch for annual reports.
- **The quarter is counted with the old rule first.** The run asks again only if that leaves the quarter under 70%, so the top-100 count stays exact.
- **A report whose other statement was found is skipped.** A company that files only separate statements always answers "no data" for the consolidated one. The rare company whose consolidated statement shows up later than its separate one waits 7 days for it, as on `main`.

## 「새 문구」
없음. New Korean text appears only in the run log and the gate summary.

## 안전 규칙 변경
- **Added:** gate row "분기 판단 (corp.json qPick · 경고만)". It never fails, including when its own check crashes or the holiday table is missing.
  - On a fresh copy of the data branch (still the 11-21 publish) it passes on 11-24 ("… 2026-11-16 뒤 8일 (아직 앞 분기 · 10일 넘으면 경고)").
  - Checked as of 11-27 it warns ("…뒤 11일인데 아직 2026.2Q 기준 …").
- **Added:** new test file `tests/test_dart_late_retry.py` (46 tests, including side-by-side runs against the old rule, the dry-run cap and the day guard).
- **No existing test edited.** `tests/test_pipeline.py`'s comment "마감+3일부턴 다시 7일" still describes `dart_entry_due`, which is unchanged; the new retry sits on top of it.

## Test evidence
- `python -m pytest tests/ -q`: 5073 passed, 1 skipped.
- `bash build.sh && bash build-app.sh`: pages unchanged.
- `python tests/check_text.py`: 0 problems.
- **Gate on a fresh copy of the data branch (still the 11-21 publish):** the new row passes ("… 2026-11-16 뒤 8일 (아직 앞 분기 · 10일 넘으면 경고)"), and no other row changed. The live-only row `최종본 날짜 계산` can't fetch from this sandbox, the same as on `main`.
- **The dry run exercises it:** 3Q's window stays open until 12-07 (rolled deadline + 21), so the companies still missing 3Q are re-asked. A dry run on the same KST day as the publish that switched to 3Q makes 0 late calls (that morning already asked everything), so it runs on 11-25 or later. The offline replays cover the switch itself; the first full season is the 사업보고서 window in April 2027.
- **Dry run:** 11-25 or later. Results will be added here.

## Fresh-eyes review
Pipeline PR: two independent reviewers in round 1, then Fable alone.
- **Round 1, Opus 5.5 Extra high: no blocker.**
  - S1: switching early shrank coverage for smaller companies. Fixed: daily re-asks continue to + 21.
  - The OFS slots were never asked, which halved the cap. Fixed: only the asked statement is planned.
  - S2: misleading log lines ("!!" when 0 were asked, keys never asked counted as left, a missing plan size, a wrong RUNBOOK claim). All fixed.
  - Nits fixed: cap on calls, gate wording.
- **Round 1, Fable 5.2 High: no blocker.**
  - S1: an 800 answer let the same keys be asked twice, 400 calls against a cap of 300. Fixed: the cap counts calls, and a key is asked once a run.
  - S2: same as Opus S1. Fixed.
  - S3: same as Opus S2. Fixed.
  - S4: the dry run won't exercise the path. The offline replay was added.
  - Nits fixed: budget text, tests for the cap, the full and empty-cache runs and 020, docs.
- **Round 2, Fable alone (199d43a): no blocker.**
  - S1: under the 300 cap the same biggest still-missing companies were re-asked every day, so smaller ones fell behind `main` (151 on 11-21 in the slower-fill replay; also the 2027-08 holiday week and top-100 churn). Fixed: entries asked longest ago go first, and the quarter in use gets one call per company for its window.
  - S2: a late ask moved the old rule's date, so after the window the next ask came up to 28 days later (2Q 2026 and 사업보고서 2026 cases behind `main`). Fixed: the old rule's date is kept, and late asks write `lt`.
  - S3: the second count re-asked the whole top 100, including entries whose first answer failed this run (398 calls against `main`'s 198 on an 800 day). Fixed: only planned entries, all counted (200 against 198).
  - S4: a same-day dry run after the publish that switches makes 0 late calls. The RUNBOOK says so, and the dry run is on 11-25 or later.
  - Nits fixed: the end line's reason (DART stopped vs the cap), the "missing re-ask line = bug" claim, the budget text, and a 000 answer that can't be read no longer counts as newly filed.
- **Round 3, Fable alone (7f1847f): no blocker.** It checked the new allowance of up to 2,500 calls for the quarter in use against DART's 20,000 a day.
  - S1: nothing at the day level stopped late asks from using up the day's allowance before the publish (switch day: publish plus 3 dry runs started before it ≈ 20,000–21,400, the same on `main`). Fixed: dry runs get only the 300, and a per-KST-day call count in the DART cache turns late asks off past 10,000.
  - S2: the RUNBOOK's dry-run and budget sections now say when to start branch dry runs in a window (after that day's publish, on a branch with no older DART cache), and that a switch day costs about 5,000–8,700 calls for the publish alone.
  - Nits fixed: two comments still said "biggest companies first" (now oldest-asked first); the 7-day batch of 3,300 is marked as a replay artefact (real runs had at most about 200 "not filed yet" answers a day); the RUNBOOK says 2,500 + 300 covers every listed company.
- The rounds stop here: round 3 had no blocker.

## After merge
- **The next publish runs this code.** I'll read the new log lines (windows open, plan, "다시 물음 / 새로 냄 / 아직 없음 / 다음 실행으로 남김"), `corp.json qPick` and the gate row.
- **For Jack:** 없음. It shows when the 4Q 사업보고서 season comes (March 2027).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
