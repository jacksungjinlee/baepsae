# 뱁새 — Handoff to Claude Code (2026-10-30)

This document carries everything decided in ~3 months of building 뱁새 in claude.ai chat (v9 → v17.4,
2026-07-30 → 2026-08-20, then a pause). Read it once fully. `CLAUDE.md` holds the rules; this file holds the context.

---

## 0. Current state and next steps (updated 2026-11-23 KST — read this first)

**Now (2026-11-23):** merged and deployed 11-22: #166 (old-app English carry lines), #167 (div reason lines), #168 (v19.6b 오늘 볼 것
page), #169 (new US tickers wait), #170 (v19.6e data: `c1w` · `wkFrom` · `usWkFrom` · `c1wv` · `c1wSrc`), #171 (v19.6e
screens: 이번 주 정리 card, ON with Jack's lines of 11-22; first card possible from Saturday 11-28's publish), #172 (Korean
last-week closes from our own publishes, Jack 11-22). Their data effects reach the site with the first publish after them, Tuesday 11-24's morning run (none since 11-21 06:41). Expect in its
log: the `새로 들어온 미국 종목` line, the `c1w` lines and the gate rows `미국 새 종목 확인 종가 기다림` and `이번 주 시작 종가`; Monday 11-23
had a final KRX list (unless it turns out to be a backup-source day), so #172 reads no old publishes: expect `c1wSrc.pub` = 0 and the log
line `c1w 지난 발행본: 읽지 않아요 …` — a 0 there is correct, not a failure, and #172's real-data proof is its dry run below. **Ready, waiting for Jack:** v19.6b switch-on (branch `claude/v19.6b-switch-on`, 66caa3f: 공시
보기, 지분 변동 cards, `look.insBoth`; Jack said yes 11-22 to the two named test edits; #168's own "still off" checks need his yes
to flip: about 30 lines that only change expected values from off to on — `tests/test_v196b_cards.py` (insBoth title, the heading/row
count), `tests/smoke_v2.py` scene_v196b / scene_v196b_states (row order and icons with 지분 변동 rows, 5 insider cards, 4 공시 보기
links, "전무가" off the must-not-show list, labels) and a rename in `tests/test_v196b_answers.py`; nothing removed or loosened). **Open questions to Jack:** the capped footnote
`weekly.nvNoteMore` ("{names} 외 {n}종목의 지난주 종가는 다른 자료로 확인한 값이에요. 이번 주 움직임이 실제와 조금 다를 수
있어요."; until then more than 5 Naver-checked stocks are left out and named), "건" on the older chips (유상증자 {n} · 지분 변동
{n} · 실적 발표 {n}), one decimal on 지분 변동 amounts. Design chat has (sent 11-22): the say-why audit, the 10 dark-mode pairs,
the approved 유상증자 card sentences with proposals for 유무상증자 and 기타주식. **Next in the queue:** v19.3 Part L. On hold: v19.4,
v19.6g, v19.6h.

**Korean stock splits (#186, 2026-11-23/24; Jack's Track 1, spec v19.6 A.6):** `data.json` `splits` gets Korean 액면분할 · 주식병합
rows (same shape and meaning as the US rows; the app reads them unchanged), dated the first trading day on the new count
(신주권상장예정일, not the legal date). A row needs two sources: the KRX market (listed shares exactly n:1 or 1:n, or the base price
reset with matching shares; daily from the final lists, Daum for days without one, 2016 → 2026-11-20 from the committed seed
`data/kr_splits_seed.csv`, 592 candidates) and the DART decision document (ratio from the par values, listing date) or a 감자결정 by
merging shares read as the holder's ratio. A document DART does not serve never confirms (삼성전자 · 삼성전자우 2018 ×50 are hand-checked
`KR_SPLIT_OVERRIDES` rows with evidence). One-source events are left out by code (`splitsKr.out`, text in the log only). **Held for Jack:** rows that leave
a fraction of a share (merges, 5:2 splits) are confirmed but not published (`KR_SPLIT_FRACTION_ROWS_ON = False`) until he approves
their line; whole splits publish. At most 50 new DART calls a run (cache runs only): new and recent events first, then the seed by
market cap (about 26 DART-on runs); Korean rows are never dropped. New warning-only gate row `한국 주식 분할 (splitsKr · 경고만)` (yellow
only on a new problem). Open for Jack: the fraction line, a FAIL row (proposed in the PR), 무상증자 not handled. RUNBOOK
§ Korean stock splits.
**Split rounding (#184, 2026-11-24; Track 2 audit 1.1, serious but rare, and 1.4):** 47 of data.json's 150 splits have a ratio
that isn't a whole number (DD 1:3, UL 8:9, HON and AZN 1:2, AMCR 1:5, SNEX 3:2 …). Records dated before one broke when they didn't give
whole 1/10,000 shares (for 11 of the 47, one share already doesn't; for the rest, a 0.0001-share sale or a 금액으로 넣기 row):
`held.js` rounded each record on its own and `lots.js` didn't round, so the app's automatic save of the split was refused and
retried hundreds of times a second with "날짜·수량·가격을 다시 확인해 주세요" on every screen, a valid sale of the old shares was
refused, and a full sale left a sliver (a −5원 '손실' on the tax screen with nothing held). Now one count everywhere (`held.js`
`count()`, read by the ledger, the store's check, 팔고 빼기 and 금액으로 넣기 sales), position by position: a sale that takes either
the per-record count (what main showed) or the running exact total to exactly 0 closes the position, and the next record starts
from 0; an open position shows main's per-record count while it stays at or above 0; a reading that goes below 0 falls back to
the running count over the whole history, then main's. Records saved by main read as main read them. Records with no split or a whole-unit ratio count bit-identically to main (`tests/test_v2_split_round.py`, main's code
frozen in `tests/fixtures/count_before_split_round_511fd6f`). `app.jsx` stores a data.json split stock by stock, only when main's
count reads the records too, tries each once per visit and says "stored" once it is in the records. A 금액으로 넣은 holding sold
with a date before a split sells every share on that date's basis (it sold a fifth after AMCR's 1:5). **Don't plain-revert #184**
(RUNBOOK § Roll back): records only #184's count reads (a sale only it accepts, or any record saved for a stock whose earlier
records main reads only without the split, which then stores the split) set that portfolio aside on main's code until the fix
is back. No new Korean text.

**CI checks the two PR rules (#175, 2026-11-23; Jack: "Automate the rules you missed"):** the last step of `ci.yml`'s `checks`
job runs `tools/pr_rules.py`, so the required `ci` check goes red when either rule is missed. Run it yourself before pushing:
`python tools/pr_rules.py --body-file BODY.md --base $(git merge-base origin/main HEAD) --head HEAD` (CI compares
with GitHub's merge commit, which this approximates). (1) A PR that changes what the site serves (deploy's
own file list `assemble_site.site_files`, `src/`, the build inputs incl. `build-styleguide.sh` and `deploy.yml`, the `tools/` files
they call and import, e.g. `build_tag.py` and `logos/logo_index.py`, and the three real-data screen checks with the `tests/`
helpers they import) needs `real_data_check.py` (with or without `--data`; it has no other mode), `smoke_launch.py --data` and
`smoke_app.py --data` in its description, each with an all-pass `N / N` and no non-passing `N / M` in the same sentence or table
cell after any check name (HTML comments are not read), and the data's date (a real YYYY-MM-DD, today KST or up to 14 days
before) on a result line or up to 3 non-blank lines above the first one (table `|---|` lines don't count). Example line:
`- Real data (data branch copy, pxDate 2026-11-20): real_data_check.py --data 3 / 3 · smoke_launch.py --data 14 / 14 ·
smoke_app.py --data 171 / 171`. (2) A PR that changes `src/`, anything under rule 1, or the pipeline (`fetch_data.py`,
`validate_data.py`, `already_published.py`, `watchdog.py`, `requirements*.txt`, `data/`, `tests/fonts/install.sh`, the
update-data / deploy / watchdog / logo-dev workflows and the `tools/` files they call, `tools/logos/`, `push_logos_branch.sh`,
`ci.yml` and `pr_rules.py`) needs this § 0 changed beyond whitespace. Files are classified in both the PR's tree and `main`'s, so
deleting a helper still counts. It compares the PR's merge commit with its first parent (the PR's own changes only) and stops if
HEAD isn't GitHub's merge commit for the PR. The description is the one in the event that started the run (CI holds no token,
`tests/test_screen_check.py`): after editing only the description, push the next commit — a re-run still sees the old one. A
push or manual run on a branch fails on purpose (its green would cover the PR's red); only `main` passes without a PR. Anything it
can't read (event file, git) fails with a message. Replayed on past merges it flags #170, #171 and #172 (the misses of 11-22) and
passes #173.

**#176 (US details after a stock split; audit 2026-11-23, SNDK 8:1 on 11-20):** after it merges, the daily run's US details step
puts a Yahoo details copy (cached up to 3 days, 14 when Yahoo refuses) taken before a split on today's share count: today's price ×
the split ratios ÷ the copy's price, for PER, PBR, 시가총액, 배당수익률 and 거래대금 (`fetch_data.us_info_split_view`; splits from today's
download, the previous publish's `splits` and `SPLIT_OVERRIDES`, up to today KST; a split dated after `usPxDate` counts only if Yahoo's
series already shows it). Such a copy is not fetched again just for the split: a normal refresh compares Yahoo's fresh numbers with
copy × ratio: when PER, PBR or volume look pre-split (within 1.25× of the copy without the ratio, at least 1.5× from copy × ratio) while
시가총액 agrees, it keeps the copy (`diff`: Yahoo's per-share numbers can still be pre-split); when 시가총액 itself looks pre-split, the
ratio was wrong and the fresh details win (`unfit`). Every multiplied copy is logged `!!` and warned (`fit`). It does
fetch again when the ratio can't be trusted (`odd`) and when a copy's price moved more than 2× with no split known (`jump`, a split
Yahoo reported late). Every path that can leave a number off by the ratio goes into `data.json usSrc.split` (only when there is
something to say) and the new warning-only gate row `미국 분할 뒤 상세 숫자 (PBR ↔ PER × ROE · usSrc.split · 경고만)` names it, along
with any US company split in the last 30 days whose PBR disagrees with PER × ROE beyond √ratio (at least 1.5). **SNDK itself stays
wrong until Yahoo corrects it:** its 11-21 PBR 0.63 (really about 5, so 가치 99) came from a fresh Yahoo fetch after the split, with no
older copy to compare, so this change does not fix it; the gate row names SNDK on every publish until then (expected, not a failure).
Blanking such a number on screen needs a new say-why line, so it is Jack's call (not asked yet). RUNBOOK § US stock splits.

**#172 (published closes), 2026-11-22:** in a week with days lacking a final KRX list, the daily run reads our earlier publishes
from the `data` branch (throw-away partial clone, no token, https, minimal env, 180 s total, process-group kill, gc off) and
confirms each Korean `c1w` day by day against KRX's base; a day with no publish is pinned by the next day's published `d1`;
no-trade rows confirm links only; rolled-back publishes are skipped; a published close that disagrees with a final list blanks
(`pubDiff`). Naver only for stocks we didn't publish (`c1wv` "nv", footnoted on the card). Stocks missing from the publish of the day before the
price date stay blank (`pxLink`: Naver may lag on the newest day). Dry run 45029231034 (week 11-16): 2,405 / 2,474 (2,363 exact,
42 Naver). RUNBOOK §이번 주 정리.

**#171 (이번 주 정리 card), 2026-11-22:** `src/v2/weekly.js` / `weekly.jsx` / `weekcfg.js` (`WEEKLY_ON` true, `WEEK_NV` "note").
Final when no KR or US trading day remains after pxDate / usPxDate up to Sunday and the publish (KST) is after pxDate (covers
Friday-holiday weeks, which get no Saturday publish); hidden on late data; US at ECOS `fxHist` at both ends. Left-out stocks are
named with Jack's lines; more than 5 Naver-checked stocks fall back to "out" until `nvNoteMore` is approved.

**#170 (v19.6e data), 2026-11-22:** `c1w` per stock (actual close before the week, price-only in both markets: US ex-dividend
weeks undone), `wkFrom` / `usWkFrom`, `c1wSrc`, `c1wv`; blank wherever a weekly move could be wrong; warn-only gate row
`이번 주 시작 종가 (c1w · wkFrom · usWkFrom · 경고만)`.


**#169 (US new tickers wait), 2026-11-22:** Jack (verbatim): "2. No relaxation. Instead, a stock newly added to the S&P (or NASDAQ) list joins our list only once it has a confirmed close; until then it isn't added. Nobody can hold it in the app before it joins, so nothing is lost, and the check stays as it is." A US ticker that is in neither the previous publish's US rows nor its `usSrc.own.aged`, and has no Yahoo close for the US date, is left out of today's file (`fetch_data.us_new_wait_step`, log `!! 새로 들어온 미국 종목 …`, `data.json usSrc.newWait`, reason in `usExtraMissing` / `usListSym`) and joins on the first run with a confirmed close; tickers the previous publish left out on purpose (`usLeftOut`) and a run without a previous publish keep today's behaviour. No existing gate row changed (`미국 d1 채움` N = 5 stays); a new warning-only row `미국 새 종목 확인 종가 기다림 (usSrc.newWait · 경고만)` names waiting tickers (and those waiting two publishes or more) and never fails. Closes the 11-21 risk (trial run 44849045557: 796 carried + LGND, MKTX, SNDK, VRNS missing; 6+ new tickers on a full Yahoo blank would have stopped the whole publish). RUNBOOK "US stocks at their last confirmed close" → "New tickers wait for a confirmed close".

