# 뱁새 — Handoff to Claude Code (2026-10-30)

This document carries everything decided in ~3 months of building 뱁새 in claude.ai chat (v9 → v17.4,
2026-07-30 → 2026-08-20, then a pause). Read it once fully. `CLAUDE.md` holds the rules; this file holds the context.

---

## 1. Product

**Purpose.** An honest, non-speculative research studio for Korean retail investors. It helps them see what they own,
how their holdings move together, and what today's prices assume — without telling them what to buy.

**Target user (single persona, decided):** 1–3년차 실전 투자자 — people who already invest real money,
know basic terms, and get burned by concentration, hype and not knowing what they hold.

**How Jack works.** Design and decisions in claude.ai chat (the Claude desktop app). Engineering in Claude Code
Cloud sessions from the desktop app's Code tab. He reviews and merges pull requests on GitHub's web pages. No local
dev setup on his PC.

**Status.** Not launched. Shared with a handful of friends. The link is on Jack's CV, and an English demo mode exists
for job interviews outside Korea. Real usage numbers are too small to drive decisions yet.

**Brand.** Name 뱁새 (long-tailed tit, from the proverb 뱁새가 황새 따라가다 가랑이 찢어진다). Tagline 황새 말고,
내 걸음으로. Mascot 뱁이 (Jack's own art). Palette ink `#1C2B45`, apricot verdict bar `#C97757`, cream background
`#FAF8F5`. Icons are custom stroke icons in `src/icons.jsx`. **Zero emoji anywhere**, always.

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

Scheduled for weekdays at 21:30 UTC (06:30 KST, after the US close). **In practice GitHub starts it ~09:00–10:00 KST**,
during Korean trading hours — see § 5. Python 3.11. Secrets
`DART_API_KEY` (OpenDART, ~20,000 calls/day quota) and `ECOS_API_KEY` (한국은행 ECOS). The workflow commits the four
JSON files to `main` as `baepsae-bot`, with `git pull --rebase` before push (avoids a race with manual uploads).

`main()` order:
1. `fetch_rf` — risk-free rate.
2. `fetch_korea` — since v17.4.1/v17.5: the latest **final** listing file before today (KST) from `fdr_krx_data_cache`
   (≥ 90% market caps filled, last commit at or after **16:00 KST**) → top 2,500 by market cap (`MAX_KR`) → sector
   descriptions (`KRX-DESC`) → KOSPI index → per-stock prices `fdr.DataReader(code)` (8 threads), every series cut at
   `pxDate` with the `pxDate` bar set to the **official close = `Marcap ÷ Stocks`** → `enrich_with_dart` (annual,
   dividends, quarterly → TTM; cached in `.dart-cache`; 5 threads) → `fill_multiples`. (Before v17.4.1 it used
   `fdr.StockListing("KRX")`, which read the pre-market file — see § 5.)
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
   April, between 16:13 and 17:59 — so v17.5 treats a file as final from 16:00 KST.)
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
2. **v17.6 never again** (right after) — `docs/tasks/v17.6-never-again.md`. Independent watchdog on the live site, CI on
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
