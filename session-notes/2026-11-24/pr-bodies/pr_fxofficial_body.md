**Today's dollar rate is the official close of the date shown with it** (Track 2 audit 3.8, minor). Pipeline and gate (one new warning-only row; the existing 10% rate row compares the two sources again); no app code, no wording, no screen change.

### What changed
- `data.json` `fx` (today's won-per-dollar rate) is now the last row of the exchange-rate history (`macro.json` `fxHist`, the ECOS Seoul 15:30 close), and `fxDate` is that row's date. Before, `fx` was Yahoo's USD/KRW bar. At the 06:40 publish that bar hasn't finished yet, but it was shown under a past date: 11-21 showed 1,345.7 under 11-20 (that day's close was 1,336.2, 0.7% apart), and 11-24 showed 1,340.7 under 11-23 (close 1,345.9, 0.39% apart).
- Everything that turns dollars into won uses this rate: US market values and 거래대금 in won, every "약 …원" under a $ price, 내 수익, 연말, the 원/달러 tile and new US records dated today. "Today's rate" and a past date's rate now come from one source and agree on the same date.
- On the 11-24 file (pxDate 2026-11-23): fx 1,340.7 → **1,345.9**, still dated 2026-11-23. Apple (AAPL, $349.08): "약 468,000원" → "약 469,800원". A holding of 10 AAPL: 4,680,116원 → 4,698,268원 (+18,152원). AAPL market value 6,910.7조원 → 6,937.5조원.
- How it works: the US step builds the exchange-rate history first. Yahoo's value is still the cross-check (within 10%, as before). The step takes the rate from the history's last row, then prices US stocks in won. The macro.json step later builds the same history from the same ECOS answer, because ECOS is asked once per run (failures included), so the two always agree.
- If the history wasn't read this run, or its last close is stale, Yahoo's rate is used as before, but the run says so. That covers four cases: ECOS down and yesterday's history kept, no history, a stale last row, or the step crashing. Stale uses the gate's holiday table: more than one Korean business day before the day the table expects (11-24's publish expects 11-23 and accepts 11-20, the late-ECOS morning; a row from 11-19 or earlier falls back). Outside the table's years it is 14 days. A new `data.json` `fxSrc` names the source and the reason, and the log gets a `!! 환율(data.json fx)` line. A Yahoo bar that hasn't finished is dated the run's own Korean date, never shown as a past close.
- New gate row **환율 출처 (fx · 경고만)** (warning only). It passes when `fx` equals the history's row for `fxDate`. It warns and names the source otherwise, and also on a gap of more than 2% to Yahoo's value, an unfinished value, or a stale ECOS date. On the live 11-24 file it warns ("fx 1,340.7 ≠ fxHist 2026-11-23 줄 1,345.9 (-0.39%) — 출처 표시 없음 (fxSrc)"). On the same file with this PR's rate it passes.
- The existing gate row **환율 이력 (fxHist)** keeps its 10% check between the history's last value and the day's rate. When `fx` is that last value, it now also checks it against Yahoo's value from the same run, so the two sources are compared as before.
- `fxSrc.yahoo` always records Yahoo's bar (date, value, finished or not) for comparison. The run log line is `!!` when ECOS and Yahoo differ by more than 2% (normal days: median 0.25%, 99% 1.44%).

### Choices I made
- **Which date `fx` describes: the latest ECOS close the run has, which is `fxHist`'s last row.** Normally that's the Korean business day before the 06:40 publish, the same day as `usPxDate` (11-23 on 11-24). On the ~5% of mornings when ECOS hasn't posted yet, it's one business day earlier. The date line already approved for this ("원화는 {md} 환율 {fx}원으로 바꾼 값이에요.") then shows that date. A late manual run can take that day's own close. Why this date:
  - it's a final, official close with one date;
  - it's the exact row the app already uses for a record of that date, so the two rates agree;
  - the date on screen describes the number.
  Two alternatives I rejected: Yahoo's bar with a new label (unfinished, and dated in London time), and "the close of `usPxDate`" (there's no row on a Korean holiday or before ECOS posts, so it would need the fallback anyway).
- **Only a history read this run counts.** A history kept from an earlier publish isn't used for today's rate, even though its rows are still right for their dates. That way an ECOS outage can't freeze today's rate: Yahoo is used and the run says so. One exception counts as fresh: a same-day re-run whose ECOS read fails keeps that day's earlier history (`fxHistFresh` = today). That's harmless: its rows are the real closes read from ECOS that morning (tested).
- **When a fresh history is too old (review round 1, both reviewers):** the bar is the gate's own holiday-table helper, `validate_data.fx_close_floor`, built on `_ecos_tail_min` and imported like the other gate names. A last row more than one Korean business day before the expected day falls back to Yahoo with `why` "old" and a `!!` line, and the new row warns. One day of slack keeps the ~5% of mornings when ECOS hasn't posted yesterday's close. The 14-day limit (`FX_HIST_ECOS_TAIL`) applies only where the table doesn't cover the date (it covers 2026–2027).
- **Korean holidays (no code change, review round 1):** the Seoul market is closed and ECOS has no row, so today's rate stays at the last Seoul close, with its date shown on screen. 추석 2025 moved 1,400.0 → 1,421.0 (1.5% over 8 days); 설 2025 moved 1.5% over 7 days; the largest 4-day gap since 2016 was 1.8%. That's larger than the 0.4–0.7% mislabel this PR fixes, but the date says which day's rate it is. The first publish after a long holiday takes the whole move, well inside the existing 5% `환율 변화` fail row.
- **The date on the Yahoo fallback.** A finished bar keeps its own date, as before. An unfinished bar (before London midnight, 08:00/09:00 KST) gets the run's Korean date, the day it was read.
- **Same rule for every history source.** The switch stays `ecos_close`. Under `yahoo_next`, `fx` would be that history's last row, which can be unfinished (`final` false) and is dated as that source already dates it: the gate's `yahoo_next` rule requires `fxDate` = the last row. This can't happen without changing Jack's switch.
- **Records dated today** still take `data.json` `fx` (`records.rateFor`, unchanged). On 11-24 that's now 11-23's close instead of Yahoo's 06:40 value: the same number the history holds for that date. The app is unchanged. 내 수익's rate split and 연말 value open holdings at the same `fx`.
- **ECOS is asked once per run** (`ecos_fx_series_once`). Failures are remembered too, so the two history builds can't disagree, and ECOS still gets one attempt per run as before (`ecos_get` tries 3 times). The second build reuses the answer and the log says so. main's line `macro.update(ph.run("환율 이력", fx_hist_fields, fx, fx_last, today, prev_macro))` is unchanged (an existing test pins it); the previous `macro.json` is now read before the US step (nothing writes it before then). Under `yahoo_next` the second build downloads again (not reachable today).
- **Still on Yahoo's 3-year series:** US `vol` in won, the S&P 500 in won, the won gold and silver monthly series, and the KRX-gold fallback. These are histories, not the day's rate, and are out of scope.
- **Where the shared names live:** the fallback reason codes (`noHist` · `kept` · `old` · `err`), the name `yahoo`, the 2% line and the staleness helper live in `validate_data.py` (`FX_SRC_WHY`, `FX_SRC_YAHOO`, `FX_SRC_GAP`, `fx_close_floor`), and the pipeline imports them, so both use the same words and dates.
- **데이터 출처 still names FinanceDataReader for 환율; the fix needs new wording from Jack (follow-up).** (`src/info.jsx` 103–106, also opened from 2.0's ☰; no Korean text changed here.)
- **A stale comment fixed:** `src/v2/weekly.js` called `data.json` fx "Yahoo's rate". Built pages are byte-identical (comments are minified away).
- **Interaction with #191 (US trade dates), if both merge:** #191 saves a US trade dated New York's today, before the history has it, with `data.json` `fx`. After this PR that is the latest Seoul close (11-23's on 11-24), not Yahoo's morning bar. Both PRs keep "a record keeps the rate of its own date, or the last close before it".

### 「새 문구」
없음. No new or changed user-facing Korean text. The approved `co.fxWon` / `co.usWon` lines show the new rate and date.

### 안전 규칙 변경
- **Existing row `환율 이력 (fxHist)`: same strength; it compares the two sources again.** Its FAIL "마지막 값 … 10% 넘게 달라요" compared the history's last value with `data.json` `fx`. Before this PR, `fx` was Yahoo's, so that was an ECOS-vs-Yahoo check. With `fx` now the history's own last value, it became a self-comparison that could never fail. Both reviewers caught this; the PR's first version said "no existing gate row changed", which was wrong.
  - Now the row still checks `fx` exactly as before. When `fxSrc.src` isn't `yahoo`, it also applies the same 10% to `fxSrc.yahoo.fx`, the Yahoo value of the same run.
  - Files without `fxSrc` (every publish so far) are judged exactly as on `main`. So are files whose source is Yahoo and files whose Yahoo value can't be read.
  - The threshold is unchanged. It rejects everything `main` rejects. The only new rejection is an ECOS row more than 10% from that run's Yahoo value, which is what the row caught before this PR.
  - The reviewer's probe (last row 4% above the day before, Yahoo 12% away) PASSED on this PR's first version and FAILs again, in publish and live mode, as it does on `main`.
  - The threshold text and the code comment (`FX_HIST_REL`) and the RUNBOOK sentence say so.
- **Added one gate row, warning only in every mode (including when it crashes):** `환율 출처 (fx · 경고만)` (`validate_data.check_fx_src`). It can never fail the publish, so it isn't category 2. It warns when:
  - `fx` ≠ the `fxHist` row of `fxDate`, compared to one decimal;
  - there is no row for that date;
  - the source is Yahoo, or `fxSrc` is missing;
  - `fx` is more than 2% from `fxSrc.yahoo.fx`;
  - the value is unfinished (`fxSrc.final` false, the `yahoo_next` case);
  - an ECOS close's date is stale by `fx_close_floor`.
  It also warns on today's live file until the first publish after merge.
- Constants added to `validate_data.py`: `FX_SRC_YAHOO`, `FX_SRC_WHY`, `FX_SRC_ROW`, `FX_SRC_TOL`, `FX_SRC_GAP`; helpers `fx_close_floor`, `fx_src_yahoo`. No other gate row or threshold changed.
- **Tests only added:** `tests/test_fx_official.py` (70 tests). No existing test edited.

### Test evidence
- `bash build.sh && bash build-app.sh`: both succeed; `baepsae.html`, `app.html` and `app-preview.html` are byte-identical to `main` (sha256 checked).
- `python -m pytest tests/ -q -p no:cacheprovider` on the head (600b003): **5507 passed, 1 skipped**.
- `python tests/check_text.py`: 글자 점검: 페이지 4개 · JSON 87개 · 문제 0개.
- `tests/test_fx_official.py`, 70 tests:
  - the 11-21 and 11-24 publishes give 1,336.2 / 2026-11-20 and 1,345.9 / 2026-11-23;
  - ECOS one day behind gives the earlier close and its date;
  - a late run takes that day's close;
  - every source switch value is covered;
  - with no history, a kept history or a broken history, the run falls back to Yahoo with the reason. An unfinished bar is dated the run's day, a finished bar keeps its date, and the London-midnight edge is tested to the second (winter and summer);
  - staleness by the holiday table: 11-23 and 11-20 used on 11-24, while 11-19 and the reviewer's 13-day-old 11-11 fall back with `why` old and a `!!` line;
  - `ecos_next` is one business day further back;
  - 추석 2026 keeps the 9-23 close with its date;
  - outside the table (2025), the 14-day limit tested to the day;
  - the same-day re-run with a kept history counts as fresh, while yesterday's kept history doesn't;
  - the `!!` line when ECOS and Yahoo differ by more than 2%;
  - no NaN or gate word in `fxSrc`;
  - the loud log lines;
  - the US step and main build identical histories with one ECOS request, and a failed read is not retried;
  - `fetch_us` prices US market values at the official close and passes Yahoo's value to the cross-check;
  - main's wiring;
  - the gate row: PASS, each WARN (2% gap, unfinished value, stale ECOS date, 1,336.25 vs 1,336.2 now equal), never FAIL, a crash becomes a WARN, and the full gate on the fixture pair;
  - the 환율 이력 (fxHist) row: the reviewer's probe FAILs in publish and live mode; 9%, 0.4% and −5% from Yahoo PASS; 11% FAILs; old-shape files pass and fail as before, with the old message; `fx` 15% from the row still FAILs; a Yahoo source or an unreadable Yahoo value falls back to the `fx` check only;
  - the err path's `fxSrc.yahoo` has the same shape (`d` · `fx` · `final`).
- Real data (data branch copy, pxDate 2026-11-23, asOf 2026-11-24, published 2026-11-24 06:40:59 KST), on the head (600b003):
  - real_data_check.py --data 3 / 3
  - smoke_launch.py --data 14 / 14
  - smoke_app.py --data 171 / 171

  An earlier run of the last check, on the busy shared machine, had one scene time out on a click (30 s): the old app's "영어 화면에서 깨진 저장본". That scene passed on the re-run above, and the built pages are byte-identical to `main`.
- Gate on that copy, live mode (`validate_data.py --dir … --live`), on the head (600b003): **PASS · 실패 0 · 경고 16 · 전체 168**. The new row warns: "fx 1,340.7 ≠ fxHist 2026-11-23 줄 1,345.9 (-0.39%) — 출처 표시 없음 (fxSrc)". 환율 이력 (fxHist) passes; the file has no `fxSrc`, so it is judged exactly as on `main`.
- The same copy with this PR's rate (`fx_official` on its own `fxHist` and Yahoo value; `fx` 1,345.9, `fxSrc` ecos_close, US `cap` / `val` scaled by 1,345.9 ÷ 1,340.7): **PASS · 실패 0 · 경고 15 · 전체 168**. The new row passes: "fx 1,345.9 = fxHist 2026-11-23 줄 · 출처 ecos_close" (Yahoo 1,340.7 is 0.39% away). The 환율 이력 (fxHist) row passes with "fx 1,345.9" and now also checks 1,345.9 against Yahoo's 1,340.7.
- Pipeline PR: a `dry_run` on this branch is **queued (dry runs run one at a time); result here before merge**.

### Fresh-eyes review
Pipeline PR: two independent reviewers in round 1 (Opus 5.5 Extra high and Fable 5.2 High), then Fable alone.

**Round 1.** Opus found 1 blocker (B1), 2 should-fix (S1, S2) and nits. Fable found no blocker, 3 should-fix (S1–S3) and nits. Fixed in 600b003:
- **B1 (Opus) / S2 (Fable): the 10% check in `환율 이력 (fxHist)` had become a self-comparison.** It now compares the two sources again, at the same strength (above, 안전 규칙 변경). The new row also warns on a gap over 2% to Yahoo, and the log line is `!!`.
- **S1 (both): a fresh but stale ECOS history was used as today's rate** (the probe: 11-11 used on 11-24). Staleness now follows the gate's holiday table (`fx_close_floor`, at most one Korean business day behind the expected day). Beyond that the run falls back to Yahoo with `why` old and a `!!` line, and the new row warns.
- **S3 (Fable): Korean holidays freeze the rate.** No code change, by design; disclosed under Choices and After merge.
- **S2 (Opus): 데이터 출처 names FinanceDataReader for 환율.** It needs new wording from Jack, so it's a follow-up, noted under Choices.
- **Nits:** the new row warns on an unfinished value (`final` false); the err path's `fxSrc.yahoo` has a `final` key; the one-decimal comparison fixes the 1,336.25 float edge; the same-day re-run with a kept history is tested and explained under Choices.

**Round 2** (Fable alone): pending.

### After merge
- Watch the next daily run. In its log, expect:
  - `· 환율(data.json fx): 1,3xx.x — 2026-11-2x 공식 종가 (환율 이력 ecos_close 의 마지막 줄) · 야후 … 과 ±0.xx%`;
  - in the macro step, `· ECOS 환율 시계열 731Y003/0000003: 이 실행에서 앞서 읽은 것을 그대로 써요 (새 요청 없음 · …줄)`;
  - the gate row `환율 출처 (fx · 경고만)` reading PASS.
- In the published files, check that `data.json` `fx` equals `macro.json` `fxHist`'s last row and that `fxDate` equals `fxHist.asOf`.
- Live site: open Apple (AAPL). "약 …원 · 환율 …원" should use the close above, and the 원/달러 tile's date should be that close's date. Then the usual 005930 / 현대차 check.
- For Jack's phone: nothing to do. US stocks' won amounts move by the gap between Yahoo's morning rate and the Seoul close (normal days: median 0.25%, 99% 1.44%). On a Korean holiday the rate stays at the last Seoul close, with its date shown, so it can lag by more (추석 2025: 1.5% over 8 days; the largest 4-day gap since 2016 was 1.8%).
- If a run's log shows `!! 환율(data.json fx)`, the rate fell back to Yahoo or differs from Yahoo by more than 2%, and the 환율 출처 row warns. Look at `data.json` `fxSrc`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
