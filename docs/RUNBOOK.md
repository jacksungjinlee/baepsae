# 뱁새 runbook — when something goes wrong

One page for Jack. Claude Code does every step below for you; this page says what each alarm means and what to ask for.

## What watches the site

| What | When | What it tells you |
|---|---|---|
| **Watchdog** (GitHub Actions, `watchdog.yml`) | Every day at 16:37 KST (weekends too), and 10 minutes after every data run or deploy | Opens one GitHub issue named **뱁새 데이터 경보** (label `data-alert`) and mentions you, so GitHub emails you. It comments on the same issue while the problem lasts and closes it with **정상화됐어요** when the site is healthy again. |
| **healthchecks.io** (outside GitHub) | Expects a "still alive" ping from the watchdog at least once a day (6 hours grace) | Emails you if the pings stop, which means GitHub Actions itself stopped running and nothing else could warn you. It also emails when the watchdog reports a problem. |
| **09:13 KST check** (Claude scheduled task, Tue–Sat) | Every morning | Says whether the morning data is in and lists any warnings from the publication gate. |

What the watchdog checks, on the files users actually download: the four data files pass `validate_data.py --live`; after
15:30 KST, the Korean price date is the last finished trading day (checked against KRX's final listing and Yahoo's KOSPI,
both separate from our pipeline); the last daily run and the last deploy succeeded; the daily run is still switched on;
the pages users get are the current build, the site's `data.json` is exactly the published copy, and the site does not
serve the `docs/` folder (two of its files must answer "not found").

## What an alert means

- **Users still see the last good data, with its date.** The publication gate refuses to publish anything that fails
  its checks, so a failed run leaves yesterday's numbers in place, labelled with yesterday's date. The app itself shows a
  warning ("N일째 갱신이 멈췄어요") once publishing has stopped for more than 4 days.
