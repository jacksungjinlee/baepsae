# Dividend chart note: where to get the cause, date and ratio of a share-count change (research, 2026-11-08)

Research only. Nothing in the repo was changed. Live data used: the deployed `data.json` / `corp.json`
(pxDate 2026-11-06, publishedAt 2026-11-08 01:49 KST). DART research calls today: **394** (budget 600; log in
`/tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/divcause/calls.log`; no key or URL
with a key was printed or saved; raw responses in `.../scratchpad/divcause/dcache/`).

## 1. The short answer

- **Use the decision filings, not the 증자(감자) 현황.** Find them with `list.json` (by company, two narrow searches),
  then read the ratio and date from the structured 무상증자 API (`fricDecsn` / `pifricDecsn`) or, for 액면분할 and 주식병합
  (which have no API), from the filing document itself (`document.xml`, a fixed KRX form).
- Coverage on today's 63 `adj` stocks: the decision filings name a cause, a date and a ratio for **63 of 63**.
  The 증자(감자) 현황 gives a usable cause and date for **18 of 63** (29%) today, and it mostly never records 액면분할 or
  주식병합 even once the next report is out.
- The filings' ratio agrees with the pipeline's factor for **60 of 63**. **The other 3 are live wrong numbers on the site
  today**, not filing problems: 대한제강, 대동금속, 티엘비 (section 4). Their past dividends and today's yield are
  understated by 17-33%. This is disaster #1 (wrong data without knowing it) and should be fixed whether or not the note
  ships.
- Cost: about 3 calls per adjusted stock, only for adjusted stocks, cached until the stock's factors change. About
  200-250 calls in a full-DART run (on top of about 15,500), about 0-10 on a normal day. No extra full run; fits the
  one-full-run-a-day rule because the calls ride in the same run and the same cache file.

## 2. How `adj` is computed today (fetch_data.py)

- `enrich_with_dart` (l.1469) calls, per company, for the latest 사업보고서 year `fy` (2025 now, else 2024):
  `fnlttSinglAcntAll.json` (CFS, else OFS; annual and the current quarter) and `alotMatter.json` (배당에 관한 사항, tag
  `DIV2`). It also calls `company.json` (업종), `corpCode.xml` (once), and for disclosures `list.json` (pblntf_ty D,
  last 90 days, no company filter), `elestock.json` and `majorstock.json` (not cached). No other DART endpoints.
- `parse_dart_basis` (l.1296) keeps from the dividend table, for 당기/전기/전전기: `cash3` 현금배당금총액, `par3`
  주당액면가액, `eps3`/`ni3` 주당순이익 and its 순이익, `pdps` preferred dividends. `parse_dart_list` keeps `cs3` 자본금 and
  `ss3` 자본잉여금 (3 years).
- `div_basis` (l.2795):
  - N = 현금배당금총액 ÷ 주당 배당금 (shares that got the dividend), W = 순이익 ÷ EPS (only when the dividend is 0),
    I = 자본금 ÷ 액면가 (issued-share ceiling).
  - **f0** (today vs the latest report year): today's listed shares (KRX listing `shr` + listed preferred) ÷ N0 is the
    upper bound, ÷ I0 the lower bound. f0 = the only "clean" candidate (1, 2, 2.5, 3, 4, 5, 10, 20, 25, 50, 100 or the
    inverse, ±5%; 1 is ±10%) inside that range.
  - **g_i** (earlier years vs the latest year, inside one report): I0/I_i must be a clean factor; the par value changing
    by the same factor = 액면분할/병합; par unchanged = bonus issue only if 자본잉여금 did not grow; N0/N_i says whether the
    company restated that year's figure (g = 1) or not (g = the factor).
  - dpsF[i] = f0 × g_i, dps3a[i] = dps3[i] ÷ dpsF[i], divSt `adj` when some paying year has a factor ≠ 1.
- **The DART cache** (`.dart-cache/dart-v2.json.gz`, GitHub Actions cache) holds the parsed alotMatter and
  fnlttSinglAcntAll entries, company.json, and the corp map. Nothing about 증자/감자, decisions or share totals.
  What it can tell without new calls: for a change **inside** the 3 report years (20 of the 63), the kind (par changed by
  the same factor = 분할/병합; par same + 자본잉여금 not up = 무상증자). It cannot give any date, and it knows nothing about
  changes **after** the latest report (43 of the 63).

### Stocks marked `adj` in the live data: 63
Splits 15, consolidations (주식병합) 26, bonus issues 21, bonus + split 1 (코미코). 43 of the 63 changed after the 2025
report (most are the 2026 penny-stock 액면병합 wave); 20 changed inside 2023-2025.

010120 LS ELECTRIC, 086280 현대글로비스, 058470 리노공업, 082920 비츠로셀, 183300 코미코, 356860 티엘비, 083450 GST,
000670 영풍, 211050 인카금융서비스, 001510 SK증권, 340570 티앤엘, 092730 네오팜, 015360 INVENI, 036800 나이스정보통신,
003350 한국화장품제조, 079370 제우스, 084010 대한제강, 134380 미원화학, 448280 에코아이, 003920 남양유업, 425040 티이엠씨,
058430 포스코스틸리온, 023760 한국캐피탈, 001460 BYC, 001130 대한제분, 115310 인포바인, 199820 제일일렉트릭, 187870 디바이스,
265740 엔에프씨, 052260 현대바이오랜드, 001520 동양, 352090 스톰테크, 008040 사조동아원, 017650 대림제지, 092220 KEC,
357230 에이치피오, 205100 엑셈, 011370 서한, 058400 KNN, 095720 웅진씽크빅, 019680 대교, 007280 한국특강, 060560 HC홈센타,
256630 포인트엔지니어링, 072990 에이치시티, 012280 영화금속, 082850 우리바이오, 475460 미트박스, 020400 대동금속, 131090 시큐브,
033830 티비씨, 153490 우리이앤엘하루틴, 090410 덕신이피씨, 020180 대신정보통신, 333050 이노테나, 037330 인지디스플레,
356890 싸이버원, 008470 부스타, 359090 씨엔알리서치, 131180 딜리, 373170 엠아이큐브솔루션, 252500 세화피앤씨, 113810 디젠스.