**v19.6b screens (#168, merged 2026-11-22; held parts switch on in `claude/v19.6b-switch-on`):** Part B.2 on #145's data: the 오늘 볼 것 page
(`#home/today`, `src/v2/todaylook.jsx`; pure rules in `src/v2/look.js`) and 홈's new compact rows (home2.jsx `Look`, today.jsx
`WatchLook` on a first visit). Cards in Part B's order: 확인 필요 (held stocks' 유상증자 · CB · BW decisions filed in the last 30 days;
확인했어요 writes the new store part `seen`, matched by stock, kind and numbers on the same filing or board date, so a correction with
other numbers shows again; marks older than 120 days pruned on the next mark), 관심 종목 조건, 국민연금 (7 days, one decimal),
다가오는 일정 (US `ed` · `xd`, today to +7 days, 5 rows). 지분 변동 cards (held + watched, 7 days, |q| × today's close ≥ 1억원)
are built but off (`look.js` `ROLE_OF` null): their title needs `role`, and
`tests/test_v196b_answers.py::test_the_role_field_is_not_read_by_either_app_yet` pins that no screen reads it. 홈 now
loads disc.json when a Korean stock is held or watched. Not built, waiting for Jack: 공시 보기 (an existing test,
`tests/test_v2_app.py::test_pages_never_load_fixtures_or_other_sites`, keeps DART links to the 공시 tab), cards for 유무상증자 (`bonus`),
기타주식 (`cls` other) and two-class (`n2` · `p2`) rows, and the insider title for role 임원·주요주주 or blank (`look.insBoth`,
proposed "임원·주요주주 지분 변동"); #145's open question 3 (old decisions corrected recently): until Jack answers, a correction filed 30 or more days after its
board date, or one with no readable board date, is left out and named in the console (`look.js` `OLD_CORRECTIONS` false; 48 of
the 116 rows of the last 30 days on the 11-21 file, e.g. MSDI's 2026-05-12 decision filed again on 11-20).

**#162 (hand-added US stocks), 2026-11-21:** Jack's 11-21 answer 2 ("Yes, warn."), applied under his standing rule for checks on our own processing (11-19; N = 5, 11-20). A hand-added US stock (`EXTRA_US`, 67) that Yahoo doesn't send already only warned: the run writes a reason for every one it leaves out (`us_extra_missing`), and #149's drop step never drops them. What changes is only a hand-added stock missing from data.json with no reason in `usExtraMissing` (our own code losing it after `fetch_us`; no such path today): 1 to 5 now warn, named ("이유 없이 빠짐 n: …"); more than 5 still fail (`US_EXTRA_QUIET_MAX`, new; the 11 publishes with the record, 11-14 to 11-20, had 0). Still failing as before: a listed row with no price (or not a US stock row) and no reason, and a reason that is not text. RUNBOOK "US stocks added by hand (EXTRA_US)".

**Merged 2026-11-21:** **#154** (CLAUDE.md "decide, then report": Jack's rule of 11-20 with his 11-21 tweaks).

**#164 (deploy Daum refusal), 2026-11-21:** Jack's answer 3 ("3. Yes."): on code deploys only (own switch `BAEPSAE_DAUM_REFUSE_SKIP`, 1 on push and by hand, 0 on the deploy after a data publish; needs #157's limit too), when Daum refuses outright (HTTP 401/403/451, or three tries all refused/reset/far-end TLS cut or alert/429, for every stock settled so far, all 7 must-haves included, at least 21 of them), the deploy's Daum spot check stops and "pxDate 최종본 여부" turns WARN; the deploy continues on the other checks. Watchdog, daily publish gate and the deploy after a data publish unchanged; partial refusal, a must-have Daum answers with no close, and wrong closes fail as before. Still blocks code deploys: a fast 5xx outage, a non-JSON block page, a DNS failure, our own client's TLS failure (RUNBOOK, "Deploy gate: Daum spot-check time limit and refusal").
**Open 2026-11-21: #163** (Korean `d1` on the first volunteer-final day after backup days). Dry run 44783218618 (02:33 KST) failed
"필수 종목 d1": the volunteer list had a final 11-20 file but its 11-17/18/19 files were intraday (11-19 last commit 14:52, CSAT
close 16:30), so every Korean `d1` was blank and nothing would publish (main had the same code: the 11-21 morning runs would fail
too; the site stays on 11-19 data, dated). Fix: on a day with no usable previous-day file, `d1` comes from KRX's base price in
today's final file (Close − Changes) only where it equals, to the won, the previous publish's close for that day (its pxDate must
be the previous trading day; carried `pxd` and no-trade rows do not count); other stocks stay blank with the reason in the log and
data.json `d1Base`. Real 11-20 files: 2,371 / 2,500 confirmed, 0 differ, all must-haves get `d1`. RUNBOOK "Backup days and the
first volunteer-final day after them".

**Merged 2026-11-20:** #151 (second-source time limit, below), #146 (KR industry words from DART, below), **#152** (the Deploy and Watchdog logs print as they go, `PYTHONUNBUFFERED`; a deploy hung 19 minutes in the live gate at 09:03 with no output, cancelled, site unaffected), **#155** (v19.7b: 내 기준으로 찾기 and 두 종목 비교; live-checked 16:0x KST), **#156** (예전 뱁새: a US close-date line in the data box, shown only when the US date differs from the Korean one), **#149** (Jack's standing rule for the #139/#142 own-processing checks: more than 5 bad rows in one run stop the publish, fewer are dropped and named; a missing BF-B now warns), **#157** (the deploy's Daum spot check stops after 10 minutes with a loud warning and the deploy goes on; deploy only, the watchdog still checks every price; first deploy 206/206 in 44 s), **#145** (v19.6b data half: `disc.json` `issue` for 유상증자 · CB · BW decisions, insider `role`, US `ed` · `xd`; four own-processing checks under the standing rule; no screens yet; the first publish after it warns once on the 주요사항 공시 row while ~75 lookups wait), **#158** (KONEX closes from Yahoo .KQ × Naver, published only when the two agree to the won and Naver's price on the last final day still matches KRX's final file). Each merge: deploy green and live-checked (삼성전자, 현대차, every tab, both apps, 0 page errors).

**Jack, 2026-11-21 (~01:20 KST), verbatim:** "Hold v19.4 accounts and v19.6g until Jack says otherwise (lowest priority; v19.6h waits with v19.4). Queue: v19.7b, v19.6b screens, v19.6e, v19.3 Part L. Answers: 1. Yes to #154, with two tweaks: * New scenes in the pre-publish screen checks need no yes only if they don't depend on specific stocks or a particular day's data (the 두산밥캣 lesson). Otherwise they're category 2. * Anything that uses Jack's personal accounts or signs him up for something never goes ahead on the 12-hour rule. 2. Yes, warn. 3. Yes. 4. Not all-or-nothing. Leave that one stock out with the approved line ("며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요.") and check the rest. 5. (c), with no new timer for Jack. KRX's final file has been stuck since 11-16, so treat Daum × Yahoo as the normal path. Publish at 06:40 with what's confirmed (carries with their date line). Later runs update that day's data when more closes are confirmed. Hold only if confirmed coverage is below a floor; set it from last week's 06:40 coverage and show the number in the PR. 6. Yes, with a cap. If more than about half of US stocks would carry, the US side shows one line: "미국 종목은 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." Set the exact cap from history. 7. Yes. 8. Yes as written for up to 5 names plus "외 n종목"; above the Q6 cap, the market-wide line instead. Also: send the design chat the say-why audit file and the 10 dark-mode screenshots in your next update."
- What the numbers refer to (questions sent 11-21 01:12 KST): 1 = this rule's added lines (#154); 2 = the 67 hand-added US stocks (EXTRA_US) warn instead of stopping; 3 = skip the deploy's Daum check when Daum refuses outright (code deploys only); 4 = the late-data check with a carried close over 5 trading days; 5 = the backup-day early hold (#161); 6 = US carry's two frozen rows (98% d1, AAPL/MSFT/NVDA); 7 = the test edits in #160, US carry and #161; 8 = the shortened carried-stocks line.
- Order now: v19.7b (done, #155), v19.6b screens, v19.6e, v19.3 Part L. **On hold until Jack says otherwise:** v19.4 accounts, v19.6g, v19.6h (lowest priority).

**Jack, 2026-11-20 (~13:40 KST), verbatim answers:** "1. Yes to “more than 5 rows” as the default for the standing rule. Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish. 2. a) Yes. After 5 trading days, show "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요." instead of "데이터를 찾지 못했어요". b) Yes. c) Yes. d) Yes to the first. Second: drop a carry with a broken date and warn; block only above 5. e) Yes. f) Yes. 3. Yes. 4. Yes. 5. Yes. 6. Yes, but “left out” means carried with its own date and the line, like any other unconfirmed close. 7. Yes. Comment-only test edits never need asking. 8. a) Yes. b) Yes. c) Yes. 9. No, agreed. 10. Yes to 10 minutes, but a timeout skips the Daum spot-check with a loud warning; the deploy continues on the other checks. An outside site must never block a code fix."
- Also (verbatim): "US stocks carry like Korean ones. A US stock with no close from Yahoo carries its last confirmed close with its own date and the same line. Block only if many are missing (set the number from history), so a Yahoo gap never stops the Korean data again."
- Also (verbatim): "Order after these merge: v19.7b, then v19.6b screens, v19.6e and v19.3 Part L."
- What the numbers refer to: 1 = #149 / #145 standing-rule N and the BF-B row; 2 = the last-confirmed-close change (a 5-trading-day limit, b list line "{names}: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요.", c English "We couldn't confirm today's close, so this shows the {date} close.", d gate changes, e the screen-test edit, f the late-data check capped at 5 trading days in total); 3 = 25 power-equipment makers (KSIC 281) → 전기전자 in the old app; 4 = v19.7b keeps the raise choice on screen; 5 = backup days: before 08:00 KST publish only at ≥97% of the last publish's confirmed count; 6 = KONEX normal-day mismatch → carry; 7 = KONEX test comment; 8 = old-app US date line ("US stocks: priced at the {md} close (US time)."); 9 = no older-publish look-back; 10 = a 10-minute limit on the deploy's Daum spot check.

**Open, 2026-11-20 (evening):** #159 (last confirmed close for Korean stocks, all of Jack's 11-20 answers; dry run passed) merges after the 11-21 06:40 publish, the first with #145, #149 and #158, is live and checked. Built and in review: US carry (Jack's "also"; on top of #159), the power-equipment move (old app, KSIC 281/283/284/289 makers → 전자·전기장비), the backup-day early-publish hold (waits for Jack's timing answer: GitHub's scheduled morning runs start late, 08:53–11:06 on the last five weekdays). Then v19.6b screens, v19.6e, v19.3 Part L.

**Old-app English carry lines (#166), 2026-11-22 (Jack: "Yes, with "these show" when several stocks are listed"):** the old app's English lists for stocks at their last confirmed close follow the Korean rules of #159/#165: "{codes}: we couldn't confirm today's close, so these show the {date} close." ("this shows" for one stock); English 종목 고르기 cuts to five names "… and {n} more: …" and, above the US cap, "US stocks: we couldn't confirm today's close, so these show the {date} close."; the single-stock card sentence is unchanged. App only.

**US carry (#165), 2026-11-20 (Jack: "US stocks carry like Korean ones … so a Yahoo gap never stops the Korean data again"):** a US stock with no Yahoo close for the US date is published at its last confirmed close from the previous publish (`pxc`, its own `pxd`, Jack's line in both apps), up to 5 NYSE trading days, then left out with the aged line (`usSrc.own.aged`). A second publish with the same US date keeps that publish's close and change. The gate's `미국 d1 채움` fails only above 5 US stocks with no close and no carry; carried stocks only warn. RUNBOOK "US stocks at their last confirmed close".

**Live, 2026-11-19 07:13 KST:** the first publish with #137 (pxDate 11-18, Korean closes from Daum × Yahoo) passed the gate and is live; checked on the site. **#139** (US share-class tickers: Brown-Forman B joins the US list) is merging next, then one publish of its own. Remaining order: the dividend follow-up, v19.7b, v19.6f, v19.6c, v19.6b data.

**v19.6f (#140), 2026-11-19:** 연말에 확인할 숫자 merges (Nov 1–Dec 31, TAX_YEAR 2026 lock; Jack's M1–M5 lines). Next in the queue: the dividend follow-up, v19.7b (waits on Jack's question 8), v19.6c (question 1), v19.6b data.

**#142 (dividend follow-up), 2026-11-19:** exact bonus ratios with the three guards (Jack's yes, a loosening recorded in the PR), the rights / data / missing-data lines (dvLine 2 · 3 · 4). One publish of its own after the merge. Next: the DART company-record industry mapping for new listings (Jack, 11-19), then v19.7b, v19.6c, v19.6b data, the late-data check.

**Jack, 2026-11-19 (~09:30 KST), verbatim answers:** "1. Yes: "주가 {x}원 이하", "주가 ${x} 이하", "PBR {x}배 이하". 2. Yes. 3. Don't hide it; use "{date} 종가 기준으로는 할 일이 없어요." while the check runs on an old close. 4. Yes. 5. Yes, both lines. 6. Yes, with one nuance: in an emergency, use only already-approved wording, and ask about new wording after the fix is live. 7. a) Include 유무상증자, marked as such. b) Same-class basis: new shares against existing shares of the same kind (20.58% for 육일씨엔에쓰). c) "임원·주요주주". d) Yes. 8. a) Yes. b) Keep the 10% line, but replace "더 올릴 수 없어요" with "이 포트폴리오는 한 종목 최대 비중이 {x}%예요." The next screen offers raising it."
- Also (verbatim): "146 new listings without an industry: move the DART company-record industry mapping up, right after the dividend follow-up." and "For KONEX, find a second source to check Daum against."
- The 06:40 KST run (Tue–Sat KST, Mon–Fri UTC) is Jack's outside timer: a workflow_dispatch from his account at 21:40 UTC, every such day since 11-04.
- On second-source days, a Korean stock without a confirmed close is shown at its last confirmed close from the previous publish, with its own date (`pxd`) and Jack's line (#159, see below); a stock with nothing to carry, or past 5 KRX trading days, is left out ("이 종목의 데이터를 찾지 못했어요." / "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요."). Never an old price under today's date.

**#143 (v19.6c 관심 종목), 2026-11-19:** watch list with 이하/이상 conditions (Jack's 11-19 lines), 홈 rows, the side key `baepsae2.v1.watch`. App only.

**#145 (v19.6b data), 2026-11-19:** 오늘 볼 것 data (issue section, insider role, US ed/xd); first publish leaves ~75 pairs pend (gate warns) until the second run. Cards (B.2) next; B.2 must handle `bonus` and `cls`/`n2`/`p2` rows and question 3 (old decisions corrected recently). Its four own-processing checks follow Jack's standing rule (11-19): bad rows are dropped or blanked before writing, recorded in `ownDrop` (issueShape · issueBd · insiderRole in disc.json, usDates in data.json), and the gate fails only above N = 5 or when a remaining value would show a wrong number.
**#146 (KR industry words from DART), 2026-11-19:** reworked per Jack's 17:45 answers. DART industry codes fill a common stock's words only when the code maps cleanly to our existing groups (`data/ksic_map_kr.csv`, 110 / 234 codes ok; `indSrc.mapSha` records the rule version: names, table and pairings); preferred shares copy the common's words, sector and 2.0 group but stay out of old-app peers and medians; standing rule for the gate row (pipeline reverts bad fills, records `ownDrop.indFill`, gate fails above `IND_FILL_MAX` = 5 or on a remaining wrong-group value); 데이터 출처 credit line.

**#144 (late-data check), 2026-11-19:** when data is late the portfolio check runs on the last official close for up to 5 trading days (from the close date), dated "{date} 종가로 점검했어요"; nothing labelled 오늘 on an old close; "{date} 종가 기준으로는 할 일이 없어요." (Jack, 11-19).

**#147 (watchdog retry), 2026-11-19:** the Watchdog asks the site once more, 20 s later, after a 5xx before raising an alarm (Jack, 11-19, Q10); once a retry has failed, later 5xx answers fail at once (30-minute job limit). Log and run summary: "5xx 다시 물음". No gate or threshold change.

**#148 (왜 움직였나 US date), 2026-11-19:** a US stock's close on 왜 움직였나 is never labelled with the Korean date (no usPxDate → no date, said in the console), and the late-data date line follows the stock's own market (cofmt.lineDate; review of #144). Open: 예전 뱁새 "가격은 {md} 공식 종가예요." labels US holdings with the Korean date (needs Jack's wording decision).

**#159 (Korean last confirmed close), 2026-11-21:** on backup-price days a Korean stock whose close the two sources could not confirm is shown at its last confirmed close from the previous publish, with its own date (`pxd`) and Jack's line "오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요." (lists: "{names}: …"; old app English "We couldn't confirm today's close, so this shows the {date} close."), for at most 5 KRX trading days; after that it is left out with "며칠째 종가를 확인하지 못해서 이 종목은 잠시 빼 두었어요." (`pxSrc.own.aged`). KONEX stocks #158 confirmed are never carried. Gate: only clean carries are exempt from the pxDate price rows; the "국내 종목 수" rows count only stocks priced at pxDate; more than 5 carries dropped by one check in a run fail. Late data (#144, Jack 11-20 f and 11-21 answer 4): a carried stock whose own close is more than 5 trading days old in total is left out of that day's check with the same aged line; every other stock and portfolio is still checked. RUNBOOK "Korean stocks at their last confirmed close".

**#158 (KONEX two sources), 2026-11-20:** Jack's 11-19 answer 5 ("Naver for KONEX only, always with Yahoo, published only when they agree to the won; daily KONEX checking too"; CLAUDE.md Naver line updated to say exactly that). Second-source days: KONEX closes from Yahoo `.KQ` × Naver daily close, confirmed only when equal to the won (live check 11-20: 87–93 of 107 a day, every one equal to the KRX final file; the 11 KONEX stocks Yahoo lacks, e.g. 본시스템즈, always drop out), and only those a normal day would publish go in (market cap ≥ the 2,500th in the last final list: 23 of 91 on 11-19), so the "국내 종목 수" floor protects as before (review M1); those ~23 displace about as many of the smallest KOSPI/KOSDAQ stocks near the cut-off, as on a normal day. Anchor check (second review M1): a KONEX close counts only if Naver's close on the last final day (px0) also equals that final file's official close, so a split or 무상증자 after px0 that both sources have already back-adjusted can't be published as the day's close (left out loudly, `pxSrc.fb.knx.adj` / `noAnchor`, gate WARN). Volunteer-file days: every published KONEX close checked against Naver (107/107 on 11-10 … 11-16), WARN only. New WARN row "코넥스 종가 두 출처 (경고만)"; `pxSrc.knx`, `pxSrc.fb.knx`; `pxSrc.fb.conf` now includes the KONEX stocks put into the file. KOSPI/KOSDAQ prices, sources and checks unchanged; Naver never used for them. Open for Jack: what to do on a volunteer-day mismatch (drop the stock / stop the publish / warn only); whether the gate should re-fetch a KONEX sample itself on backup days. (The stale comment "코넥스는 두 출처 모두 없음" in tests/test_kr_two_source.py is fixed: comment only, under Jack's 11-20 rule.) RUNBOOK "KONEX closes: Yahoo × Naver".
**Standing rule for own-processing checks (Jack, 2026-11-19):** "Standing rule for checks on our own processing: a single bad row is dropped or blanked with a loud warning and the rest publishes. Block only when many rows fail in one run (set the number from recent runs and show it in the PR) or when a value would show a wrong number. Apply this to #145's four, #146's one, and the checks you added in #139 and #142. Adding any check that stops the publish still needs Jack's yes first." #149 applies it to #139 and #142: the rule that picks the bad rows lives once in `validate_data.py`; the daily run drops the US share-class rows and blanks the hidden-yield reason lines (`dvLine` 2 · 3 · 4) it finds, logs them and records them in `data.json` `ownDrop`; the gate fails only above N = 5 rows (the last 25 publishes: 0; Jack, 2026-11-20: "Yes to “more than 5 rows” as the default for the standing rule.") or when a bad value is still in the file, and warns otherwise. Checks on what a source sends stay as they are, except #139's "BF-B in the data or named with a reason": Jack, 2026-11-20, verbatim: "Brown-Forman B: no, it becomes a warning; one stock missing from a source never holds the publish." — BF-B missing now only warns (named, with its reason or "이유 없이 빠짐"); the row still fails when BF-B's row is in the list without a price, and a published `BFB` still fails the next row. Files without `ownDrop` keep the old rule. #145 and #146 are not in this PR. RUNBOOK "Checks on our own processing".

**#151 (second-source time limit), 2026-11-20:** night dry runs hung 61–74 min on the Daum × Yahoo per-stock checks (sources throttled; no overall limit). Each of the three per-stock steps now stops after 600 s (must-haves first, then the last final listing's market cap); Yahoo closes come from one chart per stock (same values as the batch); KOSPI read has a timeout; WARN row "가격 확인 시간 한도". Open for Jack: a publish-stopping check when the cut exceeds ~50 on a blank-close night, and holding backup-day publishes until most closes are confirmed.

**#161 (backup days: coverage floor and same-day updates), 2026-11-21:** Jack's "(c)" (11-21): Daum × Yahoo is the normal path. `tools/publish_hold.py` (step id `hold`, before the gate, any time; "the last publish" = the site's file, the `data` branch's `data.json` via `already_published.read_published`, main `HEAD` only for the same-day check when that can't be read (on a Korean-holiday morning with a newer US date it is compared with instead) and to spot a half-finished publish — when `HEAD` is the newer publish, a "same" run publishes to repair the data branch): no publish when the KR or US date is older than that file; hold below `COVERAGE_FLOOR_PCT` 97 (11-19 98.99% · 11-20 98.88%; coordinator's call under Jack's rule); a same-KR-date run publishes only if it loses nothing (`lost_stocks`: no stock; on the same US date no US close back to an older date; no d1 lost on an unchanged Korean close) and has more `kr_px_count` (or a newer US date). Same-KR-date runs after a backup publish keep that publish's Korean stocks beyond the top-2,500 cut (`kr_same_day_keep`; list slightly above 2,500 until the next new date; gate count rows have no upper bound); the run that switches to the volunteer final file on the same date keeps the morning d1 where the close is unchanged (`kr_d1_same_day`, `d1Base.same`; #163 unchanged). Same-day updates fill Korean closes only: US carries (`pxc`) never cause a re-run and wait for the next new US date (decided in the second review). Third review: a newer US date ignores US stocks (not fund rows) leaving the list; a coverage record that doesn't add up skips only the floor (the same-day rule still runs); a crashed decision or unreadable data branch on a same-day run is kind `stop` (hold, exit 3, the step fails, red run, alarm); quiet runs only while the live file is < 11 h old (gate's 12 h `publishedAt` row); re-used d1 must match the KRX base (`d1Base.krx`); a single-source close that differs from the published close is not re-used (`clash1`, `pxSrc._one` in memory only); DART `no_call` only when the cache's `meta.dartAt` ≥ the live `publishedAt` (`dart_cache_covers` / `dart_cache_mark`, never written by dry runs), an empty cache on a same-day run stops before any DART call. `already_published.open_closes` counts only re-askable open closes (`fb.open` + `fb.knx.open`; Yahoo "no data" answers only — failures stay open). Re-runs: `kr_fb_cache_pick` (trusted only for closes the live file has), `kr_same_day_reuse` (KOSPI/KOSDAQ only), no DART calls when the KR date equals the live file's (`DartClient.no_call`; live `disc.json` only from the same publish and same US date), 3-hour quiet period (record in `.dart-cache/kr-rerun-v1.json`, live runs only, trusted only if that run ended green per GitHub's public run record; quiet runs are neutral). Watchdog: marker step "발행 판단 표시 (감시에 중립인 보류)" → neutral; "same, not better" → healthy. Not done: re-using the Naver price series on re-runs. The 09:13 prompt is updated after merge. RUNBOOK "Backup days: coverage floor and same-day updates".
**#160 (예전 뱁새 power-equipment makers), 2026-11-20:** Jack's "3. Yes" (11-20): the old app's sector rule (`fetch_data.map_sector_kr`, KRX industry text + main products → keyword rules) put 27 power-equipment and cable makers in 전기·가스·환경 (utility) because "발전기" in KSIC 281's name and "전력선" in two cable makers' products hit utility keywords; they showed "요금은 정부가 정해요…". Now the four KSIC names 2.0 groups as 전력기기·전선 (281 · 283 · 284 · 289, `SECTOR_ELEC_NOT_UTILITY`) give 전자·전기장비 (elec) where the rules would give utility; companies whose products hit an earlier key (반도체 · 2차전지 · 기계 …) and real utilities are unchanged. 2.0 groups were already right (power_eq) and are unchanged. `data/ksic_map_kr.csv` row 281 now says elec but stays not filled from DART (ambiguous; open question for Jack). Not moved, reported: 16 KSIC 251 metal-structure makers ("증기발생기" in the name) and 19 other companies whose products mention 발전 · 환경 · 전력 (plant builders and servicers such as 한전KPS · 한전기술, builders, 코웨이, LS, 니어스랩 …) are still in utility; 14 real utilities stay. Also (review): disc.json insider and 국민연금 rows carried from earlier runs take today's sector (`disc_rows_sector_now`; on 11-20 data 1,070 of 3,300 insider rows change: 17 utility → elec, 809 기타 → a real sector, 244 between other sectors from rows written in Aug–Oct, e.g. 66 기계 → 반도체; a row keeps its sector when today's is 기타, logged "!!"); the run logs the moved count and "!!" for any power_eq company left in utility (`power_eq_sector_report`); the name match ignores spaces and middle-dot variants (`sector_name_key`). Pipeline change: dry run before merge.

**Incident, 2026-11-18/19.** No data published after 11-17 06:40 KST (the site said "2일째 갱신이 멈췄어요").
- **Cause:** the volunteer copy of the KRX list stopped saving its after-close file after 11-16, and KRX's company list now needs a login, so industries came back empty. The gate rightly blocked every run.
- **Fixes:** #134 (a test that failed only because of the date) merged 01:25 KST. #137 merged 03:59 KST: Daum's official daily prices, kept only where Yahoo `.KS`/`.KQ` agrees to the won; industries carried forward.
- **Trial run:** 44368441532 passed the gate on pxDate 11-18.
- **Still to do:** the first real publish with #137 waits for GitHub's late scheduled runs. If none has published by 08:30 KST, start one by hand. Then check the live site and close issue #136.

**Jack, 2026-11-19 (~01:15 KST), verbatim:**
- "Emergency first. Restoring live data comes before everything else."
- "2. The price fix: cross-check Naver's closes against a source that is still working, such as Yahoo's .KS closes, not only the volunteer source's next-day file, which may be gone. Merge as soon as the two-day proof and a trial run pass, then publish right away. Don't wait for Jack."
  - Naver's daily close turned out not to be the official close (it includes after-hours trades), so #137 uses Daum × Yahoo instead. Jack was told.
- "3. Permanent two-source rule: official closes always come from two independent sources. If the primary is late or not final, the second one is used automatically after a cross-check. The publish stops only when neither can be confirmed."
  - Not yet in CLAUDE.md: that waits for Jack's yes.
- "4. Emergency rule for CLAUDE.md (Jack's yes)": now in CLAUDE.md under "The two disasters" (#138).
- "5. Product change (Jack's yes): when data is late, still run the portfolio check on the last official close, with its date ("11월 16일 종가로 점검했어요."), for up to 5 trading days. Skip it only after that."
- **Answers to the 11-19 questions:**
  - KRX industry carry-forward: yes. Later, new listings take their industry from DART's company records.
  - The 7 dividend blanks: "no blank without a reason; use "회사 공시에 배당 계산에 필요한 자료가 빠져 있어서 배당수익률은 비워 두었어요.""
  - 대동기어 and 남성: yes. The small-holder yield: a later PR, "labelled as the 소액주주 rate".
  - v19.7b lines a–d: yes. For e: "use the 이/가 helper, and add why only 10% (the per-stock cap)". Grey verdict box: yes.
  - Halt list and watchdog retry: yes.
  - v19.6f lines: yes. The 환헤지 line "only with the official source for the 2026 deduction cited in the PR". Known limits and the 2026 lock: yes.
  - v19.6c labels and error: yes. Hint: "주가와 PBR은 넣은 값 이하가 되면, 배당수익률은 넣은 값 이상이 되면 알려 드려요. 비워 두면 그 조건은 쓰지 않아요." (price and PBR alert at or below). The 홈 notice while the close shows: yes. NOT_NUMBERS exact form: yes.
  - v19.6b data: board date read from the filing's document, DART's own replacement record, cancelled 유상증자 kept, and insider words: all yes.
- "After the data is live again, merge the six waiting branches in your planned order."
- **Queue:** after the first publish,
  1. the six waiting branches: US share classes, the dividend follow-up, v19.7b, v19.6f, v19.6c, v19.6b data;
  2. the late-data portfolio check (item 5);
  3. follow-ups: a primary-day two-source FAIL with a coverage floor, the halt list, the watchdog retry, industries for new listings from DART, and the 소액주주 yield;
  4. after that, unchanged: v19.6b screens, v19.6e, v19.6g → v19.4 → v19.6h. v19.6f must merge by Dec 10.

**Jack, 2026-11-15 (morning): answers** to the 11-15 morning update (verbatim where quoted).
- 1, 3, 4: yes. (#129: merge with the 종목 순위 / 업종별 등락 side effects; switch on row 29
  "우선주·ETF처럼 기준 점수가 없는 종목 {n}개({names})는 비중에만 넣었어요." with the one smoke_v2 assertion edit;
  keep #91's row-5 wording.)
- 2: "yes, but with two labels: "거래정지" for halted stocks and "거래 없음" for stocks with no trades that day;
  "등락률 없음" for other blanks." (종목 순위 change spot.)
- 5, 6, 7: yes. (Old app: drop "(파이프라인이 사업보고서를 못 찾은 종목이에요)" on the 60 우선주 pages and the 24 KONEX
  filers, with the test_reread_lines control edit; third sentence "이익 없이 움직인 가격은 기대와 수급이 만든 거예요."
  only when both ends are losses, with the test_oldapp_dcf_wording edit.)
- 8: "use this line now, not a bare "–": "회사 전체 숫자와 비교할 수 없어서 이 숫자는 비워 두었어요.""
- 9: yes (keep checking the 4 US-style filers based abroad).
- 10: "yes, but the line on a crash day is "오늘은 이 숫자를 확인하지 못해서 비워 두었어요.", not "자료가 없어요"."
- 11: "yes, with "유상증자로 주가 기준이 바뀌어서, 배당수익률은 다시 계산하는 동안 비워 두었어요.""
- 12: "Jack's explicit yes to accepting exact non-whole bonus ratios from the filing when the share counts confirm them,
  with the reviewer's three guards. Record it under 안전 규칙 변경." (Guards: every event is a fric/pifric bonus with
  r = 1 + x read from the API; the product equals dpsF to 1e-6; the dvProof checks pass.)
- 13: "yes, but with a line: "회사가 공시한 배당 자료와 주식 수가 서로 맞지 않아서 배당수익률은 비워 두었어요.""
- US list: "fix Brown-Forman B, then check every share-class ticker in the S&P 500 and NASDAQ sources (dots, missing
  separators, A/B classes) and add any others missing for the same reason. List them in the PR."
- Order: "merge #129, the old-app lines and the wider foreign check; then v19.7b; then v19.6f before Dec 1."
- **Queue now (2026-11-15; replaces the "Then screens" line of the 11-13 block below):**
  - Jack's order: #129, the old-app lines (this PR) and the wider foreign check; then v19.7b; then v19.6f before Dec 1;
    after that, unchanged from the 11-13 queue: v19.6c, v19.6b, v19.6e, v19.6g → v19.4 → v19.6h.
  - Data work beside the screens (Jack asked for both on 11-15; their place in the order is the coordinator's, data and
    screen work run side by side per his 11-14 evening order): a dividend follow-up (the rights line, non-whole ratios
    with the three guards, the data line) and US share-class tickers (Brown-Forman B …).

**Jack, 2026-11-14 (later evening): answers and approved lines.**
- Q1–Q5 yes: #fin-warn's three PR #68 test edits; the Unilever row in `test_override_table_pins`; the
  `test_reread_lines` edit for the 40 KONEX/new listings (old app → "재무제표 데이터가 아직 없어요."); BHP/RIO without an
  업종 group and EPD/ET/BNS left out; widening the US foreign check (TSM, ASML, BABA, NVO, SHOP) comes right after the
  dividend-yield bug.
- Approved lines: US numbers blanked because they don't match company totals "자료의 숫자가 회사 전체 재무제표와 맞지
  않아서 비워 두었어요."; 재무 경고, some checks couldn't run "4가지 중 {k}가지는 필요한 자료가 없어서 확인하지 못했어요.";
  재무 경고, none could run "필요한 자료가 없어서 확인하지 못했어요."; companies with no statements yet (2.0) "공시된
  재무제표가 아직 없어서 계산할 수 없어요." (the old app keeps "재무제표 데이터가 아직 없어요.").
- Broken price history: a must-have stock with a broken day warns; two or more must-haves, or many stocks newly
  breaking in one run, block the publish. Hide only the numbers whose calculation window includes the bad day; where
  only some are hidden, each uses "과거 주가 기록 일부에 오류가 있어서 이 숫자는 비워 두었어요."; the full line stays
  where all are hidden.
- The 57 old-app 주가 분해 cards stay hidden (the old app is being retired).

**Jack, 2026-11-14 (evening) — supersedes the budget rules below:**
- **Model:** Opus 5.5 Extra high for the main session and every helper, reviews included. No Fable until Jack says so
  (he is saving it for a full-app audit later).
- **Budget mode is over.** Build continuously until Jack says stop (he stops new work at 90% weekly usage). Limits: at
  most three PRs being built at once and at most four helpers running at any moment; no polling; two updates a day
  (morning and evening) with all questions in them. Every CLAUDE.md merge rule stays.
- **Answers:** Q1 yes (#122's `tests/test_v196d_dark.py` edit). Q2 (a), this week: for the 18 Korean stocks whose
  price history is broken (#125's WARN row), hide every number built on it: the 52-week range, 출렁임, 위험, beta,
  1-year and other period returns, and the % labels on their charts; take them out of the 추세 list on 홈 and any
  출렁임-based list or rule. Line (approved): "과거 주가 기록 일부에 오류가 있어서 52주 범위와 출렁임·위험 숫자는 비워
  두었어요." Repairing the history is a later PR. Q3 yes: 예전 뱁새's false "적자 구간이 있어서…" line → the existing
  "재무제표 데이터가 아직 없어요"; the "11월 10일" notice: if it is the approved 7-day EPS/ROE notice, keep it until
  11-17 wherever it is true and remove it only where it is wrong (e.g. 우선주 pages); if it is something else, remove it.
- **Order:** (1) merge #122; (2) the Q2 hide, plus the 재무 경고 bug (when one check has no data, show the warnings
  that were checked and count the unchecked ones, using the closest approved line until the design chat sends
  wording) — first, because users now see no warning where there may be one; (3) missing US stocks; (4) the 우선주 /
  trading-halt / no-trade lines; (5) the dividend-yield bug (72 payers with no yield after a share-count change: fix
  the calculation); (6) v19.7b; (7) v19.6f (in review before Dec 1); (8) then v19.6c, v19.6b, v19.6e, v19.6g. Data
  work and screen work run side by side. Keep watching Monday's and Tuesday's publishes for the Q3 reports (#118's
  FAIL-20 row). After Wednesday 22:00 the design chat sends the batch of reason lines and the dark-mode fixes: have
  the six dark-mode screenshots (dark and light side by side) ready.

**2026-11-14:** #119 (v19.6a) merged (bf33f12); #125 (52-week fix) merged (9b6b5c9) and published 14:57; #122
(v19.7a: 종목 바꾸기) merges with Jack's yes on the `tests/test_v196d_dark.py` edit (the script goes to node on stdin).

**Jack, 2026-11-14:**
- "Yes, fix the wrong 52-week numbers first." #125 (Korean price series never pinned on an old share basis: 에쎈테크,
  인지디스플레, STX and 15 more) goes ahead of the missing US stocks. Queue after it: #122 (v19.7a) →
  missing US stocks → the 우선주 / suspended / no-trade lines → v19.7b → v19.6f.
- The 우선주, suspended-stock and no-trade lines were approved in the design chat: use the lines in `docs/design-chat/`
  on branch `docs/say-why-audit` (2026-11-08-say-why-audit.md, 2026-11-08-dart-gaps.md §9) exactly; propose new
  wording only for cases they don't cover. Build them right after the missing US stocks.
- A sold-out stock still in the plan that isn't suggested for buy-back shows which of its rules it fails, plus "다 판
  종목이에요. 다시 살 계획이 없으면 계획에서 빼 주세요." It must never look blank (built in #119).
- The next update lists every number from the say-why audit that is still hidden or adjusted without a reason line
  (screen, number, why); the design chat writes all the missing lines in one batch after Wednesday 11-18.
- Open, waiting for Jack: (1) the 18 Korean stocks whose Naver history still has a move beyond the ±30% limit (#125's
  WARN row; e.g. 에이프로젠 after an unrescaled 감자) keep artefact numbers until he approves a reason line to blank
  them; (2) #122 needs his yes to change `tests/test_v196d_dark.py` to pass its script on stdin (the bundle passed to
  `node -e` is over Linux's 131,072-byte argument limit; nothing loosened).


**Standing instruction (Jack, 2026-11-13): speed up what users can see.** Safety work stays as careful as it is; it
just stops blocking screen work.
- Correction in the same message (Jack): "Correction to the last message: v19.5b doesn't wait for the currency fix. J4
  keeps the wrong PBRs off the 홈 list, so merge v19.5b as soon as its own checks are green." So PR #120 (v19.5b)
  does not wait for #114: it merges after #107 (Jack, 2026-11-12: "Do it before v19.5b"), once its own checks are
  green. Its own 가치 guards (PBR ≤ 0, a Korean PBR that rounds to 0.00, the US 4× rule; built in its third round)
  also keep those rows out of 내 기준.
- Two tracks side by side. **Track A, data and pipeline** (the currency fix, the token fix, the gate rows, the item 4
  report): these merge one per real publish, as already agreed. **Track B, screens:** start now and keep it moving
  while Track A waits for publishes. Order: v19.5b, then v19.7 (portfolio editing: add and remove stocks, record
  sales, find stocks, which Jack asked for on 11-07), then v19.6a, then the rest of v19.6 as its dependencies allow,
  with dark mode as soon as it can go. (Final order: his second message, below. The merged v19.7 spec makes v19.7a
  wait for v19.6a's store v2 and sales, so v19.6a is built first; told Jack 11-13.) A safety fix jumps ahead of
  screen work only when users are seeing wrong numbers right now or the site could break. Otherwise screens go first.
- Keep Track B fast: (1) ask Korean wording questions before you build, not during — at the start of each version
  send every new line from the spec and boards, plus every small string you'll need, in one 「새 문구」 table with
  proposed wording, and build while the answer comes back; (2) follow the boards; for details neither the spec nor
  the board covers (spacing, order, small states), match the approved screens already live and list them in the PR
  under "Choices I made"; ask only when a choice changes what a user can do or read; (3) don't sit idle: while a PR
  waits for CI, review or an answer, prepare the next one on its own branch; (4) note unrelated problems in the
  update instead of fixing them, unless they're wrong numbers users see or something that could break the site;
  (5) target: at least one change users can see goes live every day.
- After each screen merge: besides the live check, tell Jack exactly where to look on his phone (tab, what to tap,
  what he should see).
- Updates, short, in this shape: 1. Problems (if any). 2. Live since last update: what users see now. 3. In progress,
  one line per PR. 4. Questions, with the recommended answer first, all in one place. 5. Once a day: a table of every
  approved board (v19.3, v19.5, v19.6, v19.7) marked live, partly live or not started.
- **Jack's answers, 2026-11-13 (second message):**
  - Track B order. Jack: "Both yes: v19.6a before v19.7a, and v19.6f right after v19.7a. If v19.6f isn't in
    review by Dec 1, it jumps the queue." The rest is Claude's list from the 00:06 KST update, sent under his "don't
    wait for an answer to the list": v19.5b → v19.6a → v19.7a → v19.6f → v19.7b; v19.6d (dark) as soon as v19.5b
    is in; then v19.6c, v19.6b, v19.6e, v19.6g, and v19.6h last (needs v19.4). v19.6f must merge by Dec 10, 2026,
    or it waits for Nov 2027 (the v19.6 spec's build order). Each spec's Status line says what is live and what is
    next (Jack: "Fix the Status lines … so a fresh session never starts from the wrong task").
  - New screens use the shared colour tokens only, never fixed colours, so dark mode covers them.
  - The Korean PBRs under 0.1 are wrong numbers users see now, so they are Track A, beside the currency fix: scan every
    Korean company for the DART unit error (any PBR under 0.1, or assets ≠ liabilities + equity), check SG&G and
    앱토크롬 against their filings, hide every number built on faulty amounts with "공시 자료의 단위를 확인하고 있어서
    이 숫자를 잠시 비워 두었어요.", then repair the reading. v19.5b gets its own Korean 가치 guard (a PBR that rounds
    to 0.00 is never real) so it doesn't wait for that fix.
  - Only the currency fix and the token fix need a real publish of their own. #107, #111 and #115 (the deploy check)
    merge as soon as their test runs and reviews are green, after the first real publish of 11-13.
- **Jack's answers, 2026-11-13 (third message), on the currency fix (#114) and more:**
  - Currency names approved, with 일본 엔화, 중국 위안화 and 남아공 랜드. #114 ships hiding PER, PBR and the yield
    for the 27 non-dollar filers.
  - **Next, within days:** bring all three back for them, all 27 PBRs included, from whole-company totals: market value
    ÷ equity (PBR) and ÷ net income (PER), with equity and income converted at that day's rate. That fixes currencies,
    share classes and ADR ratios together. Prove it against today's correct figures before showing anything.
  - 0% yield only where the source clearly shows no dividends in the last 12 months; a blank field stays hidden.
  - A US PBR that rounds to 0.00 (BRK-B: share classes) is blank, with its own line: "자료상 PBR이 0에 가깝게 나와서
    확인하는 동안 비워 두었어요."
  - The 17 가치 verdicts that change when the 27 PBRs leave the industry medians are corrections. Industry comparisons
    use the median, with the company count in the receipt ("업종 {n}개 회사와 비교"); keep it that way.
  - v19.5b's one existing-test edit (the 아이폰 기록 옮기기 scene waits for 홈 to load) is approved, provided its wait
    has a time limit that fails the test.
  - Split the daily run into a read-only job and a publishing job, after the currency fix, the Korean unit fix and
    the token fix.
- **Jack's answers, 2026-11-13 (fourth and fifth messages): limits for this week, and his answers to the open list.**
  - **Model and budget (until Jack says otherwise).** Jack switched the session to Fable 5.2 (High). Until he says
    he has pressed his Fable reset, use Fable for everything, the session and every helper, no Opus (this week's Fable
    use is refunded; Opus use is not). Helpers that write or judge still run at Extra high, set explicitly (rule 7).
    If Fable refuses because its limit is reached, stop and tell Jack it is time to press the reset. When he says the
    reset is pressed: back to Opus 5.5 Extra high, and "finish what's reviewed, start nothing new" until Wednesday
    2026-11-18 22:00 KST.
  - Always: at most two helpers at once. No polling (look once after a run finishes). One update a day, under 15
    lines, with all questions in it: one question message a day. At most two builds open at once. A review after
    fixes is one reviewer, one round.
  - Work order: finish the reviewed PRs first (the #114 publish, #113, #118, #116, #117, #115, #121, #119, #122),
    then continue the queue on Fable: v19.6f next, then v19.7b.
  - Data and gate: the exchange rate for a US buy dated D is the Bank of Korea 15:30 close of D (`ecos_close`).
    Yahoo's split data unreadable for 6 days is a loud warning, never a held publish ("A minor source outage must
    never hold back everyone's data"). Korean splits: their own PR after v19.6a. #118: its two FAIL rows yes; FAIL
    when 20 or more Korean companies are newly hidden in one publish; `PBR_LOW_CHECKED` (SG&G, 앱토크롬) yes; the
    old app's 미니 점검 shows "—" for a blank ROE or 부채비율. #115: when the code being deployed is exactly the live
    code, a failing check reruns once and then the publish goes ahead (it never blocks itself); its extras later.
    The extra 2-point warning for #111: no.
  - Wording: v19.6a's open lines yes with the reviewers' versions, except the date hint, which is "미국 주식은 미국
    현지 날짜로 적어 주세요."; v19.7a's five lines yes (나가기; "{name} 목표 비중 줄이기 / 늘리기"; 바꾼 기록 at the
    bottom of 종목 바꾸기; "바꾼 내용을 저장하지 못했어요. 화면을 다시 열어 확인해 주세요."); #116's line "공시에
    단위가 잘못 적혀 있어서 바로잡아 계산했어요." in 가치 자세히 only; #118's hiding line also on the 홈/포트폴리오
    warning tile; v19.5b's US 성장 line becomes "전년 동기 대비 분기 매출 증가율 높은 순" (a small PR, not built yet).
  - Screens: v19.6a amounts are always exact, and a sold-out holding counts as 0 shares (spec A.1). v19.7a stores
    each stock's planned weight (untouched stocks' bands never move), and shows the "can't reach 100%" line only when
    the targets really can't (holdings already above the cap count at their own %). v19.7b: imported portfolios (rows
    with records read-only), planned-but-not-bought stocks on 포트폴리오 with their 기록 button. v19.5b's US minimum
    sizes (25억원 of quarterly revenue, 100억원 of equity, at the day's rate) need a small data PR first. Dark mode
    ships as built; its six odd-looking spots (payout ring track, the biggest treemap block, the 처음부터 만들기
    button on the navy card, 준비 중 cards, faint 업종 bars, navy letter tiles) are a follow-up.
  - Process: a revert still passes the other merge checks (CI green plus the real-data checks; its review comes
    after). The CLAUDE.md line for "Choices I made": yes (a small docs PR, not written yet). v19.4 (accounts) goes
    after v19.7b and before v19.6h. Jack, 11-11, still stands: ask before changing any test beyond what was approved.
- **Jack, 2026-11-13 (sixth and seventh messages): back on Opus; his answers.**
  - The weekly Fable limit was reached; Jack pressed the reset and switched the session to Opus 5.5 Extra high. Until
    Wednesday 2026-11-18 22:00 KST: finish what's reviewed, start nothing new; helpers on Opus at Extra high; at most
    two at once; one reviewer after fixes. **Then, after #119 and #122 merge:** build one screen version at a time on
    Opus with one reviewer: v19.6f first (Dec 10 deadline), then v19.7b. Stop new work when Jack says his usage has
    reached 70%.
  - A sold-out stock kept in the plan (#119): "own" (it reads 먼저 사요 on its own band; every other holding reads as
    before), with the approved line under it: "다 판 종목이에요. 다시 살 계획이 없으면 계획에서 빼 주세요." Once #122
    is live, the line opens 빼기. The two edits of tests on `main` for this (test_v2_d2, test_v2_pf): Jack's yes.
  - A US record dated a day whose exchange rate isn't published yet stays a known limit, with its own approved line:
    "이 날짜의 환율이 아직 없어요. 보통 다음 날 아침에 들어오니, 그때 다시 저장해 주세요." (keep what was typed, if cheap).
  - Dark mode's six odd-looking spots: after Wednesday; send the design chat side-by-side dark/light screenshots of all
    six in one go.
  - **Visual priority (Jack, 11-13):** after #119 and #122: **missing US stocks** next, then **v19.7b**, then **v19.6f**
    (still in review before Dec 1). Missing US stocks: no separate report; add BTI, ADC and NNN, plus the US stocks
    Korean investors hold most (예탁결제원 SEIBro, if reachable) or else about 30 widely held NYSE dividend names, and
    New York-listed foreign companies (Shell, BP, Unilever, Toyota, Sony …; #114 hides their PER, PBR and yield with
    the approved line). List every added stock in the PR; one Opus reviewer and a branch dry run.
  - Next update to Jack: a table of every visible change he has asked for since 11-07, each live / ready / not started,
    with where to look on the phone. Found 11-13: only the 우선주 count line under 내 점수 is live; the per-stock lines
    for 우선주 without figures, suspended and no-trade stocks were left as "later" on 11-08 and never built.
- **Queue now (2026-11-13 17:29 KST; every merging PR updates this):**
  - Live: #107, #111 (gate rows), #120 v19.5b (홈 종목 순위), #121 v19.6d dark mode (☰ → 화면 모드), #115 (the deploy
    check: every code deploy runs the daily run's three real-data checks before it uploads; RUNBOOK "The deploy
    check"). After #115's merge: its own deploy and the first deploy after a daily publish are watched; if a deploy
    goes red for something that is not a real regression, #115 is reverted at once.
  - #114 (currency fix) is published and live (run 43368392513, 11-13 13:53 KST, once Yahoo had the 11-12 prices
    back): the 27 non-dollar filers show "–" for PER and PBR with the reason line; BRK-B has its own line.
  - #113 (token fix) is merged; its own publish (a manual `dart=cache` run right after the merge, 11-13 afternoon)
    is watched to the end and #113 is reverted at once if the push fails (Jack, 11-12).
  - #118 (Korean unit guard) is merged: 진코스텍 and 디와이에이 are blanked with Jack's line; the gate fails when 20
    or more companies are newly flagged in one publish (RUNBOOK). Watch the first publishes on 2026 Q3 reports
    (deadline 11-16).
  - #116 (the repair) is merged and published (11-13 evening): those two companies' reports are read ÷1,000 when every
    statement proves it, and 가치 자세히 says so in Jack's line.
  - #117 (fxHist and US splits; this PR) is merged: macro.json carries the won-per-dollar rate for every day since
    2016 (Bank of Korea 15:30 close, Jack's choice) and data.json every US split since 2016. Nothing users see changes
    until #119. Yahoo's split column unread for 6+ days is a loud warning, never a held publish (Jack, 11-13).
  - A branch dry run restores its own branch's newest cache first: a branch whose last run was before #114 has US
    details without the currency field, refetches about 777 of them, and can fail #114's currency row when Yahoo
    refuses some. Rerun once (the saved cache is then fresh). Follow-up after Wednesday: carry the currency over from
    the previous publish in that case.
  - Then screens (the part up to v19.6f is superseded by the 2026-11-15 queue at the top of § 0; the tail after v19.6f
    still stands): #119 v19.6a (after #117 is live) → #122
    v19.7a → missing US stocks → v19.7b → v19.6f (in review by Dec 1, merged by Dec 10) → v19.6c, v19.6b, v19.6e,
    v19.6g → v19.4 → v19.6h.
  - Small follow-ups, none started: the CLAUDE.md "Choices I made" line; v19.5b's US 성장 line and US minimum sizes;
    dark mode's six spots; PER, PBR and yield back for the 27 non-dollar filers from whole-company totals; Korean
    splits; the daily run split into a read-only job and a publishing job; the item 4 report and the
    dates-and-time-zones audit; the 3-year USD/KRW series' one-day lag; the 11-19 special-session row's source text
    (KRX confirmed 10:00–16:30 on 11-05).
  - Practice (Claude's, not a `CLAUDE.md` rule): a PR that finishes or starts a part of a spec also updates that
    spec's Status line in the same PR.

**Working cadence (Jack, 2026-11-07 evening — replaces the "work lean" note below where they differ). Since 11-13:
its two lanes and its app order are replaced by the 11-13 block above; its open-PR limit and question limit are
replaced by Jack's tighter ones of 11-13 (one question message a day; at most two builds open at once; above); the
test-exception bullet stands.**
Ship faster; Jack is fine with more of his plan being used.
- Two lanes in parallel. **Data lane:** B7, 자본금, unlisted preferred, the full re-read — DART-limited, as planned.
  **App lane:** v19.3b first, in a separate worktree (helpers' models and effort: `CLAUDE.md` rule 7); it never waits
  for the data lane.
- At most two app PRs open at once, each with its own fresh-eyes review, CI and live check.
- App order: v19.3b, then v19.6a + v19.7a if v19.3 Part F.1's imported-holdings shape folds into the same store
  version (one migration); otherwise v19.3c → v19.3d first and v19.6a + v19.7a right after. Then the rest in this
  order, skipping any already done: v19.3c, v19.3d, v19.3e, v19.5b, v19.6b/c, v19.7b, v19.6d, v19.4, v19.6e–h.
  Only a fix for wrong data or a broken site jumps the queue.
- Questions: batched, at most two question messages a day unless something blocks; each item yes/no with the
  recommended answer. While waiting, work the other lane.
- CLAUDE.md's 2026-11-07 test exception covers tests and test checks. Claude still asks before tightening a
  `validate_data.py` threshold or the must-have stock list, because a stricter gate can stop the daily publish.
- Every evening: one short list — what users can see now that they couldn't this morning, and the next three items
  with rough dates.

Jack is near his weekly usage limit (2026-11-04): work lean. Fresh-eyes reviewers and rounds: `CLAUDE.md` rule 7 (Jack,
2026-11-12; it replaced "One fresh-eyes review per PR (a second only for pipeline or safety-rule changes)"), with
Jack's answers on the details in the same rule. Fix every blocker and real bug the reviewers find (CLAUDE.md); small
points (style, nice-to-have, unreachable edge cases) go into the PR as follow-ups instead of another fix round (Jack,
2026-11-04). Decide engineering details yourself and list them in the PR; bring Jack only Korean wording and real
product decisions. (Replaced since 2026-11-13 by the update shape at the top of § 0: "in one short message per PR"
and "Reports 5–10 lines".) Push every branch after each step. Update this section before stopping.

**`baepsae.html` is permanent (Jack, 2026-11-05; CLAUDE.md product rules):** the address is on Jack's CV and recruiters
have it. Never delete or rename it. Since PR #42 a plain visit (no `?from=app` marker, no `#`) goes straight to 2.0
(`template.html`'s first script: `location.replace`, one separate GoatCounter count at `/baepsae/baepsae.html→app`);
every 2.0 link into the old app carries the marker (`src/links.js` `OLD_APP`), and old shared links with a `#` still
open the old app. When the old app retires, `baepsae.html` stays as a permanent redirect to 2.0 — and the old app
retires only once every tool worth keeping lives in 2.0 and old-app portfolios can be carried into 2.0 first.

**History (2026-11-04 – 11-08), kept for its details.** From here to the end of § 0, anything that says "not
merged", "waits for", "no PR yet" or "Next" is out of date: what merged is in `docs/CHANGELOG.md`, and the queue is
the newest "Queue now" at the top of § 0 (2026-11-15). Still current reference: the morning-run fallback, the outside
timer and the scheduled tasks.

**v19.1b (data for the app, branch `claude/v19.1b-data`, PR #50, not merged — Jack's top priority 2026-11-05).** Split-safe
Korean dividends, β error band, `flRan`, DART cache v2. New fields:
- data.json KR stocks: `dps3a` (dps3 on today's share basis), `dpsF` (factor per year = today's shares ÷ that year's
  basis), `divSt` (`same` · `adj` · `nc` not comparable · `nd` not derivable · `zero`), `dyt` (today's-close yield =
  dps3a[0] ÷ price, blank when unverified), `dz` (KR dividend percentile, from `dyt` only); top-level `divCheck` (counts;
  its presence switches on the new gate rows). KR and US stocks: `betaSE`, `betaN`.
- v19.1c (PR after #67): data.json US stocks `pxd` (that stock's own price date, only when its last bar is not
  `usPxDate`; its `d1` is then blank); top-level `nextPub` (the next morning new data is due) and `staleAfter` (that
  day's 14:47 KST start + 2 h), from `data/market_holidays.csv` (RUNBOOK).
- corp.json: the same dividend fields plus `cash3` (현금배당금총액, 억원), `eps3r` (company-reported EPS), `epsNi3` (the
  net income on the same basis, 억원), `epsB` (연결/별도), `flRan` (warning checks that ran), `flNa` (not applicable,
  financial companies). The existing `eps` (today's shares) is unchanged. **Visible on the first v2 publish:** 2.0's
  company page already reads `flRan` (#36), so "재무 경고 신호는 없어요" (approved text) starts showing where all four
  checks ran and none fired. Nothing else users see changes until the app PR.
- v19.1d (B7 pipeline PR): 유동비율 and 이자보상배율 run for every company whose statements have the lines, except
  financial companies (banks, insurers, brokers and financial holding companies by industry group → `flNa`).
  corp.json `flWhy` = `{"icr": "ie" | "op" | "neg" | "off"}` says why 이자보상배율 didn't run for a non-financial company: no
  interest line found, no operating profit, a negative figure, or switched off (`ICR_OFF`, Jack 2026-11-07, held until the
  v19.1f interest re-read: every non-financial company gets "off" and the app says nothing).
- v19.1f (interest re-read, DART cache v3): 이자보상배율 uses the income statement's 이자비용, or else the sum of the
  cash-flow statement's interest-paid lines (`ifrs-full_InterestPaidClassifiedAs…`, as positive amounts; never interest
  received; 신종자본증권 distributions left out while `HYBRID_INTEREST` is False). 금융비용/금융원가 are no longer read as
  interest. corp.json `flSrc` = `{"icr": "is" | "cf"}` when the check ran; `ICR_OFF` is False again, and flWhy "ie" now
  means neither line exists. Cache v2 → v3 means an empty cache: the branch dry run is one day's full-DART run and
  main's first run after the merge is the next day's.
- v19.1f income lines (2026-11-08 audit: 261 companies missing a line DART has): 매출 · 영업이익 · 순이익 · 지배주주 순이익
  are matched on income-statement rows (IS/CIS) by DART's standard code first (`ifrs-full_Revenue`,
  `dart_OperatingIncomeLoss` then `ifrs-full_ProfitLossFromOperatingActivities`, `ifrs-full_ProfitLoss`,
  `ifrs-full_ProfitLossAttributableToOwnersOfParent`), then by cleaned names (numbering, spaces, note refs removed; 매출,
  영업손익, 영업손실, 당기순손익, 연결반기순이익 …). IS beats CIS; several coded rows with different values → the one named like a
  total, else none (logged). A loss-only name with a positive figure is dropped. Owners' equity uses
  `ifrs-full_EquityAttributableToOwnersOfParent`. A statement without income lines keeps its balance-sheet values.
  Quarters use the same statement kind (CFS/OFS) as the annual report. Financial companies have no revenue line:
  corp.json `incNa: ["rev"]`.
- v19.1f EPS/BPS: EPS = owners' net income (TTM, else the annual figure; separate statements use their whole profit) ÷
  (common + listed preferred shares, `PER_SHARE_WITH_PREF`); BPS = owners' equity ÷ the same shares. EV and P/CF use the
  company market cap (common + listed preferreds, `COMPANY_CAP_WITH_PREF`). corp.json receipts `epsIn {ni, b, p, sh}`,
  `bpsIn {eq, b, sh}`, `nio3` (owners' net income, 3 years); `ni` stays the statement's total net income. data.json and
  corp.json carry `epsBasis: "owners"` (the app's temporary "PER과 EPS는 계산 방법을 고치는 중" line hides when it appears) and
  data.json `incCheck`. New gate rows (add-only): incCheck/epsBasis present, top-200 income-line coverage (WARN; FAIL floor
  `INC_TOP_FLOOR` to set from the dry run), must-haves have all three lines (FAIL), statements without income lines
  (WARN, named), receipts consistent (FAIL), must-have EPS on owners' profit with matching sign (FAIL), EPS basis
  differences (WARN), incCheck counts = receipts (FAIL).
- v19.1f owners' profit rules (after the 2026-11-08 branch dry run: 160 consolidated companies fell back to total
  profit, 93.2% owners/separate): owners' profit is read in order `code` (ProfitLossAttributableToOwnersOfParent) ·
  `alt` (…OrdinaryEquityHoldersOfParentEntity) · `cont` (continuing + discontinued owners' lines; continuing alone only
  without discontinued operations) · `sum` (an uncoded 지배… line that + the NCI profit line, or 0, equals total profit
  within ±1,000원) · `minus` (total − NCI profit) · `nci0` (no NCI line in the balance sheet or income statement, or
  exactly 0, and owners' equity absent or equal to total equity → owners = total). Evidence `nciBs`/`nciPl` is stored
  for annual and quarterly reports; `epsIn.how` / `bpsIn.how` say how each figure was read (`ofs` for separate
  statements, `total` when it stays on total profit). Total profit with no ProfitLoss row = owners' + NCI lines. A
  `dart=cache` run re-reads once only the consolidated entries saved before these rules without owners' or total profit
  (`OWN_REDO_TAG`, inside the per-run cap). 이자보상배율 below 1 is rounded down to one decimal (never "1.0").
- v19.1f review fixes (2026-11-08): '…손실(이익)' names with a positive figure are dropped like '…손실'; uncoded
  interest-paid lines need '이자(의) 지급·지출·납부' (not 지급이자 · 미지급이자) and are used only when no coded
  interest-paid line exists; pykrx PER/PBR/EPS/BPS are never used for Korean stocks (every EPS carries `epsIn`);
  `epsBasis` is "owners" only when every Korean must-have and ≥ 95% of EPS companies use owners'/separate profit,
  else "mixed" (gate FAIL); the v3 cache starts with the v2 cache's industry codes (`|company`) and corp map
  (`read_carry` / `adopt_carry`, ~2,400 calls saved); EV adds minority interest (`EV_WITH_NCI`) and takes listed
  preferred caps from the full listing (`kr_pref_caps`); 이자보상배율 pairs operating profit and interest from the same
  period (TTM with TTM, else annual with annual · `icr_inputs`); a new WARN-only gate row counts ICR warnings and
  interest sources.
- v19.1f review 2 (2026-11-08, review of 2d8d8fa + Jack's answers): ROE = owners' profit ÷ owners' equity of the same
  사업보고서 (`roe_source`, receipt `roeIn {ni, eq, b, p:"fy"}`; always annual because the app labels ROE with the report
  year and 2.0's ROE-floor rule compares by `fy`; consolidated companies without owners' lines keep the old total ÷ total
  and are named in the log and a WARN row). Statements filed in another currency (DART row `currency`, e.g. 두산밥캣 USD)
  are blanked like foreign issuers (`blank_non_won`, build_corp) and marked corp.json `stmtCur` (ISO code; the companion app
  PR claude/reread-lines reads it); dividends stay (the dividend table is in 원). 신종자본증권: owners' distributions in the 자본변동표
  (`dart_DividendToHybridBond` / `dart_InterestExpenseForHybridBond` at the owners' level) come off EPS/ROE profit and the
  `dart_HybridBonds` balance off BPS/ROE equity (KB금융 2025: 58,331.6 − 2,023.9 → 15,410원 = the filed basic EPS); when the
  statements don't say whose hybrid it is, EPS/BPS stay on the total basis (`how: "hybrid"`), never guessed. Receipts
  `epsFy` (annual EPS on today's shares) and `epsRep` (the statement's basic EPS). Interest paid coded
  `ifrs-full_FinanceCostsPaid…` counts when named 이자(의) 지급 (LG에너지솔루션). No minority interest → total profit =
  owners' profit (GMI벤처, 라이온켐텍; '비지배지분부채' is a liability, not NCI). 이자보상배율 warns only when interest was
  actually paid (이자비용 or 이자 지급액 > 0); zero interest → no warning, `flSrc.int0 = true`. A cache holding only
  carried industry codes is an empty cache (`dart_core_entries`; the workflow guard calls `dart_cache_core`), and the
  v2 file is deleted only after the financial fetch finished without a DART stop (`fetch_done`). Top-200 coverage block:
  98% approved by Jack 2026-11-08 on condition of an April back-test; no April data exists (first corp.json
  2026-08-15); off (WARN only) until Jack decides (`INC_TOP_FLOOR` None, `INC_TOP_FLOOR_APPROVED` 98; latest filed
  사업보고서, financial companies left out of 매출). 아남전자 also files in USD (2025 revenue 151M dollars). New gate rows (add-only):
  owners' share recounted from corp.json (≥ 95), data.json = corp.json for EPS·BPS·PER·PBR·ROE, PER/PBR = price ÷
  receipts, epsIn.sh = bpsIn.sh, stmtCur amounts blank (in the receipt-shape row), ROE receipts; WARN rows for PBR >
  100 (PER > 2,000 dropped: tiny-profit companies fired daily), annual EPS vs the statement's basic EPS (sign, or
  outside 0.67–1.5×), EPS owners but ROE old.
- v19.1f review 3 (delta review of 67750e2): corp.json `nio3` for hybrid companies is the owners' profit after
  신종자본증권 payouts (`hybrid_net_series`, receipt `nio3Hyb` = [당기, 전기, 전전기] payouts from the 자본변동표; a year whose
  자본변동표 column is absent is null → 자료가 없어요), so src/repair.js epsBase is on the EPS basis for "o"; for "s"
  (separate statements with hybrid) the same net series is written to `nio3`, and the app must read it instead of `ni`
  (or show {bad:true}) — companion app PR. Separate statements (or consolidated without NCI and without an owners
  split in the 자본변동표) treat the hybrid as owners' and take the payout from the top 자본변동표 column. Owners' equity
  = equity − NCI when the owners' line is missing (`_owners_eq` how `minus`). BPS takes the latest balance sheet that
  gives owners' equity exactly (code → minus → nci0 per balance sheet; the quarter first). Currency codes are
  normalised (`norm_currency`: 원/KRW → none, names → ISO, unknown → "XXX"); `stmtCur` companies carry no `fl`,
  `flRan`, `flSrc`, `flWhy`, and no `roe` / `qz` in either file (review 4: the app says it doesn't show their numbers
  yet; gate-checked). For "s" companies the app reads the netted `nio3` only when `nio3Hyb` is a list. Interest-paid `int0`: corp.json `flSrc.int0 = true`.
- How the factor is found (exact data only): shares that got the dividend = 현금배당금총액 ÷ 주당 배당금 (preferred
  shares counted from the KRX listing); issued-share ceiling = 자본금 ÷ 액면가. Today's factor must be the only clean
  candidate (1, 2, 2.5, 3, 4, 5, 10, 20, 25, 50, 100 or inverse) between those two bounds; earlier years compare the
  ceilings inside the same report (a clean change with unchanged par counts only if 자본잉여금 didn't grow, i.e. a bonus
  issue, not a rights issue). Live check 2026-11-05 (31 DART calls): all must-haves `same`; 대한제분 10:1 after the
  report → [400, 350, 250]; 리노공업 5:1 in 2025 → [800, 600, 600]; 엠앤씨솔루션 bonus ×3 → adjusted; 하이비젼시스템's
  real cut stays a cut; 한화에어로스페이스 `nc` (2024 spin-off + 2025 rights issue) but its yield ranks.
- **Jack's yes (2026-11-05):** cache-name test lines; "재무 경고 신호는 없어요"; the 12 gate rows with three changes —
  row 4 (dyt coverage) FAIL below the dry run's observed share − 10 points, WARN up to the observed share (both numbers
  in `DYT_COVER_BANDS`, placeholders 95 / 85 until Friday); row 6 FAIL only when two or more must-haves miss the
  dividend rank, one = WARN naming stock and reason; row 8's betaN floor = the pipeline's real beta minimum
  (`MIN_DAYS` 250), so new listings publish without a beta. Thresholds are confirmed against Friday's dry run before
  Saturday's merge.
- **Two-day plan (DART rule: one full-DART run per KST day; never start one 03:40–08:30 KST):** Friday = the branch dry
  run (`dry_run=true`, `dart=cache` on an empty v2 cache = that day's full-DART run, ~15,500 calls estimated, logged at
  the start; the workflow restores the v1 folder only to keep the US Yahoo-info cache). Set `DYT_COVER_BANDS` from that
  run's row 4 share and confirm every threshold with its numbers. Saturday:
  merge only after that morning's timer run has published (it still uses the v1 cache), then start one manual
  `dart=full` run on `main` the same day (not 03:40–08:30, not while a scheduled or timer run is waiting). It publishes
  the new fields and saves the first v2 cache on `main`; the next morning's timer run uses it. Until that run publishes,
  the site's data has no `divCheck`: the gate's `--live` check (Deploy, watchdog) shows one WARN row, not a failure.
- Follow-up app PR (separate): Korean dividend trend on with `dps3a` (`KR_DIV_TREND`), the exact check (`dyt`, `divSt`)
  instead of the 1.8× guard and the 1/3–3× `dpsAgrees` cross-check, 배당 감소 re-enabled for Korea on `dps3a`, the
  배당 card ranking Korean stocks on `dyt`, β with its band (Korean wording needs Jack), "재무 경고 신호는 없어요" only
  when every check is in `flRan` (or `flNa`).

**Merged 2026-11-04:** #21 v17.5.4 (KRX close + 30 min, CSAT 11/19 → 17:00; gate WARN/FAIL rows also GitHub
annotations), #22/#26 docs, #23 v19.0b visual pass, #24 v18.4.1 JSON import, #25 v18.5 missing holdings (old app),
and v19.0c (four tabs, phone) — see CHANGELOG. All checked on the live site.

**Morning data run — GitHub's timer failed on 2026-11-04:** none of the six scheduled starts fired by 07:30 KST.
Claude started one `dart=cache` run on main by hand (41731600516, published 07:43, gate PASS 94/0/0). If no scheduled
run has published by ~07:30 KST, start one `dart=cache` run on main (never a second full-DART run in a KST day; not
while a scheduled run is waiting or queued).
**2026-11-05:** GitHub's scheduled starts failed again (none of 03:47, 05:13, 06:43 had started by 07:10 KST). The
outside timer's run (41918230816, started 06:40) committed at 07:07 (data.json `publishedAt` shows the run start,
06:40): pxDate and usPxDate 2026-11-04, gate PASS with no warnings. With the timer working, the by-hand run above is
needed only when the timer's run also failed or didn't start (cron-job.org emails Jack when its call fails).

**Outside timer (v17.5.5, set up by Jack 2026-11-04):** cron-job.org (Jack's account) job "뱁새 morning data run"
sends `POST https://api.github.com/repos/jacksungjinlee/baepsae/actions/workflows/update-data.yml/dispatches` Tue–Sat
at 06:40, time zone Asia/Tokyo (same clock as Seoul, no summer time), body `{"ref":"main","inputs":{"timer":"true"}}`,
headers `Accept`, `Authorization`, `X-GitHub-Api-Version` and `Content-Type: application/json`, and emails Jack when
it fails. Test run 2026-11-04 23:54 KST: GitHub answered 204 and run 41852250682 stopped early as intended. A timer run
follows the scheduled-run rules: it stops early when today's data is already published, waits for the US close,
checks out the latest main, stops on an empty DART cache, and accepts only main + `dart=cache`. The token is Jack's
fine-grained token "baepsae morning timer": only the baepsae repo, only Actions (read and write), no expiry. It lives
only in cron-job.org (never in a chat, the repo or a log).
- To revoke at any time: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens →
  the token → Delete.
- The token can start *any* run (like Jack's Run-workflow button, e.g. a manual `dart=full`), cancel runs or delete
  caches — the workflow can't tell the holder apart from Jack. That's why it stays only in cron-job.org.
- Timer runs share the live concurrency group with scheduled and manual runs (1 running + 1 pending; a newer queued
  run cancels the older pending one). Don't queue a manual run while a scheduled **or timer** run is waiting or queued.

**v17.6 (started 2026-11-05 01:30 KST): PR #34, parts 1 (watchdog), 2 (CI), 3a (deploy + `data` branch), 4
(`docs/RUNBOOK.md`). Waits for Jack's "merge".** New: `.github/workflows/ci.yml` (job `ci`), `deploy.yml` ("Deploy"),
`watchdog.yml` ("Watchdog") + `watchdog.py`; `tools/push_data_branch.sh` (the daily run's new last step
`data 브랜치에 올리기`: the same four files to the `data` branch, only with the gate's sha256 receipt (and, since
2026-11-12, the screen check's receipt — the browser check between the gate and the commit, `docs/RUNBOOK.md`), never forced; the
first live run after the merge creates the branch), `tools/assemble_site.py`, `tools/build_tag.py` (build tag only when
Deploy builds). `already_published.py` reads the `data` branch (falls back to `main` only while it doesn't exist). The
daily run still commits to `main` as before (3a). Deploy's automatic triggers act only once Pages → Source is "GitHub
Actions" (Jack's click, after the `data` branch exists and one manual Deploy was green); a deliberate deviation from the
spec's "manual only", explained in the PR. `ci` is green on the PR (run 41875398590, 6 min 42 s) and went red on the
deliberately broken test PR #35 (closed; its branch `claude/v17.6-ci-proof` still needs deleting — the session's git proxy
refused). Branch dry run 41872130591 (`dart=off`): only the DART rows failed, as expected. One existing test changed and
needs Jack's OK: `tests/smoke_v2.py` waits up to 3 s for the PC search box to empty (a CI timing race). Fresh-eyes
review done (no blocker; five fixes: daily watchdog for healthchecks.io, live `data.json` = published copy, no-op
deploys skipped in the run check, exact `refs/heads/data`, `/fail` ping before the issue and a stripped ping URL).
Branch dry run 41935114973 (`dart=cache`, 2026-11-05 08:37 KST): gate PASS 95/0/0, cache hit, 816 DART calls.
**Jack, 2026-11-05: yes to the test changes and the deviations; his chat reviewed it (no blocker); "fix the conflict,
then merge".** Before he switches the Pages setting: one manual Deploy must prove it works. Alerts must reach him by
email or phone through healthchecks.io — he doesn't read GitHub, so the issue alone is not enough. Planned follow-ups:
(a) a PR that stops committing data to `main` after the switch (3b); (b) before price history lands, the `data` branch
keeps only recent versions — rewriting the `data` branch's history is fine (Jack), only `main`'s is protected.
After the merge: the steps in PR #34 (first live run creates `data`, watchdog selftest, manual Deploy, Jack's
healthchecks.io + Pages clicks), then 3b, then 3c. The 09:13 check needs no change until 3b (it keys on the step
`커밋 & 푸시`, unchanged).

**Next, in Jack's order (2026-11-04): 자동 settings fix (v18.6, with the 타임머신 line stopping at the low point) → v19.0d (PC) → v17.6:**
1. **09:13 check reports gate warnings:** done 2026-11-04 (Jack allowed the change).
2. **Outside timer:** workflow change merged (v17.5.5); Jack set up cron-job.org 2026-11-04 (above). Check that the
   next morning's run came from the timer (event workflow_dispatch, ~06:40 KST).
3. **v19.0d (PC layout):** PR #30 (left menu, top search with "/", two columns on 홈 and 시장). After it: **v17.6**.
   Open for Jack: a "내 포트폴리오" list in the left menu (heading not approved yet).
4. **Old app, 자동 settings:** done in v18.6 (#29). Jack decided 2026-11-04: 새로 시작하기 (and a file with no readable
   settings) starts from defaults + today's values, not the previous portfolio's settings — v18.6.1.
5. **Old app, saved portfolio that can't be read (v18.6.2):** it no longer opens (first screen stays, the stored text is
   kept, console warning with the slot id and reason) and an alert says so in the current language — Jack approved his
   wording 2026-11-05: "이 포트폴리오를 열지 못했어요. 저장된 내용은 지우지 않고 그대로 두었어요." / "We couldn't open this
   portfolio. Its saved data has been left as it is." (`T_SLOT_FAIL` in `src/detail.jsx`, `SLOT_FAIL` in
   `tests/smoke_app.py`).
6. **Company pages (Korea and US) for 2.0:** spec merged as #33 (`docs/tasks/v19.1-company-page.md`). **v19.1a is PR
   #36** (branch `claude/v19.1a-company`), built overnight 2026-11-05 and **not merged**: it waits for Jack's yes on
   179 proposed lines (`docs/tasks/v18.3-new-strings-pending.md` § v19.1a on that branch; each is `null` until approved),
   its test and CLAUDE.md changes, and the decisions listed in the PR (β band: single stocks have none, so no β number
   until the pipeline saves the standard error or the return count; logo provider; per-stock rule toggles; ⓘ → old
   용어 사전; the Won-first CLAUDE.md wording; `flRan` in corp.json so "재무 경고 신호는 없어요" can show).
7. **Logo test (v19.1 Part L):** prepared on branch `claude/v19.1-logo-test` (`tools/logo_test/`, steps for Jack in
   `KEYS.md`). Needs Jack's free publishable keys (Brandfetch client ID, logo.dev `pk_…`); never accept a secret
   (`sk_…`) key. **Both providers' terms forbid scripted fetching of their logo images** (README § Provider terms), so
   a full automated run is a grey area: Jack chooses between a small sample viewed in a normal browser, asking the
   providers for a coverage check, or logo.dev alone. Don't run anything that works around a provider's block.
8. **Price history (1 year of daily closes, report only):** proposal sent to Jack 2026-11-05 — one file per stock
   (~2 KB, ~5 MB total), only in v17.6's deployed copy (not in git), split-adjusted only, gate checks; after v17.6.
9. **v17.6 is PR #34** (branch `claude/v17.6-never-again`): CI on every PR, deploy from main + `data` branch, watchdog.
   `ci` green; the `dart=off` dry run failed at the gate as it should (no company data → PER/PBR/ROE 0%); the
   `dry_run=true dart=cache` run 41935114973 (2026-11-05 08:37 KST) passed: gate PASS 95/0/0, cache hit, 816 DART
   calls (comment "Dry run with saved DART data" on the PR). Jack said yes and "merge" on 2026-11-05 (see the v17.6
   paragraph above for his conditions). Jack must also create the
   healthchecks.io check and the `HC_PING_URL` secret, and later switch Pages to GitHub Actions and add the
   protect-main ruleset (steps in the PR). The leftover branch `claude/v17.6-ci-proof` (test PR #35) couldn't be
   deleted from the session (git proxy); delete it when possible.

**v19.1a (company page, Korea + US):** branch `claude/v19.1a-company`, no PR yet. Status: built and tested (pytest,
all smokes, proposal-filled smoke run too); waiting for Jack's 「새 문구」 (every company-page string is a proposal:
`docs/tasks/v18.3-new-strings-pending.md` § v19.1a) and his answers on the beta band, the US dividend/growth wording and
logos (Part L). Until the strings are approved the page shows only approved words (no tab bar, few tiles). Then: fill
the values, open the PR (fresh-eyes review), merge.

**타임머신 (old app):** Jack decided 2026-11-04 — stop the chart line at the low point (part of v18.6).

**v19.0c follow-ups (from its review):** dead first back press after reloading with the menu open; the screen
behind 소개 isn't kept mounted for build / 왜 움직였나 (typed RecordSheet input would be lost); 포트폴리오에서 빼기
has no undo; 시장 tile change uses the last two idxHist rows (a gap would show a multi-day change); the per-tab error
boundary isn't smoke-tested; `styleguide.html` mockup examples still say 내 덱 (needs a CSV-backed test change).

**Scheduled tasks:** 09:13 KST Tue–Sat read-only data check (`trig_01BGc9nmRuJcg6dsL1wNZX5E`; until 11/11 it reports
the publish time). 2026-11-13 10:17 KST: check KRX's CSAT-day hours and fix the 11-19 row before 11/18
(`trig_01JyjjakbFVQ4GPSanbsqESX`). Yearly: add next year's CSAT row before 1 September (gate blocks from 1 November).

**Later:** the 08:30 "latest close isn't in yet" line (holiday-aware; propose wording); old-app: 기업분석 "X% 보유"
counts missing holdings; page ② is 445 px wide on a 390 px phone; CSV order sheet doesn't quote names with commas;
stock edits don't travel in the backup.

---

## 1. Product

**Purpose.** An honest, non-speculative investing tool for Korean retail investors. It helps them see what they own,
how their holdings move together, and what today's prices assume — without telling them what to buy.

**Target user (single persona, decided):** 1–3년차 실전 투자자 — people who already invest real money,
know basic terms, and get burned by concentration, hype and not knowing what they hold.

**How Jack works.** Design and decisions in claude.ai chat (the Claude desktop app). Engineering in Claude Code
Cloud sessions from the desktop app's Code tab. No local dev setup on his PC, and **he does not open GitHub**.

**Who runs GitHub (standing rule since 2026-10-31).** Claude Code owns the whole GitHub process: branches, pull
requests, merging, starting and watching workflow runs, and rollbacks. It merges on its own only when build, `pytest`,
the phone-size smoke test (and, after v17.6, the `ci` check) pass, the fresh-eyes review is done and fixed, pipeline
changes have a green `dry_run` with the validation summary in the PR, and no safety rule is loosened. Since
2026-11-20 it decides anything the rules and approved specs already cover and lists those decisions under **Choices I
made** in the PR. It asks Jack, with a short yes/no question in the chat, only about new Korean wording (showing the
「새 문구」 table), loosening a safety check or adding one that can stop the publish, changes to what users can do, and
money, accounts or outside services, with a few clarifications (details in `CLAUDE.md`, including the 12-hour
go-ahead). (Until 11-20 it also asked about every `CLAUDE.md`, threshold or `tests/` change; v17.5 and v17.6 also waited
for his claude.ai chat.) After every merge it
watches the next run, checks the live site, reverts at once if something is wrong, and sends Jack a 3–6 line summary.
`docs/CHANGELOG.md` has one line per merge. The full rule, including what is never allowed, is in `CLAUDE.md`
§ GitHub process.

**Status.** Not launched. Shared with a handful of friends. The link is on Jack's CV, and an English demo mode exists
for job interviews outside Korea. Real usage numbers are too small to drive decisions yet.

**Brand** (Jack, 2026-11-03). Live since v19.0a (PR #18): name 뱁새 (the vinous-throated parrotbill, from the proverb
뱁새가 황새 따라가다 가랑이 찢어진다); descriptor "내 기준으로 만드는 포트폴리오"; catchphrase "철새처럼 옮겨 다니지 않는
투자", which replaced "황새 말고, 내 걸음으로" everywhere; the maker's credit lives on the 소개 page and footers show only the
disclaimer and a 소개 link. The disclaimer (Jack, 2026-11-08) is
"뱁새의 정보는 투자 자문이나 투자 권유가 아닙니다. 모든 투자 판단과 책임은 본인에게 있습니다." (old app in English: "Not investment
advice or a solicitation to invest. All investment decisions and responsibility are yours."). The product never calls 뱁새
"교육용" (share card, 소개 and link preview included); `tests/test_footer.py` fails if the word comes back. The design
references in `docs/design/*/reference/` still show the earlier footer: ignore it, CLAUDE.md's line wins. Mascot 뱁이
(Jack's own art; where it may appear: CLAUDE.md — the old app keeps its existing 뱁이 pictures until each tool moves to
2.0). Colours: ink `#1C2B45`; page background `#F5F3EF` in 2.0 (`src/ui/tokens.js`)
and `#FAF8F5` in the old app (`src/tokens.js`). Status colours are `watch` (amber `#8A5A00` on `#FFF3D6`) and `broken`
(white on navy) — never red or blue, which mean price direction in Korea (v18.1). **v19.0b targets, not live yet:**
apricot `#C97757` marks data only (target-weight line, rank numbers, factor dots, "my portfolio" in charts) — not alerts,
buttons, icons, selection or the focus ring (today 2.0 still uses apricot on the alert hero and the focus outline);
selection states use `#F2F0EB` with a 3 px navy edge; icons become Phosphor duotone in navy with a slate fill (vendored,
MIT). Until then 2.0 uses the v18.1 icon set in `src/ui/icons.jsx`, and the old app keeps its own stroke icons in
`src/icons.jsx`. **Zero emoji anywhere**, always.

**Repo/URL history.** GitHub username was renamed `pewpewmfer` → `jacksungjinlee` in v15.2. All URLs in code were
migrated. The old Pages URL is dead.

## 2. What the app does (by tab)

Bottom tabs on mobile (<880px), top tabs on desktop: 포트폴리오 · 기업분석 · 공시·수급 · 금리·원자재 · 정보.

**포트폴리오 (`shell.jsx` gate → `simple.jsx` / `detail.jsx`)**
- Gate ("hook ladder"): "내 종목, 괜찮은 걸까요?" search → 5-second ScoreCard (PER vs industry median, price-vs-earnings
  gap line, financial flags, "사실의 요약일 뿐" footer) → CTA into full diagnosis → three doors:
  30초 진단 (quick, balanced default profile), 성향 테스트로 시작 (`simple.jsx`), 차근차근 만들기 (`detail.jsx`).
- Detail studio: 11-question risk profile, holdings across blocks (KR stocks, US stocks, 금·은, bond ETFs), a
  **block-correlation engine** (correlations and vols per block come from the pipeline's `settings`), health score,
  concentration, tax layer (incl. 15.4% on bond-ETF distributions), stress tests, factor-tilt card, saved slots,
  share card (PNG + link `?ref=card`).
- `BASE_STOCKS` in `detail.jsx` is an **embedded fallback list with 2025-era prices** (삼성전자 78,000원). It is used
  silently when `data.json` fails to load. See § 6 — this must become visible.

**기업분석 (`corp.jsx`, `guides.jsx`)** — Korean-listed only (DART-based; intentional).
- Sub-views: 시장 지도 (cap-weighted treemap, sector distributions) · 기업 찾기 · 조건 검색 · 산업 읽는 법.
- Company page: 01 투자지표 (TTM multiples vs industry quartiles + 5-factor strip) · 02 3개년 실적 · 03 업종 내 위치 ·
  04 주가는 무엇으로 움직였나 (3-year price return = EPS change × PER change, with receipts in 원 and 배) ·
  05 reverse DCF. Compare up to 4 companies.
- 조건 검색: 20 selectable columns (가치/수익성/성과/위험/팩터 groups), sector and cap filters, factor chips
  (전체 / 상위 50% / 30% / 10%, AND-combined), sortable, presets saved to localStorage (max 12), mobile card view with
  sort selector.
- Factors (percentile 0–100; **bug until v17.5: KR and US are ranked together with mixed units**): 가치 `vz` (PBR 낮은 순), 퀄리티 `qz` (ROE 높은 순), 모멘텀 `mz`
  (12개월 수익률 순), 규모 `pz` (시가총액 작은 순), 저변동 `lz` (변동성 낮은 순). Baepsae never ships preset combos.
- 산업 읽는 법: 8 guides (semi, bank, bio, ship, defense, battery, platform, media). Anatomy: 세 줄 요약 → 성격 태그 →
  수익 방정식 (+movers, operating-leverage note) → 판의 구조 (value chain) → 스위치 cards → 사이클 strip (semi/ship/battery) →
  본문 → 지표 → 함정 → 사기 전에 물을 세 가지. Batch 2 (12 more sectors) waits on Jack's approval of this template.

**공시·수급 (`disc.jsx`)** — insider trades (DART 임원·주요주주 소유보고, last 90 days) and 국민연금 holdings changes.

**금리·원자재 (`macro.jsx`)** — 기본: 국고채 수익률 곡선 (now vs 1y ago), 장단기 금리차 (KR/US), 금·은·WTI, duration
playground. 심화 「채권·환율 연구실」: 주요국 10년물 (KR/US/JP/DE), 만기별 한·미 금리 1/3/5/10y + 환헤지 비용,
신용 스프레드 (회사채 AA− − 국고 3년, 3-year gauge). The duration card and the 심화 hedge-cost and credit cards end with a
「그래서 나는?」 box (`MyBox`) that links the data to the user's own decision.
The Brazil-bond case was deliberately deleted.

**정보 (`info.jsx`)** — about (+ recruiter-facing English paragraph), 용어 사전 (70 terms, searchable), Tally feedback
form, terms. `SUPPORT_EMAIL_HERE` is still a placeholder (Jack deferred).

**English demo mode.** EN/한국어 toggle in the masthead (localStorage `baepsae_lang`). Gate, ScoreCard, tab names and
the whole portfolio studio are bilingual. Analysis tabs show a "Korean-only for now" banner. Scope is interview demos —
full bilingual is parked.

**Navigation.** Tab, mode, sub-view and overlay changes push browser history (`NAV`, `navPush`, `navInstall` in
`tokens.js`), so back buttons and the iOS edge swipe work. In installed (standalone) mode a "뒤로" button appears.

**Install.** "홈 화면에 추가" button: Android uses `beforeinstallprompt`. iOS gets a 2-step sheet, because Apple doesn't
allow web pages to install themselves. KakaoTalk's in-app browser is told to open another browser first.

**Analytics.** GoatCounter, site code `baepsae`. Custom events: `gate-score`, `gate-diag`, `gate-quick`, `gate-test`,
`gate-detail`, `gate-corp`, `pwa-install`, `lang-ko/en`. `?dev=1` excludes the current browser (`?dev=0` undoes).

**localStorage keys.** `baepsae_lang`, `baepsae_pwa_hint`, `baepsae_screens`, `baepsae_v9_seen`, `baepsae_v10_slots`,
`baepsae_v11_simple`, `baepsae_v12_dcf`. Don't rename existing keys — users would lose saved work.

## 3. Data pipeline (`fetch_data.py`)

Scheduled runs (v17.5.3, PR #19, merged 2026-11-03 22:24 KST; first morning 2026-11-04): GitHub started the old single
06:30 KST run 2¼–5½ hours late all October (never before 08:44 KST; see § 5 for what late runs once caused). Now the run
is triggered seven times — 03:47, 05:13, 06:43, 08:17 KST (Tue–Sat) and 10:53, 13:37, 14:47 KST (Mon–Sat; 14:47 added
in v19.1c after two Yahoo gaps around 10:00–10:40 KST) — and a first job
(`already_published.py`, scheduled runs only; manual runs skip it) decides:
- a run that starts in the hours before a US trading day's close is final (New York 12:00–16:30; the close is final at
  16:30 New York = 06:30 KST in winter, 05:30 in summer) waits until 16:33 New York and then re-checks. If the close is
  more than 170 minutes away it doesn't wait at all: it ends as skipped and a later trigger does the work. No waiting on
  US holidays;
- a run ends before any download or DART call when main's `data.json` already holds the last KRX trading day before
  today and the last US trading day whose close is final (trading calendars from the gate's own sources: Naver KOSPI and
  Yahoo ^KS11, Yahoo ^GSPC). If the calendars can't be read it falls back to weekdays and says so loudly; if only one
  KOSPI source answers it never skips. (Since v17.6 / PR #34 it reads the `data` branch, and `main` only while that branch doesn't exist yet.)
Runs share one queue (`concurrency`), so two never publish at once. A scheduled run never starts DART from an empty,
unreadable or old-format cache: it stops loudly, and the day's one full-DART run is started by hand. The cache holds
parsed values, so a parse fix normally means a full re-read; v19.1e instead re-reads once only the annual statements saved
without a capital line (`DART_REDO_PER_RUN` = 800 per run, marked `rp: cap1`; a "not found" answer keeps the old entry and waits `DART_RETRY_DAYS`; logged as "자본금 다시 읽기 대상 N건" at the start and "남은 N건" at the end). v19.1g fetches DART's share-count report (`stockTotqySttus`, tag STK) only for companies
whose dividend table shows more paid preferred classes than listed preferreds (about 30, one cached call each). Before starting a
manual live run, check the run list: don't start one while a scheduled run is in progress, waiting or queued (a newer
trigger cancels a queued manual run), and confirm it actually started. Don't merge pipeline PRs while a scheduled run is
waiting. A daily scheduled check at 09:13 KST (Tue–Sat) confirms the live site has the last trading day and tells Jack
if not; it has no GitHub write access, so if a run is needed it tells Jack to ask Claude. Python 3.11. Secrets
`DART_API_KEY` (OpenDART, ~20,000 calls/day quota) and `ECOS_API_KEY` (한국은행 ECOS). The workflow commits the four
JSON files to `main` as `baepsae-bot`, with `git pull --rebase` before push (avoids a race with manual uploads).

`main()` order:
1. `fetch_rf` — risk-free rate.
2. `fetch_korea` — since v17.4.1/v17.5: the latest **final** listing file before today (KST) from `fdr_krx_data_cache`
   (≥ 90% market caps filled, last commit at or after **that day's KRX close + 30 min** — 16:00 KST on a normal day;
   later on special sessions listed in `data/krx_special_sessions.csv`, e.g. 17:00 on CSAT day (v17.5.4))
   → top 2,500 by market cap (`MAX_KR`) → sector
   descriptions (`KRX-DESC`) → KOSPI index → per-stock prices `fdr.DataReader(code)` (8 threads), every series cut at
   `pxDate` with the `pxDate` bar set to the **official close = `Marcap ÷ Stocks`** → `enrich_with_dart` (annual,
   dividends, quarterly → TTM; cached in `.dart-cache`; 5 threads) → `fill_multiples`. (Before v17.4.1 it used
   `fdr.StockListing("KRX")`, which read the pre-market file — see § 5.)
   - **Yearly chore:** add next year's CSAT row (date and hours from KRX's notice, with the source) to
     `data/krx_special_sessions.csv` before 1 September. The gate warns from 1 September and **blocks every publish
     from 1 November** while it is missing (Jack, 2026-11-04). Its `--live` mode runs the same row, so v17.6's live
     check will fail too. Gate warnings and failures are also GitHub annotations, which the 09:13 KST daily check reads.
3. `fetch_us` — S&P 500 (Wikipedia) + NASDAQ (Naver listing, first 400) + `EXTRA_US`; yfinance prices (10 threads);
   auto Korean descriptions via `us_desc()`.
4. `fetch_bonds` — 8 bond ETFs configured (`153130 114260 148070 439870 273130 305080 453850 304660`), verified by
   name keywords and vol < 30%. **Only 7 have ever been published:** 304660's real name fails its keyword check.
5. Block correlations/vols → `settings`. `add_percentiles` (factors). → **`data.json`**
6. `build_corp` → **`corp.json`** (companies, sector quartiles, market summary).
7. `fetch_macro` (ECOS 817Y002 items resolved dynamically incl. 회사채 AA−; FRED via FDR: DGS1/3/5/10/2, JP/DE 10y,
   WTI; yfinance gold/silver) → **`macro.json`**.
8. `fetch_disclosures` (DART elestock, 90 days, ≤1,200 detail calls per run) + NPS → **`disc.json`**.

TTM method: TTM = last annual + this year's YTD − last year's same-period YTD (flows). Balance sheet uses the latest
quarter. The current quarter is probed once via 삼성전자 (11014 → 11012 → 11013). The log line
`· TTM 합성 성공: N / M 기업` reports coverage.

Units in JSON (from v17.5): `cap` in 조원 for **both** markets (US converted at the run's `fx`), `val` in 억원,
`price` in 원 (KR, = `Marcap ÷ Stocks`, the official KRX close) or USD (US), percentages as numbers. Top-level `pxDate`
(KR price date = official close date), `ksDate`, `usPxDate`, `publishedAt` (KST run timestamp), `units`.

**`g3` means different things per market until v19.2 makes them the same** (Jack, 2026-11-05). Korea: revenue growth from the latest 사업보고서, the **2-year average a year** ((당기 ÷ 전전기)^0.5 − 1) when this year's and the year before last's revenue are both positive, otherwise **1 year** (당기 ÷ 전기 − 1) when this year's is non-zero and last year's is positive, e.g. when the year before last is missing (`parse_dart_list`; corp.json `rev` lets the apps tell which: 2.0 `engine.growthBasis`, old app `data.js krGrowthBasis`). US: Yahoo's `revenueGrowth`, the **latest quarter vs the same quarter a year before**. Never call either "3년"/"3y", never compare the two, and label each by how it was calculated: 2.0 "매출 증가율 (최근 2년 연평균)" / "(최근 1년)" / "최근 분기 매출, 1년 전보다"; old app "매출성장(최근 2년 연평균)" / "매출성장(최근 1년)" / "매출성장(최근 분기, 1년 전 대비)". The sector growth in corp.json (`sectors[].g`) is the 2-year average of summed revenue.

**The listing file's `Close` column is not the official close** in the evening versions: after ~16:00 it is replaced by
an after-hours (Nextrade) price, while `Marcap` stays at the official close × listed shares. Verified on 2026-10-27~30:
the next day's file (and Naver) measure the day's change from `Marcap ÷ Stocks`, not from `Close`. In the 19:58 version
of 10/29 only 27.5% of `Close` values match `Marcap ÷ Stocks` within 0.1%.

## 4. Frontend build

`npm install && bash build.sh` → esbuild bundles `src/main.jsx` (minified, React 18) → injected into `template.html`
→ `baepsae.html` (~640 KB). On 2026-10-30, a rebuild from `src/` produced a 637 KB file vs the deployed 688 KB, with
all v17.4 features present. The difference is most likely tool versions. First job of v17.5: pin versions and confirm
behavior with the smoke test.

Data is fetched with `fetch("./x.json", {cache: "no-store"})` in `shell.jsx` (gate), `detail.jsx`, `corp.jsx`,
`disc.jsx`, `macro.jsx`. Each loader currently **swallows errors** and returns empty data.

## 5. Incident report — data silently broken since 2026-09-29 (diagnosed 2026-10-30)

**Symptoms Jack saw:** first-screen search finds nothing; prices and betas "not updating for months".

**Findings (all verified):**
1. **Root cause — reading the pre-market file.** `fdr.StockListing("KRX")` asks KRX for the latest workday, then
   downloads `FinanceData/fdr_krx_data_cache/.../listing/krx/{date}.csv`. That volunteer project now writes each day's
   file three times: ~05:00 KST (**pre-market, all `Marcap`/`Amount`/`Close` blank**), ~13:00 (intraday), ~19:00
   (final). Our job runs ~06:30 KST, after KRX already reports "today", so it reads the blank pre-market file. Verified
   on `2026-10-29.csv`: 05:44 version has 0 / 2,872 market caps; the 13:19 and 19:58 versions have all 2,872.
   (Correction 2026-10-31: in the evening versions `Close` is an after-hours price; the official close is
   `Marcap ÷ Stocks` — see § 3. The final commit also lands before 18:00 on about 1 trading day in 5 — 29 of 138 since
   April, between 16:13 and 17:59 — so v17.5 treats a file as final from 16:00 KST. v17.5.4: from the day's close + 30 min,
   read from `data/krx_special_sessions.csv` — the CSAT day closes at 16:30, so it needs 17:00.)
2. **Consequences:**
   - `cap = float(row["Marcap"] or 0)` stays NaN (NaN is truthy), and the same happens to `val` → NaN written to
     JSON → browsers' `JSON.parse` rejects the entire file → the gate and 기업분석 show nothing.
   - Sorting by blank caps leaves the file's alphabetical order, so `MAX_KR` kept the **first 2,500 names
     alphabetically**. Everything after "파트론" is missing, including 현대차, 한국전력, 하나금융지주,
     한화에어로스페이스, 하이브 and 한화오션. `popular` is alphabetical too.
   - `pz` (규모 factor) is missing.
   - Days that came out clean (10/9, 10/10, 10/17) were holidays or days when "latest workday" pointed at a finished
     day. (Separately, the 10/9–10/10 runs lacked DART fields — worth checking in logs.)
3. **Silent fallback in the app.** The portfolio studio falls back to `BASE_STOCKS` (2025 prices) without any notice.
   The gate shows "찾지 못했어요" instead of "couldn't load".
4. **Time-outs.** Runs take ~43 min or ~2h20m (bimodal); `timeout-minutes: 150` cancelled 5 of the last ~19 runs
   (10/15, 10/21, 10/22, 10/23, 10/29). Likely the DART calls (≈2,500 companies × several calls daily).
   (Confirmed 2026-10-31: over 40 runs since 9/5, 15 were cancelled at 150 min. The long runs are slow DART: on 10/28
   the DART phase alone took 2h03m, against 33 min on 10/30. Real start times were 08:09–11:39 KST.)
5. **Stale service worker on old devices.** The v10 `sw.js` (still in the repo, no longer registered by the page)
   serves non-`data.json` JSON **cache-first forever** (`corp.json`, `macro.json`, `disc.json`). Devices that visited in
   July–August keep a frozen copy until a changed `sw.js` replaces it.
6. **No alarm.** The workflow went green while publishing unusable data. Nobody noticed for a month.

Found in the second-pass review (each one checked against git history and the source data):

7. **Korean prices are not closing prices.** Runs start during market hours, and the Naver price series includes the
   forming day and after-hours trades. The 10/28 run published 삼성전자 at 234,000원, while the official closes were
   **222,000원 (10/27) and 242,000원 (10/28)**. Only **15.8%** of KR prices published that day equal an official close of
   either day. Beta, vol and returns are computed on the same mixed-day series.
   (Correction 2026-10-31: an earlier version of this report gave the official closes as 222,500원 and 244,000원 and
   the match rate as ~10%. Those two prices are the listing file's evening `Close` column, which is an after-hours
   price; the official close is `Marcap ÷ Stocks` (§ 3). Naver's daily close is also the after-hours price: on 10/30
   it differed from the official close for 2,131 of 2,500 stocks.)
8. **US prices often one session stale.** yfinance's `end` is exclusive and the code passes `date.today()` (UTC).
9. **Risk-free rate stuck.** `settings.rf` = 3.0 = `RF_FALLBACK` in every snapshot since August. It feeds Sharpe,
   alpha and the user's default. (Cause: Yahoo returns 404 for `KR10YT=RR`. v17.5 reads 국고채 10년 from ECOS.)
10. **Rates tab never worked.** `macro.json` curve/tenor/credit = null in every snapshot since August, despite the ECOS
    key. The tab tells users to go to GitHub Settings. (Cause: a code bug, not the key — `sorted()` over a list mixing
    the "corp" key with maturity numbers crashed every run: `'<' not supported between instances of 'str' and 'int'`.)
11. **Unit and market mixing.** US `cap` is USD/1e12 vs KR 조원; factors are ranked over KR + US together.
12. **Embedded prices leak.** `mergeStocks` appends unmatched `BASE_STOCKS` entries. 금현물 (04020000), 069500, 379800,
    132030 and 144600 are never in `data.json`, so they always show 2025-era prices, unlabeled.
13. **Dead last-resort fallback.** `OUT_DATA` is undefined (fetch_data.py:1094); that path would crash.
14. **Bonds.** 7 published, not 8 (see § 3).
15. **Due 2026-11-16:** the 3Q TTM switch is probed only on 삼성전자 and applied to all companies, with no per-company
    fallback. Late filers would lose TTM.

Fix plan: `docs/tasks/v17.5-pipeline-safety.md` (correctness and gate), then `docs/tasks/v17.6-never-again.md`
(monitoring, tests on every change, protected `main`).

## 6. Known debts (not urgent unless a task says so)

- `BASE_STOCKS` embedded snapshot — v17.5 labels every non-live item and adds the missing codes to the pipeline.
  Removing it entirely is a later decision.
- Repo growth from daily ~3.6 MB data commits on `main` → fixed by the data/code split in v17.6.
- GitHub disables scheduled workflows after 60 days without repo activity → v17.6 verifies and adds a keep-alive if needed; the watchdog alerts if updates stop.
- US fundamentals (PER, dividend) are best-effort. Prices, risk stats and descriptions are reliable.
- Bundle size ~640 KB single file. Revisit in the v18 design pass.
- `SUPPORT_EMAIL_HERE` placeholder in `info.jsx`.
- Legacy Korean copy written before the voice guide (v16.2) hasn't been fully re-audited.
- `sample_corp.json` (render-test fixture from the old chat sandbox) is not in the repo. Build new fixtures in `tests/`.

## 7. Locked decisions (do not reopen without Jack)

- Single persona: 1–3년차 실전 투자자.
- Honest framing: no 추천/목표주가/수익률 약속. "가격에 담긴 가정" language.
- Long-only. No leverage, shorting or options features.
- Verdict-first cards. Receipts for computed numbers. 「그래서 나는?」 (`MyBox`) is the standard way to link a data card
  to the user's own decision. Use it on new macro or data cards.
- Voice guide `docs/BAEPSAE_VOICE.md` (persona 숫자에 밝은 친한 선배; banned words 몸통·잣대·항등식·빌려온 열광).
  Every release lists new copy verbatim for Jack's veto.
- Factor labels: formal name + basis line (B안). Plain verbs (싸다/잘 번다) were rejected as unprofessional.
- 기업분석 is KR-only. US names get an explicit notice pointing to the portfolio tab.
- Brazil-bond case deleted. 심화 is a sub-tab of 금리·원자재, not a 6th top tab (the mobile bar holds 5).
- Mascot art is Jack's own; never redraw. 9 poses mapped in `BAEPI_POSES`
  (happy 1, search/worried 2, data 3, think 4, cheer 5, grow 6, work 7, care 8, sleep 9).
- Mobile and web stay one responsive codebase. A native app was considered and rejected (2026-10-30): it doesn't
  fix the data pipeline, adds store costs and review, and kills the shareable link.

## 8. Roadmap

1. **v17.5 stop the damage** (now) — `docs/tasks/v17.5-pipeline-safety.md`. Correct listing, publication gate, loud app
   failures, service-worker eviction.
2. **v17.6 never again** (after v19.0c and its PC part v19.0d, Jack 2026-11-04) — `docs/tasks/v17.6-never-again.md`. Independent watchdog on the live site, CI on
   every PR, data/code split with a protected `main`, DART cache, runbook.
3. **Jack's redesign ideas** from building his own "Anti-AI" portfolio. Background: user feedback said 뱁새 is hard
   and complex, and that adding every stock by hand is tedious. The direction under discussion is to keep it
   rule-based, let users start from an investment thesis or theme, design the portfolio from that, and explain risks
   and opportunities simply. **Not specified yet** — it will arrive as a spec from claude.ai chat. Don't start it on
   your own.
4. Content freeze → "다 요리됐나" audit (every card: conclusion first? context attached? linked to my money?).
5. v18 design/UX pass (navigation logic, hierarchy, spacing, color, empty/loading states, bundle size, accessibility).
6. v19 launch-readiness discussion (약관 legal review, for-profit vs non-profit, organic vs small campaign).

Parked: bonds deep-dive extras (international bond ETFs, FX simulator, 60/40 walk), 추적 + DCA retention loop,
배당 연구실, full English bilingual, batch-2/3 industry guides.

## 9. Domain grounding

Jack's INSEAD course knowledge packs (Investment & Asset Management, Financial Markets Valuation, UDJ statistics,
Hedge Funds) live in his claude.ai Project, not in this repo. Ask him for excerpts if a task needs them.