- **The screen check (since 2026-11-12).** After the gate passes and before anything is published, the daily run opens
  the apps in a real browser on today's data:
  - `tests/real_data_check.py`: the four files read cleanly, today's data has every field 2.0 needs, and the two apps
    agree on the growth basis for every Korean stock;
  - `tests/smoke_launch.py --data .`: 2.0 on the four files exactly as they will be published (first visit, the
    portfolio builder, a Korean company page, a saved portfolio, the way into the old app);
  - all of `tests/smoke_app.py --data .`: the old app's checks on today's stocks and numbers. These scenes first set
    the publish time and due dates to "just now" (and fill in a missing price date or built-in fund row), so they do
    not check the dates users will see; the gate checks those.

  If any of the three fails, the run ends red and publishes nothing, exactly like a gate failure: yesterday's data stays
  up. Nothing retries inside the run; the next scheduled start is the retry. The run's summary page has a "발행 전 화면
  검사" section with the three results. Each step has a time limit (10, 10 and 30 minutes); running over is a failure.
  A normal check takes about 3 minutes.
  - The check comes after the DART cache is saved, so a held publish never turns the next start into a full-DART run.
  - The browser comes from GitHub's cache (`playwright-v1-ubuntu-24.04-…`), never from Ubuntu's package server. A run
    that finds no cache downloads it from Playwright's server and saves it before the check starts. The Korean font
    the tests need is a file in the repo (`tests/fonts`). If the browser cannot start, the publish is held.
  - If the cached browser itself is broken (no scene can open a page although the install step passed): raise `v1`
    to `v2` in the cache key, in all six places (`update-data.yml` twice, `ci.yml` four times; a small PR), so a fresh
    copy is downloaded. The tests accept any version number as long as every place uses the same one, so no test edit
    is needed. If the step "브라우저 · 한글 글꼴 준비" fails on the font line instead, the runner's font setup changed:
    fix `tests/fonts/install.sh` in a PR.
  - A company leaving the market must never hold the data back (Jack, 11-12), so `smoke_app` on real data
    (`--data`) follows the day's data in three places:
    - Two scenes need a kind of company and pick it by rule: any company the data marks as reporting in a currency
      other than won (`stmtCur`), and foreign companies with a 9xxxxx code (one for the "외화로…" line, a second one
      with a currency mark for the currency line). If today's data has none, the scene counts as passed and the run
      says so: `!! 확인 못 함` in the log, a warning on the run page, a paragraph in the step summary.
    - **If the `stmtCur` line appears although yesterday's data had such companies, suspect the pipeline, not the
      market:** DART's currency reading was probably lost, and then a company that files in dollars (두산밥캣,
      아남전자) is published with its dollar amounts read as won. Since 2026-11-12 the gate compares the marks with
      the previous publication (row "원화가 아닌 재무제표 표시가 직전 발행보다 사라지지 않음"):
      - **It fails** when a Korean company (code not starting with 9) had the mark in the previous publication, lost it
        today, and has amounts filled — the exact case where dollar amounts would be shown as won (Jack, 2026-11-12;
        judged against the previous publication, not a list of names). If a company really switched to reporting in
        won, add it to `STMT_WON_SWITCH` in `validate_data.py` (one line, with Jack's yes); it then only warns. It also fails when, of the marked companies still listed, at
        least 3 remain and more than half lost the mark (the "DART's currency reading was lost" day), and when the
        previous `corp.json` cannot be read or was not given. A failure is sticky: the comparison stays with the last good publication, so every later run fails
        until the pipeline is fixed. `--bootstrap` is not the fix (it skips the comparison and makes the bad day the
        new baseline).
      - **It warns**, naming the companies (domestic ones with amounts first), when any marked company lost its mark,
        or when more than half of the marked companies are gone from today's list. **The warning appears on that one
        run only:** once it publishes, the next run compares with a file that no longer has the mark. The same holds
        when a Korean marked company is missing from the day's list (also a warning, "오늘 목록에 없는 국내 회사"): check
        that company again after the next publish, because a day later its amounts could come back without the mark. So act on it the
        same morning: open the named companies on the site, and if dollar amounts show as won, revert or fix the
        pipeline and start a run by hand.
      - Branch dry runs with DART off fail this row too, like the other DART rows (expected).
      - When the gate's "previous publication" moves off `main` (v17.6 3b), the new source must include `corp.json`,
        or every run fails on this row (loudly, but it holds the publish).
    - The old app has 75 built-in stocks (`src/detail.jsx` `BASE_STOCKS`); the gate guarantees that 17 of them are in
      the data, and guarantees a beta and volatility for none of the US ones. When a built-in stock is missing from
      the day's data, or has a blank price, beta or volatility, or when the gold price is an estimate, the old app
      correctly shows its "예시 가격" or "금현물은 … 추정치예요" notice. The check then requires exactly that notice
      (not "no notice") and says so: `!! 알림` in the log, a warning, the step summary.
      **Up to 3 such stocks; with more the check fails and nothing is published** (one clear line at the top of the
      result: "내장 종목 N개가 …"), because many at once is the pipeline (for example every US beta blank), not the
      market. The number counts every built-in stock that is missing today, not only new ones, so:
      - when a built-in company has left the market for good (delisted, merged), remove it from `BASE_STOCKS` in a
        small PR (an old-app change: rebuild, Jack's yes). Until then it shows as `!! 알림` every morning and uses up
        one of the three;
      - if the check fails, first look at the names: long-gone companies mean the list needs that PR; several fresh
        blanks at once mean the pipeline. Do not raise the number.
    - One scene needs three must-have stocks (005930, 005380, 105560) to have a dividend yield; the gate lets one
      must-have stock without dividend data through with a warning (Jack, 11-05), so the scene fills a blank one in
      its own copy and says so in the log.
    - `!! 확인 못 함` and `!! 알림` lines are on a green run, where nobody looks by default. The 09:13 morning check
      must report them to Jack: its instructions are extended for the warnings titled "발행 전 화면 검사 …" as an
      after-merge step of #106 (until that is done, nothing reads them).
    - Without `--data` (CI) none of this applies: a missing company or any such notice is a failure, as before.
    - Never skip the check itself to get the data out.
- **CI runs on fixed data (since #104).** A pull request's checks no longer read the day's files: `smoke_app` uses a
  trimmed copy of the 2026-11-11 publish (`tests/fixtures/snapshot`, about 395 KB; its seven insider-trade rows are made up except for company and date), `smoke_v2` and `smoke_launch` use the
  2.0 test data (`tests/fixtures/v2`), and `smoke_app` and `smoke_v2` run on a test clock that starts at 07:00 KST on a
  fixed day (`tests/testclock.py`). So a pull request's code meets today's real data only in the daily run above, or when
  the three commands are run by hand: `python tests/real_data_check.py --data DIR`, `python tests/smoke_launch.py --data DIR`
  and `python tests/smoke_app.py --data DIR`. `CLAUDE.md` requires that before merging any PR that changes what the
  site serves, or the check scripts and their helpers (a stopgap until the deploy runs them itself): put a fresh copy of
  the four files the site serves in a folder outside the checkout (`git fetch origin data`, then
  `git show origin/data:data.json > DIR/data.json` and so on for corp, disc and macro; never copy them over the
  checkout's own files), run the three commands and paste their result lines and the data's date (`pxDate`) into the
  PR. If one fails, run the same three on `main`'s code with the same folder: if `main` fails too it is not the PR;
  tell Jack. The served files already passed these checks when they were published, so look first at what differs
  from that run: the hour (one old-app scene, "늦음 시각 · 주말 뒤", fails if it happens to run in the last seconds
  before midnight KST; run it again), the machine (fonts, node), or code merged since.
  To refresh the snapshot from a newer publish (only when a new field or a new kind of stock must be in it; the
  script refuses a day on which a built-in stock of the old app is missing or blank, or gold is an estimate): run
  `python3 tests/fixtures/snapshot/make_snapshot.py` in a checkout that has that day's four files, then run all of
  `tests/smoke_app.py` and `pytest tests/test_snapshot.py`, in a PR.
- The issue's first line says which case it is. If it says the files **on the site** failed the checks
  ("검사를 통과하지 못했어요"), users may be seeing wrong numbers: treat that one as urgent.
- An issue whose first line starts with **[시험]** is a test that Claude ran on purpose. The site is fine.
- The same test also sends healthchecks.io one failure signal, so Jack gets a "down" email, then rechecks the real site
  and, if it is fine, sends the normal signal ("up" email, usually within a minute) and closes the [시험] issue. A "down"
  email with no "up" email after it means the recheck found a real problem.

## What to do

Open a new Claude Code Cloud session and paste (replace N with the issue number, which is also written in the issue):

> 뱁새 데이터 경보 이슈 #N 이 떴어. 로그를 보고 원인을 찾아서 CLAUDE.md 규칙대로 고치고 PR 열어줘.

Claude reads the run logs, fixes the cause by the CLAUDE.md rules (fix the data or the code, never loosen a check), and
tells you what happened in plain words.

## Roll back

- **A bad code release** (the app looks broken after a merge): Claude opens the merged pull request, presses
  **Revert**, and merges the revert pull request. The deploy runs by itself after the merge. Ask: "뱁새 마지막 머지를
  되돌려 줘."
- **Bad data** (the numbers are wrong and the gate missed it): Claude reverts the last commit on the `data` branch
  (and, until v17.6 part 3b, the same data commit on `main`), then starts **Actions → Deploy → Run workflow**. Users get
  the previous day's data back within about 10 minutes. Ask: "뱁새 어제 데이터로 되돌려 줘."

## Where to look

- The issue list on GitHub, label `data-alert` (there is only ever one open).
- Your email: GitHub notifications (the issue mentions you) and healthchecks.io.
- The site's 기준 date, on your phone.
- GitHub → Actions: runs of 시세 데이터 갱신 (daily data), Deploy (puts code and data on the site), Watchdog, ci (tests on
  every pull request).

## How the pieces fit (since v17.6)

- **`main`** holds the code. Every pull request must pass the `ci` check (build, all tests, phone-size smoke tests).
- **`data`** is a branch that holds only the four data files (`data.json`, `corp.json`, `disc.json`, `macro.json`). Only
  the daily run writes to it, and only after the publication gate and (since 2026-11-12) the screen check passed: each
  leaves a fingerprint (sha256) of the four files it checked, and the upload refuses any file that doesn't match either
  one. It never force-pushes.
  The first daily run after v17.6 creates the branch by itself.
- **Deploy** builds the pages from `main`, takes the four files from `data`, runs the gate's `--live` check on exactly the
  folder it is about to publish, and only then publishes. It runs after every merge to `main` and after every daily run
  that published new data. Settings → Pages → Source has been **GitHub Actions** since 2026-11-06. Never switch it back
  to "Deploy from a branch": GitHub would then serve `main` as it is, without the publication gate and with the `docs/`
  folder, whose licensed pictures must not be offered as downloads. Deploy leaves `docs/` out of the site.
  Since 2026-11-12 Deploy also leaves out the development folders and files the site never reads (`tests/`, `tools/`,
  `data/`, `styleguide/` and the build and pipeline files at the top; the two lists are in `tools/assemble_site.py`) and
  refuses to publish if one gets in. A branch deploy would serve them again, including the test data under `tests/`.
- Until v17.6 part 3b, the daily run still also commits the data to `main`, so the site works either way.
- **`data/market_holidays.csv`** (v19.1c) lists every weekday the Korean exchange (KR) or the NYSE (US) is closed, for
  whole years (now 2026–2027). From it each publish records `nextPub` (the next morning new data is due: the earlier of
  the two markets' next trading days, plus one day) and `staleAfter` (that day's last scheduled start, 14:47 KST, plus 2
  hours). Once the app part ships (a later PR), the app shows its stale warning when `staleAfter` has passed without a
  newer file; weekends and holidays stay quiet. GitHub starts afternoon runs 7–8 hours late, so at `staleAfter` the
  day's retries may not have run yet: the warning then means "the morning publish was missed".
  Keep the table current:
  - Add a 임시공휴일 or an NYSE special closure (e.g. a national day of mourning) as soon as it is announced. Without it,
    the morning after such a day gets a false stale warning, and the gate's '다음 발행 예정' row warns ("예정일이 오늘 이전").
  - Add the next year's rows every December (KRX publishes its holiday list in late December; the NYSE list is out
    years ahead), with a source in every row and at least 8 weekday closures per market and year. The table only sets
    the warning time, so it never stops a run or a publish (Jack, 2026-11-07): when it is short, missing or broken, the
    run logs it loudly, the gate warns (the 09:13 morning check reads it) and days past the table follow the weekday
    rule, so a warning may come a day early around a holiday, never late. The gate warns from 45 days before the
    table ends.
  - The gate also warns when the last 90 days of index bars disagree with the table (a missed or wrong holiday); the
    index bars are right (one-off holidays and US mourning-day closures come at short notice). Every problem with
    `nextPub`/`staleAfter` warns and never blocks a publish. After a table edit, the live-site check may warn once
    (the published file was computed with the old table) until the next publish.
  - The 2027 KR rows 노동절 대체 휴일 (5/3) and 제헌절 대체 휴일 (7/19) follow the 2026 law changes and still need KRX's
    own notice.
- **Exchange-rate history and stock splits** (v19.6a data, for 2.0's 팔았어요 · 배당 받았어요; three gate rows, stricter only):
  - `macro.json` `fxHist` is the dollar rate (USD/KRW, Yahoo `USDKRW=X`) for every day since 2016-01-01. The last three
    years are the same series the run uses for `fx`, so it always ends on `fxDate` with the value `fx`; only the older
    part is downloaded again (one call). A US record dated in the past saves that day's rate from it. The last day is
    the bar Yahoo had at publish time and the next run rewrites it with the final close (the same as `fx` always was:
    2026-11-11 was 1,338.3 at the 06:40 publish and 1,341.9 final).
  - If Yahoo's long history fails, the run takes the older part from yesterday's `macro.json` (only if it ends at most 10
    days before today's `fxDate`) and the gate row **환율 이력 (fxHist)** warns ("출처 kept"). If that fails too, the file
    has no `fxHist`: the row warns "없음", and until the next publish the app refuses past-dated US records with its
    approved line ("환율 정보를 불러오지 못해 …"). Nothing wrong is shown, so neither case blocks the publish.
    **FAIL** means the history itself is broken (out of order, a gap of more than 7 days, a jump of more than 10% between
    two rows, a value outside 900–2,000, not starting in the first week of 2016, not ending on `fxDate` and `fx`, or
    ending on today's date, which would be an unfinished bar).
    Every rate saved from it stays in users' records, so never loosen the row; ask Claude to find the cause.
  - `data.json` `splits` lists the last three years of US stock splits, `[code, date, ratio]` (ratio = new shares per old
    share; the date is the first US trading day on the new count). It comes from the same Yahoo download as the prices
    (no extra calls). Yahoo also writes spin-offs as "splits" with ratios like 1253:1000 (GE, GE Vernova); those are not
    share-count changes, so only clean ratios are kept (the reduced fraction has a side of 20 or less: 10:1, 1:15, 3:2,
    a 5% stock dividend 21:20) and the rest are named in the log. Known gap: Ryanair's ADS ratio change on 2024-09-30
    (each ADS became 2.5) is written by Yahoo as 2499:1000 and is left out. Korean splits are not in the list yet.
  - **주식 분할 목록 (splits)** fails on a broken list (shape, a ratio of 1 or outside 0.001–1000 or not clean, a date
    after today, a code not in today's data, the same stock and date twice), and when the list is missing although
    yesterday's file had one. It warns when the list is missing on a day yesterday's file had none either, when part of
    it was taken over from yesterday's file ("출처 kept" or "part": the run could not read the split column), or when a
    split is dated after the US price date (the boundary day: check that the stock's price is already on the new count).
  - **주식 분할 목록 변화 (직전 발행본과)** warns when a split from yesterday's list is gone (other than one older than three
    years), its ratio changed, or a split dated more than 7 days ago appears for a stock that was already listed. 2.0
    stores the split with a user's records once they record on that stock, so a split that changes afterwards leaves
    those users on the old value. The gate cannot tell a correction from a mistake, and blocking would hold back every
    price too, so it only warns and names the stocks: tell Jack which stock; whether stored records need fixing is an
    app decision.
- **`logos`** is a branch that holds only `logos/` (company logo pictures plus `index.json`), made once from logo.dev
  Pro on 2026-11-06 and checked by eye. Deploy copies it into the site; if the branch is missing or fails its check,
  Deploy warns and publishes without logos (every company shows its coloured letter mark). Logos never go on `main`.
- **`logos-run`** is a record branch (not on the site) with the checked folder the logo tool works on: the same `logos/`,
  the switched-off pictures in `dropped/`, and the review records (`drops.csv`, `keeps.csv`, `adds.csv`, `review.csv`,
  `run.json`).
  To change one logo later: copy that branch into a new folder, switch a wrong logo to its letter mark with
  `python3 tools/logos/logodev_fetch.py --drop CODE --dir FOLDER` (or bring back a checked one with `--keep CODE`),
  push with `bash tools/push_logos_branch.sh FOLDER/logos`, run Deploy, then save the changed folder back to
  `logos-run` as a new commit. Never push the GitHub artifact of a logo run (`logo-dev-fetch`) as it is: that is the
  unchecked run, from before the review. To fetch one or two companies again (a paid lookup, 2 credits each: only with
  Jack's yes, and only while logo.dev is on a plan that allows it): run the logo job with `only` set to their codes (and `route` = `ticker` to skip the DART homepage), look at its
  artifact, then `python3 tools/logos/logodev_fetch.py --add-from ARTIFACT_FOLDER --dir FOLDER` adds the checked logos
  to the copy of `logos-run`; push and deploy as above.
  To retry every Korean letter mark at once (2026-11-07): run the logo job with `letters_only` (it reads `logos-run`'s
  `logos/`, `review.csv` and `drops.csv`, so pictures already rejected are not asked for again)
  and, if wanted, `extra_routes` (an ISIN lookup, 2 credits, and a brandmark lookup, 3 credits, only for companies whose
  ticker and homepage gave nothing usable; a brandmark wider than 2:1 is dropped). It refuses a cap above 2,000 credits
  ($20) unless `over_20_dollars_ok` is ticked, which needs Jack's yes first. Look at every new logo on its sheet: the
  automatic checks do not catch photos, banners, old logos or another company's logo. Add only the checked ones with
  `--add-from ARTIFACT_FOLDER --dir FOLDER --codes CODE,CODE` (a retry is never added whole), then push and deploy.
- **Group marks** (Jack, 2026-11-07): a company still showing a letter mark may get its group's main mark, only when
  its own website shows that same mark as its logo and the picture used is the group's main mark, never a sister
  company's own logo (e.g. not "SAMSUNG HEAVY INDUSTRIES" for 삼성전기). Look at both first, then
  `python3 tools/logos/logodev_fetch.py --group-mark CODE=FROM,CODE=FROM --dir FOLDER --reason "..."` (an exact copy of
  FROM's picture, flagged `group-mark`; recorded in `groups.csv`).
- **Homepage icons** (Jack, 2026-11-07): the company's own homepage icon from the site-icon survey
  (`tools/logos/site_icons.py` on `claude/logos-site-icons`), 96 px or more, every quality check, never the same picture
  as another company's logo, each looked at first. Jack asked for the largest icon: logos are stored at 128 px, so any
  icon of 128 px or more gives the same picture; for an icon under 128 px, check the site's other icons (link rel=icon,
  apple-touch-icon, manifest) and use the largest:
  `--add-site-icons SURVEY_FOLDER --codes CODE,CODE --dir FOLDER` (route `site`, flagged `homepage-icon`; `sites.csv`).
  Before the first homepage icon goes live, the 데이터 출처 line must read "회사 로고: Logo.dev, 일부는 각 회사 홈페이지.
  로고의 권리는 각 회사에 있어요." (Jack, 2026-11-07).
- After pushing the `logos` branch and running Deploy, check the live `logos/index.json` (its count and a new code).
  On 2026-11-07 a Deploy of the same `main` commit two minutes after another one reported success but the site kept
  the older files; running Deploy once more published them.
- A new paid logo run needs Jack's yes: after this run he moves logo.dev back to the free plan. Never delete the
  logo.dev account, because its terms cover the logos we host.
- GitHub switches off scheduled workflows in public repositories after 60 days without repository activity. The daily
  data commits count as activity; on the 1st of every month the watchdog also switches both scheduled workflows back on
  through GitHub's API. If GitHub Actions stops completely, healthchecks.io is the alarm.

## Known limits: 기록 and the phone clock

뱁새 2.0 keeps each 가진 종목 portfolio's 내 규칙 limits (한 종목 · 한 업종) with the time they were saved, and also keeps a
copy of them beside the saved records, so a tab of the earlier app cannot drop them. When two copies disagree, the one
saved later wins. Four rare cases can still bring back an older setting (Jack, 2026-11-08). None of them touch
holdings, purchases or notes, and the fix is always the same: open 내 규칙 정하기 and press 저장 again.

- **The phone's clock was more than a day fast.** A 저장 made then carries a time more than a day ahead, which the app
  does not believe. Once the clock is right again, an older copy (from another open tab, or 기록 불러오기 of a file
  without limits) wins over it, so the limits go back to the earlier ones.
- **The phone's clock was 24 to 48 hours fast.** That 저장's time becomes believable again about a day later, and can then
  win over a later 저장 made with the right clock, without the 합쳤어요 message.
- **The phone's clock was set back by more than a day.** Two copies saved while it was set back are compared fairly,
  but a 저장 made before the clock went back can look newer than one made after, so an older setting can win (the app
  then says 합쳤어요).
- **A portfolio deleted in a tab of the earlier app.** The earlier app does not know the copy of the limits kept beside
  the records, so that copy stays. If the portfolio is brought back later with 기록 불러오기 from an older file that has
  no limits, its old limits come back too.
