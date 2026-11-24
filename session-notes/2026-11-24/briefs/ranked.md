# Track 2 audit — findings, checked and ranked (running list)

Ranks: **serious** (users see a wrong or stale number without knowing, or the site/publish breaks) · **minor** · **false alarm**.
"Checked" = I re-ran the helper's script or re-read the code/live data myself.

## Audit 3 — pipeline silent fallbacks, units (Fable High, done 11-23 ~22:00 KST)

| # | Finding | Checked | Rank | Fix |
|---|---|---|---|---|
| 3.1 | 18 Korean payers published with dividend 0 (`dps` 0, `dyt` 0.0) although the same DART table shows a cash dividend total for that year (현대코퍼레이션 700원 → 0, 케이프 ~6.6%, 앱코, 동일산업 …). 2.0's 배당 tab reads "배당을 주지 않았어요" / a cut. Parser takes the first common-share DPS row and turns "-" into 0. | live data: 18 rows reproduced (`aud3_work/live_div_zero.py`) | **serious** | pipeline PR: DPS 0 with cash total > 0 → blank + dvLine 4 (approved "자료가 빠져 있어서"), log count, gate row (warn) |
| 3.2 | SNDK split 8:1 on 11-20: published PBR 0.63 (≈ 8× too low) → 가치 99. **Corrected by the builder:** PER 5.1 and cap were right (details fetched fresh after the split); only Yahoo's own `priceToBook` still used pre-split book value. The audit's code path (`us_rescale` ignoring splits) is a real latent bug that would make PER/PBR/yield/cap all 8× off for a cached entry. | live row + splits list; builder traced the cause | **serious** | PR #176: split-aware rescale + refetch after a split + warn-only gate row (SNDK named). Blanking a stale PBR needs a new reason line → Jack |
| 3.3 | Every Korean TTM figure is still on 2026.2Q (2,244 companies, 0 on 3Q) five days after the 3Q deadline. A "not filed yet" answer near the 11-14 deadline is not asked again for 7 days (`dart_entry_due`), and the 70%-of-top-100 rule then holds everyone on 2Q. | corp.json `bq`; code read (mechanism, not logs) | **serious (stale)** — should self-heal at the 11-24 06:40 run (7 days up); confirm in its log | pipeline PR: daily retry until the new quarter is adopted (or deadline + 10 days), deadline rolled to the next business day |
| 3.4 | Raw DART `dy` / `dps` have no plausibility check. Old app shows 흥국 배당수익률 56.0% (real 5.7%: dividend ÷ par), 지투파워 33.7% (payout ratio), and 와이엔텍 `dps` 1,809,965,900원 (total filed in the per-share row → 배당성향 absurd). 2.0 uses `dyt`/`dps3a`, unaffected. | live rows (`live_div.py`) | **serious (old app)** | pipeline PR: blank `dy` far from dps ÷ price; blank `dps` ≥ price or dps × shares ≫ cash total |
| 3.5 | One failed gold download drops `mktVol`, `usVol` and every correlation, with the wrong reason in the log. | code read | minor | compute without gold; gate row |
| 3.6 | 13 US ETFs sit in the US percentile base with junk PBRs (SOXX 0.29 → 가치 100); best US stock tops at 98. | live rows | minor | rank non-ETF rows only |
| 3.7 | Silent mixed-basis fallbacks: `g3` falls back to 1-year growth for 32 companies but is labelled "최근 2년 연평균"; EV with missing borrowings/cash as 0; EBITDA mixing TTM and annual; bond ETF `al`/`beta` 0. | live count (g3 32); code read | minor (g3 label is wrong for 32 small companies) | basis flag or blank, with counts |
| 3.8 | `fx` 1,345.7 (Yahoo bar still open at 06:41 KST) vs ECOS 11-20 close 1,336.2 under the same date; US caps in won use the first (0.7%). | data vs macro | minor | use the ECOS close for the date when present |
| 3.9 | 본시스템즈 (KONEX) 1,176,000원, 52주 최저 24,300원, mom 4,739% — consistent with source; manual look. | — | unsure | look by hand |

## Audit 1 — money math: records, 내 수익, 연말, 이번 주 정리 (Fable High, done 11-23 ~22:30 KST)

Core gain, tax (250만원 · 22% · losses), exchange-rate split, dividends, CSV, old-store, weekly-gain arithmetic all matched hand sums.

