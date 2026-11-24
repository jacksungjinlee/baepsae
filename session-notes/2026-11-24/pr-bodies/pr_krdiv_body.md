## What changed
- **From the Track 2 audit (11-23), findings 3.1 and 3.4.** Some Korean companies' DART dividend tables contradict themselves, and we published a wrong answer.
- **(A) Up to 17 Korean companies that paid a dividend this year were shown as paying nothing.** Examples: 현대코퍼레이션, 한텍, 앱코, 동일산업.
  - Their table gives a cash total (현대코퍼레이션 84.08억원) but leaves the common per-share cell as "-". We read that as 0.
  - 2.0's 배당 tab said "배당을 주지 않았어요 / 배당수익률 0.0%", and they ranked last on 배당.
- **I read the raw DART tables for eight of them (10 calls) to check that line 4 is true.**
  - For example, 현대코퍼레이션's table has one common row, "- | 700 | 600", next to a total of 8,408 백만원 and a common yield of 3.10. So the per-share figure really is missing from the filing; our parser is not skipping a row.
- **Now:** a year with per-share "-" next to a total above 0 is "unknown" (blank), unless the preferred shares explain the whole total (±15%, using the real preferred share counts). We never make a figure up from the total.
  - In 2.0 these show 자료가 없어요 with the approved line 4, "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요.", and drop out of the 배당 ranking.
  - A company whose total is fully explained by its preferred shares stays "no common dividend" (티에스아이: 우선주 4,673,989주 × 505원 = 23.60억, exactly its total).
- **(B) Implausible raw figures are blanked:**
  - a per-share cell more than 1,000× off the total: 와이엔텍 filed its total, 1,809,965,900원, as the per-share figure;
  - a DART 배당수익률 more than 3× off today's per-share dividend over the 52-week range (4× when the report's year-end falls outside that window, from January until the new annual report). The old app showed 흥국 56.0% (real ≈ 5.7%), 지투파워 33.7%, 아비코전자 30.0%, 알피바이오 10.0% and more;
  - a DART 배당수익률 of 0.0 next to a year we blanked.
- **와이엔텍 in 2.0 looks the same as before:** 배당을 줘요 with its existing line 3 and its 6% 배당성향 ring.
- **Two new warning-only gate rows** name any row left over: "DART 배당 표 0원인데 총액이 있는 해 (경고만)" and "DART 주당 배당 · 배당수익률 그럴듯함 (경고만)". The record is in `divCheck.raw`.
- **The existing FAIL row "주당 배당금·배당수익률 맞음" keeps its full strength.** It counts the mismatches as they were before blanking: 21 (0.8%) on the 11-21 copy, the same as `main`.
- **Measured in one run on the 11-21 copy** (real preferred rows for 8 companies; the real run also reads preferred share reports, so these are upper bounds):
  - 18 this-year figures blanked: 17 with line 4, plus 와이엔텍 with line 3. It becomes 16 with line 4 if the run's share report shows HL D&I's 560원 went to about 9.0M preferred shares; then HL D&I stays at 0;
  - 25 companies / 41 years of "0 with a total" blanked in all, 1 per-share figure (와이엔텍, three years), 17 `dy` values;
  - 삼성전자, 현대차 and the 10 largest payers unchanged;
  - nothing from the cached DART read is fetched again.

## Choices I made
- **Unknown, never a computed figure.** Dividing the total by the share count would invent a per-share dividend the company didn't state.
- **Blanking is all-or-nothing.** The guards plan first and apply at the end, so a crash half-way changes nothing, and the record is always present when anything was blanked.
- **와이엔텍 reuses the existing `div` case (line 3).** Its record, "총액 ÷ 주당 배당이 주식 수와 다름", is literally true. 2.0 says 배당을 줘요 for a blank line-3 stock only while its cash total is above 0; otherwise it shows 자료가 없어요 with line 3.
- **No rule blanks a per-share figure just for being at or above today's price.** Both reviewers showed it could blank a correct figure with no line. Only the ×1,000-versus-total rule remains.
- **Foreign issuers (code 9…) are left exactly as before.** The app has no reason line for them, and nothing may be blanked without one. The log names them.
- **Also left exactly as before (logged by name): a company whose this-year total won't reach corp.json above 0.** That means statements not in won (`build_corp` drops `cash3`) or a total under 50만원 (rounds to 0.00억). The gate accepts line 4 only with a corp total above 0, so blanking these would send out a line the gate rejects. None on 11-21. Both use the same rounding helper, `corp_cash3_of`.
- **The `dy` check widens from 3× to 4× outside the 52-week window instead of switching off.** With today set to 2027-01-01 on the 11-21 copy, the same seven values stay blanked (흥국 56.0, 지투파워 33.7, 아비코전자 30.0, 알피바이오 10.0, 한일철강 6.0, 갤럭시아머니트리 0.05, 디와이피엔에프 0.5), and nothing is kept only by the wider band. Any value kept only by the wider band is named in the log and by the warning row.
- **케이프 (064820) stays unknown.** It filed its common figure under a row labelled 우선주: 215.85억 ÷ 700 = its common share count. Reading a mislabelled row is a parser change for a later PR.

## 「새 문구」
없음. Line 4 and line 3 are already approved and already on screen for other stocks.

