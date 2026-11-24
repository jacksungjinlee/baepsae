Fable r1 #188 (15856bf): 0 blockers, 3 should-fix, 3 nits

Today's effect is right: with Yahoo's figures now, SNDK's PER is cut (0.095 ↔ cap ÷ NI 5.14, 54.14×), its PBR (1.30×) and 0% yield stay, and the line is true. Nothing below blocks the SNDK fix.

**Should-fix**

1. **The foreign bands blank correct numbers on ordinary US companies** (`fetch_data.py:12911`, bands `:12521`). It fails safe (blank plus line); the PR names only the missed-dividend risk.
   - **Yield:** APH (real 2:1 split, 2026-09-03). The check returns `배당수익률 0.77% ↔ 지난 350일 배당 0.5000달러 ÷ 종가 77.41 = 0.65% (1.19배)`. 0.77% is the right forward yield (dividend raised 0.125 → 0.15). Of 473 US payers, 60 (13%) have forward and trailing rates over 10% apart (Yahoo quote).
   - **PBR:** NVDA 14.92 = price ÷ book 11.06, correct, yet 1.39× → blank, and the 가치 score with it. In the live file 41 of 557 comparable US companies (7.4%) are beyond 1.35× (MU, APP, FTNT, CVNA, VST, HON). SNDK is at 1.30×; #176's RUNBOOK says it was 1.42× before its split.
   - **Can't compare:** 80 of 637 US PBRs (12.6%) have no PER or ROE, so any split blanks PBR for 30 days (the `fgnNoCmp` line is true).
   - **Fix:** say so in the PR and RUNBOOK, or narrow it (PER only; PBR and yield only on a large gap).
2. **Window edge** (`fetch_data.py:12853`, `validate_data.py:5052`). SNDK leaves `recent` at usPxDate 2026-12-21 (`us_recent_splits` returns `{}`; I ran it). If Yahoo's EPS is still 923.7, PER 0.1 publishes again with no line; only #176's warning row names it. Fix: keep checking a stock whose previous publish carries `splCut` until it agrees (`prev` is already passed in), or a tracked follow-up before 12-18.
3. **PR body is stale after merging main.** "5074 passed" and "no existing test changed" will not hold once #176's fixtures are edited; name those tests under 안전 규칙 변경. The real-data and smoke evidence predates 15856bf.

**Nits**

- `_split_why` (`fetch_data.py:12881`) replaces only `None`. `financialCurrency=float("nan")` gives "…nan…" in `usSplitChk.cut`, which trips the FAIL row `글자에 nan·None·null·undefined 없음` (reproduced). Not reachable from Yahoo's JSON.
- "Pre-split EPS 923.7" (PR, `fetch_data.py:12840`, RUNBOOK:1964) is wrong. NI 19.42B ÷ 1.138B shares = 17.06, so pre-split is about 136 (PER 0.64). 923.7 is 54× off, not 8×: don't later narrow the check to "about the split ratio".
- Kinds `currency` and `norecord` show `co.fgnCut` ("…맞지 않아서"), though nothing was compared. Approved for foreign companies; now reachable for a US one (FISV has no currency today).

**Latent foreign issue: real, not today.** A foreign-set company with no `financialCurrency` writes "…financialCurrency None…" into `usForeign.cut` (`fetch_data.py:12573`), and the same FAIL row stops the publish (reproduced). The live file has none: FISV, the only currency-unknown company, isn't in the foreign set. A new foreign ticker whose first response lacks the currency would trigger it. Separate PR.

**Sound**

- **Thresholds:** the foreign check's own (same `us_foreign_cuts`, bands, kinds, switch).
- **#176:** order is rescale → foreign check → split check. The check compares inside the raw cache entry `apply_us_info` used, so a copy × factor is consistent and never cut twice.
- **Gate:** every `rep.add` of the new row has ok=True, crash included. The foreign row's diff is additions only; `fgnCut` outside the set still fails. No US FAIL row needs PER, PBR or yield.
- **App:** every reader goes through `fgnCutOf` / `fgnKindOf`. 2.0 shows US PER only in 가치 and 가치 자세히, both with the line. Blanks are null in ranks, watch, compare and the industry median; `vz` is ranked after the check.
- **Tests:** the brief's set, 299 passed; the diff adds one test file and edits none.

Yahoo requests: 12. Raw answers: `/tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/rv188_fable_work/`.
