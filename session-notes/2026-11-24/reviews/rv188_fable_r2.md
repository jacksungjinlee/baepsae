Fable r2 #188 (258a129): 0 blockers, 3 should-fix, 3 nits

Not mergeable yet: one test is red on purpose (Jack's yes needed) and the `dry_run` is pending. Today's effect is right. Yahoo still gives SNDK EPS 923.7 (1 yfinance call): PER cut (54.14×, band 2.83), PBR (1.30×) and the 0% yield stay.

**Should-fix**

1. **The hold can end while the number is still wrong** (`fetch_data.py:13951`, `:13998`, `:14107`, `:14143`). Only a `mismatch` in the previous publish holds a stock, so one bad day after the window loses it for good. Ran each at usPxDate 12-21 with SNDK held:
   - Yahoo's refresh lacks `netIncomeToCommon` (numeric keys aren't sticky): day 1 blank as `nocompare-own`; day 2 PER 0.1 is published, no mark, gate PASS with no warning.
   - `us_split_check` crashes: day 1 `stopped`; day 2 PER 0.1 back.
   - Step crash → `us_split_guard`, `holdErr`, or the recent-list crash: PER 0.1 is published the same day (the guard blanks only `recent`, never held stocks) and stays.
   - A crash on the last in-window day (12-18) does the same on 12-21.
   - Fix: carry the hold from the previous `usSplitChk.held` plus any mark, release only when a run compared the held field and it agreed; have the guard blank held stocks too.
2. **The hold makes structural false positives permanent, undisclosed** (`fetch_data.py:13942`; `validate_data.py:5402`; RUNBOOK:2094 "Yahoo usually corrects itself"). Ran an IBKR-like company (PER 29.2 ↔ 110.7) after a 4:1 split: still blank a year later. The body's own count puts 22 of 581 US companies beyond 1.5× on PBR; any of them that splits 2:1 loses PBR and 가치 점수 for good. The line stays true, but the gate row reads PASS with no warning. Fix: say so under Choices and in the RUNBOOK, and make the row warn while `held` is non-empty.
3. **Evidence and text predate the head.** The pytest, real-data, smoke and gate-simulation logs are from 00:49–01:02 UTC; 258a129 (02:07) merged #178, #185 and #187. Re-run on the head. The body still says #178 is "not on main yet" and that `usSplitChk` "belongs in its last pass": `PUB_SWEEP_KEYS` (`fetch_data.py:566`) doesn't have it.

**Nits**

- `norecord` (and a yield under `currency`) now shows "회사 전체 숫자와 비교할 수 없어서" (`src/v2/fcur.js:102`). What was missing is the dividend record or price, not company totals. Truer than "맞지 않아서", not literal; tell Jack. For PER/PBR under `currency` it is literally true.
- The band's cost is understated. A 3:2 split's full 1.5× error stays (ran it; the test is `>`). A halved PBR after a 2:1 split on an NVDA-like company (1.39×) reads 1.44× and stays (ran it).
- New log lines use `str(e)[:120]`, not #178's `pub_raw(e)`; the one in `us_split_guard` (`:14140`) sits outside its `try`.

**Sound**

- **Round-1 fixes:** bands only on split companies (NVDA-like 1.39× stays at 2:1, 10:1, 3:2, 1:10; APH-like 1.19× stays), foreign check called without a band, EPS fact corrected in code and docs.
- **Gate:** `validate_data.py` gains one call and one new block; every `rep.add` is ok=True, crash included; `held` is accepted only by the new row. Nothing existing changed.
- **Publish safety:** step and guard are both caught; record text is reason text through `_split_why` plus exception class names.
- **Tests:** the brief's set gives 432 passed, 1 failed (the expected one). The edited `test_us_split_rescale.py` passes 52/52 on main's code, as the original does, so the fixture edits change nothing there.
- **Proposed patch:** applied locally, 52/52. It keeps the record, the log line and proof that the fresh details were used (the reason starts "주가 ÷ 주당 장부가 0.63"; the copy path would give no cut row and fail). It does accept a blank it used to reject, so waiting for Jack is right.
- **Builds:** `build.sh` and `build-app.sh` reproduce the committed pages on the head.

Worktree removed.