## 안전 규칙 변경
- **Needs Jack's yes (category 2): two gate changes, both narrow.**
  1. **The gate accepts line 4 for one new record case, `nodps`,** and only when all of these hold:
     - the file carries the standing-rule record `ownDrop.divLine` (well formed). On the older path, `nodps` never sets a line: such a line fails, exactly as on `main`;
     - the stock's `dps` and `dps3[0]` are blank;
     - `divCheck.raw.contra` lists this year;
     - the company's cash total for this year in corp.json is above 0.
     
     The pipeline blanks a year only when all of these will hold, so the gate and the pipeline's own line check always agree. The existing line-4 cases (`nototal` 총액 없음, `nostk`, `pref0`, `nopfo`, `prefmix`) each name a missing piece that is not true for these companies. Reusing one would print a false label in the daily warning row. The gate still rejects any line with no matching record; six tests check that.
  2. **The existing row "주당 배당금·배당수익률 맞음" is stricter in one case:** if the new record is present but malformed, the row fails. That way it can never under-count. Only a pipeline bug could produce a malformed record. In every other case it counts exactly what `main` counts: a test with 30 payers reading "-" plus totals fails with the same "30 (1.2%)" as before this PR.
  
  **Without the yes:** up to 17 companies would show 자료가 없어요 with no reason line, which breaks the say-why rule. So this PR waits for the yes.
- **Added:** the two warning-only gate rows above. They never fail, including when their own check crashes.
- **Added:** test files `tests/test_kr_div_contradictions.py` and `tests/test_kr_div_blank_app.py`, and smoke scene `scene_div_blank` in `tests/smoke_v2.py` at 390 and 1280 dark. That scene is not one of the pre-publish screen checks.
- No existing test edited.

## Test evidence
- **On 6ac145a:** `python -m pytest tests/ -q` 5,093 passed, 1 skipped; `python tests/smoke_app.py` 176 / 176; `python tests/smoke_v2.py` 945 / 945; `python tests/check_text.py` 0 problems.
- The new scene fails all 9 checks on `main`'s 2.0 code and passes on this branch.
- `bash build.sh && bash build-app.sh && bash build-styleguide.sh`: `app.html` and `app-preview.html` rebuilt from `src/` (round 2 changed no `src/`; rebuilt pages unchanged).
- Real data (fresh copy of the data branch fetched 11-24 02:18 KST, still the 11-21 06:41 publish, pxDate 2026-11-20): `real_data_check.py --data` 3 / 3 · `smoke_launch.py --data` 14 / 14 · `smoke_app.py --data` 171 / 171
- **Gate on that copy, patched by this branch:**
  - "주당 배당금·배당수익률 맞음" reads "어긋남 21 (0.8%) … 비우기 전 값으로 센 21", as on `main`;
  - both new rows pass; "숨긴 배당수익률의 줄" reads 배당 자료 줄 16 · 빠진 자료 줄 24 (7 before + 17);
  - the only FAILs are the two date rows, which fail on `main` too because the copy is older than today.
- **With today set to 2027-01-01 on that copy:** the seven named `dy` values stay blanked under the 4× band; none is kept only by the wider band.
- **2.0 before → after on that copy:**
  - 011760 현대코퍼레이션: "배당을 주지 않았어요 / 배당수익률 0.0%" → 자료가 없어요 + line 4;
  - 067900 와이엔텍: unchanged;
  - 277880 티에스아이: still 배당을 주지 않았어요, which is true.
- **Dry run:** after the 11-24 morning publish (DART daily allowance). Results will be added here.

## Fresh-eyes review
Pipeline, gate and app change: two independent reviewers in round 1, then Fable alone.
- **Round 1, Opus 5.5 Extra high: one blocker, fixed.**
  - B1: the new blanking emptied the existing FAIL row "주당 배당금·배당수익률 맞음" (21 → 0), an undeclared loosening. Fixed: the row counts the mismatches as they were before blanking.
  - S1: line 3 or 4 with a blank `dps` didn't check that a total exists. Fixed for `nodps` in the gate, and for line 3 in the app.
  - S2: the "≥ today's price" rule could blank a correct figure with no line. Removed.
  - S3: the preferred-only path wasn't exercised on real data. Run with real preferred rows; counts are now upper bounds.
  - Nits fixed: foreign issuers left alone, the `dy` window.
- **Round 1, Fable 5.2 High: no blocker.**
  - S1: 와이엔텍 lost its 배당성향 ring in the real pipeline shape. Fixed: the corp fields are written first.
  - S2: line 4's truth was unverified. Checked against raw DART tables.
  - S3: `nodps` was too wide. Narrowed.
  - S4: `dy` 0.0 stayed on blanked stocks. Blanked.
  - Nits fixed: a test name, a missing gate test, the RUNBOOK on lost earlier bars, the mid-loop crash.
- **Round 2, Fable alone (on 2e227a4): no blocker; four should-fix and five nits, all fixed in 6ac145a.**
  - S1: the gate's corp-total condition could reject a line the run never blanked (statements not in won; a total under 50만원). Fixed: the run leaves such stocks as before, named in the log. Tests show nothing is blanked and the gate agrees.
  - S2: a file without `ownDrop.divLine` let `nodps` set a line. Fixed: on that path it fails, as on `main` (test: 011760 with 700원, no record, no total → FAIL).
  - S3: the `dy` check switched off from January to the new annual report. Fixed: the band widens to 4×; names are given for anything kept only by the wider band.
  - S4: the "blanked without a line" log count was the literal 0. Fixed: counted after the lines are attached.
  - Nits fixed: `pre` stores `dps`; log lines and the record are built before anything changes; a blanked per-share cell with `dy` 0 blanks `dy`; one set of counts everywhere; a gate test using the pipeline's own output.
- The rounds stop here: round 2 had no blocker.

## After merge
- **The next publish runs this code.** I'll check:
  - the two new gate rows, the odd-row count and the log counts (blanked, `prefOnly`, foreign);
  - 현대코퍼레이션 (011760) in 2.0 shows 자료가 없어요 with the line;
  - 와이엔텍 (067900) shows 배당을 줘요 with its ring.
- **For Jack:** open 현대코퍼레이션 → 배당 on your phone after the next publish.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