Also checked: 4 `nc`/`nd` stocks with one adjusted year (484870 엠앤씨솔루션, 339770 교촌에프앤비, 336680 탑런토탈솔루션,
262840 아이퀘스트). The app shows no bars for nc/nd, so they need no note today.

## 3. The sources

### (a) 사업보고서 주요정보 「증자(감자) 현황」 `irdsSttus.json` — not reliable enough
Called for all 67 on the 2025 사업보고서 (67 calls), and for the 45 with a change after 2025 on the 2026 반기 and 3분기
reports (90 calls).
- **Splits and consolidations are mostly not recorded.** It is a capital-change table, and 액면분할/병합 don't change
  capital. Of 17 splits/consolidations effective in H1 2026, the 반기 report recorded 3 (HC홈센타, 씨엔알리서치, 딜리), all
  with the 형태 left as "-". 대한제분, LS ELECTRIC, INVENI, 포스코스틸리온, KEC, 웅진씽크빅 etc.: nothing. Inside the 2025
  report: 리노공업, 영풍, 싸이버원 recorded "주식분할"; 인카금융서비스, 남양유업, BYC, 시큐브 recorded nothing.
- **Bonus issues are usually there** ("무상증자"), but 네오팜 and 에이치피오 are missing.
- **형태 text is free text**: "무상증자", "주식분할", "무상감자", "-" (blank, used for splits, consolidations, mergers and
  old issues alike), "주식배당", typos ("보퉁주").
- **Quantity means different things**: 리노공업's split row has the total after (76,211,850); 영풍's has the increase
  (17,197,605 = 9 × before). A bonus row has the new shares, not the ratio. The par column has only the after-value.
- **Dates mean different things**: mostly the legal date (배정기준일 / 효력발생일), but the listing date for 티이엠씨,
  디바이스, 딜리.
- **Lag**: a change shows only in the next periodic report. 21 of the 43 post-report changes happened after 30 June and
  the 3분기 reports (due 16 Nov) are mostly not filed yet (only 2 of 45 were).
- Result for the 63: cause + date usable for **18** (inside 2023-25: 14 of 20; after the report: 4 of 43, all bonus
  issues). Ratio: derivable only for in-window splits (par3 from the dividend table) and bonus issues with a known
  before-count.

### (b) Decision filings — recommended
- `list.json` with `corp_code`, `bgn_de` = 1 Jan of (fy − 2), `end_de` = today, and **`pblntf_detail_ty=I001`**
  (거래소 수시공시: 주식분할결정, 주식병합결정) and **`B001`** (주요사항보고서: 무상증자결정, 유무상증자결정, 감자결정,
  유상증자결정). Both filters checked: I001 keeps 주식분할결정 (LS ELECTRIC, 98 rows) and 주식병합결정 (서한), B001 keeps
  무상증자결정 and 유무상증자결정 (현대글로비스, 티엘비). One page of 100 was enough for the stocks tested; a few busy
  filers may need a second. The company filter lifts DART's 3-month limit on the date range.
- **무상증자** → `fricDecsn.json` (same company + date range, 1 call): `nstk_ascnt_ps_ostk` (new shares per share),
  `nstk_asstd` (신주배정기준일), `nstk_lstprd` (listing), `bfic_tisstk_ostk`, `nstk_ostk_cnt`. It returns only the final
  (corrected) version of each decision (checked on 코미코, 디바이스, 티앤엘, 아이퀘스트).
  **유무상증자** → `pifricDecsn.json` (`fric_nstk_ascnt_ps_ostk`, `fric_nstk_asstd`, plus the rights part `piic_*`).
  **감자** → `crDecsn.json` (`bfcr_tisstk_ostk` / `atcr_tisstk_ostk`, `cr_std`, `cr_mth`).
- **주식분할결정 / 주식병합결정 have no DS005 API.** They are KRX 수시공시 (거래소 공시규정), not 자본시장법 주요사항보고서,
  so DS005 (36 APIs) has nothing for them; they appear in `list.json` as type I with the company as filer. The filing is a
  fixed KRX form, so `document.xml` (1 call, a zip) parses cleanly: "1주당 가액(원) 분할 전 / 분할 후", "발행주식총수
  보통주식(주) 전 / 후", "신주의 효력발생일", "신주권상장예정일", "주주총회예정일", "이사회결의일". Parsed 60 of 60
  documents (all versions).
- **Coverage: 63 of 63** have a decision whose ratio product can be compared; every one gives cause, date and ratio.
- **Agreement with the pipeline's factor: 60 of 63** (all 15 splits, all 26 consolidations, 코미코's ×5 = bonus ×2 then
  split ×2.5, and 18 of 21 bonus issues). The 3 disagreements are pipeline errors (section 4).
- Failure modes seen, and the handling:
  - **Corrections change the numbers.** 영화금속's first filing said 4:1 (500 → 2,000원), corrected the same day to 5:1;
    LS ELECTRIC's and 포스코스틸리온's first filings used the wrong share totals; 엑셈 and 인지디스플레 moved the effective
    date (twice for 인지디스플레, last on 25 Aug). Always use the newest version (`[기재정정]`), and take the ratio from
    the par values, not the share totals.
  - **Subsidiary filings** carry the parent's name: "유무상증자결정(종속회사의주요경영사항)" (LS ELECTRIC), "감자결정(자율공시)
    (종속회사의주요경영사항)" (우리이앤엘하루틴). Drop any report name with 종속회사/자회사.
  - **Dates in the decision are planned dates.** Use the latest correction, and name an event only if its date is on or
    before pxDate and the share count already shows it (the factor check below does this).
  - **Several events in one gap**: 코미코 (bonus then split), 영풍 (split + a 3.7% 주식배당), 에이치시티 (bonus + yearly
    주식배당), 아이퀘스트 (bonus ×2, bonus 10%, consolidation). Rights issues and mergers also change counts (대동금속,
    티엘비) and have no clean ratio.
  - **A par-only 감자** (HC홈센타 2024: 500 → 100원, no change in the share count) is not a share-count change; ignore
    when before = after.
  - No withdrawn (철회) decisions among these, but the rule must drop them.