| # | Finding | Checked | Rank | Fix |
|---|---|---|---|---|
| 1.1 | A split with a ratio that isn't exact in 4 decimals (11 of 150 in data.json, e.g. 듀폰 DD 1:3 on 2026-06-24, 유니레버 UL 8:9) breaks records saved before it: `held.js:87` rounds to 1/10,000 share, `lots.js` doesn't. (A) the app's stored-split save is refused as "sold more than held" and retried endlessly (hundreds/s, on every screen) with "날짜·수량·가격을 다시 확인해 주세요" showing; (B) a valid sale of shares bought before the split is refused "가진 수량보다 많이 팔 수는 없어요"; (C) 0.0001주 left over / a −5원 "loss" on the tax screen with nothing held. | node repro re-run: (a) tooMany + deckProblem "sold more than held" reproduced | **serious (rare)** — site misbehaves for anyone holding DD/UL-type history | app PR: compare with the ledger's tolerance (or apply the split to the running total), stop retrying a refused split store |
| 1.2 | 포트폴리오 rounds fractional US shares to whole numbers (7.5 → "8주", 0.4 → "0주") — `portfolio.jsx:195` | auditor browser repro | minor (wrong share count shown; money totals right) | use `qtyText` (4 decimals) |
| 1.3 | Two tabs: a record deleted in tab A comes back when tab B saves anything (no record tombstones) — `store.js:997` | auditor node repro | minor | deletion mark per record id |
| 1.4 | Selling a 금액으로 넣은 holding dated before a reverse split double-scales the quantity (gain +958,683원 vs +276,040원) — `records.js:145` | auditor node repro | minor (rare; wrong gain) → treat with 1.1 | quantity on the sale date's basis |
| 1.5 | Tax screen "약 0원" for a 361원 dividend / a tax under 1,000원 — `tax.js:62,142,178` | auditor repro | minor | exact amount below 1,000원 (wording same) |
| 1.6 | 내 수익 labels US-only prices with the Korean date (11월 20일 vs tax screen 11월 19일) — `returns.jsx:161`; shows after the 11-26 US holiday | auditor browser repro | minor (date label wrong) | use usPxDate when all counted holdings are US |
| 1.7 | A split ratio corrected on the same date keeps the stored old ratio — needs the pipeline to publish a wrong ratio first | — | unsure | move stored ratio to data.json's |

## Audit 2 — dates and time zones, both apps + pipeline (Fable High, done 11-23 ~23:00 KST)

Nothing serious. Sound: no device-zone APIs in src/ (179 date tests pass under New York and Kiritimati zones); freshness verdicts right for every 30 min of 2026–2027 incl. 추석/설/Thanksgiving/DST; the seven cron starts; week finality on 105 simulated weeks; no naive clocks in the pipeline; content dates.

| # | Finding | Checked | Rank | Fix |
|---|---|---|---|---|
| 2.1 | A US record typed after midnight KST (the US session, 23:30–06:00 KST in winter): the default date is the KST date (next day), and the US local date that the form's own hint asks for ("미국 주식은 미국 현지 날짜로 적어 주세요.") is refused (`rate notYet`). With a split on the KST date, the share count differs ×10. Today-dated records also take data.json `fx` whose own date is earlier. — `records.jsx:180,264,267`, `records.js:44,48` | re-ran `rec_date.mjs` on live data: at 01:00 and 05:30 KST the US date is REFUSED | minor (entry blocked/misdated; no wrong number shown in normal days) | accept the open US date for USD records (the hint already asks for it); default to it for USD records |
| 2.2 | 오늘 볼 것 drops a US earnings date at 00:00 KST, hours before an after-close release — `look.js:203` | auditor repro | minor | compare US dates with the New York date |
| 2.3 | A scheduled start > ~9h13m late crosses midnight KST: publishes Korea-new/US-old with `nextPub` = publish day; after a US long weekend the gate fails (red run, no publish); the morning run repairs. Longest delay seen ~8h. — `already_published.py:137,180` | auditor simulation | minor (edge) | treat after-midnight-before-US-close as the wait window |
| 2.4 | 이번 주 정리 "다음 주" tile on Mon/Tue still lists the week the reader is in — `weekly.js:296` | auditor repro | unsure (header carries the range; maybe intended) | relabel/hide from Monday — new wording, Jack |

## Audit 5 — places one bad row stops the publish (Fable High, done 11-24 ~00:10 KST)

Sound: KRX listing helpers (143 odd-row variants), per-stock builders wrapped, `real_data_check`/`smoke_launch` with 20 odd rows, `smoke_app` with nine odd rows, the built-in-stock cap (4 of 75), year change.

