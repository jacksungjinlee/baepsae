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
    to `v2` in the cache key, in all five places (`update-data.yml` twice, `ci.yml` four times; a small PR), so a fresh
    copy is downloaded. The tests accept any version number as long as every place uses the same one, so no test edit
    is needed. If the step "브라우저 · 한글 글꼴 준비" fails on the font line instead, the runner's font setup changed:
    fix `tests/fonts/install.sh` in a PR.
  - `smoke_app` does not depend on any one company beyond the gate's must-have list (Jack, 11-12). Two scenes need a
    kind of company and pick it by rule: any company the data marks as reporting in a currency other than won
    (`stmtCur`), and any foreign company with a 9xxxxx code. If today's data has none, the run log says so loudly
    (`!! 확인 못 함`, a warning on the run page and a paragraph in the step summary), the scene counts as passed and
    the data is published; CI still checks those scenes on its own data, where a missing company is a failure.
    A company leaving the market never holds the data back. Never skip the check itself to get the data out.
- **CI runs on fixed data (since #104).** A pull request's checks no longer read the day's files: `smoke_app` uses a
  trimmed copy of the 2026-11-11 publish (`tests/fixtures/snapshot`, about 395 KB; its few filing rows carry made-up people's names), `smoke_v2` and `smoke_launch` use the
  2.0 test data (`tests/fixtures/v2`), and `smoke_app` and `smoke_v2` run on a test clock that starts at 07:00 KST on a
  fixed day (`tests/testclock.py`). So a pull request's code meets today's real data only in the daily run above, or when
  the three commands are run by hand: `python tests/real_data_check.py --data DIR`, `python tests/smoke_launch.py --data DIR`
  and `python tests/smoke_app.py --data DIR`. `CLAUDE.md` requires that before merging any PR that changes what the
  browser runs (a stopgap until the deploy runs them itself): put a fresh copy of the four files in a folder outside the
  checkout (`git fetch origin main`, then `git show origin/main:data.json > DIR/data.json` and so on), run the three
  commands and paste their result lines into the PR.
  To refresh the snapshot from a newer publish (only when a new field or a new kind of stock must be in it): run
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
