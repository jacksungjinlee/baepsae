## What changed

- **The problem (Track 2 audit 3.5, minor):** the daily data run downloads the international gold price (Yahoo `GC=F`). When that one download failed or came back empty, the run threw away all 10 "market assumptions" both apps use for portfolio risk, including the ones that have nothing to do with gold: KOSPI and S&P 500 volatility, the Korea–US correlation and the bond numbers. The log then gave the wrong reason ("시장 가정 계산에 쓸 날이 728일뿐", too few days, when there were plenty).
- **What users would have seen on such a day:** the old app quietly used its built-in numbers (KOSPI volatility 18% instead of about 37%, Korea–US correlation +0.50 instead of about −0.04, so every 예전 뱁새 risk figure was off), and 2.0 could not show its yearly-swing line.
- **Now:** every number whose inputs exist is computed. If gold is missing, the 6 Korea, US and bond numbers are still computed and only the 4 gold ones are left out. The same holds for a gold or bond series that arrives too short.
- **On a normal day nothing changes:** with every input present the 10 numbers, and their order in `data.json`, are exactly what main produces. A new test runs main's old code side by side and compares. On real Yahoo data up to 11-23 both give the same 10 numbers.
- **The log now says exactly what happened**, e.g. "국제 금값(GC=F)을 받지 못해 금 관련 4칸(mtVol · rhoKrMt · rhoUsMt · rhoMtBd)은 빼요 …", with the count and the true reason.
- **New warning-only gate row** "시장 가정 (settings 변동성 · 상관계수 · 경고만)": it names any of the 10 numbers that is missing, and which of those yesterday's publish had. It can never stop a publish. On today's live data it reads "10칸 모두 있음" (PASS).
- **Not changed:** no screen, no wording and no build output (`baepsae.html`, `app.html` and `app-preview.html` are byte-identical to main).
- **Found, not fixed (needs Jack, see below):** when a key is missing, neither app tells the user why. The old app uses its default silently. 2.0's risk lines then blame the holdings' 베타·변동성 자료, which is the wrong reason.

## Choices I made

- **One table for all numbers:** they are all computed from the same days (the days every input used has), so the correlations stay consistent with each other. This also keeps the all-present case identical to main. Computing each pair on its own days would have changed today's numbers.
- **When a series is too short:** a gold or bond series that shares 250 days or fewer with Korea and the US is left out like a missing one. If each is long enough alone but the four together are not, the one with fewer days is left out (bonds on a tie). Main left out all 10 in both cases.
- **A value that comes out NaN or out of range** (`ann_vol` returns None) is now left out of `data.json` with a log line, instead of being written as `null`. Both apps read `null` and a missing key the same way (old app `isFinNum`, 2.0 `num`), so nothing users see changes.
- **A gold or bond series that raises an error** while it is joined is caught on its own. The Korea and US numbers are still computed, and the error is the logged reason.
- **The list of 10 keys lives in `validate_data.MKT_KEYS`** and the pipeline imports it, as it already does with `BAD_WORD` and others, so the gate and the pipeline can't drift apart.
- **The gate row is warning-only**, and a crash inside it is a warning too, following `check_us_size`. It sits next to the 무위험수익률 출처 row, in both the publish gate and the site check. In the site check there is no previous publish, so the row lists only what is missing.

## 「새 문구」

없음. No user-facing text changed. The new strings are log lines and the gate row (operator-only, Korean in house style).

## 안전 규칙 변경

- **Added (stricter only, cannot fail a publish):** gate row `시장 가정 (settings 변동성 · 상관계수 · 경고만)` (`validate_data.check_mkt_settings`). It warns when any of the 10 keys is missing or not a JSON number, and in the publish gate it names the ones the previous publish had. PASS when all 10 are numbers. It never fails, and an error inside it is a warning. Under the 11-20 rules this needs no yes (it cannot stop the publish). It is listed here and in the after-merge summary.
- **Added test file:** `tests/test_gold_corr.py` (38 tests).
- **Unchanged:** no existing test, threshold, fixture or gate row was edited.

## Test evidence

- `bash build.sh && bash build-app.sh`: OK. `git status` shows no change to `baepsae.html`, `app.html` or `app-preview.html` (byte-identical to main).
- `python -m pytest tests/test_gold_corr.py -q -p no:cacheprovider`: 38 passed. It covers:
  - all present (5 random seeds × `us_vol_krw` given or not): identical values and key order to main's old code;
  - bond missing: identical to main;
  - gold missing or empty: 6 keys, the right log line, no "일뿐";
  - gold and bond missing: 3 keys;
  - too few Korea/US days: no keys, with the true reason;
  - short gold: only the gold keys left out;
  - gold and bond each long enough but not together;
  - a broken gold series;
  - a NaN or out-of-range value;
  - `main` calls the function and the old condition is gone;
  - the gate row: PASS, WARN with names, previous-publish names, non-numbers, odd files, a crash, and inside `run_checks` in publish and live modes with every other row unchanged.
- Full suite `python -m pytest tests/ -q -p no:cacheprovider`: FULL_PYTEST_RESULT
- `python tests/check_text.py`: 글자 점검: 페이지 4개 · JSON 87개 · 문제 0개.
- **Gate on the live data** (a copy of the 4 files the site serves: `pxDate` 2026-11-23, published 2026-11-24 06:40:59 KST), `python validate_data.py --live --dir <copy>`:
  - main: 167 rows (150 PASS · 15 WARN · 2 SKIP), exit 0;
  - this branch: 168 rows (151 PASS · 15 WARN · 2 SKIP), exit 0;
  - the only difference is the new row: PASS "10칸 모두 있음".
  - With the 4 gold keys removed from a copy, the row reads "빠짐 4 / 10칸: mtVol · rhoKrMt · rhoUsMt · rhoMtBd (지난 발행본에는 있던 칸 4: …)" and is a WARN.
