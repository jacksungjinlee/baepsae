Opus r1 #188 (15856bf730): 1 blockers, 3 should-fix, 4 nits

**Blocker**
B1. The head is red. `tests/test_us_split_rescale.py` has 14 failures. #176's SNDK fixtures carry no company totals, so the check blanks PER and PBR as nocompare-own (`KeyError: 'pbr'` at :547). The fix must add totals to the fixtures without weakening #176's assertions, and list that fixture edit under 안전 규칙 변경. In production the cached copies do carry totals (US_INFO_KEYS), so this is not a live over-blank.

**Should-fix**
S1. The foreign bands (fetch_data.py:12521) blank correct US numbers, and the PR doesn't disclose it. Live Yahoo:
- NVDA's PBR is off by 1.39×, over the 1.35 band. ROE on average equity runs ahead of today's book.
- #176's own calibration (validate_data.py:2535) puts only 95% of correctly priced US companies within 1.40×.
- The yield is a forward rate checked against dividends paid, so a raise of 10% or more trips it. NVDA's rate is 1.0 against 0.52 paid. A CTAS split after its 08-14 raise would give 1.11×.
- Up-C structures fail all three checks. IBKR's PER is 29.2 against market cap ÷ net income of 110.7.
- FOX is likely about 1.34× off, inferred from its cap against FOXA's.

These would be blanked under co.fgnCut, a line that isn't quite true after a dividend raise. Today only SNDK is affected, and blanking is the safe direction. Disclose these cases under Choices and ask Jack about tying the bands to split size (√ratio with a 1.5 floor, as #176 does).

S2. The PR text and docs are stale after the merge.
- HANDOFF § 0 and the PR body still call #176 "open" and "still needed".
- The Test evidence (5074 passed) predates the merge.
- The pre-merge `dry_run` sits under "After merge". Run it with `dart=off` or `dart=cache`, because an empty-cache branch run counts as the day's one full-DART run.

S3. The reported latent issue is real (fetch_data.py:12573). A foreign-set company whose cached info lacks financialCurrency writes "None" into usForeign.cut. The FAIL row "글자에 nan·None·null·undefined 없음" scans all of data.json, so that stops the publish. It can't fire today (0 of 76 set members lack a currency). Fix it in a follow-up the way `_split_why` does.

**Nits**
N1. A norecord yield gets the co.fgnCut line, which isn't literal. Inherited.
N2. The old app shows "– / 6.4" with no reason. Inherited.
N3. Housekeeping:
- There are two different "recent split" windows in validate_data.py.
- `us_splits` reads the split column twice.
- The call at :13604 is unwrapped, so a crash in `us_split_stopped` aborts fetch_us. Same pattern as the foreign check.
N4. A stale EPS that outlasts 30 days comes back with no mark. ETF PBRs are live and wrong, outside this scope (SOXX 0.37 with 가치 점수 100, TLT 0.55); tell Jack.

**Sound**
- **SNDK:** PE 0.095 against 5.14 means PER is blanked. PBR at 1.30× and the 0 yield stay.
- **Same code as the foreign check:** same function, bands and switch.
- **#176 interplay:**
  - The check reads the cache entry actually used, after #176's swap to the pre-split copy, and compares within one Yahoo snapshot, so scale doesn't matter.
  - Pre-split copy × factor passes, which is correct. A stale fresh copy is blanked.
  - Yahoo's dividends are split-adjusted (verified on CTAS and APH).
  - `us_own_restore` keeps marks.
- **Window:** usPxDate − 30 to today, from the same sources as the published splits.
- **Dual-class:** GOOGL (1.001×) and BF-B (1.014×) agree. BRK-B's PBR is never published. Preferred shares are removed earlier.
- **Gate:**
  - The new row is warn-only on every path.
  - The foreign row is unchanged and still fails `fgnCut` on SNDK.
  - The record's text has no None or nan.
  - `us_meta_drop` is reached on every drop path.
- **2.0 shows the line** in 가치, 가치 자세히, 한눈에, 배당, 비교, 관심 종목 and 내 기준. No other direct `fgnCut` reads remain.
- **Ranking:** 가치 lists and vz use PBR, so a blanked PER never ranks. Medians and the old app's weighted PER skip blanks.
- **Tests and builds:**
  - 299 pass in the brief's set.
  - The new file passes 29/29.
  - No existing test was edited.
  - Both builds reproduce the committed outputs.
