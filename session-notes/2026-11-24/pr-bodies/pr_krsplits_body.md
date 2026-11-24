## What changed

- **Korean stock splits now reach 2.0's records.** `data.json` `splits` gets Korean 액면분할 rows in the same shape and meaning as the US rows (`[code, date, ratio]`; a 10:1 split = 10). The app reads them with no code change: a Korean holding bought before a split counts at the new number of shares (quantity × ratio, price ÷ ratio, the same 원 amount), and the 기록 sheet shows the approved Appendix 1 line ("…주식 1주가 50주로 나뉘었어요…").
- **Every Korean row needs two sources that agree.** The KRX prices (that day the listed share count moved by exactly the ratio, or the base price was reset to the previous close ÷ the ratio with matching shares) and the company's DART decision (주식분할결정 / 주식병합결정 document: ratio from the par values and the listing date; or a 감자결정 that merges shares, read as each holder's ratio). DART's exact ratio must fit the market's raw numbers and its listing date must be the market's day. Anything else is left out with a short code, e.g. 삼성바이오로직스's 2025-11-24 company split (prices moved, no split decision).
- **The date is the first trading day on the new share count** (신주권상장예정일), not the board date or the legal effective date. On the 49 split/merge filings DART had already given us, 48 match a market event listed 1–32 days after the legal date (merges about 3 weeks); the 49th disagrees and is left out.
- **Merges and 5:2-type splits wait for Jack.** They leave holders a fraction of a share that the company pays in cash, and 2.0 has no approved line for that yet. They are checked and named but not published (`KR_SPLIT_FRACTION_ROWS_ON = False`). Whole splits (×2, ×5, ×10, ×50 …) publish now.
- **History since 2016, newest first.** A one-time seed (`data/kr_splits_seed.csv`, 592 market candidates from Daum's unadjusted daily prices) plus the daily KRX lists, and Daum's daily prices for days without a KRX list. DART checks at most 50 calls a run: today's and last-30-days events first, then the seed by market cap (the backfill takes about 26 DART-on runs). Candidates not asked yet are carried in the file, so a new event is never lost.
- **삼성전자 and 삼성전자우's 2018 50:1 split** are hand-checked rows (DART no longer serves that corrected document), with the evidence written next to them.
- **Nothing published is ever dropped, and nothing here can stop a run.** If DART is down, off, or this step fails, last publish's Korean rows are kept and the log says so. US rows and rules are unchanged (a test compares them value for value). `data.json` gets short codes only, never DART's or Python's text.
- **New warning-only gate row** `한국 주식 분할 (splitsKr · 경고만)`: yellow only on a new problem (a failed lookup, a new disagreement, a recent event left out); it passes while the backfill simply waits. The two existing split rows treat Korean rows exactly as strictly as US rows. Docs: RUNBOOK § Korean stock splits, HANDOFF § 0, CHANGELOG.

## Choices I made

- **Which DART data:** there is no structured API for 액면분할 · 주식병합, so the run reads the decision document (the same fixed KRX form the dividend check reads) and, for a 감자 by merging shares, `crDecsn.json` with the ratio taken from its method text ("10주를 … 1주로"), which must be one ratio equal to the 감자비율; 차등 · 최대주주 · 소각 texts are refused. Checked by hand on 6 filings (Kakao 2021, NAVER 2018, BYC 2024, 시큐브 2025 merge, 알파칩스 2025 감자, Samsung 2018).
- **No list-only confirmation** (review round 1, my decision under the rules): a decision whose document DART does not serve (status 014) never confirms a row; it is left out with code `gone`. 800, 900 and other statuses are retried next run. Samsung 2018 went into a Korean override table, `KR_SPLIT_OVERRIDES`, not `SPLIT_OVERRIDES`: `tests/test_v196a_fxhist_splits.py::test_override_table_pins` pins that table and this PR edits no existing test. `KR_SPLIT_OVERRIDES` only adds rows; removing a Korean row would still go through `SPLIT_OVERRIDES` (and that pin).
- **Market rule:** an exact share ratio (n:1 or 1:n within 1%) wins over the price; a split must also have its base price at the previous close ÷ n (so a 무상증자 listing day is not one); a merge may not (KRX sets that base by auction). Otherwise the closest clean fraction to close ÷ base within 1%, with shares within 10%. The cache tag moved to v2, so verdicts under the first rule are asked again.
- **Order:** new candidates (KRX lists, Daum, carried) and events of the last 30 days first, then the seed by market cap. Daum stops after 3 failures in a row or 120 seconds and carries the rest to the next run.
- **Fraction rows held** behind `KR_SPLIT_FRACTION_ROWS_ON = False` (my decision under the rules) until Jack approves their line.
- **DART budget:** 50 new calls a run, in `dart=cache` runs only (not a full-DART run, not an empty cache, not a same-price-date rerun that skips DART).
- **No FAIL gate row** (a new publish-stopping row is Jack's call); proposed below.

## 「새 문구」

없음 — no new or changed user-facing Korean string. (Log lines, the data field description and the gate row text are for us, not users. The draft line for Jack below is not built.)

## 안전 규칙 변경

- New gate row `한국 주식 분할 (splitsKr · 경고만)` in `validate_data.py`: warning only, cannot fail the publish (an added check; no yes needed). Listed here as the rules ask.
- New test file `tests/test_kr_splits.py` (added only, 68 tests). No existing test, threshold, must-have list or gate row was edited; `SPLIT_OVERRIDES` is unchanged.
- The existing rows `주식 분할 목록 (splits)` and `주식 분할 목록 변화 (직전 발행본과)` are unchanged; they now also check Korean rows (shape, clean ratio, a new row's stock must be in today's list, a row may never disappear or change ratio). Tests confirm a bad Korean row still fails.
- Proposed, not built (category 2, Jack decides): a FAIL when a Korean row in `splits` has no receipt in `splitsKr.rows`; and Korean must-have splits once confirmed (삼성전자 2018-05-04 ×50, NAVER 2018-10-12 ×5, 카카오 2021-04-15 ×5).

## Test evidence

- `bash build.sh`, `bash build-app.sh`: OK; built pages unchanged (no `src/` change).
- `pytest tests/`: 5095 passed, 1 skipped
- `pytest tests/test_kr_splits.py`: 68 passed — a real event end to end (카카오 2021-04-15 ×5 from real Daum rows and the real DART document); the date choice (BYC legal 04-12 → listed 04-17; 시큐브 merge 04-29 → 05-20; a candidate on the legal date is refused); 감자 read as the holder's ratio and 차등 · 소각 · inconsistent 감자비율 refused; one-source and disagreeing events left out by code; 014 never confirms and 800 · 900 · 013 are retried, not cached; free text never reaches data.json and the whole gate passes on such values; lists capped at 30; DART failure and errors keep last publish's rows and carried candidates; new events asked before a big backlog and carried to the next run; Daum stops after 3 failures or 120 s; the fraction switch pinned off; post-seed held and recent "no" candidates kept (round 2); KONEX off Daum; US rows bit-identical; 2.0 reading a Korean purchase from before Samsung's 50:1 split, held and partly sold (Node, `src/v2` as is); the gate rows.
- `python tests/smoke_app.py`: 176 / 176 통과
- `python tests/smoke_v2.py`: 939 / 939 통과
- `python tests/check_text.py`: 글자 점검: 페이지 4개 · JSON 88개 · 문제 0개
- Real data (data branch copy, pxDate 2026-11-23, published 2026-11-24 06:40, outside the checkout): `real_data_check.py --data` 3 / 3 · `smoke_launch.py --data` 14 / 14 · `smoke_app.py --data` 171 / 171
- Simulation on that file (DART answers stubbed; the 48 events DART had already confirmed through `dvWhy` cached as verdicts): 20 whole-split rows publish (18 + Samsung's two override rows), 32 fraction rows held, gate: both existing split rows PASS, the new row WARN only for the stub's failed lookups.
- Main merged in after #176 and #184 (1de8a4b; CHANGELOG, HANDOFF and RUNBOOK conflicts resolved by keeping both sides; builds unchanged).
- Main merged in again after #182 (ca929ea; CHANGELOG and HANDOFF kept both sides; built pages unchanged). After it: `pytest tests/test_kr_splits.py tests/test_kr_px_repair.py tests/test_us_split_rescale.py tests/test_v196a_fxhist_splits.py tests/test_v2_split_round.py tests/test_validate*.py`: 603 passed. CI runs the full suite on the head. #182 touches only the Korean price-history step and its own gate row, not the split rows, so the dry run above (on 1de8a4b) still stands.
- Pipeline dry run on this branch (1de8a4b, `dart=cache`): run 45311868591, **green**, 21 min. Gate: **PASS · 실패 0 · 경고 17 · 전체 193**.
  - New row `한국 주식 분할 (splitsKr · 경고만)`: "2건 (새로 2 · 지난 발행본 0) · 싣지 않음 0 · 묻지 못함 586 · 조회 실패 0 · DART 새 호출 0/50 · 출처 cache · 오늘 새 한국 줄 2: 005930 2018-05-04 ×50, 005935 2018-05-04 ×50 · 확인 기다림 586 (실행당 DART 한도)". It warns only because two rows are new (Samsung's 50:1 split, from the fixed table).
  - Log: `· 한국 주식 분할 후보 (최근 19거래일 목록 파일 · 기준가 재설정 + 상장주식수): 11건` (e.g. 047400 2026-11-16 ×0.2, 027830 2026-11-10 ×0.2).
  - **Not exercised by this run: the DART lookups.** A dry run on a day already published repeats the same price date, and the pipeline rests DART on such a run by design ("같은 기준일을 다시 돌며 DART 를 쉬는 실행"), so 0 of the 50 calls were made and 586 candidates wait. The lookup code is covered by the stubbed simulation and tests above, and every failure becomes a fixed code with the text in the log (B1). To see the lookups on real DART before merge, I will run one more dry run after the Korean close is final (after 16:00 KST), when the price date is new.

## Fresh-eyes review

Round 1: two reviewers (Opus 5.5 Extra high, Fable 5.2 High), neither seeing the other.

- **B1 (Fable):** free text in `splitsKr` (`fail`, `out`, `err`) could put "None" or "nan" into data.json and fail the gate's text row on every publish, since an `out` reason was cached. **Fixed:** data.json carries fixed codes only (`nodoc` · `diff` · `gone` · `unread` · `cr` · `nocorp` · `pages` · `err`; fail `net` · `status`), text goes to the log; a cached verdict's code is mapped to a known code or `err`; lists capped at 30 rows with counts. Test runs the whole gate on such values.
- **B2 (both):** the `list` receipt could publish a wrong ratio (any non-000 document status counted as "gone", the market ratio came from a loose snap, one decision could confirm several events). **Fixed:** the list path is removed; 014 never confirms; Samsung 2018 is a hand-checked override row with evidence.
- **S (both): exact share path first.** **Fixed:** an exact n:1 / 1:n share ratio wins; the snap picks the closest fraction; DART's ratio is matched against the raw market numbers; seed recounted (HMM 2016-05-09 1:7, 131400 2026-10-07 1:10, 003060 2024-04-16 1:10, 057680 2026-04-30 1:5 now right); cache tag v2.
- **S (Opus): only 014 is final.** **Fixed:** 800, 900 and other statuses return "try again next run" and are never cached.
- **S (both): 감자 ratio is the holder's.** **Fixed:** read from the method text, one ratio, equal to the 감자비율; 차등 · 최대주주 · 소각 refused (`cr`).
- **S (both): new events behind the backfill, and lost after the KRX window.** **Fixed:** new and last-30-days events first; unasked candidates carried in `splitsKr.pend`, unread Daum look-ups in `splitsKr.dq`.
- **S (both): fractions after merges and 5:2 splits.** **Fixed:** those rows are held behind `KR_SPLIT_FRACTION_ROWS_ON = False` until Jack approves the line.
- **S (Opus): the spec asks for a structured source.** Not code: DART has none for these decisions; the run reads the fixed KRX form in the filing (as the dividend check already does). Flagged for Jack in the summary.
- **Nits, fixed:** Daum stops after 3 failures or 120 s with a loud line; tolerance comments; 48 vs 49 made consistent; RUNBOOK limits (ETFs and stocks with no DART code, I001 list paged up to 5 pages then `pages`); same-day-rerun wording; the gate row passes while the backfill waits.
- **Round 2 (Fable 5.2 High alone): no blocker; B1 and B2 confirmed fixed (400 whole-gate fuzz runs, 0 FAIL). Rounds stop: round 2 found no blocker.** Its should-fix and nits, all fixed before merge:
  - **S1:** events found after the seed (KRX lists, Daum) were forgotten after the ~19-session list window: a held merge would never publish once merges are switched on, and a `diff` / `unread` / `gone` verdict lost its 14-day re-ask after about 4 weeks. **Fixed:** such candidates stay in `splitsKr.pend` while held, or while their "no" is under 120 days old (no DART cost). Tests: a held merge from the KRX list publishes 40 days later when the switch is on; a corrected filing is asked on day 40.
  - **Nits:** KONEX is no longer sent to Daum, and a 4xx answer is not a failure (no 3-failure stop, not carried); `kr_prev_splits` is inside the try and tolerates odd receipts; carried `pend` / `dq` dates must be real dates (bad ones dropped with a log line); `KR_SPLIT_OVERRIDES` never changes the ratio of a published row (loud line instead of a gate FAIL); receipts and comments say `KR_SPLIT_OVERRIDES`; a listed 감자결정 that `crDecsn.json` does not give (013) is `unread`, not `nodoc`. Left as is: the "2,500주를" comma case (harmless).

## After merge

- Watch the next daily run: `한국 주식 분할` log lines (whole-split rows added, merges held, at most 50 DART calls), the gate row `한국 주식 분할 (splitsKr · 경고만)` passing or yellow only for a named problem, and `주식 분할 목록 변화` passing.
- Check the live site's `data.json`: Korean whole-split rows present (삼성전자 2018-05-04 ×50 first), US rows unchanged, `splitsKr` with codes only.
- Jack's phone: nothing changes unless a portfolio has a Korean record from before a split.

Questions for Jack (yes/no, in the chat):
1. After a merge a Korean holding keeps a fraction the company paid out in cash (단주 대금). On the built app (15 shares through a 10:1 merge) the row says "2주" while the value uses 1.5 (a separate PR shows "1.5주"), and 팔았어요 cannot sell the 0.5 (Korean sales are whole shares). Merges are held until you decide: add this line under the merge line, "1주가 안 되는 {x}주는 회사가 현금으로 줘요. 받은 돈은 증권 계좌에서 확인해 주세요.", and turn merges on? And may 팔았어요 accept that fraction?
2. Add the FAIL row and the Korean must-have splits proposed above?
3. The task asks for a structured DART source for splits. DART has none, so the run reads the company's own decision document (the same fixed KRX form the dividend check already reads), and a row publishes only when that document and the market's prices agree. Is reading the filing text acceptable? This PR waits for your yes on this one.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