| # | Finding | Checked | Rank | Fix |
|---|---|---|---|---|
| 5.1 | A built-in (non-must-have) Korean stock marked `pxBad` (broken price history, as 20 small caps are today) makes the pre-publish `smoke_app --data` fail (164/171: "일부 종목은 최신 시세가 아니라 예시 가격이에요" banner expected) — the test still counts blank β/vol as "example price", the app stopped doing that for `pxBad` on 11-14. With SK하이닉스 marked, the B안 scene also fails. Holds everyone's publish until a code fix. | auditor repro on live data (`aud5_work/d_base_pxbad`) | **serious (latent)** — not happened yet (built-ins rank ≤ 204 by cap; marks so far ≥ 611) | edit `tests/smoke_app.py` to the app's rule (`pxBad` with a price ≠ example) and let B안 pick any four stocks with vol — **edits a publish-blocking test → needs Jack's yes** |
| 5.2 | Gate row "글자에 nan·None·null·undefined 없음" scans every string in all four files with zero tolerance, and the pipeline's own "never stop the publish" guards write raw error text there (`usSrc.own.err`, `pxSrc.own.err`, `splitsInfo.err` = `str(e)`, e.g. "cannot convert float NaN to integer", pandas "None of [Index…"), and `ownDrop.rows` reasons ("…; d null"). So a caught error or a dropped row stops the whole publish. Also source free text (a DART position "None"). | code read: `validate_data.py:342` BAD_WORD + `:4033`; `fetch_data.py:2347,2754,2979,3237` store `str(err)` | **serious (latent)** | pipeline PR: write error/reason text without those words (type name + cleaned message, "빈 값"); blank a single source text that has one, with a loud line and an `ownDrop` count. Gate unchanged |
| 5.3 | On a Korean holiday after a Daum×Yahoo day, one Korean stock lost on rerun holds the whole publish (`publish_hold.py:258` `if n_lost:`) — new US closes don't go out; run green | decision function on the 11-19 file | unsure | carry the lost row with a loud line, or hold only above 5 |
| 5.4 | ~25 own-processing gate rows still FAIL on one row (data=corp EPS/PER rows, dividend rows, β SE, 업종, unitChk, etf 표시…) — each needs a new pipeline bug first | fuzz (~5,900 one-row mutations) | unsure | move to drop-or-blank with N = 5 when touched |
| 5.5 | Gate crashes (no table) on a non-text `t`/`dk`/`ind`; `write_json` rejects `pd.NA`/`NaT`/Timestamp/numpy-int keys; AAPL/MSFT/NVDA missing from the etf keep-list | fuzz | minor (implausible rows) | FAIL row instead of crash; convert unknown types with a count; add the three |

## Audit 4 — numbers hidden or adjusted without a reason line (what the 11-22 list missed or what changed) (Fable High, done 11-24 ~01:50 KST)

| # | Finding | Checked | Rank | Fix |
|---|---|---|---|---|
| 4.1 | 이번 주 정리 → 내 포트폴리오 "{%} · 코스피 {%}": shares bought mid-week count only from their buy price, 코스피 is the whole week. A portfolio bought Sat 11-21 at Friday's closes shows "0.0% · 0원 · 코스피 −7.9%" (reads as beating the market by 7.9%p). `weekly.js:238-241` | auditor browser repro on a built week copy | **serious** (user's own money, misleading comparison) | compare 코스피 over the same money flows (as 포트폴리오's vs-코스피 box does), or hide with a line — **spec/wording → Jack** |
| 4.2 | 홈 card "오늘 {amount} ({pct})" applies the last close-to-close move to every share held now, incl. shares bought after that close: bought 11-21 at the 11-20 close → "오늘 −17만원 (−4.3%)" right above "산 가격보다 0원 (0.0%)". `home.js:31` dayMove, `track.js:200-216` | code read (dayMove uses current value × d1 for all) + auditor browser repro | **serious** (wrong money number on a common path: recording today's purchase) | app PR: shares bought on/after the price date count only from their buy price (on the price date) or not at all (after it) |
| 4.3 | 오늘 볼 것 → 다가오는 일정 stops at 5 rows with no "외 n" (8 US holdings with dates → 3 dropped) — `look.js:49,207` | browser | minor | "외 n" — new wording |
| 4.4 | Weekly left-out line ("이번 주 움직임을 확인하지 못한 종목 …") also used for stocks in a portfolio made this week / entered by amount this week / taken out this week — untrue reason | browser | minor | separate lines — new wording |
| 4.5 | Corrections of 30+-day-old decisions and non-common share classes left out of 확인 필요 with a console line only (49 filings / 37 stocks; 33 get no card) | browser + counts | unsure (waits on Jack's #145 Q3) | — |
| 4.6 | Weekly 공시 tile never counts 지분 변동 (role not read until the v19.6b switch-on) | browser | minor (fixed by switch-on) | v19.6b switch-on |
| 4.7 | "다음 주" tile on Monday = this week (same as 2.4) | browser | minor | — |
| 4.8 | Weekly gain leaves out dividends recorded in the week (no line; `deck.vsNoDiv` "배당은 빼고 비교했어요." reusable) and US uses fxHist 1,336.2 vs 홈's 1,345.7 with no rate shown (`co.fxWon` reusable) | browser | minor | reuse approved lines |
| 4.9 | A US ticker waiting for its first confirmed close (#169): search says only "찾는 종목이 없어요." | code | minor | — |
| 4.10 | 오늘 등락률 rounds two ways (홈 −16.0% vs 포트폴리오 −16.1% for SNDK; 135 stocks differ by 0.1%p) — `deckcalc.js:222` vs `components.jsx:168` | browser | minor | one rounding |
| 4.11 | 업종별 등락 is a plain average (전력·가스·환경 −2.3% vs cap-weighted +0.4%) — line says "평균 등락률" | node | unsure (true as worded) | — |
| 4.12 | >5 Naver-confirmed stocks left out under "확인하지 못한" and the mover picked from the rest | node | minor (rare) | nvNoteMore (approved 11-23) |

11-22 rows fixed since: N-01 (dividend part) and N-02 (배당수익률 cell) → #167. Count changes: N-06 69 → 103 (blank 오늘 등락률 also left out of industry averages); N-04 adds the weekly card.