- Calls in this research: list 140 for 67 stocks (with the wider `pblntf_ty=I` and `B`, a second page for a few),
  decision APIs 28, documents 60 (every version). With the narrow filters and newest-version-only documents: about 2 + 1 = **3 calls per stock**.

### (c) What is already in the cache — not enough
No new calls, but only a kind (no date, no ratio check) for the 20 in-report changes, and nothing for the 43 after the
report. Useful only as a second opinion for in-report splits (par3 must change by the same factor).

### Also useful: `stockTotqySttus.json` (주식의 총수 현황)
Exact 발행주식총수, 자기주식, 유통주식수 at each report date (1 call per report, cached for good). It is the right source for
{a} in the not-found line, and it is how the 3 errors were confirmed (e.g., 대동금속 3,189,166 at end-2025 → 6,378,332 at
30 June 2026 after the bonus → 9,073,532 today after a rights issue).

## 4. Three adjusted stocks show wrong numbers on the site today

| 종목 | Pipeline factor | What DART says | Shown now | With the filing's ratio |
|---|---|---|---|---|
| 084010 대한제강 | ×2 | 무상증자 0.6616554주 per share (2026-01-06); issued shares ×1.5 (24% treasury shares get none) | dps3a 250 · yield 3.36% | 301 · 4.05% |
| 020400 대동금속 | ×3 | 무상증자 1주 per share (2026-04-13), then a 유상증자 (Aug 2026): ×2 bonus, ×1.42 rights | 20 · 0.54% | 30 · 0.81% |
| 356860 티엘비 | ×2.5 | 유무상증자: 21% rights issue, then 무상증자 1주 per share (2026-07-20) | 180 · 0.68% | about 225 · 0.85% |

Why the pipeline picked them: f0 only knows that today's share count lies between today ÷ N and today ÷ I. Treasury
shares (대한제강) or a rights issue (대동금속, 티엘비) push that range over a clean number (2, 3, 2.5) that is not the real
ratio (1.66 is not a candidate). The in-report check (자본잉여금) does not run for changes after the report, so nothing
catches it. All three are ranked in the 배당 score (dz 78, 53, 54).
**Recommendation:** whenever DART names a share-count change whose ratio disagrees with the factor, do not adjust
(that year becomes `nc`), and log it loudly. It changes what users see for 3 stocks today, so it needs Jack's yes and a
line in the spec (Question 1). Later, the pipeline could adjust by the filing's exact ratio instead (1.66, 2), which would
also rescue some of today's 215 nc/nd stocks; not researched here.

## 5. Recommended rules for the note

For each year whose dpsF is not 1 (only those years have adjusted bars):
1. **Events.** From (b): splits and consolidations (ratio = par before ÷ par after, from the newest version of the
   document), bonus issues (ratio = 1 + `nstk_ascnt_ps_ostk`), 감자 with a share-count change. Drop 종속회사 filings,
   withdrawals, par-only 감자, and anything dated after pxDate.
2. **Date.** The legal date: 신주의 효력발생일 for 분할/병합, 신주배정기준일 for 무상증자. It decides which dividends were
   paid on which share basis, and it is the date the next 사업보고서 records. (The listing date is 1-25 days later; if Jack
   prefers "the day the stock started trading on the new count", use `list`/`nstk_lstprd` instead. Either way, one
   definition everywhere.)
3. **Which gap.** An event belongs to year i's adjustment when its date is after the end of year i (31 Dec for these
   companies; use the report's `stlm_dt`) and on or before pxDate. dpsF[i] must equal the product of the clean events in
   that gap. All 60 matches worked on the 31 Dec boundary (the 3 failures are ratio errors, not boundary ones). If a company moved its dividend record date into the next year and an
   event falls between 31 Dec and that record date, the check fails rather than guesses (then: no note, loud log).
4. **Classify, never guess:**
   - **ok**: the gap's 분할/병합/무상증자/감자 events with |ratio − 1| > 10% ("named events") have a ratio product equal to
     dpsF[i] (±0.5%). Changes of 10% or less (주식배당, small bonus issues, option exercises) are left out of the name and
     the product, the same tolerance the pipeline already uses. Kind: 분할 if ratio > 1 from a 주식분할결정; 병합 if < 1 from a 주식병합결정 (or a 감자 that cut the count); 무상증자
     from fricDecsn/pifricDecsn.
   - **mismatch**: named events exist but their product differs from dpsF[i] (대한제강 1.66 vs 2, 대동금속 2 vs 3, 티엘비
     2 vs 2.5), or there is no named event but a 유상증자/합병 decision sits in the gap (the count changed for a reason that
     is not a split) → do not adjust that year (nc), no note, loud log ("· 배당 맞춤 이유: 공시와 다른 배율 3 — …").
   - **not found**: no share-changing decision at all in the gap (no 분할/병합/무상/유상/감자/합병) → Jack's not-found line, with {a} = 발행주식총수 at the end of
     the oldest adjusted year (`stockTotqySttus`, 1 call, cached for good) and {b} = today's listed shares (`shr`).
     **Risk:** for a change after the latest report, "no filing" also fits an undetected rights issue or merger that happens
     to land on a clean number (the case in section 4). Suggest: for that gap, not found → don't adjust (nd); keep the
     not-found line for in-report changes that passed the par/자본잉여금 checks. (Question 2 below.)
   - **lookup failed** (DART down, limit): keep yesterday's result if dpsF and fy are unchanged; otherwise no cause note
     (the existing generic note stays true), loud log, gate WARN. Never show the not-found line for a lookup that did not
     happen.
