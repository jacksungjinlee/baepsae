## What changed
- For the 38 US-listed companies whose statements are not in dollars (`fcur`: the "27" of Jack's 11-13 message plus 11 of the 11-14 additions), the daily run now computes their **PER and PBR from whole-company totals**: market value ÷ last four quarters' net income, and ÷ latest-quarter common equity. Equity and income are converted at the exchange rate at the US close of the price date.
- **The rate** is Yahoo's hourly bar that ended by 16:00 New York time on the US price date (never a bar still open). It must agree within 2% with the Bank of Korea's (ECOS) rate. That is ECOS's first row after the US date, because an ECOS row dated d is the Seoul-morning rate, i.e. the previous New York close; if that row is not out yet, the row of the date or just before is used.
- Market value is the same number as the 시가총액 already shown (all share classes, ADR ratio included).
- **Dividend yield** = dividends actually paid in the last year ÷ today's close, only when the payment record is regular and agrees with Yahoo's own yield within 10%. 0% stays exactly as #114 decided.
- Every blank has a recorded reason: loss, stale balance sheet, income not confirmed, statements not received, rate not confirmed, uneven dividend record, time limit, and so on. Everything goes into data.json `usFcurTot` (documented in `units.usFcurTot` and `units.fcurTot`) and the run log: "· 달러 아닌 재무제표 38곳: PER 29 / PBR 33 / 배당 19 되살림 (배당 0% 그대로 10), 빈 칸 23 (…)".
- **Load and time limits:**
  - statements are cached and asked again every 3 days or after a new quarter;
  - a failed Yahoo table is retried and logged;
  - ECOS is not asked again after its first failure in a run;
  - the whole step stops at 180 s.
- **Nothing users see changes yet.** A switch, `validate_data.US_FCUR_TOT_ON`, is OFF: the stocks keep #114's "–" and currency line. Turning it on needs Jack's yes (see 안전 규칙 변경).
- **New gate row**, "달러 아닌 재무제표 회사: 회사 합계로 계산한 PER · PBR · 배당수익률 (usFcurTot · 경고만)". It only warns, and its call is wrapped so it can never stop a publish. It names each company once:
  - a PER more than 1.5× from Yahoo's own PER;
  - a profit or loss that disagrees with Yahoo's PER;
  - a big jump against the previous publish;
  - a sharp drop in how many numbers were computed.
- Docs: RUNBOOK section "US companies not reporting in dollars: PER · PBR · yield from company totals", HANDOFF § 0, CHANGELOG.

## Choices I made
- **Equity:** *Common Stock Equity* (common shareholders' equity, without preferred shares or minority interests; the usual PBR base). The row is chosen once: *Stockholders Equity* only when that row has no value at all. If its last value is not from the latest reported period, the equity counts as stale.
- **Net income:** *Net Income Common Stockholders*.
- **"Stale"** means not the latest reported period (Yahoo's `mostRecentQuarter` and every statement column, ±7 days for 52/53-week years), or more than 280 days before the price date (half-year reporters).
- **Net income check:** a second Yahoo route must agree within 10%: the TTM row or `netIncomeToCommon`.
  - The four-quarter sum and the TTM row usually come from the same quarters, so they are not independent. The code comments and RUNBOOK now say so.
  - On 11-23 this check keeps Futu, where Yahoo's TTM row is the wrong one (3.80B; the quarters, `netIncomeToCommon` and stockanalysis.com all give 11.08B HKD).
  - It blanks Unilever.
- **Sign check (review round 1):** when our income's sign disagrees with Yahoo's own PER, PER is blank as "not confirmed", not as a loss.
  - Sony is the case: its four quarters include the Sony Financial spin-off's discontinued operations (−1,385.9B JPY in the 2025-12 quarter), so they show a loss. Yahoo's continuing-operations income (+1,252B) and its PER (20.8) do not include it.
  - Whether TTM income should include discontinued operations is left as an open question for Jack, for switch-on.
  - Where Yahoo shows no PER (as for any loss), the sign is not checked.
- **A loss** leaves PER blank, as for every other US stock. The PER and PBR ranges are the same as for other US stocks (PER under 500; PBR from 0.005 up to 100).
- **Failed fetches:** yfinance 1.7 hides failed requests and returns empty tables, so an empty table counts as a failed fetch.
  - The exception is a half-year reporter's empty quarterly income table (balance-sheet columns half a year apart: BAT, CCEP, Unilever, Vodafone).
  - Failed tables are asked once more after 20 s. A number whose table still failed is blank as "재무제표를 받지 못함", never "자본 없음"/"순이익 없음".
- **Statement cache:** next to the US info cache (`us-fcur-stmt-v1.json.gz`), refreshed every 3 days or when `mostRecentQuarter` changes. On a failed day a copy up to 14 days old is used. It is written by the existing `save_us_info`: same gzip-JSON shape, and `tests/test_pipeline.py::test_only_write_json_writes_published_files` pins the three places `json.dump` may appear. No test edited.
  - Before the cache: 114 statement requests per run.
  - Now: 114 on a refresh day and 0 between (re-run with the cache: 0).
  - Plus about 12 hourly-FX and 13 ECOS requests per run.
- **ECOS:** 2 tries per currency and a circuit breaker after the first failure. The whole step has a 180 s limit (like #172). Local runs: 38.8 s with an empty cache, 14.3 s with it.
- **Rate window:** Yahoo hourly at the US close, checked against ECOS 731Y002 (CNY through 731Y001), next Korean-morning row first, within 2%. Yahoo's daily KZT bar was 3.3% off ECOS on 11-20, so daily bars are not used.
- **US early closes** (13:00) are not in the holiday table. On a date that may be one, the rate stays the same-day 16:00 bar and the log says so (`usFcurTot.halfDay`).
- **Yield:** the rhythm (quarterly · half-yearly · yearly) is read from the payment gaps. The yield is blank if a payment is missing (Royal Bank, TD, Kaspi) or late, or if it differs from Yahoo's own yield by more than 10%.
- **Gate row:**
  - It compares the PER only with Yahoo's own PER. Yahoo's PBR for these companies is the very number #114 blanked (TSMC 61, ASML 1,087).
  - It warns only for names new since the previous publish, so Futu and H World warn once, not daily; every name stays in the detail. It always warns on jumps, count drops, the time limit and broken records.
  - It names a record with dividend payments where the stock keeps #114's 0%.
- **Cache keys:** `mostRecentQuarter` is added to the US info cache keys without bumping the cache schema (the same pattern as `netIncomeToCommon`).
- **Switch-on path:** the pipeline's switch-on code path is built and tested. A test pins that turning the switch on alone fails the #114 gate row.

## 「새 문구」
없음 (no new or changed user-facing Korean in code).
Proposed for Jack, for when the switch goes on: a line under a PER or PBR converted from another currency. Draft: "재무제표가 {currency} 기준이라 {md} 미국 장 마감 환율로 달러로 바꿔 계산했어요." Not in code.

## 안전 규칙 변경
없음 in this PR. No existing gate row, threshold or test changed. Added: one warning-only gate row (wrapped, can never fail a publish) and a new test file.
Turning the switch on later is a safety-rule change (category 2) and needs Jack's yes. Existing tests that pin the hidden state of these companies and would have to change:
- `tests/test_us_fcur.py::test_gate_fails_when_a_blanked_number_is_left`
- `tests/test_us_fcur.py::test_non_dollar_statements_blank_per_pbr_dy_and_keep_the_rest`
- `tests/test_us_fcur.py::test_fetch_us_refetches_old_cache_entries_and_blanks_the_published_rows`

The #114 gate row "미국 재무제표 통화가 달러가 아닌 회사: PER·PBR·배당수익률·가치 점수 빈 칸" would also change, to accept exactly the numbers in `usFcurTot`. So would `src/v2/fcur.js` (`fcurLeftover`: one number back removes the currency line for all three). The discontinued-operations question also needs an answer.

## Test evidence
- `pytest tests/`: 5118 passed, 1 skipped (on d722adc)
- `pytest tests/test_us_fcur_totals.py`: 91 passed. New tests cover:
  - empty-table fetch failures (a fake that returns empty tables, like yfinance 1.7);
  - the half-year exemption, retry after a pause, the time limit, the statement cache and new-quarter refetch;
  - the ECOS circuit breaker and the next-morning ECOS row;
  - Sony's sign case;
  - gate fuzzing of malformed shapes, the wrapper, new-names-only warnings and the count drop;
  - the whole-object switch-off check.
- `python tests/check_text.py`: 페이지 4개 · JSON 81개 · 문제 0개
- `bash build.sh` / `bash build-app.sh`: not needed (no `src/` change)
- Real data (data branch copy 5f1d9d1, pxDate 2026-11-20; the 11-24 publish was not out yet at 03:17 KST): real_data_check.py --data 3 / 3 · smoke_launch.py --data 14 / 14 · smoke_app.py --data 171 / 171
- **Proof on the 11-20 closes, re-run after round 1** on live Yahoo data (statements fetched fresh by the new code) and ECOS:
  - PER and PBR from company totals were compared with stockanalysis.com's statements in the reporting currency and its share counts, at our close and ECOS's next-morning rate.
  - All 11 are within ±3%: TSMC, Novo, SAP, ASML, Toyota, JD, Ryanair, Futu, H World, BAT, Kaspi.
  - The largest difference is H World's PBR, +2.9% (from the share count). Kaspi is now +0.1% (it was +6.9% against stockanalysis's own USD conversion).
  - The companies' own releases match Yahoo's totals: TSMC Q3 net income NT$763.06B, ASML Q3 €4,960.4M, Novo nine-month net profit DKK 86,286M.
- **Counts:** PER 29 · PBR 33 · yield 19 (+10 clear 0%) · 23 blanks:
  - 6 uneven dividend records;
  - 5 losses;
  - 4 stale balance sheets;
  - 2 unclear dividends;
  - 2 income not confirmed (Unilever; Sony by sign);
  - 1 yield mismatch, 1 negative equity, 1 missing income, 1 stale income.
- Gate row on that record: it names FUTU (PER 8.2 vs Yahoo 24.06), HTHT (20.0 vs 33.83) and SONY (sign). It warns on the first publish only. On the live data-branch file the row passes as an older file.
- `python tools/pr_rules.py --body-file … --base $(git merge-base origin/main HEAD) --head HEAD`: PR 규칙 통과 (rule 1 not applicable · rule 2: HANDOFF § 0 changed)
- **Dry run:** after the 11-24 morning publish (DART daily allowance). Results will be added here.

## Fresh-eyes review
Round 1, two reviewers (Opus 5.5 Extra high, Fable 5.2 High): no blocker while the switch is off. Fixed, all in the second commit:
- **Silent fetch failures** (both): yfinance 1.7 returns empty tables instead of raising. Fix: empty = failed, with a retry, a log line, the reason "stmt", and a gate count-drop warning.
- **Sony** (Opus S1): the sign check against Yahoo's PER, honest comments, and the measure question for Jack.
- **Gate crash on odd shapes** (both): isinstance guards and a wrapped call.
- **ECOS row date** (Fable S3): prefer the next Korean-morning row.
- **Load** (Opus S4): statement cache, ECOS circuit breaker, 180 s limit.
- **Daily FUTU/HTHT warnings** (Fable S2): new names only.
- **Nits:**
  - `err` rows in the log;
  - the bar-window comment;
  - the half-day log;
  - the PER-only comment;
  - the equity-row rule;
  - divMismatch with #114's 0%;
  - a whole-object switch-off test.
- The rounds stop here: round 1 had no blocker.

## After merge
- Watch the next publish's log for the `· 달러 아닌 재무제표 …곳` line, the `재무제표:` line (114 requests on that first run, about 39 s), the rates line and the new gate row. Expected: WARN once, naming FUTU, HTHT and SONY.
- Check that data.json `usFcurTot` exists with `on: false`, and that the 38 stocks still show "–" with the currency line on the site.
- Nothing for Jack to look at on his phone; the screens don't change.
- Questions for Jack:
  - switch on (with the gate row, test and app changes above)?
  - the converted-number line?
  - TTM income with or without discontinued operations?

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
