# Logo coverage test (v19.1 Part L)

One-off test: which of the ~3,250 Korean and US stocks in `data.json` get a real company logo from **Brandfetch** and
**logo.dev**, by route (ticker, ISIN, domain), per market, and for the best mix of both. No UI, nothing on the site
changes, and nothing it downloads is committed: tickers, results, summaries and contact sheets go to a scratch folder
**outside the repository** (the scripts refuse a folder inside it).

Spec: `docs/tasks/v19.1-company-page.md`, Part L. Keys: see `KEYS.md` (free publishable keys only).

## Files

| File | What it does |
|---|---|
| `build_tickers.py` | Writes `tickers.csv` from public files only (no DART key, no provider key). |
| `run_test.py` | The test. `--dry-run` prints the planned loads; `--self-test` runs everything against a fake provider. |
| `contact_sheet.py` | PNG grids of the 200 largest Korean and the 200 largest US companies with the logo the best mix chose. |
| `logo_common.py` | Shared helpers (ISIN check digit, homepage → domain, provider URLs, key masking, the summary). |
| `selftest_fake.py` | The fake Brandfetch / logo.dev used by `run_test.py --self-test`. |
| `KEYS.md` | Click-by-click steps for Jack to get the two free keys. |

Unit tests (no network): `pytest tests/test_logo_tools.py`.

## How to run (from the repository root)

The scratch folder defaults to `$LOGO_TEST_DIR`, else this session's scratchpad `…/scratchpad/logos`. In a new
session set it first, for example `export LOGO_TEST_DIR=/tmp/logo-test` (any folder outside the repo).

```bash
# 0. once per machine (the cloud environment already has these)
pip install -r requirements-dev.txt && python -m playwright install chromium

# 1. ticker list (about 10 s): live data.json + the KRX listing and company list for its pxDate
python3 tools/logo_test/build_tickers.py

# 2. checks without any provider
python3 tools/logo_test/run_test.py --dry-run          # planned loads per route, and one plain image through the browser
python3 tools/logo_test/run_test.py --self-test        # whole pipeline against a fake provider on 127.0.0.1 (~1 min)
python3 tools/logo_test/contact_sheet.py --placeholders 24

# 3. keys: only in environment variables, never on a command line that gets logged, never in a file in the repo
#    (keys.env lives in the scratch folder: two lines BRANDFETCH_CLIENT_ID=… and LOGODEV_TOKEN=pk_…, chmod 600)
set -a; . "$LOGO_TEST_DIR/keys.env"; set +a

# 4. pilot: the 200 largest of each side (~1,800 loads, about 6 minutes), then look at summary.md and the sheets
python3 tools/logo_test/run_test.py --top 200
python3 tools/logo_test/contact_sheet.py

# 5. full run if the pilot is clean (resumes; ~10,500 Brandfetch loads at 3/s ≈ 1 hour, ~8,100 logo.dev loads at
#    5/s ≈ 27 min, both at once), then the sheets again
python3 tools/logo_test/run_test.py
python3 tools/logo_test/contact_sheet.py

# 6. afterwards: delete keys.env (and images/ if --save-images was used)
```

Useful options of `run_test.py`: `--providers logodev` (one provider), `--routes logodev:ticker,brandfetch:isin`,
`--markets KOSPI,US`, `--top N` (the N largest companies of each side, no ETFs — the same rows as the contact sheets),
`--mix-order …`, `--bf-rate` (max 3.3), `--ld-rate`, `--concurrency`, `--save-images` (off by default, see the terms),
`--headed` (show the browser; needs a display).
A run that stops (refusal, Ctrl-C, lost session) resumes where it was: finished loads in `results.csv` are skipped
(only while the identifier is unchanged — after a rebuilt `tickers.csv` a changed domain or ISIN is loaded again).
`summary.md` and `mix.csv` cover the tickers and routes of the run that wrote them.

Exit codes: `0` all planned loads finished · `2` a provider was stopped (refusal, bad key, block, quota; the reason is
at the top of `summary.md`) · `3` some loads never finished (errors or 202s after 5 tries; counted loudly in the log
and in `summary.md` — rerun the same command to retry them) · `1` crash (traceback printed with keys masked).

## What it writes (scratch folder)