5. **Several events**: name every named event in the gap, oldest first (a later gap's events are named too, since its
   bars were adjusted for them). Only 코미코 needs this today. Jack's templates are one event
   each, so a joined sentence is new wording (Question 3).
6. **Ratio wording**: split r = par before ÷ after (5, 10, 2.5); consolidation r = par after ÷ before (2, 5, 10); bonus x =
   `nstk_ascnt_ps_ostk` as filed (1, 2). A non-clean x (0.66) never reaches a note because it fails the factor check.
7. The "{year}년 사업보고서에는 바꾸기 전 금액인 {x}원으로 나와요" line needs no DART: show it when dpsF[0] ∉ {null, 1},
   {year} = `fy`, {x} = `dps3[0]` (the app already reads this as `adjFrom`).

## 6. Calls, cache and the one-full-run-a-day rule

- Only for KR stocks with some dpsF ∉ {null, 1} after `apply_div_basis` (63 today; up to about 100 at most), inside the
  same run, through `DartClient.get`, so status codes, the 020 limit stop and the "DART down" switch all apply.
- Per stock: `list.json` I001 + B001 (2 calls, rarely a second page) + 1 detail call per kind found (`fricDecsn` /
  `pifricDecsn` / `crDecsn`, or `document.xml` for the newest version of each 분할/병합 decision) ≈ **3 calls**;
  `stockTotqySttus` only for not-found cases.
- Cache in the same DART cache file, key `{corp}|divwhy|v1`, value = parsed events + the dpsF and fy they were checked
  against. Reuse while dpsF and fy are unchanged; refetch when they change (a new event changes today's share count, so
  it changes dpsF); revalidate after 90 days inside the existing 300-a-run budget.
- **Full-DART run (empty cache): about 200-250 extra calls** (63-80 stocks × 3); add it to `dart_full_estimate` (15,500 →
  about 15,750; target 16,000, limit 20,000). **Normal day: 0-10.** Nothing here needs a second full run: an empty cache
  is already that day's full run, and these calls are part of it.

## 7. Data shape and gate checks

data.json, KR stocks that have some dpsF ∉ {null, 1} (copied to corp.json like the other dividend fields):

```json
"dvWhy": {"v": 1, "st": "ok",
          "ev": [{"k": "split", "d": "2026-04-24", "r": 10, "rc": "20260312802368"}]}
"dvWhy": {"v": 1, "st": "ok",
          "ev": [{"k": "bonus", "d": "2026-05-27", "r": 2, "x": 1, "rc": "20260522000156"},
                 {"k": "split", "d": "2026-07-31", "r": 2.5, "rc": "20260716900397"}]}
"dvWhy": {"v": 1, "st": "nf", "a": 10000000, "b": 20000000}      (illustration; no live stock is nf)
```
`k` split · merge · bonus; `d` the legal date (KST, ISO); `r` the share factor of that event (split > 1, merge < 1,
bonus = 1 + x); `x` new shares per share (bonus only); `rc` the filing's 접수번호, so the app can link the filing as the
receipt. `st` ok · nf; mismatch years are not published as adj, so `mm` never appears in a file. Top-level
`divCheck.why = {ok, nf, mm, fail}` counts.

validate_data.py rows (all new, stricter-only):
1. Every KR stock with some dpsF ∉ {null, 1} has `dvWhy`, and no other stock has one (WARN when the reason is a failed
   lookup, so a DART outage cannot block publishing; FAIL on a `dvWhy` on a stock with no adjusted year).
2. `st` ∈ {ok, nf}; `v` = 1.
3. For `ok`: for each year i with dpsF[i] ∉ {null, 1}, the product of `r` over events with `d` > 31 Dec of (fy − i) and
   ≤ pxDate equals dpsF[i] within 0.5%. This catches a wrong ratio, a wrong date (event in the wrong gap) and a missing event.
4. Each event: `k` known; `r` a clean factor (2, 2.5, 3, 4, 5, 10, 20, 25, 50, 100 or inverse) with split > 1, merge < 1,
   bonus = 1 + x and x > 0; `d` a real date between 1 Jan of (fy − 2) and pxDate; `rc` 14 digits starting with a year
   ≤ pxDate's year.
5. For `nf`: no `ev`; `a`, `b` positive integers, a ≠ b, b = `shr`.
6. `divCheck.why` counts equal the stocks; WARN when `nf` > 0 or `mm` > 0 (names in the row), so Jack sees each one.
7. A test pinning today's three mismatches (대한제강, 대동금속, 티엘비) as non-adjusted, and 대한제분/리노공업/코미코/영화금속
   (the corrected filing) as `ok` with the expected events.

## 8. Questions for Jack (yes/no)

1. Stop adjusting the 3 stocks whose factor the filing contradicts (대한제강, 대동금속, 티엘비) and treat any future
   mismatch the same way (their bars disappear and they show "배당을 줘요" until the pipeline can use exact ratios)?
2. For a change after the latest report where no filing is found: don't adjust (safer), instead of adjusting with the
   not-found line?
3. 코미코-type double events: OK to join two of your sentences, e.g. "회사가 2026년 5월 27일에 무상증자로 1주마다 새
   주식 1주를 나눠 줬고, 2026년 7월 31일에 주식 1주를 2.5주로 나눴어요(액면분할). …"? (new wording, needs your yes)
4. Date = the legal date (효력발생일 / 신주배정기준일), not the first trading day on the new count?

## 9. Per-stock table (63 adj + 4 partly adjusted nc/nd)

"관찰 배율" = dpsF (today's shares ÷ that year's basis). (a) = rows of 증자(감자) 현황 near the event ("없음" = not recorded;
"3분기 보고서 전" = the change came after 30 June and the 3분기 report is not filed yet). (b) = the decision filing's
ratio and dates. "맞음?" = the product of (b)'s ratios equals every adjusted year's dpsF. The proposed line follows
Jack's templates; "…" is the rest of his sentence.