- **Real-data comparison** (Yahoo ^KS11, ^GSPC, KRW=X, GC=F, 148070.KS, 3 years up to 2026-11-23; close to the pipeline's inputs, though the pipeline's KOSPI and bond series come from Naver):

  | Case | main | this branch |
  |---|---|---|
  | All present | 10 keys | identical 10 keys: mktVol 36.9 · usVol 19.1 · mtVol 23.8 · rhoKrUs −0.03 · rhoKrMt 0.03 · rhoUsMt 0.35 · bdVol 5.7 · rhoKrBd 0.16 · rhoUsBd −0.16 · rhoMtBd −0.04 |
  | Gold missing | `{}`, log "날이 728일뿐" | 6 keys: mktVol 36.9 · usVol 19.1 · rhoKrUs −0.03 · bdVol 5.7 · rhoKrBd 0.16 · rhoUsBd −0.16 |
  | Bond missing | 6 keys | identical 6 keys |
  | Gold only 120 days | `{}` | the same 6 keys, gold left out with "112일뿐" |

  For reference, the published 11-24 values are mktVol 36.8 · usVol 19.3 · rhoKrUs −0.04. The old app's defaults are 18 · 16 · 0.50.
- **Real-data screen checks** (`real_data_check.py`, `smoke_launch.py`, `smoke_app.py --data`) are not required: nothing the site serves changed, and those scripts import neither `fetch_data` nor `validate_data`.
- **Still needed before merge (pipeline change):** a green `dry_run=true` run on this branch, with its validation summary pasted here. Its log should show "· 시장 가정 계산 완료 (…): 10 / 10칸" and the gate row PASS.

## What the two apps do with a missing key (for Jack; not changed here)

- **Old app (예전 뱁새):** falls back key by key.
  - The loader copies only the keys that are finite numbers (`src/detail.jsx:4963-4966`, `AUTO`). A missing key keeps `DEFAULT_SETTINGS` (`src/detail.jsx:621-627`: mktVol 18 · usVol 16 · mtVol 15 · rhoKrUs 0.50 · rhoKrMt 0.00 · rhoUsMt 0.05 · bdVol 7 · rhoKrBd 0.05 · rhoUsBd 0.05 · rhoMtBd 0.10). A saved portfolio instead keeps the value it stored (`withTodaysAuto`, `src/detail.jsx:283-304`).
  - That value feeds every risk number as if computed: `clsVol` / `rhoOf` (`src/detail.jsx:1368-1379`), σ and "보통 해 ±…만원" (`src/detail.jsx:2562`, `2665-2666`), and the KOSPI comparison row σ (`benchMetrics` `src/detail.jsx:1487-1489`, rows `2784-2788`).
  - The only sign is the 설정 sheet's chip: 가정 instead of 자동 (`autoChip` `src/detail.jsx:330-332`, `4641-4642`). That is the same chip as the always-assumed fields (기대 초과수익, 물가), and no line says why.
  - **Finding:** a default is shown as if it were computed, with no say-why line.
  - Simple mode (`src/simple.jsx:152`) always uses `DEFAULT_SETTINGS` and never reads data.json, whatever the pipeline does. Its 위험 수준 scale (`src/simple.jsx:357`) is always drawn from the built-in assumptions (KOSPI 18%) with no line saying so. This is an older, separate finding.
- **2.0:** also key by key, and it never uses a default.
  - `engine.deckVol` (`src/v2/engine.js:986-1024`) runs only when the 2022 line can't be shown (`src/v2/deckcalc.js:51`).
  - A missing class volatility (`F[c]` null) makes that class's holdings unusable (`engine.js:997-998`). They are left out and `plan.riskPartial` shows "일부 종목(비중 {pct}%)은 베타·변동성 자료가 없어요. 위험 수치는 나머지 종목으로 계산했어요." (`src/v2/plan.jsx:126,161`; `src/copy/v2.js:1403`). Above half, `riskHalf` shows instead.
  - A missing correlation between two classes the deck holds returns null (`engine.js:990`, `1012-1013`), and `plan.riskNone` shows "담은 종목 모두 베타·변동성 자료가 없어 위험 수치를 계산할 수 없어요." (`src/v2/plan.jsx:166-168`; `src/copy/v2.js:1404`).
  - **Finding:** these approved lines give the wrong reason in this case. The holdings do have their data; it is the market assumption that is missing.
- **With this PR, on a no-gold day:** the old app uses the default only for the 4 gold keys, where before it used all 10. 2.0 leaves only gold holdings out of the yearly-swing line ("일부 종목…" line), where before every deck without a 2022 line got "담은 종목 모두…".

## Fresh-eyes review

To be done before merge. This is a pipeline PR touching `fetch_data.py` and `validate_data.py`, so round 1 has two independent reviewers (Opus 5.5 Extra high and Fable 5.2 High). Findings and fixes go here.

## After merge

- Watch the next daily run.
  - Log: "· 시장 가정 계산 완료 (…일, ~pxDate): 10 / 10칸 — {…}". On a day gold fails, "!! 시장 가정: 국제 금값(GC=F)을 받지 못해 …".
  - Gate: new row "시장 가정 (settings 변동성 · 상관계수 · 경고만)" PASS "10칸 모두 있음".
  - `data.json` `settings`: the same 10 keys in the same order.
- Then the site check (search 005930 and 현대차, open every tab, check the dates).
- New gate row to note: `시장 가정 (settings 변동성 · 상관계수 · 경고만)`, warning only.
- Jack: nothing to look at on the phone; no screen changed. One question for him later (category 1, new wording): should the apps say why when a market assumption is missing?

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01THEDvaVgXEGTc51bivEoJb
