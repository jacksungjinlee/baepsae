# 뱁새 — Handoff to Claude Code (2026-10-30)

This document carries everything decided in ~3 months of building 뱁새 in claude.ai chat (v9 → v17.4,
2026-07-30 → 2026-08-20, then a pause). Read it once fully. `CLAUDE.md` holds the rules; this file holds the context.

---

## 0. Current state and next steps (updated 2026-11-13 14:18 KST — read this first)

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
- **Queue now (2026-11-13 14:18 KST; every merging PR updates this):**
  - Live: #107, #111 (gate rows), #120 v19.5b (홈 종목 순위), #121 v19.6d dark mode (☰ → 화면 모드), #115 (the deploy
    check: every code deploy runs the daily run's three real-data checks before it uploads; RUNBOOK "The deploy
    check"). After #115's merge: its own deploy and the first deploy after a daily publish are watched; if a deploy
    goes red for something that is not a real regression, #115 is reverted at once.
  - #114 (currency fix) is published and live (run 43368392513, 11-13 13:53 KST, once Yahoo had the 11-12 prices
    back): the 27 non-dollar filers show "–" for PER and PBR with the reason line; BRK-B has its own line.
  - #113 (token fix; this PR) is merged. Its own publish (a manual `dart=cache` run right after the merge) is
    watched to the end; if the push fails, #113 is reverted at once (Jack, 11-12). The data deploy that follows should
    skip #115's check.
  - Then, in order: #118 (Korean unit guard) → #116 (its repair) → #117 (fxHist and US splits). Each needs a fresh
    green branch dry run after its last rebase. Jack's answers of 11-13 are built into all three, and their final
    reviews are done.
  - Then screens: #119 v19.6a (after #117 is live) → #122 v19.7a → v19.6f (must be in review by Dec 1, merged by
    Dec 10) → v19.7b → v19.6c, v19.6b, v19.6e, v19.6g → v19.4 → v19.6h.
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
the 2026-11-13 block at the top of § 0. Still current reference: the morning-run fallback, the outside timer and the
scheduled tasks.

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
changes have a green `dry_run` with the validation summary in the PR, and no safety rule is loosened. It asks Jack
first, with a short yes/no question in the chat, for new or changed Korean UI text (showing the 「새 문구」 table),
changes to what users see beyond an approved spec, anything that costs money or needs a sign-up or setting change, any
change to `CLAUDE.md`, a `validate_data.py` threshold or `tests/` (even when nothing is loosened; added 2026-11-01), and
— until v17.6 is done — before merging v17.5 and v17.6 (his claude.ai chat reviews those PRs). After every merge it
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