| # | 종목 | divSt | 관찰 배율 dpsF (당기/전기/전전기) | (a) 증자(감자) 현황 irdsSttus | (b) 결정 공시 (list + DS005 / 문서) | 맞음? | 제안 문구 |
|---|---|---|---|---|---|---|---|
| 1 | 010120 LS ELECTRIC | adj | 5/5/5 | split: 없음 | split 액면 5000→1000 (×5) 효력 2026-04-10 상장 2026-04-13 · 판 2개(정정 포함) | 예 | 회사가 2026년 4월 10일에 주식 1주를 5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 3,000원으로 나와요. |
| 2 | 086280 현대글로비스 | adj | 1/1/2 | bonus: 2024-07-15 형태 '무상증자' 수량 37,500,000 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2024-07-15 상장 2024-08-02 | 예 | 회사가 2024년 7월 15일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 3 | 058470 리노공업 | adj | 1/5/5 | split: 2025-04-14 형태 '주식분할' 수량 76,211,850 액면 100 | split 액면 500→100 (×5) 효력 2025-04-14 상장 2025-04-25 | 예 | 회사가 2025년 4월 14일에 주식 1주를 5주로 나눴어요(액면분할). … |
| 4 | 082920 비츠로셀 | adj | 1/2/2 | bonus: 2025-12-11 형태 '무상증자' 수량 22,467,264 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2025-12-11 상장 2025-12-30 | 예 | 회사가 2025년 12월 11일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 5 | 183300 코미코 | adj | 5/5/5 | bonus: 2026-05-27 형태 '무상증자' 수량 10,084,626 액면 500; split: 없음 (3분기 보고서 전) | bonus 1주당 1주 (×2) 배정기준일 2026-05-27 상장 2026-06-15; split 액면 500→200 (×2.5) 효력 2026-07-31 상장 2026-08-21 · 판 2개(정정 포함) | 예 | 회사가 2026년 5월 27일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. 회사가 2026년 7월 31일에 주식 1주를 2.5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 1,400원으로 나와요. |
| 6 | 356860 티엘비 | adj | 2.5/2.5/2.5 | bonus: 없음 (3분기 보고서 전) | bonus 1주당 1주 (×2) 배정기준일 2026-07-20 상장 2026-08-07 · 유상증자와 함께(유무상) | **아니오** | 권장: 맞춤을 멈추고(nc) 문구 없음 — 공시: 무상증자 ×2 (+ 유상증자 21%) ≠ 맞춘 ×2.5. 이유를 못 찾은 게 아니라 배율이 틀린 경우라 '찾지 못했지만' 문구는 맞지 않아요 |
| 7 | 083450 GST | adj | 1/1/2 | bonus: 2024-06-27 형태 '무상증자' 수량 9,300,515 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2024-06-27 상장 2024-07-24 | 예 | 회사가 2024년 6월 27일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 8 | 000670 영풍 | adj | 1/10/10 | split: 2025-04-16 형태 '주식분할' 수량 17,197,605 액면 500 | split 액면 5000→500 (×10) 효력 2025-04-16 상장 2025-04-25 · 판 2개(정정 포함) | 예 | 회사가 2025년 4월 16일에 주식 1주를 10주로 나눴어요(액면분할). … |
| 9 | 211050 인카금융서비스 | adj | 1/1/5 | split: 없음 | split 액면 500→100 (×5) 효력 2024-04-17 상장 2024-04-29 | 예 | 회사가 2024년 4월 17일에 주식 1주를 5주로 나눴어요(액면분할). … |
| 10 | 001510 SK증권 | adj | –/0.5/0.5 | merge: 없음 | merge 액면 500→1000 (×0.5) 효력 2026-04-09 상장 2026-04-27 · 판 2개(정정 포함) | 예 | 회사가 2026년 4월 9일에 주식 2주를 1주로 합쳤어요(주식병합). … |
| 11 | 340570 티앤엘 | adj | 2/2/2 | bonus: 없음 (3분기 보고서 전) | bonus 1주당 1주 (×2) 배정기준일 2026-08-07 상장 2026-08-28 | 예 | 회사가 2026년 8월 7일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … 2025년 사업보고서에는 바꾸기 전 금액인 1,500원으로 나와요. |
| 12 | 092730 네오팜 | adj | 1/1/2 | bonus: 없음 | bonus 1주당 1주 (×2) 배정기준일 2024-10-31 상장 2024-11-22 | 예 | 회사가 2024년 10월 31일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 13 | 015360 INVENI | adj | 5/5/5 | split: 없음 | split 액면 5000→1000 (×5) 효력 2026-04-08 상장 2026-04-09 · 판 2개(정정 포함) | 예 | 회사가 2026년 4월 8일에 주식 1주를 5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 5,400원으로 나와요. |
| 14 | 036800 나이스정보통신 | adj | 5/5/5 | split: 없음 (3분기 보고서 전) | split 액면 500→100 (×5) 효력 2026-07-31 상장 2026-08-18 | 예 | 회사가 2026년 7월 31일에 주식 1주를 5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 1,100원으로 나와요. |
| 15 | 003350 한국화장품제조 | adj | 5/5/5 | split: 없음 | split 액면 500→100 (×5) 효력 2026-04-15 상장 2026-04-20 | 예 | 회사가 2026년 4월 15일에 주식 1주를 5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 300원으로 나와요. |
| 16 | 079370 제우스 | adj | 1/1/3 | bonus: 2024-01-17 형태 '무상증자' 수량 20,677,990 액면 500 | bonus 1주당 2주 (×3) 배정기준일 2024-01-17 상장 2024-02-08 | 예 | 회사가 2024년 1월 17일에 무상증자로 1주마다 새 주식 2주를 나눠 줬어요. … |
| 17 | 084010 대한제강 | adj | 2/2/2 | bonus: 2026-01-06 형태 '무상증자' 수량 11,457,199 액면 1,000 | bonus 1주당 0.661655주 (×1.6617) 배정기준일 2026-01-06 상장 2026-01-26 | **아니오** | 권장: 맞춤을 멈추고(nc) 문구 없음 — 공시: 무상증자 1주당 0.6616554주 (×1.66) ≠ 맞춘 ×2. 이유를 못 찾은 게 아니라 배율이 틀린 경우라 '찾지 못했지만' 문구는 맞지 않아요 |
| 18 | 134380 미원화학 | adj | 10/10/10 | split: 없음 | split 액면 1000→100 (×10) 효력 2026-04-02 상장 2026-04-13 · 판 2개(정정 포함) | 예 | 회사가 2026년 4월 2일에 주식 1주를 10주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 4,500원으로 나와요. |
| 19 | 448280 에코아이 | adj | 1/3/3 | bonus: 2025-05-08 형태 '무상증자' 수량 19,754,086 액면 500 | bonus 1주당 2주 (×3) 배정기준일 2025-05-09 상장 2025-05-28 | 예 | 회사가 2025년 5월 9일에 무상증자로 1주마다 새 주식 2주를 나눠 줬어요. … |
| 20 | 003920 남양유업 | adj | 1/1/10 | split: 없음 | split 액면 5000→500 (×10) 효력 2024-11-12 상장 2024-11-20 · 판 2개(정정 포함) | 예 | 회사가 2024년 11월 12일에 주식 1주를 10주로 나눴어요(액면분할). … |
| 21 | 425040 티이엠씨 | adj | 1/1/2 | bonus: 2024-01-25 형태 '무상증자' 수량 10,626,108 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2024-01-03 상장 2024-01-25 | 예 | 회사가 2024년 1월 3일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 22 | 058430 포스코스틸리온 | adj | 10/10/10 | split: 없음 | split 액면 5000→500 (×10) 효력 2026-04-10 상장 2026-04-23 · 판 2개(정정 포함) | 예 | 회사가 2026년 4월 10일에 주식 1주를 10주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 1,085원으로 나와요. |
| 23 | 023760 한국캐피탈 | adj | 0.5/0.5/0.5 | merge: 없음 (3분기 보고서 전) | merge 액면 500→1000 (×0.5) 효력 2026-08-01 상장 2026-08-27 · 판 2개(정정 포함) | 예 | 회사가 2026년 8월 1일에 주식 2주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 40원으로 나와요. |
| 24 | 001460 BYC | adj | 1/1/10 | split: 없음 | split 액면 5000→500 (×10) 효력 2024-04-12 상장 2024-04-17 | 예 | 회사가 2024년 4월 12일에 주식 1주를 10주로 나눴어요(액면분할). … |
| 25 | 001130 대한제분 | adj | 10/10/10 | split: 없음 | split 액면 5000→500 (×10) 효력 2026-04-24 상장 2026-05-18 | 예 | 회사가 2026년 4월 24일에 주식 1주를 10주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 4,000원으로 나와요. |
| 26 | 115310 인포바인 | adj | 5/5/5 | split: 없음 | split 액면 500→100 (×5) 효력 2026-04-14 상장 2026-04-28 | 예 | 회사가 2026년 4월 14일에 주식 1주를 5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 1,200원으로 나와요. |
| 27 | 199820 제일일렉트릭 | adj | 1/1/2 | bonus: 2024-05-22 형태 '무상증자' 수량 11,110,000 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2024-05-22 상장 2024-06-11 | 예 | 회사가 2024년 5월 22일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 28 | 187870 디바이스 | adj | 2/2/2 | bonus: 2026-05-22 형태 '무상증자' 수량 6,733,451 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2026-04-29 상장 2026-05-22 | 예 | 회사가 2026년 4월 29일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … 2025년 사업보고서에는 바꾸기 전 금액인 650원으로 나와요. |
| 29 | 265740 엔에프씨 | adj | 1/–/2 | bonus: 2025-08-20 형태 '무상증자' 수량 8,931,800 액면 100 | bonus 1주당 1주 (×2) 배정기준일 2025-08-20 상장 2025-09-08 | 예 | 회사가 2025년 8월 20일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 30 | 052260 현대바이오랜드 | adj | 1/1/2 | bonus: 2024-05-20 형태 '무상증자' 수량 15,000,000 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2024-05-20 상장 2024-06-13 | 예 | 회사가 2024년 5월 20일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 31 | 001520 동양 | adj | –/–/0.5 | merge: 없음 (3분기 보고서 전) | merge 액면 500→1000 (×0.5) 효력 2026-07-07 상장 2026-07-20 · 판 2개(정정 포함) | 예 | 회사가 2026년 7월 7일에 주식 2주를 1주로 합쳤어요(주식병합). … |
| 32 | 352090 스톰테크 | adj | 1/1/2 | bonus: 2024-09-02 형태 '무상증자' 수량 13,436,499 액면 100 | bonus 1주당 1주 (×2) 배정기준일 2024-09-02 상장 2024-09-30 | 예 | 회사가 2024년 9월 2일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 33 | 008040 사조동아원 | adj | –/0.1/0.1 | merge: 없음 (3분기 보고서 전) | merge 액면 500→5000 (×0.1) 효력 2026-08-13 상장 2026-09-02 | 예 | 회사가 2026년 8월 13일에 주식 10주를 1주로 합쳤어요(주식병합). … |
| 34 | 017650 대림제지 | adj | 5/5/5 | split: 없음 (3분기 보고서 전) | split 액면 500→100 (×5) 효력 2026-09-22 상장 2026-10-13 | 예 | 회사가 2026년 9월 22일에 주식 1주를 5주로 나눴어요(액면분할). … 2025년 사업보고서에는 바꾸기 전 금액인 100원으로 나와요. |
| 35 | 092220 KEC | adj | –/–/0.2 | merge: 없음 | merge 액면 500→2500 (×0.2) 효력 2026-04-30 상장 2026-05-20 | 예 | 회사가 2026년 4월 30일에 주식 5주를 1주로 합쳤어요(주식병합). … |
| 36 | 357230 에이치피오 | adj | 1/1/2 | bonus: 없음 | bonus 1주당 1주 (×2) 배정기준일 2024-03-07 상장 2024-03-29 | 예 | 회사가 2024년 3월 7일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 37 | 205100 엑셈 | adj | 0.2/–/– | merge: 없음 (3분기 보고서 전) | merge 액면 100→500 (×0.2) 효력 2026-10-13 상장 2026-11-02 · 판 2개(정정 포함) | 예 | 회사가 2026년 10월 13일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 42원으로 나와요. |
| 38 | 011370 서한 | adj | 0.2/0.2/0.2 | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-08-14 상장 2026-09-01 | 예 | 회사가 2026년 8월 14일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 50원으로 나와요. |
| 39 | 058400 KNN | adj | 0.1/0.1/0.1 | merge: 없음 (3분기 보고서 전) | merge 액면 500→5000 (×0.1) 효력 2026-07-07 상장 2026-07-28 | 예 | 회사가 2026년 7월 7일에 주식 10주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 25원으로 나와요. |
| 40 | 095720 웅진씽크빅 | adj | 0.5/0.5/– | merge: 없음 | merge 액면 500→1000 (×0.5) 효력 2026-04-28 상장 2026-05-15 | 예 | 회사가 2026년 4월 28일에 주식 2주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 85원으로 나와요. |
| 41 | 019680 대교 | adj | 0.5/–/– | merge: 없음 (3분기 보고서 전) | merge 액면 500→1000 (×0.5) 효력 2026-08-19 상장 2026-09-10 | 예 | 회사가 2026년 8월 19일에 주식 2주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 60원으로 나와요. |
| 42 | 007280 한국특강 | adj | 0.5/–/– | merge: 없음 | merge 액면 500→1000 (×0.5) 효력 2026-04-17 상장 2026-05-07 | 예 | 회사가 2026년 4월 17일에 주식 2주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 200원으로 나와요. |
| 43 | 060560 HC홈센타 | adj | 0.2/0.2/– | merge: 2026-04-16 형태 '-' 수량 101,552,007 액면 500 (형태 불명확) | merge 액면 100→500 (×0.2) 효력 2026-04-16 상장 2026-04-30 | 예 | 회사가 2026년 4월 16일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 10원으로 나와요. |
| 44 | 256630 포인트엔지니어링 | adj | 0.2/–/– | merge: 없음 | merge 액면 100→500 (×0.2) 효력 2026-04-28 상장 2026-05-18 · 판 2개(정정 포함) | 예 | 회사가 2026년 4월 28일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 10원으로 나와요. |
| 45 | 072990 에이치시티 | adj | 1/2/– | bonus: 2025-11-27 형태 '무상증자' 수량 7,040,890 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2025-11-27 상장 2025-12-16 | 예 | 회사가 2025년 11월 27일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 46 | 012280 영화금속 | adj | 0.2/0.2/0.2 | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-08-13 상장 2026-08-28 · 판 2개(정정 포함) | 예 | 회사가 2026년 8월 13일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 35원으로 나와요. |
| 47 | 082850 우리바이오 | adj | 0.2/–/– | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-08-19 상장 2026-09-07 | 예 | 회사가 2026년 8월 19일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 20원으로 나와요. |
| 48 | 475460 미트박스 | adj | 3/–/– | bonus: 없음 (3분기 보고서 전) | bonus 1주당 2주 (×3) 배정기준일 2026-09-17 상장 2026-10-13 | 예 | 회사가 2026년 9월 17일에 무상증자로 1주마다 새 주식 2주를 나눠 줬어요. … 2025년 사업보고서에는 바꾸기 전 금액인 100원으로 나와요. |
| 49 | 020400 대동금속 | adj | 3/3/3 | bonus: 2026-04-13 형태 '무상증자' 수량 3,189,166 액면 1,000 | bonus 1주당 1주 (×2) 배정기준일 2026-04-13 상장 2026-05-07 | **아니오** | 권장: 맞춤을 멈추고(nc) 문구 없음 — 공시: 무상증자 ×2, 그 뒤 유상증자 ≠ 맞춘 ×3. 이유를 못 찾은 게 아니라 배율이 틀린 경우라 '찾지 못했지만' 문구는 맞지 않아요 |
| 50 | 131090 시큐브 | adj | 1/0.2/0.2 | merge: 없음 | merge 액면 100→500 (×0.2) 효력 2025-04-29 상장 2025-05-20 | 예 | 회사가 2025년 4월 29일에 주식 5주를 1주로 합쳤어요(주식병합). … |
| 51 | 033830 티비씨 | adj | 0.2/0.2/0.2 | merge: 없음 | merge 액면 500→2500 (×0.2) 효력 2026-06-12 상장 2026-07-03 · 판 2개(정정 포함) | 예 | 회사가 2026년 6월 12일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 14원으로 나와요. |
| 52 | 153490 우리이앤엘하루틴 | adj | 0.2/–/– | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-07-31 상장 2026-08-20 | 예 | 회사가 2026년 7월 31일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 20원으로 나와요. |
| 53 | 090410 덕신이피씨 | adj | –/0.2/0.2 | merge: 없음 (3분기 보고서 전) | merge 액면 100→500 (×0.2) 효력 2026-08-14 상장 2026-08-31 · 판 2개(정정 포함) | 예 | 회사가 2026년 8월 14일에 주식 5주를 1주로 합쳤어요(주식병합). … |
| 54 | 020180 대신정보통신 | adj | 0.2/0.2/0.2 | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-07-29 상장 2026-08-19 | 예 | 회사가 2026년 7월 29일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 30원으로 나와요. |
| 55 | 333050 이노테나 | adj | 0.2/0.2/0.2 | merge: 없음 | merge 액면 100→500 (×0.2) 효력 2026-04-29 상장 2026-05-20 | 예 | 회사가 2026년 4월 29일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 24원으로 나와요. |
| 56 | 037330 인지디스플레 | adj | 0.2/0.2/0.2 | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-10-13 상장 2026-11-06 · 판 3개(정정 포함) | 예 | 회사가 2026년 10월 13일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 35원으로 나와요. |
| 57 | 356890 싸이버원 | adj | 1/1/2.5 | split: 2024-04-13 형태 '주식분할' 수량 7,149,795 액면 200 | split 액면 500→200 (×2.5) 효력 2024-04-13 상장 2024-05-07 | 예 | 회사가 2024년 4월 13일에 주식 1주를 2.5주로 나눴어요(액면분할). … |
| 58 | 008470 부스타 | adj | 2/2/2 | bonus: 없음 (3분기 보고서 전) | bonus 1주당 1주 (×2) 배정기준일 2026-07-23 상장 2026-08-14 | 예 | 회사가 2026년 7월 23일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … 2025년 사업보고서에는 바꾸기 전 금액인 80원으로 나와요. |
| 59 | 359090 씨엔알리서치 | adj | 0.2/0.2/– | merge: 2026-06-09 형태 '-' 수량 45,976,574 액면 500 (형태 불명확) | merge 액면 100→500 (×0.2) 효력 2026-06-09 상장 2026-06-30 | 예 | 회사가 2026년 6월 9일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 10원으로 나와요. |
| 60 | 131180 딜리 | adj | 0.2/0.2/– | merge: 2026-05-18 형태 '-' 수량 23,480,000 액면 500 (형태 불명확) | merge 액면 100→500 (×0.2) 효력 2026-04-28 상장 2026-05-18 | 예 | 회사가 2026년 4월 28일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 90원으로 나와요. |
| 61 | 373170 엠아이큐브솔루션 | adj | 3/–/3 | bonus: 2026-02-10 형태 '무상증자' 수량 10,075,860 액면 100 | bonus 1주당 2주 (×3) 배정기준일 2026-02-10 상장 2026-03-04 | 예 | 회사가 2026년 2월 10일에 무상증자로 1주마다 새 주식 2주를 나눠 줬어요. … 2025년 사업보고서에는 바꾸기 전 금액인 200원으로 나와요. |
| 62 | 252500 세화피앤씨 | adj | 0.2/0.2/0.2 | merge: 없음 (3분기 보고서 전) | merge 액면 100→500 (×0.2) 효력 2026-08-12 상장 2026-09-01 | 예 | 회사가 2026년 8월 12일에 주식 5주를 1주로 합쳤어요(주식병합). … 2025년 사업보고서에는 바꾸기 전 금액인 10원으로 나와요. |
| 63 | 113810 디젠스 | adj | –/0.2/– | merge: 없음 (3분기 보고서 전) | merge 액면 500→2500 (×0.2) 효력 2026-07-07 상장 2026-07-28 | 예 | 회사가 2026년 7월 7일에 주식 5주를 1주로 합쳤어요(주식병합). … |
| 64 | 484870 엠앤씨솔루션 | nc | 3/3/– | bonus: 없음 | bonus 1주당 2주 (×3) 배정기준일 2026-06-29 상장 2026-07-29 | 예 | 회사가 2026년 6월 29일에 무상증자로 1주마다 새 주식 2주를 나눠 줬어요. … 2025년 사업보고서에는 바꾸기 전 금액인 2,491원으로 나와요. |
| 65 | 339770 교촌에프앤비 | nd | 1/–/2 | bonus: 2025-01-01 형태 '무상증자' 수량 24,982,540 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2025-01-01 상장 2025-01-20 | 예 | 회사가 2025년 1월 1일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 66 | 336680 탑런토탈솔루션 | nc | 1/2/– | bonus: 2025-05-30 형태 '무상증자' 수량 19,572,779 액면 500 | bonus 1주당 1주 (×2) 배정기준일 2025-05-30 상장 2025-06-20 | 예 | 회사가 2025년 5월 30일에 무상증자로 1주마다 새 주식 1주를 나눠 줬어요. … |
| 67 | 262840 아이퀘스트 | nc | 0.5/0.5/– | bonus: 2025-04-29 형태 '무상증자' 수량 1,843,905 액면 100; merge: 없음 | bonus 1주당 0.1주 (×1.1) 배정기준일 2025-04-29 상장 2025-05-23; merge 액면 100→200 (×0.5) 효력 2026-04-16 상장 2026-05-07 | 예 (10% 이하 변화는 이름에서 빼는 규칙으로) | nc 라 막대·문구 없음. 규칙대로면 전기·당기는 2026년 4월 16일 주식병합(2주→1주)으로 설명돼요. 2025년 무상증자 0.1주(10%)는 파이프라인도 같은 기준으로 봐요(오차 10%) |

## 10. Research calls (2026-11-08, one DART key, not a pipeline run)

| Endpoint | Calls | What for |
|---|---|---|
| irdsSttus.json | 157 | 2025 사업보고서 for 67 stocks; 2026 반기 + 3분기 for 45 |
| list.json | 145 | 67 stocks × (pblntf_ty I and B, a second page for a few) + 5 filter checks |
| document.xml | 60 | every version of every 주식분할결정 / 주식병합결정 |
| fricDecsn / pifricDecsn / crDecsn | 28 | stocks whose list shows those decisions |
| stockTotqySttus.json | 3 | share totals for the mismatch checks |
| corpCode.xml | 1 | download stalled and was stopped (counted anyway); the corp map from an earlier session's file was used (checked: 005930 → 00126380, 005380 → 00164742) |
| **Total** | **394** | |

Scripts and raw data: `/tmp/claude-0/-home-user-baepsae/1e263423-8dac-53f1-985c-907b07f88dab/scratchpad/divcause/`
(`step1.py` irds + lists, `step2.py` decisions + documents, `parse_docs.py`, `step3.py` interim irds, `match.py`,
`table.py`; results `match.json`, `table.json`, `docs_parsed.json`).