| File | Content |
|---|---|
| `tickers.csv` | code, name, market (KOSPI / KOSDAQ / KONEX / US), ETF flag, cap (조원), rank (all) and rank_cls (KR or US), logo.dev ticker form (`005930.KS`, `247540.KQ`, `AAPL`), ISIN + source, issuer (common share) code, domain + source, raw homepage. |
| `results.csv` | One row per load (append-only): verdict, HTTP status, content type, bytes, sha256, image size, `x-bf-error`, tries, URL with the key masked. |
| `probes.csv` | How each provider answered a known company and a nonsense identifier, with the default fallback and with `fallback=404`. |
| `summary.md` | Coverage per provider × route × market, per provider, the best mix, which step found each logo, and images shared by 3+ companies (placeholders or one group logo for several companies). |
| `mix.csv` | The route the best mix picked for each ticker (a preferred share with no logo of its own takes its common share's). |
| `contact_sheet_kr.png`, `contact_sheet_us.png` | The 200 largest companies of each side with the chosen logo, rank, code, name and route. Look for wrong matches. |

Verdicts: `hit` (a real logo) · `miss` (404 = no logo) · `fallback` (200, but the image is the provider's placeholder,
found by hash from the probe) · `bad_request` (400, malformed identifier) — these are final; `pending` (logo.dev 202,
rechecked after 5½ minutes) · `rate_limited` · `error` are retried with backoff (max 5 tries).

## What each route needs, and where the identifiers come from

| Route | Identifier | Source | Count (2026-11-03 data) |
|---|---|---|---|
| Brandfetch `ticker/` and logo.dev `ticker/` | KR `005930.KS` (KOSPI, KONEX) / `247540.KQ` (KOSDAQ); US as in data.json (`BRK-B`) | data.json + KRX listing `Market` | all 3,250 |
| Brandfetch `ticker/` with the bare code | `005930` (Brandfetch documents no exchange suffix, so both forms are tried) | data.json | 2,476 KR |
| Brandfetch `isin/` and logo.dev `isin/` | `KR7005930003` | KRX listing `ISU_CD` (check digit verified); an ETF missing from the listing gets the derived ISIN | 2,476 KR, 0 US |
| Brandfetch `domain/` and logo.dev `/<domain>` | `samsung.com` | KRX company list `HomePage` (a preferred share uses its common share's) | 2,342 KR, 0 US |

- KONEX has no logo.dev suffix; `.KS` (Korea Exchange) is tried, and logo.dev says it also checks a market's other
  exchanges. logo.dev's list: `.KS` Korea Exchange, `.KQ` KOSDAQ.
- Domains left blank on purpose (logged by `build_tickers.py`): platform hosts (`blog.naver.com`, `facebook.com` …),
  malformed values (`http://www,cuckoo.co.kr`), and a domain listed for two different companies (19 domains, 41 rows, e.g.
  아모레퍼시픽 / 아모레퍼시픽홀딩스 → apgroup.com): a logo looked up by it could be the other company's or the group's.
- US ISINs: no free keyless source (they are built from licensed CUSIPs). US domains: none yet; if the US ticker routes
  miss many, Yahoo's company profile has a website field (one Yahoo call per stock, no key).
- DART 기업개황 `hm_url` (the spec's suggestion) needs the DART key, so it was **not** used; the KRX company list gives
  the same kind of homepage for 2,588 of 2,875 listed codes. Later, at no extra DART cost: `fetch_data.py` already calls
  `company.json` for every company (for the industry code, cached 180 days) and could keep `hm_url` too.

## Provider terms (read 2026-11-04) — what affects us

**Both providers forbid fetching their CDN images with a script.** That is why `run_test.py` loads every logo as an
`<img>` on a page in Chromium, paced and once, exactly as an app page would. It is still an automated test, so it is a
grey area: Brandfetch may refuse it (`302` with `x-bf-error: automated_traffic`); the runner then stops Brandfetch at
once and says so in `summary.md`. If that happens, options are: ask Brandfetch for a one-off coverage check
(brandfetch.com/developers/contact), check Brandfetch by eye on a page opened in a normal browser, or decide on
logo.dev alone.

### Brandfetch Logo API

Sources: [Logo API overview and guidelines](https://docs.brandfetch.com/logo-api/overview) ·
[parameters](https://docs.brandfetch.com/logo-api/parameters) ·
[stock ticker logos](https://docs.brandfetch.com/use-cases/stock-ticker-logos) ·
[terms (GTC)](https://brandfetch.com/terms) · [logo fair use](https://docs.brandfetch.com/guides/logo-fair-use)

- **Free, no attribution**: "Logo API is free to use and we don't ask for any attribution." Ticker, ISIN and crypto
  routes are free too. Key = client ID in `?c=`, meant to be visible in pages.
- **Hotlink only, no copies**: "We require logo links to be directly embedded in your applications"; the ticker page
  says "hotlink the CDN URL directly in the image src, don't download, cache, or re-host the file". Caching needs "a
  custom setup" (contact them). So the app must hotlink and we must not save logo files in the repo. (The general
  terms allow 30-day caching "when applicable"; the Logo API rules are stricter and are the ones that apply.)
- **No programmatic access**: "Programmatic access to logo images is not permitted"; scraping leads to a block; a valid
  client ID does not exempt a request from the `automated_traffic` check.
- **Referer required**: requests must carry a `Referer`; the page's referrer policy must be `origin`,
  `strict-origin-when-cross-origin` (the browser default) or similar. 뱁새 sets no referrer policy and its service
  worker does not touch other sites' requests, so this works today. Part G must not add `referrerpolicy="no-referrer"`.
- **Limits**: fair use 1,000,000 requests a month (soft). 1,000 requests per 5 minutes per IP and **2,400 per 5
  minutes per customer (all our users together, about 8 a second)**; over that → `429`. Each user's browser is its own
  IP, but the per-customer cap matters for the app: a list of 50 logos is 50 requests per new visitor. Lazy-loading
  and the browser cache help; watch it once logos ship.
- **No logo**: default is a `200` placeholder (transparent, or the Brandfetch mark); with `fallback/404` a `404` with an
  empty body (cached up to 7 days); `fallback/lettermark` draws a letter icon. Refusals carry `x-bf-error`.
- **No commercial / non-commercial distinction** for the Logo API. The GTC (Swiss law) forbid scraping, make the
  customer responsible for third-party trademarks (indemnity), and let Brandfetch suspend access.

### logo.dev

Sources: [image routes](https://www.logo.dev/docs/logo-images/introduction) ·
[ticker](https://www.logo.dev/docs/logo-images/ticker) · [ISIN](https://www.logo.dev/docs/logo-images/isin) ·
[attribution](https://www.logo.dev/docs/platform/attribution) · [fair use](https://www.logo.dev/docs/platform/fair-use) ·
[rate limits](https://www.logo.dev/docs/platform/rate-limits) · [caching](https://www.logo.dev/docs/platform/caching) ·
[self-hosting](https://www.logo.dev/docs/platform/self-hosting) · [API keys](https://www.logo.dev/docs/platform/api-keys) ·
[pricing](https://www.logo.dev/pricing) · [terms](https://www.logo.dev/legal/terms) (last updated 2026-10-29)

- **Keys**: the publishable key (`pk_…`) goes in `?token=` and is safe in page source. The secret key (`sk_…`) is for
  their server API only — we never ask for it; the scripts refuse an `sk_` key.
- **Attribution — check with Jack**: a *commercial* project on the free Community plan "must show a visible link"
  (`Logos provided by Logo.dev`, linking to logo.dev) on a public page. A project "you own as an individual and that
  earns nothing is personal" and needs none. 뱁새 is free, owned by Jack, no ads → personal, as long as that stays true.
  The 데이터 출처 line planned in Part G could carry the link anyway.
- **Hotlink, no copies from the CDN**: "Load Logo.dev CDN images in your users' browsers and apps. Don't fetch them
  from a script or a crawler." "Don't download from the CDN to build your own copy"; stored copies only through their
  API with the secret key. "Bulk scraping of logos for redistribution" is not fair use.
- **Limits (Community, free)**: 500,000 CDN requests a month, a **hard cap** (then `429` until the next month). A
  per-minute limit per account and per IP (number not published; `429` with `Retry-After`). Browsers cache each logo 24
  hours (`Cache-Control: max-age=86400`).
- **No logo**: default `200` with a generated monogram (a letter); `fallback=404` → `404`. `202` = first request for a
  domain they are still fetching (try again after a few minutes).
- **Domain restriction** (optional, dashboard → API keys → Allowed domains): limits the key to listed sites by
  `Referer`. Leave it off for this test (the test page is `127.0.0.1`); turn it on with `jacksungjinlee.github.io` when
  logos ship.
- **Terms**: no "unauthorized automated or non-human means"; the customer bears sole responsibility for third-party
  trademarks; liability capped at $1,000.

### Trademarks (both)

Logos stay their owners' trademarks. Using a company's logo to identify it (as a stock app does) is the accepted use;
don't alter logos or suggest the company endorses 뱁새.
